# Phase 3: Book runner, `run_rules` dispatch, run stats, V0 parity

**Plan set:** `TRADE_RULES_DEV_SEARCH_PLAN.md`
**Analysis:** `20261003-195606-T7R2_code_analyzer.md`
**Satisfies:** R1, R8. R1: `DESIGN_V0` reproduces §5. The dispatch is identical to `run_backtest` for A, A2 and B, and the book engine replays §5 exactly. R8: determinism and purity.
**Depends on:** Phase 1 (`sim/rules.py`, `sim/book.py`), Phase 2 (`strategies/allocator.py`)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/backtest`

---

## Goal

After this phase there is one pure entry point that runs a strategy under a `TradeRules` value.
- `run_rules` sends `DESIGN_V0` to the **unchanged** `run_backtest`. It sends every book rule set to the new `run_book` loop.
- `run_stats` reduces either result type to what the dev report needs: metrics, exposure, turnover, cost drag, dividends, Sharpe and calendar-year returns.

The phase also proves on seeded synthetic markets that two runs are identical:
- `run_book(PICKS, …, V0_BOOK)`
- `run_backtest(strategy, …)`

They give equal (date, cash, equity) snapshots, equal closed-trade multisets, equal fill multisets and equal open positions, for A, A2 and B. That is the engine-level half of R1.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates** (all in `engine/src/seer_engine/backtest/book_runner.py`, new, pure):
- `DividendMap = Mapping[str, Mapping[date, Decimal]]`
- `BOOK_EXIT_REASONS: tuple[str, ...] = ("tp", "sl", "time", "gap", "signal", "forced")`: an addition to the index contract. It is the order of `RunStats.metrics.exit_reasons` for a `BookResult`, and phase 10 may render it.
- `TRADING_DAYS = 252`: an addition, the Sharpe annualization constant.
- `@dataclass(frozen=True) class BookResult`: fields exactly as the index contract, in its order.
- `def run_book(market, allocator, params, rules, start, end, *, prepared=None, dividends=<empty>, initial_idr=INITIAL_IDR, usd_idr=None) -> BookResult`
- `def run_rules(market, strategy_or_allocator, params, rules, start, end, *, prepared=None, dividends=<empty>, usd_idr=None) -> RunResult | BookResult`
- `@dataclass(frozen=True) class RunStats`: fields exactly as the index contract.
- `def run_stats(r: RunResult | BookResult) -> RunStats`
- The test file `engine/tests/test_book_runner.py` (new): **47 tests**.
- Behaviour fixed here (plan index D-J): on a decision session the allocator is handed
  `held = book.held() − {rules.idle_symbol}`. The idle position is the runner's, never a
  family's, so no allocator can keep it as its own target.

**Signature changes:** none. The `dividends` default is an immutable empty `MappingProxyType`. That is the contract's `{}` default without a shared mutable default, and it is the same for callers.

**Requires (from earlier phases).** These are interface notes. Each is a semantic the V0 parity test depends on. Every one of them was checked against phase 1's and phase 2's plan code by the reconciler and holds as written.

- **N1 (phases 1 and 2) — settled, plan index D-A.** Strategies A, A2 and B return **uncapped** pick lists. For example, B on seed 39 gets 121 `no_slot` rejections in the simulator. For §5 parity:
  - `PicksAllocator` emits **every** non-held pick, each at `equal_weight(4)`, and does not truncate to the free slots (phase 2 Decision 2);
  - `step_book` checks Σ weight ≤ 1 **only when `rules.max_positions is None`** (phase 1 interface decision 1), so `V0_BOOK` (`max_positions=4`) accepts them.

  Truncating in `PicksAllocator` would **break parity**: in `sim.size_picks` (`sizing.py:700-725`) an `lt_one_share` pick does **not** consume a slot, so the next-ranked pick takes it.
- **N2 (phase 1).** In step 4, the "add" to a held target must be gated exactly like step 3's trims: `rules.resize or symbol == rules.idle_symbol`. Under `V0_BOOK` (`resize=False`), `PicksAllocator` re-targets every held symbol at weight 0.25, so an ungated add would buy more of a held position. `sim` never adds to a holding (`sizing.py:703`).
- **N3 (phase 1).** The `max_positions` check comes **before** sizing, so `no_slot` wins over `too_small`. As in `size_picks` (`sizing.py:706-725`):
  - only an entry sized at night to more than 0 shares counts toward the cap, whether it later fills, goes `unfilled`, hits `no_bar` or hits `cash`;
  - a `too_small` entry consumes no slot.

  The parity test checks `book no_slot == sim no_slot` and `book too_small == sim lt_one_share`.
- **N4 (phase 1, plan index D-B).** `Target.limit is None` with `rules.entry == "limit"` never raises: an **unheld** limit-less target is bought exactly like `open_limit` (limit `q(last × 1.02)`), and a **held** limit-less target is never added to. `PicksAllocator` emits held symbols with no limit, stop or take, and V0_BOOK never buys those (N2); every unheld pick carries its limit, so the fallback never fires in the parity runs.
- **N5 (phase 1).** `close_book_unpriced` returns a `Book` whose `equity` is recomputed as `q(cash + Σ shares × mark)` (as `sim.close_unpriced`, `lifecycle.py:558`) and whose `last_session` is unchanged.
  - Each forced `Trade` has `exit_reason="forced"`, `exit_date = book.last_session`, `exit_price = mark` and `days_held` unchanged.
  - Each forced `Fill` has `reason="forced"`.
  - `run_book` builds the replaced snapshot from `book.cash`/`book.equity`, and the next night's sizing reads that `book.equity`, exactly as `run_backtest` does with the replaced portfolio.
- **N6 (phase 1).** After `step_book`, `book.equity == stepped.snapshot.equity_usd` (the next night's sizing base, as `Portfolio.equity`).
- **N7 (phase 1).** `run_book` passes `idle_symbol_ok=True` **exactly** when it appended the residual idle target, and `False` otherwise (phase 1 interface decision 2 gives it exactly this meaning). `run_book` raises its own ValueError if the allocator targets the idle symbol, and it hands the allocator `held` **without** the idle symbol (plan index D-J), so a family that keeps its held symbols (F7, PICKS) never re-targets the idle position.
- **N8 (phase 1).** `step_book` takes `dividends` as the **6th positional** argument and `idle_symbol_ok` as a keyword, matching the index signature order.
- **N9 (phase 1).** The following must hold:
  - `Fill.cost_usd == q(price × shares × rules.cost_rate)`;
  - `Fill.cash_usd` is signed: `-q(p×n×(1+c))` for a buy and `+q(p×n×(1−c))` for a sell;
  - `BookStep.dividends` holds `(symbol, cash credited)`;
  - `BookStep.rejected` holds `(symbol, reason)`;
  - `Book.held()` returns a `frozenset[str]` that includes `exit_pending` positions;
  - `Book.positions` is sorted by symbol;
  - every `Position` has `.symbol`, `.shares`, `.mark`, `.entry_date`, `.entry_price` and `.days_held`.
- **N10 (phase 1).** These constructors accept keywords in the index's field order: `BookSnapshot(date, cash_usd, equity_usd, invested_usd)`, `Fill(...)`, `Trade(...)` and `Target(symbol, weight, last, limit=None, stop=None, take=None)`. A `Target` weight such as `Decimal("0.4")` or `Decimal("1")` is valid: it is a multiple of `WEIGHT_QUANTUM`.
- **N11 (phase 2).** Four requirements:
  - `PicksAllocator.prepare(history)` takes no params, while the strategy lives in `PicksParams`. It must still return a value that `targets_prepared(prepared, M, d, held, PicksParams(...))` accepts for any strategy, with the P4 identity.
  - `PicksAllocator` emits held symbols first (symbol order, weight `equal_weight(slots)`, `last` = the latest close ≤ d) and then the non-held picks in rank order. It drops picks for held symbols.
  - `isinstance(PICKS, Allocator)` is True.
  - `isinstance(PICKS, Strategy)` is False, because it has no `picks` attribute. `run_rules` relies on this.
- **N12 (phase 2).** `PicksParams(strategy, params)` accepts any object satisfying `strategies.base.Strategy`, including the test-only `FixedPicks` fake from `tests/test_backtest_runner.py`, with `params=None`.
- **N13 (phase 1).** `V0_BOOK.entry == "limit"`, `max_positions == 4`, `time_stop == 5`, `resize is False`, `dividends is False`, `idle_symbol is None` and `cost_rate == Decimal("0.001")`. The presets `DAILY_SWITCH`, `DAILY_SWITCH_TBILL`, `WEEKLY_HOLD` and `MONTHLY_HOLD` are as the index fixes them. `dataclasses.replace(WEEKLY_HOLD, id="weekly-hold-tbill", idle_symbol="BIL")` and `replace(DAILY_SWITCH, id="…", dividends=False)` construct valid rules.
- **N14 (phase 1).** `is_decision_session(rules, s)` makes these sessions decisions:
  - weekly: 2025-02-24, 2025-03-03 and 2025-03-10;
  - monthly: only 2025-03-03 within 2025-02-24 … 2025-03-14.

**Leaves alone (owned by others):**
- `sim/*` (phase 1) and `strategies/allocator.py` and `tests/allocatorkit.py` (phase 2);
- `backtest/dev.py` (phase 9) and every other new module;
- `runner.py`, `metrics.py`, `benchmark.py` and `market.py`, which are imported read-only;
- every existing file, including `tests/test_backtest_runner.py`, which is imported read-only.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/book_runner.py` | create (new file, whole file at line 1) | `DividendMap`, `BOOK_EXIT_REASONS`, `TRADING_DAYS`, `BookResult`, `run_book`, `run_rules`, `RunStats`, `run_stats` and private helpers |
| `engine/tests/test_book_runner.py` | create (new file, whole file at line 1) | 47 tests: V0 dispatch, V0_BOOK parity, `run_book` wiring and `run_stats` hand checks |

No existing file is edited. `tests/test_strategy_purity.py` globs `backtest/*.py`, so it covers the new module automatically. The module was AST-checked against its rules while planning: no forbidden import, attribute or call.

## Decisions taken here (recorded for the reconciler)

| Fork | Chosen | Why |
|---|---|---|
| Idle target when the allocator already targets the idle symbol | ValueError in `run_book` | The idle weight is the runner's residual. Merging would blur which episode is "idle" (excluded from trades). No registry candidate does it |
| Idle target when the idle symbol has no bar on `data_date` | None is added; the residual stays cash. This applies even if an idle position is held: the engine then signal-exits it per its rules | This is exactly the index contract ("with a bar on d"). For BIL in the store it only bites before 2007-05-30, when nothing is held |
| Dividends when `rules.dividends` is False | `run_book` passes `{}` | This makes the gate explicit at the routing site. `step_book` gates too, harmlessly |
| `run_rules(DESIGN_V0, dividends=…)` | Ignored, no error | `DESIGN_V0.dividends` is False. Phase 9 passes the store's dividends for every candidate |
| `run_rules(DESIGN_V0, usd_idr=x)` | ValueError unless `x == market.usd_idr_on(start)` | This is the contract. `run_backtest` is frozen and always converts at that rate. REF-A-V0 before 1999 is handled by phase 9 (plan index D-C; Handoffs H1) |
| The allocator's `held` under an idle rule set | `book.held() − {rules.idle_symbol}` (plan index D-J) | The idle position belongs to the runner; F7 and PICKS keep every held symbol they are shown, and would otherwise re-target BIL beside the runner's residual (a duplicate symbol) |
| RunStats exposure, turnover and Sharpe denominators | Means run over `snapshots[1:]`, the sessions. Years run from `snapshots[0].date` to `snapshots[-1].date` (Actual/365.25, `metrics.YEAR_DAYS`) | Same span as `metrics.cagr_between` |
| Turnover numerator | Σ price × shares over **every** fill: buys, sells, trims, adds, idle and forced fills | Idle and forced fills are real orders that cost real money |
| `cost_drag` numerator | The fees of the **closed non-idle episodes' own fills**, over their gross (pnl + those fees). `costs_usd` still reports every fee | Numerator and denominator then cover the same trades |
| Matching fills to an episode | Same symbol, `entry_date ≤ fill date ≤ exit_date` | Episodes of one symbol never share a date: there is no re-entry on an exit session, and a forced close needs no bar while an entry needs one |
| `RunStats.metrics` for a `RunResult` | `metrics.run_metrics(r)` unchanged (forced closes inside `time`) | The same numbers as the closed A, A2 and B reports |
| `RunStats.metrics` for a `BookResult` | `strategy_metrics` over the non-idle pnls in exit order, plus `avg_days_held` and `exit_reasons` over the non-idle trades in `BOOK_EXIT_REASONS` order (zeros kept) | The index says "+ avg_days_held". `exit_reasons` costs nothing and phase 10 can render it |
| `worst_year` ties | The lowest return; on a tie, the earlier year | Deterministic |
| Seeded-market RNG | `numpy.random.default_rng(seed)`, as `test_backtest_b_report.py` and others do. A coverage test asserts that seed 39 still exercises every simulator path, so a numpy stream change fails loudly and never silently | Existing test convention |
| Reusing the hand-checked scenario | Import `START`, `END`, `TABLE`, `FixedPicks` and `scenario_market` from `tests/test_backtest_runner.py` (frozen, so the import is stable) | One source of the hand-checked numbers |

## Implementation Steps

### Step 1: Create the book runner module
**File:** `engine/src/seer_engine/backtest/book_runner.py:1` (new file)
**Change:** create the whole module below, verbatim.

These parts were **verified while planning**. They ran against stub `sim.book`, `sim.rules` and `allocator` modules: the `run_rules` `DESIGN_V0` branch, `run_stats` on both result types (hand checks) and the type checks. The `run_book` loop needs phases 1 and 2 to run.
**Code:**
```python
"""The book engine's session loop, the trade-rules dispatch, and run statistics (P7a, plan phase 3).

Pure (tests/test_strategy_purity.py globs this directory): no database, network, clock,
randomness, logging or file access. Three things live here.

``run_book`` drives ``sim.book.step_book`` over every NYSE session S in ``[start, end]``, in the
same shape as ``runner.run_backtest``:

1. on a decision session (``sim.rules.is_decision_session``) the allocator maps history through
   ``data_date = prev_session(S)``, the members on ``data_date`` and the symbols held at night
   (the idle instrument left out: it is the runner's, never a family's) to target weights; on
   any other session the targets are ``None`` (no signal exits, no entries, no resizes);
2. with ``rules.idle_symbol`` set and a bar for it dated ``data_date``, the residual weight
   ``1 - sum(weights)`` is appended as the last target, in that instrument;
3. ``step_book`` gets S's bars for every held or targeted symbol, and (``rules.dividends`` only)
   the cash dividends whose ex-date is S for the symbols held at night;
4. every position whose symbol has no bar on S or later in the loaded data is force-closed at
   its mark (``close_book_unpriced``) and S's snapshot is replaced, exactly as ``run_backtest``
   does with ``sim.close_unpriced``.

``run_rules`` is the one entry point by rules: ``DESIGN_V0`` with a ``Strategy`` goes to the
unchanged ``run_backtest`` (so A, A2 and B stay byte-identical by construction); any book rule
set with an ``Allocator`` goes to ``run_book``; any other pairing is a TypeError.

``run_stats`` reduces either result to what the dev report needs. Floats exist only there, and
every float sum runs left to right in a plain loop, as ``backtest.metrics`` does.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from seer_engine import dates
from seer_engine.backtest.market import Market
from seer_engine.backtest.metrics import YEAR_DAYS, Metrics, run_metrics, strategy_metrics
from seer_engine.backtest.runner import INITIAL_IDR, RunResult, run_backtest
from seer_engine.sim.book import (
    Book,
    BookSnapshot,
    Fill,
    Position,
    Target,
    Trade,
    close_book_unpriced,
    new_book,
    step_book,
    to_weight,
)
from seer_engine.sim.model import COST_RATE, initial_cash_usd, q
from seer_engine.sim.rules import TradeRules, is_decision_session
from seer_engine.strategies.allocator import Allocator
from seer_engine.strategies.base import Strategy

DividendMap = Mapping[str, Mapping[date, Decimal]]  # symbol -> {ex_date: cash amount per share}

# Book exit reasons in the order RunStats.metrics.exit_reasons lists them (zeros kept). A
# RunResult keeps metrics.EXIT_REASONS ("tp", "sl", "time", "gap"), forced closes inside "time".
BOOK_EXIT_REASONS: tuple[str, ...] = ("tp", "sl", "time", "gap", "signal", "forced")
TRADING_DAYS = 252  # Sharpe annualization: daily mean / daily pstdev x sqrt(252)

_NO_DIVIDENDS: DividendMap = MappingProxyType({})
_ZERO = Decimal("0.0000")


@dataclass(frozen=True)
class BookResult:
    """One book-engine run.

    ``snapshots[0]`` is ``BookSnapshot(prev_session(start), cash0, cash0, 0)``, then one per
    session (after any forced close). ``fills`` is every fill in execution order, forced closes
    included; ``trades`` every closed holding episode in exit order; ``open_at_end`` the
    positions still held after ``end`` (marked, never liquidated). ``dividends_usd`` is the cash
    credited by dividends, ``costs_usd`` the sum of ``Fill.cost_usd``. ``rejections`` counts
    ``step_book`` rejections by reason, sorted by reason.
    """

    allocator_id: str
    params: Any
    rules: TradeRules
    start: date
    end: date
    usd_idr: Decimal
    initial_cash: Decimal
    snapshots: tuple[BookSnapshot, ...]
    fills: tuple[Fill, ...]
    trades: tuple[Trade, ...]
    open_at_end: tuple[Position, ...]
    dividends_usd: Decimal
    costs_usd: Decimal
    rejections: tuple[tuple[str, int], ...]


def _session(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    if not dates.is_session(d):
        raise ValueError(f"{name} {d} is not an NYSE session")
    return d


def _with_idle(
    market: Market, rules: TradeRules, targets: tuple[Target, ...], data_date: date
) -> tuple[tuple[Target, ...], bool]:
    """``targets`` plus the residual idle target when ``rules`` name one, and whether one was added.

    The idle target is ``Target(idle, to_weight(1 - sum(weights)), last=its close on data_date)``,
    appended last (rank order: idle last). None is added when the idle symbol has no bar dated
    ``data_date`` or the weights already sum to 1 or more. An allocator that targets the idle
    symbol itself is a ValueError: the idle weight is the runner's alone.
    """
    idle = rules.idle_symbol
    if idle is None:
        return targets, False
    for t in targets:
        if t.symbol == idle:
            raise ValueError(f"the allocator targets the idle symbol {idle}; its weight is the runner's residual")
    idle_bar = market.bar(idle, data_date)
    if idle_bar is None:
        return targets, False
    total = Decimal(0)
    for t in targets:
        total += t.weight
    residual = Decimal(1) - total
    if residual <= 0:
        return targets, False
    return targets + (Target(symbol=idle, weight=to_weight(residual), last=q(idle_bar.close)),), True


def _dividends_on(dividends: DividendMap, held: Iterable[str], session: date) -> dict[str, Decimal]:
    """``{symbol: amount per share}`` for the ``held`` symbols whose ex-date is ``session``, by symbol."""
    out: dict[str, Decimal] = {}
    for symbol in sorted(held):
        by_date = dividends.get(symbol)
        if by_date is None:
            continue
        amount = by_date.get(session)
        if amount is not None:
            out[symbol] = amount
    return out


def _gone(market: Market, symbol: str, session: date) -> bool:
    """True when ``symbol`` has no bar on ``session`` or later in the loaded data."""
    last = market.last_bar_date(symbol)
    return last is None or last < session


def _invested(book: Book, rules: TradeRules) -> Decimal:
    """``q(sum(shares x mark))`` over the non-idle positions (the exposure numerator)."""
    total = Decimal(0)
    for p in book.positions:
        if p.symbol != rules.idle_symbol:
            total += p.shares * p.mark
    return q(total)


def run_book(
    market: Market,
    allocator: Allocator,
    params: Any,
    rules: TradeRules,
    start: date,
    end: date,
    *,
    prepared: Any = None,
    dividends: DividendMap = _NO_DIVIDENDS,
    initial_idr: Decimal = INITIAL_IDR,
    usd_idr: Decimal | None = None,
) -> BookResult:
    """Run ``allocator`` with ``params`` under the book rules ``rules`` over every session in ``[start, end]``.

    ``start`` and ``end`` are NYSE sessions, ``start <= end``. Starting cash is
    ``initial_cash_usd(initial_idr, usd_idr)``, with ``usd_idr`` defaulting to
    ``market.usd_idr_on(start)``. With ``prepared`` (``allocator.prepare(market.history)``) the
    targets come from ``targets_prepared``; without it, from ``targets`` on every history cut at
    ``data_date``. The allocator contract makes both give the same result. ``dividends`` maps
    symbol -> {ex_date: cash per share}; only the held symbols' entries for the session being
    stepped are passed on, and only when ``rules.dividends``.

    ``rules.engine`` must be ``"book"``: ``DESIGN_V0`` (``"bracket_v0"``) is a ValueError, run it
    with ``run_rules``.
    """
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    if not isinstance(rules, TradeRules):
        raise TypeError(f"rules must be TradeRules, got {type(rules).__name__}")
    if rules.engine != "book":
        raise ValueError(f"rules {rules.id!r} use the {rules.engine} engine; run them with run_rules")
    if not isinstance(allocator, Allocator):
        raise TypeError(f"allocator must be an Allocator, got {type(allocator).__name__}")
    if not isinstance(dividends, Mapping):
        raise TypeError(f"dividends must be a Mapping, got {type(dividends).__name__}")
    _session("start", start)
    _session("end", end)
    if end < start:
        raise ValueError(f"end {end} is before start {start}")
    rate = market.usd_idr_on(start) if usd_idr is None else usd_idr
    cash0 = initial_cash_usd(initial_idr, rate)

    book = new_book(cash0)
    data_date = dates.prev_session(start)
    snapshots: list[BookSnapshot] = [
        BookSnapshot(date=data_date, cash_usd=book.cash, equity_usd=book.equity, invested_usd=_ZERO)
    ]
    fills: list[Fill] = []
    trades: list[Trade] = []
    rejections: Counter[str] = Counter()
    dividends_usd = _ZERO
    costs_usd = _ZERO

    for session in dates.sessions(start, end):
        held = book.held()
        targets: tuple[Target, ...] | None = None
        idle_added = False
        if is_decision_session(rules, session):
            members = market.membership.members_on(data_date)
            # The idle position is the runner's residual, never a family's (plan index D-J).
            mine = held - {rules.idle_symbol} if rules.idle_symbol is not None else held
            if prepared is None:
                history = {s: h.upto(data_date) for s, h in market.history.items()}
                wanted = allocator.targets(history, members, data_date, mine, params)
            else:
                wanted = allocator.targets_prepared(prepared, members, data_date, mine, params)
            targets, idle_added = _with_idle(market, rules, tuple(wanted), data_date)

        symbols = set(held)
        if targets is not None:
            symbols.update(t.symbol for t in targets)
        bars = market.bars_on(session, sorted(symbols))
        divs = _dividends_on(dividends, held, session) if rules.dividends else {}

        stepped = step_book(book, session, bars, targets, rules, divs, idle_symbol_ok=idle_added)
        book = stepped.book
        fills.extend(stepped.fills)
        trades.extend(stepped.trades)
        for _, amount in stepped.dividends:
            dividends_usd += amount
        for _, reason in stepped.rejected:
            rejections[reason] += 1
        snapshot = stepped.snapshot

        gone = [p.symbol for p in book.positions if _gone(market, p.symbol, session)]
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
        snapshots.append(snapshot)
        data_date = session

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


def run_rules(
    market: Market,
    strategy_or_allocator: Strategy | Allocator,
    params: Any,
    rules: TradeRules,
    start: date,
    end: date,
    *,
    prepared: Any = None,
    dividends: DividendMap = _NO_DIVIDENDS,
    usd_idr: Decimal | None = None,
) -> RunResult | BookResult:
    """Run under ``rules``: the single dispatch every P7a caller uses.

    - ``rules.engine == "bracket_v0"`` (only ``DESIGN_V0``) with a ``Strategy``:
      ``run_backtest(market, strategy, params, start, end, prepared=prepared)`` unchanged.
      ``dividends`` are ignored (``DESIGN_V0.dividends`` is False). ``usd_idr`` must be None or
      equal ``market.usd_idr_on(start)`` (ValueError otherwise): ``run_backtest`` always converts
      at that rate.
    - ``rules.engine == "book"`` with an ``Allocator``: ``run_book`` with every argument.
    - any other pairing: TypeError.
    """
    if not isinstance(rules, TradeRules):
        raise TypeError(f"rules must be TradeRules, got {type(rules).__name__}")
    if rules.engine == "bracket_v0":
        if not isinstance(strategy_or_allocator, Strategy):
            raise TypeError(
                f"rules {rules.id!r} run a bracket Strategy, got {type(strategy_or_allocator).__name__}"
            )
        if not isinstance(market, Market):
            raise TypeError(f"market must be a Market, got {type(market).__name__}")
        if usd_idr is not None and usd_idr != market.usd_idr_on(start):
            raise ValueError(
                f"rules {rules.id!r} convert at market.usd_idr_on(start) = {market.usd_idr_on(start)}, got {usd_idr}"
            )
        return run_backtest(market, strategy_or_allocator, params, start, end, prepared=prepared)
    if not isinstance(strategy_or_allocator, Allocator):
        raise TypeError(f"rules {rules.id!r} run an Allocator, got {type(strategy_or_allocator).__name__}")
    return run_book(
        market,
        strategy_or_allocator,
        params,
        rules,
        start,
        end,
        prepared=prepared,
        dividends=dividends,
        usd_idr=usd_idr,
    )


# --------------------------------------------------------------------------- run statistics


@dataclass(frozen=True)
class RunStats:
    """What the dev report needs from either result type.

    - ``metrics``: ``metrics.run_metrics`` for a RunResult; for a BookResult
      ``strategy_metrics(snapshots, pnls of the non-idle trades)`` plus ``avg_days_held`` and
      ``exit_reasons`` (``BOOK_EXIT_REASONS`` order, zeros kept), both over the non-idle trades.
    - ``exposure``: mean over the sessions (``snapshots[1:]``) of invested / equity, where
      invested is ``BookSnapshot.invested_usd`` (idle instrument excluded) or, for a RunResult,
      ``equity - cash``.
    - ``turnover``: sum of fill notionals (price x shares, buys and sells, idle and forced fills
      included) / mean session equity / years, years = calendar days from ``snapshots[0]`` to
      ``snapshots[-1]`` / 365.25.
    - ``costs_usd``: every fee paid (``sum(Fill.cost_usd)``; for a RunResult
      ``q(price x shares x COST_RATE)`` per fill and exit).
    - ``gross_pnl_usd``: sum of the non-idle closed trades' pnl plus the fees of their own fills.
    - ``cost_drag``: those trades' fees / ``gross_pnl_usd`` when gross > 0, else None.
    - ``dividends_usd``: cash dividends credited (0 for a RunResult).
    - ``daily_returns``: ``equity[i] / equity[i-1] - 1`` over consecutive snapshots.
    - ``sharpe``: mean / population stdev of ``daily_returns`` x sqrt(252); None with fewer than
      2 returns or a zero stdev.
    - ``year_returns``: per calendar year of ``snapshots[1:]``, ascending, the last equity of the
      year over the last equity of the year before (``snapshots[0]`` for the first year), minus 1.
    - ``worst_year``: the lowest year return (ties: the earlier year), None when there is none.
    """

    metrics: Metrics
    exposure: float
    turnover: float
    costs_usd: float
    gross_pnl_usd: float
    cost_drag: float | None
    dividends_usd: float
    sharpe: float | None
    daily_returns: tuple[float, ...]
    year_returns: tuple[tuple[int, float], ...]
    worst_year: tuple[int, float] | None


def _fsum(values: Iterable[float]) -> float:
    """Left-to-right float sum from 0.0 (never ``sum``/``math.fsum``), as ``metrics._sum``."""
    total = 0.0
    for v in values:
        total += v
    return total


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("mean of no values")
    return _fsum(values) / len(values)


def _equities(snapshots: Sequence[tuple[date, Decimal, Decimal]]) -> list[tuple[date, float]]:
    """``(date, float equity)`` per snapshot; ValueError on fewer than 2 snapshots or equity <= 0."""
    if len(snapshots) < 2:
        raise ValueError(f"a run has at least 2 snapshots, got {len(snapshots)}")
    out: list[tuple[date, float]] = []
    for d, _, equity in snapshots:
        if equity <= 0:
            raise ValueError(f"equity on {d} must be > 0, got {equity}")
        out.append((d, float(equity)))
    return out


def _daily_returns(equity: Sequence[tuple[date, float]]) -> tuple[float, ...]:
    return tuple(cur / prev - 1.0 for (_, prev), (_, cur) in zip(equity, equity[1:]))


def _sharpe(returns: Sequence[float]) -> float | None:
    n = len(returns)
    if n < 2:
        return None
    mean = _fsum(returns) / n
    var = _fsum((r - mean) ** 2 for r in returns) / n
    sd = math.sqrt(var)
    if sd == 0.0:
        return None
    return mean / sd * math.sqrt(TRADING_DAYS)


def _year_returns(equity: Sequence[tuple[date, float]]) -> tuple[tuple[int, float], ...]:
    last_of_year: dict[int, float] = {}
    for d, value in equity[1:]:
        last_of_year[d.year] = value  # snapshots ascend, so the last one of a year wins
    out: list[tuple[int, float]] = []
    base = equity[0][1]
    for year in sorted(last_of_year):
        value = last_of_year[year]
        out.append((year, value / base - 1.0))
        base = value
    return tuple(out)


def _turnover(notional: Decimal, equity: Sequence[tuple[date, float]]) -> float:
    years = (equity[-1][0] - equity[0][0]).days / YEAR_DAYS
    mean_equity = _mean([value for _, value in equity[1:]])
    if years <= 0 or mean_equity <= 0:
        return 0.0
    return float(notional) / mean_equity / years


def _fee(price: Decimal, shares: Decimal | int) -> Decimal:
    """The fee part of one simulator fill: ``q(price x shares x COST_RATE)`` (== ``Fill.cost_usd``)."""
    return q(price * shares * COST_RATE)


def _assemble(
    metrics: Metrics,
    equity: Sequence[tuple[date, float]],
    exposures: Sequence[float],
    notional: Decimal,
    costs: Decimal,
    trade_pnl: Decimal,
    trade_fees: Decimal,
    dividends: Decimal,
) -> RunStats:
    gross = trade_pnl + trade_fees
    returns = _daily_returns(equity)
    years = _year_returns(equity)
    worst = min(years, key=lambda yr: (yr[1], yr[0])) if years else None
    return RunStats(
        metrics=metrics,
        exposure=_mean(exposures),
        turnover=_turnover(notional, equity),
        costs_usd=float(costs),
        gross_pnl_usd=float(gross),
        cost_drag=float(trade_fees) / float(gross) if gross > 0 else None,
        dividends_usd=float(dividends),
        sharpe=_sharpe(returns),
        daily_returns=returns,
        year_returns=years,
        worst_year=worst,
    )


def _run_result_stats(r: RunResult) -> RunStats:
    equity = _equities([(s.date, s.cash_usd, s.equity_usd) for s in r.snapshots])
    exposures = [float(s.equity_usd - s.cash_usd) / float(s.equity_usd) for s in r.snapshots[1:]]
    notional = _ZERO
    costs = _ZERO
    for e in r.events:
        if e.kind == "fill" and e.order.fill_price is not None:
            price = e.order.fill_price
        elif e.kind == "exit" and e.order.exit_price is not None:
            price = e.order.exit_price
        else:
            continue
        notional += price * e.order.shares
        costs += _fee(price, e.order.shares)
    trade_pnl = _ZERO
    trade_fees = _ZERO
    for o in r.closed:
        if o.fill_price is None or o.exit_price is None or o.pnl_usd is None:
            raise ValueError(f"closed order {o.symbol} lacks a fill, an exit or a pnl")
        trade_pnl += o.pnl_usd
        trade_fees += _fee(o.fill_price, o.shares) + _fee(o.exit_price, o.shares)
    return _assemble(run_metrics(r), equity, exposures, notional, costs, trade_pnl, trade_fees, _ZERO)


def _book_metrics(snaps: Sequence[tuple[date, float]], trades: Sequence[Trade]) -> Metrics:
    base = strategy_metrics(snaps, [float(t.pnl_usd) for t in trades])
    counts = {reason: 0 for reason in BOOK_EXIT_REASONS}
    days = 0
    for t in trades:
        if t.exit_reason not in counts:
            raise ValueError(f"trade {t.symbol} has exit_reason {t.exit_reason!r}, not one of {BOOK_EXIT_REASONS}")
        counts[t.exit_reason] += 1
        days += t.days_held
    return replace(
        base,
        avg_days_held=days / len(trades) if trades else None,
        exit_reasons=tuple((reason, counts[reason]) for reason in BOOK_EXIT_REASONS),
    )


def _book_result_stats(r: BookResult) -> RunStats:
    equity = _equities([(s.date, s.cash_usd, s.equity_usd) for s in r.snapshots])
    exposures = [float(s.invested_usd) / float(s.equity_usd) for s in r.snapshots[1:]]
    notional = _ZERO
    fees_by_symbol: dict[str, list[tuple[date, Decimal]]] = {}
    for f in r.fills:
        notional += f.price * f.shares
        fees_by_symbol.setdefault(f.symbol, []).append((f.session_date, f.cost_usd))
    trades = [t for t in r.trades if not t.idle]
    trade_pnl = _ZERO
    trade_fees = _ZERO
    for t in trades:
        trade_pnl += t.pnl_usd
        # An episode's fills are its symbol's fills dated entry_date..exit_date: episodes of one
        # symbol never share a date (no re-entry on an exit session; a forced close needs no bar).
        for d, fee in fees_by_symbol.get(t.symbol, ()):
            if t.entry_date <= d <= t.exit_date:
                trade_fees += fee
    return _assemble(
        _book_metrics(equity, trades), equity, exposures, notional, r.costs_usd, trade_pnl, trade_fees, r.dividends_usd
    )


def run_stats(r: RunResult | BookResult) -> RunStats:
    """``RunStats`` of a ``run_backtest`` or ``run_book`` result (see ``RunStats``)."""
    if isinstance(r, BookResult):
        return _book_result_stats(r)
    if isinstance(r, RunResult):
        return _run_result_stats(r)
    raise TypeError(f"r must be a RunResult or a BookResult, got {type(r).__name__}")
```

**Impact:** new module only. Nothing imports it yet; phase 9's `backtest/dev.py` is its first caller. `run_backtest`, `RunResult` and `metrics` are imported read-only, so the frozen set stays byte-identical.

### Step 2: Create the test file
**File:** `engine/tests/test_book_runner.py:1` (new file)
**Change:** create the whole file below, verbatim. Test inventory (47):

| Group | Tests | Count |
|---|---|---|
| `DESIGN_V0` dispatch | `test_run_rules_design_v0_is_run_backtest[A,A2,B]`, `…_plain_path_is_run_backtest`, `…_ignores_dividends_and_checks_usd_idr`, `test_run_rules_rejects_mismatched_pairings`, `test_run_rules_book_engine_is_run_book` | 7 |
| V0 parity | `test_seeded_market_exercises_every_v0_path[A,A2,B]`, `test_v0_book_replays_run_backtest[A,A2,B × seed 39,4]`, `test_v0_book_rejections_map_to_the_simulators[A,A2,B]`, `test_v0_book_hand_checked_scenario`, `test_v0_book_prepared_equals_plain`, `test_run_stats_agree_on_the_parity_runs[A,B]` | 16 |
| `run_book` wiring | `…_rejects_the_bracket_engine`, `…_type_and_window_checks`, `…_first_snapshot_and_cash`, `test_cadence_follows_is_decision_session[daily,weekly,monthly]`, `test_allocator_sees_history_through_data_date_members_and_held`, `test_prepared_and_plain_book_runs_agree`, `test_idle_residual_target[residual,all-idle,fully-invested]`, `test_idle_needs_a_bar_on_data_date`, `test_allocator_may_not_target_the_idle_symbol`, `test_allocator_never_sees_the_idle_position_as_held`, `test_idle_never_added_on_non_decision_sessions`, `test_bars_routing_and_rejection_accounting`, `test_dividends_routed_from_dividend_map`, `test_dividends_off_routes_nothing`, `test_forced_close_when_bars_end`, `test_run_book_is_deterministic` | 20 |
| `run_stats` | `…_run_result_hand_checked`, `…_book_result_hand_checked`, `…_degenerate_curves`, `…_type_check` | 4 |

The seeded market, verified while planning against today's `run_backtest`:
- **Seed 39, window 2019-10-17 … 2020-07-06.** Under A it gives:
  - exits: 13 TP, 5 SL, 1 gap, 7 time stops and 2 forced closes;
  - rejections: 70 `lt_one_share` and 1 `no_slot`;
  - 57 expired limits.
- **A2 `regime_calm`** gives 8 TP, 4 SL, 1 gap, 7 time, 2 forced and 1 `no_slot`.
- **B with the fake `Linear` model** gives 55 TP, 20 SL, 3 gap, 27 time, 4 forced and 121 `no_slot`.
- **Seed 4** is the secondary parity seed. It has 7 gaps under B, and 170 `no_slot`.
- **Run times:** prepared runs take 0.01–0.07 s each. A plain A run takes 0.6 s.

The hand-checked FixedPicks scenario adds a halt while held, a member leaving the index while held, and a pick for a held symbol.

**Code:**
```python
"""The book runner, the trade-rules dispatch, run statistics and the §5 parity (plan phase 3; R1, R8).

Four groups:

1. ``run_rules(..., DESIGN_V0)`` IS ``run_backtest``: ``==`` results for Strategy A, A2 and B (a
   fake linear Predictor) on seeded synthetic markets, prepared and plain.
2. The V0 parity: ``run_book(PICKS, PicksParams(strategy, params), V0_BOOK)`` replays
   ``run_backtest(strategy, params)`` exactly: the same (date, cash, equity) snapshots, the same
   closed-trade multiset, the same fill multiset and the same positions left open. Seed 39's
   market is checked to exercise every simulator path (TP, SL, gap, time stop, forced close
   when bars end, lt_one_share, no_slot, unfilled limits); the hand-checked FixedPicks scenario
   of tests/test_backtest_runner.py adds a halt while held and a member leaving while held.
3. ``run_book`` wiring with a scripted fake allocator and a recording ``step_book``: cadence,
   no look-ahead, members and held, the idle residual target, bar and dividend routing, forced
   closes, rejection and cost accounting, determinism.
4. ``run_stats`` hand-checked on a small RunResult and a small BookResult, and equal on the two
   sides of the parity.

Simulator arithmetic (``seer_engine.sim``): buy cash ``q(p x n x 1.001)``, sell proceeds
``q(p x n x 0.999)``, fee ``q(p x n x 0.001)``, ``q`` = 4 dp half-up.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from typing import Any

import numpy as np
import pytest
from simkit import D, P, opened
from stratkit import drop_days, hist, session_days, truncate_before
from test_backtest_runner import END as V0_END
from test_backtest_runner import START as V0_START
from test_backtest_runner import TABLE as V0_TABLE
from test_backtest_runner import FixedPicks, scenario_market

from seer_engine import dates
from seer_engine.backtest import book_runner
from seer_engine.backtest.book_runner import (
    BOOK_EXIT_REASONS,
    BookResult,
    run_book,
    run_rules,
    run_stats,
)
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.metrics import run_metrics, strategy_metrics
from seer_engine.backtest.runner import RunResult, run_backtest
from seer_engine.prices import to_decimal
from seer_engine.sim import Event, Snapshot, q
from seer_engine.sim.book import BookSnapshot, Fill, Target, Trade
from seer_engine.sim.book import step_book as real_step_book
from seer_engine.sim.rules import (
    DAILY_SWITCH,
    DAILY_SWITCH_TBILL,
    DESIGN_V0,
    MONTHLY_HOLD,
    V0_BOOK,
    WEEKLY_HOLD,
    is_decision_session,
)
from seer_engine.strategies.a import DESIGN_PARAMS, STRATEGY_A
from seer_engine.strategies.a2 import STRATEGY_A2, A2Params
from seer_engine.strategies.allocator import PICKS, PicksParams
from seer_engine.strategies.b import FEATURE_NAMES, STRATEGY_B, BParams
from seer_engine.strategies.base import History

# =========================================================================== seeded markets
#
# 16 member stocks S00..S15 plus SPY (never a member) on 380 sessions from 2019-01-02. The first
# 200 are warm-up (Strategy A/A2/B lookback); the window is the last 180 sessions,
# 2019-10-17 .. 2020-07-06. Prices span 12 .. 700, so with 20,000,000 IDR at 16000 (1250 USD,
# a 312.5 slot) the dear names are rejected lt_one_share. Seven names stop trading inside the
# window (forced closes when held); two have short halts. Gaps of 3-6 % on ~4 % of opens.

N_SESSIONS = 380
WARMUP = 200
SEED_DAYS = session_days(N_SESSIONS)
START_PRICES = (12.0, 18.0, 25.0, 31.0, 40.0, 48.0, 60.0, 75.0, 90.0, 120.0, 150.0, 200.0, 250.0, 420.0, 700.0, 33.0)
SEED_SYMBOLS = tuple(f"S{i:02d}" for i in range(len(START_PRICES)))
DELIST = {"S01": 240, "S03": 262, "S05": 281, "S07": 301, "S09": 322, "S10": 341, "S12": 360}  # first missing index
HALT = {"S04": (250, 251, 252), "S08": (300, 301)}
SEED_START, SEED_END = SEED_DAYS[WARMUP], SEED_DAYS[-1]
SEED_FX = ((date(2018, 12, 31), Decimal("16000")),)


def _series(rng: np.random.Generator, p0: float, n: int, drift: float, vol: float) -> tuple[np.ndarray, ...]:
    """(open, high, low, close, volume), 2 dp. Draw order is fixed: changing it changes every seed."""
    rets = rng.normal(drift, vol, n)
    close = p0 * np.exp(np.cumsum(rets))
    gaps = rng.normal(0.0, 0.006, n)
    big = rng.random(n) < 0.04
    gaps = np.where(big, rng.choice([-1.0, 1.0], n) * rng.uniform(0.03, 0.06, n), gaps)
    prev = np.concatenate([[p0], close[:-1]])
    open_ = prev * np.exp(gaps)
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.008, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.008, n)))
    volume = np.full(n, 3_000_000.0)
    return np.round(open_, 2), np.round(high, 2), np.round(low, 2), np.round(close, 2), volume


def _history(symbol: str, cols: tuple[np.ndarray, ...], keep: np.ndarray) -> History:
    o, h, lo, c, v = cols
    days = np.array(SEED_DAYS, dtype="datetime64[D]")[keep]
    return History(
        symbol,
        days,
        o[keep].astype(np.float64),
        h[keep].astype(np.float64),
        lo[keep].astype(np.float64),
        c[keep].astype(np.float64),
        v[keep].astype(np.float64),
    )


@lru_cache(maxsize=None)
def seeded_market(seed: int) -> Market:
    rng = np.random.default_rng(seed)
    histories: dict[str, History] = {}
    for symbol, p0 in zip(SEED_SYMBOLS, START_PRICES):
        cols = _series(rng, p0, N_SESSIONS, 0.0015, 0.022)
        keep = np.ones(N_SESSIONS, dtype=bool)
        if symbol in DELIST:
            keep[DELIST[symbol]:] = False
        for k in HALT.get(symbol, ()):
            keep[k] = False
        histories[symbol] = _history(symbol, cols, keep)
    histories["SPY"] = _history("SPY", _series(rng, 300.0, N_SESSIONS, 0.0006, 0.009), np.ones(N_SESSIONS, dtype=bool))
    intervals = tuple((s, date(2010, 1, 4), None) for s in SEED_SYMBOLS)
    return Market(history=dict(sorted(histories.items())), membership=Membership(intervals), fx=SEED_FX)


@dataclass(frozen=True)
class Linear:
    """A fake fitted B model: ``bias + sum_j X[:, j] x weights[j]``, row by row."""

    weights: tuple[float, ...]
    bias: float = 0.0

    def predict(self, X: np.ndarray) -> np.ndarray:
        acc = np.full(X.shape[0], self.bias, dtype=np.float64)
        for j, w in enumerate(self.weights):
            acc = acc + X[:, j] * w
        return acc


B_PARAMS = BParams(Linear(tuple({"ret_1": -1.0, "rsi_2": -0.01}.get(n, 0.0) for n in FEATURE_NAMES), bias=0.3))
STRATEGIES: dict[str, tuple[Any, Any]] = {
    "A": (STRATEGY_A, DESIGN_PARAMS),
    "A2": (STRATEGY_A2, A2Params(variant="regime_calm")),
    "B": (STRATEGY_B, B_PARAMS),
}


@lru_cache(maxsize=None)
def strategy_prepared(seed: int, key: str) -> Any:
    return STRATEGIES[key][0].prepare(seeded_market(seed).history)


@lru_cache(maxsize=None)
def picks_prepared(seed: int) -> Any:
    return PICKS.prepare(seeded_market(seed).history)


@lru_cache(maxsize=None)
def sim_run(seed: int, key: str) -> RunResult:
    strategy, params = STRATEGIES[key]
    return run_backtest(
        seeded_market(seed), strategy, params, SEED_START, SEED_END, prepared=strategy_prepared(seed, key)
    )


@lru_cache(maxsize=None)
def book_run(seed: int, key: str) -> BookResult:
    strategy, params = STRATEGIES[key]
    return run_book(
        seeded_market(seed),
        PICKS,
        PicksParams(strategy, params),
        V0_BOOK,
        SEED_START,
        SEED_END,
        prepared=picks_prepared(seed),
    )


# --------------------------------------------------------------------------- comparison keys

SIM_REASON = {
    "tp": ("tp", False),
    "sl": ("sl", False),
    "gap": ("gap", False),
    "time": ("time", False),
    "forced": ("time", True),
}


def sim_snaps(r: RunResult) -> list[tuple[date, Decimal, Decimal]]:
    return [(s.date, s.cash_usd, s.equity_usd) for s in r.snapshots]


def book_snaps(r: BookResult) -> list[tuple[date, Decimal, Decimal]]:
    return [(s.date, s.cash_usd, s.equity_usd) for s in r.snapshots]


def sim_trades(r: RunResult) -> Counter[tuple[Any, ...]]:
    return Counter(
        (
            e.order.symbol,
            e.order.fill_date,
            e.order.fill_price,
            e.order.exit_date,
            e.order.exit_price,
            e.order.exit_reason,
            e.forced,
            e.order.pnl_usd,
            e.order.days_held,
        )
        for e in r.events
        if e.kind == "exit"
    )


def book_trades(r: BookResult) -> Counter[tuple[Any, ...]]:
    out: Counter[tuple[Any, ...]] = Counter()
    for t in r.trades:
        reason, forced = SIM_REASON.get(t.exit_reason, (t.exit_reason, None))
        out[(t.symbol, t.entry_date, t.entry_price, t.exit_date, t.exit_price, reason, forced, t.pnl_usd, t.days_held)] += 1
    return out


def sim_fills(r: RunResult) -> Counter[tuple[Any, ...]]:
    out: Counter[tuple[Any, ...]] = Counter()
    for e in r.events:
        if e.kind == "fill":
            out[(e.session_date, e.order.symbol, "buy", Decimal(e.order.shares), e.order.fill_price, e.cash_usd)] += 1
        elif e.kind == "exit":
            out[(e.session_date, e.order.symbol, "sell", Decimal(e.order.shares), e.order.exit_price, e.cash_usd)] += 1
    return out


def book_fills(r: BookResult) -> Counter[tuple[Any, ...]]:
    return Counter((f.session_date, f.symbol, f.side, f.shares, f.price, f.cash_usd) for f in r.fills)


def sim_open(r: RunResult) -> list[tuple[Any, ...]]:
    return sorted((o.symbol, Decimal(o.shares), o.fill_date, o.fill_price, o.days_held) for o in r.open_at_end)


def book_open(r: BookResult) -> list[tuple[Any, ...]]:
    return sorted((p.symbol, p.shares, p.entry_date, p.entry_price, p.days_held) for p in r.open_at_end)


def sim_paths(r: RunResult) -> tuple[Counter[tuple[Any, bool]], dict[str, int], int]:
    exits = Counter((e.order.exit_reason, e.forced) for e in r.events if e.kind == "exit")
    expired = sum(1 for e in r.events if e.kind == "expire")
    return exits, dict(r.rejections), expired


# =========================================================================== 1. DESIGN_V0 dispatch


@pytest.mark.parametrize("key", ["A", "A2", "B"])
def test_run_rules_design_v0_is_run_backtest(key):
    market = seeded_market(39)
    strategy, params = STRATEGIES[key]
    prepared = strategy_prepared(39, key)
    got = run_rules(market, strategy, params, DESIGN_V0, SEED_START, SEED_END, prepared=prepared)
    assert isinstance(got, RunResult)
    assert got == run_backtest(market, strategy, params, SEED_START, SEED_END, prepared=prepared)
    assert got == sim_run(39, key)


def test_run_rules_design_v0_plain_path_is_run_backtest():
    market = seeded_market(39)
    got = run_rules(market, STRATEGY_A, DESIGN_PARAMS, DESIGN_V0, SEED_START, SEED_END)
    assert got == run_backtest(market, STRATEGY_A, DESIGN_PARAMS, SEED_START, SEED_END)
    assert got == sim_run(39, "A")  # and the prepared path agrees (the Strategy contract)


def test_run_rules_design_v0_ignores_dividends_and_checks_usd_idr():
    market = seeded_market(39)
    prepared = strategy_prepared(39, "A")
    divs = {s: {SEED_DAYS[WARMUP + k]: Decimal("0.5") for k in range(0, 180, 7)} for s in SEED_SYMBOLS}
    got = run_rules(
        market, STRATEGY_A, DESIGN_PARAMS, DESIGN_V0, SEED_START, SEED_END,
        prepared=prepared, dividends=divs, usd_idr=Decimal("16000"),
    )
    assert got == sim_run(39, "A")
    with pytest.raises(ValueError, match="usd_idr_on"):
        run_rules(market, STRATEGY_A, DESIGN_PARAMS, DESIGN_V0, SEED_START, SEED_END, usd_idr=Decimal("15000"))


def test_run_rules_rejects_mismatched_pairings():
    market = wiring_market()
    with pytest.raises(TypeError, match="Strategy"):
        run_rules(market, PICKS, PicksParams(STRATEGY_A, DESIGN_PARAMS), DESIGN_V0, W_START, W_END)
    with pytest.raises(TypeError, match="Allocator"):
        run_rules(market, STRATEGY_A, DESIGN_PARAMS, V0_BOOK, W_START, W_END)
    with pytest.raises(TypeError, match="Allocator"):
        run_rules(market, STRATEGY_A, DESIGN_PARAMS, DAILY_SWITCH, W_START, W_END)
    with pytest.raises(TypeError, match="TradeRules"):
        run_rules(market, STRATEGY_A, DESIGN_PARAMS, "design-v0", W_START, W_END)


def test_run_rules_book_engine_is_run_book():
    market = wiring_market()
    divs = {"AAA": {D("2025-02-27"): Decimal("0.25")}}
    spec = (("AAA", "0.5"),)
    got = run_rules(market, Scripted(spec), None, DAILY_SWITCH, W_START, W_END, dividends=divs, usd_idr=Decimal("8000"))
    want = run_book(market, Scripted(spec), None, DAILY_SWITCH, W_START, W_END, dividends=divs, usd_idr=Decimal("8000"))
    assert isinstance(got, BookResult)
    assert got == want
    assert got.initial_cash == P("2500")


# =========================================================================== 2. the V0 parity


@pytest.mark.parametrize("key", ["A", "A2", "B"])
def test_seeded_market_exercises_every_v0_path(key):
    exits, rejections, expired = sim_paths(sim_run(39, key))
    for path in (("tp", False), ("sl", False), ("gap", False), ("time", False), ("time", True)):
        assert exits[path] >= 1, f"seed 39 / {key} never exits by {path}"
    assert rejections.get("no_slot", 0) >= 1
    assert rejections.get("lt_one_share", 0) >= 1
    assert expired >= 1


@pytest.mark.parametrize("seed", [39, 4])
@pytest.mark.parametrize("key", ["A", "A2", "B"])
def test_v0_book_replays_run_backtest(key, seed):
    sim, book = sim_run(seed, key), book_run(seed, key)
    assert book.allocator_id == "PICKS"
    assert book.rules == V0_BOOK
    assert (book.start, book.end) == (sim.start, sim.end)
    assert (book.usd_idr, book.initial_cash) == (sim.usd_idr, sim.initial_cash)
    assert book_snaps(book) == sim_snaps(sim)
    assert book_trades(book) == sim_trades(sim)
    assert book_fills(book) == sim_fills(sim)
    assert book_open(book) == sim_open(sim)
    assert book.dividends_usd == 0
    assert all(not t.idle for t in book.trades)


@pytest.mark.parametrize("key", ["A", "A2", "B"])
def test_v0_book_rejections_map_to_the_simulators(key):
    sim, book = sim_run(39, key), book_run(39, key)
    _, sim_rej, expired = sim_paths(sim)
    got = dict(book.rejections)
    assert set(got) <= {"no_slot", "too_small", "unfilled", "no_bar"}
    assert got.get("no_slot", 0) == sim_rej.get("no_slot", 0)
    assert got.get("too_small", 0) == sim_rej.get("lt_one_share", 0)
    assert got.get("unfilled", 0) + got.get("no_bar", 0) == expired
    # Strategy picks for a held symbol are dropped by PICKS, never placed: the simulator's
    # "held" rejections have no book counterpart.
    assert "held" not in got


def test_v0_book_hand_checked_scenario():
    """tests/test_backtest_runner.py's hand-checked scenario, replayed by the book engine.

    It adds what seed 39 lacks: a halt while held (DDD, 03-11..03-13), a member leaving the
    index while held (CCC), a pick of a held symbol (BBB on 03-06) and a forced close at the
    mark (BBB on 03-06). Every number below is the hand-checked one from that file.
    """
    market = scenario_market()
    sim = run_backtest(market, FixedPicks(V0_TABLE), None, V0_START, V0_END)
    book = run_book(market, PICKS, PicksParams(FixedPicks(V0_TABLE), None), V0_BOOK, V0_START, V0_END)
    assert book_snaps(book) == sim_snaps(sim)
    assert book.snapshots[0] == BookSnapshot(D("2025-03-03"), P("1250"), P("1250"), P("0"))
    assert book.snapshots[-1] == BookSnapshot(D("2025-03-14"), P("940.5647"), P("1286.1647"), P("345.6"))  # 64 x 5.4
    want = Counter({
        ("AAA", D("2025-03-04"), P("10"), D("2025-03-05"), P("11"), "tp", False, P("30.3490"), 2): 1,
        ("BBB", D("2025-03-04"), P("19.5"), D("2025-03-06"), P("20.2"), "time", True, P("9.9045"), 3): 1,
        ("CCC", D("2025-03-06"), P("49.8"), D("2025-03-10"), P("45"), "sl", False, P("-29.3688"), 3): 1,
    })
    assert book_trades(book) == want == sim_trades(sim)
    assert book_fills(book) == sim_fills(sim)
    assert book_open(book) == [("DDD", Decimal(64), D("2025-03-10"), P("5"), 5)] == sim_open(sim)
    got = dict(book.rejections)
    assert got.get("unfilled") == 1  # DDD on 03-07: low 5.05 is not < 5
    # EEE (no bars at all, too dear for one share) is "too_small" if PICKS offers it, or never
    # offered if PICKS drops symbols without a bar on data_date (the Allocator contract).
    assert set(got) <= {"too_small", "unfilled"}


def test_v0_book_prepared_equals_plain():
    strategy, params = STRATEGIES["A"]
    plain = run_book(seeded_market(39), PICKS, PicksParams(strategy, params), V0_BOOK, SEED_START, SEED_END)
    assert plain == book_run(39, "A")


@pytest.mark.parametrize("key", ["A", "B"])
def test_run_stats_agree_on_the_parity_runs(key):
    rs, bs = run_stats(sim_run(39, key)), run_stats(book_run(39, key))
    rm, bm = rs.metrics, bs.metrics
    assert (bm.total_return, bm.max_drawdown, bm.months, bm.cagr) == (rm.total_return, rm.max_drawdown, rm.months, rm.cagr)
    assert (bm.trades, bm.win_rate, bm.avg_days_held) == (rm.trades, rm.win_rate, rm.avg_days_held)
    # P/L sums run in each engine's exit order (slot vs symbol within a session): equal to rounding.
    assert bm.profit_factor == pytest.approx(rm.profit_factor, rel=1e-12)
    sim_reasons, book_reasons = dict(rm.exit_reasons), dict(bm.exit_reasons)
    forced = sim_paths(sim_run(39, key))[0][("time", True)]
    assert [r for r, _ in bm.exit_reasons] == list(BOOK_EXIT_REASONS)
    assert book_reasons["forced"] == forced
    assert book_reasons["time"] == sim_reasons["time"] - forced
    assert book_reasons["signal"] == 0
    assert all(book_reasons[r] == sim_reasons[r] for r in ("tp", "sl", "gap"))
    for name in ("exposure", "turnover", "costs_usd", "gross_pnl_usd", "cost_drag", "dividends_usd",
                 "sharpe", "daily_returns", "year_returns", "worst_year"):
        assert getattr(bs, name) == getattr(rs, name), name
    assert [y for y, _ in rs.year_returns] == [2019, 2020]


# =========================================================================== 3. run_book wiring
#
# Sessions 2025-02-14 .. 2025-03-14 (02-17 is a holiday); the window is 02-24 .. 03-14, 15
# sessions. AAA closes 10.0 + 0.1 t, BBB 20.0 + 0.2 t, BIL 100 flat (spread 0.05), CCC 30 flat;
# open = close, high/low = close +/- spread (stratkit.hist). USD/IDR 16000 -> 1250.0000 USD.
# AAA, BBB and CCC are members; BIL is not.

W_DAYS = dates.sessions(D("2025-02-14"), D("2025-03-14"))
W_START, W_END = D("2025-02-24"), D("2025-03-14")
W_FX = ((D("2025-02-13"), Decimal("16000")),)
W_MEMBERS = (
    ("AAA", D("2020-01-02"), None),
    ("BBB", D("2020-01-02"), None),
    ("CCC", D("2020-01-02"), None),
)


def wiring_market(
    *, bil_from: date | None = None, aaa_until: date | None = None, ccc_missing: tuple[date, ...] = ()
) -> Market:
    n = len(W_DAYS)
    aaa = hist("AAA", [round(10.0 + 0.1 * t, 2) for t in range(n)], days=W_DAYS)
    bbb = hist("BBB", [round(20.0 + 0.2 * t, 2) for t in range(n)], days=W_DAYS)
    bil = hist("BIL", [100.0] * n, days=W_DAYS, spread=0.05)
    ccc = hist("CCC", [30.0] * n, days=W_DAYS)
    if aaa_until is not None:
        aaa = truncate_before(aaa, dates.next_session(aaa_until))
    if bil_from is not None:
        bil = drop_days(bil, [d for d in W_DAYS if d < bil_from])
    if ccc_missing:
        ccc = drop_days(ccc, ccc_missing)
    return Market(
        history={"AAA": aaa, "BBB": bbb, "BIL": bil, "CCC": ccc},
        membership=Membership(W_MEMBERS),
        fx=W_FX,
    )


Spec = tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Call:
    path: str
    data_date: date
    members: frozenset[str]
    held: frozenset[str]
    seen: date | None  # latest bar date in the histories handed over (plain path only)


class Scripted:
    """A fake Allocator: fixed ``(symbol, weight)`` targets per data_date (``default`` otherwise),
    each priced at its close on data_date. A symbol without a bar dated data_date is skipped
    (never a new target). Records every call."""

    id = "SCRIPTED"

    def __init__(self, default: Spec = (), table: Mapping[date, Spec] | None = None):
        self.default = default
        self.table = dict(table or {})
        self.calls: list[Call] = []

    def lookback(self, params: Any) -> int:
        return 1

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ()

    def holds(self, params: Any) -> tuple[str, ...]:
        return ()

    def uses_members(self, params: Any) -> bool:
        return True

    def _targets(self, closes: Mapping[str, float], data_date: date) -> tuple[Target, ...]:
        out = []
        for symbol, weight in self.table.get(data_date, self.default):
            if symbol in closes:
                out.append(Target(symbol=symbol, weight=Decimal(weight), last=to_decimal(closes[symbol])))
        return tuple(out)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        seen = max(h.last_date() for h in history.values() if len(h))
        self.calls.append(Call("plain", data_date, frozenset(members), held, seen))
        closes = {s: float(h.close[-1]) for s, h in history.items() if len(h) and h.last_date() == data_date}
        return self._targets(closes, data_date)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return dict(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        self.calls.append(Call("prepared", data_date, frozenset(members), held, None))
        closes: dict[str, float] = {}
        for s, h in prepared.items():
            i = h.index_of(data_date)
            if i is not None:
                closes[s] = float(h.close[i])
        return self._targets(closes, data_date)


@dataclass(frozen=True)
class StepCall:
    session: date
    bar_symbols: tuple[str, ...]
    targets: tuple[Target, ...] | None
    dividends: dict[str, Decimal]
    idle_symbol_ok: bool


@pytest.fixture
def steps(monkeypatch):
    """Every ``step_book`` call ``run_book`` makes, recorded, then run for real."""
    calls: list[StepCall] = []

    def spy(book, session, bars, targets, rules, dividends, *, idle_symbol_ok):
        calls.append(StepCall(session, tuple(sorted(bars)), targets, dict(dividends), idle_symbol_ok))
        return real_step_book(book, session, bars, targets, rules, dividends, idle_symbol_ok=idle_symbol_ok)

    monkeypatch.setattr(book_runner, "step_book", spy)
    return calls


def _held_shares(r: BookResult, symbol: str, before: date) -> Decimal:
    total = Decimal(0)
    for f in r.fills:
        if f.symbol == symbol and f.session_date < before:
            total += f.shares if f.side == "buy" else -f.shares
    return total


def test_run_book_rejects_the_bracket_engine():
    with pytest.raises(ValueError, match="run_rules"):
        run_book(wiring_market(), Scripted(), None, DESIGN_V0, W_START, W_END)


def test_run_book_type_and_window_checks():
    market = wiring_market()
    with pytest.raises(TypeError, match="Market"):
        run_book("market", Scripted(), None, DAILY_SWITCH, W_START, W_END)
    with pytest.raises(TypeError, match="Allocator"):
        run_book(market, STRATEGY_A, DESIGN_PARAMS, DAILY_SWITCH, W_START, W_END)
    with pytest.raises(TypeError, match="TradeRules"):
        run_book(market, Scripted(), None, "daily-switch", W_START, W_END)
    with pytest.raises(TypeError, match="Mapping"):
        run_book(market, Scripted(), None, DAILY_SWITCH, W_START, W_END, dividends=[("AAA", 1)])
    with pytest.raises(TypeError, match="date"):
        run_book(market, Scripted(), None, DAILY_SWITCH, datetime(2025, 2, 24), W_END)
    with pytest.raises(ValueError, match="NYSE session"):
        run_book(market, Scripted(), None, DAILY_SWITCH, D("2025-02-23"), W_END)
    with pytest.raises(ValueError, match="before start"):
        run_book(market, Scripted(), None, DAILY_SWITCH, W_END, W_START)


def test_run_book_first_snapshot_and_cash():
    market = wiring_market()
    r = run_book(market, Scripted(), None, DAILY_SWITCH, W_START, W_END)
    assert (r.allocator_id, r.params, r.rules, r.start, r.end) == ("SCRIPTED", None, DAILY_SWITCH, W_START, W_END)
    assert (r.usd_idr, r.initial_cash) == (Decimal("16000"), P("1250"))
    assert r.snapshots[0] == BookSnapshot(D("2025-02-21"), P("1250"), P("1250"), P("0"))
    assert [s.date for s in r.snapshots[1:]] == dates.sessions(W_START, W_END)
    assert len(r.snapshots) == 16
    # Nothing targeted: nothing traded, cash flat.
    assert r.fills == () and r.trades == () and r.open_at_end == () and r.rejections == ()
    assert all(s == BookSnapshot(s.date, P("1250"), P("1250"), P("0")) for s in r.snapshots)
    other = run_book(market, Scripted(), None, DAILY_SWITCH, W_START, W_END, usd_idr=Decimal("8000"))
    assert (other.usd_idr, other.initial_cash) == (Decimal("8000"), P("2500"))
    assert other.snapshots[0] == BookSnapshot(D("2025-02-21"), P("2500"), P("2500"), P("0"))


@pytest.mark.parametrize(
    ("rules", "data_dates"),
    [
        (DAILY_SWITCH, [dates.prev_session(s) for s in dates.sessions(W_START, W_END)]),
        (WEEKLY_HOLD, [D("2025-02-21"), D("2025-02-28"), D("2025-03-07")]),   # Mondays 02-24, 03-03, 03-10
        (MONTHLY_HOLD, [D("2025-02-28")]),                                     # 03-03, first session of March
    ],
    ids=["daily", "weekly", "monthly"],
)
def test_cadence_follows_is_decision_session(steps, rules, data_dates):
    alloc = Scripted((("AAA", "0.5"),))
    run_book(wiring_market(), alloc, None, rules, W_START, W_END)
    decision = [s for s in dates.sessions(W_START, W_END) if is_decision_session(rules, s)]
    assert [c.data_date for c in alloc.calls] == data_dates == [dates.prev_session(s) for s in decision]
    assert [c.session for c in steps] == dates.sessions(W_START, W_END)
    for c in steps:
        assert (c.targets is not None) == (c.session in decision), c.session


def test_allocator_sees_history_through_data_date_members_and_held():
    market = wiring_market()
    alloc = Scripted((("AAA", "0.5"),))
    r = run_book(market, alloc, None, DAILY_SWITCH, W_START, W_END)
    assert [c.path for c in alloc.calls] == ["plain"] * 15
    for c in alloc.calls:
        assert c.seen == c.data_date  # no bar after data_date reaches the allocator
        assert c.members == market.membership.members_on(c.data_date) == frozenset({"AAA", "BBB", "CCC"})
    # AAA is bought at 02-24's open (open_limit at last x 1.02 fills) and kept: held from then on.
    assert alloc.calls[0].held == frozenset()
    assert all(c.held == frozenset({"AAA"}) for c in alloc.calls[1:])
    assert [p.symbol for p in r.open_at_end] == ["AAA"]


def test_prepared_and_plain_book_runs_agree():
    market = wiring_market()
    spec = (("AAA", "0.4"), ("BBB", "0.4"))
    plain_alloc, prep_alloc = Scripted(spec), Scripted(spec)
    plain = run_book(market, plain_alloc, None, DAILY_SWITCH_TBILL, W_START, W_END)
    prepared = run_book(
        market, prep_alloc, None, DAILY_SWITCH_TBILL, W_START, W_END, prepared=prep_alloc.prepare(market.history)
    )
    assert plain == prepared
    assert {c.path for c in plain_alloc.calls} == {"plain"}
    assert {c.path for c in prep_alloc.calls} == {"prepared"}
    assert [c.data_date for c in plain_alloc.calls] == [c.data_date for c in prep_alloc.calls]


@pytest.mark.parametrize(
    ("spec", "idle_weight"),
    [((("AAA", "0.6"),), "0.4"), ((), "1"), ((("AAA", "0.5"), ("BBB", "0.5")), None)],
    ids=["residual", "all-idle", "fully-invested"],
)
def test_idle_residual_target(steps, spec, idle_weight):
    run_book(wiring_market(), Scripted(spec), None, DAILY_SWITCH_TBILL, W_START, D("2025-02-28"))
    assert len(steps) == 5
    for c in steps:
        assert c.targets is not None
        assert [(t.symbol, t.weight) for t in c.targets[: len(spec)]] == [(s, Decimal(w)) for s, w in spec]
        if idle_weight is None:
            assert len(c.targets) == len(spec)
            assert c.idle_symbol_ok is False
        else:
            assert len(c.targets) == len(spec) + 1
            assert c.targets[-1] == Target(symbol="BIL", weight=Decimal(idle_weight), last=P("100"))
            assert c.idle_symbol_ok is True
            assert "BIL" in c.bar_symbols


def test_idle_needs_a_bar_on_data_date(steps):
    # BIL trades from 02-26: data dates 02-21, 02-24, 02-25 have no BIL bar, 02-26 and 02-27 do.
    run_book(wiring_market(bil_from=D("2025-02-26")), Scripted((("AAA", "0.5"),)), None, DAILY_SWITCH_TBILL,
             W_START, D("2025-02-28"))
    with_idle = [c.session for c in steps if c.targets and c.targets[-1].symbol == "BIL"]
    assert with_idle == [D("2025-02-27"), D("2025-02-28")]
    assert [c.idle_symbol_ok for c in steps] == [False, False, False, True, True]


def test_allocator_may_not_target_the_idle_symbol():
    with pytest.raises(ValueError, match="idle symbol BIL"):
        run_book(wiring_market(), Scripted((("BIL", "0.5"),)), None, DAILY_SWITCH_TBILL, W_START, W_END)


def test_allocator_never_sees_the_idle_position_as_held():
    # D-J: BIL (the idle instrument) is really held from 02-24, yet no allocator call sees it.
    alloc = Scripted((("AAA", "0.5"),))
    r = run_book(wiring_market(), alloc, None, DAILY_SWITCH_TBILL, W_START, W_END)
    assert "BIL" in {p.symbol for p in r.open_at_end}
    assert all("BIL" not in c.held for c in alloc.calls)
    assert all(c.held == frozenset({"AAA"}) for c in alloc.calls[1:])


def test_idle_never_added_on_non_decision_sessions(steps):
    weekly_tbill = replace(WEEKLY_HOLD, id="weekly-hold-tbill", idle_symbol="BIL")
    run_book(wiring_market(), Scripted((("AAA", "0.5"),)), None, weekly_tbill, W_START, D("2025-03-07"))
    for c in steps:
        if c.session in (D("2025-02-24"), D("2025-03-03")):
            assert c.targets is not None and c.targets[-1].symbol == "BIL" and c.idle_symbol_ok is True
        else:
            assert c.targets is None and c.idle_symbol_ok is False


def test_bars_routing_and_rejection_accounting(steps):
    # CCC is targeted for 03-04 only and has no bar that day: "no_bar", never held.
    market = wiring_market(ccc_missing=(D("2025-03-04"),))
    alloc = Scripted((("AAA", "0.5"),), table={D("2025-03-03"): (("AAA", "0.5"), ("CCC", "0.2"))})
    r = run_book(market, alloc, None, DAILY_SWITCH, W_START, W_END)
    on_0304 = next(c for c in steps if c.session == D("2025-03-04"))
    assert [t.symbol for t in on_0304.targets] == ["AAA", "CCC"]
    assert all(c.bar_symbols == ("AAA",) for c in steps)  # held or targeted, with a bar on S
    assert r.rejections == (("no_bar", 1),)
    assert r.costs_usd == sum((f.cost_usd for f in r.fills), Decimal(0))
    assert r.dividends_usd == 0


def test_dividends_routed_from_dividend_map(steps):
    divs = {
        "AAA": {D("2025-02-24"): Decimal("0.75"), D("2025-02-27"): Decimal("0.25")},  # 02-24: not held at night
        "BBB": {D("2025-02-27"): Decimal("1")},                                     # never held
        "ZZZ": {D("2025-02-26"): Decimal("2")},                                     # not in the market
    }
    r = run_book(wiring_market(), Scripted((("AAA", "0.5"),)), None, DAILY_SWITCH, W_START, D("2025-03-03"),
                 dividends=divs)
    for c in steps:
        assert c.dividends == ({"AAA": Decimal("0.25")} if c.session == D("2025-02-27") else {}), c.session
    shares = _held_shares(r, "AAA", D("2025-02-27"))
    assert shares > 0
    assert r.dividends_usd == q(shares * Decimal("0.25"))


def test_dividends_off_routes_nothing(steps):
    no_divs = replace(DAILY_SWITCH, id="daily-switch-nodiv", dividends=False)
    divs = {"AAA": {D("2025-02-27"): Decimal("0.25")}}
    r = run_book(wiring_market(), Scripted((("AAA", "0.5"),)), None, no_divs, W_START, D("2025-03-03"),
                 dividends=divs)
    assert all(c.dividends == {} for c in steps)
    assert r.dividends_usd == 0


def test_forced_close_when_bars_end(steps):
    # AAA's last bar is 03-05; it is held (and still targeted) on 03-06, so it is force-closed at
    # its 03-05 close right after 03-06's step, and 03-06's snapshot is replaced.
    market = wiring_market(aaa_until=D("2025-03-05"))
    end = D("2025-03-06")
    r = run_book(market, Scripted((("AAA", "0.3"), ("BBB", "0.3"))), None, DAILY_SWITCH_TBILL, W_START, end)
    assert [t.symbol for t in steps[-1].targets] == ["AAA", "BBB", "BIL"]
    assert "AAA" not in steps[-1].bar_symbols
    forced = [t for t in r.trades if t.exit_reason == "forced"]
    assert len(forced) == 1
    aaa = forced[0]
    mark = market.bar("AAA", D("2025-03-05")).close
    assert (aaa.symbol, aaa.exit_date, aaa.exit_price, aaa.idle) == ("AAA", end, mark, False)
    sells = [f for f in r.fills if f.symbol == "AAA" and f.side == "sell"]
    assert [(f.session_date, f.price, f.reason) for f in sells] == [(end, mark, "forced")]
    assert sorted(p.symbol for p in r.open_at_end) == ["BBB", "BIL"]
    last = r.snapshots[-1]
    assert last.date == end
    held_value = sum((p.shares * p.mark for p in r.open_at_end), Decimal(0))
    assert last.equity_usd == q(last.cash_usd + held_value)
    bbb = next(p for p in r.open_at_end if p.symbol == "BBB")
    assert last.invested_usd == q(bbb.shares * bbb.mark)  # BIL is idle: excluded


def test_run_book_is_deterministic():
    divs = {"AAA": {D("2025-02-27"): Decimal("0.25")}, "BIL": {D("2025-03-03"): Decimal("0.1")}}
    spec = (("AAA", "0.4"), ("BBB", "0.3"))
    one = run_book(wiring_market(), Scripted(spec), None, DAILY_SWITCH_TBILL, W_START, W_END, dividends=divs)
    two = run_book(wiring_market(), Scripted(spec), None, DAILY_SWITCH_TBILL, W_START, W_END, dividends=divs)
    assert one == two


# =========================================================================== 4. run_stats


def _snap(d: str, cash: str, equity: str) -> Snapshot:
    return Snapshot(D(d), P(cash), P(equity))


def hand_run_result() -> RunResult:
    """50 AAA bought at 10 on 2024-12-31 (cash 500.5, fee 0.5), marked 10.5; sold at TP 12 on
    2025-01-02 (proceeds 599.4, fee 0.6, pnl 98.9); flat on 2025-01-03."""
    filled = opened("AAA", "2024-12-31", "10", "12", "9", 50, 1)
    closed = replace(
        filled, status="closed", days_held=2, exit_date=D("2025-01-02"), exit_price=P("12"),
        exit_reason="tp", pnl_usd=P("98.9"),
    )
    return RunResult(
        strategy_id="HAND",
        params=None,
        start=D("2024-12-31"),
        end=D("2025-01-03"),
        usd_idr=Decimal("16000"),
        initial_cash=P("1000"),
        snapshots=(
            _snap("2024-12-30", "1000", "1000"),
            _snap("2024-12-31", "499.5", "1024.5"),
            _snap("2025-01-02", "1098.9", "1098.9"),
            _snap("2025-01-03", "1098.9", "1098.9"),
        ),
        events=(
            Event(D("2024-12-31"), "fill", filled, cash_usd=P("-500.5")),
            Event(D("2025-01-02"), "exit", closed, cash_usd=P("599.4")),
        ),
        closed=(closed,),
        open_at_end=(),
        rejections=(),
    )


def hand_book_result() -> BookResult:
    """2024-12-31: buy 40 AAA at 10 (400.4, fee 0.4) and 5 BIL (idle) at 100 (500.5, fee 0.5);
    marks AAA 11, BIL 100 -> cash 99.1, invested 440, equity 1039.1.
    2025-01-02: AAA dividend 0.5 x 40 = 20; AAA signal-sold at 12 (479.52, fee 0.48): episode
    pnl 479.52 + 20 - 400.4 = 99.12 -> cash 598.62, equity 1098.62.
    2025-01-03: BIL sold at 90 (449.55, fee 0.45): idle episode pnl -50.95 -> cash = equity 1048.17."""
    d0, d1, d2, d3 = D("2024-12-30"), D("2024-12-31"), D("2025-01-02"), D("2025-01-03")
    fills = (
        Fill(session_date=d1, symbol="AAA", side="buy", shares=Decimal("40"), price=P("10"),
             cash_usd=P("-400.4"), cost_usd=P("0.4"), reason="entry"),
        Fill(session_date=d1, symbol="BIL", side="buy", shares=Decimal("5"), price=P("100"),
             cash_usd=P("-500.5"), cost_usd=P("0.5"), reason="entry"),
        Fill(session_date=d2, symbol="AAA", side="sell", shares=Decimal("40"), price=P("12"),
             cash_usd=P("479.52"), cost_usd=P("0.48"), reason="signal"),
        Fill(session_date=d3, symbol="BIL", side="sell", shares=Decimal("5"), price=P("90"),
             cash_usd=P("449.55"), cost_usd=P("0.45"), reason="signal"),
    )
    trades = (
        Trade(symbol="AAA", entry_date=d1, exit_date=d2, entry_price=P("10"), exit_price=P("12"), days_held=1,
              cost_usd=P("400.4"), income_usd=P("499.52"), pnl_usd=P("99.12"), exit_reason="signal", idle=False),
        Trade(symbol="BIL", entry_date=d1, exit_date=d3, entry_price=P("100"), exit_price=P("90"), days_held=2,
              cost_usd=P("500.5"), income_usd=P("449.55"), pnl_usd=P("-50.95"), exit_reason="signal", idle=True),
    )
    return BookResult(
        allocator_id="SCRIPTED",
        params=None,
        rules=DAILY_SWITCH_TBILL,
        start=d1,
        end=d3,
        usd_idr=Decimal("16000"),
        initial_cash=P("1000"),
        snapshots=(
            BookSnapshot(d0, P("1000"), P("1000"), P("0")),
            BookSnapshot(d1, P("99.1"), P("1039.1"), P("440")),
            BookSnapshot(d2, P("598.62"), P("1098.62"), P("0")),
            BookSnapshot(d3, P("1048.17"), P("1048.17"), P("0")),
        ),
        fills=fills,
        trades=trades,
        open_at_end=(),
        dividends_usd=P("20"),
        costs_usd=P("1.83"),
        rejections=(),
    )


def _hand_sharpe(rets: list[float]) -> float:
    m = (rets[0] + rets[1] + rets[2]) / 3
    var = ((rets[0] - m) ** 2 + (rets[1] - m) ** 2 + (rets[2] - m) ** 2) / 3
    return m / math.sqrt(var) * math.sqrt(252)


def test_run_stats_run_result_hand_checked():
    r = hand_run_result()
    s = run_stats(r)
    assert s.metrics == run_metrics(r)
    assert s.exposure == pytest.approx((525.0 / 1024.5 + 0.0 + 0.0) / 3)              # (equity - cash) / equity
    assert s.turnover == pytest.approx(1100.0 / ((1024.5 + 1098.9 + 1098.9) / 3) / (4 / 365.25))  # 500 + 600
    assert s.costs_usd == pytest.approx(1.1)
    assert s.gross_pnl_usd == pytest.approx(100.0)                                    # 98.9 + 0.5 + 0.6
    assert s.cost_drag == pytest.approx(0.011)
    assert s.dividends_usd == 0.0
    rets = [1024.5 / 1000.0 - 1.0, 1098.9 / 1024.5 - 1.0, 0.0]
    assert list(s.daily_returns) == pytest.approx(rets)
    assert s.sharpe == pytest.approx(_hand_sharpe(rets))
    assert [y for y, _ in s.year_returns] == [2024, 2025]
    assert [v for _, v in s.year_returns] == pytest.approx([0.0245, 1098.9 / 1024.5 - 1.0])
    assert s.worst_year[0] == 2024 and s.worst_year[1] == pytest.approx(0.0245)


def test_run_stats_book_result_hand_checked():
    r = hand_book_result()
    s = run_stats(r)
    snaps = [(D("2024-12-30"), 1000.0), (D("2024-12-31"), 1039.1), (D("2025-01-02"), 1098.62), (D("2025-01-03"), 1048.17)]
    assert s.metrics == replace(
        strategy_metrics(snaps, [99.12]),                                             # the idle BIL episode is not a trade
        avg_days_held=1.0,
        exit_reasons=(("tp", 0), ("sl", 0), ("time", 0), ("gap", 0), ("signal", 1), ("forced", 0)),
    )
    assert s.exposure == pytest.approx((440.0 / 1039.1 + 0.0 + 0.0) / 3)               # BIL excluded
    assert s.turnover == pytest.approx(1830.0 / ((1039.1 + 1098.62 + 1048.17) / 3) / (4 / 365.25))  # idle fills count
    assert s.costs_usd == pytest.approx(1.83)
    assert s.gross_pnl_usd == pytest.approx(100.0)                                    # 99.12 + 0.4 + 0.48
    assert s.cost_drag == pytest.approx(0.0088)
    assert s.dividends_usd == pytest.approx(20.0)
    rets = [1039.1 / 1000.0 - 1.0, 1098.62 / 1039.1 - 1.0, 1048.17 / 1098.62 - 1.0]
    assert list(s.daily_returns) == pytest.approx(rets)
    assert s.sharpe == pytest.approx(_hand_sharpe(rets))
    assert [y for y, _ in s.year_returns] == [2024, 2025]
    assert [v for _, v in s.year_returns] == pytest.approx([0.0391, 1048.17 / 1039.1 - 1.0])
    assert s.worst_year[0] == 2025 and s.worst_year[1] == pytest.approx(1048.17 / 1039.1 - 1.0)


def test_run_stats_degenerate_curves():
    flat = RunResult(
        strategy_id="FLAT", params=None, start=D("2025-01-02"), end=D("2025-01-03"), usd_idr=Decimal("16000"),
        initial_cash=P("1000"),
        snapshots=(_snap("2024-12-31", "1000", "1000"), _snap("2025-01-02", "1000", "1000"),
                   _snap("2025-01-03", "1000", "1000")),
        events=(), closed=(), open_at_end=(), rejections=(),
    )
    s = run_stats(flat)
    assert s.daily_returns == (0.0, 0.0)
    assert s.sharpe is None                                                           # zero stdev
    assert (s.exposure, s.turnover, s.costs_usd, s.gross_pnl_usd, s.dividends_usd) == (0.0, 0.0, 0.0, 0.0, 0.0)
    assert s.cost_drag is None                                                        # no gross profit
    assert s.year_returns == ((2025, 0.0),) and s.worst_year == (2025, 0.0)
    assert s.metrics.trades == 0
    one = replace(flat, end=D("2025-01-02"), snapshots=flat.snapshots[:2])
    assert run_stats(one).daily_returns == (0.0,)
    assert run_stats(one).sharpe is None                                              # fewer than 2 returns


def test_run_stats_type_check():
    with pytest.raises(TypeError, match="RunResult or a BookResult"):
        run_stats(object())
```

**Impact:** adds 47 tests. The test module imports `tests/test_backtest_runner.py` by module name. That works because pytest's default `prepend` import mode puts `engine/tests` on `sys.path`, which is how `simkit` and `stratkit` are already imported. The import only reads it, so the file stays byte-identical. The `steps` fixture monkeypatches `book_runner.step_book`, which is why Step 1 imports `step_book` as a module-level name. Keep it that way.

## Verification

All commands run from `/home/miftah/.worktrees/seer/trade-rules-dev-search`. Use the **worktree's own** `engine/.venv`, never `/home/miftah/seer/engine/.venv`.

**Build:** `engine/.venv/bin/python -c "import seer_engine.backtest.book_runner"`

**Tests:**
- `engine/.venv/bin/pytest engine/tests/test_book_runner.py -q`: 47 passed.
- `engine/.venv/bin/pytest engine/tests/test_strategy_purity.py -q`: the glob now includes `seer_engine.backtest.book_runner`.
- `docker start seer-pg && PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`:
  - expect 0 skipped;
  - expect **(the count after phases 1 and 2) + 47** collected and passed (1197 when phases 1, 2 and 4 have landed; see the index's count table);
  - log the number in the phase log.
- Frozen set:

  ```
  git diff --stat 2546a92 -- engine/src/seer_engine/sim/model.py engine/src/seer_engine/sim/lifecycle.py engine/src/seer_engine/sim/sizing.py engine/src/seer_engine/sim/split_adjust.py engine/src/seer_engine/backtest/runner.py engine/src/seer_engine/backtest/market.py engine/src/seer_engine/backtest/benchmark.py engine/src/seer_engine/backtest/metrics.py engine/tests/test_backtest_runner.py
  ```

  It must print nothing.

**Manual check:** if a parity test fails, compare `book_snaps`/`sim_snaps` session by session. The first differing date tells you which engine semantic is off: N1, N2 or N3 for sizing, N5 for forced closes, N9 for cash. Fix the engine (phase 1) or the adapter (phase 2), never the test's expectations. The simulator is the spec.

**Exit criteria:**
- The suite is green with 0 skipped.
- `run_rules(..., DESIGN_V0)` equals `run_backtest(...)` with `==` for A, A2 and B.
- For A, A2 and B on seeds 39 and 4, `run_book(PICKS, PicksParams(s, p), V0_BOOK)` matches `run_backtest(s, p)` exactly: snapshots, closed trades, fills and open positions.
- `run_stats` passes the hand checks on both result types, and agrees across the parity pair.
- The purity glob covers the new module.

## Handoffs

- **H1 (phase 9) — settled, plan index D-C.** `run_rules(DESIGN_V0)` goes to the frozen `run_backtest`, which always converts at `market.usd_idr_on(start)`, and a member-family `DESIGN_V0` window (REF-A-V0) starts around 1996-10, before the store's first FX row (1999-01-04). Phase 9 runs any window that starts before `FX_START` on a copy of the market whose `fx` is the single row `(start, usd_idr_on(FX_START))`, and passes that same rate as `usd_idr`, so `run_rules`' equality check holds. Windows are **not** clamped. The book path takes `usd_idr` directly and gets the same copy.
- **H2 (phase 9).** `research.ResearchData.dividends` (`dict[str, dict[date, Decimal]]`) already is a `DividendMap`. Pass it straight to `run_rules(dividends=...)`.
- **H3 (phases 9 and 10).** Three things phase 9 and phase 10 should know about `RunStats`:
  - `RunStats.metrics.exit_reasons` uses `BOOK_EXIT_REASONS` for a book run and `metrics.EXIT_REASONS` for a `DESIGN_V0` run (forced closes counted inside `time`). The report should label them per engine.
  - `RunStats.metrics.trades` counts non-idle closed episodes, forced closes included, as §1's "closed trades".
  - `RunStats.daily_returns` holds `len(snapshots) − 1` returns. Phase 9's `deflated_sharpe` takes `t` = that length.
- **H4 (phase 2).** N11 and N12 above hold: phase 2's `PicksAllocator.prepare` returns a strategy-agnostic `LazyPrepared(history)`, so `picks_prepared(seed)` here works as written.
- **H5 (phases 1 and 2) — settled, plan index D-A.** N1 is resolved in phase 1 (Σ ≤ 1 only without a slot cap) and phase 2 (PICKS uncapped).

## Rollback

Delete both new files:
- `engine/src/seer_engine/backtest/book_runner.py`
- `engine/tests/test_book_runner.py`

Or `git revert` the phase's commit. No other file changes, so nothing else needs undoing.
