# Phase 1: The printed-price floor, landed where it legally can be

**Plan set:** `FLOOR_RESERVATION_YARDSTICK_PLAN.md`
**Analysis:** `docs/analyzer/20261027-082613-F3K9_code_analyzer.md`
**Satisfies:** R1 — land the printed-price floor repair at the sites where it is legal to land it, and account for the ones where it is not
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/strategies`

---

## Goal

After this phase the lab has one supported, tested home for the printed close — the price a
newspaper actually printed, recovered as `adjusted_close × Market.shares.raw_factor(symbol, d)` —
instead of two copies buried inside frozen pre-registrations. Both editable shared screens
(`f_factor.factor_rows`, `f_fundamental.fundamental_rows`) can be asked to read the five-dollar
floor on that basis through a keyword-only argument whose default reproduces today's behaviour
byte for byte, so no recorded `config_digest`, no pinned candidate digest and no live paper spec
moves. The four frozen comparison sites are left untouched and recorded in a documentation note
that names the one legal route to repairing them.

### What this phase deliberately does not do

It does not change what any existing method, backtest, paper night or roster book computes. The
repair arrives as a reachable option, not a new default. Making it the default is a question for
a future method — see **Handoffs**.

---

## Interface Contract

**Creates:**
- module `seer_engine.strategies.price_floor` (`engine/src/seer_engine/strategies/price_floor.py`)
- `price_floor.MIN_PRICE` (float, `5.0`)
- `price_floor.BASES` (`("adjusted", "printed", "none")`)
- `price_floor.ADJUSTED`, `price_floor.PRINTED`, `price_floor.NONE` (str constants)
- `price_floor.PrintedBasisUnavailable` (subclass of `ValueError`)
- `price_floor.check_basis(basis) -> str`
- `price_floor.market_can_print(market) -> bool`
- `price_floor.check_market(market, basis) -> str`
- `price_floor.raw_factor(market, symbol, data_date) -> float`
- `price_floor.printed_close(h, market, symbol, data_date) -> float | None`
- `price_floor.floor_value(adjusted, factor, basis) -> float`
- `price_floor.passes_floor(h, market, symbol, data_date, basis, min_price=MIN_PRICE) -> bool`
- `price_floor.floor_closes(adjusted, market, symbols, data_date, basis) -> np.ndarray`
- test module `engine/tests/test_price_floor.py`
- `docs/lab/price-floor.md`

**Signature changes (all additive, all keyword-only, all defaulting to today's behaviour):**
- `f_factor._eligible_mask(close, mom, vol, dv, params)` -> `f_factor._eligible_mask(close, mom, vol, dv, params, *, floor_close=None)` (`f_factor.py:179`)
- `f_factor.factor_rows(history, members, data_date, params)` -> `f_factor.factor_rows(history, members, data_date, params, *, price_basis="adjusted", market=None)` (`f_factor.py:194`)
- `f_fundamental.fundamental_rows(history, panel, members, data_date, params)` -> `f_fundamental.fundamental_rows(history, panel, members, data_date, params, *, price_basis="adjusted", market=None)` (`f_fundamental.py:374`)

**Deletes:** none.
**Renames:** none.
**New dataclass fields:** **none.** `FactorParams` and `FundamentalParams` field lists are
untouched — this is the single hardest constraint in the phase and §Verification proves it.

**Two plan-set invariants this phase must not break** (index §Invariants 8 and 9, cross-referenced
in phase 3):

- **I8 — `factor_rows`'s default stays `price_basis="adjusted"`, in every phase.** Phase 3's ten
  amendment arms are retrofits: an `Amendment` asks one more question of an idea *under the same
  conditions as its recorded arms*. Four of the ten (`M0260-ALWAYS`, `M0261-ALWAYS`,
  `M0262-ALWAYS`, `M0334-ALWAYS`) reach `factor_rows`, so if this phase ever moved the default the
  pool would shift under them and phase 3's whole retrofit would be void — its new arms would be
  scored on a different universe from the arms they exist to be subtracted from. Phase 3 raised
  this as a risk against phase 1; this contract is the guarantee that answers it, so it is promoted
  to a plan-set invariant rather than left as one phase's worry.
- **I9 — no params dataclass may gain a field, in any phase.** `backtest/registry.py:323` applies
  the pinned-default drop-out to `TradeRules` **only**, so a new `compare=True` field on any
  allocator params dataclass moves every recorded `config_digest` that embeds it. Phases 1 and 3
  discovered this independently; phase 2 is the single exception, and relies on exactly the
  `TradeRules` carve-out that `registry.py:323` names.

**Requires (from earlier phases):** nothing. This phase depends on no other phase and may run
concurrently with phases 2 and 3.

**Leaves alone (owned by others, or frozen):**
- `engine/src/seer_engine/lab/methods/**` — every file. Phase 3 owns ten of them; the six
  named in the analysis are frozen pre-registrations and this phase does not edit a byte of any
  method file. The new test module *imports from* `m0383` and `m0387`; importing is not editing.
- `engine/src/seer_engine/sim/**` — phase 2.
- `engine/src/seer_engine/paper/**`, `web/`, `db/migrations/`, `lab/lab.sqlite`,
  `web/data/lab.json` — no phase in this set writes them, and this one does not read
  `lab.sqlite` except through `mode=ro`.
- `engine/src/seer_engine/strategies/__init__.py` — **not** edited. `f_factor` and
  `f_fundamental` are not re-exported there either; adding `price_floor` would be scope creep
  and would change the package's import surface for no caller.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/strategies/price_floor.py` | create | the whole module: the printed close, the three-rung dial, the refusal |
| `engine/src/seer_engine/strategies/f_factor.py` | modify | one import line at `:47`; `_eligible_mask` at `:179`; `factor_rows` signature at `:194`, body at `:202-204` and `:226-227` |
| `engine/src/seer_engine/strategies/f_fundamental.py` | modify | one import line after `:100`; `fundamental_rows` signature at `:374`, body at `:387-390` and the floor comparison at `:403` |
| `engine/tests/test_price_floor.py` | create | the five real-world closes, agreement with both frozen copies, the refusal, and the default-path no-op proofs |
| `docs/lab/price-floor.md` | create | the four frozen sites, the three delegating modules, why none is edited, and the one legal route |

Five files. No other file in the tree is touched.

---

## Implementation Steps

### Step 1: The new module

**File:** `engine/src/seer_engine/strategies/price_floor.py` (new file)
**Change:** The canonical home for what `m0383.printed_close` and `m0387.passes_floor` prove
works, plus the two things a shared screen needs and a method file did not: a vector path, and a
refusal in place of the silent collapse.

**Decision recorded here, as the task required.** `Market.shares` is `EMPTY_SHARES` on the paper
night (`paper/store.py:1523` builds the night's `Market` with history, membership, fx and
fundamentals and no shares), so `raw_factor` answers `1.0` for every symbol and a printed-basis
screen would degrade back to the adjusted basis with no error (insights 778, 779). **The helper
makes that visible by refusing it.** `check_market(market, basis)` raises
`PrintedBasisUnavailable` when `basis == "printed"` and the market cannot answer
(`market is None`, no `shares`, or `shares.has_splits()` is False — `backtest/market.py:468`).
Both shared screens call it **once per call, before the loop**, so the cost is one check per
decision date and the error names the day, not a symbol. The scalar helpers
(`printed_close`, `passes_floor`) deliberately do **not** raise: they reproduce the frozen
arithmetic exactly so the agreement test can pin them against `m0383`/`m0387` character for
character in behaviour. The refusal lives at the entry points, where the frozen files have no
equivalent to drift from. The module docstring also records the other half of the mechanism,
which is not this module's to enforce: an allocator built on the printed basis must declare
`market_fields = ("shares",)`, which is what makes `lab run` refuse it on a research store with
no `splits.csv` — the same problem seen from the store side, and the lab's existing answer to it.

**Code:**

```python
"""The five-dollar price floor, and which close it is compared against.

Every stock screen in this lab asks whether a member's close is at least five dollars -- the
conventional penny-stock line, ``FactorParams.min_price``. The close it reads is the research
store's, and the store's closes are back-adjusted for every split the vendor applied since. So
the floor has never asked "did this share trade above five dollars"; it has asked "did this
share trade above five dollars *after* dividing by every split between then and now". A company
that split often reads far cheaper in the old years than it ever traded, and the companies that
split often are the companies that went up: the floor removes exactly the names a momentum book
is built to hold. M0383 measured the hole on the dev store over the 238 month-ends from
1996-01-31 to 2015-10-16 -- 1293 of 62923 member-months, 2.05%, across 40 companies, led by
Nvidia at 168 month-ends, Apple at 149, KLA at 137 and CSX at 132 -- and M0387 priced repairing
it.

**Why this module exists.** The arithmetic that recovers the printed close was written, verified
and committed inside two lab method files (``m0383_nominal_price_level_tilt.printed_close`` and
``m0387_printed_price_floor_repair.passes_floor``). Those files are pre-registrations: once the
lab has run them they are frozen to a recorded ``source_sha`` and may never be edited. The lab's
one verified printed-price helper therefore lived somewhere no supported code may change, and a
screen that wanted it had to import out of a frozen pre-registration. This module is that
helper's real home. It reproduces the frozen arithmetic exactly -- ``test_price_floor.py`` pins
the agreement, so the frozen copies cannot drift away from this one -- and adds only what a
shared, supported screen needs: a basis check, a vector path, and a refusal.

**The three rungs**, as M0387 pre-registered them. ``"adjusted"`` compares the stored,
back-adjusted close, which is what every screen in this lab does today and stays the default
everywhere. ``"printed"`` compares the close as it printed -- the stored close times every split
applied after that day -- which is the repair. ``"none"`` asks nothing, the far rung that bounds
what the floor costs in total. They are three rungs of one dial rather than three ideas: a
forward split makes ``raw_factor`` at least 1, so a printed close is at or above the adjusted
one and the pools nest, and only a reverse split can flip that.

**The caveat this module refuses to keep silent.** The printed close is
``close * Market.shares.raw_factor(symbol, d)``, and ``raw_factor`` answers 1.0 for every symbol
when the market carries no splits. The paper night builds its ``Market`` from history,
membership, fx and fundamentals and *no shares* (``paper/store.py``), so ``Market.shares`` is
``EMPTY_SHARES`` there: a printed-basis screen would degrade back to the adjusted basis with no
error and no warning, and the repair would be live, measured, and not actually running
(insights 778, 779). Supplying share counts to the paper night is a table, a migration, a loader
and a nightly job, and it is not built. So the silence is turned into a refusal here instead:
:func:`check_market` raises when a caller asks for the printed basis on a market that cannot
answer, and both shared screens call it once before their loop rather than once per symbol, so
the error names the decision date rather than whichever ticker happened to be first. An
allocator built on this must *also* declare ``market_fields = ("shares",)``, which is the lab's
existing mechanism for the same problem seen from the store side -- it makes ``lab run`` refuse
the allocator on a research store with no ``splits.csv`` rather than quietly scoring the wrong
basis. Neither check can be inferred from the other, so both are named here.

**What the basis never decides.** Which close a target is *priced* at. The basis moves the pool
and nothing else: ``FactorRow.close`` and ``FundamentalRow.close`` stay the store's close, which
is the number the book engine trades and the number every recorded trial was scored on. A
printed number in a row's ``close`` would price every order at a price that has not existed
since the split.

Pure: reads only bars and splits dated on or before ``data_date``. ``raw_factor`` is a property
of the store's own adjustment of the past, not a forecast -- it says what a newspaper printed
that morning, not what the stock did afterwards.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date
from typing import Any

import numpy as np

from seer_engine.strategies.base import History

MIN_PRICE = 5.0
"""The conventional penny-stock line, and ``FactorParams.min_price``'s own default.

Not a dial this module introduces: 5.0 is the number the shared screens already default to and
the number ``m0387.MIN_PRICE`` holds. What this module changes is only which close it is
compared against."""

BASES: tuple[str, ...] = ("adjusted", "printed", "none")
"""The three rungs of the floor dial, in M0387's own order and spelling."""

ADJUSTED, PRINTED, NONE = BASES


class PrintedBasisUnavailable(ValueError):
    """The printed basis was asked for on a market that cannot supply splits.

    The failure this exists to prevent is not a crash, it is a silence: ``raw_factor`` answers
    1.0 for every symbol on a market with no splits, so the printed basis would collapse into
    the adjusted one and nothing would say so.
    """


def check_basis(basis: object) -> str:
    """``basis`` as one of :data:`BASES`, or an error naming what was asked for."""
    if not isinstance(basis, str):
        raise TypeError(f"price_basis must be a str, got {type(basis).__name__}")
    if basis not in BASES:
        raise ValueError(f"price_basis must be one of {BASES}, got {basis!r}")
    return basis


def market_can_print(market: Any) -> bool:
    """Can ``market`` answer a printed close at all -- does it carry any splits?

    Duck-typed on purpose: the history-only allocator path passes None, the lab passes a
    ``Market``, and a test passes anything with a ``shares``. Nothing here imports
    ``backtest.market``, which keeps ``strategies`` free of a dependency it does not otherwise
    have.
    """
    if market is None:
        return False
    shares = getattr(market, "shares", None)
    if shares is None:
        return False
    has = getattr(shares, "has_splits", None)
    return bool(has()) if callable(has) else False


def check_market(market: Any, basis: str) -> str:
    """``basis``, refusing ``"printed"`` on a market that would silently answer the adjusted one.

    Called once per screen call, before the loop, so the cost is one check per decision date and
    the error names the day it happened on rather than the first symbol it reached.
    """
    basis = check_basis(basis)
    if basis == PRINTED and not market_can_print(market):
        raise PrintedBasisUnavailable(
            "the printed price basis needs a market carrying splits, and this one has none "
            "(Market.shares is EMPTY_SHARES, so raw_factor answers 1.0 for every symbol and the "
            "printed floor would silently become the adjusted floor). Load a research store with "
            'a splits.csv, and declare market_fields = ("shares",) on the allocator'
        )
    return basis


def raw_factor(market: Any, symbol: str, data_date: date) -> float:
    """What ``symbol``'s stored close on ``data_date`` is multiplied by to give the printed price.

    ``ShareCounts.raw_factor``: the product of every split the vendor applied after that day,
    strictly after -- the ex-date's own bar is already adjusted. 1.0 when the market carries no
    splits for the symbol.
    """
    return float(market.shares.raw_factor(symbol, data_date))


def printed_close(h: History, market: Any, symbol: str, data_date: date) -> float | None:
    """The close as it printed on ``data_date``: the stored, split-adjusted close multiplied by
    every split the vendor applied after that day (``ShareCounts.raw_factor``).

    None when there is no bar dated ``data_date`` or the read is not finite and positive. Reads
    nothing dated after ``data_date``. This is ``m0383.printed_close``, verified against five
    known real-world closes before it was committed and reproduced here; ``test_price_floor.py``
    pins the two against each other so the frozen copy cannot drift away from this one.
    """
    i = h.index_of(data_date)
    if i is None:
        return None
    adj = float(h.close[i])
    if not (adj > 0.0 and adj == adj and adj != float("inf")):
        return None
    return adj * raw_factor(market, symbol, data_date)


def floor_value(adjusted: float, factor: float, basis: str) -> float:
    """The number the floor is compared against, from one adjusted close and one split factor.

    ``"adjusted"`` -> the close itself; ``"printed"`` -> close x factor; ``"none"`` -> infinity,
    which clears any finite floor and so is "ask nothing" without a second code path. The one
    piece of arithmetic both the scalar and the vector path go through.
    """
    if basis == ADJUSTED:
        return adjusted
    if basis == NONE:
        return math.inf
    return adjusted * factor


def passes_floor(
    h: History, market: Any, symbol: str, data_date: date, basis: str, min_price: float = MIN_PRICE
) -> bool:
    """Does ``symbol`` clear the price floor on ``data_date`` under ``basis``?

    ``"none"`` asks nothing. ``"adjusted"`` compares the store's back-adjusted close, which is
    what every screen in this lab does today. ``"printed"`` compares the close as it printed,
    which is the repair. False when the symbol has no bar dated ``data_date`` or the close is
    not finite. This is ``m0387.passes_floor`` with the floor made an argument instead of a
    module constant, defaulted to the same number; ``test_price_floor.py`` pins the two against
    each other across the three bases and across the floor itself.
    """
    if basis == NONE:
        return True
    i = h.index_of(data_date)
    if i is None:
        return False
    adj = float(h.close[i])
    if not math.isfinite(adj):
        return False
    if basis == ADJUSTED:
        return adj >= min_price
    p = printed_close(h, market, symbol, data_date)
    return p is not None and p >= min_price


def floor_closes(
    adjusted: np.ndarray, market: Any, symbols: Sequence[str], data_date: date, basis: str
) -> np.ndarray:
    """The floor price for each of ``symbols``, aligned with ``adjusted`` (the vector path).

    ``adjusted`` is one stored close per symbol, in the same order. Returns ``adjusted`` itself
    under ``"adjusted"`` -- the same object, no copy and no arithmetic, so the default path is
    exactly what it was before this argument existed -- an all-infinity array under ``"none"``,
    and close x raw_factor under ``"printed"``. ``raw_factor`` is always finite and positive
    (``ShareCounts`` validates every ratio on construction), so the printed array is finite
    wherever ``adjusted`` is and ``_eligible_mask``'s existing ``np.isfinite(close)`` term still
    carries the whole finiteness check.
    """
    if basis == ADJUSTED:
        return adjusted
    if basis == NONE:
        return np.full(adjusted.shape, np.inf, dtype=np.float64)
    factors = np.array([raw_factor(market, s, data_date) for s in symbols], dtype=np.float64)
    return adjusted * factors
```

**Impact:** a new pure module. `tests/test_strategy_purity.py` globs
`seer_engine/strategies/*.py`, so it is covered automatically with no edit to that file — and
the module imports nothing from `time`, `random`, `logging`, `urllib` or `socket` and calls no
`print`, `open` or `input`, which is what that test checks. Verified green in this session.

---

### Step 2: `f_factor` — the import

**File:** `engine/src/seer_engine/strategies/f_factor.py:47`
**Change:** one new import line, immediately before the existing `indicators` import.

**Before (`:43-54`):**

```python
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, equal_weight, to_weight
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.indicators import (
    mean_dollar_volume_window,
    return_window,
    rolling,
    sma_window,
    stdev_return_window,
)
```

**After:**

```python
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, equal_weight, to_weight
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.indicators import (
    mean_dollar_volume_window,
    return_window,
    rolling,
    sma_window,
    stdev_return_window,
)
from seer_engine.strategies.price_floor import ADJUSTED, check_market, floor_closes
```

**Impact:** `f_factor` already imports `Any` from `typing` (`:40`), so the `market: Any`
annotation in Step 4 needs no further import. No import cycle: `price_floor` imports only
`strategies.base`, which `f_factor` already imports.

---

### Step 3: `f_factor._eligible_mask`

**File:** `engine/src/seer_engine/strategies/f_factor.py:179-192`
**Change:** one keyword-only argument. The returned expression is the same expression; only the
final comparison's left operand becomes a name that defaults to `close`.

**Before:**

```python
def _eligible_mask(
    close: np.ndarray, mom: np.ndarray, vol: np.ndarray, dv: np.ndarray, params: FactorParams
) -> np.ndarray:
    """The feature part of eligibility, shared verbatim by both paths."""
    return (
        np.isfinite(close)
        & np.isfinite(mom)
        & np.isfinite(vol)
        & np.isfinite(dv)
        & (vol > 0.0)
        & (dv > params.min_dollar_volume)
        & (close >= params.min_price)
    )
```

**After:**

```python
def _eligible_mask(
    close: np.ndarray,
    mom: np.ndarray,
    vol: np.ndarray,
    dv: np.ndarray,
    params: FactorParams,
    *,
    floor_close: np.ndarray | None = None,
) -> np.ndarray:
    """The feature part of eligibility, shared verbatim by both paths.

    ``floor_close`` is the price the five-dollar floor is compared against, one per symbol,
    aligned with ``close``. None -- the default, and every caller that does not ask -- means the
    floor reads ``close`` itself, the store's back-adjusted close, which is what this screen has
    always done. ``strategies.price_floor.floor_closes`` builds the other two bases, and returns
    ``close`` unchanged for the adjusted one, so the default path runs the identical expression
    over the identical array.
    """
    floor = close if floor_close is None else floor_close
    return (
        np.isfinite(close)
        & np.isfinite(mom)
        & np.isfinite(vol)
        & np.isfinite(dv)
        & (vol > 0.0)
        & (dv > params.min_dollar_volume)
        & (floor >= params.min_price)
    )
```

**Impact:** on the default path `floor is close`, so the expression is unchanged. No extra
`np.isfinite(floor)` term is added: `raw_factor` is finite and positive by construction, so
`isfinite(close * factor) == isfinite(close)` and the existing `np.isfinite(close)` already
carries it. A NaN floor would compare False, which is the right answer anyway.

---

### Step 4: `f_factor.factor_rows`

**File:** `engine/src/seer_engine/strategies/f_factor.py:194-232`
**Change:** two keyword-only arguments, one `check_market` call before the loop, and one
`floor_close=` argument at the mask call.

**Before (whole function):**

```python
def factor_rows(
    history: Mapping[str, History], members: Set[str], data_date: date, params: FactorParams
) -> list[FactorRow]:
    """Eligible members' features on ``data_date``, sorted by symbol (the single-window path).

    Reads each member's last ``factor_lookback(params)`` bars ending at ``data_date``; later bars
    are never read.
    """
    _check_params(params)
    as_day(data_date)
    lb = factor_lookback(params)
    symbols: list[str] = []
    ends: list[int] = []
    for symbol in sorted(members):
        if symbol in EXCLUDED:
            continue
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i + 1 < lb:
            continue
        symbols.append(symbol)
        ends.append(i + 1)
    if not symbols:
        return []
    close = np.stack([history[s].close[e - lb : e] for s, e in zip(symbols, ends, strict=True)])
    volume = np.stack([history[s].volume[e - lb : e] for s, e in zip(symbols, ends, strict=True)])
    with np.errstate(divide="ignore", invalid="ignore"):
        mom = return_window(close, params.mom_n, params.mom_skip)
        vol = stdev_return_window(close, params.vol_n)
        dv = mean_dollar_volume_window(close, volume, DV_N)
    last = close[:, -1]
    mask = _eligible_mask(last, mom, vol, dv, params)
    return [
        FactorRow(symbols[k], float(last[k]), float(mom[k]), float(vol[k]), float(dv[k]))
        for k in (int(j) for j in np.flatnonzero(mask))
    ]
```

**After (whole function):**

```python
def factor_rows(
    history: Mapping[str, History],
    members: Set[str],
    data_date: date,
    params: FactorParams,
    *,
    price_basis: str = ADJUSTED,
    market: Any = None,
) -> list[FactorRow]:
    """Eligible members' features on ``data_date``, sorted by symbol (the single-window path).

    Reads each member's last ``factor_lookback(params)`` bars ending at ``data_date``; later bars
    are never read.

    ``price_basis`` chooses which close the ``min_price`` floor is compared against -- one of
    ``price_floor.BASES``. It defaults to ``"adjusted"``, the store's back-adjusted close, which
    is what this screen has always compared and what every recorded trial was scored on; at that
    default the function is byte-for-byte the function it was before the argument existed. Ask
    for ``"printed"`` and the floor reads the price that actually printed
    (``close x Market.shares.raw_factor``), which needs ``market`` to carry splits and raises
    ``price_floor.PrintedBasisUnavailable`` if it does not -- see that module for why this is a
    refusal rather than a fallback. ``"none"`` asks nothing.

    A keyword argument and not a ``FactorParams`` field, deliberately: ``registry._canon``
    enumerates every ``compare=True`` dataclass field and drops pinned defaults for ``TradeRules``
    only, so one new field here would move every recorded ``config_digest`` that embeds a
    ``FactorParams``. An argument is invisible to the digest. A method that wants the repaired
    basis as part of its pre-registration spells it in its own params, as M0387 does.

    The basis moves the pool and nothing else. ``FactorRow.close`` stays the stored close: it is
    what ``targets_from_rows`` prices a target at and what the book engine trades.
    """
    _check_params(params)
    as_day(data_date)
    basis = check_market(market, price_basis)
    lb = factor_lookback(params)
    symbols: list[str] = []
    ends: list[int] = []
    for symbol in sorted(members):
        if symbol in EXCLUDED:
            continue
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i + 1 < lb:
            continue
        symbols.append(symbol)
        ends.append(i + 1)
    if not symbols:
        return []
    close = np.stack([history[s].close[e - lb : e] for s, e in zip(symbols, ends, strict=True)])
    volume = np.stack([history[s].volume[e - lb : e] for s, e in zip(symbols, ends, strict=True)])
    with np.errstate(divide="ignore", invalid="ignore"):
        mom = return_window(close, params.mom_n, params.mom_skip)
        vol = stdev_return_window(close, params.vol_n)
        dv = mean_dollar_volume_window(close, volume, DV_N)
    last = close[:, -1]
    mask = _eligible_mask(
        last, mom, vol, dv, params, floor_close=floor_closes(last, market, symbols, data_date, basis)
    )
    return [
        FactorRow(symbols[k], float(last[k]), float(mom[k]), float(vol[k]), float(dv[k]))
        for k in (int(j) for j in np.flatnonzero(mask))
    ]
```

**Impact:** 119 method files call `factor_rows` directly and 186 of the 243 method files import
something from `f_factor` (both re-measured in this session with
`grep -rln` over `engine/src/seer_engine/lab/methods/`; the analysis's "192" used a wider
pattern). Not one of them passes `price_basis`, so not one of them sees a different pool:
`check_market(None, "adjusted")` returns `"adjusted"` without touching the market, and
`floor_closes(last, None, symbols, d, "adjusted")` returns `last` itself. The other named
caller, `prepare_factor`'s prepared path, is unchanged and still reaches `_eligible_mask`
without a `floor_close`, so the P4 identity (`assert_p4_identity` in `test_f_factor.py`) holds.

---

### Step 5: `f_fundamental` — the import

**File:** `engine/src/seer_engine/strategies/f_fundamental.py:100`
**Change:** one new import line after the existing `indicators` import.

**Before (`:96-100`):**

```python
from seer_engine.fundamentals import EMPTY_PANEL
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, equal_weight, to_weight
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.indicators import mean_dollar_volume_window, sma_window
```

**After:**

```python
from seer_engine.fundamentals import EMPTY_PANEL
from seer_engine.sim.book import WEIGHT_QUANTUM, Target, equal_weight, to_weight
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.indicators import mean_dollar_volume_window, sma_window
from seer_engine.strategies.price_floor import ADJUSTED, PRINTED, check_market, floor_value, raw_factor
```

**Impact:** `f_fundamental` already imports `Any` from `typing` (`:92`). No cycle.

---

### Step 6: `f_fundamental.fundamental_rows`

**File:** `engine/src/seer_engine/strategies/f_fundamental.py:374-418`
**Change:** two keyword-only arguments, one `check_market` call before the loop, and the floor
comparison at `:403` split into a finiteness check (unchanged) and a basis-aware floor check.

**Before (whole function):**

```python
def fundamental_rows(
    history: Mapping[str, History],
    panel: Panel,
    members: Set[str],
    data_date: date,
    params: FundamentalParams,
) -> list[FundamentalRow]:
    """Eligible members' features on ``data_date``, sorted by symbol (see the module docstring).

    Reads each member's last ``fundamental_lookback(params)`` bars ending at ``data_date`` and
    exactly one phase-5 snapshot per symbol, which answers from facts with
    ``filed <= data_date``; later bars and later filings are never read.
    """
    p = _check_params(params)
    as_day(data_date)
    panel = _panel(panel)
    lb = fundamental_lookback(p)
    wanted = factors_read(p)
    out: list[FundamentalRow] = []
    for symbol in sorted(members):
        if symbol in EXCLUDED:
            continue
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i + 1 < lb:
            continue
        close = float(h.close[i])
        if not math.isfinite(close) or close < p.min_price:
            continue
        dollar_volume = _dollar_volume(h, i)
        if not math.isfinite(dollar_volume) or not dollar_volume > p.min_dollar_volume:
            continue
        snap = panel.as_of(symbol, data_date)
        if snap is None:
            continue
        filed = snap.filed
        # filed > data_date would be a phase-5 bug, not a stale fact. Checked anyway: this is
        # the one assertion that stands between a look-ahead and a backtest that looks great.
        if filed is None or filed > data_date or (data_date - filed).days > p.max_stale_days:
            continue
        row = _row(symbol, close, dollar_volume, snap)
        if all(math.isfinite(getattr(row, name)) for name in wanted):
            out.append(row)
    return out
```

**After (whole function):**

```python
def fundamental_rows(
    history: Mapping[str, History],
    panel: Panel,
    members: Set[str],
    data_date: date,
    params: FundamentalParams,
    *,
    price_basis: str = ADJUSTED,
    market: Any = None,
) -> list[FundamentalRow]:
    """Eligible members' features on ``data_date``, sorted by symbol (see the module docstring).

    Reads each member's last ``fundamental_lookback(params)`` bars ending at ``data_date`` and
    exactly one phase-5 snapshot per symbol, which answers from facts with
    ``filed <= data_date``; later bars and later filings are never read.

    ``price_basis`` chooses which close the ``min_price`` floor is compared against -- one of
    ``price_floor.BASES``, defaulting to ``"adjusted"``, which is what this screen has always
    compared. See ``f_factor.factor_rows`` and ``strategies.price_floor`` for why this is a
    keyword argument and not a ``FundamentalParams`` field, and why ``"printed"`` refuses a
    market without splits rather than falling back to the adjusted basis.

    The basis moves the pool and nothing else: ``close`` is still the stored close everywhere
    below, including in ``_row``, where it is one half of ``market_cap``. Repairing that figure
    is a separate and much larger question (``Market.market_value`` is the repaired path) and
    this argument deliberately does not touch it.
    """
    p = _check_params(params)
    as_day(data_date)
    basis = check_market(market, price_basis)
    panel = _panel(panel)
    lb = fundamental_lookback(p)
    wanted = factors_read(p)
    out: list[FundamentalRow] = []
    for symbol in sorted(members):
        if symbol in EXCLUDED:
            continue
        h = history.get(symbol)
        if h is None:
            continue
        i = h.index_of(data_date)
        if i is None or i + 1 < lb:
            continue
        close = float(h.close[i])
        if not math.isfinite(close):
            continue
        factor = raw_factor(market, symbol, data_date) if basis == PRINTED else 1.0
        if floor_value(close, factor, basis) < p.min_price:
            continue
        dollar_volume = _dollar_volume(h, i)
        if not math.isfinite(dollar_volume) or not dollar_volume > p.min_dollar_volume:
            continue
        snap = panel.as_of(symbol, data_date)
        if snap is None:
            continue
        filed = snap.filed
        # filed > data_date would be a phase-5 bug, not a stale fact. Checked anyway: this is
        # the one assertion that stands between a look-ahead and a backtest that looks great.
        if filed is None or filed > data_date or (data_date - filed).days > p.max_stale_days:
            continue
        row = _row(symbol, close, dollar_volume, snap)
        if all(math.isfinite(getattr(row, name)) for name in wanted):
            out.append(row)
    return out
```

**Impact:** on the default path `basis == "adjusted"`, `factor` is never computed
(`raw_factor` is not called at all), and `floor_value(close, 1.0, "adjusted")` returns `close`,
so the comparison is `close < p.min_price` — the same test, now reached only after the
finiteness check that used to short-circuit it. `not math.isfinite(close) or close < p.min_price`
and `if not isfinite: continue` then `if close < min_price: continue` select the identical set.
`fundamental_rows` has exactly one non-test caller in the tree,
`strategies/evidence.py:644`, which does not pass a basis. Measured in this session.

---

### Step 7: The new test module

**File:** `engine/tests/test_price_floor.py` (new file)
**Change:** the whole file.

**Decision on the research store, as the task asked for it to be stated.** The five real-world
closes are checked **without reading any research store.** The splits are a fixture: a
`ShareCounts` built directly from four real split calendars, and the "stored" close in each case
is `printed / raw_factor`, which is exactly what a vendor's back-adjustment produces. All five
round-trip to the cent under exact float equality — verified in this session, not asserted from
memory:

```
AAPL 2014-06-06 factor=28.0 stored=23.056071428571432 -> 645.57  (exact)
AAPL 2014-06-10 factor=4.0  stored=23.5625            ->  94.25  (exact)
GOOGL 2015-10-15 factor=20.0 stored=34.650999999999996 -> 693.02 (exact)
AMZN 2015-10-15 factor=20.0 stored=28.122000000000003 -> 562.44  (exact)
KO   2000-01-14 factor=2.0  stored=30.53              ->  61.06  (exact)
```

So the test suite gains no dependency on `engine/.research` being present, and the test is a
pin on the *arithmetic and the boundary*, which is what M0383 was checking by hand. The AAPL
pair across its own 7:1 is the load-bearing case: two stored closes 2% apart that must produce
$645.57 and $94.25, which only works if the ex-date boundary is "strictly after `d`".

**Code:**

```python
"""The five-dollar floor's three bases (``strategies/price_floor.py``, R1).

The printed close, pinned against the five real-world closes M0383 checked by hand before it was
committed; the agreement between this module and the two frozen lab copies it was lifted from;
the refusal that stops the printed basis collapsing silently on a market with no splits; and the
proof that both shared screens behave exactly as they did when nobody asks for a basis.

**No research store is read.** The splits are a fixture -- a ``ShareCounts`` built from four real
split calendars -- and each stored close is the printed close divided by its own split factor,
which is exactly what a vendor's back-adjustment produces. So the suite does not depend on
``engine/.research`` being present, and the five closes are pinned by the store's own arithmetic
rather than by a file that may or may not be on this machine.
"""

from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass
from datetime import date

import numpy as np
import pytest
from stratkit import hist, session_days

from seer_engine.backtest.market import EMPTY_SHARES, ShareCounts
from seer_engine.lab.methods.m0383_nominal_price_level_tilt import (
    printed_close as m0383_printed_close,
)
from seer_engine.lab.methods.m0387_printed_price_floor_repair import (
    MIN_PRICE as M0387_MIN_PRICE,
)
from seer_engine.lab.methods.m0387_printed_price_floor_repair import (
    passes_floor as m0387_passes_floor,
)
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, _eligible_mask, factor_rows
from seer_engine.strategies.f_fundamental import FundamentalParams, fundamental_rows
from seer_engine.strategies.price_floor import (
    ADJUSTED,
    BASES,
    MIN_PRICE,
    NONE,
    PRINTED,
    PrintedBasisUnavailable,
    check_basis,
    check_market,
    floor_closes,
    floor_value,
    market_can_print,
    passes_floor,
    printed_close,
    raw_factor,
)


class FakeMarket:
    """Everything ``price_floor`` reads of a ``Market``: its ``shares``, and nothing else."""

    def __init__(self, shares: ShareCounts) -> None:
        self.shares = shares


# ``ShareCounts`` takes ``{symbol: ((ex_date, ratio), ...), after_window_factor)}`` and
# ``raw_factor(s, d)`` is the after-window factor times every in-window split dated strictly
# after ``d``. These four calendars are real: Apple's 2:1 in 2005 and 7:1 in 2014 with its 2020
# 4:1 outside a dev-length window; Alphabet's and Amazon's 2022 20:1s, both outside it; and
# Coca-Cola's 2012 2:1 inside it.
SPLITS: dict[str, tuple[tuple[tuple[date, float], ...], float]] = {
    "AAPL": (((date(2005, 2, 28), 2.0), (date(2014, 6, 9), 7.0)), 4.0),
    "GOOGL": ((), 20.0),
    "AMZN": (((date(1999, 9, 2), 2.0),), 20.0),
    "KO": (((date(2012, 8, 13), 2.0),), 1.0),
}

# (symbol, day, the close the store holds, the close that printed). The right-hand numbers are
# the five real-world closes M0383's docstring names; each stored close is that number divided
# by its own ``raw_factor``, which is what a back-adjustment produces.
REAL_CLOSES: tuple[tuple[str, date, float, float], ...] = (
    ("AAPL", date(2014, 6, 6), 23.056071428571432, 645.57),  # the Friday before the 7:1
    ("AAPL", date(2014, 6, 10), 23.5625, 94.25),  # the Tuesday after it
    ("GOOGL", date(2015, 10, 15), 34.650999999999996, 693.02),
    ("AMZN", date(2015, 10, 15), 28.122000000000003, 562.44),
    ("KO", date(2000, 1, 14), 30.53, 61.06),
)


@pytest.fixture(scope="module")
def market() -> FakeMarket:
    return FakeMarket(ShareCounts({}, SPLITS))


@pytest.fixture(scope="module")
def blind() -> FakeMarket:
    """A market built the way the paper night builds one: no shares, so no splits."""
    return FakeMarket(EMPTY_SHARES)


def one_bar(symbol: str, day: date, close: float) -> History:
    """A one-bar history, which is all the scalar helpers read."""
    c = np.array([close], dtype=np.float64)
    return History(
        symbol,
        np.array([day], dtype="datetime64[D]"),
        c.copy(),
        c.copy(),
        c.copy(),
        c.copy(),
        np.array([1_000_000.0], dtype=np.float64),
    )


# --------------------------------------------------------------------------- the printed close


@pytest.mark.parametrize(("symbol", "day", "stored", "printed"), REAL_CLOSES)
def test_the_printed_close_is_the_close_that_printed(market, symbol, day, stored, printed):
    """The five real-world closes M0383 verified by hand before it was committed, pinned.

    AAPL across its own 7:1 is the load-bearing pair: $645.57 the Friday before and $94.25 the
    Tuesday after, from two stored closes that differ by 2%. A repair that got the direction or
    the ex-date boundary wrong would pass one and fail the other.
    """
    h = one_bar(symbol, day, stored)
    assert printed_close(h, market, symbol, day) == printed


def test_the_boundary_is_the_split_day_itself(market):
    """``raw_factor`` counts splits dated strictly after ``d``: the ex-date's bar is adjusted."""
    assert raw_factor(market, "AAPL", date(2014, 6, 6)) == 28.0  # the 7:1 x the 4:1 after
    assert raw_factor(market, "AAPL", date(2014, 6, 9)) == 4.0  # the ex-date is not after itself
    assert raw_factor(market, "AAPL", date(2014, 6, 10)) == 4.0


def test_no_bar_and_a_bad_close_answer_none(market):
    h = one_bar("KO", date(2000, 1, 14), 30.53)
    assert printed_close(h, market, "KO", date(2000, 1, 13)) is None
    nan = one_bar("KO", date(2000, 1, 14), float("nan"))
    assert printed_close(nan, market, "KO", date(2000, 1, 14)) is None
    zero = one_bar("KO", date(2000, 1, 14), 0.0)
    assert printed_close(zero, market, "KO", date(2000, 1, 14)) is None


# ------------------------------------------------------- agreement with the two frozen copies


@pytest.mark.parametrize(("symbol", "day", "stored", "printed"), REAL_CLOSES)
def test_this_module_agrees_with_m0383(market, symbol, day, stored, printed):
    """``m0383.printed_close`` is frozen to a recorded ``source_sha`` and may never be edited.

    This module is where that arithmetic is supported from now on, so the two must not drift. If
    this ever fails, the supported copy moved -- the frozen one cannot.
    """
    h = one_bar(symbol, day, stored)
    assert printed_close(h, market, symbol, day) == m0383_printed_close(h, market, symbol, day)


@pytest.mark.parametrize("basis", BASES)
@pytest.mark.parametrize(("symbol", "day", "stored", "printed"), REAL_CLOSES)
def test_this_module_agrees_with_m0387(market, basis, symbol, day, stored, printed):
    """The same freeze and the same reason, for the three-rung dial.

    ``m0387.passes_floor`` compares its own module constant; this module takes the floor as an
    argument and defaults it to the same number, so the two answer identically at the default.
    """
    assert MIN_PRICE == M0387_MIN_PRICE
    h = one_bar(symbol, day, stored)
    assert passes_floor(h, market, symbol, day, basis) == m0387_passes_floor(
        h, market, symbol, day, basis
    )


@pytest.mark.parametrize("stored", [4.0, 4.999, 5.0, 5.001, 50.0, float("nan")])
def test_agreement_holds_across_the_floor_itself(market, stored):
    """The agreement that matters is at the boundary, not on the easy numbers."""
    day, symbol = date(2000, 1, 14), "KO"
    h = one_bar(symbol, day, stored)
    for basis in BASES:
        assert passes_floor(h, market, symbol, day, basis) == m0387_passes_floor(
            h, market, symbol, day, basis
        )


# --------------------------------------------------------------- the silence, made into a refusal


def test_a_market_with_no_splits_cannot_print(blind, market):
    assert market_can_print(market) is True
    assert market_can_print(blind) is False
    assert market_can_print(None) is False


def test_the_frozen_helper_collapses_silently_and_this_one_refuses(blind):
    """The standing caveat, pinned as a test so it cannot be forgotten.

    On the paper night ``Market.shares`` is ``EMPTY_SHARES``, ``raw_factor`` answers 1.0 for
    every symbol, and the printed basis becomes the adjusted basis with no error (insights 778,
    779). The first assertion is that silence, demonstrated. Every entry point in the supported
    module refuses it instead.
    """
    day, stored = date(2014, 6, 6), 23.056071428571432
    h = one_bar("AAPL", day, stored)
    assert m0383_printed_close(h, blind, "AAPL", day) == stored  # silent, and wrong by 28x
    with pytest.raises(PrintedBasisUnavailable):
        check_market(blind, PRINTED)
    with pytest.raises(PrintedBasisUnavailable):
        check_market(None, PRINTED)
    assert check_market(blind, ADJUSTED) == ADJUSTED  # the default never needs a market
    assert check_market(None, NONE) == NONE


def test_a_bad_basis_is_named_not_guessed():
    for bad in ("Printed", "raw", "", "adjusted "):
        with pytest.raises(ValueError, match="price_basis"):
            check_basis(bad)
    with pytest.raises(TypeError):
        check_basis(None)


def test_floor_value_is_the_one_piece_of_arithmetic():
    assert floor_value(23.0, 28.0, ADJUSTED) == 23.0
    assert floor_value(23.0, 28.0, PRINTED) == 23.0 * 28.0
    assert floor_value(23.0, 28.0, NONE) == float("inf")


def test_the_vector_path_matches_the_scalar_one(market):
    day = date(2014, 6, 6)
    symbols = ["AAPL", "KO"]
    adjusted = np.array([23.056071428571432, 30.53], dtype=np.float64)
    assert floor_closes(adjusted, market, symbols, day, ADJUSTED) is adjusted
    assert list(floor_closes(adjusted, market, symbols, day, PRINTED)) == [645.57, 30.53]
    assert list(floor_closes(adjusted, market, symbols, day, NONE)) == [float("inf")] * 2


# ------------------------------------------------------------------- f_factor: the shared screen

# lookback 20 (the dollar-volume window): mom = c[-2]/c[-6] - 1, vol over 3 returns, no trend.
SCREEN = FactorParams(
    "momentum", top=5, mom_n=5, mom_skip=1, vol_n=3, trend=None, min_dollar_volume=0.0
)
BARS = 25


def wiggle(first: float) -> list[float]:
    """25 closes drifting up with an alternating wiggle, so volatility > 0 and momentum finite."""
    return [first * 1.001**t * (1.002 if t % 2 else 0.998) for t in range(BARS)]


@pytest.fixture(scope="module")
def days() -> list[date]:
    """25 sessions ending 2014-06-06 -- the Friday before Apple's 7:1, so the fixture's AAPL
    reads a ``raw_factor`` of 28 on its last bar, exactly as the real one does."""
    return session_days(BARS, date(2014, 5, 2))


@pytest.fixture(scope="module")
def screen_history(days) -> dict[str, History]:
    """AAPL reads $0.92 adjusted and $25.76 printed on the last bar; KO reads $61.33 either way.

    AAPL is the shape of the hole: a company whose stored close is under five dollars only
    because of splits the vendor applied years later.
    """
    return {
        "AAPL": hist("AAPL", wiggle(0.9), days=days, spread=0.01),
        "KO": hist("KO", wiggle(60.0), days=days, spread=0.01),
    }


def test_the_adjusted_basis_is_the_default_and_the_default_changed_nothing(
    screen_history, days, market
):
    """The whole point of the keyword argument: 119 method files call this function directly and
    not one of them passes a basis, so not one of them may see a different pool."""
    d = days[-1]
    members = frozenset({"AAPL", "KO"})
    plain = factor_rows(screen_history, members, d, SCREEN)
    explicit = factor_rows(screen_history, members, d, SCREEN, price_basis=ADJUSTED)
    with_market = factor_rows(
        screen_history, members, d, SCREEN, price_basis=ADJUSTED, market=market
    )
    assert plain == explicit == with_market
    assert [r.symbol for r in plain] == ["KO"]  # AAPL's stored close is under $5


def test_the_printed_basis_keeps_the_company_the_adjusted_floor_removed(
    screen_history, days, market
):
    d = days[-1]
    members = frozenset({"AAPL", "KO"})
    rows = factor_rows(screen_history, members, d, SCREEN, price_basis=PRINTED, market=market)
    assert [r.symbol for r in rows] == ["AAPL", "KO"]


def test_the_row_price_is_always_the_stored_close(screen_history, days, market):
    """The basis decides who is eligible. It never decides what a target is priced at: the book
    trades the store's close, and a printed number in ``FactorRow.close`` would price every
    order at a price that has not existed since the split."""
    d = days[-1]
    members = frozenset({"AAPL", "KO"})
    rows = {
        r.symbol: r
        for r in factor_rows(screen_history, members, d, SCREEN, price_basis=PRINTED, market=market)
    }
    assert rows["AAPL"].close == float(screen_history["AAPL"].close[-1])
    assert rows["AAPL"].close < MIN_PRICE


def test_the_none_basis_asks_nothing(screen_history, days):
    d = days[-1]
    members = frozenset({"AAPL", "KO"})
    rows = factor_rows(screen_history, members, d, SCREEN, price_basis=NONE)
    assert [r.symbol for r in rows] == ["AAPL", "KO"]


def test_factor_rows_refuses_a_printed_basis_without_splits(screen_history, days, blind):
    d = days[-1]
    members = frozenset({"AAPL", "KO"})
    with pytest.raises(PrintedBasisUnavailable):
        factor_rows(screen_history, members, d, SCREEN, price_basis=PRINTED, market=blind)
    with pytest.raises(PrintedBasisUnavailable):
        factor_rows(screen_history, members, d, SCREEN, price_basis=PRINTED)


def test_the_mask_default_is_the_close_itself():
    close = np.array([4.0, 6.0], dtype=np.float64)
    ones = np.array([1.0, 1.0], dtype=np.float64)
    params = FactorParams("momentum", min_dollar_volume=0.0)
    implicit = _eligible_mask(close, ones, ones, ones, params)
    explicit = _eligible_mask(close, ones, ones, ones, params, floor_close=close)
    assert list(implicit) == list(explicit) == [False, True]
    lifted = _eligible_mask(
        close, ones, ones, ones, params, floor_close=np.array([40.0, 60.0], dtype=np.float64)
    )
    assert list(lifted) == [True, True]


# ------------------------------------------------------------- f_fundamental: the same, inline


@dataclass(frozen=True, slots=True)
class FakeSnapshot:
    """The seven ``Snapshot`` members the allocator reads."""

    filed: date
    equity: float
    assets: float
    shares_outstanding: float
    net_income: float
    gross_profit: float
    sue: float


class FakePanel:
    """The one method ``f_fundamental.Panel`` needs, over a constant set of facts."""

    def __init__(self, filed: date) -> None:
        self.filed = filed

    def as_of(self, symbol: str, data_date: date) -> FakeSnapshot | None:
        if data_date < self.filed:
            return None
        return FakeSnapshot(self.filed, 1.0e9, 2.0e9, 1.0e8, 1.0e8, 5.0e8, 0.5)


FND = FundamentalParams("value", top=5, min_dollar_volume=0.0, max_stale_days=4000)


@pytest.fixture(scope="module")
def panel(days) -> FakePanel:
    return FakePanel(days[0])


def test_the_fundamental_screen_default_is_unchanged(screen_history, panel, days, market):
    d = days[-1]
    members = frozenset({"AAPL", "KO"})
    plain = fundamental_rows(screen_history, panel, members, d, FND)
    explicit = fundamental_rows(
        screen_history, panel, members, d, FND, price_basis=ADJUSTED, market=market
    )
    assert plain == explicit
    assert [r.symbol for r in plain] == ["KO"]


def test_the_fundamental_screen_keeps_the_splitter_under_the_printed_basis(
    screen_history, panel, days, market
):
    d = days[-1]
    members = frozenset({"AAPL", "KO"})
    rows = fundamental_rows(
        screen_history, panel, members, d, FND, price_basis=PRINTED, market=market
    )
    assert [r.symbol for r in rows] == ["AAPL", "KO"]
    assert {r.symbol: r.close for r in rows}["AAPL"] == float(screen_history["AAPL"].close[-1])


def test_the_fundamental_screen_refuses_a_printed_basis_without_splits(
    screen_history, panel, days, blind
):
    d = days[-1]
    members = frozenset({"AAPL", "KO"})
    with pytest.raises(PrintedBasisUnavailable):
        fundamental_rows(
            screen_history, panel, members, d, FND, price_basis=PRINTED, market=blind
        )


def test_the_fundamental_none_basis_asks_nothing(screen_history, panel, days):
    d = days[-1]
    members = frozenset({"AAPL", "KO"})
    rows = fundamental_rows(screen_history, panel, members, d, FND, price_basis=NONE)
    assert [r.symbol for r in rows] == ["AAPL", "KO"]


# ----------------------------------------------------------------- the frozen sites, as a list

FROZEN_SITES: tuple[tuple[str, int], ...] = (
    ("m0052_turn_of_month_tilt", 145),
    ("m0109_book_drawdown_brake", 213),
    ("m0117_index_tenure_exclusion", 200),
    ("m0276_cheap_financial_health", 294),
)


def test_the_frozen_sites_still_read_the_adjusted_close():
    """Sites 3-6 are pre-registrations and are deliberately NOT repaired (docs/lab/price-floor.md).

    This is the record that they were looked at and left alone: each file still holds its own
    comparison against its own module's close. If one of them ever starts importing the
    supported helper, somebody edited a frozen file, and this says so in the same breath as
    ``test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha``.
    """
    for module_name, _line in FROZEN_SITES:
        mod = importlib.import_module(f"seer_engine.lab.methods.{module_name}")
        source = inspect.getsource(mod)
        assert "min_price" in source or "MIN_PRICE" in source
        assert "price_floor" not in source, (
            f"{module_name} now imports the supported helper: a frozen pre-registration was edited"
        )
```

**Impact:** 49 tests, all verified passing in this session against the full patch. The module
does not read `engine/.research`, `lab/lab.sqlite`, Postgres or the network.

---

### Step 8: The documentation note

**File:** `docs/lab/price-floor.md` (new file)
**Change:** the whole file. `docs/lab/` already holds `prereg/`, `survivorship/` and
`universe/`; this is a top-level note beside them, which is the fitting place for a record about
the lab's own screens.

**Code:**

````markdown
# The five-dollar price floor: where it is repaired, and where it is frozen

**Written:** 2026-10-27, landing R1 of `FLOOR_RESERVATION_YARDSTICK_PLAN.md`.
**Measurement of record:** M0383 (the hole) and M0387 (the price of repairing it).

## The defect, in one paragraph

Every stock screen in this lab asks whether a member's close is at least five dollars. The close
it reads is the research store's, and the store's closes are back-adjusted for every split the
vendor applied since. So the floor has never asked "did this share trade above five dollars"; it
has asked "did this share trade above five dollars after dividing by every split between then
and now". A company that split often reads far cheaper in the old years than it ever traded, and
the companies that split often are the companies that went up. M0383 measured the hole on the dev
store over the 238 month-ends from 1996-01-31 to 2015-10-16: 1293 of 62923 member-months, 2.05%,
across 40 companies — Nvidia at 168 month-ends, Apple at 149, KLA at 137, CSX at 132, then
Aimco, TJX, Lam Research, Amphenol, Amazon, Netflix, O'Reilly, Broadcom, Starbucks, Monster and
Fastenal.

The repair is `close × Market.shares.raw_factor(symbol, d)`, the product of every split the
vendor applied after `d`. It became possible only when split dates reached the store on
2026-10-17/18.

## The six sites

| # | Site | Status |
|---|---|---|
| 1 | `strategies/f_factor.py` `_eligible_mask` | **repaired as an option** — `factor_rows(..., price_basis=...)`, default `"adjusted"` |
| 2 | `strategies/f_fundamental.py` the comparison in `fundamental_rows` | **repaired as an option** — same argument, same default |
| 3 | `lab/methods/m0052_turn_of_month_tilt.py:145` | **frozen** — `rejected`, `source_sha` `601cb089`, 5 trials |
| 4 | `lab/methods/m0109_book_drawdown_brake.py:213` | **frozen** — `rejected`, `source_sha` `95421df4`, 6 trials |
| 5 | `lab/methods/m0117_index_tenure_exclusion.py:200` | **frozen** — `rejected`, `source_sha` `7ea65e61`, 5 trials |
| 6 | `lab/methods/m0276_cheap_financial_health.py:294` (its own `MIN_PRICE = 5.0` at `:108`) | **frozen** — `rejected`, `source_sha` `e18ee7c9`, 5 trials |

Three more modules declare a `min_price` of their own and hand it to m0109's screen, and contain
no comparison at all: `m0119_deposit_deployment.py:147`, `m0127_slot_relative_resize_band.py:165`
and `m0266_exposure_matched_rebalance.py:214`. Each builds m0109's `BrakeParams` (`m0119:173`,
`m0127:192`, `m0266:247`) and inherits whatever site 4 does. They need no change, and
`grep -n "min_price" <file>` over all three shows a declaration, a validation, a digest key and
a hand-off, and no `<` or `>=` against a close.

## Why sites 3-6 are not repaired

All four are committed pre-registrations with a recorded `methods.source_sha` and a verdict.

1. `engine/tests/test_lab_methods.py::test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha`
   asserts each such file's sha256 equals `store.latest_source_sha`, and tolerates a mismatch on
   exactly one condition: a committed, unrecorded `Amendment` that `runner.pending_amendment`
   resolves. A floor repair is not an amendment. Any byte change turns the test red.
2. Worse than red: a repair there would silently change what those methods' **recorded** arms do
   while their `config_digest` stayed byte-identical, because the digest canonicalizes params and
   rules, not the file. That is precisely the thing the freeze exists to stop. The rejected
   verdicts in `lab.sqlite` would then describe a book nothing in the tree can reproduce.

## The one legal route

A **new variation method** that inherits the repaired shared screen, or an **`Amendment`** on one
of the four, pre-registered by the commit that writes it and run with `lab run --amend MNNNN`.
Either way the arms are declared before they run and the old rows keep describing the old book.
Which of the two, and whether it is worth a method id at all, is a future decision and was not
taken by this phase.

## Why the default did not move

`factor_rows` is reached by 186 of the 243 method files and called directly by 119 of them
(re-measured 2026-10-27 with `grep -rln` over `engine/src/seer_engine/lab/methods/`). An
amendment exists to ask one more question of an idea *under the same conditions as its recorded
arms*. Moving the pool under `factor_rows` would make every future amendment arm of every
recorded method incomparable with the arms it was written to be measured against. The repair is
therefore landed as a reachable, tested option and the default stays `"adjusted"`.

Nor could the basis become a `FactorParams` or `FundamentalParams` field.
`lab.method.config_text` canonicalizes `c.params` through `backtest.registry._canon`, which
enumerates every `compare=True` dataclass field; the pinned-default drop-out is applied to
`TradeRules` only (`registry.py:323`). A new field would move every recorded `config_digest` that
embeds one. A plain keyword argument is invisible to `_canon`.

## The standing blocker on ever running it live

The printed close needs `Market.shares`. The paper night builds its `Market` with history,
membership, fx and fundamentals and **no shares** (`paper/store.py:1523`), so `shares` is
`EMPTY_SHARES` and `raw_factor` answers 1.0 for every symbol. A printed-basis screen would
degrade back to the adjusted basis live, with no error (insights 778, 779). Supplying share
counts to the paper night is a table, a migration, a loader and a nightly job, and it is not
built.

Two guards stand in for it until it is:

- `strategies/price_floor.check_market` raises `PrintedBasisUnavailable` when the printed basis
  is asked for on a market with no splits. Both shared screens call it once before their loop.
- An allocator reading the printed basis must declare `market_fields = ("shares",)`, which makes
  `lab run` refuse it on a research store with no `splits.csv`.

Neither implies the other, so both are required.
````

**Impact:** documentation only.

---

## Verification

### The worktree's venv, and Postgres

**The worktree venv is built and working** — re-verified 2026-10-27 by the reconciler:
`engine/.venv/bin/python` is **CPython 3.12.7**, numpy 2.5.4, pytest 9.1.1, and
`import seer_engine` succeeds. An earlier draft of this plan carried a risk saying the venv was
empty and `import numpy` failed; that was true when it was looked at and has since been repaired,
so the risk is **retired**. Confirm in one line, and only rebuild if it fails:

```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
engine/.venv/bin/python -c "import numpy, pytest, seer_engine; print('venv ok')" \
  || (python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]')
```

**`python3.11` does not exist on this machine.** `CLAUDE.md` says `python3.11 -m venv`; the real
interpreter is `python3` → CPython 3.12.7 from `/home/miftah/miniconda3/bin`, which is also what
the main checkout's venv runs. Use `python3`.

**Postgres must be up before any pytest run in this phase.** `PG_TEST_URL` is **not** exported by
default in this shell, and the `seer-pg` container had been stopped for 26 hours before this plan
set started. CI fails if the DB tests skip, so a silent local skip is a failure that reaches CI.
Every pytest invocation below assumes these two lines have been run in the same shell:

```bash
docker start seer-pg 2>/dev/null \
  || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
docker ps --filter name=seer-pg --format '{{.Names}} {{.Status}}'   # must print "seer-pg Up ..."
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
```

**Build / import:**

```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
PYTHONPATH=engine/src engine/.venv/bin/python -c \
  "import seer_engine.strategies.price_floor, seer_engine.strategies.f_factor, seer_engine.strategies.f_fundamental; print('ok')"
```

**Lint** (CI lint is bugs only — E9 and F, minus F401 — configured in `engine/pyproject.toml`):

```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
engine/.venv/bin/ruff check engine
```

**The focused tests:**

```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
PYTHONPATH=engine/src engine/.venv/bin/python -m pytest \
  engine/tests/test_price_floor.py \
  engine/tests/test_f_factor.py \
  engine/tests/test_f_fundamental.py \
  engine/tests/test_strategy_purity.py \
  engine/tests/test_evidence.py \
  -n0
```

**The full suite:**

```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
docker start seer-pg 2>/dev/null || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
PYTHONPATH=engine/src engine/.venv/bin/python -m pytest engine/tests -n auto
```

CI fails if the DB tests skip, so check `docker ps --filter name=seer-pg` prints `Up` before
reading this run as green: an unexported `PG_TEST_URL` or a stopped container turns a real
failure into a silent skip.

### The no-digest-moved proof — stated, not assumed

This is the hardest constraint in the phase, so it is proved three ways and each one is a command.

**(a) The suite's own two halves of the freeze.**

```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
PYTHONPATH=engine/src engine/.venv/bin/python -m pytest \
  engine/tests/test_registry.py engine/tests/test_lab_methods.py -n0
```

`test_registry.py::test_registry_is_append_only_against_the_pins` recomputes every pinned
candidate digest; `test_lab_methods.py::test_every_recorded_configuration_still_digests_to_its_recorded_digest`
re-digests every candidate a recorded trial names and compares against `trials.config_digest`;
`test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` proves no method file moved.

**(b) A standalone read-only re-digest**, so the proof does not depend on the test harness. Write
it to the scratchpad, not the repo:

```bash
cat > /tmp/check_digests.py <<'PY'
"""Re-digest every committed method candidate and compare against trials.config_digest.

Read-only: opens the committed lab with mode=ro so the connect-time migration cannot run and
dirty the shared file (a lab command migrates lab.sqlite even on a read). Exit 1 on any drift.
"""
from __future__ import annotations

import sqlite3
import sys

from seer_engine.lab import store
from seer_engine.lab.method import config_digest, discover

METHODS = discover()

conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
drifted: list[str] = []
checked = 0
for row in conn.execute("SELECT id FROM methods WHERE id GLOB 'M*' AND source_sha IS NOT NULL"):
    mid = str(row["id"])
    method, _ = METHODS[mid]
    have = {config_digest(c) for c in method.all_candidates()}
    for t in conn.execute(
        "SELECT candidate_id, config_digest FROM trials WHERE method_id = ?", (mid,)
    ):
        checked += 1
        if str(t["config_digest"]) not in have:
            drifted.append(f"{mid}/{t['candidate_id']} {t['config_digest']}")
conn.close()
print(f"checked {checked} recorded trial digests")
print(f"drifted: {len(drifted)}")
for d in drifted:
    print("  ", d)
sys.exit(1 if drifted else 0)
PY

cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
md5sum lab/lab.sqlite
PYTHONPATH=engine/src engine/.venv/bin/python /tmp/check_digests.py
md5sum lab/lab.sqlite   # must be the same hash: the read must not have dirtied the file
```

**Measured in this session, against the full patch applied in an out-of-tree sandbox:**

```
checked 1313 recorded trial digests
drifted: 0
lab.sqlite md5 before and after: 9dbbf873209e82c8303f7f7117cb0682 (unchanged)
```

**(c) The structural argument, which is why (a) and (b) can be expected to pass.**
`registry._canon` renders a dataclass by enumerating `fields(value)` where `f.compare`. This
phase adds no dataclass field anywhere. A keyword argument on a function is not a field, has no
`compare` attribute and is never reached by `_canon`. Confirm mechanically that the two params
classes did not grow:

```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
git diff -- engine/src/seer_engine/strategies/f_factor.py \
             engine/src/seer_engine/strategies/f_fundamental.py \
  | grep -E '^[+-].*(min_price|min_dollar_volume|: float|: int|: str|: tuple)' || echo "no field-shaped line moved"
```

### What this session already ran

The whole phase was applied to an out-of-tree copy of `engine/src` and exercised against this
worktree's real test files. Results:

| Run | Result |
|---|---|
| `test_f_factor.py test_f_fundamental.py test_registry.py test_strategy_purity.py` | 206 passed |
| `test_lab_methods.py` (both halves of the freeze, plus the per-candidate smoke run) | 2862 passed |
| the new `test_price_floor.py` | 49 passed |
| the full engine suite with `PG_TEST_URL` set | 7717 passed, 4 skipped, 14 failed — **all 14 traced to the sandbox's `REPO_ROOT` pointing at a scratch directory** (missing `data/sp500_history.csv`, a `lab/` symlink defeating `snapshot_path`, `.gitignore` and `.claude/` absent). Eight were cleared by symlinking the missing repo files; the remaining eight fail on path identity alone and are unrelated to the patch. |
| the standalone re-digest | 1313 trial digests checked, 0 drifted, `lab.sqlite` md5 unchanged |

**Manual check:** none needed. No user-visible surface changes; `web/` is untouched.

**Exit criteria:**

1. `seer_engine.strategies.price_floor` exists, is pure, and is exercised by
   `engine/tests/test_price_floor.py`.
2. The five real-world closes (AAPL $645.57 / $94.25 across its 7:1, GOOGL $693.02, AMZN
   $562.44, KO $61.06) are pinned, without reading any research store.
3. `price_floor` and the two frozen copies agree on all five closes and across the floor
   boundary, in a test, so the frozen copies cannot drift away from the supported one.
4. `factor_rows` and `fundamental_rows` accept `price_basis="printed"` with a market carrying
   splits, keep a company the adjusted floor removed, and refuse a market without splits.
5. At the default every call is byte-identical: `plain == explicit == with_market`.
6. `pytest engine/tests` is green; `ruff check engine` is clean.
7. `checked N recorded trial digests / drifted: 0`, and `lab/lab.sqlite`'s md5 is unchanged.
8. `docs/lab/price-floor.md` exists and names the four frozen sites, the three delegating
   modules and the one legal route.
9. `git status --short` shows exactly five new/modified paths and nothing under
   `engine/src/seer_engine/lab/methods/`, `lab/` or `web/`.

---

## Commit

Explicit file paths only — other sessions share this checkout, so never `git commit -a` and
never a broad pathspec. The message goes in a file and is applied with `git commit -F`: backticks
in a `-m` string are shell-substituted and silently delete words, and that has destroyed commits
in this repo twice.

```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick

# 1. stage exactly the five paths this phase owns
git add \
  engine/src/seer_engine/strategies/price_floor.py \
  engine/src/seer_engine/strategies/f_factor.py \
  engine/src/seer_engine/strategies/f_fundamental.py \
  engine/tests/test_price_floor.py \
  docs/lab/price-floor.md

# 2. look at what is actually staged before committing
git status --short
git diff --cached --stat

# 3. the message, written to a file (never inline with -m)
cat > /tmp/phase1-commit-msg.txt <<'MSG'
strategies: the printed-price floor as a supported, default-off option

The five-dollar screen has always compared the store's back-adjusted close, so it
removed the companies that split the most instead of the penny stocks. M0383 measured
the hole on the dev store and M0387 priced the repair; both ended up holding the only
verified printed-price arithmetic in the tree, inside frozen pre-registrations nobody
may edit.

This gives that arithmetic a real home in strategies/price_floor.py and threads the
basis into the two editable shared screens as a keyword-only argument defaulting to
today's behaviour. No dataclass field is added: registry._canon enumerates compare=True
fields and drops pinned defaults for TradeRules only, so a field here would move every
recorded config_digest that embeds a FactorParams. An argument is invisible to it.
Re-digested every candidate a recorded trial names against lab.sqlite opened mode=ro:
1313 digests checked, 0 drifted, the file's hash unchanged.

The four frozen comparison sites (m0052, m0109, m0117, m0276) are deliberately left
alone and recorded in docs/lab/price-floor.md with the one legal route to repairing
them. The three modules that only delegate to m0109's screen need no change and are
shown to contain no comparison.

The printed basis refuses a market with no splits rather than collapsing back to the
adjusted one, which is what would happen on the paper night, where Market.shares is
EMPTY_SHARES and raw_factor answers 1.0 for every symbol.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG

git commit -F /tmp/phase1-commit-msg.txt
```

Do **not** run `lab stage`. Do **not** stage `lab/lab.sqlite` or `web/data/lab.json`; this phase
does not change either, and the only read of `lab.sqlite` is through `mode=ro`.

---

## Handoffs

- **Making the printed basis a default, or repairing sites 3-6.** Not this phase, not any phase
  in this set. The legal route is a new variation method inheriting the repaired screen, or an
  `Amendment` on one of the four frozen methods; `docs/lab/price-floor.md` names it. Serves a
  future requirement, not R1.
- **Share counts on the paper night** (insights 778/779): a table, a migration, a loader and a
  nightly job. Until it exists the printed basis cannot run live at all. Recorded in the module
  docstring and in the note; not built here. Explicitly out of scope per the plan index.
- **`Market.market_value` versus `f_fundamental`'s `market_cap = shares × close`.** The `close`
  in `_row` is still the adjusted one and is still half of a known-broken market-cap figure.
  Repairing that is a separate question with a separate repaired path and is not touched: this
  phase changes only which number the *floor* is compared against. Not R1.
- **Phase 2** owns `sim/rules.py` and `sim/book.py`; **phase 3** owns **ten** `lab/methods/`
  files and one `docs/runbooks/` file. This phase shares no file with either, so the three may
  run concurrently. Phase 3's ten amendment arms call `factor_rows` in **four** cases
  (M0260, M0261, M0262, M0334) and will see the unchanged default pool — which is exactly the
  reason D2 fixed the default where it is, and is plan-set invariant **I8**. (M0338 also reaches
  `factor_rows`, but it is one of the three methods phase 3 does *not* amend: it already carries
  `M0338-NOSW`, "no opinion: same book, switch off, always invested". See the index's R3 row for
  the corrected census — thirteen by the `exposure >= 0.98` read, ten in fact.)
- **`strategies/__init__.py`** is not updated to re-export `price_floor`. Neither `f_factor` nor
  `f_fundamental` is re-exported there either, so adding one would be an inconsistency and a
  drive-by. Left as-is deliberately.

---

## Rollback

This phase is one commit touching five paths no other phase touches.

```bash
cd /home/miftah/.worktrees/seer/floor-reservation-yardstick
git revert --no-edit <sha>
```

Or, before the commit lands:

```bash
git checkout -- engine/src/seer_engine/strategies/f_factor.py \
                engine/src/seer_engine/strategies/f_fundamental.py
rm -f engine/src/seer_engine/strategies/price_floor.py \
      engine/tests/test_price_floor.py \
      docs/lab/price-floor.md
```

Nothing outside git changes: no lab row, no research store, no database, no deployed page, no
paper-night behaviour. `lab/lab.sqlite` is only ever read, and only `mode=ro`.
