"""``lab names``: the name-count sweep (gotrade-fee-rebuild phase 8). Report only, N never moves.

The sweep answers handover section 8's Q2 -- how many names, decided on the merits -- and the one
property it must never lose is that it records nothing: it is six free looks at six name counts,
which is exactly the search the luck gate exists to charge for, so it may inform a decision and
may never be one.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

import pytest
from labkit import smoke_data

from seer_engine import cli, research
from seer_engine.lab import name_count, store
from seer_engine.lab.method import config_digest
from seer_engine.lab.methods.m0007_residual_momentum import METHOD as M0007
from seer_engine.lab.methods.m0007_residual_momentum import RESIDMOM
from seer_engine.lab.seed import seed
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC, MONTHLY_HOLD_FRAC_GOTRADE

SMOKE_NS = (5, 10)  # the smoke market has eight members; this is a shape test, not a result


@pytest.fixture()
def lab(tmp_path):
    path = tmp_path / "lab.sqlite"
    conn = store.connect(path)
    seed(conn)
    yield conn, path
    conn.close()


@pytest.fixture(scope="module")
def data():
    return smoke_data()


def _untouched(conn):
    """Everything `lab names` must leave exactly as it found it -- insights included."""
    return (
        store.dev_trial_count(conn),
        store.test_looks(conn),
        conn.execute("SELECT count(*) FROM trials").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0],
        conn.execute("SELECT count(*) FROM insights").fetchone()[0],
        tuple(tuple(r) for r in conn.execute(
            "SELECT id, status, verdict, source_sha FROM methods ORDER BY id")),
    )


# ---- what is swept ---------------------------------------------------------------------------


def test_the_sweep_varies_the_name_count_and_nothing_else():
    cands = name_count.variants(name_count.NS)
    assert len(cands) == 2 * len(name_count.NS)
    gt = [c for c in cands if c.rules is MONTHLY_HOLD_FRAC_GOTRADE]
    flat = [c for c in cands if c.rules is MONTHLY_HOLD_FRAC]
    assert len(gt) == len(flat) == len(name_count.NS)
    for c in cands:
        assert c.allocator is RESIDMOM
        assert c.family == "M0007"
        assert c.params.scaled is False          # the RAW rank the roster trades
        assert c.params.inner.rank == "momentum"
        assert c.params.inner.trend == ("SPY", 200)
        assert c.params.beta_n == 378 and c.params.mom_n == 252 and c.params.skip == 21
    assert [c.params.inner.top for c in gt] == list(name_count.NS)


def test_the_twentyname_variant_is_the_roster_variant_but_for_fees_and_shares():
    """The sweep's N=20 point and the recorded M0007-N20-RAW differ only in the rule set."""
    recorded = next(c for c in M0007.candidates if c.id == name_count.BASE_VARIANT)
    swept = next(c for c in name_count.variants((20,), control=False))
    assert swept.params == recorded.params
    assert swept.allocator is recorded.allocator
    assert swept.rules is MONTHLY_HOLD_FRAC_GOTRADE and swept.rules is not recorded.rules
    # A different rule set is a different configuration, so no recorded digest is re-used.
    assert config_digest(swept) != config_digest(recorded)


def test_every_swept_configuration_is_distinct():
    digests = {config_digest(c) for c in name_count.variants(name_count.NS)}
    assert len(digests) == 2 * len(name_count.NS)


def test_candidate_ids_are_sortable_and_say_which_fee_they_paid():
    ids = [c.id for c in name_count.variants((5, 20), control=True)]
    assert ids == ["M0007-N05-RAW-GT", "M0007-N20-RAW-GT",
                   "M0007-N05-RAW-FLAT", "M0007-N20-RAW-FLAT"]


@pytest.mark.parametrize("bad,why", [("", "empty"), ("twenty", "whole numbers"), ("1", "outside"),
                                     ("200", "outside")])
def test_a_bad_name_count_is_refused_in_words(bad, why):
    with pytest.raises(store.LabError, match=why):
        name_count.check_names(bad)


def test_check_names_sorts_and_dedupes():
    assert name_count.check_names("20,5,20,10") == (5, 10, 20)
    assert name_count.check_names(None) == name_count.NS
    assert name_count.check_names([30, 5]) == (5, 30)


# ---- the measurement -------------------------------------------------------------------------


def test_the_lump_sweep_runs_and_writes_nothing(lab, data):
    conn, _ = lab
    before = _untouched(conn)
    sweep = name_count.measure(data, ns=SMOKE_NS, control=True, lump=True)
    assert sweep.funding == name_count.LUMP
    assert sweep.names == SMOKE_NS
    assert sweep.models == (name_count.REAL, name_count.FLAT)
    assert len(sweep.points) == 2 * len(SMOKE_NS)
    assert [p.names for p in sweep.of(name_count.REAL)] == list(SMOKE_NS)
    assert _untouched(conn) == before


def test_gotrade_only_drops_the_control_column(data):
    sweep = name_count.measure(data, ns=SMOKE_NS, control=False, lump=True)
    assert sweep.models == (name_count.REAL,)
    assert len(sweep.points) == len(SMOKE_NS)
    assert sweep.agrees is None  # one model cannot agree with itself


def test_gotrade_costs_more_than_the_flat_control_at_every_name_count(data):
    sweep = name_count.measure(data, ns=SMOKE_NS, control=True, lump=True)
    for n in SMOKE_NS:
        real = sweep.at(name_count.REAL, n)
        flat = sweep.at(name_count.FLAT, n)
        assert real is not None and flat is not None
        assert real.costs_usd > flat.costs_usd, f"gotrade must cost more than flat at {n} names"
        assert real.trades == flat.trades, "the fee model must not change which trades happen"


def test_a_test_window_store_is_refused(data):
    from dataclasses import replace as dc_replace

    from labkit import smoke_test_window

    other = dc_replace(data, window=smoke_test_window())
    with pytest.raises(store.LabError, match="test-window store is refused"):
        name_count.measure(other, ns=SMOKE_NS, lump=True)


def test_the_report_names_what_it_measured_and_what_it_is_not(data):
    sweep = name_count.measure(data, ns=SMOKE_NS, control=True, lump=True)
    out = name_count.format_report(sweep)
    assert "lab names -- M0007-N20-RAW's book at 2 name counts" in out
    assert "report only: no trial row" in out
    assert "LUMP SUM" in out                      # the funding control is labelled as a control
    assert "Gotrade's real fees" in out and "the control, not the world" in out
    assert "findings" in out


def test_the_csv_carries_every_point_at_full_precision(data, tmp_path):
    sweep = name_count.measure(data, ns=SMOKE_NS, control=True, lump=True)
    path = name_count.write_csv(sweep, tmp_path / "grid" / "g.csv")
    rows = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1 + 2 * len(SMOKE_NS)
    assert rows[0].startswith("cost_model,names,candidate_id,total_return")
    assert "M0007-N05-RAW-GT" in rows[1]


def test_the_money_weighted_column_is_soft(data):
    """Phase 7 names the measure; this module must run whether or not it found it."""
    sweep = name_count.measure(data, ns=SMOKE_NS, control=False, lump=True)
    out = name_count.format_report(sweep)
    assert "money-wtd" in out  # the column is always there; absent cells render as an em dash


# ---- the contribution schedule ---------------------------------------------------------------


def test_the_contribution_sweep_refuses_readably_when_the_schedule_is_missing(monkeypatch, data):
    """Phase 5 and 7 own the schedule; a missing one is a sentence, never a TypeError."""
    monkeypatch.setattr(name_count, "SCHEDULE_NAME", "NO_SUCH_SCHEDULE_FOR_THIS_TEST")
    with pytest.raises(store.LabError, match="NO_SUCH_SCHEDULE_FOR_THIS_TEST"):
        name_count.owner_schedule()


def test_a_run_registry_without_the_keyword_refuses_readably(monkeypatch):
    monkeypatch.setattr(name_count, "SCHEDULE_KEYWORD", "no_such_keyword_for_this_test")
    with pytest.raises(store.LabError, match="takes no 'no_such_keyword_for_this_test' keyword"):
        name_count.check_schedule_support()


def test_the_real_schedule_reaches_the_sweep(lab, data):
    """The default path: the owner's schedule, phase 7's keyword, and still nothing recorded."""
    conn, _ = lab
    before = _untouched(conn)
    sweep = name_count.measure(data, ns=SMOKE_NS, control=False, lump=False)
    assert sweep.funding == name_count.FED
    assert len(sweep.points) == len(SMOKE_NS)
    assert _untouched(conn) == before


# ---- the CLI ---------------------------------------------------------------------------------


def test_cli_lab_names_reports_without_moving_n(lab, data, monkeypatch, capsys, tmp_path):
    conn, path = lab
    before = _untouched(conn)
    monkeypatch.setattr(research, "load_store", lambda _p: data)
    csv_path = tmp_path / "grid.csv"
    assert cli.main([
        "lab", "--db", str(path), "names", "--ns", "5,10", "--lump",
        "--store", str(tmp_path), "--csv", str(csv_path),
    ]) == 0
    out = capsys.readouterr().out
    assert "lab names -- M0007-N20-RAW's book" in out
    assert "nothing was recorded" in out
    assert "`lab stage` is not needed" in out
    assert csv_path.exists()
    assert _untouched(conn) == before


def test_cli_refuses_a_bad_name_count_with_exit_2_before_any_store(lab, tmp_path, monkeypatch):
    _conn, path = lab

    def explode(_p):
        raise AssertionError("the research store must not be loaded after a bad --ns")

    monkeypatch.setattr(research, "load_store", explode)
    assert cli.main(["lab", "--db", str(path), "names", "--ns", "twenty", "--lump",
                     "--store", str(tmp_path)]) == 2


# ---- the real sweep, against the real store ---------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("SEER_LAB_NAMES_LIVE"),
    reason="set SEER_LAB_NAMES_LIVE=1 (and SEER_RESEARCH_STORE) to sweep the real dev store",
)
def test_lab_names_on_the_research_store(tmp_path, capsys):
    live_store = Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR)
    db = tmp_path / "lab.sqlite"
    shutil.copy(store.COMMITTED_DB, db)  # a copy: the committed database is never written
    assert cli.main(["lab", "--db", str(db), "names", "--store", str(live_store)]) == 0
    out = capsys.readouterr().out
    assert "lab names -- M0007-N20-RAW's book at 6 name counts" in out
    assert "Gotrade's real fees" in out
    assert "nothing was recorded" in out
