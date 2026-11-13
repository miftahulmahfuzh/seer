"""The random-twin yardstick as a screen condition (RANDOM_TWIN_YARDSTICK_PLAN.md phase 4).

Three readers decide with it, and each is proven here by what a caller can see:

- ``lab run`` measures an arm that clears every other condition before it records it, and records
  it eligible only when it out-earned at least ``store.YARDSTICK_MIN_PERCENTILE`` of its twins
  (R2.1);
- ``store.verdict`` fails an arm whose reading is below the bar or ``unmatched``, and an arm
  recorded since ``store.YARDSTICK_SINCE`` that was never measured (R2.2, Decision D5);
- ``store._blocking`` says the same no a second time, in its own words, on the one door that
  reconsiders a verdict.

The ``lab promote`` refusal (hardgate D20, R2.3) is tested in ``test_lab_hardgate.py`` beside the
other clauses of ``check``, because it needs that file's fold fixtures.

Every ``lab run`` test injects ``measure`` through ``run_method``'s own parameter. What is under
test is what the run does with a reading, not how twins are drawn, which phase 2's
``test_lab_yardstick.py`` proves. One test runs the real engine at five draws to prove the two fit.
The smoke market rarely produces an arm that clears all six other conditions, so the tests that
need one pass the real simulations through ``_clear_every_other_condition``. It marks the chosen
arms D8-clean and sets the luck bar to zero; nothing else about the run is touched.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
from datetime import date
from pathlib import Path

import pytest
from labkit import smoke_data, stamp_yardstick

from seer_engine.backtest import dev as dev_module
from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.runner import INITIAL_IDR
from seer_engine.commands.backtest_dev import month_end_curve
from seer_engine.lab import control_shape, runner, store, yardstick
from seer_engine.lab.method import Method
from seer_engine.lab.seed import seed
from seer_engine.sim.contributions import OWNER_MONTHLY
from seer_engine.sim.rules import DAILY_SWITCH, MONTHLY_HOLD, MONTHLY_HOLD_FRAC
from seer_engine.strategies.f_factor import FACTOR, FactorParams
from seer_engine.strategies.f_index import TIMING, TimingParams

HERE = Path(__file__)
OLD = "2026-10-06T00:00:00+00:00"   # before the rule: judged by a reading once it has one
NEW = "2026-11-14T00:00:00+00:00"   # on YARDSTICK_SINCE: an unmeasured arm fails closed
GATE = store.Gate(n=2, policy="all-trials")
PF_LABEL = dev_module.FAILURE_LABELS[2]


# ------------------------------------------------------------------ fixtures


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    seed(c)
    yield c
    c.close()


@pytest.fixture()
def bare(tmp_path):
    """A lab with no seed rows, for the verdict tests: two fixture trials and nothing else."""
    c = store.connect(tmp_path / "bare.sqlite")
    yield c
    c.close()


@pytest.fixture(scope="module")
def data():
    return smoke_data()


def _cand(cid: str, *, n: int = 50, rules=MONTHLY_HOLD, rationale: str = "test") -> Candidate:
    return Candidate(
        id=cid, family="M0001", rules=rules, allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=n),
        rationale=rationale, added=date(2026, 11, 13), owner_inputs=(),
    )


CONTROL_RATIONALE = "Control: the same switch with the signal removed, registered to be beaten."


def _method(*cands: Candidate) -> Method:
    return Method(
        id="M0001", name="yardstick test", family="trend", source_kind="knowledge",
        source_ref="", hypothesis="h", expected_failure="f",
        candidates=tuple(cands) if cands else (_cand("M0001-A"),),
    )


def _clear_every_other_condition(monkeypatch, *, only=None, fail=()) -> None:
    """Pass the real simulations through, marking arms in ``only`` (all when None) D8-clean and
    arms in ``fail`` failing on profit factor, and set the luck bar to zero so any computable DSR
    clears it. What the run then does with a reading is the thing under test. ``beats_spy`` is
    set with the labels because ``DevRow`` refuses a row whose two disagree."""
    real = dev_module.run_registry

    def relayed(*args, on_result=None, **kwargs):
        def relay(i, result, row):
            if row.candidate.id in fail:
                row = dataclasses.replace(row, eligible=False, failed=(PF_LABEL,), beats_spy=True)
            elif only is None or row.candidate.id in only:
                row = dataclasses.replace(row, eligible=True, failed=(), beats_spy=True)
            on_result(i, result, row)

        return real(*args, on_result=relay, **kwargs)

    monkeypatch.setattr(dev_module, "run_registry", relayed)
    monkeypatch.setattr(store, "DSR_MIN", 0.0)


def _reading(status: str = yardstick.STATUS_MEASURED, percentile: float = 0.95,
             draws: int = 200) -> yardstick.Measurement:
    if status == yardstick.STATUS_NOT_APPLICABLE:
        return yardstick.Measurement(
            status=status, draws=0, arm_rate=0.12, beaten=0, percentile=None, rates=(),
            trade_ratio=None, turnover_ratio=None, reproduced=True,
        )
    beaten = int(round(percentile * draws))
    return yardstick.Measurement(
        status=status, draws=draws, arm_rate=0.12, beaten=beaten, percentile=beaten / draws,
        rates=tuple(0.05 + i * 1e-4 for i in range(draws)), trade_ratio=1.0,
        turnover_ratio=1.0, reproduced=True,
    )


class _Twins:
    """Stands in for ``yardstick.measure``: a fixed reading (or a raise), and a log of each call
    with whether the lab-wide write lock was held at that moment."""

    def __init__(self, conn, reading=None, *, raises: Exception | None = None):
        self.conn, self.reading, self.raises, self.calls = conn, reading, raises, []

    def __call__(self, market, dividends, spy_dividends, candidate, *, initial_idr,
                 contributions, draws=yardstick.DRAWS, jobs=1, expect=None):
        self.calls.append({
            "candidate": candidate.id, "initial_idr": initial_idr,
            "contributions": contributions, "jobs": jobs, "expect": expect,
            "locked": self.conn.in_transaction,
        })
        if self.raises is not None:
            raise self.raises
        return self.reading


def _run(conn, data, twins, method=None, **kw):
    return runner.run_method(
        conn, method or _method(), HERE, data, git_sha="deadbeef", require_commit=False,
        measure=twins, **kw,
    )


# ------------------------------------------------------------------ R2.1: `lab run`


def test_an_arm_that_loses_to_its_twins_is_recorded_not_eligible_and_rejects_its_method(
    conn, data, monkeypatch
):
    _clear_every_other_condition(monkeypatch)
    twins = _Twins(conn, _reading(percentile=0.60))
    (r,) = _run(conn, data, twins).ran
    assert store.recorded_labels(r.trial.failed) == (store.YARDSTICK_LABEL,)
    assert r.trial.eligible is False
    assert store.get_method(conn, "M0001")["status"] == "rejected"
    (row,) = store.trials_of(conn, "M0001")
    assert row["eligible"] == 0 and row["failed"] == store.YARDSTICK_LABEL
    reading = store.yardstick_of(conn, row["n"])
    assert reading is not None
    assert reading["percentile"] == pytest.approx(0.60)
    assert reading["store_fingerprint"] == data.fingerprint
    assert reading["rule_id"] == yardstick.RULE_ID
    # The read agrees with the record on the yardstick. (`verdict` re-derives the owner conditions
    # from the smoke market's real numbers, which `_clear_every_other_condition` only relabelled,
    # so only the yardstick's place in it is asserted; the R2.2 tests below pin the whole tuple.)
    assert store.verdict(conn, row).failed[-1] == store.YARDSTICK_LABEL


def test_an_arm_that_beats_its_twins_is_recorded_eligible(conn, data, monkeypatch):
    _clear_every_other_condition(monkeypatch)
    (r,) = _run(conn, data, _Twins(conn, _reading(percentile=0.95))).ran
    assert r.trial.failed == "" and r.trial.eligible is True
    assert store.get_method(conn, "M0001")["status"] == "dev-eligible"
    (row,) = store.trials_of(conn, "M0001")
    assert store.yardstick_of(conn, row["n"])["percentile"] == pytest.approx(0.95)
    # As above: the read adds no yardstick label to an arm whose reading clears.
    assert store.YARDSTICK_LABEL not in store.verdict(conn, row).failed


@pytest.mark.parametrize(
    ("status", "percentile", "eligible"),
    [
        (yardstick.STATUS_MEASURED, 0.900, True),     # the bar is "at least"
        (yardstick.STATUS_MEASURED, 0.895, False),    # 179 of 200
        (yardstick.STATUS_UNMATCHED, 0.990, False),   # unmatched never clears
        (yardstick.STATUS_NOT_APPLICABLE, 0.0, True),  # no picked stock, nothing to swap
    ],
)
def test_what_lab_run_records_for_each_reading(conn, data, monkeypatch, status, percentile,
                                               eligible):
    assert store.YARDSTICK_MIN_PERCENTILE == 0.90
    _clear_every_other_condition(monkeypatch)
    (r,) = _run(conn, data, _Twins(conn, _reading(status, percentile))).ran
    assert r.trial.eligible is eligible
    assert (store.YARDSTICK_LABEL in store.recorded_labels(r.trial.failed)) is (not eligible)
    (row,) = store.trials_of(conn, "M0001")
    assert store.yardstick_of(conn, row["n"])["status"] == status


def test_only_arms_that_clear_everything_else_and_are_not_controls_are_measured_before_the_lock(
    conn, data, monkeypatch
):
    method = _method(
        _cand("M0001-A"),
        _cand("M0001-B", rules=DAILY_SWITCH, n=20),
        _cand("M0001-C", n=30, rationale=CONTROL_RATIONALE),
    )
    assert control_shape.role_of(method.candidates[2]) == control_shape.ROLE_CONTROL
    _clear_every_other_condition(monkeypatch, only={"M0001-A", "M0001-C"}, fail={"M0001-B"})
    twins = _Twins(conn, _reading(percentile=0.95))
    ran = {r.trial.candidate_id: r for r in _run(conn, data, twins, method, yardstick_jobs=3).ran}

    assert [c["candidate"] for c in twins.calls] == ["M0001-A"]
    (call,) = twins.calls
    assert call["locked"] is False, "nothing slow may run under the lab-wide write lock"
    assert call["jobs"] == 3
    assert call["initial_idr"] == INITIAL_IDR and call["contributions"] is OWNER_MONTHLY
    a = ran["M0001-A"].trial
    assert call["expect"] == (a.trades, a.total_return)

    assert a.eligible is True
    assert store.recorded_labels(ran["M0001-B"].trial.failed) == (PF_LABEL,)
    control = store.recorded_labels(ran["M0001-C"].trial.failed)
    assert store.CONTROL_LABEL in control and store.YARDSTICK_LABEL not in control
    rows = {r["candidate_id"]: r["n"] for r in store.trials_of(conn, "M0001")}
    assert store.yardstick_of(conn, rows["M0001-A"]) is not None
    assert store.yardstick_of(conn, rows["M0001-B"]) is None
    assert store.yardstick_of(conn, rows["M0001-C"]) is None


def test_an_eligible_arm_left_unmeasured_is_recorded_with_the_label_and_the_way_back(
    conn, data, monkeypatch, caplog
):
    _clear_every_other_condition(monkeypatch)
    twins = _Twins(conn, raises=yardstick.Unreproducible("the re-run made 12 trades, the run 13"))
    with caplog.at_level(logging.INFO, logger=runner.__name__):
        (r,) = _run(conn, data, twins).ran
    assert store.recorded_labels(r.trial.failed) == (store.YARDSTICK_LABEL,)
    assert r.yardstick is None
    (row,) = store.trials_of(conn, "M0001")
    assert store.yardstick_of(conn, row["n"]) is None
    assert store.get_method(conn, "M0001")["status"] == "rejected"
    assert "`lab yardstick --arm M0001-A`" in caplog.text  # the form the CLI accepts
    assert "lab reevaluate M0001" in caplog.text


def test_a_run_with_nothing_eligible_measures_nothing(conn, data, monkeypatch):
    _clear_every_other_condition(monkeypatch, only=set(), fail={"M0001-A"})
    twins = _Twins(conn, _reading())
    (r,) = _run(conn, data, twins).ran
    assert twins.calls == []
    assert store.recorded_labels(r.trial.failed) == (PF_LABEL,)


def test_trial_rows_with_no_readings_records_what_it_always_did(conn, data):
    method = _method(_cand("M0001-A"), _cand("M0001-B", rules=DAILY_SWITCH, n=20))
    results = []
    dev_module.run_registry(
        data.market, data.dividends, data.spy_dividends, method.candidates,
        on_result=lambda i, res, row: results.append((row, month_end_curve(res.snapshots))),
        contributions=OWNER_MONTHLY, initial_idr=INITIAL_IDR,
    )
    before = runner.trial_rows(conn, method, results, fingerprint="smoke", git_sha="x")
    after = runner.trial_rows(conn, method, results, fingerprint="smoke", git_sha="x",
                              yardsticks=None)
    for a, b in zip(before, after, strict=True):
        assert (a.trial.failed, a.trial.eligible, a.trial.dsr) == (
            b.trial.failed, b.trial.eligible, b.trial.dsr)
        assert store.YARDSTICK_LABEL not in a.trial.failed
        assert a.yardstick is None and b.yardstick is None


def test_the_real_engine_measures_an_arm_inside_lab_run(conn, data, monkeypatch):
    """The fake above proves what the run does with a reading; this proves the real engine's
    reading fits the record. Five draws on the smoke market's eight member stocks. The arm is
    sent to the engine by replacing the filter with "any non-control arm", because a smoke-market
    arm rarely clears the six other conditions; the filter itself is proven above."""
    monkeypatch.setattr(
        runner, "_due_for_yardstick",
        lambda row, dsr: control_shape.role_of(row.candidate) != control_shape.ROLE_CONTROL,
    )
    picker = Candidate(
        id="M0001-LV", family="M0001", rules=MONTHLY_HOLD_FRAC, allocator=FACTOR,
        params=FactorParams(rank="lowvol", top=3, mom_n=60, mom_skip=0, vol_n=20, trend=None),
        rationale="test", added=date(2026, 11, 13), owner_inputs=(),
    )
    measure = functools.partial(yardstick.measure, draws=5)
    (r,) = runner.run_method(conn, _method(picker), HERE, data, git_sha="x",
                             require_commit=False, measure=measure).ran
    assert r.yardstick is not None
    (row,) = store.trials_of(conn, "M0001")
    reading = store.yardstick_of(conn, row["n"])
    assert reading["status"] in (yardstick.STATUS_MEASURED, yardstick.STATUS_UNMATCHED)
    assert reading["draws"] == 5
    assert reading["store_fingerprint"] == data.fingerprint
    labels = store.recorded_labels(r.trial.failed)
    if not [x for x in labels if x != store.YARDSTICK_LABEL]:
        assert (store.YARDSTICK_LABEL in labels) is (not store.yardstick_clears(reading))


# ------------------------------------------------------------------ R2.2: `store.verdict`


def _trial(**kw) -> store.TrialRow:
    """Clear of every owner condition, and of the luck test at ``GATE`` (N = 2 = n_trials_at_run,
    where ``dsr_at`` returns the recorded 0.97 exactly)."""
    base = dict(
        method_id="M0001", candidate_id="M0001-A", config_digest="d1", config_text="t",
        rules_id="MONTHLY_HOLD", allocator_id="TIMING", window="dev", start="1996-01-02",
        end="2015-10-16", store_fingerprint="fp", git_sha="abc", run_at=OLD,
        total_return=3.0, cagr=0.12, max_drawdown=0.11, profit_factor=1.6, trades=250,
        sharpe=0.9, exposure=0.95, turnover=1.1, worst_year=2008, worst_year_return=-0.1,
        spy_tr_return=2.0, spy_tr_cagr=0.08, mar=0.8, failed="", eligible=True, dsr=0.97,
        n_trials_at_run=2, curve_json="[]",
    )
    base.update(kw)
    return store.TrialRow(**base)


def _ballast() -> store.TrialRow:
    """A second dev trial so the lab has a trial-Sharpe variance; ineligible on its drawdown."""
    return _trial(candidate_id="M0001-BALLAST", config_digest="ballast", sharpe=1.46,
                  max_drawdown=0.55, mar=0.1, dsr=0.50, eligible=False, failed="max DD")


def _lab(conn, *trials: store.TrialRow, status: str = "registered") -> list[int]:
    with conn:
        store.add_method(conn, id="M0001", name="n", family="f", source_kind="knowledge",
                         hypothesis="h", status="registered")
        if status != "registered":
            store.update_method(conn, "M0001", status=status)
        ns = store.insert_trials(conn, [*trials, _ballast()])
    return list(ns[: len(trials)])


def _row(conn, n: int):
    return conn.execute("SELECT * FROM trials WHERE n = ?", (n,)).fetchone()


def test_an_old_arm_reads_eligible_until_a_failing_reading_is_recorded(bare):
    (n,) = _lab(bare, _trial())
    assert store.verdict(bare, _row(bare, n), at=GATE).eligible is True
    with bare:
        stamp_yardstick(bare, [n], percentile=0.50)
    v = store.verdict(bare, _row(bare, n), at=GATE)
    assert v.failed == (store.YARDSTICK_LABEL,) and v.eligible is False
    assert store.best_dev_eligible(bare, "M0001", at=GATE) is None


def test_an_unmatched_reading_fails_the_arm_whatever_its_percentile(bare):
    (n,) = _lab(bare, _trial())
    with bare:
        stamp_yardstick(bare, [n], status=yardstick.STATUS_UNMATCHED, percentile=0.99)
    assert store.verdict(bare, _row(bare, n), at=GATE).failed == (store.YARDSTICK_LABEL,)


@pytest.mark.parametrize(
    ("status", "percentile"),
    [(yardstick.STATUS_MEASURED, 0.90), (yardstick.STATUS_MEASURED, 1.0),
     (yardstick.STATUS_NOT_APPLICABLE, 0.0)],
)
def test_a_clearing_reading_adds_nothing(bare, status, percentile):
    (n,) = _lab(bare, _trial(run_at=NEW))
    with bare:
        stamp_yardstick(bare, [n], status=status, percentile=percentile)
    v = store.verdict(bare, _row(bare, n), at=GATE)
    assert v.failed == () and v.eligible is True


def test_an_arm_recorded_since_the_rule_and_never_measured_fails_closed(bare):
    assert store.YARDSTICK_SINCE == "2026-11-14"
    new, eve = _lab(
        bare,
        _trial(run_at=NEW),
        _trial(candidate_id="M0001-E", config_digest="d-eve", run_at="2026-11-13T23:59:59+00:00"),
    )
    assert store.verdict(bare, _row(bare, new), at=GATE).failed == (store.YARDSTICK_LABEL,)
    assert store.verdict(bare, _row(bare, eve), at=GATE).failed == ()


def test_an_unmeasured_new_arm_reads_only_its_real_failure(bare):
    (n,) = _lab(bare, _trial(run_at=NEW, profit_factor=1.1))
    assert store.verdict(bare, _row(bare, n), at=GATE).failed == (PF_LABEL,)


def test_the_yardstick_label_goes_last(bare):
    (n,) = _lab(bare, _trial(profit_factor=1.1, dsr=0.50))
    with bare:
        stamp_yardstick(bare, [n], percentile=0.10)
    failed = store.verdict(bare, _row(bare, n), at=GATE).failed
    assert failed[0] == PF_LABEL and store.DSR_LABEL in failed
    assert failed[-1] == store.YARDSTICK_LABEL


def test_a_control_arm_never_carries_the_yardstick_label(bare):
    (n,) = _lab(bare, _trial())
    with bare:
        store.insert_roles(bare, [store.RoleRow(trial_n=n, role="control", source="recorded",
                                                measured=OLD)])
        stamp_yardstick(bare, [n], percentile=0.10)
    failed = store.verdict(bare, _row(bare, n), at=GATE).failed
    assert store.CONTROL_LABEL in failed and store.YARDSTICK_LABEL not in failed


def test_a_test_window_row_never_reads_the_yardstick(bare):
    """A test look recorded since the rule, with no reading: a dev arm in that state fails closed,
    a look never does. (No reading can be stamped on a look at all: phase 3's
    ``insert_yardstick`` refuses a test-window trial, and its own test proves that.)"""
    (n,) = _lab(bare, _trial(window="test", candidate_id="M0001-T", run_at=NEW))
    assert store.yardstick_of(bare, n) is None
    v = store.published_verdict(bare, _row(bare, n), at=GATE)
    assert store.YARDSTICK_LABEL not in v.failed


def test_a_lab_with_no_role_no_reading_and_nothing_new_reads_as_before(bare):
    """Plan invariant 5: with no ``trial_roles`` row, no ``trial_yardstick`` row and no trial on
    or after ``YARDSTICK_SINCE``, every verdict is the six conditions and nothing else."""
    ns = _lab(
        bare,
        _trial(),
        _trial(candidate_id="M0001-PF", config_digest="d-pf", profit_factor=1.1),
        _trial(candidate_id="M0001-DD", config_digest="d-dd", max_drawdown=0.60),
        _trial(candidate_id="M0001-LUCK", config_digest="d-luck", dsr=0.50),
    )
    assert bare.execute("SELECT count(*) FROM trial_yardstick").fetchone()[0] == 0
    assert bare.execute("SELECT count(*) FROM trial_roles").fetchone()[0] == 0
    for n in ns:
        row = _row(bare, n)
        v = store.verdict(bare, row, at=GATE)
        luck = () if (v.dsr is not None and v.dsr >= store.DSR_MIN) else (store.DSR_LABEL,)
        assert v.failed == store.owner_failures(row, store.funding_of(bare, n)) + luck
        assert store.YARDSTICK_LABEL not in v.failed
    assert store.verdict(bare, _row(bare, ns[0]), at=GATE).eligible is True


def test_the_independent_check_says_no_in_its_own_words(bare):
    assert (yardstick.STATUS_MEASURED, yardstick.STATUS_NOT_APPLICABLE) == (
        "measured", "not-applicable"), "_blocking types these two literals on purpose"
    old, new = _lab(bare, _trial(),
                    _trial(candidate_id="M0001-N", config_digest="d-new", run_at=NEW))
    lost = {"status": "measured", "percentile": 0.5, "beaten": 100, "draws": 200}
    said = "; ".join(store._blocking(_row(bare, old), None, lost))
    assert "100 of 200 random twins" in said and "90%" in said
    odd = {"status": "unmatched", "percentile": 0.99, "beaten": 198, "draws": 200}
    assert "'unmatched'" in "; ".join(store._blocking(_row(bare, old), None, odd))
    clear = {"status": "not-applicable", "percentile": None, "beaten": 0, "draws": 0}
    assert store._blocking(_row(bare, old), None, clear) == ()
    assert store._blocking(_row(bare, old)) == ()
    assert store.YARDSTICK_SINCE in "; ".join(store._blocking(_row(bare, new)))


@pytest.fixture()
def at_all_trials(monkeypatch):
    monkeypatch.setattr(store, "DSR_POLICY", "all-trials")
    store._GATE_CACHE.clear()
    yield
    store._GATE_CACHE.clear()


def test_reevaluate_refuses_outright_when_the_verdict_ignores_a_failing_reading(
    bare, monkeypatch
):
    (n,) = _lab(bare, _trial(failed="DSR >= 0.95", eligible=False), status="rejected")
    with bare:
        stamp_yardstick(bare, [n], percentile=0.10)
    monkeypatch.setattr(
        store, "verdict", lambda c, t, **kw: store.Verdict(0.99, (), True, 2, "all-trials", True)
    )
    with pytest.raises(store.LabError, match="second, independent check") as e:
        with bare:
            store.reevaluate_method(bare, "M0001")
    assert "random twins" in str(e.value)
    assert store.get_method(bare, "M0001")["status"] == "rejected"


def test_reevaluate_does_not_unblock_an_old_arm_whose_reading_failed(bare, at_all_trials):
    (n,) = _lab(bare, _trial(failed="DSR >= 0.95", eligible=False), status="rejected")
    with bare:
        stamp_yardstick(bare, [n], percentile=0.10)
        assert store.reevaluate_method(bare, "M0001").moved is False
    assert store.get_method(bare, "M0001")["status"] == "rejected"


def test_reevaluate_unblocks_an_old_arm_whose_reading_clears(bare, at_all_trials):
    (n,) = _lab(bare, _trial(failed="DSR >= 0.95", eligible=False), status="rejected")
    with bare:
        stamp_yardstick(bare, [n], percentile=0.95)
        assert store.reevaluate_method(bare, "M0001").moved is True
    assert store.get_method(bare, "M0001")["status"] == "dev-eligible"
