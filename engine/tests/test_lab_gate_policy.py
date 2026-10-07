"""The luck gate: one threshold, one N policy, read at evaluation time (plan phase 4).

Nothing here runs a backtest, loads a research store, or writes ``lab/lab.sqlite``: the committed
database is copied into ``tmp_path`` before anything opens it for writing, and the tests that need
DSR inputs construct ``trial_moments`` rows directly, because the backfill that measures them is
``lab remeasure`` (phase 3).

The claims this module exists to hold:

1. the shipped defaults -- DSR_MIN 0.90, DSR_POLICY "all-trials" -- resolve to N = 110 on the
   committed lab, which is today's N, so only the threshold moved;
2. at (110, 0.90, max DD 20%) exactly **three** candidates become eligible -- M0022-W-TV14,
   M0022-W-TV16 and M0020-W-NOSTOP -- and ``best_dev_eligible`` returns W-TV14 for M0022 because
   MAR decides; M0007-N20-RAW does NOT, on 0.8985 re-evaluated at N=110;
3. nothing that fails a non-luck condition becomes eligible at any (policy, threshold)
   combination -- in particular the candidates whose recorded DSR is already >= 0.90;
4. M0011 stays ineligible, so RM-FR stays lab-rejected while RMW-FR becomes lab-eligible;
5. every recorded dsr / eligible / failed / n_trials_at_run on all 110 rows is byte-identical
   before and after this phase, and ``test_looks`` is still 0;
6. (all-trials, 0.95, 15%) together reproduce today's verdicts exactly -- the proof that only the
   two owner-set bars moved;
7. a recorded ``failed`` of "DSR >= 0.95" reads as ZERO owner misses under DSR_MIN 0.90, and a
   recorded "max DD <= 15%" does not freeze a trial at 15% -- the proof that the two moved bars
   reach the recorded rows rather than tripping over their own labels;
8. ``Verdict.failed`` is a tuple of label strings, and the gate's estimator runs once per dev
   trial set rather than once per method.

**A note on the fixtures, and why most of them insert two trials.** ``store.dsr_at`` deflates by
``store.dev_sharpe_variance(conn)`` (Decision D12), which is the *sample* variance of the dev
trials' daily Sharpes and is therefore None in a lab holding fewer than two of them; and
``store.recover_dsr`` is undefined below two looks at either N. A one-trial fixture consequently
has no evaluable DSR at all, and every assertion about a *derived* verdict would pass for the
wrong reason -- the luck label appended because nothing could be computed, rather than because a
real number missed the bar. So a fixture that needs a derived verdict inserts a second dev trial
(``_ballast``) with a different Sharpe, and judges at ``Gate(n=2)``, which is the N those rows
were recorded at. Nothing is relaxed by this: the assertions are the ones the phase plan states,
and the fixtures are moved clear of the bar so they actually exercise them.
"""

from __future__ import annotations

import hashlib
import math
import shutil
import sqlite3
from statistics import NormalDist

import pytest

from seer_engine.backtest.dev import deflated_sharpe
from seer_engine.lab import npolicy, store

_EULER_GAMMA = 0.5772156649015329


# --------------------------------------------------------------------------- fixtures


@pytest.fixture(autouse=True)
def _clean_gate_cache():
    """``gate`` memoises on (database file, policy, dev trial set). ``tmp_path`` differs per test
    so entries cannot collide, but a monkeypatched policy or threshold should never be served a
    gate resolved under another one -- clear it at both ends and the question does not arise."""
    store._GATE_CACHE.clear()
    yield
    store._GATE_CACHE.clear()


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    yield c
    c.close()


def _method(conn, mid="M0001", status="idea"):
    with conn:
        store.add_method(conn, id=mid, name="n", family="f", source_kind="knowledge",
                         hypothesis="h", status=status)


def _trial(**kw) -> store.TrialRow:
    base = dict(
        method_id="M0001", candidate_id="M0001-A", config_digest="d1", config_text="t",
        rules_id="r", allocator_id="a", window="dev", start="2000-01-03", end="2015-10-16",
        store_fingerprint="fp", git_sha="abc", run_at="2026-10-07T00:00:00+00:00",
        total_return=1.0, cagr=0.1, max_drawdown=0.12, profit_factor=1.5, trades=200,
        sharpe=0.94, exposure=0.9, turnover=1.0, worst_year=2008, worst_year_return=-0.2,
        spy_tr_return=0.5, spy_tr_cagr=0.07, mar=0.8, failed="DSR >= 0.95", eligible=False,
        dsr=0.91, n_trials_at_run=1, curve_json="[]",
    )
    base.update(kw)
    return store.TrialRow(**base)


def _ballast(method_id="M0001", **kw) -> store.TrialRow:
    """A second dev trial, so the fixture lab has a real trial-Sharpe variance to deflate by.

    It is deliberately **ineligible on an owner condition no bar in this plan set moves** -- a
    24.5% drawdown, outside even the owner's new 20% bar -- so it supplies the spread
    ``dev_sharpe_variance`` needs without ever appearing in an eligible set or an ``unblocked``
    tuple. Its Sharpe differs from ``_trial``'s default, which is the whole of its job.
    """
    base = dict(
        method_id=method_id, candidate_id=f"{method_id}-BALLAST",
        config_digest=f"ballast-{method_id}", sharpe=1.46, max_drawdown=0.245, mar=0.1,
        dsr=0.50, n_trials_at_run=2, failed="max DD <= 15%; DSR >= 0.95",
    )
    base.update(kw)
    return _trial(**base)


def _moments(conn, trial_n, *, sr_daily, t, skew=0.0, kurt=3.0, var_trials, n_at_run,
             measured="reconstruction"):
    """Write one ``trial_moments`` row by raw SQL.

    Deliberately not through ``store.insert_moments``: that writer is phase 2's, and this phase
    depends only on the *column names*, so these tests stay green across any change to its
    keyword signature.

    ``measured`` defaults to the literal ``"reconstruction"`` rather than a timestamp, and that is
    the visible mark that these rows were fitted here rather than measured by ``lab run`` or
    recovered by ``lab remeasure`` (phase 3). It is a ``TEXT NOT NULL`` column with a
    ``length(trim(...)) > 0`` check, so it is a string, not a number.

    **``var_trials`` here is history, not a dial.** ``store.dsr_at`` deflates by
    ``store.dev_sharpe_variance(conn)`` on both routes (Decision D12) and never reads this
    column, so passing a different number here does **not** change any DSR these tests observe.
    A fixture that needs a particular hurdle sets the *spread of ``trials.sharpe``*, which is what
    ``dev_sharpe_variance`` is computed from. The column is still written because phase 2's schema
    requires it and because it is the number the trial was judged by.
    """
    conn.execute(
        "INSERT INTO trial_moments (trial_n, sr_daily, t, skew, kurt, var_trials, n_at_run, "
        "measured) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (int(trial_n), float(sr_daily), int(t), float(skew), float(kurt),
         None if var_trials is None else float(var_trials), int(n_at_run), str(measured)),
    )


# --------------------------------------------------------------------------- the constants


def test_the_luck_label_follows_the_threshold_and_still_recognises_the_old_one():
    assert store.DSR_MIN == 0.90
    assert store.DSR_LABEL == "DSR >= 0.90"
    assert store.is_luck_label(store.DSR_LABEL)
    assert store.is_luck_label("DSR >= 0.95")   # the label on all 110 recorded rows
    for owner in ("beats SPY TR", "max DD <= 15%", "max DD <= 20%", "PF >= 1.3",
                  ">= 100 trades", "owner inputs"):
        assert not store.is_luck_label(owner)
    assert store.recorded_labels("max DD <= 15%; DSR >= 0.95") == (
        "max DD <= 15%", "DSR >= 0.95")
    assert store.recorded_labels("") == ()


def test_the_owner_inputs_label_is_the_one_dev_still_writes():
    """``OWNER_INPUTS_LABEL`` is a literal in ``store`` so that importing it does not pull in the
    backtest package. This is the pin that keeps the literal equal to the thing it names."""
    from seer_engine.backtest import dev

    assert store.OWNER_INPUTS_LABEL == dev.FAILURE_LABELS[-1] == "owner inputs"
    # ...and it is the only D8 label with no number in it, which is why it can never go stale.
    assert not any(ch.isdigit() for ch in store.OWNER_INPUTS_LABEL)
    for other in dev.FAILURE_LABELS[1:-1]:
        assert any(ch.isdigit() for ch in other), other


def test_owner_failures_rederives_the_four_thresholds_and_carries_owner_inputs(conn):
    """**Four re-derived, one carried** -- the heart of the reconciled design.

    The recorded ``failed`` string names the bars of the run date. Both of them have moved: the
    luck bar to 0.90 (D1) and the drawdown bar to 20% (D6, phase 8). Only ``owner inputs`` comes
    out of the string.
    """
    from seer_engine.backtest import dev, tuning

    spy, drawdown, pf, trades, owner = dev.FAILURE_LABELS
    _method(conn)
    with conn:
        store.insert_trials(conn, [
            # 19.3% drawdown: outside the old 15% bar, inside the new 20% one. Recorded failing.
            _trial(candidate_id="A", config_digest="da", max_drawdown=0.193,
                   failed="max DD <= 15%; DSR >= 0.95", n_trials_at_run=1),
            # 20.7%: outside both bars. Must still read as a drawdown miss.
            _trial(candidate_id="B", config_digest="db", max_drawdown=0.207,
                   failed="max DD <= 15%; DSR >= 0.95", n_trials_at_run=1),
            # does not beat SPY, and recorded `owner inputs` besides
            _trial(candidate_id="C", config_digest="dc", total_return=0.4, spy_tr_return=0.5,
                   profit_factor=1.1, trades=12,
                   failed=f"beats SPY TR; PF >= 1.3; >= 100 trades; {owner}",
                   n_trials_at_run=1),
        ])
    rows = {r["candidate_id"]: r for r in conn.execute("SELECT * FROM trials")}

    assert tuning.MAX_DRAWDOWN == 0.20, "phase 8 sets the drawdown bar this phase reads"
    # A: the recorded string says it missed drawdown; the columns say it clears today's bar.
    assert rows["A"]["failed"] == "max DD <= 15%; DSR >= 0.95"       # untouched on disk
    assert store.owner_failures(rows["A"]) == ()                      # ...and clear today
    # B: still outside the bar, so still a miss -- and named with TODAY's label, not the old one.
    assert store.owner_failures(rows["B"]) == (drawdown,)
    assert drawdown == "max DD <= 20%" != rows["B"]["failed"].split("; ")[0]
    # C: three thresholds re-derived from columns, plus `owner inputs` carried from the string.
    assert store.owner_failures(rows["C"]) == (spy, pf, trades, owner)
    assert store.owner_failures(rows["C"])[-1] == store.OWNER_INPUTS_LABEL


def test_a_recorded_15pct_drawdown_label_does_not_freeze_a_trial_at_15pct(conn):
    """**The drawdown twin of the luck-label test, and the reason verdict stopped parsing.**

    All 110 recorded rows say ``max DD <= 15%``; the owner set the bar to 20% on 2026-10-07. A
    trial at 19.3% must read as *clearing* drawdown, or ``M0020-W-NOSTOP`` is frozen out of the
    lab for ever by a string describing a bar nobody applies any more.
    """
    _method(conn)
    with conn:
        store.insert_trials(conn, [
            _trial(dsr=0.9134, max_drawdown=0.193, failed="max DD <= 15%; DSR >= 0.95",
                   eligible=False, n_trials_at_run=2),
            _ballast(),
        ])
    row = conn.execute("SELECT * FROM trials WHERE candidate_id = 'M0001-A'").fetchone()
    v = store.verdict(conn, row, at=store.Gate(n=2, policy="all-trials"))
    assert v.derived is True
    assert v.dsr == pytest.approx(0.9134, abs=1e-12)  # judged at its own N, so exactly recorded
    assert v.failed == ()         # neither bar it was recorded against is the bar today
    assert v.eligible is True
    assert row["failed"] == "max DD <= 15%; DSR >= 0.95"   # and the record is untouched


def test_a_recorded_095_label_is_read_as_zero_owner_misses(conn):
    """**The test that proves the gate change reaches the 110 recorded rows.**

    `trials.failed` is append-only and every recorded luck failure says "DSR >= 0.95". If the
    luck label were recognised by equality with the live `DSR_LABEL` ("DSR >= 0.90"), that
    string would read as an unrecognised owner condition, nothing would ever be eligible, and
    the deadlock would come back silently. It must read as zero owner misses and be re-judged on
    the luck test alone.
    """
    _method(conn)
    with conn:
        store.insert_trials(conn, [
            _trial(dsr=0.9156, failed="DSR >= 0.95", eligible=False, n_trials_at_run=2),
            _ballast(),
        ])
    row = conn.execute("SELECT * FROM trials WHERE candidate_id = 'M0001-A'").fetchone()
    assert row["failed"] == "DSR >= 0.95"                  # untouched on disk
    assert store.owner_failures(row) == ()                 # zero owner misses
    v = store.verdict(conn, row, at=store.Gate(n=2, policy="all-trials"))
    assert v.derived is True
    assert v.failed == ()                                  # re-judged on the luck test alone
    assert v.eligible is True                              # 0.9156 >= DSR_MIN 0.90


def test_verdict_failed_is_a_tuple_of_labels_in_the_recorded_order(conn):
    """Shape, pinned: `failed` is a tuple of label strings, never a "; "-joined string.

    The labels are the **live** ones: a 24.5% drawdown is outside today's 20% bar and is named
    `max DD <= 20%`, not the `max DD <= 15%` the row happens to have recorded.
    """
    from seer_engine.backtest import dev

    drawdown = dev.FAILURE_LABELS[1]
    _method(conn)
    with conn:
        store.insert_trials(conn, [
            _trial(dsr=0.5, max_drawdown=0.245, failed="max DD <= 15%; DSR >= 0.95",
                   n_trials_at_run=2),
            _ballast(candidate_id="M0001-SPREAD", config_digest="spread", max_drawdown=0.30),
        ])
    row = conn.execute("SELECT * FROM trials WHERE candidate_id = 'M0001-A'").fetchone()
    v = store.verdict(conn, row, at=store.Gate(n=2, policy="all-trials"))
    assert v.derived is True                # a real DSR, evaluated -- and it misses the bar
    assert v.dsr == pytest.approx(0.5, abs=1e-12)
    assert isinstance(v.failed, tuple)
    assert all(isinstance(f, str) for f in v.failed)
    assert v.failed == (drawdown, store.DSR_LABEL)  # owners first, luck last
    assert "; ".join(v.failed) == f"{drawdown}; {store.DSR_LABEL}"
    assert v.eligible is (v.failed == ())


# --------------------------------------------------------------------------- the derived verdict


def test_verdict_rederives_the_luck_label_and_the_four_thresholds(conn):
    _method(conn)
    with conn:
        lucky, owner = store.insert_trials(conn, [
            _trial(candidate_id="M0001-A", config_digest="da", failed="DSR >= 0.95",
                   sharpe=0.94, n_trials_at_run=2),
            _trial(candidate_id="M0001-B", config_digest="db", max_drawdown=0.245,
                   failed="max DD <= 15%; DSR >= 0.95", sharpe=1.46, n_trials_at_run=2),
        ])
        for n in (lucky, owner):
            _moments(conn, n, sr_daily=0.0595, t=3900, var_trials=2.395e-04, n_at_run=2)
    rows = {r["candidate_id"]: r for r in conn.execute("SELECT * FROM trials")}
    g = store.Gate(n=2, policy="all-trials")
    a = store.verdict(conn, rows["M0001-A"], at=g)
    b = store.verdict(conn, rows["M0001-B"], at=g)
    assert a.derived and b.derived
    assert a.dsr == pytest.approx(b.dsr)        # identical moments, identical DSR
    assert a.dsr > store.DSR_MIN
    assert a.failed == () and a.eligible is True
    # ...and B's drawdown of 24.5% is still outside today's bar, re-derived from the column and
    # named with today's label rather than the one the row recorded.
    from seer_engine.backtest import dev

    assert b.failed == (dev.FAILURE_LABELS[1],)
    assert b.eligible is False


def test_a_recorded_dsr_at_the_gates_own_n_comes_back_unchanged(conn):
    """The identity `recover_dsr` rests on: at the trial's own N, nothing moves."""
    _method(conn)
    with conn:
        store.insert_trials(conn, [
            _trial(candidate_id="A", config_digest="da", dsr=0.9156, sharpe=0.945,
                   failed="DSR >= 0.95", n_trials_at_run=2),
            _trial(candidate_id="B", config_digest="db", dsr=0.80, sharpe=0.70,
                   failed="DSR >= 0.95", n_trials_at_run=2),
        ])
    row = conn.execute("SELECT * FROM trials WHERE candidate_id = 'A'").fetchone()
    v = store.verdict(conn, row, at=store.Gate(n=2, policy="all-trials"))
    assert v.derived is True
    assert v.dsr == pytest.approx(0.9156, abs=1e-12)   # exact, by the k-cancels identity
    assert v.failed == () and v.eligible is True


def test_a_recorded_dsr_at_another_n_is_re_evaluated_not_taken_at_face_value(conn):
    """**The decision this phase turns on.** 0.9156 at N = 2 is not 0.9156 at N = 110.

    An earlier draft returned such a row verbatim, which would have admitted `M0007-N20-RAW` on a
    DSR computed at N = 85 while judging M0022 at N = 110 -- a candidate admitted for having been
    tried earlier, which is the leaderboard-mixes-bars defect R2 exists to remove. The DSR is
    re-evaluated at the gate's N instead, and the luck test is decided on *that*.
    """
    _method(conn)
    with conn:
        store.insert_trials(conn, [
            _trial(candidate_id="A", config_digest="da", dsr=0.9156, sharpe=0.945,
                   failed="DSR >= 0.95", n_trials_at_run=2),
            _trial(candidate_id="B", config_digest="db", dsr=0.80, sharpe=0.70,
                   failed="DSR >= 0.95", n_trials_at_run=2),
        ])
    row = conn.execute("SELECT * FROM trials WHERE candidate_id = 'A'").fetchone()
    wide = store.verdict(conn, row, at=store.Gate(n=400, policy="all-trials"))
    assert wide.derived is True
    assert wide.n == 400                           # the gate's N, not the recorded 2
    assert wide.dsr is not None and wide.dsr < 0.9156   # the bar rose, so the score fell
    assert row["dsr"] == pytest.approx(0.9156)     # ...and the record is untouched


def test_a_trial_with_no_evaluable_dsr_fails_the_luck_test(conn):
    """**The P7a seed trap.** `dsr IS NULL` on 54 recorded rows (`seed.py`).

    A luck test that cannot be evaluated is a luck test that was not passed -- the same rule
    `runner.trial_rows` applies to a new trial. Without it, a seed row that passes all five owner
    conditions once the drawdown bar moves would become eligible on the strength of a luck test
    nobody ever ran. `F9-SPY200M70-MOM30` is exactly that row on the committed database.
    """
    _method(conn)
    with conn:
        store.insert_trials(conn, [
            _trial(dsr=None, max_drawdown=0.193, failed="max DD <= 15%", n_trials_at_run=90),
            # A second dev trial, so the lab HAS a trial-Sharpe variance: the point of this test
            # is that the NULL `dsr` is what holds the row out, not a missing variance.
            _ballast(),
        ])
    # NO `trial_moments` row is written for the subject, and that is the whole shape of the trap:
    # a NULL `dsr` with nothing measured beside it leaves route 2 with nothing to invert and
    # route 1 with nothing to recompute. (Give the row moments -- which is exactly what phase 9
    # does for the 54 seed trials -- and `dsr_at` takes route 1 and returns a real number. The
    # rule below does not change; it simply stops applying, which is R6.)
    row = conn.execute("SELECT * FROM trials WHERE candidate_id = 'M0001-A'").fetchone()
    assert store.dev_sharpe_variance(conn) is not None     # the variance is not the problem
    v = store.verdict(conn, row, at=store.Gate(n=110, policy="all-trials"))
    assert store.owner_failures(row) == ()          # every owner condition clears at 20%
    assert store.dsr_at(conn, row, 110) is None
    assert v.derived is False and v.dsr is None
    assert v.failed == (store.DSR_LABEL,)           # the luck test, failed
    assert v.eligible is False


def test_an_owner_condition_is_never_re_decided_by_the_n_policy(conn):
    """The N policy moves the luck test and nothing else.

    An owner condition is re-derived against its own constant, which no policy touches: a 24.5%
    drawdown is outside the 20% bar at every N, and `owner inputs` is outside every bar there is.
    """
    from seer_engine.backtest import dev

    _method(conn)
    # The ballast gets its own method id so that the `methods` policy also resolves to N = 2:
    # at N = 1 the expected maximum of one draw is Phi^-1(0) and no DSR is defined at all, which
    # would make this test pass by being unevaluable rather than by the drawdown binding.
    _method(conn, "M0002")
    with conn:
        n, _ = store.insert_trials(conn, [
            _trial(max_drawdown=0.245, failed="max DD <= 15%; DSR >= 0.95", n_trials_at_run=2),
            _ballast("M0002", max_drawdown=0.30),
        ])
        _moments(conn, n, sr_daily=0.0595, t=3900, var_trials=2.395e-04, n_at_run=2)
    row = conn.execute("SELECT * FROM trials WHERE candidate_id = 'M0001-A'").fetchone()
    for policy in npolicy.POLICIES:
        v = store.verdict(conn, row, policy=policy)
        assert v.derived is True, policy      # its DSR is evaluable; the drawdown is the reason
        assert dev.FAILURE_LABELS[1] in v.failed, policy
        assert v.eligible is False, policy


# --------------------------------------------------------------------------- best_dev_eligible


def test_best_dev_eligible_keeps_its_contract_on_the_derived_verdict(conn):
    _method(conn)
    with conn:
        ns = store.insert_trials(conn, [
            _trial(candidate_id="M0001-A", config_digest="da", mar=0.9, sharpe=0.94,
                   n_trials_at_run=5),
            _trial(candidate_id="M0001-B", config_digest="db", mar=0.9, sharpe=1.46,
                   n_trials_at_run=5),
            _trial(candidate_id="M0001-C", config_digest="dc", mar=1.4, max_drawdown=0.245,
                   failed="max DD <= 15%; DSR >= 0.95", sharpe=1.10,
                   n_trials_at_run=5),  # top MAR, owner fail
            _trial(candidate_id="M0001-D", config_digest="dd", mar=None, sharpe=0.80,
                   n_trials_at_run=5),
            _trial(candidate_id="M0001-E", config_digest="de", window="test", mar=2.0,
                   n_trials_at_run=5),
        ])
        for n in ns:
            _moments(conn, n, sr_daily=0.0595, t=3900, var_trials=2.395e-04, n_at_run=5)
    best = store.best_dev_eligible(conn, "M0001")
    # The tie between A and B breaks on n; C has the highest MAR but fails max DD, which no
    # threshold re-decides; D has no MAR; E is a test trial.
    assert best["candidate_id"] == "M0001-A"
    assert store.best_dev_eligible(conn, "M0002") is None


def test_best_dev_eligible_skips_a_trial_whose_luck_test_cannot_be_evaluated(conn):
    """A NULL `dsr` is never the answer, however good its MAR: it failed the luck test."""
    _method(conn)
    with conn:
        store.insert_trials(conn, [
            _trial(candidate_id="M0001-A", config_digest="da", mar=0.9, dsr=0.9156,
                   sharpe=0.945, failed="DSR >= 0.95", n_trials_at_run=2),
            _trial(candidate_id="M0001-C", config_digest="dc", mar=1.4, dsr=None,
                   sharpe=0.70, failed="DSR >= 0.95", n_trials_at_run=2),
        ])
    best = store.best_dev_eligible(conn, "M0001", at=store.Gate(n=2, policy="all-trials"))
    assert best["candidate_id"] == "M0001-A"   # C has the higher MAR and no evaluable DSR


# --------------------------------------------------------------------------- the one new edge


def _luck_only_method(conn, mid="M0001"):
    """A rejected method with one luck-only dev trial that clears 0.90 but not 0.95.

    The ``_ballast`` row beside it fails on a 24.5% drawdown -- outside even the owner's new 20%
    bar -- so it never joins ``unblocked``; it is there to give the lab two dev Sharpes, which is
    what ``dev_sharpe_variance`` needs before any DSR can be evaluated at all.
    """
    _method(conn, mid)
    with conn:
        store.update_method(conn, mid, status="registered")
        store.update_method(conn, mid, status="rejected")
        store.insert_trials(conn, [
            _trial(method_id=mid, candidate_id=f"{mid}-A", config_digest=f"d{mid}",
                   dsr=0.9156, sharpe=0.94, failed="DSR >= 0.95", n_trials_at_run=2),
            _ballast(mid),
        ])


def test_reevaluate_takes_the_edge_for_a_luck_only_rejection(conn):
    _luck_only_method(conn)
    with conn:
        r = store.reevaluate_method(conn, "M0001")
    assert r.moved is True
    assert r.status_before == "rejected" and r.status_after == "dev-eligible"
    assert r.unblocked == ("M0001-A",)
    assert store.get_method(conn, "M0001")["status"] == "dev-eligible"
    analysis = store.get_method(conn, "M0001")["analysis"]
    assert store.REEVALUATION_MARKER in analysis
    assert store.DSR_LABEL in analysis and f"N = {r.gate.n}" in analysis
    assert "M0001-A" in analysis
    # the trial that decided the rejection is untouched, label and all
    row = conn.execute(
        "SELECT * FROM trials WHERE candidate_id = 'M0001-A'").fetchone()
    assert row["eligible"] == 0 and row["failed"] == "DSR >= 0.95"
    assert row["dsr"] == pytest.approx(0.9156) and row["n_trials_at_run"] == 2


def test_reevaluate_will_not_move_a_method_that_failed_an_owner_condition(conn):
    _method(conn, "M0002")
    with conn:
        store.update_method(conn, "M0002", status="registered")
        store.update_method(conn, "M0002", status="rejected")
        store.insert_trials(conn, [
            _trial(method_id="M0002", candidate_id="M0002-A", max_drawdown=0.245, dsr=0.9156,
                   sharpe=0.94, failed="max DD <= 15%; DSR >= 0.95", n_trials_at_run=2),
            _ballast("M0002", candidate_id="M0002-SPREAD", config_digest="spread2",
                     max_drawdown=0.30),
        ])
        r = store.reevaluate_method(conn, "M0002")
    # Its DSR clears 0.90 at the gate's N -- the drawdown is the one and only reason it stays.
    row = conn.execute("SELECT * FROM trials WHERE candidate_id = 'M0002-A'").fetchone()
    v = store.verdict(conn, row, at=store.Gate(n=2, policy="all-trials"))
    assert v.derived is True and v.dsr == pytest.approx(0.9156, abs=1e-12)
    assert r.moved is False and r.unblocked == ()
    assert store.get_method(conn, "M0002")["status"] == "rejected"


def test_reevaluate_does_move_a_method_the_moved_drawdown_bar_unblocks(conn):
    """The counterpart, and the shape ``M0020-W-NOSTOP`` has on the committed database.

    A recorded failure of ``max DD <= 15%; DSR >= 0.95`` is **not** a reason to refuse the edge
    any more: the owner moved both of those bars on 2026-10-07, and a trial at 19.3% drawdown is
    inside the one in force now. The earlier draft's rule -- "only a rejection that was the luck
    label alone may be reconsidered" -- would have frozen this method out for ever.
    """
    _method(conn, "M0004")
    with conn:
        store.update_method(conn, "M0004", status="registered")
        store.update_method(conn, "M0004", status="rejected")
        store.insert_trials(conn, [
            _trial(method_id="M0004", candidate_id="M0004-A", config_digest="d4",
                   max_drawdown=0.193, dsr=0.9134, sharpe=0.94,
                   failed="max DD <= 15%; DSR >= 0.95", n_trials_at_run=2),
            _ballast("M0004"),
        ])
        r = store.reevaluate_method(conn, "M0004")
    assert r.moved is True and r.unblocked == ("M0004-A",)
    assert store.get_method(conn, "M0004")["status"] == "dev-eligible"
    row = conn.execute("SELECT * FROM trials WHERE candidate_id = 'M0004-A'").fetchone()
    assert row["failed"] == "max DD <= 15%; DSR >= 0.95"   # the record is untouched
    assert row["eligible"] == 0


def test_reevaluate_refuses_outright_if_a_verdict_contradicts_the_record(conn, monkeypatch):
    """The second, independent no.

    ``verdict`` cannot produce this state -- it derives the same four conditions from the same
    columns -- so the only way to reach the guard is to replace ``verdict``. That is the point:
    ``_blocking`` is written separately so that a future change to ``owner_failures`` or to
    ``verdict`` cannot quietly promote a method whose recorded numbers do not clear the bars.

    24.5% is outside today's 20% bar, so this is a genuine drawdown failure and not a stale label.
    """
    _method(conn, "M0003")
    with conn:
        store.update_method(conn, "M0003", status="registered")
        store.update_method(conn, "M0003", status="rejected")
        store.insert_trials(conn, [
            _trial(method_id="M0003", candidate_id="M0003-A", max_drawdown=0.245,
                   failed="max DD <= 15%; DSR >= 0.95", n_trials_at_run=1),
        ])
    monkeypatch.setattr(
        store, "verdict",
        lambda c, t, **kw: store.Verdict(0.99, (), True, 1, "all-trials", True),
    )
    with pytest.raises(store.LabError, match="second, independent check"):
        with conn:
            store.reevaluate_method(conn, "M0003")
    assert store.get_method(conn, "M0003")["status"] == "rejected"


def test_the_independent_check_refuses_a_recorded_owner_inputs_whatever_the_verdict_says(conn):
    """``owner inputs`` is the one condition no constant re-decides, and the one ``_blocking``
    reads out of the recorded string rather than out of a column."""
    _method(conn, "M0005")
    with conn:
        store.update_method(conn, "M0005", status="registered")
        store.update_method(conn, "M0005", status="rejected")
        store.insert_trials(conn, [
            _trial(method_id="M0005", candidate_id="M0005-A", config_digest="d5", dsr=0.9156,
                   sharpe=0.94, failed=f"{store.OWNER_INPUTS_LABEL}; DSR >= 0.95",
                   n_trials_at_run=2),
            _ballast("M0005"),
        ])
    # verdict already refuses it: `owner inputs` is carried from the record, and it is the ONLY
    # reason -- its DSR of 0.9156 clears 0.90 at the gate's N.
    row = conn.execute("SELECT * FROM trials WHERE candidate_id = 'M0005-A'").fetchone()
    v = store.verdict(conn, row, at=store.Gate(n=2, policy="all-trials"))
    assert v.derived is True and v.dsr == pytest.approx(0.9156, abs=1e-12)
    assert v.failed == (store.OWNER_INPUTS_LABEL,)
    with conn:
        assert store.reevaluate_method(conn, "M0005").moved is False
    # ...and so does the independent check, if verdict ever stopped.
    assert store.OWNER_INPUTS_LABEL in "; ".join(store._blocking(row))


def test_reevaluate_is_idempotent_and_moves_only_from_rejected(conn):
    _luck_only_method(conn)
    with conn:
        assert store.reevaluate_method(conn, "M0001").moved is True
    before = store.get_method(conn, "M0001")["analysis"]
    with conn:
        again = store.reevaluate_method(conn, "M0001")
    assert again.moved is False and again.status_before == "dev-eligible"
    assert store.get_method(conn, "M0001")["analysis"] == before


def test_reevaluate_sweeps_every_rejected_method(conn):
    _luck_only_method(conn, "M0001")
    _method(conn, "M0002")
    with conn:
        store.update_method(conn, "M0002", status="rejected")  # dropped before running
        results = store.reevaluate(conn)
    assert {r.method_id for r in results} == {"M0001", "M0002"}
    assert [r.method_id for r in results if r.moved] == ["M0001"]
    assert [r for r in results if r.method_id == "M0002"][0].dev_trials == 0


# --------------------------------------------------------------------------- the projection


def test_pending_gate_reproduces_todays_n_under_the_shipped_policy(conn, monkeypatch):
    _method(conn, "M0001")
    with conn:
        store.insert_trials(conn, [_trial(method_id="M0001", candidate_id="M0001-A")])
    assert store.DSR_POLICY == "all-trials"
    # exactly the expression runner.trial_rows used before this phase
    assert store.pending_gate(conn, "M0001", 3).n == store.dev_trial_count(conn) + 3
    assert store.pending_gate(conn, "M0009", 3).n == store.dev_trial_count(conn) + 3
    assert store.pending_gate(conn, "M0009", 0).n == store.gate(conn).n
    monkeypatch.setattr(store, "DSR_POLICY", "methods")
    assert store.pending_gate(conn, "M0001", 3).n == store.gate(conn).n      # known method
    assert store.pending_gate(conn, "M0009", 3).n == store.gate(conn).n + 1  # new method
    for policy in npolicy.POLICIES:
        monkeypatch.setattr(store, "DSR_POLICY", policy)
        assert store.pending_gate(conn, "M0009", 5).n >= store.gate(conn).n, policy


def test_the_gate_is_resolved_once_per_dev_trial_set(conn, monkeypatch):
    """The estimator is an eigendecomposition over every recorded curve; `lab status` walks 23
    methods. Both the memo and the explicit `at=` must keep that to one call."""
    from seer_engine.lab import npolicy

    _method(conn)
    with conn:
        store.insert_trials(conn, [
            _trial(candidate_id="M0001-A", config_digest="da", mar=0.9, n_trials_at_run=2),
            _trial(candidate_id="M0001-B", config_digest="db", mar=0.8, sharpe=1.46,
                   n_trials_at_run=2),
        ])
    store._GATE_CACHE.clear()
    calls = []
    real = npolicy.effective_n
    monkeypatch.setattr(
        npolicy, "effective_n", lambda c, p: (calls.append(p), real(c, p))[1]
    )
    for _ in range(5):
        store.gate(conn)
    assert len(calls) == 1, "the memo did not hold"
    # ...and it invalidates on an insert, because the key is the dev trial set.
    with conn:
        store.insert_trials(conn, [
            _trial(candidate_id="M0001-C", config_digest="dc", mar=0.7, n_trials_at_run=3),
        ])
    store.gate(conn)
    assert len(calls) == 2, "the memo did not invalidate"
    # The explicit route resolves once regardless of the cache.
    store._GATE_CACHE.clear()
    calls.clear()
    g = store.gate(conn)
    for _ in range(5):
        store.best_dev_eligible(conn, "M0001", at=g)
    assert len(calls) == 1


# --------------------------------------------------------------------------- the committed lab

# The four recorded columns of all 110 trials on `lab/lab.sqlite`, hashed. This phase derives a
# verdict and never writes one, so this digest is a constant for the life of the current rows:
#     SELECT n, dsr, eligible, failed, n_trials_at_run FROM trials ORDER BY n
# hashing `repr(row)` of each sqlite3 tuple into one sha256.
RECORDED_VERDICT_DIGEST = "166ae36bdc4425cebd7380b0187f9c21dc7726d502fe999bd7746e60bc974016"


def _recorded_digest(conn) -> str:
    h = hashlib.sha256()
    for row in conn.execute(
        "SELECT n, dsr, eligible, failed, n_trials_at_run FROM trials ORDER BY n"
    ):
        h.update(repr(tuple(row)).encode())
    return h.hexdigest()


@pytest.fixture()
def committed(tmp_path):
    """A writable copy of the committed lab, migrated. The original is never opened for writing."""
    if not store.COMMITTED_DB.exists():
        pytest.skip("no committed lab database")
    path = tmp_path / "lab.sqlite"
    shutil.copyfile(store.COMMITTED_DB, path)
    c = store.connect(path)
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def test_the_shipped_defaults_reproduce_todays_n(committed):
    """Nobody should have to reason about which module's default wins."""
    assert store.DSR_POLICY == "all-trials"
    g = store.gate(committed)
    assert g.policy == "all-trials"
    assert g.n == 110 == store.dev_trial_count(committed)


def test_the_committed_lab_keeps_every_recorded_verdict_and_spends_no_look(committed):
    assert committed.execute("SELECT count(*) FROM trials").fetchone()[0] == 110
    assert _recorded_digest(committed) == RECORDED_VERDICT_DIGEST
    assert store.test_looks(committed) == 0
    assert committed.execute(
        "SELECT 1 FROM transitions WHERE src = 'rejected' AND dst = 'dev-eligible'"
    ).fetchone() is not None


def test_the_two_moved_bars_unblock_exactly_m0022_and_m0020(committed):
    """R1 + R5, measured. At (N=110, DSR >= 0.90, max DD <= 20%) **three** candidates clear.

    Two of them are M0022's, admitted by the luck threshold the owner moved (D1). The third is
    `M0020-W-NOSTOP`, admitted by the drawdown threshold the owner moved (D6, phase 8): 19.3% is
    outside the old 15% bar and inside the new 20% one, and its DSR of 0.913 clears 0.90.
    """
    from seer_engine.backtest import tuning

    assert store.DSR_MIN == 0.90 and tuning.MAX_DRAWDOWN == 0.20
    # This phase migrates the committed database (Decision D5, Step 10), so by the time this
    # test runs on a landed branch M0020 and M0022 already read `dev-eligible` and there is no
    # edge left to take. Which methods the two moved bars UNBLOCK is the claim either way: it is
    # the set that is `rejected` before and `dev-eligible` after, and on an already-migrated
    # database that set is empty because the move has happened. The eligible-trial assertions
    # below are unconditional and are where R1 and R5 actually live.
    was_rejected = sorted(
        str(r[0]) for r in committed.execute(
            "SELECT id FROM methods WHERE status = 'rejected' AND id IN ('M0020', 'M0022')")
    )
    with committed:
        results = store.reevaluate(committed)
    assert sorted(r.method_id for r in results if r.moved) == was_rejected
    assert store.get_method(committed, "M0020")["status"] == "dev-eligible"
    assert store.get_method(committed, "M0022")["status"] == "dev-eligible"
    g = store.gate(committed)
    eligible = [
        row["candidate_id"]
        for row in committed.execute("SELECT * FROM trials WHERE window = 'dev' ORDER BY n")
        if store.verdict(committed, row, at=g).eligible
    ]
    assert sorted(eligible) == ["M0020-W-NOSTOP", "M0022-W-TV14", "M0022-W-TV16"]
    assert len(eligible) == 3, (
        "three, not four: M0007-N20-RAW's recorded 0.9138 was computed at N = 85 and is 0.8985 "
        "at today's N = 110 (Decision D8). If this reads four, verdict is taking a recorded DSR "
        "at face value again."
    )
    # MAR decides, not DSR: W-TV14 is MAR 0.857 / DSR 0.912, W-TV16 is MAR 0.816 / DSR 0.916.
    best = store.best_dev_eligible(committed, "M0022")
    assert best["candidate_id"] == "M0022-W-TV14"
    assert best["mar"] == pytest.approx(0.8567, abs=1e-3)
    assert store.best_dev_eligible(committed, "M0020")["candidate_id"] == "M0020-W-NOSTOP"
    # nothing recorded moved, and no look was spent
    assert _recorded_digest(committed) == RECORDED_VERDICT_DIGEST
    assert store.test_looks(committed) == 0


def test_the_three_near_misses_that_still_do_not_qualify(committed):
    """Each of the three fails for a different, named reason -- and none of them is a stale label.

    This is the test that says the two moved bars did not become a general amnesty.
    """
    from seer_engine.backtest import dev, tuning

    g = store.gate(committed)
    rows = {
        r["candidate_id"]: r
        for r in committed.execute("SELECT * FROM trials WHERE window = 'dev'")
    }

    # 1. **The one trial where the recorded number and the current bar disagree.**
    #    M0007-N20-RAW clears the NEW drawdown bar (19.6% <= 20%) and passes every owner
    #    condition. Its RECORDED dsr is 0.9138, which is above 0.90 -- so reading the recorded
    #    column would admit it. RE-EVALUATED at today's N = 110 it is 0.8985, which is not.
    #    The gate uses the re-evaluated number (Decision D8), so it stays out.
    m7 = rows["M0007-N20-RAW"]
    assert float(m7["max_drawdown"]) <= tuning.MAX_DRAWDOWN
    assert store.owner_failures(m7) == ()                      # every owner condition clears
    assert int(m7["n_trials_at_run"]) == 85
    assert float(m7["dsr"]) == pytest.approx(0.9138, abs=1e-3)  # recorded, at N = 85: ABOVE 0.90
    assert store.dsr_at(committed, m7, g.n) == pytest.approx(0.8985, abs=1e-3)  # at N=110: below
    assert store.verdict(committed, m7, at=g).eligible is False
    assert store.get_method(committed, "M0007")["status"] != "dev-eligible"

    # 2. M0019-RAW20-S25 is outside even the new bar, at 20.7%.
    m19 = rows["M0019-RAW20-S25"]
    assert float(m19["max_drawdown"]) > tuning.MAX_DRAWDOWN
    assert store.owner_failures(m19) == (dev.FAILURE_LABELS[1],)
    assert store.verdict(committed, m19, at=g).eligible is False

    # 3. M0001-TV10 does not beat SPY TR, which no threshold in this plan set moves.
    m1 = rows["M0001-TV10"]
    assert dev.FAILURE_LABELS[0] in store.owner_failures(m1)
    assert store.verdict(committed, m1, at=g).eligible is False


def test_f3_stays_ineligible_on_owner_inputs_whatever_its_luck_test_says(committed):
    """**F3 is the owner-inputs case, not the NULL-DSR case** -- and that is unconditional.

    `F3-SEC-TOP3-6M-TREND`'s recorded `failed` is `"max DD <= 15%; owner inputs"`. Phase 8's bar
    clears the drawdown half (19.5% <= 20%); `owner inputs` is the one D8 condition that is not a
    threshold, that no constant re-decides, and that `owner_failures` therefore **carries** from
    the recorded string rather than re-deriving. So F3 is ineligible on owner inputs alone,
    **independently of its luck test** -- before phase 9 gives it moments and after.

    This test takes no view on F3's DSR and must never be given one; the NULL-DSR rule is pinned
    on F9 below, where it is the *only* reason.
    """
    f3 = committed.execute(
        "SELECT * FROM trials WHERE candidate_id = 'F3-SEC-TOP3-6M-TREND'"
    ).fetchone()
    assert float(f3["max_drawdown"]) == pytest.approx(0.1951, abs=1e-3)
    assert store.owner_failures(f3) == (store.OWNER_INPUTS_LABEL,), (
        "the drawdown half clears at 20%; `owner inputs` is carried and is the whole reason"
    )
    v3 = store.verdict(committed, f3, at=store.gate(committed))
    assert store.OWNER_INPUTS_LABEL in v3.failed
    assert v3.eligible is False
    with committed:
        assert store.reevaluate_method(committed, "H-P7A-F3").moved is False


def test_f9_the_one_seed_row_held_out_by_the_luck_test_alone(committed):
    """**The P7a seed trap, on the real data, in its purest case.**

    `F9-SPY200M70-MOM30` passes **all five** owner conditions once the drawdown bar is 20%
    (fall 19.2%, MAR 0.635). Before the drawdown change the recorded 15% bar kept it out and
    nobody had to think about its missing DSR. At 20% a `verdict` that read a NULL DSR as "no luck
    failure" would admit it on a luck test that was never run. The NULL-DSR rule is the only thing
    holding it, which is what makes it the right pin for that rule.

    **This test describes the lab as phase 4 finds it, not a permanent fact about this trial.**
    Phase 9 (`lab remeasure` over the P7a seed, Decision D7) recovers its moments, at which point
    `dsr_at` takes route 1 and it gets a real luck verdict. Measured by phase 9, under Decision
    D12's today's-variance rule that `dsr_at` applies, that verdict is **0.8567 at N = 110** --
    still under 0.90, so F9 stays ineligible either way, but afterwards on a luck test it
    *received* rather than on a data gap. That is R6.

    The *rule* under test here is unchanged by phase 9 and is the point: a trial with no evaluable
    luck test fails it. Phase 9 does not change the rule; it stops the rule applying to this row
    by giving it something to evaluate. If this test fails after phase 9 has been run against the
    committed database, re-point it at a fixture rather than weakening the rule.
    """
    if committed.execute(
        "SELECT count(*) FROM trial_moments m JOIN trials t ON t.n = m.trial_n "
        "WHERE t.candidate_id = 'F9-SPY200M70-MOM30'"
    ).fetchone()[0]:
        pytest.skip("phase 9 has luck-tested the seed; this row now has moments")
    g = store.gate(committed)
    f9 = committed.execute(
        "SELECT * FROM trials WHERE candidate_id = 'F9-SPY200M70-MOM30'"
    ).fetchone()
    assert f9["dsr"] is None and float(f9["max_drawdown"]) == pytest.approx(0.1924, abs=1e-3)
    assert store.owner_failures(f9) == (), "at 20% it misses no owner condition"
    assert store.dsr_at(committed, f9, g.n) is None
    v9 = store.verdict(committed, f9, at=g)
    assert v9.failed == (store.DSR_LABEL,) and v9.eligible is False
    with committed:
        assert store.reevaluate_method(committed, "H-P7A-F9").moved is False


def test_m0011_stays_rejected_so_rm_and_rmw_diverge_on_purpose(committed):
    """RMW-FR becomes lab-eligible; RM-FR does not. The asymmetry is the measurement, not a bug.

    **Decision D8's quoting convention, as an assertion.** The RECORDED value at the RECORDED N
    is 0.8974 -- already under the new 0.90 bar on its own terms. The number the GATE uses is the
    one re-evaluated at today's N = 110, which is 0.884: further under. Both are true, they are
    different statements about the same trial, and they differ by more than the margin the gate
    decides by, which is why neither is ever quoted bare.

    (An earlier draft of this phase asserted `derived is False` and `v.n == 90` here, on the
    superseded rule that a trial recorded at another N was returned verbatim. That rule is gone:
    `verdict` evaluates every trial's DSR at the gate's N, which is what D11 settled and what the
    index's R2 requires. The assertions below are the reconciled design's, and they pin the
    re-evaluated number the index itself quotes.)
    """
    with committed:
        store.reevaluate(committed)
    assert store.get_method(committed, "M0011")["status"] == "rejected"
    assert store.get_method(committed, "M0022")["status"] == "dev-eligible"
    row = committed.execute(
        "SELECT * FROM trials WHERE candidate_id = 'M0011-RAW20-TV14-N21'"
    ).fetchone()
    assert row["dsr"] == pytest.approx(0.8974, abs=1e-3)   # recorded...
    assert row["n_trials_at_run"] == 90                    # ...at the recorded N
    g = store.gate(committed)
    v = store.verdict(committed, row)
    assert v.derived is True           # its DSR is evaluable, and it was evaluated
    assert v.n == g.n == 110           # at the GATE's N, not the recorded one
    assert v.dsr == pytest.approx(0.884, abs=1e-3)   # re-evaluated: further under the bar
    assert v.eligible is False


def test_no_candidate_that_fails_a_condition_at_todays_bars_becomes_eligible(committed):
    """The owner conditions bind under every N policy. Note the argument: ``owner_failures`` takes
    the **row**, so this asks what each trial is today, not what its recorded string says."""
    g = store.gate(committed)
    for row in committed.execute("SELECT * FROM trials WHERE window = 'dev'"):
        if store.owner_failures(row):
            assert store.verdict(committed, row, at=g).eligible is False, row["candidate_id"]
            for policy in npolicy.POLICIES:
                assert store.verdict(committed, row, policy=policy).eligible is False, (
                    row["candidate_id"], policy)
    # The two that still fail an owner condition at today's bars, and must never be admitted at
    # any N. (M0007-N20-RAW is no longer one of them -- it now clears every owner condition and
    # fails only the luck test; see test_the_three_near_misses_that_still_do_not_qualify.)
    for cid, index in (("M0019-RAW20-S25", 1), ("M0001-TV10", 0)):
        from seer_engine.backtest import dev

        row = committed.execute("SELECT * FROM trials WHERE candidate_id = ?", (cid,)).fetchone()
        assert dev.FAILURE_LABELS[index] in store.owner_failures(row), cid
        for policy in npolicy.POLICIES:
            assert store.verdict(committed, row, policy=policy).eligible is False, (cid, policy)


# --- the N-sensitivity regression, on reconstructed moments --------------------------------


def _sr_star(var: float, n: int) -> float:
    nd = NormalDist()
    return math.sqrt(var) * (
        (1 - _EULER_GAMMA) * nd.inv_cdf(1 - 1 / n) + _EULER_GAMMA * nd.inv_cdf(1 - 1 / (n * math.e))
    )


def _reconstruct_moments(conn) -> int:
    """Write a ``trial_moments`` row for every recorded dev trial that has a DSR; return the count.

    **A reconstruction, not a measurement** -- the rows are written ``measured = "reconstruction"``.
    ``lab remeasure`` (phase 3) recovers the real ``(t, skew, kurt)`` by re-running the dev
    window, which these tests cannot do. Instead: ``sr_daily`` is the recorded annualized Sharpe
    over sqrt(252), ``skew`` and ``kurt`` are pinned at the normal values, and ``t`` is solved so
    the row reproduces its own recorded DSR at its own recorded N -- verified here to 2e-5.

    **The variance it solves against is ``store.dev_sharpe_variance(conn)`` -- today's -- not the
    variance in force on the trial's run date.** That is the same variance ``store.dsr_at`` uses
    on both of its routes, and using it here is what makes the two routes comparable at all:
    solving ``t`` against a stale variance and then evaluating against today's would put the two
    routes up to **0.098** apart on the committed lab, which is eleven times the margin the gate
    is deciding by. Solved this way they agree to **1.3e-5**
    (``test_the_two_routes_to_a_dsr_agree``).

    That is enough to prove this phase's claims about N and the threshold, and nothing about the
    real higher moments. The solved ``t`` is the visible sign that it is a fit and not a
    measurement.
    """
    rows = conn.execute("SELECT * FROM trials WHERE window = 'dev' ORDER BY n").fetchall()
    var = store.dev_sharpe_variance(conn)
    assert var is not None
    nd = NormalDist()
    written = 0
    for r in rows:
        if r["dsr"] is None or r["sharpe"] is None:
            continue  # the 54 P7a seed trials: dsr IS NULL by construction (seed.py)
        n0 = int(r["n_trials_at_run"])
        sr = float(r["sharpe"]) / math.sqrt(252)
        k = nd.inv_cdf(float(r["dsr"])) / (sr - _sr_star(var, n0))
        t = round(1 + k * k * (1 + sr * sr / 2))  # skew 0, kurt 3 => radicand = 1 + sr^2/2
        _moments(conn, int(r["n"]), sr_daily=sr, t=t, var_trials=var, n_at_run=n0)
        assert deflated_sharpe(sr, n0, var, t, 0.0, 3.0) == pytest.approx(
            float(r["dsr"]), abs=2e-5
        ), r["candidate_id"]
        written += 1
    return written


def test_the_two_routes_to_a_dsr_agree(committed):
    """``dsr_at``'s two routes are one number.

    Route 2 (invert the recorded DSR and re-evaluate at the gate's N) and route 1 (recompute
    exactly from ``trial_moments``) must agree on every trial, not only on the ones whose
    recorded N is already the gate's. That agreement is what makes route 2 a *re-reading* of the
    record rather than a second opinion about it -- and it is what lets the gate judge all 56
    lab-method trials today, with ``lab remeasure`` an exactness upgrade rather than a
    precondition.
    """
    rows = committed.execute(
        "SELECT * FROM trials WHERE window = 'dev' AND dsr IS NOT NULL ORDER BY n"
    ).fetchall()
    assert rows
    g = store.gate(committed)
    before = {r["candidate_id"]: store.verdict(committed, r, at=g) for r in rows}
    assert all(v.derived for v in before.values()), "every recorded DSR is evaluable at the gate"
    with committed:
        _reconstruct_moments(committed)
    for r in rows:
        after = store.verdict(committed, r, at=g)
        assert after.derived
        assert after.dsr == pytest.approx(before[r["candidate_id"]].dsr, abs=2e-4), (
            r["candidate_id"])
        assert after.eligible == before[r["candidate_id"]].eligible, r["candidate_id"]


def test_dsr_at_deflates_by_todays_variance_not_the_one_recorded_beside_the_trial(conn):
    """**Decision D12, as an assertion.** The pin that stops this fork being re-opened.

    `trial_moments.var_trials` is the trial-Sharpe variance that was in force when the trial ran.
    It is kept as history and is **never** an input to a live verdict: `dsr_at` deflates by
    `dev_sharpe_variance(conn)` -- today's -- on both routes, read once above the branch.

    Phase 9 is where the difference bites. On the 54 P7a seed rows the recorded variance
    (2.006691e-04, the P7a search's own) and today's (2.395048e-04, all 110 dev trials) move
    `F9-SPY200M70-MOM30` from 0.903053 to 0.856651 -- across the 0.90 bar. Rung 4, the index's R2:
    the hurdle is `sqrt(var_trials) x E[max over N]`, so pairing today's N with a run-date
    variance freezes half the hurdle at the run date and reintroduces the very incoherence R2
    exists to remove. This is the same principle, and must stay the same answer, as D11's refusal
    to use `n_trials_at_run`.
    """
    from seer_engine.backtest import dev

    _method(conn)
    with conn:
        # Two trials with DIFFERENT Sharpes, so the fixture lab has a real, non-zero variance.
        a, b = store.insert_trials(conn, [
            _trial(candidate_id="M0001-A", config_digest="da", sharpe=0.94, n_trials_at_run=2),
            _trial(candidate_id="M0001-B", config_digest="db", sharpe=1.46, n_trials_at_run=2),
        ])
        # ...and a moments row whose recorded var_trials is deliberately a DIFFERENT number.
        _moments(conn, a, sr_daily=0.0595, t=3900, var_trials=9.9e-04, n_at_run=2)
    row = conn.execute("SELECT * FROM trials WHERE candidate_id = 'M0001-A'").fetchone()
    today = store.dev_sharpe_variance(conn)
    assert today is not None and today != pytest.approx(9.9e-04)

    got = store.dsr_at(conn, row, 110)
    want_today = dev.deflated_sharpe(0.0595, 110, today, 3900, 0.0, 3.0)
    want_recorded = dev.deflated_sharpe(0.0595, 110, 9.9e-04, 3900, 0.0, 3.0)
    assert want_today != pytest.approx(want_recorded), "the fixture must separate the two"
    assert got == pytest.approx(want_today), (
        "dsr_at read the stored var_trials again; it must deflate by dev_sharpe_variance (D12)"
    )
    assert got != pytest.approx(want_recorded)
    # ...and the recorded column is still there, untouched, as history.
    assert float(store.moments_of(conn, a)["var_trials"]) == pytest.approx(9.9e-04)


def test_the_old_bars_reproduce_todays_verdicts(committed, monkeypatch):
    """Decisions D1's and D6's reversal clause, as a test rather than a claim: put **all three**
    constants back -- the N policy, the luck bar and the drawdown bar -- and the lab reads exactly
    as it does on `main`, with no data change.

    The drawdown constant is in the list because this phase's `verdict` re-derives against it;
    leaving it at 20% would admit `M0020-W-NOSTOP` and the comparison would not be a comparison.
    """
    from seer_engine.backtest import dev, tuning

    monkeypatch.setattr(store, "DSR_POLICY", "all-trials")
    monkeypatch.setattr(store, "DSR_MIN", 0.95)
    monkeypatch.setattr(store, "DSR_LABEL", "DSR >= 0.95")
    monkeypatch.setattr(tuning, "MAX_DRAWDOWN", 0.15)
    monkeypatch.setattr(
        dev, "FAILURE_LABELS",
        ("beats SPY TR", "max DD <= 15%", "PF >= 1.3", ">= 100 trades", "owner inputs"),
    )
    with committed:
        assert _reconstruct_moments(committed) == 56  # the 54 seed rows have no DSR
        results = store.reevaluate(committed)
    assert store.gate(committed).n == 110
    assert [r.method_id for r in results if r.moved] == []
    g = store.gate(committed)
    for row in committed.execute("SELECT * FROM trials WHERE window = 'dev'"):
        v = store.verdict(committed, row, at=g)
        if v.derived:
            assert v.eligible == bool(row["eligible"]), row["candidate_id"]
    assert _recorded_digest(committed) == RECORDED_VERDICT_DIGEST
