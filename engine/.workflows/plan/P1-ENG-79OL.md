> Adopted from `PAPER_TRADING_SHIP_PLAN.md` phase 3. Source: `.workflows/plan/paper-trading-ship/phase-3.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 3: Bracket and benchmark night cores

**Plan set:** `PAPER_TRADING_SHIP_PLAN.md`
**Analysis:** `20261004-082027-P4S7_code_analyzer.md`
**Satisfies:** R1: the engine paper step's pure core for the bracket strategy (A) and the SPY benchmark
**Depends on:** Phase 1 (the `seer_engine/paper/` package and purity coverage of `paper/*.py`)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/paper`

---

## Goal

After this phase, two pure modules step one paper night each:
- `paper/bracket.py` settles a bracket portfolio for a session (splits, then `sim.step`, then the forced close) and decides the next session's pending orders.
- `paper/benchmark.py` steps the SPY buy-and-hold benchmark, with dividends, one session at a time over state that can be persisted.

Tests loop the night functions over at least 300 synthetic NYSE sessions. They prove the result equals `run_backtest` and `buy_and_hold` exactly. Nothing reads or writes the database yet, and no runner, `sim` module or command changes.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `seer_engine.paper.bracket` (`engine/src/seer_engine/paper/bracket.py`):
  - `BracketNight` (frozen dataclass: `session: date`, `portfolio: sim.Portfolio`, `events: tuple[sim.Event, ...]`, `snapshot: sim.Snapshot`; properties `closed -> tuple[Order, ...]`, `expired -> tuple[Order, ...]`)
  - `LastBarDate = Callable[[str], date | None]`
  - `settle_bracket(pf: Portfolio, session: date, bars: Mapping[str, Bar], splits: Sequence[tuple[str, Decimal]], last_bar_date: LastBarDate) -> BracketNight`
  - `decide_bracket(pf: Portfolio, strategy: Strategy, params: Any, history: Mapping[str, History], members: Set[str], data_date: date) -> sim.SizingResult`
- `seer_engine.paper.benchmark` (`engine/src/seer_engine/paper/benchmark.py`):
  - `SPY = "SPY"`
  - `BenchmarkState` (frozen dataclass: `start: date`, `cash: Decimal`, `equity: Decimal`, `position: sim.Position | None`, `last_session: date`; properties `shares -> int`, `income_usd -> Decimal`; method `snapshot() -> Snapshot`)
  - `start_benchmark(cash0: Decimal, start: date) -> BenchmarkState`
  - `step_benchmark(state, session, bar, dividend, *, split: Decimal | None = None) -> tuple[BenchmarkState, Snapshot, tuple[sim.Fill, ...]]`
  - `split_benchmark(state, factor: Decimal, session: date) -> tuple[BenchmarkState, Decimal]`
- Tests: `engine/tests/test_paper_bracket.py`, `engine/tests/test_paper_benchmark.py`.

**Signature changes:** none to existing code. Against C3:
- `step_benchmark` gains one keyword-only argument, `split=None`. It is additive: the C3 call `step_benchmark(state, session, bar, dividend)` is unchanged.
- `split_benchmark` is new. The reason is the decision on the benchmark split path, below.

**Decision: a SPY split is handled, not raised.** `split_benchmark` follows `sim.apply_split`'s rule for an open bracket position and reuses its exact-fraction helpers:
- shares become `floor(shares × ratio)`;
- the fraction is paid as cash in lieu, `q(fraction × new mark)`, credited to cash and to the position's `income_usd` (the plan index's book-split decision);
- mark and entry price become `q(p / ratio)`;
- a holding that floors to 0 is paid out entirely in lieu.

Raising would be wrong here. The `paper` command steps every roster strategy in one transaction (C4), so a raise on a SPY split would stop paper trading for all four strategies, every night, until someone changed the code. That is a large cost for an event whose rule is already fully defined. SPY has never split, so the rule is a completeness path, and the tests pin it.

**Persisted shape (for phase 6):**
- `BenchmarkState` maps onto `paper_state.last_session`, `cash_usd` and `equity_usd`, plus at most one `book_positions` row. That row comes from `state.position`, a `sim.Position` with symbol `SPY`, whole shares as a `Decimal`, `stop`/`take` NULL and `exit_pending` false.
- `start` is `strategies.paper_start`.
- Every buy is a `sim.Fill` with side `buy` and reason `entry` (the first buy, or a reinvestment that opens the holding) or `add` (a reinvestment). These go to `book_fills`, and the store assigns `seq` from 1.
- `BracketNight.portfolio` holds the live orders. `orders.mark` comes from `portfolio.marks`.
- Terminal orders appear once each, inside `events`:
  - `exit` events cover tp, sl, time and gap exits, forced closes, and split floor-to-zero exits.
  - `expire` events cover step expiries and split floor-to-zero pendings.

**Requires (from earlier phases):**
- Phase 1: `engine/src/seer_engine/paper/__init__.py` exists (a docstring only, no re-exports).
- Phase 1: the purity test covers `paper/*.py` except `store.py`. Both new modules import only `seer_engine.dates`, `seer_engine.prices`, `seer_engine.sim` (including `sim.split_adjust` private helpers), `seer_engine.strategies.base` and `seer_engine.backtest.benchmark._whole_shares`. All of these are pure.

**Leaves alone (owned by others):**
- `sim/*` (phase 2 owns `sim/book.apply_book_split`; this phase only imports from `sim`).
- The closed records (invariant 2): `backtest/runner.py`, `backtest/benchmark.py`, `backtest/book_runner.py`, `backtest/registry.py`.
- `paper/__init__.py` and `paper/roster.py` (phase 1).
- `paper/book.py` (phase 4).
- `paper/store.py` and `backtest/io.py` (phase 6).
- `commands/*` (phases 7 to 9).
- `paper/replay.py` (phase 8).
- Every migration and DB module.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/paper/bracket.py` | create (line 1) | `BracketNight`, `settle_bracket`, `decide_bracket`: the `run_backtest` loop body (`runner.py:171-200`) split at the night boundary, plus splits before the step |
| `engine/src/seer_engine/paper/benchmark.py` | create (line 1) | `BenchmarkState`, `start_benchmark`, `step_benchmark`, `split_benchmark`: the `buy_and_hold` loop (`benchmark.py:162-177`) one session at a time |
| `engine/tests/test_paper_bracket.py` | create (line 1) | equality with `run_backtest` over 424 sessions (plain and with a forced close); hand-checked split, forced-close and validation tests; no look-ahead |
| `engine/tests/test_paper_benchmark.py` | create (line 1) | equality with `buy_and_hold` over 374 sessions (total return and price-only, and every prefix); hand-checked `Position`/`Fill`; reinvestment that opens the holding; state round trip; split rule |

Nothing else changes. `paper/__init__.py` stays docstring-only (phase 1), so these modules are imported by their full path (`seer_engine.paper.bracket`).

## Implementation Steps

### Step 1: `paper/bracket.py`
**File:** `engine/src/seer_engine/paper/bracket.py:1` (new)
**Change:** Create the module. It mirrors `run_backtest`'s loop body (`backtest/runner.py:171-200`) exactly:
- `decide_bracket` is lines 172-183 for the `prepared is None` path, with `session = next_session(data_date)`.
- `settle_bracket` is lines 185-198, with `apply_split` per split before the step.
- The `last_bar_date` callable stands in for `market.last_bar_date`:
  - in tests, the backtest's knowledge;
  - live (phase 7), "latest stored bar for the symbol", which gives the plan index's "force-close rule live".
- Splits are sorted by symbol so the event order is deterministic. Each `(symbol, session)` has at most one split (`split_adjustments` PK).
- `decide_bracket` refuses a portfolio that has not been settled through `data_date`. That catches a store that hands over stale state.

**Code:**
```python
"""One paper night of a bracket strategy (design-§5 brackets, ``DESIGN_V0``): the loop body of
``backtest.runner.run_backtest`` split at the night boundary.

Pure: no database, network, clock or randomness. The runner steps session S as

    size_picks(pf, picks(data_date = prev_session(S)), S) -> step(S) -> close_unpriced(gone)

and the nightly paper job, which only knows S's bars after S's close, steps it as two calls on
two nights:

- night of ``prev_session(S)``: :func:`decide_bracket` (the strategy's picks on history cut at
  ``data_date``, sized into ``pf`` as pending orders for ``next_session(data_date) = S``);
- night of ``S``: :func:`settle_bracket` (splits executing on S, then ``sim.step``, then the
  forced close of open positions whose symbol has no bar on S or later).

Looping ``decide_bracket`` + ``settle_bracket`` over a window gives exactly ``run_backtest``'s
snapshots, events, closed orders, open orders and rejections (tests/test_paper_bracket.py).

Splits are the one thing the runner never sees (its bars are split-adjusted already). Live state
is kept in the units it was sized in, so a split executing on S that ``nightly`` applied to the
stored bars (``split_adjustments.applied``) is applied to the portfolio exactly once, here,
before S is stepped (``sim.apply_split``; package docstring of ``seer_engine.sim``).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence, Set
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from seer_engine import dates
from seer_engine.prices import Bar
from seer_engine.sim import (
    Event,
    Order,
    Portfolio,
    SizingResult,
    Snapshot,
    apply_split,
    close_unpriced,
    size_picks,
    step,
)
from seer_engine.strategies.base import History, Strategy

LastBarDate = Callable[[str], date | None]


@dataclass(frozen=True, slots=True)
class BracketNight:
    """One settled session of a bracket strategy.

    - ``portfolio``: the state after the session (live orders only, ``last_session = session``).
    - ``events``: every simulator event of the session, in this order: split events (splits by
      symbol, each in slot order), then ``sim.step``'s exits, fills and expiries, then the
      forced closes of gone symbols (slot order).
    - ``snapshot``: the session's ``equity_snapshots`` row, after any forced close (the runner
      replaces the step's snapshot the same way).
    """

    session: date
    portfolio: Portfolio
    events: tuple[Event, ...]
    snapshot: Snapshot

    @property
    def closed(self) -> tuple[Order, ...]:
        """The orders closed on this session (exit events, forced included), in event order."""
        return tuple(e.order for e in self.events if e.kind == "exit")

    @property
    def expired(self) -> tuple[Order, ...]:
        """The pending orders that expired on this session, in event order."""
        return tuple(e.order for e in self.events if e.kind == "expire")


def _session(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    if not dates.is_session(d):
        raise ValueError(f"{name} {d} is not an NYSE session")
    return d


def _splits(splits: Sequence[tuple[str, Decimal]]) -> list[tuple[str, Decimal]]:
    """``splits`` validated and sorted by symbol (one split per symbol and session)."""
    if isinstance(splits, (str, bytes)) or not isinstance(splits, Sequence):
        raise TypeError(f"splits must be a sequence of (symbol, factor), got {type(splits).__name__}")
    out: dict[str, Decimal] = {}
    for item in splits:
        if not (isinstance(item, tuple) and len(item) == 2):
            raise TypeError(f"a split is (symbol, factor), got {item!r}")
        symbol, factor = item
        if not isinstance(symbol, str):
            raise TypeError(f"split symbol must be a str, got {type(symbol).__name__}")
        if not symbol:
            raise ValueError("empty split symbol")
        if not isinstance(factor, Decimal):
            raise TypeError(f"split factor for {symbol} must be a Decimal, got {type(factor).__name__}")
        if symbol in out:
            raise ValueError(f"two splits for {symbol} on one session")
        out[symbol] = factor
    return sorted(out.items())


def settle_bracket(
    pf: Portfolio,
    session: date,
    bars: Mapping[str, Bar],
    splits: Sequence[tuple[str, Decimal]],
    last_bar_date: LastBarDate,
) -> BracketNight:
    """Settle ``session`` for a bracket portfolio, exactly like one ``run_backtest`` iteration
    after its ``size_picks``.

    ``pf`` holds the pending orders decided for ``session`` (``decide_bracket`` the night
    before). ``bars`` maps symbol -> that session's split-adjusted ``Bar`` (at least every live
    symbol that has one; others are ignored). ``splits`` lists ``(symbol, factor)`` for every
    split executing on ``session`` that was applied to the stored bars, ``factor =
    split_to / split_from``; each is applied with ``sim.apply_split`` before the step, in symbol
    order. ``last_bar_date(symbol)`` is the date of the symbol's last known bar (None when it has
    none): an open position whose symbol has no bar on ``session`` or later is force-closed at
    its mark after the step (``sim.close_unpriced``), and the snapshot is replaced by the
    post-close one.

    Raises what the simulator raises: TypeError on wrong types, ValueError when ``session`` is
    not a session after ``pf.last_session``, a pending order is for another session, or a split
    factor is not a split ratio.
    """
    if not isinstance(pf, Portfolio):
        raise TypeError(f"pf must be a Portfolio, got {type(pf).__name__}")
    _session("session", session)
    if not callable(last_bar_date):
        raise TypeError("last_bar_date must be callable: symbol -> date | None")
    ordered = _splits(splits)

    events: list[Event] = []
    for symbol, factor in ordered:
        pf, split_events = apply_split(pf, symbol, factor, session)
        events.extend(split_events)

    result = step(pf, session, bars)
    pf = result.portfolio
    events.extend(result.events)
    snapshot = result.snapshot

    gone = []
    for o in pf.open_orders():
        last = last_bar_date(o.symbol)
        if last is None or last < session:
            gone.append(o.symbol)
    if gone:
        pf, forced = close_unpriced(pf, gone)
        events.extend(forced)
        snapshot = Snapshot(session, pf.cash, pf.equity)

    return BracketNight(session=session, portfolio=pf, events=tuple(events), snapshot=snapshot)


def decide_bracket(
    pf: Portfolio,
    strategy: Strategy,
    params: Any,
    history: Mapping[str, History],
    members: Set[str],
    data_date: date,
) -> SizingResult:
    """The pending orders for ``next_session(data_date)``: ``strategy.picks`` on ``history`` cut
    at ``data_date`` (the ``prepared=None`` path of ``run_backtest``), sized into ``pf`` with
    ``sim.size_picks``.

    ``members`` is the point-in-time universe on ``data_date``. ``pf`` must be the portfolio
    after ``data_date`` was settled (``pf.last_session == data_date``), or a fresh portfolio
    (``last_session`` None) on the night before the first paper session. Bars dated after
    ``data_date`` are never read (no look-ahead).
    """
    if not isinstance(pf, Portfolio):
        raise TypeError(f"pf must be a Portfolio, got {type(pf).__name__}")
    _session("data_date", data_date)
    if pf.last_session is not None and pf.last_session != data_date:
        raise ValueError(
            f"data_date {data_date} is not the portfolio's last settled session {pf.last_session}"
        )
    if not isinstance(history, Mapping):
        raise TypeError(f"history must be a Mapping, got {type(history).__name__}")
    cut = {s: h.upto(data_date) for s, h in history.items()}
    picks = strategy.picks(cut, members, data_date, params)
    return size_picks(pf, picks, dates.next_session(data_date))
```
**Impact:** New module, pure. No existing caller.

### Step 2: `paper/benchmark.py`
**File:** `engine/src/seer_engine/paper/benchmark.py:1` (new)
**Change:** Create the module. It mirrors `buy_and_hold` (`backtest/benchmark.py:162-177`) one session at a time, and reuses its `_whole_shares` rule by import (`benchmark.py:103`):
- On `start`: buy at the open. A dividend that day is ignored.
- On every later session: if a dividend is given, credit `q(shares × amount)` and reinvest `_whole_shares(cash, close)` at the close.
- Every session: mark at the close, `equity = q(cash + shares × close)`.

The state must be stepped on every session (`session == next_session(last_session)`), because `buy_and_hold` marks every session and a skipped session could miss a dividend. The holding is a `sim.Position`, so phase 6 persists it as a `book_positions` row with no new column.

`days_held` counts sessions from the first buy (fill session = 1), as `Position` defines it. `cost_usd` is the sum of buy cash. `income_usd` is the dividends credited, plus split cash in lieu.

The split rule (see the Decision in the Interface Contract) reuses `sim.split_adjust`'s `_split_ratio`, `_split_shares`, `_rescale_price` and `_q_exact`, so the factor is handled as an exact fraction, as `apply_split` handles it.

**Code:**
```python
"""One paper night of the SPY buy-and-hold benchmark: ``backtest.benchmark.buy_and_hold``'s loop
body, stepped one session at a time over persisted state.

Pure: no database, network, clock or randomness. Rules, identical to ``buy_and_hold`` (total
return, dividends reinvested):

- :func:`start_benchmark` holds ``cash0 = q(initial cash)`` and nothing else; its
  :meth:`BenchmarkState.snapshot` is ``Snapshot(prev_session(start), cash0, cash0)``, the
  curve's first point.
- On ``start`` (the first paper session), buy ``_whole_shares(cash, open)`` whole shares at the
  open, paying ``sim.buy_cost``; the remainder sits idle. A dividend with ex-date ``start`` is
  not credited (bought at the open, not a holder at the previous close).
- On every later session with a SPY dividend whose ex-date is that session, credit
  ``q(shares × amount)`` and buy ``_whole_shares(cash, close)`` more at that close.
- Every session is marked at its close: ``equity = q(cash + shares × close)``. Nothing is sold.

The holding is a ``sim.book.Position`` (symbol ``SPY``, whole shares as a Decimal, no stop or
take), so the store persists it as one ``book_positions`` row; ``cost_usd`` is every buy's cash,
``income_usd`` every dividend credited (plus any split cash in lieu). Each buy is a
``sim.book.Fill``: ``entry`` (the first buy) or ``add`` (a reinvestment), for ``book_fills``.

Splits: ``buy_and_hold`` never sees one (its bars are pre-adjusted), and SPY has never split. A
split executing on a session that ``nightly`` applied to the stored bars is still handled, by
:func:`split_benchmark` (also reachable as ``step_benchmark(..., split=factor)``), with
``sim.apply_split``'s rule for an open bracket position: shares become
``floor(shares × ratio)``, the fraction is paid as cash in lieu ``q(fraction × new mark)``
(added to cash and to the position's ``income_usd``), mark and entry price become
``q(price / ratio)`` exactly; a holding that floors to 0 shares is paid out entirely in lieu.
Raising instead would fail the whole paper night (every roster strategy is stepped in one
transaction) for an event that is fully determined and cheap to define.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction

from seer_engine import dates
from seer_engine.backtest.benchmark import _whole_shares
from seer_engine.prices import Bar
from seer_engine.sim import COST_RATE, Fill, Position, Snapshot, buy_cost, q
from seer_engine.sim.split_adjust import _q_exact, _rescale_price, _split_ratio, _split_shares

SPY = "SPY"
_ZERO = Decimal("0.0000")


def _session(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    if not dates.is_session(d):
        raise ValueError(f"{name} {d} is not an NYSE session")
    return d


def _money(name: str, x: object) -> Decimal:
    if not isinstance(x, Decimal):
        raise TypeError(f"{name} must be a Decimal, got {type(x).__name__}")
    if not x.is_finite():
        raise ValueError(f"{name} must be finite, got {x!r}")
    return x


@dataclass(frozen=True, slots=True)
class BenchmarkState:
    """The SPY benchmark between nights.

    - ``start``: the first paper session (``strategies.paper_start``); the open of ``start`` buys.
    - ``cash``: idle cash, 4 dp, never negative.
    - ``equity``: equity at ``last_session``'s close (``cash0`` before the first session).
    - ``position``: the SPY holding, or None (before ``start``, or when cash never bought a share).
    - ``last_session``: the last session stepped; ``prev_session(start)`` before the first.

    Persisted as ``paper_state`` (``last_session``, ``cash_usd``, ``equity_usd``) plus one
    ``book_positions`` row from ``position``; ``start`` comes back from ``paper_start``.
    """

    start: date
    cash: Decimal
    equity: Decimal
    position: Position | None
    last_session: date

    def __post_init__(self) -> None:
        _session("start", self.start)
        if _money("cash", self.cash) < 0:
            raise ValueError(f"cash must be >= 0, got {self.cash}")
        _money("equity", self.equity)
        _session("last_session", self.last_session)
        day0 = dates.prev_session(self.start)
        if self.last_session < day0:
            raise ValueError(f"last_session {self.last_session} is before {day0}, the day before start")
        p = self.position
        if p is not None:
            if not isinstance(p, Position):
                raise TypeError(f"position must be a Position, got {type(p).__name__}")
            if p.symbol != SPY:
                raise ValueError(f"the benchmark holds {SPY}, got {p.symbol}")
            if p.shares != p.shares.to_integral_value():
                raise ValueError(f"the benchmark holds whole shares, got {p.shares}")
            if p.stop is not None or p.take is not None or p.exit_pending:
                raise ValueError("the benchmark position has no stop, take or pending exit")
            if not self.start <= p.entry_date <= self.last_session:
                raise ValueError(
                    f"position entry {p.entry_date} is outside [{self.start}, {self.last_session}]"
                )
        if self.last_session == day0 and (p is not None or self.cash != self.equity):
            raise ValueError("before the first session the benchmark holds cash only")

    @property
    def shares(self) -> int:
        """Whole SPY shares held (0 without a position)."""
        return 0 if self.position is None else int(self.position.shares)

    @property
    def income_usd(self) -> Decimal:
        """Cash dividends credited to the current holding (plus split cash in lieu, if any)."""
        return _ZERO if self.position is None else self.position.income_usd

    def snapshot(self) -> Snapshot:
        """``Snapshot(last_session, cash, equity)``: day 0 right after :func:`start_benchmark`."""
        return Snapshot(date=self.last_session, cash_usd=self.cash, equity_usd=self.equity)


def start_benchmark(cash0: Decimal, start: date) -> BenchmarkState:
    """The benchmark the night before ``start``: ``q(cash0)`` in cash, nothing held.

    Raises TypeError when ``cash0`` is not a Decimal and ValueError when it is not > 0 or
    ``start`` is not an NYSE session (``buy_and_hold``'s checks).
    """
    cash = q(_money("cash0", cash0))
    if cash <= 0:
        raise ValueError(f"cash0 must be > 0, got {cash0}")
    _session("start", start)
    return BenchmarkState(
        start=start, cash=cash, equity=cash, position=None, last_session=dates.prev_session(start)
    )


def _check_bar(bar: object, session: date) -> Bar:
    if not isinstance(bar, Bar):
        raise TypeError(f"the SPY bar on {session} must be a Bar, got {type(bar).__name__}")
    if bar.symbol != SPY:
        raise ValueError(f"expected a {SPY} bar, got {bar.symbol}")
    if bar.date != session:
        raise ValueError(f"the SPY bar for {session} is dated {bar.date}")
    for name in ("open", "high", "low", "close"):
        value = getattr(bar, name)
        if not isinstance(value, Decimal):
            raise TypeError(f"SPY {name} must be a Decimal, got {type(value).__name__}")
        if not value.is_finite() or value <= 0:
            raise ValueError(f"SPY {name} on {session} must be a finite price > 0, got {value}")
    return bar


def _buy_fill(session: date, price: Decimal, shares: int, cost: Decimal, reason: str) -> Fill:
    n = Decimal(shares)
    return Fill(
        session_date=session,
        symbol=SPY,
        side="buy",
        shares=n,
        price=price,
        cash_usd=-cost,
        cost_usd=q(price * n * COST_RATE),
        reason=reason,  # type: ignore[arg-type]
    )


def split_benchmark(state: BenchmarkState, factor: Decimal, session: date) -> tuple[BenchmarkState, Decimal]:
    """Rewrite the SPY holding in post-split units for a split executing on ``session``
    (``factor = split_to / split_from``), before ``session`` is stepped.

    Returns the new state and the cash paid in lieu (``0.0000`` when nothing is held or the
    split leaves no fraction). ``equity`` and ``last_session`` are untouched, as in
    ``sim.apply_split``. Raises ValueError when ``factor`` is not a split ratio, ``session`` is
    not a session after ``state.last_session``, or the rescaled prices cannot be held at 4 dp.
    """
    if not isinstance(state, BenchmarkState):
        raise TypeError(f"state must be a BenchmarkState, got {type(state).__name__}")
    ratio = _split_ratio(factor)
    _session("session", session)
    if session <= state.last_session:
        raise ValueError(f"split session {session} must be after the last stepped session {state.last_session}")
    p = state.position
    if p is None:
        return state, _ZERO
    whole, fraction = _split_shares(int(p.shares), ratio)
    new_mark = _rescale_price(p.mark, ratio)
    new_entry = _rescale_price(p.entry_price, ratio)
    if new_mark <= 0 or new_entry <= 0:
        raise ValueError(f"{SPY}: a split of ratio {ratio} leaves prices that 4 dp cannot hold")
    in_lieu = _q_exact(fraction * Fraction(new_mark))
    cash = state.cash + in_lieu
    if whole == 0:
        return replace(state, cash=cash, position=None), in_lieu
    position = replace(
        p,
        shares=Decimal(whole),
        mark=new_mark,
        entry_price=new_entry,
        income_usd=p.income_usd + in_lieu,
    )
    return replace(state, cash=cash, position=position), in_lieu


def step_benchmark(
    state: BenchmarkState,
    session: date,
    bar: Bar,
    dividend: Decimal | None,
    *,
    split: Decimal | None = None,
) -> tuple[BenchmarkState, Snapshot, tuple[Fill, ...]]:
    """Step the benchmark through ``session`` (which must be ``next_session(state.last_session)``:
    the benchmark is stepped on every session, like ``buy_and_hold``).

    ``bar`` is SPY's bar on ``session``; ``dividend`` the SPY cash dividend per share with
    ex-date ``session`` (None when there is none; ignored on ``start``). ``split`` is the factor
    of a SPY split executing on ``session`` that was applied to the stored bars (None when there
    is none); it is applied first (:func:`split_benchmark`).

    Returns the new state, the session's snapshot and the buys made (``entry`` at ``start``'s
    open, ``add`` for a reinvestment at the close, or ``entry`` when a reinvestment opens the
    holding).
    """
    if not isinstance(state, BenchmarkState):
        raise TypeError(f"state must be a BenchmarkState, got {type(state).__name__}")
    _session("session", session)
    expected = dates.next_session(state.last_session)
    if session != expected:
        raise ValueError(f"the benchmark steps every session: expected {expected}, got {session}")
    b = _check_bar(bar, session)
    if dividend is not None:
        if _money("dividend", dividend) <= 0:
            raise ValueError(f"dividend must be > 0, got {dividend}")
    if split is not None:
        state, _ = split_benchmark(state, split, session)

    cash = state.cash
    pos = state.position
    fills: list[Fill] = []
    if session == state.start:
        shares = _whole_shares(cash, b.open)
        cost = buy_cost(b.open, shares)
        cash -= cost
        if shares > 0:
            price = q(b.open)
            pos = Position(
                symbol=SPY,
                shares=Decimal(shares),
                mark=b.close,
                entry_date=session,
                entry_price=price,
                days_held=1,
                cost_usd=cost,
                income_usd=_ZERO,
                stop=None,
                take=None,
            )
            fills.append(_buy_fill(session, price, shares, cost, "entry"))
    else:
        if pos is not None:
            pos = replace(pos, days_held=pos.days_held + 1)
        if dividend is not None:
            held = 0 if pos is None else int(pos.shares)
            income = q(held * dividend)
            cash += income
            if pos is not None:
                pos = replace(pos, income_usd=pos.income_usd + income)
            more = _whole_shares(cash, b.close)
            if more > 0:
                cost = buy_cost(b.close, more)
                cash -= cost
                price = q(b.close)
                if pos is None:
                    pos = Position(
                        symbol=SPY,
                        shares=Decimal(more),
                        mark=b.close,
                        entry_date=session,
                        entry_price=price,
                        days_held=1,
                        cost_usd=cost,
                        income_usd=_ZERO,
                        stop=None,
                        take=None,
                    )
                    fills.append(_buy_fill(session, price, more, cost, "entry"))
                else:
                    pos = replace(pos, shares=pos.shares + more, cost_usd=pos.cost_usd + cost)
                    fills.append(_buy_fill(session, price, more, cost, "add"))

    if pos is not None:
        pos = replace(pos, mark=b.close)
    held = 0 if pos is None else int(pos.shares)
    equity = q(cash + held * b.close)
    new = BenchmarkState(start=state.start, cash=cash, equity=equity, position=pos, last_session=session)
    return new, Snapshot(date=session, cash_usd=cash, equity_usd=equity), tuple(fills)
```
**Impact:** New module, pure. No existing caller.

### Step 3: `tests/test_paper_bracket.py`
**File:** `engine/tests/test_paper_bracket.py:1` (new)
**Change:** The tests:
- **Equality.** `run_nights` loops `decide_bracket(data_date)` then `settle_bracket(next session)` over 2023-10-19 to 2025-06-30 (424 sessions; `START = SESSIONS[200]`, so A has 200 bars on the first data_date). It packs the result into a `RunResult` and asserts equality with `run_backtest(..., prepared=None)`, field by field and as a whole. The synthetic market produces tp, sl, gap and time exits, expiries and `lt_one_share` rejections, and the test asserts each one so it cannot pass vacuously.
- **Forced close.** The same equality holds on a market where UPC's bars stop on a session at whose close UPC is open. Exactly one forced close follows on the next session, and it is the last event of that night.
- **Splits.** One night is hand-checked with a reverse split on an open order (cash in lieu) and a forward split on a pending order that then fills in post-split units. A split on an unheld symbol changes nothing.
- **Forced-close rule.** Hand-checked, including the `last_bar_date` cases: None, before, on, and after the session.
- **No look-ahead.** Every bar dated on or after S is mutated (`stratkit.mutate_from`) for a sample of data_dates, and the decision stays the same. The sample must place at least one order.
- **Validation.** Bad inputs raise.

**Code:**
```python
"""Bracket paper nights (plan phase 3, contract C3): ``decide_bracket`` + ``settle_bracket`` looped
over a window equal ``run_backtest`` exactly; splits on a pending and an open order; the forced
close; no look-ahead.

Simulator arithmetic in the hand-checked comments: ``buy_cost(p, n) = q(p × n × 1.001)``,
``sell_proceeds(p, n) = q(p × n × 0.999)``; fill when ``low < limit`` at ``min(open, limit)``;
``sim.apply_split`` divides prices by the ratio and floors shares, paying the fraction of an open
position as cash in lieu at the new mark.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import Decimal

import pytest
from simkit import D, P, bar, opened, pending, portfolio
from stratkit import mutate_from

from seer_engine import dates
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.runner import INITIAL_IDR, RunResult, run_backtest
from seer_engine.paper.bracket import BracketNight, decide_bracket, settle_bracket
from seer_engine.prices import Bar
from seer_engine.sim import Event, Snapshot, initial_cash_usd, new_portfolio
from seer_engine.strategies.a import STRATEGY_A, STRATEGY_A_PARAMS
from seer_engine.strategies.base import history_from_bars

# --------------------------------------------------------------------------- synthetic market

SESSIONS = dates.sessions(D("2023-01-03"), D("2025-06-30"))
# (symbol, phase, first price). UPA and UPE dip on the same sessions; BIG is too dear for one
# share of a slot budget (``lt_one_share`` rejections).
SYMBOLS = (("UPA", 0, 100.0), ("UPB", 7, 100.0), ("UPC", 13, 100.0), ("UPD", 3, 100.0), ("UPE", 0, 100.0), ("BIG", 7, 5000.0))


def _bars(symbol: str, phase: int, first: float) -> list[Bar]:
    """An uptrend (+0.6 % a session) with two -3 % sessions every 20 (shifted by ``phase``) and a
    deep intraday low the session after, so Strategy A's setup (close > SMA200, RSI(2) < 10,
    dollar volume ~1e8 > 2e7) fires and its limit fills. Every 100 sessions the dips end
    differently: a gap through the stop (m = 20), no fill (39), an intraday drop through the stop
    (60), a take-profit (80) and five flat sessions that run into the time stop (0-5). Prices are
    rounded to 4 dp first, so the float64 History holds exactly what ``bars`` would."""
    out = []
    prev = first + phase
    for t, d in enumerate(SESSIONS):
        k = (t + phase) % 20
        m = (t + phase) % 100
        c = prev * 0.97 if k in (17, 18) else prev * 1.006
        o = prev
        lo = min(o, c) * (0.97 if k == 19 else 0.995)
        hi = max(o, c) * 1.005
        if m == 20:
            o = prev * 0.93
            c = o * 1.004
            lo = o * 0.995
            hi = c * 1.005
        elif m == 39:
            lo = min(o, c) * 0.999
        elif m == 60:
            o, c, lo, hi = prev, prev, prev * 0.95, prev * 1.001
        elif m < 6:
            o = prev
            c = prev * 1.0005
            lo = prev * 0.999
            hi = c * 1.001
        out.append(bar(symbol, d, f"{o:.4f}", f"{hi:.4f}", f"{lo:.4f}", f"{c:.4f}", 1_000_000))
        prev = float(f"{c:.4f}")
    return out


def market(cut: date | None = None) -> Market:
    """The synthetic market; with ``cut``, UPC's bars stop at ``cut`` (delisted after it)."""
    history = {}
    for symbol, phase, first in SYMBOLS:
        rows = _bars(symbol, phase, first)
        if symbol == "UPC" and cut is not None:
            rows = [b for b in rows if b.date <= cut]
        history[symbol] = history_from_bars(symbol, rows)
    return Market(
        history=history,
        membership=Membership(tuple((s, D("2020-01-02"), None) for s in sorted(history))),
        fx=((D("2022-12-30"), Decimal("16000")),),
    )


START, END = SESSIONS[200], SESSIONS[-1]  # data_date SESSIONS[199] has exactly 200 bars


def run_nights(m: Market, start: date, end: date) -> tuple[RunResult, list[BracketNight]]:
    """The paper loop over ``[start, end]``, shaped as a ``RunResult`` for comparison."""
    usd_idr = m.usd_idr_on(start)
    cash0 = initial_cash_usd(INITIAL_IDR, usd_idr)
    pf = new_portfolio(cash0)
    data_date = dates.prev_session(start)
    snapshots = [Snapshot(data_date, pf.cash, pf.equity)]
    events: list[Event] = []
    rejections: Counter[str] = Counter()
    nights: list[BracketNight] = []
    for session in dates.sessions(start, end):
        sized = decide_bracket(
            pf, STRATEGY_A, STRATEGY_A_PARAMS, m.history, m.membership.members_on(data_date), data_date
        )
        for r in sized.rejected:
            rejections[r.reason] += 1
        pf = sized.portfolio
        night = settle_bracket(pf, session, m.bars_on(session, pf.held_symbols()), (), m.last_bar_date)
        nights.append(night)
        pf = night.portfolio
        events.extend(night.events)
        snapshots.append(night.snapshot)
        data_date = session
    result = RunResult(
        strategy_id=STRATEGY_A.id,
        params=STRATEGY_A_PARAMS,
        start=start,
        end=end,
        usd_idr=usd_idr,
        initial_cash=cash0,
        snapshots=tuple(snapshots),
        events=tuple(events),
        closed=tuple(e.order for e in events if e.kind == "exit"),
        open_at_end=pf.open_orders(),
        rejections=tuple(sorted(rejections.items())),
    )
    return result, nights


def _cut_while_held() -> date:
    """A session on whose close UPC is open in the uncut run (so cutting its bars there forces a
    close on the next session)."""
    full = run_backtest(market(), STRATEGY_A, STRATEGY_A_PARAMS, START, END)
    for e in full.events:
        o = e.order
        if e.kind == "fill" and o.symbol == "UPC":
            after = [x for x in full.events if x.kind == "exit" and x.order.symbol == "UPC" and x.order.fill_date == o.fill_date]
            if not after or after[0].order.exit_date > o.fill_date:
                return o.fill_date
    raise AssertionError("UPC never stays open past its fill session")


# --------------------------------------------------------------------------- equality with run_backtest


def test_window_has_at_least_300_sessions():
    assert len(dates.sessions(START, END)) >= 300


def test_nights_equal_run_backtest():
    m = market()
    expected = run_backtest(m, STRATEGY_A, STRATEGY_A_PARAMS, START, END)
    got, nights = run_nights(m, START, END)
    assert got.snapshots == expected.snapshots
    assert got.events == expected.events
    assert got.closed == expected.closed
    assert got.open_at_end == expected.open_at_end
    assert got.rejections == expected.rejections
    assert got == expected
    # Not vacuous: every exit reason, expiries and rejections happen in the window.
    assert {o.exit_reason for o in expected.closed} == {"tp", "sl", "gap", "time"}
    assert any(e.kind == "expire" for e in expected.events)
    assert dict(expected.rejections).get("lt_one_share", 0) > 0
    assert sum(len(n.closed) for n in nights) == len(expected.closed)
    assert all(n.snapshot == s for n, s in zip(nights, expected.snapshots[1:]))


def test_nights_equal_run_backtest_with_a_forced_close():
    cut = _cut_while_held()
    m = market(cut)
    expected = run_backtest(m, STRATEGY_A, STRATEGY_A_PARAMS, START, END)
    forced = [e for e in expected.events if e.forced]
    assert len(forced) == 1
    assert forced[0].order.symbol == "UPC"
    assert forced[0].session_date == dates.next_session(cut)
    got, nights = run_nights(m, START, END)
    assert got == expected
    night = next(n for n in nights if n.session == dates.next_session(cut))
    assert night.events[-1] == forced[0]
    assert night.snapshot == Snapshot(night.session, night.portfolio.cash, night.portfolio.equity)


# --------------------------------------------------------------------------- one settled night by hand

MON, TUE, WED = D("2025-03-10"), D("2025-03-11"), D("2025-03-12")


def test_split_on_a_pending_and_on_an_open_order():
    # Before WED: cash 1000; OPN open 3 sh filled MON at 100 (tp 110, sl 90), mark 102, days 2,
    # slot 1; PND pending for WED, 5 sh, limit 50 (tp 55, sl 45), slot 2. last_session TUE.
    opn = opened("OPN", MON, "100", "110", "90", shares=3, days_held=2, slot=1)
    pnd = pending("PND", WED, "50", "55", "45", shares=5, slot=2)
    pf = portfolio("1000", opn, pnd, marks={"OPN": "102"}, last_session=TUE)
    # Splits executing on WED (given out of order; applied by symbol):
    #   PND 2-for-1 (factor 2): 10 sh, limit 25, tp 27.5, sl 22.5.
    #   OPN 1-for-2 (factor 0.5): floor(3 × 1/2) = 1 sh, remainder 1/2 sh paid in lieu at the
    #     new mark 204: q(0.5 × 204) = 102 -> cash 1102. fill 200, tp 220, sl 180.
    # WED bars (post-split units): OPN o 205 h 210 l 200 c 206 -> no exit, days 3, mark 206.
    #   PND o 25.5 h 26 l 24.5 c 25: 24.5 < 25 fills at min(25.5, 25) = 25, cost q(250 × 1.001)
    #   = 250.25 -> cash 851.75; equity 851.75 + 1 × 206 + 10 × 25 = 1307.75.
    bars = {
        "OPN": bar("OPN", WED, "205", "210", "200", "206"),
        "PND": bar("PND", WED, "25.5", "26", "24.5", "25"),
    }
    night = settle_bracket(pf, WED, bars, [("PND", Decimal(2)), ("OPN", Decimal("0.5"))], lambda s: WED)
    kinds = [(e.kind, e.order.symbol) for e in night.events]
    assert kinds == [("split", "OPN"), ("split", "PND"), ("fill", "PND")]
    assert night.events[0].cash_usd == P("102")
    assert night.events[1].cash_usd is None
    o, p = night.portfolio.orders
    assert (o.symbol, o.shares, o.fill_price, o.tp_price, o.sl_price, o.days_held) == (
        "OPN", 1, P("200"), P("220"), P("180"), 3,
    )
    assert (p.symbol, p.status, p.shares, p.limit_price, p.fill_price) == ("PND", "open", 10, P("25"), P("25"))
    assert night.portfolio.marks == (("OPN", P("206")), ("PND", P("25")))
    assert night.snapshot == Snapshot(WED, P("851.75"), P("1307.75"))
    assert night.portfolio.last_session == WED
    assert night.closed == () and night.expired == ()


def test_split_on_a_symbol_not_held_changes_nothing():
    pnd = pending("PND", WED, "50", "55", "45", shares=5)
    pf = portfolio("1000", pnd, last_session=TUE)
    bars = {"PND": bar("PND", WED, "51", "52", "50.5", "51")}  # low 50.5 not < 50: expires
    plain = settle_bracket(pf, WED, bars, (), lambda s: WED)
    with_split = settle_bracket(pf, WED, bars, [("ZZZ", Decimal(4))], lambda s: WED)
    assert with_split == plain
    assert plain.expired == (plain.events[0].order,)
    assert plain.snapshot == Snapshot(WED, P("1000"), P("1000"))


def test_forced_close_of_a_symbol_without_bars():
    # GONE: open 10 sh filled TUE at 20 (tp 25, sl 15), mark 21, days 1. cash 500.
    # WED: no bar -> days 2, mark 21, step equity 500 + 210 = 710. last bar TUE < WED -> forced
    # close at 21: proceeds q(210 × 0.999) = 209.79, pnl 209.79 - q(200 × 1.001) = 9.59.
    # cash 709.79 = equity; the snapshot is replaced.
    gone = opened("GONE", TUE, "20", "25", "15", shares=10, days_held=1)
    pf = portfolio("500", gone, marks={"GONE": "21"}, last_session=TUE)
    night = settle_bracket(pf, WED, {}, (), lambda s: TUE)
    (e,) = night.events
    assert (e.kind, e.forced, e.session_date, e.cash_usd) == ("exit", True, WED, P("209.79"))
    assert (e.order.exit_reason, e.order.exit_price, e.order.days_held, e.order.pnl_usd) == ("time", P("21"), 2, P("9.59"))
    assert night.portfolio.orders == ()
    assert night.snapshot == Snapshot(WED, P("709.79"), P("709.79"))
    assert night.closed == (e.order,)


@pytest.mark.parametrize(
    ("last", "closed"),
    [(None, True), (TUE, True), (WED, False), (D("2025-03-20"), False)],
)
def test_force_close_rule_follows_last_bar_date(last, closed):
    # No bar on WED in every case; only a last bar before WED (or none) closes the position.
    gone = opened("GONE", TUE, "20", "25", "15", shares=10, days_held=1)
    pf = portfolio("500", gone, marks={"GONE": "21"}, last_session=TUE)
    night = settle_bracket(pf, WED, {}, (), lambda s: last)
    assert (night.portfolio.orders == ()) is closed
    assert night.snapshot.equity_usd == (P("709.79") if closed else P("710"))


def test_settle_rejects_bad_input():
    pf = portfolio("1000", last_session=TUE)
    with pytest.raises(ValueError, match="not an NYSE session"):
        settle_bracket(pf, D("2025-03-15"), {}, (), lambda s: None)
    with pytest.raises(ValueError, match="not after"):
        settle_bracket(pf, TUE, {}, (), lambda s: None)
    with pytest.raises(ValueError, match="two splits"):
        settle_bracket(pf, WED, {}, [("X", Decimal(2)), ("X", Decimal(3))], lambda s: None)
    with pytest.raises(TypeError, match="Decimal"):
        settle_bracket(pf, WED, {}, [("X", 2.0)], lambda s: None)
    with pytest.raises(TypeError, match="callable"):
        settle_bracket(pf, WED, {}, (), None)
    with pytest.raises(ValueError, match="pending order"):
        settle_bracket(portfolio("1000", pending("P", D("2025-03-13"), "5", "6", "4", 1), last_session=TUE),
                       WED, {}, (), lambda s: None)


# --------------------------------------------------------------------------- decide


def test_decide_cuts_history_at_data_date_no_look_ahead():
    """Changing every bar dated on or after S leaves the decision for S unchanged."""
    m = market()
    cash0 = initial_cash_usd(INITIAL_IDR, m.usd_idr_on(START))
    seen_picks = 0
    for data_date in SESSIONS[199::7]:
        s = dates.next_session(data_date)
        members = m.membership.members_on(data_date)
        pf = new_portfolio(cash0)
        before = decide_bracket(pf, STRATEGY_A, STRATEGY_A_PARAMS, m.history, members, data_date)
        mutated = {sym: mutate_from(h, s) for sym, h in m.history.items()}
        after = decide_bracket(pf, STRATEGY_A, STRATEGY_A_PARAMS, mutated, members, data_date)
        assert after == before
        assert all(o.session_date == s for o in before.placed)
        seen_picks += len(before.placed)
    assert seen_picks > 0  # not vacuous


def test_decide_sizes_for_the_next_session_and_checks_the_portfolio():
    m = market()
    data_date = SESSIONS[250]
    pf = new_portfolio(P("1250"))
    sized = decide_bracket(pf, STRATEGY_A, STRATEGY_A_PARAMS, m.history, m.membership.members_on(data_date), data_date)
    assert all(o.session_date == dates.next_session(data_date) for o in sized.portfolio.pending_orders())
    stepped = portfolio("1250", last_session=SESSIONS[249])
    with pytest.raises(ValueError, match="last settled session"):
        decide_bracket(stepped, STRATEGY_A, STRATEGY_A_PARAMS, m.history, frozenset(), data_date)
    with pytest.raises(ValueError, match="not an NYSE session"):
        decide_bracket(pf, STRATEGY_A, STRATEGY_A_PARAMS, m.history, frozenset(), D("2025-03-15"))
```
**Impact:** About 5-6 s of test time, single-threaded (two A runs over 424 sessions, plus the sampled no-look-ahead check).

### Step 4: `tests/test_paper_benchmark.py`
**File:** `engine/tests/test_paper_benchmark.py:1` (new)
**Change:** The tests:
- **Equality.** `start_benchmark` + `step_benchmark`, looped over 374 synthetic sessions with seven quarterly dividends (one on `START`, never credited), equal `buy_and_hold(..., dividends=...)`: snapshots, shares, cash, `dividends_usd` (as `income_usd`) and final equity. They also equal `buy_and_hold` on every 37th prefix, and the price-only curve when no dividends are given.
- **Persisted shape.** `Position` and `Fill` values are hand-checked on the week used by `tests/test_benchmark.py`.
- **Edge cases.** A start-day dividend is ignored. A reinvestment can open the holding (`entry`), which matches `buy_and_hold`. A state rebuilt from DB-shaped Decimals (`10.0000` shares and so on) equals the stepped one and steps identically.
- **Validation.** Bad states and bad steps raise.
- **Split rule.** Covered for a forward split, a reverse split with cash in lieu (also through `step_benchmark(split=...)`), a floor to zero, and no holding.

**Code:**
```python
"""SPY benchmark paper nights (plan phase 3, contract C3): ``start_benchmark`` + ``step_benchmark``
looped over a window equal ``buy_and_hold`` with dividends exactly; the persisted shape
(``Position``, ``Fill``); the split rule.

Arithmetic: ``buy_cost(p, n) = q(p × n × 1.001)``; whole shares ``floor(cash / (price × 1.001))``
(``backtest.benchmark._whole_shares``); dividend credit ``q(shares × amount)``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from simkit import D, P, bar

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend, buy_and_hold
from seer_engine.paper.benchmark import (
    SPY,
    BenchmarkState,
    split_benchmark,
    start_benchmark,
    step_benchmark,
)
from seer_engine.prices import Bar
from seer_engine.sim import Fill, Position, Snapshot

# --------------------------------------------------------------------------- synthetic SPY

SESSIONS = dates.sessions(D("2024-01-02"), D("2025-06-30"))
START, END = SESSIONS[0], SESSIONS[-1]
CASH0 = P("1250")


def _spy() -> dict[date, Bar]:
    """A wavy SPY around 100: +0.3 % a session with a -4 % session every 13, so idle cash plus a
    dividend sometimes buys a share and sometimes does not."""
    out: dict[date, Bar] = {}
    prev = 100.0
    for t, d in enumerate(SESSIONS):
        c = prev * 0.96 if t % 13 == 12 else prev * 1.003
        o = prev * (0.998 if t % 2 else 1.002)
        hi = max(o, c) * 1.004
        lo = min(o, c) * 0.996
        out[d] = bar(SPY, d, f"{o:.4f}", f"{hi:.4f}", f"{lo:.4f}", f"{c:.4f}", 50_000_000)
        prev = float(f"{c:.4f}")
    return out


SPY_BARS = _spy()
# Quarterly ex-dates on sessions, one of them on START itself (never credited), amounts large
# enough that the idle cash plus a dividend buys a share at some ex-date closes.
DIVIDENDS = tuple(
    Dividend(d, Decimal(a))
    for d, a in (
        (START, "1.5"),
        (D("2024-03-15"), "1.6"),
        (D("2024-06-21"), "1.75"),
        (D("2024-09-20"), "1.7"),
        (D("2024-12-20"), "1.9"),
        (D("2025-03-21"), "1.7"),
        (D("2025-06-20"), "1.75"),
    )
)
PAID = {d.ex_date: d.amount for d in DIVIDENDS}


def run_nights(spy: dict[date, Bar], start: date, end: date, cash0: Decimal, paid: dict[date, Decimal]):
    state = start_benchmark(cash0, start)
    snaps = [state.snapshot()]
    fills: list[Fill] = []
    states = [state]
    for d in dates.sessions(start, end):
        state, snap, night_fills = step_benchmark(state, d, spy[d], paid.get(d))
        snaps.append(snap)
        fills.extend(night_fills)
        states.append(state)
    return state, tuple(snaps), fills, states


# --------------------------------------------------------------------------- equality with buy_and_hold


def test_window_has_at_least_300_sessions_and_all_ex_dates_are_sessions():
    assert len(SESSIONS) >= 300
    assert all(dates.is_session(d.ex_date) for d in DIVIDENDS)


def test_nights_equal_buy_and_hold_total_return():
    curve = buy_and_hold(SPY_BARS, START, END, CASH0, dividends=DIVIDENDS, name="spy_tr")
    state, snaps, fills, _ = run_nights(SPY_BARS, START, END, CASH0, PAID)
    assert snaps == curve.snapshots
    assert state.shares == curve.shares
    assert state.cash == curve.cash
    assert state.income_usd == curve.dividends_usd
    assert state.equity == curve.snapshots[-1].equity_usd
    # Not vacuous: the start-day dividend is skipped, and reinvestment bought shares.
    assert curve.dividends_usd > 0
    assert [f.reason for f in fills][0] == "entry"
    assert any(f.reason == "add" for f in fills)


def test_every_prefix_equals_buy_and_hold_on_that_prefix():
    _, _, _, states = run_nights(SPY_BARS, START, END, CASH0, PAID)
    for i in range(1, len(states), 37):
        end = states[i].last_session
        curve = buy_and_hold(SPY_BARS, START, end, CASH0, dividends=DIVIDENDS, name="spy_tr")
        assert (states[i].shares, states[i].cash, states[i].equity) == (
            curve.shares, curve.cash, curve.snapshots[-1].equity_usd,
        )


def test_nights_equal_buy_and_hold_price_only():
    curve = buy_and_hold(SPY_BARS, START, END, CASH0, name="spy_price")
    state, snaps, fills, _ = run_nights(SPY_BARS, START, END, CASH0, {})
    assert snaps == curve.snapshots
    assert (state.shares, state.cash) == (curve.shares, curve.cash)
    assert len(fills) == 1


# --------------------------------------------------------------------------- persisted shape, by hand

WEEK = [  # (date, open, close), the week of tests/test_benchmark.py
    ("2026-03-02", "100", "101"),
    ("2026-03-03", "101", "102"),
    ("2026-03-04", "100", "98"),
    ("2026-03-05", "98", "99"),
    ("2026-03-06", "99", "100.5"),
]
WEEK_BARS = {
    D(d): bar(SPY, d, o, str(max(Decimal(o), Decimal(c)) + 1), str(min(Decimal(o), Decimal(c)) - 1), c)
    for d, o, c in WEEK
}
MON, TUE, WED, THU, FRI = (D(d) for d, _, _ in WEEK)


def test_start_state_is_day_zero_cash_only():
    s = start_benchmark(P("1000"), MON)
    assert s == BenchmarkState(start=MON, cash=P("1000"), equity=P("1000"), position=None, last_session=D("2026-02-27"))
    assert s.snapshot() == Snapshot(D("2026-02-27"), P("1000"), P("1000"))
    assert (s.shares, s.income_usd) == (0, P("0"))


def test_position_and_fills_by_hand():
    # MON open 100: floor(1000 / 100.1) = 9 sh, cost q(900.9) = 900.9000, fee q(0.9) = 0.9;
    #   cash 99.1, equity 99.1 + 9 × 101 = 1008.1.
    # WED dividend 2.5: cash + q(22.5) = 121.6; floor(121.6 / 98.098) = 1 sh at close 98,
    #   cost 98.0980 (fee 0.098 -> 0.0980): cash 23.502, 10 sh, equity 23.502 + 980 = 1003.502.
    s = start_benchmark(P("1000"), MON)
    s, snap, fills = step_benchmark(s, MON, WEEK_BARS[MON], None)
    assert snap == Snapshot(MON, P("99.1"), P("1008.1"))
    assert fills == (Fill(MON, SPY, "buy", Decimal(9), P("100"), P("-900.9"), P("0.9"), "entry"),)
    assert s.position == Position(SPY, Decimal(9), P("101"), MON, P("100"), 1, P("900.9"), P("0"), None, None)
    s, snap, fills = step_benchmark(s, TUE, WEEK_BARS[TUE], None)
    assert fills == () and s.position.days_held == 2 and s.position.mark == P("102")
    s, snap, fills = step_benchmark(s, WED, WEEK_BARS[WED], Decimal("2.5"))
    assert snap == Snapshot(WED, P("23.502"), P("1003.502"))
    assert fills == (Fill(WED, SPY, "buy", Decimal(1), P("98"), P("-98.098"), P("0.098"), "add"),)
    assert s.position == Position(SPY, Decimal(10), P("98"), MON, P("100"), 3, P("998.998"), P("22.5"), None, None)
    assert s.income_usd == P("22.5")


def test_dividend_on_start_is_not_credited():
    s = start_benchmark(P("1000"), MON)
    with_div, snap_a, _ = step_benchmark(s, MON, WEEK_BARS[MON], Decimal("2.5"))
    plain, snap_b, _ = step_benchmark(s, MON, WEEK_BARS[MON], None)
    assert (with_div, snap_a) == (plain, snap_b)


def test_reinvestment_can_open_the_holding():
    # 100 USD buys no share at MON's open (100.1 each). WED dividend credits q(0 × 2.5) = 0, but
    # the 100 idle buys floor(100 / 98.098) = 1 sh at the close 98: cost 98.098, cash 1.902.
    curve = buy_and_hold(WEEK_BARS, MON, FRI, P("100"), dividends=[Dividend(WED, Decimal("2.5"))], name="x")
    state, snaps, fills, _ = run_nights(WEEK_BARS, MON, FRI, P("100"), {WED: Decimal("2.5")})
    assert snaps == curve.snapshots
    assert (state.shares, state.cash) == (curve.shares, curve.cash) == (1, P("1.902"))
    assert [f.reason for f in fills] == ["entry"]
    assert state.position.entry_date == WED and state.position.days_held == 3


def test_state_round_trips_through_its_fields():
    # The store rebuilds the state from paper_state + one book_positions row + paper_start.
    s = start_benchmark(P("1000"), MON)
    for d in (MON, TUE, WED):
        s, _, _ = step_benchmark(s, d, WEEK_BARS[d], Decimal("2.5") if d == WED else None)
    p = s.position
    loaded = BenchmarkState(
        start=MON,
        cash=Decimal("23.5020"),
        equity=Decimal("1003.5020"),
        position=Position(p.symbol, Decimal("10.0000"), Decimal("98.0000"), p.entry_date, Decimal("100.0000"),
                          p.days_held, Decimal("998.9980"), Decimal("22.5000"), None, None),
        last_session=WED,
    )
    assert loaded == s
    a = step_benchmark(loaded, THU, WEEK_BARS[THU], None)
    b = step_benchmark(s, THU, WEEK_BARS[THU], None)
    assert a == b


def test_state_validation():
    with pytest.raises(ValueError, match="cash only"):
        BenchmarkState(start=MON, cash=P("1"), equity=P("2"), position=None, last_session=D("2026-02-27"))
    with pytest.raises(ValueError, match="whole shares"):
        BenchmarkState(start=MON, cash=P("1"), equity=P("2"),
                       position=Position(SPY, Decimal("1.5"), P("1"), MON, P("1"), 1, P("1"), P("0"), None, None),
                       last_session=MON)
    with pytest.raises(ValueError, match="holds SPY"):
        BenchmarkState(start=MON, cash=P("1"), equity=P("2"),
                       position=Position("QQQ", Decimal(1), P("1"), MON, P("1"), 1, P("1"), P("0"), None, None),
                       last_session=MON)
    with pytest.raises(ValueError, match="before"):
        BenchmarkState(start=MON, cash=P("1"), equity=P("1"), position=None, last_session=D("2026-02-26"))
    with pytest.raises(ValueError, match="> 0"):
        start_benchmark(P("0"), MON)
    with pytest.raises(TypeError):
        start_benchmark(1000.0, MON)
    with pytest.raises(ValueError, match="not an NYSE session"):
        start_benchmark(P("1000"), D("2026-03-07"))


def test_step_validation():
    s = start_benchmark(P("1000"), MON)
    with pytest.raises(ValueError, match="every session"):
        step_benchmark(s, TUE, WEEK_BARS[TUE], None)
    with pytest.raises(ValueError, match="dated"):
        step_benchmark(s, MON, WEEK_BARS[TUE], None)
    with pytest.raises(ValueError, match="SPY bar"):
        step_benchmark(s, MON, bar("QQQ", MON, "1", "2", "0.5", "1"), None)
    with pytest.raises(ValueError, match="> 0"):
        step_benchmark(s, MON, WEEK_BARS[MON], Decimal("0"))
    with pytest.raises(TypeError):
        step_benchmark(s, MON, WEEK_BARS[MON], 2.5)


# --------------------------------------------------------------------------- splits


def _held_after_tue(cash: str = "1000") -> BenchmarkState:
    s = start_benchmark(P(cash), MON)
    s, _, _ = step_benchmark(s, MON, WEEK_BARS[MON], None)
    s, _, _ = step_benchmark(s, TUE, WEEK_BARS[TUE], None)
    return s


def test_forward_split_rescales_exactly():
    # 9 sh, mark 102, entry 100 -> 2-for-1: 18 sh, mark 51, entry 50, no cash in lieu.
    s = _held_after_tue()
    out, in_lieu = split_benchmark(s, Decimal(2), WED)
    assert in_lieu == P("0")
    assert (out.shares, out.position.mark, out.position.entry_price, out.cash) == (18, P("51"), P("50"), s.cash)
    assert (out.equity, out.last_session) == (s.equity, s.last_session)


def test_reverse_split_pays_the_fraction_in_lieu():
    # 9 sh, 1-for-2 (factor 0.5): floor(4.5) = 4 sh, mark 204; 0.5 sh in lieu q(0.5 × 204) = 102
    # -> cash 99.1 + 102 = 201.1, income 102. Then WED (bar in post-split units, close 196):
    # equity 201.1 + 4 × 196 = 985.1.
    s = _held_after_tue()
    out, in_lieu = split_benchmark(s, Decimal("0.5"), WED)
    assert in_lieu == P("102")
    assert (out.shares, out.position.mark, out.position.entry_price, out.cash, out.income_usd) == (
        4, P("204"), P("200"), P("201.1"), P("102"),
    )
    wed = bar(SPY, WED, "200", "205", "195", "196")
    stepped, snap, fills = step_benchmark(s, WED, wed, None, split=Decimal("0.5"))
    assert fills == ()
    assert snap == Snapshot(WED, P("201.1"), P("985.1"))
    assert stepped.position.mark == P("196") and stepped.position.days_held == 3


def test_split_that_floors_to_zero_pays_everything_in_lieu():
    # 1500 buys floor(1500 / 100.1) = 14 sh at MON's open; 1-for-20: floor(0.7) = 0 sh, all 0.7 sh
    # in lieu at the new mark 102 × 20 = 2040: q(0.7 × 2040) = 1428.
    s = _held_after_tue("1500")
    assert s.shares == 14
    out, in_lieu = split_benchmark(s, Decimal("0.05"), WED)
    assert in_lieu == P("1428")
    assert out.position is None and out.cash == s.cash + P("1428")


def test_split_without_a_holding_and_bad_splits():
    s = start_benchmark(P("1000"), MON)
    assert split_benchmark(s, Decimal(2), MON) == (s, P("0"))
    held = _held_after_tue()
    with pytest.raises(ValueError, match="after the last stepped session"):
        split_benchmark(held, Decimal(2), TUE)
    with pytest.raises(ValueError, match="not a split"):
        split_benchmark(held, Decimal(1), WED)
    with pytest.raises(TypeError):
        split_benchmark(held, 2.0, WED)
```
**Impact:** Under 1 s.

## Verification

**Build:** `engine/.venv/bin/python -c "import seer_engine.paper.bracket, seer_engine.paper.benchmark"`
**Tests:**
- `engine/.venv/bin/pytest engine/tests/test_paper_bracket.py engine/tests/test_paper_benchmark.py -q` (28 tests)
- then the whole suite: `docker start seer-pg; PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`, with 0 skipped. Phase 1's purity test must pick up both new files.
- then `cd web && npx vitest run` (untouched, invariant 1).

**Manual check:** none.

**Exit criteria:**
- Both equality tests pass:
  - bracket nights equal `run_backtest` over at least 300 sessions, including a forced close;
  - benchmark nights equal `buy_and_hold` with dividends over at least 300 sessions.
- The hand-checked split and forced-close tests pass.
- The no-look-ahead test passes.
- Phase 1's purity test covers `paper/bracket.py` and `paper/benchmark.py` and passes.

**Pre-verified:** both modules and both test files were run on the worktree's venv against `HEAD` 844e4d7, through a stand-in package in the planner's scratchpad (imports rewritten from `seer_engine.paper.` to the stand-in). Result: 28 passed, pyflakes clean.

## Handoffs

- **Phase 6 (store)**, persisting `BracketNight`:
  - Upsert every live order in `night.portfolio.orders`, with `orders.mark` from `night.portfolio.marks` for open ones.
  - Write every terminal order from `night.events` (`exit` and `expire`, split floor-to-zero cases included).
  - Write `night.snapshot` to `equity_snapshots`, and `cash`/`equity`/`last_session` to `paper_state`.
- **Phase 6, loading a `Portfolio`:** use `orders` rows with status pending or open, marks from `orders.mark` (never from `bars`; plan Decisions), and cash/equity/last_session from `paper_state`. Before the first session, `last_session` may be `None` or `prev_session(paper_start)`. `decide_bracket` and `settle_bracket` accept both, and the runner equality does not depend on which.
- **Phase 6, persisting `BenchmarkState`:**
  - `paper_state` gets last_session, cash and equity. Reconciled: phase 7 then sets SPY's `pending_session = next_session(last_session)` with `pending_decision` false (`store.write_pending`), the same convention as every engine; nothing here reads it.
  - One `book_positions` row comes from `state.position`; delete the row when it is `None`.
  - `book_fills` come from the returned fills.
  - The SPY snapshot goes to `equity_snapshots`.
  - To rebuild the state, call `BenchmarkState(start=paper_start, ...)`; its `__post_init__` validates.
- **Phase 7 (command)**, order per night for session S:
  - bracket: `settle_bracket(pf, S, bars on S for pf.held_symbols(), applied splits on S, last_bar_date)` then `decide_bracket(pf, STRATEGY_A, STRATEGY_A_PARAMS, history, members_on(S), S)`;
  - SPY: `step_benchmark(state, S, spy_bar(S), spy_dividend(S), split=applied SPY factor on S or None)`.
- **Phase 7, the init night:**
  - bracket: `decide_bracket(new_portfolio(cash0), ..., data_date=prev_session(paper_start))`;
  - SPY: `start_benchmark(cash0, paper_start)` and its `snapshot()` as the day-0 row.
- **Phase 7, splits and the last bar date:** only `split_adjustments.applied = true` rows are passed as splits. `last_bar_date` is the latest stored bar date for the symbol, read after this night's bars were written.
- **Phase 7, SPY bars:** the benchmark raises when SPY has no bar on a session, as `buy_and_hold` does. That fails the night, which is design §8's visible failure.
- **Phase 8 (replay):** a SPY split inside the window makes the SPY benchmark "split-affected", like a bracket strategy with a split on a held or pending symbol. `buy_and_hold` over adjusted bars will not equal the stepped state across one.
- **Phase 13 (docs):** describe `paper/bracket.py` and `paper/benchmark.py` in `engine/package_readme.md`, including the SPY split rule above.

## Rollback

Delete the four new files (`git revert` of the phase commit). Nothing else references them until phases 6 and 7 land.
