> Adopted from `STRATEGY_A_BACKTEST_PLAN.md` phase 4. Source: `.workflows/plan/strategy-a-backtest/phase-4.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 4: Metrics (web parity), grid + selection + gate, report rendering

**Plan set:** `STRATEGY_A_BACKTEST_PLAN.md`
**Analysis:** `20261003-144506-Q8N4_code_analyzer.md`
**Satisfies:** R4, R5. R4: the fixed 81-run grid, the in-sample-only selection and the gate. R5: the
report (curves vs SPY, return, CAGR, win rate, PF, max DD, trades, exit reasons, go-live items,
IS/OOS/full shown separately, survivorship, verdict), with metrics identical to `web/lib/metrics.ts`
**Depends on:** Phase 2 (`BenchmarkCurve`) and Phase 3 (`RunResult`, `YearGap`). Phase 1 is reached through them (`AParams`, `DESIGN_PARAMS`)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/backtest/`

---

## Goal

After this phase the backtest has a pure "measure and decide" layer:

- `metrics.py` computes the same numbers and the same checklist strings as `web/lib/metrics.ts`,
  byte for byte, and adds CAGR, average days held and the exit-reason breakdown.
- `tuning.py` declares the fixed 81-run grid. It selects on in-sample metrics only and gives the
  gate verdict from out-of-sample metrics.
- `report.py` turns a `BacktestReport` value into deterministic Markdown, a wide CSV and a
  self-contained SVG.

Nothing here touches a database, a file or the clock. Phase 5 builds the `BacktestReport` and
writes the files, and phase 6 commits the real ones.

## Interface Contract

**Deletes:** none
**Renames:** none
**Creates** (every name in the shared contract, with the same signature, plus the extra public
helpers marked "+"):

- `seer_engine.backtest.metrics` (`engine/src/seer_engine/backtest/metrics.py`):
  - `Metrics` (frozen dataclass): `total_return`, `win_rate`, `profit_factor`, `max_drawdown`,
    `trades`, `months`, `cagr`, `avg_days_held`, `exit_reasons`. The last three default to
    `None`, `None`, `()`, so a value shaped like the web's `Metrics` can be built from the first
    six fields only.
  - `CheckItem(label, val, ok)`
  - `strategy_metrics(snaps, pnls)`, `checklist(m, spy_return)`, `run_metrics(r)`, `curve_metrics(c)`
  - \+ `MONTH_DAYS = 30.44`, `YEAR_DAYS = 365.25`, `EXIT_REASONS = ("tp", "sl", "time", "gap")`,
    `MINUS = "−"`, `DASH = "—"`, `INFINITY = "∞"`
  - \+ `cagr_between(first, last)`, `avg_days_held(orders)`, `exit_reason_counts(orders)`,
    `forced_closes(r)`
  - \+ formatters: `to_fixed(x, digits)` (a port of JS `Number.prototype.toFixed`),
    `fmt_signed_pct`, `fmt_pct`, `fmt_pf`, `fmt_num`
- `seer_engine.backtest.tuning` (`engine/src/seer_engine/backtest/tuning.py`):
  - `IS_START`, `OOS_START`, `GRID_RSI`, `GRID_LIMIT`, `GRID_TP`, `GRID_SL`, `MAX_DRAWDOWN`,
    `MIN_PROFIT_FACTOR`
  - `grid()`, `GridRow`, `Selection`, `select(rows)`, `Verdict`, `gate(oos, spy_tr_oos)`
  - \+ `qualifies(m)`
- `seer_engine.backtest.report` (`engine/src/seer_engine/backtest/report.py`):
  - `WindowResult`, `BacktestReport` (+ method `windows()`)
  - `render_markdown`, `equity_csv`, `equity_svg`, `report_stem`
  - \+ `FROZEN_KEY = "frozen-params"`, `SELECTED_KEY = "selected-params"`, `params_line(key, params)`,
    `parse_params_line(markdown, key)`

**The machine-readable lines** that phase 6 parses. `render_markdown` emits each of these exactly
once, on a line of its own with no indentation, inside a fenced `text` block:

```text
frozen-params: {"rsi_max": "10", "limit_atr": "0.5", ...}
selected-params: {"rsi_max": "...", ...}
```

The JSON is `json.dumps(params.as_dict())` with the default separators `", "` and `": "`, keys in
`as_dict()` order, and is never sorted. `frozen-params` comes from `report.frozen_params` (what
`STRATEGY_A_PARAMS` held at run time). `selected-params` comes from `report.selection.params`.
Only two lines depend on `frozen_params`: the `frozen-params:` line and the one sentence
"Frozen in code ... matches / differs". Every number in the report comes from the runs, and all
three window runs must have used `selection.params` (a `ValueError` is raised otherwise).
Regex: `^frozen-params: (\{.*\})$` (MULTILINE).

**Signature changes:** none (all new)
**Requires (from earlier phases):**

- Phase 1: `seer_engine.strategies.a.AParams` must be a frozen dataclass with `__eq__` and with
  `as_dict() -> dict[str, str]`. The keys must be, in this order, `rsi_max`, `limit_atr`,
  `tp_atr`, `sl_atr`, `min_dollar_volume`. `AParams(rsi_max=float, limit_atr=Decimal,
  tp_atr=Decimal, sl_atr=Decimal)` must construct, leaving `min_dollar_volume` at its default.
  `DESIGN_PARAMS = AParams()` must equal `(10.0, 0.5, 1.0, 1.5)`. Phase 1 must also provide
  `seer_engine/backtest/__init__.py` (docstring only) and the purity test that globs
  `backtest/*.py`.
- Phase 2: `seer_engine.backtest.benchmark.BenchmarkCurve(name, snapshots, shares, cash,
  dividends_usd)` must be a plain frozen dataclass that builds from keyword arguments.
  `snapshots[0]` is `Snapshot(prev_session(start), cash0, cash0)`.
- Phase 3: `seer_engine.backtest.runner.RunResult(strategy_id, params, start, end, usd_idr,
  initial_cash, snapshots, events, closed, open_at_end, rejections)` must be a plain frozen
  dataclass that builds from keyword arguments, with no `__post_init__` that would refuse
  hand-built values.
  - `closed` holds `sim.Order` with `status="closed"`, and forced closes are included.
  - `events` holds `sim.Event`. A forced close is `kind="exit", forced=True`.
  - `rejections` is sorted `(reason, count)` pairs.
  - The module also defines `INITIAL_IDR` and
    `YearGap(year, member_sessions, missing, missing_never_fetched, missing_other)`.
  - Importing `runner` must not import `metrics`, `tuning` or `report`, or there is a cycle.
- Phase 5 (a downstream expectation, not something this phase needs in order to build):
  - Build `BacktestReport` with the three `WindowResult`s run on `selection.params`.
  - Set `frozen_params = STRATEGY_A_PARAMS`.
  - Set `verdict = gate(run_metrics(oos.run), curve_metrics(oos.spy_tr))`.
  - Use the window names `"In-sample"`, `"Out-of-sample"` and `"Full window"` (reconciled: phase 5's
    `commands/backtest.WINDOW_NAMES` holds exactly these; this module renders `WindowResult.name` as given).

**Leaves alone (owned by others):** `backtest/benchmark.py` (P2), `backtest/market.py` and
`backtest/runner.py` (P3), `strategies/*` (P1, P6), `backtest/io.py` and `commands/backtest.py` (P5),
`engine/package_readme.md` and `docs/*` (P6), `seer_engine/sim/*` (no one), `web/*` (no one).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/metrics.py` | create (line 1) | `Metrics`, `CheckItem`, the web-parity `strategy_metrics`/`checklist`, CAGR, days held, exit reasons, JS-exact formatters |
| `engine/src/seer_engine/backtest/tuning.py` | create (line 1) | window constants, the 81-run grid, `qualifies`, `select`, `gate` |
| `engine/src/seer_engine/backtest/report.py` | create (line 1) | `WindowResult`, `BacktestReport`, `render_markdown`, `equity_csv`, `equity_svg`, `report_stem`, params lines |
| `engine/tests/test_backtest_metrics.py` | create (line 1) | parity with every `web/lib/metrics.test.ts` case, `to_fixed` against JS, CAGR, days held, exit reasons, run/curve metrics |
| `engine/tests/test_backtest_tuning.py` | create (line 1) | grid size and order, selection rules and tie-breaks, fallback, gate pass and each fail |
| `engine/tests/test_backtest_report.py` | create (line 1) | a synthetic `BacktestReport`: determinism, every section, 81 grid rows, params lines, CSV, SVG |

Six files, all new. Line references are line 1 because every file is created by this phase.

## Implementation Steps

### Step 0: Worktree venv (only if absent)

**File:** none (environment)
**Change:** The worktree may have no `engine/.venv`. Never use `/home/miftah/seer/engine/.venv`,
because it tests main's tree.

```sh
cd /home/miftah/.worktrees/seer/strategy-a-backtest
test -x engine/.venv/bin/python || python3 -m venv engine/.venv
engine/.venv/bin/pip install -q -e 'engine[dev]'
docker start seer-pg
```

**Impact:** none on the tree.

### Step 1: `metrics.py`

**File:** `engine/src/seer_engine/backtest/metrics.py:1` (new)

**Change:** a line-for-line port of `web/lib/metrics.ts`, plus the extra metrics.

- **Sums:** plain left-to-right loops. Never use `sum()` or `math.fsum`. Python 3.12+ `sum`
  compensates float rounding, and that would break parity with `Array.reduce`.
- **`to_fixed`:** reproduces `toFixed`. It rounds the exact binary value with ties away from
  zero, and turns `-0` into `"0.0"`. Python's `format(x, ".1f")` differs on exact ties: `2.5`
  gives `"2"` in Python and `"3"` in JS.

**CAGR definition (Actual/365.25):**

- The curve runs from its first snapshot `(d0, e0)` to its last snapshot `(d1, e1)`. The first
  snapshot is `prev_session(start)` at the starting cash.
- `days = (d1 − d0).days` (calendar days) and `years = days / 365.25`.
- `CAGR = (e1 / e0) ** (1 / years) − 1`.
- CAGR is `None` when there are fewer than one snapshot, when `days <= 0`, when `e0 <= 0` or when
  `e1 < 0`.

**Code:**

```python
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
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext

from seer_engine.backtest.benchmark import BenchmarkCurve
from seer_engine.backtest.runner import RunResult
from seer_engine.sim import Order

MONTH_DAYS = 30.44
YEAR_DAYS = 365.25
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


def checklist(m: Metrics, spy_return: float | None) -> list[CheckItem]:
    """``checklist`` from web/lib/metrics.ts: the fixed go-live rules (design §1), same labels and
    value strings."""
    ret = m.total_return if m.total_return is not None else 0.0
    pf = m.profit_factor
    return [
        CheckItem(
            "≥ 3 months forward",
            f"{to_fixed(math.floor(m.months * 10) / 10, 1)} mo",
            m.months >= 3,
        ),
        CheckItem("≥ 100 trades", f"{m.trades} / 100", m.trades >= 100),
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
            "Max drawdown ≤ 15%",
            DASH if m.max_drawdown is None else to_fixed(m.max_drawdown * 100, 1) + "%",
            m.max_drawdown is not None and m.max_drawdown <= 0.15,
        ),
    ]
```

**Impact:** a new module. It imports `benchmark` and `runner`, and nothing imports it yet.

**Parity notes** (keep in the implementer's head and do not change):

- JS `Math.floor(m.months*10)/10` is `math.floor(...)/10`. An int divided by 10 gives the same
  float as in JS.
- JS `grossLoss = -losses.reduce(...)`. With no losses this is `-0`, and `-0 === 0`, so the
  profit factor is `Infinity`. In Python `-0.0 == 0` is also true.
- A trade with P/L exactly 0 is a loss. So `pnls = [0]` gives `win_rate 0`, gross loss `-0` and
  profit factor `inf`, the same as the web.
- Division by a zero peak or a zero first equity raises in Python, where JS gives `NaN`/`Infinity`.
  It cannot happen here, because every curve starts at positive cash.

### Step 2: `tuning.py`

**File:** `engine/src/seer_engine/backtest/tuning.py:1` (new)
**Change:** the windows, the grid (fixed before any result), selection on in-sample only, and the
gate on out-of-sample only. The gate's three checks are items 3–5 of `checklist`, so the gate
uses exactly the web's labels and its strict `>`. A test pins `MAX_DRAWDOWN` and
`MIN_PROFIT_FACTOR` to the thresholds hard-coded in `checklist`.

**Code:**

```python
"""Parameter grid, in-sample selection and the P3 gate (handover §3 "Tuning", "Gate verdict").

Pure. The grid was fixed before any result was seen and never changes. ``select`` reads
in-sample metrics only. ``gate`` reads out-of-sample metrics only. No function here can see both
windows at once, so nothing out of sample can feed back into selection (invariant 6).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from seer_engine.backtest.metrics import CheckItem, Metrics, checklist, fmt_pct, fmt_signed_pct
from seer_engine.strategies.a import DESIGN_PARAMS, AParams

IS_START = date(2015, 10, 19)  # first session whose data_date has 200 bars of history
OOS_START = date(2022, 1, 3)  # in-sample ends at prev_session(OOS_START) = 2021-12-31

GRID_RSI: tuple[float, ...] = (5.0, 10.0, 15.0)
GRID_LIMIT: tuple[Decimal, ...] = (Decimal("0.25"), Decimal("0.5"), Decimal("0.75"))
GRID_TP: tuple[Decimal, ...] = (Decimal("0.75"), Decimal("1.0"), Decimal("1.5"))
GRID_SL: tuple[Decimal, ...] = (Decimal("1.0"), Decimal("1.5"), Decimal("2.0"))

MAX_DRAWDOWN = 0.15  # go-live #4; equals the threshold in metrics.checklist
MIN_PROFIT_FACTOR = 1.3  # go-live #3; equals the threshold in metrics.checklist

_GATE_NAMES = ("beating total-return SPY", "profit factor ≥ 1.3", "max drawdown ≤ 15%")


def grid() -> tuple[AParams, ...]:
    """The 81 parameter sets: RSI → limit → TP → SL, each ascending (SL varies fastest).

    ``min_dollar_volume`` stays at the design value. ``DESIGN_PARAMS`` is entry 40 (0-based).
    """
    return tuple(
        AParams(rsi_max=rsi, limit_atr=limit, tp_atr=tp, sl_atr=sl)
        for rsi in GRID_RSI
        for limit in GRID_LIMIT
        for tp in GRID_TP
        for sl in GRID_SL
    )


@dataclass(frozen=True)
class GridRow:
    params: AParams
    metrics: Metrics  # in-sample


@dataclass(frozen=True)
class Selection:
    params: AParams
    qualified: bool  # False: no run qualified and the design values were kept
    reason: str


@dataclass(frozen=True)
class Verdict:
    passed: bool
    checks: tuple[CheckItem, ...]  # checklist items "Beats SPY", "Profit factor ≥ 1.3", "Max drawdown ≤ 15%"
    sentence: str


def qualifies(m: Metrics) -> bool:
    """A grid run may be selected only if max DD ≤ 15% and PF ≥ 1.3 (infinite PF qualifies)."""
    return (
        m.total_return is not None
        and m.max_drawdown is not None
        and m.max_drawdown <= MAX_DRAWDOWN
        and m.profit_factor is not None
        and m.profit_factor >= MIN_PROFIT_FACTOR
    )


def select(rows: Sequence[GridRow]) -> Selection:
    """The qualifying row with the highest in-sample total return.

    Ties go to the lower max drawdown, then to the earlier grid index. When no row qualifies,
    ``DESIGN_PARAMS`` is kept with ``qualified=False``.
    """
    n = len(rows)
    candidates = [(i, row) for i, row in enumerate(rows) if qualifies(row.metrics)]
    if not candidates:
        return Selection(
            params=DESIGN_PARAMS,
            qualified=False,
            reason=(
                f"No in-sample grid run had max drawdown ≤ 15% and profit factor ≥ 1.3 (0 of {n}), "
                "so the design values are kept."
            ),
        )
    best_i, best = min(
        candidates,
        key=lambda c: (-c[1].metrics.total_return, c[1].metrics.max_drawdown, c[0]),
    )
    tied = 0
    for _, row in candidates:
        if row.metrics.total_return == best.metrics.total_return:
            tied += 1
    reason = (
        f"Grid run #{best_i + 1} has the highest in-sample total return "
        f"({fmt_signed_pct(best.metrics.total_return)}, max drawdown {fmt_pct(best.metrics.max_drawdown)}) "
        f"among the {len(candidates)} of {n} runs with max drawdown ≤ 15% and profit factor ≥ 1.3"
    )
    if tied > 1:
        reason += f"; {tied} runs tied on return, broken by the lower max drawdown, then grid order"
    return Selection(params=best.params, qualified=True, reason=reason + ".")


def _join(items: Sequence[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def gate(oos: Metrics, spy_tr_oos: Metrics) -> Verdict:
    """The P3 gate, decided by out-of-sample results only.

    It passes when total return > total-return SPY (strict), profit factor ≥ 1.3 and max
    drawdown ≤ 15%. The checks are ``checklist`` items 3–5, so the labels and value strings
    match the web.
    """
    beats, pf, dd = checklist(oos, spy_tr_oos.total_return)[2:5]
    checks = (beats, pf, dd)
    passed = beats.ok and pf.ok and dd.ok
    said = (
        f"out of sample it returned {fmt_signed_pct(oos.total_return)} against "
        f"{fmt_signed_pct(spy_tr_oos.total_return)} for total-return SPY, with profit factor "
        f"{pf.val} and max drawdown {dd.val}"
    )
    if passed:
        sentence = f"Strategy A passes the P3 gate: {said}."
    else:
        failed = [name for name, item in zip(_GATE_NAMES, checks) if not item.ok]
        sentence = (
            f"Strategy A fails the P3 gate: {said}, so it fails on {_join(failed)}; "
            "P4 must not start until Strategy A is reworked."
        )
    return Verdict(passed=passed, checks=checks, sentence=sentence)
```

**Impact:** a new module.

### Step 3: `report.py`

**File:** `engine/src/seer_engine/backtest/report.py:1` (new)

**Change:** pure rendering, with fixed section order. All numbers go through `to_fixed`, `str(int)`
or `format(Decimal, ...)`, so the output is the same on every platform. SVG coordinates go through
`f"{x:.1f}"`; Python formats floats with correct rounding, so equal floats give equal text.
`_validate` refuses a report whose window runs did not use `selection.params`, or whose curves do
not line up date for date.

Markdown sections, in order:

1. Title
2. Gate verdict sentence (top)
3. `## Data` (provenance: data end, bar rows, symbols with bars, never-fetched members, windows
   with sessions, USD/IDR and starting cash)
4. `## Method`
5. `## In-sample grid` (every row)
6. `## Selection` (reason, design vs selected vs frozen table, the two machine lines, the
   "frozen in code" sentence)
7. `## Results`, with one `###` per window: strategy vs SPY price-only vs SPY total-return.
   Rows: ending equity, total return, CAGR, win rate, PF, max DD, trades, avg days held, four
   exit reasons, forced closes, open at end, months, SPY shares, dividends. Then the simulator
   rejections line.
8. `## Go-live checklist`: the backtest-evaluable items, with IS/OOS/full side by side and #5
   tied to the gate
9. `## Survivorship bias` (plain words + per-year table + totals)
10. `## Open positions at end` (per window)
11. `## Equity curves` (SVG embed + CSV link)
12. `## Gate verdict` (sentence + the three checks)

A Markdown code fence cannot appear literally inside this plan's Python block, so the code builds
it as `FENCE = "`" * 3`.

**Code:**

```python
"""Backtest report rendering: Markdown, a wide CSV and a self-contained SVG.

Pure: takes a ``BacktestReport`` value and returns text. Phase 5's ``io.write_report`` writes
the files. Everything is deterministic (invariant 5):
- numbers go through ``metrics.to_fixed`` (exact decimal rounding), ``str(int)`` or ``format``
  of a ``Decimal``
- SVG coordinates are ``f"{x:.1f}"`` of floats computed the same way every time
- iteration is in tuple order or in sorted order

Two lines are machine-readable, each exactly once, on its own line:
``frozen-params: <json.dumps(report.frozen_params.as_dict())>`` and
``selected-params: <json.dumps(report.selection.params.as_dict())>``. Phase 6's
test_strategy_a_frozen.py reads them back. Only those two lines and the one "Frozen in code"
sentence depend on ``frozen_params``. Every number comes from the runs, which must all have used
``selection.params``.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from seer_engine.backtest.benchmark import BenchmarkCurve
from seer_engine.backtest.metrics import (
    DASH,
    EXIT_REASONS,
    Metrics,
    checklist,
    curve_metrics,
    fmt_num,
    fmt_pct,
    fmt_pf,
    fmt_signed_pct,
    forced_closes,
    run_metrics,
    to_fixed,
)
from seer_engine.backtest.runner import INITIAL_IDR, RunResult, YearGap
from seer_engine.backtest.tuning import (
    GRID_LIMIT,
    GRID_RSI,
    GRID_SL,
    GRID_TP,
    GridRow,
    Selection,
    Verdict,
    qualifies,
)
from seer_engine.sim import Order, Snapshot
from seer_engine.strategies.a import DESIGN_PARAMS, AParams

FROZEN_KEY = "frozen-params"
SELECTED_KEY = "selected-params"
FENCE = "`" * 3

_EXIT_LABELS = {
    "tp": "Exits: take profit",
    "sl": "Exits: stop loss",
    "time": "Exits: time stop",
    "gap": "Exits: gap at the open",
}


# --------------------------------------------------------------------------- values


@dataclass(frozen=True)
class WindowResult:
    name: str  # "In-sample" | "Out-of-sample" | "Full window"
    run: RunResult
    spy_price: BenchmarkCurve
    spy_tr: BenchmarkCurve


@dataclass(frozen=True)
class BacktestReport:
    data_end: date
    bars_rows: int
    symbols_with_bars: int
    grid_rows: tuple[GridRow, ...]
    selection: Selection
    frozen_params: AParams  # STRATEGY_A_PARAMS at run time; rendered only in its own two lines
    in_sample: WindowResult
    out_of_sample: WindowResult
    full: WindowResult
    survivorship: tuple[YearGap, ...]
    never_fetched_members: int
    verdict: Verdict

    def windows(self) -> tuple[WindowResult, WindowResult, WindowResult]:
        return (self.in_sample, self.out_of_sample, self.full)


def report_stem(data_end: date) -> str:
    """File stem for one data end date: ``<data_end>-strategy-a``."""
    return f"{data_end.isoformat()}-strategy-a"


# --------------------------------------------------------------------------- machine lines


def params_line(key: str, params: AParams) -> str:
    """``<key>: <json.dumps(params.as_dict())>``, keys in ``as_dict`` order (never sorted)."""
    return f"{key}: {json.dumps(params.as_dict())}"


def parse_params_line(markdown: str, key: str) -> dict[str, str]:
    """The JSON object on the single ``<key>: {...}`` line; ValueError unless exactly one exists."""
    found = re.findall(rf"^{re.escape(key)}: (\{{.*\}})$", markdown, flags=re.MULTILINE)
    if len(found) != 1:
        raise ValueError(f"expected exactly one '{key}:' line, found {len(found)}")
    value = json.loads(found[0])
    if not isinstance(value, dict):
        raise ValueError(f"'{key}:' is not a JSON object: {found[0]!r}")
    return value


# --------------------------------------------------------------------------- validation


def _check_aligned(name: str, curves: Sequence[Sequence[Snapshot]]) -> None:
    lengths = {len(c) for c in curves}
    if len(lengths) != 1:
        raise ValueError(f"{name}: curves have different lengths {[len(c) for c in curves]}")
    if not curves[0]:
        raise ValueError(f"{name}: curves are empty")
    for i, snaps in enumerate(zip(*curves)):
        dates = [s.date for s in snaps]
        if any(d != dates[0] for d in dates):
            raise ValueError(f"{name}: snapshot {i} dates differ {dates}")


def _validate(report: BacktestReport) -> None:
    for w in report.windows():
        if w.run.params != report.selection.params:
            raise ValueError(
                f"{w.name}: run used {w.run.params!r}, not the selection {report.selection.params!r}"
            )
        _check_aligned(w.name, (w.run.snapshots, w.spy_price.snapshots, w.spy_tr.snapshots))


# --------------------------------------------------------------------------- markdown helpers


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def _table(header: Sequence[str], align: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    """A GitHub table; ``align`` is ``"l"`` or ``"r"`` per column."""
    lines = [
        "| " + " | ".join(_cell(h) for h in header) + " |",
        "|" + "|".join("---:" if a == "r" else ":---" for a in align) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_cell(c) for c in row) + " |")
    return lines


def _usd(d: Decimal) -> str:
    return format(d, ",.2f")


def _span(run: RunResult) -> str:
    return f"{run.start.isoformat()} → {run.end.isoformat()}"


def _sessions(run: RunResult) -> int:
    return len(run.snapshots) - 1  # snapshots[0] is the starting cash on the session before


def _plain(values: Sequence[float | Decimal]) -> str:
    return ", ".join(format(v, "g") if isinstance(v, float) else str(v) for v in values)


def _pass(ok: bool) -> str:
    return "pass" if ok else "fail"


# --------------------------------------------------------------------------- sections


def _data_section(report: BacktestReport) -> list[str]:
    rows = [
        [
            w.name,
            _span(w.run),
            f"{_sessions(w.run):,}",
            format(w.run.usd_idr, ",.4f"),
            _usd(w.run.initial_cash),
        ]
        for w in report.windows()
    ]
    return [
        "## Data",
        "",
        f"- Data end (last bar loaded): {report.data_end.isoformat()}",
        f"- Bar rows loaded: {report.bars_rows:,}",
        f"- Symbols with bars: {report.symbols_with_bars:,}",
        f"- Index members in the window with no bars at all: {report.never_fetched_members:,}",
        "",
        *_table(
            ["Window", "Dates", "Sessions", "USD/IDR at start", "Starting cash (USD)"],
            ["l", "l", "r", "r", "r"],
            rows,
        ),
        "",
    ]


def _method_section(report: BacktestReport) -> list[str]:
    design = DESIGN_PARAMS.as_dict()
    return [
        "## Method",
        "",
        "- **Strategy A** (design §4): a setup needs close > SMA(200), Wilder RSI(2) < `rsi_max` and "
        "20-session mean close × volume > `min_dollar_volume` "
        f"(design: RSI < {design['rsi_max']}, ${design['min_dollar_volume']}). "
        "Limit = close − `limit_atr` × ATR(14), TP = limit + `tp_atr` × ATR(14), "
        "SL = limit − `sl_atr` × ATR(14), each to 4 dp. Candidates are ranked by RSI(2) ascending, "
        "with the symbol breaking ties.",
        "- **No look-ahead.** Picks for session S use bars through the previous session only. "
        "The universe is S&P 500 ∪ Nasdaq-100 members on that data date (point in time).",
        "- **One simulator.** Every size, fill, exit and cost (0.1% per side, whole shares, 4 slots) "
        f"comes from `seer_engine.sim`, unchanged. Each window is a fresh portfolio of "
        f"{INITIAL_IDR:,} IDR converted at the start date's USD/IDR rate. A held symbol whose bars "
        "end for good is closed at its last close (a forced `time` exit).",
        "- **SPY benchmarks.** Buy whole shares at the first session's open after the 0.1% cost, "
        "hold, and mark at each close. Price-only ignores dividends. Total-return reinvests each "
        "dividend at the ex-date close (whole shares, with cost). At the end of a window, open "
        "positions and the SPY holding are both marked at the last close and never sold.",
        "- **Metrics** follow `web/lib/metrics.ts`:",
        "  - Total return = last / first equity − 1. Every curve starts at the starting cash on "
        "the session before the window.",
        "  - A win is P/L > 0 and a loss is P/L ≤ 0. Profit factor = gross win / gross loss "
        "(∞ with no loss).",
        "  - Max drawdown is measured on per-session equity. Months = calendar days / 30.44.",
        "  - CAGR = (last / first)^(1 / years) − 1, with years = calendar days between the first "
        "and last snapshot / 365.25 (Actual/365.25).",
        "  - Avg days held is the mean of the simulator's `days_held` over closed trades.",
        f"- **Tuning.** The grid is RSI {{{_plain(GRID_RSI)}}} × limit {{{_plain(GRID_LIMIT)}}} × "
        f"TP {{{_plain(GRID_TP)}}} × SL {{{_plain(GRID_SL)}}} ATR, and it runs on the in-sample "
        "window only.",
        "  - Selection takes the highest in-sample total return among runs with max drawdown ≤ 15% "
        "and profit factor ≥ 1.3. Ties go to the lower max drawdown, then to grid order. If no "
        "run qualifies, the design values are kept.",
        "  - The out-of-sample window runs once, with the selected parameters, and its numbers "
        "never feed back into the selection.",
        "- **Gate.** Passes only if, out of sample, total return > total-return SPY, profit "
        "factor ≥ 1.3 and max drawdown ≤ 15%. In-sample numbers never decide it.",
        "",
    ]


def _grid_section(report: BacktestReport) -> list[str]:
    sel = report.selection
    selected_index = next((i for i, r in enumerate(report.grid_rows) if r.params == sel.params), None)
    rows: list[list[str]] = []
    for i, row in enumerate(report.grid_rows):
        p = row.params.as_dict()
        m = row.metrics
        mark = ""
        if i == selected_index:
            mark = "selected" if sel.qualified else "kept (fallback)"
        rows.append(
            [
                str(i + 1),
                p["rsi_max"],
                p["limit_atr"],
                p["tp_atr"],
                p["sl_atr"],
                fmt_signed_pct(m.total_return),
                fmt_signed_pct(m.cagr),
                fmt_pct(m.win_rate),
                fmt_pf(m.profit_factor),
                fmt_pct(m.max_drawdown),
                str(m.trades),
                "yes" if qualifies(m) else "no",
                mark,
            ]
        )
    return [
        f"## In-sample grid ({len(report.grid_rows)} runs, {_span(report.in_sample.run)})",
        "",
        "Every grid run, in grid order, on the in-sample window. A run qualifies when max "
        "drawdown ≤ 15% and profit factor ≥ 1.3. Selection reads these numbers and nothing else.",
        "",
        *_table(
            [
                "#",
                "RSI(2) <",
                "Limit ×ATR",
                "TP ×ATR",
                "SL ×ATR",
                "Total return",
                "CAGR",
                "Win rate",
                "Profit factor",
                "Max drawdown",
                "Trades",
                "Qualifies",
                "Selected",
            ],
            ["r"] * 11 + ["l", "l"],
            rows,
        ),
        "",
    ]


def _selection_section(report: BacktestReport) -> list[str]:
    design = DESIGN_PARAMS.as_dict()
    selected = report.selection.params.as_dict()
    frozen = report.frozen_params.as_dict()
    rows = [[k, design[k], selected[k], frozen.get(k, DASH)] for k in selected]
    if report.frozen_params == report.selection.params:
        frozen_note = "Frozen in code (`STRATEGY_A_PARAMS`): matches the selection."
    else:
        frozen_note = (
            "Frozen in code (`STRATEGY_A_PARAMS`): differs from the selection. Set it to the "
            "selection and re-run the backtest."
        )
    return [
        "## Selection",
        "",
        report.selection.reason,
        "",
        *_table(["Parameter", "Design", "Selected", "Frozen in code"], ["l", "r", "r", "r"], rows),
        "",
        frozen_note,
        "",
        FENCE + "text",
        params_line(FROZEN_KEY, report.frozen_params),
        params_line(SELECTED_KEY, report.selection.params),
        FENCE,
        "",
    ]


def _results_table(w: WindowResult) -> list[str]:
    sm = run_metrics(w.run)
    pm = curve_metrics(w.spy_price)
    tm = curve_metrics(w.spy_tr)
    reasons = dict(sm.exit_reasons)
    rows: list[list[str]] = [
        [
            "Ending equity (USD)",
            _usd(w.run.snapshots[-1].equity_usd),
            _usd(w.spy_price.snapshots[-1].equity_usd),
            _usd(w.spy_tr.snapshots[-1].equity_usd),
        ],
        ["Total return", fmt_signed_pct(sm.total_return), fmt_signed_pct(pm.total_return), fmt_signed_pct(tm.total_return)],
        ["CAGR", fmt_signed_pct(sm.cagr), fmt_signed_pct(pm.cagr), fmt_signed_pct(tm.cagr)],
        ["Win rate", fmt_pct(sm.win_rate), DASH, DASH],
        ["Profit factor", fmt_pf(sm.profit_factor), DASH, DASH],
        ["Max drawdown", fmt_pct(sm.max_drawdown), fmt_pct(pm.max_drawdown), fmt_pct(tm.max_drawdown)],
        ["Trades (closed)", str(sm.trades), DASH, DASH],
        ["Avg days held", fmt_num(sm.avg_days_held), DASH, DASH],
    ]
    for reason in EXIT_REASONS:
        rows.append([_EXIT_LABELS[reason], str(reasons.get(reason, 0)), DASH, DASH])
    rows += [
        ["Forced closes (bars ended; inside time stop)", str(forced_closes(w.run)), DASH, DASH],
        ["Open at end", str(len(w.run.open_at_end)), DASH, DASH],
        ["Months", fmt_num(sm.months, 1), fmt_num(pm.months, 1), fmt_num(tm.months, 1)],
        ["SPY shares at end", DASH, str(w.spy_price.shares), str(w.spy_tr.shares)],
        ["SPY dividends credited (USD)", DASH, DASH, _usd(w.spy_tr.dividends_usd)],
    ]
    rejected = ", ".join(f"{reason} {count:,}" for reason, count in w.run.rejections) or "none"
    return [
        f"### {w.name} ({_span(w.run)}, {_sessions(w.run):,} sessions)",
        "",
        *_table(["Metric", "Strategy A", "SPY price-only", "SPY total-return"], ["l", "r", "r", "r"], rows),
        "",
        f"Picks the simulator rejected: {rejected}.",
        "",
    ]


def _results_section(report: BacktestReport) -> list[str]:
    out = [
        "## Results",
        "",
        "In-sample shows the tuned parameters on the data they were tuned on, which is not "
        "evidence. Out-of-sample is the honest test. The full window is one continuous "
        "portfolio over both.",
        "",
    ]
    for w in report.windows():
        out += _results_table(w)
    return out


_CHECK_NOTES = (
    "#1, forward-only: information",
    "#1, forward-only: information",
    "#2, in the gate (vs total-return SPY)",
    "#3, in the gate",
    "#4, in the gate",
)


def _checklist_section(report: BacktestReport) -> list[str]:
    per_window = [
        checklist(run_metrics(w.run), curve_metrics(w.spy_tr).total_return) for w in report.windows()
    ]
    rows: list[list[str]] = []
    for k, note in enumerate(_CHECK_NOTES):
        label = per_window[0][k].label
        rows.append([label, note] + [f"{_pass(items[k].ok)}: {items[k].val}" for items in per_window])
    rows.append(
        [
            "Passed a 10-year backtest under identical rules",
            "#5, decided by the gate",
            DASH,
            f"{_pass(report.verdict.passed)}: gate verdict",
            DASH,
        ]
    )
    names = [w.name for w in report.windows()]
    return [
        "## Go-live checklist (what a backtest can evaluate)",
        "",
        "These are design §1's fixed rules, computed exactly as the web computes them. The "
        "\"months forward\" and \"100 trades\" items need forward paper trading, so here they are "
        "information only. \"Beats SPY\" compares with total-return SPY.",
        "",
        *_table(["Item", "Design §1", *names], ["l", "l", "l", "l", "l"], rows),
        "",
    ]


def _survivorship_section(report: BacktestReport) -> list[str]:
    rows: list[list[str]] = []
    tot_member = tot_missing = tot_never = tot_other = 0
    for g in report.survivorship:
        rows.append(
            [
                str(g.year),
                f"{g.member_sessions:,}",
                f"{g.missing:,}",
                f"{g.missing_never_fetched:,}",
                f"{g.missing_other:,}",
                fmt_pct(g.missing / g.member_sessions, 2) if g.member_sessions else DASH,
            ]
        )
        tot_member += g.member_sessions
        tot_missing += g.missing
        tot_never += g.missing_never_fetched
        tot_other += g.missing_other
    rows.append(
        [
            "All",
            f"{tot_member:,}",
            f"{tot_missing:,}",
            f"{tot_never:,}",
            f"{tot_other:,}",
            fmt_pct(tot_missing / tot_member, 2) if tot_member else DASH,
        ]
    )
    return [
        "## Survivorship bias",
        "",
        "This backtest can only trade stocks that still have price data. "
        f"{report.never_fetched_members:,} stocks were in the S&P 500 or the Nasdaq-100 at some "
        "point in the window, but they have no price data at all. They were delisted or bought "
        "out, and the free data source no longer serves them.",
        "",
        "On the days they were index members, Strategy A could not see them. So it never had the "
        "chance to buy one of them on the way down. A dip-buying strategy is exactly the kind "
        "that such collapses would have hurt. **These results are therefore probably better than "
        "reality**, by an amount this data cannot measure.",
        "",
        "The table counts, per year, the (member, session) pairs with no bar:",
        "",
        "- \"Never fetched\" are members with no bars at all.",
        "- \"Other\" are members that have bars elsewhere but none on that session, such as "
        "halts or the days before a listing.",
        "",
        *_table(
            ["Year", "Member-sessions", "Missing", "Never fetched", "Other", "Missing share"],
            ["l", "r", "r", "r", "r", "r"],
            rows,
        ),
        "",
    ]


def _order_row(o: Order) -> list[str]:
    return [
        o.symbol,
        o.status,
        str(o.slot),
        o.session_date.isoformat(),
        o.fill_date.isoformat() if o.fill_date is not None else DASH,
        str(o.fill_price) if o.fill_price is not None else DASH,
        str(o.shares),
        str(o.limit_price),
        str(o.tp_price),
        str(o.sl_price),
        str(o.days_held),
    ]


def _open_positions_section(report: BacktestReport) -> list[str]:
    out = [
        "## Open positions at end",
        "",
        "Positions still live after a window's last session are marked at that close and never "
        "sold, the same treatment as the SPY holding.",
        "",
    ]
    for w in report.windows():
        out += [f"### {w.name}", ""]
        if not w.run.open_at_end:
            out += ["None.", ""]
            continue
        out += _table(
            ["Symbol", "Status", "Slot", "Session", "Filled", "Fill price", "Shares", "Limit", "TP", "SL", "Days held"],
            ["l", "l", "r", "l", "l", "r", "r", "r", "r", "r", "r"],
            [_order_row(o) for o in w.run.open_at_end],
        )
        out.append("")
    return out


def _curves_section(report: BacktestReport) -> list[str]:
    stem = report_stem(report.data_end)
    return [
        "## Equity curves",
        "",
        f"![Strategy A vs SPY price-only and SPY total-return, full window]({stem}-equity.svg)",
        "",
        f"The daily values for the full window are in [`{stem}-equity.csv`]({stem}-equity.csv).",
        "",
    ]


def _verdict_section(report: BacktestReport) -> list[str]:
    out = ["## Gate verdict", "", report.verdict.sentence, ""]
    for c in report.verdict.checks:
        out.append(f"- {c.label}: {_pass(c.ok)} ({c.val})")
    out.append("")
    return out


def render_markdown(report: BacktestReport) -> str:
    """The full report as Markdown, ending in exactly one newline."""
    _validate(report)
    out: list[str] = [
        f"# Strategy A backtest, data through {report.data_end.isoformat()}",
        "",
        f"**Gate verdict:** {report.verdict.sentence}",
        "",
    ]
    out += _data_section(report)
    out += _method_section(report)
    out += _grid_section(report)
    out += _selection_section(report)
    out += _results_section(report)
    out += _checklist_section(report)
    out += _survivorship_section(report)
    out += _open_positions_section(report)
    out += _curves_section(report)
    out += _verdict_section(report)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- CSV


def equity_csv(report: BacktestReport) -> str:
    """Wide daily CSV of the full window: ``date,strategy_a,spy_price,spy_tr`` (USD, 4 dp)."""
    _validate(report)
    w = report.full
    lines = ["date,strategy_a,spy_price,spy_tr"]
    for a, p, t in zip(w.run.snapshots, w.spy_price.snapshots, w.spy_tr.snapshots):
        lines.append(f"{a.date.isoformat()},{a.equity_usd:f},{p.equity_usd:f},{t.equity_usd:f}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- SVG

_SVG_W = 960
_SVG_H = 460
_ML, _MR, _MT, _MB = 80, 190, 80, 40
_LABEL_GAP = 15.0
_SERIES = (("s1", "Strategy A"), ("s2", "SPY price-only"), ("s3", "SPY total-return"))
_SVG_STYLE = (
    ".bg{fill:#fcfcfb}.t1{fill:#0b0b0b}.t2{fill:#52514e}"
    ".grid{stroke:#e6e5e0;stroke-width:1}.axis{stroke:#a3a29c;stroke-width:1}"
    ".line{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}"
    ".s1{stroke:#2a78d6}.s2{stroke:#eb6834;stroke-dasharray:6 4}.s3{stroke:#1baf7a}"
    "@media (prefers-color-scheme: dark){"
    ".bg{fill:#1a1a19}.t1{fill:#ffffff}.t2{fill:#c3c2b7}"
    ".grid{stroke:#33322f}.axis{stroke:#6b6a64}"
    ".s1{stroke:#3987e5}.s2{stroke:#d95926}.s3{stroke:#199e70}}"
)


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _nice_ticks(lo: float, hi: float, target: int = 5) -> tuple[list[float], float]:
    """Round y ticks covering ``[lo, hi]``, with a step of 1, 2, 2.5 or 5 × 10^k."""
    if hi <= lo:
        hi = lo + 1.0
    raw = (hi - lo) / target
    mag = 10.0 ** math.floor(math.log10(raw))
    step = 10.0 * mag
    for m in (1.0, 2.0, 2.5, 5.0, 10.0):
        if m * mag >= raw:
            step = m * mag
            break
    first = math.floor(lo / step)
    last = math.ceil(hi / step)
    return [k * step for k in range(first, last + 1)], step


def _tick_label(v: float, step: float) -> str:
    decimals = 0 if step >= 1 and float(step).is_integer() else 2
    return f"${v:,.{decimals}f}"


def equity_svg(report: BacktestReport) -> str:
    """The full window's three equity curves as one self-contained SVG.

    It has light and dark palettes through ``prefers-color-scheme``, an opaque background,
    a legend, direct end labels and no script.
    """
    _validate(report)
    w = report.full
    curves = (w.run.snapshots, w.spy_price.snapshots, w.spy_tr.snapshots)
    dates = [s.date for s in curves[0]]
    span = (dates[-1] - dates[0]).days
    if span <= 0:
        raise ValueError("the full window needs snapshots on at least two different dates")
    values = [[float(s.equity_usd) for s in c] for c in curves]
    ticks, step = _nice_ticks(min(min(v) for v in values), max(max(v) for v in values))
    lo, hi = ticks[0], ticks[-1]
    pw = _SVG_W - _ML - _MR
    ph = _SVG_H - _MT - _MB
    bottom = _MT + ph

    def px(d: date) -> float:
        return _ML + (d - dates[0]).days / span * pw

    def py(v: float) -> float:
        return _MT + (hi - v) / (hi - lo) * ph

    returns = (
        run_metrics(w.run).total_return,
        curve_metrics(w.spy_price).total_return,
        curve_metrics(w.spy_tr).total_return,
    )
    title = f"Strategy A vs SPY, full window {_span(w.run)}"
    subtitle = (
        f"Equity in USD from {_usd(curves[0][0].equity_usd)} on {dates[0].isoformat()}; "
        "0.1% cost per side; marked at each close."
    )
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_SVG_W} {_SVG_H}" '
        f'width="{_SVG_W}" height="{_SVG_H}" role="img" aria-labelledby="title desc" '
        'font-family="system-ui, -apple-system, Segoe UI, Helvetica, Arial, sans-serif">',
        f'<title id="title">{_esc(title)}</title>',
        '<desc id="desc">Line chart of daily equity in USD for Strategy A, SPY price-only and '
        "SPY total-return over the full window. The values are in the CSV next to this file.</desc>",
        f"<style>{_SVG_STYLE}</style>",
        f'<rect class="bg" x="0" y="0" width="{_SVG_W}" height="{_SVG_H}"/>',
        f'<text class="t1" x="{_ML}" y="24" font-size="16" font-weight="600">{_esc(title)}</text>',
        f'<text class="t2" x="{_ML}" y="42" font-size="12">{_esc(subtitle)}</text>',
    ]
    legend_x = _ML
    for cls, label in _SERIES:
        out.append(f'<line class="line {cls}" x1="{legend_x}" y1="60" x2="{legend_x + 22}" y2="60"/>')
        out.append(f'<text class="t2" x="{legend_x + 28}" y="64" font-size="12">{_esc(label)}</text>')
        legend_x += 170
    for t in ticks:
        y = py(t)
        out.append(f'<line class="grid" x1="{_ML}" y1="{y:.1f}" x2="{_ML + pw}" y2="{y:.1f}"/>')
        out.append(
            f'<text class="t2" x="{_ML - 8}" y="{y + 4:.1f}" font-size="11" text-anchor="end">'
            f"{_esc(_tick_label(t, step))}</text>"
        )
    out.append(f'<line class="axis" x1="{_ML}" y1="{bottom}" x2="{_ML + pw}" y2="{bottom}"/>')
    for year in range(dates[0].year + 1, dates[-1].year + 1):
        d = date(year, 1, 1)
        if not dates[0] < d <= dates[-1]:
            continue
        x = px(d)
        out.append(f'<line class="axis" x1="{x:.1f}" y1="{bottom}" x2="{x:.1f}" y2="{bottom + 5}"/>')
        out.append(
            f'<text class="t2" x="{x:.1f}" y="{bottom + 20}" font-size="11" text-anchor="middle">{year}</text>'
        )
    for (cls, label), vals in zip(_SERIES, values):
        points = " ".join(f"{px(d):.1f},{py(v):.1f}" for d, v in zip(dates, vals))
        out.append(f'<polyline class="line {cls}" points="{points}"><title>{_esc(label)}</title></polyline>')
    ends = sorted((py(vals[-1]), i) for i, vals in enumerate(values))
    placed: list[tuple[int, float]] = []
    prev = -math.inf
    for y, i in ends:
        y = max(y, prev + _LABEL_GAP)
        placed.append((i, y))
        prev = y
    x0 = _ML + pw + 8
    for i, y in sorted(placed):
        cls, label = _SERIES[i]
        out.append(f'<line class="line {cls}" x1="{x0}" y1="{y:.1f}" x2="{x0 + 14}" y2="{y:.1f}"/>')
        out.append(
            f'<text class="t1" x="{x0 + 18}" y="{y + 4:.1f}" font-size="11">'
            f"{_esc(label)} {_esc(fmt_signed_pct(returns[i]))}</text>"
        )
    out.append("</svg>")
    return "\n".join(out) + "\n"
```

**Impact:** a new module. Phase 5's `io.write_report` calls `render_markdown`, `equity_csv`,
`equity_svg` and `report_stem`.

The palette is the dataviz reference categorical slots 1–3 (blue, orange, aqua). Those slots pass
the validator in both modes on the `--pairs all` list. Because the price-only line is also
dashed, color is never the only thing that identifies a series. Text uses ink colors, never
series colors.

### Step 4: `test_backtest_metrics.py`

**File:** `engine/tests/test_backtest_metrics.py:1` (new)

**Change:** the tests below.

- Every `web/lib/metrics.test.ts` case, with the same inputs. Snaps are dated 2026-07-01 + i,
  exactly like the TS helper. The tests use the same tolerances: `toBeCloseTo(x)` means
  `abs < 0.005`, and `toBeCloseTo(x, 1)` means `abs < 0.05`. They also assert exact float
  equality with the JS expression, and the checklist `label`/`val` strings, which were checked
  with node 20 on 2026-10-03.
- JS `toFixed` reference values, also produced with node.
- Left-to-right summation.
- CAGR.
- Days held, exit reasons and forced closes on a hand-built `RunResult`.
- `curve_metrics` on a hand-built `BenchmarkCurve`.

**Code:**

```python
"""Backtest metrics: parity with web/lib/metrics.ts (handover §6 item 6) plus CAGR, days held
and exit reasons. Every expected string was produced by node 20 from metrics.ts's own code."""

from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import Decimal

import pytest

from seer_engine.backtest.benchmark import BenchmarkCurve
from seer_engine.backtest.metrics import (
    DASH,
    INFINITY,
    MINUS,
    Metrics,
    avg_days_held,
    cagr_between,
    checklist,
    curve_metrics,
    exit_reason_counts,
    fmt_pct,
    fmt_pf,
    fmt_signed_pct,
    forced_closes,
    run_metrics,
    strategy_metrics,
    to_fixed,
)
from seer_engine.backtest.runner import RunResult
from seer_engine.sim import Event, Order, Snapshot

D = date.fromisoformat


def snaps(vals):
    """metrics.test.ts ``snaps``: equity i dated 2026-07-01 + i (UTC)."""
    return [(date(2026, 7, 1) + timedelta(days=i), float(v)) for i, v in enumerate(vals)]


# --------------------------------------------------------------------------- parity: strategyMetrics


def test_parity_computes_return_win_rate_profit_factor_drawdown_and_trades():
    m = strategy_metrics(snaps([1000, 1100, 990, 1050]), [30, -10, 20, -10])
    assert m.total_return == pytest.approx(0.05, abs=0.005)
    assert m.win_rate == pytest.approx(0.5, abs=0.005)
    assert m.profit_factor == pytest.approx(2.5, abs=0.005)
    assert m.max_drawdown == pytest.approx(0.1, abs=0.005)  # 1100 -> 990
    assert m.trades == 4
    # bit-exact with JS (node: 1050/1000-1, (1100-990)/1100, 50/20)
    assert m.total_return == 0.050000000000000044
    assert m.max_drawdown == 0.1
    assert m.profit_factor == 2.5
    assert m.win_rate == 0.5


def test_parity_returns_nulls_with_no_data():
    m = strategy_metrics([], [])
    assert m.total_return is None
    assert m.win_rate is None
    assert m.profit_factor is None
    assert m.max_drawdown is None
    assert m.trades == 0
    assert m.months == 0
    assert m.cagr is None


def test_parity_infinite_profit_factor_when_nothing_lost():
    assert strategy_metrics(snaps([1, 2]), [5]).profit_factor == math.inf


def test_parity_measures_months_of_forward_testing():
    m = strategy_metrics([(D("2026-07-06"), 1.0), (D("2026-10-05"), 1.0)], [])
    assert m.months == pytest.approx(3.0, abs=0.05)
    assert m.months == 2.9894875164257555  # node: (Date.parse(b)-Date.parse(a))/86400000/30.44


def test_zero_pnl_is_a_loss_like_the_web():
    m = strategy_metrics(snaps([1, 1]), [0.0])
    assert m.win_rate == 0.0
    assert m.profit_factor == math.inf  # grossLoss is -0, and -0 === 0


def test_sums_run_left_to_right_like_reduce():
    m = strategy_metrics(snaps([1, 1]), [0.1, 0.2, 0.3, -0.3])
    assert m.profit_factor == ((0.0 + 0.1 + 0.2) + 0.3) / 0.3
    assert m.profit_factor == 2.0000000000000004  # math.fsum would give exactly 2.0


# --------------------------------------------------------------------------- parity: checklist


BASE = Metrics(total_return=0.068, win_rate=0.58, profit_factor=1.42, max_drawdown=0.079, trades=84, months=3.0)


def test_parity_checklist_passes_only_when_every_rule_holds():
    items = checklist(BASE, 0.046)
    assert [i.ok for i in items] == [True, False, True, True, True]
    assert items[1].val == "84 / 100"
    assert all(i.ok for i in checklist(Metrics(**{**BASE.__dict__, "trades": 120}), 0.046))
    assert checklist(Metrics(**{**BASE.__dict__, "max_drawdown": 0.16, "trades": 120}), 0.046)[4].ok is False


def test_parity_checklist_labels_and_values_match_the_web_strings():
    items = checklist(BASE, 0.046)
    assert [(i.label, i.val) for i in items] == [
        ("≥ 3 months forward", "3.0 mo"),
        ("≥ 100 trades", "84 / 100"),
        ("Beats SPY", "+6.8 vs +4.6"),
        ("Profit factor ≥ 1.3", "1.42"),
        ("Max drawdown ≤ 15%", "7.9%"),
    ]


def test_checklist_edge_strings():
    m = Metrics(total_return=-0.0123, win_rate=None, profit_factor=None, max_drawdown=None, trades=0, months=91 / 30.44)
    items = checklist(m, None)
    assert items[0].val == "2.9 mo" and items[0].ok is False  # floor to 0.1, like the web
    assert items[2].val == DASH and items[2].ok is False
    assert items[3].val == DASH and items[3].ok is False
    assert items[4].val == DASH and items[4].ok is False
    assert checklist(m, 0.0)[2].val == f"{MINUS}1.2 vs +0.0"
    inf = Metrics(total_return=0.2, win_rate=1.0, profit_factor=math.inf, max_drawdown=0.15, trades=1, months=1.0)
    items = checklist(inf, 0.2)
    assert items[3].val == INFINITY and items[3].ok is True
    assert items[4].val == "15.0%" and items[4].ok is True  # ≤ is inclusive
    assert items[2].ok is False  # beats SPY is strict
    assert checklist(Metrics(**{**inf.__dict__, "profit_factor": 1.3}), 0.1)[3].ok is True


def test_checklist_total_return_none_counts_as_zero_in_the_value_but_never_beats():
    m = Metrics(total_return=None, win_rate=None, profit_factor=None, max_drawdown=None, trades=0, months=0.0)
    item = checklist(m, -0.5)[2]
    assert item.val == f"+0.0 vs {MINUS}50.0"
    assert item.ok is False


# --------------------------------------------------------------------------- toFixed port


@pytest.mark.parametrize(
    ("x", "digits", "js"),
    [  # every right-hand side printed by node 20
        (0.125, 2, "0.13"),
        (2.5, 0, "3"),
        (1.005, 2, "1.00"),
        (-0.04, 1, "-0.0"),
        (-0.0, 1, "0.0"),
        (8.345, 2, "8.35"),
        (1.45, 1, "1.4"),
        (0.079 * 100, 1, "7.9"),
        (abs(0.068 * 100), 1, "6.8"),
        (0.16 * 100, 1, "16.0"),
        (0, 2, "0.00"),
    ],
)
def test_to_fixed_matches_javascript(x, digits, js):
    assert to_fixed(x, digits) == js


def test_to_fixed_refuses_what_js_would_not_print_plainly():
    for bad in (math.inf, math.nan, 1e21):
        with pytest.raises(ValueError):
            to_fixed(bad, 1)
    with pytest.raises(TypeError):
        to_fixed(Decimal("1.5"), 1)  # type: ignore[arg-type]


def test_formatters():
    assert fmt_signed_pct(0.068) == "+6.8%"
    assert fmt_signed_pct(-0.0123) == f"{MINUS}1.2%"
    assert fmt_signed_pct(None) == DASH
    assert fmt_pct(0.079) == "7.9%"
    assert fmt_pct(0.012, 2) == "1.20%"
    assert fmt_pf(math.inf) == INFINITY
    assert fmt_pf(None) == DASH
    assert fmt_pf(1.425) == "1.43"  # node: (1.425).toFixed(2)


# --------------------------------------------------------------------------- CAGR


def test_cagr_is_actual_365_25():
    first, last = (D("2020-01-01"), 100.0), (D("2021-01-01"), 121.0)  # 366 days
    assert cagr_between(first, last) == (121.0 / 100.0) ** (1.0 / (366 / 365.25)) - 1.0
    two_years = cagr_between((D("2019-01-01"), 1.0), (D("2021-01-01"), 4.0))  # 731 days
    assert two_years == pytest.approx(1.0, abs=0.002)


def test_cagr_undefined_cases():
    assert cagr_between((D("2020-01-01"), 1.0), (D("2020-01-01"), 2.0)) is None
    assert cagr_between((D("2020-01-01"), 0.0), (D("2021-01-01"), 2.0)) is None
    assert cagr_between((D("2020-01-01"), 1.0), (D("2021-01-01"), -1.0)) is None
    assert cagr_between((D("2020-01-01"), 1.0), (D("2021-01-01"), 0.0)) == -1.0
    assert strategy_metrics(snaps([1000]), []).cagr is None  # a single snapshot spans 0 days


def test_strategy_metrics_fills_cagr_from_the_same_snapshots():
    m = strategy_metrics([(D("2020-01-01"), 100.0), (D("2020-07-01"), 90.0), (D("2021-01-01"), 121.0)], [])
    assert m.cagr == cagr_between((D("2020-01-01"), 100.0), (D("2021-01-01"), 121.0))


# --------------------------------------------------------------------------- run / curve metrics


def _closed(symbol, slot, reason, pnl, days):
    return Order(
        session_date=D("2026-07-01"),
        slot=slot,
        symbol=symbol,
        last_price=Decimal("10.0000"),
        limit_price=Decimal("9.5000"),
        tp_price=Decimal("10.5000"),
        sl_price=Decimal("8.7500"),
        shares=10,
        status="closed",
        fill_date=D("2026-07-01"),
        fill_price=Decimal("9.5000"),
        days_held=days,
        exit_date=D("2026-07-03"),
        exit_price=Decimal("10.5000"),
        exit_reason=reason,
        pnl_usd=Decimal(pnl),
    )


def _run(closed, events=()):
    s = [Snapshot(d, Decimal(e), Decimal(e)) for d, e in [
        (D("2026-07-01"), "1000.0000"),
        (D("2026-07-02"), "1100.0000"),
        (D("2026-07-03"), "990.0000"),
        (D("2026-07-04"), "1050.0000"),
    ]]
    return RunResult(
        strategy_id="A",
        params=None,
        start=D("2026-07-02"),
        end=D("2026-07-04"),
        usd_idr=Decimal("16000.0000"),
        initial_cash=Decimal("1000.0000"),
        snapshots=tuple(s),
        events=tuple(events),
        closed=tuple(closed),
        open_at_end=(),
        rejections=(),
    )


def test_run_metrics_matches_strategy_metrics_and_adds_days_and_reasons():
    closed = [
        _closed("AAA", 1, "tp", "30.0000", 2),
        _closed("BBB", 2, "sl", "-10.0000", 3),
        _closed("CCC", 3, "time", "20.0000", 5),
        _closed("DDD", 4, "tp", "-10.0000", 1),
    ]
    forced = Event(D("2026-07-03"), "exit", closed[2], forced=True, cash_usd=Decimal("104.8950"))
    normal = Event(D("2026-07-03"), "exit", closed[0], forced=False, cash_usd=Decimal("104.8950"))
    r = _run(closed, events=(normal, forced))
    m = run_metrics(r)
    web = strategy_metrics(snaps([1000, 1100, 990, 1050]), [30, -10, 20, -10])
    assert (m.total_return, m.win_rate, m.profit_factor, m.max_drawdown, m.trades, m.months) == (
        web.total_return, web.win_rate, web.profit_factor, web.max_drawdown, web.trades, web.months,
    )
    assert m.avg_days_held == 2.75
    assert m.exit_reasons == (("tp", 2), ("sl", 1), ("time", 1), ("gap", 0))
    assert forced_closes(r) == 1


def test_run_metrics_with_no_trades():
    m = run_metrics(_run([]))
    assert m.trades == 0 and m.win_rate is None and m.profit_factor is None
    assert m.avg_days_held is None
    assert m.exit_reasons == (("tp", 0), ("sl", 0), ("time", 0), ("gap", 0))
    assert avg_days_held([]) is None
    assert exit_reason_counts([]) == (("tp", 0), ("sl", 0), ("time", 0), ("gap", 0))


def test_curve_metrics_has_no_trades():
    c = BenchmarkCurve(
        name="spy_tr",
        snapshots=(
            Snapshot(D("2026-07-01"), Decimal("1000.0000"), Decimal("1000.0000")),
            Snapshot(D("2026-07-02"), Decimal("1.0000"), Decimal("1020.0000")),
            Snapshot(D("2026-07-03"), Decimal("1.0000"), Decimal("1010.0000")),
        ),
        shares=2,
        cash=Decimal("1.0000"),
        dividends_usd=Decimal("0.0000"),
    )
    m = curve_metrics(c)
    assert m.total_return == 1010.0 / 1000.0 - 1
    assert m.max_drawdown == (1020.0 - 1010.0) / 1020.0
    assert m.trades == 0 and m.profit_factor is None and m.win_rate is None
    assert m.exit_reasons == () and m.avg_days_held is None
```

**Impact:** new tests. Every JS reference string in them (including `(1.425).toFixed(2) == "1.43"`)
was printed by node 20 while this plan was written.

### Step 5: `test_backtest_tuning.py`

**File:** `engine/tests/test_backtest_tuning.py:1` (new)

**Code:**

```python
"""Grid, in-sample selection and the P3 gate (handover §3 "Tuning" and "Gate verdict")."""

from __future__ import annotations

import itertools
import math
from datetime import date
from decimal import Decimal

from seer_engine import dates
from seer_engine.backtest.metrics import MINUS, Metrics, checklist
from seer_engine.backtest.tuning import (
    GRID_LIMIT,
    GRID_RSI,
    GRID_SL,
    GRID_TP,
    IS_START,
    MAX_DRAWDOWN,
    MIN_PROFIT_FACTOR,
    OOS_START,
    GridRow,
    gate,
    grid,
    qualifies,
    select,
)
from seer_engine.strategies.a import DESIGN_PARAMS, AParams


def M(ret, pf=1.5, dd=0.10, trades=120):
    return Metrics(total_return=ret, win_rate=0.6, profit_factor=pf, max_drawdown=dd, trades=trades, months=70.0)


def rows_with(*metrics):
    g = grid()
    return [GridRow(params=g[i], metrics=m) for i, m in enumerate(metrics)]


# --------------------------------------------------------------------------- constants and grid


def test_windows():
    assert IS_START == date(2015, 10, 19)
    assert OOS_START == date(2022, 1, 3)
    assert dates.prev_session(OOS_START) == date(2021, 12, 31)


def test_grid_is_the_declared_81_in_nested_order():
    g = grid()
    assert len(g) == 81
    assert len(set(g)) == 81
    expected = [
        (r, l, t, s) for r, l, t, s in itertools.product(GRID_RSI, GRID_LIMIT, GRID_TP, GRID_SL)
    ]
    assert [(p.rsi_max, p.limit_atr, p.tp_atr, p.sl_atr) for p in g] == expected
    assert (g[0].rsi_max, g[0].limit_atr, g[0].tp_atr, g[0].sl_atr) == (5.0, Decimal("0.25"), Decimal("0.75"), Decimal("1.0"))
    assert (g[1].sl_atr, g[3].tp_atr, g[9].limit_atr, g[27].rsi_max) == (Decimal("1.5"), Decimal("1.0"), Decimal("0.5"), 10.0)
    assert g[40] == DESIGN_PARAMS
    assert all(p.min_dollar_volume == DESIGN_PARAMS.min_dollar_volume for p in g)
    assert grid() == g  # deterministic


def test_grid_values_are_the_handover_values():
    assert GRID_RSI == (5.0, 10.0, 15.0)
    assert GRID_LIMIT == (Decimal("0.25"), Decimal("0.5"), Decimal("0.75"))
    assert GRID_TP == (Decimal("0.75"), Decimal("1.0"), Decimal("1.5"))
    assert GRID_SL == (Decimal("1.0"), Decimal("1.5"), Decimal("2.0"))


def test_thresholds_equal_the_web_checklist():
    edge = Metrics(total_return=0.1, win_rate=0.5, profit_factor=MIN_PROFIT_FACTOR, max_drawdown=MAX_DRAWDOWN, trades=1, months=1.0)
    items = checklist(edge, 0.0)
    assert items[3].ok and items[4].ok
    below = Metrics(total_return=0.1, win_rate=0.5, profit_factor=math.nextafter(MIN_PROFIT_FACTOR, 0), max_drawdown=math.nextafter(MAX_DRAWDOWN, 1), trades=1, months=1.0)
    items = checklist(below, 0.0)
    assert not items[3].ok and not items[4].ok
    assert qualifies(edge) and not qualifies(below)


# --------------------------------------------------------------------------- selection


def test_select_takes_the_highest_return_among_qualified_runs():
    rows = rows_with(
        M(0.30, dd=0.16),  # higher return, drawdown too deep
        M(0.25, pf=1.29),  # profit factor too low
        M(0.20),
        M(0.22, pf=math.inf),  # no loss: qualifies
        M(0.10),
    )
    s = select(rows)
    assert s.qualified is True
    assert s.params == grid()[3]
    assert s.reason.startswith("Grid run #4 has the highest in-sample total return (+22.0%")
    assert "among the 3 of 5 runs" in s.reason
    assert "tied" not in s.reason


def test_select_boundaries_are_inclusive():
    s = select(rows_with(M(0.05, pf=1.3, dd=0.15)))
    assert s.qualified and s.params == grid()[0]


def test_select_ties_break_by_lower_drawdown_then_grid_order():
    s = select(rows_with(M(0.2, dd=0.12), M(0.2, dd=0.08), M(0.2, dd=0.08)))
    assert s.params == grid()[1]
    assert "3 runs tied on return" in s.reason


def test_select_negative_returns_still_pick_the_least_bad_qualified_run():
    s = select(rows_with(M(-0.05), M(-0.02), M(-0.10)))
    assert s.params == grid()[1]
    assert f"({MINUS}2.0%" in s.reason


def test_select_falls_back_to_design_values_when_nothing_qualifies():
    s = select(rows_with(M(0.5, dd=0.2), M(0.4, pf=1.0), M(0.3, pf=None, trades=0)))
    assert s.qualified is False
    assert s.params == DESIGN_PARAMS
    assert s.reason == (
        "No in-sample grid run had max drawdown ≤ 15% and profit factor ≥ 1.3 (0 of 3), "
        "so the design values are kept."
    )
    assert select([]).params == DESIGN_PARAMS


def test_select_is_deterministic():
    rows = rows_with(*(M(0.01 * (i % 7), dd=0.05 + 0.001 * i) for i in range(81)))
    assert select(rows) == select(list(rows))


# --------------------------------------------------------------------------- gate


def spy(ret):
    return Metrics(total_return=ret, win_rate=None, profit_factor=None, max_drawdown=0.25, trades=0, months=57.0)


def test_gate_passes_only_when_all_three_hold():
    v = gate(M(0.40, pf=1.45, dd=0.098), spy(0.35))
    assert v.passed is True
    assert [c.label for c in v.checks] == ["Beats SPY", "Profit factor ≥ 1.3", "Max drawdown ≤ 15%"]
    assert v.sentence == (
        "Strategy A passes the P3 gate: out of sample it returned +40.0% against +35.0% for "
        "total-return SPY, with profit factor 1.45 and max drawdown 9.8%."
    )


def test_gate_fails_on_each_condition_alone():
    assert gate(M(0.30), spy(0.35)).passed is False
    assert gate(M(0.35), spy(0.35)).passed is False  # strict: a tie does not beat SPY
    assert gate(M(0.40, pf=1.29), spy(0.35)).passed is False
    assert gate(M(0.40, dd=0.151), spy(0.35)).passed is False
    assert gate(M(0.40, pf=None, trades=0), spy(0.35)).passed is False
    assert gate(M(0.40), spy(None)).passed is False


def test_gate_failure_sentence_names_every_failed_check_and_stops_p4():
    v = gate(M(-0.032, pf=1.10, dd=0.12), spy(0.401))
    assert v.passed is False
    assert v.sentence == (
        f"Strategy A fails the P3 gate: out of sample it returned {MINUS}3.2% against +40.1% for "
        "total-return SPY, with profit factor 1.10 and max drawdown 12.0%, so it fails on "
        "beating total-return SPY and profit factor ≥ 1.3; P4 must not start until Strategy A is reworked."
    )
    v3 = gate(M(-0.1, pf=1.0, dd=0.3), spy(0.1))
    assert "fails on beating total-return SPY, profit factor ≥ 1.3 and max drawdown ≤ 15%;" in v3.sentence


def test_gate_accepts_an_infinite_profit_factor():
    v = gate(M(0.4, pf=math.inf), spy(0.1))
    assert v.passed and v.checks[1].val == "∞"


def test_gate_and_select_see_only_their_own_window():
    # Structural guard for invariant 6: neither takes the other window's data.
    import inspect

    assert list(inspect.signature(select).parameters) == ["rows"]
    assert list(inspect.signature(gate).parameters) == ["oos", "spy_tr_oos"]


def test_aparams_in_grid_construct_with_decimal_offsets():
    for p in grid():
        assert isinstance(p, AParams)
        assert isinstance(p.limit_atr, Decimal) and isinstance(p.tp_atr, Decimal) and isinstance(p.sl_atr, Decimal)
```

**Impact:** new tests. `M(0.3, pf=None, trades=0)` passes `pf=None` on purpose.

### Step 6: `test_backtest_report.py`

**File:** `engine/tests/test_backtest_report.py:1` (new)

**Change:** builds a small synthetic `BacktestReport` from hand-built `RunResult`,
`BenchmarkCurve` and `YearGap` values:

- 81 grid rows with synthetic metrics
- the selection
- the verdict from `gate`

**Code:**

```python
"""Report rendering (handover §6 items 6, 7, 9): deterministic, every section, the machine lines,
CSV and SVG, all from a small synthetic BacktestReport."""

from __future__ import annotations

import dataclasses
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal

import pytest

from seer_engine.backtest.benchmark import BenchmarkCurve
from seer_engine.backtest.metrics import Metrics, curve_metrics, run_metrics
from seer_engine.backtest.report import (
    FROZEN_KEY,
    SELECTED_KEY,
    BacktestReport,
    WindowResult,
    equity_csv,
    equity_svg,
    params_line,
    parse_params_line,
    render_markdown,
    report_stem,
)
from seer_engine.backtest.runner import RunResult, YearGap
from seer_engine.backtest.tuning import GridRow, gate, grid, select
from seer_engine.sim import Event, Order, Snapshot
from seer_engine.strategies.a import DESIGN_PARAMS

D = date.fromisoformat
CASH0 = "1250.0000"
FULL_DATES = ["2021-12-29", "2021-12-30", "2021-12-31", "2022-01-03", "2022-01-04", "2022-01-05"]
STRAT = [CASH0, "1262.5000", "1240.0000", "1255.0000", "1270.0000", "1280.0000"]
SPY_P = [CASH0, "1251.0000", "1249.0000", "1253.0000", "1252.0000", "1256.0000"]
SPY_T = [CASH0, "1251.0000", "1249.5000", "1254.0000", "1253.5000", "1258.0000"]


def _snaps(ds, vals):
    return tuple(Snapshot(D(d), Decimal(v), Decimal(v)) for d, v in zip(ds, vals))


def _order(symbol, slot, status, reason=None, pnl=None, days=0):
    filled = status in ("open", "closed")
    return Order(
        session_date=D("2021-12-30"),
        slot=slot,
        symbol=symbol,
        last_price=Decimal("10.0000"),
        limit_price=Decimal("9.5000"),
        tp_price=Decimal("10.5000"),
        sl_price=Decimal("8.7500"),
        shares=10,
        status=status,
        fill_date=D("2021-12-30") if filled else None,
        fill_price=Decimal("9.5000") if filled else None,
        days_held=days if filled else 0,
        exit_date=D("2022-01-03") if status == "closed" else None,
        exit_price=Decimal("10.5000") if status == "closed" else None,
        exit_reason=reason,
        pnl_usd=Decimal(pnl) if pnl is not None else None,
    )


def _run(ds, vals, params, closed=(), events=(), open_at_end=(), rejections=()):
    return RunResult(
        strategy_id="A",
        params=params,
        start=D(ds[1]),
        end=D(ds[-1]),
        usd_idr=Decimal("16000.0000"),
        initial_cash=Decimal(CASH0),
        snapshots=_snaps(ds, vals),
        events=tuple(events),
        closed=tuple(closed),
        open_at_end=tuple(open_at_end),
        rejections=tuple(rejections),
    )


def _curve(name, ds, vals, dividends="0.0000"):
    return BenchmarkCurve(
        name=name,
        snapshots=_snaps(ds, vals),
        shares=2,
        cash=Decimal("12.3400"),
        dividends_usd=Decimal(dividends),
    )


def _window(name, lo, hi, params, **run_kw):
    ds, s, p, t = FULL_DATES[lo:hi], STRAT[lo:hi], SPY_P[lo:hi], SPY_T[lo:hi]
    s = [CASH0] + s[1:]
    p = [CASH0] + p[1:]
    t = [CASH0] + t[1:]
    return WindowResult(
        name=name,
        run=_run(ds, s, params, **run_kw),
        spy_price=_curve("spy_price", ds, p),
        spy_tr=_curve("spy_tr", ds, t, dividends="1.5000"),
    )


def _grid_rows():
    return tuple(
        GridRow(
            params=p,
            metrics=Metrics(
                total_return=0.01 * i - 0.2,
                win_rate=0.5,
                profit_factor=1.0 + 0.01 * i,
                max_drawdown=0.10 + (0.1 if i % 2 else 0.0),
                trades=100 + i,
                months=74.0,
                cagr=0.001 * i,
                avg_days_held=2.5,
                exit_reasons=(("tp", 1), ("sl", 1), ("time", 0), ("gap", 0)),
            ),
        )
        for i, p in enumerate(grid())
    )


def build_report(frozen=None):
    rows = _grid_rows()
    selection = select(rows)
    params = selection.params
    closed = (
        _order("AAA", 1, "closed", "tp", "30.0000", 2),
        _order("CCC", 2, "closed", "time", "-10.0000", 3),
    )
    forced = Event(D("2022-01-03"), "exit", closed[1], forced=True, cash_usd=Decimal("94.8950"))
    full = _window(
        "Full window", 0, 6, params,
        closed=closed, events=(forced,),
        open_at_end=(_order("BBB", 3, "open", days=2),),
        rejections=(("held", 1), ("no_slot", 2)),
    )
    ins = _window("In-sample", 0, 3, params)
    oos = _window("Out-of-sample", 2, 6, params, closed=closed[:1])
    verdict = gate(run_metrics(oos.run), curve_metrics(oos.spy_tr))
    return BacktestReport(
        data_end=D("2026-10-02"),
        bars_rows=1_817_429,
        symbols_with_bars=663,
        grid_rows=rows,
        selection=selection,
        frozen_params=DESIGN_PARAMS if frozen is None else frozen,
        in_sample=ins,
        out_of_sample=oos,
        full=full,
        survivorship=(
            YearGap(year=2021, member_sessions=1000, missing=12, missing_never_fetched=10, missing_other=2),
            YearGap(year=2022, member_sessions=500, missing=0, missing_never_fetched=0, missing_other=0),
        ),
        never_fetched_members=133,
        verdict=verdict,
    )


def _section(md: str, heading: str) -> str:
    start = md.index(heading)
    nxt = md.find("\n## ", start + 1)
    return md[start: nxt if nxt != -1 else len(md)]


# --------------------------------------------------------------------------- basics


def test_report_stem():
    assert report_stem(D("2026-10-02")) == "2026-10-02-strategy-a"


def test_selection_in_fixture_is_the_last_qualifying_row():
    r = build_report()
    assert r.selection.qualified and r.selection.params == grid()[80]


def test_outputs_are_deterministic():
    a, b = build_report(), build_report()
    assert render_markdown(a) == render_markdown(b)
    assert equity_csv(a) == equity_csv(b)
    assert equity_svg(a) == equity_svg(b)
    assert render_markdown(a) == render_markdown(a)


# --------------------------------------------------------------------------- markdown


def test_markdown_contains_every_required_section_in_order():
    md = render_markdown(build_report())
    headings = [
        "# Strategy A backtest, data through 2026-10-02",
        "**Gate verdict:** ",
        "## Data",
        "## Method",
        "## In-sample grid (81 runs, 2021-12-30 → 2021-12-31)",
        "## Selection",
        "## Results",
        "### In-sample (2021-12-30 → 2021-12-31, 2 sessions)",
        "### Out-of-sample (2022-01-03 → 2022-01-05, 3 sessions)",
        "### Full window (2021-12-30 → 2022-01-05, 5 sessions)",
        "## Go-live checklist (what a backtest can evaluate)",
        "## Survivorship bias",
        "## Open positions at end",
        "## Equity curves",
        "## Gate verdict",
    ]
    positions = [md.index(h) for h in headings]
    assert positions == sorted(positions)
    assert md.endswith("\n") and not md.endswith("\n\n")
    assert "nan" not in md.lower().replace("financ", "")


def test_markdown_data_provenance():
    md = _section(render_markdown(build_report()), "## Data")
    assert "- Data end (last bar loaded): 2026-10-02" in md
    assert "- Bar rows loaded: 1,817,429" in md
    assert "- Symbols with bars: 663" in md
    assert "| Full window | 2021-12-30 → 2022-01-05 | 5 | 16,000.0000 | 1,250.00 |" in md


def test_markdown_method_states_cagr_convention_and_grid():
    md = _section(render_markdown(build_report()), "## Method")
    assert "Actual/365.25" in md
    assert "RSI {5, 10, 15} × limit {0.25, 0.5, 0.75} × TP {0.75, 1.0, 1.5} × SL {1.0, 1.5, 2.0} ATR" in md
    assert "20,000,000 IDR" in md


def test_markdown_lists_all_81_grid_rows_in_order():
    sec = _section(render_markdown(build_report()), "## In-sample grid")
    rows = [line for line in sec.splitlines() if line[:3].strip("| ").isdigit()]
    assert [int(line.split("|")[1]) for line in rows] == list(range(1, 82))
    assert rows[80].endswith("| yes | selected |")
    assert rows[1].endswith("| no |  |")  # odd rows have drawdown 0.20
    assert sum(1 for line in rows if line.endswith("| selected |")) == 1


def test_markdown_grid_marks_the_fallback():
    r = build_report()
    rows = tuple(GridRow(params=g.params, metrics=dataclasses.replace(g.metrics, max_drawdown=0.5)) for g in r.grid_rows)
    sel = select(rows)
    assert sel.params == DESIGN_PARAMS and not sel.qualified
    windows = {
        k: dataclasses.replace(w, run=dataclasses.replace(w.run, params=DESIGN_PARAMS))
        for k, w in (("in_sample", r.in_sample), ("out_of_sample", r.out_of_sample), ("full", r.full))
    }
    md = render_markdown(dataclasses.replace(r, grid_rows=rows, selection=sel, **windows))
    assert "| kept (fallback) |" in _section(md, "## In-sample grid")
    assert sel.reason in md


def test_machine_lines_round_trip():
    r = build_report()
    md = render_markdown(r)
    assert parse_params_line(md, FROZEN_KEY) == DESIGN_PARAMS.as_dict()
    assert parse_params_line(md, SELECTED_KEY) == r.selection.params.as_dict()
    assert list(parse_params_line(md, SELECTED_KEY)) == list(r.selection.params.as_dict())  # key order kept
    assert md.count("\nfrozen-params: ") == 1 and md.count("\nselected-params: ") == 1
    assert params_line(FROZEN_KEY, DESIGN_PARAMS) in md.splitlines()
    assert "differs from the selection" in md


def test_frozen_params_change_only_their_own_lines():
    a = render_markdown(build_report()).splitlines()
    r = build_report()
    b = render_markdown(build_report(frozen=r.selection.params)).splitlines()
    changed = [(x, y) for x, y in zip(a, b) if x != y]
    assert len(a) == len(b)
    assert all(
        x.startswith("frozen-params: ") or x.startswith("Frozen in code") or x.startswith("| ")
        for x, _ in changed
    )
    assert len(changed) == 2 + sum(
        1 for k in DESIGN_PARAMS.as_dict() if DESIGN_PARAMS.as_dict()[k] != r.selection.params.as_dict()[k]
    )
    assert "matches the selection" in "\n".join(b)


def test_parse_params_line_needs_exactly_one():
    with pytest.raises(ValueError):
        parse_params_line("nothing here\n", FROZEN_KEY)
    line = params_line(FROZEN_KEY, DESIGN_PARAMS)
    with pytest.raises(ValueError):
        parse_params_line(f"{line}\n{line}\n", FROZEN_KEY)


def test_markdown_window_tables():
    md = _section(render_markdown(build_report()), "## Results")
    assert md.count("| Metric | Strategy A | SPY price-only | SPY total-return |") == 3
    full = md[md.index("### Full window"):]
    assert "| Ending equity (USD) | 1,280.00 | 1,256.00 | 1,258.00 |" in full
    assert "| Total return | +2.4% | +0.5% | +0.6% |" in full
    assert "| Trades (closed) | 2 | — | — |" in full
    assert "| Avg days held | 2.50 | — | — |" in full
    assert "| Exits: take profit | 1 | — | — |" in full
    assert "| Exits: time stop | 1 | — | — |" in full
    assert "| Exits: gap at the open | 0 | — | — |" in full
    assert "| Forced closes (bars ended; inside time stop) | 1 | — | — |" in full
    assert "| Open at end | 1 | — | — |" in full
    assert "| SPY dividends credited (USD) | — | — | 1.50 |" in full
    assert "Picks the simulator rejected: held 1, no_slot 2." in full
    for row in ("| CAGR |", "| Win rate |", "| Profit factor |", "| Max drawdown |"):
        assert row in full


def test_markdown_checklist_has_the_backtest_items():
    md = _section(render_markdown(build_report()), "## Go-live checklist")
    for label in ("≥ 3 months forward", "≥ 100 trades", "Beats SPY", "Profit factor ≥ 1.3", "Max drawdown ≤ 15%"):
        assert f"| {label} |" in md
    assert "| Passed a 10-year backtest under identical rules | #5, decided by the gate |" in md
    assert "forward-only: information" in md


def test_markdown_survivorship_in_plain_words_with_per_year_gaps():
    md = _section(render_markdown(build_report()), "## Survivorship bias")
    assert "133 stocks were in the S&P 500 or the Nasdaq-100" in md
    assert "probably better than reality" in md
    assert "| 2021 | 1,000 | 12 | 10 | 2 | 1.20% |" in md
    assert "| 2022 | 500 | 0 | 0 | 0 | 0.00% |" in md
    assert "| All | 1,500 | 12 | 10 | 2 | 0.80% |" in md


def test_markdown_open_positions():
    md = _section(render_markdown(build_report()), "## Open positions at end")
    assert "| BBB | open | 3 | 2021-12-30 | 2021-12-30 | 9.5000 | 10 | 9.5000 | 10.5000 | 8.7500 | 2 |" in md
    assert md.count("None.") == 2  # in-sample and out-of-sample hold nothing


def test_markdown_verdict_sentence_twice_and_checks():
    r = build_report()
    md = render_markdown(r)
    assert md.count(r.verdict.sentence) == 2
    assert md.startswith(f"# Strategy A backtest, data through 2026-10-02\n\n**Gate verdict:** {r.verdict.sentence}\n")
    v = _section(md, "## Gate verdict")
    assert "- Beats SPY: " in v and "- Profit factor ≥ 1.3: " in v and "- Max drawdown ≤ 15%: " in v


def test_markdown_links_the_curve_files():
    md = render_markdown(build_report())
    assert "](2026-10-02-strategy-a-equity.svg)" in md
    assert "(2026-10-02-strategy-a-equity.csv)" in md


def test_render_refuses_runs_not_on_the_selection():
    r = build_report()
    bad = dataclasses.replace(r.out_of_sample, run=dataclasses.replace(r.out_of_sample.run, params=grid()[0]))
    with pytest.raises(ValueError, match="Out-of-sample"):
        render_markdown(dataclasses.replace(r, out_of_sample=bad))


def test_render_refuses_misaligned_curves():
    r = build_report()
    short = dataclasses.replace(r.full.spy_tr, snapshots=r.full.spy_tr.snapshots[:-1])
    bad = dataclasses.replace(r, full=dataclasses.replace(r.full, spy_tr=short))
    for fn in (render_markdown, equity_csv, equity_svg):
        with pytest.raises(ValueError, match="Full window"):
            fn(bad)


# --------------------------------------------------------------------------- CSV


def test_equity_csv_is_the_full_window_wide():
    assert equity_csv(build_report()) == (
        "date,strategy_a,spy_price,spy_tr\n"
        "2021-12-29,1250.0000,1250.0000,1250.0000\n"
        "2021-12-30,1262.5000,1251.0000,1251.0000\n"
        "2021-12-31,1240.0000,1249.0000,1249.5000\n"
        "2022-01-03,1255.0000,1253.0000,1254.0000\n"
        "2022-01-04,1270.0000,1252.0000,1253.5000\n"
        "2022-01-05,1280.0000,1256.0000,1258.0000\n"
    )


# --------------------------------------------------------------------------- SVG


def test_equity_svg_is_self_contained_and_themed():
    svg = equity_svg(build_report())
    root = ET.fromstring(svg.encode("utf-8"))
    ns = "{http://www.w3.org/2000/svg}"
    assert root.tag == f"{ns}svg"
    assert root.get("viewBox") == "0 0 960 460"
    lines = root.findall(f"{ns}polyline")
    assert [pl.get("class") for pl in lines] == ["line s1", "line s2", "line s3"]
    assert all(len(pl.get("points").split()) == 6 for pl in lines)
    style = root.find(f"{ns}style").text
    assert "@media (prefers-color-scheme: dark)" in style
    assert root.find(f"{ns}rect").get("class") == "bg"
    assert "<script" not in svg and "href" not in svg
    assert "nan" not in svg.lower() and "inf" not in svg.lower()
    texts = [t.text for t in root.iter(f"{ns}text")]
    assert "2022" in texts  # one year tick inside the window
    assert any(t and t.startswith("Strategy A +2.4%") for t in texts)
    assert any(t and t.startswith("SPY price-only") for t in texts)
    assert any(t and t.startswith("SPY total-return") for t in texts)


def test_equity_svg_needs_two_dates():
    r = build_report()
    one = lambda c: dataclasses.replace(c, snapshots=c.snapshots[:1])  # noqa: E731
    full = dataclasses.replace(
        r.full,
        run=dataclasses.replace(r.full.run, snapshots=r.full.run.snapshots[:1]),
        spy_price=one(r.full.spy_price),
        spy_tr=one(r.full.spy_tr),
    )
    with pytest.raises(ValueError):
        equity_svg(dataclasses.replace(r, full=full))
```

**Impact:** new tests. Three of the hand-computed strings in these tests are worth checking
before running:

- Full window total return: 1280 / 1250 − 1 = 0.024, printed as `+2.4%`.
- SPY price-only: 1256 / 1250 − 1 = 0.0048. `to_fixed(0.48, 1)` gives `0.5`.
- SPY total-return: 1258 / 1250 − 1 = 0.0064, printed as `+0.6%`.

`avg_days_held = (2 + 3) / 2 = 2.5`, printed as `2.50`.

The "nan" check in the SVG is a substring check on lowercase text. `inf` must not appear because
every curve has a total return. The words in the SVG ("Line chart ...", "information") do not
contain `inf`, but this must be verified when implementing. If `desc` ever gains a word containing
"inf", narrow the check to `">inf"` and `"nan,"`.

## Verification

**Build:** `engine/.venv/bin/python -c "import seer_engine.backtest.metrics, seer_engine.backtest.tuning, seer_engine.backtest.report"`
**Tests:** `docker start seer-pg; PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`
(run it from the worktree root, with the worktree's own venv)
**Phase-focused:** `engine/.venv/bin/pytest engine/tests/test_backtest_metrics.py engine/tests/test_backtest_tuning.py engine/tests/test_backtest_report.py engine/tests/test_strategy_purity.py -q`
**Manual checks:**

- Check the parity strings against the web code:
  `node -e 'const p1=(v)=>(v>=0?"+":"−")+Math.abs(v*100).toFixed(1);console.log(p1(0.068),p1(0.046),(0.079*100).toFixed(1),(1.42).toFixed(2),(1.425).toFixed(2))'`.
  The expected output is `+6.8 +4.6 7.9 1.42 1.43`.
- Write the synthetic SVG to the scratchpad once and open it in a browser in light and in dark
  mode to look for label collisions. Do this from a throwaway Python snippet, not from a test.
  Pure modules never write files.

**Exit criteria:**

- All three new test files pass: **67 tests** (`test_backtest_metrics.py` 29, `test_backtest_tuning.py` 16,
  `test_backtest_report.py` 22).
- `test_strategy_purity.py` (phase 1, which globs `backtest/*.py` except `io.py`) passes with the
  three new modules: they have no `open`/`print`/`logging`/`time`/clock attributes.
- The full suite is green with 0 skipped: **570 passed** (503 after phases 1–3 + 67), measured by
  the reconciler with phases 1–4 applied to a scratch copy.
- `render_markdown`, `equity_csv` and `equity_svg` are byte-identical across two builds of the
  same report.

## Handoffs

- **Phase 5 (R5/R6).**
  - Build `BacktestReport` with:
    - `frozen_params=STRATEGY_A_PARAMS`
    - all three `WindowResult.run`s run on `selection.params` (otherwise `render_markdown` raises)
    - `verdict=gate(run_metrics(oos.run), curve_metrics(oos.spy_tr))`
    - window names `"In-sample"`, `"Out-of-sample"`, `"Full window"`
  - `io.write_report` writes `render_markdown`/`equity_csv`/`equity_svg` to `<stem>.md`,
    `<stem>-equity.csv` and `<stem>-equity.svg`, with `stem = report_stem(data_end)`. Each is
    written UTF-8 with `newline=""` or as bytes, so the `\n` line endings survive.
  - `GridRow.metrics` must be `run_metrics(grid_run)`.
- **Phase 6 (R4/R5/R6).**
  - Parse with `report.parse_params_line(text, FROZEN_KEY)` and
    `parse_params_line(text, SELECTED_KEY)` (reconciled: phase 6's test uses exactly these, no regex of its own). Both lines are
    plain, unindented, inside a fenced `text` block, and appear exactly once each.
  - Before freezing, the `.md` diff between two runs is limited to the `frozen-params:` line, the
    "Frozen in code" sentence and the "Frozen in code" column of the selection table.
  - The selection table's "Frozen in code" column also derives from `frozen_params`, so its
    rows for the parameters that differ change too. **Reconciled: the column stays**; phase 6
    Step 5's byte-diff expectation now lists it (index Decisions "Pre/post-freeze report diff").
    `test_frozen_params_change_only_their_own_lines` pins exactly this set of changed lines.
- **Phase 1 (R1).**
  - `AParams.as_dict()` must use exactly the keys `rsi_max`, `limit_atr`, `tp_atr`, `sl_atr`,
    `min_dollar_volume`, in that order. The grid table indexes the first four.
  - `AParams` must stay hashable (`frozen=True`), because `test_grid_is_the_declared_81_in_nested_order`
    uses `set(grid())`.
- **Phase 6 readme** documents:
  - the CAGR convention (Actual/365.25, from the starting-cash snapshot)
  - that `to_fixed` mirrors JS `toFixed`
  - the machine lines
- Not done here (no requirement in scope): a per-year return table and a drawdown chart. Both
  would be useful later; they are not in handover §6, so they are not added.

## Rollback

Delete the six new files, or `git revert` the phase's commit. No other file changes, so nothing
else needs undoing. Phase 5 imports these modules, so roll it back first if it has landed.
