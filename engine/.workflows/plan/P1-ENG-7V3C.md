> Adopted from `ROSTER_PROMOTION_PIPELINE_PLAN.md` phase 3. Source: `.workflows/plan/roster-promotion-pipeline/phase-3.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 3: Common-window, risk-adjusted comparison over `equity_snapshots`

**Plan set:** `ROSTER_PROMOTION_PIPELINE_PLAN.md`
**Analysis:** `20261005-165054-XGER_code_analyzer.md`
**Satisfies:** R3 — "a robust pipeline to easily compare and 're-sort' the current SEER's four horsemen"
**Depends on:** none (runs concurrently with phase 1)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/paper`

---

## Runtime preamble

Verbatim from the index. Every command below assumes it.

```bash
export SEER_WT=/home/miftah/.worktrees/seer/roster-promotion-pipeline
export SEER_PY=/home/miftah/seer/engine/.venv/bin/python
export PYTHONPATH=$SEER_WT/engine/src                        # wins over the editable .pth
export SEER_MAIN=/home/miftah/seer
export SEER_ENV_FILE=$SEER_MAIN/.env.local-train             # ABSOLUTE, always
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
cd "$SEER_WT"
"$SEER_PY" -c 'import seer_engine, pathlib; print(pathlib.Path(seer_engine.__file__).resolve())'
# must print $SEER_WT/engine/src/seer_engine/__init__.py
```

Measured on the `fundamental-panel-coverage` set that landed today: the worktree has **no venv of
its own**, `/home/miftah/seer/engine/.venv` is an *editable* install pointing at
`/home/miftah/seer/engine/src`, and `engine/pyproject.toml` sets `testpaths` but no `pythonpath`.
Without `PYTHONPATH` a phase can edit this worktree and watch `main`'s code pass the tests.

For `web/`: `cd $SEER_WT/web && npm ci` once, then `npm test` and `npm run build`.

---

## Goal

`web/app/(app)/leaderboard/view.ts:60` ranks the horsemen by `max(totalReturn)` across whatever
span each one happened to live through. After this phase a pure module answers the same question
honestly: over **one window shared by every ranked strategy**, it returns total return, CAGR, max
drawdown and an annualised Sharpe, carries the window and its session count with every figure,
keeps inception-to-date in a separate block that is never ranked, and reports a strategy too young
to be compared as `insufficient` instead of letting it win or collapse the board's window. A
read-only `python -m seer_engine compare` prints the table and emits the exact JSON shape phase 4
ports to TypeScript.

Nothing else moves: no schema, no roster, no paper night, no `web/`.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** none.
**Renames:** none.

**Creates — `engine/src/seer_engine/paper/compare.py` (new, pure):**

Module constants
- `compare.MIN_COMMON_SESSIONS: int = 63`
- `compare.MIN_RANKED: int = 2`
- `compare.SESSIONS_PER_YEAR: int = 252`
- `compare.YEAR_DAYS: float = 365.25`

Types (all `@dataclass(frozen=True, slots=True)`)
- `compare.Window(start: date, end: date, sessions: int)`
- `compare.Performance(start: date, end: date, sessions: int, total_return: float, cagr: float | None, max_drawdown: float, sharpe: float | None)`
- `compare.Row(strategy_id: str, status: Status, rank: int | None, reason: str | None, window: Performance | None, inception: Performance | None)`
- `compare.Comparison(window: Window | None, min_sessions: int, rows: tuple[Row, ...])` with
  properties `ranked -> tuple[Row, ...]` (rank order), `insufficient -> tuple[Row, ...]`
  (id order) and `best -> Row | None` (the rank-1 row, or `None`)
- `compare.Status = Literal["ranked", "insufficient"]`
- `compare.Point = tuple[date, float]`

Functions
- `compare.compare(series: Mapping[str, Sequence[tuple[date, Any]]], *, min_sessions: int = MIN_COMMON_SESSIONS) -> Comparison`
- `compare.performance(points: Sequence[Point]) -> Performance | None`
- `compare.render(c: Comparison) -> tuple[str, ...]`
- `compare.as_json(c: Comparison) -> dict[str, Any]`

**Creates — `engine/src/seer_engine/commands/compare.py` (new, the impure edge):**
- `HELP: str`, `add_arguments(p)`, `run(args) -> int` (the `cli.discover()` contract)
- `commands.compare.read_series(conn, *, exclude: Sequence[str] = ()) -> dict[str, list[tuple[date, Decimal]]]`
- `commands.compare.execute(conn, *, min_sessions: int, exclude: Sequence[str] = (), as_json: bool = False, require_window: bool = False) -> int`
- CLI: `python -m seer_engine compare [--min-sessions N] [--exclude ID ...] [--json] [--require-window]`
- Reads exactly one table: `equity_snapshots (strategy_id, date, equity_usd)`. **It does not read
  `strategies` at all**, so phase 1's `status` / `paper_end` / `promoted_from` columns are
  irrelevant to it and no column of phase 1's is required.

**Signature changes:** none. No existing symbol changes shape.

**Requires (from earlier phases):** nothing. This phase has no `depends_on` and compiles against
`origin/main @ 0d03490` as it stands.

**Leaves alone (owned by others):** `engine/src/seer_engine/paper/roster.py` and
`db/migrations/*` (Phase 1); `engine/src/seer_engine/paper/store.py` and
`engine/src/seer_engine/commands/paper.py` (Phases 1, 2); `web/**` (Phase 4);
`engine/src/seer_engine/commands/promote.py` and `engine/src/seer_engine/lab/store.py` (Phase 5);
`engine/src/seer_engine/backtest/registry.py` (never).

### The shape phase 4 consumes — pinned

**Phase 4 PORTS this math to TypeScript; it does not call the CLI.** The leaderboard is
server-rendered by Next.js reading Neon directly (`web/lib/data.ts:363`); it cannot shell out to
Python per request. Porting across this boundary is already the house pattern —
`backtest/metrics.py:1` says it *"ports `strategyMetrics` and `checklist` line for line"* from
`web/lib/metrics.ts`. The CLI's `--json` exists so phase 4 can pin fixtures against the Python
oracle, not so it can be invoked at render time.

`as_json(c)` emits exactly these keys and units. Nulls are JSON `null`; dates are `YYYY-MM-DD`
strings; `totalReturn`, `cagr` and `maxDrawdown` are **fractions** (`0.123` = 12.3%), matching
`web/lib/metrics.ts`'s `Metrics`; `sharpe` is **annualised, risk-free rate zero**; `sessions` is a
count of snapshot dates (so the return count is `sessions - 1`).

```jsonc
{
  "minSessions": 63,
  "window": { "start": "2026-01-05", "end": "2026-10-02", "sessions": 188 },   // null when none
  "rows": [
    {
      "strategyId": "F4-MOM12-N20-TREND",
      "status": "ranked",                  // "ranked" | "insufficient"
      "rank": 1,                           // null when insufficient
      "reason": null,                      // a sentence when insufficient, else null
      "window": {                          // null when insufficient
        "start": "2026-01-05", "end": "2026-10-02", "sessions": 188,
        "totalReturn": 0.1234, "cagr": 0.1712, "maxDrawdown": 0.0841, "sharpe": 1.12
      },
      "inception": {                       // the strategy's OWN whole curve; never ranked
        "start": "2025-11-03", "end": "2026-10-02", "sessions": 231,
        "totalReturn": 0.2210, "cagr": 0.2431, "maxDrawdown": 0.0991, "sharpe": 0.98
      }
    }
  ]
}
```

**What phase 4 must port, not paraphrase.** The reconciler pinned these against phase 4's
TypeScript; a port that diverges makes the leaderboard and the CLI disagree silently, which is
worse than either being wrong alone:

| Pinned | Value |
|---|---|
| `MIN_COMMON_SESSIONS` | **63** (phase 4 had guessed 21; 63 stands, see Decisions D8) |
| `MIN_RANKED` | **2** — a ranking of one is not a comparison |
| Risk-adjusted figure | annualised Sharpe, `mean / stdev(ddof=1) * sqrt(252)`, risk-free 0. **No Calmar, no configurable rank key** — a knob is a drift vector |
| Rank key | `_select`'s order exactly: finite Sharpe descending; then undefined-Sharpe rows; within each, total return descending, then the **smaller** max drawdown, then `strategy_id` |
| Who is ranked | `_select`'s algorithm exactly: drop every curve shorter than `min_sessions` on its own; then, while the intersection is short, drop the strategy whose removal leaves the **longest** intersection (ties: shortest own curve, then id); stop at `min_sessions` or at `MIN_RANKED` |
| `window` | non-null **iff** at least one row is `ranked`. A UI that wants to say how short the shared span still is must carry that count in a field of its own |
| `status` vocabulary | `"ranked"` / `"insufficient"`. Phase 4 adds a third, `"retired"`, as a **pre-filter outcome in the UI only** — it never reaches this module |

Guarantees phase 4 may rely on:
- `rows` is every id passed in, exactly once, ranked rows first in rank order, then insufficient
  rows in `strategyId` order. Nothing is ever silently dropped.
- For a ranked row, `row.window.start`, `.end` and `.sessions` equal the top-level `window`'s.
- `window === null` ⟺ no row has `status === "ranked"`.
- `cagr` is `null` when the window spans zero calendar days; `sharpe` is `null` when the window has
  fewer than two returns or zero variance. `totalReturn` and `maxDrawdown` are always numbers on a
  non-null `Performance`.
- `inception` is `null` only for a strategy with fewer than two snapshots.
- The benchmark is **not** special-cased here (`compare.py` knows nothing about `is_benchmark`).
  Phase 4 passes SPY in like any other id and picks `best` among non-benchmark ranked rows.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/paper/compare.py` | **create** | the whole pure module (new file, ~250 lines) |
| `engine/src/seer_engine/commands/compare.py` | **create** | the read-only CLI edge; `cli.discover()` picks it up with no edit to `cli.py` |
| `engine/tests/test_paper_compare.py` | **create** | 35 tests (3 need `PG_TEST_URL`) |

No existing file is modified. `engine/src/seer_engine/cli.py:9` states the contract explicitly:
*"Adding a command means adding a module; this file never changes."*

## Implementation Steps

### Step 1: The pure comparison module

**File:** `engine/src/seer_engine/paper/compare.py` (new file, line 1)
**Change:** The whole module. Siblings for style: `paper/roster.py:4` (*"Pure: no database, no
clock, no I/O"*) and `backtest/metrics.py:3` (*"Pure: floats only, no clock, no I/O"*).

Three design decisions are made here and each is defended in the docstring, because phase 4 and
the reconciler both need to see the reasoning, not just the result:

1. **The window is a set intersection of snapshot dates**, not `[max(start), min(end)]`. A session
   one strategy missed is dropped for everyone, so every strategy's returns are measured over the
   very same consecutive pairs of dates.
2. **The risk-adjusted figure is the annualised Sharpe ratio** (`mean / stdev(ddof=1) * sqrt(252)`,
   risk-free rate 0). Sortino needs enough losing sessions to estimate a downside tail; Calmar/MAR
   divides by max drawdown, an extreme-value statistic that is systematically understated over a
   short window and exactly `0.0` for a curve that only rises (a division by zero on the very
   series a leaderboard most wants to rank). Sharpe is defined for any window with two returns and
   non-zero variance, is scale-free so it does not reward merely running longer, and — because the
   window is common by construction — is estimated here from the **same number of observations for
   every ranked strategy**, which removes the sample-size bias that makes Sharpe unfair across
   unequal spans.
3. **`MIN_COMMON_SESSIONS = 63`**, one quarter of a 252-session trading year. Reasoning, stated in
   the module: 63 sessions is three full rebalances for the two `MONTHLY_HOLD` book strategies
   (`roster.py`: F4 and F1 decide monthly), so a ranked book strategy has made at least three
   independent decisions inside the window; three weeks (~15 sessions) is one. It is a floor on
   nonsense, not a claim of precision — at 63 sessions the standard error of an annualised Sharpe
   near 1 is about `sqrt(252 * 1.5 / 63) ≈ 2.4` — which is exactly why the window and session count
   travel with every figure.

**Code:**

```python
"""Common-window, risk-adjusted comparison of paper equity curves (plan
roster-promotion-pipeline, phase 3; invariant 6).

Pure: no database, no clock, no I/O, in the discipline of ``paper/roster.py`` and the ``sim``
modules. ``commands/compare.py`` is the one impure edge: it reads ``equity_snapshots`` and hands
the rows here.

**Why a common window.** Paper strategies start on different dates (``strategies.paper_start``,
``db/migrations/003_paper.sql``) and a retired one stops on its own date. Ranking their raw total
returns -- which is all ``web/app/(app)/leaderboard/view.ts`` does today -- measures the market
over whatever span each strategy happened to live through, not the method. So every ranked figure
here is computed over one window shared by every ranked strategy, and that window is returned in
``Comparison.window`` rather than implied.

**The window is the intersection of snapshot dates**, not ``[max(start), min(end)]``: a session one
strategy missed is dropped for all of them, so every strategy's returns are measured over the very
same consecutive pairs of dates.

**Who is in the intersection.** A strategy whose own curve is shorter than ``min_sessions`` never
joins it; otherwise one three-week-old entry would collapse the window for the whole board. Among
the rest, while the intersection is still short, the strategy whose removal leaves the longest
intersection is dropped (ties: the shortest own curve, then the id) and the intersection
recomputed, until it reaches ``min_sessions`` or fewer than :data:`MIN_RANKED` strategies remain.
Everything left out is a row with ``status="insufficient"`` carrying a ``reason`` -- never a ranked
row, and never a silent omission.

**The risk-adjusted figure is the annualised Sharpe ratio** of the session returns, risk-free rate
zero: ``mean(r) / stdev(r, ddof=1) * sqrt(SESSIONS_PER_YEAR)``. It suits this series better than
the alternatives. Sortino's downside deviation needs enough losing sessions to estimate a tail; a
Calmar/MAR ratio divides by max drawdown, an extreme-value statistic that is systematically
understated over a short window and exactly ``0.0`` for a curve that only rises. Sharpe is defined
for any window with two returns and non-zero variance, is scale-free so it does not reward merely
having run longer, and -- because the window is common by construction -- is estimated here from
the same number of observations for every ranked strategy, which removes the sample-size bias that
makes Sharpe unfair across unequal spans. It is still noisy: at 63 sessions the standard error of
an annualised Sharpe near 1 is about ``sqrt(252 * 1.5 / 63) ~ 2.4``. :data:`MIN_COMMON_SESSIONS` is
a floor on nonsense, not a claim of precision, and the window and session count travel with every
figure so a reader can see how thin it is.

**Inception-to-date is separate.** Every row carries an ``inception`` block over the strategy's own
whole curve, with its own start, end and session count. It is never ranked and never mixed into the
common-window figures (invariant 6).

Fractions, not percents: ``total_return``, ``cagr`` and ``max_drawdown`` are ``0.123`` for 12.3%,
matching ``web/lib/metrics.ts`` and ``backtest/metrics.py``. CAGR uses Actual/365.25, the same
convention as ``backtest.metrics.cagr_between``; it is re-implemented here rather than imported,
because importing ``backtest.metrics`` would pull in the backtest runner and numpy and cost this
module its purity.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

#: A strategy needs this many sessions in the common window to be ranked. 63 is one quarter of a
#: 252-session year, and three full rebalances for a ``MONTHLY_HOLD`` book strategy.
MIN_COMMON_SESSIONS: int = 63

#: A ranking of one is not a comparison.
MIN_RANKED: int = 2

#: Trading sessions per year, the Sharpe annualisation factor.
SESSIONS_PER_YEAR: int = 252

#: Actual/365.25, the CAGR convention of ``backtest.metrics``.
YEAR_DAYS: float = 365.25

NA = "n/a"

Status = Literal["ranked", "insufficient"]
Point = tuple[date, float]


@dataclass(frozen=True, slots=True)
class Window:
    """The span every ranked strategy shares. ``sessions`` counts snapshot dates, ends included."""

    start: date
    end: date
    sessions: int


@dataclass(frozen=True, slots=True)
class Performance:
    """One curve's figures over one stated span.

    ``total_return``, ``cagr`` and ``max_drawdown`` are fractions (0.123 is 12.3%). ``cagr`` is
    ``None`` when the span covers zero calendar days; ``sharpe`` is ``None`` when the span has
    fewer than two returns or zero variance. ``sessions`` counts snapshot dates, so the span holds
    ``sessions - 1`` returns.
    """

    start: date
    end: date
    sessions: int
    total_return: float
    cagr: float | None
    max_drawdown: float
    sharpe: float | None


@dataclass(frozen=True, slots=True)
class Row:
    """One strategy's place in the comparison.

    ``status="ranked"``: ``rank`` is 1-based, ``window`` holds the common-window figures and
    ``reason`` is ``None``. ``status="insufficient"``: ``rank`` and ``window`` are ``None`` and
    ``reason`` says why in one sentence. ``inception`` is the strategy's own whole curve either
    way, and is never ranked.
    """

    strategy_id: str
    status: Status
    rank: int | None
    reason: str | None
    window: Performance | None
    inception: Performance | None


@dataclass(frozen=True, slots=True)
class Comparison:
    """The whole answer: the stated window, the floor it was held to, and every strategy.

    ``window`` is ``None`` exactly when no row is ranked. ``rows`` holds every id handed in,
    once: ranked rows first in rank order, then insufficient rows in id order.
    """

    window: Window | None
    min_sessions: int
    rows: tuple[Row, ...]

    @property
    def ranked(self) -> tuple[Row, ...]:
        """The ranked rows, best first."""
        return tuple(r for r in self.rows if r.status == "ranked")

    @property
    def insufficient(self) -> tuple[Row, ...]:
        """The rows that were not ranked, in id order, each with its ``reason``."""
        return tuple(r for r in self.rows if r.status == "insufficient")

    @property
    def best(self) -> Row | None:
        """The rank-1 row, or ``None`` when nothing could be ranked.

        This module knows nothing about benchmarks: a caller that must exclude one (the
        leaderboard's ``bestResearch``) filters ``ranked`` itself.
        """
        ranked = self.ranked
        return ranked[0] if ranked else None


# --------------------------------------------------------------------------- arithmetic


def _sum(values: Iterable[float]) -> float:
    """Left-to-right float sum from 0, like ``backtest.metrics._sum`` and JavaScript's reduce."""
    total = 0.0
    for v in values:
        total += v
    return total


def _points(strategy_id: str, raw: Sequence[Any]) -> tuple[Point, ...]:
    """``(date, equity)`` as floats, in date order.

    Raises ``TypeError``/``ValueError`` on anything a comparison cannot use: a ``datetime`` where a
    ``date`` belongs, a repeated or out-of-order date, a non-finite equity, or an equity <= 0 (the
    ratios every figure here is built from are undefined at or below zero). ``compare`` catches
    these per strategy, so one broken curve costs its own row, not the table.
    """
    out: list[Point] = []
    previous: date | None = None
    for item in raw:
        day, equity = item
        if isinstance(day, datetime) or not isinstance(day, date):
            raise TypeError(f"{strategy_id}: {day!r} is not a date")
        if previous is not None and day <= previous:
            raise ValueError(f"{strategy_id}: snapshot dates must increase, got {previous} then {day}")
        previous = day
        value = float(equity)
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError(f"{strategy_id}: equity on {day} is {equity!r}; a curve must be finite and positive")
        out.append((day, value))
    return tuple(out)


def _returns(points: Sequence[Point]) -> tuple[float, ...]:
    """Session returns: ``equity[i] / equity[i - 1] - 1`` over consecutive points."""
    return tuple(points[i][1] / points[i - 1][1] - 1.0 for i in range(1, len(points)))


def _max_drawdown(points: Sequence[Point]) -> float:
    """Largest ``(peak - equity) / peak`` over the points, exactly as ``strategy_metrics`` does."""
    peak = points[0][1]
    worst = 0.0
    for _, equity in points:
        if equity > peak:
            peak = equity
        drop = (peak - equity) / peak
        if drop > worst:
            worst = drop
    return worst


def _cagr(points: Sequence[Point]) -> float | None:
    """Compound annual growth, Actual/365.25; ``None`` when the span is zero calendar days."""
    days = (points[-1][0] - points[0][0]).days
    if days <= 0:
        return None
    years = days / YEAR_DAYS
    return (points[-1][1] / points[0][1]) ** (1.0 / years) - 1.0


def _sharpe(returns: Sequence[float]) -> float | None:
    """Annualised Sharpe of session returns, risk-free rate 0; ``None`` when undefined.

    Undefined with fewer than two returns (no sample variance) and on a flat curve (zero
    variance): a strategy that never moved has no risk-adjusted return, and 0/0 is not 0.
    """
    n = len(returns)
    if n < 2:
        return None
    mean = _sum(returns) / n
    variance = _sum((r - mean) ** 2 for r in returns) / (n - 1)
    if variance <= 0.0:
        return None
    return mean / math.sqrt(variance) * math.sqrt(SESSIONS_PER_YEAR)


def performance(points: Sequence[Point]) -> Performance | None:
    """Every figure over ``points``; ``None`` when there are fewer than two (no return exists)."""
    if len(points) < 2:
        return None
    return Performance(
        start=points[0][0],
        end=points[-1][0],
        sessions=len(points),
        total_return=points[-1][1] / points[0][1] - 1.0,
        cagr=_cagr(points),
        max_drawdown=_max_drawdown(points),
        sharpe=_sharpe(_returns(points)),
    )


# --------------------------------------------------------------------------- the common window


def _common_dates(points_by_id: Mapping[str, tuple[Point, ...]], ids: Sequence[str]) -> tuple[date, ...]:
    """The dates every id in ``ids`` has a snapshot for, ascending. Empty for an empty ``ids``."""
    if not ids:
        return ()
    common: set[date] | None = None
    for strategy_id in ids:
        days = {d for d, _ in points_by_id[strategy_id]}
        common = days if common is None else common & days
    return tuple(sorted(common or set()))


def _count(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one}" if n == 1 else f"{n} {many or one + 's'}"


def _select(
    points_by_id: Mapping[str, tuple[Point, ...]], min_sessions: int
) -> tuple[tuple[str, ...], dict[str, str], tuple[date, ...]]:
    """``(ranked ids, {dropped id: reason}, common dates)``.

    Deterministic, and independent of the order the caller handed the strategies in. First every
    curve shorter than ``min_sessions`` on its own is dropped, so one young strategy cannot
    shorten the window for the board. Then, while the intersection is still short, the strategy
    whose removal leaves the longest intersection goes (ties: the shortest own curve, then the
    id). It stops when the intersection is long enough or fewer than ``MIN_RANKED`` remain.
    """
    dropped: dict[str, str] = {}
    live: list[str] = []
    for strategy_id in sorted(points_by_id):
        own = len(points_by_id[strategy_id])
        if own < min_sessions:
            dropped[strategy_id] = f"{_count(own, 'session')} of its own, fewer than {min_sessions}"
        else:
            live.append(strategy_id)

    while len(live) >= MIN_RANKED:
        common = _common_dates(points_by_id, live)
        if len(common) >= min_sessions:
            return tuple(live), dropped, common
        if len(live) == MIN_RANKED:
            break
        worst = min(
            live,
            key=lambda s: (
                -len(_common_dates(points_by_id, [o for o in live if o != s])),
                len(points_by_id[s]),
                s,
            ),
        )
        dropped[worst] = (
            f"leaves only {_count(len(common), 'common session')} with the other "
            f"{_count(len(live) - 1, 'strategy', 'strategies')} compared, fewer than {min_sessions}"
        )
        live = [s for s in live if s != worst]

    for strategy_id in live:
        dropped[strategy_id] = (
            f"fewer than {MIN_RANKED} strategies share a window of {min_sessions} sessions"
        )
    return (), dropped, ()


def _rank_key(row: Row) -> tuple[Any, ...]:
    """Sharpe descending, undefined Sharpe last; then total return descending, then the smaller
    max drawdown, then the id. Every tie is broken, so the order never depends on input order."""
    w = row.window
    if w is None:  # unreachable for a ranked row; keeps the key total
        return (2, 0.0, 0.0, 0.0, row.strategy_id)
    if w.sharpe is None:
        return (1, 0.0, -w.total_return, w.max_drawdown, row.strategy_id)
    return (0, -w.sharpe, -w.total_return, w.max_drawdown, row.strategy_id)


def compare(
    series: Mapping[str, Sequence[Any]], *, min_sessions: int = MIN_COMMON_SESSIONS
) -> Comparison:
    """Compare every curve in ``series`` over the window they share.

    ``series`` maps a strategy id to its ``(date, equity)`` snapshots in date order; the equity may
    be anything ``float()`` accepts, so ``equity_snapshots``' ``Decimal`` rows go straight in.

    Every id handed in comes back as exactly one :class:`Row`. A strategy that cannot be ranked --
    too short on its own, too little overlap, or an unusable curve -- comes back
    ``status="insufficient"`` with a ``reason``, and is never dropped from ``rows``.
    """
    if min_sessions < 2:
        raise ValueError(f"min_sessions must be at least 2, got {min_sessions}")

    points_by_id: dict[str, tuple[Point, ...]] = {}
    unusable: dict[str, str] = {}
    for strategy_id in sorted(series):
        try:
            points_by_id[strategy_id] = _points(strategy_id, series[strategy_id])
        except (TypeError, ValueError) as exc:
            unusable[strategy_id] = f"unusable curve ({exc})"

    ranked_ids, dropped, common = _select(points_by_id, min_sessions)
    common_set = frozenset(common)

    ranked: list[Row] = []
    for strategy_id in ranked_ids:
        points = points_by_id[strategy_id]
        in_window = tuple(p for p in points if p[0] in common_set)
        ranked.append(
            Row(
                strategy_id=strategy_id,
                status="ranked",
                rank=None,
                reason=None,
                window=performance(in_window),
                inception=performance(points),
            )
        )
    ranked.sort(key=_rank_key)
    ranked = [
        Row(
            strategy_id=r.strategy_id,
            status="ranked",
            rank=i,
            reason=None,
            window=r.window,
            inception=r.inception,
        )
        for i, r in enumerate(ranked, start=1)
    ]

    short: list[Row] = []
    for strategy_id in sorted({*dropped, *unusable}):
        short.append(
            Row(
                strategy_id=strategy_id,
                status="insufficient",
                rank=None,
                reason=unusable.get(strategy_id) or dropped[strategy_id],
                window=None,
                inception=performance(points_by_id.get(strategy_id, ())),
            )
        )

    window = Window(start=common[0], end=common[-1], sessions=len(common)) if common else None
    return Comparison(window=window, min_sessions=min_sessions, rows=tuple(ranked) + tuple(short))


# --------------------------------------------------------------------------- rendering


def _pct(v: float | None, *, signed: bool = True) -> str:
    if v is None:
        return NA
    if math.isinf(v):
        return "inf" if v > 0 else "-inf"
    body = f"{abs(v) * 100:.1f}%"
    return (("+" if v >= 0 else "-") + body) if signed else body


def _ratio(v: float | None) -> str:
    return NA if v is None else f"{v:+.2f}"


def render(c: Comparison) -> tuple[str, ...]:
    """The comparison as plain lines: the window first, then the ranking, then what was left out,
    then inception-to-date as its own block so it can never be read as part of the ranking."""
    width = max((len(r.strategy_id) for r in c.rows), default=8)
    lines: list[str] = []
    if c.window is None:
        lines.append(
            f"no common window of {c.min_sessions} sessions among "
            f"{_count(len(c.rows), 'strategy', 'strategies')}"
        )
    else:
        lines.append(
            f"common window {c.window.start.isoformat()}..{c.window.end.isoformat()}, "
            f"{_count(c.window.sessions, 'session')} (minimum {c.min_sessions})"
        )

    ranked = c.ranked
    if ranked:
        lines.append(
            f"{'#':>2}  {'strategy':<{width}}  {'total':>8}  {'CAGR':>8}  {'max DD':>7}  {'Sharpe':>7}"
        )
    for r in ranked:
        w = r.window
        if w is None:
            continue
        lines.append(
            f"{r.rank:>2}  {r.strategy_id:<{width}}  {_pct(w.total_return):>8}  {_pct(w.cagr):>8}  "
            f"{_pct(w.max_drawdown, signed=False):>7}  {_ratio(w.sharpe):>7}"
        )
    for r in c.insufficient:
        lines.append(f"{'-':>2}  {r.strategy_id:<{width}}  not ranked: {r.reason}")

    lines.append("inception to date (its own window; never ranked)")
    for r in sorted(c.rows, key=lambda x: x.strategy_id):
        i = r.inception
        if i is None:
            lines.append(f"    {r.strategy_id:<{width}}  fewer than two sessions")
        else:
            lines.append(
                f"    {r.strategy_id:<{width}}  {i.start.isoformat()}..{i.end.isoformat()}  "
                f"{_count(i.sessions, 'session'):>14}  {_pct(i.total_return):>8}"
            )
    return tuple(lines)


def _window_json(w: Window | None) -> dict[str, Any] | None:
    if w is None:
        return None
    return {"start": w.start.isoformat(), "end": w.end.isoformat(), "sessions": w.sessions}


def _performance_json(p: Performance | None) -> dict[str, Any] | None:
    if p is None:
        return None
    return {
        "start": p.start.isoformat(),
        "end": p.end.isoformat(),
        "sessions": p.sessions,
        "totalReturn": p.total_return,
        "cagr": p.cagr,
        "maxDrawdown": p.max_drawdown,
        "sharpe": p.sharpe,
    }


def as_json(c: Comparison) -> dict[str, Any]:
    """The comparison as JSON-ready data, camelCased for the web (phase 4 ports this math to
    TypeScript and pins its fixtures against this output). Fractions, not percents; ISO dates."""
    return {
        "minSessions": c.min_sessions,
        "window": _window_json(c.window),
        "rows": [
            {
                "strategyId": r.strategy_id,
                "status": r.status,
                "rank": r.rank,
                "reason": r.reason,
                "window": _performance_json(r.window),
                "inception": _performance_json(r.inception),
            }
            for r in c.rows
        ],
    }
```

**Impact:** a new pure module. Nothing imports it yet except step 2 and the tests, so the tree
builds and the existing suite is untouched.

**Degenerate cases, each decided here and tested in step 3:**

| Case | What `compare` returns |
|---|---|
| a single session (one snapshot) | own curve < `min_sessions` → `insufficient`, `reason` says `"1 session of its own, fewer than 63"`; `inception` is `None` (no return exists) |
| a flat series (equity never moves) | ranked if long enough; `total_return = 0.0`, `max_drawdown = 0.0`, `sharpe = None` (0/0 is not 0), and `_rank_key` sorts it after every finite Sharpe |
| zero variance but non-zero drift | impossible on a ratio series unless every session return is identical; then variance is 0 and `sharpe` is `None`, same branch |
| a strategy retired mid-window | its last snapshot is its `paper_end` session; the intersection simply ends there, truncating the window for everyone — and the window is *returned*, so the reader sees it |
| a retired strategy that overlaps nothing | the intersection empties; `_select` drops whichever removal restores the longest intersection, and that strategy is `insufficient` with `"leaves only 0 common sessions …"` |
| an empty intersection with only two strategies | the `len(live) == MIN_RANKED` break fires; both are `insufficient` with `"fewer than 2 strategies share a window of 63 sessions"`, `Comparison.window is None`, `ranked` empty |
| one strategy in, or none | never ranked — a ranking of one is not a comparison (`MIN_RANKED = 2`) |
| equity <= 0, NaN, or a repeated/out-of-order date | that one strategy is `insufficient` with `"unusable curve (…)"`; the rest still rank |
| `min_sessions < 2` | `ValueError` — a window with no return in it is not a window |

### Step 2: The read-only CLI edge

**File:** `engine/src/seer_engine/commands/compare.py` (new file, line 1)
**Change:** The whole module. `cli.py:29` discovers every public module under `commands/`, so no
existing file changes. The read-only transaction pattern is `commands/paper_check.py:92-104`
verbatim; `print` for a report is `commands/lab.py:193`'s house style.

**Code:**

```python
"""compare: rank the paper strategies over the window they share (read-only).

``python -m seer_engine compare [--min-sessions N] [--exclude ID ...] [--json] [--require-window]``

Reads every ``equity_snapshots`` row and hands them to ``paper.compare``, which is pure. Prints
the common window, the ranking over it, what could not be ranked and why, and inception-to-date
as a separate block. ``--json`` prints ``paper.compare.as_json`` instead -- the exact shape the
leaderboard's TypeScript port is pinned against.

Reads one table and nothing else: no ``strategies`` row, no roster, no clock. Everything happens
in one REPEATABLE READ, READ ONLY transaction that is always rolled back, so ``--dry-run``
changes nothing because there is nothing to change.

Because it does not read ``strategies``, it does not know which strategies are retired, and that
is deliberate: a retired strategy is not a live competitor, so excluding it is the caller's
decision, not this module's arithmetic. ``--exclude <id>`` is how a human makes it; the
leaderboard's TypeScript port makes it from ``strategies.status``.

Exit 0 when the comparison was produced; with ``--require-window``, exit 1 when no window of
``--min-sessions`` sessions exists (useful in CI, and the honest answer for a young board).
Config errors exit 2 (cli).
"""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

import psycopg
from psycopg.pq import TransactionStatus

from seer_engine import db
from seer_engine.paper import compare as compare_

log = logging.getLogger(__name__)

HELP = "Rank the paper strategies over the window they share, with the window stated (read-only)"


def _sessions_arg(value: str) -> int:
    try:
        n = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"--min-sessions must be a whole number, got {value!r}") from e
    if n < 2:
        raise argparse.ArgumentTypeError(f"--min-sessions must be at least 2, got {n}")
    return n


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--min-sessions",
        type=_sessions_arg,
        default=compare_.MIN_COMMON_SESSIONS,
        metavar="N",
        help=(
            f"sessions a strategy needs in the common window to be ranked "
            f"(default {compare_.MIN_COMMON_SESSIONS}, one quarter of a trading year)"
        ),
    )
    p.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="ID",
        help="leave this strategy out of the comparison entirely (repeatable, e.g. --exclude SPY). "
             "A retired strategy is not a live competitor: exclude it to rank the living",
    )
    p.add_argument("--json", action="store_true", help="print the comparison as JSON instead of a table")
    p.add_argument(
        "--require-window",
        action="store_true",
        help="exit 1 when no common window of --min-sessions sessions exists",
    )


def run(args: argparse.Namespace) -> int:
    conn = db.connect()
    try:
        return execute(
            conn,
            min_sessions=int(args.min_sessions),
            exclude=tuple(args.exclude),
            as_json=bool(args.json),
            require_window=bool(args.require_window),
        )
    finally:
        conn.close()


def read_series(
    conn: psycopg.Connection, *, exclude: Sequence[str] = ()
) -> dict[str, list[tuple[date, Decimal]]]:
    """Every strategy's ``equity_snapshots`` rows as ``(date, equity_usd)`` in date order.

    Reads only ``equity_snapshots``; a strategy with no snapshot simply has no key.
    """
    skip = {s.strip() for s in exclude if s.strip()}
    rows = conn.execute(
        "SELECT strategy_id, date, equity_usd FROM equity_snapshots ORDER BY strategy_id, date"
    ).fetchall()
    series: dict[str, list[tuple[date, Decimal]]] = {}
    for strategy_id, day, equity in rows:
        if strategy_id in skip:
            continue
        series.setdefault(strategy_id, []).append((day, equity))
    return series


def execute(
    conn: psycopg.Connection,
    *,
    min_sessions: int = compare_.MIN_COMMON_SESSIONS,
    exclude: Sequence[str] = (),
    as_json: bool = False,
    require_window: bool = False,
) -> int:
    """Read, compare, print; return the exit code. Writes nothing.

    ``conn`` must have autocommit off and no transaction in progress; the read-only transaction
    this opens is always rolled back.
    """
    if conn.info.transaction_status != TransactionStatus.IDLE:
        raise ValueError("compare needs a connection with no transaction in progress")
    try:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        series = read_series(conn, exclude=exclude)
    finally:
        conn.rollback()

    result = compare_.compare(series, min_sessions=min_sessions)
    if as_json:
        print(json.dumps(compare_.as_json(result), indent=2, sort_keys=True))
    else:
        for line in compare_.render(result):
            print(line)
    if result.window is None:
        log.warning(
            "compare: no common window of %d sessions; nothing was ranked (invariant 6: a "
            "cross-window comparison is not a ranking)",
            min_sessions,
        )
        if require_window:
            return 1
    return 0
```

**Impact:** `python -m seer_engine compare` appears in `--help`. `cli.discover()` picks it up with
no edit to `cli.py`; `engine/tests/test_cli.py` pins no command list (it asserts only that
`"migrate" in cli.discover()`), so nothing existing changes result.

### Step 3: Tests

**File:** `engine/tests/test_paper_compare.py` (new file, line 1)
**Change:** 35 tests. Three need `PG_TEST_URL` (the `pg` fixture, `conftest.py:107`) and skip
without it; the rest are pure and always run.

Builders used throughout (defined at the top of the file):

```python
def curve(start: date, equities: Sequence[float], *, step: int = 1) -> list[tuple[date, float]]:
    """(date, equity) on consecutive calendar days from ``start`` (weekends are irrelevant here:
    the module compares snapshot dates, never trading calendars)."""
    return [(start + timedelta(days=i * step), float(e)) for i, e in enumerate(equities)]


def flat(start: date, n: int, value: float = 100_000.0) -> list[tuple[date, float]]:
    return curve(start, [value] * n)


def drifting(start: date, n: int, per_session: float, value: float = 100_000.0) -> list[tuple[date, float]]:
    """A curve compounding ``per_session`` every session, with a single 1% dip at session n//2 so
    it has non-zero variance and a measurable drawdown."""
    out: list[float] = [value]
    for i in range(1, n):
        out.append(out[-1] * (1.0 + per_session) * (0.99 if i == n // 2 else 1.0))
    return curve(start, out)
```

| # | Test | Asserts |
|---|---|---|
| 1 | `test_performance_total_return_and_sessions` | `performance(curve(D, [100, 110, 121]))` has `total_return == pytest.approx(0.21)`, `sessions == 3`, `start`/`end` the first and last date |
| 2 | `test_cagr_matches_backtest_metrics_cagr_between` | `performance(...).cagr == backtest.metrics.cagr_between(first, last)` on three spans — the Actual/365.25 parity claim in the docstring |
| 3 | `test_max_drawdown_matches_strategy_metrics` | `performance(c).max_drawdown == strategy_metrics(c, []).max_drawdown` on a curve with two separate dips |
| 4 | `test_sharpe_is_annualised_from_session_returns` | hand-computed: returns `(0.01, -0.005, 0.02, 0.0)` → `mean/stdev(ddof=1)*sqrt(252)`, compared with `pytest.approx` |
| 5 | `test_sharpe_is_none_on_a_flat_series` | `performance(flat(D, 10)).sharpe is None`, and `total_return == 0.0`, `max_drawdown == 0.0` |
| 6 | `test_sharpe_is_none_with_one_return` | two points → `sharpe is None`, `total_return` still a number |
| 7 | `test_performance_is_none_for_a_single_session` | `performance([(D, 1.0)]) is None` and `performance([]) is None` |
| 8 | `test_cagr_is_none_over_zero_calendar_days` | a two-point curve built by hand cannot repeat a date, so this goes through `_cagr` directly with equal dates |
| 9 | `test_points_rejects_out_of_order_dates` | `pytest.raises(ValueError)` |
| 10 | `test_points_rejects_a_duplicate_date` | `pytest.raises(ValueError)` |
| 11 | `test_points_rejects_non_positive_equity` | `0.0` and `-1.0` both raise `ValueError` |
| 12 | `test_points_rejects_a_datetime` | `pytest.raises(TypeError)` |
| 13 | `test_points_accepts_decimal_equity` | `Decimal("100000.0000")` goes through unchanged |
| 14 | `test_common_window_is_the_intersection_and_is_returned` | two 100-session curves offset by 20 days → `c.window.start`/`.end`/`.sessions` are the intersection's, not either curve's, and `min_sessions=10` |
| 15 | `test_a_missed_session_is_dropped_for_everyone` | one curve missing one interior date → that date is absent from the window for both, and `window.sessions` is one less |
| 16 | `test_a_short_strategy_is_insufficient_and_does_not_shorten_the_window` | the **FND case**: two 200-session curves plus a 9-session one; `window.sessions == 200`, the short one is `insufficient`, `rank is None`, `window is None`, reason mentions `"9 sessions of its own"` |
| 17 | `test_a_retired_strategy_truncates_the_common_window` | a curve that stops 40 sessions early → `c.window.end` is its last date and both are still ranked |
| 18 | `test_a_retired_strategy_that_overlaps_nothing_is_dropped_not_ranked` | three curves, one retired long before the others started → the other two rank over their own intersection and the retired one is `insufficient` |
| 19 | `test_two_strategies_with_an_empty_intersection_rank_nothing` | `c.window is None`, `c.ranked == ()`, both rows `insufficient` with the `"fewer than 2 strategies"` reason |
| 20 | `test_no_strategies_yields_an_empty_comparison` | `compare({})` → `window is None`, `rows == ()` |
| 21 | `test_one_strategy_is_never_a_ranking` | a single 500-session curve → `ranked == ()`, one `insufficient` row, `best is None` |
| 22 | `test_selection_is_independent_of_input_order` | the same four series in 6 shuffled dict orders produce an identical `as_json` payload |
| 23 | `test_min_sessions_below_two_is_refused` | `pytest.raises(ValueError)` |
| 24 | `test_ranks_by_sharpe_descending` | three curves with known Sharpes → `[r.strategy_id for r in c.ranked]` is the expected order and `ranks` are `1, 2, 3` |
| 25 | `test_ties_on_sharpe_break_on_total_return_then_drawdown` | two curves with identical Sharpe (one a scaled copy) and different total return |
| 26 | `test_a_flat_ranked_row_sorts_after_every_finite_sharpe` | a flat curve and a drifting one, both long enough → the flat one ranks last, `window.sharpe is None` |
| 27 | `test_best_is_the_rank_one_row` | `c.best.strategy_id == c.ranked[0].strategy_id`; `best is None` when nothing ranks |
| 28 | `test_insufficient_rows_carry_no_rank_and_no_window` | every `insufficient` row has `rank is None`, `window is None`, `reason` a non-empty string |
| 29 | `test_every_input_id_appears_exactly_once_in_rows` | `sorted(r.strategy_id for r in c.rows) == sorted(series)` on a mixed case |
| 30 | `test_inception_is_the_whole_own_curve_and_differs_from_the_window` | a ranked row's `inception.sessions > window.sessions` and `inception.total_return != window.total_return`; `inception.start` is the curve's first date |
| 31 | `test_inception_is_present_for_an_insufficient_row` | the 9-session FND row has a non-null `inception` with `sessions == 9` |
| 32 | `test_an_unusable_curve_costs_its_own_row_not_the_table` | one series with a negative equity among three good ones → it is `insufficient` with `"unusable curve"`, the others still rank |
| 33 | `test_render_states_the_window_on_its_first_line_and_marks_what_is_not_ranked` | line 0 matches `common window \d{4}-..-..\.\.\d{4}-..-.., \d+ sessions \(minimum 63\)`; an `insufficient` id appears on a `not ranked:` line; `"inception to date"` appears exactly once |
| 34 | `test_render_says_so_when_there_is_no_common_window` | line 0 starts `no common window of` |
| 35 | `test_as_json_field_names_units_and_nulls` | **the phase-4 contract**: top-level keys `== {"minSessions", "window", "rows"}`; a row's keys `== {"strategyId", "status", "rank", "reason", "window", "inception"}`; a `Performance` payload's keys `== {"start", "end", "sessions", "totalReturn", "cagr", "maxDrawdown", "sharpe"}`; dates are `YYYY-MM-DD` strings; `totalReturn` is a fraction (`0 < v < 1` for a +20% curve); a ranked row's `window["start"]`/`["end"]`/`["sessions"]` equal the top-level window's; the whole payload survives `json.loads(json.dumps(payload))` |

Plus two the table above numbers as part of the 35 (listed separately because they are structural,
not arithmetic):

| # | Test | Asserts |
|---|---|---|
| 36→ folded into 33 | — | — |

And the purity and CLI tests:

| # | Test | Asserts |
|---|---|---|
| P1 | `test_compare_module_has_no_clock_randomness_or_io` | `ast.parse` of `paper/compare.py`, modelled on `test_sim_purity.py:65`: no import whose root is in `{"psycopg", "requests", "yfinance", "time", "random", "logging", "urllib", "socket"}`, no `seer_engine.bars`, no attribute in `{"now", "utcnow", "today", "fromtimestamp"}`, no call to `print`/`open`/`input`. This is the executable form of the "Pure" claim. |
| D1 | `test_execute_reads_equity_snapshots_and_prints_the_window` *(needs `pg`)* | insert 120 snapshots each for `SPY`, `A`, `F4-MOM12-N20-TREND` (ids the `pg` fixture's `003_paper.sql` INSERT already created, so the FK holds); `execute(pg, min_sessions=63) == 0`; `capsys` output's first line starts `common window`; the connection is left with no open transaction |
| D2 | `test_execute_excludes_ids` *(needs `pg`)* | `execute(pg, min_sessions=63, exclude=("SPY",))` prints no `SPY` line, and `read_series(pg, exclude=("SPY",))` has no `"SPY"` key |
| D3 | `test_require_window_exits_1_without_a_common_window` *(needs `pg`)* | 10 snapshots each → `execute(pg, min_sessions=63) == 0` but `execute(pg, min_sessions=63, require_window=True) == 1`, and `--json` output parses with `window is None` |

Final count: **32 pure tests + 3 database tests = 35.**

**Impact:** no existing test file is touched, so no existing test can change result (invariant 1).

## Verification

**Build:**

```bash
"$SEER_PY" -c 'import seer_engine.paper.compare, seer_engine.commands.compare; print("ok")'
"$SEER_PY" -m ruff check engine/src/seer_engine/paper/compare.py \
                         engine/src/seer_engine/commands/compare.py \
                         engine/tests/test_paper_compare.py
```

**Tests:**

```bash
# this phase alone
"$SEER_PY" -m pytest engine/tests/test_paper_compare.py -q
# the whole suite, the delta that matters
"$SEER_PY" -m pytest engine/tests -q
```

**Test delta (never an absolute, invariant 1).** This phase adds one test file and modifies none:

- without `PG_TEST_URL`: **+32 passed, +3 skipped**
- with `PG_TEST_URL` exported: **+35 passed, +0 skipped**

No existing test changes result, because no existing file is edited.

**Manual check:**

```bash
"$SEER_PY" -m seer_engine compare --min-sessions 10
"$SEER_PY" -m seer_engine compare --min-sessions 10 --exclude SPY --json | head -40
"$SEER_PY" -m seer_engine --help | grep compare
```

Read the first line of the table. It must name a start date, an end date and a session count. If
it says `no common window`, that is the honest answer for a board this young, and
`--require-window` is the flag that turns it into a failure.

**Exit criteria:**

1. `python -m seer_engine compare` prints a table whose **first line states the window and its
   session count**, and whose ranking rows all come from that one window (invariant 6).
2. `compare.compare` is importable and callable with no database, no network and no clock, and
   `test_compare_module_has_no_clock_randomness_or_io` proves it mechanically.
3. A strategy with fewer than `MIN_COMMON_SESSIONS = 63` sessions appears as `insufficient` with a
   reason, is absent from `ranked`, and **does not shorten the window for anyone else**.
4. `inception` is on every row, carries its own `start`/`end`/`sessions`, and appears under its own
   heading in `render` — never inside the ranking table.
5. `as_json` emits exactly the keys pinned in the Interface Contract, and
   `test_as_json_field_names_units_and_nulls` fails if any of them moves.
6. `"$SEER_PY" -m pytest engine/tests -q` shows the delta above and no changed result.

## Handoffs

- **Phase 4 (R3) ports this math to TypeScript** and must **show the window in the UI**, which this
  phase deliberately does not do. The port replaces `web/app/(app)/leaderboard/view.ts:60`
  `bestResearch`. Pin the TS fixtures against `python -m seer_engine compare --json`. The field
  names, units and null rules are in the Interface Contract above and are stable.
- **Phase 4 also owns benchmark exclusion.** `compare.py` is deliberately benchmark-blind: it has
  no `is_benchmark` concept, so SPY is ranked like anything else. `bestResearch`'s replacement must
  take the first row of `Comparison.ranked` whose strategy is not the benchmark. Putting that rule
  in `compare.py` would have made a pure math module depend on roster semantics phase 1 owns.
- **Retired strategies: excluded by the CALLER, never ranked. Settled by the reconciler.**
  `compare.py` stays status-blind — it never reads `status` or `paper_end`, which is what keeps it
  a wave-1 phase with no dependency on phase 1 — but the index's phase-4 exit criterion says a
  retired strategy *"is excluded from 'best' without being hidden"*, so a retired curve must not
  enter a ranking. The rule is therefore: **whoever calls `compare` drops the retired ids first.**
  Phase 4's port filters `status === 'retired'` before building the window. On this side, the
  `--exclude ID` flag is that filter for a human (`compare --exclude <a retired id>`), and
  `commands/compare.py`'s module docstring and `--exclude` help text must say so in one sentence:
  *"a retired strategy is not a live competitor; exclude it to rank the living."* Do **not** add a
  `strategies` read to make this automatic — that would give this phase a phase-1 dependency it
  does not have, and the exclusion is a presentation decision, not arithmetic.
  Tests 17 and 18 stay as they are: they pin what the math does with a curve that stops early,
  which is a real case (a gap in a feed, a strategy excluded by hand) independent of retirement.
  Labelling the row "retired" in the UI is phase 4's, from phase 1's `status`.
- **Phase 2 (R2)** sets `paper_end` on retirement. Nothing is needed from it here: this phase's
  `test_a_retired_strategy_truncates_the_common_window` and
  `test_a_retired_strategy_that_overlaps_nothing_is_dropped_not_ranked` already cover a series that
  stops mid-window, because a retirement is just a curve with an earlier last date.
- **Phase 6 (R1)** adds `FND`, a strategy with almost no history — the `insufficient` path.
  Test 16 is written as that case by name. When `FND` lands, `compare` will show it as not ranked
  with `"N sessions of its own, fewer than 63"` and the other four will keep their full window.
  Phase 6 needs to do nothing here.
- **Not done, deliberately:** no excess-return-vs-benchmark figure, no rolling window, no
  statistical significance test on the Sharpe difference, and no persistence of the comparison. All
  four are real follow-ups; none is needed for R3 and each would widen a phase the index already
  marks HARD.
- **Not done, deliberately:** `backtest/metrics.py` now has a near-duplicate CAGR and max-drawdown.
  Merging them would require making `backtest.metrics` importable without the backtest runner — a
  refactor of a module this plan set does not own. Test 2 and test 3 pin the two implementations to
  agree, which is the cheap guarantee.

## Rollback

`git revert` the phase's single commit, or delete the three new files:

```bash
rm -f "$SEER_WT/engine/src/seer_engine/paper/compare.py" \
      "$SEER_WT/engine/src/seer_engine/commands/compare.py" \
      "$SEER_WT/engine/tests/test_paper_compare.py"
```

Nothing else is touched, so that is the whole of it. There is no migration, no data written, no
schema change and no effect on a paper night — `commands/compare.py` runs inside a READ ONLY
transaction that is always rolled back. The only externally visible loss is the `compare`
subcommand disappearing from `python -m seer_engine --help`, since `cli.discover()` enumerates the
directory and the file is gone.
