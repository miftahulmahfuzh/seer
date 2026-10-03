"""Strategy A2 and its variants V0–V3 (P3b handover §3, §6.1–§6.2, §6.5; plan Decisions D2, D4, D5)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import numpy as np
import pytest
from simkit import P
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

from seer_engine import universe
from seer_engine.dates import prev_session
from seer_engine.sim import Pick
from seer_engine.strategies import (
    A2_DESIGN_PARAMS,
    DESIGN_PARAMS,
    STRATEGY_A,
    STRATEGY_A2,
    VARIANTS,
    A2Params,
    A2Prepared,
    AParams,
    History,
    Strategy,
    features_at,
)
from seer_engine.strategies.a2 import (
    FLOOR_PRICE,
    REGIME_SYMBOL,
    picks_from_features_a2,
    regime_on,
)

PERMISSIVE = AParams(rsi_max=100.0)  # every RSI(2) strictly below 100 passes
MID = AParams(rsi_max=60.0, limit_atr=Decimal("0.25"), tp_atr=Decimal("1.5"))
A_PARAMS = (DESIGN_PARAMS, PERMISSIVE, MID)
A_IDS = ["design", "permissive", "mid"]


def upto_all(history: dict[str, History], d: date) -> dict[str, History]:
    return {s: h.upto(d) for s, h in history.items()}


def every(variant_params: AParams = DESIGN_PARAMS) -> list[A2Params]:
    """One A2Params per variant, in VARIANTS order, with ``variant_params``' five values."""
    return [A2Params.from_a(v, variant_params) for v in VARIANTS]


def symbols(picks: list[Pick]) -> list[str]:
    return [p.symbol for p in picks]


def flat_spy(n: int, close: float = 100.0, days: list[date] | None = None) -> History:
    """SPY with ``n`` identical closes: SMA(200) == close exactly in float, so the regime is OFF."""
    return hist(REGIME_SYMBOL, [close] * n, days=days)


def spy_closes(n: int) -> list[float]:
    """Rise 0.2/day for 250 bars, fall 1.5/day for 25, then rise 2.0/day: the regime goes on, off, on."""
    out: list[float] = []
    for t in range(n):
        if t < 250:
            out.append(100.0 + 0.2 * t)
        elif t < 275:
            out.append(out[-1] - 1.5)
        else:
            out.append(out[-1] + 2.0)
    return out


# ---- constants and params ------------------------------------------------------------------


def test_constants():
    assert VARIANTS == ("control", "regime", "regime_calm", "regime_calm_floor")
    assert REGIME_SYMBOL == universe.BENCHMARK == "SPY"
    assert FLOOR_PRICE == 10.0
    assert A2_DESIGN_PARAMS == A2Params() == A2Params.from_a("control", DESIGN_PARAMS)
    assert A2_DESIGN_PARAMS.a_params() == DESIGN_PARAMS


def test_a2params_defaults_coercion_and_as_dict():
    p = A2Params(variant="regime_calm", rsi_max=5, limit_atr=Decimal("0.25"), sl_atr=Decimal("2.0"))
    assert p.rsi_max == 5.0 and isinstance(p.rsi_max, float)
    assert isinstance(p.min_dollar_volume, float)
    assert list(p.as_dict().items()) == [
        ("variant", "regime_calm"),
        ("rsi_max", "5"),
        ("limit_atr", "0.25"),
        ("tp_atr", "1"),
        ("sl_atr", "2"),
        ("min_dollar_volume", "20000000"),
    ]
    assert p.a_params() == AParams(rsi_max=5.0, limit_atr=Decimal("0.25"), sl_atr=Decimal("2.0"))
    assert A2Params(min_dollar_volume=1).min_dollar_volume == 1.0


def test_from_a_round_trips_and_params_are_hashable():
    for variant in VARIANTS:
        for a in A_PARAMS:
            p = A2Params.from_a(variant, a)
            assert (p.variant, p.a_params()) == (variant, a)
    assert len({A2Params.from_a(v, a) for v in VARIANTS for a in A_PARAMS}) == len(VARIANTS) * len(A_PARAMS)
    assert A2Params(variant="regime") != A2Params(variant="control")
    with pytest.raises(TypeError):
        A2Params.from_a("control", {"rsi_max": 10.0})


@pytest.mark.parametrize(
    ("kw", "exc"),
    [
        ({"variant": "V1"}, ValueError),
        ({"variant": "Control"}, ValueError),
        ({"variant": ""}, ValueError),
        ({"variant": None}, TypeError),
        ({"variant": 1}, TypeError),
        ({"limit_atr": 0.5}, TypeError),
        ({"rsi_max": "10"}, TypeError),
        ({"rsi_max": True}, TypeError),
        ({"rsi_max": 0.0}, ValueError),
        ({"rsi_max": 100.5}, ValueError),
        ({"tp_atr": Decimal("0")}, ValueError),
        ({"sl_atr": Decimal("-1")}, ValueError),
        ({"limit_atr": Decimal("-0.1")}, ValueError),
        ({"min_dollar_volume": -1.0}, ValueError),
    ],
)
def test_a2params_rejects_bad_values(kw, exc):
    with pytest.raises(exc):
        A2Params(**kw)


def test_strategy_a2_implements_the_protocol():
    assert isinstance(STRATEGY_A2, Strategy)
    assert (STRATEGY_A2.id, STRATEGY_A2.lookback) == ("A2", 200)


def test_wrong_param_prepared_or_date_types_raise():
    h = {"S": hist("S", sawtooth(210)), "SPY": hist("SPY", uptrend(210))}
    d = h["S"].last_date()
    with pytest.raises(TypeError):
        STRATEGY_A2.picks(h, {"S"}, d, DESIGN_PARAMS)  # AParams is not A2Params
    with pytest.raises(TypeError):
        STRATEGY_A2.picks(h, {"S"}, d, {"variant": "control"})
    with pytest.raises(TypeError):
        STRATEGY_A2.picks_prepared(STRATEGY_A.prepare(h), {"S"}, d, A2_DESIGN_PARAMS)  # APrepared, not A2Prepared
    with pytest.raises(TypeError):
        STRATEGY_A2.picks_prepared(STRATEGY_A2.prepare(h), {"S"}, d, None)
    with pytest.raises(TypeError):
        picks_from_features_a2([feat("AAA")], {"AAA"}, DESIGN_PARAMS, True)
    with pytest.raises(TypeError):
        regime_on(h["SPY"], datetime(2019, 10, 15))
    with pytest.raises(TypeError):
        regime_on(None, "2019-10-15")
    with pytest.raises(TypeError):
        STRATEGY_A2.prepare(h).regime_on(datetime(2019, 10, 15))


# ---- V1: the regime ------------------------------------------------------------------------


def test_flat_spy_sma_equals_close_exactly():
    # Guards the equality tests: 200 closes of 100.0 sum to 20000.0 exactly; / 200 == 100.0.
    days = session_days(200)
    spy = flat_spy(200, days=days)
    [f] = features_at({REGIME_SYMBOL: spy}, days[-1])
    assert f.close == f.sma == 100.0


@pytest.mark.parametrize(
    ("last", "on"),
    [
        (100.0, False),  # close == SMA(200): equality is OFF (strict)
        (99.5, False),  # below
        (100.5, True),  # SMA = (199·100 + 100.5) / 200 = 100.0025 < 100.5
    ],
)
def test_regime_boundary(last, on):
    days = session_days(200)
    spy = hist(REGIME_SYMBOL, [100.0] * 199 + [last], days=days)
    assert regime_on(spy, days[-1]) is on
    assert STRATEGY_A2.prepare({REGIME_SYMBOL: spy}).regime_on(days[-1]) is on


def test_regime_off_when_spy_missing_short_or_without_a_bar_on_data_date():
    days = session_days(201)
    rising = uptrend(201)
    assert regime_on(hist(REGIME_SYMBOL, rising, days=days), days[200]) is True
    assert regime_on(None, days[200]) is False
    assert regime_on(hist(REGIME_SYMBOL, rising[:199], days=days[:199]), days[198]) is False  # 199 bars
    assert regime_on(hist(REGIME_SYMBOL, rising[:200], days=days[:200]), days[199]) is True  # 200 bars
    gappy = drop_days(hist(REGIME_SYMBOL, rising, days=days), [days[200]])
    assert regime_on(gappy, days[200]) is False  # no SPY bar on data_date
    assert regime_on(hist(REGIME_SYMBOL, rising, days=days), date(2030, 1, 2)) is False  # after the last bar
    for history in ({}, {REGIME_SYMBOL: hist(REGIME_SYMBOL, rising[:199], days=days[:199])}, {REGIME_SYMBOL: gappy}):
        prepared = STRATEGY_A2.prepare(history)
        assert isinstance(prepared, A2Prepared)
        assert prepared.regime_on(days[200]) is False
        assert prepared.regime_on(days[198]) is False


def test_regime_reads_only_the_last_lookback_spy_bars():
    # 50 tiny closes then 200 flat ones: over all 250 bars the mean is < 100 (regime would be on),
    # but over the last 200 it is exactly 100 (off).
    days = session_days(250)
    spy = hist(REGIME_SYMBOL, [1.0] * 50 + [100.0] * 200, days=days)
    assert regime_on(spy, days[-1]) is False
    assert STRATEGY_A2.prepare({REGIME_SYMBOL: spy}).regime_on(days[-1]) is False
    short = hist(REGIME_SYMBOL, [100.0] * 200, days=days[50:])
    assert regime_on(short, days[-1]) is regime_on(spy, days[-1])


def test_regime_gates_new_picks_end_to_end():
    # DIP sets up on day 229 (see test_strategy_a.test_dip_in_uptrend_hand_computed).
    days = session_days(230)
    dipper = hist("DIP", dip(uptrend(230), 229), days=days)
    d = days[229]
    cases = {
        "spy rising": (hist(REGIME_SYMBOL, uptrend(230), days=days), True),
        "spy flat (close == SMA)": (flat_spy(230, days=days), False),
        "spy falling": (hist(REGIME_SYMBOL, uptrend(230, first=200.0, step=-0.1), days=days), False),
        "spy missing": (None, False),
    }
    for name, (spy, on) in cases.items():
        history = {"DIP": dipper} if spy is None else {"DIP": dipper, REGIME_SYMBOL: spy}
        prepared = STRATEGY_A2.prepare(history)
        assert prepared.regime_on(d) is on, name
        for p in every():
            got = STRATEGY_A2.picks(history, {"DIP"}, d, p)
            expected = ["DIP"] if (on or p.variant == "control") else []
            assert symbols(got) == expected, (name, p.variant)
            assert STRATEGY_A2.picks_prepared(prepared, {"DIP"}, d, p) == got, (name, p.variant)


def test_regime_flag_gates_variants_at_the_feature_level():
    features = [feat("AAA", rsi=2.0), feat("BBB", rsi=1.0)]
    members = {"AAA", "BBB"}
    for p in every():
        assert symbols(picks_from_features_a2(features, members, p, True)) == ["BBB", "AAA"], p.variant
        off = picks_from_features_a2(features, members, p, False)
        assert symbols(off) == (["BBB", "AAA"] if p.variant == "control" else []), p.variant


# ---- V2: ATR% ranking ----------------------------------------------------------------------


def calm_features() -> list:
    # ATR/close: LOW 0.01; TIE_R, TIE_A, TIE_B 0.02 (exactly equal floats); HIGH 0.05.
    return [
        feat("TIE_B", close=50.0, atr=1.0, rsi=3.0),
        feat("HIGH", close=50.0, atr=2.5, rsi=0.5),
        feat("TIE_A", close=100.0, atr=2.0, rsi=3.0),
        feat("LOW", close=50.0, atr=0.5, rsi=9.0),
        feat("TIE_R", close=25.0, sma=20.0, atr=0.5, rsi=1.0),
    ]


def test_atr_pct_ties_are_exact_floats():
    assert 1.0 / 50.0 == 2.0 / 100.0 == 0.5 / 25.0
    assert 0.5 / 50.0 < 1.0 / 50.0 < 2.5 / 50.0


def test_calm_ranking_is_atr_pct_then_rsi_then_symbol():
    features = calm_features()
    members = {f.symbol for f in features}
    by_rsi = ["HIGH", "TIE_R", "TIE_A", "TIE_B", "LOW"]
    by_atr_pct = ["LOW", "TIE_R", "TIE_A", "TIE_B", "HIGH"]
    expected = {"control": by_rsi, "regime": by_rsi, "regime_calm": by_atr_pct, "regime_calm_floor": by_atr_pct}
    for p in every():
        assert symbols(picks_from_features_a2(features, members, p, True)) == expected[p.variant], p.variant
    # the picks themselves (brackets) are the same objects V0 would make, only reordered
    v0 = picks_from_features_a2(features, members, A2_DESIGN_PARAMS, True)
    v2 = picks_from_features_a2(features, members, A2Params(variant="regime_calm"), True)
    assert sorted(v0, key=lambda p: p.symbol) == sorted(v2, key=lambda p: p.symbol)


def test_calm_ranking_is_uncapped_and_input_order_free():
    features = calm_features()
    members = {f.symbol for f in features}
    p = A2Params(variant="regime_calm", rsi_max=100.0)
    forward = picks_from_features_a2(features, members, p, True)
    backward = picks_from_features_a2(list(reversed(features)), members, p, True)
    assert forward == backward and len(forward) == len(features)


# ---- V3: the $10 floor ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("close", "kept"),
    [
        (10.0, True),  # exactly 10.0000: inclusive
        (10.0001, True),
        (9.9999, False),
        (9.0, False),
    ],
)
def test_floor_at_exactly_ten(close, kept):
    f = feat("AAA", close=close, sma=5.0, atr=1.0)
    for p in every():
        got = picks_from_features_a2([f], {"AAA"}, p, True)
        expected = ["AAA"] if (kept or p.variant != "regime_calm_floor") else []
        assert symbols(got) == expected, (close, p.variant)


def test_floor_reads_the_close_not_the_limit():
    # close 10.0, ATR 1.0: limit = 9.5 < 10, but the floor is on the close, so it is kept.
    [pick] = picks_from_features_a2(
        [feat("AAA", close=10.0, sma=5.0, atr=1.0)], {"AAA"}, A2Params(variant="regime_calm_floor"), True
    )
    assert pick == Pick("AAA", P("10"), P("9.5"), P("10.5"), P("8"))


# ---- SPY is never a pick -------------------------------------------------------------------


def test_spy_is_never_a_pick_even_as_a_member():
    features = [feat(REGIME_SYMBOL, rsi=0.5), feat("AAA", rsi=2.0)]
    for p in every():
        assert symbols(picks_from_features_a2(features, {REGIME_SYMBOL, "AAA"}, p, True)) == ["AAA"], p.variant
        assert picks_from_features_a2(features[:1], {REGIME_SYMBOL}, p, True) == [], p.variant


def test_spy_is_never_a_pick_end_to_end():
    # SPY itself dips on day 229 and would pass Strategy A's setup; DIP does too.
    days = session_days(230)
    history = {
        REGIME_SYMBOL: hist(REGIME_SYMBOL, dip(uptrend(230), 229), days=days),
        "DIP": hist("DIP", dip(uptrend(230, first=80.0), 229), days=days),
    }
    d = days[229]
    members = frozenset(history)
    assert symbols(STRATEGY_A.picks(history, members, d, DESIGN_PARAMS)) == ["DIP", REGIME_SYMBOL]  # guard: v1 would
    prepared = STRATEGY_A2.prepare(history)
    assert prepared.regime_on(d) is True
    for a in (DESIGN_PARAMS, PERMISSIVE):
        for p in every(a):
            got = STRATEGY_A2.picks(history, members, d, p)
            assert symbols(got) == ["DIP"], p.variant
            assert STRATEGY_A2.picks_prepared(prepared, members, d, p) == got, p.variant


# ---- the contract set: V0 == v1, and picks_prepared == picks for every variant --------------


def contract_set() -> tuple[list[date], dict[str, History]]:
    """test_strategy_a's contract set plus SPY (regime on, off, on again) and a stock crossing $10."""
    days = session_days(320)
    return days, {
        "SAW": hist("SAW", sawtooth(320), days=days),
        "DIP": hist("DIP", dip(dip(dip(uptrend(320), 229), 260), 290, drop=2.0), days=days),
        "LATE": hist("LATE", sawtooth(260, first=40.0, up=0.9, down=0.5), days=days[60:]),
        "GAPPY": drop_days(hist("GAPPY", sawtooth(320, first=70.0), days=days), days[100:105] + [days[250]]),
        "GONE": hist("GONE", sawtooth(270, first=90.0), days=days[:270]),
        "THIN": hist("THIN", dip(uptrend(320), 229), days=days, volume=1000.0),
        "PENNY": hist("PENNY", sawtooth(320, first=7.5, up=0.06, down=0.04), days=days, spread=0.05, volume=5e6),
        REGIME_SYMBOL: hist(REGIME_SYMBOL, spy_closes(320), days=days, volume=1e8),
    }


def contract_members(days: list[date], d: date, *, spy: bool) -> frozenset[str]:
    out = {"SAW", "DIP", "LATE", "GAPPY", "GONE", "THIN", "PENNY"}
    if d < days[280]:
        out.discard("LATE")
    if days[240] <= d < days[260]:
        out.discard("SAW")
    if spy:
        out.add(REGIME_SYMBOL)
    return frozenset(out)


def test_contract_set_exercises_every_rule():
    # Guards the two contract tests below: the regime is on and off, the ATR% order differs from the
    # RSI order, and the floor drops a pick, on some data_date in the tested range.
    days, history = contract_set()
    prepared = STRATEGY_A2.prepare(history)
    on = [prepared.regime_on(d) for d in days[190:]]
    assert any(on) and not all(on)
    differs = {"regime": 0, "regime_calm": 0, "regime_calm_floor": 0}
    for d in days[190:]:
        members = contract_members(days, d, spy=False)
        picks = {p.variant: STRATEGY_A2.picks(history, members, d, p) for p in every(PERMISSIVE)}
        differs["regime"] += picks["regime"] != picks["control"]
        differs["regime_calm"] += bool(picks["regime_calm"]) and picks["regime_calm"] != picks["regime"]
        differs["regime_calm_floor"] += picks["regime_calm_floor"] != picks["regime_calm"]
    assert all(n > 0 for n in differs.values()), differs


@pytest.mark.parametrize("a", A_PARAMS, ids=A_IDS)
def test_v0_picks_equal_strategy_a_picks(a):
    days, history = contract_set()
    v0 = A2Params.from_a("control", a)
    prepared_a = STRATEGY_A.prepare(history)
    prepared_a2 = STRATEGY_A2.prepare(history)
    nonempty = 0
    for d in days[190:]:
        members = contract_members(days, d, spy=False)
        expected = STRATEGY_A.picks(history, members, d, a)
        assert STRATEGY_A2.picks(history, members, d, v0) == expected, d
        assert STRATEGY_A2.picks_prepared(prepared_a2, members, d, v0) == expected, d
        assert STRATEGY_A.picks_prepared(prepared_a, members, d, a) == expected, d
        nonempty += bool(expected)
    assert nonempty > 0


@pytest.mark.parametrize("a", A_PARAMS, ids=A_IDS)
@pytest.mark.parametrize("variant", VARIANTS)
def test_picks_prepared_equals_picks_on_every_date(variant, a):
    days, history = contract_set()
    params = A2Params.from_a(variant, a)
    prepared = STRATEGY_A2.prepare(history)
    assert isinstance(prepared, A2Prepared)
    nonempty = 0
    for d in days[190:]:
        visible = upto_all(history, d)
        assert prepared.regime_on(d) is regime_on(visible[REGIME_SYMBOL], d), d  # bit-identical SMA
        members = contract_members(days, d, spy=d >= days[300])  # SPY listed as a member near the end
        expected = STRATEGY_A2.picks(visible, members, d, params)
        assert STRATEGY_A2.picks_prepared(prepared, members, d, params) == expected, d
        assert STRATEGY_A2.picks(history, members, d, params) == expected, d  # later bars ignored
        assert REGIME_SYMBOL not in symbols(expected), d
        nonempty += bool(expected)
    assert nonempty > 0


def test_prepared_regime_equals_regime_on_on_every_spy_date():
    days, history = contract_set()
    spy = history[REGIME_SYMBOL]
    prepared = STRATEGY_A2.prepare(history)
    assert prepared.regime_dates.tolist() == days[199:]
    assert prepared.regime.dtype == np.bool_ and prepared.regime.shape == prepared.regime_dates.shape
    for d in days:
        assert prepared.regime_on(d) is regime_on(spy, d), d
        assert prepared.regime_on(d) is regime_on(spy.upto(d), d), d


def test_prepare_on_short_or_empty_history_or_without_spy():
    d = date(2019, 6, 3)
    short = {"X": hist("X", sawtooth(150)), REGIME_SYMBOL: hist(REGIME_SYMBOL, uptrend(150))}
    for history in ({}, short):
        prepared = STRATEGY_A2.prepare(history)
        assert prepared.regime_dates.shape == (0,) and prepared.regime_on(d) is False
        for p in every(PERMISSIVE):
            assert STRATEGY_A2.picks_prepared(prepared, {"X"}, d, p) == []
            assert STRATEGY_A2.picks(history, {"X"}, d, p) == []
    days, history = contract_set()
    no_spy = {s: h for s, h in history.items() if s != REGIME_SYMBOL}
    prepared = STRATEGY_A2.prepare(no_spy)
    d = days[229]
    members = contract_members(days, d, spy=False)
    v0 = A2Params.from_a("control", PERMISSIVE)
    assert STRATEGY_A2.picks_prepared(prepared, members, d, v0) == STRATEGY_A.picks(no_spy, members, d, PERMISSIVE) != []
    for p in every(PERMISSIVE)[1:]:
        assert STRATEGY_A2.picks(no_spy, members, d, p) == STRATEGY_A2.picks_prepared(prepared, members, d, p) == []


# ---- no look-ahead, SPY's bars included ----------------------------------------------------


def lookahead_set() -> dict[str, History]:
    """test_strategy_a's look-ahead set plus a rising SPY (regime on from day 199)."""
    days = session_days(260)
    return {
        "DIP": hist("DIP", dip(uptrend(260), 229), days=days),
        "DIP2": hist("DIP2", dip(dip(uptrend(260, first=80.0, step=0.15), 240), 250, days=3), days=days),
        "SAW": hist("SAW", sawtooth(260), days=days),
        REGIME_SYMBOL: hist(REGIME_SYMBOL, uptrend(260, first=200.0, step=0.2), days=days, volume=1e8),
    }


def halve(x: np.ndarray) -> np.ndarray:
    return x * 0.5


@pytest.mark.parametrize("mutation", ["change", "halve", "truncate", "spy_only_halve", "spy_only_truncate"])
def test_no_look_ahead(mutation):
    """Changing (or deleting) every bar dated on or after S, SPY's included, leaves S's picks unchanged."""
    history = lookahead_set()
    days = session_days(260)
    prepared = STRATEGY_A2.prepare(history)
    members = frozenset(history) - {REGIME_SYMBOL}
    nonempty = {v: 0 for v in VARIANTS}
    for s in days[200:]:
        data_date = prev_session(s)
        if mutation == "change":
            future = {k: mutate_from(h, s) for k, h in history.items()}
        elif mutation == "halve":
            future = {k: mutate_from(h, s, halve) for k, h in history.items()}
        elif mutation == "truncate":
            future = {k: truncate_before(h, s) for k, h in history.items()}
        elif mutation == "spy_only_halve":
            future = {**history, REGIME_SYMBOL: mutate_from(history[REGIME_SYMBOL], s, halve)}
        else:
            future = {**history, REGIME_SYMBOL: truncate_before(history[REGIME_SYMBOL], s)}
        future_prepared = STRATEGY_A2.prepare(future)
        assert future_prepared.regime_on(data_date) is prepared.regime_on(data_date), s
        for a in (DESIGN_PARAMS, PERMISSIVE):
            for p in every(a):
                before = STRATEGY_A2.picks(history, members, data_date, p)
                assert STRATEGY_A2.picks(future, members, data_date, p) == before, (s, p.variant)
                assert STRATEGY_A2.picks_prepared(future_prepared, members, data_date, p) == before, (s, p.variant)
                assert STRATEGY_A2.picks_prepared(prepared, members, data_date, p) == before, (s, p.variant)
                nonempty[p.variant] += a is DESIGN_PARAMS and bool(before)
    assert all(n >= 2 for n in nonempty.values()), nonempty  # the setup fired for every variant: not vacuous


def test_the_spy_mutation_does_change_later_regime_and_picks():
    # Guards test_no_look_ahead: the same SPY mutation, read at data_date = S, turns the regime off
    # and empties V1..V3's picks, while V0 (which ignores SPY) is unchanged.
    history = lookahead_set()
    s = session_days(260)[229]
    members = frozenset(history) - {REGIME_SYMBOL}
    future = {**history, REGIME_SYMBOL: mutate_from(history[REGIME_SYMBOL], s, halve)}
    assert regime_on(history[REGIME_SYMBOL], s) is True
    assert regime_on(future[REGIME_SYMBOL], s) is False
    assert STRATEGY_A2.prepare(future).regime_on(s) is False
    for p in every():
        before = STRATEGY_A2.picks(history, members, s, p)
        after = STRATEGY_A2.picks(future, members, s, p)
        assert symbols(before) == ["DIP"], p.variant
        assert after == (before if p.variant == "control" else []), p.variant


def test_the_full_mutation_does_change_later_picks():
    # Guards test_no_look_ahead for the stocks' bars, as test_strategy_a does for v1.
    history = lookahead_set()
    s = session_days(260)[230]
    future = {k: mutate_from(h, s) for k, h in history.items()}
    members = frozenset(history) - {REGIME_SYMBOL}
    for p in every(PERMISSIVE):
        assert STRATEGY_A2.picks(future, members, s, p) != STRATEGY_A2.picks(history, members, s, p), p.variant
