"""Evidence stored with every paper entry (why-this-pick pipeline, phase 2, contract K2).

Migration 009 adds a nullable jsonb ``evidence`` column to ``orders``, ``book_targets`` and
``book_previews``. ``paper`` fills it from ``strategies.evidence`` for every decision it writes;
the idle instrument gets none; an evidence function that raises leaves NULL and the night still
succeeds; decisions and ``paper_check`` are unchanged.

The world is ``test_paper_check``'s: A picks every night, F4 and F1 decide 2026-11-02, FND has no
fundamentals panel and so picks nothing, C has no stored verdicts and so buys nothing.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

import test_paper_c as tc
import test_paper_check as pc
from seer_engine import bars, db, fx
from seer_engine.commands import paper, paper_check
from seer_engine.commands.migrate import MIGRATIONS_DIR
from seer_engine.paper import roster, store
from seer_engine.sim import MONTHLY_HOLD_TBILL, Pick, Target, size_picks
from seer_engine.strategies.a import STRATEGY_A_PARAMS
from seer_engine.strategies.c import STRATEGY_C_PARAMS

D = Decimal
EVIDENCE_TABLES = ("orders", "book_targets", "book_previews")
S1 = date(2026, 9, 29)
S3 = date(2026, 10, 1)


def boom(*args, **kwargs):
    raise RuntimeError("evidence exploded apiKey=sekret")


@pytest.fixture
def world(pg):
    """``test_paper_check.world``, declared here (bars, one FX row, 24 members, a SPY dividend)."""
    with db.transaction(pg, False):
        # This file tests paper-night mechanics through a live BRACKET strategy and through
        # FACTOR's and TIMING's evidence functions -- all still live code (RESOLVER and EVIDENCE
        # name them, and the retired entries' stored facts were written by them). So it pins its
        # OWN world rather than following production membership: 013 retired A, F4-FR and F1-FR,
        # and 017 retired the other six in favour of their Gotrade-fee successors.
        pg.execute("UPDATE strategies SET status = 'retired'")
        pg.execute(
            "UPDATE strategies SET status = 'active' WHERE id IN "
            "('SPY', 'A', 'C', 'F4-MOM12-N20-TREND-FR', 'F1-SPY-SMA200-M-FR', "
            "'RMW-FR', 'RAW-FR', 'MOM-FR', 'MVW-FR')"
        )
        bars.upsert_bars(pg, pc.synthetic_bars())
        fx.upsert_fx(pg, [(pc.HIST_START, pc.USD_IDR)])
        for s in pc.MEMBERS:
            pg.execute(
                "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
                "VALUES (%s, 'SP500', '2000-01-03', NULL, %s)",
                (s, s),
            )
        pg.execute(
            "INSERT INTO dividends (symbol, ex_date, amount) VALUES ('SPY', %s, %s)",
            (pc.SPY_EX_DATE, pc.SPY_DIVIDEND),
        )
    return pg


def run_nights(conn, nights=pc.NIGHTS) -> None:
    for d in nights:
        pc.night(conn, d)  # asserts paper.execute(...) == 0


def evidence_rows(conn, table: str, strategy_id: str):
    key = "data_date" if table == "book_previews" else "session_date"
    return pc.q(
        conn,
        f"SELECT {key}, symbol, evidence FROM {table} WHERE strategy_id = %s ORDER BY {key}, symbol",
        (strategy_id,),
    )


def assert_facts(value) -> None:
    assert isinstance(value, list) and value, value
    assert all(isinstance(f, str) and f.strip() for f in value), value


# Decision content without evidence: must be identical whatever evidence does.
DECISIONS = {
    "orders": (
        "strategy_id, session_date, slot, symbol, company, last_price, limit_price, tp_price, sl_price, "
        "shares, status, fill_date, fill_price, days_held, exit_date, exit_price, exit_reason, pnl_usd, mark",
        "strategy_id, session_date, symbol",
    ),
    "book_targets": (
        "strategy_id, session_date, rank, symbol, weight, last_price, limit_price, stop_price, take_price",
        "strategy_id, session_date, rank",
    ),
    "book_previews": ("strategy_id, data_date, rank, symbol, weight, last", "strategy_id, rank"),
    "book_positions": ("*", "strategy_id, symbol"),
    "book_fills": (
        "strategy_id, session_date, seq, symbol, side, shares, price, cash_usd, cost_usd, reason",
        "strategy_id, session_date, seq",
    ),
    "equity_snapshots": ("*", "strategy_id, date"),
    "paper_state": (
        "strategy_id, last_session, cash_usd, equity_usd, pending_session, pending_decision, kickoff_session",
        "strategy_id",
    ),
}


def decisions(conn):
    return {t: pc.q(conn, f"SELECT {cols} FROM {t} ORDER BY {order}") for t, (cols, order) in DECISIONS.items()}


def reset(conn) -> None:
    """Reset the paper clock (bars, universe and runs rows stay), as test_paper_command.reset does."""
    with db.transaction(conn, False):
        conn.execute(
            "TRUNCATE paper_state, book_positions, book_targets, book_fills, book_trades, book_previews, "
            "action_dismissals, orders, equity_snapshots RESTART IDENTITY"
        )
        conn.execute("UPDATE strategies SET paper_start = NULL, params = '{}'::jsonb")
        conn.execute("UPDATE runs SET paper_status = NULL, paper_error = NULL, paper_finished_at = NULL")


# ---- migration 009 -----------------------------------------------------------------------------


def test_009_adds_a_nullable_jsonb_evidence_column_to_three_tables(pg):
    rows = pg.execute(
        "SELECT table_name, data_type, is_nullable, column_default FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND column_name = 'evidence' ORDER BY table_name"
    ).fetchall()
    assert rows == [(t, "jsonb", "YES", None) for t in sorted(EVIDENCE_TABLES)]


def test_009_is_idempotent(pg):
    before = pg.execute(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = current_schema() ORDER BY table_name, ordinal_position"
    ).fetchall()
    pg.execute((MIGRATIONS_DIR / "009_evidence.sql").read_text(encoding="utf-8"))
    pg.commit()
    after = pg.execute(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = current_schema() ORDER BY table_name, ordinal_position"
    ).fetchall()
    assert after == before


# ---- paper.store -------------------------------------------------------------------------------


PICKS = (
    Pick("AAA", D("10"), D("10"), D("11"), D("9.5")),
    Pick("BBB", D("20"), D("20"), D("22"), D("19")),
)
TARGETS = (
    Target("AAA", D("0.500000"), D("10")),
    Target("BIL", D("0.500000"), D("91.5")),
)


def test_insert_pending_orders_stores_each_symbols_facts_and_null_when_absent(pg):
    store.init_paper_state(pg, "A", paper_start=S1, cash0=D("1250.0000"), usd_idr=D("16000.0000"))
    sized = size_picks(store.load_portfolio(pg, "A"), PICKS, S1)
    facts = {"AAA": ("Closed at $10.00.", "1st of 2 that qualified.")}
    assert store.insert_pending_orders(pg, "A", sized.placed, evidence=facts) == 2
    assert pg.execute("SELECT symbol, evidence FROM orders ORDER BY symbol").fetchall() == [
        ("AAA", ["Closed at $10.00.", "1st of 2 that qualified."]),
        ("BBB", None),
    ]


def book_state(pg) -> None:
    """save_book_decision writes paper_state.pending_session, so the book needs a state row."""
    store.init_paper_state(pg, pc.F4, paper_start=S3, cash0=D("1250.0000"), usd_idr=D("16000.0000"))


def test_store_without_evidence_writes_null_like_before(pg):
    store.init_paper_state(pg, "A", paper_start=S1, cash0=D("1250.0000"), usd_idr=D("16000.0000"))
    book_state(pg)
    sized = size_picks(store.load_portfolio(pg, "A"), PICKS, S1)
    store.insert_pending_orders(pg, "A", sized.placed)
    store.save_book_decision(pg, pc.F4, S3, TARGETS)
    store.save_book_preview(pg, pc.F4, S1, TARGETS)
    for t in EVIDENCE_TABLES:
        assert pg.execute(f"SELECT count(*) FROM {t} WHERE evidence IS NOT NULL").fetchone()[0] == 0
        assert pg.execute(f"SELECT count(*) FROM {t}").fetchone()[0] == 2


def test_book_decision_and_preview_store_facts_and_null_for_the_idle_symbol(pg):
    book_state(pg)
    facts = {"AAA": ["Rose 48.2% over the 12 months up to a month ago."]}
    store.save_book_decision(pg, pc.F4, S3, TARGETS, evidence=facts)
    store.save_book_preview(pg, pc.F4, S1, TARGETS, evidence=facts)
    expected = [("AAA", ["Rose 48.2% over the 12 months up to a month ago."]), ("BIL", None)]
    assert pg.execute("SELECT symbol, evidence FROM book_targets ORDER BY rank").fetchall() == expected
    assert pg.execute("SELECT symbol, evidence FROM book_previews ORDER BY rank").fetchall() == expected
    # The replay's reader is unchanged: evidence never reaches a Target.
    assert store.read_book_targets(pg, pc.F4, S3) == TARGETS


def test_empty_facts_are_stored_as_null_and_bad_facts_are_refused(pg):
    book_state(pg)
    store.save_book_decision(pg, pc.F4, S3, TARGETS, evidence={"AAA": ()})
    assert pg.execute("SELECT evidence FROM book_targets ORDER BY rank").fetchall() == [(None,), (None,)]
    with pytest.raises(TypeError):
        store.save_book_decision(pg, pc.F4, S3, TARGETS, evidence={"AAA": "not a list"})
    with pytest.raises(TypeError):
        store.save_book_decision(pg, pc.F4, S3, TARGETS, evidence={"AAA": ["ok", 3]})


# ---- commands.paper._evidence (no database) ----------------------------------------------------


def test_helper_never_asks_for_the_idle_symbol_and_dedups(monkeypatch):
    seen = []

    def fake(object_name, market, params, data_date, symbols):
        seen.append((object_name, tuple(symbols)))
        return {s: (f"{s} fact.",) for s in symbols}

    monkeypatch.setattr(paper.evidence, "evidence_for", fake)
    e = replace(roster.entry(pc.F4), rules=MONTHLY_HOLD_TBILL)
    out = paper._evidence(e, None, S1, ["AAA", "BIL", "AAA", "BBB"])
    assert seen == [("FACTOR", ("AAA", "BBB"))]
    assert out == {"AAA": ("AAA fact.",), "BBB": ("BBB fact.",)}
    seen.clear()
    assert paper._evidence(e, None, S1, ["BIL"]) == {}
    assert seen == []  # nothing to explain: no call at all


def test_helper_turns_any_failure_into_no_evidence_and_a_warning(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="seer_engine.commands.paper")
    e = roster.entry("A")
    monkeypatch.setattr(paper.evidence, "evidence_for", boom)
    assert paper._evidence(e, None, S1, ["AAA"]) == {}
    assert "A 2026-09-29: no evidence stored tonight" in caplog.text
    assert "sekret" not in caplog.text
    for bad in (["not a mapping"], {"AAA": "a bare string"}, {"AAA": ("ok", "")}, {"AAA": (1,)}):
        monkeypatch.setattr(paper.evidence, "evidence_for", lambda *a, _bad=bad, **k: _bad)
        assert paper._evidence(e, None, S1, ["AAA"]) == {}


def test_helper_drops_symbols_the_method_cannot_explain(monkeypatch):
    monkeypatch.setattr(paper.evidence, "evidence_for", lambda *a, **k: {"AAA": ("x.",), "BBB": ()})
    assert paper._evidence(roster.entry("A"), None, S1, ["AAA", "BBB", "CCC"]) == {"AAA": ("x.",)}


def test_the_benchmark_is_never_asked(world, monkeypatch):
    calls = []
    real = paper.evidence.evidence_for

    def spy(object_name, *args, **kwargs):
        calls.append(object_name)
        return real(object_name, *args, **kwargs)

    monkeypatch.setattr(paper.evidence, "evidence_for", spy)
    run_nights(world, pc.NIGHTS[:2])
    assert calls and roster.BENCHMARK_OBJECT not in calls


# ---- whole nights ------------------------------------------------------------------------------


def test_every_entry_written_by_paper_has_evidence(world):
    run_nights(world)
    a_orders = evidence_rows(world, "orders", "A")
    assert len(a_orders) >= 7  # A picks every night in this world
    for _, _, value in a_orders:
        assert_facts(value)
    # Each stock has its own reason: no two orders of one session share their facts.
    by_session: dict[date, list] = {}
    for session, _, value in a_orders:
        by_session.setdefault(session, []).append(tuple(value))
    for facts in by_session.values():
        assert len(set(facts)) == len(facts)
    for sid in (pc.F4, pc.F1):
        # The idle instrument (if the rules have one) is never explained; every other row is. A night
        # F1's rule is off decides nothing but the idle (TIMING returns {}), so only non-idle rows count.
        idle = roster.entry(sid).rules.idle_symbol
        targets = [r for r in evidence_rows(world, "book_targets", sid) if r[1] != idle]
        previews = [r for r in evidence_rows(world, "book_previews", sid) if r[1] != idle]
        assert targets  # F4 and F1 both decide 2026-11-02 in this world (test_paper_check)
        for _, _, value in targets + previews:
            assert_facts(value)
        for _, symbol, value in evidence_rows(world, "book_targets", sid) + evidence_rows(world, "book_previews", sid):
            if symbol == idle:
                assert value is None
    assert {s for _, s, _ in evidence_rows(world, "book_targets", pc.F1)} - {roster.entry(pc.F1).rules.idle_symbol} == {"SPY"}
    # Nothing paper writes for SPY, C (no verdicts) or FND (no panel) carries evidence.
    for t in EVIDENCE_TABLES:
        assert pc.q(world, f"SELECT count(*) FROM {t} WHERE strategy_id IN ('SPY', 'C', 'FND') AND evidence IS NOT NULL") == [(0,)]
    assert paper_check.execute(world, require_sessions=7) == 0


def test_c_orders_carry_a_facts_under_c_params(world):
    """C's placed orders get STRATEGY_C evidence (A's facts under ``CParams.a``). Phase 3's
    ``test_paper_c.py::test_explain_fills_c_pending_orders_like_a`` relies on this."""
    for d in pc.NIGHTS[:3]:
        tc.night(world, d, tc.allow_all)  # bars run, every candidate allowed, paper
    c_orders = evidence_rows(world, "orders", "C")
    assert c_orders
    for _, _, value in c_orders:
        assert_facts(value)
    if STRATEGY_C_PARAMS.a == STRATEGY_A_PARAMS:
        a_facts = {(d, s): v for d, s, v in evidence_rows(world, "orders", "A")}
        for d, s, v in c_orders:
            if (d, s) in a_facts:
                assert v == a_facts[(d, s)]


def test_an_evidence_function_that_raises_leaves_null_and_the_night_succeeds(world, monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="seer_engine.commands.paper")
    monkeypatch.setattr(paper.evidence, "evidence_for", boom)
    run_nights(world)
    for t in EVIDENCE_TABLES:
        assert pc.q(world, f"SELECT count(*) FROM {t} WHERE evidence IS NOT NULL") == [(0,)]
    assert pc.q(world, "SELECT count(*) FROM orders WHERE strategy_id = 'A'")[0][0] >= 7
    assert pc.q(world, "SELECT DISTINCT paper_status FROM runs WHERE NOT is_demo AND paper_status IS NOT NULL") == [
        ("success",)
    ]
    assert "no evidence stored tonight" in caplog.text and "sekret" not in caplog.text
    assert paper_check.execute(world, require_sessions=7) == 0


def test_one_method_failing_does_not_touch_the_others(world, monkeypatch):
    monkeypatch.setitem(paper.evidence.EVIDENCE, "FACTOR", boom)
    run_nights(world)
    assert evidence_rows(world, "book_targets", pc.F4)
    assert all(value is None for _, _, value in evidence_rows(world, "book_targets", pc.F4))
    assert all(value is None for _, _, value in evidence_rows(world, "book_previews", pc.F4))
    for _, _, value in evidence_rows(world, "orders", "A") + evidence_rows(world, "book_targets", pc.F1):
        assert_facts(value)
    assert paper_check.execute(world, require_sessions=7) == 0


def test_evidence_never_changes_a_decision(world, monkeypatch):
    nights = pc.NIGHTS[:6]  # through the night that decides 2026-11-02
    run_nights(world, nights)
    with_evidence = decisions(world)
    reset(world)
    monkeypatch.setattr(paper.evidence, "evidence_for", boom)
    run_nights(world, nights)
    assert decisions(world) == with_evidence
