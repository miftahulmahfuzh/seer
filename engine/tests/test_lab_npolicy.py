"""The N the luck gate deflates by (lab-luck-gate phase 1): the three named policies, the
participation-ratio estimator over the recorded dev curves, and the floor that keeps the
``methods`` policy from asserting fewer independent looks than the evidence shows.

Pure reads throughout: no backtest runs here and no test-window look is spent.
"""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import date

import numpy as np
import pytest

from seer_engine.lab import npolicy, store


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    yield c
    c.close()


def _method(conn, mid: str) -> None:
    with conn:
        store.add_method(
            conn, id=mid, name=f"n{mid}", family="f", source_kind="knowledge", hypothesis="h"
        )


def _month_ends(count: int) -> list[date]:
    return [date(1996 + i // 12, i % 12 + 1, 28) for i in range(count)]


def _curve(returns) -> str:
    """A month-end equity curve compounded from ``returns`` (one fewer month-end than points)."""
    days = _month_ends(len(returns) + 1)
    level = 1.0
    points = [(days[0], level)]
    for day, r in zip(days[1:], returns):
        level *= 1.0 + float(r)
        points.append((day, level))
    return store.curve_json(points)


def _trial(conn, method_id: str, tag: str, curve: str) -> None:
    row = store.TrialRow(
        method_id=method_id,
        candidate_id=f"{method_id}-{tag}",
        config_digest=f"{method_id}-{tag}-digest",
        config_text="t",
        rules_id="r",
        allocator_id="a",
        window="dev",
        start="2000-01-03",
        end="2015-10-16",
        store_fingerprint="fp",
        git_sha="abc",
        run_at="2026-10-07T00:00:00+00:00",
        total_return=1.0,
        cagr=0.1,
        max_drawdown=0.2,
        profit_factor=1.5,
        trades=200,
        sharpe=0.8,
        exposure=0.9,
        turnover=1.0,
        worst_year=2008,
        worst_year_return=-0.2,
        spy_tr_return=0.5,
        spy_tr_cagr=0.07,
        mar=0.5,
        failed="",
        eligible=True,
        dsr=0.9,
        n_trials_at_run=1,
        curve_json=curve,
    )
    with conn:
        store.insert_trials(conn, [row])


def _independent(count: int, months: int = 120, seed: int = 7) -> list[str]:
    """``count`` curves whose monthly returns are mutually uncorrelated by construction."""
    rng = np.random.default_rng(seed)
    return [_curve(rng.normal(0.006, 0.03, months)) for _ in range(count)]


# ---- the named set ---------------------------------------------------------------------------


def test_the_policy_names_are_a_closed_set():
    assert npolicy.POLICIES == ("all-trials", "methods", "effective")
    assert npolicy.DEFAULT_POLICY in npolicy.POLICIES
    # Reconciled: this module's default is the policy the lab ships (store.DSR_POLICY, phase 4),
    # so no caller can be deflated by an N the gate does not use. Phase 4 pins the other side.
    assert npolicy.DEFAULT_POLICY == "all-trials"
    for name in npolicy.POLICIES:
        assert npolicy.check_policy(name) == name
    with pytest.raises(npolicy.UnknownPolicy, match="unknown N policy"):
        npolicy.check_policy("per-variant")
    with pytest.raises(ValueError):  # UnknownPolicy is a ValueError, so callers may catch either
        npolicy.check_policy("")


def test_an_unknown_policy_is_refused_before_anything_is_measured(conn):
    with pytest.raises(npolicy.UnknownPolicy):
        npolicy.effective_n(conn, "all trials")


# ---- an empty lab ----------------------------------------------------------------------------


def test_an_empty_lab_measures_nothing_and_still_answers(conn):
    corr = npolicy.correlation(conn)
    assert corr.participation_ratio == 1.0
    assert corr.mean_pairwise is None
    assert corr.curves_used == 0
    assert npolicy.participation_ratio(conn) == 1.0
    assert npolicy.effective_n(conn, "all-trials").n == 0  # the literal row count, as before
    assert npolicy.effective_n(conn, "methods").n == 1
    assert npolicy.effective_n(conn, "effective").n == npolicy.DSR_MIN_N


# ---- what each policy counts -----------------------------------------------------------------


def test_all_trials_counts_rows_and_methods_counts_methods(conn):
    for mid in ("M0001", "M0002"):
        _method(conn, mid)
    curves = _independent(6)
    for i, curve in enumerate(curves):
        _trial(conn, "M0001" if i < 3 else "M0002", f"V{i}", curve)

    assert store.dev_trial_count(conn) == 6
    assert npolicy.dev_method_count(conn) == 2

    rows = npolicy.effective_n(conn, "all-trials")
    assert rows.n == 6
    assert rows.policy == "all-trials"
    assert rows.trial_rows == 6
    assert rows.distinct_methods == 2
    assert rows.curves_used == 6
    assert rows.month_ends == 121
    assert not rows.floored

    # Six uncorrelated curves: the participation ratio is near six, so the floor outranks the
    # two methods and the evidence -- not the method count -- decides N.
    methods = npolicy.effective_n(conn, "methods")
    assert methods.participation_ratio > 2.0
    assert methods.n == math.ceil(methods.participation_ratio)
    assert methods.floored


def test_the_methods_floor_binds_when_the_evidence_exceeds_the_method_count(conn):
    """One method, eight uncorrelated variants: 1 look is a claim the curves contradict."""
    _method(conn, "M0001")
    for i, curve in enumerate(_independent(8, seed=11)):
        _trial(conn, "M0001", f"V{i}", curve)

    count = npolicy.effective_n(conn, "methods")
    assert count.distinct_methods == 1
    assert count.participation_ratio > 1.0
    assert count.floored, "the floor must bind when the ratio exceeds the method count"
    assert count.n == math.ceil(count.participation_ratio) > count.distinct_methods
    assert count.n >= npolicy.DSR_MIN_N
    assert "the participation-ratio floor binds" in count.evidence()


def test_identical_curves_are_one_independent_look(conn):
    """The floor must not punish a family that is genuinely one idea measured many ways."""
    _method(conn, "M0001")
    one = _independent(1, seed=3)[0]
    for i in range(5):
        _trial(conn, "M0001", f"V{i}", one)

    corr = npolicy.correlation(conn)
    assert corr.curves_used == 5
    assert corr.participation_ratio == pytest.approx(1.0, abs=1e-9)
    assert corr.mean_pairwise == pytest.approx(1.0, abs=1e-9)

    assert npolicy.effective_n(conn, "all-trials").n == 5
    assert npolicy.effective_n(conn, "methods").n == 1  # the floor is 1 and does not bind
    assert npolicy.effective_n(conn, "effective").n == npolicy.DSR_MIN_N


def test_effective_is_the_rounded_ratio_floored_at_two(conn):
    _method(conn, "M0001")
    for i, curve in enumerate(_independent(5, seed=23)):
        _trial(conn, "M0001", f"V{i}", curve)

    count = npolicy.effective_n(conn, "effective")
    assert count.policy == "effective"
    assert count.n == max(npolicy.DSR_MIN_N, round(count.participation_ratio))
    assert count.n >= npolicy.DSR_MIN_N


# ---- what the estimator refuses to be fooled by ----------------------------------------------


def test_a_flat_curve_carries_no_information_and_is_dropped(conn):
    _method(conn, "M0001")
    for i, curve in enumerate(_independent(3, seed=5)):
        _trial(conn, "M0001", f"V{i}", curve)
    _trial(conn, "M0001", "FLAT", _curve([0.0] * 120))

    corr = npolicy.correlation(conn)
    assert store.dev_trial_count(conn) == 4
    assert corr.curves_used == 3, "a zero-variance curve must not enter the correlation matrix"
    assert npolicy.effective_n(conn, "all-trials").n == 4  # the row count is still the row count


def test_a_short_or_empty_curve_never_raises(conn):
    _method(conn, "M0001")
    for i, curve in enumerate(_independent(2, seed=9)):
        _trial(conn, "M0001", f"V{i}", curve)
    _trial(conn, "M0001", "EMPTY", "[]")
    _trial(conn, "M0001", "TINY", store.curve_json([(date(2000, 1, 31), 1.0)]))

    corr = npolicy.correlation(conn)
    assert corr.curves_used == 2
    assert npolicy.effective_n(conn, "methods").n >= 1


def test_the_test_window_is_never_read(conn):
    """Only dev trials count. No policy may be moved by a test-window look."""
    _method(conn, "M0001")
    for i, curve in enumerate(_independent(3, seed=13)):
        _trial(conn, "M0001", f"V{i}", curve)
    before = npolicy.effective_n(conn, "all-trials")

    row = store.TrialRow(
        method_id="M0001", candidate_id="M0001-T", config_digest="test-digest", config_text="t",
        rules_id="r", allocator_id="a", window="test", start="2015-10-19", end="2018-12-31",
        store_fingerprint="fp", git_sha="abc", run_at="2026-10-07T00:00:00+00:00", total_return=1.0,
        cagr=0.1, max_drawdown=0.2, profit_factor=1.5, trades=200, sharpe=0.8, exposure=0.9,
        turnover=1.0, worst_year=2008, worst_year_return=-0.2, spy_tr_return=0.5, spy_tr_cagr=0.07,
        mar=0.5, failed="", eligible=True, dsr=0.9, n_trials_at_run=1,
        curve_json=_independent(1, seed=99)[0],
    )
    with conn:
        store.insert_trials(conn, [row])

    after = npolicy.effective_n(conn, "all-trials")
    assert after == before


# ---- the evidence line phase 7 commits -------------------------------------------------------


def test_the_basis_is_one_usable_line_for_every_policy_on_every_lab(conn):
    """``NCount.basis`` is written verbatim into a committed pre-registration and into
    ``web/data/lab.json``'s one-line ``gate.dsrNBasis``. It must never be empty and never wrap."""
    for policy in npolicy.POLICIES:  # an empty lab first: snapshot runs on empty fixtures
        basis = npolicy.effective_n(conn, policy).basis
        assert basis and "\n" not in basis, policy

    _method(conn, "M0001")
    for i, curve in enumerate(_independent(4, seed=31)):
        _trial(conn, "M0001", f"V{i}", curve)
    for policy in npolicy.POLICIES:
        count = npolicy.effective_n(conn, policy)
        basis = count.basis
        assert basis and "\n" not in basis, policy
        assert basis == npolicy.effective_n(conn, policy).basis  # stable for one database
    assert "dev trials" in npolicy.effective_n(conn, "all-trials").basis
    assert "distinct methods" in npolicy.effective_n(conn, "methods").basis
    assert "participation ratio" in npolicy.effective_n(conn, "effective").basis


# ---- the committed database ------------------------------------------------------------------


def _committed():
    if not store.COMMITTED_DB.exists():
        pytest.skip("no committed lab database")
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _reference_correlation(conn: sqlite3.Connection) -> tuple[float, float, int, int]:
    """Recompute the dev trials' co-movement here, from the raw ``trials.curve_json`` rows.

    Calls none of ``npolicy``'s helpers, so the test below compares two independent routes to the
    same four figures: (participation ratio, mean pairwise correlation, curves used, common
    month-ends).

    This replaced four typed constants (a participation ratio pinned at 2.442, and friends). A
    typed number is a
    property of one set of curves, and Sera adds curves: by the time the lab reached 126 dev trials
    the pin said 110 and the test that held it had turned itself into a skip, so CI was asserting
    nothing while reporting a pass. There is no number for which "the ratio is 2.44" survives the
    lab growing -- but the arithmetic that produces it is the same at any size, so the arithmetic
    is what this pins. The filters mirror ``npolicy._dev_curves`` and ``_return_matrix``: a curve
    too short to carry a variance, with a non-positive level, or perfectly flat is dropped rather
    than correlated. If those rules ever change, this changes with them -- deliberately.
    """
    curves: list[dict[str, float]] = []
    for (text,) in conn.execute("SELECT curve_json FROM trials WHERE window = 'dev' ORDER BY n"):
        curve = {str(day): float(level) for day, level in json.loads(text or "[]")}
        if len(curve) >= 3:  # npolicy._MIN_POINTS: fewer points carry no variance
            curves.append(curve)
    assert len(curves) >= 2, "the committed database must hold at least two usable dev curves"
    days = sorted(set.intersection(*(set(c) for c in curves)))
    assert len(days) >= 3, "the dev curves must share at least three month-ends"
    rows: list[np.ndarray] = []
    for curve in curves:
        levels = np.asarray([curve[d] for d in days], dtype=float)
        returns = levels[1:] / levels[:-1] - 1.0
        if np.all(levels > 0.0) and np.all(np.isfinite(returns)) and float(np.std(returns)) > 0.0:
            rows.append(returns)
    matrix = np.vstack(rows)
    corr = np.corrcoef(matrix)
    eigenvalues = np.linalg.eigvalsh(corr)
    ratio = float(np.sum(eigenvalues)) ** 2 / float(np.sum(eigenvalues**2))
    upper = np.triu_indices(len(rows), k=1)
    return ratio, float(np.mean(corr[upper])), len(rows), len(days)


def test_the_committed_database_orders_the_three_policies():
    """Holds for every lab: the measured independence never exceeds the ideas, which never
    exceed the rows. This is the whole claim behind choosing ``methods``."""
    conn = _committed()
    try:
        rows = npolicy.effective_n(conn, "all-trials")
        methods = npolicy.effective_n(conn, "methods")
        effective = npolicy.effective_n(conn, "effective")
        assert rows.n == store.dev_trial_count(conn)
        assert methods.n == max(npolicy.dev_method_count(conn), math.ceil(rows.participation_ratio))
        assert effective.n == max(npolicy.DSR_MIN_N, round(rows.participation_ratio))
        assert npolicy.DSR_MIN_N <= effective.n <= methods.n <= rows.n
        assert rows.mean_pairwise_corr is not None and 0.0 < rows.mean_pairwise_corr < 1.0
    finally:
        conn.close()


def test_the_committed_evidence_is_recomputed_from_the_database_that_holds_it():
    """The gate's N and the evidence behind it, asserted against the lab as it stands today.

    Nothing here is a typed number, so nothing here can age. This test used to carry four
    ``COMMITTED_*`` constants measured at 110 dev trials and skip itself once the lab moved past
    them; the lab now holds 126 dev trials (plus 2 in the test window, 128 rows in all), so it had
    been skipping -- asserting nothing -- while CI failed on the skip itself with a message about
    PG_TEST_URL that was false. Every expected value below is either read from the database or
    recomputed from its raw curves by ``_reference_correlation``, which keeps the test's teeth at
    any lab size.
    """
    conn = _committed()
    try:
        trials = store.dev_trial_count(conn)
        methods = npolicy.dev_method_count(conn)
        corr = npolicy.correlation(conn)
        ratio, rho, curves_used, month_ends = _reference_correlation(conn)

        # The estimator agrees with the arithmetic, curve for curve and month-end for month-end.
        assert corr.curves_used == curves_used
        assert corr.month_ends == month_ends
        assert corr.participation_ratio == pytest.approx(ratio, rel=1e-9)
        assert corr.mean_pairwise == pytest.approx(rho, rel=1e-9)

        # No dev trial's curve is dropped on the way into the measurement. If this fails, the
        # gate's N rests on fewer curves than the lab recorded, which is worth a look before it
        # is accepted.
        assert corr.curves_used == trials, (
            f"{trials - corr.curves_used} of {trials} dev curves were dropped before the "
            "measurement; find which trial and why rather than loosening this"
        )

        # The trials are not independent, and it is measurable: the claim npolicy exists to make.
        # A correlation matrix regressed to the identity would put the ratio at `trials` and rho
        # at 0, and both of these would catch it.
        assert 1.0 <= corr.participation_ratio < float(trials)
        assert corr.mean_pairwise is not None and 0.0 < corr.mean_pairwise < 1.0

        # Each policy resolves to exactly what it is defined as, on this database.
        assert npolicy.effective_n(conn, "all-trials").n == trials
        assert npolicy.effective_n(conn, "methods").n == max(methods, math.ceil(ratio))
        assert npolicy.effective_n(conn, "effective").n == max(npolicy.DSR_MIN_N, round(ratio))

        # The one line committed into every docs/lab/prereg/MNNNN.md and published as
        # web/data/lab.json's gate.dsrNBasis. Built from the measured count, so it can never
        # quote a count the lab has outgrown -- which is the bug this whole test is the fix for.
        assert npolicy.effective_n(conn, "all-trials").basis == (
            f"{trials} dev trials, every variant run counted as one independent look"
        )
    finally:
        conn.close()
