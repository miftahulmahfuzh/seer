# Phase 2: Per-trial provenance, and re-runs at the recorded capital

**Plan set:** `TRIAL_REPRODUCIBILITY_PLAN.md`
**Analysis:** `20261009-192826-T7RQ_code_analyzer.md`
**Satisfies:** R1 (policy (d): record enough per trial to re-derive it), R4 (the 58-trial
`5451195fd552` cohort is *marked* by an append-only annotation, never rewritten)
**Depends on:** Phase 1 (`dev._run` / `run_candidate` / `run_registry` take
`initial_idr: Decimal = INITIAL_IDR` and pass it to `run_rules`)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab` (plus `engine/src/seer_engine/research.py`)

---

## Goal

Every trial in the lab carries, in a new append-only side table, the two inputs that make a re-run
the same measurement and that no existing column records: the **starting capital** it ran on and
the **price fingerprint** of the store it read (fundamentals excluded). New trials write it in the
same transaction as the trial; the 152 existing ones get it by migration, by the rules the
analysis measured exactly (M1, M3). Every path that re-runs a recorded trial (`lab remeasure`
dev + seed, `lab costs`) runs it at that recorded capital, and the hard gate's de-funding divides
by it instead of the live `INITIAL_IDR` — so `lab remeasure M0011`, `M0007` and `H-P7A` reproduce
on today's store with today's `INITIAL_IDR` (10M) untouched.

## Interface Contract

**Deletes:** nothing. (`from seer_engine.backtest.runner import INITIAL_IDR` inside
`hardgate.trial_deposits` is removed — a local import, not a symbol.)

**Renames:** none.

**Creates:**

- `research.price_fingerprint_of(files: Mapping[str, str]) -> str` (`research.py`, after
  `fingerprint_of`) — `fingerprint_of` over the four `DATA_FILES` only; `ValueError` when one is
  missing.
- `research.ResearchData.price_fingerprint: str | None = None` (new **last** field, default
  `None`; `load_store` always sets it to `price_fingerprint_of(manifest["files"])`. `None` means
  "not loaded from a real store" — a test fixture).
- `store.SCHEMA_VERSION = "5"`.
- table `trial_provenance(trial_n INTEGER PRIMARY KEY REFERENCES trials(n), initial_idr TEXT NOT
  NULL CHECK (CAST(initial_idr AS REAL) > 0), price_fingerprint TEXT NULL CHECK (NULL or
  non-blank), source TEXT NOT NULL CHECK (source IN ('recorded','backfill')), measured TEXT NOT
  NULL CHECK (non-blank))`; triggers `trial_provenance_no_update`, `trial_provenance_no_delete`.
- `store.PROVENANCE_SOURCES: tuple[str, ...] = ("recorded", "backfill")`
- `store.P7A_PRICE_FINGERPRINT: str = "5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a"`
- `store.BACKFILL_LUMP_SUM_IDR: Decimal = Decimal("20000000")`,
  `store.BACKFILL_FUNDED_IDR: Decimal = Decimal("10000000")`
- `store.BACKFILL_PRICE_FINGERPRINTS: Mapping[str, str]` — `5451195f…`, `e597367b…`,
  `399d0d25…` → `5451195f…`; `56e83810…` → itself; anything absent → NULL.
- `store._PROVENANCE_TABLE: str`, `store._PROVENANCE_TRIGGERS: tuple[str, str]` (module-private
  DDL constants, same pattern as `_FUNDING_TABLE` / `_FUNDING_TRIGGERS`; `test_lab_snapshot.py`
  reads them).
- `store._v4_to_v5(conn) -> None` (migration step; backfills every trial lacking a row).
- `@dataclass(frozen=True) store.ProvenanceRow` with fields, in order:
  `trial_n: int`, `initial_idr: Decimal`, `price_fingerprint: str | None`, `source: str`,
  `measured: str`.
- `store.PROVENANCE_COLUMNS: tuple[str, ...]`
- `store.insert_provenance(conn: sqlite3.Connection, rows: Sequence[ProvenanceRow]) -> None`
  (caller holds the transaction; refuses `trial_n <= 0`, a non-`Decimal` / non-finite / `<= 0`
  capital, an unknown `source`, and a second row for the same trial — all `store.LabError`).
- `store.provenance_of(conn: sqlite3.Connection, trial_n: int) -> sqlite3.Row | None` (None also
  when the table does not exist — an unmigrated read-only connection).
- `runner.recorded_capital(conn: sqlite3.Connection, trial_n: int) -> Decimal` (`lab/runner.py`,
  beside `recorded_contributions`; `store.LabError` when the trial has no provenance row).
- `seed.P7A_INITIAL_IDR: Decimal = Decimal("20000000")`.
- `remeasure.plan_capital(conn: sqlite3.Connection, label: str, ns: Sequence[int]) -> Decimal`
  (the one recorded capital of trials `ns`; `store.LabError` when mixed, missing, or empty).
- `remeasure.Plan.initial_idr: Decimal` (new required last field; `Plan` is constructed only by
  `remeasure.preflight`).
- Test helpers (`engine/tests/labkit.py`), the **one** fixture stamping site for the whole plan
  set (phase 3 uses them; it does not create its own):
  - `labkit.LAB_PRICE_FINGERPRINT: str = store.P7A_PRICE_FINGERPRINT`
  - `labkit.stamp_provenance(conn, trial_ns: Iterable[int], *, price_fingerprint: str | None =
    LAB_PRICE_FINGERPRINT, initial_idr: Decimal = Decimal("10000000")) -> None` — caller holds
    the transaction; **idempotent**: a trial that already has a provenance row (from `run_method`,
    `seed`, the v4→v5 backfill or an earlier stamp) is skipped, never stamped twice.

**Signature changes:**

- `remeasure.run_chunk(data, candidates)` → `remeasure.run_chunk(data, candidates, *, initial_idr: Decimal)`
  (required keyword — the test seam; `perfect()` in `test_lab_remeasure_seed.py` is updated).
- `real_costs.measure(method, candidate, trial, data, *, contributions=None)` →
  `real_costs.measure(method, candidate, trial, data, *, contributions=None, initial_idr: Decimal = INITIAL_IDR)`.

**Behaviour changes:**

- `runner.run_method` / `runner.run_test` pass `initial_idr=INITIAL_IDR` explicitly to
  `dev.run_registry` and write one `source='recorded'` provenance row per trial in the existing
  `BEGIN IMMEDIATE` transaction (capital = that same value; price fingerprint =
  `data.price_fingerprint`; `measured` = the trial's `run_at`).
- `seed.seed` writes 54 `source='backfill'` rows (20M, `P7A_FINGERPRINT`, `measured=P7A_RUN_AT`).
- `remeasure.preflight` refuses (before any store loads) a method whose trials carry no recorded
  capital or two different ones; `remeasure.measure` runs at `plan.initial_idr`.
- `remeasure.seed_preflight` refuses (before any store loads) a to-do set with a seed trial that
  has no recorded capital **or** with two different recorded capitals (`plan_capital` over the
  whole to-do set — `dev.run_registry` takes one capital per call, phase 1's handoff);
  `remeasure.remeasure_seed` still resolves one capital per chunk via `plan_capital` (the same
  value, by construction) and passes it to `run_chunk`.
- `commands/lab.py:_costs` resolves `runner.recorded_capital` before loading the store and passes
  it to `real_costs.measure`.
- `hardgate.trial_deposits`: `unit = amount_idr / runner.recorded_capital(conn, n)`.
- The METRIC_TOL comment in `remeasure.py` is corrected with M4.

**Requires (from earlier phases):** `dev.run_registry(..., initial_idr: Decimal = INITIAL_IDR)`
reaching `run_rules` (Phase 1). Every call in this phase passes it **by keyword**.

**Leaves alone (owned by others):**
- `hardgate.fold_record` / `check` / `fold_summary` / `summary` / `geometry` and any
  comparability helper (Phase 3).
- `commands/lab.py` `_run` (store pin), `_walkforward`, `_regime` (Phase 3). This phase edits
  **only** `_costs` in that file.
- `backtest/dev.py`, `backtest/runner.py:INITIAL_IDR` (Phase 1 / never).
- `lab/lab.sqlite`, `web/data/lab.json`, every doc (Phase 4). This phase never connects to the
  committed database with `store.connect`.
- `lab/name_count.py` — runs at live capital by design (it is not a re-run of a recorded trial).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/research.py` | modify | `price_fingerprint_of` (after `fingerprint_of`, :372); `ResearchData.price_fingerprint` (:194); `load_store` sets it (:937) |
| `engine/src/seer_engine/lab/store.py` | modify | docstring (:23-32); `Decimal` import (:51-60); `SCHEMA_VERSION` (:70); provenance DDL + backfill constants (after :277); `_SCHEMA` (:367); `_v4_to_v5` (after :501); `_migrate` ladder (:504-541); provenance section (after :1795) |
| `engine/src/seer_engine/lab/runner.py` | modify | imports (:46-68); `recorded_capital` (after :122); `run_method` (:359-446); `run_test` (:748-790) |
| `engine/src/seer_engine/lab/seed.py` | modify | docstring, `Decimal` import, `P7A_INITIAL_IDR` (after :30); `seed` writes provenance (:141-156) |
| `engine/src/seer_engine/lab/remeasure.py` | modify | imports (:48-68); `Plan.initial_idr` (:164-176); `plan_capital` (before `preflight`, :286); `preflight` (:359-366); `measure` (:372-417); METRIC_TOL comment (:666-669); `seed_preflight` return (:995-1002); `run_chunk` (:1026-1055); `remeasure_seed` loop (:1133-1134) |
| `engine/src/seer_engine/lab/real_costs.py` | modify | `INITIAL_IDR` import (:36); `measure` (:247-293) |
| `engine/src/seer_engine/lab/hardgate.py` | modify | `trial_deposits` (:183-227) |
| `engine/src/seer_engine/commands/lab.py` | modify | `_costs` only (:1710-1757) |
| `engine/tests/labkit.py` | modify | `store` import; `smoke_data` / `smoke_test_data` set `price_fingerprint` (:53-59, :92-106); `LAB_PRICE_FINGERPRINT` + idempotent `stamp_provenance` appended |
| `engine/tests/test_research_store.py` | modify | append price-fingerprint tests |
| `engine/tests/test_lab_store.py` | modify | imports; append provenance + seed tests |
| `engine/tests/test_lab_snapshot.py` | modify | `"4"` → `"5"` (:116); v4 fixture + v4→v5 migration test; committed-copy backfill test |
| `engine/tests/test_lab_runner.py` | modify | imports; append recorded-capital tests |
| `engine/tests/test_lab_test_window.py` | modify | `fake_run_registry` accepts `initial_idr` (:347-352); look test asserts provenance (:242-262) |
| `engine/tests/test_lab_remeasure.py` | modify | imports (`Decimal`, `labkit.stamp_provenance`); append capital tests |
| `engine/tests/test_lab_remeasure_seed.py` | modify | imports; `perfect` (:53); no-window test (:432-434); append capital tests |
| `engine/tests/test_lab_hardgate.py` | modify | imports (`Decimal`, `labkit.stamp_provenance`); two funded tests (:311-366) stamp via labkit; `_funded_trial` helper + two new tests inserted after :366 |
| `engine/tests/test_lab_costs.py` | modify | `measure` calls pass `initial_idr` (:94-97, :153-156); two new tests |

## Implementation Steps

### Step 1: `research.price_fingerprint_of` and `ResearchData.price_fingerprint`

**File:** `engine/src/seer_engine/research.py:372` (insert after `fingerprint_of`, i.e. after :375)
**Change:** new function.
**Code:**
```python
def price_fingerprint_of(files: Mapping[str, str]) -> str:
    """``fingerprint_of`` over the four price files alone (``DATA_FILES``): the store's identity
    as far as a backtest is concerned.

    **Why this exists, measured 2026-10-09 (trial-reproducibility analysis M1).** ``fingerprint_of``
    hashes the store's whole ``files`` map, so adding or refreshing ``fundamentals.csv`` moves it
    without moving a single bar. That is the correct identity for *the store* -- the
    ``sync-research-store`` skill keys on it, and a store whose panel changed is a different store
    -- and the wrong identity for *a price-only comparison*. The lab's 148 dev trials were recorded
    under three store fingerprints (``5451195f…`` 58 trials, ``e597367b…`` 6, ``399d0d25…`` 84),
    and this function over today's ``399d0d25…`` manifest returns exactly ``5451195f…``, the P7a
    store's fingerprint: the three carry byte-identical bars, dividends, FX and unserved rows, and
    differ only in the panel. Keying a comparability rule on ``store_fingerprint`` would refuse
    every promotion in the lab for a difference no price-only method can see; keying it on this
    strands nothing.

    For a four-file store (one built before fundamentals existed) the two fingerprints are the
    same hash, because the file map *is* ``DATA_FILES``. ``ValueError`` when ``files`` lacks one
    of the four -- which ``_read_manifest`` already refuses for any store that loads, so in
    practice only a hand-built map can reach it.
    """
    missing = [name for name in DATA_FILES if name not in files]
    if missing:
        raise ValueError(
            f"a price fingerprint covers all of {list(DATA_FILES)}; the file map lacks {missing}"
        )
    return fingerprint_of({name: files[name] for name in DATA_FILES})
```
**Impact:** none on its own.

**File:** `engine/src/seer_engine/research.py:184-194`
**Change:** add the field, last, with a default (so every hand-built `ResearchData` keeps working).
**Code:** replace the class body with
```python
@dataclass(frozen=True)
class ResearchData:
    """A loaded, verified research store.

    ``price_fingerprint`` is ``price_fingerprint_of(manifest["files"])`` -- the fingerprint of the
    four price files, fundamentals excluded -- and ``load_store`` always sets it. It defaults to
    None only so a hand-built fixture need not invent one; a None reaches ``trial_provenance`` as
    NULL, which reads as "price data unknown", never as a match.
    """

    market: Market  # history from bars.csv, membership clipped to ``window``, fx from fx.csv
    dividends: dict[str, dict[date, Decimal]]  # symbol -> ex_date -> amount (ascending)
    spy_dividends: tuple[Dividend, ...]  # SPY's, as benchmark.Dividend, ascending
    fingerprint: str
    manifest: Mapping[str, Any]
    unserved: tuple[str, ...] = ()  # requested members with no bars, sorted
    window: Window = DEV_WINDOW  # the window this store declares; its ``end`` is the D9 bound
    price_fingerprint: str | None = None  # price_fingerprint_of(files): fundamentals excluded
```

**File:** `engine/src/seer_engine/research.py:937-945`
**Change:** `load_store`'s return sets the field.
**Code:**
```python
    return ResearchData(
        market=market,
        dividends=dividends,
        spy_dividends=spy_dividends,
        fingerprint=fingerprint,
        manifest=manifest,
        unserved=unserved,
        window=window,
        price_fingerprint=price_fingerprint_of(files),
    )
```
**Impact:** additive. No manifest key, file or `fingerprint` changes; `sync-research-store` is
unaffected.

### Step 2: `store.py` — the `trial_provenance` table, its constants and the backfill rules

**File:** `engine/src/seer_engine/lab/store.py:51-62` (imports)
**Change:** add `from decimal import Decimal` after `from datetime import date, datetime, timezone`.
**Code:**
```python
from datetime import date, datetime, timezone
from decimal import Decimal
```

**File:** `engine/src/seer_engine/lab/store.py:70`
**Code:**
```python
SCHEMA_VERSION = "5"  # 2: synthesis kind; 3: trial_moments; 4: trial_funding; 5: trial_provenance (see _migrate)
```

**File:** `engine/src/seer_engine/lab/store.py:23-32` (module docstring)
**Change:** after the `trial_funding` bullet (ends "…Triggers refuse every UPDATE and DELETE." at
:27) insert a bullet, and replace the "Schema versions" paragraph (:29-32).
**Code:** insert after :27
```python
- ``trial_provenance``: the two inputs that make a re-run of one trial the same measurement and
  that no ``trials`` column carries -- the starting capital in IDR it ran on, and the price
  fingerprint (``research.price_fingerprint_of``: the four price files, fundamentals excluded) of
  the store it read. Exactly one row per trial: written by the run in its own transaction
  (``source='recorded'``), or added after the fact by a stated rule (``source='backfill'``: the
  v4 -> v5 migration and the seed import). Triggers refuse every UPDATE and DELETE.
```
and replace :29-32 with
```python
Schema versions (``meta.schema_version``): 1 is the first lab; 2 adds the ``synthesis`` insight
kind; 3 adds the ``trial_moments`` side table; 4 adds the ``trial_funding`` side table (the
money-weighted return of a trial that received deposits, and of the SPY fed the same ones); 5 adds
the ``trial_provenance`` side table and backfills it for every trial already recorded.
``connect`` migrates an older database in place; ``connect_readonly`` never does.
```

**File:** `engine/src/seer_engine/lab/store.py:277` (insert after `_FUNDING_TRIGGERS`, before
`_SCHEMA = f"""`)
**Change:** new constants and DDL.
**Code:**
```python
# The trial_provenance side table and its two triggers -- one definition of the v5 table, shared
# by ``_SCHEMA`` and ``_v4_to_v5`` for the same reason ``_FUNDING_TABLE`` is shared.
#
# **What it records and why (trial-reproducibility analysis, 2026-10-09).** A recorded trial can
# only be re-run as the same measurement if every input the engine reads is known, and two were
# not:
#
# - **the starting capital.** ``d79fc83`` (2026-10-08) moved ``backtest.runner.INITIAL_IDR`` from
#   20,000,000 to 10,000,000 IDR. It is not part of ``config_digest``, not a ``trials`` column, and
#   a recorded curve is normalised to its opening cash, so nothing said which capital a trial had
#   used -- and whole-share lot rounding makes it result-moving. Measured (M2): ``lab remeasure
#   M0011`` and ``M0007`` diverged at 10M by Sharpe deltas 9.5e-4 .. 5.2e-2 against a 1e-9
#   tolerance, and reproduced *every* variant with delta 0.000e+00 at 20M; ``lab costs M0011``
#   read +545.3% where trial #90 records +660.2% for the same reason.
# - **the price data.** ``trials.store_fingerprint`` hashes the whole store, fundamentals panel
#   included, so it over-reports drift: the three dev fingerprints carry byte-identical prices
#   (M1, ``research.price_fingerprint_of``).
#
# A side table, not columns on ``trials``, for exactly the reason ``trial_funding`` is one:
# ``trials`` is append-only and ``ALTER TABLE trials ADD COLUMN`` would move every recorded row's
# bytes. The capital is TEXT so the ``Decimal`` the run was given round-trips exactly;
# ``price_fingerprint`` is NULL when it is not known (a store whose file map this lab never saw),
# which a comparison must read as "unknown", never as a match.
PROVENANCE_SOURCES: tuple[str, ...] = ("recorded", "backfill")

_PROVENANCE_TABLE = f"""CREATE TABLE IF NOT EXISTS trial_provenance (
    trial_n           INTEGER PRIMARY KEY REFERENCES trials(n),
    initial_idr       TEXT NOT NULL CHECK (CAST(initial_idr AS REAL) > 0),
    price_fingerprint TEXT CHECK (price_fingerprint IS NULL OR length(trim(price_fingerprint)) > 0),
    source            TEXT NOT NULL CHECK (source IN ({_quoted(PROVENANCE_SOURCES)})),
    measured          TEXT NOT NULL CHECK (length(trim(measured)) > 0)
)"""
_PROVENANCE_TRIGGERS: tuple[str, ...] = (
    """CREATE TRIGGER IF NOT EXISTS trial_provenance_no_update BEFORE UPDATE ON trial_provenance
BEGIN SELECT RAISE(ABORT, 'trial_provenance is append-only: a provenance row is never updated'); END""",
    """CREATE TRIGGER IF NOT EXISTS trial_provenance_no_delete BEFORE DELETE ON trial_provenance
BEGIN SELECT RAISE(ABORT, 'trial_provenance is append-only: a provenance row is never deleted'); END""",
)

#: The backfill's capital rule, exact on every trial recorded before schema v5 (analysis M3).
#: Cross-checked with ``git merge-base --is-ancestor d79fc83 <trials.git_sha>`` over all 26
#: distinct ``git_sha`` values: the 20 shas behind trials #1..#128 predate ``d79fc83`` and none of
#: those trials has a ``trial_funding`` row; the 6 shas behind #129..#152 follow it and every one
#: of those trials has one. So "no funding row" and "ran at 20M" are the same set, and "funding
#: row" and "ran at 10M" are the same set -- test trials included (#123 and #125 lump at 20M,
#: #130 and #131 funded at 10M). This is a rule about the past; a trial recorded from v5 on
#: carries the capital its run was actually given and never passes through it.
BACKFILL_LUMP_SUM_IDR = Decimal("20000000")
BACKFILL_FUNDED_IDR = Decimal("10000000")

#: The price fingerprint of the P7a store -- a four-file store, so its whole fingerprint and its
#: price fingerprint are the same hash -- and of every dev store the lab has recorded against.
P7A_PRICE_FINGERPRINT = "5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a"

#: ``trials.store_fingerprint`` -> price fingerprint, for the backfill (analysis M1). Only stores
#: whose file map was actually seen are listed:
#:
#: - ``5451195f…`` (P7a, 2026-10-04, four files): itself.
#: - ``e597367b…`` (2026-10-05, adds a 2015-only ``fundamentals.csv``): ``5451195f…`` -- the
#:   ``399d0d25…`` refresh copied its four price files byte for byte (data-pipeline runbook).
#: - ``399d0d25…`` (2026-10-05, the panel rebuilt from 2009; today's dev store):
#:   ``5451195f…`` -- proven by ``research.price_fingerprint_of`` over its manifest.
#: - ``56e83810…`` (a four-file test store, window end 2026-10-06): itself.
#:
#: Anything else -- ``bbe7abfb…``, the test store on the other laptop, whose file map is not here
#: -- backfills NULL ("unknown"). No comparison reads a test trial against the dev benchmark, so
#: that NULL affects nothing today, and a NULL is the honest answer rather than a guess.
BACKFILL_PRICE_FINGERPRINTS: Mapping[str, str] = {
    P7A_PRICE_FINGERPRINT: P7A_PRICE_FINGERPRINT,
    "e597367bb6806d7edc2f9af4033b26c366aae92517207b4e71daad96346fcca3": P7A_PRICE_FINGERPRINT,
    "399d0d254c7a90b8cdb49f7ce598269087d38730f795cae90453eeb580b07cf8": P7A_PRICE_FINGERPRINT,
    "56e83810e82ed59d0857f6851a638a96fc94fdbb8f781a3f4d56914dce8d141a": (
        "56e83810e82ed59d0857f6851a638a96fc94fdbb8f781a3f4d56914dce8d141a"
    ),
}
```
**Impact:** constants only; `_quoted` is defined at :199, above this.

**File:** `engine/src/seer_engine/lab/store.py:363-368` (inside `_SCHEMA`)
**Change:** insert the provenance DDL after `{_FUNDING_TRIGGERS[1]};` and before
`CREATE TRIGGER IF NOT EXISTS trials_no_update`. Keep exactly one statement per paragraph, each
followed by `;` and a blank line — `test_lab_snapshot.py` strips them by that layout.
**Code:** the block from `{_FUNDING_TABLE};` to the first `trials_` trigger becomes
```python
{_FUNDING_TABLE};

{_FUNDING_TRIGGERS[0]};

{_FUNDING_TRIGGERS[1]};

{_PROVENANCE_TABLE};

{_PROVENANCE_TRIGGERS[0]};

{_PROVENANCE_TRIGGERS[1]};

CREATE TRIGGER IF NOT EXISTS trials_no_update BEFORE UPDATE ON trials
```

### Step 3: `store.py` — migration v4 → v5 with the backfill

**File:** `engine/src/seer_engine/lab/store.py:501` (insert after `_v3_to_v4`)
**Code:**
```python
def _v4_to_v5(conn: sqlite3.Connection) -> None:
    """Add the ``trial_provenance`` side table and its two append-only triggers, and give every
    trial that lacks a provenance row one, by the documented rules.

    Additive in the sense that matters: no ``trials``, ``trial_moments`` or ``trial_funding`` row
    is read-modified-written, rebuilt or re-keyed, no column is altered, and no verdict moves --
    ``trials`` is byte-identical across it, which
    ``test_connect_migrates_a_v4_database_backfilling_provenance_and_touching_no_trial`` pins.
    Unlike v3 -> v4 it does write rows, because the table is only useful when it is complete:
    ``lab remeasure`` / ``lab costs`` / the hard gate's de-funding refuse a trial with no
    recorded capital, so an empty v5 table would close every one of them.

    The rows are an **annotation, not a rewrite**: ``source='backfill'`` says they were added
    after the fact, by a rule, and the rule is in this file --

    - ``initial_idr``: ``BACKFILL_FUNDED_IDR`` (10M) when the trial has a ``trial_funding`` row,
      ``BACKFILL_LUMP_SUM_IDR`` (20M) when it has none -- exact on all 152 trials recorded before
      this version (analysis M3, cross-checked against git ancestry).
    - ``price_fingerprint``: ``BACKFILL_PRICE_FINGERPRINTS[trials.store_fingerprint]``, or NULL
      for a store whose file map this lab never saw (analysis M1).

    This is also R4's answer for the 58-trial ``5451195f…`` cohort: it needs neither re-running
    nor rewriting. Re-run on today's store at its recorded 20M, all 54 seed trials reproduce all
    six recorded metrics within ``remeasure.METRIC_TOL`` (analysis M4), and the annotation gives
    every one of them the same price fingerprint as the 84 trials recorded on ``399d0d25…``.

    Only trials with no row are touched, so a database that somehow already carries some rows
    (none should) keeps them. ``measured`` is the moment the annotation was made, not the run.
    """
    conn.execute(_PROVENANCE_TABLE)
    for trigger in _PROVENANCE_TRIGGERS:
        conn.execute(trigger)
    stamp = now_iso()
    rows = conn.execute(
        "SELECT t.n AS n, t.store_fingerprint AS store_fingerprint, "
        "       EXISTS (SELECT 1 FROM trial_funding f WHERE f.trial_n = t.n) AS funded "
        "FROM trials t "
        "WHERE NOT EXISTS (SELECT 1 FROM trial_provenance p WHERE p.trial_n = t.n) "
        "ORDER BY t.n"
    ).fetchall()
    insert_provenance(conn, [
        ProvenanceRow(
            trial_n=int(r["n"]),
            initial_idr=BACKFILL_FUNDED_IDR if r["funded"] else BACKFILL_LUMP_SUM_IDR,
            price_fingerprint=BACKFILL_PRICE_FINGERPRINTS.get(str(r["store_fingerprint"])),
            source="backfill",
            measured=stamp,
        )
        for r in rows
    ])
```
Note: `connect` sets `row_factory = sqlite3.Row` before `_migrate`, so `r["n"]` works.
`ProvenanceRow` and `insert_provenance` are defined further down the module (Step 4); they are
resolved at call time, which is after import.

**File:** `engine/src/seer_engine/lab/store.py:504-541`
**Change:** the ladder gains one rung; docstring updated.
**Code:** full replacement of `_migrate`
```python
def _migrate(conn: sqlite3.Connection) -> None:
    """Bring an older database up to ``SCHEMA_VERSION`` in one transaction under the write lock.

    A ladder: each step moves the database up exactly one version, so a v1 database reaches v5 in
    one open by running all four steps in order. v1 -> v2 adds the ``synthesis`` insight kind
    (``_v1_to_v2``); v2 -> v3 adds the ``trial_moments`` side table (``_v2_to_v3``); v3 -> v4 adds
    the ``trial_funding`` side table (``_v3_to_v4``); v4 -> v5 adds the ``trial_provenance`` side
    table and backfills it (``_v4_to_v5``) -- after v3 -> v4, because the backfill reads
    ``trial_funding``. A version this code does not know is refused rather than guessed at.

    Parallel sessions may connect at once, so the version is read again after
    ``BEGIN IMMEDIATE``: only the first one migrates, the others find the current version and do
    nothing. The backfill runs inside this same transaction, so a database is never seen at v5
    with its provenance half-written.
    """
    if schema_version(conn) == SCHEMA_VERSION:
        return
    begin_immediate(conn)
    try:
        found = schema_version(conn)
        version = found
        if version == "1":
            _v1_to_v2(conn)
            version = "2"
        if version == "2":
            _v2_to_v3(conn)
            version = "3"
        if version == "3":
            _v3_to_v4(conn)
            version = "4"
        if version == "4":
            _v4_to_v5(conn)
            version = "5"
        if version != SCHEMA_VERSION:
            raise LabError(
                f"lab database schema version {found!r} is unknown to this code "
                f"(expects {SCHEMA_VERSION})"
            )
        conn.execute("UPDATE meta SET value = ? WHERE key = 'schema_version'", (SCHEMA_VERSION,))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
```
**Impact:** any v1–v4 database opened with `store.connect` gains the table and one row per
existing trial. Fixture DBs in tests migrate too (they hold no trials, or trials with fake
fingerprints → NULL price fingerprint, capital by funding). A fresh database is created at v5
directly (`_SCHEMA` + `INSERT OR IGNORE` meta) and backfills nothing — its trials get provenance
from whoever inserts them (`run_method`, `run_test`, `seed`).

### Step 4: `store.py` — `ProvenanceRow`, `insert_provenance`, `provenance_of`

**File:** `engine/src/seer_engine/lab/store.py:1796` (insert after `insert_funding`, before the
`# ---- ideas_seen` banner at :1798)
**Code:**
```python
# --------------------------------------------------------------------------- trial provenance


@dataclass(frozen=True)
class ProvenanceRow:
    """What a re-run of one trial must be given to be the same measurement (schema v5).

    Every trial has exactly one row. ``lab remeasure`` and ``lab costs`` re-run a recorded trial
    at ``initial_idr`` (through ``runner.recorded_capital``), and the hard gate de-funds a funded
    curve in units of it; a trial with no row is refused by all three rather than re-run or
    de-funded at a guess.

    - ``trial_n``           the ``trials.n`` this describes. ``insert_trials`` assigns it;
                            ``insert_provenance`` refuses the pre-insert sentinel ``0``.
    - ``initial_idr``       the starting capital in IDR the run was given, as a ``Decimal`` --
                            the very value passed to ``dev.run_registry(initial_idr=...)``.
                            Stored as TEXT (``format(d, "f")``) so it round-trips exactly.
    - ``price_fingerprint`` ``research.price_fingerprint_of`` of the store the run read: the four
                            price files, fundamentals excluded. None when it is not known; a
                            reader must treat None as "unknown", never as a match.
    - ``source``            ``"recorded"`` when the run wrote it in its own transaction;
                            ``"backfill"`` when it was added after the fact by a rule stated in
                            this module (the v4 -> v5 migration) or in ``lab.seed`` (the P7a
                            import, whose run predates the lab).
    - ``measured``          an ISO timestamp: the trial's own ``run_at`` for a recorded row, the
                            moment of the annotation for a backfilled one.
    """

    trial_n: int
    initial_idr: Decimal
    price_fingerprint: str | None
    source: str
    measured: str


PROVENANCE_COLUMNS: tuple[str, ...] = tuple(f.name for f in fields(ProvenanceRow))


def provenance_of(conn: sqlite3.Connection, trial_n: int) -> sqlite3.Row | None:
    """The recorded provenance of one trial, or None when it has none.

    After the v4 -> v5 migration every trial has a row, so None on a migrated database means the
    trial was inserted by something that skipped this table -- and every caller that needs the
    capital refuses it (``runner.recorded_capital``) rather than assuming the live constant.

    A database on schema v1-v4 has no ``trial_provenance`` table at all and answers None the same
    way. ``connect`` migrates, so this can only be a ``connect_readonly`` caller; ``moments_of``
    and ``funding_of`` carry the same branch for the same reason.
    """
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'trial_provenance'"
    ).fetchone() is None:
        return None
    return conn.execute(
        "SELECT * FROM trial_provenance WHERE trial_n = ?", (int(trial_n),)
    ).fetchone()


def insert_provenance(conn: sqlite3.Connection, rows: Sequence[ProvenanceRow]) -> None:
    """Record the capital and price fingerprint of trials that already exist (the caller holds
    the transaction).

    Append-only and one row per trial: a trial that already has provenance is refused rather
    than overwritten -- a second capital for the same trial would make "re-run it as it was"
    ambiguous. ``trial_n`` must be a real trial number (the foreign key enforces existence; the
    explicit check turns the sentinel ``0`` into a readable refusal). The capital must be a
    positive, finite ``Decimal``: a float would not round-trip, and zero or NaN is not a sum any
    run could have started with.
    """
    cols = ", ".join(f'"{c}"' for c in PROVENANCE_COLUMNS)
    marks = ", ".join("?" for _ in PROVENANCE_COLUMNS)
    for r in rows:
        if r.trial_n <= 0:
            raise LabError(
                f"provenance needs the trial number insert_trials assigned, got {r.trial_n!r}: "
                "insert the trial first, then record its provenance"
            )
        capital = r.initial_idr
        if not isinstance(capital, Decimal):
            raise LabError(
                f"trial {r.trial_n}: initial_idr must be a Decimal, got "
                f"{type(capital).__name__} {capital!r}"
            )
        if not capital.is_finite() or capital <= 0:
            raise LabError(
                f"trial {r.trial_n}: initial_idr must be a positive, finite number of IDR, "
                f"got {capital!r}"
            )
        if r.source not in PROVENANCE_SOURCES:
            raise LabError(
                f"trial {r.trial_n}: provenance source must be one of {PROVENANCE_SOURCES}, "
                f"got {r.source!r}"
            )
        if provenance_of(conn, r.trial_n) is not None:
            raise LabError(
                f"trial {r.trial_n} already has recorded provenance: trial_provenance is "
                "append-only, and a second capital for the same trial would make a re-run ambiguous"
            )
        conn.execute(
            f"INSERT INTO trial_provenance ({cols}) VALUES ({marks})",
            [int(r.trial_n), format(capital, "f"), r.price_fingerprint, r.source, r.measured],
        )
```
**Impact:** new API only. `PROVENANCE_COLUMNS` order matches the list built in the INSERT.

### Step 5: `runner.recorded_capital`, and `run_method` / `run_test` record provenance

**File:** `engine/src/seer_engine/lab/runner.py:46-68` (imports)
**Change:** add two imports.
**Code:** after `from datetime import date` add
```python
from decimal import Decimal
```
and after `from seer_engine.backtest.metrics import external_cashflows` add
```python
from seer_engine.backtest.runner import INITIAL_IDR
```

**File:** `engine/src/seer_engine/lab/runner.py:122` (insert after `recorded_contributions`)
**Code:**
```python
def recorded_capital(conn: sqlite3.Connection, trial_n: int) -> Decimal:
    """The starting capital, in IDR, trial ``trial_n`` was run on -- its ``trial_provenance`` row.

    **Every path that re-runs a recorded trial must go through this**, beside
    ``recorded_contributions``, and for the same reason: a re-run at the wrong capital is not the
    same measurement. ``backtest.runner.INITIAL_IDR`` is the capital a *new* run gets; it moved
    from 20,000,000 to 10,000,000 IDR in ``d79fc83`` (2026-10-08), and whole-share lot rounding
    makes the capital result-moving. Measured (trial-reproducibility analysis M2/M4): at the live
    10M, ``lab remeasure M0011`` / ``M0007`` miss their recorded Sharpe by up to 5.2e-2 against a
    1e-9 tolerance and all 54 P7a seed trials diverge; at their recorded 20M every one reproduces
    exactly.

    ``store.LabError`` when the trial has no provenance row. After the v4 -> v5 migration every
    trial has one, so a missing row means the trial was inserted by something that skipped the
    table; re-running it at the live constant instead would be precisely the guess this exists
    to stop.
    """
    row = store.provenance_of(conn, int(trial_n))
    if row is None:
        raise store.LabError(
            f"trial #{int(trial_n)} has no recorded starting capital (no trial_provenance row), so "
            f"it cannot be re-run as the measurement it was. A trial recorded by `lab run` or "
            f"`lab test` carries one; a database opened by this code is backfilled on connect"
        )
    return Decimal(str(row["initial_idr"]))
```

**File:** `engine/src/seer_engine/lab/runner.py:359-446`
**Change:** full replacement of `run_method`: one local `capital`, passed to `run_registry` and
written into provenance.
**Code:**
```python
def run_method(
    conn: sqlite3.Connection,
    method: Method,
    path: Path,
    data: research.ResearchData,
    *,
    git_sha: str,
    require_commit: bool = True,
) -> list[Ran]:
    """Run ``method`` on the dev window and record it (see the module docstring).

    The run is given ``INITIAL_IDR`` -- passed to ``dev.run_registry`` explicitly rather than left
    to its default -- and that same value is written into each trial's ``trial_provenance`` row,
    with ``data.price_fingerprint``, in the transaction that inserts the trial. So the record can
    never name a capital the run was not given, and a later ``lab remeasure`` re-runs it at the
    capital it actually had, whatever ``INITIAL_IDR`` reads by then.
    """
    preflight(conn, method, path, require_commit=require_commit)
    capital = INITIAL_IDR
    results: list[tuple[DevRow, Any]] = []
    deposits: list[Sequence[tuple[date, float]]] = []

    def on_result(i: int, result: Any, row: DevRow) -> None:
        results.append((row, month_end_curve(result.snapshots)))
        cash = external_cashflows(result)
        deposits.append(cash)
        m = row.stats.metrics
        log.info(
            "[%d/%d] %s %s..%s: money-weighted %s vs DCA SPY TR %s (%d deposits, %.2f USD), "
            "max DD %s, PF %s, trades %d",
            i + 1, len(method.candidates), row.candidate.id, row.start, row.end,
            m.mwr, row.spy_tr.mwr, len(cash), float(sum(a for _, a in cash)),
            m.max_drawdown, m.profit_factor, m.trades,
        )

    dev.run_registry(
        data.market, data.dividends, data.spy_dividends, method.candidates,
        on_result=on_result, contributions=OWNER_MONTHLY, initial_idr=capital,
    )
    store.begin_immediate(conn)  # lab-wide N and the inserts, atomic against parallel sessions
    with conn:
        preflight(conn, method, path, require_commit=False)  # a parallel session may have won a race
        ran = trial_rows(
            conn, method, results, fingerprint=data.fingerprint, git_sha=git_sha, deposits=deposits
        )
        status = "dev-eligible" if any(r.trial.eligible for r in ran) else "rejected"
        if store.get_method(conn, method.id) is None:
            store.add_method(
                conn,
                id=method.id,
                name=method.name,
                family=method.family,
                source_kind=method.source_kind,
                source_ref=method.source_ref,
                hypothesis=_hypothesis(method),
                parent_id=method.parent_id,
                status="registered",
            )
        else:
            row = store.get_method(conn, method.id)
            if row["status"] == "idea":
                store.update_method(
                    conn, method.id, hypothesis=_hypothesis(method), name=method.name,
                    family=method.family, source_kind=method.source_kind,
                    source_ref=method.source_ref, parent_id=method.parent_id,
                )
                store.update_method(conn, method.id, status="registered")
        ns = store.insert_trials(conn, [r.trial for r in ran])
        # The DSR's inputs, stamped with the trial numbers SQLite just assigned, in this same
        # transaction: a trial and the measurement that judged it are recorded together or not
        # at all. A variant with no computable moments contributes no row, exactly as it
        # contributes no dsr.
        store.insert_moments(conn, [
            replace(r.moments, trial_n=n)
            for n, r in zip(ns, ran, strict=True)
            if r.moments is not None
        ])
        # The deposits and what they earned, stamped the same way and in the same transaction, for
        # the same reason: the money-weighted verdict and the trial it judges are one record. A
        # variant that received no deposit contributes no row, and no row is how the lab says
        # "this run was not fed" -- the answer `funding_of` gives for all 128 trials recorded
        # before this, which this phase does not backfill (GOTRADE_FEE_REBUILD_PLAN.md D18).
        store.insert_funding(conn, [
            replace(r.funding, trial_n=n)
            for n, r in zip(ns, ran, strict=True)
            if r.funding is not None
        ])
        # The two inputs a re-run needs and no `trials` column carries -- the capital this batch
        # was given and the price fingerprint of the store it read -- one row per trial, in this
        # same transaction. Unlike funding, every trial gets a row: there is no run without a
        # starting capital.
        store.insert_provenance(conn, [
            store.ProvenanceRow(
                trial_n=n,
                initial_idr=capital,
                price_fingerprint=data.price_fingerprint,
                source="recorded",
                measured=r.trial.run_at,
            )
            for n, r in zip(ns, ran, strict=True)
        ])
        store.update_method(conn, method.id, source_sha=source_sha(path), status=status)
        for key in method.seen_keys:
            store.mark_seen(conn, key, method.id)
    return ran
```

**File:** `engine/src/seer_engine/lab/runner.py:741-790` (inside `run_test`)
**Change:** `capital` local, passed to `run_registry`, provenance row written inside the look's
transaction after the funding row. Replace from the line `captured: list[tuple[DevRow, Any,
Sequence[tuple[date, float]]]] = []` (:743) to the end of the function (:791) with:
**Code:**
```python
    capital = INITIAL_IDR
    captured: list[tuple[DevRow, Any, Sequence[tuple[date, float]]]] = []

    def on_result(i: int, result: Any, row: DevRow) -> None:
        captured.append((row, month_end_curve(result.snapshots), external_cashflows(result)))

    dev.run_registry(
        data.market,
        data.dividends,
        data.spy_dividends,
        (candidate,),
        on_result=on_result,
        window=window,
        contributions=OWNER_MONTHLY,
        initial_idr=capital,
    )
    (row, curve, cash), = captured
    m = row.stats.metrics
    log.info(
        "%s on the test window %s..%s: money-weighted %s vs DCA SPY TR %s (%d deposits, %.2f USD), "
        "max DD %s, PF %s, trades %d",
        candidate.id, row.start, row.end, m.mwr, row.spy_tr.mwr,
        len(cash), float(sum(a for _, a in cash)),
        m.max_drawdown, m.profit_factor, m.trades,
    )
    store.begin_immediate(conn)  # the look and the status move, atomic against parallel sessions
    with conn:
        # A parallel session may have won the race to this configuration's one look. `pre` is
        # the pre-registration git already vouched for above, so this re-check costs no
        # subprocess and still re-runs check_digest and both database refusals.
        preflight_test(conn, method, path, candidate, pre=pre, require_commit=False)
        trial = test_trial_row(conn, method, row, curve, fingerprint=data.fingerprint, git_sha=git_sha)
        status = "test-passed" if row.eligible else "test-failed"
        (n,) = store.insert_trials(conn, [trial])
        # Inside this transaction on purpose: a raise here rolls the look back rather than
        # spending it, and a spent test-window look is unrecoverable (`UNIQUE(config_digest,
        # window)` plus the append-only triggers mean the configuration never gets a second one).
        # The `if cash:` guard is load-bearing too -- an unconditional insert would hit
        # `trial_funding`'s `deposits_usd > 0` CHECK on a window with no 25th in it and fail a
        # look that had nothing wrong with it. Do not move either out of the transaction.
        if cash:
            store.insert_funding(conn, [store.FundingRow(
                trial_n=n,
                mwr=_f(m.mwr),
                spy_tr_mwr=_f(row.spy_tr.mwr),
                deposits_usd=float(sum(a for _, a in cash)),
                deposits_n=len(cash),
                schedule=OWNER_SCHEDULE_TEXT,
                measured=trial.run_at,
            )])
        # The look's capital and price fingerprint, in the same transaction and for the same
        # reason: the record of the look and what it was given land together or not at all.
        store.insert_provenance(conn, [store.ProvenanceRow(
            trial_n=n,
            initial_idr=capital,
            price_fingerprint=data.price_fingerprint,
            source="recorded",
            measured=trial.run_at,
        )])
        store.update_method(conn, method.id, status=status)
    return Tested(trial=trial, row=row, status=status)
```
**Impact:** `lab run` / `lab test` results are byte-identical (capital unchanged, now explicit);
one extra row per trial. Test doubles of `run_registry` with a fixed keyword list must accept
`initial_idr` (Step 12).

### Step 6: `seed.py` writes the seed trials' provenance

**File:** `engine/src/seer_engine/lab/seed.py:1-10` (module docstring)
**Change:** add a bullet after the "P7a's 54 dev-window candidates…" bullet.
**Code:**
```python
- Each of the 54 gets a ``trial_provenance`` row: 20,000,000 IDR (``P7A_INITIAL_IDR``, the
  engine's starting capital when P7a ran) and ``P7A_FINGERPRINT`` as its price fingerprint (a
  four-file store, so the two fingerprints are one hash). ``source='backfill'``: P7a ran before
  the lab, so these are a stated fact about that run, not something the run wrote.
```

**File:** `engine/src/seer_engine/lab/seed.py:14-18` (imports) — add `from decimal import Decimal`
after `import sqlite3`.

**File:** `engine/src/seer_engine/lab/seed.py:30` (after `P7A_RUN_AT`)
**Code:**
```python
# The capital P7a's 54 candidates ran on: `backtest.runner.INITIAL_IDR` at b2ec090, before
# d79fc83 (2026-10-08) moved it to 10,000,000 IDR. Re-run at this sum on today's store, all 54
# reproduce all six recorded metrics (trial-reproducibility analysis M4); at 10M all 54 diverge.
P7A_INITIAL_IDR = Decimal("20000000")
```

**File:** `engine/src/seer_engine/lab/seed.py:141-156` (the `with conn:` block in `seed`)
**Change:** keep the trial numbers and record provenance in the same transaction.
**Code:** replace the block with
```python
    with conn:
        for fam, (name, hypothesis) in P7A_FAMILIES.items():
            store.add_method(
                conn, id=f"H-P7A-{fam}", name=name, family=f"p7a-{fam.lower()}", source_kind="seed",
                source_ref=P7A_REPORT, hypothesis=hypothesis, status="rejected",
                verdict="P7a: none eligible on the dev window; every candidate failed max DD <= 15%",
                allow_any_status=True,
            )
        for mid, name, family, hypothesis, verdict in HISTORICAL:
            store.add_method(
                conn, id=mid, name=name, family=family, source_kind="seed", source_ref="docs/ROADMAP.md",
                hypothesis=hypothesis, status="rejected", verdict=verdict, allow_any_status=True,
            )
        ns = store.insert_trials(conn, trials)
        store.insert_provenance(conn, [
            store.ProvenanceRow(
                trial_n=n,
                initial_idr=P7A_INITIAL_IDR,
                price_fingerprint=P7A_FINGERPRINT,
                source="backfill",
                measured=P7A_RUN_AT,
            )
            for n in ns
        ])
        for c in REGISTRY:
            store.mark_seen(conn, f"concept:{c.id.lower()}", f"H-P7A-{c.family}", c.rationale)
    return len(trials)
```
**Impact:** every seeded test lab now carries 54 provenance rows; `seed` stays deterministic
(`measured` is the constant `P7A_RUN_AT`).

### Step 7: `remeasure.py` — the dev path runs at the recorded capital

**File:** `engine/src/seer_engine/lab/remeasure.py:48-68` (imports)
**Change:** add `from decimal import Decimal` after `from dataclasses import dataclass`, and
`from seer_engine.lab.runner import recorded_capital` after
`from seer_engine.lab.method import METHOD_ID, Method, config_digest, source_sha`.
(`lab.runner` does not import `remeasure`, directly or indirectly — no cycle.)

**File:** `engine/src/seer_engine/lab/remeasure.py:164-176`
**Code:** replace `Plan` with
```python
@dataclass(frozen=True)
class Plan:
    """What ``remeasure`` would do, decided from the database alone: no store, no backtest."""

    method_id: str
    batches: tuple[Batch, ...]
    candidates: tuple[Candidate, ...]  # the variants to re-run, in trial order
    missing: tuple[int, ...]  # trial numbers with no trial_moments row
    present: tuple[int, ...]  # trial numbers that already have one
    initial_idr: Decimal  # the one starting capital every one of these trials was recorded at

    @property
    def nothing_to_do(self) -> bool:
        return not self.missing
```

**File:** `engine/src/seer_engine/lab/remeasure.py:286` (insert before `def preflight(`)
**Code:**
```python
def plan_capital(conn: sqlite3.Connection, label: str, ns: Sequence[int]) -> Decimal:
    """The one starting capital trials ``ns`` were recorded at (``runner.recorded_capital``).

    One ``dev.run_registry`` call runs every candidate at one capital, so a set of trials recorded
    at two different capitals has no single re-run that reproduces them all -- the same shape as
    ``measure``'s refusal of a plan mixing funded and unfunded trials. ``store.LabError`` when
    the trials disagree, when any has no recorded capital, or when there are none.

    Why the capital matters at all (trial-reproducibility analysis M2/M4): ``INITIAL_IDR`` moved
    from 20M to 10M IDR in ``d79fc83``, and at the live 10M ``M0007``, ``M0011`` and all 54 seed
    trials fail to reproduce on an unchanged store; at their recorded 20M every one does.
    """
    by_capital: dict[Decimal, list[int]] = {}
    for n in ns:
        by_capital.setdefault(recorded_capital(conn, int(n)), []).append(int(n))
    if not by_capital:
        raise store.LabError(f"{label}: no trial to re-run, so there is no capital to re-run it at")
    if len(by_capital) > 1:
        parts = []
        for capital, group in sorted(by_capital.items()):
            numbers = ", ".join(f"#{n}" for n in group)
            parts.append(f"{capital:,.0f} IDR for {numbers}")
        raise store.LabError(
            f"{label}: these trials were recorded at different starting capitals "
            f"({'; '.join(parts)}), so one re-run cannot reproduce them all: one run_registry call "
            f"runs every candidate at one capital. Nothing is backfilled"
        )
    (capital,) = by_capital
    return capital
```

**File:** `engine/src/seer_engine/lab/remeasure.py:359-366` (end of `preflight`)
**Change:** resolve the capital from the database before any store is loaded.
**Code:** replace the `have = …` line and the `return Plan(...)` with
```python
    have = {int(r["n"]) for r in trials if store.moments_of(conn, int(r["n"])) is not None}
    # Refused here, before the caller loads a research store: a re-run at a capital the trials
    # did not have is not the recorded measurement, and neither is one at two capitals.
    capital = plan_capital(conn, method.id, [int(r["n"]) for r in trials])
    return Plan(
        method_id=method.id,
        batches=batches_of(conn, trials),
        candidates=tuple(by_digest[str(r["config_digest"])] for r in trials),
        missing=tuple(int(r["n"]) for r in trials if int(r["n"]) not in have),
        present=tuple(sorted(have)),
        initial_idr=capital,
    )
```

**File:** `engine/src/seer_engine/lab/remeasure.py:372-417` (`measure`, through the
`dev.run_registry(...)` call)
**Change:** docstring gains the capital paragraph; the call passes `initial_idr=plan.initial_idr`.
**Code:** replace from `def measure(` through the closing `)` of `dev.run_registry(` (:417) with
```python
def measure(
    conn: sqlite3.Connection, method: Method, plan: Plan, data: research.ResearchData
) -> tuple[Reproduced, ...]:
    """Re-run ``plan.candidates`` on the dev window and reproduce each trial's recorded numbers.

    ``conn`` is read from only (``plan`` already carries every row this needs); it is taken so the
    signature matches the rest of the module and a future check can reach the database without a
    call-site change.

    The dev window is not a parameter and not a choice. ``data`` is refused unless it *is* the dev
    window -- the mirror of ``runner.run_test``'s refusal of a dev store -- and ``dev.run_registry``
    is called with no ``window`` keyword, so the run is bounded by ``DEV_WINDOW`` by construction.

    The **funding** is not a parameter either: it is read off the trials being reproduced. A trial
    with a ``trial_funding`` row was run on ``sim.contributions.OWNER_MONTHLY`` and is re-run on
    it; a trial without one was run on a lump sum and is re-run on a lump sum. Getting this wrong
    is not a small error -- measured, an unfunded re-run of a funded trial reports an annualized
    Sharpe of 0.26 against a recorded 2.65 and this module correctly refuses to write anything. A
    plan that mixes the two is refused outright, because one ``run_registry`` call runs every
    candidate on one schedule and there is no answer that reproduces both.

    The **starting capital** is not a parameter for the same reason: it is ``plan.initial_idr``,
    the one capital ``preflight`` read off the trials' ``trial_provenance`` rows, and never the
    live ``INITIAL_IDR``. Measured 2026-10-09: at the live 10,000,000 IDR, ``M0011`` and ``M0007``
    miss their recorded Sharpe by 9.5e-4 .. 5.2e-2 against ``SHARPE_TOL``; at their recorded
    20,000,000 IDR every variant reproduces with delta 0.000e+00.
    """
    if data.window != research.DEV_WINDOW:
        w = data.window
        raise store.LabError(
            f"{method.id}: this research store was built for the {w.name!r} window "
            f"({w.start}..{w.end}); `lab remeasure` re-runs the dev window and nothing else. "
            f"Build it with `python -m seer_engine research_store`"
        )
    ns = tuple(sorted(plan.missing + plan.present))
    funded = tuple(n for n in ns if store.funding_of(conn, n) is not None)
    if funded and len(funded) != len(ns):
        raise store.LabError(
            f"{method.id}: trials {funded} received deposits and "
            f"{tuple(n for n in ns if n not in funded)} did not, so one re-run cannot reproduce "
            f"both. Nothing is backfilled"
        )
    contributions = OWNER_MONTHLY if funded else None
    rows: dict[str, DevRow] = {}

    def on_result(i: int, result: Any, row: DevRow) -> None:
        rows[config_digest(row.candidate)] = row

    dev.run_registry(
        data.market, data.dividends, data.spy_dividends, plan.candidates,
        on_result=on_result, contributions=contributions, initial_idr=plan.initial_idr,
    )
```
The rest of `measure` (from `out: list[Reproduced] = []`, :418) is unchanged.
**Impact:** `remeasure.remeasure` (:535) is unchanged; it calls `preflight` twice (once outside,
once under the lock) — the second resolves the same capital (provenance is append-only).

### Step 8: `remeasure.py` — the seed path, and the METRIC_TOL comment

**File:** `engine/src/seer_engine/lab/remeasure.py:666-669`
**Change:** replace the now-false paragraph (it described a measurement at a capital nobody
recorded; at today's code it does not hold).
**Code:** replace lines 666-669 (from `# 1e-6 is 2x the rounding bound.` through `…in the third
decimal.`) with
```python
# 1e-6 is 2x the rounding bound. Re-measured 2026-10-09 against the committed database and the dev
# store `399d0d25...` (trial-reproducibility analysis M4): **at the capital these trials ran on**
# -- 20,000,000 IDR, their `trial_provenance` row, which `remeasure_seed` hands every chunk -- all
# 54 reproduce all six metrics within this tolerance, exact on trades. The worst delta recorded
# when the tolerance was set was 4.986e-07, under the bound, so the headroom exists for a libm or
# platform ulp and for nothing larger. A genuine divergence is orders of magnitude bigger, and the
# one actually observed was not the store: at the live `INITIAL_IDR` of 10,000,000 IDR (`d79fc83`,
# 2026-10-08) all 54 diverge -- `REF-SPY-HOLD` total return 5.945958 recorded against 5.874617
# re-run, `F9-SPY200M70-MOM30` 8.786433 against 8.031926 with 17 fewer trades -- because
# whole-share lot rounding makes the starting capital a result-moving input. The three dev
# fingerprints the lab's trials carry hold byte-identical price files (analysis M1).
```

**File:** `engine/src/seer_engine/lab/remeasure.py:995-1002` (end of `seed_preflight`)
**Code:** replace the `have = …` line and the `return SeedPlan(...)` with
```python
    have = {p.n for p in pairs if store.moments_of(conn, p.n) is not None}
    todo = tuple(p for p in pairs if p.n not in have)
    if todo:
        # Refused here, before any store is loaded, exactly as `preflight` refuses for the dev
        # path: a seed trial with no recorded capital cannot be re-run as the measurement it was
        # (analysis M4), and a to-do set recorded at two capitals has no single re-run (one
        # `run_registry` call, one capital). `remeasure_seed` resolves the same capital per chunk.
        plan_capital(conn, wanted, [p.n for p in todo])
    return SeedPlan(
        method_id=wanted,
        todo=todo,
        present=tuple(sorted(have)),
        var_trials=seed_var_trials(conn),
        n_at_run=n_at_run.pop(),
    )
```

**File:** `engine/src/seer_engine/lab/remeasure.py:1026-1055`
**Code:** full replacement of `run_chunk`
```python
def run_chunk(
    data: research.ResearchData, candidates: Sequence[Candidate], *, initial_idr: Decimal
) -> dict[str, Observed | None]:
    """Re-run ``candidates`` on the dev window at ``initial_idr``; ``{candidate id: Observed}``.

    The dev window is not a parameter and not a choice: this function has no ``window``
    parameter, and ``dev.run_registry`` is called with no ``window`` keyword, so the run is
    bounded by ``DEV_WINDOW`` by construction. ``remeasure_seed`` has already refused any ``data``
    that is not the dev window before this is reached.

    ``initial_idr`` is required, with no default, because there is no right default: it is the
    capital the chunk's trials were recorded at (``plan_capital``), and defaulting to the live
    ``INITIAL_IDR`` is exactly what made all 54 seed trials diverge on 2026-10-09 (analysis M4).

    Splitting the 54 into chunks is free of correctness cost. ``run_registry`` rebuilds its
    per-allocator ``prepare_for`` cache per call, so a chunk pays re-preparation time, but the
    measurement is identical: re-running ``F1-SPY-SMA200-M``, ``F3-SEC-TOP3-6M-TREND``,
    ``F4-MOM12-N20-TREND`` and ``F9-SPY200M70-MOM30`` alone and inside the full 54-candidate call
    gives **bit-identical** annualized Sharpes and ``t``. That is what makes it safe for the batch
    to be interrupted and resumed at any boundary.

    This is the seam the tests replace. Everything above it -- the refusals, the digest guard --
    and everything below it -- the metric checks, the chunked write, the report -- is exercised
    against a substituted ``run_chunk`` without a research store.
    """
    out: dict[str, Observed | None] = {}

    def on_result(i: int, result: Any, row: DevRow) -> None:
        out[row.candidate.id] = observe(row)

    dev.run_registry(
        data.market, data.dividends, data.spy_dividends, list(candidates), on_result=on_result,
        initial_idr=initial_idr,
    )
    return out
```

**File:** `engine/src/seer_engine/lab/remeasure.py:1133-1134` (inside `remeasure_seed`'s
`for index, group in enumerate(groups):` loop)
**Change:** the first statement of the loop body, `fresh = run_chunk(data, [s.candidate for s in
group])`, becomes
**Code:**
```python
        # One capital per chunk, read off the trials' provenance -- never the live constant.
        # `seed_preflight` already refused a to-do set recorded at two capitals before the store
        # loaded, so this resolves the one capital it found; it stays a refusal (not an assert)
        # so a chunk can never be re-run at a capital nobody checked.
        capital = plan_capital(conn, plan.method_id, [s.n for s in group])
        fresh = run_chunk(data, [s.candidate for s in group], initial_idr=capital)
```
**Impact:** the loop variable named `seed` inside `remeasure_seed` is untouched; nothing named
`seed` is imported into this module.

### Step 9: `real_costs.measure` takes the recorded capital; `_costs` passes it

**File:** `engine/src/seer_engine/lab/real_costs.py:36`
**Change:** add after `from seer_engine.backtest.dev import FAILURE_LABELS, Candidate, DevRow`:
```python
from seer_engine.backtest.runner import INITIAL_IDR
```

**File:** `engine/src/seer_engine/lab/real_costs.py:247-280`
**Change:** new keyword, docstring paragraph, pass-through. Replace from `def measure(` through
the closing `)` of the `dev.run_registry(` call with
**Code:**
```python
def measure(
    method: Method,
    candidate: Candidate,
    trial: Mapping[str, Any],
    data: research.ResearchData,
    *,
    contributions: Any = None,
    initial_idr: Decimal = INITIAL_IDR,
) -> Comparison:
    """Run ``candidate`` at both cost models on the dev window. Writes nothing anywhere.

    ``contributions`` is the funding the **recorded** trial ran on -- resolve it with
    ``lab.runner.recorded_contributions(conn, trial["n"])`` and pass it through, so the re-run is
    the same measurement and ``Comparison.reproduced`` means what it says. Measured: re-running a
    funded trial unfunded lands on a different total return, and the report then announces that
    the store or the engine changed when neither did. None -- the default -- is right for every
    trial recorded before the lab was funded, which is all 128 of them.

    ``initial_idr`` is the starting capital the recorded trial ran on, for the same reason --
    resolve it with ``lab.runner.recorded_capital(conn, trial["n"])``. Measured 2026-10-09: the
    flat side of ``lab costs M0011`` read +545.3% at the live 10,000,000 IDR where trial #90
    records +660.2%, because the trial ran at 20,000,000 IDR and whole-share rounding makes the
    capital result-moving (trial-reproducibility analysis M2). The default is the live constant
    only so a caller re-measuring something that is not a recorded trial need not invent one;
    ``commands/lab.py:_costs`` always passes the recorded value.

    Both sides are fed the same schedule and the same capital, so the flat/Gotrade comparison is
    still a comparison of one variant at two fee models and nothing else.
    """
    if data.window != research.DEV_WINDOW:
        w = data.window
        raise store.LabError(
            f"{method.id}: this research store was built for the {w.name!r} window "
            f"({w.start}..{w.end}); `lab costs` re-runs the dev window and nothing else. "
            f"Build it with `python -m seer_engine research_store`"
        )
    flat, real = twins(candidate)
    rows: dict[str, DevRow] = {}

    def on_result(i: int, result: Any, row: DevRow) -> None:
        rows[row.candidate.id] = row

    dev.run_registry(
        data.market, data.dividends, data.spy_dividends, (flat, real),
        on_result=on_result, contributions=contributions, initial_idr=initial_idr,
    )
```
The rest of `measure` (from `f, g = rows[flat.id], rows[real.id]`) is unchanged. `Decimal` is
already imported in `real_costs.py` (:31). `real_costs` must **not** import `lab.runner`
(`runner` imports `real_costs`).

**File:** `engine/src/seer_engine/commands/lab.py:1720-1745` (inside `_costs` only)
**Change:** resolve the capital before the store is loaded (a missing row refuses with exit 2 and
loads nothing), then pass it.
**Code:** replace
```python
    method, _path = real_costs.resolve_method(args.method)
    candidate, trial = real_costs.pick_candidate(conn, method, args.candidate)
    real_costs.twins(candidate)  # refuses a variant with no real-fee twin before the store loads
```
with
```python
    method, _path = real_costs.resolve_method(args.method)
    candidate, trial = real_costs.pick_candidate(conn, method, args.candidate)
    real_costs.twins(candidate)  # refuses a variant with no real-fee twin before the store loads
    # The capital the recorded trial ran on, resolved before the store loads: a trial with none
    # recorded is refused here, and a re-run at the live INITIAL_IDR would not be the trial
    # (trial #90: +545.3% at 10M against +660.2% recorded at 20M).
    capital = runner.recorded_capital(conn, int(trial["n"]))
```
and replace
```python
    cmp = real_costs.measure(
        method, candidate, trial, data,
        contributions=runner.recorded_contributions(conn, int(trial["n"])),
    )
```
with
```python
    cmp = real_costs.measure(
        method, candidate, trial, data,
        contributions=runner.recorded_contributions(conn, int(trial["n"])),
        initial_idr=capital,
    )
```

### Step 10: `hardgate.trial_deposits` divides by the recorded capital

**File:** `engine/src/seer_engine/lab/hardgate.py:183-227` (45 lines at `e5eda52`; the replacement is 55, so everything below moves +10 — phase 3 quotes it that way)
**Code:** full replacement
```python
def trial_deposits(
    conn: sqlite3.Connection, row: sqlite3.Row, curve: list[tuple[date, float]]
) -> dict[date, float]:
    """What a funded trial received inside each curve step, in the curve's own units.

    A recorded curve is normalised to the opening cash, so one deposit is
    ``amount_idr / <the capital the trial ran on>`` -- 0.5 for the owner's 5,000,000 against the
    10,000,000 start every funded trial has used so far -- and no exchange rate is involved,
    because the run converted both at the same rate. (M0032's curve opens at 1.5 for exactly this
    reason: January's deposit is already in the first point.)

    **The divisor is the trial's recorded capital** (``runner.recorded_capital``: its
    ``trial_provenance`` row), never the live ``backtest.runner.INITIAL_IDR``. For all 24 funded
    trials recorded today the two are the same 10,000,000 IDR, which is why the switch moves no
    verdict (trial-reproducibility analysis M5: 0 stranded). They stop being the same number the
    moment the constant moves again -- ``d79fc83`` already moved it once, 20M to 10M, on
    2026-10-08 -- and a de-funding that read the constant would then silently credit every
    deposit of every funded trial at a size it never had. A funded trial with no recorded
    capital is refused (``store.LabError``) rather than de-funded at a guess.

    ``{}`` for a lump-sum trial, which is every trial recorded before the contribution schedule
    existed. Without this, slicing a funded curve counts the owner's deposits as growth and
    compares the result against a benchmark that received none -- see ``regime.split``.

    This lived in ``commands/lab.py`` as ``_trial_deposits`` until the hard gate needed it too.
    It is here, not there, so that the gate, ``lab regime`` and ``lab walkforward`` share **one**
    de-funding path: a second reconstruction is a second chance to read a deposit as edge.
    """
    from seer_engine import dates as nyse
    from seer_engine.backtest.regime import bucket
    from seer_engine.lab import runner as labrunner

    schedule = labrunner.recorded_contributions(conn, int(row["n"]))
    if schedule is None:
        return {}
    start, end = date.fromisoformat(row["start"]), date.fromisoformat(row["end"])
    capital = labrunner.recorded_capital(conn, int(row["n"]))
    unit = float(schedule.amount_idr / capital)
    due = schedule.dates_in(start, end)
    credited: dict[date, float] = {}
    for d in due:
        session = d if nyse.is_session(d) else nyse.next_session(d)
        if session > end:
            continue
        credited[session] = credited.get(session, 0.0) + unit
    recorded = store.funding_of(conn, int(row["n"]))
    expected = int(recorded["deposits_n"])
    if len(due) != expected:
        raise store.LabError(
            f"{row['candidate_id']}: reconstructed {len(due)} deposits from "
            f"{recorded['schedule']!r} over {start}..{end}, but the trial records {expected}. "
            f"The schedule in sim.contributions has moved since this trial ran, so its curve "
            f"cannot be de-funded safely; `lab regime` will not guess"
        )
    return bucket(curve, credited)
```
(`schedule.amount_idr` is a `Decimal`; `Decimal / Decimal` then `float(...)` — identical to
today's arithmetic when the recorded capital is 10M.)
**Impact:** `fold_record`, `lab walkforward`, `lab regime` read the same numbers on every
existing trial (all funded trials backfill at 10M). Not touched: anything else in `hardgate.py`.

### Step 11: test fixtures carry a price fingerprint, and one helper stamps provenance

**File:** `engine/tests/labkit.py:1-16` (imports), `:53-59`, `:92-106`, and the end of the file
**Change:** import `store`; add one keyword to each `ResearchData(...)`; append the plan set's
**only** fixture provenance helper. Phase 3 imports it for its gate fixtures and does not edit
`labkit.py`; every test file that stamps fixture provenance uses it (store-level tests of
`insert_provenance` itself, in `test_lab_store.py`, build `ProvenanceRow`s directly on purpose).
**Code:** in the import block, after `from seer_engine.backtest.window import Window` add
```python
from seer_engine.lab import store
```
in `smoke_data`:
```python
    return ResearchData(
        market=smoke_market(extra),
        dividends={"SPY": {SPY_EX_DATE: spy_div}},
        spy_dividends=(Dividend(SPY_EX_DATE, spy_div),),
        fingerprint="smoke",
        manifest={},
        price_fingerprint="smoke",
    )
```
and in `smoke_test_data`, after `window=smoke_test_window(),` add
```python
        price_fingerprint="smoke-test",
```
append at the end of the file (after `smoke_test_data`):
```python


# ---- per-trial provenance (trial-reproducibility) --------------------------------------------

#: The price fingerprint every dev trial in the committed lab carries (analysis M1): the P7a
#: store's, which is also the current dev store's with ``fundamentals.csv`` left out.
LAB_PRICE_FINGERPRINT = store.P7A_PRICE_FINGERPRINT


def stamp_provenance(
    conn,
    trial_ns: Iterable[int],
    *,
    price_fingerprint: str | None = LAB_PRICE_FINGERPRINT,
    initial_idr: Decimal = Decimal("10000000"),
) -> None:
    """Record provenance for fixture trials, the way ``lab run`` does for real ones.

    Every reader of a trial's provenance -- ``runner.recorded_capital``, the hard gate's
    de-funding -- refuses a trial with no row, so a fixture that inserts trials with
    ``store.insert_trials`` and then asks one of them anything stamps them here. ``initial_idr``
    defaults to today's ``INITIAL_IDR``, 10,000,000, so a funded fixture's de-funding unit stays
    ``5,000,000 / 10,000,000 = 0.5``; it is a ``Decimal`` because ``insert_provenance`` refuses
    anything else. The caller holds the transaction, as with every ``store.insert_*``.

    **Idempotent.** ``trial_provenance`` is append-only and refuses a second row for a trial, so
    a trial that already has one -- from ``run_method``, ``seed``, the v4 -> v5 backfill or an
    earlier stamp -- is skipped. Two fixture helpers that both stamp the same trial therefore
    never collide, and the first stamp wins.
    """
    store.insert_provenance(conn, [
        store.ProvenanceRow(
            trial_n=int(n), initial_idr=initial_idr, price_fingerprint=price_fingerprint,
            source="recorded", measured="test fixture",
        )
        for n in trial_ns
        if store.provenance_of(conn, int(n)) is None
    ])
```
(`Iterable` and `Decimal` are already imported by `labkit`. `labkit` → `seer_engine.lab.store`
adds no cycle: `store` imports nothing from `tests/`.)

### Step 12: tests

All new tests follow the house voice: a docstring saying what is pinned and why.

**12a. `engine/tests/test_research_store.py`** — append at end of file:
```python
# ---- the price fingerprint (trial-reproducibility phase 2) ------------------------------------

#: The live dev store's file map on 2026-10-09 (`engine/.research/manifest.json`, store fingerprint
#: 399d0d25...). Pinned as data so the measurement it encodes (analysis M1) is arithmetic a test
#: can check without the 282 MB store.
DEV_STORE_FILES_20261009 = {
    "bars.csv": "4148a0fbcf3af8d7432618c8b92101a1447f47dcf11e7fffb984881392e39109",
    "dividends.csv": "3a46b0a4ff24819afddb79d9d62d328bb6db2a6cabc0bce3da622d7845ed3067",
    "fundamentals.csv": "79c880ecf7bce03812d5076c02c92bd58c089b5c9ec149a8d6985adff58334e2",
    "fx.csv": "7bd5aff00a5ec26133771f6a11eff0b6c584b918b2c3fec4bcba7f4786500748",
    "unserved.csv": "e58d0496b439209a15a2ef8a316d80cfddce4d4ad733c8601d06b26884753e16",
}


def test_today_s_dev_store_has_the_p7a_store_s_prices():
    """Analysis M1: the store fingerprint moved with the panel; the price fingerprint never did."""
    assert research.fingerprint_of(DEV_STORE_FILES_20261009) == (
        "399d0d254c7a90b8cdb49f7ce598269087d38730f795cae90453eeb580b07cf8"
    )
    assert research.price_fingerprint_of(DEV_STORE_FILES_20261009) == (
        "5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a"
    )


def test_the_price_fingerprint_ignores_the_fundamental_panel(tmp_path, members_dir):
    """A four-file store's two fingerprints are one hash; adding a panel moves only the store's."""
    store = tmp_path / "store"
    build(store, members_dir)  # facts=None: four files, no panel
    four = research.load_store(store, data_dir=members_dir)
    assert four.price_fingerprint == four.fingerprint
    research.refresh_fundamentals(store, FACTS_A, data_dir=members_dir)
    five = research.load_store(store, data_dir=members_dir)
    assert five.fingerprint != four.fingerprint
    assert five.price_fingerprint == four.price_fingerprint


def test_a_price_fingerprint_needs_all_four_price_files():
    files = {name: "0" * 64 for name in research.DATA_FILES if name != research.UNSERVED_FILE}
    with pytest.raises(ValueError, match="unserved.csv"):
        research.price_fingerprint_of(files)
```

**12b. `engine/tests/test_lab_store.py`** — imports: add `from decimal import Decimal` (after
`from datetime import date`) and `from seer_engine.lab import seed as seed_mod` (after
`from seer_engine.lab import store`). Append at end of file:
```python
# ---- trial_provenance (schema v5, trial-reproducibility phase 2) ------------------------------


def _provenance(n: int, **kw) -> store.ProvenanceRow:
    base = dict(trial_n=n, initial_idr=Decimal("10000000"), price_fingerprint="pf",
                source="recorded", measured="2026-10-09T00:00:00+00:00")
    base.update(kw)
    return store.ProvenanceRow(**base)


def test_provenance_round_trips_the_capital_exactly_and_is_append_only(conn):
    _method(conn)
    with conn:
        (n,) = store.insert_trials(conn, [_trial()])
        store.insert_provenance(conn, [_provenance(n, initial_idr=Decimal("2E+7"))])
    row = store.provenance_of(conn, n)
    assert row["initial_idr"] == "20000000"  # format(d, "f"): exponent notation never stored
    assert Decimal(row["initial_idr"]) == Decimal("20000000")
    assert row["price_fingerprint"] == "pf" and row["source"] == "recorded"
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE trial_provenance SET initial_idr = '1'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM trial_provenance")
    with pytest.raises(store.LabError, match="already has recorded provenance"):
        with conn:
            store.insert_provenance(conn, [_provenance(n)])


def test_provenance_refuses_what_a_rerun_could_not_use(conn):
    """A capital a run could not have started with, an unknown source, or the sentinel 0."""
    _method(conn)
    with conn:
        (n,) = store.insert_trials(conn, [_trial()])
    for bad, match in (
        (_provenance(0), "trial number"),
        (_provenance(n, initial_idr=Decimal("0")), "positive, finite"),
        (_provenance(n, initial_idr=Decimal("NaN")), "positive, finite"),
        (_provenance(n, initial_idr=10_000_000), "must be a Decimal"),
        (_provenance(n, source="guess"), "source"),
    ):
        with pytest.raises(store.LabError, match=match):
            with conn:
                store.insert_provenance(conn, [bad])
    assert store.provenance_of(conn, n) is None
    with conn:  # an unknown price fingerprint is recordable, and reads back as NULL
        store.insert_provenance(conn, [_provenance(n, price_fingerprint=None, source="backfill")])
    assert store.provenance_of(conn, n)["price_fingerprint"] is None


def test_seed_records_the_p7a_capital_and_price_fingerprint(conn):
    """The 58-trial cohort's 54 seed rows are marked, not rewritten (R4): 20M, the P7a prices."""
    seed(conn)
    rows = conn.execute("SELECT * FROM trial_provenance ORDER BY trial_n").fetchall()
    assert [r["trial_n"] for r in rows] == list(range(1, 55))
    assert {r["initial_idr"] for r in rows} == {"20000000"}
    assert {r["price_fingerprint"] for r in rows} == {seed_mod.P7A_FINGERPRINT}
    assert {r["source"] for r in rows} == {"backfill"}
    assert seed_mod.P7A_INITIAL_IDR == store.BACKFILL_LUMP_SUM_IDR
    assert seed_mod.P7A_FINGERPRINT == store.P7A_PRICE_FINGERPRINT
    assert store.BACKFILL_PRICE_FINGERPRINTS[seed_mod.P7A_FINGERPRINT] == store.P7A_PRICE_FINGERPRINT
```

**12c. `engine/tests/test_lab_snapshot.py`**
- `:116` — `assert store.schema_version(conn) == store.SCHEMA_VERSION == "4"` →
  `assert store.schema_version(conn) == store.SCHEMA_VERSION == "5"`, and add after the
  `trial_moments` count assertion (still inside the `try`):
```python
        assert conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type = 'table' AND name = 'trial_provenance'"
        ).fetchone()[0] == 1
```
- Insert after `test_connect_migrates_a_v3_database_adding_trial_funding_and_touching_no_trial`
  (after :287):
```python
def _without_provenance(schema: str) -> str:
    """``schema`` as it read at v4: the ``trial_provenance`` table and its triggers removed.

    Derived from ``store._SCHEMA`` exactly as ``_without_moments`` is, for the same reason.
    """
    for ddl in (store._PROVENANCE_TABLE, *store._PROVENANCE_TRIGGERS):
        assert f"{ddl};\n\n" in schema
        schema = schema.replace(f"{ddl};\n\n", "")
    assert "trial_provenance" not in schema
    return schema


V4_SCHEMA = _without_provenance(store._SCHEMA)
P7A = "5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a"
E597 = "e597367bb6806d7edc2f9af4033b26c366aae92517207b4e71daad96346fcca3"
D399 = "399d0d254c7a90b8cdb49f7ce598269087d38730f795cae90453eeb580b07cf8"
T568 = "56e83810e82ed59d0857f6851a638a96fc94fdbb8f781a3f4d56914dce8d141a"
TBBE = "bbe7abfb4a127127be48f177268a39346f94c718a672dcf5dc7ca900fa5ebc4b"
# One trial per (store, funded) case the committed lab holds, and what the backfill must give it.
V4_TRIALS = (
    # candidate, window, store_fingerprint, funded -> (initial_idr, price_fingerprint)
    ("M0001-1", "dev", P7A, False, ("20000000", P7A)),
    ("M0001-2", "dev", E597, False, ("20000000", P7A)),
    ("M0001-3", "dev", D399, True, ("10000000", P7A)),
    ("M0001-4", "test", T568, False, ("20000000", T568)),
    ("M0001-5", "test", TBBE, True, ("10000000", None)),
)


def _v4_db(path):
    """A schema-v4 database holding one trial for each store and funding case the lab has."""
    c = sqlite3.connect(path)
    c.executescript(V4_SCHEMA)
    c.executemany("INSERT INTO transitions (src, dst) VALUES (?, ?)", store.TRANSITIONS)
    c.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '4')")
    c.execute(
        "INSERT INTO methods (id, name, family, source_kind, hypothesis, status, created, updated) "
        "VALUES ('M0001', 'n', 'f', 'knowledge', 'h', 'rejected', '2026-10-01T00:00:00+00:00', "
        "'2026-10-01T00:00:00+00:00')"
    )
    for i, (cid, window, fp, funded, _want) in enumerate(V4_TRIALS, start=1):
        c.execute(
            'INSERT INTO trials (method_id, candidate_id, config_digest, config_text, rules_id, '
            'allocator_id, window, start, "end", store_fingerprint, git_sha, run_at, trades, '
            'sharpe, mar, failed, eligible, dsr, n_trials_at_run, curve_json) VALUES '
            "('M0001', ?, ?, 't', 'r', 'a', ?, '2000-01-03', '2015-10-16', ?, 'abc', "
            "'2026-10-05T00:00:00+00:00', 200, 0.945, 0.82, '', 0, 0.9, 110, '[]')",
            (cid, f"d{i}", window, fp),
        )
        if funded:
            c.execute(
                "INSERT INTO trial_funding (trial_n, mwr, spy_tr_mwr, deposits_usd, deposits_n, "
                "schedule, measured) VALUES (?, 0.07, 0.06, 3681.0, 12, "
                "'+5,000,000 IDR on the 25th of each month', '2026-10-08T00:00:00+00:00')",
                (i,),
            )
    c.commit()
    c.close()


def _provenance_schema(conn) -> list[tuple[str, str, str]]:
    return [tuple(r) for r in conn.execute(
        "SELECT type, name, sql FROM sqlite_master WHERE tbl_name = 'trial_provenance' "
        "ORDER BY type, name"
    )]


def test_connect_migrates_a_v4_database_backfilling_provenance_and_touching_no_trial(tmp_path):
    """Phase 2's exit criterion: v4 -> v5 annotates, it never rewrites.

    ``trials`` and ``trial_funding`` are byte-identical across the migration; every trial gains
    exactly one ``source='backfill'`` row by the rules the analysis measured (M1, M3) -- capital
    by the funding row, price fingerprint by the known-store map, NULL for a store never seen --
    and the table that arrives is as append-only as one a fresh database creates.
    """
    db = tmp_path / "lab.sqlite"
    _v4_db(db)
    before = _trials_bytes(db)
    funding_before = sqlite3.connect(db).execute("SELECT * FROM trial_funding ORDER BY trial_n").fetchall()

    conn = store.connect(db)
    fresh = store.connect(tmp_path / "fresh.sqlite")
    try:
        assert store.schema_version(conn) == store.SCHEMA_VERSION == "5"
        assert _trials_bytes(db) == before
        assert conn.execute("SELECT * FROM trial_funding ORDER BY trial_n").fetchall() == funding_before
        assert _provenance_schema(conn) == _provenance_schema(fresh)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        got = {
            int(r["trial_n"]): (r["initial_idr"], r["price_fingerprint"])
            for r in conn.execute("SELECT * FROM trial_provenance")
        }
        assert got == {i: want for i, (*_rest, want) in enumerate(V4_TRIALS, start=1)}
        assert {r[0] for r in conn.execute("SELECT source FROM trial_provenance")} == {"backfill"}
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("UPDATE trial_provenance SET initial_idr = '1'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM trial_provenance")
    finally:
        conn.close()
        fresh.close()

    again = store.connect(db)  # idempotent: a second connect backfills nothing
    try:
        assert store.schema_version(again) == store.SCHEMA_VERSION
        assert again.execute("SELECT count(*) FROM trial_provenance").fetchone()[0] == len(V4_TRIALS)
        assert _trials_bytes(db) == before
    finally:
        again.close()


@pytest.mark.skipif(not store.COMMITTED_DB.is_file(), reason="no committed lab database here")
def test_every_committed_trial_gets_exactly_one_provenance_row_by_the_rule(tmp_path):
    """On a copy of the committed lab (the original is never opened for writing): one row per
    trial, every backfilled row follows the stated rule, and every dev trial -- all three store
    fingerprints of them -- reads one price fingerprint, the P7a store's (analysis M1, M5 (c')).

    The last clause also covers dev trials recorded *after* the migration (``source='recorded'``).
    It holds because ``lab run`` refuses a dev store whose price fingerprint is not the
    benchmark's (phase 3, ``hardgate.pin_dev_store``); until phase 3 lands, the committed lab in
    this branch is still v4 and gains no trial (plan Invariant 3), so every row here is a backfill.
    """
    db = tmp_path / "lab.sqlite"
    shutil.copyfile(store.COMMITTED_DB, db)
    conn = store.connect(db)
    try:
        rows = conn.execute(
            "SELECT p.*, t.store_fingerprint, t.window, "
            "EXISTS (SELECT 1 FROM trial_funding f WHERE f.trial_n = t.n) AS funded "
            "FROM trials t JOIN trial_provenance p ON p.trial_n = t.n ORDER BY t.n"
        ).fetchall()
        n_trials = conn.execute("SELECT count(*) FROM trials").fetchone()[0]
        assert len(rows) == n_trials
        assert conn.execute("SELECT count(*) FROM trial_provenance").fetchone()[0] == n_trials
        for r in rows:
            if r["source"] == "backfill":
                assert r["initial_idr"] == ("10000000" if r["funded"] else "20000000"), r["trial_n"]
                assert r["price_fingerprint"] == store.BACKFILL_PRICE_FINGERPRINTS.get(
                    r["store_fingerprint"]
                ), r["trial_n"]
        dev_fps = {r["price_fingerprint"] for r in rows if r["window"] == "dev"}
        assert dev_fps == {store.P7A_PRICE_FINGERPRINT}
    finally:
        conn.close()
```
(`shutil` and `sqlite3` are already imported in this file.)

**12d. `engine/tests/test_lab_runner.py`** — imports: add `from decimal import Decimal` and
`from seer_engine.backtest.runner import INITIAL_IDR`. Append:
```python
# ---- trial-reproducibility phase 2: the capital and the price data are recorded -----------------


def test_a_run_records_the_capital_it_was_given_and_the_store_s_price_fingerprint(conn, data, monkeypatch):
    """The provenance row names the capital `run_registry` was actually handed, not a constant
    read separately, so the two cannot disagree; and every trial gets one."""
    seen: list = []
    real = dev_module.run_registry

    def spy(*a, **k):
        seen.append(k.get("initial_idr"))
        return real(*a, **k)

    monkeypatch.setattr(runner.dev, "run_registry", spy)
    runner.run_method(conn, _method(), Path(__file__), data, git_sha="x", require_commit=False)
    assert seen == [INITIAL_IDR]
    for r in store.trials_of(conn, "M0001"):
        p = store.provenance_of(conn, r["n"])
        assert p is not None and p["source"] == "recorded"
        assert Decimal(p["initial_idr"]) == INITIAL_IDR
        assert p["price_fingerprint"] == data.price_fingerprint == "smoke"
        assert p["measured"] == r["run_at"]  # one measurement, one stamp
        assert runner.recorded_capital(conn, r["n"]) == INITIAL_IDR
    # and the seed's 54 still read the 20M they ran on, whatever the live constant is
    assert {runner.recorded_capital(conn, n) for n in range(1, 55)} == {Decimal("20000000")}


def test_recorded_capital_refuses_a_trial_whose_capital_was_never_recorded(conn, data, monkeypatch):
    """No row is a refusal, never a silent fall-back to the live INITIAL_IDR."""
    monkeypatch.setattr(store, "insert_provenance", lambda conn, rows: None)
    runner.run_method(conn, _method(), Path(__file__), data, git_sha="x", require_commit=False)
    monkeypatch.undo()
    n = int(store.trials_of(conn, "M0001")[0]["n"])
    with pytest.raises(store.LabError, match="no recorded starting capital"):
        runner.recorded_capital(conn, n)
```

**12e. `engine/tests/test_lab_test_window.py`**
- Imports: add `from seer_engine.backtest.runner import INITIAL_IDR`.
- `:347-352` — `fake_run_registry` becomes
```python
    def fake_run_registry(market, dividends, spy_dividends, registry, *,
                          on_result=None, window=None, contributions=None, initial_idr=None):
        assert window.name == "test" and tuple(registry) == (c,)
        assert contributions is OWNER_MONTHLY  # the look is funded like the owner's account
        assert initial_idr == INITIAL_IDR  # and starts at the capital its provenance records
        on_result(0, SimpleNamespace(snapshots=snaps, cashflows=CASHFLOWS), row)
        return (row,)
```
- In `test_the_look_is_recorded_and_does_not_move_the_lab_s_n` (:242), after
  `assert row["n_trials_at_run"] == before_n` add:
```python
    prov = store.provenance_of(conn, row["n"])
    assert prov["source"] == "recorded" and prov["measured"] == row["run_at"]
    assert Decimal(prov["initial_idr"]) == INITIAL_IDR
    assert prov["price_fingerprint"] == "smoke-test"
```
  (`Decimal` is already imported in this file.)

**12f. `engine/tests/test_lab_remeasure.py`** — imports: add `from decimal import Decimal`, and
extend the existing `from labkit import smoke_data, smoke_test_data` (:16) to
`from labkit import smoke_data, smoke_test_data, stamp_provenance`.
Append:
```python
# ---- trial-reproducibility phase 2: the re-run is given the recorded capital ----------------


def _without_provenance_run(conn, data, m, monkeypatch):
    """`lab run` with the provenance write suppressed, so a test can record the capital itself."""
    monkeypatch.setattr(store, "insert_provenance", lambda conn, rows: None)
    _run(conn, data, m)
    monkeypatch.undo()
    return [int(r["n"]) for r in store.trials_of(conn, m.id)]


def test_the_rerun_is_given_the_recorded_capital_not_the_live_constant(conn, data, no_moments):
    """Analysis M2: M0011 and M0007 ran at 20M and reproduce only there. Whatever the live
    INITIAL_IDR reads, `measure` hands `run_registry` the capital the trials recorded."""
    m = _method()
    ns = _without_provenance_run(conn, data, m, no_moments)
    with conn:
        stamp_provenance(conn, ns, price_fingerprint="smoke", initial_idr=Decimal("20000000"))
    plan = remeasure.preflight(conn, m, HERE, require_commit=False)
    assert plan.initial_idr == Decimal("20000000")

    class Stop(Exception):
        pass

    seen: list = []

    def spy(*a, **k):
        seen.append(k.get("initial_idr"))
        raise Stop

    no_moments.setattr(remeasure.dev, "run_registry", spy)
    with pytest.raises(Stop):
        remeasure.measure(conn, m, plan, data)
    assert seen == [Decimal("20000000")]
    assert all(store.moments_of(conn, n) is None for n in ns)


def test_trials_recorded_at_two_capitals_are_refused_before_any_store_is_loaded(conn, data, no_moments):
    m = _method()
    ns = _without_provenance_run(conn, data, m, no_moments)
    assert len(ns) == 2  # `_method()` records two variants
    with conn:
        stamp_provenance(conn, ns[:1], price_fingerprint="smoke", initial_idr=Decimal("10000000"))
        stamp_provenance(conn, ns[1:], price_fingerprint="smoke", initial_idr=Decimal("20000000"))
    with pytest.raises(store.LabError, match="different starting capitals"):
        remeasure.preflight(conn, m, HERE, require_commit=False)


def test_a_trial_with_no_recorded_capital_is_refused_before_any_store_is_loaded(conn, data, no_moments):
    m = _method()
    _without_provenance_run(conn, data, m, no_moments)
    with pytest.raises(store.LabError, match="no recorded starting capital"):
        remeasure.preflight(conn, m, HERE, require_commit=False)
```
(`no_moments` is the fixture's `monkeypatch`; `.undo()` inside the helper also lifts the
`insert_moments` suppression, which these tests do not need — they write no moments.)

**12g. `engine/tests/test_lab_remeasure_seed.py`**
- Imports: add `from decimal import Decimal` and `from labkit import stamp_provenance`
  (`from seer_engine.lab import seed as seed_mod` is **not** needed); use
  `from seer_engine.lab.seed import P7A_FINGERPRINT, seed` in place of the existing
  `from seer_engine.lab.seed import seed`.
- `perfect()`'s inner function (:53): `def run_chunk(data, candidates):` →
```python
    def run_chunk(data, candidates, *, initial_idr):
        # Every seed trial ran at 20M (its provenance row); a chunk handed anything else is
        # the failure analysis M4 measured, so the double refuses to "reproduce" it.
        assert initial_idr == Decimal("20000000"), initial_idr
```
  followed by the existing body (`out = {}` …) unchanged.
- `test_no_window_can_be_selected_anywhere_in_the_seed_path` (:432-434): replace the last two
  lines with
```python
    real_run_chunk(FakeData(), [], initial_idr=Decimal("20000000"))
    assert calls and all("window" not in k for k in calls)
    assert all(k["initial_idr"] == Decimal("20000000") for k in calls)
```
- Append:
```python
# ---- trial-reproducibility phase 2: one recorded capital per chunk ----------------------------


def _seeded_without_provenance(path, monkeypatch):
    monkeypatch.setattr(store, "insert_provenance", lambda conn, rows: None)
    c = store.connect(path)
    seed(c)
    monkeypatch.undo()
    return c


def test_seed_trials_recorded_at_two_capitals_are_refused_before_any_store_is_loaded(tmp_path, monkeypatch):
    """One `run_registry` call runs one capital, so a mixed to-do set has no faithful re-run --
    and it is refused by `seed_preflight`, from the database alone, as the dev path's
    `preflight` refuses its own (phase 1's handoff: `run_registry` takes one capital per call)."""
    c = _seeded_without_provenance(tmp_path / "mixed.sqlite", monkeypatch)
    try:
        with c:
            stamp_provenance(c, range(1, 54), price_fingerprint=P7A_FINGERPRINT,
                             initial_idr=Decimal("20000000"))
            stamp_provenance(c, [54], price_fingerprint=P7A_FINGERPRINT,
                             initial_idr=Decimal("10000000"))
        with pytest.raises(store.LabError, match="different starting capitals"):
            _plan(c)
        assert c.execute("SELECT count(*) FROM trial_moments").fetchone()[0] == 0
    finally:
        c.close()


def test_a_seed_trial_with_no_recorded_capital_is_refused_before_any_store_is_loaded(tmp_path, monkeypatch):
    c = _seeded_without_provenance(tmp_path / "bare.sqlite", monkeypatch)
    try:
        with pytest.raises(store.LabError, match="no recorded starting capital"):
            _plan(c)
    finally:
        c.close()
```

**12h. `engine/tests/test_lab_hardgate.py`** — imports: the block at :9-18 becomes
```python
import argparse
import json
from datetime import date, timedelta
from decimal import Decimal
from math import comb

import pytest

from labkit import stamp_provenance
from seer_engine.backtest import regime
from seer_engine.lab import hardgate, store
from seer_engine.lab import walkforward as wf
```
(two lines added, so everything below shifts by +2: `_benchmark` / `_method` sit at :81-112).
No local stamping helper is added — the file uses `labkit.stamp_provenance` (Step 11), which is
idempotent, so phase 3's `_benchmark` / `_method` stamping every trial they insert and these
calls never collide.
- `test_a_funded_trial_is_de_funded_before_it_is_scored` (:311): after the `with conn:
  store.insert_funding(...)` block add
  ```python
      with conn:
          stamp_provenance(conn, [int(row["n"])])  # 10M: the 0.5-per-deposit unit asserted below
  ```
  Update its docstring's "The reconstruction credits ``amount_idr / INITIAL_IDR``" → "The
  reconstruction credits ``amount_idr / <recorded capital>``".
- `test_a_moved_contribution_schedule_refuses_rather_than_guesses` (:350): after its
  `insert_funding` block add the same two lines (so the refusal asserted is the deposit-count
  one, not the missing-capital one).
- Insert after that test (before the `# ---- what the gate judges` banner):
```python
def _funded_trial(conn, mid: str, *, capital: str | None):
    """A funded dev trial built directly (not through ``_method``), recorded at ``capital``."""
    from seer_engine.sim.contributions import OWNER_MONTHLY

    due = OWNER_MONTHLY.dates_in(date(1996, 1, 2), date(2015, 10, 16))
    with conn:
        store.add_method(conn, id=mid, name=f"n{mid}", family="trend", source_kind="knowledge",
                         hypothesis="h", status="registered")
        (n,) = store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-A", config_digest=f"d-{mid}",
            curve_json=_curve(_months(*DEV_SPAN), 0.15),
        )])
        store.insert_funding(conn, [store.FundingRow(
            trial_n=n, mwr=0.11, spy_tr_mwr=0.08, deposits_usd=1.0, deposits_n=len(due),
            schedule="+5,000,000 IDR on the 25th of each month", measured="test",
        )])
        if capital is not None:
            stamp_provenance(conn, [n], initial_idr=Decimal(capital))
    row = conn.execute(
        'SELECT n, candidate_id, start, "end", curve_json FROM trials WHERE n = ?', (n,)
    ).fetchone()
    curve = [(date.fromisoformat(d), float(v)) for d, v in json.loads(row["curve_json"])]
    return row, curve, due


def test_a_deposit_is_measured_against_the_capital_the_trial_ran_on(conn):
    """Recorded at 20M, each 5M deposit is 0.25 of the opening balance, not the 0.5 the live
    INITIAL_IDR would say. The day the constant moves again, nothing recorded re-scales."""
    row, curve, due = _funded_trial(conn, "M0002", capital="20000000")
    deposits = hardgate.trial_deposits(conn, row, curve)
    assert len(deposits) == len(due) - 1
    assert set(deposits.values()) == {0.25}


def test_a_funded_trial_with_no_recorded_capital_is_refused_not_guessed(conn):
    row, curve, _due = _funded_trial(conn, "M0003", capital=None)
    with pytest.raises(store.LabError, match="no recorded starting capital"):
        hardgate.trial_deposits(conn, row, curve)
```

**12i. `engine/tests/test_lab_costs.py`**
- `:94-97` and `:153-156`: both `real_costs.measure(...)` calls gain
  `initial_idr=runner.recorded_capital(conn, int(trial["n"])),` after the `contributions=` line.
- Append after `test_measure_refuses_a_test_window_store`:
```python
def test_measure_runs_both_sides_at_the_capital_it_is_given(lab, data, recorded, monkeypatch):
    """Analysis M2: trial #90 reads +660.2% at its recorded 20M and +545.3% at the live 10M.
    The capital passed in is the one both fee models run at."""
    conn, _ = lab
    c, trial = real_costs.pick_candidate(conn, recorded, None)
    seen: list = []
    real = real_costs.dev.run_registry

    def spy(*a, **k):
        seen.append(k.get("initial_idr"))
        return real(*a, **k)

    monkeypatch.setattr(real_costs.dev, "run_registry", spy)
    real_costs.measure(
        recorded, c, trial, data,
        contributions=runner.recorded_contributions(conn, int(trial["n"])),
        initial_idr=Decimal("20000000"),
    )
    assert seen == [Decimal("20000000")]


def test_cli_refuses_a_trial_with_no_recorded_capital_before_any_store(tmp_path, monkeypatch):
    """`lab costs` resolves the recorded capital before the store loads; none is exit 2."""
    path = tmp_path / "lab.sqlite"
    c = store.connect(path)
    seed(c)
    m = _method()
    monkeypatch.setattr(store, "insert_provenance", lambda conn, rows: None)
    runner.run_method(c, m, HERE, smoke_data(), git_sha="x", require_commit=False)
    monkeypatch.undo()
    c.close()

    def boom(*a, **k):
        raise AssertionError("the store must not be loaded for a refusal")

    monkeypatch.setattr(research, "load_store", boom)
    monkeypatch.setattr(real_costs, "discover", lambda: {"M0001": (m, HERE)})
    assert cli.main(["lab", "--db", str(path), "costs", "M0001", "--store", str(tmp_path)]) == 2
```
  Note: `seed` is patched-around: `seed(c)` runs before the `insert_provenance` patch, so the 54
  seed rows exist; only M0001's trials lack a row.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/trial-reproducibility/engine && PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -c "import seer_engine.lab.store, seer_engine.lab.runner, seer_engine.lab.remeasure, seer_engine.lab.real_costs, seer_engine.lab.hardgate, seer_engine.lab.seed, seer_engine.commands.lab"`

**Tests (targeted, then full):**
```
cd /home/miftah/.worktrees/seer/trial-reproducibility/engine
PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -m pytest -q \
  tests/test_research_store.py tests/test_lab_store.py tests/test_lab_snapshot.py \
  tests/test_lab_runner.py tests/test_lab_test_window.py tests/test_lab_remeasure.py \
  tests/test_lab_remeasure_seed.py tests/test_lab_hardgate.py tests/test_lab_costs.py \
  tests/test_lab_status.py tests/test_lab_walkforward.py tests/test_lab_gate_policy.py
PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -m pytest -q
```
(`test_lab_snapshot.py`'s committed-snapshot guard must still pass: phase 2 does not touch
`lab/lab.sqlite` or `web/data/lab.json`, and `snapshot` reads no provenance.)

**Manual check — on a scratch COPY of the committed database (never the original; `lab` migrates
on connect):**
```
SCRATCH="$(mktemp -d)"
cp /home/miftah/.worktrees/seer/trial-reproducibility/lab/lab.sqlite "$SCRATCH/lab.sqlite"
cd /home/miftah/.worktrees/seer/trial-reproducibility/engine
PY="env PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python"
STORE=/home/miftah/seer/engine/.research

# 1. migration: 152 provenance rows, one per trial, by the rule
$PY -c "
import sys; from seer_engine.lab import store
c = store.connect(sys.argv[1])
print(store.schema_version(c),
      c.execute('select count(*) from trials').fetchone()[0],
      c.execute('select count(*) from trial_provenance').fetchone()[0])
print(c.execute('select initial_idr, price_fingerprint, source, count(*) from trial_provenance group by 1,2,3').fetchall())
" "$SCRATCH/lab.sqlite"
# expect: 5 152 152; groups: (10000000, 5451195f…, backfill, 22), (10000000, None, backfill, 2),
#         (20000000, 5451195f…, backfill, 126), (20000000, 56e83810…, backfill, 2)

# 2. the three re-runs reproduce at today's INITIAL_IDR (10M), unchanged
$PY -c "from seer_engine.backtest.runner import INITIAL_IDR; print(INITIAL_IDR)"   # 10000000
$PY -m seer_engine lab --db "$SCRATCH/lab.sqlite" remeasure M0011 --store "$STORE"; echo "exit $?"
$PY -m seer_engine lab --db "$SCRATCH/lab.sqlite" remeasure M0007 --store "$STORE"; echo "exit $?"
$PY -m seer_engine lab --db "$SCRATCH/lab.sqlite" remeasure H-P7A --store "$STORE"; echo "exit $?"

# 3. optional, phase 4 repeats it: lab costs M0011's flat column reads trial #90's +660.2%
cp /home/miftah/.worktrees/seer/trial-reproducibility/lab/lab.sqlite "$SCRATCH/costs.sqlite"
$PY -m seer_engine lab --db "$SCRATCH/costs.sqlite" costs M0011 --candidate M0011-RAW20-TV14-N21 --store "$STORE"

# 4. the committed database was not touched
cd /home/miftah/.worktrees/seer/trial-reproducibility && git status --short lab/ web/data/
```
Expected group counts in (1), measured on the committed database at `e5eda52`: 24 funded trials
(22 dev on `399d0d25…` → 10M at `5451195f…`; 2 test on `bbe7abfb…` → 10M, NULL) and 128 lump
(58 dev on `5451195f…` + 6 on `e597367b…` + 62 on `399d0d25…` → 126 dev at 20M, `5451195f…`;
2 test on `56e83810…` → 20M, itself). If the counts differ, the M3 rule or the map is wrong — stop.

**Exit criteria:**
- On a scratch copy migrated to v5: exactly 152 `trial_provenance` rows, one per trial, all
  `backfill`, every dev trial at price fingerprint `5451195f…`.
- On that copy, with `backtest.runner.INITIAL_IDR == Decimal("10000000")` unchanged:
  `lab remeasure M0011`, `lab remeasure M0007` and `lab remeasure H-P7A` each exit 0 (H-P7A:
  54 written, 0 blocked).
- Full engine suite green.
- `git status` shows no change to `lab/lab.sqlite` or `web/data/lab.json`.

## Handoffs

- **Phase 3 (comparability), test fixtures.** `labkit.smoke_data().price_fingerprint == "smoke"`
  and `smoke_test_data().price_fingerprint == "smoke-test"`, while a seeded lab's benchmark
  (`REF-SPY-HOLD`, trial #1) records `P7A_PRICE_FINGERPRINT`. Phase 3's `_run` store pin would
  refuse smoke data against a seeded lab in a CLI-level `lab run` test. Reconciled: no existing
  test drives `commands/lab.py:_run` (grep at `e5eda52`), and phase 3's own `_run` tests stub
  `research.load_store` with an explicit price fingerprint; `runner.run_method` itself is not
  pinned, so runner-level tests are unaffected.
- **Phase 3, `test_lab_hardgate.py` / `test_lab_prereg.py` / `test_lab_status.py`.** Phase 3
  stamps its gate fixtures with `labkit.stamp_provenance` (Step 11 here) and creates no helper of
  its own. Its defaults — capital `Decimal("10000000")`, price fingerprint
  `LAB_PRICE_FINGERPRINT` — keep the funded tests' 0.5-per-deposit assertions true; the explicit
  `stamp_provenance` calls this phase adds to the two funded tests become no-ops once phase 3's
  `_method` stamps first (idempotent by design).
- **Phase 3, `hardgate`.** Consume `store.provenance_of(conn, n)["price_fingerprint"]` (None or
  missing row = unknown → refuse) and `ResearchData.price_fingerprint`. This phase does not read
  either in any comparison.
- **Phase 4 (docs, lab insight, `lab stage`).** `lab stage` on the committed DB runs the v4→v5
  migration and its backfill; expect the group counts in Verification step 1. The test
  `test_every_committed_trial_gets_exactly_one_provenance_row_by_the_rule` passes before and
  after staging. Docs to mention: `trial_provenance`, `price_fingerprint_of`, the M3 rule.
- **Drive-by, not taken (no phase owns it):** `engine/src/seer_engine/paper/capital.py:9`
  still says "The backtests keep ``backtest.runner.INITIAL_IDR`` (20,000,000 IDR …)" — false since
  `d79fc83`. Reconciler: left out of the set. It is a source comment in `paper/`, no requirement
  or impact point names it, and phase 4 edits no source file; it belongs on its own card.
- **Out of scope by the plan index:** writing any recovered `trial_moments` row to the committed
  database (M6). The exit-criteria re-runs write moments to the scratch copy only.

## Rollback

Revert this phase's commit. No committed database is migrated by this phase, so nothing persists
outside the code: `lab/lab.sqlite` stays at schema 4. A scratch copy migrated to v5 during
verification is refused by reverted code (`schema version '5' is unknown`) — delete the copy.
If phase 4 has already staged a v5 database, this phase cannot be reverted alone; revert phase 4
first (its rollback restores the v4 file byte for byte).
