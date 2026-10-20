"""``lab insight --supersedes`` and ``lab link``: the journal's two ways to say "this replaces
that".

Both write one column through the store, so what these tests really pin is the **exit code**.
The lab's contract is 0 ok, 2 the lab's rules refused, 1 something broke. Phase 6's backfill
reads that contract to tell "I asked the journal for something it forbids" from "the tool is
broken", and a refusal that leaked out as 1 -- a bare ``sqlite3.IntegrityError`` from the
one-successor index, say -- would look like the second. So every refusal below asserts **2**,
and then re-reads the row to prove nothing moved.

The happy paths assert the stored value, never which store function stored it: ``lab insight
--supersedes`` may link on the insert or immediately after it, and both are correct."""

from __future__ import annotations

import argparse

from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import store


def _lab(tmp_path):
    """Two methods, so the "a link may not cross methods" case has somewhere to cross to."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    with c:
        store.add_method(
            c, id="M0001", name="VIX gate", family="regime", source_kind="knowledge",
            hypothesis="h",
        )
        store.add_method(
            c, id="M0002", name="Dividend hold", family="income", source_kind="knowledge",
            hypothesis="h",
        )
    c.close()
    return db


def _run(db, command, **kw):
    return lab_cmd.run(argparse.Namespace(db=db, lab_command=command, **kw))


def _insight(db, *, title, body, method=None, doc_key=None, supersedes=None, kind="observation"):
    return _run(
        db, "insight", kind=kind, title=title, body=body, file=None, method=method,
        doc_key=doc_key, supersedes=supersedes,
    )


def _rows(db):
    c = store.connect(db)
    try:
        return {int(r["id"]): dict(r) for r in c.execute("SELECT * FROM insights ORDER BY id")}
    finally:
        c.close()


def _two(db, method="M0001"):
    """Two unlinked entries under one method: 1 the older, 2 the newer."""
    assert _insight(db, title="what the fees did", body="first reading", method=method) == 0
    assert _insight(db, title="what the fees did", body="second reading", method=method) == 0
    ids = sorted(_rows(db))
    assert len(ids) == 2
    return ids


# ---- lab insight --------------------------------------------------------------------------

def test_insight_without_the_new_flags_is_unchanged(tmp_path):
    db = _lab(tmp_path)
    assert _insight(db, title="a thought", body="a body", method="M0001") == 0
    row = _rows(db)[1]
    assert row["title"] == "a thought"
    assert row["body"] == "a body"
    assert row["supersedes"] is None
    assert row["doc_key"] is None


def test_insight_stores_a_doc_key(tmp_path):
    db = _lab(tmp_path)
    assert _insight(db, title="t", body="b", method="M0001", doc_key="real-costs:M0001-N20") == 0
    assert _rows(db)[1]["doc_key"] == "real-costs:M0001-N20"


def test_insight_supersedes_links_the_new_entry_and_leaves_the_old_one_whole(tmp_path):
    db = _lab(tmp_path)
    assert _insight(db, title="what the fees did", body="first reading", method="M0001") == 0
    before = _rows(db)[1]

    assert _insight(db, title="what the fees did", body="a better reading", method="M0001",
                    supersedes=1) == 0

    rows = _rows(db)
    assert rows[2]["supersedes"] == 1
    assert rows[1] == before, "the superseded entry must not change in any column"


def test_insight_supersedes_a_missing_entry_is_refused_and_writes_nothing(tmp_path):
    db = _lab(tmp_path)
    assert _insight(db, title="t", body="b", method="M0001", supersedes=99) == 2
    assert _rows(db) == {}, "a refused link must not leave the new entry behind"


def test_insight_still_demands_exactly_one_of_body_and_file(tmp_path):
    db = _lab(tmp_path)
    assert _run(db, "insight", kind="observation", title="t", body=None, file=None,
                method=None, doc_key=None, supersedes=None) == 2
    assert _run(db, "insight", kind="observation", title="t", body="b",
                file=tmp_path / "b.txt", method=None, doc_key=None, supersedes=None) == 2
    assert _rows(db) == {}


# ---- lab link -----------------------------------------------------------------------------

def test_link_threads_an_entry_already_written(tmp_path):
    db = _lab(tmp_path)
    older, newer = _two(db)
    before = _rows(db)[older]

    assert _run(db, "link", insight=newer, supersedes=older) == 0

    rows = _rows(db)
    assert rows[newer]["supersedes"] == older
    assert rows[older] == before


def test_link_builds_a_chain_of_three(tmp_path):
    """320 -> 499 -> 500, the shape phase 6 backfills, in id order."""
    db = _lab(tmp_path)
    for body in ("first", "second", "third"):
        assert _insight(db, title="the same note", body=body, method="M0001") == 0

    assert _run(db, "link", insight=2, supersedes=1) == 0
    assert _run(db, "link", insight=3, supersedes=2) == 0

    rows = _rows(db)
    assert [rows[i]["supersedes"] for i in (1, 2, 3)] == [None, 1, 2]


def test_link_refuses_a_missing_entry(tmp_path):
    db = _lab(tmp_path)
    older, _newer = _two(db)
    assert _run(db, "link", insight=99, supersedes=older) == 2
    assert all(r["supersedes"] is None for r in _rows(db).values())


def test_link_refuses_a_missing_predecessor(tmp_path):
    db = _lab(tmp_path)
    _older, newer = _two(db)
    assert _run(db, "link", insight=newer, supersedes=99) == 2
    assert _rows(db)[newer]["supersedes"] is None


def test_link_refuses_a_predecessor_at_or_above_the_entry(tmp_path):
    """A journal reads forward. A link that points forward would make the chain a cycle or a
    fork in time, and the version number unresolvable."""
    db = _lab(tmp_path)
    older, newer = _two(db)
    assert _run(db, "link", insight=older, supersedes=newer) == 2
    assert all(r["supersedes"] is None for r in _rows(db).values())


def test_link_refuses_an_entry_superseding_itself(tmp_path):
    db = _lab(tmp_path)
    _older, newer = _two(db)
    assert _run(db, "link", insight=newer, supersedes=newer) == 2
    assert _rows(db)[newer]["supersedes"] is None


def test_link_refuses_a_predecessor_that_already_has_a_successor(tmp_path):
    """One predecessor, one successor: a fork has no version number.

    This is the cross-phase check. If it returns 1 rather than 2, the refusal escaped as a bare
    ``sqlite3.IntegrityError`` from ``insights_one_successor`` instead of as a ``LabError`` from
    ``store.set_supersedes``, and the fix belongs in phase 1's store, not in the CLI."""
    db = _lab(tmp_path)
    assert _insight(db, title="t", body="first", method="M0001") == 0
    assert _insight(db, title="t", body="second", method="M0001") == 0
    assert _insight(db, title="t", body="third", method="M0001") == 0
    assert _run(db, "link", insight=2, supersedes=1) == 0

    assert _run(db, "link", insight=3, supersedes=1) == 2

    rows = _rows(db)
    assert rows[2]["supersedes"] == 1
    assert rows[3]["supersedes"] is None


def test_link_refuses_an_entry_that_is_already_linked(tmp_path):
    """Once set, the link is frozen -- it cannot be moved to a different predecessor."""
    db = _lab(tmp_path)
    assert _insight(db, title="t", body="first", method="M0001") == 0
    assert _insight(db, title="t", body="second", method="M0001") == 0
    assert _insight(db, title="t", body="third", method="M0001") == 0
    assert _run(db, "link", insight=3, supersedes=2) == 0

    assert _run(db, "link", insight=3, supersedes=1) == 2

    assert _rows(db)[3]["supersedes"] == 2


def test_link_refuses_crossing_methods(tmp_path):
    """A version of a note about M0001 cannot be a note about M0002."""
    db = _lab(tmp_path)
    assert _insight(db, title="t", body="first", method="M0001") == 0
    assert _insight(db, title="t", body="second", method="M0002") == 0

    assert _run(db, "link", insight=2, supersedes=1) == 2

    assert _rows(db)[2]["supersedes"] is None


def test_link_is_registered_in_the_dispatch_table(tmp_path):
    """The parser and the handler table are edited separately; a subcommand that parses and then
    dies on a KeyError exits 1, which phase 6 would read as a broken tool."""
    assert "link" in lab_cmd._HANDLERS
