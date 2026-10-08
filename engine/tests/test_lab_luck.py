"""`lab luck`: the dev leaderboard under each N policy (lab-luck-gate phase 5).

Read-only by construction and by test: `lab luck` opens no research store, runs no backtest,
inserts no row and spends no test-window look.

The numbers here are the analysis document's N-sensitivity table
(`20261007-085606-D3K1_code_analyzer.md`, "What each N would do to the recorded verdicts") plus
the two measured claims the plan index's Decisions D1 and D1b rest on, all at the trial-Sharpe
variance they were computed at. They are pinned to the document rather than to the live database
because the database's variance moves with every trial that lands, and a table at a different
variance is a different table.
"""

from __future__ import annotations

import argparse
import math

import pytest

from seer_engine.backtest import dev
from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import store

# The variance of the 110 dev trials' daily Sharpes on the committed database, 2026-10-07 --
# the analysis document's "var = 2.395e-04, sd 0.01548".
DOC_VAR = 2.395048e-04

# The document's SR*(N) row, daily, at DOC_VAR.
DOC_SR_STAR: tuple[tuple[int, float], ...] = (
    (10, 0.0244), (20, 0.0294), (37, 0.0334), (54, 0.0357), (85, 0.0383),
    (110, 0.0397), (135, 0.0408), (200, 0.0428), (400, 0.0462),
)

# candidate, annualized Sharpe, DSR as recorded, N at run, DSR at N=37, DSR at N=23.
# The last two columns are the document's table; the first three are the recorded columns it was
# computed from.
DOC_TABLE: tuple[tuple[str, float, float, int, float, float], ...] = (
    ("M0022-W-TV16", 0.9451487465911588, 0.9156233536577147, 110, 0.965, 0.978),
    ("M0022-W-TV14", 0.9399457541304774, 0.9122102223368624, 110, 0.963, 0.977),
    ("M0020-W-NOSTOP", 0.9381821396726596, 0.9143575652641522, 107, 0.964, 0.978),
    ("M0007-N20-RAW", 0.9415179650334398, 0.9137573992873155, 85, 0.953, 0.970),
    ("M0019-RAW20-S25", 0.9165875788092439, 0.9004485465260565, 104, 0.956, 0.972),
    ("M0001-TV10", 0.8139921595082781, 0.9034978186707492, 58, 0.937, 0.964),
)

# A SAMPLE of seven dev trials that miss NO owner condition **at the bars in force since
# 2026-10-07** -- DSR >= 0.90 (D1) and max DD <= 20% (D6, phase 8) -- and are therefore judged by
# the luck bar alone. It includes M0020-W-NOSTOP at 19.3% and M0007-N20-RAW at 19.6%, which the
# old 15% drawdown bar kept out of the pool entirely.
#
# **It is a sample, not the whole pool.** Measured on the committed database at this phase:
# 56 dev trials carry a recorded DSR, 25 of them miss no owner condition, and of those 3 clear
# the bar at N=110, 12 at N=37 and 18 at N=23. The plan index's phase-5 exit criterion 6 said
# "seven at N=23"; that was this seven-row sample all clearing, not a count over the database,
# and `lab luck` prints the real figure because `_eligible_at` recomputes rather than quotes.
# The number D1 actually rests on -- **three** at the live N=110, and which three -- is exact and
# is asserted by name below.
#
# (candidate, annualized Sharpe, DSR as recorded, N at run)
LUCK_ONLY: tuple[tuple[str, float, float, int], ...] = (
    ("M0011-RAW20-TV12", 0.8377892220995373, 0.8106495874759774, 90),
    ("M0011-RAW20-TV14-N21", 0.9263098412009216, 0.8974466395413563, 90),
    ("M0019-TV14N21-S20", 0.8853472123958809, 0.8728852717568223, 104),
    ("M0020-W-NOSTOP", 0.9381821396726596, 0.9143575652641522, 107),
    ("M0007-N20-RAW", 0.9415179650334398, 0.9137573992873155, 85),
    ("M0022-W-TV14", 0.9399457541304774, 0.9122102223368624, 110),
    ("M0022-W-TV16", 0.9451487465911588, 0.9156233536577147, 110),
)

OWNER_BAR = 0.90  # Decision D1: the owner's stated risk appetite, 2026-10-07


def _daily(annualized: float) -> float:
    return annualized / math.sqrt(252)


def _at(sharpe: float, dsr: float, n_at: int, n: int) -> float | None:
    return lab_cmd.recover_dsr(
        sharpe_daily=_daily(sharpe), dsr_at_run=dsr, n_at_run=n_at,
        var_trials=DOC_VAR, n_trials=n,
    )


# ------------------------------------------------------------------ the document's arithmetic


def test_sr_star_reproduces_the_documents_hurdle_row():
    for n, expected in DOC_SR_STAR:
        assert round(lab_cmd.sr_star(n, DOC_VAR), 4) == expected


def test_sr_star_rises_with_n():
    """The defect R1 names, as an assertion: every extra look raises the bar."""
    values = [lab_cmd.sr_star(n, DOC_VAR) for n, _ in DOC_SR_STAR]
    assert values == sorted(values)
    assert values[0] < values[-1]


def test_recover_dsr_reproduces_the_analysis_table():
    """The exit criterion: `lab luck`'s arithmetic is the document's table."""
    for candidate, sharpe, dsr, n_at, at37, at23 in DOC_TABLE:
        got37 = _at(sharpe, dsr, n_at, 37)
        got23 = _at(sharpe, dsr, n_at, 23)
        assert got37 is not None and got23 is not None
        assert round(got37, 3) == at37, candidate
        assert round(got23, 3) == at23, candidate


def test_recover_dsr_returns_the_known_value_at_its_own_n_for_any_variance():
    """The identity that makes the `recorded` column a reproduction, not a second estimate --
    and that lets the ratchet warning anchor on `store.verdict`'s own number."""
    for _, sharpe, dsr, n_at, _, _ in DOC_TABLE:
        for var in (1e-6, DOC_VAR, 1e-2):
            got = lab_cmd.recover_dsr(
                sharpe_daily=_daily(sharpe), dsr_at_run=dsr, n_at_run=n_at,
                var_trials=var, n_trials=n_at,
            )
            assert got == pytest.approx(dsr, abs=1e-12)


def test_recover_dsr_falls_monotonically_as_n_rises():
    """What `_sinks_at` bisects on."""
    for _, sharpe, dsr, n_at, _, _ in DOC_TABLE:
        series = [_at(sharpe, dsr, n_at, n) for n in (23, 37, 54, 85, 110, 200, 400)]
        assert series == sorted(series, reverse=True)


@pytest.mark.parametrize(
    "kw",
    [
        dict(n_trials=1),
        dict(n_at_run=1),
        dict(var_trials=0.0),
        dict(var_trials=-1.0),
        dict(dsr_at_run=0.0),
        dict(dsr_at_run=1.0),
        dict(sharpe_daily=float("nan")),
    ],
)
def test_recover_dsr_is_none_where_the_inversion_is_undefined(kw):
    base = dict(sharpe_daily=0.0595, dsr_at_run=0.916, n_at_run=110,
                var_trials=DOC_VAR, n_trials=23)
    base.update(kw)
    assert lab_cmd.recover_dsr(**base) is None


# ------------------------------------------------------------------ D1 and D1b, measured


def test_d1_three_candidates_clear_the_owners_bar_at_the_live_n_and_all_seven_at_n_23():
    """Decisions D1 and D6's evidence, and D1's reason for leaving the N lever alone.

    At N = 110 -- what `all-trials` resolved to on the 110-trial lab this sample was measured
    from -- the two owner-set bars admit **three** candidates across the whole lab, the three
    highest-MAR books, asserted by name. Pulling the N lever as well (N = 23, the distinct-method
    count of that same lab) admits **every one of this sample's seven**, including
    `M0011-RAW20-TV12` at MAR 0.60; over the full database it admits 18 of the 25 luck-only
    trials rather than 3.

    **That was the argument for leaving the lever alone, and the lever has since been pulled.**
    `DSR_POLICY` moved to `methods` on 2026-10-08 (lab-realistic-gate R1) -- not because the
    number of admissions became acceptable, but because `all-trials` asserts an independence the
    lab's own estimator contradicts (participation ratio 2.34 over 126 curves, mean pairwise
    correlation 0.612) and because counting one look per variant *run* is what made re-running a
    method perturb every other method's verdict. This test is therefore the measured record of
    what that move costs, stated in advance, and both literals below are deliberate: 110 and 23
    are the two N's of the lab this sample was taken from, not the live gate's.
    """
    at110 = [c for c, s, d, n in LUCK_ONLY if _at(s, d, n, 110) >= OWNER_BAR]
    at23 = [c for c, s, d, n in LUCK_ONLY if _at(s, d, n, 23) >= OWNER_BAR]
    assert sorted(at110) == ["M0020-W-NOSTOP", "M0022-W-TV14", "M0022-W-TV16"]
    assert len(at23) == len(LUCK_ONLY) == 7


def test_d1_m0007_is_in_the_pool_now_and_still_does_not_clear():
    """The drawdown change let M0007-N20-RAW into the luck-only pool (19.6% <= 20%); the luck
    bar still keeps it out. Recorded 0.914 at its recorded N = 85, **0.898** at today's N = 110 --
    the clearest case in the lab of why a recorded DSR is not a verdict."""
    _, sharpe, dsr, n_at = LUCK_ONLY[4]
    assert LUCK_ONLY[4][0] == "M0007-N20-RAW"
    assert round(dsr, 3) == 0.914                      # as recorded, at N = 85
    assert round(_at(sharpe, dsr, n_at, 110), 3) == 0.898   # re-evaluated at today's N
    assert _at(sharpe, dsr, n_at, 110) < OWNER_BAR


def test_d1_nothing_cleared_the_old_bar_at_the_live_n():
    """The deadlock the plan set was opened on: at (N=110, 0.95) the gate admits nothing."""
    assert [c for c, s, d, n in LUCK_ONLY if _at(s, d, n, 110) >= 0.95] == []


def test_d1b_the_best_candidate_sinks_back_below_the_bar_at_n_143():
    """Decision D1b: the threshold change buys runway, it does not remove the ratchet. The
    warning `lab status` prints has to name this N, and this is the N."""
    name, sharpe, dsr, n_at = LUCK_ONLY[-1]
    assert name == "M0022-W-TV16"
    assert round(_at(sharpe, dsr, n_at, 110), 3) == 0.916
    assert _at(sharpe, dsr, n_at, 142) >= OWNER_BAR
    assert _at(sharpe, dsr, n_at, 143) < OWNER_BAR
    assert round(_at(sharpe, dsr, n_at, 200), 3) == 0.877


# ------------------------------------------------------------------ the historical luck label


def test_owner_misses_is_a_one_line_delegation_and_reads_the_row_not_the_string():
    """There is one rule for "which conditions does this trial miss?", and it is phase 4's.

    The 110 recorded `failed` strings say "DSR >= 0.95" and "max DD <= 15%" and always will; the
    live bars are 0.90 and 20%. A trial at 19.3% drawdown whose record says it missed the old 15%
    bar must read as missing **nothing** -- that trial is M0020-W-NOSTOP, and showing it as a
    drawdown failure is the bug this delegation exists to prevent.
    """
    import inspect

    src = inspect.getsource(lab_cmd._owner_misses)
    assert "store.owner_failures" in src
    assert "startswith" not in src and "split" not in src, (
        "_owner_misses must carry no rule of its own: one definition, in store.py"
    )

    row = {
        "total_return": 3.0, "spy_tr_return": 2.0, "max_drawdown": 0.193,
        "profit_factor": 1.6, "trades": 250, "failed": "max DD <= 15%; DSR >= 0.95",
    }
    assert lab_cmd._owner_misses(row) == []          # both recorded bars have moved
    assert lab_cmd._owner_misses({**row, "max_drawdown": 0.247}) == [dev.FAILURE_LABELS[1]]
    assert lab_cmd._owner_misses({**row, "failed": store.OWNER_INPUTS_LABEL}) == [
        store.OWNER_INPUTS_LABEL
    ]  # the one condition carried from the record rather than re-derived


def test_no_owner_condition_label_could_be_mistaken_for_a_luck_label():
    """`store.is_luck_label` is still the display readers' rule, and it is still exact."""
    for label in dev.FAILURE_LABELS:
        assert not store.is_luck_label(label), label
    assert store.is_luck_label("DSR >= 0.95") and store.is_luck_label(store.DSR_LABEL)
    assert store.LUCK_LABEL_PREFIX == "DSR >= "


# ------------------------------------------------------------------ the CLI


def _trial(**kw) -> store.TrialRow:
    base = dict(
        method_id="M0001", candidate_id="M0001-A", config_digest="d1", config_text="t",
        rules_id="MONTHLY_HOLD", allocator_id="TIMING", window="dev", start="1996-01-02",
        end="2015-10-16", store_fingerprint="399d0d25", git_sha="abc123",
        run_at="2026-10-06T00:00:00+00:00", total_return=3.0, cagr=0.12, max_drawdown=0.11,
        profit_factor=1.6, trades=250, sharpe=0.9, exposure=0.95, turnover=1.1, worst_year=2008,
        worst_year_return=-0.1, spy_tr_return=2.0, spy_tr_cagr=0.08, mar=0.8,
        failed="DSR >= 0.95", eligible=False, dsr=0.91, n_trials_at_run=6, curve_json="[]",
    )
    base.update(kw)
    return store.TrialRow(**base)


def _lab(db):
    """A small lab: three methods, six dev trials, varied Sharpes so a variance exists."""
    c = store.connect(db)
    with c:
        for i, mid in enumerate(("M0001", "M0002", "M0003"), start=1):
            store.add_method(c, id=mid, name=f"m{i}", family="f", source_kind="knowledge",
                             hypothesis="h", status="registered")
            store.insert_trials(c, [
                _trial(method_id=mid, candidate_id=f"{mid}-A", config_digest=f"{mid}a",
                       sharpe=0.70 + 0.07 * i, dsr=0.80 + 0.03 * i),
                _trial(method_id=mid, candidate_id=f"{mid}-B", config_digest=f"{mid}b",
                       sharpe=0.55 + 0.05 * i, dsr=0.70 + 0.02 * i,
                       failed="max DD <= 15%; DSR >= 0.95"),
            ])
            store.update_method(c, mid, status="rejected")
    c.close()


def test_lab_luck_prints_a_column_per_policy_and_per_at(tmp_path, capsys):
    db = tmp_path / "lab.sqlite"
    _lab(db)
    args = argparse.Namespace(db=db, lab_command="luck", at=[37, 23], limit=0)
    assert lab_cmd.run(args) == 0
    out = capsys.readouterr().out
    assert "read-only" in out
    assert "N=37" in out and "N=23" in out
    for name in lab_cmd._policies():
        assert name in out
    assert "live policy: " + store.DSR_POLICY in out
    assert "M0001-A" in out and "M0003-B" in out
    assert "clear " + store.DSR_LABEL in out
    assert "Nothing was written" in out


def test_lab_luck_recorded_column_reproduces_the_database(tmp_path, capsys):
    db = tmp_path / "lab.sqlite"
    _lab(db)
    args = argparse.Namespace(db=db, lab_command="luck", at=None, limit=0)
    assert lab_cmd.run(args) == 0
    out = capsys.readouterr().out
    c = store.connect(db)
    recorded = {
        r["candidate_id"]: float(r["dsr"])
        for r in c.execute("SELECT * FROM trials WHERE window = 'dev'")
    }
    c.close()
    # Only the leaderboard table: the per-policy block above it also names candidates (the ones
    # clearing the bar at that N), on a line that carries no columns to compare.
    table = out.split("other failed conditions")[1]
    seen = 0
    for line in table.splitlines():
        parts = line.split()
        if parts and parts[0] in recorded:
            assert float(parts[2]) == pytest.approx(recorded[parts[0]], abs=5e-4)
            seen += 1
    assert seen == len(recorded)


def test_lab_luck_writes_nothing(tmp_path, capsys):
    db = tmp_path / "lab.sqlite"
    _lab(db)
    before = db.read_bytes()
    args = argparse.Namespace(db=db, lab_command="luck", at=[23], limit=0)
    assert lab_cmd.run(args) == 0
    capsys.readouterr()
    assert db.read_bytes() == before
    c = store.connect(db)
    assert store.test_looks(c) == 0
    c.close()


def test_lab_luck_on_an_empty_lab_says_so_instead_of_failing(tmp_path, capsys):
    db = tmp_path / "lab.sqlite"
    store.connect(db).close()
    args = argparse.Namespace(db=db, lab_command="luck", at=None, limit=0)
    assert lab_cmd.run(args) == 0
    assert "No leaderboard" in capsys.readouterr().out


def test_at_refuses_an_n_the_deflated_sharpe_is_undefined_at():
    with pytest.raises(argparse.ArgumentTypeError):
        lab_cmd._positive_n("1")
    assert lab_cmd._positive_n("23") == 23
