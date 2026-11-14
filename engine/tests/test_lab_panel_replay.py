"""``lab panel-replay`` (lab/panel_replay.py): recorded stock-signal arms become pick-set panels.

Driven against a scratch lab database with real allocators -- a toy whose params choose its
behaviour, a market-aware toy that declares Market.series, and F4's ``FACTOR`` -- over a synthetic
40-member market from 2005, through phase 1's real ``panel.build_frame`` and ``panel.measure``.
Stores are manifest-only tmp directories with ``research.load_store`` answered from memory, the
seam ``test_lab_panel_cli.py`` uses. What is asserted is what the lab holds afterwards: which rows,
of which kind, under which ids, the skip report, and the frozen records byte for byte.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from labkit import LAB_PRICE_FINGERPRINT, SMOKE_T13W, smoke_history

from seer_engine import cli, dates, research
from seer_engine.backtest.dev import DEV_END, Candidate
from seer_engine.backtest.market import Market, Membership
from seer_engine.lab import panel, panel_replay, store
from seer_engine.lab.method import Method, config_digest
from seer_engine.lab.seed import seed
from seer_engine.research import ResearchData
from seer_engine.sim.book import equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.f_factor import FACTOR, FactorParams

SV = research.SURVIVORSHIP_PURPOSE
# 2005, not 2007: F4's screen (and FACTOR) needs 253 bars, so a 2007 start leaves the pre-2009
# era exactly panel.MIN_ERA_MONTHS (12) months; 2005 gives about 36 (reconciled).
FIRST = date(2005, 1, 3)
STOCKS = tuple(f"S{k:02d}" for k in range(40))
ADDED = date(2026, 11, 13)
STAMP = "2026-11-13T00:00:00+00:00"


@pytest.fixture(autouse=True)
def _clean_gate_cache():
    store._GATE_CACHE.clear()
    yield
    store._GATE_CACHE.clear()


# ---- allocators whose params say what they do -------------------------------------------------


@dataclass(frozen=True)
class Rule:
    kind: str  # top | keep | cash | boom | etf
    n: int = 6
    tag: str = ""  # moves the config digest and nothing else: two rules differing here are one book


class Toy:
    """Ranks the members with a bar on d by that close, highest first; ``Rule.kind`` decides the rest.

    top: the first n. keep: what is held first, then the ranking, n in all (a keep band).
    cash: nothing (a switch that is always off). boom: raises. etf: SPY (a fixed holding) plus the
    first n.
    """

    id = "TOY"

    def lookback(self, params: Any) -> int:
        return 1

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ("SPY",) if params.kind == "etf" else ()

    def holds(self, params: Any) -> tuple[str, ...]:
        return ("SPY",) if params.kind == "etf" else ()

    def uses_members(self, params: Any) -> bool:
        return True

    def prepare(self, history):
        return dict(history)

    def targets(self, history, members, data_date, held, params):
        cut = {s: h.upto(data_date) for s, h in history.items()}
        return self.targets_prepared(cut, members, data_date, held, params)

    def targets_prepared(self, prepared, members, data_date, held, params):
        if params.kind == "boom":
            raise RuntimeError("toy allocator failure")
        if params.kind == "cash":
            return ()

        def close(s):
            h = prepared.get(s)
            i = None if h is None else h.index_of(data_date)
            return None if i is None else float(h.close[i])

        ranked = sorted((s for s in members if close(s) is not None), key=lambda s: (-close(s), s))
        if params.kind == "keep":
            kept = [s for s in sorted(held) if close(s) is not None]
            ranked = kept + [s for s in ranked if s not in kept]
        names = ranked[: params.n]
        if params.kind == "etf":
            names = ["SPY", *names]
        if not names:
            return ()
        w = equal_weight(len(names))
        out = (target_from_close(s, close(s), w) for s in names)
        return tuple(t for t in out if t is not None)


class SeriesToy(Toy):
    """The same ranking, declared as reading Market.series: a store without series cannot feed it."""

    id = "TOYSERIES"
    market_fields = ("series",)

    def prepare_market(self, market):
        return dict(market.history)


TOY = Toy()
SERIES_TOY = SeriesToy()


def _arm(mid: str, suffix: str, allocator, params, rationale: str = "toy arm") -> Candidate:
    return Candidate(id=f"{mid}-{suffix}", family=mid, rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


def _method(mid: str, name: str, family: str, *arms: Candidate) -> Method:
    return Method(id=mid, name=name, family=family, source_kind="knowledge", source_ref="",
                  hypothesis=f"{name} hypothesis", expected_failure=f"{name} failure",
                  candidates=tuple(arms))


TOYS = _method(
    "M9001", "Toy picks", "stock-toy",
    _arm("M9001", "TOP", TOY, Rule("top")),
    _arm("M9001", "TOPB", TOY, Rule("top", tag="b")),
    _arm("M9001", "KEEP", TOY, Rule("keep")),
    _arm("M9001", "CASH", TOY, Rule("cash")),
    _arm("M9001", "BOOM", TOY, Rule("boom")),
    _arm("M9001", "ETF", TOY, Rule("etf")),
)
MOMENTUM = _method(
    "M9002", "Momentum", "stock-momentum",
    _arm("M9002", "MOM", FACTOR, FactorParams(rank="momentum", top=10, trend=None),
         "twelve-minus-one momentum, ten names"),
    _arm("M9002", "SER", SERIES_TOY, Rule("top", tag="series")),
)
ROTATION = _method("M9003", "Rotation", "etf-rotation", _arm("M9003", "ROT", TOY, Rule("top", tag="rot")))
DRIFT = _method("M9005", "Drifted", "stock-drift", _arm("M9005", "A", TOY, Rule("top", tag="drift")))

RECORDABLE = ("M9001-TOP", "M9001-TOPB", "M9001-KEEP", "M9001-ETF", "M9002-MOM", "M9002-SER")


# ---- a scratch lab ----------------------------------------------------------------------------


@dataclass
class Lab:
    conn: Any
    path: Path
    files: dict[str, tuple[Method, Path]]

    def load(self, method_id: str) -> tuple[Method, Path]:
        if method_id not in self.files:
            raise ImportError(f"No module named 'seer_engine.lab.methods.{method_id.lower()}_broken'")
        return self.files[method_id]


def _trial(method_id: str, candidate_id: str, digest: str) -> store.TrialRow:
    return store.TrialRow(
        method_id=method_id, candidate_id=candidate_id, config_digest=digest, config_text="t",
        rules_id="r", allocator_id="a", window="dev", start="2008-01-02", end="2015-10-16",
        store_fingerprint="fp", git_sha="abc", run_at=STAMP,
        total_return=1.0, cagr=0.1, max_drawdown=0.3, profit_factor=1.2, trades=200,
        sharpe=0.5, exposure=0.9, turnover=1.0, worst_year=2008, worst_year_return=-0.2,
        spy_tr_return=0.5, spy_tr_cagr=0.07, mar=0.3, failed="", eligible=False,
        dsr=0.5, n_trials_at_run=5, curve_json="[]",
    )


def _make_lab(root: Path) -> Lab:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "lab.sqlite"
    conn = store.connect(path)
    seed(conn)
    files: dict[str, tuple[Method, Path]] = {}
    for m in (TOYS, MOMENTUM, ROTATION, DRIFT):
        f = root / f"{m.id.lower()}_test.py"
        f.write_text(f"# {m.id} {m.name}\n", encoding="utf-8")
        files[m.id] = (m, f)
    with conn:
        for mid, name, family in (("M9001", "Toy picks", "stock-toy"),
                                  ("M9002", "Momentum", "stock-momentum"),
                                  ("M9003", "Rotation", "etf-rotation"),
                                  ("M9004", "Broken", "stock-broken"),
                                  ("M9005", "Drifted", "stock-drift")):
            store.add_method(conn, id=mid, name=name, family=family, source_kind="knowledge",
                             hypothesis="h")
        trials = [_trial(m.id, c.id, config_digest(c))
                  for m in (TOYS, MOMENTUM, ROTATION) for c in m.all_candidates()]
        trials += [_trial("M9004", "M9004-A", "d-broken"),
                   _trial("M9005", "M9005-A", "stale-digest"),
                   _trial("M9001", "M9001-GONE", "d-gone")]
        store.insert_trials(conn, trials)
    return Lab(conn, path, files)


@pytest.fixture()
def lab(tmp_path):
    made = _make_lab(tmp_path / "lab")
    yield made
    made.conn.close()


# ---- stores -----------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def market() -> Market:
    days = dates.sessions(FIRST, DEV_END)
    history = {s: smoke_history(s, k, days) for k, s in enumerate(("SPY", *STOCKS))}
    membership = Membership(intervals=tuple((s, days[0], None) for s in STOCKS))
    return Market(history=history, membership=membership, fx=((days[0], Decimal("2000")),))


def _data(market: Market, fingerprint: str, purpose: str | None = None) -> ResearchData:
    # The dev store carries the seeded benchmark's prices: D10 (``hardgate.pin_dev_store``) refuses
    # any other on a seeded lab, as it does in ``test_lab_panel_cli.py``.
    return ResearchData(market=market, dividends={}, spy_dividends=(), fingerprint=fingerprint,
                        manifest={} if purpose is None else {"purpose": purpose},
                        price_fingerprint=LAB_PRICE_FINGERPRINT if purpose is None else fingerprint,
                        purpose=purpose)


@dataclass
class Stores:
    dev: Path
    sv: Path
    loads: list[str]


def _stores(root: Path, monkeypatch, market: Market, *, sv_series: bool = True) -> Stores:
    d, s = root / "dev-store", root / "sv-store"
    d.mkdir(parents=True, exist_ok=True)
    s.mkdir(parents=True, exist_ok=True)
    (d / research.MANIFEST_FILE).write_text(json.dumps({"fingerprint": "smoke-dev"}))
    (s / research.MANIFEST_FILE).write_text(json.dumps({"fingerprint": "smoke-sv", "purpose": SV}))
    with_series = market.with_series(SMOKE_T13W)
    by_dir = {d: _data(with_series, "smoke-dev"),
              s: _data(with_series if sv_series else market, "smoke-sv", SV)}
    loads: list[str] = []

    def load_store(store_dir, **kw):
        loads.append(Path(store_dir).name)
        return by_dir[Path(store_dir)]

    monkeypatch.setattr(research, "load_store", load_store)
    return Stores(d, s, loads)


@pytest.fixture()
def stores(tmp_path, monkeypatch, market) -> Stores:
    return _stores(tmp_path / "stores", monkeypatch, market)


def _replay(lab: Lab, stores: Stores, **kw) -> panel_replay.Report:
    return panel_replay.run(lab.conn, stores.dev, stores.sv, git_sha="abc", load=lab.load,
                            now=lambda: STAMP, **kw)


def _frozen(conn) -> tuple[str, str]:
    trials = repr([tuple(r) for r in conn.execute("SELECT * FROM trials ORDER BY n")])
    shas = repr([tuple(r) for r in conn.execute("SELECT id, source_sha FROM methods ORDER BY id")])
    return hashlib.sha256(trials.encode()).hexdigest(), hashlib.sha256(shas.encode()).hexdigest()


def _whole(conn, cid: str) -> set[tuple[str, str]]:
    """(store role, picks hash) of the arm's whole-window rows."""
    return {(str(r["store_role"]), str(r["picks_hash"]))
            for r in store.panel_results(conn, signal_id=cid) if str(r["era"]) == panel.ERAS[0]}


def _panels(conn) -> list[tuple]:
    return sorted((str(r["signal_id"]), str(r["store_role"]), str(r["era"]), int(r["months"]),
                   str(r["picks_hash"]), round(float(r["fm_slope"]), 12))
                  for r in store.panel_results(conn))


def _lab_cli(lab: Lab, stores: Stores, *argv: str) -> int:
    return cli.main(["lab", "--db", str(lab.path), "panel-replay", *argv,
                     "--store", str(stores.dev), "--sv-store", str(stores.sv)])


# ---- recording --------------------------------------------------------------------------------


def test_every_recorded_stock_arm_gets_one_replay_panel_on_both_stores(lab, stores):
    rep = _replay(lab, stores)
    assert rep.selected == 11 and rep.already == 0 and rep.attempted == 11
    assert rep.recorded == RECORDABLE
    rows = {str(r["id"]): r for r in store.panel_signals(lab.conn) if str(r["kind"]) == "replay"}
    assert set(rows) == set(RECORDABLE)
    for cid, r in rows.items():
        method, path = lab.files[cid.split("-")[0]]
        assert r["method_id"] == method.id
        assert r["source_sha"] == hashlib.sha256(path.read_bytes()).hexdigest()
        roles = {(str(x["store_role"]), str(x["store_fingerprint"]))
                 for x in store.panel_results(lab.conn, signal_id=cid)}
        assert roles == {("dev", "smoke-dev"), ("survivorship", "smoke-sv")}
        assert {x[0] for x in _whole(lab.conn, cid)} == {"dev", "survivorship"}
    assert rows["M9001-TOP"]["name"] == "Toy picks"  # the method's own name (Decisions)
    assert rows["M9001-TOP"]["hypothesis"] == "Toy picks hypothesis"
    assert rows["M9002-MOM"]["family"] == "stock-momentum"
    assert "M9003-ROT" not in rows  # an etf-* method is outside the default family
    assert stores.loads == ["dev-store", "sv-store"]  # each store once, dev first


def test_trials_and_recorded_method_shas_are_byte_identical_after_a_replay(lab, stores):
    before = _frozen(lab.conn)
    _replay(lab, stores)
    assert _frozen(lab.conn) == before


def test_two_arms_that_pick_the_same_names_record_the_same_pick_set(lab, stores):
    _replay(lab, stores)
    assert _whole(lab.conn, "M9001-TOP") == _whole(lab.conn, "M9001-TOPB")
    assert _whole(lab.conn, "M9001-TOP") != _whole(lab.conn, "M9002-MOM")


def test_a_fixed_holding_is_not_a_pick(lab, stores):
    _replay(lab, stores)
    # SPY plus the same six names as TOP: with the fixed holding dropped, the pick set is TOP's.
    assert _whole(lab.conn, "M9001-ETF") == _whole(lab.conn, "M9001-TOP")


def test_the_scorer_drops_fixed_holdings_and_names_outside_the_pool(market):
    d = date(2015, 9, 30)
    prepared = TOY.prepare(market.history)
    targets = TOY.targets_prepared(prepared, market.membership.members_on(d), d, frozenset(), Rule("etf"))
    named = [t.symbol for t in targets if t.symbol != "SPY"]
    pool = frozenset(STOCKS) - {named[0]}
    scorer = panel_replay.PickScorer(TOY, prepared, Rule("etf"))
    assert scorer(market, pool, d) == {s: 1.0 for s in named[1:]}


def test_an_arm_that_reads_its_holdings_is_counted_not_special_cased(lab, stores):
    rep = _replay(lab, stores)
    assert "M9001-KEEP" in rep.recorded
    assert rep.held_sensitive == ("M9001-KEEP",)


# ---- skipping ---------------------------------------------------------------------------------


def test_one_failing_allocator_does_not_stop_the_sweep(lab, stores):
    rep = _replay(lab, stores)
    why = {s.candidate_id: s.category for s in rep.skipped}
    assert why["M9001-BOOM"] == panel_replay.RAISED
    assert why["M9001-CASH"] == panel_replay.TOO_FEW
    assert "M9001-ETF" in rep.recorded  # after BOOM in trial order, same allocator object


def test_unimportable_vanished_and_drifted_arms_are_skipped_before_any_store_loads(lab, stores):
    rep = _replay(lab, stores, method_ids=["M9004", "M9005"])
    why = {s.candidate_id: s.category for s in rep.skipped}
    assert why == {"M9004-A": panel_replay.NO_IMPORT, "M9005-A": panel_replay.DRIFTED}
    assert stores.loads == []
    full = _replay(lab, stores)
    assert {s.candidate_id: s.category for s in full.skipped}["M9001-GONE"] == panel_replay.NOT_IN_FILE


def test_an_arm_the_survivorship_store_cannot_feed_is_recorded_on_neither_store(lab, tmp_path, monkeypatch, market):
    stores = _stores(tmp_path / "no-series", monkeypatch, market, sv_series=False)
    rep = _replay(lab, stores)
    skip = {s.candidate_id: s for s in rep.skipped}["M9002-SER"]
    assert skip.category == panel_replay.NO_DATA and "survivorship" in skip.detail
    assert store.panel_results(lab.conn, signal_id="M9002-SER") == []
    assert "M9002-SER" not in {str(r["id"]) for r in store.panel_signals(lab.conn)}
    assert "M9002-MOM" in rep.recorded


# ---- resuming ---------------------------------------------------------------------------------


def test_limit_takes_the_unfinished_arms_in_trial_order(lab, stores):
    first = _replay(lab, stores, limit=2)
    assert first.recorded == ("M9001-TOP", "M9001-TOPB")
    second = _replay(lab, stores, limit=2)
    assert second.already == 2
    assert second.recorded == ("M9001-KEEP",)
    assert [s.candidate_id for s in second.skipped] == ["M9001-CASH"]


def test_a_finished_selection_measures_nothing_and_loads_no_store(lab, stores):
    first = _replay(lab, stores, method_ids=["M9002"])
    assert first.recorded == ("M9002-MOM", "M9002-SER")
    loads = list(stores.loads)
    again = _replay(lab, stores, method_ids=["M9002"])
    assert (again.attempted, again.already, again.recorded) == (0, 2, ())
    assert stores.loads == loads
    assert len(store.panel_results(lab.conn, signal_id="M9002-MOM")) == len(
        store.panel_results(lab.conn, signal_id="M9002-SER"))


def test_two_jobs_record_the_same_panels_as_one(tmp_path, stores):
    one, two = _make_lab(tmp_path / "one"), _make_lab(tmp_path / "two")
    try:
        _replay(one, stores, jobs=1)
        _replay(two, stores, jobs=2)
        assert _panels(one.conn) == _panels(two.conn)
        assert _panels(one.conn)
    finally:
        one.conn.close()
        two.conn.close()


# ---- the command ------------------------------------------------------------------------------


def test_the_command_replays_through_the_real_handler(lab, stores, monkeypatch, capsys):
    monkeypatch.setattr(panel_replay, "module_loader", lambda: lab.load)
    assert _lab_cli(lab, stores, "M9002") == 0
    out = capsys.readouterr().out
    assert "recorded 2 replay panel(s), one transaction each" in out
    m = re.search(r"Lab N \(dev trials\): (\d+) before, (\d+) after; luck gate N = (\d+) before, (\d+) after", out)
    assert m is not None and m.group(1) == m.group(2) and m.group(3) == m.group(4)
    assert {str(r["id"]) for r in store.panel_signals(lab.conn)} >= {"M9002-MOM", "M9002-SER"}


def test_a_method_outside_the_family_exits_2_and_loads_nothing(lab, stores, monkeypatch):
    monkeypatch.setattr(panel_replay, "module_loader", lambda: lab.load)
    assert _lab_cli(lab, stores, "M9003") == 2
    assert stores.loads == []
    assert store.panel_signals(lab.conn) == []


def test_a_run_that_can_replay_nothing_exits_1(lab, stores, monkeypatch):
    monkeypatch.setattr(panel_replay, "module_loader", lambda: lab.load)
    assert _lab_cli(lab, stores, "M9004") == 1
    assert stores.loads == []


def test_jobs_above_two_is_refused_by_the_parser(lab, stores):
    with pytest.raises(SystemExit) as e:
        _lab_cli(lab, stores, "--jobs", "3")
    assert e.value.code == 2


def test_the_help_formats_and_names_the_default_family(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["lab", "panel-replay", "--help"])
    assert e.value.code == 0
    assert "stock-%" in capsys.readouterr().out
