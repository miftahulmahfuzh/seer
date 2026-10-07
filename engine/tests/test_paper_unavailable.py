"""paper.unavailable: stocks the broker does not offer leave the membership for their window."""

from datetime import date

import pytest

from seer_engine.backtest.market import Membership
from seer_engine.paper.unavailable import Window, clip, excluded_on, held_excluded

D = date


def test_open_window_ends_the_interval_on_since():
    out = clip([("SNDK", D(2025, 2, 24), None)], [Window("SNDK", D(2026, 10, 6))])
    assert out == (("SNDK", D(2025, 2, 24), D(2026, 10, 6)),)


def test_closed_window_splits_the_interval():
    out = clip([("TPL", D(2024, 1, 1), None)], [Window("TPL", D(2026, 1, 5), D(2026, 2, 1))])
    assert out == (("TPL", D(2024, 1, 1), D(2026, 1, 5)), ("TPL", D(2026, 2, 1), None))


def test_window_before_membership_starts_removes_nothing_or_trims_start():
    assert clip([("X", D(2026, 1, 1), None)], [Window("X", D(2025, 1, 1), D(2025, 6, 1))]) == (
        ("X", D(2026, 1, 1), None),
    )
    assert clip([("X", D(2026, 1, 1), None)], [Window("X", D(2025, 1, 1))]) == ()


def test_empty_window_and_other_symbols_untouched():
    rows = [("A", D(2020, 1, 1), D(2021, 1, 1)), ("B", D(2020, 1, 1), None)]
    assert clip(rows, [Window("B", D(2026, 1, 1), D(2026, 1, 1))]) == tuple(rows)
    assert clip(rows, [Window("C", D(2020, 6, 1))]) == tuple(rows)


def test_membership_reads_the_clipped_intervals():
    m = Membership(intervals=clip([("SNDK", D(2025, 2, 24), None), ("SPY", D(2000, 1, 3), None)],
                                  [Window("SNDK", D(2026, 10, 6))]))
    assert "SNDK" in m.members_on(D(2026, 10, 5))
    assert "SNDK" not in m.members_on(D(2026, 10, 6))
    assert "SPY" in m.members_on(D(2026, 10, 6))


def test_excluded_on_and_held_excluded():
    ws = [Window("SNDK", D(2026, 10, 6)), Window("TPL", D(2026, 1, 1), D(2026, 10, 6))]
    assert excluded_on(ws, D(2026, 10, 6)) == {"SNDK"}
    assert excluded_on(ws, D(2026, 10, 5)) == {"TPL"}
    assert held_excluded(["NVDA", "SNDK", "TPL", "SNDK"], ws, D(2026, 10, 6)) == ["SNDK"]


def test_until_before_since_is_refused():
    with pytest.raises(ValueError):
        Window("X", D(2026, 1, 2), D(2026, 1, 1))
