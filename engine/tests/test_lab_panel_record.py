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
