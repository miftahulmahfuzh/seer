# Phase 3: Split recompute for live orders

**Plan set:** `ENGINE_FILL_SIMULATOR_PLAN.md`
**Analysis:** `20261003-134417-F7S2_code_analyzer.md`
**Satisfies:** R5 — the pure split-recompute function for live orders (design §8 "open orders recomputed"; handover §4 "P2 provides the pure function; P4 calls it"), forward and reverse
**Depends on:** Phase 1
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/sim/` (`seer_engine.sim.split_adjust`)

---

## Goal

After this phase, `seer_engine.sim.split_adjust.apply_split(portfolio, symbol, factor, session_date)`
rewrites a portfolio's live orders and mark for one symbol into post-split units when a split
executes. It handles forward and reverse splits, pays cash in lieu for an open position's
fractional share, expires a pending order that floors to 0 shares, and reports one event per
affected order. A test file proves every rule by hand, and also shows that a split followed by
`step` on adjusted bars produces the same economic P/L.

## Interface Contract

**Deletes:** nothing
**Renames:** nothing
**Creates:**
- `seer_engine.sim.split_adjust.apply_split(portfolio: Portfolio, symbol: str, factor: Decimal, session_date: date) -> tuple[Portfolio, tuple[Event, ...]]` (`engine/src/seer_engine/sim/split_adjust.py`). This is the exact signature in the index's Shared API contract.
- Private helpers in the same module, which are not public API and not exported: `_q_exact`, `_split_ratio`, `_check_session`, `_rescale_price`, `_split_shares`, `_rescale_order`, `_MAX_SPLIT_DENOMINATOR = 1_000_000`, `_RATIO_TOLERANCE = Fraction(1, 10**20)`, `_QUANTA_PER_UNIT`.
- `engine/tests/test_sim_split.py` (35 tests counting parametrize cases).

**Signature changes:** none

**Behaviour of `apply_split` (what P4, the phase 4 docs and the reconciler can rely on):**

| Input | Result |
|---|---|
| `factor` not a `Decimal` (including `int`, `float`, `str`, `bool`, `None`) | `TypeError` |
| `factor` ≤ 0, NaN, ±Infinity, == 1, or not within a 1e-20 relative distance of a fraction with a denominator ≤ 1,000,000 | `ValueError` |
| `portfolio` not a `Portfolio`; `symbol` not a `str`; `session_date` not a `date` or is a `datetime` | `TypeError` |
| `symbol == ""`; `session_date` not an NYSE session (`dates.is_session`); `session_date <= portfolio.last_session` | `ValueError` |
| A rescaled price of a live order (last, limit, TP, SL, fill) or the rescaled mark rounds to 0 at 4 dp, or the rescaled SL rounds to ≥ the rescaled TP | `ValueError` naming the symbol and slot, raised before anything is built, so the input portfolio is untouched (index Decisions, "Split leaves prices 4 dp cannot hold") |
| No live order and no mark for `symbol` | returns `(portfolio, ())`, the **same object** |
| Live order of `symbol`, pending, `floor(shares × factor) ≥ 1` | prices `q(p / factor)` (last, limit, TP, SL), `shares = floor(shares × factor)`, remainder dropped (nothing is held), `Event(kind="split", cash_usd=None)` |
| Live order of `symbol`, pending, floors to 0 | removed. `Event(kind="expire", order=replace(order, status="expired"))`, with the order kept in pre-split units |
| Live order of `symbol`, open, floors to ≥ 1 | prices `q(p / factor)` (last, limit, TP, SL, fill), `shares = floor(...)`. Cash in lieu `q(fraction × adjusted mark)` is added to `cash`. `Event(kind="split", cash_usd=in_lieu)`, where `in_lieu` is `Decimal("0.0000")` when there is no remainder. `fill_date`, `days_held`, `status`, `slot` and `session_date` are unchanged |
| Live order of `symbol`, open, floors to 0 | removed and paid out entirely in lieu: `Event(kind="exit", forced=True, cash_usd=in_lieu)`. The order is in **pre-split units** with `status="closed"`, `exit_date=session_date`, `exit_price=<mark before rescale>`, `exit_reason="time"`, `days_held` unchanged (an exit before session S trades, like any exit at the open), and `pnl_usd = in_lieu − buy_cost(fill_price, shares)`. That is the same rule as `close_unpriced`: `pnl_usd = event cash_usd − buy_cost`, so Σ `pnl_usd` reconciles with cash. The only difference is that cash in lieu carries no sell cost. The mark is dropped. Phase 1's `Order` validation accepts this order (shares ≥ 1, sl < tp, fill and exit fields set, days_held ≥ 1), and the test proves it |
| `marks` | the symbol's mark becomes `q(mark / factor)` (dropped only in the floor-to-0 open case). Other marks are untouched |
| Not changed | `equity`, `last_session`, every order of another symbol (same objects), the order of `orders` (slot) |
| Events | one per live order of `symbol`, in slot order |

All arithmetic on the ratio is exact (`fractions.Fraction`). The result equals `q(p / factor)` and
`floor(shares × factor)` for the true ratio, so a 28-digit `Split.factor` for a 1-for-3 still gives
`floor(300 × 1/3) = 100`. Naive `Decimal` arithmetic gives 99, which was measured.

**Requires (from earlier phases):** Phase 1 has landed, with these items exactly as the index's Shared API contract states them:
- `seer_engine.prices.PRICE_QUANTUM` (`Decimal("0.0001")`) and `seer_engine.prices.Bar(symbol, date, open, high, low, close, volume)`.
- `seer_engine.sim.model`: `Order` (fields and defaults as in the contract, frozen and slotted, so `dataclasses.replace` works), `Portfolio` (fields `cash, equity, orders, marks, last_session`; methods `mark(symbol) -> Decimal | None` and `free_slots()`), `Event(session_date, kind, order, forced=False, cash_usd=None)`, and `buy_cost(price, shares)` = `q(price × shares × 1.001)`.
- `seer_engine.sim.lifecycle.step(portfolio, session_date, bars)` behaves as the plan Decisions say: a TP exit at the TP price on `high > TP`, a fill at the limit when `low < limit <= open`, `cash -= buy_cost` on a fill, `cash += sell_proceeds` on an exit, `pnl_usd = sell_proceeds − buy_cost` computed from the order's own `fill_price` and `shares`, and a snapshot equity of `cash + Σ shares × close`. The three end-to-end tests depend on this.
- If `Order.__post_init__` or `Portfolio.__post_init__` validates its fields, it accepts these states: the orders this phase builds (the test data always has sl < fill ≤ limit < tp and limit ≤ last), an `expired` order with only `status` changed, and a `closed` order carrying `exit_date`, `exit_price`, `exit_reason` and `pnl_usd`.
- `engine/tests/simkit.py` exports `D(str) -> date` and `P(str) -> Decimal` (quantized). Those are the only two helpers this phase imports from it. Orders, portfolios and bars are built straight from the contract types, so the tests do not depend on how `pending`, `opened`, `portfolio` or `bar` take their arguments.

**Leaves alone (owned by others):** `engine/src/seer_engine/sim/__init__.py` (phase 1 creates it; phase 4 adds the `apply_split` export), `sim/model.py` and `sim/lifecycle.py` (phase 1), `sim/sizing.py` (phase 2), `engine/tests/simkit.py` (phase 1), `seer_engine/prices.py` and `bars.py` (phase 1), `seer_engine/splits.py` (out of scope; it is only *imported* by the test, to take `Split.factor`), `engine/package_readme.md` and `docs/ROADMAP.md` (phase 4).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/sim/split_adjust.py` | create (whole file, line 1) | `apply_split` plus private exact-ratio helpers |
| `engine/tests/test_sim_split.py` | create (whole file, line 1) | forward 10:1 and 3:2, reverse 1:32 and 1:3, open and pending, floor-to-0 on pending and open, unaffected symbols, marks, validation, determinism, 3 end-to-end tests through `step` |

No other file changes. `sim/__init__.py` is **not** edited, so `apply_split` is imported from `seer_engine.sim.split_adjust` directly until phase 4 re-exports it.

## Implementation Steps

### Step 1: Create the split-recompute module
**File:** `engine/src/seer_engine/sim/split_adjust.py:1` (new file)
**Change:** Add `apply_split` and its private helpers. Imports are `fractions`, `dataclasses`, `datetime`, `decimal`, `seer_engine.dates`, `seer_engine.prices` and `seer_engine.sim.model`. All of them are inside the purity allowlist (invariant 3: no `seer_engine.bars`, `psycopg`, `requests` or `yfinance`). The module reads no clock, uses no randomness, does no I/O and does not log.

Design notes, for the reviewer:
- **Why `Fraction`.** `Split.factor` (`splits.py:47`) for a 1-for-3 split is `Decimal(1)/Decimal(3)` = `0.3333333333333333333333333333`. `Decimal(300) * that` is `99.99999999999999999999999999`, and its floor is 99. That was measured with the engine venv. The factor is therefore read as the nearest fraction with a denominator ≤ 1,000,000 (which recovers 1/3 exactly), and any other factor (for example `1.00000000001`) is rejected. Prices are then computed exactly as `p / ratio` and rounded half-up to 4 dp in integer arithmetic (`_q_exact`), so there is no double rounding.
- **Open position flooring to 0** is not covered by the index Decisions, and it is realistic: about $300 slots in a cheap stock under a 1-for-32 split. Decision: the whole position is paid out in lieu, like a broker, and closes with a forced `exit` event. The event stays in pre-split units, so the `orders` row is internally consistent (`shares > 0`, fill and exit in the same units). `exit_reason="time"` with `forced=True` is the same signature `close_unpriced` uses for "exit at the last known close without a bar", so P3 counts both the same way. `pnl_usd = in_lieu − buy_cost`, with no sell cost because cash in lieu has no cost, so Σ `pnl_usd` still reconciles with cash for that trade. This is flagged for the reconciler in the Handoffs below.
- **Pending remainders** are not paid. A pending order holds no shares, so it simply orders fewer.
- **Two live orders of one symbol** cannot happen (sizing rejects `held`), but the loop handles any number in slot order, and drops the mark only when no open order of the symbol remains.

**Code:**
```python
"""Split recompute for live orders (design §8; handover §4 and §7).

When a split executes on session S, the nightly job rescales stored bars backwards by
``factor = split_to / split_from`` (the same number as ``seer_engine.splits.Split.factor``: 10 for
a 10-for-1, 1/32 for a 1-for-32 reverse split). A live order's prices and share count were set in
pre-split units, so ``apply_split`` rewrites them in post-split units. Call it after session S-1's
``step`` and before stepping S, with ``session_date = S``.

Rules (plan Decisions, "Reverse-split rounding" and "Split factor convention"):

- Every price of a live order for the symbol (last, limit, TP, SL, fill) becomes ``q(p / factor)``.
- Shares become ``floor(shares * factor)``.
- An open position's fractional remainder is paid as cash in lieu, ``q(fraction * adjusted mark)``,
  with no cost and outside ``pnl_usd``. The amount is on the ``split`` event's ``cash_usd``.
- An open position whose shares floor to 0 is paid out entirely in lieu. It closes with a forced
  ``exit`` event in pre-split units (reason ``time``, exit at the last mark, ``pnl_usd`` = cash in
  lieu - buy cost), so the sum of ``pnl_usd`` still reconciles with cash for that trade.
- A pending order whose shares floor to 0 expires (``expire`` event, the order as it was).
- The symbol's mark is rescaled. Other symbols, ``equity`` and ``last_session`` are untouched.

The ratio is handled as an exact fraction. ``Split.factor`` for a 1-for-3 is the 28-digit Decimal
0.3333…, and 300 x that is 99.999…, which floors to 99 instead of 100. The factor is therefore
read as the nearest fraction with a denominator of at most ``_MAX_SPLIT_DENOMINATOR``; a factor that
is not within ``_RATIO_TOLERANCE`` (relative) of such a fraction is rejected.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction

from seer_engine import dates
from seer_engine.prices import PRICE_QUANTUM
from seer_engine.sim.model import Event, Order, Portfolio, buy_cost

_MAX_SPLIT_DENOMINATOR = 1_000_000
_RATIO_TOLERANCE = Fraction(1, 10**20)
_QUANTA_PER_UNIT = Fraction(1) / Fraction(PRICE_QUANTUM)  # 10_000


def _q_exact(x: Fraction) -> Decimal:
    """``x`` (>= 0) rounded half-up to PRICE_QUANTUM, computed without intermediate rounding."""
    if x < 0:
        raise ValueError(f"negative amount: {x}")
    scaled = x * _QUANTA_PER_UNIT
    quanta = (2 * scaled.numerator + scaled.denominator) // (2 * scaled.denominator)
    return Decimal(quanta) * PRICE_QUANTUM


def _split_ratio(factor: Decimal) -> Fraction:
    """The exact split ratio behind ``factor``. Raises TypeError/ValueError on a bad factor."""
    if not isinstance(factor, Decimal):
        raise TypeError(f"factor must be a Decimal, got {type(factor).__name__}")
    if not factor.is_finite() or factor <= 0:
        raise ValueError(f"factor must be a positive finite Decimal: {factor!r}")
    exact = Fraction(factor)
    ratio = exact.limit_denominator(_MAX_SPLIT_DENOMINATOR)
    if abs(ratio - exact) > ratio * _RATIO_TOLERANCE:
        raise ValueError(f"factor is not a split ratio: {factor!r}")
    if ratio == 1:
        raise ValueError(f"factor 1 is not a split: {factor!r}")
    return ratio


def _check_session(portfolio: Portfolio, session_date: date) -> None:
    if isinstance(session_date, datetime) or not isinstance(session_date, date):
        raise TypeError(f"session_date must be a date, got {type(session_date).__name__}")
    if not dates.is_session(session_date):
        raise ValueError(f"{session_date} is not an NYSE session")
    if portfolio.last_session is not None and session_date <= portfolio.last_session:
        raise ValueError(
            f"split session {session_date} must be after the last stepped session "
            f"{portfolio.last_session}"
        )


def _rescale_price(price: Decimal, ratio: Fraction) -> Decimal:
    return _q_exact(Fraction(price) / ratio)


def _split_shares(shares: int, ratio: Fraction) -> tuple[int, Fraction]:
    """``(floor(shares * ratio), fractional remainder)`` in post-split shares."""
    total = shares * ratio
    whole = total.numerator // total.denominator
    return whole, total - whole


def _rescale_order(order: Order, ratio: Fraction, shares: int) -> Order:
    """``order`` in post-split units. Raises ValueError (before building anything) when the
    rescaled prices cannot be held at 4 dp: a price rounds to 0, or SL rounds up to TP."""
    last = _rescale_price(order.last_price, ratio)
    limit = _rescale_price(order.limit_price, ratio)
    tp = _rescale_price(order.tp_price, ratio)
    sl = _rescale_price(order.sl_price, ratio)
    fill = None if order.fill_price is None else _rescale_price(order.fill_price, ratio)
    if min(last, limit, tp, sl) <= 0 or (fill is not None and fill <= 0) or sl >= tp:
        raise ValueError(
            f"{order.symbol} (slot {order.slot}): a split of ratio {ratio} leaves prices that "
            f"4 dp cannot hold (limit {limit}, tp {tp}, sl {sl}, fill {fill})"
        )
    return replace(
        order,
        shares=shares,
        last_price=last,
        limit_price=limit,
        tp_price=tp,
        sl_price=sl,
        fill_price=fill,
    )


def apply_split(
    portfolio: Portfolio, symbol: str, factor: Decimal, session_date: date
) -> tuple[Portfolio, tuple[Event, ...]]:
    """Rewrite ``symbol``'s live orders and mark in post-split units for a split executing on
    ``session_date``.

    Returns the new portfolio and one event per live order of ``symbol``, in slot order:
    ``split`` (adjusted; ``cash_usd`` = cash in lieu for an open position, None for a pending
    order), ``expire`` (pending order floored to 0 shares) or ``exit`` (open position floored to
    0 shares, ``forced=True``). A portfolio with nothing in ``symbol`` is returned as is, with no
    events. The caller applies each split exactly once (``split_adjustments`` guarantees that).
    """
    if not isinstance(portfolio, Portfolio):
        raise TypeError(f"portfolio must be a Portfolio, got {type(portfolio).__name__}")
    if not isinstance(symbol, str):
        raise TypeError(f"symbol must be a str, got {type(symbol).__name__}")
    if not symbol:
        raise ValueError("empty symbol")
    ratio = _split_ratio(factor)
    _check_session(portfolio, session_date)

    old_mark = portfolio.mark(symbol)
    if old_mark is None and all(o.symbol != symbol for o in portfolio.orders):
        return portfolio, ()
    new_mark = None if old_mark is None else _rescale_price(old_mark, ratio)
    if new_mark is not None and new_mark <= 0:
        raise ValueError(
            f"{symbol}: a split of ratio {ratio} leaves a mark ({old_mark} -> {new_mark}) "
            f"that 4 dp cannot hold"
        )

    kept: list[Order] = []
    events: list[Event] = []
    cash = portfolio.cash
    still_open = False
    liquidated = False
    for order in portfolio.orders:  # Portfolio keeps orders sorted by slot
        if order.symbol != symbol:
            kept.append(order)
            continue
        whole, fraction = _split_shares(order.shares, ratio)
        if order.status == "pending":
            if whole == 0:
                expired = replace(order, status="expired")
                events.append(Event(session_date=session_date, kind="expire", order=expired))
                continue
            adjusted = _rescale_order(order, ratio, whole)
            kept.append(adjusted)
            events.append(Event(session_date=session_date, kind="split", order=adjusted))
            continue
        # status == "open"
        if new_mark is None or order.fill_price is None:
            raise ValueError(f"open {symbol} order in slot {order.slot} has no mark or fill price")
        in_lieu = _q_exact(fraction * Fraction(new_mark))
        cash += in_lieu
        if whole == 0:
            closed = replace(
                order,
                status="closed",
                exit_date=session_date,
                exit_price=old_mark,
                exit_reason="time",
                pnl_usd=in_lieu - buy_cost(order.fill_price, order.shares),
            )
            events.append(
                Event(session_date=session_date, kind="exit", order=closed, forced=True, cash_usd=in_lieu)
            )
            liquidated = True
            continue
        adjusted = _rescale_order(order, ratio, whole)
        kept.append(adjusted)
        still_open = True
        events.append(Event(session_date=session_date, kind="split", order=adjusted, cash_usd=in_lieu))

    drop_mark = liquidated and not still_open
    marks = tuple(
        (s, new_mark if s == symbol else m)
        for s, m in portfolio.marks
        if not (s == symbol and drop_mark)
    )
    new_portfolio = replace(portfolio, cash=cash, orders=tuple(kept), marks=marks)
    return new_portfolio, tuple(events)
```
**Impact:** New module only. Nothing imports it yet, apart from the new test, so no existing behaviour changes. The phase 1 purity test (`test_sim_purity.py`) imports `seer_engine.sim`, which does not import `split_adjust` until phase 4. The module's own imports are inside the allowlist anyway.

### Step 2: Create the tests
**File:** `engine/tests/test_sim_split.py:1` (new file)
**Change:** Plain pytest functions, in the repo's style (`test_bars.py`, `test_dates.py`). The DB is not needed. `seer_engine.splits` is imported only to take a real `Split.factor`. It pulls in `psycopg`, which is fine in the test process because the purity test runs in its own subprocess. Every expected number is hand-worked in a comment and was checked against exact arithmetic. Sessions: Mon 2026-10-05 is `last_session`, Tue 2026-10-06 is the split session, and Sat 2026-10-10 is a non-session. All were checked with `dates.is_session`.

Coverage, mapped to the phase's exit criteria:

| Exit criterion | Test(s) |
|---|---|
| forward 10:1 on open | `test_forward_10_for_1_on_open_position` (includes a half-up price `121.0005 → 12.1001`) |
| forward 3:2 (non-integer factor → floor + cash in lieu) on open | `test_forward_3_for_2_on_open_position_pays_cash_in_lieu` |
| forward 3:2 on pending | `test_forward_3_for_2_on_pending_order` |
| reverse 1:32 on open, with remainder | `test_reverse_1_for_32_on_open_position_with_remainder` |
| reverse 1:3 with remainder → cash in lieu, using real `Split.factor` | `test_reverse_1_for_3_with_split_factor_on_open_and_pending`, `test_reverse_1_for_3_on_pending_order_floors_without_cash` |
| pending floor-to-0 → `expire` | `test_reverse_split_flooring_pending_order_to_zero_expires_it` |
| open floor-to-0 (decision above) | `test_reverse_split_flooring_open_position_to_zero_pays_it_all_in_lieu` |
| symbols not affected, `marks` rescaled | `test_unaffected_symbols_and_order_are_untouched`, `test_symbol_not_held_returns_the_same_portfolio`, plus the `marks` asserts in every forward and reverse test |
| determinism, input not mutated | `test_apply_split_is_deterministic_and_leaves_input_alone` |
| validation | `test_split_that_leaves_prices_unrepresentable_at_4dp_is_a_value_error`, `test_non_decimal_factor_is_a_type_error` (5 cases), `test_bad_factor_is_a_value_error` (7), `test_session_must_follow_last_session`, `test_session_must_be_an_nyse_session`, `test_session_date_must_be_a_date`, `test_no_last_session_accepts_any_session`, `test_bad_symbol` (3), `test_bad_portfolio_is_a_type_error` |
| split then `step` on adjusted bars gives the same economic P/L | `test_10_for_1_then_step_gives_the_same_trade_as_no_split` (pnl, cash and equity are identical to the no-split world: 23.4960 / 1023.4960), `test_1_for_3_then_step_reconciles_cash_with_pnl_and_cash_in_lieu` (economic P/L 2.7403 = pnl_usd 2.6433 + in-lieu 3.1000 − in-lieu basis 3.0030), `test_pending_order_adjusted_by_split_fills_at_the_adjusted_limit` (fills 7 at 33.3333, cash 766.4336) |

**Code:**
```python
"""apply_split: live orders rewritten in post-split units (design §8, plan Decisions).

Every expected number below is worked by hand in the comment next to it. Sessions: Mon 2026-10-05
is the last stepped session, Tue 2026-10-06 is the split's execution session.
"""
from dataclasses import replace
from datetime import datetime
from decimal import Decimal

import pytest

from seer_engine.prices import Bar
from seer_engine.sim.lifecycle import step
from seer_engine.sim.model import Event, Order, Portfolio
from seer_engine.sim.split_adjust import apply_split
from seer_engine.splits import Split
from simkit import D, P

MON = D("2026-10-05")
TUE = D("2026-10-06")
SAT = D("2026-10-10")

TEN_FOR_ONE = Decimal(10)
THREE_FOR_TWO = Decimal(3) / Decimal(2)  # 1.5
ONE_FOR_32 = Decimal(1) / Decimal(32)  # 0.03125, exact
ONE_FOR_3 = Split("ABC", TUE, split_from=Decimal(3), split_to=Decimal(1)).factor  # 0.3333…3 (28 digits)


def _open(symbol, *, slot, last, limit, fill, tp, sl, shares, days_held=1):
    return Order(
        session_date=MON,
        slot=slot,
        symbol=symbol,
        last_price=P(last),
        limit_price=P(limit),
        tp_price=P(tp),
        sl_price=P(sl),
        shares=shares,
        status="open",
        fill_date=MON,
        fill_price=P(fill),
        days_held=days_held,
    )


def _pending(symbol, *, slot, last, limit, tp, sl, shares):
    return Order(
        session_date=TUE,
        slot=slot,
        symbol=symbol,
        last_price=P(last),
        limit_price=P(limit),
        tp_price=P(tp),
        sl_price=P(sl),
        shares=shares,
    )


def _pf(cash, *orders, marks=(), equity=None, last_session=MON):
    return Portfolio(
        cash=P(cash),
        equity=P(equity if equity is not None else cash),
        orders=tuple(sorted(orders, key=lambda o: o.slot)),
        marks=tuple(sorted((s, P(m)) for s, m in marks)),
        last_session=last_session,
    )


def _bar(symbol, d, o, h, l, c):  # noqa: E741
    return Bar(symbol, d, P(o), P(h), P(l), P(c), 1_000_000)


# ---- forward splits ----

def test_forward_10_for_1_on_open_position():
    abc = _open("ABC", slot=2, last="125", limit="121.0005", fill="120", tp="132", sl="114", shares=3)
    pf = _pf("640", abc, marks=[("ABC", "125.5")], equity="1016.5")

    out, events = apply_split(pf, "ABC", TEN_FOR_ONE, TUE)

    adjusted = replace(
        abc,
        shares=30,  # 3 x 10
        last_price=P("12.5"),  # 125 / 10
        limit_price=P("12.1001"),  # 121.0005 / 10 = 12.10005 -> half-up 12.1001
        fill_price=P("12"),  # 120 / 10
        tp_price=P("13.2"),  # 132 / 10
        sl_price=P("11.4"),  # 114 / 10
    )
    assert out.orders == (adjusted,)
    assert out.marks == (("ABC", P("12.55")),)  # 125.5 / 10
    assert out.cash == P("640")  # 30 is whole: no cash in lieu
    assert out.equity == P("1016.5")  # untouched
    assert out.last_session == MON  # untouched
    assert events == (
        Event(session_date=TUE, kind="split", order=adjusted, cash_usd=Decimal("0.0000")),
    )
    # fill date, days held and status survive the split
    assert (adjusted.status, adjusted.fill_date, adjusted.days_held) == ("open", MON, 1)


def test_forward_3_for_2_on_open_position_pays_cash_in_lieu():
    abc = _open("ABC", slot=1, last="102", limit="101", fill="100", tp="110", sl="95", shares=5)
    pf = _pf("500", abc, marks=[("ABC", "104")])

    out, events = apply_split(pf, "ABC", THREE_FOR_TWO, TUE)

    adjusted = replace(
        abc,
        shares=7,  # 5 x 1.5 = 7.5 -> floor 7, remainder 0.5 share
        last_price=P("68"),  # 102 x 2/3
        limit_price=P("67.3333"),  # 101 x 2/3 = 67.3333…
        fill_price=P("66.6667"),  # 100 x 2/3 = 66.6666… -> 66.6667
        tp_price=P("73.3333"),  # 110 x 2/3
        sl_price=P("63.3333"),  # 95 x 2/3
    )
    assert out.orders == (adjusted,)
    assert out.marks == (("ABC", P("69.3333")),)  # 104 x 2/3
    # cash in lieu = q(0.5 x 69.3333) = q(34.66665) = 34.6667, no cost
    assert events == (
        Event(session_date=TUE, kind="split", order=adjusted, cash_usd=P("34.6667")),
    )
    assert out.cash == P("534.6667")  # 500 + 34.6667


def test_forward_3_for_2_on_pending_order():
    xyz = _pending("XYZ", slot=3, last="51", limit="50", tp="55", sl="47.5", shares=5)
    pf = _pf("1000", xyz)

    out, events = apply_split(pf, "XYZ", THREE_FOR_TWO, TUE)

    adjusted = replace(
        xyz,
        shares=7,  # 5 x 1.5 = 7.5 -> 7; a pending order holds nothing, so no cash in lieu
        last_price=P("34"),  # 51 x 2/3
        limit_price=P("33.3333"),  # 50 x 2/3
        tp_price=P("36.6667"),  # 55 x 2/3 = 36.6666…
        sl_price=P("31.6667"),  # 47.5 x 2/3 = 31.6666…
    )
    assert out.orders == (adjusted,)
    assert adjusted.status == "pending" and adjusted.fill_price is None
    assert events == (Event(session_date=TUE, kind="split", order=adjusted),)
    assert events[0].cash_usd is None
    assert out.cash == P("1000")
    assert out.marks == ()  # a pending order has no mark, and none is invented


# ---- reverse splits ----

def test_reverse_1_for_32_on_open_position_with_remainder():
    abc = _open("ABC", slot=1, last="0.52", limit="0.51", fill="0.5", tp="0.55", sl="0.475", shares=70)
    pf = _pf("100", abc, marks=[("ABC", "0.53")])

    out, events = apply_split(pf, "ABC", ONE_FOR_32, TUE)

    adjusted = replace(
        abc,
        shares=2,  # 70 / 32 = 2.1875 -> 2, remainder 0.1875 share
        last_price=P("16.64"),  # 0.52 x 32
        limit_price=P("16.32"),  # 0.51 x 32
        fill_price=P("16"),  # 0.50 x 32
        tp_price=P("17.6"),  # 0.55 x 32
        sl_price=P("15.2"),  # 0.475 x 32
    )
    assert out.orders == (adjusted,)
    assert out.marks == (("ABC", P("16.96")),)  # 0.53 x 32
    # cash in lieu = q(0.1875 x 16.96) = 3.18
    assert events == (Event(session_date=TUE, kind="split", order=adjusted, cash_usd=P("3.18")),)
    assert out.cash == P("103.18")


def test_reverse_1_for_3_with_split_factor_on_open_and_pending():
    # ONE_FOR_3 is Split.factor, the 28-digit Decimal 0.333…; naive Decimal math floors 300 x it to 99
    assert int(Decimal(300) * ONE_FOR_3) == 99
    abc = _open("ABC", slot=1, last="3.1", limit="3.05", fill="3", tp="3.3", sl="2.8", shares=10)
    xyz = _pending("XYZ", slot=2, last="2", limit="1.9", tp="2.1", sl="1.8", shares=300)
    pf = _pf("969.97", abc, xyz, marks=[("ABC", "3.1")])

    out, events = apply_split(pf, "ABC", ONE_FOR_3, TUE)
    adjusted = replace(
        abc,
        shares=3,  # 10 / 3 = 3.333… -> 3, remainder 1/3 share
        last_price=P("9.3"),
        limit_price=P("9.15"),
        fill_price=P("9"),
        tp_price=P("9.9"),
        sl_price=P("8.4"),
    )
    assert out.orders == (adjusted, xyz)
    assert out.marks == (("ABC", P("9.3")),)
    # cash in lieu = q(1/3 x 9.3) = 3.1 (exactly the one pre-split share at its 3.10 close)
    assert events == (Event(session_date=TUE, kind="split", order=adjusted, cash_usd=P("3.1")),)
    assert out.cash == P("973.07")

    # the same factor on the 300-share pending order gives exactly 100, not 99
    out2, events2 = apply_split(pf, "XYZ", ONE_FOR_3, TUE)
    assert out2.orders[1].shares == 100
    assert out2.orders[1].limit_price == P("5.7")  # 1.9 x 3
    assert events2[0].kind == "split" and events2[0].cash_usd is None


def test_reverse_1_for_3_on_pending_order_floors_without_cash():
    xyz = _pending("XYZ", slot=1, last="2", limit="1.9", tp="2.1", sl="1.8", shares=10)
    out, events = apply_split(_pf("1000", xyz), "XYZ", ONE_FOR_3, TUE)
    assert out.orders[0].shares == 3  # 10 / 3 -> 3; the remainder is simply not ordered
    assert out.cash == P("1000")
    assert events[0].cash_usd is None


def test_reverse_split_flooring_pending_order_to_zero_expires_it():
    xyz = _pending("XYZ", slot=2, last="0.52", limit="0.5", tp="0.55", sl="0.475", shares=20)
    def_ = _open("DEF", slot=4, last="40", limit="40", fill="39.5", tp="44", sl="37", shares=7)
    pf = _pf("200", xyz, def_, marks=[("DEF", "40.25")])

    out, events = apply_split(pf, "XYZ", ONE_FOR_32, TUE)  # 20 / 32 = 0.625 -> 0

    assert events == (
        Event(session_date=TUE, kind="expire", order=replace(xyz, status="expired")),
    )
    assert out.orders == (def_,)
    assert 2 in out.free_slots()
    assert out.cash == P("200")
    assert out.marks == (("DEF", P("40.25")),)


def test_reverse_split_flooring_open_position_to_zero_pays_it_all_in_lieu():
    abc = _open("ABC", slot=3, last="0.52", limit="0.51", fill="0.5", tp="0.55", sl="0.475", shares=20)
    pf = _pf("100", abc, marks=[("ABC", "0.53")])

    out, events = apply_split(pf, "ABC", ONE_FOR_32, TUE)

    # 20 / 32 = 0.625 share -> 0 whole; in lieu = q(0.625 x 16.96) = 10.6
    # pnl_usd = 10.6 - buy_cost(0.50, 20) = 10.6 - q(10 x 1.001) = 10.6 - 10.01 = 0.59
    closed = replace(
        abc,
        status="closed",
        exit_date=TUE,
        exit_price=P("0.53"),
        exit_reason="time",
        pnl_usd=P("0.59"),
    )
    assert events == (
        Event(session_date=TUE, kind="exit", order=closed, forced=True, cash_usd=P("10.6")),
    )
    assert out.orders == ()
    assert out.marks == ()
    assert out.cash == P("110.6")


# ---- scope: only the split symbol moves ----

def test_unaffected_symbols_and_order_are_untouched():
    abc = _open("ABC", slot=1, last="125", limit="121", fill="120", tp="132", sl="114", shares=3)
    xyz = _pending("XYZ", slot=2, last="51", limit="50", tp="55", sl="47.5", shares=5)
    def_ = _open("DEF", slot=3, last="40", limit="40", fill="39.5", tp="44", sl="37", shares=7)
    pf = _pf("100", abc, xyz, def_, marks=[("ABC", "125.5"), ("DEF", "40.25")])

    out, events = apply_split(pf, "ABC", TEN_FOR_ONE, TUE)

    assert [o.slot for o in out.orders] == [1, 2, 3]
    assert out.orders[1] is xyz
    assert out.orders[2] is def_
    assert out.marks == (("ABC", P("12.55")), ("DEF", P("40.25")))
    assert [e.order.symbol for e in events] == ["ABC"]


def test_symbol_not_held_returns_the_same_portfolio():
    def_ = _open("DEF", slot=1, last="40", limit="40", fill="39.5", tp="44", sl="37", shares=7)
    pf = _pf("100", def_, marks=[("DEF", "40.25")])
    out, events = apply_split(pf, "NVDA", TEN_FOR_ONE, TUE)
    assert out is pf
    assert events == ()


def test_apply_split_is_deterministic_and_leaves_input_alone():
    abc = _open("ABC", slot=1, last="102", limit="101", fill="100", tp="110", sl="95", shares=5)
    pf = _pf("500", abc, marks=[("ABC", "104")])
    before = replace(pf)
    assert apply_split(pf, "ABC", THREE_FOR_TWO, TUE) == apply_split(pf, "ABC", THREE_FOR_TWO, TUE)
    assert pf == before


# ---- validation ----

@pytest.mark.parametrize("factor", [10, 1.5, "10", True, None])
def test_non_decimal_factor_is_a_type_error(factor):
    with pytest.raises(TypeError):
        apply_split(_pf("100"), "ABC", factor, TUE)


@pytest.mark.parametrize(
    "factor",
    [
        Decimal(0),
        Decimal(-2),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal(1),
        Decimal("1.0000"),
        Decimal("1.00000000001"),  # not a ratio of small integers
    ],
)
def test_bad_factor_is_a_value_error(factor):
    with pytest.raises(ValueError):
        apply_split(_pf("100"), "ABC", factor, TUE)


def test_split_that_leaves_prices_unrepresentable_at_4dp_is_a_value_error():
    # 10-for-1 on a sub-cent bracket: sl 0.0009 -> 0.00009 -> 0.0001 and tp 0.0011 -> 0.00011
    # -> 0.0001, so sl == tp. Order validation would reject it; apply_split says why, up front.
    xyz = _pending("XYZ", slot=1, last="0.001", limit="0.001", tp="0.0011", sl="0.0009", shares=1000)
    pf = _pf("100", xyz)
    with pytest.raises(ValueError, match="4 dp"):
        apply_split(pf, "XYZ", TEN_FOR_ONE, TUE)
    # An open position whose mark rounds to 0: 0.0004 / 10 = 0.00004 -> 0.0000.
    abc = _open("ABC", slot=1, last="0.0004", limit="0.0004", fill="0.0004", tp="0.0005", sl="0.0003", shares=1000)
    pf2 = _pf("100", abc, marks=[("ABC", "0.0004")])
    before = replace(pf2)
    with pytest.raises(ValueError, match="4 dp"):
        apply_split(pf2, "ABC", TEN_FOR_ONE, TUE)
    assert pf2 == before  # nothing was half-applied


def test_session_must_follow_last_session():
    with pytest.raises(ValueError):
        apply_split(_pf("100", last_session=TUE), "ABC", TEN_FOR_ONE, TUE)
    with pytest.raises(ValueError):
        apply_split(_pf("100", last_session=TUE), "ABC", TEN_FOR_ONE, MON)


def test_session_must_be_an_nyse_session():
    with pytest.raises(ValueError):
        apply_split(_pf("100"), "ABC", TEN_FOR_ONE, SAT)


def test_session_date_must_be_a_date():
    with pytest.raises(TypeError):
        apply_split(_pf("100"), "ABC", TEN_FOR_ONE, datetime(2026, 10, 6, 9, 30))


def test_no_last_session_accepts_any_session():
    out, events = apply_split(_pf("100", last_session=None), "ABC", TEN_FOR_ONE, TUE)
    assert events == ()


@pytest.mark.parametrize("symbol, exc", [("", ValueError), (None, TypeError), (7, TypeError)])
def test_bad_symbol(symbol, exc):
    with pytest.raises(exc):
        apply_split(_pf("100"), symbol, TEN_FOR_ONE, TUE)


def test_bad_portfolio_is_a_type_error():
    with pytest.raises(TypeError):
        apply_split(None, "ABC", TEN_FOR_ONE, TUE)


# ---- end to end: split, then step on adjusted bars ----

def test_10_for_1_then_step_gives_the_same_trade_as_no_split():
    # Filled Mon: 2 x 120.00, buy_cost = q(240 x 1.001) = 240.24; cash 1000 - 240.24 = 759.76
    abc = _open("ABC", slot=1, last="121", limit="121", fill="120", tp="132", sl="114", shares=2)
    pf = _pf("759.76", abc, marks=[("ABC", "125")], equity="1009.76")

    # No split: Tue bar o 126 h 133 l 121 c 130. No gap; low 121 > SL 114; high 133 > TP 132 -> TP at 132.
    # proceeds = q(264 x 0.999) = 263.736; pnl = 263.736 - 240.24 = 23.496; cash 1023.496
    plain = step(pf, TUE, {"ABC": _bar("ABC", TUE, "126", "133", "121", "130")})

    # Split 10:1 executes Tue; the same session in post-split units: o 12.6 h 13.3 l 12.1 c 13.0.
    # 20 x 12.00 (buy_cost(12, 20) = 240.24); high 13.3 > TP 13.2 -> exit 20 x 13.2:
    # proceeds q(264 x 0.999) = 263.736; pnl 23.496
    split_pf, split_events = apply_split(pf, "ABC", TEN_FOR_ONE, TUE)
    assert split_events[0].cash_usd == Decimal("0.0000")
    split = step(split_pf, TUE, {"ABC": _bar("ABC", TUE, "12.6", "13.3", "12.1", "13")})

    (plain_exit,) = plain.events
    (split_exit,) = split.events
    assert plain_exit.kind == split_exit.kind == "exit"
    assert plain_exit.order.exit_reason == split_exit.order.exit_reason == "tp"
    assert plain_exit.order.exit_price == P("132")
    assert split_exit.order.exit_price == P("13.2")
    assert split_exit.order.shares == 20
    assert plain_exit.order.pnl_usd == split_exit.order.pnl_usd == P("23.496")
    assert plain.portfolio.cash == split.portfolio.cash == P("1023.496")
    assert plain.snapshot.equity_usd == split.snapshot.equity_usd == P("1023.496")


def test_1_for_3_then_step_reconciles_cash_with_pnl_and_cash_in_lieu():
    # Filled Mon: 10 x 3.00, buy_cost = q(30 x 1.001) = 30.03; cash 1000 - 30.03 = 969.97
    abc = _open("ABC", slot=1, last="3.1", limit="3.05", fill="3", tp="3.3", sl="2.8", shares=10)
    pf = _pf("969.97", abc, marks=[("ABC", "3.1")], equity="1000.97")

    # 1-for-3 on Tue: 3 shares at fill 9.00, TP 9.90, SL 8.40; 1/3 share paid as q(9.3 / 3) = 3.10
    split_pf, split_events = apply_split(pf, "ABC", ONE_FOR_3, TUE)
    assert split_events[0].cash_usd == P("3.1")
    assert split_pf.cash == P("973.07")

    # Tue bar (post-split units) o 9.2 h 9.95 l 9.0 c 9.8: no gap, low 9.0 > SL 8.4, high 9.95 > TP 9.9
    # exit 3 x 9.90: proceeds = q(29.7 x 0.999) = 29.6703; pnl = 29.6703 - buy_cost(9, 3) = 29.6703 - 27.027 = 2.6433
    result = step(split_pf, TUE, {"ABC": _bar("ABC", TUE, "9.2", "9.95", "9", "9.8")})
    (exit_,) = result.events
    assert exit_.order.exit_reason == "tp"
    assert exit_.order.exit_price == P("9.9")
    assert exit_.order.pnl_usd == P("2.6433")
    assert result.portfolio.cash == P("1002.7403")  # 973.07 + 29.6703

    # Economic P/L over the trade = final cash - starting cash = 2.7403. It splits exactly into
    # pnl_usd (3 post-split shares) + cash in lieu - the cost basis of the share paid in lieu,
    # which is buy_cost(3.00, 10) - buy_cost(9.00, 3) = 30.03 - 27.027 = 3.003.
    economic = result.portfolio.cash - P("1000")
    basis_in_lieu = P("30.03") - P("27.027")
    assert economic == P("2.7403")
    assert economic == exit_.order.pnl_usd + split_events[0].cash_usd - basis_in_lieu


def test_pending_order_adjusted_by_split_fills_at_the_adjusted_limit():
    xyz = _pending("XYZ", slot=1, last="51", limit="50", tp="55", sl="47.5", shares=5)
    split_pf, _ = apply_split(_pf("1000", xyz), "XYZ", THREE_FOR_TWO, TUE)

    # Tue bar o 34 h 35 l 33 c 34.5: low 33 < limit 33.3333 and open 34 >= limit -> fill at limit
    # buy_cost = q(33.3333 x 7 x 1.001) = q(233.5664331) = 233.5664
    result = step(split_pf, TUE, {"XYZ": _bar("XYZ", TUE, "34", "35", "33", "34.5")})
    (fill,) = result.events
    assert fill.kind == "fill"
    assert fill.order.fill_price == P("33.3333")
    assert fill.order.shares == 7
    assert result.portfolio.cash == P("766.4336")  # 1000 - 233.5664
```
**Impact:** Adds 35 tests to the engine suite (216 + phase 1's 76 + phase 2's 36 + 35). No skips, no DB.

## Verification

**Pre-check (index Invariant 1):** the worktree has no `engine/.venv` of its own. If phase 1 has not created it, run `cd /home/miftah/.worktrees/seer/engine-fill-simulator && python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'` (`python3` is pyenv's 3.11.0). Never run the tests with `/home/miftah/seer/engine/.venv`: it is an editable install of `/home/miftah/seer` and tests main's tree, not this worktree.
**Build:** `engine/.venv/bin/python -c "from seer_engine.sim.split_adjust import apply_split"`
**Tests:**
- Phase-local: `engine/.venv/bin/pytest engine/tests/test_sim_split.py -q`, which should give 35 passed.
- Full suite (the invariant): `docker start seer-pg; PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`, which should be green with **0 skipped**.
- Purity guard: `engine/.venv/bin/python -c "import sys, seer_engine.sim.split_adjust; bad = {'psycopg','requests','yfinance','seer_engine.bars'} & set(sys.modules); assert not bad, bad"`
**Manual check:** grep the new module for `float`, `datetime.now`, `date.today`, `time.`, `random`, `logging` and `print`. There should be no hits, apart from the `datetime` imported for the `isinstance` guard.
**Exit criteria:** `apply_split` exists at `seer_engine.sim.split_adjust` with the contract signature. `test_sim_split.py` passes, covering forward 10:1 and 3:2, reverse 1:32 and 1:3 with cash in lieu, open and pending orders, pending floor-to-0 → `expire`, open floor-to-0 → forced `exit`, prices that 4 dp cannot hold → `ValueError`, unaffected symbols, rescaled `marks`, and split + `step` with economically consistent P/L. The full suite is green with 0 skipped.

**Pre-validation:** at reconciliation both files were run verbatim against the real phase 1 code blocks (and phase 2 and 4's) in a scratch copy of the engine: 34 passed before the 4-dp `ValueError` test was added, 35 after; the full suite was green with 0 skipped. The real phase 1 `step` is the authority. If an end-to-end test disagrees with it, re-check the Decision rows ("Cash and `pnl_usd` rounding", "Gap at open precedence") before changing any expected number.

## Handoffs

- **Phase 4 (R4):** export `apply_split` from `seer_engine/sim/__init__.py` (add `"apply_split"` to `__all__`). Then the purity test covers `split_adjust` through `import seer_engine.sim`.
- **Phase 4 (R4):** document in `engine/package_readme.md`, in the `sim` section:
  - the call order: after session S−1's `step`, before stepping the execution session S, with `factor = Split.factor` and `session_date = Split.execution_date` (or the first session on or after it);
  - the event kinds it emits (`split`, `expire`, forced `exit`);
  - that cash in lieu is outside `pnl_usd`, except in the floor-to-0 liquidation case;
  - that a split leaving prices 4 dp cannot hold raises `ValueError`;
  - that the caller must apply each split once (`split_adjustments` already guarantees this);
  - that `equity` is left at the last snapshot until the next `step`.
- **Phase 4 (R4), optional:** the ≥10-session scenario may include a split, but it does not have to.
- **P4 (roadmap, not this plan set):** wire `apply_split` into `nightly` when `splits.apply` records a new split for a symbol with live orders, and persist the `split` events as `UPDATE orders` (prices and shares) and `cash_usd` into the portfolio cash.

- **Settled at reconciliation (index Decisions):** the open floor-to-0 case emits `kind="exit"`, `exit_reason="time"`, `forced=True` from outside `lifecycle`. Phase 1's `Event.forced` means "an exit at the last known close, made without a bar", which covers both `close_unpriced` and this case, and phase 1's `Order` validation accepts the closed order. A new `exit_reason` such as `split` would need a migration and a web label, and is out of scope.
- **Settled at reconciliation (index Decisions):** a split whose rescaled prices cannot be held at 4 dp raises `ValueError` and leaves the input untouched. It is unreachable for real listed stocks (it needs a bracket narrower than 0.0001 × factor), so P4 lets the night fail loudly rather than inventing an expiry.

## Rollback

`git revert <phase-3 sha>` removes the two new files. Nothing else references them until phase 4, so a revert after phase 4 has landed also requires removing the `apply_split` export from `sim/__init__.py`. There is no data rollback.
