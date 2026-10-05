"""The book engine's night: one paper session of a book strategy (R1, plan contract C3).

Pure (purity-tested with every ``paper/*.py`` except ``store.py``): no database, network,
clock, randomness, logging or file access. Paper trading runs ``backtest.book_runner.run_book``'s
loop body one session at a time, over state persisted between nights, in two halves:

``decide_book`` (the night of ``data_date``, after its bars arrived) is ``run_book``'s step 1 and
2 for ``S = next_session(data_date)``: ``None`` when ``S`` is not a decision session under
``rules``; otherwise ``allocator.targets`` on every history cut at ``data_date``, the members on
``data_date`` and the symbols held at night minus the idle instrument, then
``book_runner._with_idle`` (imported, not copied). It returns ``(targets, idle_added)``; the
caller persists both and hands them back to ``settle_book`` for ``S``.

``settle_book`` (the night of ``S``, after S's bars arrived) is ``run_book``'s steps 3 and 4 for
``S``, preceded by the splits that executed on ``S``:

1. each ``(symbol, factor)`` in ``splits``, in symbol order: ``sim.book.apply_book_split``, which
   rewrites the book and the targets decided for ``S`` (they were priced the night before, in
   pre-split units) into post-split units;
2. ``step_book`` with ``bars`` (S's bars; extra symbols are ignored) and, when
   ``rules.dividends``, the cash dividends whose ex-date is ``S`` for the symbols held after the
   splits (``book_runner._dividends_on``, the runner's selection);
3. every position whose ``last_bar_date(symbol)`` is None or before ``S`` is force-closed at its
   mark (``close_book_unpriced``) and S's snapshot is replaced, exactly as ``run_book`` does.

Looping ``decide_book`` then ``settle_book`` from ``new_book(cash0)`` with ``data_date =
prev_session(start)`` and no splits reproduces ``run_book`` field for field
(tests/test_paper_book.py). ``last_bar_date`` is ``Market.last_bar_date`` in a replay; at night
it is the latest bar date the database holds, so a halted symbol is force-closed on the first
session it misses (plan Decisions, "Force-close rule live").
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from seer_engine import dates
from seer_engine.backtest.book_runner import DividendMap, _dividends_on, _invested, _with_idle
from seer_engine.backtest.market import Market
from seer_engine.prices import Bar
from seer_engine.sim.book import (
    Book,
    BookSnapshot,
    BookSplit,
    Fill,
    RejectReason,
    Target,
    Trade,
    apply_book_split,
    close_book_unpriced,
    step_book,
)
from seer_engine.sim.rules import TradeRules, is_decision_session, is_rank_session
from seer_engine.strategies.allocator import Allocator

LastBarDate = Callable[[str], date | None]  # symbol -> its latest bar date known, or None


@dataclass(frozen=True, slots=True)
class BookNight:
    """One settled session of a book strategy.

    ``book``: the state after the session (forced closes applied), ``last_session = session``.
    ``targets``: the targets executed on ``session`` in post-split units (None on a
    non-decision session); a caller that persisted them before the split rewrites them with this.
    ``splits``: each ``apply_book_split`` result, in the order applied (symbol order).
    ``fills``: split fills, then ``step_book``'s (open exits, trims, buys, intraday exits), then
    forced closes: the ``book_fills.seq`` order. ``trades``: closed episodes in the same order.
    ``dividends``: ``(symbol, cash credited)`` by symbol. ``rejected``: ``step_book``'s
    rejections in its order. ``forced``: the symbols force-closed because their bars ended.
    ``snapshot``: S's snapshot, after any forced close.
    """

    session: date
    book: Book
    targets: tuple[Target, ...] | None
    splits: tuple[BookSplit, ...]
    fills: tuple[Fill, ...]
    trades: tuple[Trade, ...]
    dividends: tuple[tuple[str, Decimal], ...]
    rejected: tuple[tuple[str, RejectReason], ...]
    forced: tuple[str, ...]
    snapshot: BookSnapshot


def _session(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    if not dates.is_session(d):
        raise ValueError(f"{name} {d} is not an NYSE session")
    return d


def _book_rules(rules: object) -> TradeRules:
    if not isinstance(rules, TradeRules):
        raise TypeError(f"rules must be TradeRules, got {type(rules).__name__}")
    if rules.engine != "book":
        raise ValueError(f"rules {rules.id!r} use the {rules.engine} engine; the book night runs 'book' rules only")
    return rules


def _held(held: object) -> frozenset[str]:
    if isinstance(held, str) or not isinstance(held, AbstractSet):
        raise TypeError(f"held must be a set of symbols, got {type(held).__name__}")
    for s in held:
        if not isinstance(s, str):
            raise TypeError(f"held symbols must be str, got {type(s).__name__}")
    return frozenset(held)


def _splits(splits: object) -> tuple[tuple[str, Decimal], ...]:
    """``splits`` as ``(symbol, factor)`` pairs sorted by symbol; one split per symbol."""
    if isinstance(splits, (str, Mapping)) or not isinstance(splits, Sequence):
        raise TypeError(f"splits must be a sequence of (symbol, factor) pairs, got {type(splits).__name__}")
    out: dict[str, Decimal] = {}
    for pair in splits:
        if not (isinstance(pair, tuple) and len(pair) == 2):
            raise TypeError(f"a split is a (symbol, factor) tuple, got {pair!r}")
        symbol, factor = pair
        if not isinstance(symbol, str) or not symbol:
            raise TypeError(f"split symbol must be a non-empty str, got {symbol!r}")
        if not isinstance(factor, Decimal):
            raise TypeError(f"split factor for {symbol} must be a Decimal, got {type(factor).__name__}")
        if symbol in out:
            raise ValueError(f"two splits for {symbol} on one session")
        out[symbol] = factor
    return tuple(sorted(out.items()))


def decide_book(
    market: Market,
    allocator: Allocator,
    params: Any,
    rules: TradeRules,
    data_date: date,
    held: AbstractSet[str],
) -> tuple[tuple[Target, ...] | None, bool]:
    """The targets for ``next_session(data_date)`` and whether the idle residual was appended.

    ``(None, False)`` when that session is not a decision session under ``rules`` (the
    allocator is not called).

    Split-cadence rules (``rules.resize_cadence``) are a ValueError here: a resize-only session
    needs the LAST RANK SESSION'S basket, and this function is stateless — the paper store does
    not carry it yet. ``backtest.book_runner.run_book`` does, so backtests and replays of split
    rules are correct; only the nightly live decision is refused, loudly rather than by silently
    re-ranking every week. Otherwise exactly ``run_book``'s decision: ``allocator.targets``
    on ``{s: h.upto(data_date)}``, ``market.membership.members_on(data_date)``, ``held`` minus
    ``rules.idle_symbol``, ``params``; then ``book_runner._with_idle``. ``held`` is the set of
    symbols the book holds at the night of ``data_date`` (``book.held()`` after that session
    settled). Nothing dated after ``data_date`` is read.
    """
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    if not isinstance(allocator, Allocator):
        raise TypeError(f"allocator must be an Allocator, got {type(allocator).__name__}")
    _book_rules(rules)
    _session("data_date", data_date)
    held_now = _held(held)
    session = dates.next_session(data_date)
    if rules.resize_cadence is not None:
        raise ValueError(
            f"rules {rules.id!r} split rank and resize cadences; paper trading cannot decide them yet "
            "(the last rank session's basket is not stored). Backtest them with run_book."
        )
    if not is_decision_session(rules, session):
        return None, False
    assert is_rank_session(rules, session)  # no resize_cadence above, so every decision is a rank
    members = market.membership.members_on(data_date)
    # The idle position is the runner's residual, never a family's (as run_book).
    mine = held_now - {rules.idle_symbol} if rules.idle_symbol is not None else held_now
    history = {s: h.upto(data_date) for s, h in market.history.items()}
    wanted = allocator.targets(history, members, data_date, mine, params)
    return _with_idle(market, rules, tuple(wanted), data_date)


def settle_book(
    book: Book,
    session: date,
    bars: Mapping[str, Bar],
    targets: tuple[Target, ...] | None,
    idle_added: bool,
    rules: TradeRules,
    dividends: DividendMap,
    splits: Sequence[tuple[str, Decimal]],
    last_bar_date: LastBarDate,
) -> BookNight:
    """Settle ``session`` for ``book`` (see the module docstring).

    ``targets``/``idle_added``: what ``decide_book`` returned the night before (``idle_added``
    must be False when ``targets`` is None). ``dividends``: symbol -> {ex_date: cash per share},
    only ex-date ``session`` is read. ``splits``: ``(symbol, factor)`` for every split executing
    on ``session`` whose stored history was rewritten (``factor`` as ``splits.Split.factor``).
    ``last_bar_date``: symbol -> the date of its latest bar known, or None.

    TypeError on a wrong type, ValueError on a non-session, non-book rules, ``idle_added``
    without targets, or two splits for one symbol; ``apply_book_split`` and ``step_book`` raise
    on what they refuse (a session not after ``book.last_session`` among them).
    """
    if not isinstance(book, Book):
        raise TypeError(f"book must be a Book, got {type(book).__name__}")
    _session("session", session)
    _book_rules(rules)
    if not isinstance(idle_added, bool):
        raise TypeError("idle_added must be a bool")
    if idle_added and targets is None:
        raise ValueError("idle_added is True but there are no targets for this session")
    if not isinstance(dividends, Mapping):
        raise TypeError(f"dividends must be a Mapping, got {type(dividends).__name__}")
    if not callable(last_bar_date):
        raise TypeError("last_bar_date must be callable: symbol -> date | None")
    split_list = _splits(splits)

    executed = targets
    applied: list[BookSplit] = []
    fills: list[Fill] = []
    trades: list[Trade] = []
    for symbol, factor in split_list:
        done = apply_book_split(book, symbol, factor, session, rules, executed)
        applied.append(done)
        book = done.book
        executed = done.targets
        fills.extend(done.fills)
        if done.trade is not None:
            trades.append(done.trade)

    divs = _dividends_on(dividends, book.held(), session) if rules.dividends else {}
    stepped = step_book(book, session, bars, executed, rules, divs, idle_symbol_ok=idle_added)
    book = stepped.book
    fills.extend(stepped.fills)
    trades.extend(stepped.trades)
    snapshot = stepped.snapshot

    gone: list[str] = []
    for p in book.positions:
        last = last_bar_date(p.symbol)
        if last is None or last < session:
            gone.append(p.symbol)
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

    return BookNight(
        session=session,
        book=book,
        targets=executed,
        splits=tuple(applied),
        fills=tuple(fills),
        trades=tuple(trades),
        dividends=stepped.dividends,
        rejected=stepped.rejected,
        forced=tuple(gone),
        snapshot=snapshot,
    )
