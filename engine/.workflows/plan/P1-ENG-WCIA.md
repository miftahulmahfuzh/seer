> Adopted from `STRATEGY_A_REWORK_PLAN.md` phase 1. Source: `.workflows/plan/strategy-a-rework/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: Strategy A2: variants V0–V3

**Plan set:** `STRATEGY_A_REWORK_PLAN.md`
**Analysis:** `20261003-160830-R4W9_code_analyzer.md`
**Spec:** `docs/handover/2026-10-03-strategy-a-rework.md` (§3 "Decided in this handover" rows V0–V3, Code shape; §6 items 1, 2, 5)
**Satisfies:** R1, R2, R5. These give the user the four pre-registered variants, each one tested on its added rule, with P4 identity and no look-ahead (SPY's own bars included), in a module the purity glob covers.
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/strategies`

---

## Goal

`seer_engine.strategies.a2` exists. It is a pure Strategy `"A2"` whose `A2Params` carries a
variant name (`control`, `regime`, `regime_calm`, `regime_calm_floor`) plus Strategy A's five
tunable fields. V0 reproduces Strategy A v1's picks exactly. V1 adds the SPY > SMA(200) regime
gate, which is strict, so equality means off. V2 ranks by ATR(14)/close, then RSI(2), then
symbol. V3 adds an inclusive $10 close floor. `picks_prepared(prepare(H), …) == picks(upto(d), …)`
holds for every variant, and changing any bar dated ≥ S, SPY's included, never changes S's picks.
`strategies/a.py` and the rest of the tree are untouched.

**Verified:** the code in this plan was built in a scratch copy of the worktree's `engine/`
with its own venv. The new test file passes (62 passed). The purity tests pass with `a2.py`
in the glob. Two deliberate mutants are caught: (1) `regime_on` reading `spy.close[-1]`
(look-ahead) gives 10 failures; (2) `prepare_a2` using `>=` (equality on) gives 3 failures.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts.

**Deletes:** nothing.
**Renames:** nothing.
**Creates** (all in `engine/src/seer_engine/strategies/a2.py`, new file):
- `REGIME_SYMBOL: str = "SPY"`. A test asserts `== seer_engine.universe.BENCHMARK`. `a2.py` does **not** import `universe`, because it imports psycopg.
- `FLOOR_PRICE: float = 10.0`.
- `VARIANTS: tuple[str, ...] = ("control", "regime", "regime_calm", "regime_calm_floor")`. This is the V0..V3 order everywhere.
- `@dataclass(frozen=True, slots=True) class A2Params`.
  - Fields, in order: `variant: str = "control"`, `rsi_max: float = 10.0`, `limit_atr: Decimal = Decimal("0.5")`, `tp_atr: Decimal = Decimal("1.0")`, `sl_atr: Decimal = Decimal("1.5")`, `min_dollar_volume: float = 20_000_000.0`.
  - It is hashable, and `==` is field-wise.
  - Validation:
    - a non-str `variant` raises `TypeError`;
    - a `variant` not in `VARIANTS` raises `ValueError`;
    - the other five fields raise exactly `AParams`'s errors, because validation builds an `AParams`;
    - `rsi_max` and `min_dollar_volume` are coerced to `float`.
  - Methods:
    - `a_params() -> AParams`;
    - `as_dict() -> dict[str, str]`: `"variant"` first, then `AParams.as_dict()`'s five keys in their order;
    - `@classmethod from_a(variant: str, p: AParams) -> A2Params`, which raises `TypeError` if `p` is not an `AParams`.
- `A2_DESIGN_PARAMS: A2Params = A2Params()`: V0 with the design values. It is equal to `A2Params.from_a("control", DESIGN_PARAMS)`.
- `STRATEGY_A2_PARAMS: A2Params | None = None`. **Phase 6 owns the value**, plus the comment above it.
- `regime_on(spy: History | None, data_date: date) -> bool`: strict `close > sma_window(last LOOKBACK closes ending at data_date)`. It returns `False` in each of these cases:
  - `spy` is None;
  - there is no bar on `data_date`;
  - there are fewer than 200 bars through `data_date`.

  It raises `TypeError` if `data_date` is not a `date`, or is a `datetime`.
- `picks_from_features_a2(features: Iterable[Features], members: Set[str], params: A2Params, regime: bool) -> list[Pick]`.
- `@dataclass(frozen=True, slots=True, eq=False) class A2Prepared`.
  - Fields: `a: APrepared`, `regime_dates: np.ndarray` (datetime64[D], read-only), `regime: np.ndarray` (bool, read-only).
  - Method: `regime_on(data_date) -> bool`.
- `prepare_a2(history: Mapping[str, History]) -> A2Prepared`.
- `picks_prepared_a2(prepared: A2Prepared, members: Set[str], data_date: date, params: A2Params) -> list[Pick]`.
- `class StrategyA2`: `id = "A2"`, `lookback = 200`, and the methods `picks`, `prepare`, `picks_prepared`. It satisfies `strategies.base.Strategy`.
- `STRATEGY_A2 = StrategyA2()`.
- Private helpers: `_REGIME_VARIANTS`, `_CALM_VARIANTS`, `_FLOOR_VARIANTS` (frozensets) and `_check_params`.

**Re-exported from `seer_engine.strategies`** (additive): `A2_DESIGN_PARAMS`, `STRATEGY_A2`,
`STRATEGY_A2_PARAMS`, `VARIANTS`, `A2Params`, `A2Prepared`, `StrategyA2`. Import `REGIME_SYMBOL`,
`FLOOR_PRICE`, `regime_on`, `picks_from_features_a2`, `prepare_a2` and `picks_prepared_a2` from
`seer_engine.strategies.a2`.

**Signature changes:** none.

**Behavioural guarantees other phases may rely on:**
- **P4 identity**, for every variant: `STRATEGY_A2.picks_prepared(STRATEGY_A2.prepare(H), M, d, p) == STRATEGY_A2.picks({s: h.upto(d)}, M, d, p)`.
- **V0 identity:** if `"SPY" not in M`, then `STRATEGY_A2.picks(H, M, d, A2Params.from_a("control", a)) == STRATEGY_A.picks(H, M, d, a)`, and the same holds for `picks_prepared`.
- **Prepare once:** `prepare_a2` does not depend on params or variant. One `A2Prepared` serves all 324 combinations (Decision D3).
- **Bad input types raise `TypeError`:**
  - `picks`, `picks_prepared` and `picks_from_features_a2` raise it for any params value that is not an `A2Params`, including a plain `AParams`;
  - `picks_prepared` raises it for a `prepared` that is not an `A2Prepared`.
- **No mutable state:** `A2Params` instances are immutable and hashable, so they are safe as dict keys in `tuning`/`walkforward`.

**Requires (from earlier phases):** none.

**Leaves alone (owned by others):**
- `strategies/a.py`, `base.py` and `indicators.py`: these are Law, never edited.
- `backtest/runner.py`, `metrics.py` and `tuning.py` (Phase 2).
- `backtest/walkforward.py` (Phase 3).
- `backtest/wf_report.py` (Phase 4).
- `backtest/io.py` and `commands/backtest_wf.py` (Phase 5).
- The value of `STRATEGY_A2_PARAMS`, `tests/test_strategy_a2_frozen.py`, `docs/*` and `engine/package_readme.md` (Phase 6).
- `tests/test_strategy_purity.py` is not edited: its glob picks up `a2.py` automatically.
- `tests/stratkit.py` is not edited: no new shared builder was needed.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/strategies/a2.py` | create | the whole module (275 lines) |
| `engine/src/seer_engine/strategies/__init__.py` | modify | docstring line 4–5 mentions `a2`; new `from seer_engine.strategies.a2 import (...)` after line 18; 7 names added to `__all__` (lines 21–34) |
| `engine/tests/test_strategy_a2.py` | create | 62 tests: params, regime boundary, ATR% ranking + ties, $10 floor, SPY never picked, V0 == v1, P4 identity × 4 variants × 3 params, no look-ahead (5 mutation kinds incl. SPY-only) + 2 guard tests |

`engine/tests/stratkit.py`: **not touched.** Its builders (`hist`, `uptrend`, `dip`,
`sawtooth`, `drop_days`, `mutate_from` with a custom `fn`, `truncate_before`, `session_days`,
`feat`) cover every case.

## Implementation Steps

### Step 0: Worktree venv (only if `engine/.venv` is absent)
**File:** `engine/.venv`, which is gitignored by `.gitignore:14`.
**Change:** the worktree has no venv. Main's venv tests main's tree, so never use `/home/miftah/seer/engine/.venv`.
**Code:**
```bash
cd /home/miftah/.worktrees/seer/strategy-a-rework
test -x engine/.venv/bin/pytest || { python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'; }
docker start seer-pg
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q   # baseline: 598 passed
```
**Impact:** none on the tree. If another phase's session already created the venv, skip this step.

### Step 1: Create `strategies/a2.py`
**File:** `engine/src/seer_engine/strategies/a2.py:1` (new file)
**Change:** the whole module. Design notes, so the implementer does not "simplify" a load-bearing choice:
- **The regime is strict** (`>`). Equality means off (D5). `prepare_a2` uses `rolling(sma_window, …)` and `regime_on` uses `sma_window` on a single `(1, 200)` window. Both run `_column_mean` in the same left-to-right order, so their floats are bit-identical; the test `test_prepared_regime_equals_regime_on_on_every_spy_date` checks this.
- **`regime_on` calls `as_day(data_date)` first.** A bad date therefore raises even when SPY is missing, and even on the early-return path.
- **The early return.** `picks` returns `[]` before computing features when a V1–V3 variant runs with the regime off. `picks_prepared_a2` does the same before its pre-filter. Both are pure short-cuts of the rule that `picks_from_features_a2` applies anyway.
- **SPY is excluded twice:**
  - in `picks_prepared_a2`'s candidate loop (to save work);
  - in `picks_from_features_a2`, which is authoritative.

  `features_at` in `picks` sees only members. If a caller lists SPY as a member, its features are computed and then dropped.
- **The floor applies to `f.close`, the float close.** It does not apply to the rounded `last`, and it does not apply to the limit. `close >= 10.0` is inclusive.
- **Why `f.atr / f.close` cannot fail:** `_bracket` has already rejected `last <= 0` after rounding, so `f.close >= 0.00005 > 0` when the key is computed.
- **Ranking keys are tuples sorted ascending.** Symbols are unique within one `data_date`, so the sort is total and does not depend on input order.
- **Defaults.** `A2Params` defaults are literals that equal `AParams`'s. `A2_DESIGN_PARAMS.a_params() == DESIGN_PARAMS` is tested.
- **Imports of private helpers.** The module imports `_setup`, `_bracket`, `APrepared._rows` and `APrepared._features` from the sibling `a.py`. That is deliberate: the handover says to reuse `a.py`'s helpers, and `a.py` must not change.

**Code:**
```python
"""Strategy A2: Strategy A v1 plus pre-registered variants V0–V3 (P3b rework, handover §3).

Every variant uses Strategy A's features, setup and bracket unchanged (``strategies/a.py``,
which this module never edits). A variant only adds rules on top:

    V0 ``control``            Strategy A v1 exactly: rank by (RSI(2), symbol).
    V1 ``regime``             V0, plus no new picks on a ``data_date`` where SPY's close <= SPY's
                              SMA(200). Regime on <=> close > SMA(200), STRICT; equality is off.
    V2 ``regime_calm``        V1, but rank by (ATR(14) / close, RSI(2), symbol) ascending.
    V3 ``regime_calm_floor``  V2, plus a candidate needs close >= ``FLOOR_PRICE`` (10.0, inclusive).

The regime reads ``REGIME_SYMBOL``'s bars from the SAME history mapping the picks come from
(SPY is in ``Market.history`` but never a universe member). SPY's SMA(200) is ``sma_window``
over its last ``LOOKBACK`` closes ending at ``data_date``, so the backtest (``prepare_a2``,
rolling) and the nightly job (``regime_on``, one window) compute bit-identical floats. SPY
missing, without a bar on ``data_date`` or with fewer than ``LOOKBACK`` bars through it means the
regime is OFF. SPY itself is never a pick, even when a caller lists it in ``members``.

The variant is a field of ``A2Params`` so one selection can run over every (variant, grid)
combination and a params schedule can switch variant by date. Pure: no database, network,
clock or randomness (tests/test_strategy_purity.py).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Set
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.sim import Pick
from seer_engine.strategies.a import (
    LOOKBACK,
    SMA_N,
    AParams,
    APrepared,
    Features,
    _bracket,
    _setup,
    features_at,
    prepare_a,
)
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.indicators import rolling, sma_window

REGIME_SYMBOL = "SPY"  # == seer_engine.universe.BENCHMARK (tested; universe imports psycopg, so not imported here)
FLOOR_PRICE = 10.0  # V3: close >= FLOOR_PRICE (inclusive). Fixed by the handover, never tuned.
VARIANTS: tuple[str, ...] = ("control", "regime", "regime_calm", "regime_calm_floor")  # V0..V3

_REGIME_VARIANTS = frozenset(VARIANTS[1:])  # V1..V3: no new picks while the regime is off
_CALM_VARIANTS = frozenset(VARIANTS[2:])  # V2..V3: rank by ATR(14) / close first
_FLOOR_VARIANTS = frozenset(VARIANTS[3:])  # V3: close >= FLOOR_PRICE


@dataclass(frozen=True, slots=True)
class A2Params:
    """A variant name plus Strategy A's five tunable parameters (defaults: V0 with design §4 values)."""

    variant: str = "control"  # one of VARIANTS
    rsi_max: float = 10.0  # the five below mean exactly what they mean in AParams
    limit_atr: Decimal = Decimal("0.5")
    tp_atr: Decimal = Decimal("1.0")
    sl_atr: Decimal = Decimal("1.5")
    min_dollar_volume: float = 20_000_000.0

    def __post_init__(self) -> None:
        if not isinstance(self.variant, str):
            raise TypeError(f"variant must be a str, got {type(self.variant).__name__}")
        if self.variant not in VARIANTS:
            raise ValueError(f"variant must be one of {', '.join(VARIANTS)}, got {self.variant!r}")
        a = self.a_params()  # validates the five A fields exactly as AParams does
        object.__setattr__(self, "rsi_max", a.rsi_max)
        object.__setattr__(self, "min_dollar_volume", a.min_dollar_volume)

    def a_params(self) -> AParams:
        """Strategy A's params with the same five values."""
        return AParams(
            rsi_max=self.rsi_max,
            limit_atr=self.limit_atr,
            tp_atr=self.tp_atr,
            sl_atr=self.sl_atr,
            min_dollar_volume=self.min_dollar_volume,
        )

    def as_dict(self) -> dict[str, str]:
        """``variant`` first, then ``AParams.as_dict()``'s five plain decimal strings in its order."""
        return {"variant": self.variant, **self.a_params().as_dict()}

    @classmethod
    def from_a(cls, variant: str, p: AParams) -> A2Params:
        """``variant`` with ``p``'s five values."""
        if not isinstance(p, AParams):
            raise TypeError(f"p must be AParams, got {type(p).__name__}")
        return cls(
            variant=variant,
            rsi_max=p.rsi_max,
            limit_atr=p.limit_atr,
            tp_atr=p.tp_atr,
            sl_atr=p.sl_atr,
            min_dollar_volume=p.min_dollar_volume,
        )


A2_DESIGN_PARAMS = A2Params()  # V0 with the design values: the walk-forward's none-qualifies fallback
# Set by phase 6 ONLY if the P3b gate passes, to the last fold's selection, with a comment naming
# the report (tests/test_strategy_a2_frozen.py ties the two). None means A2 is not frozen.
STRATEGY_A2_PARAMS: A2Params | None = None


def _check_params(params: object) -> A2Params:
    if not isinstance(params, A2Params):
        raise TypeError(f"params must be A2Params, got {type(params).__name__}")
    return params


def regime_on(spy: History | None, data_date: date) -> bool:
    """True iff SPY's close on ``data_date`` is STRICTLY above its SMA(200).

    SMA(200) = ``sma_window`` over SPY's last ``LOOKBACK`` closes ending at ``data_date``; later
    bars are never read. ``spy`` None, no SPY bar dated ``data_date``, or fewer than ``LOOKBACK``
    bars through it -> False (the regime is off, so V1..V3 make no new picks).
    """
    as_day(data_date)
    if spy is None:
        return False
    i = spy.index_of(data_date)
    if i is None or i + 1 < LOOKBACK:
        return False
    window = spy.close[i + 1 - LOOKBACK : i + 1].reshape(1, LOOKBACK)
    sma = sma_window(window, SMA_N)
    return bool(spy.close[i] > sma[0])


def picks_from_features_a2(
    features: Iterable[Features],
    members: Set[str],
    params: A2Params,
    regime: bool,
) -> list[Pick]:
    """Ranked A2 picks from Strategy A features under ``params.variant``'s rules.

    V1..V3 with ``regime`` False -> []. Candidates: member, not ``REGIME_SYMBOL``, Strategy A's
    setup and a valid bracket; V3 also needs ``close >= FLOOR_PRICE``. Ranked ascending by
    (RSI, symbol) for V0/V1 and by (ATR / close, RSI, symbol) for V2/V3. Uncapped.
    """
    params = _check_params(params)
    if params.variant in _REGIME_VARIANTS and not regime:
        return []
    a = params.a_params()
    calm = params.variant in _CALM_VARIANTS
    floor = params.variant in _FLOOR_VARIANTS
    ranked: list[tuple[tuple[Any, ...], Pick]] = []
    for f in features:
        if f.symbol not in members or f.symbol == REGIME_SYMBOL or not _setup(f, a):
            continue
        if floor and not f.close >= FLOOR_PRICE:
            continue
        pick = _bracket(f, a)
        if pick is None:
            continue
        # _bracket rejects last <= 0 after rounding, so f.close > 0 here.
        key = (f.atr / f.close, f.rsi, f.symbol) if calm else (f.rsi, f.symbol)
        ranked.append((key, pick))
    ranked.sort(key=lambda r: r[0])
    return [pick for _, pick in ranked]


@dataclass(frozen=True, slots=True, eq=False)
class A2Prepared:
    """Strategy A's prepared features plus SPY's regime on every date it is defined.

    ``a`` is ``prepare_a(history)`` unchanged (it includes SPY's rows, which the rules drop).
    ``regime_dates``: every SPY bar date with at least ``LOOKBACK`` bars through it, ascending.
    ``regime``: SPY close > rolling SMA(200) on that date, bit-identical to ``regime_on``.
    """

    a: APrepared
    regime_dates: np.ndarray  # datetime64[D], ascending
    regime: np.ndarray  # bool, same length

    def regime_on(self, data_date: date) -> bool:
        """``regime_on(SPY.upto(data_date), data_date)``: False when ``data_date`` has no regime row."""
        day = as_day(data_date)
        i = int(np.searchsorted(self.regime_dates, day, side="left"))
        if i == self.regime_dates.shape[0] or self.regime_dates[i] != day:
            return False
        return bool(self.regime[i])


def prepare_a2(history: Mapping[str, History]) -> A2Prepared:
    """``prepare_a(history)`` plus SPY's rolling regime column (see ``A2Prepared``)."""
    a = prepare_a(history)
    spy = history.get(REGIME_SYMBOL)
    if spy is None or len(spy) < LOOKBACK:
        dates = np.empty(0, dtype="datetime64[D]")
        regime = np.empty(0, dtype=np.bool_)
    else:
        start = LOOKBACK - 1
        sma = rolling(sma_window, spy.close, window=LOOKBACK, n=SMA_N)[start:]
        dates = spy.dates[start:].copy()
        regime = spy.close[start:] > sma
    dates.setflags(write=False)
    regime.setflags(write=False)
    return A2Prepared(a, dates, regime)


def picks_prepared_a2(prepared: A2Prepared, members: Set[str], data_date: date, params: A2Params) -> list[Pick]:
    """``picks_from_features_a2`` on ``prepared``'s rows for ``data_date``, with a vectorized pre-filter.

    The pre-filter is Strategy A's (the same strict comparisons as ``a._setup``); every survivor
    is re-checked by ``picks_from_features_a2``, so the result is exactly
    ``picks_from_features_a2(prepared.a.features_on(d), members, params, prepared.regime_on(d))``.
    """
    if not isinstance(prepared, A2Prepared):
        raise TypeError(f"prepared must be A2Prepared, got {type(prepared).__name__}")
    params = _check_params(params)
    regime = prepared.regime_on(data_date)
    if params.variant in _REGIME_VARIANTS and not regime:
        return []
    p = prepared.a
    lo, hi = p._rows(data_date)
    if lo == hi:
        return []
    window = slice(lo, hi)
    mask = (
        (p.close[window] > p.sma[window])
        & (p.rsi[window] < params.rsi_max)
        & (p.dollar_volume[window] > params.min_dollar_volume)
    )
    candidates = []
    for j in np.flatnonzero(mask):
        k = lo + int(j)
        symbol = p.symbols[int(p.sym[k])]
        if symbol in members and symbol != REGIME_SYMBOL:
            candidates.append(p._features(k, data_date))
    return picks_from_features_a2(candidates, members, params, regime)


class StrategyA2:
    """Strategy A2 behind the ``Strategy`` protocol."""

    id = "A2"
    lookback = LOOKBACK

    def picks(
        self,
        history: Mapping[str, History],
        members: Set[str],
        data_date: date,
        params: Any,
    ) -> list[Pick]:
        params = _check_params(params)
        regime = regime_on(history.get(REGIME_SYMBOL), data_date)
        if params.variant in _REGIME_VARIANTS and not regime:
            return []
        member_history = {s: h for s, h in history.items() if s in members}
        return picks_from_features_a2(features_at(member_history, data_date), members, params, regime)

    def prepare(self, history: Mapping[str, History]) -> A2Prepared:
        return prepare_a2(history)

    def picks_prepared(
        self,
        prepared: Any,
        members: Set[str],
        data_date: date,
        params: Any,
    ) -> list[Pick]:
        return picks_prepared_a2(prepared, members, data_date, params)


STRATEGY_A2 = StrategyA2()
```
**Impact:** new module, imported by nothing yet except `strategies/__init__` (Step 2). The purity glob in `tests/test_strategy_purity.py` now imports it in a fresh interpreter and AST-scans it. It imports only `numpy`, `seer_engine.sim`, and `seer_engine.strategies.{a,base,indicators}`, so the purity tests stay green.

### Step 2: Export from `strategies/__init__.py`
**File:** `engine/src/seer_engine/strategies/__init__.py:1-35` (whole file; the changes are the docstring at lines 4–5, a new import block after line 18, and 7 new `__all__` entries)
**Change:** additive re-exports. No existing name changes. `__all__` stays in the existing order: constants first, then classes, then functions.
**Code:**
```python
"""Trading strategies: pure functions from daily bar history to ranked ``sim.Pick``s.

``base`` holds the interface every strategy implements (P3 Strategy A, P6 B and C) and the
``History`` bar container; ``indicators`` the window functions; ``a`` Strategy A; ``a2``
Strategy A2, the P3b rework (Strategy A plus the pre-registered variants V0–V3). Pure: no
database, network, clock or randomness (tests/test_strategy_purity.py).
"""

from seer_engine.strategies.a import (
    DESIGN_PARAMS,
    STRATEGY_A,
    STRATEGY_A_PARAMS,
    AParams,
    APrepared,
    Features,
    StrategyA,
    features_at,
    picks_from_features,
)
from seer_engine.strategies.a2 import (
    A2_DESIGN_PARAMS,
    STRATEGY_A2,
    STRATEGY_A2_PARAMS,
    VARIANTS,
    A2Params,
    A2Prepared,
    StrategyA2,
)
from seer_engine.strategies.base import History, Strategy, history_from_bars

__all__ = [
    "A2_DESIGN_PARAMS",
    "DESIGN_PARAMS",
    "STRATEGY_A",
    "STRATEGY_A2",
    "STRATEGY_A2_PARAMS",
    "STRATEGY_A_PARAMS",
    "VARIANTS",
    "A2Params",
    "A2Prepared",
    "AParams",
    "APrepared",
    "Features",
    "History",
    "Strategy",
    "StrategyA",
    "StrategyA2",
    "features_at",
    "history_from_bars",
    "picks_from_features",
]
```
**Impact:** `from seer_engine.strategies import STRATEGY_A2, A2Params, VARIANTS, ...` works for Phases 3–6. No circular import: `a2` imports `a`, `base`, `indicators` and `sim`, never the package `__init__`.

### Step 3: Create `tests/test_strategy_a2.py`
**File:** `engine/tests/test_strategy_a2.py:1` (new file)
**Change:** 62 tests, mirroring `test_strategy_a.py`'s style (`contract_set`, `lookahead_set`, `mutate_from`, `truncate_before`, guard tests that keep the checks non-vacuous). They map to the requirements like this:

**R1, V1 regime:**
- `test_flat_spy_sma_equals_close_exactly`: guard. 200 × 100.0 gives SMA == close == 100.0 exactly in float.
- `test_regime_boundary`: three cases: equal means off, 99.5 means off, 100.5 means on. Both `regime_on` and `A2Prepared.regime_on` are checked.
- `test_regime_off_when_spy_missing_short_or_without_a_bar_on_data_date`
- `test_regime_reads_only_the_last_lookback_spy_bars`
- `test_regime_gates_new_picks_end_to_end`: SPY rising, flat (equality), falling and missing, × the 4 variants, through `picks` and `picks_prepared`.
- `test_regime_flag_gates_variants_at_the_feature_level`

**R1, V2 ATR% ranking:**
- `test_atr_pct_ties_are_exact_floats`: guard. `1/50 == 2/100 == 0.5/25`.
- `test_calm_ranking_is_atr_pct_then_rsi_then_symbol`: three-way ATR% tie, broken by RSI and then by symbol; V0/V1 use the RSI order on the same set.
- `test_calm_ranking_is_uncapped_and_input_order_free`

**R1, V3 floor:**
- `test_floor_at_exactly_ten`: 10.0 is kept, 10.0001 is kept, 9.9999 is dropped, 9.0 is dropped. Only V3 drops.
- `test_floor_reads_the_close_not_the_limit`

**R1, V0 == v1:** `test_v0_picks_equal_strategy_a_picks`. It runs over the contract set with SPY present, for each of the design, permissive and mid `AParams`, on every date in `days[190:]`, through both `picks` and `picks_prepared`.

**R2:**
- `test_contract_set_exercises_every_rule`: guard. On the contract set, the regime is both on and off, and V1≠V0, V2≠V1 and V3≠V2 each happen on some date.
- `test_picks_prepared_equals_picks_on_every_date`: 4 variants × 3 params, every date, with SPY listed as a member on `days[300:]`.
- `test_prepared_regime_equals_regime_on_on_every_spy_date`
- `test_no_look_ahead`, with 5 mutations:
  - `change` (×3 + 7), `halve` and `truncate`, applied to all symbols, SPY included;
  - `spy_only_halve` and `spy_only_truncate`.

  Each mutation is checked for 4 variants × 2 params. A non-vacuity guard requires every variant to have at least 2 non-empty design-params days.
- `test_the_spy_mutation_does_change_later_regime_and_picks`: guard. Halving SPY from S, read at `data_date = S`, flips the regime off. V1–V3 picks become `[]` and V0 is unchanged.
- `test_the_full_mutation_does_change_later_picks`: guard.

**SPY / contract:**
- `test_spy_is_never_a_pick_even_as_a_member`
- `test_spy_is_never_a_pick_end_to_end`: guard. v1 *would* pick SPY in this set.
- `test_constants`: `REGIME_SYMBOL == universe.BENCHMARK`. The test imports `seer_engine.universe`, which is fine in tests; only `a2.py` must avoid psycopg.
- params validation, protocol, and type errors.

**Contract-set design:**
- `SPY = spy_closes(320)`:
  - it rises 0.2/day for 250 bars, falls 1.5/day for 25, then rises 2.0/day;
  - the regime is off on days[190..198] (too few bars), on from days[199] to about days[261], off to about days[284], then on again.
- `PENNY = sawtooth(320, first=7.5, up=0.06, down=0.04)`, with `spread=0.05` and `volume=5e6`. It crosses $10 around day 250, while the regime is on, so V3 ≠ V2 on some days.

The values were tuned and checked in the scratch run. **Do not change them without re-running the guard test.**

**Code:**
```python
"""Strategy A2 and its variants V0–V3 (P3b handover §3, §6.1–§6.2, §6.5; plan Decisions D2, D4, D5)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import numpy as np
import pytest
from simkit import P
from stratkit import (
    dip,
    drop_days,
    feat,
    hist,
    mutate_from,
    sawtooth,
    session_days,
    truncate_before,
    uptrend,
)

from seer_engine import universe
from seer_engine.dates import prev_session
from seer_engine.sim import Pick
from seer_engine.strategies import (
    A2_DESIGN_PARAMS,
    DESIGN_PARAMS,
    STRATEGY_A,
    STRATEGY_A2,
    VARIANTS,
    A2Params,
    A2Prepared,
    AParams,
    History,
    Strategy,
    features_at,
)
from seer_engine.strategies.a2 import (
    FLOOR_PRICE,
    REGIME_SYMBOL,
    picks_from_features_a2,
    regime_on,
)

PERMISSIVE = AParams(rsi_max=100.0)  # every RSI(2) strictly below 100 passes
MID = AParams(rsi_max=60.0, limit_atr=Decimal("0.25"), tp_atr=Decimal("1.5"))
A_PARAMS = (DESIGN_PARAMS, PERMISSIVE, MID)
A_IDS = ["design", "permissive", "mid"]


def upto_all(history: dict[str, History], d: date) -> dict[str, History]:
    return {s: h.upto(d) for s, h in history.items()}


def every(variant_params: AParams = DESIGN_PARAMS) -> list[A2Params]:
    """One A2Params per variant, in VARIANTS order, with ``variant_params``' five values."""
    return [A2Params.from_a(v, variant_params) for v in VARIANTS]


def symbols(picks: list[Pick]) -> list[str]:
    return [p.symbol for p in picks]


def flat_spy(n: int, close: float = 100.0, days: list[date] | None = None) -> History:
    """SPY with ``n`` identical closes: SMA(200) == close exactly in float, so the regime is OFF."""
    return hist(REGIME_SYMBOL, [close] * n, days=days)


def spy_closes(n: int) -> list[float]:
    """Rise 0.2/day for 250 bars, fall 1.5/day for 25, then rise 2.0/day: the regime goes on, off, on."""
    out: list[float] = []
    for t in range(n):
        if t < 250:
            out.append(100.0 + 0.2 * t)
        elif t < 275:
            out.append(out[-1] - 1.5)
        else:
            out.append(out[-1] + 2.0)
    return out


# ---- constants and params ------------------------------------------------------------------


def test_constants():
    assert VARIANTS == ("control", "regime", "regime_calm", "regime_calm_floor")
    assert REGIME_SYMBOL == universe.BENCHMARK == "SPY"
    assert FLOOR_PRICE == 10.0
    assert A2_DESIGN_PARAMS == A2Params() == A2Params.from_a("control", DESIGN_PARAMS)
    assert A2_DESIGN_PARAMS.a_params() == DESIGN_PARAMS


def test_a2params_defaults_coercion_and_as_dict():
    p = A2Params(variant="regime_calm", rsi_max=5, limit_atr=Decimal("0.25"), sl_atr=Decimal("2.0"))
    assert p.rsi_max == 5.0 and isinstance(p.rsi_max, float)
    assert isinstance(p.min_dollar_volume, float)
    assert list(p.as_dict().items()) == [
        ("variant", "regime_calm"),
        ("rsi_max", "5"),
        ("limit_atr", "0.25"),
        ("tp_atr", "1"),
        ("sl_atr", "2"),
        ("min_dollar_volume", "20000000"),
    ]
    assert p.a_params() == AParams(rsi_max=5.0, limit_atr=Decimal("0.25"), sl_atr=Decimal("2.0"))
    assert A2Params(min_dollar_volume=1).min_dollar_volume == 1.0


def test_from_a_round_trips_and_params_are_hashable():
    for variant in VARIANTS:
        for a in A_PARAMS:
            p = A2Params.from_a(variant, a)
            assert (p.variant, p.a_params()) == (variant, a)
    assert len({A2Params.from_a(v, a) for v in VARIANTS for a in A_PARAMS}) == len(VARIANTS) * len(A_PARAMS)
    assert A2Params(variant="regime") != A2Params(variant="control")
    with pytest.raises(TypeError):
        A2Params.from_a("control", {"rsi_max": 10.0})


@pytest.mark.parametrize(
    ("kw", "exc"),
    [
        ({"variant": "V1"}, ValueError),
        ({"variant": "Control"}, ValueError),
        ({"variant": ""}, ValueError),
        ({"variant": None}, TypeError),
        ({"variant": 1}, TypeError),
        ({"limit_atr": 0.5}, TypeError),
        ({"rsi_max": "10"}, TypeError),
        ({"rsi_max": True}, TypeError),
        ({"rsi_max": 0.0}, ValueError),
        ({"rsi_max": 100.5}, ValueError),
        ({"tp_atr": Decimal("0")}, ValueError),
        ({"sl_atr": Decimal("-1")}, ValueError),
        ({"limit_atr": Decimal("-0.1")}, ValueError),
        ({"min_dollar_volume": -1.0}, ValueError),
    ],
)
def test_a2params_rejects_bad_values(kw, exc):
    with pytest.raises(exc):
        A2Params(**kw)


def test_strategy_a2_implements_the_protocol():
    assert isinstance(STRATEGY_A2, Strategy)
    assert (STRATEGY_A2.id, STRATEGY_A2.lookback) == ("A2", 200)


def test_wrong_param_prepared_or_date_types_raise():
    h = {"S": hist("S", sawtooth(210)), "SPY": hist("SPY", uptrend(210))}
    d = h["S"].last_date()
    with pytest.raises(TypeError):
        STRATEGY_A2.picks(h, {"S"}, d, DESIGN_PARAMS)  # AParams is not A2Params
    with pytest.raises(TypeError):
        STRATEGY_A2.picks(h, {"S"}, d, {"variant": "control"})
    with pytest.raises(TypeError):
        STRATEGY_A2.picks_prepared(STRATEGY_A.prepare(h), {"S"}, d, A2_DESIGN_PARAMS)  # APrepared, not A2Prepared
    with pytest.raises(TypeError):
        STRATEGY_A2.picks_prepared(STRATEGY_A2.prepare(h), {"S"}, d, None)
    with pytest.raises(TypeError):
        picks_from_features_a2([feat("AAA")], {"AAA"}, DESIGN_PARAMS, True)
    with pytest.raises(TypeError):
        regime_on(h["SPY"], datetime(2019, 10, 15))
    with pytest.raises(TypeError):
        regime_on(None, "2019-10-15")
    with pytest.raises(TypeError):
        STRATEGY_A2.prepare(h).regime_on(datetime(2019, 10, 15))


# ---- V1: the regime ------------------------------------------------------------------------


def test_flat_spy_sma_equals_close_exactly():
    # Guards the equality tests: 200 closes of 100.0 sum to 20000.0 exactly; / 200 == 100.0.
    days = session_days(200)
    spy = flat_spy(200, days=days)
    [f] = features_at({REGIME_SYMBOL: spy}, days[-1])
    assert f.close == f.sma == 100.0


@pytest.mark.parametrize(
    ("last", "on"),
    [
        (100.0, False),  # close == SMA(200): equality is OFF (strict)
        (99.5, False),  # below
        (100.5, True),  # SMA = (199·100 + 100.5) / 200 = 100.0025 < 100.5
    ],
)
def test_regime_boundary(last, on):
    days = session_days(200)
    spy = hist(REGIME_SYMBOL, [100.0] * 199 + [last], days=days)
    assert regime_on(spy, days[-1]) is on
    assert STRATEGY_A2.prepare({REGIME_SYMBOL: spy}).regime_on(days[-1]) is on


def test_regime_off_when_spy_missing_short_or_without_a_bar_on_data_date():
    days = session_days(201)
    rising = uptrend(201)
    assert regime_on(hist(REGIME_SYMBOL, rising, days=days), days[200]) is True
    assert regime_on(None, days[200]) is False
    assert regime_on(hist(REGIME_SYMBOL, rising[:199], days=days[:199]), days[198]) is False  # 199 bars
    assert regime_on(hist(REGIME_SYMBOL, rising[:200], days=days[:200]), days[199]) is True  # 200 bars
    gappy = drop_days(hist(REGIME_SYMBOL, rising, days=days), [days[200]])
    assert regime_on(gappy, days[200]) is False  # no SPY bar on data_date
    assert regime_on(hist(REGIME_SYMBOL, rising, days=days), date(2030, 1, 2)) is False  # after the last bar
    for history in ({}, {REGIME_SYMBOL: hist(REGIME_SYMBOL, rising[:199], days=days[:199])}, {REGIME_SYMBOL: gappy}):
        prepared = STRATEGY_A2.prepare(history)
        assert isinstance(prepared, A2Prepared)
        assert prepared.regime_on(days[200]) is False
        assert prepared.regime_on(days[198]) is False


def test_regime_reads_only_the_last_lookback_spy_bars():
    # 50 tiny closes then 200 flat ones: over all 250 bars the mean is < 100 (regime would be on),
    # but over the last 200 it is exactly 100 (off).
    days = session_days(250)
    spy = hist(REGIME_SYMBOL, [1.0] * 50 + [100.0] * 200, days=days)
    assert regime_on(spy, days[-1]) is False
    assert STRATEGY_A2.prepare({REGIME_SYMBOL: spy}).regime_on(days[-1]) is False
    short = hist(REGIME_SYMBOL, [100.0] * 200, days=days[50:])
    assert regime_on(short, days[-1]) is regime_on(spy, days[-1])


def test_regime_gates_new_picks_end_to_end():
    # DIP sets up on day 229 (see test_strategy_a.test_dip_in_uptrend_hand_computed).
    days = session_days(230)
    dipper = hist("DIP", dip(uptrend(230), 229), days=days)
    d = days[229]
    cases = {
        "spy rising": (hist(REGIME_SYMBOL, uptrend(230), days=days), True),
        "spy flat (close == SMA)": (flat_spy(230, days=days), False),
        "spy falling": (hist(REGIME_SYMBOL, uptrend(230, first=200.0, step=-0.1), days=days), False),
        "spy missing": (None, False),
    }
    for name, (spy, on) in cases.items():
        history = {"DIP": dipper} if spy is None else {"DIP": dipper, REGIME_SYMBOL: spy}
        prepared = STRATEGY_A2.prepare(history)
        assert prepared.regime_on(d) is on, name
        for p in every():
            got = STRATEGY_A2.picks(history, {"DIP"}, d, p)
            expected = ["DIP"] if (on or p.variant == "control") else []
            assert symbols(got) == expected, (name, p.variant)
            assert STRATEGY_A2.picks_prepared(prepared, {"DIP"}, d, p) == got, (name, p.variant)


def test_regime_flag_gates_variants_at_the_feature_level():
    features = [feat("AAA", rsi=2.0), feat("BBB", rsi=1.0)]
    members = {"AAA", "BBB"}
    for p in every():
        assert symbols(picks_from_features_a2(features, members, p, True)) == ["BBB", "AAA"], p.variant
        off = picks_from_features_a2(features, members, p, False)
        assert symbols(off) == (["BBB", "AAA"] if p.variant == "control" else []), p.variant


# ---- V2: ATR% ranking ----------------------------------------------------------------------


def calm_features() -> list:
    # ATR/close: LOW 0.01; TIE_R, TIE_A, TIE_B 0.02 (exactly equal floats); HIGH 0.05.
    return [
        feat("TIE_B", close=50.0, atr=1.0, rsi=3.0),
        feat("HIGH", close=50.0, atr=2.5, rsi=0.5),
        feat("TIE_A", close=100.0, atr=2.0, rsi=3.0),
        feat("LOW", close=50.0, atr=0.5, rsi=9.0),
        feat("TIE_R", close=25.0, sma=20.0, atr=0.5, rsi=1.0),
    ]


def test_atr_pct_ties_are_exact_floats():
    assert 1.0 / 50.0 == 2.0 / 100.0 == 0.5 / 25.0
    assert 0.5 / 50.0 < 1.0 / 50.0 < 2.5 / 50.0


def test_calm_ranking_is_atr_pct_then_rsi_then_symbol():
    features = calm_features()
    members = {f.symbol for f in features}
    by_rsi = ["HIGH", "TIE_R", "TIE_A", "TIE_B", "LOW"]
    by_atr_pct = ["LOW", "TIE_R", "TIE_A", "TIE_B", "HIGH"]
    expected = {"control": by_rsi, "regime": by_rsi, "regime_calm": by_atr_pct, "regime_calm_floor": by_atr_pct}
    for p in every():
        assert symbols(picks_from_features_a2(features, members, p, True)) == expected[p.variant], p.variant
    # the picks themselves (brackets) are the same objects V0 would make, only reordered
    v0 = picks_from_features_a2(features, members, A2_DESIGN_PARAMS, True)
    v2 = picks_from_features_a2(features, members, A2Params(variant="regime_calm"), True)
    assert sorted(v0, key=lambda p: p.symbol) == sorted(v2, key=lambda p: p.symbol)


def test_calm_ranking_is_uncapped_and_input_order_free():
    features = calm_features()
    members = {f.symbol for f in features}
    p = A2Params(variant="regime_calm", rsi_max=100.0)
    forward = picks_from_features_a2(features, members, p, True)
    backward = picks_from_features_a2(list(reversed(features)), members, p, True)
    assert forward == backward and len(forward) == len(features)


# ---- V3: the $10 floor ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("close", "kept"),
    [
        (10.0, True),  # exactly 10.0000: inclusive
        (10.0001, True),
        (9.9999, False),
        (9.0, False),
    ],
)
def test_floor_at_exactly_ten(close, kept):
    f = feat("AAA", close=close, sma=5.0, atr=1.0)
    for p in every():
        got = picks_from_features_a2([f], {"AAA"}, p, True)
        expected = ["AAA"] if (kept or p.variant != "regime_calm_floor") else []
        assert symbols(got) == expected, (close, p.variant)


def test_floor_reads_the_close_not_the_limit():
    # close 10.0, ATR 1.0: limit = 9.5 < 10, but the floor is on the close, so it is kept.
    [pick] = picks_from_features_a2(
        [feat("AAA", close=10.0, sma=5.0, atr=1.0)], {"AAA"}, A2Params(variant="regime_calm_floor"), True
    )
    assert pick == Pick("AAA", P("10"), P("9.5"), P("10.5"), P("8"))


# ---- SPY is never a pick -------------------------------------------------------------------


def test_spy_is_never_a_pick_even_as_a_member():
    features = [feat(REGIME_SYMBOL, rsi=0.5), feat("AAA", rsi=2.0)]
    for p in every():
        assert symbols(picks_from_features_a2(features, {REGIME_SYMBOL, "AAA"}, p, True)) == ["AAA"], p.variant
        assert picks_from_features_a2(features[:1], {REGIME_SYMBOL}, p, True) == [], p.variant


def test_spy_is_never_a_pick_end_to_end():
    # SPY itself dips on day 229 and would pass Strategy A's setup; DIP does too.
    days = session_days(230)
    history = {
        REGIME_SYMBOL: hist(REGIME_SYMBOL, dip(uptrend(230), 229), days=days),
        "DIP": hist("DIP", dip(uptrend(230, first=80.0), 229), days=days),
    }
    d = days[229]
    members = frozenset(history)
    assert symbols(STRATEGY_A.picks(history, members, d, DESIGN_PARAMS)) == ["DIP", REGIME_SYMBOL]  # guard: v1 would
    prepared = STRATEGY_A2.prepare(history)
    assert prepared.regime_on(d) is True
    for a in (DESIGN_PARAMS, PERMISSIVE):
        for p in every(a):
            got = STRATEGY_A2.picks(history, members, d, p)
            assert symbols(got) == ["DIP"], p.variant
            assert STRATEGY_A2.picks_prepared(prepared, members, d, p) == got, p.variant


# ---- the contract set: V0 == v1, and picks_prepared == picks for every variant --------------


def contract_set() -> tuple[list[date], dict[str, History]]:
    """test_strategy_a's contract set plus SPY (regime on, off, on again) and a stock crossing $10."""
    days = session_days(320)
    return days, {
        "SAW": hist("SAW", sawtooth(320), days=days),
        "DIP": hist("DIP", dip(dip(dip(uptrend(320), 229), 260), 290, drop=2.0), days=days),
        "LATE": hist("LATE", sawtooth(260, first=40.0, up=0.9, down=0.5), days=days[60:]),
        "GAPPY": drop_days(hist("GAPPY", sawtooth(320, first=70.0), days=days), days[100:105] + [days[250]]),
        "GONE": hist("GONE", sawtooth(270, first=90.0), days=days[:270]),
        "THIN": hist("THIN", dip(uptrend(320), 229), days=days, volume=1000.0),
        "PENNY": hist("PENNY", sawtooth(320, first=7.5, up=0.06, down=0.04), days=days, spread=0.05, volume=5e6),
        REGIME_SYMBOL: hist(REGIME_SYMBOL, spy_closes(320), days=days, volume=1e8),
    }


def contract_members(days: list[date], d: date, *, spy: bool) -> frozenset[str]:
    out = {"SAW", "DIP", "LATE", "GAPPY", "GONE", "THIN", "PENNY"}
    if d < days[280]:
        out.discard("LATE")
    if days[240] <= d < days[260]:
        out.discard("SAW")
    if spy:
        out.add(REGIME_SYMBOL)
    return frozenset(out)


def test_contract_set_exercises_every_rule():
    # Guards the two contract tests below: the regime is on and off, the ATR% order differs from the
    # RSI order, and the floor drops a pick, on some data_date in the tested range.
    days, history = contract_set()
    prepared = STRATEGY_A2.prepare(history)
    on = [prepared.regime_on(d) for d in days[190:]]
    assert any(on) and not all(on)
    differs = {"regime": 0, "regime_calm": 0, "regime_calm_floor": 0}
    for d in days[190:]:
        members = contract_members(days, d, spy=False)
        picks = {p.variant: STRATEGY_A2.picks(history, members, d, p) for p in every(PERMISSIVE)}
        differs["regime"] += picks["regime"] != picks["control"]
        differs["regime_calm"] += bool(picks["regime_calm"]) and picks["regime_calm"] != picks["regime"]
        differs["regime_calm_floor"] += picks["regime_calm_floor"] != picks["regime_calm"]
    assert all(n > 0 for n in differs.values()), differs


@pytest.mark.parametrize("a", A_PARAMS, ids=A_IDS)
def test_v0_picks_equal_strategy_a_picks(a):
    days, history = contract_set()
    v0 = A2Params.from_a("control", a)
    prepared_a = STRATEGY_A.prepare(history)
    prepared_a2 = STRATEGY_A2.prepare(history)
    nonempty = 0
    for d in days[190:]:
        members = contract_members(days, d, spy=False)
        expected = STRATEGY_A.picks(history, members, d, a)
        assert STRATEGY_A2.picks(history, members, d, v0) == expected, d
        assert STRATEGY_A2.picks_prepared(prepared_a2, members, d, v0) == expected, d
        assert STRATEGY_A.picks_prepared(prepared_a, members, d, a) == expected, d
        nonempty += bool(expected)
    assert nonempty > 0


@pytest.mark.parametrize("a", A_PARAMS, ids=A_IDS)
@pytest.mark.parametrize("variant", VARIANTS)
def test_picks_prepared_equals_picks_on_every_date(variant, a):
    days, history = contract_set()
    params = A2Params.from_a(variant, a)
    prepared = STRATEGY_A2.prepare(history)
    assert isinstance(prepared, A2Prepared)
    nonempty = 0
    for d in days[190:]:
        visible = upto_all(history, d)
        assert prepared.regime_on(d) is regime_on(visible[REGIME_SYMBOL], d), d  # bit-identical SMA
        members = contract_members(days, d, spy=d >= days[300])  # SPY listed as a member near the end
        expected = STRATEGY_A2.picks(visible, members, d, params)
        assert STRATEGY_A2.picks_prepared(prepared, members, d, params) == expected, d
        assert STRATEGY_A2.picks(history, members, d, params) == expected, d  # later bars ignored
        assert REGIME_SYMBOL not in symbols(expected), d
        nonempty += bool(expected)
    assert nonempty > 0


def test_prepared_regime_equals_regime_on_on_every_spy_date():
    days, history = contract_set()
    spy = history[REGIME_SYMBOL]
    prepared = STRATEGY_A2.prepare(history)
    assert prepared.regime_dates.tolist() == days[199:]
    assert prepared.regime.dtype == np.bool_ and prepared.regime.shape == prepared.regime_dates.shape
    for d in days:
        assert prepared.regime_on(d) is regime_on(spy, d), d
        assert prepared.regime_on(d) is regime_on(spy.upto(d), d), d


def test_prepare_on_short_or_empty_history_or_without_spy():
    d = date(2019, 6, 3)
    short = {"X": hist("X", sawtooth(150)), REGIME_SYMBOL: hist(REGIME_SYMBOL, uptrend(150))}
    for history in ({}, short):
        prepared = STRATEGY_A2.prepare(history)
        assert prepared.regime_dates.shape == (0,) and prepared.regime_on(d) is False
        for p in every(PERMISSIVE):
            assert STRATEGY_A2.picks_prepared(prepared, {"X"}, d, p) == []
            assert STRATEGY_A2.picks(history, {"X"}, d, p) == []
    days, history = contract_set()
    no_spy = {s: h for s, h in history.items() if s != REGIME_SYMBOL}
    prepared = STRATEGY_A2.prepare(no_spy)
    d = days[229]
    members = contract_members(days, d, spy=False)
    v0 = A2Params.from_a("control", PERMISSIVE)
    assert STRATEGY_A2.picks_prepared(prepared, members, d, v0) == STRATEGY_A.picks(no_spy, members, d, PERMISSIVE) != []
    for p in every(PERMISSIVE)[1:]:
        assert STRATEGY_A2.picks(no_spy, members, d, p) == STRATEGY_A2.picks_prepared(prepared, members, d, p) == []


# ---- no look-ahead, SPY's bars included ----------------------------------------------------


def lookahead_set() -> dict[str, History]:
    """test_strategy_a's look-ahead set plus a rising SPY (regime on from day 199)."""
    days = session_days(260)
    return {
        "DIP": hist("DIP", dip(uptrend(260), 229), days=days),
        "DIP2": hist("DIP2", dip(dip(uptrend(260, first=80.0, step=0.15), 240), 250, days=3), days=days),
        "SAW": hist("SAW", sawtooth(260), days=days),
        REGIME_SYMBOL: hist(REGIME_SYMBOL, uptrend(260, first=200.0, step=0.2), days=days, volume=1e8),
    }


def halve(x: np.ndarray) -> np.ndarray:
    return x * 0.5


@pytest.mark.parametrize("mutation", ["change", "halve", "truncate", "spy_only_halve", "spy_only_truncate"])
def test_no_look_ahead(mutation):
    """Changing (or deleting) every bar dated on or after S, SPY's included, leaves S's picks unchanged."""
    history = lookahead_set()
    days = session_days(260)
    prepared = STRATEGY_A2.prepare(history)
    members = frozenset(history) - {REGIME_SYMBOL}
    nonempty = {v: 0 for v in VARIANTS}
    for s in days[200:]:
        data_date = prev_session(s)
        if mutation == "change":
            future = {k: mutate_from(h, s) for k, h in history.items()}
        elif mutation == "halve":
            future = {k: mutate_from(h, s, halve) for k, h in history.items()}
        elif mutation == "truncate":
            future = {k: truncate_before(h, s) for k, h in history.items()}
        elif mutation == "spy_only_halve":
            future = {**history, REGIME_SYMBOL: mutate_from(history[REGIME_SYMBOL], s, halve)}
        else:
            future = {**history, REGIME_SYMBOL: truncate_before(history[REGIME_SYMBOL], s)}
        future_prepared = STRATEGY_A2.prepare(future)
        assert future_prepared.regime_on(data_date) is prepared.regime_on(data_date), s
        for a in (DESIGN_PARAMS, PERMISSIVE):
            for p in every(a):
                before = STRATEGY_A2.picks(history, members, data_date, p)
                assert STRATEGY_A2.picks(future, members, data_date, p) == before, (s, p.variant)
                assert STRATEGY_A2.picks_prepared(future_prepared, members, data_date, p) == before, (s, p.variant)
                assert STRATEGY_A2.picks_prepared(prepared, members, data_date, p) == before, (s, p.variant)
                nonempty[p.variant] += a is DESIGN_PARAMS and bool(before)
    assert all(n >= 2 for n in nonempty.values()), nonempty  # the setup fired for every variant: not vacuous


def test_the_spy_mutation_does_change_later_regime_and_picks():
    # Guards test_no_look_ahead: the same SPY mutation, read at data_date = S, turns the regime off
    # and empties V1..V3's picks, while V0 (which ignores SPY) is unchanged.
    history = lookahead_set()
    s = session_days(260)[229]
    members = frozenset(history) - {REGIME_SYMBOL}
    future = {**history, REGIME_SYMBOL: mutate_from(history[REGIME_SYMBOL], s, halve)}
    assert regime_on(history[REGIME_SYMBOL], s) is True
    assert regime_on(future[REGIME_SYMBOL], s) is False
    assert STRATEGY_A2.prepare(future).regime_on(s) is False
    for p in every():
        before = STRATEGY_A2.picks(history, members, s, p)
        after = STRATEGY_A2.picks(future, members, s, p)
        assert symbols(before) == ["DIP"], p.variant
        assert after == (before if p.variant == "control" else []), p.variant


def test_the_full_mutation_does_change_later_picks():
    # Guards test_no_look_ahead for the stocks' bars, as test_strategy_a does for v1.
    history = lookahead_set()
    s = session_days(260)[230]
    future = {k: mutate_from(h, s) for k, h in history.items()}
    members = frozenset(history) - {REGIME_SYMBOL}
    for p in every(PERMISSIVE):
        assert STRATEGY_A2.picks(future, members, s, p) != STRATEGY_A2.picks(history, members, s, p), p.variant
```
**Impact:** +62 tests. Runtime is about 21 s for the file, most of it the 5 `test_no_look_ahead` cases at about 2.4 s each.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/strategy-a-rework && engine/.venv/bin/python -c "import seer_engine.strategies as s; print(s.STRATEGY_A2.id, s.VARIANTS)"`, which should print `A2 ('control', 'regime', 'regime_calm', 'regime_calm_floor')`.
**Tests:**
- Phase file: `engine/.venv/bin/pytest engine/tests/test_strategy_a2.py engine/tests/test_strategy_a.py engine/tests/test_strategy_a_frozen.py engine/tests/test_strategy_purity.py -q`
- Full suite: `docker start seer-pg && PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q -rs`

**Expected count:** **660 passed, 0 skipped**, which is 598 baseline + 62 new. Phase 2 may land in parallel and adds 13: if phase 2 landed first, this phase takes the suite from 611 to **673**. After both, the total is 673 whichever order they land in (plan index invariant 1).

**Manual check:** `git diff --stat` shows exactly the 3 files above. `git diff engine/src/seer_engine/strategies/a.py engine/src/seer_engine/strategies/base.py engine/src/seer_engine/strategies/indicators.py` is empty.

**Exit criteria:**
- `a2.py` exists per the contract.
- `seer_engine.strategies` re-exports the 7 names.
- `test_strategy_a2.py` passes.
- The purity tests pass with `a2.py` in the glob.
- The full suite is green with 0 skipped.
- `a.py`, `base.py` and `indicators.py` are byte-identical to `e14de0c`.

## Handoffs

- **Phase 3 (walkforward):** `combinations()` should build with `A2Params.from_a(variant, p)` for `variant in VARIANTS`, `p in tuning.grid()`, with the variant loop outer. The per-variant fallback is `A2Params(variant=v)`, and the combined fallback is `A2_DESIGN_PARAMS`. Pass `STRATEGY_A2.prepare(market.history)` once as `prepared=`. It is variant- and param-independent.
- **Phase 2 (runner):** nothing is required from this phase. `run_backtest` already calls `strategy.picks_prepared(prepared, members, data_date, params)` with whatever params object it is given. With a `ParamsSchedule`, it must pass `schedule.at(S)`, which is an `A2Params`, never the schedule itself, because `_check_params` raises `TypeError` otherwise.
- **Phase 4/5 (report/command):** `A2Params.as_dict()` is the serialization: `variant` first, then plain decimal strings. Use it for the `last-fold-params` and `frozen-params` JSON lines and the grid CSV columns, so the frozen test in Phase 6 can compare dicts.
- **Phase 6 (freeze):**
  - It owns the `STRATEGY_A2_PARAMS` value and its comment block. The placeholder comment is the **two** lines directly above `STRATEGY_A2_PARAMS: A2Params | None = None` in `a2.py` (`# Set by phase 6 ONLY if the P3b gate passes, ...` and `# the report (tests/test_strategy_a2_frozen.py ties the two). ...`); replace those three lines together. The `A2_DESIGN_PARAMS = A2Params()` line above them stays. `Decimal` is already imported (`from decimal import Decimal`).
  - `seer_engine.strategies.STRATEGY_A2_PARAMS` is a re-export bound at import time, so it picks up the new value automatically.
  - Phase 6 also writes the `package_readme.md` `strategies` section for A2, which this phase does not touch.
- **Not done, deliberately:** `test_strategy_purity.test_the_glob_finds_the_strategy_modules` could list `seer_engine.strategies.a2` explicitly. It is not edited, because the glob already covers the module and the test file is not in this phase's scope. An optional drive-by for Phase 6.

## Rollback

`git revert <phase-1 commit>`, or delete `strategies/a2.py` and `tests/test_strategy_a2.py`
and restore `strategies/__init__.py` to `e14de0c`. Nothing else in the tree references A2
until Phase 3, so Phase 1 can be undone on its own only before Phase 3 lands.
