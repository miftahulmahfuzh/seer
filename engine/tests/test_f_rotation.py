"""Families F2/F3: ETF rotation (plan phase 6; handover §4.B F2/F3, §7 R3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import allocatorkit
import numpy as np
import pytest
from stratkit import drop_days, hist, mutate_from, session_days, truncate_before

from seer_engine.dates import prev_session
from seer_engine.prices import to_decimal
from seer_engine.sim import Target, equal_weight, q
from seer_engine.strategies.allocator import Allocator
from seer_engine.strategies.base import History
from seer_engine.strategies.f_rotation import (
    ROTATION,
    RotationAllocator,
    RotationParams,
    RotationPrepared,
)

DAYS = session_days(12)
D = DAYS[-1]  # the data_date of every hand-checked case
NOTHING: frozenset[str] = frozenset()


def flat_then(last: float, base: float = 100.0, n: int = 12) -> list[float]:
    """``n`` closes: ``base`` repeated, then ``last`` on the final session (D)."""
    return [base] * (n - 1) + [last]


def tgt(symbol: str, weight: str, close: float) -> Target:
    return Target(symbol, Decimal(weight), q(to_decimal(close)))


def run(history: dict[str, History], params: RotationParams, held: frozenset[str] = NOTHING) -> tuple[Target, ...]:
    """ROTATION.targets on D, after checking targets_prepared agrees."""
    got = ROTATION.targets(history, NOTHING, D, held, params)
    assert ROTATION.targets_prepared(ROTATION.prepare(history), NOTHING, D, held, params) == got
    return got


def P(universe: tuple[str, ...] = ("AAA", "BBB", "CCC"), lookback: int = 2, top: int = 1, **kw: object) -> RotationParams:
    return RotationParams(universe, lookback, top, **kw)  # type: ignore[arg-type]


IEF = hist("IEF", [80.0] * 12)


# ---- params -------------------------------------------------------------------------------


def test_params_defaults_and_as_dict():
    p = RotationParams(("QQQ", "SPY"), 252, 1)
    assert (p.absolute, p.fallback, p.trend) == (True, None, None)
    assert p.as_dict() == {
        "universe": "QQQ,SPY",
        "lookback": "252",
        "top": "1",
        "absolute": "true",
        "fallback": "none",
        "trend": "none",
    }
    full = RotationParams(("XLB", "XLE", "XLK"), 126, 3, False, "IEF", ("SPY", 200))
    assert full.as_dict() == {
        "universe": "XLB,XLE,XLK",
        "lookback": "126",
        "top": "3",
        "absolute": "false",
        "fallback": "IEF",
        "trend": "SPY:200",
    }
    assert list(full.as_dict()) == ["universe", "lookback", "top", "absolute", "fallback", "trend"]


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"universe": ["QQQ", "SPY"]}, TypeError),
        ({"universe": ("SPY", "QQQ")}, ValueError),  # not sorted
        ({"universe": ("QQQ", "QQQ")}, ValueError),  # not unique
        ({"universe": ("SPY",), "top": 1}, ValueError),  # < 2 ETFs
        ({"universe": ("QQQ", "")}, ValueError),
        ({"universe": ("QQQ", 1)}, TypeError),
        ({"lookback": 0}, ValueError),
        ({"lookback": True}, TypeError),
        ({"lookback": 2.0}, TypeError),
        ({"top": 0}, ValueError),
        ({"top": 3}, ValueError),  # > len(universe)
        ({"absolute": 1}, TypeError),
        ({"fallback": "SPY"}, ValueError),  # inside the universe
        ({"fallback": ""}, ValueError),
        ({"trend": ("SPY",)}, TypeError),
        ({"trend": ["SPY", 200]}, TypeError),
        ({"trend": ("SPY", 0)}, ValueError),
        ({"trend": (200, "SPY")}, TypeError),
    ],
)
def test_params_validation(kwargs, error):
    base = {"universe": ("QQQ", "SPY"), "lookback": 252, "top": 1}
    with pytest.raises(error):
        RotationParams(**{**base, **kwargs})


def test_params_are_frozen():
    p = RotationParams(("QQQ", "SPY"), 252, 1)
    with pytest.raises(AttributeError):
        p.top = 2  # type: ignore[misc]


# ---- the allocator's shape -----------------------------------------------------------------


def test_allocator_shape():
    assert isinstance(ROTATION, RotationAllocator)
    assert isinstance(ROTATION, Allocator)
    assert ROTATION.id == "ROT"
    plain = RotationParams(("QQQ", "SPY"), 252, 1)
    assert ROTATION.lookback(plain) == 253
    assert ROTATION.symbols(plain) == ("QQQ", "SPY")
    assert ROTATION.holds(plain) == ("QQQ", "SPY")
    assert ROTATION.uses_members(plain) is False
    full = RotationParams(("XLB", "XLE"), 126, 1, True, "IEF", ("SPY", 200))
    assert ROTATION.lookback(full) == 200  # the trend SMA needs more bars than the momentum
    assert ROTATION.symbols(full) == ("IEF", "SPY", "XLB", "XLE")
    assert ROTATION.holds(full) == ("IEF", "XLB", "XLE")  # reads SPY, never holds it
    short_trend = RotationParams(("XLB", "XLE"), 126, 1, True, None, ("XLE", 50))
    assert ROTATION.lookback(short_trend) == 127
    assert ROTATION.symbols(short_trend) == ("XLB", "XLE")


def test_wrong_types_raise():
    h = {"AAA": hist("AAA", flat_then(110.0))}
    for call in (
        lambda: ROTATION.lookback(object()),
        lambda: ROTATION.symbols(None),
        lambda: ROTATION.holds("x"),
        lambda: ROTATION.uses_members(1),
        lambda: ROTATION.targets(h, NOTHING, D, NOTHING, object()),
        lambda: ROTATION.targets_prepared(h, NOTHING, D, NOTHING, P()),
    ):
        with pytest.raises(TypeError):
            call()
    prepared = ROTATION.prepare(h)
    assert isinstance(prepared, RotationPrepared)
    with pytest.raises(TypeError):
        ROTATION.targets(h, NOTHING, D.isoformat(), NOTHING, P())  # type: ignore[arg-type]


# ---- ranking, top K, weights ---------------------------------------------------------------


def three(a: float, b: float, c: float) -> dict[str, History]:
    return {
        "AAA": hist("AAA", flat_then(a)),
        "BBB": hist("BBB", flat_then(b)),
        "CCC": hist("CCC", flat_then(c)),
    }


def test_ranks_by_momentum_highest_first():
    h = three(110.0, 120.0, 105.0)  # momentum 0.10, 0.20, 0.05
    assert run(h, P(top=1)) == (tgt("BBB", "1", 120.0),)
    assert run(h, P(top=2)) == (tgt("BBB", "0.5", 120.0), tgt("AAA", "0.5", 110.0))
    assert run(h, P(top=3)) == (
        tgt("BBB", "0.333333", 120.0),
        tgt("AAA", "0.333333", 110.0),
        tgt("CCC", "0.333333", 105.0),
    )
    assert equal_weight(3) == Decimal("0.333333")


def test_ties_are_broken_by_symbol():
    h = three(110.0, 110.0, 110.0)
    assert run(h, P(top=1)) == (tgt("AAA", "1", 110.0),)
    assert run(h, P(top=2)) == (tgt("AAA", "0.5", 110.0), tgt("BBB", "0.5", 110.0))
    h2 = three(105.0, 110.0, 110.0)
    assert run(h2, P(top=1)) == (tgt("BBB", "1", 110.0),)


def test_momentum_uses_exactly_lookback_sessions():
    # AAA: 50 six sessions back, 80 now -> +60% over 5 sessions, 0% over 2.
    # BBB: +10% over both.
    h = {
        "AAA": hist("AAA", [100.0] * 6 + [50.0] + [80.0] * 5),
        "BBB": hist("BBB", flat_then(110.0)),
    }
    assert run(h, P(("AAA", "BBB"), lookback=5)) == (tgt("AAA", "1", 80.0),)
    assert run(h, P(("AAA", "BBB"), lookback=2)) == (tgt("BBB", "1", 110.0),)
    # lookback 6 reaches the 100 before the dip: AAA -20%, BBB +10%.
    assert run(h, P(("AAA", "BBB"), lookback=6)) == (tgt("BBB", "1", 110.0),)


# ---- the absolute filter -------------------------------------------------------------------


def test_absolute_filter_leaves_non_positive_slots_unused():
    h = three(110.0, 95.0, 100.0)  # +0.10, -0.05, 0.00 (zero is not > 0)
    assert run(h, P(top=3)) == (tgt("AAA", "0.333333", 110.0),)
    assert run(h, P(top=3, absolute=False)) == (
        tgt("AAA", "0.333333", 110.0),
        tgt("CCC", "0.333333", 100.0),
        tgt("BBB", "0.333333", 95.0),
    )
    all_down = three(90.0, 95.0, 99.0)
    assert run(all_down, P(top=2)) == ()
    assert run(all_down, P(top=1, absolute=False)) == (tgt("CCC", "1", 99.0),)


# ---- the fallback --------------------------------------------------------------------------


def test_fallback_takes_the_unused_slots():
    h = {**three(110.0, 95.0, 90.0), "IEF": IEF}
    assert run(h, P(top=1, fallback="IEF")) == (tgt("AAA", "1", 110.0),)
    assert run(h, P(top=3, fallback="IEF")) == (tgt("AAA", "0.333333", 110.0), tgt("IEF", "0.666666", 80.0))
    assert run(h, P(top=2, fallback="IEF")) == (tgt("AAA", "0.5", 110.0), tgt("IEF", "0.5", 80.0))
    down = {**three(90.0, 95.0, 99.0), "IEF": IEF}
    assert run(down, P(top=1, fallback="IEF")) == (tgt("IEF", "1", 80.0),)
    assert run(down, P(top=3, fallback="IEF")) == (tgt("IEF", "0.999999", 80.0),)
    # every slot used: no fallback target
    assert run(down, P(top=2, absolute=False, fallback="IEF")) == (
        tgt("CCC", "0.5", 99.0),
        tgt("BBB", "0.5", 95.0),
    )


def test_fallback_without_a_bar_on_the_data_date_means_cash():
    base = three(110.0, 95.0, 90.0)
    gap = {**base, "IEF": drop_days(IEF, [D])}
    assert run(gap, P(top=3, fallback="IEF")) == (tgt("AAA", "0.333333", 110.0),)
    assert run(base, P(top=3, fallback="IEF")) == (tgt("AAA", "0.333333", 110.0),)  # not in the history at all
    zero = {**base, "IEF": hist("IEF", [80.0] * 11 + [0.00001])}  # rounds to 0.0000
    assert run(zero, P(top=3, fallback="IEF")) == (tgt("AAA", "0.333333", 110.0),)


# ---- the trend gate ------------------------------------------------------------------------


def test_trend_gate_on_and_off():
    rising = hist("SPY", [100.0 + t for t in range(12)])  # close 111 > SMA3 110
    falling = hist("SPY", [111.0 - t for t in range(12)])  # close 100 < SMA3 101
    flat = hist("SPY", [100.0] * 12)  # close == SMA3: not on (strict)
    base = {**three(110.0, 120.0, 105.0), "IEF": IEF}
    p = P(top=2, fallback="IEF", trend=("SPY", 3))
    assert run({**base, "SPY": rising}, p) == (tgt("BBB", "0.5", 120.0), tgt("AAA", "0.5", 110.0))
    assert run({**base, "SPY": falling}, p) == (tgt("IEF", "1", 80.0),)
    assert run({**base, "SPY": flat}, p) == (tgt("IEF", "1", 80.0),)
    no_fallback = P(top=2, trend=("SPY", 3))
    assert run({**base, "SPY": falling}, no_fallback) == ()


def test_trend_gate_is_off_without_the_signal_bars():
    base = {**three(110.0, 120.0, 105.0), "IEF": IEF}
    p = P(top=1, fallback="IEF", trend=("SPY", 3))
    rising = hist("SPY", [100.0 + t for t in range(12)])
    assert run({**base, "SPY": rising}, p) == (tgt("BBB", "1", 120.0),)
    assert run(base, p) == (tgt("IEF", "1", 80.0),)  # no SPY history
    assert run({**base, "SPY": drop_days(rising, [D])}, p) == (tgt("IEF", "1", 80.0),)  # no bar on D
    short = hist("SPY", [110.0, 111.0], days=DAYS[-2:])  # 2 bars < 3
    assert run({**base, "SPY": short}, p) == (tgt("IEF", "1", 80.0),)
    exactly = hist("SPY", [109.0, 110.0, 111.0], days=DAYS[-3:])  # 3 bars: SMA3 = 110 < 111
    assert run({**base, "SPY": exactly}, p) == (tgt("BBB", "1", 120.0),)


def test_trend_symbol_may_be_in_the_universe():
    h = three(110.0, 120.0, 105.0)
    p = P(top=1, trend=("AAA", 12))  # AAA: 100 × 11 then 110 > SMA12
    assert run(h, p) == (tgt("BBB", "1", 120.0),)
    assert ROTATION.symbols(p) == ("AAA", "BBB", "CCC")


# ---- missing and short ETFs ----------------------------------------------------------------


def test_missing_or_short_etfs_are_excluded_that_date():
    h = {
        "AAA": hist("AAA", [100.0, 300.0], days=DAYS[-2:]),  # 2 bars < lookback + 1 = 3
        "BBB": drop_days(hist("BBB", flat_then(200.0)), [D]),  # best, but no bar on D
        "CCC": hist("CCC", flat_then(105.0)),
        # DDD: not in the history at all
        "IEF": IEF,
    }
    p = P(("AAA", "BBB", "CCC", "DDD"), top=2, fallback="IEF")
    assert run(h, p) == (tgt("CCC", "0.5", 105.0), tgt("IEF", "0.5", 80.0))
    # exactly lookback + 1 bars is enough
    h["AAA"] = hist("AAA", [100.0, 100.0, 130.0], days=DAYS[-3:])
    assert run(h, p) == (tgt("AAA", "0.5", 130.0), tgt("CCC", "0.5", 105.0))


def test_a_close_that_rounds_to_zero_is_not_eligible():
    h = {"AAA": hist("AAA", flat_then(0.00001)), "BBB": hist("BBB", flat_then(90.0))}
    assert run(h, P(("AAA", "BBB"), top=2, absolute=False)) == (tgt("BBB", "0.5", 90.0),)


def test_a_zero_past_close_is_not_eligible():
    h = {"AAA": hist("AAA", [100.0] * 9 + [0.0, 100.0, 110.0]), "BBB": hist("BBB", flat_then(90.0))}
    assert run(h, P(("AAA", "BBB"), top=1, absolute=False)) == (tgt("BBB", "1", 90.0),)


# ---- held and members ----------------------------------------------------------------------


def test_held_is_passed_through_untouched_and_never_kept():
    h = {**three(110.0, 120.0, 95.0), "IEF": IEF}
    p = P(top=1, fallback="IEF")
    want = (tgt("BBB", "1", 120.0),)
    assert run(h, p) == want
    # AAA held and no longer the top: it is dropped (the engine signal-exits it at the open)
    assert run(h, p, held=frozenset({"AAA"})) == want
    assert run(h, p, held=frozenset({"BBB"})) == want  # held and still the top: same weight
    assert run(h, p, held=frozenset({"CCC", "IEF", "ZZZ"})) == want
    # a held ETF with a bar on D but negative momentum is dropped under the absolute filter
    assert run(h, P(top=3, fallback="IEF"), held=frozenset({"CCC"})) == (
        tgt("BBB", "0.333333", 120.0),
        tgt("AAA", "0.333333", 110.0),
        tgt("IEF", "0.333333", 80.0),
    )
    # a held ETF with no bar on D is excluded too (no momentum that date)
    gap = {**h, "BBB": drop_days(h["BBB"], [D])}
    assert run(gap, p, held=frozenset({"BBB"})) == (tgt("AAA", "1", 110.0),)


def test_members_are_ignored():
    h = three(110.0, 120.0, 105.0)
    p = P(top=2)
    want = ROTATION.targets(h, NOTHING, D, NOTHING, p)
    assert ROTATION.targets(h, frozenset({"AAA"}), D, NOTHING, p) == want
    assert ROTATION.targets(h, frozenset({"MSFT", "AAPL"}), D, NOTHING, p) == want


# ---- P4 identity and no look-ahead ---------------------------------------------------------

N = 200
CONTRACT_DAYS = session_days(N)


def walk(seed: int, n: int = N, drift: float = 0.0004, vol: float = 0.012) -> list[float]:
    rng = np.random.default_rng(seed)
    return [float(x) for x in np.round(100.0 * np.cumprod(1.0 + rng.normal(drift, vol, n)), 4)]


def contract_set() -> dict[str, History]:
    days = CONTRACT_DAYS
    return {
        "AAA": hist("AAA", walk(1)),
        "BBB": drop_days(hist("BBB", walk(2, drift=0.001)), [days[50], days[51], days[120]]),
        "CCC": hist("CCC", walk(3, drift=-0.0005)),
        "DDD": hist("DDD", walk(4, n=N - 80, drift=0.002), days=days[80:]),  # launches late
        "IEF": drop_days(hist("IEF", walk(5, vol=0.003)), [days[100], days[150]]),
        "SPY": hist("SPY", walk(6, drift=0.0006)),
    }


CONTRACT_PARAMS = (
    RotationParams(("AAA", "BBB", "CCC", "DDD"), 20, 1),
    RotationParams(("AAA", "BBB", "CCC", "DDD"), 20, 2, False, "IEF"),
    RotationParams(("AAA", "BBB", "CCC", "DDD"), 63, 3, True, "IEF", ("SPY", 50)),
    RotationParams(("AAA", "BBB"), 5, 2, True, "IEF", ("SPY", 10)),
)
HELDS = (NOTHING, frozenset({"AAA", "IEF"}), frozenset({"DDD", "ZZZ"}))


def check_targets(history: dict[str, History], d: date, params: RotationParams, got: tuple[Target, ...]) -> None:
    symbols = [t.symbol for t in got]
    assert len(set(symbols)) == len(symbols)
    assert set(symbols) <= set(ROTATION.holds(params))
    assert sum((t.weight for t in got), Decimal(0)) <= 1
    for t in got:
        i = history[t.symbol].index_of(d)
        assert i is not None  # never a target without a bar on d
        assert t.last == q(to_decimal(float(history[t.symbol].close[i])))
        assert (t.limit, t.stop, t.take) == (None, None, None)


def test_p4_identity_and_no_look_ahead():
    history = contract_set()
    prepared = ROTATION.prepare(history)
    sizes: set[int] = set()
    fallback_seen = 0
    for s in CONTRACT_DAYS[1:]:
        d = prev_session(s)
        upto = {k: h.upto(d) for k, h in history.items()}
        changed = {k: mutate_from(h, s) for k, h in history.items()}
        cut = {k: truncate_before(h, s) for k, h in history.items()}
        for params in CONTRACT_PARAMS:
            for held in HELDS:
                want = ROTATION.targets(upto, NOTHING, d, held, params)
                assert ROTATION.targets_prepared(prepared, NOTHING, d, held, params) == want, (s, params)
                assert ROTATION.targets(history, NOTHING, d, held, params) == want, (s, params)
                assert ROTATION.targets(changed, NOTHING, d, held, params) == want, (s, params)
                assert ROTATION.targets(cut, NOTHING, d, held, params) == want, (s, params)
                assert ROTATION.targets_prepared(ROTATION.prepare(changed), NOTHING, d, held, params) == want
                check_targets(history, d, params, want)
                sizes.add(len(want))
                fallback_seen += any(t.symbol == "IEF" for t in want)
    assert sizes >= {0, 1, 2, 3}  # not vacuous: empty, single, pair and triple target sets all occur
    assert fallback_seen > 0


def test_the_mutation_does_change_later_targets():
    # Guards test_p4_identity_and_no_look_ahead: read at data_date = s, the mutation is visible.
    history = contract_set()
    p = CONTRACT_PARAMS[1]
    changed_any = False
    for s in CONTRACT_DAYS[100:]:
        changed = {k: mutate_from(h, s, lambda x: x[::-1].copy()) for k, h in history.items()}
        if ROTATION.targets(changed, NOTHING, s, NOTHING, p) != ROTATION.targets(history, NOTHING, s, NOTHING, p):
            changed_any = True
            break
    assert changed_any


def test_allocatorkit_contract():
    history = contract_set()
    members = lambda d: NOTHING  # noqa: E731
    dates = [prev_session(s) for s in CONTRACT_DAYS[1::7]]
    assert allocatorkit.assert_p4_identity(ROTATION, history, members, dates, list(HELDS), list(CONTRACT_PARAMS)) > 0
    sessions = list(CONTRACT_DAYS[1::13])
    assert allocatorkit.assert_no_lookahead(ROTATION, history, members, sessions, list(HELDS), list(CONTRACT_PARAMS)) > 0
