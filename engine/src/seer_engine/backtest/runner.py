"""The backtest session loop around the simulator, and the survivorship count (P3, handover §2.2).

Pure. ``run_backtest`` is the readme's "Simulator: P3 backtest loop", verbatim in shape: for
every NYSE session S in ``[start, end]``

1. the strategy picks from the point-in-time universe on ``data_date = prev_session(S)``
   with history through ``data_date`` only;
2. ``sim.size_picks(pf, picks, S)``;
3. ``sim.step(pf, S, bars on S for every live symbol)``;
4. every open position whose symbol has no bar on S or later in the loaded data is gone:
   ``sim.close_unpriced`` right after S's step, and S's snapshot is replaced by the
   post-close one. A halt (bars resume later) is left to the simulator's missing-bar rule.

Sizing, fills, exits and costs all happen inside ``seer_engine.sim``; nothing here does money
arithmetic. Positions still open after ``end`` are marked at the close, never liquidated.

``survivorship`` counts the (member, session) pairs that have no bar, per calendar year, split
into members never fetched at all and members missing a bar on that session.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine import dates
from seer_engine.backtest.market import Market
from seer_engine.sim import (
    Event,
    Order,
    Snapshot,
    close_unpriced,
    initial_cash_usd,
    new_portfolio,
    size_picks,
    step,
)
from seer_engine.sim.contributions import (
    ContributionSchedule,
    Contributions,
    credit_for,
)
from seer_engine.sim.rules import DESIGN_V0, TradeRules
from seer_engine.strategies.base import Strategy

#: The owner's real Gotrade capital, the same number ``paper.capital.PAPER_INITIAL_IDR`` holds.
#: It was 20,000,000 while every simulated fee was a flat percentage, where only ratios matter.
#: Gotrade's measured schedule has a $0.10 per-order floor, so the rate depends on the slot:
#: at 17,841 IDR/USD over 20 names a 10M book pays 1.035% round trip and a 20M book 0.660%.
#: Measuring at 20M would price a cheaper world than the owner lives in.
INITIAL_IDR = Decimal("10000000")


@dataclass(frozen=True)
class RunResult:
    """One backtest run.

    ``snapshots[0]`` is ``Snapshot(prev_session(start), cash0, cash0)``, then one per session
    (after any forced close). ``events`` is every simulator event in order, forced closes
    included. ``closed`` is every closed order in exit order; ``open_at_end`` the positions
    still open after ``end``. ``rejections`` counts ``size_picks`` rejections by reason,
    sorted by reason.

    ``contributions`` is the schedule the run was funded on, or None (the default, and every
    closed record). ``cashflows`` is ``(session, usd)`` per credited contribution in session
    order -- the dated series a money-weighted return is computed from. A contribution is money
    arriving, never a return: it raises cash and equity on its session and nothing else.
    """

    strategy_id: str
    params: Any
    start: date
    end: date
    usd_idr: Decimal
    initial_cash: Decimal
    snapshots: tuple[Snapshot, ...]
    events: tuple[Event, ...]
    closed: tuple[Order, ...]
    open_at_end: tuple[Order, ...]
    rejections: tuple[tuple[str, int], ...]
    contributions: Contributions | None = None
    cashflows: tuple[tuple[date, Decimal], ...] = ()


def _session(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    if not dates.is_session(d):
        raise ValueError(f"{name} {d} is not an NYSE session")
    return d


@dataclass(frozen=True)
class ParamsSchedule:
    """Strategy params that change by traded session (P3b walk-forward, Decision D1/D6).

    ``segments[i] = (first_session_i, params_i)``: ``params_i`` is used for every traded session
    from ``first_session_i`` up to the session before ``first_session_{i+1}`` (the last segment
    runs to the end of the window). First sessions are NYSE sessions, strictly ascending, and
    there is at least one segment. A list or other sequence is accepted and stored as a tuple
    of 2-tuples. A segment's params may not itself be a ``ParamsSchedule``.
    """

    segments: tuple[tuple[date, Any], ...]

    def __post_init__(self) -> None:
        raw = self.segments
        if isinstance(raw, (str, bytes)) or not hasattr(raw, "__iter__"):
            raise TypeError(f"segments must be a sequence of (date, params), got {type(raw).__name__}")
        segments: list[tuple[date, Any]] = []
        for i, seg in enumerate(raw):
            if isinstance(seg, (str, bytes)) or not hasattr(seg, "__len__") or len(seg) != 2:
                raise TypeError(f"segments[{i}] must be a (first_session, params) pair")
            first, params = seg[0], seg[1]
            _session(f"segments[{i}] first session", first)
            if isinstance(params, ParamsSchedule):
                raise TypeError(f"segments[{i}] params must not be a ParamsSchedule")
            if segments and first <= segments[-1][0]:
                raise ValueError(
                    f"segments[{i}] first session {first} is not after segments[{i - 1}] ({segments[-1][0]})"
                )
            segments.append((first, params))
        if not segments:
            raise ValueError("a ParamsSchedule needs at least one segment")
        object.__setattr__(self, "segments", tuple(segments))

    def at(self, session: date) -> Any:
        """The params of the last segment whose first session is ``<= session``.

        ``session`` must be a ``date`` (not a ``datetime``); ValueError when it is before the
        first segment's first session.
        """
        if isinstance(session, datetime) or not isinstance(session, date):
            raise TypeError(f"session must be a date, got {type(session).__name__}")
        i = bisect_right([first for first, _ in self.segments], session)
        if i == 0:
            raise ValueError(f"session {session} is before the schedule's first session {self.segments[0][0]}")
        return self.segments[i - 1][1]


def run_backtest(
    market: Market,
    strategy: Strategy,
    params: Any,
    start: date,
    end: date,
    *,
    prepared: Any = None,
    initial_idr: Decimal = INITIAL_IDR,
    contributions: Contributions | None = None,
    rules: TradeRules = DESIGN_V0,
) -> RunResult:
    """Run ``strategy`` with ``params`` on a fresh portfolio over every session in ``[start, end]``.

    ``start`` and ``end`` must be NYSE sessions, ``start <= end``. Starting cash is
    ``initial_cash_usd(initial_idr, market.usd_idr_on(start))``. With ``prepared`` (the value of
    ``allocator.prepare_for(strategy, market)`` -- ``strategy.prepare(market.history)`` unless
    the strategy is ``MarketAware``), picks come from ``strategy.picks_prepared``;
    without it, from ``strategy.picks`` on every history cut at ``data_date``. The strategy
    contract makes both give the same result.

    ``params`` may be a ``ParamsSchedule``: then ``start`` must not be before its first
    segment, and the picks for session S use ``params.at(S)``, keyed by the session being
    traded, not by ``data_date``. Orders keep the bracket they were placed with; the simulator
    never rewrites one. ``RunResult.params`` is the schedule itself. Any other ``params`` value
    is handed to the strategy unchanged for every session.

    ``contributions``: the owner's recurring deposit (``sim.contributions``), or None for a lump
    sum -- the default, so every existing caller and every closed record is unchanged. A
    contribution dated ``d`` is credited at the OPEN of the first session on or after ``d``,
    before that session's sizing, so the money is deployable the moment it lands and sits as idle
    cash until the strategy next buys. It raises cash AND equity (the slot budget is
    ``q(equity / SLOTS)``: crediting cash alone would leave the deposit under-deployed for good).
    It is converted at this run's single ``usd_idr``, the rate the starting capital used.

    ``rules`` prices every buy, fill and exit: ``DESIGN_V0`` (the default) is the flat 0.1% a side
    every closed §5 record was run at, ``DESIGN_V0_GOTRADE`` is Gotrade's measured schedule
    including its $0.10 per-order minimum. It is passed straight to ``sim.size_picks``,
    ``sim.step`` and ``sim.close_unpriced``; a book or fractional rule set raises there
    (``sim.charges.bracket_rules``).
    """
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    _session("start", start)
    _session("end", end)
    if end < start:
        raise ValueError(f"end {end} is before start {start}")
    if contributions is not None and (
        isinstance(contributions, (str, Mapping))
        or not isinstance(contributions, (ContributionSchedule, Sequence))
    ):
        raise TypeError(
            "contributions must be a ContributionSchedule, a sequence of (date, Decimal) "
            f"pairs or None, got {type(contributions).__name__}"
        )
    schedule = params if isinstance(params, ParamsSchedule) else None
    if schedule is not None and start < schedule.segments[0][0]:
        raise ValueError(f"start {start} is before the schedule's first session {schedule.segments[0][0]}")
    usd_idr = market.usd_idr_on(start)
    cash0 = initial_cash_usd(initial_idr, usd_idr)

    pf = new_portfolio(cash0)
    data_date = dates.prev_session(start)
    snapshots: list[Snapshot] = [Snapshot(data_date, pf.cash, pf.equity)]
    events: list[Event] = []
    rejections: Counter[str] = Counter()
    cashflows: list[tuple[date, Decimal]] = []

    for session in dates.sessions(start, end):
        if contributions is not None:
            credit = credit_for(contributions, data_date, session, usd_idr)
            if credit > 0:
                pf = replace(pf, cash=pf.cash + credit, equity=pf.equity + credit)
                cashflows.append((session, credit))
        members = market.membership.members_on(data_date)
        session_params = params if schedule is None else schedule.at(session)
        if prepared is None:
            history = {s: h.upto(data_date) for s, h in market.history.items()}
            picks = strategy.picks(history, members, data_date, session_params)
        else:
            picks = strategy.picks_prepared(prepared, members, data_date, session_params)

        sized = size_picks(pf, picks, session, rules=rules)
        for r in sized.rejected:
            rejections[r.reason] += 1
        pf = sized.portfolio

        result = step(pf, session, market.bars_on(session, pf.held_symbols()), rules=rules)
        pf = result.portfolio
        events.extend(result.events)
        snapshots.append(result.snapshot)

        gone = []
        for o in pf.open_orders():
            last = market.last_bar_date(o.symbol)
            if last is None or last < session:
                gone.append(o.symbol)
        if gone:
            pf, forced = close_unpriced(pf, gone, rules=rules)
            events.extend(forced)
            snapshots[-1] = Snapshot(session, pf.cash, pf.equity)

        data_date = session

    return RunResult(
        strategy_id=strategy.id,
        params=params,
        start=start,
        end=end,
        usd_idr=usd_idr,
        initial_cash=cash0,
        snapshots=tuple(snapshots),
        events=tuple(events),
        closed=tuple(e.order for e in events if e.kind == "exit"),
        open_at_end=pf.open_orders(),
        rejections=tuple(sorted(rejections.items())),
        contributions=contributions,
        cashflows=tuple(cashflows),
    )


@dataclass(frozen=True)
class YearGap:
    """Survivorship gap in one calendar year: (member, session) pairs and those with no bar.

    ``missing = missing_never_fetched + missing_other``. ``missing_never_fetched`` counts pairs
    whose symbol has no bars at all in the loaded data (delisted or acquired before the
    backfill could fetch it); ``missing_other`` counts pairs whose symbol has bars, just not on
    that session.
    """

    year: int
    member_sessions: int
    missing: int
    missing_never_fetched: int
    missing_other: int


def survivorship(market: Market, start: date, end: date) -> tuple[YearGap, ...]:
    """Per calendar year, ascending: how many (member on S, session S) pairs in ``[start, end]``
    have no bar on S. Membership is taken on the session itself. Years without a session are
    left out."""
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    sess = dates.sessions(start, end)
    if not sess:
        return ()
    sess64 = np.array(sess, dtype="datetime64[D]")
    year_list = sorted({d.year for d in sess})
    year_idx = np.array([year_list.index(d.year) for d in sess], dtype=np.int64)
    n_years = len(year_list)
    member = np.zeros(n_years, dtype=np.int64)
    never = np.zeros(n_years, dtype=np.int64)
    other = np.zeros(n_years, dtype=np.int64)

    by_symbol: dict[str, list[tuple[date, date | None]]] = {}
    for symbol, a, b in market.membership.intervals:
        by_symbol.setdefault(symbol, []).append((a, b))

    for symbol in sorted(by_symbol):
        mask = np.zeros(len(sess), dtype=bool)
        for a, b in by_symbol[symbol]:
            inside = sess64 >= np.datetime64(a, "D")
            if b is not None:
                inside &= sess64 < np.datetime64(b, "D")
            mask |= inside
        if not mask.any():
            continue
        member += np.bincount(year_idx[mask], minlength=n_years)
        h = market.history.get(symbol)
        if h is None or len(h) == 0:
            never += np.bincount(year_idx[mask], minlength=n_years)
            continue
        pos = np.searchsorted(h.dates, sess64)
        has = (pos < len(h)) & (h.dates[np.minimum(pos, len(h) - 1)] == sess64)
        other += np.bincount(year_idx[mask & ~has], minlength=n_years)

    return tuple(
        YearGap(
            year=y,
            member_sessions=int(member[i]),
            missing=int(never[i] + other[i]),
            missing_never_fetched=int(never[i]),
            missing_other=int(other[i]),
        )
        for i, y in enumerate(year_list)
    )
