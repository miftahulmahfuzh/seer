"""Family F7: longer-horizon mean reversion (P7a phase 8; handover §4.B F7, D12; plan R3)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest
from allocatorkit import assert_no_lookahead, assert_p4_identity
from simkit import P
from stratkit import dip, drop_days, hist, mutate_from, sawtooth, session_days, truncate_before, uptrend

from seer_engine.dates import prev_session
from seer_engine.sim import Target, equal_weight
from seer_engine.strategies.allocator import Allocator
from seer_engine.strategies.base import History
from seer_engine.strategies.f_swing import (
    ATR_N,
    DV_N,
    SWING,
    WINDOW,
    SwingFeatures,
    SwingParams,
    SwingPrepared,
    entry_target,
    features_at,
    has_exit_signal,
    has_setup,
    member_window,
    rank_entries,
    swing_lookback,
    trend_on,
)

DEFAULT = SwingParams()
QUARTER = Decimal("0.25")


def upto_all(history: dict[str, History], d: date) -> dict[str, History]:
    return {s: h.upto(d) for s, h in history.items()}


def sf(
    symbol: str = "AAA",
    *,
    close: float = 50.0,
    sma: float = 40.0,
    exit_sma: float | None = 55.0,
    rsi: float = 5.0,
    atr: float = 1.0,
    dollar_volume: float = 100_000_000.0,
) -> SwingFeatures:
    """A SwingFeatures row that passes the default setup and has no exit signal, unless overridden."""
    return SwingFeatures(symbol, date(2019, 1, 2), close, sma, exit_sma, rsi, atr, dollar_volume)


def dip_set() -> tuple[list[date], dict[str, History]]:
    """Day 229 is a dip in every DIP* series (RSI(2) well below 10, close above SMA200)."""
    days = session_days(230)
    return days, {
        "DIP": hist("DIP", dip(uptrend(230), 229), days=days),
        "DIPB": hist("DIPB", dip(uptrend(230), 229, drop=2.0), days=days),
        "DIPC": hist("DIPC", dip(uptrend(230, first=90.0), 229, drop=1.5), days=days),
        "UP": hist("UP", uptrend(230, first=60.0), days=days),
    }


# ---- params ---------------------------------------------------------------------------------


def test_defaults_and_as_dict():
    assert (WINDOW, ATR_N, DV_N) == (200, 14, 20)
    assert DEFAULT == SwingParams(
        4, 2, 10.0, 200, "dip", Decimal("0.5"), Decimal("2.5"), None, 5, None, 20_000_000.0, None
    )
    assert list(DEFAULT.as_dict().items()) == [
        ("slots", "4"),
        ("rsi_n", "2"),
        ("rsi_max", "10"),
        ("sma_n", "200"),
        ("entry", "dip"),
        ("limit_atr", "0.5"),
        ("stop_atr", "2.5"),
        ("take_atr", "none"),
        ("exit_sma", "5"),
        ("exit_rsi", "none"),
        ("min_dollar_volume", "20000000"),
        ("market_trend", "none"),
    ]
    p = SwingParams(
        slots=8, rsi_max=5, entry="close", stop_atr=None, take_atr=Decimal("1.50"), exit_sma=None,
        exit_rsi=70, market_trend=("SPY", 200),
    )
    assert isinstance(p.rsi_max, float) and isinstance(p.exit_rsi, float)
    assert p.as_dict() == {
        "slots": "8", "rsi_n": "2", "rsi_max": "5", "sma_n": "200", "entry": "close", "limit_atr": "0.5",
        "stop_atr": "none", "take_atr": "1.5", "exit_sma": "none", "exit_rsi": "70",
        "min_dollar_volume": "20000000", "market_trend": "SPY:200",
    }


@pytest.mark.parametrize(
    ("kw", "exc"),
    [
        ({"slots": 0}, ValueError),
        ({"slots": 101}, ValueError),
        ({"slots": True}, TypeError),
        ({"slots": 4.0}, TypeError),
        ({"rsi_n": 0}, ValueError),
        ({"sma_n": 0}, ValueError),
        ({"rsi_max": 0.0}, ValueError),
        ({"rsi_max": 100.5}, ValueError),
        ({"rsi_max": "10"}, TypeError),
        ({"rsi_max": float("nan")}, ValueError),
        ({"entry": "open"}, ValueError),
        ({"entry": 1}, TypeError),
        ({"limit_atr": 0.5}, TypeError),
        ({"limit_atr": Decimal("-0.1")}, ValueError),
        ({"stop_atr": Decimal("0")}, ValueError),
        ({"stop_atr": 2.5}, TypeError),
        ({"take_atr": Decimal("-1")}, ValueError),
        ({"take_atr": Decimal("NaN")}, ValueError),
        ({"exit_sma": 0}, ValueError),
        ({"exit_rsi": 100.0}, ValueError),
        ({"exit_rsi": -1.0}, ValueError),
        ({"min_dollar_volume": -1.0}, ValueError),
        ({"market_trend": ["SPY", 200]}, TypeError),
        ({"market_trend": ("SPY",)}, TypeError),
        ({"market_trend": ("", 200)}, TypeError),
        ({"market_trend": ("SPY", 0)}, ValueError),
    ],
)
def test_params_reject_bad_values(kw, exc):
    with pytest.raises(exc):
        SwingParams(**kw)


def test_windows_and_lookback():
    assert member_window(DEFAULT) == swing_lookback(DEFAULT) == 200
    assert member_window(SwingParams(sma_n=250)) == 250
    assert member_window(SwingParams(exit_sma=300)) == 300
    p = SwingParams(market_trend=("SPY", 260))
    assert (member_window(p), swing_lookback(p)) == (200, 260)  # the trend never widens member windows


def test_swing_implements_the_allocator_protocol():
    assert isinstance(SWING, Allocator)
    assert SWING.id == "F7"
    assert SWING.lookback(DEFAULT) == 200
    assert SWING.symbols(DEFAULT) == ()
    assert SWING.symbols(SwingParams(market_trend=("SPY", 200))) == ("SPY",)
    assert SWING.holds(DEFAULT) == ()
    assert SWING.uses_members(DEFAULT) is True


def test_wrong_types_raise():
    days, history = dip_set()
    d = days[-1]
    with pytest.raises(TypeError, match="SwingParams"):
        SWING.targets(history, {"DIP"}, d, frozenset(), object())
    with pytest.raises(TypeError, match="SwingParams"):
        SWING.lookback({"slots": 4})
    with pytest.raises(TypeError, match="held"):
        SWING.targets(history, {"DIP"}, d, ["DIP"], DEFAULT)
    with pytest.raises(TypeError, match="SwingPrepared"):
        SWING.targets_prepared(object(), {"DIP"}, d, frozenset(), DEFAULT)


# ---- features -------------------------------------------------------------------------------


def test_features_hand_computed_on_the_dip():
    # The Strategy A dip (tests/test_strategy_a.py): close 120.9, SMA200 112.935, RSI(2) 100/28,
    # ATR(14) 206.8/196, DV 121.8e6. SMA(5) = (122.5 + 122.6 + 122.7 + 121.8 + 120.9) / 5 = 122.1.
    days, history = dip_set()
    [f] = features_at(history, ["DIP"], days[229], DEFAULT)
    assert (f.symbol, f.data_date) == ("DIP", days[229])
    assert f.close == pytest.approx(120.9, rel=1e-12)
    assert f.sma == pytest.approx(112.935, rel=1e-12)
    assert f.exit_sma == pytest.approx(122.1, rel=1e-12)
    assert f.rsi == pytest.approx(100 / 28, rel=1e-9)
    assert f.atr == pytest.approx(206.8 / 196, rel=1e-12)
    assert f.dollar_volume == pytest.approx(121.8e6, rel=1e-12)
    [g] = features_at(history, ["DIP"], days[229], SwingParams(exit_sma=None))
    assert g.exit_sma is None and g.rsi == f.rsi


def test_features_eligibility_and_order():
    days = session_days(201)
    closes = sawtooth(201)
    h199 = {"X": hist("X", closes[:199], days=days[:199])}
    h200 = {"X": hist("X", closes[:200], days=days[:200])}
    assert features_at(h199, ["X"], days[198], DEFAULT) == ()
    assert [f.symbol for f in features_at(h200, ["X", "X", "NOPE"], days[199], DEFAULT)] == ["X"]
    gappy = {"X": drop_days(hist("X", closes, days=days), [days[200]])}
    assert features_at(gappy, ["X"], days[200], DEFAULT) == ()
    many = {s: hist(s, sawtooth(200)) for s in ("MMM", "AAA", "ZZZ")}
    assert [f.symbol for f in features_at(many, ["ZZZ", "AAA", "MMM"], many["AAA"].last_date(), DEFAULT)] == [
        "AAA", "MMM", "ZZZ",
    ]
    assert features_at(h200, ["X"], days[199], SwingParams(sma_n=201)) == ()  # window 201 > 200 bars


def test_features_read_only_the_member_window():
    days = session_days(300)
    tail = sawtooth(200, first=150.0)
    a = {"X": hist("X", [50.0 + t for t in range(100)] + tail, days=days)}
    b = {"X": hist("X", [999.0 - t for t in range(100)] + tail, days=days)}
    c = {"X": hist("X", tail, days=days[100:])}
    assert features_at(a, ["X"], days[-1], DEFAULT) == features_at(b, ["X"], days[-1], DEFAULT)
    assert features_at(b, ["X"], days[-1], DEFAULT) == features_at(c, ["X"], days[-1], DEFAULT)


# ---- setup and exit signal, each condition alone --------------------------------------------


@pytest.mark.parametrize(
    ("kw", "passes"),
    [
        ({}, True),
        ({"rsi": 10.0}, False),  # RSI exactly rsi_max: strict
        ({"rsi": 9.999999}, True),
        ({"close": 40.0, "sma": 40.0}, False),  # close == SMA: strict
        ({"close": 39.0, "sma": 40.0}, False),
        ({"dollar_volume": 20_000_000.0}, False),  # exactly the floor: strict
        ({"dollar_volume": 20_000_000.5}, True),
        ({"sma": float("nan")}, False),
        ({"atr": float("nan")}, False),
        ({"exit_sma": 10.0}, True),  # an exit signal does not block the setup
    ],
)
def test_setup_each_condition_alone(kw, passes):
    assert has_setup(sf(**kw), DEFAULT) is passes


@pytest.mark.parametrize(
    ("kw", "params", "exits"),
    [
        ({}, DEFAULT, False),  # close 50 < SMA5 55
        ({"exit_sma": 50.0}, DEFAULT, False),  # close == SMA5: strict
        ({"exit_sma": 49.99}, DEFAULT, True),
        ({"exit_sma": 10.0}, SwingParams(exit_sma=None), False),  # SMA exit off
        ({"rsi": 70.0}, SwingParams(exit_rsi=70.0), False),  # RSI == exit_rsi: strict
        ({"rsi": 70.01}, SwingParams(exit_rsi=70.0), True),
        ({"rsi": 99.0}, DEFAULT, False),  # RSI exit off by default
        ({"exit_sma": 10.0, "rsi": 99.0}, SwingParams(exit_sma=None, exit_rsi=None), False),  # never by signal
        ({"exit_sma": None}, DEFAULT, False),  # no SMA value: nothing to decide
    ],
)
def test_exit_signal_each_condition_alone(kw, params, exits):
    assert has_exit_signal(sf(**kw), params) is exits


# ---- entry targets --------------------------------------------------------------------------


def test_dip_target_hand_computed():
    # last = 120.9000, ATR -> 1.0551; limit = q(120.9 - 0.52755) = 120.3725 (half-up);
    # stop = q(120.3725 - 2.5 × 1.0551) = q(117.73475) = 117.7348; no take
    days, history = dip_set()
    assert SWING.targets(history, {"DIP"}, days[229], frozenset(), DEFAULT) == (
        Target("DIP", QUARTER, P("120.9"), P("120.3725"), P("117.7348"), None),
    )


def test_close_entry_and_take_hand_computed():
    days, history = dip_set()
    # entry close: limit = last = 120.9; stop = q(120.9 - 2.63775) = q(118.26225) = 118.2623
    close = SwingParams(entry="close")
    assert SWING.targets(history, {"DIP"}, days[229], frozenset(), close) == (
        Target("DIP", QUARTER, P("120.9"), P("120.9"), P("118.2623"), None),
    )
    # take 1 ATR above the dip limit: q(120.3725 + 1.0551) = 121.4276; no stop
    take = SwingParams(take_atr=Decimal("1.0"), stop_atr=None)
    assert SWING.targets(history, {"DIP"}, days[229], frozenset(), take) == (
        Target("DIP", QUARTER, P("120.9"), P("120.3725"), None, P("121.4276")),
    )


@pytest.mark.parametrize(
    ("atr", "limit", "stop"),
    [
        # atr 1.2345: limit = q(50 - 0.61725) = 49.3828; stop = q(49.3828 - 3.08625) = q(46.29655) = 46.2966
        (1.2345, "49.3828", "46.2966"),
        # ATR quantized first: 1.23456789 -> 1.2346; limit = q(50 - 0.6173) = 49.3827;
        # stop = q(49.3827 - 3.0865) = 46.2962
        (1.23456789, "49.3827", "46.2962"),
    ],
)
def test_entry_prices_at_four_dp(atr, limit, stop):
    assert entry_target(sf(close=50.0, atr=atr), DEFAULT) == Target("AAA", QUARTER, P("50"), P(limit), P(stop), None)


@pytest.mark.parametrize(
    ("close", "atr", "params"),
    [
        (1.0, 3.0, DEFAULT),  # limit = 1 - 1.5 < 0
        (1.0, 2.0, DEFAULT),  # limit = 0
        (1.0, 0.4, DEFAULT),  # limit 0.8, stop = 0.8 - 1.0 < 0
        (50.0, 0.0, DEFAULT),  # zero ATR: stop == limit
        (50.0, 0.00004, DEFAULT),  # ATR rounds to 0.0000: stop == limit
        (50.0, 0.0001, SwingParams(stop_atr=None, take_atr=Decimal("0.25"))),  # take = q(50 + 0.000025) == limit
        (0.00004, 0.00001, DEFAULT),  # last rounds to 0.0000
    ],
)
def test_invalid_orderings_are_dropped_not_raised(close, atr, params):
    f = sf(close=close, sma=close / 2, atr=atr)
    assert entry_target(f, params) is None
    assert rank_entries([f], params, 4) == ()


def test_no_stop_no_take_is_a_plain_limit():
    # zero ATR with no stop and no TP: limit == last is a valid target
    assert entry_target(sf(close=50.0, atr=0.0), SwingParams(stop_atr=None)) == Target(
        "AAA", QUARTER, P("50"), P("50"), None, None
    )


def test_weight_is_one_over_slots():
    for slots, w in ((1, "1"), (3, "0.333333"), (8, "0.125")):
        t = entry_target(sf(), SwingParams(slots=slots))
        assert t is not None and t.weight == Decimal(w) == equal_weight(slots)


def test_rank_entries_by_rsi_then_symbol_and_capped():
    feats = [
        sf("MMM", rsi=3.0),
        sf("ZZZ", rsi=1.0),
        sf("AAA", rsi=3.0),
        sf("BBB", rsi=7.0),
        sf("CCC", rsi=2.0),
        sf("NOP", rsi=12.0),  # fails the setup
    ]
    assert [t.symbol for t in rank_entries(feats, DEFAULT, 10)] == ["ZZZ", "CCC", "AAA", "MMM", "BBB"]
    assert [t.symbol for t in rank_entries(feats, DEFAULT, 2)] == ["ZZZ", "CCC"]
    assert rank_entries(feats, DEFAULT, 0) == ()


# ---- held symbols, slots and the market gate (through targets) ------------------------------


def test_new_entries_ranked_and_non_members_excluded():
    days, history = dip_set()
    d = days[229]
    got = SWING.targets(history, {"DIP", "DIPB", "DIPC", "UP"}, d, frozenset(), DEFAULT)
    rsi = {f.symbol: f.rsi for f in features_at(history, history, d, DEFAULT)}
    assert rsi["DIPB"] < rsi["DIPC"] < rsi["DIP"] < 10.0 < rsi["UP"]  # the scenario is what it claims
    assert [t.symbol for t in got] == ["DIPB", "DIPC", "DIP"]  # UP has no dip
    assert [t.symbol for t in SWING.targets(history, {"DIP"}, d, frozenset(), DEFAULT)] == ["DIP"]
    assert SWING.targets(history, frozenset(), d, frozenset(), DEFAULT) == ()


def test_held_kept_first_in_symbol_order_then_new_until_slots():
    days, history = dip_set()
    d = days[229]
    members = frozenset(history)
    # DIPC and DIP are held without an exit signal (close < SMA5); DIPB is the one new entry that fits
    got = SWING.targets(history, members, d, frozenset({"DIPC", "DIP"}), SwingParams(slots=3))
    third = Decimal("0.333333")
    assert [(t.symbol, t.limit, t.stop, t.take) for t in got] == [
        ("DIP", None, None, None),
        ("DIPC", None, None, None),
        ("DIPB", got[2].limit, got[2].stop, None),
    ]
    assert got[2].limit is not None and got[2].stop is not None
    assert all(t.weight == third for t in got)
    assert got[0].last == P("120.9")  # kept targets carry the data_date close
    # slots full with kept: no new entry at all
    full = SWING.targets(history, members, d, frozenset({"DIPC", "DIP"}), SwingParams(slots=2))
    assert [t.symbol for t in full] == ["DIP", "DIPC"]


def test_held_with_exit_signal_is_dropped_and_frees_its_slot():
    days, history = dip_set()
    d = days[229]
    # UP rises every day: close > SMA5, so it is signal-exited (not returned); its slot goes to a new entry
    got = SWING.targets(history, frozenset(history), d, frozenset({"UP"}), SwingParams(slots=1))
    assert [t.symbol for t in got] == ["DIPB"]
    # RSI exit: UP's RSI(2) is 100 > 50; DIP's 3.6 is not
    rsi_exit = SwingParams(exit_sma=None, exit_rsi=50.0, slots=2)
    got = SWING.targets(history, frozenset(), d, frozenset({"UP", "DIP"}), rsi_exit)
    assert [t.symbol for t in got] == ["DIP"]
    # both exits off: held forever by signal
    never = SwingParams(exit_sma=None, exit_rsi=None)
    assert [t.symbol for t in SWING.targets(history, frozenset(), d, frozenset({"UP"}), never)] == ["UP"]


def test_held_without_a_bar_on_data_date_is_kept_at_its_last_close():
    days, history = dip_set()
    gappy = dict(history, DIP=drop_days(history["DIP"], [days[229]]))
    got = SWING.targets(gappy, frozenset(gappy), days[229], frozenset({"DIP"}), SwingParams(slots=1))
    # day 228's close: 100 + 22.8 - 1 = 121.8
    assert got == (Target("DIP", Decimal("1"), P("121.8")),)
    # a held symbol with no bar at all on or before data_date, or not in history, is not returned
    assert SWING.targets(gappy, frozenset(), days[0], frozenset({"NOPE"}), DEFAULT) == ()


def test_held_that_left_the_index_is_kept_until_it_exits():
    days, history = dip_set()
    d = days[229]
    # DIP is no longer a member: kept while held (no exit signal), never a new entry otherwise
    assert [t.symbol for t in SWING.targets(history, frozenset({"UP"}), d, frozenset({"DIP"}), DEFAULT)] == ["DIP"]
    assert SWING.targets(history, frozenset({"UP"}), d, frozenset(), DEFAULT) == ()
    # with too little history to compute features it is still kept
    short = {"DIP": hist("DIP", dip(uptrend(50), 49), days=days[180:])}
    assert [t.symbol for t in SWING.targets(short, frozenset(), d, frozenset({"DIP"}), DEFAULT)] == ["DIP"]


def test_kept_never_exceed_slots():
    days, history = dip_set()
    got = SWING.targets(history, frozenset(), days[229], frozenset({"DIP", "DIPB", "DIPC"}), SwingParams(slots=2))
    assert [t.symbol for t in got] == ["DIP", "DIPB"]  # symbol order, truncated at slots
    assert sum(t.weight for t in got) <= 1


def market(closes: list[float], days: list[date]) -> History:
    return hist("SPY", closes, days=days)


def test_market_trend_gates_new_entries_only():
    days, history = dip_set()
    d = days[229]
    gated = SwingParams(market_trend=("SPY", 200))
    up = dict(history, SPY=market(uptrend(230, first=200.0), days))
    down = dict(history, SPY=market([300.0 - 0.1 * t for t in range(230)], days))
    members = frozenset({"DIP", "DIPB", "DIPC"})
    assert [t.symbol for t in SWING.targets(up, members, d, frozenset(), gated)] == ["DIPB", "DIPC", "DIP"]
    assert SWING.targets(down, members, d, frozenset(), gated) == ()
    # held are kept when the gate is shut
    assert [t.symbol for t in SWING.targets(down, members, d, frozenset({"DIPC"}), gated)] == ["DIPC"]
    # no SPY, too little SPY history, or no SPY bar on data_date: shut
    assert SWING.targets(history, members, d, frozenset(), gated) == ()
    short = dict(history, SPY=market(uptrend(199), days[31:]))
    assert SWING.targets(short, members, d, frozenset(), gated) == ()
    gap = dict(up, SPY=drop_days(up["SPY"], [d]))
    assert SWING.targets(gap, members, d, frozenset(), gated) == ()


def test_trend_on_is_strict():
    days = session_days(200)
    flat = {"SPY": market([100.0] * 200, days)}
    assert trend_on(flat, ("SPY", 200), days[-1]) is False  # close == SMA
    assert trend_on(flat, None, days[-1]) is True
    rising = {"SPY": market(uptrend(200), days)}
    assert trend_on(rising, ("SPY", 200), days[-1]) is True
    assert trend_on(rising, ("SPY", 201), days[-1]) is False


# ---- the targets / targets_prepared contract -------------------------------------------------


def contract_set() -> tuple[list[date], dict[str, History]]:
    days = session_days(320)
    spy = uptrend(260, first=200.0) + [225.9 - 0.8 * t for t in range(60)]
    return days, {
        "SAW": hist("SAW", sawtooth(320), days=days),
        "DIP": hist("DIP", dip(dip(dip(uptrend(320), 229), 260), 290, drop=2.0), days=days),
        "DIP2": hist("DIP2", dip(dip(uptrend(320, first=80.0, step=0.15), 240), 250, days=3), days=days),
        "DIP3": hist("DIP3", dip(dip(uptrend(320, first=50.0, step=0.05), 233, drop=0.8), 284, drop=0.6), days=days),
        "LATE": hist("LATE", dip(uptrend(260, first=40.0), 255, drop=0.7), days=days[60:]),
        "GAPPY": drop_days(
            hist("GAPPY", dip(uptrend(320, first=70.0), 235, drop=0.9), days=days), days[100:105] + [days[236]]
        ),
        "GONE": hist("GONE", dip(uptrend(270, first=90.0), 250, drop=1.2), days=days[:270]),
        "THIN": hist("THIN", dip(uptrend(320), 229), days=days, volume=1000.0),
        "SPY": hist("SPY", spy, days=days),
    }


def contract_members(days: list[date]) -> Callable[[date], frozenset[str]]:
    def members(d: date) -> frozenset[str]:
        out = {"SAW", "DIP", "DIP2", "DIP3", "GAPPY", "GONE", "THIN"}
        if d >= days[280]:
            out.add("LATE")
        if d >= days[255]:
            out.discard("DIP2")  # leaves the index while possibly held
        return frozenset(out)

    return members


def held_path(history: dict[str, History], days: list[date], members, params: SwingParams) -> dict[date, frozenset[str]]:
    """Held on each data_date = what the single-window path targeted the day before (fills ignored)."""
    held: frozenset[str] = frozenset()
    out: dict[date, frozenset[str]] = {}
    for d in days:
        out[d] = held
        held = frozenset(t.symbol for t in SWING.targets(upto_all(history, d), members(d), d, held, params))
    return out


CONTRACT_PARAMS = [
    DEFAULT,
    SwingParams(rsi_max=60.0),
    SwingParams(slots=2, entry="close", take_atr=Decimal("1.0"), exit_sma=None, exit_rsi=70.0),
    SwingParams(market_trend=("SPY", 200)),
    SwingParams(stop_atr=None, rsi_max=100.0, slots=8),
    SwingParams(rsi_n=3, rsi_max=30.0),  # not covered by the prepared columns: single-window path
    SwingParams(sma_n=220),  # member window 220: single-window path
]
CONTRACT_IDS = ["default", "loose", "close-take-rsi-exit", "trend", "nostop-wide", "rsi3", "sma220"]


@pytest.mark.parametrize("params", CONTRACT_PARAMS, ids=CONTRACT_IDS)
def test_targets_prepared_equals_targets_on_every_date(params):
    days, history = contract_set()
    members = contract_members(days)
    held = held_path(history, days[190:], members, params)
    prepared = SWING.prepare(history)
    assert isinstance(prepared, SwingPrepared)
    kept_days = new_days = exits = 0
    for d in days[190:]:
        visible = upto_all(history, d)
        if prepared.covers(params):
            assert prepared.features_on(d, params) == features_at(visible, visible, d, params), d  # bit-identical
        expected = SWING.targets(visible, members(d), d, held[d], params)
        assert SWING.targets_prepared(prepared, members(d), d, held[d], params) == expected, d
        assert SWING.targets(history, members(d), d, held[d], params) == expected, d  # later bars ignored
        symbols = [t.symbol for t in expected]
        assert len(set(symbols)) == len(symbols) and sum(t.weight for t in expected) <= 1
        kept_days += any(s in held[d] for s in symbols)
        new_days += any(s not in held[d] for s in symbols)
        exits += len(held[d] - set(symbols))
    assert kept_days > 0 and new_days > 0 and exits > 0  # every branch fired: the check is not vacuous


def test_prepared_coverage():
    _, history = contract_set()
    prepared = SWING.prepare(history)
    assert prepared.covers(DEFAULT) and prepared.covers(SwingParams(exit_sma=None, exit_rsi=60.0))
    assert prepared.covers(SwingParams(market_trend=("SPY", 300)))  # the trend reads history directly
    for p in (SwingParams(rsi_n=3), SwingParams(sma_n=150), SwingParams(exit_sma=10), SwingParams(exit_sma=250)):
        assert not prepared.covers(p)
        with pytest.raises(ValueError, match="cover"):
            prepared.features_on(date(2019, 11, 1), p)


def test_prepare_on_short_or_empty_history():
    short = {"X": hist("X", sawtooth(150))}
    d = date(2019, 6, 3)
    for history in ({}, short):
        prepared = SWING.prepare(history)
        assert prepared.features_on(d, DEFAULT) == ()
        assert SWING.targets_prepared(prepared, {"X"}, d, frozenset(), DEFAULT) == ()
        assert SWING.targets(history, {"X"}, d, frozenset(), DEFAULT) == ()
    # a held symbol with a short history is kept on both paths
    prepared = SWING.prepare(short)
    want = SWING.targets(short, {"X"}, d, frozenset({"X"}), DEFAULT)
    assert [t.symbol for t in want] == ["X"]
    assert SWING.targets_prepared(prepared, {"X"}, d, frozenset({"X"}), DEFAULT) == want


# ---- no look-ahead --------------------------------------------------------------------------


LOOK_AHEAD_PARAMS = (DEFAULT, SwingParams(market_trend=("SPY", 200)), SwingParams(rsi_n=3, rsi_max=30.0))


@pytest.mark.parametrize("mutation", ["change", "truncate"])
def test_no_look_ahead(mutation):
    """Changing (or deleting) every bar dated on or after S leaves S's targets unchanged."""
    days, history = contract_set()
    members = contract_members(days)
    prepared = SWING.prepare(history)
    held = {p: held_path(history, days[220:], members, p) for p in LOOK_AHEAD_PARAMS}
    nonempty = 0
    for s in days[221:]:
        d = prev_session(s)
        if mutation == "change":
            future = {k: mutate_from(h, s) for k, h in history.items()}
        else:
            future = {k: truncate_before(h, s) for k, h in history.items()}
        future_prepared = SWING.prepare(future)
        for params in LOOK_AHEAD_PARAMS:
            h = held[params][d]
            before = SWING.targets(history, members(d), d, h, params)
            assert SWING.targets(future, members(d), d, h, params) == before, s
            assert SWING.targets_prepared(future_prepared, members(d), d, h, params) == before, s
            assert SWING.targets_prepared(prepared, members(d), d, h, params) == before, s
            nonempty += bool(before)
    assert nonempty > 0


def test_the_mutation_does_change_later_targets():
    # Guards test_no_look_ahead: the same mutation, read at data_date = S, changes the targets.
    days, history = contract_set()
    s = days[229]
    future = {k: mutate_from(h, s) for k, h in history.items()}
    members = frozenset(history) - {"SPY"}
    loose = SwingParams(rsi_max=100.0)
    assert SWING.targets(future, members, s, frozenset(), loose) != SWING.targets(history, members, s, frozenset(), loose)


def test_kit_identity_and_no_look_ahead():
    """The shared phase-2 checkers (tests/allocatorkit.py; plan index D-E) agree on F7."""
    days, history = contract_set()
    members = contract_members(days)
    # Fixed held sets on every date: nothing, two dipping members (one leaves the index at day
    # 255), and a gappy member plus one whose bars end at day 270 (kept at its last close).
    held_sets = [frozenset(), frozenset({"DIP", "DIP2"}), frozenset({"GAPPY", "GONE"})]
    params = [DEFAULT, SwingParams(market_trend=("SPY", 200))]
    assert assert_p4_identity(SWING, history, members, days[220:], held_sets, params) > 0
    assert assert_no_lookahead(SWING, history, members, days[221:300:3], held_sets, params) > 0
