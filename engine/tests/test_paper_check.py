"""`paper_check` on Postgres: real `paper` nights over a synthetic world, then the replay check.

The world: 24 members S00..S23 on an 8-session sawtooth (+0.5 x 5, -0.75 x 3; a 3-day dip puts
RSI(2) under 10 above a rising SMA(200), so A picks every night and its trades close at tp), SPY
rising 0.25 a session, one USD/IDR row, one SPY dividend. Bars run past the last night. Eight
nights: the first (2026-10-23) starts paper on 2026-10-26; the rest step 7 sessions through
2026-11-03, with 2026-11-02 the monthly decision for F4 and F1.
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from functools import lru_cache

import pytest
from psycopg.rows import tuple_row

from seer_engine import bars, cli, dates, db, fx
from seer_engine.commands import paper, paper_check
from seer_engine.paper import replay
from seer_engine.prices import Bar

UTC = timezone.utc
HIST_START = date(2025, 5, 1)
HIST_END = date(2026, 11, 13)
MEMBERS = tuple(f"S{k:02d}" for k in range(24))
CYCLE = tuple(Decimal(x) for x in ("0.5", "0.5", "0.5", "0.5", "0.5", "-0.75", "-0.75", "-0.75"))
USD_IDR = Decimal("16500.0000")
SPY_EX_DATE = date(2026, 10, 28)
SPY_DIVIDEND = Decimal("1.850000")

NIGHTS = (
    date(2026, 10, 23),  # first night: paper_start = 2026-10-26
    date(2026, 10, 26),
    date(2026, 10, 27),
    date(2026, 10, 28),
    date(2026, 10, 29),
    date(2026, 10, 30),  # decides 2026-11-02, the first session of November (F4, F1)
    date(2026, 11, 2),
    date(2026, 11, 3),
)
PAPER_START = date(2026, 10, 26)
LAST = date(2026, 11, 3)
DAY0 = date(2026, 10, 23)
NOV2 = date(2026, 11, 2)
F4 = "F4-MOM12-N20-TREND"
F1 = "F1-SPY-SMA200-M"
ROSTER_IDS = ("SPY", "A", F4, F1, "C", "FND")


# ---- the synthetic world -----------------------------------------------------------------------


@lru_cache(maxsize=1)
def synthetic_bars() -> tuple[Bar, ...]:
    days = dates.sessions(HIST_START, HIST_END)
    out: list[Bar] = []
    for k, symbol in enumerate(MEMBERS):
        close = Decimal(10) + Decimal(k) / 2
        for t, d in enumerate(days):
            o = close
            c = o + CYCLE[(t + k) % len(CYCLE)]
            out.append(Bar(symbol, d, o, max(o, c) + Decimal("0.125"), min(o, c) - 1, c, 3_000_000))
            close = c
    spy = Decimal(400)
    for d in days:
        o = spy
        c = o + Decimal("0.25")
        out.append(Bar("SPY", d, o, c + Decimal("0.5"), o - Decimal("0.5"), c, 80_000_000))
        spy = c
    return tuple(out)


@pytest.fixture
def world(pg):
    with db.transaction(pg, False):
        bars.upsert_bars(pg, synthetic_bars())
        fx.upsert_fx(pg, [(HIST_START, USD_IDR)])
        for s in MEMBERS:
            pg.execute(
                "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
                "VALUES (%s, 'SP500', '2000-01-03', NULL, %s)",
                (s, s),
            )
        pg.execute(
            "INSERT INTO dividends (symbol, ex_date, amount) VALUES ('SPY', %s, %s)", (SPY_EX_DATE, SPY_DIVIDEND)
        )
    return pg


def night(conn, d: date) -> None:
    """The real runs row a successful bars run writes for the night of ``d``, then ``paper``."""
    now = datetime(d.year, d.month, d.day, 23, tzinfo=UTC)
    rd = dates.run_dates(now)
    with db.transaction(conn, False):
        conn.execute(
            """
            INSERT INTO runs (status, data_date, session_date, is_demo, finished_at)
            VALUES ('success', %s, %s, false, now())
            ON CONFLICT (session_date) WHERE NOT is_demo DO NOTHING
            """,
            (rd.data_date, rd.session_date),
        )
    assert paper.execute(conn, now=now) == 0, f"paper failed on the night of {d}"


@pytest.fixture
def stepped(world):
    for d in NIGHTS:
        night(world, d)
    return world


def q(conn, sql, params=()):
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    conn.rollback()
    return rows


def results(conn) -> dict[str, replay.CheckResult]:
    return {r.strategy_id: r for r in paper_check.check(conn)}


def text(found: dict[str, replay.CheckResult]) -> str:
    return "\n".join(replay.render(tuple(found.values())))


def tamper(conn, sql: str, params=()) -> None:
    with db.transaction(conn, False):
        with conn.cursor() as cur:
            cur.execute(sql, params)
            assert cur.rowcount >= 1, f"the tamper touched no row: {sql}"


# Whole rows of every table paper state lives in: the check must leave them all unchanged.
TABLES = {
    "paper_state": "strategy_id",
    "book_positions": "strategy_id, symbol",
    "book_targets": "strategy_id, session_date, rank",
    "book_fills": "id",
    "book_trades": "id",
    "orders": "id",
    "equity_snapshots": "strategy_id, date",
    "strategies": "id",
    "runs": "id",
    "bars": "symbol, date",
    "dividends": "symbol, ex_date",
    "split_adjustments": "symbol, execution_date",
}


def everything(conn):
    return {t: q(conn, f"SELECT x::text FROM {t} x ORDER BY {order}") for t, order in TABLES.items()}


# ---- not started and the first night -----------------------------------------------------------


def test_paper_check_is_a_command():
    assert "paper_check" in cli.discover()


def test_fresh_database_reports_every_strategy_not_started(pg):
    found = results(pg)
    assert tuple(found) == ROSTER_IDS
    assert {r.status for r in found.values()} == {"not-started"}
    assert paper_check.execute(pg) == 0
    assert paper_check.execute(pg, require_sessions=1) == 1


def test_first_night_only_is_ok_with_zero_sessions(world):
    night(world, NIGHTS[0])
    found = results(world)
    for sid in ROSTER_IDS:
        r = found[sid]
        assert r.status == "ok", text(found)
        assert (r.sessions, r.paper_start, r.last_session) == (0, PAPER_START, DAY0)
    assert q(world, "SELECT count(*) FROM orders WHERE strategy_id = 'A' AND status = 'pending'") >= [(1,)]
    assert paper_check.execute(world) == 0
    assert paper_check.execute(world, require_sessions=1) == 1


# ---- eight nights ------------------------------------------------------------------------------


def test_eight_nights_equal_the_replay(stepped):
    found = results(stepped)
    for sid in ROSTER_IDS:
        r = found[sid]
        assert r.status == "ok", text(found)
        assert (r.sessions, r.paper_start, r.last_session) == (7, PAPER_START, LAST)
    # The check was not vacuous: every record kind it compares exists.
    assert q(stepped, "SELECT count(*) FROM orders WHERE strategy_id = 'A' AND status = 'closed'")[0][0] >= 1
    assert q(stepped, "SELECT count(*) FROM orders WHERE strategy_id = 'A' AND status = 'open'")[0][0] >= 1
    assert q(stepped, "SELECT count(*) FROM orders WHERE strategy_id = 'A' AND status = 'pending'")[0][0] >= 1
    assert q(stepped, "SELECT count(*) FROM book_positions WHERE strategy_id = %s", (F4,))[0][0] >= 1
    assert q(stepped, "SELECT count(*) FROM book_targets WHERE strategy_id = %s AND session_date = %s", (F4, NOV2))[0][0] >= 1
    assert q(stepped, "SELECT symbol FROM book_positions WHERE strategy_id = %s", (F1,)) == [("SPY",)]
    assert q(stepped, "SELECT symbol FROM book_positions WHERE strategy_id = 'SPY'") == [("SPY",)]
    assert paper_check.execute(stepped, require_sessions=7) == 0
    assert paper_check.execute(stepped, require_sessions=8) == 1


def test_check_writes_nothing(stepped):
    before = everything(stepped)
    assert paper_check.execute(stepped, require_sessions=7) == 0
    assert everything(stepped) == before


def test_execute_logs_a_line_per_strategy_and_each_failure(stepped, caplog):
    caplog.set_level(logging.INFO, logger="seer_engine.commands.paper_check")
    assert paper_check.execute(stepped, require_sessions=8) == 1
    for sid in ROSTER_IDS:
        assert f"paper_check: {sid} " in caplog.text
    assert "paper_check failed: SPY: 7 sessions stepped, 8 required" in caplog.text


TAMPERS = [
    pytest.param(
        "UPDATE equity_snapshots SET equity_usd = equity_usd + 1 WHERE strategy_id = 'A' AND date = DATE '2026-10-28'",
        "A",
        "snapshot 2026-10-28: equity_usd stored",
        id="snapshot",
    ),
    pytest.param(
        "UPDATE equity_snapshots SET cash_usd = cash_usd - 1 WHERE strategy_id = 'SPY' AND date = DATE '2026-10-23'",
        "SPY",
        "snapshot 2026-10-23: cash_usd stored",
        id="day0-snapshot",
    ),
    pytest.param(
        "UPDATE orders SET pnl_usd = pnl_usd + 1 "
        "WHERE id = (SELECT min(id) FROM orders WHERE strategy_id = 'A' AND status = 'closed')",
        "A",
        ": pnl_usd stored",
        id="closed-order",
    ),
    pytest.param(
        "DELETE FROM orders WHERE id = (SELECT max(id) FROM orders WHERE strategy_id = 'A' AND status = 'pending')",
        "A",
        "in the replay, missing from the database",
        id="pending-order",
    ),
    pytest.param(
        "UPDATE orders SET mark = mark + 1 "
        "WHERE id = (SELECT min(id) FROM orders WHERE strategy_id = 'A' AND status = 'open')",
        "A",
        ": stored",
        id="open-mark",
    ),
    pytest.param(
        "UPDATE book_positions SET shares = shares + 1 WHERE strategy_id = 'F1-SPY-SMA200-M' AND symbol = 'SPY'",
        F1,
        "position SPY: shares stored",
        id="position",
    ),
    pytest.param(
        "UPDATE book_targets SET weight = weight / 2 "
        "WHERE strategy_id = 'F4-MOM12-N20-TREND' AND session_date = DATE '2026-11-02' AND rank = 1",
        F4,
        "target 2026-11-02 rank 1: weight stored",
        id="target",
    ),
    pytest.param(
        "UPDATE book_fills SET price = price + 0.01 "
        "WHERE strategy_id = 'F4-MOM12-N20-TREND' AND session_date = DATE '2026-11-02' AND seq = 1",
        F4,
        ": price stored",
        id="fill",
    ),
    pytest.param(
        "INSERT INTO book_trades (strategy_id, symbol, entry_date, exit_date, entry_price, exit_price, days_held, "
        "cost_usd, income_usd, pnl_usd, exit_reason, idle) VALUES ('F4-MOM12-N20-TREND', 'S00', "
        "DATE '2026-11-03', DATE '2026-11-03', 10, 11, 1, 0.02, 0, 0.98, 'signal', false)",
        F4,
        "in the database, not in the replay",
        id="trade",
    ),
    pytest.param(
        "UPDATE paper_state SET pending_decision = NOT pending_decision WHERE strategy_id = 'F1-SPY-SMA200-M'",
        F1,
        "paper_state: pending_decision stored",
        id="pending-decision",
    ),
    pytest.param(
        "UPDATE book_positions SET mark = mark + 1 WHERE strategy_id = 'SPY'",
        "SPY",
        "holding SPY: mark stored",
        id="benchmark-holding",
    ),
]


@pytest.mark.parametrize(("sql", "victim", "fragment"), TAMPERS)
def test_tampered_record_fails_with_a_readable_difference(stepped, sql, victim, fragment):
    tamper(stepped, sql)
    found = results(stepped)
    rendered = text(found)
    assert found[victim].status == "mismatch", rendered
    assert fragment in rendered, rendered
    for sid in ROSTER_IDS:
        if sid != victim:
            assert found[sid].status == "ok", rendered
    assert paper_check.execute(stepped) == 1


# ---- splits and broken state -------------------------------------------------------------------


def test_applied_split_on_a_held_symbol_reports_split_affected(stepped):
    split_day = LAST
    with db.transaction(stepped, False):
        stepped.execute(
            "INSERT INTO split_adjustments (symbol, execution_date, split_from, split_to, applied) "
            "VALUES ('SPY', %s, 1, 2, true)",
            (split_day,),
        )
        # What splits.apply_splits does to history before the execution date.
        stepped.execute(
            "UPDATE bars SET open = round(open / 2, 4), high = round(high / 2, 4), low = round(low / 2, 4), "
            "close = round(close / 2, 4), volume = volume * 2 WHERE symbol = 'SPY' AND date < %s",
            (split_day,),
        )
        stepped.execute(
            "UPDATE dividends SET amount = round(amount / 2, 6) WHERE symbol = 'SPY' AND ex_date < %s", (split_day,)
        )
    found = results(stepped)
    rendered = text(found)
    assert found["SPY"].status == "split-affected", rendered
    assert found["SPY"].splits == (("SPY", split_day),)
    assert found[F1].status == "split-affected", rendered  # held SPY since 2026-11-02
    assert found["A"].status == "ok", rendered  # never touched SPY
    assert found[F4].status == "ok", rendered  # SPY only gates its trend (a ratio)
    assert "applied split SPY on 2026-11-03" in rendered
    assert paper_check.execute(stepped) == 0


def test_unapplied_split_is_ignored(stepped):
    with db.transaction(stepped, False):
        stepped.execute(
            "INSERT INTO split_adjustments (symbol, execution_date, split_from, split_to, applied) "
            "VALUES ('SPY', %s, 1, 2, false)",
            (LAST,),
        )
    assert {r.status for r in results(stepped).values()} == {"ok"}


def test_paper_start_without_state_is_a_mismatch(stepped):
    tamper(stepped, "DELETE FROM paper_state WHERE strategy_id = 'A'")
    found = results(stepped)
    assert found["A"].status == "mismatch"
    assert "paper_state: strategies.paper_start is 2026-10-26 but paper_state has no row" in text(found)
    assert paper_check.execute(stepped) == 1


def test_unreadable_stored_row_is_a_mismatch_not_a_crash(stepped):
    # An open order whose stop is above its target fails sim.Order's own validation.
    tamper(
        stepped,
        "UPDATE orders SET sl_price = tp_price + 1 "
        "WHERE id = (SELECT min(id) FROM orders WHERE strategy_id = 'A' AND status = 'open')",
    )
    found = results(stepped)
    assert found["A"].status == "mismatch"
    assert found["A"].differences[0].where == "stored rows"
    assert {found[s].status for s in ("SPY", F4, F1)} == {"ok"}


def test_the_replay_passes_over_a_window_containing_a_retirement(world):
    from seer_engine.paper import store

    for d in NIGHTS[:4]:
        night(world, d)
    [(last_traded,)] = q(world, "SELECT last_session FROM paper_state WHERE strategy_id = 'A'")
    with db.transaction(world, False):
        assert store.retire(world, "A") == last_traded
    for d in NIGHTS[4:]:
        night(world, d)

    found = results(world)
    assert tuple(found) == ROSTER_IDS  # retired, but still on the board and still checked
    assert found["A"].status in ("ok", "split-affected"), text(found)
    assert found["A"].last_session == last_traded
    assert found["SPY"].last_session == LAST
    assert paper_check.execute(world) == 0


def test_check_needs_an_idle_connection(pg):
    pg.execute("SELECT 1")
    with pytest.raises(ValueError, match="no transaction in progress"):
        paper_check.check(pg)
    pg.rollback()


# ---- the command line --------------------------------------------------------------------------


def test_require_sessions_argument():
    p = argparse.ArgumentParser()
    paper_check.add_arguments(p)
    assert p.parse_args([]).require_sessions == 0
    assert p.parse_args(["--require-sessions", "5"]).require_sessions == 5
    with pytest.raises(SystemExit):
        p.parse_args(["--require-sessions", "-1"])
    with pytest.raises(SystemExit):
        p.parse_args(["--require-sessions", "five"])


def test_run_wiring(monkeypatch):
    p = argparse.ArgumentParser()
    paper_check.add_arguments(p)
    args = p.parse_args(["--require-sessions", "5"])
    args.dry_run = False
    args.verbose = 0

    class DummyConn:
        closed = False

        def close(self):
            self.closed = True

    conn = DummyConn()
    seen = {}

    def fake_execute(c, **kw):
        seen.update(kw, conn=c)
        return 1

    monkeypatch.setattr(paper_check.db, "connect", lambda: conn)
    monkeypatch.setattr(paper_check, "execute", fake_execute)
    assert paper_check.run(args) == 1
    assert seen == {"require_sessions": 5, "conn": conn} and conn.closed


def test_execute_refuses_a_negative_requirement(pg):
    with pytest.raises(ValueError):
        paper_check.execute(pg, require_sessions=-1)
