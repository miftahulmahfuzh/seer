"""Strategy C on paper: `paper` decides it from stored verdicts, `paper_check` replays it, `explain`
covers it (PG; handover D6, D8; acceptance 1, 2, 3, 5).

The world is `test_paper_check`'s: 24 members on an 8-session sawtooth, so A has three picks every
night (fewer than C's cap of 10) and its trades close at tp. Verdict rows are written the way
`veto` writes them: `store.write_vetoes` for `run_dates(night).session_date`, one row per
`strategies.c.candidates` entry on the windowed market at the night's data date, ranks 1..n,
before `paper` runs. The test chooses each verdict.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta, timezone

import pytest
from psycopg.rows import tuple_row
from test_explain import FakeClient
from test_paper_check import HIST_START, MEMBERS, NIGHTS, SPY_DIVIDEND, SPY_EX_DATE, USD_IDR, synthetic_bars

from seer_engine import bars, dates, db, fx
from seer_engine.commands import explain, paper, paper_check
from seer_engine.paper import replay, roster, store
from seer_engine.strategies.a import STRATEGY_A
from seer_engine.strategies.c import FROZEN_MODEL, PROMPT_VERSION, STRATEGY_C_PARAMS, NewsVeto, candidates

UTC = timezone.utc
C = "C"
FOUR = ("SPY", "A", "F4-MOM12-N20-TREND-FR", "F1-SPY-SMA200-M-FR")  # the active book pair since 010
ALL = FOUR + (C,)

# (session, rank, symbol) -> the stored verdict, or None for no row. Only a tail of the ranked
# list may be left without a row (write_vetoes takes ranks 1..n).
Choose = Callable[[date, int, str], str | None]


def allow_all(session: date, rank: int, symbol: str) -> str | None:
    return "allow"


def mixed(session: date, rank: int, symbol: str) -> str | None:
    """Rank 2 vetoed, rank 3 failed, the rest allowed: C buys a strict subset of A's list."""
    return {2: "veto", 3: "failed"}.get(rank, "allow")


def four_only() -> tuple[roster.RosterEntry, ...]:
    """The roster as it was before C landed: the four frozen entries, in order."""
    return tuple(e for e in roster.ROSTER if e.id != C)


def hide_c(conn) -> str:
    """Take C off the DATABASE roster and return the ``engine`` it had, so it can land again.

    Since phase 2 the night and the replay resolve their entries from
    ``store.read_roster_rows(conn)`` -- every ``strategies`` row with an ``engine`` -- so
    monkeypatching ``roster.ROSTER`` no longer hides a strategy from a night. Clearing C's
    ``engine`` is ``four_only()`` at the data layer, and it is literally C's row before migration
    004 gave it one: the state these tests call "before C landed".
    """
    [(engine,)] = q(conn, "SELECT engine FROM strategies WHERE id = %s", (C,))
    assert engine is not None
    with db.transaction(conn, False):
        conn.execute("UPDATE strategies SET engine = NULL WHERE id = %s", (C,))
    return engine


def land_c(conn, engine: str) -> None:
    """C joins the database roster: the other half of ``hide_c``."""
    with db.transaction(conn, False):
        conn.execute("UPDATE strategies SET engine = %s WHERE id = %s", (engine, C))


# ---- the world and the night -------------------------------------------------------------------


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


def night_of(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 23, tzinfo=UTC)


def session_of(d: date) -> date:
    return dates.run_dates(night_of(d)).session_date


def bars_run(conn, d: date) -> None:
    """The real runs row a successful bars run writes for the night of ``d``."""
    rd = dates.run_dates(night_of(d))
    with db.transaction(conn, False):
        conn.execute(
            """
            INSERT INTO runs (status, data_date, session_date, is_demo, finished_at)
            VALUES ('success', %s, %s, false, now())
            ON CONFLICT (session_date) WHERE NOT is_demo DO NOTHING
            """,
            (rd.data_date, rd.session_date),
        )


def _market(conn, d: date):
    rd = dates.run_dates(night_of(d))
    try:
        return rd, store.load_market_window(conn, store.market_window_since(rd.data_date))
    finally:
        conn.rollback()


def ranked(conn, d: date) -> list[str]:
    """C's candidates for the night of ``d`` as `veto` computes them (rank order)."""
    rd, market = _market(conn, d)
    members = market.membership.members_on(rd.data_date)
    return [p.symbol for p in candidates(market.history, members, rd.data_date, STRATEGY_C_PARAMS)]


def a_picks(conn, d: date) -> list[str]:
    """A's whole ranked list for the night of ``d`` (no cap)."""
    rd, market = _market(conn, d)
    cut = {s: h.upto(rd.data_date) for s, h in market.history.items()}
    members = market.membership.members_on(rd.data_date)
    return [p.symbol for p in STRATEGY_A.picks(cut, members, rd.data_date, STRATEGY_C_PARAMS.a)]


def veto(conn, d: date, choose: Choose) -> dict[str, str]:
    """The verdict rows `veto` stores on the night of ``d``; returns {symbol: verdict} written."""
    session = session_of(d)
    rows: list[store.NewsVerdict] = []
    for rank, symbol in enumerate(ranked(conn, d), start=1):
        verdict = choose(session, rank, symbol)
        if verdict is None:
            continue
        rows.append(
            store.NewsVerdict(
                rank=rank,
                symbol=symbol,
                verdict=verdict,
                reason=f"test verdict {verdict} for {symbol}",
                model=FROZEN_MODEL,
                prompt_version=PROMPT_VERSION,
                headlines=(),
                earnings_date=None,
                decided_at=night_of(d) - timedelta(minutes=30),
            )
        )
    if rows:
        with db.transaction(conn, False):
            assert not store.has_vetoes(conn, C, session)
            assert store.write_vetoes(conn, C, session, rows) == len(rows)
    return {r.symbol: r.verdict for r in rows}


def go(conn, d: date, *, dry_run: bool = False) -> int:
    return paper.execute(conn, now=night_of(d), dry_run=dry_run)


def night(conn, d: date, choose: Choose | None = allow_all) -> dict[str, str]:
    """A whole night: the bars run, `veto` (``choose`` None: the step did not run), `paper`."""
    bars_run(conn, d)
    written = {} if choose is None else veto(conn, d, choose)
    assert go(conn, d) == 0, f"paper failed on the night of {d}"
    return written


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


ORDER_COLS = (
    "session_date, slot, symbol, last_price, limit_price, tp_price, sl_price, shares, status, fill_date, "
    "fill_price, days_held, exit_date, exit_price, exit_reason, pnl_usd, mark"
)


def orders(conn, sid: str):
    return q(conn, f"SELECT {ORDER_COLS} FROM orders WHERE strategy_id = %s ORDER BY session_date, slot", (sid,))


def pending(conn, sid: str, session: date) -> list[str]:
    rows = q(
        conn,
        "SELECT symbol FROM orders WHERE strategy_id = %s AND session_date = %s ORDER BY slot",
        (sid, session),
    )
    return [r[0] for r in rows]


def snaps(conn, sid: str):
    return q(conn, "SELECT date, cash_usd, equity_usd FROM equity_snapshots WHERE strategy_id = %s ORDER BY date", (sid,))


def state(conn, sid: str):
    return q(
        conn,
        "SELECT last_session, cash_usd, equity_usd, initial_cash_usd, pending_session, pending_decision "
        "FROM paper_state WHERE strategy_id = %s",
        (sid,),
    )


# Whole rows of every table `paper` writes (ids and timestamps included), and the verdicts.
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
    "news_vetoes": "strategy_id, session_date, rank",
}


def everything(conn):
    return {t: q(conn, f"SELECT x::text FROM {t} x ORDER BY {order}") for t, order in EVERYTHING.items()}


# Paper content without ids or timestamps. `orders.id` and `book_*.id` are shared sequences, so a
# strategy's ids move when another strategy's rows interleave with its own; nothing else may move.
CONTENT = {
    "paper_state": "strategy_id, last_session, cash_usd, equity_usd, initial_cash_usd, usd_idr, pending_session, "
    "pending_decision",
    "book_positions": "*",
    "book_targets": "*",
    "book_fills": "strategy_id, session_date, seq, symbol, side, shares, price, cash_usd, cost_usd, reason",
    "book_trades": "strategy_id, symbol, entry_date, exit_date, entry_price, exit_price, days_held, cost_usd, "
    "income_usd, pnl_usd, exit_reason, idle",
    "orders": f"strategy_id, company, explanation, {ORDER_COLS}",
    "equity_snapshots": "*",
    "strategies": "id, paper_start, params",
}


def content(conn, ids: Sequence[str]):
    """``CONTENT`` of the strategies ``ids``, each table's rows sorted by their text."""
    out = {}
    for table, cols in CONTENT.items():
        key = "id" if table == "strategies" else "strategy_id"
        rows = q(conn, f"SELECT {cols} FROM {table} WHERE {key} = ANY(%s)", (list(ids),))
        out[table] = sorted(rows, key=str)
    return out


def reset(conn) -> None:
    """The runbook's paper-clock reset for every strategy; bars, runs rows and verdicts stay."""
    with db.transaction(conn, False):
        conn.execute(
            "TRUNCATE paper_state, book_positions, book_targets, book_fills, book_trades, "
            "action_dismissals, orders, equity_snapshots RESTART IDENTITY"
        )
        conn.execute("UPDATE strategies SET paper_start = NULL, params = '{}'::jsonb")
        conn.execute("UPDATE runs SET paper_status = NULL, paper_error = NULL, paper_finished_at = NULL")


# ---- the world: C's cap of 10 never binds ------------------------------------------------------


def test_a_has_at_most_ten_picks_every_night_so_c_candidates_are_all_of_them(world):
    assert isinstance(roster.entry(C).obj, NewsVeto)
    for d in NIGHTS:
        picks = a_picks(world, d)
        assert 1 <= len(picks) <= STRATEGY_C_PARAMS.max_candidates, f"A has {len(picks)} picks on {d}"
        assert ranked(world, d) == picks


# ---- C's clock ---------------------------------------------------------------------------------


def test_c_starts_on_its_first_night_with_its_own_paper_start(world, monkeypatch):
    monkeypatch.setattr(roster, "ROSTER", four_only())
    c_engine = hide_c(world)
    for d in NIGHTS[:3]:  # before C landed
        night(world, d, None)
    monkeypatch.undo()
    land_c(world, c_engine)
    # C is back on the roster. It is no longer the LAST entry -- FND joined at sort 6 in
    # roster-promotion-pipeline phase 6 -- and what this line checks is that it is on it.
    assert C in roster.ROSTER_IDS
    for d in NIGHTS[3:]:
        night(world, d, allow_all)

    four_start, c_start = session_of(NIGHTS[0]), session_of(NIGHTS[3])
    assert q(world, "SELECT id, paper_start FROM strategies WHERE id = ANY(%s) ORDER BY id", (list(ALL),)) == sorted(
        [*[(i, four_start) for i in FOUR], (C, c_start)]
    )
    entry = roster.entry(C)
    assert q(world, "SELECT params->>'digest', params->'backtest_gate' FROM strategies WHERE id = %s", (C,)) == [
        (roster.strategy_params(entry)["digest"], roster.backtest_gate(entry))
    ]
    assert [r[0] for r in snaps(world, C)] == list(NIGHTS[3:])  # day 0 is the night it started
    assert [r[0] for r in snaps(world, "A")] == list(NIGHTS)

    found = results(world)
    for sid in ALL:
        assert found[sid].status == "ok", text(found)
    assert (found[C].paper_start, found[C].sessions) == (c_start, len(NIGHTS) - 4)
    assert (found["A"].paper_start, found["A"].sessions) == (four_start, len(NIGHTS) - 1)


# ---- same path: >= 5 nights replay from stored verdicts; all-allow equals A --------------------


def test_eight_mixed_nights_equal_the_replay_from_stored_verdicts(world):
    stored = [night(world, d, mixed) for d in NIGHTS]
    assert all({"allow", "veto", "failed"} <= set(s.values()) for s in stored)

    found = results(world)
    for sid in ALL:
        assert found[sid].status == "ok", text(found)
    assert found[C].sessions == len(NIGHTS) - 1 >= 5
    assert paper_check.execute(world, require_sessions=len(NIGHTS) - 1) == 0
    for status in ("closed", "pending"):  # not vacuous: C traded and has a pending decision
        assert q(world, "SELECT count(*) FROM orders WHERE strategy_id = %s AND status = %s", (C, status))[0][0] >= 1
    allowed = set(q(world, "SELECT session_date, symbol FROM news_vetoes WHERE verdict = 'allow'"))
    placed = {(r[0], r[2]) for r in orders(world, C)}
    assert placed and placed <= allowed  # every order C placed had an `allow` verdict for its session
    assert {(r[0], r[2]) for r in orders(world, "A")} - placed  # and the veto kept C out of some of A's


def test_replay_reads_the_stored_verdicts(world):
    for d in NIGHTS:
        night(world, d, mixed)
    [(session, symbol)] = q(
        world,
        "SELECT session_date, symbol FROM orders WHERE strategy_id = %s AND status = 'closed' "
        "ORDER BY session_date, slot LIMIT 1",
        (C,),
    )
    with db.transaction(world, False):  # the verdict that let that trade through, now a veto
        world.execute(
            "UPDATE news_vetoes SET verdict = 'veto' WHERE strategy_id = %s AND session_date = %s AND symbol = %s",
            (C, session, symbol),
        )
    found = results(world)
    assert found[C].status == "mismatch", text(found)
    for sid in FOUR:
        assert found[sid].status == "ok", text(found)
    assert paper_check.execute(world) == 1


def test_all_allow_c_trades_exactly_like_a(world):
    for d in NIGHTS:
        night(world, d, allow_all)
    assert orders(world, C) == orders(world, "A")
    assert {r[8] for r in orders(world, C)} >= {"closed", "open", "pending"}
    assert snaps(world, C) == snaps(world, "A")
    assert state(world, C) == state(world, "A")
    found = results(world)
    assert found[C].status == "ok", text(found)


# ---- failure = no trade, never a failed night --------------------------------------------------


@pytest.mark.parametrize(
    ("verdicts", "bought"),
    [
        pytest.param({1: "veto", 2: "allow", 3: "allow"}, (1, 2), id="veto"),
        pytest.param({1: "failed", 2: "allow", 3: "allow"}, (1, 2), id="failed"),
        pytest.param({1: "allow", 2: "allow"}, (0, 1), id="missing"),
    ],
)
def test_veto_failed_or_missing_verdict_is_no_order_and_paper_exits_zero(world, verdicts, bought):
    first = NIGHTS[0]
    want = ranked(world, first)
    assert len(want) == 3
    bars_run(world, first)
    veto(world, first, lambda s, rank, sym: verdicts.get(rank))
    assert go(world, first) == 0
    start = session_of(first)
    assert pending(world, "A", start) == want  # A buys all three
    assert pending(world, C, start) == [want[i] for i in bought]
    assert q(world, "SELECT paper_status FROM runs WHERE session_date = %s AND NOT is_demo", (start,)) == [
        ("success",)
    ]


def test_a_night_without_verdicts_buys_nothing_for_c_only(world):
    night(world, NIGHTS[0], None)  # the veto step never ran (no keys, crashed, timed out)
    start = session_of(NIGHTS[0])
    assert pending(world, C, start) == []
    assert pending(world, "A", start) == ranked(world, NIGHTS[0])
    night(world, NIGHTS[1], allow_all)  # the next night it ran: C buys from then on
    assert pending(world, C, session_of(NIGHTS[1])) != []
    found = results(world)
    for sid in ALL:
        assert found[sid].status == "ok", text(found)


# ---- catch-up and idempotency ------------------------------------------------------------------


def test_catch_up_uses_verdicts_of_the_newest_session_only(world):
    # Night by night, with the veto step missing on NIGHTS[2].
    for d in NIGHTS[:2]:
        night(world, d, allow_all)
    night(world, NIGHTS[2], None)
    night(world, NIGHTS[3], allow_all)
    expected = content(world, ALL)
    assert pending(world, C, session_of(NIGHTS[2])) == []

    # The same as a catch-up: the bars ran on NIGHTS[2], veto and paper did not; on NIGHTS[3]
    # veto wrote verdicts for that night's session only and paper steps two sessions at once.
    reset(world)
    for d in NIGHTS[:2]:
        assert go(world, d) == 0  # their verdicts are stored already
    assert go(world, NIGHTS[3]) == 0
    assert content(world, ALL) == expected
    assert pending(world, C, session_of(NIGHTS[3])) != []
    assert q(world, "SELECT count(*) FROM news_vetoes WHERE session_date = %s", (session_of(NIGHTS[2]),)) == [(0,)]
    found = results(world)
    for sid in ALL:
        assert found[sid].status == "ok", text(found)


def test_paper_rerun_writes_nothing(world):
    night(world, NIGHTS[0], mixed)
    night(world, NIGHTS[1], mixed)
    before = everything(world)
    assert go(world, NIGHTS[1]) == 0
    assert go(world, NIGHTS[1], dry_run=True) == 0
    assert everything(world) == before


# ---- non-regression: the four frozen strategies never see C ------------------------------------


def test_the_four_strategies_rows_are_identical_with_or_without_c(world, monkeypatch):
    monkeypatch.setattr(roster, "ROSTER", four_only())
    c_engine = hide_c(world)
    for d in NIGHTS:
        night(world, d, None)
    four_alone = content(world, FOUR)
    assert q(world, "SELECT count(*) FROM paper_state WHERE strategy_id = %s", (C,)) == [(0,)]
    assert q(world, "SELECT count(*) FROM orders WHERE strategy_id = %s", (C,)) == [(0,)]
    monkeypatch.undo()
    land_c(world, c_engine)

    reset(world)
    for d in NIGHTS:  # the same nights with C on the roster, trading from stored verdicts
        veto(world, d, mixed)
        assert go(world, d) == 0
    assert q(world, "SELECT count(*) FROM orders WHERE strategy_id = %s", (C,))[0][0] >= 1
    assert content(world, FOUR) == four_alone  # orders, snapshots, book rows, state, frozen specs


# ---- explain covers C --------------------------------------------------------------------------


def test_explain_fills_c_pending_orders_like_a(world):
    for d in NIGHTS[:3]:
        night(world, d, allow_all)
    session = session_of(NIGHTS[2])
    c_pending = pending(world, C, session)
    assert c_pending
    client = FakeClient()
    assert explain.execute(world, client=client) == 0
    notes = dict(
        q(world, "SELECT symbol, explanation FROM orders WHERE strategy_id = %s AND session_date = %s", (C, session))
    )
    assert notes == {s: f"Paper note for {s}." for s in c_pending}
    assert sum("Method: News veto," in p for p in client.prompts) == len(c_pending)
    again = FakeClient()
    assert explain.execute(world, client=again) == 0
    assert again.prompts == []


# ---- the helper ------------------------------------------------------------------------------


def test_bracket_strategy_carries_verdicts_for_c_only(world):
    first = NIGHTS[0]
    s = session_of(first)
    a = roster.entry("A")
    assert paper._bracket_strategy(world, a, s, s) is a.obj
    c = roster.entry(C)
    assert dict(paper._bracket_strategy(world, c, s, s).allowed) == {}  # no rows: buys nothing
    veto(world, first, mixed)
    want = ranked(world, first)
    carried = paper._bracket_strategy(world, c, s, dates.next_session(s))
    assert isinstance(carried, NewsVeto) and carried is not c.obj
    assert dict(carried.allowed) == {s: frozenset({want[0]})}
    assert dict(c.obj.allowed) == {}  # the roster object itself never changes
    world.rollback()
