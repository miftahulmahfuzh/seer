"""Book twins (lab/twins.py): one book recorded under several candidate ids, named on read.

Every fixture builds its own temp lab. `_curve` is deterministic, so two trials recorded with the
same ``annual`` and ``trades`` carry byte-identical curves -- which is the whole fixture. The live
tests at the bottom read the committed lab ``mode=ro`` through a bare ``sqlite3.connect`` (the way
the calculate-assets skill opens it) and hash the file either side: the twins they name are
append-only trial rows, so a later batch can add names after them but never move them.
"""

from __future__ import annotations

import argparse
import hashlib
import sqlite3

import pytest

from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import store, twins
from test_lab_hardgate import (
    DEV_SPAN,
    R_DRAW,
    R_IDEA,
    _Arm,
    _curve,
    _declare,
    _months,
    _stub_full_run,
    _trial,
)

R_STEP = "Step aside when the book falls 10 pct and come back when it recovers"


def _method_row(conn, mid: str) -> None:
    with conn:
        store.add_method(conn, id=mid, name=f"n{mid}", family="twins", source_kind="knowledge",
                         hypothesis="h", status="registered")


def _arm(conn, mid: str, suffix: str, *, annual: float = 0.15, trades: int = 250,
         window: str = "dev", store_fp: str = "640fc25e00", curve: str | None = None) -> int:
    """Record one trial of ``mid`` and return its ``n``."""
    with conn:
        (n,) = store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-{suffix}",
            config_digest=f"d-{mid}-{suffix}-{window}", window=window, trades=trades,
            store_fingerprint=store_fp,
            curve_json=_curve(_months(*DEV_SPAN), annual) if curve is None else curve,
        )])
    return n


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    _method_row(c, "M0001")
    _method_row(c, "M0002")
    yield c
    c.close()


# ------------------------------------------------------------------ what a twin is


def test_the_same_curve_and_trades_on_one_window_is_one_book(conn):
    first = _arm(conn, "M0001", "A")
    second = _arm(conn, "M0002", "A")

    found = twins.twins_of(conn, "M0002-A")
    assert [t.candidate_id for t in found] == ["M0001-A"]
    t = twins.first_recorded(conn, "M0002-A")
    assert t is not None
    assert (t.n, t.of_n, t.method_id, t.of_method_id) == (first, second, "M0001", "M0002")
    assert t.earlier and not t.same_method and t.same_store
    assert t.book == twins.fingerprint(_curve(_months(*DEV_SPAN), 0.15))[:12]


def test_the_first_recording_sees_its_later_copy_and_knows_it_came_first(conn):
    _arm(conn, "M0001", "A")
    _arm(conn, "M0002", "A")

    t = twins.first_recorded(conn, "M0001-A")
    assert t is not None and t.candidate_id == "M0002-A"
    assert not t.earlier


def test_a_different_trade_count_is_a_different_book(conn):
    _arm(conn, "M0001", "A", trades=250)
    _arm(conn, "M0002", "A", trades=251)
    assert twins.twins_of(conn, "M0002-A") == ()
    assert twins.first_recorded(conn, "M0002-A") is None


def test_a_curve_one_byte_different_is_a_different_book(conn):
    curve = _curve(_months(*DEV_SPAN), 0.15)
    _arm(conn, "M0001", "A", curve=curve)
    _arm(conn, "M0002", "A", curve=curve[:-1] + " ]")
    assert twins.twins_of(conn, "M0002-A") == ()


def test_another_window_is_not_a_twin(conn):
    _arm(conn, "M0001", "A", window="dev")
    _arm(conn, "M0002", "A", window="test")
    assert twins.twins_of(conn, "M0002-A", "test") == ()
    assert twins.twins_of(conn, "M0001-A", "dev") == ()


def test_a_twin_across_store_fingerprints_is_a_twin_and_both_are_reported(conn):
    """The handover's own case: trial 519 on one store, its three copies on another."""
    _arm(conn, "M0001", "A", store_fp="77c37d55aa")
    _arm(conn, "M0002", "A", store_fp="640fc25ebb")

    t = twins.first_recorded(conn, "M0002-A")
    assert t is not None and not t.same_store
    assert (t.store_fingerprint, t.of_store_fingerprint) == ("77c37d55aa", "640fc25ebb")
    said = t.provenance()
    assert "store 77c37d55" in said and "this arm's store 640fc25e" in said


def test_a_trial_with_no_curve_has_no_twins(conn):
    _arm(conn, "M0001", "A", curve="[]")
    _arm(conn, "M0002", "A", curve="[]")
    assert twins.twins_of(conn, "M0002-A") == ()


def test_an_unknown_candidate_has_no_twins(conn):
    assert twins.twins_of(conn, "M9999-Z") == ()
    assert twins.first_recorded(conn, "M9999-Z") is None


def test_for_method_lists_only_arms_with_twins_in_recorded_order(conn):
    _arm(conn, "M0001", "A", annual=0.15)
    _arm(conn, "M0002", "X", annual=0.30)           # its own book
    _arm(conn, "M0002", "B", annual=0.15)           # M0001-A's book
    _arm(conn, "M0002", "C", annual=0.15)           # and again, same method
    found = twins.for_method(conn, "M0002")
    assert list(found) == ["M0002-B", "M0002-C"]
    assert [t.candidate_id for t in found["M0002-C"]] == ["M0001-A", "M0002-B"]
    assert list(twins.for_method(conn, "M0001")) == ["M0001-A"]


def test_it_reads_a_bare_read_only_connection_and_writes_nothing(tmp_path):
    """The calculate-assets path: no `store.connect`, no row factory, `mode=ro`."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method_row(c, "M0001")
    _method_row(c, "M0002")
    _arm(c, "M0001", "A")
    _arm(c, "M0002", "A")
    c.close()
    before = hashlib.sha256(db.read_bytes()).hexdigest()

    ro = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        t = twins.first_recorded(ro, "M0002-A")
        assert t is not None and t.candidate_id == "M0001-A"
        assert list(twins.for_method(ro, "M0002")) == ["M0002-A"]
    finally:
        ro.close()
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before


# ------------------------------------------------------------------ the report


def test_report_lines_name_the_first_recording_and_an_inert_treatment(conn):
    _arm(conn, "M0001", "A")                        # first recording, another method
    _arm(conn, "M0002", "NEVER")                    # this method's control
    _arm(conn, "M0002", "RECOVER")                  # the treatment, identical to it
    found = twins.for_method(conn, "M0002")
    lines = "\n".join(twins.report_lines(found, {
        "M0001-A": "treatment", "M0002-NEVER": "control", "M0002-RECOVER": "treatment",
    }))
    assert "M0002-NEVER (control) = M0001-A, first recorded (trial 1, M0001" in lines
    assert "M0002-RECOVER (treatment) = M0001-A, first recorded" in lines
    assert "own control M0002-NEVER: the treatment never acted" in lines


def test_an_unread_role_flags_nothing(conn):
    _arm(conn, "M0002", "NEVER")
    _arm(conn, "M0002", "RECOVER")
    lines = "\n".join(twins.report_lines(twins.for_method(conn, "M0002"), {}))
    assert "M0002-RECOVER = M0002-NEVER, an earlier arm of this method" in lines
    assert "never acted" not in lines


def test_the_first_recording_lists_its_later_copies(conn):
    for suffix in ("D15", "D15N", "D10", "D20", "D25"):
        _arm(conn, "M0002", suffix)
    lines = twins.report_lines({"M0002-D15": twins.twins_of(conn, "M0002-D15")}, {})
    assert lines[0].startswith("  M0002-D15 is the first recording of this book")
    assert lines[1] == "      also recorded as M0002-D15N, M0002-D10, M0002-D20 and 1 more"


# ------------------------------------------------------------------ `lab twins`


def test_lab_twins_reports_a_method_and_a_candidate_and_writes_nothing(
    tmp_path, monkeypatch, capsys
):
    _declare(monkeypatch)                            # no method files: no role labels
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method_row(c, "M0001")
    _method_row(c, "M0002")
    _arm(c, "M0001", "A")
    _arm(c, "M0002", "A")
    _arm(c, "M0002", "OWN", annual=0.30)
    c.close()
    before = hashlib.sha256(db.read_bytes()).hexdigest()

    args = argparse.Namespace(db=db, lab_command="twins", ids=["M0002", "M0001-A"], window="dev")
    assert lab_cmd.run(args) == 0
    out = capsys.readouterr().out
    assert "M0002 (2 dev arms): 1 arm(s) are a book the lab already holds" in out
    assert "M0002-A = M0001-A, first recorded (trial 1, M0001" in out
    assert "M0001-A: 1 arm(s) are a book the lab already holds" in out
    assert "M0001-A is the first recording of this book" in out
    assert "Nothing was written" in out
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before


def test_lab_twins_says_none_for_an_arm_with_no_twin(tmp_path, monkeypatch, capsys):
    _declare(monkeypatch)
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method_row(c, "M0001")
    _arm(c, "M0001", "A")
    c.close()
    args = argparse.Namespace(db=db, lab_command="twins", ids=["M0001"], window="dev")
    assert lab_cmd.run(args) == 0
    assert "M0001 (1 dev arm): no other dev trial holds the same book" in capsys.readouterr().out


def test_lab_twins_refuses_an_id_it_cannot_find_rather_than_reading_clean(tmp_path):
    """"No twins" for a typo would be a false all-clear -- the failure `lab control` was caught in."""
    db = tmp_path / "lab.sqlite"
    store.connect(db).close()
    args = argparse.Namespace(db=db, lab_command="twins", ids=["M0001-TYPO"], window="dev")
    assert lab_cmd.run(args) == 2


# ------------------------------------------------------------------ `lab run` prints them (D15)


def test_lab_run_names_the_first_recording_and_still_exits_zero(tmp_path, monkeypatch, capsys):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method_row(c, "M0001")
    _method_row(c, "M0099")
    _arm(c, "M0001", "A")                            # recorded first, by another method
    _arm(c, "M0099", "NEVER")                        # this run's control: the same book
    _arm(c, "M0099", "RECOVER")                      # this run's treatment: the same book again
    c.close()

    _stub_full_run(monkeypatch, tmp_path, "M0099",
                   [_Arm("M0099-NEVER", R_DRAW), _Arm("M0099-RECOVER", R_STEP)])
    assert lab_cmd.run(argparse.Namespace(
        db=db, lab_command="run", method="M0099", store=tmp_path / "store", allow_coverage=0.8,
    )) == 0
    out = capsys.readouterr().out
    block = out.split("Book twins:")[1]
    assert "2 arm(s) of M0099" in block
    assert "M0099-NEVER (control) = M0001-A, first recorded" in block
    assert "own control M0099-NEVER: the treatment never acted" in block
    assert "lab twins M0099" in block and "D19" in block


def test_lab_run_says_none_when_no_arm_repeats_a_book(tmp_path, monkeypatch, capsys):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method_row(c, "M0099")
    _arm(c, "M0099", "A", annual=0.15)
    _arm(c, "M0099", "B", annual=0.20)
    c.close()

    _stub_full_run(monkeypatch, tmp_path, "M0099",
                   [_Arm("M0099-A", R_IDEA), _Arm("M0099-B", R_STEP)])
    assert lab_cmd.run(argparse.Namespace(
        db=db, lab_command="run", method="M0099", store=tmp_path / "store", allow_coverage=0.8,
    )) == 0
    assert "Book twins: none." in capsys.readouterr().out


# ------------------------------------------------------------------ `lab status` tags


def test_lab_status_tags_role_and_first_recorded_twin(tmp_path, monkeypatch, capsys):
    """Both lists rank raw trial rows; before this, a copy read as a fresh near miss."""
    monkeypatch.setattr(store, "DSR_POLICY", "all-trials")
    store._GATE_CACHE.clear()
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method_row(c, "M0001")
    _method_row(c, "M0002")
    _arm(c, "M0001", "A")
    _arm(c, "M0002", "A")
    c.close()
    _declare(monkeypatch, M0001=[_Arm("M0001-A", R_IDEA)], M0002=[_Arm("M0002-A", R_DRAW)])

    assert lab_cmd.run(argparse.Namespace(db=db, lab_command="status")) == 0
    out = capsys.readouterr().out
    store._GATE_CACHE.clear()
    near = out.split("Near misses")[1].split("Closest to eligible")[0]
    line_b = next(ln for ln in near.splitlines() if ln.strip().startswith("M0002-A"))
    line_a = next(ln for ln in near.splitlines() if ln.strip().startswith("M0001-A"))
    assert line_b.endswith("[control; = M0001-A]")
    assert line_a.endswith("[idea; first of 2]")


# ------------------------------------------------------------------ the committed lab, read-only


def _committed_ro():
    if not store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    return sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)


def test_the_handovers_book_was_first_recorded_as_m0125_dv_c10():
    """Trial 519, on another store, before the three wrappers that re-recorded it."""
    before = hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest() \
        if store.COMMITTED_DB.exists() else None
    ro = _committed_ro()
    try:
        if ro.execute("SELECT 1 FROM trials WHERE candidate_id = 'M0488-DVC10-NEVER'").fetchone() is None:
            pytest.skip("M0488 is not in this tree's lab")
        t = twins.first_recorded(ro, "M0488-DVC10-NEVER")
        assert t is not None
        assert (t.candidate_id, t.method_id, t.n) == ("M0125-DV-C10", "M0125", 519)
        assert t.earlier and not t.same_store
        assert t.store_fingerprint.startswith("77c37d55")
        assert t.of_store_fingerprint.startswith("640fc25e")
        names = [x.candidate_id for x in twins.twins_of(ro, "M0488-DVC10-NEVER")]
        assert names[:5] == ["M0125-DV-C10", "M0442-DVC10-NEVER", "M0447-DVC10-NEVER",
                             "M0447-DVC10-RECOVER", "M0447-DVC10-RECOVER-CAP730"]
        fixed = twins.first_recorded(ro, "M0488-DVC10-FIXED730")
        assert fixed is not None and fixed.candidate_id == "M0442-DVC10-FIXED730"
    finally:
        ro.close()
    assert hashlib.sha256(store.COMMITTED_DB.read_bytes()).hexdigest() == before

# ------------------------------------------------------- lab idea lists recorded controls


def _idea_args(db) -> argparse.Namespace:
    return argparse.Namespace(
        db=db, lab_command="idea", name="A dead zone on the drawdown brake",
        family="drawdown-brake",
        hypothesis="Trim the book in proportion to its fall below its own high, ignoring small falls",
        source_kind="knowledge", source_ref="", parent=None,
    )


def _idea_lab(tmp_path, monkeypatch, *, roles, extra=None):
    """A lab with M0001 (the neighbour) and the arms recorded by ``extra(c)``."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    with c:
        store.add_method(c, id="M0001", name="A brake on the account's own fall",
                         family="drawdown-brake", source_kind="knowledge",
                         hypothesis="Trim in proportion to how far the book is below its own high",
                         status="registered")
    if extra:
        extra(c)
    c.close()
    monkeypatch.setattr(lab_cmd, "_roles", lambda ids: roles)
    return db


def test_lab_idea_lists_a_neighbours_control_by_its_first_recording(tmp_path, monkeypatch, capsys):
    def extra(c):
        _arm(c, "M0001", "CTRL")

    db = _idea_lab(tmp_path, monkeypatch, roles={("M0001", "M0001-CTRL"): "control"}, extra=extra)
    assert lab_cmd.run(_idea_args(db)) == 0
    got = capsys.readouterr()
    assert got.out == "M0002\n"
    assert "  M0001-CTRL  trial 1, M0001, MONTHLY_HOLD/TIMING, " in got.err


def test_a_control_that_copies_an_earlier_book_is_named_by_the_earlier_one_once(
    tmp_path, monkeypatch, capsys
):
    def extra(c):
        _method_row(c, "M0009")
        _arm(c, "M0009", "FIRST")            # n=1, the first recording
        _arm(c, "M0001", "CTRL")             # n=2, same curve and trades

    db = _idea_lab(tmp_path, monkeypatch, roles={("M0001", "M0001-CTRL"): "control"}, extra=extra)
    lab_cmd.run(_idea_args(db))
    err = capsys.readouterr().err
    assert err.count("M0009-FIRST") == 1 and "M0001-CTRL  trial" not in err


def test_the_store_of_the_newest_trial_decides_current_versus_older(tmp_path, monkeypatch, capsys):
    def extra(c):
        _arm(c, "M0001", "OLD", annual=0.10, store_fp="aaaaaaaa00")
        _arm(c, "M0001", "NEW", annual=0.20, store_fp="640fc25e00")

    roles = {("M0001", "M0001-OLD"): "control", ("M0001", "M0001-NEW"): "control"}
    db = _idea_lab(tmp_path, monkeypatch, roles=roles, extra=extra)
    lab_cmd.run(_idea_args(db))
    err = capsys.readouterr().err
    assert "M0001-OLD  trial 1, M0001, MONTHLY_HOLD/TIMING, older store only" in err
    assert "M0001-NEW  trial 2, M0001, MONTHLY_HOLD/TIMING, current store" in err


def test_unreadable_controls_never_fail_the_reservation_and_write_nothing_more(
    tmp_path, monkeypatch, capsys
):
    db = _idea_lab(tmp_path, monkeypatch, roles={})
    monkeypatch.setattr(lab_cmd, "_roles", lambda ids: (_ for _ in ()).throw(RuntimeError("boom")))
    before = store.connect(db).execute("SELECT count(*) FROM trials").fetchone()[0]
    assert lab_cmd.run(_idea_args(db)) == 0
    got = capsys.readouterr()
    assert got.out == "M0002\n" and "Recorded controls: not read (boom)" in got.err
    c = store.connect(db)
    assert c.execute("SELECT count(*) FROM trials").fetchone()[0] == before
    assert c.execute("SELECT status FROM methods WHERE id = 'M0002'").fetchone()[0] == "idea"
