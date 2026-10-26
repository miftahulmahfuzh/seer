"""Collapsing method ids to distinct books (lab/books.py, lab/firings.py).

The bug these guard is insight 529: the buy signal named three methods and they were one book,
and "four test-window looks, all four failed" was really two books and nought for two. Both
numbers gate decisions the owner makes with real money, and the first was wrong in the direction
that encourages spending.

Every test builds its own temp lab. The committed lab's own answer is asserted separately, in the
one test that is skipped when the file is not here.
"""

from __future__ import annotations

import json
import shutil
from datetime import date, timedelta

import pytest

from labkit import LAB_PRICE_FINGERPRINT, stamp_provenance
from seer_engine.backtest import regime
from seer_engine.lab import books, firings, hardgate, store

SAME_PRICES = LAB_PRICE_FINGERPRINT
OTHER_PRICES = "e" * 64

BENCH_SPAN = (date(1993, 2, 1), date(2015, 10, 16))
DEV_SPAN = (date(1996, 1, 2), date(2015, 10, 16))


@pytest.fixture(autouse=True)
def _at_the_policy_these_fixtures_were_recorded_under(monkeypatch):
    monkeypatch.setattr(store, "DSR_POLICY", "all-trials")
    store._GATE_CACHE.clear()
    yield
    store._GATE_CACHE.clear()


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    yield c
    c.close()


def _months(start: date, end: date) -> list[date]:
    out, d = [], date(start.year, start.month, 1)
    while True:
        nxt = date(d.year + (d.month == 12), (d.month % 12) + 1, 1)
        last = nxt - timedelta(days=1)
        if last > end:
            return out
        if last >= start:
            out.append(last)
        d = nxt


def _curve(months: list[date], annual: float, wobble: float = 0.0, phase: int = 0) -> str:
    """A monthly curve. ``wobble`` adds a deterministic month-to-month kick, and ``phase`` shifts
    it, so two curves can be made to agree or disagree after the market's share is removed --
    which is the only thing the correlation bar reads."""
    out, v = [], 1.0
    for i, d in enumerate(months):
        out.append([d.isoformat(), round(v, 8)])
        kick = wobble * (1 if (i + phase) % 3 == 0 else -0.5)
        v *= (1.0 + annual) ** (1.0 / 12.0) * (1.0 + kick)
    return json.dumps(out)


def _trial(**kw) -> store.TrialRow:
    base = dict(
        method_id="M0001", candidate_id="M0001-A", config_digest="d1", config_text="t",
        rules_id="MONTHLY_HOLD", allocator_id="TIMING", window="dev", start="1996-01-02",
        end="2015-10-16", store_fingerprint="399d0d25", git_sha="abc123",
        run_at="2026-10-06T00:00:00+00:00", total_return=3.0, cagr=0.12, max_drawdown=0.11,
        profit_factor=1.6, trades=250, sharpe=0.9, exposure=0.95, turnover=1.1, worst_year=2008,
        worst_year_return=-0.1, spy_tr_return=2.0, spy_tr_cagr=0.08, mar=0.8, failed="",
        eligible=True, dsr=0.97, n_trials_at_run=60, curve_json="[]",
    )
    base.update(kw)
    return store.TrialRow(**base)


def _benchmark(conn) -> None:
    with conn:
        store.add_method(conn, id="H-P7A-REF", name="SPY buy and hold", family="reference",
                         source_kind="seed", hypothesis="h", status="registered")
        ns = store.insert_trials(conn, [_trial(
            method_id="H-P7A-REF", candidate_id=regime.BENCH_CANDIDATE,
            config_digest="ref-spy-hold", start="1993-02-01", end="2015-10-16",
            store_fingerprint="5451195f",
            curve_json=_curve(_months(*BENCH_SPAN), 0.08, wobble=0.02),
        )])
        stamp_provenance(conn, ns, price_fingerprint=SAME_PRICES)


def _method(conn, mid, *, parent=None, family="trend", status="dev-eligible", annual=0.15,
            wobble=0.03, phase=0, prices=SAME_PRICES, stamped=True, curves=True) -> None:
    with conn:
        store.add_method(conn, id=mid, name=f"n{mid}", family=family, parent_id=parent,
                         source_kind="variation" if parent else "knowledge", hypothesis="h",
                         status="registered")
        ns = store.insert_trials(conn, [_trial(
            method_id=mid, candidate_id=f"{mid}-A", config_digest=f"d-{mid}",
            curve_json="[]" if not curves else _curve(_months(*DEV_SPAN), annual, wobble, phase),
        )])
        if stamped:
            stamp_provenance(conn, ns, price_fingerprint=prices)
        for step in {
            "registered": (),
            "dev-eligible": ("dev-eligible",),
            "test-failed": ("dev-eligible", "promoted", "test-failed"),
        }[status]:
            store.update_method(conn, mid, status=step)


def _leads(bs: list[books.Book]) -> list[tuple[str, tuple[str, ...]]]:
    return [(b.lead, b.others) for b in bs]


# ------------------------------------------------------------------ the rule, stated


def test_the_bar_is_the_hard_gates_own_and_is_not_restated_here():
    """books.py must never grow a second definition of "two books move together".

    The brief that commissioned it said so in capitals, and the clustering pass that found the
    bug obeyed the same rule -- it agreed with ``hardgate.correlation`` to 1.2e-15 over 400 spot
    checks. The cheapest way to keep it true is to assert that the only bar in the module is the
    gate's object, and that the module says which functions it borrows.
    """
    src = (books.__file__,)
    text = open(src[0], encoding="utf-8").read()
    assert "KIN_CORRELATION = " not in text  # the gate declares it; this module reads it
    assert "hardgate.KIN_CORRELATION" in text
    for borrowed in ("geometry", "mismatches", "trial_deposits", "monthly_returns", "residual",
                     "correlation"):
        assert borrowed in (books.__doc__ or ""), borrowed


def test_a_lone_method_is_its_own_book_and_nothing_is_measured():
    assert _leads(books.group(None, ["M0001"])) == [("M0001", ())]
    assert _leads(books.group(None, [])) == []


# ------------------------------------------------------------------ lineage proposes


def test_a_declared_child_whose_curve_agrees_is_the_same_book(conn):
    """The firing case, in miniature: a child of a method that trades the way its parent does."""
    _benchmark(conn)
    _method(conn, "M0001")
    _method(conn, "M0002", parent="M0001")
    (lead, others), = _leads(books.group(conn, ["M0001", "M0002"]))
    assert (lead, others) == ("M0001", ("M0002",))


def test_the_reason_is_directional_and_names_the_lead_not_the_other_way_about(conn):
    _benchmark(conn)
    _method(conn, "M0001")
    _method(conn, "M0002", parent="M0001")
    bk, = books.group(conn, ["M0001", "M0002"])
    why = bk.why["M0002"]
    assert why.kind == "child"
    assert why.correlation is not None and why.correlation >= hardgate.KIN_CORRELATION
    assert "version of M0001" in why.sentence("M0001")


def test_siblings_of_one_earlier_method_are_one_book(conn):
    """M0021 and M0022 are both M0011's, and that is what holds the spent looks together."""
    _benchmark(conn)
    _method(conn, "M0011")
    _method(conn, "M0021", parent="M0011")
    _method(conn, "M0022", parent="M0011")
    bk, = books.group(conn, ["M0021", "M0022"])
    assert (bk.lead, bk.others) == ("M0021", ("M0022",))
    assert bk.why["M0022"].kind == "sibling"
    assert bk.why["M0022"].via == "M0011"


def test_a_common_ancestor_is_not_enough_when_the_curves_refuse_it(conn):
    """Lineage proposes and the recorded curves confirm. This is the clause that stops the
    lineage pass chaining: a shared ancestor several generations back is declared of a large part
    of the real lab, and a child that changed the idea is a new book."""
    _benchmark(conn)
    _method(conn, "M0011")
    _method(conn, "M0021", parent="M0011", wobble=0.03, phase=0)
    _method(conn, "M0030", parent="M0011", wobble=0.06, phase=1)
    assert _leads(books.group(conn, ["M0021", "M0030"])) == [("M0021", ()), ("M0030", ())]


# ------------------------------------------------------------------ behaviour catches the rest


def test_two_methods_that_are_not_relatives_merge_on_behaviour_alone(conn):
    """The catch for twins that are not relatives -- two authors arriving at one book."""
    _benchmark(conn)
    _method(conn, "M0040", family="a")
    _method(conn, "M0041", family="b")
    bk, = books.group(conn, ["M0040", "M0041"])
    assert (bk.lead, bk.others) == ("M0040", ("M0041",))
    assert bk.why["M0041"].kind == "twin"
    assert "not related on paper" in bk.why["M0041"].sentence("M0040")


def test_an_unrelated_pair_whose_curves_disagree_stays_two_books(conn):
    _benchmark(conn)
    _method(conn, "M0040", family="a", wobble=0.02, phase=0)
    _method(conn, "M0041", family="b", wobble=0.09, phase=2)
    assert len(books.group(conn, ["M0040", "M0041"])) == 2


def test_when_the_curves_cannot_be_read_the_declaration_stands(conn):
    """(D10) refuses a comparison across two price fingerprints. For a spending decision the safe
    error is to count FEWER independent confirmations, so the declared child still collapses."""
    _benchmark(conn)
    _method(conn, "M0001")
    _method(conn, "M0002", parent="M0001", prices=OTHER_PRICES)
    bk, = books.group(conn, ["M0001", "M0002"])
    assert (bk.lead, bk.others) == ("M0001", ("M0002",))
    assert bk.why["M0002"].kind == "declared"
    assert bk.why["M0002"].correlation is None


def test_an_unreadable_pair_with_no_declared_relation_stays_apart(conn):
    """The same failure the other way: nothing declared and nothing measurable is not a book."""
    _benchmark(conn)
    _method(conn, "M0040", family="a")
    _method(conn, "M0041", family="b", prices=OTHER_PRICES)
    assert len(books.group(conn, ["M0040", "M0041"])) == 2


def test_a_lab_with_no_benchmark_falls_back_to_the_declaration_rather_than_raising(conn):
    """With no recorded benchmark nothing is measurable, so rule 4 stands everywhere at once:
    declared relatives still collapse, and ids with no declared relation still do not. A
    presentation rule has to answer, and this is the conservative answer."""
    _method(conn, "M0001")
    _method(conn, "M0002", parent="M0001")
    _method(conn, "M0040", family="elsewhere")
    assert _leads(books.group(conn, ["M0001", "M0002", "M0040"])) == [
        ("M0001", ("M0002",)), ("M0040", ()),
    ]


# ------------------------------------------------------------------ the shape of the grouping


def test_linkage_is_complete_so_one_weak_pair_cannot_chain_three_into_one(conn):
    """Single linkage put 147 of 171 methods in one cluster where only 12% of the pairs cleared
    the bar and the minimum was -0.372. A chain is not a book, and complete linkage cannot make
    one: C joins only if it clears against A *and* B."""
    _benchmark(conn)
    _method(conn, "M0001", wobble=0.03, phase=0)
    _method(conn, "M0002", parent="M0001", wobble=0.03, phase=0)
    _method(conn, "M0003", parent="M0002", wobble=0.10, phase=1)
    got = books.group(conn, ["M0001", "M0002", "M0003"])
    assert len(got) == 2
    assert ("M0001", ("M0002",)) in _leads(got)


def test_the_lead_is_the_one_the_others_descend_from(conn):
    """Not the lowest id by luck: the row the owner reads has to be the origin of the book."""
    _benchmark(conn)
    _method(conn, "M0100")
    _method(conn, "M0003", parent="M0100")
    bk, = books.group(conn, ["M0003", "M0100"])
    assert bk.lead == "M0100"
    assert bk.members == ("M0100", "M0003")


def test_grouping_is_deterministic_whatever_order_the_ids_arrive_in(conn):
    _benchmark(conn)
    _method(conn, "M0001")
    _method(conn, "M0002", parent="M0001")
    _method(conn, "M0003", parent="M0001")
    a = _leads(books.group(conn, ["M0003", "M0001", "M0002"]))
    b = _leads(books.group(conn, ["M0002", "M0003", "M0001"]))
    assert a == b == [("M0001", ("M0002", "M0003"))]


# ------------------------------------------------------------------ the two counters


def test_the_spent_looks_collapse_to_the_books_they_bought(conn):
    """Four looks, two books: the record is 0-for-2 and the budget was spent twice on one thing."""
    _benchmark(conn)
    _method(conn, "M0011")
    for mid, parent in [("M0021", "M0011"), ("M0022", "M0011"), ("M0029", "M0021")]:
        _method(conn, mid, parent=parent, status="test-failed")
    _method(conn, "M0002", family="other", status="test-failed", wobble=0.09, phase=2)
    with conn:
        for mid in ("M0021", "M0029", "M0022", "M0002"):
            store.insert_trials(conn, [_trial(
                method_id=mid, candidate_id=f"{mid}-T", config_digest=f"t-{mid}", window="test",
                start="2015-10-19", end="2026-10-01", curve_json="[]",
            )])
    got = firings.test_look_books(conn)
    assert len(got) == 2
    assert _leads(got)[0] == ("M0021", ("M0022", "M0029"))
    assert _leads(got)[1] == ("M0002", ())


def test_the_snapshot_publishes_both_counters_and_the_names_under_them(conn):
    _benchmark(conn)
    _method(conn, "M0011")
    _method(conn, "M0021", parent="M0011", status="test-failed")
    _method(conn, "M0029", parent="M0021", status="test-failed")
    with conn:
        for mid in ("M0021", "M0029"):
            store.insert_trials(conn, [_trial(
                method_id=mid, candidate_id=f"{mid}-T", config_digest=f"t-{mid}", window="test",
                start="2015-10-19", end="2026-10-01", curve_json="[]",
            )])
    snap = store.snapshot(conn)
    assert snap["version"] == 7
    assert snap["summary"]["testLooks"] == 2
    assert snap["summary"]["testBooks"] == 1
    block, = snap["books"]["testLooks"]
    assert block == {
        "lead": "M0021", "others": ["M0029"],
        "why": {"M0029": books.SAME_BOOK_TEXT["child"]},
    }
    # The site fills {lead} itself, so the exported text must still carry the placeholder and
    # must never carry an id, a digest or a correlation coefficient.
    assert "{lead}" in block["why"]["M0029"]
    assert "M00" not in block["why"]["M0029"]


def test_the_snapshot_survives_a_lab_with_no_benchmark_rather_than_failing_the_export(conn):
    """``snapshot`` is documented to answer on an un-migrated database, and every fresh fixture
    has no REF-SPY-HOLD curve. An empty block reads as "nothing is asking to be bought", which
    can never render as a reason to spend money."""
    _method(conn, "M0001")
    snap = store.snapshot(conn)
    assert snap["books"] == {"firing": [], "testLooks": []}
    assert snap["summary"]["testBooks"] == 0


def test_only_dev_eligible_methods_are_evaluated_for_a_firing(conn):
    """Not an optimisation with a behaviour risk attached: ``dev-eligible`` is ``buy_signal``'s
    first condition and it refuses on it before reading anything else."""
    _benchmark(conn)
    _method(conn, "M0001", status="registered")
    assert firings.firing(conn) == ([], {})


# ------------------------------------------------------------------ the committed lab's answer


@pytest.mark.skipif(not store.COMMITTED_DB.is_file(), reason="no committed lab database here")
def test_the_committed_lab_reads_five_looks_and_three_books(tmp_path):
    """The measured fact, pinned: insight 529 and docs/backtests/2026-10-21-lab-book-clustering.md,
    updated 2026-10-26 (sera-20261026-0703) when M0377 spent the lab's fifth test-window look --
    its first promotion to clear the hard gate and the buy signal -- and test-failed.

    Five test-window looks are spent and they bought three books -- M0021, M0022 and M0029 are one
    (0.93 to 0.99; M0029 is M0021's child and both it and M0022 grew out of M0011), M0002 is
    genuinely separate at 0.73, and M0377 (family stock-updown-asymmetry, unrelated to the other
    three) is a third, standalone book. The look count itself must not move: it is 5 before and
    after.
    """
    db = tmp_path / "lab.sqlite"
    shutil.copyfile(store.COMMITTED_DB, db)
    c = store.connect(db)
    try:
        assert store.test_looks(c) == 5
        got = firings.test_look_books(c)
        assert [(b.lead, b.others) for b in got] == [
            ("M0021", ("M0022", "M0029")), ("M0002", ()), ("M0377", ())
        ]
        assert store.test_looks(c) == 5
    finally:
        c.close()
