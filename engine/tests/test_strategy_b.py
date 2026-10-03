"""Strategy B's features, ranks, candidates and picks (P6a handover §3, §6.2, §6.3; plan D5–D8).

The model is a fake here (any per-row ``Predictor``): the real tree and ridge models are
phase 4's to test through the same ``STRATEGY_B``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pytest
from simkit import P
from stratkit import dip, drop_days, hist, mutate_from, sawtooth, session_days, truncate_before, uptrend

import seer_engine
from seer_engine import universe
from seer_engine.dates import prev_session
from seer_engine.sim import Pick
from seer_engine.strategies import (
    DESIGN_PARAMS,
    FEATURE_NAMES,
    STRATEGY_B,
    BParams,
    BPrepared,
    Design,
    FrozenModel,
    History,
    Predictor,
    Strategy,
    design_at,
    picks_from_design,
    prepare_b,
)
from seer_engine.strategies import a as strategy_a
from seer_engine.strategies import a2 as strategy_a2
from seer_engine.strategies import b
from seer_engine.strategies.b import (
    LOOKBACK,
    MIN_DOLLAR_VOLUME,
    RAW_COLUMNS,
    SPY_FEATURES,
    SPY_SYMBOL,
    STRATEGY_B_FROZEN,
    SYMBOL_FEATURES,
    bracket,
    rank01,
    spy_window_features,
    window_features,
)
from seer_engine.strategies.indicators import stdev_return_window


@dataclass(frozen=True)
class Linear:
    """A fake fitted model: ``bias + Σ_j X[:, j] * weights[j]``, row by row (an explicit column loop)."""

    weights: tuple[float, ...]
    bias: float = 0.0

    def predict(self, X: np.ndarray) -> np.ndarray:
        acc = np.full(X.shape[0], self.bias, dtype=np.float64)
        for j, w in enumerate(self.weights):
            acc = acc + X[:, j] * w
        return acc


def weights(**named: float) -> tuple[float, ...]:
    return tuple(float(named.get(name, 0.0)) for name in FEATURE_NAMES)


@dataclass(frozen=True)
class Fixed:
    """A fake model returning ``values`` as they are (for hand-built designs)."""

    values: tuple[float, ...]

    def predict(self, X: np.ndarray) -> np.ndarray:
        assert X.shape[0] == len(self.values)
        return np.array(self.values, dtype=np.float64)


@dataclass(frozen=True)
class Exploding:
    def predict(self, X: np.ndarray) -> np.ndarray:
        raise AssertionError("predict must not be called")


MODELS = {
    "momentum": BParams(Linear(weights(ret_5=1.0, ret_20=0.5, rsi_2=-0.4), bias=-0.6)),
    "reversion": BParams(Linear(weights(ret_1=-1.0, close_sma50=-0.3, range_pos=-0.2), bias=0.7)),
    "spy_gated": BParams(Linear(weights(ret_20=1.0, spy_ret_20=40.0), bias=-0.6)),
    "all_positive": BParams(Linear(weights(), bias=1.0)),
    "all_negative": BParams(Linear(weights(), bias=-1.0)),
}


def upto_all(history: dict[str, History], d: date) -> dict[str, History]:
    return {s: h.upto(d) for s, h in history.items()}


def symbols(picks: list[Pick]) -> list[str]:
    return [p.symbol for p in picks]


def same_design(x: Design, y: Design) -> bool:
    """Bit-for-bit equality of two designs."""
    return (
        x.data_date == y.data_date
        and x.symbols == y.symbols
        and x.X.shape == y.X.shape
        and x.X.tobytes() == y.X.tobytes()
        and x.close.tobytes() == y.close.tobytes()
        and x.atr.tobytes() == y.atr.tobytes()
    )


# ---- constants -----------------------------------------------------------------------------


def test_constants():
    assert SPY_SYMBOL == universe.BENCHMARK == strategy_a2.REGIME_SYMBOL == "SPY"
    assert MIN_DOLLAR_VOLUME == DESIGN_PARAMS.min_dollar_volume == 20_000_000.0
    assert LOOKBACK == strategy_a.LOOKBACK == 200
    assert b.RETURN_HORIZONS == (1, 5, 20, 60, 120)
    assert len(SYMBOL_FEATURES) == 15 and len(SPY_FEATURES) == 3
    assert FEATURE_NAMES == SYMBOL_FEATURES + SPY_FEATURES and len(FEATURE_NAMES) == 18
    assert len(set(FEATURE_NAMES)) == 18
    assert RAW_COLUMNS == SYMBOL_FEATURES + ("close", "atr", "dollar_volume")
    assert STRATEGY_B_FROZEN is None or isinstance(STRATEGY_B_FROZEN, FrozenModel)


def test_strategy_b_implements_the_protocol():
    assert isinstance(STRATEGY_B, Strategy)
    assert (STRATEGY_B.id, STRATEGY_B.lookback) == ("B", 200)
    assert isinstance(Linear(weights()), Predictor)


def test_importing_strategies_loads_neither_b_model_nor_sklearn():
    pkg = Path(seer_engine.__file__).resolve().parent
    env = dict(os.environ)
    env["PYTHONPATH"] = str(pkg.parent) + os.pathsep + env.get("PYTHONPATH", "")
    code = (
        "import sys\n"
        "import seer_engine.strategies, seer_engine.strategies.b\n"
        "print(','.join(m for m in ('sklearn', 'seer_engine.strategies.b_model') if m in sys.modules))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, check=True, timeout=120)
    assert out.stdout.strip() == ""


# ---- raw features, hand-computed -----------------------------------------------------------


def hand_window() -> History:
    """200 bars: closes 100..299 (high/low = close ± 0.5, open = close), except the last bar
    (open 300, high 301, low 298, close 299); volume 1e6, the last 5 bars 3e6."""
    closes = [100.0 + t for t in range(200)]
    opens = closes[:-1] + [300.0]
    highs = [c + 0.5 for c in closes[:-1]] + [301.0]
    lows = [c - 0.5 for c in closes[:-1]] + [298.0]
    volumes = [1e6] * 195 + [3e6] * 5
    return hist("HAND", closes, opens=opens, highs=highs, lows=lows, volumes=volumes)


def as_window(h: History) -> list[np.ndarray]:
    return [getattr(h, f)[-LOOKBACK:].reshape(1, LOOKBACK).copy() for f in ("open", "high", "low", "close", "volume")]


def test_window_features_hand_computed():
    h = hand_window()
    raw = window_features(*as_window(h))
    assert raw.shape == (1, 18) and raw.dtype == np.float64
    got = dict(zip(RAW_COLUMNS, raw[0].tolist(), strict=True))
    # returns over k bars: 299 / (299 - k) - 1
    for k in (1, 5, 20, 60, 120):
        assert got[f"ret_{k}"] == 299.0 / (299.0 - k) - 1.0, k
    # SMA(50) = mean(250..299) = 274.5; SMA(200) = mean(100..299) = 199.5 (exact sums)
    assert got["close_sma50"] == 299.0 / 274.5 - 1.0
    assert got["close_sma200"] == 299.0 / 199.5 - 1.0
    # strictly rising closes: no loss, so both Wilder RSIs are 100
    assert got["rsi_2"] == got["rsi_14"] == 100.0
    # TR = max(1, |c+0.5 - (c-1)|, |c-0.5 - (c-1)|) = 1.5 on every bar but the last; the last bar's
    # TR = max(301-298, |301-298|, |298-298|) = 3. Seed 1.5, the recursion keeps 1.5, then (1.5·13 + 3)/14.
    atr = (1.5 * 13.0 + 3.0) / 14.0
    assert got["atr"] == atr
    assert got["atr_pct"] == atr / 299.0
    # stdev of the last 20 one-bar returns (280/279 - 1 .. 299/298 - 1), population
    r = [(280.0 + i) / (279.0 + i) - 1.0 for i in range(20)]
    mean = sum(r) / 20
    var = sum((x - mean) ** 2 for x in r) / 20
    assert got["stdev_20"] == pytest.approx(var**0.5, rel=1e-12)
    # dollar volume: (1e6·(280+…+294) + 3e6·(295+…+299)) / 20 = (4.305e9 + 4.455e9) / 20
    assert got["dollar_volume_20"] == got["dollar_volume"] == 4.38e8
    # mean volume 5 = 3e6; mean volume 20 = (15·1e6 + 5·3e6) / 20 = 1.5e6
    assert got["volume_5_20"] == 2.0
    assert got["gap"] == 300.0 / 298.0 - 1.0
    assert got["range_pos"] == 1.0 / 3.0
    assert got["close"] == 299.0


def test_window_features_read_only_the_last_lookback_bars():
    h = hand_window()
    longer = hist(
        "HAND",
        [5.0] * 30 + h.close.tolist(),
        opens=[5.0] * 30 + h.open.tolist(),
        highs=[9.0] * 30 + h.high.tolist(),
        lows=[1.0] * 30 + h.low.tolist(),
        volumes=[1.0] * 30 + h.volume.tolist(),
    )
    assert window_features(*as_window(longer)).tobytes() == window_features(*as_window(h)).tobytes()


def test_range_pos_is_one_half_on_a_flat_bar_and_spans_zero_to_one():
    o, hi, lo, c, v = as_window(hand_window())
    for last_close, last_high, last_low, expected in ((299.0, 299.0, 299.0, 0.5), (298.0, 301.0, 298.0, 0.0), (301.0, 301.0, 298.0, 1.0)):
        cc, hh, ll = c.copy(), hi.copy(), lo.copy()
        cc[0, -1], hh[0, -1], ll[0, -1] = last_close, last_high, last_low
        assert window_features(o, hh, ll, cc, v)[0, RAW_COLUMNS.index("range_pos")] == expected


def test_spy_window_features_hand_computed():
    c = np.array([[200.0 + t for t in range(200)]])
    assert spy_window_features(c).tolist() == [[399.0 / 394.0 - 1.0, 399.0 / 379.0 - 1.0, 399.0 / 299.5 - 1.0]]


def test_window_functions_reject_bad_shapes():
    good = np.ones((2, LOOKBACK))
    with pytest.raises(ValueError, match="2-D"):
        window_features(good, good, good, np.ones((2, LOOKBACK - 1)), good)
    with pytest.raises(ValueError, match="2-D"):
        window_features(good, good, good, good, np.ones((2, LOOKBACK), dtype=np.int64))
    with pytest.raises(ValueError, match="2-D"):
        spy_window_features(np.ones(LOOKBACK))


def test_window_features_rows_are_independent_bit_for_bit():
    rng = np.random.default_rng(5)
    c = np.round(100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.02, (9, LOOKBACK)), axis=1)), 4)
    o = np.round(c * (1.0 + rng.uniform(-0.01, 0.01, c.shape)), 4)
    h = np.round(np.maximum(o, c) * (1.0 + rng.uniform(0.0, 0.02, c.shape)), 4)
    lo = np.round(np.minimum(o, c) * (1.0 - rng.uniform(0.0, 0.02, c.shape)), 4)
    v = np.round(rng.uniform(1e5, 5e7, c.shape))
    together = window_features(o, h, lo, c, v)
    for i in range(9):
        alone = window_features(*(x[i : i + 1].copy() for x in (o, h, lo, c, v)))
        assert alone.tobytes() == together[i : i + 1].tobytes(), i
    assert together[:, RAW_COLUMNS.index("stdev_20")].tobytes() == stdev_return_window(c, 20).tobytes()


# ---- rank01 --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("x", "expected"),
    [
        ([3.0, 1.0, 2.0], [1.0, 0.0, 0.5]),
        ([2.0, 1.0, 3.0, 2.0], [0.5, 0.0, 1.0, 0.5]),  # ranks 2.5, 1, 4, 2.5 -> (r - 1) / 3
        ([1.0, 2.0, 2.0, 2.0, 5.0], [0.0, 0.5, 0.5, 0.5, 1.0]),  # ranks 1, 3, 3, 3, 5
        ([7.0, 7.0, 7.0], [0.5, 0.5, 0.5]),
        ([4.0], [0.5]),
        ([], []),
        ([0.0, -0.0, 1.0], [0.25, 0.25, 1.0]),  # signed zeros are equal, so tied
    ],
    ids=["distinct", "pair_tie", "triple_tie", "all_equal", "one", "none", "signed_zero"],
)
def test_rank01_hand_computed(x, expected):
    out = rank01(np.array(x, dtype=np.float64))
    assert out.dtype == np.float64 and out.tolist() == expected


def test_rank01_is_order_independent():
    rng = np.random.default_rng(9)
    x = rng.integers(0, 12, 60).astype(np.float64)  # many ties
    base = rank01(x)
    for _ in range(5):
        perm = rng.permutation(60)
        assert rank01(x[perm]).tobytes() == base[perm].tobytes()
    assert ((base >= 0.0) & (base <= 1.0)).all()


def test_rank01_rejects_bad_input():
    for bad in (np.array([1.0, np.nan]), np.array([np.inf, 1.0]), np.array([1, 2]), np.ones((2, 2)), [1.0, 2.0]):
        with pytest.raises(ValueError):
            rank01(bad)


# ---- the contract set ------------------------------------------------------------------------


def spy_closes(n: int) -> list[float]:
    """Rise 0.2/day for 250 bars, fall 1.5/day for 25, then rise 2.0/day."""
    out: list[float] = []
    for t in range(n):
        if t < 250:
            out.append(100.0 + 0.2 * t)
        elif t < 275:
            out.append(out[-1] - 1.5)
        else:
            out.append(out[-1] + 2.0)
    return out


def contract_set() -> tuple[list[date], dict[str, History]]:
    days = session_days(320)
    return days, {
        "SAW": hist("SAW", sawtooth(320), days=days),
        "TWIN": hist("TWIN", sawtooth(320), days=days),  # every raw feature ties with SAW's
        "DIP": hist("DIP", dip(dip(dip(uptrend(320), 229), 260), 290, drop=2.0), days=days),
        "LATE": hist("LATE", sawtooth(260, first=40.0, up=0.9, down=0.5), days=days[60:], volume=2e6),
        "GAPPY": drop_days(hist("GAPPY", sawtooth(320, first=70.0), days=days), days[100:105] + [days[250]]),
        "GONE": hist("GONE", sawtooth(270, first=90.0), days=days[:270]),
        "THIN": hist("THIN", dip(uptrend(320), 229), days=days, volume=1000.0),
        "FALL": hist("FALL", uptrend(320, first=150.0, step=-0.2), days=days, spread=1.0, volume=3e6),
        SPY_SYMBOL: drop_days(hist(SPY_SYMBOL, spy_closes(320), days=days, volume=1e8), [days[240]]),
    }


def contract_members(days: list[date], d: date, *, spy: bool) -> frozenset[str]:
    out = {"SAW", "TWIN", "DIP", "LATE", "GAPPY", "GONE", "THIN", "FALL"}
    if d < days[280]:
        out.discard("LATE")
    if days[230] <= d < days[260]:
        out.discard("SAW")
    if spy:
        out.add(SPY_SYMBOL)
    return frozenset(out)


def test_prepare_raw_rows_equal_single_window_features():
    days, history = contract_set()
    prepared = prepare_b(history)
    assert isinstance(prepared, BPrepared)
    assert prepared.symbols == tuple(sorted(s for s in history if s != SPY_SYMBOL))
    assert prepared.raw.shape == (prepared.dates.shape[0], 18) and not prepared.raw.flags.writeable
    keys = list(zip(prepared.dates.tolist(), prepared.sym.tolist(), strict=True))
    assert keys == sorted(keys)  # ordered by (date, symbol)
    for k in range(prepared.dates.shape[0]):
        h = history[prepared.symbols[int(prepared.sym[k])]]
        i = h.index_of(prepared.dates[k].item())
        assert i is not None and i + 1 >= LOOKBACK
        alone = window_features(*(getattr(h, f)[None, i + 1 - LOOKBACK : i + 1].copy() for f in ("open", "high", "low", "close", "volume")))
        assert alone[0].tobytes() == prepared.raw[k].tobytes(), k
    spy = history[SPY_SYMBOL]
    assert prepared.spy_dates.tolist() == spy.dates[LOOKBACK - 1 :].tolist()
    for k, d in enumerate(prepared.spy_dates.tolist()):
        i = spy.index_of(d)
        assert spy_window_features(spy.close[None, i + 1 - LOOKBACK : i + 1].copy())[0].tobytes() == prepared.spy[k].tobytes()


def test_design_on_equals_design_at_bit_for_bit_on_every_date():
    days, history = contract_set()
    prepared = prepare_b(history)
    sizes = []
    for d in days[190:]:
        members = contract_members(days, d, spy=d >= days[300])
        expected = design_at(upto_all(history, d), members, d)
        assert same_design(prepared.design_on(members, d), expected), d
        assert same_design(design_at(history, members, d), expected), d  # later bars ignored
        assert same_design(prepare_b(upto_all(history, d)).design_on(members, d), expected), d
        assert SPY_SYMBOL not in expected.symbols
        assert not expected.X.flags.writeable
        sizes.append(len(expected))
    assert max(sizes) >= 5 and 0 in sizes  # SPY's missing day 240 empties that date


def test_design_ranks_and_spy_columns_hand_checked():
    days, history = contract_set()
    d = days[300]
    design = design_at(history, {"SAW", "TWIN", "FALL", "THIN"}, d)
    assert design.symbols == ("FALL", "SAW", "TWIN")  # THIN fails the liquidity floor
    raw = window_features(*(np.stack([getattr(history[s], f)[days.index(d) + 1 - LOOKBACK : days.index(d) + 1] for s in design.symbols]) for f in ("open", "high", "low", "close", "volume")))
    for j in range(15):
        col = raw[:, j]
        # SAW and TWIN tie on every raw value: both get the mean rank; FALL is below or above both
        assert design.X[1, j] == design.X[2, j] == (0.75 if col[0] < col[1] else 0.25 if col[0] > col[1] else 0.5), SYMBOL_FEATURES[j]
        assert design.X[0, j] == (0.0 if col[0] < col[1] else 1.0 if col[0] > col[1] else 0.5), SYMBOL_FEATURES[j]
    spy = history[SPY_SYMBOL]
    i = spy.index_of(d)
    spy_row = spy_window_features(spy.close[None, i + 1 - LOOKBACK : i + 1].copy())[0]
    assert (design.X[:, 15:] == spy_row).all()
    assert design.close.tolist() == raw[:, RAW_COLUMNS.index("close")].tolist()
    assert design.atr.tolist() == raw[:, RAW_COLUMNS.index("atr")].tolist()


def test_ranks_use_the_members_on_d_only():
    days, history = contract_set()
    d = days[300]
    prepared = prepare_b(history)
    three = prepared.design_on({"SAW", "DIP", "FALL"}, d)
    two = prepared.design_on({"SAW", "DIP"}, d)
    assert two.symbols == ("DIP", "SAW")
    assert sorted(two.X[:, 0].tolist()) == [0.0, 1.0]  # two candidates: ranks 0 and 1
    assert three.X[:, :15].tobytes() != two.X[:, :15].tobytes()
    # a non-member's bars never touch the members' ranks
    changed = {**history, "FALL": mutate_from(history["FALL"], days[0], lambda x: x * 0.25 + 1.0)}
    assert same_design(prepare_b(changed).design_on({"SAW", "DIP"}, d), two)
    assert same_design(design_at(changed, {"SAW", "DIP"}, d), two)


@pytest.mark.parametrize(("volume", "kept"), [(200_000.0, False), (200_001.0, True)])
def test_liquidity_floor_is_strict(volume, kept):
    # close 100 every bar: 20-day mean dollar volume = 100 × volume; 2e7 exactly is NOT above the floor
    days = session_days(200)
    history = {
        "AAA": hist("AAA", [100.0] * 200, days=days, volume=volume),
        "BBB": hist("BBB", uptrend(200), days=days, volume=1e6),
        SPY_SYMBOL: hist(SPY_SYMBOL, uptrend(200, first=300.0), days=days),
    }
    for design in (design_at(history, {"AAA", "BBB"}, days[-1]), prepare_b(history).design_on({"AAA", "BBB"}, days[-1])):
        assert design.symbols == (("AAA", "BBB") if kept else ("BBB",))


def test_a_non_finite_raw_feature_excludes_the_candidate():
    # ZERO's close 120 bars before d is 0.0, so ret_120 = c / 0 - 1 = inf: not a candidate on d.
    days = session_days(201)
    closes = uptrend(201)
    closes[200 - 120] = 0.0
    history = {
        "ZERO": hist("ZERO", closes, days=days),
        "OK": hist("OK", uptrend(201), days=days),
        SPY_SYMBOL: hist(SPY_SYMBOL, uptrend(201, first=300.0), days=days),
    }
    d = days[200]
    assert window_features(*as_window(history["ZERO"]))[0, 4] == np.inf
    for design in (design_at(history, {"ZERO", "OK"}, d), prepare_b(history).design_on({"ZERO", "OK"}, d)):
        assert design.symbols == ("OK",)


# ---- SPY: features through d only, and no candidates without them --------------------------


def test_spy_features_read_spy_bars_through_d_only():
    days, history = contract_set()
    d = days[260]
    members = contract_members(days, d, spy=False)
    base = design_at(history, members, d)
    assert len(base) > 0
    spy = history[SPY_SYMBOL]
    i = spy.index_of(d)
    assert base.X[0, 15:].tolist() == spy_window_features(spy.close[None, i + 1 - LOOKBACK : i + 1].copy())[0].tolist()
    later = days[days.index(d) + 1]
    for spy_future in (mutate_from(spy, later, lambda x: x * 0.5), truncate_before(spy, later)):
        future = {**history, SPY_SYMBOL: spy_future}
        assert same_design(design_at(future, members, d), base)
        assert same_design(prepare_b(future).design_on(members, d), base)


def test_no_candidates_when_spy_is_missing_short_or_has_no_bar_on_d():
    days, history = contract_set()
    d = days[260]
    members = contract_members(days, d, spy=False)
    assert len(design_at(history, members, d)) > 0  # guard
    spy = history[SPY_SYMBOL]
    cases = {
        "missing": {s: h for s, h in history.items() if s != SPY_SYMBOL},
        "short": {**history, SPY_SYMBOL: hist(SPY_SYMBOL, uptrend(199), days=days[62:261])},  # 199 bars through d
        "no bar on d": {**history, SPY_SYMBOL: drop_days(spy, [d])},
    }
    for name, h in cases.items():
        for design in (design_at(h, members, d), prepare_b(h).design_on(members, d)):
            assert len(design) == 0 and design.X.shape == (0, 18), name
        for model in MODELS.values():
            assert STRATEGY_B.picks(h, members, d, model) == [], name
    exactly = {**history, SPY_SYMBOL: hist(SPY_SYMBOL, uptrend(200), days=days[61:261])}  # 200 bars: defined
    assert same_design(design_at(exactly, members, d), prepare_b(exactly).design_on(members, d))
    assert len(design_at(exactly, members, d)) > 0


# ---- bracket and picks_from_design -----------------------------------------------------------


def test_bracket_is_strategy_a_design_bracket():
    # last 100, ATR 2: limit 100 - 1 = 99, tp 99 + 2 = 101, sl 99 - 3 = 96
    assert bracket("AAA", 100.0, 2.0) == Pick("AAA", P("100"), P("99"), P("101"), P("96"))
    # 4-dp rounding, half-up: ATR 0.33333 -> to_decimal 0.3333; limit q(10 - 0.16665) = 9.8334,
    # tp q(9.8334 + 0.3333) = 10.1667, sl q(9.8334 - 0.49995) = q(9.33345) = 9.3335
    assert bracket("BBB", 10.0, 0.33333) == Pick("BBB", P("10"), P("9.8334"), P("10.1667"), P("9.3335"))
    assert bracket("AAA", 100.0, 0.0) is None  # tp == limit
    assert bracket("AAA", 1.0, 1.0) is None  # sl <= 0
    assert bracket("AAA", 0.00001, 0.000001) is None  # last rounds to 0
    assert bracket("AAA", float("nan"), 1.0) is None
    assert bracket("AAA", 100.0, float("inf")) is None


def hand_design(close: list[float], atr: list[float], names: tuple[str, ...]) -> Design:
    m = len(names)
    return Design(date(2020, 1, 2), names, np.zeros((m, 18)), np.array(close), np.array(atr))


def test_picks_keep_positive_predictions_only_ordered_with_symbol_ties():
    design = hand_design([100.0] * 6, [2.0] * 6, ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF"))
    preds = (0.5, 0.0, -0.1, 0.5, 1e-12, float("nan"))  # 0.0 is not > 0 (strict); NaN never qualifies
    got = picks_from_design(design, BParams(Fixed(preds)))
    assert symbols(got) == ["AAA", "DDD", "EEE"]  # 0.5 (AAA before DDD by symbol), then 1e-12
    assert got[0] == bracket("AAA", 100.0, 2.0)


def test_picks_drop_invalid_brackets_after_ranking():
    design = hand_design([100.0, 100.0, 50.0], [2.0, 0.0, 1.0], ("AAA", "BAD", "CCC"))
    got = picks_from_design(design, BParams(Fixed((0.1, 0.9, 0.2))))
    assert symbols(got) == ["CCC", "AAA"]  # BAD ranked first, then dropped (ATR 0: tp == limit)


def test_an_empty_design_never_calls_the_model():
    empty = hand_design([], [], ())
    assert picks_from_design(empty, BParams(Exploding())) == []
    days, history = contract_set()
    d = days[240]  # SPY has no bar: no candidates
    assert STRATEGY_B.picks(history, contract_members(days, d, spy=False), d, BParams(Exploding())) == []
    assert STRATEGY_B.picks_prepared(prepare_b(history), contract_members(days, d, spy=False), d, BParams(Exploding())) == []


@dataclass(frozen=True)
class Bad:
    out: object

    def predict(self, X: np.ndarray) -> object:
        return self.out


def test_picks_reject_bad_predictions_and_types():
    design = hand_design([100.0, 100.0], [2.0, 2.0], ("AAA", "BBB"))
    for out in (np.ones(3), np.ones((2, 1)), np.ones(2, dtype=np.float32), [1.0, 1.0]):
        with pytest.raises(ValueError):
            picks_from_design(design, BParams(Bad(out)))
    with pytest.raises(TypeError):
        picks_from_design(design, Linear(weights()))  # a model is not BParams
    with pytest.raises(TypeError):
        picks_from_design("design", MODELS["all_positive"])


def test_design_validates_its_shapes():
    with pytest.raises(ValueError):
        Design(date(2020, 1, 2), ("AAA",), np.zeros((1, 17)), np.zeros(1), np.zeros(1))
    with pytest.raises(ValueError):
        Design(date(2020, 1, 2), ("AAA",), np.zeros((1, 18)), np.zeros(2), np.zeros(1))
    with pytest.raises(TypeError):
        Design(date(2020, 1, 2), ["AAA"], np.zeros((1, 18)), np.zeros(1), np.zeros(1))
    with pytest.raises(TypeError):
        Design(datetime(2020, 1, 2), (), np.zeros((0, 18)), np.zeros(0), np.zeros(0))


def test_bparams_equality_hash_and_validation():
    a = BParams(Linear(weights(ret_1=1.0), bias=0.5))
    assert a == BParams(Linear(weights(ret_1=1.0), bias=0.5))
    assert hash(a) == hash(BParams(Linear(weights(ret_1=1.0), bias=0.5)))
    assert a != BParams(Linear(weights(ret_1=1.0), bias=0.25))
    assert len(set(MODELS.values())) == len(MODELS)
    for bad in (None, 1.0, "model", object()):
        with pytest.raises(TypeError):
            BParams(bad)


def test_wrong_param_prepared_or_date_types_raise():
    days, history = contract_set()
    d = days[260]
    members = contract_members(days, d, spy=False)
    prepared = prepare_b(history)
    p = MODELS["all_positive"]
    with pytest.raises(TypeError):
        STRATEGY_B.picks(history, members, d, DESIGN_PARAMS)
    with pytest.raises(TypeError):
        STRATEGY_B.picks(history, members, d, Linear(weights()))
    with pytest.raises(TypeError):
        STRATEGY_B.picks_prepared(prepared, members, d, None)
    with pytest.raises(TypeError):
        STRATEGY_B.picks_prepared(strategy_a.STRATEGY_A.prepare(history), members, d, p)
    with pytest.raises(TypeError):
        STRATEGY_B.picks(history, members, datetime(2020, 3, 2), p)
    with pytest.raises(TypeError):
        prepared.design_on(members, "2020-03-02")
    with pytest.raises(TypeError):
        design_at(history, members, datetime(2020, 3, 2))


# ---- the contract: picks_prepared == picks on every date, for every model -------------------


@pytest.mark.parametrize("name", list(MODELS))
def test_picks_prepared_equals_picks_on_every_date(name):
    params = MODELS[name]
    days, history = contract_set()
    prepared = STRATEGY_B.prepare(history)
    nonempty = 0
    for d in days[190:]:
        visible = upto_all(history, d)
        members = contract_members(days, d, spy=d >= days[300])  # SPY listed as a member near the end
        expected = STRATEGY_B.picks(visible, members, d, params)
        assert STRATEGY_B.picks_prepared(prepared, members, d, params) == expected, d
        assert STRATEGY_B.picks(history, members, d, params) == expected, d  # later bars ignored
        assert expected == picks_from_design(design_at(visible, members, d), params), d
        assert SPY_SYMBOL not in symbols(expected), d
        nonempty += bool(expected)
    if name == "all_negative":
        assert nonempty == 0
    else:
        assert nonempty > 0


def test_the_models_disagree_so_the_contract_test_is_not_vacuous():
    days, history = contract_set()
    prepared = prepare_b(history)
    differ = {"momentum": 0, "reversion": 0, "spy_gated": 0}
    for d in days[200:]:
        members = contract_members(days, d, spy=False)
        everyone = STRATEGY_B.picks_prepared(prepared, members, d, MODELS["all_positive"])
        for name in differ:
            got = STRATEGY_B.picks_prepared(prepared, members, d, MODELS[name])
            differ[name] += bool(everyone) and got != everyone
    assert all(n > 0 for n in differ.values()), differ


# ---- no look-ahead, SPY's bars included ------------------------------------------------------


def lookahead_set() -> tuple[list[date], dict[str, History]]:
    days = session_days(260)
    return days, {
        "DIP": hist("DIP", dip(uptrend(260), 229), days=days),
        "DIP2": hist("DIP2", dip(dip(uptrend(260, first=80.0, step=0.15), 240), 250, days=3), days=days),
        "SAW": hist("SAW", sawtooth(260), days=days),
        "FALL": hist("FALL", uptrend(260, first=150.0, step=-0.2), days=days, spread=1.0, volume=3e6),
        SPY_SYMBOL: hist(SPY_SYMBOL, spy_closes(260), days=days, volume=1e8),
    }


def halve(x: np.ndarray) -> np.ndarray:
    return x * 0.5


@pytest.mark.parametrize("mutation", ["change", "truncate", "spy_only_halve", "spy_only_truncate"])
def test_no_look_ahead(mutation):
    """Changing (or deleting) every bar dated on or after S, SPY's included, leaves S's picks unchanged."""
    days, history = lookahead_set()
    prepared = prepare_b(history)
    members = frozenset(history)  # SPY listed too: it is never a candidate
    nonempty = 0
    for s in days[200:]:
        data_date = prev_session(s)
        if mutation == "change":
            future = {k: mutate_from(h, s) for k, h in history.items()}
        elif mutation == "truncate":
            future = {k: truncate_before(h, s) for k, h in history.items()}
        elif mutation == "spy_only_halve":
            future = {**history, SPY_SYMBOL: mutate_from(history[SPY_SYMBOL], s, halve)}
        else:
            future = {**history, SPY_SYMBOL: truncate_before(history[SPY_SYMBOL], s)}
        future_prepared = prepare_b(future)
        assert same_design(future_prepared.design_on(members, data_date), prepared.design_on(members, data_date)), s
        for name, params in MODELS.items():
            before = STRATEGY_B.picks(history, members, data_date, params)
            assert STRATEGY_B.picks(future, members, data_date, params) == before, (s, name)
            assert STRATEGY_B.picks_prepared(future_prepared, members, data_date, params) == before, (s, name)
            assert STRATEGY_B.picks_prepared(prepared, members, data_date, params) == before, (s, name)
            nonempty += bool(before)
    assert nonempty > 0


def test_the_spy_mutation_does_change_later_designs_and_picks():
    # Guards test_no_look_ahead: the same SPY mutation, read at data_date = S, changes the SPY
    # columns, and the SPY-gated model's picks with them.
    days, history = lookahead_set()
    members = frozenset(history)
    changed = 0
    for s in days[200:]:
        future = {**history, SPY_SYMBOL: mutate_from(history[SPY_SYMBOL], s, halve)}
        before = design_at(history, members, s)
        after = design_at(future, members, s)
        assert before.symbols == after.symbols and len(before) > 0
        assert before.X[:, :15].tobytes() == after.X[:, :15].tobytes()
        assert before.X[:, 15:].tobytes() != after.X[:, 15:].tobytes()
        p = MODELS["spy_gated"]
        changed += STRATEGY_B.picks(future, members, s, p) != STRATEGY_B.picks(history, members, s, p)
    assert changed > 0


# ---- SPY is never a pick; empty and short histories ------------------------------------------


def test_spy_is_never_a_pick_even_as_a_liquid_member():
    days, history = lookahead_set()
    d = days[230]
    members = frozenset(history)
    prepared = prepare_b(history)
    assert SPY_SYMBOL not in prepared.symbols
    picks = STRATEGY_B.picks(history, members, d, MODELS["all_positive"])
    assert symbols(picks) == sorted(s for s in history if s != SPY_SYMBOL)  # every candidate, by symbol
    assert STRATEGY_B.picks_prepared(prepared, members, d, MODELS["all_positive"]) == picks
    assert STRATEGY_B.picks(history, {SPY_SYMBOL}, d, MODELS["all_positive"]) == []


def test_prepare_on_empty_or_short_history():
    d = date(2019, 6, 3)
    short = {"X": hist("X", sawtooth(150)), SPY_SYMBOL: hist(SPY_SYMBOL, uptrend(150))}
    for history in ({}, short):
        prepared = prepare_b(history)
        assert prepared.raw.shape == (0, 18) and prepared.spy.shape == (0, 3)
        assert len(prepared.design_on({"X"}, d)) == 0
        assert STRATEGY_B.picks_prepared(prepared, {"X"}, d, MODELS["all_positive"]) == []
        assert STRATEGY_B.picks(history, {"X"}, d, MODELS["all_positive"]) == []
