"""The P7a dev-window runner (handover D1, D3, D6-D9; plan phase 9).

Pure: no database, network, files, clock or randomness (tests/test_strategy_purity.py globs
this module). It never imports ``seer_engine.research``, the impure research store, whose own
``DEV_END`` is a duplicate constant pinned equal to this one by a test.

- **D9, the code-level guard.** ``DEV_END`` is 2015-10-16 and ``DEV_WINDOW`` is the window
  every entry point here defaults to. Every public entry point that is handed a date, a market
  or dividends raises ``DevWindowError`` (a ``ValueError``) when any of them is dated after
  that window's end: ``check_dev_session``, ``candidate_window``, ``run_candidate``,
  ``run_registry``, ``make_row`` and ``DevRow`` itself. A caller that passes nothing gets the
  dev window, so the refusal is absolute by default. The ``window=`` argument is the only way
  to reach the P7b test window (method lab design §3), and only ``lab test`` passes one.
  Nothing takes a bare ``end``: every candidate runs to its window's end.
- **D3, each candidate's own window.** ``candidate_window`` starts at the first session whose
  data date gives every instrument the candidate reads (and SPY) its full lookback, and, for
  candidates that read index members, not before the first membership snapshot.
- **One path per rule set.** ``run_candidate`` goes through ``book_runner.run_rules``:
  ``DESIGN_V0`` bracket strategies reach the unchanged ``run_backtest``, every other rule set
  the book engine. SPY curves come from ``benchmark.spy_curves`` on the same window and the
  same starting cash, with the store's SPY dividends.
- **D8.** ``make_row`` applies the §1 thresholds (beating total-return SPY,
  ``tuning.MAX_DRAWDOWN``, ``tuning.MIN_PROFIT_FACTOR``, 100 closed trades) and the
  owner-input rule; ``finalists`` ranks the eligible rows by MAR and keeps one per family, at
  most three.
- **D7.** ``deflated_sharpe`` is Bailey & López de Prado's (2014) deflated Sharpe ratio for
  the report's multiple-testing note.

FX before ``FX_START`` (1999-01-04, Frankfurter's first USD/IDR row): a window that starts
earlier converts the IDR starting capital at the ``FX_START`` rate. FX feeds the starting cash
only, so no decision depends on it.

**Starting capital is an input, not a constant.** ``run_candidate`` and ``run_registry`` take
``initial_idr``, defaulting to ``runner.INITIAL_IDR``, and hand it to ``run_rules`` unchanged. A
caller that passes nothing runs at the live constant, byte-for-byte as before the keyword
existed. A caller re-running a *recorded* trial passes the capital that trial was recorded at:
whole-share rounding (and, under ``cost_model="gotrade"``, the per-order fee floor) makes capital
a result-moving input -- a 10,000,000 IDR book and a 20,000,000 IDR book buy different share
counts of the same names, so their curves differ in shape, not only in scale -- and
``INITIAL_IDR`` moved from 20,000,000 to 10,000,000 on 2026-10-08 (``d79fc83``) with nothing in
the lab recording which one a trial ran on.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from statistics import NormalDist
from typing import Any

from seer_engine import dates
from seer_engine.backtest import tuning
from seer_engine.backtest.benchmark import Dividend, spy_curves
from seer_engine.backtest.book_runner import BookResult, DividendMap, RunStats, run_rules, run_stats
from seer_engine.backtest.market import SPY, Market
from seer_engine.backtest.metrics import (
    Metrics,
    curve_metrics,
    external_cashflows,
    money_weighted_return,
)
from seer_engine.backtest.runner import INITIAL_IDR, RunResult
from seer_engine.backtest.window import Window
from seer_engine.sim.contributions import ContributionSchedule
from seer_engine.sim.rules import DEFAULT_ETFS, LEVERAGED_ETFS, TradeRules, is_bracket, rule_owner_inputs
from seer_engine.strategies.allocator import Allocator, prepare_for
from seer_engine.strategies.base import Strategy

DEV_END = date(2015, 10, 16)  # last dev session; 2015-10-19 opens the P7b test window
MEMBERSHIP_START = date(1996, 1, 2)  # first sp500_history.csv row
FX_START = date(1999, 1, 4)  # first Frankfurter USD/IDR row (verified 2026-10-03)
MAX_CANDIDATES = 60  # handover D6

DEV_WINDOW = Window(name="dev", start=date.min, end=DEV_END)
"""The window every entry point in this module defaults to (D9).

``start`` is ``date.min``, not ``MEMBERSHIP_START``: the dev window has no lower bound, and a
long-lookback SPY candidate legitimately opens in 1993. ``research.DEV_WINDOW`` is the same
value built from ``research.DEV_END``; ``tests/test_backtest_window.py`` pins them equal.
"""

FAILURE_LABELS: tuple[str, ...] = (
    "beats SPY TR",
    # go-live #4's label, interpolated from the bar it names so the two can never disagree.
    # Raised 0.15 -> 0.20 by the owner on 2026-10-07 (design §1 item 4, §11); at 0.15 this
    # formats to "max DD <= 15%" byte-for-byte, which is what makes the change revertible and
    # what keeps the 110 recorded rows comparable. The PREFIX is the stable part: `trials.failed`
    # is append-only, so rows judged before that day keep "max DD <= 15%" for ever and rows
    # judged after carry "max DD <= 20%". Both are misses, and every reader -- store.owner_failures
    # in Python, DRAWDOWN_FAILURE_PREFIX in web/lib/sera/derive.ts -- matches on "max DD <= ",
    # never on the whole string. See tests/test_lab_gate_wording.py (phase 7).
    f"max DD <= {tuning.MAX_DRAWDOWN:.0%}",
    "PF >= 1.3",
    ">= 100 trades",
    "owner inputs",
)

# The DEV-WINDOW trades bar, and deliberately NOT design §1 item 1 any more: the owner deleted
# item 1's trades clause on 2026-10-07 (design §13) and left this one standing, because a
# profit factor computed from 11 trades is not a measurement. The asymmetry is intentional
# and dated; see §13 for the measurement behind it. Not yours to "tidy".
_MIN_TRADES = 100
_MAX_FINALISTS = 3  # handover D8
_EULER_GAMMA = 0.5772156649  # Euler-Mascheroni, as Bailey & López de Prado state it
_ID = re.compile(r"[A-Z0-9]+(-[A-Z0-9]+)*")
_FAMILY = re.compile(r"F([1-9]|1[01])|REF|M\d{4}")  # M0001…: method lab families


class DevWindowError(ValueError):
    """A session, bar, FX row or dividend after the running window's end reached the runner (D9).

    The running window is ``DEV_WINDOW`` unless the caller passed one, so the unqualified
    reading -- "after ``DEV_END``" -- is the only one a dev path can produce.
    """


def _as_date(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    return d


def check_dev_session(d: date, window: Window = DEV_WINDOW) -> None:
    """Raise ``DevWindowError`` when ``d`` is after ``window.end`` (``TypeError`` for a non-date).

    The name is historical and the default is the point: ``check_dev_session(d)`` is the D9
    check it has always been.
    """
    _as_date("session", d)
    if d > window.end:
        raise DevWindowError(f"session {d} is after the {window.name} window end {window.end} (D9)")


def _check_market(market: object, window: Window = DEV_WINDOW) -> Market:
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    for symbol in sorted(market.history):
        last = market.history[symbol].last_date()
        if last is not None and last > window.end:
            raise DevWindowError(f"{symbol} has a bar on {last}, after the {window.name} window end {window.end} (D9)")
    if market.fx and market.fx[-1][0] > window.end:
        raise DevWindowError(f"the market has a usd_idr row on {market.fx[-1][0]}, after the {window.name} window end {window.end} (D9)")
    return market


def _check_dividends(dividends: object, spy_dividends: object, window: Window = DEV_WINDOW) -> tuple[Dividend, ...]:
    if not isinstance(dividends, Mapping):
        raise TypeError(f"dividends must be a Mapping, got {type(dividends).__name__}")
    for symbol in sorted(dividends):
        by_date = dividends[symbol]
        if not isinstance(by_date, Mapping):
            raise TypeError(f"dividends[{symbol!r}] must be a Mapping of ex_date -> amount")
        late = [d for d in by_date if _as_date(f"{symbol} ex_date", d) > window.end]
        if late:
            raise DevWindowError(f"{symbol} has a dividend on {min(late)}, after the {window.name} window end {window.end} (D9)")
    if isinstance(spy_dividends, (str, bytes)) or not isinstance(spy_dividends, Sequence):
        raise TypeError(f"spy_dividends must be a sequence of Dividend, got {type(spy_dividends).__name__}")
    out = tuple(spy_dividends)
    for div in out:
        if not isinstance(div, Dividend):
            raise TypeError(f"spy_dividends holds a {type(div).__name__}, not a Dividend")
        if div.ex_date > window.end:
            raise DevWindowError(f"SPY has a dividend on {div.ex_date}, after the {window.name} window end {window.end} (D9)")
    return out


# --------------------------------------------------------------------------- candidates


@dataclass(frozen=True)
class Candidate:
    """One registry entry (handover D6): a family, a rule set, an allocator or strategy, fixed
    params, a one-line rationale, the date it was appended, and its declared owner inputs.

    ``allocator`` is a ``strategies.base.Strategy`` exactly when ``rules`` run the bracket
    simulator (``sim.rules.is_bracket``), and an ``Allocator`` otherwise. ``owner_inputs`` is sorted
    and unique; the registry test checks it equals ``candidate_owner_inputs(self)``, and D8
    always uses the computed value.
    """

    id: str
    family: str
    rules: TradeRules
    allocator: Allocator | Strategy
    params: Any
    rationale: str
    added: date
    owner_inputs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or _ID.fullmatch(self.id) is None:
            raise ValueError(f"candidate id must match {_ID.pattern}, got {self.id!r}")
        if not isinstance(self.family, str) or _FAMILY.fullmatch(self.family) is None:
            raise ValueError(f"{self.id}: family must be F1..F11, REF or a lab method id, got {self.family!r}")
        if not isinstance(self.rules, TradeRules):
            raise TypeError(f"{self.id}: rules must be a TradeRules, got {type(self.rules).__name__}")
        if is_bracket(self.rules):
            if not isinstance(self.allocator, Strategy) or isinstance(self.allocator, Allocator):
                raise TypeError(f"{self.id}: rules {self.rules.id} need a bracket Strategy, got {type(self.allocator).__name__}")
        elif not isinstance(self.allocator, Allocator):
            raise TypeError(f"{self.id}: rules {self.rules.id} need an Allocator, got {type(self.allocator).__name__}")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise ValueError(f"{self.id}: rationale must be a non-empty str")
        if "\n" in self.rationale or "\r" in self.rationale:
            raise ValueError(f"{self.id}: rationale must be one line")
        _as_date(f"{self.id}: added", self.added)
        if not isinstance(self.owner_inputs, tuple):
            raise TypeError(f"{self.id}: owner_inputs must be a tuple of str")
        for item in self.owner_inputs:
            if not isinstance(item, str) or not item:
                raise ValueError(f"{self.id}: owner_inputs holds {item!r}, not a non-empty str")
        if self.owner_inputs != tuple(sorted(set(self.owner_inputs))):
            raise ValueError(f"{self.id}: owner_inputs must be sorted and unique, got {self.owner_inputs!r}")


def _reads(c: Candidate) -> tuple[tuple[str, ...], int, bool]:
    """(symbols the window must cover, sorted and including SPY; lookback; reads members)."""
    if is_bracket(c.rules):
        lookback: object = c.allocator.lookback
        symbols: tuple[str, ...] = ()
        members = True
    else:
        lookback = c.allocator.lookback(c.params)
        symbols = tuple(c.allocator.symbols(c.params))
        members = bool(c.allocator.uses_members(c.params))
    if isinstance(lookback, bool) or not isinstance(lookback, int) or lookback < 1:
        raise ValueError(f"{c.id}: lookback must be an int >= 1, got {lookback!r}")
    for symbol in symbols:
        if not isinstance(symbol, str) or not symbol:
            raise ValueError(f"{c.id}: symbols() returned {symbol!r}, not a non-empty str")
    return tuple(sorted(set(symbols) | {SPY})), lookback, members


def _holds(c: Candidate) -> tuple[str, ...]:
    if is_bracket(c.rules):
        return ()
    return tuple(sorted(set(c.allocator.holds(c.params))))


def candidate_owner_inputs(c: Candidate) -> tuple[str, ...]:
    """What the owner must verify before ``c`` is Gotrade-executable, sorted and unique.

    ``rule_owner_inputs(c.rules)``, plus ``etf:<symbol>`` for every held instrument outside
    ``DEFAULT_ETFS``, plus ``leverage`` when it holds a leveraged ETF. Empty means executable
    under the conservative defaults.
    """
    if not isinstance(c, Candidate):
        raise TypeError(f"expected a Candidate, got {type(c).__name__}")
    holds = _holds(c)
    out = set(rule_owner_inputs(c.rules))
    for symbol in holds:
        if symbol not in DEFAULT_ETFS:
            out.add(f"etf:{symbol}")
    if any(symbol in LEVERAGED_ETFS for symbol in holds):
        out.add("leverage")
    return tuple(sorted(out))


def candidate_window(market: Market, c: Candidate, *, window: Window = DEV_WINDOW) -> tuple[date, date]:
    """``(start, window.end)``: ``start`` is the first NYSE session S such that every symbol the
    candidate reads, and SPY, has at least ``lookback`` bars dated on or before
    ``prev_session(S)``; for candidates that read index members, also
    ``prev_session(S) >= MEMBERSHIP_START``; and never before ``window.start``. ``DESIGN_V0``
    strategies read SPY and members with ``strategy.lookback``. The idle instrument is not part
    of the rule (idle cash earns nothing until it has a bar).

    ``window`` defaults to ``DEV_WINDOW``, whose ``start`` is ``date.min``: on the dev window
    the floor can never bind and the result is exactly what it has always been. On the test
    window the floor is the window's opening session, so a long history in the store warms the
    lookback up without the run reaching back into it.

    ``ValueError`` when a symbol is missing or has fewer than ``lookback`` bars;
    ``DevWindowError`` when the window would start after ``window.end`` or the market holds
    data after it.
    """
    _check_market(market, window)
    if not isinstance(c, Candidate):
        raise TypeError(f"expected a Candidate, got {type(c).__name__}")
    symbols, lookback, members = _reads(c)
    ready = MEMBERSHIP_START if members else date.min
    for symbol in symbols:
        h = market.history.get(symbol)
        n = 0 if h is None else len(h)
        if h is None or n < lookback:
            raise ValueError(f"{c.id}: {symbol} has {n} bars in the market, the candidate needs {lookback}")
        enough = h.dates[lookback - 1].item()
        if enough > ready:
            ready = enough
    data_date = ready if dates.is_session(ready) else dates.next_session(ready)
    start = dates.next_session(data_date)
    if start < window.start:
        start = window.start if dates.is_session(window.start) else dates.next_session(window.start)
    if start > window.end:
        raise DevWindowError(f"{c.id}: its {window.name} window would start on {start}, after the {window.name} window end {window.end} (D9)")
    return start, window.end


def beats_spy_tr(
    total_return: float | None,
    spy_total_return: float | None,
    mwr: float | None = None,
    spy_mwr: float | None = None,
) -> bool:
    """``FAILURE_LABELS[0]``: does this run beat total-return SPY? The single definition.

    **Money-weighted when both sides have one**, and the total-return comparison otherwise.

    Once a book receives deposits, its total return is not a return: measured on the owner's real
    funding plan, a book that earns nothing at all reports +600.0%. So when both the run and its
    benchmark carry a money-weighted return -- which happens exactly when both were fed a
    contribution schedule -- the comparison is made in that, the rate the money actually earned.

    The fallback is not a second bar, it is the same condition in the only number the row has.
    Every one of the 128 recorded lab trials ran with no deposits and has no money-weighted
    return, so every one of them is judged exactly as it is today and no recorded verdict changes
    meaning. ``lab.store.owner_failures`` calls this rather than writing the comparison again, so
    the gate cannot drift between the runner and the re-read.

    Worth knowing: when SPY is dollar-cost-averaged on the identical schedule from the identical
    opening cash, the two branches agree in direction anyway -- both sides divide by the same
    opening cash, so comparing total returns *is* comparing ending equity. The money-weighted
    branch is what makes the number a human reads true, and what keeps the comparison right if
    the two sides are ever fed differently.
    """
    if mwr is not None and spy_mwr is not None:
        return mwr > spy_mwr
    return total_return is not None and spy_total_return is not None and total_return > spy_total_return


# --------------------------------------------------------------------------- rows


@dataclass(frozen=True)
class DevRow:
    """One candidate's result on its window and its D8 standing.

    ``spy_tr``/``spy_price`` are the SPY curves' metrics on the same window and starting cash.
    ``failed`` lists the D8 conditions the row misses, in ``FAILURE_LABELS`` order;
    ``eligible`` is ``failed == ()``. ``window`` is the window the row was produced on and
    defaults to ``DEV_WINDOW``, so a row built without one is a dev row and is checked against
    ``DEV_END`` exactly as before. ``window.name`` is what a lab trial records.
    """

    candidate: Candidate
    start: date
    end: date
    stats: RunStats
    spy_tr: Metrics
    spy_price: Metrics
    beats_spy: bool
    mar: float | None
    eligible: bool
    failed: tuple[str, ...]
    window: Window = DEV_WINDOW

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, Candidate):
            raise TypeError(f"candidate must be a Candidate, got {type(self.candidate).__name__}")
        if not isinstance(self.window, Window):
            raise TypeError(f"window must be a Window, got {type(self.window).__name__}")
        _as_date("start", self.start)
        _as_date("end", self.end)
        check_dev_session(self.end, self.window)
        if self.start > self.end:
            raise ValueError(f"{self.candidate.id}: start {self.start} is after end {self.end}")
        if self.start < self.window.start:
            raise ValueError(
                f"{self.candidate.id}: start {self.start} is before the {self.window.name} "
                f"window start {self.window.start}"
            )
        if not isinstance(self.stats, RunStats):
            raise TypeError(f"stats must be a RunStats, got {type(self.stats).__name__}")
        for name in ("spy_tr", "spy_price"):
            if not isinstance(getattr(self, name), Metrics):
                raise TypeError(f"{name} must be a Metrics, got {type(getattr(self, name)).__name__}")
        if not isinstance(self.beats_spy, bool) or not isinstance(self.eligible, bool):
            raise TypeError("beats_spy and eligible must be bool")
        if self.mar is not None and (isinstance(self.mar, bool) or not isinstance(self.mar, float)):
            raise TypeError(f"mar must be a float or None, got {type(self.mar).__name__}")
        if not isinstance(self.failed, tuple):
            raise TypeError("failed must be a tuple of FAILURE_LABELS")
        positions: list[int] = []
        for label in self.failed:
            if label not in FAILURE_LABELS:
                raise ValueError(f"{self.candidate.id}: unknown failure {label!r}")
            positions.append(FAILURE_LABELS.index(label))
        if positions != sorted(set(positions)):
            raise ValueError(f"{self.candidate.id}: failed must be unique and in FAILURE_LABELS order")
        if self.eligible != (not self.failed):
            raise ValueError(f"{self.candidate.id}: eligible must equal failed == ()")
        if (FAILURE_LABELS[0] in self.failed) == self.beats_spy:
            raise ValueError(f"{self.candidate.id}: beats_spy disagrees with failed")


def make_row(
    candidate: Candidate,
    start: date,
    end: date,
    stats: RunStats,
    *,
    spy_tr: Metrics,
    spy_price: Metrics,
    window: Window = DEV_WINDOW,
) -> DevRow:
    """The ``DevRow`` for ``candidate``: SPY comparison, MAR and the D8 eligibility checks.

    MAR = rate / max drawdown (None when either is None or the drawdown is 0). The rate is the
    **money-weighted return** when the run received deposits, and the CAGR otherwise -- which is
    the same number, because with no deposits CAGR *is* the money-weighted return. Without the
    switch, a book fed 5,000,000 IDR a month would rank on a CAGR that counts its own deposits as
    growth: measured, a book that earns nothing reports +600.9%, which would outrank every honest
    candidate in the registry.

    Thresholds are read from ``tuning`` at call time; owner inputs are
    ``candidate_owner_inputs(candidate)``. ``window`` defaults to ``DEV_WINDOW`` and is carried
    onto the row.
    """
    if not isinstance(candidate, Candidate):
        raise TypeError(f"expected a Candidate, got {type(candidate).__name__}")
    if not isinstance(stats, RunStats):
        raise TypeError(f"stats must be a RunStats, got {type(stats).__name__}")
    if not isinstance(spy_tr, Metrics):
        raise TypeError(f"spy_tr must be a Metrics, got {type(spy_tr).__name__}")
    m = stats.metrics
    beats = beats_spy_tr(m.total_return, spy_tr.total_return, m.mwr, spy_tr.mwr)
    rate = m.cagr if m.mwr is None else m.mwr
    if rate is None or m.max_drawdown is None or m.max_drawdown == 0:
        mar: float | None = None
    else:
        mar = float(rate / m.max_drawdown)
    passed = (
        beats,
        m.max_drawdown is not None and m.max_drawdown <= tuning.MAX_DRAWDOWN,
        m.profit_factor is not None and m.profit_factor >= tuning.MIN_PROFIT_FACTOR,
        m.trades >= _MIN_TRADES,
        not candidate_owner_inputs(candidate),
    )
    failed = tuple(label for label, ok in zip(FAILURE_LABELS, passed) if not ok)
    return DevRow(
        candidate=candidate,
        start=start,
        end=end,
        stats=stats,
        spy_tr=spy_tr,
        spy_price=spy_price,
        beats_spy=bool(beats),
        mar=mar,
        eligible=not failed,
        failed=failed,
        window=window,
    )


# --------------------------------------------------------------------------- running


def _funded_stats(result: RunResult | BookResult) -> RunStats:
    """``run_stats(result)``, with the money-weighted return filled in for a funded **book** run.

    ``metrics.run_metrics`` reads ``RunResult.cashflows``, so a bracket run already carries its
    IRR. A ``BookResult`` does not: ``book_runner._book_result_stats`` builds its ``Metrics``
    through ``_book_metrics``, which calls ``strategy_metrics`` without cashflows. Measured on the
    dev registry, a book candidate run on ``OWNER_MONTHLY`` reported ``mwr=None`` while its
    dollar-cost-averaged SPY reported 0.345 -- so ``make_row`` ranked it on a CAGR that counts the
    owner's own deposits as growth, which is the +600.9% lie this phase exists to end, surviving on
    the engine four of the roster's six entries actually run.

    The gap is one keyword in ``book_runner._book_metrics``, which belongs to phase 5 and which
    this phase leaves alone (Interface Contract, "Leaves alone"); see Handoffs. Filling it here
    keeps the change inside this phase's Owns and is complete for every funded run that can exist
    today, because ``dev`` is the only caller that passes a schedule -- every other ``run_stats``
    caller runs unfunded, where ``cashflows`` is ``()`` and this is a no-op.

    The equity curve is the one ``_book_result_stats`` itself measured (``_equities`` is
    ``(date, float(equity))`` per snapshot), so the IRR and the CAGR beside it are taken over the
    same points.
    """
    stats = run_stats(result)
    cashflows = external_cashflows(result)
    if not cashflows or stats.metrics.mwr is not None:
        return stats
    snaps = [(s.date, float(s.equity_usd)) for s in result.snapshots]
    return replace(
        stats, metrics=replace(stats.metrics, mwr=money_weighted_return(snaps, cashflows))
    )


def _run(
    market: Market,
    spy: Mapping[date, Any],
    dividends: DividendMap,
    spy_dividends: tuple[Dividend, ...],
    c: Candidate,
    prepared: Any,
    window: Window,
    *,
    initial_idr: Decimal = INITIAL_IDR,
    contributions: ContributionSchedule | None = None,
    contribution_fx: Callable[[date], Decimal] | None = None,
) -> tuple[RunResult | BookResult, DevRow]:
    start, end = candidate_window(market, c, window=window)
    check_dev_session(end, window)
    rate: Decimal = market.usd_idr_on(max(start, FX_START))
    run_market = market
    if contribution_fx is not None and start < FX_START:
        raise ValueError(
            f"contribution_fx needs a USD/IDR rate per session, and this window starts {start}, "
            f"before the first rate on {FX_START}"
        )
    if start < FX_START:
        # No USD/IDR before FX_START: the starting cash converts at the FX_START rate. replace()
        # carries history, membership and fundamentals over, so a long window keeps the panel.
        run_market = replace(market, fx=((start, rate),))
    result = run_rules(
        run_market,
        c.allocator,
        c.params,
        c.rules,
        start,
        end,
        prepared=prepared,
        dividends=dividends if c.rules.engine == "book" else {},
        usd_idr=rate,
        # Passed explicitly even at its default: run_rules's own default is the same
        # runner.INITIAL_IDR object, so a caller that passes nothing gets the run it always got,
        # and a caller that passes a recorded capital gets that capital on both engines (run_book
        # and, for DESIGN_V0, run_backtest). The SPY benchmark below starts from
        # result.initial_cash, so it follows the capital without being told.
        initial_idr=initial_idr,
        contributions=contributions,
        contribution_fx=contribution_fx,
    )
    # The benchmark pays what the candidate pays and is fed what the candidate is fed: Gotrade's
    # schedule for a cost_model="gotrade" rule set, the flat 0.1% (unchanged) otherwise, and the
    # candidate's own deposits on the candidate's own dates.
    #
    # `result.cashflows` are already in USD and already dated by the session they landed on, so
    # SPY receives the identical dollars on the identical days however the runner resolved the
    # IDR schedule and the FX. "Beats SPY TR" only means anything when it does: SPY buy-and-hold
    # of a single opening sum against a book fed 5,000,000 IDR a month flatters the book in a
    # rising market and punishes it in a falling one, because the two are holding different
    # amounts of money at different times.
    #
    # The field is passed straight through rather than via `metrics.external_cashflows`, which
    # converts it to float for the IRR: `buy_and_hold` requires Decimal amounts and moves real
    # money through `q()`, so rounding the deposits to binary floats and back would make the
    # benchmark pay a different sum from the book it is benchmarking. The two readers of this
    # field are here and `metrics.external_cashflows`; a rename touches both.
    price, total = spy_curves(
        spy,
        start,
        end,
        result.initial_cash,
        spy_dividends,
        cost_model=c.rules.cost_model,
        contributions=result.cashflows,
    )
    row = make_row(
        c,
        start,
        end,
        _funded_stats(result),
        spy_tr=curve_metrics(total),
        spy_price=curve_metrics(price),
        window=window,
    )
    return result, row


def run_candidate(
    market: Market,
    dividends: DividendMap,
    spy_dividends: Sequence[Dividend],
    c: Candidate,
    *,
    prepared: Any = None,
    window: Window = DEV_WINDOW,
    initial_idr: Decimal = INITIAL_IDR,
    contributions: ContributionSchedule | None = None,
    contribution_fx: Callable[[date], Decimal] | None = None,
) -> tuple[RunResult | BookResult, DevRow]:
    """Run ``c`` once on ``candidate_window(market, c, window=window)``.

    ``dividends`` (symbol -> ex_date -> amount) reach the book engine only; ``spy_dividends``
    feed the total-return SPY curve. ``prepared`` is ``c.allocator.prepare(market.history)``
    or None. Every input is checked against ``window.end`` first (``DevWindowError``), and
    ``window`` defaults to ``DEV_WINDOW``: pass nothing and this is the D9-guarded dev run it
    has always been.

    ``initial_idr`` is the opening book in IDR, converted to USD once at the window's first
    rate (the ``FX_START`` rate for a window that opens earlier). It defaults to
    ``runner.INITIAL_IDR``; see ``run_registry`` for who passes anything else, and why.
    """
    _check_market(market, window)
    spy_divs = _check_dividends(dividends, spy_dividends, window)
    if not isinstance(c, Candidate):
        raise TypeError(f"expected a Candidate, got {type(c).__name__}")
    return _run(
        market, market.spy(), dividends, spy_divs, c, prepared, window,
        initial_idr=initial_idr, contributions=contributions, contribution_fx=contribution_fx,
    )


def run_registry(
    market: Market,
    dividends: DividendMap,
    spy_dividends: Sequence[Dividend],
    registry: Sequence[Candidate],
    *,
    on_result: Callable[[int, RunResult | BookResult, DevRow], None] | None = None,
    window: Window = DEV_WINDOW,
    initial_idr: Decimal = INITIAL_IDR,
    contributions: ContributionSchedule | None = None,
    contribution_fx: Callable[[date], Decimal] | None = None,
) -> tuple[DevRow, ...]:
    """Every candidate, sequentially, in registry order; one row each, in that order.

    ``prepare_for(allocator, market)`` runs once per allocator id within this call (a strategy's
    id for ``DESIGN_V0`` candidates) and is dropped after the last candidate that uses it: that
    is ``allocator.prepare_market(market)`` for a ``MarketAware`` allocator and
    ``allocator.prepare(market.history)`` for every other. Two different objects sharing an id
    are refused. ``on_result(index, result, row)``, when given, is called after each candidate.
    ``window`` defaults to ``DEV_WINDOW``; ``lab test`` is the only caller that passes another.

    ``contributions`` is the funding schedule every candidate is run on
    (``sim.contributions.ContributionSchedule``), or None -- the default, and a lump-sum book that
    never grows. ``lab.runner.run_method`` and ``run_test`` pass ``OWNER_MONTHLY``, and
    ``lab.name_count`` passes it unless ``--lump``; ``lab.remeasure`` and ``lab.real_costs`` pass
    whatever the trial they are reproducing was recorded on
    (``lab.runner.recorded_contributions``), so a recorded trial re-runs as the measurement it was.
    Every one of the 128 trials recorded before the lab was funded has no ``trial_funding`` row and
    re-runs unfunded, byte-for-byte as it did. When a schedule is given, the book is fed the
    deposits AND ``spy_curves`` receives the same dollars on the same sessions, so "beats SPY TR"
    stays a comparison of two books holding the same money.

    ``initial_idr`` is every candidate's opening book in IDR, defaulting to
    ``runner.INITIAL_IDR`` -- the live capital, which is what a *new* trial runs at, so
    ``lab.runner.run_method``, ``run_test`` and ``lab.name_count`` pass nothing. It is the second
    half of the same rule as ``contributions``: a path that re-runs a recorded trial must pass the
    capital that trial was recorded at, or it reproduces a different measurement. Whole-share
    rounding makes capital result-moving, and ``INITIAL_IDR`` moved from 20,000,000 to 10,000,000
    on 2026-10-08 (``d79fc83``): measured on 2026-10-09, ``lab remeasure`` of M0007, M0011 and
    all 54 P7a seed trials diverges at the live 10,000,000 and reproduces every one exactly at
    20,000,000. The capital reaches both engines through ``run_rules`` and, via
    ``result.initial_cash``, the SPY benchmark, so "beats SPY TR" still compares two books that
    opened with the same money.
    """
    _check_market(market, window)
    spy_divs = _check_dividends(dividends, spy_dividends, window)
    if isinstance(registry, (str, bytes)) or not isinstance(registry, Sequence):
        raise TypeError(f"registry must be a sequence of Candidate, got {type(registry).__name__}")
    candidates = tuple(registry)
    if len(candidates) > MAX_CANDIDATES:
        raise ValueError(f"the registry holds {len(candidates)} candidates, the cap is {MAX_CANDIDATES} (D6)")
    owners: dict[str, object] = {}
    last_use: dict[str, int] = {}
    ids: set[str] = set()
    for i, c in enumerate(candidates):
        if not isinstance(c, Candidate):
            raise TypeError(f"registry[{i}] is a {type(c).__name__}, not a Candidate")
        if c.id in ids:
            raise ValueError(f"candidate id {c.id} appears twice")
        ids.add(c.id)
        key = c.allocator.id
        owner = owners.get(key)
        if owner is not None and owner is not c.allocator:
            raise ValueError(f"two different allocator objects share the id {key!r}")
        owners[key] = c.allocator
        last_use[key] = i
    spy = market.spy()
    cache: dict[str, Any] = {}
    rows: list[DevRow] = []
    for i, c in enumerate(candidates):
        key = c.allocator.id
        if key not in cache:
            cache[key] = prepare_for(c.allocator, market)
        result, row = _run(
            market, spy, dividends, spy_divs, c, cache[key], window,
            initial_idr=initial_idr, contributions=contributions, contribution_fx=contribution_fx,
        )
        if last_use[key] == i:
            del cache[key]
        rows.append(row)
        if on_result is not None:
            on_result(i, result, row)
    return tuple(rows)


# --------------------------------------------------------------------------- D8 and D7


def _rank_key(row: DevRow) -> tuple[int, float, str]:
    if row.mar is None:
        return (1, 0.0, row.candidate.id)
    return (0, -row.mar, row.candidate.id)


def finalists(rows: Sequence[DevRow]) -> tuple[DevRow, ...]:
    """D8: the eligible rows ranked by MAR (highest first, ties by candidate id), keeping the
    first row of each family, at most three. ``()`` when none is eligible."""
    all_rows = tuple(rows)
    for row in all_rows:
        if not isinstance(row, DevRow):
            raise TypeError(f"expected DevRow values, got {type(row).__name__}")
    chosen: list[DevRow] = []
    families: set[str] = set()
    for row in sorted((r for r in all_rows if r.eligible), key=_rank_key):
        if row.candidate.family in families:
            continue
        chosen.append(row)
        families.add(row.candidate.family)
        if len(chosen) == _MAX_FINALISTS:
            break
    return tuple(chosen)


def _real(name: str, x: object) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise TypeError(f"{name} must be a number, got {type(x).__name__}")
    return float(x)


def deflated_sharpe(
    sharpe_daily: float,
    n_trials: int,
    var_trials: float,
    t: int,
    skew: float,
    kurt: float,
) -> float | None:
    """Bailey & López de Prado (2014), the deflated Sharpe ratio.

    ``SR* = sqrt(var_trials) × ((1 − γ)·Φ⁻¹(1 − 1/N) + γ·Φ⁻¹(1 − 1/(N·e)))`` with γ the
    Euler-Mascheroni constant, then
    ``DSR = Φ((SR − SR*)·sqrt(t − 1) / sqrt(1 − skew·SR + (kurt − 1)/4·SR²))``.
    ``sharpe_daily`` and ``var_trials`` are per-period (not annualized); ``t`` is the number of
    returns; ``kurt`` is the non-excess kurtosis (3 for a normal). None when undefined:
    ``n_trials < 2``, ``t < 2``, ``var_trials < 0``, a non-finite input, or a non-positive
    term under the root.
    """
    sr = _real("sharpe_daily", sharpe_daily)
    var = _real("var_trials", var_trials)
    g3 = _real("skew", skew)
    g4 = _real("kurt", kurt)
    for name, value in (("n_trials", n_trials), ("t", t)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    if not all(math.isfinite(v) for v in (sr, var, g3, g4)):
        return None
    if n_trials < 2 or t < 2 or var < 0:
        return None
    normal = NormalDist()
    expected_max = (1 - _EULER_GAMMA) * normal.inv_cdf(1 - 1 / n_trials) + _EULER_GAMMA * normal.inv_cdf(
        1 - 1 / (n_trials * math.e)
    )
    sr_star = math.sqrt(var) * expected_max
    radicand = 1 - g3 * sr + (g4 - 1) / 4 * sr * sr
    if radicand <= 0:
        return None
    return normal.cdf((sr - sr_star) * math.sqrt(t - 1) / math.sqrt(radicand))
