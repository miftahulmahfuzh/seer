"""Phase 6: ``Market.fundamentals``, the panel load in ``backtest.io``, and ``prepare_market``.

The DB tests use the ``pg`` fixture (a throwaway schema with every migration applied), so they
skip when PG_TEST_URL is unset. The dispatch tests are pure and always run.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import FrozenInstanceError, replace as dc_replace
from datetime import date
from decimal import Decimal
from typing import Any

import pandas as pd
import pytest
from stratkit import hist, sawtooth

from seer_engine import dates, db, fx as fx_module, research
from seer_engine.backtest import dev, io as bio
from seer_engine.backtest.market import EMPTY_FUNDAMENTALS, Market, Membership
from seer_engine.fundamentals import FACT_COLUMNS, Fact, FundamentalPanel as Panel
from seer_engine.prices import to_decimal
from seer_engine.sim import q
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD
from seer_engine.strategies.allocator import Allocator, MarketAware, prepare_for
from seer_engine.strategies.base import History

D1, D2, D3 = date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30)
Y2020 = date(2020, 1, 2)
DAYS = [D1, D2, D3]

BARS = [
    ("AAPL", D1, "100.1", "101.2", "99.5", "100.9", 1_000_000),
    ("AAPL", D2, "101", "102", "100", "101.5", 1_100_000),
    ("SPY", D1, "500", "505", "499", "501.1", 50_000_000),
    ("SPY", D2, "501", "506", "500", "502.2", 51_000_000),
]
UNIVERSE = [("AAPL", "SP500", Y2020, None), ("ATVI", "SP500", Y2020, D2)]
FX = [(D1, "16000"), (D2, "16100.5")]

# fundamental_facts is keyed by CIK (C1); the symbol arrives from the ticker_cik join.
CIK_AAPL, CIK_ATVI, CIK_GOOG = 320193, 718877, 1652044

# ATVI has facts and no bars: the Gap A case. AAPL has both. The two Assets rows for the same
# period_end differ only by accn and filed -- a restatement, which must survive the load.
# An instantaneous fact is stored period_start = period_end (C2) and must come back as None.
FACTS = [
    (CIK_AAPL, "us-gaap", "Assets", "USD", date(2015, 12, 31), date(2015, 12, 31),
     "352000000000", "0000320193-16-000001", 2016, "Q1", "10-Q", date(2016, 2, 1)),
    (CIK_AAPL, "us-gaap", "Revenues", "USD", date(2015, 10, 1), date(2015, 12, 31),
     "75872000000", "0000320193-16-000001", 2016, "Q1", "10-Q", date(2016, 2, 1)),
    (CIK_ATVI, "us-gaap", "Assets", "USD", date(2015, 12, 31), date(2015, 12, 31),
     "15274000000", "0000718877-16-000010", 2015, "FY", "10-K", date(2016, 2, 29)),
    (CIK_ATVI, "us-gaap", "Assets", "USD", date(2015, 12, 31), date(2015, 12, 31),
     "15300000000", "0000718877-17-000011", 2016, "FY", "10-K", date(2017, 3, 1)),
]
# One CIK, two symbols -- the share-class fan-out the join is expected to produce.
MAP = [
    ("AAPL", CIK_AAPL, date(2015, 1, 2), None, "Apple Inc.", "current", None),
    ("ATVI", CIK_ATVI, date(2015, 1, 2), date(2023, 10, 13), "Activision Blizzard, Inc.",
     "current", None),
    ("GOOG", CIK_GOOG, date(2015, 10, 2), None, "Alphabet Inc.", "current", None),
    ("GOOGL", CIK_GOOG, date(2015, 10, 2), None, "Alphabet Inc.", "current", None),
]
PANEL_ROWS = len(FACTS)  # no share class among FACTS' CIKs, so the join is 1:1 here


def market(**kwargs: Any) -> Market:
    base: dict[str, Any] = dict(
        history={"SPY": hist("SPY", sawtooth(len(DAYS), 200.0, 2.0, 1.5), days=DAYS)},
        membership=Membership((("AAA", Y2020, None),)),
        fx=((D1, Decimal("16000")),),
    )
    base.update(kwargs)
    return Market(**base)


def panel_facts(panel: Panel) -> dict[str, tuple[Fact, ...]]:
    """``{symbol: facts}`` -- how two panels are compared.

    ``FundamentalPanel`` is ``eq=False`` (phase 5 owns that type and this phase does not touch
    it), so ``==`` on two panels is identity. ``Fact`` is a plain frozen dataclass, so comparing
    the fact tuples is the value equality the exit criteria mean by "the same panel".
    """
    return {s: panel.get(s).facts for s in panel.names()}


def a_panel() -> Panel:
    return Panel.from_facts(
        (
            Fact(
                symbol="ATVI",
                taxonomy="us-gaap",
                tag="Assets",
                unit="USD",
                period_start=None,
                period_end=date(2015, 12, 31),
                val=15_274_000_000.0,
                accn="0000718877-16-000010",
                fy=2015,
                fp="FY",
                form="10-K",
                filed=date(2016, 2, 29),
            ),
        )
    )


# ---- the field ------------------------------------------------------------------------------


def test_market_defaults_to_the_empty_panel():
    m = market()
    assert m.fundamentals is EMPTY_FUNDAMENTALS
    assert isinstance(m.fundamentals, Panel)


def test_market_still_takes_three_positional_fields():
    """Every shipped construction site passes history, membership and fx and nothing else."""
    m = Market({"SPY": hist("SPY", sawtooth(3, 200.0, 2.0, 1.5), days=DAYS)}, Membership(()), ())
    assert m.fundamentals is EMPTY_FUNDAMENTALS


def test_market_stays_frozen():
    m = market()
    with pytest.raises(FrozenInstanceError):
        m.fundamentals = a_panel()  # type: ignore[misc]


def test_market_rejects_a_non_panel():
    with pytest.raises(TypeError, match="fundamentals must be a Panel"):
        market(fundamentals={"ATVI": []})


def test_with_fundamentals_carries_every_other_field():
    m = market()
    panel = a_panel()
    n = m.with_fundamentals(panel)
    assert n is not m
    assert m.fundamentals is EMPTY_FUNDAMENTALS  # the original is untouched
    assert n.fundamentals is panel
    assert n.history is m.history and n.membership is m.membership and n.fx == m.fx
    assert n.usd_idr_on(D1) == m.usd_idr_on(D1)  # the init=False caches were rebuilt
    assert n.last_bar_date("SPY") == m.last_bar_date("SPY")


def test_a_panel_symbol_needs_no_bars():
    """Gap A independence: ATVI has facts and no bars, and the Market accepts it."""
    m = market(fundamentals=a_panel())
    assert "ATVI" not in m.history
    assert m.last_bar_date("ATVI") is None
    assert m.fundamentals is not EMPTY_FUNDAMENTALS


# ---- the dispatch ----------------------------------------------------------------------------


class BarsOnly:
    """An allocator of the shipped shape: ``prepare`` only, no ``prepare_market``."""

    id = "FAKE_BARS_ONLY"

    def __init__(self) -> None:
        self.prepare_calls = 0

    def lookback(self, params: Any) -> int:
        return 1

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ("SPY",)

    def holds(self, params: Any) -> tuple[str, ...]:
        return ("SPY",)

    def uses_members(self, params: Any) -> bool:
        return False

    def targets(self, history: Mapping[str, History], members: AbstractSet[str],
                data_date: date, held: frozenset[str], params: Any) -> tuple:
        return ()

    def prepare(self, history: Mapping[str, History]) -> Any:
        self.prepare_calls += 1
        return {"history": dict(history)}

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple:
        return ()


class PanelAware(BarsOnly):
    """The shape phase 7's allocator will have: ``prepare`` plus ``prepare_market``."""

    id = "FAKE_PANEL_AWARE"

    def __init__(self) -> None:
        super().__init__()
        self.prepare_market_calls = 0
        self.seen_panel: Any = None

    def prepare_market(self, m: Market) -> Any:
        self.prepare_market_calls += 1
        self.seen_panel = m.fundamentals
        return {"history": dict(m.history), "panel": m.fundamentals}


def test_adding_the_hook_does_not_change_the_allocator_check():
    """The whole point of a sibling protocol: Allocator's member set is untouched.

    Asserted twice over, deliberately. The first two lines are the CONSEQUENCE and hold on every
    Python: ``BarsOnly`` has no ``prepare_market``, and a ``runtime_checkable`` Protocol's
    ``isinstance`` is exactly "has every member", so if ``prepare_market`` had been added to
    ``Allocator`` rather than to the sibling protocol, ``BarsOnly`` would stop being an
    ``Allocator`` and the eight production sites that rely on structural typing would break.

    The third line states it directly on the member set, which is sharper but is only available
    where ``__protocol_attrs__`` is: that is a CPython internal added in 3.12, and CI runs 3.11
    (``engine-ci.yml``). It is therefore read through ``getattr`` and vacuously true on 3.11,
    where the two lines above carry the test. ``pytest.skip`` is NOT an option here -- the CI
    step greps for ``^SKIPPED`` and fails the job on any skip.
    """
    assert isinstance(BarsOnly(), Allocator)
    assert isinstance(PanelAware(), Allocator)
    assert "prepare_market" not in getattr(Allocator, "__protocol_attrs__", frozenset())


def test_market_aware_is_presence_only():
    assert not isinstance(BarsOnly(), MarketAware)
    assert isinstance(PanelAware(), MarketAware)

    class DataAttribute(BarsOnly):
        prepare_market = 5  # not callable, but runtime_checkable cannot tell

    assert isinstance(DataAttribute(), MarketAware)


def test_prepare_for_falls_back_to_prepare():
    a = BarsOnly()
    m = market(fundamentals=a_panel())
    prepared = prepare_for(a, m)
    assert a.prepare_calls == 1
    assert prepared == {"history": dict(m.history)}


def test_prepare_for_uses_prepare_market_and_passes_the_whole_market():
    a = PanelAware()
    panel = a_panel()
    m = market(fundamentals=panel)
    prepared = prepare_for(a, m)
    assert a.prepare_market_calls == 1 and a.prepare_calls == 0
    assert a.seen_panel is panel
    assert prepared["panel"] is panel


def test_prepare_for_rejects_a_non_callable_hook():
    class Broken(BarsOnly):
        prepare_market = 5

    with pytest.raises(TypeError, match="prepare_market must be callable"):
        prepare_for(Broken(), market())


# ---- the dev/lab runner ------------------------------------------------------------------------


DEV_DAYS = dates.sessions(date(2015, 6, 1), dev.DEV_END)
DEV_FX = ((date(2015, 1, 2), Decimal("12500")),)


class DevHoldOne(BarsOnly):
    """Weight 1 in SPY whenever SPY has a bar on data_date; enough for a real dev run."""

    id = "FAKE_DEV_HOLD"

    def _targets(self, history: Mapping[str, History], data_date: date) -> tuple:
        h = history.get("SPY")
        if h is None:
            return ()
        i = h.index_of(data_date)
        if i is None:
            return ()
        return (Target("SPY", Decimal("1"), q(to_decimal(float(h.close[i])))),)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ("SPY",)

    def targets(self, history, members, data_date, held, params) -> tuple:
        return self._targets(history, data_date)

    def targets_prepared(self, prepared, members, data_date, held, params) -> tuple:
        return self._targets(prepared["history"], data_date)


class DevPanelHoldOne(DevHoldOne):
    id = "FAKE_DEV_PANEL_HOLD"

    def __init__(self) -> None:
        super().__init__()
        self.prepare_market_calls = 0
        self.seen_panel: Any = None

    def prepare_market(self, m: Market) -> Any:
        self.prepare_market_calls += 1
        self.seen_panel = m.fundamentals
        return {"history": dict(m.history), "panel": m.fundamentals}


def dev_market(*, days=None, fx=DEV_FX, fundamentals=None) -> Market:
    d = DEV_DAYS if days is None else days
    kwargs: dict[str, Any] = dict(
        history={"SPY": hist("SPY", sawtooth(len(d), 200.0, 2.0, 1.5), days=d)},
        membership=Membership((("SPY", Y2020, None),)),
        fx=fx,
    )
    if fundamentals is not None:
        kwargs["fundamentals"] = fundamentals
    return Market(**kwargs)


def dev_candidate(allocator: Any) -> dev.Candidate:
    c = dev.Candidate(
        id="C-PHASE6",
        family="F1",
        rules=MONTHLY_HOLD,
        allocator=allocator,
        params=None,
        rationale="phase 6 dispatch test",
        added=date(2026, 10, 5),
        owner_inputs=(),
    )
    return dc_replace(c, owner_inputs=dev.candidate_owner_inputs(c))


def test_run_registry_keeps_the_bars_only_path_for_a_plain_allocator():
    a = DevHoldOne()
    m = dev_market(fundamentals=a_panel())
    rows = dev.run_registry(m, {}, (), (dev_candidate(a),))
    assert len(rows) == 1
    assert a.prepare_calls == 1
    assert not isinstance(a, MarketAware)


def test_run_registry_hands_a_market_aware_allocator_the_whole_market():
    a = DevPanelHoldOne()
    panel = a_panel()
    m = dev_market(fundamentals=panel)
    rows = dev.run_registry(m, {}, (), (dev_candidate(a),))
    assert len(rows) == 1
    assert a.prepare_market_calls == 1 and a.prepare_calls == 0
    assert a.seen_panel is panel


def test_the_two_paths_give_the_same_result():
    """prepare_market must not change the numbers when the extra data is unused."""
    panel = a_panel()
    plain = dev.run_registry(dev_market(fundamentals=panel), {}, (), (dev_candidate(DevHoldOne()),))
    aware = dev.run_registry(
        dev_market(fundamentals=panel), {}, (), (dev_candidate(DevPanelHoldOne()),)
    )
    assert plain[0].stats.metrics == aware[0].stats.metrics
    assert plain[0].start == aware[0].start and plain[0].end == aware[0].end


def test_the_fx_rebuild_keeps_the_panel():
    """dev._run rebuilds the Market for a pre-FX_START window; replace() carries the panel."""
    panel = a_panel()
    m = market(fundamentals=panel)
    rebuilt = dc_replace(m, fx=((date(1999, 1, 4), Decimal("8002")),))
    assert rebuilt.fundamentals is panel
    assert rebuilt.history is m.history and rebuilt.membership is m.membership


# ---- the loader --------------------------------------------------------------------------------


def seed_bars(conn):
    from seer_engine import bars

    with db.transaction(conn, False):
        bars.upsert_bars(conn, [bars.make_bar(*r) for r in BARS])


def seed_universe(conn):
    with db.transaction(conn, False):
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
                "VALUES (%s, %s, %s, %s, %s)",
                [(s, i, a, b, s) for s, i, a, b in UNIVERSE],
            )


def seed_fx(conn):
    with db.transaction(conn, False):
        fx_module.upsert_fx(conn, FX)


def seed_facts(conn, rows=FACTS):
    with db.transaction(conn, False):
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO fundamental_facts "
                "(cik, taxonomy, tag, unit, period_start, period_end, val, accn, fy, fp, form, filed) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                rows,
            )


def seed_map(conn, rows=MAP):
    """``ticker_cik`` -- phase 4 writes it from phase 1's CSV; the panel load joins it."""
    with db.transaction(conn, False):
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO ticker_cik "
                "(symbol, cik, start_date, end_date, company, source, note) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                rows,
            )


def seed_panel(conn, rows=FACTS):
    """Both halves of the panel: facts and the dated bridge that names them."""
    seed_facts(conn, rows)
    seed_map(conn)


@pytest.fixture
def seeded(pg):
    seed_bars(pg)
    seed_universe(pg)
    seed_fx(pg)
    return pg


def test_load_market_without_any_fundamentals_rows(seeded, tmp_path):
    """The live database today: the table exists (migration applied) and holds nothing."""
    market_, rows = bio.load_market(seeded, cache_dir=tmp_path)
    assert rows == len(BARS)
    assert market_.fundamentals is EMPTY_FUNDAMENTALS
    assert list(tmp_path.glob("fundamentals-*.pkl")) == []


@pytest.mark.parametrize("missing", ["fundamental_facts", "ticker_cik"])
def test_load_market_without_the_tables_at_all(seeded, tmp_path, missing):
    """A database that has not run 005_fundamentals.sql still backs a backtest.

    Either table missing is enough: the panel load joins both, and ``to_regclass`` is used
    rather than catching ``UndefinedTable``, because that error would abort ``load_market``'s
    read-only transaction with no savepoint to recover from.
    """
    with db.transaction(seeded, False):
        seeded.execute(f"DROP TABLE {missing}")
    assert bio.facts_fingerprint(seeded) == (0, None)
    seeded.rollback()  # the fingerprint query opened an implicit transaction; load_market wants none
    market_, rows = bio.load_market(seeded, cache_dir=tmp_path)
    assert rows == len(BARS)
    assert market_.fundamentals is EMPTY_FUNDAMENTALS


def test_facts_with_no_ticker_cik_row_are_dropped_not_guessed(seeded, tmp_path):
    """A fact whose filed date falls in no interval for its CIK has no symbol, so it is dropped.

    This is the mechanism that keeps a recycled ticker's two filers apart, and it is why an
    incomplete ticker_cik shrinks the panel rather than corrupting it.
    """
    seed_facts(seeded)
    seed_map(seeded, [("AAPL", CIK_AAPL, date(2015, 1, 2), None, "Apple Inc.", "current", None)])
    rows, _ = bio.facts_fingerprint(seeded)
    assert rows == 2  # AAPL's two facts; ATVI's two have no interval and vanish
    panel = bio.load_panel(seeded, cache_dir=tmp_path)
    assert panel.names() == ("AAPL",)


def test_a_share_class_pair_fans_one_fact_out_to_both_symbols(seeded, tmp_path):
    """One CIK, two tickers (GOOG/GOOGL). The join is 1:2 and the fingerprint counts the join."""
    seed_facts(
        seeded,
        [(CIK_GOOG, "us-gaap", "Assets", "USD", date(2015, 12, 31), date(2015, 12, 31),
          "147461000000", "0001652044-16-000012", 2015, "FY", "10-K", date(2016, 2, 11))],
    )
    seed_map(seeded)
    rows, _ = bio.facts_fingerprint(seeded)
    assert rows == 2  # one stored fact, two panel rows
    panel = bio.load_panel(seeded, cache_dir=tmp_path)
    assert panel.names() == ("GOOG", "GOOGL")


def test_re_vendoring_ticker_cik_invalidates_the_pickle(seeded, tmp_path):
    """The cache key counts over the join, so a map change busts it even with no new fact."""
    seed_panel(seeded)
    bio.load_market(seeded, cache_dir=tmp_path)
    before = sorted(p.name for p in tmp_path.glob("fundamentals-*.pkl"))
    seed_map(seeded, [("AAPL2", CIK_AAPL, date(2015, 1, 2), None, "Apple Inc.", "manual", None)])
    bio.load_market(seeded, cache_dir=tmp_path)
    after = sorted(p.name for p in tmp_path.glob("fundamentals-*.pkl"))
    assert after != before and len(after) == 1


def test_facts_fingerprint_and_load_panel(seeded, tmp_path):
    seed_panel(seeded)
    rows, max_filed = bio.facts_fingerprint(seeded)
    assert rows == PANEL_ROWS
    assert max_filed == date(2017, 3, 1)

    frame = bio.read_facts_frame(seeded)
    assert tuple(frame.columns) == bio.FACTS_COLUMNS == FACT_COLUMNS
    assert len(frame) == PANEL_ROWS
    facts = bio.facts_from_frame(frame)
    assert len(facts) == PANEL_ROWS
    by_symbol = {f.symbol for f in facts}
    assert by_symbol == {"AAPL", "ATVI"}

    instantaneous = [f for f in facts if f.tag == "Assets" and f.symbol == "ATVI"]
    assert [f.period_start for f in instantaneous] == [None, None]
    assert sorted(f.filed for f in instantaneous) == [date(2016, 2, 29), date(2017, 3, 1)]
    assert len({f.accn for f in instantaneous}) == 2  # the restatement is kept, not overwritten

    flow = next(f for f in facts if f.tag == "Revenues")
    assert flow.period_start == date(2015, 10, 1) and flow.period_end == date(2015, 12, 31)
    assert flow.fy == 2016 and flow.fp == "Q1" and flow.form == "10-Q"
    assert flow.val == pytest.approx(75_872_000_000.0)


def test_load_market_attaches_the_panel_and_caches_it(seeded, tmp_path, caplog):
    seed_panel(seeded)
    market_, _ = bio.load_market(seeded, cache_dir=tmp_path)
    assert market_.fundamentals is not EMPTY_FUNDAMENTALS
    cached = list(tmp_path.glob("fundamentals-*.pkl"))
    assert [p.name for p in cached] == [f"fundamentals-2017-03-01-{PANEL_ROWS}.pkl"]

    # a second load hits the pickle instead of the table
    with caplog.at_level("INFO"):
        again, _ = bio.load_market(seeded, cache_dir=tmp_path)
    assert "fundamentals cache hit" in caplog.text
    assert panel_facts(again.fundamentals) == panel_facts(market_.fundamentals)


def test_a_new_fingerprint_sweeps_the_stale_pickle(seeded, tmp_path):
    seed_panel(seeded)
    bio.load_market(seeded, cache_dir=tmp_path)
    seed_facts(
        seeded,
        [
            (CIK_AAPL, "us-gaap", "Assets", "USD", date(2017, 3, 31), date(2017, 3, 31),
             "305000000000", "0000320193-17-000002", 2017, "Q2", "10-Q", date(2017, 4, 27)),
        ],
    )
    bio.load_market(seeded, cache_dir=tmp_path)
    names = sorted(p.name for p in tmp_path.glob("fundamentals-*.pkl"))
    assert names == [f"fundamentals-2017-04-27-{PANEL_ROWS + 1}.pkl"]


def test_the_panel_holds_a_symbol_with_no_bars(seeded, tmp_path):
    """Gap A independence end to end: ATVI has facts in the panel and no row in history."""
    seed_panel(seeded)
    market_, _ = bio.load_market(seeded, cache_dir=tmp_path)
    assert "ATVI" not in market_.history
    frame = bio.read_facts_frame(seeded)
    assert "ATVI" in set(frame["symbol"])


def test_load_market_leaves_no_transaction_open(seeded, tmp_path):
    from psycopg.pq import TransactionStatus

    seed_panel(seeded)
    bio.load_market(seeded, cache_dir=tmp_path)
    assert seeded.info.transaction_status == TransactionStatus.IDLE


# ---- the research store (Step 7) ---------------------------------------------------------------

# A tiny store built with injected fakes, in the shape engine/tests/test_research_store.py uses.
# It is written here rather than imported so that test_research_store.py stays byte-identical --
# that file has no owner in this plan set and must not need one.

_COLS = ["Open", "High", "Low", "Close", "Adj Close", "Volume", "Dividends", "Stock Splits"]
S1 = date(1999, 1, 4)  # == research.FX_START
S2 = research.DEV_END


def _ticker_frame(days):
    index = pd.DatetimeIndex([pd.Timestamp(d) for d in days], name="Date")
    data = [[10.0, 11.0, 9.0, 10.5, 9.45, 1000 + i, 0.0, 0.0] for i, _ in enumerate(days)]
    return pd.DataFrame(data, index=index, columns=pd.Index(_COLS, name="Price"), dtype=float)


class _FakeYahoo:
    """Serves the same two sessions for every ticker asked for."""

    def __call__(self, tickers, start, end_exclusive):
        frames = {t: _ticker_frame([S1, S2]) for t in tickers}
        return pd.concat(
            list(frames.values()), axis=1, keys=list(frames), names=["Ticker", "Price"], sort=True
        )


def _fake_fx(start, end):
    return [(S1, Decimal("8002")), (S2, Decimal("13600"))]


@pytest.fixture
def members_dir(tmp_path):
    d = tmp_path / "members"
    d.mkdir()
    (d / "sp500_history.csv").write_text(
        'date,tickers\n1996-01-02,"AAPL,ATVI"\n', encoding="utf-8"
    )
    (d / "ndx_history.csv").write_text('date,tickers\n2007-02-01,"AAPL"\n', encoding="utf-8")
    (d / "membership_overrides.csv").write_text("date,index_id,action,ticker,note\n", encoding="utf-8")
    (d / "ticker_aliases.csv").write_text("old,new,effective_date,note\n", encoding="utf-8")
    return d


def _build_tiny_store(store, members_dir, *, facts=None):
    research.build_store(
        store,
        downloader=_FakeYahoo(),
        fetch_fx=_fake_fx,
        sleep=lambda _s: None,
        data_dir=members_dir,
        facts=facts,
    )
    return store


def test_data_files_is_not_widened():
    """The whole backward-compatibility argument in one assertion.

    research._read_manifest requires the four DATA_FILES names and allows only the optional
    ones beyond them, and load_store hashes the manifest's own keys. If fundamentals.csv ever
    joins DATA_FILES, every store on disk stops loading -- with a ValueError, before any reader
    runs.
    """
    assert research.FUNDAMENTALS_FILE not in research.DATA_FILES
    assert research.ANNOUNCEMENTS_FILE not in research.DATA_FILES
    assert research.OPTIONAL_DATA_FILES == (research.FUNDAMENTALS_FILE, research.ANNOUNCEMENTS_FILE)
    assert research.FUNDAMENTALS_HEADER == ",".join(FACT_COLUMNS)


def test_a_store_without_fundamentals_loads_with_an_empty_panel(tmp_path, members_dir):
    """A store built before this phase: four files, the old fingerprint, no error."""
    store = _build_tiny_store(tmp_path / "plain", members_dir)  # build_store(facts=None)
    assert not (store / research.FUNDAMENTALS_FILE).exists()
    before = research.fingerprint_of(research._read_manifest(store)["files"])
    data = research.load_store(store, data_dir=members_dir)
    assert sorted(data.manifest["files"]) == sorted(research.DATA_FILES)
    assert data.fingerprint == before
    assert data.market.fundamentals is EMPTY_FUNDAMENTALS


def test_a_store_with_fundamentals_round_trips_the_panel(seeded, tmp_path, members_dir):
    """The store CSV and the database give the SAME facts, because both go through
    io.facts_from_frame. This is the assertion that would fail if the reader were routed
    through fundamentals.fact_from_row, which takes typed values and would silently drop
    every string row."""
    seed_panel(seeded)
    facts = bio.facts_from_frame(bio.read_facts_frame(seeded))
    store = _build_tiny_store(tmp_path / "with", members_dir, facts=facts)
    data = research.load_store(store, data_dir=members_dir)
    assert research.FUNDAMENTALS_FILE in data.manifest["files"]
    assert data.market.fundamentals.names() == ("AAPL", "ATVI")
    assert panel_facts(data.market.fundamentals) == panel_facts(Panel.from_facts(facts))
    # and the instant marker survived the CSV: '' in the file, None in memory
    assets = [f for f in facts if f.tag == "Assets"]
    assert assets and all(f.period_start is None for f in assets)
    header = (store / research.FUNDAMENTALS_FILE).read_text(encoding="utf-8").splitlines()[0]
    assert header == research.FUNDAMENTALS_HEADER


def test_the_optional_file_changes_the_fingerprint_but_not_the_old_store(tmp_path, members_dir):
    """A fifth file is a new fingerprint, exactly as a rebuild with new bars would be -- while
    a store built without it keeps the digest it already had."""
    plain = _build_tiny_store(tmp_path / "a", members_dir)
    rich = _build_tiny_store(tmp_path / "b", members_dir, facts=())
    a = research.load_store(plain, data_dir=members_dir)
    b = research.load_store(rich, data_dir=members_dir)
    assert a.fingerprint != b.fingerprint
    assert set(b.manifest["files"]) - set(a.manifest["files"]) == {research.FUNDAMENTALS_FILE}
    assert set(a.manifest) == set(b.manifest) == research.MANIFEST_KEYS
    assert b.market.fundamentals.names() == ()


def test_facts_from_frame_skips_a_row_edgar_tagged_with_filed_before_period_end():
    """EDGAR's own tagging errors must not abort the whole load.

    ``Fact.__post_init__`` rejects ``filed < period_end`` and is right to: a filing cannot
    report a period that has not ended. But EDGAR contains such rows -- MEASURED at 28 of
    1,228,822 across 13 CIKs on the full load, e.g. CIK 6201 reporting shares outstanding
    for period 2027-07-17 in a filing dated 2026-07-23. Raising would make ``load_market``
    and the research store unusable against real data, so the boundary drops and counts
    them, matching ``fundamentals.facts_from_rows(skip_invalid=True)``.
    """
    import pandas as pd
    from seer_engine.backtest import io as bt_io
    from seer_engine.fundamentals import FACT_COLUMNS

    good = ("AAPL", "us-gaap", "Assets", "USD", "", "2024-06-30", "1000", "a-1", "10-Q",
            "2024", "Q2", "2024-08-01")
    bad = ("AAL", "dei", "EntityCommonStockSharesOutstanding", "shares", "", "2027-07-17",
           "5", "a-2", "10-Q", "2026", "Q2", "2026-07-23")
    frame = pd.DataFrame([good, bad], columns=list(FACT_COLUMNS))

    facts = bt_io.facts_from_frame(frame)
    assert len(facts) == 1, "the malformed row should be dropped, not raise"
    assert facts[0].tag == "Assets"
