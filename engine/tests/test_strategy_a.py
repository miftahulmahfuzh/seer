"""Strategy A and the strategy interface (handover §6.1–§6.3, plan Decisions)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import numpy as np
import pytest
from simkit import P, bar
from stratkit import (
    dip,
    drop_days,
    feat,
    hist,
    mutate_from,
    sawtooth,
    session_days,
    truncate_before,
    uptrend,
)

from seer_engine.dates import prev_session
from seer_engine.sim import Pick
from seer_engine.strategies import (
    DESIGN_PARAMS,
    STRATEGY_A,
    AParams,
    APrepared,
    History,
    Strategy,
    features_at,
    history_from_bars,
    picks_from_features,
)
from seer_engine.strategies.a import ATR_N, DV_N, LOOKBACK, RSI_N, SMA_N

PERMISSIVE = AParams(rsi_max=100.0)  # every RSI(2) strictly below 100 passes


def upto_all(history: dict[str, History], d: date) -> dict[str, History]:
    return {s: h.upto(d) for s, h in history.items()}


# ---- params and identity -------------------------------------------------------------------


def test_design_params_are_the_design_values():
    assert (SMA_N, RSI_N, ATR_N, DV_N, LOOKBACK) == (200, 2, 14, 20, 200)
    assert DESIGN_PARAMS == AParams(10.0, Decimal("0.5"), Decimal("1.0"), Decimal("1.5"), 20_000_000.0)
    assert DESIGN_PARAMS.as_dict() == {
        "rsi_max": "10",
        "limit_atr": "0.5",
        "tp_atr": "1",
        "sl_atr": "1.5",
        "min_dollar_volume": "20000000",
    }


def test_as_dict_is_plain_and_ordered():
    p = AParams(rsi_max=5, limit_atr=Decimal("0.25"), tp_atr=Decimal("0.75"), sl_atr=Decimal("2.0"))
    assert p.rsi_max == 5.0 and isinstance(p.rsi_max, float)
    assert list(p.as_dict().items()) == [
        ("rsi_max", "5"),
        ("limit_atr", "0.25"),
        ("tp_atr", "0.75"),
        ("sl_atr", "2"),
        ("min_dollar_volume", "20000000"),
    ]


@pytest.mark.parametrize(
    ("kw", "exc"),
    [
        ({"limit_atr": 0.5}, TypeError),
        ({"rsi_max": "10"}, TypeError),
        ({"rsi_max": 0.0}, ValueError),
        ({"rsi_max": 100.5}, ValueError),
        ({"tp_atr": Decimal("0")}, ValueError),
        ({"sl_atr": Decimal("-1")}, ValueError),
        ({"limit_atr": Decimal("-0.1")}, ValueError),
        ({"min_dollar_volume": -1.0}, ValueError),
    ],
)
def test_aparams_rejects_bad_values(kw, exc):
    with pytest.raises(exc):
        AParams(**kw)


def test_strategy_a_implements_the_protocol():
    assert isinstance(STRATEGY_A, Strategy)
    assert (STRATEGY_A.id, STRATEGY_A.lookback) == ("A", 200)


def test_wrong_param_or_prepared_types_raise():
    h = {"S": hist("S", sawtooth(210))}
    d = h["S"].last_date()
    with pytest.raises(TypeError):
        STRATEGY_A.picks(h, {"S"}, d, {"rsi_max": 10})
    with pytest.raises(TypeError):
        STRATEGY_A.picks_prepared(object(), {"S"}, d, DESIGN_PARAMS)
    with pytest.raises(TypeError):
        STRATEGY_A.picks_prepared(STRATEGY_A.prepare(h), {"S"}, d, None)


# ---- History -------------------------------------------------------------------------------


def test_history_upto_last_date_and_index_of():
    h = hist("X", [1.0, 2.0, 3.0, 4.0], days=[date(2020, 1, 2), date(2020, 1, 3), date(2020, 1, 7), date(2020, 1, 8)])
    assert len(h) == 4 and h.last_date() == date(2020, 1, 8)
    assert h.index_of(date(2020, 1, 7)) == 2
    assert h.index_of(date(2020, 1, 6)) is None  # a gap
    assert h.index_of(date(2020, 1, 9)) is None
    cut = h.upto(date(2020, 1, 6))
    assert len(cut) == 2 and cut.last_date() == date(2020, 1, 3) and cut.close.tolist() == [1.0, 2.0]
    assert h.upto(date(2020, 2, 1)) is h
    assert len(h.upto(date(2019, 12, 31))) == 0 and h.upto(date(2019, 12, 31)).last_date() is None


def test_history_validates_its_arrays():
    days = np.array([date(2020, 1, 3), date(2020, 1, 2)], dtype="datetime64[D]")
    one = np.ones(2, dtype=np.float64)
    with pytest.raises(ValueError, match="ascending"):
        History("X", days, one, one, one, one, one)
    with pytest.raises(TypeError, match="float64"):
        History("X", days[::-1], one, one, one, np.ones(2, dtype=np.int64), one)
    with pytest.raises(ValueError, match="shape"):
        History("X", days[::-1], one, one, one, np.ones(3), one)
    with pytest.raises(TypeError, match="datetime64"):
        History("X", np.array([1, 2]), one, one, one, one, one)


def test_history_from_bars_converts_decimals_to_floats():
    bars = [bar("X", "2020-01-02", "10", "11", "9.5", "10.1234", 500), bar("X", "2020-01-03", "10", "12", "9", "11", 7)]
    h = history_from_bars("X", bars)
    assert h.dates.tolist() == [date(2020, 1, 2), date(2020, 1, 3)]
    assert h.close.tolist() == [10.1234, 11.0] and h.volume.tolist() == [500.0, 7.0]
    assert h.high.tolist() == [11.0, 12.0] and h.low.tolist() == [9.5, 9.0] and h.open.tolist() == [10.0, 10.0]
    assert not h.close.flags.writeable
    with pytest.raises(ValueError, match="bar for Y"):
        history_from_bars("X", [bar("Y", "2020-01-02", "1", "1", "1", "1")])


# ---- features ------------------------------------------------------------------------------


def test_features_hand_computed_on_a_line():
    # closes 1..200, high = c + 0.5, low = c - 0.5, volume 1000
    # SMA200 = mean(1..200) = 100.5; RSI = 100 (no loss); TR = max(1, 1.5, 0.5) = 1.5 -> ATR 1.5;
    # dollar volume = 1000 * mean(181..200) = 190500
    h = {"LIN": hist("LIN", [float(t + 1) for t in range(200)], volume=1000.0)}
    d = h["LIN"].last_date()
    [f] = features_at(h, d)
    assert (f.symbol, f.data_date, f.close, f.sma, f.rsi, f.atr, f.dollar_volume) == (
        "LIN", d, 200.0, 100.5, 100.0, 1.5, 190500.0,
    )


def test_eligibility_needs_lookback_bars_and_a_bar_on_data_date():
    days = session_days(201)
    closes = sawtooth(201)
    h199 = {"X": hist("X", closes[:199], days=days[:199])}
    h200 = {"X": hist("X", closes[:200], days=days[:200])}
    assert features_at(h199, days[198]) == []  # 199 bars: not yet
    assert [f.symbol for f in features_at(h200, days[199])] == ["X"]  # 200 bars: eligible
    gappy = {"X": drop_days(hist("X", closes, days=days), [days[200]])}
    assert features_at(gappy, days[200]) == []  # no bar on data_date


def test_features_read_only_the_last_lookback_bars():
    days = session_days(300)
    tail = sawtooth(200, first=150.0)
    a = {"X": hist("X", [50.0 + t for t in range(100)] + tail, days=days)}
    b = {"X": hist("X", [999.0 - t for t in range(100)] + tail, days=days)}
    c = {"X": hist("X", tail, days=days[100:])}
    assert features_at(a, days[-1]) == features_at(b, days[-1]) == features_at(c, days[-1])


def test_features_are_sorted_by_symbol():
    h = {s: hist(s, sawtooth(200)) for s in ("MMM", "AAA", "ZZZ")}
    assert [f.symbol for f in features_at(h, h["AAA"].last_date())] == ["AAA", "MMM", "ZZZ"]


def test_dip_in_uptrend_hand_computed():
    # uptrend 100 + 0.1 t, then two days each net -0.9 at t = 228, 229 (data_date = day 229).
    # close  = 100 + 22.9 - 2 = 120.9
    # SMA200 = mean(100 + 0.1 t, t = 30..229) - (1 + 2)/200 = 112.95 - 0.015 = 112.935
    # RSI(2): avgG 0.1 -> 0.05 -> 0.025, avgL 0 -> 0.45 -> 0.675; 100 - 100/(1 + 1/27) = 100/28
    # ATR(14): TR 1.0 on rising days, 1.4 on the drops; (13 + 1.4)/14, then (14.4/14·13 + 1.4)/14 = 206.8/196
    # DV = 1e6 · (mean(100 + 0.1 t, t = 210..229) - 0.15) = 121.8e6
    days = session_days(230)
    h = {"DIP": hist("DIP", dip(uptrend(230), 229), days=days)}
    [f] = features_at(h, days[229])
    assert f.close == pytest.approx(120.9, rel=1e-12)
    assert f.sma == pytest.approx(112.935, rel=1e-12)
    assert f.rsi == pytest.approx(100 / 28, rel=1e-9)
    assert f.atr == pytest.approx(206.8 / 196, rel=1e-12)
    assert f.dollar_volume == pytest.approx(121.8e6, rel=1e-12)
    # last = 120.9000, ATR -> 1.0551; limit = q(120.9 - 0.52755) = 120.3725 (half-up)
    # tp = q(120.3725 + 1.0551) = 121.4276; sl = q(120.3725 - 1.58265) = 118.7899
    assert STRATEGY_A.picks(h, {"DIP"}, days[229], DESIGN_PARAMS) == [
        Pick("DIP", P("120.9"), P("120.3725"), P("121.4276"), P("118.7899"))
    ]


# ---- setup filter, each condition alone ----------------------------------------------------


@pytest.mark.parametrize(
    ("kw", "passes"),
    [
        ({}, True),
        ({"close": 40.0, "sma": 40.0}, False),  # close == SMA: strict
        ({"close": 39.0, "sma": 40.0}, False),  # below trend
        ({"rsi": 10.0}, False),  # RSI exactly rsi_max: strict
        ({"rsi": 9.999999}, True),
        ({"rsi": 50.0}, False),
        ({"dollar_volume": 20_000_000.0}, False),  # exactly the floor: strict
        ({"dollar_volume": 20_000_000.5}, True),
        ({"dollar_volume": 5_000_000.0}, False),
    ],
)
def test_setup_filter_each_condition_alone(kw, passes):
    out = picks_from_features([feat("AAA", **kw)], {"AAA"}, DESIGN_PARAMS)
    assert [p.symbol for p in out] == (["AAA"] if passes else [])


# ---- bracket prices ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("atr", "limit", "tp", "sl"),
    [
        # atr 1.2345: limit = q(50 - 0.61725) = 49.3828; tp = q(49.3828 + 1.2345) = 50.6173;
        # sl = q(49.3828 - 1.85175) = q(47.53105) = 47.5311 (half-up)
        (1.2345, "49.3828", "50.6173", "47.5311"),
        # ATR is quantized first: 1.23456789 -> 1.2346; limit = q(50 - 0.6173) = 49.3827;
        # tp = q(49.3827 + 1.2346) = 50.6173; sl = q(49.3827 - 1.8519) = 47.5308
        (1.23456789, "49.3827", "50.6173", "47.5308"),
    ],
)
def test_bracket_prices_at_four_dp(atr, limit, tp, sl):
    [pick] = picks_from_features([feat("AAA", close=50.0, atr=atr)], {"AAA"}, DESIGN_PARAMS)
    assert pick == Pick("AAA", P("50"), P(limit), P(tp), P(sl))


def test_bracket_follows_the_params():
    # limit = 50 - 0.25·2 = 49.5; tp = 49.5 + 1.5·2 = 52.5; sl = 49.5 - 2.0·2 = 45.5
    p = AParams(limit_atr=Decimal("0.25"), tp_atr=Decimal("1.5"), sl_atr=Decimal("2.0"))
    assert picks_from_features([feat("AAA", close=50.0, atr=2.0)], {"AAA"}, p) == [
        Pick("AAA", P("50"), P("49.5"), P("52.5"), P("45.5"))
    ]


@pytest.mark.parametrize(
    ("close", "atr", "params"),
    [
        (1.0, 3.0, DESIGN_PARAMS),  # limit = 1 - 1.5 < 0
        (1.0, 2.0, DESIGN_PARAMS),  # limit = 0
        (1.0, 0.5, DESIGN_PARAMS),  # limit 0.75, sl = 0.75 - 0.75 = 0
        (50.0, 0.0, DESIGN_PARAMS),  # zero ATR: sl == limit == tp
        (50.0, 0.00004, DESIGN_PARAMS),  # ATR rounds to 0.0000
        (50.0, 0.0001, AParams(sl_atr=Decimal("0.25"))),  # sl = q(50.0000 - 0.000025) == limit
        (50.0, 0.0001, AParams(tp_atr=Decimal("0.25"))),  # tp = q(50.0000 + 0.000025) == limit
        (0.00004, 0.00001, DESIGN_PARAMS),  # last rounds to 0.0000
    ],
)
def test_invalid_brackets_are_dropped_not_raised(close, atr, params):
    assert picks_from_features([feat("AAA", close=close, sma=close / 2, atr=atr)], {"AAA"}, params) == []


# ---- ranking and membership ----------------------------------------------------------------


def test_ranking_is_rsi_then_symbol_and_uncapped():
    features = [
        feat("MMM", rsi=3.0),
        feat("ZZZ", rsi=1.0),
        feat("AAA", rsi=3.0),
        feat("BBB", rsi=7.0),
        feat("CCC", rsi=2.0),
        feat("DDD", rsi=9.5),
    ]
    out = picks_from_features(features, {f.symbol for f in features}, DESIGN_PARAMS)
    assert [p.symbol for p in out] == ["ZZZ", "CCC", "AAA", "MMM", "BBB", "DDD"]


def test_non_members_are_excluded():
    features = [feat("AAA", rsi=1.0), feat("BBB", rsi=2.0)]
    assert [p.symbol for p in picks_from_features(features, {"BBB"}, DESIGN_PARAMS)] == ["BBB"]
    assert picks_from_features(features, frozenset(), DESIGN_PARAMS) == []


def test_symbols_joining_and_leaving_mid_window():
    days = session_days(260)
    history = {s: hist(s, sawtooth(260, first=f), days=days) for s, f in (("STAY", 100.0), ("JOIN", 80.0), ("LEAVE", 60.0))}
    join, leave = days[220], days[240]

    def members(d: date) -> frozenset[str]:
        return frozenset({"STAY"} | ({"JOIN"} if d >= join else set()) | ({"LEAVE"} if d < leave else set()))

    prepared = STRATEGY_A.prepare(history)
    for d in days[199:]:
        expected = sorted(members(d))
        got = STRATEGY_A.picks(history, members(d), d, PERMISSIVE)
        assert sorted(p.symbol for p in got) == expected, d
        assert STRATEGY_A.picks_prepared(prepared, members(d), d, PERMISSIVE) == got, d


# ---- no look-ahead -------------------------------------------------------------------------


def lookahead_set() -> dict[str, History]:
    days = session_days(260)
    return {
        "DIP": hist("DIP", dip(uptrend(260), 229), days=days),
        "DIP2": hist("DIP2", dip(dip(uptrend(260, first=80.0, step=0.15), 240), 250, days=3), days=days),
        "SAW": hist("SAW", sawtooth(260), days=days),
    }


@pytest.mark.parametrize("mutation", ["change", "truncate"])
def test_no_look_ahead(mutation):
    """Changing (or deleting) every bar dated on or after S leaves S's picks unchanged."""
    history = lookahead_set()
    days = session_days(260)
    prepared = STRATEGY_A.prepare(history)
    nonempty = 0
    for s in days[200:]:
        data_date = prev_session(s)
        if mutation == "change":
            future = {k: mutate_from(h, s) for k, h in history.items()}
        else:
            future = {k: truncate_before(h, s) for k, h in history.items()}
        members = frozenset(history)
        for params in (DESIGN_PARAMS, PERMISSIVE):
            before = STRATEGY_A.picks(history, members, data_date, params)
            assert STRATEGY_A.picks(future, members, data_date, params) == before, s
            assert STRATEGY_A.picks_prepared(STRATEGY_A.prepare(future), members, data_date, params) == before, s
            assert STRATEGY_A.picks_prepared(prepared, members, data_date, params) == before, s
            nonempty += params is DESIGN_PARAMS and bool(before)
    assert nonempty >= 2  # the design setup fired on the dip days, so the check is not vacuous


def test_the_mutation_does_change_later_picks():
    # Guards test_no_look_ahead: the same mutation, read at data_date = S, changes the picks.
    history = lookahead_set()
    s = session_days(260)[230]
    future = {k: mutate_from(h, s) for k, h in history.items()}
    members = frozenset(history)
    assert STRATEGY_A.picks(future, members, s, PERMISSIVE) != STRATEGY_A.picks(history, members, s, PERMISSIVE)


# ---- the picks / picks_prepared contract ---------------------------------------------------


def contract_set() -> tuple[list[date], dict[str, History]]:
    days = session_days(320)
    return days, {
        "SAW": hist("SAW", sawtooth(320), days=days),
        "DIP": hist("DIP", dip(dip(dip(uptrend(320), 229), 260), 290, drop=2.0), days=days),
        "LATE": hist("LATE", sawtooth(260, first=40.0, up=0.9, down=0.5), days=days[60:]),
        "GAPPY": drop_days(hist("GAPPY", sawtooth(320, first=70.0), days=days), days[100:105] + [days[250]]),
        "GONE": hist("GONE", sawtooth(270, first=90.0), days=days[:270]),
        "THIN": hist("THIN", dip(uptrend(320), 229), days=days, volume=1000.0),
    }


@pytest.mark.parametrize(
    "params",
    [DESIGN_PARAMS, PERMISSIVE, AParams(rsi_max=60.0, limit_atr=Decimal("0.25"), tp_atr=Decimal("1.5"))],
    ids=["design", "permissive", "mid"],
)
def test_picks_prepared_equals_picks_on_every_date(params):
    days, history = contract_set()

    def members(d: date) -> frozenset[str]:
        out = set(history) - {"LATE"} if d < days[280] else set(history)
        return frozenset(out - {"SAW"} if days[240] <= d < days[260] else out)

    prepared = STRATEGY_A.prepare(history)
    assert isinstance(prepared, APrepared)
    nonempty = 0
    for d in days[190:]:
        visible = upto_all(history, d)
        assert prepared.features_on(d) == features_at(visible, d), d  # bit-identical floats
        expected = STRATEGY_A.picks(visible, members(d), d, params)
        assert STRATEGY_A.picks_prepared(prepared, members(d), d, params) == expected, d
        assert STRATEGY_A.picks(history, members(d), d, params) == expected, d  # later bars ignored
        nonempty += bool(expected)
    assert nonempty > 0


def test_prepare_on_short_or_empty_history():
    short = {"X": hist("X", sawtooth(150))}
    for history in ({}, short):
        prepared = STRATEGY_A.prepare(history)
        assert prepared.features_on(date(2019, 6, 3)) == []
        assert STRATEGY_A.picks_prepared(prepared, {"X"}, date(2019, 6, 3), PERMISSIVE) == []
        assert STRATEGY_A.picks(history, {"X"}, date(2019, 6, 3), PERMISSIVE) == []
