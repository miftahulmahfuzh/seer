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
