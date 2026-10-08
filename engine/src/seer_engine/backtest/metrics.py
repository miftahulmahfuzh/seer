"""Backtest metrics, identical to the web's (``web/lib/metrics.ts``), plus CAGR, average days
held and the exit-reason breakdown.

Pure: floats only, no clock, no I/O. ``strategy_metrics`` and ``checklist`` port
``strategyMetrics`` and ``checklist`` line for line. ``to_fixed`` ports JavaScript's
``Number.prototype.toFixed`` (the exact binary value, rounded with ties away from zero), so
every string the web shows comes out byte for byte the same. Sums run left to right in a plain
loop, like ``Array.prototype.reduce``, and never through ``sum``/``math.fsum``, which may
compensate rounding.

CAGR uses Actual/365.25: years = calendar days between the first and last snapshot / 365.25,
CAGR = (last / first) ** (1 / years) - 1. The first snapshot of every curve is the starting cash
on the session before the window, so CAGR and total return measure from the same point.

``money_weighted_return`` is the measure for a curve that received deposits: the interest rate a
savings account would have had to pay to turn the same deposits, paid in on the same days, into
the same final balance. CAGR cannot answer that -- a deposit raises the ending balance without
being a return, and measured on the owner's real funding plan a book that earns nothing at all
reports a CAGR of +600.9%. ``Metrics.mwr`` carries it, and is None exactly when the run received
no deposits, because then CAGR already *is* the money-weighted return.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any

from seer_engine import dates
from seer_engine.backtest.benchmark import BenchmarkCurve
from seer_engine.backtest.runner import RunResult
from seer_engine.sim import Order

MONTH_DAYS = 30.44
YEAR_DAYS = 365.25

MIN_PAPER_MONTHS = 18
"""Go-live condition #1 (design §1, §13): months of forward paper before a real-money decision.

The single definition in Python; ``tuning.MIN_PAPER_MONTHS`` re-exports it and ``web/lib/
golive.ts`` is the TypeScript twin. Set by the owner on 2026-10-07, replacing "≥ 3 months AND
≥ 100 closed trades" -- a trade count scales with how many names a book holds rather than with
how much evidence exists, so it asked two centuries of an index-timing strategy and five months
of a twenty-name book. 18 is where the deleted bar already stood for the current roster
(14.9-20.7 months at its trade rates), stated in a unit that does not depend on the engine.

It is a floor on noise, not a claim of confidence: measured on the recorded dev curves, these
strategies beat SPY in 54-72% of rolling 18-month windows and only 65-78% of 36-month ones.
Design §13 carries the table.
"""

MAX_DRAWDOWN = 0.20
"""Go-live condition #4 (design §1): the deepest peak-to-trough fall a strategy may show.

The single definition in Python. ``tuning.MAX_DRAWDOWN`` re-exports this name, so every caller
that reads the threshold -- ``checklist`` below, ``tuning.qualifies``, ``tuning.gate``,
``walkforward.gate_p3b``, ``b_walkforward.gate_p6a``, ``dev.make_row`` and ``lab.store.snapshot``
-- resolves to this one float. It lives here, not in ``tuning``, only because ``tuning`` imports
``metrics`` and the dependency cannot run the other way.

0.15 until 2026-10-07, when the owner raised it to 0.20 on stated risk appetite; design §11
records the revision. ``web/lib/golive.ts`` carries the same number for the leaderboard and is
pinned to it through ``data/lab.json``'s gate by ``web/lib/golive.test.ts``.
"""
EXIT_REASONS: tuple[str, ...] = ("tp", "sl", "time", "gap")
MINUS = "−"  # the web's minus sign in signed percentages
DASH = "—"  # the web's "no value"
INFINITY = "∞"


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


@dataclass(frozen=True)
class CheckItem:
    label: str
    val: str
    ok: bool


# --------------------------------------------------------------------------- arithmetic


def _sum(values: Iterable[float]) -> float:
    """Left-to-right float sum starting at 0, exactly like ``reduce((a, p) => a + p, 0)``."""
    total = 0.0
    for v in values:
        total += v
    return total


def cagr_between(first: tuple[date, float], last: tuple[date, float]) -> float | None:
    """Compound annual growth from ``first`` to ``last`` (Actual/365.25); None when undefined."""
    days = (last[0] - first[0]).days
    if days <= 0 or first[1] <= 0 or last[1] < 0:
        return None
    years = days / YEAR_DAYS
    return (last[1] / first[1]) ** (1.0 / years) - 1.0


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

    ``max_drawdown`` is **not** in that amnesty, and the asymmetry is the point. ``total_return``
    and ``cagr`` are left contaminated deliberately, because they are the recorded shape of the
    curve that readers of the 128 historical trials depend on, and ``mwr`` stands beside them with
    the honest number. The drawdown has no such companion and is read directly as a go-live
    condition, so for a funded run it is measured on the time-weighted index instead of on raw
    equity -- a deposit must not be allowed to make a method look safer than it was.
    """
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gross_win = _sum(wins)
    gross_loss = -_sum(losses)

    peak = -math.inf
    max_dd = 0.0
    if cashflows:
        # A deposit raises the peak and refills the trough, so a funded run's drawdown measured on
        # raw equity reads SAFER than the strategy was -- and `max_drawdown` is a gate condition
        # (`tuning.MAX_DRAWDOWN`, re-derived by `lab.store.owner_failures` and `_blocking`).
        # Measured on the smoke fixture: 7.96% on raw equity against 10.55% honest, and the DCA'd
        # SPY benchmark damped from 25.75% to 10.59%. So the drawdown of a funded run is taken on
        # the time-weighted wealth index -- the curve the strategy would have traced on one
        # unchanging dollar -- built from the same cashflow-adjusted session growth
        # `book_runner._daily_returns` uses. With no cashflows the branch below is skipped and the
        # original loop runs unchanged, so every unfunded run is byte-identical.
        flows = flow_map(cashflows)
        index = 1.0
        peak = index
        for (_, prev), (d, cur) in zip(snaps, snaps[1:]):
            index *= cur / (prev + flows.get(d, 0.0))
            peak = max(peak, index)
            max_dd = max(max_dd, (peak - index) / peak)
    else:
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


def avg_days_held(orders: Sequence[Order]) -> float | None:
    """Mean ``days_held`` of closed orders (the simulator's session count); None when empty."""
    if not orders:
        return None
    total = 0
    for o in orders:
        total += o.days_held
    return total / len(orders)


def exit_reason_counts(orders: Sequence[Order]) -> tuple[tuple[str, int], ...]:
    """``(reason, count)`` for every simulator exit reason, in ``EXIT_REASONS`` order, zeros kept."""
    counts = {reason: 0 for reason in EXIT_REASONS}
    for o in orders:
        if o.exit_reason not in counts:
            raise ValueError(f"order {o.symbol} has exit_reason {o.exit_reason!r}, not one of {EXIT_REASONS}")
        counts[o.exit_reason] += 1
    return tuple((reason, counts[reason]) for reason in EXIT_REASONS)


def forced_closes(r: RunResult) -> int:
    """Exits forced by ``close_unpriced`` (bars ended). Counted inside the ``time`` reason too."""
    n = 0
    for e in r.events:
        if e.kind == "exit" and e.forced:
            n += 1
    return n


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


def flow_map(cashflows: Sequence[tuple[date, float]]) -> dict[date, float]:
    """``{session: total deposited that session}`` -- the one place deposits become a lookup.

    Several deposits can share a session (a schedule the calendar lagged onto one open), so they
    are summed rather than overwritten. Used by the cashflow-adjusted return and drawdown
    computations in this module and in ``book_runner``.
    """
    out: dict[date, float] = {}
    for when, amount in cashflows:
        out[when] = out.get(when, 0.0) + float(amount)
    return out


def run_metrics(r: RunResult) -> Metrics:
    """Metrics of a strategy run: its per-session snapshots, every closed order (forced included),
    and the deposits it received."""
    snaps = [(s.date, float(s.equity_usd)) for s in r.snapshots]
    pnls = [float(o.pnl_usd) for o in r.closed if o.pnl_usd is not None]
    base = strategy_metrics(snaps, pnls, external_cashflows(r))
    return replace(base, avg_days_held=avg_days_held(r.closed), exit_reasons=exit_reason_counts(r.closed))


def metrics_through(r: RunResult, end: date) -> Metrics:
    """``run_metrics`` of ``r`` cut at the session ``end``.

    Keeps the snapshots dated ``<= end`` and the orders whose exit event has
    ``session_date <= end``, in event order. A forced close (``close_unpriced``) is dated the
    session it happens on, so one on the session after ``end`` is left out, as it would be
    in a run that stops at ``end``. ``end`` must be an NYSE session with
    ``r.start <= end <= r.end``.

    Prefix property: the runner's loop never reads ``end`` except to bound its sessions, so
    this equals ``run_metrics(run_backtest(<same market, strategy, params, start, prepared>,
    end=end))``.
    """
    if not isinstance(r, RunResult):
        raise TypeError(f"r must be a RunResult, got {type(r).__name__}")
    if isinstance(end, datetime) or not isinstance(end, date):
        raise TypeError(f"end must be a date, got {type(end).__name__}")
    if not dates.is_session(end):
        raise ValueError(f"end {end} is not an NYSE session")
    if not r.start <= end <= r.end:
        raise ValueError(f"end {end} is outside the run's window [{r.start}, {r.end}]")
    snapshots = tuple(s for s in r.snapshots if s.date <= end)
    events = tuple(e for e in r.events if e.session_date <= end)
    closed = tuple(e.order for e in events if e.kind == "exit")
    return run_metrics(replace(r, end=end, snapshots=snapshots, events=events, closed=closed))


def curve_metrics(c: BenchmarkCurve) -> Metrics:
    """Metrics of a buy-and-hold curve: no trades, so win rate and profit factor are None.

    ``c.cashflows`` are the deposits the curve received, so a dollar-cost-averaged SPY reports a
    money-weighted return computed from the same dollars on the same days as the book it is
    benchmarking.
    """
    return strategy_metrics(
        [(s.date, float(s.equity_usd)) for s in c.snapshots], (), c.cashflows
    )


# --------------------------------------------------------------------------- formatting


def to_fixed(x: float, digits: int) -> str:
    """JavaScript ``x.toFixed(digits)`` for finite ``|x| < 1e21``.

    It rounds the exact binary value of ``x`` to ``digits`` decimals, ties away from zero
    ("pick the larger n"), and ``-0`` prints as ``0``. That is what JS does, and Python's
    ``format`` does not.
    """
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise TypeError(f"to_fixed takes an int or float, got {type(x).__name__}")
    if not 0 <= digits <= 100:
        raise ValueError(f"digits must be 0..100, got {digits}")
    if not math.isfinite(x):
        raise ValueError(f"to_fixed needs a finite number, got {x!r}")
    if abs(x) >= 1e21:
        raise ValueError(f"toFixed switches to exponent notation at 1e21, got {x!r}")
    if x == 0:
        x = 0.0  # -0 and int 0 both print as "0", like JS
    with localcontext() as ctx:
        ctx.prec = 200
        d = Decimal(x).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    return format(d, "f")


def _p1(v: float) -> str:
    """The web's ``p1``: sign (+ or U+2212) and |v × 100| to 1 decimal, no percent sign."""
    return ("+" if v >= 0 else MINUS) + to_fixed(abs(v * 100), 1)


def fmt_signed_pct(v: float | None) -> str:
    """``+6.8%`` / ``−3.2%``; the dash for None."""
    return DASH if v is None else _p1(v) + "%"


def fmt_pct(v: float | None, digits: int = 1) -> str:
    """``7.9%`` (v × 100, unsigned format); the dash for None."""
    return DASH if v is None else to_fixed(v * 100, digits) + "%"


def fmt_pf(v: float | None) -> str:
    """A profit factor as the web shows it: 2 decimals, ``∞``, or the dash."""
    if v is None:
        return DASH
    if v == math.inf:
        return INFINITY
    return to_fixed(v, 2)


def fmt_num(v: float | None, digits: int = 2) -> str:
    return DASH if v is None else to_fixed(v, digits)


# --------------------------------------------------------------------------- go-live checklist

MAX_DRAWDOWN_LABEL = f"Max drawdown ≤ {fmt_pct(MAX_DRAWDOWN, 0)}"
"""The checklist's label for go-live #4, built from ``MAX_DRAWDOWN`` so it cannot drift from the
threshold it names. ``web/lib/golive.ts`` builds the same string the same way."""



def checklist(m: Metrics, spy_return: float | None) -> list[CheckItem]:
    """``checklist`` from web/lib/metrics.ts: the fixed go-live rules (design §1), same labels and
    value strings."""
    ret = m.total_return if m.total_return is not None else 0.0
    pf = m.profit_factor
    return [
        CheckItem(
            f"≥ {MIN_PAPER_MONTHS} months forward",
            f"{to_fixed(math.floor(m.months * 10) / 10, 1)} mo",
            m.months >= MIN_PAPER_MONTHS,
        ),
        CheckItem(
            "Beats SPY",
            DASH if spy_return is None else f"{_p1(ret)} vs {_p1(spy_return)}",
            m.total_return is not None and spy_return is not None and ret > spy_return,
        ),
        CheckItem(
            "Profit factor ≥ 1.3",
            DASH if pf is None else INFINITY if pf == math.inf else to_fixed(pf, 2),
            (pf if pf is not None else 0.0) >= 1.3,
        ),
        CheckItem(
            MAX_DRAWDOWN_LABEL,
            DASH if m.max_drawdown is None else to_fixed(m.max_drawdown * 100, 1) + "%",
            m.max_drawdown is not None and m.max_drawdown <= MAX_DRAWDOWN,
        ),
    ]


def gate_checks(m: Metrics, spy_return: float | None) -> tuple[CheckItem, CheckItem, CheckItem]:
    """The three conditions a BACKTEST can evaluate: beats SPY TR, profit factor, max drawdown.

    Design §1 items 2, 3 and 4. ``tuning.gate``, ``walkforward.gate_p3b``,
    ``b_walkforward.gate_p6a`` and ``wf_report`` all judge exactly these three and take their
    labels and value strings from :func:`checklist`, so the reports and the web read identically.

    **Why this exists rather than a slice.** Those four call sites each wrote
    ``checklist(...)[2:5]``. When design §13 dropped the trades item on 2026-10-07 the list
    shortened, every one of those slices silently became the wrong three items, and 96 tests
    failed at once. Selecting by meaning rather than by position means the next change to
    ``checklist`` cannot do that again.
    """
    items = {c.label: c for c in checklist(m, spy_return)}
    return items["Beats SPY"], items["Profit factor ≥ 1.3"], items[MAX_DRAWDOWN_LABEL]
