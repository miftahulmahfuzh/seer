"""`promote`: the lab -> roster bridge (plan roster-promotion-pipeline, phase 5).

The rules this file holds to the wall: a promotable method exposes a Candidate whose allocator the
roster resolver names; the inserted row is active with no paper_start; an id that already started
is refused; --retire shares the insert's transaction; the lab record respects the append-only
triggers and moves only along TRANSITIONS; --dry-run writes to neither database.
"""

from __future__ import annotations

import argparse
import logging
from datetime import date

import pytest

from seer_engine import dates
from seer_engine.commands import promote
from seer_engine.lab import store as lab_store
from seer_engine.paper import roster
from seer_engine.paper import store as paper_store
from seer_engine.sim.rules import MONTHLY_HOLD
from seer_engine.strategies import evidence
from seer_engine.strategies.f_fundamental import FUNDAMENTAL, FundamentalParams

METHOD = "M0005"
VARIANT = "M0005-ALL"


@pytest.fixture(autouse=True)
def resolver_entry(monkeypatch):
    """Name FUNDAMENTAL in the resolver for the duration of a test, and only there.

    **This is the real state of the tree and not a convenience.** No lab method's allocator is in
    ``roster.RESOLVER`` on `main`: M0001 and M0004 use the lab-local OWNVOL, M0005 uses FUNDAMENTAL,
    and phase 1 seeds the resolver with buy_and_hold / STRATEGY_A / STRATEGY_C / FACTOR / TIMING
    only. So **every** promotion available today costs exactly one committed RESOLVER entry, which
    is Decisions D2's stated price and what `promote`'s refusal exists to say out loud. Phase 6
    commits that line for FUNDAMENTAL; this phase ships the road, not the traveller, so it borrows
    the line for a test and gives it back.

    `test_the_resolver_must_name_the_allocator_first` turns the fixture off to prove the refusal.
    """
    monkeypatch.setitem(
        roster.RESOLVER,
        "FUNDAMENTAL",
        roster.Binding(obj=FUNDAMENTAL, params=FundamentalParams(rank="composite", top=20)),
    )


def _args(**kw) -> argparse.Namespace:
    base = dict(
        method=METHOD, candidate=VARIANT, id="TEST-FND", name="T · Fundamentals",
        sub="Top 20 on filed fundamentals, monthly", icon="book-open", sort=None,
        gate_note="No backtest gate: the dev window predates usable XBRL coverage",
        gate_not_applicable=False, retire=None, lab_db=None, lab_status_stays=True,
        lab_override_reason="the lab has not passed it; on paper to test it forward",
        dry_run=False, verbose=0,
    )
    base.update(kw)
    return argparse.Namespace(**base)


@pytest.fixture()
def lab(tmp_path):
    conn = lab_store.connect(tmp_path / "lab.sqlite")
    with conn:
        lab_store.add_method(
            conn, id=METHOD, name="fundamentals", family="f", source_kind="knowledge",
            hypothesis="h", status="idea",
        )
        lab_store.update_method(conn, METHOD, status="rejected")
    yield conn
    conn.close()


def _seed_roster_row(pg, sid="OLD", paper_start=None, sort=1):
    pg.execute(
        "INSERT INTO strategies (id, name, sub, icon, sort, engine, rules_id, paper_start, params) "
        "VALUES (%s, 'old', 'old', 'x', %s, 'book', 'monthly-hold', %s, '{}'::jsonb) "
        "ON CONFLICT (id) DO NOTHING",
        (sid, sort, paper_start),
    )
    pg.commit()


class _Borrowed:
    """What `promote` gets instead of a connection it owns: everything real, `close()` only rolls back.

    `promote` closes the connections it opens, but the test needs `pg` to stay usable for its own
    assertions afterwards -- and, crucially, still closable by conftest's `pg_schema` teardown.
    Patching `pg.close` to a no-op does not work here: the autouse `resolver_entry` fixture pulls
    `monkeypatch` into the closure FIRST, so monkeypatch's undo runs LAST -- after `pg_schema` has
    already called the still-patched `close`. The connection then survives the test holding its
    locks, and the schema's `DROP ... CASCADE` blocks on them forever (measured: the suite hangs).

    Borrowing instead of patching keeps `close` the real method and keeps the command's own
    `finally: conn.close()` meaningful -- it ends the transaction, which is all the command's
    contract needs.
    """

    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        self._conn.rollback()


def _wire(monkeypatch, *, pg=None, lab=None):
    """Point `promote` at the throwaway schema and the temp lab, as borrowed connections."""
    if pg is not None:
        monkeypatch.setattr(promote.db, "connect", lambda url=None: _Borrowed(pg))
    if lab is not None:
        monkeypatch.setattr(lab_store, "connect", lambda path=None: _Borrowed(lab))


# ---- the promotable contract (pure) ------------------------------------------------------------


def test_a_method_without_a_file_is_not_promotable():
    with pytest.raises(promote.NotPromotable, match="no method file for M9999"):
        promote.find_candidate("M9999", None)


def test_a_multi_variant_method_must_name_the_variant():
    with pytest.raises(promote.NotPromotable, match="M0005-ALL"):
        promote.find_candidate(METHOD, None)


def test_an_unknown_variant_lists_the_real_ones():
    with pytest.raises(promote.NotPromotable, match="M0005-VAL"):
        promote.find_candidate(METHOD, "M0005-NOPE")


def test_find_candidate_returns_the_frozen_triple():
    _m, path, c = promote.find_candidate(METHOD, VARIANT)
    assert c.id == VARIANT
    assert c.allocator is FUNDAMENTAL
    assert c.rules is MONTHLY_HOLD
    assert isinstance(c.params, FundamentalParams)
    assert path.name == "m0005_fundamental_factors.py"


def test_object_name_of_refuses_an_object_the_resolver_does_not_name():
    class Unnamed:
        id = "UNNAMED"

    with pytest.raises(promote.NotPromotable, match="has no name for <UNNAMED>"):
        promote.object_name_of(Unnamed())


def test_object_name_of_is_the_resolvers_inverse():
    # RESOLVER maps a name to a roster.Binding; the live object is binding.obj, None for the
    # benchmark (which has no object to name).
    for name, binding in roster.RESOLVER.items():
        if binding.obj is not None:
            assert promote.object_name_of(binding.obj) == name


def test_the_resolver_must_name_the_allocator_first(monkeypatch):
    """The designed refusal, with the fixture's borrowed entry taken back out.

    This is what a brand-new lab allocator meets today, and the message must be the one that tells
    an operator the single line to commit (D2). It is the state phase 6 resolves for FUNDAMENTAL.
    """
    monkeypatch.delitem(roster.RESOLVER, "FUNDAMENTAL")
    _m, _p, c = promote.find_candidate(METHOD, VARIANT)
    with pytest.raises(promote.NotPromotable, match="has no name for <FND>"):
        promote.object_name_of(c.allocator)
    with pytest.raises(promote.NotPromotable, match="Add one entry to RESOLVER"):
        promote.object_name_of(c.allocator)


def test_a_variant_whose_rules_are_not_a_preset_is_refused():
    from dataclasses import replace

    with pytest.raises(promote.NotPromotable, match="not the sim.rules preset"):
        promote._check_rules(replace(MONTHLY_HOLD, cost_rate=MONTHLY_HOLD.cost_rate * 2))
    promote._check_rules(MONTHLY_HOLD)  # the real preset passes


def test_check_lookback_refuses_more_bars_than_the_night_loads():
    d = date(2026, 10, 2)
    have = len(dates.sessions(paper_store.market_window_since(d), d))
    promote.check_lookback(have, d)
    with pytest.raises(promote.NotPromotable, match="MARKET_WINDOW_DAYS"):
        promote.check_lookback(have + 1, d)


def test_check_evidence_refuses_an_object_without_evidence(monkeypatch):
    promote._check_evidence("FUNDAMENTAL")  # phase 1 gives the real roster object its facts
    monkeypatch.delitem(evidence.EVIDENCE, "FUNDAMENTAL")
    with pytest.raises(promote.NotPromotable, match="FUNDAMENTAL has no per-pick evidence"):
        promote._check_evidence("FUNDAMENTAL")
    with pytest.raises(promote.NotPromotable, match="seer_engine/strategies/evidence.py"):
        promote._check_evidence("FUNDAMENTAL")


def test_every_resolver_object_has_evidence():
    """The roster today is promotable by this rule: every named object can explain its picks."""
    for name, binding in roster.RESOLVER.items():
        if binding.obj is not None:
            promote._check_evidence(name)


# ---- the roster row (database) ------------------------------------------------------------------


def test_a_lab_without_the_method_refuses_before_writing(pg, monkeypatch, tmp_path):
    """No lab row for the method -> exit 2, and the roster is never touched.

    The lab's rules are checked first, before the Neon transaction opens, precisely so the only
    possible partial outcome is "roster written, lab note missing" and never the reverse.
    """
    _wire(monkeypatch, pg=pg)
    assert promote.run(_args(lab_db=tmp_path / "lab.sqlite")) == 2  # no method row in a fresh lab
    assert pg.execute("SELECT count(*) FROM strategies WHERE id = 'TEST-FND'").fetchone()[0] == 0


def test_promote_writes_the_row_the_night_expects(pg, monkeypatch, lab, tmp_path):
    _wire(monkeypatch, pg=pg, lab=lab)
    assert promote.run(_args(lab_db=tmp_path / "lab.sqlite")) == 0
    row = pg.execute(
        "SELECT status, promoted_from, paper_start, engine, rules_id, params FROM strategies "
        "WHERE id = 'TEST-FND'"
    ).fetchone()
    status, promoted_from, paper_start, engine, rules_id, params = row
    assert (status, promoted_from, paper_start) == ("active", METHOD, None)
    assert (engine, rules_id) == ("book", "monthly-hold")
    assert set(params) == {"spec", "digest", "backtest_gate"}
    assert params["spec"]["object"] == promote.object_name_of(FUNDAMENTAL)
    assert params["spec"]["registry_id"] is None and params["spec"]["registry_digest"] is None
    assert params["digest"] == roster.spec_digest(params["spec"])
    assert params["backtest_gate"]["passed"] is False


def test_the_written_row_rebuilds_into_the_entry_the_night_will_read(pg, monkeypatch, lab, tmp_path):
    """The round trip, which is the whole reason promote writes the definition columns.

    A row missing `object_name`, `gate_note` or `gate_applicable` builds nothing: phase 1's
    `from_row` raises, and the paper night's failure would be the WHOLE board's, not this row's.
    """
    _wire(monkeypatch, pg=pg, lab=lab)
    assert promote.run(_args(lab_db=tmp_path / "lab.sqlite")) == 0

    rows = [r for r in paper_store.read_roster_rows(pg) if r.id == "TEST-FND"]
    assert len(rows) == 1
    assert (rows[0].object_name, rows[0].registry_id, rows[0].gate_applicable) == (
        promote.object_name_of(FUNDAMENTAL), None, True,
    )
    assert rows[0].gate_note
    rebuilt = roster.from_row(rows[0])
    assert (rebuilt.obj, rebuilt.rules, rebuilt.status, rebuilt.paper_end) == (
        FUNDAMENTAL, MONTHLY_HOLD, "active", None,
    )
    assert roster.strategy_params(rebuilt)["digest"] == rows[0].params["digest"]
    # And the whole roster still builds with the new row in it: nothing was left unresolvable.
    assert "TEST-FND" in {e.id for e in roster.from_rows(paper_store.read_roster_rows(pg))}


def test_an_id_that_already_started_is_refused(pg, monkeypatch, lab, tmp_path):
    _seed_roster_row(pg, "TEST-FND", paper_start=date(2026, 1, 5))
    _wire(monkeypatch, pg=pg, lab=lab)
    with pytest.raises(promote.AlreadyStarted, match="already has paper_start"):
        promote._run(_args(lab_db=tmp_path / "lab.sqlite"))


def test_an_unrelated_existing_id_is_refused(pg, monkeypatch, lab, tmp_path):
    _seed_roster_row(pg, "TEST-FND", paper_start=None)
    _wire(monkeypatch, pg=pg, lab=lab)
    with pytest.raises(promote.RosterConflict, match="is not this promotion's row"):
        promote._run(_args(lab_db=tmp_path / "lab.sqlite"))


def test_rerunning_the_same_promotion_resumes_instead_of_inserting_twice(pg, monkeypatch, lab, tmp_path):
    _wire(monkeypatch, pg=pg, lab=lab)
    assert promote.run(_args(lab_db=tmp_path / "lab.sqlite")) == 0
    assert promote.run(_args(lab_db=tmp_path / "lab.sqlite")) == 0
    n = pg.execute("SELECT count(*) FROM strategies WHERE id = 'TEST-FND'").fetchone()[0]
    assert n == 1
    assert lab_store.get_method(lab, METHOD)["analysis"].count(lab_store.PROMOTION_MARKER) == 1


def test_retire_shares_the_inserts_transaction(pg, monkeypatch, lab, tmp_path):
    _seed_roster_row(pg, "OLD", paper_start=date(2026, 1, 5))
    _wire(monkeypatch, pg=pg, lab=lab)
    assert promote.run(_args(retire="OLD", lab_db=tmp_path / "lab.sqlite")) == 0
    rows = dict(pg.execute("SELECT id, status FROM strategies WHERE id IN ('OLD','TEST-FND')").fetchall())
    assert rows == {"OLD": "retired", "TEST-FND": "active"}


def test_a_failed_retire_leaves_no_inserted_row(pg, monkeypatch, lab, tmp_path):
    _wire(monkeypatch, pg=pg, lab=lab)
    assert promote.run(_args(retire="NO-SUCH-ID", lab_db=tmp_path / "lab.sqlite")) == 2
    pg.rollback()
    assert pg.execute("SELECT count(*) FROM strategies WHERE id = 'TEST-FND'").fetchone()[0] == 0
    assert lab_store.PROMOTION_MARKER not in lab_store.get_method(lab, METHOD)["analysis"]


def test_dry_run_prints_the_rows_and_writes_to_neither_database(pg, monkeypatch, lab, tmp_path, capsys):
    _wire(monkeypatch, pg=pg, lab=lab)
    assert promote.run(_args(dry_run=True, lab_db=tmp_path / "lab.sqlite")) == 0
    text = capsys.readouterr().out
    assert "strategies INSERT" in text and "promoted_from  M0005" in text
    assert "params.digest" in text and "REGISTRY  untouched" in text
    assert pg.execute("SELECT count(*) FROM strategies WHERE id = 'TEST-FND'").fetchone()[0] == 0
    assert lab_store.PROMOTION_MARKER not in lab_store.get_method(lab, METHOD)["analysis"]


def test_a_rejected_method_needs_the_acknowledgement(pg, monkeypatch, lab, tmp_path):
    _wire(monkeypatch, pg=pg, lab=lab)
    with pytest.raises(lab_store.LabError, match="--lab-status-stays"):
        promote._run(_args(lab_status_stays=False, lab_db=tmp_path / "lab.sqlite"))
    assert pg.execute("SELECT count(*) FROM strategies WHERE id = 'TEST-FND'").fetchone()[0] == 0


def test_an_override_with_no_reason_is_refused_before_writing(pg, monkeypatch, lab, tmp_path):
    """The roster may take a method the lab has not passed -- but not silently (D3)."""
    _wire(monkeypatch, pg=pg, lab=lab)
    with pytest.raises(promote.PromoteError, match="--lab-override-reason"):
        promote._run(_args(lab_override_reason="", lab_db=tmp_path / "lab.sqlite"))
    assert pg.execute("SELECT count(*) FROM strategies WHERE id = 'TEST-FND'").fetchone()[0] == 0
    assert lab_store.PROMOTION_MARKER not in lab_store.get_method(lab, METHOD)["analysis"]


def test_the_plan_prints_the_basis_and_the_roster_line_to_add(pg, monkeypatch, lab, tmp_path, capsys):
    _wire(monkeypatch, pg=pg, lab=lab)
    assert promote.run(_args(lab_db=tmp_path / "lab.sqlite")) == 0
    text = capsys.readouterr().out
    assert "basis           owner-override" in text
    assert f"method/variant  {METHOD} / {VARIANT}" in text
    # the `lab` fixture leaves the method at 'rejected' (the plan's prose said 'idea'); either way
    # it is an owner-override, and what the printed line must name is the status actually read.
    assert "LAB_PROVENANCE" in text and "lab_status='rejected'" in text


@pytest.mark.parametrize("dry_run", [False, True])
def test_an_allocator_without_evidence_is_refused_before_writing(
    pg, monkeypatch, lab, tmp_path, caplog, dry_run
):
    """R7: no evidence entry -> exit 2 with the file and dict to extend, and neither database moves."""
    monkeypatch.delitem(evidence.EVIDENCE, "FUNDAMENTAL")
    _wire(monkeypatch, pg=pg, lab=lab)
    caplog.set_level(logging.ERROR, logger=promote.__name__)
    assert promote.run(_args(dry_run=dry_run, lab_db=tmp_path / "lab.sqlite")) == 2
    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert "\n" not in errors[0]
    assert "EVIDENCE" in errors[0] and "seer_engine/strategies/evidence.py" in errors[0]
    pg.rollback()
    assert pg.execute("SELECT count(*) FROM strategies WHERE id = 'TEST-FND'").fetchone()[0] == 0
    assert lab_store.PROMOTION_MARKER not in lab_store.get_method(lab, METHOD)["analysis"]


def test_the_registry_is_not_appended_to():
    from seer_engine.backtest.registry import REGISTRY

    before = len(REGISTRY)
    promote.find_candidate(METHOD, VARIANT)
    from seer_engine.backtest.registry import REGISTRY as after_registry

    assert len(after_registry) == before
    assert all(c.id != VARIANT for c in after_registry)


# ---- --fractional (2026-10-07): a book variant may be traded in fractional shares --------------


def test_fractional_twin_maps_a_whole_share_preset_to_its_fractional_preset():
    from seer_engine.sim.rules import (
        DESIGN_V0,
        MONTHLY_HOLD,
        MONTHLY_HOLD_FRAC,
        MONTHLY_RANK_WEEKLY_RESIZE,
        MONTHLY_RANK_WEEKLY_RESIZE_FRAC,
        MONTHLY_RANK_WEEKLY_RESIZE_TBILL,
    )

    assert promote.fractional_twin(MONTHLY_HOLD) is MONTHLY_HOLD_FRAC
    assert promote.fractional_twin(MONTHLY_HOLD_FRAC) is MONTHLY_HOLD_FRAC
    assert promote.fractional_twin(MONTHLY_RANK_WEEKLY_RESIZE) is MONTHLY_RANK_WEEKLY_RESIZE_FRAC
    assert promote.fractional_twin(MONTHLY_RANK_WEEKLY_RESIZE_FRAC) is MONTHLY_RANK_WEEKLY_RESIZE_FRAC
    # The T-bill split cadence has no fractional preset (not asked for): still refused.
    with pytest.raises(promote.NotPromotable, match="no fractional preset matching 'monthly-rank-weekly-resize-tbill'"):
        promote.fractional_twin(MONTHLY_RANK_WEEKLY_RESIZE_TBILL)
    with pytest.raises(promote.NotPromotable, match="no fractional preset matching 'design-v0'"):
        promote.fractional_twin(DESIGN_V0)
