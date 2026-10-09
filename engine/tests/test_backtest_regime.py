"""The breadth regime panel: one subtraction, and a curve split by its answer."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from seer_engine.backtest import regime
from seer_engine.backtest.market import Market, Membership
from seer_engine.strategies.base import History

MONTHS = [date(2020, m, 28) for m in range(1, 7)]


def hist(symbol: str, closes: list[float], days: list[date] | None = None) -> History:
    d = days or MONTHS[: len(closes)]
    a = np.array(closes, dtype=np.float64)
    return History(symbol, np.array(d, dtype="datetime64[D]"), a, a, a, a,
                   np.full(len(a), 1e6))


def market(spy: list[float], members: dict[str, list[float]]) -> Market:
    hs = {regime.SPY: hist(regime.SPY, spy)}
    hs.update({s: hist(s, c) for s, c in members.items()})
    intervals = tuple((s, date(2019, 1, 1), None) for s in members)
    return Market(history=dict(sorted(hs.items())), membership=Membership(intervals),
                  fx=((date(2019, 1, 1), __import__("decimal").Decimal("14000")),))


def wide(n: int, pattern: list[float]) -> dict[str, list[float]]:
    """``n`` members all following ``pattern``; enough of them to clear MIN_MEMBERS."""
    return {f"S{i:03d}": list(pattern) for i in range(n)}


def test_a_month_the_index_wins_alone_is_narrow():
    """SPY +10% while the typical member is flat: a few big names carried it."""
    m = market([100, 110], wide(40, [100, 100]))
    sp = regime.breadth(m, MONTHS[:2])
    assert sp[MONTHS[1]] == pytest.approx(0.10)
    assert regime.labels(sp) == {MONTHS[1]: regime.NARROW}


def test_a_month_the_members_keep_up_is_broad():
    m = market([100, 110], wide(40, [100, 125]))
    sp = regime.breadth(m, MONTHS[:2])
    assert sp[MONTHS[1]] == pytest.approx(0.10 - 0.25)
    assert regime.labels(sp) == {MONTHS[1]: regime.BROAD}


def test_the_first_month_is_never_labelled():
    """The value at a date describes the move INTO it, so there is nothing to say about the first."""
    m = market([100, 110, 121], wide(40, [100, 100, 100]))
    assert MONTHS[0] not in regime.breadth(m, MONTHS[:3])


def test_a_month_with_too_few_priced_members_is_left_out_not_guessed():
    m = market([100, 110], wide(regime.MIN_MEMBERS - 1, [100, 100]))
    assert regime.breadth(m, MONTHS[:2]) == {}


def test_membership_is_read_at_the_month_start_not_the_end():
    """A company that joins the index mid-window must not score the months before it joined."""
    m = market([100, 110, 121], wide(40, [100, 100, 100]))
    late = Membership((*[(f"S{i:03d}", date(2019, 1, 1), None) for i in range(40)],
                       ("LATE", date(2020, 3, 1), None)))
    m = Market(history={**m.history, "LATE": hist("LATE", [1, 1000, 1000])},
               membership=late, fx=m.fx)
    sp = regime.breadth(m, MONTHS[:3])
    # LATE's 1000x happens in the month ending MONTHS[1]; it was not a member at MONTHS[0], so
    # it must not drag that month's mean. Both months read as the flat members plus SPY.
    assert sp[MONTHS[1]] == pytest.approx(0.10)


def test_split_chains_only_its_own_regimes_months():
    curve = [(MONTHS[0], 1.0), (MONTHS[1], 1.10), (MONTHS[2], 1.21), (MONTHS[3], 1.0890)]
    label = {MONTHS[1]: regime.NARROW, MONTHS[2]: regime.NARROW, MONTHS[3]: regime.BROAD}
    got = regime.split(curve, label)
    assert got[regime.NARROW].months == 2
    assert got[regime.NARROW].total_return == pytest.approx(0.21)
    assert got[regime.BROAD].months == 1
    assert got[regime.BROAD].total_return == pytest.approx(-0.10)
    # annualised: two months of +21% compounds hard; one month of -10% compounds harder down
    assert got[regime.NARROW].annualised == pytest.approx(1.21 ** 6 - 1)
    assert got[regime.BROAD].annualised == pytest.approx(0.9 ** 12 - 1)


def test_a_regime_with_no_months_reports_nothing_rather_than_zero():
    curve = [(MONTHS[0], 1.0), (MONTHS[1], 1.10)]
    got = regime.split(curve, {MONTHS[1]: regime.NARROW})
    assert got[regime.BROAD] == regime.Span(regime.BROAD, 0, None, None)


def test_panel_reports_the_gap_that_is_the_whole_point():
    """A book that beats the index when breadth is broad and loses when it is narrow."""
    book = [(MONTHS[0], 1.0), (MONTHS[1], 0.95), (MONTHS[2], 1.14)]
    bench = [(MONTHS[0], 1.0), (MONTHS[1], 1.10), (MONTHS[2], 1.155)]
    label = {MONTHS[1]: regime.NARROW, MONTHS[2]: regime.BROAD}
    got = regime.panel(book, bench, label)
    narrow_book, narrow_bench, narrow_gap = got[regime.NARROW]
    broad_book, broad_bench, broad_gap = got[regime.BROAD]
    assert narrow_book.total_return == pytest.approx(-0.05)
    assert narrow_bench.total_return == pytest.approx(0.10)
    assert narrow_gap < 0  # loses the narrow months
    assert broad_book.total_return == pytest.approx(0.20)
    assert broad_bench.total_return == pytest.approx(0.05)
    assert broad_gap > 0  # wins the broad ones


def test_split_ignores_a_month_the_breadth_could_not_label():
    curve = [(MONTHS[0], 1.0), (MONTHS[1], 1.10), (MONTHS[2], 1.21)]
    got = regime.split(curve, {MONTHS[2]: regime.BROAD})
    assert got[regime.BROAD].months == 1
    assert got[regime.NARROW].months == 0


def test_persistence_is_a_trailing_mean_not_a_month_label():
    spread = {MONTHS[i]: v for i, v in enumerate([0.01, 0.03, -0.02, 0.02])}
    got = regime.persistence(spread, months=3)
    assert [d for d, _ in got] == [MONTHS[2], MONTHS[3]]
    assert got[0][1] == pytest.approx((0.01 + 0.03 - 0.02) / 3)
    assert got[1][1] == pytest.approx((0.03 - 0.02 + 0.02) / 3)


def test_persistence_needs_a_full_window_before_it_says_anything():
    spread = {MONTHS[0]: 0.01, MONTHS[1]: 0.02}
    assert regime.persistence(spread, months=3) == []
    assert regime.headwind(spread, months=3) is None


def test_headwind_is_the_latest_trailing_mean():
    spread = {MONTHS[i]: v for i, v in enumerate([0.01, 0.03, -0.02, 0.02])}
    assert regime.headwind(spread, months=3) == pytest.approx((0.03 - 0.02 + 0.02) / 3)


def test_persistence_refuses_a_window_too_short_to_mean_anything():
    with pytest.raises(ValueError, match="at least 2"):
        regime.persistence({MONTHS[0]: 0.01}, months=1)
