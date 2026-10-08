# Phase 7: Money-weighted return, and a SPY fed the same money

**Plan set:** `GOTRADE_FEE_REBUILD_PLAN.md`
**Analysis:** `20261008-091321-H3M8_code_analyzer.md`
**Satisfies:** R3 — "every CAGR-phrased gate restated", "a money-weighted return", "a dollar-cost-averaged SPY"
**Depends on:** Phase 2 (`lab/store.py`, `test_lab_snapshot.py`), Phase 5 (`RunResult.cashflows` / `BookResult.cashflows`)
**Difficulty:** HARD
**Package:** `engine.backtest`, `engine.lab`

---

## Goal

After this phase a book that was fed deposits reports **what its money actually earned**, not what
its ending balance looks like; SPY receives the identical dollars on the identical days, so
"beats SPY TR" compares two books holding the same money at the same times; and MAR — the number
the lab ranks finalists by — is computed from the money-weighted rate rather than from a CAGR that
counts deposits as growth. Nothing about the 128 recorded trials changes: they had no deposits, and
on a deposit-free run the new measure is the old CAGR to within 5×10⁻¹⁴.

### The measurement that makes this phase non-optional

Measured here on the owner's real plan — 10,000,000 IDR on 2026-11-02, +5,000,000 IDR on the 25th of
each month for twelve months, ending 2027-11-02 (script:
`/tmp/claude-1000/-home-miftah-seer/3d70e116-a966-48b6-b5e9-bef2b7607cfb/scratchpad/irr.py`, rerun
with `python3 <that path>` from the worktree root):

| What the book actually did | money-weighted return | today's `total_return` | today's `cagr` |
|---|---|---|---|
| **earned nothing at all** | **0.00%** | **+600.0%** | **+600.9%** |
| earned 10% on every dollar | +18.45% | +670.0% | +671.1% |
| lost 10% on every dollar | −17.60% | +530.0% | +530.8% |

A book that does **nothing** reports a CAGR of **+600.9%** once contributions exist. That is the
"flattering lie" of Decision D4, measured, and it is why phases 5, 6 and 7 ship as one unit.

---

## Decisions settled here

### D7a. The measure is IRR (the money-weighted rate of return), not modified Dietz.

**The sentence the owner reads, and which must appear in the code:**

> **Money-weighted return**: the interest rate a savings account would have had to pay to turn the
> same deposits, paid in on the same days, into the same final balance.

Modified Dietz is rejected: it weights each deposit linearly by the fraction of the window it was
present for, which is a sound approximation over one month and a poor one over the lab's 10–22 year
dev windows with 120–260 monthly deposits, where growth compounds and linear weighting does not.
It would also have to be annualised by a power rule it does not satisfy.

The usual objection to IRR — "it needs a solver and can fail to converge" — **does not apply to this
cashflow shape and that is provable, not hoped for.** Every flow here is money going *in* (the
opening cash, then each deposit) except the final valuation, so the sequence in time order has
**exactly one sign change**. By Descartes' rule of signs there is at most one positive real root,
and the bracket is guaranteed in both directions: as the rate falls towards −100% the final
valuation's discount factor grows without bound (NPV → +∞), and as it rises the undiscounted
opening cash dominates (NPV → −V₀ < 0). Bisection on that bracket is deterministic, pure, and
measured at **41 iterations** to full double precision on real window lengths.

**When it is undefined** it returns `None`, exactly where `cagr_between` already returns `None`:
fewer than two snapshots, a window of zero days, non-positive opening cash, or a book wiped out to
zero or below (whose true answer is −100%, which the bracket excludes). `None` is never an error.

**Measured, IRR is a strict generalisation of CAGR.** With no deposits the flows are
(−V₀ at t₀, +V₁ at t₁) and the root is exactly `(V₁/V₀)^(365.25/days) − 1`, which *is*
`cagr_between`. Measured agreement over three real-shaped windows: 5.3×10⁻¹⁴, 1.1×10⁻¹³ and
3.9×10⁻¹³ relative (`scratchpad/irr3.py`). This is pinned as a test, not assumed.

### D7b. `cagr` is JOINED, not replaced — and the new field is `None` when there were no deposits.

`Metrics.cagr` keeps its definition, its value and its meaning. Every one of the 128 recorded lab
trials was run with no contributions, `lab/remeasure.py` reproduces six recorded metrics including
`cagr`, and `web/lib/metrics.ts` is its twin. None of that moves.

`Metrics.mwr` is added beside it and is **`None` exactly when the run had no external cashflows** —
meaning "this run had no deposits, so CAGR already *is* the money-weighted return". That choice is
load-bearing, not cosmetic: it keeps `make_row`'s MAR bit-for-bit identical on every unfunded run
(bisection and the closed form agree to 5×10⁻¹⁴, which is **not** bit equality), so no recorded
`mar`, no `best_dev_eligible` ranking and no `finalists` order can shift by a rounding artefact.

### D7c. "beats SPY TR" is restated money-weighted, with the recorded condition preserved.

Today it is `total_return > spy_tr_return` (`lab/store.py:987`). It becomes: compare the
money-weighted returns **when both sides have one**, and fall back to the total-return comparison
otherwise. All 128 historical rows have no money-weighted number, so they are judged exactly as they
are today — no recorded verdict silently changes meaning, which is the defect `owner_failures`'
own docstring exists to prevent.

The **label** `"beats SPY TR"` is unchanged (`dev.FAILURE_LABELS[0]`), so no recorded `trials.failed`
string drifts and `web/lib/sera/derive.ts` needs nothing.

Worth writing down because it is not obvious: once SPY receives the *identical* cashflows from the
*identical* opening cash, comparing `total_return` is already comparing ending equity, so the
restatement does not change the comparison's **direction** on a correctly-funded pair. What it
changes is that the number a human reads is now true, and that the comparison stays right if the two
sides are ever fed differently. The load-bearing half of this phase is the DCA SPY, not the formula.

### D7d. The lab's storage is a **side table**, not new `trials` columns.

`engine/tests/test_lab_snapshot.py:177` asserts `_trials_bytes(db) == before` — the `trials` table
must be **byte-identical across a migration**. `ALTER TABLE trials ADD COLUMN` would break that pin
and would force `TrialRow` to grow defaulted fields that `lab/runner.py` (not this phase's file)
would silently leave NULL.

So schema v4 adds `trial_funding`, in exactly the shape, prose and trigger pattern that
`trial_moments` established at v3 for the same reason. The migration is purely additive, `trials` is
not read, written or re-keyed, and **the existence of a row is the funded flag** — a trial with no
`trial_funding` row had no deposits, which is true of all 128 recorded trials with no NULL ambiguity.

### D7e. SPY buys as the money arrives, and the direction of that bias is stated.

A deposit lands as cash on the first NYSE session on or after its calendar date (D6: the 25th, with
the calendar producing the lag — measured mean 7.0 days, range 4 to 10) and SPY buys at that
session's close. The book, by contrast, waits for its rotation. SPY therefore has a **shorter** idle
gap than the book, which makes SPY **harder** to beat. That is the conservative direction for a gate
and it is deliberate; the alternative — making the benchmark wait for the strategy's calendar —
would make "buy and hold" depend on the thing it is benchmarking.

---

## Interface Contract

**Creates:**
- `backtest.metrics.money_weighted_return` (`metrics.py`) — the IRR
- `backtest.metrics.external_cashflows` (`metrics.py`) — reads phase 5's field off either result type
- `backtest.metrics.Metrics.mwr` (`metrics.py`) — new field, default `None`
- `backtest.benchmark.BenchmarkCurve.cashflows` (`benchmark.py`) — new field, default `()`
- `backtest.dev.beats_spy_tr` (`dev.py`) — the one definition of the restated condition
- `lab.store.FundingRow`, `lab.store.FUNDING_COLUMNS`, `lab.store.insert_funding`,
  `lab.store.funding_of` (`store.py`)
- `lab.store._FUNDING_TABLE`, `lab.store._FUNDING_TRIGGERS`, `lab.store._v3_to_v4` (`store.py`)

**Signature changes:**
- `dev.run_registry(market, dividends, spy_dividends, registry, *, window=DEV_WINDOW)` ->
  `(..., contributions: ContributionSchedule | None = None)`, passed through `dev._run` to
  `run_rules` (**added by the reconciler** — phase 8 cannot run without it; Step 10b)
- `strategy_metrics(snaps, pnls)` -> `strategy_metrics(snaps, pnls, cashflows=())`
- `buy_and_hold(..., cost_model="flat")` -> `buy_and_hold(..., cost_model="flat", contributions=())` (keyword-only)
- `spy_curves(..., cost_model="flat")` -> `spy_curves(..., cost_model="flat", contributions=())` (keyword-only)
- `store.owner_failures(trial)` -> `store.owner_failures(trial, funding=None)`
- `store._blocking(trial)` -> `store._blocking(trial, funding=None)`

**Value changes:**
- `lab.store.SCHEMA_VERSION` `"3"` -> `"4"` — the **sqlite schema version of `lab/lab.sqlite`**, a
  **string**. It is *not* `SNAPSHOT_VERSION`, the published-JSON version, which is an **int** and
  which **phase 2** moves `3` -> `4` in the same file. Two different numbers, both reading "3 to 4",
  both in `lab/store.py`, both pinned in `test_lab_snapshot.py`. This phase touches only the string;
  phase 2 touched only the int. See the table in `phase-2.md`'s Interface Contract.

**Deletes:** none. **Renames:** none. No column, function or label is removed.

**Requires (from earlier phases):**
- **Phase 5** — `RunResult.cashflows` and `BookResult.cashflows`, each
  `tuple[tuple[date, Decimal], ...]`: the external deposits the run applied, **dated by the NYSE
  session they were applied on** (not by the schedule's calendar date), ascending, amounts > 0,
  excluding the opening cash, `()` when the run had none. This phase reads them through the single
  function `metrics.external_cashflows`, so a different field name is a **one-line** fix there and
  nowhere else. If phase 5 instead exposes a schedule object, `external_cashflows` is the only
  place that has to resolve it to dated amounts.
- **Phase 5** — contributions are **opt-in**, default none. **Verified by the reconciler against
  `phase-5.md`: `contributions: ContributionSchedule | None = None` on `run_backtest`, `run_book`
  and `run_rules`, with `RunResult.contributions is None` / `cashflows == ()` as phase 5's own exit
  criterion 3.** Every existing caller (`tuning.gate`, `walkforward.gate_p3b`,
  `b_walkforward.gate_p6a`, `commands/backtest_dev.py`, `commands/backtest_b.py`, `paper/replay.py`)
  passes no schedule and so is byte-for-byte unchanged by this phase. The "if phase 5 makes funding
  default-on" branch of this plan's draft is **dead**: it did not.
- **Phase 5** — the schedule's names, read off `phase-5.md` and fixed by the reconciler:
  module `seer_engine.sim.contributions`, class `ContributionSchedule(amount_idr, day_of_month=25)`,
  instance `OWNER_MONTHLY`. This phase imports only the class, and only for the type annotation on
  `run_registry`'s new keyword (Step 10b).
- **Phase 2** — `lab/store.py` is quoted as phase 2 leaves it (D8). Phase 2 edits `_snapshot_trial`
  and the module docstring; **this phase does not touch `_snapshot_trial` at all**, by design (see
  D7d — the side table keeps `TRIAL_KEYS` in `test_lab_snapshot.py:50-53` unchanged too).

**Leaves alone (owned by others):**
- `backtest/runner.py`, `backtest/book_runner.py`, `sim/contributions.py` — Phase 5
- `sim/costs.py` — invariant 5, never modified
- `paper/*` — Phases 3, 6, 12
- `sim/*` — Phase 4
- `web/*` — Phases 2, 9, 10
- `lab/runner.py`, `lab/seed.py`, `lab/real_costs.py`, `lab/remeasure.py` — see Handoffs
- `lab/lab.sqlite` — not touched; it migrates itself on the next `lab` write (additive)
- `engine/tests/test_benchmark.py` — the existing benchmark suite; new tests go in a new file

**SETTLED BY THE RECONCILER — `engine/tests/test_lab_snapshot.py` has two owners, by line:**

| lines | what | owner |
|---|---|---|
| `:50-53` `TRIAL_KEYS`, `:280` `s["version"] == 3` (**int**, the snapshot version), two new tests after `:359` | the `luckGated` marker | **phase 2** |
| `:86`, `:104`, `:113`, `:180`, `:207`, `:238` — every `store.schema_version(...) == "3"` / `store.SCHEMA_VERSION == "3"` (**string**, the sqlite schema version), plus the new v3 -> v4 migration test | schema v4 | **THIS PHASE** (Step 11) |

The six substitutions are mechanical one-token edits. **This phase depends on phase 2, so phase 2
lands first and there is no concurrent edit** — the file is quoted as phase 2 leaves it, and phase 2's
plan now states in its own Files table that it leaves the six `"3"` pins at `"3"`. Step 11 is **not**
optional and **does not** move to phase 2: without it the suite is red, and phase 2 has no reason to
know about `trial_funding`.

**Line numbers in `lab/store.py` shift after phase 2.** Phase 2 inserts `luck_gated()` at `:1272`,
moving everything below it by about **+22 lines**. This phase's Files table quotes pre-phase-2
numbers for `:1294` (`_blocking`), `:1386` and `:1564` (where `FundingRow` / `insert_funding` /
`funding_of` go). **Locate those three hunks by symbol, not by line.** Everything this phase edits
*above* `:1272` — `:62`, `:230`, `:313`, `:431`, `:453-458`, `:980`, `:1232`, `:1266` — is unmoved.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/metrics.py` | modify | the IRR (`:107`), `Metrics.mwr` (`:77`), `strategy_metrics` takes cashflows (`:109`), `run_metrics` / `curve_metrics` pass them (`:178`, `:213`), docstring (`:11-13`) |
| `engine/src/seer_engine/backtest/benchmark.py` | modify | `BenchmarkCurve.cashflows` (`:62-66`), `buy_and_hold(contributions=…)` (`:161-242`), `spy_curves(contributions=…)` (`:245-260`), docstring (`:20-24`) |
| `engine/src/seer_engine/backtest/dev.py` | modify | `beats_spy_tr` (new, before `:289`), `make_row`'s `beats` and `mar` (`:374-378`), `_run` feeds SPY the same money (`:433-435`); **`contributions=` on `run_registry` / `_run` and `is_bracket` at `:185`, `:206`, `:223` (Step 10b)** |
| `engine/src/seer_engine/lab/store.py` | modify | `_FUNDING_TABLE`/`_FUNDING_TRIGGERS` (after `:230`), `_SCHEMA` (`:313`), `SCHEMA_VERSION` (`:62`), `_v3_to_v4` + ladder (`:431`, `:453-458`), `FundingRow`/`insert_funding`/`funding_of` (after `:1564`), `owner_failures` (`:980`), `verdict`/`published_verdict` call sites (`:1232`, `:1266`), `_blocking` (`:1294`, `:1386`), docstrings (`:20-25`) |
| `engine/tests/test_backtest_metrics.py` | modify | the IRR's tests, including CAGR equivalence and the +600.9% distortion |
| `engine/tests/test_backtest_benchmark.py` | **create** | the DCA SPY's tests (the existing `test_benchmark.py` is untouched) |
| `engine/tests/test_lab_snapshot.py` | modify | six `"3"` version pins -> `"4"`; one new v3 -> v4 migration test (see CONFLICT above) |

---

## Implementation Steps

### Step 1: The money-weighted return

**File:** `engine/src/seer_engine/backtest/metrics.py:107` (between `cagr_between` and `strategy_metrics`)
**Change:** add the IRR and its helper. Nothing else in the module calls them yet.
**Code:**
```python
IRR_LOW = -0.9999
"""The lowest rate the solver brackets. A book wiped out to zero has a true money-weighted return
of exactly -100%, which no finite bracket contains; that case answers None, like every other
undefined one."""

_IRR_TOL = 1e-12  # relative: the bracket closes to tol * (1 + |rate|)
_IRR_MAX_RATE = 1e9
_IRR_MAX_STEPS = 200  # measured: 41 steps on a real 22-year window, 40 on a 5-month one


def _npv(rate: float, years: Sequence[float], amounts: Sequence[float]) -> float:
    """Net present value of ``amounts`` at ``years`` (Actual/365.25), discounted at ``rate``.

    Money in is negative, the final valuation positive. Summed left to right in a plain loop, like
    ``_sum``, so the arithmetic matches the rest of this module.
    """
    base = 1.0 + rate
    total = 0.0
    for t, a in zip(years, amounts):
        total += a * base ** (-t)
    return total


def money_weighted_return(
    snaps: Sequence[tuple[date, float]],
    cashflows: Sequence[tuple[date, float]],
) -> float | None:
    """The money-weighted return (IRR) of a curve that received deposits; None when undefined.

    **In one sentence a human reads:** the interest rate a savings account would have had to pay
    to turn the same deposits, paid in on the same days, into the same final balance.

    Why this and not CAGR: a deposit raises the ending equity without being a return. Measured on
    the owner's real funding plan (10,000,000 IDR, then +5,000,000 IDR on the 25th of each month
    for a year), a book that earns **nothing at all** reports a CAGR of +600.9% and a total return
    of +600.0%. Its money-weighted return is 0.00%, which is the truth.

    ``snaps`` are ``(date, equity)`` in date order, the same sequence ``strategy_metrics`` takes;
    ``snaps[0]`` is the opening cash on the session before the window and ``snaps[-1]`` the final
    mark. ``cashflows`` are the external deposits, ``(date, amount)`` with ``amount > 0``,
    ascending, each dated strictly after ``snaps[0]`` and no later than ``snaps[-1]``.

    The cashflow sequence is the opening cash and every deposit (all money **in**), then one
    positive final valuation -- exactly one sign change -- so by Descartes' rule of signs there is
    at most one positive real root, and it is found by bisection rather than by a Newton step that
    could wander. The bracket is guaranteed: as the rate approaches -100% the final valuation's
    discount factor grows without bound, and as it rises the undiscounted opening cash dominates.
    Measured: 41 bisection steps to full double precision on a 1993-2015 window.

    With **no** cashflows this is exactly ``cagr_between(snaps[0], snaps[-1])`` -- the two-flow
    root of ``-V0 + V1 (1+r)^(-T) = 0`` is ``(V1/V0)^(365.25/T) - 1``. Measured agreement over
    three real-shaped windows: 5.3e-14, 1.1e-13 and 3.9e-13 relative.

    None (never an error) when: fewer than two snapshots; the window is zero days or negative;
    the opening equity is not positive; the final equity is negative; the bracket does not close
    (a book wiped out to zero or below, whose answer is -100%); or the rate would exceed 1e9.

    ValueError for a deposit that is not positive, is out of order, or falls outside
    ``(snaps[0].date, snaps[-1].date]`` -- those are programming errors in the caller, not data.
    """
    if len(snaps) < 2:
        return None
    first, last = snaps[0], snaps[-1]
    days = (last[0] - first[0]).days
    if days <= 0 or first[1] <= 0 or last[1] < 0:
        return None

    flows: list[tuple[date, float]] = [(first[0], -float(first[1]))]
    previous: date | None = None
    for when, amount in cashflows:
        if isinstance(when, datetime) or not isinstance(when, date):
            raise TypeError(f"a cashflow date must be a date, got {type(when).__name__}")
        value = float(amount)
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"a cashflow must be a finite amount > 0, got {amount!r} on {when}")
        if previous is not None and when <= previous:
            raise ValueError(f"cashflows must ascend strictly: {when} is not after {previous}")
        if not first[0] < when <= last[0]:
            raise ValueError(f"cashflow {when} is outside the curve's ({first[0]}, {last[0]}]")
        previous = when
        flows.append((when, -value))
    flows.append((last[0], float(last[1])))

    years = [(when - first[0]).days / YEAR_DAYS for when, _ in flows]
    amounts = [a for _, a in flows]

    low = IRR_LOW
    if not _npv(low, years, amounts) > 0:
        return None
    high = 1.0
    while _npv(high, years, amounts) >= 0:
        high *= 2.0
        if high > _IRR_MAX_RATE:
            return None
    steps = 0
    while high - low > _IRR_TOL * (1.0 + abs(low)) and steps < _IRR_MAX_STEPS:
        middle = (low + high) / 2.0
        if _npv(middle, years, amounts) > 0:
            low = middle
        else:
            high = middle
        steps += 1
    return (low + high) / 2.0
```
**Impact:** pure addition; nothing calls it yet, so the suite is unchanged after this step.

### Step 2: `Metrics.mwr`

**File:** `engine/src/seer_engine/backtest/metrics.py:66-79`
**Change:** one field, defaulted, after the existing defaulted ones so no positional construction breaks.
**Code:**
```python
@dataclass(frozen=True)
class Metrics:
    """One curve's metrics. The first six fields are the web's ``Metrics``; the last four are
    backtest additions (``None``/empty where they do not apply, e.g. a buy-and-hold curve)."""

    total_return: float | None
    win_rate: float | None
    profit_factor: float | None  # math.inf when trades exist and none lost
    max_drawdown: float | None
    trades: int
    months: float
    cagr: float | None = None
    avg_days_held: float | None = None
    exit_reasons: tuple[tuple[str, int], ...] = ()
    mwr: float | None = None
    """The money-weighted return: the interest rate a savings account would have had to pay to
    turn the same deposits, paid in on the same days, into the same final balance.

    **None means the run received no deposits**, in which case ``cagr`` already *is* the
    money-weighted return -- the two agree to 5e-14 and the equality is pinned by
    ``test_backtest_metrics.py``. It is None rather than a recomputed copy of ``cagr`` on purpose:
    bisection and the closed form agree to that tolerance but not bit-for-bit, and ``dev.make_row``
    divides this by the max drawdown to get MAR, which the lab ranks finalists by and records. A
    silent rounding change there would reorder ``best_dev_eligible`` for no reason.
    """
```
**Impact:** `Metrics(...)` is constructed by keyword everywhere; the new default keeps every caller
and every `dataclasses.replace` working.

### Step 3: `strategy_metrics` takes the cashflows

**File:** `engine/src/seer_engine/backtest/metrics.py:109-146`
**Change:** one new defaulted parameter and one new computed field.
**Code:**
```python
def strategy_metrics(
    snaps: Sequence[tuple[date, float]],
    pnls: Sequence[float],
    cashflows: Sequence[tuple[date, float]] = (),
) -> Metrics:
    """``strategyMetrics`` from web/lib/metrics.ts, plus CAGR over the same snapshots, plus the
    money-weighted return when the run received deposits.

    ``snaps`` are ``(date, equity)`` in date order; ``pnls`` are closed trades' P/L in USD.
    A win is ``p > 0`` and a loss is ``p <= 0``. Profit factor is gross win / gross loss, or
    ``inf`` when trades exist and the gross loss is 0, or None with no trades. Max drawdown is
    the largest ``(peak - equity) / peak`` over the snapshots. Total return is
    last / first - 1. Months is calendar days / 30.44.

    ``cashflows`` are external deposits, ``(date, amount)`` with ``amount > 0``, dated by the
    session they were applied on. Empty (the default, and every caller before the contribution
    schedule existed) leaves ``mwr`` None and every other field byte-for-byte as it was.

    ``total_return`` and ``cagr`` are **deliberately left as they are** when deposits exist, and
    are then not returns at all -- they are the recorded shape of the curve, which readers of the
    128 historical trials depend on. ``mwr`` is the number that answers "what did the money
    earn". See ``money_weighted_return``.
    """
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gross_win = _sum(wins)
    gross_loss = -_sum(losses)

    peak = -math.inf
    max_dd = 0.0
    for _, equity in snaps:
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)

    first = snaps[0] if snaps else None
    last = snaps[-1] if snaps else None
    n = len(pnls)
    if n == 0:
        profit_factor: float | None = None
    elif gross_loss == 0:
        profit_factor = math.inf
    else:
        profit_factor = gross_win / gross_loss
    return Metrics(
        total_return=None if first is None or last is None else last[1] / first[1] - 1,
        win_rate=len(wins) / n if n else None,
        profit_factor=profit_factor,
        max_drawdown=max_dd if snaps else None,
        trades=n,
        months=0.0 if first is None or last is None else (last[0] - first[0]).days / MONTH_DAYS,
        cagr=None if first is None or last is None else cagr_between(first, last),
        mwr=None if not cashflows else money_weighted_return(snaps, cashflows),
    )
```
**Impact:** every existing call site (`run_metrics`, `curve_metrics`, `book_runner._book_metrics`,
the tests) passes two arguments and is unchanged.

### Step 4: `external_cashflows`, and `run_metrics` / `curve_metrics` pass them

**File:** `engine/src/seer_engine/backtest/metrics.py:178-215`
**Change:** add the single reader of phase 5's field and wire both metric entry points.
**Code:**
**Import cycle — measured, not hypothetical.** `book_runner.py:48` is
`from seer_engine.backtest.metrics import YEAR_DAYS, Metrics, run_metrics, strategy_metrics`, so
`metrics.py` **must not import `book_runner`**. `external_cashflows` therefore takes `Any` and names
both result types in its docstring. Add `from typing import Any` to `metrics.py`'s imports; do not
add a `BookResult` import.

**Code:**
```python
def external_cashflows(r: Any) -> tuple[tuple[date, float], ...]:
    """The external deposits a run received, as floats for the money-weighted return.

    ``r`` is a ``backtest.runner.RunResult`` or a ``backtest.book_runner.BookResult``. It is typed
    ``Any`` rather than their union because ``book_runner`` imports *this* module (``:48``), so an
    import here would close a cycle.

    **This is the one place that reads phase 5's field.** ``RunResult.cashflows`` and
    ``BookResult.cashflows`` are ``tuple[tuple[date, Decimal], ...]``: the deposits the run
    applied, dated by the NYSE session they were applied on (not by the schedule's calendar date,
    which the calendar lags by a measured mean of 7.0 days), ascending, amounts > 0, the opening
    cash excluded, ``()`` for a run with no schedule. If that field is ever renamed, this function
    is the only edit.
    """
    return tuple((when, float(amount)) for when, amount in r.cashflows)


def run_metrics(r: RunResult) -> Metrics:
    """Metrics of a strategy run: its per-session snapshots, every closed order (forced included),
    and the deposits it received."""
    snaps = [(s.date, float(s.equity_usd)) for s in r.snapshots]
    pnls = [float(o.pnl_usd) for o in r.closed if o.pnl_usd is not None]
    base = strategy_metrics(snaps, pnls, external_cashflows(r))
    return replace(base, avg_days_held=avg_days_held(r.closed), exit_reasons=exit_reason_counts(r.closed))
```
and
```python
def curve_metrics(c: BenchmarkCurve) -> Metrics:
    """Metrics of a buy-and-hold curve: no trades, so win rate and profit factor are None.

    ``c.cashflows`` are the deposits the curve received, so a dollar-cost-averaged SPY reports a
    money-weighted return computed from the same dollars on the same days as the book it is
    benchmarking.
    """
    return strategy_metrics(
        [(s.date, float(s.equity_usd)) for s in c.snapshots], (), c.cashflows
    )
```
**Imports:** `metrics.py:16-27` gains one line, `from typing import Any`. Nothing else: the
`RunResult` import at `:26` stays, and `BookResult` is deliberately not imported (see the cycle note
above).
**Impact:** `run_metrics` now reads `r.cashflows`, which phase 5 puts on `RunResult`. Both metric
entry points — the strategy's and the benchmark's — now carry the deposits that produced them.

### Step 5: `BenchmarkCurve` carries its cashflows

**File:** `engine/src/seer_engine/backtest/benchmark.py:53-67`
**Change:** one defaulted field.
**Code:**
```python
@dataclass(frozen=True)
class BenchmarkCurve:
    """A buy-and-hold equity curve.

    ``snapshots[0]`` is ``Snapshot(prev_session(start), cash0, cash0)``; then one per session
    ``start..end``. ``shares`` and ``cash`` are the holding after ``end``; ``dividends_usd`` is
    the total cash dividends credited (0 for the price-only curve).

    ``cashflows`` are the deposits this curve received, summed per landing session and ascending:
    ``()`` for a plain buy-and-hold, and the dollar-cost-averaging schedule for a curve built with
    ``contributions``. ``metrics.curve_metrics`` reads it, so the money-weighted return of the
    benchmark is computed from the same dollars on the same days as the book's.
    """

    name: str
    snapshots: tuple[Snapshot, ...]
    shares: int | Decimal  # whole shares, or a multiple of SHARE_QUANTUM when fractional
    cash: Decimal
    dividends_usd: Decimal
    cashflows: tuple[tuple[date, Decimal], ...] = ()
```
**Impact:** measured — all seven construction sites (`benchmark.py:236`, and
`test_backtest_wf_report.py:128`, `test_backtest_b_report.py:211`, `test_backtest_report.py:83`,
`test_backtest_metrics.py:295`, `test_backtest_dev_report.py:208`, `test_backtest_walkforward.py:596`)
use keywords, so a defaulted trailing field breaks none of them.

### Step 6: `buy_and_hold` receives contributions

**File:** `engine/src/seer_engine/backtest/benchmark.py:161-242` (whole function replaced)
**Change:** a keyword-only `contributions`, landed on the first session on or after each date, and
credited through the same single buy the dividend path already uses.
**Code:**
```python
def _landing(window: Sequence[date], d: date) -> date | None:
    """The first session in ``window`` on or after ``d``; None when ``d`` is after the window.

    Resolved against the window already in hand rather than through ``dates.next_session``, so a
    deposit can never land outside the curve it funds. ``next_session`` is also strictly *after*
    its argument, which would push a deposit dated on a trading day to the following one.
    """
    i = bisect_left(window, d)
    return window[i] if i < len(window) else None


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
    contributions: Sequence[tuple[date, Decimal]] = (),
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

    ``contributions`` are ``(date, amount)`` deposits in USD, strictly ascending, each amount a
    ``Decimal`` > 0. This is the **dollar-cost-averaged** benchmark: the same money, paid in on
    the same days, put into SPY instead -- without it, "beats SPY TR" compares a book fed
    5,000,000 IDR a month against a single opening sum, which flatters the book in a rising
    market and punishes it in a falling one, because the two are holding different amounts at
    different times.

    Each deposit lands as cash at the close of the first session **on or after** its calendar
    date, and is spent at that close. The owner's schedule deposits on the 25th and the NYSE
    calendar produces the gap to the next session -- measured, a mean of 7.0 calendar days
    ranging 4 (Feb 2027) to 10 (Dec 2026) -- so the idle cash is reproduced rather than assumed
    away. A deposit whose landing session is on or before ``start``, or after ``end``, is
    dropped: the opening cash is the opening cash, exactly as a dividend dated on ``start`` is
    not credited. Two deposits landing on one session are summed and spent in one buy.

    SPY buys as the money arrives, while a book waits for its rotation, so SPY's idle gap is the
    shorter of the two and the benchmark is the harder to beat. That direction is deliberate.
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

    deposits: dict[date, Decimal] = {}
    previous: date | None = None
    for when, amount in contributions:
        if isinstance(when, datetime) or not isinstance(when, date):
            raise TypeError(f"a contribution date must be a date, got {type(when).__name__}")
        if not isinstance(amount, Decimal):
            raise TypeError(f"a contribution amount must be a Decimal, got {type(amount).__name__}")
        if amount <= 0:
            raise ValueError(f"a contribution must be > 0, got {amount} on {when}")
        if previous is not None and when <= previous:
            raise ValueError(f"contributions not strictly ascending at {when}")
        previous = when
        session = _landing(window, when)
        if session is None or session <= start:
            continue
        deposits[session] = deposits.get(session, Decimal("0.0000")) + q(amount)

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
        reinvest = False
        amount = paid.get(d)
        if amount is not None:
            income = q(shares * amount)
            cash += income
            credited += income
            reinvest = True
        deposit = deposits.get(d)
        if deposit is not None:
            cash += deposit
            reinvest = True
        if reinvest:
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
        cashflows=tuple(sorted(deposits.items())),
    )
```
**Imports:** add at `benchmark.py:29`:
```python
from bisect import bisect_left
```
and extend the `datetime` import at `:31` to `from datetime import date, datetime`.
**Impact:** the `reinvest` flag, not a truthiness test on the credited amount, is what keeps the
contribution-free path **byte-identical**: today a dividend session with zero shares held still
runs the buy, and a `if income:` guard would silently stop doing that. `engine/tests/test_benchmark.py`
and `test_paper_benchmark.py` (which compares `paper/benchmark.py` night-by-night against this
function) must both pass unchanged.

### Step 7: `spy_curves` passes them to both curves

**File:** `engine/src/seer_engine/backtest/benchmark.py:245-260`
**Code:**
```python
def spy_curves(
    spy: Mapping[date, Bar],
    start: date,
    end: date,
    initial_cash: Decimal,
    dividends: Sequence[Dividend],
    *,
    cost_model: CostModel = "flat",
    contributions: Sequence[tuple[date, Decimal]] = (),
) -> tuple[BenchmarkCurve, BenchmarkCurve]:
    """``(spy_price, spy_tr)``: the price-only and total-return SPY curves over one window,
    both paying ``cost_model`` and both receiving ``contributions`` (see ``buy_and_hold``).

    Both curves get the deposits, not just the total-return one: ``spy_price`` is the same
    comparison with dividends withheld, and a price-only curve fed differently from the
    total-return one would not be that.
    """
    price = buy_and_hold(
        spy, start, end, initial_cash, name=PRICE_CURVE, cost_model=cost_model,
        contributions=contributions,
    )
    total = buy_and_hold(
        spy, start, end, initial_cash, dividends=dividends, name=TOTAL_RETURN_CURVE,
        cost_model=cost_model, contributions=contributions,
    )
    return price, total
```
**Impact:** both existing callers (`dev.py:435`, `commands/backtest_dev.py:275`,
`commands/backtest_b.py:187`) pass no `contributions` and are unchanged.

### Step 8: the restated condition, in one place

**File:** `engine/src/seer_engine/backtest/dev.py:286` (immediately above the `# --- rows` banner)
**Change:** add the pure predicate that both `make_row` and `lab.store.owner_failures` use.
**Code:**
```python
def beats_spy_tr(
    total_return: float | None,
    spy_total_return: float | None,
    mwr: float | None = None,
    spy_mwr: float | None = None,
) -> bool:
    """``FAILURE_LABELS[0]``: does this run beat total-return SPY? The single definition.

    **Money-weighted when both sides have one**, and the total-return comparison otherwise.

    Once a book receives deposits, its total return is not a return: measured on the owner's real
    funding plan, a book that earns nothing at all reports +600.0%. So when both the run and its
    benchmark carry a money-weighted return -- which happens exactly when both were fed a
    contribution schedule -- the comparison is made in that, the rate the money actually earned.

    The fallback is not a second bar, it is the same condition in the only number the row has.
    Every one of the 128 recorded lab trials ran with no deposits and has no money-weighted
    return, so every one of them is judged exactly as it is today and no recorded verdict changes
    meaning. ``lab.store.owner_failures`` calls this rather than writing the comparison again, so
    the gate cannot drift between the runner and the re-read.

    Worth knowing: when SPY is dollar-cost-averaged on the identical schedule from the identical
    opening cash, the two branches agree in direction anyway -- both sides divide by the same
    opening cash, so comparing total returns *is* comparing ending equity. The money-weighted
    branch is what makes the number a human reads true, and what keeps the comparison right if
    the two sides are ever fed differently.
    """
    if mwr is not None and spy_mwr is not None:
        return mwr > spy_mwr
    return total_return is not None and spy_total_return is not None and total_return > spy_total_return
```
**Impact:** pure addition.

### Step 9: `make_row` uses it, and MAR becomes money-weighted when funded

**File:** `engine/src/seer_engine/backtest/dev.py:351-399` (whole function replaced)
**Code:**
```python
def make_row(
    candidate: Candidate,
    start: date,
    end: date,
    stats: RunStats,
    *,
    spy_tr: Metrics,
    spy_price: Metrics,
    window: Window = DEV_WINDOW,
) -> DevRow:
    """The ``DevRow`` for ``candidate``: SPY comparison, MAR and the D8 eligibility checks.

    MAR = rate / max drawdown (None when either is None or the drawdown is 0). The rate is the
    **money-weighted return** when the run received deposits, and the CAGR otherwise -- which is
    the same number, because with no deposits CAGR *is* the money-weighted return. Without the
    switch, a book fed 5,000,000 IDR a month would rank on a CAGR that counts its own deposits as
    growth: measured, a book that earns nothing reports +600.9%, which would outrank every honest
    candidate in the registry.

    Thresholds are read from ``tuning`` at call time; owner inputs are
    ``candidate_owner_inputs(candidate)``. ``window`` defaults to ``DEV_WINDOW`` and is carried
    onto the row.
    """
    if not isinstance(candidate, Candidate):
        raise TypeError(f"expected a Candidate, got {type(candidate).__name__}")
    if not isinstance(stats, RunStats):
        raise TypeError(f"stats must be a RunStats, got {type(stats).__name__}")
    if not isinstance(spy_tr, Metrics):
        raise TypeError(f"spy_tr must be a Metrics, got {type(spy_tr).__name__}")
    m = stats.metrics
    beats = beats_spy_tr(m.total_return, spy_tr.total_return, m.mwr, spy_tr.mwr)
    rate = m.cagr if m.mwr is None else m.mwr
    if rate is None or m.max_drawdown is None or m.max_drawdown == 0:
        mar: float | None = None
    else:
        mar = float(rate / m.max_drawdown)
    passed = (
        beats,
        m.max_drawdown is not None and m.max_drawdown <= tuning.MAX_DRAWDOWN,
        m.profit_factor is not None and m.profit_factor >= tuning.MIN_PROFIT_FACTOR,
        m.trades >= _MIN_TRADES,
        not candidate_owner_inputs(candidate),
    )
    failed = tuple(label for label, ok in zip(FAILURE_LABELS, passed) if not ok)
    return DevRow(
        candidate=candidate,
        start=start,
        end=end,
        stats=stats,
        spy_tr=spy_tr,
        spy_price=spy_price,
        beats_spy=bool(beats),
        mar=mar,
        eligible=not failed,
        failed=failed,
        window=window,
    )
```
**Impact:** on an unfunded run `m.mwr` is `None`, `rate` is `m.cagr`, and `beats_spy_tr` takes the
total-return branch — every existing row is **bit-for-bit** what it is today. That is the whole
reason `mwr` is `None` rather than a recomputed CAGR (D7b).

### Step 10: SPY is fed the money the book was fed

**File:** `engine/src/seer_engine/backtest/dev.py:433-435`
**Change:** pass the run's own cashflows into the benchmark.
**Code:**
```python
    # The benchmark pays what the candidate pays and is fed what the candidate is fed: Gotrade's
    # schedule for a cost_model="gotrade" rule set, the flat 0.1% (unchanged) otherwise, and the
    # candidate's own deposits on the candidate's own dates.
    #
    # `result.cashflows` are already in USD and already dated by the session they landed on, so
    # SPY receives the identical dollars on the identical days however the runner resolved the
    # IDR schedule and the FX. "Beats SPY TR" only means anything when it does: SPY buy-and-hold
    # of a single opening sum against a book fed 5,000,000 IDR a month flatters the book in a
    # rising market and punishes it in a falling one, because the two are holding different
    # amounts of money at different times.
    price, total = spy_curves(
        spy,
        start,
        end,
        result.initial_cash,
        spy_dividends,
        cost_model=c.rules.cost_model,
        contributions=metrics_mod.external_cashflows(result),
    )
```
**Imports:** `dev.py:50` imports `Metrics, curve_metrics` from `metrics`. Extend it:
```python
from seer_engine.backtest.metrics import Metrics, curve_metrics, external_cashflows
```
and use the bare name `external_cashflows(result)` in the call above (drop the `metrics_mod.`
prefix; it is written that way only to make the origin obvious while reading this plan).
**Impact:** `run_stats(result)` already reads `result.snapshots`, and `metrics.run_metrics` now
reads `result.cashflows` through the same helper, so the book and SPY are provably given the same
list. This is the single line that satisfies the second half of handover §4.

### Step 10b: a schedule can actually reach `dev._run` — the keyword phase 8 runs on

**File:** `engine/src/seer_engine/backtest/dev.py` — `run_registry`'s keyword list, `_run`'s keyword
list, and the `run_rules(...)` call inside `_run`.
**Change:** **added by the reconciler, 2026-10-08.** Step 10 above feeds SPY `result.cashflows` — but
`result.cashflows` is `()` for every run, because nothing in `dev.py` can hand phase 5's schedule to
`run_rules`. The measurement in **Goal** is therefore unreachable from the dev path, and **phase 8's
whole sweep cannot run**: `phase-8.md` states as its *Requires* #3 that *"phase 7 gives
`dev.run_registry` a keyword that carries the schedule into the book and into `spy_curves`"*, and
its `check_schedule_support()` refuses readably when the keyword is absent. Phase 8 depends on this
phase, so this is the phase that must supply it.

**Code** — `run_registry` and `_run` each gain the same trailing keyword-only parameter, passed
straight through:

```python
def run_registry(
    market: Market,
    dividends: DividendMap,
    spy_dividends: Sequence[Dividend],
    registry: Sequence[Candidate],
    *,
    window: Window = DEV_WINDOW,
    contributions: ContributionSchedule | None = None,
) -> tuple[DevRow, ...]:
    """... (existing docstring unchanged, plus:)

    ``contributions`` is the funding schedule every candidate is run on
    (``sim.contributions.ContributionSchedule``), or None -- the default, and what every caller in
    the tree passes, so every recorded trial and every gate run is byte-for-byte unchanged. When it
    is given, the book is fed the deposits AND ``spy_curves`` receives the same dollars on the same
    sessions (Step 10), so "beats SPY TR" stays a comparison of two books holding the same money.
    """
```

and inside `_run`, the `run_rules(...)` call gains `contributions=contributions`:

```python
    result = run_rules(
        market, obj, params, c.rules, start, end,
        prepared=prepared, dividends=dividends, contributions=contributions,
    )
```

(keep every other argument of that call exactly as it stands; only the one keyword is added. Phase 5
added `contributions` to `run_rules` as a pass-through to whichever engine the rules name.)

**Imports:** `dev.py` gains
`from seer_engine.sim.contributions import ContributionSchedule` — type-only, and the module is pure.

**Code — phase 4's Handoff H3, assigned here by the reconciler.** `dev.py:185`, `:206` and `:223`
each branch on `rules.engine == "bracket_v0"` to tell a bracket candidate from a book one. Phase 4
adds a second bracket engine, `"bracket"`, so each becomes:

```python
    if is_bracket(c.rules):
```

with `is_bracket` added to `dev.py`'s `seer_engine.sim.rules` import. Harmless today — no
`"bracket"` candidate is registered anywhere the dev registry can see — and a trap for whoever first
registers one, which is why it lands with the rest of the bracket vocabulary rather than later.

**Impact:** both changes are no-ops on every existing call. `run_registry`'s six production callers
(`tuning.gate`, `walkforward.gate_p3b`, `b_walkforward.gate_p6a`, `commands/backtest_dev.py`,
`commands/backtest_b.py`, `paper/replay.py`) pass no schedule, so `contributions` is None,
`result.cashflows` is `()`, `Metrics.mwr` is None, `make_row` takes the CAGR branch, and every
recorded row is bit-for-bit what it is today — which is exactly what D7b exists to guarantee.

### Step 11: schema v4 — the `trial_funding` side table

**File:** `engine/src/seer_engine/lab/store.py`

**11a — the table and its triggers**, inserted at `:230` (directly after `_MOMENTS_TRIGGERS`, before `_SCHEMA`):
```python
# The trial_funding side table and its two triggers, one statement each. ``_SCHEMA`` creates them
# on a new database; ``_migrate`` creates them on a v3 database. Deliberately separate constants
# rather than inline SQL, for the same reason ``_MOMENTS_TABLE`` is: exactly one definition of the
# v4 table, so the migration cannot drift from the fresh schema.
#
# **Why a side table and not two columns on ``trials``.** ``trials`` is append-only and
# ``test_lab_snapshot.py`` pins it byte-identical across a migration; ``ALTER TABLE trials ADD
# COLUMN`` would break that and would put two permanently-NULL columns on 128 rows. Here, the
# *existence* of a row is the funded flag: a trial with no funding row received no deposits, which
# is true of every trial recorded before the contribution schedule existed, with no NULL to read
# two ways. ``trial_n`` is the primary key, so a trial has at most one funding row and ``INSERT``
# is the whole lifecycle.
#
# ``mwr`` and ``spy_tr_mwr`` are nullable for the same reason ``trials.cagr`` is: a run whose
# money-weighted return is undefined (a book wiped out, a zero-day window) records NULL rather
# than a wrong number.
_FUNDING_TABLE = """CREATE TABLE IF NOT EXISTS trial_funding (
    trial_n      INTEGER PRIMARY KEY REFERENCES trials(n),
    mwr          REAL,
    spy_tr_mwr   REAL,
    deposits_usd REAL NOT NULL CHECK (deposits_usd > 0),
    deposits_n   INTEGER NOT NULL CHECK (deposits_n >= 1),
    schedule     TEXT NOT NULL CHECK (length(trim(schedule)) > 0),
    measured     TEXT NOT NULL CHECK (length(trim(measured)) > 0)
)"""
_FUNDING_TRIGGERS: tuple[str, ...] = (
    """CREATE TRIGGER IF NOT EXISTS trial_funding_no_update BEFORE UPDATE ON trial_funding
BEGIN SELECT RAISE(ABORT, 'trial_funding are append-only: a funding row is never updated'); END""",
    """CREATE TRIGGER IF NOT EXISTS trial_funding_no_delete BEFORE DELETE ON trial_funding
BEGIN SELECT RAISE(ABORT, 'trial_funding are append-only: a funding row is never deleted'); END""",
)
```

**11b — `_SCHEMA`**, at `:313` (after `{_MOMENTS_TRIGGERS[1]};`, before the `trials_no_update` trigger):
```
{_FUNDING_TABLE};

{_FUNDING_TRIGGERS[0]};

{_FUNDING_TRIGGERS[1]};
```

**11c — the version**, `:62`:
```python
SCHEMA_VERSION = "4"  # 2: the synthesis insight kind; 3: trial_moments; 4: trial_funding (see _migrate)
```

**11d — the migration step**, inserted at `:431` (after `_v2_to_v3`, before `_migrate`):
```python
def _v3_to_v4(conn: sqlite3.Connection) -> None:
    """Add the ``trial_funding`` side table and its two append-only triggers.

    Purely additive, exactly as ``_v2_to_v3`` was and for the same reason: no ``trials`` row is
    read, written, rebuilt or re-keyed, no column is altered, and no verdict moves. A v3 database
    that migrates and is then never written again differs from its v3 self only by an empty table,
    two triggers and the ``schema_version`` string -- and ``trials`` is byte-identical, which
    ``test_connect_migrates_a_v3_database_adding_trial_funding_and_touching_no_trial`` pins.

    This is why the money-weighted return is a side table rather than two columns on ``trials``:
    ``ALTER TABLE trials ADD COLUMN`` would move every recorded row's bytes.
    """
    conn.execute(_FUNDING_TABLE)
    for trigger in _FUNDING_TRIGGERS:
        conn.execute(trigger)
```

**11e — the ladder**, replacing `:453-458` inside `_migrate`:
```python
        found = schema_version(conn)
        version = found
        if version == "1":
            _v1_to_v2(conn)
            version = "2"
        if version == "2":
            _v2_to_v3(conn)
            version = "3"
        if version == "3":
            _v3_to_v4(conn)
            version = "4"
        if version != SCHEMA_VERSION:
```
and the `_migrate` docstring's ladder sentence (`:437-440`) becomes:
```
    A ladder: each step moves the database up exactly one version, so a v1 database reaches v4 in
    one open by running all three steps in order. v1 -> v2 adds the ``synthesis`` insight kind
    (``_v1_to_v2``); v2 -> v3 adds the ``trial_moments`` side table (``_v2_to_v3``); v3 -> v4 adds
    the ``trial_funding`` side table (``_v3_to_v4``). A version this code does not know is refused
    rather than guessed at.
```

**11f — the module docstring**, `:24-25`:
```
Schema versions (``meta.schema_version``): 1 is the first lab; 2 adds the ``synthesis`` insight
kind; 3 adds the ``trial_moments`` side table; 4 adds the ``trial_funding`` side table (the
money-weighted return of a trial that received deposits, and of the SPY fed the same ones).
``connect`` migrates an older database in place; ``connect_readonly`` never does.
```
and the `trials` bullet at `:20-22` gains a sibling after the `trial_moments` one:
```
- ``trial_funding``: the money-weighted return of one trial that received deposits, and of the
  dollar-cost-averaged SPY it was measured against, with the deposits themselves. **A trial with
  no row here received no deposits** -- true of every trial recorded before the contribution
  schedule existed -- so its ``cagr`` already is its money-weighted return. At most one row per
  trial, keyed by ``trials.n``. Triggers refuse every UPDATE and DELETE.
```
**Impact:** `connect` runs `_SCHEMA` before `_migrate`, so on a fresh database `_v3_to_v4`'s two
statements are no-ops; on the committed v3 database they create the table. `lab/lab.sqlite` is not
touched by this phase and migrates itself on its next `lab` write.

### Step 12: `FundingRow`, `insert_funding`, `funding_of`

**File:** `engine/src/seer_engine/lab/store.py:1565` (after `moments_of`, before the `ideas_seen` banner)
**Code:**
```python
# --------------------------------------------------------------------------- trial funding


@dataclass(frozen=True)
class FundingRow:
    """What one trial's deposits were, and what they earned (schema v4).

    A trial has a row here **exactly when it received deposits**. Every trial recorded before the
    contribution schedule existed has none, and for those ``trials.cagr`` already is the
    money-weighted return: with no money going in or out after the start, the two are the same
    number (measured: they agree to 5e-14).

    - ``trial_n``      the ``trials.n`` this describes. ``insert_trials`` assigns it, so a row
                       built before the insert carries ``0`` and is stamped with
                       ``dataclasses.replace(row, trial_n=n)`` afterwards; ``insert_funding``
                       refuses ``0``.
    - ``mwr``          the **money-weighted return**: the interest rate a savings account would
                       have had to pay to turn the same deposits, paid in on the same days, into
                       the same final balance. ``backtest.metrics.money_weighted_return``. NULL
                       when undefined (a book wiped out), never when merely unflattering.
    - ``spy_tr_mwr``   the same measure for the **dollar-cost-averaged** total-return SPY curve --
                       the same money, paid in on the same days, put into SPY instead. This is the
                       number ``beats SPY TR`` compares against for a funded trial.
    - ``deposits_usd`` the total deposited after the opening cash, in USD.
    - ``deposits_n``   how many deposits that was.
    - ``schedule``     the schedule in the owner's own words, e.g.
                       ``"+5,000,000 IDR on the 25th of each month"``, so a reader of the row
                       never has to reconstruct it from the dates.
    - ``measured``     an ISO timestamp; for a trial recorded by ``lab run`` this is the trial's
                       own ``run_at``, so the pair is one measurement with one stamp.
    """

    trial_n: int
    mwr: float | None
    spy_tr_mwr: float | None
    deposits_usd: float
    deposits_n: int
    schedule: str
    measured: str


FUNDING_COLUMNS: tuple[str, ...] = tuple(f.name for f in fields(FundingRow))


def funding_of(conn: sqlite3.Connection, trial_n: int) -> sqlite3.Row | None:
    """The recorded funding for one trial, or None when it received no deposits.

    None is the normal answer for every trial recorded before this table existed -- all 128 of
    them -- and it means something definite rather than something missing: this run was not fed,
    so its ``cagr`` is already its money-weighted return and ``total_return`` is already a return.
    A caller must therefore have a fallback for None; it is never an error.

    A database on schema v1, v2 or v3 has no ``trial_funding`` table at all, which is the limiting
    case of "recorded before this table existed" and is answered the same way. ``connect``
    migrates, so this can only be a ``connect_readonly`` caller -- ``snapshot`` is one, and its
    promise to work on an unmigrated read-only connection is what this branch keeps. ``moments_of``
    carries the same branch for the same reason.
    """
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'trial_funding'"
    ).fetchone() is None:
        return None
    return conn.execute(
        "SELECT * FROM trial_funding WHERE trial_n = ?", (int(trial_n),)
    ).fetchone()


def insert_funding(conn: sqlite3.Connection, rows: Sequence[FundingRow]) -> None:
    """Record the deposits and the money-weighted returns for trials that already exist (the
    caller holds the transaction).

    Append-only and one row per trial: a trial that already has funding is refused rather than
    overwritten, so a backfill can be made idempotent by skipping what ``funding_of`` already
    returns instead of racing the triggers. ``trial_n`` must be a real trial number -- the foreign
    key enforces that the trial exists, and the explicit check below turns the pre-insert sentinel
    ``0`` into a readable refusal rather than a foreign-key error from inside a long run.
    """
    cols = ", ".join(f'"{c}"' for c in FUNDING_COLUMNS)
    marks = ", ".join("?" for _ in FUNDING_COLUMNS)
    for r in rows:
        if r.trial_n <= 0:
            raise LabError(
                f"funding needs the trial number insert_trials assigned, got {r.trial_n!r}: "
                "insert the trial first, then stamp its funding with dataclasses.replace"
            )
        if funding_of(conn, r.trial_n) is not None:
            raise LabError(
                f"trial {r.trial_n} already has recorded funding: trial_funding is append-only, "
                "and a second measurement of the same trial would be a second verdict"
            )
        conn.execute(
            f"INSERT INTO trial_funding ({cols}) VALUES ({marks})",
            [getattr(r, c) for c in FUNDING_COLUMNS],
        )
```
**Impact:** pure addition, mirroring `MomentsRow` / `insert_moments` / `moments_of` exactly.

### Step 13: `owner_failures` reads the restated condition

**File:** `engine/src/seer_engine/lab/store.py:980-1024` (whole function replaced)
**Code:**
```python
def _opt_float(x: Any) -> float | None:
    """A recorded REAL as a float, or None. Unlike ``_num`` this does **not** round: it feeds a
    gate comparison, not a JSON document."""
    return None if x is None else float(x)


def owner_failures(
    trial: Mapping[str, Any] | sqlite3.Row,
    funding: Mapping[str, Any] | sqlite3.Row | None = None,
) -> tuple[str, ...]:
    """The five P7a D8 conditions ``trial`` misses **as they read now**, in FAILURE_LABELS order.

    **Four re-derived, one carried.** Four of the five are thresholds over numbers ``trials``
    already records, so they are recomputed here from the recorded columns against the live
    constants -- the same comparisons ``dev.py`` makes, on the same values:

    - ``beats SPY TR``  ``dev.beats_spy_tr`` -- money-weighted when ``funding`` carries both
                        sides' rates, and ``total_return > spy_tr_return`` otherwise
    - ``max DD``        ``max_drawdown <= tuning.MAX_DRAWDOWN`` (0.20 since 2026-10-07, phase 8)
    - ``PF``            ``profit_factor >= tuning.MIN_PROFIT_FACTOR``
    - ``trades``        ``trades >= dev._MIN_TRADES``

    The fifth, ``owner inputs``, is **carried from the recorded ``failed`` string**, because it is
    the one condition that is not a threshold: it asks whether a human hand-picked a parameter of
    the *candidate* (``dev.candidate_owner_inputs``), there is no column to recompute it from, and
    no constant re-decides it -- so its recorded label can never go stale.

    **``funding`` is ``store.funding_of(conn, trial["n"])``**, or None. A trial has one exactly
    when it received deposits. Once deposits exist, total return is not a return: measured on the
    owner's real funding plan, a book that earns nothing at all records +600.0%. So a funded row
    is judged on the money-weighted return of the book against the money-weighted return of a SPY
    fed the identical dollars on the identical days. **Every one of the 128 recorded trials has no
    funding row**, so every one of them is judged exactly as it was before this parameter existed
    and no recorded verdict silently changes meaning. The comparison itself lives in
    ``dev.beats_spy_tr`` and is written once.

    **Why nothing is parsed out of ``failed`` for the other four.** ``trials`` is append-only, so
    a recorded label names the bar in force on its run date. All 110 recorded rows carry
    ``"max DD <= 15%"``, and the owner moved that bar to 20% on 2026-10-07; reading the condition
    back out of the string would freeze every recorded trial at the bar it was judged by and
    ``M0020-W-NOSTOP`` (19.3%) could never become eligible. That is precisely the "verdicts mix
    bars" defect R2 names, and it is why this function takes the row rather than the string.

    The returned labels are the **live** ones (``dev.FAILURE_LABELS``), so a caller printing them
    states today's bar, not the one the row was judged by.
    """
    from seer_engine.backtest import dev, tuning

    spy, drawdown, pf, trades, owner = dev.FAILURE_LABELS
    total, bench = trial["total_return"], trial["spy_tr_return"]
    mwr = None if funding is None else funding["mwr"]
    spy_mwr = None if funding is None else funding["spy_tr_mwr"]
    dd, factor, count = trial["max_drawdown"], trial["profit_factor"], trial["trades"]
    out: list[str] = []
    if not dev.beats_spy_tr(
        _opt_float(total), _opt_float(bench), _opt_float(mwr), _opt_float(spy_mwr)
    ):
        out.append(spy)
    if dd is None or float(dd) > tuning.MAX_DRAWDOWN:
        out.append(drawdown)
    if factor is None or float(factor) < tuning.MIN_PROFIT_FACTOR:
        out.append(pf)
    if count is None or int(count) < dev._MIN_TRADES:
        out.append(trades)
    if owner in recorded_labels(trial["failed"]):
        out.append(owner)
    return tuple(out)
```
**Impact:** `commands/lab.py:404` calls `owner_failures(row)` with one argument and is unchanged.
`engine/tests/test_lab_gate_policy.py` calls it with one argument in sixteen places and is unchanged.

### Step 14: `verdict` and `published_verdict` fetch the funding

**File:** `engine/src/seer_engine/lab/store.py:1232` and `:1266`
**Change:** each `failed = owner_failures(trial)` becomes:
```python
    failed = owner_failures(trial, funding_of(conn, trial["n"]))
```
Both functions already take `conn` as their first parameter and both docstrings already state that
`trial` carries `n`. Append to each docstring's list of re-derived conditions, after the sentence
naming the four thresholds:
```
      today's. ``beats SPY TR`` is money-weighted for a trial that received deposits
      (``trial_funding``) and the recorded total-return comparison for every one that did not,
      which is all 128 recorded trials.
```
**Impact:** one extra indexed read per trial. `verdict` is called in a loop over a method's trials
(`reevaluate_method`, `:1382`) — `trial_funding` is keyed by its primary key, so the read is an
index seek, and it returns on the `sqlite_master` check alone for any pre-v4 read-only connection.

### Step 15: `_blocking`, the second independent check

**File:** `engine/src/seer_engine/lab/store.py:1294-1326`
**Change:** the signature and the first condition. The function deliberately writes the comparisons
a second time (its docstring says so), so `beats_spy_tr` is **not** called here — the money-weighted
branch is written out again, on purpose.
**Code:**
```python
def _blocking(
    trial: Mapping[str, Any] | sqlite3.Row,
    funding: Mapping[str, Any] | sqlite3.Row | None = None,
) -> tuple[str, ...]:
    """The second, independent no: why this trial may **not** take the ``rejected`` edge.

    ``owner_failures`` derives the same four conditions and ``verdict`` reads it, so these
    comparisons are written here a second time **on purpose**. Two owner-set bars moved in this
    plan set -- the luck threshold (phase 4) and the drawdown threshold (phase 8) -- and a gate
    that loosens on two axes at once should not be able to promote a method through a single
    expression. A future change to ``owner_failures`` has to get past this too. That is also why
    the money-weighted branch below is spelled out rather than delegated to ``dev.beats_spy_tr``.

    Phrased as sentences with the numbers in them, because this text goes into the refusal a
    human reads.
    """
    from seer_engine.backtest import dev, tuning

    out: list[str] = []
    mwr = None if funding is None else funding["mwr"]
    spy_mwr = None if funding is None else funding["spy_tr_mwr"]
    if mwr is not None and spy_mwr is not None:
        if float(mwr) <= float(spy_mwr):
            out.append(
                f"money-weighted return {mwr!r} does not beat the SPY TR fed the same deposits "
                f"{spy_mwr!r}"
            )
    else:
        total, bench = trial["total_return"], trial["spy_tr_return"]
        if total is None or bench is None or float(total) <= float(bench):
            out.append(f"total return {total!r} does not beat SPY TR {bench!r}")
    dd = trial["max_drawdown"]
    if dd is None or float(dd) > tuning.MAX_DRAWDOWN:
        out.append(f"max drawdown {dd!r} is outside the {tuning.MAX_DRAWDOWN:.0%} bar")
    factor = trial["profit_factor"]
    if factor is None or float(factor) < tuning.MIN_PROFIT_FACTOR:
        out.append(f"profit factor {factor!r} is under {tuning.MIN_PROFIT_FACTOR}")
    count = trial["trades"]
    if count is None or int(count) < dev._MIN_TRADES:
        out.append(f"{count!r} closed trades is under {dev._MIN_TRADES}")
    if OWNER_INPUTS_LABEL in recorded_labels(trial["failed"]):
        out.append(
            f"it recorded {OWNER_INPUTS_LABEL!r}, which is a property of the candidate and which "
            f"no threshold re-decides"
        )
    return tuple(out)
```
**File:** `engine/src/seer_engine/lab/store.py:1386`
```python
        blocking = _blocking(t, funding_of(conn, t["n"]))
```
**Impact:** `dev` is now imported for `_MIN_TRADES` only in the fallback path, so the local import
stays. No caller outside this module uses `_blocking`.

### Step 16: the metrics tests

**File:** `engine/tests/test_backtest_metrics.py` (append; extend the import list at `:22-40` with
`money_weighted_return` and `external_cashflows`)
**Code:**
```python
# --------------------------------------------------------------------------- money-weighted return
#
# The measure R3 asks for: the interest rate a savings account would have had to pay to turn the
# same deposits, paid in on the same days, into the same final balance. Every number below was
# produced by the code under test; the +600.9% figure is the reason this phase exists.


def _flat_curve(start: date, end: date, v0: float, v1: float) -> list[tuple[date, float]]:
    """Two snapshots: the opening cash and the final mark. Enough for every IRR property."""
    return [(start, v0), (end, v1)]


def test_with_no_deposits_the_money_weighted_return_is_exactly_cagr():
    """IRR is a strict generalisation of CAGR: with one sum in and one valuation out, the root of
    -V0 + V1(1+r)^-T is (V1/V0)^(365.25/T) - 1, which is cagr_between."""
    for start, end, v0, v1 in (
        (date(1993, 2, 1), date(2015, 10, 16), 1419.0, 9000.0),
        (date(2005, 1, 3), date(2015, 10, 16), 2000.0, 1200.0),
        (date(2020, 1, 2), date(2026, 10, 8), 100000.0, 180000.0),
        (date(2020, 1, 1), date(2020, 6, 1), 100.0, 100000.0),  # 1.6e7 %/yr: the bracket expands
    ):
        snaps = _flat_curve(start, end, v0, v1)
        mwr = money_weighted_return(snaps, ())
        cagr = cagr_between((start, v0), (end, v1))
        assert mwr is not None and cagr is not None
        assert abs(mwr - cagr) <= 1e-12 * max(1.0, abs(cagr)), (start, end, mwr, cagr)


def test_a_book_that_earns_nothing_on_the_owners_real_plan_reports_zero():
    """The measurement this phase exists for (plan set Decision D4, handover section 4).

    10,000,000 IDR on 2026-11-02 and +5,000,000 IDR on the 25th of each month for twelve months,
    at 16,300 IDR/USD: 613.50 USD then 306.75 USD a month. A book that earns nothing at all ends
    holding exactly what was paid in.
    """
    start, end = date(2026, 11, 2), date(2027, 11, 2)
    deposits: list[tuple[date, float]] = []
    when = date(2026, 11, 25)
    for i in range(12):
        year = when.year + (when.month + i - 1) // 12
        month = (when.month + i - 1) % 12 + 1
        deposits.append((date(year, month, 25), 306.75))
    paid_in = 613.50 + 306.75 * 12
    snaps = _flat_curve(start, end, 613.50, paid_in)

    mwr = money_weighted_return(snaps, deposits)
    assert mwr is not None and abs(mwr) < 1e-9, "a book that earns nothing earned nothing"

    # ...and this is what the two numbers the lab records today would have said instead.
    m = strategy_metrics(snaps, (), deposits)
    assert m.total_return is not None and m.total_return > 5.99  # +600.0%
    assert m.cagr is not None and m.cagr > 6.00                  # +600.9%
    assert m.mwr is not None and abs(m.mwr) < 1e-9


def test_the_sign_of_the_money_weighted_return_follows_the_money():
    start, end = date(2026, 11, 2), date(2027, 11, 2)
    deposits = [(date(2027, 1, 25), 306.75), (date(2027, 4, 26), 306.75)]
    paid_in = 613.50 + 306.75 * 2
    up = money_weighted_return(_flat_curve(start, end, 613.50, paid_in * 1.10), deposits)
    down = money_weighted_return(_flat_curve(start, end, 613.50, paid_in * 0.90), deposits)
    assert up is not None and up > 0
    assert down is not None and down < 0


def test_strategy_metrics_leaves_mwr_none_without_deposits():
    """None means "no deposits, so CAGR already is the money-weighted return" -- and it is what
    keeps dev.make_row's MAR bit-for-bit what it is today on every unfunded run."""
    snaps = _flat_curve(date(2020, 1, 2), date(2026, 10, 8), 100000.0, 180000.0)
    m = strategy_metrics(snaps, ())
    assert m.mwr is None and m.cagr is not None


def test_the_money_weighted_return_is_none_where_cagr_is_none():
    d = date(2026, 11, 2)
    assert money_weighted_return([(d, 100.0)], ()) is None                       # one snapshot
    assert money_weighted_return([(d, 100.0), (d, 120.0)], ()) is None           # zero days
    assert money_weighted_return([(d, 0.0), (date(2027, 1, 2), 120.0)], ()) is None   # no capital
    wiped = [(d, 613.50), (date(2027, 11, 2), 0.0)]
    assert money_weighted_return(wiped, [(date(2027, 1, 25), 306.75)]) is None   # -100%, unbracketed


def test_a_cashflow_outside_the_curve_is_a_programming_error():
    snaps = _flat_curve(date(2026, 11, 2), date(2027, 11, 2), 613.50, 1000.0)
    with pytest.raises(ValueError, match="outside the curve"):
        money_weighted_return(snaps, [(date(2026, 11, 2), 306.75)])  # on the opening snapshot
    with pytest.raises(ValueError, match="outside the curve"):
        money_weighted_return(snaps, [(date(2027, 11, 3), 306.75)])  # after the last mark
    with pytest.raises(ValueError, match="ascend strictly"):
        money_weighted_return(snaps, [(date(2027, 4, 26), 1.0), (date(2027, 1, 25), 1.0)])
    with pytest.raises(ValueError, match="> 0"):
        money_weighted_return(snaps, [(date(2027, 1, 25), -1.0)])
```
**Impact:** `date` and `pytest` are already imported by this file.

### Step 17: the benchmark tests

**File:** `engine/tests/test_backtest_benchmark.py` (**new**; the existing `test_benchmark.py` keeps
the pre-contribution suite and is not edited)

**Every calendar fact below was measured**, not assumed — reproduce with:
```
PYTHONPATH=engine/src python3 -c "
from datetime import date
from seer_engine import dates
for d in [date(2015,12,25), date(2015,12,26), date(2015,12,24), date(2015,6,25), date(2015,3,20)]:
    print(d, dates.is_session(d))"
```
2015-12-25 and 2015-12-26 are **not** sessions and both land on **2015-12-28**; 2015-12-24,
2015-06-25 and 2015-03-20 **are** sessions and land on themselves. 2014-12-25 lands on
2015-01-02, which is `START`, so it is dropped. 2016-01-25 is past `END`, so it is dropped. The
ten `_schedule(date(2015, 2, 25), 10)` deposits land on ten **distinct** sessions — four of them
lagged (04-25 -> 04-27, 05-25 -> 05-26, 07-25 -> 07-27, 10-25 -> 10-26), which is the idle gap
Decision D6 requires be reproduced rather than assumed away.

**Code:**
```python
"""The dollar-cost-averaged SPY benchmark (plan set R3, handover section 4).

"Beats SPY TR" only means something if SPY is fed the same money on the same days as the book it
is compared against. These tests pin that the schedule reaches both curves, that the money lands
on the first session on or after its calendar date (so the owner's 25th-of-the-month deposit is
idle for the measured mean of 7.0 days before it buys anything), and that a curve built with no
contributions is byte-for-byte the curve this module has always produced.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend, buy_and_hold, spy_curves
from seer_engine.backtest.metrics import curve_metrics
from seer_engine.prices import Bar

START = date(2015, 1, 2)
END = date(2015, 12, 31)
CASH0 = Decimal("10000.0000")


def _bar(d: date, price: str) -> Bar:
    """One flat bar. ``Bar`` is ``(symbol, date, open, high, low, close, volume)``
    (``seer_engine/prices.py:19-26``) -- the symbol field is easy to forget."""
    p = Decimal(price)
    return Bar(symbol="SPY", date=d, open=p, high=p, low=p, close=p, volume=1_000_000)


def _bars(start: date, end: date, price: str = "100.00") -> dict[date, Bar]:
    """A flat SPY at one price: every session's open, high, low and close are the same, so a
    curve's equity moves only when cash moves and the arithmetic is readable by hand."""
    return {d: _bar(d, price) for d in dates.sessions(start, end)}


def _schedule(first: date, months: int, amount: str = "500.0000") -> list[tuple[date, Decimal]]:
    """The owner's shape: the 25th of each month, as a calendar date (plan set Decision D6)."""
    out: list[tuple[date, Decimal]] = []
    for i in range(months):
        year = first.year + (first.month + i - 1) // 12
        month = (first.month + i - 1) % 12 + 1
        out.append((date(year, month, 25), Decimal(amount)))
    return out


def test_no_contributions_is_the_curve_this_module_has_always_produced():
    spy = _bars(START, END)
    plain = buy_and_hold(spy, START, END, CASH0, name="spy_price")
    explicit = buy_and_hold(spy, START, END, CASH0, name="spy_price", contributions=())
    assert plain == explicit
    assert plain.cashflows == ()
    assert curve_metrics(plain).mwr is None  # no deposits: CAGR already is the money-weighted return


def test_a_deposit_lands_on_the_first_session_on_or_after_its_date():
    """2015-12-25 was Christmas Day, an NYSE holiday: the money arrives on 2015-12-28."""
    spy = _bars(START, END)
    assert not dates.is_session(date(2015, 12, 25))
    curve = buy_and_hold(
        spy, START, END, CASH0, name="spy_price",
        contributions=[(date(2015, 12, 25), Decimal("500.0000"))],
    )
    assert [d for d, _ in curve.cashflows] == [date(2015, 12, 28)]

    # Measured against the unfunded curve rather than a hand-computed number, so the test states
    # the property -- identical until the money lands, then ahead by it less the fee of spending
    # it -- instead of restating the fee schedule.
    plain = buy_and_hold(spy, START, END, CASH0, name="spy_price")
    before = {s.date: s.equity_usd for s in plain.snapshots}
    after = {s.date: s.equity_usd for s in curve.snapshots}
    assert before[date(2015, 12, 24)] == after[date(2015, 12, 24)], "identical until the money lands"
    gained = after[date(2015, 12, 28)] - before[date(2015, 12, 28)]
    assert Decimal("499") < gained <= Decimal("500"), (
        "a flat market gives back the deposit less the fee of putting it to work"
    )


def test_a_deposit_dated_on_a_session_lands_on_that_session_not_the_next():
    spy = _bars(START, END)
    assert dates.is_session(date(2015, 6, 25))
    curve = buy_and_hold(
        spy, START, END, CASH0, name="spy_price",
        contributions=[(date(2015, 6, 25), Decimal("500.0000"))],
    )
    assert [d for d, _ in curve.cashflows] == [date(2015, 6, 25)]


def test_deposits_outside_the_window_are_dropped_like_a_dividend_on_the_start():
    spy = _bars(START, END)
    curve = buy_and_hold(
        spy, START, END, CASH0, name="spy_price",
        contributions=[
            (date(2014, 12, 25), Decimal("500.0000")),  # lands on START: the opening cash is the opening cash
            (date(2015, 6, 25), Decimal("500.0000")),
            (date(2016, 1, 25), Decimal("500.0000")),   # after END
        ],
    )
    assert [d for d, _ in curve.cashflows] == [date(2015, 6, 25)]


def test_the_deposit_is_spent_so_the_curve_rides_the_market_with_it():
    """A flat market holds the deposit as equity; a rising one must compound it. Buying is what
    makes this dollar-cost averaging rather than a savings account."""
    rising = _bars(START, END)
    for d in dates.sessions(date(2015, 7, 1), END):
        rising[d] = _bar(d, "200.00")
    curve = buy_and_hold(
        rising, START, END, CASH0, name="spy_price",
        contributions=[(date(2015, 2, 25), Decimal("1000.0000"))],
    )
    assert curve.cash < Decimal("200.0000"), "the deposit was put to work, not left idle"
    assert curve.snapshots[-1].equity_usd > CASH0 * 2


def test_two_deposits_landing_on_one_session_are_summed_and_spent_once():
    spy = _bars(START, END)
    curve = buy_and_hold(
        spy, START, END, CASH0, name="spy_price",
        contributions=[
            (date(2015, 12, 25), Decimal("300.0000")),  # holiday -> 12-28
            (date(2015, 12, 26), Decimal("200.0000")),  # weekend -> 12-28
        ],
    )
    assert curve.cashflows == ((date(2015, 12, 28), Decimal("500.0000")),)


def test_both_spy_curves_receive_the_schedule():
    spy = _bars(START, END)
    schedule = _schedule(date(2015, 2, 25), 10)
    divs = (Dividend(ex_date=date(2015, 3, 20), amount=Decimal("1.00")),)
    price, total = spy_curves(spy, START, END, CASH0, divs, contributions=schedule)
    assert price.cashflows == total.cashflows
    assert len(price.cashflows) == 10
    assert total.dividends_usd > 0 and price.dividends_usd == 0


def test_a_dollar_cost_averaged_spy_reports_a_money_weighted_return():
    spy = _bars(START, END)
    schedule = _schedule(date(2015, 2, 25), 10)
    curve = buy_and_hold(spy, START, END, CASH0, name="spy_tr", contributions=schedule)
    m = curve_metrics(curve)
    assert m.mwr is not None, "a curve that was fed deposits has a money-weighted return"
    assert -0.02 < m.mwr < 0.0, (
        "a flat market earns nothing however much you pay into it -- the small negative is the "
        "fee on each buy, which is the only thing that happens here"
    )
    assert m.total_return is not None and m.total_return > 0.4, (
        "...while total return counts the deposits as growth, which is the whole problem"
    )


def test_contributions_are_validated():
    spy = _bars(START, END)
    with pytest.raises(TypeError, match="must be a Decimal"):
        buy_and_hold(spy, START, END, CASH0, name="x", contributions=[(date(2015, 6, 25), 500.0)])
    with pytest.raises(ValueError, match="must be > 0"):
        buy_and_hold(spy, START, END, CASH0, name="x", contributions=[(date(2015, 6, 25), Decimal("0"))])
    with pytest.raises(ValueError, match="not strictly ascending"):
        buy_and_hold(
            spy, START, END, CASH0, name="x",
            contributions=[(date(2015, 6, 25), Decimal("1")), (date(2015, 5, 25), Decimal("1"))],
        )
```
**Note for the implementer:** `benchmark._bar(spy, d)` raises if a bar is keyed under one date and
carries another, so `_bar(d, price)` above must use the same `d` for the key and the field. If
`engine/tests/test_benchmark.py` already exposes a usable bar factory, import it rather than
keeping a second one.

### Step 18: the schema-version pins and the v3 -> v4 migration test

**File:** `engine/tests/test_lab_snapshot.py` — **phase 2's file; see the CONFLICT notice above.
Quote it as phase 2 leaves it.**

**18a — six version pins.** Each reads "this database is at the current schema version", so each
becomes `store.SCHEMA_VERSION`, which cannot go stale again:

| Line (at `485d416`) | From | To |
|---|---|---|
| `:86` | `assert store.schema_version(conn) == "3"` | `assert store.schema_version(conn) == store.SCHEMA_VERSION` |
| `:104` | `assert store.schema_version(again) == "3"` | `assert store.schema_version(again) == store.SCHEMA_VERSION` |
| `:113` | `assert store.schema_version(conn) == store.SCHEMA_VERSION == "3"` | `assert store.schema_version(conn) == store.SCHEMA_VERSION == "4"` |
| `:180` | `assert store.schema_version(conn) == "3"` | `assert store.schema_version(conn) == store.SCHEMA_VERSION` |
| `:207` | `assert store.schema_version(again) == "3"` | `assert store.schema_version(again) == store.SCHEMA_VERSION` |
| `:238` | `assert store.schema_version(ro) == "3"` | `assert store.schema_version(ro) == store.SCHEMA_VERSION` |

`:113` keeps a literal on purpose: it is the one test whose job is to say what the current version
*is*, so exactly one place in the suite has to move when the schema moves again.

**18b — the new migration test**, appended after
`test_connect_migrates_a_v2_database_adding_trial_moments_and_touching_no_trial` (`:209`).
`_v2_db` already builds a database whose `trials` rows the helper `_trials_bytes` can blob, and
`store.connect` runs the whole ladder, so a v2 fixture reaches v4 in one open:
```python
def _funding_schema(conn) -> list[tuple[str, str, str]]:
    return [tuple(r) for r in conn.execute(
        "SELECT type, name, sql FROM sqlite_master WHERE tbl_name = 'trial_funding' ORDER BY type, name"
    )]


def test_connect_migrates_a_v3_database_adding_trial_funding_and_touching_no_trial(tmp_path):
    """Phase 7's exit criterion: v3 -> v4 is purely additive, exactly as v2 -> v3 was.

    This is *why* the money-weighted return is a side table rather than two columns on ``trials``:
    ``ALTER TABLE trials ADD COLUMN`` would move every recorded row's bytes and this assertion
    would fail. The ladder also carries a v2 fixture all the way to v4 in one open.
    """
    db = tmp_path / "lab.sqlite"
    _v2_db(db)
    store.connect(db).close()          # v2 -> v3 -> v4
    before = _trials_bytes(db)

    conn = store.connect(db)
    fresh = store.connect(tmp_path / "fresh.sqlite")
    try:
        assert store.schema_version(conn) == store.SCHEMA_VERSION
        assert _trials_bytes(db) == before          # no recorded trial moved
        assert conn.execute("SELECT count(*) FROM trial_funding").fetchone()[0] == 0
        assert _funding_schema(conn) == _funding_schema(fresh)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []

        # A trial with no funding row received no deposits -- true of all 128 recorded trials --
        # and that is what funding_of answers, never an error.
        assert store.funding_of(conn, 1) is None

        # The triggers are row-level, so prove they bite on a row that arrived by migration.
        with conn:
            store.insert_funding(conn, [store.FundingRow(
                trial_n=1, mwr=0.0712, spy_tr_mwr=0.0689, deposits_usd=3681.00, deposits_n=12,
                schedule="+5,000,000 IDR on the 25th of each month",
                measured="2026-10-08T00:00:00+00:00",
            )])
        assert store.funding_of(conn, 1)["deposits_n"] == 12
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("UPDATE trial_funding SET mwr = 9")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM trial_funding")
        with pytest.raises(store.LabError, match="already has recorded funding"):
            with conn:
                store.insert_funding(conn, [store.FundingRow(
                    trial_n=1, mwr=0.1, spy_tr_mwr=0.1, deposits_usd=1.0, deposits_n=1,
                    schedule="s", measured="2026-10-08T00:00:00+00:00",
                )])
        assert _trials_bytes(db) == before          # and recording funding still moved no trial
    finally:
        conn.close()
        fresh.close()


def test_a_funded_trial_is_judged_money_weighted_and_an_unfunded_one_is_not(tmp_path):
    """The restated gate (R3). The same recorded row reads two ways depending on whether it was
    fed: by total return when it was not, by the money-weighted return when it was."""
    db = tmp_path / "lab.sqlite"
    _v2_db(db)
    conn = store.connect(db)
    try:
        row = dict(conn.execute("SELECT * FROM trials WHERE n = 1").fetchone())
        row["total_return"], row["spy_tr_return"] = 6.00, 0.40   # "+600%" vs SPY: beats it today
        row["max_drawdown"], row["profit_factor"] = 0.10, 2.0
        assert dev.FAILURE_LABELS[0] not in store.owner_failures(row)

        # ...but the money it was fed earned less than the SPY fed the same money.
        funding = {"mwr": 0.004, "spy_tr_mwr": 0.071}
        assert dev.FAILURE_LABELS[0] in store.owner_failures(row, funding)
    finally:
        conn.close()
```
**Impact:** `dev` and `sqlite3` are already imported by this file (`:46`, `:62`).

---

## Verification

**Build:**
```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild && PYTHONPATH=engine/src python -c "import seer_engine.backtest.dev, seer_engine.lab.store"
```
(this also catches the `metrics` <-> `book_runner` import cycle Step 4 warns about)

**Tests, from the worktree root — `PYTHONPATH` is required or pytest silently tests the main checkout:**
```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild && \
PYTHONPATH=engine/src PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  python -m pytest engine/tests -q -n auto
```
Never pass `-o addopts`. `main` is red for two known reasons (handover section 6); neither is this
phase's. The targeted subset while iterating:
```
PYTHONPATH=engine/src python -m pytest \
  engine/tests/test_backtest_metrics.py engine/tests/test_backtest_benchmark.py \
  engine/tests/test_benchmark.py engine/tests/test_paper_benchmark.py \
  engine/tests/test_backtest_dev.py engine/tests/test_lab_snapshot.py \
  engine/tests/test_lab_gate_policy.py engine/tests/test_lab_test_window.py -q
```

**Manual check — the measurement the owner reads.** This must print `0.00%` for a book that earned
nothing, beside the two numbers the lab records today:
```
PYTHONPATH=engine/src python - <<'PY'
from datetime import date
from seer_engine.backtest.metrics import strategy_metrics
start, end = date(2026, 11, 2), date(2027, 11, 2)
deposits = [(date(2026 + (10 + i) // 12, (10 + i) % 12 + 1, 25), 306.75) for i in range(12)]
paid_in = 613.50 + 306.75 * 12
m = strategy_metrics([(start, 613.50), (end, paid_in)], (), deposits)
print(f"money-weighted {m.mwr:+.2%}   total return {m.total_return:+.1%}   CAGR {m.cagr:+.1%}")
PY
```
Expected: `money-weighted +0.00%   total return +600.0%   CAGR +600.9%`.

**Also confirm nothing moved for the record:** `git diff --stat` must show **no** change to
`lab/lab.sqlite`, `backtest/runner.py`, `backtest/book_runner.py`, `sim/`, `paper/` or `web/`.

**Exit criteria:**
1. `money_weighted_return` equals `cagr_between` to 1e-12 relative on every deposit-free curve, and
   reports 0.00% for a book that earns nothing on the owner's real funding plan.
2. `Metrics.mwr` is `None` for every run that received no deposits, so every recorded `cagr`,
   `mar`, `best_dev_eligible` choice and `finalists` order is bit-for-bit unchanged.
3. `spy_curves` is fed `result.cashflows` in `dev._run`, so both SPY curves receive the identical
   dollars on the identical sessions as the book they benchmark.
4. "beats SPY TR" is money-weighted for a funded trial and the recorded total-return comparison for
   all 128 unfunded ones, defined once in `dev.beats_spy_tr` and read by `lab.store.owner_failures`.
5. Schema v4 exists, `trials` is byte-identical across the migration, and a trial with no
   `trial_funding` row answers `None` from `funding_of` on a v1/v2/v3 read-only connection.
6. The engine suite reports the same failures as `main` and no more.
7. **(Step 10b)** `inspect.signature(dev.run_registry).parameters` contains `"contributions"`, and a
   registry run given a schedule produces a `DevRow` whose `stats.metrics.mwr` is not None — this is
   the exact check `phase-8.md`'s `check_schedule_support()` makes before it loads the research store.
8. **(B2, the rule phases 6 and 7 both honour)** a credited deposit raises **equity as well as
   cash**. On this phase's side that holds by construction: `buy_and_hold` adds the deposit to `cash`
   and re-marks `equity = q(cash + shares * close)` on the same session, so the benchmark's equity
   carries it with no separate step. Pinned by `test_backtest_benchmark.py`: a DCA curve's snapshot
   equity on a deposit session equals the undeposited curve's plus the deposit.
9. **(phase 4's H3)** `grep -n 'bracket_v0' engine/src/seer_engine/backtest/dev.py` returns nothing;
   the three dispatches read `is_bracket(...)`.

---

## Handoffs

- **Phase 8 — writing the funding rows.** `lab/runner.py:266,276,546,556` and `lab/seed.py:122,132`
  build `TrialRow`; this phase deliberately leaves `TrialRow` alone (so `lab/runner.py` is
  untouched and unbroken) and adds `store.insert_funding` for the writer. Phase 8 owns the N sweep,
  which produces the **first funded trials in the lab's history**, so the `insert_funding` call
  belongs there, stamped with the trial's own `run_at` and the schedule's own words. Until then
  `trial_funding` is correctly empty: nothing in the lab has ever been fed.
- **Phase 8 — `config_digest` and the funded/unfunded pair.** `trials` carries
  `UNIQUE(config_digest, window)`. If the contribution schedule does **not** reach
  `lab/runner.config_digest`, a funded and an unfunded run of the same method collide and the
  second insert is refused with "no re-rolls". Phase 8's sweep needs both, so it must settle
  whether the schedule is part of the digest. Flagged, not decided here — `lab/runner.py` is not
  this phase's file.
- **Phase 2 / the web — publishing the money-weighted return.** `_snapshot_trial` (`store.py:1745`)
  is phase 2's function and is **not** touched here, which is also why `TRIAL_KEYS` in
  `test_lab_snapshot.py:50-53` needs no change. Once funded trials exist, `/sera` will want
  `mwr` / `spyTrMwr` beside `cagr` / `spyTrCagr`, with the plain gloss. That is a later phase's
  work, not a gap in this one: there is nothing to publish yet.
- **`lab/real_costs.py:296-298, 387-389`** print "CAGR" and "SPY TR CAGR (same fees)" in a report
  the owner reads. `lab costs` re-runs the dev window with no schedule, so those lines are
  **correct today** and were deliberately left. When a funded comparison is added they need the
  money-weighted line and its one-sentence gloss.
- **`metrics.checklist` / `gate_checks`** keep comparing `total_return` against `spy_return`.
  That is correct and deliberate: their callers (`tuning.gate`, `walkforward.gate_p3b`,
  `b_walkforward.gate_p6a`, `wf_report`, `report`) are the P3b/P6a walk-forward paths, which pass
  no contribution schedule, so their CAGR *is* their money-weighted return and there is nothing to
  restate. `checklist` is also the line-for-line twin of `web/lib/metrics.ts`; changing its
  signature would ripple into the web for no measured benefit. ~~If phase 5 makes contributions
  default-on rather than opt-in, this paragraph becomes false~~ — **checked by the reconciler: phase 5
  defaults `contributions` to `None` everywhere and asserts it, so this paragraph stands and the five
  call sites are untouched.**
- **`lab/remeasure.py`'s `SEED_METRICS`** reproduces six recorded metrics including `cagr`. `mwr`
  is deliberately not among them: there is nothing recorded to reproduce. When phase 8 records the
  first funded trials, `mwr` becomes a seventh candidate for that tuple.
- **`lab/lab.sqlite`** is not touched here. It is v3 and will migrate itself to v4 on its next
  `lab` write; the migration adds an empty table and two triggers and changes no recorded value.
  Whoever first runs a `lab` command that writes should commit the migrated file in that commit.

---

## Rollback

`git revert` this phase's single commit. It restores `SCHEMA_VERSION = "3"`, removes
`trial_funding`'s definition, `FundingRow`, `insert_funding`, `funding_of` and `_v3_to_v4`, drops
`Metrics.mwr`, `money_weighted_return`, `external_cashflows`, `beats_spy_tr` and
`BenchmarkCurve.cashflows`, and returns `buy_and_hold` / `spy_curves` / `strategy_metrics` /
`owner_failures` / `_blocking` to their current signatures.

**Two caveats.**

1. **A database already migrated to v4 is then refused**, because `_migrate` refuses a version it
   does not know (`"lab database schema version '4' is unknown to this code"`). That is the
   designed behaviour and it is loud rather than silent. To undo it:
   `DROP TABLE trial_funding;` then
   `UPDATE meta SET value = '3' WHERE key = 'schema_version';` — safe at any time, because
   `trials` was never altered and the table holds nothing any recorded verdict depends on. This
   phase does not touch `lab/lab.sqlite`, so unless someone has run a `lab` write in between there
   is nothing to undo.
2. **Phases 5, 6 and 7 are one unit (Decision D4): revert all three or none.** Contributions
   without the money-weighted measure is strictly worse than no contributions at all — it is the
   state in which a book that earns nothing reports a CAGR of +600.9%.
