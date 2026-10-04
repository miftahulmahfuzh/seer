> Adopted from `STRATEGY_C_NEWS_VETO_PLAN.md` phase 5. Source: `.workflows/plan/strategy-c-news-veto/phase-5.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 5: `paper`, `paper_check`, `explain` decide and replay C

**Plan set:** `STRATEGY_C_NEWS_VETO_PLAN.md`
**Analysis:** `20261004-171449-C5V8_code_analyzer.md`
**Satisfies:** R2 — `paper` deciding C from stored verdicts, `paper_check` replaying C (D8), `explain` covering C
**Depends on:** Phase 2 (and, through it, Phase 1)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/commands`

---

## Goal

After this phase the nightly `paper` step buys for C only the candidates whose stored `news_vetoes`
verdict for that session is `allow` (veto, failed or no row = no trade, never a failed night), using
the same `decide_bracket` path as A, and `paper_check` replays C with `run_rules(DESIGN_V0)` from the
same stored verdicts, read in its read-only transaction. A new PG test module proves the acceptance
list: C's own clock, ≥ 5 nights replay-ok, all-allow C == A, failure = no trade, catch-up, idempotent
re-run, non-regression of the four frozen strategies, and `explain` filling C's pending orders.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `seer_engine.commands.paper._bracket_strategy(conn: psycopg.Connection, e: RosterEntry, first: date, last: date) -> Strategy` (`commands/paper.py`, new function placed directly above `_start`).
- `engine/tests/test_paper_c.py` (new test module, 14 tests).
**Signature changes:**
- `commands.paper_check._expected(entry, head, market, dividends)` -> `_expected(conn, entry, head, market, dividends)` (private; one caller, `_check`, updated here).
- `commands.paper._step_bracket` keeps its signature; it now returns early when `sessions` is empty (never happens from `_night`, which only steps entries with `last_session < rd.data_date`).
**New imports:** `commands/paper.py` imports `Strategy` from `strategies.base` and `NewsVeto` from `strategies.c`; `commands/paper_check.py` imports `dates` and `commands.paper._bracket_strategy` (one helper shared by the live path and the replay, so they cannot disagree on which sessions' verdicts count).
**Requires (from earlier phases):**
- K1 (Phase 1): `strategies.c.NewsVeto` with `.allowed`, `.with_allowed(Mapping[date, frozenset[str]]) -> NewsVeto` (returns a new object; the roster's `STRATEGY_C` is never mutated), `.picks` looking up `allowed.get(next_session(data_date), frozenset())`; `candidates(history, members, data_date, params)`; `STRATEGY_C_PARAMS` with `.a` and `.max_candidates == 10`; `FROZEN_MODEL`, `PROMPT_VERSION`.
- K2 (Phase 2): `db/migrations/004_news_veto.sql` (table `news_vetoes`, row `C` in `strategies`), applied by the `pg` fixture (it applies every `db/migrations/*.sql`).
- K3 (Phase 2): `store.NewsVerdict`, `store.has_vetoes`, `store.write_vetoes` (accepts ranks 1..n for n ≤ the candidate count; the tests only ever omit a *tail* of the ranked list), `store.allowed_between(conn, strategy_id, start, end) -> dict[date, frozenset[str]]` (inclusive, `allow` only).
- K4 (Phase 2): `roster.ROSTER` ends with entry `C` (`engine="bracket"`, `obj=STRATEGY_C`, `params=STRATEGY_C_PARAMS`, `name="C · News veto"`); `roster.entry("C")`; `roster.backtest_gate(e)`.
- **Phase 2 owns** the one-line `engine/tests/test_paper_check.py:51` edit (`ROSTER_IDS = ("SPY", "A", F4, F1, "C")`) and the `engine/tests/test_paper_store.py:58` edit (`read_strategies` returns five rows, `"C"` last), so Phase 2 lands green on its own (reconciliation decision). This phase starts from those files **as Phase 2 leaves them** and edits neither. After Phase 2, `test_paper_check.py:51` reads:
  ```python
  ROSTER_IDS = ("SPY", "A", F4, F1, "C")
  ```
  and `test_paper_store.py:58` reads:
  ```python
      assert [r.id for r in rows] == ["SPY", "A", BOOK_ID, TIMING_ID, "C"]
  ```
- Test helpers this phase imports and never renames: `test_paper_check.HIST_START, MEMBERS, NIGHTS, SPY_DIVIDEND, SPY_EX_DATE, USD_IDR, synthetic_bars`, `test_explain.FakeClient`. Phase 4 imports `test_paper_command.synthetic_bars, fx_rate, _sessions, STOCKS`; this phase does not edit `test_paper_command.py`.
**Leaves alone (owned by others):** `paper/bracket.py`, `paper/replay.py`, `paper/book.py`, `paper/benchmark.py`, `paper/store.py`, `paper/roster.py`, `demo.py`, `db/migrations/*` (Phase 2 / closed records); `strategies/c.py` (Phase 1); `commands/veto.py` (Phase 4); `commands/explain.py` (no change, K7); `llm.py`, `finnhub.py` (Phase 3); `web/**` (Phase 6); workflows and docs (Phase 7).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/commands/paper.py` | modify | docstring paragraph on C (`:31`); imports (`:57`); new `_bracket_strategy` above `_start` (`:351`); `_start` bracket branch uses it (`:386`); `_step_bracket` builds the strategy once per run (`:404-410`) |
| `engine/src/seer_engine/commands/paper_check.py` | modify | docstring (`:5-11`); imports (`:27-29`); `_check` passes `conn` to `_expected` (`:161`); `_expected` takes `conn` and builds C's verdict-carrying object (`:218-220`) |
| `engine/tests/test_paper_c.py` | create | the acceptance tests (14) on the `test_paper_check` world, verdict rows via `store.write_vetoes` |

`engine/tests/test_paper_check.py` and `engine/tests/test_paper_store.py` are **not** edited here: Phase 2 owns
their one-line `"C"` edits (see Requires).

`commands/explain.py`, `tests/test_paper_command.py`, `tests/test_explain.py`: **no change**. The
existing `test_paper_command.py` derives its ids from `roster.ROSTER` and passes unchanged with C
on the roster (verified in scratch: C starts with the others, places no order without verdicts);
`test_explain.py` seeds only the four strategies' rows. The explain-covers-C proof lives in
`test_paper_c.py` (it needs real C orders, which need the `world` and verdicts).

## Implementation Steps

Line numbers are the current file (`d9cecce`); Phases 1–2 do not touch these two files.

### Step 1: `paper.py` — module docstring
**File:** `engine/src/seer_engine/commands/paper.py:31`
**Change:** insert a paragraph before the existing final paragraph ("Trade logic lives in ...").
Replace

```python
Trade logic lives in ``paper.bracket``, ``paper.book`` and ``paper.benchmark`` (pure), and all
persistence in ``paper.store``; this module only sequences them.
"""
```

with

```python
Strategy C (``strategies.c.NewsVeto``) is decided like A, by ``decide_bracket``, on a copy of
its roster object that carries the verdicts ``veto`` stored for the sessions being decided
(``store.allowed_between``): only a symbol whose stored verdict is ``allow`` can be bought; a
``veto``, a ``failed`` verdict or no row at all is no trade (design §8). ``paper`` never calls the
network and never fails because of C's verdicts.

Trade logic lives in ``paper.bracket``, ``paper.book`` and ``paper.benchmark`` (pure), and all
persistence in ``paper.store``; this module only sequences them.
"""
```
**Impact:** none (text).

### Step 2: `paper.py` — imports, the helper, `_start`, `_step_bracket`
**File:** `engine/src/seer_engine/commands/paper.py:57`
**Change (imports):** replace

```python
from seer_engine.strategies.base import History
```

with

```python
from seer_engine.strategies.base import History, Strategy
from seer_engine.strategies.c import NewsVeto
```

(`strategies.c` is pure and imports only `strategies.a`, `dates` and the stdlib per K1, so no cycle.)

**File:** `engine/src/seer_engine/commands/paper.py:351` (directly above `def _start`)
**Change (new helper):** insert

```python
def _bracket_strategy(conn: psycopg.Connection, e: RosterEntry, first: date, last: date) -> Strategy:
    """The strategy object ``decide_bracket`` gets for ``e`` when it decides sessions ``first`` ..
    ``last`` (inclusive).

    Every bracket entry but C: ``e.obj`` unchanged. C (a ``NewsVeto``): ``e.obj`` carrying the
    ``allow`` verdicts stored for those sessions (``store.allowed_between``), so a candidate with
    a ``veto`` or ``failed`` verdict, or with no verdict row, is not bought (handover D6, D8).
    """
    if not isinstance(e.obj, NewsVeto):
        return e.obj
    return e.obj.with_allowed(store.allowed_between(conn, e.id, first, last))
```

**File:** `engine/src/seer_engine/commands/paper.py:384-391` (`_start`, bracket branch)
**Change:** replace

```python
        sized = decide_bracket(
            new_portfolio(cash0),
            e.obj,
            e.params,
```

with

```python
        sized = decide_bracket(
            new_portfolio(cash0),
            _bracket_strategy(conn, e, paper_start, paper_start),
            e.params,
```

(`decide_bracket` here decides `next_session(rd.data_date) == rd.session_date == paper_start`.)

**File:** `engine/src/seer_engine/commands/paper.py:404-414` (`_step_bracket`)
**Change:** replace the whole function with

```python
def _step_bracket(conn: psycopg.Connection, e: RosterEntry, sessions: Sequence[date], tonight: _Tonight) -> None:
    pf = store.load_portfolio(conn, e.id)
    if not sessions:
        return
    strategy = _bracket_strategy(conn, e, dates.next_session(sessions[0]), dates.next_session(sessions[-1]))
    for s in sessions:
        view = tonight.view(s)
        night = settle_bracket(pf, s, view.bars_on(s, pf.held_symbols()), tonight.splits_on(s), view.last_bar_date)
        store.save_bracket_night(conn, e.id, night.portfolio, night.events, night.snapshot)
        sized = decide_bracket(night.portfolio, strategy, e.params, view.history, view.membership.members_on(s), s)
        store.insert_pending_orders(conn, e.id, sized.placed)
        store.write_pending(conn, e.id, dates.next_session(s), decision=False)
        pf = sized.portfolio
        log.info("%s %s: equity %s, %d live order(s)", e.id, s, pf.equity, len(pf.orders))
```

**Impact:** for A (and any non-`NewsVeto` bracket entry) `strategy is e.obj`: byte-identical
behaviour, no extra query. For C: one `SELECT` on `news_vetoes` per night inside the existing paper
transaction (read only; `--dry-run` still rolls everything back). A catch-up night reads the
verdicts of every session it decides; sessions with no rows map to nothing, so C sits them out
(handover §6 recommendation). `paper` cannot fail because of verdicts: no rows is just an empty map.

### Step 3: `paper_check.py` — replay C from stored verdicts
**File:** `engine/src/seer_engine/commands/paper_check.py:5-11` (module docstring)
**Change:** replace

```python
For every roster strategy with a paper start, replay it from ``paper_start`` through its last
stepped session on the bars in the database and compare every stored record with the replay
(``paper.replay``): every ``equity_snapshots`` row from day 0; A's every ``orders`` row and open
marks; the book strategies' ``book_positions``, ``book_fills`` (in order), ``book_trades`` (in
order) and every stored ``book_targets`` decision; the benchmark's SPY holding; ``paper_state``.

Read-only: everything is read in one REPEATABLE READ, READ ONLY transaction that is rolled back,
```

with

```python
For every roster strategy with a paper start, replay it from ``paper_start`` through its last
stepped session on the bars in the database and compare every stored record with the replay
(``paper.replay``): every ``equity_snapshots`` row from day 0; A's and C's every ``orders`` row and
open marks; the book strategies' ``book_positions``, ``book_fills`` (in order), ``book_trades`` (in
order) and every stored ``book_targets`` decision; the benchmark's SPY holding; ``paper_state``.

C is replayed from the verdicts ``veto`` stored (``news_vetoes``), read in the same transaction;
the LLM is never asked again (handover D8): only ``allow`` verdicts can be bought, a ``veto``,
``failed`` or missing verdict is no trade, exactly as ``paper`` decided it.

Read-only: everything is read in one REPEATABLE READ, READ ONLY transaction that is rolled back,
```

**File:** `engine/src/seer_engine/commands/paper_check.py:27-29` (imports)
**Change:** replace

```python
from seer_engine import db
from seer_engine.backtest.book_runner import DividendMap
from seer_engine.backtest.market import Market
```

with

```python
from seer_engine import dates, db
from seer_engine.backtest.book_runner import DividendMap
from seer_engine.backtest.market import Market
from seer_engine.commands.paper import _bracket_strategy
```

(Precedent for a command importing a private helper from another command: `commands/paper.py:49`
imports `_parse_now` from `commands.nightly`. `commands.paper` does not import `paper_check`: no cycle.)

**File:** `engine/src/seer_engine/commands/paper_check.py:161` (in `_check`)
**Change:** replace

```python
                expected = _expected(entry, head, market, dividends)
```

with

```python
                expected = _expected(conn, entry, head, market, dividends)
```

**File:** `engine/src/seer_engine/commands/paper_check.py:218-225`
**Change:** replace the whole `_expected` with

```python
def _expected(
    conn: psycopg.Connection, entry: RosterEntry, head: PaperHead, market: Market, dividends: DividendMap
) -> Records:
    if entry.engine == "bracket":
        # The replay decides paper_start .. next_session(last_session): C carries the verdicts
        # stored for exactly those sessions (read in this read-only transaction).
        strategy = _bracket_strategy(conn, entry, head.paper_start, dates.next_session(head.last_session))
        return replay.expected_bracket(market, strategy, entry.params, head)
    if entry.engine == "book":
        return replay.expected_book(market, entry.obj, entry.params, entry.rules, head, dividends)
    if entry.engine == "benchmark":
        return replay.expected_benchmark(market, head, dividends)
    raise ValueError(f"{entry.id}: unknown engine {entry.engine!r}")
```

**Impact:** `run_rules` in `replay.expected_bracket` decides every session `paper_start ..
last_session` (each on the night before it) and the trailing `decide_bracket` decides
`next_session(last_session)`; the map covers exactly that range. On a first-night-only head
(`last_session = prev_session(paper_start)`) the range is `paper_start .. paper_start`. The verdict
read happens inside `_expected`'s existing `try`, so a failing read is C's `broken("replay", ...)`
result, not a crash. A is unchanged (`strategy is entry.obj`).

### Step 4: (removed by reconciliation) `test_paper_check.py`
Phase 2 already made `ROSTER_IDS = ("SPY", "A", F4, F1, "C")` (and the five-row `test_paper_store.py:58`
assertion). This phase assumes that state and changes nothing in either file: every test in
`test_paper_check.py` iterates `ROSTER_IDS`, and C (no verdicts in that world) is `ok` with 0 orders over the
same 7 sessions, before and after this phase's code changes.

### Step 5: new `engine/tests/test_paper_c.py`
**File:** `engine/tests/test_paper_c.py` (new)
**Change:** create with exactly this content. It reuses `test_paper_check`'s synthetic world
(imported, like `test_paper_book.py` imports from `test_book_runner`) and `test_explain.FakeClient`.
In that world A has exactly 3 picks every night (24 members, 8-session cycle), so C's cap of 10
never binds and all-allow C must equal A; the first test pins that precondition.
**Code:**
```python
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
FOUR = ("SPY", "A", "F4-MOM12-N20-TREND", "F1-SPY-SMA200-M")
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
    for d in NIGHTS[:3]:  # before C landed
        night(world, d, None)
    monkeypatch.undo()
    assert roster.ROSTER[-1].id == C
    for d in NIGHTS[3:]:
        night(world, d, allow_all)

    four_start, c_start = session_of(NIGHTS[0]), session_of(NIGHTS[3])
    assert q(world, "SELECT id, paper_start FROM strategies WHERE id = ANY(%s) ORDER BY sort", (list(ALL),)) == [
        *[(i, four_start) for i in FOUR],
        (C, c_start),
    ]
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
    for d in NIGHTS:
        night(world, d, None)
    four_alone = content(world, FOUR)
    assert q(world, "SELECT count(*) FROM orders WHERE strategy_id = %s", (C,)) == [(0,)]
    monkeypatch.undo()

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
    assert sum("C · News veto" in p for p in client.prompts) == len(c_pending)
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
```

What each acceptance item maps to:

| Acceptance (phase scope) | Test |
|---|---|
| C starts with its own `paper_start`; the four keep theirs | `test_c_starts_on_its_first_night_with_its_own_paper_start` (roster monkeypatched to the four for 3 nights, then C joins) |
| ≥ 5 synthetic nights -> `paper_check` ok for all five | `test_eight_mixed_nights_equal_the_replay_from_stored_verdicts` (7 sessions, allow/veto/failed every night, `require_sessions=7` passes) |
| the replay really reads the stored verdicts | `test_replay_reads_the_stored_verdicts` (flip one `allow` that produced a trade to `veto` -> C mismatch, the four ok) |
| all-allow C orders == A orders (A ≤ 10 picks) | `test_a_has_at_most_ten_picks_every_night_so_c_candidates_are_all_of_them`, `test_all_allow_c_trades_exactly_like_a` (orders, snapshots, paper_state equal) |
| veto / failed / missing -> no C order for that symbol; `paper` exit 0 | `test_veto_failed_or_missing_verdict_is_no_order_and_paper_exits_zero[veto|failed|missing]`, `test_a_night_without_verdicts_buys_nothing_for_c_only` |
| catch-up night, verdicts only for the newest session | `test_catch_up_uses_verdicts_of_the_newest_session_only` (equals night-by-night with the veto step missing that night; replay ok) |
| idempotent re-run writes nothing | `test_paper_rerun_writes_nothing` (whole rows incl. `news_vetoes`; plus a `--dry-run` re-run) |
| non-regression of the four | `test_the_four_strategies_rows_are_identical_with_or_without_c` (all content of the four, incl. `strategies.params` digests, equal with C absent vs. C trading on verdicts; row ids excluded because `orders.id` etc. are shared sequences) |
| `explain` fills C's pending orders | `test_explain_fills_c_pending_orders_like_a` (no code change in `explain`) |
| the helper | `test_bracket_strategy_carries_verdicts_for_c_only` (A passes through by identity; C's copy carries `allow` only; the roster object is never changed) |

## Verification

**Build:** `/home/miftah/.worktrees/seer/strategy-c-news-veto/engine/.venv/bin/ruff check /home/miftah/.worktrees/seer/strategy-c-news-veto/engine`
**Tests:** `docker start seer-pg`, then from the worktree root
`PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`
(0 skipped). Fast loop: `... pytest engine/tests/test_paper_c.py engine/tests/test_paper_command.py engine/tests/test_paper_check.py engine/tests/test_explain.py engine/tests/test_paper_replay.py -q`.
**Verified in a scratch build** (worktree copy + K1/K2/K3/K4 stubs written to the contract, worktree
venv, local PG): `test_paper_c.py` 14 passed; `test_paper_command.py`, `test_paper_check.py` (as Phase 2
leaves it), `test_explain.py`, `test_paper_replay.py` all green; `ruff check` clean. **Re-verified by the
reconciler** with the real phase 1–4 plan code applied (no stubs): `test_paper_c.py`, `test_paper_check.py`,
`test_explain.py` green. With Steps 2–3
reverted, 10 of the new tests fail (with only Step 3 reverted, 5 fail), so both code changes are
covered.
**Manual check:** none (no network, no UI).
**Exit criteria:** the full engine suite passes with 0 skipped and ruff is clean; `test_paper_c.py`
proves every acceptance row above; the four frozen digests are untouched (`test_paper_roster.py`
`PINS` unchanged by this phase).

## Handoffs

- **Phase 2:** owns the `ROSTER_IDS` line in `engine/tests/test_paper_check.py:51` and `test_paper_store.py:58` (settled by reconciliation; Phase 2's Step 9 carries both).
- **Phase 2:** `store.write_vetoes` validation — this phase's tests write true ranks `1..k` for the first `k` candidates (`k` = all, or all but the last). If Phase 2 instead requires `n` to equal some externally known candidate count, the `missing` param of `test_veto_failed_or_missing_verdict_is_no_order_and_paper_exits_zero` must change to "no rows at all", which `test_a_night_without_verdicts_buys_nothing_for_c_only` already covers.
- **Phase 4:** `veto` computes candidates with `strategies.c.candidates` over `store.load_market_window(conn, store.market_window_since(rd.data_date))` at `rd.data_date` (K6 step 5). `test_paper_c.ranked()` mirrors that; `paper` (through `NewsVeto.picks` on `view.history` cut at the data date) must yield the same list or C's allowed symbols will not match. The precondition test asserts `ranked == A's picks` on the windowed market; Phase 4 should keep the exact same window call.
- **Phase 7 (docs):** runbook and `engine/package_readme.md` should say: `paper` reads `news_vetoes` for the sessions it decides; a missing row = no trade; `paper_check` replays C from stored verdicts (so deleting or editing `news_vetoes` rows after `paper` ran makes C a `mismatch`); the paper-clock reset for C must not need to delete verdicts (verdicts are inputs, kept by the reset used in these tests).
- **Phase 6:** none from here (the web reads `orders` for C like A).

## Rollback

Revert this phase's commit: `paper.py` and `paper_check.py` go back to passing `e.obj` / `entry.obj`
(C, with `allowed={}`, then never buys and its replay stays `ok` with no orders, so the tree remains
green with Phases 1–2 in place) and `test_paper_c.py` disappears. The `ROSTER_IDS` line is Phase 2's
and stays. No data migration is involved; rows already written by a live `paper` run for C are
consistent with the reverted replay only if C had no `allow` verdicts — otherwise reset C's paper
clock per the runbook.
