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

    ``deposited`` is the dollars the owner added over the span -- money arriving, not performance.
    It is 0.0 for every strategy that received nothing, which is every strategy on the roster
    today. When it is non-zero ``cagr`` is ``None``: compound growth over a book that was fed
    cannot be read off the endpoints, and the honest figure is a money-weighted return, which
    lives in ``backtest.metrics`` and is deliberately not imported into this pure module.
    ``total_return`` and ``max_drawdown`` still read the raw curve and so still carry the
    deposit; ``render`` says so in a line beneath the table rather than quoting them as clean.
    """

    start: date
    end: date
    sessions: int
    total_return: float
    cagr: float | None
    max_drawdown: float
    sharpe: float | None
    deposited: float = 0.0


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


def _returns(points: Sequence[Point], deposits: Mapping[date, float] = {}) -> tuple[float, ...]:
    """Session returns over consecutive points, with external deposits removed.

    ``equity[i]`` includes any money the owner added on that session, and money arriving is not a
    return -- a book that earns nothing and is handed 5,000,000 IDR would otherwise report the
    deposit as performance (plan set Decision D4, measured in phase 7 as +600.9% over a year).
    So the credited dollars are taken out of the ending equity before the ratio:
    ``(equity[i] - deposit[i]) / equity[i - 1] - 1``.

    ``deposits`` maps a session date to the dollars credited at the OPEN of that session
    (``paper.store.read_contributions``, whose ``session_date`` is exactly this key, and whose
    ``amount_usd`` is exactly this value). Empty -- the default, and every strategy that has
    received nothing -- leaves every number bit-for-bit as it was.
    """
    out: list[float] = []
    for i in range(1, len(points)):
        day, equity = points[i]
        out.append((equity - deposits.get(day, 0.0)) / points[i - 1][1] - 1.0)
    return tuple(out)


def _deposited(points: Sequence[Point], deposits: Mapping[date, float] = {}) -> float:
    """The dollars added over ``points``, counting the same sessions ``_returns`` corrects.

    The first point is the span's opening equity, so a deposit dated on it is part of the
    baseline rather than something that happened during the span -- exactly the sessions
    ``_returns`` skips, and the same rule, so the two can never disagree about whether a window
    was fed.
    """
    return _sum(deposits.get(day, 0.0) for day, _ in points[1:])


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


def performance(points: Sequence[Point], deposits: Mapping[date, float] = {}) -> Performance | None:
    """Every figure over ``points``; ``None`` when there are fewer than two (no return exists).

    ``deposits`` is this strategy's session-dated dollars (see ``_returns``). With none -- the
    default -- every field is bit-for-bit what it was before deposits existed. With some, the
    session returns and therefore ``sharpe`` have the money taken out, and ``cagr`` is ``None``
    because an endpoint ratio counts the owner's own money as growth.
    """
    if len(points) < 2:
        return None
    deposited = _deposited(points, deposits)
    return Performance(
        start=points[0][0],
        end=points[-1][0],
        sessions=len(points),
        total_return=points[-1][1] / points[0][1] - 1.0,
        cagr=None if deposited else _cagr(points),
        max_drawdown=_max_drawdown(points),
        sharpe=_sharpe(_returns(points, deposits)),
        deposited=deposited,
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
    series: Mapping[str, Sequence[Any]],
    *,
    min_sessions: int = MIN_COMMON_SESSIONS,
    deposits: Mapping[str, Mapping[date, float]] = {},
) -> Comparison:
    """Compare every curve in ``series`` over the window they share.

    ``series`` maps a strategy id to its ``(date, equity)`` snapshots in date order; the equity may
    be anything ``float()`` accepts, so ``equity_snapshots``' ``Decimal`` rows go straight in.

    ``deposits`` maps a strategy id to the dollars the owner added, by the session they were
    credited on (``paper.store.read_contributions``' ``session_date`` -> ``amount_usd``, applied
    rows only). A strategy absent from it received nothing, which is every strategy on the roster
    today and is the default; money arriving is not a return, so for one that is present the
    session returns have it removed and its ``cagr`` is suppressed. See ``_returns``.

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
                window=performance(in_window, deposits.get(strategy_id, {})),
                inception=performance(points, deposits.get(strategy_id, {})),
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
                inception=performance(points_by_id.get(strategy_id, ()), deposits.get(strategy_id, {})),
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

    fed = [r for r in ranked if r.window is not None and r.window.deposited]
    if fed:
        lines.append(
            "money added during the window, so CAGR is not shown for "
            + ", ".join(f"{r.strategy_id} (+{r.window.deposited:,.2f} USD)" for r in fed)
        )
        lines.append(
            "    total and max DD still count that money; the figure that does not is the "
            "money-weighted return"
        )

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
