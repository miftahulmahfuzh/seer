"""B walk-forward (plan phase 4; handover §6.1 purge, §6.3, §6.4, §6.5).

One seeded synthetic market, 2019-01-02..2021-06-30:

- ``S00``..``S19``: seeded random walks (4-dp prices, lognormal volumes, $30M+ a day). ``S19`` is
  a member only from 2020-06-01 (point-in-time membership).
- ``ZZZ``: liquid, closes alternating 1 and 3, so ATR > close/2 and every bracket is invalid
  (NaN rows in the table, never picked).
- ``ILQ``: about $4M a day, never a candidate. ``SPY``: a walk, never a member.

``IS`` = 2019-10-17 (its data date is the first with 200 bars). The folds are ``folds(IS, 2020,
END)``: 2020, and 2021 to 2021-06-30. Fold 2020 trains on roughly 1,000 purged rows and fold
2021 on roughly 6,000, both above the 400 that HistGradientBoosting's ``min_samples_leaf=200``
needs for a split.
"""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import numpy as np
import pytest
from simkit import D
from stratkit import hist, mutate_from

from seer_engine import dates
from seer_engine.backtest.b_walkforward import (
    B,
    B_LINEAR,
    DECILES,
    TOP_FEATURES,
    BWalkForward,
    CalibrationRow,
    FoldModel,
    calibration,
    candidate_table,
    gate_p6a,
    model_schedule,
    oos_predictions,
    passed_nights,
    probe_determinism,
    train_folds,
    training_mask,
    walk_forward_b,
)
from seer_engine.backtest.labels import label_orders
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.metrics import Metrics, checklist, gate_checks
from seer_engine.backtest.tuning import MAX_DRAWDOWN
from seer_engine.backtest.runner import ParamsSchedule, run_backtest
from seer_engine.backtest.walkforward import Fold, folds
from seer_engine.strategies.b import FEATURE_NAMES, STRATEGY_B, BParams, bracket, prepare_b
from seer_engine.strategies.b_model import RIDGE, TREE, fit, fit_ridge, importance, r2
from seer_engine.strategies.base import History

SESSIONS = dates.sessions(D("2019-01-02"), D("2021-06-30"))
IS = SESSIONS[200]  # 2019-10-17: data date SESSIONS[199] has exactly 200 bars
END = SESSIONS[-1]  # 2021-06-30
FIRST_YEAR = 2020
WALKS = tuple(f"S{k:02d}" for k in range(20))
LATE, LATE_JOIN = "S19", D("2020-06-01")
WIDE, THIN, SPY = "ZZZ", "ILQ", "SPY"


# --------------------------------------------------------------------------- the synthetic market


def _walk(symbol: str, k: int, *, first: float, volume: float) -> History:
    """A seeded random walk rounded to 4 dp, with gaps, wicks and lognormal volumes."""
    n = len(SESSIONS)
    rng = np.random.default_rng(6000 + k)
    ret = rng.normal(0.0004, 0.02, n)
    gap = rng.normal(0.0, 0.005, n)
    up = np.abs(rng.normal(0.0, 0.010, n))
    down = np.abs(rng.normal(0.0, 0.012, n))
    vol = rng.lognormal(0.0, 0.3, n)
    o, h, lo, c = [], [], [], []
    prev = first
    for i in range(n):
        op = round(prev * (1 + gap[i]), 4)
        cl = round(prev * math.exp(ret[i]), 4)
        o.append(op)
        c.append(cl)
        h.append(round(max(op, cl) * (1 + up[i]), 4))
        lo.append(round(min(op, cl) * (1 - down[i]), 4))
        prev = cl
    return hist(symbol, c, days=SESSIONS, opens=o, highs=h, lows=lo, volumes=[float(round(volume * v)) for v in vol])


def _wide() -> History:
    """Closes 1, 3, 1, 3, …; high = close + 0.5, low = close − 0.5; $100M a day. ATR ≈ 2.5 > close/2."""
    closes = [1.0 if i % 2 == 0 else 3.0 for i in range(len(SESSIONS))]
    return hist(WIDE, closes, days=SESSIONS, volume=50_000_000.0)


def base_history() -> dict[str, History]:
    out = {s: _walk(s, k, first=30.0 + 5.0 * k, volume=1_000_000.0) for k, s in enumerate(WALKS)}
    out[WIDE] = _wide()
    out[THIN] = _walk(THIN, 50, first=40.0, volume=100_000.0)
    out[SPY] = _walk(SPY, 99, first=300.0, volume=50_000_000.0)
    return out


def b_market(history: dict[str, History] | None = None) -> Market:
    intervals = tuple((s, D("2015-01-02"), None) for s in WALKS if s != LATE)
    intervals += ((LATE, LATE_JOIN, None), (WIDE, D("2015-01-02"), None), (THIN, D("2015-01-02"), None))
    return Market(
        history=dict(base_history() if history is None else history),
        membership=Membership(intervals),  # SPY is never a member
        fx=((D("2018-12-31"), Decimal("16000")),),
    )


@pytest.fixture(scope="module")
def world():
    market = b_market()
    prepared = prepare_b(market.history)
    fs = folds(IS, FIRST_YEAR, END)
    table = candidate_table(market, prepared, IS, END)
    return SimpleNamespace(
        market=market,
        prepared=prepared,
        folds=fs,
        table=table,
        tree=train_folds(table, fs, TREE),
        ridge=train_folds(table, fs, RIDGE),
    )


@pytest.fixture(scope="module")
def runs(world):
    return {
        B: walk_forward_b(world.market, world.prepared, world.folds, world.tree, B),
        B_LINEAR: walk_forward_b(world.market, world.prepared, world.folds, world.ridge, B_LINEAR),
    }


@pytest.fixture(scope="module")
def targeted(world):
    """Real fits whose top ``ret_1`` ranks predict > 0 on every date (non-empty picks)."""
    t = world.table
    y = t.X[:, 0] - 0.3
    return {TREE: fit(TREE, t.X, y), RIDGE: fit(RIDGE, t.X, y)}


def _constant_models(world, values: tuple[float, ...]) -> tuple[FoldModel, ...]:
    """One ridge FoldModel per fold that predicts ≈ ``values[k]`` for every row (y ≡ value)."""
    X = np.ascontiguousarray(world.table.X[:50])
    out = []
    for f, v in zip(world.folds, values):
        model = fit_ridge(X, np.full(50, v, dtype=np.float64))
        out.append(
            FoldModel(
                fold=f, model=model, rows=50, label_mean=v, label_sum=50 * v, pred_mean=v, r2=None,
                positive_share=1.0 if v > 0 else 0.0, importance=(0.0,) * len(FEATURE_NAMES),
            )
        )
    return tuple(out)


def _next_sessions(t) -> np.ndarray:
    nxt = {d: dates.next_session(d) for d in sorted({x.item() for x in t.data_dates})}
    return np.array([nxt[x.item()] for x in t.data_dates], dtype="datetime64[D]")


# --------------------------------------------------------------------------- constants


def test_constants():
    assert (B, B_LINEAR, DECILES, TOP_FEATURES) == ("B", "B-linear", 10, 5)
    assert IS == D("2019-10-17") and END == D("2021-06-30")


# --------------------------------------------------------------------------- the candidate table


def test_candidate_table_rows_are_each_dates_design(world):
    t = world.table
    n = len(t.symbols)
    assert t.X.shape == (n, len(FEATURE_NAMES)) and t.X.dtype == np.float64
    for arr in (t.data_dates, t.limit, t.tp, t.sl):
        assert arr.shape == (n,)
        assert not arr.flags.writeable
    assert t.data_dates.dtype == np.dtype("datetime64[D]")
    seen = 0
    invalid = 0
    for d in dates.sessions(dates.prev_session(IS), dates.prev_session(END)):
        design = world.prepared.design_on(world.market.membership.members_on(d), d)
        rows = np.flatnonzero(t.data_dates == np.datetime64(d, "D"))
        assert rows.size == len(design.symbols)
        if rows.size == 0:
            continue
        assert rows.tolist() == list(range(seen, seen + rows.size))  # ordered by (date, symbol)
        assert tuple(t.symbols[i] for i in rows.tolist()) == design.symbols
        assert t.X[rows].tobytes() == np.ascontiguousarray(design.X).tobytes()
        for i, s, c, a in zip(rows.tolist(), design.symbols, design.close.tolist(), design.atr.tolist()):
            pick = bracket(s, c, a)
            got = (t.limit[i], t.tp[i], t.sl[i])
            if pick is None:
                assert all(math.isnan(v) for v in got)
                invalid += 1
            else:
                assert got == (float(pick.limit_price), float(pick.tp_price), float(pick.sl_price))
        seen += rows.size
    assert seen == n > 0
    assert invalid > 0 and all(t.symbols[i] == WIDE for i in np.flatnonzero(np.isnan(t.limit)).tolist())
    assert WIDE in t.symbols and THIN not in t.symbols and SPY not in t.symbols
    assert t.data_dates[0] == np.datetime64(dates.prev_session(IS), "D")
    assert t.data_dates[-1] == np.datetime64(dates.prev_session(END), "D")
    late = t.data_dates[np.array([s == LATE for s in t.symbols])]
    assert late.size > 0 and late.min() >= np.datetime64(LATE_JOIN, "D")


def test_candidate_table_labels_are_label_orders_on_the_valid_rows(world):
    t = world.table
    lab = t.labels
    valid = np.flatnonzero(~np.isnan(t.limit))
    invalid = np.flatnonzero(np.isnan(t.limit))
    direct = label_orders(
        world.market.history, [t.symbols[i] for i in valid.tolist()], t.data_dates[valid],
        t.limit[valid], t.tp[valid], t.sl[valid], END,
    )
    n = len(t.symbols)
    for name in ("label", "fill", "exit"):
        got = getattr(lab, name)
        assert got.shape == (n,) and got.dtype == np.float64
        assert got[valid].tobytes() == np.asarray(getattr(direct, name), dtype=np.float64).tobytes()
        assert np.isnan(got[invalid]).all()
    assert lab.resolved.dtype == np.dtype("datetime64[D]")
    assert lab.resolved[valid].view(np.int64).tolist() == np.asarray(direct.resolved).view(np.int64).tolist()
    assert np.isnat(lab.resolved[invalid]).all()
    assert lab.reason.dtype == np.int8
    assert lab.reason[valid].tolist() == np.asarray(direct.reason).tolist()
    assert (lab.reason[invalid] == -1).all()
    assert (lab.reason[valid] >= 0).any() and (lab.reason[valid] == -1).any()  # some still open at END


def test_candidate_table_rejects_bad_arguments(world):
    with pytest.raises(TypeError):
        candidate_table("market", world.prepared, IS, END)
    with pytest.raises(TypeError):
        candidate_table(world.market, None, IS, END)
    with pytest.raises(TypeError):
        candidate_table(world.market, world.prepared, datetime(2019, 10, 17), END)
    with pytest.raises(ValueError):
        candidate_table(world.market, world.prepared, D("2019-10-19"), END)  # a Saturday
    with pytest.raises(ValueError):
        candidate_table(world.market, world.prepared, END, IS)


# --------------------------------------------------------------------------- the purge


def test_training_mask_keeps_valid_rows_resolved_by_tune_end(world):
    t = world.table
    first = np.datetime64(dates.prev_session(IS), "D")
    for f in world.folds:
        m = training_mask(t, f)
        cut = np.datetime64(f.tune_end, "D")
        assert m.dtype == np.bool_ and m.shape == (len(t.symbols),)
        expect = np.array(
            [
                (not math.isnan(t.limit[i]))
                and (not np.isnat(t.labels.resolved[i]))
                and bool(t.labels.resolved[i] <= cut)
                and bool(t.data_dates[i] >= first)
                for i in range(len(t.symbols))
            ]
        )
        assert np.array_equal(m, expect)
        assert int(m.sum()) >= 400  # enough rows for min_samples_leaf=200 to split
        assert (t.data_dates[m] < cut).all()  # an order placed on tune_end resolves after it
        on_cut = (t.data_dates == cut) & ~np.isnan(t.limit)
        assert on_cut.any() and not (m & on_cut).any()
    later = replace(world.folds[0], tune_start=SESSIONS[230])
    m2 = training_mask(t, later)
    assert (m2 <= training_mask(t, world.folds[0])).all()
    assert (t.data_dates[m2] >= np.datetime64(SESSIONS[229], "D")).all()
    with pytest.raises(TypeError):
        training_mask(t, "2020")
    with pytest.raises(TypeError):
        training_mask("table", world.folds[0])


@pytest.mark.parametrize("year", [2020, 2021])
def test_mutating_every_bar_after_tune_end_leaves_the_fold_unchanged(world, year):
    k = [f.year for f in world.folds].index(year)
    f = world.folds[k]
    mutated = b_market({s: mutate_from(h, f.trade_start) for s, h in world.market.history.items()})  # SPY too
    mt = candidate_table(mutated, prepare_b(mutated.history), IS, END)
    t = world.table
    cut = np.datetime64(f.tune_end, "D")
    n = int(np.count_nonzero(t.data_dates <= cut))
    assert int(np.count_nonzero(mt.data_dates <= cut)) == n
    assert mt.symbols[:n] == t.symbols[:n]
    assert mt.X[:n].tobytes() == t.X[:n].tobytes()
    for name in ("limit", "tp", "sl"):
        assert getattr(mt, name)[:n].tobytes() == getattr(t, name)[:n].tobytes()
    m0, m1 = training_mask(t, f), training_mask(mt, f)
    assert np.array_equal(m0[:n], m1[:n]) and not m0[n:].any() and not m1[n:].any()
    assert mt.X[m1].tobytes() == t.X[m0].tobytes()
    assert mt.labels.label[m1].tobytes() == t.labels.label[m0].tobytes()
    assert mt.labels.resolved[m1].tobytes() == t.labels.resolved[m0].tobytes()
    assert train_folds(mt, (f,), TREE) == (world.tree[k],)  # same rows, same labels, same digest
    assert mt.X[n:].tobytes() != t.X[n:].tobytes()  # the change is real after tune_end


# --------------------------------------------------------------------------- folds and fits


def test_the_folds_are_p3bs(world, runs):
    assert world.folds == folds(IS, FIRST_YEAR, END)
    assert [(f.year, f.tune_start, f.tune_end, f.trade_start, f.trade_end) for f in world.folds] == [
        (2020, IS, D("2019-12-31"), D("2020-01-02"), D("2020-12-31")),
        (2021, IS, D("2020-12-31"), D("2021-01-04"), END),
    ]
    for fms in (world.tree, world.ridge):
        assert tuple(fm.fold for fm in fms) == world.folds
    for w in runs.values():
        assert w.folds == world.folds and tuple(fm.fold for fm in w.fold_models) == world.folds


@pytest.mark.parametrize("kind", [TREE, RIDGE])
def test_train_folds_fits_each_fold_on_its_purged_rows(world, kind):
    fms = world.tree if kind == TREE else world.ridge
    assert len(fms) == len(world.folds)
    for f, fm in zip(world.folds, fms):
        m = training_mask(world.table, f)
        X, y = world.table.X[m], world.table.labels.label[m]
        model = fit(kind, X, y)
        pred = model.predict(X)
        rows = int(m.sum())
        assert fm == FoldModel(
            fold=f,
            model=model,
            rows=rows,
            label_mean=math.fsum(y.tolist()) / rows,
            label_sum=math.fsum(y.tolist()),
            pred_mean=math.fsum(pred.tolist()) / rows,
            r2=r2(y, pred),
            positive_share=int(np.count_nonzero(pred > 0.0)) / rows,
            importance=importance(model, X),
        )
        assert fm.model.kind == kind and fm.model.n_features == len(FEATURE_NAMES)
        assert len(fm.importance) == len(FEATURE_NAMES) and math.isclose(sum(fm.importance), 1.0)
        assert 0.0 <= fm.positive_share <= 1.0
    assert fms[0].rows < fms[1].rows  # anchored: the later fold sees more
    assert fms[0].model != fms[1].model


def test_train_folds_rejects_bad_kinds_and_folds_without_rows(world):
    with pytest.raises(ValueError):
        train_folds(world.table, world.folds, "forest")
    with pytest.raises(ValueError):
        train_folds(world.table, (), TREE)
    with pytest.raises(TypeError):
        train_folds("table", world.folds, TREE)
    no_brackets = replace(world.table, limit=np.full_like(world.table.limit, np.nan))
    with pytest.raises(ValueError):
        train_folds(no_brackets, world.folds, RIDGE)
    with pytest.raises(ValueError):
        probe_determinism(no_brackets, world.folds[-1])


def test_probe_determinism_is_true_on_synthetic_data(world):
    assert probe_determinism(world.table, world.folds[-1]) is True


# --------------------------------------------------------------------------- schedule and runs


def test_model_schedule_switches_at_each_trade_start(world):
    sched = model_schedule(world.folds, world.tree)
    p0, p1 = BParams(world.tree[0].model), BParams(world.tree[1].model)
    assert sched == ParamsSchedule(segments=((D("2020-01-02"), p0), (D("2021-01-04"), p1)))
    assert sched.at(D("2020-12-31")) == p0
    assert sched.at(D("2021-01-04")) == p1
    assert p0 != p1


def test_model_schedule_rejects_misaligned_fold_models(world):
    with pytest.raises(ValueError):
        model_schedule(world.folds, world.tree[:1])
    with pytest.raises(ValueError):
        model_schedule(world.folds, world.tree[::-1])
    with pytest.raises(TypeError):
        model_schedule(world.folds, (world.tree[0], "model"))


def test_an_order_open_across_31_december_keeps_the_bracket_it_was_placed_with(world):
    fms = _constant_models(world, (0.01, 0.02))  # two different models, both pick every valid candidate
    assert fms[0].model != fms[1].model
    w = walk_forward_b(world.market, world.prepared, world.folds, fms, B_LINEAR)
    assert w.run.params.segments == ((D("2020-01-02"), BParams(fms[0].model)), (D("2021-01-04"), BParams(fms[1].model)))
    t = world.table
    row = {(t.data_dates[i].item(), s): i for i, s in enumerate(t.symbols)}
    orders = w.run.closed + w.run.open_at_end
    assert orders
    for o in orders:
        i = row[(dates.prev_session(o.session_date), o.symbol)]
        assert (float(o.limit_price), float(o.tp_price), float(o.sl_price)) == (t.limit[i], t.tp[i], t.sl[i])
        assert o.symbol != WIDE  # invalid brackets are never picked
    across = [o for o in w.run.closed if o.fill_date <= D("2020-12-31") and o.exit_date >= D("2021-01-04")]
    assert across  # placed under fold 2020's model, closed under fold 2021's, bracket unchanged


def test_walk_forward_b_trades_every_fold_as_one_run(world, runs):
    for name, fms in ((B, world.tree), (B_LINEAR, world.ridge)):
        w = runs[name]
        assert isinstance(w, BWalkForward)
        assert (w.name, w.folds, w.fold_models) == (name, world.folds, fms)
        sched = model_schedule(world.folds, fms)
        assert w.run.params == sched
        assert w.run == run_backtest(world.market, STRATEGY_B, sched, D("2020-01-02"), END, prepared=world.prepared)
        assert w.run.strategy_id == "B"
        assert [s.date for s in w.run.snapshots] == [D("2019-12-31")] + dates.sessions(D("2020-01-02"), END)
        assert w.run.usd_idr == Decimal("16000")  # starting cash once, never reset at a year start


def test_walk_forward_b_rejects_bad_names_kinds_and_prepared(world):
    with pytest.raises(ValueError):
        walk_forward_b(world.market, world.prepared, world.folds, world.tree, "A2")
    with pytest.raises(TypeError):
        walk_forward_b(world.market, world.prepared, world.folds, world.tree, None)
    with pytest.raises(ValueError):
        walk_forward_b(world.market, world.prepared, world.folds, world.ridge, B)  # ridge models under B
    with pytest.raises(ValueError):
        walk_forward_b(world.market, world.prepared, world.folds, world.tree, B_LINEAR)
    with pytest.raises(TypeError):
        walk_forward_b(world.market, None, world.folds, world.tree, B)


# --------------------------------------------------------------------------- P4 identity and no look-ahead


@pytest.mark.parametrize("kind", [TREE, RIDGE])
def test_p4_identity_with_real_fitted_models(world, targeted, kind):
    trained = (world.tree if kind == TREE else world.ridge)[-1].model
    days = SESSIONS[199:-1:37]
    nonempty = 0
    for model in (targeted[kind], trained):
        p = BParams(model)
        for d in days:
            members = world.market.membership.members_on(d)
            cut = {s: h.upto(d) for s, h in world.market.history.items()}
            prepared_picks = STRATEGY_B.picks_prepared(world.prepared, members, d, p)
            assert prepared_picks == STRATEGY_B.picks(cut, members, d, p)
            if model is targeted[kind]:
                nonempty += bool(prepared_picks)
    assert nonempty == len(days)  # the identity is not vacuous


def test_bars_dated_on_or_after_the_session_never_change_its_picks(world, targeted):
    for session in (D("2020-06-15"), D("2021-01-04")):
        d = dates.prev_session(session)
        mutated = b_market({s: mutate_from(h, session) for s, h in world.market.history.items()})  # SPY too
        mp = prepare_b(mutated.history)
        members = world.market.membership.members_on(d)
        for model in (targeted[TREE], targeted[RIDGE], world.tree[-1].model, world.ridge[-1].model):
            p = BParams(model)
            base = STRATEGY_B.picks_prepared(world.prepared, members, d, p)
            assert STRATEGY_B.picks_prepared(mp, members, d, p) == base
            if model is targeted[TREE] or model is targeted[RIDGE]:
                assert base != []


# --------------------------------------------------------------------------- out-of-sample diagnostics


def test_oos_predictions_use_each_folds_model(world):
    t = world.table
    idx, pred = oos_predictions(t, world.folds, world.tree)
    assert idx.dtype == np.int64 and pred.dtype == np.float64 and idx.shape == pred.shape
    assert (np.diff(idx) > 0).all()
    session = _next_sessions(t)
    lo, hi = np.datetime64(world.folds[0].trade_start, "D"), np.datetime64(world.folds[-1].trade_end, "D")
    expected = np.flatnonzero(~np.isnan(t.limit) & (session >= lo) & (session <= hi))
    assert idx.tolist() == expected.tolist()
    assert t.data_dates[idx[0]] == np.datetime64(world.folds[0].tune_end, "D")
    for f, fm in zip(world.folds, world.tree):
        inside = (session[idx] >= np.datetime64(f.trade_start, "D")) & (session[idx] <= np.datetime64(f.trade_end, "D"))
        rows = idx[inside]
        assert rows.size > 0
        assert pred[inside].tobytes() == fm.model.predict(t.X[rows]).tobytes()
        for j in np.flatnonzero(inside)[:3].tolist():  # one row alone gives the same float
            assert fm.model.predict(t.X[idx[j] : idx[j] + 1])[0] == pred[j]
    in21 = session[idx] >= np.datetime64(world.folds[1].trade_start, "D")
    assert pred[in21].tobytes() != world.tree[0].model.predict(t.X[idx[in21]]).tobytes()  # not fold 2020's model


def test_calibration_hand_checked():
    pred = np.array([0.5, -0.125, 0.0625, 0.0625, 0.25, -0.25, 0.125, 0.75, 0.0, 0.375, -0.0625, 0.1875, 1.0])
    label = np.array(
        [0.03125, -0.0625, 0.0, 0.125, 0.015625, -0.03125, 0.0, 0.0625, np.nan, 0.046875, -0.015625, 0.0078125, np.nan]
    )
    # 11 resolved rows (8 and 12 are not), ordered by (pred, position):
    # 5, 1 | 10 | 2 | 3 | 6 | 11 | 4 | 9 | 0 | 7  — array_split gives the first decile the extra row,
    # and the tie at 0.0625 keeps position order (row 2 before row 3).
    assert calibration(pred, label) == (
        CalibrationRow(1, 2, -0.25, -0.125, -0.1875, -0.046875),
        CalibrationRow(2, 1, -0.0625, -0.0625, -0.0625, -0.015625),
        CalibrationRow(3, 1, 0.0625, 0.0625, 0.0625, 0.0),
        CalibrationRow(4, 1, 0.0625, 0.0625, 0.0625, 0.125),
        CalibrationRow(5, 1, 0.125, 0.125, 0.125, 0.0),
        CalibrationRow(6, 1, 0.1875, 0.1875, 0.1875, 0.0078125),
        CalibrationRow(7, 1, 0.25, 0.25, 0.25, 0.015625),
        CalibrationRow(8, 1, 0.375, 0.375, 0.375, 0.046875),
        CalibrationRow(9, 1, 0.5, 0.5, 0.5, 0.03125),
        CalibrationRow(10, 1, 0.75, 0.75, 0.75, 0.0625),
    )
    even = calibration(np.arange(100, dtype=np.float64)[::-1] / 128.0, np.arange(100, dtype=np.float64)[::-1] / 64.0)
    assert [r.rows for r in even] == [10] * 10
    assert (even[0].pred_min, even[0].pred_max, even[-1].pred_max) == (0.0, 9 / 128.0, 99 / 128.0)
    assert [r.label_mean for r in even] == [2.0 * r.pred_mean for r in even]


def test_calibration_rejects_bad_input():
    ok = np.arange(12, dtype=np.float64)
    with pytest.raises(ValueError):
        calibration(ok, ok[:11])
    with pytest.raises(ValueError):
        calibration(ok.reshape(3, 4), ok.reshape(3, 4))
    with pytest.raises(ValueError):
        calibration(ok, np.where(ok < 3, ok, np.nan))  # 3 resolved < DECILES
    with pytest.raises(ValueError):
        calibration(np.where(ok == 0, np.nan, ok), ok)
    with pytest.raises(TypeError):
        calibration(np.arange(12), ok)


def test_passed_nights_are_the_sessions_without_picks(world, runs):
    sessions = dates.sessions(world.folds[0].trade_start, world.folds[-1].trade_end)
    for name, fms in ((B, world.tree), (B_LINEAR, world.ridge)):
        sched = runs[name].run.params
        empty = 0
        for session in sessions:
            d = dates.prev_session(session)
            members = world.market.membership.members_on(d)
            if not STRATEGY_B.picks_prepared(world.prepared, members, d, sched.at(session)):
                empty += 1
        assert passed_nights(world.table, world.folds, fms) == (empty, len(sessions))


def test_passed_nights_when_every_prediction_is_negative_or_positive(world):
    n = len(dates.sessions(D("2020-01-02"), END))
    assert passed_nights(world.table, world.folds, _constant_models(world, (-0.01, -0.02))) == (n, n)
    assert passed_nights(world.table, world.folds, _constant_models(world, (0.01, 0.02))) == (0, n)


# --------------------------------------------------------------------------- the P6a gate


def M(ret, pf=1.5, dd=0.10, trades=120, months=105.0):
    return Metrics(total_return=ret, win_rate=0.55, profit_factor=pf, max_drawdown=dd, trades=trades, months=months)


SPY_TR = Metrics(total_return=0.75, win_rate=None, profit_factor=None, max_drawdown=0.20, trades=0, months=105.0)
GATE_START, GATE_END = D("2018-01-02"), D("2026-10-02")
SWITCHED = "Strategy B (as B-linear, by the pre-registered determinism switch)"
SUBJECTS = [(B, "Strategy B"), (B_LINEAR, SWITCHED)]


@pytest.mark.parametrize(("gated", "subject"), SUBJECTS)
def test_gate_p6a_pass_sentence(gated, subject):
    wf_m = M(0.80, pf=1.5, dd=0.12, trades=300)
    v = gate_p6a(wf_m, SPY_TR, GATE_START, GATE_END, gated)
    assert v.passed
    assert v.checks == tuple(gate_checks(wf_m, 0.75))
    assert v.sentence == (
        f"{subject} passes the P6a gate: walk-forward from 2018-01-02 to 2026-10-02 it returned "
        "+80.0% against +75.0% for total-return SPY, with profit factor 1.50 and max drawdown 12.0%."
    )


@pytest.mark.parametrize(("gated", "subject"), SUBJECTS)
def test_gate_p6a_fail_sentence_names_every_failed_check_and_blocks_p4(gated, subject):
    v = gate_p6a(M(-0.10, pf=0.9, dd=0.30), SPY_TR, GATE_START, GATE_END, gated)
    assert not v.passed
    assert v.sentence == (
        f"{subject} fails the P6a gate: walk-forward from 2018-01-02 to 2026-10-02 it returned "
        "−10.0% against +75.0% for total-return SPY, with profit factor 0.90 and max drawdown 30.0%, "
        "so it fails on beating total-return SPY, profit factor ≥ 1.3 and max drawdown ≤ 20%; "
        "Strategy B's one round has failed on this data, and P4 stays blocked."
    )


@pytest.mark.parametrize(
    ("wf_m", "name"),
    [
        (M(0.70, pf=1.5, dd=0.12), "beating total-return SPY"),
        (M(0.80, pf=1.29, dd=0.12), "profit factor ≥ 1.3"),
        (M(0.80, pf=1.5, dd=math.nextafter(MAX_DRAWDOWN, 1)), "max drawdown ≤ 20%"),
    ],
)
def test_gate_p6a_fails_on_each_condition_alone(wf_m, name):
    v = gate_p6a(wf_m, SPY_TR, GATE_START, GATE_END, B)
    assert not v.passed
    assert v.sentence.endswith(
        f", so it fails on {name}; Strategy B's one round has failed on this data, and P4 stays blocked."
    )


def test_gate_p6a_boundaries_and_bad_arguments():
    assert not gate_p6a(M(0.75, pf=1.5, dd=0.12), SPY_TR, GATE_START, GATE_END, B).passed  # equal is not beating
    assert gate_p6a(M(0.80, pf=1.3, dd=MAX_DRAWDOWN), SPY_TR, GATE_START, GATE_END, B).passed  # inclusive thresholds
    inf = gate_p6a(M(0.80, pf=math.inf, dd=0.10), SPY_TR, GATE_START, GATE_END, B)
    assert inf.passed and "profit factor ∞" in inf.sentence
    with pytest.raises(TypeError):
        gate_p6a(M(0.80), SPY_TR, "2018-01-02", GATE_END, B)
    with pytest.raises(TypeError):
        gate_p6a("metrics", SPY_TR, GATE_START, GATE_END, B)
    with pytest.raises(TypeError):
        gate_p6a(M(0.80), SPY_TR, GATE_START, GATE_END, None)
    with pytest.raises(ValueError):
        gate_p6a(M(0.80), SPY_TR, GATE_START, GATE_END, "A2")


# --------------------------------------------------------------------------- determinism and purity


def test_identical_calls_give_equal_results(world, runs):
    t = world.table
    t2 = candidate_table(world.market, prepare_b(world.market.history), IS, END)
    assert t2.symbols == t.symbols
    for name in ("data_dates", "X", "limit", "tp", "sl"):
        assert getattr(t2, name).tobytes() == getattr(t, name).tobytes()
    for name in ("label", "resolved", "reason", "fill", "exit"):
        assert getattr(t2.labels, name).tobytes() == getattr(t.labels, name).tobytes()
    assert train_folds(t2, world.folds, TREE) == world.tree
    assert train_folds(t2, world.folds, RIDGE) == world.ridge
    assert walk_forward_b(world.market, world.prepared, world.folds, world.tree, B) == runs[B]
    assert walk_forward_b(world.market, world.prepared, world.folds, world.ridge, B_LINEAR) == runs[B_LINEAR]
    for fms in (world.tree, world.ridge):
        i1, p1 = oos_predictions(t, world.folds, fms)
        i2, p2 = oos_predictions(t2, world.folds, fms)
        assert i1.tobytes() == i2.tobytes() and p1.tobytes() == p2.tobytes()
        assert calibration(p1, t.labels.label[i1]) == calibration(p2, t2.labels.label[i2])
        assert passed_nights(t, world.folds, fms) == passed_nights(t2, world.folds, fms)


def test_the_purity_glob_covers_the_module():
    from test_strategy_purity import _module_name, _pure_sources

    assert "seer_engine.backtest.b_walkforward" in {_module_name(p) for p in _pure_sources()}
