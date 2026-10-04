> Adopted from `PAPER_TRADING_SHIP_PLAN.md` phase 7. Source: `.workflows/plan/paper-trading-ship/phase-7.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 7: `paper` command and workflow step

**Plan set:** `PAPER_TRADING_SHIP_PLAN.md`
**Analysis:** `20261004-082027-P4S7_code_analyzer.md`
**Satisfies:** R1 (the impure paper step that runs every roster strategy forward each night), R3 (design §8 failure handling: no paper step after a failed bars run, one transaction, failed status, holidays are no sessions)
**Depends on:** Phase 5, Phase 6 (and through them Phases 1, 2, 3, 4)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/commands`

---

## Goal

`python -m seer_engine [--dry-run] [-v] paper [--now ISO8601]` exists. After a successful bars run it
moves every roster strategy (SPY, A, F4-MOM12-N20-TREND, F1-SPY-SMA200-M) forward through every new
session in one transaction. The steps for each session are: splits, settle, dividends, force-close,
persist, then decide the next session. On the first night it starts each strategy (sets
`paper_start`, writes the frozen spec, the day-0 snapshot and the first decision).

The night is idempotent. A failure writes nothing to paper state and records
`runs.paper_status = 'failed'`. `nightly.yml` runs the step after "Nightly".

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.

**Creates:**
- `seer_engine.commands.paper` (`engine/src/seer_engine/commands/paper.py`, new). Discovered by `cli` as the command `paper`:
  - `HELP: str`, `MAX_ERROR_LEN = 2000`. There is no window constant here: the bars window is `store.market_window_since(d)` = `d − store.MARKET_WINDOW_DAYS` (550), phase 6's single source.
  - `class PaperError(RuntimeError)`
  - `@dataclass(frozen=True) class NightPlan`, with fields `start: tuple[RosterEntry, ...]` and `step: tuple[tuple[RosterEntry, PaperState], ...]` (entry, its `store.PaperState`)
  - `add_arguments(p)`, `run(args) -> int`
  - `execute(conn, *, now: datetime, dry_run: bool = False) -> int`
  - `plan_night(entries, rows: Mapping[str, store.StrategyRow], states: Mapping[str, store.PaperState], rd) -> NightPlan` (raises `store.SpecMismatch` on a changed frozen spec)
  - `later_factors(splits_by_session, session) -> dict[str, Decimal]`
  - `night_view(market, session, later) -> Market`
  - private: `_Tonight`, `_night`, `_check_window`, `_start`, `_step_bracket`, `_step_book`, `_step_benchmark`, `_undo_split`, `_has_paper_rows`, `_error_text`. Tests monkeypatch `_step_book` by module attribute, so the dispatch looks it up by global name.
- `seer_engine.runs` (`engine/src/seer_engine/runs.py`, appended):
  - `@dataclass(frozen=True, slots=True) class RealRun`, with fields `id: int`, `status: str`, `data_date: date | None`, `session_date: date`, `paper_status: str | None`
  - `real_run(conn, session_date) -> RealRun | None`
  - `start_paper(conn, run_id) -> None`, `finish_paper(conn, run_id) -> None`, `fail_paper(conn, run_id, error) -> None`. Each raises `LookupError` on an unknown or demo id. None of them commits.
- `.github/workflows/nightly.yml`: step `Paper` after `Nightly`.
- `engine/tests/test_paper_command.py` (new). `engine/tests/test_runs.py` gets 4 new tests.

**Signature changes:** none to existing code.

**Requires (from earlier phases).** These are the exact names this plan calls, quoted from the sibling plan files (reconciled against phase 1's and phase 6's real APIs).

| Phase | Symbol used here | Shape |
|---|---|---|
| 1 | `seer_engine.paper.roster.ROSTER` | `tuple[RosterEntry, ...]`, in `sort` order (SPY, A, F4, F1) |
| 1 | `roster.RosterEntry` attributes | `.id`, `.engine` (`"bracket"`, `"book"`, `"benchmark"`), `.obj` (`STRATEGY_A`, `FACTOR`, `TIMING`, `None` for SPY), `.params`, `.rules` (`DESIGN_V0`, `MONTHLY_HOLD`, `None` for SPY), `.lookback: int` (200, 253, 200, 1) |
| 1 | `roster.strategy_params(entry) -> dict` | the whole C2 jsonb, `{"spec", "digest", "backtest_gate"}`; `["digest"]` is the code's digest (`spec_digest(spec(entry))`) |
| 1 | `roster.MAX_LOOKBACK_BARS` | 253 (what `_check_window` must cover; it takes `max(e.lookback)` of tonight's entries) |
| 1 | migration 003 | C1 exactly: `runs.paper_status/paper_error/paper_finished_at`, `paper_state`, `book_*`, `dividends`, `orders.mark`, roster rows |
| 1 | `demo.purge_demo_if_needed(conn, dry_run)` | purges the demo tables and resets `strategies.paper_start`/`params` (reconciled) |
| 3 | `paper.bracket.settle_bracket(pf, session, bars, splits, last_bar_date) -> BracketNight` | `BracketNight.portfolio`, `.events`, `.snapshot` |
| 3 | `paper.bracket.decide_bracket(pf, strategy, params, history, members, data_date) -> SizingResult` | requires `pf.last_session in (None, data_date)`; `.placed`, `.portfolio` |
| 3 | `paper.benchmark.step_benchmark(state, session, bar, dividend, *, split=None)` | returns `(BenchmarkState, Snapshot, fills)`; an applied SPY split is passed as `split=factor` and goes through `split_benchmark` (C3 extended) |
| 3 | `paper.benchmark.SPY` | `"SPY"` |
| 4 | `paper.book.settle_book(book, session, bars, targets, idle_added, rules, dividends, splits, last_bar_date) -> BookNight` | `dividends` is a DividendMap (`{symbol: {ex_date: amount}}`; only ex-date == session is read). `BookNight.book`, `.fills`, `.trades`, `.snapshot`, `.targets` (post-split) |
| 4 | `paper.book.decide_book(market, allocator, params, rules, data_date, held) -> (targets \| None, idle_added)` | |
| 6 | `store.StrategyRow`, `store.read_strategies(conn) -> tuple[StrategyRow, ...]` | `.id`, `.paper_start`, `.params` |
| 6 | `store.check_digest(row, digest)` | raises `store.SpecMismatch` (a `StoreError`) when `row.paper_start` is set and the stored digest differs |
| 6 | `store.freeze_spec(conn, sid, *, spec, digest, backtest_gate, paper_start)` | writes C2 + `paper_start` once; refuses an already-frozen row |
| 6 | `store.PaperState`, `store.read_paper_state(conn, sid) -> PaperState \| None` | C1 `paper_state` columns minus `updated_at` |
| 6 | `store.init_paper_state(conn, sid, *, paper_start, cash0, usd_idr) -> PaperState` | day 0: `paper_state` with `last_session = prev_session(paper_start)` and the day-0 snapshot |
| 6 | `store.write_pending(conn, sid, session, *, decision)` | `session` must be `next_session(last_session)` |
| 6 | `store.load_portfolio(conn, sid) -> Portfolio` | live `orders` + `orders.mark` + `paper_state` |
| 6 | `store.save_bracket_night(conn, sid, portfolio, events, snapshot)` | updates orders by key, upserts the snapshot, writes `paper_state` (clears pending) |
| 6 | `store.insert_pending_orders(conn, sid, placed, companies=None) -> int` | `company` falls back to the symbol |
| 6 | `store.load_book(conn, sid, *, idle_symbol=None) -> LoadedBook` | `.book`, `.targets` (`None` / `()` / rows for `pending_session`), `.idle_added` |
| 6 | `store.save_book_night(conn, sid, book, fills, trades, snapshot, *, executed_targets=None)` | positions replaced, fills `seq` 1.., trades, snapshot, `paper_state`; `executed_targets` rewrites the stored decision in place |
| 6 | `store.save_book_decision(conn, sid, session, targets \| None)` | `write_pending` + the ranked `book_targets` rows (none for `None` or `()`) |
| 6 | `store.load_benchmark(conn, sid="SPY") -> BenchmarkState` | `start` from `strategies.paper_start`; `position=None` before the first buy |
| 6 | `store.save_benchmark_night(conn, sid, state, snapshot, fills)` | the SPY `book_positions` row (deleted when `position` is None), `book_fills`, snapshot, `paper_state` |
| 6 | `store.dividends_between(conn, start, end) -> DividendMap` | both ends inclusive |
| 6 | `store.applied_splits_on(conn, session) -> tuple[tuple[str, Decimal], ...]` | `(symbol, split_to / split_from)`, applied only, by symbol |
| 6 | `store.market_window_since(d)`, `store.MARKET_WINDOW_DAYS`, `store.load_market_window(conn, since) -> Market` | `d − 550` days; the load reads inside the caller's transaction and never commits |
| 6 | `store.DIVIDEND_QUANTUM` | `0.000001` (the undo of a later split on a dividend amount) |
| 5 | `nightly` writes `dividends` and `split_adjustments` before `paper` runs; `universe.paper_symbols` keeps held symbols' bars flowing | quoted |

**Leaves alone (owned by others):**
- `commands/nightly.py`: phase 5 changes it; this phase imports only `nightly._parse_now`.
- `paper/roster.py` (phase 1), `paper/bracket.py` and `paper/benchmark.py` (phase 3), `paper/book.py` (phase 4), `paper/store.py` and `backtest/io.py` (phase 6). This phase only calls them.
- `demo.py` (phase 1), `paper/replay.py` and `commands/paper_check.py` (phase 8), `commands/explain.py` (phase 9), `web/*` (10–12).
- `docs/*`, `engine/package_readme.md`, `engine-ci.yml`, and the "Paper check" and "Explain" steps of `nightly.yml` (phase 13).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/commands/paper.py` | create | the command: guards, plan, one-transaction night, failure marking, night view |
| `engine/src/seer_engine/runs.py:62` (append after `fail_run`) | modify | `RealRun`, `real_run`, `start_paper`, `finish_paper`, `fail_paper`; new imports at lines 6–11 |
| `.github/workflows/nightly.yml:65` (append after the `Nightly` step) | modify | `Paper` step, same flags pattern as `Nightly` |
| `engine/tests/test_paper_command.py` | create | PG integration tests on synthetic bars, universe, FX and dividends, plus pure tests of `night_view` and `later_factors` |
| `engine/tests/test_runs.py:11` (import) and `:92` (append) | modify | paper-status helper tests |

## Implementation Steps

### Step 1: paper-status helpers in `runs.py`
**File:** `engine/src/seer_engine/runs.py:1-11` (imports) and `:62` (append at end of file)
**Change:** Add a read of the real run row for a session, and the three paper-status transitions. They mirror `start_run`/`_set_final`: none commits, an unknown or demo id raises `LookupError`, and the error is redacted and cut to `MAX_ERROR_CHARS`.

Replace the import block (lines 6–11) with:
```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import psycopg

from seer_engine.dates import RunDates
from seer_engine.http import redact
```
Keep the module docstring (lines 1–4) and `MAX_ERROR_CHARS = 2000` as they are.

Append after `fail_run` (line 62):
```python
@dataclass(frozen=True, slots=True)
class RealRun:
    """The real (non-demo) ``runs`` row of one session, as the paper step reads it."""

    id: int
    status: str
    data_date: date | None
    session_date: date
    paper_status: str | None


def real_run(conn: psycopg.Connection, session_date: date) -> RealRun | None:
    """The real run row for ``session_date``, or None when there is none (demo rows never count)."""
    row = conn.execute(
        """
        SELECT id, status, data_date, session_date, paper_status
        FROM runs
        WHERE session_date = %(session_date)s AND NOT is_demo
        """,
        {"session_date": session_date},
    ).fetchone()
    if row is None:
        return None
    return RealRun(
        id=int(row[0]),
        status=str(row[1]),
        data_date=row[2],
        session_date=row[3],
        paper_status=None if row[4] is None else str(row[4]),
    )


_PAPER_RUNNING_SQL = """
    UPDATE runs
    SET paper_status = 'running', paper_error = NULL, paper_finished_at = NULL
    WHERE id = %(id)s AND NOT is_demo
"""

_PAPER_FINAL_SQL = """
    UPDATE runs
    SET paper_status = %(status)s, paper_error = %(error)s, paper_finished_at = clock_timestamp()
    WHERE id = %(id)s AND NOT is_demo
"""


def _set_paper(conn: psycopg.Connection, sql: str, params: dict[str, object]) -> None:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        if cur.rowcount != 1:
            raise LookupError(f"no real run with id {params['id']}")


def start_paper(conn: psycopg.Connection, run_id: int) -> None:
    """Mark the run's paper step running (error and finished_at cleared)."""
    _set_paper(conn, _PAPER_RUNNING_SQL, {"id": run_id})


def finish_paper(conn: psycopg.Connection, run_id: int) -> None:
    """Mark the run's paper step successful."""
    _set_paper(conn, _PAPER_FINAL_SQL, {"id": run_id, "status": "success", "error": None})


def fail_paper(conn: psycopg.Connection, run_id: int, error: str) -> None:
    """Mark the run's paper step failed with ``error`` (secrets redacted, cut to 2000 characters)."""
    _set_paper(
        conn,
        _PAPER_FINAL_SQL,
        {"id": run_id, "status": "failed", "error": redact(error)[:MAX_ERROR_CHARS]},
    )
```
**Impact:** Additive. It needs migration 003's `runs.paper_*` columns (phase 1). `nightly` does not call these.

### Step 2: the `paper` command
**File:** `engine/src/seer_engine/commands/paper.py` (new)
**Change:** The impure sequencer.

- **Guards before any write:** the demo purge, a real bars run marked `success`, the roster/spec check, and the no-op.
- **One transaction for the night:** the window load, the inits, and each strategy's sessions in order. Every per-session computation uses the market as it stood that night.
- **Failure:** rollback, then `paper_status = 'failed'` in its own transaction.

The loop is strategy-outer and session-inner. Strategies share no state, so this matches "per session S, per strategy". It also lets each strategy keep its state in memory between sessions.

**Code:**
```python
"""paper: paper-trade every roster strategy through each new session, after a successful bars run.

``python -m seer_engine [--dry-run] [-v] paper [--now ISO8601]``

Flow (handover D10, design §8, plan index C4):
  1. purge demo data if a demo run exists (own transaction; rolled back under --dry-run)
  2. rd = run_dates(now). The real runs row for rd.session_date must be ``success``; otherwise log
     and exit 1 with no paper writes (no paper step after a failed or missing bars run)
  3. read the roster rows and paper_state; a set paper_start under a different spec digest is
     refused (``store.check_digest``: a changed strategy needs a new id, handover D4)
  4. every roster strategy already stepped through rd.data_date: no-op, exit 0, nothing written
     (a re-run, a weekend or a holiday lands here)
  5. runs.paper_status = running (own transaction)
  6. ONE transaction: load the bars window; start new strategies (frozen spec + paper_start =
     rd.session_date, USD/IDR = the latest fx row on or before rd.data_date, day-0 snapshot at
     rd.data_date = prev_session(paper_start), the decision for paper_start); then for every
     session S after a strategy's last_session through rd.data_date, in order: splits applied on
     S, settle S (dividends, force-close), persist, decide next_session(S), persist; finally
     paper_status = success
  7. any exception in 3-6: rollback, paper_status = failed (own transaction), exit 1

Every session is computed on ``night_view(market, S, ...)``, the market as it stood on the night
of S:
- bars and FX dated after S are invisible;
- splits that executed after S are undone on the stored history, and on the stored dividends.

So catching up several sessions in one night takes the decisions the missed nights would have
taken. Undoing a split is exact only up to the 4-dp (bars) / 6-dp (dividends) rounding of the
stored rewrite; such sessions are inside the replay check's split-affected scope anyway.

Trade logic lives in ``paper.bracket``, ``paper.book`` and ``paper.benchmark`` (pure), and all
persistence in ``paper.store``; this module only sequences them.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

import psycopg

from seer_engine import dates, db, demo, http, runs
from seer_engine.backtest.market import Market
from seer_engine.backtest.runner import INITIAL_IDR
from seer_engine.commands.nightly import _parse_now
from seer_engine.paper import roster, store
from seer_engine.paper.benchmark import SPY, step_benchmark
from seer_engine.paper.book import decide_book, settle_book
from seer_engine.paper.bracket import decide_bracket, settle_bracket
from seer_engine.paper.roster import RosterEntry
from seer_engine.paper.store import PaperState, StrategyRow
from seer_engine.sim import initial_cash_usd, new_portfolio
from seer_engine.strategies.base import History

log = logging.getLogger(__name__)

HELP = "Paper-trade the roster through every new session (runs after a successful bars run)"

MAX_ERROR_LEN = 2000

Splits = tuple[tuple[str, Decimal], ...]
Dividends = dict[str, dict[date, Decimal]]  # backtest.book_runner.DividendMap shape


class PaperError(RuntimeError):
    """A precondition of the paper step failed; the step is marked failed."""


@dataclass(frozen=True)
class NightPlan:
    """What tonight does.

    ``start``: roster entries with no paper state yet (they start tonight).
    ``step``: (entry, its state) for entries whose last session is before rd.data_date.
    """

    start: tuple[RosterEntry, ...]
    step: tuple[tuple[RosterEntry, PaperState], ...]

    def empty(self) -> bool:
        return not self.start and not self.step


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--now",
        type=_parse_now,
        default=None,
        metavar="ISO8601",
        help="pretend the current time is this (UTC if no offset); for tests and replays",
    )


def run(args: argparse.Namespace) -> int:
    now = getattr(args, "now", None) or datetime.now(timezone.utc)
    conn = db.connect()
    try:
        return execute(conn, now=now, dry_run=bool(args.dry_run))
    finally:
        conn.close()


def _error_text(e: BaseException) -> str:
    return http.redact(f"{type(e).__name__}: {e}")[:MAX_ERROR_LEN]


def execute(conn: psycopg.Connection, *, now: datetime, dry_run: bool = False) -> int:
    """Run one paper night against ``conn``. Returns the exit code (0 ok or no-op, 1 failed)."""
    demo.purge_demo_if_needed(conn, dry_run)

    rd = dates.run_dates(now)
    log.info("now %s -> data_date %s, session_date %s", now.isoformat(), rd.data_date, rd.session_date)

    try:
        bars_run = runs.real_run(conn, rd.session_date)
    finally:
        conn.rollback()
    if bars_run is None or bars_run.status != "success":
        found = "missing" if bars_run is None else bars_run.status
        log.error(
            "the bars run for session %s is %s; no paper step after a failed or missing bars run",
            rd.session_date,
            found,
        )
        return 1
    run_id = bars_run.id

    try:
        try:
            rows = {row.id: row for row in store.read_strategies(conn)}
            states: dict[str, PaperState] = {}
            for e in roster.ROSTER:
                state = store.read_paper_state(conn, e.id)
                if state is not None:
                    states[e.id] = state
        finally:
            conn.rollback()
        plan = plan_night(roster.ROSTER, rows, states, rd)
        if plan.empty():
            log.info("every roster strategy is stepped through %s; nothing to do", rd.data_date)
            return 0

        with db.transaction(conn, dry_run):
            runs.start_paper(conn, run_id)
        with db.transaction(conn, dry_run):
            _night(conn, rd, plan, run_id)
    except Exception as e:  # noqa: BLE001 - every failure must become a failed paper step
        message = _error_text(e)
        conn.rollback()
        log.error("paper failed for session %s: %s", rd.session_date, message)
        if dry_run:
            log.info("dry-run: would mark the paper step failed")
            return 1
        with db.transaction(conn, False):
            runs.fail_paper(conn, run_id, message)
        return 1
    if dry_run:
        log.info("dry-run: rolled back; nothing written")
    return 0


def plan_night(
    entries: Sequence[RosterEntry],
    rows: Mapping[str, StrategyRow],
    states: Mapping[str, PaperState],
    rd: dates.RunDates,
) -> NightPlan:
    """Which entries start tonight and which step, after the frozen-spec checks.

    Raises ``store.SpecMismatch`` when a set ``paper_start`` holds a spec digest other than the
    code's (handover D4: a changed strategy needs a new id). Raises PaperError when an entry has
    no ``strategies`` row, has ``paper_start`` but no paper state (its clock must be reset first),
    has paper state but no ``paper_start``, or when the stored pending session is not the session
    after the last one stepped.
    """
    start: list[RosterEntry] = []
    step: list[tuple[RosterEntry, PaperState]] = []
    for e in entries:
        row = rows.get(e.id)
        if row is None:
            raise PaperError(f"strategies row {e.id!r} is missing; run `migrate` (003) first")
        store.check_digest(row, roster.strategy_params(e)["digest"])
        state = states.get(e.id)
        if state is None:
            if row.paper_start is not None:
                raise PaperError(
                    f"strategy {e.id!r} has paper_start {row.paper_start} but no paper_state; reset its "
                    f"paper clock (paper runbook) before it can start"
                )
            start.append(e)
            continue
        if row.paper_start is None:
            raise PaperError(f"strategy {e.id!r} has paper state but no paper_start")
        if state.last_session >= rd.data_date:
            continue
        expected = dates.next_session(state.last_session)
        if state.pending_session != expected:
            raise PaperError(
                f"strategy {e.id!r}: pending session {state.pending_session} is not the session "
                f"after its last one ({state.last_session} -> {expected})"
            )
        step.append((e, state))
    return NightPlan(start=tuple(start), step=tuple(step))


# ---- the market as it stood on the night of a session ------------------------------------------


def later_factors(
    splits_by_session: Mapping[date, Sequence[tuple[str, Decimal]]], session: date
) -> dict[str, Decimal]:
    """``{symbol: product of factors}`` over the applied splits that executed after ``session``."""
    out: dict[str, Decimal] = {}
    for executed, items in splits_by_session.items():
        if executed <= session:
            continue
        for symbol, factor in items:
            out[symbol] = out.get(symbol, Decimal(1)) * factor
    return out


def _undo_split(h: History, factor: Decimal) -> History:
    """``h`` in pre-split units: prices x factor, volume / factor (the inverse of the stored rewrite)."""
    f = float(factor)
    return History(h.symbol, h.dates, h.open * f, h.high * f, h.low * f, h.close * f, h.volume / f)


def night_view(market: Market, session: date, later: Mapping[str, Decimal]) -> Market:
    """``market`` as it stood on the night of ``session``.

    It keeps the bars and FX dated on or before ``session``. For each ``symbol: factor`` in
    ``later`` (splits that executed after ``session``), the symbol's history is put back in the
    units it had that night. Membership is point in time already and is shared.
    """
    history: dict[str, History] = {}
    for symbol, h in market.history.items():
        cut = h.upto(session)
        factor = later.get(symbol)
        if factor is not None and len(cut):
            cut = _undo_split(cut, factor)
        history[symbol] = cut
    fx = tuple(row for row in market.fx if row[0] <= session)
    return Market(history=history, membership=market.membership, fx=fx)


@dataclass
class _Tonight:
    """Everything tonight reads: the bars window, splits and dividends by session, cached views."""

    market: Market
    splits: Mapping[date, Splits]
    dividends: Mapping[str, Mapping[date, Decimal]]  # store.dividends_between over the window
    views: dict[date, Market] = field(default_factory=dict)

    def view(self, session: date) -> Market:
        v = self.views.get(session)
        if v is None:
            v = night_view(self.market, session, later_factors(self.splits, session))
            self.views[session] = v
        return v

    def splits_on(self, session: date) -> Splits:
        return tuple(self.splits.get(session, ()))

    def dividends_on(self, session: date) -> Dividends:
        """The dividends going ex on ``session`` as a DividendMap, in that night's units (a later
        applied split's rewrite of the stored amount undone, 6 dp)."""
        later = later_factors(self.splits, session)
        out: Dividends = {}
        for symbol, by_date in self.dividends.items():
            amount = by_date.get(session)
            if amount is None:
                continue
            factor = later.get(symbol)
            if factor is not None:
                amount = (amount * factor).quantize(store.DIVIDEND_QUANTUM, rounding=ROUND_HALF_UP)
            out[symbol] = {session: amount}
        return out


# ---- the night -------------------------------------------------------------------------------


def _check_window(since: date, earliest: date, entries: Sequence[RosterEntry]) -> None:
    need = max((e.lookback for e in entries), default=0)
    have = len(dates.sessions(since, earliest))
    if have < need:
        raise PaperError(
            f"the bars window {since}..{earliest} holds {have} sessions, fewer than the roster's "
            f"longest lookback ({need}); raise store.MARKET_WINDOW_DAYS"
        )


def _night(conn: psycopg.Connection, rd: dates.RunDates, plan: NightPlan, run_id: int) -> None:
    """The single paper transaction's body (the caller's db.transaction commits or rolls back)."""
    lasts = [state.last_session for _, state in plan.step]
    if plan.start:
        lasts.append(rd.data_date)
    earliest = min(lasts)
    since = store.market_window_since(earliest)  # earliest - store.MARKET_WINDOW_DAYS (550) days
    _check_window(since, earliest, list(plan.start) + [e for e, _ in plan.step])

    market = store.load_market_window(conn, since)
    window = dates.sessions(dates.next_session(earliest), rd.data_date)
    tonight = _Tonight(
        market=market,
        splits={s: store.applied_splits_on(conn, s) for s in window},
        dividends=store.dividends_between(conn, window[0], window[-1]) if window else {},
    )
    log.info(
        "bars window since %s; %d session(s) to step (%s..%s)",
        since,
        len(window),
        window[0] if window else "-",
        window[-1] if window else "-",
    )

    for e in plan.start:
        _start(conn, e, rd, tonight)
    for e, state in plan.step:
        sessions = dates.sessions(dates.next_session(state.last_session), rd.data_date)
        if e.engine == "bracket":
            _step_bracket(conn, e, sessions, tonight)
        elif e.engine == "book":
            _step_book(conn, e, sessions, tonight)
        elif e.engine == "benchmark":
            _step_benchmark(conn, e, sessions, tonight)
        else:
            raise PaperError(f"strategy {e.id!r} has unknown engine {e.engine!r}")
    runs.finish_paper(conn, run_id)


_PAPER_ROWS_SQL = """
    SELECT EXISTS (SELECT 1 FROM orders WHERE strategy_id = %(id)s)
        OR EXISTS (SELECT 1 FROM equity_snapshots WHERE strategy_id = %(id)s)
        OR EXISTS (SELECT 1 FROM book_positions WHERE strategy_id = %(id)s)
        OR EXISTS (SELECT 1 FROM book_targets WHERE strategy_id = %(id)s)
        OR EXISTS (SELECT 1 FROM book_fills WHERE strategy_id = %(id)s)
        OR EXISTS (SELECT 1 FROM book_trades WHERE strategy_id = %(id)s)
"""


def _has_paper_rows(conn: psycopg.Connection, strategy_id: str) -> bool:
    return bool(conn.execute(_PAPER_ROWS_SQL, {"id": strategy_id}).fetchone()[0])


def _start(conn: psycopg.Connection, e: RosterEntry, rd: dates.RunDates, tonight: _Tonight) -> None:
    """Start ``e`` tonight.

    ``store.freeze_spec`` writes the frozen spec (C2) and ``paper_start = rd.session_date``;
    ``store.init_paper_state`` writes ``paper_state`` and the day-0 snapshot at
    ``prev_session(paper_start)`` (= ``rd.data_date``); then the decision for ``paper_start`` is
    written and ``paper_state.pending_session`` set to it (every engine, SPY included).
    """
    if _has_paper_rows(conn, e.id):
        raise PaperError(
            f"strategy {e.id!r} has no paper_state but has paper rows; reset its paper clock "
            f"(paper runbook) before it can start"
        )
    view = tonight.view(rd.data_date)
    try:
        usd_idr = view.usd_idr_on(rd.data_date)
    except ValueError as exc:
        raise PaperError(f"no USD/IDR rate on or before {rd.data_date}; cannot start {e.id!r}") from exc
    cash0 = initial_cash_usd(INITIAL_IDR, usd_idr)
    paper_start = rd.session_date

    frozen = roster.strategy_params(e)
    store.freeze_spec(
        conn,
        e.id,
        spec=frozen["spec"],
        digest=frozen["digest"],
        backtest_gate=frozen["backtest_gate"],
        paper_start=paper_start,
    )
    store.init_paper_state(conn, e.id, paper_start=paper_start, cash0=cash0, usd_idr=usd_idr)

    if e.engine == "bracket":
        sized = decide_bracket(
            new_portfolio(cash0),
            e.obj,
            e.params,
            view.history,
            view.membership.members_on(rd.data_date),
            rd.data_date,
        )
        store.insert_pending_orders(conn, e.id, sized.placed)
        store.write_pending(conn, e.id, paper_start, decision=False)
    elif e.engine == "book":
        targets, _ = decide_book(view, e.obj, e.params, e.rules, rd.data_date, frozenset())
        store.save_book_decision(conn, e.id, paper_start, targets)
    elif e.engine == "benchmark":
        store.write_pending(conn, e.id, paper_start, decision=False)
    else:
        raise PaperError(f"strategy {e.id!r} has unknown engine {e.engine!r}")
    log.info("%s: paper starts %s with %s USD (USD/IDR %s)", e.id, paper_start, cash0, usd_idr)


def _step_bracket(conn: psycopg.Connection, e: RosterEntry, sessions: Sequence[date], tonight: _Tonight) -> None:
    pf = store.load_portfolio(conn, e.id)
    for s in sessions:
        view = tonight.view(s)
        night = settle_bracket(pf, s, view.bars_on(s, pf.held_symbols()), tonight.splits_on(s), view.last_bar_date)
        store.save_bracket_night(conn, e.id, night.portfolio, night.events, night.snapshot)
        sized = decide_bracket(night.portfolio, e.obj, e.params, view.history, view.membership.members_on(s), s)
        store.insert_pending_orders(conn, e.id, sized.placed)
        store.write_pending(conn, e.id, dates.next_session(s), decision=False)
        pf = sized.portfolio
        log.info("%s %s: equity %s, %d live order(s)", e.id, s, pf.equity, len(pf.orders))


def _step_book(conn: psycopg.Connection, e: RosterEntry, sessions: Sequence[date], tonight: _Tonight) -> None:
    rules = e.rules
    loaded = store.load_book(conn, e.id, idle_symbol=rules.idle_symbol)
    book, targets, idle_added = loaded.book, loaded.targets, loaded.idle_added
    for s in sessions:
        view = tonight.view(s)
        symbols = set(book.held())
        if targets is not None:
            symbols.update(t.symbol for t in targets)
        night = settle_book(
            book,
            s,
            view.bars_on(s, sorted(symbols)),
            targets,
            idle_added,
            rules,
            tonight.dividends_on(s),
            tonight.splits_on(s),
            view.last_bar_date,
        )
        store.save_book_night(
            conn, e.id, night.book, night.fills, night.trades, night.snapshot, executed_targets=night.targets
        )
        book = night.book
        nxt = dates.next_session(s)
        targets, idle_added = decide_book(view, e.obj, e.params, rules, s, book.held())
        store.save_book_decision(conn, e.id, nxt, targets)
        log.info(
            "%s %s: equity %s, %d position(s)%s",
            e.id,
            s,
            book.equity,
            len(book.positions),
            f", {len(targets)} target(s) for {nxt}" if targets is not None else "",
        )


def _step_benchmark(conn: psycopg.Connection, e: RosterEntry, sessions: Sequence[date], tonight: _Tonight) -> None:
    bench = store.load_benchmark(conn, e.id)
    for s in sessions:
        view = tonight.view(s)
        bar = view.bar(SPY, s)
        if bar is None:
            raise PaperError(f"no {SPY} bar on {s}; the benchmark is marked every session")
        split = dict(tonight.splits_on(s)).get(SPY)  # an applied SPY split goes through split_benchmark (C3)
        dividend = tonight.dividends_on(s).get(SPY, {}).get(s)
        bench, snapshot, fills = step_benchmark(bench, s, bar, dividend, split=split)
        store.save_benchmark_night(conn, e.id, bench, snapshot, fills)
        store.write_pending(conn, e.id, dates.next_session(s), decision=False)
        log.info("%s %s: equity %s", e.id, s, snapshot.equity_usd)
```
**Impact:**
- New command, picked up by `cli.discover()`.
- It imports `nightly._parse_now` so `--now` parses the same way (nightly.py is not edited).
- It imports `backtest.runner.INITIAL_IDR`, the same 20,000,000 IDR the runners use. That module is a closed record and is only imported here.
- It does not touch `nightly`'s behaviour.

Notes for the implementer:
- `_has_paper_rows` is the only SQL in this module. It guards a start over leftover rows (a partial hand reset). Without it, the start would collide with old `equity_snapshots` and `orders` primary keys. Every other read and write goes through `paper.store`.
- Every write that ends a night goes through phase 6's store, which also writes `paper_state` (`save_*_night` set cash/equity/`last_session` and clear the pending decision; `write_pending` / `save_book_decision` set it again). The command never writes `paper_state` itself.
- `paper_state.pending_session` is `next_session(last_session)` between nights for **every** engine, SPY included (SPY's with `pending_decision` false). `plan_night` checks it for every engine. Phase 8 ignores SPY's pending fields.
- Book dividends: `tonight.dividends_on(S)` is every symbol's ex-date-S amount (a DividendMap); `settle_book` credits only symbols held at night, as `run_book` does.
- The demo case: `demo.purge_demo` (phase 1) resets `strategies.paper_start`/`params` whenever it purges, so after a purge every roster entry starts cleanly. A row with `paper_start` set but no `paper_state` (a partial hand reset) is refused by `plan_night`, and a changed digest under a set `paper_start` by `store.check_digest`.
- Under `--dry-run`, `start_paper` and the night run fully and roll back, as in `nightly`. The run row already exists (it was committed by a real bars run), so `finish_paper` updates a real row inside the rolled-back transaction.

### Step 3: the `Paper` workflow step
**File:** `.github/workflows/nightly.yml:65` (append after the `Nightly` step, same indentation)
**Change:** Run `paper` after `Nightly` with the same flags pattern. The default `if: success()` already skips it when `Nightly` fails, and the command refuses on its own when the bars run is not `success`. It needs only `DATABASE_URL_UNPOOLED`, which the job env already sets.
**Code:**
```yaml
      - name: Paper
        run: |
          flags=(-v)
          if [ "$DRY_RUN" = "true" ]; then flags+=(--dry-run); fi
          python -m seer_engine "${flags[@]}" paper
```
**Impact:**
- The scheduled job now writes paper state after bars.
- The concurrency group `seer-db-writer` keeps a single writer.
- Phase 13 appends "Paper check" and "Explain" after this step.

### Step 4: runs helper tests
**File:** `engine/tests/test_runs.py:11` (import) and `:92` (append at end)
**Change:** Replace line 11:
```python
from seer_engine.runs import (
    MAX_ERROR_CHARS,
    RealRun,
    fail_paper,
    fail_run,
    finish_paper,
    finish_run,
    real_run,
    start_paper,
    start_run,
)
```
Append:
```python
def _paper(conn, run_id):
    return conn.execute(
        "SELECT paper_status, paper_error, paper_finished_at FROM runs WHERE id = %s", (run_id,)
    ).fetchone()


def test_paper_status_lifecycle(pg):
    run_id = start_run(pg, RD)
    finish_run(pg, run_id)
    assert real_run(pg, RD.session_date) == RealRun(run_id, "success", RD.data_date, RD.session_date, None)
    start_paper(pg, run_id)
    assert _paper(pg, run_id) == ("running", None, None)
    finish_paper(pg, run_id)
    status, error, finished_at = _paper(pg, run_id)
    assert status == "success" and error is None and finished_at is not None
    assert real_run(pg, RD.session_date).paper_status == "success"
    start_paper(pg, run_id)  # a re-run clears the previous outcome
    assert _paper(pg, run_id) == ("running", None, None)


def test_fail_paper_truncates_and_redacts(pg):
    run_id = start_run(pg, RD)
    fail_paper(pg, run_id, "token=sekret " + "x" * 5000)
    status, error, finished_at = _paper(pg, run_id)
    assert status == "failed" and finished_at is not None
    assert len(error) == MAX_ERROR_CHARS and "sekret" not in error


def test_real_run_ignores_demo_rows(pg):
    assert real_run(pg, RD.session_date) is None
    pg.execute(
        "INSERT INTO runs (status, data_date, session_date, is_demo) VALUES ('success', %s, %s, true)",
        (RD.data_date, RD.session_date),
    )
    assert real_run(pg, RD.session_date) is None


def test_paper_helpers_on_unknown_run_raise(pg):
    with pytest.raises(LookupError):
        start_paper(pg, 999_999)
    with pytest.raises(LookupError):
        finish_paper(pg, 999_999)
    with pytest.raises(LookupError):
        fail_paper(pg, 999_999, "x")
```
**Impact:** Test-only.

### Step 5: command integration tests
**File:** `engine/tests/test_paper_command.py` (new)
**Change:** PG tests on a synthetic world:
- 24 stocks plus SPY, with bars on every NYSE session from 2025-01-02 to 2026-10-09. The bars run past every night tested, so any look-ahead would show.
- Universe rows for the 24 stocks from 2020.
- FX that changes from day to day.
- One SPY dividend, ex-date 2026-09-28.

A "night" inserts the real `runs` row that a successful bars run would have written, then calls `paper.execute(conn, now=<D 23:00 UTC>)`. The first night is Wed 2026-09-23, so `paper_start` is Thu 2026-09-24. The nights through Thu 2026-10-01 include 10-01, the first session of October, so F4 and F1 decide on night 09-30 and execute on 10-01.

Test 2 also proves same-path equality on synthetic data for SPY (`buy_and_hold`), F4 and F1 (`run_rules` with the stored `usd_idr`). A's equality is phase 8's replay; see Handoffs on FX.

**Code:**
```python
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
F4 = "F4-MOM12-N20-TREND"
F1 = "F1-SPY-SMA200-M"

ENTRIES = {e.id: e for e in roster.ROSTER}
IDS = tuple(sorted(ENTRIES))


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
    assert q(world, "SELECT count(*) FROM book_targets") == [(0,)]  # 2026-09-24 is no monthly decision
    assert q(world, "SELECT DISTINCT pending_decision FROM paper_state") == [(False,)]
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
            market, e.obj, e.params, e.rules, PAPER_START, OCT1, dividends={"SPY": {DIV_DATE: DIV_AMT}}, usd_idr=usd
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
```
**Impact:** Test-only. It needs phases 1, 3, 4 and 6 to have landed (their modules are imported).

The tests use about 11k bar rows per test. Each night loads a window of about 9.4k rows. Ten DB tests take roughly 20 to 40 s on the local container.

## Verification

**Build:** `engine/.venv/bin/python -c "import seer_engine.commands.paper"` and `engine/.venv/bin/python -m seer_engine paper --help`
**Tests:** `docker start seer-pg`, then:
- `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests/test_paper_command.py engine/tests/test_runs.py -q`
- the full suite `... pytest engine/tests -q`, which must show 0 skipped.
- `cd web && npx vitest run`, which is unchanged.

**Manual check:** `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/nightly.yml'))"` parses, and the `Paper` step sits after `Nightly`.

**Exit criteria:**
- Every test above is green, with 0 skipped.
- `paper --dry-run` leaves every table byte-identical.
- A failed or missing bars run produces exit 1 with no paper writes.
- A re-run, a weekend or a holiday is a no-op.
- A mid-night failure leaves no partial state and marks `paper_status = 'failed'`.
- Changing bars dated on or after S leaves S's decisions unchanged.

## Handoffs

- **Phase 6 / Phase 1 (API, reconciled).** Every call site uses phase 6's and phase 1's real names (Requires table). Behaviours relied on: `load_market_window` reads inside the caller's open transaction and never commits; `load_book` returns `targets=()` (not None) for a decision session with no rows; `load_benchmark` returns `position=None` before the first buy; `init_paper_state` writes the day-0 snapshot; `save_*_night` refuse a second save of the same session (fills `seq` / key updates), so `plan_night` steps only sessions after `last_session`.
- **Phase 1 / Phase 10 (demo, reconciled).** `demo.purge_demo` resets `strategies.paper_start`/`params` when it purges; the demo seed may write both. The frozen-spec refusal here is unchanged.
- **Phase 8 (replay).** `run_rules` for `bracket_v0` refuses an explicit `usd_idr` other than `market.usd_idr_on(start)`. Paper starts A at the rate on or before `prev_session(paper_start)` (Decisions, "Initial FX"). On real data those differ whenever an FX row exists for `paper_start` itself. The A replay must therefore call `run_backtest` on a `Market` whose `fx` stops at `prev_session(paper_start)`, or use an equivalent. This phase's tests only prove equality for SPY, F4 and F1 for that reason.
  Two cases are reported as "split-affected" or mismatch, never silently equal:
  - a catch-up night across an applied split: `night_view` (bars) and `_Tonight.dividends_on` (dividends) undo a later split only up to the 4-dp / 6-dp rounding of the stored rewrite. Such sessions lie inside phase 8's split-affected scope (an applied split on a held or pending symbol), so the check reports them split-affected (plan index Decisions, "Catch-up night view");
  - live versus replay force-close timing (Decisions, "Force-close rule live").
- **Phase 13 (runbook, workflow).** Four items:
  1. A dispatched `dry_run` workflow fails at `Paper` (exit 1) when the session's bars run has not already succeeded for real. Under dry-run, `Nightly` writes no run row. This is intentional: the same path as a real run.
  2. The "reset a strategy's paper clock" procedure: delete its paper rows (`paper_state`, `book_*`, `orders`, `equity_snapshots`) **and** `UPDATE strategies SET paper_start = NULL, params = '{}'` for it. The `plan_night` and `_has_paper_rows` error messages point to it.
  3. "Paper check" and "Explain" steps go after `Paper` in `nightly.yml`.
  4. The job's `timeout-minutes` (30 today) is raised to 45 by phase 13; this phase does not touch it.
- **Later (not this set).** `nightly._parse_now` is imported privately because `nightly.py` may not be edited here. Moving it to `dates.parse_now` is a small follow-up cleanup.

## Rollback

`git revert` this phase's commit. That removes `commands/paper.py`, the `runs.py` helpers and tests, and the `Paper` workflow step. No schema is touched; migration 003 belongs to phase 1.

On Neon, to stop paper trading without touching bars, delete the `Paper` step. Paper rows already written stay; the plan index's Rollback lists how to clear them.
