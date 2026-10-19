"""The shortfall decomposition (lab/shortfall.py): the gap, the terms, and the residual.

The rules are tested on synthetic rows in a temp database, so they hold for any input and keep
holding on the day the real lab contains something different. The headline -- trial 828's
2009-2015 gap and its decomposition -- is pinned against the committed lab.sqlite, because that
row is frozen and append-only and nothing else would notice if an unrelated change re-priced the
published answer. The committed file is opened read-only (no migration, so no dirtying) and the
pin skips when the row is absent.

The research stores are gitignored and absent from every worktree, so the gate's era shape is
measured on a synthetic History built here instead.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import pytest

from labkit import LAB_PRICE_FINGERPRINT, stamp_provenance
from seer_engine.backtest import regime
from seer_engine.lab import hardgate, shortfall, store, turnover
from seer_engine.lab import walkforward as wf
from seer_engine.lab.exposure import WHOLE
from seer_engine.lab.gate_probe import GATE_N, GATE_SYMBOL
from seer_engine.strategies.base import History

BENCH_SPAN = (date(1993, 2, 1), date(2015, 10, 16))
DEV_SPAN = (date(1996, 1, 2), date(2015, 10, 16))

GATED_CONFIG = (
    "rules=TradeRules(id='monthly-hold-frac-gotrade')\n"
    "allocator=<M0244>\n"
    "params=GestureParams(top=30,screen=FactorParams(rank='momentum',top=1000,"
    "trend=('SPY',200)))\n"
)
UNGATED_CONFIG = (
    "rules=TradeRules(id='monthly-hold-frac-gotrade')\n"
    "allocator=<M0248>\n"
    "params=CheapBuybackParams(top=20,w_pct=50,pick='random',seed=1)\n"
)


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    yield c
    c.close()


def _months(start: date, end: date) -> list[date]:
    out, d = [], date(start.year, start.month, 1)
    while True:
        nxt = date(d.year + (d.month == 12), (d.month % 12) + 1, 1)
        last = nxt - timedelta(days=1)
        if last > end:
            return out
        if last >= start:
            out.append(last)
        d = nxt


def _curve(months: list[date], annual: float) -> str:
    out, v = [], 1.0
    for d in months:
        out.append([d.isoformat(), round(v, 8)])
        v *= (1.0 + annual) ** (1.0 / 12.0)
    return json.dumps(out)


def _trial(**kw) -> store.TrialRow:
    base = dict(
        method_id="M0001", candidate_id="M0001-A", config_digest="d1",
        config_text=GATED_CONFIG, rules_id="MONTHLY_HOLD", allocator_id="M0001", window="dev",
        start=DEV_SPAN[0].isoformat(), end=DEV_SPAN[1].isoformat(),
        store_fingerprint="399d0d25", git_sha="abc123", run_at="2026-10-19T00:00:00+00:00",
        total_return=3.0, cagr=0.12, max_drawdown=0.11, profit_factor=1.6, trades=250,
        sharpe=0.9, exposure=0.69, turnover=15.0, worst_year=2008, worst_year_return=-0.1,
        spy_tr_return=2.0, spy_tr_cagr=0.08, mar=0.8, failed="", eligible=False, dsr=0.5,
        n_trials_at_run=60, curve_json=_curve(_months(*DEV_SPAN), 0.09),
    )
    base.update(kw)
    return store.TrialRow(**base)


def _lab(conn, *, arms=(("M0001", "M0001-A", 0.09, GATED_CONFIG),), prices=LAB_PRICE_FINGERPRINT):
    """The benchmark plus one dev trial per arm, all stamped on the same price fingerprint."""
    with conn:
        store.add_method(conn, id="H-REF", name="SPY buy and hold", family="reference",
                         source_kind="seed", hypothesis="h", status="registered")
        ns = store.insert_trials(conn, [_trial(
            method_id="H-REF", candidate_id=regime.BENCH_CANDIDATE, config_digest="ref",
            config_text="params=None\n", start=BENCH_SPAN[0].isoformat(),
            exposure=1.0, turnover=0.0,
            curve_json=_curve(_months(*BENCH_SPAN), 0.08),
        )])
        stamp_provenance(conn, ns, price_fingerprint=prices)
        seen: set[str] = set()
        for mid, cid, annual, cfg in arms:
            if mid not in seen:
                store.add_method(conn, id=mid, name=f"n{mid}", family="momentum",
                                 source_kind="knowledge", hypothesis="h", status="registered")
                seen.add(mid)
            ns = store.insert_trials(conn, [_trial(
                method_id=mid, candidate_id=cid, config_digest=f"d-{cid}", config_text=cfg,
                curve_json=_curve(_months(*DEV_SPAN), annual),
            )])
            stamp_provenance(conn, ns, price_fingerprint=prices)


def _spy_history(first: date, days: int, *, rise_after: int) -> History:
    """A SPY-shaped history that falls for ``rise_after`` sessions and then rises.

    Deterministic and hand-checkable: the gate can only be on once the 200-day mean is behind the
    close, which is exactly what the rise produces and the fall does not.
    """
    dates = np.array(
        [np.datetime64(first + timedelta(days=i)) for i in range(days)], dtype="datetime64[D]"
    )
    t = np.arange(days, dtype=np.float64)
    close = np.where(t < rise_after, 100.0 - 0.05 * t, 100.0 - 0.05 * rise_after + 0.4 * (t - rise_after))
    close = np.maximum(close, 1.0)
    return History(GATE_SYMBOL, dates, close.copy(), close * 1.01, close * 0.99, close,
                   np.full(days, 1e6))


# --------------------------------------------------------------------------- the gap


def test_the_era_slice_is_walkforwards_own_and_is_not_recomputed(conn):
    _lab(conn)
    row = shortfall.resolve_trial(conn, "M0001-A")
    sf = shortfall.measure(conn, row, "2009-2015")
    bench, _n = shortfall.benchmark(conn)
    curve = shortfall.curve_of(row)
    deposits = hardgate.trial_deposits(conn, row, curve)
    mine = wf.measure(curve, sf.era[0], sf.era[1], deposits)
    theirs = wf.measure(bench, sf.era[0], sf.era[1])
    assert sf.mine == pytest.approx(mine.cagr)
    assert sf.theirs == pytest.approx(theirs.cagr)
    assert sf.gap == pytest.approx(mine.cagr - theirs.cagr)
    assert sf.months == mine.months


def test_the_benchmark_row_is_the_hard_gates_own(conn):
    _lab(conn)
    assert shortfall.benchmark(conn)[1] == hardgate.benchmark_n(conn)


def test_the_terms_sum_back_to_the_gap(conn):
    _lab(conn)
    row = shortfall.resolve_trial(conn, "M0001-A")
    sf = shortfall.measure(conn, row, "2009-2015")
    assert sf.gap == pytest.approx(-sf.gate_premium - sf.fees.drag + sf.residual, abs=1e-12)


def test_the_split_sums_back_to_the_residual(conn):
    _lab(conn, arms=(("M0001", "M0001-A", 0.09, GATED_CONFIG),
                     ("M0001", "M0001-B", 0.12, GATED_CONFIG)))
    row = shortfall.resolve_trial(conn, "M0001-A")
    peer = shortfall.resolve_trial(conn, "M0001-B")
    sf = shortfall.measure(conn, row, "2009-2015", against=peer)
    assert sf.against is not None
    assert sf.against.shared + sf.against.own == pytest.approx(sf.residual, abs=1e-12)
    alone = shortfall.measure(conn, peer, "2009-2015")
    assert sf.against.shared == pytest.approx(alone.residual)


# --------------------------------------------------------------------------- what is refused


def test_a_test_window_trial_is_refused_by_name(conn):
    _lab(conn)
    with conn:
        ns = store.insert_trials(conn, [_trial(
            method_id="M0001", candidate_id="M0001-T", config_digest="d-t", window="test",
            start="2015-10-19", end="2026-10-01",
            curve_json=_curve(_months(date(2015, 11, 1), date(2026, 1, 31)), 0.07),
        )])
        stamp_provenance(conn, ns)
    with pytest.raises(store.LabError, match="dev window and nothing else"):
        shortfall.resolve_trial(conn, "M0001-T")


def test_an_against_from_another_method_is_refused(conn):
    _lab(conn, arms=(("M0001", "M0001-A", 0.09, GATED_CONFIG),
                     ("M0002", "M0002-A", 0.12, GATED_CONFIG)))
    row = shortfall.resolve_trial(conn, "M0001-A")
    other = shortfall.resolve_trial(conn, "M0002-A")
    with pytest.raises(store.LabError, match="two different methods share neither"):
        shortfall.measure(conn, row, "2009-2015", against=other)


def test_an_against_on_other_prices_is_refused(conn):
    """D10: a residual split across two price fingerprints is cross-store arithmetic."""
    _lab(conn)
    with conn:
        # M0001 already exists (``_lab`` created it); this is a second arm of it, not a second
        # method, so nothing is added to ``methods`` here.
        ns = store.insert_trials(conn, [_trial(
            method_id="M0001", candidate_id="M0001-B", config_digest="d-b",
            curve_json=_curve(_months(*DEV_SPAN), 0.12),
        )])
        stamp_provenance(conn, ns, price_fingerprint="e" * 64)
    row = shortfall.resolve_trial(conn, "M0001-A")
    other = shortfall.resolve_trial(conn, "M0001-B")
    with pytest.raises(store.LabError, match="D10"):
        shortfall.measure(conn, row, "2009-2015", against=other)


def test_an_arm_cannot_be_its_own_control(conn):
    _lab(conn)
    row = shortfall.resolve_trial(conn, "M0001-A")
    with pytest.raises(store.LabError, match="its own control"):
        shortfall.measure(conn, row, "2009-2015", against=row)


def test_an_unknown_era_names_the_ones_that_exist(conn):
    with pytest.raises(store.LabError, match="2009-2015"):
        shortfall.era_bounds("2016-2020", DEV_SPAN)


def test_whole_is_the_trials_own_window():
    label, lo, hi = shortfall.era_bounds("whole", DEV_SPAN)
    assert (label, lo, hi) == (WHOLE, DEV_SPAN[0], DEV_SPAN[1])


def test_a_store_without_bars_is_refused(tmp_path):
    with pytest.raises(store.LabError, match="bars.csv"):
        shortfall.gate_history(tmp_path)


# --------------------------------------------------------------------------- the gate's shape


def test_the_gate_share_is_measured_with_the_labs_own_trend_rule():
    """A long fall then a long rise: off through the fall, on well into the rise."""
    first = date(2000, 1, 1)
    h = _spy_history(first, 900, rise_after=400)
    window = (first, first + timedelta(days=899))
    early = (first, first + timedelta(days=399))
    late = (first + timedelta(days=700), window[1])
    gate = shortfall.gate_shares(h, window, early)
    assert gate.era == 0.0  # the first 199 bars cannot be read, and the rest are falling
    assert gate.era_sessions == 400
    late_gate = shortfall.gate_shares(h, window, late)
    assert late_gate.era == 1.0
    assert 0.0 < late_gate.whole < 1.0


def test_era_exposure_scales_by_the_gates_own_era_shape():
    gate = shortfall.GateShare(GATE_SYMBOL, GATE_N, 0.711620, 0.805848, 4983, 1710, "s")
    got = shortfall.era_exposure(0.691941, gate, carries_gate=True, store_given=True)
    assert got.basis == shortfall.ERA_BASIS
    assert got.value == pytest.approx(0.691941 * (0.805848 / 0.711620), abs=1e-9)
    assert got.value == pytest.approx(0.7836, abs=5e-4)


def test_without_a_store_the_whole_window_figure_is_used_and_labelled():
    got = shortfall.era_exposure(0.691941, None, carries_gate=True, store_given=False)
    assert got.basis == shortfall.WHOLE_BASIS
    assert got.value == 0.691941
    assert "no --store" in got.why


def test_a_book_with_no_shared_gate_falls_back_and_says_so():
    gate = shortfall.GateShare(GATE_SYMBOL, GATE_N, 0.711620, 0.805848, 4983, 1710, "s")
    got = shortfall.era_exposure(0.915296, gate, carries_gate=False, store_given=True)
    assert got.basis == shortfall.WHOLE_BASIS
    assert "carries no shared" in got.why


def test_a_book_that_held_money_with_the_gate_off_falls_back_and_says_so():
    """M0248-R's shape: exposure 0.915 against a gate that was on 0.712 of the window."""
    gate = shortfall.GateShare(GATE_SYMBOL, GATE_N, 0.711620, 0.805848, 4983, 1710, "s")
    got = shortfall.era_exposure(0.915296, gate, carries_gate=True, store_given=True)
    assert got.basis == shortfall.WHOLE_BASIS
    assert got.fill is not None and got.fill > shortfall.MAX_GATE_FILL
    assert "above the gate's own whole-window on-share" in got.why


# --------------------------------------------------------------------------- the fee model


@pytest.mark.parametrize(
    "month, rate",
    [(0, "0.00722559"), (24, "0.00298494"), (120, "0.00254892"), (236, "0.00249849")],
)
def test_the_fee_model_reproduces_the_measured_per_dollar_rates(month, rate):
    """Measured 2026-10-19 at 30 names on the owner's funding: 0.7226%, 0.2985%, 0.2549%, 0.2498%."""
    assert shortfall.round_trip_rate(month, 30) == Decimal(rate)


def test_the_era_mean_rate_is_the_measured_one():
    """Months 156..237 are 2009-2015 of the dev window; measured 0.251041%."""
    assert shortfall.mean_round_trip_rate(156, 237, 30) == Decimal("0.00251041")


def test_the_rate_divides_by_both_sides_of_the_round_trip():
    """trials.turnover counts buys AND sells (book_runner._turnover), so the rate must too."""
    slot = turnover.slot_usd(turnover.equity_usd(200), 30)
    buy, sell = turnover.round_trip(slot)
    assert shortfall.round_trip_rate(200, 30) == (
        (buy.total + sell.total) / (2 * slot)
    ).quantize(shortfall.RATE_Q)


def test_the_month_offsets_are_the_eras_own():
    fees = shortfall.fee_model(
        15.054823476049172, date(1996, 1, 3), (date(2009, 1, 1), date(2015, 10, 16)),
        30, "test",
    )
    assert (fees.first_month, fees.last_month) == (156, 237)
    assert fees.rate == Decimal("0.00251041")
    assert fees.drag == pytest.approx(0.0378, abs=5e-5)
    assert [n for n, _d in fees.sensitivity] == list(shortfall.SENSITIVITY_NAMES)


def test_the_book_size_is_read_from_the_outermost_top():
    assert shortfall.names_in(GATED_CONFIG) == 30  # not the screen's top=1000
    assert shortfall.names_in(UNGATED_CONFIG) == 20
    assert shortfall.names_in("params=None\n") is None
    assert shortfall.names_in("") is None


def test_an_unreadable_book_size_falls_back_to_the_roster_and_says_so(conn):
    _lab(conn, arms=(("M0001", "M0001-A", 0.09, "params=None\n"),))
    row = shortfall.resolve_trial(conn, "M0001-A")
    sf = shortfall.measure(conn, row, "2009-2015")
    assert sf.fees.names == shortfall.DEFAULT_NAMES == turnover.ROSTER_NAMES
    assert "roster" in sf.fees.names_from
    assert "roster" in shortfall.format_report(sf)


# --------------------------------------------------------------------------- the gate detector


def test_the_gate_is_detected_from_the_recorded_configuration_generically():
    assert shortfall.carries_shared_gate(GATED_CONFIG)
    assert not shortfall.carries_shared_gate(UNGATED_CONFIG)
    timing = "params=BlendParams(parts=(BlendPart(params=TimingParams(hold='SPY',signal='SPY',rule='sma',n=200)),))\n"
    assert shortfall.carries_shared_gate(timing)
    off = timing.replace("rule='sma'", "rule='always'")
    assert not shortfall.carries_shared_gate(off)
    other = "params=FactorParams(rank='momentum',top=20,trend=('QQQ',200))\n"
    assert not shortfall.carries_shared_gate(other)


# --------------------------------------------------------------------------- what it says


def test_the_report_says_what_it_is_and_what_it_assumed(conn):
    _lab(conn)
    row = shortfall.resolve_trial(conn, "M0001-A")
    text = shortfall.format_report(shortfall.measure(conn, row, "2009-2015"))
    assert "attribution under stated assumptions, not an identity" in text
    assert "never named after a cause" in text
    assert "T-bills paid about nothing after 2008" in text
    assert shortfall.WHOLE_BASIS in text  # which exposure figure was used
    assert "Modelled, not recovered" in text


def test_the_pre_2008_cash_caveat_is_carried_per_era(conn):
    _lab(conn)
    row = shortfall.resolve_trial(conn, "M0001-A")
    text = shortfall.format_report(shortfall.measure(conn, row, "1996-2002"))
    assert "T-bills paid a real rate" in text
    assert "LARGER than the truth" in text


def test_the_csv_carries_every_term(conn):
    _lab(conn)
    row = shortfall.resolve_trial(conn, "M0001-A")
    rows = shortfall.csv_rows(shortfall.measure(conn, row, "2009-2015"))
    terms = [r[4] for r in rows[1:]]
    assert terms == ["book_cagr", "spy_tr_cagr", "gap", "gate_premium", "fee_drag",
                     "pool_weighting_residual"]


# --------------------------------------------------------------------------- the pinned headline


def _committed():
    """The committed lab, read-only (no migration, so the file is not dirtied), or None."""
    path = store.COMMITTED_DB
    if not path.is_file():
        return None
    try:
        return store.connect_readonly(path)
    except store.LabError:
        return None


def test_trial_828_decomposes_the_way_it_was_measured():
    """The phase's own headline, pinned on a frozen append-only row.

    No research store, so this is the whole-window-exposure reading: gap -8.24, gate -5.11,
    fees -3.78, residual +0.65. The era-resolved reading -- gate -3.60, residual -0.87 -- needs
    the dev store and is checked by hand in the backtest note, not here.
    """
    c = _committed()
    if c is None:
        pytest.skip("no committed lab database")
    try:
        row = c.execute("SELECT * FROM trials WHERE n = 828").fetchone()
        if row is None or row["candidate_id"] != "M0244-PLACEBO30":
            pytest.skip("trial 828 is not M0244-PLACEBO30 in this lab")
        sf = shortfall.measure(c, row, "2009-2015")
        assert sf.gap == pytest.approx(-0.0824, abs=5e-4)
        assert sf.theirs == pytest.approx(0.16603, abs=5e-5)
        assert sf.exposure.basis == shortfall.WHOLE_BASIS
        assert sf.gate_premium == pytest.approx(0.0511, abs=5e-4)
        assert sf.fees.names == 30
        assert sf.fees.rate == Decimal("0.00251041")
        assert sf.fees.drag == pytest.approx(0.0378, abs=5e-4)
        assert sf.residual == pytest.approx(0.0065, abs=5e-4)
        assert sf.gap == pytest.approx(-sf.gate_premium - sf.fees.drag + sf.residual, abs=1e-12)
        assert sf.warnings == ()  # measured: D10 clean against REF-SPY-HOLD
    finally:
        c.close()


def test_the_era_resolved_reading_of_trial_828_is_the_one_that_retires_the_82():
    """With the gate's measured era shape the residual is -0.87, not +0.65.

    The gate shares are the measured ones (lab/shortfall.py's docstring); only the scaling is
    exercised here, because the store that produced them is gitignored.
    """
    c = _committed()
    if c is None:
        pytest.skip("no committed lab database")
    try:
        row = c.execute("SELECT * FROM trials WHERE n = 828").fetchone()
        if row is None or row["candidate_id"] != "M0244-PLACEBO30":
            pytest.skip("trial 828 is not M0244-PLACEBO30 in this lab")
        gate = shortfall.GateShare(GATE_SYMBOL, GATE_N, 0.711620, 0.805848, 4983, 1710, "measured")
        sf = shortfall.measure(c, row, "2009-2015", gate=gate, store_given=True)
        assert sf.exposure.basis == shortfall.ERA_BASIS
        assert sf.exposure.value == pytest.approx(0.7836, abs=5e-4)
        assert sf.gate_premium == pytest.approx(0.0360, abs=5e-4)
        assert sf.residual == pytest.approx(-0.0087, abs=5e-4)
        assert abs(sf.residual) < 0.01  # pool and weighting together, under one point a year
    finally:
        c.close()
