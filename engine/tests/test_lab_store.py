"""The lab database's rules (method lab design §1): append-only trials, forward-only status,
growing analysis, one test look per configuration, the seed import and the export."""

from __future__ import annotations

import sqlite3
from dataclasses import replace

import pytest

from seer_engine.backtest.registry import REGISTRY
from seer_engine.lab import store
from seer_engine.lab.method import config_digest
from seer_engine.lab.seed import seed


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    yield c
    c.close()


def _method(conn, mid="M0001", status="idea"):
    with conn:
        store.add_method(conn, id=mid, name="n", family="f", source_kind="knowledge", hypothesis="h", status=status)


def _trial(**kw) -> store.TrialRow:
    base = dict(
        method_id="M0001", candidate_id="M0001-A", config_digest="d1", config_text="t", rules_id="r",
        allocator_id="a", window="dev", start="2000-01-03", end="2015-10-16", store_fingerprint="fp",
        git_sha="abc", run_at="2026-10-04T00:00:00+00:00", total_return=1.0, cagr=0.1, max_drawdown=0.2,
        profit_factor=1.5, trades=200, sharpe=0.8, exposure=0.9, turnover=1.0, worst_year=2008,
        worst_year_return=-0.2, spy_tr_return=0.5, spy_tr_cagr=0.07, mar=0.5, failed="max DD <= 15%",
        eligible=False, dsr=0.5, n_trials_at_run=55, curve_json="[]",
    )
    base.update(kw)
    return store.TrialRow(**base)


def test_trials_are_append_only(conn):
    _method(conn)
    with conn:
        store.insert_trials(conn, [_trial()])
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE trials SET mar = 9")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM trials")
    with pytest.raises(sqlite3.IntegrityError, match="never deleted"):
        conn.execute("DELETE FROM methods")


def test_a_configuration_runs_once_per_window(conn):
    _method(conn)
    with conn:
        store.insert_trials(conn, [_trial()])
    with pytest.raises(store.LabError, match="already has a dev trial"):
        store.insert_trials(conn, [_trial(candidate_id="M0001-B")])
    with conn:
        store.insert_trials(conn, [_trial(window="test")])
    with pytest.raises(store.LabError, match="already has a test trial"):
        store.insert_trials(conn, [_trial(window="test", candidate_id="M0001-C")])
    assert store.test_looks(conn) == 1
    assert store.dev_trial_count(conn) == 1


def test_status_only_moves_forward(conn):
    _method(conn)
    with conn:
        store.update_method(conn, "M0001", status="registered")
        store.update_method(conn, "M0001", status="rejected")
    with pytest.raises(store.LabError, match="forward"):
        store.update_method(conn, "M0001", status="dev-eligible")
    with pytest.raises(store.LabError, match="forward"):
        store.update_method(conn, "M0001", status="idea")


def test_a_new_method_starts_as_an_idea_or_registered(conn):
    with pytest.raises(store.LabError):
        store.add_method(conn, id="M0001", name="n", family="f", source_kind="knowledge",
                         hypothesis="h", status="dev-eligible")
    with pytest.raises(sqlite3.IntegrityError):
        store.add_method(conn, id="X1", name="n", family="f", source_kind="knowledge", hypothesis="h")


def test_analysis_grows_and_hypothesis_freezes(conn):
    _method(conn)
    with conn:
        store.append_analysis(conn, "M0001", "first")
        store.append_analysis(conn, "M0001", "second")
    text = store.get_method(conn, "M0001")["analysis"]
    assert text.index("first") < text.index("second")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE methods SET analysis = 'rewritten' WHERE id = 'M0001'")
    with conn:
        store.update_method(conn, "M0001", hypothesis="h2")  # still an idea
        store.update_method(conn, "M0001", status="registered")
    with pytest.raises(store.LabError, match="frozen"):
        store.update_method(conn, "M0001", hypothesis="h3")


def test_source_sha_is_set_once(conn):
    _method(conn)
    with conn:
        store.update_method(conn, "M0001", source_sha="aaa")
    with pytest.raises(store.LabError, match="set once"):
        store.update_method(conn, "M0001", source_sha="bbb")


def test_next_id_and_seen(conn):
    assert store.next_method_id(conn) == "M0001"
    _method(conn, "M0007")
    assert store.next_method_id(conn) == "M0008"
    with conn:
        assert store.mark_seen(conn, "url:https://example.com/x", "M0007", "a paper")
        assert not store.mark_seen(conn, "url:https://example.com/x")
    assert [r["key"] for r in store.seen(conn, "EXAMPLE")] == ["url:https://example.com/x"]
    with pytest.raises(store.LabError):
        store.mark_seen(conn, "no-kind")


def test_seed_imports_p7a_as_trials_1_to_54(conn):
    assert seed(conn) == 54
    rows = conn.execute("SELECT * FROM trials ORDER BY n").fetchall()
    assert [r["n"] for r in rows] == list(range(1, 55))
    assert [r["candidate_id"] for r in rows] == [c.id for c in REGISTRY[:54]]
    assert [r["config_digest"] for r in rows] == [config_digest(c) for c in REGISTRY[:54]]
    assert not any(r["eligible"] for r in rows)
    best = max(rows, key=lambda r: r["mar"] or -1)
    assert best["candidate_id"] == "F4-MOM12-N20-TREND"
    assert {r["status"] for r in conn.execute("SELECT status FROM methods")} == {"rejected"}
    with pytest.raises(store.LabError, match="runs once"):
        seed(conn)


def test_seed_configs_are_distinct():
    assert len({config_digest(c) for c in REGISTRY}) == len(REGISTRY)
    c = REGISTRY[3]
    assert config_digest(replace(c, id="F1-OTHER")) == config_digest(c)  # renaming is not a new trial


def test_export_writes_every_sheet(conn, tmp_path):
    from openpyxl import load_workbook

    seed(conn)
    path = store.export_xlsx(conn, tmp_path / "lab.xlsx")
    wb = load_workbook(path)
    assert wb.sheetnames == ["summary", "leaderboard", "methods", "trials", "ideas_seen", "insights"]
    assert wb["leaderboard"].max_row == 55
    assert wb["leaderboard"]["B2"].value == "F4-MOM12-N20-TREND"


def test_insights_are_an_append_only_journal(conn):
    _method(conn)
    with conn:
        n = store.add_insight(conn, kind="data-wish", title="Fundamentals", body="Quarterly earnings would unlock value/quality.", method_id="M0001")
    assert n == 1
    with pytest.raises(store.LabError):
        store.add_insight(conn, kind="rumor", title="t", body="b")
    with pytest.raises(store.LabError):
        store.add_insight(conn, kind="risk", title="t", body="b", method_id="M0404")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE insights SET body = 'x'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM insights")


def test_begin_immediate_makes_id_allocation_atomic(tmp_path):
    a = store.connect(tmp_path / "lab.sqlite")
    b = store.connect(tmp_path / "lab.sqlite")
    b.execute("PRAGMA busy_timeout = 0")
    store.begin_immediate(a)
    with pytest.raises(sqlite3.OperationalError, match="locked"):
        store.begin_immediate(b)
    a.rollback()
    store.begin_immediate(b)
    b.rollback()


# ---- promotion (roster-promotion-pipeline phase 5) ----------------------------------------------


def _promote(conn, **kw):
    base = dict(
        method_id="M0001", strategy_id="FND", candidate_id="M0001-A",
        object_name="FUNDAMENTAL", spec_digest="d" * 64,
    )
    base.update(kw)
    with conn:
        return store.record_promotion(conn, **base)


def test_record_promotion_appends_analysis_and_an_insight(conn):
    _method(conn, status="idea")
    assert _promote(conn, move_status=False) == "idea"
    row = store.get_method(conn, "M0001")
    assert store.PROMOTION_MARKER + "`FND`" in row["analysis"]
    assert "M0001-A" in row["analysis"] and "FUNDAMENTAL" in row["analysis"]
    assert row["status"] == "idea"
    insight = conn.execute("SELECT * FROM insights ORDER BY id DESC LIMIT 1").fetchone()
    assert insight["kind"] == "observation" and insight["method_id"] == "M0001"
    assert "promoted to the paper roster as FND" in insight["title"]


def test_record_promotion_takes_the_edge_transitions_already_has(conn):
    _method(conn, status="idea")
    with conn:
        for nxt in ("registered", "dev-eligible", "promoted", "test-passed"):
            store.update_method(conn, "M0001", status=nxt)
    assert _promote(conn) == "paper"
    assert store.get_method(conn, "M0001")["status"] == "paper"


def test_record_promotion_refuses_a_status_with_no_path_to_paper(conn):
    _method(conn, status="idea")
    with conn:
        store.update_method(conn, "M0001", status="rejected")
    with pytest.raises(store.LabError, match="--lab-status-stays"):
        _promote(conn)
    assert store.get_method(conn, "M0001")["status"] == "rejected"
    assert store.PROMOTION_MARKER not in store.get_method(conn, "M0001")["analysis"]


def test_record_promotion_is_idempotent_and_never_touches_source_sha(conn):
    _method(conn, status="idea")
    with conn:
        store.update_method(conn, "M0001", source_sha="a" * 64)
    _promote(conn, move_status=False)
    _promote(conn, move_status=False)
    row = store.get_method(conn, "M0001")
    assert row["analysis"].count(store.PROMOTION_MARKER) == 1
    assert conn.execute("SELECT count(*) FROM insights").fetchone()[0] == 1
    assert row["source_sha"] == "a" * 64
