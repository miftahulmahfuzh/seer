"""P7a phase 2: the Allocator protocol, its helpers, PICKS, BLEND, VOLTARGET, return_window, and the kit.

The P4 identity and no-look-ahead checks run through tests/allocatorkit.py, which phases 5–8
reuse; the kit's own checks are tested here against deliberately broken allocators.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
import pytest
from allocatorkit import (
    FIXED,
    MOMENTUM,
    FixedParams,
    MomentumParams,
    assert_no_lookahead,
    assert_p4_identity,
    assert_valid_targets,
    everyone,
    upto,
)
from stratkit import dip, drop_days, hist, sawtooth, session_days, uptrend

from seer_engine.dates import prev_session, sessions
from seer_engine.sim import Pick
from seer_engine.sim.book import Target
from seer_engine.strategies import STRATEGY_A, AParams, Strategy
from seer_engine.strategies.allocator import (
    BLEND,
    PICKS,
    VOLTARGET,
    Allocator,
    BlendAllocator,
    BlendParams,
    BlendPart,
    LazyPrepared,
    PicksAllocator,
    PicksParams,
    VolTargetAllocator,
    VolTargetParams,
    last_close,
    month_end_closes,
    scale_weight,
    target_from_close,
    vol_scale,
)
from seer_engine.strategies.indicators import return_window, rolling

D = Decimal
PERMISSIVE = AParams(rsi_max=100.0, min_dollar_volume=0.0)


def rows(*r: list[float]) -> np.ndarray:
    return np.array(r, dtype=np.float64)


# ---- fakes local to this module ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConstParams:
    targets: tuple[Target, ...]
    holds: tuple[str, ...] = ()
    lookback: int = 1

    def as_dict(self) -> dict[str, str]:
        return {"targets": ",".join(t.symbol for t in self.targets)}


class ConstAllocator:
    """Returns ``params.targets`` verbatim and records every ``held`` it was called with."""

    id = "FAKE_CONST"

    def __init__(self) -> None:
        self.seen_held: list[frozenset[str]] = []
        self.prepare_calls = 0

    def lookback(self, params: Any) -> int:
        return params.lookback

    def symbols(self, params: Any) -> tuple[str, ...]:
        return tuple(sorted({t.symbol for t in params.targets}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return params.holds

    def uses_members(self, params: Any) -> bool:
        return False

    def targets(self, history, members, data_date, held, params):
        self.seen_held.append(held)
        return params.targets

    def prepare(self, history):
        self.prepare_calls += 1
        return "prepared"

    def targets_prepared(self, prepared, members, data_date, held, params):
        assert prepared == "prepared"
        return self.targets({}, members, data_date, held, params)


class MembersFake(ConstAllocator):
    id = "FAKE_MEMBERS"

    def uses_members(self, params: Any) -> bool:
        return True


class ListStrategy:
    """A Strategy returning a fixed pick list; counts prepare calls."""

    id = "LIST"
    lookback = 3

    def __init__(self, picks: list[Pick]) -> None:
        self._picks = picks
        self.prepare_calls = 0

    def picks(self, history, members, data_date, params):
        return list(self._picks)

    def prepare(self, history):
        self.prepare_calls += 1
        return None

    def picks_prepared(self, prepared, members, data_date, params):
        return list(self._picks)


class PeekAllocator:
    """BROKEN on purpose: reads each history's very last bar, whatever the data date."""

    id = "FAKE_PEEK"

    def lookback(self, params):
        return 1

    def symbols(self, params):
        return ()

    def holds(self, params):
        return ()

    def uses_members(self, params):
        return True

    def targets(self, history, members, data_date, held, params):
        out = []
        for s in sorted(history):
            h = history[s]
            i = h.index_of(data_date)
            if s in members and i is not None and h.close[-1] > h.close[i]:  # "a later bar is higher"
                out.append(target_from_close(s, float(h.close[i]), D("0.1")))
        return tuple(out)

    def prepare(self, history):
        return dict(history)

    def targets_prepared(self, prepared, members, data_date, held, params):
        return self.targets(prepared, members, data_date, held, params)


class ForgetfulAllocator(PeekAllocator):
    """BROKEN on purpose: honest single-window targets, but the prepared path returns nothing."""

    id = "FAKE_FORGET"

    def targets(self, history, members, data_date, held, params):
        return tuple(
            target_from_close(s, float(history[s].close[history[s].index_of(data_date)]), D("0.1"))
            for s in sorted(history)
            if s in members and history[s].index_of(data_date) is not None
        )

    def targets_prepared(self, prepared, members, data_date, held, params):
        return ()


def t(symbol: str, weight: str, last: str = "10", **prices: str) -> Target:
    return Target(symbol=symbol, weight=D(weight), last=D(last), **{k: D(v) for k, v in prices.items()})


# ---- return_window ------------------------------------------------------------------------


def test_return_window_hand_computed():
    assert return_window(rows([100, 110, 121]), 2).tolist() == [121.0 / 100.0 - 1.0]
    # Two rows, each its own window: 30/20 - 1 and 9/12 - 1.
    assert return_window(rows([10, 20, 30], [12, 3, 9]), 1).tolist() == [30.0 / 20.0 - 1.0, 9.0 / 3.0 - 1.0]


def test_return_window_reads_only_the_two_end_columns():
    # n = 2: c[-1] / c[-3] - 1; columns 0 and -2 are ignored.
    assert return_window(rows([999, 100, 7, 110]), 2).tolist() == [110.0 / 100.0 - 1.0]


def test_return_window_skip_is_the_12_1_shape():
    # n = 3, skip = 1: c[-2] / c[-4] - 1 = 200 / 100 - 1; the last close (120) is skipped.
    assert return_window(rows([100, 50, 200, 120]), 3, skip=1).tolist() == [1.0]
    assert return_window(rows([100, 50, 200, 120]), 3, 2).tolist() == [50.0 / 100.0 - 1.0]


def test_return_window_warm_up_boundary():
    assert math.isnan(return_window(rows([1, 2]), 2)[0])  # W = n
    assert return_window(rows([4, 1, 6]), 2).tolist() == [0.5]  # W = n + 1


def test_return_window_zero_base_is_not_finite_and_silent():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = return_window(rows([0, 1, 2], [0, 1, 0]), 2)
    assert math.isinf(out[0]) and math.isnan(out[1])


def test_return_window_rejects_bad_input():
    with pytest.raises(ValueError, match="2-D"):
        return_window(np.array([1.0, 2.0, 3.0]), 2)
    with pytest.raises(ValueError, match="n must be"):
        return_window(rows([1, 2, 3]), 0)
    for skip in (2, 3, -1, True, 1.0):
        with pytest.raises(ValueError, match="skip"):
            return_window(rows([1, 2, 3]), 2, skip)


@pytest.mark.parametrize(("n", "skip"), [(1, 0), (20, 0), (126, 21), (199, 21)])
def test_return_window_rolling_is_bit_identical_to_one_window(n, skip):
    rng = np.random.default_rng(7)
    close = np.round(100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.02, 600))), 4)
    out = rolling(return_window, close, window=200, n=n, skip=skip)
    assert np.isnan(out[:199]).all()
    for i in range(199, 600):
        assert return_window(close[None, i - 199 : i + 1].copy(), n, skip)[0] == out[i], i


# ---- the protocol -------------------------------------------------------------------------


def test_the_adapters_are_allocators_and_not_strategies():
    for a in (PICKS, BLEND, VOLTARGET, FIXED, MOMENTUM):
        assert isinstance(a, Allocator)
        assert not isinstance(a, Strategy)
    assert not isinstance(STRATEGY_A, Allocator)
    assert (PICKS.id, BLEND.id, VOLTARGET.id) == ("PICKS", "BLEND", "VOLTARGET")
    assert isinstance(PICKS, PicksAllocator)
    assert isinstance(BLEND, BlendAllocator)
    assert isinstance(VOLTARGET, VolTargetAllocator)


# ---- target_from_close --------------------------------------------------------------------


def test_target_from_close_rounds_through_to_decimal():
    got = target_from_close("AAA", 101.23456, D("0.5"))
    assert got == Target(symbol="AAA", weight=D("0.5"), last=D("101.2346"))
    assert target_from_close("AAA", 0.1, D("1")).last == D("0.1000")  # shortest repr, not binary
    assert target_from_close("AAA", D("7.12345"), D("1")).last == D("7.1235")  # half-up


def test_target_from_close_bracket():
    got = target_from_close("AAA", 50.0, D("0.25"), limit=49.5, stop=47.0, take=51.25)
    assert got == Target(symbol="AAA", weight=D("0.25"), last=D("50.0000"), limit=D("49.5000"), stop=D("47.0000"), take=D("51.2500"))
    # Without a limit, stop and take are ordered around the close.
    assert target_from_close("AAA", 50.0, D("1"), stop=45.0, take=60.0).stop == D("45.0000")
    # A limit above the close is allowed (an open_limit-style entry).
    assert target_from_close("AAA", 50.0, D("1"), limit=51.0).limit == D("51.0000")


@pytest.mark.parametrize(
    "kw",
    [
        {"close": 0.0},
        {"close": -1.0},
        {"close": 0.00004},  # rounds to 0
        {"close": math.nan},
        {"close": math.inf},
        {"close": 50.0, "limit": 0.0},
        {"close": 50.0, "limit": math.nan},
        {"close": 50.0, "stop": 50.0},  # stop must be < the close (no limit)
        {"close": 50.0, "take": 50.0},  # take must be > the close
        {"close": 50.0, "limit": 49.0, "stop": 49.0},
        {"close": 50.0, "limit": 49.0, "take": 49.00004},  # rounds to the limit
        {"close": 50.0, "stop": -1.0},
    ],
)
def test_target_from_close_drops_unusable_prices(kw):
    close = kw.pop("close")
    assert target_from_close("AAA", close, D("0.5"), **kw) is None


def test_target_from_close_rejects_bad_types_and_weights():
    with pytest.raises(TypeError):
        target_from_close("AAA", True, D("0.5"))
    with pytest.raises(TypeError):
        target_from_close("AAA", "50", D("0.5"))
    with pytest.raises(TypeError):
        target_from_close("AAA", 50.0, 0.5)  # a float weight never reaches a Target
    with pytest.raises(ValueError):
        target_from_close("AAA", 50.0, D("0"))


# ---- month_end_closes ---------------------------------------------------------------------


def _jan_to_apr_2019():
    days = sessions(date(2019, 1, 2), date(2019, 4, 30))
    h = hist("AAA", [float(i + 1) for i in range(len(days))], days=days)
    return days, h


def _close_on(days, h, d) -> float:
    return float(h.close[days.index(d)])


def test_month_end_closes_completed_months_only():
    days, h = _jan_to_apr_2019()
    jan, feb, mar = (_close_on(days, h, x) for x in (date(2019, 1, 31), date(2019, 2, 28), date(2019, 3, 29)))
    assert month_end_closes(h, date(2019, 3, 15)).tolist() == [jan, feb]
    assert month_end_closes(h, date(2019, 3, 28)).tolist() == [jan, feb]
    assert month_end_closes(h, date(2019, 3, 29)).tolist() == [jan, feb, mar]  # its last session
    assert month_end_closes(h, date(2019, 3, 30)).tolist() == [jan, feb, mar]  # a Saturday after it
    assert month_end_closes(h, date(2019, 4, 1)).tolist() == [jan, feb, mar]
    assert month_end_closes(h, date(2019, 1, 30)).tolist() == []
    assert month_end_closes(h, date(2018, 12, 31)).tolist() == []
    out = month_end_closes(h, date(2019, 4, 30))
    assert out.dtype == np.float64 and out.tolist() == [jan, feb, mar, _close_on(days, h, date(2019, 4, 30))]


def test_month_end_closes_uses_the_symbols_own_last_bar_of_a_month():
    days, h = _jan_to_apr_2019()
    gappy = drop_days(h, [date(2019, 2, 28)])  # no bar on February's last session
    feb27 = _close_on(days, h, date(2019, 2, 27))
    assert month_end_closes(gappy, date(2019, 3, 15)).tolist()[-1] == feb27
    # A symbol whose bars stop in February: February is complete by mid-March.
    stopped = h.upto(date(2019, 2, 20))
    assert month_end_closes(stopped, date(2019, 3, 15)).tolist() == [
        _close_on(days, h, date(2019, 1, 31)),
        _close_on(days, h, date(2019, 2, 20)),
    ]


def test_month_end_closes_reads_no_later_bar():
    days, h = _jan_to_apr_2019()
    for d in days:
        assert month_end_closes(h, d).tolist() == month_end_closes(h.upto(d), d).tolist(), d
    with pytest.raises(TypeError):
        month_end_closes(h, np.datetime64("2019-03-01"))
    with pytest.raises(TypeError):
        month_end_closes("AAA", date(2019, 3, 1))


# ---- helpers ------------------------------------------------------------------------------


def test_last_close_and_scale_weight():
    days, h = _jan_to_apr_2019()
    assert last_close(h, date(2019, 1, 5)) == _close_on(days, h, date(2019, 1, 4))  # a Saturday
    assert last_close(h, date(2018, 12, 31)) is None
    assert last_close(None, date(2019, 1, 5)) is None
    assert scale_weight(D("0.5"), D("0.333333")) == D("0.166666")  # floored, not rounded
    assert scale_weight(D("0.000001"), D("0.5")) is None  # floors to zero: dropped
    assert scale_weight(D("0.25"), D("1")) == D("0.25")


def test_lazy_prepared_prepares_each_inner_object_once():
    inner, other = ConstAllocator(), ConstAllocator()
    lazy = LazyPrepared({})
    assert lazy.of(inner) == "prepared" and lazy.of(inner) == "prepared" and lazy.of(other) == "prepared"
    assert (inner.prepare_calls, other.prepare_calls) == (1, 1)


# ---- PICKS --------------------------------------------------------------------------------


def picks_set() -> tuple[list[date], dict]:
    days = session_days(260)
    return days, {
        "SAW": hist("SAW", sawtooth(260), days=days),
        "DIP": hist("DIP", dip(dip(uptrend(260), 229), 245, drop=2.0), days=days),
        "GAPPY": drop_days(hist("GAPPY", sawtooth(260, first=70.0), days=days), days[230:233]),
        "LATE": hist("LATE", sawtooth(240, first=40.0, up=0.9, down=0.5), days=days[20:]),
    }


def test_picks_targets_hold_first_then_the_strategys_picks():
    days, history = picks_set()
    d = days[240]
    params = PicksParams(STRATEGY_A, PERMISSIVE)
    members = frozenset(history)
    picks = STRATEGY_A.picks(history, members, d, PERMISSIVE)
    assert len(picks) >= 3
    held = frozenset({picks[1].symbol})
    got = PICKS.targets(history, members, d, held, params)
    w = D("0.25")
    expected = [Target(symbol=picks[1].symbol, weight=w, last=picks[1].last_price)]
    expected += [
        Target(symbol=p.symbol, weight=w, last=p.last_price, limit=p.limit_price, stop=p.sl_price, take=p.tp_price)
        for p in picks
        if p.symbol not in held
    ]
    assert got == tuple(expected)
    assert PICKS.targets(history, members, d, frozenset(), PicksParams(STRATEGY_A, PERMISSIVE, slots=3))[0].weight == D("0.333333")


def test_picks_keeps_a_held_symbol_without_a_bar_at_its_last_close():
    days, history = picks_set()
    d = days[231]  # GAPPY has no bar on days[230..232]
    got = PICKS.targets(history, frozenset(history), d, frozenset({"GAPPY"}), PicksParams(STRATEGY_A, PERMISSIVE))
    assert got[0] == Target(symbol="GAPPY", weight=D("0.25"), last=D(repr(float(history["GAPPY"].upto(d).close[-1]))).quantize(D("0.0001")))
    assert "GAPPY" not in [x.symbol for x in got[1:]]
    with pytest.raises(ValueError, match="held symbol NOPE"):
        PICKS.targets(history, frozenset(history), d, frozenset({"NOPE"}), PicksParams(STRATEGY_A, PERMISSIVE))


def test_picks_skips_held_and_repeated_picks():
    days = session_days(5)
    history = {s: hist(s, [10.0, 11.0, 12.0, 13.0, 14.0], days=days) for s in ("AAA", "BBB", "CCC")}
    pick = lambda s: Pick(s, D("14"), D("13.5"), D("15"), D("12"))  # noqa: E731
    strategy = ListStrategy([pick("BBB"), pick("AAA"), pick("BBB"), pick("CCC")])
    params = PicksParams(strategy, None, slots=2)
    got = PICKS.targets(history, frozenset(), days[-1], frozenset({"AAA"}), params)
    assert [x.symbol for x in got] == ["AAA", "BBB", "CCC"]
    assert got[0].limit is None and got[1].limit == D("13.5") and got[1].stop == D("12") and got[1].take == D("15")
    assert sum(x.weight for x in got) == D("1.5")  # PICKS may exceed 1: the engine's slot cap decides


def test_picks_prepares_the_strategy_once():
    days = session_days(5)
    history = {"AAA": hist("AAA", [10.0, 11.0, 12.0, 13.0, 14.0], days=days)}
    strategy = ListStrategy([])
    params = PicksParams(strategy, None)
    prepared = PICKS.prepare(history)
    for d in days:
        assert PICKS.targets_prepared(prepared, frozenset(), d, frozenset(), params) == ()
    assert strategy.prepare_calls == 1


def test_picks_metadata_and_validation():
    params = PicksParams(STRATEGY_A, PERMISSIVE)
    assert PICKS.lookback(params) == STRATEGY_A.lookback
    assert PICKS.symbols(params) == () and PICKS.holds(params) == ()
    assert PICKS.uses_members(params) is True
    assert params.as_dict() == {"strategy": "A", "slots": "4", **{f"params.{k}": v for k, v in PERMISSIVE.as_dict().items()}}
    with pytest.raises(TypeError):
        PicksParams(PICKS, None)
    with pytest.raises(TypeError):
        PicksParams(STRATEGY_A, PERMISSIVE, slots=True)
    with pytest.raises(ValueError):
        PicksParams(STRATEGY_A, PERMISSIVE, slots=0)
    with pytest.raises(TypeError, match="PicksParams"):
        PICKS.targets({}, frozenset(), date(2019, 1, 2), frozenset(), PERMISSIVE)
    with pytest.raises(TypeError, match="held"):
        PICKS.targets({}, frozenset(), date(2019, 1, 2), {"AAA"}, params)
    with pytest.raises(TypeError, match="LazyPrepared"):
        PICKS.targets_prepared({}, frozenset(), date(2019, 1, 2), frozenset(), params)


def test_picks_p4_identity():
    days, history = picks_set()
    held_sets = [frozenset(), frozenset({"SAW"}), frozenset({"GAPPY", "DIP"})]
    params = [PicksParams(STRATEGY_A, PERMISSIVE), PicksParams(STRATEGY_A, AParams(), slots=2)]
    n = assert_p4_identity(PICKS, history, everyone(history), days[200:], held_sets, params, max_weight_sum=None)
    assert n >= 60


def test_picks_no_lookahead():
    days, history = picks_set()
    held_sets = [frozenset(), frozenset({"GAPPY"})]
    params = [PicksParams(STRATEGY_A, PERMISSIVE)]
    assert assert_no_lookahead(PICKS, history, everyone(history), days[201:260:6], held_sets, params) >= 5


# ---- BLEND --------------------------------------------------------------------------------


def test_blend_scales_sums_and_ranks_by_first_appearance():
    core, sat = ConstAllocator(), ConstAllocator()
    params = BlendParams(
        (
            BlendPart(core, ConstParams((t("SPY", "1", stop="9"),)), D("0.7")),
            BlendPart(sat, ConstParams((t("QQQ", "0.5"), t("SPY", "0.5", limit="9.5"))), D("0.3")),
        )
    )
    got = BLEND.targets({}, frozenset(), date(2019, 1, 2), frozenset(), params)
    # SPY: 0.7 + 0.15 at rank 1 with the core's prices; QQQ: 0.15.
    assert got == (t("SPY", "0.85", stop="9"), t("QQQ", "0.15"))


def test_blend_floors_each_scaled_weight_and_drops_zeros():
    a, b = ConstAllocator(), ConstAllocator()
    params = BlendParams(
        (
            BlendPart(a, ConstParams((t("AAA", "0.5"), t("TINY", "0.000001"))), D("0.333333")),
            BlendPart(b, ConstParams((t("BBB", "1"),)), D("0.5")),
        )
    )
    got = BLEND.targets({}, frozenset(), date(2019, 1, 2), frozenset(), params)
    assert got == (t("AAA", "0.166666"), t("BBB", "0.5"))


def test_blend_parts_do_not_see_each_others_fixed_holdings():
    a, b = ConstAllocator(), ConstAllocator()
    params = BlendParams(
        (
            BlendPart(a, ConstParams((), holds=("SPY",)), D("0.5")),
            BlendPart(b, ConstParams((), holds=("QQQ", "TLT")), D("0.5")),
        )
    )
    held = frozenset({"SPY", "QQQ", "XYZ"})
    BLEND.targets({}, frozenset(), date(2019, 1, 2), held, params)
    BLEND.targets_prepared(BLEND.prepare({}), frozenset(), date(2019, 1, 2), held, params)
    assert a.seen_held == [frozenset({"SPY", "XYZ"})] * 2
    assert b.seen_held == [frozenset({"QQQ", "XYZ"})] * 2


def test_blend_metadata_validation_and_as_dict():
    a, m = ConstAllocator(), MembersFake()
    params = BlendParams(
        (
            BlendPart(a, ConstParams((t("SPY", "1"),), holds=("SPY",), lookback=200), D("0.6")),
            BlendPart(m, ConstParams((t("AAA", "1"), t("BBB", "1")), holds=("BBB",), lookback=60), D("0.4")),
        )
    )
    assert BLEND.lookback(params) == 200
    assert BLEND.symbols(params) == ("AAA", "BBB", "SPY")
    assert BLEND.holds(params) == ("BBB", "SPY")
    assert BLEND.uses_members(params) is True
    assert params.as_dict() == {
        "part1.allocator": "FAKE_CONST",
        "part1.share": "0.6",
        "part1.targets": "SPY",
        "part2.allocator": "FAKE_MEMBERS",
        "part2.share": "0.4",
        "part2.targets": "AAA,BBB",
    }
    part = BlendPart(a, ConstParams(()), D("0.5"))
    with pytest.raises(ValueError, match=">= 2 parts"):
        BlendParams((part,))
    with pytest.raises(ValueError, match="sum"):
        BlendParams((part, BlendPart(a, ConstParams(()), D("0.500001"))))
    with pytest.raises(TypeError):
        BlendParams([part, part])
    with pytest.raises(TypeError):
        BlendPart(STRATEGY_A, None, D("0.5"))
    with pytest.raises(TypeError):
        BlendPart(a, None, 0.5)
    for bad in ("0", "1.000001", "0.0000005", "NaN"):
        with pytest.raises(ValueError):
            BlendPart(a, None, D(bad))


def blend_set() -> tuple[list[date], dict]:
    days = session_days(80)
    return days, {
        "SPY": drop_days(hist("SPY", sawtooth(80, first=250.0), days=days), days[40:42]),
        "AAA": hist("AAA", uptrend(80, first=20.0, step=0.3), days=days),
        "BBB": hist("BBB", sawtooth(80, first=30.0, up=1.0, down=0.9), days=days),
        "CCC": hist("CCC", [50.0 - 0.2 * i for i in range(70)], days=days[10:]),
    }


def _stocks(d: date) -> frozenset[str]:
    return frozenset({"AAA", "BBB", "CCC"})


def test_blend_p4_identity_and_no_lookahead():
    days, history = blend_set()
    params = [
        BlendParams((BlendPart(FIXED, FixedParams((("SPY", D("1")),)), D("0.7")), BlendPart(MOMENTUM, MomentumParams(2), D("0.3")))),
        BlendParams((BlendPart(MOMENTUM, MomentumParams(1), D("0.5")), BlendPart(FIXED, FixedParams((("AAA", D("0.5")), ("SPY", D("0.5")))), D("0.5")))),
    ]
    held_sets = [frozenset(), frozenset({"SPY"}), frozenset({"SPY", "AAA"})]
    assert assert_p4_identity(BLEND, history, _stocks, days[5:], held_sets, params) >= 100
    assert assert_no_lookahead(BLEND, history, _stocks, days[10:80:7], held_sets, params) >= 20


def test_blend_prepares_each_part_once():
    a, b = ConstAllocator(), ConstAllocator()
    params = BlendParams((BlendPart(a, ConstParams(()), D("0.5")), BlendPart(b, ConstParams(()), D("0.5"))))
    prepared = BLEND.prepare({})
    for d in session_days(5):
        BLEND.targets_prepared(prepared, frozenset(), d, frozenset(), params)
    assert (a.prepare_calls, b.prepare_calls) == (1, 1)


# ---- VOLTARGET ----------------------------------------------------------------------------


def _signal(closes: list[float]) -> tuple[list[date], dict]:
    days = session_days(len(closes))
    return days, {"SPY": hist("SPY", closes, days=days)}


def test_voltarget_hand_computed_scale():
    # Returns +0.1 and -0.1: population stdev 0.1; scale = 0.12 / (0.1 × sqrt(252)) = 0.07559289...
    days, history = _signal([100.0, 110.0, 99.0])
    inner = ConstAllocator()
    params = VolTargetParams(inner, ConstParams((t("SPY", "1"), t("TLT", "0.000010"))), n=2)
    got = VOLTARGET.targets(history, frozenset(), days[2], frozenset(), params)
    assert got == (t("SPY", "0.075592"),)  # TLT: 0.00001 × 0.0756 floors to zero and is dropped
    assert vol_scale(history["SPY"], days[2], 2, D("0.12")) == D(repr(0.12 / (0.10000000000000003 * math.sqrt(252))))


def test_voltarget_passes_inner_targets_unchanged_when_it_cannot_or_need_not_scale():
    inner = ConstAllocator()
    targets = (t("SPY", "0.6"), t("TLT", "0.4"))
    params = VolTargetParams(inner, ConstParams(targets), n=2)
    calm_days, calm = _signal([100.0, 100.5, 100.0])  # ~11% annualized < 12%: scale >= 1
    assert VOLTARGET.targets(calm, frozenset(), calm_days[2], frozenset(), params) == targets
    flat_days, flat = _signal([100.0, 100.0, 100.0])  # zero stdev
    assert VOLTARGET.targets(flat, frozenset(), flat_days[2], frozenset(), params) == targets
    short_days, short = _signal([100.0, 110.0, 99.0])
    assert VOLTARGET.targets(short, frozenset(), short_days[1], frozenset(), params) == targets  # 2 bars < n + 1
    assert VOLTARGET.targets({}, frozenset(), short_days[2], frozenset(), params) == targets  # no signal history


def test_voltarget_metadata_validation_and_as_dict():
    inner = MembersFake()
    params = VolTargetParams(inner, ConstParams((t("AAA", "1"),), holds=("AAA",), lookback=10), signal="QQQ", target_vol=D("0.150"), n=20)
    assert VOLTARGET.lookback(params) == 21
    assert VOLTARGET.lookback(VolTargetParams(inner, ConstParams((), lookback=200))) == 200
    assert VOLTARGET.symbols(params) == ("AAA", "QQQ")
    assert VOLTARGET.holds(params) == ("AAA",)
    assert VOLTARGET.uses_members(params) is True
    assert params.as_dict() == {"inner": "FAKE_MEMBERS", "signal": "QQQ", "target_vol": "0.15", "n": "20", "inner.targets": "AAA"}
    with pytest.raises(TypeError):
        VolTargetParams(STRATEGY_A, None)
    with pytest.raises(TypeError):
        VolTargetParams(inner, None, target_vol=0.12)
    with pytest.raises(ValueError):
        VolTargetParams(inner, None, target_vol=D("0"))
    with pytest.raises(ValueError):
        VolTargetParams(inner, None, signal="")
    with pytest.raises(ValueError):
        VolTargetParams(inner, None, n=1)
    with pytest.raises(TypeError):
        VolTargetParams(inner, None, n=True)
    with pytest.raises(TypeError, match="VolTargetParams"):
        VOLTARGET.targets({}, frozenset(), date(2019, 1, 2), frozenset(), None)


def test_voltarget_p4_identity_and_no_lookahead():
    days, history = blend_set()
    params = [
        VolTargetParams(MOMENTUM, MomentumParams(2), n=5),
        VolTargetParams(FIXED, FixedParams((("SPY", D("1")),)), target_vol=D("0.05"), n=10),
    ]
    held_sets = [frozenset(), frozenset({"SPY"})]
    assert assert_p4_identity(VOLTARGET, history, _stocks, days[5:], held_sets, params) >= 100
    assert assert_no_lookahead(VOLTARGET, history, _stocks, days[12:80:7], held_sets, params) >= 15
    # Not vacuous: on most days the overlay really scales the inner weights down.
    d = days[60]
    inner = FIXED.targets(upto(history, d), _stocks(d), d, frozenset(), params[1].inner_params)
    outer = VOLTARGET.targets(upto(history, d), _stocks(d), d, frozenset(), params[1])
    assert outer[0].weight < inner[0].weight


def test_voltarget_prepares_the_inner_allocator_once():
    inner = ConstAllocator()
    days, history = _signal([100.0, 110.0, 99.0, 104.0])
    params = VolTargetParams(inner, ConstParams((t("SPY", "1"),)), n=2)
    prepared = VOLTARGET.prepare(history)
    for d in days:
        VOLTARGET.targets_prepared(prepared, frozenset(), d, frozenset(), params)
    assert inner.prepare_calls == 1


# ---- the kit catches broken allocators ----------------------------------------------------


def _kit_set() -> tuple[list[date], dict]:
    days = session_days(40)
    return days, {
        "UP": hist("UP", uptrend(40), days=days),
        "SAW": hist("SAW", sawtooth(40), days=days),
    }


def test_kit_catches_look_ahead():
    days, history = _kit_set()
    with pytest.raises(AssertionError, match="look-ahead|reads bars after"):
        assert_no_lookahead(PeekAllocator(), history, everyone(history), days[10:12], [frozenset()], [None])
    with pytest.raises(AssertionError, match="reads bars after"):
        assert_p4_identity(PeekAllocator(), history, everyone(history), days[10:12], [frozenset()], [None])


def test_kit_catches_a_broken_prepared_path():
    days, history = _kit_set()
    with pytest.raises(AssertionError, match="P4 identity"):
        assert_p4_identity(ForgetfulAllocator(), history, everyone(history), days[10:12], [frozenset()], [None])
    with pytest.raises(AssertionError, match="P4 identity"):
        assert_no_lookahead(ForgetfulAllocator(), history, everyone(history), days[10:12], [frozenset()], [None])


def test_kit_catches_a_lookback_that_is_too_short():
    days, history = blend_set()

    class Short(type(MOMENTUM)):
        def lookback(self, params):
            return 3  # needs n + 1 = 6

    with pytest.raises(AssertionError, match="lookback too short"):
        assert_p4_identity(Short(), history, _stocks, days[20:25], [frozenset()], [MomentumParams(2)])
    assert assert_p4_identity(MOMENTUM, history, _stocks, days[20:25], [frozenset()], [MomentumParams(2)]) == 5


def test_kit_target_shape_checks():
    days, history = _kit_set()
    d = days[10]
    up = target_from_close("UP", float(history["UP"].close[10]), D("0.6"))
    saw = target_from_close("SAW", float(history["SAW"].close[10]), D("0.6"))
    assert_valid_targets((up,), history, d, frozenset())
    with pytest.raises(AssertionError, match="tuple"):
        assert_valid_targets([up], history, d, frozenset())
    with pytest.raises(AssertionError, match="duplicate"):
        assert_valid_targets((up, up), history, d, frozenset(), max_weight_sum=None)
    with pytest.raises(AssertionError, match="Σ weight"):
        assert_valid_targets((up, saw), history, d, frozenset())
    assert_valid_targets((up, saw), history, d, frozenset(), max_weight_sum=None)
    with pytest.raises(AssertionError, match="last"):
        assert_valid_targets((t("UP", "0.5", last="1"),), history, d, frozenset())
    with pytest.raises(AssertionError, match="no history"):
        assert_valid_targets((t("NOPE", "0.5"),), history, d, frozenset())
    gappy = {"UP": drop_days(history["UP"], [d])}
    kept = target_from_close("UP", float(history["UP"].close[9]), D("0.5"))
    with pytest.raises(AssertionError, match="without a bar"):
        assert_valid_targets((kept,), gappy, d, frozenset())
    assert_valid_targets((kept,), gappy, d, frozenset({"UP"}))


def test_kit_rejects_a_bare_params_value():
    days, history = _kit_set()
    with pytest.raises(TypeError, match="params"):
        assert_p4_identity(FIXED, history, everyone(history), days[:2], [frozenset()], FixedParams((("UP", D("1")),)))
    with pytest.raises(TypeError, match="held_sets"):
        assert_p4_identity(FIXED, history, everyone(history), days[:2], frozenset(), [FixedParams((("UP", D("1")),))])


def test_kit_no_lookahead_uses_prev_session():
    # The data date of session S is prev_session(S): bars dated S itself are already "future".
    days, history = _kit_set()
    s = days[20]
    assert prev_session(s) == days[19]
    assert assert_no_lookahead(FIXED, history, everyone(history), [s], [frozenset()], [FixedParams((("UP", D("1")),))]) == 1
