"""Replay check (D7): one strategy's stored paper record against a fresh one-shot replay.

Pure (the paper purity test globs ``seer_engine/paper/*.py`` except ``store.py``): no database,
network, clock, randomness, logging or file access. ``commands/paper_check.py`` reads the stored
records, the windowed market and the dividends, and hands them in.

Expected records, per engine, over ``[paper_start, last_session]``:

- ``bracket`` (A): ``run_rules(market', strategy, params, DESIGN_V0, paper_start, last_session)``
  where ``market'`` is the market with ``fx = ((paper_start, usd_idr),)``. ``run_backtest``
  converts at ``market.usd_idr_on(start)``; paper converted at the stored rate (plan Decisions
  "Initial FX"). Expected orders: the run's closed, expired and open orders, plus the pending
  orders ``paper.bracket.decide_bracket`` sizes for ``pending_session`` from the run's end
  portfolio. Expected marks: each open symbol's last close on or before ``last_session``.
- ``book`` (F4, F1): ``run_rules(market, allocator, params, rules, paper_start, last_session,
  dividends=dividends, usd_idr=usd_idr)``. Expected targets: ``paper.book.decide_book`` on every
  decision session from ``paper_start`` through ``pending_session``, with the held set rebuilt
  from the run's fills; an empty decision is left out (it writes no ``book_targets`` row).
- ``benchmark`` (SPY): ``buy_and_hold(market.spy(), paper_start, last_session, cash0,
  dividends=SPY's)``; the holding is ``(SPY, whole shares, last close)``.

The first night steps no session (``last_session == prev_session(paper_start)``): the expected
record is the day-0 snapshot plus the first decision.

``judge`` gives one ``CheckResult``: ``ok`` when stored == expected; ``mismatch`` with the first
``MAX_SHOWN`` differences; ``split-affected`` when an applied split executed on or after
``paper_start`` on a symbol the strategy held or had pending the night before it, whatever the
differences (plan Decisions "Replay check scope": whole shares sized before a split cannot equal
a replay over the rewritten bars); ``not-started`` without a paper start.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend, buy_and_hold
from seer_engine.backtest.book_runner import BookResult, DividendMap, run_rules
from seer_engine.backtest.market import SPY, Market
from seer_engine.backtest.runner import INITIAL_IDR, RunResult
from seer_engine.paper.book import decide_book
from seer_engine.paper.bracket import decide_bracket
from seer_engine.sim import (
    DESIGN_V0,
    Fill,
    Order,
    Portfolio,
    Position,
    Snapshot,
    Target,
    Trade,
    TradeRules,
    initial_cash_usd,
    is_decision_session,
    new_portfolio,
)
from seer_engine.strategies.allocator import Allocator, MarketAware, prepare_for
from seer_engine.strategies.base import Strategy

Engine = Literal["bracket", "book", "benchmark"]
Status = Literal["ok", "mismatch", "split-affected", "not-started"]

ENGINES: tuple[str, ...] = ("bracket", "book", "benchmark")
MAX_SHOWN = 10  # differences listed per strategy; the rest are only counted
BENCHMARK_SYMBOL = SPY

SNAPSHOT_FIELDS: tuple[str, ...] = ("cash_usd", "equity_usd")
ORDER_FIELDS: tuple[str, ...] = (
    "slot",
    "last_price",
    "limit_price",
    "tp_price",
    "sl_price",
    "shares",
    "status",
    "fill_date",
    "fill_price",
    "days_held",
    "exit_date",
    "exit_price",
    "exit_reason",
    "pnl_usd",
)
POSITION_FIELDS: tuple[str, ...] = (
    "shares",
    "mark",
    "entry_date",
    "entry_price",
    "days_held",
    "cost_usd",
    "income_usd",
    "stop",
    "take",
    "exit_pending",
)
FILL_FIELDS: tuple[str, ...] = ("session_date", "symbol", "side", "shares", "price", "cash_usd", "cost_usd", "reason")
TRADE_FIELDS: tuple[str, ...] = (
    "symbol",
    "entry_date",
    "exit_date",
    "entry_price",
    "exit_price",
    "days_held",
    "cost_usd",
    "income_usd",
    "pnl_usd",
    "exit_reason",
    "idle",
)
TARGET_FIELDS: tuple[str, ...] = ("symbol", "weight", "last", "limit", "stop", "take")
HOLDING_FIELDS: tuple[str, ...] = ("shares", "mark")


# --------------------------------------------------------------------------- values


@dataclass(frozen=True, slots=True)
class Holding:
    """The benchmark's holding as ``book_positions`` stores it: whole shares and the last close."""

    symbol: str
    shares: Decimal
    mark: Decimal


@dataclass(frozen=True, slots=True)
class PaperHead:
    """What the replay needs from a started strategy: its engine, window and starting rate.

    ``last_session`` is ``prev_session(paper_start)`` right after the first night, then the last
    session stepped. ``usd_idr`` is ``paper_state.usd_idr``, the rate the initial cash was
    converted at.
    """

    strategy_id: str
    engine: Engine
    paper_start: date
    last_session: date
    usd_idr: Decimal

    def __post_init__(self) -> None:
        if self.engine not in ENGINES:
            raise ValueError(f"{self.strategy_id}: unknown engine {self.engine!r}")
        for name in ("paper_start", "last_session"):
            value = getattr(self, name)
            if isinstance(value, datetime) or not isinstance(value, date):
                raise TypeError(f"{self.strategy_id}: {name} must be a date, got {type(value).__name__}")
            if not dates.is_session(value):
                raise ValueError(f"{self.strategy_id}: {name} {value} is not an NYSE session")
        if self.last_session < dates.prev_session(self.paper_start):
            raise ValueError(
                f"{self.strategy_id}: last session {self.last_session} is before the day-0 session "
                f"{dates.prev_session(self.paper_start)}"
            )
        if not isinstance(self.usd_idr, Decimal):
            raise TypeError(f"{self.strategy_id}: usd_idr must be a Decimal, got {type(self.usd_idr).__name__}")
        if not self.usd_idr.is_finite() or self.usd_idr <= 0:
            raise ValueError(f"{self.strategy_id}: usd_idr must be > 0, got {self.usd_idr}")

    @property
    def sessions(self) -> int:
        """How many sessions have been stepped (0 after the first night)."""
        return sessions_stepped(self.paper_start, self.last_session)


@dataclass(frozen=True)
class Records:
    """One strategy's paper record: as stored in the database, or as the replay expects it.

    ``initial_cash``, ``cash``, ``equity``, ``pending_session`` and ``pending_decision`` are the
    ``paper_state`` columns. ``snapshots`` are every ``equity_snapshots`` row from day 0. Bracket:
    ``orders`` (every ``orders`` row) and ``marks`` (``(symbol, orders.mark)`` of the open
    orders, by symbol). Book: ``positions``, ``fills`` (execution order), ``trades`` (exit
    order) and ``targets`` (``(session, ranked targets)`` for every stored, non-empty decision,
    by session). Benchmark: ``holdings``.
    """

    initial_cash: Decimal | None
    cash: Decimal | None
    equity: Decimal | None
    pending_session: date | None
    pending_decision: bool
    snapshots: tuple[Snapshot, ...]
    orders: tuple[Order, ...] = ()
    marks: tuple[tuple[str, Decimal | None], ...] = ()
    positions: tuple[Position, ...] = ()
    fills: tuple[Fill, ...] = ()
    trades: tuple[Trade, ...] = ()
    targets: tuple[tuple[date, tuple[Target, ...]], ...] = ()
    holdings: tuple[Holding, ...] = ()


@dataclass(frozen=True, slots=True)
class Difference:
    """One stored value that is not the replay's, in words: ``str()`` is ``"where: text"``."""

    where: str
    text: str

    def __str__(self) -> str:
        return f"{self.where}: {self.text}"


@dataclass(frozen=True, slots=True)
class CheckResult:
    """The verdict for one roster strategy.

    ``differences`` holds the first ``MAX_SHOWN`` differences, ``total_differences`` counts all
    of them. ``splits`` are the applied ``(symbol, execution_date)`` splits that made the
    strategy split-affected.
    """

    strategy_id: str
    status: Status
    sessions: int
    paper_start: date | None = None
    last_session: date | None = None
    differences: tuple[Difference, ...] = ()
    total_differences: int = 0
    splits: tuple[tuple[str, date], ...] = ()


# --------------------------------------------------------------------------- helpers


def sessions_stepped(paper_start: date, last_session: date) -> int:
    """NYSE sessions in ``[paper_start, last_session]`` (0 when ``last_session`` is before the start)."""
    return len(dates.sessions(paper_start, last_session))


def last_close(market: Market, symbol: str, on: date) -> Decimal:
    """``symbol``'s close on its last bar dated on or before ``on``: the mark ``sim.step`` leaves."""
    h = market.history.get(symbol)
    last = None if h is None else h.upto(on).last_date()
    if last is None:
        raise ValueError(f"{symbol} has no bar on or before {on}")
    bar = market.bar(symbol, last)
    if bar is None:
        raise ValueError(f"{symbol} has no bar on {last}")
    return bar.close


def held_before(fills: Iterable[Fill], session: date) -> frozenset[str]:
    """Symbols with net shares > 0 from the fills dated before ``session``: the book's held set the
    night before it (a replay has no splits, so bought minus sold is the position exactly)."""
    net: dict[str, Decimal] = {}
    for f in fills:
        if f.session_date >= session:
            continue
        change = f.shares if f.side == "buy" else -f.shares
        net[f.symbol] = net.get(f.symbol, Decimal(0)) + change
    return frozenset(symbol for symbol, shares in net.items() if shares > 0)


def _day0(paper_start: date, cash0: Decimal) -> Snapshot:
    return Snapshot(date=dates.prev_session(paper_start), cash_usd=cash0, equity_usd=cash0)


def _order_key(o: Order) -> tuple[date, int, str]:
    return (o.session_date, o.slot, o.symbol)


# --------------------------------------------------------------------------- expected records


def expected_bracket(market: Market, strategy: Strategy, params: Any, head: PaperHead) -> Records:
    """The bracket record ``run_rules(DESIGN_V0)`` gives over the head's window, plus the next decision."""
    if head.engine != "bracket":
        raise ValueError(f"{head.strategy_id} is a {head.engine} strategy, not bracket")
    start, last = head.paper_start, head.last_session
    cash0 = initial_cash_usd(INITIAL_IDR, head.usd_idr)
    settled: tuple[Order, ...] = ()
    if last < start:
        pf = new_portfolio(cash0)
        snapshots: tuple[Snapshot, ...] = (_day0(start, cash0),)
    else:
        fixed = replace(market, fx=((start, head.usd_idr),))
        run = run_rules(fixed, strategy, params, DESIGN_V0, start, last)
        if not isinstance(run, RunResult):
            raise TypeError(f"DESIGN_V0 replay of {head.strategy_id} returned {type(run).__name__}")
        snapshots = run.snapshots
        expired = tuple(e.order for e in run.events if e.kind == "expire")
        settled = run.closed + expired + run.open_at_end
        marks = tuple(sorted((o.symbol, last_close(market, o.symbol, last)) for o in run.open_at_end))
        pf = Portfolio(
            cash=snapshots[-1].cash_usd,
            equity=snapshots[-1].equity_usd,
            orders=run.open_at_end,
            marks=marks,
            last_session=last,
        )
    sized = decide_bracket(pf, strategy, params, market.history, market.membership.members_on(last), last)
    orders = tuple(sorted(settled + sized.portfolio.pending_orders(), key=_order_key))
    return Records(
        initial_cash=cash0,
        cash=snapshots[-1].cash_usd,
        equity=snapshots[-1].equity_usd,
        pending_session=dates.next_session(last),
        pending_decision=False,
        snapshots=tuple(snapshots),
        orders=orders,
        marks=pf.marks,
    )


def expected_book(
    market: Market,
    allocator: Allocator,
    params: Any,
    rules: TradeRules,
    head: PaperHead,
    dividends: DividendMap,
) -> Records:
    """The book record ``run_rules(rules)`` gives over the head's window, plus every decision."""
    if head.engine != "book":
        raise ValueError(f"{head.strategy_id} is a {head.engine} strategy, not book")
    if not isinstance(rules, TradeRules) or rules.engine != "book":
        raise ValueError(f"{head.strategy_id}: book replay needs book rules, got {rules!r}")
    start, last = head.paper_start, head.last_session
    cash0 = initial_cash_usd(INITIAL_IDR, head.usd_idr)
    fills: tuple[Fill, ...] = ()
    trades: tuple[Trade, ...] = ()
    positions: tuple[Position, ...] = ()
    if last < start:
        snapshots: tuple[Snapshot, ...] = (_day0(start, cash0),)
    else:
        # A MarketAware allocator is replayed through run_book's prepared branch, exactly as
        # paper.book.decide_book decides it; `prepared` stays None for every other allocator so
        # the five strategies with a paper clock replay byte for byte as before. `market` is
        # passed uncut here because run_book cuts per session itself and FUNDAMENTAL indexes its
        # bars by date (History.index_of), never by last row -- the property
        # allocatorkit.assert_no_lookahead pins.
        prepared = prepare_for(allocator, market) if isinstance(allocator, MarketAware) else None
        run = run_rules(
            market,
            allocator,
            params,
            rules,
            start,
            last,
            prepared=prepared,
            dividends=dividends,
            usd_idr=head.usd_idr,
        )
        if not isinstance(run, BookResult):
            raise TypeError(f"book replay of {head.strategy_id} returned {type(run).__name__}")
        snapshots = tuple(Snapshot(date=s.date, cash_usd=s.cash_usd, equity_usd=s.equity_usd) for s in run.snapshots)
        fills, trades, positions = run.fills, run.trades, run.open_at_end
    pending = dates.next_session(last)
    decisions: list[tuple[date, tuple[Target, ...]]] = []
    pending_decision = False
    for session in dates.sessions(start, pending):
        if not is_decision_session(rules, session):
            continue
        wanted, _ = decide_book(
            market, allocator, params, rules, dates.prev_session(session), held_before(fills, session)
        )
        if session == pending:
            pending_decision = wanted is not None
        if wanted:
            decisions.append((session, tuple(wanted)))
    return Records(
        initial_cash=cash0,
        cash=snapshots[-1].cash_usd,
        equity=snapshots[-1].equity_usd,
        pending_session=pending,
        pending_decision=pending_decision,
        snapshots=snapshots,
        positions=positions,
        fills=fills,
        trades=trades,
        targets=tuple(decisions),
    )


def expected_benchmark(market: Market, head: PaperHead, dividends: DividendMap) -> Records:
    """The SPY buy-and-hold record over the head's window (dividends reinvested at the ex-date close)."""
    if head.engine != "benchmark":
        raise ValueError(f"{head.strategy_id} is a {head.engine} strategy, not benchmark")
    start, last = head.paper_start, head.last_session
    cash0 = initial_cash_usd(INITIAL_IDR, head.usd_idr)
    if last < start:
        snapshots: tuple[Snapshot, ...] = (_day0(start, cash0),)
        cash = cash0
        holdings: tuple[Holding, ...] = ()
    else:
        by_date = dividends.get(BENCHMARK_SYMBOL, {})
        paid = tuple(Dividend(ex_date=d, amount=by_date[d]) for d in sorted(by_date))
        curve = buy_and_hold(market.spy(), start, last, cash0, dividends=paid, name=BENCHMARK_SYMBOL)
        snapshots = curve.snapshots
        cash = curve.cash
        holdings = ()
        if curve.shares > 0:
            holdings = (
                Holding(
                    symbol=BENCHMARK_SYMBOL,
                    shares=Decimal(curve.shares),
                    mark=last_close(market, BENCHMARK_SYMBOL, last),
                ),
            )
    return Records(
        initial_cash=cash0,
        cash=cash,
        equity=snapshots[-1].equity_usd,
        pending_session=dates.next_session(last),
        pending_decision=False,
        snapshots=tuple(snapshots),
        holdings=holdings,
    )


# --------------------------------------------------------------------------- comparison


def _fmt(value: object) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _diff_fields(where: str, stored: object, expected: object, names: Sequence[str]) -> list[Difference]:
    out: list[Difference] = []
    for name in names:
        a, b = getattr(stored, name), getattr(expected, name)
        if a != b:
            out.append(Difference(where, f"{name} stored {_fmt(a)}, replay {_fmt(b)}"))
    return out


def _diff_keyed(
    label: str,
    stored: Mapping[Any, Any],
    expected: Mapping[Any, Any],
    names: Sequence[str],
    key_text: Callable[[Any], str],
) -> list[Difference]:
    out: list[Difference] = []
    for key in sorted(set(stored) | set(expected)):
        where = f"{label} {key_text(key)}"
        if key not in stored:
            out.append(Difference(where, "in the replay, missing from the database"))
        elif key not in expected:
            out.append(Difference(where, "in the database, not in the replay"))
        else:
            out.extend(_diff_fields(where, stored[key], expected[key], names))
    return out


def _diff_sequence(
    label: str,
    stored: Sequence[Any],
    expected: Sequence[Any],
    names: Sequence[str],
    describe: Callable[[Any], str],
) -> list[Difference]:
    out: list[Difference] = []
    for i in range(max(len(stored), len(expected))):
        if i >= len(stored):
            out.append(Difference(f"{label} #{i + 1} ({describe(expected[i])})", "in the replay, missing from the database"))
        elif i >= len(expected):
            out.append(Difference(f"{label} #{i + 1} ({describe(stored[i])})", "in the database, not in the replay"))
        else:
            out.extend(_diff_fields(f"{label} #{i + 1} ({describe(expected[i])})", stored[i], expected[i], names))
    return out


def _diff_values(label: str, stored: Mapping[str, Any], expected: Mapping[str, Any]) -> list[Difference]:
    out: list[Difference] = []
    for key in sorted(set(stored) | set(expected)):
        where = f"{label} {key}"
        if key not in stored:
            out.append(Difference(where, "in the replay, missing from the database"))
        elif key not in expected:
            out.append(Difference(where, "in the database, not in the replay"))
        elif stored[key] != expected[key]:
            out.append(Difference(where, f"stored {_fmt(stored[key])}, replay {_fmt(expected[key])}"))
    return out


def _iso(d: date) -> str:
    return d.isoformat()


def _order_text(key: tuple[date, str]) -> str:
    return f"{key[0].isoformat()} {key[1]}"


def _target_text(key: tuple[date, int]) -> str:
    return f"{key[0].isoformat()} rank {key[1]}"


def _fill_text(f: Fill) -> str:
    return f"{f.session_date.isoformat()} {f.side} {f.symbol}"


def _trade_text(t: Trade) -> str:
    return f"{t.symbol} {t.entry_date.isoformat()}..{t.exit_date.isoformat()}"


def _targets_by_key(decisions: Iterable[tuple[date, tuple[Target, ...]]]) -> dict[tuple[date, int], Target]:
    out: dict[tuple[date, int], Target] = {}
    for session, targets in decisions:
        for rank, t in enumerate(targets, start=1):
            out[(session, rank)] = t
    return out


def compare(engine: Engine, stored: Records, expected: Records) -> tuple[Difference, ...]:
    """Every stored value that differs from the replay, snapshots first, ``paper_state`` last."""
    if engine not in ENGINES:
        raise ValueError(f"unknown engine {engine!r}")
    out: list[Difference] = _diff_keyed(
        "snapshot",
        {s.date: s for s in stored.snapshots},
        {s.date: s for s in expected.snapshots},
        SNAPSHOT_FIELDS,
        _iso,
    )
    if engine == "bracket":
        out += _diff_keyed(
            "order",
            {(o.session_date, o.symbol): o for o in stored.orders},
            {(o.session_date, o.symbol): o for o in expected.orders},
            ORDER_FIELDS,
            _order_text,
        )
        out += _diff_values("mark", dict(stored.marks), dict(expected.marks))
        state = ("initial_cash", "cash", "equity", "pending_session")
    elif engine == "book":
        out += _diff_keyed(
            "position",
            {p.symbol: p for p in stored.positions},
            {p.symbol: p for p in expected.positions},
            POSITION_FIELDS,
            str,
        )
        out += _diff_sequence("fill", stored.fills, expected.fills, FILL_FIELDS, _fill_text)
        out += _diff_sequence("trade", stored.trades, expected.trades, TRADE_FIELDS, _trade_text)
        out += _diff_keyed(
            "target", _targets_by_key(stored.targets), _targets_by_key(expected.targets), TARGET_FIELDS, _target_text
        )
        state = ("initial_cash", "cash", "equity", "pending_session", "pending_decision")
    else:
        out += _diff_keyed(
            "holding",
            {h.symbol: h for h in stored.holdings},
            {h.symbol: h for h in expected.holdings},
            HOLDING_FIELDS,
            str,
        )
        state = ("initial_cash", "cash", "equity")
    out += _diff_fields("paper_state", stored, expected, state)
    return tuple(out)


# --------------------------------------------------------------------------- splits


def _exposed(engine: Engine, paper_start: date, r: Records, symbol: str, day: date) -> bool:
    """Whether ``r`` had live state on ``symbol`` the night before the split executing on ``day``."""
    if engine == "bracket":
        for o in r.orders:
            if o.symbol != symbol or o.session_date > day:
                continue
            if o.status == "closed" and o.exit_date is not None and o.exit_date < day:
                continue
            if o.status == "expired" and o.session_date < day:
                continue
            return True
        return False
    if engine == "book":
        for t in r.trades:
            if t.symbol == symbol and t.entry_date < day <= t.exit_date:
                return True
        for p in r.positions:
            if p.symbol == symbol and p.entry_date < day:
                return True
        for session, targets in r.targets:
            if session == day and any(t.symbol == symbol for t in targets):
                return True
        return False
    return symbol == BENCHMARK_SYMBOL and day > paper_start


def split_exposure(
    engine: Engine,
    paper_start: date,
    records: Iterable[Records],
    splits: Iterable[tuple[str, date]],
) -> tuple[tuple[str, date], ...]:
    """The applied ``(symbol, execution_date)`` splits, on or after ``paper_start``, that hit a
    symbol any of ``records`` (stored and replayed) held or had pending the night before; by
    (date, symbol)."""
    if engine not in ENGINES:
        raise ValueError(f"unknown engine {engine!r}")
    pool = tuple(records)
    hit: set[tuple[str, date]] = set()
    for symbol, day in splits:
        if day < paper_start:
            continue
        if any(_exposed(engine, paper_start, r, symbol, day) for r in pool):
            hit.add((symbol, day))
    return tuple(sorted(hit, key=lambda s: (s[1], s[0])))


# --------------------------------------------------------------------------- verdicts


def judge(
    head: PaperHead, stored: Records, expected: Records, splits: Iterable[tuple[str, date]]
) -> CheckResult:
    """The verdict for one started strategy."""
    found = compare(head.engine, stored, expected)
    exposed = split_exposure(head.engine, head.paper_start, (stored, expected), splits)
    if exposed:
        status: Status = "split-affected"
    elif found:
        status = "mismatch"
    else:
        status = "ok"
    return CheckResult(
        strategy_id=head.strategy_id,
        status=status,
        sessions=head.sessions,
        paper_start=head.paper_start,
        last_session=head.last_session,
        differences=found[:MAX_SHOWN],
        total_differences=len(found),
        splits=exposed,
    )


def not_started(strategy_id: str) -> CheckResult:
    """A roster strategy with no paper start and no paper state."""
    return CheckResult(strategy_id=strategy_id, status="not-started", sessions=0)


def broken(
    strategy_id: str,
    where: str,
    message: str,
    *,
    paper_start: date | None = None,
    last_session: date | None = None,
) -> CheckResult:
    """A strategy whose stored state cannot be read or replayed: a mismatch with one difference."""
    sessions = 0
    if paper_start is not None and last_session is not None:
        sessions = sessions_stepped(paper_start, last_session)
    return CheckResult(
        strategy_id=strategy_id,
        status="mismatch",
        sessions=sessions,
        paper_start=paper_start,
        last_session=last_session,
        differences=(Difference(where, message),),
        total_differences=1,
    )


def _count(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def failures(results: Sequence[CheckResult], require_sessions: int) -> tuple[str, ...]:
    """Why the check fails, one line per reason (empty: it passes). A mismatch always fails;
    with ``require_sessions > 0`` so does any strategy that stepped fewer sessions (not started
    counts as 0). Split-affected never fails by itself."""
    if require_sessions < 0:
        raise ValueError(f"require_sessions must be >= 0, got {require_sessions}")
    out: list[str] = []
    for r in results:
        if r.status == "mismatch":
            out.append(f"{r.strategy_id}: replay mismatch ({_count(r.total_differences, 'difference')})")
        if require_sessions > 0 and r.sessions < require_sessions:
            out.append(f"{r.strategy_id}: {r.sessions} sessions stepped, {require_sessions} required")
    return tuple(out)


def exit_code(results: Sequence[CheckResult], require_sessions: int) -> int:
    """1 when ``failures`` is non-empty, else 0."""
    return 1 if failures(results, require_sessions) else 0


def render(results: Sequence[CheckResult]) -> tuple[str, ...]:
    """One line per strategy, then its listed differences indented, then a count of the rest."""
    width = max((len(r.strategy_id) for r in results), default=0)
    lines: list[str] = []
    for r in results:
        head = f"{r.strategy_id:<{width}}  {r.status:<14}"
        if r.status == "not-started":
            lines.append(f"{head}  no paper start")
            continue
        if r.sessions == 0 or r.paper_start is None or r.last_session is None:
            start = "-" if r.paper_start is None else r.paper_start.isoformat()
            span = f"0 sessions (starts {start})"
        else:
            span = f"{_count(r.sessions, 'session')} ({r.paper_start.isoformat()}..{r.last_session.isoformat()})"
        if r.status == "ok":
            lines.append(f"{head}  {span}")
        elif r.status == "mismatch":
            lines.append(f"{head}  {span}, {_count(r.total_differences, 'difference')}")
        else:
            hit = ", ".join(f"{symbol} on {day.isoformat()}" for symbol, day in r.splits)
            lines.append(
                f"{head}  {span}, applied split {hit}; "
                f"{_count(r.total_differences, 'difference')} not failed"
            )
        for d in r.differences:
            lines.append(f"    {d}")
        hidden = r.total_differences - len(r.differences)
        if hidden > 0:
            lines.append(f"    ... and {hidden} more")
    return tuple(lines)
