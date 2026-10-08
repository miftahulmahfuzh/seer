# Phase 4: The bracket path can express and charge Gotrade's fees

**Plan set:** `GOTRADE_FEE_REBUILD_PLAN.md`
**Analysis:** `20261008-091321-H3M8_code_analyzer.md`
**Satisfies:** R4 — strategy C, the roster's permanent daily-trading control, can be rebuilt to pay
what Gotrade really charges, so the counterfactual it exists to measure is honest.
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/sim`

---

## Goal

After this phase a bracket rule set can say `cost_model="gotrade"` and construct, and every place
the bracket path moves money — sizing a pick, filling it, exiting it, paying cash in lieu at a
split — charges Gotrade's measured schedule including the $0.10 per-order floor instead of the
assumed 0.1% a side. `DESIGN_V0` is untouched: it still constructs, still carries engine
`"bracket_v0"`, and still digests identically, so the live roster entry C keeps running exactly as
it does today until phase 12 gives it a successor. The phase creates **no** roster entry; it makes
one expressible.

**For phase 12 — the two values it needs:** the preset is
`seer_engine.sim.rules.DESIGN_V0_GOTRADE`, `rules_id = "design-v0-gotrade"`, and its
`TradeRules.engine` is `"bracket"`. The `RosterEntry.engine` column value stays the string
`"bracket"` it already is for C (`paper/roster.py` SEED_ROWS, `commands/paper.py:726`) — the two
spellings coincide and nothing about the roster's engine column changes.

### What this costs C, measured

Run from the worktree root with `PYTHONPATH=engine/src`:

```python
from decimal import Decimal as D
from seer_engine.sim.costs import fee_parts, gotrade_cash
for a in ("10", "28", "50", "560"):
    b, s = fee_parts("buy", D(a)).total, fee_parts("sell", D(a)).total
    print(a, b, s, (b + s) / D(a) * 100)
print(gotrade_cash("buy", D("27.90"), 1), gotrade_cash("sell", D("72.51"), 1))
```

| order | buy fee | sell fee | round trip |
|---|---|---|---|
| $10 | $0.12 | $0.13 | 2.500% |
| $28 | $0.13 | $0.16 | **1.036%** |
| $50 | $0.14 | $0.17 | 0.620% |
| $560 | $1.37 | $1.62 | 0.534% |

The flat model charges $0.056 on a $28 round trip. Gotrade charges $0.29 — **5.2x**. The floor
binds below about $50. The same call reproduces the owner's two real receipts to the cent: a 1-share
buy at $27.90 costs $28.03 (receipt: $28.03 paid), a 1-share sell at $72.51 returns $72.27 (receipt:
$72.27 received).

**The finding this phase will surface, and must not be softened:** at a $140 slot budget on the
owner's $560 book, the floor does not merely shave the share count — at a $28 budget against a
$27.90 pick, flat sizing buys 1 share and Gotrade sizing buys **0**, because $27.90 + $0.13 does not
fit $28. C will reject picks the flat model bought. That is the counterfactual working, not a bug.
Never propose retiring C.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Creates:**
- `seer_engine.sim.charges` — **new module** `engine/src/seer_engine/sim/charges.py`, holding
  `bracket_rules`, `buy_cash`, `sell_cash`, `order_fee`, `whole_shares_for`.
- `seer_engine.sim.rules.DESIGN_V0_GOTRADE` (`sim/rules.py`) — preset id `"design-v0-gotrade"`,
  engine `"bracket"`, inserted into `PRESETS` at **index 13** (not appended).
- `seer_engine.sim.rules.BRACKET_ENGINES` and `seer_engine.sim.rules.is_bracket` (`sim/rules.py`).

**Signature changes** (all additions are **keyword-only** with a default, so every existing
positional caller keeps compiling and keeps its exact numbers):
- `sim.sizing.size_picks(pf, picks, session_date)` -> `(..., *, rules: TradeRules = DESIGN_V0)`
- `sim.lifecycle.step(pf, session_date, bars)` -> `(..., *, rules: TradeRules = DESIGN_V0)`
- `sim.lifecycle.close_unpriced(pf, symbols)` -> `(..., *, rules: TradeRules = DESIGN_V0)`
- `sim.split_adjust.apply_split(pf, symbol, factor, session_date)` -> `(..., *, rules: TradeRules = DESIGN_V0)`
- `paper.bracket.settle_bracket(pf, session, bars, splits, last_bar_date)` -> `(..., *, rules: TradeRules = DESIGN_V0)`
- `paper.bracket.decide_bracket(pf, strategy, params, history, members, data_date)` -> `(..., *, rules: TradeRules = DESIGN_V0)`
- private: `sim.lifecycle._close(order, when, price, reason, days_held)` -> `(..., rules)`

**Widened value sets:**
- `sim.rules.Engine` Literal: `"bracket_v0" | "book"` -> `"bracket_v0" | "bracket" | "book"`
- `sim.rules._ENGINES`: `("bracket_v0", "book")` -> `("bracket_v0", "bracket", "book")`

**Deletes:**
- `sim.sizing._ONE_PLUS_COST` (`sizing.py:31`) — the import-time constant; the third measured
  blocker.
- `sim.sizing._whole_shares` (`sizing.py:95-105`) — moved to `charges.whole_shares_for`, which takes
  the rule set.

**Renames:** none.

**Requires (from earlier phases):** none. This phase has no `depends_on`.

**The two caller files this planner intended to edit are NOT edited here — they are HANDOFFS to
phase 12.** Reconciled 2026-10-08 under the index's Decision **D10**, which was taken after this
plan was dispatched: `commands/paper.py` is needed by phases 3, 4, 6 and 12, two of which (3 and 4)
run **concurrently in wave 1**, so no wave-1 phase may edit it. D10 gives `commands/paper.py`,
`paper/replay.py` and `commands/promote.py` to phase 12, the only phase that depends on all of 3, 4
and 6 and can therefore quote every signature as it actually landed. The exact code is reproduced in
**Handoffs → H6** and again, verbatim, as explicit steps in `phase-12.md`.

- `engine/src/seer_engine/commands/paper.py` — four call sites must pass `rules=e.rules`
  (`:553-555`, `:727-734`, `:777`, `:779`). **Phase 12 does this.**
- `engine/src/seer_engine/commands/promote.py:275` — `engine = "bracket" if rules.engine ==
  "bracket_v0" else "book"` must become `... if is_bracket(rules) else "book"`. **Phase 12 does this.**

**This is safe, and the safety is checkable, not hoped for:** every parameter this phase adds is
keyword-only with `DESIGN_V0` as its default, and `DESIGN_V0` is what all four of those call sites
already ran. So with the wiring absent the tree builds, the engine suite passes, and every number in
the system is bit-for-bit what it is today — the capability is complete and **inert** until phase 12
turns it on, which is exactly the state the pause already holds the system in.

**`backtest/runner.py`: NOT TOUCHED HERE.** `runner.py:181`, `:186` and `:197` call `size_picks` /
`step` / `close_unpriced` positionally and get `DESIGN_V0`, which is what they already ran, so this
phase leaves the file byte-identical at `485d416`. **Phase 5 owns `runner.py` and, by the
reconciler's assignment, also owns adding `run_backtest(..., *, rules: TradeRules = DESIGN_V0)` and
forwarding it to those three lines** — see Handoffs H1.

**Leaves alone (owned by others):** `sim/book.py` (already complies — four gotrade branches, and
`_shares_for` already bisects); `sim/costs.py` (invariant 5, not modified in any way);
`sim/model.py` (**not modified** — `COST_RATE`, `buy_cost` and `sell_proceeds` stay exactly as they
are, still used by `backtest/benchmark.py`, `paper/benchmark.py` and their tests);
`paper/benchmark.py` (phase 3); `paper/roster.py` (phase 12); `paper/store.py`, `paper/book.py`
(phase 6); `backtest/runner.py`, `backtest/book_runner.py`, `sim/contributions.py` (phase 5);
`backtest/metrics.py`, `backtest/benchmark.py`, `backtest/dev.py` (phase 7); `lab/store.py`
(phases 2 and 7); everything under `web/`.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/sim/charges.py` | **create** | the bracket path's money, priced by a rule set |
| `engine/src/seer_engine/sim/rules.py` | modify | `:7-11` docstring, `:35` `Engine`, `:45` `_ENGINES` + `BRACKET_ENGINES`, new `is_bracket`, `:203-206` + `DESIGN_V0_GOTRADE`, `:208-224` `PRESETS`, `:345` and `:373` describe branches |
| `engine/src/seer_engine/sim/sizing.py` | modify | `:1-16` docstring, `:27` imports, `:31` delete `_ONE_PLUS_COST`, `:95-105` delete `_whole_shares`, `:108` signature, `:136`, `:151`, `:166` |
| `engine/src/seer_engine/sim/lifecycle.py` | modify | `:35-46` imports, `:65-84` `_close`, `:128` `step` signature, `:179`, `:189`, `:208` `close_unpriced` signature, `:246` |
| `engine/src/seer_engine/sim/split_adjust.py` | modify | `:35` imports, `:113-115` signature, `:175` |
| `engine/src/seer_engine/sim/__init__.py` | modify | `:10-13` docstring, charges import block, rules imports, `__all__` |
| `engine/src/seer_engine/paper/bracket.py` | modify | `:35-45` imports, `:108-114` + `:141,144,155`, `:162-169` + `:190` |
| `engine/tests/test_sim_rules.py` | modify | `:82-88` preset loop, `:92-111` id list, new engine/preset tests |
| `engine/tests/test_sim_sizing.py` | modify | new Gotrade sizing tests + the flat-identity pin |
| `engine/tests/test_sim_lifecycle.py` | modify | new Gotrade fill/exit/forced-close tests |
| `engine/tests/test_sim_split.py` | modify | new Gotrade cash-in-lieu pnl test |
| `engine/tests/test_paper_bracket.py` | modify | a Gotrade night through `decide_bracket` + `settle_bracket` |
| `engine/tests/test_cost_model_pins.py` | modify | `:71-74` the non-flat preset id list grows by one |

**Thirteen files** (the plan index's draft said 10, and this planner's own first count was 15; the
two caller files moved to phase 12 under D10, leaving 13 — the index now says 13).

`engine/tests/test_lab_costs.py:257` (`PRESETS[-2:] == (MONTHLY_HOLD_FRAC_GOTRADE,
MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE)`), `test_sim_rules.py:88` (`PRESETS[:13]` all flat) and
`test_sim_rules.py:352` (`PRESETS[12] is MONTHLY_RANK_WEEKLY_RESIZE_FRAC`) are the reason the new
preset goes in at **index 13** rather than the end: at index 13 all three pins still hold untouched.
`test_paper_kickoff.py:64` skips any preset whose engine is not `"book"`, so it is unaffected.

---

## Implementation Steps

### Step 1: Give the bracket path an engine value of its own
**File:** `engine/src/seer_engine/sim/rules.py:7-11, :35, :45`
**Change:** add `"bracket"` to the `Engine` Literal and `_ENGINES`, name the bracket family once as
`BRACKET_ENGINES`, and correct the module docstring, which today claims every non-`DESIGN_V0` rule
set is a book rule set. `bracket_v0` stays reserved for `DESIGN_V0` exactly as it is (`:136-140` is
not touched): the new engine is how a *second* bracket rule set is expressed.

**Code** — replace lines 7-11 of the module docstring:

```python
- ``DESIGN_V0`` is §5 exactly. It is the only rule set with ``engine="bracket_v0"``, and it is
  executed by the unchanged ``sim.size_picks`` + ``sim.step`` path (``backtest.runner``), so the
  closed A, A2 and B records stay byte-identical by construction.
- ``engine="bracket"`` is that same simulator under a rule set that is not §5 — today only
  ``DESIGN_V0_GOTRADE``, which is §5 paying Gotrade's measured fee schedule instead of the
  assumed 0.1% a side. ``BRACKET_ENGINES`` is the two of them; ``is_bracket`` is the test.
- Every other rule set has ``engine="book"`` and is executed by ``sim.book.step_book``.
  ``V0_BOOK`` is §5 replayed by the book engine; it exists only for the parity test.
```

**Code** — line 35:

```python
Engine = Literal["bracket_v0", "bracket", "book"]
```

**Code** — line 45, and the new public constant directly after it:

```python
_ENGINES: tuple[str, ...] = ("bracket_v0", "bracket", "book")
#: The engines run by ``sim.size_picks`` + ``sim.step`` + ``sim.apply_split`` (not the book).
BRACKET_ENGINES: tuple[str, ...] = ("bracket_v0", "bracket")
```

**Code** — a new function, placed immediately after `_rules` (which ends at `:248`):

```python
def is_bracket(rules: TradeRules) -> bool:
    """True when ``rules`` run the design §5 bracket simulator rather than the book engine.

    ``engine="bracket_v0"`` (``DESIGN_V0``) or ``engine="bracket"`` (a §5 rule set that differs
    from §5 in a lever — today only the cost model). The dispatch every caller that has to pick
    between ``sim.size_picks`` + ``sim.step`` and ``sim.book.step_book`` should use.
    """
    _rules(rules)
    return rules.engine in BRACKET_ENGINES
```

**Impact:** `TradeRules(id="x", engine="bracket")` now constructs. Nothing that exists changes:
no preset, no digest, no canonical form. `_V0_LEVERS` and the two reservation checks at `:136-140`
are untouched, so `replace(DESIGN_V0, …)` still raises exactly as before.

### Step 2: Describe a `"bracket"` rule set as the bracket simulator, not as a book
**File:** `engine/src/seer_engine/sim/rules.py:345, :373`
**Change:** two branches test `rules.engine == "bracket_v0"` and so send a `"bracket"` rule set down
the *book* text. Measured, before the fix, `describe_rules(DESIGN_V0_GOTRADE)` printed
`"Engine: the target-weight book; a position the strategy stops wanting is sold at the next open…"`
and the limit-entry fallback paragraph — both false of the bracket simulator. Use `is_bracket`.
The text for `bracket_v0` is byte-identical to today, so every golden assertion in
`test_sim_rules.py` holds.

**Code** — `:345-351` becomes:

```python
    if is_bracket(rules):
        lines.append("Engine: the design §5 bracket simulator, unchanged.")
    else:
        lines.append(
            "Engine: the target-weight book; a position the strategy stops wanting is sold at the "
            "next open, and stops and take-profits are fixed at entry."
        )
```

**Code** — `:373` becomes:

```python
    if rules.entry == "limit" and is_bracket(rules):
```

**Impact:** `describe_rules` is deterministic and golden-tested; for all 15 existing presets the
output is unchanged character for character. The 16th preset now gets the correct first and fifth
lines.

### Step 3: The preset — §5 at Gotrade's real fees
**File:** `engine/src/seer_engine/sim/rules.py:203-224`
**Change:** add `DESIGN_V0_GOTRADE` beside the two existing Gotrade presets, and put it into
`PRESETS` at index 13 so the three index-sensitive pins listed in **Files** do not move.

**Code** — after `MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE` (ends `:206`), insert:

```python
# Design §5 at Gotrade's real fees: the daily-trading control the owner requires on the roster
# permanently ("I want to see how bad it got if I had used daily trading on Gotrade like my
# initial plan", 2026-10-08). Every lever is DESIGN_V0's; only the cost model differs, which is
# why it cannot be engine "bracket_v0" (that id and that engine are reserved for §5 exactly).
# Measured at Gotrade's current schedule: a $28 order pays $0.13 to buy and $0.16 to sell --
# 1.036% the round trip, against the flat model's 0.2%.
DESIGN_V0_GOTRADE = replace(DESIGN_V0, id="design-v0-gotrade", engine="bracket", cost_model="gotrade")
```

**Code** — `PRESETS` in full:

```python
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
    DESIGN_V0_GOTRADE,
    MONTHLY_HOLD_FRAC_GOTRADE,
    MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
)
```

**Impact:** `paper.roster.rules_for("design-v0-gotrade")` now resolves, which is what phase 12
needs. `LEVERS_SINCE_PINS` is untouched, so every preset that does not use `cost_model`
canonicalizes exactly as it did before the lever existed; `DESIGN_V0_GOTRADE` names its model and
therefore digests apart, which is the point. Measured: `roster.rules_dict(DESIGN_V0_GOTRADE)`
carries `'cost_model': 'gotrade'` and `'engine': 'bracket'`; `rule_owner_inputs` is `()` (the
schedule is fitted to the owner's own receipts and the cost rate stays at its default).

### Step 4: The bracket path's money, priced by a rule set
**File:** `engine/src/seer_engine/sim/charges.py` — **new file**
**Change:** `sim/model.py` cannot grow these, because `sim/costs.py` imports `sim.model.q` and a
rules-aware helper must import `sim.costs` — that is a cycle. `sim/costs.py` may not be modified
(invariant 5). So the bracket path gets a module of its own, the twin of `sim/book.py`'s private
`_buy_cash` / `_sell_cash` / `_fee` / `_shares_for`. Import order is
`rules -> costs -> model` and `charges -> {rules, costs, model}`; `sizing`, `lifecycle` and
`split_adjust` import `charges`. Nothing imports back, so there is no cycle.

**Code** — the complete file:

```python
"""The money of the bracket path, priced by a rule set's cost model (plan set phase 4).

``sim.model.buy_cost`` and ``sell_proceeds`` multiply one module-level constant, ``COST_RATE``:
every design §5 fill paid an assumed 0.1% a side whatever its rule set said, and
``sim.sizing`` precomputed ``1 + COST_RATE`` at import. Gotrade's measured schedule
(``sim.costs``, fitted to the owner's receipts) is not proportional -- a $0.10 minimum on every
order, a capped regulatory fee -- so the bracket path has to be handed the rule set and ask it.

Four functions, the bracket twins of ``sim.book``'s private helpers:

- :func:`buy_cash` -- cash out to buy ``shares`` at ``price``;
- :func:`sell_cash` -- cash in selling them;
- :func:`order_fee` -- the fee inside one of those two numbers;
- :func:`whole_shares_for` -- the most WHOLE shares whose buy cash fits a budget.

Under ``cost_model="flat"`` each is the old arithmetic with ``rules.cost_rate`` in place of the
constant, so ``buy_cash(p, n, DESIGN_V0) == sim.model.buy_cost(p, n)`` and
``sell_cash(p, n, DESIGN_V0) == sim.model.sell_proceeds(p, n)`` exactly, for every price and
share count (pinned by ``tests/test_sim_sizing.py``). That is what keeps the closed A, A2, B and
C records byte-identical.

Shares are whole: a bracket ``Order`` holds an ``int`` share count. A fractional rule set is a
book rule set and :func:`bracket_rules` refuses it here.

Pure: no clock, no I/O, no randomness, no floats.
"""

from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal

from seer_engine.sim.costs import SIDES, Side, gotrade_cash, gotrade_shares_for
from seer_engine.sim.model import q
from seer_engine.sim.rules import BRACKET_ENGINES, TradeRules

_ONE = Decimal(1)


def _price(name: str, x: object) -> Decimal:
    if not isinstance(x, Decimal):
        raise TypeError(f"{name} must be a Decimal, got {type(x).__name__}")
    if not x.is_finite():
        raise ValueError(f"{name} must be finite, got {x!r}")
    if x <= 0:
        raise ValueError(f"{name} must be > 0, got {x}")
    return x


def _shares(name: str, x: object) -> int:
    if isinstance(x, bool) or not isinstance(x, int):
        raise TypeError(f"{name} must be an int, got {type(x).__name__}")
    if x < 0:
        raise ValueError(f"{name} must be >= 0, got {x}")
    return x


def bracket_rules(rules: object) -> TradeRules:
    """``rules`` if the bracket path can run them; TypeError or ValueError saying why not.

    A book rule set belongs to ``sim.book.step_book``, and a fractional one cannot be held in a
    bracket ``Order`` at all (``sim.model.Order.shares`` is an ``int``).
    """
    if not isinstance(rules, TradeRules):
        raise TypeError(f"rules must be a TradeRules, got {type(rules).__name__}")
    if rules.engine not in BRACKET_ENGINES:
        raise ValueError(
            f"rules {rules.id!r} run the {rules.engine!r} engine; the bracket path takes one of "
            f"{BRACKET_ENGINES} (run a book rule set with sim.book.step_book)"
        )
    if rules.fractional:
        raise ValueError(
            f"rules {rules.id!r} are fractional; a bracket order holds a whole share count "
            f"(sim.model.Order.shares is an int)"
        )
    return rules


def buy_cash(price: Decimal, shares: int, rules: TradeRules) -> Decimal:
    """Cash paid to buy ``shares`` at ``price`` under ``rules``.

    "flat": ``q(price x shares x (1 + rules.cost_rate))`` -- ``sim.model.buy_cost`` with the rule
    set's own rate. "gotrade": ``q(price x shares)`` plus the measured schedule's fee, which
    carries a $0.10 per-order minimum (``sim.costs.gotrade_cash``).
    """
    _price("price", price)
    _shares("shares", shares)
    bracket_rules(rules)
    if rules.cost_model == "gotrade":
        return gotrade_cash("buy", price, shares)[0]
    return q(price * shares * (_ONE + rules.cost_rate))


def sell_cash(price: Decimal, shares: int, rules: TradeRules) -> Decimal:
    """Cash received selling ``shares`` at ``price`` under ``rules``.

    "flat": ``q(price x shares x (1 - rules.cost_rate))`` -- ``sim.model.sell_proceeds`` with the
    rule set's own rate. "gotrade": ``q(price x shares)`` less the schedule's fee, the fee capped
    at the amount so a dust sale never costs more than it brings in.
    """
    _price("price", price)
    _shares("shares", shares)
    bracket_rules(rules)
    if rules.cost_model == "gotrade":
        return gotrade_cash("sell", price, shares)[0]
    return q(price * shares * (_ONE - rules.cost_rate))


def order_fee(side: Side, price: Decimal, shares: int, rules: TradeRules) -> Decimal:
    """The fee inside one order's cash: ``buy_cash - amount``, or ``amount - sell_cash``.

    The bracket simulator does not record a per-fill fee (an ``Order`` has no cost column), so
    nothing in ``sim`` calls this; it is here so a reporting caller never has to re-derive the
    schedule. ``side`` matters only under "gotrade", which charges more on a sell.
    """
    if side not in SIDES:
        raise ValueError(f"side must be one of {SIDES}, got {side!r}")
    _price("price", price)
    _shares("shares", shares)
    bracket_rules(rules)
    if rules.cost_model == "gotrade":
        return gotrade_cash(side, price, shares)[1]
    return q(price * shares * rules.cost_rate)


def whole_shares_for(budget: Decimal, price: Decimal, rules: TradeRules) -> int:
    """The most whole shares at ``price`` whose :func:`buy_cash` fits ``budget``; 0 when none does.

    "flat": ``floor(budget / (price x (1 + rules.cost_rate)))``, stepped back while the exact
    unrounded cost exceeds the budget -- ``sim.sizing._whole_shares`` verbatim, with the rule
    set's rate in place of the import-time ``_ONE_PLUS_COST``. Decimal division rounds to 28
    significant digits, so a quotient a hair under an integer could round up to it.

    "gotrade": there is no unit cost to divide by, because the $0.10 minimum makes the fee
    non-proportional in the share count. The cost never falls as shares grow, so the answer is
    SOLVED by bisection on the rounded cash (``sim.costs.gotrade_shares_for``, which
    ``sim.book._shares_for`` already uses for the book engine). It never overspends.
    """
    _price("price", price)
    if not isinstance(budget, Decimal):
        raise TypeError(f"budget must be a Decimal, got {type(budget).__name__}")
    if not budget.is_finite():
        raise ValueError(f"budget must be finite, got {budget!r}")
    bracket_rules(rules)
    if budget <= 0:
        return 0
    if rules.cost_model == "gotrade":
        return int(gotrade_shares_for(budget, price, _ONE))
    unit = price * (_ONE + rules.cost_rate)
    shares = int((budget / unit).to_integral_value(rounding=ROUND_FLOOR))
    while shares > 0 and unit * shares > budget:
        shares -= 1
    return max(shares, 0)
```

**Impact:** nothing imports it yet. `tests/test_sim_purity.py` globs `sim/*.py` and will scan this
file: it has no clock, no randomness, no I/O and no float, and importing it loads only `decimal`
plus three sim modules. Measured over 20,000 random (price, share) pairs, the flat branch of
`buy_cash` and `sell_cash` and the flat branch of `whole_shares_for` match `sim.model.buy_cost`,
`sim.model.sell_proceeds` and today's `sizing._whole_shares` in **every** case — 0 mismatches.

### Step 5: Sizing takes the rule set
**File:** `engine/src/seer_engine/sim/sizing.py:1-16, :27, :31, :95-105, :108-175`
**Change:** `size_picks` gains a keyword-only `rules`, the import-time `_ONE_PLUS_COST` and the
local `_whole_shares` go, and the three charge sites (`:136` the committed cap, `:151` the share
count, `:166` the running commitment) go through `charges`.

**Code** — the docstring, lines 1-16, in full:

```python
"""Whole-share sizing of ranked picks into free slots (design §5, handover §3 sizing row).

Each night, after session S's close, a strategy hands over its ranked picks for the next session.
``size_picks`` turns them into pending bracket orders:

* slot budget = equity ÷ 4, using the equity at the last snapshot (S's close), so it is recomputed
  every session;
* budget = min(slot budget, cash − buy cash of every pending order already placed for that
  session), so a position that has risen in value cannot lend new picks cash that does not exist;
* shares = the most whole shares whose buy cash fits the budget, priced by ``rules`` --
  ``floor(budget / (limit × (1 + cost_rate)))`` under the flat model, and under
  ``cost_model="gotrade"`` the count solved against Gotrade's measured schedule, whose $0.10
  per-order minimum makes the cost non-proportional (``sim.charges.whole_shares_for``);
* fewer than 1 share → rejected ``lt_one_share``; a symbol already live (open or pending) or
  repeated in the picks → rejected ``held`` (no adding to a holding); no free slot → ``no_slot``.

``rules`` defaults to ``DESIGN_V0``, which is what every caller ran before the lever existed, so
its numbers are unchanged to the last digit.

Picks are handled in the given order (the strategy's rank), and each placed pick takes the lowest
free slot. Pure and deterministic: no I/O, no clock, no randomness, Decimal only.
"""
```

**Code** — line 27 (the import block) becomes:

```python
from seer_engine.dates import is_session
from seer_engine.sim.charges import bracket_rules, buy_cash, whole_shares_for
from seer_engine.sim.model import SLOTS, Order, Portfolio, q
from seer_engine.sim.rules import DESIGN_V0, TradeRules

RejectReason = Literal["no_slot", "held", "lt_one_share"]
```

(`COST_RATE` and `buy_cost` are no longer imported here; line 31's `_ONE_PLUS_COST` and lines
95-105's `_whole_shares` are deleted outright.)

**Code** — `size_picks` in full, replacing lines 108-175:

```python
def size_picks(
    portfolio: Portfolio,
    picks: Sequence[Pick],
    session_date: date,
    *,
    rules: TradeRules = DESIGN_V0,
) -> SizingResult:
    """Size ``picks`` (in rank order) into ``portfolio``'s free slots for ``session_date``.

    ``session_date`` is the session the brackets are placed for (the next session after the
    portfolio's last stepped one). ``rules`` prices every buy: ``DESIGN_V0`` (the default) is the
    flat 0.1% a side the §5 records were closed at; ``DESIGN_V0_GOTRADE`` is Gotrade's measured
    schedule. Returns the portfolio with the new pending orders added, the orders placed (in pick
    order), and the picks rejected (in pick order). Cash is not touched: a pending order reserves
    cash only through the sizing cap, and pays at fill.

    Raises ValueError when ``rules`` are a book or fractional rule set (``sim.charges``).
    """
    if not isinstance(portfolio, Portfolio):
        raise TypeError(f"portfolio must be a Portfolio, got {type(portfolio).__name__}")
    bracket_rules(rules)
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
    committed = sum((buy_cash(o.limit_price, o.shares, rules) for o in pending), Decimal(0))
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
        shares = whole_shares_for(budget, pick.limit_price, rules)
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
        committed += buy_cash(order.limit_price, order.shares, rules)

    if not placed:
        return SizingResult(portfolio=portfolio, placed=(), rejected=tuple(rejected))
    orders = tuple(sorted(portfolio.orders + tuple(placed), key=lambda o: o.slot))
    return SizingResult(
        portfolio=replace(portfolio, orders=orders),
        placed=tuple(placed),
        rejected=tuple(rejected),
    )
```

**Impact:** the measured behaviour change, at the owner's real scale — equity $560, slot budget
$140:

| budget | limit | flat shares | gotrade shares |
|---|---|---|---|
| $140 | $10 | 13 (cost $130.13) | 13 (cost $130.38) |
| $130.20 | $10 | 13 | **12** |
| $28 | $27.90 | 1 | **0** — rejected `lt_one_share` |

The last row is the floor at work: $27.90 plus $0.13 does not fit $28. C will reject picks the flat
model bought, and that is the finding, not a defect.

### Step 6: The lifecycle takes the rule set
**File:** `engine/src/seer_engine/sim/lifecycle.py:35-46, :65-84, :128, :179, :189, :208, :246`
**Change:** `_close` takes `rules` so the pnl subtracts what was really paid at fill; `step` and
`close_unpriced` gain the keyword-only `rules`.

**Code** — the import block, replacing lines 35-46:

```python
from seer_engine.sim.charges import bracket_rules, buy_cash, sell_cash
from seer_engine.sim.model import (
    TIME_STOP_DAYS,
    Event,
    ExitReason,
    Order,
    Portfolio,
    Snapshot,
    StepResult,
    q,
)
from seer_engine.sim.rules import DESIGN_V0, TradeRules
```

**Code** — `_close` in full, replacing lines 65-84:

```python
def _close(
    order: Order,
    when: date,
    price: Decimal,
    reason: ExitReason,
    days_held: int,
    rules: TradeRules,
) -> tuple[Order, Decimal]:
    """The closed order and the cash its sale brings in.

    ``pnl_usd = sell_cash - buy_cash`` under ``rules``, both priced the way the cash actually
    moved, so the sum of pnl reconciles with cash exactly under either cost model.
    """
    if order.fill_price is None:
        raise ValueError(f"{order.symbol} has no fill price")
    exit_price = q(price)
    proceeds = sell_cash(exit_price, order.shares, rules)
    pnl = proceeds - buy_cash(order.fill_price, order.shares, rules)
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
```

**Code** — `step`'s signature and docstring, replacing lines 128-138:

```python
def step(
    portfolio: Portfolio,
    session_date: date,
    bars: Mapping[str, Bar],
    *,
    rules: TradeRules = DESIGN_V0,
) -> StepResult:
    """Advance ``portfolio`` through the NYSE session ``session_date``.

    ``bars`` maps symbol → that session's split-adjusted ``Bar``; a symbol absent from it
    has no bar this session. Only bars for symbols with a live order are read (and
    validated); the rest are ignored.

    ``rules`` prices every fill and exit: ``DESIGN_V0`` (the default) charges the flat 0.1% a
    side the §5 records were closed at, ``DESIGN_V0_GOTRADE`` charges Gotrade's measured
    schedule including its $0.10 per-order minimum (``sim.charges``).

    Raises TypeError on a non-Decimal price or a wrong type, and ValueError when
    ``session_date`` is not an NYSE session, is not after ``portfolio.last_session``,
    differs from a pending order's ``session_date``, or ``rules`` are not a bracket rule set.
    """
    if not isinstance(portfolio, Portfolio):
        raise TypeError(f"portfolio must be a Portfolio, got {type(portfolio).__name__}")
    bracket_rules(rules)
```

(the remaining validation from `:141` on is unchanged)

**Code** — line 179 becomes:

```python
        closed, proceeds = _close(o, session_date, price, reason, days_held, rules)
```

**Code** — line 189 becomes:

```python
            cost = buy_cash(fill_price, o.shares, rules)
```

**Code** — `close_unpriced`'s signature and docstring, replacing lines 208-221:

```python
def close_unpriced(
    portfolio: Portfolio,
    symbols: Iterable[str],
    *,
    rules: TradeRules = DESIGN_V0,
) -> tuple[Portfolio, tuple[Event, ...]]:
    """Force-close open positions that will never get another bar (delisted, halted for good).

    Each named position exits at its last known close (its mark), reason ``time``,
    ``exit_date = portfolio.last_session``, ``days_held`` unchanged, with ``forced=True``
    on its event. Cash takes the proceeds net of ``rules``' cost (the flat rate by default,
    Gotrade's measured schedule under ``cost_model="gotrade"``), and ``equity`` is
    recomputed as ``cash + Σ shares × mark`` for what is still open. Events are in slot
    order. Every symbol must belong to an open position; the caller decides that no
    further bar will come (a pure step cannot know it).
    """
    if not isinstance(portfolio, Portfolio):
        raise TypeError(f"portfolio must be a Portfolio, got {type(portfolio).__name__}")
    bracket_rules(rules)
```

(the remaining body from `:220` on is unchanged except line 246)

**Code** — line 246 becomes:

```python
        closed, proceeds = _close(o, when, marks[o.symbol], "time", o.days_held, rules)
```

**Impact:** measured, a 5-share round trip at the owner's scale — in at $27.90, out at $30.00 —
costs `buy_cash $139.90 / sell_cash $149.50 / pnl $9.60` under Gotrade against
`$139.6395 / $149.8500 / $10.2105` flat: **$0.61 of the $10.21 gain, 6%, is the fee difference on
one trade.** With `rules=DESIGN_V0` every number in `test_sim_lifecycle.py` and
`test_sim_scenario.py` is unchanged.

### Step 7: Splits pay cash in lieu against the right buy cost
**File:** `engine/src/seer_engine/sim/split_adjust.py:35, :113-115, :175`
**Change:** a position liquidated by a reverse split closes with
`pnl_usd = cash in lieu − buy cost`. Under Gotrade the buy cost is not `q(p × n × 1.001)`, so the
pnl would not reconcile with the cash that actually left at fill. Thread `rules` the same way.

**Code** — line 35 becomes:

```python
from seer_engine.sim.charges import bracket_rules, buy_cash
from seer_engine.sim.model import Event, Order, Portfolio
from seer_engine.sim.rules import DESIGN_V0, TradeRules
```

**Code** — the signature, replacing lines 113-115:

```python
def apply_split(
    portfolio: Portfolio,
    symbol: str,
    factor: Decimal,
    session_date: date,
    *,
    rules: TradeRules = DESIGN_V0,
) -> tuple[Portfolio, tuple[Event, ...]]:
```

**Code** — the first validation inside the body, immediately after the `isinstance(portfolio, …)`
check at `:125-126`:

```python
    bracket_rules(rules)
```

**Code** — line 175 becomes:

```python
                pnl_usd=in_lieu - buy_cash(order.fill_price, order.shares, rules),
```

**Code** — the docstring bullet at lines 15-17 becomes:

```python
- An open position whose shares floor to 0 is paid out entirely in lieu. It closes with a forced
  ``exit`` event in pre-split units (reason ``time``, exit at the last mark, ``pnl_usd`` = cash in
  lieu - the buy cash ``rules`` charged at fill), so the sum of ``pnl_usd`` still reconciles with
  cash for that trade.
```

**Impact:** cash in lieu itself is unchanged — it is `q(fraction × adjusted mark)`, paid with no
cost, which is correct under both models (a split pays no brokerage). Only the pnl bookkeeping of a
liquidated position moves, and only under Gotrade.

### Step 8: Export the new surface
**File:** `engine/src/seer_engine/sim/__init__.py:10-13, :16-51, :83-149`
**Change:** add the charges module, the new preset, `BRACKET_ENGINES` and `is_bracket`.

**Code** — the docstring paragraph at lines 10-13 becomes:

```python
P7a adds trade rules as a value (``sim.rules``: ``TradeRules``, ``DESIGN_V0`` and the presets)
and the book engine every non-default rule set runs on (``sim.book``: ``step_book``, and
``apply_book_split`` for splits on live book positions).
``DESIGN_V0`` keeps running on ``size_picks`` + ``step`` above, unchanged. A second bracket rule
set is expressible as ``engine="bracket"`` (``DESIGN_V0_GOTRADE``, §5 at Gotrade's measured fee
schedule); ``sim.charges`` prices the bracket path's money from whichever rule set it is handed.
```

**Code** — insert, between the `sim.book` import block (ends `:32`) and the `sim.lifecycle` one:

```python
from seer_engine.sim.charges import bracket_rules, buy_cash, order_fee, sell_cash, whole_shares_for
```

**Code** — the `sim.rules` import block gains four names (keep alphabetical order within it):
`BRACKET_ENGINES` before `DAILY_SWITCH`, `DESIGN_V0_GOTRADE` directly after `DESIGN_V0`, and
`is_bracket` directly before `is_decision_session`.

**Code** — `__all__` gains, each in its existing alphabetical position:
`"BRACKET_ENGINES"` (first, before `"COST_RATE"`), `"DESIGN_V0_GOTRADE"` (after `"DESIGN_V0"`),
`"bracket_rules"` (after `"apply_split"`), `"buy_cash"` (before `"buy_cost"`), `"is_bracket"`
(before `"is_decision_session"`), `"order_fee"` (after `"new_portfolio"`), `"sell_cash"` (before
`"sell_proceeds"`), `"whole_shares_for"` (after `"to_weight"`, last).

**Impact:** `sim.COST_RATE`, `sim.buy_cost` and `sim.sell_proceeds` stay exported and stay what they
are — `backtest/benchmark.py:36`, `paper/benchmark.py:44`, `paper/roster.py:123` and several tests
import them.

### Step 9: The paper bracket night takes the rule set
**File:** `engine/src/seer_engine/paper/bracket.py:35-45, :108-114, :141, :144, :155, :162-169, :190`
**Change:** both entry points gain the keyword-only `rules` and hand it to the four simulator calls.

**Code** — the import block, replacing lines 35-45:

```python
from seer_engine.sim import (
    DESIGN_V0,
    Event,
    Order,
    Portfolio,
    SizingResult,
    Snapshot,
    TradeRules,
    apply_split,
    bracket_rules,
    close_unpriced,
    size_picks,
    step,
)
```

**Code** — `settle_bracket`'s signature and the paragraph of its docstring that names `rules`,
replacing lines 108-114 and adding to the docstring:

```python
def settle_bracket(
    pf: Portfolio,
    session: date,
    bars: Mapping[str, Bar],
    splits: Sequence[tuple[str, Decimal]],
    last_bar_date: LastBarDate,
    *,
    rules: TradeRules = DESIGN_V0,
) -> BracketNight:
```

add to its docstring, directly before the "Raises" paragraph:

```
    ``rules`` prices every fill, exit and forced close, and the buy cost a reverse split's
    liquidation reconciles against: ``DESIGN_V0`` (the default) is the flat 0.1% a side,
    ``DESIGN_V0_GOTRADE`` is Gotrade's measured schedule. Pass the roster entry's own rules.
```

**Code** — the body's validation, after the `callable(last_bar_date)` check at `:135-136`:

```python
    bracket_rules(rules)
```

**Code** — lines 141, 144 and 155 become:

```python
        pf, split_events = apply_split(pf, symbol, factor, session, rules=rules)
```
```python
    result = step(pf, session, bars, rules=rules)
```
```python
        pf, forced = close_unpriced(pf, gone, rules=rules)
```

**Code** — `decide_bracket`'s signature, replacing lines 162-169:

```python
def decide_bracket(
    pf: Portfolio,
    strategy: Strategy,
    params: Any,
    history: Mapping[str, History],
    members: Set[str],
    data_date: date,
    *,
    rules: TradeRules = DESIGN_V0,
) -> SizingResult:
```

add to its docstring, after the existing second paragraph:

```
    ``rules`` prices the sizing: under ``cost_model="gotrade"`` the share count is solved against
    Gotrade's schedule, whose $0.10 per-order minimum can reject a pick the flat model would have
    bought. Pass the roster entry's own rules.
```

**Code** — the body's validation, after the `isinstance(pf, Portfolio)` check at `:179-180`:

```python
    bracket_rules(rules)
```

**Code** — line 190 becomes:

```python
    return size_picks(pf, picks, dates.next_session(data_date), rules=rules)
```

**Impact:** `commands/paper.py` and `paper/replay.py` keep compiling **and keep their exact
numbers** untouched (the default is `DESIGN_V0`, which is what C carries today). That is what makes
it safe for phase 12 to be the one that wires them (D10).

### Steps 10 and 11 — moved to phase 12 (index Decision D10)

**Nothing is done here.** This planner's Step 10 (`commands/paper.py`'s four `rules=e.rules` call
sites) and Step 11 (`commands/promote.py:275`'s `is_bracket` dispatch) are the **wiring layer**, and
D10 assigns the whole wiring layer to phase 12, because `commands/paper.py` is wanted by phases 3, 4,
6 and 12 and two of those run concurrently in wave 1.

The code is unchanged, reproduced verbatim in **Handoffs → H6** and copied into `phase-12.md` as its
Step 7a. Phase 12 depends on 3, 4, 6 and 7, so it is the only phase that can quote every signature as
it actually landed.

**What this phase must leave true for that to work**, and must verify before it is called done:

- every parameter added by Steps 5, 6, 7 and 9 is **keyword-only with `DESIGN_V0` as its default**;
- `git diff --stat` shows **no** change to `engine/src/seer_engine/commands/paper.py`,
  `engine/src/seer_engine/commands/promote.py`, `engine/src/seer_engine/paper/replay.py` or
  `engine/src/seer_engine/backtest/runner.py`;
- `PYTHONPATH=engine/src python -c "import seer_engine.commands.paper, seer_engine.commands.promote,
  seer_engine.paper.replay"` still succeeds — the unwired callers must keep importing and running;
- the engine suite's failing-node set is identical to the pre-edit one.

### Step 12: Tests
**Files:** `engine/tests/test_sim_rules.py`, `test_sim_sizing.py`, `test_sim_lifecycle.py`,
`test_sim_split.py`, `test_paper_bracket.py`, `test_cost_model_pins.py`

**12a — `test_sim_rules.py:82-88`**, the preset loop, which today asserts every preset but
`DESIGN_V0` is a book rule set. Replace with:

```python
    for r in PRESETS:
        if r is not DESIGN_V0 and r is not DESIGN_V0_GOTRADE:
            assert r.engine == "book"
            assert r.dividends is True
            assert r.cost_rate == Decimal("0.001")
    # The 13 presets that predate Gotrade's measured schedule all keep the flat 0.1% model.
    assert [r.cost_model for r in PRESETS[:13]] == ["flat"] * 13
```

**12b — `test_sim_rules.py:92-111`**, the pinned id list: insert `"design-v0-gotrade"` between
`"monthly-rank-weekly-resize-frac"` and `"monthly-hold-frac-gotrade"`.

**12c — `test_sim_rules.py`**, three new tests:

```python
def test_bracket_is_a_second_bracket_engine_and_bracket_v0_stays_reserved():
    assert rules.BRACKET_ENGINES == ("bracket_v0", "bracket")
    assert rules._ENGINES == ("bracket_v0", "bracket", "book")
    assert is_bracket(DESIGN_V0) and is_bracket(DESIGN_V0_GOTRADE)
    assert not is_bracket(MONTHLY_HOLD) and not is_bracket(V0_BOOK)
    # The new engine does not loosen the reservation: §5's id and engine are still §5's alone.
    with pytest.raises(ValueError, match="reserved for DESIGN_V0"):
        replace(DESIGN_V0, cost_model="gotrade")
    with pytest.raises(ValueError, match="reserved for DESIGN_V0"):
        TradeRules(id="x", engine="bracket_v0")
    with pytest.raises(ValueError, match="reserved for DESIGN_V0"):
        TradeRules(id="design-v0", engine="bracket")
    with pytest.raises(ValueError, match="unknown engine"):
        TradeRules(id="x", engine="brackets")


def test_design_v0_gotrade_is_section_5_at_gotrades_real_fees():
    g = DESIGN_V0_GOTRADE
    assert g.id == "design-v0-gotrade" and g.engine == "bracket" and g.cost_model == "gotrade"
    # Every other lever is DESIGN_V0's, to the field.
    assert replace(g, id="design-v0", engine="bracket_v0", cost_model="flat") == DESIGN_V0
    assert g.cost_rate == DESIGN_V0.cost_rate  # the schedule prices it; the rate stays at default
    assert rule_owner_inputs(g) == ()  # fitted to the owner's own receipts
    assert PRESETS[13] is g and sim.DESIGN_V0_GOTRADE is g
    assert roster.rules_for("design-v0-gotrade") is g


def test_design_v0_still_constructs_and_digests_identically():
    # Strategy C is live with rules_id "design-v0" and a frozen spec: this digest may not move.
    assert DESIGN_V0.engine == "bracket_v0"
    assert roster.rules_dict(DESIGN_V0) == {
        "id": "design-v0",
        "engine": "bracket_v0",
        "cadence": "daily",
        "entry": "limit",
        "max_positions": "4",
        "time_stop": "5",
        "resize": "false",
        "fractional": "false",
        "dividends": "false",
        "idle_symbol": None,
        "cost_rate": "0.001",
    }
    assert "cost_model" not in roster.rules_dict(DESIGN_V0)  # the lever's pinned default
    assert roster.rules_dict(DESIGN_V0_GOTRADE)["cost_model"] == "gotrade"


def test_a_bracket_rule_set_is_described_as_the_bracket_simulator():
    lines = describe_rules(DESIGN_V0_GOTRADE)
    assert lines[1] == "Engine: the design §5 bracket simulator, unchanged."
    assert lines[1] == describe_rules(DESIGN_V0)[1]
    assert lines[4] == describe_rules(DESIGN_V0)[4]  # no open_limit fallback paragraph
    assert lines[11].startswith("Costs: Gotrade's fee schedule measured from the owner's receipts")
    assert "$0.10" in lines[11]
    assert describe_rules(DESIGN_V0)[11] == "Costs: 0.1% per side."
```

(add `DESIGN_V0_GOTRADE`, `is_bracket` and `roster` to that file's imports)

**12d — `test_sim_sizing.py`**, the identity pin plus the Gotrade cases:

```python
def test_the_flat_path_is_byte_identical_to_the_old_module_constants():
    """charges with DESIGN_V0 == sim.model's constants, which is what keeps the closed records."""
    for price, shares in (("50", 100), ("12.3457", 7), ("33", 75), ("10", 99), ("0.0001", 1), ("10", 0)):
        p, n = P(price), shares
        assert buy_cash(p, n, DESIGN_V0) == buy_cost(p, n)
        assert sell_cash(p, n, DESIGN_V0) == sell_proceeds(p, n)
    for budget, limit in (("2500", "33"), ("1000", "10"), ("2000", "10"), ("0", "10"), ("9.99", "10")):
        b, l = P(budget), P(limit)
        shares = whole_shares_for(b, l, DESIGN_V0)
        assert shares == 0 or buy_cost(l, shares) <= b
        assert buy_cost(l, shares + 1) > b


def test_gotrade_sizing_charges_the_measured_schedule():
    # The owner's book: equity 560 -> slot budget 140. Measured from sim.costs.
    res = size_picks(flat("560"), [pick("AAA", "10")], SESSION, rules=DESIGN_V0_GOTRADE)
    (o,) = res.placed
    assert o.shares == 13
    assert buy_cash(P("10"), 13, DESIGN_V0_GOTRADE) == P("130.3800")  # 130.00 + 0.38 of fees
    assert buy_cost(P("10"), 13) == P("130.1300")  # the flat model charged 0.13


def test_the_gotrade_fee_can_drop_a_share_the_flat_model_bought():
    # equity 520.80 -> slot budget 130.20. Flat buys 13 at 130.13; Gotrade's 13 cost 130.38.
    pf = portfolio(P("130.20"), equity=P("520.80"), last_session=PREV)
    flat_res = size_picks(pf, [pick("AAA", "10")], SESSION)
    gt_res = size_picks(pf, [pick("AAA", "10")], SESSION, rules=DESIGN_V0_GOTRADE)
    assert flat_res.placed[0].shares == 13
    assert gt_res.placed[0].shares == 12
    assert buy_cash(P("10"), 12, DESIGN_V0_GOTRADE) == P("120.3400")


def test_the_ten_cent_floor_can_reject_a_pick_the_flat_model_bought():
    # The counterfactual C exists to produce: at a 28 dollar slot a 27.90 pick does not fit,
    # because Gotrade charges 0.13 on top of it (the owner's own receipt: 27.90 -> 28.03 paid).
    pf = portfolio(P("28"), equity=P("112"), last_session=PREV)
    assert size_picks(pf, [pick("AAA", "27.90")], SESSION).placed[0].shares == 1
    gt = size_picks(pf, [pick("AAA", "27.90")], SESSION, rules=DESIGN_V0_GOTRADE)
    assert gt.placed == ()
    assert gt.rejected == (Rejection(symbol="AAA", reason="lt_one_share"),)
    assert buy_cash(P("27.90"), 1, DESIGN_V0_GOTRADE) == P("28.0300")


def test_size_picks_refuses_a_book_or_fractional_rule_set():
    with pytest.raises(ValueError, match="book rule set"):
        size_picks(flat(), [pick("AAA", "10")], SESSION, rules=MONTHLY_HOLD)
    with pytest.raises(ValueError, match="whole share count"):
        size_picks(flat(), [pick("AAA", "10")], SESSION, rules=replace(DESIGN_V0_GOTRADE, id="x", fractional=True))
    with pytest.raises(TypeError, match="TradeRules"):
        size_picks(flat(), [pick("AAA", "10")], SESSION, rules="design-v0")
```

**12e — `test_sim_lifecycle.py`**, the fill/exit/pnl pins:

```python
def test_gotrade_buy_and_sell_cash_reproduce_the_owners_receipts():
    # sim/costs.py is fitted to these two real Gotrade receipts; the bracket path must charge them.
    assert buy_cash(P("27.90"), 1, DESIGN_V0_GOTRADE) == Decimal("28.0300")
    assert sell_cash(P("72.51"), 1, DESIGN_V0_GOTRADE) == Decimal("72.2700")
    # The flat model, for scale.
    assert buy_cost(P("27.90"), 1) == Decimal("27.9279")
    assert sell_proceeds(P("72.51"), 1) == Decimal("72.4375")


def test_a_gotrade_round_trip_reconciles_pnl_with_cash():
    # 5 shares in at 27.90 (cash out 139.90), out at 30.00 (cash in 149.50): pnl 9.60.
    p = portfolio("1000", opened("AAA", MON, "27.90", "30", "25", 5, days_held=1), last_session=MON)
    r = step(p, D(TUE), day(bar("AAA", TUE, "30.10", "30.20", "29.50", "29.80")),
             rules=DESIGN_V0_GOTRADE)
    o = _only(r.events).order
    assert (o.exit_reason, o.exit_price) == ("tp", Decimal("30.1000"))
    assert r.portfolio.cash == Decimal("1000") + sell_cash(P("30.10"), 5, DESIGN_V0_GOTRADE)
    assert o.pnl_usd == sell_cash(P("30.10"), 5, DESIGN_V0_GOTRADE) - buy_cash(P("27.90"), 5, DESIGN_V0_GOTRADE)
    # The same trade on the flat model keeps more of the gain.
    flat_r = step(p, D(TUE), day(bar("AAA", TUE, "30.10", "30.20", "29.50", "29.80")))
    assert flat_r.events[0].order.pnl_usd > o.pnl_usd


def test_a_gotrade_fill_pays_the_schedule_not_the_flat_rate():
    p = portfolio("1000", pending("AAA", D(TUE), "10", "11", "9", 13), last_session=MON)
    r = step(p, D(TUE), day(bar("AAA", TUE, "9.95", "10.50", "9.80", "10.20")),
             rules=DESIGN_V0_GOTRADE)
    fill = _only(r.events)
    assert fill.kind == "fill" and fill.order.fill_price == Decimal("9.9500")
    assert fill.cash_usd == -buy_cash(P("9.95"), 13, DESIGN_V0_GOTRADE)
    assert r.portfolio.cash == Decimal("1000") - buy_cash(P("9.95"), 13, DESIGN_V0_GOTRADE)


def test_close_unpriced_charges_the_rule_sets_cost_model():
    p = portfolio("100", opened("AAA", MON, "10", "12", "9", 20, days_held=2),
                  marks=(("AAA", P("11")),), last_session=D(TUE))
    _, (ev,) = close_unpriced(p, ["AAA"], rules=DESIGN_V0_GOTRADE)
    assert ev.forced and ev.cash_usd == sell_cash(P("11"), 20, DESIGN_V0_GOTRADE)
    assert ev.order.pnl_usd == sell_cash(P("11"), 20, DESIGN_V0_GOTRADE) - buy_cash(P("10"), 20, DESIGN_V0_GOTRADE)


def test_the_bracket_path_refuses_a_book_rule_set():
    p = portfolio("1000", last_session=MON)
    with pytest.raises(ValueError, match="book rule set"):
        step(p, D(TUE), {}, rules=MONTHLY_HOLD)
    with pytest.raises(ValueError, match="book rule set"):
        close_unpriced(p, [], rules=MONTHLY_HOLD)
```

(adjust the `portfolio(...)` / `opened(...)` helper arguments to `simkit`'s real signatures as the
surrounding tests in that file use them; the asserted money is what matters and is measured)

**12f — `test_sim_split.py`**, one test: a reverse split that liquidates an open position under
`DESIGN_V0_GOTRADE` closes with `pnl_usd == in_lieu - buy_cash(fill_price, shares,
DESIGN_V0_GOTRADE)`, and the cash in lieu itself is identical to the flat run (a split pays no
brokerage).

**12g — `test_paper_bracket.py`**, one test: loop `decide_bracket` + `settle_bracket` over the
existing fixture window with `rules=DESIGN_V0_GOTRADE`, and assert (i) the loop still equals a
single `run_backtest`-shaped replay in *shape* — same sessions, same symbols, same slot
assignment — and (ii) its ending equity is strictly below the `DESIGN_V0` run's, because the fees
are strictly higher. Keep the existing parity test exactly as it is: with the default `rules` it
must still pass unchanged, which is the proof that the signature change moved nothing.

**12h — `test_cost_model_pins.py:71-74`**: the list grows to three ids, in `PRESETS` order:

```python
    assert [r.id for r in PRESETS if r.cost_model != "flat"] == [
        "design-v0-gotrade",
        "monthly-hold-frac-gotrade",
        "monthly-rank-weekly-resize-frac-gotrade",
    ]
```

**Impact:** `test_lab_costs.py:257`'s `PRESETS[-2:]` pin, `test_sim_rules.py:88`'s `PRESETS[:13]`
pin and `:352`'s `PRESETS[12]` pin all still hold with no edit, because the new preset goes in at
index 13.

---

## Verification

**Build / lint:**

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild
PYTHONPATH=engine/src python -c "import seer_engine.sim, seer_engine.paper.bracket, seer_engine.commands.paper, seer_engine.commands.promote"
ruff check engine/src engine/tests && ruff format --check engine/src engine/tests
```

**Tests — the full suite is the gate, not a subset.** This is the broadest-blast-radius phase in
the set: it changes four signatures in `sim/` and the preset tuple that half a dozen other test
files pin.

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild
PYTHONPATH=engine/src PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  python -m pytest engine/tests -q -n auto
```

`PYTHONPATH` is **required**: without it pytest silently tests the main checkout instead of this
branch. Never pass `-o addopts`. `main` is RED for two reasons described in handover §6 (phases 1
and 2 fix them); neither is in `sim/`, `paper/bracket.py` or `commands/paper.py`. Record the failing
node ids before the first edit and compare the set afterwards — the two sets must be identical.

**Manual check — the measured claims in this plan, re-run:**

```
PYTHONPATH=engine/src python -c "
from decimal import Decimal as D
from seer_engine.sim import DESIGN_V0, DESIGN_V0_GOTRADE, buy_cash, sell_cash, whole_shares_for, buy_cost
print(buy_cash(D('27.90'), 1, DESIGN_V0_GOTRADE))                      # 28.0300 (receipt: 28.03)
print(sell_cash(D('72.51'), 1, DESIGN_V0_GOTRADE))                     # 72.2700 (receipt: 72.27)
print(whole_shares_for(D('130.20'), D('10'), DESIGN_V0),               # 13
      whole_shares_for(D('130.20'), D('10'), DESIGN_V0_GOTRADE))       # 12
print(whole_shares_for(D('28'), D('27.90'), DESIGN_V0),                # 1
      whole_shares_for(D('28'), D('27.90'), DESIGN_V0_GOTRADE))        # 0
"
```

**Exit criteria:**
1. `TradeRules(id="design-v0-gotrade", engine="bracket", cost_model="gotrade", …)` constructs, is
   `PRESETS[13]`, and `paper.roster.rules_for("design-v0-gotrade")` returns it.
2. `size_picks` / `step` / `close_unpriced` / `apply_split` / `decide_bracket` / `settle_bracket`
   each take a `rules` keyword and charge Gotrade's schedule under it, floor included — the two
   owner receipts reproduced to the cent, and a $28 slot rejecting a $27.90 pick.
3. `DESIGN_V0` constructs, is still `engine="bracket_v0"`, and `roster.rules_dict(DESIGN_V0)` is
   byte-identical to today (no `cost_model` key), so C's frozen spec digest has not moved.
4. The four bracket call sites in `commands/paper.py` are **unchanged**, and the tree still builds
   and the suite still passes with them unchanged — the proof that the capability is inert and that
   phase 12 can wire it later (D10). `git diff --stat` shows no `commands/` file at all.
5. `backtest/runner.py` is unmodified (phase 5 owns its `rules` keyword — Handoffs H1).
6. The engine suite's failing-node set is identical to the pre-edit one (i.e. only the two known
   `main` failures, which phases 1 and 2 own).
7. `PAPER_PAUSED` is still `'true'` and no roster entry was added, edited or retired.

---

## Handoffs

Work found, deliberately not done here, with the file and line:

1. **`backtest/runner.run_backtest` has no `rules` parameter** (`backtest/runner.py:150-215`), so a
   backtest of §5 **at Gotrade's fees** is not yet runnable, and `paper/replay.py:290`'s
   `run_rules(fixed, strategy, params, DESIGN_V0, …)` hard-codes `DESIGN_V0`. Consequence: once
   phase 12 creates the Gotrade C successor, `seer paper check`'s replay of it will reconstruct at
   the flat rate and disagree with the stored records. Nothing breaks before that entry steps a
   session, and `PAPER_PAUSED` is `'true'` with zero sessions stepped, so there is room.
   **ASSIGNED by the reconciler, 2026-10-08, split in two:**
   - `run_backtest(..., *, rules: TradeRules = DESIGN_V0)` forwarding to the three sim calls at
     `runner.py:181`, `:186`, `:197`, plus `run_rules`'s pass-through and
     `book_runner.run_rules:380`'s `== "bracket_v0"` becoming `is_bracket(rules)` — **phase 5**,
     which already owns both files and depends on this one. It is written out as phase 5's Step 2b.
   - `replay.expected_bracket` taking the head's rules — **phase 12** (D10 gives it `paper/replay.py`).

   This phase still leaves `runner.py` byte-identical, so phase 5 quotes it as it stands at `485d416`.
2. **`backtest/book_runner.py:521-522`** prices a bracket run's cost as
   `q(price × shares × COST_RATE)` for the metrics. Under `cost_model="gotrade"` that understates;
   `sim.charges.order_fee(side, price, shares, rules)` is the drop-in. **ASSIGNED: phase 5**
   (it owns `book_runner.py`), in the same step as H1's first half.
3. **`backtest/dev.py:185, :206, :223`** branch on `rules.engine == "bracket_v0"` to tell a bracket
   candidate from a book one; they should use `sim.rules.is_bracket`. Harmless today — this phase
   registers no `"bracket"` candidate anywhere the dev registry can see — but it is a trap for
   whoever first does. **ASSIGNED: phase 7** (it owns `dev.py`), as a one-line hardening.
4. **`lab/real_costs.py:150-154`** (`twins`) refuses any non-book rule set, so `lab costs` cannot
   re-measure a bracket method at Gotrade's fees. That is the lab's deliberate rule (the M0031 book
   rule), not a defect; recording it only so nobody reads it as an oversight. Not a phase in this
   set.
5. **`sim/book.py`'s private `_buy_cash` / `_sell_cash` / `_fee` / `_shares_for`
   (`book.py:339-379`) now duplicate `sim/charges.py`.** Collapsing them into one module would be a
   clean follow-up, but `sim/book.py` is explicitly out of this phase's scope and already complies,
   so it is not touched. Not scheduled.
6. **Phase 12 inputs, restated so they cannot be missed:** preset `DESIGN_V0_GOTRADE`, `rules_id =
   "design-v0-gotrade"`, `TradeRules.engine = "bracket"`, `RosterEntry.engine = "bracket"` (the
   roster's engine column value does not change). C's predecessor is marked retired, never edited,
   and is **never** retired-without-successor: the daily control stays on the roster permanently.

   **H6 — the wiring phase 12 must apply, verbatim.** These are this planner's Steps 10 and 11,
   moved intact under D10. Each is a no-op on today's numbers, because every entry on the roster
   today carries `DESIGN_V0`; `e.rules` is never `None` for a bracket entry
   (`paper/roster.py:656-657` refuses a bracket row without a `rules_id`). Without them a Gotrade
   bracket entry would construct, be stored with the right spec digest, and then pay the flat rate
   every night — the exact failure R4 exists to end.

   `engine/src/seer_engine/commands/paper.py:553-555` becomes:

   ```python
                   sized = decide_bracket(
                       pf,
                       _bracket_strategy(conn, e, p, p),
                       e.params,
                       view.history,
                       view.membership.members_on(d),
                       d,
                       rules=e.rules,
                   )
   ```

   `commands/paper.py:727-734` becomes:

   ```python
           sized = decide_bracket(
               new_portfolio(cash0),
               _bracket_strategy(conn, e, paper_start, paper_start),
               e.params,
               view.history,
               view.membership.members_on(rd.data_date),
               rd.data_date,
               rules=e.rules,
           )
   ```

   `commands/paper.py:777` and `:779`, inside `_step_bracket`, become:

   ```python
           night = settle_bracket(
               pf,
               s,
               view.bars_on(s, pf.held_symbols()),
               tonight.splits_on(s),
               view.last_bar_date,
               rules=e.rules,
           )
           store.save_bracket_night(conn, e.id, night.portfolio, night.events, night.snapshot)
           sized = decide_bracket(
               night.portfolio,
               strategy,
               e.params,
               view.history,
               view.membership.members_on(s),
               s,
               rules=e.rules,
           )
   ```

   `engine/src/seer_engine/commands/promote.py:275` becomes:

   ```python
       engine = "bracket" if is_bracket(rules) else "book"
   ```

   and its import at `:75` becomes:

   ```python
   from seer_engine.sim.rules import PRESETS, TradeRules, is_bracket
   ```

   The dispatch today is `"bracket_v0" -> "bracket", else "book"`, which would file a `"bracket"`
   rule set as a book entry and then ask an `Allocator` for `obj.lookback(params)` on the next line.
   No behaviour changes for anything promotable today: `promote` only ever sees registry candidates,
   all of which are `"book"` or `DESIGN_V0`.

## Rollback

`git revert` the single commit. The phase is additive-with-defaults: the only non-default-safe
pieces are the new file, the new preset and the new engine value, and nothing outside this commit
references them (phases 5 and 12 are the first consumers and land later). Reverting restores
`sizing._ONE_PLUS_COST` and `sizing._whole_shares` and the four original signatures. No file under
`commands/` is in this commit at all, so a revert cannot touch the nightly job.

**Reverting this phase alone is safe only while phase 12 has not landed.** Once a roster entry
carries `rules_id = "design-v0-gotrade"`, `paper.roster.rules_for` would raise `UnknownRules` on
that row and the nightly would fail — so revert 12 first, then 4. The plan index's Rollback section
already says phase 4 is the floor of the 4/5/6/7/12 group; nothing here changes that.
