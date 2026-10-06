# Phase 1: Pure split-cadence decision, replay and fractional preset

**Plan set:** `PAPER_SPLIT_CADENCE_PLAN.md`
**Analysis:** `20261007-011957-S9C4_code_analyzer.md`
**Satisfies:** R1, R3, R5 (holds R4) — `decide_book` decides a split-cadence rule set's resize weeks exactly as `run_book` does; the replay agrees; `promote --fractional` has a preset to map a split-cadence winner to
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/paper` (+ `engine/src/seer_engine/sim`)

---

## Goal

`paper.book.decide_book` stops refusing rule sets with a `resize_cadence`: given the last rank
basket (pre-idle) and the book's marks it returns, on a resize-only session, exactly
`run_book`'s `_with_idle(_rescaled(...))`; rank sessions and every rule set without a
`resize_cadence` are unchanged byte for byte. Two pure helpers (`last_rank_session`,
`rank_basket`) let a caller rebuild `run_book`'s `last_rank` loop variable from the calendar and
the stored rows; `needs_kickoff` kicks off on a resize-only Monday; `paper.replay.expected_book`
decides resize sessions from its own last rank basket; and `MONTHLY_RANK_WEEKLY_RESIZE_FRAC`
is the last preset, so `fractional_twin(MONTHLY_RANK_WEEKLY_RESIZE)` maps to it.

This plan was prototyped in a scratch copy of `engine/` (the worktree was not touched) and every
test below ran green there: `test_paper_book.py` 58 passed, `test_paper_kickoff.py` 8,
`test_paper_replay.py` 49, `test_sim_rules.py` + `test_promote_command.py` 57 (+12 PG skips);
`test_book_runner.py`, `test_paper_roster.py`, `test_strategy_purity.py`, `test_sim_purity.py`
green; `ruff check` clean. The rest of the suite was unchanged: only the two known
Python-3.12-only failures (`test_f_fundamental.py::test_allocator_shape`,
`test_market_fundamentals.py::test_adding_the_hook_does_not_change_the_allocator_check`) failed.

## Interface Contract

**Deletes:** the split-cadence refusal in `paper.book.decide_book` (`paper/book.py:178-182`, the
`ValueError("... paper trading cannot decide them yet ...")`) and its `assert` at `:185`;
the test `tests/test_paper_book.py::test_decide_book_refuses_a_split_cadence_rule_set` (`:641-649`).

**Renames:** none.

**Creates:**
- `sim.rules.MONTHLY_RANK_WEEKLY_RESIZE_FRAC` = `replace(MONTHLY_RANK_WEEKLY_RESIZE, id="monthly-rank-weekly-resize-frac", fractional=True)`, appended LAST to `PRESETS`; re-exported as `seer_engine.sim.MONTHLY_RANK_WEEKLY_RESIZE_FRAC`. Preset id: **`monthly-rank-weekly-resize-frac`**.
- `paper.book.last_rank_session(rules: TradeRules, paper_start: date, kickoff: date | None, session: date) -> date | None`
- `paper.book.rank_basket(targets: Sequence[Target], idle_symbol: str | None) -> tuple[Target, ...]`
- private `paper.book._wanted`, `paper.book._last_rank`, `paper.book._marks` (helpers of `decide_book`).
- test helpers in `tests/test_paper_book.py`: `split_market`, `Breathe`/`BREATHE`, `SplitRun`, `split_paper_run`, constants `SPLIT_DAYS`, `SPLIT_END`, `DDD_CRASH`, `AAA_SPLIT`, `SPLIT_RULES`, `W_RANK`.

**Signature changes:**
`decide_book(market, allocator, params, rules, data_date, held, *, force=False)` ->
```python
def decide_book(
    market: Market,
    allocator: Allocator,
    params: Any,
    rules: TradeRules,
    data_date: date,
    held: AbstractSet[str],
    *,
    force: bool = False,
    last_rank: tuple[Target, ...] | None = None,
    marks: Mapping[str, Decimal] | None = None,
) -> tuple[tuple[Target, ...] | None, bool]
```
Semantics (the contract phase 2 codes against):
- `rank = force or is_rank_session(rules, next_session(data_date))` -> today's path, unchanged; `last_rank` and `marks` are not read.
- elif `is_resize_session(rules, S)` and `last_rank is not None` -> the allocator is called once (same dispatch, `MarketAware` included) and the result is `book_runner._with_idle(market, rules, book_runner._rescaled(market, last_rank, wanted, held - {idle}, data_date, marks), data_date)`. `marks` is REQUIRED here (ValueError mentioning "marks" when None). `last_rank` must be a `tuple` of `Target` (TypeError otherwise; a list is refused — pass `rank_basket(...)`, which returns a tuple). `last_rank == ()` is a valid basket (an empty rank): the result is `_with_idle(())`.
- else `(None, False)`, allocator not called (this includes a resize session with `last_rank=None`: no rank yet).
- `marks`: `Mapping[str, Decimal]` (TypeError on a non-str key or a non-Decimal value); the caller passes `{p.symbol: p.mark for p in book.positions}` of the same book whose `held()` it passes.

`needs_kickoff(rules, paper_start, session, kickoff)`: signature unchanged; it tests `is_rank_session` instead of `is_decision_session` (identical for every rule set without `resize_cadence`).

`last_rank_session`: the latest `d` in `[paper_start, session)` with `d == kickoff or is_rank_session(rules, d)`; None when there is none. It checks for book rules and that `paper_start`, `session` and `kickoff` (when given) are NYSE sessions.
`rank_basket`: `tuple(targets)` minus ONE trailing row whose symbol is `idle_symbol`. ValueError when `idle_symbol` appears anywhere else; TypeError on a non-sequence (str and Mapping included) or a non-`Target` element. `rank_basket((), x) == ()`, `rank_basket((idle_row,), idle) == ()`.

**Requires (from earlier phases):** nothing.

**Leaves alone (owned by others):** `commands/paper.py` and `paper/store.py` (phase 2). They keep
calling `decide_book` without `last_rank`/`marks`, which is valid and unchanged for every roster
rule set. Every `web/*` file (phase 3). `backtest/*`, `sim/book.py`, the `sim/rules.py` session
functions and `RESIZE_BAND` (closed record). `tests/test_paper_roster.py::PINS` (not edited).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/sim/rules.py` | modify | `:182` add `MONTHLY_RANK_WEEKLY_RESIZE_FRAC`; `:196` append it to `PRESETS` |
| `engine/src/seer_engine/sim/__init__.py` | modify | `:61` import, `:92` `__all__` entry |
| `engine/src/seer_engine/paper/book.py` | modify | module docstring `:7-12`, `:26-28`; imports `:43`, `:58`; replace `decide_book` + `needs_kickoff` (`:135-223`) with `_wanted`, `_last_rank`, `_marks`, `decide_book`, `needs_kickoff`, `last_rank_session`, `rank_basket` |
| `engine/src/seer_engine/paper/replay.py` | modify | docstring `:17-19`; imports `:46`, `:60`; `expected_book` decisions loop `:359-372` |
| `engine/tests/test_paper_book.py` | modify | imports `:25-50` (`_ZERO` at `:52` stays); delete refusal test `:641-649`; append section 5 (split cadence) |
| `engine/tests/test_paper_kickoff.py` | modify | imports `:3-8`; append split-cadence kickoff and `last_rank_session` tests |
| `engine/tests/test_paper_replay.py` | modify | imports `:19-45`; append split-cadence replay tests |
| `engine/tests/test_sim_rules.py` | modify | import `:25`; preset id list `:88-105`; new preset test after `:339` |
| `engine/tests/test_promote_command.py` | modify | `test_fractional_twin_maps_a_whole_share_preset_to_its_fractional_preset` (`:351-357`) |

## Implementation Steps

### Step 0: A venv for this worktree
**File:** `engine/.venv` (not committed)
**Change:** the worktree has no `engine/.venv`, and main's venv would test main's tree.
**Code:**
```bash
cd /home/miftah/.worktrees/seer/paper-split-cadence
python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q   # baseline: only the two Python-3.12-only failures
```
**Impact:** none on the tree.

### Step 1: The fractional split-cadence preset
**File:** `engine/src/seer_engine/sim/rules.py:178-197`
**Change:** after `MONTHLY_RANK_WEEKLY_RESIZE_TBILL` (ends `:182`), add the preset. Append it as the
LAST element of `PRESETS` (after `MONTHLY_HOLD_FRAC`, `:196`). Appending keeps every earlier
index, so `backtest/registry.py` and pinned digests do not move (registry candidates use
presets by identity, and none uses the new one).
**Code** (the block from `:178` to the end of `PRESETS`, complete):
```python
# Monthly basket, weekly exposure: the lab's "weekly risk checks with monthly re-ranking" wish.
MONTHLY_RANK_WEEKLY_RESIZE = replace(MONTHLY_HOLD, id="monthly-rank-weekly-resize", resize_cadence="weekly")
MONTHLY_RANK_WEEKLY_RESIZE_TBILL = replace(
    MONTHLY_RANK_WEEKLY_RESIZE, id="monthly-rank-weekly-resize-tbill", idle_symbol="BIL"
)
# The split cadence in fractional shares: what `promote --fractional` maps a monthly-rank-weekly-resize
# lab winner to, as monthly-hold-frac is monthly-hold's (paper split cadence, 2026-10-07).
MONTHLY_RANK_WEEKLY_RESIZE_FRAC = replace(
    MONTHLY_RANK_WEEKLY_RESIZE, id="monthly-rank-weekly-resize-frac", fractional=True
)

PRESETS: tuple[TradeRules, ...] = (
    DESIGN_V0,
    MONTHLY_HOLD,
    MONTHLY_HOLD_TBILL,
    WEEKLY_HOLD,
    DAILY_SWITCH,
    DAILY_SWITCH_TBILL,
    SWING_T10,
    SWING_T20,
    SWING_T20_OPEN,
    MONTHLY_RANK_WEEKLY_RESIZE,
    MONTHLY_RANK_WEEKLY_RESIZE_TBILL,
    MONTHLY_HOLD_FRAC,
    MONTHLY_RANK_WEEKLY_RESIZE_FRAC,
)
```
**Impact:** `roster.rules_for("monthly-rank-weekly-resize-frac")` now resolves (the roster's `_PRESETS`
is built from `PRESETS`). `promote.fractional_twin(MONTHLY_RANK_WEEKLY_RESIZE)` returns it with
no code change in `promote.py`, which scans `PRESETS`. `fractional_twin(MONTHLY_RANK_WEEKLY_RESIZE_TBILL)`
still raises because the idle symbol differs. `test_sim_rules.py::test_preset_ids_are_unique_and_in_order`
must be updated (Step 8).

### Step 2: Export the preset from `seer_engine.sim`
**File:** `engine/src/seer_engine/sim/__init__.py:61` and `:92`
**Change:** in the `from seer_engine.sim.rules import (...)` list, add `MONTHLY_RANK_WEEKLY_RESIZE_FRAC,`
after `MONTHLY_RANK_WEEKLY_RESIZE,` (`:61`). In `__all__`, add `"MONTHLY_RANK_WEEKLY_RESIZE_FRAC",`
after `"MONTHLY_RANK_WEEKLY_RESIZE",` (`:92`).
**Code:**
```python
# import list, lines 61-63 after the edit
    MONTHLY_RANK_WEEKLY_RESIZE,
    MONTHLY_RANK_WEEKLY_RESIZE_FRAC,
    MONTHLY_RANK_WEEKLY_RESIZE_TBILL,
```
```python
# __all__, lines 93-95 after the edit
    "MONTHLY_RANK_WEEKLY_RESIZE",
    "MONTHLY_RANK_WEEKLY_RESIZE_FRAC",
    "MONTHLY_RANK_WEEKLY_RESIZE_TBILL",
```
**Impact:** none beyond the export.

### Step 3: `paper/book.py` module docstring and imports
**File:** `engine/src/seer_engine/paper/book.py:7-12`, `:26-28`, `:43`, `:58`
**Change:** describe the resize path. Import `_rescaled` (never copy it) and `is_resize_session`, and
drop the `is_decision_session` import, which is no longer used.
**Code** — replace the paragraph at `:7-12` with:
```text
``decide_book`` (the night of ``data_date``, after its bars arrived) is ``run_book``'s step 1,
1b and 2 for ``S = next_session(data_date)``: ``None`` when ``S`` is not a decision session under
``rules``; on a rank session ``allocator.targets`` on every history cut at ``data_date``, the
members on ``data_date`` and the symbols held at night minus the idle instrument; on a
resize-only session (split-cadence rules) the last rank basket re-scaled by
``book_runner._rescaled``; then ``book_runner._with_idle`` (both imported, not copied). It
returns ``(targets, idle_added)``; the caller persists both and hands them back to
``settle_book`` for ``S``. ``run_book`` keeps the last rank basket in a loop variable; paper
keeps none, so the caller passes it in: the targets stored for ``last_rank_session(...)``,
through ``rank_basket``.
```
Replace the sentence at `:26-28` (up to and including "(tests/test_paper_book.py).") with:
```text
Looping ``decide_book`` then ``settle_book`` from ``new_book(cash0)`` with ``data_date =
prev_session(start)`` and no splits reproduces ``run_book`` field for field
(tests/test_paper_book.py), split-cadence rules included when each night passes ``last_rank``
and the book's ``marks``.
```
Imports (`:43` and `:58`):
```python
from seer_engine.backtest.book_runner import DividendMap, _dividends_on, _invested, _rescaled, _with_idle
```
```python
from seer_engine.sim.rules import TradeRules, is_rank_session, is_resize_session
```
**Impact:** none at runtime.

### Step 4: `decide_book` split path, `needs_kickoff`, and the two helpers
**File:** `engine/src/seer_engine/paper/book.py:135-223`
**Change:** replace everything from `def decide_book(` (`:135`) up to (not including)
`def settle_book(` (`:226`) with the block below. What it does:
- `_wanted` is the allocator call lifted verbatim out of today's `decide_book` (members on
  `data_date`, history cut at `data_date`, the `MarketAware` branch with its comment). It returns
  `tuple(...)`. The rank path calls it and then `_with_idle`, which is today's expression.
- The refusal and its `assert` are gone. `rank = force or is_rank_session(...)`. When the session
  is not a rank and either `last_rank is None` or `is_resize_session` is False, it returns
  `(None, False)` without calling the allocator. For a rule set without `resize_cadence`,
  `is_resize_session` is always False and `is_decision_session == is_rank_session`, so this is
  exactly today's early return.
- Resize path: `_rescaled(market, last_rank, wanted, mine, data_date, marks)` and then
  `_with_idle`. These are `run_book`'s lines 297-300 with the argument in place of the loop variable.
- `needs_kickoff`: `is_decision_session` becomes `is_rank_session` (Decisions: "A clock that starts on
  a resize-only Monday").
**Code:**
```python
def _wanted(
    market: Market, allocator: Allocator, params: Any, data_date: date, mine: frozenset[str]
) -> tuple[Target, ...]:
    """``allocator``'s targets for the night of ``data_date``: ``run_book``'s allocator call.

    ``market.membership.members_on(data_date)``, every history cut at ``data_date``, ``mine``
    (the held symbols, the idle instrument left out) and ``params``. A ``MarketAware`` allocator
    (``strategies.allocator.MarketAware``: it defines ``prepare_market``) takes the prepared
    branch -- ``targets_prepared(prepare_for(allocator, market_cut_at_data_date), ...)``. It must:
    such an allocator reads part of the ``Market`` that ``history`` cannot carry, and for
    ``FUNDAMENTAL`` the history-only path is not a worse answer but a fixed empty one (its
    docstring: with no panel no symbol is eligible, so ``targets`` returns ``()``). The branch is
    keyed on the protocol and nothing else, so an allocator without ``prepare_market`` runs the
    plain expression unchanged.
    """
    members = market.membership.members_on(data_date)
    history = {s: h.upto(data_date) for s, h in market.history.items()}
    if isinstance(allocator, MarketAware):
        # A MarketAware allocator reads more of the Market than its bars (FUNDAMENTAL reads
        # market.fundamentals), so handing it the history dict alone is not a degraded result,
        # it is a WRONG one: f_fundamental's history-only path finds every symbol ineligible
        # and returns (), forever, silently. This is run_book's own dispatch
        # (backtest/book_runner.py:289) brought to the nightly decision.
        #
        # The Market handed over carries `history` -- the same dict the plain path passes, cut
        # at data_date -- so no bar dated after data_date is reachable on either path. The
        # panel needs no cut of its own: panel.as_of(symbol, d) answers from facts with
        # filed <= d and only those, and `filed` IS the no-look-ahead boundary
        # (005_fundamentals.sql, "filed IS THE ONLY NO-LOOK-AHEAD BOUNDARY").
        prepared = prepare_for(allocator, replace(market, history=history))
        return tuple(allocator.targets_prepared(prepared, members, data_date, mine, params))
    return tuple(allocator.targets(history, members, data_date, mine, params))


def _last_rank(last_rank: object) -> tuple[Target, ...] | None:
    if last_rank is None:
        return None
    if not isinstance(last_rank, tuple):
        raise TypeError(f"last_rank must be a tuple of Target or None, got {type(last_rank).__name__}")
    for t in last_rank:
        if not isinstance(t, Target):
            raise TypeError(f"last_rank holds Targets, got {type(t).__name__}")
    return last_rank


def _marks(marks: object) -> Mapping[str, Decimal] | None:
    if marks is None:
        return None
    if not isinstance(marks, Mapping):
        raise TypeError(f"marks must be a Mapping of symbol -> Decimal or None, got {type(marks).__name__}")
    for symbol, mark in marks.items():
        if not isinstance(symbol, str):
            raise TypeError(f"marks keys are symbols (str), got {type(symbol).__name__}")
        if not isinstance(mark, Decimal):
            raise TypeError(f"mark for {symbol} must be a Decimal, got {type(mark).__name__}")
    return marks


def decide_book(
    market: Market,
    allocator: Allocator,
    params: Any,
    rules: TradeRules,
    data_date: date,
    held: AbstractSet[str],
    *,
    force: bool = False,
    last_rank: tuple[Target, ...] | None = None,
    marks: Mapping[str, Decimal] | None = None,
) -> tuple[tuple[Target, ...] | None, bool]:
    """The targets for ``S = next_session(data_date)`` and whether the idle residual was appended.

    Exactly ``run_book``'s decision for ``S``. ``held`` is the set of symbols the book holds at
    the night of ``data_date`` (``book.held()`` after that session settled); the allocator sees
    it minus ``rules.idle_symbol``. Nothing dated after ``data_date`` is read.

    - A RANK session -- ``force`` (the kickoff, ``needs_kickoff``; also the nightly preview of
      what the book would pick now) or ``is_rank_session(rules, S)``: ``_wanted`` (the allocator
      on every history cut at ``data_date``, the members on ``data_date``, the held symbols,
      ``params``; a ``MarketAware`` allocator through its prepared branch), then
      ``book_runner._with_idle``. ``last_rank`` and ``marks`` are not read.
    - A RESIZE-ONLY session (``is_resize_session(rules, S)``, only under a ``resize_cadence``)
      with ``last_rank`` given: the allocator is called the same way, but only its total weight
      is used: ``book_runner._with_idle(book_runner._rescaled(market, last_rank, wanted, held -
      idle, data_date, marks))`` (both imported, not copied). ``last_rank`` is the last rank
      session's targets WITHOUT the idle row (``rank_basket``), ``()`` when that rank chose
      nothing; only each target's ``symbol`` and ``weight`` reach the result, so the basket may
      be in pre- or post-split units. ``marks`` is ``{p.symbol: p.mark for p in
      book.positions}`` of the same book ``held`` came from (``_rescaled``'s price for a held
      symbol without a bar on ``data_date``); a ValueError when it is missing here.
    - Otherwise ``(None, False)`` and the allocator is not called: a session that is neither,
      and a resize-only session with ``last_rank`` None (no rank yet: ``run_book`` does not
      decide a resize session before its first rank either).

    For every rule set without a ``resize_cadence`` no session is resize-only, so the result is
    the rank-or-nothing decision it always was, whatever ``last_rank`` and ``marks`` hold.
    """
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    if not isinstance(allocator, Allocator):
        raise TypeError(f"allocator must be an Allocator, got {type(allocator).__name__}")
    _book_rules(rules)
    _session("data_date", data_date)
    held_now = _held(held)
    basket_then = _last_rank(last_rank)
    marks_now = _marks(marks)
    session = dates.next_session(data_date)
    rank = force or is_rank_session(rules, session)
    if not rank and (basket_then is None or not is_resize_session(rules, session)):
        return None, False
    if not rank and marks_now is None:
        raise ValueError(
            f"{session} is a resize-only session under {rules.id!r}: decide_book needs the book's marks "
            "(symbol -> mark) to re-scale the last rank basket"
        )
    # The idle position is the runner's residual, never a family's (as run_book).
    mine = held_now - {rules.idle_symbol} if rules.idle_symbol is not None else held_now
    wanted = _wanted(market, allocator, params, data_date, mine)
    if rank:
        return _with_idle(market, rules, wanted, data_date)
    assert basket_then is not None and marks_now is not None
    basket = _rescaled(market, basket_then, wanted, mine, data_date, marks_now)
    return _with_idle(market, rules, basket, data_date)


def needs_kickoff(rules: TradeRules, paper_start: date, session: date, kickoff: date | None) -> bool:
    """True when ``session`` must be the book's kickoff: its first decision, off the cadence.

    A book strategy whose paper clock starts between two rank sessions would otherwise hold its
    starting cash until the next one (up to a month for monthly rules). It ranks instead on the
    first session it can, once: when no kickoff is stored yet (``kickoff`` None), ``session`` is
    not a rank session, and no rank session lies in ``[paper_start, session)`` (one there was
    already a first decision). Replays rank on the stored kickoff (``run_book(kickoff=...)``).

    A resize-only session (split-cadence rules) is not a rank session: before the first rank
    there is no basket to re-scale, so ``run_book`` does not decide it, and a clock starting on
    one kicks off there. Without a ``resize_cadence`` every decision session is a rank session,
    so this is the test it always was.
    """
    _book_rules(rules)
    _session("paper_start", paper_start)
    _session("session", session)
    if kickoff is not None or is_rank_session(rules, session):
        return False
    return not any(is_rank_session(rules, s) for s in dates.sessions(paper_start, session) if s < session)


def last_rank_session(rules: TradeRules, paper_start: date, kickoff: date | None, session: date) -> date | None:
    """The session whose decision holds the basket a resize-only ``session`` re-scales, or None.

    The latest ``d`` in ``[paper_start, session)`` that ranked: ``is_rank_session(rules, d)`` or
    ``d == kickoff`` (the stored kickoff session) -- ``run_book``'s ``last_rank`` variable, read
    off the calendar instead of a loop. Paper decides every session in order, so that session's
    stored targets (``rank_basket`` of them; ``()`` when it chose nothing and wrote no row) are
    the basket exactly. None when nothing ranked before ``session``: ``decide_book`` then decides
    no resize session, as ``run_book`` does not.
    """
    _book_rules(rules)
    _session("paper_start", paper_start)
    _session("session", session)
    if kickoff is not None:
        _session("kickoff", kickoff)
    for d in reversed(dates.sessions(paper_start, session)):
        if d < session and (d == kickoff or is_rank_session(rules, d)):
            return d
    return None


def rank_basket(targets: Sequence[Target], idle_symbol: str | None) -> tuple[Target, ...]:
    """A rank decision's targets as ``decide_book``'s ``last_rank``: the idle row taken off.

    ``book_runner._with_idle`` appends at most one target, last, in ``idle_symbol``; an allocator
    that targets the idle symbol is a ValueError there, so a trailing ``idle_symbol`` row is the
    runner's residual and nothing else. A row in ``idle_symbol`` anywhere but last is a
    ValueError (those targets were not a decision). ``targets`` in rank order, as stored.
    """
    if isinstance(targets, (str, Mapping)) or not isinstance(targets, Sequence):
        raise TypeError(f"targets must be a sequence of Target, got {type(targets).__name__}")
    rows = tuple(targets)
    for t in rows:
        if not isinstance(t, Target):
            raise TypeError(f"targets holds Targets, got {type(t).__name__}")
    if idle_symbol is not None and rows and rows[-1].symbol == idle_symbol:
        rows = rows[:-1]
    if idle_symbol is not None and any(t.symbol == idle_symbol for t in rows):
        raise ValueError(f"the idle symbol {idle_symbol} is targeted before the last row; not a book decision")
    return rows
```
**Impact:** `commands/paper.py` (untouched, phase 2) still compiles and behaves as before for every
roster rule set: it passes neither `last_rank` nor `marks`, and no roster entry has a
`resize_cadence`. A split-cadence entry (none exists) would skip resize weeks silently between
this phase and phase 2, instead of failing loudly. See Handoffs.

### Step 5: `paper/replay.py` — the replay's own last rank basket
**File:** `engine/src/seer_engine/paper/replay.py:17-19`, `:46`, `:60`, `:359-372`
**Change:** the decisions loop tracks the expected pre-idle rank basket from its OWN rank and kickoff
decisions (`rank_basket(wanted, rules.idle_symbol)`). On a resize-only session that has a basket,
it passes the basket with `marks = {s: last_close(market, s, data_date) for s in held}`. The mark
`sim.book` leaves is the last close on or before the night, unquantized, and that is what
`last_close` returns. The skip condition is unchanged (`not kickoff and not is_decision_session`).
So for rule sets without `resize_cadence`, the loop calls `decide_book` on the same sessions with
the same arguments plus `last_rank=<tuple>`/`marks=None`, which the rank path never reads, and the
decisions are byte for byte the same.
**Code** — docstring bullet (replaces `:17-19`, the three lines that start with `  ``paper.book.decide_book`` on every decision`):
```text
  ``paper.book.decide_book`` on every decision session (and the stored kickoff session, forced)
  from ``paper_start`` through ``pending_session``, with the held set rebuilt
  from the run's fills; an empty decision is left out (it writes no ``book_targets`` row). Under
  split-cadence rules a resize-only session is decided from the replay's OWN last rank basket
  (``paper.book.rank_basket`` of its latest rank or kickoff decision) and marks (``last_close``
  of each held symbol), never from the stored rows.
```
Imports:
```python
from seer_engine.paper.book import decide_book, rank_basket
```
```python
from seer_engine.sim import (
    DESIGN_V0,
    Fill,
    Order,
    Portfolio,
    Position,
    Snapshot,
    Target,
    Trade,
    TradeRules,
    initial_cash_usd,
    is_decision_session,
    is_rank_session,
    new_portfolio,
)
```
Decisions loop: replace `:359-372` (from `    pending = dates.next_session(last)` through
`            decisions.append((session, tuple(wanted)))`) with:
```python
    pending = dates.next_session(last)
    decisions: list[tuple[date, tuple[Target, ...]]] = []
    pending_decision = False
    # The replay's own last rank basket (pre-idle), as run_book's loop keeps it: built from the
    # replay's rank decisions, never read from the stored rows, so the check stays a check. It
    # only matters under a resize_cadence; without one every decision session is a rank.
    last_rank: tuple[Target, ...] | None = None
    for session in dates.sessions(start, pending):
        kickoff = session == head.kickoff
        if not kickoff and not is_decision_session(rules, session):
            continue
        data_date = dates.prev_session(session)
        held = held_before(fills, session)
        rank = kickoff or is_rank_session(rules, session)
        marks: dict[str, Decimal] | None = None
        if not rank and last_rank is not None:
            # The book's marks the night of data_date: each held symbol's last close on or before it.
            marks = {symbol: last_close(market, symbol, data_date) for symbol in sorted(held)}
        wanted, _ = decide_book(
            market, allocator, params, rules, data_date, held, force=kickoff, last_rank=last_rank, marks=marks
        )
        if rank:
            if wanted is None:
                raise AssertionError(f"decide_book gave no decision for the rank session {session}")
            last_rank = rank_basket(wanted, rules.idle_symbol)
        if session == pending:
            pending_decision = wanted is not None
        if wanted:
            decisions.append((session, tuple(wanted)))
```
**Impact:** `paper_check` of a split-cadence strategy now compares resize decisions instead of
crashing on the refusal. Purity is unchanged (no new import outside `seer_engine`).

### Step 6: `test_paper_book.py` — replace the refusal test with night-by-night equality
**File:** `engine/tests/test_paper_book.py`
**Change:**
1. Imports (`:25-50`) become the block below. Line `:52` (`_ZERO = Decimal("0.0000")`) is NOT
   part of the range and must stay: `split_paper_run` below uses it. It adds `Callable`, `Mapping`, `dataclass`,
   `book_runner`, `last_rank_session`, `needs_kickoff`, `rank_basket`, `q`, the three split
   presets, `is_rank_session`, `is_resize_session` and `target_from_close`.
2. Delete `test_decide_book_refuses_a_split_cadence_rule_set` (`:641-649`, the end of the file).
3. Append section 5 below at the end of the file. Optionally, add a fifth item to the module
   docstring's list: "5. Split cadence: the night loop with last_rank read back from the stored
   rank decision equals run_book; decide_book's resize path; rank_basket."

`split_paper_run` is the paper night as phase 2 will wire it. It takes the kickoff from
`needs_kickoff`, `last_rank` from the decisions stored so far via `last_rank_session` +
`rank_basket` (an empty decision stores nothing), `marks` from the book, then calls `decide_book`.
It then calls `settle_book` with the night's splits. `test_paper_replay.py` also imports it (Step 9).

Scenarios covered, for all three split presets (whole shares, BIL idle, fractional):
- start on a rank day, on a mid-month Wednesday (kickoff), and on a resize-only Monday (kickoff);
- at least 12 resize weeks with real `trim` and `add` fills, plus dividends;
- a resize week never adds a new name, and it moves the freed weight to BIL;
- DDD is stopped out (`sl`) on 2025-03-12 and NOT re-bought on the 03-17, 03-24 and 03-31 resize
  weeks, although the allocator still wants it; it is re-bought on the 04-01 rank;
- a 2-for-1 split on AAA between the 03-03 rank (stored in pre-split units) and the 03-10 resize
  gives the same decisions as the unsplit history;
- the resize path checked by hand: idle, a dropped held name, no rank yet, marks required,
  rank/skip/force, rule sets without a split ignore the new arguments, argument checks;
- `rank_basket`.

**Code** — imports (replacing `:25-50`, from `from __future__ import annotations` through the `f_index` import; keep `_ZERO` at `:52`):
```python
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from functools import lru_cache
from typing import Any

import pytest
from allocatorkit import FIXED, FixedParams
from simkit import D, P
from stratkit import hist, mutate_from, session_days, truncate_before
from test_book_runner import SEED_DAYS, Scripted, seeded_market, wiring_market

from seer_engine import dates
from seer_engine.backtest import book_runner
from seer_engine.backtest.book_runner import BookResult, DividendMap, run_book
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.runner import INITIAL_IDR
from seer_engine.paper.book import (
    BookNight,
    decide_book,
    last_rank_session,
    needs_kickoff,
    rank_basket,
    settle_book,
)
from seer_engine.prices import Bar
from seer_engine.sim.book import Book, BookSnapshot, Position, Target, apply_book_split, new_book
from seer_engine.sim.model import initial_cash_usd, q
from seer_engine.sim.rules import (
    DESIGN_V0,
    MONTHLY_HOLD,
    MONTHLY_HOLD_TBILL,
    MONTHLY_RANK_WEEKLY_RESIZE,
    MONTHLY_RANK_WEEKLY_RESIZE_FRAC,
    MONTHLY_RANK_WEEKLY_RESIZE_TBILL,
    is_decision_session,
    is_rank_session,
    is_resize_session,
)
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.f_factor import FACTOR, FactorParams
from seer_engine.strategies.f_index import TIMING, TimingParams
```
Append at the end of the file (after `test_settle_book_argument_checks`, two blank lines):
```python
# =========================================================================== 5. split cadence
#
# MONTHLY_RANK_WEEKLY_RESIZE ranks on each month's first session and re-scales on every other
# week start. run_book keeps the last rank basket in a loop variable; the paper night has none,
# so `split_paper_run` reads it back the way the paper night does: the targets stored for
# last_rank_session(...) (an empty decision stores no row), through rank_basket, with the book's
# marks. Looping that from new_book(cash0) must equal run_book(kickoff=<the kickoff it chose>).
#
# SPLIT_DAYS: 2025-01-02 .. 2025-06-30. AAA 50 + 0.2 t, BBB 40 + 0.1 t, CCC 30 flat, BIL 100 flat
# (spread 0.05, not a member), DDD 60 + 0.1 t until 2025-03-12, when it opens at the previous
# close and trades down 25% intraday (below the 10% stop BREATHE puts on it) and stays there.

SPLIT_DAYS = dates.sessions(D("2025-01-02"), D("2025-06-30"))
SPLIT_END = SPLIT_DAYS[-1]
DDD_CRASH = D("2025-03-12")
AAA_SPLIT = D("2025-03-05")  # between the 03-03 rank and the 03-10 resize (split test only)
SPLIT_RULES = (MONTHLY_RANK_WEEKLY_RESIZE, MONTHLY_RANK_WEEKLY_RESIZE_TBILL, MONTHLY_RANK_WEEKLY_RESIZE_FRAC)


def split_market(*, aaa_split: bool = False) -> Market:
    """The split-cadence market. With ``aaa_split``: AAA before AAA_SPLIT as it traded (2x the
    adjusted prices), i.e. the database before the 2-for-1 split on AAA_SPLIT rewrote it."""
    n = len(SPLIT_DAYS)
    crash = SPLIT_DAYS.index(DDD_CRASH)
    aaa = [round(50.0 + 0.2 * t, 2) for t in range(n)]
    if aaa_split:
        cut = SPLIT_DAYS.index(AAA_SPLIT)
        aaa = [c * 2 if t < cut else c for t, c in enumerate(aaa)]
    ddd = [round(60.0 + 0.1 * t, 2) for t in range(n)]
    ddd = ddd[:crash] + [round(c * 0.75, 2) for c in ddd[crash:]]
    ddd_opens = list(ddd)
    ddd_opens[crash] = ddd[crash - 1]
    ddd_highs = [max(o, c) + 0.5 for o, c in zip(ddd_opens, ddd)]
    return Market(
        history={
            "AAA": hist("AAA", aaa, days=SPLIT_DAYS),
            "BBB": hist("BBB", [round(40.0 + 0.1 * t, 2) for t in range(n)], days=SPLIT_DAYS),
            "BIL": hist("BIL", [100.0] * n, days=SPLIT_DAYS, spread=0.05),
            "CCC": hist("CCC", [30.0] * n, days=SPLIT_DAYS),
            "DDD": hist("DDD", ddd, days=SPLIT_DAYS, opens=ddd_opens, highs=ddd_highs),
        },
        membership=Membership(tuple((s, D("2020-01-02"), None) for s in ("AAA", "BBB", "CCC", "DDD"))),
        fx=((D("2024-12-31"), Decimal("16000")),),
    )


# Two names chosen by data_date's month (a rank on the first session of month m+1 reads month m),
# each at half the exposure of data_date's ISO week. DDD carries a stop 10% under its close.
BREATHE_BASKETS = {1: ("AAA", "BBB"), 2: ("DDD", "AAA"), 3: ("DDD", "CCC"), 4: ("BBB", "CCC"), 5: ("AAA", "DDD"),
                   6: ("CCC", "BBB")}
BREATHE_EXPOSURE = ("0.9", "0.5", "0.7", "0.3", "0.8")


class Breathe:
    """A fixed-width basket whose exposure moves every week: what a split cadence is for."""

    id = "BREATHE"

    def lookback(self, params: Any) -> int:
        return 1

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ()

    def holds(self, params: Any) -> tuple[str, ...]:
        return ()

    def uses_members(self, params: Any) -> bool:
        return True

    def targets(self, history, members, data_date, held, params) -> tuple[Target, ...]:
        each = Decimal(BREATHE_EXPOSURE[data_date.isocalendar()[1] % len(BREATHE_EXPOSURE)]) / 2
        out: list[Target] = []
        for symbol in BREATHE_BASKETS[data_date.month]:
            h = history.get(symbol)
            i = None if h is None else h.index_of(data_date)
            if i is None or symbol not in members:
                continue
            close = float(h.close[i])
            t = target_from_close(symbol, close, each, stop=close * 0.9 if symbol == "DDD" else None)
            if t is not None:
                out.append(t)
        return tuple(out)

    def prepare(self, history):
        return dict(history)

    def targets_prepared(self, prepared, members, data_date, held, params) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


BREATHE = Breathe()


@dataclass(frozen=True)
class SplitRun:
    result: BookResult
    kickoff: date | None
    stored: dict[date, tuple[Target, ...]]  # book_targets: session -> the decision (no row when empty)
    decided: dict[date, tuple[Target, ...]]  # every decision, empty ones included


def split_paper_run(
    market_at: Callable[[date], Market],
    allocator: Any,
    params: Any,
    rules: Any,
    start: date,
    end: date,
    *,
    splits: Mapping[date, tuple[tuple[str, Decimal], ...]] | None = None,
    dividends: DividendMap | None = None,
    initial_idr: Decimal = INITIAL_IDR,
) -> SplitRun:
    """The paper night over a split-cadence rule set, one session at a time.

    ``market_at(d)``: the market as the database holds it the night of ``d`` (its bars through
    ``d``). Night of ``data_date``: the kickoff from ``needs_kickoff``, the last rank basket from
    the decisions stored so far (``last_rank_session`` -> ``rank_basket``), the marks from the
    book, then ``decide_book``. Night of S: ``settle_book`` with S's bars and the splits on S.
    """
    divs: DividendMap = {} if dividends is None else dividends
    split_on = {} if splits is None else splits
    rate = market_at(start).usd_idr_on(start)
    cash0 = initial_cash_usd(initial_idr, rate)
    book = new_book(cash0)
    data_date = dates.prev_session(start)
    snapshots = [BookSnapshot(date=data_date, cash_usd=book.cash, equity_usd=book.equity, invested_usd=_ZERO)]
    fills: list[Any] = []
    trades: list[Any] = []
    rejections: Counter[str] = Counter()
    dividends_usd = _ZERO
    stored: dict[date, tuple[Target, ...]] = {}
    decided: dict[date, tuple[Target, ...]] = {}
    kickoff: date | None = None

    def decide(d: date, now: Book) -> tuple[tuple[Target, ...] | None, bool]:
        nonlocal kickoff
        session = dates.next_session(d)
        force = needs_kickoff(rules, start, session, kickoff)
        rank_day = last_rank_session(rules, start, kickoff, session)
        last_rank = None if rank_day is None else rank_basket(stored.get(rank_day, ()), rules.idle_symbol)
        marks = {p.symbol: p.mark for p in now.positions}
        targets, idle_added = decide_book(market_at(d), allocator, params, rules, d, now.held(), force=force,
                                          last_rank=last_rank, marks=marks)
        if force:
            kickoff = session
        if targets is not None:
            decided[session] = targets
            if targets:
                stored[session] = targets
        return targets, idle_added

    targets, idle_added = decide(data_date, book)
    for session in dates.sessions(start, end):
        night_market = market_at(session)
        symbols = set(book.held())
        if targets is not None:
            symbols.update(t.symbol for t in targets)
        bars = night_market.bars_on(session, sorted(symbols))
        night = settle_book(book, session, bars, targets, idle_added, rules, divs, split_on.get(session, ()),
                            night_market.last_bar_date)
        book = night.book
        fills.extend(night.fills)
        trades.extend(night.trades)
        for _, amount in night.dividends:
            dividends_usd += amount
        for _, reason in night.rejected:
            rejections[reason] += 1
        snapshots.append(night.snapshot)
        data_date = session
        targets, idle_added = decide(data_date, book)

    costs_usd = _ZERO
    for f in fills:
        costs_usd += f.cost_usd
    result = BookResult(
        allocator_id=allocator.id,
        params=params,
        rules=rules,
        start=start,
        end=end,
        usd_idr=rate,
        initial_cash=cash0,
        snapshots=tuple(snapshots),
        fills=tuple(fills),
        trades=tuple(trades),
        open_at_end=book.positions,
        dividends_usd=dividends_usd,
        costs_usd=costs_usd,
        rejections=tuple(sorted(rejections.items())),
    )
    return SplitRun(result=result, kickoff=kickoff, stored=stored, decided=decided)


SPLIT_STARTS = {
    "rank-day": D("2025-02-03"),  # the first session of February: ranks on the cadence, no kickoff
    "mid-month": D("2025-02-12"),  # a Wednesday: kicks off there
    "resize-monday": D("2025-02-10"),  # a resize-only Monday with no rank behind it: kicks off there
}
SPLIT_DIVIDENDS = {
    "AAA": {D("2025-03-20"): Decimal("0.30")},
    "BBB": {D("2025-05-15"): Decimal("0.20")},
    "BIL": {D("2025-04-15"): Decimal("0.30")},
}


@pytest.mark.parametrize("rules", SPLIT_RULES, ids=lambda r: r.id)
@pytest.mark.parametrize("start", list(SPLIT_STARTS.values()), ids=list(SPLIT_STARTS))
def test_split_cadence_nights_equal_run_book(rules, start):
    market = split_market()
    got = split_paper_run(lambda d: cut_market(market, dates.next_session(d)), BREATHE, None, rules, start,
                          SPLIT_END, dividends=SPLIT_DIVIDENDS)
    assert got.kickoff == (None if is_rank_session(rules, start) else start)
    want = run_book(market, BREATHE, None, rules, start, SPLIT_END, dividends=SPLIT_DIVIDENDS, kickoff=got.kickoff)
    assert_same_run(got.result, want)
    resized = [s for s in got.decided if is_resize_session(rules, s)]
    assert len(resized) >= 12, "the window re-scales every week between the month starts"
    assert {f.reason for f in want.fills if f.session_date in resized} >= {"trim", "add"}
    assert want.dividends_usd > 0


@pytest.mark.parametrize("rules", SPLIT_RULES, ids=lambda r: r.id)
def test_a_resize_week_keeps_the_ranked_names_at_the_new_exposure(rules):
    market = split_market()
    got = split_paper_run(lambda d: market, BREATHE, None, rules, D("2025-02-12"), SPLIT_END)
    idle = rules.idle_symbol
    for session, targets in got.decided.items():
        if not is_resize_session(rules, session):
            continue
        rank_day = last_rank_session(rules, D("2025-02-12"), got.kickoff, session)
        ranked = {t.symbol for t in rank_basket(got.decided[rank_day], idle)}
        names = [t.symbol for t in rank_basket(targets, idle)]
        assert set(names) <= ranked, session  # never a new name on a resize week
        if idle is not None and targets:
            assert targets[-1].symbol == idle  # the freed weight goes to the idle instrument
    # 2025-03-10: the March rank (DDD, AAA at 0.4 each: week 9 wants 0.8) at week 10's 0.9; the
    # allocator wanted (DDD, CCC) that week, and CCC is not bought.
    resize = rank_basket(got.decided[D("2025-03-10")], idle)
    assert [(t.symbol, t.weight) for t in resize] == [("DDD", Decimal("0.45")), ("AAA", Decimal("0.45"))]
    assert not any(f.symbol == "CCC" and f.side == "buy" and f.session_date < D("2025-04-01")
                   for f in got.result.fills)


@pytest.mark.parametrize("rules", SPLIT_RULES, ids=lambda r: r.id)
def test_a_stopped_out_position_is_not_bought_back_on_a_resize_week(rules):
    market = split_market()
    got = split_paper_run(lambda d: market, BREATHE, None, rules, D("2025-02-12"), SPLIT_END)
    (stopped,) = [t for t in got.result.trades if t.symbol == "DDD" and t.exit_date == DDD_CRASH]
    assert stopped.exit_reason == "sl"
    # The allocator still wants DDD on the next three resize weeks (March's basket is DDD, CCC) ...
    weeks = [D("2025-03-17"), D("2025-03-24"), D("2025-03-31")]
    for session in weeks:
        assert is_resize_session(rules, session)
        assert "DDD" not in {t.symbol for t in got.decided[session]}
    # ... and buys it again only on the April rank.
    ddd_buys = [f.session_date for f in got.result.fills if f.symbol == "DDD" and f.side == "buy"]
    assert DDD_CRASH not in ddd_buys and not any(DDD_CRASH < d < D("2025-04-01") for d in ddd_buys)
    assert D("2025-04-01") in ddd_buys


def test_a_split_between_the_rank_and_the_resize_changes_nothing_the_resize_reads():
    # The 03-03 rank is decided and stored in pre-split units (AAA at its traded price); AAA
    # splits 2-for-1 on 03-05 and the database is rewritten. The 03-10 resize reads that stored
    # basket for its symbols and weights only, so it decides exactly what run_book decides over
    # the rewritten history.
    rules = MONTHLY_RANK_WEEKLY_RESIZE_FRAC
    raw, adjusted = split_market(aaa_split=True), split_market()

    def market_at(d: date) -> Market:
        return cut_market(raw if d < AAA_SPLIT else adjusted, dates.next_session(d))

    start = D("2025-02-12")
    got = split_paper_run(market_at, BREATHE, None, rules, start, D("2025-04-30"),
                          splits={AAA_SPLIT: (("AAA", Decimal("2")),)})
    want = split_paper_run(lambda d: adjusted, BREATHE, None, rules, start, D("2025-04-30"))
    rank_got, rank_want = got.stored[D("2025-03-03")], want.stored[D("2025-03-03")]
    aaa_got = next(t for t in rank_got if t.symbol == "AAA")
    aaa_want = next(t for t in rank_want if t.symbol == "AAA")
    assert aaa_got.last == 2 * aaa_want.last  # stored before the split, in the units it traded in
    assert [(t.symbol, t.weight) for t in rank_got] == [(t.symbol, t.weight) for t in rank_want]
    for session in dates.sessions(D("2025-03-06"), D("2025-04-30")):
        if session in want.decided:
            assert got.decided[session] == want.decided[session], session
    assert got.decided[D("2025-03-10")] == want.decided[D("2025-03-10")] != ()


# ---- decide_book's resize path, hand-checked on the wiring market ------------------------------
#
# wiring_market: 2025-03-03 ranks (data_date 02-28), 2025-03-10 is resize-only (data_date 03-07),
# 2025-03-05 is neither (data_date 03-04).

W_RANK = (Target(symbol="AAA", weight=Decimal("0.4"), last=P("11.2")),
          Target(symbol="BBB", weight=Decimal("0.4"), last=P("22.4")))


def test_decide_book_rescales_the_last_rank_basket_on_a_resize_session():
    market = wiring_market()
    alloc = Scripted((("CCC", "0.2"),))
    marks = {"AAA": P("11"), "BBB": P("22")}
    held, day = frozenset({"AAA", "BBB"}), D("2025-03-07")
    got = decide_book(market, alloc, None, MONTHLY_RANK_WEEKLY_RESIZE, day, held, last_rank=W_RANK, marks=marks)
    fresh = (Target(symbol="CCC", weight=Decimal("0.2"), last=P("30")),)  # what Scripted answers on 03-07
    rescaled = book_runner._rescaled(market, W_RANK, fresh, held, day, marks)
    assert got == book_runner._with_idle(market, MONTHLY_RANK_WEEKLY_RESIZE, rescaled, day)
    assert [(t.symbol, t.weight) for t in got[0]] == [("AAA", Decimal("0.1")), ("BBB", Decimal("0.1"))]
    assert [t.last for t in got[0]] == [q(market.bar("AAA", D("2025-03-07")).close),
                                        q(market.bar("BBB", D("2025-03-07")).close)]
    (call,) = alloc.calls  # called once, at data_date, for its total only
    assert (call.data_date, call.held) == (D("2025-03-07"), frozenset({"AAA", "BBB"}))


def test_decide_book_resize_with_the_idle_instrument_moves_only_the_idle_weight():
    alloc = Scripted((("AAA", "0.2"), ("BBB", "0.2")))
    tbill = MONTHLY_RANK_WEEKLY_RESIZE_TBILL
    targets, idle_added = decide_book(wiring_market(), alloc, None, tbill, D("2025-03-07"),
                                      frozenset({"AAA", "BBB", "BIL"}), last_rank=W_RANK, marks={})
    assert idle_added is True
    assert [(t.symbol, t.weight) for t in targets] == [
        ("AAA", Decimal("0.2")), ("BBB", Decimal("0.2")), ("BIL", Decimal("0.6"))
    ]
    assert alloc.calls[0].held == frozenset({"AAA", "BBB"})  # the idle position is never the allocator's


def test_decide_book_resize_drops_what_is_no_longer_held():
    alloc = Scripted((("AAA", "0.8"),))
    targets, _ = decide_book(wiring_market(), alloc, None, MONTHLY_RANK_WEEKLY_RESIZE, D("2025-03-07"),
                             frozenset({"BBB"}), last_rank=W_RANK, marks={"BBB": P("22")})
    assert [(t.symbol, t.weight) for t in targets] == [("BBB", Decimal("0.4"))]
    empty, added = decide_book(wiring_market(), alloc, None, MONTHLY_RANK_WEEKLY_RESIZE, D("2025-03-07"),
                               frozenset(), last_rank=W_RANK, marks={})
    assert (empty, added) == ((), False)  # a decision to hold nothing, not "no decision"
    from_empty_rank, _ = decide_book(wiring_market(), alloc, None, MONTHLY_RANK_WEEKLY_RESIZE, D("2025-03-07"),
                                     frozenset({"BBB"}), last_rank=(), marks={})
    assert from_empty_rank == ()


def test_decide_book_resize_without_a_rank_yet_is_no_decision():
    alloc = Scripted((("AAA", "0.5"),))
    assert decide_book(wiring_market(), alloc, None, MONTHLY_RANK_WEEKLY_RESIZE, D("2025-03-07"), frozenset(),
                       marks={}) == (None, False)
    assert alloc.calls == []


def test_decide_book_resize_needs_the_marks():
    with pytest.raises(ValueError, match="marks"):
        decide_book(wiring_market(), Scripted((("AAA", "0.5"),)), None, MONTHLY_RANK_WEEKLY_RESIZE,
                    D("2025-03-07"), frozenset({"AAA"}), last_rank=W_RANK)


def test_decide_book_split_rules_rank_and_skip_as_the_cadence_says():
    market = wiring_market()
    split = MONTHLY_RANK_WEEKLY_RESIZE
    # The month start ranks, whatever last_rank says: the allocator's basket, not the old one.
    alloc = Scripted((("CCC", "0.5"),))
    ranked, _ = decide_book(market, alloc, None, split, D("2025-02-28"), frozenset({"AAA"}), last_rank=W_RANK,
                            marks={})
    assert [(t.symbol, t.weight) for t in ranked] == [("CCC", Decimal("0.5"))]
    # A session that is neither: no decision, no call.
    idle = Scripted((("CCC", "0.5"),))
    assert decide_book(market, idle, None, split, D("2025-03-04"), frozenset(), last_rank=W_RANK,
                       marks={}) == (None, False)
    assert idle.calls == []
    # force ranks a resize-only session (the kickoff on a resize Monday, and the nightly preview).
    forced, _ = decide_book(market, Scripted((("CCC", "0.5"),)), None, split, D("2025-03-07"), frozenset({"AAA"}),
                            force=True, last_rank=W_RANK, marks={})
    assert [t.symbol for t in forced] == ["CCC"]


def test_decide_book_ignores_last_rank_and_marks_without_a_resize_cadence():
    market = wiring_market()
    for data_date in (D("2025-02-28"), D("2025-03-07"), D("2025-03-04")):  # a rank, a week start, neither
        plain = decide_book(market, Scripted((("AAA", "0.5"),)), None, MONTHLY_HOLD, data_date, frozenset({"AAA"}))
        given = decide_book(market, Scripted((("AAA", "0.5"),)), None, MONTHLY_HOLD, data_date, frozenset({"AAA"}),
                            last_rank=W_RANK, marks={"AAA": P("1")})
        assert given == plain


def test_decide_book_last_rank_and_marks_argument_checks():
    market, alloc, d = wiring_market(), Scripted(), D("2025-03-07")
    with pytest.raises(TypeError, match="last_rank"):
        decide_book(market, alloc, None, MONTHLY_RANK_WEEKLY_RESIZE, d, frozenset(), last_rank=list(W_RANK), marks={})
    with pytest.raises(TypeError, match="Target"):
        decide_book(market, alloc, None, MONTHLY_RANK_WEEKLY_RESIZE, d, frozenset(), last_rank=("AAA",), marks={})
    with pytest.raises(TypeError, match="marks"):
        decide_book(market, alloc, None, MONTHLY_RANK_WEEKLY_RESIZE, d, frozenset(), last_rank=W_RANK, marks=[])
    with pytest.raises(TypeError, match="Decimal"):
        decide_book(market, alloc, None, MONTHLY_RANK_WEEKLY_RESIZE, d, frozenset(), last_rank=W_RANK,
                    marks={"AAA": 11.0})


# ---- rank_basket ---------------------------------------------------------------------------------


def test_rank_basket_takes_off_the_trailing_idle_row_only():
    bil = Target(symbol="BIL", weight=Decimal("0.2"), last=P("100"))
    assert rank_basket(W_RANK + (bil,), "BIL") == W_RANK
    assert rank_basket(W_RANK, "BIL") == W_RANK  # no idle row (no BIL bar that night, or full weight)
    assert rank_basket(W_RANK, None) == W_RANK
    assert rank_basket((bil,), "BIL") == ()  # the rank chose nothing; the book sat in BIL
    assert rank_basket((), "BIL") == () and rank_basket([], None) == ()
    assert rank_basket(list(W_RANK), None) == W_RANK


def test_rank_basket_refuses_what_no_decision_writes():
    bil = Target(symbol="BIL", weight=Decimal("0.2"), last=P("100"))
    with pytest.raises(ValueError, match="idle"):
        rank_basket((bil,) + W_RANK, "BIL")
    with pytest.raises(TypeError, match="Target"):
        rank_basket(("AAA",), None)
    with pytest.raises(TypeError, match="sequence"):
        rank_basket({"AAA": 1}, None)
```
**Impact:** the refusal test is gone, along with the refusal.

### Step 7: `test_paper_kickoff.py` — resize-only Monday and `last_rank_session`
**File:** `engine/tests/test_paper_kickoff.py:3-8` (imports), append at the end (`:30`)
**Code** — imports:
```python
from __future__ import annotations

from datetime import date

import pytest

from seer_engine import dates
from seer_engine.paper.book import last_rank_session, needs_kickoff
from seer_engine.sim.rules import (
    DESIGN_V0,
    MONTHLY_HOLD,
    MONTHLY_RANK_WEEKLY_RESIZE,
    PRESETS,
    is_decision_session,
    is_rank_session,
    is_resize_session,
)
```
Appended:
```python
# ---- split cadence (monthly rank, weekly resize) ------------------------------------------------

OCT5, OCT12, OCT13, OCT19 = date(2026, 10, 5), date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 19)
NOV9 = date(2026, 11, 9)


def test_a_clock_starting_on_a_resize_only_monday_kicks_off_there():
    # 2026-10-12 is a week start but not a month start: a resize session, and nothing has ranked
    # yet, so run_book would not decide it. The kickoff ranks it instead.
    assert is_resize_session(MONTHLY_RANK_WEEKLY_RESIZE, OCT12)
    assert needs_kickoff(MONTHLY_RANK_WEEKLY_RESIZE, OCT12, OCT12, None)
    assert needs_kickoff(MONTHLY_RANK_WEEKLY_RESIZE, OCT6, OCT12, None)
    assert not needs_kickoff(MONTHLY_RANK_WEEKLY_RESIZE, OCT12, OCT13, OCT12)
    assert not needs_kickoff(MONTHLY_RANK_WEEKLY_RESIZE, OCT1, OCT12, None)  # 2026-10-01 already ranked
    assert not needs_kickoff(MONTHLY_RANK_WEEKLY_RESIZE, OCT12, NOV2, None)  # the cadence ranks it


def test_without_a_resize_cadence_the_kickoff_test_is_unchanged():
    # Before the split, needs_kickoff tested is_decision_session; for every rule set without a
    # resize_cadence that is is_rank_session, session for session.
    for rules in PRESETS:
        if rules.engine != "book" or rules.resize_cadence is not None:
            continue
        for start in (OCT1, OCT5, OCT6):
            for session in dates.sessions(start, NOV9):
                old = not is_decision_session(rules, session) and not any(
                    is_rank_session(rules, s) for s in dates.sessions(start, session) if s < session
                )
                assert needs_kickoff(rules, start, session, None) is old, (rules.id, start, session)


def test_last_rank_session_is_the_latest_rank_or_kickoff_before_the_session():
    r = MONTHLY_RANK_WEEKLY_RESIZE
    assert last_rank_session(r, OCT1, None, OCT12) == OCT1
    assert last_rank_session(r, OCT6, OCT6, OCT12) == OCT6  # the kickoff ranked
    assert last_rank_session(r, OCT12, OCT12, OCT19) == OCT12  # a kickoff on a resize Monday
    assert last_rank_session(r, OCT6, OCT6, NOV2) == OCT6  # strictly before the session
    assert last_rank_session(r, OCT6, OCT6, NOV9) == NOV2  # the cadence rank supersedes the kickoff
    assert last_rank_session(r, OCT6, None, OCT12) is None  # nothing ranked yet
    assert last_rank_session(r, OCT6, None, OCT6) is None


def test_last_rank_session_argument_checks():
    with pytest.raises(ValueError, match="book"):
        last_rank_session(DESIGN_V0, OCT1, None, OCT12)
    with pytest.raises(ValueError, match="NYSE session"):
        last_rank_session(MONTHLY_RANK_WEEKLY_RESIZE, OCT1, date(2026, 10, 10), OCT12)
    with pytest.raises(TypeError, match="date"):
        last_rank_session(MONTHLY_RANK_WEEKLY_RESIZE, OCT1, None, "2026-10-12")
```
**Impact:** pins that the `needs_kickoff` change is a no-op for every preset without a split.

### Step 8: `test_sim_rules.py` and `test_promote_command.py`
**File:** `engine/tests/test_sim_rules.py:25`, `:88-105`, after `:339`; `engine/tests/test_promote_command.py:351-357`
**Change:**
- In `test_sim_rules.py`, add `MONTHLY_RANK_WEEKLY_RESIZE_FRAC,` to the `from seer_engine.sim.rules import (...)`
  list, after `MONTHLY_RANK_WEEKLY_RESIZE,` (`:25`).
- Append `"monthly-rank-weekly-resize-frac",` as the last id in `test_preset_ids_are_unique_and_in_order`
  (after `"monthly-hold-frac",`, `:102`).
- Add the new test after `test_monthly_rank_weekly_resize_preset` (`:333-339`).
- Replace the fractional-twin test in `test_promote_command.py`.

`test_owner_inputs_of_the_presets` and the 12-line check on `describe_rules` already cover the new
preset without changes: it is fractional with no idle symbol, so its owner inputs are `("fractional",)`.
**Code** — `test_sim_rules.py` id list after the edit:
```python
def test_preset_ids_are_unique_and_in_order():
    ids = [r.id for r in PRESETS]
    assert ids == [
        "design-v0",
        "monthly-hold",
        "monthly-hold-tbill",
        "weekly-hold",
        "daily-switch",
        "daily-switch-tbill",
        "swing-t10",
        "swing-t20",
        "swing-t20-open",
        "monthly-rank-weekly-resize",
        "monthly-rank-weekly-resize-tbill",
        "monthly-hold-frac",
        "monthly-rank-weekly-resize-frac",
    ]
    assert len(set(ids)) == len(ids)
```
New test in `test_sim_rules.py`:
```python
def test_monthly_rank_weekly_resize_frac_is_the_split_cadence_in_fractional_shares():
    r = MONTHLY_RANK_WEEKLY_RESIZE_FRAC
    assert r == replace(MONTHLY_RANK_WEEKLY_RESIZE, id="monthly-rank-weekly-resize-frac", fractional=True)
    assert (r.cadence, r.resize_cadence, r.fractional, r.idle_symbol) == ("monthly", "weekly", True, None)
    assert PRESETS[-1] is r and sim.MONTHLY_RANK_WEEKLY_RESIZE_FRAC is r
    assert rule_owner_inputs(r) == ("fractional",)
```
`test_promote_command.py` (replaces `:351-357`):
```python
def test_fractional_twin_maps_a_whole_share_preset_to_its_fractional_preset():
    from seer_engine.sim.rules import (
        DESIGN_V0,
        MONTHLY_HOLD,
        MONTHLY_HOLD_FRAC,
        MONTHLY_RANK_WEEKLY_RESIZE,
        MONTHLY_RANK_WEEKLY_RESIZE_FRAC,
        MONTHLY_RANK_WEEKLY_RESIZE_TBILL,
    )

    assert promote.fractional_twin(MONTHLY_HOLD) is MONTHLY_HOLD_FRAC
    assert promote.fractional_twin(MONTHLY_HOLD_FRAC) is MONTHLY_HOLD_FRAC
    assert promote.fractional_twin(MONTHLY_RANK_WEEKLY_RESIZE) is MONTHLY_RANK_WEEKLY_RESIZE_FRAC
    assert promote.fractional_twin(MONTHLY_RANK_WEEKLY_RESIZE_FRAC) is MONTHLY_RANK_WEEKLY_RESIZE_FRAC
    # The T-bill split cadence has no fractional preset (not asked for): still refused.
    with pytest.raises(promote.NotPromotable, match="no fractional preset matching 'monthly-rank-weekly-resize-tbill'"):
        promote.fractional_twin(MONTHLY_RANK_WEEKLY_RESIZE_TBILL)
    with pytest.raises(promote.NotPromotable, match="no fractional preset matching 'design-v0'"):
        promote.fractional_twin(DESIGN_V0)
```

### Step 9: `test_paper_replay.py` — replay decisions for split rules
**File:** `engine/tests/test_paper_replay.py:19-45` (imports), append at the end (`:518`)
**Change:**
- Add `from test_paper_book import BREATHE, SPLIT_END, SPLIT_RULES, split_market, split_paper_run`
  after `from simkit import D, P, bar` (`:20`).
- In the `from seer_engine.sim import (...)` block (`:37-45`), add `MONTHLY_RANK_WEEKLY_RESIZE,`
  after `MONTHLY_HOLD,` and `is_resize_session,` after `initial_cash_usd,`.
- Append the tests.
**Code** — the `seer_engine.sim` import block after the edit:
```python
from seer_engine.sim import (
    MONTHLY_HOLD,
    MONTHLY_RANK_WEEKLY_RESIZE,
    Pick,
    Portfolio,
    Snapshot,
    Trade,
    initial_cash_usd,
    is_resize_session,
    size_picks,
)
```
Appended:
```python
# ---- split cadence: the replay keeps its own last rank basket ---------------------------------
#
# The split-cadence market and allocator of tests/test_paper_book.py. The replay rebuilds the
# last rank basket from its own rank decisions and the marks from last_close; the paper night
# (split_paper_run there) reads them back from what it stored. Both must decide the same.


@pytest.mark.parametrize("rules", SPLIT_RULES, ids=lambda r: r.id)
@pytest.mark.parametrize("start", [D("2025-02-03"), D("2025-02-10"), D("2025-02-12")],
                         ids=["rank-day", "resize-monday", "mid-month"])
def test_expected_book_of_split_cadence_rules_equals_the_nights(rules, start):
    m = split_market()
    nights = split_paper_run(lambda d: m, BREATHE, None, rules, start, SPLIT_END, initial_idr=PAPER_INITIAL_IDR)
    head = PaperHead("S", "book", start, SPLIT_END, USD_IDR, kickoff=nights.kickoff)
    got = replay.expected_book(m, BREATHE, None, rules, head, {})
    assert got.snapshots == tuple(Snapshot(s.date, s.cash_usd, s.equity_usd) for s in nights.result.snapshots)
    assert got.fills == nights.result.fills and got.trades == nights.result.trades
    assert got.positions == nights.result.open_at_end
    assert got.targets == tuple(sorted(nights.stored.items()))
    assert any(is_resize_session(rules, s) for s, _ in got.targets)
    assert replay.compare("book", got, got) == ()


def test_expected_book_pending_resize_decision():
    m, rules = split_market(), MONTHLY_RANK_WEEKLY_RESIZE
    head = PaperHead("S", "book", D("2025-02-12"), D("2025-03-07"), USD_IDR, kickoff=D("2025-02-12"))
    got = replay.expected_book(m, BREATHE, None, rules, head, {})
    assert got.pending_session == D("2025-03-10") and got.pending_decision is True
    (pending,) = [t for s, t in got.targets if s == D("2025-03-10")]
    assert [(t.symbol, t.weight) for t in pending] == [("DDD", Decimal("0.45")), ("AAA", Decimal("0.45"))]
    # Before any rank (a head with no kickoff, started mid-month) a resize week decides nothing.
    early = replay.expected_book(m, BREATHE, None, rules, replace(head, last_session=D("2025-02-14"), kickoff=None), {})
    assert early.pending_session == D("2025-02-18") and is_resize_session(rules, D("2025-02-18"))
    assert early.pending_decision is False and early.targets == ()
```
**Impact:** pins the replay's resize decisions equal to the night loop's, for all three split
presets and three kinds of start. The night loop's run is itself pinned equal to `run_book`.

## Verification

**Build:** `engine/.venv/bin/ruff check engine`
**Tests:** `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`
(only the two known Python-3.12-only failures allowed). Focused run:
`engine/.venv/bin/pytest -q engine/tests/test_paper_book.py engine/tests/test_paper_kickoff.py engine/tests/test_paper_replay.py engine/tests/test_sim_rules.py engine/tests/test_promote_command.py engine/tests/test_book_runner.py engine/tests/test_paper_roster.py engine/tests/test_strategy_purity.py engine/tests/test_sim_purity.py`
**Manual check:** `git diff --stat` touches only the nine files above. `git diff engine/tests/test_paper_roster.py` is empty (PINS untouched). `git diff engine/src/seer_engine/backtest engine/src/seer_engine/sim/book.py` is empty.
**Exit criteria:**
- `split_paper_run` (decide_book/settle_book night by night, with `last_rank` from `rank_basket`
  of the stored rank decision) equals `run_book` field for field for `monthly-rank-weekly-resize`,
  `-tbill` and `-frac`, starting on a rank day, on a mid-month kickoff and on a resize-Monday kickoff.
- `expected_book`'s decisions equal that loop's stored decisions.
- `fractional_twin(MONTHLY_RANK_WEEKLY_RESIZE) is MONTHLY_RANK_WEEKLY_RESIZE_FRAC`.
- The full engine suite and ruff are green, and every existing paper/book/replay test passes
  unedited (apart from the deleted refusal test).

## Handoffs

- **Phase 2 (R1, R2, R3, R7) — the nightly wiring.** `commands/paper.py` `_start` (`:559-566`)
  and `_step_book` (`:625-637`) must pass `last_rank` and `marks` to `decide_book`:
  - `rank_day = last_rank_session(rules, paper_start, kickoff_stored_or_this_nights, nxt)`
  - `last_rank = None if rank_day is None else rank_basket(<the book_targets rows stored for rank_day>, rules.idle_symbol)`
    (no rows gives `()`)
  - `marks = {p.symbol: p.mark for p in book.positions}`, from the book whose `held()` is passed.

  Copy `split_paper_run` in `tests/test_paper_book.py` exactly: it is the executable spec. Pass the
  kickoff that `last_rank_session` sees as the kickoff stored before this night's decision —
  in `_step_book` that is the `kicked` variable, which is set to `nxt` right after a kickoff is
  written, so a later session decided in the same catch-up loop sees the kickoff it just made
  (as `split_paper_run` updates `kickoff` after a forced decision). On
  `_start` (first night, empty book), `marks={}` is fine, because the first night can only rank or
  do nothing (`last_rank_session` is None). A resize-only decision gets evidence `None`. The preview
  call `decide_book(..., force=True)` needs no `last_rank`.
  Until phase 2 lands, a split-cadence roster entry would skip resize weeks silently instead of
  being refused. None exists, and none can be promoted before phase 2 lands in the same merge.
- **Phase 2 — Postgres end to end** (`test_paper_split_cadence.py`): reconciled — phase 2 builds
  its own Postgres world (`ScriptedSplit`, `M0022-W-TV14`) and imports nothing from
  `tests/test_paper_book.py`, so the helper names above are this phase's alone and phase 2 does not
  edit `test_paper_book.py` or `test_paper_replay.py`. Only `test_paper_replay.py` (Step 9) imports
  them.
- **Phase 3 (R6):** nothing from here. The web reads `rulesId`, and `monthly-rank-weekly-resize-frac`
  is the new id it must recognize.
- Deliberately not done: a fractional twin for `MONTHLY_RANK_WEEKLY_RESIZE_TBILL` (out of scope).
  `fractional_twin` keeps refusing it, and Step 8's test pins that.

## Rollback

Revert this phase's commit. It touches no data and no migration. Phase 2 depends on the new
`decide_book` keywords and helpers, so revert phase 2 first if it has landed.
