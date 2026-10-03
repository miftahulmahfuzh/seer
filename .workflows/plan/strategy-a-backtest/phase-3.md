# Phase 3: Point-in-time market + backtest runner + survivorship

**Plan set:** `STRATEGY_A_BACKTEST_PLAN.md`
**Analysis:** `20261003-144506-Q8N4_code_analyzer.md`
**Satisfies:** R2 — the backtest runner over the point-in-time universe, every NYSE session, `size_picks` → `step` → `close_unpriced`, delisting handled
**Depends on:** Phase 1
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/backtest/`

---

## Goal

After this phase the engine can run any `Strategy` over a window of NYSE sessions entirely in
memory: `Market` holds float64 `History` per symbol, the point-in-time `Membership` (both indices
unioned, `[start, end)`), and USD/IDR; `run_backtest` drives the simulator exactly as the readme's
"Simulator: P3 backtest loop" prescribes, force-closing a held symbol only when its bars have ended
for good; and `survivorship` counts the (member, session) pairs the backtest cannot see, per year.
Everything is pure, deterministic and covered by a hand-checked synthetic scenario.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `seer_engine.backtest.market` (`engine/src/seer_engine/backtest/market.py`, new, pure):
  - `SPY = "SPY"` — module constant (the benchmark symbol; `universe.BENCHMARK` cannot be imported because `universe.py` imports `psycopg`).
  - `@dataclass(frozen=True) class Membership` — field `intervals: tuple[tuple[str, date, date | None], ...]` (exactly the contract); private `_breaks`, `_segments` (`init=False, compare=False, repr=False`).
    - `members_on(self, d: date) -> frozenset[str]` — one `bisect`; 2,955 sessions over 1,544 intervals in milliseconds.
    - `symbols(self) -> tuple[str, ...]` — **addition to the shared contract**: every ever-member, sorted. A listing helper only: the report's never-fetched count is defined once, window-restricted, in phase 5's `commands/backtest.never_fetched_members` (index Decisions "Never-fetched count").
    - Raises `TypeError` (intervals not a tuple, a non-date bound) / `ValueError` (empty symbol, `end <= start`).
  - `@dataclass(frozen=True, eq=False) class Market` — fields `history: Mapping[str, History]`, `membership: Membership`, `fx: tuple[tuple[date, Decimal], ...]` (exactly the contract); private `_fx_dates`, `_last` (`init=False`).
    - `bar(self, symbol: str, d: date) -> Bar | None` — `Bar` via `prices.to_decimal(float(x))`, `volume=int(x)`.
    - `bars_on(self, d: date, symbols: Iterable[str]) -> dict[str, Bar]` — only symbols with a bar on `d`.
    - `last_bar_date(self, symbol: str) -> date | None` — precomputed at construction.
    - `usd_idr_on(self, d: date) -> Decimal` — latest row dated `<= d`; `ValueError` when none.
    - `spy(self) -> dict[date, Bar]` — every SPY bar ascending; `{}` when the market has no SPY history.
    - Construction raises `TypeError`/`ValueError` when a history key differs from `History.symbol`, a value is not a `History`, or `fx` is not strictly ascending positive `Decimal`s.
- `seer_engine.backtest.runner` (`engine/src/seer_engine/backtest/runner.py`, new, pure):
  - `INITIAL_IDR = Decimal("20000000")`.
  - `@dataclass(frozen=True) class RunResult` — fields exactly as the shared contract: `strategy_id, params, start, end, usd_idr, initial_cash, snapshots, events, closed, open_at_end, rejections`.
  - `run_backtest(market: Market, strategy: Strategy, params: Any, start: date, end: date, *, prepared: Any = None, initial_idr: Decimal = INITIAL_IDR) -> RunResult` — **`start` and `end` must be NYSE sessions with `start <= end`** (`ValueError` otherwise); `RunResult.start/end` are the arguments.
  - `@dataclass(frozen=True) class YearGap` — `year, member_sessions, missing, missing_never_fetched, missing_other` (exactly the contract; `missing = never + other`).
  - `survivorship(market: Market, start: date, end: date) -> tuple[YearGap, ...]` — membership taken on the session itself; years ascending; years without a session omitted; `()` for a window with no session.
- Tests: `engine/tests/test_backtest_market.py`, `engine/tests/test_backtest_runner.py` (new).

**Signature changes:** none.
**Requires (from earlier phases):**
- Phase 1: `seer_engine.strategies.base.History` with fields `symbol, dates (datetime64[D]), open, high, low, close, volume (float64)`, constructible by keyword; `History.__len__`, `upto(d: date)`, `last_date() -> date | None` (a `datetime.date`, not `np.datetime64`), `index_of(d: date) -> int | None` accepting a `datetime.date`; `history_from_bars(symbol, bars)`; the `Strategy` protocol (`id`, `lookback`, `picks`, `prepare`, `picks_prepared`) and its equality contract.
- Phase 1: `seer_engine.strategies.a.STRATEGY_A` and `DESIGN_PARAMS` (smoke test only).
- Phase 1: `engine/src/seer_engine/backtest/__init__.py` exists (docstring only) so `seer_engine.backtest` is a package.
- Phase 1: `engine/tests/test_strategy_purity.py` globs `backtest/*.py` minus `io.py`; `market.py` and `runner.py` are written to pass it (imports: stdlib `bisect/collections/dataclasses/datetime/decimal/typing`, `numpy`, `seer_engine.{dates,prices,sim,strategies.base,backtest.market}` only; no forbidden attribute or call).
- Phase 1: `numpy` declared in `engine/pyproject.toml`.

**Leaves alone (owned by others):** `strategies/*`, `engine/tests/stratkit.py`, `backtest/__init__.py`, `engine/pyproject.toml`, `test_strategy_purity.py` (phase 1); `backtest/benchmark.py`, `engine/data/*`, `test_benchmark.py` (phase 2); `backtest/{metrics,tuning,report}.py` (phase 4); `backtest/io.py`, `commands/backtest.py`, `.gitignore` (phase 5); `engine/package_readme.md`, `docs/ROADMAP.md` (phase 6); `seer_engine/sim/*`, `dates.py`, `prices.py`, `universe.py`, `membership.py` (nobody).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/market.py` | create (line 1) | `SPY`, `Membership`, `Market` |
| `engine/src/seer_engine/backtest/runner.py` | create (line 1) | `INITIAL_IDR`, `RunResult`, `run_backtest`, `YearGap`, `survivorship` |
| `engine/tests/test_backtest_market.py` | create (line 1) | membership boundaries, union, speed + brute-force parity; exact Decimal bars; FX lookup; SPY |
| `engine/tests/test_backtest_runner.py` | create (line 1) | hand-checked 9-session scenario (fake strategy), forced close once, halt not closed, members on `data_date`, no look-ahead, `prepared` parity, determinism, bad windows, survivorship per year, `STRATEGY_A` smoke |

## Implementation Steps

### Step 0: Worktree venv
**File:** `engine/.venv` (not committed)
**Change:** The worktree has no venv of its own at planning time, and `/home/miftah/seer/engine/.venv`
is an editable install of the main checkout (it would test the wrong tree). From the worktree root:
**Code:**
```bash
cd /home/miftah/.worktrees/seer/strategy-a-backtest
test -x engine/.venv/bin/python || python3 -m venv engine/.venv
engine/.venv/bin/pip install -e 'engine[dev]'   # re-run even if the venv exists: phase 1 declared numpy
engine/.venv/bin/python -c "import seer_engine, numpy; print(seer_engine.__file__, numpy.__version__)"
# must print a path under /home/miftah/.worktrees/seer/strategy-a-backtest/engine/src
docker start seer-pg
```
**Impact:** none on the tree.

### Step 1: `market.py` — point-in-time membership and the in-memory market
**File:** `engine/src/seer_engine/backtest/market.py:1` (new)
**Change:** New pure module. Design notes:
- `Membership.__post_init__` sweeps every interval boundary once (`+1` at `start`, `-1` at `end`,
  per symbol, so a symbol in both indices or in overlapping intervals is counted, not duplicated)
  and stores, for each distinct boundary date, the frozenset of members from that date up to the
  next boundary. `members_on(d)` is `bisect_right(_breaks, d) - 1` → that segment. With 1,544
  intervals there are at most ~3,000 boundaries; building is a few ms and a lookup is O(log n).
- `Market.bar` converts with `to_decimal(float(h.open[i]))`. **The `float(...)` is load-bearing:**
  `h.open[i]` is an `np.float64`, which *is* a `float` subclass, so `to_decimal` takes its float
  branch and calls `repr(x)` — and in numpy 2 `repr(np.float64(1.5))` is `'np.float64(1.5)'`,
  which `Decimal` rejects. `float()` gives a plain float whose shortest repr is the stored
  `numeric(12,4)` value, so the Decimal is exact. `spy()` uses `.tolist()`, which yields plain
  floats and `datetime.date`s.
- `last_bar_date` is precomputed for every symbol at construction (the runner calls it for every
  open position every session).
- `fx` is validated strictly ascending, so `usd_idr_on` is one bisect.
**Code:**
```python
"""The backtest's in-memory, point-in-time market: membership, bars and FX (P3, handover §3/§4).

Pure. Built once per process (``backtest.io.load_market`` in phase 5, or by a test), then read
by the runner, the benchmark and the survivorship count. Nothing here touches a database, a
file, the network or a clock.

- ``Membership`` answers "who was in the S&P 500 ∪ Nasdaq-100 on day d" from the ``universe``
  intervals (``[start, end)``, end exclusive, ``None`` = still a member) without a query per
  day: the intervals are swept once into constant segments, and a lookup is one bisect.
- ``Market`` holds every symbol's float64 ``History`` (SPY included) and builds a Decimal
  ``prices.Bar`` on demand, only for the few symbols the simulator needs on a session. Prices
  go through ``prices.to_decimal(float(x))``: ``bars`` columns are ``numeric(12,4)``, so the
  float's shortest repr is the stored value and the Decimal is exact.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from seer_engine.prices import Bar, to_decimal
from seer_engine.strategies.base import History

SPY = "SPY"


def _check_date(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    return d


@dataclass(frozen=True)
class Membership:
    """Point-in-time index membership, both indices unioned.

    ``intervals`` holds ``(symbol, start, end)`` with ``start`` inclusive and ``end``
    exclusive (``None`` = still a member); one row per ``universe`` row, so a symbol in both
    indices may appear twice and overlapping intervals are fine.
    """

    intervals: tuple[tuple[str, date, date | None], ...]
    _breaks: tuple[date, ...] = field(init=False, repr=False, compare=False)
    _segments: tuple[frozenset[str], ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.intervals, tuple):
            raise TypeError("intervals must be a tuple")
        delta: dict[date, dict[str, int]] = {}
        for item in self.intervals:
            if not (isinstance(item, tuple) and len(item) == 3):
                raise TypeError(f"an interval is (symbol, start, end), got {item!r}")
            symbol, start, end = item
            if not isinstance(symbol, str) or not symbol:
                raise ValueError(f"symbol must be a non-empty str, got {symbol!r}")
            _check_date("start", start)
            if end is not None:
                _check_date("end", end)
                if end <= start:
                    raise ValueError(f"{symbol}: end {end} must be after start {start}")
            delta.setdefault(start, {}).setdefault(symbol, 0)
            delta[start][symbol] += 1
            if end is not None:
                delta.setdefault(end, {}).setdefault(symbol, 0)
                delta[end][symbol] -= 1
        breaks = sorted(delta)
        active: dict[str, int] = {}
        segments: list[frozenset[str]] = []
        for b in breaks:
            for symbol, change in delta[b].items():
                count = active.get(symbol, 0) + change
                if count:
                    active[symbol] = count
                else:
                    active.pop(symbol, None)
            segments.append(frozenset(active))
        object.__setattr__(self, "_breaks", tuple(breaks))
        object.__setattr__(self, "_segments", tuple(segments))

    def members_on(self, d: date) -> frozenset[str]:
        """Symbols that were a member of either index on ``d`` (one bisect)."""
        i = bisect_right(self._breaks, _check_date("d", d)) - 1
        return self._segments[i] if i >= 0 else frozenset()

    def symbols(self) -> tuple[str, ...]:
        """Every symbol that was ever a member, sorted."""
        return tuple(sorted({s for s, _, _ in self.intervals}))


@dataclass(frozen=True, eq=False)
class Market:
    """Everything a backtest reads, in memory.

    ``history``: every symbol with bars (SPY included), keyed by symbol, each ``History``
    ascending. ``fx``: ``(date, usd_idr)`` rows, strictly ascending, ``usd_idr`` a Decimal > 0
    (publishing days only, so not every session has a row).
    """

    history: Mapping[str, History]
    membership: Membership
    fx: tuple[tuple[date, Decimal], ...]
    _fx_dates: tuple[date, ...] = field(init=False, repr=False)
    _last: Mapping[str, date] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.history, Mapping):
            raise TypeError(f"history must be a Mapping, got {type(self.history).__name__}")
        if not isinstance(self.membership, Membership):
            raise TypeError(f"membership must be a Membership, got {type(self.membership).__name__}")
        if not isinstance(self.fx, tuple):
            raise TypeError("fx must be a tuple of (date, Decimal) rows")
        last: dict[str, date] = {}
        for symbol, h in self.history.items():
            if not isinstance(h, History):
                raise TypeError(f"history[{symbol!r}] must be a History, got {type(h).__name__}")
            if h.symbol != symbol:
                raise ValueError(f"history[{symbol!r}] holds bars for {h.symbol!r}")
            d = h.last_date()
            if d is not None:
                last[symbol] = d
        prev: date | None = None
        for row in self.fx:
            if not (isinstance(row, tuple) and len(row) == 2):
                raise TypeError(f"an fx row is (date, Decimal), got {row!r}")
            d, rate = row
            _check_date("fx date", d)
            if not isinstance(rate, Decimal):
                raise TypeError(f"usd_idr on {d} must be a Decimal, got {type(rate).__name__}")
            if not rate.is_finite() or rate <= 0:
                raise ValueError(f"usd_idr on {d} must be > 0, got {rate}")
            if prev is not None and d <= prev:
                raise ValueError(f"fx rows must be strictly ascending: {d} after {prev}")
            prev = d
        object.__setattr__(self, "_fx_dates", tuple(d for d, _ in self.fx))
        object.__setattr__(self, "_last", last)

    def bar(self, symbol: str, d: date) -> Bar | None:
        """``symbol``'s bar dated ``d`` as a Decimal ``Bar`` (exact 4 dp), or None."""
        h = self.history.get(symbol)
        if h is None:
            return None
        i = h.index_of(_check_date("d", d))
        if i is None:
            return None
        return Bar(
            symbol=symbol,
            date=d,
            open=to_decimal(float(h.open[i])),
            high=to_decimal(float(h.high[i])),
            low=to_decimal(float(h.low[i])),
            close=to_decimal(float(h.close[i])),
            volume=int(h.volume[i]),
        )

    def bars_on(self, d: date, symbols: Iterable[str]) -> dict[str, Bar]:
        """``{symbol: Bar}`` for each of ``symbols`` that has a bar on ``d`` (as ``sim.step`` takes them)."""
        out: dict[str, Bar] = {}
        for symbol in symbols:
            b = self.bar(symbol, d)
            if b is not None:
                out[symbol] = b
        return out

    def last_bar_date(self, symbol: str) -> date | None:
        """The date of ``symbol``'s last bar in the loaded data, or None when it has none."""
        return self._last.get(symbol)

    def usd_idr_on(self, d: date) -> Decimal:
        """USD/IDR from the latest fx row dated on or before ``d``; ValueError when there is none."""
        i = bisect_right(self._fx_dates, _check_date("d", d)) - 1
        if i < 0:
            raise ValueError(f"no usd_idr rate on or before {d}")
        return self.fx[i][1]

    def spy(self) -> dict[date, Bar]:
        """Every SPY bar as a Decimal ``Bar``, keyed by date ascending ({} when SPY has no bars)."""
        h = self.history.get(SPY)
        if h is None:
            return {}
        out: dict[date, Bar] = {}
        for d, o, hi, lo, c, v in zip(
            h.dates.tolist(), h.open.tolist(), h.high.tolist(), h.low.tolist(),
            h.close.tolist(), h.volume.tolist(),
        ):
            out[d] = Bar(SPY, d, to_decimal(o), to_decimal(hi), to_decimal(lo), to_decimal(c), int(v))
        return out
```
**Impact:** new module only. Phase 1's purity test picks it up through its glob.

### Step 2: `runner.py` — the session loop and the survivorship count
**File:** `engine/src/seer_engine/backtest/runner.py:1` (new)
**Change:** New pure module. It is the readme's "Simulator: P3 backtest loop" (`engine/package_readme.md:395-420`) with the strategy and the data source filled in:
- `data_date` starts at `prev_session(start)` and then trails the loop variable, so
  `prev_session` is called once per run, not once per session.
- Members are taken on `data_date` (handover §3 "Signal timing"), never on the session.
- Without `prepared`, every history is cut with `History.upto(data_date)` before
  `strategy.picks` sees it (so no strategy can look ahead through the runner). With `prepared`,
  `strategy.picks_prepared(prepared, members, data_date, params)` is called; the phase 1 contract
  makes the two paths equal, and a test here checks the runner wires both.
- `bars_on(session, pf.held_symbols())` — every live symbol (pending and open), as `step` needs.
- Gone = an **open** position whose `last_bar_date` is `None` or `< session`, checked after the
  step (plan Decisions "Gone vs halted"). A pending order on a symbol with no bar simply expires
  in `step`, so only open positions need it. `close_unpriced` exits at the mark with
  `exit_date = session`, and the session's snapshot is replaced. A symbol with a later bar (a
  halt) is never force-closed; the simulator's missing-bar rule handles it.
- After `end`, open positions stay open (`open_at_end`) and are marked at `end`'s close — never
  liquidated (plan Decisions "End of window"). No picks are sized for a session after `end`, so
  no pending order is left.
- `closed` is the exit events' orders in event order (`apply_split` is never called, so no
  `split` events exist).
- `survivorship` is vectorized per ever-member symbol (≤ 795): a session mask from its
  intervals, a "has a bar" mask from `np.searchsorted` on its dates, then `np.bincount` per
  year. Measured on a 663-symbol × 2,955-session synthetic market: 0.04 s.

Measured with the scratch copy of this module on 663 symbols × 2,955 bars and a fake prepared
strategy placing 6 picks a session: one in-sample run (2015-10-19 → 2021-12-31, 1,564 sessions)
costs **0.27 s** of runner + simulator time, so the 81-run grid spends ~22 s outside the
strategy. The un-prepared path adds one `upto` per symbol per session (~1 M slices for 663
symbols); it is for P4-shaped checks and tests, not the grid.
**Code:**
```python
"""The backtest session loop around the simulator, and the survivorship count (P3, handover §2.2).

Pure. ``run_backtest`` is the readme's "Simulator: P3 backtest loop", verbatim in shape: for
every NYSE session S in ``[start, end]``

1. the strategy picks from the point-in-time universe on ``data_date = prev_session(S)``
   with history through ``data_date`` only;
2. ``sim.size_picks(pf, picks, S)``;
3. ``sim.step(pf, S, bars on S for every live symbol)``;
4. every open position whose symbol has no bar on S or later in the loaded data is gone:
   ``sim.close_unpriced`` right after S's step, and S's snapshot is replaced by the
   post-close one. A halt (bars resume later) is left to the simulator's missing-bar rule.

Sizing, fills, exits and costs all happen inside ``seer_engine.sim``; nothing here does money
arithmetic. Positions still open after ``end`` are marked at the close, never liquidated.

``survivorship`` counts the (member, session) pairs that have no bar, per calendar year, split
into members never fetched at all and members missing a bar on that session.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine import dates
from seer_engine.backtest.market import Market
from seer_engine.sim import (
    Event,
    Order,
    Snapshot,
    close_unpriced,
    initial_cash_usd,
    new_portfolio,
    size_picks,
    step,
)
from seer_engine.strategies.base import Strategy

INITIAL_IDR = Decimal("20000000")


@dataclass(frozen=True)
class RunResult:
    """One backtest run.

    ``snapshots[0]`` is ``Snapshot(prev_session(start), cash0, cash0)``, then one per session
    (after any forced close). ``events`` is every simulator event in order, forced closes
    included. ``closed`` is every closed order in exit order; ``open_at_end`` the positions
    still open after ``end``. ``rejections`` counts ``size_picks`` rejections by reason,
    sorted by reason.
    """

    strategy_id: str
    params: Any
    start: date
    end: date
    usd_idr: Decimal
    initial_cash: Decimal
    snapshots: tuple[Snapshot, ...]
    events: tuple[Event, ...]
    closed: tuple[Order, ...]
    open_at_end: tuple[Order, ...]
    rejections: tuple[tuple[str, int], ...]


def _session(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    if not dates.is_session(d):
        raise ValueError(f"{name} {d} is not an NYSE session")
    return d


def run_backtest(
    market: Market,
    strategy: Strategy,
    params: Any,
    start: date,
    end: date,
    *,
    prepared: Any = None,
    initial_idr: Decimal = INITIAL_IDR,
) -> RunResult:
    """Run ``strategy`` with ``params`` on a fresh portfolio over every session in ``[start, end]``.

    ``start`` and ``end`` must be NYSE sessions, ``start <= end``. Starting cash is
    ``initial_cash_usd(initial_idr, market.usd_idr_on(start))``. With ``prepared`` (the value of
    ``strategy.prepare(market.history)``), picks come from ``strategy.picks_prepared``;
    without it, from ``strategy.picks`` on every history cut at ``data_date``. The strategy
    contract makes both give the same result.
    """
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    _session("start", start)
    _session("end", end)
    if end < start:
        raise ValueError(f"end {end} is before start {start}")
    usd_idr = market.usd_idr_on(start)
    cash0 = initial_cash_usd(initial_idr, usd_idr)

    pf = new_portfolio(cash0)
    data_date = dates.prev_session(start)
    snapshots: list[Snapshot] = [Snapshot(data_date, pf.cash, pf.equity)]
    events: list[Event] = []
    rejections: Counter[str] = Counter()

    for session in dates.sessions(start, end):
        members = market.membership.members_on(data_date)
        if prepared is None:
            history = {s: h.upto(data_date) for s, h in market.history.items()}
            picks = strategy.picks(history, members, data_date, params)
        else:
            picks = strategy.picks_prepared(prepared, members, data_date, params)

        sized = size_picks(pf, picks, session)
        for r in sized.rejected:
            rejections[r.reason] += 1
        pf = sized.portfolio

        result = step(pf, session, market.bars_on(session, pf.held_symbols()))
        pf = result.portfolio
        events.extend(result.events)
        snapshots.append(result.snapshot)

        gone = []
        for o in pf.open_orders():
            last = market.last_bar_date(o.symbol)
            if last is None or last < session:
                gone.append(o.symbol)
        if gone:
            pf, forced = close_unpriced(pf, gone)
            events.extend(forced)
            snapshots[-1] = Snapshot(session, pf.cash, pf.equity)

        data_date = session

    return RunResult(
        strategy_id=strategy.id,
        params=params,
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


@dataclass(frozen=True)
class YearGap:
    """Survivorship gap in one calendar year: (member, session) pairs and those with no bar.

    ``missing = missing_never_fetched + missing_other``. ``missing_never_fetched`` counts pairs
    whose symbol has no bars at all in the loaded data (delisted or acquired before the
    backfill could fetch it); ``missing_other`` counts pairs whose symbol has bars, just not on
    that session.
    """

    year: int
    member_sessions: int
    missing: int
    missing_never_fetched: int
    missing_other: int


def survivorship(market: Market, start: date, end: date) -> tuple[YearGap, ...]:
    """Per calendar year, ascending: how many (member on S, session S) pairs in ``[start, end]``
    have no bar on S. Membership is taken on the session itself. Years without a session are
    left out."""
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    sess = dates.sessions(start, end)
    if not sess:
        return ()
    sess64 = np.array(sess, dtype="datetime64[D]")
    year_list = sorted({d.year for d in sess})
    year_idx = np.array([year_list.index(d.year) for d in sess], dtype=np.int64)
    n_years = len(year_list)
    member = np.zeros(n_years, dtype=np.int64)
    never = np.zeros(n_years, dtype=np.int64)
    other = np.zeros(n_years, dtype=np.int64)

    by_symbol: dict[str, list[tuple[date, date | None]]] = {}
    for symbol, a, b in market.membership.intervals:
        by_symbol.setdefault(symbol, []).append((a, b))

    for symbol in sorted(by_symbol):
        mask = np.zeros(len(sess), dtype=bool)
        for a, b in by_symbol[symbol]:
            inside = sess64 >= np.datetime64(a, "D")
            if b is not None:
                inside &= sess64 < np.datetime64(b, "D")
            mask |= inside
        if not mask.any():
            continue
        member += np.bincount(year_idx[mask], minlength=n_years)
        h = market.history.get(symbol)
        if h is None or len(h) == 0:
            never += np.bincount(year_idx[mask], minlength=n_years)
            continue
        pos = np.searchsorted(h.dates, sess64)
        has = (pos < len(h)) & (h.dates[np.minimum(pos, len(h) - 1)] == sess64)
        other += np.bincount(year_idx[mask & ~has], minlength=n_years)

    return tuple(
        YearGap(
            year=y,
            member_sessions=int(member[i]),
            missing=int(never[i] + other[i]),
            missing_never_fetched=int(never[i]),
            missing_other=int(other[i]),
        )
        for i, y in enumerate(year_list)
    )
```
**Impact:** new module only.

### Step 3: Market tests
**File:** `engine/tests/test_backtest_market.py:1` (new)
**Change:** Membership boundaries (`[start, end)`, open-ended, union of both indices with an
overlap and a leave/rejoin gap), validation, a 1,544-interval × 2,955-session speed bound (< 2 s;
measured in ms) with brute-force parity every 97th session; exact 4-dp Decimals from float64
(including `99999999.9999`, `0.0001`, a 10-digit volume), half-up rounding of a non-4-dp float
through its repr (`0.1 + 0.2 → 0.3000`, `10.12345 → 10.1235`), missing date/symbol, `bars_on`,
`last_bar_date`, `usd_idr_on` (on, between, after, before-first raises), FX validation, a history
key mismatch, `spy()`. Bars are built with `simkit.bar` (exact Decimals) and turned into
`History` with phase 1's `history_from_bars`; one test builds a `History` directly by keyword.
No helper from `stratkit.py` is needed.
**Code:**
```python
"""Point-in-time membership and the in-memory market (handover §6.4, plan phase 3).

Everything is synthetic and in memory: no database. Bars are built with ``simkit.bar`` (exact
4-dp Decimals) and turned into float64 ``History`` with ``history_from_bars``, the same way
``backtest.io`` will build them from Neon, so ``Market.bar`` must give the original Decimals back.
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import pytest
from simkit import D, bar

from seer_engine import dates
from seer_engine.backtest.market import SPY, Market, Membership
from seer_engine.prices import Bar
from seer_engine.strategies.base import History, history_from_bars


def _market(*histories: History, intervals=(), fx=()) -> Market:
    return Market(
        history={h.symbol: h for h in histories},
        membership=Membership(tuple(intervals)),
        fx=tuple(fx),
    )


# --------------------------------------------------------------------------- Membership


def test_members_on_honours_start_inclusive_end_exclusive():
    m = Membership((("AAA", D("2025-03-04"), D("2025-03-07")),))
    assert m.members_on(D("2025-03-03")) == frozenset()
    assert m.members_on(D("2025-03-04")) == frozenset({"AAA"})
    assert m.members_on(D("2025-03-06")) == frozenset({"AAA"})
    assert m.members_on(D("2025-03-07")) == frozenset()
    assert m.members_on(D("2030-01-01")) == frozenset()


def test_open_ended_interval_stays_a_member():
    m = Membership((("AAA", D("2025-03-04"), None),))
    assert m.members_on(D("2025-03-03")) == frozenset()
    assert m.members_on(D("2025-03-04")) == frozenset({"AAA"})
    assert m.members_on(D("2040-12-31")) == frozenset({"AAA"})


def test_members_on_unions_both_indices():
    # AAA: SP500 2020→2025-03-06, NDX 2025-03-05→open (overlap on 03-05); BBB only NDX;
    # CCC SP500 leaves 03-05 and rejoins 03-10 (a gap of three sessions).
    m = Membership(
        (
            ("AAA", D("2020-01-02"), D("2025-03-06")),
            ("AAA", D("2025-03-05"), None),
            ("BBB", D("2025-03-05"), None),
            ("CCC", D("2020-01-02"), D("2025-03-05")),
            ("CCC", D("2025-03-10"), None),
        )
    )
    assert m.members_on(D("2025-03-04")) == frozenset({"AAA", "CCC"})
    assert m.members_on(D("2025-03-05")) == frozenset({"AAA", "BBB"})
    assert m.members_on(D("2025-03-06")) == frozenset({"AAA", "BBB"})  # still in NDX
    assert m.members_on(D("2025-03-07")) == frozenset({"AAA", "BBB"})
    assert m.members_on(D("2025-03-10")) == frozenset({"AAA", "BBB", "CCC"})
    assert m.symbols() == ("AAA", "BBB", "CCC")


def test_membership_rejects_bad_intervals():
    with pytest.raises(ValueError):
        Membership((("AAA", D("2025-03-05"), D("2025-03-05")),))
    with pytest.raises(ValueError):
        Membership((("", D("2025-03-05"), None),))
    with pytest.raises(TypeError):
        Membership((("AAA", "2025-03-05", None),))
    with pytest.raises(TypeError):
        Membership([("AAA", D("2025-03-05"), None)])  # a list, not a tuple


def _synthetic_intervals(n: int) -> tuple[tuple[str, date, date | None], ...]:
    """``n`` deterministic intervals over 2015–2026 (no randomness): 795 symbols, some with
    two intervals, some open-ended, like the real ``universe`` table."""
    base = date(2015, 1, 2)
    out = []
    for i in range(n):
        start = base + timedelta(days=(i * 7919) % 4000)
        length = 30 + (i * 104729) % 3000
        end = None if i % 3 == 0 else start + timedelta(days=length)
        out.append((f"S{i % 795:03d}", start, end))
    return tuple(out)


def test_members_on_matches_brute_force_and_is_fast():
    intervals = _synthetic_intervals(1544)
    m = Membership(intervals)
    sessions = dates.sessions(date(2015, 1, 2), date(2026, 10, 2))
    assert len(sessions) == 2955

    t0 = time.perf_counter()
    got = [m.members_on(d) for d in sessions]
    elapsed = time.perf_counter() - t0
    assert elapsed < 2.0, f"members_on over {len(sessions)} sessions took {elapsed:.2f}s"

    for d, members in list(zip(sessions, got))[::97]:
        brute = frozenset(s for s, a, b in intervals if a <= d and (b is None or d < b))
        assert members == brute, d


# --------------------------------------------------------------------------- Market.bar


def test_bar_returns_exact_four_dp_decimals_from_float64():
    bars = [
        bar("AAA", "2025-03-03", "123.4567", "99999999.9999", "0.0001", "100.1000", 7_654_321_000),
        bar("AAA", "2025-03-04", "0.1", "1234.6", "0.07", "1234.5678", 1),
    ]
    m = _market(history_from_bars("AAA", bars))
    for b in bars:
        got = m.bar("AAA", b.date)
        assert got == b
        for name in ("open", "high", "low", "close"):
            value = getattr(got, name)
            assert type(value) is Decimal
            assert value.as_tuple().exponent == -4
        assert type(got.volume) is int


def test_bar_rounds_a_non_4dp_float_half_up_through_its_repr():
    h = History(
        symbol="AAA",
        dates=np.array([D("2025-03-03")], dtype="datetime64[D]"),
        open=np.array([0.1 + 0.2]),  # 0.30000000000000004
        high=np.array([10.12345]),  # repr '10.12345' -> half-up 10.1235
        low=np.array([0.00005]),  # -> 0.0001
        close=np.array([2.5]),
        volume=np.array([1500.0]),
    )
    got = _market(h).bar("AAA", D("2025-03-03"))
    assert got == Bar("AAA", D("2025-03-03"), Decimal("0.3000"), Decimal("10.1235"),
                      Decimal("0.0001"), Decimal("2.5000"), 1500)


def test_bar_is_none_for_a_missing_date_or_symbol():
    m = _market(history_from_bars("AAA", [bar("AAA", "2025-03-03", 10, 11, 9, 10)]))
    assert m.bar("AAA", D("2025-03-04")) is None
    assert m.bar("AAA", D("2025-02-28")) is None
    assert m.bar("ZZZ", D("2025-03-03")) is None


def test_bars_on_keeps_only_symbols_with_a_bar_that_day():
    a = [bar("AAA", "2025-03-03", 10, 11, 9, 10), bar("AAA", "2025-03-04", 10, 12, 9, 11)]
    b = [bar("BBB", "2025-03-03", 20, 21, 19, 20)]
    m = _market(history_from_bars("AAA", a), history_from_bars("BBB", b))
    assert m.bars_on(D("2025-03-04"), ("AAA", "BBB", "ZZZ")) == {"AAA": a[1]}
    assert m.bars_on(D("2025-03-03"), ["BBB", "AAA"]) == {"BBB": b[0], "AAA": a[0]}
    assert m.bars_on(D("2025-03-04"), ()) == {}


def test_last_bar_date():
    a = [bar("AAA", "2025-03-03", 10, 11, 9, 10), bar("AAA", "2025-03-05", 10, 12, 9, 11)]
    m = _market(history_from_bars("AAA", a))
    assert m.last_bar_date("AAA") == D("2025-03-05")
    assert m.last_bar_date("ZZZ") is None


# --------------------------------------------------------------------------- FX and SPY


def test_usd_idr_on_takes_the_latest_row_on_or_before():
    m = _market(fx=((D("2025-03-03"), Decimal("16000.0000")), (D("2025-03-05"), Decimal("16500.5000"))))
    assert m.usd_idr_on(D("2025-03-03")) == Decimal("16000.0000")
    assert m.usd_idr_on(D("2025-03-04")) == Decimal("16000.0000")
    assert m.usd_idr_on(D("2025-03-05")) == Decimal("16500.5000")
    assert m.usd_idr_on(D("2026-01-01")) == Decimal("16500.5000")
    with pytest.raises(ValueError):
        m.usd_idr_on(D("2025-03-02"))


def test_fx_must_be_ascending_decimals():
    with pytest.raises(ValueError):
        _market(fx=((D("2025-03-05"), Decimal("1")), (D("2025-03-03"), Decimal("1"))))
    with pytest.raises(TypeError):
        _market(fx=((D("2025-03-05"), 16000.0),))
    with pytest.raises(ValueError):
        _market(fx=((D("2025-03-05"), Decimal("0")),))


def test_history_key_must_match_its_symbol():
    h = history_from_bars("AAA", [bar("AAA", "2025-03-03", 10, 11, 9, 10)])
    with pytest.raises(ValueError):
        Market(history={"BBB": h}, membership=Membership(()), fx=())


def test_spy_returns_every_spy_bar_as_decimal_bars():
    spy = [bar(SPY, "2025-03-03", "580.1", "585.25", "578", "583.4567", 50_000_000),
           bar(SPY, "2025-03-04", "583", "590", "582.5", "589.0001", 60_000_000)]
    m = _market(history_from_bars(SPY, spy), history_from_bars("AAA", [bar("AAA", "2025-03-03", 1, 2, 1, 1)]))
    got = m.spy()
    assert got == {b.date: b for b in spy}
    assert list(got) == [D("2025-03-03"), D("2025-03-04")]
    assert _market().spy() == {}
```
**Impact:** +14 tests.

### Step 4: Runner tests
**File:** `engine/tests/test_backtest_runner.py:1` (new)
**Change:** **Which strategy:** the hand-checked scenario uses `FixedPicks`, a small fake
implementing the `Strategy` protocol (fixed ranked picks per `data_date`, filtered to the members
it is handed, and recording every call), so its numbers depend only on the simulator and the
runner. A separate smoke test runs the real `STRATEGY_A` with `DESIGN_PARAMS` on three synthetic
uptrending symbols with periodic two-session dips, asserting `prepared` == plain, repeat ==,
snapshot count, at least one fill, and only those symbols traded.

The scenario (March 2025, 9 sessions 03-04 … 03-14, `usd_idr` 16000 → cash0 1250.0000) covers:
two fills on the first session (one at the open below the limit), a TP exit, a session with 0
picks (03-05), BBB's bars ending on 03-05 while held → `close_unpriced` exactly once on 03-06
(`time`, forced, at the 20.2 mark, snapshot replaced), a `held` rejection, an `lt_one_share`
rejection, an expiry, an SL exit, CCC leaving the index while held (not closed by that), DDD
joining on 03-06 (offered for `data_date` 03-05 but filtered, because members are taken on
`data_date`), DDD halted 03-11 … 03-13 with bars back on 03-14 (never force-closed, still open at
the end with `days_held` 5). Every number is worked out in the test's comments and was confirmed
against the real `seer_engine.sim` at `d3a2e1d` with a scratch copy of steps 1–2: final cash
**940.5647**, final equity **1286.1647**, trades AAA tp +30.3490, BBB time (forced) +9.9045,
CCC sl −29.3688, DDD open (64 sh @ 5).

The smoke data was checked against an independent reference implementation of the Decisions'
indicator definitions (16 fills, 16 TP exits over 112 sessions); if phase 1's `STRATEGY_A`
places no order on it, investigate phase 1 before weakening the assertion.
**Code:**
```python
"""The backtest loop and the survivorship count (handover §6.4 and §6.7, plan phase 3).

The hand-checked scenario uses ``FixedPicks``, a fake strategy that returns a fixed, ranked
list of picks per ``data_date`` (filtered to the members it is given), so every number below
depends only on the simulator rules and the runner's wiring, not on Strategy A's indicators.
A separate smoke test runs the real ``STRATEGY_A`` through the runner on synthetic bars.

Simulator arithmetic used in the comments (``seer_engine.sim``):

- ``buy_cost(p, n) = q(p * n * 1.001)``, ``sell_proceeds(p, n) = q(p * n * 0.999)``, ``q`` = 4 dp half-up;
  ``pnl = sell_proceeds(exit) - buy_cost(fill)``.
- sizing: ``budget = min(q(equity / 4), cash - Σ buy_cost(limit, shares) of pending)``,
  ``shares = floor(budget / (limit * 1.001))``, lowest free slot, picks in rank order.
- fill when ``low < limit`` at ``min(open, limit)``; intraday SL before TP; ``high > tp`` exits at tp.
- equity = cash + Σ shares × last close.
"""

from __future__ import annotations

from collections.abc import Mapping, Set as AbstractSet
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from simkit import D, P, bar

from seer_engine import dates
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.runner import INITIAL_IDR, RunResult, YearGap, run_backtest, survivorship
from seer_engine.prices import Bar
from seer_engine.sim import Pick, Snapshot
from seer_engine.strategies.a import DESIGN_PARAMS, STRATEGY_A
from seer_engine.strategies.base import History, history_from_bars


def pick(symbol: str, limit: str, tp: str, sl: str) -> Pick:
    return Pick(symbol, P(limit), P(limit), P(tp), P(sl))


class FixedPicks:
    """A fake ``Strategy``: fixed ranked picks per data_date, keeping members only.

    Records every call as ``(entry, data_date, members, latest bar date seen)`` so tests can
    check what the runner passed in.
    """

    id = "FIXED"
    lookback = 1

    def __init__(self, table: Mapping[date, tuple[Pick, ...]]):
        self.table = dict(table)
        self.calls: list[tuple[str, date, frozenset[str], date | None]] = []

    def _picks(self, members: AbstractSet[str], data_date: date) -> list[Pick]:
        return [p for p in self.table.get(data_date, ()) if p.symbol in members]

    def picks(self, history: Mapping[str, History], members: AbstractSet[str],
              data_date: date, params: Any) -> list[Pick]:
        seen = [h.last_date() for h in history.values() if len(h)]
        self.calls.append(("picks", data_date, frozenset(members), max(seen) if seen else None))
        return self._picks(members, data_date)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return tuple(sorted(history))

    def picks_prepared(self, prepared: Any, members: AbstractSet[str],
                       data_date: date, params: Any) -> list[Pick]:
        self.calls.append(("prepared", data_date, frozenset(members), None))
        return self._picks(members, data_date)


# --------------------------------------------------------------------------- the scenario
#
# Sessions (March 2025, no holidays): 03-03 (data_date of the first session), then the window
# 03-04, 03-05, 03-06, 03-07, 03-10, 03-11, 03-12, 03-13, 03-14.
# USD/IDR on 03-04 = the 03-03 row, 16000 -> cash0 = q(20,000,000 / 16,000) = 1250.0000.

START, END = D("2025-03-04"), D("2025-03-14")

BARS = {
    "AAA": [
        bar("AAA", "2025-03-03", "10.5", "10.6", "10.1", "10.4"),
        bar("AAA", "2025-03-04", "10.2", "10.5", "9.8", "10.1"),
        bar("AAA", "2025-03-05", "10.3", "11.2", "10.2", "11.0"),
        bar("AAA", "2025-03-06", "11.0", "11.1", "10.9", "11.0"),
    ],
    # BBB's bars end on 03-05: it is gone from 03-06 on (delisted while held).
    "BBB": [
        bar("BBB", "2025-03-03", "20.5", "20.6", "20.1", "20.4"),
        bar("BBB", "2025-03-04", "19.5", "20.5", "19.0", "20.0"),
        bar("BBB", "2025-03-05", "20.0", "20.4", "19.8", "20.2"),
    ],
    "CCC": [
        bar("CCC", "2025-03-05", "51.0", "51.5", "50.5", "51.0"),
        bar("CCC", "2025-03-06", "49.8", "50.5", "49.5", "50.2"),
        bar("CCC", "2025-03-07", "50.5", "51.0", "50.0", "50.8"),
        bar("CCC", "2025-03-10", "50.0", "50.5", "44.0", "46.0"),
        bar("CCC", "2025-03-11", "46.0", "47.0", "45.5", "46.5"),
    ],
    # DDD: no bar on 03-11, 03-12, 03-13 (a three-session halt), bars resume 03-14.
    "DDD": [
        bar("DDD", "2025-03-06", "5.2", "5.3", "5.1", "5.2"),
        bar("DDD", "2025-03-07", "5.1", "5.2", "5.05", "5.15"),
        bar("DDD", "2025-03-10", "5.0", "5.1", "4.9", "4.95"),
        bar("DDD", "2025-03-14", "5.2", "5.5", "5.1", "5.4"),
        bar("DDD", "2025-03-17", "5.4", "5.6", "5.3", "5.5"),
    ],
}

INTERVALS = (
    ("AAA", D("2020-01-02"), None),
    ("AAA", D("2024-06-03"), None),  # also in the other index: unioned
    ("BBB", D("2020-01-02"), D("2025-03-06")),
    ("CCC", D("2020-01-02"), D("2025-03-07")),  # leaves the index while held
    ("DDD", D("2025-03-06"), None),  # joins on 03-06: a member for data_date 03-06, not 03-05
    ("EEE", D("2020-01-02"), None),  # never has bars
)

FX = (
    (D("2025-02-27"), Decimal("15000")),
    (D("2025-03-03"), Decimal("16000")),
    (D("2025-03-05"), Decimal("17000")),  # after the start: never used
)

TABLE = {
    # data_date 03-03 -> session 03-04
    D("2025-03-03"): (pick("AAA", "10", "11", "9"), pick("BBB", "20", "22", "18")),
    # data_date 03-04 -> session 03-05: no picks
    # data_date 03-05 -> session 03-06: BBB is held (rejected), DDD is not a member on 03-05
    D("2025-03-05"): (pick("BBB", "20", "22", "18"), pick("CCC", "50", "55", "45"), pick("DDD", "5", "6", "4")),
    # data_date 03-06 -> session 03-07: DDD (expires), EEE too dear for one share
    D("2025-03-06"): (pick("DDD", "5", "6", "4"), pick("EEE", "400", "450", "350")),
    # data_date 03-07 -> session 03-10: DDD again (fills)
    D("2025-03-07"): (pick("DDD", "5", "6", "4"),),
}


def scenario_market() -> Market:
    return Market(
        history={s: history_from_bars(s, b) for s, b in sorted(BARS.items())},
        membership=Membership(INTERVALS),
        fx=FX,
    )


def run_scenario(prepared: bool = False) -> tuple[RunResult, FixedPicks]:
    market = scenario_market()
    strategy = FixedPicks(TABLE)
    prep = strategy.prepare(market.history) if prepared else None
    return run_backtest(market, strategy, None, START, END, prepared=prep), strategy


def test_scenario_final_cash_equity_and_trades():
    r, _ = run_scenario()
    assert r.strategy_id == "FIXED"
    assert (r.start, r.end) == (START, END)
    assert r.usd_idr == Decimal("16000")
    assert r.initial_cash == Decimal("1250.0000")

    # 03-04: slot budget q(1250/4) = 312.5.
    #   AAA: floor(312.5 / 10.01) = 31 sh; committed buy_cost(10, 31) = 310.31.
    #   BBB: min(312.5, 1250 - 310.31) = 312.5 -> floor(312.5 / 20.02) = 15 sh.
    #   AAA low 9.8 < 10 fills at min(10.2, 10) = 10: cost q(310 * 1.001) = 310.3100.
    #   BBB low 19 < 20 fills at min(19.5, 20) = 19.5: cost q(292.5 * 1.001) = 292.7925.
    #   cash 1250 - 310.31 - 292.7925 = 646.8975; equity + 31*10.1 + 15*20 = 1259.9975.
    # 03-05: no picks. AAA high 11.2 > tp 11 -> exit at 11 (days 2): q(341 * 0.999) = 340.6590,
    #   pnl 340.659 - 310.31 = 30.3490. BBB stays (sl 18, tp 22), mark 20.2.
    #   cash 987.5565; equity + 15*20.2 = 1290.5565.
    # 03-06: slot budget q(1290.5565/4) = 322.6391. BBB held -> rejected 'held'; CCC:
    #   floor(322.6391 / 50.05) = 6 sh in slot 1; DDD not a member on 03-05 -> never offered.
    #   BBB has no bar (days 3). CCC low 49.5 < 50 fills at 49.8: cost q(298.8 * 1.001) = 299.0988.
    #   cash 688.4577. BBB's last bar (03-05) < 03-06 -> close_unpriced at mark 20.2:
    #   q(303 * 0.999) = 302.6970, pnl 302.697 - 292.7925 = 9.9045, reason time, forced.
    #   cash 991.1547; equity + 6*50.2 = 1292.3547 (the replaced snapshot).
    # 03-07: slot budget q(1292.3547/4) = 323.0887. DDD: floor(323.0887 / 5.005) = 64 sh, slot 2;
    #   EEE: floor(323.0887 / 400.4) = 0 -> 'lt_one_share'. DDD low 5.05 is not < 5 -> expires.
    #   CCC stays (days 2), mark 50.8. cash 991.1547; equity + 6*50.8 = 1295.9547.
    # 03-10: slot budget q(1295.9547/4) = 323.9887 -> DDD floor(323.9887 / 5.005) = 64 sh, slot 2.
    #   CCC low 44 <= sl 45 -> exit at 45 (days 3): q(270 * 0.999) = 269.7300,
    #   pnl 269.73 - 299.0988 = -29.3688. DDD low 4.9 < 5 fills at min(5.0, 5) = 5: cost 320.3200.
    #   cash 991.1547 + 269.73 - 320.32 = 940.5647; equity + 64*4.95 = 1257.3647.
    # 03-11, 03-12, 03-13: DDD has no bar (halt): no event, no forced close (it has a later bar),
    #   days 2, 3, 4, mark 4.95. equity 1257.3647.
    # 03-14: DDD bar back, days_held 4 < 5, o 5.2 h 5.5 l 5.1: no exit; days 5, mark 5.4.
    #   cash 940.5647; equity + 64*5.4 = 1286.1647. Open at the end, never liquidated.
    assert r.snapshots == (
        Snapshot(D("2025-03-03"), P("1250"), P("1250")),
        Snapshot(D("2025-03-04"), P("646.8975"), P("1259.9975")),
        Snapshot(D("2025-03-05"), P("987.5565"), P("1290.5565")),
        Snapshot(D("2025-03-06"), P("991.1547"), P("1292.3547")),
        Snapshot(D("2025-03-07"), P("991.1547"), P("1295.9547")),
        Snapshot(D("2025-03-10"), P("940.5647"), P("1257.3647")),
        Snapshot(D("2025-03-11"), P("940.5647"), P("1257.3647")),
        Snapshot(D("2025-03-12"), P("940.5647"), P("1257.3647")),
        Snapshot(D("2025-03-13"), P("940.5647"), P("1257.3647")),
        Snapshot(D("2025-03-14"), P("940.5647"), P("1286.1647")),
    )

    trades = [
        (o.symbol, o.shares, o.fill_date, o.fill_price, o.exit_date, o.exit_price, o.exit_reason,
         o.days_held, o.pnl_usd)
        for o in r.closed
    ]
    assert trades == [
        ("AAA", 31, D("2025-03-04"), P("10"), D("2025-03-05"), P("11"), "tp", 2, P("30.349")),
        ("BBB", 15, D("2025-03-04"), P("19.5"), D("2025-03-06"), P("20.2"), "time", 3, P("9.9045")),
        ("CCC", 6, D("2025-03-06"), P("49.8"), D("2025-03-10"), P("45"), "sl", 3, P("-29.3688")),
    ]
    # Cash reconciles: cash0 + Σ pnl - buy cost of what is still open.
    assert r.snapshots[-1].cash_usd == r.initial_cash + sum(o.pnl_usd for o in r.closed) - P("320.32")

    assert [(o.symbol, o.shares, o.slot, o.fill_price, o.days_held) for o in r.open_at_end] == [
        ("DDD", 64, 2, P("5"), 5)
    ]
    assert r.rejections == (("held", 1), ("lt_one_share", 1))

    kinds = [(e.session_date, e.kind, e.order.symbol, e.forced) for e in r.events]
    assert kinds == [
        (D("2025-03-04"), "fill", "AAA", False),
        (D("2025-03-04"), "fill", "BBB", False),
        (D("2025-03-05"), "exit", "AAA", False),
        (D("2025-03-06"), "fill", "CCC", False),
        (D("2025-03-06"), "exit", "BBB", True),
        (D("2025-03-07"), "expire", "DDD", False),
        (D("2025-03-10"), "exit", "CCC", False),
        (D("2025-03-10"), "fill", "DDD", False),
    ]


def test_gone_symbol_is_force_closed_exactly_once_at_the_first_session_after_its_last_bar():
    r, _ = run_scenario()
    forced = [e for e in r.events if e.forced]
    assert len(forced) == 1
    assert forced[0].order.symbol == "BBB"
    assert forced[0].session_date == D("2025-03-06")  # next_session(03-05), BBB's last bar
    assert forced[0].order.exit_reason == "time"
    # The halted DDD (no bars 03-11..03-13, back on 03-14) is never force-closed.
    assert not [e for e in r.events if e.order.symbol == "DDD" and e.kind == "exit"]


def test_members_are_taken_on_data_date_and_history_is_cut_at_data_date():
    _, strategy = run_scenario()
    sessions = dates.sessions(START, END)
    data_dates = [dates.prev_session(START)] + sessions[:-1]
    assert [c[1] for c in strategy.calls] == data_dates
    assert all(c[0] == "picks" for c in strategy.calls)
    members = {c[1]: c[2] for c in strategy.calls}
    assert members[D("2025-03-05")] == frozenset({"AAA", "BBB", "CCC", "EEE"})  # DDD joins 03-06
    assert members[D("2025-03-06")] == frozenset({"AAA", "CCC", "DDD", "EEE"})  # BBB left 03-06
    assert members[D("2025-03-07")] == frozenset({"AAA", "DDD", "EEE"})  # CCC left 03-07
    # No look-ahead: no history handed to the strategy reaches past data_date.
    for _, data_date, _, latest in strategy.calls:
        assert latest is not None and latest <= data_date


def test_prepared_run_equals_unprepared_and_runs_repeat_identically():
    plain, _ = run_scenario()
    prepped, strategy = run_scenario(prepared=True)
    assert all(c[0] == "prepared" for c in strategy.calls)
    assert prepped == plain
    again, _ = run_scenario()
    assert again == plain


def test_initial_idr_and_a_window_of_one_session():
    market = scenario_market()
    r = run_backtest(market, FixedPicks(TABLE), None, START, START, initial_idr=Decimal("16000000"))
    # 16,000,000 / 16,000 = 1000; AAA floor(250 / 10.01) = 24, BBB floor(250 / 20.02) = 12.
    # AAA fills at 10: q(240 * 1.001) = 240.24; BBB at 19.5: q(234 * 1.001) = 234.234.
    # cash 1000 - 240.24 - 234.234 = 525.526; equity + 24*10.1 + 12*20 = 1007.926.
    assert r.initial_cash == P("1000")
    assert r.snapshots == (
        Snapshot(D("2025-03-03"), P("1000"), P("1000")),
        Snapshot(D("2025-03-04"), P("525.526"), P("1007.926")),
    )
    assert r.closed == ()
    assert [o.symbol for o in r.open_at_end] == ["AAA", "BBB"]


def test_run_rejects_bad_windows_and_missing_fx():
    market = scenario_market()
    with pytest.raises(ValueError):
        run_backtest(market, FixedPicks(TABLE), None, D("2025-03-08"), END)  # a Saturday
    with pytest.raises(ValueError):
        run_backtest(market, FixedPicks(TABLE), None, START, D("2025-03-09"))  # a Sunday
    with pytest.raises(ValueError):
        run_backtest(market, FixedPicks(TABLE), None, END, START)
    no_fx = Market(history=market.history, membership=market.membership, fx=((D("2025-03-05"), Decimal("1")),))
    with pytest.raises(ValueError):
        run_backtest(no_fx, FixedPicks(TABLE), None, START, END)


def test_initial_idr_default():
    assert INITIAL_IDR == Decimal("20000000")


# --------------------------------------------------------------------------- survivorship


def test_survivorship_counts_member_sessions_without_a_bar_per_year():
    # Sessions 2024-12-30, 2024-12-31, 2025-01-02, 2025-01-03 (01-01 is a holiday).
    bars = {
        "AAA": [bar("AAA", d, 1, 1, 1, 1) for d in ("2024-12-30", "2024-12-31", "2025-01-02", "2025-01-03")],
        "GAP": [bar("GAP", d, 1, 1, 1, 1) for d in ("2024-12-30", "2025-01-03")],
        "LFT": [bar("LFT", "2024-12-30", 1, 1, 1, 1)],
        "SPY": [bar("SPY", "2024-12-30", 1, 1, 1, 1)],  # bars, never a member: ignored
    }
    intervals = (
        ("AAA", D("2020-01-02"), None),
        ("AAA", D("2024-01-02"), None),  # both indices: counted once per session
        ("GAP", D("2020-01-02"), None),
        ("GON", D("2024-12-31"), D("2025-01-03")),  # never fetched; member 12-31 and 01-02
        ("LFT", D("2024-12-01"), D("2024-12-31")),  # member on 12-30 only, has that bar
        ("OLD", D("2010-01-04"), D("2015-01-02")),  # never fetched, but not a member in the window
    )
    market = Market(
        history={s: history_from_bars(s, b) for s, b in sorted(bars.items())},
        membership=Membership(intervals),
        fx=(),
    )
    # 2024: pairs AAA 2 + GAP 2 + GON 1 + LFT 1 = 6; missing GON 12-31 (never), GAP 12-31 (other).
    # 2025: pairs AAA 2 + GAP 2 + GON 1 (01-03 is its end, exclusive) = 5;
    #       missing GON 01-02 (never), GAP 01-02 (other).
    assert survivorship(market, D("2024-12-30"), D("2025-01-03")) == (
        YearGap(year=2024, member_sessions=6, missing=2, missing_never_fetched=1, missing_other=1),
        YearGap(year=2025, member_sessions=5, missing=2, missing_never_fetched=1, missing_other=1),
    )
    assert survivorship(market, D("2025-01-04"), D("2025-01-05")) == ()  # a weekend


# --------------------------------------------------------------------------- Strategy A smoke


def _smoke_bars(symbol: str, sessions: list[date], phase: int) -> list[Bar]:
    """An uptrend (+0.4 % a session) with two -3 % sessions every 20 (shifted by ``phase``), and a
    deep intraday low the session after, so Strategy A's setup (close > SMA200, RSI(2) < 10,
    dollar volume ~1e8 > 2e7) fires and its limit fills. Prices are rounded to 4 dp first, so the
    float64 History holds exactly what ``bars`` would."""
    out = []
    prev = 100.0 + phase
    for t, d in enumerate(sessions):
        k = (t + phase) % 20
        c = prev * 0.97 if k in (17, 18) else prev * 1.004
        o = prev
        lo = min(o, c) * (0.97 if k == 19 else 0.995)
        hi = max(o, c) * 1.005
        out.append(bar(symbol, d, f"{o:.4f}", f"{hi:.4f}", f"{lo:.4f}", f"{c:.4f}", 1_000_000))
        prev = float(f"{c:.4f}")
    return out


def test_strategy_a_smoke_prepared_equals_plain():
    sessions = dates.sessions(D("2024-01-02"), D("2025-03-31"))
    history = {
        s: history_from_bars(s, _smoke_bars(s, sessions, phase))
        for s, phase in (("UPA", 0), ("UPB", 7), ("UPC", 13))
    }
    market = Market(
        history=history,
        membership=Membership(tuple((s, D("2020-01-02"), None) for s in sorted(history))),
        fx=((D("2023-12-29"), Decimal("16000")),),
    )
    start, end = sessions[200], sessions[-1]  # data_date sessions[199] has exactly 200 bars
    plain = run_backtest(market, STRATEGY_A, DESIGN_PARAMS, start, end)
    prepped = run_backtest(
        market, STRATEGY_A, DESIGN_PARAMS, start, end, prepared=STRATEGY_A.prepare(market.history)
    )
    assert prepped == plain
    assert run_backtest(market, STRATEGY_A, DESIGN_PARAMS, start, end) == plain
    assert plain.strategy_id == "A"
    assert len(plain.snapshots) == len(dates.sessions(start, end)) + 1
    assert any(e.kind == "fill" for e in plain.events)
    assert {o.symbol for o in plain.closed} <= {"UPA", "UPB", "UPC"}
```
**Impact:** +9 tests.

## Verification

**Build:** `engine/.venv/bin/python -c "import seer_engine.backtest.market, seer_engine.backtest.runner"` (from the worktree root, after Step 0)
**Tests:**
```bash
cd /home/miftah/.worktrees/seer/strategy-a-backtest
engine/.venv/bin/pytest engine/tests/test_backtest_market.py engine/tests/test_backtest_runner.py engine/tests/test_strategy_purity.py -q
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q
```
The full run must report 0 skipped: **471 passed** on phase 1 alone (448 + 23 here), **503 passed** if phase 2 landed first (480 + 23). Both measured by the reconciler on scratch copies.
**Manual check:** `test_strategy_purity.py` (phase 1) lists `market.py` and `runner.py` among the files it walked — if it reports what it checked, confirm both appear; otherwise `grep -n "glob" engine/tests/test_strategy_purity.py` and confirm `backtest/*.py` is covered.
**Exit criteria:** `Membership.members_on` honours `[start, end)` and unions both indices; `Market.bar` returns exact 4-dp Decimals from float64; the synthetic scenario ends with cash 940.5647 and equity 1286.1647 and the stated trade list, with exactly one forced close (BBB on 03-06), no forced close for the halted DDD, a 0-pick session, members on `data_date`, `prepared` == plain and repeat ==; `survivorship` per-year counts match the hand count; Strategy A smoke passes; 23 new tests (14 market + 9 runner); full suite green (471, or 503 with phase 2), 0 skipped.

## Handoffs

- **Phase 1 (checked by the reconciler, holds):** any `to_decimal(x)` where `x` is an element of a
  numpy array must be `to_decimal(float(x))` — numpy 2's `repr(np.float64)` is
  `'np.float64(…)'`, which `Decimal` rejects (`to_decimal` sees a `float` subclass and uses
  `repr`). Phase 1's `a.py` calls `to_decimal(f.close)` / `to_decimal(f.atr)` on `Features`
  fields, which `features_at` and `APrepared._features` build with `float(...)`, so they are plain
  floats; the smoke test here exercises that path.
  `History.last_date()` must return a `datetime.date` (`.item()` / `.tolist()`), and
  `index_of`/`upto` must accept a `datetime.date` — `Market` and the runner call them that way.
- **Phase 2:** `Market.spy()` returns `{}` (not an error) when there is no SPY history; a missing
  SPY bar is for `buy_and_hold` to raise on.
- **Phase 4:** `RunResult.snapshots[0]` is the start point (`prev_session(start)`, cash0, cash0);
  `run_metrics` should take pnls from `RunResult.closed` (forced closes included, reason `time`)
  and leave `open_at_end` out of the trade count. (`never_fetched_members` is computed by phase 5's
  command, restricted to the window; `Membership.symbols()` is not used for it.)
- **Phase 5:** `load_market` must build `Membership(tuple((symbol, start_date, end_date), ...))`
  from every `universe` row (both indices, no dedup needed), `fx` as a strictly ascending
  tuple of `(date, Decimal)`, and every `History` keyed by its own symbol with strictly ascending
  dates. `run_backtest` requires `start` and `end` to be NYSE sessions — the command must
  resolve `--end` to a session (the last SPY bar) before calling it.
- **Phase 6:** document `Market`, `Membership`, `run_backtest`, `RunResult`, `survivorship` and
  the gone-vs-halted rule in `engine/package_readme.md`.

## Rollback

Delete the four new files (`git revert` the phase commit). Nothing else references them until
phases 4–5 land; no data, schema or config is touched.
