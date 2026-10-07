"""``lab costs`` and the M0031 real-fee rule (Sean phase 7): report only, N never moves."""

from __future__ import annotations

import os
import shutil
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from labkit import smoke_data, smoke_test_data

from seer_engine import cli, research
from seer_engine.backtest.dev import Candidate
from seer_engine.commands import promote
from seer_engine.lab import real_costs, runner, store
from seer_engine.lab.method import Method, discover
from seer_engine.lab.seed import seed
from seer_engine.paper import roster
from seer_engine.sim.rules import (
    MONTHLY_HOLD,
    MONTHLY_HOLD_FRAC,
    MONTHLY_HOLD_FRAC_GOTRADE,
    MONTHLY_RANK_WEEKLY_RESIZE_FRAC,
    MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
    PRESETS,
    rule_owner_inputs,
)
from seer_engine.strategies.f_index import TIMING, TimingParams

HERE = Path(__file__)


def _cand(cid, family, rules=MONTHLY_HOLD_FRAC, n=50) -> Candidate:
    return Candidate(
        id=cid, family=family, rules=rules, allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=n),
        rationale="test", added=date(2026, 10, 7), owner_inputs=(),
    )


def _method(mid="M0001", cands=None) -> Method:
    cands = cands or (_cand(f"{mid}-A", mid), _cand(f"{mid}-B", mid, n=20))
    return Method(id=mid, name="SPY above its average", family="trend", source_kind="knowledge",
                  source_ref="", hypothesis="h", expected_failure="f", candidates=tuple(cands))


@pytest.fixture()
def lab(tmp_path):
    path = tmp_path / "lab.sqlite"
    c = store.connect(path)
    seed(c)
    yield c, path
    c.close()


@pytest.fixture(scope="module")
def data():
    return smoke_data()


@pytest.fixture()
def recorded(lab, data):
    conn, _ = lab
    m = _method()
    runner.run_method(conn, m, HERE, data, git_sha="x", require_commit=False)
    return m


def _untouched(conn):
    """Everything `lab costs` must leave as it found it (insights excepted)."""
    return (
        store.dev_trial_count(conn),
        store.test_looks(conn),
        conn.execute("SELECT count(*) FROM trials").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0],
        tuple(tuple(r) for r in conn.execute("SELECT id, status, verdict, source_sha FROM methods ORDER BY id")),
    )


def _insights(conn):
    return conn.execute("SELECT count(*) FROM insights").fetchone()[0]


# ---- measure ---------------------------------------------------------------------------------


def test_measure_runs_the_variant_at_both_fees_and_writes_nothing(lab, data, recorded):
    conn, _ = lab
    before, notes = _untouched(conn), _insights(conn)
    c, trial = real_costs.pick_candidate(conn, recorded, None)
    cmp = real_costs.measure(recorded, c, trial, data)
    assert (cmp.flat.model, cmp.real.model) == ("flat", "gotrade")
    assert cmp.recorded_model == "flat" and cmp.reproduced is True
    assert cmp.real.candidate_id == f"{c.id}-GT"
    assert cmp.real.costs_usd > cmp.flat.costs_usd
    assert cmp.real.total_return < cmp.flat.total_return
    assert _untouched(conn) == before and _insights(conn) == notes


def test_the_default_variant_is_the_best_recorded_by_mar(lab, recorded):
    conn, _ = lab
    rows = [t for t in store.trials_of(conn, "M0001") if t["window"] == "dev"]
    best = sorted(rows, key=lambda t: (t["mar"] is None, -(t["mar"] or 0.0), t["n"]))[0]
    c, trial = real_costs.pick_candidate(conn, recorded, None)
    assert c.id == best["candidate_id"] == trial["candidate_id"]
    other, _ = real_costs.pick_candidate(conn, recorded, "M0001-B")
    assert other.id == "M0001-B"
    with pytest.raises(store.LabError, match="no dev trial for 'M0001-Z'"):
        real_costs.pick_candidate(conn, recorded, "M0001-Z")


def test_a_method_that_never_ran_is_refused(lab):
    conn, _ = lab
    with pytest.raises(store.LabError, match="has no dev trial"):
        real_costs.pick_candidate(conn, _method("M0002"), None)


def test_twins_name_the_side_the_lab_did_not_record():
    flat_c = _cand("M0001-A", "M0001")
    f, g = real_costs.twins(flat_c)
    assert f is flat_c and g.id == "M0001-A-GT"
    assert g.rules == replace(flat_c.rules, cost_model="gotrade")
    real_c = _cand("M0031-A", "M0031", rules=MONTHLY_HOLD_FRAC_GOTRADE)
    f, g = real_costs.twins(real_c)
    assert g is real_c and f.id == "M0031-A-FLAT" and f.rules.cost_model == "flat"


def test_a_variant_with_its_own_cost_rate_has_no_twin():
    odd = _cand("M0001-A", "M0001", rules=replace(MONTHLY_HOLD, id="odd-fee", cost_rate=Decimal("0.002")))
    with pytest.raises(store.LabError, match="its own cost rate"):
        real_costs.twins(odd)


def test_measure_refuses_a_test_window_store(lab, recorded):
    conn, _ = lab
    c, trial = real_costs.pick_candidate(conn, recorded, None)
    with pytest.raises(store.LabError, match="dev window"):
        real_costs.measure(recorded, c, trial, smoke_test_data())


# ---- the journal -----------------------------------------------------------------------------


def test_the_journal_entry_is_one_plain_observation(lab, data, recorded):
    conn, _ = lab
    c, trial = real_costs.pick_candidate(conn, recorded, None)
    cmp = real_costs.measure(recorded, c, trial, data)
    before = _untouched(conn)
    with conn:
        entry = real_costs.journal(conn, cmp)
    row = conn.execute("SELECT * FROM insights WHERE id = ?", (entry,)).fetchone()
    assert row["kind"] == "observation" and row["method_id"] == "M0001"
    assert row["title"] == "SPY above its average: what Gotrade's real fees do to it"
    for text in (row["title"], row["body"]):
        assert "M0001" not in text and "`" not in text and "cost_model" not in text
    assert "count of tries did not move" in row["body"]
    assert _untouched(conn) == before


def _side(model, beats, failed=()):
    return real_costs.Side(
        model=model, candidate_id="M0001-A", total_return=0.5, cagr=0.1, max_drawdown=0.15,
        profit_factor=1.5, trades=120, sharpe=0.8, mar=0.6, exposure=0.9, costs_usd=10.0,
        cost_drag=0.02, spy_tr_return=0.4, spy_tr_cagr=0.08, beats_spy=beats, failed=failed,
    )


@pytest.mark.parametrize(
    ("flat_beats", "real_beats", "phrase"),
    [
        (True, False, "no longer beats SPY"),
        (True, True, "still beats SPY"),
        (False, False, "did not beat SPY at either fee"),
        (False, True, "beats SPY only at the real fees"),
    ],
)
def test_the_verdict_sentence(flat_beats, real_beats, phrase):
    cmp = real_costs.Comparison(
        method_id="M0001", method_name="x", candidate_id="M0001-A", recorded_model="flat",
        trial_n=55, recorded_total_return=0.5, start=date(1996, 1, 2), end=date(2015, 10, 16),
        fingerprint="smoke", flat=_side("flat", flat_beats),
        real=_side("gotrade", real_beats, () if real_beats else ("beats SPY TR",)),
    )
    _, body = real_costs.insight_text(cmp)
    assert phrase in body
    assert ("falls short on beating SPY" in body) is (not real_beats)


# ---- the command -----------------------------------------------------------------------------


def test_cli_lab_costs_reports_and_journals_without_moving_n(lab, data, recorded, monkeypatch, capsys, tmp_path):
    conn, path = lab
    before, notes = _untouched(conn), _insights(conn)
    monkeypatch.setattr(research, "load_store", lambda *a, **k: data)
    monkeypatch.setattr(real_costs, "discover", lambda: {"M0001": (recorded, HERE)})
    assert cli.main(["lab", "--db", str(path), "costs", "M0001", "--store", str(tmp_path / "store")]) == 0
    out = capsys.readouterr().out
    assert "report only" in out and "Gotrade real fees" in out and "reproduces it" in out
    assert _untouched(conn) == before
    assert _insights(conn) == notes + 1


def test_cli_refuses_an_unknown_method_with_exit_2_before_any_store(lab, tmp_path, monkeypatch):
    _, path = lab

    def boom(*a, **k):
        raise AssertionError("the store must not be loaded for a refusal")

    monkeypatch.setattr(research, "load_store", boom)
    assert cli.main(["lab", "--db", str(path), "costs", "M9999", "--store", str(tmp_path)]) == 2
    assert cli.main(["lab", "--db", str(path), "costs", "H-P7A", "--store", str(tmp_path)]) == 2


# ---- the M0031 rule --------------------------------------------------------------------------


def test_requires_real_cost_starts_at_m0031():
    assert not real_costs.requires_real_cost("M0030")
    assert real_costs.requires_real_cost("M0031") and real_costs.requires_real_cost("M1000")
    assert not real_costs.requires_real_cost("H-P7A")


def test_lab_run_refuses_a_flat_cost_variant_from_m0031(lab):
    conn, _ = lab
    flat = _method("M0031", cands=(_cand("M0031-A", "M0031"),))
    with pytest.raises(store.LabError, match="Gotrade's real fees"):
        runner.preflight(conn, flat, HERE, require_commit=False)
    real = _method("M0031", cands=(_cand("M0031-A", "M0031", rules=MONTHLY_HOLD_FRAC_GOTRADE),))
    runner.preflight(conn, real, HERE, require_commit=False)
    old = _method("M0030", cands=(_cand("M0030-A", "M0030"),))
    runner.preflight(conn, old, HERE, require_commit=False)


def test_every_committed_method_from_m0031_runs_at_real_fees():
    for mid, (method, _path) in discover().items():
        assert real_costs.real_cost_problem(method) is None, mid


# ---- the presets -----------------------------------------------------------------------------


def test_the_real_fee_presets_are_promotable_fractional_books():
    pairs = (
        (MONTHLY_HOLD_FRAC_GOTRADE, MONTHLY_HOLD_FRAC),
        (MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE, MONTHLY_RANK_WEEKLY_RESIZE_FRAC),
    )
    for preset, base in pairs:
        assert preset == replace(base, id=f"{base.id}-gotrade", cost_model="gotrade")
        assert preset in PRESETS
        assert roster.rules_for(preset.id) is preset
        assert rule_owner_inputs(preset) == ()
        assert preset.fractional and preset.engine == "book"
    assert PRESETS[-2:] == (MONTHLY_HOLD_FRAC_GOTRADE, MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE)
    # the whole-share flat preset's fractional twin is still the flat one
    assert promote.fractional_twin(MONTHLY_HOLD) is MONTHLY_HOLD_FRAC


# ---- opt-in: the real research store ---------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("SEER_LAB_COSTS_LIVE"),
    reason="set SEER_LAB_COSTS_LIVE=1 (and SEER_RESEARCH_STORE) to run lab costs M0007 on the real store",
)
def test_lab_costs_m0007_on_the_research_store(tmp_path, capsys):
    live_store = Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR)
    db = tmp_path / "lab.sqlite"
    shutil.copy(store.COMMITTED_DB, db)  # a copy: the committed database is never written
    assert cli.main(["lab", "--db", str(db), "costs", "M0007", "--store", str(live_store)]) == 0
    out = capsys.readouterr().out
    assert "lab costs M0007 -- M0007-" in out and "Gotrade real fees" in out
