> Adopted from `ENGINE_FILL_SIMULATOR_PLAN.md` phase 1. Source: `.workflows/plan/engine-fill-simulator/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: Pure price types, sim model and session lifecycle

**Plan set:** `ENGINE_FILL_SIMULATOR_PLAN.md`
**Analysis:** `20261003-134417-F7S2_code_analyzer.md`
**Satisfies:** R1, R3, R4 (purity test only). Order lifecycle `pending -> open -> closed / expired`; cash, equity and `pnl_usd` with 0.1% per side; a per-session snapshot; an import-clean core
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine` (`seer_engine.prices`, `seer_engine.sim`)

---

## Goal

After this phase, `seer_engine.sim` exists as a pure, Decimal-only package. `step(portfolio, session_date, bars)`
takes a portfolio through one NYSE session (time stop, gap, intraday SL then TP, fill, expiry, mark to close) and returns
the new portfolio, the ordered events and an equity snapshot. `close_unpriced` force-closes positions that will never get
another bar. `Bar`, `PRICE_QUANTUM` and `to_decimal` live in the new pure module `seer_engine.prices`, and `seer_engine.bars`
re-exports them, so the core never loads `psycopg`. A fresh-subprocess test enforces that.

All code below was run in a scratch copy of the engine before this plan was written:
`tests/test_sim_lifecycle.py` + `tests/test_sim_purity.py` gave 76 passed, and the full suite with `PG_TEST_URL` gave
**292 passed, 0 skipped** (216 baseline + 76). A rough benchmark (2,955 sessions, 4 slots, constant churn) ran in 0.18 s.

## Interface Contract

**Deletes:** none. The definitions of `Bar`, `PRICE_QUANTUM` and `to_decimal` move out of `bars.py` (`bars.py:17-47`) and are re-exported (see Renames).
**Renames / moves:** `seer_engine.bars.Bar` / `.PRICE_QUANTUM` / `.to_decimal` are now defined in `seer_engine.prices`. `seer_engine.bars` re-exports the **same objects** (`bars.Bar is prices.Bar`). `Bar.__module__` becomes `seer_engine.prices`. The repr is unchanged.
**Creates:**

- `seer_engine/prices.py`: `PRICE_QUANTUM = Decimal("0.0001")`, `@dataclass(frozen=True, slots=True) class Bar(symbol: str, date: date, open: Decimal, high: Decimal, low: Decimal, close: Decimal, volume: int)`, `def to_decimal(x: Decimal | float | int | str) -> Decimal` (body unchanged from `bars.py`)
- `seer_engine/sim/model.py`:
  - `SLOTS = 4`, `TIME_STOP_DAYS = 5`, `COST_RATE = Decimal("0.001")`
  - `OrderStatus = Literal["pending","open","closed","expired"]`, `ExitReason = Literal["tp","sl","time","gap"]`, `EventKind = Literal["fill","expire","exit","split"]`
  - `def q(x: Decimal) -> Decimal`: TypeError on a non-Decimal, ValueError when not finite
  - `def buy_cost(price: Decimal, shares: int) -> Decimal`: `q(price*shares*(1+COST_RATE))`. Price must be a Decimal > 0, shares an int >= 0 (bool refused)
  - `def sell_proceeds(price: Decimal, shares: int) -> Decimal`: `q(price*shares*(1-COST_RATE))`, with the same validation
  - `def initial_cash_usd(idr: Decimal, usd_idr: Decimal) -> Decimal`: `q(idr/usd_idr)`. Both must be > 0
  - `@dataclass(frozen=True, slots=True) class Order`: fields exactly as in the index contract. `__post_init__` validates:
    - `slot` is 1..4
    - `symbol` is a non-empty str
    - every price is a Decimal > 0 (TypeError for any other type)
    - `sl_price < tp_price`
    - `shares` is an int >= 1
    - the status is known
    - pending/expired: no fill fields and `days_held == 0`
    - open/closed: fill fields set and `days_held >= 1`
    - closed: exit fields + `pnl_usd` set and `exit_reason` known
    - not closed: no exit fields
  - `@dataclass(frozen=True, slots=True) class Portfolio(cash, equity, orders=(), marks=(), last_session=None)`. `__post_init__` validates:
    - `orders` is a tuple of live (pending/open) orders, strictly ascending by slot, len <= 4, and no symbol appears twice
    - `marks` is a tuple of `(str, Decimal>0)`, strictly ascending by symbol
    - the mark symbols are **exactly** the open orders' symbols

    Methods:
    - `open_orders() -> tuple[Order, ...]` (by slot)
    - `pending_orders() -> tuple[Order, ...]` (by slot)
    - `free_slots() -> tuple[int, ...]` (ascending)
    - `held_symbols() -> tuple[str, ...]`: sorted symbols of **every live order, pending included**
    - `mark(symbol: str) -> Decimal | None`
  - `def new_portfolio(cash_usd: Decimal) -> Portfolio`: `cash = equity = q(cash_usd)`, and `cash_usd` must be > 0
  - `@dataclass(frozen=True, slots=True) class Event(session_date: date, kind: EventKind, order: Order, forced: bool = False, cash_usd: Decimal | None = None)`, validated
  - `@dataclass(frozen=True, slots=True) class Snapshot(date: date, cash_usd: Decimal, equity_usd: Decimal)`
  - `@dataclass(frozen=True, slots=True) class StepResult(portfolio: Portfolio, events: tuple[Event, ...], snapshot: Snapshot)`
- `seer_engine/sim/lifecycle.py`:
  - `def step(portfolio: Portfolio, session_date: date, bars: Mapping[str, Bar]) -> StepResult`
  - `def close_unpriced(portfolio: Portfolio, symbols: Iterable[str]) -> tuple[Portfolio, tuple[Event, ...]]`
- `seer_engine/sim/__init__.py`: re-exports `COST_RATE, SLOTS, TIME_STOP_DAYS, Event, EventKind, ExitReason, Order, OrderStatus, Portfolio, Snapshot, StepResult, buy_cost, close_unpriced, initial_cash_usd, new_portfolio, q, sell_proceeds, step`. `__all__` is isort-style sorted (ruff RUF022): UPPER_CASE constants, then CamelCase types, then functions, each group alphabetical. It is **not** `sorted()` order.
- `engine/tests/simkit.py`. Dates may be an ISO `str` or a `date`. Numbers may be a `str`, `int` or `Decimal`; a float raises TypeError.
  - `D(s: str | date) -> date`
  - `P(x: str | int | Decimal) -> Decimal` (quantized with `q`)
  - `bar(symbol: str, d: str | date, o, h, l, c, volume: int = 1_000_000) -> Bar`
  - `day(*bars: Bar) -> dict[str, Bar]`. **This one is an addition to the index list**, a convenience used to build `step`'s mapping
  - `pending(symbol, session_date, limit, tp, sl, shares: int, slot: int = 1, last=None) -> Order`. `last_price` defaults to `limit`
  - `opened(symbol, fill_date, fill_price, tp, sl, shares: int, days_held: int, slot: int = 1, limit=None) -> Order`. `session_date = fill_date`, and `limit_price = last_price = limit or fill_price`
  - `portfolio(cash, *orders, marks: Mapping[str, Num] | None = None, last_session=None, equity=None) -> Portfolio`. Orders are sorted by slot for the caller. `marks` defaults to each open order's `fill_price`. `equity` defaults to `q(cash + Σ shares × mark)`

**Behavioral contract other phases rely on:**

- `step` events come out as **exits (by slot), then fills (by slot), then expiries (by slot)**.
- Bars are only read for symbols with a live order. Other entries of the mapping are ignored and not validated.
- `step` raises:
  - TypeError for a non-`Portfolio`, a `datetime`, a non-Mapping, a non-`Bar` value or a non-Decimal OHLC on a bar it reads.
  - ValueError when the date is not a session (`dates.is_session`), when `session_date <= last_session`, when a pending order's `session_date != session_date`, or when a bar it reads has the wrong symbol or date, or a price that is <= 0 or not finite.
- `step` leaves `days_held` and `marks` consistent: after `step`, `portfolio.marks` holds exactly the open symbols.
- `close_unpriced` **recomputes `equity`** as `q(cash + Σ shares × mark)` over the positions still open and keeps `last_session`. It refuses:
  - a bare `str` (TypeError)
  - a symbol that is not an open position, pending ones included (ValueError)
  - `last_session is None` (ValueError)

  Duplicate symbols are de-duplicated. An empty iterable returns `(portfolio, ())` unchanged.
- `Portfolio` validation runs on **every** construction (including `dataclasses.replace`). Phase 2 must keep `orders` sorted by slot and marks equal to the open symbols. Phase 3 must rescale marks and keep `shares >= 1` on every `Order`, so an expired-by-split pending order keeps its pre-split shares, or at least 1. See Handoffs.

**Requires (from earlier phases):** nothing.
**Leaves alone (owned by others):**
- `sim/sizing.py` and `tests/test_sim_sizing.py` (Phase 2)
- `sim/split_adjust.py` and `tests/test_sim_split.py` (Phase 3)
- the sizing/split exports in `sim/__init__.py`, plus `tests/test_sim_scenario.py`, `engine/package_readme.md` and `docs/ROADMAP.md` (Phase 4)
- `splits.py`, `dates.py` and `commands/*` (nobody)

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/prices.py` | create | pure `PRICE_QUANTUM`, `Bar`, `to_decimal` (moved verbatim from `bars.py:17-47`) |
| `engine/src/seer_engine/bars.py` | modify | drop line 11 (`from dataclasses import dataclass`); replace lines 17-47 with a re-export from `seer_engine.prices` |
| `engine/src/seer_engine/sim/__init__.py` | create | phase-1 public surface (model + lifecycle) |
| `engine/src/seer_engine/sim/model.py` | create | constants, money helpers, `Order`, `Portfolio`, `new_portfolio`, `Event`, `Snapshot`, `StepResult` |
| `engine/src/seer_engine/sim/lifecycle.py` | create | `step`, `close_unpriced` |
| `engine/tests/simkit.py` | create | synthetic bar/order/portfolio builders (shared by phases 1-4) |
| `engine/tests/test_sim_lifecycle.py` | create | 72 tests (after parametrize): money, model invariants, every lifecycle rule |
| `engine/tests/test_sim_purity.py` | create | fresh-subprocess `sys.modules` check, AST purity scan of `sim/*.py`, bars-re-export identity |

## Implementation Steps

### Step 0: Get a working venv in the worktree
The worktree has **no** `engine/.venv` (checked). Create it (index Invariant 1):

    cd /home/miftah/.worktrees/seer/engine-fill-simulator && python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'

`python3` resolves to pyenv's Python 3.11.0. Do **not** run tests with `/home/miftah/seer/engine/.venv`: it is an editable
install of `/home/miftah/seer`, so it tests main's tree, not this worktree. Phases 2-4 reuse the venv this step creates.

### Step 1: Create the pure price module
**File:** `engine/src/seer_engine/prices.py` (new)
**Change:** move `PRICE_QUANTUM`, `Bar` and `to_decimal` here unchanged. Imports are stdlib only.
**Code:**
```python
"""Pure price value types: the daily ``Bar`` and 4-decimal price rounding.

No database and no network. ``seer_engine.bars`` re-exports everything here so existing
imports keep working; code that must stay free of ``psycopg`` (the ``sim`` core) imports
from this module instead.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

PRICE_QUANTUM = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class Bar:
    symbol: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


def to_decimal(x: Decimal | float | int | str) -> Decimal:
    """``x`` as a Decimal rounded half-up to 4 decimals (Postgres numeric rounding).

    Floats go through their shortest repr, so 0.1 becomes Decimal('0.1000'), not the
    binary expansion.
    """
    if isinstance(x, bool):
        raise TypeError("bool is not a price")
    if isinstance(x, float):
        if not math.isfinite(x):
            raise ValueError(f"non-finite value: {x!r}")
        d = Decimal(repr(x))
    else:
        d = Decimal(x)
    if not d.is_finite():
        raise ValueError(f"non-finite value: {x!r}")
    return d.quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP)
```
**Impact:** none on its own. `Bar.__module__` becomes `seer_engine.prices` once step 2 lands. No code or test inspects it (grepped).

### Step 2: Re-export from `bars.py`
**File:** `engine/src/seer_engine/bars.py:7-47`
**Change:** delete `from dataclasses import dataclass` (line 11; `Bar` was its only user). Replace lines 17-47 (`PRICE_QUANTUM = …` through the end of `to_decimal`) with the re-export below. Keep `math`, `ROUND_HALF_UP` and `Decimal`, because `to_volume` still uses them. Everything from `def to_volume` (line 50) down is untouched. After the edit, the top of the file reads:
**Code:**
```python
"""Daily bars: the value type and idempotent writes to ``bars``.

Prices are split-adjusted only (no dividend adjustment), stored as numeric(12,4);
volume is an integer. Symbols are in canonical dot form ('BRK.B').
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

import psycopg

# Re-exported: these moved to the pure seer_engine.prices so the sim core can use them
# without importing psycopg. Every `from seer_engine.bars import Bar, ...` keeps working.
from seer_engine.prices import PRICE_QUANTUM, Bar, to_decimal  # noqa: F401

```
**Impact:** every existing `from seer_engine.bars import Bar, to_decimal, PRICE_QUANTUM, make_bar, …` and `bars.Bar`-style access keeps working: these names are module attributes and the same objects. `monkeypatch.setattr(bars, "upsert_bars", …)` in `test_backfill.py:459` is unaffected.

### Step 3: Sim model
**File:** `engine/src/seer_engine/sim/model.py` (new)
**Change:** constants, the money helpers and the immutable value types, exactly the index's shared API contract plus validation.
**Code:**
```python
"""Simulator value types and money arithmetic (design §5, fill-simulator handover §3).

Everything here is an immutable value. Money and prices are ``Decimal`` quantized to 4
decimals half-up (``PRICE_QUANTUM``, matching ``numeric(12,4)`` / ``numeric(14,4)``);
shares are ``int``. A ``float`` never enters: every constructor and helper raises
``TypeError`` on a non-Decimal price or amount.

``Order`` mirrors the ``orders`` table columns (minus strategy_id, company, explanation,
id and created_at) so P4 can persist it without translation. A ``Portfolio`` holds only
LIVE orders (pending and open); a terminal order (closed, expired) leaves the portfolio
and appears exactly once, inside the ``Event`` that ended it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from seer_engine.prices import PRICE_QUANTUM

SLOTS = 4
TIME_STOP_DAYS = 5
COST_RATE = Decimal("0.001")

OrderStatus = Literal["pending", "open", "closed", "expired"]
ExitReason = Literal["tp", "sl", "time", "gap"]
EventKind = Literal["fill", "expire", "exit", "split"]

_STATUSES: tuple[str, ...] = ("pending", "open", "closed", "expired")
_LIVE: tuple[str, ...] = ("pending", "open")
_EXIT_REASONS: tuple[str, ...] = ("tp", "sl", "time", "gap")
_EVENT_KINDS: tuple[str, ...] = ("fill", "expire", "exit", "split")


# --------------------------------------------------------------------------- validation


def _decimal(name: str, x: object) -> Decimal:
    """``x`` if it is a finite Decimal; TypeError for any other type (float included)."""
    if not isinstance(x, Decimal):
        raise TypeError(f"{name} must be a Decimal, got {type(x).__name__}")
    if not x.is_finite():
        raise ValueError(f"{name} must be finite, got {x!r}")
    return x


def _positive(name: str, x: object) -> Decimal:
    d = _decimal(name, x)
    if d <= 0:
        raise ValueError(f"{name} must be > 0, got {d}")
    return d


def _int(name: str, x: object) -> int:
    if isinstance(x, bool) or not isinstance(x, int):
        raise TypeError(f"{name} must be an int, got {type(x).__name__}")
    return x


def _date(name: str, x: object) -> date:
    if isinstance(x, datetime) or not isinstance(x, date):
        raise TypeError(f"{name} must be a date, got {type(x).__name__}")
    return x


# --------------------------------------------------------------------------- money


def q(x: Decimal) -> Decimal:
    """``x`` quantized to 4 decimals, ROUND_HALF_UP (the schema's numeric rounding)."""
    return _decimal("value", x).quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP)


def buy_cost(price: Decimal, shares: int) -> Decimal:
    """Cash paid to buy ``shares`` at ``price``, including the 0.1% cost: q(p × n × 1.001)."""
    _positive("price", price)
    if _int("shares", shares) < 0:
        raise ValueError(f"shares must be >= 0, got {shares}")
    return q(price * shares * (1 + COST_RATE))


def sell_proceeds(price: Decimal, shares: int) -> Decimal:
    """Cash received selling ``shares`` at ``price``, net of the 0.1% cost: q(p × n × 0.999)."""
    _positive("price", price)
    if _int("shares", shares) < 0:
        raise ValueError(f"shares must be >= 0, got {shares}")
    return q(price * shares * (1 - COST_RATE))


def initial_cash_usd(idr: Decimal, usd_idr: Decimal) -> Decimal:
    """Starting capital in USD: q(idr / usd_idr), with ``usd_idr`` the IDR price of 1 USD."""
    return q(_positive("idr", idr) / _positive("usd_idr", usd_idr))


# --------------------------------------------------------------------------- orders


@dataclass(frozen=True, slots=True)
class Order:
    """One bracket order, shaped like an ``orders`` row.

    ``days_held`` counts sessions the position has been open: the fill session is day 1,
    every later session adds 1 (with or without a bar). An exit at the open of a session
    records the count before that session; an intraday exit includes it.
    """

    session_date: date
    slot: int
    symbol: str
    last_price: Decimal
    limit_price: Decimal
    tp_price: Decimal
    sl_price: Decimal
    shares: int
    status: OrderStatus = "pending"
    fill_date: date | None = None
    fill_price: Decimal | None = None
    days_held: int = 0
    exit_date: date | None = None
    exit_price: Decimal | None = None
    exit_reason: ExitReason | None = None
    pnl_usd: Decimal | None = None

    def __post_init__(self) -> None:
        _date("session_date", self.session_date)
        if not (1 <= _int("slot", self.slot) <= SLOTS):
            raise ValueError(f"slot must be 1..{SLOTS}, got {self.slot}")
        if not isinstance(self.symbol, str) or not self.symbol:
            raise ValueError(f"symbol must be a non-empty str, got {self.symbol!r}")
        _positive("last_price", self.last_price)
        _positive("limit_price", self.limit_price)
        _positive("tp_price", self.tp_price)
        _positive("sl_price", self.sl_price)
        if self.sl_price >= self.tp_price:
            raise ValueError(f"sl_price {self.sl_price} must be below tp_price {self.tp_price}")
        if _int("shares", self.shares) < 1:
            raise ValueError(f"shares must be >= 1, got {self.shares}")
        if self.status not in _STATUSES:
            raise ValueError(f"unknown status {self.status!r}")
        if _int("days_held", self.days_held) < 0:
            raise ValueError(f"days_held must be >= 0, got {self.days_held}")
        filled = self.status in ("open", "closed")
        if filled:
            if self.fill_date is None or self.fill_price is None:
                raise ValueError(f"a {self.status} order needs fill_date and fill_price")
            _date("fill_date", self.fill_date)
            _positive("fill_price", self.fill_price)
            if self.days_held < 1:
                raise ValueError(f"a {self.status} order has days_held >= 1")
        elif self.fill_date is not None or self.fill_price is not None or self.days_held != 0:
            raise ValueError(f"a {self.status} order has no fill and days_held 0")
        if self.status == "closed":
            if self.exit_date is None or self.exit_price is None or self.pnl_usd is None:
                raise ValueError("a closed order needs exit_date, exit_price and pnl_usd")
            _date("exit_date", self.exit_date)
            _positive("exit_price", self.exit_price)
            if self.exit_reason not in _EXIT_REASONS:
                raise ValueError(f"unknown exit_reason {self.exit_reason!r}")
            _decimal("pnl_usd", self.pnl_usd)
        elif (
            self.exit_date is not None
            or self.exit_price is not None
            or self.exit_reason is not None
            or self.pnl_usd is not None
        ):
            raise ValueError(f"a {self.status} order has no exit fields")


# --------------------------------------------------------------------------- portfolio


@dataclass(frozen=True, slots=True)
class Portfolio:
    """One strategy's state between sessions.

    - ``cash``: real cash, 4 dp. Pending orders reserve nothing here.
    - ``equity``: equity at the last snapshot (initial cash before the first session).
    - ``orders``: LIVE orders only (pending + open), sorted by slot, at most one per slot,
      at most one per symbol.
    - ``marks``: last known close for every OPEN order's symbol, sorted by symbol.
    - ``last_session``: the last session stepped, or None before the first.
    """

    cash: Decimal
    equity: Decimal
    orders: tuple[Order, ...] = ()
    marks: tuple[tuple[str, Decimal], ...] = ()
    last_session: date | None = None

    def __post_init__(self) -> None:
        _decimal("cash", self.cash)
        _decimal("equity", self.equity)
        if not isinstance(self.orders, tuple):
            raise TypeError("orders must be a tuple")
        if not isinstance(self.marks, tuple):
            raise TypeError("marks must be a tuple")
        if self.last_session is not None:
            _date("last_session", self.last_session)
        if len(self.orders) > SLOTS:
            raise ValueError(f"at most {SLOTS} live orders, got {len(self.orders)}")
        prev_slot = 0
        symbols: list[str] = []
        for o in self.orders:
            if not isinstance(o, Order):
                raise TypeError(f"orders must hold Order values, got {type(o).__name__}")
            if o.status not in _LIVE:
                raise ValueError(f"portfolio holds live orders only, got {o.status!r} ({o.symbol})")
            if o.slot <= prev_slot:
                raise ValueError("orders must be sorted by slot with one order per slot")
            prev_slot = o.slot
            if o.symbol in symbols:
                raise ValueError(f"symbol {o.symbol} appears in two live orders")
            symbols.append(o.symbol)
        prev_symbol = ""
        for item in self.marks:
            if not (isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str)):
                raise TypeError("marks must be (symbol, Decimal) pairs")
            if item[0] <= prev_symbol:
                raise ValueError("marks must be sorted by symbol, one per symbol")
            prev_symbol = item[0]
            _positive(f"mark {item[0]}", item[1])
        open_symbols = sorted(o.symbol for o in self.orders if o.status == "open")
        if [s for s, _ in self.marks] != open_symbols:
            raise ValueError(
                f"marks must cover exactly the open symbols {open_symbols}, "
                f"got {[s for s, _ in self.marks]}"
            )

    def open_orders(self) -> tuple[Order, ...]:
        """Open positions, by slot."""
        return tuple(o for o in self.orders if o.status == "open")

    def pending_orders(self) -> tuple[Order, ...]:
        """Pending orders, by slot."""
        return tuple(o for o in self.orders if o.status == "pending")

    def free_slots(self) -> tuple[int, ...]:
        """Slots with no live order, ascending."""
        used = [o.slot for o in self.orders]
        return tuple(s for s in range(1, SLOTS + 1) if s not in used)

    def held_symbols(self) -> tuple[str, ...]:
        """Symbols of every LIVE order (open and pending), sorted. "No adding" means a
        symbol here cannot take a new order."""
        return tuple(sorted(o.symbol for o in self.orders))

    def mark(self, symbol: str) -> Decimal | None:
        """Last known close for an open symbol, or None."""
        for s, price in self.marks:
            if s == symbol:
                return price
        return None


def new_portfolio(cash_usd: Decimal) -> Portfolio:
    """An empty portfolio with ``cash = equity = q(cash_usd)``."""
    cash = q(_positive("cash_usd", cash_usd))
    return Portfolio(cash=cash, equity=cash)


# --------------------------------------------------------------------------- results


@dataclass(frozen=True, slots=True)
class Event:
    """Something that happened to one order.

    ``order`` is the order's state AFTER the event (a terminal order lives only here).
    ``cash_usd`` is the cash it moved: ``-buy_cost`` on a fill, ``+sell_proceeds`` on an
    exit, ``+cash in lieu`` on a split, None when no cash moved. ``forced`` marks an exit
    at the last known close made without a bar: ``close_unpriced``, or a split that floors
    an open position to 0 shares (``split_adjust.apply_split``).
    """

    session_date: date
    kind: EventKind
    order: Order
    forced: bool = False
    cash_usd: Decimal | None = None

    def __post_init__(self) -> None:
        _date("session_date", self.session_date)
        if self.kind not in _EVENT_KINDS:
            raise ValueError(f"unknown event kind {self.kind!r}")
        if not isinstance(self.order, Order):
            raise TypeError("order must be an Order")
        if not isinstance(self.forced, bool):
            raise TypeError("forced must be a bool")
        if self.cash_usd is not None:
            _decimal("cash_usd", self.cash_usd)


@dataclass(frozen=True, slots=True)
class Snapshot:
    """One ``equity_snapshots`` row: cash and equity at a session's close."""

    date: date
    cash_usd: Decimal
    equity_usd: Decimal


@dataclass(frozen=True, slots=True)
class StepResult:
    portfolio: Portfolio
    events: tuple[Event, ...]
    snapshot: Snapshot
```
**Impact:** new module. It imports only `dataclasses`, `datetime`, `decimal`, `typing` and `seer_engine.prices`.

### Step 4: Session lifecycle
**File:** `engine/src/seer_engine/sim/lifecycle.py` (new)
**Change:** `step` and `close_unpriced`, implementing the session-order rows of the index's Decisions table. Those rows cover:
- `days_held` counting (fill session = day 1; exit at the open of session k records k-1; intraday exit records k; no bar still counts)
- time stop first, then gap SL (`gap`), then gap TP (`tp`), then intraday SL, then TP (`high > tp` strictly)
- `pnl = sell_proceeds - buy_cost`
- the ValueError rules
- `close_unpriced` semantics
**Code:**
```python
"""One NYSE session of the order lifecycle (design §5, fill-simulator handover §3).

``step`` advances a portfolio through one session's split-adjusted bars. For every open
position, in slot order:

1. time stop: ``days_held >= TIME_STOP_DAYS`` and a bar → exit at the open, reason ``time``;
2. gap: ``open <= sl`` → exit at the open, reason ``gap``; ``open >= tp`` → exit at the
   open, reason ``tp``;
3. intraday: ``low <= sl`` → exit at sl, reason ``sl`` (checked first); else ``high > tp``
   → exit at tp, reason ``tp``;
4. otherwise it stays open, ``days_held`` + 1, marked at the close.

An open position with no bar has no event; ``days_held`` still + 1 and the mark stays at
its last known close. Then every pending order (all must be for this session):

5. fill when ``low < limit`` (strict) at ``min(open, limit)``, ``days_held`` = 1, marked
   at the close; a position filled today is not checked against TP/SL today;
6. otherwise (including no bar) it expires.

Events come out as all exits (by slot), then all fills (by slot), then all expiries
(by slot). The snapshot is ``cash + Σ shares × mark`` at the close.

Pure: no clock, no I/O, no randomness. The caller owns the calendar and the bars.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal

from seer_engine import dates
from seer_engine.prices import Bar
from seer_engine.sim.model import (
    TIME_STOP_DAYS,
    Event,
    ExitReason,
    Order,
    Portfolio,
    Snapshot,
    StepResult,
    buy_cost,
    q,
    sell_proceeds,
)


def _check_bar(symbol: str, bar: object, session_date: date) -> Bar:
    if not isinstance(bar, Bar):
        raise TypeError(f"bars[{symbol!r}] must be a Bar, got {type(bar).__name__}")
    if bar.symbol != symbol:
        raise ValueError(f"bars[{symbol!r}] holds a bar for {bar.symbol!r}")
    if bar.date != session_date:
        raise ValueError(f"bars[{symbol!r}] is dated {bar.date}, expected {session_date}")
    for field in ("open", "high", "low", "close"):
        value = getattr(bar, field)
        if not isinstance(value, Decimal):
            raise TypeError(f"{symbol} {field} must be a Decimal, got {type(value).__name__}")
        if not value.is_finite() or value <= 0:
            raise ValueError(f"{symbol} {field} must be a finite price > 0, got {value}")
    return bar


def _close(order: Order, when: date, price: Decimal, reason: ExitReason, days_held: int) -> tuple[Order, Decimal]:
    """The closed order and the cash its sale brings in.

    ``pnl_usd = sell_proceeds - buy_cost`` so the sum of pnl reconciles with cash exactly.
    """
    if order.fill_price is None:
        raise ValueError(f"{order.symbol} has no fill price")
    exit_price = q(price)
    proceeds = sell_proceeds(exit_price, order.shares)
    pnl = proceeds - buy_cost(order.fill_price, order.shares)
    closed = replace(
        order,
        status="closed",
        days_held=days_held,
        exit_date=when,
        exit_price=exit_price,
        exit_reason=reason,
        pnl_usd=pnl,
    )
    return closed, proceeds


def _exit_on_bar(order: Order, bar: Bar) -> tuple[Decimal, ExitReason, int] | None:
    """(exit price, reason, days_held) when the open position exits on ``bar``, else None."""
    if order.days_held >= TIME_STOP_DAYS:
        return bar.open, "time", order.days_held
    if bar.open <= order.sl_price:
        return bar.open, "gap", order.days_held
    if bar.open >= order.tp_price:
        return bar.open, "tp", order.days_held
    if bar.low <= order.sl_price:
        return order.sl_price, "sl", order.days_held + 1
    if bar.high > order.tp_price:
        return order.tp_price, "tp", order.days_held + 1
    return None


def _snapshot_equity(cash: Decimal, orders: Iterable[Order], marks: Mapping[str, Decimal]) -> Decimal:
    total = cash
    for o in orders:
        if o.status == "open":
            total += o.shares * marks[o.symbol]
    return q(total)


def _rebuild(
    cash: Decimal,
    equity: Decimal,
    live: list[Order],
    marks: Mapping[str, Decimal],
    last_session: date | None,
) -> Portfolio:
    orders = tuple(sorted(live, key=lambda o: o.slot))
    open_symbols = sorted(o.symbol for o in orders if o.status == "open")
    return Portfolio(
        cash=cash,
        equity=equity,
        orders=orders,
        marks=tuple((s, marks[s]) for s in open_symbols),
        last_session=last_session,
    )


def step(portfolio: Portfolio, session_date: date, bars: Mapping[str, Bar]) -> StepResult:
    """Advance ``portfolio`` through the NYSE session ``session_date``.

    ``bars`` maps symbol → that session's split-adjusted ``Bar``; a symbol absent from it
    has no bar this session. Only bars for symbols with a live order are read (and
    validated); the rest are ignored.

    Raises TypeError on a non-Decimal price or a wrong type, and ValueError when
    ``session_date`` is not an NYSE session, is not after ``portfolio.last_session``,
    or differs from a pending order's ``session_date``.
    """
    if not isinstance(portfolio, Portfolio):
        raise TypeError(f"portfolio must be a Portfolio, got {type(portfolio).__name__}")
    if isinstance(session_date, datetime) or not isinstance(session_date, date):
        raise TypeError(f"session_date must be a date, got {type(session_date).__name__}")
    if not isinstance(bars, Mapping):
        raise TypeError(f"bars must be a Mapping, got {type(bars).__name__}")
    if not dates.is_session(session_date):
        raise ValueError(f"{session_date} is not an NYSE session")
    if portfolio.last_session is not None and session_date <= portfolio.last_session:
        raise ValueError(f"{session_date} is not after the last session stepped ({portfolio.last_session})")
    for o in portfolio.pending_orders():
        if o.session_date != session_date:
            raise ValueError(
                f"pending order {o.symbol} (slot {o.slot}) is for {o.session_date}, not {session_date}"
            )
    day: dict[str, Bar] = {}
    for o in portfolio.orders:
        bar = bars.get(o.symbol)
        if bar is not None:
            day[o.symbol] = _check_bar(o.symbol, bar, session_date)

    cash = portfolio.cash
    marks: dict[str, Decimal] = dict(portfolio.marks)
    live: list[Order] = []
    exits: list[Event] = []
    fills: list[Event] = []
    expiries: list[Event] = []

    # (1)-(3) exits of open positions, at the open first, then intraday (SL before TP).
    for o in portfolio.open_orders():
        bar = day.get(o.symbol)
        if bar is None:
            live.append(replace(o, days_held=o.days_held + 1))
            continue
        hit = _exit_on_bar(o, bar)
        if hit is None:
            live.append(replace(o, days_held=o.days_held + 1))
            marks[o.symbol] = bar.close
            continue
        price, reason, days_held = hit
        closed, proceeds = _close(o, session_date, price, reason, days_held)
        cash += proceeds
        del marks[o.symbol]
        exits.append(Event(session_date, "exit", closed, cash_usd=proceeds))

    # (4)-(5) fills of pending orders (strict low < limit), else expiry.
    for o in portfolio.pending_orders():
        bar = day.get(o.symbol)
        if bar is not None and bar.low < o.limit_price:
            fill_price = q(bar.open if bar.open < o.limit_price else o.limit_price)
            cost = buy_cost(fill_price, o.shares)
            cash -= cost
            filled = replace(o, status="open", fill_date=session_date, fill_price=fill_price, days_held=1)
            marks[o.symbol] = bar.close
            live.append(filled)
            fills.append(Event(session_date, "fill", filled, cash_usd=-cost))
        else:
            expiries.append(Event(session_date, "expire", replace(o, status="expired")))

    # (6) mark to close.
    equity = _snapshot_equity(cash, live, marks)
    new = _rebuild(cash, equity, live, marks, session_date)
    return StepResult(
        portfolio=new,
        events=tuple(exits + fills + expiries),
        snapshot=Snapshot(date=session_date, cash_usd=cash, equity_usd=equity),
    )


def close_unpriced(portfolio: Portfolio, symbols: Iterable[str]) -> tuple[Portfolio, tuple[Event, ...]]:
    """Force-close open positions that will never get another bar (delisted, halted for good).

    Each named position exits at its last known close (its mark), reason ``time``,
    ``exit_date = portfolio.last_session``, ``days_held`` unchanged, with ``forced=True``
    on its event. Cash takes the proceeds net of the 0.1% cost, and ``equity`` is
    recomputed as ``cash + Σ shares × mark`` for what is still open. Events are in slot
    order. Every symbol must belong to an open position; the caller decides that no
    further bar will come (a pure step cannot know it).
    """
    if not isinstance(portfolio, Portfolio):
        raise TypeError(f"portfolio must be a Portfolio, got {type(portfolio).__name__}")
    if isinstance(symbols, str):
        raise TypeError("symbols must be an iterable of symbols, not a single str")
    wanted: list[str] = []
    for s in symbols:
        if not isinstance(s, str):
            raise TypeError(f"symbol must be a str, got {type(s).__name__}")
        if s not in wanted:
            wanted.append(s)
    if not wanted:
        return portfolio, ()
    open_symbols = [o.symbol for o in portfolio.open_orders()]
    for s in wanted:
        if s not in open_symbols:
            raise ValueError(f"{s} is not an open position")
    when = portfolio.last_session
    if when is None:
        raise ValueError("cannot close a position before any session was stepped")

    cash = portfolio.cash
    marks: dict[str, Decimal] = dict(portfolio.marks)
    live: list[Order] = []
    events: list[Event] = []
    for o in portfolio.orders:
        if o.status != "open" or o.symbol not in wanted:
            live.append(o)
            continue
        closed, proceeds = _close(o, when, marks[o.symbol], "time", o.days_held)
        cash += proceeds
        del marks[o.symbol]
        events.append(Event(when, "exit", closed, forced=True, cash_usd=proceeds))
    equity = _snapshot_equity(cash, live, marks)
    return _rebuild(cash, equity, live, marks, when), tuple(events)
```
**Impact:** new module. It imports `seer_engine.dates`, which is measured import-clean, plus `seer_engine.prices` and `sim.model`. It never imports `seer_engine.bars`.

### Step 5: Package surface
**File:** `engine/src/seer_engine/sim/__init__.py` (new)
**Change:** export model + lifecycle only. Phase 4 adds the sizing and split names.
**Code:**
```python
"""Seer fill simulator: pure, deterministic order lifecycle and portfolio accounting.

One code path for the backtest (P3) and nightly paper trading (P4). No database, no
network, no clock: importing this package must never load psycopg, requests or yfinance
(enforced by tests/test_sim_purity.py).
"""

from seer_engine.sim.lifecycle import close_unpriced, step
from seer_engine.sim.model import (
    COST_RATE,
    SLOTS,
    TIME_STOP_DAYS,
    Event,
    EventKind,
    ExitReason,
    Order,
    OrderStatus,
    Portfolio,
    Snapshot,
    StepResult,
    buy_cost,
    initial_cash_usd,
    new_portfolio,
    q,
    sell_proceeds,
)

__all__ = [
    "COST_RATE",
    "SLOTS",
    "TIME_STOP_DAYS",
    "Event",
    "EventKind",
    "ExitReason",
    "Order",
    "OrderStatus",
    "Portfolio",
    "Snapshot",
    "StepResult",
    "buy_cost",
    "close_unpriced",
    "initial_cash_usd",
    "new_portfolio",
    "q",
    "sell_proceeds",
    "step",
]
```
**Impact:** `import seer_engine.sim` loads `model`, `lifecycle`, `dates`, `prices` (and pandas_market_calendars through `dates`). It loads no psycopg, requests or yfinance (tested).

### Step 6: Test builders
**File:** `engine/tests/simkit.py` (new)
**Change:** shared helpers. `engine/tests` has no `__init__.py`, and pytest's default `prepend` import mode puts `engine/tests` on `sys.path`, so test modules use `from simkit import …`. It is not collected, because the name does not match `test_*.py`.
**Code:**
```python
"""Builders for simulator tests: synthetic bars, orders and portfolios.

Shared by every tests/test_sim_*.py (phases 1-4). Strings in, exact Decimals out; a float
is refused so no binary rounding sneaks into a hand-checked number. Dates may be given as
ISO strings or ``date`` values.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from seer_engine.prices import Bar
from seer_engine.sim.model import Order, Portfolio, q

Num = str | int | Decimal
Day = str | date


def D(s: Day) -> date:
    """``date.fromisoformat(s)``; a ``date`` passes through."""
    return s if isinstance(s, date) else date.fromisoformat(s)


def P(x: Num) -> Decimal:
    """An exact Decimal quantized to 4 dp (half-up). Floats are refused."""
    if isinstance(x, (float, bool)):
        raise TypeError(f"use a str, int or Decimal, not {type(x).__name__}")
    return q(x if isinstance(x, Decimal) else Decimal(x))


def bar(symbol: str, d: Day, o: Num, h: Num, l: Num, c: Num, volume: int = 1_000_000) -> Bar:  # noqa: E741
    """A Bar for ``symbol`` on ``d`` with exact 4-dp prices."""
    return Bar(symbol, D(d), P(o), P(h), P(l), P(c), volume)


def day(*bars: Bar) -> dict[str, Bar]:
    """One session's bars keyed by symbol, as ``step`` takes them."""
    return {b.symbol: b for b in bars}


def pending(
    symbol: str,
    session_date: Day,
    limit: Num,
    tp: Num,
    sl: Num,
    shares: int,
    slot: int = 1,
    last: Num | None = None,
) -> Order:
    """A pending bracket for ``session_date``; ``last`` defaults to ``limit``."""
    return Order(
        session_date=D(session_date),
        slot=slot,
        symbol=symbol,
        last_price=P(limit if last is None else last),
        limit_price=P(limit),
        tp_price=P(tp),
        sl_price=P(sl),
        shares=shares,
    )


def opened(
    symbol: str,
    fill_date: Day,
    fill_price: Num,
    tp: Num,
    sl: Num,
    shares: int,
    days_held: int,
    slot: int = 1,
    limit: Num | None = None,
) -> Order:
    """An open position filled on ``fill_date`` (also its session_date) at ``fill_price``;
    ``limit`` (and last_price) default to ``fill_price``."""
    lim = P(fill_price if limit is None else limit)
    return Order(
        session_date=D(fill_date),
        slot=slot,
        symbol=symbol,
        last_price=lim,
        limit_price=lim,
        tp_price=P(tp),
        sl_price=P(sl),
        shares=shares,
        status="open",
        fill_date=D(fill_date),
        fill_price=P(fill_price),
        days_held=days_held,
    )


def portfolio(
    cash: Num,
    *orders: Order,
    marks: Mapping[str, Num] | None = None,
    last_session: Day | None = None,
    equity: Num | None = None,
) -> Portfolio:
    """A Portfolio holding ``orders`` (sorted by slot for you).

    ``marks`` defaults to each open order's fill price. ``equity`` defaults to
    ``cash + Σ shares × mark`` over the open orders.
    """
    live = tuple(sorted(orders, key=lambda o: o.slot))
    if marks is None:
        mark_map = {o.symbol: o.fill_price for o in live if o.status == "open"}
    else:
        mark_map = {s: P(v) for s, v in marks.items()}
    cash_d = P(cash)
    if equity is None:
        eq = q(cash_d + sum((o.shares * mark_map[o.symbol] for o in live if o.status == "open"), Decimal(0)))
    else:
        eq = P(equity)
    return Portfolio(
        cash=cash_d,
        equity=eq,
        orders=live,
        marks=tuple(sorted(mark_map.items())),
        last_session=None if last_session is None else D(last_session),
    )
```
**Impact:** phases 2-4 import it and must not edit it.

### Step 7: Lifecycle tests
**File:** `engine/tests/test_sim_lifecycle.py` (new)
**Change:** one test per phase-1 rule. Each pnl assertion carries the hand arithmetic, and the comment checks it against handover §3's formula. Map to handover §6.1:

| §6.1 item | Test(s) |
|---|---|
| touch vs penetrate, entry | `test_entry_touch_does_not_fill_and_expires`, `test_entry_penetrate_fills_at_limit` |
| touch vs penetrate, TP | `test_tp_touch_does_not_exit`, `test_tp_penetrate_exits_at_tp` |
| touch vs penetrate, SL | `test_sl_touch_exits_at_sl` |
| open < limit -> fill at open | `test_entry_open_below_limit_fills_at_open`, `test_entry_open_equal_to_limit_fills_at_limit` |
| gap through SL (`gap`) / TP (`tp`) | `test_gap_down_through_sl_exits_at_open_reason_gap`, `test_open_exactly_at_sl_is_a_gap_exit`, `test_gap_up_through_tp_exits_at_open_reason_tp`, `test_open_exactly_at_tp_exits_at_open_reason_tp` |
| SL and TP same bar -> SL first | `test_sl_and_tp_on_the_same_bar_takes_sl_first` |
| no TP/SL check on the fill session | `test_no_tp_sl_check_on_the_fill_session` |
| time stop at day-6 open, holiday + half day | `test_time_stop_at_the_open_of_day_6` (Oct 5-12 2026), `test_time_stop_across_thanksgiving_and_the_half_day` (fill 2026-11-24, holiday 11-26, half day 11-27, exit at the open of 12-02 with `days_held=5`), `test_time_stop_comes_before_gap_and_tp_checks`, `test_day_5_still_checks_tp_and_sl_intraday`, `test_days_held_counts_each_session` |
| expiry | `test_entry_touch_does_not_fill_and_expires`, `test_missing_bar_for_pending_order_expires` |
| costs and `pnl_usd` to the cent | `test_buy_cost_and_sell_proceeds`, `test_pnl_to_the_cent_with_rounding` (12.3457 -> 11.1111 × 7 = -8.8064), `test_round_trip_pnl_reconciles_with_cash`, the pnl asserts in the TP/SL/gap/time tests |
| slot reuse after an exit (phase-1 half: the slot is freed) | `test_slot_is_freed_after_an_exit`. Phase 2 tests the re-placement |
| missing bar for a held symbol | `test_missing_bar_for_a_held_symbol_counts_the_day_and_keeps_the_mark`, `test_due_time_stop_waits_for_the_next_bar` |
| cash/equity snapshot (R3) | `test_snapshot_marks_every_open_position_at_the_close`, `test_empty_portfolio_still_snapshots`, `test_entry_penetrate_fills_at_limit` |
| determinism / ordering (supports §6.2) | `test_events_are_exits_then_fills_then_expiries_in_slot_order` (also checks that a reversed mapping gives an identical result), `test_step_does_not_change_its_input` |
| `close_unpriced` (§7 settlement) | `test_close_unpriced_exits_at_the_last_known_close`, `test_close_unpriced_events_are_in_slot_order`, `test_close_unpriced_with_nothing_to_close_is_a_no_op`, `test_close_unpriced_rejects_bad_symbols`, `test_close_unpriced_needs_a_stepped_session` |
| validation (Decisions: ValueError rules, invariant 5) | `test_floats_are_refused`, `test_order_rejects_bad_fields`, `test_order_refuses_float_prices`, `test_portfolio_rejects_broken_state`, `test_step_rejects_*`, `test_bars_for_unrelated_symbols_are_ignored` |

**Code:**
```python
"""Fill simulator: money helpers, model invariants and the one-session lifecycle.

Every rule in design §5 and fill-simulator handover §3 / §6.1 that phase 1 owns has a test
here, on synthetic bars. Real NYSE dates (via seer_engine.dates) are used throughout:
2026-10-05 is a Monday; Thanksgiving 2026-11-26 is a holiday and 2026-11-27 a half day.
No database needed.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal

import pytest

from seer_engine import dates
from seer_engine.prices import Bar
from seer_engine.sim import (
    COST_RATE,
    SLOTS,
    TIME_STOP_DAYS,
    Event,
    Order,
    Portfolio,
    Snapshot,
    buy_cost,
    close_unpriced,
    initial_cash_usd,
    new_portfolio,
    q,
    sell_proceeds,
    step,
)
from simkit import D, P, bar, day, opened, pending, portfolio

MON = "2026-10-05"
TUE = "2026-10-06"
WED = "2026-10-07"
THU = "2026-10-08"
FRI = "2026-10-09"
MON2 = "2026-10-12"
TUE2 = "2026-10-13"


def _only(events: tuple[Event, ...]) -> Event:
    assert len(events) == 1, events
    return events[0]


# ============================================================== money helpers and model


def test_constants():
    assert SLOTS == 4
    assert TIME_STOP_DAYS == 5
    assert COST_RATE == Decimal("0.001")


def test_q_rounds_half_up_to_4dp():
    assert q(Decimal("1.00005")) == Decimal("1.0001")
    assert q(Decimal("1.00004999")) == Decimal("1.0000")
    assert q(Decimal("-1.00005")) == Decimal("-1.0001")  # half-up = away from zero
    assert str(q(Decimal("7"))) == "7.0000"


def test_buy_cost_and_sell_proceeds():
    # 100 × 50 = 5000; × 1.001 = 5005; × 0.999 = 4995
    assert buy_cost(P("50"), 100) == Decimal("5005.0000")
    assert sell_proceeds(P("50"), 100) == Decimal("4995.0000")
    # 7 × 12.3457 = 86.4199; × 1.001 = 86.5063199 -> 86.5063
    assert buy_cost(P("12.3457"), 7) == Decimal("86.5063")
    # 7 × 11.1111 = 77.7777; × 0.999 = 77.6999223 -> 77.6999
    assert sell_proceeds(P("11.1111"), 7) == Decimal("77.6999")


def test_initial_cash_usd():
    # 20,000,000 / 16,250 = 1230.769230... -> 1230.7692
    assert initial_cash_usd(Decimal("20000000"), Decimal("16250")) == Decimal("1230.7692")


@pytest.mark.parametrize(
    "call",
    [
        lambda: q(1.5),
        lambda: buy_cost(50.0, 1),
        lambda: sell_proceeds(Decimal("50"), 1.0),
        lambda: buy_cost(Decimal("50"), True),
        lambda: initial_cash_usd(20_000_000.0, Decimal("16250")),
        lambda: new_portfolio(1000.0),
    ],
)
def test_floats_are_refused(call):
    with pytest.raises(TypeError):
        call()


def test_new_portfolio():
    p = new_portfolio(Decimal("1230.76923"))
    assert p.cash == p.equity == Decimal("1230.7692")
    assert p.orders == () and p.marks == () and p.last_session is None
    assert p.free_slots() == (1, 2, 3, 4)


def test_portfolio_helpers():
    a = opened("AAA", MON, "10", "11", "9", 10, days_held=2, slot=3)
    b = pending("BBB", TUE, "20", "22", "18", 5, slot=1)
    p = portfolio("1000", a, b, marks={"AAA": "10.5"})
    assert [o.slot for o in p.orders] == [1, 3]
    assert p.open_orders() == (a,)
    assert p.pending_orders() == (b,)
    assert p.free_slots() == (2, 4)
    assert p.held_symbols() == ("AAA", "BBB")
    assert p.mark("AAA") == Decimal("10.5000")
    assert p.mark("BBB") is None
    assert p.equity == Decimal("1105.0000")  # 1000 + 10 × 10.5


@pytest.mark.parametrize(
    "build",
    [
        # two orders in one slot
        lambda: Portfolio(
            P("1"), P("1"), (pending("A", MON, "10", "11", "9", 1), pending("B", MON, "10", "11", "9", 1))
        ),
        # not sorted by slot
        lambda: Portfolio(
            P("1"),
            P("1"),
            (pending("A", MON, "10", "11", "9", 1, slot=2), pending("B", MON, "10", "11", "9", 1, slot=1)),
        ),
        # one symbol twice
        lambda: Portfolio(
            P("1"),
            P("1"),
            (pending("A", MON, "10", "11", "9", 1, slot=1), pending("A", MON, "10", "11", "9", 1, slot=2)),
        ),
        # a terminal order
        lambda: Portfolio(P("1"), P("1"), (replace(pending("A", MON, "10", "11", "9", 1), status="expired"),)),
        # an open order without a mark
        lambda: Portfolio(P("1"), P("1"), (opened("A", MON, "10", "11", "9", 1, 1),)),
        # a mark without an open order
        lambda: Portfolio(P("1"), P("1"), (), (("A", P("10")),)),
    ],
)
def test_portfolio_rejects_broken_state(build):
    with pytest.raises(ValueError):
        build()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"slot": 0},
        {"slot": 5},
        {"shares": 0},
        {"sl_price": P("11"), "tp_price": P("11")},
        {"limit_price": P("0")},
        {"status": "open"},  # open without fill fields
        {"days_held": 1},  # pending with days held
    ],
)
def test_order_rejects_bad_fields(kwargs):
    base = pending("AAA", MON, "10", "11", "9", 10)
    with pytest.raises(ValueError):
        replace(base, **kwargs)


def test_order_refuses_float_prices():
    base = pending("AAA", MON, "10", "11", "9", 10)
    with pytest.raises(TypeError):
        replace(base, limit_price=10.0)
    with pytest.raises(TypeError):
        replace(base, shares=10.0)


# ============================================================== entry (fill)


def test_entry_touch_does_not_fill_and_expires():
    # low == limit: a touch is not a fill (strict low < limit).
    p = portfolio("1000", pending("AAA", MON, "10", "11", "9", 10, slot=2))
    r = step(p, D(MON), day(bar("AAA", MON, "10.20", "10.50", "10", "10.30")))
    ev = _only(r.events)
    assert ev.kind == "expire" and ev.cash_usd is None
    assert ev.order.status == "expired" and ev.order.fill_price is None
    assert r.portfolio.orders == ()
    assert r.portfolio.free_slots() == (1, 2, 3, 4)  # slot freed
    assert r.portfolio.cash == Decimal("1000.0000")
    assert r.snapshot == Snapshot(D(MON), Decimal("1000.0000"), Decimal("1000.0000"))


def test_entry_penetrate_fills_at_limit():
    # low one tick below the limit fills; open above the limit -> fill at the limit.
    p = portfolio("1000", pending("AAA", MON, "10", "11", "9", 10))
    r = step(p, D(MON), day(bar("AAA", MON, "10.20", "10.50", "9.9999", "10.30")))
    ev = _only(r.events)
    assert ev.kind == "fill"
    o = ev.order
    assert (o.status, o.fill_date, o.fill_price, o.days_held) == ("open", D(MON), Decimal("10.0000"), 1)
    # cost = 10 × 10 × 1.001 = 100.1000
    assert ev.cash_usd == Decimal("-100.1000")
    assert r.portfolio.cash == Decimal("899.9000")
    # equity = 899.9000 + 10 × 10.30 (close) = 1002.9000
    assert r.snapshot.equity_usd == Decimal("1002.9000")
    assert r.portfolio.equity == Decimal("1002.9000")
    assert r.portfolio.marks == (("AAA", Decimal("10.3000")),)
    assert r.portfolio.last_session == D(MON)


def test_entry_open_below_limit_fills_at_open():
    p = portfolio("1000", pending("AAA", MON, "10", "11", "9", 10))
    r = step(p, D(MON), day(bar("AAA", MON, "9.80", "10.40", "9.70", "10.10")))
    ev = _only(r.events)
    assert ev.order.fill_price == Decimal("9.8000")
    # cost = 10 × 9.80 × 1.001 = 98.0980
    assert ev.cash_usd == Decimal("-98.0980")
    assert r.portfolio.cash == Decimal("901.9020")


def test_entry_open_equal_to_limit_fills_at_limit():
    p = portfolio("1000", pending("AAA", MON, "10", "11", "9", 10))
    r = step(p, D(MON), day(bar("AAA", MON, "10", "10.40", "9.70", "10.10")))
    assert _only(r.events).order.fill_price == Decimal("10.0000")


def test_missing_bar_for_pending_order_expires():
    p = portfolio("1000", pending("AAA", MON, "10", "11", "9", 10))
    r = step(p, D(MON), day(bar("ZZZ", MON, "1", "1", "1", "1")))
    ev = _only(r.events)
    assert ev.kind == "expire" and ev.order.status == "expired"
    assert r.portfolio.orders == ()


def test_no_tp_sl_check_on_the_fill_session():
    # The fill bar spans both SL (9) and TP (11): the position is filled and stays open.
    p = portfolio("1000", pending("AAA", MON, "10", "11", "9", 10))
    r = step(p, D(MON), day(bar("AAA", MON, "10.50", "11.50", "8.50", "10.20")))
    ev = _only(r.events)
    assert ev.kind == "fill"
    (o,) = r.portfolio.orders
    assert o.status == "open" and o.days_held == 1


# ============================================================== TP and SL


def _held(days_held: int = 1, shares: int = 10) -> Portfolio:
    # Bought 10 AAA at 10 on MON: cost 100.1000, cash left 899.9000.
    return portfolio("899.9", opened("AAA", MON, "10", "11", "9", shares, days_held), last_session=MON)


def test_tp_touch_does_not_exit():
    r = step(_held(), D(TUE), day(bar("AAA", TUE, "10.50", "11", "10.20", "10.80")))
    assert r.events == ()
    (o,) = r.portfolio.orders
    assert o.days_held == 2
    assert r.portfolio.mark("AAA") == Decimal("10.8000")
    # equity = 899.9000 + 10 × 10.80 = 1007.9000
    assert r.snapshot.equity_usd == Decimal("1007.9000")


def test_tp_penetrate_exits_at_tp():
    r = step(_held(), D(TUE), day(bar("AAA", TUE, "10.50", "11.0001", "10.20", "10.80")))
    ev = _only(r.events)
    o = ev.order
    assert ev.kind == "exit" and not ev.forced
    assert (o.status, o.exit_reason, o.exit_price, o.exit_date) == ("closed", "tp", Decimal("11.0000"), D(TUE))
    assert o.days_held == 2  # intraday exit on day 2 counts day 2
    # proceeds = 10 × 11 × 0.999 = 109.8900; pnl = 109.8900 − 100.1000 = 9.7900
    # handover formula: (11 − 10) × 10 − 0.001 × (11 + 10) × 10 = 10 − 0.21 = 9.79
    assert ev.cash_usd == Decimal("109.8900")
    assert o.pnl_usd == Decimal("9.7900")
    assert r.portfolio.cash == Decimal("1009.7900")
    assert r.snapshot.equity_usd == Decimal("1009.7900")
    assert r.portfolio.orders == () and r.portfolio.marks == ()


def test_sl_touch_exits_at_sl():
    r = step(_held(), D(TUE), day(bar("AAA", TUE, "9.80", "10.10", "9", "9.50")))
    o = _only(r.events).order
    assert (o.exit_reason, o.exit_price, o.days_held) == ("sl", Decimal("9.0000"), 2)
    # proceeds = 10 × 9 × 0.999 = 89.9100; pnl = 89.9100 − 100.1000 = −10.1900
    # formula: (9 − 10) × 10 − 0.001 × 19 × 10 = −10 − 0.19 = −10.19
    assert o.pnl_usd == Decimal("-10.1900")
    assert r.portfolio.cash == Decimal("989.8100")


def test_sl_and_tp_on_the_same_bar_takes_sl_first():
    r = step(_held(), D(TUE), day(bar("AAA", TUE, "10", "11.50", "8.90", "10.60")))
    o = _only(r.events).order
    assert (o.exit_reason, o.exit_price) == ("sl", Decimal("9.0000"))


def test_gap_down_through_sl_exits_at_open_reason_gap():
    r = step(_held(), D(TUE), day(bar("AAA", TUE, "8.50", "8.90", "8.00", "8.20")))
    o = _only(r.events).order
    assert (o.exit_reason, o.exit_price) == ("gap", Decimal("8.5000"))
    assert o.days_held == 1  # exit at the open of day 2 records the days before it
    # proceeds = 85 × 0.999 = 84.9150; pnl = 84.9150 − 100.1000 = −15.1850
    # formula: (8.5 − 10) × 10 − 0.001 × 18.5 × 10 = −15 − 0.185 = −15.185
    assert o.pnl_usd == Decimal("-15.1850")


def test_open_exactly_at_sl_is_a_gap_exit():
    r = step(_held(), D(TUE), day(bar("AAA", TUE, "9", "9.50", "8.80", "9.20")))
    o = _only(r.events).order
    assert (o.exit_reason, o.exit_price) == ("gap", Decimal("9.0000"))


def test_gap_up_through_tp_exits_at_open_reason_tp():
    r = step(_held(), D(TUE), day(bar("AAA", TUE, "11.40", "11.90", "11.20", "11.60")))
    o = _only(r.events).order
    assert (o.exit_reason, o.exit_price, o.days_held) == ("tp", Decimal("11.4000"), 1)
    # proceeds = 114 × 0.999 = 113.8860; pnl = 113.8860 − 100.1000 = 13.7860
    # formula: (11.4 − 10) × 10 − 0.001 × 21.4 × 10 = 14 − 0.214 = 13.786
    assert o.pnl_usd == Decimal("13.7860")


def test_open_exactly_at_tp_exits_at_open_reason_tp():
    r = step(_held(), D(TUE), day(bar("AAA", TUE, "11", "11", "10.50", "10.70")))
    o = _only(r.events).order
    assert (o.exit_reason, o.exit_price) == ("tp", Decimal("11.0000"))


def test_pnl_to_the_cent_with_rounding():
    # 7 shares filled at 12.3457, SL hit at 11.1111.
    p = portfolio(
        "913.4937",
        opened("XYZ", MON, "12.3457", "13.5", "11.1111", 7, days_held=1),
        last_session=MON,
    )
    r = step(p, D(TUE), day(bar("XYZ", TUE, "12", "12.10", "11.00", "11.05")))
    o = _only(r.events).order
    # buy_cost = q(86.4199 × 1.001 = 86.5063199) = 86.5063
    # proceeds = q(77.7777 × 0.999 = 77.6999223) = 77.6999
    # pnl = 77.6999 − 86.5063 = −8.8064
    # formula: (11.1111 − 12.3457) × 7 − 0.001 × 23.4568 × 7 = −8.6422 − 0.1641976 = −8.8063976
    assert o.pnl_usd == Decimal("-8.8064")
    assert abs(o.pnl_usd - Decimal("-8.8063976")) <= Decimal("0.0001")
    # cash = 913.4937 + 77.6999 = 991.1936
    assert r.portfolio.cash == Decimal("991.1936")


def test_round_trip_pnl_reconciles_with_cash():
    # Fill then exit via step: cash change equals pnl exactly.
    start = portfolio("1000", pending("AAA", MON, "10", "11", "9", 10))
    r1 = step(start, D(MON), day(bar("AAA", MON, "9.95", "10.10", "9.90", "10.05")))
    # fill at open 9.95: cost = 99.5 × 1.001 = 99.5995
    assert r1.portfolio.cash == Decimal("900.4005")
    r2 = step(r1.portfolio, D(TUE), day(bar("AAA", TUE, "10.40", "11.20", "10.30", "11.10")))
    o = _only(r2.events).order
    # proceeds = 110 × 0.999 = 109.8900; pnl = 109.8900 − 99.5995 = 10.2905
    assert o.pnl_usd == Decimal("10.2905")
    assert r2.portfolio.cash - start.cash == o.pnl_usd
    assert r2.portfolio.cash == Decimal("1010.2905")


# ============================================================== time stop


@pytest.mark.parametrize(
    ("session", "days_before"),
    [(TUE, 1), (WED, 2), (THU, 3), (FRI, 4)],
)
def test_days_held_counts_each_session(session, days_before):
    p = portfolio(
        "899.9",
        opened("AAA", MON, "10", "11", "9", 10, days_held=days_before),
        last_session=dates.prev_session(D(session)),
    )
    r = step(p, D(session), day(bar("AAA", session, "10", "10.5", "9.5", "10")))
    assert r.events == ()
    assert r.portfolio.orders[0].days_held == days_before + 1


def test_time_stop_at_the_open_of_day_6():
    # Fill MON (day 1); TUE..FRI are days 2-5; nothing hits. Exit at MON2's open.
    p = portfolio("1000", pending("AAA", MON, "10", "11", "9", 10))
    quiet = ("10", "10.50", "9.50", "10.20")
    p = step(p, D(MON), day(bar("AAA", MON, "10", "10.5", "9.9", "10.2"))).portfolio
    for s in (TUE, WED, THU, FRI):
        r = step(p, D(s), day(bar("AAA", s, *quiet)))
        assert r.events == ()
        p = r.portfolio
    assert p.orders[0].days_held == 5
    r = step(p, D(MON2), day(bar("AAA", MON2, "10.30", "10.90", "10.10", "10.60")))
    o = _only(r.events).order
    assert (o.exit_reason, o.exit_price, o.exit_date, o.days_held) == ("time", Decimal("10.3000"), D(MON2), 5)
    # cost = 100.1000; proceeds = 103 × 0.999 = 102.8970; pnl = 2.7970
    assert o.pnl_usd == Decimal("2.7970")
    assert r.portfolio.cash == Decimal("1002.7970")


def test_time_stop_across_thanksgiving_and_the_half_day():
    # 2026-11-26 (Thu) is a holiday, 2026-11-27 (Fri) a half day.
    assert not dates.is_session(D("2026-11-26"))
    assert dates.is_session(D("2026-11-27"))
    with pytest.raises(ValueError):
        step(new_portfolio(Decimal("1000")), D("2026-11-26"), {})
    # Fill Tue 11-24 = day 1, Wed 11-25 = day 2, (Thu holiday: no day), Fri 11-27 half
    # day = day 3, Mon 11-30 = day 4, Tue 12-01 = day 5 -> exit at Wed 12-02's open.
    p = portfolio("1000", pending("AAA", "2026-11-24", "10", "11", "9", 10))
    p = step(p, D("2026-11-24"), day(bar("AAA", "2026-11-24", "10", "10.5", "9.9", "10.2"))).portfolio
    expected = {"2026-11-25": 2, "2026-11-27": 3, "2026-11-30": 4, "2026-12-01": 5}
    for s in dates.sessions(D("2026-11-25"), D("2026-12-01")):
        r = step(p, s, day(bar("AAA", s, "10", "10.50", "9.50", "10.20")))
        assert r.events == ()
        p = r.portfolio
        assert p.orders[0].days_held == expected[s.isoformat()]
    assert [s.isoformat() for s in dates.sessions(D("2026-11-25"), D("2026-12-01"))] == list(expected)
    r = step(p, D("2026-12-02"), day(bar("AAA", "2026-12-02", "9.70", "10.10", "9.60", "9.90")))
    o = _only(r.events).order
    assert (o.exit_reason, o.exit_price, o.exit_date, o.days_held) == (
        "time",
        Decimal("9.7000"),
        D("2026-12-02"),
        5,
    )
    # proceeds = 97 × 0.999 = 96.9030; pnl = 96.9030 − 100.1000 = −3.1970
    assert o.pnl_usd == Decimal("-3.1970")


def test_time_stop_comes_before_gap_and_tp_checks():
    # Day 6's open is below SL and its high above TP: still a time exit at the open.
    p = _held(days_held=5)
    r = step(p, D(TUE), day(bar("AAA", TUE, "8.80", "11.50", "8.50", "11.20")))
    o = _only(r.events).order
    assert (o.exit_reason, o.exit_price, o.days_held) == ("time", Decimal("8.8000"), 5)


def test_day_5_still_checks_tp_and_sl_intraday():
    r = step(_held(days_held=4), D(TUE), day(bar("AAA", TUE, "10", "10.20", "8.90", "9.10")))
    o = _only(r.events).order
    assert (o.exit_reason, o.days_held) == ("sl", 5)


# ============================================================== missing bars


def test_missing_bar_for_a_held_symbol_counts_the_day_and_keeps_the_mark():
    p = portfolio(
        "899.9",
        opened("AAA", MON, "10", "11", "9", 10, days_held=1),
        marks={"AAA": "10.40"},
        last_session=MON,
    )
    r = step(p, D(TUE), day(bar("BBB", TUE, "5", "5", "5", "5")))
    assert r.events == ()
    (o,) = r.portfolio.orders
    assert o.days_held == 2
    assert r.portfolio.mark("AAA") == Decimal("10.4000")
    # equity = 899.9000 + 10 × 10.40 (last known close) = 1003.9000
    assert r.snapshot == Snapshot(D(TUE), Decimal("899.9000"), Decimal("1003.9000"))


def test_due_time_stop_waits_for_the_next_bar():
    p = _held(days_held=5)
    r = step(p, D(TUE), {})  # no bar on day 6: nothing happens, the day still counts
    assert r.events == ()
    assert r.portfolio.orders[0].days_held == 6
    r = step(r.portfolio, D(WED), day(bar("AAA", WED, "10.10", "10.20", "9.90", "10")))
    o = _only(r.events).order
    assert (o.exit_reason, o.exit_price, o.exit_date, o.days_held) == ("time", Decimal("10.1000"), D(WED), 6)


# ============================================================== slots, ordering, purity


def test_slot_is_freed_after_an_exit():
    p = portfolio(
        "500",
        opened("AAA", MON, "10", "11", "9", 10, days_held=1, slot=1),
        opened("BBB", MON, "20", "22", "18", 5, days_held=1, slot=3),
        last_session=MON,
    )
    r = step(
        p,
        D(TUE),
        day(
            bar("AAA", TUE, "10", "11.50", "9.80", "11"),  # TP
            bar("BBB", TUE, "20", "20.50", "19.50", "20.10"),  # holds
        ),
    )
    assert [e.order.symbol for e in r.events] == ["AAA"]
    assert r.portfolio.free_slots() == (1, 2, 4)
    assert r.portfolio.held_symbols() == ("BBB",)


def test_events_are_exits_then_fills_then_expiries_in_slot_order():
    p = portfolio(
        "2000",
        pending("EEE", TUE, "10", "11", "9", 1, slot=1),  # expires
        pending("FFF", TUE, "10", "11", "9", 1, slot=2),  # fills
        opened("XXX", MON, "10", "11", "9", 1, days_held=1, slot=3),  # exits (SL)
        opened("YYY", MON, "10", "11", "9", 1, days_held=1, slot=4),  # exits (TP)
        last_session=MON,
    )
    bars = day(
        bar("YYY", TUE, "10", "11.5", "9.8", "11"),
        bar("FFF", TUE, "10", "10.2", "9.5", "10"),
        bar("XXX", TUE, "10", "10.2", "8.5", "9"),
        bar("EEE", TUE, "10.5", "10.8", "10.1", "10.6"),
    )
    r = step(p, D(TUE), bars)
    assert [(e.kind, e.order.symbol) for e in r.events] == [
        ("exit", "XXX"),
        ("exit", "YYY"),
        ("fill", "FFF"),
        ("expire", "EEE"),
    ]
    assert [o.symbol for o in r.portfolio.orders] == ["FFF"]
    # Same inputs, same outputs, independent of the mapping's insertion order.
    again = step(p, D(TUE), dict(reversed(list(bars.items()))))
    assert again == r


def test_snapshot_marks_every_open_position_at_the_close():
    p = portfolio(
        "1000",
        pending("NEW", TUE, "50", "55", "45", 2, slot=2),
        opened("OLD", MON, "10", "11", "9", 10, days_held=1, slot=1),
        last_session=MON,
    )
    r = step(
        p,
        D(TUE),
        day(bar("OLD", TUE, "10.1", "10.6", "9.6", "10.5"), bar("NEW", TUE, "49", "51", "48", "50.5")),
    )
    # NEW fills at open 49: cost = 98 × 1.001 = 98.0980 -> cash 901.9020
    # equity = 901.9020 + 10 × 10.50 + 2 × 50.50 = 901.9020 + 105 + 101 = 1107.9020
    assert r.snapshot == Snapshot(D(TUE), Decimal("901.9020"), Decimal("1107.9020"))
    assert r.portfolio.marks == (("NEW", Decimal("50.5000")), ("OLD", Decimal("10.5000")))


def test_empty_portfolio_still_snapshots():
    r = step(new_portfolio(Decimal("1230.7692")), D(MON), {})
    assert r.events == ()
    assert r.snapshot == Snapshot(D(MON), Decimal("1230.7692"), Decimal("1230.7692"))
    assert r.portfolio.last_session == D(MON)


def test_step_does_not_change_its_input():
    p = _held()
    before = repr(p)
    step(p, D(TUE), day(bar("AAA", TUE, "10.50", "11.50", "10.20", "11")))
    assert repr(p) == before


def test_bars_for_unrelated_symbols_are_ignored():
    # A bad bar for a symbol nobody holds is never read.
    r = step(_held(), D(TUE), {"AAA": bar("AAA", TUE, "10", "10.5", "9.5", "10"), "JUNK": object()})
    assert r.events == ()


# ============================================================== validation


def test_step_rejects_a_non_session():
    with pytest.raises(ValueError):
        step(new_portfolio(Decimal("1000")), D("2026-10-03"), {})  # Saturday


def test_step_rejects_a_session_not_after_the_last():
    p = _held()
    with pytest.raises(ValueError):
        step(p, D(MON), {})
    with pytest.raises(ValueError):
        step(p, D("2026-10-02"), {})


def test_step_rejects_a_pending_order_for_another_session():
    p = portfolio("1000", pending("AAA", WED, "10", "11", "9", 10))
    with pytest.raises(ValueError):
        step(p, D(TUE), {})


def test_step_rejects_a_datetime():
    with pytest.raises(TypeError):
        step(new_portfolio(Decimal("1000")), datetime(2026, 10, 5, 14, 30), {})


def test_step_rejects_float_bar_prices():
    bad = Bar("AAA", D(TUE), 10.0, Decimal("10.5"), Decimal("9.5"), Decimal("10"), 1)
    with pytest.raises(TypeError):
        step(_held(), D(TUE), {"AAA": bad})


@pytest.mark.parametrize(
    "bars",
    [
        {"AAA": bar("BBB", TUE, "10", "10.5", "9.5", "10")},  # keyed under the wrong symbol
        {"AAA": bar("AAA", WED, "10", "10.5", "9.5", "10")},  # wrong date
    ],
)
def test_step_rejects_mismatched_bars(bars):
    with pytest.raises(ValueError):
        step(_held(), D(TUE), bars)


# ============================================================== close_unpriced


def test_close_unpriced_exits_at_the_last_known_close():
    p = portfolio(
        "500",
        opened("AAA", MON, "10", "11", "9", 10, days_held=3, slot=2),
        opened("BBB", MON, "20", "22", "18", 5, days_held=3, slot=1),
        marks={"AAA": "9.50", "BBB": "21"},
        last_session=THU,
    )
    p2, events = close_unpriced(p, ["AAA"])
    ev = _only(events)
    o = ev.order
    assert ev.kind == "exit" and ev.forced and ev.session_date == D(THU)
    assert (o.status, o.exit_reason, o.exit_price, o.exit_date, o.days_held) == (
        "closed",
        "time",
        Decimal("9.5000"),
        D(THU),
        3,
    )
    # proceeds = 95 × 0.999 = 94.9050; pnl = 94.9050 − 100.1000 = −5.1950
    assert ev.cash_usd == Decimal("94.9050")
    assert o.pnl_usd == Decimal("-5.1950")
    assert p2.cash == Decimal("594.9050")
    # equity = 594.9050 + 5 × 21 = 699.9050
    assert p2.equity == Decimal("699.9050")
    assert p2.marks == (("BBB", Decimal("21.0000")),)
    assert p2.free_slots() == (2, 3, 4)
    assert p2.last_session == D(THU)


def test_close_unpriced_events_are_in_slot_order():
    p = portfolio(
        "0",
        opened("AAA", MON, "10", "11", "9", 1, days_held=2, slot=4),
        opened("BBB", MON, "10", "11", "9", 1, days_held=2, slot=2),
        last_session=TUE,
    )
    p2, events = close_unpriced(p, ("AAA", "BBB", "AAA"))
    assert [e.order.symbol for e in events] == ["BBB", "AAA"]
    assert p2.orders == ()


def test_close_unpriced_with_nothing_to_close_is_a_no_op():
    p = _held()
    assert close_unpriced(p, []) == (p, ())


@pytest.mark.parametrize(
    ("symbols", "exc"),
    [
        ("AAA", TypeError),  # a bare str
        (["ZZZ"], ValueError),  # not held
        (["PND"], ValueError),  # pending, not open
    ],
)
def test_close_unpriced_rejects_bad_symbols(symbols, exc):
    p = portfolio(
        "899.9",
        opened("AAA", MON, "10", "11", "9", 10, days_held=1, slot=1),
        pending("PND", TUE, "10", "11", "9", 10, slot=2),
        last_session=MON,
    )
    with pytest.raises(exc):
        close_unpriced(p, symbols)


def test_close_unpriced_needs_a_stepped_session():
    p = portfolio("899.9", opened("AAA", MON, "10", "11", "9", 10, days_held=1))
    with pytest.raises(ValueError):
        close_unpriced(p, ["AAA"])
```
**Impact:** adds 72 test cases, all DB-free.

### Step 8: Purity tests
**File:** `engine/tests/test_sim_purity.py` (new)
**Change:** the tests below. The AST scan covers every `sim/*.py`, so the files phases 2 and 3 add are checked automatically.
- A fresh interpreter imports `seer_engine.sim` + `seer_engine.prices` and asserts that none of `psycopg`, `requests`, `yfinance` or `seer_engine.bars` is in `sys.modules`.
- A control test proves the probe can fail: importing `bars` does load psycopg.
- An AST scan of every `sim/*.py` rejects:
  - imports of `psycopg`, `requests`, `yfinance`, `time`, `random`, `logging`, `urllib`, `socket` or `seer_engine.bars`
  - the attributes `.now`, `.utcnow`, `.today`, `.fromtimestamp`
  - calls to `print`, `open`, `input`
- `bars.Bar is prices.Bar` (and the same for `to_decimal` and `PRICE_QUANTUM`).
**Code:**
```python
"""The sim core is pure (fill-simulator handover §6.2 and §6.4).

- Importing it in a fresh interpreter loads no psycopg, requests or yfinance, and never
  seer_engine.bars (which imports psycopg).
- Its source never reads the clock, draws random numbers, logs, prints or opens files.
- seer_engine.bars re-exports the moved price types as the very same objects.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import seer_engine
import seer_engine.sim

FORBIDDEN_MODULES = ("psycopg", "requests", "yfinance", "seer_engine.bars")
FORBIDDEN_IMPORT_ROOTS = {"psycopg", "requests", "yfinance", "time", "random", "logging", "urllib", "socket"}
FORBIDDEN_ATTRS = {"now", "utcnow", "today", "fromtimestamp"}
FORBIDDEN_CALLS = {"print", "open", "input"}


def _fresh_python(code: str) -> str:
    src = str(Path(seer_engine.__file__).resolve().parents[1])
    env = dict(os.environ)
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        check=True,
        timeout=120,
    )
    return out.stdout.strip()


def test_sim_import_loads_no_db_or_network_module():
    code = (
        "import sys\n"
        "import seer_engine.sim\n"
        "import seer_engine.prices\n"
        f"bad = [m for m in {FORBIDDEN_MODULES!r} if m in sys.modules]\n"
        "print(','.join(bad))\n"
    )
    assert _fresh_python(code) == ""


def test_fresh_python_does_see_a_bars_import():
    # Guards the test above against a check that can never fail.
    code = "import sys\nimport seer_engine.bars\nprint('psycopg' in sys.modules)\n"
    assert _fresh_python(code) == "True"


def _sim_sources() -> list[Path]:
    files = sorted(Path(seer_engine.sim.__file__).resolve().parent.glob("*.py"))
    assert files, "no sim sources found"
    return files


def test_sim_sources_have_no_clock_randomness_or_io():
    problems: list[str] = []
    for path in _sim_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            where = f"{path.name}:{getattr(node, 'lineno', '?')}"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in FORBIDDEN_IMPORT_ROOTS or alias.name == "seer_engine.bars":
                        problems.append(f"{where} import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                if root in FORBIDDEN_IMPORT_ROOTS or node.module == "seer_engine.bars":
                    problems.append(f"{where} from {node.module} import ...")
                if node.module == "seer_engine" and any(a.name == "bars" for a in node.names):
                    problems.append(f"{where} from seer_engine import bars")
            elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRS:
                problems.append(f"{where} .{node.attr}")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                problems.append(f"{where} {node.func.id}()")
    assert problems == []


def test_bars_reexports_the_same_objects_as_prices():
    from seer_engine import bars, prices

    assert bars.Bar is prices.Bar
    assert bars.to_decimal is prices.to_decimal
    assert bars.PRICE_QUANTUM is prices.PRICE_QUANTUM
    b = bars.make_bar("SPY", date(2026, 10, 2), "1", "2", "0.5", "1.5", 10)
    assert isinstance(b, prices.Bar)
```
**Impact:** adds 4 tests. The two subprocess tests take about 1 s together.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/engine-fill-simulator && engine/.venv/bin/python -c "import seer_engine, seer_engine.sim, seer_engine.bars; print(seer_engine.__file__)"` prints a path inside the worktree
**Tests (phase):** `engine/.venv/bin/pytest engine/tests/test_sim_lifecycle.py engine/tests/test_sim_purity.py -q` gives 76 passed
**Tests (full):** `docker start seer-pg; PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q` gives **292 passed, 0 skipped** (verified in a scratch copy)
**Manual check:** `engine/.venv/bin/python -c "import sys, seer_engine.sim; print([m for m in ('psycopg','requests','yfinance','seer_engine.bars') if m in sys.modules])"` prints `[]`.
**Exit criteria:** `step` and `close_unpriced` implement every lifecycle rule and Decisions row. Each handover §6.1 lifecycle item in the table above has a passing test. The purity subprocess test passes. The full suite is green with 0 skipped.

## Handoffs

- **Phase 2 (R2):**
  - `size_picks` must build `Portfolio(...)` with `orders` sorted by slot and unique symbols. `Portfolio.__post_init__` raises otherwise.
  - Use `Portfolio.held_symbols()`, which **includes pending** symbols, for the "held" rejection.
  - Use `free_slots()` for the lowest-free-slot rule.
  - Pick prices must be Decimals > 0 with `sl < tp` (`Order` validates). Quantize them with `q` if strategies hand in more than 4 dp: `Order` does not check the quantum.
  - Slot reuse after an exit or expiry on the same session (the second half of §6.1 "slot reuse") is phase 2's test, driven through `step`.
- **Phase 3 (R5):**
  - `Order.shares >= 1` and `sl_price < tp_price` are enforced on every construction. For a pending order that floors to 0 shares, emit the `expire` event with the order's **pre-split** shares, not 0.
  - An open position that floors to 0 closes with a forced `exit` (reason `time`, pre-split units, `pnl_usd = cash_usd − buy_cost`). That order passes `Order` validation, and `forced` covers it (Event docstring above).
  - After an adjustment, `marks` must still equal exactly the open symbols, sorted.
  - Cash in lieu goes on `Event(kind="split", cash_usd=…)`.
  - A split whose rescaled prices round to 0 or make `sl >= tp` raises `ValueError` up front (settled at reconciliation, index Decisions).
- **Phase 4 (R4):**
  - Export sizing and split names from `sim/__init__.py`.
  - Document in the readme:
    - the step event order (exits, fills, expiries)
    - that `close_unpriced` recomputes `equity`, so P4 should persist the snapshot after it
    - that only bars for live symbols are read
  - Write the benchmark test. Phase-1 rough timing: 0.18 s for 2,955 sessions × 4 slots.
- **Any phase:** the AST purity scan in `test_sim_purity.py` applies to every `sim/*.py`. Phases 2 and 3 must not import `time`, `random` or `logging`, must not call `.now()` or `.today()`, and must not `print` or `open` in the core.
- **Index note (applied at reconciliation):** `simkit` gains one helper beyond the draft index list, `day(*bars) -> dict[str, Bar]`; the index now lists it. `held_symbols()` is defined as all live orders (pending + open).

## Rollback

`git revert <phase-1 sha>`. That removes `prices.py`, `sim/`, `simkit.py` and the two test files, and restores `bars.py` to define `Bar`, `PRICE_QUANTUM` and `to_decimal` itself. Phases 2-4 depend on this phase, so revert them first. There are no database or config changes.
