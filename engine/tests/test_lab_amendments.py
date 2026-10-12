"""``lab run --amend``: a further pre-registered batch of variants of a method that has run.

The whole point of the mechanism is the gate: under ``store.DSR_POLICY = 'methods'`` a new method
id costs the lab one more independent look, retroactively, while another variant of an idea it has
already counted costs nothing. So the assertion that matters most here is that an amendment's
trials land under the method's own id and ``store.pending_gate`` does not move -- everything else
is the pre-registration discipline that keeps that cheapness honest.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest
from labkit import smoke_data

from seer_engine.lab import runner, store
from seer_engine.lab.method import Amendment, Method, config_digest
from seer_engine.lab.seed import seed
from seer_engine.sim.rules import DAILY_SWITCH, MONTHLY_HOLD
from seer_engine.strategies.f_index import TIMING, TimingParams
from seer_engine.backtest.dev import Candidate

HERE = Path(__file__)


def _cand(cid: str, family: str, rules=MONTHLY_HOLD, n: int = 50) -> Candidate:
    return Candidate(
        id=cid, family=family, rules=rules, allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=n),
        rationale="test", added=date(2026, 10, 4), owner_inputs=(),
    )


def _amendment(*cands: Candidate, added: date = date(2026, 10, 12)) -> Amendment:
    return Amendment(
        added=added,
        why="the parked market money is the drag",
        hypothesis="the satellite at full size beats the blend after 2009",
        expected_failure="the worst fall goes past 20% and nothing is eligible",
        candidates=tuple(cands),
    )


def _method(mid="M0001", cands=None, amendments=(), **kw) -> Method:
    cands = cands or (_cand(f"{mid}-A", mid), _cand(f"{mid}-B", mid, rules=DAILY_SWITCH, n=20))
    base = dict(id=mid, name="SMA test", family="trend", source_kind="knowledge", source_ref="",
                hypothesis="h", expected_failure="f", candidates=tuple(cands),
                amendments=tuple(amendments))
    base.update(kw)
    return Method(**base)


def _amended(mid="M0001") -> Method:
    return _method(mid, amendments=(_amendment(_cand(f"{mid}-C", mid, n=75)),))


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    seed(c)
    yield c
    c.close()


@pytest.fixture(scope="module")
def data():
    return smoke_data()


# ---- the value ---------------------------------------------------------------------------------


def test_all_candidates_is_the_originals_then_each_amendments_in_order():
    m = _method(amendments=(
        _amendment(_cand("M0001-C", "M0001", n=75)),
        _amendment(_cand("M0001-D", "M0001", n=76), _cand("M0001-E", "M0001", n=77)),
    ))
    assert [c.id for c in m.all_candidates()] == ["M0001-A", "M0001-B", "M0001-C", "M0001-D", "M0001-E"]
    assert m.all_candidates()[:2] == m.candidates
    assert _method().all_candidates() == _method().candidates


def test_an_amendment_may_not_repeat_an_id_or_a_configuration_of_any_batch():
    with pytest.raises(ValueError, match="appears twice"):
        _method(amendments=(_amendment(_cand("M0001-A", "M0001", n=99)),))
    with pytest.raises(ValueError, match="repeats another variant's configuration"):
        _method(amendments=(_amendment(_cand("M0001-C", "M0001", n=50)),))
    with pytest.raises(ValueError, match="must have family M0001"):
        _method(amendments=(_amendment(_cand("M0001-C", "M0002", n=75)),))
    with pytest.raises(ValueError, match="must start with M0001-"):
        _method(amendments=(_amendment(_cand("M0009-C", "M0001", n=75)),))


def test_an_amendment_carries_one_to_six_candidates_of_its_own():
    """Decision D3: the cap is per amendment, not per method lifetime."""
    six = tuple(_cand(f"M0001-X{i}", "M0001", n=60 + i) for i in range(6))
    assert len(_method(amendments=(_amendment(*six),)).all_candidates()) == 8
    with pytest.raises(ValueError, match="1..6 candidates"):
        _amendment(*(_cand(f"M0001-Y{i}", "M0001", n=70 + i) for i in range(7)))
    with pytest.raises(ValueError, match="1..6 candidates"):
        Amendment(added=date(2026, 10, 12), why="w", hypothesis="h",
                  expected_failure="e", candidates=())


def test_adding_the_amendments_field_moves_no_config_digest():
    """Plan invariant 3, from the other side of ``test_lab_methods``'s recorded-trial check.

    ``config_text`` reads ``c.rules``, ``c.allocator.id`` and ``c.params`` and never the ``Method``
    that holds the candidate, so a field added to ``Method`` cannot reach ``registry._canon``.
    """
    plain = _method()
    amended = _amended()
    assert [config_digest(c) for c in plain.candidates] == [config_digest(c) for c in amended.candidates]


# ---- the record --------------------------------------------------------------------------------


def test_an_amendment_run_lands_under_the_same_method_id_and_moves_no_gate(conn, data):
    before = store.gate(conn)
    runner.run_method(conn, _method(), HERE, data, git_sha="x", require_commit=False)
    after_first = store.gate(conn)
    projected = store.pending_gate(conn, "M0001", 1)
    runner.run_method(conn, _amended(), HERE, data, git_sha="y", require_commit=False, amend=True)
    rows = store.trials_of(conn, "M0001")
    assert [r["candidate_id"] for r in rows] == ["M0001-A", "M0001-B", "M0001-C"]
    assert {str(r["method_id"]) for r in rows} == {"M0001"}
    # The batch was judged at the N `pending_gate` projected for an already-counted method, and
    # the lab's own N did not move because no new method was looked at.
    assert rows[-1]["n_trials_at_run"] == projected.n
    assert store.gate(conn) == after_first
    assert after_first.n >= before.n


def test_an_amendment_records_its_sha_and_leaves_methods_source_sha_alone(conn, data):
    runner.run_method(conn, _method(), HERE, data, git_sha="x", require_commit=False)
    first = store.get_method(conn, "M0001")["source_sha"]
    status_before = store.get_method(conn, "M0001")["status"]
    runner.run_method(conn, _amended(), HERE, data, git_sha="y", require_commit=False, amend=True)
    assert store.get_method(conn, "M0001")["source_sha"] == first
    assert store.get_method(conn, "M0001")["status"] == status_before  # Decision P2
    rows = store.amendments_of(conn, "M0001")
    assert [int(r["seq"]) for r in rows] == [1]
    assert str(rows[0]["source_sha"]) == first  # the same file, so the same sha, recorded anyway
    assert str(rows[0]["added"]) == "2026-10-12"
    assert str(rows[0]["why"]) == "the parked market money is the drag"
    assert str(rows[0]["git_sha"]) == "y"
    # The join back to the batch it pre-registered.
    assert str(rows[0]["run_at"]) == str(store.trials_of(conn, "M0001")[-1]["run_at"])
    assert store.latest_source_sha(conn, "M0001") == first


def test_method_amendments_is_append_only(conn, data):
    runner.run_method(conn, _method(), HERE, data, git_sha="x", require_commit=False)
    runner.run_method(conn, _amended(), HERE, data, git_sha="y", require_commit=False, amend=True)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE method_amendments SET why = 'something else'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM method_amendments")


def test_seq_must_be_contiguous(conn, data):
    runner.run_method(conn, _method(), HERE, data, git_sha="x", require_commit=False)
    with pytest.raises(store.LabError, match="amendment seq must be 1"):
        with conn:
            store.insert_amendment(conn, store.AmendmentRow(
                method_id="M0001", seq=2, source_sha="c" * 64, added="2026-10-12",
                why="w", hypothesis="h", expected_failure="e",
                run_at="2026-10-12T00:00:00+00:00", git_sha="z",
            ))


def test_an_amendment_needs_a_method_that_has_run(conn, data):
    with pytest.raises(store.LabError, match="has not run"):
        runner.preflight(conn, _amended(), HERE, require_commit=False, amend=True)
    # A method row that exists but has never run: source_sha is still NULL, so there is a method
    # to name and nothing to amend. Without the row `insert_amendment` would stop one guard
    # earlier, on "no method M0001", and this branch would go untested.
    with conn:
        store.add_method(conn, id="M0001", name="SMA test", family="trend",
                         source_kind="knowledge", source_ref="", hypothesis="h",
                         status="registered")
    with pytest.raises(store.LabError, match="nothing to amend"):
        with conn:
            store.insert_amendment(conn, store.AmendmentRow(
                method_id="M0001", seq=1, source_sha="c" * 64, added="2026-10-12",
                why="w", hypothesis="h", expected_failure="e",
                run_at="2026-10-12T00:00:00+00:00", git_sha="z",
            ))


def test_amend_refuses_a_method_file_that_declares_none(conn, data):
    runner.run_method(conn, _method(), HERE, data, git_sha="x", require_commit=False)
    with pytest.raises(store.LabError, match="declares none"):
        runner.preflight(conn, _method(), HERE, require_commit=False, amend=True)


def test_a_committed_but_unrun_amendment_is_the_one_tolerated_sha_mismatch(conn, data):
    """The pre-registration window, as a unit.

    ``pending_amendment`` resolving is exactly the predicate
    ``test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha`` accepts a sha mismatch on, and
    it is the state phases 3 and 4 leave the tree in until phase 5 runs. It opens when the
    amendment is committed and closes the moment it is recorded; it is not a state a method can
    sit in twice for the same block.
    """
    runner.run_method(conn, _method(), HERE, data, git_sha="x", require_commit=False)
    m = _amended()
    assert store.amendments_of(conn, "M0001") == []      # committed, not yet run
    assert runner.pending_amendment(conn, m) == m.amendments[0]
    runner.run_method(conn, m, HERE, data, git_sha="y", require_commit=False, amend=True)
    with pytest.raises(store.LabError, match="have already run"):
        runner.pending_amendment(conn, m)                # window closed: the row exists now


def test_an_amendment_runs_once(conn, data):
    runner.run_method(conn, _method(), HERE, data, git_sha="x", require_commit=False)
    runner.run_method(conn, _amended(), HERE, data, git_sha="y", require_commit=False, amend=True)
    with pytest.raises(store.LabError, match="have already run"):
        runner.preflight(conn, _amended(), HERE, require_commit=False, amend=True)


def test_a_spent_amendment_may_not_be_edited(conn, data):
    """Plan Decision P4: the record is a prefix of the file, checked field for field."""
    runner.run_method(conn, _method(), HERE, data, git_sha="x", require_commit=False)
    runner.run_method(conn, _amended(), HERE, data, git_sha="y", require_commit=False, amend=True)
    edited = _method(amendments=(
        Amendment(added=date(2026, 10, 12), why="a different reason", hypothesis="h2",
                  expected_failure="e2", candidates=(_cand("M0001-C", "M0001", n=75),)),
        _amendment(_cand("M0001-D", "M0001", n=76)),
    ))
    with pytest.raises(store.LabError, match="no longer matches the one the lab recorded"):
        runner.preflight(conn, edited, HERE, require_commit=False, amend=True)
    dropped = _method()  # the amendment removed from the file entirely
    with pytest.raises(store.LabError, match="recorded 1 amendment"):
        runner.preflight(conn, dropped, HERE, require_commit=False, amend=True)


def test_a_method_that_reached_the_test_window_is_not_amended(conn, data):
    runner.run_method(conn, _method(), HERE, data, git_sha="x", require_commit=False)
    with conn:
        store.update_method(conn, "M0001", status="dev-eligible")
        store.update_method(conn, "M0001", status="promoted")
    with pytest.raises(store.LabError, match="not amended"):
        runner.preflight(conn, _amended(), HERE, require_commit=False, amend=True)


def test_an_amendment_may_not_repeat_a_recorded_configuration(conn, data):
    """``Method.__post_init__`` refuses it before any backtest is paid for.

    The database would refuse it too -- ``preflight``'s ``has_trial`` loop, and in the last resort
    ``trials``'s ``UNIQUE (config_digest, window)`` -- but the method file is the cheaper no, and
    it is the one a phase-3 or phase-4 author hits while writing the amendment.
    """
    runner.run_method(conn, _method(), HERE, data, git_sha="x", require_commit=False)
    with pytest.raises(ValueError, match="repeats another variant's configuration"):
        _method(amendments=(_amendment(_cand("M0001-C", "M0001", n=50)),))
