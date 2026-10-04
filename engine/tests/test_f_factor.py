"""Families F4/F5/F6: stock factors (P7a phase 7; requirement R3).

Hand-computed features, eligibility, the three rankings, weights, the trend gate, held
semantics, P4 identity (prepared rows bit-identical to single-window rows) and no look-ahead.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal

import numpy as np
import pytest
from allocatorkit import assert_no_lookahead, assert_p4_identity
from stratkit import drop_days, hist, mutate_from, session_days, truncate_before

from seer_engine.dates import prev_session
from seer_engine.prices import to_decimal
from seer_engine.sim import q
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, equal_weight
from seer_engine.strategies.allocator import Allocator
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import (
    DV_N,
    EXCLUDED,
    FACTOR,
    FactorAllocator,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    factor_weights,
    rank_rows,
    targets_from_rows,
    trend_on,
)

# lookback 20: mom = c[-2]/c[-6] − 1, vol over 3 returns, no trend, no dollar-volume floor
SMALL = FactorParams("momentum", top=2, mom_n=5, mom_skip=1, vol_n=3, trend=None, min_dollar_volume=0.0)


def upto_all(history: dict[str, History], d: date) -> dict[str, History]:
    return {s: h.upto(d) for s, h in history.items()}


def wiggle(n: int, first: float = 50.0, growth: float = 0.0, amp: float = 0.2) -> list[float]:
    """Geometric growth with an alternating ±amp wiggle (volatility > 0, momentum monotone in growth)."""
    return [first * (1.0 + growth) ** t + (amp if t % 2 else -amp) for t in range(n)]


def walk(seed: int, n: int, first: float = 50.0, drift: float = 0.0003, sigma: float = 0.015) -> list[float]:
    rng = np.random.default_rng(seed)
    return [float(x) for x in first * np.cumprod(1.0 + rng.normal(drift, sigma, n))]


def py_stdev(c: Sequence[float], n: int) -> float:
    r = [c[i] / c[i - 1] - 1.0 for i in range(len(c) - n, len(c))]
    mean = r[0]
    for x in r[1:]:
        mean = mean + x
    mean = mean / n
    acc = (r[0] - mean) * (r[0] - mean)
    for x in r[1:]:
        acc = acc + (x - mean) * (x - mean)
    return math.sqrt(acc / n)


def py_dollar_volume(c: Sequence[float], v: Sequence[float]) -> float:
    first = len(c) - DV_N
    acc = c[first] * v[first]
    for j in range(first + 1, len(c)):
        acc = acc + c[j] * v[j]
    return acc / DV_N


def row(symbol: str, momentum: float, vol: float, close: float = 50.0) -> FactorRow:
    return FactorRow(symbol, close, momentum, vol, 1e9)


# ---- params, protocol ----------------------------------------------------------------------


def test_factor_implements_the_allocator_protocol():
    assert isinstance(FACTOR, FactorAllocator)
    assert isinstance(FACTOR, Allocator)
    assert FACTOR.id == "FAC"
    assert EXCLUDED == frozenset({"SPY"})


def test_defaults_are_the_contract_values():
    p = FactorParams("momentum")
    assert (p.top, p.mom_n, p.mom_skip, p.vol_n, p.pool) == (10, 252, 21, 60, 50)
    assert (p.sizing, p.min_dollar_volume, p.min_price, p.trend) == ("equal", 20_000_000.0, 5.0, ("SPY", 200))


def test_as_dict_is_plain_and_ordered():
    assert FactorParams("mom_lowvol", top=20, sizing="inverse_vol").as_dict() == {
        "rank": "mom_lowvol",
        "top": "20",
        "mom_n": "252",
        "mom_skip": "21",
        "vol_n": "60",
        "pool": "50",
        "sizing": "inverse_vol",
        "min_dollar_volume": "20000000",
        "min_price": "5",
        "trend": "SPY:200",
    }
    d = FactorParams("lowvol", trend=None, min_price=7.5, min_dollar_volume=1_500_000).as_dict()
    assert list(d) == ["rank", "top", "mom_n", "mom_skip", "vol_n", "pool", "sizing", "min_dollar_volume", "min_price", "trend"]
    assert (d["trend"], d["min_price"], d["min_dollar_volume"]) == ("none", "7.5", "1500000")


def test_int_floats_are_coerced():
    p = FactorParams("momentum", min_dollar_volume=0, min_price=5)
    assert isinstance(p.min_dollar_volume, float) and isinstance(p.min_price, float)


@pytest.mark.parametrize(
    "kw, exc",
    [
        ({"rank": "value"}, ValueError),
        ({"rank": 1}, TypeError),
        ({"top": 0}, ValueError),
        ({"top": 1001}, ValueError),
        ({"top": True}, TypeError),
        ({"top": 2.0}, TypeError),
        ({"mom_n": 1}, ValueError),
        ({"mom_skip": -1}, ValueError),
        ({"mom_n": 21, "mom_skip": 21}, ValueError),
        ({"vol_n": 1}, ValueError),
        ({"pool": 0}, ValueError),
        ({"rank": "mom_lowvol", "top": 11, "pool": 10}, ValueError),
        ({"sizing": "risk_parity"}, ValueError),
        ({"min_dollar_volume": -1.0}, ValueError),
        ({"min_dollar_volume": float("nan")}, ValueError),
        ({"min_dollar_volume": "1"}, TypeError),
        ({"min_price": 0.0}, ValueError),
        ({"min_price": float("inf")}, ValueError),
        ({"trend": ["SPY", 200]}, TypeError),
        ({"trend": ("SPY",)}, TypeError),
        ({"trend": ("", 200)}, ValueError),
        ({"trend": ("SPY", 0)}, ValueError),
        ({"trend": ("SPY", 200.0)}, TypeError),
    ],
)
def test_params_reject_bad_values(kw, exc):
    kw = {"rank": "momentum", **kw}
    with pytest.raises(exc):
        FactorParams(**kw)


def test_pool_below_top_is_fine_outside_mom_lowvol():
    assert FactorParams("momentum", top=20, pool=5).pool == 5


@pytest.mark.parametrize(
    "params, expected",
    [
        (FactorParams("momentum"), 253),
        (FactorParams("momentum", mom_n=126), 200),  # the SPY 200-day trend dominates
        (FactorParams("momentum", mom_n=126, trend=None), 127),
        (FactorParams("lowvol", vol_n=252), 253),
        (SMALL, 20),  # the 20-day dollar volume dominates
        (FactorParams("lowvol", trend=("SPY", 300)), 300),
    ],
)
def test_lookback_covers_every_window(params, expected):
    assert factor_lookback(params) == expected
    assert FACTOR.lookback(params) == expected


def test_symbols_holds_and_members():
    assert FACTOR.symbols(FactorParams("momentum")) == ("SPY",)
    assert FACTOR.symbols(FactorParams("momentum", trend=("QQQ", 100))) == ("QQQ",)
    assert FACTOR.symbols(FactorParams("momentum", trend=None)) == ()
    assert FACTOR.holds(FactorParams("momentum")) == ()
    assert FACTOR.uses_members(FactorParams("lowvol")) is True


def test_wrong_types_raise():
    days = session_days(30)
    history = {"AAA": hist("AAA", wiggle(30), days=days)}
    d = days[-1]
    with pytest.raises(TypeError):
        FACTOR.targets(history, {"AAA"}, d, frozenset(), object())
    with pytest.raises(TypeError):
        FACTOR.targets(history, {"AAA"}, d, ["AAA"], SMALL)
    with pytest.raises(TypeError):
        FACTOR.targets(history, {"AAA"}, datetime(2019, 2, 13), frozenset(), SMALL)
    with pytest.raises(TypeError):
        FACTOR.targets_prepared(object(), {"AAA"}, d, frozenset(), SMALL)
    with pytest.raises(TypeError):
        FACTOR.targets_prepared(FACTOR.prepare(history), {"AAA"}, d, frozenset(), "params")
    with pytest.raises(TypeError):
        FACTOR.lookback(None)


# ---- hand-computed features ----------------------------------------------------------------


def test_12_1_momentum_vol_and_dollar_volume_hand_computed():
    days = session_days(260)
    c = wiggle(260, growth=0.001)
    v = [1_000_000.0 + 1000.0 * t for t in range(260)]
    history = {"AAA": hist("AAA", c, days=days, volumes=v)}
    params = FactorParams("momentum", trend=None)
    [r] = factor_rows(history, {"AAA"}, days[-1], params)
    assert r.symbol == "AAA"
    assert r.close == c[-1]
    assert r.momentum == c[259 - 21] / c[259 - 252] - 1.0  # 12-1: skip the last month
    assert r.vol == py_stdev(c, 60)
    assert r.dollar_volume == py_dollar_volume(c, v)


def test_6_1_momentum_hand_computed():
    days = session_days(260)
    c = wiggle(260, growth=0.002)
    history = {"AAA": hist("AAA", c, days=days)}
    [r] = factor_rows(history, {"AAA"}, days[-1], FactorParams("momentum", mom_n=126, trend=None))
    assert r.momentum == c[259 - 21] / c[259 - 126] - 1.0


def test_vol_window_follows_vol_n():
    days = session_days(260)
    c = walk(3, 260)
    history = {"AAA": hist("AAA", c, days=days)}
    [r] = factor_rows(history, {"AAA"}, days[-1], FactorParams("lowvol", vol_n=252, trend=None))
    assert r.vol == py_stdev(c, 252)


def test_features_read_only_bars_through_data_date():
    days = session_days(40)
    c = wiggle(40, growth=0.01)
    history = {"AAA": hist("AAA", c, days=days)}
    d = days[29]
    [r] = factor_rows(history, {"AAA"}, d, SMALL)
    assert r.close == c[29]
    assert r.momentum == c[28] / c[24] - 1.0
    assert r.vol == py_stdev(c[:30], 3)
    assert factor_rows(upto_all(history, d), {"AAA"}, d, SMALL) == [r]


# ---- eligibility ---------------------------------------------------------------------------


def test_eligibility_each_condition():
    days = session_days(30)
    d = days[-1]
    history = {
        "OK": hist("OK", wiggle(30), days=days),
        "EXACT": hist("EXACT", wiggle(20), days=days[10:]),  # exactly lookback (20) bars through d
        "SHORT": hist("SHORT", wiggle(19), days=days[11:]),  # one bar short
        "GAP": hist("GAP", wiggle(29), days=days[:29]),  # no bar dated d
        "NONMEM": hist("NONMEM", wiggle(30), days=days),  # not a member
        "SPY": hist("SPY", wiggle(30, growth=0.05), days=days),  # a member here, never a target
        "FLAT": hist("FLAT", [50.0] * 30, days=days),  # volatility 0
    }
    members = frozenset(history) - {"NONMEM"} | {"ABSENT"}  # ABSENT has no history at all
    assert [r.symbol for r in factor_rows(history, members, d, SMALL)] == ["EXACT", "OK"]
    prepared = FACTOR.prepare(history)
    assert prepared.rows_on(members, d, SMALL) == factor_rows(history, members, d, SMALL)


def test_dollar_volume_floor_is_strict():
    days = session_days(30)
    c = wiggle(30)
    history = {"AAA": hist("AAA", c, days=days, volume=400_000.0)}
    dv = py_dollar_volume(c, [400_000.0] * 30)
    at = FactorParams("momentum", top=2, mom_n=5, mom_skip=1, vol_n=3, trend=None, min_dollar_volume=dv)
    below = FactorParams("momentum", top=2, mom_n=5, mom_skip=1, vol_n=3, trend=None, min_dollar_volume=dv - 1.0)
    assert factor_rows(history, {"AAA"}, days[-1], at) == []
    assert [r.symbol for r in factor_rows(history, {"AAA"}, days[-1], below)] == ["AAA"]


@pytest.mark.parametrize("last, eligible", [(5.0, True), (4.99, False), (5.01, True)])
def test_min_price_is_inclusive(last, eligible):
    days = session_days(30)
    c = wiggle(29, first=6.0, amp=0.1) + [last]
    history = {"AAA": hist("AAA", c, days=days)}
    got = factor_rows(history, {"AAA"}, days[-1], SMALL)
    assert bool(got) is eligible


# ---- rankings ------------------------------------------------------------------------------


def test_momentum_ranking_desc_with_symbol_tiebreak():
    rows = [row("CCC", 0.10, 0.02), row("BBB", 0.30, 0.01), row("AAA", 0.30, 0.03), row("DDD", -0.05, 0.01)]
    p = FactorParams("momentum", top=3)
    assert [r.symbol for r in rank_rows(rows, p)] == ["AAA", "BBB", "CCC"]


def test_lowvol_ranking_asc_with_symbol_tiebreak():
    rows = [row("CCC", 0.10, 0.02), row("BBB", 0.30, 0.01), row("AAA", -0.30, 0.01), row("DDD", 0.5, 0.05)]
    p = FactorParams("lowvol", top=3)
    assert [r.symbol for r in rank_rows(rows, p)] == ["AAA", "BBB", "CCC"]


def test_mom_lowvol_takes_the_lowest_vol_inside_the_momentum_pool():
    rows = [
        row("AAA", 0.30, 0.03),
        row("BBB", 0.20, 0.01),
        row("CCC", 0.10, 0.005),  # the calmest name, but outside the 3-name momentum pool
        row("DDD", 0.25, 0.02),
    ]
    p = FactorParams("mom_lowvol", top=2, pool=3)
    assert [r.symbol for r in rank_rows(rows, p)] == ["BBB", "DDD"]
    assert [r.symbol for r in rank_rows(rows, FactorParams("mom_lowvol", top=2, pool=4))] == ["CCC", "BBB"]


def test_mom_lowvol_pool_ties_by_symbol():
    rows = [row("BBB", 0.2, 0.01), row("AAA", 0.2, 0.02), row("CCC", 0.1, 0.001)]
    assert [r.symbol for r in rank_rows(rows, FactorParams("mom_lowvol", top=1, pool=1))] == ["AAA"]


def test_end_to_end_momentum_ranking_on_bars():
    days = session_days(30)
    history = {
        "AAA": hist("AAA", wiggle(30, growth=0.002), days=days),
        "BBB": hist("BBB", wiggle(30, growth=0.004), days=days),
        "CCC": hist("CCC", wiggle(30, growth=0.001), days=days),
        "TWIN": hist("TWIN", wiggle(30, growth=0.004), days=days),  # ties BBB exactly
    }
    got = FACTOR.targets(history, frozenset(history), days[-1], frozenset(), SMALL)
    assert [t.symbol for t in got] == ["BBB", "TWIN"]


def test_end_to_end_lowvol_ranking_on_bars():
    days = session_days(30)
    history = {
        "CALM": hist("CALM", wiggle(30, amp=0.05), days=days),
        "MID": hist("MID", wiggle(30, amp=0.2), days=days),
        "WILD": hist("WILD", wiggle(30, amp=1.0), days=days),
    }
    p = FactorParams("lowvol", top=2, mom_n=5, mom_skip=1, vol_n=3, trend=None, min_dollar_volume=0.0)
    got = FACTOR.targets(history, frozenset(history), days[-1], frozenset(), p)
    assert [t.symbol for t in got] == ["CALM", "MID"]


# ---- weights and targets -------------------------------------------------------------------


def test_equal_weights_use_top_even_when_fewer_names_qualify():
    chosen = [row("AAA", 0.3, 0.01), row("BBB", 0.2, 0.02)]
    assert factor_weights(chosen, FactorParams("momentum", top=4)) == [Decimal("0.25"), Decimal("0.25")]
    assert factor_weights(chosen, FactorParams("momentum", top=3)) == [equal_weight(3)] * 2
    assert factor_weights([], FactorParams("momentum", top=3)) == []


def test_inverse_vol_weights_hand_computed():
    chosen = [row("AAA", 0.3, 0.01), row("BBB", 0.2, 0.02)]
    full = FactorParams("momentum", top=2, sizing="inverse_vol")
    half = FactorParams("momentum", top=4, sizing="inverse_vol")
    assert factor_weights(chosen, full) == [Decimal("0.666666"), Decimal("0.333333")]  # 100/150, 50/150
    assert factor_weights(chosen, half) == [Decimal("0.333333"), Decimal("0.166666")]  # × 2/4


def test_inverse_vol_weights_are_quantized_and_sum_to_at_most_one():
    rng = np.random.default_rng(7)
    for top in (1, 3, 10, 20, 50):
        vols = rng.uniform(0.002, 0.08, top)
        chosen = [row(f"S{k:03d}", 0.1, float(v)) for k, v in enumerate(vols)]
        weights = factor_weights(chosen, FactorParams("momentum", top=top, sizing="inverse_vol"))
        assert all(w is not None and w > 0 and w % WEIGHT_QUANTUM == 0 for w in weights)
        assert sum(weights) <= Decimal(1)
        assert sum(weights) > Decimal(1) - Decimal(top) * WEIGHT_QUANTUM
        calmest = int(np.argmin(vols))
        assert weights[calmest] == max(weights)  # calmer -> heavier


def test_inverse_vol_drops_a_weight_that_floors_to_zero():
    chosen = [row("CALM", 0.3, 1e-9), row("WILD", 0.2, 1.0)]
    params = FactorParams("lowvol", top=2, sizing="inverse_vol")
    assert factor_weights(chosen, params) == [Decimal("0.999999"), None]
    assert [t.symbol for t in targets_from_rows(chosen, params)] == ["CALM"]


def test_targets_are_priced_at_the_close_without_brackets():
    days = session_days(30)
    c = wiggle(30, growth=0.003)
    history = {"AAA": hist("AAA", c, days=days), "BBB": hist("BBB", wiggle(30, growth=0.001), days=days)}
    got = FACTOR.targets(history, frozenset(history), days[-1], frozenset(), SMALL)
    assert got[0] == Target("AAA", equal_weight(2), q(to_decimal(c[-1])))
    assert all(t.limit is None and t.stop is None and t.take is None for t in got)
    assert sum(t.weight for t in got) <= 1


def test_members_only_and_spy_never_a_target():
    days = session_days(30)
    history = {
        "SPY": hist("SPY", wiggle(30, growth=0.02), days=days),  # the strongest momentum
        "AAA": hist("AAA", wiggle(30, growth=0.002), days=days),
        "OUT": hist("OUT", wiggle(30, growth=0.01), days=days),
    }
    members = frozenset({"SPY", "AAA"})
    for params in (SMALL, FactorParams("lowvol", top=3, mom_n=5, mom_skip=1, vol_n=3, trend=None, min_dollar_volume=0.0)):
        got = FACTOR.targets(history, members, days[-1], frozenset(), params)
        assert [t.symbol for t in got] == ["AAA"]
        assert FACTOR.targets_prepared(FACTOR.prepare(history), members, days[-1], frozenset(), params) == got


# ---- trend gate ----------------------------------------------------------------------------

TRENDED = FactorParams("momentum", top=2, mom_n=5, mom_skip=1, vol_n=3, trend=("SPY", 10), min_dollar_volume=0.0)


def gate_history(spy: list[float] | None, spy_days: list[date] | None = None) -> tuple[list[date], dict[str, History]]:
    days = session_days(30)
    history = {"AAA": hist("AAA", wiggle(30, growth=0.002), days=days)}
    if spy is not None:
        history["SPY"] = hist("SPY", spy, days=spy_days or days[: len(spy)])
    return days, history


@pytest.mark.parametrize(
    "case, on",
    [
        ("rising", True),
        ("falling", False),
        ("flat", False),  # close == SMA: strict
        ("missing", False),
        ("no_bar_on_d", False),
        ("short", False),  # fewer than n bars through d
    ],
)
def test_trend_gate(case, on):
    days = session_days(30)
    spy = {
        "rising": ([100.0 + t for t in range(30)], days),
        "falling": ([200.0 - t for t in range(30)], days),
        "flat": ([100.0] * 30, days),
        "missing": (None, None),
        "no_bar_on_d": ([100.0 + t for t in range(29)], days[:29]),
        "short": ([100.0 + t for t in range(9)], days[21:]),
    }[case]
    _, history = gate_history(*spy)
    d = days[-1]
    assert trend_on(history, d, TRENDED) is on
    got = FACTOR.targets(history, frozenset({"AAA"}), d, frozenset(), TRENDED)
    assert bool(got) is on
    assert FACTOR.targets_prepared(FACTOR.prepare(history), frozenset({"AAA"}), d, frozenset(), TRENDED) == got


def test_trend_gate_reads_only_through_data_date():
    days = session_days(30)
    spy = [100.0 + t for t in range(25)] + [10.0] * 5  # collapses after days[24]
    _, history = gate_history(spy, days)
    assert trend_on(history, days[24], TRENDED) is True
    assert trend_on(history, days[29], TRENDED) is False


def test_no_trend_means_always_on():
    _, history = gate_history(None)
    assert trend_on(history, session_days(30)[-1], SMALL) is True


# ---- held semantics ------------------------------------------------------------------------


def test_held_names_are_kept_only_if_they_rank_in_the_new_top():
    days = session_days(30)
    history = {
        "AAA": hist("AAA", wiggle(30, growth=0.004), days=days),
        "BBB": hist("BBB", wiggle(30, growth=0.003), days=days),
        "CCC": hist("CCC", wiggle(30, growth=0.001), days=days),  # third: outside top 2
    }
    members = frozenset(history)
    d = days[-1]
    fresh = FACTOR.targets(history, members, d, frozenset(), SMALL)
    assert [t.symbol for t in fresh] == ["AAA", "BBB"]
    for held in (frozenset({"CCC"}), frozenset({"AAA", "CCC"}), frozenset({"AAA", "BBB"}), frozenset({"GONE"})):
        assert FACTOR.targets(history, members, d, held, SMALL) == fresh
        assert FACTOR.targets_prepared(FACTOR.prepare(history), members, d, held, SMALL) == fresh


# ---- P4 identity ---------------------------------------------------------------------------


def contract_set() -> tuple[list[date], dict[str, History]]:
    days = session_days(330)
    history = {s: hist(s, walk(k, 330), days=days) for k, s in enumerate(("AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH"))}
    history["TWIN"] = hist("TWIN", [float(x) for x in history["AAA"].close], days=days)  # ties with AAA
    history["LATE"] = hist("LATE", walk(20, 250, first=30.0), days=days[80:])
    history["GONE"] = hist("GONE", walk(21, 280, first=70.0), days=days[:280])
    history["GAPPY"] = drop_days(hist("GAPPY", walk(22, 330), days=days), days[100:105] + [days[250]])
    history["THIN"] = hist("THIN", walk(23, 330), days=days, volume=1000.0)
    cheap = [5.0 + 0.6 * math.sin(t / 15.0) + (0.05 if t % 2 else -0.05) for t in range(330)]
    history["CHEAP"] = hist("CHEAP", cheap, days=days, volume=10_000_000.0)  # crosses min_price = 5 often
    history["SPY"] = hist("SPY", walk(30, 330, first=100.0, drift=0.0004, sigma=0.02), days=days)
    return days, history


def contract_members(days: list[date]):
    def members(d: date) -> frozenset[str]:
        out = {"AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH", "TWIN", "GONE", "GAPPY", "THIN", "CHEAP", "SPY"}
        if d >= days[200]:
            out.add("LATE")
        if days[240] <= d < days[260]:
            out.discard("BBB")
        return frozenset(out)

    return members


CONTRACT_PARAMS = [
    FactorParams("momentum", top=3, mom_n=40, mom_skip=5, vol_n=20, trend=None),
    FactorParams("lowvol", top=4, mom_n=40, mom_skip=5, vol_n=30, trend=("SPY", 30)),
    FactorParams("mom_lowvol", top=2, pool=5, mom_n=60, mom_skip=10, vol_n=20, sizing="inverse_vol", trend=("SPY", 50)),
    FactorParams("momentum", top=4, mom_n=20, mom_skip=0, vol_n=10, sizing="inverse_vol", trend=None),
]


@pytest.mark.parametrize("params", CONTRACT_PARAMS, ids=["mom", "lowvol-trend", "ml-ivol-trend", "mom-noskip-ivol"])
def test_prepared_rows_are_bit_identical_and_targets_equal(params):
    days, history = contract_set()
    members = contract_members(days)
    prepared = FACTOR.prepare(history)
    assert isinstance(prepared, FactorPrepared)
    nonempty = 0
    for d in days[15:]:
        visible = upto_all(history, d)
        m = members(d)
        rows = factor_rows(visible, m, d, params)
        assert prepared.rows_on(m, d, params) == rows, d  # bit-identical floats
        assert factor_rows(history, m, d, params) == rows, d  # later bars ignored
        for held in (frozenset(), frozenset({"AAA", "GONE"})):
            expected = FACTOR.targets(visible, m, d, held, params)
            assert FACTOR.targets_prepared(prepared, m, d, held, params) == expected, d
            assert FACTOR.targets(history, m, d, held, params) == expected, d
            assert sum(t.weight for t in expected) <= 1
            assert "SPY" not in {t.symbol for t in expected}
            nonempty += bool(expected)
    assert nonempty > 100


def test_default_params_identity_on_a_long_history():
    days, history = contract_set()
    members = contract_members(days)
    prepared = FACTOR.prepare(history)
    for params in (FactorParams("momentum"), FactorParams("mom_lowvol", top=3, pool=6, sizing="inverse_vol")):
        nonempty = 0
        for d in days[250:]:
            visible = upto_all(history, d)
            m = members(d)
            assert prepared.rows_on(m, d, params) == factor_rows(visible, m, d, params), d
            expected = FACTOR.targets(visible, m, d, frozenset(), params)
            assert FACTOR.targets_prepared(prepared, m, d, frozenset(), params) == expected, d
            nonempty += bool(expected)
        assert nonempty > 0


def test_prepared_caches_each_feature_column_once():
    days, history = contract_set()
    prepared = FACTOR.prepare(history)
    p = CONTRACT_PARAMS[0]
    prepared.rows_on(frozenset(history), days[100], p)
    col = prepared.column(("mom", p.mom_n, p.mom_skip))
    prepared.rows_on(frozenset(history), days[101], p)
    assert prepared.column(("mom", p.mom_n, p.mom_skip)) is col
    assert set(prepared.cache) == {("mom", 40, 5), ("vol", 20)}
    assert not col.flags.writeable


def test_prepare_on_short_or_empty_history():
    short = {"X": hist("X", wiggle(DV_N - 1))}
    d = session_days(DV_N - 1)[-1]
    for history in ({}, short):
        prepared = FACTOR.prepare(history)
        assert prepared.rows_on({"X"}, d, SMALL) == []
        assert FACTOR.targets_prepared(prepared, {"X"}, d, frozenset(), SMALL) == ()
        assert FACTOR.targets(history, {"X"}, d, frozenset(), SMALL) == ()


def test_allocatorkit_p4_identity():
    days, history = contract_set()
    members = contract_members(days)
    held_sets = [frozenset(), frozenset({"AAA", "GONE"})]
    assert assert_p4_identity(FACTOR, history, members, days[40::7], held_sets, CONTRACT_PARAMS) > 0


# ---- no look-ahead -------------------------------------------------------------------------


@pytest.mark.parametrize("mutation", ["change", "truncate"])
def test_no_look_ahead(mutation):
    """Changing (or deleting) every bar dated on or after S leaves S's targets unchanged."""
    days, history = contract_set()
    members = contract_members(days)
    prepared = FACTOR.prepare(history)
    nonempty = 0
    for s in days[70::9]:
        data_date = prev_session(s)
        if mutation == "change":
            future = {k: mutate_from(h, s) for k, h in history.items()}
        else:
            future = {k: truncate_before(h, s) for k, h in history.items()}
        future_prepared = FACTOR.prepare(future)
        m = members(data_date)
        for params in CONTRACT_PARAMS:
            before = FACTOR.targets(history, m, data_date, frozenset(), params)
            assert FACTOR.targets(future, m, data_date, frozenset(), params) == before, s
            assert FACTOR.targets_prepared(future_prepared, m, data_date, frozenset(), params) == before, s
            assert FACTOR.targets_prepared(prepared, m, data_date, frozenset(), params) == before, s
            nonempty += bool(before)
    assert nonempty >= 10


def test_the_mutation_does_change_rows_read_on_s():
    # Guards test_no_look_ahead: the same mutation, read at data_date = S, changes the features.
    days, history = contract_set()
    members = contract_members(days)
    s = days[200]
    future = {k: mutate_from(h, s) for k, h in history.items()}
    p = CONTRACT_PARAMS[0]
    assert factor_rows(future, members(s), s, p) != factor_rows(history, members(s), s, p)


def test_allocatorkit_no_look_ahead():
    days, history = contract_set()
    members = contract_members(days)
    assert assert_no_lookahead(FACTOR, history, members, days[70::23], [frozenset()], CONTRACT_PARAMS) > 0
