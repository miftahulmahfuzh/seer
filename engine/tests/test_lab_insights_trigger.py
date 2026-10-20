"""The narrowed ``insights_no_update`` (JOURNAL_VERSIONING_PLAN.md, phase 1).

Schema 8 lets one column of one table move, exactly once: ``insights.supersedes``, from NULL to
the id of the row this one replaces. Nothing else about the lab journal moves, and that is the
whole of what this module exists to prove.

Why it gets its own file rather than a few more cases in ``test_lab_store.py``: before schema 8
the rule was one line of SQL -- *abort every UPDATE* -- and one assertion was an honest test of
it. A whitelist is a list, and a list is only as good as the enumeration of what is *not* on it.
This trigger is now the only thing standing between the lab and a rewritten prediction: the
append-only rule exists so that nobody, the owner included, can quietly change what a method said
*before* a run after seeing how the run turned out. So every protected column gets its own named
test, every one of them re-reads the row afterwards (an UPDATE that aborted halfway and left the
row changed would still be a catastrophe, and "it raised" does not prove it did not), and the
multi-column case -- ``SET supersedes = ?, body = ?`` -- gets a test of its own because that is
the exact trap the owner named when he chose this design: the permitted column must not be able
to smuggle a forbidden one through in the same statement.

``test_an_update_to_body_still_aborts`` is the single most important test in this change.
"""

from __future__ import annotations

import sqlite3

import pytest

from seer_engine.lab import store

ADDED = "2026-10-20T00:00:00+00:00"


@pytest.fixture()
def conn(tmp_path):
    """A lab with one method and four journal entries, ids 1-4, every ``supersedes`` NULL.

    Entries 1-3 belong to M0001 and 4 to no method, so the method_id invariant has both shapes to
    be tested against.
    """
    c = store.connect(tmp_path / "lab.sqlite")
    with c:
        store.add_method(c, id="M0001", name="n", family="f", source_kind="knowledge",
                         hypothesis="h", status="idea")
        store.add_method(c, id="M0002", name="n2", family="f", source_kind="knowledge",
                         hypothesis="h", status="idea")
        for i in (1, 2, 3):
            store.add_insight(c, kind="observation", title=f"t{i}", body=f"b{i}", method_id="M0001")
        store.add_insight(c, kind="risk", title="t4", body="b4")
    yield c
    c.close()


def _row(conn, insight_id: int) -> tuple:
    return tuple(conn.execute(
        "SELECT id, kind, title, body, method_id, added, supersedes, doc_key "
        "FROM insights WHERE id = ?", (insight_id,)
    ).fetchone())


def _aborts(conn, sql: str, args: tuple = (), *, row_id: int = 1) -> None:
    """``sql`` aborts, and row ``row_id`` is byte-identical afterwards.

    The second half is the one that is easy to leave out and is not optional: a BEFORE UPDATE
    trigger that raised after half a statement had landed would still be a rewritten journal.
    """
    before = _row(conn, row_id)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute(sql, args)
    conn.rollback()
    assert _row(conn, row_id) == before


# --------------------------------------------------------------- the protected columns


def test_an_update_to_body_still_aborts(conn):
    """The single most important test in this change.

    If this ever goes green-to-red the lab has lost the property it was built on, and no feature
    in this plan set is worth that.
    """
    _aborts(conn, "UPDATE insights SET body = 'rewritten' WHERE id = 1")


def test_an_update_to_kind_aborts(conn):
    _aborts(conn, "UPDATE insights SET kind = 'risk' WHERE id = 1")


def test_an_update_to_title_aborts(conn):
    _aborts(conn, "UPDATE insights SET title = 'rewritten' WHERE id = 1")


def test_an_update_to_method_id_aborts(conn):
    _aborts(conn, "UPDATE insights SET method_id = 'M0002' WHERE id = 1")


def test_an_update_to_method_id_from_a_value_to_null_aborts(conn):
    """``IS NOT`` is SQLite's null-safe distinct operator, so a column going to NULL is caught
    where plain ``<>`` would have compared NULL and yielded NULL -- not true, not an abort."""
    _aborts(conn, "UPDATE insights SET method_id = NULL WHERE id = 1")


def test_an_update_to_method_id_from_null_to_a_value_aborts(conn):
    """The mirror of the case above, on the row that has no method: NULL -> value is a rewrite
    too. An unmethodded observation must not be able to acquire a method after the fact."""
    _aborts(conn, "UPDATE insights SET method_id = 'M0001' WHERE id = 4", row_id=4)


def test_an_update_to_added_aborts(conn):
    _aborts(conn, "UPDATE insights SET added = '2020-01-01T00:00:00+00:00' WHERE id = 1")


def test_an_update_to_id_aborts(conn):
    """The id is in the whitelist's protected list for a reason: re-keying a row moves what every
    ``supersedes`` link, every seen-state record and every rendered permalink points at."""
    _aborts(conn, "UPDATE insights SET id = 99 WHERE id = 1")


def test_an_update_to_doc_key_aborts(conn):
    """Decision: ``doc_key`` is protected like content. The owner permitted exactly one column to
    change, ``supersedes``; a column added in the same migration is not a new permission."""
    _aborts(conn, "UPDATE insights SET doc_key = 'real-costs:M0001-A' WHERE id = 1")


def test_a_delete_still_aborts(conn):
    before = _row(conn, 1)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM insights WHERE id = 1")
    conn.rollback()
    assert _row(conn, 1) == before
    assert conn.execute("SELECT count(*) FROM insights").fetchone()[0] == 4


# --------------------------------------------------------------- the one permitted move


def test_supersedes_null_to_a_value_succeeds_once(conn):
    """The whole point of schema 8, and the only test in this module that is red before Step 3
    and green after it."""
    with conn:
        conn.execute("UPDATE insights SET supersedes = 1 WHERE id = 2")
    assert _row(conn, 2)[6] == 1
    # ...and the rest of the row did not move.
    assert _row(conn, 2)[:6] == (2, "observation", "t2", "b2", "M0001", _row(conn, 2)[5])


def test_supersedes_value_to_a_different_value_aborts(conn):
    with conn:
        conn.execute("UPDATE insights SET supersedes = 1 WHERE id = 3")
    _aborts(conn, "UPDATE insights SET supersedes = 2 WHERE id = 3", row_id=3)


def test_supersedes_value_to_null_aborts(conn):
    """Once set, the link is frozen in both directions: a successor cannot be unlinked either."""
    with conn:
        conn.execute("UPDATE insights SET supersedes = 1 WHERE id = 3")
    _aborts(conn, "UPDATE insights SET supersedes = NULL WHERE id = 3", row_id=3)


def test_supersedes_and_body_in_one_statement_aborts_and_leaves_supersedes_null(conn):
    """The trap the owner named: the permitted column must not smuggle a forbidden one through.

    ``_aborts`` already re-reads the whole row, which covers ``supersedes`` still being NULL, but
    that clause is asserted again by name here because it is the specific thing that was asked
    for and a reader of this file should not have to infer it.
    """
    _aborts(conn, "UPDATE insights SET supersedes = 1, body = 'rewritten' WHERE id = 2", row_id=2)
    assert _row(conn, 2)[6] is None
    assert _row(conn, 2)[3] == "b2"


def test_supersedes_and_title_in_one_statement_aborts(conn):
    _aborts(conn, "UPDATE insights SET supersedes = 1, title = 'rewritten' WHERE id = 2", row_id=2)
    assert _row(conn, 2)[6] is None


def test_supersedes_and_doc_key_in_one_statement_aborts(conn):
    """``doc_key`` is the column most likely to be mistaken for "also fine to set later", so the
    smuggling case is tested for it specifically and not only for the obvious content columns."""
    _aborts(conn, "UPDATE insights SET supersedes = 1, doc_key = 'k' WHERE id = 2", row_id=2)
    assert _row(conn, 2)[6] is None


def test_two_rows_cannot_supersede_the_same_predecessor(conn):
    """``insights_one_successor``. A predecessor with two successors is a fork, and a fork has no
    single "latest version" to render -- the reader would have to choose one and hide a
    measurement, which is the failure this whole plan exists to avoid."""
    with conn:
        conn.execute("UPDATE insights SET supersedes = 1 WHERE id = 2")
    before = _row(conn, 3)
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        conn.execute("UPDATE insights SET supersedes = 1 WHERE id = 3")
    conn.rollback()
    assert _row(conn, 3) == before


def test_many_rows_may_have_a_null_supersedes(conn):
    """The index is partial (``WHERE supersedes IS NOT NULL``), so "unlinked" is not a value that
    collides. All four fixture rows are unlinked and a fifth may be added."""
    with conn:
        store.add_insight(conn, kind="observation", title="t5", body="b5")
    assert conn.execute("SELECT count(*) FROM insights WHERE supersedes IS NULL").fetchone()[0] == 5


def test_a_chain_of_three_is_allowed(conn):
    """One successor per row, not one link per chain: 1 <- 2 <- 3 is how "version 3" is stored."""
    with conn:
        conn.execute("UPDATE insights SET supersedes = 1 WHERE id = 2")
        conn.execute("UPDATE insights SET supersedes = 2 WHERE id = 3")
    # ``store.connect`` sets ``row_factory = sqlite3.Row``, so the rows are tupled to compare --
    # the same reason ``_row`` above does it.
    assert [tuple(r) for r in conn.execute(
        "SELECT id, supersedes FROM insights WHERE supersedes IS NOT NULL ORDER BY id"
    )] == [(2, 1), (3, 2)]


def test_a_backwards_link_is_refused_by_sql_as_well_as_by_python(conn):
    """``CHECK (supersedes IS NULL OR supersedes < id)`` makes a cycle impossible by construction,
    self-reference included -- a successor is always a later row than what it replaces. The
    friendly path is ``set_supersedes``'s LabError (tested below); this is the floor under it, and
    it is what protects the invariant from a future caller that writes SQL directly."""
    for sql in (
        "UPDATE insights SET supersedes = 3 WHERE id = 2",   # forwards
        "UPDATE insights SET supersedes = 2 WHERE id = 2",   # itself
    ):
        before = _row(conn, 2)
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            conn.execute(sql)
        conn.rollback()
        assert _row(conn, 2) == before


# --------------------------------------------------------------- store.set_supersedes


def test_set_supersedes_links_a_row_and_is_the_one_permitted_update(conn):
    with conn:
        store.set_supersedes(conn, 2, 1)
    assert store.get_insight(conn, 2)["supersedes"] == 1
    assert _row(conn, 1) == (1, "observation", "t1", "b1", "M0001", _row(conn, 1)[5], None, None)


def test_set_supersedes_refuses_a_missing_predecessor(conn):
    with pytest.raises(store.LabError, match="no insight 404"):
        store.set_supersedes(conn, 2, 404)
    assert store.get_insight(conn, 2)["supersedes"] is None


def test_set_supersedes_refuses_a_missing_successor(conn):
    with pytest.raises(store.LabError, match="no insight 404"):
        store.set_supersedes(conn, 404, 1)


def test_set_supersedes_refuses_itself_and_a_later_predecessor(conn):
    with pytest.raises(store.LabError, match="earlier"):
        store.set_supersedes(conn, 2, 2)
    with pytest.raises(store.LabError, match="earlier"):
        store.set_supersedes(conn, 2, 3)
    assert store.get_insight(conn, 2)["supersedes"] is None


def test_set_supersedes_refuses_a_second_successor(conn):
    with conn:
        store.set_supersedes(conn, 2, 1)
    with pytest.raises(store.LabError, match="already superseded"):
        store.set_supersedes(conn, 3, 1)
    assert store.get_insight(conn, 3)["supersedes"] is None


def test_set_supersedes_refuses_relinking_a_row_that_is_already_linked(conn):
    with conn:
        store.set_supersedes(conn, 3, 1)
    with pytest.raises(store.LabError, match="already supersedes"):
        store.set_supersedes(conn, 3, 2)
    assert store.get_insight(conn, 3)["supersedes"] == 1


def test_set_supersedes_refuses_crossing_method_id(conn):
    """A version of a note about M0001 is still about M0001. Crossing methods is not a new
    version, it is a different document, and the reader would merge two subjects into one card."""
    with pytest.raises(store.LabError, match="method"):
        store.set_supersedes(conn, 4, 1)          # 4 has no method, 1 is M0001
    with conn:
        store.add_insight(conn, kind="observation", title="t5", body="b5", method_id="M0002")
    with pytest.raises(store.LabError, match="method"):
        store.set_supersedes(conn, 5, 1)          # M0002 superseding M0001
    assert store.get_insight(conn, 4)["supersedes"] is None
    assert store.get_insight(conn, 5)["supersedes"] is None


def test_set_supersedes_allows_two_unmethodded_rows(conn):
    """"Both NULL counts as shared": two journal entries that belong to no method may be threaded."""
    with conn:
        store.add_insight(conn, kind="risk", title="t5", body="b5")
    with conn:
        store.set_supersedes(conn, 5, 4)
    assert store.get_insight(conn, 5)["supersedes"] == 4


def test_kind_may_change_along_a_chain(conn):
    """Deliberate: a hypothesis that has been measured becomes an observation, and the lab should
    be able to say so by superseding rather than by leaving two cards that disagree."""
    with conn:
        n = store.add_insight(conn, kind="synthesis", title="t5", body="b5", method_id="M0001")
        store.set_supersedes(conn, n, 1)
    assert store.get_insight(conn, n)["kind"] == "synthesis"
    assert store.get_insight(conn, 1)["kind"] == "observation"


# --------------------------------------------------------------- store.add_insight


def test_add_insight_links_at_birth(conn):
    with conn:
        n = store.add_insight(conn, kind="observation", title="t5", body="b5",
                              method_id="M0001", doc_key="real-costs:M0001-A", supersedes=1)
    row = store.get_insight(conn, n)
    assert (row["supersedes"], row["doc_key"]) == (1, "real-costs:M0001-A")


def test_add_insight_without_the_new_arguments_writes_nulls(conn):
    """Every caller that predates schema 8 keeps working and keeps writing an unlinked row."""
    with conn:
        n = store.add_insight(conn, kind="observation", title="t5", body="b5")
    row = store.get_insight(conn, n)
    assert (row["supersedes"], row["doc_key"]) == (None, None)


def test_add_insight_validates_supersedes_before_it_inserts(conn):
    """A refused link must not leave a half-written journal entry behind."""
    for bad, match in ((404, "no insight 404"), (1, "method")):
        with pytest.raises(store.LabError, match=match):
            store.add_insight(conn, kind="observation", title="t5", body="b5", supersedes=bad)
    assert conn.execute("SELECT count(*) FROM insights").fetchone()[0] == 4


def test_add_insight_refuses_a_second_successor(conn):
    with conn:
        store.add_insight(conn, kind="observation", title="t5", body="b5",
                          method_id="M0001", supersedes=1)
    with pytest.raises(store.LabError, match="already superseded"):
        store.add_insight(conn, kind="observation", title="t6", body="b6",
                          method_id="M0001", supersedes=1)
    assert conn.execute("SELECT count(*) FROM insights").fetchone()[0] == 5


def test_add_insight_refuses_a_blank_doc_key(conn):
    with pytest.raises(store.LabError, match="doc_key"):
        store.add_insight(conn, kind="observation", title="t5", body="b5", doc_key="   ")
    assert conn.execute("SELECT count(*) FROM insights").fetchone()[0] == 4


def test_head_for_doc_key_finds_the_unsuperseded_row(conn):
    """Phase 3's affordance: the row to supersede is the one with this key that nothing replaces.

    Three versions of one document, and the answer is always the newest -- never the first, and
    never a row carrying a different key.
    """
    assert store.head_for_doc_key(conn, "real-costs:M0001-A") is None
    with conn:
        a = store.add_insight(conn, kind="observation", title="t5", body="b5",
                              method_id="M0001", doc_key="real-costs:M0001-A")
        other = store.add_insight(conn, kind="observation", title="t6", body="b6",
                                  method_id="M0001", doc_key="real-costs:M0001-B")
    assert store.head_for_doc_key(conn, "real-costs:M0001-A")["id"] == a
    with conn:
        b = store.add_insight(conn, kind="observation", title="t7", body="b7",
                              method_id="M0001", doc_key="real-costs:M0001-A", supersedes=a)
    assert store.head_for_doc_key(conn, "real-costs:M0001-A")["id"] == b
    assert store.head_for_doc_key(conn, "real-costs:M0001-B")["id"] == other


def test_head_for_doc_key_ignores_rows_with_no_key(conn):
    """The 500 rows that predate schema 8 all carry a NULL ``doc_key``; none of them is the head
    of anything, and ``head_for_doc_key(conn, None)`` is not a question that has an answer."""
    assert store.head_for_doc_key(conn, "") is None
    assert store.head_for_doc_key(conn, "   ") is None
