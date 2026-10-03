# Phase 3: Walk-forward engine

**Plan set:** `STRATEGY_A_REWORK_PLAN.md`
**Analysis:** `20261003-160830-R4W9_code_analyzer.md`
**Satisfies:** R3, R4, R5 — the anchored yearly walk-forward (folds, per-fold tuning that sees only its window, one chained portfolio, brackets that survive 31 Dec, fallbacks), determinism, purity
**Depends on:** Phase 1 (`strategies/a2.py`), Phase 2 (`ParamsSchedule`, `metrics_through`, `select(fallback=)`)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/backtest`

---

## Goal

After this phase, `seer_engine.backtest.walkforward` turns a `Market` plus Strategy A2 into the whole P3b
procedure as pure functions. It defines the folds, lists the 324 combinations, tunes every fold with one
run per combination, selects per fold (combined, or with the variant fixed), and chains the selections
into **one** `run_backtest` whose params are a `ParamsSchedule`. It also computes diagnostics, the
"seen before" window metrics and the P3b gate verdict. Phase 4 renders these results and phase 5 runs them.
A new test file proves every R3 rule on synthetic data.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:** everything in `engine/src/seer_engine/backtest/walkforward.py` (new). These match the plan
index contract exactly:
- `FIRST_TRADE_YEAR = 2018`, `SEEN_BEFORE_START = tuning.OOS_START`, `COMBINED = "walk-forward"`
- `@dataclass(frozen=True) Fold(year, tune_start, tune_end, trade_start, trade_end)`. Plain, with no `__post_init__`. Validation lives in `_check_folds`, which `tune`/`schedule`/`walk_forward` call.
- `folds(is_start, first_year, end) -> tuple[Fold, ...]`
- `combinations() -> tuple[A2Params, ...]`
- `tune(market, strategy, prepared, combos, folds) -> tuple[tuple[GridRow, ...], ...]`
- `select_fold(rows, variant=None) -> Selection`
- `schedule(folds, selections) -> ParamsSchedule`
- `@dataclass(frozen=True) WalkForward(name, folds, selections, run)`
- `walk_forward(market, strategy, prepared, folds, fold_rows, variant=None) -> WalkForward`
- `@dataclass(frozen=True) Diagnostics(trades, pnl_by_reason, pnl_by_year, small_trades, gross_pnl_usd, costs_usd, cost_drag)`
- `diagnostics(r) -> Diagnostics`
- `window_metrics(r, start) -> Metrics`, `curve_window_metrics(c, start) -> Metrics`
- `gate_p3b(wf, spy_tr, start, end) -> tuning.Verdict`
- Private: `_day`, `_session`, `_variant`, `_check_folds`, `_window_start`, `_join`, `_GATE_NAMES`, `_ZERO`. `_join`/`_GATE_NAMES` are local copies of `tuning`'s private names, so nothing imports a private name from another module.
- `engine/tests/test_backtest_walkforward.py` (new, 39 tests).

**Signature changes:** none.
**Requires (from earlier phases):**
- Phase 1: `seer_engine.strategies.a2` exports `A2Params` (frozen, hashable, `==` by value; fields `variant` + A's five; `from_a(variant, AParams)`, `a_params()`), `VARIANTS` (the four names in order), `A2_DESIGN_PARAMS == A2Params()`, `STRATEGY_A2` (`prepare`, `picks_prepared`, `picks`; it reads SPY from `history`, and SPY is never a member). `A2Params(variant=v)` is v with the design values.
- Phase 2: `runner.ParamsSchedule(segments=...)` (frozen dataclass, `==` by value) and `run_backtest` accepting one (picks for session S use `params.at(S)`; `RunResult.params` is the schedule object; `ValueError` if `start < segments[0][0]`). `metrics.metrics_through(r, end)` (a session in `[r.start, r.end]`; the prefix property). `tuning.select(rows, *, fallback=...)` with unchanged rule, tie-breaks and reason strings.
- `tests/test_backtest_runner.py` still exports `START` and `run_scenario()` with the hand-checked FixedPicks scenario unchanged (phase 2 only adds tests to that file).

**Leaves alone (owned by others):** `runner.py`, `metrics.py`, `tuning.py` (Phase 2); `strategies/*` and `tests/stratkit.py` (Phase 1); `wf_report.py` (Phase 4); `io.py`, `commands/*` (Phase 5); docs and the frozen constant (Phase 6). `test_strategy_purity.py` is not edited, because its glob already covers the new module.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/walkforward.py` | create (line 1) | the whole walk-forward engine, pure |
| `engine/tests/test_backtest_walkforward.py` | create (line 1) | 39 tests on synthetic data |

## Design notes (read before implementing)

- **Tuning cost (D3).** `tune` makes one `run_backtest` per combo over `[folds[0].tune_start, folds[-1].tune_end]`
  and slices each fold with `metrics_through`. A test checks every row `==` a fresh
  `run_metrics(run_backtest(..., f.tune_start, f.tune_end))`, which is the prefix property end to end.
- **Per-combo timing (phase 5).** `tune` is pure and cannot time itself. `tune(market, s, prep, (combo,), folds)` is
  valid, so phase 5 can call it once per combo, time each call, and merge the results in combo order:
  `tuple(tuple(r for part in parts for r in part[k]) for k in range(len(folds)))`. This gives exactly what one
  `tune(..., combos, ...)` call returns.
- **Schedule key (D6).** `schedule` keys fold Y's params by `trade_start(Y)`. The first session of Y
  picks on `data_date = tune_end(Y)` with fold Y's params. The bracket test checks this call by call.
- **Fallbacks (D7).** Combined: `A2_DESIGN_PARAMS`. Per variant: `A2Params(variant=v)`. `select_fold` filters
  rows by `params.variant` before `tuning.select`, so the reason string counts "of 81" for a variant.
  "Grid run #k" is the 1-based position in the rows passed in: the combined index for the combined
  selection, the grid index for a variant.
- **Diagnostics (D12).** Sums are `Decimal`, seeded with `Decimal("0.0000")` so a zero prints as `0.0000`.
  Gross = Σ(exit − fill)×shares, which is exact. Costs = Σ(gross_i − pnl_i). `cost_drag = float(costs)/float(gross)`
  when gross > 0, else `None`. P/L by year uses `exit_date.year`. Forced closes count under `time`, as in
  `exit_reason_counts`.
- **Windows (D13).** `window_metrics(r, start)` keeps the snapshots dated ≥ `prev_session(start)` and the
  orders of exit events with `session_date ≥ start`, in event order. It is the mirror image of
  `metrics_through`, and `window_metrics(r, r.start) == run_metrics(r)`. `curve_window_metrics` slices a
  `BenchmarkCurve` the same way, and `curve_window_metrics(c, first session) == curve_metrics(c)`.
- **Purity (R5).** The module imports no `logging`/`time`/`random`, and calls no `print`/`open`/`.now`/`.today`.
  It imports `seer_engine.dates` (as `runner` already does), `backtest.{tuning,benchmark,market,metrics,runner}`
  and `strategies.{a2,base}`, none of which loads psycopg.
- **Determinism (R4).** It is sequential, has no set iteration in an output path (`sorted(year_n)` for years),
  and all containers are tuples.

## Implementation Steps

### Step 1: Create the walk-forward module
**File:** `engine/src/seer_engine/backtest/walkforward.py:1` (new)
**Change:** the complete module below.
**Code:**
```python
"""Anchored yearly walk-forward for Strategy A2 (roadmap P3b, handover §3 "Walk-forward folds").

Pure: no database, files, clock, logging or randomness (tests/test_strategy_purity.py globs this
module). ``commands/backtest_wf.py`` times and logs around these calls.

The procedure, fixed before any result was seen:

- ``folds``: for each trade year Y from ``first_year`` to the data end's year, tune on
  ``[is_start, prev_session(first session of Y)]`` and trade ``[first session of Y,
  min(last session of Y, end)]``. Anchored: every tuning window starts at ``is_start``.
- ``combinations``: 4 variants x 81 grid sets = 324, variant outer, grid inner. This order is the
  selection's last tie-break ("variant -> grid").
- ``tune``: ONE ``run_backtest`` per combination over ``[is_start, last tune_end]``; fold k's row is
  ``metrics_through(run, folds[k].tune_end)``. The runner is causal, so that equals a fresh run
  ending at ``tune_end`` (the prefix property), and a fold's rows read nothing after its own
  ``tune_end``. Sequential, in ``combos`` order (Decision D3).
- ``select_fold``: ``tuning.select`` unchanged, over every combination (fallback: V0 with the design
  values) or over one variant's rows (fallback: that variant with the design values) (Decision D7).
- ``walk_forward``: one ``run_backtest`` from the first fold's trade start to the last fold's trade
  end with a ``ParamsSchedule`` that switches to fold Y's selection at Y's first session (Decision
  D6). One portfolio: cash, positions and pending orders carry across 31 December, and an order
  keeps the bracket it was placed with (the simulator never rewrites one).
- ``diagnostics``, ``window_metrics``, ``curve_window_metrics`` and ``gate_p3b`` read finished runs
  only. Nothing they compute reaches ``select_fold`` (Decision D12).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from seer_engine import dates
from seer_engine.backtest import tuning
from seer_engine.backtest.benchmark import BenchmarkCurve
from seer_engine.backtest.market import Market
from seer_engine.backtest.metrics import (
    EXIT_REASONS,
    Metrics,
    avg_days_held,
    checklist,
    exit_reason_counts,
    fmt_signed_pct,
    metrics_through,
    strategy_metrics,
)
from seer_engine.backtest.runner import ParamsSchedule, RunResult, run_backtest
from seer_engine.backtest.tuning import GridRow, Selection, Verdict
from seer_engine.strategies.a2 import A2_DESIGN_PARAMS, VARIANTS, A2Params
from seer_engine.strategies.base import Strategy

FIRST_TRADE_YEAR = 2018  # the first traded year; fold 2018 tunes on 2015-10-19..2017-12-29
SEEN_BEFORE_START = tuning.OOS_START  # 2022-01-03: the burned P3 out-of-sample start (Decision D13)
COMBINED = "walk-forward"  # name of the curve whose variant is chosen per fold

_ZERO = Decimal("0.0000")
_GATE_NAMES = ("beating total-return SPY", "profit factor ≥ 1.3", "max drawdown ≤ 15%")


@dataclass(frozen=True)
class Fold:
    """One walk-forward fold: tune on ``[tune_start, tune_end]``, trade ``[trade_start, trade_end]``."""

    year: int
    tune_start: date  # is_start (anchored)
    tune_end: date  # prev_session(trade_start)
    trade_start: date  # first NYSE session of ``year``
    trade_end: date  # min(last NYSE session of ``year``, end)


@dataclass(frozen=True)
class WalkForward:
    """One walk-forward curve: per-fold selections chained into one run."""

    name: str  # COMBINED or a VARIANTS entry
    folds: tuple[Fold, ...]
    selections: tuple[Selection, ...]  # one per fold, folds order
    run: RunResult  # params is the ParamsSchedule built from ``selections``


@dataclass(frozen=True)
class Diagnostics:
    """Explains a run's result. Never read by any selection."""

    trades: int
    pnl_by_reason: tuple[tuple[str, int, Decimal], ...]  # (reason, trades, Σ pnl_usd), EXIT_REASONS order, zeros kept
    pnl_by_year: tuple[tuple[int, int, Decimal], ...]  # (exit year, trades, Σ pnl_usd), ascending, years with trades only
    small_trades: int  # closed trades with shares < 3
    gross_pnl_usd: Decimal  # Σ (exit_price − fill_price) × shares
    costs_usd: Decimal  # Σ (gross_i − pnl_usd_i): both 0.1% sides
    cost_drag: float | None  # costs / gross when gross > 0, else None


# --------------------------------------------------------------------------- validation


def _day(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    return d


def _session(name: str, d: object) -> date:
    _day(name, d)
    if not dates.is_session(d):
        raise ValueError(f"{name} {d} is not an NYSE session")
    return d


def _variant(variant: object) -> str:
    if not isinstance(variant, str):
        raise TypeError(f"variant must be a str, got {type(variant).__name__}")
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}, expected one of {VARIANTS}")
    return variant


def _check_folds(folds: Sequence[Fold]) -> tuple[Fold, ...]:
    """``folds`` as a tuple: non-empty, well formed, anchored and contiguous, else ValueError."""
    fs = tuple(folds)
    if not fs:
        raise ValueError("at least one fold is needed")
    for f in fs:
        if not isinstance(f, Fold):
            raise TypeError(f"folds must hold Fold values, got {type(f).__name__}")
        if not (f.tune_start <= f.tune_end < f.trade_start <= f.trade_end):
            raise ValueError(f"fold {f.year} windows are out of order: {f}")
        if f.tune_end != dates.prev_session(f.trade_start):
            raise ValueError(f"fold {f.year}: tune_end {f.tune_end} is not the session before {f.trade_start}")
    for a, b in zip(fs, fs[1:]):
        if b.tune_start != a.tune_start:
            raise ValueError(f"folds are anchored: fold {b.year} tunes from {b.tune_start}, not {a.tune_start}")
        if b.trade_start != dates.next_session(a.trade_end):
            raise ValueError(f"fold {b.year} does not start right after fold {a.year} ends ({a.trade_end})")
    return fs


# --------------------------------------------------------------------------- folds and combinations


def folds(is_start: date, first_year: int, end: date) -> tuple[Fold, ...]:
    """One fold per year ``first_year..end.year`` whose first session is on or before ``end``.

    Raises TypeError on a non-date/non-int argument, and ValueError when ``is_start`` or ``end``
    is not an NYSE session, when no fold results, or when the first fold's tuning window would
    end before ``is_start``.
    """
    _session("is_start", is_start)
    _session("end", end)
    if isinstance(first_year, bool) or not isinstance(first_year, int):
        raise TypeError(f"first_year must be an int, got {type(first_year).__name__}")
    out: list[Fold] = []
    for year in range(first_year, end.year + 1):
        trade_start = dates.next_session(date(year - 1, 12, 31))
        if trade_start > end:
            break
        last = dates.prev_session(date(year + 1, 1, 1))
        out.append(
            Fold(
                year=year,
                tune_start=is_start,
                tune_end=dates.prev_session(trade_start),
                trade_start=trade_start,
                trade_end=min(last, end),
            )
        )
    if not out:
        raise ValueError(f"no trade year from {first_year} has a session on or before {end}")
    if out[0].tune_end < is_start:
        raise ValueError(
            f"fold {out[0].year} would tune on {is_start}..{out[0].tune_end}: the window ends before it starts"
        )
    return tuple(out)


def combinations() -> tuple[A2Params, ...]:
    """The 324 combinations: every variant (``VARIANTS`` order) x the 81-set P3 grid (grid order).

    ``A2_DESIGN_PARAMS`` is entry 40 (variant ``control``, grid entry 40).
    """
    return tuple(A2Params.from_a(variant, p) for variant in VARIANTS for p in tuning.grid())


# --------------------------------------------------------------------------- tuning and selection


def tune(
    market: Market,
    strategy: Strategy,
    prepared: Any,
    combos: Sequence[Any],
    folds: Sequence[Fold],
) -> tuple[tuple[GridRow, ...], ...]:
    """Every fold's tuning-window rows: ``result[k][j] = GridRow(combos[j], metrics through folds[k].tune_end)``.

    One ``run_backtest`` per combination on ``[folds[0].tune_start, folds[-1].tune_end]``, sliced per
    fold with ``metrics_through``. Sequential, in ``combos`` order, so the rows come back in a fixed
    order. ``prepared`` is ``strategy.prepare(market.history)`` or None.
    """
    fs = _check_folds(folds)
    cs = tuple(combos)
    start, end = fs[0].tune_start, fs[-1].tune_end
    per_fold: list[list[GridRow]] = [[] for _ in fs]
    for combo in cs:
        run = run_backtest(market, strategy, combo, start, end, prepared=prepared)
        for k, f in enumerate(fs):
            per_fold[k].append(GridRow(params=combo, metrics=metrics_through(run, f.tune_end)))
    return tuple(tuple(rows) for rows in per_fold)


def select_fold(rows: Sequence[GridRow], variant: str | None = None) -> Selection:
    """P3's selection rule on one fold's rows.

    ``variant`` None: over every row, falling back to ``A2_DESIGN_PARAMS`` (V0, design values).
    ``variant`` v: over the rows of variant v only, falling back to ``A2Params(variant=v)``.
    """
    rs = tuple(rows)
    for r in rs:
        if not isinstance(r, GridRow) or not isinstance(r.params, A2Params):
            raise TypeError("select_fold takes GridRows whose params are A2Params")
    if variant is None:
        return tuning.select(rs, fallback=A2_DESIGN_PARAMS)
    v = _variant(variant)
    return tuning.select([r for r in rs if r.params.variant == v], fallback=A2Params(variant=v))


def schedule(folds: Sequence[Fold], selections: Sequence[Selection]) -> ParamsSchedule:
    """The params schedule: fold k's selection from fold k's first traded session on."""
    fs = _check_folds(folds)
    sel = tuple(selections)
    if len(sel) != len(fs):
        raise ValueError(f"{len(fs)} folds but {len(sel)} selections")
    return ParamsSchedule(segments=tuple((f.trade_start, s.params) for f, s in zip(fs, sel)))


def walk_forward(
    market: Market,
    strategy: Strategy,
    prepared: Any,
    folds: Sequence[Fold],
    fold_rows: Sequence[Sequence[GridRow]],
    variant: str | None = None,
) -> WalkForward:
    """Select per fold from ``fold_rows`` (``tune``'s output), then trade every fold as ONE run.

    ``variant`` None gives the combined curve (named ``COMBINED``); a variant name gives that
    variant's own curve (variant fixed, grid tuned per fold).
    """
    fs = _check_folds(folds)
    rows = tuple(tuple(r) for r in fold_rows)
    if len(rows) != len(fs):
        raise ValueError(f"{len(fs)} folds but {len(rows)} sets of fold rows")
    if variant is not None:
        _variant(variant)
    selections = tuple(select_fold(r, variant) for r in rows)
    run = run_backtest(
        market, strategy, schedule(fs, selections), fs[0].trade_start, fs[-1].trade_end, prepared=prepared
    )
    return WalkForward(name=COMBINED if variant is None else variant, folds=fs, selections=selections, run=run)


# --------------------------------------------------------------------------- reading finished runs


def diagnostics(r: RunResult) -> Diagnostics:
    """P/L by exit reason and exit year, small trades, gross P/L, costs and cost drag of ``r.closed``."""
    if not isinstance(r, RunResult):
        raise TypeError(f"r must be a RunResult, got {type(r).__name__}")
    reason_n = {reason: 0 for reason in EXIT_REASONS}
    reason_pnl = {reason: _ZERO for reason in EXIT_REASONS}
    year_n: dict[int, int] = {}
    year_pnl: dict[int, Decimal] = {}
    small = 0
    gross = _ZERO
    costs = _ZERO
    for o in r.closed:
        if o.exit_reason not in reason_n:
            raise ValueError(f"order {o.symbol} has exit_reason {o.exit_reason!r}, not one of {EXIT_REASONS}")
        if o.fill_price is None or o.exit_price is None or o.exit_date is None or o.pnl_usd is None:
            raise ValueError(f"order {o.symbol} is not a closed, filled order")
        g = (o.exit_price - o.fill_price) * o.shares
        reason_n[o.exit_reason] += 1
        reason_pnl[o.exit_reason] += o.pnl_usd
        y = o.exit_date.year
        year_n[y] = year_n.get(y, 0) + 1
        year_pnl[y] = year_pnl.get(y, _ZERO) + o.pnl_usd
        if o.shares < 3:
            small += 1
        gross += g
        costs += g - o.pnl_usd
    return Diagnostics(
        trades=len(r.closed),
        pnl_by_reason=tuple((reason, reason_n[reason], reason_pnl[reason]) for reason in EXIT_REASONS),
        pnl_by_year=tuple((y, year_n[y], year_pnl[y]) for y in sorted(year_n)),
        small_trades=small,
        gross_pnl_usd=gross,
        costs_usd=costs,
        cost_drag=float(costs) / float(gross) if gross > 0 else None,
    )


def _window_start(start: object, first: date, last: date) -> date:
    _session("start", start)
    if not first <= start <= last:
        raise ValueError(f"start {start} is outside the curve's sessions {first}..{last}")
    return start


def window_metrics(r: RunResult, start: date) -> Metrics:
    """``r``'s metrics from ``start`` on: the curve from ``prev_session(start)`` (its close is the
    base), and the trades whose exit event is on or after ``start``.

    ``start`` must be a session in ``[r.start, r.end]``. ``window_metrics(r, r.start) == run_metrics(r)``.
    """
    if not isinstance(r, RunResult):
        raise TypeError(f"r must be a RunResult, got {type(r).__name__}")
    _window_start(start, r.start, r.end)
    cut = dates.prev_session(start)
    snaps = [(s.date, float(s.equity_usd)) for s in r.snapshots if s.date >= cut]
    closed = [e.order for e in r.events if e.kind == "exit" and e.session_date >= start]
    pnls = [float(o.pnl_usd) for o in closed if o.pnl_usd is not None]
    base = strategy_metrics(snaps, pnls)
    return replace(base, avg_days_held=avg_days_held(closed), exit_reasons=exit_reason_counts(closed))


def curve_window_metrics(c: BenchmarkCurve, start: date) -> Metrics:
    """A SPY curve's metrics from ``start`` on, sliced exactly like ``window_metrics``.

    ``start`` must be a session of the curve (not its leading base snapshot).
    ``curve_window_metrics(c, first session) == curve_metrics(c)``.
    """
    if not isinstance(c, BenchmarkCurve):
        raise TypeError(f"c must be a BenchmarkCurve, got {type(c).__name__}")
    if len(c.snapshots) < 2:
        raise ValueError("the curve has no session")
    _window_start(start, c.snapshots[1].date, c.snapshots[-1].date)
    cut = dates.prev_session(start)
    return strategy_metrics([(s.date, float(s.equity_usd)) for s in c.snapshots if s.date >= cut], ())


def _join(items: Sequence[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def gate_p3b(wf: Metrics, spy_tr: Metrics, start: date, end: date) -> Verdict:
    """The P3b gate on the walk-forward curve over ``[start, end]``.

    Passes when the walk-forward total return beats total-return SPY (strict), profit factor
    ≥ 1.3 and max drawdown ≤ 15%: ``checklist`` items 3–5, the same labels and values as the web.
    """
    if not isinstance(wf, Metrics) or not isinstance(spy_tr, Metrics):
        raise TypeError("gate_p3b takes two Metrics")
    _day("start", start)
    _day("end", end)
    beats, pf, dd = checklist(wf, spy_tr.total_return)[2:5]
    checks = (beats, pf, dd)
    passed = beats.ok and pf.ok and dd.ok
    said = (
        f"walk-forward from {start.isoformat()} to {end.isoformat()} it returned "
        f"{fmt_signed_pct(wf.total_return)} against {fmt_signed_pct(spy_tr.total_return)} for "
        f"total-return SPY, with profit factor {pf.val} and max drawdown {dd.val}"
    )
    if passed:
        sentence = f"Strategy A2 passes the P3b gate: {said}."
    else:
        failed = [name for name, item in zip(_GATE_NAMES, checks) if not item.ok]
        sentence = (
            f"Strategy A2 fails the P3b gate: {said}, so it fails on {_join(failed)}; "
            "Strategy A's one rework has failed, and P4 stays blocked."
        )
    return Verdict(passed=passed, checks=checks, sentence=sentence)
```
**Impact:** this is a new module, so nothing existing changes. `test_strategy_purity.py` picks it up through its glob
(`test_pure_sources_have_no_clock_randomness_or_io`, `test_pure_modules_load_no_db_or_network_module`).

### Step 2: Create the tests
**File:** `engine/tests/test_backtest_walkforward.py:1` (new)
**Change:** the complete test file below. What it covers:
- the real-calendar folds with every date, plus the edge cases (the data ends on the first session of January, mid-year, or on 31 Dec), and the errors;
- the 324 combinations in variant→grid order, with `A2_DESIGN_PARAMS` at index 40;
- fallbacks and tie order;
- `tune` rows `==` direct per-fold runs;
- mutating every bar (SPY included) from a traded year's first session on leaves that fold's rows and earlier folds' rows, and every selection, `==`;
- one continuous run with a schedule switching at trade starts;
- a bracket that survives 31 Dec;
- hand-computed diagnostics, window metrics and gate sentences;
- `==` repeat calls.

Runtime: about **2–3 s** in a scratch tree with a stub A2. Allow < 10 s with the real `prepare_a2`.
The A2 market has 5 symbols × 796 sessions, and tuning uses 8 of the 324 combinations.
**Code:**
```python
"""Walk-forward engine (plan phase 3; handover §6.3, §6.4, §6.5).

Two synthetic markets:

- ``wf_market``: four traded symbols plus SPY on a seeded random walk, 2019-01-02..2022-02-28,
  traded by the real ``STRATEGY_A2``. Folds 2020, 2021, 2022 tune from ``WF_IS_START``. Tuning
  uses a reduced combination list (``COMBOS``, 8 of the 324, two per variant): ``tune`` takes
  the list as an argument, and the rules under test do not depend on its length.
- ``bracket_market``: one symbol, XYZ, flat at 50 around the 2020/2021 year end, traded by
  ``BracketByParams``, a fake strategy whose bracket is a function of the params it is handed.
  It proves the schedule switches at the traded session and that an open order keeps its bracket.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Set as AbstractSet
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import numpy as np
import pytest
from simkit import D, P
from stratkit import hist, mutate_from
from test_backtest_runner import START as SCENARIO_START, run_scenario

from seer_engine import dates
from seer_engine.backtest.benchmark import BenchmarkCurve
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.metrics import Metrics, checklist, curve_metrics, run_metrics, strategy_metrics
from seer_engine.backtest.runner import ParamsSchedule, RunResult, run_backtest
from seer_engine.backtest.tuning import GridRow, Selection, grid
from seer_engine.backtest.walkforward import (
    COMBINED,
    FIRST_TRADE_YEAR,
    SEEN_BEFORE_START,
    Diagnostics,
    Fold,
    WalkForward,
    combinations,
    curve_window_metrics,
    diagnostics,
    folds,
    gate_p3b,
    schedule,
    select_fold,
    tune,
    walk_forward,
    window_metrics,
)
from seer_engine.sim import Order, Pick, Snapshot, buy_cost, q, sell_proceeds
from seer_engine.strategies.a2 import A2_DESIGN_PARAMS, STRATEGY_A2, VARIANTS, A2Params
from seer_engine.strategies.base import History

IS_START = D("2015-10-19")
DATA_END = D("2026-10-02")


def M(ret, pf=1.5, dd=0.10, trades=120, months=24.0):
    return Metrics(total_return=ret, win_rate=0.55, profit_factor=pf, max_drawdown=dd, trades=trades, months=months)


QUALIFIES = M(0.20)
FAILS = M(0.50, pf=1.0)  # PF < 1.3: never selected


# --------------------------------------------------------------------------- constants


def test_constants():
    assert FIRST_TRADE_YEAR == 2018
    assert SEEN_BEFORE_START == D("2022-01-03")
    assert COMBINED == "walk-forward"


# --------------------------------------------------------------------------- folds


def test_folds_on_the_real_calendar_are_exactly_as_defined():
    expected = [
        # year, tune_end,     trade_start,  trade_end
        (2018, "2017-12-29", "2018-01-02", "2018-12-31"),
        (2019, "2018-12-31", "2019-01-02", "2019-12-31"),
        (2020, "2019-12-31", "2020-01-02", "2020-12-31"),
        (2021, "2020-12-31", "2021-01-04", "2021-12-31"),
        (2022, "2021-12-31", "2022-01-03", "2022-12-30"),
        (2023, "2022-12-30", "2023-01-03", "2023-12-29"),
        (2024, "2023-12-29", "2024-01-02", "2024-12-31"),
        (2025, "2024-12-31", "2025-01-02", "2025-12-31"),
        (2026, "2025-12-31", "2026-01-02", "2026-10-02"),
    ]
    assert folds(IS_START, FIRST_TRADE_YEAR, DATA_END) == tuple(
        Fold(year=y, tune_start=IS_START, tune_end=D(te), trade_start=D(ts), trade_end=D(tx))
        for y, te, ts, tx in expected
    )


def test_folds_when_the_data_ends_on_the_first_session_of_january():
    fs = folds(IS_START, 2018, D("2026-01-02"))
    assert len(fs) == 9
    assert fs[-1] == Fold(2026, IS_START, D("2025-12-31"), D("2026-01-02"), D("2026-01-02"))
    assert fs[-2].trade_end == D("2025-12-31")


def test_folds_when_the_data_ends_mid_year_or_on_the_last_session_of_a_year():
    mid = folds(IS_START, 2018, D("2023-06-15"))
    assert [f.year for f in mid] == [2018, 2019, 2020, 2021, 2022, 2023]
    assert mid[-1] == Fold(2023, IS_START, D("2022-12-30"), D("2023-01-03"), D("2023-06-15"))
    year_end = folds(IS_START, 2018, D("2025-12-31"))
    assert [f.year for f in year_end] == list(range(2018, 2026))
    assert year_end[-1].trade_end == D("2025-12-31")
    one = folds(IS_START, 2016, D("2016-03-01"))
    assert one == (Fold(2016, IS_START, D("2015-12-31"), D("2016-01-04"), D("2016-03-01")),)


def test_folds_reject_bad_windows():
    with pytest.raises(ValueError):
        folds(D("2015-10-18"), 2018, DATA_END)  # a Sunday
    with pytest.raises(ValueError):
        folds(IS_START, 2018, D("2026-10-03"))  # a Saturday
    with pytest.raises(ValueError):
        folds(IS_START, 2027, DATA_END)  # no trade year inside the data
    with pytest.raises(ValueError):
        folds(IS_START, 2018, D("2017-12-29"))  # data ends before the first trade year
    with pytest.raises(ValueError):
        folds(IS_START, 2015, DATA_END)  # fold 2015 would tune on 2015-10-19..2014-12-31
    with pytest.raises(TypeError):
        folds(datetime(2015, 10, 19), 2018, DATA_END)
    with pytest.raises(TypeError):
        folds(IS_START, True, DATA_END)
    with pytest.raises(TypeError):
        folds(IS_START, "2018", DATA_END)


# --------------------------------------------------------------------------- combinations


def test_combinations_are_324_in_variant_then_grid_order():
    combos = combinations()
    g = grid()
    assert len(combos) == 324 == len(set(combos))
    assert VARIANTS == ("control", "regime", "regime_calm", "regime_calm_floor")
    for v, variant in enumerate(VARIANTS):
        for j, p in enumerate(g):
            assert combos[v * 81 + j] == A2Params.from_a(variant, p)
    assert combos.index(A2_DESIGN_PARAMS) == 40
    assert combinations() == combos


# --------------------------------------------------------------------------- selection


def test_select_fold_falls_back_when_nothing_qualifies():
    rows = tuple(GridRow(c, FAILS) for c in combinations())
    s = select_fold(rows)
    assert s == Selection(
        params=A2_DESIGN_PARAMS,
        qualified=False,
        reason=(
            "No in-sample grid run had max drawdown ≤ 15% and profit factor ≥ 1.3 (0 of 324), "
            "so the design values are kept."
        ),
    )
    for variant in VARIANTS:
        sv = select_fold(rows, variant)
        assert sv.params == A2Params(variant=variant)
        assert not sv.qualified
        assert "(0 of 81)" in sv.reason


def test_select_fold_chooses_across_variants_or_within_one():
    combos = combinations()
    rows = [GridRow(c, FAILS) for c in combos]
    rows[200] = GridRow(combos[200], M(0.30))  # regime_calm, grid entry 38
    rows[7] = GridRow(combos[7], M(0.10))  # control, grid entry 7
    assert combos[200].variant == "regime_calm"
    combined = select_fold(rows)
    assert (combined.params, combined.qualified) == (combos[200], True)
    assert select_fold(rows, "regime_calm").params == combos[200]
    assert select_fold(rows, "control").params == combos[7]
    regime = select_fold(rows, "regime")
    assert (regime.params, regime.qualified) == (A2Params(variant="regime"), False)


def test_select_fold_ties_break_by_drawdown_then_variant_then_grid_order():
    combos = combinations()
    rows = [GridRow(c, FAILS) for c in combos]
    rows[81 + 3] = GridRow(combos[81 + 3], M(0.30, dd=0.10))  # regime
    rows[5] = GridRow(combos[5], M(0.30, dd=0.10))  # control: earlier in variant -> grid order
    rows[250] = GridRow(combos[250], M(0.30, dd=0.12))  # same return, deeper drawdown
    s = select_fold(rows)
    assert s.params == combos[5]
    assert "3 runs tied on return" in s.reason


def test_select_fold_rejects_unknown_variants_and_foreign_rows():
    rows = tuple(GridRow(c, FAILS) for c in combinations()[:3])
    with pytest.raises(ValueError):
        select_fold(rows, "nope")
    with pytest.raises(TypeError):
        select_fold(rows, 1)
    from seer_engine.strategies.a import DESIGN_PARAMS

    with pytest.raises(TypeError):
        select_fold((GridRow(DESIGN_PARAMS, FAILS),))


def test_schedule_switches_at_each_trade_start():
    fs = folds(IS_START, 2024, DATA_END)
    p = combinations()
    sel = (Selection(p[0], True, "a"), Selection(p[100], True, "b"), Selection(A2_DESIGN_PARAMS, False, "c"))
    sched = schedule(fs, sel)
    assert sched == ParamsSchedule(
        segments=((D("2024-01-02"), p[0]), (D("2025-01-02"), p[100]), (D("2026-01-02"), A2_DESIGN_PARAMS))
    )
    with pytest.raises(ValueError):
        schedule(fs, sel[:2])


# --------------------------------------------------------------------------- the A2 market


WF_SESSIONS = dates.sessions(D("2019-01-02"), D("2022-02-28"))
WF_IS_START = WF_SESSIONS[200]  # data_date WF_SESSIONS[199] has exactly 200 bars
WF_END = WF_SESSIONS[-1]
TRADED = ("AAA", "BBB", "CCC", "DDD")
WF_SYMBOLS = TRADED + ("SPY",)
COMBOS = tuple(c for c in combinations() if c.a_params() in (grid()[40], grid()[67]))  # 2 per variant


def _walk(symbol: str, k: int) -> History:
    """A seeded random walk rounded to 4 dp (what ``bars`` would hold): dips, gaps and losses."""
    n = len(WF_SESSIONS)
    rng = np.random.default_rng(1000 + k)
    ret = rng.normal(0.0006, 0.018, n)
    gap = rng.normal(0.0, 0.004, n)
    up = np.abs(rng.normal(0.0, 0.008, n))
    down = np.abs(rng.normal(0.0, 0.010, n))
    o, h, lo, c = [], [], [], []
    prev = 50.0 + 10.0 * k
    for i in range(n):
        op = round(prev * (1 + gap[i]), 4)
        cl = round(prev * math.exp(ret[i]), 4)
        o.append(op)
        c.append(cl)
        h.append(round(max(op, cl) * (1 + up[i]), 4))
        lo.append(round(min(op, cl) * (1 - down[i]), 4))
        prev = cl
    return hist(symbol, c, days=WF_SESSIONS, opens=o, highs=h, lows=lo, volume=1_000_000.0 + 50_000.0 * k)


def wf_market(history: Mapping[str, History] | None = None) -> Market:
    if history is None:
        history = {s: _walk(s, k) for k, s in enumerate(WF_SYMBOLS)}
    return Market(
        history=dict(history),
        membership=Membership(tuple((s, D("2015-01-02"), None) for s in TRADED)),  # SPY is never a member
        fx=((D("2018-12-31"), Decimal("16000")), (D("2021-01-04"), Decimal("16500"))),
    )


@pytest.fixture(scope="module")
def wf():
    market = wf_market()
    prepared = STRATEGY_A2.prepare(market.history)
    fs = folds(WF_IS_START, 2020, WF_END)
    return market, prepared, fs, tune(market, STRATEGY_A2, prepared, COMBOS, fs)


def test_the_a2_market_folds(wf):
    _, _, fs, rows = wf
    assert WF_IS_START == D("2019-10-17")
    assert [(f.year, f.trade_start, f.trade_end) for f in fs] == [
        (2020, D("2020-01-02"), D("2020-12-31")),
        (2021, D("2021-01-04"), D("2021-12-31")),
        (2022, D("2022-01-03"), WF_END),
    ]
    assert len(COMBOS) == 8 and [c.variant for c in COMBOS] == [v for v in VARIANTS for _ in (0, 1)]
    assert len(rows) == 3 and all(len(r) == len(COMBOS) for r in rows)


def test_tune_rows_equal_a_fresh_run_per_fold_and_combination(wf):
    market, prepared, fs, rows = wf
    for k, f in enumerate(fs):
        for j, combo in enumerate(COMBOS):
            direct = run_backtest(market, STRATEGY_A2, combo, f.tune_start, f.tune_end, prepared=prepared)
            assert rows[k][j] == GridRow(combo, run_metrics(direct))
    assert any(row.metrics.trades > 0 for row in rows[0])  # the synthetic market trades


def test_tune_rejects_unanchored_gapped_or_no_folds(wf):
    market, prepared, fs, _ = wf
    with pytest.raises(ValueError):
        tune(market, STRATEGY_A2, prepared, COMBOS, (fs[0], replace(fs[1], tune_start=WF_SESSIONS[201])))
    with pytest.raises(ValueError):
        tune(market, STRATEGY_A2, prepared, COMBOS, (fs[0], fs[2]))
    with pytest.raises(ValueError):
        tune(market, STRATEGY_A2, prepared, COMBOS, ())


@pytest.mark.parametrize("year", [2020, 2021, 2022])
def test_changing_every_bar_from_a_traded_year_on_leaves_that_fold_and_earlier_folds_unchanged(wf, year):
    market, _, fs, rows = wf
    k = [f.year for f in fs].index(year)
    cut = fs[k].trade_start
    mutated = wf_market({s: mutate_from(h, cut) for s, h in market.history.items()})  # SPY included
    m_rows = tune(mutated, STRATEGY_A2, STRATEGY_A2.prepare(mutated.history), COMBOS, fs)
    assert m_rows[: k + 1] == rows[: k + 1]
    for j in range(k + 1):
        assert select_fold(m_rows[j]) == select_fold(rows[j])
        for variant in VARIANTS:
            assert select_fold(m_rows[j], variant) == select_fold(rows[j], variant)
    if k + 1 < len(fs):
        assert m_rows[k + 1] != rows[k + 1]  # the change is real: the next fold's window sees it


def test_walk_forward_is_one_continuous_portfolio_whose_params_switch_at_year_starts(wf):
    market, prepared, fs, rows = wf
    w = walk_forward(market, STRATEGY_A2, prepared, fs, rows)
    assert isinstance(w, WalkForward)
    assert (w.name, w.folds) == (COMBINED, fs)
    assert w.selections == tuple(select_fold(r) for r in rows)
    sched = schedule(fs, w.selections)
    assert w.run.params == sched
    assert [d for d, _ in sched.segments] == [D("2020-01-02"), D("2021-01-04"), D("2022-01-03")]
    assert w.run == run_backtest(market, STRATEGY_A2, sched, fs[0].trade_start, fs[-1].trade_end, prepared=prepared)
    assert (w.run.start, w.run.end) == (D("2020-01-02"), WF_END)
    assert [s.date for s in w.run.snapshots] == [D("2019-12-31")] + dates.sessions(D("2020-01-02"), WF_END)
    assert w.run.usd_idr == Decimal("16000")  # starting cash once, never reset at a year start


@pytest.mark.parametrize("variant", VARIANTS)
def test_walk_forward_per_variant_keeps_the_variant_fixed(wf, variant):
    market, prepared, fs, rows = wf
    w = walk_forward(market, STRATEGY_A2, prepared, fs, rows, variant)
    assert w.name == variant
    assert w.selections == tuple(select_fold(r, variant) for r in rows)
    assert all(s.params.variant == variant for s in w.selections)
    assert w.run.params == schedule(fs, w.selections)


def test_identical_calls_give_equal_results(wf):
    market, prepared, fs, rows = wf
    assert tune(market, STRATEGY_A2, STRATEGY_A2.prepare(market.history), COMBOS, fs) == rows
    a = walk_forward(market, STRATEGY_A2, prepared, fs, rows)
    b = walk_forward(market, STRATEGY_A2, prepared, fs, rows)
    assert a == b
    assert diagnostics(a.run) == diagnostics(b.run)
    assert window_metrics(a.run, D("2021-01-04")) == window_metrics(b.run, D("2021-01-04"))


# --------------------------------------------------------------------------- the year boundary


P1 = A2Params(variant="control", limit_atr=Decimal("0.25"), tp_atr=Decimal("1.5"), sl_atr=Decimal("2.0"))
P2 = A2Params(variant="regime", limit_atr=Decimal("0.75"), tp_atr=Decimal("1.0"), sl_atr=Decimal("1.0"))
# With ATR = 1 and last = 50:  P1 -> limit 49.75, tp 51.25, sl 47.75;  P2 -> limit 49.25, tp 50.25, sl 48.25.


class BracketByParams:
    """A fake ``Strategy``: on the listed data_dates it picks XYZ at last 50 with the bracket
    limit = 50 − limit_atr, tp = limit + tp_atr, sl = limit − sl_atr of the params it is handed.
    Records every ``(data_date, params)`` call."""

    id = "BRACKET"
    lookback = 1

    def __init__(self, on: AbstractSet[date]):
        self.on = frozenset(on)
        self.calls: list[tuple[date, Any]] = []

    def _picks(self, members: AbstractSet[str], data_date: date, params: Any) -> list[Pick]:
        self.calls.append((data_date, params))
        if data_date not in self.on or "XYZ" not in members:
            return []
        limit = q(Decimal("50") - params.limit_atr)
        return [Pick("XYZ", Decimal("50"), limit, q(limit + params.tp_atr), q(limit - params.sl_atr))]

    def picks(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date, params: Any) -> list[Pick]:
        return self._picks(members, data_date, params)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return None

    def picks_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date, params: Any) -> list[Pick]:
        return self._picks(members, data_date, params)


XYZ_DAYS = dates.sessions(D("2020-12-01"), D("2021-01-29"))
BRACKET_FOLDS_ARGS = (D("2019-12-02"), 2020, D("2021-01-29"))  # folds 2020 and 2021 (to 01-29)


def bracket_market() -> Market:
    """XYZ: open = close = 50, high 50.4, low 49.9, except 2020-12-31 and 2021-01-11 (low 49.0:
    a pending order fills) and 2021-01-06 (high 51.5: P1's take-profit is hit)."""
    lows = {D("2020-12-31"): 49.0, D("2021-01-11"): 49.0}
    highs = {D("2021-01-06"): 51.5}
    n = len(XYZ_DAYS)
    xyz = hist(
        "XYZ",
        [50.0] * n,
        days=XYZ_DAYS,
        opens=[50.0] * n,
        highs=[highs.get(d, 50.4) for d in XYZ_DAYS],
        lows=[lows.get(d, 49.9) for d in XYZ_DAYS],
    )
    return Market(
        history={"XYZ": xyz},
        membership=Membership((("XYZ", D("2015-01-02"), None),)),
        fx=((D("2019-11-29"), Decimal("16000")),),
    )


def test_an_order_open_across_31_december_keeps_its_bracket_and_params_switch_on_the_traded_session():
    fs = folds(*BRACKET_FOLDS_ARGS)
    assert [(f.year, f.trade_start, f.trade_end) for f in fs] == [
        (2020, D("2020-01-02"), D("2020-12-31")),
        (2021, D("2021-01-04"), D("2021-01-29")),
    ]
    fold_rows = (
        (GridRow(P1, QUALIFIES), GridRow(P2, FAILS)),  # fold 2020 selects P1
        (GridRow(P1, FAILS), GridRow(P2, QUALIFIES)),  # fold 2021 selects P2
    )
    strategy = BracketByParams({D("2020-12-30"), D("2020-12-31"), D("2021-01-08")})
    w = walk_forward(bracket_market(), strategy, None, fs, fold_rows)
    assert [s.params for s in w.selections] == [P1, P2]
    assert w.run.params == ParamsSchedule(segments=((D("2020-01-02"), P1), (D("2021-01-04"), P2)))

    # Params are keyed by the traded session S = next_session(data_date) (Decision D6).
    for data_date, params in strategy.calls:
        assert params == (P1 if dates.next_session(data_date) < D("2021-01-04") else P2)
    seen = dict(strategy.calls)
    assert seen[D("2020-12-30")] == P1  # session 2020-12-31
    assert seen[D("2020-12-31")] == P2  # session 2021-01-04: data_date = tune_end(2021)

    # 12-31: P1's order fills at 49.75 (low 49.0). 01-04 and 01-05: high 50.4 would hit P2's tp
    # 50.25 but not P1's 51.25, so it stays open. 01-04's P2 pick for XYZ is rejected 'held'.
    # 01-06: high 51.5 > 51.25 -> tp at 51.25. 01-11: P2's order fills at 49.25; 01-12 exits at 50.25.
    trades = [
        (o.symbol, o.limit_price, o.tp_price, o.sl_price, o.fill_date, o.fill_price, o.exit_date, o.exit_price, o.exit_reason)
        for o in w.run.closed
    ]
    assert trades == [
        ("XYZ", P("49.75"), P("51.25"), P("47.75"), D("2020-12-31"), P("49.75"), D("2021-01-06"), P("51.25"), "tp"),
        ("XYZ", P("49.25"), P("50.25"), P("48.25"), D("2021-01-11"), P("49.25"), D("2021-01-12"), P("50.25"), "tp"),
    ]
    assert w.run.rejections == (("held", 1),)
    assert w.run.snapshots[0].date == D("2019-12-31")
    assert len(w.run.snapshots) == len(dates.sessions(D("2020-01-02"), D("2021-01-29"))) + 1


def test_walk_forward_uses_the_fallbacks_when_nothing_qualifies():
    fs = folds(*BRACKET_FOLDS_ARGS)
    fold_rows = tuple(tuple(GridRow(c, FAILS) for c in (P1, P2)) for _ in fs)
    market = bracket_market()
    w = walk_forward(market, BracketByParams(set()), None, fs, fold_rows)
    assert [(s.params, s.qualified) for s in w.selections] == [(A2_DESIGN_PARAMS, False)] * 2
    assert w.run.params.segments == ((D("2020-01-02"), A2_DESIGN_PARAMS), (D("2021-01-04"), A2_DESIGN_PARAMS))
    per = walk_forward(market, BracketByParams(set()), None, fs, fold_rows, "regime_calm")
    assert [(s.params, s.qualified) for s in per.selections] == [(A2Params(variant="regime_calm"), False)] * 2
    mixed = ((GridRow(P1, QUALIFIES), GridRow(P2, FAILS)), (GridRow(P1, FAILS), GridRow(P2, FAILS)))
    control = walk_forward(market, BracketByParams(set()), None, fs, mixed, "control")
    assert [s.params for s in control.selections] == [P1, A2_DESIGN_PARAMS]


def test_walk_forward_rejects_mismatched_rows_and_unknown_variants():
    fs = folds(*BRACKET_FOLDS_ARGS)
    rows = ((GridRow(P1, QUALIFIES),),)
    with pytest.raises(ValueError):
        walk_forward(bracket_market(), BracketByParams(set()), None, fs, rows)
    with pytest.raises(ValueError):
        walk_forward(bracket_market(), BracketByParams(set()), None, fs, rows * 2, "nope")


# --------------------------------------------------------------------------- diagnostics


def test_diagnostics_of_the_runner_scenario():
    r, _ = run_scenario()
    # AAA 31 sh 10 -> 11 tp:   gross 31.0000, pnl 30.3490, cost 0.6510
    # BBB 15 sh 19.5 -> 20.2 time (forced): gross 10.5000, pnl 9.9045, cost 0.5955
    # CCC  6 sh 49.8 -> 45 sl: gross -28.8000, pnl -29.3688, cost 0.5688
    d = diagnostics(r)
    assert d == Diagnostics(
        trades=3,
        pnl_by_reason=(("tp", 1, P("30.349")), ("sl", 1, P("-29.3688")), ("time", 1, P("9.9045")), ("gap", 0, P("0"))),
        pnl_by_year=((2025, 3, P("10.8847")),),
        small_trades=0,
        gross_pnl_usd=P("12.7"),
        costs_usd=P("1.8153"),
        cost_drag=1.8153 / 12.7,
    )
    assert d.gross_pnl_usd - d.costs_usd == sum(o.pnl_usd for o in r.closed)


def _closed(symbol: str, slot: int, shares: int, fill: str, exit_: str, reason: str, exit_day: str) -> Order:
    f, x, day = P(fill), P(exit_), D(exit_day)
    return Order(
        session_date=day, slot=slot, symbol=symbol, last_price=f, limit_price=f,
        tp_price=f + 10, sl_price=f - 1, shares=shares, status="closed", fill_date=day,
        fill_price=f, days_held=1, exit_date=day, exit_price=x, exit_reason=reason,
        pnl_usd=sell_proceeds(x, shares) - buy_cost(f, shares),
    )


def _result(*closed: Order) -> RunResult:
    return RunResult(
        strategy_id="X", params=None, start=D("2020-12-31"), end=D("2021-01-06"), usd_idr=Decimal("16000"),
        initial_cash=P("1000"), snapshots=(), events=(), closed=tuple(closed), open_at_end=(), rejections=(),
    )


def test_diagnostics_hand_computed_small_trades_years_and_cost_drag():
    # X 1 sh 100 -> 104 tp: buy 100.1000, sell 103.8960, pnl 3.7960, gross 4, cost 0.2040
    # Y 2 sh 50 -> 48 sl:   buy 100.1000, sell 95.9040, pnl -4.1960, gross -4, cost 0.1960
    # Z 3 sh 20 -> 21 gap:  buy 60.0600, sell 62.9370, pnl 2.8770, gross 3, cost 0.1230
    x = _closed("X", 1, 1, "100", "104", "tp", "2020-12-31")
    y = _closed("Y", 2, 2, "50", "48", "sl", "2021-01-05")
    z = _closed("Z", 3, 3, "20", "21", "gap", "2021-01-06")
    assert (x.pnl_usd, y.pnl_usd, z.pnl_usd) == (P("3.796"), P("-4.196"), P("2.877"))
    d = diagnostics(_result(x, y, z))
    assert d == Diagnostics(
        trades=3,
        pnl_by_reason=(("tp", 1, P("3.796")), ("sl", 1, P("-4.196")), ("time", 0, P("0")), ("gap", 1, P("2.877"))),
        pnl_by_year=((2020, 1, P("3.796")), (2021, 2, P("-1.319"))),
        small_trades=2,
        gross_pnl_usd=P("3"),
        costs_usd=P("0.523"),
        cost_drag=0.523 / 3.0,
    )


def test_diagnostics_without_trades_or_without_gross_profit():
    empty = diagnostics(_result())
    assert empty == Diagnostics(
        trades=0,
        pnl_by_reason=tuple((reason, 0, P("0")) for reason in ("tp", "sl", "time", "gap")),
        pnl_by_year=(),
        small_trades=0,
        gross_pnl_usd=P("0"),
        costs_usd=P("0"),
        cost_drag=None,
    )
    losing = diagnostics(_result(_closed("Y", 2, 2, "50", "48", "sl", "2021-01-05")))
    assert (losing.gross_pnl_usd, losing.costs_usd, losing.cost_drag) == (P("-4"), P("0.196"), None)
    with pytest.raises(TypeError):
        diagnostics("not a run")


# --------------------------------------------------------------------------- windows


def test_window_metrics_from_the_first_session_is_run_metrics():
    r, _ = run_scenario()
    assert window_metrics(r, SCENARIO_START) == run_metrics(r)


def test_window_metrics_slice_hand_checked():
    r, _ = run_scenario()
    w = window_metrics(r, D("2025-03-06"))
    # Base: the 03-05 close (1290.5565). Exits on/after 03-06: BBB (forced, +9.9045), CCC (-29.3688).
    snaps = [
        (D("2025-03-05"), 1290.5565), (D("2025-03-06"), 1292.3547), (D("2025-03-07"), 1295.9547),
        (D("2025-03-10"), 1257.3647), (D("2025-03-11"), 1257.3647), (D("2025-03-12"), 1257.3647),
        (D("2025-03-13"), 1257.3647), (D("2025-03-14"), 1286.1647),
    ]
    assert w == replace(
        strategy_metrics(snaps, [9.9045, -29.3688]),
        avg_days_held=3.0,
        exit_reasons=(("tp", 0), ("sl", 1), ("time", 1), ("gap", 0)),
    )
    assert w.total_return == 1286.1647 / 1290.5565 - 1
    assert w.max_drawdown == (1295.9547 - 1257.3647) / 1295.9547
    assert (w.trades, w.win_rate, w.profit_factor) == (2, 0.5, 9.9045 / 29.3688)
    assert w.months == 9 / 30.44
    last = window_metrics(r, D("2025-03-14"))
    assert (last.trades, last.profit_factor, last.avg_days_held) == (0, None, None)
    assert last.total_return == 1286.1647 / 1257.3647 - 1


def test_window_metrics_rejects_starts_outside_the_run():
    r, _ = run_scenario()
    for bad in (D("2025-03-03"), D("2025-03-17"), D("2025-03-08")):
        with pytest.raises(ValueError):
            window_metrics(r, bad)
    with pytest.raises(TypeError):
        window_metrics(r, "2025-03-06")


def test_curve_window_metrics():
    def snap(d, v):
        return Snapshot(D(d), P(v), P(v))

    c = BenchmarkCurve(
        name="spy_tr",
        snapshots=(snap("2025-03-03", "1000"), snap("2025-03-04", "1010"), snap("2025-03-05", "990"),
                   snap("2025-03-06", "1020"), snap("2025-03-07", "1030")),
        shares=1, cash=P("0"), dividends_usd=P("0"),
    )
    assert curve_window_metrics(c, D("2025-03-04")) == curve_metrics(c)
    mid = curve_window_metrics(c, D("2025-03-05"))
    assert mid.total_return == 1030.0 / 1010.0 - 1
    assert mid.max_drawdown == (1010.0 - 990.0) / 1010.0
    assert (mid.trades, mid.profit_factor, mid.months) == (0, None, 3 / 30.44)
    late = curve_window_metrics(c, D("2025-03-06"))
    assert (late.total_return, late.max_drawdown) == (1030.0 / 990.0 - 1, 0.0)
    for bad in (D("2025-03-03"), D("2025-03-10"), D("2025-03-08")):
        with pytest.raises(ValueError):
            curve_window_metrics(c, bad)


# --------------------------------------------------------------------------- the P3b gate


SPY_TR = Metrics(total_return=0.75, win_rate=None, profit_factor=None, max_drawdown=0.20, trades=0, months=105.0)
WF_START, WF_GATE_END = D("2018-01-02"), D("2026-10-02")


def test_gate_p3b_pass_sentence():
    wf_m = M(0.80, pf=1.5, dd=0.12, trades=300, months=105.0)
    v = gate_p3b(wf_m, SPY_TR, WF_START, WF_GATE_END)
    assert v.passed
    assert v.checks == tuple(checklist(wf_m, 0.75)[2:5])
    assert v.sentence == (
        "Strategy A2 passes the P3b gate: walk-forward from 2018-01-02 to 2026-10-02 it returned "
        "+80.0% against +75.0% for total-return SPY, with profit factor 1.50 and max drawdown 12.0%."
    )


def test_gate_p3b_fail_sentence_names_every_failed_check_and_blocks_p4():
    v = gate_p3b(M(-0.10, pf=0.9, dd=0.30), SPY_TR, WF_START, WF_GATE_END)
    assert not v.passed
    assert v.sentence == (
        "Strategy A2 fails the P3b gate: walk-forward from 2018-01-02 to 2026-10-02 it returned "
        "−10.0% against +75.0% for total-return SPY, with profit factor 0.90 and max drawdown 30.0%, "
        "so it fails on beating total-return SPY, profit factor ≥ 1.3 and max drawdown ≤ 15%; "
        "Strategy A's one rework has failed, and P4 stays blocked."
    )


@pytest.mark.parametrize(
    ("wf_m", "name"),
    [
        (M(0.70, pf=1.5, dd=0.12), "beating total-return SPY"),
        (M(0.80, pf=1.29, dd=0.12), "profit factor ≥ 1.3"),
        (M(0.80, pf=1.5, dd=0.151), "max drawdown ≤ 15%"),
    ],
)
def test_gate_p3b_fails_on_each_condition_alone(wf_m, name):
    v = gate_p3b(wf_m, SPY_TR, WF_START, WF_GATE_END)
    assert not v.passed
    assert v.sentence.endswith(f", so it fails on {name}; Strategy A's one rework has failed, and P4 stays blocked.")


def test_gate_p3b_boundaries():
    assert not gate_p3b(M(0.75, pf=1.5, dd=0.12), SPY_TR, WF_START, WF_GATE_END).passed  # equal is not beating
    assert gate_p3b(M(0.80, pf=1.3, dd=0.15), SPY_TR, WF_START, WF_GATE_END).passed  # inclusive thresholds
    inf = gate_p3b(M(0.80, pf=math.inf, dd=0.10), SPY_TR, WF_START, WF_GATE_END)
    assert inf.passed and "profit factor ∞" in inf.sentence
    with pytest.raises(TypeError):
        gate_p3b(M(0.80), SPY_TR, "2018-01-02", WF_GATE_END)
```
**Impact:** this is a new test file. It imports `run_scenario`/`START` from `test_backtest_runner` (the tests dir is on
`sys.path`, the same way `simkit`/`stratkit` are imported) and `hist`/`mutate_from` from `stratkit`, both read only.
The A2 market uses `numpy.random.default_rng` with fixed seeds, and only in the test. No assertion hard-codes a value
that depends on the random stream: every check compares two computations with each other.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/strategy-a-rework && engine/.venv/bin/python -c "import seer_engine.backtest.walkforward"` (use the worktree's own venv, never main's)
**Tests:**
- `docker start seer-pg`
- `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests/test_backtest_walkforward.py engine/tests/test_strategy_purity.py -q` → 39 + 3 passed
- the full suite `PG_TEST_URL=... engine/.venv/bin/pytest engine/tests -q` → **712 passed, 0 skipped** (673 after phases 1 + 2, + 39; plan index invariant 1).

**Manual check:**
- The planner pre-ran both files green (39 passed in 2.2 s, plus the 3 purity tests) in a scratch copy of the tree, with minimal stand-ins for the phase 1/2 contract.
- If the real phase 1/2 code differs from the contract, fix the call site here, not the contract, and record it.
- Check in particular:
  - `A2Params` is hashable (`len(set(combinations())) == 324`);
  - `A2Params.a_params()` exists (`COMBOS` uses it);
  - `ParamsSchedule` takes `segments=` as a keyword.

**Exit criteria:**
- the module exists exactly per the contract;
- `test_backtest_walkforward.py` is 39 passed;
- the purity glob covers `seer_engine.backtest.walkforward` and passes;
- the full suite is green with 0 skipped;
- no file outside the two listed is touched.

## Handoffs

- **Phase 5 (`backtest_wf`):**
  - Per-combo timing: call `tune` once per combo and merge, as described in Design notes. The merged result `==` a single `tune` call.
  - Call order:
    1. `folds(tuning.IS_START, FIRST_TRADE_YEAR, data_end)`;
    2. `STRATEGY_A2.prepare(market.history)` once;
    3. `tune(..., combinations(), fs)`;
    4. `walk_forward(..., None)` and once per `VARIANTS` entry;
    5. `spy_curves(market.spy(), fs[0].trade_start, fs[-1].trade_end, combined.run.initial_cash, dividends)`;
    6. `gate_p3b(run_metrics(combined.run), curve_metrics(spy_tr), fs[0].trade_start, fs[-1].trade_end)`.
- **Phase 4 (`wf_report`):**
  - "Seen before" uses `window_metrics(wf.run, SEEN_BEFORE_START)` and `curve_window_metrics(spy_x, SEEN_BEFORE_START)`. Both need `SEEN_BEFORE_START` inside the run's sessions, so it renders only when `data_end >= 2022-01-03`.
  - Diagnostics come from `diagnostics(wf.run)`. Render `cost_drag None` as "—".
  - Build `Fold`s via `folds()`, not by hand. `_check_folds` rejects inconsistent hand-built folds when they reach `tune`/`walk_forward`.
- **Phase 2:** keep `run_scenario`/`START` in `test_backtest_runner.py` unchanged (this phase imports them).
- No drive-by cleanups found.

## Rollback

Delete `engine/src/seer_engine/backtest/walkforward.py` and `engine/tests/test_backtest_walkforward.py` (or `git revert`
the phase commit). Nothing else references them until phases 4–5 land.
