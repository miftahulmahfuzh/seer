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
from seer_engine.backtest import dev, tuning
from seer_engine.lab import seed as seed_mod
from seer_engine.lab import store
from seer_engine.lab.seed import seed

def _without_moments(schema: str) -> str:
    """``schema`` as it read at v2: the ``trial_moments`` table and its triggers removed.

    Derived from ``store._SCHEMA`` rather than pasted, so a v2 fixture cannot drift away from the
    real schema. The assertions below fail loudly if the statements stop being laid out one per
    paragraph, which is what makes the strip exact.
    """
    for ddl in (store._MOMENTS_TABLE, *store._MOMENTS_TRIGGERS):
        assert f"{ddl};\n\n" in schema
        schema = schema.replace(f"{ddl};\n\n", "")
    assert "trial_moments" not in schema
    return schema


V2_SCHEMA = _without_moments(store._SCHEMA)
V1_SCHEMA = V2_SCHEMA.replace(", 'synthesis'", "")
V1_INSIGHTS = [
    (1, "observation", "Vol scaling buys drawdown", "It costs CAGR.", "M0001", "2026-10-02T00:00:00+00:00"),
    (2, "data-wish", "Delisted stocks", "Survivorship.", None, "2026-10-02T00:00:01+00:00"),
    (3, "risk", "The 15% bar", "2008 is in the window.", None, "2026-10-02T00:00:02+00:00"),
]
# The recorded labels this fixture lab wrote (the bars of its own run date) and the live ones a
# verdict is written in today. `failed` draws from the first set, `failedNow` from the second.
LABELS = {"beats SPY TR", "max DD <= 15%", "PF >= 1.3", ">= 100 trades", "owner inputs", "DSR >= 0.95"}
LIVE_LABELS = set(dev.FAILURE_LABELS) | {store.DSR_LABEL}
METHOD_KEYS = {"id", "name", "family", "parentId", "sourceKind", "sourceRef", "hypothesis", "expectedFailure",
               "status", "analysis", "verdict", "blockedOn", "created", "updated", "historical"}
TRIAL_KEYS = {"n", "methodId", "candidateId", "rulesId", "allocatorId", "configText", "window", "start", "end",
              "gitSha", "runAt", "totalReturn", "cagr", "maxDrawdown", "profitFactor", "pfInfinite", "trades",
              "sharpe", "exposure", "turnover", "worstYear", "worstYearReturn", "spyTrReturn", "spyTrCagr", "mar",
              "failed", "eligible", "dsr", "nTrialsAtRun", "failedNow", "eligibleNow", "dsrNow", "curve"}


def _v1_db(path):
    """A schema-v1 database as the first lab wrote it: one method, three insights (ids 1-3)."""
    assert V1_SCHEMA != V2_SCHEMA != store._SCHEMA
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
        assert store.schema_version(conn) == "3"
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
        assert store.schema_version(again) == "3"
        assert again.execute("SELECT count(*) FROM insights").fetchone()[0] == 4
    finally:
        again.close()


def test_a_new_database_starts_at_the_current_schema_version(tmp_path):
    conn = store.connect(tmp_path / "lab.sqlite")
    try:
        assert store.schema_version(conn) == store.SCHEMA_VERSION == "3"
        assert "synthesis" in store.INSIGHT_KINDS
        with conn:
            assert store.add_insight(conn, kind="synthesis", title="t", body="b") == 1
        assert conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type = 'table' AND name = 'trial_moments'"
        ).fetchone()[0] == 1
    finally:
        conn.close()


def _v2_db(path):
    """A schema-v2 database with one method and two recorded dev trials, one of them eligible."""
    assert V2_SCHEMA != store._SCHEMA
    c = sqlite3.connect(path)
    c.executescript(V2_SCHEMA)
    c.executemany("INSERT INTO transitions (src, dst) VALUES (?, ?)", store.TRANSITIONS)
    c.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '2')")
    c.execute(
        "INSERT INTO methods (id, name, family, source_kind, hypothesis, status, created, updated) "
        "VALUES ('M0001', 'n', 'f', 'knowledge', 'h', 'rejected', '2026-10-01T00:00:00+00:00', "
        "'2026-10-01T00:00:00+00:00')"
    )
    v2_trials = (("d1", 0.916, "DSR >= 0.95", 0), ("d2", 0.978, "", 1))
    for i, (digest, dsr, failed, elig) in enumerate(v2_trials, start=1):
        c.execute(
            'INSERT INTO trials (method_id, candidate_id, config_digest, config_text, rules_id, '
            'allocator_id, window, start, "end", store_fingerprint, git_sha, run_at, trades, '
            'sharpe, mar, failed, eligible, dsr, n_trials_at_run, curve_json) VALUES '
            "('M0001', ?, ?, 't', 'r', 'a', 'dev', '2000-01-03', '2015-10-16', 'fp', 'abc', "
            "'2026-10-05T00:00:00+00:00', 200, 0.945, 0.82, ?, ?, ?, 110, '[]')",
            (f"M0001-{i}", digest, failed, elig, dsr),
        )
    c.commit()
    c.close()


def _trials_bytes(path) -> bytes:
    """Every ``trials`` row, in order, as one blob -- the thing a migration must not move."""
    c = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        return repr(c.execute("SELECT * FROM trials ORDER BY n").fetchall()).encode("utf-8")
    finally:
        c.close()


def _moments_schema(conn) -> list[tuple[str, str, str]]:
    return [tuple(r) for r in conn.execute(
        "SELECT type, name, sql FROM sqlite_master WHERE tbl_name = 'trial_moments' ORDER BY type, name"
    )]


def test_connect_migrates_a_v2_database_adding_trial_moments_and_touching_no_trial(tmp_path):
    """Phase 2's exit criterion: v2 -> v3 is purely additive.

    The ``trials`` table is byte-identical across the migration -- same rows, same order, same
    ``dsr``, ``failed``, ``eligible`` and ``n_trials_at_run`` -- and the new table arrives empty
    with the same definition a fresh v3 database gets.
    """
    db = tmp_path / "lab.sqlite"
    _v2_db(db)
    before = _trials_bytes(db)
    assert hashlib.sha256(before).hexdigest()  # the checksum a reviewer compares

    conn = store.connect(db)
    fresh = store.connect(tmp_path / "fresh.sqlite")
    try:
        assert store.schema_version(conn) == "3"
        assert _trials_bytes(db) == before  # no verdict moved
        assert conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0] == 0
        assert _moments_schema(conn) == _moments_schema(fresh)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []

        # The two triggers are row-level (``BEFORE UPDATE``/``BEFORE DELETE`` fire per row), so on
        # the empty table just migrated in they would never fire and asserting against it would
        # pass vacuously. Give the migrated table a row and prove they bite on *it* -- the point
        # being that a table arriving by migration is as append-only as one created by _SCHEMA.
        with conn:
            store.insert_moments(conn, [store.MomentsRow(
                trial_n=1, sr_daily=0.0501, t=3959, skew=-0.31, kurt=7.2,
                var_trials=2.395e-04, n_at_run=110, measured="2026-10-07T00:00:00+00:00",
            )])
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("UPDATE trial_moments SET t = 9")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM trial_moments")
        assert store.moments_of(conn, 1)["t"] == 3959
        assert _trials_bytes(db) == before  # and recording moments still moved no trial
    finally:
        conn.close()
        fresh.close()

    again = store.connect(db)  # idempotent: a second connect migrates nothing
    try:
        assert store.schema_version(again) == "3"
        assert _trials_bytes(db) == before
    finally:
        again.close()


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
        assert store.schema_version(ro) == "3"
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
                       "insights", "ideasSeen", "paper"]
    assert s["version"] == 3
    gate = s["gate"]
    assert list(gate) == [
        "maxDrawdown", "minProfitFactor", "minTrades", "dsrMin",
        "dsrPolicy", "dsrN", "dsrNBasis", "devStart", "devEnd", "testStart",
    ]
    assert {k: gate[k] for k in ("minProfitFactor", "minTrades",
                                 "devStart", "devEnd", "testStart")} == {
        "minProfitFactor": 1.3, "minTrades": 100,
        "devStart": "1993-01-29", "devEnd": "2015-10-16", "testStart": "2015-10-19"}
    # BOTH bars are the owner's dials and BOTH moved on 2026-10-07 (design §7.1 and §1 item 4):
    # published from the constants, never pinned here. A test that hardcodes an owner-set number
    # turns the next adjustment into a test failure for no benefit -- which is what happened to
    # the six files this phase is fixing.
    assert gate["dsrMin"] == store.DSR_MIN
    assert gate["maxDrawdown"] == tuning.MAX_DRAWDOWN
    # The N is resolved from the policy at export time, not stored: assert the contract the web
    # reads (a known policy, a usable integer, one line of evidence), not phase 1's arithmetic.
    assert gate["dsrPolicy"] == store.DSR_POLICY
    assert isinstance(gate["dsrN"], int) and gate["dsrN"] >= 0
    assert isinstance(gate["dsrNBasis"], str) and gate["dsrNBasis"]
    assert "\n" not in gate["dsrNBasis"]  # it is a one-line field in a committed prereg file too
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
        # The verdict is written in today's labels, whatever the row recorded, and it is a
        # verdict rather than a copy: `eligibleNow` follows `failedNow`, never `eligible`.
        assert set(t["failedNow"]) <= LIVE_LABELS
        assert t["eligibleNow"] == (not t["failedNow"])
        assert all(isinstance(p[0], str) and isinstance(p[1], float) for p in t["curve"])
    t55 = s["trials"][-1]
    assert t55["profitFactor"] is None and t55["pfInfinite"] is True
    assert t55["cagr"] == 0.123457 and t55["dsr"] == 0.412346
    assert t55["failed"] == ["beats SPY TR", "DSR >= 0.95"] and t55["eligible"] is False
    # The same row read against the bars in force now. Nothing is copied: the four threshold
    # conditions are re-derived from this row's own columns, so the recorded `beats SPY TR` drops
    # (total_return 1.0 > spy_tr_return 0.5) and only the luck label survives -- in today's
    # spelling, 0.90, not the 0.95 the row still records.
    assert t55["failedNow"] == [store.DSR_LABEL] and t55["eligibleNow"] is False
    row = lab.execute("SELECT * FROM trials WHERE n = 55").fetchone()
    assert t55["dsrNow"] == store._num(store.published_verdict(lab, row).dsr)
    assert t55["curve"] == [["2000-01-31", 1.0], ["2000-02-29", 1.012346]]
    assert not any(t["pfInfinite"] for t in s["trials"][:54])

    assert [(i["id"], i["kind"], i["methodId"]) for i in s["insights"]] == [(1, "observation", "M0001"), (2, "synthesis", None)]
    keys = [x["key"] for x in s["ideasSeen"]]
    assert keys == sorted(keys) and "url:https://example.com/paper" in keys
    assert set(s["ideasSeen"][0]) == {"key", "methodId", "note", "added"}

    stamps = ([m["updated"] for m in s["methods"]] + [t["runAt"] for t in s["trials"]]
              + [i["added"] for i in s["insights"]] + [x["added"] for x in s["ideasSeen"]])
    assert s["asOf"] == max(stamps)


def test_the_paper_block_is_the_rosters_provenance_verbatim(lab):
    """``paper`` is the only block that is not a read of the lab database.

    It exists so the web can answer "which method is this roster entry?", which nothing else in
    the snapshot can: ``rules_id`` is shared by a dozen methods. Asserted against
    ``LAB_PROVENANCE`` itself rather than against a copied list of ids, so promoting a strategy
    does not break this test -- the roster is the source and this only checks it arrives whole.
    """
    from seer_engine.paper import roster

    paper = store.snapshot(lab)["paper"]
    assert [p["strategyId"] for p in paper] == sorted(roster.LAB_PROVENANCE)
    for p in paper:
        assert set(p) == {"strategyId", "methodId", "candidateId", "labStatus", "basis"}
        prov = roster.LAB_PROVENANCE[p["strategyId"]]
        assert (p["methodId"], p["candidateId"], p["labStatus"], p["basis"]) == (
            prov.method_id, prov.candidate_id, prov.lab_status, prov.basis)
        # The variant is NOT required to be named after its method: the historical entries carry
        # their own ids (`F1-SPY-SMA200-M` under `H-P7A-F1`). Only `methodId` ever builds an href,
        # and that those ids reach a real method is asserted on the committed lab, not on this
        # fixture, which holds one method.
    # `reason` is deliberately not published: the roster's prose stays on the roster.
    assert all("reason" not in p for p in paper)
    # Entries the lab never produced (C, SPY) have no row, and the web must find none for them.
    assert {"SPY", "C"}.isdisjoint({p["strategyId"] for p in paper})


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
    # Every roster entry's `methodId` reaches a method this snapshot publishes. The leaderboard
    # turns that id into `/sera/methods/<id>` with nothing else to check against, so a provenance
    # row naming a method the lab does not hold is a 404 on a live page -- caught here, on the
    # real lab, rather than by a reader clicking it.
    snap = json.loads(committed)
    ids = {m["id"] for m in snap["methods"]}
    missing = sorted({p["methodId"] for p in snap["paper"]} - ids)
    assert not missing, f"paper provenance names methods the lab does not have: {missing}"
