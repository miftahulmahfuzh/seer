# Phase 2: Book-engine split rule

**Plan set:** `PAPER_TRADING_SHIP_PLAN.md`
**Analysis:** `20261004-082027-P4S7_code_analyzer.md`
**Satisfies:** R1 — the nightly paper step can carry a book strategy's held positions and persisted targets across a stock split without double-adjusting or losing cash
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/sim`

---

## Goal

`sim.book` gains a pure split rule for live book positions, `apply_book_split`, the book-engine
twin of `sim.apply_split`. After this phase a caller holding a `Book` (and the `Target`s it
persisted the night before) in pre-split units can rewrite both in post-split units, exactly once
per applied split, with an exact-fraction ratio, whole/fractional share flooring, cash in lieu
credited to cash and the position's `income_usd`, and a `forced` close when shares floor to zero.
`step_book`, `close_book_unpriced`, `sim/split_adjust.py` and every runner are unchanged.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `seer_engine.sim.book.BookSplit` (`sim/book.py`, frozen slots dataclass after `BookStep`):
  `book: Book`, `targets: tuple[Target, ...] | None`, `in_lieu: Decimal`, `trade: Trade | None`, `fills: tuple[Fill, ...]`.
- `seer_engine.sim.book.apply_book_split(book, symbol, factor, session, rules, targets=None) -> BookSplit` (`sim/book.py`, end of file) — the C3 signature, unchanged.
- Private helpers in `sim/book.py`: `_SHARE_QUANTA_PER_UNIT`, `_split_position_shares`, `_rescale_optional`, `_rescale_target`.
- Re-exports `apply_book_split` and `BookSplit` from `seer_engine.sim` (`sim/__init__.py`, import list and `__all__`).
- New test file `engine/tests/test_sim_book_split.py`.

**Signature changes:** none.

**Semantics callers code against (phase 4 `settle_book`, phase 8 replay):**
- `factor` = `split_to / split_from` (`seer_engine.splits.Split.factor`, the same value `sim.apply_split` takes; also what `split_adjustments` stores). Read as an exact fraction via `split_adjust._split_ratio` (1-for-3 is exactly 1/3).
- Must be called with `session > book.last_session`, `session` an NYSE session, `rules.engine == "book"`; call it after `last_session`'s step and before `step_book(session)`, once per applied `(symbol, session)` split.
- Position: `shares = floor(shares × r)` (whole) or floored to `SHARE_QUANTUM` (0.0001) when `rules.fractional`; `mark`, `entry_price`, `stop`, `take` → `_q_exact(p / r)`; `cost_usd`, `entry_date`, `days_held`, `exit_pending` unchanged; `income_usd += in_lieu`.
- `in_lieu = _q_exact(remainder × new_mark)` (new mark is the already-rounded rescaled mark, as in `apply_split`), credited to `book.cash`. No cost.
- Floor to zero: position removed; `trade` = `Trade(exit_date=session, exit_price=old mark, days_held unchanged, income = old income + in_lieu, pnl = income − cost, exit_reason="forced", idle = symbol == rules.idle_symbol)`; `fills` = one `Fill(session, symbol, "sell", old shares, old mark, cash_usd=in_lieu, cost_usd=0, reason="forced")`. Note the fill's `cash_usd` is the in-lieu cash, **not** `price × shares × (1 − c)`.
- A surviving position produces **no** fill (the remainder is not representable as a 4-dp share count in general, e.g. 1/3 share); its in-lieu cash is visible only as `BookSplit.in_lieu` and in `income_usd`.
- `book.equity` is recomputed as `q(cash + Σ shares × mark)` when the symbol is held (may differ from the pre-split equity by the rounding of the rescaled mark, e.g. 605 → 604.9998); `last_session` unchanged.
- Targets: each `Target` whose symbol matches gets `last`, `limit`, `stop`, `take` rescaled (weight unchanged, order kept); other targets are the same objects; `None` stays `None`, `()` stays `()`.
- No position in `symbol`: `BookSplit.book is book` (cash/equity untouched) — targets are still rescaled. Nothing references `symbol`: `book` and `targets` are returned as the same objects, `in_lieu = 0`, `trade None`, `fills ()`. Input validation (factor, session, rules, targets types) runs before this shortcut, as in `apply_split`.
- Errors: TypeError for a non-`Book`, non-`str` symbol, non-`Decimal` factor (float or int), non-`date`/`datetime` session, non-`TradeRules`, non-tuple targets or a non-`Target` element; ValueError for an empty symbol, a factor that is not a split ratio (≤ 0, 1, non-finite, not near a fraction with denominator ≤ 10^6), a non-session or `session <= last_session`, a non-book rule set, a rescaled mark that rounds to 0, or (surviving position only) a rescaled entry/stop/take that rounds to 0 or `stop >= take`, or a rescaled target that `Target` refuses.

**Requires (from earlier phases):** nothing.
**Leaves alone (owned by others):** `step_book` and `close_book_unpriced` behaviour and every other function in `sim/book.py`; `sim/split_adjust.py` (imported from, not edited); `backtest/*` runners (closed records); `paper/*` (phases 1, 3, 4, 6, 8); `db/migrations/*` (phase 1); `engine/package_readme.md` (phase 13).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/sim/book.py:1-37` | modify | module docstring: one paragraph on splits |
| `engine/src/seer_engine/sim/book.py:39-52` | modify | imports: `Fraction`, `split_adjust` private helpers |
| `engine/src/seer_engine/sim/book.py:298` (after `BookStep`) | modify | add `BookSplit` dataclass |
| `engine/src/seer_engine/sim/book.py:762` (end of file, after `close_book_unpriced`) | modify | add `_SHARE_QUANTA_PER_UNIT`, `_split_position_shares`, `_rescale_optional`, `_rescale_target`, `apply_book_split` |
| `engine/src/seer_engine/sim/__init__.py:15-29, 74-132` | modify | re-export `BookSplit`, `apply_book_split`; docstring line |
| `engine/tests/test_sim_book_split.py` | create | 20 hand-checked tests |

`engine/tests/test_sim_purity.py` needs no edit: it globs every `sim/*.py`, so the new code is
covered by the existing AST and fresh-interpreter import checks.

## Implementation Steps

### Step 1: Module docstring
**File:** `engine/src/seer_engine/sim/book.py:33-36`
**Change:** insert one paragraph between the `V0_BOOK` paragraph (ends line 34) and the "Pure:" line (36).
**Code:** replace lines 33–36

```python
Under ``V0_BOOK`` with every held symbol re-targeted and §5 brackets for new picks, this is
``sim.size_picks`` + ``sim.step`` exactly (the phase-3 parity test).

Splits (paper trading): ``apply_book_split`` rewrites a held position and the persisted targets
for a symbol in post-split units before the split's execution session is stepped, mirroring
``sim.apply_split`` (exact-fraction ratio, floored shares, cash in lieu, floor-to-zero forced close).

Pure: no clock, no I/O, no randomness. Floats are refused at every boundary.
```
**Impact:** documentation only.

### Step 2: Imports
**File:** `engine/src/seer_engine/sim/book.py:39-52`
**Change:** add `from fractions import Fraction` and the `split_adjust` import. `split_adjust` imports
only `seer_engine.dates`, `seer_engine.prices` and `seer_engine.sim.model`, never `sim.book`, so there
is no cycle. The three helpers are private to `split_adjust`; importing them (rather than copying) is
what the phase scope asks for ("reuse … by import") and keeps the ratio rule in one place.
**Code:** the import block becomes

```python
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import ROUND_DOWN, ROUND_FLOOR, Decimal
from fractions import Fraction
from types import MappingProxyType
from typing import Literal

from seer_engine import dates
from seer_engine.prices import Bar
from seer_engine.sim.model import q
from seer_engine.sim.rules import OPEN_LIMIT_BAND, RESIZE_BAND, SHARE_QUANTUM, TradeRules
from seer_engine.sim.split_adjust import _q_exact, _rescale_price, _split_ratio
```
**Impact:** none at runtime; `seer_engine.sim` already imports `split_adjust` (line 72 of `__init__`).

### Step 3: `BookSplit` value
**File:** `engine/src/seer_engine/sim/book.py:298` — directly after `class BookStep` (ends line 297), before `def new_book` (line 300).
**Code:**

```python
@dataclass(frozen=True, slots=True)
class BookSplit:
    """What ``apply_book_split`` did to one symbol on its execution session.

    ``book``: the book in post-split units (``last_session`` unchanged). ``targets``: the
    targets passed in with the symbol's prices rescaled (None when None was passed).
    ``in_lieu``: cash paid for the fractional remainder (the whole payout on a floor-to-zero),
    already in ``book.cash`` and in the position's ``income_usd``. ``trade``/``fills``: the
    forced close when the position floored to zero shares, else None / ().
    """

    book: Book
    targets: tuple[Target, ...] | None
    in_lieu: Decimal
    trade: Trade | None
    fills: tuple[Fill, ...]
```
**Impact:** new public value; nothing existing changes.

### Step 4: the split rule
**File:** `engine/src/seer_engine/sim/book.py:762` — append after `close_book_unpriced` (ends line 761), under a new section header.
**Code:**

```python
# --------------------------------------------------------------------------- splits

_SHARE_QUANTA_PER_UNIT = Fraction(1) / Fraction(SHARE_QUANTUM)  # 10_000


def _split_position_shares(shares: Decimal, ratio: Fraction, fractional: bool) -> tuple[Decimal, Fraction]:
    """``shares × ratio`` floored to whole shares (or to ``SHARE_QUANTUM`` when ``fractional``),
    and the exact remainder in post-split shares."""
    total = Fraction(shares) * ratio
    if fractional:
        scaled = total * _SHARE_QUANTA_PER_UNIT
        kept = Decimal(scaled.numerator // scaled.denominator) * SHARE_QUANTUM
    else:
        kept = Decimal(total.numerator // total.denominator)
    return kept, total - Fraction(kept)


def _rescale_optional(price: Decimal | None, ratio: Fraction) -> Decimal | None:
    return None if price is None else _rescale_price(price, ratio)


def _rescale_target(t: Target, ratio: Fraction) -> Target:
    """``t`` in post-split units, weight unchanged. ValueError (from ``Target``) when 4 dp cannot
    hold a rescaled price or the rescaled stop/take no longer bracket the reference price."""
    return Target(
        symbol=t.symbol,
        weight=t.weight,
        last=_rescale_price(t.last, ratio),
        limit=_rescale_optional(t.limit, ratio),
        stop=_rescale_optional(t.stop, ratio),
        take=_rescale_optional(t.take, ratio),
    )


def apply_book_split(
    book: Book,
    symbol: str,
    factor: Decimal,
    session: date,
    rules: TradeRules,
    targets: tuple[Target, ...] | None = None,
) -> BookSplit:
    """Rewrite ``symbol``'s position (and its targets) in post-split units for a split executing
    on ``session`` (mirrors ``sim.apply_split`` for the book engine).

    ``factor`` is ``split_to / split_from`` (``seer_engine.splits.Split.factor``), read as an
    exact fraction ``r``. The position's shares become ``floor(shares × r)`` (whole shares, or
    multiples of ``SHARE_QUANTUM`` under ``rules.fractional``); mark, entry price, stop and take
    become ``q(p / r)``; the remainder is paid as cash in lieu ``q(remainder × new mark)``, with
    no cost, into ``cash`` and the position's ``income_usd``. A position that floors to 0 shares
    is closed: a "forced" ``Trade`` and sell ``Fill`` dated ``session`` at the old mark, whose
    income includes the in-lieu cash (fill ``cash_usd`` = the in-lieu cash, ``cost_usd`` 0). The
    book's equity is recomputed; ``last_session`` is unchanged. Each target for ``symbol`` gets
    last, limit, stop and take rescaled, weight unchanged; other targets are kept as they are.
    Nothing references ``symbol``: the book and targets come back as the same objects.

    Call it after ``last_session``'s step and before stepping ``session``, once per applied split.
    TypeError on a wrong type (a float factor included); ValueError when ``factor`` is not a split
    ratio, ``rules.engine`` is not "book", ``session`` is not an NYSE session after
    ``book.last_session``, or a rescaled price cannot be held at 4 dp.
    """
    if not isinstance(book, Book):
        raise TypeError(f"book must be a Book, got {type(book).__name__}")
    if not isinstance(symbol, str):
        raise TypeError(f"symbol must be a str, got {type(symbol).__name__}")
    if not symbol:
        raise ValueError("empty symbol")
    ratio = _split_ratio(factor)
    _date("session", session)
    if not dates.is_session(session):
        raise ValueError(f"{session} is not an NYSE session")
    if book.last_session is not None and session <= book.last_session:
        raise ValueError(f"split session {session} must be after the last session stepped ({book.last_session})")
    if not isinstance(rules, TradeRules):
        raise TypeError(f"rules must be a TradeRules, got {type(rules).__name__}")
    if rules.engine != "book":
        raise ValueError(f"apply_book_split runs engine 'book' rules only, got {rules.engine!r} ({rules.id})")
    if targets is not None:
        if not isinstance(targets, tuple):
            raise TypeError(f"targets must be a tuple or None, got {type(targets).__name__}")
        for t in targets:
            if not isinstance(t, Target):
                raise TypeError(f"targets must hold Target values, got {type(t).__name__}")

    new_targets = targets
    if targets is not None and any(t.symbol == symbol for t in targets):
        new_targets = tuple(_rescale_target(t, ratio) if t.symbol == symbol else t for t in targets)

    p = book.position(symbol)
    if p is None:
        return BookSplit(book=book, targets=new_targets, in_lieu=_ZERO, trade=None, fills=())

    mark = _rescale_price(p.mark, ratio)
    if mark <= 0:
        raise ValueError(f"{symbol}: a split of ratio {ratio} leaves a mark ({p.mark} -> {mark}) that 4 dp cannot hold")
    shares, remainder = _split_position_shares(p.shares, ratio, rules.fractional)
    in_lieu = _q_exact(remainder * Fraction(mark))
    cash = book.cash + in_lieu
    income = p.income_usd + in_lieu

    trade: Trade | None = None
    fills: tuple[Fill, ...] = ()
    if shares <= 0:
        exit_price = p.mark
        fills = (
            Fill(
                session_date=session,
                symbol=symbol,
                side="sell",
                shares=p.shares,
                price=exit_price,
                cash_usd=in_lieu,
                cost_usd=_ZERO,
                reason="forced",
            ),
        )
        trade = Trade(
            symbol=symbol,
            entry_date=p.entry_date,
            exit_date=session,
            entry_price=p.entry_price,
            exit_price=exit_price,
            days_held=p.days_held,
            cost_usd=p.cost_usd,
            income_usd=income,
            pnl_usd=income - p.cost_usd,
            exit_reason="forced",
            idle=symbol == rules.idle_symbol,
        )
        positions = tuple(x for x in book.positions if x.symbol != symbol)
    else:
        entry_price = _rescale_price(p.entry_price, ratio)
        stop = _rescale_optional(p.stop, ratio)
        take = _rescale_optional(p.take, ratio)
        if (
            entry_price <= 0
            or (stop is not None and stop <= 0)
            or (take is not None and take <= 0)
            or (stop is not None and take is not None and stop >= take)
        ):
            raise ValueError(
                f"{symbol}: a split of ratio {ratio} leaves prices that 4 dp cannot hold "
                f"(mark {mark}, entry {entry_price}, stop {stop}, take {take})"
            )
        adjusted = replace(
            p,
            shares=shares,
            mark=mark,
            entry_price=entry_price,
            stop=stop,
            take=take,
            income_usd=income,
        )
        positions = tuple(adjusted if x.symbol == symbol else x for x in book.positions)
    equity, _ = _valuation(cash, positions, rules.idle_symbol)
    return BookSplit(
        book=Book(cash=cash, equity=equity, positions=positions, last_session=book.last_session),
        targets=new_targets,
        in_lieu=in_lieu,
        trade=trade,
        fills=fills,
    )
```
Notes for the implementer:
- `_ZERO`, `_date`, `_valuation`, `Position`, `Target`, `Trade`, `Fill`, `Book` are the module's own names (lines 61, 92, 404, 143–279).
- Rounding: `_q_exact` is half-up on the exact fraction, the same as `q` for 4-dp inputs; using it keeps the result identical to `sim.apply_split` for the same prices.
- Survivors' entry/stop/take are only validated when the position survives (a closing position's stop/take are dropped, so their rescaled values do not matter); the mark is always validated first (as in `apply_split`).

**Impact:** new public function; `step_book` untouched.

### Step 5: export from `sim`
**File:** `engine/src/seer_engine/sim/__init__.py:10-12` (docstring), `:15-29` (import), `:74-132` (`__all__`)
**Change:** docstring sentence, import list, `__all__` (kept alphabetical in its two groups, as today).
**Code:** the docstring paragraph at lines 10–12 becomes

```python
P7a adds trade rules as a value (``sim.rules``: ``TradeRules``, ``DESIGN_V0`` and the presets)
and the book engine every non-default rule set runs on (``sim.book``: ``step_book``, and
``apply_book_split`` for splits on live book positions).
``DESIGN_V0`` keeps running on ``size_picks`` + ``step`` above, unchanged.
```
the `sim.book` import (lines 15–29) becomes

```python
from seer_engine.sim.book import (
    WEIGHT_QUANTUM,
    Book,
    BookSnapshot,
    BookSplit,
    BookStep,
    Fill,
    Position,
    Target,
    Trade,
    apply_book_split,
    close_book_unpriced,
    equal_weight,
    new_book,
    step_book,
    to_weight,
)
```
and `__all__` (lines 74–132) becomes

```python
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
    "BookSplit",
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
    "apply_book_split",
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
**Impact:** `from seer_engine.sim import apply_book_split, BookSplit` works (phase 4 relies on it).

### Step 6: tests
**File:** `engine/tests/test_sim_book_split.py` (new)
**Change:** 20 tests: forward 10-for-1 and 3-for-2, reverse 1-for-32 and 1-for-10, exact 1-for-3,
whole vs fractional flooring, floor-to-zero (incl. idle instrument), targets rescale (alone, with the
position, empty), no-op identity, stepping the split session afterwards, `exit_pending` kept, type and
value errors, 4-dp refusals, purity (inputs untouched, deterministic, frozen) and the `sim` export.
Every number is worked by hand in a comment. Planner check: Steps 1–6 were applied verbatim to a
scratch copy of `engine/src` and run on the worktree's `engine/.venv` together with every
`test_sim_*.py`, `test_book_runner.py` and `test_strategy_purity.py`: 319 passed, and `step_book`'s
source is byte-identical to today's.
**Code:**

```python
"""apply_book_split: live book positions and targets rewritten in post-split units (paper-trading-ship
phase 2; plan index Decisions "§6 book split rule").

Every expected number is worked by hand in the comment next to it. Sessions: Mon 2026-10-05 is the
last stepped session, Tue 2026-10-06 is the split's execution session. No database needed.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime
from decimal import Decimal

import pytest

from seer_engine import sim
from seer_engine.sim import (
    DESIGN_V0,
    MONTHLY_HOLD,
    MONTHLY_HOLD_TBILL,
    Book,
    BookSplit,
    Fill,
    Position,
    Target,
    Trade,
    TradeRules,
    apply_book_split,
    step_book,
)
from seer_engine.splits import Split
from simkit import D, P, bar, day

MON = D("2026-10-05")
TUE = D("2026-10-06")
SAT = D("2026-10-10")

W = Decimal

TEN_FOR_ONE = W(10)
THREE_FOR_TWO = W(3) / W(2)  # 1.5
ONE_FOR_32 = W(1) / W(32)  # 0.03125, exact
ONE_FOR_10 = W("0.1")
ONE_FOR_3 = Split("ABC", TUE, split_from=W(3), split_to=W(1)).factor  # 0.3333…3 (28 digits)

WHOLE = MONTHLY_HOLD  # fractional=False
FRACTIONAL = TradeRules(id="fractional", engine="book", entry="open_limit", resize=True, fractional=True)


def pos(
    symbol: str,
    shares: str,
    mark: str,
    *,
    entry_price: str | None = None,
    days_held: int = 3,
    cost: str | None = None,
    income: str = "0",
    stop: str | None = None,
    take: str | None = None,
    exit_pending: bool = False,
) -> Position:
    """A held position entered 2026-10-01; ``cost`` defaults to q(entry × shares × 1.001)."""
    n = W(shares)
    entry = P(mark if entry_price is None else entry_price)
    return Position(
        symbol=symbol,
        shares=n,
        mark=P(mark),
        entry_date=D("2026-10-01"),
        entry_price=entry,
        days_held=days_held,
        cost_usd=sim.q(entry * n * W("1.001")) if cost is None else P(cost),
        income_usd=P(income),
        stop=None if stop is None else P(stop),
        take=None if take is None else P(take),
        exit_pending=exit_pending,
    )


def book(cash: str, *positions: Position, last=MON) -> Book:
    ps = tuple(sorted(positions, key=lambda p: p.symbol))
    equity = sim.q(P(cash) + sum((p.shares * p.mark for p in ps), W(0)))
    return Book(cash=P(cash), equity=equity, positions=ps, last_session=last)


def T(symbol: str, weight: str, last: str, limit: str | None = None, stop: str | None = None, take: str | None = None) -> Target:
    return Target(
        symbol=symbol,
        weight=W(weight),
        last=P(last),
        limit=None if limit is None else P(limit),
        stop=None if stop is None else P(stop),
        take=None if take is None else P(take),
    )


# ============================================================== forward splits


def test_forward_10_for_1_whole_shares_no_remainder():
    abc = pos("ABC", "3", "125.5", entry_price="120", stop="114", take="132")  # cost q(360.36)
    b = book("640", abc)  # equity 640 + 3 × 125.5 = 1016.5

    out = apply_book_split(b, "ABC", TEN_FOR_ONE, TUE, WHOLE)

    assert isinstance(out, BookSplit)
    (p,) = out.book.positions
    assert p.shares == W(30)  # 3 × 10
    assert p.mark == P("12.55")  # 125.5 / 10
    assert p.entry_price == P("12")  # 120 / 10
    assert p.stop == P("11.4") and p.take == P("13.2")  # 114 / 10, 132 / 10
    assert p.cost_usd == P("360.36") and p.income_usd == P("0")  # cost unchanged, no in lieu
    assert p.entry_date == D("2026-10-01") and p.days_held == 3
    assert out.in_lieu == P("0")
    assert out.book.cash == P("640")
    assert out.book.equity == P("1016.5")  # 640 + 30 × 12.55 = 640 + 376.5
    assert out.book.last_session == MON  # the split does not step a session
    assert out.trade is None and out.fills == ()
    assert out.targets is None


def test_forward_3_for_2_whole_shares_pays_the_half_share_in_lieu():
    abc = pos("ABC", "5", "101", entry_price="99", stop="96", take="108", income="2")
    b = book("100", abc)  # equity 100 + 505 = 605

    out = apply_book_split(b, "ABC", THREE_FOR_TWO, TUE, WHOLE)

    (p,) = out.book.positions
    assert p.shares == W(7)  # floor(5 × 1.5 = 7.5)
    assert p.mark == P("67.3333")  # 101 / 1.5 = 67.3333…
    assert p.entry_price == P("66")  # 99 / 1.5
    assert p.stop == P("64") and p.take == P("72")  # 96 / 1.5, 108 / 1.5
    assert out.in_lieu == P("33.6667")  # q(0.5 × 67.3333 = 33.66665), half-up
    assert p.income_usd == P("35.6667")  # 2 + 33.6667
    assert out.book.cash == P("133.6667")  # 100 + 33.6667
    # Recomputed: 133.6667 + 7 × 67.3333 = 133.6667 + 471.3331 = 604.9998 (605 before; the
    # 0.0002 is the rounding of the rescaled mark, not lost cash).
    assert out.book.equity == P("604.9998")
    assert out.trade is None and out.fills == ()


# ============================================================== reverse splits


def test_reverse_1_for_32_keeps_three_shares_and_pays_an_eighth_in_lieu():
    abc = pos("ABC", "100", "2.5", entry_price="2.4", stop="2.2", take="3")
    b = book("0", abc)  # equity 250

    out = apply_book_split(b, "ABC", ONE_FOR_32, TUE, WHOLE)

    (p,) = out.book.positions
    assert p.shares == W(3)  # floor(100 / 32 = 3.125)
    assert p.mark == P("80")  # 2.5 × 32
    assert p.entry_price == P("76.8")  # 2.4 × 32
    assert p.stop == P("70.4") and p.take == P("96")  # 2.2 × 32, 3 × 32
    assert out.in_lieu == P("10")  # 0.125 × 80
    assert p.income_usd == P("10")
    assert out.book.cash == P("10")
    assert out.book.equity == P("250")  # 10 + 3 × 80


def test_one_for_3_is_read_as_an_exact_third():
    # 300 × 0.3333…3 (the 28-digit Decimal) is 99.99…, which would floor to 99.
    b = book("0", pos("ABC", "300", "10"))
    out = apply_book_split(b, "ABC", ONE_FOR_3, TUE, WHOLE)
    (p,) = out.book.positions
    assert p.shares == W(100)  # 300 / 3 exactly
    assert p.mark == P("30")  # 10 × 3
    assert out.in_lieu == P("0")

    b = book("0", pos("ABC", "301", "10"))
    out = apply_book_split(b, "ABC", ONE_FOR_3, TUE, WHOLE)
    (p,) = out.book.positions
    assert p.shares == W(100)  # floor(301 / 3 = 100.333…)
    assert out.in_lieu == P("10")  # 1/3 × 30
    assert out.book.cash == P("10")
    assert out.book.equity == P("3010")  # 10 + 100 × 30


# ============================================================== whole vs fractional shares


def test_whole_and_fractional_rules_floor_to_their_own_quantum():
    abc = pos("ABC", "2.5001", "90")  # a fractional book's position
    b = book("0", abc)  # equity q(2.5001 × 90 = 225.009)

    whole = apply_book_split(b, "ABC", THREE_FOR_TWO, TUE, WHOLE)
    (p,) = whole.book.positions
    assert p.shares == W(3)  # floor(2.5001 × 1.5 = 3.75015)
    assert p.mark == P("60")  # 90 / 1.5
    assert whole.in_lieu == P("45.009")  # 0.75015 × 60

    frac = apply_book_split(b, "ABC", THREE_FOR_TWO, TUE, FRACTIONAL)
    (p,) = frac.book.positions
    assert p.shares == W("3.7501")  # 3.75015 floored to 0.0001
    assert frac.in_lieu == P("0.003")  # 0.00005 × 60
    assert p.income_usd == P("0.003")
    assert frac.book.equity == P("225.009")  # 0.003 + 3.7501 × 60 = 0.003 + 225.006


def test_fractional_one_for_3_floors_a_third_to_the_share_quantum():
    b = book("0", pos("ABC", "1", "30"))
    out = apply_book_split(b, "ABC", ONE_FOR_3, TUE, FRACTIONAL)
    (p,) = out.book.positions
    assert p.shares == W("0.3333")  # 1/3 floored to 0.0001
    assert p.mark == P("90")  # 30 × 3
    assert out.in_lieu == P("0.003")  # (1/3 − 0.3333 = 1/30000) × 90 = 0.003


# ============================================================== floor to zero


def test_floor_to_zero_closes_the_position_as_a_forced_trade_at_the_old_mark():
    abc = pos("ABC", "7", "4", entry_price="3.5", income="1.2")  # cost q(3.5 × 7 × 1.001 = 24.5245)
    xyz = pos("XYZ", "2", "50")
    b = book("100", abc, xyz)  # equity 100 + 28 + 100 = 228

    out = apply_book_split(b, "ABC", ONE_FOR_10, TUE, WHOLE)

    assert out.book.positions == (xyz,)  # other positions untouched
    assert out.in_lieu == P("28")  # 7 / 10 = 0.7 share × (4 × 10 = 40)
    assert out.book.cash == P("128")
    assert out.book.equity == P("228")  # 128 + 2 × 50
    assert out.book.last_session == MON
    assert out.trade == Trade(
        symbol="ABC",
        entry_date=D("2026-10-01"),
        exit_date=TUE,
        entry_price=P("3.5"),
        exit_price=P("4"),  # the old (pre-split) mark
        days_held=3,
        cost_usd=P("24.5245"),
        income_usd=P("29.2"),  # 1.2 + 28 in lieu
        pnl_usd=P("4.6755"),  # 29.2 − 24.5245
        exit_reason="forced",
        idle=False,
    )
    assert out.fills == (
        Fill(
            session_date=TUE,
            symbol="ABC",
            side="sell",
            shares=W(7),  # pre-split shares
            price=P("4"),
            cash_usd=P("28"),
            cost_usd=P("0"),  # cash in lieu has no cost
            reason="forced",
        ),
    )


def test_floor_to_zero_of_the_idle_instrument_is_an_idle_trade():
    b = book("0", pos("BIL", "3", "91"))
    out = apply_book_split(b, "BIL", ONE_FOR_10, TUE, MONTHLY_HOLD_TBILL)
    assert out.book.positions == ()
    assert out.trade is not None and out.trade.idle is True
    assert out.in_lieu == P("273")  # 0.3 × 910
    assert out.book.equity == P("273")


def test_floor_to_zero_does_not_check_stop_and_take_it_drops():
    # stop 0.4 / 10000 would round to 0; the position is closed, so that does not matter.
    b = book("0", pos("ABC", "1", "1", stop="0.4", take="2"))
    out = apply_book_split(b, "ABC", W("0.5"), TUE, WHOLE)  # 1-for-2: floor(0.5) = 0
    assert out.book.positions == ()
    assert out.in_lieu == P("1")  # 0.5 × 2


# ============================================================== targets


def test_targets_for_the_symbol_are_rescaled_and_others_kept():
    abc_t = T("ABC", "0.5", "125", limit="124", stop="114", take="132")
    xyz_t = T("XYZ", "0.25", "50")
    targets = (abc_t, xyz_t)
    b = book("1000")  # nothing held

    out = apply_book_split(b, "ABC", TEN_FOR_ONE, TUE, WHOLE, targets)

    assert out.book is b  # no position in ABC: the book is returned as is
    assert out.in_lieu == P("0") and out.trade is None and out.fills == ()
    assert out.targets == (
        Target(symbol="ABC", weight=W("0.5"), last=P("12.5"), limit=P("12.4"), stop=P("11.4"), take=P("13.2")),
        xyz_t,
    )
    assert out.targets[1] is xyz_t  # untouched targets are the same objects, in the same order


def test_reverse_split_rescales_targets_and_the_position_together():
    targets = (T("ABC", "1", "2.5", stop="2.2", take="3"),)
    b = book("0", pos("ABC", "64", "2.5"))
    out = apply_book_split(b, "ABC", ONE_FOR_32, TUE, WHOLE, targets)
    assert out.targets == (Target(symbol="ABC", weight=W("1"), last=P("80"), stop=P("70.4"), take=P("96")),)
    (p,) = out.book.positions
    assert p.shares == W(2)  # 64 / 32
    assert out.in_lieu == P("0")


def test_empty_targets_stay_empty():
    b = book("10", pos("ABC", "3", "10"))
    out = apply_book_split(b, "ABC", TEN_FOR_ONE, TUE, WHOLE, ())
    assert out.targets == ()


# ============================================================== no-op, sequencing


def test_nothing_references_the_symbol_is_a_no_op():
    xyz = pos("XYZ", "2", "50")
    b = book("100", xyz)
    targets = (T("XYZ", "0.5", "50"),)
    out = apply_book_split(b, "ABC", TEN_FOR_ONE, TUE, WHOLE, targets)
    assert out == BookSplit(book=b, targets=targets, in_lieu=P("0"), trade=None, fills=())
    assert out.book is b and out.targets is targets


def test_a_split_book_steps_the_split_session_in_post_split_units():
    b = book("640", pos("ABC", "3", "125.5", entry_price="120", stop="114", take="132"))
    split = apply_book_split(b, "ABC", TEN_FOR_ONE, TUE, WHOLE)
    stepped = step_book(split.book, TUE, day(bar("ABC", TUE, "12.6", "12.9", "12.5", "12.8")), None, WHOLE)
    (p,) = stepped.book.positions
    assert p.shares == W(30) and p.mark == P("12.8") and p.days_held == 4
    assert stepped.trades == ()  # 12.5 > stop 11.4, 12.9 < take 13.2
    assert stepped.snapshot.equity_usd == P("1024")  # 640 + 30 × 12.8


def test_exit_pending_survives_the_split():
    b = book("0", pos("ABC", "3", "10", exit_pending=True))
    out = apply_book_split(b, "ABC", TEN_FOR_ONE, TUE, WHOLE)
    assert out.book.positions[0].exit_pending is True


# ============================================================== errors


def test_type_errors():
    b = book("10", pos("ABC", "3", "10"))
    with pytest.raises(TypeError):
        apply_book_split("book", "ABC", TEN_FOR_ONE, TUE, WHOLE)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        apply_book_split(b, b"ABC", TEN_FOR_ONE, TUE, WHOLE)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        apply_book_split(b, "ABC", 10.0, TUE, WHOLE)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        apply_book_split(b, "ABC", 10, TUE, WHOLE)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        apply_book_split(b, "ABC", TEN_FOR_ONE, datetime(2026, 10, 6), WHOLE)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        apply_book_split(b, "ABC", TEN_FOR_ONE, "2026-10-06", WHOLE)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        apply_book_split(b, "ABC", TEN_FOR_ONE, TUE, "monthly-hold")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        apply_book_split(b, "ABC", TEN_FOR_ONE, TUE, WHOLE, [T("ABC", "1", "10")])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        apply_book_split(b, "ABC", TEN_FOR_ONE, TUE, WHOLE, ("ABC",))  # type: ignore[arg-type]


def test_value_errors():
    b = book("10", pos("ABC", "3", "10"))
    with pytest.raises(ValueError):
        apply_book_split(b, "", TEN_FOR_ONE, TUE, WHOLE)
    for bad in (W(1), W(0), W(-2), W("NaN"), W("Infinity"), W("3.14159265358979")):
        with pytest.raises(ValueError):
            apply_book_split(b, "ABC", bad, TUE, WHOLE)
    with pytest.raises(ValueError):
        apply_book_split(b, "ABC", TEN_FOR_ONE, SAT, WHOLE)  # not a session
    with pytest.raises(ValueError):
        apply_book_split(b, "ABC", TEN_FOR_ONE, MON, WHOLE)  # not after last_session
    with pytest.raises(ValueError):
        apply_book_split(b, "ABC", TEN_FOR_ONE, TUE, DESIGN_V0)  # a bracket rule set
    # The checks run before the no-op shortcut, like sim.apply_split.
    with pytest.raises(ValueError):
        apply_book_split(b, "XYZ", TEN_FOR_ONE, SAT, WHOLE)


def test_prices_4dp_cannot_hold_are_refused():
    # 10000-for-1: stop 0.4 -> 0.00004 rounds to 0 on a surviving position.
    b = book("0", pos("ABC", "1", "1", stop="0.4", take="2"))
    with pytest.raises(ValueError):
        apply_book_split(b, "ABC", W(10000), TUE, WHOLE)
    # A mark that rounds to 0 is refused even when the position would close.
    b = book("0", pos("ABC", "1", "0.0004"))
    with pytest.raises(ValueError):
        apply_book_split(b, "ABC", W(10), TUE, WHOLE)
    # A target whose rescaled limit rounds to 0.
    with pytest.raises(ValueError):
        apply_book_split(book("0"), "ABC", W(10000), TUE, WHOLE, (T("ABC", "1", "1", limit="0.4"),))


# ============================================================== purity


def test_inputs_untouched_and_result_deterministic():
    abc = pos("ABC", "5", "101", entry_price="99", stop="96", take="108")
    b = book("100", abc, pos("XYZ", "2", "50"))
    targets = (T("ABC", "0.5", "101", stop="96", take="108"), T("XYZ", "0.5", "50"))
    before = (b, targets)
    first = apply_book_split(b, "ABC", THREE_FOR_TWO, TUE, WHOLE, targets)
    second = apply_book_split(b, "ABC", THREE_FOR_TWO, TUE, WHOLE, targets)
    assert first == second
    assert (b, targets) == before
    assert b.positions[0] is abc and abc.shares == W(5)
    with pytest.raises(FrozenInstanceError):
        first.in_lieu = W(0)  # type: ignore[misc]


def test_exported_from_sim():
    from seer_engine.sim import book as book_module

    assert sim.apply_book_split is book_module.apply_book_split
    assert sim.BookSplit is book_module.BookSplit
    assert "apply_book_split" in sim.__all__ and "BookSplit" in sim.__all__
```
**Impact:** new tests only; no DB.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/paper-trading-ship && engine/.venv/bin/python -c "import seer_engine.sim as s; print(s.apply_book_split, s.BookSplit)"`
**Tests:**
- Focused: `engine/.venv/bin/pytest engine/tests/test_sim_book_split.py engine/tests/test_sim_book.py engine/tests/test_sim_split.py engine/tests/test_sim_purity.py -q`
- Full (invariant 1): `docker start seer-pg; PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q` — passes with **0 skipped**. `cd web && npx vitest run` is unaffected (no web change) but run it for the invariant.
**Manual check:** `git diff --stat` touches exactly `sim/book.py`, `sim/__init__.py`, `tests/test_sim_book_split.py`; `git diff engine/src/seer_engine/sim/book.py` shows no change inside `step_book` or `close_book_unpriced`.
**Exit criteria:** whole-share and fractional rules, cash in lieu credited to cash and `income_usd`, floor-to-zero → `forced` Trade + Fill at the old mark, prices and targets rescaled by the exact fraction, reverse splits, purity — all covered by green tests; the whole engine suite green with 0 skipped.

## Handoffs

- **Phase 4 (`paper/book.py`, `settle_book`)**: call `apply_book_split(book, symbol, factor, session, rules, targets)` for every applied `(symbol, factor)` split executing on `session`, in a deterministic order (e.g. sorted by symbol), threading `BookSplit.book` and `BookSplit.targets` into the next call and then into `step_book`. Collect `BookSplit.trade`/`fills` ahead of `step_book`'s fills (C1's `book_fills.seq` comment puts "splits" first). Sum `in_lieu` if it wants to report it. Note that `step_book` sizes from `book.equity`, which this rule recomputes.
- **Phase 4 / 6 (persistence)**: a floor-to-zero `Fill` has `cash_usd` = in-lieu cash and `cost_usd` 0, so `price × shares` does not reconcile with `cash_usd` for that row; a surviving position's in-lieu cash produces no `book_fills` row (only `income_usd` moves). If phase 6 or 8 reconciles cash from `book_fills`, it must add `income_usd` deltas or accept this; flagging it for the reconciler.
- **Phase 3 (SPY benchmark)**: `apply_book_split` requires `rules.engine == "book"`. If the benchmark wants to split its SPY holding through this rule it must pass a book rule set (e.g. `MONTHLY_HOLD`, whole shares); otherwise it needs its own rule. Not decided here.
- **Phase 8 (replay)**: a split on a held/pending symbol makes the state differ from a `run_rules` replay over adjusted bars by rounding (whole-share floor, in lieu, recomputed equity); the plan's "split-affected" decision covers it.
- **Phase 13 (docs)**: `engine/package_readme.md` should document `apply_book_split` under the simulator section; not edited here (invariant 8).

## Rollback

`git revert` the phase commit. Nothing else imports `apply_book_split` until phase 4 lands; if phase 4
has landed, revert it first.
