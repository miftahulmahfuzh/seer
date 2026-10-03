"""Point-in-time membership and the in-memory market (handover §6.4, plan phase 3).

Everything is synthetic and in memory: no database. Bars are built with ``simkit.bar`` (exact
4-dp Decimals) and turned into float64 ``History`` with ``history_from_bars``, the same way
``backtest.io`` will build them from Neon, so ``Market.bar`` must give the original Decimals back.
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import pytest
from simkit import D, bar

from seer_engine import dates
from seer_engine.backtest.market import SPY, Market, Membership
from seer_engine.prices import Bar
from seer_engine.strategies.base import History, history_from_bars


def _market(*histories: History, intervals=(), fx=()) -> Market:
    return Market(
        history={h.symbol: h for h in histories},
        membership=Membership(tuple(intervals)),
        fx=tuple(fx),
    )


# --------------------------------------------------------------------------- Membership


def test_members_on_honours_start_inclusive_end_exclusive():
    m = Membership((("AAA", D("2025-03-04"), D("2025-03-07")),))
    assert m.members_on(D("2025-03-03")) == frozenset()
    assert m.members_on(D("2025-03-04")) == frozenset({"AAA"})
    assert m.members_on(D("2025-03-06")) == frozenset({"AAA"})
    assert m.members_on(D("2025-03-07")) == frozenset()
    assert m.members_on(D("2030-01-01")) == frozenset()


def test_open_ended_interval_stays_a_member():
    m = Membership((("AAA", D("2025-03-04"), None),))
    assert m.members_on(D("2025-03-03")) == frozenset()
    assert m.members_on(D("2025-03-04")) == frozenset({"AAA"})
    assert m.members_on(D("2040-12-31")) == frozenset({"AAA"})


def test_members_on_unions_both_indices():
    # AAA: SP500 2020→2025-03-06, NDX 2025-03-05→open (overlap on 03-05); BBB only NDX;
    # CCC SP500 leaves 03-05 and rejoins 03-10 (a gap of three sessions).
    m = Membership(
        (
            ("AAA", D("2020-01-02"), D("2025-03-06")),
            ("AAA", D("2025-03-05"), None),
            ("BBB", D("2025-03-05"), None),
            ("CCC", D("2020-01-02"), D("2025-03-05")),
            ("CCC", D("2025-03-10"), None),
        )
    )
    assert m.members_on(D("2025-03-04")) == frozenset({"AAA", "CCC"})
    assert m.members_on(D("2025-03-05")) == frozenset({"AAA", "BBB"})
    assert m.members_on(D("2025-03-06")) == frozenset({"AAA", "BBB"})  # still in NDX
    assert m.members_on(D("2025-03-07")) == frozenset({"AAA", "BBB"})
    assert m.members_on(D("2025-03-10")) == frozenset({"AAA", "BBB", "CCC"})
    assert m.symbols() == ("AAA", "BBB", "CCC")


def test_membership_rejects_bad_intervals():
    with pytest.raises(ValueError):
        Membership((("AAA", D("2025-03-05"), D("2025-03-05")),))
    with pytest.raises(ValueError):
        Membership((("", D("2025-03-05"), None),))
    with pytest.raises(TypeError):
        Membership((("AAA", "2025-03-05", None),))
    with pytest.raises(TypeError):
        Membership([("AAA", D("2025-03-05"), None)])  # a list, not a tuple


def _synthetic_intervals(n: int) -> tuple[tuple[str, date, date | None], ...]:
    """``n`` deterministic intervals over 2015–2026 (no randomness): 795 symbols, some with
    two intervals, some open-ended, like the real ``universe`` table."""
    base = date(2015, 1, 2)
    out = []
    for i in range(n):
        start = base + timedelta(days=(i * 7919) % 4000)
        length = 30 + (i * 104729) % 3000
        end = None if i % 3 == 0 else start + timedelta(days=length)
        out.append((f"S{i % 795:03d}", start, end))
    return tuple(out)


def test_members_on_matches_brute_force_and_is_fast():
    intervals = _synthetic_intervals(1544)
    m = Membership(intervals)
    sessions = dates.sessions(date(2015, 1, 2), date(2026, 10, 2))
    assert len(sessions) == 2955

    t0 = time.perf_counter()
    got = [m.members_on(d) for d in sessions]
    elapsed = time.perf_counter() - t0
    assert elapsed < 2.0, f"members_on over {len(sessions)} sessions took {elapsed:.2f}s"

    for d, members in list(zip(sessions, got))[::97]:
        brute = frozenset(s for s, a, b in intervals if a <= d and (b is None or d < b))
        assert members == brute, d


# --------------------------------------------------------------------------- Market.bar


def test_bar_returns_exact_four_dp_decimals_from_float64():
    bars = [
        bar("AAA", "2025-03-03", "123.4567", "99999999.9999", "0.0001", "100.1000", 7_654_321_000),
        bar("AAA", "2025-03-04", "0.1", "1234.6", "0.07", "1234.5678", 1),
    ]
    m = _market(history_from_bars("AAA", bars))
    for b in bars:
        got = m.bar("AAA", b.date)
        assert got == b
        for name in ("open", "high", "low", "close"):
            value = getattr(got, name)
            assert type(value) is Decimal
            assert value.as_tuple().exponent == -4
        assert type(got.volume) is int


def test_bar_rounds_a_non_4dp_float_half_up_through_its_repr():
    h = History(
        symbol="AAA",
        dates=np.array([D("2025-03-03")], dtype="datetime64[D]"),
        open=np.array([0.1 + 0.2]),  # 0.30000000000000004
        high=np.array([10.12345]),  # repr '10.12345' -> half-up 10.1235
        low=np.array([0.00005]),  # -> 0.0001
        close=np.array([2.5]),
        volume=np.array([1500.0]),
    )
    got = _market(h).bar("AAA", D("2025-03-03"))
    assert got == Bar("AAA", D("2025-03-03"), Decimal("0.3000"), Decimal("10.1235"),
                      Decimal("0.0001"), Decimal("2.5000"), 1500)


def test_bar_is_none_for_a_missing_date_or_symbol():
    m = _market(history_from_bars("AAA", [bar("AAA", "2025-03-03", 10, 11, 9, 10)]))
    assert m.bar("AAA", D("2025-03-04")) is None
    assert m.bar("AAA", D("2025-02-28")) is None
    assert m.bar("ZZZ", D("2025-03-03")) is None


def test_bars_on_keeps_only_symbols_with_a_bar_that_day():
    a = [bar("AAA", "2025-03-03", 10, 11, 9, 10), bar("AAA", "2025-03-04", 10, 12, 9, 11)]
    b = [bar("BBB", "2025-03-03", 20, 21, 19, 20)]
    m = _market(history_from_bars("AAA", a), history_from_bars("BBB", b))
    assert m.bars_on(D("2025-03-04"), ("AAA", "BBB", "ZZZ")) == {"AAA": a[1]}
    assert m.bars_on(D("2025-03-03"), ["BBB", "AAA"]) == {"BBB": b[0], "AAA": a[0]}
    assert m.bars_on(D("2025-03-04"), ()) == {}


def test_last_bar_date():
    a = [bar("AAA", "2025-03-03", 10, 11, 9, 10), bar("AAA", "2025-03-05", 10, 12, 9, 11)]
    m = _market(history_from_bars("AAA", a))
    assert m.last_bar_date("AAA") == D("2025-03-05")
    assert m.last_bar_date("ZZZ") is None


# --------------------------------------------------------------------------- FX and SPY


def test_usd_idr_on_takes_the_latest_row_on_or_before():
    m = _market(fx=((D("2025-03-03"), Decimal("16000.0000")), (D("2025-03-05"), Decimal("16500.5000"))))
    assert m.usd_idr_on(D("2025-03-03")) == Decimal("16000.0000")
    assert m.usd_idr_on(D("2025-03-04")) == Decimal("16000.0000")
    assert m.usd_idr_on(D("2025-03-05")) == Decimal("16500.5000")
    assert m.usd_idr_on(D("2026-01-01")) == Decimal("16500.5000")
    with pytest.raises(ValueError):
        m.usd_idr_on(D("2025-03-02"))


def test_fx_must_be_ascending_decimals():
    with pytest.raises(ValueError):
        _market(fx=((D("2025-03-05"), Decimal("1")), (D("2025-03-03"), Decimal("1"))))
    with pytest.raises(TypeError):
        _market(fx=((D("2025-03-05"), 16000.0),))
    with pytest.raises(ValueError):
        _market(fx=((D("2025-03-05"), Decimal("0")),))


def test_history_key_must_match_its_symbol():
    h = history_from_bars("AAA", [bar("AAA", "2025-03-03", 10, 11, 9, 10)])
    with pytest.raises(ValueError):
        Market(history={"BBB": h}, membership=Membership(()), fx=())


def test_spy_returns_every_spy_bar_as_decimal_bars():
    spy = [bar(SPY, "2025-03-03", "580.1", "585.25", "578", "583.4567", 50_000_000),
           bar(SPY, "2025-03-04", "583", "590", "582.5", "589.0001", 60_000_000)]
    m = _market(history_from_bars(SPY, spy), history_from_bars("AAA", [bar("AAA", "2025-03-03", 1, 2, 1, 1)]))
    got = m.spy()
    assert got == {b.date: b for b in spy}
    assert list(got) == [D("2025-03-03"), D("2025-03-04")]
    assert _market().spy() == {}
