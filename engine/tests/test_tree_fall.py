"""The forward-fall label and the sizing head (lab/tree_rank.py; R2, handover 2026-10-13).

The ranker's own tests are in tests/test_tree_rank.py and are untouched; this module tests only
what was added beside it. The market, the probe dates and the membership helper are imported from
there so both heads are judged on the same synthetic history.

What is proved here: the two fall measures on hand-built paths, including that an unmeasurable
window is NaN and a calm window is a measured 0.0; that nothing dated after the label end is read;
that the fall label is the RAW measure and is never rank-normalised (D13); that the three
market-level columns are appended un-normalised, are constant within a date, move across dates, and
read no bar after the decision date; that the fall caches and the return caches cannot serve each
other; that the fit is deterministic; that the exposure ladder is monotone in the market level and
reaches both ends; that the head sizes the book in whole slots at a fixed weight and can go to
cash; that the prepared path equals the from-scratch path bit for bit; that nothing after the
decision date changes a target; that the history-only path targets nothing; that a candidate runs
the lab's smoke window at a reach of 401 <= 473; and that `FALL` is free across the whole lab while
`FALLF` is left unclaimed.

The module's purity is already covered: tests/test_tree_rank.py's AST and fresh-interpreter checks
read the whole of lab/tree_rank.py, additions included.
"""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import numpy as np
import pytest
from allocatorkit import assert_no_lookahead, assert_p4_identity, assert_valid_targets, everyone
from labkit import SPY_EX_DATE, smoke_market
from stratkit import hist, mutate_from, truncate_before
from test_tree_rank import DIVS, MARKET, PANEL, STOCKS, members

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend
from seer_engine.backtest.dev import DEV_END, Candidate, run_candidate
from seer_engine.backtest.market import DividendCalendar, Market, Membership
from seer_engine.backtest.registry import REGISTRY
from seer_engine.lab import runner
from seer_engine.lab.method import discover
from seer_engine.lab.tree_rank import (
    FALL_FEATURE_LOOKBACK,
    FALL_MEASURES,
    FALL_SIZE,
    FEATURE_LOOKBACK,
    MARKET_FEATURES,
    MARKET_HIGH_N,
    MARKET_VOL_N,
    QUARTER,
    TREE_RANK,
    FallSizeAllocator,
    FallSizeParams,
    Section,
    TreeInputs,
    TreeRankPrepared,
    anchor_for,
    fall_feature_names,
    fall_targets_with_inputs,
    feature_names,
    forward_downside_vol,
    forward_drawdown,
    forward_fall,
    market_columns,
    month_ends,
    year_end,
)
from seer_engine.sim.book import equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE_TBAND, TARGET_RESIZE_BAND
from seer_engine.strategies.allocator import Allocator, MarketAware

# The ranker's SMALL, re-pointed at the fall: a quarter's horizon, three slots, sizing on.
SMALL = FallSizeParams(
    slots=3,
    max_iter=15,
    max_leaf_nodes=7,
    min_samples_leaf=5,
    train_start=date(2010, 2, 1),
    min_train_months=6,
    horizon=QUARTER,
)
FULL = replace(SMALL, size=False)  # the control: always fully invested
VOL = replace(SMALL, measure="downside_vol")
FUND = replace(SMALL, feature_set="price+fund")  # D14: no exported object; built locally below
FALL_FUND = FallSizeAllocator("price+fund")  # local only -- never a module-level name
FUND_MARKET = SimpleNamespace(
    history=MARKET.history, membership=MARKET.membership, dividends=MARKET.dividends, fundamentals=PANEL
)

# 2010-11-30's anchor is 2009-12-31, before the first fall model; the rest trade.
PROBES: tuple[date, ...] = (
    date(2010, 11, 30),
    date(2010, 12, 31),
    date(2011, 6, 30),
    date(2012, 12, 31),
    date(2013, 3, 14),
    date(2014, 11, 28),
)
DECIDE: tuple[date, ...] = month_ends(date(2012, 1, 1), date(2014, 11, 30))


@pytest.fixture(scope="module")
def prepared() -> TreeRankPrepared:
    return FALL_SIZE.prepare_market(MARKET)


def book(prep: TreeRankPrepared, d: date, params: FallSizeParams):
    return FALL_SIZE.targets_prepared(prep, members(d), d, frozenset(), params)


# ---- the two measures, by hand ------------------------------------------------------------------


def _bare_section(day: date, symbols: tuple[str, ...]) -> Section:
    """A Section carrying only what the measures read: the day and the symbols."""
    n = len(symbols)
    return Section(day, symbols, np.zeros(n), np.zeros((n, 1)), np.zeros((n, 1)))


def _tiny_history(closes: dict[str, list[float]], days: list[date]):
    return {s: hist(s, c, days=days[: len(c)], volume=5e6) for s, c in closes.items()}


def test_forward_drawdown_is_the_worst_peak_to_trough_fall():
    days = dates.sessions(date(2014, 1, 2), date(2014, 1, 10))  # 7 sessions
    t, end = days[0], days[3]
    history = _tiny_history(
        {
            "DIP": [100.0, 110.0, 88.0, 99.0, 10.0, 10.0, 10.0],   # 1 - 88/110 = 0.20, crash after end
            "UP": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0],
            "SHORT": [100.0],                                       # no bar after t
            "ZERO": [100.0, 0.0, 90.0, 95.0, 95.0, 95.0, 95.0],     # an unusable close in the window
        },
        days,
    )
    sec = _bare_section(t, ("DIP", "UP", "SHORT", "ZERO"))
    got = forward_drawdown(history, sec, end)
    assert got[0] == pytest.approx(0.20)
    assert got[1] == 0.0 and not math.isnan(got[1])  # measured calm is zero, never NaN
    assert math.isnan(got[2])
    assert math.isnan(got[3])
    assert not got.flags.writeable


def test_forward_downside_vol_is_the_root_mean_square_of_the_down_days():
    days = dates.sessions(date(2014, 1, 2), date(2014, 1, 10))
    t, end = days[0], days[3]
    history = _tiny_history(
        {"DIP": [100.0, 110.0, 88.0, 99.0, 10.0, 10.0, 10.0], "UP": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0]},
        days,
    )
    sec = _bare_section(t, ("DIP", "UP"))
    got = forward_downside_vol(history, sec, end)
    assert got[0] == pytest.approx(math.sqrt((0.2**2) / 3))  # +10%, -20%, +12.5% over three days
    assert got[1] == 0.0


def test_no_bar_after_the_label_end_is_ever_read():
    """The 10.0 crash on the sessions after ``end`` must not reach either measure."""
    days = dates.sessions(date(2014, 1, 2), date(2014, 1, 10))
    t, end = days[0], days[3]
    full = _tiny_history({"DIP": [100.0, 110.0, 88.0, 99.0, 10.0, 10.0, 10.0]}, days)
    cut = _tiny_history({"DIP": [100.0, 110.0, 88.0, 99.0]}, days)
    sec = _bare_section(t, ("DIP",))
    for measure in FALL_MEASURES:
        np.testing.assert_array_equal(
            forward_fall(full, sec, end, measure), forward_fall(cut, sec, end, measure)
        )
    with pytest.raises(ValueError, match="measure"):
        forward_fall(full, sec, end, "variance")


# ---- the label ----------------------------------------------------------------------------------


def test_the_fall_label_is_the_raw_level_and_is_never_rank_normalised(prepared):
    """D13: the label is the measure itself. rank01 is not applied and must never be."""
    t = date(2012, 6, 29)
    raw = prepared.forward_fall(t, QUARTER, "drawdown")
    labels = prepared.fall_labels(t, QUARTER, "drawdown")
    np.testing.assert_array_equal(labels, raw)  # identical, not merely correlated
    finite = np.isfinite(raw)
    assert finite.any()
    assert (np.isfinite(labels) == finite).all()
    # a rank label would be exactly {0, 1/(n-1), ..., 1} on every date. This one is not.
    vals = np.sort(labels[finite])
    assert not (vals[0] == 0.0 and vals[-1] == 1.0 and len(vals) > 2)
    assert prepared.end(t, QUARTER) == date(2012, 9, 28)


def test_two_dates_labels_live_on_a_shared_scale(prepared):
    """The point of a level: a calm date and a violent date are comparable, which ranks are not.

    Pick the two decision dates whose mean finite drawdown differs most and assert the means
    differ. Under the superseded rank label every date's mean is (n-1)/2n ~ 0.5 by construction and
    this test is impossible to pass -- which is exactly why it is here.
    """
    means = {}
    for t in DECIDE:
        y = prepared.fall_labels(t, QUARTER, "drawdown")
        ok = np.isfinite(y)
        if ok.any():
            means[t] = float(np.mean(y[ok]))
    assert len(means) >= 10
    assert max(means.values()) - min(means.values()) > 0.01


def test_the_fall_cache_and_the_return_cache_cannot_serve_each_other(prepared):
    t = date(2012, 6, 29)
    rets = prepared.forward_returns(t, QUARTER)
    dd = prepared.forward_fall(t, QUARTER, "drawdown")
    dv = prepared.forward_fall(t, QUARTER, "downside_vol")
    assert not np.array_equal(rets, dd)
    assert not np.array_equal(dd, dv)
    assert (dd[np.isfinite(dd)] >= 0.0).all()  # a fall is never negative; a return can be
    # the caches are different dicts, keyed differently, and first-use order cannot matter
    assert all(len(k) == 2 for k in prepared._returns)
    assert all(len(k) == 3 for k in prepared._falls)
    a, b = TREE_RANK.prepare_market(MARKET), TREE_RANK.prepare_market(MARKET)
    a.forward_returns(t, QUARTER)
    np.testing.assert_array_equal(a.forward_fall(t, QUARTER, "drawdown"), b.forward_fall(t, QUARTER, "drawdown"))
    b.forward_returns(t, QUARTER)
    np.testing.assert_array_equal(a.forward_returns(t, QUARTER), b.forward_returns(t, QUARTER))


# ---- the market-level columns (D13) ---------------------------------------------------------------


def test_the_market_columns_are_appended_un_normalised_and_constant_within_a_date(prepared):
    t = date(2012, 6, 29)
    base = prepared.section(t)
    fall = prepared.fall_section(t)
    k = len(feature_names("price"))
    assert fall_feature_names("price") == tuple(feature_names("price")) + MARKET_FEATURES
    assert base.X.shape[1] == k == 7
    assert fall.X.shape[1] == k + len(MARKET_FEATURES) == 10
    # the ranker's own columns pass through byte for byte: build_section is composed, not replaced
    np.testing.assert_array_equal(fall.X[:, :k], base.X)
    np.testing.assert_array_equal(fall.raw[:, :k], base.raw)
    assert fall.symbols == base.symbols and fall.day == base.day
    # each appended column is ONE value repeated down the rows: a level, carrying no cross-section
    for c in range(k, fall.X.shape[1]):
        col = fall.X[:, c]
        assert len(np.unique(col[np.isfinite(col)])) <= 1
    assert not fall.X.flags.writeable


def test_the_market_columns_move_across_dates_which_is_the_whole_point(prepared):
    """A level the model can read. Under per-date ranking alone these would be constants."""
    seen = {c: set() for c in range(len(MARKET_FEATURES))}
    for t in DECIDE:
        sec = prepared.fall_section(t)
        for c in range(len(MARKET_FEATURES)):
            v = float(sec.X[0, len(feature_names("price")) + c])
            if math.isfinite(v):
                seen[c].add(round(v, 9))
    for c, vals in seen.items():
        assert len(vals) >= 5, (MARKET_FEATURES[c], sorted(vals))


def test_the_market_columns_read_no_bar_after_the_decision_date():
    """Same discipline as _window: searchsorted(side='right') on the decision date."""
    days = dates.sessions(date(2012, 1, 3), date(2014, 1, 10))
    closes = [100.0 + i for i in range(len(days))]
    full = {"SPY": hist("SPY", closes, days=days, volume=5e6)}
    cut_at = 400
    cut = {"SPY": hist("SPY", closes[: cut_at + 1], days=days[: cut_at + 1], volume=5e6)}
    mom = np.array([0.1, 0.2, 0.3])
    assert market_columns(full, days[cut_at], mom) == market_columns(cut, days[cut_at], mom)
    # a market with no SPY at all is NaN on the two SPY columns, never an exception
    dd, vol, disp = market_columns({}, days[cut_at], mom)
    assert math.isnan(dd) and math.isnan(vol) and math.isfinite(disp)
    assert FALL_FEATURE_LOOKBACK == max(FEATURE_LOOKBACK, MARKET_HIGH_N, MARKET_VOL_N + 1) == 401


# ---- params and protocol -------------------------------------------------------------------------


def test_params_defaults_validation_and_as_dict():
    assert FallSizeParams().as_dict() == {
        "slots": "20",
        "size": "on",
        "feature_set": "price",
        "measure": "drawdown",
        "learning_rate": "0.05",
        "max_iter": "300",
        "max_leaf_nodes": "15",
        "min_samples_leaf": "200",
        "l2": "1",
        "train_start": "1996-01-31",
        "min_train_months": "35",
        "horizon": "63",
        "seed": "0",
    }
    assert FallSizeParams().horizon == QUARTER == 63
    coerced = FallSizeParams(learning_rate=1, l2=0)
    assert isinstance(coerced.learning_rate, float) and isinstance(coerced.l2, float)
    for bad in (
        dict(slots=0), dict(slots=101), dict(feature_set="fund"), dict(measure="variance"),
        dict(learning_rate=0.0), dict(learning_rate=1.5), dict(max_iter=0), dict(max_leaf_nodes=1),
        dict(min_samples_leaf=0), dict(l2=-1.0), dict(min_train_months=0), dict(horizon=0),
        dict(horizon=253), dict(seed=-1),
    ):
        with pytest.raises(ValueError):
            FallSizeParams(**bad)
    for bad in (dict(slots=True), dict(size=1), dict(measure=1), dict(train_start=datetime(1996, 1, 31))):
        with pytest.raises(TypeError):
            FallSizeParams(**bad)
    # D2c2: neither slots nor size touches the fit, exactly as top_n does not for the ranker
    assert replace(SMALL, size=False).model_key() == SMALL.model_key()
    assert replace(SMALL, slots=5).model_key() == SMALL.model_key()
    assert replace(SMALL, measure="downside_vol").model_key() != SMALL.model_key()


def test_one_fall_allocator_object_and_what_lab_run_reads_off_it():
    assert isinstance(FALL_SIZE, Allocator) and isinstance(FALL_SIZE, MarketAware)
    assert FALL_SIZE.id == "FALL"
    assert runner.market_fields(FALL_SIZE) == ("dividends",)
    assert FALL_SIZE.lookback(SMALL) == FALL_FEATURE_LOOKBACK == 401
    assert FALL_SIZE.symbols(SMALL) == ("SPY",)
    assert FALL_SIZE.holds(SMALL) == ()
    assert FALL_SIZE.uses_members(SMALL) is True
    with pytest.raises(ValueError, match="feature_set"):
        FALL_SIZE.lookback(FUND)
    with pytest.raises(TypeError):
        FALL_SIZE.lookback(object())
    # D14: there is no module-level fundamentals object to import
    import seer_engine.lab.tree_rank as tr

    assert not hasattr(tr, "FALL_SIZE_FUND")


def test_the_new_allocator_id_is_free_and_fallf_is_left_unclaimed():
    """D5: a config digest names the allocator by id, so a collision would merge two methods."""
    taken = {str(c.allocator.id) for c in REGISTRY}
    for _, (method, _) in discover().items():
        taken |= {str(c.allocator.id) for c in method.all_candidates()}
    assert "FALL" not in taken
    assert "FALLF" not in taken  # D14: left free for whoever needs it, claimed by nothing here
    assert len(taken) >= 75


# ---- the model ------------------------------------------------------------------------------------


def test_no_model_before_enough_months_means_cash(prepared):
    early = date(2010, 11, 30)
    assert prepared.fall_model_on(early, SMALL) is None  # its refit is 2009-12-31: no sample yet
    assert book(prepared, early, SMALL) == ()
    model = prepared.fall_model_on(date(2010, 12, 31), SMALL)
    assert model is not None
    assert (model.anchor, model.n_features) == (date(2010, 12, 31), 10)  # 7 ranked + 3 level
    assert model.months >= SMALL.min_train_months
    assert len(model.levels) == model.months  # one date-level mean per labelled month-end
    strict = replace(SMALL, min_train_months=model.months + 1)
    assert prepared.fall_model_on(date(2010, 12, 31), strict) is None


def test_two_prepares_fit_bit_identical_fall_models_and_levels():
    a = FALL_SIZE.prepare_market(MARKET)
    b = FALL_SIZE.prepare_market(MARKET)
    for year in (2011, 2012, 2013):
        ma, mb = a.fall_model(SMALL, year_end(year)), b.fall_model(SMALL, year_end(year))
        assert ma is not None and ma == mb
        assert ma.digest == mb.digest and len(ma.digest) == 64
        assert ma.levels == mb.levels and ma.cut == mb.cut
        assert list(ma.levels) == sorted(ma.levels)  # kept sorted, so searchsorted is valid
    for d in PROBES:
        assert book(a, d, SMALL) == book(b, d, SMALL)


def test_the_book_size_does_not_change_the_fit_only_the_ladder(prepared):
    """D2c2: slots and size are decision-time, not fit-time. One refit serves every book size."""
    anchor = year_end(2012)
    base = prepared.fall_model(SMALL, anchor)
    assert prepared.fall_model(FULL, anchor) is base
    assert prepared.fall_model(replace(SMALL, slots=5), anchor) is base
    assert prepared.fall_model(replace(SMALL, slots=9), anchor) is base


def test_the_exposure_ladder_is_monotone_and_reaches_both_ends(prepared):
    """D13: the head reads a MARKET-LEVEL quantity against the model's training distribution."""
    model = prepared.fall_model(SMALL, year_end(2012))
    assert model is not None
    lo, hi = model.levels[0], model.levels[-1]
    span = hi - lo
    assert span > 0.0  # the training dates did not all look identical: there IS a level to read
    for slots in (3, 5, 20):
        assert model.exposure(lo - span, slots) == slots      # calmer than anything seen -> full
        assert model.exposure(hi + span, slots) == 0          # worse than anything seen -> cash
        assert model.exposure(model.cut, slots) == pytest.approx(slots / 2, abs=1)
        ks = [model.exposure(lo + span * i / 20.0, slots) for i in range(21)]
        assert ks == sorted(ks, reverse=True)                 # monotone non-increasing
        assert all(0 <= k <= slots for k in ks)
    assert model.cut == model.levels[len(model.levels) // 2]


# ---- the head: exposure, not selection ------------------------------------------------------------


def test_the_head_holds_whole_slots_at_a_fixed_weight(prepared):
    weight = equal_weight(SMALL.slots)
    for d in DECIDE:
        got = book(prepared, d, SMALL)
        assert len(got) <= SMALL.slots
        assert all(t.weight == weight for t in got)  # never renormalised onto the survivors
        assert sum((t.weight for t in got), Decimal(0)) == weight * len(got)
        assert_valid_targets(got, MARKET.history, d, frozenset())


def test_the_head_sizes_the_book_and_the_control_does_not(prepared):
    sized = [len(book(prepared, d, SMALL)) for d in DECIDE]
    full = [len(book(prepared, d, FULL)) for d in DECIDE]
    assert max(sized) == SMALL.slots           # it reaches a full book
    assert min(sized) < SMALL.slots            # and it goes below one: this is the sizing
    assert len(set(sized)) >= 3                # in more than one step
    assert set(full) == {SMALL.slots}          # the control is always fully invested
    vol = [len(book(prepared, d, VOL)) for d in DECIDE]
    assert min(vol) < max(vol) == SMALL.slots  # the other measure sizes too


def test_a_cross_section_the_model_reads_as_dangerous_is_all_cash():
    """The k = 0 end of the range, forced rather than waited for: a training distribution that

    makes every real date look catastrophic. Deterministic, and the half of the exposure claim that
    must never be weakened.
    """
    prep = FALL_SIZE.prepare_market(MARKET)
    d = date(2013, 3, 14)
    anchor = anchor_for(d)
    model = prep.fall_model(SMALL, anchor)
    assert model is not None and book(prep, d, SMALL)
    calm = tuple(v - 10.0 for v in model.levels)  # every training date looked far calmer
    prep._fall_models[(anchor, SMALL.model_key())] = replace(model, levels=calm)
    assert book(prep, d, SMALL) == ()
    assert len(book(prep, d, FULL)) == SMALL.slots  # the control ignores the ladder and stays full
    wild = tuple(v + 10.0 for v in model.levels)   # every training date looked far worse
    prep._fall_models[(anchor, SMALL.model_key())] = replace(model, levels=wild)
    assert len(book(prep, d, SMALL)) == SMALL.slots  # ... so today is calm: a full book


def test_one_slot_is_five_times_the_resize_band():
    """D7, in the tape's own arithmetic: an exposure step the measuring tape cannot miss."""
    for slots in (3, 10, 20, 25):
        weight = equal_weight(slots)
        band = TARGET_RESIZE_BAND * weight  # of equity, per sim/book.py:462
        assert weight == band * 5
    assert MONTHLY_HOLD_FRAC_GOTRADE_TBAND.resize_basis == "target"
    assert TARGET_RESIZE_BAND == Decimal("0.20")


# ---- the two paths ---------------------------------------------------------------------------------


def test_market_path_equals_the_from_scratch_path(prepared):
    inputs = TreeInputs.from_market(MARKET)
    nonempty = 0
    for d in PROBES:
        for held in (frozenset(), frozenset({"S01"})):
            for p in (SMALL, FULL, VOL):
                got = FALL_SIZE.targets_prepared(prepared, members(d), d, held, p)
                assert got == fall_targets_with_inputs(inputs, members(d), d, held, p), (d, held, p)
                assert_valid_targets(got, MARKET.history, d, held)
                nonempty += bool(got)
    assert nonempty == 6 * (len(PROBES) - 1)  # every probe but the pre-model one trades


def test_bars_dividends_and_membership_after_d_change_nothing(prepared):
    nonempty = 0
    for d in PROBES[1:]:
        s = dates.next_session(d)
        divs = {k: list(v) for k, v in DIVS.items()}
        divs["S04"] = [(s, Decimal("5.00"))]
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
        before = book(prepared, d, SMALL)
        for future in futures:
            assert book(FALL_SIZE.prepare_market(future), d, SMALL) == before, (d, s)
        nonempty += bool(before)
    assert nonempty == len(PROBES) - 1


def test_the_fund_branch_is_reachable_but_is_not_exported(prepared):
    """D14 + D8: the "price+fund" branch works; no module-level object claims the id "FALLF".

    Built locally, never imported. Phase 5 may not pre-register on it (the EDGAR panel starts in
    2009), so exporting it would claim an allocator id for ever for nothing.
    """
    assert FALL_FUND.id == "FALLF"
    assert runner.market_fields(FALL_FUND) == ("dividends", "fundamentals")
    fund = FALL_FUND.prepare_market(FUND_MARKET)
    t = date(2012, 6, 29)
    assert fund.section(t).raw.shape[1] == 11
    assert fund.fall_section(t).X.shape[1] == 11 + len(MARKET_FEATURES) == 14
    assert fund.fall_model(FUND, year_end(2012)).n_features == 14
    d = date(2013, 7, 31)
    got = FALL_FUND.targets_prepared(fund, members(d), d, frozenset(), FUND)
    assert got == fall_targets_with_inputs(TreeInputs.from_market(FUND_MARKET), members(d), d, frozenset(), FUND)
    with pytest.raises(ValueError, match="feature_set"):
        FALL_FUND.targets_prepared(fund, members(d), d, frozenset(), SMALL)


def test_history_only_path_targets_nothing():
    """test_lab_methods.test_allocator_contract requires exactly this of a market-aware allocator."""
    stocks = everyone({s: MARKET.history[s] for s in STOCKS})
    probe = [dates.next_session(d) for d in PROBES[1:]]
    assert assert_p4_identity(FALL_SIZE, MARKET.history, stocks, PROBES, [frozenset()], [SMALL]) == 0
    assert assert_no_lookahead(FALL_SIZE, MARKET.history, stocks, probe, [frozenset()], [SMALL]) == 0


def test_a_candidate_runs_the_lab_smoke_window():
    """The shape phase 5's method will have, on the tape it will be priced at (473-bar fixture)."""
    params = FallSizeParams()
    market = smoke_market(FALL_SIZE.symbols(params))
    c = Candidate(
        id="M9999-FALL-SMOKE",
        family="M9999",
        rules=MONTHLY_HOLD_FRAC_GOTRADE_TBAND,
        allocator=FALL_SIZE,
        params=params,
        rationale="smoke: the fall model through the dev runner",
        added=date(2026, 10, 13),
        owner_inputs=(),
    )
    amount = Decimal("1.0300")
    result, row = run_candidate(market, {"SPY": {SPY_EX_DATE: amount}}, (Dividend(SPY_EX_DATE, amount),), c)
    assert row.end == DEV_END
    assert len(result.snapshots) >= 2
    # D13/M4a: the market columns add no reach. 401 is the fall allocator's own constant.
    assert FALL_SIZE.lookback(params) == FALL_FEATURE_LOOKBACK == 401
    assert FALL_SIZE.lookback(params) <= len(market.history["SPY"])  # 401 <= 473
