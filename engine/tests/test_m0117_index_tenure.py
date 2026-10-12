"""M0117's membership-calendar logic, which the shared contract test cannot reach.

``tests/test_lab_methods.py`` drives a market-aware allocator's history-only path, where M0117
targets nothing by contract. Everything that makes this method what it is -- merging a symbol's
membership spells, censoring the two snapshot epochs, and the exclusion itself -- therefore has
no coverage there. It has it here.
"""

from __future__ import annotations

from datetime import date

from seer_engine.lab.methods.m0117_index_tenure_exclusion import (
    TenureParams,
    merge_spells,
    months_before,
    too_new,
)

EPOCH = date(1996, 1, 2)


def test_months_before_clamps_the_day_to_a_shorter_month():
    assert months_before(date(2015, 3, 31), 1) == date(2015, 2, 28)
    assert months_before(date(2016, 3, 31), 1) == date(2016, 2, 29)
    assert months_before(date(2015, 1, 15), 12) == date(2014, 1, 15)
    assert months_before(date(2015, 1, 15), 36) == date(2012, 1, 15)
    assert months_before(date(2015, 6, 30), 0) == date(2015, 6, 30)


def test_two_index_listings_of_one_company_become_one_spell():
    spells, counts = merge_spells(
        (("AAPL", EPOCH, None), ("AAPL", date(2007, 2, 1), None)),
    )
    assert spells["AAPL"] == ((EPOCH, None),)
    assert counts == {EPOCH: 1}


def test_a_company_that_left_and_came_back_keeps_two_spells():
    spells, counts = merge_spells(
        (("AAL", EPOCH, date(1997, 1, 15)), ("AAL", date(2014, 12, 22), None)),
    )
    assert spells["AAL"] == ((EPOCH, date(1997, 1, 15)), (date(2014, 12, 22), None))
    assert counts == {EPOCH: 1, date(2014, 12, 22): 1}


def test_abutting_spells_merge_and_a_contained_one_is_absorbed():
    spells, _ = merge_spells(
        (
            ("X", date(2000, 1, 3), date(2005, 1, 3)),
            ("X", date(2005, 1, 3), None),
            ("X", date(2001, 6, 1), date(2002, 6, 1)),
        ),
    )
    assert spells["X"] == ((date(2000, 1, 3), None),)


def _one(start: date, *, shared: int = 1) -> tuple[dict, dict]:
    spells = {"S": ((start, None),)}
    return spells, {start: shared}


def test_a_recent_addition_is_excluded_and_an_old_member_is_not():
    p = TenureParams(min_tenure_months=12)
    spells, counts = _one(date(2014, 6, 2))
    assert too_new(spells, counts, "S", date(2015, 1, 2), p) is True
    assert too_new(spells, counts, "S", date(2015, 6, 2), p) is False  # exactly 12 months: kept
    assert too_new(spells, counts, "S", date(2016, 1, 4), p) is False


def test_the_control_excludes_nobody():
    spells, counts = _one(date(2015, 9, 1))
    assert too_new(spells, counts, "S", date(2015, 10, 1), TenureParams()) is False


def test_a_snapshot_epoch_is_left_censored_not_an_addition():
    """The 1996 and 2007 first rows are the data's first sight, so tenure is unknown, not zero."""
    p = TenureParams(min_tenure_months=36)
    shared, counts = _one(EPOCH, shared=487)
    assert too_new(shared, counts, "S", date(1996, 2, 1), p) is False
    lone, lone_counts = _one(EPOCH, shared=1)
    assert too_new(lone, lone_counts, "S", date(1996, 2, 1), p) is True


def test_a_quarterly_rebalance_cohort_is_still_a_real_addition():
    """Nine symbols on one date is the busiest real add day in the store; it must not censor."""
    p = TenureParams(min_tenure_months=12)
    spells, counts = _one(date(2008, 12, 22), shared=9)
    assert too_new(spells, counts, "S", date(2009, 3, 2), p) is True


def test_a_symbol_with_no_spell_covering_the_date_is_not_excluded():
    p = TenureParams(min_tenure_months=12)
    spells = {"S": ((date(2000, 1, 3), date(2001, 1, 3)),)}
    assert too_new(spells, {date(2000, 1, 3): 1}, "S", date(2015, 1, 2), p) is False
    assert too_new(spells, {}, "MISSING", date(2015, 1, 2), p) is False


def test_the_spell_covering_the_date_is_the_one_that_counts():
    """An old first spell must not make a fresh re-entry look long-tenured."""
    p = TenureParams(min_tenure_months=12)
    spells = {"S": ((EPOCH, date(1997, 1, 15)), (date(2014, 12, 22), None))}
    counts = {EPOCH: 487, date(2014, 12, 22): 1}
    assert too_new(spells, counts, "S", date(2015, 3, 2), p) is True
    assert too_new(spells, counts, "S", date(1996, 6, 3), p) is False  # censored first spell
