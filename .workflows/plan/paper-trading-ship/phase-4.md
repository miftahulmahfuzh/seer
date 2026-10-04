# Phase 4: Book night core

**Plan set:** `PAPER_TRADING_SHIP_PLAN.md`
**Analysis:** `20261004-082027-P4S7_code_analyzer.md`
**Satisfies:** R1 — the engine paper step's pure core for the two book strategies on the roster (F4-MOM12-N20-TREND, F1-SPY-SMA200-M): one night of `run_book`, split in a "decide" half and a "settle" half over persisted state
**Depends on:** Phase 1 (the `seer_engine.paper` package and purity coverage of `paper/*.py`), Phase 2 (`sim.book.apply_book_split` / `BookSplit`)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/paper`

---

## Goal

`seer_engine.paper.book` exists and is pure: `decide_book` computes the targets for the next
session exactly as `run_book` does at night, and `settle_book` steps one session over a
persisted `Book` (splits first, then `step_book` with the session's dividends, then the
force-close of positions whose bars ended, snapshot replaced). Looping the two from
`new_book(cash0)` reproduces `run_book` field for field on synthetic markets for FACTOR, TIMING and
a fixed allocator (with and without the idle instrument), including dividends and forced closes,
and decisions never read a bar dated on or after the session they are for.

## Interface Contract

**Deletes:** nothing
**Renames:** nothing
**Creates:**
- `seer_engine.paper.book.BookNight` (frozen dataclass: `session`, `book`, `targets`, `splits`, `fills`, `trades`, `dividends`, `rejected`, `forced`, `snapshot`) (`engine/src/seer_engine/paper/book.py`)
- `seer_engine.paper.book.decide_book(market, allocator, params, rules, data_date, held) -> tuple[tuple[Target, ...] | None, bool]` (C3, exact signature)
- `seer_engine.paper.book.settle_book(book, session, bars, targets, idle_added, rules, dividends, splits, last_bar_date) -> BookNight` (C3, exact signature)
- `seer_engine.paper.book.LastBarDate` (type alias `Callable[[str], date | None]`)
- `engine/tests/test_paper_book.py` (29 tests)

Argument types phase 6/7 code against:
- `bars`: `Mapping[str, Bar]` — the session's bars for every held or targeted symbol (extra symbols are ignored by `step_book`).
- `targets`: what `decide_book` returned the night before, as persisted (`None` = not a decision session; `()` = a decision session that wants nothing). `idle_added` must be False when `targets` is None.
- `dividends`: `DividendMap` (`backtest.book_runner.DividendMap`, symbol -> {ex_date: cash per share}); only ex-date == `session` is read. A store may pass just that session's rows.
- `splits`: `Sequence[tuple[str, Decimal]]` of `(symbol, factor)` for splits executing on `session` with `split_adjustments.applied = true`; factor as `splits.Split.factor`. Applied in symbol order; two for one symbol is a ValueError.
- `last_bar_date`: `Callable[[str], date | None]`; replay passes `Market.last_bar_date`, the night passes "latest bar date in the DB" for the symbol.
- `held` (decide): any `Set[str]`; normally `night.book.held()`.

`BookNight.fills` order is the `book_fills.seq` order of C1 (split fills, open exits, trims, buys, intraday exits, forced). `BookNight.targets` is the executed targets in post-split units — phase 6 must overwrite the persisted `book_targets` rows for that session with them when a split hit a targeted symbol.

**Signature changes:** none
**Requires (from earlier phases):**
- Phase 1: package `engine/src/seer_engine/paper/__init__.py` exists (docstring only); the purity test covers every `paper/*.py` except `store.py` (so `paper/book.py` is checked without editing a test here).
- Phase 2: `seer_engine.sim.book.apply_book_split(book, symbol, factor, session, rules, targets=None) -> BookSplit` and `seer_engine.sim.book.BookSplit` with fields `book: Book`, `targets: tuple[Target, ...] | None` (rescaled; None when None was passed; returned even when the book does not hold the symbol), `in_lieu: Decimal`, `trade: Trade | None` (the forced close on floor-to-zero), `fills: tuple[Fill, ...]` — as written in `.workflows/plan/paper-trading-ship/phase-2.md` Step 3. Whole shares under `MONTHLY_HOLD` floor `shares × r`; mark, entry price, stop and take become `q(p / r)`; `last_session` unchanged.
- Closed records used by import, unchanged: `backtest.book_runner.DividendMap`, `_dividends_on`, `_invested`, `_with_idle`, `run_book`, `BookResult`; `backtest.runner.INITIAL_IDR`.

**Leaves alone (owned by others):** `sim/*` (phase 2), `backtest/*` (closed records; `io.py` is phase 6), `paper/__init__.py` and `paper/roster.py` and the purity tests (phase 1), `paper/bracket.py` and `paper/benchmark.py` (phase 3), `paper/store.py` (phase 6), `commands/*` (phases 7–9), the DB and migrations.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/paper/book.py` | create | `BookNight`, `decide_book`, `settle_book` and their argument checks (pure) |
| `engine/tests/test_paper_book.py` | create | same-path equality vs `run_book`, no look-ahead, wiring, splits, dividends, force-close |

No other file changes. (`paper/__init__.py` stays docstring-only per phase 1: no re-export.)

## Implementation Steps

### Step 1: The night module
**File:** `engine/src/seer_engine/paper/book.py:1` (new file)
**Change:** create the module. Design notes the implementer must keep:
- `decide_book` is `run_book` lines 222–231 (`backtest/book_runner.py`) for `session = next_session(data_date)`; it returns `(None, False)` *without calling the allocator* off decision sessions. It always uses the single-window path (`allocator.targets` on histories cut at `data_date`), never `targets_prepared`: the allocator contract makes them equal and `run_book(prepared=None)` is what the tests compare against.
- `settle_book` is `run_book` lines 233–260 for one session, preceded by the splits. The dividend selection runs on `book.held()` *after* the splits (a position floored to zero by a split has nothing left to receive a dividend; with no split this is exactly `run_book`'s `held`, taken before `step_book`).
- The force-close test is `last is None or last < session`, i.e. `book_runner._gone` with a callable instead of a `Market`. The replacement snapshot uses `book_runner._invested`, as `run_book` does.
- No float, clock, logging or I/O; nothing named `now`, `today`, `random`, `print`, `open` (phase 1's purity test).
**Code:**
```python
"""The book engine's night: one paper session of a book strategy (R1, plan contract C3).

Pure (purity-tested with every ``paper/*.py`` except ``store.py``): no database, network,
clock, randomness, logging or file access. Paper trading runs ``backtest.book_runner.run_book``'s
loop body one session at a time, over state persisted between nights, in two halves:

``decide_book`` (the night of ``data_date``, after its bars arrived) is ``run_book``'s step 1 and
2 for ``S = next_session(data_date)``: ``None`` when ``S`` is not a decision session under
``rules``; otherwise ``allocator.targets`` on every history cut at ``data_date``, the members on
``data_date`` and the symbols held at night minus the idle instrument, then
``book_runner._with_idle`` (imported, not copied). It returns ``(targets, idle_added)``; the
caller persists both and hands them back to ``settle_book`` for ``S``.

``settle_book`` (the night of ``S``, after S's bars arrived) is ``run_book``'s steps 3 and 4 for
``S``, preceded by the splits that executed on ``S``:

1. each ``(symbol, factor)`` in ``splits``, in symbol order: ``sim.book.apply_book_split``, which
   rewrites the book and the targets decided for ``S`` (they were priced the night before, in
   pre-split units) into post-split units;
2. ``step_book`` with ``bars`` (S's bars; extra symbols are ignored) and, when
   ``rules.dividends``, the cash dividends whose ex-date is ``S`` for the symbols held after the
   splits (``book_runner._dividends_on``, the runner's selection);
3. every position whose ``last_bar_date(symbol)`` is None or before ``S`` is force-closed at its
   mark (``close_book_unpriced``) and S's snapshot is replaced, exactly as ``run_book`` does.

Looping ``decide_book`` then ``settle_book`` from ``new_book(cash0)`` with ``data_date =
prev_session(start)`` and no splits reproduces ``run_book`` field for field
(tests/test_paper_book.py). ``last_bar_date`` is ``Market.last_bar_date`` in a replay; at night
it is the latest bar date the database holds, so a halted symbol is force-closed on the first
session it misses (plan Decisions, "Force-close rule live").
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from seer_engine import dates
from seer_engine.backtest.book_runner import DividendMap, _dividends_on, _invested, _with_idle
from seer_engine.backtest.market import Market
from seer_engine.prices import Bar
from seer_engine.sim.book import (
    Book,
    BookSnapshot,
    BookSplit,
    Fill,
    RejectReason,
    Target,
    Trade,
    apply_book_split,
    close_book_unpriced,
    step_book,
)
from seer_engine.sim.rules import TradeRules, is_decision_session
from seer_engine.strategies.allocator import Allocator

LastBarDate = Callable[[str], date | None]  # symbol -> its latest bar date known, or None


@dataclass(frozen=True, slots=True)
class BookNight:
    """One settled session of a book strategy.

    ``book``: the state after the session (forced closes applied), ``last_session = session``.
    ``targets``: the targets executed on ``session`` in post-split units (None on a
    non-decision session); a caller that persisted them before the split rewrites them with this.
    ``splits``: each ``apply_book_split`` result, in the order applied (symbol order).
    ``fills``: split fills, then ``step_book``'s (open exits, trims, buys, intraday exits), then
    forced closes: the ``book_fills.seq`` order. ``trades``: closed episodes in the same order.
    ``dividends``: ``(symbol, cash credited)`` by symbol. ``rejected``: ``step_book``'s
    rejections in its order. ``forced``: the symbols force-closed because their bars ended.
    ``snapshot``: S's snapshot, after any forced close.
    """

    session: date
    book: Book
    targets: tuple[Target, ...] | None
    splits: tuple[BookSplit, ...]
    fills: tuple[Fill, ...]
    trades: tuple[Trade, ...]
    dividends: tuple[tuple[str, Decimal], ...]
    rejected: tuple[tuple[str, RejectReason], ...]
    forced: tuple[str, ...]
    snapshot: BookSnapshot


def _session(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    if not dates.is_session(d):
        raise ValueError(f"{name} {d} is not an NYSE session")
    return d


def _book_rules(rules: object) -> TradeRules:
    if not isinstance(rules, TradeRules):
        raise TypeError(f"rules must be TradeRules, got {type(rules).__name__}")
    if rules.engine != "book":
        raise ValueError(f"rules {rules.id!r} use the {rules.engine} engine; the book night runs 'book' rules only")
    return rules


def _held(held: object) -> frozenset[str]:
    if isinstance(held, str) or not isinstance(held, AbstractSet):
        raise TypeError(f"held must be a set of symbols, got {type(held).__name__}")
    for s in held:
        if not isinstance(s, str):
            raise TypeError(f"held symbols must be str, got {type(s).__name__}")
    return frozenset(held)


def _splits(splits: object) -> tuple[tuple[str, Decimal], ...]:
    """``splits`` as ``(symbol, factor)`` pairs sorted by symbol; one split per symbol."""
    if isinstance(splits, (str, Mapping)) or not isinstance(splits, Sequence):
        raise TypeError(f"splits must be a sequence of (symbol, factor) pairs, got {type(splits).__name__}")
    out: dict[str, Decimal] = {}
    for pair in splits:
        if not (isinstance(pair, tuple) and len(pair) == 2):
            raise TypeError(f"a split is a (symbol, factor) tuple, got {pair!r}")
        symbol, factor = pair
        if not isinstance(symbol, str) or not symbol:
            raise TypeError(f"split symbol must be a non-empty str, got {symbol!r}")
        if not isinstance(factor, Decimal):
            raise TypeError(f"split factor for {symbol} must be a Decimal, got {type(factor).__name__}")
        if symbol in out:
            raise ValueError(f"two splits for {symbol} on one session")
        out[symbol] = factor
    return tuple(sorted(out.items()))


def decide_book(
    market: Market,
    allocator: Allocator,
    params: Any,
    rules: TradeRules,
    data_date: date,
    held: AbstractSet[str],
) -> tuple[tuple[Target, ...] | None, bool]:
    """The targets for ``next_session(data_date)`` and whether the idle residual was appended.

    ``(None, False)`` when that session is not a decision session under ``rules`` (the
    allocator is not called). Otherwise exactly ``run_book``'s decision: ``allocator.targets``
    on ``{s: h.upto(data_date)}``, ``market.membership.members_on(data_date)``, ``held`` minus
    ``rules.idle_symbol``, ``params``; then ``book_runner._with_idle``. ``held`` is the set of
    symbols the book holds at the night of ``data_date`` (``book.held()`` after that session
    settled). Nothing dated after ``data_date`` is read.
    """
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    if not isinstance(allocator, Allocator):
        raise TypeError(f"allocator must be an Allocator, got {type(allocator).__name__}")
    _book_rules(rules)
    _session("data_date", data_date)
    held_now = _held(held)
    session = dates.next_session(data_date)
    if not is_decision_session(rules, session):
        return None, False
    members = market.membership.members_on(data_date)
    # The idle position is the runner's residual, never a family's (as run_book).
    mine = held_now - {rules.idle_symbol} if rules.idle_symbol is not None else held_now
    history = {s: h.upto(data_date) for s, h in market.history.items()}
    wanted = allocator.targets(history, members, data_date, mine, params)
    return _with_idle(market, rules, tuple(wanted), data_date)


def settle_book(
    book: Book,
    session: date,
    bars: Mapping[str, Bar],
    targets: tuple[Target, ...] | None,
    idle_added: bool,
    rules: TradeRules,
    dividends: DividendMap,
    splits: Sequence[tuple[str, Decimal]],
    last_bar_date: LastBarDate,
) -> BookNight:
    """Settle ``session`` for ``book`` (see the module docstring).

    ``targets``/``idle_added``: what ``decide_book`` returned the night before (``idle_added``
    must be False when ``targets`` is None). ``dividends``: symbol -> {ex_date: cash per share},
    only ex-date ``session`` is read. ``splits``: ``(symbol, factor)`` for every split executing
    on ``session`` whose stored history was rewritten (``factor`` as ``splits.Split.factor``).
    ``last_bar_date``: symbol -> the date of its latest bar known, or None.

    TypeError on a wrong type, ValueError on a non-session, non-book rules, ``idle_added``
    without targets, or two splits for one symbol; ``apply_book_split`` and ``step_book`` raise
    on what they refuse (a session not after ``book.last_session`` among them).
    """
    if not isinstance(book, Book):
        raise TypeError(f"book must be a Book, got {type(book).__name__}")
    _session("session", session)
    _book_rules(rules)
    if not isinstance(idle_added, bool):
        raise TypeError("idle_added must be a bool")
    if idle_added and targets is None:
        raise ValueError("idle_added is True but there are no targets for this session")
    if not isinstance(dividends, Mapping):
        raise TypeError(f"dividends must be a Mapping, got {type(dividends).__name__}")
    if not callable(last_bar_date):
        raise TypeError("last_bar_date must be callable: symbol -> date | None")
    split_list = _splits(splits)

    executed = targets
    applied: list[BookSplit] = []
    fills: list[Fill] = []
    trades: list[Trade] = []
    for symbol, factor in split_list:
        done = apply_book_split(book, symbol, factor, session, rules, executed)
        applied.append(done)
        book = done.book
        executed = done.targets
        fills.extend(done.fills)
        if done.trade is not None:
            trades.append(done.trade)

    divs = _dividends_on(dividends, book.held(), session) if rules.dividends else {}
    stepped = step_book(book, session, bars, executed, rules, divs, idle_symbol_ok=idle_added)
    book = stepped.book
    fills.extend(stepped.fills)
    trades.extend(stepped.trades)
    snapshot = stepped.snapshot

    gone: list[str] = []
    for p in book.positions:
        last = last_bar_date(p.symbol)
        if last is None or last < session:
            gone.append(p.symbol)
    if gone:
        book, forced_fills, forced_trades = close_book_unpriced(book, gone, rules)
        fills.extend(forced_fills)
        trades.extend(forced_trades)
        snapshot = BookSnapshot(
            date=session,
            cash_usd=book.cash,
            equity_usd=book.equity,
            invested_usd=_invested(book, rules),
        )

    return BookNight(
        session=session,
        book=book,
        targets=executed,
        splits=tuple(applied),
        fills=tuple(fills),
        trades=tuple(trades),
        dividends=stepped.dividends,
        rejected=stepped.rejected,
        forced=tuple(gone),
        snapshot=snapshot,
    )
```
**Impact:** new module, nothing existing changes. It imports four private names from the closed `backtest/book_runner.py` on purpose (C3: "`_with_idle` reused by import"); renaming them there would break this module, and that file is a closed record (invariant 2), so it will not happen silently.

### Step 2: Tests
**File:** `engine/tests/test_paper_book.py:1` (new file)
**Change:** create the test module. It reuses `seeded_market`, `SEED_DAYS`, `Scripted` and `wiring_market` from `tests/test_book_runner.py`, `FIXED`/`FixedParams` from `tests/allocatorkit.py`, and `hist`/`mutate_from`/`truncate_before`/`session_days` from `tests/stratkit.py` (all importable: `tests/` is on `sys.path`, as `test_book_runner` itself imports `simkit`). Only non-`test_*` names are imported, so nothing is collected twice.

What the groups prove (numbers measured with a stand-in for phase 2's split while planning; all 29 tests passed in under 1 s):
- FACTOR on seeds 39 and 7, `top=20` (the roster params) and `top=4`, starting mid-month (2020-01-14, like the paper clock) and on a decision session (2020-02-03), through 2020-07-06 (six month boundaries) with a staggered dividend map: 8 equality runs. Across them: signal exits and a forced close (seed 7, top 4: S05/S07/... stop trading), `too_small` rejections (1,250 USD of cash), dividends credited in every run.
- TIMING (F1 params) on a SPY market that crosses its 200-day average down and back up: entry 2019-12-02, signal exit 2020-02-03, re-entry 2020-06-01, quarterly SPY dividends.
- A fixed allocator (AAA 0.4, GONE 0.4) under `MONTHLY_HOLD` and `MONTHLY_HOLD_TBILL`: entries, an add, trims, BIL idle buys, dividends (one on a never-held symbol that must be ignored), and GONE force-closed on 2025-03-17 after its last bar on 2025-03-14.
- No look-ahead: for every decision session of the FACTOR window, `decide_book` is unchanged when every bar dated on or after the session is changed (`mutate_from`) or deleted (`truncate_before`); and the whole loop run with each night's decision taken on a market cut at that night still equals `run_book` (FACTOR and TIMING).
- Splits: a hand-checked 2-for-1 on a held position; `settle_book` with a split equals `apply_book_split` followed by a split-free `settle_book` (whatever phase 2's internals); targets decided at 100 and executed after a 2-for-1 buy 9 shares at 50, not 4 (hand-checked); a 1-for-20 floor-to-zero closes the position before the step; a split of an unrelated symbol is a no-op.
**Code:**
```python
"""The book engine's night (``seer_engine.paper.book``; plan phase 4, contract C3, R1).

Four groups:

1. Same path: ``decide_book`` + ``settle_book`` looped night by night from ``new_book(cash0)``
   equal ``run_book`` field for field (snapshots, fills, trades, open_at_end, dividends_usd,
   costs_usd, rejections) under ``MONTHLY_HOLD``: FACTOR (12-1 momentum over members, SPY 200-day
   trend gate) on the seeded markets of tests/test_book_runner.py (delistings force closes),
   TIMING (F1, SPY over its 200-day average) on a SPY market that crosses its average twice,
   and a fixed allocator whose second name stops trading (a forced close) with dividends, with
   and without the idle instrument. Windows start mid-month (as the paper clock does) and on a
   month's first session; each spans several month boundaries.
2. No look-ahead: ``decide_book`` for session S is unchanged when every bar dated S or later
   is changed or deleted, and the loop run on markets cut at each night equals ``run_book``.
3. ``decide_book`` wiring: no allocator call off decision sessions, members and history at
   ``data_date``, the idle symbol never passed as held, argument checks.
4. ``settle_book``: splits (on a held position and on the targets decided for the split
   session), dividend routing, force-close timing from ``last_bar_date``, argument checks.

Simulator arithmetic (``seer_engine.sim``): buy cash ``q(p x n x 1.001)``, sell proceeds
``q(p x n x 0.999)``, ``q`` = 4 dp half-up; "open_limit" buys at ``min(open, q(last x 1.02))``
when the low trades below that limit.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
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
from seer_engine.backtest.book_runner import BookResult, DividendMap, run_book
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.runner import INITIAL_IDR
from seer_engine.paper.book import BookNight, decide_book, settle_book
from seer_engine.prices import Bar
from seer_engine.sim.book import Book, BookSnapshot, Position, Target, apply_book_split, new_book
from seer_engine.sim.model import initial_cash_usd
from seer_engine.sim.rules import DESIGN_V0, MONTHLY_HOLD, MONTHLY_HOLD_TBILL, is_decision_session
from seer_engine.strategies.f_factor import FACTOR, FactorParams
from seer_engine.strategies.f_index import TIMING, TimingParams

_ZERO = Decimal("0.0000")


# =========================================================================== the night loop


def cut_market(market: Market, session: date) -> Market:
    """``market`` as the database holds it the night before ``session``: no bar dated >= session."""
    return Market(
        history={s: truncate_before(h, session) for s, h in market.history.items()},
        membership=market.membership,
        fx=market.fx,
    )


def paper_run(
    market: Market,
    allocator: Any,
    params: Any,
    rules: Any,
    start: date,
    end: date,
    *,
    dividends: DividendMap | None = None,
    night_cut: bool = False,
) -> BookResult:
    """``run_book``'s result rebuilt from the night functions, one session at a time.

    Night of ``data_date``: ``decide_book`` (on the market cut after ``data_date`` with
    ``night_cut``). Night of S: ``settle_book`` with S's bars for every held or targeted symbol,
    no splits, and ``market.last_bar_date`` (the replay's view of which bars ended).
    """
    divs: DividendMap = {} if dividends is None else dividends
    rate = market.usd_idr_on(start)
    cash0 = initial_cash_usd(INITIAL_IDR, rate)
    book = new_book(cash0)
    data_date = dates.prev_session(start)
    snapshots = [BookSnapshot(date=data_date, cash_usd=book.cash, equity_usd=book.equity, invested_usd=_ZERO)]
    fills: list[Any] = []
    trades: list[Any] = []
    rejections: Counter[str] = Counter()
    dividends_usd = _ZERO

    def decide(d: date, held: frozenset[str]) -> tuple[tuple[Target, ...] | None, bool]:
        view = cut_market(market, dates.next_session(d)) if night_cut else market
        return decide_book(view, allocator, params, rules, d, held)

    targets, idle_added = decide(data_date, book.held())
    for session in dates.sessions(start, end):
        assert dates.next_session(data_date) == session
        symbols = set(book.held())
        if targets is not None:
            symbols.update(t.symbol for t in targets)
        bars = market.bars_on(session, sorted(symbols))
        night = settle_book(book, session, bars, targets, idle_added, rules, divs, (), market.last_bar_date)
        assert isinstance(night, BookNight)
        assert night.session == session and night.book.last_session == session
        assert night.targets == targets and night.splits == ()
        book = night.book
        fills.extend(night.fills)
        trades.extend(night.trades)
        for _, amount in night.dividends:
            dividends_usd += amount
        for _, reason in night.rejected:
            rejections[reason] += 1
        snapshots.append(night.snapshot)
        data_date = session
        targets, idle_added = decide(data_date, book.held())

    costs_usd = _ZERO
    for f in fills:
        costs_usd += f.cost_usd
    return BookResult(
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


def assert_same_run(got: BookResult, want: BookResult) -> None:
    """Field by field first (readable failures), then the whole result."""
    assert got.initial_cash == want.initial_cash
    assert len(got.snapshots) == len(want.snapshots)
    for a, b in zip(got.snapshots, want.snapshots):
        assert a == b, f"snapshot {b.date}"
    assert got.fills == want.fills
    assert got.trades == want.trades
    assert got.open_at_end == want.open_at_end
    assert got.dividends_usd == want.dividends_usd
    assert got.costs_usd == want.costs_usd
    assert got.rejections == want.rejections
    assert got == want


def every_session_dividends(market: Market, start: date, end: date, every: int, amount: str) -> dict[str, dict[date, Decimal]]:
    """A dividend of ``amount`` per share every ``every`` sessions of [start, end], staggered by symbol."""
    window = dates.sessions(start, end)
    out: dict[str, dict[date, Decimal]] = {}
    for i, symbol in enumerate(sorted(market.history)):
        out[symbol] = {window[k]: Decimal(amount) for k in range((3 * i) % every, len(window), every)}
    return out


# =========================================================================== 1. same path

# Seeded markets (tests/test_book_runner.py): 16 members S00..S15 and SPY on 380 sessions from
# 2019-01-02. 2020-01-14 (index 260) leaves 2020-01-31 as the first decision's data_date with
# 273 bars (12-1 momentum needs 253). Decisions: 02-03, 03-02, 04-01, 05-01, 06-01, 07-01.
# S05, S07, S09, S10 and S12 stop trading inside the window (forced closes when held).

FACTOR_START_MID = SEED_DAYS[260]  # 2020-01-14, mid-month like the paper clock
FACTOR_START_FIRST = SEED_DAYS[273]  # 2020-02-03, a decision session
FACTOR_END = SEED_DAYS[-1]  # 2020-07-06
F4_ROSTER = FactorParams(rank="momentum", top=20)  # F4-MOM12-N20-TREND (registry, read-only)
F4_TIGHT = FactorParams(rank="momentum", top=4)  # fewer names: signal exits, resizes, no_slot-free turnover


@lru_cache(maxsize=None)
def factor_dividends(seed: int) -> dict[str, dict[date, Decimal]]:
    return every_session_dividends(seeded_market(seed), FACTOR_START_MID, FACTOR_END, 17, "0.15")


@pytest.mark.parametrize("seed", [39, 7])
@pytest.mark.parametrize("params", [F4_ROSTER, F4_TIGHT], ids=["top20", "top4"])
@pytest.mark.parametrize("start", [FACTOR_START_MID, FACTOR_START_FIRST], ids=["mid-month", "first-of-month"])
def test_factor_nights_equal_run_book(seed, params, start):
    market = seeded_market(seed)
    divs = factor_dividends(seed)
    want = run_book(market, FACTOR, params, MONTHLY_HOLD, start, FACTOR_END, dividends=divs)
    got = paper_run(market, FACTOR, params, MONTHLY_HOLD, start, FACTOR_END, dividends=divs)
    assert_same_run(got, want)
    assert want.trades or want.open_at_end, "the run never bought anything"
    assert want.dividends_usd > 0, "no dividend was credited"


def test_factor_runs_cover_signal_exits_and_forced_closes():
    reasons: Counter[str] = Counter()
    for seed in (39, 7):
        for params in (F4_ROSTER, F4_TIGHT):
            r = run_book(seeded_market(seed), FACTOR, params, MONTHLY_HOLD, FACTOR_START_MID, FACTOR_END,
                         dividends=factor_dividends(seed))
            reasons.update(t.exit_reason for t in r.trades)
    assert reasons["signal"] > 0
    assert reasons["forced"] > 0


# SPY alone on 420 sessions from 2019-01-02: up 0.3 a session for 260 sessions, down 4 for 40
# (below its 200-day average), then up 3 (above it again). Window 2019-11-15 .. 2020-08-31.

TIMING_DAYS = session_days(420)
_spy_closes = [300.0 + 0.3 * t for t in range(260)]
_spy_closes += [_spy_closes[-1] - 4.0 * (t + 1) for t in range(40)]
_spy_closes += [_spy_closes[-1] + 3.0 * (t + 1) for t in range(120)]
TIMING_MARKET = Market(
    history={"SPY": hist("SPY", [round(c, 2) for c in _spy_closes], days=TIMING_DAYS)},
    membership=Membership(()),
    fx=((date(2018, 12, 31), Decimal("16000")),),
)
F1_PARAMS = TimingParams(hold="SPY", signal="SPY", rule="sma", n=200)  # F1-SPY-SMA200-M
TIMING_START_MID = TIMING_DAYS[220]
TIMING_START_FIRST = next(d for d in TIMING_DAYS[221:] if is_decision_session(MONTHLY_HOLD, d))
TIMING_END = TIMING_DAYS[-1]
SPY_DIVIDENDS = {"SPY": {d: Decimal("1.40") for d in TIMING_DAYS[221::63]}}


@pytest.mark.parametrize("start", [TIMING_START_MID, TIMING_START_FIRST], ids=["mid-month", "first-of-month"])
def test_timing_nights_equal_run_book(start):
    want = run_book(TIMING_MARKET, TIMING, F1_PARAMS, MONTHLY_HOLD, start, TIMING_END, dividends=SPY_DIVIDENDS)
    got = paper_run(TIMING_MARKET, TIMING, F1_PARAMS, MONTHLY_HOLD, start, TIMING_END, dividends=SPY_DIVIDENDS)
    assert_same_run(got, want)
    assert [t.exit_reason for t in want.trades] == ["signal"], "SPY is held, dropped below the SMA, then held again"
    assert len(want.open_at_end) == 1 and want.open_at_end[0].symbol == "SPY"
    assert want.dividends_usd > 0


# A fixed allocator: AAA and GONE at 0.4 each (BIL takes the 0.2 residual under the T-bill rules).
# GONE's last bar is 2025-03-14: it is force-closed on 2025-03-17 at its mark. Window
# 2025-01-15 (mid-month) .. 2025-05-30; decisions 02-03, 03-03, 04-01, 05-01.

FIXED_DAYS = dates.sessions(D("2024-12-02"), D("2025-05-30"))
FIXED_START, FIXED_END = D("2025-01-15"), D("2025-05-30")
GONE_LAST = D("2025-03-14")
FIXED_PARAMS = FixedParams((("AAA", Decimal("0.4")), ("GONE", Decimal("0.4"))))
FIXED_DIVIDENDS = {
    "AAA": {D("2025-02-20"): Decimal("0.10"), D("2025-05-15"): Decimal("0.12")},
    "GONE": {D("2025-03-03"): Decimal("0.20")},
    "BIL": {D("2025-04-15"): Decimal("0.30")},
    "ZZZ": {D("2025-02-20"): Decimal("9.99")},  # never held: never credited
}


def fixed_market() -> Market:
    n = len(FIXED_DAYS)
    aaa = hist("AAA", [round(10.0 + 0.05 * t, 2) for t in range(n)], days=FIXED_DAYS)
    gone = truncate_before(hist("GONE", [round(20.0 + 0.02 * t, 2) for t in range(n)], days=FIXED_DAYS),
                           dates.next_session(GONE_LAST))
    bil = hist("BIL", [100.0] * n, days=FIXED_DAYS, spread=0.05)
    return Market(
        history={"AAA": aaa, "BIL": bil, "GONE": gone},
        membership=Membership((("AAA", D("2020-01-02"), None), ("GONE", D("2020-01-02"), None))),
        fx=((D("2024-11-29"), Decimal("16000")),),
    )


@pytest.mark.parametrize("rules", [MONTHLY_HOLD, MONTHLY_HOLD_TBILL], ids=["monthly-hold", "monthly-hold-tbill"])
def test_fixed_nights_equal_run_book_with_dividends_and_a_forced_close(rules):
    market = fixed_market()
    want = run_book(market, FIXED, FIXED_PARAMS, rules, FIXED_START, FIXED_END, dividends=FIXED_DIVIDENDS)
    got = paper_run(market, FIXED, FIXED_PARAMS, rules, FIXED_START, FIXED_END, dividends=FIXED_DIVIDENDS)
    assert_same_run(got, want)
    forced = [t for t in want.trades if t.exit_reason == "forced"]
    assert [(t.symbol, t.exit_date) for t in forced] == [("GONE", D("2025-03-17"))]
    assert want.dividends_usd > 0
    if rules.idle_symbol is not None:
        assert any(f.symbol == "BIL" for f in want.fills)


def test_settle_book_reports_the_forced_symbols():
    market = fixed_market()
    book = new_book(initial_cash_usd(INITIAL_IDR, Decimal("16000")))
    data_date = dates.prev_session(FIXED_START)
    targets, idle_added = decide_book(market, FIXED, FIXED_PARAMS, MONTHLY_HOLD, data_date, book.held())
    nights: list[BookNight] = []
    for session in dates.sessions(FIXED_START, D("2025-03-18")):
        symbols = sorted(book.held() | ({t.symbol for t in targets} if targets is not None else set()))
        night = settle_book(book, session, market.bars_on(session, symbols), targets, idle_added, MONTHLY_HOLD,
                            {}, (), market.last_bar_date)
        nights.append(night)
        book = night.book
        targets, idle_added = decide_book(market, FIXED, FIXED_PARAMS, MONTHLY_HOLD, session, book.held())
    by_day = {n.session: n for n in nights}
    assert by_day[D("2025-03-14")].forced == ()
    night = by_day[D("2025-03-17")]
    assert night.forced == ("GONE",)
    assert [(f.symbol, f.reason) for f in night.fills] == [("GONE", "forced")]
    assert night.snapshot == BookSnapshot(D("2025-03-17"), night.book.cash, night.book.equity,
                                          night.book.positions[0].shares * night.book.positions[0].mark)
    assert by_day[D("2025-03-18")].forced == ()


# =========================================================================== 2. no look-ahead


def test_decide_book_ignores_every_bar_from_the_session_on():
    market = seeded_market(39)
    held_sets = (frozenset(), frozenset({"S00", "S05"}))
    nonempty = 0
    for session in dates.sessions(FACTOR_START_MID, FACTOR_END):
        if not is_decision_session(MONTHLY_HOLD, session):
            continue
        d = dates.prev_session(session)
        futures = {
            "changed": Market({s: mutate_from(h, session) for s, h in market.history.items()}, market.membership, market.fx),
            "deleted": cut_market(market, session),
        }
        for held in held_sets:
            for params in (F4_ROSTER, F4_TIGHT):
                before = decide_book(market, FACTOR, params, MONTHLY_HOLD, d, held)
                for name, future in futures.items():
                    assert decide_book(future, FACTOR, params, MONTHLY_HOLD, d, held) == before, (name, session)
                nonempty += bool(before[0])
    assert nonempty > 0


@pytest.mark.parametrize("seed", [39])
def test_nights_on_markets_cut_at_each_night_equal_run_book(seed):
    market = seeded_market(seed)
    divs = factor_dividends(seed)
    want = run_book(market, FACTOR, F4_TIGHT, MONTHLY_HOLD, FACTOR_START_MID, FACTOR_END, dividends=divs)
    got = paper_run(market, FACTOR, F4_TIGHT, MONTHLY_HOLD, FACTOR_START_MID, FACTOR_END, dividends=divs, night_cut=True)
    assert_same_run(got, want)


def test_timing_decisions_on_cut_markets_equal_run_book():
    want = run_book(TIMING_MARKET, TIMING, F1_PARAMS, MONTHLY_HOLD, TIMING_START_MID, TIMING_END, dividends=SPY_DIVIDENDS)
    got = paper_run(TIMING_MARKET, TIMING, F1_PARAMS, MONTHLY_HOLD, TIMING_START_MID, TIMING_END,
                    dividends=SPY_DIVIDENDS, night_cut=True)
    assert_same_run(got, want)


# =========================================================================== 3. decide_book wiring
#
# wiring_market (tests/test_book_runner.py): sessions 2025-02-14 .. 2025-03-14; AAA 10.0 + 0.1 t,
# BBB 20.0 + 0.2 t, BIL 100 flat, CCC 30 flat; AAA, BBB, CCC are members, BIL is not.


def test_decide_book_off_decision_sessions_is_none_without_calling_the_allocator():
    alloc = Scripted((("AAA", "0.5"),))
    # 2025-02-27 -> next session 2025-02-28: not the first session of March.
    assert decide_book(wiring_market(), alloc, None, MONTHLY_HOLD, D("2025-02-27"), frozenset()) == (None, False)
    assert alloc.calls == []


def test_decide_book_reads_members_and_history_at_data_date():
    alloc = Scripted((("AAA", "0.5"), ("BBB", "0.25")))
    # 2025-02-28 -> 2025-03-03, the first session of March.
    targets, idle_added = decide_book(wiring_market(), alloc, None, MONTHLY_HOLD, D("2025-02-28"), frozenset({"AAA"}))
    assert idle_added is False
    assert targets == (
        Target(symbol="AAA", weight=Decimal("0.5"), last=P("10.9")),
        Target(symbol="BBB", weight=Decimal("0.25"), last=P("21.8")),
    )
    (call,) = alloc.calls
    assert (call.path, call.data_date, call.seen) == ("plain", D("2025-02-28"), D("2025-02-28"))
    assert call.members == frozenset({"AAA", "BBB", "CCC"})
    assert call.held == frozenset({"AAA"})


def test_decide_book_appends_the_idle_residual_and_hides_the_idle_position():
    alloc = Scripted((("AAA", "0.5"),))
    targets, idle_added = decide_book(
        wiring_market(), alloc, None, MONTHLY_HOLD_TBILL, D("2025-02-28"), frozenset({"AAA", "BIL"})
    )
    assert idle_added is True
    assert [(t.symbol, t.weight) for t in targets] == [("AAA", Decimal("0.5")), ("BIL", Decimal("0.5"))]
    assert alloc.calls[0].held == frozenset({"AAA"})


def test_decide_book_argument_checks():
    market = wiring_market()
    alloc = Scripted()
    with pytest.raises(TypeError, match="Market"):
        decide_book(market.history, alloc, None, MONTHLY_HOLD, D("2025-02-28"), frozenset())
    with pytest.raises(TypeError, match="Allocator"):
        decide_book(market, object(), None, MONTHLY_HOLD, D("2025-02-28"), frozenset())
    with pytest.raises(ValueError, match="book"):
        decide_book(market, alloc, None, DESIGN_V0, D("2025-02-28"), frozenset())
    with pytest.raises(ValueError, match="NYSE session"):
        decide_book(market, alloc, None, MONTHLY_HOLD, D("2025-03-01"), frozenset())
    with pytest.raises(TypeError, match="held"):
        decide_book(market, alloc, None, MONTHLY_HOLD, D("2025-02-28"), "AAA")


# =========================================================================== 4. settle_book
#
# Hand-checked on 2025-03-03 (a decision session under MONTHLY_HOLD), MONTHLY_HOLD whole shares.

S = D("2025-03-03")
PREV = D("2025-02-28")


def _bar(symbol: str, d: date, o: str, h: str, lo: str, c: str) -> Bar:
    return Bar(symbol, d, P(o), P(h), P(lo), P(c), 1_000_000)


def _held_book() -> Book:
    """Cash 500, 10 AAA bought at 48 (cost 480.4800), marked at 50 on 2025-02-28: equity 1000."""
    aaa = Position(
        symbol="AAA", shares=Decimal("10"), mark=P("50"), entry_date=D("2025-02-03"), entry_price=P("48"),
        days_held=19, cost_usd=P("480.48"), income_usd=_ZERO, stop=None, take=None,
    )
    return Book(cash=P("500"), equity=P("1000"), positions=(aaa,), last_session=PREV)


def _always(symbol: str) -> date:
    return D("2025-12-31")


def test_two_for_one_split_on_a_held_position_hand_checked():
    # Split 2-for-1 on S, no decision for S: 20 shares, entry 24, mark 25 -> marked at S's close 25.80.
    bars = {"AAA": _bar("AAA", S, "25.5", "26", "25", "25.8")}
    night = settle_book(_held_book(), S, bars, None, False, MONTHLY_HOLD, {}, (("AAA", Decimal("2")),), _always)
    (p,) = night.book.positions
    assert (p.shares, p.entry_price, p.mark, p.days_held, p.cost_usd) == (Decimal("20"), P("24"), P("25.8"), 20, P("480.48"))
    assert night.book.cash == P("500")
    assert night.snapshot == BookSnapshot(S, P("500"), P("1016"), P("516"))
    assert night.fills == () and night.trades == () and night.forced == ()
    assert len(night.splits) == 1 and night.targets is None


def test_split_equals_apply_book_split_then_a_plain_settle():
    # Whatever the split rule does (phase 2), settle_book applies it first and steps the result.
    book = _held_book()
    targets = (Target(symbol="AAA", weight=Decimal("0.3"), last=P("50")), Target(symbol="BBB", weight=Decimal("0.3"), last=P("20")))
    bars = {
        "AAA": _bar("AAA", S, "16.5", "17", "16.4", "16.9"),
        "BBB": _bar("BBB", S, "20", "20.5", "19.5", "20.2"),
    }
    divs = {"AAA": {S: Decimal("0.05")}}
    factor = Decimal(3)
    split = apply_book_split(book, "AAA", factor, S, MONTHLY_HOLD, targets)
    plain = settle_book(split.book, S, bars, split.targets, False, MONTHLY_HOLD, divs, (), _always)
    got = settle_book(book, S, bars, targets, False, MONTHLY_HOLD, divs, (("AAA", factor),), _always)
    assert got.book == plain.book
    assert got.snapshot == plain.snapshot
    assert got.targets == split.targets
    assert got.fills == split.fills + plain.fills
    assert got.trades == ((split.trade,) if split.trade is not None else ()) + plain.trades
    assert got.dividends == plain.dividends == (("AAA", plain.dividends[0][1]),)
    assert got.splits == (split,)


def test_split_rescales_the_targets_decided_for_the_split_session():
    # Decided the night before at AAA 100; AAA splits 2-for-1 on S and opens at 50. Equity 1000,
    # weight 0.5: budget 500, sizing limit q(50 x 1.02) = 51 -> 9 shares (9 x 51 x 1.001 = 459.459).
    # Unscaled, the limit would be 102 and only 4 shares would be bought.
    book = new_book(P("1000"))
    book = Book(cash=book.cash, equity=book.equity, positions=(), last_session=PREV)
    targets = (Target(symbol="AAA", weight=Decimal("0.5"), last=P("100")),)
    bars = {"AAA": _bar("AAA", S, "50", "51", "49", "50.5")}
    night = settle_book(book, S, bars, targets, False, MONTHLY_HOLD, {}, (("AAA", Decimal("2")),), _always)
    assert night.targets == (Target(symbol="AAA", weight=Decimal("0.5"), last=P("50")),)
    (fill,) = night.fills
    assert (fill.side, fill.shares, fill.price, fill.cash_usd, fill.reason) == ("buy", Decimal("9"), P("50"), P("-450.45"), "entry")
    assert night.book.cash == P("549.55")
    assert night.snapshot == BookSnapshot(S, P("549.55"), P("1004.05"), P("454.5"))


def test_split_that_floors_a_position_to_zero_closes_it_before_the_step():
    # 1-for-20 on 10 shares: 0.5 post-split shares floor to 0; the whole holding is paid in lieu
    # (q(0.5 x 1000) = 500) and closed "forced" by the split rule. The ex-date dividend finds no
    # position, and the bar-ended force-close has nothing left to close.
    bars = {"AAA": _bar("AAA", S, "1000", "1010", "990", "1005")}
    divs = {"AAA": {S: Decimal("1")}}
    night = settle_book(_held_book(), S, bars, None, False, MONTHLY_HOLD, divs, (("AAA", Decimal("0.05")),), _always)
    (split,) = night.splits
    assert split.trade is not None and split.trade.exit_reason == "forced"
    assert night.trades == (split.trade,)
    assert night.fills == split.fills
    assert split.in_lieu == P("500")
    assert night.book.positions == () and night.dividends == () and night.forced == ()
    assert night.book.cash == P("1000")
    assert night.snapshot == BookSnapshot(S, P("1000"), P("1000"), _ZERO)


def test_split_of_an_unrelated_symbol_changes_nothing():
    book = _held_book()
    bars = {"AAA": _bar("AAA", S, "50", "51", "49", "50.5")}
    plain = settle_book(book, S, bars, None, False, MONTHLY_HOLD, {}, (), _always)
    got = settle_book(book, S, bars, None, False, MONTHLY_HOLD, {}, (("ZZZ", Decimal("4")),), _always)
    assert (got.book, got.fills, got.trades, got.snapshot) == (plain.book, plain.fills, plain.trades, plain.snapshot)


def test_dividends_routed_by_ex_date_for_held_symbols_only():
    bars = {"AAA": _bar("AAA", S, "50", "51", "49", "50.5")}
    divs = {"AAA": {S: Decimal("0.25"), PREV: Decimal("9")}, "BBB": {S: Decimal("1")}}
    night = settle_book(_held_book(), S, bars, None, False, MONTHLY_HOLD, divs, (), _always)
    assert night.dividends == (("AAA", P("2.5")),)
    assert night.book.cash == P("502.5")
    assert night.book.positions[0].income_usd == P("2.5")
    no_divs = replace(MONTHLY_HOLD, id="monthly-hold-nodiv", dividends=False)
    off = settle_book(_held_book(), S, bars, None, False, no_divs, divs, (), _always)
    assert off.dividends == () and off.book.cash == P("500")


def test_force_close_uses_last_bar_date():
    bars = {"AAA": _bar("AAA", S, "50", "51", "49", "50.5")}
    # A bar on S and last_bar_date == S: not gone.
    kept = settle_book(_held_book(), S, bars, None, False, MONTHLY_HOLD, {}, (), lambda s: S)
    assert kept.forced == ()
    # No bar on S and the latest bar known is the night before: closed at its mark (50).
    gone = settle_book(_held_book(), S, {}, None, False, MONTHLY_HOLD, {}, (), lambda s: PREV)
    assert gone.forced == ("AAA",)
    (fill,) = gone.fills
    assert (fill.reason, fill.price, fill.shares, fill.cash_usd) == ("forced", P("50"), Decimal("10"), P("499.5"))
    (trade,) = gone.trades
    assert (trade.exit_reason, trade.exit_date, trade.days_held) == ("forced", S, 20)
    assert gone.book.positions == ()
    assert gone.snapshot == BookSnapshot(S, P("999.5"), P("999.5"), _ZERO)
    # Never seen at all: also gone.
    assert settle_book(_held_book(), S, {}, None, False, MONTHLY_HOLD, {}, (), lambda s: None).forced == ("AAA",)


def test_settle_book_argument_checks():
    book = _held_book()
    with pytest.raises(TypeError, match="Book"):
        settle_book(object(), S, {}, None, False, MONTHLY_HOLD, {}, (), _always)
    with pytest.raises(ValueError, match="NYSE session"):
        settle_book(book, D("2025-03-01"), {}, None, False, MONTHLY_HOLD, {}, (), _always)
    with pytest.raises(ValueError, match="book"):
        settle_book(book, S, {}, None, False, DESIGN_V0, {}, (), _always)
    with pytest.raises(ValueError, match="idle_added"):
        settle_book(book, S, {}, None, True, MONTHLY_HOLD_TBILL, {}, (), _always)
    with pytest.raises(TypeError, match="idle_added"):
        settle_book(book, S, {}, None, 0, MONTHLY_HOLD, {}, (), _always)
    with pytest.raises(TypeError, match="dividends"):
        settle_book(book, S, {}, None, False, MONTHLY_HOLD, [("AAA", 1)], (), _always)
    with pytest.raises(TypeError, match="last_bar_date"):
        settle_book(book, S, {}, None, False, MONTHLY_HOLD, {}, (), {"AAA": S})
    with pytest.raises(TypeError, match="split"):
        settle_book(book, S, {}, None, False, MONTHLY_HOLD, {}, {"AAA": Decimal(2)}, _always)
    with pytest.raises(TypeError, match="Decimal"):
        settle_book(book, S, {}, None, False, MONTHLY_HOLD, {}, (("AAA", 2.0),), _always)
    with pytest.raises(ValueError, match="two splits"):
        settle_book(book, S, {}, None, False, MONTHLY_HOLD, {}, (("AAA", Decimal(2)), ("AAA", Decimal(3))), _always)
    with pytest.raises(ValueError, match="not after"):
        settle_book(book, PREV, {}, None, False, MONTHLY_HOLD, {}, (), _always)
```
**Impact:** new tests only. Runtime < 2 s (FACTOR on 17 symbols decides six times per run).

## Verification

**Build:** `engine/.venv/bin/python -c "import seer_engine.paper.book"` (after phases 1 and 2 have landed)
**Tests:**
- `engine/.venv/bin/pytest engine/tests/test_paper_book.py -q` — 29 passed
- purity: `engine/.venv/bin/pytest engine/tests -q -k purity` (phase 1's coverage of `paper/*.py` picks up `paper/book.py`)
- full suite (invariant 1): `docker start seer-pg`; `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q` — 0 failed, 0 skipped
**Manual check:** none.
**Exit criteria:** `test_paper_book.py` green (every FACTOR/TIMING/FIXED loop `==` its `run_book` result, no-look-ahead green, split wiring green); purity green with `paper/book.py` covered; no file outside the two listed changed.

## Assumptions

- Phase 2's `BookSplit` fields are `book`, `targets`, `in_lieu`, `trade`, `fills` (its plan, Step 3). If the reconciler renames them, only `settle_book`'s split loop (`done.book`, `done.targets`, `done.fills`, `done.trade`) and three tests (`test_split_equals_apply_book_split_then_a_plain_settle`, `test_split_that_floors_a_position_to_zero_closes_it_before_the_step`, the `in_lieu` assert) change.
- `apply_book_split(..., targets)` rescales the targets even when the book does not hold the symbol (phase 2 docstring: "Each target for `symbol` gets last, limit, stop and take rescaled"). `test_split_rescales_the_targets_decided_for_the_split_session` depends on it — that is the "split on targets persisted for the split session" case.
- `apply_book_split` refuses a `session` not after `book.last_session`, like `apply_split`; `settle_book` relies on it and on `step_book` for that check.
- Phase 1's purity test globs `paper/*.py` (minus `store.py`) the way `test_strategy_purity.py` globs `strategies/` and `backtest/`, with the same forbidden imports/attributes/calls.

## Handoffs

- **Phase 6 (store, R1):** persist `BookNight` as follows — `book.positions` -> `book_positions` (replace the strategy's rows), `fills` -> `book_fills` with `seq` = index + 1 in `BookNight.fills` order, `trades` -> `book_trades`, `snapshot` -> `equity_snapshots` (cash, equity), `paper_state.cash_usd/equity_usd/last_session` from `book`. When `night.splits` is non-empty and `night.targets` is not None, rewrite that session's `book_targets` prices with `night.targets`. The `last_bar_date` callable for a night is "max(bars.date) for the symbol" in the loaded window (None when absent); the dividend map can be the session's rows only.
- **Phase 6/7:** at paper start a book strategy is `new_book(initial_cash_usd(INITIAL_IDR, usd_idr))` with `paper_state.last_session = prev_session(paper_start)`, and the first decision is `decide_book(market, ..., data_date=prev_session(paper_start), held=frozenset())`; the persisted `pending_decision` flag is `targets is not None`, and `idle_added` must be persisted or re-derived (it is True only when the last target's symbol is `rules.idle_symbol`, which the allocator may never target itself — `_with_idle` raises otherwise). Both roster book strategies use `MONTHLY_HOLD` (no idle), so `idle_added` is always False for them today.
- **Phase 7 (command):** the night order per book strategy is `settle_book(S)` for each new session S (with S's applied splits), then `decide_book(data_date=S)` once; the market handed to `decide_book` must hold bars only through S (the loop with `night_cut=True` proves that is enough).
- **Phase 8 (replay):** `run_rules(..., usd_idr=paper_state.usd_idr)` is the comparison; the tests here already show the night functions equal `run_book` when no split hit the strategy and `last_bar_date` is the replay's.
- Not done here (R1 scope of other phases): bracket and benchmark nights (phase 3), dividends ingestion (phase 5).

## Rollback

Delete `engine/src/seer_engine/paper/book.py` and `engine/tests/test_paper_book.py` (or `git revert` the phase commit). Nothing else references them until phases 6–8 land.
