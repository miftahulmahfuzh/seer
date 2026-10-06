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
earlier converts the 20,000,000 IDR starting capital at the ``FX_START`` rate. FX feeds the
starting cash only, so no decision depends on it.
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
from seer_engine.backtest.metrics import Metrics, curve_metrics
from seer_engine.backtest.runner import RunResult
from seer_engine.backtest.window import Window
from seer_engine.sim.rules import DEFAULT_ETFS, LEVERAGED_ETFS, TradeRules, rule_owner_inputs
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
    "max DD <= 15%",
    "PF >= 1.3",
    ">= 100 trades",
    "owner inputs",
)

_MIN_TRADES = 100  # design §1 go-live item 2
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

    ``allocator`` is a ``strategies.base.Strategy`` exactly when ``rules`` is ``DESIGN_V0``
    (``engine == "bracket_v0"``), and an ``Allocator`` otherwise. ``owner_inputs`` is sorted
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
        if self.rules.engine == "bracket_v0":
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
    if c.rules.engine == "bracket_v0":
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
    if c.rules.engine == "bracket_v0":
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

    MAR = CAGR / max drawdown (None when either is None or the drawdown is 0). Thresholds are
    read from ``tuning`` at call time; owner inputs are ``candidate_owner_inputs(candidate)``.
    ``window`` defaults to ``DEV_WINDOW`` and is carried onto the row.
    """
    if not isinstance(candidate, Candidate):
        raise TypeError(f"expected a Candidate, got {type(candidate).__name__}")
    if not isinstance(stats, RunStats):
        raise TypeError(f"stats must be a RunStats, got {type(stats).__name__}")
    if not isinstance(spy_tr, Metrics):
        raise TypeError(f"spy_tr must be a Metrics, got {type(spy_tr).__name__}")
    m = stats.metrics
    beats = m.total_return is not None and spy_tr.total_return is not None and m.total_return > spy_tr.total_return
    if m.cagr is None or m.max_drawdown is None or m.max_drawdown == 0:
        mar: float | None = None
    else:
        mar = float(m.cagr / m.max_drawdown)
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


def _run(
    market: Market,
    spy: Mapping[date, Any],
    dividends: DividendMap,
    spy_dividends: tuple[Dividend, ...],
    c: Candidate,
    prepared: Any,
    window: Window,
) -> tuple[RunResult | BookResult, DevRow]:
    start, end = candidate_window(market, c, window=window)
    check_dev_session(end, window)
    rate: Decimal = market.usd_idr_on(max(start, FX_START))
    run_market = market
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
    )
    price, total = spy_curves(spy, start, end, result.initial_cash, spy_dividends)
    row = make_row(
        c,
        start,
        end,
        run_stats(result),
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
) -> tuple[RunResult | BookResult, DevRow]:
    """Run ``c`` once on ``candidate_window(market, c, window=window)``.

    ``dividends`` (symbol -> ex_date -> amount) reach the book engine only; ``spy_dividends``
    feed the total-return SPY curve. ``prepared`` is ``c.allocator.prepare(market.history)``
    or None. Every input is checked against ``window.end`` first (``DevWindowError``), and
    ``window`` defaults to ``DEV_WINDOW``: pass nothing and this is the D9-guarded dev run it
    has always been.
    """
    _check_market(market, window)
    spy_divs = _check_dividends(dividends, spy_dividends, window)
    if not isinstance(c, Candidate):
        raise TypeError(f"expected a Candidate, got {type(c).__name__}")
    return _run(market, market.spy(), dividends, spy_divs, c, prepared, window)


def run_registry(
    market: Market,
    dividends: DividendMap,
    spy_dividends: Sequence[Dividend],
    registry: Sequence[Candidate],
    *,
    on_result: Callable[[int, RunResult | BookResult, DevRow], None] | None = None,
    window: Window = DEV_WINDOW,
) -> tuple[DevRow, ...]:
    """Every candidate, sequentially, in registry order; one row each, in that order.

    ``prepare_for(allocator, market)`` runs once per allocator id within this call (a strategy's
    id for ``DESIGN_V0`` candidates) and is dropped after the last candidate that uses it: that
    is ``allocator.prepare_market(market)`` for a ``MarketAware`` allocator and
    ``allocator.prepare(market.history)`` for every other. Two different objects sharing an id
    are refused. ``on_result(index, result, row)``, when given, is called after each candidate.
    ``window`` defaults to ``DEV_WINDOW``; ``lab test`` is the only caller that passes another.
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
        result, row = _run(market, spy, dividends, spy_divs, c, cache[key], window)
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
