"""``lab run`` (method lab design §2, §3) on a synthetic dev-window market."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from labkit import smoke_data

from seer_engine.backtest.dev import Candidate
from seer_engine.lab import runner, store
from seer_engine.lab.method import Method, config_digest
from seer_engine.lab.seed import seed
from seer_engine.sim.rules import DAILY_SWITCH, MONTHLY_HOLD
from seer_engine.strategies.f_index import TIMING, TimingParams
from seer_engine.strategies.f_rotation import ROTATION, RotationParams

def _cand(cid: str, family: str, rules=MONTHLY_HOLD, n: int = 50) -> Candidate:
    return Candidate(
        id=cid, family=family, rules=rules, allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=n),
        rationale="test", added=date(2026, 10, 4), owner_inputs=(),
    )


def _method(mid="M0001", cands=None, **kw) -> Method:
    cands = cands or (_cand(f"{mid}-A", mid), _cand(f"{mid}-B", mid, rules=DAILY_SWITCH, n=20))
    base = dict(id=mid, name="SMA test", family="trend", source_kind="knowledge", source_ref="",
                hypothesis="h", expected_failure="f", candidates=tuple(cands))
    base.update(kw)
    return Method(**base)


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    seed(c)
    yield c
    c.close()


@pytest.fixture(scope="module")
def data():
    return smoke_data()


def test_run_records_trials_with_lab_wide_n(conn, data, tmp_path):
    m = _method()
    ran = runner.run_method(conn, m, Path(__file__), data, git_sha="deadbeef", require_commit=False)
    assert [r.trial.candidate_id for r in ran] == ["M0001-A", "M0001-B"]
    rows = store.trials_of(conn, "M0001")
    assert [r["n"] for r in rows] == [55, 56]
    assert {r["n_trials_at_run"] for r in rows} == {56}
    assert all(r["git_sha"] == "deadbeef" and r["window"] == "dev" for r in rows)
    for r in rows:
        assert r["end"] == "2015-10-16"
        assert json.loads(r["curve_json"])[0][1] > 0
        if r["dsr"] is None or r["dsr"] < store.DSR_MIN:
            assert store.DSR_LABEL in r["failed"] and not r["eligible"]
    method = store.get_method(conn, "M0001")
    assert method["status"] in ("rejected", "dev-eligible")
    assert method["source_sha"]
    assert "Expected failure: f" in method["hypothesis"]


def test_a_method_runs_once_and_configs_never_repeat(conn, data):
    runner.run_method(conn, _method(), Path(__file__), data, git_sha="x", require_commit=False)
    with pytest.raises(store.LabError, match="runs once"):
        runner.preflight(conn, _method(), Path(__file__), require_commit=False)
    clone = _method("M0002", cands=(_cand("M0002-A", "M0002"),))  # same config as M0001-A
    with pytest.raises(store.LabError, match="repeats M0001-A"):
        runner.preflight(conn, clone, Path(__file__), require_commit=False)


def test_a_p7a_configuration_is_not_a_new_trial(conn):
    p7a = Candidate(id="M0003-A", family="M0003", rules=MONTHLY_HOLD, allocator=TIMING,
                    params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=200),
                    rationale="F1-SPY-SMA200-M again", added=date(2026, 10, 4), owner_inputs=())
    with pytest.raises(store.LabError, match="repeats F1-SPY-SMA200-M"):
        runner.preflight(conn, _method("M0003", cands=(p7a,)), Path(__file__), require_commit=False)


def test_an_idea_row_is_registered_by_its_run(conn, data):
    with conn:
        store.add_method(conn, id="M0001", name="queued", family="trend", source_kind="knowledge", hypothesis="old")
    runner.run_method(conn, _method(), Path(__file__), data, git_sha="x", require_commit=False)
    row = store.get_method(conn, "M0001")
    assert row["name"] == "SMA test" and row["hypothesis"].startswith("h")


def test_an_uncommitted_method_file_is_refused(conn, tmp_path):
    f = tmp_path / "m0009_x.py"
    f.write_text("x = 1\n")
    with pytest.raises(store.LabError, match="pre-registration"):
        runner.preflight(conn, _method("M0009"), f)


def test_method_validation():
    with pytest.raises(ValueError, match="start with"):
        _method(cands=(_cand("M0002-A", "M0001"),))
    with pytest.raises(ValueError, match="family"):
        _method(cands=(_cand("M0001-A", "M0002"),))
    with pytest.raises(ValueError, match="repeats"):
        _method(cands=(_cand("M0001-A", "M0001"), _cand("M0001-B", "M0001")))
    with pytest.raises(ValueError, match="parent_id"):
        _method(source_kind="variation", source_ref="M0000")
    with pytest.raises(ValueError, match="source_ref"):
        _method(source_kind="paper")
    rot = Candidate(id="M0001-R", family="M0001", rules=MONTHLY_HOLD, allocator=ROTATION,
                    params=RotationParams(universe=("QQQ", "SPY"), lookback=63, top=1,
                                          absolute=True, fallback=None, trend=None),
                    rationale="r", added=_cand("M0001-A", "M0001").added, owner_inputs=())
    assert config_digest(rot) != config_digest(_cand("M0001-A", "M0001"))
