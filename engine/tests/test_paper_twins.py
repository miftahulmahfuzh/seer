"""Claude twins on the paper night (plan seer-adversarial phase 2; contracts C2, C3; Decision D1).

The world is test_paper_command's synthetic market (24 random-walk stocks and SPY, bars through
2026-10-09) with a small set of originals active. Every night here runs `paper.execute` with the
twins ON, the CLI's default, so the twins are created, started and stepped as in production: one
session behind their originals. Verdict rows are inserted the way mcp-notes' writer inserts them.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_DOWN
from functools import lru_cache

import pytest
from psycopg.types.json import Jsonb

import test_paper_command as tp
from seer_engine import bars, dates, db, fx
from seer_engine.commands import explain, paper, paper_check
from seer_engine.paper import roster
from seer_engine.paper.capital import PAPER_INITIAL_IDR
from seer_engine.sim import initial_cash_usd, new_portfolio
from seer_engine.sim.book import WEIGHT_QUANTUM
from seer_engine.sim.sizing import size_picks
from seer_engine.strategies.a import STRATEGY_A, STRATEGY_A_PARAMS
from seer_engine.strategies.base import history_from_bars

UTC = timezone.utc
A, A_CX = "A", "A-CX"
RAW, RAW_CX = "RAW-FR", "RAW-FR-CX"
N = tp.NIGHTS  # 2026-09-23 .. 2026-10-01
OCT1, OCT2 = tp.OCT1, tp.OCT2
# A ranks META, PEP, HD, AAPL on AUG3 and can afford META and AAPL (whole shares, 10,000,000 IDR).
# Most nights of this synthetic market A can afford nothing, 2026-08-06 included.
AUG3, AUG4 = date(2026, 8, 3), date(2026, 8, 4)
# A buys WMT on several of these nights; it buys nothing during N.
A_TRADES = tuple(dates.sessions(date(2026, 9, 9), date(2026, 9, 17)))


# ---- the world ---------------------------------------------------------------------------------


def _world(pg, ids):
    with db.transaction(pg, False):
        pg.execute("UPDATE strategies SET status = 'retired'")
        pg.execute("UPDATE strategies SET status = 'active' WHERE id = ANY(%s)", (list(ids),))
        bars.upsert_bars(pg, tp.synthetic_bars())
        fx.upsert_fx(pg, [(d, tp.fx_rate(d)) for d in tp._sessions()])
        for s in tp.STOCKS:
            pg.execute(
                "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
                "VALUES (%s, 'SP500', '2020-01-02', NULL, %s)",
                (s, s),
            )
        pg.execute("INSERT INTO dividends (symbol, ex_date, amount) VALUES ('SPY', %s, %s)", (tp.DIV_DATE, tp.DIV_AMT))
    return pg


@pytest.fixture
def world(pg):
    """A bracket original, a book original and the benchmark."""
    return _world(pg, (A, RAW, "SPY"))


@pytest.fixture
def bracket_world(pg):
    return _world(pg, (A,))


@pytest.fixture
def book_world(pg):
    return _world(pg, (RAW,))


def night(conn, d: date, *, dry_run: bool = False) -> int:
    tp.bars_run(conn, d)
    return paper.execute(conn, now=tp.night_of(d), dry_run=dry_run)  # twins ON: the CLI's default


def nights(conn, ds) -> None:
    for d in ds:
        assert night(conn, d) == 0, f"paper failed on the night of {d}"


def verdict(conn, strategy_id: str, session: date, symbol: str, what: str, decided_at: datetime) -> int:
    """One adversary_verdicts row, shaped as mcp-notes' writer shapes it (migration 027)."""
    sources = [] if what == "unsure" else [{
        "url": "https://example.invalid/news",
        "title": "A test source",
        "publisher": "test",
        "published_at": None,
        "fetched_at": decided_at.isoformat(),
    }]
    with db.transaction(conn, False):
        (vid,) = conn.execute(
            "INSERT INTO adversary_verdicts (strategy_id, session_date, symbol, verdict, reason, sources, "
            "lens, model, prompt_version, host, started_at, decided_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                strategy_id, session, symbol, what, "A test verdict.", Jsonb(sources), "test@1",
                "test-model", "test-v1", "test-host", decided_at - timedelta(minutes=5), decided_at,
            ),
        ).fetchone()
    return vid


def supersede(conn, old: int, new: int) -> None:
    with db.transaction(conn, False):
        conn.execute("UPDATE adversary_verdicts SET superseded_by = %s WHERE id = %s", (new, old))


def state(conn, sid: str):
    return tp.q(conn, "SELECT last_session, pending_session FROM paper_state WHERE strategy_id = %s", (sid,))


def pending(conn, sid: str, session: date) -> list[str]:
    rows = tp.q(conn, "SELECT symbol FROM orders WHERE strategy_id = %s AND session_date = %s", (sid, session))
    return sorted(s for (s,) in rows)


def targets(conn, sid: str, session: date):
    return tp.q(
        conn, "SELECT symbol, weight FROM book_targets WHERE strategy_id = %s AND session_date = %s ORDER BY rank",
        (sid, session),
    )


def held(conn, sid: str) -> set[str]:
    return {s for (s,) in tp.q(conn, "SELECT symbol FROM book_positions WHERE strategy_id = %s", (sid,))}


def checked(conn):
    conn.rollback()
    return {r.strategy_id: r for r in paper_check.check(conn)}


DECISION = "session_date, symbol, shares, last_price, limit_price, tp_price, sl_price"
FILL = "session_date, seq, symbol, side, shares, price, cash_usd, cost_usd, reason"


def decisions(conn, sid: str, through: date):
    return tp.q(
        conn,
        f"SELECT {DECISION} FROM orders WHERE strategy_id = %s AND session_date <= %s ORDER BY session_date, symbol",
        (sid, through),
    )


def book_decisions(conn, sid: str, through: date):
    return tp.q(
        conn,
        "SELECT session_date, rank, symbol, weight FROM book_targets WHERE strategy_id = %s AND session_date <= %s "
        "ORDER BY session_date, rank",
        (sid, through),
    )


def fills(conn, sid: str, through: date):
    return tp.q(
        conn,
        f"SELECT {FILL} FROM book_fills WHERE strategy_id = %s AND session_date <= %s ORDER BY session_date, seq",
        (sid, through),
    )


# ---- creation and the lag ----------------------------------------------------------------------


def test_the_first_night_creates_a_twin_per_eligible_original_and_none_for_the_benchmark(world):
    assert night(world, N[0]) == 0
    rows = tp.q(
        world,
        "SELECT id, name, twin_of, status, paper_start, is_champion, is_benchmark, gate_applicable, gate_note, "
        "sort, engine, rules_id, object_name FROM strategies WHERE twin_of IS NOT NULL ORDER BY id",
    )
    originals = {
        r[0]: r
        for r in tp.q(
            world, "SELECT id, name, sort, engine, rules_id, object_name FROM strategies WHERE id = ANY(%s)", ([A, RAW],)
        )
    }
    assert [r[0] for r in rows] == [A_CX, RAW_CX]
    for r in rows:
        o = originals[r[2]]
        assert r[1] == roster.twin_name(o[1])
        assert r[3:9] == ("active", None, False, False, False, roster.TWIN_GATE_NOTE)
        assert r[9:] == o[2:]


def test_twins_start_one_night_later_and_stay_one_session_behind(world):
    nights(world, N[:2])
    assert tp.q(
        world, "SELECT id, paper_start FROM strategies WHERE id = ANY(%s) ORDER BY id", ([A, A_CX, RAW, RAW_CX],)
    ) == [(A, tp.PAPER_START), (A_CX, tp.PAPER_START), (RAW, tp.PAPER_START), (RAW_CX, tp.PAPER_START)]
    nights(world, N[2:])
    for orig, twin in ((A, A_CX), (RAW, RAW_CX)):
        assert state(world, orig) == [(N[-1], OCT2)]
        assert state(world, twin) == [(dates.prev_session(N[-1]), N[-1])]


def test_a_dry_run_night_creates_no_twin(world):
    assert night(world, N[0], dry_run=True) == 0
    assert tp.q(world, "SELECT count(*) FROM strategies WHERE twin_of IS NOT NULL") == [(0,)]


def test_twins_write_no_review_candidates(world):
    nights(world, N[:3])
    assert tp.q(
        world, "SELECT count(*) FROM strategy_candidates WHERE strategy_id = ANY(%s)", ([A_CX, RAW_CX],)
    ) == [(0,)]


# ---- no verdicts: the twin is its original -----------------------------------------------------


def test_a_twin_with_no_verdicts_trades_exactly_like_its_original(world):
    nights(world, A_TRADES)
    for orig, twin in ((A, A_CX), (RAW, RAW_CX)):
        [(last, _)] = state(world, twin)
        assert tp.snaps(world, twin) == [s for s in tp.snaps(world, orig) if s[0] <= last]
        assert tp.deposits(world, twin) == tuple(d for d in tp.deposits(world, orig) if d[0] <= last)
    [(_, a_pending)] = state(world, A_CX)
    assert decisions(world, A, a_pending), "A must have decided something for this to compare"
    assert decisions(world, A_CX, a_pending) == decisions(world, A, a_pending)
    [(r_last, r_pending)] = state(world, RAW_CX)
    assert book_decisions(world, RAW_CX, r_pending) == book_decisions(world, RAW, r_pending)
    assert fills(world, RAW_CX, r_last) == fills(world, RAW, r_last)
    found = checked(world)
    assert (found[A_CX].status, found[RAW_CX].status) == ("ok", "ok")


def test_a_twin_catching_up_equals_night_by_night(world):
    nights(world, N)
    by_night = tp.content(world)
    tp.reset(world)
    with db.transaction(world, False):
        world.execute("TRUNCATE strategy_candidates")  # phase 1's table; the second pass writes it again
    nights(world, (N[0], N[1], N[-1]))  # the twins start on N[1] both times, then catch up five sessions
    assert tp.content(world) == by_night


# ---- objections (bracket) ----------------------------------------------------------------------


@lru_cache(maxsize=1)
def ranked_aug4():
    """A's ranked picks for AUG4, computed without the database (the full history cut at AUG3)."""
    by_symbol = defaultdict(list)
    for b in tp.synthetic_bars():
        by_symbol[b.symbol].append(b)
    history = {s: history_from_bars(s, bs).upto(AUG3) for s, bs in by_symbol.items()}
    return tuple(STRATEGY_A.picks(history, frozenset(tp.STOCKS), AUG3, STRATEGY_A_PARAMS))


def sized(picks) -> list[str]:
    """What A's first decision buys from ``picks`` (fresh book, A's own rules)."""
    cash0 = initial_cash_usd(PAPER_INITIAL_IDR, tp.fx_rate(AUG3))
    placed = size_picks(new_portfolio(cash0), list(picks), AUG4, rules=tp.ENTRIES[A].rules).placed
    return sorted(o.symbol for o in placed)


def _first_bought(w) -> str:
    """A starts on AUG3 and decides AUG4; the best-ranked pick it bought."""
    assert night(w, AUG3) == 0
    orig = pending(w, A, AUG4)
    assert orig and orig == sized(ranked_aug4()), "A's own AUG4 decision is its ranked picks, sized"
    return next(p.symbol for p in ranked_aug4() if p.symbol in orig)


def test_an_objection_drops_exactly_that_pick_and_the_next_ranked_takes_its_slot(bracket_world):
    w = bracket_world
    x = _first_bought(w)
    verdict(w, A, AUG4, x, "object", datetime(2026, 8, 4, 12, tzinfo=UTC))  # before the 13:30 UTC open
    assert night(w, AUG4) == 0  # the twin starts and decides AUG4 from AUG3's bars
    twin = pending(w, A_CX, AUG4)
    assert twin == sized(p for p in ranked_aug4() if p.symbol != x)
    assert x not in twin and x in pending(w, A, AUG4)
    assert checked(w)[A_CX].status == "ok"


def test_a_verdict_decided_at_the_open_is_ignored(bracket_world):
    w = bracket_world
    x = _first_bought(w)
    verdict(w, A, AUG4, x, "object", datetime(2026, 8, 4, 13, 30, tzinfo=UTC))  # the open itself: late
    assert night(w, AUG4) == 0
    assert pending(w, A_CX, AUG4) == pending(w, A, AUG4)
    assert checked(w)[A_CX].status == "ok"


@pytest.mark.parametrize(("first", "second", "dropped"), [("object", "agree", False), ("agree", "object", True)])
def test_a_re_review_before_the_open_is_the_one_that_counts(bracket_world, first, second, dropped):
    w = bracket_world
    x = _first_bought(w)
    old = verdict(w, A, AUG4, x, first, datetime(2026, 8, 4, 11, tzinfo=UTC))
    new = verdict(w, A, AUG4, x, second, datetime(2026, 8, 4, 12, tzinfo=UTC))
    supersede(w, old, new)
    assert night(w, AUG4) == 0
    expected = sized(p for p in ranked_aug4() if p.symbol != x) if dropped else pending(w, A, AUG4)
    assert pending(w, A_CX, AUG4) == expected
    assert checked(w)[A_CX].status == "ok"


# ---- objections (book) -------------------------------------------------------------------------


def test_a_book_objection_drops_the_name_renormalises_pro_rata_and_sells_it_with_fees(book_world):
    w = book_world
    nights(w, N[:-1])  # through 2026-09-30: RAW-FR has decided OCT1 (a rank session); its twin has not
    orig = targets(w, RAW, OCT1)
    both = sorted(held(w, RAW) & {s for s, _ in orig})
    assert both, "RAW-FR keeps at least one held name at its October rank"
    h = both[0]
    verdict(w, RAW, OCT1, h, "object", datetime(2026, 10, 1, 12, tzinfo=UTC))  # before the 13:30 UTC open
    nights(w, (OCT1,))  # the twin settles 09-30 and decides OCT1 with the objection
    total = sum(wt for _, wt in orig)
    kept = [(s, wt) for s, wt in orig if s != h]
    kept_total = sum(wt for _, wt in kept)
    twin = targets(w, RAW_CX, OCT1)
    assert twin == [(s, (wt * total / kept_total).quantize(WEIGHT_QUANTUM, rounding=ROUND_DOWN)) for s, wt in kept]
    assert total - len(kept) * WEIGHT_QUANTUM <= sum(wt for _, wt in twin) <= total
    nights(w, (OCT2,))  # the twin settles OCT1: the objected held name is sold, and the sale pays fees
    sold = tp.q(
        w, "SELECT side, cost_usd FROM book_fills WHERE strategy_id = %s AND session_date = %s AND symbol = %s",
        (RAW_CX, OCT1, h),
    )
    assert sold and all(side == "sell" and cost > 0 for side, cost in sold)
    assert h not in held(w, RAW_CX) and h in held(w, RAW)
    assert checked(w)[RAW_CX].status == "ok"


# ---- lifecycle ---------------------------------------------------------------------------------


def test_retiring_an_original_retires_its_twin_on_the_next_night(world):
    nights(world, N[:3])
    [(twin_last, twin_pending)] = state(world, A_CX)
    tp.retire_by_hand(world, A)
    assert night(world, N[3]) == 0
    assert tp.lifecycle(world, A_CX) == ("retired", twin_last)
    assert state(world, A_CX) == [(twin_last, twin_pending)]  # retired before tonight stepped anything
    assert tp.lifecycle(world, RAW_CX)[0] == "active"


def test_a_retired_twin_of_an_active_original_stops_the_night_by_name(world):
    assert night(world, N[0]) == 0
    with db.transaction(world, False):
        world.execute("UPDATE strategies SET status = 'retired' WHERE id = %s", (A_CX,))
    assert night(world, N[1]) == 1
    [(status, error, _)] = tp.paper_run(world, N[1])
    assert status == "failed" and A_CX in error and "already exists" in error


# ---- explain -----------------------------------------------------------------------------------


def test_explain_never_reads_a_twins_decisions(world):
    nights(world, N[:2])  # the twins have just started: RAW-FR-CX holds kickoff targets, unexplained
    assert tp.q(
        world, "SELECT count(*) FROM book_targets WHERE strategy_id = %s AND session_date = %s", (RAW_CX, tp.PAPER_START)
    )[0][0] > 0
    ids = {s.id for s, _ in explain.load_batches(world)}
    world.rollback()
    assert ids.isdisjoint({A_CX, RAW_CX})
