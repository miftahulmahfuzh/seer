"""``lab exposure``: a method's own picks, measured apart from the money it parks.

Report only: N, the looks and every trial-side table stay as they were; every refusal comes before
a store loads; the wrapper keeps the Allocator contract; and a method that parks half its book
reads differently with the parked half removed.
"""

from __future__ import annotations

import csv
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from allocatorkit import assert_p4_identity, assert_valid_targets, everyone, upto
from labkit import smoke_data, smoke_test_data

from seer_engine import cli, research
from seer_engine.backtest.dev import Candidate
from seer_engine.lab import exposure as exp
from seer_engine.lab import hardgate, runner, store
from seer_engine.lab.method import Method
from seer_engine.lab.seed import seed
from seer_engine.sim.book import WEIGHT_QUANTUM, Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC, MONTHLY_HOLD_TBILL
from seer_engine.strategies.allocator import (
    BLEND,
    Allocator,
    BlendParams,
    BlendPart,
    last_close,
    target_from_close,
)
from seer_engine.strategies.f_factor import FACTOR, FactorParams
from seer_engine.strategies.f_index import TIMING, TimingParams

HERE = Path(__file__)
PARKED = "SPY"
PARAMS_A = FactorParams(rank="lowvol", top=6, mom_n=60, mom_skip=0, vol_n=20, trend=None)
PARAMS_B = FactorParams(rank="momentum", top=6, mom_n=40, mom_skip=0, vol_n=20, trend=None)
ALWAYS_SPY = TimingParams(hold=PARKED, signal=PARKED, rule="always")


def _blend(params: FactorParams) -> BlendParams:
    """Half a timed-off-never SPY core, half a stock sleeve: M0030's shape on the smoke fixture."""
    return BlendParams((
        BlendPart(TIMING, ALWAYS_SPY, Decimal("0.5")),
        BlendPart(FACTOR, params, Decimal("0.5")),
    ))


def _cand(cid: str, params: FactorParams, *, parks: bool = True) -> Candidate:
    allocator: Any = BLEND if parks else FACTOR
    return Candidate(
        id=cid, family="M0001", rules=MONTHLY_HOLD_FRAC, allocator=allocator,
        params=_blend(params) if parks else params,
        rationale="test", added=date(2026, 10, 12), owner_inputs=(),
    )


def _method(cands=None) -> Method:
    return Method(
        id="M0001", name="Half the market, half quiet stocks", family="factor",
        source_kind="knowledge", source_ref="", hypothesis="h", expected_failure="f",
        candidates=cands or (_cand("M0001-A", PARAMS_A), _cand("M0001-B", PARAMS_B)),
    )


# ---- a tiny parking allocator, for the contract checks -------------------------------------------


class ParkingFake:
    """Half its weight in one fixed instrument, half split between two members with a bar on d."""

    id = "FAKE_PARK"

    def lookback(self, params: Any) -> int:
        return 1

    def symbols(self, params: Any) -> tuple[str, ...]:
        return tuple(sorted({PARKED, "AAA", "BBB"}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (PARKED,)

    def uses_members(self, params: Any) -> bool:
        return False

    def targets(self, history, members, data_date, held, params) -> tuple[Target, ...]:
        out: list[Target] = []
        for symbol, weight in ((PARKED, "0.5"), ("AAA", "0.25"), ("BBB", "0.25")):
            h = history.get(symbol)
            close = last_close(h, data_date)
            if close is None or (h.index_of(data_date) is None and symbol not in held):
                continue
            t = target_from_close(symbol, close, Decimal(weight))
            if t is not None:
                out.append(t)
        return tuple(out)

    def prepare(self, history):
        return dict(history)

    def targets_prepared(self, prepared, members, data_date, held, params) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


PARKING = ParkingFake()


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
    monkeypatch.setattr(exp, "discover", lambda: {"M0001": (m, HERE)})
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
    """Everything `lab exposure` must leave as it found it (insights excepted)."""
    return (
        store.dev_trial_count(conn),
        store.test_looks(conn),
        conn.execute("SELECT count(*) FROM trials").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_funding").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_provenance").fetchone()[0],
        conn.execute("SELECT count(*) FROM method_amendments").fetchone()[0],
        tuple(tuple(r) for r in conn.execute(
            "SELECT id, status, verdict, source_sha FROM methods ORDER BY id")),
    )


def _insights(conn) -> int:
    return conn.execute("SELECT count(*) FROM insights").fetchone()[0]


def _measure(conn, dev_data, tmp_path, monkeypatch, only=None):
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data}))
    plans = exp.plan_methods(conn, ["M0001"], only)
    geo = hardgate.geometry(conn)
    run, arms = exp.measure_store(conn, plans, d, geo.bench)
    return exp.compare(plans, arms), run


# ---- the wrapper keeps the Allocator contract ----------------------------------------------------


def _cases(dev_data):
    """The fixture's histories and its last twelve sessions.

    ``History.dates`` is ``datetime64[D]``; ``.tolist()`` already yields ``datetime.date``.
    """
    history = dev_data.market.history
    return history, list(history[PARKED].dates.tolist())[-12:]


@pytest.mark.parametrize("mode", [exp.PICKS, exp.FULL, exp.PARK])
def test_the_wrapper_keeps_the_allocator_contract(dev_data, mode):
    history, days = _cases(dev_data)
    wrapper = exp.wrapper_for(PARKING)
    assert isinstance(wrapper, Allocator)
    params = [exp.ExposureParams(mode=mode, inner_params=None, park=frozenset({PARKED}))]
    nonempty = assert_p4_identity(
        wrapper, history, everyone(history), days,
        [frozenset(), frozenset({PARKED, "AAA"})], params,
    )
    assert nonempty > 0  # the check was not vacuous


def test_one_wrapper_per_inner_object():
    """``dev.run_registry`` refuses two allocator objects sharing an id, so the memo is required."""
    assert exp.wrapper_for(PARKING) is exp.wrapper_for(PARKING)
    other = ParkingFake()
    assert exp.wrapper_for(other) is not exp.wrapper_for(PARKING)
    assert exp.wrapper_for(PARKING).id == "EXPOSURE-FAKE_PARK"


def test_the_wrapper_delegates_preparation_to_prepare_for(dev_data):
    """A MarketAware inner must keep its market: LazyPrepared would silently drop it."""
    seen: list[Any] = []

    class MarketAwareFake(ParkingFake):
        id = "FAKE_MARKET"

        def prepare_market(self, market):
            seen.append(market)
            return dict(market.history)

    wrapper = exp.wrapper_for(MarketAwareFake())
    prepared = wrapper.prepare_market(dev_data.market)
    assert seen == [dev_data.market]
    assert set(prepared) == set(dev_data.market.history)


# ---- the re-weighting arithmetic -----------------------------------------------------------------


def _targets(dev_data, data_date):
    return PARKING.targets(dev_data.market.history, frozenset(), data_date, frozenset(), None)


def test_reweight_drops_rescales_and_stays_a_legal_basket(dev_data):
    history, days = _cases(dev_data)
    d = days[-1]
    full_basket = _targets(dev_data, d)
    assert [t.symbol for t in full_basket] == [PARKED, "AAA", "BBB"]
    park = frozenset({PARKED})

    picks = exp.reweight(full_basket, exp.PICKS, park)
    assert [t.symbol for t in picks] == ["AAA", "BBB"]
    assert [t.weight for t in picks] == [Decimal("0.25"), Decimal("0.25")]  # weights kept

    full = exp.reweight(full_basket, exp.FULL, park)
    assert [t.symbol for t in full] == ["AAA", "BBB"]
    assert sum(t.weight for t in full) == Decimal("1.000000")

    parked = exp.reweight(full_basket, exp.PARK, park)
    assert [(t.symbol, t.weight) for t in parked] == [(PARKED, Decimal("1.000000"))]

    for got in (picks, full, parked):
        assert_valid_targets(got, history, d, frozenset())
        for t in got:
            assert t.weight.quantize(WEIGHT_QUANTUM) == t.weight

    assert exp.reweight((), exp.FULL, park) == ()
    assert exp.reweight(full_basket, exp.PARK, frozenset()) == ()


def test_reweight_with_an_empty_park_set_changes_nothing_on_the_picks_arm(dev_data):
    _history, days = _cases(dev_data)
    basket = _targets(dev_data, days[-1])
    assert exp.reweight(basket, exp.PICKS, frozenset()) == basket


def test_reweight_rescales_an_awkward_sum_without_exceeding_one(dev_data):
    """Three equal thirds rescale to 0.333333 each: floored down, so Σ is 0.999999, never > 1."""
    _history, days = _cases(dev_data)
    d = days[-1]
    close = last_close(dev_data.market.history["AAA"], d)
    third = Decimal("0.111111")
    basket = tuple(
        target_from_close(s, close, third) for s in ("AAA", "BBB", "CCC")
    )
    got = exp.reweight(basket, exp.FULL, frozenset())
    assert sum(t.weight for t in got) <= Decimal(1)
    assert all(t.weight == Decimal("0.333333") for t in got)


# ---- the park set and the arms -------------------------------------------------------------------


def test_the_park_set_is_read_from_holds_and_the_idle_instrument():
    c = _cand("M0001-A", PARAMS_A)
    assert exp.park_set(c) == frozenset({PARKED})
    plain = _cand("M0001-C", PARAMS_A, parks=False)
    assert exp.park_set(plain) == frozenset()
    idle = replace(plain, rules=MONTHLY_HOLD_TBILL)  # the one shipped rules value with an idle leg
    assert exp.park_set(idle) == frozenset({"BIL"})
    assert exp.arm_rules(idle.rules).idle_symbol is None
    assert exp.arm_rules(plain.rules) is plain.rules


def test_four_arms_when_it_parks_and_three_when_it_does_not(lab, dev_data, recorded):
    conn, _ = lab
    (plan,) = exp.plan_methods(conn, ["M0001"])
    modes = [mode for mode, _c in exp.arms_for(plan.variants[0])]
    assert modes == [exp.BOOK, exp.PICKS, exp.FULL, exp.PARK]
    ids = [c.id for _m, c in exp.arms_for(plan.variants[0])]
    assert ids == ["M0001-A", "M0001-A-PICKS", "M0001-A-FULL", "M0001-A-PARK"]
    for _mode, c in exp.arms_for(plan.variants[0]):
        assert c.family == "M0001"
    bare = replace(plan.variants[0], park=frozenset(), holds=frozenset())
    assert [m for m, _c in exp.arms_for(bare)] == [exp.BOOK, exp.PICKS, exp.FULL]


# ---- the measurement -----------------------------------------------------------------------------


def test_the_parked_half_is_separated_and_nothing_is_written(lab, dev_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    before, notes = _untouched(conn), _insights(conn)
    (rep,), run = _measure(conn, dev_data, tmp_path, monkeypatch)
    assert [r.variant.candidate.id for r in rep.rows] == ["M0001-A", "M0001-B"]
    row = rep.rows[0]
    assert row.modes == (exp.BOOK, exp.PICKS, exp.FULL, exp.PARK)
    assert row.reproduced is True
    book, picks, full, park = (row.arms[m] for m in row.modes)
    # Half the book is a fixed SPY holding, so the picks sleeve holds about half the money.
    assert picks.exposure < book.exposure
    assert full.exposure > picks.exposure
    assert park.exposure > 0.0
    assert picks.empty_share == 0.0 and picks.mean_names is not None
    assert book.empty_share is None  # the recorded arm runs unwrapped, so nothing counted it
    assert set(book.era_lead) == set(exp.ERA_LABELS)
    assert run.fingerprint == "smoke"
    assert _untouched(conn) == before and _insights(conn) == notes


def test_the_picks_arm_reproduces_the_book_when_nothing_is_parked(lab, dev_data, tmp_path, monkeypatch):
    conn, _ = lab
    m = _method((_cand("M0001-C", PARAMS_A, parks=False),))
    runner.run_method(conn, m, HERE, dev_data, git_sha="x", require_commit=False)
    monkeypatch.setattr(exp, "discover", lambda: {"M0001": (m, HERE)})
    (rep,), _run = _measure(conn, dev_data, tmp_path, monkeypatch)
    row = rep.rows[0]
    assert row.modes == (exp.BOOK, exp.PICKS, exp.FULL)  # no park column
    assert row.arms[exp.PICKS].total_return == row.arms[exp.BOOK].total_return
    assert row.arms[exp.PICKS].exposure == row.arms[exp.BOOK].exposure


def test_every_arm_runs_at_the_recorded_capital_and_funding(lab, dev_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    seen: list = []
    real = exp.dev.run_registry

    def spy(*a, **k):
        seen.append((k.get("initial_idr"), k.get("contributions"), "window" in k, len(a[3])))
        return real(*a, **k)

    monkeypatch.setattr(exp.dev, "run_registry", spy)
    _measure(conn, dev_data, tmp_path, monkeypatch)
    n = int(store.trials_of(conn, "M0001")[0]["n"])
    want = (runner.recorded_capital(conn, n), runner.recorded_contributions(conn, n))
    assert len(seen) == 1  # both variants share capital and schedule: one call
    assert seen[0][:3] == (*want, False)  # and NO window= keyword, so the dev default binds
    assert seen[0][3] == 8  # two variants x four arms


# ---- refusals ------------------------------------------------------------------------------------


def _boom(*a, **k):
    raise AssertionError("a store must not be loaded for a refusal")


def test_cli_refuses_unknown_or_unrun_methods_before_loading(lab, recorded, tmp_path, monkeypatch):
    _, path = lab
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _boom)
    for mid in ("M9999", "H-P7A", "nonsense"):
        assert cli.main(["lab", "--db", str(path), "exposure", mid, "--store", str(d)]) == 2


def test_an_unknown_only_id_is_refused_before_loading(lab, recorded, tmp_path, monkeypatch):
    conn, path = lab
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _boom)
    with pytest.raises(store.LabError, match="not a recorded dev variant"):
        exp.plan_methods(conn, ["M0001"], "M0001-ZZZ")
    assert cli.main(["lab", "--db", str(path), "exposure", "M0001",
                     "--only", "M0001-ZZZ", "--store", str(d)]) == 2
    (plan,) = exp.plan_methods(conn, ["M0001"], "m0001-a")
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
    monkeypatch.setattr(exp, "discover", lambda: {"M0001": (_method((bracket,)), HERE)})
    with pytest.raises(store.LabError, match="bracket engine"):
        exp.plan_methods(conn, ["M0001"])


def test_a_trial_with_no_recorded_capital_is_refused_before_loading(lab, recorded, monkeypatch):
    conn, _ = lab
    monkeypatch.setattr(store, "provenance_of", lambda c, n: None)
    with pytest.raises(store.LabError, match="no recorded starting capital"):
        exp.plan_methods(conn, ["M0001"])


def test_a_variant_gone_from_the_file_is_listed_not_run(lab, dev_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    monkeypatch.setattr(exp, "discover", lambda: {"M0001": (_method((_cand("M0001-A", PARAMS_A),)), HERE)})
    (rep,), run = _measure(conn, dev_data, tmp_path, monkeypatch)
    assert rep.missing == ("M0001-B",)
    assert "no longer in the method file): M0001-B" in exp.format_report(rep, run)


def test_a_test_window_store_is_refused(lab, recorded, tmp_path, monkeypatch):
    conn, path = lab
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: smoke_test_data()}))
    with pytest.raises(store.LabError, match="dev window"):
        exp.load_dev_store(d)
    monkeypatch.setattr(research, "load_store", _loader({d: ValueError("declares the 'test' window")}))
    with pytest.raises(store.LabError, match="test-window store is refused"):
        exp.load_dev_store(d)
    before = _untouched(conn)
    assert cli.main(["lab", "--db", str(path), "exposure", "M0001", "--store", str(d)]) == 2
    assert _untouched(conn) == before


# ---- the command ---------------------------------------------------------------------------------


def test_cli_reports_journals_and_writes_the_grid(lab, dev_data, recorded, tmp_path, monkeypatch, capsys):
    conn, path = lab
    before, notes = _untouched(conn), _insights(conn)
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data}))
    grid = tmp_path / "out" / "grid.csv"
    argv = ["lab", "--db", str(path), "exposure", "m0001", "M0001", "--store", str(d),
            "--csv", str(grid)]
    assert cli.main(argv) == 0
    out = capsys.readouterr().out
    assert "report only" in out and "money in its own picks" in out
    assert "parks money in: SPY" in out
    assert "lead over SPY a year, by era:" in out and "2009-2015" in out
    assert f"Lab N (dev trials): {before[0]} before, {before[0]} after" in out
    assert "no method id was minted" in out
    assert _untouched(conn) == before
    assert _insights(conn) == notes + 1  # one method, named twice: one observation
    rows = list(csv.reader(grid.open(encoding="utf-8")))
    assert rows[0] == list(exp.CSV_HEADER)
    assert [(r[1], r[2]) for r in rows[1:]] == [
        ("M0001-A", "book"), ("M0001-A", "picks"), ("M0001-A", "full"), ("M0001-A", "park"),
        ("M0001-B", "book"), ("M0001-B", "picks"), ("M0001-B", "full"), ("M0001-B", "park"),
    ]


def test_no_journal_writes_nothing(lab, dev_data, recorded, tmp_path, monkeypatch, capsys):
    conn, path = lab
    before, notes = _untouched(conn), _insights(conn)
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data}))
    assert cli.main(["lab", "--db", str(path), "exposure", "M0001", "--store", str(d),
                     "--no-journal"]) == 0
    assert "No journal entry" in capsys.readouterr().out
    assert _untouched(conn) == before and _insights(conn) == notes


def test_the_journal_entry_is_plain_words(lab, dev_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    (rep,), _run = _measure(conn, dev_data, tmp_path, monkeypatch)
    before = _untouched(conn)
    with conn:
        entry = exp.journal(conn, rep)
    row = conn.execute("SELECT * FROM insights WHERE id = ?", (entry,)).fetchone()
    assert row["kind"] == "observation" and row["method_id"] == "M0001"
    assert row["title"].endswith("what its own picks did, apart from the money it parks")
    for text in (row["title"], row["body"]):
        for banned in ("M0001", "-PICKS", "-FULL", "-PARK", "`", "DSR", "MAR", "exposure"):
            assert banned not in text, banned
    assert "count of tries did not move" in row["body"]
    assert _untouched(conn) == before


def test_the_help_strings_still_format(capsys):
    """argparse %-interpolates every help= string; a bare % there kills `lab --help`."""
    with pytest.raises(SystemExit) as e:
        cli.main(["lab", "exposure", "--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "--only" in out and "--no-journal" in out and "--csv" in out
    with pytest.raises(SystemExit):
        cli.main(["lab", "--help"])
    assert "exposure" in capsys.readouterr().out
