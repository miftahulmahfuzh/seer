"""What a timing rule knows apart from what its habits cost (lab/dressing.py).

The rules are tested on synthetic rows in a temp database, so they hold for any input and keep
holding on the day the real lab contains something different. The three answers the lab has
already derived **by hand** -- M0254's 0.682 and 0.701, M0265's split, and M0267's opinion against
its toll -- are pinned against the committed lab.sqlite, because those rows are frozen and
append-only and nothing else would notice if an unrelated change re-priced a published number.
The committed file is opened read-only (no migration, so no dirtying) and every pin skips when
the rows are absent.

Two disciplines this module is most concerned with:

- **nothing is written.** `lab survivorship` and `lab costs` journal on every invocation into an
  append-only table whose triggers make the row permanent; insight 500 is a permanent duplicate
  of 499 from exactly that. This report must not, on any path, and that is asserted rather than
  assumed.
- **the money column is the recorded one.** The report recomputes the money-weighted return from
  the recorded monthly curve, so that a synthetic endpoint -- which has no `trial_funding` row --
  is measured by the same path as the arms it is subtracted from. A test checks that
  recomputation against every funded dev trial's recorded `trial_funding.mwr`, because a
  decomposition built on a reconstruction nobody checked is not a measurement.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal

import pytest

from labkit import LAB_PRICE_FINGERPRINT, stamp_provenance
from seer_engine.backtest import regime
from seer_engine.lab import control_shape as cs
from seer_engine.lab import dressing, store
from seer_engine.sim.contributions import OWNER_MONTHLY

BENCH_SPAN = (date(1993, 2, 1), date(2015, 10, 16))
DEV_SPAN = (date(1996, 1, 2), date(2015, 10, 16))
UNIT = 0.5  # 5,000,000 IDR against the 10,000,000 start labkit.stamp_provenance records


def _config(**params) -> str:
    """A ``config_text`` in the exact shape ``method.config_text`` writes."""
    body = ",".join(f"{k}={v}" for k, v in params.items())
    return (
        "rules=TradeRules(id='monthly-hold-frac-gotrade',resize=True)\n"
        "allocator=<M0001>\n"
        f"params=FakeParams({body})\n"
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


def _curve(months: list[date], annual: float, *, funded: bool = True) -> str:
    """A monthly curve at a flat rate, fed the owner's deposit every month by default.

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


def _trial(**kw) -> store.TrialRow:
    base = dict(
        method_id="M0001", candidate_id="M0001-A", config_digest="d1",
        config_text=_config(mirror="False"),
        rules_id="MONTHLY_HOLD", allocator_id="M0001", window="dev",
        start=DEV_SPAN[0].isoformat(), end=DEV_SPAN[1].isoformat(),
        store_fingerprint="399d0d25", git_sha="abc123", run_at="2026-10-21T00:00:00+00:00",
        total_return=3.0, cagr=0.12, max_drawdown=0.11, profit_factor=1.6, trades=10,
        sharpe=0.9, exposure=0.69, turnover=2.0, worst_year=2008, worst_year_return=-0.1,
        spy_tr_return=2.0, spy_tr_cagr=0.08, mar=0.8, failed="", eligible=False, dsr=0.5,
        n_trials_at_run=60, curve_json=_curve(_months(*DEV_SPAN), 0.09),
    )
    base.update(kw)
    return store.TrialRow(**base)


def _fund(conn, n: int, span=DEV_SPAN) -> None:
    due = OWNER_MONTHLY.dates_in(span[0], span[1])
    store.insert_funding(conn, [store.FundingRow(
        trial_n=n, mwr=0.07, spy_tr_mwr=0.08, deposits_usd=1000.0 * len(due),
        deposits_n=len(due), schedule="+5,000,000 IDR on the 25th of each month",
        measured="2026-10-21T00:00:00+00:00",
    )])


def _arm(conn, cid: str, annual: float, config: str, *, exposure=0.69, turnover=2.0,
         trades=10, funded=True, span=DEV_SPAN, method_id=None) -> int:
    with conn:
        ns = store.insert_trials(conn, [_trial(
            method_id=method_id or cid.split("-")[0],
            candidate_id=cid, config_digest=f"d-{cid}", config_text=config,
            start=span[0].isoformat(), end=span[1].isoformat(),
            exposure=exposure, turnover=turnover, trades=trades,
            curve_json=_curve(_months(*span), annual, funded=funded),
        )])
        stamp_provenance(conn, ns, price_fingerprint=LAB_PRICE_FINGERPRINT,
                         initial_idr=Decimal("10000000"))
        if funded:
            _fund(conn, ns[0], span)
    return ns[0]


def _method(conn, mid="M0001", parent=None) -> None:
    with conn:
        store.add_method(conn, id=mid, name="n", family="f", source_kind="knowledge",
                         hypothesis="h", status="registered", parent_id=parent)


def _pair(conn, *, straight=0.12, flipped=0.06, hold=0.14) -> dressing.Decomposition:
    """The canonical fixture: a straight arm, its mirror, and an always-invested endpoint."""
    _method(conn)
    _arm(conn, "M0001-A", straight, _config(mirror="False"))
    _arm(conn, "M0001-MIRROR", flipped, _config(mirror="True"))
    _arm(conn, "M0001-HOLD", hold, _config(mirror="False", floor="1.0"),
         exposure=0.995, turnover=0.07, trades=0)
    pairing, rows = dressing.resolve_pairing(conn, "M0001")
    return dressing.measure(conn, pairing, rows)


# ----------------------------------------------------------------- reading a configuration


def test_a_recorded_configuration_reads_as_its_fields():
    got = dressing.fields_of(_config(floor="0.5", mirror="True"))
    assert got["floor"] == "0.5"
    assert got["mirror"] == "True"
    assert got["#params"] == "FakeParams"
    assert got["#allocator"] == "<M0001>"


def test_a_nested_params_object_stays_one_field():
    """``inner=`` is the lab's commonest field and it carries commas. Splitting it invents two."""
    got = dressing.fields_of(
        "rules=R(a=1)\nallocator=<M0202>\nparams=Outer(inner=Inner(a=1,b=2),top=20)\n"
    )
    assert got["inner"] == "Inner(a=1,b=2)"
    assert got["top"] == "20"


def test_two_arms_differing_only_in_a_mirror_flag_are_a_pair():
    a, b = dressing.fields_of(_config(mirror="False")), dressing.fields_of(_config(mirror="True"))
    assert dressing.reversal_between(a, b) == ("mirror", "False", "True")


def test_two_arms_differing_in_a_dose_are_not_a_pair():
    """The commonest thing a method varies, and the commonest way a detector could go wrong."""
    a = dressing.fields_of(_config(mirror="False", floor="0.5"))
    b = dressing.fields_of(_config(mirror="False", floor="0.0"))
    assert dressing.reversal_between(a, b) is None


def test_two_arms_differing_in_a_mirror_flag_AND_a_dose_are_not_a_pair():
    """A pair matched on everything but one setting is the whole claim; two settings is not."""
    a = dressing.fields_of(_config(mirror="False", floor="0.5"))
    b = dressing.fields_of(_config(mirror="True", floor="0.0"))
    assert dressing.reversal_between(a, b) is None


def test_an_antonym_value_pair_is_a_pair_in_either_direction():
    a = dressing.fields_of(_config(side="'high'"))
    b = dressing.fields_of(_config(side="'low'"))
    assert dressing.reversal_between(a, b) is not None
    assert dressing.reversal_between(b, a) is not None


def test_a_different_way_of_reading_a_signal_is_not_a_reversal():
    """``absolute`` against ``relative`` was met in the measurement and deliberately rejected."""
    a = dressing.fields_of(_config(mode="'absolute'"))
    b = dressing.fields_of(_config(mode="'relative'"))
    assert dressing.reversal_between(a, b) is None


def test_an_arm_whose_allocator_differs_is_not_a_pair():
    """``#allocator`` is kept whole so a re-implemented arm can never read as differing in nothing."""
    a = dressing.fields_of(_config(mirror="False"))
    b = dressing.fields_of(_config(mirror="False").replace("<M0001>", "<M0001-A1>"))
    assert dressing.reversal_between(a, b) is None


# --------------------------------------------------------------------------- orientation


class _Arm:
    def __init__(self, cid, rationale):
        self.id, self.rationale = cid, rationale


def test_role_of_names_the_reversed_arm_when_it_can():
    arms = {
        "A": _Arm("A", "The 20 biggest winners, behind the gate"),
        "B": _Arm("B", "Control: the losing end of the same screen, expected to trail"),
    }
    assert cs.role_of(arms["B"]) == cs.ROLE_CONTROL
    assert dressing.orient("A", "B", "side", "'high'", "'low'", arms) == ("A", "B", "role")


def test_the_flag_decides_when_role_of_cannot():
    """Every mirror in the lab opens `Falsification:`, which role_of reads as a treatment."""
    arms = {
        "A": _Arm("A", "The book at floor 50%"),
        "B": _Arm("B", "Falsification: floor 50% reversed -- the same weights, flipped"),
    }
    assert cs.role_of(arms["B"]) == cs.ROLE_TREATMENT  # the reason this rung has to exist
    assert dressing.orient("A", "B", "mirror", "False", "True", arms) == ("A", "B", "flag")
    assert dressing.orient("B", "A", "mirror", "True", "False", arms) == ("A", "B", "flag")


def test_a_mirror_mode_value_decides_when_there_is_no_flag():
    arms = {"A": _Arm("A", "the ladder"), "B": _Arm("B", "the other way up")}
    assert dressing.orient("A", "B", "mode", "'ladder'", "'mirror'", arms) == ("A", "B", "value")


def test_prose_is_the_last_rung_and_structure_wins_over_it():
    """An arm whose prose and whose structure disagree is decided by the structure."""
    arms = {
        "A": _Arm("A", "Falsification: this one says it is the mirror"),
        "B": _Arm("B", "the book"),
    }
    # the flag says B is the reversal; the prose says A is. The flag rung is asked first.
    assert dressing.orient("A", "B", "mirror", "False", "True", arms) == ("A", "B", "flag")
    # with nothing structural to go on, the prose decides and says so
    assert dressing.orient("A", "B", "side", "'x'", "'y'", arms) == ("B", "A", "prose")


def test_an_undecidable_pair_says_unresolved_rather_than_guessing_quietly():
    arms = {"A": _Arm("A", "one book"), "B": _Arm("B", "another book")}
    assert dressing.orient("A", "B", "side", "'x'", "'y'", arms)[2] == dressing.UNRESOLVED


def test_an_unresolved_orientation_is_warned_about_on_the_report(conn):
    _method(conn)
    _arm(conn, "M0001-HIGH", 0.12, _config(side="'high'"))
    _arm(conn, "M0001-LOW", 0.06, _config(side="'low'"))
    pairing, rows = dressing.resolve_pairing(conn, "M0001")
    assert pairing.rung == dressing.UNRESOLVED  # no method file, so no rationale to read
    got = dressing.measure(conn, pairing, rows)
    assert any("the wrong way round" in w for w in got.warnings)


# --------------------------------------------------------------------------- the endpoint


def test_the_endpoint_is_the_always_invested_opinion_free_arm(conn):
    got = _pair(conn)
    assert got.endpoint is not None
    assert got.endpoint.arms == ("M0001-HOLD",)
    assert got.endpoint.rung == dressing.OWN_HOLD


def test_an_arm_that_barely_trades_but_sits_in_cash_is_not_an_endpoint(conn):
    """Both bars are mandatory. ``M0005-ALL`` turns over 0.111 and is in the market 1.8% of the time."""
    _method(conn)
    _arm(conn, "M0001-A", 0.12, _config(mirror="False"))
    _arm(conn, "M0001-MIRROR", 0.06, _config(mirror="True"))
    _arm(conn, "M0001-CASHY", 0.14, _config(mirror="False", floor="1.0"),
         exposure=0.02, turnover=0.07, trades=0)
    pairing, rows = dressing.resolve_pairing(conn, "M0001")
    assert dressing.measure(conn, pairing, rows).endpoint is None


def test_a_method_with_no_always_invested_arm_is_unpriced_and_not_an_error(conn):
    _method(conn)
    _arm(conn, "M0001-A", 0.12, _config(mirror="False"))
    _arm(conn, "M0001-MIRROR", 0.06, _config(mirror="True"))
    pairing, rows = dressing.resolve_pairing(conn, "M0001")
    got = dressing.measure(conn, pairing, rows)
    assert got.endpoint is None
    assert got.verdict == dressing.UNPRICED
    assert got.at(dressing.PAPER, "whole").direction is not None  # the opinion is still measured
    assert any("cannot be priced" in w for w in got.warnings)


def test_several_always_invested_arms_are_blended(conn):
    """Several single-asset holds are the EXTREMES of a switch, never its neutral point."""
    _method(conn)
    _arm(conn, "M0001-A", 0.12, _config(mirror="False"))
    _arm(conn, "M0001-MIRROR", 0.06, _config(mirror="True"))
    _arm(conn, "M0001-SPY", 0.08, _config(fixed="'SPY'"), exposure=0.99, turnover=0.1, trades=0)
    _arm(conn, "M0001-QQQ", 0.16, _config(fixed="'QQQ'"), exposure=0.99, turnover=0.1, trades=0)
    pairing, rows = dressing.resolve_pairing(conn, "M0001")
    got = dressing.measure(conn, pairing, rows)
    assert got.endpoint is not None
    assert got.endpoint.rung == dressing.BLEND
    assert got.endpoint.arms == ("M0001-QQQ", "M0001-SPY")
    middle = got.at(dressing.PAPER, "whole").endpoint
    assert 0.08 < middle < 0.16  # between the two it blends, as a half-and-half must be


def test_a_recorded_blend_is_used_instead_of_the_synthetic_one(conn):
    """When the method already registered the neutral book, that recorded arm is the endpoint."""
    _method(conn)
    _arm(conn, "M0001-A", 0.12, _config(mirror="False"))
    _arm(conn, "M0001-MIRROR", 0.06, _config(mirror="True"))
    _arm(conn, "M0001-SPY", 0.08, _config(fixed="'SPY'"), exposure=0.99, turnover=0.1, trades=0)
    _arm(conn, "M0001-QQQ", 0.16, _config(fixed="'QQQ'"), exposure=0.99, turnover=0.1, trades=0)
    # a flat 12% book sits almost exactly where a rebalanced half of 8% and 16% does
    _arm(conn, "M0001-BLEND", 0.1196, _config(fixed="None"), exposure=0.99, turnover=0.1, trades=0)
    pairing, rows = dressing.resolve_pairing(conn, "M0001")
    got = dressing.measure(conn, pairing, rows)
    assert got.endpoint is not None
    assert got.endpoint.arms == ("M0001-BLEND",)
    assert got.endpoint.rung == dressing.OWN_HOLD


def test_an_exactly_matching_window_beats_a_sliced_one_in_the_pairs_own_method(conn):
    """The preference that reproduces the lab's published 0.682; M0254's own file argues it."""
    _method(conn)
    _method(conn, "M0002", parent="M0001")
    _arm(conn, "M0001-A", 0.12, _config(mirror="False"))
    _arm(conn, "M0001-MIRROR", 0.06, _config(mirror="True"))
    _arm(conn, "M0001-HOLD", 0.14, _config(floor="1.0"), exposure=0.995, turnover=0.07,
         trades=0, span=(date(1993, 2, 1), DEV_SPAN[1]))      # covers, but starts earlier
    _arm(conn, "M0002-HOLD", 0.20, _config(floor="1.0"), exposure=0.995, turnover=0.07,
         trades=0, method_id="M0002")
    pairing, rows = dressing.resolve_pairing(conn, "M0001")
    got = dressing.measure(conn, pairing, rows)
    assert got.endpoint is not None
    assert got.endpoint.arms == ("M0002-HOLD",)              # the child's, window-matched
    assert got.endpoint.rung == dressing.LINEAGE_HOLD


def test_the_lineage_walk_reaches_children_as_well_as_parents(conn):
    _method(conn)
    _method(conn, "M0002", parent="M0001")
    _method(conn, "M0003", parent="M0002")
    assert dressing.lineage(conn, "M0001") == ("M0001", "M0002", "M0003")
    assert dressing.lineage(conn, "M0003") == ("M0001", "M0002", "M0003")


def test_an_endpoint_that_stops_before_the_pair_does_is_refused(conn):
    """Extrapolating an endpoint would be inventing a return, so coverage is mandatory."""
    _method(conn)
    _arm(conn, "M0001-A", 0.12, _config(mirror="False"))
    _arm(conn, "M0001-MIRROR", 0.06, _config(mirror="True"))
    _arm(conn, "M0001-HOLD", 0.14, _config(floor="1.0"), exposure=0.995, turnover=0.07,
         trades=0, span=(DEV_SPAN[0], date(2008, 12, 31)))
    pairing, rows = dressing.resolve_pairing(conn, "M0001")
    assert dressing.measure(conn, pairing, rows).endpoint is None


# --------------------------------------------------------------------------- the arithmetic


def test_the_direction_is_half_the_gap_between_the_arms(conn):
    """One-sided, because the gap counts the opinion twice: obeying it and disobeying it."""
    got = _pair(conn, straight=0.12, flipped=0.06)
    s = got.at(dressing.PAPER, "whole")
    assert s.direction == pytest.approx((s.straight - s.reversed_) / 2)
    assert s.direction == pytest.approx(0.03, abs=1e-4)


def test_the_toll_is_the_midpoint_against_the_always_invested_arm(conn):
    got = _pair(conn, straight=0.12, flipped=0.06, hold=0.14)
    s = got.at(dressing.PAPER, "whole")
    assert s.toll == pytest.approx(0.09 - 0.14, abs=1e-4)
    assert s.ratio == pytest.approx(0.03 / 0.05, abs=1e-3)


def test_dilution_halves_both_halves_so_the_ratio_is_invariant(conn):
    """M0254's whole finding, as arithmetic: no gentler setting of a dial can rescue a loser.

    Two doses of the same rule are recorded -- one leaning twice as hard as the other, both
    against the same always-invested arm -- and both are decomposed. The gap between the arms
    halves and the drop from the endpoint halves with it, so the ratio does not move. That is
    why a ratio below one closes a question instead of inviting a gentler setting.
    """
    _method(conn)
    _arm(conn, "M0001-FULL", 0.14, _config(lean="1.0", mirror="False"))
    _arm(conn, "M0001-FULL-M", 0.06, _config(lean="1.0", mirror="True"))
    _arm(conn, "M0001-HALF", 0.15, _config(lean="0.5", mirror="False"))
    _arm(conn, "M0001-HALF-M", 0.11, _config(lean="0.5", mirror="True"))
    _arm(conn, "M0001-HOLD", 0.16, _config(lean="0.0", mirror="False"),
         exposure=0.995, turnover=0.07, trades=0)
    found = {d.pairing.straight_id: d for d in dressing.survey(conn).found}
    full = found["M0001-FULL"].at(dressing.PAPER, "whole")
    half = found["M0001-HALF"].at(dressing.PAPER, "whole")
    assert full.direction == pytest.approx(2 * half.direction, rel=0.02)
    assert full.toll == pytest.approx(2 * half.toll, rel=0.02)
    assert full.ratio == pytest.approx(half.ratio, rel=0.02)
    assert full.ratio < dressing.RATIO_BAR and half.ratio < dressing.RATIO_BAR


def test_a_rule_whose_opinion_outruns_its_habits_is_badly_dressed(conn):
    got = _pair(conn, straight=0.16, flipped=0.04, hold=0.11)
    assert got.at(dressing.PAPER, "whole").ratio > dressing.RATIO_BAR
    assert got.verdict == dressing.BADLY_DRESSED


def test_a_rule_whose_habits_outrun_its_opinion_is_dead(conn):
    got = _pair(conn, straight=0.12, flipped=0.10, hold=0.16)
    assert got.at(dressing.PAPER, "whole").ratio < dressing.RATIO_BAR
    assert got.verdict == dressing.DEAD


def test_a_pair_whose_arms_agree_has_no_opinion_to_dress(conn):
    got = _pair(conn, straight=0.12, flipped=0.12, hold=0.16)
    assert got.verdict == dressing.NO_SIGNAL


def test_a_mirror_that_beats_its_straight_arm_reads_backwards(conn):
    got = _pair(conn, straight=0.06, flipped=0.12, hold=0.16)
    assert got.verdict == dressing.BACKWARDS


def test_an_arrangement_that_beats_being_invested_is_a_free_chassis(conn):
    got = _pair(conn, straight=0.16, flipped=0.10, hold=0.09)
    assert got.at(dressing.PAPER, "whole").toll > 0
    assert got.verdict == dressing.FREE


def test_the_verdict_is_split_when_the_two_columns_disagree(conn):
    """M0267 reads 3.47 on the prices and 0.98 on the money. Neither word alone is the answer."""
    s = dressing.Split(dressing.PAPER, "whole", DEV_SPAN[0], DEV_SPAN[1], 0.16, 0.04, 0.11)
    m = dressing.Split(dressing.MONEY, "whole", DEV_SPAN[0], DEV_SPAN[1], 0.12, 0.10, 0.16)
    assert s.verdict == dressing.BADLY_DRESSED
    assert m.verdict == dressing.DEAD
    d = dressing.Decomposition(
        pairing=dressing.Pairing("M0001", "A", "B", "mirror", "False", "True", "flag"),
        straight_n=1, reversed_n=2, window=DEV_SPAN, months=100, endpoint=None,
        splits=(s, m), trades=(5, 5), turnover=(1.0, 1.0), exposure=(0.9, 0.9),
        deposits=10, warnings=(),
    )
    assert d.verdict == dressing.SPLIT


def test_a_ratio_is_never_taken_across_the_two_columns(conn):
    """The mistake insight 511's 0.33 made. Each Split owns one column and both of its halves."""
    got = _pair(conn)
    for s in got.splits:
        if s.ratio is None:
            continue
        assert s.ratio == pytest.approx(s.direction / abs(s.toll))
        assert s.column in dressing.COLUMNS


def test_both_spans_are_reported_and_the_era_comes_from_the_shared_table(conn):
    got = _pair(conn)
    spans = {s.span for s in got.splits}
    assert spans == {"whole", dressing.ERA_LABEL}
    from seer_engine.lab.exposure import ERAS
    assert dressing.ERA_LABEL in {label for label, _s, _e in ERAS}


def test_a_pair_with_too_few_shared_months_is_refused_by_name(conn):
    _method(conn)
    short = (date(2014, 1, 2), date(2015, 1, 31))
    _arm(conn, "M0001-A", 0.12, _config(mirror="False"), span=short)
    _arm(conn, "M0001-MIRROR", 0.06, _config(mirror="True"), span=short)
    pairing, rows = dressing.resolve_pairing(conn, "M0001")
    with pytest.raises(store.LabError, match="are needed before a decomposition"):
        dressing.measure(conn, pairing, rows)


def test_a_cross_store_pair_is_refused_rather_than_reported(conn):
    """Hard gate D10: two curves are comparable only on the same recorded price fingerprint."""
    _method(conn)
    _arm(conn, "M0001-A", 0.12, _config(mirror="False"))
    with conn:
        ns = store.insert_trials(conn, [_trial(
            candidate_id="M0001-MIRROR", config_digest="d-m", config_text=_config(mirror="True"),
            curve_json=_curve(_months(*DEV_SPAN), 0.06),
        )])
        stamp_provenance(conn, ns, price_fingerprint="a-different-store",
                         initial_idr=Decimal("10000000"))
        _fund(conn, ns[0])
    pairing, rows = dressing.resolve_pairing(conn, "M0001")
    with pytest.raises(store.LabError, match="not comparable"):
        dressing.measure(conn, pairing, rows)


# --------------------------------------------------------------------- the flip count


def test_every_toll_is_printed_with_the_flip_count_beside_it(conn):
    """A chassis toll is a per-flip price. Quoting one without the count mis-prices the next rule."""
    got = _pair(conn)
    text = dressing.format_report(got)
    assert "what habits cost" in text
    assert "closed round trips" in text
    assert "turnover a year" in text
    assert "PER-FLIP price" in text


def test_a_book_that_never_closes_out_still_has_a_churn_price(conn):
    """M0254's floor arms record ``trades 0`` and turn over 2.8. A per-flip price would divide by 0."""
    _method(conn)
    _arm(conn, "M0001-A", 0.12, _config(mirror="False"), trades=0, turnover=2.8)
    _arm(conn, "M0001-MIRROR", 0.06, _config(mirror="True"), trades=0, turnover=2.7)
    _arm(conn, "M0001-HOLD", 0.14, _config(floor="1.0"), exposure=0.995, turnover=0.07, trades=0)
    pairing, rows = dressing.resolve_pairing(conn, "M0001")
    got = dressing.measure(conn, pairing, rows)
    assert got.flips == 0
    assert got.per_flip(dressing.PAPER) is None
    assert got.per_turnover(dressing.PAPER) is not None
    assert "not that it is inert" in dressing.format_report(got)


# --------------------------------------------------------------------------- the sweep


def test_the_sweep_finds_the_pair_and_names_the_method(conn):
    _pair(conn)
    s = dressing.survey(conn)
    assert [d.pairing.straight_id for d in s.found] == ["M0001-A"]
    assert s.priced and not s.unpriced


def test_the_sweep_separates_the_priced_pairs_from_the_unpriced_ones(conn):
    _method(conn)
    _method(conn, "M0002")
    _arm(conn, "M0001-A", 0.12, _config(mirror="False"))
    _arm(conn, "M0001-MIRROR", 0.06, _config(mirror="True"))
    _arm(conn, "M0001-HOLD", 0.14, _config(floor="1.0"), exposure=0.995, turnover=0.07, trades=0)
    _arm(conn, "M0002-A", 0.12, _config(mirror="False"))
    _arm(conn, "M0002-MIRROR", 0.06, _config(mirror="True"))
    s = dressing.survey(conn)
    assert {d.pairing.method_id for d in s.priced} == {"M0001"}
    assert {d.pairing.method_id for d in s.unpriced} == {"M0002"}
    assert "Priced: 1 of 2" in dressing.format_survey(s)


def test_the_sweep_can_be_limited_to_named_methods(conn):
    _pair(conn)
    assert dressing.survey(conn, methods=["M0999"]).found == ()
    assert len(dressing.survey(conn, methods=["m0001"]).found) == 1  # case-insensitive


def test_naming_a_method_with_no_reversed_arm_says_so_usefully(conn):
    _method(conn)
    _arm(conn, "M0001-A", 0.12, _config(floor="0.5"))
    _arm(conn, "M0001-B", 0.11, _config(floor="0.0"))
    with pytest.raises(store.LabError, match="recorded no reversed arm"):
        dressing.resolve_pairing(conn, "M0001")


def test_a_pair_can_be_declared_by_hand_and_says_its_orientation_is_unresolved(conn):
    _method(conn)
    _arm(conn, "M0001-A", 0.12, _config(floor="0.5"))
    _arm(conn, "M0001-B", 0.06, _config(floor="0.0"))
    pairing, _rows = dressing.resolve_pairing(conn, "M0001-A", "M0001-B")
    assert pairing.rung == dressing.UNRESOLVED
    assert (pairing.straight_id, pairing.reversed_id) == ("M0001-A", "M0001-B")


def test_the_csv_carries_every_split_at_full_precision(conn):
    got = _pair(conn)
    rows = dressing.csv_rows([got])
    assert rows[0][0] == "method_id"
    assert len(rows) == 1 + len(got.splits)
    assert any("e-" in cell or "." in cell for cell in rows[1])


# --------------------------------------------------------------------------- nothing is written


def test_measuring_and_sweeping_write_nothing_at_all(conn):
    """`lab survivorship` and `lab costs` journal on every run. This must not, on any path."""
    _pair(conn)
    tables = ("trials", "trial_moments", "trial_funding", "trial_provenance", "insights",
              "method_folds", "method_amendments", "methods", "ideas_seen")
    before = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}
    looks = store.test_looks(conn)

    pairing, rows = dressing.resolve_pairing(conn, "M0001")
    one = dressing.measure(conn, pairing, rows)
    dressing.format_report(one)
    dressing.format_survey(dressing.survey(conn))
    dressing.csv_rows([one])

    after = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}
    assert after == before
    assert store.test_looks(conn) == looks


def test_the_test_window_is_never_read(conn):
    """A budget spent once per method. The one query this module issues is pinned to dev."""
    _pair(conn)
    with conn:
        ns = store.insert_trials(conn, [_trial(
            candidate_id="M0001-A-TEST", config_digest="d-test", window="test",
            config_text=_config(mirror="False"),
            start="2015-10-19", end="2026-10-01", curve_json=_curve(
                _months(date(2015, 10, 19), date(2026, 10, 1)), 0.2),
        )])
        stamp_provenance(conn, ns, price_fingerprint=LAB_PRICE_FINGERPRINT)
    seen = {r["candidate_id"] for r in dressing.dev_rows(conn)}
    assert "M0001-A-TEST" not in seen
    assert all("TEST" not in d.pairing.straight_id for d in dressing.survey(conn).found)


# ------------------------------------------------------- the answers the lab already has


def _committed():
    """The committed lab, read-only (no migration, so the file is not dirtied), or None."""
    path = store.COMMITTED_DB
    if not path.is_file():
        return None
    try:
        return store.connect_readonly(path)
    except store.LabError:
        return None


def _split(c, method_id: str, straight: str | None = None):
    found = dressing.survey(c, methods=[method_id]).found
    if straight is not None:
        found = [d for d in found if d.pairing.straight_id == straight]
    return found[0] if found else None


def test_the_committed_lab_reproduces_M0254s_published_ratio_at_floor_50():
    """Insight 490: direction +1.76, shape -2.51, ratio 0.701. Derived by hand on 2026-10-20."""
    c = _committed()
    if c is None:
        pytest.skip("no committed lab.sqlite")
    try:
        got = _split(c, "M0254")
        if got is None:
            pytest.skip("M0254 is not recorded here")
        assert got.pairing.straight_id == "M0254-FLOOR50"
        assert got.pairing.reversed_id == "M0254-MIRROR50"
        assert got.endpoint is not None and got.endpoint.arms == ("M0254-HOLD",)
        s = got.at(dressing.MONEY, "whole")
        assert s.direction * 100 == pytest.approx(1.76, abs=0.01)
        assert s.toll * 100 == pytest.approx(-2.51, abs=0.01)
        assert s.ratio == pytest.approx(0.701, abs=0.001)
        assert got.verdict == dressing.DEAD
    finally:
        c.close()


def test_the_committed_lab_reproduces_M0254s_published_ratio_at_floor_0():
    """The same insight's other rung: +3.59 / -5.26 / 0.682.

    Floor 0 is M0251-LADDER -- M0254's own file says FLOOR00 reproduces it bar for bar, and the
    two recorded curves are identical -- and the hand decomposition priced it against
    **M0254-HOLD**, the child's window-matched re-run of the always-invested arm. Against
    M0251-HOLD, whose window starts thirteen months earlier, the same pair reads 0.657. That the
    endpoint ladder lands on M0254-HOLD is the half of this test that is easy to break.
    """
    c = _committed()
    if c is None:
        pytest.skip("no committed lab.sqlite")
    try:
        got = _split(c, "M0251", "M0251-LADDER")
        if got is None:
            pytest.skip("M0251 is not recorded here")
        assert got.pairing.reversed_id == "M0251-MIRROR"
        assert got.endpoint is not None
        assert got.endpoint.arms == ("M0254-HOLD",)
        assert got.endpoint.rung == dressing.LINEAGE_HOLD
        s = got.at(dressing.MONEY, "whole")
        assert s.direction * 100 == pytest.approx(3.59, abs=0.01)
        assert s.toll * 100 == pytest.approx(-5.26, abs=0.01)
        assert s.ratio == pytest.approx(0.682, abs=0.001)
    finally:
        c.close()


def test_floor_0_and_M0254s_own_floor_00_arm_are_the_same_book():
    """The identity the test above rests on: M0251-LADDER and M0254-FLOOR00 recorded one curve."""
    c = _committed()
    if c is None:
        pytest.skip("no committed lab.sqlite")
    try:
        rows = {str(r["candidate_id"]): r for r in c.execute(
            "SELECT candidate_id, curve_json FROM trials "
            "WHERE candidate_id IN ('M0251-LADDER', 'M0254-FLOOR00')"
        )}
        if len(rows) != 2:
            pytest.skip("both arms are not recorded here")
        assert rows["M0251-LADDER"]["curve_json"] == rows["M0254-FLOOR00"]["curve_json"]
    finally:
        c.close()


def test_the_committed_lab_reproduces_M0265s_split_and_names_the_cross_column_ratio():
    """Insight 511 reads 0.9 / 2.75 = 0.33 -- a money numerator over a paper denominator.

    Both of its halves reproduce, in the columns they came from: the money column's direction is
    0.90 and the paper column's toll is 2.78, within the 0.03 the lab's own third-fund study
    calls rounding on the same family of numbers. Inside one column the ratio is 0.315 and 0.199.
    Dead either way, which is why the verdict never depended on the mix-up.
    """
    c = _committed()
    if c is None:
        pytest.skip("no committed lab.sqlite")
    try:
        got = _split(c, "M0265")
        if got is None:
            pytest.skip("M0265 is not recorded here")
        assert got.endpoint is not None and got.endpoint.arms == ("M0265-BLEND",)
        money = got.at(dressing.MONEY, "whole")
        paper = got.at(dressing.PAPER, "whole")
        assert money.direction * 100 == pytest.approx(0.90, abs=0.01)   # the published 0.9
        assert paper.toll * 100 == pytest.approx(-2.75, abs=0.04)       # the published 2.75
        assert money.ratio == pytest.approx(0.315, abs=0.002)
        assert paper.ratio == pytest.approx(0.199, abs=0.002)
        assert got.verdict == dressing.DEAD
        # and the cross-column ratio the lab quoted, reproduced as the arithmetic it was
        assert money.direction / abs(paper.toll) == pytest.approx(0.33, abs=0.01)
    finally:
        c.close()


def test_the_committed_lab_reproduces_M0267s_opinion_and_prices_its_toll_at_13_flips():
    """Published: +2.38 pts/yr one-sided through the pair, and a toll far below M0265's.

    The published 2.38 came from a separate month-by-month pipeline over the two funds' prices;
    the lab's own third-fund study reproduced it at 2.41 and called the 0.03 rounding. Off the
    recorded curves it is 2.42. The toll is the headline the wish cares about: 0.70 points on the
    prices at 13 round trips against M0265's 2.78 at 80, which is the whole point that a chassis
    toll is a per-flip price and not the constant 2.75 the lab started quoting.
    """
    c = _committed()
    if c is None:
        pytest.skip("no committed lab.sqlite")
    try:
        got = _split(c, "M0267", "M0267-GATE")
        other = _split(c, "M0265")
        if got is None or other is None:
            pytest.skip("M0265/M0267 are not recorded here")
        paper = got.at(dressing.PAPER, "whole")
        assert paper.direction * 100 == pytest.approx(2.42, abs=0.02)
        assert paper.straight - paper.reversed_ == pytest.approx(0.0484, abs=0.0002)  # insight 515
        assert got.endpoint is not None and got.endpoint.rung == dressing.BLEND
        assert got.endpoint.arms == ("M0267-QQQ-HOLD", "M0267-SPY-HOLD")
        assert got.trades == (13, 13)
        assert abs(paper.toll) * 100 == pytest.approx(0.70, abs=0.02)
        # the generalisation: seven times the churn, five times the toll
        assert other.churn / got.churn == pytest.approx(7.4, abs=0.3)
        assert abs(other.at(dressing.PAPER, "whole").toll / paper.toll) == pytest.approx(4.0, abs=0.3)
        # and the two columns disagree, which is insight 515 showing up as a verdict
        assert got.at(dressing.MONEY, "whole").ratio == pytest.approx(0.98, abs=0.02)
        assert got.verdict == dressing.SPLIT
    finally:
        c.close()


def test_the_synthetic_blend_reproduces_the_one_blend_the_lab_actually_recorded():
    """M0265-BLEND is a fixed 50/50 book. Blending its two single-fund holds must land on it."""
    c = _committed()
    if c is None:
        pytest.skip("no committed lab.sqlite")
    try:
        rows = {str(r["candidate_id"]): r for r in dressing.dev_rows(c, "M0265")}
        if not {"M0265-BLEND", "M0265-SPY-HOLD", "M0265-QQQ-HOLD"} <= set(rows):
            pytest.skip("M0265 is not recorded here")
        legs = [dressing.leg_of(c, rows[k]) for k in ("M0265-SPY-HOLD", "M0265-QQQ-HOLD")]
        synthetic = dressing.blended(
            [regime.defunded(list(lg.curve), lg.deposits) for lg in legs]
        )
        real = dressing.leg_of(c, rows["M0265-BLEND"])
        lo, hi = real.window
        mine = dressing.paper_return(synthetic, {}, lo, hi)
        theirs = dressing.paper_return(real.curve, real.deposits, lo, hi)
        assert abs(mine - theirs) < dressing.BLEND_TOLERANCE
        assert abs(mine - theirs) * 100 == pytest.approx(0.0015, abs=0.001)
    finally:
        c.close()


def test_the_money_column_agrees_with_every_recorded_money_weighted_return():
    """The report recomputes `mwr` off the monthly curve so a synthetic endpoint can be measured.

    A reconstruction nobody checked is not a measurement. Over every funded dev trial in the
    committed lab the recomputation must sit within 0.02 points a year of the recorded figure,
    and the bias must be one-signed -- it comes from bucketing each deposit to its month end, and
    a one-signed bias is what makes it cancel in the subtractions this module does.
    """
    c = _committed()
    if c is None:
        pytest.skip("no committed lab.sqlite")
    try:
        gaps = []
        for row in dressing.dev_rows(c):
            recorded = c.execute(
                "SELECT mwr FROM trial_funding WHERE trial_n = ?", (int(row["n"]),)
            ).fetchone()
            if recorded is None or recorded["mwr"] is None or not row["curve_json"]:
                continue
            leg = dressing.leg_of(c, row)
            lo, hi = leg.window
            mine = dressing.money_return(leg.curve, leg.deposits, lo, hi)
            if mine is None:
                continue
            gaps.append(mine - float(recorded["mwr"]))
        if not gaps:
            pytest.skip("no funded dev trial is recorded here")
        assert max(abs(g) for g in gaps) < 0.00025
        # overwhelmingly one-signed, which is what makes it cancel in a subtraction: measured
        # 2026-10-21 over 761 funded dev trials, 736 positive and 25 negative, worst 0.019 pts.
        assert sum(1 for g in gaps if g > 0) > 0.9 * len(gaps)
    finally:
        c.close()


def test_the_committed_sweep_finds_every_mirror_pair_without_reading_a_single_name():
    """The detector is structural. Every pair it finds differs in one recorded setting only."""
    c = _committed()
    if c is None:
        pytest.skip("no committed lab.sqlite")
    try:
        s = dressing.survey(c)
        if not s.found:
            pytest.skip("the committed lab records no mirror pair")
        assert {"M0251", "M0254", "M0265", "M0267"} <= {d.pairing.method_id for d in s.found}
        rows = {str(r["candidate_id"]): r for r in dressing.dev_rows(c)}
        for d in s.found:
            a = dressing.fields_of(rows[d.pairing.straight_id]["config_text"])
            b = dressing.fields_of(rows[d.pairing.reversed_id]["config_text"])
            assert dressing.reversal_between(a, b) is not None
        assert dressing.format_survey(s)
    finally:
        c.close()


def test_role_of_cannot_see_the_lab_mirrors_which_is_why_the_flag_rung_exists():
    """Pinned so that widening control_shape's openers one day is a visible decision, not a drift."""
    from seer_engine.lab.method import discover

    found = discover()
    seen = 0
    for mid in ("M0251", "M0254", "M0265", "M0267"):
        entry = found.get(mid)
        if entry is None:
            continue
        for arm in entry[0].all_candidates():
            if "MIRROR" in arm.id:
                seen += 1
                assert cs.role_of(arm) == cs.ROLE_TREATMENT
    if seen == 0:
        pytest.skip("none of those method files is present")


def test_the_committed_lab_is_not_dirtied_by_reading_it():
    """A lab command migrates on connect, and even a read can move the file. This one may not."""
    path = store.COMMITTED_DB
    if not path.is_file():
        pytest.skip("no committed lab.sqlite")
    import hashlib

    before = hashlib.sha256(path.read_bytes()).hexdigest()
    c = _committed()
    if c is None:
        pytest.skip("cannot open the committed lab read-only")
    try:
        dressing.survey(c, methods=["M0254"])
    finally:
        c.close()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
