"""``lab remeasure`` (plan phase 3): recover the DSR inputs of trials recorded before them.

The fixture that matters is ``no_moments``: it suppresses phase 2's ``store.insert_moments`` for
the duration of one ``runner.run_method`` call, which is exactly the shape of the 56 lab-method dev
trials recorded before the ``trial_moments`` table existed.
"""

from __future__ import annotations

import dataclasses
import inspect
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from labkit import smoke_data, smoke_test_data, stamp_provenance

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.dev import Candidate
from seer_engine.lab import remeasure, runner, store
from seer_engine.lab.method import Method
from seer_engine.lab.seed import seed
from seer_engine.sim.rules import DAILY_SWITCH, MONTHLY_HOLD
from seer_engine.strategies.f_index import TIMING, TimingParams

HERE = Path(__file__)


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


@pytest.fixture()
def no_moments(monkeypatch):
    """``lab run`` as it behaved before ``trial_moments``: trials written, moments not.

    Yields the ``monkeypatch`` instance so a test can ``.undo()`` the suppression after the run it
    was for -- pytest hands the fixture and the test the same instance, so a test that also takes
    ``monkeypatch`` must call ``no_moments.undo()`` **before** its own ``setattr``.
    """
    monkeypatch.setattr(store, "insert_moments", lambda conn, rows: None)
    yield monkeypatch


def _run(conn, data, method):
    return runner.run_method(conn, method, HERE, data, git_sha="deadbeef", require_commit=False)


def _trials_snapshot(conn):
    return [tuple(r) for r in conn.execute("SELECT * FROM trials ORDER BY n")]


# ---- the backfill ------------------------------------------------------------------------------


def test_remeasure_backfills_moments_and_reproduces_the_recorded_dsr(conn, data, no_moments):
    m = _method()
    _run(conn, data, m)
    no_moments.undo()
    numbers = [int(r["n"]) for r in store.trials_of(conn, "M0001")]
    assert numbers == [55, 56]
    assert all(store.moments_of(conn, n) is None for n in numbers)
    # The N to reproduce is the one the run recorded, whatever `store.DSR_POLICY` resolved to --
    # read back off the rows rather than typed, because it is the row count only under
    # `all-trials` and `methods` has shipped since 2026-10-08 (lab-realistic-gate R1). The whole
    # point of `remeasure` is to rebuild inputs that reproduce the RECORDED dsr, so the recorded
    # N is the only honest source for it.
    recorded = {int(r["n_trials_at_run"]) for r in store.trials_of(conn, "M0001")}
    assert len(recorded) == 1, f"one batch, one N: {recorded}"
    (n_at_run,) = recorded

    report = remeasure.remeasure(conn, m, HERE, data, require_commit=False)

    assert sorted(report.written) == numbers
    assert report.skipped == ()
    assert len(report.measured) == 2
    for r in report.measured:
        assert r.ok
        assert r.sharpe_delta <= remeasure.SHARPE_TOL * max(abs(r.recorded_sharpe), 1.0)
        assert r.dsr_delta <= remeasure.DSR_TOL
        assert r.n_at_run == n_at_run
    for n in numbers:
        row = store.moments_of(conn, n)
        assert row is not None and row["n_at_run"] == n_at_run and row["t"] > 2
    assert store.test_looks(conn) == 0
    text = remeasure.format_report(report)
    assert "re-measured on the dev window" in text and "No trials row was inserted" in text


def test_the_reconstructed_var_trials_equals_what_the_run_used(tmp_path, data, monkeypatch):
    """The proof that the reconstruction is the original quantity, not a lookalike.

    ``var_trials`` as of a run is recorded nowhere. Run the same method into two databases -- once
    with phase 2's writer live, once with it suppressed and then backfilled by ``remeasure`` -- and
    the two ``trial_moments`` rows must agree exactly.
    """
    m = _method()
    live = store.connect(tmp_path / "live.sqlite")
    seed(live)
    runner.run_method(live, m, HERE, data, git_sha="x", require_commit=False)
    truth = {int(r["n"]): dict(store.moments_of(live, int(r["n"])))
             for r in store.trials_of(live, "M0001")}
    live.close()
    assert truth and all(v["var_trials"] is not None for v in truth.values())

    back = store.connect(tmp_path / "back.sqlite")
    seed(back)
    monkeypatch.setattr(store, "insert_moments", lambda conn, rows: None)
    runner.run_method(back, m, HERE, data, git_sha="x", require_commit=False)
    monkeypatch.undo()
    remeasure.remeasure(back, m, HERE, data, require_commit=False)
    for n, want in truth.items():
        got = store.moments_of(back, n)
        assert got["var_trials"] == want["var_trials"]
        assert got["sr_daily"] == want["sr_daily"]
        assert got["t"] == want["t"]
        assert got["skew"] == want["skew"]
        assert got["kurt"] == want["kurt"]
        assert got["n_at_run"] == want["n_at_run"]
    back.close()


def test_remeasure_is_idempotent(conn, data, no_moments):
    m = _method()
    _run(conn, data, m)
    no_moments.undo()
    first = remeasure.remeasure(conn, m, HERE, data, require_commit=False)
    assert len(first.written) == 2
    before = {n: dict(store.moments_of(conn, n)) for n in first.written}

    plan = remeasure.preflight(conn, m, HERE, require_commit=False)
    assert plan.nothing_to_do and sorted(plan.present) == sorted(first.written)

    second = remeasure.remeasure(conn, m, HERE, data, require_commit=False)
    assert second.written == () and second.measured == ()
    assert sorted(second.skipped) == sorted(first.written)
    assert {n: dict(store.moments_of(conn, n)) for n in first.written} == before


def test_remeasure_writes_only_trial_moments(conn, data, no_moments):
    m = _method()
    _run(conn, data, m)
    no_moments.undo()
    trials_before = _trials_snapshot(conn)
    method_before = tuple(store.get_method(conn, "M0001"))

    remeasure.remeasure(conn, m, HERE, data, require_commit=False)

    assert _trials_snapshot(conn) == trials_before
    assert tuple(store.get_method(conn, "M0001")) == method_before
    assert store.dev_trial_count(conn) == 56
    assert store.test_looks(conn) == 0


# ---- the refusals ------------------------------------------------------------------------------


def test_a_method_with_a_test_trial_is_refused_before_anything_is_loaded(conn, data, no_moments):
    m = _method()
    ran = _run(conn, data, m)
    no_moments.undo()
    # The same configuration, one window along: `UNIQUE(config_digest, window)` and
    # `UNIQUE(candidate_id, window)` are both per-window, so this is the shape `lab test` writes.
    with conn:
        store.insert_trials(conn, [dataclasses.replace(ran[0].trial, window="test")])
    assert store.test_looks(conn) == 1
    # `data` is never reached: preflight refuses first, so None is safe to pass.
    with pytest.raises(store.LabError, match="look at the test window"):
        remeasure.remeasure(conn, m, HERE, None, require_commit=False)


def test_a_method_with_no_dev_trial_is_refused(conn, data):
    with conn:
        store.add_method(conn, id="M0003", name="queued", family="trend",
                         source_kind="knowledge", hypothesis="h")
    with pytest.raises(store.LabError, match="no dev trial"):
        remeasure.remeasure(conn, _method("M0003"), HERE, None, require_commit=False)


def test_a_seed_family_is_refused_by_name(conn):
    with pytest.raises(store.LabError, match="not a lab method id"):
        remeasure.resolve_method("H-P7A-F1")
    with pytest.raises(store.LabError, match="no method file"):
        remeasure.resolve_method("M9999")


def test_a_trial_with_no_recorded_dsr_cannot_be_verified(conn, data, no_moments):
    """The P7a seed's shape: a dev trial whose ``dsr`` is NULL has no verdict to reproduce."""
    ran = _run(conn, data, _method())
    no_moments.undo()
    with conn:
        store.add_method(conn, id="M0003", name="seed-shaped", family="trend",
                         source_kind="knowledge", hypothesis="h")
        store.insert_trials(conn, [dataclasses.replace(
            ran[0].trial, method_id="M0003", candidate_id="M0003-A",
            config_digest="0" * 64, dsr=None,
        )])
    with pytest.raises(store.LabError, match="recorded no DSR"):
        remeasure.preflight(conn, _method("M0003", cands=(_cand("M0003-A", "M0003"),)),
                            HERE, require_commit=False)


# ---- the test window is unreachable, structurally ----------------------------------------------


def test_a_test_window_store_is_refused(conn, data, no_moments):
    m = _method()
    _run(conn, data, m)
    no_moments.undo()
    with pytest.raises(store.LabError, match="re-runs the dev window"):
        remeasure.remeasure(conn, m, HERE, smoke_test_data(), require_commit=False)
    assert all(store.moments_of(conn, n) is None for n in (55, 56))
    assert store.test_looks(conn) == 0


def test_no_window_can_be_selected_anywhere_in_the_command(conn, data, no_moments, monkeypatch):
    m = _method()
    _run(conn, data, m)
    no_moments.undo()
    for fn in (remeasure.measure, remeasure.remeasure, remeasure.preflight):
        assert "window" not in inspect.signature(fn).parameters
    calls: list[dict] = []
    real = dev.run_registry

    def spy(*a, **k):
        calls.append(dict(k))
        return real(*a, **k)

    monkeypatch.setattr(remeasure.dev, "run_registry", spy)
    remeasure.remeasure(conn, m, HERE, data, require_commit=False)
    assert calls and all("window" not in k for k in calls)
    assert data.window == research.DEV_WINDOW
    assert store.test_looks(conn) == 0


# ---- a divergent re-run aborts -----------------------------------------------------------------


def test_a_divergent_rerun_aborts_and_writes_nothing(conn, data, no_moments, monkeypatch):
    m = _method()
    _run(conn, data, m)
    no_moments.undo()
    real = remeasure.daily_moments

    def shifted(returns):
        out = real(returns)
        return None if out is None else (out[0] * 1.05, out[1], out[2])

    monkeypatch.setattr(remeasure, "daily_moments", shifted)
    with pytest.raises(store.LabError, match="does not reproduce"):
        remeasure.remeasure(conn, m, HERE, data, require_commit=False)
    assert all(store.moments_of(conn, n) is None for n in (55, 56))


def test_check_names_the_trial_and_the_delta(conn):
    base = dict(trial_n=55, candidate_id="M0001-A", n_at_run=56, t=400, sr_daily=0.05,
                skew=-0.1, kurt=4.0, var_trials=2.4e-4, recorded_sharpe=0.9,
                measured_sharpe=0.9, recorded_dsr=0.91, recomputed_dsr=0.91)
    remeasure.check("M0001", [remeasure.Reproduced(**base)])  # the good case raises nothing

    drifted_sharpe = remeasure.Reproduced(**{**base, "measured_sharpe": 0.8})
    with pytest.raises(store.LabError, match="annualized Sharpe"):
        remeasure.check("M0001", [drifted_sharpe])

    drifted_dsr = remeasure.Reproduced(**{**base, "recomputed_dsr": 0.95})
    with pytest.raises(store.LabError, match=r"DSR 0\.91 recorded"):
        remeasure.check("M0001", [drifted_dsr])


# ---- the CLI ------------------------------------------------------------------------------------


def test_the_cli_refuses_with_exit_2_and_loads_no_store(tmp_path, conn):
    import argparse

    from seer_engine.commands import lab as lab_cmd

    args = argparse.Namespace(
        db=tmp_path / "lab.sqlite", lab_command="remeasure", method="M9999",
        store=tmp_path / "nowhere",
    )
    assert lab_cmd.run(args) == 2
    assert not (tmp_path / "nowhere").exists()


def test_a_plan_that_mixes_funded_and_unfunded_trials_is_refused(conn, data, tmp_path):
    """One `run_registry` call runs every candidate on one schedule, so a mixed plan has no
    answer that reproduces both. It is refused before anything is re-run or written."""
    import sqlite3 as _sqlite3

    m = _method()
    runner.run_method(conn, m, HERE, data, git_sha="x", require_commit=False)
    ns = sorted(int(r["n"]) for r in store.trials_of(conn, m.id))
    assert len(ns) >= 2 and all(store.funding_of(conn, n) is not None for n in ns)
    # Drop one trial's funding row the only way the schema allows it to be absent: a database
    # where it was never written. `trial_funding` has no-delete and no-update triggers, so this
    # test builds the mixed state by copying the lab to a file and deleting with the triggers
    # dropped -- a state a real run cannot produce, which is the point of refusing it.
    path = tmp_path / "mixed.sqlite"
    other = _sqlite3.connect(path)
    conn.backup(other)
    other.execute("DROP TRIGGER trial_funding_no_delete")
    other.execute("DELETE FROM trial_funding WHERE trial_n = ?", (ns[0],))
    other.commit()
    other.close()
    mixed = store.connect(path)
    try:
        plan = remeasure.preflight(mixed, m, HERE, require_commit=False)
        with pytest.raises(store.LabError, match="received deposits"):
            remeasure.measure(mixed, m, plan, data)
    finally:
        mixed.close()


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
