"""``lab.control_weight``: the assignment contract, on its own.

A module of its own rather than more tests in ``test_lab_control_draw``: these are a different
rule on a different axis and the test layout says what the source layout says. Nothing here opens
a store, a database or a backtest -- the whole module is two hashes, a sort, a rescale and a zip,
and that is exactly what makes it testable without any of them.
"""

from __future__ import annotations

import ast
import inspect
from datetime import date
from decimal import Decimal

import pytest

from seer_engine.lab import control_draw as cd
from seer_engine.lab import control_weight as cw

TAG = "M0221"
SEED = 1
NAMES = ("AAA", "BBB", "CCC", "DDD", "EEE")
DAY = date(2008, 3, 3)

#: How far a renormalised sum may sit from its target. ``rescaled`` divides in Decimal at the
#: context's 28 significant digits, so ``sum(w / s * total)`` is exact only when the division is;
#: the residual is ~1e-28. It is not corrected into the last rung, because the chassis quantizes
#: every weight DOWN to ``sim.book.WEIGHT_QUANTUM`` (1e-6) before it builds a Target, and that step
#: moves the total by up to one quantum per name -- twenty-two orders of magnitude more than this.
_RESIDUAL = Decimal("0.0000000001")


def _vec(*xs: str) -> list[Decimal | None]:
    return [None if x == "-" else Decimal(x) for x in xs]


def test_the_kth_rung_takes_the_kth_largest_weight():
    """The rule in one line: the ladder's first name is paid the real book's biggest slot."""
    order = ["AAA", "BBB", "CCC"]
    out = cw.assigned(order, _vec("0.10", "0.30", "0.20"))
    assert out == {"AAA": Decimal("0.30"), "BBB": Decimal("0.20"), "CCC": Decimal("0.10")}


def test_the_assignment_reads_the_vectors_values_and_never_its_order():
    """Blindness, asserted. Only the multiset of weights is read: the real book's own ordering
    carries its identity and the control must never see it."""
    order = ["AAA", "BBB", "CCC"]
    a = cw.assigned(order, _vec("0.10", "0.30", "0.20"))
    b = cw.assigned(order, _vec("0.30", "0.20", "0.10"))
    c = cw.assigned(order, _vec("0.20", "0.10", "0.30"))
    assert a == b == c


def test_the_assignment_spends_every_rung_and_mints_none():
    """A control must hold the real book's weights, not a rescaled lookalike: the sum is the real
    book's own exposure and no name is paid a weight the real book never held."""
    vector = _vec("0.10", "0.30", "0.20", "0.40")
    out = cw.assigned(["AAA", "BBB", "CCC", "DDD"], vector)
    assert sorted(out.values()) == sorted(w for w in vector if w is not None)


def test_a_none_or_zero_entry_is_not_a_rung():
    """``weights`` and ``sized_weights`` both return None where a weight floored to zero at
    ``WEIGHT_QUANTUM``. A name the real book could not hold is not a slot to pay out."""
    out = cw.assigned(["AAA", "BBB"], _vec("0.50", "-", "0.00", "0.25"))
    assert out == {"AAA": Decimal("0.50"), "BBB": Decimal("0.25")}


def test_fewer_rungs_than_names_leaves_the_tail_unpaid_rather_than_raising():
    """A pool thins and a ceiling floors names. The honest answer is a shorter dict -- the caller
    skips the missing keys, which is what the real book did with them -- not a crash years into a
    recorded trial."""
    out = cw.assigned(["AAA", "BBB", "CCC"], _vec("0.60", "0.40"))
    assert out == {"AAA": Decimal("0.60"), "BBB": Decimal("0.40")}
    assert "CCC" not in out


def test_more_rungs_than_names_leaves_the_surplus_unspent():
    out = cw.assigned(["AAA"], _vec("0.60", "0.40"))
    assert out == {"AAA": Decimal("0.60")}


def test_a_duplicate_name_is_refused_on_every_entry_point():
    """A silent ``set()`` would pay one rung twice and leave the last unpaid, and every size
    assertion downstream would still pass. That class of bug is why this raises."""
    with pytest.raises(ValueError, match="duplicate"):
        cw.assigned(["AAA", "AAA"], _vec("0.60", "0.40"))
    with pytest.raises(ValueError, match="duplicate"):
        cw.rung_order(["AAA", "AAA"], tag=TAG, seed=SEED)
    with pytest.raises(ValueError, match="duplicate"):
        cw.bottom_entry_order(
            ["AAA", "AAA"], held=frozenset(), tag=TAG, seed=SEED, data_date=DAY
        )


def test_a_float_weight_is_refused():
    """``sim.book.Target.weight`` is a Decimal and a float there is a TypeError. The vector that
    feeds it is held to the same rule rather than silently quantized here."""
    with pytest.raises(TypeError, match="Decimal"):
        cw.assigned(["AAA"], [0.5])  # type: ignore[list-item]


def test_the_ladder_is_the_keep_order_and_carries_no_date():
    """Date-free by construction: the ladder IS ``control_draw.keep_key``'s order, so a rung moves
    only when a neighbour leaves the book and never on the calendar alone."""
    order = cw.rung_order(NAMES, tag=TAG, seed=SEED)
    assert order == sorted(NAMES, key=lambda s: (cd.keep_key(TAG, SEED, s), s))
    assert "data_date" not in inspect.signature(cw.rung_order).parameters
    assert "data_date" not in inspect.signature(cw.assigned).parameters
    assert "data_date" not in inspect.signature(cw.rescaled).parameters


def test_a_name_that_stays_keeps_its_rung_when_its_neighbours_do():
    """What the ladder buys, stated as a test: drop the last name of the book and every survivor
    is paid the same rung it was paid before."""
    before = cw.assigned(cw.rung_order(NAMES, tag=TAG, seed=SEED), _vec(
        "0.30", "0.25", "0.20", "0.15", "0.10"))
    last = cw.rung_order(NAMES, tag=TAG, seed=SEED)[-1]
    rest = [s for s in NAMES if s != last]
    after = cw.assigned(cw.rung_order(rest, tag=TAG, seed=SEED), _vec(
        "0.30", "0.25", "0.20", "0.15"))
    for s in rest:
        assert after[s] == before[s], s


def test_the_tag_separates_two_books_so_a_twin_pair_can_share_one():
    """``tag`` is the book's method id, not the allocator id: M0221 and M0225 pass the same tag on
    purpose, so the twin pair draws the same names AND pays them the same rungs wherever both
    stores size the same company."""
    assert cd.keep_key("M0221", SEED, "AAA") != cd.keep_key("M0225", SEED, "AAA")
    assert cd.entry_key("M0221", SEED, "AAA", DAY) != cd.entry_key("M0225", SEED, "AAA", DAY)


# --------------------------------------------------------------- the shipped ladder: bottom-entry


def test_an_entrant_always_takes_a_bottom_rung():
    """The whole mechanism of the shipped rule, in one assertion. On a cap-weighted top-N the name
    that enters IS the new number ``top``, so it enters at the book's smallest weight; a blind
    entrant handed an average rung buys three or four times too much of it on the one session it
    changes hands, and that error taken 371 times was M0221's entire 1.90x turnover excess."""
    held = frozenset({"AAA", "BBB", "CCC"})
    order = cw.bottom_entry_order(NAMES, held=held, tag=TAG, seed=SEED, data_date=DAY)
    rungs = cw.assigned(order, _vec("0.30", "0.25", "0.20", "0.15", "0.10"))
    assert set(order[:3]) == held, "every name the control already held ranks above every entrant"
    assert set(order[3:]) == {"DDD", "EEE"}
    assert max(rungs[s] for s in ("DDD", "EEE")) < min(rungs[s] for s in held)


def test_the_keeps_half_is_the_date_free_ladder_and_the_entrants_half_is_the_entry_order():
    """Which is also why ``rung_order`` stays in the module: the shipped rule is built out of it."""
    held = frozenset({"AAA", "BBB", "CCC"})
    order = cw.bottom_entry_order(NAMES, held=held, tag=TAG, seed=SEED, data_date=DAY)
    assert order[:3] == cw.rung_order(sorted(held), tag=TAG, seed=SEED)
    assert order[3:] == sorted(
        ("DDD", "EEE"), key=lambda s: (cd.entry_key(TAG, SEED, s, DAY), s)
    )


def test_a_held_name_keeps_its_rung_across_a_decision_that_only_adds():
    """The keeps half is date-free, so a decision that takes in a new name re-prices nobody above
    it. A ladder that re-shuffled the survivors would be a turnover generator in its own right --
    which is exactly what the month-keyed ``"entry"`` order measured at 14.96x the book."""
    kept = ("AAA", "BBB", "CCC")
    before = cw.assigned(
        cw.bottom_entry_order(kept, held=frozenset(kept), tag=TAG, seed=SEED, data_date=DAY),
        _vec("0.40", "0.35", "0.25"),
    )
    after = cw.assigned(
        cw.bottom_entry_order(
            (*kept, "DDD"), held=frozenset(kept), tag=TAG, seed=SEED, data_date=DAY
        ),
        _vec("0.40", "0.35", "0.25", "0.20"),
    )
    for s in kept:
        assert after[s] == before[s], s
    assert after["DDD"] == Decimal("0.20")


def test_the_entrants_order_is_keyed_on_the_month_and_not_on_the_day():
    """Two decisions inside one month -- which a monthly rule set does not make, but a kickoff
    session can -- order the entrants identically, so the control does not churn on the calendar
    alone. ``matched_names`` keys its own draw the same way."""
    same = cw.bottom_entry_order(
        NAMES, held=frozenset(), tag=TAG, seed=SEED, data_date=date(2008, 3, 28)
    )
    assert same == cw.bottom_entry_order(
        NAMES, held=frozenset(), tag=TAG, seed=SEED, data_date=DAY
    )


def test_the_shipped_ladder_holds_nothing_between_calls():
    """Invariant I9, asserted: ``dev.run_registry`` reuses one allocator object per id across
    candidates and across folds, so a rule that remembered a rung would leak it between them. The
    entrants are ``picks - held`` by definition, at no cost and with no state."""
    args = dict(tag=TAG, seed=SEED, data_date=DAY)
    first = cw.bottom_entry_order(NAMES, held=frozenset({"AAA"}), **args)
    cw.bottom_entry_order(NAMES, held=frozenset({"EEE", "DDD"}), **args)
    assert cw.bottom_entry_order(NAMES, held=frozenset({"AAA"}), **args) == first


def test_held_names_the_book_does_not_hold_are_simply_not_in_the_order():
    """``held`` is the control's whole book and ``names`` is what it drew this decision; a name it
    is dropping is in the first and not the second, and must not reappear in the ladder."""
    order = cw.bottom_entry_order(
        ("AAA", "BBB"), held=frozenset({"AAA", "ZZZ"}), tag=TAG, seed=SEED, data_date=DAY
    )
    assert order == ["AAA", "BBB"]


# ------------------------------------------------------------------------------ the rescale


def test_the_rescale_keeps_the_controls_own_exposure_and_takes_only_the_shape():
    """``total`` is the SHIPPED control's own weight sum, never the real book's, so the rule
    changes the shape of the vector and never how much of the book is invested. A rule that moved
    exposure would be measuring two things at once, and D17 bands on neither."""
    out = cw.rescaled(_vec("0.50", "0.30", "0.20"), slots=3, total=Decimal("0.90"))
    assert abs(sum(out) - Decimal("0.90")) < _RESIDUAL
    assert out == sorted(out, reverse=True)
    assert [w / Decimal("0.90") for w in out] == [
        Decimal("0.50"), Decimal("0.30"), Decimal("0.20"),
    ]


def test_padding_repeats_the_smallest_rung_rather_than_the_average():
    """What a real top-N does with one more name: it joins at the bottom. Padding with the mean
    would hand the extra name a middle rung, which is the error the shipped ladder exists to
    remove."""
    out = cw.rescaled(_vec("0.60", "0.40"), slots=4, total=Decimal("1"))
    shape = [w / sum(out) for w in out]
    assert shape[2] == shape[3] == shape[1], "the pad repeats the smallest rung"
    assert shape[0] > shape[1]


def test_a_longer_vector_is_trimmed_from_the_bottom():
    """The control holds fewer names than the real book this month, so it holds the real book's
    biggest rungs -- the ones a shorter top-N would itself have held."""
    out = cw.rescaled(_vec("0.40", "0.30", "0.20", "0.10"), slots=2, total=Decimal("1"))
    assert [w / sum(out) for w in out] == [
        Decimal("0.40") / Decimal("0.70"), Decimal("0.30") / Decimal("0.70"),
    ]


def test_a_vector_with_no_usable_rung_falls_back_to_equal_shares():
    """A thin month years into a recorded trial must not be a crash. With nothing to shape by, the
    honest answer is the chassis's own fallback shape at the chassis's own exposure."""
    out = cw.rescaled(_vec("-", "0.00"), slots=4, total=Decimal("1"))
    assert out == [Decimal(1) / 4] * 4


def test_no_slots_and_no_exposure_each_pay_nothing():
    assert cw.rescaled(_vec("0.50"), slots=0, total=Decimal("1")) == []
    assert cw.rescaled(_vec("0.50"), slots=3, total=Decimal("0")) == []


def test_the_rescale_refuses_a_float_total_and_a_bool_slot_count():
    with pytest.raises(TypeError, match="Decimal"):
        cw.rescaled(_vec("0.50"), slots=1, total=1.0)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="int"):
        cw.rescaled(_vec("0.50"), slots=True, total=Decimal("1"))  # type: ignore[arg-type]


def test_the_rescale_and_the_assignment_compose_into_the_shipped_rule():
    """The whole contract end to end, as a chassis calls it: the real book's vector shaped to the
    control's own length and exposure, paid down the keeps-first ladder."""
    held = frozenset({"AAA", "BBB"})
    rungs = cw.assigned(
        cw.bottom_entry_order(NAMES, held=held, tag=TAG, seed=SEED, data_date=DAY),
        cw.rescaled(_vec("0.40", "0.30", "0.20", "-"), slots=5, total=Decimal("0.95")),
    )
    assert set(rungs) == set(NAMES)
    assert abs(sum(rungs.values()) - Decimal("0.95")) < _RESIDUAL
    assert max(rungs[s] for s in ("CCC", "DDD", "EEE")) < min(rungs[s] for s in held)


# ------------------------------------------------------------------------------ the contract


def test_the_module_computes_no_vector_and_reads_no_market():
    """The honest core of R2, asserted rather than argued: this module owns the ASSIGNMENT of a
    vector a chassis hands over, and it has no way to produce one. If it ever imports a store, a
    market or a strategy, the contract has quietly become something else."""
    src = ast.parse(inspect.getsource(cw))
    imported = set()
    for node in ast.walk(src):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
    assert imported == {"__future__", "collections.abc", "datetime", "decimal",
                        "seer_engine.lab.control_draw"}


def test_the_rule_id_and_the_four_measured_ladders_are_named():
    """``ORDERS`` is the record that four ladders were measured and one was chosen. A method file
    naming its wiring must be naming something this module recognises, and the three that lost are
    kept so a reader meeting one wiring knows the others were tried."""
    assert cw.RULE_ID == "matched-weight-v1"
    assert cw.ORDERS == ("bottom-entry", "ladder", "own-size", "entry")
