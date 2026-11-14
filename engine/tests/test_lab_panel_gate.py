"""``lab run``'s panel gate (lab/hardgate.py, D21; SERA_SIGNAL_PANEL_PLAN.md phase 5, R4.1 and R4.2).

A method with an arm that chooses among index members runs only when it names a signal whose
published panel verdict clears on the dev store the run loads -- and then only on that signal's
standard book, beside declared controls -- or when it declares a panel exemption. Every refusal is
a ``store.LabError`` raised in ``runner.preflight`` before any store is loaded or any backtest
runs, so it records nothing and spends no N. ``lab run`` turns it into exit 2.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from labkit import smoke_data

from seer_engine import research
from seer_engine.backtest.dev import Candidate
from seer_engine.commands import lab as lab_cmd
from seer_engine.lab import hardgate, panel, runner, signal_book, store, tree_rank
from seer_engine.lab import method as method_mod
from seer_engine.lab import signal as signals
from seer_engine.lab.method import Amendment, Method, config_digest
from seer_engine.lab.seed import seed
from seer_engine.sim.rules import DESIGN_V0, MONTHLY_HOLD
from seer_engine.strategies.a import DESIGN_PARAMS, STRATEGY_A
from seer_engine.strategies.f_factor import FACTOR, FactorParams
from seer_engine.strategies.f_index import TIMING, TimingParams

HERE = Path(__file__)
COMMITTED = Path(tree_rank.__file__)  # tracked and clean, as a committed method file is
ADDED = date(2026, 11, 13)
SID = "S9001"
EXEMPT = "chassis: a test fixture's book, not a stock-picking idea"


def _score(history, market, pool, data_date):
    return {s: float(len(history[s])) for s in pool if s in history}


SIGNAL = signals.Signal(
    id=SID, name="test ranking", family="test", source_kind="knowledge", source_ref="",
    hypothesis="h", expected_failure="f", lookback=1, score=_score,
)


class _Reached(Exception):
    """Raised by a stubbed step to prove the run got past the gate to it."""


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    seed(c)
    yield c
    c.close()


@pytest.fixture(scope="module")
def data():
    return smoke_data()


@pytest.fixture()
def registered(monkeypatch):
    monkeypatch.setattr(signals, "discover", lambda: {SID: (SIGNAL, HERE)})


def _timing(cid: str, n: int = 50) -> Candidate:
    return Candidate(
        id=cid, family=cid.split("-")[0], rules=MONTHLY_HOLD, allocator=TIMING,
        params=TimingParams(hold="SPY", signal="SPY", rule="sma", n=n),
        rationale="test", added=ADDED, owner_inputs=(),
    )


def _picker(cid: str, rationale: str = "a hand-built momentum book") -> Candidate:
    return Candidate(
        id=cid, family=cid.split("-")[0], rules=MONTHLY_HOLD, allocator=FACTOR,
        params=FactorParams(rank="momentum", top=5, trend=None),
        rationale=rationale, added=ADDED, owner_inputs=(),
    )


def _method(*cands: Candidate, mid: str = "M0001", **kw) -> Method:
    return Method(
        id=mid, name="panel gate test", family="test", source_kind="knowledge", source_ref="",
        hypothesis="h", expected_failure="f", candidates=tuple(cands), **kw,
    )


def _signal_method(*extra: Candidate, sig=SIGNAL, mid: str = "M0001") -> Method:
    return _method(*signal_book.standard_candidates(sig, mid, ADDED), *extra, mid=mid, signal=SID)


def _seed_panel(conn, *, sha: str | None = None, dev_fp: str = "smoke", clears: bool = True) -> None:
    """One recorded panel for S9001: every era on the dev and the survivorship store.

    A clearing reading is plainly clear (controlled slope t = 5, positive recent spread, positive
    survivorship slope); a failing one is the same numbers with the sign flipped.
    """
    sign = 1.0 if clears else -1.0
    with conn:
        store.insert_panel_signal(conn, store.PanelSignalRow(
            id=SID, kind="signal", name="test ranking", family="test", hypothesis="h",
            expected_failure="f", source_kind="knowledge", source_ref="", method_id=None,
            source_sha=signals.source_sha(HERE) if sha is None else sha,
            created="2026-11-13T00:00:00+00:00",
        ))
        store.insert_panel_results(conn, [
            store.PanelResultRow(
                signal_id=SID, rule_id=panel.RULE_ID, store_role=role, store_fingerprint=fp,
                era=era, months=120, mean_pool=400.0, mean_scored=380.0,
                ic_mean=0.03 * sign, ic_t=4.0 * sign, spread_top=0.06 * sign, spread_t=4.0 * sign,
                fm_slope=0.004 * sign, fm_t=5.0 * sign, top_turnover=0.3,
                picks_hash=f"test-{SID}", git_sha="test", measured="2026-11-13T00:00:00+00:00",
            )
            for role, fp in (("dev", dev_fp), ("survivorship", f"{dev_fp}-sv"))
            for era in panel.ERAS
        ])


def _recorded(conn, mid: str = "M0001") -> tuple[int, int, bool]:
    """(dev trials, methods with a dev trial -- what the luck gate's N counts, whether ``mid`` has a row)."""
    trials, methods = conn.execute(
        "SELECT COUNT(*), COUNT(DISTINCT method_id) FROM trials WHERE window = 'dev'"
    ).fetchone()
    return int(trials), int(methods), store.get_method(conn, mid) is not None


def _no_backtest(*_a, **_k):
    raise AssertionError("the panel gate must refuse before any backtest")


def _reached(*_a, **_k):
    raise _Reached()


# ---- which methods the gate binds ---------------------------------------------------------


def test_a_member_picking_arm_binds_and_a_market_arm_does_not():
    assert hardgate.picks_members(_picker("M0001-A"))
    assert not hardgate.picks_members(_timing("M0001-B"))
    bracket = Candidate(
        id="M0001-C", family="M0001", rules=DESIGN_V0, allocator=STRATEGY_A,
        params=DESIGN_PARAMS, rationale="t", added=ADDED, owner_inputs=(),
    )
    assert hardgate.picks_members(bracket)


def test_a_method_that_picks_no_member_is_not_bound(conn):
    assert runner.preflight(conn, _method(_timing("M0001-A")), HERE, require_commit=False) is None


# ---- R4.1: neither a cleared signal nor an exemption ----------------------------------------


def test_an_unpanelled_member_picker_is_refused_in_preflight(conn):
    before = _recorded(conn)
    with pytest.raises(store.LabError, match="D21") as refused:
        runner.preflight(
            conn, _method(_picker("M0001-A"), _timing("M0001-B")), HERE, require_commit=False
        )
    text = str(refused.value)
    assert "M0001-A" in text and "M0001-B" not in text
    assert "lab panel" in text and "panel_exempt" in text
    assert "Nothing ran and nothing was recorded" in text
    assert _recorded(conn) == before


def test_run_method_refuses_before_any_backtest(conn, data, monkeypatch):
    monkeypatch.setattr(runner.dev, "run_registry", _no_backtest)
    before = _recorded(conn)
    with pytest.raises(store.LabError, match="D21"):
        runner.run_method(conn, _method(_picker("M0001-A")), HERE, data, git_sha="x", require_commit=False)
    assert _recorded(conn) == before


def test_lab_run_exits_2_before_loading_a_store(tmp_path, monkeypatch):
    db = tmp_path / "lab.sqlite"
    c = store.connect(db)
    seed(c)
    before = _recorded(c)
    c.close()
    m = _method(_picker("M0001-A"))
    monkeypatch.setattr(method_mod, "discover", lambda: {"M0001": (m, COMMITTED)})
    monkeypatch.setattr(research, "load_store", _no_backtest)
    rc = lab_cmd.run(argparse.Namespace(
        db=db, lab_command="run", method="M0001", store=tmp_path / "store", allow_coverage=0.8,
    ))
    assert rc == 2
    c = store.connect(db)
    assert _recorded(c) == before
    c.close()


def test_the_gate_holds_for_an_amendment(conn, data):
    runner.run_method(conn, _method(_timing("M0001-A")), HERE, data, git_sha="x", require_commit=False)
    amendment = Amendment(
        added=ADDED, why="w", hypothesis="h", expected_failure="f",
        candidates=(_picker("M0001-P"),),
    )
    before = _recorded(conn)
    with pytest.raises(store.LabError, match="D21"):
        runner.preflight(
            conn, _method(_timing("M0001-A"), amendments=(amendment,)), HERE,
            require_commit=False, amend=True,
        )
    assert _recorded(conn) == before
    exempt = _method(_timing("M0001-A"), amendments=(amendment,), panel_exempt=EXEMPT)
    assert runner.preflight(conn, exempt, HERE, require_commit=False, amend=True) is amendment


# ---- the exemption --------------------------------------------------------------------------


@pytest.mark.parametrize("why", ["chassis: a brake on a recorded book", "control-study: twin spread", "market: breadth"])
def test_a_declared_exemption_lets_a_member_picker_through(conn, why):
    m = _method(_picker("M0001-A"), panel_exempt=why)
    assert runner.preflight(conn, m, HERE, require_commit=False) is None


# ---- the signal path (R4.1) -----------------------------------------------------------------


def test_an_unknown_signal_is_refused(conn, monkeypatch):
    monkeypatch.setattr(signals, "discover", lambda: {})
    with pytest.raises(store.LabError, match="names signal S9001, and no"):
        runner.preflight(conn, _signal_method(), HERE, require_commit=False, dev_fingerprint="smoke")


def test_a_signal_with_no_panel_on_this_store_is_refused(conn, registered):
    with pytest.raises(store.LabError, match="lab panel S9001"):
        runner.preflight(conn, _signal_method(), HERE, require_commit=False, dev_fingerprint="smoke")


def test_a_panel_on_another_dev_store_does_not_count(conn, registered):
    _seed_panel(conn, dev_fp="another-store")
    with pytest.raises(store.LabError, match="lab panel S9001"):
        runner.preflight(conn, _signal_method(), HERE, require_commit=False, dev_fingerprint="smoke")


def test_a_signal_that_did_not_clear_is_refused(conn, registered):
    _seed_panel(conn, clears=False)
    before = _recorded(conn)
    with pytest.raises(store.LabError, match="did not clear the panel"):
        runner.preflight(conn, _signal_method(), HERE, require_commit=False, dev_fingerprint="smoke")
    assert _recorded(conn) == before


def test_a_signal_file_changed_since_its_panel_is_refused(conn, registered):
    _seed_panel(conn, sha="0" * 64)
    with pytest.raises(store.LabError, match="no longer hashes"):
        runner.preflight(conn, _signal_method(), HERE, require_commit=False, dev_fingerprint="smoke")


def test_a_cleared_signal_on_its_standard_book_passes(conn, registered):
    _seed_panel(conn)
    assert runner.preflight(conn, _signal_method(), HERE, require_commit=False, dev_fingerprint="smoke") is None


def test_run_method_judges_the_panel_of_the_store_it_loaded(conn, data, registered, monkeypatch):
    """run_method hands preflight data.fingerprint ('smoke' for labkit's store), not a default."""
    _seed_panel(conn)  # recorded on "smoke"
    monkeypatch.setattr(runner.dev, "run_registry", _reached)
    with pytest.raises(_Reached):
        runner.run_method(conn, _signal_method(), HERE, data, git_sha="x", require_commit=False)


def test_run_method_refuses_a_panel_on_another_store(conn, data, registered, monkeypatch):
    _seed_panel(conn, dev_fp="another-store")
    monkeypatch.setattr(runner.dev, "run_registry", _no_backtest)
    with pytest.raises(store.LabError, match="lab panel S9001"):
        runner.run_method(conn, _signal_method(), HERE, data, git_sha="x", require_commit=False)


def test_the_fingerprint_defaults_to_the_store_lab_run_would_load(conn, registered, tmp_path, monkeypatch):
    where = tmp_path / "store"
    where.mkdir()
    (where / "manifest.json").write_text(json.dumps({"fingerprint": "fp-from-manifest"}), encoding="utf-8")
    monkeypatch.setenv("SEER_RESEARCH_STORE", str(where))
    assert hardgate.dev_store_fingerprint() == "fp-from-manifest"
    _seed_panel(conn, dev_fp="fp-from-manifest")
    assert runner.preflight(conn, _signal_method(), HERE, require_commit=False) is None


def test_an_unreadable_dev_store_refuses_a_signal_method(conn, registered, tmp_path, monkeypatch):
    monkeypatch.setenv("SEER_RESEARCH_STORE", str(tmp_path / "missing"))
    with pytest.raises(store.LabError, match="SEER_RESEARCH_STORE"):
        runner.preflight(conn, _signal_method(), HERE, require_commit=False)


# ---- R4.2: a signal method books the standard chassis and nothing else ------------------------


def test_a_hand_built_treatment_beside_a_signal_is_refused(conn, registered):
    _seed_panel(conn)  # the signal clears: the extra arm is the only thing wrong
    before = _recorded(conn)
    with pytest.raises(store.LabError, match="M0001-HAND") as refused:
        runner.preflight(
            conn, _signal_method(_picker("M0001-HAND")), HERE, require_commit=False,
            dev_fingerprint="smoke",
        )
    assert "standard book" in str(refused.value)
    assert _recorded(conn) == before


def test_the_arm_shape_is_refused_before_any_store_is_read(conn, registered, tmp_path, monkeypatch):
    monkeypatch.setenv("SEER_RESEARCH_STORE", str(tmp_path / "missing"))
    with pytest.raises(store.LabError, match="M0001-HAND"):
        runner.preflight(conn, _signal_method(_timing("M0001-HAND")), HERE, require_commit=False)


def test_a_standard_book_of_another_signal_is_refused(conn, registered):
    _seed_panel(conn)
    other = replace(SIGNAL, id="S9002")
    m = _method(*signal_book.standard_candidates(other, "M0001", ADDED), signal=SID)
    with pytest.raises(store.LabError, match="standard book"):
        runner.preflight(conn, m, HERE, require_commit=False, dev_fingerprint="smoke")


def test_a_declared_control_beside_the_standard_book_is_allowed(conn, registered):
    _seed_panel(conn)
    foil = _picker("M0001-CTRL", rationale="Control: twenty names in hash order, registered to be beaten.")
    assert runner.preflight(
        conn, _signal_method(foil), HERE, require_commit=False, dev_fingerprint="smoke"
    ) is None


# ---- the two fields ---------------------------------------------------------------------------


def test_signal_and_exemption_are_validated_at_construction():
    with pytest.raises(ValueError, match="S0001"):
        _method(_timing("M0001-A"), signal="0001")
    with pytest.raises(ValueError, match="panel_exempt"):
        _method(_timing("M0001-A"), panel_exempt="because")
    with pytest.raises(ValueError, match="panel_exempt"):
        _method(_timing("M0001-A"), panel_exempt="chassis:   ")
    with pytest.raises(ValueError, match="never both"):
        _method(_timing("M0001-A"), signal="S0001", panel_exempt=EXEMPT)
    with pytest.raises(TypeError, match="panel_exempt"):
        _method(_timing("M0001-A"), panel_exempt=None)


def test_the_method_and_signal_id_patterns_agree():
    assert method_mod.SIGNAL_ID.pattern == signals.SIGNAL_ID.pattern


def test_the_two_fields_move_no_config_digest():
    plain = _method(_picker("M0001-A"))
    exempt = _method(_picker("M0001-A"), panel_exempt=EXEMPT)
    assert [config_digest(c) for c in plain.candidates] == [config_digest(c) for c in exempt.candidates]


def test_discovering_the_method_files_never_consults_the_gate(monkeypatch):
    def tripwire(*_a, **_k):
        raise AssertionError("the panel gate fired outside lab run")

    monkeypatch.setattr(hardgate, "panel_refusal", tripwire)
    monkeypatch.setattr(hardgate, "panel_gate", tripwire)
    assert method_mod.discover()
