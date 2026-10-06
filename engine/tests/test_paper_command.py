"""`paper`: the nightly paper step on Postgres with synthetic bars, universe, FX and dividends.

Bars are seeded up front through 2026-10-09, so a look-ahead would be visible. A night inserts the
real runs row a successful bars run writes, then runs `paper.execute(conn, now=<night 23:00 UTC>)`.
"""

from __future__ import annotations

import math
import random
from datetime import date, datetime, timezone
from decimal import Decimal
from functools import lru_cache

import pytest
from psycopg.rows import tuple_row

from seer_engine import bars, cli, dates, db, fx
from seer_engine.backtest import io as bio
from seer_engine.backtest.benchmark import Dividend, buy_and_hold
from seer_engine.backtest.book_runner import run_rules
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.runner import INITIAL_IDR
from seer_engine.commands import paper
from seer_engine.paper import roster
from seer_engine.prices import Bar
from seer_engine.sim import initial_cash_usd
from seer_engine.strategies.base import history_from_bars

UTC = timezone.utc
HIST_START = date(2025, 1, 2)
HIST_END = date(2026, 10, 9)
STOCKS = (
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "JPM", "V", "MA", "UNH",
    "HD", "PG", "COST", "LLY", "XOM", "JNJ", "ABBV", "MRK", "PEP", "KO", "WMT", "BAC",
)
DIV_DATE = date(2026, 9, 28)
DIV_AMT = Decimal("1.500000")

NIGHTS = (
    date(2026, 9, 23),  # first night: paper_start = 2026-09-24
    date(2026, 9, 24),
    date(2026, 9, 25),
    date(2026, 9, 28),
    date(2026, 9, 29),
    date(2026, 9, 30),  # decides 2026-10-01, the first session of October (F4, F1)
    date(2026, 10, 1),
)
N0 = NIGHTS[0]
PAPER_START = date(2026, 9, 24)
OCT1 = date(2026, 10, 1)
OCT2 = date(2026, 10, 2)
F4 = "F4-MOM12-N20-TREND-FR"
F1 = "F1-SPY-SMA200-M-FR"

ENTRIES = {e.id: e for e in roster.ROSTER}
IDS = tuple(sorted(e.id for e in roster.active(roster.ROSTER)))  # the whole-share F4, F1, FND are retired (010)


# ---- the synthetic world -----------------------------------------------------------------------


def _sessions() -> list[date]:
    return dates.sessions(HIST_START, HIST_END)


def fx_rate(d: date) -> Decimal:
    """A rate that differs between neighbouring sessions (so a look-ahead on FX would show)."""
    i = _sessions().index(d)
    return Decimal(16000 + 5 * (i % 11)).quantize(Decimal("0.0001"))


@lru_cache(maxsize=1)
def synthetic_bars() -> tuple[Bar, ...]:
    days = _sessions()
    out: list[Bar] = []
    for i, d in enumerate(days):  # SPY: a smooth uptrend, always above its 200-day average at the end
        c = 400.0 * 1.0005**i * (1 + 0.01 * math.sin(i / 5))
        o = c * (1 - 0.002 * math.cos(i / 3))
        out.append(
            bars.make_bar(
                "SPY", d, round(o, 4), round(max(o, c) * 1.004, 4), round(min(o, c) * 0.996, 4), round(c, 4), 80_000_000
            )
        )
    for symbol in STOCKS:
        rng = random.Random(f"paper-{symbol}")
        price = 40 + 160 * rng.random()
        drift = 0.0002 + 0.0012 * rng.random()
        for d in days:
            o = price * (1 + rng.gauss(0, 0.004))
            c = price * (1 + drift + rng.gauss(0, 0.018))
            h = max(o, c) * (1 + abs(rng.gauss(0, 0.006)))
            lo = min(o, c) * (1 - abs(rng.gauss(0, 0.006)))
            out.append(
                bars.make_bar(
                    symbol, d, round(o, 4), round(h, 4), round(lo, 4), round(c, 4), 1_500_000 + rng.randrange(1_000_000)
                )
            )
            price = c
    return tuple(out)


@pytest.fixture
def world(pg):
    with db.transaction(pg, False):
        bars.upsert_bars(pg, synthetic_bars())
        fx.upsert_fx(pg, [(d, fx_rate(d)) for d in _sessions()])
        for s in STOCKS:
            pg.execute(
                "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
                "VALUES (%s, 'SP500', '2020-01-02', NULL, %s)",
                (s, s),
            )
        pg.execute("INSERT INTO dividends (symbol, ex_date, amount) VALUES ('SPY', %s, %s)", (DIV_DATE, DIV_AMT))
    return pg


# ---- helpers ---------------------------------------------------------------------------------


def night_of(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 23, tzinfo=UTC)


def session_of(d: date) -> date:
    return dates.run_dates(night_of(d)).session_date


def bars_run(conn, d: date, status: str = "success") -> None:
    """The real runs row `nightly` writes for the night of `d`."""
    rd = dates.run_dates(night_of(d))
    with db.transaction(conn, False):
        conn.execute(
            """
            INSERT INTO runs (status, data_date, session_date, is_demo, finished_at)
            VALUES (%s, %s, %s, false, now())
            ON CONFLICT (session_date) WHERE NOT is_demo DO NOTHING
            """,
            (status, rd.data_date, rd.session_date),
        )


def go(conn, d: date, *, dry_run: bool = False) -> int:
    return paper.execute(conn, now=night_of(d), dry_run=dry_run)


def night(conn, d: date, *, dry_run: bool = False) -> int:
    bars_run(conn, d)
    return go(conn, d, dry_run=dry_run)


def q(conn, sql, params=()):
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    conn.rollback()
    return rows


def paper_run(conn, d: date):
    return q(
        conn,
        "SELECT paper_status, paper_error, paper_finished_at FROM runs WHERE session_date = %s AND NOT is_demo",
        (session_of(d),),
    )


# Paper content without ids or timestamps: equal across two passes over the same nights.
CONTENT = {
    "paper_state": (
        "strategy_id, last_session, cash_usd, equity_usd, initial_cash_usd, usd_idr, pending_session, pending_decision",
        "strategy_id",
    ),
    "book_positions": ("*", "strategy_id, symbol"),
    "book_targets": ("*", "strategy_id, session_date, rank"),
    "book_fills": (
        "strategy_id, session_date, seq, symbol, side, shares, price, cash_usd, cost_usd, reason",
        "strategy_id, session_date, seq",
    ),
    "book_trades": (
        "strategy_id, symbol, entry_date, exit_date, entry_price, exit_price, days_held, cost_usd, "
        "income_usd, pnl_usd, exit_reason, idle",
        "strategy_id, symbol, entry_date",
    ),
    "orders": (
        "strategy_id, session_date, slot, symbol, company, last_price, limit_price, tp_price, sl_price, "
        "shares, explanation, status, fill_date, fill_price, days_held, exit_date, exit_price, exit_reason, "
        "pnl_usd, mark",
        "strategy_id, session_date, symbol",
    ),
    "equity_snapshots": ("*", "strategy_id, date"),
    "strategies": ("id, paper_start, params", "id"),
}

# Whole rows (ids and timestamps included) of everything `paper` may write: "writes nothing".
EVERYTHING = {
    "paper_state": "strategy_id",
    "book_positions": "strategy_id, symbol",
    "book_targets": "strategy_id, session_date, rank",
    "book_fills": "id",
    "book_trades": "id",
    "orders": "id",
    "equity_snapshots": "strategy_id, date",
    "strategies": "id",
    "runs": "id",
}


def content(conn):
    return {t: q(conn, f"SELECT {cols} FROM {t} ORDER BY {order}") for t, (cols, order) in CONTENT.items()}


def everything(conn):
    return {t: q(conn, f"SELECT x::text FROM {t} x ORDER BY {order}") for t, order in EVERYTHING.items()}


def reset(conn) -> None:
    """The plan index Rollback's "reset the paper clock" (the bars, runs rows and universe stay)."""
    with db.transaction(conn, False):
        conn.execute(
            "TRUNCATE paper_state, book_positions, book_targets, book_fills, book_trades, "
            "action_dismissals, orders, equity_snapshots RESTART IDENTITY"
        )
        conn.execute("UPDATE strategies SET paper_start = NULL, params = '{}'::jsonb")
        conn.execute("UPDATE runs SET paper_status = NULL, paper_error = NULL, paper_finished_at = NULL")


def snaps(conn, strategy_id):
    return q(
        conn,
        "SELECT date, cash_usd, equity_usd FROM equity_snapshots WHERE strategy_id = %s ORDER BY date",
        (strategy_id,),
    )


def lifecycle(conn, strategy_id: str):
    """``(status, paper_end)`` of one strategies row."""
    return q(conn, "SELECT status, paper_end FROM strategies WHERE id = %s", (strategy_id,))[0]


def retire_by_hand(conn, strategy_id: str) -> None:
    """Retire without going through ``store.retire``: status only, paper_end left NULL.

    This is the plan index's Rollback-style hand SQL, and the case the night must repair.
    """
    with db.transaction(conn, False):
        conn.execute("UPDATE strategies SET status = 'retired' WHERE id = %s", (strategy_id,))


def make_unresolvable(conn, strategy_id: str) -> None:
    """Break ``strategy_id``'s name->object link in the database.

    The link is ``strategies.object_name`` (migration 006, phase 1) -- a column of its own, not
    ``params->'spec'->>'object'``, which is NULL until a strategy has been frozen. Setting it to a
    name ``roster.RESOLVER`` does not know is exactly the typo invariant 9 is about. The test below
    cannot pass silently if the break does not take: it asserts the night fails.
    """
    with db.transaction(conn, False):
        conn.execute(
            "UPDATE strategies SET object_name = 'NO_SUCH_OBJECT' WHERE id = %s",
            (strategy_id,),
        )


# ---- tests -----------------------------------------------------------------------------------


def test_paper_is_a_command():
    assert "paper" in cli.discover()


def test_first_night_starts_every_roster_strategy(world):
    assert night(world, N0) == 0
    usd = fx_rate(N0)
    assert usd != fx_rate(PAPER_START)  # the first paper day's own rate is not known yet
    cash0 = initial_cash_usd(INITIAL_IDR, usd)
    assert q(
        world,
        "SELECT strategy_id, last_session, cash_usd, equity_usd, initial_cash_usd, usd_idr, pending_session "
        "FROM paper_state ORDER BY strategy_id",
    ) == [(i, N0, cash0, cash0, cash0, usd, PAPER_START) for i in IDS]
    assert q(
        world,
        "SELECT id, paper_start, params->>'digest' FROM strategies WHERE id = ANY(%s) ORDER BY id",
        (list(IDS),),
    ) == [(i, PAPER_START, roster.strategy_params(ENTRIES[i])["digest"]) for i in IDS]
    assert q(world, "SELECT strategy_id, date, cash_usd, equity_usd FROM equity_snapshots ORDER BY strategy_id") == [
        (i, N0, cash0, cash0) for i in IDS
    ]
    # 2026-09-24 is no monthly decision, so every book strategy kicks off on it instead of waiting
    # for 2026-10-01 (paper.book.needs_kickoff); bracket and benchmark entries have no kickoff.
    books = sorted(i for i in IDS if ENTRIES[i].engine == "book")
    assert q(world, "SELECT strategy_id, pending_decision, kickoff_session FROM paper_state ORDER BY strategy_id") == [
        (i, i in books, PAPER_START if i in books else None) for i in IDS
    ]
    assert q(world, "SELECT count(*) FROM book_targets WHERE strategy_id = %s AND session_date = %s", (F1, PAPER_START)) == [
        (1,)
    ]
    assert q(world, "SELECT DISTINCT strategy_id, data_date FROM book_previews WHERE strategy_id = %s", (F1,)) == [
        (F1, N0)
    ]
    [(status, error, finished_at)] = paper_run(world, N0)
    assert status == "success" and error is None and finished_at is not None


def test_seven_nights_step_every_session_and_equal_the_runners(world, tmp_path):
    for d in NIGHTS:
        assert night(world, d) == 0
    assert q(world, "SELECT DISTINCT last_session, pending_session FROM paper_state") == [(OCT1, OCT2)]
    for i in IDS:
        assert [r[0] for r in snaps(world, i)] == list(NIGHTS)
    for d in NIGHTS:
        assert paper_run(world, d)[0][0] == "success"
    assert q(world, "SELECT count(*) FROM book_targets WHERE strategy_id = %s AND session_date = %s", (F1, OCT1)) == [
        (1,)
    ]
    assert q(world, "SELECT symbol FROM book_positions WHERE strategy_id = %s", (F1,)) == [("SPY",)]
    assert q(world, "SELECT symbol FROM book_positions WHERE strategy_id = 'SPY'") == [("SPY",)]

    [(usd, cash0)] = q(world, "SELECT usd_idr, initial_cash_usd FROM paper_state WHERE strategy_id = 'SPY'")
    market, _ = bio.load_market(world, cache_dir=tmp_path)
    spy = buy_and_hold(
        market.spy(), PAPER_START, OCT1, cash0, dividends=(Dividend(DIV_DATE, DIV_AMT),), name="spy_tr"
    )
    assert snaps(world, "SPY") == [(s.date, s.cash_usd, s.equity_usd) for s in spy.snapshots]
    for sid in (F4, F1):
        e = ENTRIES[sid]
        result = run_rules(
            market,
            e.obj,
            e.params,
            e.rules,
            PAPER_START,
            OCT1,
            dividends={"SPY": {DIV_DATE: DIV_AMT}},
            usd_idr=usd,
            kickoff=PAPER_START,
        )
        assert snaps(world, sid) == [(s.date, s.cash_usd, s.equity_usd) for s in result.snapshots]
        assert q(
            world, "SELECT symbol, shares FROM book_positions WHERE strategy_id = %s ORDER BY symbol", (sid,)
        ) == [(p.symbol, p.shares) for p in result.open_at_end]


def test_same_night_twice_writes_nothing(world):
    assert night(world, NIGHTS[0]) == 0
    assert night(world, NIGHTS[1]) == 0
    before = everything(world)
    assert night(world, NIGHTS[1]) == 0
    assert everything(world) == before


def test_weekend_run_is_a_no_op(world):
    for d in NIGHTS[:3]:  # through Friday 2026-09-25
        assert night(world, d) == 0
    before = everything(world)
    assert paper.execute(world, now=datetime(2026, 9, 26, 23, tzinfo=UTC)) == 0  # Saturday
    assert paper.execute(world, now=datetime(2026, 9, 27, 12, tzinfo=UTC)) == 0  # Sunday
    assert everything(world) == before


def test_catch_up_of_two_sessions_equals_night_by_night(world):
    for d in NIGHTS[:4]:
        assert night(world, d) == 0
    expected = content(world)
    reset(world)
    for d in NIGHTS[:2]:
        assert night(world, d) == 0
    bars_run(world, NIGHTS[2])  # the bars ran on 2026-09-25; its paper step did not
    assert go(world, NIGHTS[3]) == 0  # steps 2026-09-25 and 2026-09-28
    assert content(world) == expected
    assert paper_run(world, NIGHTS[2])[0][0] is None
    assert paper_run(world, NIGHTS[3])[0][0] == "success"


def test_failure_mid_night_leaves_no_partial_state_and_marks_failed(world, monkeypatch):
    for d in NIGHTS[:2]:
        assert night(world, d) == 0
    bars_run(world, NIGHTS[2])
    before = content(world)
    real = paper._step_book

    def boom(*args, **kwargs):
        real(*args, **kwargs)  # SPY, A and this book strategy have written by now
        raise RuntimeError("boom mid-night apiKey=sekret")

    monkeypatch.setattr(paper, "_step_book", boom)
    assert go(world, NIGHTS[2]) == 1
    assert content(world) == before
    [(status, error, finished_at)] = paper_run(world, NIGHTS[2])
    assert status == "failed" and finished_at is not None
    assert "boom mid-night" in error and "sekret" not in error

    monkeypatch.setattr(paper, "_step_book", real)
    assert go(world, NIGHTS[2]) == 0
    assert paper_run(world, NIGHTS[2])[0][:2] == ("success", None)


def test_no_paper_step_after_a_failed_or_missing_bars_run(world):
    before = everything(world)
    assert go(world, N0) == 1  # no runs row at all
    assert everything(world) == before
    bars_run(world, N0, status="failed")
    before = everything(world)
    assert go(world, N0) == 1
    assert everything(world) == before
    assert paper_run(world, N0) == [(None, None, None)]


def test_no_look_ahead(world):
    for d in NIGHTS[:6]:  # through the night of 2026-09-30, which decides 2026-10-01
        assert night(world, d) == 0
    expected = content(world)
    assert q(world, "SELECT count(*) FROM book_targets WHERE strategy_id = %s AND session_date = %s", (F1, OCT1)) == [
        (1,)
    ]
    reset(world)
    with db.transaction(world, False):  # rewrite everything dated on or after 2026-10-01
        world.execute(
            "UPDATE bars SET open = open * 0.5, high = high * 0.5, low = low * 0.5, close = close * 0.5 "
            "WHERE date >= %s",
            (OCT1,),
        )
        world.execute("UPDATE fx_rates SET usd_idr = 99999 WHERE date >= %s", (OCT1,))
        world.execute("INSERT INTO dividends (symbol, ex_date, amount) VALUES ('SPY', %s, 9)", (OCT2,))
    for d in NIGHTS[:6]:
        assert night(world, d) == 0
    assert content(world) == expected


def test_changed_frozen_spec_is_refused(world):
    assert night(world, N0) == 0
    with db.transaction(world, False):
        world.execute("UPDATE strategies SET params = jsonb_set(params, '{digest}', '\"0000\"') WHERE id = 'A'")
    before = content(world)
    assert night(world, NIGHTS[1]) == 1
    assert content(world) == before
    [(status, error, _)] = paper_run(world, NIGHTS[1])
    assert status == "failed" and "SpecMismatch: A: stored spec digest" in error and "new id" in error


def test_dry_run_writes_nothing(world):
    bars_run(world, N0)
    before = everything(world)
    assert go(world, N0, dry_run=True) == 0
    assert everything(world) == before
    assert go(world, N0) == 0
    bars_run(world, NIGHTS[1])
    before = everything(world)
    assert go(world, NIGHTS[1], dry_run=True) == 0
    assert everything(world) == before


# ---- the roster lifecycle (phase 2) -----------------------------------------------------------


def test_a_retired_strategy_is_skipped_and_keeps_its_history(world):
    from seer_engine.paper import store

    for d in NIGHTS[:3]:
        assert night(world, d) == 0
    before_a = {
        "snaps": snaps(world, "A"),
        "state": q(world, "SELECT * FROM paper_state WHERE strategy_id = 'A'"),
        "orders": q(world, "SELECT id FROM orders WHERE strategy_id = 'A' ORDER BY id"),
    }
    assert before_a["snaps"] and before_a["state"]
    last_traded = before_a["state"][0][1]

    with db.transaction(world, False):
        assert store.retire(world, "A") == last_traded
    assert lifecycle(world, "A") == ("retired", last_traded)

    assert night(world, NIGHTS[3]) == 0
    # A wrote nothing more: no snapshot, no order, no paper_state step.
    assert snaps(world, "A") == before_a["snaps"]
    assert q(world, "SELECT * FROM paper_state WHERE strategy_id = 'A'") == before_a["state"]
    assert q(world, "SELECT id FROM orders WHERE strategy_id = 'A' ORDER BY id") == before_a["orders"]
    assert lifecycle(world, "A") == ("retired", last_traded)
    # and every active strategy did step.
    for sid in IDS:
        if sid == "A":
            continue
        assert snaps(world, sid)[-1][0] == dates.run_dates(night_of(NIGHTS[3])).data_date
    assert paper_run(world, NIGHTS[3])[0][0] == "success"


def test_retiring_by_hand_stamps_paper_end_on_the_next_night(world, caplog):
    import logging

    for d in NIGHTS[:3]:
        assert night(world, d) == 0
    [(_, last_traded)] = q(
        world, "SELECT strategy_id, last_session FROM paper_state WHERE strategy_id = 'A'"
    )
    retire_by_hand(world, "A")
    assert lifecycle(world, "A") == ("retired", None)

    caplog.set_level(logging.INFO, logger="seer_engine.commands.paper")
    assert night(world, NIGHTS[3]) == 0
    assert lifecycle(world, "A") == ("retired", last_traded)
    assert "A: retired; no orders, no equity snapshot, no paper_state step" in caplog.text
    assert snaps(world, "A")[-1][0] == last_traded  # still no new snapshot


def test_a_stamped_retirement_leaves_later_nights_untouched(world):
    for d in NIGHTS[:3]:
        assert night(world, d) == 0
    retire_by_hand(world, "A")
    assert night(world, NIGHTS[3]) == 0  # stamps paper_end
    before = everything(world)
    assert night(world, NIGHTS[3]) == 0  # same night again: nothing left to do
    assert everything(world) == before


def test_a_retired_strategy_is_not_digest_checked_but_an_active_one_still_is(world):
    for d in NIGHTS[:2]:
        assert night(world, d) == 0
    with db.transaction(world, False):
        world.execute(
            "UPDATE strategies SET params = jsonb_set(params, '{digest}', '\"0000\"') WHERE id = 'A'"
        )
        world.execute(
            "UPDATE strategies SET params = jsonb_set(params, '{digest}', '\"0000\"') WHERE id = 'C'"
        )
    # C retired: its changed digest is never compared, because it takes no decision.
    retire_by_hand(world, "C")
    assert night(world, NIGHTS[2]) == 1  # A is still active, so SpecMismatch still stops the night
    [(status, error, _)] = paper_run(world, NIGHTS[2])
    assert status == "failed" and "SpecMismatch: A: stored spec digest" in error and "new id" in error
    # Put A back and the night runs, with C's bad digest still in the row and still unexamined.
    with db.transaction(world, False):
        world.execute(
            "UPDATE strategies SET params = jsonb_set(params, '{digest}', to_jsonb(%s::text)) WHERE id = 'A'",
            (roster.strategy_params(ENTRIES["A"])["digest"],),
        )
    assert go(world, NIGHTS[2]) == 0
    assert q(world, "SELECT params->>'digest' FROM strategies WHERE id = 'C'") == [("0000",)]


def test_an_active_strategy_with_no_paper_start_starts_on_the_next_night(world):
    # C is retired before the first night, so it never starts; it is reactivated three nights in.
    retire_by_hand(world, "C")
    for d in NIGHTS[:3]:
        assert night(world, d) == 0
    assert q(world, "SELECT count(*) FROM paper_state WHERE strategy_id = 'C'") == [(0,)]
    assert q(world, "SELECT paper_start FROM strategies WHERE id = 'C'") == [(None,)]

    with db.transaction(world, False):
        world.execute("UPDATE strategies SET status = 'active', paper_end = NULL WHERE id = 'C'")
    assert night(world, NIGHTS[3]) == 0

    start = session_of(NIGHTS[3])
    day0 = dates.run_dates(night_of(NIGHTS[3])).data_date
    assert q(world, "SELECT paper_start, params->>'digest' FROM strategies WHERE id = 'C'") == [
        (start, roster.strategy_params(ENTRIES["C"])["digest"])
    ]
    assert q(world, "SELECT last_session, pending_session FROM paper_state WHERE strategy_id = 'C'") == [
        (day0, start)
    ]
    assert [r[0] for r in snaps(world, "C")] == [day0]
    assert lifecycle(world, "C") == ("active", None)


def test_an_unresolvable_roster_entry_stops_the_night_and_is_not_a_skip(world):
    assert night(world, N0) == 0
    make_unresolvable(world, "A")
    before = content(world)
    assert night(world, NIGHTS[1]) == 1
    # Nothing of the night landed. `content` and not `everything` for the same reason
    # `test_changed_frozen_spec_is_refused` uses it: a deliberately failed night DOES write its
    # `runs` row (paper_status = failed + paper_error), which is the named stop, not a write.
    assert content(world) == before
    [(status, error, _)] = paper_run(world, NIGHTS[1])
    assert status == "failed"
    assert "A" in error and "NO_SUCH_OBJECT" in error
    # Invariant 9: a hard named error, never the deliberate skip a retired entry gets.
    assert "retired" not in error.lower() and "skip" not in error.lower()


# ---- pure helpers ----------------------------------------------------------------------------


def test_night_view_hides_later_bars_and_fx_and_undoes_later_splits():
    d1, d2, d3 = date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30)
    h = history_from_bars("X", [bars.make_bar("X", d, 10, 11, 9, 10, 1000) for d in (d1, d2, d3)])
    m = Market(
        history={"X": h},
        membership=Membership(intervals=()),
        fx=((d1, Decimal("16000.0000")), (d3, Decimal("17000.0000"))),
    )
    v = paper.night_view(m, d2, {"X": Decimal(2)})
    assert v.last_bar_date("X") == d2
    assert v.bar("X", d3) is None
    assert v.bar("X", d2) == Bar("X", d2, Decimal("20.0000"), Decimal("22.0000"), Decimal("18.0000"), Decimal("20.0000"), 500)
    assert v.usd_idr_on(d3) == Decimal("16000.0000")
    plain = paper.night_view(m, d3, {})
    assert plain.bar("X", d3).close == Decimal("10.0000") and plain.usd_idr_on(d3) == Decimal("17000.0000")


def test_later_factors_multiply_splits_after_the_session():
    d1, d2, d3 = date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30)
    by_session = {d2: (("X", Decimal(2)),), d3: (("X", Decimal(3)), ("Y", Decimal("0.5")))}
    assert paper.later_factors(by_session, d1) == {"X": Decimal(6), "Y": Decimal("0.5")}
    assert paper.later_factors(by_session, d2) == {"X": Decimal(3), "Y": Decimal("0.5")}
    assert paper.later_factors(by_session, d3) == {}
