"""`lab unblock`: the missing data arrived (EODHD plan set, phase 3, R9)."""

from __future__ import annotations

import argparse

from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import store


def _lab(tmp_path):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    with c:
        store.add_method(
            c, id="M0001", name="VIX gate", family="regime", source_kind="knowledge", hypothesis="h"
        )
    c.close()
    return db


def _run(db, command, **kw):
    return lab_cmd.run(argparse.Namespace(db=db, lab_command=command, **kw))


def _row(db, mid="M0001"):
    c = store.connect(db)
    try:
        return dict(store.get_method(c, mid))
    finally:
        c.close()


def test_unblock_moves_a_blocked_idea_back_and_keeps_why_it_was_blocked(tmp_path):
    db = _lab(tmp_path)
    assert _run(db, "block", method="M0001", on="CBOE VIX3M daily closes") == 0
    assert _row(db)["status"] == "blocked-data"

    assert _run(db, "unblock", method="M0001", note="Covers 46.8% of the dev window.") == 0

    row = _row(db)
    assert row["status"] == "idea"
    assert row["blocked_on"] == ""
    assert "Unblocked: the missing data arrived. Covers 46.8% of the dev window." in row["analysis"]
    assert "It was blocked on: CBOE VIX3M daily closes" in row["analysis"]


def test_unblock_refuses_a_method_that_is_not_blocked(tmp_path):
    db = _lab(tmp_path)
    assert _run(db, "unblock", method="M0001", note="n") == 2
    row = _row(db)
    assert row["status"] == "idea"
    assert row["analysis"] == ""


def test_unblock_refuses_an_empty_note_and_an_unknown_method(tmp_path):
    db = _lab(tmp_path)
    assert _run(db, "block", method="M0001", on="x") == 0
    assert _run(db, "unblock", method="M0001", note="   ") == 2
    assert _row(db)["status"] == "blocked-data"
    assert _run(db, "unblock", method="M0099", note="n") == 2
