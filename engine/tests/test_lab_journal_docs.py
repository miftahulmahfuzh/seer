"""Journal documents: what a `doc_key` is, and the M0260 incident that defines it.

The headline test here is `test_m0260s_three_arms_stay_three_documents`. Insights 466, 467 and 468
in the committed lab share one generated title, were written 25 and 30 seconds apart, and are NOT
duplicates: they are M0260-M-NATIVE, M0260-M-G12 and M0260-M-G3, matched to trials n=835, 838 and
836 by their recorded max drawdown and profit factor. An auto-linker keyed on the method or on the
title would have buried a 23.8% drawdown underneath a 33.6% one and shown the owner only the last.
"""

from __future__ import annotations

from datetime import date

import pytest

from seer_engine.lab import journal_docs, real_costs, store
from seer_engine.lab.seed import seed


@pytest.fixture()
def lab(tmp_path):
    path = tmp_path / "lab.sqlite"
    conn = store.connect(path)
    seed(conn)
    with conn:
        store.add_method(
            conn, id="M0001", name="one method, three arms", family="trend",
            source_kind="knowledge", hypothesis="h",
        )
    yield conn
    conn.close()


def _write(conn, key, body="a body", *, supersede=True, method_id="M0001"):
    with conn:
        return journal_docs.append(
            conn, kind="observation", title="a title", body=body,
            method_id=method_id, key=key, supersede=supersede,
        )


def _row(conn, insight_id):
    return conn.execute("SELECT * FROM insights WHERE id = ?", (insight_id,)).fetchone()


# ---- the key ------------------------------------------------------------------------------


def test_an_unnarrowed_run_is_keyed_on_the_method():
    assert journal_docs.doc_key("gate", "M0260") == "gate:M0260:all"


def test_a_narrowed_run_is_keyed_on_the_arms_it_measured():
    assert journal_docs.doc_key("gate", "M0260", ["M0260-M-G3"]) == "gate:M0260:M0260-M-G3"


def test_the_arm_list_is_sorted_and_deduplicated_so_order_is_not_identity():
    a = journal_docs.doc_key("exposure", "M0260", ["M0260-B", "M0260-A"])
    b = journal_docs.doc_key("exposure", "M0260", ["M0260-A", "M0260-B", "M0260-A"])
    assert a == b == "exposure:M0260:M0260-A+M0260-B"


def test_a_narrowed_run_with_no_arms_is_a_refusal_not_a_method_wide_key():
    with pytest.raises(store.LabError, match="at least one candidate id"):
        journal_docs.doc_key("gate", "M0260", [])


def test_two_commands_never_collide_on_one_method():
    assert journal_docs.doc_key("gate", "M0007") != journal_docs.doc_key("exposure", "M0007")


# ---- the head -----------------------------------------------------------------------------


def test_a_document_with_no_rows_has_no_head(lab):
    assert journal_docs.head_for(lab, "gate:M0001:all", method_id="M0001") is None


def test_the_head_is_the_row_nothing_supersedes(lab):
    first, _ = _write(lab, "gate:M0001:all", "one")
    assert journal_docs.head_for(lab, "gate:M0001:all", method_id="M0001") == first
    second, revised = _write(lab, "gate:M0001:all", "two")
    assert revised == first
    assert journal_docs.head_for(lab, "gate:M0001:all", method_id="M0001") == second


def test_a_head_belonging_to_another_method_is_not_a_chain_this_writer_may_join(lab):
    """`store._check_supersedes` refuses a cross-method link, so answering None appends a fresh
    document instead of raising LabError in the middle of a journal write."""
    with lab:
        store.add_method(
            conn=lab, id="M0002", name="another", family="trend",
            source_kind="knowledge", hypothesis="h",
        )
    mine, _ = _write(lab, "hand-written:key", "theirs", method_id="M0002")
    assert journal_docs.head_for(lab, "hand-written:key", method_id="M0001") is None
    assert journal_docs.head_for(lab, "hand-written:key", method_id="M0002") == mine


def test_a_row_written_before_schema_8_can_never_be_superseded_by_a_writer(lab):
    """The 500 historical rows carry doc_key NULL, and `doc_key = ?` never matches NULL."""
    with lab:
        old = store.add_insight(
            lab, kind="observation", title="a title", body="an old body", method_id="M0001",
        )
    assert _row(lab, old)["doc_key"] is None
    new_id, revised = _write(lab, "gate:M0001:all", "a new body")
    assert revised is None
    assert new_id != old
    assert _row(lab, old)["supersedes"] is None


# ---- the chain ----------------------------------------------------------------------------


def test_rerunning_the_same_subject_makes_one_document_at_version_two(lab):
    first, none_yet = _write(lab, "real-costs:M0001:M0001-A", "the first reading")
    second, revised = _write(lab, "real-costs:M0001:M0001-A", "the second reading")
    assert none_yet is None and revised == first
    before, after = _row(lab, first), _row(lab, second)
    # The predecessor is still there, and every byte of its content is untouched.
    assert before["body"] == "the first reading"
    assert before["supersedes"] is None and before["doc_key"] == "real-costs:M0001:M0001-A"
    assert after["supersedes"] == first
    heads = lab.execute(
        "SELECT count(*) FROM insights WHERE doc_key = ? AND id NOT IN "
        "(SELECT supersedes FROM insights WHERE supersedes IS NOT NULL)",
        ("real-costs:M0001:M0001-A",),
    ).fetchone()[0]
    assert heads == 1


def test_no_supersede_writes_a_sibling_and_leaves_the_head_alone(lab):
    first, _ = _write(lab, "real-costs:M0001:M0001-A", "the first reading")
    second, revised = _write(lab, "real-costs:M0001:M0001-A", "beside it", supersede=False)
    assert revised is None
    assert _row(lab, second)["supersedes"] is None
    assert _row(lab, first)["supersedes"] is None


def test_a_third_run_chains_onto_the_second_not_the_first(lab):
    first, _ = _write(lab, "gate:M0001:all", "one")
    second, _ = _write(lab, "gate:M0001:all", "two")
    third, revised = _write(lab, "gate:M0001:all", "three")
    assert revised == second
    assert [_row(lab, i)["supersedes"] for i in (first, second, third)] == [None, first, second]


def test_a_concurrent_link_to_the_same_head_chains_instead_of_forking(lab, monkeypatch):
    """`insights_one_successor` refuses the second link; `append` re-reads and chains on."""
    first, _ = _write(lab, "gate:M0001:all", "one")
    rival, _ = _write(lab, "gate:M0001:all", "a rival session got there first")
    assert _row(lab, rival)["supersedes"] == first

    # Force `append` to see the stale head exactly once, the way a racing session would.
    real_head = journal_docs.head_for
    seen = {"n": 0}

    def stale(conn, key, *, method_id):
        seen["n"] += 1
        return first if seen["n"] == 1 else real_head(conn, key, method_id=method_id)

    monkeypatch.setattr(journal_docs, "head_for", stale)
    mine, revised = _write(lab, "gate:M0001:all", "mine")
    assert revised == rival and _row(lab, mine)["supersedes"] == rival


def test_the_entry_label_says_what_happened_to_the_page():
    assert journal_docs.entry_label(471, None) == "#471"
    assert journal_docs.entry_label(471, 468) == "#471 (revises #468)"


# ---- the M0260 incident --------------------------------------------------------------------


def _side(model, candidate_id, dd, pf):
    return real_costs.Side(
        model=model, candidate_id=candidate_id, total_return=0.5, cagr=0.1, max_drawdown=dd,
        profit_factor=pf, trades=120, sharpe=0.8, mar=0.6, exposure=0.9, costs_usd=10.0,
        cost_drag=0.02, spy_tr_return=0.4, spy_tr_cagr=0.08, beats_spy=True, failed=(),
    )


def _comparison(candidate_id, dd, pf):
    """One `lab costs` reading of one arm, with the numbers the lab actually recorded."""
    return real_costs.Comparison(
        method_id="M0001", method_name="one method, three arms", candidate_id=candidate_id,
        recorded_model="flat", trial_n=1, recorded_total_return=0.5,
        start=date(1996, 1, 2), end=date(2015, 10, 16), fingerprint="smoke",
        flat=_side("flat", candidate_id, dd, pf),
        real=_side("gotrade", f"{candidate_id}-GT", dd, pf),
    )


#: The three arms of M0260 that insights 466, 467 and 468 really are, with the max drawdown and
#: profit factor each one reported, matched to trials n=835, 838 and 836.
M0260_ARMS = (
    ("M0001-M-NATIVE", 0.238, 1.98),
    ("M0001-M-G12", 0.256, 1.62),
    ("M0001-M-G3", 0.336, 1.60),
)


def test_m0260s_three_arms_stay_three_documents(lab):
    """The measured bug, replayed. Three arms, one generated title, three documents.

    Keyed on the method or on the title, the 23.8% arm would be buried under the 33.6% one and
    the owner would see only the last. That is a measurement vanishing off the page.
    """
    written = []
    for candidate_id, dd, pf in M0260_ARMS:
        cmp = _comparison(candidate_id, dd, pf)
        with lab:
            written.append(real_costs.journal(lab, cmp))

    ids = [i for i, _ in written]
    assert [prev for _, prev in written] == [None, None, None], "no arm may supersede another"
    rows = [_row(lab, i) for i in ids]
    assert len({r["doc_key"] for r in rows}) == 3
    assert [r["supersedes"] for r in rows] == [None, None, None]
    # One generated title across all three, which is exactly why the title is not the key.
    assert len({r["title"] for r in rows}) == 1
    # And all three are still readable as their own documents.
    heads = lab.execute(
        "SELECT count(*) FROM insights WHERE doc_key IS NOT NULL AND id NOT IN "
        "(SELECT supersedes FROM insights WHERE supersedes IS NOT NULL)"
    ).fetchone()[0]
    assert heads == 3


def test_rerunning_one_of_m0260s_arms_revises_only_that_arm(lab):
    """The mirror of the test above: the same arm twice is one document at version 2."""
    for candidate_id, dd, pf in M0260_ARMS:
        with lab:
            real_costs.journal(lab, _comparison(candidate_id, dd, pf))
    g3_first = lab.execute(
        "SELECT id FROM insights WHERE doc_key = ?", ("real-costs:M0001:M0001-M-G3",)
    ).fetchone()[0]

    with lab:
        again, revised = real_costs.journal(lab, _comparison("M0001-M-G3", 0.336, 1.60))

    assert revised == g3_first
    assert _row(lab, again)["supersedes"] == g3_first
    # The first reading is still there, byte for byte.
    assert _row(lab, g3_first)["body"] == real_costs.insight_text(
        _comparison("M0001-M-G3", 0.336, 1.60)
    )[1].strip()
    # The other two arms were not touched.
    untouched = lab.execute(
        "SELECT count(*) FROM insights WHERE doc_key IN (?, ?) AND supersedes IS NOT NULL",
        ("real-costs:M0001:M0001-M-NATIVE", "real-costs:M0001:M0001-M-G12"),
    ).fetchone()[0]
    assert untouched == 0


def test_the_doc_key_is_the_arm_not_the_method(lab):
    cmp = _comparison("M0001-M-G3", 0.336, 1.60)
    assert real_costs.doc_key(cmp) == "real-costs:M0001:M0001-M-G3"
