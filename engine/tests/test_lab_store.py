"""The lab database's rules (method lab design §1): append-only trials, forward-only status,
growing analysis, one test look per configuration, the seed import and the export."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import date

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


def test_best_dev_eligible_is_the_highest_mar_and_breaks_ties_on_the_trial_number(conn):
    # Since LAB_LUCK_GATE_PLAN.md phase 4, "eligible" here is `store.verdict(...).eligible`, not
    # the recorded `eligible` column -- so the rows have to be eligible in their NUMBERS, under
    # the bars in force now. Two consequences for this fixture, neither of which touches what the
    # test is about (MAR order, the tie on `n`, the NULL MAR and the test trial):
    #   * the Sharpes differ, so the lab has a trial-Sharpe variance for `dsr_at` to deflate by
    #     -- with one repeated Sharpe there is no dispersion and no DSR is evaluable at all;
    #   * `n_trials_at_run` is the 4 dev rows below, so each DSR is read back at its own N, and
    #     C is kept out by a 24.5% drawdown rather than by its recorded `failed` string.
    _method(conn)
    assert store.best_dev_eligible(conn, "M0001") is None
    with conn:
        store.insert_trials(conn, [
            _trial(candidate_id="M0001-A", config_digest="da", mar=0.9, eligible=True, failed="",
                   dsr=0.95, sharpe=0.80, n_trials_at_run=4),
            _trial(candidate_id="M0001-B", config_digest="db", mar=0.9, eligible=True, failed="",
                   dsr=0.95, sharpe=0.94, n_trials_at_run=4),
            _trial(candidate_id="M0001-C", config_digest="dc", mar=1.4, max_drawdown=0.245,
                   dsr=0.95, sharpe=1.10, n_trials_at_run=4),  # not eligible: drawdown
            _trial(candidate_id="M0001-D", config_digest="dd", mar=None, eligible=True, failed="",
                   dsr=0.95, sharpe=1.46, n_trials_at_run=4),
            _trial(candidate_id="M0001-E", config_digest="de", window="test", mar=2.0,
                   eligible=True, failed=""),
        ])
    # Judge at the N these rows were RECORDED at -- `n_trials_at_run=4`, which is the dev row
    # count -- rather than at whatever `store.DSR_POLICY` resolves to. That is what makes
    # `store.verdict`'s re-evaluation the identity here, which is the condition the comment above
    # describes and which every assertion below rests on. Derived from the data, not typed, and
    # it names no shipped constant: the subject is `best_dev_eligible`'s ordering, not the gate.
    at = store.Gate(n=store.dev_trial_count(conn), policy="all-trials")
    best = store.best_dev_eligible(conn, "M0001", at=at)
    assert best["candidate_id"] == "M0001-A"  # the tie breaks on n, and the test trial is not it
    assert store.best_dev_eligible(conn, "M0002", at=at) is None


def _moments(**kw) -> store.MomentsRow:
    base = dict(trial_n=1, sr_daily=0.0501, t=3959, skew=-0.31, kurt=7.2, var_trials=2.395e-04,
                n_at_run=110, measured="2026-10-07T00:00:00+00:00")
    base.update(kw)
    return store.MomentsRow(**base)


def test_trial_moments_are_append_only_and_at_most_one_per_trial(conn):
    _method(conn)
    with conn:
        ns = store.insert_trials(conn, [_trial()])
    assert store.moments_of(conn, ns[0]) is None  # a trial recorded before this table has none
    with conn:
        store.insert_moments(conn, [_moments(trial_n=ns[0])])
    got = store.moments_of(conn, ns[0])
    assert list(got.keys()) == list(store.MOMENTS_COLUMNS)
    assert (got["trial_n"], got["t"], got["n_at_run"]) == (ns[0], 3959, 110)
    assert got["sr_daily"] == 0.0501 and got["skew"] == -0.31 and got["kurt"] == 7.2
    assert got["var_trials"] == 2.395e-04 and got["measured"] == "2026-10-07T00:00:00+00:00"

    with pytest.raises(store.LabError, match="already has recorded moments"):
        store.insert_moments(conn, [_moments(trial_n=ns[0], t=10)])
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE trial_moments SET t = 9")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM trial_moments")
    assert store.moments_of(conn, ns[0])["t"] == 3959


def test_moments_need_a_real_trial_number(conn):
    _method(conn)
    with conn:
        store.insert_trials(conn, [_trial()])
    with pytest.raises(store.LabError, match="insert_trials assigned"):
        store.insert_moments(conn, [_moments(trial_n=0)])
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        with conn:
            store.insert_moments(conn, [_moments(trial_n=999)])
    assert store.moments_of(conn, 999) is None
    with conn:  # var_trials is nullable: a lab with fewer than two Sharpes has no variance
        store.insert_moments(conn, [_moments(trial_n=1, var_trials=None, n_at_run=1)])
    assert store.moments_of(conn, 1)["var_trials"] is None


def test_status_only_moves_forward(conn):
    # `rejected -> dev-eligible` is the one edge out of `rejected` (LAB_LUCK_GATE_PLAN.md
    # Decision D2) and is exercised in test_lab_gate_policy.py, where the Python guard that
    # admits it lives. Every other move out of `rejected` is still refused, which is what this
    # test is about.
    _method(conn)
    with conn:
        store.update_method(conn, "M0001", status="registered")
        store.update_method(conn, "M0001", status="rejected")
    with pytest.raises(store.LabError, match="forward"):
        store.update_method(conn, "M0001", status="promoted")
    with pytest.raises(store.LabError, match="forward"):
        store.update_method(conn, "M0001", status="paper")
    with pytest.raises(store.LabError, match="forward"):
        store.update_method(conn, "M0001", status="idea")


def test_a_new_method_starts_as_an_idea_or_registered(conn):
    with pytest.raises(store.LabError):
        store.add_method(conn, id="M0001", name="n", family="f", source_kind="knowledge",
                         hypothesis="h", status="dev-eligible")
    with pytest.raises(sqlite3.IntegrityError):
        store.add_method(conn, id="X1", name="n", family="f", source_kind="knowledge", hypothesis="h")


def test_append_analysis_does_not_double_the_authors_own_date_heading(conn):
    today = date.today().isoformat()
    _method(conn)
    with conn:
        store.append_analysis(conn, "M0001", f"### {today}\n\nthe note")
        store.append_analysis(conn, "M0001", "a note with no heading of its own")
        store.append_analysis(conn, "M0001", "### 2020-01-01\n\nsomeone else's date")
    text = store.get_method(conn, "M0001")["analysis"]
    assert f"### {today}\n\n### {today}" not in text
    assert text.count(f"### {today}") == 3  # one head per append, never two
    assert text.startswith(f"### {today}\n\nthe note")
    assert f"### {today}\n\n### 2020-01-01" in text  # a stale date is headed, not trusted


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
        reason="the lab has not passed it; on paper to test it forward",
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
    assert "starts paper trading as FND" in insight["title"]
    assert "`" not in insight["body"] and "digest" not in insight["body"]


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


def test_promotion_basis_is_derived_from_the_lab_status():
    assert store.promotion_basis("test-passed") == "test-passed"
    assert store.promotion_basis("paper") == "test-passed"
    for s in ("idea", "registered", "rejected", "dev-eligible", "promoted", "blocked-data"):
        assert store.promotion_basis(s) == "owner-override"
    assert set(store.PROMOTION_BASES) == {"test-passed", "owner-override"}


def test_record_promotion_writes_the_basis_the_status_and_the_reason(conn):
    _method(conn, status="idea")
    assert _promote(conn, move_status=False) == "idea"
    analysis = store.get_method(conn, "M0001")["analysis"]
    assert "Lab status at admission: `idea`" in analysis
    assert "Basis: `owner-override`" in analysis
    assert "on paper to test it forward" in analysis


def test_an_override_with_no_reason_is_refused_and_writes_nothing(conn):
    _method(conn, status="idea")
    with pytest.raises(store.LabError, match="reason"):
        _promote(conn, move_status=False, reason="   ")
    row = store.get_method(conn, "M0001")
    assert store.PROMOTION_MARKER not in row["analysis"]
    assert conn.execute("SELECT count(*) FROM insights").fetchone()[0] == 0


def test_a_test_passed_method_needs_no_reason_and_says_so(conn):
    _method(conn, status="idea")
    with conn:
        for nxt in ("registered", "dev-eligible", "promoted", "test-passed"):
            store.update_method(conn, "M0001", status=nxt)
    assert _promote(conn, reason="") == "paper"
    analysis = store.get_method(conn, "M0001")["analysis"]
    assert "Basis: `test-passed`" in analysis
    assert "Lab status at admission: `test-passed`" in analysis
