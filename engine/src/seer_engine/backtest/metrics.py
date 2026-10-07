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
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, localcontext

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
    """One curve's metrics. The first six fields are the web's ``Metrics``; the last three are
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


def strategy_metrics(snaps: Sequence[tuple[date, float]], pnls: Sequence[float]) -> Metrics:
    """``strategyMetrics`` from web/lib/metrics.ts, plus CAGR over the same snapshots.

    ``snaps`` are ``(date, equity)`` in date order; ``pnls`` are closed trades' P/L in USD.
    A win is ``p > 0`` and a loss is ``p <= 0``. Profit factor is gross win / gross loss, or
    ``inf`` when trades exist and the gross loss is 0, or None with no trades. Max drawdown is
    the largest ``(peak - equity) / peak`` over the snapshots. Total return is
    last / first - 1. Months is calendar days / 30.44.
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


def run_metrics(r: RunResult) -> Metrics:
    """Metrics of a strategy run: its per-session snapshots and every closed order (forced included)."""
    snaps = [(s.date, float(s.equity_usd)) for s in r.snapshots]
    pnls = [float(o.pnl_usd) for o in r.closed if o.pnl_usd is not None]
    base = strategy_metrics(snaps, pnls)
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
    """Metrics of a buy-and-hold curve: no trades, so win rate and profit factor are None."""
    return strategy_metrics([(s.date, float(s.equity_usd)) for s in c.snapshots], ())


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
