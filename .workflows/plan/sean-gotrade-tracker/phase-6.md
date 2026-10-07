# Phase 6: Engine: Gotrade fee schedule as a cost-model lever

**Plan set:** `SEAN_GOTRADE_TRACKER_PLAN.md`
**Analysis:** `20261007-222658-S3AN_code_analyzer.md`
**Satisfies:** R5 — real Gotrade costs feed method exploration and the Sera lab's profit and loss
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/sim` (plus `engine/src/seer_engine/backtest`)

---

## Goal

The engine gets a Gotrade fee schedule (`sim/costs.py`) fitted to the owner's 30 real receipts:
every receipt from the current regime (since 2026-06-16) comes out to the cent, and so does every
older one except a single documented outlier. A new `TradeRules.cost_model` lever (`"flat"` |
`"gotrade"`, default `"flat"`, registered in `LEVERS_SINCE_PINS`) lets a book rule set pay that
schedule instead of the assumed 0.1%. The book engine solves the non-linear fee exactly, and
the lab's SPY benchmark pays the same model as the candidate. No pinned digest moves: every
committed lab trial, registry pin and paper spec digest canonicalizes byte for byte as before,
and a new test proves it row by row.

## The fit (read this before the code)

Source: `.workflows/plan/sean-gotrade-tracker/screenshots_truth.json` (30 receipts, 29 buys and
1 sell). It was replayed against the schedule below in a scratch copy of the tree: 29 of 30 match
to the cent, and all 23 receipts in the current regime match.

| Regime `since` | Trading fee | Regulatory fee | PPN | Receipts |
|---|---|---|---|---|
| 2025-06-10 | none | 0.3% of amount, **rounded up**, uncapped | none | 2 buys |
| 2025-06-26 | 0.3%, **half-up**, min $0.10 | 0.054% **rounded up**, cap **$0.10**; sells + 0.04% up | 11% | 2 buys |
| 2026-03-25 | 0.3%, half-up, min $0.10 | 0.054% up, cap **$0.11**; sells + 0.04% up | 11% | 3 buys (LLY outlier) |
| **2026-06-16 (current)** | **0.2%**, half-up, min $0.10 | 0.054% up, cap $0.11; sells + 0.04% up | 11% | 22 buys + 1 sell |

- **Amount** is price × shares rounded half-up to the cent, with a floor of $0.01 when it is
  above zero, so a sub-cent sliver is never free. An amount of exactly 0 pays nothing.
- **Trading, half-up and not up:** GE $147.55 × 0.3% = 0.44265 was printed as $0.44. The
  minimum applies after rounding: every $27.90 buy shows 0.0558, printed as $0.10.
- **Regulatory rate:** with rounding up, any rate in (0.0475%, 0.0542%] reproduces $0.02 at
  $27.90, $0.06 at $105.27 and $0.08 at $147.55. We use **0.054%**, near the top of that band,
  to stay conservative. The cap moved from $0.10 (2025) to $0.11 (2026).
- **PPN = 11% × (printed trading + printed regulatory), rounded HALF-DOWN.** This is the only
  rounding that fits all 30 receipts:
  - Half-up fits 29 and fails WDC 2026-06-16: 2.39 + 0.11 = 2.50, × 0.11 = 0.275, printed $0.27.
  - Computing PPN on the unrounded fees fails SPY 2025-06-26.
  - Taking PPN per fee and summing fails LRCX 2026-03-25.
- **Sell side, one data point** (PLTR $72.51 paid $0.07 regulatory). The model is the buy-side
  formula ($0.04) plus an **uncapped sell-only 0.04%, rounded up** ($0.03). Any rate in
  (0.0276%, 0.0413%] fits; 0.04% is near the top. Leaving it uncapped is the cautious reading of
  a single point. This part stands in for the SEC fee, the FINRA TAF and whatever Gotrade adds.
  The statutory SEC fee alone is about 0.003%, so this is deliberately high until more sells
  arrive (Phase 7's `calibrate` prints the residuals).
- **LLY 2026-03-25 $366.62 paid $1.08, where the schedule says $1.10.** That is 0.2946%. It
  matches exactly 0.3% of $360.00, as if the fee were charged on the requested notional rather
  than the fill. It is tolerated: the schedule overcharges this receipt by $0.02, which errs on
  the side of cost. The test pins it as the only anomaly.
- **Which regime a backtest uses:** `on=None` means the current regime. Every simulated trade
  on every historical date uses today's schedule, because the lab asks what a method would cost
  the owner now. Regime `since` dates are the first receipt seen under each regime, not
  Gotrade's announcement dates.

Cost of the exact solve: `gotrade_shares_for` bisects between a count that surely fits and one
that surely does not. That takes about 20 µs per call, against about 2 µs for one `fee_parts`.
The flat path pays one extra `if` per money function.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `seer_engine.sim.costs` (new module `engine/src/seer_engine/sim/costs.py`):
  - `CostModel = Literal["flat", "gotrade"]`, `COST_MODELS = ("flat", "gotrade")`
  - `Side = Literal["buy", "sell"]`, `SIDES`, `CENT`
  - `FeeParts(trading, regulatory, ppn, total)`, a frozen dataclass of Decimals; `total` is a
    real field and is validated to equal the sum
  - `FeeRegime(since, trading_rate, trading_min, regulatory_rate, regulatory_cap,
    sell_extra_rate, ppn_rate)` with `.fees(side, amount) -> FeeParts`
  - `GotradeSchedule(regimes)` with `.current`, `.regime_on(on: date | None)` and
    `.fee_parts(side, amount, on=None)`
  - `GOTRADE: GotradeSchedule`, the fitted schedule
  - `fee_parts(side, amount, on=None) -> FeeParts`, the public API Phase 7 replays receipts with
  - `gotrade_cash(side, price, shares) -> (cash, fee)`, one simulated order at the current regime
  - `gotrade_shares_for(budget, price, quantum) -> Decimal`, the exact inverse; never overspends
- `TradeRules.cost_model: CostModel = "flat"`, a new last field in `sim/rules.py`
- `LEVERS_SINCE_PINS["cost_model"] = "flat"`
- `sim.rules._usd` and `sim.rules._gotrade_costs_line`, both private
- `backtest.benchmark._whole_buy_cost`, private
- `engine/tests/fixtures/gotrade_fees.json`, fee-only rows
- `engine/tests/test_sim_costs.py` and `engine/tests/test_cost_model_pins.py`

**Signature changes** (every new parameter defaults to the old behavior):
- `sim.book._fee(price, shares, rules)` -> `_fee(price, shares, rules, side)`. It is private
  and its 3 call sites are in `book.py`.
- `backtest.benchmark._whole_shares(cash, price)` -> `_whole_shares(cash, price, cost_model="flat")`
- `backtest.benchmark._fractional_shares(cash, price)` -> `_fractional_shares(cash, price, cost_model="flat")`.
  `paper/benchmark.py` calls it positionally with 2 arguments, which still works.
- `backtest.benchmark.fractional_buy_cost(price, shares)` -> `fractional_buy_cost(price, shares, cost_model="flat")`.
  This is the same case: `paper/benchmark.py` calls it with 2 arguments.
- `backtest.benchmark.buy_and_hold(..., fractional=False)` -> `buy_and_hold(..., fractional=False, cost_model="flat")`
- `backtest.benchmark.spy_curves(spy, start, end, initial_cash, dividends)` -> `spy_curves(..., dividends, *, cost_model="flat")`

**Behavior changes:**
- `backtest.dev._run` now passes `cost_model=c.rules.cost_model` to `spy_curves`. Under flat
  rules nothing changes.
- `TradeRules.__post_init__` validates `cost_model`. `"gotrade"` requires `cost_rate == 0.001`.
- A `TradeRules` repr now ends with `, cost_model='flat')`. That repr is used only in
  `dev_report._rules_literal` and in one test string.

**Requires (from earlier phases):** nothing.

**Provides to Phase 7:**
- `from seer_engine.sim.costs import fee_parts, GOTRADE, FeeParts`.
- `fee_parts(side, Decimal(amount), on=executed_date)` replays a receipt.
- `GOTRADE.current.since` is the start date of the "current regime".
- `dataclasses.replace(c.rules, cost_model="gotrade")` derives a real-cost copy of any book rule
  set at the default `cost_rate`. It raises `ValueError` for `DESIGN_V0`.
- `dev.run_candidate` / `dev.run_registry` with such a candidate charges the SPY benchmark
  Gotrade fees automatically.

**Leaves alone (owned by others):**
- `sim/model.py` (`COST_RATE` semantics), `sim/sizing.py`, `sim/lifecycle.py`: the
  `DESIGN_V0` bracket engine.
- `paper/*`: `paper/benchmark.py` and `paper/replay.py` keep calling the flat defaults.
- `lab/*`, `commands/*`: Phase 4 and Phase 7.
- `web/*`.
- `docs/plans/2026-10-03-seer-design.md`: Phase 7.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/sim/costs.py` | create | the fitted schedule, `fee_parts`, `gotrade_cash`, `gotrade_shares_for` |
| `engine/src/seer_engine/sim/rules.py` | modify | import (`:32`), `cost_model` field (`:86`), validation (after `:124`), `_V0_LEVERS` (`:137-150`), `LEVERS_SINCE_PINS` (`:213-215`), `rule_owner_inputs` (`:289-306`), `describe_rules` cost line + 2 helpers (`:395-396`) |
| `engine/src/seer_engine/sim/book.py` | modify | docstring (`:8-9`), import (`:56`), money functions (`:335-362`), the 3 `_fee` call sites (`:408`, `:614`, `:680`) |
| `engine/src/seer_engine/backtest/benchmark.py` | modify | docstring (`:20`), import (`:32`), `_whole_shares`/`_fractional_shares`/`fractional_buy_cost` (`:104-125`), new `_whole_buy_cost`, `buy_and_hold` (`:139-213`), `spy_curves` (`:216-226`) |
| `engine/src/seer_engine/backtest/dev.py` | modify | `_run` passes the candidate's cost model to `spy_curves` (`:433`) |
| `engine/src/seer_engine/backtest/book_runner.py` | modify | docstrings only (`:429-430`, `:518-520`): `costs_usd` is already model-aware through `Fill.cost_usd` |
| `engine/tests/fixtures/gotrade_fees.json` | create | 30 fee-only rows |
| `engine/tests/test_sim_costs.py` | create | the fit, rule by rule, plus exactness of `gotrade_shares_for` |
| `engine/tests/test_cost_model_pins.py` | create | invariant 2: every committed lab trial digest recomputes; flat is absent from canonical text; gotrade digests differently |
| `engine/tests/test_sim_rules.py` | modify | preset pin (`:82-86`), `LEVERS_SINCE_PINS` pin (`:404`), 4 new tests appended |
| `engine/tests/test_sim_book.py` | modify | 4 new tests appended (gotrade buys and sells, $28 slots, whole shares, forced close) |
| `engine/tests/test_benchmark.py` | modify | 4 new tests appended |
| `engine/tests/test_backtest_dev.py` | modify | 1 new test before `test_window_before_fx_start_converts_at_the_fx_start_rate` (`:412`) |
| `engine/tests/test_backtest_dev_report.py` | modify | the `TradeRules(...)` repr string gains `cost_model='flat'` (`:567-570`) |

## Implementation Steps

### Step 0: Worktree venv

The worktree has no `engine/.venv`, and main's venv would test the wrong tree:

```bash
cd /home/miftah/.worktrees/seer/sean-gotrade-tracker
python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'
```

### Step 1: The fee schedule module
**File:** `engine/src/seer_engine/sim/costs.py` (new)
**Change:** Create the whole file below. It imports only `seer_engine.sim.model.q`, so there is
no import cycle: `sim/__init__` loads `book`, which loads `model`, then `rules`, then `costs`,
and `model` is already loaded by then. It reads no clock and uses no floats, which
`test_sim_purity` enforces.
**Code:**
```python
"""Gotrade's fee schedule, fitted to the owner's real order receipts (Sean plan, phase 6).

Until 2026-10-07 every simulated trade paid one assumed number, ``TradeRules.cost_rate`` (0.1%
per side). The owner's 30 Gotrade order receipts (``tests/fixtures/gotrade_fees.json``, fee
columns only) show what an order really costs, and at the sizes the owner trades (a few tens of
dollars a slot) it is 3-5x that. This module is that schedule, as data plus one pure function.

One order of ``amount`` dollars (price × shares, rounded half-up to the cent) pays three
separately printed fees, each in cents:

- **trading fee**: ``trading_rate × amount`` rounded half-up to the cent, at least
  ``trading_min`` (only when ``trading_rate > 0``);
- **regulatory fee**: ``regulatory_rate × amount`` rounded UP to the cent, at most
  ``regulatory_cap``; a sell adds ``sell_extra_rate × amount`` rounded up to the cent, uncapped
  (the sell-side SEC fee + FINRA TAF + whatever Gotrade adds; see the fit below);
- **PPN** (Indonesian VAT): ``ppn_rate × (trading + regulatory)`` rounded HALF-DOWN to the cent.

A buy pays ``amount + total``; a sell receives ``amount − total``.

The fit (every number reproduced by ``tests/test_sim_costs.py``):

- 2025-06-10 (2 buys): no trading fee, no PPN; a 0.3% "regulatory" fee rounded up
  ($707.31 -> $2.13, $1,429.00 -> $4.29).
- 2025-06-26 .. 2025-07-22 (2 buys): trading 0.3% half-up ($1,832.90 -> $5.50, $592.41 ->
  $1.78); regulatory capped at $0.10.
- 2026-03-25 (3 buys): trading 0.3% half-up. Half-up, not up: $147.55 -> $0.44 (0.44265). The
  regulatory fee is 0.054% rounded up and capped at $0.11: $27.90 -> $0.02, $105.27 -> $0.06,
  $147.55 -> $0.08, $366.62 -> $0.11. Any rate in (0.0475%, 0.0542%] fits these with
  rounding up; 0.054% is the top of that band (conservative). LLY $366.62 paid $1.08, not the
  schedule's $1.10 (0.2946%, the only receipt off the schedule; it matches 0.3% of $360.00, as if
  the fee were taken on the order's requested notional): the schedule charges $0.02 more there,
  which errs on the side of cost.
- 2026-06-16 onward, the CURRENT regime (23 receipts: 22 buys, 1 sell): trading 0.2% half-up,
  minimum $0.10 (every $27.90 buy pays $0.10); regulatory as above, cap $0.11.
- PPN: 11% of (trading + regulatory), both as printed, rounded HALF-DOWN. Half-up fits 29 of 30
  and fails WDC 2026-06-16 ($2.39 + $0.11 = $2.50 -> 0.275 printed as $0.27); half-down fits
  all 30. Rounding the unrounded fees instead fails SPY 2025-06-26; rounding each fee's PPN
  separately fails LRCX 2026-03-25.
- Sells: ONE receipt (PLTR 2026-10-07, $72.51: trading $0.15, regulatory $0.07, PPN $0.02). The
  buy-side regulatory formula gives $0.04; the remaining $0.03 is modelled as an uncapped
  sell-only ``sell_extra_rate`` of 0.04%, rounded up. Any rate in (0.0276%, 0.0413%] fits; 0.04%
  sits near the top (conservative), and uncapped is the cautious reading of one data point. The
  statutory SEC fee alone is ~0.003%: this is far above it on purpose until more sells arrive
  (``seer sean calibrate`` reports every receipt's residual against this schedule).

Regime dates are the first receipt seen under each regime, not Gotrade's announcement dates:
an order between two receipts is priced by the earlier regime. ``on=None`` means the current
(latest) regime, which is what every backtest uses for every simulated date: the lab asks what
a method would cost the owner now, not what it would have cost in 2012.

Pure: no clock, no I/O, no floats.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_FLOOR, ROUND_HALF_DOWN, ROUND_HALF_UP, ROUND_UP, Decimal
from typing import Literal

from seer_engine.sim.model import q

CostModel = Literal["flat", "gotrade"]
COST_MODELS: tuple[str, ...] = ("flat", "gotrade")
Side = Literal["buy", "sell"]
SIDES: tuple[str, ...] = ("buy", "sell")
CENT = Decimal("0.01")
_ZERO = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class FeeParts:
    """One order's fees as Gotrade prints them, in dollars to the cent. ``total`` is their sum."""

    trading: Decimal
    regulatory: Decimal
    ppn: Decimal
    total: Decimal

    def __post_init__(self) -> None:
        for name in ("trading", "regulatory", "ppn", "total"):
            v = getattr(self, name)
            if not isinstance(v, Decimal):
                raise TypeError(f"{name} must be a Decimal, got {type(v).__name__}")
            if not v.is_finite() or v < 0:
                raise ValueError(f"{name} must be a finite amount >= 0, got {v}")
        if self.total != self.trading + self.regulatory + self.ppn:
            raise ValueError(
                f"total {self.total} != trading {self.trading} + regulatory {self.regulatory} + ppn {self.ppn}"
            )


@dataclass(frozen=True, slots=True)
class FeeRegime:
    """Gotrade's fees from ``since`` until the next regime (see the module docstring)."""

    since: date
    trading_rate: Decimal
    trading_min: Decimal
    regulatory_rate: Decimal
    regulatory_cap: Decimal | None
    sell_extra_rate: Decimal
    ppn_rate: Decimal

    def __post_init__(self) -> None:
        if isinstance(self.since, datetime) or not isinstance(self.since, date):
            raise TypeError(f"since must be a date, got {type(self.since).__name__}")
        for name in ("trading_rate", "trading_min", "regulatory_rate", "sell_extra_rate", "ppn_rate"):
            v = getattr(self, name)
            if not isinstance(v, Decimal):
                raise TypeError(f"{name} must be a Decimal, got {type(v).__name__}")
            if not v.is_finite() or v < 0:
                raise ValueError(f"{name} must be a finite value >= 0, got {v}")
        if self.regulatory_cap is not None:
            if not isinstance(self.regulatory_cap, Decimal):
                raise TypeError(f"regulatory_cap must be a Decimal or None, got {type(self.regulatory_cap).__name__}")
            if not self.regulatory_cap.is_finite() or self.regulatory_cap <= 0:
                raise ValueError(f"regulatory_cap must be > 0, got {self.regulatory_cap}")

    def fees(self, side: Side, amount: Decimal) -> FeeParts:
        """The fees of one ``side`` order of ``amount`` dollars under this regime."""
        raw = _amount(amount)
        if side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {side!r}")
        if raw == 0:
            return FeeParts(_ZERO, _ZERO, _ZERO, _ZERO)
        # Any real order is at least a cent: a sub-cent sliver of a share is never free.
        cents = max(raw.quantize(CENT, rounding=ROUND_HALF_UP), CENT)
        trading = (cents * self.trading_rate).quantize(CENT, rounding=ROUND_HALF_UP)
        if self.trading_rate > 0 and trading < self.trading_min:
            trading = self.trading_min.quantize(CENT)
        regulatory = (cents * self.regulatory_rate).quantize(CENT, rounding=ROUND_UP)
        if self.regulatory_cap is not None and regulatory > self.regulatory_cap:
            regulatory = self.regulatory_cap.quantize(CENT)
        if side == "sell":
            regulatory += (cents * self.sell_extra_rate).quantize(CENT, rounding=ROUND_UP)
        ppn = ((trading + regulatory) * self.ppn_rate).quantize(CENT, rounding=ROUND_HALF_DOWN)
        return FeeParts(trading, regulatory, ppn, trading + regulatory + ppn)


@dataclass(frozen=True, slots=True)
class GotradeSchedule:
    """Gotrade's fee regimes, oldest first. ``regime_on(None)`` is the current (last) one."""

    regimes: tuple[FeeRegime, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.regimes, tuple) or not self.regimes:
            raise ValueError("regimes must be a non-empty tuple")
        for r in self.regimes:
            if not isinstance(r, FeeRegime):
                raise TypeError(f"regimes must hold FeeRegime values, got {type(r).__name__}")
        for a, b in zip(self.regimes, self.regimes[1:]):
            if b.since <= a.since:
                raise ValueError(f"regimes must be strictly ascending by since: {b.since} after {a.since}")

    @property
    def current(self) -> FeeRegime:
        return self.regimes[-1]

    def regime_on(self, on: date | None) -> FeeRegime:
        """The regime in force on ``on`` (the last one whose ``since <= on``); None = current.

        ValueError when ``on`` is before the first regime (no receipt says what Gotrade
        charged then).
        """
        if on is None:
            return self.regimes[-1]
        if isinstance(on, datetime) or not isinstance(on, date):
            raise TypeError(f"on must be a date or None, got {type(on).__name__}")
        found: FeeRegime | None = None
        for r in self.regimes:
            if r.since <= on:
                found = r
        if found is None:
            raise ValueError(f"no Gotrade fee schedule is known before {self.regimes[0].since} (asked for {on})")
        return found

    def fee_parts(self, side: Side, amount: Decimal, on: date | None = None) -> FeeParts:
        return self.regime_on(on).fees(side, amount)


def _amount(amount: object) -> Decimal:
    """``amount`` as a Decimal; TypeError for a non-Decimal (floats refused), ValueError for a
    negative or non-finite one."""
    if isinstance(amount, bool) or not isinstance(amount, (Decimal, int)):
        raise TypeError(f"amount must be a Decimal, got {type(amount).__name__}")
    a = Decimal(amount)
    if not a.is_finite() or a < 0:
        raise ValueError(f"amount must be a finite dollar amount >= 0, got {amount}")
    return a


_PPN = Decimal("0.11")
_REG_RATE = Decimal("0.00054")
_SELL_EXTRA = Decimal("0.0004")
_MIN = Decimal("0.10")

GOTRADE = GotradeSchedule(
    regimes=(
        FeeRegime(
            since=date(2025, 6, 10),
            trading_rate=Decimal(0),
            trading_min=Decimal(0),
            regulatory_rate=Decimal("0.003"),
            regulatory_cap=None,
            sell_extra_rate=Decimal(0),
            ppn_rate=Decimal(0),
        ),
        FeeRegime(
            since=date(2025, 6, 26),
            trading_rate=Decimal("0.003"),
            trading_min=_MIN,
            regulatory_rate=_REG_RATE,
            regulatory_cap=Decimal("0.10"),
            sell_extra_rate=_SELL_EXTRA,
            ppn_rate=_PPN,
        ),
        FeeRegime(
            since=date(2026, 3, 25),
            trading_rate=Decimal("0.003"),
            trading_min=_MIN,
            regulatory_rate=_REG_RATE,
            regulatory_cap=Decimal("0.11"),
            sell_extra_rate=_SELL_EXTRA,
            ppn_rate=_PPN,
        ),
        FeeRegime(
            since=date(2026, 6, 16),
            trading_rate=Decimal("0.002"),
            trading_min=_MIN,
            regulatory_rate=_REG_RATE,
            regulatory_cap=Decimal("0.11"),
            sell_extra_rate=_SELL_EXTRA,
            ppn_rate=_PPN,
        ),
    )
)


def fee_parts(side: Side, amount: Decimal, on: date | None = None) -> FeeParts:
    """Gotrade's fees for one ``side`` ("buy"/"sell") order of ``amount`` dollars on ``on``
    (None: the current regime). ``amount`` is rounded half-up to the cent first (at least $0.01
    when it is above zero); an amount of exactly 0 pays nothing (there is no order)."""
    return GOTRADE.fee_parts(side, amount, on)


def gotrade_cash(side: Side, price: Decimal, shares: Decimal | int) -> tuple[Decimal, Decimal]:
    """``(cash, fee)`` of one simulated order at today's schedule: amount ``q(price × shares)``;
    a buy's cash out is ``amount + fee``; a sell's proceeds are ``amount − fee`` with the fee
    capped at the amount (a dust sale never costs more than it brings in)."""
    amount = q(price * shares)
    fee = fee_parts(side, amount).total
    if side == "sell":
        fee = min(fee, amount)
        return amount - fee, fee
    return amount + fee, fee


def gotrade_shares_for(budget: Decimal, price: Decimal, quantum: Decimal) -> Decimal:
    """The most shares, a multiple of ``quantum``, whose buy cash (``gotrade_cash("buy", …)``)
    is <= ``budget``; 0 when none fits. Exact: the minimum fee makes cost non-linear in shares,
    but it never falls as shares grow, so the answer is found by bisection between a count that
    surely fits (shares the budget less the budget's own fee buys) and one that surely does not
    (shares the whole budget buys, fees ignored)."""
    for name, value in (("budget", budget), ("price", price), ("quantum", quantum)):
        if not isinstance(value, Decimal):
            raise TypeError(f"{name} must be a Decimal, got {type(value).__name__}")
    if quantum <= 0:
        raise ValueError(f"quantum must be > 0, got {quantum}")
    if price <= 0:
        raise ValueError(f"price must be > 0, got {price}")
    if budget <= 0:
        return quantum * 0

    def fits(k: int) -> bool:
        return gotrade_cash("buy", price, quantum * k)[0] <= budget

    step = price * quantum
    hi = int((budget / step).to_integral_value(rounding=ROUND_FLOOR))
    room = budget - fee_parts("buy", q(budget)).total
    lo = int((room / step).to_integral_value(rounding=ROUND_FLOOR)) if room > 0 else 0
    lo = min(lo, hi)
    if lo > 0 and not fits(lo):
        lo = 0  # never expected (see above); bisection needs a count that fits
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if fits(mid):
            lo = mid
        else:
            hi = mid - 1
    return quantum * lo
```
**Impact:** None on its own. Nothing imports the module until Step 2.

### Step 2: The `cost_model` lever
**File:** `engine/src/seer_engine/sim/rules.py`

**2a. Import (`:32`).** Replace

```python
from seer_engine import dates
```

with

```python
from seer_engine import dates
from seer_engine.sim.costs import COST_MODELS, GOTRADE, CostModel
```

**2b. Field (`:86`).** Add a new last field after `cost_rate`. It must be last: `_V0_LEVERS` and
every repr follow field order.

```python
    idle_symbol: str | None = None
    cost_rate: Decimal = _DEFAULT_COST
    cost_model: CostModel = "flat"
```

**2c. Validation.** Insert directly after `:124`
(`raise ValueError(f"cost_rate must be in [0, {_MAX_COST}), got {self.cost_rate}")`) and before
`is_v0 = _lever_values(self) == _V0_LEVERS`:

```python
        if not isinstance(self.cost_model, str):
            raise TypeError(f"cost_model must be a str, got {type(self.cost_model).__name__}")
        if self.cost_model not in COST_MODELS:
            raise ValueError(f"unknown cost_model {self.cost_model!r}; expected one of {COST_MODELS}")
        if self.cost_model == "gotrade" and self.cost_rate != _DEFAULT_COST:
            raise ValueError(
                f"cost_model 'gotrade' prices every order from Gotrade's measured fee schedule "
                f"(sim.costs); cost_rate must stay at its default {_DEFAULT_COST}, got {self.cost_rate}"
            )
```

**2d. `_V0_LEVERS` (`:137-150`).** Append `"flat"`. `DESIGN_V0` stays the only `bracket_v0`
rule set, and `replace(DESIGN_V0, cost_model="gotrade")` now raises "reserved for DESIGN_V0",
so the bracket engine never sees Gotrade costs.

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
)
```

**2e. `LEVERS_SINCE_PINS` (`:213-215`).** This is the invariant-2 hinge.
`backtest.registry._canon` (`registry.py:323-332`) and `paper.roster.rules_dict`
(`roster.py:1030-1042`) already skip any field this dict maps to its current value. They need no
code change.

```python
LEVERS_SINCE_PINS: dict[str, object] = {
    "resize_cadence": None,  # the rank/resize cadence split, 2026-10-05
    "cost_model": "flat",  # Gotrade's measured fee schedule (sim.costs), 2026-10-07
}
```

**2f. `rule_owner_inputs` (`:289-306`).** Gotrade is not an owner input. Because it requires
the default `cost_rate`, the old check already gives the right answer. The guard below makes the
intent explicit. Replace the whole function:

```python
def rule_owner_inputs(rules: TradeRules) -> tuple[str, ...]:
    """The Gotrade features ``rules`` needs that the owner has not verified, sorted and unique.

    ``market-on-open`` (entry "open"), ``etf:<symbol>`` (an idle instrument outside
    ``DEFAULT_ETFS``) and ``fee`` (a flat cost rate other than 0.1% per side). Empty means
    executable under the conservative owner-input defaults. Fractional shares are not on the
    list: the owner verified that Gotrade takes fractional limit buys and sells (2026-10-07), and
    the paper roster already trades its lab winners that way. Neither is ``cost_model="gotrade"``:
    its schedule is fitted to the owner's own Gotrade receipts (``sim.costs``), and it requires
    the default ``cost_rate``, so it never raises ``fee`` either.
    """
    _rules(rules)
    out: set[str] = set()
    if rules.entry == "open":
        out.add("market-on-open")
    if rules.idle_symbol is not None and rules.idle_symbol not in DEFAULT_ETFS:
        out.add(f"etf:{rules.idle_symbol}")
    if rules.cost_model == "flat" and rules.cost_rate != _DEFAULT_COST:
        out.add("fee")
    return tuple(sorted(out))
```

**2g. `describe_rules` cost line (`:395-396`).** Keep 12 lines: the two cost fields share the
one "Costs:" line, and the flat text does not change, so the golden tests stay as they are.
Replace the last two lines of `describe_rules`

```python
    lines.append(f"Costs: {_pct(rules.cost_rate)} per side.")
    return tuple(lines)
```

with the following. Both helpers go at the end of the module.

```python
    if rules.cost_model == "gotrade":
        lines.append(_gotrade_costs_line())
    else:
        lines.append(f"Costs: {_pct(rules.cost_rate)} per side.")
    return tuple(lines)


def _usd(x: Decimal) -> str:
    """``x`` dollars to the cent: Decimal('0.1') -> '$0.10'."""
    return f"${x:.2f}"


def _gotrade_costs_line() -> str:
    """The plain-English line for ``cost_model="gotrade"``, read off the current regime so it
    can never drift from the numbers the simulator charges."""
    r = GOTRADE.current
    trading = f"a trading fee of {_pct(r.trading_rate)} of each order"
    if r.trading_min > 0:
        trading += f", at least {_usd(r.trading_min)}"
    regulatory = f"a regulatory fee of {_pct(r.regulatory_rate)} rounded up to the cent"
    if r.regulatory_cap is not None:
        regulatory += f", at most {_usd(r.regulatory_cap)}"
    if r.sell_extra_rate > 0:
        regulatory += f", plus {_pct(r.sell_extra_rate)} more on sells"
    return (
        f"Costs: Gotrade's fee schedule measured from the owner's receipts (in force since "
        f"{r.since.isoformat()}): {trading}; {regulatory}; and {_pct(r.ppn_rate)} VAT (PPN) on "
        f"those two fees."
    )
```

**Impact:**
- The `TradeRules` repr gains `cost_model='flat'`. One test string in
  `test_backtest_dev_report.py` has to change (Step 8).
- `test_sim_rules.py:404` pins `LEVERS_SINCE_PINS` and has to change (Step 8).
- `promote.fractional_twin` (`commands/promote.py:144`) compares every field except
  `id`/`fractional`. That still works, because every preset is flat.
- No digest moves (Step 8, `test_cost_model_pins.py`).

### Step 3: The book engine pays the model
**File:** `engine/src/seer_engine/sim/book.py`

**3a. Module docstring (`:8-9`).** Replace

```text
One session, in this exact order (all money ``Decimal``; ``q`` at every product; buy cash
``q(p × n × (1 + c))``, sell proceeds ``q(p × n × (1 − c))``, fee ``q(p × n × c)``):
```

with

```text
One session, in this exact order (all money ``Decimal``; ``q`` at every product; buy cash
``q(p × n × (1 + c))``, sell proceeds ``q(p × n × (1 − c))``, fee ``q(p × n × c)``; under
``rules.cost_model == "gotrade"`` instead buy cash ``q(p × n) + fee``, sell proceeds
``q(p × n) − fee``, the fee from Gotrade's current schedule, ``sim.costs.gotrade_cash``):
```

**3b. Import (`:56`).** Replace

```python
from seer_engine.sim.model import q
```

with

```python
from seer_engine.sim.costs import gotrade_cash, gotrade_shares_for
from seer_engine.sim.model import q
```

`Literal` is already imported at `:52`.

**3c. Money functions (`:335-362`).** Replace `_buy_cash`, `_sell_cash`, `_fee` and
`_shares_for` with the code below. `_desired_shares`, starting at `:365`, is unchanged.

```python
def _buy_cash(price: Decimal, shares: Decimal, rules: TradeRules) -> Decimal:
    if rules.cost_model == "gotrade":
        return gotrade_cash("buy", price, shares)[0]
    return q(price * shares * (_ONE + rules.cost_rate))


def _sell_cash(price: Decimal, shares: Decimal, rules: TradeRules) -> Decimal:
    if rules.cost_model == "gotrade":
        return gotrade_cash("sell", price, shares)[0]
    return q(price * shares * (_ONE - rules.cost_rate))


def _fee(price: Decimal, shares: Decimal, rules: TradeRules, side: Literal["buy", "sell"]) -> Decimal:
    """The fee part of one fill (``Fill.cost_usd``). ``side`` matters only under "gotrade"."""
    if rules.cost_model == "gotrade":
        return gotrade_cash(side, price, shares)[1]
    return q(price * shares * rules.cost_rate)


def _shares_for(budget: Decimal, price: Decimal, rules: TradeRules) -> Decimal:
    """The most shares whose unrounded buy cash ``price × n × (1 + c)`` fits ``budget``:
    whole shares (``sim.sizing._whole_shares``, step-back loop included) or, with
    ``rules.fractional``, multiples of ``SHARE_QUANTUM``. 0 when nothing fits.

    Under ``cost_model == "gotrade"`` the fee is not proportional (a $0.10 minimum, a capped
    regulatory fee), so the count is solved exactly: the most shares whose ROUNDED buy cash
    ``_buy_cash`` is <= ``budget`` (``sim.costs.gotrade_shares_for``); it never overspends."""
    if budget <= 0:
        return _ZERO
    if rules.cost_model == "gotrade":
        n = gotrade_shares_for(budget, price, SHARE_QUANTUM if rules.fractional else _ONE)
        return n if n > 0 else _ZERO
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
```

**3d. The three `_fee` call sites.** Each one gains its side:
- `:408` in `_close_out`: `cost_usd=_fee(exit_price, p.shares, rules, "sell"),`
- `:614` (trim):
  ```python
                  Fill(session, symbol, "sell", excess, price, proceeds, _fee(price, excess, rules, "sell"), "trim")
  ```
- `:680` (buy):
  ```python
                  Fill(session, symbol, "buy", shares, fill_price, -cost, _fee(fill_price, shares, rules, "buy"), fill_reason)
  ```

**Impact:**
- Under flat rules, every value is computed exactly as before.
- Under gotrade rules:
  - Sizing (night budgets, trims and adds through `_desired_shares`) and the cash guard at
    `:670-677` use the exact inverse, so `cost <= cash` holds by construction.
  - Every sell, forced closes included, nets the fee, capped at the amount.
  - `Fill.cost_usd` carries the Gotrade fee, so `BookResult.costs_usd`, `RunStats.costs_usd` and
    `cost_drag` report real costs with no further change.
- The cash-in-lieu fill in `apply_book_split` stays at cost 0, unchanged. A split is not an
  order.

### Step 4: The SPY benchmark pays the same model
**File:** `engine/src/seer_engine/backtest/benchmark.py`

**4a. Module docstring.** After the last bullet (`:20`, "Every NYSE session in the window must
have a SPY bar ..."), add:

```text
- ``cost_model="gotrade"`` (a lab method on Gotrade's measured fees, ``sim.costs``): every buy
  above, the first one and each dividend reinvestment, pays Gotrade's schedule instead of 0.1%,
  and the share count is the most whose rounded cash fits (``sim.costs.gotrade_shares_for``), so
  a method and its benchmark pay alike. The default "flat" is every curve above, unchanged.
```

**4b. Import (`:32`).** After `from seer_engine.sim import COST_RATE, Snapshot, buy_cost, q`, add

```python
from seer_engine.sim.costs import COST_MODELS, CostModel, gotrade_cash, gotrade_shares_for
```

**4c. Share counts and costs (`:104-125`).** Replace `_whole_shares`, `_fractional_shares` and
`fractional_buy_cost`, and add `_whole_buy_cost`. Every new parameter defaults to flat, so
`paper/benchmark.py:42,249-278`, which calls the 2-argument forms, is untouched.

```python
def _whole_shares(cash: Decimal, price: Decimal, cost_model: CostModel = "flat") -> int:
    """The most whole shares ``cash`` buys at ``price`` after the 0.1% cost (or, under
    "gotrade", after Gotrade's fees)."""
    if cost_model == "gotrade":
        return int(gotrade_shares_for(cash, price, Decimal(1)))
    n = int(cash // (price * (1 + COST_RATE)))
    # q() rounds half-up; never let the rounded cost exceed the cash.
    while n > 0 and buy_cost(price, n) > cash:
        n -= 1
    return n


def _fractional_shares(cash: Decimal, price: Decimal, cost_model: CostModel = "flat") -> Decimal:
    """The most shares ``cash`` buys at ``price`` after the 0.1% cost (or, under "gotrade",
    after Gotrade's fees), in multiples of ``SHARE_QUANTUM`` (0.0001): the paper benchmark
    (Gotrade sells SPY in fractions)."""
    if cost_model == "gotrade":
        n = gotrade_shares_for(cash, price, SHARE_QUANTUM)
        return n if n > 0 else Decimal(0)
    unit = price * (1 + COST_RATE)
    n = (cash / unit).quantize(SHARE_QUANTUM, rounding=ROUND_FLOOR)
    while n > 0 and fractional_buy_cost(price, n) > cash:
        n -= SHARE_QUANTUM
    return n if n > 0 else Decimal(0)


def fractional_buy_cost(price: Decimal, shares: Decimal, cost_model: CostModel = "flat") -> Decimal:
    """``buy_cost`` for a fractional share count: ``q(price × n × 1.001)``, or under "gotrade"
    ``q(price × n)`` plus Gotrade's fees (nothing for 0 shares)."""
    if cost_model == "gotrade":
        return gotrade_cash("buy", price, shares)[0]
    return q(price * shares * (1 + COST_RATE))


def _whole_buy_cost(price: Decimal, shares: int, cost_model: CostModel) -> Decimal:
    """``sim.buy_cost`` for whole shares, or under "gotrade" ``q(price × n)`` plus Gotrade's fees."""
    if cost_model == "gotrade":
        return gotrade_cash("buy", price, shares)[0]
    return buy_cost(price, shares)
```

**4d. `buy_and_hold` (`:139-213`).** Replace the whole function:

```python
def buy_and_hold(
    spy: Mapping[date, Bar],
    start: date,
    end: date,
    initial_cash: Decimal,
    *,
    dividends: Sequence[Dividend] = (),
    name: str,
    fractional: bool = False,
    cost_model: CostModel = "flat",
) -> BenchmarkCurve:
    """Buy SPY at ``start``'s open, hold, mark every close through ``end``.

    ``dividends`` empty gives the price-only curve; SPY's dividends give the total-return
    curve. Raises ``ValueError`` when ``start``/``end`` are not sessions, ``end < start``,
    ``initial_cash <= 0``, a dividend list is not strictly ascending, a dividend inside
    ``(start, end]`` is not dated on a session, or a session has no SPY bar.

    ``fractional`` buys in multiples of ``SHARE_QUANTUM`` instead of whole shares (the paper
    benchmark since 2026-10-07; every backtest keeps the whole-share default).

    ``cost_model`` "gotrade" prices every buy with Gotrade's measured schedule (``sim.costs``)
    instead of 0.1%: the benchmark a ``cost_model="gotrade"`` lab method is measured against.
    ValueError for any other value than "flat"/"gotrade".
    """
    if cost_model not in COST_MODELS:
        raise ValueError(f"unknown cost_model {cost_model!r}; expected one of {COST_MODELS}")
    if not isinstance(initial_cash, Decimal):
        raise TypeError(f"initial_cash must be a Decimal, got {type(initial_cash).__name__}")
    cash0 = q(initial_cash)
    if cash0 <= 0:
        raise ValueError(f"initial_cash must be > 0, got {initial_cash}")
    if end < start:
        raise ValueError(f"end {end} is before start {start}")
    window = sessions(start, end)
    if not window or window[0] != start:
        raise ValueError(f"start {start} is not an NYSE session")
    if window[-1] != end:
        raise ValueError(f"end {end} is not an NYSE session")
    for prev, cur in zip(dividends, dividends[1:]):
        if cur.ex_date <= prev.ex_date:
            raise ValueError(f"dividends not strictly ascending at {cur.ex_date}")
    in_window = set(window)
    paid: dict[date, Decimal] = {}
    for div in dividends:
        if start < div.ex_date <= end:
            if div.ex_date not in in_window:
                raise ValueError(f"dividend ex_date {div.ex_date} is not an NYSE session")
            paid[div.ex_date] = div.amount

    snaps: list[Snapshot] = [Snapshot(date=prev_session(start), cash_usd=cash0, equity_usd=cash0)]
    first = _bar(spy, start)
    if fractional:
        shares: int | Decimal = _fractional_shares(cash0, first.open, cost_model)
        cash = cash0 - fractional_buy_cost(first.open, shares, cost_model)
    else:
        shares = _whole_shares(cash0, first.open, cost_model)
        cash = cash0 - _whole_buy_cost(first.open, shares, cost_model)
    credited = Decimal("0.0000")
    for d in window:
        bar = _bar(spy, d)
        amount = paid.get(d)
        if amount is not None:
            income = q(shares * amount)
            cash += income
            credited += income
            if fractional:
                extra = _fractional_shares(cash, bar.close, cost_model)
                cash -= fractional_buy_cost(bar.close, extra, cost_model)
                shares += extra
            else:
                more = _whole_shares(cash, bar.close, cost_model)
                cash -= _whole_buy_cost(bar.close, more, cost_model)
                shares += more
        snaps.append(Snapshot(date=d, cash_usd=cash, equity_usd=q(cash + shares * bar.close)))
    return BenchmarkCurve(
        name=name,
        snapshots=tuple(snaps),
        shares=shares,
        cash=cash,
        dividends_usd=credited,
    )
```

**4e. `spy_curves` (`:216-226`).** Replace the whole function:

```python
def spy_curves(
    spy: Mapping[date, Bar],
    start: date,
    end: date,
    initial_cash: Decimal,
    dividends: Sequence[Dividend],
    *,
    cost_model: CostModel = "flat",
) -> tuple[BenchmarkCurve, BenchmarkCurve]:
    """``(spy_price, spy_tr)``: the price-only and total-return SPY curves over one window,
    both paying ``cost_model`` (see ``buy_and_hold``)."""
    price = buy_and_hold(spy, start, end, initial_cash, name=PRICE_CURVE, cost_model=cost_model)
    total = buy_and_hold(
        spy, start, end, initial_cash, dividends=dividends, name=TOTAL_RETURN_CURVE, cost_model=cost_model
    )
    return price, total
```

**Impact:** Every existing caller keeps the flat default:
- `commands/backtest*.py`
- `paper/replay.py:419`
- `paper/benchmark.py`
- the tests

### Step 5: The lab's dev runs give the benchmark the candidate's model
**File:** `engine/src/seer_engine/backtest/dev.py:433`
**Change:** In `_run`, replace

```python
    price, total = spy_curves(spy, start, end, result.initial_cash, spy_dividends)
```

with

```python
    # The benchmark pays what the candidate pays: Gotrade's schedule for a cost_model="gotrade"
    # rule set, the flat 0.1% (unchanged) otherwise.
    price, total = spy_curves(spy, start, end, result.initial_cash, spy_dividends, cost_model=c.rules.cost_model)
```

**Impact:**
- Every lab path runs through here: `lab/runner.py` and `lab/remeasure.py` call
  `dev.run_registry`, which calls `_run`. A gotrade method is therefore judged against a gotrade
  SPY.
- Flat candidates, which means every existing one, get identical rows.

### Step 6: Book-runner cost reporting (docstrings only)
**File:** `engine/src/seer_engine/backtest/book_runner.py`
**Change:** `_book_result_stats` already sums `Fill.cost_usd`, which Step 3 makes model-aware.
The bracket path's `_fee` uses `COST_RATE`, and `DESIGN_V0` cannot be gotrade. Only the two
docstrings change.

At `:429-430`, replace

```text
    - ``costs_usd``: every fee paid (``sum(Fill.cost_usd)``; for a RunResult
      ``q(price x shares x COST_RATE)`` per fill and exit).
```

with

```text
    - ``costs_usd``: every fee paid (``sum(Fill.cost_usd)``, which is already the rule set's
      cost model: Gotrade's schedule under ``cost_model="gotrade"``; for a RunResult, always
      ``DESIGN_V0``'s flat rate, ``q(price x shares x COST_RATE)`` per fill and exit).
```

At `:518-520`, replace the whole function:

```python
def _fee(price: Decimal, shares: Decimal | int) -> Decimal:
    """The fee part of one bracket-simulator fill (``DESIGN_V0`` only, always flat):
    ``q(price x shares x COST_RATE)``. Book fills carry their own ``Fill.cost_usd``."""
    return q(price * shares * COST_RATE)
```

**Impact:** none. These are documentation changes.

### Step 7: The fee fixture
**File:** `engine/tests/fixtures/gotrade_fees.json` (new; the directory already exists and holds
`lab_n110.sqlite`)
**Change:** Fee columns only. There are no tickers, prices or shares (the owner's privacy, R2).
Rows are in receipt order.
**Code:**
```json
{
  "about": "Fee columns of the owner's 30 Gotrade order receipts (2025-06-10 .. 2026-10-07), copied from the Order Summary screenshots: date (WIB), side, trade amount and the three printed fees, in USD. No tickers, prices or share counts. sim.costs.GOTRADE is fitted to these; tests/test_sim_costs.py replays every row.",
  "rows": [
    {"date": "2025-06-10", "side": "buy", "amount": "1429.00", "trading": "0.00", "regulatory": "4.29", "ppn": "0.00"},
    {"date": "2025-06-10", "side": "buy", "amount": "707.31", "trading": "0.00", "regulatory": "2.13", "ppn": "0.00"},
    {"date": "2025-06-26", "side": "buy", "amount": "1832.90", "trading": "5.50", "regulatory": "0.10", "ppn": "0.62"},
    {"date": "2025-07-22", "side": "buy", "amount": "592.41", "trading": "1.78", "regulatory": "0.10", "ppn": "0.21"},
    {"date": "2026-03-25", "side": "buy", "amount": "147.55", "trading": "0.44", "regulatory": "0.08", "ppn": "0.06"},
    {"date": "2026-03-25", "side": "buy", "amount": "105.27", "trading": "0.32", "regulatory": "0.06", "ppn": "0.04"},
    {"date": "2026-03-25", "side": "buy", "amount": "366.62", "trading": "1.08", "regulatory": "0.11", "ppn": "0.13"},
    {"date": "2026-06-16", "side": "buy", "amount": "1196.77", "trading": "2.39", "regulatory": "0.11", "ppn": "0.27"},
    {"date": "2026-10-05", "side": "buy", "amount": "1673.14", "trading": "3.35", "regulatory": "0.11", "ppn": "0.38"},
    {"date": "2026-10-07", "side": "sell", "amount": "72.51", "trading": "0.15", "regulatory": "0.07", "ppn": "0.02"},
    {"date": "2026-10-07", "side": "buy", "amount": "27.90", "trading": "0.10", "regulatory": "0.02", "ppn": "0.01"},
    {"date": "2026-10-07", "side": "buy", "amount": "27.90", "trading": "0.10", "regulatory": "0.02", "ppn": "0.01"},
    {"date": "2026-10-07", "side": "buy", "amount": "27.90", "trading": "0.10", "regulatory": "0.02", "ppn": "0.01"},
    {"date": "2026-10-07", "side": "buy", "amount": "27.90", "trading": "0.10", "regulatory": "0.02", "ppn": "0.01"},
    {"date": "2026-10-07", "side": "buy", "amount": "27.90", "trading": "0.10", "regulatory": "0.02", "ppn": "0.01"},
    {"date": "2026-10-07", "side": "buy", "amount": "27.90", "trading": "0.10", "regulatory": "0.02", "ppn": "0.01"},
    {"date": "2026-10-07", "side": "buy", "amount": "27.90", "trading": "0.10", "regulatory": "0.02", "ppn": "0.01"},
    {"date": "2026-10-07", "side": "buy", "amount": "27.90", "trading": "0.10", "regulatory": "0.02", "ppn": "0.01"},
    {"date": "2026-10-07", "side": "buy", "amount": "27.90", "trading": "0.10", "regulatory": "0.02", "ppn": "0.01"},
    {"date": "2026-10-07", "side": "buy", "amount": "27.90", "trading": "0.10", "regulatory": "0.02", "ppn": "0.01"},
    {"date": "2026-10-07", "side": "buy", "amount": "27.90", "trading": "0.10", "regulatory": "0.02", "ppn": "0.01"},
    {"date": "2026-10-07", "side": "buy", "amount": "27.90", "trading": "0.10", "regulatory": "0.02", "ppn": "0.01"},
    {"date": "2026-10-07", "side": "buy", "amount": "27.90", "trading": "0.10", "regulatory": "0.02", "ppn": "0.01"},
    {"date": "2026-10-07", "side": "buy", "amount": "27.90", "trading": "0.10", "regulatory": "0.02", "ppn": "0.01"},
    {"date": "2026-10-07", "side": "buy", "amount": "27.90", "trading": "0.10", "regulatory": "0.02", "ppn": "0.01"},
    {"date": "2026-10-07", "side": "buy", "amount": "27.90", "trading": "0.10", "regulatory": "0.02", "ppn": "0.01"},
    {"date": "2026-10-07", "side": "buy", "amount": "27.90", "trading": "0.10", "regulatory": "0.02", "ppn": "0.01"},
    {"date": "2026-10-07", "side": "buy", "amount": "27.90", "trading": "0.10", "regulatory": "0.02", "ppn": "0.01"},
    {"date": "2026-10-07", "side": "buy", "amount": "27.90", "trading": "0.10", "regulatory": "0.02", "ppn": "0.01"},
    {"date": "2026-10-07", "side": "buy", "amount": "27.90", "trading": "0.10", "regulatory": "0.02", "ppn": "0.01"}
  ]
}
```
**Impact:** none (test data).

### Step 8: Tests

**8a. New file `engine/tests/test_sim_costs.py`.** It covers:
- the fit: all 23 current-regime receipts to the cent, and every older receipt except the
  pinned LLY anomaly;
- each rule on its own;
- monotonicity;
- exactness and maximality of `gotrade_shares_for`.

```python
"""Gotrade's fee schedule (Sean plan, phase 6): ``sim.costs`` replays the owner's real receipts.

``tests/fixtures/gotrade_fees.json`` holds the fee columns of all 30 receipts (no tickers,
prices or shares). Every receipt of the CURRENT regime (2026-06-16 on: 22 buys and the one
sell) must come out to the cent; so must every older receipt except LLY 2026-03-25, which paid
$1.08 where 0.3% is $1.10 (the schedule overcharges it by $0.02: conservative, documented in
``sim/costs.py``). No database needed.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from seer_engine.sim import costs
from seer_engine.sim.costs import (
    COST_MODELS,
    GOTRADE,
    FeeParts,
    FeeRegime,
    GotradeSchedule,
    fee_parts,
    gotrade_cash,
    gotrade_shares_for,
)
from seer_engine.sim.model import q

FIXTURE = Path(__file__).parent / "fixtures" / "gotrade_fees.json"
ROWS = json.loads(FIXTURE.read_text())["rows"]
CURRENT_SINCE = date(2026, 6, 16)
# The one receipt the schedule does not reproduce: (date, side, amount) -> (trading, printed).
ANOMALIES = {("2026-03-25", "buy", "366.62"): (Decimal("1.10"), Decimal("1.08"))}
M = Decimal


def _expected(row: dict[str, str]) -> tuple[Decimal, Decimal, Decimal]:
    return M(row["trading"]), M(row["regulatory"]), M(row["ppn"])


def _got(row: dict[str, str], on: date | None) -> FeeParts:
    return fee_parts(row["side"], M(row["amount"]), on)


# ============================================================== the fixture


def test_fixture_is_fee_columns_only_and_complete():
    assert len(ROWS) == 30
    for row in ROWS:
        assert set(row) == {"date", "side", "amount", "trading", "regulatory", "ppn"}
        assert row["side"] in ("buy", "sell")
        date.fromisoformat(row["date"])
        for k in ("amount", "trading", "regulatory", "ppn"):
            assert M(row[k]) == M(row[k]).quantize(Decimal("0.01")) and M(row[k]) >= 0
    assert sum(1 for r in ROWS if r["side"] == "sell") == 1
    assert sum(1 for r in ROWS if date.fromisoformat(r["date"]) >= CURRENT_SINCE) == 23


# ============================================================== the fit


def test_every_current_regime_receipt_to_the_cent():
    current = [r for r in ROWS if date.fromisoformat(r["date"]) >= CURRENT_SINCE]
    assert len(current) == 23
    for row in current:
        for on in (date.fromisoformat(row["date"]), None):  # None is the current regime
            f = _got(row, on)
            assert (f.trading, f.regulatory, f.ppn) == _expected(row), row
            assert f.total == sum(_expected(row)), row


def test_every_older_receipt_to_the_cent_but_the_documented_anomaly():
    for row in ROWS:
        f = _got(row, date.fromisoformat(row["date"]))
        key = (row["date"], row["side"], row["amount"])
        if key in ANOMALIES:
            model, printed = ANOMALIES[key]
            assert (f.trading, M(row["trading"])) == (model, printed)
            assert f.trading - printed == Decimal("0.02")  # the schedule errs on the side of cost
            assert (f.regulatory, f.ppn) == (M(row["regulatory"]), M(row["ppn"]))
            continue
        assert (f.trading, f.regulatory, f.ppn) == _expected(row), row


def test_regimes_and_their_dates():
    assert [r.since for r in GOTRADE.regimes] == [
        date(2025, 6, 10),
        date(2025, 6, 26),
        date(2026, 3, 25),
        date(2026, 6, 16),
    ]
    cur = GOTRADE.current
    assert cur is GOTRADE.regimes[-1] is GOTRADE.regime_on(None)
    assert (cur.trading_rate, cur.trading_min) == (M("0.002"), M("0.10"))
    assert (cur.regulatory_rate, cur.regulatory_cap, cur.sell_extra_rate, cur.ppn_rate) == (
        M("0.00054"),
        M("0.11"),
        M("0.0004"),
        M("0.11"),
    )
    assert GOTRADE.regime_on(date(2026, 6, 15)).trading_rate == M("0.003")
    assert GOTRADE.regime_on(date(2026, 6, 16)) is cur
    assert GOTRADE.regime_on(date(2030, 1, 1)) is cur
    assert GOTRADE.regime_on(date(2025, 6, 25)).ppn_rate == 0
    with pytest.raises(ValueError, match="before 2025-06-10"):
        GOTRADE.regime_on(date(2025, 6, 9))
    with pytest.raises(TypeError):
        GOTRADE.regime_on(datetime(2026, 1, 2))  # type: ignore[arg-type]


# ============================================================== the rules, one by one


def test_trading_fee_rounds_half_up_with_a_ten_cent_minimum():
    assert fee_parts("buy", M("27.90")).trading == M("0.10")  # 0.0558 -> the minimum
    assert fee_parts("buy", M("1673.14")).trading == M("3.35")  # 3.34628 -> half-up
    assert fee_parts("buy", M("50.00")).trading == M("0.10")
    assert fee_parts("buy", M("75.00")).trading == M("0.15")  # 0.15 exactly
    # 2026-03-25: half-up, not up -- $147.55 x 0.3% = 0.44265 printed $0.44
    assert fee_parts("buy", M("147.55"), date(2026, 3, 25)).trading == M("0.44")


def test_regulatory_fee_rounds_up_and_is_capped():
    assert fee_parts("buy", M("27.90")).regulatory == M("0.02")  # 0.015066 -> up
    assert fee_parts("buy", M("105.27")).regulatory == M("0.06")
    assert fee_parts("buy", M("147.55")).regulatory == M("0.08")
    assert fee_parts("buy", M("366.62")).regulatory == M("0.11")  # capped
    assert fee_parts("buy", M("100000")).regulatory == M("0.11")
    assert fee_parts("buy", M("1832.90"), date(2025, 6, 26)).regulatory == M("0.10")  # 2025 cap


def test_sells_pay_an_uncapped_extra_regulatory_part():
    # $72.51: 0.04 (buy formula) + 0.03 (0.04% up) = the receipt's 0.07
    assert fee_parts("sell", M("72.51")).regulatory == M("0.07")
    # $1,000: 0.11 (capped) + 0.40 (uncapped)
    assert fee_parts("sell", M("1000")).regulatory == M("0.51")
    assert fee_parts("sell", M("1000")).total > fee_parts("buy", M("1000")).total


def test_ppn_is_eleven_percent_of_the_printed_fees_rounded_half_down():
    # WDC 2026-06-16: 2.39 + 0.11 = 2.50 -> 0.275 -> printed 0.27 (half-up would say 0.28)
    f = fee_parts("buy", M("1196.77"))
    assert (f.trading, f.regulatory, f.ppn, f.total) == (M("2.39"), M("0.11"), M("0.27"), M("2.77"))


def test_amount_is_taken_to_the_cent_and_only_zero_pays_nothing():
    assert fee_parts("buy", M("27.8951")) == fee_parts("buy", M("27.90"))
    assert fee_parts("buy", M("0")) == FeeParts(M("0.00"), M("0.00"), M("0.00"), M("0.00"))
    assert fee_parts("buy", M("0.004")) == fee_parts("buy", M("0.01"))  # never a free sliver
    assert fee_parts("buy", M("0.004")).trading == M("0.10")
    assert fee_parts("buy", 100) == fee_parts("buy", M("100"))


def test_bad_inputs():
    with pytest.raises(TypeError):
        fee_parts("buy", 27.9)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        fee_parts("buy", True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        fee_parts("buy", M("-1"))
    with pytest.raises(ValueError):
        fee_parts("buy", M("NaN"))
    with pytest.raises(ValueError, match="side"):
        fee_parts("short", M("10"))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="total"):
        FeeParts(M("0.10"), M("0.02"), M("0.01"), M("0.14"))
    with pytest.raises(ValueError, match="ascending"):
        GotradeSchedule(regimes=(GOTRADE.regimes[1], GOTRADE.regimes[0]))
    with pytest.raises(ValueError):
        GotradeSchedule(regimes=())
    with pytest.raises(TypeError):
        FeeRegime(
            since=date(2026, 1, 2),
            trading_rate=0.002,  # type: ignore[arg-type]
            trading_min=M("0.10"),
            regulatory_rate=M("0.00054"),
            regulatory_cap=None,
            sell_extra_rate=M(0),
            ppn_rate=M("0.11"),
        )


def test_fees_never_fall_as_the_amount_grows():
    for side in ("buy", "sell"):
        prev = M(0)
        for cents in range(0, 400_000, 37):
            total = fee_parts(side, M(cents) / 100).total
            assert total >= prev, (side, cents)
            prev = total


def test_cost_models():
    assert COST_MODELS == ("flat", "gotrade")


# ============================================================== simulated orders


def test_gotrade_cash_buy_and_sell():
    # q(10.1 x 2.7323) = 27.5962; fees on $27.60: 0.10 + 0.02 + 0.01
    assert gotrade_cash("buy", M("10.1"), M("2.7323")) == (M("27.7262"), M("0.13"))
    # q(10.5 x 2.7323) = 28.6892; fees on $28.69: 0.10 + (0.02 + 0.02) + 0.02
    assert gotrade_cash("sell", M("10.5"), M("2.7323")) == (M("28.5292"), M("0.16"))
    assert gotrade_cash("buy", M("101"), 9) == (M("911.14"), M("2.14"))


def test_a_dust_sale_never_costs_more_than_it_brings_in():
    proceeds, fee = gotrade_cash("sell", M("0.5"), M("0.1"))  # $0.05 of stock
    assert (proceeds, fee) == (M("0.0000"), M("0.0500"))


def test_shares_for_is_exact_and_never_overspends():
    assert gotrade_shares_for(M("28.0000"), M("10.2"), M("0.0001")) == M("2.7323")
    assert gotrade_cash("buy", M("10.2"), M("2.7323"))[0] == M("27.9995")
    assert gotrade_cash("buy", M("10.2"), M("2.7324"))[0] == M("28.0005")
    assert gotrade_shares_for(M("1000"), M("101"), M(1)) == 9
    assert gotrade_shares_for(M("0"), M("10"), M("0.0001")) == 0
    assert gotrade_shares_for(M("0.10"), M("10"), M("0.0001")) == 0  # the minimum fee eats it
    with pytest.raises(ValueError):
        gotrade_shares_for(M("10"), M("0"), M(1))
    with pytest.raises(TypeError):
        gotrade_shares_for(10.0, M("10"), M(1))  # type: ignore[arg-type]


def test_shares_for_is_the_most_that_fits_on_a_grid():
    for budget_cents in (1, 13, 99, 2_790, 2_800, 10_000, 36_662, 99_999, 250_000):
        budget = M(budget_cents) / 100
        for price in (M("0.37"), M("1"), M("10.2"), M("98.765"), M("455.1"), M("1189.736")):
            for quantum in (M("0.0001"), M(1)):
                n = gotrade_shares_for(budget, price, quantum)
                if n > 0:
                    assert gotrade_cash("buy", price, n)[0] <= budget
                assert gotrade_cash("buy", price, n + quantum)[0] > budget
                assert n == q(n) and (n / quantum) == int(n / quantum)


def test_module_is_decimal_only():
    source = Path(costs.__file__).read_text()
    assert "float(" not in source
```

**8b. New file `engine/tests/test_cost_model_pins.py`.** This is the proof of invariant 2. In a
scratch copy of the tree, all 128 trials in the committed `lab/lab.sqlite` recompute their
`config_text` and `config_digest` byte for byte with the lever in place. The registry pins
(`test_registry.py`) and the paper spec digests (`test_paper_roster.py:86-90`) keep passing
unchanged.

```python
"""Invariant 2 of the Sean plan: adding ``TradeRules.cost_model`` moves no pinned digest.

``cost_model`` is a lever added after the pins (``sim.rules.LEVERS_SINCE_PINS``), so at its
no-op value "flat" it is left out of every canonical form: the registry's ``candidate_text``,
the lab's ``config_text`` (every closed trial's ``config_digest``) and the paper roster's
``rules_dict`` (every live spec digest). A rule set that USES "gotrade" canonicalizes
differently, which is the point. ``tests/test_registry.py`` and ``tests/test_paper_roster.py``
pin their digests already; this file adds the committed lab database, row by row.
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace

import pytest

from seer_engine.backtest.registry import REGISTRY, candidate_digest, candidate_text
from seer_engine.lab import store
from seer_engine.lab.method import config_digest, config_text, discover
from seer_engine.paper import roster
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC, PRESETS


def _gotrade(c):
    return replace(c, rules=replace(c.rules, cost_model="gotrade"))


def _book_candidates():
    out = [c for c in REGISTRY if c.rules.engine == "book"]
    for m, _ in discover().values():
        out += [c for c in m.candidates if c.rules.engine == "book"]
    return out


def test_every_committed_lab_trial_recomputes_its_config_digest_byte_for_byte():
    if not store.COMMITTED_DB.exists():
        pytest.skip("no lab database")
    by_id = {c.id: c for c in REGISTRY}
    for m, _ in discover().values():
        for c in m.candidates:
            by_id[c.id] = c
    conn = sqlite3.connect(f"file:{store.COMMITTED_DB}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT candidate_id, config_digest, config_text FROM trials").fetchall()
    finally:
        conn.close()
    checked = 0
    for candidate_id, digest, text in rows:
        c = by_id.get(candidate_id)
        if c is None:
            continue  # a sibling worktree's method: test_lab_methods says why that is allowed
        assert config_text(c) == text, candidate_id
        assert config_digest(c) == digest, candidate_id
        checked += 1
    assert checked > 0


def test_flat_is_absent_from_every_canonical_form():
    for c in REGISTRY:
        assert "cost_model" not in candidate_text(c), c.id
        assert "cost_model" not in config_text(c), c.id
    for m, _ in discover().values():
        for c in m.candidates:
            assert "cost_model" not in config_text(c), c.id
    for r in PRESETS:
        assert "cost_model" not in roster.rules_dict(r), r.id


def test_gotrade_digests_differently():
    for c in _book_candidates()[:25]:
        g = _gotrade(c)
        assert "cost_model='gotrade'" in config_text(g)
        assert config_digest(g) != config_digest(c)
        assert candidate_digest(g) != candidate_digest(c)
    g = replace(MONTHLY_HOLD_FRAC, id="monthly-hold-frac-gotrade", cost_model="gotrade")
    assert roster.rules_dict(g)["cost_model"] == "gotrade"
```

**8c. `engine/tests/test_sim_rules.py`.**

In `test_preset_values_are_pinned` (`:82-86`), replace the trailing loop

```python
    for r in PRESETS:
        if r is not DESIGN_V0:
            assert r.engine == "book"
            assert r.dividends is True
            assert r.cost_rate == Decimal("0.001")
```

with the version below. It is scoped to the first 13 presets, so a future gotrade preset can be
appended without breaking this test.

```python
    for r in PRESETS:
        if r is not DESIGN_V0:
            assert r.engine == "book"
            assert r.dividends is True
            assert r.cost_rate == Decimal("0.001")
    # The 13 presets that predate Gotrade's measured schedule all keep the flat 0.1% model.
    assert [r.cost_model for r in PRESETS[:13]] == ["flat"] * 13
```

Replace `test_a_lever_added_after_the_pins_is_left_out_of_canonical_text_at_its_default`
(`:400-404`) with:

```python
def test_a_lever_added_after_the_pins_is_left_out_of_canonical_text_at_its_default():
    assert is_pinned_default("resize_cadence", None) is True
    assert is_pinned_default("resize_cadence", "weekly") is False
    assert is_pinned_default("cadence", "monthly") is False  # only post-pin levers are skippable
    assert is_pinned_default("cost_model", "flat") is True
    assert is_pinned_default("cost_model", "gotrade") is False
    assert LEVERS_SINCE_PINS == {"resize_cadence": None, "cost_model": "flat"}
```

Append at the end of the file:

```python

# ============================================================== the Gotrade cost model


GOTRADE_HOLD = replace(MONTHLY_HOLD, id="monthly-hold-gotrade", cost_model="gotrade")


def test_cost_model_defaults_to_flat_and_design_v0_keeps_it():
    assert TradeRules(id="x", engine="book").cost_model == "flat"
    assert DESIGN_V0.cost_model == "flat" and V0_BOOK.cost_model == "flat"
    assert GOTRADE_HOLD.cost_model == "gotrade" and GOTRADE_HOLD.cost_rate == Decimal("0.001")
    with pytest.raises(ValueError, match="reserved for DESIGN_V0"):
        replace(DESIGN_V0, cost_model="gotrade")


def test_cost_model_validation():
    with pytest.raises(ValueError, match="unknown cost_model"):
        TradeRules(id="x", engine="book", cost_model="ibkr")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="cost_model"):
        TradeRules(id="x", engine="book", cost_model=None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="cost_rate must stay at its default"):
        TradeRules(id="x", engine="book", cost_model="gotrade", cost_rate=Decimal("0.002"))
    assert TradeRules(id="x", engine="book", cost_model="gotrade", cost_rate=Decimal("0.0010")).cost_model == "gotrade"


def test_gotrade_is_not_an_owner_input_but_a_flat_fee_still_is():
    assert rule_owner_inputs(GOTRADE_HOLD) == ()
    assert rule_owner_inputs(replace(GOTRADE_HOLD, idle_symbol="IEF")) == ("etf:IEF",)
    assert rule_owner_inputs(replace(MONTHLY_HOLD, id="x", cost_rate=Decimal("0.002"))) == ("fee",)


def test_describe_gotrade_costs():
    lines = describe_rules(GOTRADE_HOLD)
    assert len(lines) == 12
    assert lines[:11] == describe_rules(replace(MONTHLY_HOLD, id="monthly-hold-gotrade"))[:11]
    assert lines[11] == (
        "Costs: Gotrade's fee schedule measured from the owner's receipts (in force since 2026-06-16): "
        "a trading fee of 0.2% of each order, at least $0.10; a regulatory fee of 0.054% rounded up "
        "to the cent, at most $0.11, plus 0.04% more on sells; and 11% VAT (PPN) on those two fees."
    )
    assert describe_rules(MONTHLY_HOLD)[11] == "Costs: 0.1% per side."
```

**8d. `engine/tests/test_sim_book.py`.** Append at the end of the file (after `:811`). It uses
the existing helpers `T`, `go`, `day`, `bar`, `new_book`, `close_book_unpriced` and the
existing `FRACTIONAL`/`DAILY_SWITCH` rules. Every number is hand-checked in the comments and was
run green in a scratch copy of the tree.

```python
# ============================================================== the Gotrade cost model

GOTRADE_FRAC = replace(FRACTIONAL, id="fractional-gotrade", cost_model="gotrade")
SLOTS_28 = (T("A", "0.028", "10"), T("B", "0.028", "10"), T("C", "0.028", "10"))


def _slot_bars(session: str, open_: str, close: str) -> dict[str, Bar]:
    return day(*(bar(s, session, open_, "10.6", "10", close) for s in ("A", "B", "C")))


def test_gotrade_buys_pay_the_schedule_and_never_overspend_the_slot():
    out = go(new_book(W(1000)), TUE, _slot_bars(TUE, "10.1", "10.2"), SLOTS_28, GOTRADE_FRAC)
    # budget q(1000 × 0.028) = 28 at the limit q(10 × 1.02) = 10.2: 2.7323 shares cost 27.9995
    # there (2.7324 would cost 28.0005). Filled at the open 10.1: q(10.1 × 2.7323) = 27.5962,
    # fees on $27.60: trading 0.10 (minimum) + regulatory 0.02 + PPN 0.01 = 0.13.
    assert [(f.symbol, f.shares, f.price, f.cash_usd, f.cost_usd) for f in out.fills] == [
        (s, W("2.7323"), P("10.1"), P("-27.7262"), P("0.13")) for s in ("A", "B", "C")
    ]
    assert out.snapshot.cash_usd == P("916.8214")


def test_gotrade_pays_more_than_flat_on_28_dollar_slots():
    flat_buy = go(new_book(W(1000)), TUE, _slot_bars(TUE, "10.1", "10.2"), SLOTS_28, FRACTIONAL)
    real_buy = go(new_book(W(1000)), TUE, _slot_bars(TUE, "10.1", "10.2"), SLOTS_28, GOTRADE_FRAC)
    flat_sell = go(flat_buy.book, WED, _slot_bars(WED, "10.5", "10.5"), (), FRACTIONAL)
    real_sell = go(real_buy.book, WED, _slot_bars(WED, "10.5", "10.5"), (), GOTRADE_FRAC)
    # flat: 2.7423 shares, fee q(10.1 × 2.7423 × 0.001) = 0.0277 a buy
    assert [f.cost_usd for f in flat_buy.fills] == [P("0.0277")] * 3
    # gotrade sell: q(10.5 × 2.7323) = 28.6892, fees on $28.69: 0.10 + (0.02 + 0.02) + 0.02 = 0.16
    assert [(f.cash_usd, f.cost_usd) for f in real_sell.fills] == [(P("28.5292"), P("0.16"))] * 3
    flat_fees = sum(f.cost_usd for f in flat_buy.fills + flat_sell.fills)
    real_fees = sum(f.cost_usd for f in real_buy.fills + real_sell.fills)
    assert real_fees == P("0.87") and real_fees > 5 * flat_fees
    assert real_sell.snapshot.equity_usd < flat_sell.snapshot.equity_usd
    assert [t.pnl_usd for t in real_sell.trades] == [P("0.8030")] * 3  # 28.5292 − 27.7262


def test_gotrade_whole_shares_and_forced_close():
    rules = replace(DAILY_SWITCH, id="daily-switch-gotrade", cost_model="gotrade")
    bars = day(bar("XYZ", TUE, "101", "103", "100", "102"))
    out = go(new_book(W(1000)), TUE, bars, (T("XYZ", "1", "100"),), rules)
    # limit 102: 9 shares cost 918 + fees(1.84 + 0.11 + 0.22) = 920.17 <= 1000; filled at 101:
    # 909 + fees on $909: 1.82 + 0.11 + q½↓(1.93 × 0.11 = 0.2123) 0.21 = 2.14
    (f,) = out.fills
    assert (f.shares, f.cash_usd, f.cost_usd) == (W(9), P("-911.14"), P("2.14"))
    nb, fills, trades = close_book_unpriced(out.book, ["XYZ"], rules)
    # at the mark 102: 918 − fees on $918 (1.84 + (0.11 + 0.37) + 0.26) = 918 − 2.58
    (s,) = fills
    assert (s.cash_usd, s.cost_usd) == (P("915.42"), P("2.58"))
    assert trades[0].pnl_usd == P("915.42") - P("911.14")


def test_flat_rules_are_unchanged_by_the_cost_model_lever():
    bars = day(bar("XYZ", TUE, "301", "305", "299", "304"))
    out = go(new_book(W(1000)), TUE, bars, (T("XYZ", "1", "300"),), replace(FRACTIONAL, cost_model="flat"))
    (f,) = out.fills
    assert (f.shares, f.cash_usd, f.cost_usd) == (W("3.2647"), P("-983.6574"), P("0.9827"))
```

**8e. `engine/tests/test_benchmark.py`.** Append at the end of the file (after `:260`). It uses
the existing `spy_bars`, `START`, `END`, `CASH`, `div` and `equities`.

```python
# ----------------------------------------------------------------------------- Gotrade costs


def test_gotrade_benchmark_pays_the_schedule_on_the_first_buy():
    # 9 shares at the open 100: $900 + trading 1.80 + regulatory 0.11 (cap) + PPN
    # q½↓(1.91 × 0.11 = 0.2101) 0.21 = 902.12; 10 shares would need 1002.34.
    c = buy_and_hold(spy_bars(), START, END, CASH, name="spy_price", cost_model="gotrade")
    assert (c.shares, c.cash) == (9, P("97.88"))
    assert equities(c) == [P(x) for x in ("1000", "1006.88", "1015.88", "979.88", "988.88", "1002.38")]


def test_gotrade_benchmark_pays_the_schedule_on_each_reinvestment():
    # 03-04: cash 97.88 + q(9 × 2.5) = 120.38; 1 share at the close 98 costs
    # 98 + 0.20 + 0.06 + q½↓(0.26 × 0.11 = 0.0286) 0.03 = 98.29 -> cash 22.09, 10 shares.
    _, tr = spy_curves(spy_bars(), START, END, CASH, [div("2026-03-04", "2.5")], cost_model="gotrade")
    assert (tr.shares, tr.cash, tr.dividends_usd) == (10, P("22.09"), P("22.5"))
    assert equities(tr) == [P(x) for x in ("1000", "1006.88", "1015.88", "1002.09", "1012.09", "1027.09")]


def test_gotrade_fractional_benchmark_spends_to_the_cent():
    # fees on the whole $1000 are 2.00 + 0.11 + 0.23 = 2.34, so 9.9766 shares (997.66) fit exactly.
    c = buy_and_hold(spy_bars(), START, END, CASH, name="x", fractional=True, cost_model="gotrade")
    assert (c.shares, c.cash) == (Decimal("9.9766"), P("0"))


def test_cost_model_default_is_flat_and_unknown_is_refused():
    assert buy_and_hold(spy_bars(), START, END, CASH, name="x") == buy_and_hold(
        spy_bars(), START, END, CASH, name="x", cost_model="flat"
    )
    with pytest.raises(ValueError, match="cost_model"):
        buy_and_hold(spy_bars(), START, END, CASH, name="x", cost_model="ibkr")  # type: ignore[arg-type]
```

**8f. `engine/tests/test_backtest_dev.py`.** Insert before
`def test_window_before_fx_start_converts_at_the_fx_start_rate():` (`:412`). `replace`,
`DAILY_SWITCH`, `BookResult`, `run_stats`, `spy_curves`, `curve_metrics`, `cand`, `HoldOne`,
`short_market`, `DIVS` and `SPY_DIVS` are all already imported or defined in the file.

```python
def test_a_gotrade_candidate_and_its_spy_benchmark_both_pay_gotrade_fees():
    market = short_market()
    gotrade = replace(DAILY_SWITCH, id="daily-switch-gotrade", cost_model="gotrade")
    flat_c = cand("F1-FLIP-D", allocator=HoldOne("FLIP", "SPY", flip=True), rules=DAILY_SWITCH)
    real_c = cand("F1-FLIP-G", allocator=HoldOne("FLIP", "SPY", flip=True), rules=gotrade)
    assert real_c.owner_inputs == flat_c.owner_inputs  # the measured schedule needs no owner input
    flat, flat_row = run_candidate(market, DIVS, SPY_DIVS, flat_c)
    real, real_row = run_candidate(market, DIVS, SPY_DIVS, real_c)
    assert isinstance(real, BookResult) and isinstance(flat, BookResult)
    assert (real_row.start, real_row.end) == (flat_row.start, flat_row.end)
    assert real.costs_usd > flat.costs_usd
    assert real_row.stats == run_stats(real)
    price, total = spy_curves(
        market.spy(), real_row.start, real_row.end, real.initial_cash, SPY_DIVS, cost_model="gotrade"
    )
    assert real_row.spy_price == curve_metrics(price)
    assert real_row.spy_tr == curve_metrics(total)
    assert real_row.spy_tr != flat_row.spy_tr  # the benchmark paid Gotrade's fees too
```

**8g. `engine/tests/test_backtest_dev_report.py:567-570`.** The `TradeRules` repr gains its
new last field. Replace

```python
    assert (
        "TradeRules(id='monthly-hold', engine='book', cadence='monthly', resize_cadence=None, "
        "entry='open_limit', max_positions=None, "
        "time_stop=None, resize=True, fractional=False, dividends=True, idle_symbol=None, cost_rate=Decimal('0.001'))"
    ) in text
```

with

```python
    assert (
        "TradeRules(id='monthly-hold', engine='book', cadence='monthly', resize_cadence=None, "
        "entry='open_limit', max_positions=None, "
        "time_stop=None, resize=True, fractional=False, dividends=True, idle_symbol=None, cost_rate=Decimal('0.001'), "
        "cost_model='flat')"
    ) in text
```

**Impact:** No existing assertion weakens. The repr string is the only existing expectation
that changes.

## Verification

Every command runs from the worktree:

**Build:** `cd engine && .venv/bin/ruff check .`

**Tests:** `cd engine && .venv/bin/python -m pytest -q`. This is the full suite, with xdist
from `addopts`. Run these in particular:
- `tests/test_sim_costs.py`
- `tests/test_cost_model_pins.py`
- `tests/test_registry.py`
- `tests/test_paper_roster.py`
- `tests/test_lab_methods.py`
- `tests/test_sim_rules.py`
- `tests/test_sim_book.py`
- `tests/test_benchmark.py`
- `tests/test_paper_benchmark.py`
- `tests/test_backtest_dev.py`
- `tests/test_backtest_dev_report.py`
- `tests/test_sim_purity.py`
- `tests/test_strategy_purity.py`

**What was checked before this plan was written.** Steps 1-8 were applied to a scratch copy of
this worktree and run with a fresh venv:
- `ruff check .`: all checks passed.
- Full pytest: 2919 passed and 388 skipped (Postgres). One test failed:
  `test_lab_prereg.py::test_lab_promote_command_exits_2_when_the_lab_refuses`. It runs
  `git rev-parse HEAD`, and the scratch copy had no `.git`. It passes in the real worktree, both
  before and after the change.

**Manual check:** In a Python shell, `describe_rules(replace(MONTHLY_HOLD, id="x",
cost_model="gotrade"))[-1]` reads:

> Costs: Gotrade's fee schedule measured from the owner's receipts (in force since 2026-06-16):
> a trading fee of 0.2% of each order, at least $0.10; a regulatory fee of 0.054% rounded up to
> the cent, at most $0.11, plus 0.04% more on sells; and 11% VAT (PPN) on those two fees.

**Exit criteria:** The phase is done when all of these hold:
- ruff and the full pytest suite are green, including `test_registry` (the pinned digests),
  `test_lab_methods` (the source shas), `test_paper_roster` (the spec digests) and the new
  `test_cost_model_pins` (every committed lab trial digest recomputes);
- `test_sim_costs` reproduces every current-regime receipt to the cent;
- a book run under `cost_model="gotrade"` pays more than one under `"flat"` on $28 slots
  ($0.87 against less than $0.18 for 3 buys and 3 sells).

## Handoffs

- **Phase 7 (R5):**
  - `seer sean calibrate` replays `sean_orders` through `fee_parts(side, amount, on=date)`. The
    "current regime" is `GOTRADE.current.since` (2026-06-16).
  - Refitting `sell_extra_rate` and the regime dates as receipts arrive is a change to
    `sim/costs.py` numbers. That change happens only after `calibrate` shows a residual, and it
    must keep `tests/test_sim_costs.py` green against an updated fixture.
  - `lab costs MNNNN` builds its real-cost copy with
    `replace(c, rules=replace(c.rules, cost_model="gotrade"))`. It must refuse `DESIGN_V0`
    methods (`ValueError` from `TradeRules`) and can call `dev.run_candidate` directly; the SPY
    benchmark pays Gotrade automatically (Step 5).
  - Skills and design doc: new methods pre-register with `cost_model="gotrade"`.
- **Paper promotion of a gotrade method:**
  - `commands/promote.py:_check_rules` requires the rules to be the `PRESETS` entry of their id.
  - `fractional_twin` compares every field except `id`/`fractional`, `cost_model` included.
  - Promoting a gotrade lab winner therefore needs a gotrade preset appended to `PRESETS`, for
    example `monthly-hold-frac-gotrade`. The ordered id pin in `test_sim_rules.py` would then
    need updating. Paper books would then pay Gotrade automatically through `step_book`.
  - None of this is in this phase's steps. **Reconciled:** Phase 7 adds the two presets
    (`monthly-hold-frac-gotrade`, `monthly-rank-weekly-resize-frac-gotrade`) after this phase
    lands, updates the id pin in `test_sim_rules.py`, and narrows this phase's
    `test_cost_model_pins.py::test_flat_is_absent_from_every_canonical_form` preset loop to flat
    presets (the new ones carry `cost_model` in their canonical text on purpose).
- **Paper SPY benchmark** (`paper/benchmark.py`, `paper/replay.py`) stays on flat 0.1%. If paper
  books ever pay Gotrade, their benchmark should too, by passing `cost_model` to
  `_fractional_shares`/`fractional_buy_cost`/`buy_and_hold`. This belongs to the `paper/` owner
  and is out of scope here.
- **`engine/package_readme.md`** gets a `sim/costs.py` line and the `cost_model` lever. The
  completion handler or readme-updater owns that, not this phase.

## Rollback

Revert this phase's commit. Every digest stays where it was, because the lever's default is a
true no-op and `LEVERS_SINCE_PINS` drops it from canonical text. No database rows, files outside
`engine/` or migrations are involved. If Phase 7 has already landed, revert it first: it imports
`seer_engine.sim.costs`.
