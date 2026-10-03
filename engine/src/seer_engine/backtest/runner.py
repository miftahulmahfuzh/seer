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

from collections import Counter
from dataclasses import dataclass
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
from seer_engine.strategies.base import Strategy

INITIAL_IDR = Decimal("20000000")


@dataclass(frozen=True)
class RunResult:
    """One backtest run.

    ``snapshots[0]`` is ``Snapshot(prev_session(start), cash0, cash0)``, then one per session
    (after any forced close). ``events`` is every simulator event in order, forced closes
    included. ``closed`` is every closed order in exit order; ``open_at_end`` the positions
    still open after ``end``. ``rejections`` counts ``size_picks`` rejections by reason,
    sorted by reason.
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


def _session(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    if not dates.is_session(d):
        raise ValueError(f"{name} {d} is not an NYSE session")
    return d


def run_backtest(
    market: Market,
    strategy: Strategy,
    params: Any,
    start: date,
    end: date,
    *,
    prepared: Any = None,
    initial_idr: Decimal = INITIAL_IDR,
) -> RunResult:
    """Run ``strategy`` with ``params`` on a fresh portfolio over every session in ``[start, end]``.

    ``start`` and ``end`` must be NYSE sessions, ``start <= end``. Starting cash is
    ``initial_cash_usd(initial_idr, market.usd_idr_on(start))``. With ``prepared`` (the value of
    ``strategy.prepare(market.history)``), picks come from ``strategy.picks_prepared``;
    without it, from ``strategy.picks`` on every history cut at ``data_date``. The strategy
    contract makes both give the same result.
    """
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    _session("start", start)
    _session("end", end)
    if end < start:
        raise ValueError(f"end {end} is before start {start}")
    usd_idr = market.usd_idr_on(start)
    cash0 = initial_cash_usd(initial_idr, usd_idr)

    pf = new_portfolio(cash0)
    data_date = dates.prev_session(start)
    snapshots: list[Snapshot] = [Snapshot(data_date, pf.cash, pf.equity)]
    events: list[Event] = []
    rejections: Counter[str] = Counter()

    for session in dates.sessions(start, end):
        members = market.membership.members_on(data_date)
        if prepared is None:
            history = {s: h.upto(data_date) for s, h in market.history.items()}
            picks = strategy.picks(history, members, data_date, params)
        else:
            picks = strategy.picks_prepared(prepared, members, data_date, params)

        sized = size_picks(pf, picks, session)
        for r in sized.rejected:
            rejections[r.reason] += 1
        pf = sized.portfolio

        result = step(pf, session, market.bars_on(session, pf.held_symbols()))
        pf = result.portfolio
        events.extend(result.events)
        snapshots.append(result.snapshot)

        gone = []
        for o in pf.open_orders():
            last = market.last_bar_date(o.symbol)
            if last is None or last < session:
                gone.append(o.symbol)
        if gone:
            pf, forced = close_unpriced(pf, gone)
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
