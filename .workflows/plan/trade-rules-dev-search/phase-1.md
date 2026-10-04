# Phase 1: `TradeRules` + the book engine

**Plan set:** `TRADE_RULES_DEV_SEARCH_PLAN.md`
**Analysis:** `20261003-195606-T7R2_code_analyzer.md`
**Satisfies:** R1 (rules as a value; `DESIGN_V0` == §5; every new lever has synthetic-bar tests at engine level), R8 (pure, deterministic, Decimal-only engine covered by the purity glob)
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/sim`

---

## Goal

After this phase, design §5's trade shape is a value: `sim.rules.TradeRules`, with `DESIGN_V0`
equal to §5 (pinned against `model.SLOTS`, `TIME_STOP_DAYS`, `COST_RATE`), `V0_BOOK`, and the eight
registry presets. A new pure engine, `sim.book.step_book`, executes every non-`DESIGN_V0` rule set
from ranked `Target` weights: signal exits at the next open (with `exit_pending` for missing bars),
trims and adds under `RESIZE_BAND`, dividends on the ex-date, fractional shares, `open` /
`open_limit` / `limit` entries, `max_positions`, any time stop, an idle instrument and a fill-time
cash guard. A session-by-session replay test proves that `step_book(..., V0_BOOK)` reproduces
`size_picks` + `step` exactly (snapshots and closed trades), which de-risks phase 3's
`run_backtest` parity test. Nothing existing in `sim/` changes behaviour.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `seer_engine/sim/rules.py`: `Engine`, `Cadence`, `Entry`, `OPEN_LIMIT_BAND`, `RESIZE_BAND`,
  `SHARE_QUANTUM`, `DEFAULT_ETFS`, `LEVERAGED_ETFS`, `TradeRules`, `DESIGN_V0`, `V0_BOOK`,
  `MONTHLY_HOLD`, `MONTHLY_HOLD_TBILL`, `WEEKLY_HOLD`, `DAILY_SWITCH`, `DAILY_SWITCH_TBILL`,
  `SWING_T10`, `SWING_T20`, `SWING_T20_OPEN`, `PRESETS`, `is_decision_session`,
  `rule_owner_inputs`, `describe_rules` — names, values and signatures exactly as the plan index's
  shared contract.
- `seer_engine/sim/book.py`: `WEIGHT_QUANTUM`, `Target`, `to_weight`, `equal_weight`,
  `ExitReason`, `FillReason`, `RejectReason`, `Position`, `Book` (`held()`, `position()`), `Fill`,
  `Trade`, `BookSnapshot`, `BookStep`, `new_book`, `step_book`, `close_book_unpriced` — fields and
  signatures exactly as the shared contract.
- `tests/test_sim_rules.py` (35 tests), `tests/test_sim_book.py` (56 tests).

**Signature changes:** none to existing code. `step_book`'s `dividends` default is an empty
read-only `MappingProxyType` instead of a literal `{}` (same call interface, no shared mutable
default).

**Additive exports** (`sim/__init__.py`): everything the contract lists (`TradeRules`, `DESIGN_V0`,
`V0_BOOK`, the 8 presets and `PRESETS`, `Target`, `Book`, `Position`, `Fill`, `Trade`,
`BookSnapshot`, `BookStep`, `new_book`, `step_book`, `close_book_unpriced`, `to_weight`,
`equal_weight`) **plus** `is_decision_session`, `rule_owner_inputs`, `describe_rules`,
`OPEN_LIMIT_BAND`, `RESIZE_BAND`, `SHARE_QUANTUM`, `DEFAULT_ETFS`, `LEVERAGED_ETFS`,
`WEIGHT_QUANTUM`. **Not** re-exported from `sim`: `book.ExitReason`, `book.FillReason`,
`book.RejectReason` — `sim.ExitReason` (model) and `sim.RejectReason` (sizing) already exist and
keep their meaning; import the book literals from `seer_engine.sim.book`.

**Interface decisions made here (the contract was silent or self-contradictory):**
1. **Σ weight ≤ 1 is enforced only when `rules.max_positions is None`** (plan index Decisions,
   D-A). With a slot cap, §5-style ranked targets (held symbols + every pick, each at
   `equal_weight(4)`) legitimately sum past 1; the excess is rejected `no_slot` exactly as
   `size_picks` does. Truncating picks in the allocator instead would break parity (`size_picks`
   skips an `lt_one_share` pick and keeps ranking). Phase 2's `PicksAllocator` emits held + every
   non-held pick at `equal_weight(slots)`, uncapped; phase 3's parity relies on this.
2. **`idle_symbol_ok`**: `False` (default) makes a target whose symbol is `rules.idle_symbol` a
   `ValueError`; the runner passes `True` when it has appended the idle target itself. Idle
   semantics (no slot, trims without `resize`, `Trade.idle=True`, not in `invested_usd`) are thus
   reachable only through the runner.
3. **Entry "limit" without `Target.limit`** (plan index Decisions, D-B): an **unheld** target
   with `limit=None` under `rules.entry == "limit"` is bought exactly like `"open_limit"`: buy
   limit and sizing price `q(last × (1 + OPEN_LIMIT_BAND))`, filled when `low < limit` (strict)
   at `min(open, limit)`. This is what lets a BLEND of a price-less core (TIMING) and a priced
   satellite (F7) run under `SWING_T20` (registry row 54). A **held** target with no limit is
   never added to (adds are skipped), so `PicksAllocator`'s and F7's price-less held targets are
   legal and never bought. Nothing raises for a missing limit.
4. **Desired shares** for trims and adds = `shares_for(q(equity × weight), price = target.last)`,
   using the same cost-inclusive whole/fractional rounding as buys. Adds buy
   `min(desired − held, shares_for(available − committed, sizing price))`.
5. **A trim to 0 shares** (desired == 0) sells everything: `Fill.reason = "trim"`, and the closed
   episode's `Trade.exit_reason = "signal"`.
6. **Night exits** = positions with `exit_pending` or (decision session and not targeted). They
   free their slot and count as planned proceeds at `q(mark × shares × (1 − c))`, whether or not
   they get a bar on S. `exit_pending` is sticky: a re-targeted pending position is still sold.
7. A target whose symbol was sold at S's open (time/gap/tp/signal/trim-to-0) is skipped silently
   (no rejection entry).
8. Dividends: validated (`Decimal`, > 0) only when `rules.dividends`; symbols not held are ignored;
   credited in symbol order; a position sold at the open on its ex-date still gets it.
9. `Target` prices are quantized to 4 dp half-up (as `sim.Pick` does) rather than rejected; the
   weight must be an exact multiple of `WEIGHT_QUANTUM` (`ValueError`). `to_weight` also accepts
   an `int`.
10. `sim/rules.py` imports `seer_engine.dates` (needed by `is_decision_session`) and `re`; it does
    **not** import `sim.model` — `DESIGN_V0`'s agreement with the model constants is a test.

**Requires (from earlier phases):** nothing.
**Leaves alone (owned by others):** `sim/model.py`, `sim/lifecycle.py`, `sim/sizing.py`,
`sim/split_adjust.py` (frozen); `strategies/*` (phases 2, 5–8); `backtest/*` (phases 3, 9–12);
`research.py`, `yahoo.py`, `commands/*` (phases 4, 12); `tests/simkit.py` and every existing test
(frozen — imported read-only).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/sim/rules.py` | create | `TradeRules`, `DESIGN_V0`, `V0_BOOK`, presets, cadence, owner inputs, description |
| `engine/src/seer_engine/sim/book.py` | create | `Target`, weights, `Book`/`Position`/`Fill`/`Trade`/`BookSnapshot`/`BookStep`, `step_book`, `close_book_unpriced` |
| `engine/src/seer_engine/sim/__init__.py` | modify (lines 1–58, whole file) | docstring paragraph + additive imports and `__all__` entries; nothing removed |
| `engine/tests/test_sim_rules.py` | create | 35 tests: validation, V0 == model constants, presets, cadence, owner inputs, golden descriptions |
| `engine/tests/test_sim_book.py` | create | 56 tests: one or more per lever, argument checks, the limit-less fallback, P&L reconciliation, V0 replay vs `size_picks` + `step` |

Both new modules sit flat in `sim/`, so `tests/test_sim_purity.py::_sim_sources` globs them with no
edit to that test.

## Implementation Steps

### Step 1: `sim/rules.py`
**File:** `engine/src/seer_engine/sim/rules.py:1` (new)
**Change:** the rule value, `DESIGN_V0`, `V0_BOOK`, the presets, and the three helpers.
`engine="bracket_v0"` is accepted only when every field equals `DESIGN_V0`'s, and
`id="design-v0"` only with `engine="bracket_v0"` (both directions are `ValueError`).
**Code:**
```python
"""Trade rules as a value (P7a, handover D2).

Design §5's trade shape used to be module constants (``SLOTS``, ``TIME_STOP_DAYS``,
``COST_RATE``) and hard-wired code paths. ``TradeRules`` carries every execution lever as one
frozen value:

- ``DESIGN_V0`` is §5 exactly. It is the only rule set with ``engine="bracket_v0"``, and it is
  executed by the unchanged ``sim.size_picks`` + ``sim.step`` path (``backtest.runner``), so the
  closed A, A2 and B records stay byte-identical by construction.
- Every other rule set has ``engine="book"`` and is executed by ``sim.book.step_book``.
  ``V0_BOOK`` is §5 replayed by the book engine; it exists only for the parity test.

Selection levers (slot count, sizing, universe, exposure switch, vol targeting) are not here:
they are functions of history and live in the allocators (``strategies.allocator``).

Pure: no clock, no I/O, no randomness.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from seer_engine import dates

Engine = Literal["bracket_v0", "book"]
Cadence = Literal["daily", "weekly", "monthly"]
Entry = Literal["limit", "open_limit", "open"]

OPEN_LIMIT_BAND = Decimal("0.02")
RESIZE_BAND = Decimal("0.01")
SHARE_QUANTUM = Decimal("0.0001")
DEFAULT_ETFS: frozenset[str] = frozenset({"SPY", "QQQ"})
LEVERAGED_ETFS: frozenset[str] = frozenset({"SSO", "QLD", "UPRO", "TQQQ"})

_ENGINES: tuple[str, ...] = ("bracket_v0", "book")
_CADENCES: tuple[str, ...] = ("daily", "weekly", "monthly")
_ENTRIES: tuple[str, ...] = ("limit", "open_limit", "open")
_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_DEFAULT_COST = Decimal("0.001")
_MAX_COST = Decimal("0.05")
_V0_ID = "design-v0"


def _bool(name: str, x: object) -> bool:
    if not isinstance(x, bool):
        raise TypeError(f"{name} must be a bool, got {type(x).__name__}")
    return x


def _opt_count(name: str, x: object) -> int | None:
    if x is None:
        return None
    if isinstance(x, bool) or not isinstance(x, int):
        raise TypeError(f"{name} must be an int or None, got {type(x).__name__}")
    if x < 1:
        raise ValueError(f"{name} must be >= 1, got {x}")
    return x


@dataclass(frozen=True, slots=True)
class TradeRules:
    """Every execution lever of a rule set. See the module docstring and the plan index."""

    id: str
    engine: Engine
    cadence: Cadence = "daily"
    entry: Entry = "limit"
    max_positions: int | None = None
    time_stop: int | None = None
    resize: bool = False
    fractional: bool = False
    dividends: bool = True
    idle_symbol: str | None = None
    cost_rate: Decimal = _DEFAULT_COST

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            raise TypeError(f"id must be a str, got {type(self.id).__name__}")
        if not _ID_RE.match(self.id):
            raise ValueError(f"id must be kebab-case ^[a-z0-9]+(-[a-z0-9]+)*$, got {self.id!r}")
        for name, allowed in (("engine", _ENGINES), ("cadence", _CADENCES), ("entry", _ENTRIES)):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise TypeError(f"{name} must be a str, got {type(value).__name__}")
            if value not in allowed:
                raise ValueError(f"unknown {name} {value!r}; expected one of {allowed}")
        _opt_count("max_positions", self.max_positions)
        _opt_count("time_stop", self.time_stop)
        _bool("resize", self.resize)
        _bool("fractional", self.fractional)
        _bool("dividends", self.dividends)
        if self.idle_symbol is not None:
            if not isinstance(self.idle_symbol, str):
                raise TypeError(f"idle_symbol must be a str or None, got {type(self.idle_symbol).__name__}")
            if not self.idle_symbol:
                raise ValueError("idle_symbol must be non-empty")
        if not isinstance(self.cost_rate, Decimal):
            raise TypeError(f"cost_rate must be a Decimal, got {type(self.cost_rate).__name__}")
        if not self.cost_rate.is_finite() or not (0 <= self.cost_rate < _MAX_COST):
            raise ValueError(f"cost_rate must be in [0, {_MAX_COST}), got {self.cost_rate}")
        is_v0 = _lever_values(self) == _V0_LEVERS
        if self.engine == "bracket_v0" and not is_v0:
            raise ValueError("engine 'bracket_v0' is reserved for DESIGN_V0 (the unchanged §5 simulator)")
        if self.id == _V0_ID and self.engine != "bracket_v0":
            raise ValueError(f"id {_V0_ID!r} is reserved for DESIGN_V0 (engine 'bracket_v0')")


def _lever_values(r: TradeRules) -> tuple[object, ...]:
    """Every field of ``r`` (``id`` and ``engine`` included), in field order."""
    return tuple(getattr(r, f.name) for f in fields(r))


_V0_LEVERS: tuple[object, ...] = (
    _V0_ID,
    "bracket_v0",
    "daily",
    "limit",
    4,
    5,
    False,
    False,
    False,
    None,
    _DEFAULT_COST,
)

DESIGN_V0 = TradeRules(
    id=_V0_ID,
    engine="bracket_v0",
    cadence="daily",
    entry="limit",
    max_positions=4,
    time_stop=5,
    resize=False,
    fractional=False,
    dividends=False,
    idle_symbol=None,
    cost_rate=Decimal("0.001"),
)
V0_BOOK = replace(DESIGN_V0, id="v0-book", engine="book")

MONTHLY_HOLD = TradeRules(id="monthly-hold", engine="book", cadence="monthly", entry="open_limit", resize=True)
MONTHLY_HOLD_TBILL = replace(MONTHLY_HOLD, id="monthly-hold-tbill", idle_symbol="BIL")
WEEKLY_HOLD = TradeRules(id="weekly-hold", engine="book", cadence="weekly", entry="open_limit", resize=True)
DAILY_SWITCH = TradeRules(id="daily-switch", engine="book", cadence="daily", entry="open_limit", resize=False)
DAILY_SWITCH_TBILL = replace(DAILY_SWITCH, id="daily-switch-tbill", idle_symbol="BIL")
SWING_T10 = TradeRules(id="swing-t10", engine="book", cadence="daily", entry="limit", time_stop=10)
SWING_T20 = replace(SWING_T10, id="swing-t20", time_stop=20)
SWING_T20_OPEN = replace(SWING_T20, id="swing-t20-open", entry="open_limit")

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
)


def _rules(x: object) -> TradeRules:
    if not isinstance(x, TradeRules):
        raise TypeError(f"rules must be a TradeRules, got {type(x).__name__}")
    return x


def is_decision_session(rules: TradeRules, session: date) -> bool:
    """True when ``session`` is one on which ``rules`` acts on the strategy's targets.

    daily: every session; weekly: the first NYSE session of its ISO (year, week); monthly: the
    first NYSE session of its calendar (year, month). ValueError when ``session`` is not an
    NYSE session.
    """
    _rules(rules)
    if isinstance(session, datetime) or not isinstance(session, date):
        raise TypeError(f"session must be a date, got {type(session).__name__}")
    if not dates.is_session(session):
        raise ValueError(f"{session} is not an NYSE session")
    if rules.cadence == "daily":
        return True
    prev = dates.prev_session(session)
    if rules.cadence == "weekly":
        return session.isocalendar()[:2] != prev.isocalendar()[:2]
    return (session.year, session.month) != (prev.year, prev.month)


def rule_owner_inputs(rules: TradeRules) -> tuple[str, ...]:
    """The Gotrade features ``rules`` needs that the owner has not verified, sorted and unique.

    ``market-on-open`` (entry "open"), ``fractional``, ``etf:<symbol>`` (an idle instrument
    outside ``DEFAULT_ETFS``) and ``fee`` (a cost rate other than 0.1% per side). Empty means
    executable under the conservative owner-input defaults.
    """
    _rules(rules)
    out: set[str] = set()
    if rules.entry == "open":
        out.add("market-on-open")
    if rules.fractional:
        out.add("fractional")
    if rules.idle_symbol is not None and rules.idle_symbol not in DEFAULT_ETFS:
        out.add(f"etf:{rules.idle_symbol}")
    if rules.cost_rate != _DEFAULT_COST:
        out.add("fee")
    return tuple(sorted(out))


def _pct(x: Decimal) -> str:
    """``x`` as a plain percentage string: Decimal('0.001') -> '0.1%'."""
    return f"{format((x * 100).normalize(), 'f')}%"


def describe_rules(rules: TradeRules) -> tuple[str, ...]:
    """One fixed plain-English line per field of ``rules``, in field order.

    Used by the dev report and the pre-registration file. Deterministic (golden-tested).
    """
    _rules(rules)
    lines: list[str] = [f"Rule set: {rules.id}."]
    if rules.engine == "bracket_v0":
        lines.append("Engine: the design §5 bracket simulator, unchanged.")
    else:
        lines.append(
            "Engine: the target-weight book; a position the strategy stops wanting is sold at the "
            "next open, and stops and take-profits are fixed at entry."
        )
    if rules.cadence == "daily":
        lines.append("Decisions: every session, from the previous session's close.")
    elif rules.cadence == "weekly":
        lines.append("Decisions: the first session of each ISO week, from the previous session's close.")
    else:
        lines.append("Decisions: the first session of each calendar month, from the previous session's close.")
    if rules.entry == "limit" and rules.engine == "bracket_v0":
        lines.append(
            "Entry: a buy limit at the strategy's limit price for the next session; it fills only "
            "when the low trades below the limit, at the lower of the open and the limit."
        )
    elif rules.entry == "limit":
        lines.append(
            "Entry: a buy limit at the strategy's limit price for the next session; it fills only "
            "when the low trades below the limit, at the lower of the open and the limit. A new "
            f"position the strategy gives no limit price is bought at a limit of the last close + "
            f"{_pct(OPEN_LIMIT_BAND)} instead, filled the same way."
        )
    elif rules.entry == "open_limit":
        lines.append(
            f"Entry: a buy limit at the last close + {_pct(OPEN_LIMIT_BAND)} for the next session; it "
            "fills only when the low trades below the limit, at the lower of the open and the limit."
        )
    else:
        lines.append("Entry: a market order at the next open (needs owner verification: market-on-open).")
    if rules.max_positions is None:
        lines.append("Positions: as many as the strategy targets.")
    else:
        lines.append(f"Positions: at most {rules.max_positions} at a time (the idle instrument not counted).")
    if rules.time_stop is None:
        lines.append("Time stop: none.")
    else:
        lines.append(f"Time stop: sell at the next open once a position has been held {rules.time_stop} sessions.")
    if rules.resize:
        lines.append(
            f"Rebalance: on decision sessions, a held position is traded back to its target weight "
            f"at the open when it is off by at least {_pct(RESIZE_BAND)} of equity."
        )
    else:
        lines.append("Rebalance: none; a held position keeps its shares until it exits.")
    if rules.fractional:
        lines.append(f"Shares: fractional, rounded down to {SHARE_QUANTUM} share (needs owner verification).")
    else:
        lines.append("Shares: whole shares only.")
    if rules.dividends:
        lines.append("Dividends: cash dividends are credited on the ex-date.")
    else:
        lines.append("Dividends: not credited.")
    if rules.idle_symbol is None:
        lines.append("Idle cash: held as cash, earning nothing.")
    else:
        lines.append(f"Idle cash: the unallocated weight is held in {rules.idle_symbol} on decision sessions.")
    lines.append(f"Costs: {_pct(rules.cost_rate)} per side.")
    return tuple(lines)
```
**Impact:** new module only. Importing `seer_engine.sim` now also loads `seer_engine.dates`
(already loaded by `lifecycle.py`), so the purity subprocess test is unaffected.

### Step 2: `sim/book.py`
**File:** `engine/src/seer_engine/sim/book.py:1` (new)
**Change:** the book engine. The algorithm order is the contract's, binding for phase 3's parity:
dividends -> open exits (time, gap, tp-at-open, signal) -> trims -> buys (rank order, idle last;
slots counted as the night before; sized from the last snapshot's equity and night cash +
planned sells; strict `low < limit` at `min(open, limit)`; cash guard) -> intraday SL-then-TP for
positions held before S -> survivors age + mark -> snapshot. Money mirrors `sim.model`:
buy cash `q(p × n × (1 + c))`, proceeds `q(p × n × (1 − c))`, `q` half-up at 4 dp, and the whole-share
sizing is `sizing._whole_shares` (floor, then the step-back loop) on `Decimal` share counts.
**Code:**
```python
"""The book engine: target weights in, fills and holding episodes out (P7a, handover D2).

Every rule set except ``DESIGN_V0`` runs here. Each night a strategy (an allocator) hands over
the instruments it wants held after the next session's open, as ranked ``Target`` values with
weights; ``step_book`` turns them into sells and buys at that session's open, applies stops
and take-profits fixed at entry, credits dividends, and marks the book at the close.

One session, in this exact order (all money ``Decimal``; ``q`` at every product; buy cash
``q(p × n × (1 + c))``, sell proceeds ``q(p × n × (1 − c))``, fee ``q(p × n × c)``):

1. dividends (``rules.dividends``): each position held before S with an ex-date on S is
   credited ``q(shares × amount)``;
2. open exits, in symbol order, positions with a bar on S: time stop, then gap below the
   stop / at or above the take, then a signal exit (``exit_pending``, or a decision session
   whose targets omit the symbol). A position the targets drop that has no bar on S is
   marked ``exit_pending`` and sold at its next bar's open. Nothing sold here is re-bought on S;
3. trims (decision sessions; ``rules.resize`` or the idle instrument): a held target worth
   at least ``RESIZE_BAND × equity`` more than its target weight is sold down at the open;
4. buys, targets in rank order with the idle instrument last: new entries (``max_positions``
   counted as the night before, exactly as ``sim.size_picks``) and adds (same band as trims,
   upward), sized the night before from the last snapshot's equity and the cash the night's
   planned sells will bring, then filled at the open ("open") or when the low trades strictly
   below the limit, at ``min(open, limit)`` ("limit", "open_limit"); a new entry under "limit"
   whose target has no limit price is bought exactly like "open_limit" (limit ``q(last × 1.02)``);
   a held target with no limit price is never added to; a fill cash cannot cover
   is shrunk to what cash affords. A new position is not checked against its stop or take on
   its fill session;
5. intraday exits of positions held before S: ``low <= stop`` at the stop ("sl"), else
   ``high > take`` at the take ("tp");
6. survivors: ``days_held + 1``, marked at the close when there is a bar;
7. snapshot ``q(cash + Σ shares × mark)``.

Under ``V0_BOOK`` with every held symbol re-targeted and §5 brackets for new picks, this is
``sim.size_picks`` + ``sim.step`` exactly (the phase-3 parity test).

Pure: no clock, no I/O, no randomness. Floats are refused at every boundary.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import ROUND_DOWN, ROUND_FLOOR, Decimal
from types import MappingProxyType
from typing import Literal

from seer_engine import dates
from seer_engine.prices import Bar
from seer_engine.sim.model import q
from seer_engine.sim.rules import OPEN_LIMIT_BAND, RESIZE_BAND, SHARE_QUANTUM, TradeRules

WEIGHT_QUANTUM = Decimal("0.000001")

ExitReason = Literal["signal", "time", "gap", "tp", "sl", "forced"]
FillReason = Literal["entry", "add", "trim", "signal", "time", "gap", "tp", "sl", "forced"]
RejectReason = Literal["no_slot", "too_small", "unfilled", "no_bar", "cash"]

_ONE = Decimal(1)
_ZERO = Decimal(0)
_NO_DIVIDENDS: Mapping[str, Decimal] = MappingProxyType({})


# --------------------------------------------------------------------------- validation


def _decimal(name: str, x: object) -> Decimal:
    if not isinstance(x, Decimal):
        raise TypeError(f"{name} must be a Decimal, got {type(x).__name__}")
    if not x.is_finite():
        raise ValueError(f"{name} must be finite, got {x!r}")
    return x


def _price(name: str, x: object) -> Decimal:
    """``x`` as a positive 4-dp Decimal (half-up); a float or other type is a TypeError."""
    v = q(_decimal(name, x))
    if v <= 0:
        raise ValueError(f"{name} must be > 0, got {x!r}")
    return v


def _symbol(name: str, x: object) -> str:
    if not isinstance(x, str):
        raise TypeError(f"{name} must be a str, got {type(x).__name__}")
    if not x:
        raise ValueError(f"{name} must be non-empty")
    return x


def _date(name: str, x: object) -> date:
    if isinstance(x, datetime) or not isinstance(x, date):
        raise TypeError(f"{name} must be a date, got {type(x).__name__}")
    return x


def _int(name: str, x: object) -> int:
    if isinstance(x, bool) or not isinstance(x, int):
        raise TypeError(f"{name} must be an int, got {type(x).__name__}")
    return x


# --------------------------------------------------------------------------- weights


def to_weight(x: float | Decimal) -> Decimal:
    """``x`` quantized DOWN to ``WEIGHT_QUANTUM``. Floats go through their shortest repr.

    ValueError when the result is not > 0 (or ``x`` is not finite); TypeError for a bool or a
    non-numeric value. An int is accepted.
    """
    if isinstance(x, bool):
        raise TypeError("bool is not a weight")
    if isinstance(x, float):
        if not math.isfinite(x):
            raise ValueError(f"weight must be finite, got {x!r}")
        d = Decimal(repr(x))
    elif isinstance(x, int):
        d = Decimal(x)
    elif isinstance(x, Decimal):
        if not x.is_finite():
            raise ValueError(f"weight must be finite, got {x!r}")
        d = x
    else:
        raise TypeError(f"weight must be a float or Decimal, got {type(x).__name__}")
    w = d.quantize(WEIGHT_QUANTUM, rounding=ROUND_DOWN)
    if w <= 0:
        raise ValueError(f"weight {x!r} is not > 0 at {WEIGHT_QUANTUM}")
    return w


def equal_weight(n: int) -> Decimal:
    """``to_weight(1 / n)``: the weight of one of ``n`` equal slots."""
    if _int("n", n) < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    return to_weight(_ONE / n)


# --------------------------------------------------------------------------- values


@dataclass(frozen=True, slots=True)
class Target:
    """One instrument the strategy wants held after the next session's open, in rank order.

    ``weight`` in (0, 1], a multiple of ``WEIGHT_QUANTUM``. Prices are positive Decimals,
    quantized to 4 dp half-up (like ``sim.Pick``). ``stop`` must be below and ``take`` above the
    reference price (``limit``, or ``last`` when there is no limit). A float is a TypeError.
    """

    symbol: str
    weight: Decimal
    last: Decimal
    limit: Decimal | None = None
    stop: Decimal | None = None
    take: Decimal | None = None

    def __post_init__(self) -> None:
        _symbol("symbol", self.symbol)
        w = _decimal("weight", self.weight)
        if not (0 < w <= 1):
            raise ValueError(f"{self.symbol}: weight must be in (0, 1], got {w}")
        if w.quantize(WEIGHT_QUANTUM, rounding=ROUND_DOWN) != w:
            raise ValueError(f"{self.symbol}: weight {w} is not a multiple of {WEIGHT_QUANTUM}")
        object.__setattr__(self, "last", _price("last", self.last))
        for name in ("limit", "stop", "take"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _price(name, value))
        ref = self.limit if self.limit is not None else self.last
        if self.stop is not None and not self.stop < ref:
            raise ValueError(f"{self.symbol}: stop {self.stop} must be below {ref}")
        if self.take is not None and not self.take > ref:
            raise ValueError(f"{self.symbol}: take {self.take} must be above {ref}")


@dataclass(frozen=True, slots=True)
class Position:
    """One holding episode in progress. ``days_held`` counts sessions since the first fill
    (fill session = 1), exactly as ``sim.Order.days_held``."""

    symbol: str
    shares: Decimal
    mark: Decimal
    entry_date: date
    entry_price: Decimal
    days_held: int
    cost_usd: Decimal
    income_usd: Decimal
    stop: Decimal | None
    take: Decimal | None
    exit_pending: bool = False

    def __post_init__(self) -> None:
        _symbol("symbol", self.symbol)
        if _decimal("shares", self.shares) <= 0:
            raise ValueError(f"{self.symbol}: shares must be > 0, got {self.shares}")
        if _decimal("mark", self.mark) <= 0:
            raise ValueError(f"{self.symbol}: mark must be > 0, got {self.mark}")
        _date("entry_date", self.entry_date)
        if _decimal("entry_price", self.entry_price) <= 0:
            raise ValueError(f"{self.symbol}: entry_price must be > 0, got {self.entry_price}")
        if _int("days_held", self.days_held) < 1:
            raise ValueError(f"{self.symbol}: days_held must be >= 1, got {self.days_held}")
        _decimal("cost_usd", self.cost_usd)
        _decimal("income_usd", self.income_usd)
        if self.stop is not None:
            _decimal("stop", self.stop)
        if self.take is not None:
            _decimal("take", self.take)
        if not isinstance(self.exit_pending, bool):
            raise TypeError("exit_pending must be a bool")


@dataclass(frozen=True, slots=True)
class Book:
    """One rule set's state between sessions: real cash, the equity at the last snapshot
    (initial cash before the first session), and the open positions sorted by symbol."""

    cash: Decimal
    equity: Decimal
    positions: tuple[Position, ...] = ()
    last_session: date | None = None

    def __post_init__(self) -> None:
        _decimal("cash", self.cash)
        _decimal("equity", self.equity)
        if not isinstance(self.positions, tuple):
            raise TypeError("positions must be a tuple")
        prev = ""
        for p in self.positions:
            if not isinstance(p, Position):
                raise TypeError(f"positions must hold Position values, got {type(p).__name__}")
            if p.symbol <= prev:
                raise ValueError("positions must be sorted by symbol, one per symbol")
            prev = p.symbol
        if self.last_session is not None:
            _date("last_session", self.last_session)

    def held(self) -> frozenset[str]:
        """Every symbol with an open position."""
        return frozenset(p.symbol for p in self.positions)

    def position(self, symbol: str) -> Position | None:
        """The open position in ``symbol``, or None."""
        for p in self.positions:
            if p.symbol == symbol:
                return p
        return None


@dataclass(frozen=True, slots=True)
class Fill:
    session_date: date
    symbol: str
    side: Literal["buy", "sell"]
    shares: Decimal
    price: Decimal
    cash_usd: Decimal
    cost_usd: Decimal
    reason: FillReason


@dataclass(frozen=True, slots=True)
class Trade:
    """One closed holding episode: shares went 0 -> > 0 -> 0."""

    symbol: str
    entry_date: date
    exit_date: date
    entry_price: Decimal
    exit_price: Decimal
    days_held: int
    cost_usd: Decimal
    income_usd: Decimal
    pnl_usd: Decimal
    exit_reason: ExitReason
    idle: bool


@dataclass(frozen=True, slots=True)
class BookSnapshot:
    date: date
    cash_usd: Decimal
    equity_usd: Decimal
    invested_usd: Decimal


@dataclass(frozen=True, slots=True)
class BookStep:
    book: Book
    fills: tuple[Fill, ...]
    trades: tuple[Trade, ...]
    dividends: tuple[tuple[str, Decimal], ...]
    rejected: tuple[tuple[str, RejectReason], ...]
    snapshot: BookSnapshot


def new_book(cash_usd: Decimal) -> Book:
    """An empty book with ``cash = equity = q(cash_usd)``, which must be > 0."""
    cash = q(_decimal("cash_usd", cash_usd))
    if cash <= 0:
        raise ValueError(f"cash_usd must be > 0, got {cash_usd}")
    return Book(cash=cash, equity=cash)


# --------------------------------------------------------------------------- money


def _buy_cash(price: Decimal, shares: Decimal, rules: TradeRules) -> Decimal:
    return q(price * shares * (_ONE + rules.cost_rate))


def _sell_cash(price: Decimal, shares: Decimal, rules: TradeRules) -> Decimal:
    return q(price * shares * (_ONE - rules.cost_rate))


def _fee(price: Decimal, shares: Decimal, rules: TradeRules) -> Decimal:
    return q(price * shares * rules.cost_rate)


def _shares_for(budget: Decimal, price: Decimal, rules: TradeRules) -> Decimal:
    """The most shares whose unrounded buy cash ``price × n × (1 + c)`` fits ``budget``:
    whole shares (``sim.sizing._whole_shares``, step-back loop included) or, with
    ``rules.fractional``, multiples of ``SHARE_QUANTUM``. 0 when nothing fits."""
    if budget <= 0:
        return _ZERO
    unit = price * (_ONE + rules.cost_rate)
    if rules.fractional:
        shares = (budget / unit).quantize(SHARE_QUANTUM, rounding=ROUND_FLOOR)
        while shares > 0 and unit * shares > budget:
            shares -= SHARE_QUANTUM
    else:
        shares = Decimal(int((budget / unit).to_integral_value(rounding=ROUND_FLOOR)))
        while shares > 0 and unit * shares > budget:
            shares -= 1
    return shares if shares > 0 else _ZERO


def _desired_shares(equity: Decimal, weight: Decimal, last: Decimal, rules: TradeRules) -> Decimal:
    """Shares a target weight is worth at ``last``: ``_shares_for(q(equity × weight), last)``."""
    return _shares_for(q(equity * weight), last, rules)


def _sizing_price(t: Target, rules: TradeRules) -> Decimal:
    """The buy limit (and sizing price): ``t.limit`` under entry "limit" when the target has
    one; otherwise ``q(t.last × (1 + OPEN_LIMIT_BAND))`` ("open_limit", the sizing price of
    "open", and the fallback for a limit-entry target with no limit price: plan index D-B)."""
    if rules.entry == "limit" and t.limit is not None:
        return t.limit
    return q(t.last * (_ONE + OPEN_LIMIT_BAND))


def _check_bar(symbol: str, bar: object, session: date) -> Bar:
    if not isinstance(bar, Bar):
        raise TypeError(f"bars[{symbol!r}] must be a Bar, got {type(bar).__name__}")
    if bar.symbol != symbol:
        raise ValueError(f"bars[{symbol!r}] holds a bar for {bar.symbol!r}")
    if bar.date != session:
        raise ValueError(f"bars[{symbol!r}] is dated {bar.date}, expected {session}")
    for name in ("open", "high", "low", "close"):
        value = getattr(bar, name)
        if not isinstance(value, Decimal):
            raise TypeError(f"{symbol} {name} must be a Decimal, got {type(value).__name__}")
        if not value.is_finite() or value <= 0:
            raise ValueError(f"{symbol} {name} must be a finite price > 0, got {value}")
    return bar


def _close_out(
    p: Position, when: date, price: Decimal, reason: ExitReason, days_held: int, rules: TradeRules, fill_reason: FillReason
) -> tuple[Decimal, Fill, Trade]:
    """Sell all of ``p`` at ``price``: (proceeds, the sell fill, the closed episode)."""
    exit_price = q(price)
    proceeds = _sell_cash(exit_price, p.shares, rules)
    fill = Fill(
        session_date=when,
        symbol=p.symbol,
        side="sell",
        shares=p.shares,
        price=exit_price,
        cash_usd=proceeds,
        cost_usd=_fee(exit_price, p.shares, rules),
        reason=fill_reason,
    )
    income = p.income_usd + proceeds
    trade = Trade(
        symbol=p.symbol,
        entry_date=p.entry_date,
        exit_date=when,
        entry_price=p.entry_price,
        exit_price=exit_price,
        days_held=days_held,
        cost_usd=p.cost_usd,
        income_usd=income,
        pnl_usd=income - p.cost_usd,
        exit_reason=reason,
        idle=p.symbol == rules.idle_symbol,
    )
    return proceeds, fill, trade


def _valuation(cash: Decimal, positions: Iterable[Position], idle_symbol: str | None) -> tuple[Decimal, Decimal]:
    """(equity, invested): q(cash + Σ shares × mark) and q(Σ shares × mark) over non-idle."""
    total = cash
    invested = _ZERO
    for p in positions:
        value = p.shares * p.mark
        total += value
        if p.symbol != idle_symbol:
            invested += value
    return q(total), q(invested)


def _check_targets(targets: object, rules: TradeRules, idle_symbol_ok: bool) -> tuple[Target, ...] | None:
    if targets is None:
        return None
    if not isinstance(targets, tuple):
        raise TypeError(f"targets must be a tuple or None, got {type(targets).__name__}")
    seen: set[str] = set()
    total = _ZERO
    for t in targets:
        if not isinstance(t, Target):
            raise TypeError(f"targets must hold Target values, got {type(t).__name__}")
        if t.symbol in seen:
            raise ValueError(f"{t.symbol} appears twice in the targets")
        seen.add(t.symbol)
        if t.symbol == rules.idle_symbol and not idle_symbol_ok:
            raise ValueError(
                f"{t.symbol} is the idle instrument; only a caller that appended the idle target "
                f"(idle_symbol_ok=True) may target it"
            )
        total += t.weight
    if rules.max_positions is None and total > 1:
        # With max_positions set, targets beyond the free slots are rejected "no_slot" (§5 picks
        # are ranked past the slot count on purpose), so only an uncapped book enforces Σ <= 1.
        raise ValueError(f"target weights sum to {total} > 1")
    return targets


# --------------------------------------------------------------------------- one session


def step_book(
    book: Book,
    session: date,
    bars: Mapping[str, Bar],
    targets: tuple[Target, ...] | None,
    rules: TradeRules,
    dividends: Mapping[str, Decimal] = _NO_DIVIDENDS,
    idle_symbol_ok: bool = False,
) -> BookStep:
    """Advance ``book`` through the NYSE session ``session`` (see the module docstring).

    ``targets`` None: not a decision session (no signal exits, entries, trims or adds).
    ``targets`` (): a decision session that wants nothing (every position is signal-exited).
    ``dividends``: {symbol: cash amount per share} for ex-dates ON ``session``.
    ``idle_symbol_ok``: True when the caller appended the ``rules.idle_symbol`` target itself
    (the runner); otherwise a target for the idle instrument is a ValueError.

    TypeError on a wrong type (a float anywhere included). ValueError when ``rules.engine`` is
    not "book", ``session`` is not an NYSE session after ``book.last_session``, the targets
    repeat a symbol, or they weigh more than 1 while ``rules.max_positions`` is None. A new
    entry under entry "limit" with no limit price is bought like "open_limit" (never an error).
    """
    if not isinstance(book, Book):
        raise TypeError(f"book must be a Book, got {type(book).__name__}")
    if not isinstance(rules, TradeRules):
        raise TypeError(f"rules must be a TradeRules, got {type(rules).__name__}")
    if rules.engine != "book":
        raise ValueError(f"step_book runs engine 'book' rules only, got {rules.engine!r} ({rules.id})")
    _date("session", session)
    if not dates.is_session(session):
        raise ValueError(f"{session} is not an NYSE session")
    if book.last_session is not None and session <= book.last_session:
        raise ValueError(f"{session} is not after the last session stepped ({book.last_session})")
    if not isinstance(bars, Mapping):
        raise TypeError(f"bars must be a Mapping, got {type(bars).__name__}")
    if not isinstance(dividends, Mapping):
        raise TypeError(f"dividends must be a Mapping, got {type(dividends).__name__}")
    if not isinstance(idle_symbol_ok, bool):
        raise TypeError("idle_symbol_ok must be a bool")
    held_at_night = book.held()
    checked = _check_targets(targets, rules, idle_symbol_ok)
    wanted: dict[str, Target] | None = None if checked is None else {t.symbol: t for t in checked}

    day: dict[str, Bar] = {}
    for symbol in sorted(held_at_night | (frozenset(wanted) if wanted is not None else frozenset())):
        b = bars.get(symbol)
        if b is not None:
            day[symbol] = _check_bar(symbol, b, session)

    idle = rules.idle_symbol
    equity = book.equity
    cash = book.cash
    pos: dict[str, Position] = {p.symbol: p for p in book.positions}
    fills_open: list[Fill] = []
    fills_trim: list[Fill] = []
    fills_buy: list[Fill] = []
    fills_intraday: list[Fill] = []
    trades: list[Trade] = []
    credited: list[tuple[str, Decimal]] = []
    rejected: list[tuple[str, RejectReason]] = []

    # The night before S: planned signal exits and trims (they fund buys and free slots).
    night_exits: set[str] = set()
    planned = _ZERO
    for p in book.positions:
        if p.exit_pending or (wanted is not None and p.symbol not in wanted):
            night_exits.add(p.symbol)
            planned += _sell_cash(p.mark, p.shares, rules)
    if wanted is not None:
        for p in book.positions:
            t = wanted.get(p.symbol)
            if t is None or p.symbol in night_exits or not (rules.resize or p.symbol == idle):
                continue
            desired = _desired_shares(equity, t.weight, t.last, rules)
            excess = p.shares - desired
            if excess > 0 and excess * t.last >= RESIZE_BAND * equity:
                planned += _sell_cash(t.last, excess, rules)
    slots_used = sum(1 for p in book.positions if p.symbol != idle and p.symbol not in night_exits)

    # (1) dividends on the ex-date, to positions held at the previous close.
    if rules.dividends:
        for symbol in sorted(dividends):
            amount = _decimal(f"dividends[{symbol!r}]", dividends[symbol])
            if amount <= 0:
                raise ValueError(f"dividends[{symbol!r}] must be > 0, got {amount}")
            p = pos.get(symbol)
            if p is None:
                continue
            credit = q(p.shares * amount)
            cash += credit
            pos[symbol] = replace(p, income_usd=p.income_usd + credit)
            credited.append((symbol, credit))

    # (2) exits at the open: time stop, gap, signal.
    sold_at_open: set[str] = set()
    for symbol in sorted(pos):
        p = pos[symbol]
        b = day.get(symbol)
        dropped = p.exit_pending or (wanted is not None and symbol not in wanted)
        if b is None:
            if dropped and not p.exit_pending:
                pos[symbol] = replace(p, exit_pending=True)
            continue
        reason: ExitReason | None = None
        if rules.time_stop is not None and p.days_held >= rules.time_stop:
            reason = "time"
        elif p.stop is not None and b.open <= p.stop:
            reason = "gap"
        elif p.take is not None and b.open >= p.take:
            reason = "tp"
        elif dropped:
            reason = "signal"
        if reason is None:
            continue
        proceeds, fill, trade = _close_out(p, session, b.open, reason, p.days_held, rules, reason)
        cash += proceeds
        fills_open.append(fill)
        trades.append(trade)
        del pos[symbol]
        sold_at_open.add(symbol)

    # (3) trims at the open (decision sessions; resize rules or the idle instrument).
    if wanted is not None:
        for symbol in sorted(pos):
            p = pos[symbol]
            t = wanted.get(symbol)
            b = day.get(symbol)
            if t is None or b is None or p.exit_pending or not (rules.resize or symbol == idle):
                continue
            desired = _desired_shares(equity, t.weight, t.last, rules)
            excess = p.shares - desired
            if excess <= 0 or excess * t.last < RESIZE_BAND * equity:
                continue
            if desired <= 0:
                proceeds, fill, trade = _close_out(p, session, b.open, "signal", p.days_held, rules, "trim")
                cash += proceeds
                fills_trim.append(fill)
                trades.append(trade)
                del pos[symbol]
                sold_at_open.add(symbol)
                continue
            price = q(b.open)
            proceeds = _sell_cash(price, excess, rules)
            cash += proceeds
            fills_trim.append(
                Fill(session, symbol, "sell", excess, price, proceeds, _fee(price, excess, rules), "trim")
            )
            pos[symbol] = replace(p, shares=desired, income_usd=p.income_usd + proceeds)

    # (4) buys in rank order, the idle instrument last.
    new_today: set[str] = set()
    if checked is not None:
        ordered = [t for t in checked if t.symbol != idle] + [t for t in checked if t.symbol == idle]
        available = book.cash + planned
        committed = _ZERO
        for t in ordered:
            symbol = t.symbol
            if symbol in sold_at_open:
                continue
            is_idle = symbol == idle
            p = pos.get(symbol)
            if p is not None:
                if p.exit_pending or not (rules.resize or is_idle):
                    continue
                if rules.entry == "limit" and t.limit is None:
                    continue
                desired = _desired_shares(equity, t.weight, t.last, rules)
                gap = desired - p.shares
                if gap <= 0 or gap * t.last < RESIZE_BAND * equity:
                    continue
                price = _sizing_price(t, rules)
                shares = min(gap, _shares_for(available - committed, price, rules))
                if shares <= 0:
                    rejected.append((symbol, "too_small"))
                    continue
                fill_reason: FillReason = "add"
            else:
                if not is_idle and rules.max_positions is not None and slots_used >= rules.max_positions:
                    rejected.append((symbol, "no_slot"))
                    continue
                price = _sizing_price(t, rules)
                budget = min(q(equity * t.weight), available - committed)
                shares = _shares_for(budget, price, rules)
                if shares <= 0:
                    rejected.append((symbol, "too_small"))
                    continue
                if not is_idle:
                    slots_used += 1
                fill_reason = "entry"
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
            fills_buy.append(
                Fill(session, symbol, "buy", shares, fill_price, -cost, _fee(fill_price, shares, rules), fill_reason)
            )
            if p is not None:
                pos[symbol] = replace(p, shares=p.shares + shares, cost_usd=p.cost_usd + cost)
            else:
                pos[symbol] = Position(
                    symbol=symbol,
                    shares=shares,
                    mark=b.close,
                    entry_date=session,
                    entry_price=fill_price,
                    days_held=1,
                    cost_usd=cost,
                    income_usd=_ZERO,
                    stop=t.stop,
                    take=t.take,
                )
                new_today.add(symbol)

    # (5) intraday exits of positions held before S (SL before TP).
    for symbol in sorted(pos):
        if symbol in new_today:
            continue
        p = pos[symbol]
        b = day.get(symbol)
        if b is None:
            continue
        if p.stop is not None and b.low <= p.stop:
            hit: tuple[Decimal, ExitReason] | None = (p.stop, "sl")
        elif p.take is not None and b.high > p.take:
            hit = (p.take, "tp")
        else:
            hit = None
        if hit is None:
            continue
        proceeds, fill, trade = _close_out(p, session, hit[0], hit[1], p.days_held + 1, rules, hit[1])
        cash += proceeds
        fills_intraday.append(fill)
        trades.append(trade)
        del pos[symbol]

    # (6) survivors age one session and are marked at the close.
    for symbol in sorted(pos):
        if symbol in new_today:
            continue
        p = pos[symbol]
        b = day.get(symbol)
        pos[symbol] = replace(p, days_held=p.days_held + 1, mark=b.close if b is not None else p.mark)

    # (7) snapshot.
    positions = tuple(pos[s] for s in sorted(pos))
    equity_now, invested = _valuation(cash, positions, idle)
    return BookStep(
        book=Book(cash=cash, equity=equity_now, positions=positions, last_session=session),
        fills=tuple(fills_open + fills_trim + fills_buy + fills_intraday),
        trades=tuple(trades),
        dividends=tuple(credited),
        rejected=tuple(rejected),
        snapshot=BookSnapshot(date=session, cash_usd=cash, equity_usd=equity_now, invested_usd=invested),
    )


def close_book_unpriced(
    book: Book, symbols: Iterable[str], rules: TradeRules
) -> tuple[Book, tuple[Fill, ...], tuple[Trade, ...]]:
    """Force-close positions that will never get another bar (mirrors ``sim.close_unpriced``).

    Each named position is sold at its mark, reason "forced", ``exit_date =
    book.last_session``, ``days_held`` unchanged, in symbol order. ``equity`` is recomputed for
    what stays open. Every symbol must be held; ValueError before any session was stepped.
    """
    if not isinstance(book, Book):
        raise TypeError(f"book must be a Book, got {type(book).__name__}")
    if not isinstance(rules, TradeRules):
        raise TypeError(f"rules must be a TradeRules, got {type(rules).__name__}")
    if isinstance(symbols, str):
        raise TypeError("symbols must be an iterable of symbols, not a single str")
    wanted: set[str] = set()
    for s in symbols:
        if not isinstance(s, str):
            raise TypeError(f"symbol must be a str, got {type(s).__name__}")
        wanted.add(s)
    if not wanted:
        return book, (), ()
    held = book.held()
    for s in sorted(wanted):
        if s not in held:
            raise ValueError(f"{s} is not an open position")
    when = book.last_session
    if when is None:
        raise ValueError("cannot close a position before any session was stepped")
    cash = book.cash
    keep: list[Position] = []
    fills: list[Fill] = []
    trades: list[Trade] = []
    for p in book.positions:
        if p.symbol not in wanted:
            keep.append(p)
            continue
        proceeds, fill, trade = _close_out(p, when, p.mark, "forced", p.days_held, rules, "forced")
        cash += proceeds
        fills.append(fill)
        trades.append(trade)
    positions = tuple(keep)
    equity, _ = _valuation(cash, positions, rules.idle_symbol)
    return Book(cash=cash, equity=equity, positions=positions, last_session=when), tuple(fills), tuple(trades)
```
**Impact:** new module only. No existing code calls it until phase 3.

**Parity notes (why `V0_BOOK` == `size_picks` + `step`, checked by the replay test in Step 5):**
- slot budget: `q(equity × 0.250000) == q(equity / 4)` exactly; `committed` counts every sized
  buy (filled or not), as pending orders do at night; a sized buy takes its slot even if it later
  goes `unfilled`/`no_bar`, as a pending order does;
- with every held symbol re-targeted and `resize=False` there are no night exits or trims, so
  `available == book.cash == portfolio.cash`;
- `size_picks` never over-commits cash and fills are at or below the limit, so the cash guard
  never fires under V0; the different in-session order (intraday exits after buys) only changes
  the order of cash additions, never the result;
- time stop / gap / tp-at-open keep `days_held`; intraday SL/TP use `days_held + 1`; a fill's
  `days_held` is 1 and is not aged on its fill session; forced closes keep `days_held`.

### Step 3: additive exports in `sim/__init__.py`
**File:** `engine/src/seer_engine/sim/__init__.py:1-58` (whole file; every existing import and
`__all__` entry is kept)
**Change:** one docstring paragraph, two new import blocks (`sim.book`, `sim.rules`), new
`__all__` entries in sorted position.
**Code:**
```python
"""Seer fill simulator: pure, deterministic order lifecycle and portfolio accounting.

One code path for the backtest (P3) and nightly paper trading (P4). No database, no
network, no clock: importing this package must never load psycopg, requests or yfinance
(enforced by tests/test_sim_purity.py).

Per session S: ``apply_split`` (only if a split executes on S) -> ``step(S)`` -> persist
events and snapshot -> ``size_picks(..., next session)``. See engine/package_readme.md.

P7a adds trade rules as a value (``sim.rules``: ``TradeRules``, ``DESIGN_V0`` and the presets)
and the book engine every non-default rule set runs on (``sim.book``: ``step_book``).
``DESIGN_V0`` keeps running on ``size_picks`` + ``step`` above, unchanged.
"""

from seer_engine.sim.book import (
    WEIGHT_QUANTUM,
    Book,
    BookSnapshot,
    BookStep,
    Fill,
    Position,
    Target,
    Trade,
    close_book_unpriced,
    equal_weight,
    new_book,
    step_book,
    to_weight,
)
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
from seer_engine.sim.rules import (
    DAILY_SWITCH,
    DAILY_SWITCH_TBILL,
    DEFAULT_ETFS,
    DESIGN_V0,
    LEVERAGED_ETFS,
    MONTHLY_HOLD,
    MONTHLY_HOLD_TBILL,
    OPEN_LIMIT_BAND,
    PRESETS,
    RESIZE_BAND,
    SHARE_QUANTUM,
    SWING_T10,
    SWING_T20,
    SWING_T20_OPEN,
    V0_BOOK,
    WEEKLY_HOLD,
    TradeRules,
    describe_rules,
    is_decision_session,
    rule_owner_inputs,
)
from seer_engine.sim.sizing import Pick, RejectReason, Rejection, SizingResult, size_picks
from seer_engine.sim.split_adjust import apply_split

__all__ = [
    "COST_RATE",
    "DAILY_SWITCH",
    "DAILY_SWITCH_TBILL",
    "DEFAULT_ETFS",
    "DESIGN_V0",
    "LEVERAGED_ETFS",
    "MONTHLY_HOLD",
    "MONTHLY_HOLD_TBILL",
    "OPEN_LIMIT_BAND",
    "PRESETS",
    "RESIZE_BAND",
    "SHARE_QUANTUM",
    "SLOTS",
    "SWING_T10",
    "SWING_T20",
    "SWING_T20_OPEN",
    "TIME_STOP_DAYS",
    "V0_BOOK",
    "WEEKLY_HOLD",
    "WEIGHT_QUANTUM",
    "Book",
    "BookSnapshot",
    "BookStep",
    "Event",
    "EventKind",
    "ExitReason",
    "Fill",
    "Order",
    "OrderStatus",
    "Pick",
    "Portfolio",
    "Position",
    "RejectReason",
    "Rejection",
    "SizingResult",
    "Snapshot",
    "StepResult",
    "Target",
    "Trade",
    "TradeRules",
    "apply_split",
    "buy_cost",
    "close_book_unpriced",
    "close_unpriced",
    "describe_rules",
    "equal_weight",
    "initial_cash_usd",
    "is_decision_session",
    "new_book",
    "new_portfolio",
    "q",
    "rule_owner_inputs",
    "sell_proceeds",
    "size_picks",
    "step",
    "step_book",
    "to_weight",
]
```
**Impact:** additive. `sim.ExitReason` and `sim.RejectReason` still mean the model/sizing
literals.

### Step 4: `tests/test_sim_rules.py`
**File:** `engine/tests/test_sim_rules.py:1` (new)
**Change:** 35 tests: `DESIGN_V0` vs `model.SLOTS/TIME_STOP_DAYS/COST_RATE`, `V0_BOOK`, constants,
pinned preset values, unique ids in order, exports, frozen/hashable, the `bracket_v0` reservation
both ways, id/literal/count/flag/idle/cost validation, daily/weekly/monthly cadence around MLK
day, ISO week 53 and New Year, non-session rejection, owner inputs, and golden descriptions.
**Code:**
```python
"""Trade rules as a value (P7a phase 1): validation, DESIGN_V0 == §5, presets, cadence,
owner inputs and the plain-English description. No database needed."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime
from decimal import Decimal

import pytest

from seer_engine import sim
from seer_engine.sim import model, rules
from seer_engine.sim.rules import (
    DAILY_SWITCH,
    DAILY_SWITCH_TBILL,
    DESIGN_V0,
    MONTHLY_HOLD,
    MONTHLY_HOLD_TBILL,
    PRESETS,
    SWING_T10,
    SWING_T20,
    SWING_T20_OPEN,
    V0_BOOK,
    WEEKLY_HOLD,
    TradeRules,
    describe_rules,
    is_decision_session,
    rule_owner_inputs,
)


def D(s: str) -> date:
    return date.fromisoformat(s)


# ============================================================== DESIGN_V0 and the presets


def test_design_v0_agrees_with_the_model_constants():
    assert DESIGN_V0.engine == "bracket_v0"
    assert DESIGN_V0.max_positions == model.SLOTS
    assert DESIGN_V0.time_stop == model.TIME_STOP_DAYS
    assert DESIGN_V0.cost_rate == model.COST_RATE
    assert DESIGN_V0.cadence == "daily"
    assert DESIGN_V0.entry == "limit"
    assert (DESIGN_V0.resize, DESIGN_V0.fractional, DESIGN_V0.dividends) == (False, False, False)
    assert DESIGN_V0.idle_symbol is None


def test_v0_book_is_design_v0_on_the_book_engine():
    assert V0_BOOK.id == "v0-book"
    assert V0_BOOK.engine == "book"
    assert replace(V0_BOOK, id="design-v0", engine="bracket_v0") == DESIGN_V0
    assert V0_BOOK not in PRESETS


def test_constants():
    assert rules.OPEN_LIMIT_BAND == Decimal("0.02")
    assert rules.RESIZE_BAND == Decimal("0.01")
    assert rules.SHARE_QUANTUM == Decimal("0.0001")
    assert rules.DEFAULT_ETFS == frozenset({"SPY", "QQQ"})
    assert rules.LEVERAGED_ETFS == frozenset({"SSO", "QLD", "UPRO", "TQQQ"})


def test_preset_values_are_pinned():
    assert MONTHLY_HOLD == TradeRules(id="monthly-hold", engine="book", cadence="monthly", entry="open_limit", resize=True)
    assert MONTHLY_HOLD_TBILL == replace(MONTHLY_HOLD, id="monthly-hold-tbill", idle_symbol="BIL")
    assert WEEKLY_HOLD == TradeRules(id="weekly-hold", engine="book", cadence="weekly", entry="open_limit", resize=True)
    assert DAILY_SWITCH == TradeRules(id="daily-switch", engine="book", cadence="daily", entry="open_limit")
    assert DAILY_SWITCH_TBILL.idle_symbol == "BIL" and DAILY_SWITCH_TBILL.resize is False
    assert SWING_T10 == TradeRules(id="swing-t10", engine="book", entry="limit", time_stop=10)
    assert SWING_T20.time_stop == 20 and SWING_T20.entry == "limit"
    assert SWING_T20_OPEN.time_stop == 20 and SWING_T20_OPEN.entry == "open_limit"
    for r in PRESETS:
        if r is not DESIGN_V0:
            assert r.engine == "book"
            assert r.dividends is True
            assert r.cost_rate == Decimal("0.001")


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
    ]
    assert len(set(ids)) == len(ids)


def test_rules_are_exported_from_sim():
    assert sim.TradeRules is TradeRules
    assert sim.DESIGN_V0 is DESIGN_V0
    assert sim.V0_BOOK is V0_BOOK
    assert sim.PRESETS is PRESETS
    assert sim.MONTHLY_HOLD is MONTHLY_HOLD
    assert sim.SWING_T20_OPEN is SWING_T20_OPEN


def test_rules_are_frozen_and_hashable():
    with pytest.raises(FrozenInstanceError):
        MONTHLY_HOLD.cadence = "daily"  # type: ignore[misc]
    assert len({*PRESETS}) == len(PRESETS)


# ============================================================== validation


def test_bracket_v0_is_reserved_for_design_v0_both_ways():
    with pytest.raises(ValueError, match="reserved for DESIGN_V0"):
        replace(DESIGN_V0, time_stop=10)
    with pytest.raises(ValueError, match="reserved for DESIGN_V0"):
        replace(DESIGN_V0, id="other")
    with pytest.raises(ValueError, match="reserved for DESIGN_V0"):
        replace(V0_BOOK, id="design-v0")
    with pytest.raises(ValueError, match="reserved for DESIGN_V0"):
        TradeRules(id="x", engine="bracket_v0")
    # An equal-valued re-construction is DESIGN_V0 itself.
    assert replace(DESIGN_V0) == DESIGN_V0


@pytest.mark.parametrize("bad", ["", "Monthly", "monthly_hold", "-x", "x-", "a--b", "a b"])
def test_id_must_be_kebab_case(bad):
    with pytest.raises(ValueError, match="kebab-case"):
        TradeRules(id=bad, engine="book")


def test_id_must_be_a_str():
    with pytest.raises(TypeError):
        TradeRules(id=1, engine="book")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field,value",
    [("engine", "bracket"), ("cadence", "yearly"), ("entry", "market")],
)
def test_unknown_literal_values(field, value):
    kwargs = {"id": "x", "engine": "book", field: value}
    with pytest.raises(ValueError, match=f"unknown {field}"):
        TradeRules(**kwargs)


@pytest.mark.parametrize("field", ["max_positions", "time_stop"])
def test_counts(field):
    assert getattr(TradeRules(id="x", engine="book", **{field: 1}), field) == 1
    assert getattr(TradeRules(id="x", engine="book", **{field: None}), field) is None
    with pytest.raises(ValueError, match=">= 1"):
        TradeRules(id="x", engine="book", **{field: 0})
    with pytest.raises(TypeError):
        TradeRules(id="x", engine="book", **{field: True})
    with pytest.raises(TypeError):
        TradeRules(id="x", engine="book", **{field: 2.0})


@pytest.mark.parametrize("field", ["resize", "fractional", "dividends"])
def test_flags_are_bools(field):
    with pytest.raises(TypeError, match=field):
        TradeRules(id="x", engine="book", **{field: 1})


def test_idle_symbol():
    assert TradeRules(id="x", engine="book", idle_symbol="BIL").idle_symbol == "BIL"
    with pytest.raises(ValueError):
        TradeRules(id="x", engine="book", idle_symbol="")
    with pytest.raises(TypeError):
        TradeRules(id="x", engine="book", idle_symbol=5)  # type: ignore[arg-type]


def test_cost_rate():
    assert TradeRules(id="x", engine="book", cost_rate=Decimal(0)).cost_rate == 0
    assert TradeRules(id="x", engine="book", cost_rate=Decimal("0.0499")).cost_rate == Decimal("0.0499")
    with pytest.raises(TypeError):
        TradeRules(id="x", engine="book", cost_rate=0.001)  # type: ignore[arg-type]
    for bad in (Decimal("0.05"), Decimal("-0.001"), Decimal("NaN")):
        with pytest.raises(ValueError, match="cost_rate"):
            TradeRules(id="x", engine="book", cost_rate=bad)


# ============================================================== cadence


def test_daily_cadence_decides_every_session():
    for d in ("2026-10-05", "2026-10-06", "2026-11-27"):
        assert is_decision_session(DAILY_SWITCH, D(d)) is True
    assert is_decision_session(DESIGN_V0, D("2026-10-07")) is True


def test_weekly_cadence_is_the_first_session_of_each_iso_week():
    assert is_decision_session(WEEKLY_HOLD, D("2026-10-05")) is True  # Monday
    assert is_decision_session(WEEKLY_HOLD, D("2026-10-06")) is False
    assert is_decision_session(WEEKLY_HOLD, D("2026-10-09")) is False  # Friday
    # MLK day 2026-01-19 is a holiday: Tuesday opens the week.
    assert is_decision_session(WEEKLY_HOLD, D("2026-01-20")) is True
    assert is_decision_session(WEEKLY_HOLD, D("2026-01-21")) is False
    # ISO week 53 of 2026 runs into 2027: Monday 2026-12-28 opens it, 2027-01-04 the next.
    assert is_decision_session(WEEKLY_HOLD, D("2026-12-28")) is True
    assert is_decision_session(WEEKLY_HOLD, D("2026-12-31")) is False
    assert is_decision_session(WEEKLY_HOLD, D("2027-01-04")) is True


def test_monthly_cadence_is_the_first_session_of_each_month():
    assert is_decision_session(MONTHLY_HOLD, D("2026-10-01")) is True  # Thursday
    assert is_decision_session(MONTHLY_HOLD, D("2026-10-02")) is False
    assert is_decision_session(MONTHLY_HOLD, D("2026-11-02")) is True  # Monday after Oct 30
    assert is_decision_session(MONTHLY_HOLD, D("2026-01-02")) is True  # Jan 1 is a holiday
    assert is_decision_session(MONTHLY_HOLD, D("2026-10-30")) is False


def test_decision_session_rejects_non_sessions_and_bad_types():
    with pytest.raises(ValueError, match="not an NYSE session"):
        is_decision_session(MONTHLY_HOLD, D("2026-10-04"))  # Sunday
    with pytest.raises(ValueError, match="not an NYSE session"):
        is_decision_session(DAILY_SWITCH, D("2026-11-26"))  # Thanksgiving
    with pytest.raises(TypeError):
        is_decision_session(MONTHLY_HOLD, datetime(2026, 10, 1))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        is_decision_session("monthly-hold", D("2026-10-01"))  # type: ignore[arg-type]


# ============================================================== owner inputs


def test_owner_inputs_of_the_presets():
    for r in PRESETS:
        expected = ("etf:BIL",) if r.idle_symbol == "BIL" else ()
        assert rule_owner_inputs(r) == expected, r.id
    assert rule_owner_inputs(V0_BOOK) == ()


def test_owner_inputs_every_lever_sorted():
    r = TradeRules(
        id="x", engine="book", entry="open", fractional=True, idle_symbol="IEF", cost_rate=Decimal("0.0005")
    )
    assert rule_owner_inputs(r) == ("etf:IEF", "fee", "fractional", "market-on-open")
    assert rule_owner_inputs(replace(r, idle_symbol="SPY")) == ("fee", "fractional", "market-on-open")
    assert rule_owner_inputs(replace(r, cost_rate=Decimal("0.0010"))) == ("etf:IEF", "fractional", "market-on-open")
    assert rule_owner_inputs(replace(MONTHLY_HOLD, entry="open_limit")) == ()


# ============================================================== description


def test_describe_design_v0_golden():
    assert describe_rules(DESIGN_V0) == (
        "Rule set: design-v0.",
        "Engine: the design §5 bracket simulator, unchanged.",
        "Decisions: every session, from the previous session's close.",
        "Entry: a buy limit at the strategy's limit price for the next session; it fills only when "
        "the low trades below the limit, at the lower of the open and the limit.",
        "Positions: at most 4 at a time (the idle instrument not counted).",
        "Time stop: sell at the next open once a position has been held 5 sessions.",
        "Rebalance: none; a held position keeps its shares until it exits.",
        "Shares: whole shares only.",
        "Dividends: not credited.",
        "Idle cash: held as cash, earning nothing.",
        "Costs: 0.1% per side.",
    )


def test_describe_monthly_hold_tbill_golden():
    assert describe_rules(MONTHLY_HOLD_TBILL) == (
        "Rule set: monthly-hold-tbill.",
        "Engine: the target-weight book; a position the strategy stops wanting is sold at the next "
        "open, and stops and take-profits are fixed at entry.",
        "Decisions: the first session of each calendar month, from the previous session's close.",
        "Entry: a buy limit at the last close + 2% for the next session; it fills only when the low "
        "trades below the limit, at the lower of the open and the limit.",
        "Positions: as many as the strategy targets.",
        "Time stop: none.",
        "Rebalance: on decision sessions, a held position is traded back to its target weight at "
        "the open when it is off by at least 1% of equity.",
        "Shares: whole shares only.",
        "Dividends: cash dividends are credited on the ex-date.",
        "Idle cash: the unallocated weight is held in BIL on decision sessions.",
        "Costs: 0.1% per side.",
    )


def test_describe_other_levers():
    r = TradeRules(
        id="x", engine="book", cadence="weekly", entry="open", fractional=True, cost_rate=Decimal("0.0015")
    )
    lines = describe_rules(r)
    assert len(lines) == 11
    assert lines[2] == "Decisions: the first session of each ISO week, from the previous session's close."
    assert lines[3] == "Entry: a market order at the next open (needs owner verification: market-on-open)."
    assert lines[7] == "Shares: fractional, rounded down to 0.0001 share (needs owner verification)."
    assert lines[10] == "Costs: 0.15% per side."
    assert describe_rules(replace(r, cost_rate=Decimal(0)))[10] == "Costs: 0% per side."
    assert describe_rules(SWING_T20)[5] == "Time stop: sell at the next open once a position has been held 20 sessions."
    assert describe_rules(SWING_T20)[3] == (
        "Entry: a buy limit at the strategy's limit price for the next session; it fills only when "
        "the low trades below the limit, at the lower of the open and the limit. A new position the "
        "strategy gives no limit price is bought at a limit of the last close + 2% instead, filled "
        "the same way."
    )
    assert all(len(describe_rules(p)) == 11 for p in PRESETS)
    assert describe_rules(DAILY_SWITCH) == describe_rules(DAILY_SWITCH)
```
**Impact:** test-only.

### Step 5: `tests/test_sim_book.py`
**File:** `engine/tests/test_sim_book.py:1` (new)
**Change:** 56 tests. Lever coverage (plan-index list -> tests):
- signal exit at the next open, missing bar / `exit_pending`: `test_signal_exit_sells_a_dropped_position_at_the_next_open`,
  `test_no_decision_means_no_signal_exit`, `test_a_kept_target_is_not_sold`,
  `test_signal_exit_without_a_bar_waits_for_the_next_bar`, `test_no_reentry_on_the_session_of_an_exit_at_the_open`;
- rebalance with trims and adds under `RESIZE_BAND`: `test_rebalance_trims_and_adds_at_the_open`,
  `test_rebalance_inside_the_band_does_nothing`, `test_without_resize_held_targets_keep_their_shares`,
  `test_a_trim_to_zero_closes_the_episode`;
- dividends on the ex-date: five tests (`test_dividends_*`, `test_a_position_*_ex_date`, `test_dividend_amounts_are_decimals`);
- fractional shares: `test_fractional_shares_round_down_to_the_share_quantum`, `test_whole_shares_by_default`;
- `open` and `open_limit` entries incl. a gap above the band: `test_open_limit_entry_fills_below_the_band`,
  `test_open_limit_entry_gapping_above_the_band_goes_unfilled`, `test_open_entry_fills_at_the_open_whatever_the_gap`,
  `test_limit_entry_uses_the_target_limit_and_brackets`, `test_limit_entry_without_a_limit_buys_like_open_limit`
  (plan index D-B: the fallback, and held limit-less targets never bought);
- `max_positions` ≠ 4: `test_max_positions_two`, `test_an_exit_by_rule_at_the_open_does_not_free_a_slot`,
  `test_a_signal_exit_frees_its_slot_and_funds_the_entry`, `test_max_positions_lets_ranked_targets_weigh_more_than_one`;
- time stop 10/20/None: `test_time_stop_sells_at_the_open_once_held_long_enough[10,20]`, `test_no_time_stop_holds_indefinitely`;
- vol-scaled weights: `test_unequal_weights_are_sized_by_their_own_weight`;
- idle T-bill: five tests (`test_idle_*` and `test_targeting_the_idle_instrument_needs_the_caller_flag`);
- cash guard: `test_cash_guard_shrinks_a_buy_cash_cannot_cover`, `test_cash_guard_rejects_when_nothing_fits`;
- `close_book_unpriced`: two tests;
- episode P&L reconciling with cash exactly: `test_episode_pnl_reconciles_with_cash_exactly`;
- §5 replay: `test_v0_book_replays_size_picks_and_step[1,2,3]` — 4 months of seeded bars on a
  0.25 price grid (so `low == limit`, `low == stop`, `open == take` ties occur), 6 symbols
  including one too expensive for a slot, 5% missing bars; asserts equal (cash, equity) every
  session, equal held sets, and equal closed-trade multisets
  `(symbol, fill date, fill price, exit date, exit price, reason, days_held, pnl)` with all four
  §5 exit reasons present. Verified while planning: it kills the mutants `low <= limit`,
  `low < stop`, `open > take`, `high >= take`, fill-at-limit, and "time stops free a slot".

Uses `random.Random(seed)` in the test only (tests are outside the purity globs).
**Code:**
```python
"""The book engine (P7a phase 1): one synthetic-bar test (or more) per lever, plus a
session-by-session replay of §5 (``size_picks`` + ``step``) under ``V0_BOOK``.

Real NYSE dates: 2026-10-05 is a Monday. Every hand-checked number is in the comments.
No database needed.
"""

from __future__ import annotations

import random
from dataclasses import FrozenInstanceError, replace
from datetime import date
from decimal import Decimal

import pytest

from seer_engine import dates, sim
from seer_engine.prices import Bar
from seer_engine.sim import (
    DAILY_SWITCH,
    DAILY_SWITCH_TBILL,
    DESIGN_V0,
    SWING_T10,
    SWING_T20,
    V0_BOOK,
    Book,
    BookStep,
    Pick,
    Position,
    Target,
    TradeRules,
    close_book_unpriced,
    equal_weight,
    new_book,
    new_portfolio,
    size_picks,
    step,
    step_book,
    to_weight,
)
from seer_engine.sim.book import WEIGHT_QUANTUM
from simkit import D, P, bar, day

MON = "2026-10-05"
TUE = "2026-10-06"
WED = "2026-10-07"
THU = "2026-10-08"
FRI = "2026-10-09"

W = Decimal

RESIZE = TradeRules(id="resize", engine="book", entry="open_limit", resize=True)
OPEN = TradeRules(id="open", engine="book", entry="open")
FRACTIONAL = TradeRules(id="fractional", engine="book", entry="open_limit", fractional=True)


def T(symbol: str, weight: str, last: str, limit: str | None = None, stop: str | None = None, take: str | None = None) -> Target:
    return Target(
        symbol=symbol,
        weight=W(weight),
        last=P(last),
        limit=None if limit is None else P(limit),
        stop=None if stop is None else P(stop),
        take=None if take is None else P(take),
    )


def pos(
    symbol: str,
    shares: int | str,
    mark: str,
    *,
    entry_date: str = "2026-10-01",
    entry_price: str | None = None,
    days_held: int = 3,
    cost: str | None = None,
    income: str = "0",
    stop: str | None = None,
    take: str | None = None,
    exit_pending: bool = False,
) -> Position:
    """A held position; ``cost`` defaults to q(entry × shares × 1.001)."""
    n = W(shares)
    entry = P(mark if entry_price is None else entry_price)
    return Position(
        symbol=symbol,
        shares=n,
        mark=P(mark),
        entry_date=D(entry_date),
        entry_price=entry,
        days_held=days_held,
        cost_usd=sim.q(entry * n * W("1.001")) if cost is None else P(cost),
        income_usd=P(income),
        stop=None if stop is None else P(stop),
        take=None if take is None else P(take),
        exit_pending=exit_pending,
    )


def book(cash: str, *positions: Position, last: str = MON) -> Book:
    ps = tuple(sorted(positions, key=lambda p: p.symbol))
    equity = sim.q(P(cash) + sum((p.shares * p.mark for p in ps), W(0)))
    return Book(cash=P(cash), equity=equity, positions=ps, last_session=D(last))


def go(b: Book, session: str, bars: dict[str, Bar], targets, rules: TradeRules, **kw) -> BookStep:
    return step_book(b, D(session), bars, targets, rules, **kw)


# ============================================================== weights and values


def test_to_weight_quantizes_down():
    assert to_weight(W("0.3333339")) == W("0.333333")
    assert to_weight(0.1) == W("0.100000")  # float via repr, not its binary expansion
    assert to_weight(1) == W("1")
    assert to_weight(W("0.0000019")) == WEIGHT_QUANTUM
    for bad in (W("0.0000009"), W(0), W("-0.5"), float("nan"), W("Infinity")):
        with pytest.raises(ValueError):
            to_weight(bad)
    for bad in (True, "0.5", None):
        with pytest.raises(TypeError):
            to_weight(bad)  # type: ignore[arg-type]


def test_equal_weight():
    assert equal_weight(1) == W(1)
    assert equal_weight(3) == W("0.333333")
    assert equal_weight(4) == W("0.25")
    assert equal_weight(8) == W("0.125")
    with pytest.raises(ValueError):
        equal_weight(0)
    with pytest.raises(TypeError):
        equal_weight(2.0)  # type: ignore[arg-type]


def test_target_validation():
    t = Target("SPY", W("0.5"), W("100.00004"), limit=W("99.5"), stop=W("95"), take=W("110"))
    assert t.last == W("100.0000")
    with pytest.raises(TypeError):
        Target("SPY", W("0.5"), 100.0)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Target("SPY", 0.5, W(100))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Target("SPY", W("0.5"), W(100), limit=99.0)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="multiple"):
        Target("SPY", W("0.1234567"), W(100))
    for bad in (W(0), W("1.000001"), W("-0.1")):
        with pytest.raises(ValueError, match=r"\(0, 1\]"):
            Target("SPY", bad, W(100))
    with pytest.raises(ValueError, match="> 0"):
        Target("SPY", W("0.5"), W("0.00001"))
    with pytest.raises(ValueError, match="below"):
        Target("SPY", W("0.5"), W(100), limit=W(99), stop=W(99))
    with pytest.raises(ValueError, match="above"):
        Target("SPY", W("0.5"), W(100), take=W(100))
    with pytest.raises(ValueError):
        Target("", W("0.5"), W(100))
    with pytest.raises(FrozenInstanceError):
        t.weight = W(1)  # type: ignore[misc]


def test_book_validation_and_accessors():
    b = book("100", pos("BBB", 1, "10"), pos("AAA", 2, "5"))
    assert b.held() == frozenset({"AAA", "BBB"})
    assert b.position("AAA").shares == W(2)
    assert b.position("ZZZ") is None
    with pytest.raises(ValueError, match="sorted"):
        Book(cash=W(1), equity=W(1), positions=(pos("BBB", 1, "10"), pos("AAA", 1, "10")))
    with pytest.raises(TypeError):
        Book(cash=1.0, equity=W(1))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        pos("AAA", 0, "10")
    with pytest.raises(TypeError):
        Position("AAA", 1, W(1), D(MON), W(1), 1, W(1), W(0), None, None)  # type: ignore[arg-type]


def test_new_book():
    b = new_book(W("1234.56789"))
    assert (b.cash, b.equity, b.positions, b.last_session) == (W("1234.5679"), W("1234.5679"), (), None)
    with pytest.raises(ValueError):
        new_book(W(0))
    with pytest.raises(TypeError):
        new_book(1000.0)  # type: ignore[arg-type]


def test_book_values_are_exported_from_sim():
    assert sim.step_book is step_book
    assert sim.Target is Target
    assert sim.to_weight is to_weight
    assert sim.close_book_unpriced is close_book_unpriced
    for name in ("Book", "Position", "Fill", "Trade", "BookSnapshot", "BookStep", "new_book", "equal_weight"):
        assert hasattr(sim, name), name


# ============================================================== step_book argument checks


def test_step_book_rejects_the_bracket_engine_and_bad_sessions():
    b = new_book(W(1000))
    with pytest.raises(ValueError, match="engine 'book'"):
        go(b, TUE, {}, None, DESIGN_V0)
    with pytest.raises(ValueError, match="not an NYSE session"):
        go(b, "2026-10-04", {}, None, DAILY_SWITCH)
    later = go(b, TUE, {}, None, DAILY_SWITCH).book
    with pytest.raises(ValueError, match="not after"):
        go(later, TUE, {}, None, DAILY_SWITCH)
    with pytest.raises(TypeError):
        go(b, TUE, {}, [T("SPY", "1", "100")], DAILY_SWITCH)  # a list, not a tuple


def test_step_book_rejects_bad_targets():
    b = new_book(W(1000))
    with pytest.raises(ValueError, match="twice"):
        go(b, TUE, {}, (T("SPY", "0.5", "100"), T("SPY", "0.5", "100")), DAILY_SWITCH)
    with pytest.raises(ValueError, match="sum to"):
        go(b, TUE, {}, (T("SPY", "0.6", "100"), T("QQQ", "0.5", "100")), DAILY_SWITCH)
    with pytest.raises(TypeError):
        go(b, TUE, {}, ("SPY",), DAILY_SWITCH)


def test_step_book_rejects_float_prices_in_bars():
    b = new_book(W(1000))
    bad = Bar("SPY", D(TUE), 100.0, W(101), W(99), W(100), 1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        go(b, TUE, {"SPY": bad}, (T("SPY", "0.5", "100"),), DAILY_SWITCH)


def test_max_positions_lets_ranked_targets_weigh_more_than_one():
    # §5 ranks more picks than slots on purpose; with max_positions set the extra ones are no_slot.
    r = replace(DAILY_SWITCH, id="capped", max_positions=2)
    out = go(new_book(W(1000)), TUE, {}, (T("A", "0.5", "10"), T("B", "0.5", "10"), T("C", "0.5", "10")), r)
    assert out.rejected == (("A", "no_bar"), ("B", "no_bar"), ("C", "no_slot"))


# ============================================================== signal exits


def test_signal_exit_sells_a_dropped_position_at_the_next_open():
    b = book("1000", pos("AAA", 10, "100", cost="1001"))
    out = go(b, TUE, day(bar("AAA", TUE, "105", "106", "104", "105.5")), (), DAILY_SWITCH)
    # q(105 × 10 × 0.999) = 1048.95; fee q(105 × 10 × 0.001) = 1.05
    (f,) = out.fills
    assert (f.side, f.shares, f.price, f.cash_usd, f.cost_usd, f.reason) == ("sell", W(10), P("105"), P("1048.95"), P("1.05"), "signal")
    (t,) = out.trades
    assert (t.exit_reason, t.days_held, t.exit_price, t.pnl_usd, t.idle) == ("signal", 3, P("105"), P("47.95"), False)
    assert out.book.positions == ()
    assert (out.snapshot.cash_usd, out.snapshot.equity_usd, out.snapshot.invested_usd) == (P("2048.95"), P("2048.95"), P(0))


def test_no_decision_means_no_signal_exit():
    b = book("1000", pos("AAA", 10, "100"))
    out = go(b, TUE, day(bar("AAA", TUE, "105", "106", "104", "105.5")), None, DAILY_SWITCH)
    assert out.fills == () and out.trades == ()
    p = out.book.position("AAA")
    assert (p.days_held, p.mark) == (4, P("105.5"))
    assert out.snapshot.equity_usd == P("2055")


def test_a_kept_target_is_not_sold():
    b = book("1000", pos("AAA", 10, "100"))
    out = go(b, TUE, day(bar("AAA", TUE, "105", "106", "104", "105.5")), (T("AAA", "0.5", "100"),), DAILY_SWITCH)
    assert out.fills == () and out.book.position("AAA").shares == W(10)


def test_signal_exit_without_a_bar_waits_for_the_next_bar():
    b = book("1000", pos("AAA", 10, "100", cost="1001"))
    out = go(b, TUE, {}, (), DAILY_SWITCH)
    p = out.book.position("AAA")
    assert (p.exit_pending, p.days_held, p.mark) == (True, 4, P("100"))
    assert out.fills == ()
    # WED is not a decision session (targets None), yet the pending exit is sold at its open.
    out2 = go(out.book, WED, day(bar("AAA", WED, "99", "101", "98", "100")), None, DAILY_SWITCH)
    (t,) = out2.trades
    # q(99 × 10 × 0.999) = 989.01; pnl = 989.01 − 1001 = −11.99; days_held stays 4 at the open
    assert (t.exit_reason, t.exit_price, t.days_held, t.pnl_usd) == ("signal", P("99"), 4, P("-11.99"))
    assert out2.book.positions == ()
    assert out2.snapshot.cash_usd == P("1989.01")


def test_no_reentry_on_the_session_of_an_exit_at_the_open():
    b = book("0", pos("AAA", 10, "100", days_held=10))
    bars = day(bar("AAA", TUE, "100", "101", "99", "100"))
    out = go(b, TUE, bars, (T("AAA", "1", "100"),), replace(SWING_T10, entry="open_limit", id="t10-open"))
    assert [f.reason for f in out.fills] == ["time"]
    assert out.book.positions == ()
    assert out.rejected == ()


# ============================================================== rebalance (trims and adds)


def _two_held() -> Book:
    return book("0", pos("AAA", 60, "100"), pos("BBB", 40, "100"))  # equity 10,000


def test_rebalance_trims_and_adds_at_the_open():
    b = _two_held()
    bars = day(
        bar("AAA", TUE, "101", "102", "100", "101"),
        bar("BBB", TUE, "99", "100", "98.5", "99.5"),
    )
    out = go(b, TUE, bars, (T("AAA", "0.5", "100"), T("BBB", "0.5", "100")), RESIZE)
    # desired = floor(q(10000 × 0.5) / (100 × 1.001)) = 49 for both.
    # AAA: excess 11 × 100 = 1100 >= 1% × 10000 -> trim 11 at the open 101: q(1111 × 0.999) = 1109.889.
    # BBB: gap 9 × 100 = 900 >= 100 -> add; limit q(100 × 1.02) = 102, cash at night = 0 + planned
    #      trim q(100 × 11 × 0.999) = 1098.9 -> min(9, floor(1098.9 / 102.102) = 10) = 9;
    #      fill at min(99, 102) = 99: q(99 × 9 × 1.001) = 891.891.
    assert [(f.symbol, f.side, f.shares, f.price, f.cash_usd, f.reason) for f in out.fills] == [
        ("AAA", "sell", W(11), P("101"), P("1109.889"), "trim"),
        ("BBB", "buy", W(9), P("99"), P("-891.891"), "add"),
    ]
    assert out.trades == ()
    a, bb = out.book.position("AAA"), out.book.position("BBB")
    assert (a.shares, a.income_usd, a.days_held, a.mark) == (W(49), P("1109.889"), 4, P("101"))
    assert (bb.shares, bb.cost_usd, bb.days_held, bb.entry_price) == (W(49), b.position("BBB").cost_usd + P("891.891"), 4, P("100"))
    # cash 217.998; equity = 217.998 + 49 × 101 + 49 × 99.5
    assert out.snapshot.cash_usd == P("217.998")
    assert out.snapshot.equity_usd == P("10042.498")


def test_rebalance_inside_the_band_does_nothing():
    # equity 10,000: desired = floor(5000 / 99.099) = 50; AAA is 1 share × 99 = 99 < 100 over.
    b = book("100", pos("AAA", 51, "99"), pos("BBB", 49, "99"))
    bars = day(bar("AAA", TUE, "99", "99", "99", "99"), bar("BBB", TUE, "99", "99", "98", "99"))
    out = go(b, TUE, bars, (T("AAA", "0.5", "99"), T("BBB", "0.5", "99")), RESIZE)
    assert out.fills == () and out.rejected == ()


def test_without_resize_held_targets_keep_their_shares():
    b = _two_held()
    bars = day(bar("AAA", TUE, "101", "102", "100", "101"), bar("BBB", TUE, "99", "100", "98.5", "99.5"))
    out = go(b, TUE, bars, (T("AAA", "0.5", "100"), T("BBB", "0.5", "100")), DAILY_SWITCH)
    assert out.fills == ()
    assert [p.shares for p in out.book.positions] == [W(60), W(40)]


def test_a_trim_to_zero_closes_the_episode():
    b = book("0", pos("AAA", 1, "100"), pos("BBB", 99, "100"))  # equity 10,000
    bars = day(bar("AAA", TUE, "100", "100", "100", "100"), bar("BBB", TUE, "100", "100", "100", "100"))
    # AAA weight 0.000001 -> q(0.01) buys 0 shares at 100.1 -> desired 0; excess 1 × 100 >= 100.
    out = go(b, TUE, bars, (T("AAA", "0.000001", "100"), T("BBB", "0.9", "100")), RESIZE)
    assert [(f.symbol, f.reason) for f in out.fills][0] == ("AAA", "trim")
    (t,) = out.trades
    assert (t.symbol, t.exit_reason) == ("AAA", "signal")
    assert out.book.position("AAA") is None


# ============================================================== dividends


def test_dividends_are_credited_on_the_ex_date():
    b = book("500", pos("AAA", 10, "50"))
    out = go(b, TUE, day(bar("AAA", TUE, "50", "51", "49", "50")), None, DAILY_SWITCH, dividends={"AAA": W("0.4567"), "ZZZ": W(1)})
    # q(10 × 0.4567) = 4.567 (ZZZ is not held)
    assert out.dividends == (("AAA", P("4.567")),)
    assert out.snapshot.cash_usd == P("504.567")
    assert out.book.position("AAA").income_usd == P("4.567")
    assert out.snapshot.equity_usd == P("1004.567")


def test_dividends_off_credits_nothing():
    b = book("500", pos("AAA", 10, "50"))
    r = replace(DAILY_SWITCH, id="no-divs", dividends=False)
    out = go(b, TUE, day(bar("AAA", TUE, "50", "51", "49", "50")), None, r, dividends={"AAA": W("0.4567")})
    assert out.dividends == () and out.snapshot.cash_usd == P("500")


def test_a_position_sold_on_the_ex_date_still_gets_the_dividend():
    b = book("500", pos("AAA", 10, "50", cost="500.5"))
    out = go(b, TUE, day(bar("AAA", TUE, "51", "52", "50", "51")), (), DAILY_SWITCH, dividends={"AAA": W("0.4567")})
    (t,) = out.trades
    # income = 4.567 + q(510 × 0.999) = 4.567 + 509.49; pnl = 514.057 − 500.5
    assert (t.income_usd, t.pnl_usd) == (P("514.057"), P("13.557"))
    assert out.snapshot.cash_usd == P("1014.057")


def test_a_position_bought_on_the_ex_date_gets_no_dividend():
    out = go(new_book(W(1000)), TUE, day(bar("AAA", TUE, "50", "51", "49", "50")), (T("AAA", "0.5", "50"),), DAILY_SWITCH, dividends={"AAA": W(1)})
    assert out.dividends == ()
    assert out.book.position("AAA").income_usd == 0


def test_dividend_amounts_are_decimals():
    b = book("500", pos("AAA", 10, "50"))
    with pytest.raises(TypeError):
        go(b, TUE, {}, None, DAILY_SWITCH, dividends={"AAA": 0.5})
    with pytest.raises(ValueError):
        go(b, TUE, {}, None, DAILY_SWITCH, dividends={"AAA": W(0)})


# ============================================================== fractional shares


def test_fractional_shares_round_down_to_the_share_quantum():
    bars = day(bar("XYZ", TUE, "301", "305", "299", "304"))
    out = go(new_book(W(1000)), TUE, bars, (T("XYZ", "1", "300"),), FRACTIONAL)
    # limit q(300 × 1.02) = 306; 1000 / (306 × 1.001) = 3.26470... -> 3.2647
    (f,) = out.fills
    assert (f.shares, f.price) == (W("3.2647"), P("301"))
    # q(301 × 3.2647 × 1.001) = q(983.6573747) = 983.6574
    assert f.cash_usd == P("-983.6574")
    assert out.snapshot.cash_usd == P("16.3426")
    assert out.snapshot.equity_usd == sim.q(P("16.3426") + W("3.2647") * P("304"))


def test_whole_shares_by_default():
    bars = day(bar("XYZ", TUE, "301", "305", "299", "304"))
    out = go(new_book(W(1000)), TUE, bars, (T("XYZ", "1", "300"),), DAILY_SWITCH)
    (f,) = out.fills
    assert f.shares == W(3)
    assert f.cash_usd == P("-903.903")  # q(301 × 3 × 1.001)
    assert out.book.position("XYZ").shares == W(3)


# ============================================================== entry types


def test_open_limit_entry_fills_below_the_band():
    bars = day(bar("SPY", TUE, "101", "103", "100.5", "102"))
    out = go(new_book(W(10000)), TUE, bars, (T("SPY", "0.5", "100"),), DAILY_SWITCH)
    # limit q(100 × 1.02) = 102; floor(5000 / 102.102) = 48; fill at min(101, 102) = 101
    (f,) = out.fills
    assert (f.shares, f.price, f.cash_usd, f.reason) == (W(48), P("101"), P("-4852.848"), "entry")
    p = out.book.position("SPY")
    assert (p.days_held, p.entry_date, p.entry_price, p.mark, p.cost_usd) == (1, D(TUE), P("101"), P("102"), P("4852.848"))


def test_open_limit_entry_gapping_above_the_band_goes_unfilled():
    bars = day(bar("SPY", TUE, "103", "104", "102.5", "103.5"))
    out = go(new_book(W(10000)), TUE, bars, (T("SPY", "0.5", "100"),), DAILY_SWITCH)
    assert out.fills == () and out.rejected == (("SPY", "unfilled"),)
    # the low must trade strictly below the limit
    bars = day(bar("SPY", TUE, "103", "104", "102", "103.5"))
    assert go(new_book(W(10000)), TUE, bars, (T("SPY", "0.5", "100"),), DAILY_SWITCH).rejected == (("SPY", "unfilled"),)
    # a gap above the band that trades back through it fills at the limit
    bars = day(bar("SPY", TUE, "103", "104", "101.9999", "103.5"))
    (f,) = go(new_book(W(10000)), TUE, bars, (T("SPY", "0.5", "100"),), DAILY_SWITCH).fills
    assert f.price == P("102")


def test_open_entry_fills_at_the_open_whatever_the_gap():
    bars = day(bar("SPY", TUE, "103", "104", "102.5", "103.5"))
    out = go(new_book(W(10000)), TUE, bars, (T("SPY", "0.5", "100"),), OPEN)
    # sized at q(100 × 1.02) = 102 -> 48 shares; filled at the open 103: q(103 × 48 × 1.001) = 4948.944
    (f,) = out.fills
    assert (f.shares, f.price, f.cash_usd) == (W(48), P("103"), P("-4948.944"))


def test_limit_entry_uses_the_target_limit_and_brackets():
    bars = day(bar("AAA", TUE, "100", "101", "98.9", "100.5"))
    out = go(new_book(W(10000)), TUE, bars, (T("AAA", "0.25", "100", limit="99", stop="95", take="104"),), SWING_T20)
    # floor(2500 / (99 × 1.001)) = 25; fill at min(100, 99) = 99
    (f,) = out.fills
    assert (f.shares, f.price) == (W(25), P("99"))
    p = out.book.position("AAA")
    assert (p.stop, p.take) == (P("95"), P("104"))


def test_limit_entry_without_a_limit_buys_like_open_limit():
    # SWING_T20 (entry "limit"): an unheld target with no limit price is bought at q(last × 1.02).
    bars = day(bar("SPY", TUE, "101", "103", "100.5", "102"))
    out = go(new_book(W(10000)), TUE, bars, (T("SPY", "0.5", "100"),), SWING_T20)
    # limit q(100 × 1.02) = 102; floor(5000 / 102.102) = 48; fill at min(101, 102) = 101
    (f,) = out.fills
    assert (f.shares, f.price, f.reason) == (W(48), P("101"), "entry")
    assert out.book.position("SPY").stop is None and out.book.position("SPY").take is None
    # gapping above the band: unfilled, exactly as open_limit
    gap = day(bar("SPY", TUE, "103", "104", "102.5", "103.5"))
    assert go(new_book(W(10000)), TUE, gap, (T("SPY", "0.5", "100"),), SWING_T20).rejected == (("SPY", "unfilled"),)
    # a HELD target without a limit price is kept and never added to
    held = book("10000", pos("SPY", 10, "100"))
    kept = go(held, TUE, bars, (T("SPY", "1", "100"),), SWING_T20)
    assert kept.fills == () and kept.book.position("SPY").shares == W(10)


def test_a_new_position_is_not_stopped_on_its_fill_session():
    bars = day(bar("AAA", TUE, "100", "110", "90", "100"))  # through both stop and take
    out = go(new_book(W(10000)), TUE, bars, (T("AAA", "0.25", "100", limit="99", stop="95", take="104"),), SWING_T20)
    assert out.trades == () and out.book.position("AAA") is not None


def test_no_bar_on_the_session_rejects_the_entry():
    out = go(new_book(W(10000)), TUE, {}, (T("AAA", "0.25", "100"),), DAILY_SWITCH)
    assert out.rejected == (("AAA", "no_bar"),)


def test_too_small_rejects_and_ranks_on():
    bars = day(bar("BIG", TUE, "3000", "3000", "2990", "3000"), bar("SMALL", TUE, "10", "10", "9.9", "10"))
    out = go(new_book(W(1000)), TUE, bars, (T("BIG", "0.5", "3000"), T("SMALL", "0.5", "10")), DAILY_SWITCH)
    assert out.rejected == (("BIG", "too_small"),)
    assert [f.symbol for f in out.fills] == ["SMALL"]


# ============================================================== max_positions


def test_max_positions_two():
    r = replace(DAILY_SWITCH, id="two", max_positions=2)
    bars = day(*(bar(s, TUE, "10", "10", "9.9", "10") for s in ("A", "B", "C")))
    out = go(new_book(W(10000)), TUE, bars, (T("A", "0.25", "10"), T("B", "0.25", "10"), T("C", "0.25", "10")), r)
    assert [f.symbol for f in out.fills] == ["A", "B"]
    assert out.rejected == (("C", "no_slot"),)


def test_an_exit_by_rule_at_the_open_does_not_free_a_slot():
    r = TradeRules(id="one", engine="book", entry="open_limit", max_positions=1, time_stop=2)
    b = book("1000", pos("A", 10, "10", days_held=2))
    bars = day(bar("A", TUE, "10", "10", "9.9", "10"), bar("B", TUE, "10", "10", "9.9", "10"))
    out = go(b, TUE, bars, (T("A", "0.5", "10"), T("B", "0.5", "10")), r)
    assert [(f.symbol, f.reason) for f in out.fills] == [("A", "time")]
    assert out.rejected == (("B", "no_slot"),)


def test_a_signal_exit_frees_its_slot_and_funds_the_entry():
    r = TradeRules(id="one", engine="book", entry="open_limit", max_positions=1)
    b = book("0", pos("A", 100, "10"))
    bars = day(bar("A", TUE, "10", "10", "9.9", "10"), bar("B", TUE, "10.1", "10.2", "10", "10.1"))
    out = go(b, TUE, bars, (T("B", "1", "10"),), r)
    # night: planned q(10 × 100 × 0.999) = 999; budget min(1000, 999) at 10.2 -> floor(999 / 10.2102) = 97
    assert [(f.symbol, f.side, f.shares, f.reason) for f in out.fills] == [
        ("A", "sell", W(100), "signal"),
        ("B", "buy", W(97), "entry"),
    ]
    # 999 − q(10.1 × 97 × 1.001) = 999 − 980.6797
    assert out.snapshot.cash_usd == P("18.3203")


# ============================================================== time stop


@pytest.mark.parametrize("rules,limit", [(SWING_T10, 10), (SWING_T20, 20)])
def test_time_stop_sells_at_the_open_once_held_long_enough(rules, limit):
    b = book("0", pos("AAA", 10, "100", days_held=limit - 1))
    out = go(b, TUE, day(bar("AAA", TUE, "100", "101", "99", "100")), None, rules)
    assert out.fills == () and out.book.position("AAA").days_held == limit
    out2 = go(out.book, WED, day(bar("AAA", WED, "102", "103", "101", "102")), None, rules)
    (t,) = out2.trades
    assert (t.exit_reason, t.days_held, t.exit_price) == ("time", limit, P("102"))


def test_no_time_stop_holds_indefinitely():
    b = book("0", pos("AAA", 10, "100", days_held=500))
    out = go(b, TUE, day(bar("AAA", TUE, "100", "101", "99", "100")), None, DAILY_SWITCH)
    assert out.fills == () and out.book.position("AAA").days_held == 501


# ============================================================== stops and take-profits


def test_gap_and_intraday_exits_follow_sim_semantics():
    held = (pos("GAP", 10, "100", stop="95", take="110"), pos("SL", 10, "100", stop="95"), pos("TP", 10, "100", take="104"))
    b = book("0", *held)
    bars = day(
        bar("GAP", TUE, "94", "96", "93", "95"),  # open <= stop -> at the open, days unchanged
        bar("SL", TUE, "97", "98", "95", "96"),  # low <= stop -> at the stop, days + 1
        bar("TP", TUE, "103", "104.01", "102", "104"),  # high > take -> at the take, days + 1
    )
    out = go(b, TUE, bars, None, DAILY_SWITCH)
    got = {t.symbol: (t.exit_reason, t.exit_price, t.days_held) for t in out.trades}
    assert got == {"GAP": ("gap", P("94"), 3), "SL": ("sl", P("95"), 4), "TP": ("tp", P("104"), 4)}
    # fills: open sells first (symbol order), then the intraday sells (symbol order)
    assert [f.symbol for f in out.fills] == ["GAP", "SL", "TP"]


def test_take_at_the_open_and_high_equal_to_take():
    b = book("0", pos("A", 10, "100", take="104"), pos("B", 10, "100", take="104"))
    bars = day(bar("A", TUE, "104", "105", "103", "104"), bar("B", TUE, "103", "104", "102", "103"))
    out = go(b, TUE, bars, None, DAILY_SWITCH)
    assert [(t.symbol, t.exit_reason, t.exit_price) for t in out.trades] == [("A", "tp", P("104"))]


# ============================================================== vol-scaled (unequal) weights


def test_unequal_weights_are_sized_by_their_own_weight():
    bars = day(
        bar("A", TUE, "50", "51", "49", "50"),
        bar("B", TUE, "20", "20.5", "19.8", "20"),
        bar("C", TUE, "1000", "1000", "999", "1000"),
    )
    out = go(new_book(W(10000)), TUE, bars, (T("A", "0.6", "50"), T("B", "0.3", "20"), T("C", "0.1", "1000")), DAILY_SWITCH)
    # A: floor(6000 / (51 × 1.001)) = 117; B: floor(3000 / (20.4 × 1.001)) = 146; C: 1000 < 1020 × 1.001
    assert [(f.symbol, f.shares) for f in out.fills] == [("A", W(117)), ("B", W(146))]
    assert out.rejected == (("C", "too_small"),)


# ============================================================== the idle instrument


def test_idle_target_takes_the_residual_weight_and_is_not_invested():
    bars = day(bar("SPY", TUE, "100", "101", "99", "101"), bar("BIL", TUE, "50", "50.02", "49.99", "50.01"))
    targets = (T("SPY", "0.6", "100"), T("BIL", "0.4", "50"))
    out = go(new_book(W(10000)), TUE, bars, targets, DAILY_SWITCH_TBILL, idle_symbol_ok=True)
    # SPY floor(6000 / 102.102) = 58 at 100; BIL floor(4000 / 51.051) = 78 at 50
    assert [(f.symbol, f.shares, f.price) for f in out.fills] == [("SPY", W(58), P("100")), ("BIL", W(78), P("50"))]
    # cash 10000 − 5805.8 − 3903.9 = 290.3; invested = 58 × 101 only
    assert out.snapshot.cash_usd == P("290.3")
    assert out.snapshot.invested_usd == P("5858")
    assert out.snapshot.equity_usd == P("10049.08")


def test_idle_target_is_ranked_last_and_needs_no_slot():
    r = replace(DAILY_SWITCH_TBILL, id="tbill-one", max_positions=1)
    bars = day(bar("SPY", TUE, "100", "101", "99", "101"), bar("BIL", TUE, "50", "50.02", "49.99", "50.01"))
    out = go(new_book(W(10000)), TUE, bars, (T("BIL", "0.4", "50"), T("SPY", "0.6", "100")), r, idle_symbol_ok=True)
    assert [f.symbol for f in out.fills] == ["SPY", "BIL"]
    assert out.rejected == ()


def test_targeting_the_idle_instrument_needs_the_caller_flag():
    with pytest.raises(ValueError, match="idle instrument"):
        go(new_book(W(10000)), TUE, {}, (T("BIL", "0.4", "50"),), DAILY_SWITCH_TBILL)


def test_idle_position_is_trimmed_even_without_resize():
    b = book("0", pos("SPY", 50, "100"), pos("BIL", 100, "50"))  # equity 10,000
    bars = day(bar("SPY", TUE, "100", "101", "99", "100"), bar("BIL", TUE, "50", "50", "50", "50"))
    out = go(b, TUE, bars, (T("SPY", "0.8", "100"), T("BIL", "0.2", "50")), DAILY_SWITCH_TBILL, idle_symbol_ok=True)
    # BIL desired floor(2000 / 50.05) = 39 -> trim 61; SPY (resize False) is not added to
    assert [(f.symbol, f.side, f.shares, f.reason) for f in out.fills] == [("BIL", "sell", W(61), "trim")]


def test_idle_episode_is_flagged_idle():
    b = book("0", pos("SPY", 50, "100"), pos("BIL", 100, "50"))
    bars = day(bar("SPY", TUE, "100", "101", "99", "100"), bar("BIL", TUE, "50", "50", "50", "50"))
    out = go(b, TUE, bars, (T("SPY", "1", "100"),), DAILY_SWITCH_TBILL)
    (t,) = out.trades
    assert (t.symbol, t.exit_reason, t.idle) == ("BIL", "signal", True)


# ============================================================== cash guard


def test_cash_guard_shrinks_a_buy_cash_cannot_cover():
    # A planned sell (A, no bar on TUE) does not happen, so B's fill finds only 500 in cash.
    b = book("500", pos("A", 50, "10"))
    bars = day(bar("B", TUE, "10.1", "10.2", "10", "10.1"))
    out = go(b, TUE, bars, (T("B", "1", "10"),), DAILY_SWITCH)
    # sized: min(1000, 500 + 499.5) / 10.2102 -> 97; at fill q(10.1 × 97 × 1.001) = 980.6797 > 500
    # -> floor(500 / (10.1 × 1.001)) = 49: q(495.3949)
    (f,) = out.fills
    assert (f.symbol, f.shares, f.cash_usd) == ("B", W(49), P("-495.3949"))
    assert out.snapshot.cash_usd == P("4.6051")
    assert out.book.position("A").exit_pending is True


def test_cash_guard_rejects_when_nothing_fits():
    b = book("0", pos("A", 100, "10"))
    bars = day(bar("B", TUE, "10.1", "10.2", "10", "10.1"))
    out = go(b, TUE, bars, (T("B", "1", "10"),), DAILY_SWITCH)
    assert out.fills == () and out.rejected == (("B", "cash"),)


# ============================================================== close_book_unpriced


def test_close_book_unpriced_sells_at_the_mark():
    b = book("100", pos("A", 10, "20", entry_price="20", days_held=3), pos("B", 5, "40"), last=TUE)
    nb, fills, trades = close_book_unpriced(b, ["A"], DAILY_SWITCH)
    # q(20 × 10 × 0.999) = 199.8; cost q(20 × 10 × 1.001) = 200.2
    (f,) = fills
    assert (f.reason, f.price, f.cash_usd, f.session_date) == ("forced", P("20"), P("199.8"), D(TUE))
    (t,) = trades
    assert (t.exit_reason, t.exit_date, t.days_held, t.pnl_usd) == ("forced", D(TUE), 3, P("-0.4"))
    assert nb.held() == frozenset({"B"})
    assert (nb.cash, nb.equity, nb.last_session) == (P("299.8"), P("499.8"), D(TUE))


def test_close_book_unpriced_checks():
    b = book("100", pos("A", 10, "20"), last=TUE)
    assert close_book_unpriced(b, [], DAILY_SWITCH) == (b, (), ())
    with pytest.raises(ValueError, match="not an open position"):
        close_book_unpriced(b, ["Z"], DAILY_SWITCH)
    with pytest.raises(TypeError):
        close_book_unpriced(b, "A", DAILY_SWITCH)
    with pytest.raises(ValueError, match="before any session"):
        close_book_unpriced(replace(b, last_session=None), ["A"], DAILY_SWITCH)


# ============================================================== P&L reconciles with cash


def test_episode_pnl_reconciles_with_cash_exactly():
    r = TradeRules(id="pnl", engine="book", entry="open_limit", resize=True)
    cash0 = W(10000)
    steps = []
    s = go(
        new_book(cash0),
        MON,
        day(bar("A", MON, "100", "101", "99", "100.5"), bar("B", MON, "40", "40.5", "39.5", "40.2")),
        (T("A", "0.5", "100", stop="90"), T("B", "0.3", "40", take="48")),
        r,
    )
    steps.append(s)
    s = go(
        s.book,
        TUE,
        day(bar("A", TUE, "101", "102", "100", "101"), bar("B", TUE, "40", "41", "39.9", "40.5")),
        (T("A", "0.3", "100.5", stop="90"), T("B", "0.5", "40.2", take="48")),
        r,
        dividends={"A": W("0.37"), "B": W("0.11")},
    )
    steps.append(s)
    s = go(s.book, WED, day(bar("A", WED, "101", "101", "100", "100.5"), bar("B", WED, "45", "48.5", "44", "47")), None, r)
    steps.append(s)
    s = go(s.book, THU, day(bar("A", THU, "99.5", "100", "99", "99.8")), (), r)
    steps.append(s)

    fills = [f for st in steps for f in st.fills]
    trades = [t for st in steps for t in st.trades]
    credited = [amount for st in steps for _, amount in st.dividends]
    assert [f.reason for f in fills] == ["entry", "entry", "trim", "add", "tp", "signal"]
    assert [t.exit_reason for t in trades] == ["tp", "signal"]
    assert len(credited) == 2
    assert s.book.positions == ()
    # Every cash movement belongs to exactly one episode: Σ pnl == Σ fill cash + Σ dividends == Δcash.
    assert sum((t.pnl_usd for t in trades), W(0)) == s.book.cash - cash0
    assert sum((f.cash_usd for f in fills), W(0)) + sum(credited, W(0)) == s.book.cash - cash0
    assert s.snapshot.equity_usd == s.book.cash


# ============================================================== §5 replay: V0_BOOK == size_picks + step


def _tick(x: float | Decimal) -> Decimal:
    """``x`` on a 0.25 price grid, so exact ties (low == limit, low == stop, open == take) occur."""
    d = W(repr(x)) if isinstance(x, float) else x
    return sim.q((d * 4).to_integral_value() / 4)


def _market(seed: int, symbols: dict[str, float], sessions: list[date]) -> dict[date, dict[str, Bar]]:
    rng = random.Random(seed)
    closes = dict(symbols)
    out: dict[date, dict[str, Bar]] = {}
    for i, s in enumerate(sessions):
        bars: dict[str, Bar] = {}
        for sym in sorted(symbols):
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


def _picks(bars: dict[str, Bar], order: list[str]) -> list[Pick]:
    out = []
    for sym in order:
        b = bars.get(sym)
        if b is None:
            continue
        c = b.close
        limit, tp, sl = _tick(c * W("0.995")), _tick(c * W("1.015")), _tick(c * W("0.97"))
        if sl < limit < tp:
            out.append(Pick(sym, c, limit, tp, sl))
    return out


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_v0_book_replays_size_picks_and_step(seed):
    sessions = dates.sessions(D("2026-06-01"), D("2026-09-30"))
    symbols = {"AAA": 50.0, "BBB": 120.0, "CCC": 20.0, "DDD": 300.0, "EEE": 75.0, "XPN": 3000.0}
    market = _market(seed, symbols, sessions)
    rng = random.Random(seed + 100)
    cash0 = W("10000")
    pf = new_portfolio(cash0)
    bk = new_book(cash0)
    w = equal_weight(4)
    sim_closed = []
    book_closed = []
    data = market[sessions[0]]
    for s in sessions[1:]:
        order = sorted(symbols)
        rng.shuffle(order)
        picks = _picks(data, order)

        sized = size_picks(pf, picks, s)
        res = step(sized.portfolio, s, market[s])
        pf = res.portfolio
        sim_closed += [
            (e.order.symbol, e.order.fill_date, e.order.fill_price, e.order.exit_date, e.order.exit_price, e.order.exit_reason, e.order.days_held, e.order.pnl_usd)
            for e in res.events
            if e.kind == "exit"
        ]

        held = bk.held()
        targets = tuple(Target(p.symbol, w, p.mark) for p in bk.positions) + tuple(
            Target(p.symbol, w, p.last_price, limit=p.limit_price, stop=p.sl_price, take=p.tp_price)
            for p in picks
            if p.symbol not in held
        )
        out = step_book(bk, s, market[s], targets, V0_BOOK)
        bk = out.book
        book_closed += [
            (t.symbol, t.entry_date, t.entry_price, t.exit_date, t.exit_price, t.exit_reason, t.days_held, t.pnl_usd)
            for t in out.trades
        ]

        assert (out.snapshot.cash_usd, out.snapshot.equity_usd) == (res.snapshot.cash_usd, res.snapshot.equity_usd), s
        assert sorted(o.symbol for o in pf.open_orders()) == sorted(bk.held()), s
        data = market[s]

    assert sorted(book_closed) == sorted(sim_closed)
    assert len(sim_closed) >= 20
    assert {r[5] for r in sim_closed} == {"gap", "sl", "time", "tp"}
```
**Impact:** test-only.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/trade-rules-dev-search && engine/.venv/bin/python -c "import seer_engine.sim as s; print(len(s.PRESETS), s.V0_BOOK.engine)"` prints `9 book`.
**Tests:**
- `docker start seer-pg`
- `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`
  — **1061 passed, 0 skipped** when phase 1 lands first (970 baseline + 35 `test_sim_rules.py` +
  56 `test_sim_book.py`); 1095 if phase 4 (+34) landed before it (see the index's count table).
  A different count is a finding: name the missing or extra tests in the phase log.
- Focused: `engine/.venv/bin/pytest engine/tests/test_sim_rules.py engine/tests/test_sim_book.py engine/tests/test_sim_purity.py engine/tests/test_sim_lifecycle.py engine/tests/test_sim_sizing.py -q`.
  (Run while planning against a scratch copy of the tree with the code above: 205 passed.)
- Frozen set: `git diff --stat 2546a92 -- engine/src/seer_engine/sim/model.py engine/src/seer_engine/sim/lifecycle.py engine/src/seer_engine/sim/sizing.py engine/src/seer_engine/sim/split_adjust.py engine/tests/simkit.py engine/tests/test_sim_purity.py`
  prints nothing.
- Use the worktree's own `engine/.venv`, never `/home/miftah/seer/engine/.venv`.

**Manual check:** none.
**Exit criteria:** the suite is green with 0 skipped at 1061 collected (1095 with phase 4 landed); `test_sim_purity.py`
covers `rules.py` and `book.py` (glob); `test_design_v0_agrees_with_the_model_constants` passes;
the V0 replay passes for all three seeds; the frozen-set diff is empty.

## Handoffs

- **Phase 2 (`PicksAllocator`, R3):** its targets are every held symbol (weight
  `equal_weight(slots)`, `last` = most recent close, no limit/stop/take) then every unheld pick;
  their Σ weight may exceed 1, which `step_book` accepts because `V0_BOOK.max_positions == 4`
  (interface decision 1, plan index D-A; phase 2's tests already pass `max_weight_sum=None` for
  `PICKS`). `BlendAllocator`/`VolTargetAllocator` must still keep Σ ≤ 1 (the TBILL/HOLD presets
  have no cap and `step_book` raises).
- **Phase 3 (`run_book`, R1):**
  - pass `idle_symbol_ok=True` exactly when it appended the `rules.idle_symbol` target (phase 3
    raises its own `ValueError` when the allocator targets the idle symbol itself, and passes
    the allocator `held` without the idle symbol, plan index D-J);
  - an `entry="limit"` rule set with an idle symbol is valid: the price-less idle target is
    bought by the D-B fallback (no preset combines them today);
  - after `close_book_unpriced`, rebuild the session's `BookSnapshot` from the returned book:
    `equity_usd = book.equity`, `cash_usd = book.cash`,
    `invested_usd = q(Σ shares × mark over positions whose symbol != rules.idle_symbol)`
    (there is no public helper for `invested`; the contract fixes the function's return shape);
  - the parity sim-reason map is `forced -> time + forced`; `Trade.days_held` already matches
    `Order.days_held` in every case (replay-tested here at engine level).
- **Phase 9/10 (stats/report):** `Trade.idle` episodes and idle `Fill`s exist only under an idle
  rule set; `Fill.cost_usd` is the fee (`q(p × n × c)`), which differs from
  `|cash_usd| − notional` by at most 0.0001 per fill due to independent rounding.
- **Phase 13 (docs, R9):** `engine/package_readme.md` should document `sim.rules` / `sim.book`
  (this phase writes no docs).

## Rollback

`git revert` this phase's commit(s): it creates `sim/rules.py`, `sim/book.py` and two test files
and only adds lines to `sim/__init__.py`. Reverting removes them cleanly; no other module depends
on them until phase 3.

