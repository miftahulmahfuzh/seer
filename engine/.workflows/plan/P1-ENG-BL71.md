> Adopted from `/home/miftah/seer/.workflows/orchestration/floor-reservation-yardstick/PLAN.md` phase 2. Source: `.workflows/plan/floor-reservation-yardstick/phase-2.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 2: The order-reservation repair, as a pinned-default lever

**Plan set:** `FLOOR_RESERVATION_YARDSTICK_PLAN.md`
**Analysis:** `docs/analyzer/20261027-082613-F3K9_code_analyzer.md`
**Satisfies:** R2 — an unequal-weight book stops silently declining picks it has chosen and can afford
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/sim`

---

## Goal

`sim.book.step_book` tallies a night's buy budget in two currencies that nothing reconciles:
`committed` counts **reservations** priced at the order's limit, `cash` counts **fills** priced at
`min(open, limit)`. After this phase a rule set can ask for one currency — `reserve_basis="fill"`,
where a reservation is the cash the night actually spent, nothing is held back for an order that
never filled, and a clamped fill reserves only what it bought. The default `"order"` is the engine
every recorded lab trial and every live paper strategy ran on, byte for byte, and is pinned as such
by a golden ledger captured from the pre-change engine.

## Interface Contract

**Deletes:** nothing.

**Renames:** nothing.

**Creates:**
- `seer_engine.sim.rules.ReserveBasis` — `Literal["order", "fill"]` (`sim/rules.py`, beside `ResizeBasis`)
- `seer_engine.sim.rules._RESERVE_BASES` — `("order", "fill")` (`sim/rules.py`, beside `_RESIZE_BASES`)
- `seer_engine.sim.rules.TradeRules.reserve_basis` — **new last field**, `ReserveBasis = "order"` (`sim/rules.py:135`, after `resize_band`)
- `engine/tests/test_reserve_basis_pins.py` — new test module (the repo's fifth lever-pins module)
- `engine/tests/fixtures/sim_book_reserve_order_golden.txt` — new golden fixture, **generated from the pre-change engine** (see Step 0)

**Signature changes:** none. `step_book`'s signature is untouched; the lever is read off `rules`.

**Config/table changes:**
- `LEVERS_SINCE_PINS` gains exactly one line, appended last (`sim/rules.py:385`):
  ```python
      "reserve_basis": "order",  # the buy budget reconciled to the fill, not the order, 2026-10-27
  ```
- `_V0_LEVERS` (`sim/rules.py:224-241`) gains one trailing element `"order",` — it is a positional
  tuple of **every** field, so appending a field without appending its DESIGN_V0 value makes
  `engine="bracket_v0"` unconstructible.

**Requires (from earlier phases):** nothing. `depends_on` is empty; this phase stands on `origin/main @ 35b41bd`.

**The plan-set invariant this phase is the one exception to** (index §Invariants 9, cross-referenced
in phases 1 and 3): **no params dataclass may gain a field, in any phase.**
`backtest/registry.py:323` applies the pinned-default drop-out to **`TradeRules` only**, so a new
`compare=True` field on any *allocator* params dataclass would move every recorded `config_digest`
that embeds it. Phases 1 and 3 therefore add no field at all — phase 1 threads a keyword argument,
phase 3 gives each new allocator its own fresh `AlwaysParams`. This phase appends a field to
`TradeRules`, which is legal **only** because of that carve-out, and only while `reserve_basis`
sits in `LEVERS_SINCE_PINS` at its pinned no-op default `"order"`. If `LEVERS_SINCE_PINS` ever
stops covering it, every recorded digest in the lab moves. Step 1 and Step 3 are what prove it
does cover it.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/strategies/*` and `engine/tests/test_price_floor.py` — Phase 1 (R1)
- `engine/src/seer_engine/lab/methods/*` and `docs/runbooks/*` — Phase 3 (R3)
- `engine/src/seer_engine/sim/sizing.py` — **not touched, deliberately.** `size_picks` seeds its own
  `committed` from already-pending orders (`:140`) and adds `buy_cash(order.limit_price, …)` (`:170`),
  which **looks** like the same line and is not the same bug: nothing fills inside that loop, it is
  genuinely a night-before function, and the limit **is** the most such an order can pay. There is
  no leak there to repair. The bracket engine is also the one `DESIGN_V0` runs on and the §5 records
  are frozen by construction.
- `PRESETS` (`sim/rules.py:349`) — **no new preset.** See plan-index Decision **D5**, restated
  under Notes.
- `paper/`, `web/`, `db/migrations/`, `lab/lab.sqlite`, `web/data/lab.json` — untouched by every step.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/sim/rules.py` | modify | one appended `TradeRules` field + its `Literal`, its `_RESERVE_BASES`, its `__post_init__` validation, the `_V0_LEVERS` element, the `LEVERS_SINCE_PINS` line, one module-docstring paragraph, one conditional `describe_rules` line |
| `engine/src/seer_engine/sim/book.py` | modify | the buy loop's `committed` accounting (`:776` and `:795`), gated on the lever; the module docstring's step-4 paragraph (`:30-38`) |
| `engine/tests/test_sim_rules.py` | modify | `:429` — the pinned `LEVERS_SINCE_PINS` table gains one line; two `is_pinned_default` assertions above it |
| `engine/tests/test_backtest_dev_report.py` | modify | `:569-574` — the pinned full `TradeRules(...)` literal gains `, reserve_basis='order'` |
| `engine/tests/test_sim_book.py` | modify | append one section: the regression, the `no_bar` leak, the cash-clamp leak |
| `engine/tests/test_reserve_basis_pins.py` | create | the lever moved nothing: canonical forms, digests, validation, `describe_rules`, the golden ledger |
| `engine/tests/fixtures/sim_book_reserve_order_golden.txt` | create (generated) | 84 lines, one per session, captured from the engine **before** the source edits |

Seven files, two of them source. The plan index's **draft** said four; it now says seven, and the
two extras are assigned to this phase by plan-index decision **D11** — `test_backtest_dev_report.py`
because it pins the full `TradeRules(...)` literal and moves the moment this phase appends a field,
and `engine/tests/fixtures/…` because it is generated, not authored, and exists only to serve this
phase's no-op proof. Both are also recorded under **Handoffs → Discoveries**.

---

## Implementation Steps

Steps run **in this order**. Step 0 must happen before Step 2 or the golden fixture pins the
post-change engine and proves nothing.

### Step 0: Capture the golden ledger from the PRE-change engine
**File:** `engine/tests/test_reserve_basis_pins.py` (write it first — Step 4), then
`engine/tests/fixtures/sim_book_reserve_order_golden.txt` (generated)
**Change:** Write the new test module (Step 4's code, verbatim) and run the capture script below
**while `sim/rules.py` and `sim/book.py` are still untouched**. The module is written so that
nothing it imports or evaluates at import time mentions `reserve_basis`: every reference to the
lever lives inside a test function body, so it imports cleanly against HEAD.

**Code (the capture script — write it to the scratchpad, NOT to the repo):**

```python
# /tmp/capture_reserve_golden.py — run once, at HEAD, before editing any source.
import sys
from pathlib import Path

ROOT = Path("/home/miftah/.worktrees/seer/floor-reservation-yardstick")
sys.path.insert(0, str(ROOT / "engine" / "src"))
sys.path.insert(0, str(ROOT / "engine" / "tests"))

from test_reserve_basis_pins import GOLDEN_PATH, GOLDEN_RULES, golden_ledger  # noqa: E402

text = golden_ledger(GOLDEN_RULES)
GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
GOLDEN_PATH.write_text(text, encoding="utf-8")
print(f"wrote {GOLDEN_PATH} — {len(text.splitlines())} sessions, {len(text)} bytes")
```

Run it with the worktree's own interpreter:

```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
engine/.venv/bin/python /tmp/capture_reserve_golden.py
git -C . diff --stat -- engine/src/seer_engine/sim   # MUST be empty; if not, you captured too late
```

Expect `wrote … — 84 sessions, …` and a **clean** `engine/src/seer_engine/sim` diff.

**If you capture too late** (you edited `book.py` first): `git stash push -- engine/src/seer_engine/sim/book.py engine/src/seer_engine/sim/rules.py`, delete the fixture, re-run the capture, then `git stash pop`. Never hand-edit the fixture.

**Impact:** The fixture becomes the only artifact in this phase that cannot be re-derived after the
change. Measured here on `35b41bd`: 84 session lines, 406 fills, 17 `no_bar` rejections, and the
`"fill"` basis differs from it on 81 of the 84 lines — so it is a sensitive pin, not a formality.

---

### Step 1: The lever on `TradeRules`
**File:** `engine/src/seer_engine/sim/rules.py` — six edits: `:1-48` (docstring), `:72` (alias),
`:97` (`_RESERVE_BASES`), `:135` (field), `:206` (validation), `:241` (`_V0_LEVERS`), `:385`
(`LEVERS_SINCE_PINS`), `:614` (`describe_rules`).

**Change 1a — the module docstring.** Insert this paragraph immediately **after** the `cash_yield`
paragraph and immediately **before** the final `Pure: no clock, no I/O, no randomness.` line.

**Code:**
```python
``reserve_basis`` says how much of one night's buy budget an order holds while the rest of the rank
is sized. "order" (every rule set before 2026-10-27) reserves the order at its LIMIT the moment it
is sized, before any bar is read, and never gives any of it back: an order that found no bar, one
the day's low never reached, the part of one the cash clamp shrank away, and the difference between
a limit and a fill below it all keep their reservation against every pick ranked below. "fill"
reserves instead the cash the order actually spent, after the clamp, and reserves nothing for an
order that never filled.

Only an unequal-weight book notices. ``sim.book`` sizes a new entry at
``min(q(equity × weight), available − committed)``; under equal weights the first term binds and the
drift in the second is invisible, which is why the equal-weight and shuffled arms never skipped a
pick while the unequal-weight one did so six times in twenty years (lab journal, 2026-10-26) --
once with $11,936 of cash against a $7,431 order.

The two halves of "fill" are NOT equally defensible, and the lever exists because of that. Releasing
an order that was never placed is pure accounting repair: there is no live book in which a cancelled
order holds cash. Handing the limit/fill slack back DOWN the list inside one session is not: the
owner places the whole night's orders in the morning and cannot know an early fill price before
sizing a later one, so a book that opts in is buying picks it would not have been able to size live.
They move together under one value because a book that opts in opts into one coherent rule -- a
reservation is what the night actually commits -- and because measuring them apart would cost a
second lever on a shared value that every config digest reads. The default is a pinned no-op
(``LEVERS_SINCE_PINS``), so no recorded result, digest or live paper strategy moves.
```

**Change 1b — the type alias.** After `ResizeBasis = Literal["equity", "target"]`:

**Code:**
```python
ResizeBasis = Literal["equity", "target"]
ReserveBasis = Literal["order", "fill"]
```

**Change 1c — the allowed values.** After `_RESIZE_BASES: tuple[str, ...] = ("equity", "target")`:

**Code:**
```python
_RESIZE_BASES: tuple[str, ...] = ("equity", "target")
_RESERVE_BASES: tuple[str, ...] = ("order", "fill")
```

**Change 1d — the field.** Append as the **last** field of `TradeRules`, after
`resize_band: Decimal | None = None`:

**Code:**
```python
    resize_band: Decimal | None = None
    reserve_basis: ReserveBasis = "order"
```

**Change 1e — validation.** In `__post_init__`, insert immediately **after** the `resize_band`
block (which ends `raise ValueError("resize_band needs resize=True: …")`) and immediately
**before** `is_v0 = _lever_values(self) == _V0_LEVERS`:

**Code:**
```python
        if not isinstance(self.reserve_basis, str):
            raise TypeError(f"reserve_basis must be a str, got {type(self.reserve_basis).__name__}")
        if self.reserve_basis not in _RESERVE_BASES:
            raise ValueError(f"unknown reserve_basis {self.reserve_basis!r}; expected one of {_RESERVE_BASES}")
        if self.reserve_basis == "fill" and self.engine != "book":
            raise ValueError(
                f"reserve_basis 'fill' is a book-engine lever; the {self.engine} simulator sizes the "
                "whole night before anything fills (sim.sizing.size_picks), so its limit already is "
                "the most an order can pay"
            )
```

**Change 1f — `_V0_LEVERS`.** The tuple is positional over every field; append `"order"`:

**Code:**
```python
_V0_LEVERS: tuple[object, ...] = (
    _V0_ID,
    "bracket_v0",
    "daily",
    None,
    "limit",
    4,
    5,
    False,
    False,
    False,
    None,
    _DEFAULT_COST,
    "flat",
    "equity",
    None,
    None,
    "order",
)
```

**Change 1g — `LEVERS_SINCE_PINS`.** Append one line, last (the comment above the dict says
"Append only, and only for a lever whose default is a true no-op"):

**Code:**
```python
LEVERS_SINCE_PINS: dict[str, object] = {
    "resize_cadence": None,  # the rank/resize cadence split, 2026-10-05
    "cost_model": "flat",  # Gotrade's measured fee schedule (sim.costs), 2026-10-07
    "resize_basis": "equity",  # the band measured against the holding's own target, 2026-10-12
    "cash_yield": None,  # interest on idle cash at a T-bill yield, 2026-10-12
    "resize_band": None,  # the band's size, overriding the basis's constant, 2026-10-20
    "reserve_basis": "order",  # the buy budget reconciled to the fill, not the order, 2026-10-27
}
```

**Change 1h — `describe_rules`.** Append a line **only when the lever is used**, at the very end,
immediately before `return tuple(lines)`. Appending last and conditionally is what keeps
`test_sim_rules.py:337` (`all(len(describe_rules(p)) == 12 for p in PRESETS)`) and every
index-based assertion (`lines[4]`, `lines[6]`, `lines[7]`, `lines[11]`) green: no preset uses the
lever, so no preset's description changes by one byte.

**Code:**
```python
    if rules.reserve_basis == "fill":
        lines.append(
            "Buy budget: the night's orders are placed in rank order against one budget, and each "
            "order holds only the cash it actually spends -- an order that does not fill holds "
            "none, and one that fills below its limit leaves the difference to the picks ranked "
            "below it. A live book cannot know an early fill price before sizing a later order, so "
            "this reads the night with hindsight the morning does not have."
        )
    return tuple(lines)
```

**Impact:** Every `TradeRules` gains a field. `registry._canon` (`backtest/registry.py:323`) and
`roster.rules_dict` (`paper/roster.py:1704`) both enumerate fields generically and drop a
`LEVERS_SINCE_PINS` field at its no-op value, so no pinned candidate digest, no closed lab trial's
`config_digest` and no live paper `strategies.params` spec digest moves. Two tests that print or
pin the **full** field list do move, and are repaired in Step 3.

---

### Step 2: The buy loop
**File:** `engine/src/seer_engine/sim/book.py` — two edits: `:30-38` (docstring) and `:776`/`:795`
(the loop).

**Change 2a — the module docstring, step (4).** Replace lines 30-38 **in full**.

**Before (exactly, lines 30-38):**
```
4. buys, targets in rank order with the idle instrument last: new entries (``max_positions``
   counted as the night before, exactly as ``sim.size_picks``) and adds (same band as trims,
   upward), sized the night before from the last snapshot's equity and the cash the night's
   planned sells will bring, then filled at the open ("open") or when the low trades strictly
   below the limit, at ``min(open, limit)`` ("limit", "open_limit"); a new entry under "limit"
   whose target has no limit price is bought exactly like "open_limit" (limit ``q(last × 1.02)``);
   a held target with no limit price is never added to; a fill cash cannot cover
   is shrunk to what cash affords. A new position is not checked against its stop or take on
   its fill session;
```

**After:**
```
4. buys, targets in rank order with the idle instrument last: new entries (``max_positions``
   counted as the night before, exactly as ``sim.size_picks``) and adds (same band as trims,
   upward), sized the night before from the last snapshot's equity and the cash the night's
   planned sells will bring, then filled at the open ("open") or when the low trades strictly
   below the limit, at ``min(open, limit)`` ("limit", "open_limit"); a new entry under "limit"
   whose target has no limit price is bought exactly like "open_limit" (limit ``q(last × 1.02)``);
   a held target with no limit price is never added to; a fill cash cannot cover
   is shrunk to what cash affords. A new position is not checked against its stop or take on
   its fill session.

   Each buy also holds part of that one budget while the rest of the rank is sized, and
   ``rules.reserve_basis`` says how much. "order" (every rule set before 2026-10-27) reserves
   ``_buy_cash(limit, shares)`` the moment the order is sized, before any bar is read, and nothing
   gives it back: a target rejected "no_bar" (an order never placed), one rejected "unfilled", the
   part of one the cash clamp shrank away, and the difference between a limit and a fill below it
   all keep their reservation against every later pick. "fill" reserves instead the cash the order
   really spent, after the clamp, and reserves nothing for an order that never filled. Only an
   unequal-weight book can tell: ``min(q(equity × weight), available − committed)`` is bound by its
   first term under equal weights. Releasing a cancelled order is plain repair; handing the
   limit/fill slack back down the list is hindsight the morning's order ticket does not have, which
   is why both are behind the lever and the default is the engine every recorded trial ran on;
```

**Change 2b — the loop.** Replace lines 776-796 **in full**.

**Before (exactly, lines 776-796):**
```python
            committed += _buy_cash(price, shares, rules)

            b = day.get(symbol)
            if b is None:
                rejected.append((symbol, "no_bar"))
                continue
            if rules.entry == "open":
                fill_price = q(b.open)
            elif b.low < price:
                fill_price = q(b.open if b.open < price else price)
            else:
                rejected.append((symbol, "unfilled"))
                continue
            cost = _buy_cash(fill_price, shares, rules)
            if cost > cash:
                shares = _shares_for(cash, fill_price, rules)
                if shares <= 0:
                    rejected.append((symbol, "cash"))
                    continue
                cost = _buy_cash(fill_price, shares, rules)
            cash -= cost
```

**After:**
```python
            # How much of the night's one budget this order holds while the rest of the rank is
            # sized (rules.reserve_basis). "order": the whole order at its LIMIT, here, before any
            # bar is read -- and every path below that buys less than that, or nothing at all,
            # leaves the difference reserved for a night that never spends it. "fill": reserved
            # once the fill is final, at the cash it really cost, so the picks below see what is
            # left. slots_used is NOT part of this: a slot is counted as of the night before, which
            # is the §5 parity contract (see the module docstring, step 4).
            if rules.reserve_basis == "order":
                committed += _buy_cash(price, shares, rules)

            b = day.get(symbol)
            if b is None:
                rejected.append((symbol, "no_bar"))
                continue
            if rules.entry == "open":
                fill_price = q(b.open)
            elif b.low < price:
                fill_price = q(b.open if b.open < price else price)
            else:
                rejected.append((symbol, "unfilled"))
                continue
            cost = _buy_cash(fill_price, shares, rules)
            if cost > cash:
                shares = _shares_for(cash, fill_price, rules)
                if shares <= 0:
                    rejected.append((symbol, "cash"))
                    continue
                cost = _buy_cash(fill_price, shares, rules)
            if rules.reserve_basis == "fill":
                committed += cost
            cash -= cost
```

Nothing else in the loop moves. In particular `slots_used += 1` at `:773-774` stays exactly where it
is: it is a different quantity with a different contract (`max_positions` counted as of the night
before, "exactly as `sim.size_picks`"), and moving it would break the §5 parity tests. See
**Handoffs**.

**Impact:** At `reserve_basis="order"` the emitted bytecode path is identical to today's (one extra
`str ==` per target). At `"fill"` an unequal-weight book buys picks it previously declined. Nothing
about sells, trims, dividends, interest, stops, takes or the snapshot changes on either value.

---

### Step 3: The two pinned tables that enumerate every field
**File:** `engine/tests/test_sim_rules.py:419-435` and `engine/tests/test_backtest_dev_report.py:569-574`

**Change 3a.** Replace `test_a_lever_added_after_the_pins_is_left_out_of_canonical_text_at_its_default`
in full.

**Code:**
```python
def test_a_lever_added_after_the_pins_is_left_out_of_canonical_text_at_its_default():
    assert is_pinned_default("resize_cadence", None) is True
    assert is_pinned_default("resize_cadence", "weekly") is False
    assert is_pinned_default("cadence", "monthly") is False  # only post-pin levers are skippable
    assert is_pinned_default("cost_model", "flat") is True
    assert is_pinned_default("cost_model", "gotrade") is False
    assert is_pinned_default("resize_basis", "equity") is True
    assert is_pinned_default("resize_basis", "target") is False
    assert is_pinned_default("resize_band", None) is True
    assert is_pinned_default("resize_band", Decimal("0.10")) is False
    assert is_pinned_default("reserve_basis", "order") is True
    assert is_pinned_default("reserve_basis", "fill") is False
    assert LEVERS_SINCE_PINS == {
        "resize_cadence": None,
        "cost_model": "flat",
        "resize_basis": "equity",
        "cash_yield": None,
        "resize_band": None,
        "reserve_basis": "order",
    }
```

**Change 3b.** In `test_preregistration_names_each_finalist_exactly`, the pinned literal (the
`assert (...) in text` block at `:569-574`) becomes:

**Code:**
```python
    assert (
        "TradeRules(id='monthly-hold', engine='book', cadence='monthly', resize_cadence=None, "
        "entry='open_limit', max_positions=None, "
        "time_stop=None, resize=True, fractional=False, dividends=True, idle_symbol=None, cost_rate=Decimal('0.001'), "
        "cost_model='flat', resize_basis='equity', cash_yield=None, resize_band=None, "
        "reserve_basis='order')"
    ) in text
```

**Impact:** These are the only two tests in the suite that enumerate the full field list.
`backtest/dev_report.py:_rules_literal` prints every field by `repr`, which is why the
pre-registration golden moves; the digest-bearing `_canon` and `rules_dict` do not.

---

### Step 4: The new pins module
**File:** `engine/tests/test_reserve_basis_pins.py` (new, written **before** Step 0's capture run)

**Code (the complete file):**
```python
"""``TradeRules.reserve_basis``: how much of one night's budget an order holds, and the pins that
say adding the lever moved nothing.

``sim.book.step_book`` sizes a night's buys against ``available = book.cash + planned`` and runs a
``committed`` tally down the rank-ordered targets. That tally counted RESERVATIONS priced at the
order's limit while ``cash`` counted FILLS priced at ``min(open, limit)``, and nothing reconciled
them. Two leaks sat in that one line, and they are not equally defensible:

- an order rejected "no_bar" was never placed at all, one rejected "unfilled" never traded, and the
  part of one the cash clamp shrank away was never bought -- yet each kept a full reservation
  against every pick ranked below it. That is accounting error with no live-book defence;
- an order that filled under its limit kept the difference reserved. Reserving at the limit is what
  a live book HAS to do: the owner places the whole night's orders in the morning and cannot know an
  early fill price before sizing a later one, so handing that slack back inside one session reads
  the night with hindsight.

Both are repaired together behind ``reserve_basis="fill"``, because a book that opts in opts into
one rule -- a reservation is what the night actually commits -- and because splitting them would
cost a second field on a value every config digest reads.

It is a lever added after the P7a registry, the lab trials and the paper roster were pinned, so it
sits in ``sim.rules.LEVERS_SINCE_PINS`` at "order" and drops out of every canonical text while it is
there. These tests are the proof, in the shape ``test_resize_basis_pins.py`` set, plus a golden
ledger: a seeded unequal-weight tape stepped at the default and captured from the engine BEFORE the
lever existed, so any default-path change in the buy loop goes red with a readable diff.

The tape exercises entries, adds, trims, signal sells and the "no_bar" leak (17 of them). The
"unfilled", "too_small" and cash-clamp leaks are covered one at a time in ``test_sim_book.py``.
"""

from __future__ import annotations

import random
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from seer_engine import dates, sim
from seer_engine.backtest.registry import REGISTRY, candidate_digest, candidate_text
from seer_engine.lab.method import config_digest, config_text, discover
from seer_engine.paper import roster
from seer_engine.prices import Bar
from seer_engine.sim import Target, new_book, step_book
from seer_engine.sim.rules import (
    DESIGN_V0,
    DESIGN_V0_GOTRADE,
    LEVERS_SINCE_PINS,
    MONTHLY_HOLD,
    PRESETS,
    V0_BOOK,
    TradeRules,
    describe_rules,
    is_pinned_default,
)

W = Decimal

GOLDEN_PATH = Path(__file__).parent / "fixtures" / "sim_book_reserve_order_golden.txt"

# The golden tape. Six names, an unequal weight ladder summing to 1, and a resizing open_limit book,
# so entries, adds, trims, signal sells and missing bars all occur. The market generator mirrors
# ``test_sim_book._market`` exactly -- the same 0.25 price grid and the same 5% missing-bar rate --
# so the two tapes stay comparable, and like it this relies on ``random.Random.gauss`` being stable
# across CPython versions, which the §5 parity test has relied on since P7a.
GOLDEN_RULES = TradeRules(id="gold-unequal", engine="book", entry="open_limit", resize=True)
GOLDEN_SYMBOLS: dict[str, float] = {
    "AAA": 50.0,
    "BBB": 120.0,
    "CCC": 20.0,
    "DDD": 300.0,
    "EEE": 75.0,
    "FFF": 8.0,
}
GOLDEN_WEIGHTS: tuple[Decimal, ...] = (W("0.30"), W("0.25"), W("0.18"), W("0.12"), W("0.09"), W("0.06"))
GOLDEN_SEED = 7
GOLDEN_START = date(2026, 6, 1)
GOLDEN_END = date(2026, 9, 30)
GOLDEN_CASH = W("10000")


def _tick(x: float | Decimal) -> Decimal:
    """``x`` on a 0.25 price grid, so exact ties (low == limit) occur."""
    d = W(repr(x)) if isinstance(x, float) else x
    return sim.q((d * 4).to_integral_value() / 4)


def _golden_market(sessions: list[date]) -> dict[date, dict[str, Bar]]:
    rng = random.Random(GOLDEN_SEED)
    closes = dict(GOLDEN_SYMBOLS)
    out: dict[date, dict[str, Bar]] = {}
    for i, s in enumerate(sessions):
        bars: dict[str, Bar] = {}
        for sym in sorted(GOLDEN_SYMBOLS):
            prev = closes[sym]
            o = prev * (1 + rng.gauss(0, 0.012))
            c = prev * (1 + rng.gauss(0.0005, 0.018))
            h = max(o, c) * (1 + abs(rng.gauss(0, 0.008)))
            lo = min(o, c) * (1 - abs(rng.gauss(0, 0.008)))
            closes[sym] = c
            if i > 0 and rng.random() < 0.05:
                continue  # a missing bar
            bars[sym] = Bar(sym, s, _tick(o), _tick(h), _tick(lo), _tick(c), 1_000_000)
        out[s] = bars
    return out


def golden_ledger(rules: TradeRules) -> str:
    """One line per session -- fills, rejections, cash, equity -- as text a human can diff.

    Also the capture function: run it at HEAD and write the result to ``GOLDEN_PATH`` before the
    lever exists, so the fixture pins the engine the lab recorded and not the repaired one.
    """
    sessions = dates.sessions(GOLDEN_START, GOLDEN_END)
    market = _golden_market(sessions)
    rng = random.Random(GOLDEN_SEED + 500)
    bk = new_book(GOLDEN_CASH)
    data = market[sessions[0]]
    lines: list[str] = []
    for s in sessions[1:]:
        order = sorted(data)
        rng.shuffle(order)
        targets = tuple(Target(sym, w, data[sym].close) for sym, w in zip(order, GOLDEN_WEIGHTS))
        out = step_book(bk, s, market[s], targets, rules)
        bk = out.book
        lines.append(
            "|".join(
                (
                    s.isoformat(),
                    ";".join(
                        f"{f.symbol},{f.side},{f.shares},{f.price},{f.cash_usd},{f.reason}"
                        for f in out.fills
                    ),
                    ";".join(f"{sym},{why}" for sym, why in out.rejected),
                    str(out.snapshot.cash_usd),
                    str(out.snapshot.equity_usd),
                )
            )
        )
        data = market[s]
    return "\n".join(lines) + "\n"


# ============================================================== the default is the old engine


def test_the_default_basis_replays_the_engine_the_lab_recorded():
    """The golden tape, captured before the lever existed. A readable diff on failure."""
    want = GOLDEN_PATH.read_text(encoding="utf-8")
    got = golden_ledger(GOLDEN_RULES)
    assert got == want


def test_the_fill_basis_is_not_inert_on_the_same_tape():
    """If this passed, the lever would be doing nothing and the test above would prove nothing."""
    other = golden_ledger(replace(GOLDEN_RULES, reserve_basis="fill"))
    assert other != GOLDEN_PATH.read_text(encoding="utf-8")


def test_every_rule_set_the_repo_ships_is_on_the_old_basis():
    assert TradeRules(id="x", engine="book").reserve_basis == "order"
    assert DESIGN_V0.reserve_basis == "order" and V0_BOOK.reserve_basis == "order"
    assert [r.id for r in PRESETS if r.reserve_basis != "order"] == []


# ============================================================== validation


def test_reserve_basis_validation():
    with pytest.raises(TypeError, match="reserve_basis"):
        replace(MONTHLY_HOLD, id="x", reserve_basis=None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unknown reserve_basis"):
        replace(MONTHLY_HOLD, id="x", reserve_basis="limit")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="book-engine lever"):
        replace(DESIGN_V0_GOTRADE, id="x", reserve_basis="fill")
    with pytest.raises(ValueError, match="book-engine lever"):
        replace(DESIGN_V0, reserve_basis="fill")
    assert replace(MONTHLY_HOLD, id="x", reserve_basis="fill").reserve_basis == "fill"


# ============================================================== it moved nothing that was pinned


def test_reserve_basis_is_a_lever_since_the_pins():
    assert LEVERS_SINCE_PINS["reserve_basis"] == "order"
    assert is_pinned_default("reserve_basis", "order") is True
    assert is_pinned_default("reserve_basis", "fill") is False
    # Append only: an insertion would re-order nothing, but the habit is the point.
    assert list(LEVERS_SINCE_PINS)[-1] == "reserve_basis"


def _all_candidates():
    """Every registry candidate and every lab variant, amendments included (``all_candidates``)."""
    out = list(REGISTRY)
    for m, _ in discover().values():
        out += list(m.all_candidates())
    return out


def _asserts_reserve_basis(text: str, c) -> None:
    """"order" is left out of a canonical form; "fill" names itself, so it digests apart.

    Conditional on purpose: a later method built on the repaired budget must name the lever, and
    asserting absence unconditionally would pin the lab to the leak forever.
    """
    if c.rules.reserve_basis == "order":
        assert "reserve_basis" not in text, c.id
    else:
        assert f"reserve_basis='{c.rules.reserve_basis}'" in text, c.id


def test_order_is_absent_from_every_canonical_form():
    for c in REGISTRY:
        _asserts_reserve_basis(candidate_text(c), c)
    for c in _all_candidates():
        _asserts_reserve_basis(config_text(c), c)
    for r in (*PRESETS, V0_BOOK):
        if r.reserve_basis == "order":
            assert "reserve_basis" not in roster.rules_dict(r), r.id
        else:
            assert roster.rules_dict(r)["reserve_basis"] == r.reserve_basis, r.id


def test_fill_digests_differently():
    book_candidates = [c for c in _all_candidates() if c.rules.engine == "book"]
    assert book_candidates
    for c in book_candidates[:25]:
        # The rules id is kept, so the only thing that moves in the text is the lever itself.
        f = replace(c, rules=replace(c.rules, reserve_basis="fill"))
        assert "reserve_basis='fill'" in config_text(f), c.id
        assert config_digest(f) != config_digest(c), c.id
        assert candidate_digest(f) != candidate_digest(c), c.id
    g = replace(MONTHLY_HOLD, id="monthly-hold-fill", reserve_basis="fill")
    assert roster.rules_dict(g)["reserve_basis"] == "fill"
    assert "reserve_basis" not in roster.rules_dict(MONTHLY_HOLD)


# ============================================================== the plain-English description


def test_describe_rules_names_the_lever_only_when_it_is_used():
    plain = describe_rules(MONTHLY_HOLD)
    assert len(plain) == 12
    assert not any(line.startswith("Buy budget:") for line in plain)
    used = describe_rules(replace(MONTHLY_HOLD, id="monthly-hold-fill", reserve_basis="fill"))
    assert len(used) == 13
    assert used[1:12] == plain[1:12]  # index 0 is the rule-set id, which differs by construction
    assert used[12].startswith("Buy budget:")
    assert "hindsight" in used[12]
```

**Impact:** Five pins and one behaviour golden. `test_fill_digests_differently` is the counterpart
every other lever-pins module has: proof the lever is readable by the digest machinery when a rule
set actually uses it.

---

### Step 5: The three leak regressions
**File:** `engine/tests/test_sim_book.py` — append at the end of the file (after
`test_beyond_band_is_the_old_comparison_under_the_equity_basis`, currently `:929-939`).

Every number below was run against the engine at `35b41bd` (both values of the lever, the `"fill"`
half on a patched scratch copy) and is reproduced exactly.

**Code:**
```python
# ============================================================== reserve_basis: the night's budget

# The shape the lab measured on 2026-10-26: an unequal-weight book, mid-rotation, with far more
# equity than budget. 2,000 in cash plus an 8,000 holding it keeps makes equity 10,000 and the
# night's budget 2,000, so `available - committed` -- not `q(equity x weight)` -- is what binds for
# the tail of the rank. A and B are sized at their limit of 99.9 (= q(97.9412 x 1.02)) and fill 12%
# lower at 88; C is the tail.
RESERVE_FILL = replace(DAILY_SWITCH, id="daily-switch-fill", reserve_basis="fill")


def _starved_tail():
    b = book("2000", pos("Y", 800, "10"))  # equity = 2,000 cash + 8,000 held
    bars = day(
        bar("Y", TUE, "10", "10", "10", "10"),
        bar("A", TUE, "88", "100", "87", "90"),
        bar("B", TUE, "88", "100", "87", "90"),
        bar("C", TUE, "190", "205", "189", "195"),
    )
    targets = (
        T("Y", "0.795", "10"),  # held, rules.resize is False: never trimmed, never added to
        T("A", "0.09", "97.9412"),
        T("B", "0.09", "97.9412"),
        T("C", "0.025", "200"),
    )
    return b, bars, targets


def test_at_the_order_basis_an_unequal_book_declines_a_pick_it_can_afford():
    """The bug, reproduced: C is refused "too_small" with 414.42 of cash against a 190.19 order."""
    b, bars, targets = _starved_tail()
    out = go(b, TUE, bars, targets, DAILY_SWITCH)
    # A and B: budget q(10,000 x 0.09) = 900 each, 9 shares at a limit of 99.9. Reserved
    # q(99.9 x 9 x 1.001) = 899.9991 each; spent q(88 x 9 x 1.001) = 792.7920 each.
    assert [(f.symbol, f.shares, f.price, f.cash_usd) for f in out.fills] == [
        ("A", W(9), P("88"), P("-792.792")),
        ("B", W(9), P("88"), P("-792.792")),
    ]
    # 1,799.9982 of 2,000 is reserved though only 1,585.5840 was spent, so C's budget is
    # min(q(10,000 x 0.025) = 250, 2,000 - 1,799.9982 = 0.0018) = 0.0018 -- not one share.
    assert out.rejected == (("C", "too_small"),)
    # And it was never affordability: C's one share would have cost q(190 x 1.001) = 190.19.
    assert out.snapshot.cash_usd == P("414.416")


def test_at_the_fill_basis_the_same_book_buys_the_tail():
    b, bars, targets = _starved_tail()
    out = go(b, TUE, bars, targets, RESERVE_FILL)
    # Now 1,585.5840 is reserved, C's budget is its full 250, and one share at a limit of 204 fits.
    assert [(f.symbol, f.shares, f.price, f.cash_usd) for f in out.fills] == [
        ("A", W(9), P("88"), P("-792.792")),
        ("B", W(9), P("88"), P("-792.792")),
        ("C", W(1), P("190"), P("-190.19")),
    ]
    assert out.rejected == ()
    assert out.snapshot.cash_usd == P("224.226")  # 414.416 - 190.19
    assert out.snapshot.equity_usd == P("10039.226")


def test_an_order_with_no_bar_holds_no_cash_against_the_picks_below_it():
    """Leak (1) alone: P1 is sized, has no bar at all, and is never placed."""
    b = book("2000", pos("Y", 800, "10"))  # equity 10,000, budget 2,000
    bars = day(bar("Y", TUE, "10", "10", "10", "10"), bar("P2", TUE, "190", "205", "189", "195"))
    targets = (T("Y", "0.785", "10"), T("P1", "0.19", "97.9412"), T("P2", "0.025", "200"))
    # P1: budget min(1,900, 2,000) = 1,900 -> 19 shares reserved at q(99.9 x 19 x 1.001) = 1,899.9981.
    out = go(b, TUE, bars, targets, DAILY_SWITCH)
    assert out.fills == ()
    assert out.rejected == (("P1", "no_bar"), ("P2", "too_small"))
    assert out.snapshot.cash_usd == P("2000")  # the whole night traded nothing at all
    out = go(b, TUE, bars, targets, RESERVE_FILL)
    assert [(f.symbol, f.shares, f.price) for f in out.fills] == [("P2", W(1), P("190"))]
    assert out.rejected == (("P1", "no_bar"),)
    assert out.snapshot.cash_usd == P("1809.81")


def test_the_cash_clamp_reserves_what_it_bought_not_what_it_ordered():
    """Leak (1) in its third form, isolated from the limit/fill slack.

    X is dropped and has no bar, so its 1,498.50 of planned proceeds sit in the night's budget and
    never reach cash. P1's open (110) is above its limit (99.9) and its low (95) is below it, so it
    fills exactly AT the limit: the only thing the lever can move here is the clamp, which cuts the
    order from 19 shares to the 5 that 500 of cash affords.

    P2 cannot buy under either basis, because a clamp by definition leaves less than one share's
    worth of cash behind. What moves is the REASON it is refused, and that is the whole proof: at
    "order" P2 is never sized at all (budget 98.5019, under one share); at "fill" it is sized, and
    refused for the honest reason that the night has really spent its money. The budget moved; the
    cash did not.
    """
    b = book("500", pos("Y", 800, "10"), pos("X", 150, "10"))  # equity 10,000
    bars = day(
        bar("Y", TUE, "10", "10", "10", "10"),
        bar("P1", TUE, "110", "112", "95", "108"),
        bar("P2", TUE, "190", "205", "189", "195"),
    )
    targets = (T("Y", "0.775", "10"), T("P1", "0.19", "97.9412"), T("P2", "0.035", "200"))
    bought = [("P1", W(5), P("99.9"), P("-499.9995"))]
    out = go(b, TUE, bars, targets, DAILY_SWITCH)
    assert [(f.symbol, f.shares, f.price, f.cash_usd) for f in out.fills] == bought
    assert out.rejected == (("P2", "too_small"),)
    assert out.snapshot.cash_usd == P("0.0005")
    assert out.book.position("X").exit_pending is True
    out = go(b, TUE, bars, targets, RESERVE_FILL)
    assert [(f.symbol, f.shares, f.price, f.cash_usd) for f in out.fills] == bought
    assert out.rejected == (("P2", "cash"),)
    assert out.snapshot.cash_usd == P("0.0005")
```

**Impact:** `test_sim_book.py` needs no new imports: `replace`, `DAILY_SWITCH`, `W`, `P`, `bar`,
`day`, `book`, `pos`, `T` and `go` are all already in scope at the top of that module.

---

## Verification

The worktree needs its **own** virtualenv or pytest silently tests the main checkout.

**It is already built and working** — re-verified 2026-10-27 by the reconciler:
`engine/.venv/bin/python` is **CPython 3.12.7**, numpy 2.5.4, pytest 9.1.1, `import seer_engine`
ok. **`python3.11` does not exist on this machine**; `CLAUDE.md` says `python3.11 -m venv` but the
real interpreter is `python3` → CPython 3.12.7 from `/home/miftah/miniconda3/bin`, which is what
the main checkout's venv also runs. Confirm, and rebuild only if the check fails:

```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
engine/.venv/bin/python -c "import numpy, pytest, seer_engine; print('venv ok')" \
  || (python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]')
```

**Postgres and `PG_TEST_URL` — before any pytest run below, not only the full suite.**
`PG_TEST_URL` is **not** exported by default in this shell, and the `seer-pg` container had been
stopped for 26 hours before this plan set started. CI fails if the DB tests skip, so a silent
local skip is a failure that reaches CI. Run these two lines in the same shell as every pytest
command in this section:

```bash
docker start seer-pg 2>/dev/null \
  || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
docker ps --filter name=seer-pg --format '{{.Names}} {{.Status}}'   # must print "seer-pg Up ..."
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
```

**Build / lint:**
```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
engine/.venv/bin/ruff check engine
engine/.venv/bin/python -c "import sys; sys.path.insert(0,'engine/src'); import seer_engine.sim.book, seer_engine.sim.rules; print('ok')"
```

**Tests — the files this phase touches, first and alone (fast, and isolates a real failure):**
```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
PYTHONPATH=engine/src engine/.venv/bin/pytest -n0 \
  engine/tests/test_reserve_basis_pins.py \
  engine/tests/test_sim_book.py \
  engine/tests/test_sim_rules.py \
  engine/tests/test_backtest_dev_report.py
```

**Then the lever's blast radius — every test that reads a canonical form, a digest or the parity:**
```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
PYTHONPATH=engine/src engine/.venv/bin/pytest -n0 \
  engine/tests/test_registry.py \
  engine/tests/test_resize_basis_pins.py \
  engine/tests/test_resize_band_pins.py \
  engine/tests/test_cost_model_pins.py \
  engine/tests/test_cash_yield.py \
  engine/tests/test_sim_rules_fixed_tape.py \
  engine/tests/test_paper_roster.py \
  engine/tests/test_sean_mirrors.py \
  engine/tests/test_book_runner.py \
  engine/tests/test_sim_book_split.py \
  engine/tests/test_sim_purity.py \
  engine/tests/test_lab_methods.py
```

**The two §5 parity tests named in `book.py:44` — they must still pass untouched:**
- `engine/tests/test_sim_book.py::test_v0_book_replays_size_picks_and_step` (`:766`, seeds 1, 2, 3)
- `engine/tests/test_book_runner.py::test_v0_book_replays_run_backtest` (`:357`, keys A/A2/B × seeds 39, 4),
  plus `::test_v0_book_rejections_map_to_the_simulators` and `::test_v0_book_hand_checked_scenario`

`V0_BOOK.reserve_basis` is `"order"`, so both take the unchanged branch. Run them explicitly:
```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
PYTHONPATH=engine/src engine/.venv/bin/pytest -n0 \
  "engine/tests/test_sim_book.py::test_v0_book_replays_size_picks_and_step" \
  "engine/tests/test_book_runner.py::test_v0_book_replays_run_backtest" \
  "engine/tests/test_book_runner.py::test_v0_book_rejections_map_to_the_simulators" \
  "engine/tests/test_book_runner.py::test_v0_book_hand_checked_scenario"
```

**Full suite (what CI runs):**
```bash
docker start seer-pg 2>/dev/null || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
PYTHONPATH=engine/src engine/.venv/bin/pytest engine/tests -n auto
```
Use `-n0` to isolate anything that goes red under `-n auto`.

> **A peer's red is not your red.** Other phases and other sessions share this checkout, and a
> **concurrent `lab run` in `/home/miftah/seer` reddens three lab tests** that read exactly like a
> broken frozen record (`test_lab_methods.py`, `test_lab_store.py`, `test_lab_runner.py` are the
> usual three). Before reporting any failure as real: re-run **that one file alone** with `-n0`,
> and say in the report which run you verified it in and at what time. The same goes for
> `test_lab_methods.py` while Phase 3 is landing its **ten** pending amendments — that is its
> state, not a break. (Ten, not thirteen: the index's corrected R3 census.)

**Manual check:** none. No web page, no database row, no deployed artifact, no lab state. `git
status --porcelain` must show exactly the seven files of this phase and **nothing** under
`lab/lab.sqlite` or `web/data/lab.json`.

**Exit criteria:**
1. `test_at_the_order_basis_an_unequal_book_declines_a_pick_it_can_afford` reproduces the bug —
   C refused `too_small` with `414.416` of cash against a `190.19` order — and
   `test_at_the_fill_basis_the_same_book_buys_the_tail` buys it.
2. The `no_bar` and cash-clamp leaks each have a test that fails at `"order"` and passes at `"fill"`.
3. `engine/tests/fixtures/sim_book_reserve_order_golden.txt` was captured from the pre-change engine
   and `test_the_default_basis_replays_the_engine_the_lab_recorded` is green, while
   `test_the_fill_basis_is_not_inert_on_the_same_tape` proves the pin is sensitive.
4. `"reserve_basis"` appears in no `candidate_text`, no `config_text` and no `roster.rules_dict` for
   any registry candidate, any lab variant or any preset.
5. Both §5 parity tests pass untouched.
6. The full engine suite is green with `PG_TEST_URL` set (DB tests must not skip).

---

## Handoffs

**Discoveries — two files the plan index did not list, and why they are mine**
- `engine/tests/test_backtest_dev_report.py:569-574` pins the **full** `TradeRules(...)` literal that
  `backtest/dev_report.py:_rules_literal` prints into every pre-registration document. It is the
  only test outside `test_sim_rules.py` that enumerates every field, and it moves the moment a field
  is appended. It belongs to this phase because this phase appends the field.
- `engine/tests/fixtures/sim_book_reserve_order_golden.txt` is generated, not authored, and only
  exists because the no-op proof demanded a pin of the pre-change engine.

**Left for a later, separate piece of work — none of it is R1 or R3**
- **Measuring what the lever is worth.** Nothing here runs a backtest, a lab method or a paper night.
  Whether `"fill"` earns anything on dev is an experiment, needs a pre-registered method file, and is
  the deliberate next step — not a side effect of a repair.
- **A `PRESETS` entry, and therefore paper.** Plan-index **D5**: no preset is added. A method that wants the
  repaired budget declares its own `TradeRules` in its own method file, exactly as M0127 did with its
  `T00` (`sim/rules.py:306-322` documents that pattern and why a preset arrived only later, when the
  **roster** needed to name it). Adding one here would move `test_sim_rules_fixed_tape.py`
  (`len(PRESETS) == 20` and its index assertions), `test_cost_model_pins.py:86`,
  `test_lab_costs.py:387` and `test_sean_mirrors.py:101,121` — which mirrors into
  `web/lib/cadence.ts` — for a capability nothing in this plan set uses. Promotion to paper is a
  later step that adds the preset **then**; note also
  `commands/promote.py:144` matches a lab rule set to a preset on every field but `id` and
  `fractional`, so a `"fill"` lab winner simply finds no preset until one exists, which is the
  correct refusal.
- **`slots_used` has the same shape of leak and is deliberately untouched.** `slots_used += 1` at
  `book.py:773-774` counts a slot for an entry that is afterwards rejected `no_bar` or `unfilled`.
  That is not an accident: `max_positions` is counted "as of the night before, exactly as
  `sim.size_picks`" (module docstring, step 4), and `test_v0_book_rejections_map_to_the_simulators`
  asserts the book's `no_slot` count equals the bracket simulator's. Changing it would break §5
  parity and belongs in its own phase with its own lever, if anyone ever wants it.
- **`sim/sizing.py` is not a second instance of this bug.** Recorded in the Interface Contract above
  so the next reader does not "fix" it.
- **The paper night.** `step_book` is the live engine, and this phase changes nothing live because
  every roster entry resolves to a preset and every preset is `"order"`. If a repaired book is ever
  promoted, `paper/roster.py`'s spec digest for that entry will legitimately carry
  `reserve_basis='fill'` — a new roster id with its own paper clock, never an edit to a started one.

---

## Rollback

This phase is one commit over seven files that no other phase touches.

```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
git revert --no-edit <sha>
```

Or, before it is committed, by explicit path only (never `git checkout .`, never `reset --hard` —
other sessions share this checkout):

```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
git checkout -- engine/src/seer_engine/sim/rules.py engine/src/seer_engine/sim/book.py \
                engine/tests/test_sim_rules.py engine/tests/test_backtest_dev_report.py \
                engine/tests/test_sim_book.py
rm -f engine/tests/test_reserve_basis_pins.py engine/tests/fixtures/sim_book_reserve_order_golden.txt
```

Nothing outside git is touched: no lab row, no database, no deployed page, no paper-night behaviour,
no research store. A revert returns `TradeRules` to sixteen fields and the buy loop to the single
unconditional `committed +=`.

---

## Committing

Write the message to a file and apply it with `-F`. **Never `-m` with backticks in it** — the shell
substitutes them and silently deletes words; it has destroyed commits in this repo twice.

```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
cat > /tmp/reserve_basis_msg.txt <<'EOF'
sim: reserve_basis — a night's buy budget reconciled to the fill, behind a pinned default

step_book ran two tallies down one rank-ordered target list and reconciled neither: committed
counted reservations priced at the order's limit, cash counted fills priced at min(open, limit).
Every fill under its limit, every order with no bar, every unfilled order and every share the cash
clamp shrank away left cash reserved for a night that never spent it, so each later pick was sized
against a budget that was too small. Only an unequal-weight book could tell, because
min(q(equity x weight), available - committed) is bound by its first term under equal weights —
which is why the lab measured six skipped picks in twenty years on the unequal arm and none on the
equal-weight or shuffled ones, one of them declining a 7,431 dollar order while holding 11,936 in
cash.

reserve_basis is the repair, as a lever with a pinned no-op default, because step_book is the engine
for every engine="book" rule set from M0001 on and for the live paper roster: an unconditional
change would move what the owner's board shows tomorrow and make every recorded trial
un-reproducible with nothing recording that it had. "order" is today's engine byte for byte; "fill"
reserves the cash an order really spent and nothing at all for one that never filled.

The two halves are not equally defensible and the docstrings say so. Releasing an order that was
never placed is plain repair. Handing the limit/fill slack back down the list inside one session is
hindsight the morning's order ticket does not have, since the owner places the whole night at once.
They move together because a book that opts in opts into one rule — a reservation is what the night
actually commits.

Pinned: the lever sits last in LEVERS_SINCE_PINS, so registry._canon, lab config_text and
paper.roster.rules_dict all drop it at "order" and no candidate digest, no closed trial digest and
no live spec digest moves. A golden ledger captured from the pre-change engine — 84 sessions of an
unequal-weight tape — pins the default path, and a companion test proves the lever is not inert on
it. No new PRESETS entry: a method that wants the repaired budget declares its own TradeRules, as
M0127 did. sim/sizing.py is left alone; its limit really is the most such an order can pay.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF

git add engine/src/seer_engine/sim/rules.py \
        engine/src/seer_engine/sim/book.py \
        engine/tests/test_sim_rules.py \
        engine/tests/test_backtest_dev_report.py \
        engine/tests/test_sim_book.py \
        engine/tests/test_reserve_basis_pins.py \
        engine/tests/fixtures/sim_book_reserve_order_golden.txt

git status --porcelain   # confirm ONLY those seven are staged
git commit -F /tmp/reserve_basis_msg.txt
```

Explicit paths only. Never `git commit -a`, never `git add .`, never a directory pathspec: other
sessions are working in this checkout and a broad pathspec lands their half-finished work under this
message. `lab/lab.sqlite` and `web/data/lab.json` are never staged by this phase — if either shows
up in `git status`, a peer's `lab stage` put it there and it is not yours to commit.

---

## Notes — the decisions that were made before this plan, recorded so nobody relitigates them

These ids are the plan index's, not this file's: see `FLOOR_RESERVATION_YARDSTICK_PLAN.md`
§Decisions for the full table and the rung each was settled on. (An earlier draft of this file
numbered them D6, D7 and D3 on its own; they are renumbered here to match the index, so a reader
meeting "D4" in either document finds the same decision.)

- **D4.** The repair arrives as a `TradeRules` lever with a pinned no-op default, not as an
  unconditional change. Five precedents (`resize_cadence`, `cost_model`, `resize_basis`,
  `cash_yield`, `resize_band`) and `LEVERS_SINCE_PINS`'s own comment: "Append only, and only for a
  lever whose default is a true no-op." The present behaviour at the default is a true no-op, and
  Step 4 proves it rather than assuming it.
- **P2-a** (local to this phase, no index row). The repaired semantics: `committed` tracks what
  the night actually commits. Leak A (never
  released — `no_bar`, `unfilled`, the cash clamp) is pure accounting error. Leak B
  (over-reservation at the limit) is a realism trade the lever makes safe by being opt-in and by
  writing both halves into the docstring. Both repaired under one value.
- **D5.** No new `PRESETS` entry. Smallest change that satisfies the request; promotion to paper is a
  later, separate step that would add the preset then.
- **D11.** This phase owns `engine/tests/test_backtest_dev_report.py` and the generated golden
  fixture, which the draft plan index did not list. Both are consequences of this phase's own act:
  the dev-report test pins the full `TradeRules(...)` literal and moves the moment a field is
  appended, and the fixture exists only to serve this phase's no-op proof. The index's phase-2 file
  count is **7**, not the draft's 4.
