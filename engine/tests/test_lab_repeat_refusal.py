"""`lab run` refuses an arm that repeats a book another method recorded (lab/twins.py, runner).

Two halves. The rule is read off hand-built trial rows (the `test_lab_twins` fixtures: `_curve` is
deterministic, so two rows built with one ``annual`` and ``trades`` are one book). The refusal is
then driven through `runner.run_method` on the smoke market. A first lab records three arms, their
curves are copied into a second lab under another method id (M0090), and the second lab runs the
same arms again. Copying a curve the runner really produced is the only honest way to make the
simulator repeat a book on purpose: a hand-written curve would never match a simulated one.
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
from datetime import date
from pathlib import Path

import pytest
from labkit import smoke_data

from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import runner, store, twins
from seer_engine.lab.method import Amendment
from seer_engine.lab.seed import seed
from seer_engine.sim.rules import DAILY_SWITCH
from test_lab_hardgate import DEV_SPAN, R_DRAW, R_IDEA, _Arm, _curve, _months, _trial
from test_lab_runner import _cand, _method
from test_lab_twins import R_STEP, _arm, _method_row

HERE = Path(__file__)
HOST = "M0090"
CURVE = _curve(_months(*DEV_SPAN), 0.15)  # what `_arm` records at its defaults


# ------------------------------------------------------------------ the rule, on recorded rows


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    _method_row(c, "M0001")
    _method_row(c, "M0002")
    yield c
    c.close()


def test_recorded_as_finds_every_trial_of_an_unrecorded_book_earliest_first(conn):
    first = _arm(conn, "M0001", "A")
    second = _arm(conn, "M0002", "A")
    found = twins.recorded_as(conn, CURVE, 250)
    assert [(r.n, r.candidate_id) for r in found] == [(first, "M0001-A"), (second, "M0002-A")]
    assert found[0].provenance() == f"trial {first}, M0001, run 2026-10-06, store 640fc25e"
    assert twins.recorded_as(conn, CURVE, 251) == ()
    assert twins.recorded_as(conn, CURVE, 250, "test") == ()
    assert twins.recorded_as(conn, "[]", 250) == ()


def test_an_undeclared_repeat_of_another_methods_book_is_refused(conn):
    n = _arm(conn, "M0001", "A")
    found = twins.repeats(conn, "M0002", [(_Arm("M0002-X", R_STEP), CURVE, 250)])
    assert [(r.candidate_id, r.first.candidate_id, r.first.n, r.declared) for r in found] == [
        ("M0002-X", "M0001-A", n, ""),
    ]
    assert twins.refused(found, 2) == found


def test_a_control_arm_is_a_declared_repeat(conn):
    _arm(conn, "M0001", "A")
    found = twins.repeats(conn, "M0002", [(_Arm("M0002-NEVER", R_DRAW), CURVE, 250)])
    assert found[0].declared == "a control arm"
    assert twins.refused(found, 2) == ()


def test_naming_the_first_recording_method_declares_the_repeat(conn):
    _arm(conn, "M0001", "A")
    arm = _Arm("M0002-HOST", "M0001-A's book, run again so the pair shares one frame")
    found = twins.repeats(conn, "M0002", [(arm, CURVE, 250)])
    assert found[0].declared == "its rationale names M0001"
    assert twins.refused(found, 2) == ()


def test_naming_another_id_that_merely_contains_it_declares_nothing(conn):
    _arm(conn, "M0001", "A")
    arm = _Arm("M0002-HOST", "M00011's book, which is not this one")
    found = twins.repeats(conn, "M0002", [(arm, CURVE, 250)])
    assert found[0].declared == ""


def test_an_idea_arm_is_not_a_declaration(conn):
    _arm(conn, "M0001", "A")
    found = twins.repeats(conn, "M0002", [(_Arm("M0002-A", R_IDEA), CURVE, 250)])
    assert found[0].declared == ""


def test_every_arm_repeating_a_recorded_book_is_refused_even_when_declared(conn):
    _arm(conn, "M0001", "A")
    _arm(conn, "M0001", "B", annual=0.30)
    batch = [
        (_Arm("M0002-NEVER", R_DRAW), CURVE, 250),
        (_Arm("M0002-B", "M0001's other arm, named"), _curve(_months(*DEV_SPAN), 0.30), 250),
    ]
    found = twins.repeats(conn, "M0002", batch)
    assert all(r.declared for r in found)
    assert twins.refused(found, 2) == found


def test_a_book_first_recorded_by_this_same_method_is_not_a_repeat(conn):
    """An amendment re-measuring its original stays an annotation (`report_lines`)."""
    _arm(conn, "M0002", "A")  # the method's own earlier arm
    _arm(conn, "M0001", "A")  # the same book, recorded later by another method
    assert twins.repeats(conn, "M0002", [(_Arm("M0002-C", R_STEP), CURVE, 250)]) == ()


def test_a_repeat_across_store_fingerprints_is_still_a_repeat(conn):
    _arm(conn, "M0001", "A", store_fp="77c37d55aa")
    found = twins.repeats(conn, "M0002", [(_Arm("M0002-X", R_STEP), CURVE, 250)])
    assert found and "store 77c37d55" in found[0].first.provenance()


def test_the_refusal_names_each_arm_its_first_recording_and_the_way_through(conn):
    n = _arm(conn, "M0001", "A")
    found = twins.repeats(conn, "M0002", [(_Arm("M0002-X", R_STEP), CURVE, 250)])
    blocked = twins.refused(found, 2)
    said = twins.refusal("M0002", blocked, 2, amend=False)
    assert f"M0002-X = M0001-A, first recorded (trial {n}, M0001" in said
    assert "1 of 2 arm(s)" in said
    assert "Nothing was recorded and no N was spent" in said
    assert "`lab run M0002`" in said and "--amend" not in said
    assert "`lab run --amend M0002`" in twins.refusal("M0002", blocked, 2, amend=True)


def test_more_repeats_than_arms_is_a_caller_error():
    rec = twins.Recorded(n=1, method_id="M0001", candidate_id="M0001-A",
                         store_fingerprint="x", run_at="2026-11-10")
    with pytest.raises(ValueError):
        twins.refused([twins.Repeat("M0002-A", rec, ""), twins.Repeat("M0002-B", rec, "")], 1)


# ------------------------------------------------------------------ `lab run` itself


@pytest.fixture(scope="module")
def data():
    return smoke_data()


def _three() -> tuple:
    return (
        _cand("M0001-A", "M0001"),
        _cand("M0001-B", "M0001", rules=DAILY_SWITCH, n=20),
        _cand("M0001-C", "M0001", n=75),
    )


def _said(c, rationale: str):
    return dataclasses.replace(c, rationale=rationale)


@pytest.fixture(scope="module")
def books(tmp_path_factory, data):
    """``candidate -> (curve_json, trades)`` for the three arms, as a real run records them."""
    c = store.connect(tmp_path_factory.mktemp("books") / "lab.sqlite")
    seed(c)
    try:
        runner.run_method(c, _method(cands=_three()), HERE, data, git_sha="x", require_commit=False)
        out = {
            str(r["candidate_id"]): (str(r["curve_json"]), int(r["trades"]))
            for r in store.trials_of(c, "M0001")
        }
    finally:
        c.close()
    assert len(set(out.values())) == 3, "the fixture needs three different books"
    return out


@pytest.fixture()
def lab(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    seed(c)
    yield c
    c.close()


def _host(conn, books, *suffixes) -> list[int]:
    """Record ``books`` for ``suffixes`` under HOST, as if another method had run them first."""
    with conn:
        store.add_method(conn, id=HOST, name="the host", family="host",
                         source_kind="knowledge", hypothesis="h", status="registered")
        return store.insert_trials(conn, [
            _trial(method_id=HOST, candidate_id=f"{HOST}-{s}", config_digest=f"host-{s}",
                   curve_json=books[f"M0001-{s}"][0], trades=books[f"M0001-{s}"][1])
            for s in suffixes
        ])


def _metric_lines(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if "money-weighted" in r.getMessage()]


def test_lab_run_refuses_an_undeclared_repeat_and_writes_nothing(lab, data, books, caplog):
    (n,) = _host(lab, books, "A")
    rows_before = store.dev_trial_count(lab)
    caplog.set_level(logging.INFO, logger="seer_engine.lab.runner")
    with pytest.raises(store.LabError) as e:
        runner.run_method(lab, _method(), HERE, data, git_sha="x", require_commit=False)
    said = str(e.value)
    assert f"M0001-A = {HOST}-A, first recorded (trial {n}, {HOST}" in said
    assert "M0001-B =" not in said
    assert store.dev_trial_count(lab) == rows_before
    assert store.trials_of(lab, "M0001") == []
    assert store.get_method(lab, "M0001") is None
    assert not lab.in_transaction
    assert _metric_lines(caplog) == [], "a refused batch must not show any arm's result"


def test_a_refused_idea_stays_an_idea_and_runs_once_the_arm_is_declared(lab, data, books, caplog):
    _host(lab, books, "A")
    with lab:
        store.add_method(lab, id="M0001", name="queued", family="trend",
                         source_kind="knowledge", hypothesis="old")
    with pytest.raises(store.LabError):
        runner.run_method(lab, _method(), HERE, data, git_sha="x", require_commit=False)
    assert store.get_method(lab, "M0001")["status"] == "idea"

    caplog.set_level(logging.INFO, logger="seer_engine.lab.runner")
    a, b = _method().candidates
    fixed = _method(cands=(_said(a, "Control: the host's book, run beside B"), b))
    ran = runner.run_method(lab, fixed, HERE, data, git_sha="y", require_commit=False).ran
    assert [r.trial.candidate_id for r in ran] == ["M0001-A", "M0001-B"]
    assert store.get_method(lab, "M0001")["status"] in ("rejected", "dev-eligible")
    assert len(_metric_lines(caplog)) == 2, "a recorded batch still logs every arm's result"


def test_naming_the_host_in_the_rationale_lets_the_arm_record(lab, data, books):
    _host(lab, books, "A")
    a, b = _method().candidates
    named = _method(cands=(_said(a, f"{HOST}-A's book again, so B is read on one frame"), b))
    ran = runner.run_method(lab, named, HERE, data, git_sha="x", require_commit=False).ran
    assert [r.trial.candidate_id for r in ran] == ["M0001-A", "M0001-B"]


def test_lab_run_refuses_a_batch_that_measures_nothing_new_even_when_declared(lab, data, books):
    _host(lab, books, "A", "B")
    a, b = _method().candidates
    both = _method(cands=(_said(a, "Control: the host's first book"),
                          _said(b, f"{HOST}'s second book, named")))
    with pytest.raises(store.LabError, match="measure nothing new"):
        runner.run_method(lab, both, HERE, data, git_sha="x", require_commit=False)
    assert store.trials_of(lab, "M0001") == []


def test_an_amendment_that_repeats_another_methods_book_is_refused_the_same_way(lab, data, books):
    runner.run_method(lab, _method(), HERE, data, git_sha="x", require_commit=False)
    (n,) = _host(lab, books, "C")
    amended = _method(amendments=(Amendment(
        added=date(2026, 11, 10), why="a slower average", hypothesis="h", expected_failure="e",
        candidates=(_cand("M0001-C", "M0001", n=75),),
    ),))
    rows_before = store.dev_trial_count(lab)
    with pytest.raises(store.LabError) as e:
        runner.run_method(lab, amended, HERE, data, git_sha="y", require_commit=False, amend=True)
    said = str(e.value)
    assert f"M0001-C = {HOST}-C, first recorded (trial {n}" in said
    assert "every one of its 1 arm(s)" in said
    assert "`lab run --amend M0001`" in said
    assert store.dev_trial_count(lab) == rows_before
    assert store.amendments_of(lab, "M0001") == []


# ------------------------------------------------------------------ `lab idea` neighbours


def _idea_args(db, **kw) -> argparse.Namespace:
    base = dict(
        db=db, lab_command="idea", name="A dead zone on the drawdown brake",
        family="drawdown-brake",
        hypothesis="Trim the book in proportion to its fall below its own high, ignoring small falls",
        source_kind="knowledge", source_ref="", parent=None,
    )
    base.update(kw)
    return argparse.Namespace(**base)


def test_lab_idea_prints_the_id_alone_on_stdout_and_its_nearest_methods_on_stderr(
    tmp_path, capsys
):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    with c:
        store.add_method(c, id="M0001", name="A brake on the account's own fall",
                         family="drawdown-brake", source_kind="knowledge",
                         hypothesis="Trim in proportion to how far the book is below its own high",
                         status="registered")
        store.add_method(c, id="M0002", name="Buy last month's losers", family="reversal",
                         source_kind="knowledge", hypothesis="Short-term reversal on residuals",
                         status="registered")
    c.close()
    assert lab_cmd.run(_idea_args(db)) == 0
    got = capsys.readouterr()
    assert got.out == "M0003\n"
    listed = [ln.split()[0] for ln in got.err.splitlines() if ln.startswith("  M")]
    assert listed == ["M0001"]
    assert "lab drop M0003" in got.err


def test_lab_idea_never_refuses_in_an_empty_lab(tmp_path, capsys):
    db = tmp_path / "lab.sqlite"
    store.connect(db).close()
    assert lab_cmd.run(_idea_args(db)) == 0
    got = capsys.readouterr()
    assert got.out == "M0001\n"
    assert "none share a word" in got.err


def test_nearest_methods_weighs_rare_words_and_divides_out_a_long_hypothesis():
    rows = [
        ("M0001", "Quiet uptrend brake", "timing", "step aside in a quiet uptrend", "rejected"),
        ("M0002", "A long essay", "misc",
         "brake " + " ".join(f"filler{i}" for i in range(200)), "rejected"),
        ("M0003", "Nothing alike", "misc", "dividends calendar", "idea"),
    ]
    near = lab_cmd._nearest_methods(rows, "quiet uptrend brake")
    assert [x.id for x in near] == ["M0001", "M0002"]
    assert near[0].shared[:2] == ("quiet", "uptrend")
