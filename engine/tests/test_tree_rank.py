"""The tree ranker (lab/tree_rank.py; measure-then-learn phase 6, R5).

Hand-checked calendar and labels; features equal to the lab code they import; point-in-time
training membership; the market path equal to the from-scratch path built on data cut at d; no
look-ahead in bars, dividends or membership; bit-identical refits; the feature-set switch; the
history-only contract (nothing targeted, as test_lab_methods requires of a market-aware
allocator); a smoke run through the dev runner; and the module's purity (test_strategy_purity
does not glob lab/).
"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from allocatorkit import assert_no_lookahead, assert_p4_identity, assert_valid_targets, everyone
from labkit import SPY_EX_DATE, smoke_market
from stratkit import hist, mutate_from, truncate_before
from test_strategy_purity import (
    FORBIDDEN_ATTRS,
    FORBIDDEN_CALLS,
    FORBIDDEN_IMPORT_ROOTS,
    FORBIDDEN_MODULES,
    _fresh_python,
)

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend
from seer_engine.backtest.dev import DEV_END, Candidate, run_candidate
from seer_engine.backtest.market import DividendCalendar, Market, Membership
from seer_engine.lab import runner, tree_rank
from seer_engine.lab.methods.m0007_residual_momentum import build_grid, residual_scores
from seer_engine.lab.methods.m0015_52week_high import nearness
from seer_engine.lab.methods.m0070_dividend_raise_drift import live_event
from seer_engine.lab.tree_rank import (
    FEATURE_LOOKBACK,
    PRICE_FEATURES,
    RAISE_EVENT,
    RESID,
    SCREEN,
    TREE_RANK,
    TREE_RANK_FUND,
    TreeInputs,
    TreeRankParams,
    TreeRankPrepared,
    anchor_for,
    fundamental_features,
    label_end,
    month_ends,
    targets_with_inputs,
    year_end,
)
from seer_engine.sim.book import equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import Allocator, MarketAware
from seer_engine.strategies.f_factor import factor_rows

# ---- the synthetic market ---------------------------------------------------------------------

START = date(2009, 1, 2)
END = date(2014, 12, 31)
DAYS = dates.sessions(START, END)  # 1510 sessions
STOCKS: tuple[str, ...] = tuple(f"S{k:02d}" for k in range(10))
LEAVER, LEAVES = "S08", date(2012, 6, 1)  # leaves the index (interval end, exclusive)
JOINER, JOINS = "S09", date(2011, 3, 1)  # joins the index late


def walk(seed: int, drift: float) -> list[float]:
    """A seeded random walk from 80, floored at 10 (close >= $5 and $50M dollar volume always hold)."""
    rng = np.random.default_rng(seed)
    path = 80.0 * np.cumprod(1.0 + rng.normal(drift, 0.015, len(DAYS)))
    return [float(x) for x in np.round(np.maximum(path, 10.0), 2)]


def quarterly(first: int, amounts: list[str]) -> list[tuple[date, Decimal]]:
    """One ex-date every 63 sessions from DAYS[first], one per amount."""
    return [(DAYS[first + 63 * q], Decimal(a)) for q, a in enumerate(amounts)]


DIVS: dict[str, list[tuple[date, Decimal]]] = {
    "S00": quarterly(30, ["0.25"] * 22),
    "S01": quarterly(40, ["0.20"] * 10 + ["0.30"] * 12),  # a 50% raise at the 11th payment
    "S02": quarterly(700, ["0.15"] * 12),  # a first payment in late 2011: an initiation
    "S03": quarterly(20, ["0.40"] * 22),
}


def build_market() -> Market:
    history = {
        s: hist(s, walk(100 + k, 0.0002 * (k % 5) - 0.0003), days=DAYS, volume=5_000_000.0)
        for k, s in enumerate(STOCKS)
    }
    history["SPY"] = hist("SPY", walk(99, 0.0003), days=DAYS, volume=50_000_000.0)
    intervals = tuple(
        (s, DAYS[0], LEAVES if s == LEAVER else None) for s in STOCKS if s != JOINER
    ) + ((JOINER, JOINS, None),)
    return Market(
        history=history,
        membership=Membership(intervals=intervals),
        fx=((DAYS[0], Decimal("15000")),),
        dividends=DividendCalendar(DIVS),
    )


MARKET = build_market()
SMALL = TreeRankParams(
    top_n=3, max_iter=15, max_leaf_nodes=7, min_samples_leaf=5, train_start=date(2010, 2, 1), min_train_months=6
)
WIDE = replace(SMALL, top_n=5, learning_rate=0.1, max_leaf_nodes=5)
FUND = replace(SMALL, feature_set="price+fund")
# 2010-11-30 is before the first model (anchor 2009-12-31: no sample yet); the rest trade.
PROBES: tuple[date, ...] = (
    date(2010, 11, 30),
    date(2010, 12, 31),
    date(2011, 6, 30),
    date(2012, 12, 31),
    date(2013, 3, 14),
    date(2014, 11, 28),
)


def members(d: date) -> frozenset[str]:
    return MARKET.membership.members_on(d)


@pytest.fixture(scope="module")
def prepared() -> TreeRankPrepared:
    return TREE_RANK.prepare_market(MARKET)


# ---- a fake fundamental panel ------------------------------------------------------------------


@dataclass(frozen=True)
class Snap:
    filed: date | None
    net_income: float
    gross_profit: float
    assets: float
    equity: float
    shares_outstanding: float
    sue: float


NAN_SNAP = Snap(None, math.nan, math.nan, math.nan, math.nan, math.nan, math.nan)


class FakePanel:
    """Each symbol's snapshots by filing date; ``as_of`` answers from those filed on or before t."""

    def __init__(self, facts: dict[str, list[Snap]]) -> None:
        self.facts = facts

    def as_of(self, symbol: str, data_date: date) -> Snap | None:
        snaps = self.facts.get(symbol)
        if snaps is None:
            return None
        seen = [s for s in snaps if s.filed is not None and s.filed <= data_date]
        return seen[-1] if seen else NAN_SNAP


PANEL = FakePanel({
    "S01": [
        Snap(date(2011, 3, 1), 1.0e8, 4.0e8, 2.0e9, 1.0e9, 1.0e8, 0.5),
        Snap(date(2012, 3, 1), 1.2e8, 4.4e8, 2.2e9, 1.1e9, 1.0e8, 1.5),
    ],
    "S02": [Snap(date(2010, 3, 1), 5.0e7, 1.0e8, 1.0e9, 5.0e8, 2.0e7, -0.5)],  # stale after 2011-04-05
    "S03": [Snap(date(2012, 1, 15), 2.0e7, 9.0e7, 6.0e8, 3.0e8, 5.0e7, 0.0)],
})
FUND_MARKET = SimpleNamespace(
    history=MARKET.history, membership=MARKET.membership, dividends=MARKET.dividends, fundamentals=PANEL
)


# ---- the fixture itself -----------------------------------------------------------------------


def test_fixture_every_member_is_eligible_on_every_probe(prepared):
    """If a seed ever walks a stock under the screen, change the seed: the tests below assume this."""
    for d in PROBES + (date(2011, 2, 28), date(2011, 3, 31), date(2012, 5, 31), date(2012, 6, 29)):
        assert set(prepared.section(d).symbols) == set(members(d)), d


# ---- params and protocol ----------------------------------------------------------------------


def test_params_defaults_validation_and_as_dict():
    assert TreeRankParams().as_dict() == {
        "top_n": "20",
        "feature_set": "price",
        "learning_rate": "0.05",
        "max_iter": "300",
        "max_leaf_nodes": "15",
        "min_samples_leaf": "200",
        "l2": "1",
        "train_start": "1996-01-31",
        "min_train_months": "35",
        "horizon": "21",
        "seed": "0",
    }
    coerced = TreeRankParams(learning_rate=1, l2=0)
    assert isinstance(coerced.learning_rate, float) and isinstance(coerced.l2, float)
    for bad in (
        dict(top_n=0), dict(top_n=101), dict(feature_set="fund"), dict(learning_rate=0.0),
        dict(learning_rate=1.5), dict(max_iter=0), dict(max_leaf_nodes=1), dict(min_samples_leaf=0),
        dict(l2=-1.0), dict(min_train_months=0), dict(horizon=0), dict(seed=-1),
    ):
        with pytest.raises(ValueError):
            TreeRankParams(**bad)
    with pytest.raises(TypeError):
        TreeRankParams(top_n=True)
    with pytest.raises(TypeError):
        TreeRankParams(train_start=datetime(1996, 1, 31))
    assert replace(SMALL, top_n=9).model_key() == SMALL.model_key()
    assert replace(SMALL, seed=1).model_key() != SMALL.model_key()


def test_two_allocator_objects_and_what_lab_run_reads_off_them():
    for alloc in (TREE_RANK, TREE_RANK_FUND):
        assert isinstance(alloc, Allocator) and isinstance(alloc, MarketAware)
    assert (TREE_RANK.id, TREE_RANK_FUND.id) == ("TREE", "TREEF")
    assert runner.market_fields(TREE_RANK) == ("dividends",)
    assert runner.market_fields(TREE_RANK_FUND) == ("dividends", "fundamentals")
    assert TREE_RANK.lookback(SMALL) == FEATURE_LOOKBACK == 401
    assert TREE_RANK.symbols(SMALL) == ("SPY",)
    assert TREE_RANK.holds(SMALL) == ()
    assert TREE_RANK.uses_members(SMALL) is True
    with pytest.raises(ValueError, match="feature_set"):
        TREE_RANK.lookback(FUND)
    with pytest.raises(ValueError, match="feature_set"):
        TREE_RANK_FUND.lookback(SMALL)
    with pytest.raises(TypeError):
        TREE_RANK.lookback(object())


# ---- the calendar and the labels, by hand ------------------------------------------------------


def test_calendar_is_hand_checked():
    assert month_ends(date(2014, 1, 1), date(2014, 3, 31)) == (date(2014, 1, 31), date(2014, 2, 28), date(2014, 3, 31))
    assert month_ends(date(2014, 1, 31), date(2014, 1, 31)) == (date(2014, 1, 31),)
    assert month_ends(date(2014, 2, 1), date(2014, 2, 27)) == ()
    assert label_end(date(2014, 1, 31), 21) == date(2014, 3, 4)  # 19 February sessions, then Mar 3, 4
    assert label_end(date(2012, 11, 30), 21) == date(2013, 1, 2)  # December 2012 had 20 sessions
    assert label_end(date(2014, 1, 31), 1) == date(2014, 2, 3)
    assert year_end(2010) == date(2010, 12, 31)
    assert year_end(2014) == date(2014, 12, 31)
    assert anchor_for(date(2014, 12, 30)) == date(2013, 12, 31)
    assert anchor_for(date(2014, 12, 31)) == date(2014, 12, 31)
    assert anchor_for(date(2015, 1, 2)) == date(2014, 12, 31)


def test_training_dates_hold_only_labels_read_by_the_refit(prepared):
    anchor = date(2012, 12, 31)
    ts = prepared.training_dates(SMALL, anchor)
    assert ts[0] == date(2010, 2, 26)
    assert ts[-1] == date(2012, 10, 31)  # November's label is read on 2013-01-02, after the refit
    assert all(label_end(t, SMALL.horizon) <= anchor for t in ts)
    assert label_end(date(2012, 11, 30), SMALL.horizon) > anchor


def test_labels_are_the_cross_sectional_rank_of_the_forward_return():
    days = dates.sessions(date(2013, 1, 2), date(2014, 6, 30))
    t = date(2014, 1, 31)
    i0 = days.index(t)
    j = days.index(label_end(t, 21))  # 2014-03-04

    def series(after: float, later: float) -> list[float]:
        before = [50.0 + (0.2 if k % 2 else -0.2) for k in range(i0)]
        return before + [50.0] + [after] * (j - i0) + [later] * (len(days) - j - 1)

    history = {
        "A": hist("A", series(55.0, 70.0), days=days, volume=5e6),
        "B": hist("B", series(50.0, 20.0), days=days, volume=5e6),
        "C": hist("C", series(45.0, 90.0), days=days, volume=5e6),
        "D": hist("D", series(50.0, 50.0)[: i0 + 1], days=days[: i0 + 1], volume=5e6),  # no bar after t
        "SPY": hist("SPY", [100.0 + 0.1 * k for k in range(len(days))], days=days, volume=5e7),
    }
    inputs = TreeInputs(history, lambda d: frozenset({"A", "B", "C", "D"}))
    prep = TreeRankPrepared.build(inputs, "price")
    assert prep.section(t).symbols == ("A", "B", "C", "D")
    rets = prep.forward_returns(t, 21)
    assert rets[0] == pytest.approx(0.10)  # read at the label date, not at the later 70.0
    assert rets[1] == 0.0
    assert rets[2] == pytest.approx(-0.10)
    assert math.isnan(rets[3])
    labels = prep.labels(t, 21)
    assert labels[:3].tolist() == [1.0, 0.5, 0.0]
    assert math.isnan(labels[3])


# ---- features ---------------------------------------------------------------------------------


def test_features_are_the_lab_code_they_import(prepared):
    t = date(2012, 6, 29)
    sec = prepared.section(t)
    rows = factor_rows(MARKET.history, members(t), t, SCREEN)
    assert sec.symbols == tuple(r.symbol for r in rows)
    assert sec.raw.shape == (len(rows), len(PRICE_FEATURES))
    col = {name: sec.raw[:, k] for k, name in enumerate(PRICE_FEATURES)}
    np.testing.assert_array_equal(col["momentum"], [r.momentum for r in rows])
    np.testing.assert_array_equal(col["volatility"], [r.vol for r in rows])
    np.testing.assert_array_equal(col["dollar_volume"], [r.dollar_volume for r in rows])
    scores = residual_scores(build_grid(MARKET.history, "SPY"), list(sec.symbols), t, RESID)
    np.testing.assert_array_equal(col["residual_momentum"], [scores.get(s, math.nan) for s in sec.symbols])
    np.testing.assert_array_equal(col["high_nearness"], [nearness(MARKET.history, s, t, 252) for s in sec.symbols])
    raised = [
        1.0 if live_event(MARKET.dividends.known_on(s, t), DAYS[0], t, RAISE_EVENT) is not None else 0.0
        for s in sec.symbols
    ]
    np.testing.assert_array_equal(col["dividend_raise"], raised)
    yields = []
    for s, close in zip(sec.symbols, sec.close.tolist()):
        paid = sum((a for e, a in MARKET.dividends.known_on(s, t) if e > t - timedelta(days=365)), Decimal(0))
        yields.append(float(paid) / close)
    np.testing.assert_array_equal(col["dividend_yield"], yields)
    for k in range(sec.X.shape[1]):
        finite = np.isfinite(sec.raw[:, k])
        assert (np.isfinite(sec.X[:, k]) == finite).all()
        if finite.any():
            assert sec.X[finite, k].min() >= 0.0 and sec.X[finite, k].max() <= 1.0


def test_the_dividend_event_feature_is_not_vacuous(prepared):
    k = PRICE_FEATURES.index("dividend_raise")
    assert any(1.0 in prepared.section(m).raw[:, k] for m in month_ends(date(2011, 10, 1), date(2012, 3, 31)))


def test_training_universe_is_point_in_time_membership(prepared):
    assert LEAVER in prepared.section(date(2012, 5, 31)).symbols
    assert LEAVER not in prepared.section(date(2012, 6, 29)).symbols
    assert JOINER not in prepared.section(date(2011, 2, 28)).symbols
    assert JOINER in prepared.section(date(2011, 3, 31)).symbols


# ---- the walk-forward model and the book --------------------------------------------------------


def test_no_model_before_enough_months_means_cash(prepared):
    early = date(2010, 12, 30)
    assert prepared.model_on(early, SMALL) is None  # its refit is 2009-12-31: no sample yet
    assert TREE_RANK.targets_prepared(prepared, members(early), early, frozenset(), SMALL) == ()
    model = prepared.model_on(date(2010, 12, 31), SMALL)
    assert model is not None
    assert (model.anchor, model.months, model.n_features) == (date(2010, 12, 31), 10, 7)  # Feb..Nov 2010
    strict = replace(SMALL, min_train_months=11)
    assert prepared.model_on(date(2010, 12, 31), strict) is None
    assert prepared.model_on(date(2011, 12, 30), strict) is not None


def test_targets_are_the_top_n_predictions_at_equal_weight(prepared):
    d = date(2013, 7, 31)
    got = TREE_RANK.targets_prepared(prepared, members(d), d, frozenset(), SMALL)
    sec = prepared.section(d, members(d))
    pred = prepared.model_on(d, SMALL).predict(sec.X)
    order = sorted(range(len(sec.symbols)), key=lambda k: (-pred[k], sec.symbols[k]))[: SMALL.top_n]
    assert [t.symbol for t in got] == [sec.symbols[k] for k in order]
    assert all(t.weight == equal_weight(3) for t in got)
    assert_valid_targets(got, MARKET.history, d, frozenset())


def test_market_path_equals_the_from_scratch_path(prepared):
    inputs = TreeInputs.from_market(MARKET)
    nonempty = 0
    for d in PROBES:
        for held in (frozenset(), frozenset({"S01"})):
            for p in (SMALL, WIDE):
                got = TREE_RANK.targets_prepared(prepared, members(d), d, held, p)
                assert got == targets_with_inputs(inputs, members(d), d, held, p), (d, held, p)
                assert_valid_targets(got, MARKET.history, d, held)
                nonempty += bool(got)
    assert nonempty == 4 * (len(PROBES) - 1)


def test_bars_dividends_and_membership_after_d_change_nothing(prepared):
    nonempty = 0
    for d in PROBES[1:]:
        s = dates.next_session(d)
        divs = {k: list(v) for k, v in DIVS.items()}
        divs["S04"] = [(s, Decimal("5.00"))]
        divs["S01"] = [x for x in divs["S01"] if x[0] < s] + [(dates.next_session(s), Decimal("9.99"))]
        intervals = tuple((sym, a, s if sym == "S07" else b) for sym, a, b in MARKET.membership.intervals)
        futures = (
            Market(
                history={k: mutate_from(h, s) for k, h in MARKET.history.items()},
                membership=Membership(intervals=intervals),
                fx=MARKET.fx,
                dividends=DividendCalendar(divs),
            ),
            Market(
                history={k: truncate_before(h, s) for k, h in MARKET.history.items()},
                membership=MARKET.membership,
                fx=MARKET.fx,
                dividends=MARKET.dividends,
            ),
        )
        before = TREE_RANK.targets_prepared(prepared, members(d), d, frozenset(), SMALL)
        for future in futures:
            after = TREE_RANK.targets_prepared(TREE_RANK.prepare_market(future), members(d), d, frozenset(), SMALL)
            assert after == before, (d, s)
        nonempty += bool(before)
    assert nonempty == len(PROBES) - 1


def test_two_prepares_fit_bit_identical_models():
    a = TREE_RANK.prepare_market(MARKET)
    b = TREE_RANK.prepare_market(MARKET)
    for year in (2010, 2011, 2012, 2013):
        ma = a.model(SMALL, year_end(year))
        mb = b.model(SMALL, year_end(year))
        assert ma is not None and ma == mb and ma.digest == mb.digest and len(ma.digest) == 64
    for d in PROBES:
        assert TREE_RANK.targets_prepared(a, members(d), d, frozenset(), SMALL) == TREE_RANK.targets_prepared(
            b, members(d), d, frozenset(), SMALL
        )
    anchor = year_end(2012)
    assert a.model(replace(SMALL, top_n=9), anchor) is a.model(SMALL, anchor)  # book size shares the fit
    assert a.model(replace(SMALL, learning_rate=0.2), anchor).digest != a.model(SMALL, anchor).digest


def test_an_all_missing_column_fits_as_unsplittable_and_leaves_other_fits_untouched():
    # The fundamentals before 2009: four columns with no finite value. sklearn 1.9 raised on them
    # ("window shape cannot be larger than input array shape"); the guard fits them as a constant.
    rng = np.random.default_rng(0)
    X = rng.normal(size=(600, 3))
    y = X[:, 0] + 0.1 * rng.normal(size=600)
    blank = np.column_stack([X, np.full(600, np.nan)])
    est = tree_rank.fit_model(blank, y, SMALL)
    filled = np.column_stack([X, rng.normal(size=600)])
    assert np.array_equal(est.predict(blank), est.predict(filled))  # the blank column is never split on
    assert np.array_equal(est.predict(blank), tree_rank.fit_model(X, y, SMALL).predict(X))
    assert np.isnan(blank[:, 3]).all()  # the caller's matrix is not written to


# ---- the feature-set switch ---------------------------------------------------------------------


def test_feature_set_switch_adds_the_four_fundamental_columns(prepared):
    fund = TREE_RANK_FUND.prepare_market(FUND_MARKET)
    t = date(2012, 6, 29)
    a, b = prepared.section(t), fund.section(t)
    assert a.symbols == b.symbols
    assert b.raw.shape == (len(b.symbols), 11)
    np.testing.assert_array_equal(b.raw[:, :7], a.raw)
    k = b.symbols.index("S01")
    close = float(b.close[k])
    assert b.raw[k, 7:].tolist() == [1.1e9 / (1.0e8 * close), 1.2e8 / 1.1e9, 4.4e8 / 2.2e9, 1.5]
    assert np.isnan(b.raw[b.symbols.index("S02"), 7:]).all()  # filed 2010-03-01: older than 400 days
    assert np.isnan(b.raw[b.symbols.index("S00"), 7:]).all()  # never filed
    assert fund.model(FUND, year_end(2012)).n_features == 11
    assert prepared.model(SMALL, year_end(2012)).n_features == 7
    with pytest.raises(ValueError, match="feature_set"):
        TREE_RANK.targets_prepared(prepared, members(t), t, frozenset(), FUND)
    with pytest.raises(ValueError, match="feature_set"):
        TREE_RANK_FUND.targets_prepared(fund, members(t), t, frozenset(), SMALL)
    d = date(2013, 7, 31)
    got = TREE_RANK_FUND.targets_prepared(fund, members(d), d, frozenset(), FUND)
    assert got
    assert got == targets_with_inputs(TreeInputs.from_market(FUND_MARKET), members(d), d, frozenset(), FUND)


def test_a_filing_dated_after_t_is_never_read():
    class Liar:
        def as_of(self, symbol: str, data_date: date) -> Snap:
            return Snap(data_date + timedelta(days=1), 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)

    assert all(math.isnan(x) for x in fundamental_features(Liar(), "S01", date(2012, 6, 29), 50.0, 1e8))


# ---- the history-only contract and the dev runner ---------------------------------------------


def test_history_only_path_targets_nothing():
    """test_lab_methods.test_allocator_contract requires exactly this of a market-aware allocator."""
    stocks = everyone({s: MARKET.history[s] for s in STOCKS})
    probe = [dates.next_session(d) for d in PROBES[1:]]
    assert assert_p4_identity(TREE_RANK, MARKET.history, stocks, PROBES, [frozenset()], [SMALL]) == 0
    assert assert_no_lookahead(TREE_RANK, MARKET.history, stocks, probe, [frozenset()], [SMALL]) == 0


def test_a_candidate_runs_the_lab_smoke_window():
    """The shape phase 7's method will have, through the same runner test_lab_methods uses."""
    params = TreeRankParams()
    market = smoke_market(TREE_RANK.symbols(params))
    c = Candidate(
        id="M9999-SMOKE",
        family="M9999",  # a lab-method-shaped family; phase 7 uses its real id
        rules=MONTHLY_HOLD_FRAC_GOTRADE,
        allocator=TREE_RANK,
        params=params,
        rationale="smoke: the tree ranker through the dev runner",
        added=date(2026, 10, 12),
        owner_inputs=(),
    )
    amount = Decimal("1.0300")
    result, row = run_candidate(market, {"SPY": {SPY_EX_DATE: amount}}, (Dividend(SPY_EX_DATE, amount),), c)
    assert row.end == DEV_END
    assert len(result.snapshots) >= 2


# ---- purity (tests/test_strategy_purity.py does not glob lab/) ---------------------------------

LAB_IMPORT_ROOTS = FORBIDDEN_IMPORT_ROOTS | {"os", "subprocess", "sqlite3"}  # test_lab_methods' extras
LAB_CALLS = FORBIDDEN_CALLS | {"eval", "exec"}


def test_tree_rank_source_has_no_clock_randomness_or_io():
    path = Path(tree_rank.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    problems: list[str] = []
    for node in ast.walk(tree):
        where = f"{path.name}:{getattr(node, 'lineno', '?')}"
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in LAB_IMPORT_ROOTS or alias.name == "seer_engine.bars":
                    problems.append(f"{where} import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in LAB_IMPORT_ROOTS or node.module in (
                "seer_engine.bars", "seer_engine.research", "seer_engine.lab.store"
            ):
                problems.append(f"{where} from {node.module} import ...")
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRS:
            problems.append(f"{where} .{node.attr}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in LAB_CALLS:
            problems.append(f"{where} {node.func.id}()")
    assert problems == []


def test_tree_rank_loads_no_db_or_network_module():
    code = (
        "import importlib, sys\n"
        "importlib.import_module('seer_engine.lab.tree_rank')\n"
        f"bad = [m for m in {FORBIDDEN_MODULES!r} if m in sys.modules]\n"
        "print(','.join(bad))\n"
    )
    assert _fresh_python(code) == ""
