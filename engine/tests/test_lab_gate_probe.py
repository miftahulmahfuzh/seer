"""``lab gate``: the shared SPY 200-day gate, priced apart from everything else a book does.

Report only: N, the looks and every trial-side table stay as they were; every refusal comes before
a store loads; the transform agrees with the gate-off controls the lab already holds; the wrapper
keeps the Allocator contract and perturbs nothing; and a variant whose gate cannot be identified is
listed, never run as though the gate were off.
"""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from allocatorkit import assert_p4_identity, assert_valid_targets, everyone
from labkit import smoke_data, smoke_test_data

from seer_engine import cli, research
from seer_engine.backtest.dev import Candidate
from seer_engine.lab import gate_probe as gp
from seer_engine.lab import hardgate, runner, store
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0007_residual_momentum import N20, N20_NOTREND
from seer_engine.lab.seed import seed
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC
from seer_engine.strategies.allocator import (
    BLEND,
    Allocator,
    BlendParams,
    BlendPart,
    last_close,
    target_from_close,
)
from seer_engine.sim.book import Target
from seer_engine.strategies.f_factor import FACTOR, FactorParams
from seer_engine.strategies.f_index import TIMING, TimingParams

HERE = Path(__file__)
GATED_PARAMS = FactorParams(rank="momentum", top=6, mom_n=40, mom_skip=0, vol_n=20,
                            trend=("SPY", 200))
OPEN_PARAMS = replace(GATED_PARAMS, trend=None)
OTHER_GATE = replace(GATED_PARAMS, trend=("QQQ", 50))
TIMED_SPY = TimingParams(hold="SPY", signal="SPY", rule="sma", n=200)
ALWAYS_SPY = TimingParams(hold="SPY", signal="SPY", rule="always")


def _blend(params: FactorParams, core: TimingParams = TIMED_SPY) -> BlendParams:
    """M0030's shape on the smoke fixture: half a timed SPY core, half a gated stock sleeve."""
    return BlendParams((
        BlendPart(TIMING, core, Decimal("0.5")),
        BlendPart(FACTOR, params, Decimal("0.5")),
    ))


def _cand(cid: str, params: Any, allocator: Any = FACTOR) -> Candidate:
    return Candidate(
        id=cid, family="M0001", rules=MONTHLY_HOLD_FRAC, allocator=allocator, params=params,
        rationale="test", added=date(2026, 10, 12), owner_inputs=(),
    )


def _method(cands=None) -> Method:
    return Method(
        id="M0001", name="Fast movers, bought only in a rising market", family="factor",
        source_kind="knowledge", source_ref="", hypothesis="h", expected_failure="f",
        candidates=cands or (_cand("M0001-A", GATED_PARAMS), _cand("M0001-B", OPEN_PARAMS)),
    )


# ---- a tiny gated allocator, for the contract checks ---------------------------------------------


class GatedFake:
    """Two names, but only on days the fixture's SPY is above its own 200-day average."""

    id = "FAKE_GATE"

    def lookback(self, params: Any) -> int:
        return 200

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ("AAA", "BBB", "SPY")

    def holds(self, params: Any) -> tuple[str, ...]:
        return ()

    def uses_members(self, params: Any) -> bool:
        return False

    def targets(self, history, members, data_date, held, params) -> tuple[Target, ...]:
        out: list[Target] = []
        for symbol in ("AAA", "BBB"):
            h = history.get(symbol)
            close = last_close(h, data_date)
            if close is None:
                continue
            t = target_from_close(symbol, close, Decimal("0.5"))
            if t is not None:
                out.append(t)
        return tuple(out)

    def prepare(self, history):
        return dict(history)

    def targets_prepared(self, prepared, members, data_date, held, params) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


GATED_FAKE = GatedFake()


# ---- fixtures ------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def dev_data():
    return smoke_data()


@pytest.fixture()
def lab(tmp_path):
    path = tmp_path / "lab.sqlite"
    c = store.connect(path)
    seed(c)
    yield c, path
    c.close()


@pytest.fixture()
def recorded(lab, dev_data, monkeypatch):
    conn, _ = lab
    m = _method()
    runner.run_method(conn, m, HERE, dev_data, git_sha="x", require_commit=False)
    monkeypatch.setattr(gp, "discover", lambda: {"M0001": (m, HERE)})
    return m


def _dir(tmp_path) -> Path:
    d = tmp_path / "dev-store"
    d.mkdir()
    return d


def _loader(by_dir):
    def load(store_dir, **kw):
        got = by_dir[Path(store_dir)]
        if isinstance(got, BaseException):
            raise got
        return replace(got)

    return load


def _untouched(conn):
    """Everything `lab gate` must leave as it found it (insights excepted)."""
    return (
        store.dev_trial_count(conn),
        store.test_looks(conn),
        conn.execute("SELECT count(*) FROM trials").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_funding").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_provenance").fetchone()[0],
        tuple(tuple(r) for r in conn.execute(
            "SELECT id, status, verdict, source_sha FROM methods ORDER BY id")),
    )


def _insights(conn) -> int:
    return conn.execute("SELECT count(*) FROM insights").fetchone()[0]


def _measure(conn, dev_data, tmp_path, monkeypatch, only=None, gated_only=False):
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data}))
    plans = gp.plan_methods(conn, ["M0001"], only, gated_only=gated_only)
    geo = hardgate.geometry(conn)
    run, arms = gp.measure_store(conn, plans, d, geo.bench)
    return gp.compare(plans, arms), run


# ---- the transform -------------------------------------------------------------------------------


def test_the_transform_switches_off_a_trend_pair_and_a_timing_rule():
    off, sites = gp.gate_off(GATED_PARAMS)
    assert off == OPEN_PARAMS and len(sites) == 1 and "trend" in sites[0]
    off, sites = gp.gate_off(_blend(GATED_PARAMS))
    assert off.parts[0].params == ALWAYS_SPY
    assert off.parts[1].params == OPEN_PARAMS
    assert len(sites) == 2
    # the shares, the allocators and everything else are untouched
    assert [p.share for p in off.parts] == [p.share for p in _blend(GATED_PARAMS).parts]
    assert [p.allocator for p in off.parts] == [TIMING, FACTOR]


def test_the_transform_is_a_no_op_on_a_book_with_no_gate():
    off, sites = gp.gate_off(OPEN_PARAMS)
    assert sites == () and off is OPEN_PARAMS
    off, sites = gp.gate_off(_blend(OPEN_PARAMS, ALWAYS_SPY))
    assert sites == () and off is not None


def test_the_transform_refuses_a_gate_that_is_not_the_shared_one():
    with pytest.raises(gp.GateOffRefused, match="not the shared"):
        gp.gate_off(OTHER_GATE)
    with pytest.raises(gp.GateOffRefused, match="not the shared"):
        gp.gate_off(_blend(GATED_PARAMS, TimingParams(hold="SPY", signal="SPY", rule="sma", n=50)))
    with pytest.raises(gp.GateOffRefused, match="timing gate"):
        gp.gate_off(_blend(OPEN_PARAMS, TimingParams(hold="QQQ", signal="QQQ", rule="sma", n=200)))


def test_the_transform_refuses_params_that_reject_the_gateless_version():
    """A method built around the gate being on has no 'same book without it' to measure."""

    @dataclass(frozen=True)
    class NeedsGate:
        inner: FactorParams

        def __post_init__(self) -> None:
            if self.inner.trend is None:
                raise ValueError("inner must have a trend switch")

    with pytest.raises(gp.GateOffRefused, match="refuses the gate off"):
        gp.gate_off(NeedsGate(GATED_PARAMS))


def test_the_transform_leaves_allocators_and_non_compare_fields_alone():
    """``BlendPart.allocator`` is an Allocator and ``Tally`` is compare=False: neither is walked."""
    off, _sites = gp.gate_off(_blend(GATED_PARAMS))
    assert off.parts[0].allocator is TIMING and off.parts[1].allocator is FACTOR
    p = gp.GateParams(inner_params=GATED_PARAMS)
    assert p.tally is not gp.GateParams(inner_params=GATED_PARAMS).tally
    assert gp.GateParams(inner_params=GATED_PARAMS) == p  # tally does not enter equality


def test_the_transform_reproduces_every_recorded_gate_off_control():
    """The committed lab already holds six configurations the transform must land on exactly.

    This is the check that makes the transform trustworthy anywhere else; ``lab gate`` runs it
    before it measures anything and refuses (exit 2) when it fails.
    """
    problems, checked = gp.control_problems()
    assert problems == ()
    assert checked == len(gp.CONTROLS) + len(gp.CORE_CONTROLS)


def test_the_impure_controls_are_listed_with_their_reason():
    """M0001-TV10's recorded NOTREND sibling moves two things, so it is not a control."""
    assert ("M0001-TV10", "M0001-TV10-NOTREND") in gp.IMPURE_CONTROLS
    assert ("M0001-TV10", "M0001-TV10-NOTREND") not in gp.CONTROLS
    assert "own-vol window" in gp.IMPURE_CONTROLS[("M0001-TV10", "M0001-TV10-NOTREND")]


def test_the_m0007_pair_is_the_simplest_control_and_still_holds():
    """``ResidParams(N20)`` -> ``ResidParams(N20_NOTREND)``: the lab's own recorded gate control."""
    assert N20.trend == gp.GATE and N20_NOTREND.trend is None
    off, sites = gp.gate_off(N20)
    assert off == N20_NOTREND and len(sites) == 1


# ---- the wrapper ---------------------------------------------------------------------------------


def _cases(dev_data):
    history = dev_data.market.history
    return history, list(history["SPY"].dates.tolist())[-12:]


def test_the_wrapper_keeps_the_allocator_contract(dev_data):
    history, days = _cases(dev_data)
    wrapper = gp.wrapper_for(GATED_FAKE)
    assert isinstance(wrapper, Allocator)
    params = [gp.GateParams(inner_params=None)]
    nonempty = assert_p4_identity(
        wrapper, history, everyone(history), days,
        [frozenset(), frozenset({"AAA"})], params,
    )
    assert nonempty > 0  # the check was not vacuous


def test_the_wrapper_returns_exactly_what_the_inner_returned(dev_data):
    """A pass-through that perturbed anything would break the reproduction check silently."""
    history, days = _cases(dev_data)
    d = days[-1]
    wrapper = gp.wrapper_for(GATED_FAKE)
    inner = GATED_FAKE.targets(history, frozenset(), d, frozenset(), None)
    got = wrapper.targets(history, frozenset(), d, frozenset(),
                          gp.GateParams(inner_params=None))
    assert got == inner
    assert_valid_targets(got, history, d, frozenset())


def test_one_wrapper_per_inner_object():
    """``dev.run_registry`` refuses two allocator objects sharing an id, so the memo is required."""
    assert gp.wrapper_for(GATED_FAKE) is gp.wrapper_for(GATED_FAKE)
    assert gp.wrapper_for(GatedFake()) is not gp.wrapper_for(GATED_FAKE)
    assert gp.wrapper_for(GATED_FAKE).id == "NOGATE-FAKE_GATE"


def test_the_wrapper_delegates_preparation_and_market_fields(dev_data):
    """A MarketAware inner must keep its market: LazyPrepared would silently drop it."""
    seen: list[Any] = []

    class MarketAwareFake(GatedFake):
        id = "FAKE_MARKET_GATE"
        market_fields = ("dividends",)

        def prepare_market(self, market):
            seen.append(market)
            return dict(market.history)

    wrapper = gp.wrapper_for(MarketAwareFake())
    prepared = wrapper.prepare_market(dev_data.market)
    assert seen == [dev_data.market]
    assert set(prepared) == set(dev_data.market.history)
    assert wrapper.market_fields == ("dividends",)
    assert gp.wrapper_for(GATED_FAKE).market_fields == ("fundamentals",)


def test_the_tally_counts_the_gate_firing(dev_data):
    """The empty-decision count is how both arms prove the gate turned on and off."""
    history, days = _cases(dev_data)
    p = gp.GateParams(inner_params=None)
    wrapper = gp.wrapper_for(GATED_FAKE)
    for d in days:
        wrapper.targets(history, frozenset(), d, frozenset(), p)
    assert p.tally.calls == len(days)
    assert p.tally.empty_share == 0.0 and p.tally.mean_names == 2.0


# ---- the arms and the plan -----------------------------------------------------------------------


def test_two_arms_when_it_carries_the_gate_and_one_when_it_does_not(lab, dev_data, recorded):
    conn, _ = lab
    (plan,) = gp.plan_methods(conn, ["M0001"])
    by_id = {v.candidate.id: v for v in plan.variants}
    assert by_id["M0001-A"].status == gp.CARRIES
    assert by_id["M0001-B"].status == gp.NO_GATE
    assert [m for m, _c in gp.arms_for(by_id["M0001-A"])] == [gp.GATED, gp.UNGATED]
    assert [c.id for _m, c in gp.arms_for(by_id["M0001-A"])] == ["M0001-A", "M0001-A-NOGATE"]
    assert [m for m, _c in gp.arms_for(by_id["M0001-B"])] == [gp.GATED]
    for _mode, c in gp.arms_for(by_id["M0001-A"]):
        assert c.family == "M0001"
        assert c.rules is by_id["M0001-A"].candidate.rules  # rules are NOT stripped here


def test_an_arm_id_never_shadows_a_recorded_candidate_id():
    """M0064 really does hold both ``M0064-P50`` and a recorded ``M0064-P50-NOGATE``."""
    assert gp.arm_id_for("X-A", "-NOGATE", set()) == "X-A-NOGATE"
    assert gp.arm_id_for("X-A", "-NOGATE", {"X-A-NOGATE"}) == "X-A-NOGATE-2"
    assert gp.arm_id_for("X-A", "-NOGATE", {"X-A-NOGATE", "X-A-NOGATE-2"}) == "X-A-NOGATE-3"


def test_a_variant_whose_method_refuses_the_gate_off_is_planned_not_run(lab, dev_data, monkeypatch):
    @dataclass(frozen=True)
    class NeedsGate:
        inner: FactorParams

        def __post_init__(self) -> None:
            if self.inner.trend is None:
                raise ValueError("inner must have a trend switch")

        def as_dict(self) -> dict[str, str]:
            return self.inner.as_dict()

    class NeedsGateAllocator(GatedFake):
        id = "FAKE_NEEDS_GATE"

    conn, _ = lab
    needs = NeedsGateAllocator()
    m = _method((_cand("M0001-A", GATED_PARAMS),
                 _cand("M0001-N", NeedsGate(GATED_PARAMS), needs)))
    runner.run_method(conn, m, HERE, dev_data, git_sha="x", require_commit=False)
    monkeypatch.setattr(gp, "discover", lambda: {"M0001": (m, HERE)})
    (plan,) = gp.plan_methods(conn, ["M0001"])
    v = next(x for x in plan.variants if x.candidate.id == "M0001-N")
    assert v.status == gp.REFUSED and "trend switch" in v.why
    assert [m for m, _c in gp.arms_for(v)] == [gp.GATED]
    assert "NOT MEASURED with the gate off" in gp.format_plan(plan.variants and [plan])


def test_dry_run_classifies_without_opening_a_store(lab, recorded, tmp_path, monkeypatch, capsys):
    conn, path = lab
    before, notes = _untouched(conn), _insights(conn)
    monkeypatch.setattr(research, "load_store", _boom)
    assert cli.main(["lab", "--db", str(path), "gate", "M0001", "--store",
                     str(_dir(tmp_path)), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "carries the shared gate and can switch it off (1)" in out
    assert "M0001-A-NOGATE" in out and "M0001-B" in out
    assert "no store was opened" in out
    assert _untouched(conn) == before and _insights(conn) == notes


# ---- the measurement -----------------------------------------------------------------------------


def test_the_gate_is_priced_and_nothing_is_written(lab, dev_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    before, notes = _untouched(conn), _insights(conn)
    (rep,), run = _measure(conn, dev_data, tmp_path, monkeypatch)
    assert [r.variant.candidate.id for r in rep.rows] == ["M0001-A", "M0001-B"]
    gated_row = rep.rows[0]
    assert gated_row.modes == (gp.GATED, gp.UNGATED)
    assert gated_row.reproduced is True
    gated, off = gated_row.gated, gated_row.ungated
    # the gate's whole job is to hand back nothing sometimes; with it off, never.
    assert gated.empty_share is not None and gated.empty_share > 0.0
    assert off.empty_share == 0.0
    assert gated_row.gate_cost(gp.WHOLE) is not None
    assert set(gated.era_lead) == set(gp.ERA_LABELS)
    assert rep.rows[1].modes == (gp.GATED,) and rep.rows[1].ungated is None
    assert run.fingerprint == "smoke"
    assert _untouched(conn) == before and _insights(conn) == notes


def test_the_gated_arm_reproduces_the_recorded_trial(lab, dev_data, recorded, tmp_path, monkeypatch):
    """The pass-through wrapper must not perturb the measurement; this is how we know it does not."""
    conn, _ = lab
    (rep,), _run = _measure(conn, dev_data, tmp_path, monkeypatch)
    assert rep.reproduced is True
    for row in rep.rows:
        assert row.gated.total_return == pytest.approx(row.variant.recorded_total_return, rel=1e-12)


def test_the_ungated_arm_matches_the_recorded_sibling_that_has_no_gate(
        lab, dev_data, recorded, tmp_path, monkeypatch):
    """M0001-A with the gate off IS M0001-B, so the two must measure identically."""
    conn, _ = lab
    (rep,), _run = _measure(conn, dev_data, tmp_path, monkeypatch)
    off = rep.rows[0].ungated
    sibling = rep.rows[1].gated
    assert off.total_return == sibling.total_return
    assert off.max_drawdown == sibling.max_drawdown
    assert off.trades == sibling.trades


def test_every_arm_runs_at_the_recorded_capital_and_funding(
        lab, dev_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    seen: list = []
    real = gp.dev.run_registry

    def spy(*a, **k):
        seen.append((k.get("initial_idr"), k.get("contributions"), "window" in k, len(a[3])))
        return real(*a, **k)

    monkeypatch.setattr(gp.dev, "run_registry", spy)
    _measure(conn, dev_data, tmp_path, monkeypatch)
    n = int(store.trials_of(conn, "M0001")[0]["n"])
    want = (runner.recorded_capital(conn, n), runner.recorded_contributions(conn, n))
    assert len(seen) == 1  # both variants share capital and schedule: one call
    assert seen[0][:3] == (*want, False)  # and NO window= keyword, so the dev default binds
    assert seen[0][3] == 3  # one gated variant x two arms, one ungated variant x one


def test_gated_only_drops_the_variants_with_no_gate(lab, dev_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    (rep,), _run = _measure(conn, dev_data, tmp_path, monkeypatch, gated_only=True)
    assert [r.variant.candidate.id for r in rep.rows] == ["M0001-A"]


# ---- refusals ------------------------------------------------------------------------------------


def _boom(*a, **k):
    raise AssertionError("a store must not be loaded for a refusal")


def test_cli_refuses_unknown_or_unrun_methods_before_loading(lab, recorded, tmp_path, monkeypatch):
    _, path = lab
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _boom)
    for mid in ("M9999", "H-P7A", "nonsense"):
        assert cli.main(["lab", "--db", str(path), "gate", mid, "--store", str(d)]) == 2


def test_cli_refuses_both_or_neither_of_methods_and_all(lab, recorded, tmp_path, monkeypatch):
    _, path = lab
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _boom)
    assert cli.main(["lab", "--db", str(path), "gate", "--store", str(d)]) == 2
    assert cli.main(["lab", "--db", str(path), "gate", "M0001", "--all", "--store", str(d)]) == 2


def test_an_unknown_only_id_is_refused_before_loading(lab, recorded, tmp_path, monkeypatch):
    conn, path = lab
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _boom)
    with pytest.raises(store.LabError, match="not a recorded dev variant"):
        gp.plan_methods(conn, ["M0001"], "M0001-ZZZ")
    assert cli.main(["lab", "--db", str(path), "gate", "M0001",
                     "--only", "M0001-ZZZ", "--store", str(d)]) == 2
    (plan,) = gp.plan_methods(conn, ["M0001"], "m0001-a")
    assert [v.candidate.id for v in plan.variants] == ["M0001-A"]


def test_a_bracket_variant_is_refused_before_loading(lab, dev_data, monkeypatch):
    conn, _ = lab
    from seer_engine.sim.rules import DESIGN_V0
    from seer_engine.strategies.a import DESIGN_PARAMS, STRATEGY_A

    m = _method()
    runner.run_method(conn, m, HERE, dev_data, git_sha="x", require_commit=False)
    bracket = Candidate(id="M0001-A", family="M0001", rules=DESIGN_V0, allocator=STRATEGY_A,
                        params=DESIGN_PARAMS, rationale="t", added=date(2026, 10, 12),
                        owner_inputs=())
    monkeypatch.setattr(gp, "discover", lambda: {"M0001": (_method((bracket,)), HERE)})
    with pytest.raises(store.LabError, match="bracket engine"):
        gp.plan_methods(conn, ["M0001"])


def test_a_broken_transform_refuses_the_whole_command(lab, recorded, tmp_path, monkeypatch, capsys):
    """``control_problems`` is the gate on the gate probe: a wrong transform measures nothing."""
    conn, path = lab
    before = _untouched(conn)
    monkeypatch.setattr(research, "load_store", _boom)
    monkeypatch.setattr(gp, "control_problems", lambda: (("M0007-N20: nope",), 6))
    assert cli.main(["lab", "--db", str(path), "gate", "M0001", "--store",
                     str(_dir(tmp_path))]) == 2
    assert _untouched(conn) == before


def test_a_trial_with_no_recorded_capital_is_refused_before_loading(lab, recorded, monkeypatch):
    conn, _ = lab
    monkeypatch.setattr(store, "provenance_of", lambda c, n: None)
    with pytest.raises(store.LabError, match="no recorded starting capital"):
        gp.plan_methods(conn, ["M0001"])


def test_a_variant_gone_from_the_file_is_listed_not_run(lab, dev_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    monkeypatch.setattr(gp, "discover",
                        lambda: {"M0001": (_method((_cand("M0001-A", GATED_PARAMS),)), HERE)})
    (rep,), run = _measure(conn, dev_data, tmp_path, monkeypatch)
    assert rep.missing == ("M0001-B",)
    assert "no longer in the method file): M0001-B" in gp.format_report(rep, run)


def test_other_brakes_resolves_by_family_and_leaves_an_unknown_method_alone():
    assert gp.other_brake("M0084-WEEKLY") == gp.OTHER_BRAKES["M0084"]
    assert gp.other_brake("M0107-STOCK200-SPREAD") == gp.OTHER_BRAKES["M0107"]
    assert gp.other_brake("M0030-C70T") is None


def test_every_control_other_brakes_names_is_a_recorded_trial():
    """``OTHER_BRAKES`` claims a switched-off arm already exists; this is that claim, checked.

    The whole point of the mapping is that refusing to transform these families costs the lab
    nothing, because the comparison is already on file. If one of the named controls is ever
    renamed or dropped the claim becomes a comfortable lie, and the probe would be declining to
    measure something nobody else measures either.
    """
    if not store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    try:
        recorded = {str(r[0]) for r in conn.execute("SELECT candidate_id FROM trials")}
    finally:
        conn.close()
    for cid in ("M0007-N20-RAW", "M0084-ALWAYS", "M0107-NONE"):
        assert cid in recorded, (
            f"OTHER_BRAKES points a reader at {cid} as the already-recorded switched-off arm, "
            "and the lab no longer holds it"
        )
    for prefix, (what, where) in gp.OTHER_BRAKES.items():
        assert what.strip() and where.strip(), f"{prefix} must say what its brake is and where"


def test_a_variant_an_amendment_added_is_planned_not_called_missing(
    lab, dev_data, recorded, tmp_path, monkeypatch
):
    """A variant that lives in an amendment is still a variant of this method.

    ``plan_method`` resolved its recorded trials against ``method.candidates``, which is the
    original batch and nothing else, so every variant an amendment added came back as "recorded,
    but no longer in a method file" and was never priced. Measured on the committed lab
    2026-10-12, before this was fixed: ``lab gate M0030 M0053 --dry-run`` reported 8 recorded dev
    variants and listed all six of the 2026-10-12 amendments' as gone from their files; it reports
    14 now. The method file had not changed -- only the reader was looking at half of it.
    """
    conn, _ = lab
    amended = Method(
        id="M0001", name="Fast movers, bought only in a rising market", family="factor",
        source_kind="knowledge", source_ref="", hypothesis="h", expected_failure="f",
        candidates=(_cand("M0001-A", GATED_PARAMS),),
        amendments=(
            Amendment(
                added=date(2026, 10, 12), why="w", hypothesis="h", expected_failure="f",
                candidates=(_cand("M0001-B", OPEN_PARAMS),),
            ),
        ),
    )
    monkeypatch.setattr(gp, "discover", lambda: {"M0001": (amended, HERE)})
    (rep,), run = _measure(conn, dev_data, tmp_path, monkeypatch)
    assert rep.missing == ()
    assert [r.variant.candidate.id for r in rep.rows] == ["M0001-A", "M0001-B"]


def test_a_test_window_store_is_refused(lab, recorded, tmp_path, monkeypatch):
    conn, path = lab
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: smoke_test_data()}))
    with pytest.raises(store.LabError, match="dev window"):
        gp.load_dev_store(d)
    before = _untouched(conn)
    assert cli.main(["lab", "--db", str(path), "gate", "M0001", "--store", str(d)]) == 2
    assert _untouched(conn) == before


# ---- the command ---------------------------------------------------------------------------------


def test_cli_reports_journals_and_writes_the_grid(lab, dev_data, recorded, tmp_path, monkeypatch, capsys):
    conn, path = lab
    before, notes = _untouched(conn), _insights(conn)
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data}))
    grid = tmp_path / "out" / "grid.csv"
    argv = ["lab", "--db", str(path), "gate", "m0001", "M0001", "--store", str(d),
            "--csv", str(grid)]
    assert cli.main(argv) == 0
    out = capsys.readouterr().out
    assert "report only" in out and "reproduced all 6 of the lab's recorded gate-off controls" in out
    assert "gate switched off at:" in out
    assert "lead over SPY a year, by era:" in out and "2009-2015" in out
    assert "what the gate was worth, by era:" in out
    assert "what the shared SPY 200-day gate was worth" in out
    # Two numbers under two labels, and the misleading `Lab N (dev trials)` wording of the ten
    # §5.1 strings is NOT among them (plan invariant 9, reconciler C8). This assertion is what
    # keeps a later edit from quietly adding an eleventh copy.
    assert f"Luck hurdle N: {store.gate(conn).n} (policy {store.gate(conn).policy})" in out
    assert f"Dev trial rows: {before[0]} before, {before[0]} after" in out
    assert "Lab N (dev trials)" not in out
    assert "no method id was minted" in out
    assert _untouched(conn) == before
    assert _insights(conn) == notes + 1  # one method, named twice: one observation
    rows = list(csv.reader(grid.open(encoding="utf-8")))
    assert rows[0] == list(gp.CSV_HEADER)
    assert [(r[1], r[2]) for r in rows[1:]] == [
        ("M0001-A", "gated"), ("M0001-A", "ungated"), ("M0001-B", "gated"),
    ]
    assert rows[1][4] == gp.CARRIES and rows[3][4] == gp.NO_GATE


def test_no_journal_writes_nothing(lab, dev_data, recorded, tmp_path, monkeypatch, capsys):
    conn, path = lab
    before, notes = _untouched(conn), _insights(conn)
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data}))
    assert cli.main(["lab", "--db", str(path), "gate", "M0001", "--store", str(d),
                     "--no-journal"]) == 0
    assert "No journal entry" in capsys.readouterr().out
    assert _untouched(conn) == before and _insights(conn) == notes


def test_the_journal_entry_is_plain_words(lab, dev_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    (rep,), _run = _measure(conn, dev_data, tmp_path, monkeypatch)
    before = _untouched(conn)
    with conn:
        entry = gp.journal(conn, rep)
    row = conn.execute("SELECT * FROM insights WHERE id = ?", (entry,)).fetchone()
    assert row["kind"] == "observation" and row["method_id"] == "M0001"
    assert row["title"].endswith("what its market safety rule was worth")
    for text in (row["title"], row["body"]):
        for banned in ("M0001", "-NOGATE", "SPY", "200-day average", "`", "DSR", "MAR",
                       "trend", "params"):
            assert banned not in text, banned
    assert "count of tries did not move" in row["body"]
    assert _untouched(conn) == before


def test_the_help_strings_still_format(capsys):
    """argparse %-interpolates every help= string; a bare % there kills `lab --help`."""
    with pytest.raises(SystemExit) as e:
        cli.main(["lab", "gate", "--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    for flag in ("--all", "--only", "--gated-only", "--dry-run", "--no-journal", "--csv"):
        assert flag in out, flag
    with pytest.raises(SystemExit):
        cli.main(["lab", "--help"])
    assert "gate" in capsys.readouterr().out
