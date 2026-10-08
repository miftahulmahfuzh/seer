"""The book engine's session loop, the trade-rules dispatch, and run statistics (P7a, plan phase 3).

Pure (tests/test_strategy_purity.py globs this directory): no database, network, clock,
randomness, logging or file access. Three things live here.

``run_book`` drives ``sim.book.step_book`` over every NYSE session S in ``[start, end]``, in the
same shape as ``runner.run_backtest``:

1. on a rank session (``sim.rules.is_rank_session``) the allocator maps history through
   ``data_date = prev_session(S)``, the members on ``data_date`` and the symbols held at night
   (the idle instrument left out: it is the runner's, never a family's) to target weights; on
   any other session the targets are ``None`` (no signal exits, no entries, no resizes);
1b. on a resize-only session (``sim.rules.is_resize_session``, only with ``rules.resize_cadence``)
   the allocator is called the same way, but its answer is used for its TOTAL weight alone: the
   last rank session's basket is kept and rescaled by ``_rescaled`` (below). Nothing is ranked,
   entered or signal-exited for being out of rank. A resize session BEFORE the window's first
   rank session has no basket to re-scale and is not a decision session at all (the allocator is
   not called), so the run never parks itself in the idle instrument before it has ranked once;
2. with ``rules.idle_symbol`` set and a bar for it dated ``data_date``, the residual weight
   ``1 - sum(weights)`` is appended as the last target, in that instrument;
3. ``step_book`` gets S's bars for every held or targeted symbol, and (``rules.dividends`` only)
   the cash dividends whose ex-date is S for the symbols held at night;
4. every position whose symbol has no bar on S or later in the loaded data is force-closed at
   its mark (``close_book_unpriced``) and S's snapshot is replaced, exactly as ``run_backtest``
   does with ``sim.close_unpriced``.

``run_rules`` is the one entry point by rules: ``DESIGN_V0`` with a ``Strategy`` goes to the
unchanged ``run_backtest`` (so A, A2 and B stay byte-identical by construction); any book rule
set with an ``Allocator`` goes to ``run_book``; any other pairing is a TypeError.

``run_stats`` reduces either result to what the dev report needs. Floats exist only there, and
every float sum runs left to right in a plain loop, as ``backtest.metrics`` does.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from seer_engine import dates
from seer_engine.backtest.market import Market
from seer_engine.backtest.metrics import YEAR_DAYS, Metrics, run_metrics, strategy_metrics
from seer_engine.backtest.runner import INITIAL_IDR, RunResult, run_backtest
from seer_engine.sim.book import (
    Book,
    BookSnapshot,
    Fill,
    Position,
    Target,
    Trade,
    close_book_unpriced,
    new_book,
    step_book,
    to_weight,
)
from seer_engine.sim.charges import order_fee
from seer_engine.sim.contributions import (
    ContributionSchedule,
    Contributions,
    credit_for,
)
from seer_engine.sim.costs import Side
from seer_engine.sim.model import initial_cash_usd, q
from seer_engine.sim.rules import (
    DESIGN_V0,
    TradeRules,
    is_bracket,
    is_rank_session,
    is_resize_session,
)
from seer_engine.strategies.allocator import Allocator, scale_weight
from seer_engine.strategies.base import Strategy

DividendMap = Mapping[str, Mapping[date, Decimal]]  # symbol -> {ex_date: cash amount per share}

# Book exit reasons in the order RunStats.metrics.exit_reasons lists them (zeros kept). A
# RunResult keeps metrics.EXIT_REASONS ("tp", "sl", "time", "gap"), forced closes inside "time".
BOOK_EXIT_REASONS: tuple[str, ...] = ("tp", "sl", "time", "gap", "signal", "forced")
TRADING_DAYS = 252  # Sharpe annualization: daily mean / daily pstdev x sqrt(252)

_NO_DIVIDENDS: DividendMap = MappingProxyType({})
_ZERO = Decimal("0.0000")


@dataclass(frozen=True)
class BookResult:
    """One book-engine run.

    ``snapshots[0]`` is ``BookSnapshot(prev_session(start), cash0, cash0, 0)``, then one per
    session (after any forced close). ``fills`` is every fill in execution order, forced closes
    included; ``trades`` every closed holding episode in exit order; ``open_at_end`` the
    positions still held after ``end`` (marked, never liquidated). ``dividends_usd`` is the cash
    credited by dividends, ``costs_usd`` the sum of ``Fill.cost_usd``. ``rejections`` counts
    ``step_book`` rejections by reason, sorted by reason.

    ``contributions`` is the schedule the run was funded on, or None (the default, and every
    closed record). ``cashflows`` is ``(session, usd)`` per credited contribution in session
    order -- the dated series a money-weighted return is computed from.
    """

    allocator_id: str
    params: Any
    rules: TradeRules
    start: date
    end: date
    usd_idr: Decimal
    initial_cash: Decimal
    snapshots: tuple[BookSnapshot, ...]
    fills: tuple[Fill, ...]
    trades: tuple[Trade, ...]
    open_at_end: tuple[Position, ...]
    dividends_usd: Decimal
    costs_usd: Decimal
    rejections: tuple[tuple[str, int], ...]
    contributions: Contributions | None = None
    cashflows: tuple[tuple[date, Decimal], ...] = ()


def _session(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    if not dates.is_session(d):
        raise ValueError(f"{name} {d} is not an NYSE session")
    return d


def _rescaled(
    market: Market,
    last_rank: tuple[Target, ...],
    fresh: tuple[Target, ...],
    held: frozenset[str],
    data_date: date,
    marks: Mapping[str, Decimal],
) -> tuple[Target, ...]:
    """The last rank session's basket at today's exposure: the resize-only session's targets.

    Every target of ``last_rank`` whose symbol is still in ``held``, with its weight multiplied by
    ``k = sum(fresh weights) / sum(last_rank weights)`` and its ``last`` refreshed to the symbol's
    close on ``data_date`` (falling back to ``marks``, the book's mark, when it has no bar that
    day). ``limit``, ``stop`` and ``take`` are dropped: a resize session opens no position, so the
    only one of the three that can matter is ``limit``, and a limit priced at the last rank is
    stale. Under entry ``"limit"`` that means a resize session trims but never adds.

    ``k`` is the allocator's own exposure move, read off its totals: for an overlay that scales a
    fixed-width basket (vol targeting) ``k`` is exactly the ratio of the two scales. For an
    allocator whose basket WIDTH varies, ``k`` conflates "fewer names" with "less exposure" —
    such an allocator is a poor fit for a split cadence.

    ``k >= 0`` and ``sum(last_rank) >= sum(kept)``, so the result never weighs more than ``fresh``
    does, and never more than 1. ``()`` when nothing of the basket is still held or the basket
    weighed nothing: with ``fresh`` empty, every weight floors away and the book goes to the idle
    instrument (an exposure cut to zero is a re-scale, not a re-rank).
    """
    kept = tuple(t for t in last_rank if t.symbol in held)
    if not kept:
        return ()
    rank_total = _ZERO
    for t in last_rank:
        rank_total += t.weight
    if rank_total <= 0:
        return ()
    fresh_total = _ZERO
    for t in fresh:
        fresh_total += t.weight
    k = fresh_total / rank_total
    out: list[Target] = []
    for t in kept:
        weight = scale_weight(t.weight, k)
        if weight is None:
            continue
        bar = market.bar(t.symbol, data_date)
        last = q(bar.close) if bar is not None else marks.get(t.symbol, t.last)
        out.append(replace(t, weight=weight, last=last, limit=None, stop=None, take=None))
    return tuple(out)


def _with_idle(
    market: Market, rules: TradeRules, targets: tuple[Target, ...], data_date: date
) -> tuple[tuple[Target, ...], bool]:
    """``targets`` plus the residual idle target when ``rules`` name one, and whether one was added.

    The idle target is ``Target(idle, to_weight(1 - sum(weights)), last=its close on data_date)``,
    appended last (rank order: idle last). None is added when the idle symbol has no bar dated
    ``data_date`` or the weights already sum to 1 or more. An allocator that targets the idle
    symbol itself is a ValueError: the idle weight is the runner's alone.
    """
    idle = rules.idle_symbol
    if idle is None:
        return targets, False
    for t in targets:
        if t.symbol == idle:
            raise ValueError(f"the allocator targets the idle symbol {idle}; its weight is the runner's residual")
    idle_bar = market.bar(idle, data_date)
    if idle_bar is None:
        return targets, False
    total = Decimal(0)
    for t in targets:
        total += t.weight
    residual = Decimal(1) - total
    if residual <= 0:
        return targets, False
    return targets + (Target(symbol=idle, weight=to_weight(residual), last=q(idle_bar.close)),), True


def _dividends_on(dividends: DividendMap, held: Iterable[str], session: date) -> dict[str, Decimal]:
    """``{symbol: amount per share}`` for the ``held`` symbols whose ex-date is ``session``, by symbol."""
    out: dict[str, Decimal] = {}
    for symbol in sorted(held):
        by_date = dividends.get(symbol)
        if by_date is None:
            continue
        amount = by_date.get(session)
        if amount is not None:
            out[symbol] = amount
    return out


def _gone(market: Market, symbol: str, session: date) -> bool:
    """True when ``symbol`` has no bar on ``session`` or later in the loaded data."""
    last = market.last_bar_date(symbol)
    return last is None or last < session


def _invested(book: Book, rules: TradeRules) -> Decimal:
    """``q(sum(shares x mark))`` over the non-idle positions (the exposure numerator)."""
    total = Decimal(0)
    for p in book.positions:
        if p.symbol != rules.idle_symbol:
            total += p.shares * p.mark
    return q(total)


def run_book(
    market: Market,
    allocator: Allocator,
    params: Any,
    rules: TradeRules,
    start: date,
    end: date,
    *,
    prepared: Any = None,
    dividends: DividendMap = _NO_DIVIDENDS,
    initial_idr: Decimal = INITIAL_IDR,
    usd_idr: Decimal | None = None,
    kickoff: date | None = None,
    contributions: Contributions | None = None,
) -> BookResult:
    """Run ``allocator`` with ``params`` under the book rules ``rules`` over every session in ``[start, end]``.

    ``start`` and ``end`` are NYSE sessions, ``start <= end``. Starting cash is
    ``initial_cash_usd(initial_idr, usd_idr)``, with ``usd_idr`` defaulting to
    ``market.usd_idr_on(start)``. With ``prepared`` (``allocator.prepare(market.history)``) the
    targets come from ``targets_prepared``; without it, from ``targets`` on every history cut at
    ``data_date``. The allocator contract makes both give the same result. ``dividends`` maps
    symbol -> {ex_date: cash per share}; only the held symbols' entries for the session being
    stepped are passed on, and only when ``rules.dividends``.

    ``rules.engine`` must be ``"book"``: ``DESIGN_V0`` (``"bracket_v0"``) is a ValueError, run it
    with ``run_rules``.

    ``kickoff``: one extra rank session, off the cadence (paper trading's first decision, see
    ``paper.book.needs_kickoff``). None, the default and every backtest, ranks on the cadence only.

    ``contributions``: the owner's recurring deposit (``sim.contributions``), or None for a lump
    sum -- the default, so every closed record is unchanged. A contribution dated ``d`` is
    credited at the OPEN of the first session on or after ``d``, before ``step_book`` sizes
    anything, so a deposit that lands between rotations sits as idle cash until the next rank
    session -- which is the point: the owner's 25th is a mean of 4.2 sessions before a month-start
    rotation. It raises cash AND equity, because ``step_book`` sizes every target from
    ``book.equity``. It is converted at this run's single rate.
    """
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    if not isinstance(rules, TradeRules):
        raise TypeError(f"rules must be TradeRules, got {type(rules).__name__}")
    if rules.engine != "book":
        raise ValueError(f"rules {rules.id!r} use the {rules.engine} engine; run them with run_rules")
    if not isinstance(allocator, Allocator):
        raise TypeError(f"allocator must be an Allocator, got {type(allocator).__name__}")
    if not isinstance(dividends, Mapping):
        raise TypeError(f"dividends must be a Mapping, got {type(dividends).__name__}")
    if contributions is not None and (
        isinstance(contributions, (str, Mapping))
        or not isinstance(contributions, (ContributionSchedule, Sequence))
    ):
        raise TypeError(
            "contributions must be a ContributionSchedule, a sequence of (date, Decimal) "
            f"pairs or None, got {type(contributions).__name__}"
        )
    _session("start", start)
    _session("end", end)
    if end < start:
        raise ValueError(f"end {end} is before start {start}")
    rate = market.usd_idr_on(start) if usd_idr is None else usd_idr
    cash0 = initial_cash_usd(initial_idr, rate)

    book = new_book(cash0)
    data_date = dates.prev_session(start)
    last_rank: tuple[Target, ...] | None = None  # the last rank session's targets, pre-idle; None = none yet
    snapshots: list[BookSnapshot] = [
        BookSnapshot(date=data_date, cash_usd=book.cash, equity_usd=book.equity, invested_usd=_ZERO)
    ]
    fills: list[Fill] = []
    trades: list[Trade] = []
    rejections: Counter[str] = Counter()
    dividends_usd = _ZERO
    costs_usd = _ZERO
    cashflows: list[tuple[date, Decimal]] = []

    for session in dates.sessions(start, end):
        if contributions is not None:
            credit = credit_for(contributions, data_date, session, rate)
            if credit > 0:
                book = replace(book, cash=book.cash + credit, equity=book.equity + credit)
                cashflows.append((session, credit))
        held = book.held()
        targets: tuple[Target, ...] | None = None
        idle_added = False
        rank = is_rank_session(rules, session) or session == kickoff
        # A resize session before the first rank has no basket to re-scale: it is not a decision.
        if rank or (last_rank is not None and is_resize_session(rules, session)):
            members = market.membership.members_on(data_date)
            # The idle position is the runner's residual, never a family's (plan index D-J).
            mine = held - {rules.idle_symbol} if rules.idle_symbol is not None else held
            if prepared is None:
                history = {s: h.upto(data_date) for s, h in market.history.items()}
                wanted = allocator.targets(history, members, data_date, mine, params)
            else:
                wanted = allocator.targets_prepared(prepared, members, data_date, mine, params)
            if rank:
                last_rank = tuple(wanted)
                basket = last_rank
            else:
                marks = {p.symbol: p.mark for p in book.positions}
                basket = _rescaled(market, last_rank, tuple(wanted), mine, data_date, marks)
            targets, idle_added = _with_idle(market, rules, basket, data_date)

        symbols = set(held)
        if targets is not None:
            symbols.update(t.symbol for t in targets)
        bars = market.bars_on(session, sorted(symbols))
        divs = _dividends_on(dividends, held, session) if rules.dividends else {}

        stepped = step_book(book, session, bars, targets, rules, divs, idle_symbol_ok=idle_added)
        book = stepped.book
        fills.extend(stepped.fills)
        trades.extend(stepped.trades)
        for _, amount in stepped.dividends:
            dividends_usd += amount
        for _, reason in stepped.rejected:
            rejections[reason] += 1
        snapshot = stepped.snapshot

        gone = [p.symbol for p in book.positions if _gone(market, p.symbol, session)]
        if gone:
            book, forced_fills, forced_trades = close_book_unpriced(book, gone, rules)
            fills.extend(forced_fills)
            trades.extend(forced_trades)
            snapshot = BookSnapshot(
                date=session,
                cash_usd=book.cash,
                equity_usd=book.equity,
                invested_usd=_invested(book, rules),
            )
        snapshots.append(snapshot)
        data_date = session

    for f in fills:
        costs_usd += f.cost_usd

    return BookResult(
        allocator_id=allocator.id,
        params=params,
        rules=rules,
        start=start,
        end=end,
        usd_idr=rate,
        initial_cash=cash0,
        snapshots=tuple(snapshots),
        fills=tuple(fills),
        trades=tuple(trades),
        open_at_end=book.positions,
        dividends_usd=dividends_usd,
        costs_usd=costs_usd,
        rejections=tuple(sorted(rejections.items())),
        contributions=contributions,
        cashflows=tuple(cashflows),
    )


def run_rules(
    market: Market,
    strategy_or_allocator: Strategy | Allocator,
    params: Any,
    rules: TradeRules,
    start: date,
    end: date,
    *,
    prepared: Any = None,
    dividends: DividendMap = _NO_DIVIDENDS,
    usd_idr: Decimal | None = None,
    kickoff: date | None = None,
    initial_idr: Decimal = INITIAL_IDR,
    contributions: Contributions | None = None,
) -> RunResult | BookResult:
    """Run under ``rules``: the single dispatch every P7a caller uses.

    - ``rules.engine == "bracket_v0"`` (only ``DESIGN_V0``) with a ``Strategy``:
      ``run_backtest(market, strategy, params, start, end, prepared=prepared)`` unchanged.
      ``dividends`` are ignored (``DESIGN_V0.dividends`` is False). ``usd_idr`` must be None or
      equal ``market.usd_idr_on(start)`` (ValueError otherwise): ``run_backtest`` always converts
      at that rate.
    - ``rules.engine == "book"`` with an ``Allocator``: ``run_book`` with every argument.
    - ``kickoff`` is a book argument; with bracket rules it must be None (ValueError).
    - any other pairing: TypeError.
    """
    if not isinstance(rules, TradeRules):
        raise TypeError(f"rules must be TradeRules, got {type(rules).__name__}")
    if is_bracket(rules):
        if not isinstance(strategy_or_allocator, Strategy):
            raise TypeError(
                f"rules {rules.id!r} run a bracket Strategy, got {type(strategy_or_allocator).__name__}"
            )
        if not isinstance(market, Market):
            raise TypeError(f"market must be a Market, got {type(market).__name__}")
        if usd_idr is not None and usd_idr != market.usd_idr_on(start):
            raise ValueError(
                f"rules {rules.id!r} convert at market.usd_idr_on(start) = {market.usd_idr_on(start)}, got {usd_idr}"
            )
        if kickoff is not None:
            raise ValueError(f"rules {rules.id!r} rank no book; kickoff must be None, got {kickoff}")
        return run_backtest(
            market,
            strategy_or_allocator,
            params,
            start,
            end,
            prepared=prepared,
            initial_idr=initial_idr,
            contributions=contributions,
            rules=rules,
        )
    if not isinstance(strategy_or_allocator, Allocator):
        raise TypeError(f"rules {rules.id!r} run an Allocator, got {type(strategy_or_allocator).__name__}")
    return run_book(
        market,
        strategy_or_allocator,
        params,
        rules,
        start,
        end,
        prepared=prepared,
        dividends=dividends,
        usd_idr=usd_idr,
        kickoff=kickoff,
        initial_idr=initial_idr,
        contributions=contributions,
    )


# --------------------------------------------------------------------------- run statistics


@dataclass(frozen=True)
class RunStats:
    """What the dev report needs from either result type.

    - ``metrics``: ``metrics.run_metrics`` for a RunResult; for a BookResult
      ``strategy_metrics(snapshots, pnls of the non-idle trades)`` plus ``avg_days_held`` and
      ``exit_reasons`` (``BOOK_EXIT_REASONS`` order, zeros kept), both over the non-idle trades.
    - ``exposure``: mean over the sessions (``snapshots[1:]``) of invested / equity, where
      invested is ``BookSnapshot.invested_usd`` (idle instrument excluded) or, for a RunResult,
      ``equity - cash``.
    - ``turnover``: sum of fill notionals (price x shares, buys and sells, idle and forced fills
      included) / mean session equity / years, years = calendar days from ``snapshots[0]`` to
      ``snapshots[-1]`` / 365.25.
    - ``costs_usd``: every fee paid (``sum(Fill.cost_usd)``, which is already the rule set's
      cost model: Gotrade's schedule under ``cost_model="gotrade"``; for a RunResult, always
      ``DESIGN_V0``'s flat rate, ``q(price x shares x COST_RATE)`` per fill and exit).
    - ``gross_pnl_usd``: sum of the non-idle closed trades' pnl plus the fees of their own fills.
    - ``cost_drag``: those trades' fees / ``gross_pnl_usd`` when gross > 0, else None.
    - ``dividends_usd``: cash dividends credited (0 for a RunResult).
    - ``daily_returns``: ``equity[i] / equity[i-1] - 1`` over consecutive snapshots.
    - ``sharpe``: mean / population stdev of ``daily_returns`` x sqrt(252); None with fewer than
      2 returns or a zero stdev.
    - ``year_returns``: per calendar year of ``snapshots[1:]``, ascending, the last equity of the
      year over the last equity of the year before (``snapshots[0]`` for the first year), minus 1.
    - ``worst_year``: the lowest year return (ties: the earlier year), None when there is none.
    """

    metrics: Metrics
    exposure: float
    turnover: float
    costs_usd: float
    gross_pnl_usd: float
    cost_drag: float | None
    dividends_usd: float
    sharpe: float | None
    daily_returns: tuple[float, ...]
    year_returns: tuple[tuple[int, float], ...]
    worst_year: tuple[int, float] | None


def _fsum(values: Iterable[float]) -> float:
    """Left-to-right float sum from 0.0 (never ``sum``/``math.fsum``), as ``metrics._sum``."""
    total = 0.0
    for v in values:
        total += v
    return total


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("mean of no values")
    return _fsum(values) / len(values)


def _equities(snapshots: Sequence[tuple[date, Decimal, Decimal]]) -> list[tuple[date, float]]:
    """``(date, float equity)`` per snapshot; ValueError on fewer than 2 snapshots or equity <= 0."""
    if len(snapshots) < 2:
        raise ValueError(f"a run has at least 2 snapshots, got {len(snapshots)}")
    out: list[tuple[date, float]] = []
    for d, _, equity in snapshots:
        if equity <= 0:
            raise ValueError(f"equity on {d} must be > 0, got {equity}")
        out.append((d, float(equity)))
    return out


def _daily_returns(equity: Sequence[tuple[date, float]]) -> tuple[float, ...]:
    return tuple(cur / prev - 1.0 for (_, prev), (_, cur) in zip(equity, equity[1:]))


def _sharpe(returns: Sequence[float]) -> float | None:
    n = len(returns)
    if n < 2:
        return None
    mean = _fsum(returns) / n
    var = _fsum((r - mean) ** 2 for r in returns) / n
    sd = math.sqrt(var)
    if sd == 0.0:
        return None
    return mean / sd * math.sqrt(TRADING_DAYS)


def _year_returns(equity: Sequence[tuple[date, float]]) -> tuple[tuple[int, float], ...]:
    last_of_year: dict[int, float] = {}
    for d, value in equity[1:]:
        last_of_year[d.year] = value  # snapshots ascend, so the last one of a year wins
    out: list[tuple[int, float]] = []
    base = equity[0][1]
    for year in sorted(last_of_year):
        value = last_of_year[year]
        out.append((year, value / base - 1.0))
        base = value
    return tuple(out)


def _turnover(notional: Decimal, equity: Sequence[tuple[date, float]]) -> float:
    years = (equity[-1][0] - equity[0][0]).days / YEAR_DAYS
    mean_equity = _mean([value for _, value in equity[1:]])
    if years <= 0 or mean_equity <= 0:
        return 0.0
    return float(notional) / mean_equity / years


def _fee(side: Side, price: Decimal, shares: Decimal | int, rules: TradeRules = DESIGN_V0) -> Decimal:
    """The fee part of one bracket-simulator fill, priced by ``rules``.

    An ``Order`` has no cost column, so a bracket run's fees are re-derived here for the metrics.
    Under ``DESIGN_V0`` -- the default and every caller until phase 12 wires a Gotrade entry --
    ``sim.charges.order_fee`` is ``q(price x shares x rules.cost_rate)`` with
    ``cost_rate == COST_RATE``, so this is bit-identical to the flat form it replaces. Under
    ``cost_model="gotrade"`` the flat form understates, and ``side`` starts to matter: Gotrade
    charges more on a sell. Book fills carry their own ``Fill.cost_usd`` and never come here.
    """
    return order_fee(side, price, int(shares), rules)


def _assemble(
    metrics: Metrics,
    equity: Sequence[tuple[date, float]],
    exposures: Sequence[float],
    notional: Decimal,
    costs: Decimal,
    trade_pnl: Decimal,
    trade_fees: Decimal,
    dividends: Decimal,
) -> RunStats:
    gross = trade_pnl + trade_fees
    returns = _daily_returns(equity)
    years = _year_returns(equity)
    worst = min(years, key=lambda yr: (yr[1], yr[0])) if years else None
    return RunStats(
        metrics=metrics,
        exposure=_mean(exposures),
        turnover=_turnover(notional, equity),
        costs_usd=float(costs),
        gross_pnl_usd=float(gross),
        cost_drag=float(trade_fees) / float(gross) if gross > 0 else None,
        dividends_usd=float(dividends),
        sharpe=_sharpe(returns),
        daily_returns=returns,
        year_returns=years,
        worst_year=worst,
    )


def _run_result_stats(r: RunResult, rules: TradeRules = DESIGN_V0) -> RunStats:
    equity = _equities([(s.date, s.cash_usd, s.equity_usd) for s in r.snapshots])
    exposures = [float(s.equity_usd - s.cash_usd) / float(s.equity_usd) for s in r.snapshots[1:]]
    notional = _ZERO
    costs = _ZERO
    for e in r.events:
        if e.kind == "fill" and e.order.fill_price is not None:
            price = e.order.fill_price
        elif e.kind == "exit" and e.order.exit_price is not None:
            price = e.order.exit_price
        else:
            continue
        notional += price * e.order.shares
        costs += _fee("buy" if e.kind == "fill" else "sell", price, e.order.shares, rules)
    trade_pnl = _ZERO
    trade_fees = _ZERO
    for o in r.closed:
        if o.fill_price is None or o.exit_price is None or o.pnl_usd is None:
            raise ValueError(f"closed order {o.symbol} lacks a fill, an exit or a pnl")
        trade_pnl += o.pnl_usd
        trade_fees += _fee("buy", o.fill_price, o.shares, rules) + _fee(
            "sell", o.exit_price, o.shares, rules
        )
    return _assemble(run_metrics(r), equity, exposures, notional, costs, trade_pnl, trade_fees, _ZERO)


def _book_metrics(snaps: Sequence[tuple[date, float]], trades: Sequence[Trade]) -> Metrics:
    base = strategy_metrics(snaps, [float(t.pnl_usd) for t in trades])
    counts = {reason: 0 for reason in BOOK_EXIT_REASONS}
    days = 0
    for t in trades:
        if t.exit_reason not in counts:
            raise ValueError(f"trade {t.symbol} has exit_reason {t.exit_reason!r}, not one of {BOOK_EXIT_REASONS}")
        counts[t.exit_reason] += 1
        days += t.days_held
    return replace(
        base,
        avg_days_held=days / len(trades) if trades else None,
        exit_reasons=tuple((reason, counts[reason]) for reason in BOOK_EXIT_REASONS),
    )


def _book_result_stats(r: BookResult) -> RunStats:
    equity = _equities([(s.date, s.cash_usd, s.equity_usd) for s in r.snapshots])
    exposures = [float(s.invested_usd) / float(s.equity_usd) for s in r.snapshots[1:]]
    notional = _ZERO
    fees_by_symbol: dict[str, list[tuple[date, Decimal]]] = {}
    for f in r.fills:
        notional += f.price * f.shares
        fees_by_symbol.setdefault(f.symbol, []).append((f.session_date, f.cost_usd))
    trades = [t for t in r.trades if not t.idle]
    trade_pnl = _ZERO
    trade_fees = _ZERO
    for t in trades:
        trade_pnl += t.pnl_usd
        # An episode's fills are its symbol's fills dated entry_date..exit_date: episodes of one
        # symbol never share a date (no re-entry on an exit session; a forced close needs no bar).
        for d, fee in fees_by_symbol.get(t.symbol, ()):
            if t.entry_date <= d <= t.exit_date:
                trade_fees += fee
    return _assemble(
        _book_metrics(equity, trades), equity, exposures, notional, r.costs_usd, trade_pnl, trade_fees, r.dividends_usd
    )


def run_stats(r: RunResult | BookResult, rules: TradeRules = DESIGN_V0) -> RunStats:
    """``RunStats`` of a ``run_backtest`` or ``run_book`` result (see ``RunStats``).

    ``rules`` prices a ``RunResult``'s fees, which the bracket simulator does not record per
    fill. It defaults to ``DESIGN_V0``, the rule set every closed record ran at, so every number
    is bit-identical unless a caller passes the Gotrade schedule. A ``BookResult`` carries its own
    ``rules`` and its fills carry their own cost, so the argument is ignored for one.
    """
    if isinstance(r, BookResult):
        return _book_result_stats(r)
    if isinstance(r, RunResult):
        return _run_result_stats(r, rules)
    raise TypeError(f"r must be a RunResult or a BookResult, got {type(r).__name__}")
