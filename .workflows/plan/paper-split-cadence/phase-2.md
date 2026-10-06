# Phase 2: Nightly wiring and end-to-end tests (paper night, paper_check, promote)

**Plan set:** `PAPER_SPLIT_CADENCE_PLAN.md`
**Analysis:** `20261007-011957-S9C4_code_analyzer.md`
**Satisfies:** R1, R2, R3, R7: the paper night decides split-cadence books from the persisted last rank basket, the replay agrees over many nights, and a promoted split-cadence variant paper-trades end to end
**Depends on:** Phase 1
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/commands` (+ `engine/tests`)

---

## Goal

Today `commands/paper.py` calls `decide_book` with no last rank basket, so a roster entry on a
split-cadence rule set could not be decided (phase 1 removes the refusal but needs the basket).
After this phase the nightly `_start` and `_step_book` give `decide_book` the last rank session's
basket, read back from `book_targets` inside tonight's transaction, plus the book's marks, and a
resize-only decision stores no evidence. A new Postgres test file shows that a
`monthly-rank-weekly-resize-frac` entry run over 20 nights (with resize weeks, a mid-month
kickoff, a catch-up across the monthly rank, a 2:1 split on a held symbol inside the month, and a
stopped-out position) matches `run_rules`. `paper_check` never reports `mismatch` for it, and a
real `promote --fractional` of lab variant `M0022-W-TV14` lands as
`monthly-rank-weekly-resize-frac` and trades through 25 nights to a green `paper_check`.

## Interface Contract

**Deletes:** none
**Renames:** none
**Creates:**
- `commands.paper._split_inputs(conn, strategy_id, rules, paper_start, kickoff, session, positions) -> tuple[tuple[Target, ...] | None, dict[str, Decimal]]` (`commands/paper.py`, private)
- `commands.paper._resize_only(rules, session, kickoff) -> bool` (`commands/paper.py`, private)
- `engine/tests/test_paper_split_cadence.py` (new test module)

**Signature changes:** none. `_start` and `_step_book` keep their signatures. Only their bodies change.
**Requires (from earlier phases):**
- `seer_engine.paper.book.decide_book(market, allocator, params, rules, data_date, held, *, force=False, last_rank: tuple[Target, ...] | None = None, marks: Mapping[str, Decimal] | None = None)`. With split rules, `force=True` ranks. A resize-only session with `last_rank` None returns `(None, False)`, and one with a `last_rank` tuple (possibly `()`) returns `_with_idle(_rescaled(market, last_rank, fresh, mine, data_date, marks))`. On that resize path `marks` is REQUIRED (ValueError mentioning "marks" when None) and `last_rank` must be a `tuple` of `Target` (TypeError on a list: always pass `rank_basket(...)`'s result); `marks` must be a `Mapping[str, Decimal]`. Rules without `resize_cadence` ignore both keywords and behave as on `dffac31` (Phase 1). This phase always passes a `tuple` (or None) and a `dict` for split rules, never None marks.
- `seer_engine.paper.book.last_rank_session(rules, paper_start, kickoff, session) -> date | None`: the latest `d` in `[paper_start, session)` with `is_rank_session(rules, d)` or `d == kickoff` (where `kickoff` is the stored `paper_state.kickoff_session`, possibly None — in `_step_book` the `kicked` variable, which is updated to `nxt` in the loop right after a kickoff is written, so a later session of the same catch-up night sees it). Returns None when there is no such `d` (no rank yet); a rank session whose decision was empty stores no rows, and `read_book_targets` then gives `()`, which `rank_basket` keeps as `()` — a valid basket, not "no rank". Pure (Phase 1).
- `seer_engine.paper.book.rank_basket(targets, idle_symbol) -> tuple[Target, ...]`: `targets` with a trailing row whose symbol is `idle_symbol` dropped. `()` stays `()`. Pure (Phase 1).
- `seer_engine.paper.book.needs_kickoff` tests `is_rank_session` (Phase 1), so a clock that starts on a resize-only Monday (no rank behind it) DOES kick off there: that decision is a forced rank, not a resize (`_resize_only` returns False for it, so it keeps its evidence).
- `seer_engine.sim.rules.MONTHLY_RANK_WEEKLY_RESIZE_FRAC` (id `monthly-rank-weekly-resize-frac`) exists, is in `PRESETS` (so `roster.rules_for` finds it), and `commands.promote.fractional_twin(MONTHLY_RANK_WEEKLY_RESIZE) is MONTHLY_RANK_WEEKLY_RESIZE_FRAC` (Phase 1).
- `seer_engine.paper.replay.expected_book` replays split rules: it tracks its own expected rank basket and uses `last_close` marks, so `paper_check` judges a split-cadence entry (Phase 1).

**Leaves alone (owned by others):** `paper/book.py`, `paper/replay.py`, `sim/*`, `backtest/*`, `commands/promote.py` (Phase 1 owns the code; this phase only *runs* promote), `paper/store.py` (unchanged: `read_book_targets` is reused as is and no store helper is added), all existing tests (no edits; `tests/test_paper_roster.py::PINS` untouched), `web/*` (Phase 3).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/commands/paper.py` | modify | docstring paragraph (after line 48); imports (line 70 + two new lines); new `_resize_only` and `_split_inputs` (inserted after `_evidence`, before `_start` at line 515); `_start` book branch (lines 559–566); `_step_book` decision block (lines 623–629) |
| `engine/tests/test_paper_split_cadence.py` | create | scripted split-cadence world on Postgres (runner equality, decisions, split, stop-out) and the `promote --fractional` end-to-end test |

`paper/store.py` is not touched. A thin `read_rank_basket` helper was considered and rejected:
it would duplicate `read_book_targets` plus a phase 1 pure function, and the composition is 3
lines in `_split_inputs`.

## Implementation Steps

### Step 0: Worktree venv (environment, no source change)
**File:** none
**Change:** The worktree needs its own venv. Main's venv tests the wrong tree. The planner
already created one at `/home/miftah/.worktrees/seer/paper-split-cadence/engine/.venv`. If it is
missing, recreate it:
```bash
cd /home/miftah/.worktrees/seer/paper-split-cadence
python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'
```
**Impact:** none on the tree.

### Step 1: Module docstring paragraph
**File:** `engine/src/seer_engine/commands/paper.py:48` (insert after the "Evidence (migration 009 …" paragraph, which ends at line 48 with "logs a warning.", before the blank line and the "Trade logic lives in …" paragraph)
**Change:** Insert this paragraph, preceded by one blank line.
**Code:**
```python
Split-cadence rules (``rules.resize_cadence``, e.g. ``monthly-rank-weekly-resize-frac``): a book
picks its basket on rank sessions (and its kickoff) and re-scales that frozen basket on
resize-only sessions. The basket is never recomputed. The night reads it back from the
``book_targets`` rows of the last rank session (``paper.book.last_rank_session``, then
``paper.book.rank_basket`` drops a trailing idle row) on tonight's own connection, so a rank decided
earlier in a catch-up loop is seen. It hands that basket and the settled book's marks to
``decide_book``. A resize-only decision opens no position, so it stores no evidence. A rule
set without ``resize_cadence`` takes none of these reads and calls ``decide_book`` exactly as before.
```
**Impact:** documentation only.

### Step 2: Imports
**File:** `engine/src/seer_engine/commands/paper.py:70`
**Change:** Replace line 70
```python
from seer_engine.paper.book import decide_book, needs_kickoff, settle_book
```
with
```python
from seer_engine.paper.book import decide_book, last_rank_session, needs_kickoff, rank_basket, settle_book
```
and after line 75 (`from seer_engine.sim import initial_cash_usd, new_portfolio`) add:
```python
from seer_engine.sim.book import Position, Target
from seer_engine.sim.rules import TradeRules, is_resize_session
```
**Impact:** `last_rank_session` and `rank_basket` must exist (Phase 1). No import cycle: `commands` already imports `paper.book`, which imports `sim.book` and `sim.rules`.

### Step 3: `_resize_only` and `_split_inputs`
**File:** `engine/src/seer_engine/commands/paper.py:513` (after `_evidence`, which ends at line 512 with `return {}`, and before `def _start` at line 515)
**Change:** Insert two private helpers (two blank lines before and after each, per file style).
**Code:**
```python
def _resize_only(rules: TradeRules, session: date, kickoff: bool) -> bool:
    """True when the decision for ``session`` is a resize-only one: ``rules`` split their
    cadences, ``session`` re-scales the frozen basket (``sim.rules.is_resize_session``) and it is
    not the kickoff (a forced rank). Such a decision opens no position, so it stores no evidence
    (plan Decisions, handover §5 Q1).

    False at once for every rule set without ``resize_cadence``: ``is_resize_session`` is not even
    called, so those nights run exactly as before.
    """
    return rules.resize_cadence is not None and not kickoff and is_resize_session(rules, session)


def _split_inputs(
    conn: psycopg.Connection,
    strategy_id: str,
    rules: TradeRules,
    paper_start: date,
    kickoff: date | None,
    session: date,
    positions: Sequence[Position],
) -> tuple[tuple[Target, ...] | None, dict[str, Decimal]]:
    """``(last_rank, marks)`` for ``decide_book`` deciding ``session`` under split-cadence rules.

    ``last_rank`` is the pre-idle basket of the last rank session before ``session``:
    ``paper.book.last_rank_session`` gives the latest rank session, or the stored ``kickoff``, in
    ``[paper_start, session)``. Its ``book_targets`` rows are read on ``conn`` (inside tonight's
    transaction, so a rank decided earlier in tonight's catch-up loop is visible), and
    ``paper.book.rank_basket`` drops a trailing idle row. ``()`` when that rank chose nothing (an
    empty decision writes no rows). None when no rank has happened yet. Stored weights are exact
    at ``WEIGHT_QUANTUM`` and a split never changes a weight, so this is ``run_book``'s own
    ``last_rank`` (plan Decisions: option (a), read back, not recomputed).

    ``marks`` is ``{symbol: mark}`` over ``positions``: the book after ``prev_session(session)``
    settled, which is ``run_book``'s ``marks``.
    """
    marks = {p.symbol: p.mark for p in positions}
    ranked = last_rank_session(rules, paper_start, kickoff, session)
    if ranked is None:
        return None, marks
    return rank_basket(store.read_book_targets(conn, strategy_id, ranked), rules.idle_symbol), marks
```
**Impact:** new private functions only. They are called only when `rules.resize_cadence is not None` (Steps 4–5).

### Step 4: `_start` passes the split inputs
**File:** `engine/src/seer_engine/commands/paper.py:515–571` (the whole function. The change is in the `elif e.engine == "book":` branch, lines 559–566)
**Change:** Replace `_start` with the version below. Behaviour for rule sets without
`resize_cadence` is unchanged: the same `decide_book` call and the same evidence expression.
For split rules `last_rank` is always None at the start, because `[paper_start, paper_start)` is
empty. The first decision is then a rank, either because `paper_start` is a rank session or
because `needs_kickoff` forces one. The helper is still called so that both entry points share
one path.
**Code:**
```python
def _start(conn: psycopg.Connection, e: RosterEntry, rd: dates.RunDates, tonight: _Tonight) -> None:
    """Start ``e`` tonight.

    ``store.freeze_spec`` writes the frozen spec (C2) and ``paper_start = rd.session_date``;
    ``store.init_paper_state`` writes ``paper_state`` and the day-0 snapshot at
    ``prev_session(paper_start)`` (= ``rd.data_date``); then the decision for ``paper_start`` is
    written and ``paper_state.pending_session`` set to it (every engine, SPY included).

    A split-cadence book (``e.rules.resize_cadence``) gets ``last_rank`` and ``marks`` from
    ``_split_inputs``: at the start there is no rank yet and nothing is held, so they are None and
    ``{}``, and the first decision is a rank (``paper_start`` is a rank session or the kickoff).
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
    cash0 = initial_cash_usd(PAPER_INITIAL_IDR, usd_idr)
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
            _bracket_strategy(conn, e, paper_start, paper_start),
            e.params,
            view.history,
            view.membership.members_on(rd.data_date),
            rd.data_date,
        )
        facts = _evidence(e, view, rd.data_date, (o.symbol for o in sized.placed))
        store.insert_pending_orders(conn, e.id, sized.placed, evidence=facts)
        store.write_pending(conn, e.id, paper_start, decision=False)
    elif e.engine == "book":
        kickoff = needs_kickoff(e.rules, paper_start, paper_start, None)
        if e.rules.resize_cadence is None:
            targets, _ = decide_book(view, e.obj, e.params, e.rules, rd.data_date, frozenset(), force=kickoff)
        else:
            last_rank, marks = _split_inputs(conn, e.id, e.rules, paper_start, None, paper_start, ())
            targets, _ = decide_book(
                view,
                e.obj,
                e.params,
                e.rules,
                rd.data_date,
                frozenset(),
                force=kickoff,
                last_rank=last_rank,
                marks=marks,
            )
        if targets is None or _resize_only(e.rules, paper_start, kickoff):
            facts = None
        else:
            facts = _evidence(e, view, rd.data_date, (t.symbol for t in targets))
        store.save_book_decision(conn, e.id, paper_start, targets, evidence=facts)
        if kickoff:
            store.write_kickoff(conn, e.id, paper_start)
        store.save_book_preview(conn, e.id, rd.data_date, targets, evidence=facts)
    elif e.engine == "benchmark":
        store.write_pending(conn, e.id, paper_start, decision=False)
    else:
        raise PaperError(f"strategy {e.id!r} has unknown engine {e.engine!r}")
    log.info("%s: paper starts %s with %s USD (USD/IDR %s)", e.id, paper_start, cash0, usd_idr)
```
**Impact:** none for any current roster entry (none has `resize_cadence`). For those, `_resize_only` returns False before calling anything, so `facts` is exactly `None if targets is None else _evidence(...)` as before.

### Step 5: `_step_book` passes the split inputs and drops evidence on resize-only nights
**File:** `engine/src/seer_engine/commands/paper.py:591–647` (the whole function. The change is lines 623–629)
**Change:** Replace `_step_book` with the version below. The preview rule (lines 633–639) is
kept as is. On a resize night the preview is the decision itself, with its evidence None. On a
non-decision night it is the fresh `force=True` rank, which ranks for split rules too (no
`last_rank` needed).
**Code:**
```python
def _step_book(
    conn: psycopg.Connection,
    e: RosterEntry,
    sessions: Sequence[date],
    tonight: _Tonight,
    state: PaperState,
    paper_start: date,
) -> None:
    rules = e.rules
    loaded = store.load_book(conn, e.id, idle_symbol=rules.idle_symbol)
    book, targets, idle_added = loaded.book, loaded.targets, loaded.idle_added
    kicked = state.kickoff_session
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
        # A book that has never decided ranks on its first session instead of waiting for its
        # cadence (008, paper.book.needs_kickoff); the replay ranks on the stored kickoff too.
        kickoff = needs_kickoff(rules, paper_start, nxt, kicked)
        if rules.resize_cadence is None:
            targets, idle_added = decide_book(view, e.obj, e.params, rules, s, book.held(), force=kickoff)
        else:
            # Split cadences: a resize-only session re-scales the LAST RANK SESSION'S basket, read
            # back from book_targets in this transaction, at the settled book's marks.
            last_rank, marks = _split_inputs(conn, e.id, rules, paper_start, kicked, nxt, book.positions)
            targets, idle_added = decide_book(
                view,
                e.obj,
                e.params,
                rules,
                s,
                book.held(),
                force=kickoff,
                last_rank=last_rank,
                marks=marks,
            )
        # A resize-only decision opens no position, so it has nothing to explain.
        if targets is None or _resize_only(rules, nxt, kickoff):
            facts = None
        else:
            facts = _evidence(e, view, s, (t.symbol for t in targets))
        store.save_book_decision(conn, e.id, nxt, targets, evidence=facts)
        if kickoff:
            store.write_kickoff(conn, e.id, nxt)
            kicked = nxt
        if s == sessions[-1]:
            # What it would pick if it ranked tonight: display only, never traded or replayed.
            preview, preview_facts = targets, facts
            if preview is None:
                preview, _ = decide_book(view, e.obj, e.params, rules, s, book.held(), force=True)
                preview_facts = None if preview is None else _evidence(e, view, s, (t.symbol for t in preview))
            store.save_book_preview(conn, e.id, s, preview, evidence=preview_facts)
        log.info(
            "%s %s: equity %s, %d position(s)%s",
            e.id,
            s,
            book.equity,
            len(book.positions),
            f", {len(targets)} target(s) for {nxt}" if targets is not None else "",
        )
```
**Impact:** none for current roster entries (the `resize_cadence is None` branch is today's call, character for character, and `_resize_only` short-circuits). For split rules: `kicked` starts as the stored `state.kickoff_session` and is set to `nxt` right after `store.write_kickoff`, so every later session in the same catch-up loop passes the kickoff made earlier that night to `_split_inputs` (exactly what phase 1's `split_paper_run` does). When `kickoff` is True tonight the decision is a forced rank and `last_rank` is unused (and None, since nothing lies in `[paper_start, nxt)`).

### Step 6: New end-to-end test module
**File:** `engine/tests/test_paper_split_cadence.py` (new)
**Change:** Create the file below. The scenario was checked before planning: the scripted
allocator under `replace(MONTHLY_RANK_WEEKLY_RESIZE, fractional=True)` was run through today's
`run_rules` over 2026-10-14..2026-11-16 (kickoff 2026-10-14) on this exact world. It produced
trims on 10-19, the S03 `sl` exit on 10-21, adds on 10-26 for S00..S02 only, the November rank
on 11-02, adds on 11-09 and trims on 11-16. `M0022-W-TV14` under fractional rules on the promote
world held 20 names throughout and trimmed on resize Monday 11-16.
**Code:**
```python
"""Split-cadence rules on the paper night (plan paper-split-cadence, phase 2), on Postgres.

A roster entry on ``monthly-rank-weekly-resize-frac`` picks its basket on the first session of
each month (or its kickoff) and re-scales that basket on the first session of every other week.
The paper night reads the last rank basket back from ``book_targets``. These tests hold that night
to ``run_rules`` (the closed backtest record) and to ``paper_check`` (the replay), and run a real
``promote --fractional`` of a split-cadence lab variant onto the roster and through nights.

World one (scripted): eight stocks S00..S07 with smooth 2-decimal prices, so a 2:1 split is exact
both ways. ``ScriptedSplit`` picks S00..S03 for October and S01, S04, S05, S06 after, at a total
weight fixed per ISO week, so every resize week moves the book. S03 carries a stop 10% under its
entry close and dips 15% intraday on 2026-10-21. Paper starts on Wednesday 2026-10-14 (a kickoff,
not a month start). The nights of 2026-10-30 .. 2026-11-05 are skipped, so the night of 2026-11-06
catches up across the November rank and decides the resize after it in one transaction.

World two (promote): test_paper_command's 24 random-walk stocks plus SPY. That history is long
enough for lab M0022's 426-session lookback.
"""

from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from functools import lru_cache
from typing import Any

import pytest
from psycopg.rows import tuple_row

from seer_engine import bars, dates, db, fx, splits
from seer_engine.backtest import io as bio
from seer_engine.backtest.book_runner import run_rules
from seer_engine.backtest.market import Market, Membership
from seer_engine.commands import paper, paper_check, promote
from seer_engine.lab import store as lab_store
from seer_engine.paper import replay, roster
from seer_engine.paper.capital import PAPER_INITIAL_IDR
from seer_engine.prices import Bar
from seer_engine.sim.book import Target, to_weight
from seer_engine.sim.rules import (
    MONTHLY_RANK_WEEKLY_RESIZE,
    MONTHLY_RANK_WEEKLY_RESIZE_FRAC,
    is_rank_session,
    is_resize_session,
)
from seer_engine.splits import Split
from seer_engine.strategies import evidence
from seer_engine.strategies.allocator import Allocator, scale_weight, target_from_close
from seer_engine.strategies.base import history_from_bars

UTC = timezone.utc
FRAC = "monthly-rank-weekly-resize-frac"
RULES = MONTHLY_RANK_WEEKLY_RESIZE_FRAC
SID = "SPLIT-TEST"
OBJECT = "SCRIPTED_SPLIT"
USD_IDR = Decimal("16500.0000")

HIST_START = date(2025, 1, 2)
HIST_END = date(2026, 11, 30)  # bars run past the last night, so a look-ahead would be visible
STOCKS = tuple(f"S{k:02d}" for k in range(8))
OCTOBER = ("S00", "S01", "S02", "S03")
NOVEMBER = ("S01", "S04", "S05", "S06")
STOPPED = "S03"
SPLIT_SYMBOL = "S01"  # held from the kickoff to the end

FIRST_NIGHT = date(2026, 10, 13)
PAPER_START = date(2026, 10, 14)  # a Wednesday: the kickoff, not a month start
OCT19 = date(2026, 10, 19)  # resize-only
STOP_DAY = date(2026, 10, 21)  # S03's stop is hit intraday
OCT26 = date(2026, 10, 26)  # resize-only: S03 is gone and is not bought back
NOV2 = date(2026, 11, 2)  # rank: the first session of November
NOV9 = date(2026, 11, 9)  # resize-only; in the split world S01 splits 2:1 on it
NOV16 = date(2026, 11, 16)  # resize-only
LAST = NOV16
PENDING = date(2026, 11, 17)
SKIPPED = frozenset({date(2026, 10, 30), NOV2, date(2026, 11, 3), date(2026, 11, 4), date(2026, 11, 5)})
NIGHTS = tuple(d for d in dates.sessions(FIRST_NIGHT, LAST) if d not in SKIPPED)
RESIZES = (OCT19, OCT26, NOV9, NOV16)
DECISIONS = (PAPER_START, OCT19, OCT26, NOV2, NOV9, NOV16)

# Monday of the decided session's ISO week -> the basket's total weight.
EXPOSURE = {
    date(2026, 10, 12): Decimal("0.80"),  # kickoff 2026-10-14
    date(2026, 10, 19): Decimal("0.48"),  # resize: trim
    date(2026, 10, 26): Decimal("0.88"),  # resize: add (S00..S02; S03 stopped out)
    date(2026, 11, 2): Decimal("0.60"),  # rank: the November basket
    date(2026, 11, 9): Decimal("0.92"),  # resize: add, on the split day
    date(2026, 11, 16): Decimal("0.40"),  # resize: trim
}
OTHER_WEEKS = Decimal("0.70")


# ---- the scripted allocator --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScriptedParams:
    """The scripted allocator has no levers; its spec names the script."""

    def as_dict(self) -> dict[str, str]:
        return {"script": "S00-S03 in October, S01 and S04-S06 after, total weight fixed per week"}


class ScriptedSplit:
    """A fixed monthly basket at a fixed weekly total weight (an Allocator).

    The basket is chosen by the month of the session decided, and its total by that session's ISO
    week, so ``run_book``'s resize factor k is a known ratio every week. S03 carries a stop at 90%
    of its close. Weights never depend on prices, so a split cannot move them.
    """

    id = "SCRIPTED-SPLIT"

    def lookback(self, params: Any) -> int:
        return 5

    def symbols(self, params: Any) -> tuple[str, ...]:
        return STOCKS

    def holds(self, params: Any) -> tuple[str, ...]:
        return ()

    def uses_members(self, params: Any) -> bool:
        return False

    def targets(self, history, members, data_date, held, params) -> tuple[Target, ...]:
        session = dates.next_session(data_date)
        exposure = EXPOSURE.get(session - timedelta(days=session.weekday()), OTHER_WEEKS)
        basket = OCTOBER if session.month == 10 else NOVEMBER
        weight = to_weight(exposure / len(basket))
        out: list[Target] = []
        for symbol in basket:
            h = history.get(symbol)
            i = None if h is None else h.index_of(data_date)
            if i is None:
                continue
            close = float(h.close[i])
            t = target_from_close(symbol, close, weight, stop=close * 0.9 if symbol == STOPPED else None)
            if t is not None:
                out.append(t)
        return tuple(out)

    def prepare(self, history):
        return dict(history)

    def targets_prepared(self, prepared, members, data_date, held, params) -> tuple[Target, ...]:
        cut = {s: h.upto(data_date) for s, h in prepared.items()}
        return self.targets(cut, members, data_date, held, params)


SCRIPTED = ScriptedSplit()
PARAMS = ScriptedParams()
assert isinstance(SCRIPTED, Allocator)


def scripted_evidence(market, params, data_date, symbols):
    return {s: (f"the test script picks {s} on {data_date.isoformat()}",) for s in symbols}


@pytest.fixture(autouse=True)
def scripted_object(monkeypatch):
    """Name the scripted allocator in the resolver and give it evidence, for one test only."""
    monkeypatch.setitem(roster.RESOLVER, OBJECT, roster.Binding(obj=SCRIPTED, params=PARAMS))
    monkeypatch.setitem(evidence.EVIDENCE, OBJECT, scripted_evidence)


# ---- the expected decisions (price-free, so the split world must match them too) ---------------


def _resized(rank_weight: Decimal, kept: tuple[str, ...], exposure: str) -> tuple[tuple[str, Decimal], ...]:
    """``book_runner._rescaled``'s weights for a four-name rank basket of ``rank_weight`` each:
    every kept name's weight times k = (this week's fresh total) / (the rank basket's total)."""
    fresh_total = 4 * to_weight(Decimal(exposure) / 4)
    k = fresh_total / (4 * rank_weight)
    return tuple((s, scale_weight(rank_weight, k)) for s in kept)


W_OCT = to_weight(Decimal("0.80") / 4)
W_NOV = to_weight(Decimal("0.60") / 4)
EXPECTED_WEIGHTS = {
    PAPER_START: tuple((s, W_OCT) for s in OCTOBER),
    OCT19: _resized(W_OCT, OCTOBER, "0.48"),
    OCT26: _resized(W_OCT, OCTOBER[:3], "0.88"),  # S03 was stopped out: never re-bought on a resize
    NOV2: tuple((s, W_NOV) for s in NOVEMBER),
    NOV9: _resized(W_NOV, NOVEMBER, "0.92"),
    NOV16: _resized(W_NOV, NOVEMBER, "0.40"),
}


# ---- the worlds --------------------------------------------------------------------------------


def _px(x: float) -> float:
    return round(x, 2)


@lru_cache(maxsize=1)
def scripted_bars() -> tuple[Bar, ...]:
    days = dates.sessions(HIST_START, HIST_END)
    out: list[Bar] = []
    for k, symbol in enumerate(STOCKS):
        base = 20.0 + 5.0 * k
        for i, d in enumerate(days):
            c = base * (1 + 0.0008 * i) * (1 + 0.01 * math.sin((i + k) / 4))
            o = c * (1 - 0.003 * math.cos((i + k) / 3))
            dip = 0.85 if (symbol == STOPPED and d == STOP_DAY) else 0.995
            out.append(
                bars.make_bar(symbol, d, _px(o), _px(max(o, c) * 1.005), _px(min(o, c) * dip), _px(c), 2_000_000)
            )
    for i, d in enumerate(days):
        c = 400.0 * (1 + 0.0005 * i)
        o = c * 0.999
        out.append(bars.make_bar("SPY", d, _px(o), _px(c * 1.004), _px(o * 0.996), _px(c), 80_000_000))
    return tuple(out)


def _halved(b: Bar) -> Bar:
    """``b`` in the units after a 2:1 split (exact: every stored price has 2 decimals)."""
    return bars.make_bar(b.symbol, b.date, b.open / 2, b.high / 2, b.low / 2, b.close / 2, b.volume * 2)


def memory_market() -> Market:
    """World one without the split, in memory: the book the split world must come close to."""
    by: dict[str, list[Bar]] = {}
    for b in scripted_bars():
        by.setdefault(b.symbol, []).append(b)
    return Market(
        history={s: history_from_bars(s, rows) for s, rows in by.items()},
        membership=Membership(intervals=tuple((s, date(2020, 1, 2), None) for s in STOCKS)),
        fx=((HIST_START, USD_IDR),),
    )


PROMOTE_STOCKS = (
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "JPM", "V", "MA", "UNH",
    "HD", "PG", "COST", "LLY", "XOM", "JNJ", "ABBV", "MRK", "PEP", "KO", "WMT", "BAC",
)


@lru_cache(maxsize=1)
def promote_bars() -> tuple[Bar, ...]:
    """test_paper_command's random-walk world, run to HIST_END (M0022 reads 426 sessions)."""
    days = dates.sessions(HIST_START, HIST_END)
    out: list[Bar] = []
    for i, d in enumerate(days):
        c = 400.0 * 1.0005**i * (1 + 0.01 * math.sin(i / 5))
        o = c * (1 - 0.002 * math.cos(i / 3))
        out.append(
            bars.make_bar(
                "SPY", d, round(o, 4), round(max(o, c) * 1.004, 4), round(min(o, c) * 0.996, 4), round(c, 4), 80_000_000
            )
        )
    for symbol in PROMOTE_STOCKS:
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


def _seed(conn, rows, members) -> None:
    with db.transaction(conn, False):
        bars.upsert_bars(conn, rows)
        fx.upsert_fx(conn, [(HIST_START, USD_IDR)])
        for s in members:
            conn.execute(
                "INSERT INTO universe (symbol, index_id, start_date, end_date, source_symbol) "
                "VALUES (%s, 'SP500', '2020-01-02', NULL, %s)",
                (s, s),
            )


def _only(conn, sid: str) -> None:
    """Retire every other roster row before it starts: only ``sid`` trades in these worlds."""
    with db.transaction(conn, False):
        conn.execute("UPDATE strategies SET status = 'retired' WHERE id <> %s", (sid,))


def _add_scripted_entry(conn) -> None:
    with db.transaction(conn, False):
        conn.execute(
            "INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id, "
            "object_name, registry_id, gate_note, gate_applicable, status, params) "
            "VALUES (%s, 'Split test', 'Picks monthly, resizes weekly', 'flask-conical', false, false, 99, "
            "'book', %s, %s, NULL, 'No backtest gate: a test entry', true, 'active', '{}'::jsonb)",
            (SID, FRAC, OBJECT),
        )
    _only(conn, SID)


@pytest.fixture
def world(pg):
    _seed(pg, scripted_bars(), STOCKS)
    _add_scripted_entry(pg)
    return pg


@pytest.fixture
def split_world(pg):
    """World one with S01's bars from the split day on held back until the split night."""
    _seed(pg, tuple(b for b in scripted_bars() if not (b.symbol == SPLIT_SYMBOL and b.date >= NOV9)), STOCKS)
    _add_scripted_entry(pg)
    return pg


# ---- nights ------------------------------------------------------------------------------------


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


def split_s01(conn) -> None:
    """What the bars run does on the split night: record and apply the split (rewriting S01's
    stored history), then store the post-split bars."""
    post = tuple(_halved(b) for b in scripted_bars() if b.symbol == SPLIT_SYMBOL and b.date >= NOV9)
    with db.transaction(conn, False):
        [outcome] = splits.apply_splits(
            conn, [Split(SPLIT_SYMBOL, NOV9, Decimal(1), Decimal(2))], {SPLIT_SYMBOL: post[0].open}
        )
        assert outcome.applied, outcome.reason
        bars.upsert_bars(conn, post)


def step(conn, *, split: bool = False) -> None:
    for d in NIGHTS:
        if split and d == NOV9:
            split_s01(conn)
        night(conn, d)


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


def stored_weights(conn, sid: str = SID) -> dict[date, tuple[tuple[str, Decimal], ...]]:
    out: dict[date, list[tuple[str, Decimal]]] = {}
    for d, symbol, weight in q(
        conn,
        "SELECT session_date, symbol, weight FROM book_targets WHERE strategy_id = %s ORDER BY session_date, rank",
        (sid,),
    ):
        out.setdefault(d, []).append((symbol, weight))
    return {d: tuple(v) for d, v in out.items()}


def evidence_counts(conn, sid: str):
    """``[(session, rows without evidence, rows)]`` per stored decision."""
    return q(
        conn,
        "SELECT session_date, count(*) FILTER (WHERE evidence IS NULL), count(*) FROM book_targets "
        "WHERE strategy_id = %s GROUP BY session_date ORDER BY session_date",
        (sid,),
    )


# ---- the calendar this file relies on ----------------------------------------------------------


def test_the_calendar_is_what_the_scenario_says():
    assert not is_rank_session(RULES, PAPER_START) and not is_resize_session(RULES, PAPER_START)
    assert is_rank_session(RULES, NOV2) and not is_resize_session(RULES, NOV2)
    assert all(is_resize_session(RULES, d) for d in RESIZES)
    assert RULES.id == FRAC and RULES.fractional and RULES.resize_cadence == "weekly"
    assert NOV9 in NIGHTS and NOV2 not in NIGHTS and date(2026, 11, 6) in NIGHTS


# ---- world one: the runner, the replay, the decisions ------------------------------------------


def test_split_cadence_nights_equal_the_runner_and_the_replay(world, tmp_path):
    step(world)
    [(kickoff, usd, last_session, pending)] = q(
        world,
        "SELECT kickoff_session, usd_idr, last_session, pending_session FROM paper_state WHERE strategy_id = %s",
        (SID,),
    )
    assert (kickoff, last_session, pending) == (PAPER_START, LAST, PENDING)

    market, _ = bio.load_market(world, cache_dir=tmp_path)
    result = run_rules(
        market, SCRIPTED, PARAMS, RULES, PAPER_START, LAST, usd_idr=usd, kickoff=kickoff, initial_idr=PAPER_INITIAL_IDR
    )
    assert q(
        world, "SELECT date, cash_usd, equity_usd FROM equity_snapshots WHERE strategy_id = %s ORDER BY date", (SID,)
    ) == [(s.date, s.cash_usd, s.equity_usd) for s in result.snapshots]
    assert q(
        world,
        "SELECT session_date, symbol, side, shares, price, cash_usd, cost_usd, reason FROM book_fills "
        "WHERE strategy_id = %s ORDER BY session_date, seq",
        (SID,),
    ) == [(f.session_date, f.symbol, f.side, f.shares, f.price, f.cash_usd, f.cost_usd, f.reason) for f in result.fills]
    assert q(world, "SELECT symbol, shares FROM book_positions WHERE strategy_id = %s ORDER BY symbol", (SID,)) == [
        (p.symbol, p.shares) for p in result.open_at_end
    ]

    # Not vacuous: every resize week traded, trimming or topping up the frozen basket only.
    resized = q(
        world,
        "SELECT session_date, symbol, reason FROM book_fills WHERE strategy_id = %s AND session_date = ANY(%s)",
        (SID, list(RESIZES)),
    )
    assert set(resized) == (
        {(OCT19, s, "trim") for s in OCTOBER}
        | {(OCT26, s, "add") for s in OCTOBER[:3]}
        | {(NOV9, s, "add") for s in NOVEMBER}
        | {(NOV16, s, "trim") for s in NOVEMBER}
    )

    found = results(world)
    r = found[SID]
    assert r.status == "ok", text(found)
    assert (r.sessions, r.paper_start, r.last_session) == (len(dates.sessions(PAPER_START, LAST)), PAPER_START, LAST)
    assert paper_check.execute(world) == 0


def test_resize_decisions_rescale_the_stored_rank_basket(world):
    step(world)
    # The kickoff, the rank and every resize, the rank and the resize after it decided in one
    # catch-up night (2026-11-06), each equal to run_book's weights.
    assert stored_weights(world) == EXPECTED_WEIGHTS
    # A resize-only decision stores no evidence; the kickoff and the rank keep theirs.
    assert evidence_counts(world, SID) == [
        (d, len(EXPECTED_WEIGHTS[d]) if d in RESIZES else 0, len(EXPECTED_WEIGHTS[d])) for d in DECISIONS
    ]
    # The stopped-out position: trimmed on the first resize, stopped intraday, never bought back.
    assert q(
        world,
        "SELECT session_date, side, reason FROM book_fills WHERE strategy_id = %s AND symbol = %s "
        "ORDER BY session_date, seq",
        (SID, STOPPED),
    ) == [(PAPER_START, "buy", "entry"), (OCT19, "sell", "trim"), (STOP_DAY, "sell", "sl")]
    assert STOPPED not in {s for s, _ in stored_weights(world)[OCT26]}


# ---- world one with a 2:1 split on a held symbol inside the month ------------------------------


def test_a_split_inside_the_month_on_a_held_symbol(split_world):
    step(split_world, split=True)
    assert q(split_world, "SELECT symbol, execution_date, applied FROM split_adjustments") == [
        (SPLIT_SYMBOL, NOV9, True)
    ]
    # The resize after the split re-scales the stored November rank: same weights as without it.
    assert stored_weights(split_world) == EXPECTED_WEIGHTS

    found = results(split_world)
    r = found[SID]
    assert r.status != "mismatch", text(found)
    assert r.status == "split-affected", text(found)  # the judge's defined status for a held split
    assert r.splits == ((SPLIT_SYMBOL, NOV9),)
    assert paper_check.execute(split_world) == 0

    # The same book as the unsplit world, to fractional-share rounding.
    unsplit = run_rules(
        memory_market(), SCRIPTED, PARAMS, RULES, PAPER_START, LAST,
        usd_idr=USD_IDR, kickoff=PAPER_START, initial_idr=PAPER_INITIAL_IDR,
    )
    got = q(split_world, "SELECT date, equity_usd FROM equity_snapshots WHERE strategy_id = %s ORDER BY date", (SID,))
    assert [d for d, _ in got] == [s.date for s in unsplit.snapshots]
    for (d, equity), s in zip(got, unsplit.snapshots):
        assert abs(equity - s.equity_usd) <= Decimal("0.05"), (d, equity, s.equity_usd)
    held = dict(q(split_world, "SELECT symbol, shares FROM book_positions WHERE strategy_id = %s", (SID,)))
    want = {p.symbol: p.shares for p in unsplit.open_at_end}
    assert set(held) == set(want)
    assert abs(held[SPLIT_SYMBOL] - 2 * want[SPLIT_SYMBOL]) <= Decimal("0.0010")


# ---- promote --fractional of a split-cadence lab variant, then nights --------------------------


PROMOTE_ID = "RMW-FR"
M0022_VARIANT = "M0022-W-TV14"


class _Borrowed:
    """A connection ``promote`` may close: ``close()`` only rolls back (test_promote_command's)."""

    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        self._conn.rollback()


def test_promote_fractional_puts_a_split_cadence_variant_on_paper(pg, monkeypatch, tmp_path):
    from seer_engine.lab.methods.m0022_weekly_brake_residual import METHOD as M0022
    from seer_engine.lab.methods.m0022_weekly_brake_residual import WEEKLYBRAKE

    candidate = next(c for c in M0022.candidates if c.id == M0022_VARIANT)
    assert candidate.rules is MONTHLY_RANK_WEEKLY_RESIZE  # whole shares in the lab
    # The one RESOLVER line and one EVIDENCE entry a real promotion of M0022 would commit.
    monkeypatch.setitem(roster.RESOLVER, "WEEKLYBRAKE", roster.Binding(obj=WEEKLYBRAKE, params=candidate.params))
    residvol = evidence.EVIDENCE["RESIDVOL"]
    monkeypatch.setitem(
        evidence.EVIDENCE, "WEEKLYBRAKE", lambda market, params, d, symbols: residvol(market, params.inner, d, symbols)
    )
    _seed(pg, promote_bars(), PROMOTE_STOCKS)

    lab = lab_store.connect(tmp_path / "lab.sqlite")
    try:
        with lab:
            lab_store.add_method(
                lab, id="M0022", name="weekly brake", family="stock-residual-momentum",
                source_kind="knowledge", hypothesis="h", status="idea",
            )
            lab_store.update_method(lab, "M0022", status="rejected")
        monkeypatch.setattr(promote.db, "connect", lambda url=None: _Borrowed(pg))
        monkeypatch.setattr(lab_store, "connect", lambda path=None: _Borrowed(lab))
        args = argparse.Namespace(
            method="M0022", candidate=M0022_VARIANT, id=PROMOTE_ID, name="RMW · Weekly brake",
            sub="Picks monthly, adjusts weekly", icon="flask-conical", sort=None,
            gate_note="No backtest gate: a test promotion", gate_not_applicable=False, fractional=True,
            retire=None, lab_db=tmp_path / "lab.sqlite", lab_status_stays=True, dry_run=False, verbose=0,
        )
        assert promote.run(args) == 0
    finally:
        lab.close()

    assert q(
        pg,
        "SELECT engine, rules_id, object_name, paper_start, promoted_from, status FROM strategies WHERE id = %s",
        (PROMOTE_ID,),
    ) == [("book", FRAC, "WEEKLYBRAKE", None, "M0022", "active")]

    _only(pg, PROMOTE_ID)
    for d in dates.sessions(FIRST_NIGHT, LAST):
        night(pg, d)

    assert q(pg, "SELECT kickoff_session FROM paper_state WHERE strategy_id = %s", (PROMOTE_ID,)) == [(PAPER_START,)]
    decided = evidence_counts(pg, PROMOTE_ID)
    assert [d for d, _, _ in decided] == list(DECISIONS)
    for d, unexplained, n in decided:
        assert n > 0, d
        if d in RESIZES:
            assert unexplained == n, d  # a resize-only decision stores no evidence
    # Checked before planning on this world: M0022-W-TV14 in fractional shares trims on 2026-11-16.
    assert q(
        pg,
        "SELECT count(*) FROM book_fills WHERE strategy_id = %s AND session_date = ANY(%s) AND reason IN ('trim', 'add')",
        (PROMOTE_ID, list(RESIZES)),
    )[0][0] >= 1

    found = results(pg)
    r = found[PROMOTE_ID]
    assert r.status == "ok", text(found)
    assert (r.sessions, r.paper_start, r.last_session) == (len(dates.sessions(PAPER_START, LAST)), PAPER_START, LAST)
    assert paper_check.execute(pg) == 0
```
**Impact:** new tests only. The module-level `assert isinstance(SCRIPTED, Allocator)` runs at
collection time and fails fast if the protocol changes. Both worlds retire every seeded roster
row before the first night (`_only`), so only the entry under test trades. The retired rows never
start, so `paper_check` reports them `not-started`, which `paper_check.execute(conn)` (no
`--require-sessions`) accepts.

Notes for the implementer:
- `MONTHLY_RANK_WEEKLY_RESIZE_FRAC` is defined in `seer_engine.sim.rules` and re-exported from
  `seer_engine.sim` (Phase 1, reconciled); import it from `seer_engine.sim.rules` as written.
- The `RESOLVER`/`EVIDENCE` entries for `WEEKLYBRAKE` exist ONLY through `monkeypatch` inside the
  promote test. Do not commit them, do not touch the `RM-FR` roster entry, and do not change
  `PAPER_PAUSED` in `nightly.yml` (index "On Landing": another session owns those).
- If `test_promote_fractional_puts_a_split_cadence_variant_on_paper` fails on the
  "trim or add on a resize week" count, the paper night or the replay is wrong. Do not drop the
  assertion. The `run_rules` experiment behind it (M0022-W-TV14, fractional, kickoff 2026-10-14,
  this exact generator) trimmed AAPL on 2026-11-16.
- Runtime: about 85 paper nights across the file. Each night loads a window of 9 or 25 symbols,
  which is comparable to `test_paper_check.py`.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/paper-split-cadence && engine/.venv/bin/ruff check engine`
**Tests:**
```bash
cd /home/miftah/.worktrees/seer/paper-split-cadence
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests/test_paper_split_cadence.py -q
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests/test_paper_command.py engine/tests/test_paper_check.py engine/tests/test_paper_roster.py engine/tests/test_promote_command.py engine/tests/test_paper_book.py -q
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q   # only the two known Python-3.12-only failures allowed
```
**Manual check:** `git diff --stat` touches only `engine/src/seer_engine/commands/paper.py` and
`engine/tests/test_paper_split_cadence.py` (plus Phase 1's files). `git diff` on
`commands/paper.py` shows that the `resize_cadence is None` branches call `decide_book` with
exactly today's arguments.
**Exit criteria:** A `monthly-rank-weekly-resize-frac` roster entry paper-trades over 20 nights.
Its snapshots, fills and positions equal `run_rules(..., kickoff=stored kickoff)`. Its stored
decisions equal `run_book`'s weights, including after a catch-up across the rank and after a 2:1
split on a held symbol. Resize-only decisions carry no evidence. The stopped-out S03 is never
re-bought on a resize week. `paper_check` reports `ok` without the split and `split-affected`
with it, never `mismatch`. A `promote --fractional` of `M0022-W-TV14` writes
`rules_id = 'monthly-rank-weekly-resize-frac'` and trades 25 nights to a green `paper_check`.
Every existing test is unedited and green.

## Handoffs

- **Phase 1** (R1, R3, R5): everything under "Requires". In particular, `decide_book`'s
  `last_rank`/`marks` keywords, `last_rank_session`, `rank_basket`, `needs_kickoff` on
  `is_rank_session`, `expected_book` for split rules, and the `MONTHLY_RANK_WEEKLY_RESIZE_FRAC`
  preset with its `fractional_twin` mapping. This phase's tests are the end-to-end proof of those
  pieces, so a Phase 1 deviation in helper names or semantics (for example, `kickoff` meaning
  anything other than the stored `paper_state.kickoff_session`) must be mirrored in Step 3.
- **Phase 3** (R6): the Positions page reads `book_targets`. A resize-only session's rows now
  exist with `evidence` NULL, and `book_previews` on a resize night equals the resize decision.
  Explain needs no change: it selects only targets not already held, and every resize target is
  held.
- **Not in this plan set:** a fractional twin for `MONTHLY_RANK_WEEKLY_RESIZE_TBILL` (out of
  scope per the index). Committing `RESOLVER`/`EVIDENCE` entries for `WEEKLYBRAKE` is not done
  either: M0022 was rejected by the lab, and the test borrows those lines through `monkeypatch`.

## Rollback

Revert this phase's commit. That restores today's `_start`/`_step_book` bodies and removes
`test_paper_split_cadence.py`. Nothing else depends on the two private helpers. There is no
migration or data to undo, and no live roster row uses a split rule set. Phase 1 can stay: with
this phase reverted, a split-cadence entry would get `last_rank=None` and never resize. That is
harmless while no such entry exists. Revert this phase before reverting Phase 1.
