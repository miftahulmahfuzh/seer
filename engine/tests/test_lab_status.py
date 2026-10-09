"""`lab status`'s promotion path, look budget and ratchet warning (lab-luck-gate phase 5).

Every test builds its own temp lab. The real one's state changes with every Sera batch and these
tests must keep passing through all of them -- so nothing here asserts a count the committed
database happens to have.

The recorded `failed` strings in these fixtures deliberately say "DSR >= 0.95", the text the 110
append-only rows carry, while `store.DSR_LABEL` now reads "DSR >= 0.90". That mismatch is the
hazard Decision D1 created and `_owner_misses` exists to handle.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import date, timedelta

import pytest

from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import store

OLD_LUCK_LABEL = "DSR >= 0.95"  # what the append-only rows say, forever


@pytest.fixture(autouse=True)
def _at_the_policy_these_fixtures_were_recorded_under(monkeypatch):
    """Judge every lab in this module under ``all-trials``, the policy its rows were stamped with.

    Not a convenience and not a workaround for the shipped policy: it is the one assumption these
    fixtures already encode. Every trial they insert carries ``n_trials_at_run`` equal to the
    fixture's dev row count, which is what a lab recorded under ``all-trials`` looks like and
    nothing else. ``store.verdict`` re-evaluates a recorded DSR **at the gate's current N**, so
    the re-evaluation is the identity -- and an eligibility assertion means what it says -- only
    while the gate resolves to the N stamped on the rows. Judging a recorded lab under the policy
    it was recorded under is the condition, and naming it here is strictly more honest than
    inheriting it from whatever ``store.DSR_POLICY`` happens to be.

    Since 2026-10-08 it no longer is: ``DSR_POLICY`` is ``methods`` (lab-realistic-gate R1), which
    on a one-method lab resolves to ``max(1, ceil(participation ratio))`` -- 1 when the fixtures
    record no curves -- and ``dev.deflated_sharpe`` is undefined below two looks. Every derived
    verdict here would then collapse to "no evaluable luck test" for a reason that has nothing to
    do with this module's subject. What the shipped policy resolves to is pinned where it belongs,
    in ``test_lab_gate_policy.py`` and ``test_lab_npolicy.py``.

    Autouse rather than folded into a connection fixture, because the paths under test resolve the
    gate themselves -- ``lab status`` resolves the gate inside the command, and every test here
    builds its own database and hands the path to the CLI.
    """
    monkeypatch.setattr(store, "DSR_POLICY", "all-trials")
    store._GATE_CACHE.clear()
    yield
    store._GATE_CACHE.clear()


@pytest.fixture()
def status(capsys):
    def go(db) -> str:
        args = argparse.Namespace(db=db, lab_command="status")
        assert lab_cmd.run(args) == 0
        return capsys.readouterr().out

    return go


def _trial(**kw) -> store.TrialRow:
    base = dict(
        method_id="M0001", candidate_id="M0001-A", config_digest="d1", config_text="t",
        rules_id="MONTHLY_HOLD", allocator_id="TIMING", window="dev", start="1996-01-02",
        end="2015-10-16", store_fingerprint="399d0d25", git_sha="abc123",
        run_at="2026-10-06T00:00:00+00:00", total_return=3.0, cagr=0.12, max_drawdown=0.11,
        profit_factor=1.6, trades=250, sharpe=0.9, exposure=0.95, turnover=1.1, worst_year=2008,
        worst_year_return=-0.1, spy_tr_return=2.0, spy_tr_cagr=0.08, mar=0.8, failed="",
        eligible=True, dsr=0.97, n_trials_at_run=2, curve_json="[]",
    )
    base.update(kw)
    return store.TrialRow(**base)


# `n_trials_at_run=2` is load-bearing in this file, not arbitrary. Phase 4's `store.verdict`
# re-evaluates every recorded DSR **at the gate's current N**; these fixtures hold two dev trials,
# so the gate resolves to N = 2 under `all-trials` and the re-evaluation is the identity. Give a
# fixture a different N and its DSR moves under the assertions -- which is exactly the behaviour
# the gate is supposed to have, and exactly what makes a fixture that forgets it confusing.


def _method(c, mid: str, *, status: str, trials) -> None:
    """A method at ``status`` with ``trials`` recorded, walked along TRANSITIONS."""
    path = {
        "registered": ("registered",),
        "rejected": ("registered", "rejected"),
        "dev-eligible": ("registered", "dev-eligible"),
        "promoted": ("registered", "dev-eligible", "promoted"),
        "test-passed": ("registered", "dev-eligible", "promoted", "test-passed"),
        "test-failed": ("registered", "dev-eligible", "promoted", "test-failed"),
    }[status]
    with c:
        store.add_method(c, id=mid, name=f"name {mid}", family="fam",
                         source_kind="knowledge", hypothesis="h")
        store.insert_trials(c, list(trials))
        for s in path:
            store.update_method(c, mid, status=s)


# ------------------------------------------------------------------ the path prints when empty


def test_an_empty_promotion_path_still_prints_every_section(tmp_path, status):
    """R3 in one assertion: a lab in which `lab promote` and `lab test` are both unreachable
    says so, instead of printing nothing at all about the promotion path."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="rejected", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a",
               failed=OLD_LUCK_LABEL, eligible=False, dsr=0.80),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.7,
               failed=f"max DD <= 15%; {OLD_LUCK_LABEL}", eligible=False, dsr=0.70),
    ])
    c.close()
    out = status(db)
    assert "Promotion path" in out
    for title in ("Dev-eligible", "Promoted (pre-registered)", "Test-passed", "Test-failed",
                  "Paper"):
        assert f"{title}: (none)" in out
    assert "Promotable now" in out
    assert "Test-window looks used: 0" in out
    assert "never given back" in out


def test_the_empty_dev_eligible_section_names_the_closest_candidate_and_the_bar(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="rejected", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a",
               failed=OLD_LUCK_LABEL, eligible=False, dsr=0.88),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.7, mar=0.7,
               failed=OLD_LUCK_LABEL, eligible=False, dsr=0.70),
    ])
    c.close()
    out = status(db)
    assert "held by the luck bar alone" in out
    assert "M0001-A" in out            # the closest, not the other one
    assert str(store.DSR_MIN) in out
    assert "lab luck" in out


def test_a_candidate_that_misses_an_owner_condition_is_named_as_unrescuable(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="rejected", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a",
               max_drawdown=0.31, failed=f"max DD <= 15%; {OLD_LUCK_LABEL}",
               eligible=False, dsr=0.99),
    ])
    c.close()
    out = status(db)
    assert "none passes the five go-live conditions" in out
    assert "max DD <= " in out
    assert "can rescue" in out


def test_a_historical_luck_label_is_not_read_as_an_owner_condition(tmp_path, status):
    """Decision D1's hazard: `store.DSR_LABEL` reads "DSR >= 0.90" while every recorded row says
    "DSR >= 0.95". A trial that missed only the old luck bar must still count as passing all five
    owner conditions, in the reason sentence and in the Closest-to-eligible table."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="rejected", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a",
               failed=OLD_LUCK_LABEL, eligible=False, dsr=0.88),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.7, mar=0.7,
               failed=OLD_LUCK_LABEL, eligible=False, dsr=0.70),
    ])
    c.close()
    out = status(db)
    assert "held by the luck bar alone" in out
    assert "M0001-A" in out
    assert "misses 0" in out        # the Closest-to-eligible table agrees
    assert OLD_LUCK_LABEL not in out.split("Closest to eligible")[1].split("Promotion path")[0]


def test_an_empty_lab_says_nothing_has_run(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    store.connect(db).close()
    out = status(db)
    assert "no method has run on the dev window yet" in out
    assert "Test-window looks used: 0" in out


# ------------------------------------------------------------------ promotable now


def test_promotable_now_lists_what_lab_promote_would_take(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="dev-eligible", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a", mar=0.9),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.7, mar=0.5),
    ])
    c.close()
    out = status(db)
    block = out.split("Promotable now")[1]
    assert "M0001-A" in block          # best by MAR, the one `lab promote` pre-registers
    assert "Dev-eligible (1)" in out


def test_a_derived_eligible_method_still_rejected_is_named_as_held(tmp_path, status):
    """`lab promote` refuses a rejected method however good its trial is, and the status says
    which command moves it rather than leaving the reader to guess."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="rejected", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a", mar=0.9),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.7, mar=0.5),
    ])
    c.close()
    out = status(db)
    assert "held by the status machine" in out
    assert "'rejected'" in out
    assert "lab reevaluate M0001" in out   # the command that actually moves it, not `lab run`


# ------------------------------------------------------------------ D1b: the ratchet warning


def _near_the_bar(c) -> None:
    """A lab whose best luck-only candidate clears the bar by less than `_WARN_MARGIN`.

    Two trials so there is a Sharpe variance to deflate by, and `n_trials_at_run=2` so the gate's
    N is the trial's own N and `store.dsr_at` returns the recorded number unchanged -- the
    identity `recover_dsr` rests on. The warning then has a DSR of exactly `DSR_MIN + 0.01` to
    reason about, which is what makes these assertions deterministic.
    """
    _method(c, "M0001", status="dev-eligible", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a", sharpe=0.95,
               mar=0.9, failed="", eligible=True,
               dsr=store.DSR_MIN + 0.01, n_trials_at_run=2),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.40,
               mar=0.4, max_drawdown=0.31, failed=f"max DD <= 15%; {OLD_LUCK_LABEL}",
               eligible=False, dsr=0.55, n_trials_at_run=2),
    ])


def test_the_ratchet_warning_fires_and_names_the_n_that_sinks_the_candidate(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _near_the_bar(c)
    c.close()
    out = status(db)
    assert "The luck bar is close" in out
    assert "M0001-A" in out
    assert "of margin" in out
    assert "falls below the bar at N =" in out
    assert "more dev trials" in out
    assert "lab luck" in out


def test_the_ratchet_warning_is_silent_when_the_margin_is_comfortable(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="dev-eligible", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a", sharpe=0.95,
               mar=0.9, failed="", eligible=True, dsr=0.999, n_trials_at_run=2),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.40,
               mar=0.4, max_drawdown=0.31, failed=f"max DD <= 15%; {OLD_LUCK_LABEL}",
               eligible=False, dsr=0.55, n_trials_at_run=2),
    ])
    c.close()
    assert "The luck bar is close" not in status(db)


def test_the_ratchet_warning_is_silent_when_nothing_is_above_the_bar(tmp_path, status):
    """Below the bar, the empty Dev-eligible section is already the sentence; a second one would
    be noise."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="rejected", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a", sharpe=0.95,
               mar=0.9, failed=OLD_LUCK_LABEL, eligible=False, dsr=0.70, n_trials_at_run=2),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.40,
               mar=0.4, max_drawdown=0.31, failed=f"max DD <= 15%; {OLD_LUCK_LABEL}",
               eligible=False, dsr=0.55, n_trials_at_run=2),
    ])
    c.close()
    out = status(db)
    assert "The luck bar is close" not in out
    assert "held by the luck bar alone" in out


def test_sinks_at_finds_the_first_n_below_the_bar(tmp_path):
    """The bisection, directly: the N it returns is below the bar and the one before it is not."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _near_the_bar(c)
    found = lab_cmd._best_luck_only(c)
    assert found is not None
    trial, v = found
    var = lab_cmd._dev_var(c)
    n = lab_cmd._sinks_at(c, trial, v, var)
    c.close()
    assert n is not None and n > int(v.n)
    common = dict(sharpe_daily=float(trial["sharpe"]) / (252 ** 0.5),
                  dsr_at_run=float(v.dsr), n_at_run=int(v.n), var_trials=var)
    assert lab_cmd.recover_dsr(n_trials=n, **common) < store.DSR_MIN
    assert lab_cmd.recover_dsr(n_trials=n - 1, **common) >= store.DSR_MIN


# ------------------------------------------------------------------ the hard gate in `lab status`
#
# R7 (lab-hard-gate phase 3): a dev-eligible method `lab promote` would refuse must not be listed
# as promotable, and the reason must be on the screen. Six tests, nothing above this line edited.
#
# Two of them need a real fold geometry, so they build a `REF-SPY-HOLD` dev trial with a monthly
# curve. The span is 1993-02..2015-09 and not the dev window's 1996-01, because `walkforward.folds`
# cuts the geometry from the *benchmark*: from 1996 the last slice is 9 months, below
# `MIN_EVAL_MONTHS`, and only three folds survive -- which the gate then refuses on MIN_FOLDS, for
# a reason that has nothing to do with what the test is about. From 1993-02 there are exactly four
# 36-month slices, which is the committed lab's own geometry.


def _month_ends(first: date, last: date) -> list[date]:
    """Every month end in ``[first, last]``, the shape a recorded `trials.curve_json` has."""
    out: list[date] = []
    y, m = first.year, first.month
    while True:
        nxt = date(y + (m // 12), (m % 12) + 1, 1)
        end = nxt - timedelta(days=1)
        if end > last:
            return out
        if end >= first:
            out.append(end)
        y, m = nxt.year, nxt.month


def _curve(days: list[date], monthly: float) -> str:
    """A monotone curve compounding at ``monthly``, as `trials.curve_json` stores it.

    Monotone on purpose: `walkforward.measure` gives a slice that never fell an infinite MAR, so
    `pick` ranks it rather than dropping it, and `FoldPick.beat` compares total return, so the
    faster curve wins every fold deterministically. No randomness, no tuning.
    """
    value, points = 1.0, []
    for d in days:
        points.append([d.isoformat(), round(value, 8)])
        value *= 1.0 + monthly
    return json.dumps(points)


def _method_at(c, mid: str, *, status: str, family: str = "fam", trials=()) -> None:
    """Like ``_method``, but reaching the statuses the hard gate cares about.

    ``_method`` above stops at ``dev-eligible``; the gate's (K) condition needs a kin that reads
    ``test-failed``, which is three transitions further along. A separate helper rather than an
    edit to ``_method``, because every test above depends on that one exactly as it is.
    """
    path = {
        "registered": ("registered",),
        "rejected": ("registered", "rejected"),
        "dev-eligible": ("registered", "dev-eligible"),
        "promoted": ("registered", "dev-eligible", "promoted"),
        "test-failed": ("registered", "dev-eligible", "promoted", "test-failed"),
    }[status]
    with c:
        store.add_method(c, id=mid, name=f"name {mid}", family=family,
                         source_kind="knowledge", hypothesis="h")
        if trials:
            store.insert_trials(c, list(trials))
        for s in path:
            store.update_method(c, mid, status=s)


def _lab_with_a_benchmark(c, *, method_monthly: float, kin_failed: bool = False) -> None:
    """A lab the walk-forward can actually score: a benchmark, and one dev-eligible method.

    ``method_monthly`` above the benchmark's 0.004 wins every fold; below it loses every fold.
    ``kin_failed`` adds a sibling in the same family that reads ``test-failed``, which is the
    gate's (K) condition and nothing else.
    """
    days = _month_ends(date(1993, 2, 1), date(2015, 9, 30))
    n = 3 if kin_failed else 2
    _method_at(c, "M0001", status="dev-eligible", family="fam", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a", mar=0.9,
               start="1993-02-28", end="2015-09-30", n_trials_at_run=n,
               curve_json=_curve(days, method_monthly)),
    ])
    _method_at(c, "M0009", status="rejected", family="bench", trials=[
        # `sharpe=0.7` against M0001's 0.9 is not decoration: `store.dsr_at` recovers a DSR
        # through `dev_sharpe_variance`, which is zero on a lab whose dev trials all carry the
        # same Sharpe -- the luck test then fails for want of a variance and the method never
        # reaches the hard gate at all. The same 0.9 / 0.7 spread `_method`'s fixtures use.
        _trial(method_id="M0009", candidate_id="REF-SPY-HOLD", config_digest="spy",
               start="1993-02-28", end="2015-09-30", n_trials_at_run=n, eligible=False,
               failed=OLD_LUCK_LABEL, dsr=0.10, sharpe=0.7, curve_json=_curve(days, 0.004)),
    ])
    if kin_failed:
        _method_at(c, "M0002", status="test-failed", family="fam", trials=[
            _trial(method_id="M0002", candidate_id="M0002-A", config_digest="b", mar=0.6,
                   start="1993-02-28", end="2015-09-30", n_trials_at_run=n,
                   curve_json=_curve(days, 0.006)),
        ])


def test_a_method_that_clears_the_hard_gate_is_listed_with_its_fold_record(tmp_path, status):
    """R7's positive half: taken, and the line says on what evidence."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _lab_with_a_benchmark(c, method_monthly=0.009)
    c.close()
    out = status(db)
    ready = out.split("Promotable now")[1].split("\n  Dev-eligible")[0]
    assert "M0001" in ready
    assert "of 4 folds" in ready          # `walkforward.Record.summary()`, printed verbatim
    assert "kin clean" in ready
    assert "Refused by the hard gate" not in out


def test_a_method_that_loses_its_folds_is_refused_and_the_record_says_so(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _lab_with_a_benchmark(c, method_monthly=0.001)   # below the benchmark's 0.004, every fold
    c.close()
    out = status(db)
    ready = out.split("Promotable now")[1].split("Refused by the hard gate")[0]
    assert "(none)" in ready and "M0001 " not in ready
    blocked = out.split("Refused by the hard gate")[1].split("\n  Dev-eligible")[0]
    assert "M0001" in blocked
    assert "of 4 folds" in blocked


def test_a_method_whose_kin_test_failed_is_refused_and_the_kin_is_named(tmp_path, status):
    """(K): the folds are won 4 of 4, so the only thing left to refuse on is the sibling."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _lab_with_a_benchmark(c, method_monthly=0.009, kin_failed=True)
    c.close()
    out = status(db)
    blocked = out.split("Refused by the hard gate")[1].split("\n  Dev-eligible")[0]
    assert "M0001" in blocked
    assert "M0002" in blocked      # the kin, named, so the reader does not go looking


def test_lab_status_still_prints_when_the_gate_cannot_score_the_lab(tmp_path, status):
    """The shape every other fixture in this module has: no benchmark, empty curves.

    The gate refuses it and is right to -- the folds are cut from the benchmark curve. What must
    not happen is `lab status` exiting non-zero or printing nothing, which is what a `LabError`
    escaping `_hard_gate_states` would do. The `status` fixture asserts the exit code for us.
    """
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="dev-eligible", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a", mar=0.9),
        _trial(method_id="M0001", candidate_id="M0001-B", config_digest="b", sharpe=0.7, mar=0.5),
    ])
    c.close()
    out = status(db)
    assert "Promotable now" in out
    blocked = out.split("Refused by the hard gate")[1].split("\n  Dev-eligible")[0]
    assert "M0001" in blocked
    assert "REF-SPY-HOLD" in blocked    # the lab's fixture is wrong, not the method (D7)


def test_the_empty_promoted_section_blames_the_gate_not_an_unrun_command(tmp_path, status):
    """"`lab promote` has not been run on them yet" is false when it would exit 2 on all of them."""
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _lab_with_a_benchmark(c, method_monthly=0.001)
    c.close()
    out = status(db)
    promoted = out.split("Promoted (pre-registered): (none)")[1].split("\n")[0]
    assert "hard gate refuses" in promoted
    assert "has not been run on" not in promoted
    assert "no override" in promoted


def test_the_dev_eligible_header_no_longer_promises_a_promotion(tmp_path, status):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _lab_with_a_benchmark(c, method_monthly=0.001)
    c.close()
    out = status(db)
    assert "`lab promote` pre-registers these" not in out
    assert "the hard gate decides which of these `lab promote` takes" in out


# ------------------------------------------------------------------ the committed database


@pytest.mark.skipif(not store.COMMITTED_DB.is_file(), reason="no committed lab database here")
def test_status_runs_on_a_copy_of_the_committed_database(tmp_path, status):
    """The real shape, on the real data, without touching the committed file."""
    db = tmp_path / "lab.sqlite"
    shutil.copy(store.COMMITTED_DB, db)
    c = store.connect(db)
    looks = store.test_looks(c)
    c.close()
    out = status(db)
    assert "Promotion path" in out
    assert f"Test-window looks used: {looks}" in out


def test_a_test_failed_method_is_not_offered_a_way_back(tmp_path, status):
    """`lab reevaluate` takes exactly one edge, `rejected -> dev-eligible`, and TRANSITIONS has
    none at all out of `test-failed`. Offering it there advertised a way back that does not exist
    -- and in the one direction that matters, since un-failing a method would unblock the hard
    gate's kin check on every relative of it.
    """
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    _method(c, "M0001", status="test-failed", trials=[
        _trial(method_id="M0001", candidate_id="M0001-A", config_digest="a",
               failed="", eligible=True, dsr=0.99),
    ])
    c.close()
    for line in status(db).splitlines():
        if "status 'test-failed'" in line:
            assert "lab reevaluate" not in line, line
            assert "final" in line, line
