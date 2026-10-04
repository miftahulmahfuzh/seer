"""One paper night of a bracket strategy (design-§5 brackets, ``DESIGN_V0``): the loop body of
``backtest.runner.run_backtest`` split at the night boundary.

Pure: no database, network, clock or randomness. The runner steps session S as

    size_picks(pf, picks(data_date = prev_session(S)), S) -> step(S) -> close_unpriced(gone)

and the nightly paper job, which only knows S's bars after S's close, steps it as two calls on
two nights:

- night of ``prev_session(S)``: :func:`decide_bracket` (the strategy's picks on history cut at
  ``data_date``, sized into ``pf`` as pending orders for ``next_session(data_date) = S``);
- night of ``S``: :func:`settle_bracket` (splits executing on S, then ``sim.step``, then the
  forced close of open positions whose symbol has no bar on S or later).

Looping ``decide_bracket`` + ``settle_bracket`` over a window gives exactly ``run_backtest``'s
snapshots, events, closed orders, open orders and rejections (tests/test_paper_bracket.py).

Splits are the one thing the runner never sees (its bars are split-adjusted already). Live state
is kept in the units it was sized in, so a split executing on S that ``nightly`` applied to the
stored bars (``split_adjustments.applied``) is applied to the portfolio exactly once, here,
before S is stepped (``sim.apply_split``; package docstring of ``seer_engine.sim``).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence, Set
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from seer_engine import dates
from seer_engine.prices import Bar
from seer_engine.sim import (
    Event,
    Order,
    Portfolio,
    SizingResult,
    Snapshot,
    apply_split,
    close_unpriced,
    size_picks,
    step,
)
from seer_engine.strategies.base import History, Strategy

LastBarDate = Callable[[str], date | None]


@dataclass(frozen=True, slots=True)
class BracketNight:
    """One settled session of a bracket strategy.

    - ``portfolio``: the state after the session (live orders only, ``last_session = session``).
    - ``events``: every simulator event of the session, in this order: split events (splits by
      symbol, each in slot order), then ``sim.step``'s exits, fills and expiries, then the
      forced closes of gone symbols (slot order).
    - ``snapshot``: the session's ``equity_snapshots`` row, after any forced close (the runner
      replaces the step's snapshot the same way).
    """

    session: date
    portfolio: Portfolio
    events: tuple[Event, ...]
    snapshot: Snapshot

    @property
    def closed(self) -> tuple[Order, ...]:
        """The orders closed on this session (exit events, forced included), in event order."""
        return tuple(e.order for e in self.events if e.kind == "exit")

    @property
    def expired(self) -> tuple[Order, ...]:
        """The pending orders that expired on this session, in event order."""
        return tuple(e.order for e in self.events if e.kind == "expire")


def _session(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    if not dates.is_session(d):
        raise ValueError(f"{name} {d} is not an NYSE session")
    return d


def _splits(splits: Sequence[tuple[str, Decimal]]) -> list[tuple[str, Decimal]]:
    """``splits`` validated and sorted by symbol (one split per symbol and session)."""
    if isinstance(splits, (str, bytes)) or not isinstance(splits, Sequence):
        raise TypeError(f"splits must be a sequence of (symbol, factor), got {type(splits).__name__}")
    out: dict[str, Decimal] = {}
    for item in splits:
        if not (isinstance(item, tuple) and len(item) == 2):
            raise TypeError(f"a split is (symbol, factor), got {item!r}")
        symbol, factor = item
        if not isinstance(symbol, str):
            raise TypeError(f"split symbol must be a str, got {type(symbol).__name__}")
        if not symbol:
            raise ValueError("empty split symbol")
        if not isinstance(factor, Decimal):
            raise TypeError(f"split factor for {symbol} must be a Decimal, got {type(factor).__name__}")
        if symbol in out:
            raise ValueError(f"two splits for {symbol} on one session")
        out[symbol] = factor
    return sorted(out.items())


def settle_bracket(
    pf: Portfolio,
    session: date,
    bars: Mapping[str, Bar],
    splits: Sequence[tuple[str, Decimal]],
    last_bar_date: LastBarDate,
) -> BracketNight:
    """Settle ``session`` for a bracket portfolio, exactly like one ``run_backtest`` iteration
    after its ``size_picks``.

    ``pf`` holds the pending orders decided for ``session`` (``decide_bracket`` the night
    before). ``bars`` maps symbol -> that session's split-adjusted ``Bar`` (at least every live
    symbol that has one; others are ignored). ``splits`` lists ``(symbol, factor)`` for every
    split executing on ``session`` that was applied to the stored bars, ``factor =
    split_to / split_from``; each is applied with ``sim.apply_split`` before the step, in symbol
    order. ``last_bar_date(symbol)`` is the date of the symbol's last known bar (None when it has
    none): an open position whose symbol has no bar on ``session`` or later is force-closed at
    its mark after the step (``sim.close_unpriced``), and the snapshot is replaced by the
    post-close one.

    Raises what the simulator raises: TypeError on wrong types, ValueError when ``session`` is
    not a session after ``pf.last_session``, a pending order is for another session, or a split
    factor is not a split ratio.
    """
    if not isinstance(pf, Portfolio):
        raise TypeError(f"pf must be a Portfolio, got {type(pf).__name__}")
    _session("session", session)
    if not callable(last_bar_date):
        raise TypeError("last_bar_date must be callable: symbol -> date | None")
    ordered = _splits(splits)

    events: list[Event] = []
    for symbol, factor in ordered:
        pf, split_events = apply_split(pf, symbol, factor, session)
        events.extend(split_events)

    result = step(pf, session, bars)
    pf = result.portfolio
    events.extend(result.events)
    snapshot = result.snapshot

    gone = []
    for o in pf.open_orders():
        last = last_bar_date(o.symbol)
        if last is None or last < session:
            gone.append(o.symbol)
    if gone:
        pf, forced = close_unpriced(pf, gone)
        events.extend(forced)
        snapshot = Snapshot(session, pf.cash, pf.equity)

    return BracketNight(session=session, portfolio=pf, events=tuple(events), snapshot=snapshot)


def decide_bracket(
    pf: Portfolio,
    strategy: Strategy,
    params: Any,
    history: Mapping[str, History],
    members: Set[str],
    data_date: date,
) -> SizingResult:
    """The pending orders for ``next_session(data_date)``: ``strategy.picks`` on ``history`` cut
    at ``data_date`` (the ``prepared=None`` path of ``run_backtest``), sized into ``pf`` with
    ``sim.size_picks``.

    ``members`` is the point-in-time universe on ``data_date``. ``pf`` must be the portfolio
    after ``data_date`` was settled (``pf.last_session == data_date``), or a fresh portfolio
    (``last_session`` None) on the night before the first paper session. Bars dated after
    ``data_date`` are never read (no look-ahead).
    """
    if not isinstance(pf, Portfolio):
        raise TypeError(f"pf must be a Portfolio, got {type(pf).__name__}")
    _session("data_date", data_date)
    if pf.last_session is not None and pf.last_session != data_date:
        raise ValueError(
            f"data_date {data_date} is not the portfolio's last settled session {pf.last_session}"
        )
    if not isinstance(history, Mapping):
        raise TypeError(f"history must be a Mapping, got {type(history).__name__}")
    cut = {s: h.upto(data_date) for s, h in history.items()}
    picks = strategy.picks(cut, members, data_date, params)
    return size_picks(pf, picks, dates.next_session(data_date))
