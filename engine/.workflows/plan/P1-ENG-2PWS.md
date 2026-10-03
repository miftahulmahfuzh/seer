> Adopted from `ENGINE_FILL_SIMULATOR_PLAN.md` phase 2. Source: `.workflows/plan/engine-fill-simulator/phase-2.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 2: Whole-share sizing of picks into slots

**Plan set:** `ENGINE_FILL_SIMULATOR_PLAN.md`
**Analysis:** `20261003-134417-F7S2_code_analyzer.md`
**Satisfies:** R2. Whole-share sizing across 4 slots, equity ÷ 4 recomputed daily, the cash cap, ineligible below 1 share, no adding to a holding, and 0 picks is valid.
**Depends on:** Phase 1
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/sim` (`seer_engine.sim.sizing`)

---

## Goal

After this phase, `seer_engine.sim.sizing.size_picks(portfolio, picks, session_date)` turns a
strategy's ranked picks into whole-share pending bracket `Order`s in the portfolio's free slots for
the next session. It applies the handover §3 sizing row exactly: budget = min(equity ÷ 4, cash not
committed to pending orders), shares = floor(budget / (limit × 1.001)). Picks that cannot be placed
come back as `Rejection`s with a reason. The function is pure, deterministic and Decimal-only, and
`engine/tests/test_sim_sizing.py` proves every R2 rule with hand-checked arithmetic, including slot
reuse after an exit and an expiry driven through phase 1's `lifecycle.step`.

## Interface Contract

**Deletes:** nothing
**Renames:** nothing
**Creates:**
- `seer_engine.sim.sizing.RejectReason = Literal["no_slot", "held", "lt_one_share"]` (`engine/src/seer_engine/sim/sizing.py`)
- `seer_engine.sim.sizing.Pick` (frozen, slotted dataclass: `symbol: str, last_price, limit_price, tp_price, sl_price: Decimal`). Its `__post_init__` validates the inputs and quantizes the prices to 4 dp.
- `seer_engine.sim.sizing.Rejection` (frozen, slotted: `symbol: str, reason: RejectReason`)
- `seer_engine.sim.sizing.SizingResult` (frozen, slotted: `portfolio: Portfolio, placed: tuple[Order, ...], rejected: tuple[Rejection, ...]`)
- `seer_engine.sim.sizing.size_picks(portfolio: Portfolio, picks: Sequence[Pick], session_date: date) -> SizingResult`
- private helpers: `_price`, `_check_session_date`, `_whole_shares`, `_ONE_PLUS_COST`
- test module `engine/tests/test_sim_sizing.py`

**Signature changes:** none

**Requires (from earlier phases):** Phase 1 has landed with exactly the index's Shared API contract:
- `seer_engine.sim.model`: `SLOTS` (4), `COST_RATE` (`Decimal("0.001")`), `q`, `buy_cost`, `Order`
  (constructor fields `session_date, slot, symbol, last_price, limit_price, tp_price, sl_price,
  shares`, with `status` defaulting to `"pending"`), `Portfolio` (fields `cash, equity, orders,
  marks, last_session`, plus methods `pending_orders()` and `free_slots()` returning ascending slot
  ints, and `held_symbols()` returning the sorted symbols of every live order, pending included), and `new_portfolio(cash_usd)`.
- `Portfolio` is a frozen dataclass, so `dataclasses.replace(portfolio, orders=...)` works. Any
  `__post_init__` validation it has accepts `orders` sorted by slot with at most one order per slot.
- `seer_engine.sim.lifecycle.step(portfolio, session_date, bars) -> StepResult`, where
  `StepResult.portfolio.equity` is that session's snapshot equity and `last_session` is set to
  `session_date`. A closed or expired order leaves `portfolio.orders`.
- `engine/tests/simkit.py`, importable as `from simkit import D, P, bar, opened, pending, portfolio`
  (the `engine/tests` directory has no `__init__.py`, so pytest's default `prepend` import mode
  puts it on `sys.path`). These tests pass `P(...)` Decimals to every simkit price argument,
  `bar` included. With `marks=None`, `simkit.portfolio` must give a valid `Portfolio` for any open
  orders passed in. Sizing never reads `marks`, so these tests never pass it.
- `seer_engine.dates.is_session` (exists today, `dates.py:80`).

**Leaves alone (owned by others):**
- `engine/src/seer_engine/sim/__init__.py`. Phase 4 adds the `Pick`, `Rejection`, `RejectReason`, `SizingResult`, `size_picks` exports. These tests import from `seer_engine.sim.sizing` directly.
- `sim/model.py`, `sim/lifecycle.py`, `prices.py`, `bars.py`, `tests/simkit.py`, `test_sim_lifecycle.py`, `test_sim_purity.py` (Phase 1)
- `sim/split_adjust.py`, `tests/test_sim_split.py` (Phase 3)
- `tests/test_sim_scenario.py`, `engine/package_readme.md`, `docs/ROADMAP.md` (Phase 4)

**Behavioural contract (for phase 4's scenario and the readme):**
1. The validation order is: `portfolio` type, `session_date` type (a `date` but not a `datetime`,
   otherwise `TypeError`), `is_session` (otherwise `ValueError`), and
   `session_date > portfolio.last_session` when that is set (otherwise `ValueError`). Next, each
   pick must be a `Pick` (otherwise `TypeError`). Last, every existing pending order must have
   `session_date == session_date` (otherwise `ValueError`, because a stale pending order means
   `step` was skipped).
2. Zero picks, once validation passes, returns `SizingResult(portfolio, (), ())` with the **same**
   portfolio object.
3. `slot_budget = q(portfolio.equity / SLOTS)`, computed once per call. `committed` starts at
   Σ `buy_cost(o.limit_price, o.shares)` over the existing pending orders and grows with every
   placement in this call.
4. Picks are handled in the order given. For each pick:
   - If its symbol was already seen earlier in this call's picks, or the symbol is on a live
     order (open or pending), it is rejected as `held`.
   - Otherwise, if no slot is free, it is rejected as `no_slot`.
   - Otherwise `budget = min(slot_budget, cash − committed)` and
     `shares = floor(budget / (limit × 1.001))`. If `shares < 1`, it is rejected as
     `lt_one_share`. Otherwise it takes the lowest free slot.
   A rejection never consumes a slot. The `held` check comes before `no_slot`.
5. `buy_cost(limit, shares) <= cash − committed` always holds for a placed order, so a fill at or
   below the limit can never drive cash negative.
6. Cash, equity, marks and last_session are unchanged. The only change to the returned portfolio
   is that the placed orders are added to `orders`, which stays sorted by slot.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/sim/sizing.py` | create (line 1) | `RejectReason`, `Pick`, `Rejection`, `SizingResult`, `size_picks` and private helpers |
| `engine/tests/test_sim_sizing.py` | create (line 1) | 36 tests (parametrized cases counted individually) for every R2 rule, with hand-checked arithmetic |

## Implementation Steps

### Step 1: Create the sizing module
**File:** `engine/src/seer_engine/sim/sizing.py:1` (new file)
**Change:** New pure module. It imports only `seer_engine.dates` (measured import-clean) and
`seer_engine.sim.model`, and never `seer_engine.bars` (invariant 3). It iterates no sets in output
paths: `taken` and `seen` are used only for membership tests (invariant 4).
**Code:**
```python
"""Whole-share sizing of ranked picks into free slots (design §5, handover §3 sizing row).

Each night, after session S's close, a strategy hands over its ranked picks for the next session.
``size_picks`` turns them into pending bracket orders:

* slot budget = equity ÷ 4, using the equity at the last snapshot (S's close), so it is recomputed
  every session;
* budget = min(slot budget, cash − buy cost of every pending order already placed for that
  session), so a position that has risen in value cannot lend new picks cash that does not exist;
* shares = floor(budget / (limit × 1.001)), so the buy cost including the 0.1 % charge fits;
* fewer than 1 share → rejected ``lt_one_share``; a symbol already live (open or pending) or
  repeated in the picks → rejected ``held`` (no adding to a holding); no free slot → ``no_slot``.

Picks are handled in the given order (the strategy's rank), and each placed pick takes the lowest
free slot. Pure and deterministic: no I/O, no clock, no randomness, Decimal only.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import ROUND_FLOOR, Decimal
from typing import Literal

from seer_engine.dates import is_session
from seer_engine.sim.model import COST_RATE, SLOTS, Order, Portfolio, buy_cost, q

RejectReason = Literal["no_slot", "held", "lt_one_share"]

_ONE_PLUS_COST = Decimal(1) + COST_RATE


def _price(name: str, value: object) -> Decimal:
    """``value`` as a positive 4-dp Decimal; anything that is not a Decimal is a TypeError."""
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be a Decimal, got {type(value).__name__}")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite, got {value!r}")
    v = q(value)
    if v <= 0:
        raise ValueError(f"{name} must be > 0, got {value!r}")
    return v


@dataclass(frozen=True, slots=True)
class Pick:
    """One ranked pick for the next session: the bracket a strategy proposes, before sizing."""

    symbol: str
    last_price: Decimal
    limit_price: Decimal
    tp_price: Decimal
    sl_price: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str):
            raise TypeError(f"symbol must be a str, got {type(self.symbol).__name__}")
        if not self.symbol:
            raise ValueError("symbol must be non-empty")
        for name in ("last_price", "limit_price", "tp_price", "sl_price"):
            object.__setattr__(self, name, _price(name, getattr(self, name)))
        if not self.sl_price < self.limit_price < self.tp_price:
            raise ValueError(
                f"{self.symbol}: need sl < limit < tp, got "
                f"sl={self.sl_price} limit={self.limit_price} tp={self.tp_price}"
            )


@dataclass(frozen=True, slots=True)
class Rejection:
    symbol: str
    reason: RejectReason


@dataclass(frozen=True, slots=True)
class SizingResult:
    portfolio: Portfolio
    placed: tuple[Order, ...]
    rejected: tuple[Rejection, ...]


def _check_session_date(portfolio: Portfolio, session_date: object) -> None:
    if not isinstance(session_date, date) or isinstance(session_date, datetime):
        raise TypeError(f"session_date must be a date, got {type(session_date).__name__}")
    if not is_session(session_date):
        raise ValueError(f"{session_date} is not an NYSE session")
    if portfolio.last_session is not None and session_date <= portfolio.last_session:
        raise ValueError(
            f"session_date {session_date} must be after the last stepped session "
            f"{portfolio.last_session}"
        )


def _whole_shares(budget: Decimal, limit_price: Decimal) -> int:
    """floor(budget / (limit × 1.001)), never letting limit × shares × 1.001 exceed ``budget``."""
    if budget <= 0:
        return 0
    unit = limit_price * _ONE_PLUS_COST
    shares = int((budget / unit).to_integral_value(rounding=ROUND_FLOOR))
    # Decimal division rounds to 28 significant digits; a quotient a hair under an integer could
    # round up to it. Step back so the exact cost always fits.
    while shares > 0 and unit * shares > budget:
        shares -= 1
    return max(shares, 0)


def size_picks(portfolio: Portfolio, picks: Sequence[Pick], session_date: date) -> SizingResult:
    """Size ``picks`` (in rank order) into ``portfolio``'s free slots for ``session_date``.

    ``session_date`` is the session the brackets are placed for (the next session after the
    portfolio's last stepped one). Returns the portfolio with the new pending orders added, the
    orders placed (in pick order), and the picks rejected (in pick order). Cash is not touched:
    a pending order reserves cash only through the sizing cap, and pays at fill.
    """
    if not isinstance(portfolio, Portfolio):
        raise TypeError(f"portfolio must be a Portfolio, got {type(portfolio).__name__}")
    _check_session_date(portfolio, session_date)
    picks = tuple(picks)
    for p in picks:
        if not isinstance(p, Pick):
            raise TypeError(f"picks must be Pick values, got {type(p).__name__}")
    pending = portfolio.pending_orders()
    for o in pending:
        if o.session_date != session_date:
            raise ValueError(
                f"pending order {o.symbol} is for {o.session_date}, not {session_date}; "
                f"step that session before sizing"
            )
    if not picks:
        return SizingResult(portfolio=portfolio, placed=(), rejected=())

    free = list(portfolio.free_slots())
    taken = set(portfolio.held_symbols())  # every live order, pending included (no adding)
    seen: set[str] = set()
    committed = sum((buy_cost(o.limit_price, o.shares) for o in pending), Decimal(0))
    slot_budget = q(portfolio.equity / SLOTS)

    placed: list[Order] = []
    rejected: list[Rejection] = []
    for pick in picks:
        duplicate = pick.symbol in seen
        seen.add(pick.symbol)
        if duplicate or pick.symbol in taken:
            rejected.append(Rejection(symbol=pick.symbol, reason="held"))
            continue
        if not free:
            rejected.append(Rejection(symbol=pick.symbol, reason="no_slot"))
            continue
        budget = min(slot_budget, portfolio.cash - committed)
        shares = _whole_shares(budget, pick.limit_price)
        if shares < 1:
            rejected.append(Rejection(symbol=pick.symbol, reason="lt_one_share"))
            continue
        order = Order(
            session_date=session_date,
            slot=free.pop(0),
            symbol=pick.symbol,
            last_price=pick.last_price,
            limit_price=pick.limit_price,
            tp_price=pick.tp_price,
            sl_price=pick.sl_price,
            shares=shares,
        )
        placed.append(order)
        committed += buy_cost(order.limit_price, order.shares)

    if not placed:
        return SizingResult(portfolio=portfolio, placed=(), rejected=tuple(rejected))
    orders = tuple(sorted(portfolio.orders + tuple(placed), key=lambda o: o.slot))
    return SizingResult(
        portfolio=replace(portfolio, orders=orders),
        placed=tuple(placed),
        rejected=tuple(rejected),
    )
```
**Impact:** Additive only. Nothing imports this module until phase 4 exports it from
`sim/__init__.py`. Phase 1's purity test covers `seer_engine.sim`. Once phase 4 adds the export,
this module falls under that test too, and it passes: it imports only `dates` and `sim.model`.

### Step 2: Create the sizing tests
**File:** `engine/tests/test_sim_sizing.py:1` (new file)
**Change:** Plain pytest functions in the repo's style (see `test_dates.py`). Every share count and
cost has its arithmetic in a comment. The values were checked with Python `Decimal`:
2500/33.033 = 75.68; 3000/50.05 = 59.94; 47.05/40.04 = 1.175; 7.01/20.02 = 0.35;
11038.12/4 = 2759.53; 2759.53/25.025 = 110.27; 2759.53/40.04 = 68.92; 3125/10.01 = 312.19;
3125/20.02 = 156.09; 2000/10.01 = 199.80; 1000/10.01 = 99.90.
buy_cost(33,75) = 2477.4750; buy_cost(50,59) = 2952.9500; buy_cost(40,1) = 40.0400;
buy_cost(25,110) = 2752.7500; buy_cost(40,68) = 2722.7200; buy_cost(10,312) = 3123.1200;
buy_cost(10,249) = 2492.4900; buy_cost(150,10) = 1501.5000; sell_proceeds(47,40) = 1878.1200.
**Code:**
```python
"""Whole-share sizing of picks into slots (design §5, handover §3 sizing row). No database."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from simkit import D, P, bar, opened, pending, portfolio

from seer_engine.sim.lifecycle import step
from seer_engine.sim.model import buy_cost, new_portfolio, sell_proceeds
from seer_engine.sim.sizing import Pick, Rejection, size_picks

PREV = D("2026-10-02")  # Friday, last stepped session (data_date)
SESSION = D("2026-10-05")  # Monday, the session the picks are placed for
NEXT = D("2026-10-06")


def pick(symbol: str, limit: str, tp: str | None = None, sl: str | None = None) -> Pick:
    lim = P(limit)
    return Pick(
        symbol=symbol,
        last_price=lim,
        limit_price=lim,
        tp_price=P(tp) if tp is not None else lim * Decimal("1.1"),
        sl_price=P(sl) if sl is not None else lim * Decimal("0.9"),
    )


def flat(cash: str = "10000") -> object:
    """A portfolio with no live orders, equity == cash, last stepped on PREV."""
    return portfolio(P(cash), equity=P(cash), last_session=PREV)


# --- zero picks -------------------------------------------------------------------------------


def test_zero_picks_returns_portfolio_unchanged() -> None:
    pf = flat()
    res = size_picks(pf, [], SESSION)
    assert res.portfolio is pf
    assert res.placed == ()
    assert res.rejected == ()


def test_zero_picks_on_full_portfolio_is_fine() -> None:
    pf = portfolio(
        P("1000"),
        opened("AAA", D("2026-10-01"), P("10"), P("11"), P("9"), 10, 2, slot=1),
        opened("BBB", D("2026-10-01"), P("10"), P("11"), P("9"), 10, 2, slot=2),
        opened("CCC", D("2026-10-01"), P("10"), P("11"), P("9"), 10, 2, slot=3),
        opened("DDD", D("2026-10-01"), P("10"), P("11"), P("9"), 10, 2, slot=4),
        equity=P("1400"),
        last_session=PREV,
    )
    assert size_picks(pf, (), SESSION).portfolio is pf


# --- whole shares, equity ÷ 4 ---------------------------------------------------------------


def test_whole_shares_floor_of_equity_quarter_over_limit_with_cost() -> None:
    pf = flat("10000")
    res = size_picks(pf, [pick("AAA", "33", tp="36", sl="31")], SESSION)
    # slot budget = 10000 / 4 = 2500; 2500 / (33 × 1.001) = 2500 / 33.033 = 75.68 → 75 (floor, not 76)
    (o,) = res.placed
    assert o.symbol == "AAA"
    assert o.shares == 75
    assert o.slot == 1
    assert o.session_date == SESSION
    assert o.status == "pending"
    assert (o.limit_price, o.tp_price, o.sl_price, o.last_price) == (P("33"), P("36"), P("31"), P("33"))
    assert o.fill_date is None and o.days_held == 0
    # The buy cost fits the budget: 75 × 33 × 1.001 = 2477.4750 <= 2500.
    assert buy_cost(o.limit_price, o.shares) == P("2477.4750")
    assert res.rejected == ()
    # Sizing reserves nothing in cash or equity; it only adds the pending order.
    assert res.portfolio.cash == P("10000")
    assert res.portfolio.equity == P("10000")
    assert res.portfolio.last_session == PREV
    assert res.portfolio.marks == pf.marks
    assert res.portfolio.orders == (o,)


def test_cost_buffer_drops_a_share() -> None:
    # equity 4000 → slot 1000. Without the 0.1 % buffer 1000 / 10 = 100 shares would cost 1001.00.
    # With it: 1000 / 10.01 = 99.90 → 99; 99 × 10 × 1.001 = 990.9900.
    res = size_picks(flat("4000"), [pick("AAA", "10")], SESSION)
    assert res.placed[0].shares == 99
    assert buy_cost(P("10"), 99) == P("990.9900")


def test_fresh_portfolio_without_last_session() -> None:
    pf = new_portfolio(P("8000"))
    res = size_picks(pf, [pick("AAA", "10")], SESSION)
    # 8000 / 4 = 2000; 2000 / 10.01 = 199.80 → 199
    assert res.placed[0].shares == 199
    assert res.placed[0].slot == 1


# --- slots ------------------------------------------------------------------------------------


def test_picks_take_lowest_free_slots_in_pick_order_then_no_slot() -> None:
    picks = [pick("AAA", "10"), pick("BBB", "20"), pick("CCC", "50"), pick("DDD", "100"), pick("EEE", "5")]
    res = size_picks(flat("10000"), picks, SESSION)
    # Slot budget 2500 each, and cash never binds:
    #   AAA 2500 / 10.01  = 249.75 → 249, cost 2492.49, committed 2492.49
    #   BBB 2500 / 20.02  = 124.88 → 124, cost 2482.48, committed 4974.97
    #   CCC 2500 / 50.05  =  49.95 →  49, cost 2452.45, committed 7427.42 (cash left 2572.58 > 2500)
    #   DDD 2500 / 100.10 =  24.98 →  24, cost 2402.40
    #   EEE no free slot
    assert [(o.symbol, o.slot, o.shares) for o in res.placed] == [
        ("AAA", 1, 249),
        ("BBB", 2, 124),
        ("CCC", 3, 49),
        ("DDD", 4, 24),
    ]
    assert res.rejected == (Rejection("EEE", "no_slot"),)
    assert res.portfolio.free_slots() == ()
    assert [o.slot for o in res.portfolio.orders] == [1, 2, 3, 4]


def test_lowest_free_slot_skips_occupied_slots() -> None:
    pf = portfolio(
        P("10000"),
        opened("XOM", D("2026-10-01"), P("100"), P("110"), P("95"), 10, 2, slot=1),
        opened("CVX", D("2026-10-01"), P("150"), P("165"), P("140"), 10, 2, slot=3),
        equity=P("12500"),
        last_session=PREV,
    )
    res = size_picks(pf, [pick("AAA", "10"), pick("BBB", "20"), pick("CCC", "30")], SESSION)
    # slot budget 12500 / 4 = 3125
    #   AAA 3125 / 10.01 = 312.19 → 312, cost 3123.12, cash left 6876.88 > 3125
    #   BBB 3125 / 20.02 = 156.09 → 156
    assert [(o.symbol, o.slot, o.shares) for o in res.placed] == [("AAA", 2, 312), ("BBB", 4, 156)]
    assert res.rejected == (Rejection("CCC", "no_slot"),)
    assert [(o.slot, o.symbol) for o in res.portfolio.orders] == [(1, "XOM"), (2, "AAA"), (3, "CVX"), (4, "BBB")]


def test_pick_order_decides_who_gets_the_lower_slot() -> None:
    res = size_picks(flat(), [pick("BBB", "20"), pick("AAA", "10")], SESSION)
    assert [(o.symbol, o.slot) for o in res.placed] == [("BBB", 1), ("AAA", 2)]


# --- the cash cap -----------------------------------------------------------------------------


def _appreciated() -> object:
    # XOM: 90 shares bought at 100, now marked near 133.33. Equity 15000 = 3000 cash + 12000 stock,
    # so equity / 4 = 3750 is more than the 3000 cash actually free.
    return portfolio(
        P("3000"),
        opened("XOM", D("2026-09-30"), P("100"), P("130"), P("90"), 90, 3, slot=1),
        equity=P("15000"),
        last_session=PREV,
    )


def test_cash_cap_when_appreciated_holding_lifts_equity_quarter_above_cash() -> None:
    picks = [pick("AAA", "50", tp="55", sl="45"), pick("BBB", "40", tp="44", sl="36"), pick("CCC", "20")]
    res = size_picks(_appreciated(), picks, SESSION)
    #   AAA budget = min(3750, 3000)          = 3000;  3000 / 50.05 = 59.94 → 59 (uncapped: 74)
    #       cost 59 × 50 × 1.001 = 2952.95;  committed 2952.95
    #   BBB budget = min(3750, 3000 − 2952.95) = 47.05; 47.05 / 40.04 = 1.18 → 1
    #       cost 40.04;                    committed 2992.99
    #   CCC budget = min(3750, 3000 − 2992.99) = 7.01;  7.01 / 20.02 = 0.35 → ineligible
    assert [(o.symbol, o.slot, o.shares) for o in res.placed] == [("AAA", 2, 59), ("BBB", 3, 1)]
    assert res.rejected == (Rejection("CCC", "lt_one_share"),)
    assert res.portfolio.free_slots() == (4,)
    committed = sum(buy_cost(o.limit_price, o.shares) for o in res.placed)
    assert committed == P("2992.9900")
    assert committed <= res.portfolio.cash == P("3000")


def test_cash_cap_counts_pending_orders_placed_by_an_earlier_call() -> None:
    first = size_picks(_appreciated(), [pick("AAA", "50", tp="55", sl="45")], SESSION)
    assert first.placed[0].shares == 59
    # Second call the same night: the pending AAA (cost 2952.95) is already committed.
    second = size_picks(first.portfolio, [pick("BBB", "40", tp="44", sl="36")], SESSION)
    assert [(o.symbol, o.slot, o.shares) for o in second.placed] == [("BBB", 3, 1)]
    assert [o.symbol for o in second.portfolio.pending_orders()] == ["AAA", "BBB"]


def test_no_cash_left_rejects_lt_one_share() -> None:
    pf = portfolio(
        P("0"),
        opened("XOM", D("2026-10-01"), P("100"), P("110"), P("95"), 100, 2, slot=1),
        equity=P("10000"),
        last_session=PREV,
    )
    res = size_picks(pf, [pick("AAA", "10")], SESSION)
    assert res.placed == ()
    assert res.rejected == (Rejection("AAA", "lt_one_share"),)
    assert res.portfolio is pf


# --- ineligible -------------------------------------------------------------------------------


def test_ineligible_pick_does_not_consume_a_slot() -> None:
    picks = [pick("BRK.A", "700000", tp="770000", sl="630000"), pick("AAA", "10")]
    res = size_picks(flat("10000"), picks, SESSION)
    # 2500 / 700700 = 0.0036 → 0 shares; AAA still gets slot 1 with 2500 / 10.01 = 249.75 → 249
    assert res.rejected == (Rejection("BRK.A", "lt_one_share"),)
    assert [(o.symbol, o.slot, o.shares) for o in res.placed] == [("AAA", 1, 249)]


# --- no adding, duplicates --------------------------------------------------------------------


def test_no_adding_to_open_or_pending_holding() -> None:
    pf = portfolio(
        P("10000"),
        opened("XOM", D("2026-10-01"), P("100"), P("110"), P("95"), 10, 2, slot=1),
        pending("CVX", SESSION, P("150"), P("165"), P("140"), 10, slot=2),
        equity=P("10000"),
        last_session=PREV,
    )
    res = size_picks(pf, [pick("XOM", "105"), pick("CVX", "151"), pick("AAA", "10")], SESSION)
    # Pending CVX commits 150 × 10 × 1.001 = 1501.50; cash left 8498.50 > 2500, so AAA gets 249.
    assert res.rejected == (Rejection("XOM", "held"), Rejection("CVX", "held"))
    assert [(o.symbol, o.slot, o.shares) for o in res.placed] == [("AAA", 3, 249)]
    assert buy_cost(P("150"), 10) == P("1501.5000")


def test_duplicate_pick_is_rejected_held() -> None:
    res = size_picks(flat("10000"), [pick("AAA", "10"), pick("AAA", "12"), pick("BBB", "20")], SESSION)
    # AAA 249 (cost 2492.49); cash left 7507.51 > 2500, so BBB: 2500 / 20.02 = 124.88 → 124
    assert [(o.symbol, o.slot, o.shares) for o in res.placed] == [("AAA", 1, 249), ("BBB", 2, 124)]
    assert res.rejected == (Rejection("AAA", "held"),)


def test_duplicate_of_an_ineligible_pick_is_still_held() -> None:
    picks = [pick("BRK.A", "700000", tp="770000", sl="630000"), pick("BRK.A", "700000", tp="770000", sl="630000")]
    res = size_picks(flat(), picks, SESSION)
    assert res.rejected == (Rejection("BRK.A", "lt_one_share"), Rejection("BRK.A", "held"))


def test_held_is_reported_before_no_slot() -> None:
    pf = portfolio(
        P("1000"),
        opened("XOM", D("2026-10-01"), P("10"), P("11"), P("9"), 10, 2, slot=1),
        opened("CVX", D("2026-10-01"), P("10"), P("11"), P("9"), 10, 2, slot=2),
        opened("KO", D("2026-10-01"), P("10"), P("11"), P("9"), 10, 2, slot=3),
        opened("PEP", D("2026-10-01"), P("10"), P("11"), P("9"), 10, 2, slot=4),
        equity=P("1400"),
        last_session=PREV,
    )
    res = size_picks(pf, [pick("XOM", "10"), pick("AAA", "10")], SESSION)
    assert res.rejected == (Rejection("XOM", "held"), Rejection("AAA", "no_slot"))
    assert res.portfolio is pf


# --- slot reuse after an exit and an expiry, through step --------------------------------------


def test_slots_freed_by_exit_and_expiry_are_reused_next_night() -> None:
    pf = portfolio(
        P("5000"),
        opened("AAA", D("2026-10-01"), P("50"), P("55"), P("47"), 40, 2, slot=1),
        pending("BBB", SESSION, P("30"), P("33"), P("28"), 80, slot=2),
        opened("CCC", D("2026-10-01"), P("20"), P("22"), P("19"), 100, 2, slot=3),
        opened("DDD", D("2026-10-02"), P("10"), P("11"), P("9.5"), 200, 1, slot=4),
        equity=P("10000"),
        last_session=PREV,
    )
    bars = {
        # AAA: open 49 is above SL 47 and below TP 55; low 46.5 <= 47 → SL exit at 47.
        "AAA": bar("AAA", SESSION, P("49"), P("49.5"), P("46.5"), P("47.5")),
        # BBB: low 30 is not < limit 30 → not filled → expires; slot 2 freed.
        "BBB": bar("BBB", SESSION, P("30.5"), P("31"), P("30"), P("30.8")),
        "CCC": bar("CCC", SESSION, P("20.5"), P("21"), P("20.2"), P("20.8")),
        "DDD": bar("DDD", SESSION, P("10.2"), P("10.5"), P("10.0"), P("10.4")),
    }
    stepped = step(pf, SESSION, bars)
    # cash 5000 + sell_proceeds(47, 40) = 5000 + 1878.12 = 6878.12
    # equity 6878.12 + 100 × 20.8 + 200 × 10.4 = 6878.12 + 2080 + 2080 = 11038.12
    assert sell_proceeds(P("47"), 40) == P("1878.1200")
    assert stepped.portfolio.cash == P("6878.1200")
    assert stepped.portfolio.equity == P("11038.1200")
    assert stepped.portfolio.free_slots() == (1, 2)

    picks = [pick("CCC", "21"), pick("EEE", "25", tp="27.5", sl="23"), pick("FFF", "40", tp="44", sl="37"), pick("GGG", "15")]
    res = size_picks(stepped.portfolio, picks, NEXT)
    # equity ÷ 4 recomputed from the new snapshot: 11038.12 / 4 = 2759.53
    #   CCC still open → held
    #   EEE min(2759.53, 6878.12)          → 2759.53 / 25.025 = 110.27 → 110, cost 2752.75
    #   FFF min(2759.53, 6878.12 − 2752.75 = 4125.37) → 2759.53 / 40.04 = 68.92 → 68, cost 2722.72
    #   GGG no free slot
    assert [(o.symbol, o.slot, o.shares, o.session_date) for o in res.placed] == [
        ("EEE", 1, 110, NEXT),
        ("FFF", 2, 68, NEXT),
    ]
    assert res.rejected == (Rejection("CCC", "held"), Rejection("GGG", "no_slot"))
    assert buy_cost(P("25"), 110) == P("2752.7500")
    assert buy_cost(P("40"), 68) == P("2722.7200")
    assert [(o.slot, o.symbol) for o in res.portfolio.orders] == [(1, "EEE"), (2, "FFF"), (3, "CCC"), (4, "DDD")]
    assert res.portfolio.cash == P("6878.1200")


# --- determinism ------------------------------------------------------------------------------


def test_same_inputs_give_identical_results() -> None:
    picks = [pick("AAA", "50", tp="55", sl="45"), pick("BBB", "40", tp="44", sl="36"), pick("CCC", "20")]
    assert size_picks(_appreciated(), picks, SESSION) == size_picks(_appreciated(), picks, SESSION)


# --- Pick validation --------------------------------------------------------------------------


def test_pick_quantizes_prices_to_4dp() -> None:
    p = Pick("AAA", Decimal("10.00005"), Decimal("10.00005"), Decimal("11"), Decimal("9"))
    assert p.limit_price == Decimal("10.0001")
    assert p.last_price == Decimal("10.0001")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"last_price": 10.0},
        {"limit_price": 10},
        {"tp_price": "11"},
        {"sl_price": None},
    ],
)
def test_pick_rejects_non_decimal_prices(kwargs: dict[str, object]) -> None:
    base: dict[str, object] = {
        "symbol": "AAA",
        "last_price": P("10"),
        "limit_price": P("10"),
        "tp_price": P("11"),
        "sl_price": P("9"),
    }
    with pytest.raises(TypeError):
        Pick(**{**base, **kwargs})


@pytest.mark.parametrize(
    ("limit", "tp", "sl"),
    [
        ("10", "11", "10"),  # sl == limit
        ("10", "11", "10.5"),  # sl > limit
        ("10", "10", "9"),  # tp == limit
        ("10", "9.5", "9"),  # tp < limit
        ("10", "11", "0"),  # sl not positive
    ],
)
def test_pick_requires_sl_below_limit_below_tp(limit: str, tp: str, sl: str) -> None:
    with pytest.raises(ValueError):
        Pick("AAA", P(limit), P(limit), P(tp), P(sl))


def test_pick_rejects_non_finite_and_empty_symbol() -> None:
    with pytest.raises(ValueError):
        Pick("AAA", P("10"), Decimal("NaN"), P("11"), P("9"))
    with pytest.raises(ValueError):
        Pick("", P("10"), P("10"), P("11"), P("9"))
    with pytest.raises(TypeError):
        Pick(None, P("10"), P("10"), P("11"), P("9"))  # type: ignore[arg-type]


# --- size_picks validation --------------------------------------------------------------------


@pytest.mark.parametrize(
    "session_date",
    [
        D("2026-10-03"),  # Saturday
        D("2026-11-26"),  # Thanksgiving
    ],
)
def test_session_date_must_be_an_nyse_session(session_date) -> None:
    with pytest.raises(ValueError):
        size_picks(flat(), [pick("AAA", "10")], session_date)


@pytest.mark.parametrize("session_date", [PREV, D("2026-10-01")])
def test_session_date_must_be_after_last_session(session_date) -> None:
    with pytest.raises(ValueError):
        size_picks(flat(), [], session_date)


def test_session_date_must_be_a_date_not_datetime() -> None:
    with pytest.raises(TypeError):
        size_picks(flat(), [], datetime(2026, 10, 5, 13, 30))


def test_picks_must_be_pick_values() -> None:
    with pytest.raises(TypeError):
        size_picks(flat(), [("AAA", P("10"))], SESSION)  # type: ignore[list-item]


def test_stale_pending_order_for_another_session_is_an_error() -> None:
    pf = portfolio(
        P("10000"),
        pending("CVX", PREV, P("150"), P("165"), P("140"), 10, slot=1),
        equity=P("10000"),
        last_session=D("2026-10-01"),
    )
    with pytest.raises(ValueError):
        size_picks(pf, [pick("AAA", "10")], SESSION)
```
**Impact:** Adds 36 test cases (parametrized cases counted individually). They need no database
and run in well under a second. `test_slots_freed_by_exit_and_expiry_are_reused_next_night` also
exercises phase 1's `step` (SL exit, expiry, cash and equity snapshot). A failure there with the
sizing assertions intact means a lifecycle bug, which phase 1 owns.

## Verification

**Environment note (index Invariant 1):** phase 1 Step 0 creates the worktree venv. If it is missing, run
`cd /home/miftah/.worktrees/seer/engine-fill-simulator && python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'`
(`python3` is pyenv's 3.11.0). Never run the tests with `/home/miftah/seer/engine/.venv`: it is an editable
install of `/home/miftah/seer` and tests main's tree, not this worktree.

**Build:** `cd /home/miftah/.worktrees/seer/engine-fill-simulator && engine/.venv/bin/python -c "import seer_engine.sim.sizing, sys; assert not {'psycopg','requests','yfinance'} & set(sys.modules)"`
**Tests:** `docker start seer-pg; cd /home/miftah/.worktrees/seer/engine-fill-simulator && PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`
(run `engine/.venv/bin/pytest engine/tests/test_sim_sizing.py -q` first, for fast iteration).
**Manual check:** `grep -nE "datetime\.now|date\.today|import time|random|seer_engine\.bars|float\(" engine/src/seer_engine/sim/sizing.py` prints nothing. (The `datetime` import exists only for the `isinstance` check.)
**Exit criteria:** `test_sim_sizing.py` passes (36 cases). The full engine suite is green with
**0 skipped** (216 baseline + phase 1's tests + 36). `sim/__init__.py`, `model.py`, `lifecycle.py`
and `simkit.py` are unchanged by this phase's commit.

## Handoffs

- **Phase 4 (R4):** export `Pick`, `RejectReason`, `Rejection`, `SizingResult`, `size_picks` from
  `seer_engine.sim.__init__` and add them to `__all__`. Document the behavioural contract above in
  `engine/package_readme.md`: rank order, the lowest free slot, `held` before `no_slot`, a
  rejection never consumes a slot, a duplicate pick is `held` even when its first occurrence was
  `lt_one_share`, and a stale pending order raises `ValueError`. Show the P3/P4 nightly loop as
  `step(S)` → `size_picks(..., next_session(S))`.
- **Phase 1 (R1/R3), assumptions to confirm at reconciliation:**
  - `Portfolio.pending_orders()` and `free_slots()` exist as methods.
  - `free_slots()` returns ascending ints from 1 to 4.
  - `Portfolio.__post_init__`, if it exists, accepts `dataclasses.replace(..., orders=sorted_by_slot)`.
  - `simkit.portfolio(cash, *orders, equity=..., last_session=...)` without `marks` builds a valid portfolio with open orders in it.
  - `simkit.bar`, `opened` and `pending` accept `Decimal` price arguments.
  - `step` sets `portfolio.equity` to the snapshot equity.
  All confirmed at reconciliation against phase 1's code blocks (scratch run: 36 passed). `held` uses
  `Portfolio.held_symbols()`, so phase 1 and phase 2 share one definition of "held".
- **Not done here (no R):** quantization of `Pick` prices is lenient: it rounds to 4 dp and does
  not reject extra precision. Tightening that to a strict check is a separate decision.

## Rollback

Delete `engine/src/seer_engine/sim/sizing.py` and `engine/tests/test_sim_sizing.py`, or
`git revert <phase-2 sha>`. No other file is touched. Phase 4's exports depend on this module, so
reverting phase 2 after phase 4 has landed means reverting phase 4's sizing exports too.
