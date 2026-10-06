"""The book engine's night: one paper session of a book strategy (R1, plan contract C3).

Pure (purity-tested with every ``paper/*.py`` except ``store.py``): no database, network,
clock, randomness, logging or file access. Paper trading runs ``backtest.book_runner.run_book``'s
loop body one session at a time, over state persisted between nights, in two halves:

``decide_book`` (the night of ``data_date``, after its bars arrived) is ``run_book``'s step 1,
1b and 2 for ``S = next_session(data_date)``: ``None`` when ``S`` is not a decision session under
``rules``; on a rank session ``allocator.targets`` on every history cut at ``data_date``, the
members on ``data_date`` and the symbols held at night minus the idle instrument; on a
resize-only session (split-cadence rules) the last rank basket re-scaled by
``book_runner._rescaled``; then ``book_runner._with_idle`` (both imported, not copied). It
returns ``(targets, idle_added)``; the caller persists both and hands them back to
``settle_book`` for ``S``. ``run_book`` keeps the last rank basket in a loop variable; paper
keeps none, so the caller passes it in: the targets stored for ``last_rank_session(...)``,
through ``rank_basket``.

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
(tests/test_paper_book.py), split-cadence rules included when each night passes ``last_rank``
and the book's ``marks``. ``last_bar_date`` is ``Market.last_bar_date`` in a replay; at night
it is the latest bar date the database holds, so a halted symbol is force-closed on the first
session it misses (plan Decisions, "Force-close rule live").
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from seer_engine import dates
from seer_engine.backtest.book_runner import DividendMap, _dividends_on, _invested, _rescaled, _with_idle
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
from seer_engine.sim.rules import TradeRules, is_rank_session, is_resize_session
from seer_engine.strategies.allocator import Allocator, MarketAware, prepare_for

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


def _wanted(
    market: Market, allocator: Allocator, params: Any, data_date: date, mine: frozenset[str]
) -> tuple[Target, ...]:
    """``allocator``'s targets for the night of ``data_date``: ``run_book``'s allocator call.

    ``market.membership.members_on(data_date)``, every history cut at ``data_date``, ``mine``
    (the held symbols, the idle instrument left out) and ``params``. A ``MarketAware`` allocator
    (``strategies.allocator.MarketAware``: it defines ``prepare_market``) takes the prepared
    branch -- ``targets_prepared(prepare_for(allocator, market_cut_at_data_date), ...)``. It must:
    such an allocator reads part of the ``Market`` that ``history`` cannot carry, and for
    ``FUNDAMENTAL`` the history-only path is not a worse answer but a fixed empty one (its
    docstring: with no panel no symbol is eligible, so ``targets`` returns ``()``). The branch is
    keyed on the protocol and nothing else, so an allocator without ``prepare_market`` runs the
    plain expression unchanged.
    """
    members = market.membership.members_on(data_date)
    history = {s: h.upto(data_date) for s, h in market.history.items()}
    if isinstance(allocator, MarketAware):
        # A MarketAware allocator reads more of the Market than its bars (FUNDAMENTAL reads
        # market.fundamentals), so handing it the history dict alone is not a degraded result,
        # it is a WRONG one: f_fundamental's history-only path finds every symbol ineligible
        # and returns (), forever, silently. This is run_book's own dispatch
        # (backtest/book_runner.py:289) brought to the nightly decision.
        #
        # The Market handed over carries `history` -- the same dict the plain path passes, cut
        # at data_date -- so no bar dated after data_date is reachable on either path. The
        # panel needs no cut of its own: panel.as_of(symbol, d) answers from facts with
        # filed <= d and only those, and `filed` IS the no-look-ahead boundary
        # (005_fundamentals.sql, "filed IS THE ONLY NO-LOOK-AHEAD BOUNDARY").
        prepared = prepare_for(allocator, replace(market, history=history))
        return tuple(allocator.targets_prepared(prepared, members, data_date, mine, params))
    return tuple(allocator.targets(history, members, data_date, mine, params))


def _last_rank(last_rank: object) -> tuple[Target, ...] | None:
    if last_rank is None:
        return None
    if not isinstance(last_rank, tuple):
        raise TypeError(f"last_rank must be a tuple of Target or None, got {type(last_rank).__name__}")
    for t in last_rank:
        if not isinstance(t, Target):
            raise TypeError(f"last_rank holds Targets, got {type(t).__name__}")
    return last_rank


def _marks(marks: object) -> Mapping[str, Decimal] | None:
    if marks is None:
        return None
    if not isinstance(marks, Mapping):
        raise TypeError(f"marks must be a Mapping of symbol -> Decimal or None, got {type(marks).__name__}")
    for symbol, mark in marks.items():
        if not isinstance(symbol, str):
            raise TypeError(f"marks keys are symbols (str), got {type(symbol).__name__}")
        if not isinstance(mark, Decimal):
            raise TypeError(f"mark for {symbol} must be a Decimal, got {type(mark).__name__}")
    return marks


def decide_book(
    market: Market,
    allocator: Allocator,
    params: Any,
    rules: TradeRules,
    data_date: date,
    held: AbstractSet[str],
    *,
    force: bool = False,
    last_rank: tuple[Target, ...] | None = None,
    marks: Mapping[str, Decimal] | None = None,
) -> tuple[tuple[Target, ...] | None, bool]:
    """The targets for ``S = next_session(data_date)`` and whether the idle residual was appended.

    Exactly ``run_book``'s decision for ``S``. ``held`` is the set of symbols the book holds at
    the night of ``data_date`` (``book.held()`` after that session settled); the allocator sees
    it minus ``rules.idle_symbol``. Nothing dated after ``data_date`` is read.

    - A RANK session -- ``force`` (the kickoff, ``needs_kickoff``; also the nightly preview of
      what the book would pick now) or ``is_rank_session(rules, S)``: ``_wanted`` (the allocator
      on every history cut at ``data_date``, the members on ``data_date``, the held symbols,
      ``params``; a ``MarketAware`` allocator through its prepared branch), then
      ``book_runner._with_idle``. ``last_rank`` and ``marks`` are not read.
    - A RESIZE-ONLY session (``is_resize_session(rules, S)``, only under a ``resize_cadence``)
      with ``last_rank`` given: the allocator is called the same way, but only its total weight
      is used: ``book_runner._with_idle(book_runner._rescaled(market, last_rank, wanted, held -
      idle, data_date, marks))`` (both imported, not copied). ``last_rank`` is the last rank
      session's targets WITHOUT the idle row (``rank_basket``), ``()`` when that rank chose
      nothing; only each target's ``symbol`` and ``weight`` reach the result, so the basket may
      be in pre- or post-split units. ``marks`` is ``{p.symbol: p.mark for p in
      book.positions}`` of the same book ``held`` came from (``_rescaled``'s price for a held
      symbol without a bar on ``data_date``); a ValueError when it is missing here.
    - Otherwise ``(None, False)`` and the allocator is not called: a session that is neither,
      and a resize-only session with ``last_rank`` None (no rank yet: ``run_book`` does not
      decide a resize session before its first rank either).

    For every rule set without a ``resize_cadence`` no session is resize-only, so the result is
    the rank-or-nothing decision it always was, whatever ``last_rank`` and ``marks`` hold.
    """
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    if not isinstance(allocator, Allocator):
        raise TypeError(f"allocator must be an Allocator, got {type(allocator).__name__}")
    _book_rules(rules)
    _session("data_date", data_date)
    held_now = _held(held)
    basket_then = _last_rank(last_rank)
    marks_now = _marks(marks)
    session = dates.next_session(data_date)
    rank = force or is_rank_session(rules, session)
    if not rank and (basket_then is None or not is_resize_session(rules, session)):
        return None, False
    if not rank and marks_now is None:
        raise ValueError(
            f"{session} is a resize-only session under {rules.id!r}: decide_book needs the book's marks "
            "(symbol -> mark) to re-scale the last rank basket"
        )
    # The idle position is the runner's residual, never a family's (as run_book).
    mine = held_now - {rules.idle_symbol} if rules.idle_symbol is not None else held_now
    wanted = _wanted(market, allocator, params, data_date, mine)
    if rank:
        return _with_idle(market, rules, wanted, data_date)
    assert basket_then is not None and marks_now is not None
    basket = _rescaled(market, basket_then, wanted, mine, data_date, marks_now)
    return _with_idle(market, rules, basket, data_date)


def needs_kickoff(rules: TradeRules, paper_start: date, session: date, kickoff: date | None) -> bool:
    """True when ``session`` must be the book's kickoff: its first decision, off the cadence.

    A book strategy whose paper clock starts between two rank sessions would otherwise hold its
    starting cash until the next one (up to a month for monthly rules). It ranks instead on the
    first session it can, once: when no kickoff is stored yet (``kickoff`` None), ``session`` is
    not a rank session, and no rank session lies in ``[paper_start, session)`` (one there was
    already a first decision). Replays rank on the stored kickoff (``run_book(kickoff=...)``).

    A resize-only session (split-cadence rules) is not a rank session: before the first rank
    there is no basket to re-scale, so ``run_book`` does not decide it, and a clock starting on
    one kicks off there. Without a ``resize_cadence`` every decision session is a rank session,
    so this is the test it always was.
    """
    _book_rules(rules)
    _session("paper_start", paper_start)
    _session("session", session)
    if kickoff is not None or is_rank_session(rules, session):
        return False
    return not any(is_rank_session(rules, s) for s in dates.sessions(paper_start, session) if s < session)


def last_rank_session(rules: TradeRules, paper_start: date, kickoff: date | None, session: date) -> date | None:
    """The session whose decision holds the basket a resize-only ``session`` re-scales, or None.

    The latest ``d`` in ``[paper_start, session)`` that ranked: ``is_rank_session(rules, d)`` or
    ``d == kickoff`` (the stored kickoff session) -- ``run_book``'s ``last_rank`` variable, read
    off the calendar instead of a loop. Paper decides every session in order, so that session's
    stored targets (``rank_basket`` of them; ``()`` when it chose nothing and wrote no row) are
    the basket exactly. None when nothing ranked before ``session``: ``decide_book`` then decides
    no resize session, as ``run_book`` does not.
    """
    _book_rules(rules)
    _session("paper_start", paper_start)
    _session("session", session)
    if kickoff is not None:
        _session("kickoff", kickoff)
    for d in reversed(dates.sessions(paper_start, session)):
        if d < session and (d == kickoff or is_rank_session(rules, d)):
            return d
    return None


def rank_basket(targets: Sequence[Target], idle_symbol: str | None) -> tuple[Target, ...]:
    """A rank decision's targets as ``decide_book``'s ``last_rank``: the idle row taken off.

    ``book_runner._with_idle`` appends at most one target, last, in ``idle_symbol``; an allocator
    that targets the idle symbol is a ValueError there, so a trailing ``idle_symbol`` row is the
    runner's residual and nothing else. A row in ``idle_symbol`` anywhere but last is a
    ValueError (those targets were not a decision). ``targets`` in rank order, as stored.
    """
    if isinstance(targets, (str, Mapping)) or not isinstance(targets, Sequence):
        raise TypeError(f"targets must be a sequence of Target, got {type(targets).__name__}")
    rows = tuple(targets)
    for t in rows:
        if not isinstance(t, Target):
            raise TypeError(f"targets holds Targets, got {type(t).__name__}")
    if idle_symbol is not None and rows and rows[-1].symbol == idle_symbol:
        rows = rows[:-1]
    if idle_symbol is not None and any(t.symbol == idle_symbol for t in rows):
        raise ValueError(f"the idle symbol {idle_symbol} is targeted before the last row; not a book decision")
    return rows


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
