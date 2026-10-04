# Phase 1: Lab snapshot export + synthesis kind

**Plan set:** `SERA_LAB_SITE_PLAN.md`
**Analysis:** `20261004-211729-H54F_code_analyzer.md`
**Satisfies:** R3, R6, R7. Every experiment reaches the web as `web/data/lab.json`, kept in sync by `lab stage` with no human step (R3). Batch syntheses get their own insight kind, so the journal and overview can find them (R6). R7 (cross-cutting): the snapshot carries the whole record (every method, trial curve, insight and seen idea), not a summary.
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab` (+ `commands/lab.py`)

---

## Goal

After this phase:
- `python -m seer_engine lab export-json` turns the lab database into the exact `web/data/lab.json` bytes the plan index's Interface Contract describes.
- `lab stage` writes that file under the same exclusive lock as the database and `git add`s both.
- The committed `lab/lab.sqlite` is at schema v2, which accepts `insight --kind synthesis`.
- The committed `web/data/lab.json` matches the committed database byte for byte. An engine test guards this.

**Prototype status:** every code block below was applied to a scratch copy of the tree and run. Results: 40/40 lab tests passed (the new file plus the existing `test_lab_store`, `test_lab_runner` and `test_lab_methods`), and `ruff check` was clean. The full engine suite showed 1912 passed, 286 skipped (PG). Its one failure, `test_store_dirs_are_gitignored`, came only from the scratch copy, which had no `.gitignore`. The generated snapshot of the current lab is 399,157 bytes.

### Decision: the sync guard and v1 databases (asked by the phase scope)

This phase does **both** of the following:

1. **`snapshot()` is schema-version agnostic.** It reads only the columns that v1 and v2 share and never reads `meta`. A v1 database therefore exports through a read-only connection, and the export is identical before and after migration (tested). The sync guard opens the committed DB with `store.connect_readonly` (SQLite `mode=ro`). It never runs the migration and never writes. The test also asserts the file's sha256 is unchanged.
2. **This phase migrates and commits `lab/lab.sqlite` at v2.** Running `lab stage` on the worktree's committed DB calls `connect()`, which migrates it, and then writes `web/data/lab.json`.

Why both: a main checkout or explorer session still holding a v1 file gets migrated by its next `lab` command. That changes the database bytes but not the snapshot bytes, because the snapshot contains no schema version. So the guard never fails just because a migration happened.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing. `lab stage`'s `git add` now uses absolute paths: it was `git add -- lab.sqlite` with `cwd=lab/`, and is now `git add -- <abs db> <abs json>` with `cwd=lab/`.

**Creates:**
- `store.connect_readonly(path=COMMITTED_DB) -> sqlite3.Connection` (`store.py`)
- `store.schema_version(conn) -> str | None` (`store.py`)
- `store._migrate(conn)` (private) (`store.py`)
- `store._INSIGHTS_TABLE: str`, `store._INSIGHTS_TRIGGERS: tuple[str, str]` (private DDL) (`store.py`)
- `store.SNAPSHOT_VERSION = 1`, `store.EXPECTED_FAILURE_SEP = "\n\nExpected failure: "` (`store.py`)
- `store.snapshot_path(db: Path) -> Path`: `<db>.resolve().parent.parent / "web/data/lab.json"` (`store.py`)
- `store.snapshot(conn) -> dict[str, Any]`, `store.snapshot_json(conn) -> str`, `store.write_snapshot(conn, path) -> bool` (`store.py`)
- `seed.P7A_BAR_ROWS = 2_490_793`, `seed.P7A_SYMBOLS_REQUESTED = 1_061`, `seed.P7A_SYMBOLS_SERVED = 539`, `seed.P7A_DIVIDEND_ROWS = 28_206` (`seed.py`)
- `seed.benchmark_curves() -> dict[str, list[tuple[str, float]]]`, with keys `spy_tr` and `spy_price` (`seed.py`)
- CLI `lab export-json [--out PATH]` (`commands/lab.py`, handler `_export_json`)
- `engine/tests/test_lab_snapshot.py`
- generated file `web/data/lab.json` (new directory `web/data/`)

**Signature / value changes:**
- `store.SCHEMA_VERSION`: `"1"` -> `"2"`.
- `store.INSIGHT_KINDS`: gains `"synthesis"` as its 6th member. `lab insight --kind` picks it up through `choices=store.INSIGHT_KINDS`.
- `store.connect(path)`: same signature. It now migrates v1 -> v2, closes the connection on failure, and raises `LabError` on an unknown schema version.
- `lab stage`: it still prints `staged <db>`, and now also prints `staged <json>`.
- The committed `lab/lab.sqlite`: binary change. `meta.schema_version='2'`, and the `insights` table has been rebuilt.

**Snapshot details the contract left open.** The reconciler must check phase 2 against these:
- `summary.byStatus` holds **every** `store.STATUSES` key in `STATUSES` order, with zero counts included: `idea, registered, rejected, dev-eligible, promoted, test-passed, test-failed, paper, blocked-data`.
- `asOf` is `""` for an empty lab. Never `null`.
- Key order inside every object is the contract's order, as listed in the index.
- `curve` and `benchmark` points are 2-element JSON arrays `[isoDate, number]`.
- `failed` labels are exactly the six in the index.
- `gate.testStart` is computed: `dates.next_session(dev.DEV_END)`, which gives `2015-10-19`.
- `gate.minTrades` comes from `dev._MIN_TRADES`.
- `devStart` and `storeStart` come from `research.STORE_START`.

**Requires (from earlier phases):** none.

**Leaves alone (owned by others):**
- `web/lib/sera/*` and every `web/` code file (Phases 2–6). This phase writes only the data file `web/data/lab.json`.
- `.github/workflows/engine-ci.yml` (Phase 7)
- both lab `SKILL.md` files, `docs/ROADMAP.md`, `web/package_readme.md` (Phase 7)

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/store.py` | modify | docstring (l.1–19); `SCHEMA_VERSION` (l.40); `INSIGHT_KINDS` (l.68); insights DDL extracted ahead of `_SCHEMA` (l.77); `_SCHEMA`'s insights block (l.149–162); `connect` (l.203–217) + `connect_readonly`, `schema_version`, `_migrate`; `add_insight` docstring (l.422–423); new web snapshot section appended after `as_mapping` (l.502–503) |
| `engine/src/seer_engine/lab/seed.py` | modify | store-fact constants after `P7A_REPORT` (l.30); `benchmark_curves()` before `seed()` (l.75) |
| `engine/src/seer_engine/commands/lab.py` | modify | docstring (l.12, l.14); `stage` help (l.87); `export-json` subparser (l.91); `_stage` (l.280–294); new `_export_json` before `_seed` (l.308); `_HANDLERS` (l.328) |
| `engine/tests/test_lab_snapshot.py` | create | migration, read-only v1 export, contract shape, determinism, CLI export/stage, sync guard |
| `lab/lab.sqlite` | regenerate | migrated to schema v2 by `lab stage` (Step 6) |
| `web/data/lab.json` | create (generated) | `lab stage` output (Step 6) |

## Implementation Steps

### Step 1: Schema v2 constants and the insights DDL
**File:** `engine/src/seer_engine/lab/store.py:1-19`, `:40`, `:68`, `:77`, `:149-162`

**Change 1a, module docstring.** Insert these lines after line 16 (`- ``ideas_seen``: …`) and before the blank line that precedes `` ``journal_mode`` stays DELETE ``:
```python
- ``insights``: the lab journal (observations, hypotheses, data and feature wishes, risks, and
  batch syntheses). Triggers refuse every UPDATE and DELETE.

Schema versions (``meta.schema_version``): 1 is the first lab; 2 adds the ``synthesis`` insight
kind. ``connect`` migrates an older database in place; ``connect_readonly`` never does.

``snapshot`` / ``snapshot_json`` turn a database (v1 or v2) into the web's ``web/data/lab.json``
(seertrade.site/sera). ``lab stage`` writes it next to the database and stages both.
```

**Change 1b, line 40.** Replace `SCHEMA_VERSION = "1"` with:
```python
SCHEMA_VERSION = "2"  # 2: the synthesis insight kind (see _migrate)
```

**Change 1c, line 68.** Replace the `INSIGHT_KINDS` line with:
```python
INSIGHT_KINDS: tuple[str, ...] = (
    "observation", "hypothesis", "data-wish", "feature-wish", "risk", "synthesis",
)
```

**Change 1d.** Directly before `_SCHEMA = f"""` (line 77), insert:
```python
# The insights table and its two triggers, one statement each. ``_SCHEMA`` creates them on a new
# database; ``_migrate`` recreates them when it rebuilds a v1 table (SQLite cannot alter a CHECK).
_INSIGHTS_TABLE = f"""CREATE TABLE IF NOT EXISTS insights (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    kind      TEXT NOT NULL CHECK (kind IN ({_quoted(INSIGHT_KINDS)})),
    title     TEXT NOT NULL CHECK (length(trim(title)) > 0),
    body      TEXT NOT NULL CHECK (length(trim(body)) > 0),
    method_id TEXT REFERENCES methods(id),
    added     TEXT NOT NULL
)"""
_INSIGHTS_TRIGGERS: tuple[str, ...] = (
    """CREATE TRIGGER IF NOT EXISTS insights_no_update BEFORE UPDATE ON insights
BEGIN SELECT RAISE(ABORT, 'insights are append-only: add a newer one instead'); END""",
    """CREATE TRIGGER IF NOT EXISTS insights_no_delete BEFORE DELETE ON insights
BEGIN SELECT RAISE(ABORT, 'insights are append-only'); END""",
)

```

**Change 1e, inside `_SCHEMA` (lines 149–162).** Replace the whole block from `CREATE TABLE IF NOT EXISTS insights (` through the `insights_no_delete` trigger's `END;` with:
```python
{_INSIGHTS_TABLE};

{_INSIGHTS_TRIGGERS[0]};

{_INSIGHTS_TRIGGERS[1]};
```
The surrounding blank lines stay as they are. The `trials_no_update` trigger follows next, as before.

**Impact:**
- A new database gets the v2 CHECK. SQLite stores the CREATE text without `IF NOT EXISTS`, so a migrated database's `sqlite_master` rows for `insights` are byte-identical to a fresh v2 database's. The test asserts this.
- `_SCHEMA` keeps running through `executescript` exactly as before.

### Step 2: `connect` migrates; `connect_readonly`, `schema_version`, `_migrate`
**File:** `engine/src/seer_engine/lab/store.py:203-217`
**Change:** Replace `connect` (lines 203–217) with the four functions below. `_migrate` calls `begin_immediate`, which is defined later in the module. That is fine at runtime.
**Code:**
```python
def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    """Open (creating when missing) the lab database with the schema, triggers and transitions,
    migrating an older database to ``SCHEMA_VERSION`` first."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=120)  # parallel explorer sessions share one file
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = DELETE")
        with conn:
            conn.executescript(_SCHEMA)
            conn.executemany("INSERT OR IGNORE INTO transitions (src, dst) VALUES (?, ?)", TRANSITIONS)
            conn.execute(
                "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)", (SCHEMA_VERSION,)
            )
        _migrate(conn)
    except BaseException:
        conn.close()
        raise
    return conn


def connect_readonly(path: Path = COMMITTED_DB) -> sqlite3.Connection:
    """Open an existing lab database read-only, exactly as it is: no schema, no migration, no
    write (``mode=ro``). For the snapshot sync guard, which must not touch the committed file."""
    path = Path(path).resolve()
    if not path.is_file():
        raise LabError(f"no lab database at {path}")
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def schema_version(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    return None if row is None else str(row[0])


def _migrate(conn: sqlite3.Connection) -> None:
    """Bring an older database up to ``SCHEMA_VERSION`` in one transaction under the write lock.

    v1 -> v2 adds the ``synthesis`` insight kind. SQLite cannot alter a CHECK, so ``insights`` is
    rebuilt: the v1 table is renamed aside, the v2 table is created from ``_INSIGHTS_TABLE``,
    every row is copied with its id, the AUTOINCREMENT counter is carried over, the v1 table is
    dropped (which drops its triggers and fires none), and the two append-only triggers are
    created on the new table. The triggers come last: while the v1 table exists its triggers
    hold their names, and ``CREATE TRIGGER IF NOT EXISTS`` would silently skip them.

    Parallel sessions may connect at once, so the version is read again after
    ``BEGIN IMMEDIATE``: only the first one migrates, the others find v2 and do nothing.
    """
    if schema_version(conn) == SCHEMA_VERSION:
        return
    begin_immediate(conn)
    try:
        version = schema_version(conn)
        if version == "1":
            seq = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = 'insights'").fetchone()
            conn.execute("ALTER TABLE insights RENAME TO insights_v1")
            conn.execute(_INSIGHTS_TABLE)
            conn.execute(
                "INSERT INTO insights (id, kind, title, body, method_id, added) "
                "SELECT id, kind, title, body, method_id, added FROM insights_v1 ORDER BY id"
            )
            conn.execute("DROP TABLE insights_v1")
            if seq is not None:
                cur = conn.execute(
                    "UPDATE sqlite_sequence SET seq = max(seq, ?) WHERE name = 'insights'", (seq[0],)
                )
                if cur.rowcount == 0:
                    conn.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('insights', ?)", (seq[0],))
            for trigger in _INSIGHTS_TRIGGERS:
                conn.execute(trigger)
            conn.execute("UPDATE meta SET value = ? WHERE key = 'schema_version'", (SCHEMA_VERSION,))
        elif version != SCHEMA_VERSION:
            raise LabError(
                f"lab database schema version {version!r} is unknown to this code (expects {SCHEMA_VERSION})"
            )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
```
**Impact:**
- **Fresh DB:** `INSERT OR IGNORE` writes `'2'`, and `_migrate` returns at once.
- **v1 DB:** migrated once. `sqlite_sequence` is updated as follows:
  - the rename moves the `insights` row to `insights_v1`;
  - copying rows with explicit ids writes a new `insights` row;
  - the DROP removes the `insights_v1` row;
  - the `max(seq, old)` step keeps the counter even if the old value was ever ahead.
- **Older code on a v2 DB:** v1 code (an old checkout) still opens it. Its `INSERT OR IGNORE '1'` is a no-op, and it only fails if it reads a `synthesis` row, which it never validates. This matches the index's Rollback note.
- The connection is now closed if the schema step or migration fails. Before this change it leaked.

### Step 3: `add_insight` docstring
**File:** `engine/src/seer_engine/lab/store.py:422-423`
**Change:** Replace the two docstring lines of `add_insight` with:
```python
    """Append one entry to the lab journal: an observation across methods, a hypothesis worth
    testing, data or a feature the lab lacks, a risk, or a batch synthesis (the state of the
    search after a batch of methods). The food-for-thought record, shown at seertrade.site/sera."""
```
The validation code is unchanged: it already checks `kind not in INSIGHT_KINDS`.

### Step 4: The web snapshot
**File:** `engine/src/seer_engine/lab/store.py`, appended after `as_mapping` (the last function, line 502–503)
**Change:** Append this new section. The imports inside `snapshot()` are lazy, for two reasons:
- `seed` imports `store`, so a top-level import would be circular.
- `backtest.dev` and `research` are heavy, and store's other callers should not pay that cost.

The module already imports `json`, `math`, `os`, `Mapping` and `Any` at top level.
**Code:**
```python
# --------------------------------------------------------------------------- web snapshot

SNAPSHOT_VERSION = 1
EXPECTED_FAILURE_SEP = "\n\nExpected failure: "  # how lab ideas write their hypothesis


def snapshot_path(db: Path) -> Path:
    """The web snapshot of a database: ``<repo>/web/data/lab.json`` for ``<repo>/lab/lab.sqlite``.

    Derived from the database's own checkout, not from this code's: a worktree session with
    ``SEER_LAB_DB`` pointing at the main checkout writes the snapshot into that checkout, next to
    the database it exports, and ``lab stage`` stages both there."""
    return Path(db).resolve().parent.parent / "web" / "data" / "lab.json"


def _num(x: Any) -> float | None:
    """A JSON-safe number: None and non-finite values become None, the rest rounds to 6 dp."""
    if x is None:
        return None
    x = float(x)
    return round(x, 6) if math.isfinite(x) else None


def _dicts(conn: sqlite3.Connection, sql: str) -> list[dict[str, Any]]:
    """Rows as dicts, whatever the connection's row_factory."""
    cur = conn.execute(sql)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def _snapshot_method(m: Mapping[str, Any]) -> dict[str, Any]:
    hypothesis, sep, expected = m["hypothesis"].partition(EXPECTED_FAILURE_SEP)
    return {
        "id": m["id"],
        "name": m["name"],
        "family": m["family"],
        "parentId": m["parent_id"],
        "sourceKind": m["source_kind"],
        "sourceRef": m["source_ref"],
        "hypothesis": hypothesis,
        "expectedFailure": expected if sep else None,
        "status": m["status"],
        "analysis": m["analysis"],
        "verdict": m["verdict"],
        "blockedOn": m["blocked_on"],
        "created": m["created"],
        "updated": m["updated"],
        "historical": m["id"].startswith("H-"),
    }


def _snapshot_curve(text: str) -> list[list[Any]]:
    out: list[list[Any]] = []
    for day, value in json.loads(text):
        v = _num(value)
        if v is not None:
            out.append([str(day), v])
    return out


def _snapshot_trial(t: Mapping[str, Any]) -> dict[str, Any]:
    pf = t["profit_factor"]
    return {
        "n": int(t["n"]),
        "methodId": t["method_id"],
        "candidateId": t["candidate_id"],
        "rulesId": t["rules_id"],
        "allocatorId": t["allocator_id"],
        "configText": t["config_text"],
        "window": t["window"],
        "start": t["start"],
        "end": t["end"],
        "gitSha": t["git_sha"],
        "runAt": t["run_at"],
        "totalReturn": _num(t["total_return"]),
        "cagr": _num(t["cagr"]),
        "maxDrawdown": _num(t["max_drawdown"]),
        "profitFactor": _num(pf),
        "pfInfinite": pf is not None and float(pf) == math.inf,
        "trades": int(t["trades"]),
        "sharpe": _num(t["sharpe"]),
        "exposure": _num(t["exposure"]),
        "turnover": _num(t["turnover"]),
        "worstYear": None if t["worst_year"] is None else int(t["worst_year"]),
        "worstYearReturn": _num(t["worst_year_return"]),
        "spyTrReturn": _num(t["spy_tr_return"]),
        "spyTrCagr": _num(t["spy_tr_cagr"]),
        "mar": _num(t["mar"]),
        "failed": [f for f in t["failed"].split("; ") if f],
        "eligible": bool(t["eligible"]),
        "dsr": _num(t["dsr"]),
        "nTrialsAtRun": int(t["n_trials_at_run"]),
        "curve": _snapshot_curve(t["curve_json"]),
    }


def snapshot(conn: sqlite3.Connection) -> dict[str, Any]:
    """The whole lab as the web's ``LabSnapshot`` (SERA_LAB_SITE_PLAN.md Interface Contract).

    Deterministic: the same database gives the same value; there is no wall-clock time in it
    (``asOf`` is the latest timestamp found in the data, "" for an empty lab). Reads only what
    schema v1 and v2 share and never touches ``meta``, so it works on a read-only connection to
    a database that has not been migrated. Gate and data facts come from the engine's constants.
    """
    from seer_engine import dates, research
    from seer_engine.backtest import dev, tuning
    from seer_engine.lab import seed

    def count(sql: str) -> int:
        return int(conn.execute(sql).fetchone()[0])

    by_status: dict[str, int] = dict.fromkeys(STATUSES, 0)
    for status, n in conn.execute("SELECT status, count(*) FROM methods GROUP BY status ORDER BY status"):
        by_status[str(status)] = int(n)
    as_of = conn.execute(
        "SELECT max(ts) FROM (SELECT max(updated) AS ts FROM methods UNION ALL "
        "SELECT max(run_at) FROM trials UNION ALL SELECT max(added) FROM insights UNION ALL "
        "SELECT max(added) FROM ideas_seen)"
    ).fetchone()[0]
    bench = seed.benchmark_curves()
    return {
        "version": SNAPSHOT_VERSION,
        "asOf": as_of or "",
        "gate": {
            "maxDrawdown": tuning.MAX_DRAWDOWN,
            "minProfitFactor": tuning.MIN_PROFIT_FACTOR,
            "minTrades": dev._MIN_TRADES,
            "dsrMin": DSR_MIN,
            "devStart": research.STORE_START.isoformat(),
            "devEnd": dev.DEV_END.isoformat(),
            "testStart": dates.next_session(dev.DEV_END).isoformat(),
        },
        "data": {
            "storeStart": research.STORE_START.isoformat(),
            "membershipStart": dev.MEMBERSHIP_START.isoformat(),
            "fxStart": dev.FX_START.isoformat(),
            "fingerprints": [
                str(r[0]) for r in conn.execute(
                    "SELECT DISTINCT store_fingerprint FROM trials ORDER BY store_fingerprint"
                )
            ],
            "barRows": seed.P7A_BAR_ROWS,
            "symbolsRequested": seed.P7A_SYMBOLS_REQUESTED,
            "symbolsServed": seed.P7A_SYMBOLS_SERVED,
            "dividendRows": seed.P7A_DIVIDEND_ROWS,
        },
        "summary": {
            "devTrials": count("SELECT count(*) FROM trials WHERE window = 'dev'"),
            "testLooks": count("SELECT count(*) FROM trials WHERE window = 'test'"),
            "methods": count("SELECT count(*) FROM methods"),
            "labMethods": count("SELECT count(*) FROM methods WHERE id GLOB 'M*'"),
            "historicalMethods": count("SELECT count(*) FROM methods WHERE id GLOB 'H-*'"),
            "insights": count("SELECT count(*) FROM insights"),
            "byStatus": by_status,
        },
        "benchmark": {
            "spyTr": [[d, v] for d, v in bench["spy_tr"]],
            "spyPrice": [[d, v] for d, v in bench["spy_price"]],
        },
        "methods": [_snapshot_method(m) for m in _dicts(conn, "SELECT * FROM methods ORDER BY id")],
        "trials": [_snapshot_trial(t) for t in _dicts(conn, "SELECT * FROM trials ORDER BY n")],
        "insights": [
            {"id": int(i["id"]), "kind": i["kind"], "title": i["title"], "body": i["body"],
             "methodId": i["method_id"], "added": i["added"]}
            for i in _dicts(conn, "SELECT * FROM insights ORDER BY id")
        ],
        "ideasSeen": [
            {"key": s["key"], "methodId": s["method_id"], "note": s["note"], "added": s["added"]}
            for s in _dicts(conn, "SELECT * FROM ideas_seen ORDER BY key")
        ],
    }


def snapshot_json(conn: sqlite3.Connection) -> str:
    """``snapshot`` as the exact bytes of ``web/data/lab.json``: compact, key order as built,
    UTF-8 kept, one trailing newline. ``allow_nan=False``: a stray NaN/inf fails loudly."""
    return json.dumps(snapshot(conn), ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"


def write_snapshot(conn: sqlite3.Connection, path: Path) -> bool:
    """Write ``snapshot_json(conn)`` to ``path`` (temp file + atomic replace). False when the
    file already held exactly that, in which case it is left untouched."""
    data = snapshot_json(conn).encode("utf-8")
    path = Path(path)
    if path.is_file() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return True
```
**Impact:**
- The new functions are purely additive.
- `ORDER BY id` on methods puts `H-*` before `M*`, because ASCII `H` (0x48) sorts before `M` (0x4D).
- `write_bytes` avoids newline translation, so the bytes match `snapshot_json` exactly on any OS.

### Step 5: Store facts and the benchmark reader in `seed.py`
**File:** `engine/src/seer_engine/lab/seed.py:30` and `:75`

**Change 5a.** Directly after line 30 (`P7A_REPORT = "docs/backtests/2026-10-04-p7a-dev-exploration.md"`), insert:
```python
# The P7a research store behind fingerprint P7A_FINGERPRINT (P7A_REPORT, "Data"): shown on
# seertrade.site/sera through store.snapshot. The store itself is local and gitignored.
P7A_BAR_ROWS = 2_490_793
P7A_SYMBOLS_REQUESTED = 1_061
P7A_SYMBOLS_SERVED = 539
P7A_DIVIDEND_ROWS = 28_206
```
These values come from `docs/backtests/2026-10-04-p7a-dev-exploration.md` lines 12–15 and match `docs/ROADMAP.md:60`.

**Change 5b.** Directly before `def seed(conn: sqlite3.Connection) -> int:` (line 75), insert:
```python
def benchmark_curves() -> dict[str, list[tuple[str, float]]]:
    """SPY's month-end growth of 1 over the dev window, from the committed P7a curves file:
    ``spy_tr`` (dividends reinvested) and ``spy_price`` (price only), 1993-01-29 = 1.0 through
    2015-10-16, rounded to 6 dp. Trials store only SPY's totals; the web draws this line."""
    out: dict[str, list[tuple[str, float]]] = {"spy_tr": [], "spy_price": []}
    with P7A_CURVES.open(encoding="utf-8", newline="") as f:
        for rec in csv.DictReader(f):
            for key, points in out.items():
                if rec[key] != "":
                    points.append((rec["date"], round(float(rec[key]), 6)))
    return out


```
**Impact:** Additive only. The CSV has 274 month-end rows, `1993-01-29` through `2015-10-16`, and no blank SPY cells (checked). `seed()` and `_curves()` are unchanged.

### Step 6: `lab export-json`, and `lab stage` writes and stages the snapshot
**File:** `engine/src/seer_engine/commands/lab.py:12`, `:14`, `:87`, `:91`, `:280-294`, `:308`, `:328`

**Change 6a, docstring.** Replace line 12 with:
```python
    lab stage                       under the write lock: write web/data/lab.json, git-add it and the database
```
After line 14 (`    lab export [--out F] …`), insert:
```python
    lab export-json [--out F]       the web snapshot (default: web/data/lab.json beside the database's repo)
```

**Change 6b, line 87.** Replace the `stage` subparser line with:
```python
    sub.add_parser("stage", help="write the web snapshot and git-add it with the database, under the write lock")
```

**Change 6c, line 91.** Replace `    sub.add_parser("seed", help="one-time import of the pre-lab record")` with:
```python
    s = sub.add_parser("export-json", help="write the web snapshot (seertrade.site/sera)")
    s.add_argument("--out", type=Path, default=None,
                   help="output file (default: web/data/lab.json in the database's repo)")
    sub.add_parser("seed", help="one-time import of the pre-lab record")
```

**Change 6d.** Replace `_stage` (lines 280–294) with:
```python
def _stage(conn, args) -> int:
    """Write the web snapshot and ``git add`` it with the database, both while holding an
    exclusive lock: a parallel session's half-written transaction can never be what gets
    committed, and the staged ``web/data/lab.json`` is always the export of the staged database.
    The snapshot goes beside the database's own repo (``store.snapshot_path``), so a worktree
    session with ``SEER_LAB_DB`` stages both files in the checkout that owns the database."""
    import subprocess

    path = Path(args.db).resolve()
    snap = store.snapshot_path(path)
    conn.execute("BEGIN EXCLUSIVE")
    try:
        store.write_snapshot(conn, snap)
        out = subprocess.run(
            ["git", "add", "--", str(path), str(snap)], cwd=path.parent, capture_output=True, text=True
        )
    finally:
        conn.rollback()
    if out.returncode != 0:
        raise store.LabError(f"git add {path} {snap} failed: {out.stderr.strip()}")
    print(f"staged {path}")
    print(f"staged {snap}")
    return 0
```

**Change 6e.** Directly before `def _seed(conn, args) -> int:` (line 308), insert:
```python
def _export_json(conn, args) -> int:
    path = Path(args.out) if args.out is not None else store.snapshot_path(args.db)
    if not store.write_snapshot(conn, path):
        log.info("%s already up to date", path)
    print(path)
    return 0


```

**Change 6f, `_HANDLERS` (line 328).** After `    "export": _export,`, add:
```python
    "export-json": _export_json,
```

**Impact:**
- `lab insight --kind synthesis` works with no CLI change, because `choices=store.INSIGHT_KINDS`.
- `lab stage` holds `BEGIN EXCLUSIVE` while snapshotting. The first call pays the lazy imports (`registry`, the market calendar), about 1–2 s, which is far inside other sessions' 120 s `timeout`.
- `run()` opens the DB with `store.connect`, so `export-json` and `stage` migrate a v1 DB first. Intended.

### Step 7: Tests
**File:** `engine/tests/test_lab_snapshot.py` (new)
**Code:**
```python
"""Schema v2 (the ``synthesis`` insight kind) and the web snapshot ``web/data/lab.json``
(SERA_LAB_SITE_PLAN.md, phase 1): the v1 -> v2 migration, the snapshot's contract and
determinism, ``lab export-json`` / ``lab stage``, and the guard that the committed snapshot is
the export of the committed database."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import sqlite3
import subprocess

import pytest

from seer_engine import cli
from seer_engine.lab import seed as seed_mod
from seer_engine.lab import store
from seer_engine.lab.seed import seed

V1_SCHEMA = store._SCHEMA.replace(", 'synthesis'", "")
V1_INSIGHTS = [
    (1, "observation", "Vol scaling buys drawdown", "It costs CAGR.", "M0001", "2026-10-02T00:00:00+00:00"),
    (2, "data-wish", "Delisted stocks", "Survivorship.", None, "2026-10-02T00:00:01+00:00"),
    (3, "risk", "The 15% bar", "2008 is in the window.", None, "2026-10-02T00:00:02+00:00"),
]
LABELS = {"beats SPY TR", "max DD <= 15%", "PF >= 1.3", ">= 100 trades", "owner inputs", "DSR >= 0.95"}
METHOD_KEYS = {"id", "name", "family", "parentId", "sourceKind", "sourceRef", "hypothesis", "expectedFailure",
               "status", "analysis", "verdict", "blockedOn", "created", "updated", "historical"}
TRIAL_KEYS = {"n", "methodId", "candidateId", "rulesId", "allocatorId", "configText", "window", "start", "end",
              "gitSha", "runAt", "totalReturn", "cagr", "maxDrawdown", "profitFactor", "pfInfinite", "trades",
              "sharpe", "exposure", "turnover", "worstYear", "worstYearReturn", "spyTrReturn", "spyTrCagr", "mar",
              "failed", "eligible", "dsr", "nTrialsAtRun", "curve"}


def _v1_db(path):
    """A schema-v1 database as the first lab wrote it: one method, three insights (ids 1-3)."""
    assert V1_SCHEMA != store._SCHEMA
    c = sqlite3.connect(path)
    c.executescript(V1_SCHEMA)
    c.executemany("INSERT INTO transitions (src, dst) VALUES (?, ?)", store.TRANSITIONS)
    c.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '1')")
    c.execute(
        "INSERT INTO methods (id, name, family, source_kind, hypothesis, status, created, updated) "
        "VALUES ('M0001', 'n', 'f', 'knowledge', 'h', 'idea', '2026-10-01T00:00:00+00:00', "
        "'2026-10-01T00:00:00+00:00')"
    )
    c.executemany("INSERT INTO insights (id, kind, title, body, method_id, added) VALUES (?, ?, ?, ?, ?, ?)", V1_INSIGHTS)
    c.commit()
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        c.execute("INSERT INTO insights (kind, title, body, added) VALUES ('synthesis', 't', 'b', 'x')")
    c.close()


def _insights_schema(conn) -> list[tuple[str, str, str]]:
    return [tuple(r) for r in conn.execute(
        "SELECT type, name, sql FROM sqlite_master WHERE tbl_name = 'insights' ORDER BY type, name"
    )]


def test_connect_migrates_a_v1_database_keeping_rows_and_triggers(tmp_path):
    _v1_db(tmp_path / "lab.sqlite")
    conn = store.connect(tmp_path / "lab.sqlite")
    fresh = store.connect(tmp_path / "fresh.sqlite")
    try:
        assert store.schema_version(conn) == "2"
        rows = conn.execute("SELECT id, kind, title, body, method_id, added FROM insights ORDER BY id").fetchall()
        assert [tuple(r) for r in rows] == V1_INSIGHTS
        assert _insights_schema(conn) == _insights_schema(fresh)  # same table and triggers as a new v2 db
        assert conn.execute("SELECT count(*) FROM sqlite_master WHERE name = 'insights_v1'").fetchone()[0] == 0
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("UPDATE insights SET body = 'x'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM insights")
        with conn:
            n = store.add_insight(conn, kind="synthesis", title="Batch 1", body="Where the search stands.")
        assert n == 4  # the AUTOINCREMENT counter carried over
    finally:
        conn.close()
        fresh.close()
    again = store.connect(tmp_path / "lab.sqlite")  # a second connect is a no-op
    try:
        assert store.schema_version(again) == "2"
        assert again.execute("SELECT count(*) FROM insights").fetchone()[0] == 4
    finally:
        again.close()


def test_a_new_database_starts_at_v2(tmp_path):
    conn = store.connect(tmp_path / "lab.sqlite")
    try:
        assert store.schema_version(conn) == store.SCHEMA_VERSION == "2"
        assert "synthesis" in store.INSIGHT_KINDS
        with conn:
            assert store.add_insight(conn, kind="synthesis", title="t", body="b") == 1
    finally:
        conn.close()


def test_an_unknown_schema_version_is_refused(tmp_path):
    conn = store.connect(tmp_path / "lab.sqlite")
    with conn:
        conn.execute("UPDATE meta SET value = '9' WHERE key = 'schema_version'")
    conn.close()
    with pytest.raises(store.LabError, match="'9'"):
        store.connect(tmp_path / "lab.sqlite")


def test_the_snapshot_reads_a_v1_database_read_only_and_migration_does_not_change_it(tmp_path):
    db = tmp_path / "lab" / "lab.sqlite"
    db.parent.mkdir()
    _v1_db(db)
    before = db.read_bytes()
    ro = store.connect_readonly(db)
    try:
        v1_text = store.snapshot_json(ro)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            ro.execute("INSERT INTO meta (key, value) VALUES ('x', 'y')")
    finally:
        ro.close()
    assert db.read_bytes() == before  # opened as it is: not migrated, not written
    store.connect(db).close()  # migrates to v2
    ro = store.connect_readonly(db)
    try:
        assert store.schema_version(ro) == "2"
        assert store.snapshot_json(ro) == v1_text
    finally:
        ro.close()


def test_connect_readonly_refuses_a_missing_file(tmp_path):
    with pytest.raises(store.LabError, match="no lab database"):
        store.connect_readonly(tmp_path / "nope.sqlite")
    assert not (tmp_path / "nope.sqlite").exists()


@pytest.fixture()
def lab(tmp_path):
    """The seeded record plus one lab method with an infinite-PF trial, insights and a seen key."""
    c = store.connect(tmp_path / "lab" / "lab.sqlite")
    seed(c)
    with c:
        store.add_method(
            c, id="M0001", name="Vol-scaled momentum", family="momentum", source_kind="knowledge",
            hypothesis="Scaling cuts the drawdown.\n\nExpected failure: Monthly is too slow.", status="registered",
        )
        store.insert_trials(c, [store.TrialRow(
            method_id="M0001", candidate_id="M0001-A", config_digest="d1", config_text="t", rules_id="r",
            allocator_id="a", window="dev", start="2000-01-03", end="2015-10-16", store_fingerprint="fp",
            git_sha="abc", run_at="2026-10-05T00:00:00+00:00", total_return=1.0, cagr=0.1234567891,
            max_drawdown=0.2, profit_factor=math.inf, trades=200, sharpe=0.8, exposure=0.9, turnover=1.0,
            worst_year=2008, worst_year_return=-0.2, spy_tr_return=0.5, spy_tr_cagr=0.07, mar=0.5,
            failed="beats SPY TR; DSR >= 0.95", eligible=False, dsr=0.4123456789, n_trials_at_run=55,
            curve_json='[["2000-01-31",1.0],["2000-02-29",1.0123456789]]',
        )])
        store.add_insight(c, kind="observation", title="Obs", body="b", method_id="M0001")
        store.add_insight(c, kind="synthesis", title="Batch", body="Where we stand.")
        store.mark_seen(c, "url:https://example.com/paper", "M0001", "a paper")
    yield c
    c.close()


def test_the_snapshot_follows_the_contract(lab):
    s = store.snapshot(lab)
    assert list(s) == ["version", "asOf", "gate", "data", "summary", "benchmark", "methods", "trials",
                       "insights", "ideasSeen"]
    assert s["version"] == 1
    assert s["gate"] == {"maxDrawdown": 0.15, "minProfitFactor": 1.3, "minTrades": 100, "dsrMin": 0.95,
                         "devStart": "1993-01-29", "devEnd": "2015-10-16", "testStart": "2015-10-19"}
    assert s["data"] == {
        "storeStart": "1993-01-29", "membershipStart": "1996-01-02", "fxStart": "1999-01-04",
        "fingerprints": sorted({seed_mod.P7A_FINGERPRINT, "fp"}),
        "barRows": 2490793, "symbolsRequested": 1061, "symbolsServed": 539, "dividendRows": 28206,
    }
    summary = s["summary"]
    assert {k: v for k, v in summary.items() if k != "byStatus"} == {
        "devTrials": 55, "testLooks": 0, "methods": 15, "labMethods": 1, "historicalMethods": 14, "insights": 2,
    }
    assert list(summary["byStatus"]) == list(store.STATUSES)
    assert summary["byStatus"]["rejected"] == 14 and summary["byStatus"]["registered"] == 1
    assert sum(summary["byStatus"].values()) == 15

    spy_tr, spy_price = s["benchmark"]["spyTr"], s["benchmark"]["spyPrice"]
    assert spy_tr[0] == ["1993-01-29", 1.0] and spy_price[0] == ["1993-01-29", 1.0]
    assert spy_tr[-1][0] == spy_price[-1][0] == "2015-10-16"
    assert len(spy_tr) == len(spy_price) == 274

    ids = [m["id"] for m in s["methods"]]
    assert ids == sorted(ids) and ids[0].startswith("H-") and ids[-1] == "M0001"
    for m in s["methods"]:
        assert set(m) == METHOD_KEYS
        assert m["historical"] == m["id"].startswith("H-")
    m1 = s["methods"][-1]
    assert m1["hypothesis"] == "Scaling cuts the drawdown." and m1["expectedFailure"] == "Monthly is too slow."
    assert s["methods"][0]["expectedFailure"] is None

    assert [t["n"] for t in s["trials"]] == list(range(1, 56))
    for t in s["trials"]:
        assert set(t) == TRIAL_KEYS
        assert set(t["failed"]) <= LABELS
        assert all(isinstance(p[0], str) and isinstance(p[1], float) for p in t["curve"])
    t55 = s["trials"][-1]
    assert t55["profitFactor"] is None and t55["pfInfinite"] is True
    assert t55["cagr"] == 0.123457 and t55["dsr"] == 0.412346
    assert t55["failed"] == ["beats SPY TR", "DSR >= 0.95"] and t55["eligible"] is False
    assert t55["curve"] == [["2000-01-31", 1.0], ["2000-02-29", 1.012346]]
    assert not any(t["pfInfinite"] for t in s["trials"][:54])

    assert [(i["id"], i["kind"], i["methodId"]) for i in s["insights"]] == [(1, "observation", "M0001"), (2, "synthesis", None)]
    keys = [x["key"] for x in s["ideasSeen"]]
    assert keys == sorted(keys) and "url:https://example.com/paper" in keys
    assert set(s["ideasSeen"][0]) == {"key", "methodId", "note", "added"}

    stamps = ([m["updated"] for m in s["methods"]] + [t["runAt"] for t in s["trials"]]
              + [i["added"] for i in s["insights"]] + [x["added"] for x in s["ideasSeen"]])
    assert s["asOf"] == max(stamps)


def test_the_snapshot_json_is_deterministic(lab, tmp_path):
    text = store.snapshot_json(lab)
    assert text == store.snapshot_json(lab)
    assert text.endswith("}\n") and text.count("\n") == 1
    assert "NaN" not in text and "Infinity" not in text
    assert json.loads(text) == store.snapshot(lab)
    copy = tmp_path / "copy.sqlite"
    shutil.copyfile(tmp_path / "lab" / "lab.sqlite", copy)
    ro = store.connect_readonly(copy)
    try:
        assert store.snapshot_json(ro) == text
    finally:
        ro.close()


def test_an_empty_lab_has_an_empty_as_of(tmp_path):
    conn = store.connect(tmp_path / "lab.sqlite")
    try:
        s = store.snapshot(conn)
    finally:
        conn.close()
    assert s["asOf"] == "" and s["methods"] == [] and s["trials"] == [] and s["data"]["fingerprints"] == []


def test_snapshot_path_is_beside_the_databases_repo(tmp_path):
    assert store.snapshot_path(tmp_path / "lab" / "lab.sqlite") == (tmp_path / "web" / "data" / "lab.json").resolve()
    assert store.snapshot_path(store.COMMITTED_DB) == store.config.REPO_ROOT / "web" / "data" / "lab.json"


def _git(repo, *args) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def test_export_json_and_stage_write_the_snapshot_beside_the_database(tmp_path):
    repo = tmp_path / "repo"
    (repo / "lab").mkdir(parents=True)
    _git(repo, "init", "-q")
    db = repo / "lab" / "lab.sqlite"
    store.connect(db).close()
    snap = repo / "web" / "data" / "lab.json"

    assert cli.main(["lab", "--db", str(db), "export-json"]) == 0
    ro = store.connect_readonly(db)
    try:
        assert snap.read_text(encoding="utf-8") == store.snapshot_json(ro)
    finally:
        ro.close()
    out = tmp_path / "elsewhere.json"
    assert cli.main(["lab", "--db", str(db), "export-json", "--out", str(out)]) == 0
    assert out.read_bytes() == snap.read_bytes()

    assert cli.main(["lab", "--db", str(db), "insight", "--kind", "synthesis", "--title", "Batch 1",
                     "--body", "Where the search stands."]) == 0
    assert cli.main(["lab", "--db", str(db), "stage"]) == 0
    staged = set(_git(repo, "diff", "--cached", "--name-only").split())
    assert staged == {"lab/lab.sqlite", "web/data/lab.json"}
    assert json.loads(snap.read_text(encoding="utf-8"))["insights"][0]["kind"] == "synthesis"
    assert not (repo / "web" / "data" / "lab.json.tmp").exists()


def test_the_committed_snapshot_is_the_export_of_the_committed_database():
    """Invariant 2: web/data/lab.json == `lab export-json` of lab/lab.sqlite, byte for byte.
    Read-only: the committed database is opened with mode=ro, never migrated or written."""
    db = store.COMMITTED_DB
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    ro = store.connect_readonly(db)
    try:
        expected = store.snapshot_json(ro)
    finally:
        ro.close()
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    committed = store.snapshot_path(db).read_bytes().decode("utf-8")
    if committed != expected:
        pytest.fail(
            "web/data/lab.json is not the export of lab/lab.sqlite: run "
            "`python -m seer_engine lab stage` (or `lab export-json`) and commit both files"
        )
```
**Impact:**
- `test_lab_store.py` stays as it is and keeps passing. Its `kind="rumor"` rejection still holds.
- The sync guard reads `store.COMMITTED_DB` (`REPO_ROOT/lab/lab.sqlite`), never `DB_PATH`, so a `SEER_LAB_DB` in the environment cannot redirect it.

### Step 8: Generate and stage the migrated DB and the snapshot
**Files:** `lab/lab.sqlite` (migrated), `web/data/lab.json` (new)
**Change:** Run this once, after Steps 1–7 are applied. `SEER_LAB_DB` **must** be unset: `DB_PATH` honours it, and pointing it at main's DB would export the wrong database into the wrong checkout.
```bash
WT=/home/miftah/.worktrees/seer/sera-lab-site
cd $WT/engine && env -u SEER_LAB_DB PYTHONPATH=$WT/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab stage
# prints: staged $WT/lab/lab.sqlite / staged $WT/web/data/lab.json
```
**Impact:**
- `lab/lab.sqlite` becomes schema v2. All 4 insights are kept (ids 1–4), and the `sqlite_sequence` row for `insights` is 4.
- `web/data/lab.json` is about 399 KB on one line.
- Commit both files with the code in a single commit. The sync guard needs all three to agree.

## Verification

**Build/lint:** `cd $WT/engine && /home/miftah/seer/engine/.venv/bin/ruff check .`. If the ruff binary is missing, use `… /bin/python -m ruff check .`.

**Tests:** `cd $WT/engine && env -u SEER_LAB_DB PYTHONPATH=$WT/engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest -q tests/test_lab_snapshot.py tests/test_lab_store.py tests/test_lab_runner.py tests/test_lab_methods.py`. Then run the full suite with `… -m pytest -q`.

**Manual check:**
- `env -u SEER_LAB_DB PYTHONPATH=$WT/engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab export-json` should log "already up to date" after Step 8. `git status` should show no change to `web/data/lab.json`.
- `python -c "import json;d=json.load(open('$WT/web/data/lab.json'));print(d['summary'], d['asOf'])"` should show 58 dev trials, 17 methods, 4 insights and `asOf` `2026-10-04T14:12:24+00:00`.

**Exit criteria:**
- `lab export-json` reproduces the committed `web/data/lab.json` byte for byte.
- The committed `lab/lab.sqlite` has `meta.schema_version='2'` and accepts `lab insight --kind synthesis`.
- `test_the_committed_snapshot_is_the_export_of_the_committed_database` passes.
- `ruff check` and the full engine `pytest` are green.

## Handoffs

- **Phase 7 (R3), CI path filter:** `.github/workflows/engine-ci.yml` should add `lab/**` to both path filters. Without it, a push that changes only `lab/lab.sqlite` and `web/data/lab.json` would still run CI, because `web/**` matches the JSON, but a push that changed only `lab/**` (which `lab stage` now prevents) would not.
- **Phase 7 (R3), skills:** both lab `SKILL.md` files must commit through `lab stage`, which now stages `web/data/lab.json` too. The commit must include both paths, and nothing may `git add lab/lab.sqlite` directly. The skills should also say that `pytest` fails on a checkout where `lab/lab.sqlite` changed without `lab stage` (the sync guard fails by design), so tests run after staging. A worktree session using `SEER_LAB_DB` gets the JSON written into the checkout that owns the DB, which is the coordinator's main checkout.
- **Phase 7 (R6):** `sera-the-explorer`'s batch synthesis uses `lab insight --kind synthesis` (available from this phase).
- **Phase 2 (R3):** must type against the shape-level details in the Interface Contract above. These are: `byStatus` includes all nine statuses with zeros, `asOf` may be `""`, and points are `[string, number]` arrays. `web/data/lab.json` exists from this phase. Import it as `@/data/lab.json` (tsconfig `@/*` -> `./*`).
- **Docs (Phase 7):** `docs/ROADMAP.md` / `web/package_readme.md` should mention `lab export-json` and schema v2.

## Rollback

- Revert this phase's commit. That restores the v1 `lab/lab.sqlite` bytes and removes `web/data/lab.json`, the code and the test.
- If a later commit added `synthesis` insights to the DB, reverting only the code leaves a v2 DB that v1 code still opens. `INSERT OR IGNORE` keeps `'2'`, and the CHECK it reads is the stored v2 one. Only `lab insight --kind synthesis` disappears from the CLI.
- No other phase's files are touched.
