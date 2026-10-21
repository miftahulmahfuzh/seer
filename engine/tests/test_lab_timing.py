"""When a lead was earned (lab/timing.py): the partition, the shares, and the money behind them.

The rules are tested on synthetic rows in a temp database, so they hold for any input and keep
holding on the day the real lab contains something different. The headline -- M0267's gate arm
against its mirror arm, the case insight 517 was written about -- is pinned against the committed
lab.sqlite, because those rows are frozen and append-only and nothing else would notice if an
unrelated change re-priced the published answer. The committed file is opened read-only (no
migration, so no dirtying) and the pin skips when the rows are absent.

The discipline this module is most concerned with is that *nothing is written*. `lab survivorship`
and `lab costs` are report-shaped and journal on every invocation into an append-only table; this
one must not, on any path, and that is asserted rather than assumed.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import date, timedelta
from decimal import Decimal

import pytest

from labkit import LAB_PRICE_FINGERPRINT, stamp_provenance
from seer_engine.backtest import regime
from seer_engine.lab import hardgate, shortfall, store, timing
from seer_engine.lab import walkforward as wf
from seer_engine.lab.exposure import ERAS
from seer_engine.sim.contributions import OWNER_MONTHLY

BENCH_SPAN = (date(1993, 2, 1), date(2015, 10, 16))
DEV_SPAN = (date(1996, 1, 2), date(2015, 10, 16))
UNIT = 0.5  # 5,000,000 IDR against the 10,000,000 start labkit.stamp_provenance records

CONFIG = (
    "rules=TradeRules(id='monthly-hold-frac-gotrade')\n"
    "allocator=<M0001>\n"
    "params=GestureParams(top=30)\n"
)


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    yield c
    c.close()


# --------------------------------------------------------------------------- fixtures


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


def _curve(months: list[date], annual: float, *, funded: bool = False) -> str:
    """A monthly curve at a flat rate, optionally fed the owner's deposit every month.

    A funded curve opens at ``1 + UNIT`` for the reason ``hardgate.trial_deposits`` gives: the
    starting capital and the first deposit are both already in the opening mark.
    """
    out, v = [], (1.0 + UNIT if funded else 1.0)
    step = (1.0 + annual) ** (1.0 / 12.0)
    for i, d in enumerate(months):
        out.append([d.isoformat(), round(v, 10)])
        v = v * step + (UNIT if funded else 0.0)
        if funded and i == len(months) - 1:
            break
    return json.dumps(out)


def _bent(months: list[date], *, early: float, late: float, turn: date) -> str:
    """A funded curve that grows at ``early`` until ``turn`` and at ``late`` after it."""
    out, v = [], 1.0 + UNIT
    for d in months:
        out.append([d.isoformat(), round(v, 10)])
        rate = early if d <= turn else late
        v = v * (1.0 + rate) ** (1.0 / 12.0) + UNIT
    return json.dumps(out)


def _trial(**kw) -> store.TrialRow:
    base = dict(
        method_id="M0001", candidate_id="M0001-A", config_digest="d1", config_text=CONFIG,
        rules_id="MONTHLY_HOLD", allocator_id="M0001", window="dev",
        start=DEV_SPAN[0].isoformat(), end=DEV_SPAN[1].isoformat(),
        store_fingerprint="399d0d25", git_sha="abc123", run_at="2026-10-20T00:00:00+00:00",
        total_return=3.0, cagr=0.12, max_drawdown=0.11, profit_factor=1.6, trades=250,
        sharpe=0.9, exposure=0.69, turnover=15.0, worst_year=2008, worst_year_return=-0.1,
        spy_tr_return=2.0, spy_tr_cagr=0.08, mar=0.8, failed="", eligible=False, dsr=0.5,
        n_trials_at_run=60, curve_json=_curve(_months(*DEV_SPAN), 0.09),
    )
    base.update(kw)
    return store.TrialRow(**base)


def _fund(conn, n: int, *, mwr: float, spy_mwr: float) -> None:
    """Stamp a trial as funded on the owner's real schedule, the way ``lab run`` does."""
    due = OWNER_MONTHLY.dates_in(DEV_SPAN[0], DEV_SPAN[1])
    store.insert_funding(conn, [store.FundingRow(
        trial_n=n, mwr=mwr, spy_tr_mwr=spy_mwr, deposits_usd=1000.0 * len(due),
        deposits_n=len(due), schedule="+5,000,000 IDR on the 25th of each month",
        measured="2026-10-20T00:00:00+00:00",
    )])


def _lab(conn, *arms, funded=True):
    """The benchmark plus one dev trial per ``(candidate_id, curve_json, mwr[, mar])`` arm."""
    with conn:
        store.add_method(conn, id="H-REF", name="SPY buy and hold", family="reference",
                         source_kind="seed", hypothesis="h", status="registered")
        ns = store.insert_trials(conn, [_trial(
            method_id="H-REF", candidate_id=regime.BENCH_CANDIDATE, config_digest="ref",
            config_text="params=None\n", start=BENCH_SPAN[0].isoformat(), exposure=1.0,
            turnover=0.0, curve_json=_curve(_months(*BENCH_SPAN), 0.08),
        )])
        stamp_provenance(conn, ns, price_fingerprint=LAB_PRICE_FINGERPRINT)
        store.add_method(conn, id="M0001", name="n", family="momentum",
                         source_kind="knowledge", hypothesis="h", status="registered")
        for arm in arms:
            cid, curve_json, mwr = arm[:3]
            ns = store.insert_trials(conn, [_trial(
                candidate_id=cid, config_digest=f"d-{cid}", curve_json=curve_json,
                mar=(arm[3] if len(arm) > 3 else 0.8),
            )])
            stamp_provenance(conn, ns, price_fingerprint=LAB_PRICE_FINGERPRINT,
                             initial_idr=Decimal("10000000"))
            if funded:
                _fund(conn, ns[0], mwr=mwr, spy_mwr=0.08)


def _default(conn, *, annual=0.12, mwr=0.10, funded=True):
    _lab(conn, ("M0001-A", _curve(_months(*DEV_SPAN), annual, funded=funded), mwr), funded=funded)
    return shortfall.resolve_trial(conn, "M0001-A")


# --------------------------------------------------------------------------- the era table


def test_the_partition_drops_the_nested_era_and_keeps_the_rest():
    """2008 sits inside 2003-2008 on purpose, so it cannot be part of a partition."""
    labels = [label for label, _s, _e in timing.PARTITION]
    assert labels == ["1996-2002", "2003-2008", "2009-2015"]
    assert [label for label, _s, _e in timing.NESTED] == ["2008"]
    assert set(timing.PARTITION) | set(timing.NESTED) == set(ERAS)


def test_the_partition_is_contiguous_and_covers_every_era_the_table_names():
    """No gap and no overlap between consecutive eras, which is what makes the shares add up."""
    spans = sorted(((s, e) for _l, s, e in timing.PARTITION))
    for (_s0, e0), (s1, _e1) in zip(spans, spans[1:]):
        assert s1 == e0 + timedelta(days=1)
    assert spans[0][0] == min(s for _l, s, _e in ERAS)
    assert spans[-1][1] == max(e for _l, _s, e in ERAS)


# --------------------------------------------------------------------------- the attribution


def test_the_era_shares_add_back_to_the_whole_windows_lead(conn):
    """The claim the whole report rests on: every month is counted once, and exactly once."""
    row = _default(conn)
    t = timing.measure(conn, row)
    parts = sum(e.edge for e in t.eras if not e.nested) + t.outside
    assert parts == pytest.approx(t.total_edge, abs=1e-12)
    assert sum(e.share for e in t.eras if not e.nested) == pytest.approx(1.0, abs=1e-9)


def test_no_month_is_dropped_at_an_era_boundary(conn):
    """What the slice form gets wrong, and the reason this module sums steps instead.

    ``walkforward.measure`` starts each era at the first curve point *inside* it, so the month
    that straddles a boundary belongs to no slice. Here the months are counted directly.
    """
    row = _default(conn)
    t = timing.measure(conn, row)
    assert sum(e.months for e in t.eras if not e.nested) == t.months


def test_a_month_belongs_to_the_era_it_ends_in(conn):
    """January 2009's return is 2009's, even though its step opens on 2008-12-31."""
    row = _default(conn)
    t = timing.measure(conn, row)
    by_label = {e.label: e for e in t.eras}
    jan09 = [d for d in _months(*DEV_SPAN) if d.year == 2009 and d.month == 1]
    assert jan09 and jan09[0] <= by_label["2009-2015"].end
    assert by_label["2009-2015"].start == date(2009, 1, 1)
    assert by_label["2003-2008"].end == date(2008, 12, 31)


def test_a_front_loaded_lead_is_found_and_a_late_one_is_not(conn):
    """The feature, in one test: same whole-window shape, opposite timing, opposite verdict."""
    months = _months(*DEV_SPAN)
    turn = date(2002, 12, 31)
    _lab(
        conn,
        ("M0001-EARLY", _bent(months, early=0.30, late=0.08, turn=turn), 0.10),
        ("M0001-LATE", _bent(months, early=0.08, late=0.11, turn=turn), 0.10),
        ("M0001-FLAT", _curve(months, 0.08, funded=True), 0.08),
    )
    flat = shortfall.resolve_trial(conn, "M0001-FLAT")
    early = timing.measure(conn, shortfall.resolve_trial(conn, "M0001-EARLY"), flat)
    late = timing.measure(conn, shortfall.resolve_trial(conn, "M0001-LATE"), flat)

    assert early.front_loaded is True
    assert early.half_funded < 0.25
    assert {e.label: e.share for e in early.eras if not e.nested}["1996-2002"] > 0.9

    assert late.front_loaded is False
    assert late.half_funded > 0.5
    assert {e.label: e.share for e in late.eras if not e.nested}["2009-2015"] > 0.3


def test_the_per_era_lead_a_year_is_walkforwards_own_slice(conn):
    """So this report reconciles with lab exposure, lab gate and lab survivorship line for line."""
    row = _default(conn)
    t = timing.measure(conn, row)
    bench = shortfall.curve_of(timing.benchmark_row(conn))
    curve = shortfall.curve_of(row)
    deposits = hardgate.trial_deposits(conn, row, curve)
    for e in t.eras:
        mine = wf.measure(curve, e.start, e.end, deposits)
        theirs = wf.measure(bench, e.start, e.end)
        assert e.lead == pytest.approx(mine.cagr - theirs.cagr)


def test_the_benchmark_row_is_the_hard_gates_own(conn):
    """Three readers of "the benchmark" can never mean three different rows."""
    _default(conn)
    assert int(timing.benchmark_row(conn)["n"]) == hardgate.benchmark_n(conn)
    assert int(timing.benchmark_row(conn)["n"]) == shortfall.benchmark(conn)[1]


# --------------------------------------------------------------------------- the money


def test_money_paid_in_runs_from_the_opening_mark_to_all_of_it(conn):
    """The opening mark is money too, and the last month is 100% by construction."""
    row = _default(conn)
    curve = shortfall.curve_of(row)
    deposits = hardgate.trial_deposits(conn, row, curve)
    paid = timing.paid_in(curve, deposits)
    assert paid[curve[-1][0]] == pytest.approx(1.0)
    assert 0.0 < paid[curve[0][0]] < 0.05
    values = [paid[d] for d, _v in curve]
    assert values == sorted(values)


def test_a_lump_sum_trial_had_all_its_money_from_the_first_day(conn):
    """So its half-lead share is 100% and the question this report asks does not arise."""
    row = _default(conn, funded=False)
    curve = shortfall.curve_of(row)
    paid = timing.paid_in(curve, {})
    assert set(paid.values()) == {1.0}
    t = timing.measure(conn, row)
    assert t.deposits == 0
    assert t.front_loaded is None


def test_the_delivered_lead_against_spy_comes_from_the_trials_own_recorded_columns(conn):
    """No second curve is touched: trial_funding already holds a deposit-matched pair."""
    row = _default(conn, mwr=0.103)
    t = timing.measure(conn, row)
    rec = store.funding_of(conn, int(row["n"]))
    assert t.delivered_lead == pytest.approx(rec["mwr"] - rec["spy_tr_mwr"])
    assert "recorded money-weighted return" in t.delivered_how


def test_the_delivered_lead_against_a_sibling_is_the_two_recorded_returns(conn):
    months = _months(*DEV_SPAN)
    _lab(conn, ("M0001-A", _curve(months, 0.12, funded=True), 0.10),
         ("M0001-B", _curve(months, 0.09, funded=True), 0.085))
    t = timing.measure(conn, shortfall.resolve_trial(conn, "M0001-A"),
                       shortfall.resolve_trial(conn, "M0001-B"))
    assert t.delivered_lead == pytest.approx(0.10 - 0.085)


def test_a_lump_sum_control_leaves_the_delivered_lead_unanswered(conn):
    """Unanswered, with a reason -- never silently reported as zero."""
    months = _months(*DEV_SPAN)
    _lab(conn, ("M0001-A", _curve(months, 0.12, funded=True), 0.10), funded=True)
    with conn:
        ns = store.insert_trials(conn, [_trial(
            candidate_id="M0001-L", config_digest="d-L", curve_json=_curve(months, 0.09),
        )])
        stamp_provenance(conn, ns, price_fingerprint=LAB_PRICE_FINGERPRINT)
    t = timing.measure(conn, shortfall.resolve_trial(conn, "M0001-A"),
                       shortfall.resolve_trial(conn, "M0001-L"))
    assert t.delivered_lead is None
    assert "no money-weighted return" in t.delivered_how


# --------------------------------------------------------------------------- what is refused


def test_a_test_window_trial_is_refused_by_name(conn):
    _default(conn)
    with conn:
        ns = store.insert_trials(conn, [_trial(
            candidate_id="M0001-T", config_digest="d-t", window="test",
            start="2015-10-19", end="2026-10-01",
            curve_json=_curve(_months(date(2015, 11, 1), date(2026, 1, 31)), 0.07),
        )])
        stamp_provenance(conn, ns)
    with pytest.raises(store.LabError, match="dev window and nothing else"):
        shortfall.resolve_trial(conn, "M0001-T")


def test_a_trial_cannot_be_its_own_control(conn):
    row = _default(conn)
    with pytest.raises(store.LabError, match="cannot be its own control"):
        timing.measure(conn, row, row)


def test_too_few_shared_months_is_refused_rather_than_attributed(conn):
    """Two eras of three months each would give shares that mean nothing."""
    _default(conn, funded=False)
    months = _months(date(2014, 1, 1), date(2015, 10, 16))
    with conn:
        ns = store.insert_trials(conn, [_trial(
            candidate_id="M0001-SHORT", config_digest="d-short",
            start=months[0].isoformat(), curve_json=_curve(months, 0.12),
        )])
        stamp_provenance(conn, ns, price_fingerprint=LAB_PRICE_FINGERPRINT)
    row = shortfall.resolve_trial(conn, "M0001-SHORT")
    with pytest.raises(store.LabError, match="are needed"):
        timing.measure(conn, row)


# --------------------------------------------------------------------------- the sweep


def test_the_sweep_skips_lump_sum_trials_by_name(conn):
    """Counting them as "not front-loaded" would pad the clean half with trials never asked."""
    months = _months(*DEV_SPAN)
    _lab(conn, ("M0001-A", _curve(months, 0.12, funded=True), 0.10))
    with conn:
        ns = store.insert_trials(conn, [_trial(
            candidate_id="M0001-L", config_digest="d-L", curve_json=_curve(months, 0.12),
        )])
        stamp_provenance(conn, ns, price_fingerprint=LAB_PRICE_FINGERPRINT)
    s = timing.sweep(conn)
    assert [t.candidate_id for t in s.scored] == ["M0001-A"]
    assert [sk.candidate_id for sk in s.skipped] == ["M0001-L"]
    assert "lump-sum" in s.skipped[0].reason


def test_the_sweep_skips_a_trial_with_no_lead_to_attribute(conn):
    months = _months(*DEV_SPAN)
    _lab(conn, ("M0001-A", _curve(months, 0.04, funded=True), 0.03))
    s = timing.sweep(conn)
    assert s.scored == ()
    assert "no lead over the benchmark" in s.skipped[0].reason


def test_the_sweeps_floor_band_re_counts_the_same_trials(conn):
    """The band exists so the floor is visibly not what the answer rests on."""
    months = _months(*DEV_SPAN)
    _lab(conn, ("M0001-A", _bent(months, early=0.30, late=0.08, turn=date(2002, 12, 31)), 0.10))
    s = timing.sweep(conn)
    assert [floor for floor, _b in s.floors] == list(timing.FLOORS)
    assert s.floors[0][1].trials >= s.floors[-1][1].trials
    assert s.band.under_bar == len(s.flagged)


def test_the_sweep_names_one_headline_arm_per_method(conn):
    months = _months(*DEV_SPAN)
    _lab(conn, ("M0001-A", _curve(months, 0.12, funded=True), 0.10, 0.8),
         ("M0001-B", _curve(months, 0.14, funded=True), 0.11, 9.0))
    s = timing.sweep(conn)
    assert len(s.methods) == 1
    assert s.methods[0][1].candidate_id == "M0001-B"


# --------------------------------------------------------------------------- nothing is written


def test_measuring_and_sweeping_write_nothing_at_all(conn):
    """`lab survivorship` and `lab costs` journal on every run. This must not, on any path."""
    months = _months(*DEV_SPAN)
    _lab(conn, ("M0001-A", _bent(months, early=0.30, late=0.08, turn=date(2002, 12, 31)), 0.10))
    tables = ("trials", "trial_moments", "trial_funding", "trial_provenance", "insights",
              "method_folds", "method_amendments", "methods", "ideas_seen")
    before = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}
    looks = store.test_looks(conn)

    report = timing.measure(conn, shortfall.resolve_trial(conn, "M0001-A"))
    timing.format_report(report)
    timing.format_sweep(timing.sweep(conn))

    after = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}
    assert after == before
    assert store.test_looks(conn) == looks


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


def _m0267(c):
    g = c.execute("SELECT * FROM trials WHERE candidate_id = 'M0267-GATE'").fetchone()
    m = c.execute("SELECT * FROM trials WHERE candidate_id = 'M0267-MIRROR'").fetchone()
    return g, m


def test_m0267_shows_its_lead_was_earned_in_the_dot_com_crash():
    """The case insight 517 was written about, pinned on frozen append-only rows.

    4.84 points a year on the prices, 1.03 to the owner's money, and the reason: the first era
    earned more than the whole lead and half of it was in by February 2001, when a eleventh of
    his money had arrived.
    """
    c = _committed()
    if c is None:
        pytest.skip("no committed lab database")
    try:
        g, m = _m0267(c)
        if g is None or m is None:
            pytest.skip("M0267 is not in this lab")
        t = timing.measure(c, g, m)
        assert t.paper_lead == pytest.approx(0.0483, abs=5e-4)
        assert t.delivered_lead == pytest.approx(0.0103, abs=5e-4)
        assert t.delivered_fraction == pytest.approx(0.213, abs=5e-3)

        by = {e.label: e for e in t.eras}
        assert by["1996-2002"].share > 1.0          # more than the whole lead
        assert by["2003-2008"].share < 0.0
        assert abs(by["2009-2015"].share) < 0.1
        assert sum(e.edge for e in t.eras if not e.nested) == pytest.approx(t.total_edge, abs=1e-12)

        assert t.half_date == date(2001, 2, 28)
        assert t.half_funded == pytest.approx(0.089, abs=5e-3)
        assert t.front_loaded is True
        assert by["1996-2002"].funded == pytest.approx(0.203, abs=5e-3)
    finally:
        c.close()


def test_m0267s_first_era_share_survives_the_boundary_month_the_slice_form_drops():
    """The 2009-2015 figure moves by 6 points on one month, which is why steps are summed.

    Measured: the stepwise share of the lead earned in 2009-2015 is about -2.8%, and the slice
    form -- which opens the era at its first interior curve point and so drops January 2009 --
    reads +4.1%. The month is real and belongs to 2009.
    """
    c = _committed()
    if c is None:
        pytest.skip("no committed lab database")
    try:
        g, m = _m0267(c)
        if g is None or m is None:
            pytest.skip("M0267 is not in this lab")
        t = timing.measure(c, g, m)
        by = {e.label: e for e in t.eras}
        assert by["2009-2015"].edge < 0 < by["2009-2015"].lead
        assert by["2009-2015"].start == date(2009, 1, 1)
    finally:
        c.close()


def test_the_report_says_when_the_lead_was_earned_in_words():
    c = _committed()
    if c is None:
        pytest.skip("no committed lab database")
    try:
        g, m = _m0267(c)
        if g is None or m is None:
            pytest.skip("M0267 is not in this lab")
        text = timing.format_report(timing.measure(c, g, m))
        assert "Half of the lead had been earned by 2001-02-28" in text
        assert "8.9% of the money had arrived" in text
        assert "21.3% of the paper lead" in text
        assert "1996-2002" in text and "2009-2015" in text
    finally:
        c.close()


def test_the_dataclasses_are_values(conn):
    """Frozen, so a report cannot be edited after it is measured."""
    row = _default(conn)
    t = timing.measure(conn, row)
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.paper_lead = 1.0  # type: ignore[misc]


# --------------------------------------------------------------------------- the command


def _args(argv: list[str]):
    """``lab <argv>`` parsed by the real parser, so the positional wiring is exercised."""
    import argparse

    from seer_engine.commands import lab as lab_cmd

    p = argparse.ArgumentParser(prog="lab")
    lab_cmd.add_arguments(p)
    return p.parse_args(argv)


def test_all_reads_every_positional_as_a_method_id(conn, capsys):
    """`lab timing --all M0001` must sweep M0001, not every method in the lab.

    argparse fills the optional `trial` positional first, so without the handler's fold the
    method id would land in `trial` and the sweep would silently widen to the whole catalogue.
    """
    from seer_engine.commands import lab as lab_cmd

    months = _months(*DEV_SPAN)
    _lab(conn, ("M0001-A", _curve(months, 0.12, funded=True), 0.10))
    with conn:
        store.add_method(conn, id="M0002", name="other", family="momentum",
                         source_kind="knowledge", hypothesis="h", status="registered")
        ns = store.insert_trials(conn, [_trial(
            method_id="M0002", candidate_id="M0002-A", config_digest="d-2",
            curve_json=_curve(months, 0.13, funded=True),
        )])
        stamp_provenance(conn, ns, price_fingerprint=LAB_PRICE_FINGERPRINT)
        _fund(conn, ns[0], mwr=0.11, spy_mwr=0.08)

    args = _args(["timing", "--all", "M0002"])
    assert args.trial == "M0002"  # argparse really does put it here
    assert lab_cmd._timing(conn, args) == 0
    text = capsys.readouterr().out
    assert "M0002-A" in text
    assert "M0001-A" not in text


def test_all_and_against_cannot_be_combined(conn):
    from seer_engine.commands import lab as lab_cmd

    _default(conn)
    with pytest.raises(store.LabError, match="cannot be combined"):
        lab_cmd._timing(conn, _args(["timing", "--all", "--against", "M0001-A"]))
