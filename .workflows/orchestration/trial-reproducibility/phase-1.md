# Phase 1: Starting capital is a run input

**Plan set:** `TRIAL_REPRODUCIBILITY_PLAN.md`
**Analysis:** `20261009-192826-T7RQ_code_analyzer.md`
**Satisfies:** R1 — policy (d), "record enough per trial to re-derive": the input that was
missing (starting capital, M2) becomes something a re-run can actually pass
**Depends on:** none
**Difficulty:** EASY
**Package:** `engine/src/seer_engine/backtest` (`dev.py` only)

---

## Goal

`dev.run_candidate` and `dev.run_registry` (and the private `dev._run` both call) take an
`initial_idr: Decimal = INITIAL_IDR` keyword and hand it to `book_runner.run_rules`, which already
accepts it and forwards it to both engines (`run_book`, and `run_backtest` for `DESIGN_V0`). A
caller that passes nothing gets exactly the run it gets today; phase 2 can now re-run a recorded
trial at the capital it was recorded at (20,000,000 IDR for every lump-sum trial before
`d79fc83`, M3) without touching `INITIAL_IDR`.

## Interface Contract

**Deletes:** nothing
**Renames:** nothing
**Creates:** no new symbol. A new keyword-only parameter on three existing functions (below).
`dev.py` newly imports `INITIAL_IDR` from `seer_engine.backtest.runner` (it already imports
`RunResult` from there; `runner` is not `research`, so `test_dev_does_not_import_research` and the
purity glob are unaffected).
**Signature changes** (all keyword-only; placed after `window`, before `contributions`):

```python
def _run(market, spy, dividends, spy_dividends, c, prepared, window, *,
         initial_idr: Decimal = INITIAL_IDR,
         contributions: ContributionSchedule | None = None,
         contribution_fx: Callable[[date], Decimal] | None = None,
) -> tuple[RunResult | BookResult, DevRow]

def run_candidate(market, dividends, spy_dividends, c, *,
                  prepared: Any = None,
                  window: Window = DEV_WINDOW,
                  initial_idr: Decimal = INITIAL_IDR,
                  contributions: ContributionSchedule | None = None,
                  contribution_fx: Callable[[date], Decimal] | None = None,
) -> tuple[RunResult | BookResult, DevRow]

def run_registry(market, dividends, spy_dividends, registry, *,
                 on_result: Callable[[int, RunResult | BookResult, DevRow], None] | None = None,
                 window: Window = DEV_WINDOW,
                 initial_idr: Decimal = INITIAL_IDR,
                 contributions: ContributionSchedule | None = None,
                 contribution_fx: Callable[[date], Decimal] | None = None,
) -> tuple[DevRow, ...]
```

`initial_idr` is IDR (a `Decimal`), the same unit and meaning as `run_rules(initial_idr=...)`
(`book_runner.py:432`). No validation is added in `dev`: `sim.model.initial_cash_usd`
(`sim/model.py:92`) already refuses a non-positive amount.

**Requires (from earlier phases):** nothing.
**Provides (for later phases):** Phase 2 passes a recorded capital by keyword to
`dev.run_registry(..., initial_idr=...)` from `lab/remeasure.py` (dev path:
`plan.initial_idr`, resolved by `remeasure.plan_capital` in `preflight`; seed path: `run_chunk(...,
initial_idr=...)`, resolved per chunk by `plan_capital` after `seed_preflight` refused a mixed set)
and from `lab/real_costs.py` (`measure(..., initial_idr=...)`, which `commands/lab.py:_costs`
resolves with `runner.recorded_capital` — `real_costs` cannot import `runner`), and passes
`INITIAL_IDR` explicitly from `lab/runner.py:run_method` / `run_test`. Every existing caller
(`lab/runner.py:386,748`, `lab/remeasure.py:414,1052`, `lab/real_costs.py:280`,
`lab/name_count.py:353`) keeps compiling and behaving identically without change, because the
keyword is optional and defaults to the constant `run_rules` already defaults to.
**Leaves alone (owned by others):** `backtest/runner.py:INITIAL_IDR` (value unchanged — out of
scope for the whole set); `backtest/book_runner.py` (already takes `initial_idr`); everything under
`engine/src/seer_engine/lab/` and `commands/` (phases 2 and 3); `research.py` (phase 2); docs and
`lab/lab.sqlite` (phase 4).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/dev.py` | modify | module docstring (29-31) drops the stale "20,000,000 IDR" and states the new rule; import `INITIAL_IDR` (56); `initial_idr` keyword on `_run` (482), passed to `run_rules` (516); on `run_candidate` (557) with a docstring paragraph; on `run_registry` (586) with a docstring paragraph; both forward it to `_run` (582, 648) |
| `engine/tests/test_backtest_dev.py` | modify | import `OWNER_MONTHLY` (after 52); seven new tests appended after the last line (793) |

## Implementation Steps

Line numbers are against `e5eda52` (the worktree base); this phase depends on nothing, so the
file is as it is today. Apply the steps top to bottom; each later step's line number shifts by the
lines earlier steps added (the anchor text is given so the edit is unambiguous).

### Step 1: Module docstring — capital is an input, and the stale 20M goes
**File:** `engine/src/seer_engine/backtest/dev.py:29-32`
**Change:** the paragraph about FX still says "the 20,000,000 IDR starting capital", which has
been false since `d79fc83` set `INITIAL_IDR` to 10,000,000. Make it capital-neutral and add one
bold paragraph, in the file's existing `**D9, ...**` style, that states the new keyword and why it
exists.

Replace these lines (the end of the module docstring):

```python
FX before ``FX_START`` (1999-01-04, Frankfurter's first USD/IDR row): a window that starts
earlier converts the 20,000,000 IDR starting capital at the ``FX_START`` rate. FX feeds the
starting cash only, so no decision depends on it.
"""
```

with:

```python
FX before ``FX_START`` (1999-01-04, Frankfurter's first USD/IDR row): a window that starts
earlier converts the IDR starting capital at the ``FX_START`` rate. FX feeds the starting cash
only, so no decision depends on it.

**Starting capital is an input, not a constant.** ``run_candidate`` and ``run_registry`` take
``initial_idr``, defaulting to ``runner.INITIAL_IDR``, and hand it to ``run_rules`` unchanged. A
caller that passes nothing runs at the live constant, byte-for-byte as before the keyword
existed. A caller re-running a *recorded* trial passes the capital that trial was recorded at:
whole-share rounding (and, under ``cost_model="gotrade"``, the per-order fee floor) makes capital
a result-moving input -- a 10,000,000 IDR book and a 20,000,000 IDR book buy different share
counts of the same names, so their curves differ in shape, not only in scale -- and
``INITIAL_IDR`` moved from 20,000,000 to 10,000,000 on 2026-10-08 (``d79fc83``) with nothing in
the lab recording which one a trial ran on.
"""
```

**Impact:** documentation only.

### Step 2: Import the constant
**File:** `engine/src/seer_engine/backtest/dev.py:56`
**Change:**

```python
from seer_engine.backtest.runner import RunResult
```

becomes

```python
from seer_engine.backtest.runner import INITIAL_IDR, RunResult
```

**Impact:** none at runtime. `book_runner` already imports the same name from the same module, so
`dev`'s default and `run_rules`'s default are the same `Decimal` object.

### Step 3: `_run` takes the capital and passes it to `run_rules`
**File:** `engine/src/seer_engine/backtest/dev.py:482-555` (whole function; the only changes are the
`initial_idr` parameter and the `initial_idr=` argument with its comment at the `run_rules` call,
line 516)
**Code:**

```python
def _run(
    market: Market,
    spy: Mapping[date, Any],
    dividends: DividendMap,
    spy_dividends: tuple[Dividend, ...],
    c: Candidate,
    prepared: Any,
    window: Window,
    *,
    initial_idr: Decimal = INITIAL_IDR,
    contributions: ContributionSchedule | None = None,
    contribution_fx: Callable[[date], Decimal] | None = None,
) -> tuple[RunResult | BookResult, DevRow]:
    start, end = candidate_window(market, c, window=window)
    check_dev_session(end, window)
    rate: Decimal = market.usd_idr_on(max(start, FX_START))
    run_market = market
    if contribution_fx is not None and start < FX_START:
        raise ValueError(
            f"contribution_fx needs a USD/IDR rate per session, and this window starts {start}, "
            f"before the first rate on {FX_START}"
        )
    if start < FX_START:
        # No USD/IDR before FX_START: the starting cash converts at the FX_START rate. replace()
        # carries history, membership and fundamentals over, so a long window keeps the panel.
        run_market = replace(market, fx=((start, rate),))
    result = run_rules(
        run_market,
        c.allocator,
        c.params,
        c.rules,
        start,
        end,
        prepared=prepared,
        dividends=dividends if c.rules.engine == "book" else {},
        usd_idr=rate,
        # Passed explicitly even at its default: run_rules's own default is the same
        # runner.INITIAL_IDR object, so a caller that passes nothing gets the run it always got,
        # and a caller that passes a recorded capital gets that capital on both engines (run_book
        # and, for DESIGN_V0, run_backtest). The SPY benchmark below starts from
        # result.initial_cash, so it follows the capital without being told.
        initial_idr=initial_idr,
        contributions=contributions,
        contribution_fx=contribution_fx,
    )
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
    #
    # The field is passed straight through rather than via `metrics.external_cashflows`, which
    # converts it to float for the IRR: `buy_and_hold` requires Decimal amounts and moves real
    # money through `q()`, so rounding the deposits to binary floats and back would make the
    # benchmark pay a different sum from the book it is benchmarking. The two readers of this
    # field are here and `metrics.external_cashflows`; a rename touches both.
    price, total = spy_curves(
        spy,
        start,
        end,
        result.initial_cash,
        spy_dividends,
        cost_model=c.rules.cost_model,
        contributions=result.cashflows,
    )
    row = make_row(
        c,
        start,
        end,
        _funded_stats(result),
        spy_tr=curve_metrics(total),
        spy_price=curve_metrics(price),
        window=window,
    )
    return result, row
```

**Impact:** the bracket path of `run_rules` (`book_runner.py:448-479`) forwards `initial_idr` to
`run_backtest`; the book path (`book_runner.py:480-495`) to `run_book`. Neither validates it
against `usd_idr`, so a non-default capital is legal on both engines. The `spy_curves` call is
unchanged and already reads `result.initial_cash`, so the benchmark opens with the same dollars.

### Step 4: `run_candidate` takes and forwards the capital
**File:** `engine/src/seer_engine/backtest/dev.py:557-583` (whole function)
**Code:**

```python
def run_candidate(
    market: Market,
    dividends: DividendMap,
    spy_dividends: Sequence[Dividend],
    c: Candidate,
    *,
    prepared: Any = None,
    window: Window = DEV_WINDOW,
    initial_idr: Decimal = INITIAL_IDR,
    contributions: ContributionSchedule | None = None,
    contribution_fx: Callable[[date], Decimal] | None = None,
) -> tuple[RunResult | BookResult, DevRow]:
    """Run ``c`` once on ``candidate_window(market, c, window=window)``.

    ``dividends`` (symbol -> ex_date -> amount) reach the book engine only; ``spy_dividends``
    feed the total-return SPY curve. ``prepared`` is ``c.allocator.prepare(market.history)``
    or None. Every input is checked against ``window.end`` first (``DevWindowError``), and
    ``window`` defaults to ``DEV_WINDOW``: pass nothing and this is the D9-guarded dev run it
    has always been.

    ``initial_idr`` is the opening book in IDR, converted to USD once at the window's first
    rate (the ``FX_START`` rate for a window that opens earlier). It defaults to
    ``runner.INITIAL_IDR``; see ``run_registry`` for who passes anything else, and why.
    """
    _check_market(market, window)
    spy_divs = _check_dividends(dividends, spy_dividends, window)
    if not isinstance(c, Candidate):
        raise TypeError(f"expected a Candidate, got {type(c).__name__}")
    return _run(
        market, market.spy(), dividends, spy_divs, c, prepared, window,
        initial_idr=initial_idr, contributions=contributions, contribution_fx=contribution_fx,
    )
```

**Impact:** none for existing callers (keyword-only, optional).

### Step 5: `run_registry` takes and forwards the capital
**File:** `engine/src/seer_engine/backtest/dev.py:586-655` (whole function; changes: the parameter,
the last docstring paragraph, and the `_run` call at 646-649)
**Code:**

```python
def run_registry(
    market: Market,
    dividends: DividendMap,
    spy_dividends: Sequence[Dividend],
    registry: Sequence[Candidate],
    *,
    on_result: Callable[[int, RunResult | BookResult, DevRow], None] | None = None,
    window: Window = DEV_WINDOW,
    initial_idr: Decimal = INITIAL_IDR,
    contributions: ContributionSchedule | None = None,
    contribution_fx: Callable[[date], Decimal] | None = None,
) -> tuple[DevRow, ...]:
    """Every candidate, sequentially, in registry order; one row each, in that order.

    ``prepare_for(allocator, market)`` runs once per allocator id within this call (a strategy's
    id for ``DESIGN_V0`` candidates) and is dropped after the last candidate that uses it: that
    is ``allocator.prepare_market(market)`` for a ``MarketAware`` allocator and
    ``allocator.prepare(market.history)`` for every other. Two different objects sharing an id
    are refused. ``on_result(index, result, row)``, when given, is called after each candidate.
    ``window`` defaults to ``DEV_WINDOW``; ``lab test`` is the only caller that passes another.

    ``contributions`` is the funding schedule every candidate is run on
    (``sim.contributions.ContributionSchedule``), or None -- the default, and a lump-sum book that
    never grows. ``lab.runner.run_method`` and ``run_test`` pass ``OWNER_MONTHLY``, and
    ``lab.name_count`` passes it unless ``--lump``; ``lab.remeasure`` and ``lab.real_costs`` pass
    whatever the trial they are reproducing was recorded on
    (``lab.runner.recorded_contributions``), so a recorded trial re-runs as the measurement it was.
    Every one of the 128 trials recorded before the lab was funded has no ``trial_funding`` row and
    re-runs unfunded, byte-for-byte as it did. When a schedule is given, the book is fed the
    deposits AND ``spy_curves`` receives the same dollars on the same sessions, so "beats SPY TR"
    stays a comparison of two books holding the same money.

    ``initial_idr`` is every candidate's opening book in IDR, defaulting to
    ``runner.INITIAL_IDR`` -- the live capital, which is what a *new* trial runs at, so
    ``lab.runner.run_method``, ``run_test`` and ``lab.name_count`` pass nothing. It is the second
    half of the same rule as ``contributions``: a path that re-runs a recorded trial must pass the
    capital that trial was recorded at, or it reproduces a different measurement. Whole-share
    rounding makes capital result-moving, and ``INITIAL_IDR`` moved from 20,000,000 to 10,000,000
    on 2026-10-08 (``d79fc83``): measured on 2026-10-09, ``lab remeasure`` of M0007, M0011 and
    all 54 P7a seed trials diverges at the live 10,000,000 and reproduces every one exactly at
    20,000,000. The capital reaches both engines through ``run_rules`` and, via
    ``result.initial_cash``, the SPY benchmark, so "beats SPY TR" still compares two books that
    opened with the same money.
    """
    _check_market(market, window)
    spy_divs = _check_dividends(dividends, spy_dividends, window)
    if isinstance(registry, (str, bytes)) or not isinstance(registry, Sequence):
        raise TypeError(f"registry must be a sequence of Candidate, got {type(registry).__name__}")
    candidates = tuple(registry)
    if len(candidates) > MAX_CANDIDATES:
        raise ValueError(f"the registry holds {len(candidates)} candidates, the cap is {MAX_CANDIDATES} (D6)")
    owners: dict[str, object] = {}
    last_use: dict[str, int] = {}
    ids: set[str] = set()
    for i, c in enumerate(candidates):
        if not isinstance(c, Candidate):
            raise TypeError(f"registry[{i}] is a {type(c).__name__}, not a Candidate")
        if c.id in ids:
            raise ValueError(f"candidate id {c.id} appears twice")
        ids.add(c.id)
        key = c.allocator.id
        owner = owners.get(key)
        if owner is not None and owner is not c.allocator:
            raise ValueError(f"two different allocator objects share the id {key!r}")
        owners[key] = c.allocator
        last_use[key] = i
    spy = market.spy()
    cache: dict[str, Any] = {}
    rows: list[DevRow] = []
    for i, c in enumerate(candidates):
        key = c.allocator.id
        if key not in cache:
            cache[key] = prepare_for(c.allocator, market)
        result, row = _run(
            market, spy, dividends, spy_divs, c, cache[key], window,
            initial_idr=initial_idr, contributions=contributions, contribution_fx=contribution_fx,
        )
        if last_use[key] == i:
            del cache[key]
        rows.append(row)
        if on_result is not None:
            on_result(i, result, row)
    return tuple(rows)
```

**Impact:** none for existing callers. The docstring names `lab.remeasure` / `lab.real_costs` as
the paths that *must* pass a recorded capital; they start doing so in phase 2. Until phase 2
lands the docstring states the rule ahead of its callers — that is deliberate (the rule lives
beside the parameter), and the sentence does not claim they already pass it.

### Step 6: Test import
**File:** `engine/tests/test_backtest_dev.py:52`
**Change:** add one import line directly after

```python
from seer_engine.sim import Pick, initial_cash_usd, q
```

so it reads

```python
from seer_engine.sim import Pick, initial_cash_usd, q
from seer_engine.sim.contributions import OWNER_MONTHLY
```

### Step 7: Tests
**File:** `engine/tests/test_backtest_dev.py:793` (append after the last line,
`test_the_drawdown_label_follows_the_bar_and_keeps_its_prefix`)
**Code:**

```python


# --------------------------------------------------------------------------- starting capital

RECORDED_IDR = Decimal("20000000")  # the capital every lump-sum trial before d79fc83 ran at


def test_starting_capital_defaults_to_the_engine_constant():
    """Passing nothing and passing ``INITIAL_IDR`` are the same run, on both engines."""
    market = short_market()
    registry, _, _, _ = short_registry()
    for c in registry:
        assert run_candidate(market, DIVS, SPY_DIVS, c) == run_candidate(
            market, DIVS, SPY_DIVS, c, initial_idr=INITIAL_IDR
        )
    assert run_registry(market, DIVS, SPY_DIVS, registry) == run_registry(
        market, DIVS, SPY_DIVS, registry, initial_idr=INITIAL_IDR
    )


def test_starting_capital_reaches_run_rules(monkeypatch):
    """``_run`` hands ``run_rules`` the capital it was given -- and the constant when given none."""
    seen: list[Decimal] = []
    real_run_rules = dev_module.run_rules

    def spy_run_rules(*args: Any, **kwargs: Any) -> Any:
        seen.append(kwargs["initial_idr"])
        return real_run_rules(*args, **kwargs)

    monkeypatch.setattr(dev_module, "run_rules", spy_run_rules)
    market = short_market()
    registry, _, _, _ = short_registry()
    run_candidate(market, DIVS, SPY_DIVS, registry[0])
    run_candidate(market, DIVS, SPY_DIVS, registry[0], initial_idr=RECORDED_IDR)
    run_registry(market, DIVS, SPY_DIVS, registry, initial_idr=RECORDED_IDR)
    assert seen == [INITIAL_IDR, RECORDED_IDR] + [RECORDED_IDR] * len(registry)


def test_a_book_run_at_another_capital_opens_with_that_cash_and_so_does_spy():
    market = short_market()
    c = cand("F1-FLIP-D", allocator=HoldOne("FLIP", "SPY", flip=True), rules=DAILY_SWITCH)
    live, live_row = run_candidate(market, DIVS, SPY_DIVS, c)
    result, row = run_candidate(market, DIVS, SPY_DIVS, c, initial_idr=RECORDED_IDR)
    assert isinstance(result, BookResult)
    assert result.initial_cash == initial_cash_usd(RECORDED_IDR, Decimal("12500"))
    assert result.initial_cash == 2 * live.initial_cash
    assert (row.start, row.end) == (live_row.start, live_row.end)
    assert row.stats == run_stats(result)
    price, total = spy_curves(market.spy(), row.start, row.end, result.initial_cash, SPY_DIVS)
    assert row.spy_price == curve_metrics(price)
    assert row.spy_tr == curve_metrics(total)
    # Whole shares: doubling the cash does not double every position, so the curve's shape moves.
    # This is the property that makes a recorded trial irreproducible at the wrong capital.
    assert row.stats.metrics.total_return != live_row.stats.metrics.total_return


def test_a_design_v0_run_at_another_capital_matches_run_backtest_at_that_capital():
    market = short_market()
    strategy = DipPicks()
    c = cand("REF-DIP-V0", "REF", allocator=strategy, rules=DESIGN_V0)
    live, live_row = run_candidate(market, DIVS, SPY_DIVS, c)
    result, row = run_candidate(market, DIVS, SPY_DIVS, c, initial_idr=RECORDED_IDR)
    assert isinstance(result, RunResult)
    assert result == run_backtest(market, strategy, None, row.start, row.end, initial_idr=RECORDED_IDR)
    assert result.initial_cash == initial_cash_usd(RECORDED_IDR, Decimal("12500"))
    assert row.stats.metrics.total_return != live_row.stats.metrics.total_return


def test_a_window_before_fx_start_converts_another_capital_at_the_fx_start_rate():
    market = long_market()
    book, _ = run_candidate(market, {}, (), cand("F1-LONG", allocator=HoldOne("LONG", "SPY", lookback=1)),
                            initial_idr=RECORDED_IDR)
    assert isinstance(book, BookResult)
    assert (book.usd_idr, book.initial_cash) == (Decimal("8002"), initial_cash_usd(RECORDED_IDR, Decimal("8002")))


def test_a_registry_at_another_capital_equals_single_runs_at_that_capital():
    market = short_market()
    registry, _, _, _ = short_registry()
    rows = run_registry(market, DIVS, SPY_DIVS, registry, initial_idr=RECORDED_IDR)
    assert rows == tuple(
        run_candidate(market, DIVS, SPY_DIVS, c, initial_idr=RECORDED_IDR)[1] for c in registry
    )
    assert rows != run_registry(market, DIVS, SPY_DIVS, registry)


def test_a_funded_run_at_another_capital_still_feeds_spy_the_same_deposits():
    market = short_market()
    c = cand("F1-FLIP-D", allocator=HoldOne("FLIP", "SPY", flip=True), rules=DAILY_SWITCH)
    result, row = run_candidate(market, DIVS, SPY_DIVS, c, initial_idr=RECORDED_IDR, contributions=OWNER_MONTHLY)
    assert isinstance(result, BookResult)
    assert result.initial_cash == initial_cash_usd(RECORDED_IDR, Decimal("12500"))
    assert result.cashflows  # the deposits landed on top of the larger opening book
    price, total = spy_curves(market.spy(), row.start, row.end, result.initial_cash, SPY_DIVS,
                              contributions=result.cashflows)
    assert row.spy_tr == curve_metrics(total)
```

**Impact:** seven new tests. Every name they use is already imported by the test module
(`dev_module`, `Any`, `Decimal`, `BookResult`, `RunResult`, `run_backtest`, `run_stats`,
`spy_curves`, `curve_metrics`, `initial_cash_usd`, `INITIAL_IDR`, `DAILY_SWITCH`, `DESIGN_V0`,
`short_market`, `long_market`, `short_registry`, `cand`, `HoldOne`, `DipPicks`, `DIVS`,
`SPY_DIVS`) except `OWNER_MONTHLY` (Step 6).

**Pre-validated by the planner** on a scratch copy of the engine with Steps 1-7 applied
(2026-10-09): `tests/test_backtest_dev.py` 66 passed (59 existing + 7 new); the same seven new
tests against the *unmodified* `dev.py` fail 7 of 7 (TypeError on the unknown keyword), so they
pin the change. The whole-share premise was checked directly through `run_rules` on
`short_market()`: total return at 10M vs 20M differs on `daily-switch` (0.7155 vs 0.6854),
`monthly-hold` (1.0154 vs 1.0179) and `design-v0` (1.0655 vs 1.0764). Full suite on the scratch
copy: 3247 passed (baseline 3242 + 7 − 2 path-only failures caused by the scratch copy's
symlinked `web/`/`lab/`, `test_lab_snapshot::test_snapshot_path_is_beside_the_databases_repo` and
`test_lab_prereg::test_lab_promote_command_exits_2_when_the_lab_refuses` — both pass in the real
worktree, where nothing is symlinked).

## Verification

Run from the worktree; the worktree has no venv, and without `PYTHONPATH` pytest tests the main
checkout's source.

**Build:**
```bash
cd /home/miftah/.worktrees/seer/trial-reproducibility/engine && PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -c "import inspect, seer_engine.backtest.dev as d; [print(f.__name__, inspect.signature(f).parameters['initial_idr']) for f in (d._run, d.run_candidate, d.run_registry)]"
```
Expected: three lines, each `<name> initial_idr: 'Decimal' = Decimal('10000000')` (string
annotation because the module uses `from __future__ import annotations`).

**Tests (focused):**
```bash
cd /home/miftah/.worktrees/seer/trial-reproducibility/engine && PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -m pytest -q tests/test_backtest_dev.py tests/test_strategy_purity.py tests/test_lab_runner.py tests/test_lab_remeasure.py tests/test_lab_remeasure_seed.py tests/test_lab_name_count.py
```
Expected: no failures; `test_backtest_dev.py` reports 66 (was 59).

**Tests (full suite, the invariant):**
```bash
cd /home/miftah/.worktrees/seer/trial-reproducibility/engine && PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -m pytest -q
```
Expected: 0 failed. The passed count is this phase's baseline + 7; measure the baseline on the
same machine before editing (for reference, `e5eda52` read 3242 passed, 411 skipped on the GPD
without `PG_TEST_URL`). Pass and skip counts depend on the machine, so the gate is "no failure",
not a number.

**Manual check:** `git diff --stat` touches exactly the two files. `grep -n "20,000,000 IDR
starting" engine/src/seer_engine/backtest/dev.py` returns nothing.

**Exit criteria:** the three functions accept `initial_idr`; a call without it is equal (`==`) to
a call with `initial_idr=INITIAL_IDR` on both engines; `initial_idr=Decimal("20000000")` reaches
`run_rules` (monkeypatched spy) and changes a whole-share run's total return; the full engine
suite passes. No file outside `backtest/dev.py` and its test module changed; `INITIAL_IDR` is
still `Decimal("10000000")`.

## Handoffs

- **Phase 2 (R1, R4):** pass `initial_idr=recorded_capital(conn, n)` to `dev.run_registry` in
  `lab/remeasure.py` (`measure`, ~414; `run_chunk`, ~1052) and `lab/real_costs.py` (~280). A
  registry re-run spans several variants, each a trial; `run_registry` takes **one** capital for
  the whole call, so phase 2 must either assert every trial in the chunk shares one recorded
  capital (true today: within a method all trials are either lump/20M or funded/10M, M3) and
  refuse otherwise, or group the re-run by capital. This phase deliberately does not add a
  per-candidate capital — nothing measured needs it. **Reconciled:** phase 2 refuses, from the
  database alone and before any store loads — `remeasure.plan_capital` in `preflight` (dev path)
  and in `seed_preflight` (seed path); `lab costs` re-runs one trial, resolved by
  `runner.recorded_capital` in `_costs` before the store loads.
- **Phase 2:** `lab/runner.run_method` / `run_test` record the capital they ran at. They do not
  pass `initial_idr` today and need not: the run's capital is `INITIAL_IDR`, which is what the
  provenance row should say. If phase 2 prefers to pass it explicitly (so the recorded value and
  the run value come from one variable), the keyword now exists.
- **Not in any phase (noticed, left alone):** the report generators
  `backtest/report.py:232`, `b_report.py:474`, `dev_report.py:452`, `wf_report.py:452` print
  `INITIAL_IDR` as "the" starting capital. They describe live runs and stay true; if a report is
  ever generated from a re-run at a recorded capital it would need the capital passed through.
  Not a requirement of this plan set.

## Rollback

`git revert` the phase's commit. It touches only `backtest/dev.py` and
`tests/test_backtest_dev.py`; no database, schema or committed artifact changes. Phase 2's
re-run paths depend on the keyword, so reverting phase 1 after phase 2 has landed requires
reverting phase 2 first.
