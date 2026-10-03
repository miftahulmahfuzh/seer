# Phase 9: Dev runner: window guard, candidate windows, D8, deflated Sharpe

**Plan set:** `TRADE_RULES_DEV_SEARCH_PLAN.md`
**Analysis:** `20261003-195606-T7R2_code_analyzer.md`
**Satisfies:** R4 (the dev window is enforced in code and a test proves it), R5 (the `Candidate` type, its validation and its computed owner inputs, the ≤ 60 cap at run time), R8 (pure module under the purity glob; `==` rows on a re-run)
**Depends on:** Phase 3 (and through it phases 1 and 2)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/backtest`

---

## Goal

After this phase, `seer_engine.backtest.dev` exists as a pure module. It turns a registry
candidate into one dev-window run and one `DevRow`. Each candidate runs on its own window,
which ends at `DEV_END = 2015-10-16`. Each row is compared with SPY on that same window and
starting cash. The phase also adds the D8 finalist rule and the deflated Sharpe ratio. Any
date, bar, FX row or dividend after 2015-10-16 that reaches a public entry point raises
`DevWindowError`. That is the code-level half of D9, and `tests/test_backtest_dev.py` proves it.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates (all in `engine/src/seer_engine/backtest/dev.py`, new):**
- constants `DEV_END = date(2015, 10, 16)`, `MEMBERSHIP_START = date(1996, 1, 2)`,
  `FX_START = date(1999, 1, 4)`, `MAX_CANDIDATES = 60`;
- `class DevWindowError(ValueError)`;
- `def check_dev_session(d: date) -> None`;
- `@dataclass(frozen=True) class Candidate(id, family, rules, allocator, params, rationale, added, owner_inputs)`,
  with field order and types exactly as in the index contract, keyword-constructible;
- `def candidate_owner_inputs(c: Candidate) -> tuple[str, ...]`;
- `def candidate_window(market: Market, c: Candidate) -> tuple[date, date]`;
- `@dataclass(frozen=True) class DevRow(candidate, start, end, stats, spy_tr, spy_price, beats_spy, mar, eligible, failed)`,
  with field order exactly as in the contract;
- `def run_candidate(market, dividends, spy_dividends, c, *, prepared=None) -> tuple[RunResult | BookResult, DevRow]`;
- `def run_registry(market, dividends, spy_dividends, registry, *, on_result=None) -> tuple[DevRow, ...]`.
  **Additive extension:** the keyword-only `on_result` (default `None`) is not in the index
  contract. See Interface notes 1.
- `def finalists(rows: Sequence[DevRow]) -> tuple[DevRow, ...]`;
- `def deflated_sharpe(sharpe_daily, n_trials, var_trials, t, skew, kurt) -> float | None`;
- **two additive public names** that are not in the index contract:
  - `FAILURE_LABELS: tuple[str, ...] = ("beats SPY TR", "max DD <= 15%", "PF >= 1.3", ">= 100 trades", "owner inputs")`.
    This is the contract's fixed failure order, given a name.
  - `def make_row(candidate, start, end, stats, *, spy_tr, spy_price) -> DevRow`. This is the
    one place the eligibility and MAR rules live. `run_candidate` uses it. Phases 10 and 11
    can use it to build synthetic rows in their tests.

**Signature changes:** none (every symbol is new).

**Requires (from earlier phases, as the index contract states them):**
- Phase 1, `seer_engine.sim.rules`: `TradeRules` (a frozen dataclass with an `.engine` field,
  where `"bracket_v0"` occurs only for `DESIGN_V0`), `DESIGN_V0`, `MONTHLY_HOLD`,
  `DAILY_SWITCH`, `DAILY_SWITCH_TBILL`, `rule_owner_inputs(rules) -> tuple[str, ...]`,
  `DEFAULT_ETFS`, `LEVERAGED_ETFS`. `rule_owner_inputs(MONTHLY_HOLD) == ()`,
  `rule_owner_inputs(DAILY_SWITCH) == ()` and `rule_owner_inputs(DAILY_SWITCH_TBILL) == ("etf:BIL",)`.
- Phase 1, `seer_engine.sim.book`: `Target(symbol, weight, last, limit=None, stop=None, take=None)`
  (used by the test's fake allocators only).
- Phase 2, `seer_engine.strategies.allocator`: the `@runtime_checkable` `Allocator` protocol,
  with the members `id`, `lookback(params)`, `symbols(params)`, `holds(params)`,
  `uses_members(params)`, `targets(...)`, `prepare(history)` and `targets_prepared(...)`.
  - `prepare(history)` takes no params, so its output depends only on the history. That is
    what makes it correct to cache the prepared value by allocator id (see Decisions).
- Phase 3, `seer_engine.backtest.book_runner`: `BookResult` (with `.initial_cash`,
  `.usd_idr`, `.snapshots`), `DividendMap`, `RunStats` (frozen dataclass; keyword fields
  `metrics, exposure, turnover, costs_usd, gross_pnl_usd, cost_drag, dividends_usd, sharpe,
  daily_returns, year_returns, worst_year`), `run_stats(result)`, and
  `run_rules(market, strategy_or_allocator, params, rules, start, end, *, prepared=None, dividends={}, usd_idr=None)`.
  - With `DESIGN_V0` and a `Strategy`, it accepts `usd_idr == market.usd_idr_on(start)` and
    `dividends={}`, and returns `run_backtest(...)` unchanged.
- Existing and unchanged:
  - `backtest.benchmark.spy_curves` and `Dividend`;
  - `backtest.metrics.Metrics` and `curve_metrics`;
  - `backtest.market.Market`, `Membership` and `SPY`;
  - `backtest.runner.RunResult`, `run_backtest` and `INITIAL_IDR`;
  - `backtest.tuning.MAX_DRAWDOWN` and `MIN_PROFIT_FACTOR`;
  - `strategies.base.Strategy`;
  - `seer_engine.dates`.

**Leaves alone (owned by others):**
- every existing module (the frozen set and everything else);
- `sim/rules.py` and `sim/book.py` (phase 1);
- `strategies/allocator.py` (phase 2);
- `backtest/book_runner.py` (phase 3);
- `seer_engine/research.py` (phase 4). It is **not imported**, and a test enforces that.
- `backtest/dev_report.py` (phase 10), `backtest/registry.py` (phase 11);
- `commands/backtest_dev.py` and `backtest/io.py` (phase 12); docs (phase 13).

### Interface notes for the reconciler

1. **`run_registry(..., *, on_result=None)`.**
   - `on_result(index, result, row)` is called after each candidate, in registry order.
   - Why it exists:
     - `DevRow` carries no equity curve, but phase 10's `DevReport.curves` (month-end equity
       per candidate) needs the `RunResult`/`BookResult`.
     - Phase 12 has to time every candidate, and `dev.py` is pure and has no clock.
   - The callback gives phase 12 both: the result, and a hook to time from. It does this
     without phase 12 re-implementing the prepare cache.
   - It defaults to `None`, so a caller written against the bare contract is unaffected.
2. **What the D9 guard rejects.** `candidate_window`, `run_candidate` and `run_registry`
   reject:
   - a market holding **any** bar dated after `DEV_END`;
   - a market whose last FX row is after `DEV_END`.

   `run_candidate` and `run_registry` also reject any dividend (in the map or in
   `spy_dividends`) dated after `DEV_END`.

   The research store (phase 4) satisfies this by construction. Phase 11's smoke market
   (`dates.sessions(2013-12-02, DEV_END)`, FX on 2013-12-02, dividends in 2015-03 and
   2015-06) satisfies it too. **Phase 12's command tests must build markets that end on or
   before `DEV_END`.**
3. **`Candidate.__post_init__` validates shape only.** It checks the id and family patterns,
   the rules/allocator pairing, the rationale, the `added` date, and that `owner_inputs` is a
   sorted, unique tuple of non-empty strings.
   - It does **not** require `owner_inputs == candidate_owner_inputs(self)`. That equality is
     phase 11's registry test, as the contract says.
   - D8's "owner inputs" check uses the **computed** `candidate_owner_inputs(c)`, never the
     declared field. A wrong declaration therefore cannot make a candidate eligible.
4. **The rules/allocator pairing is enforced** (`TypeError`):
   - `rules.engine == "bracket_v0"` requires a `Strategy` that is not an `Allocator`;
   - any other rules require an `Allocator`.
5. **`DESIGN_V0` runs are given `dividends={}`.** That rule set has `dividends=False`, and
   `run_backtest` takes no dividends. They are also given `usd_idr` equal to the run market's
   `usd_idr_on(start)` (see Decisions, FX).
6. **Phase 10, deflated Sharpe units.**
   - `RunStats.sharpe` is annualized (`× sqrt(252)`). `deflated_sharpe` takes the
     **per-period (daily)** Sharpe, so pass `stats.sharpe / sqrt(252)`.
   - `var_trials` is the variance of the trials' **daily** Sharpe ratios.
   - `t` is the number of daily returns.
   - `kurt` is the **non-excess** kurtosis (3 for a normal distribution).
7. **The `research.DEV_END == dev.DEV_END` equality test is not in this phase.** Phase 4 is
   not among this phase's dependencies. It is handed to phase 12, whose dependencies (4, 10,
   11) cover both modules.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/dev.py` | create (line 1) | the whole module, below |
| `engine/tests/test_backtest_dev.py` | create (line 1) | 50 collected tests (counted below) |

No existing file is modified. `tests/test_strategy_purity.py` globs `backtest/*.py`, so it
covers `dev.py` without an edit.

## Decisions (made here, recorded for the reconciler)

| Fork | Chosen | Why |
|---|---|---|
| What "a session after DEV_END given to every entry point" means when no entry point takes an `end` | A date argument (`check_dev_session`, `DevRow.end` and therefore `make_row`) is checked. So is the **data** handed in: the market's bars, its FX rows, the dividend map and `spy_dividends`. Every run ends at `DEV_END` by construction, and there is no `end` parameter to misuse | D9 says "the dev runner refuses any session after 2015-10-16". Data after the cutoff is the only route by which a later session could reach a number. The handover also says commands "never take an `--end`" |
| Window rule details | `ready = max over (symbols(params) ∪ {SPY}) of the date of each symbol's lookback-th bar`, then `max(ready, MEMBERSHIP_START)` when the candidate uses members. The data date is the first NYSE session on or after `ready`, and `start = next_session(data_date)`. A symbol that is missing or short → `ValueError`. `start > DEV_END` → `DevWindowError` | Index contract; handover §8 ("start where **all** its instruments have ≥ 200 bars") |
| The idle instrument (`rules.idle_symbol`, e.g. BIL) in the window rule | **Not** included | Index Decision: "Idle cash earns 0% while BIL has no bar". Including it would push every T-bill candidate's start to BIL's launch (2007) |
| FX before `FX_START` | `rate = market.usd_idr_on(max(start, FX_START))`. When `start < FX_START`, the run uses a copy of the market (same `history` and `membership` objects) whose `fx` is the single row `(start, rate)`. That way the unchanged `run_backtest` computes `usd_idr_on(start) == rate`, and `run_rules`' `DESIGN_V0` equality check holds. `usd_idr=rate` is passed in both cases | Index Decision "FX before 1999-01-04"; FX is used only for the starting cash (`run_backtest` and `run_book` read it once, at `start`), so no decision changes |
| MAR with a zero drawdown | `mar = None` (contract). In `finalists`, eligible rows with `mar is None` rank **after** every row that has a MAR, then by id | Conservative: an unmeasurable ratio does not jump the queue. In practice this cannot happen with ≥ 100 trades |
| The prepare cache | One `prepare(market.history)` per allocator id per `run_registry` call. Two **different** objects with the same id in one registry → `ValueError`, before anything runs. An entry is dropped after the last candidate that uses it, to bound memory | Index contract ("keyed by allocator.id"); prepare has no params, so the id is a sound key only while one object stands behind it |
| `deflated_sharpe` undefined cases | `None` when `n_trials < 2` (Φ⁻¹(0) is undefined), `t < 2`, `var_trials < 0`, any non-finite float input, or `1 − skew·SR + (kurt−1)/4·SR² <= 0`. Wrong types (bool, str, …) → `TypeError` | Contract: "None when undefined" |
| Strict vs. non-strict thresholds | beats SPY: strict `>`, and `None` fails. DD: `<= tuning.MAX_DRAWDOWN`, and `None` fails. PF: `>= tuning.MIN_PROFIT_FACTOR`, `inf` passes and `None` fails. Trades: `>= 100` | Same as `metrics.checklist`/`tuning.qualifies`; thresholds read from `tuning` at call time (monkeypatch-tested) |

## Implementation Steps

### Step 1: Create the dev runner module
**File:** `engine/src/seer_engine/backtest/dev.py:1` (new)
**Change:** the whole module.
**Code:**
```python
"""The P7a dev-window runner (handover D1, D3, D6-D9; plan phase 9).

Pure: no database, network, files, clock or randomness (tests/test_strategy_purity.py globs
this module). It never imports ``seer_engine.research``, the impure research store, whose own
``DEV_END`` is a duplicate constant pinned equal to this one by a test.

- **D9, the code-level guard.** ``DEV_END`` is 2015-10-16. Every public entry point that is
  handed a date, a market or dividends raises ``DevWindowError`` (a ``ValueError``) when any
  of them is dated after ``DEV_END``: ``check_dev_session``, ``candidate_window``,
  ``run_candidate``, ``run_registry``, ``make_row`` and ``DevRow`` itself. Nothing takes an
  ``end``: every candidate runs to ``DEV_END``.
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
from dataclasses import dataclass
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
from seer_engine.sim.rules import DEFAULT_ETFS, LEVERAGED_ETFS, TradeRules, rule_owner_inputs
from seer_engine.strategies.allocator import Allocator
from seer_engine.strategies.base import Strategy

DEV_END = date(2015, 10, 16)  # last dev session; 2015-10-19 opens the P7b test window
MEMBERSHIP_START = date(1996, 1, 2)  # first sp500_history.csv row
FX_START = date(1999, 1, 4)  # first Frankfurter USD/IDR row (verified 2026-10-03)
MAX_CANDIDATES = 60  # handover D6

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
_FAMILY = re.compile(r"F([1-9]|1[01])|REF")


class DevWindowError(ValueError):
    """A session, bar, FX row or dividend after ``DEV_END`` reached the dev runner (D9)."""


def _as_date(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    return d


def check_dev_session(d: date) -> None:
    """Raise ``DevWindowError`` when ``d`` is after ``DEV_END`` (``TypeError`` for a non-date)."""
    _as_date("session", d)
    if d > DEV_END:
        raise DevWindowError(f"session {d} is after the dev window end {DEV_END} (D9)")


def _check_market(market: object) -> Market:
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    for symbol in sorted(market.history):
        last = market.history[symbol].last_date()
        if last is not None and last > DEV_END:
            raise DevWindowError(f"{symbol} has a bar on {last}, after the dev window end {DEV_END} (D9)")
    if market.fx and market.fx[-1][0] > DEV_END:
        raise DevWindowError(f"the market has a usd_idr row on {market.fx[-1][0]}, after the dev window end {DEV_END} (D9)")
    return market


def _check_dividends(dividends: object, spy_dividends: object) -> tuple[Dividend, ...]:
    if not isinstance(dividends, Mapping):
        raise TypeError(f"dividends must be a Mapping, got {type(dividends).__name__}")
    for symbol in sorted(dividends):
        by_date = dividends[symbol]
        if not isinstance(by_date, Mapping):
            raise TypeError(f"dividends[{symbol!r}] must be a Mapping of ex_date -> amount")
        late = [d for d in by_date if _as_date(f"{symbol} ex_date", d) > DEV_END]
        if late:
            raise DevWindowError(f"{symbol} has a dividend on {min(late)}, after the dev window end {DEV_END} (D9)")
    if isinstance(spy_dividends, (str, bytes)) or not isinstance(spy_dividends, Sequence):
        raise TypeError(f"spy_dividends must be a sequence of Dividend, got {type(spy_dividends).__name__}")
    out = tuple(spy_dividends)
    for div in out:
        if not isinstance(div, Dividend):
            raise TypeError(f"spy_dividends holds a {type(div).__name__}, not a Dividend")
        if div.ex_date > DEV_END:
            raise DevWindowError(f"SPY has a dividend on {div.ex_date}, after the dev window end {DEV_END} (D9)")
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
            raise ValueError(f"{self.id}: family must be F1..F11 or REF, got {self.family!r}")
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


def candidate_window(market: Market, c: Candidate) -> tuple[date, date]:
    """``(start, DEV_END)``: ``start`` is the first NYSE session S such that every symbol the
    candidate reads, and SPY, has at least ``lookback`` bars dated on or before
    ``prev_session(S)``; for candidates that read index members, also
    ``prev_session(S) >= MEMBERSHIP_START``. ``DESIGN_V0`` strategies read SPY and members
    with ``strategy.lookback``. The idle instrument is not part of the rule (idle cash earns
    nothing until it has a bar).

    ``ValueError`` when a symbol is missing or has fewer than ``lookback`` bars;
    ``DevWindowError`` when the window would start after ``DEV_END`` or the market holds data
    after it.
    """
    _check_market(market)
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
    if start > DEV_END:
        raise DevWindowError(f"{c.id}: its dev window would start on {start}, after the dev window end {DEV_END} (D9)")
    return start, DEV_END


# --------------------------------------------------------------------------- rows


@dataclass(frozen=True)
class DevRow:
    """One candidate's dev-window result and its D8 standing.

    ``spy_tr``/``spy_price`` are the SPY curves' metrics on the same window and starting cash.
    ``failed`` lists the D8 conditions the row misses, in ``FAILURE_LABELS`` order;
    ``eligible`` is ``failed == ()``.
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

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, Candidate):
            raise TypeError(f"candidate must be a Candidate, got {type(self.candidate).__name__}")
        _as_date("start", self.start)
        _as_date("end", self.end)
        check_dev_session(self.end)
        if self.start > self.end:
            raise ValueError(f"{self.candidate.id}: start {self.start} is after end {self.end}")
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
) -> DevRow:
    """The ``DevRow`` for ``candidate``: SPY comparison, MAR and the D8 eligibility checks.

    MAR = CAGR / max drawdown (None when either is None or the drawdown is 0). Thresholds are
    read from ``tuning`` at call time; owner inputs are ``candidate_owner_inputs(candidate)``.
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
    )


# --------------------------------------------------------------------------- running


def _run(
    market: Market,
    spy: Mapping[date, Any],
    dividends: DividendMap,
    spy_dividends: tuple[Dividend, ...],
    c: Candidate,
    prepared: Any,
) -> tuple[RunResult | BookResult, DevRow]:
    start, end = candidate_window(market, c)
    check_dev_session(end)
    rate: Decimal = market.usd_idr_on(max(start, FX_START))
    run_market = market
    if start < FX_START:
        # No USD/IDR before FX_START: the starting cash converts at the FX_START rate.
        run_market = Market(history=market.history, membership=market.membership, fx=((start, rate),))
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
    )
    return result, row


def run_candidate(
    market: Market,
    dividends: DividendMap,
    spy_dividends: Sequence[Dividend],
    c: Candidate,
    *,
    prepared: Any = None,
) -> tuple[RunResult | BookResult, DevRow]:
    """Run ``c`` once on its dev window ``candidate_window(market, c)``.

    ``dividends`` (symbol -> ex_date -> amount) reach the book engine only; ``spy_dividends``
    feed the total-return SPY curve. ``prepared`` is ``c.allocator.prepare(market.history)``
    or None. Every input is checked against ``DEV_END`` first (``DevWindowError``).
    """
    _check_market(market)
    spy_divs = _check_dividends(dividends, spy_dividends)
    if not isinstance(c, Candidate):
        raise TypeError(f"expected a Candidate, got {type(c).__name__}")
    return _run(market, market.spy(), dividends, spy_divs, c, prepared)


def run_registry(
    market: Market,
    dividends: DividendMap,
    spy_dividends: Sequence[Dividend],
    registry: Sequence[Candidate],
    *,
    on_result: Callable[[int, RunResult | BookResult, DevRow], None] | None = None,
) -> tuple[DevRow, ...]:
    """Every candidate, sequentially, in registry order; one row each, in that order.

    ``prepare(market.history)`` runs once per allocator id within this call (a strategy's id
    for ``DESIGN_V0`` candidates) and is dropped after the last candidate that uses it. Two
    different objects sharing an id are refused. ``on_result(index, result, row)``, when
    given, is called after each candidate.
    """
    _check_market(market)
    spy_divs = _check_dividends(dividends, spy_dividends)
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
            cache[key] = c.allocator.prepare(market.history)
        result, row = _run(market, spy, dividends, spy_divs, c, cache[key])
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
```
**Impact:**
- This is a new module, so nothing existing changes.
- `test_strategy_purity.py` now also imports and AST-scans `dev.py`. The module passes:
  - it has no forbidden imports. `statistics` imports `random` internally, but the AST
    check scans only this source, and the subprocess check forbids only psycopg, requests,
    yfinance and `seer_engine.bars`;
  - it makes no `.now`/`.today`/`.random` attribute access;
  - it calls no `print`/`open`/`input`.
- Import chain: `dev` → `tuning` → `strategies.a`. All of it is pure, with no cycle: no
  existing module imports `dev`.

### Step 2: Create the tests
**File:** `engine/tests/test_backtest_dev.py:1` (new)
**Change:** the whole test module.

**Test count:** 50 collected tests:
- `test_constants` (1), `test_check_dev_session` (1);
- `test_entry_points_reject_a_bar_after_dev_end` (1), `test_entry_points_reject_fx_after_dev_end` (1),
  `test_run_entry_points_reject_dividends_after_dev_end` (1), `test_rows_reject_an_end_after_dev_end` (1);
- `test_dev_does_not_import_research` (1), `test_candidate_validation` (1);
- `test_candidate_owner_inputs` (1);
- `test_window_waits_for_the_latest_launch` (1), `test_window_respects_the_membership_start` (1),
  `test_window_errors` (1);
- `test_design_v0_candidate_runs_through_run_backtest` (1), `test_book_candidate_and_spy_curves` (1),
  `test_window_before_fx_start_converts_at_the_fx_start_rate` (1);
- `test_eligibility_boundaries` (14, parametrized), `test_every_failure_in_order` (1),
  `test_thresholds_come_from_tuning` (1), `test_mar` (1), `test_dev_row_consistency` (1);
- `test_finalists_d8` (1), `test_finalists_none_eligible` (1), `test_finalists_rank_rows_without_mar_last` (1);
- `test_deflated_sharpe_hand_case` (1), `test_deflated_sharpe_second_case` (1),
  `test_deflated_sharpe_at_the_threshold_is_one_half` (1), `test_deflated_sharpe_undefined` (6, parametrized),
  `test_deflated_sharpe_types` (1);
- `test_registry_runs_in_order_and_repeats_equal` (1), `test_registry_prepares_once_per_allocator_id_per_call` (1),
  `test_registry_refuses_shared_ids_duplicates_and_oversize` (1),
  `test_registry_rows_equal_unprepared_single_runs` (1).

That is 30 plain test functions + 14 + 6 parametrized cases = **50**: 15 plain tests before
the boundary test, 14 boundary cases, 11 plain tests from `test_every_failure_in_order`
through `test_deflated_sharpe_types` (excluding the 6 undefined cases), and 4 registry tests.

**Code:**
```python
"""The P7a dev-window runner (plan phase 9; handover D3, D6-D9, §7.4).

Fake allocators (``HoldOne``) and a fake bracket strategy (``DipPicks``) keep every number here
independent of the strategy families (phases 5-8). Every market ends on or before DEV_END,
except the ones built to prove the D9 guard.
"""

from __future__ import annotations

import ast
import math
from collections.abc import Mapping, Set as AbstractSet
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from stratkit import hist, sawtooth

import seer_engine.backtest.dev as dev_module
from seer_engine import dates
from seer_engine.backtest import tuning
from seer_engine.backtest.benchmark import Dividend, spy_curves
from seer_engine.backtest.book_runner import BookResult, RunStats, run_stats
from seer_engine.backtest.dev import (
    DEV_END,
    FAILURE_LABELS,
    FX_START,
    MAX_CANDIDATES,
    MEMBERSHIP_START,
    Candidate,
    DevRow,
    DevWindowError,
    candidate_owner_inputs,
    candidate_window,
    check_dev_session,
    deflated_sharpe,
    finalists,
    make_row,
    run_candidate,
    run_registry,
)
from seer_engine.backtest.market import Market, Membership
from seer_engine.backtest.metrics import Metrics, curve_metrics
from seer_engine.backtest.runner import INITIAL_IDR, RunResult, run_backtest
from seer_engine.prices import to_decimal
from seer_engine.sim import Pick, initial_cash_usd, q
from seer_engine.sim.book import Target
from seer_engine.sim.rules import DAILY_SWITCH, DAILY_SWITCH_TBILL, DESIGN_V0, MONTHLY_HOLD
from seer_engine.strategies.base import History

ADDED = date(2026, 10, 3)


# --------------------------------------------------------------------------- fakes


class HoldOne:
    """A fake ``Allocator``: weight 1 in ``hold`` whenever it has a bar on data_date.

    ``flip``: only on data dates at an even row of ``hold``'s history (so a daily rule set
    trades in and out). Counts ``prepare`` calls and records which prepared object it was given.
    """

    def __init__(self, id: str, hold: str, *, reads: tuple[str, ...] = (), lookback: int = 5,
                 members: bool = False, flip: bool = False) -> None:
        self.id = id
        self.hold = hold
        self.reads = reads
        self._lookback = lookback
        self.members = members
        self.flip = flip
        self.prepare_calls = 0
        self.prepared_seen: list[int] = []

    def lookback(self, params: Any) -> int:
        return self._lookback

    def symbols(self, params: Any) -> tuple[str, ...]:
        return tuple(sorted({self.hold, *self.reads}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (self.hold,)

    def uses_members(self, params: Any) -> bool:
        return self.members

    def _targets(self, history: Mapping[str, History], data_date: date) -> tuple[Target, ...]:
        h = history.get(self.hold)
        if h is None:
            return ()
        i = h.index_of(data_date)
        if i is None or (self.flip and i % 2 == 1):
            return ()
        return (Target(self.hold, Decimal("1"), q(to_decimal(float(h.close[i])))),)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        return self._targets(history, data_date)

    def prepare(self, history: Mapping[str, History]) -> Any:
        self.prepare_calls += 1
        return {"history": dict(history)}

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        self.prepared_seen.append(id(prepared))
        return self._targets(prepared["history"], data_date)


class DipPicks:
    """A fake bracket ``Strategy``: every member with a bar on data_date, limit 1% under its close."""

    id = "DIPFAKE"
    lookback = 3

    def __init__(self) -> None:
        self.prepare_calls = 0

    def _picks(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date) -> list[Pick]:
        out: list[Pick] = []
        for symbol in sorted(members):
            h = history.get(symbol)
            if h is None:
                continue
            i = h.index_of(data_date)
            if i is None:
                continue
            close = to_decimal(float(h.close[i]))
            out.append(Pick(symbol, close, q(close * Decimal("0.99")), q(close * Decimal("1.02")),
                            q(close * Decimal("0.95"))))
        return out

    def picks(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
              params: Any) -> list[Pick]:
        return self._picks(history, members, data_date)

    def prepare(self, history: Mapping[str, History]) -> Any:
        self.prepare_calls += 1
        return dict(history)

    def picks_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                       params: Any) -> list[Pick]:
        return self._picks(prepared, members, data_date)


SPY_HOLD = HoldOne("FAKE", "SPY")


def cand(id: str, family: str = "F1", *, allocator: Any = None, rules: Any = MONTHLY_HOLD,
         owner_inputs: tuple[str, ...] | None = None) -> Candidate:
    """A candidate whose declared owner inputs are the computed ones unless given."""
    c = Candidate(id=id, family=family, rules=rules, allocator=SPY_HOLD if allocator is None else allocator,
                  params=None, rationale="a test candidate", added=ADDED, owner_inputs=())
    return replace(c, owner_inputs=candidate_owner_inputs(c) if owner_inputs is None else owner_inputs)


# --------------------------------------------------------------------------- markets

W_DAYS = dates.sessions(date(2015, 6, 1), DEV_END)  # 98 sessions, 2015-06-01 .. 2015-10-16
XLK_DAYS = dates.sessions(date(2015, 7, 1), DEV_END)  # "launches" 2015-07-01
DIV_DAY = date(2015, 9, 18)
SPY_DIVS = (Dividend(DIV_DAY, Decimal("1.0335")),)
DIVS = {"SPY": {DIV_DAY: Decimal("1.0335")}}
FX_SHORT = ((date(2015, 1, 2), Decimal("12500")),)


def short_market(*, extra_day: date | None = None, fx: tuple = FX_SHORT) -> Market:
    spy_days = W_DAYS + ([extra_day] if extra_day is not None else [])
    return Market(
        history={
            "AAA": hist("AAA", sawtooth(len(W_DAYS), 50.0, 1.0, 0.9), days=W_DAYS),
            "SPY": hist("SPY", sawtooth(len(spy_days), 200.0, 2.0, 1.5), days=spy_days),
            "XLK": hist("XLK", sawtooth(len(XLK_DAYS), 40.0, 0.5, 0.4), days=XLK_DAYS),
        },
        membership=Membership((("AAA", date(1990, 1, 2), None),)),
        fx=fx,
    )


def long_market() -> Market:
    """SPY from 1998-11-02 (before FX_START) to DEV_END: 4,267 sessions; USD/IDR from FX_START."""
    days = dates.sessions(date(1998, 11, 2), DEV_END)
    return Market(
        history={"SPY": hist("SPY", sawtooth(len(days), 100.0, 1.2, 0.8), days=days)},
        membership=Membership(()),
        fx=((FX_START, Decimal("8002")), (date(2015, 1, 2), Decimal("12500"))),
    )


# --------------------------------------------------------------------------- constants and D9


def test_constants():
    assert DEV_END == date(2015, 10, 16)
    assert dates.is_session(DEV_END) and dates.next_session(DEV_END) == date(2015, 10, 19)
    assert FX_START == date(1999, 1, 4)
    assert MAX_CANDIDATES == 60
    csv = Path(__file__).resolve().parents[1] / "data" / "sp500_history.csv"
    first_row = csv.read_text(encoding="utf-8").splitlines()[1]
    assert MEMBERSHIP_START == date.fromisoformat(first_row.split(",", 1)[0])
    assert FAILURE_LABELS == ("beats SPY TR", "max DD <= 15%", "PF >= 1.3", ">= 100 trades", "owner inputs")


def test_check_dev_session():
    check_dev_session(DEV_END)
    check_dev_session(date(1996, 1, 2))
    for late in (date(2015, 10, 17), date(2015, 10, 19), date(2026, 10, 2)):
        with pytest.raises(DevWindowError, match="after the dev window end"):
            check_dev_session(late)
    assert issubclass(DevWindowError, ValueError)
    with pytest.raises(TypeError):
        check_dev_session(datetime(2015, 10, 16))
    with pytest.raises(TypeError):
        check_dev_session("2015-10-16")


def test_entry_points_reject_a_bar_after_dev_end():
    market = short_market(extra_day=date(2015, 10, 19))
    c = cand("C-LATE", allocator=SPY_HOLD)
    with pytest.raises(DevWindowError, match="SPY has a bar on 2015-10-19"):
        candidate_window(market, c)
    with pytest.raises(DevWindowError, match="SPY has a bar on 2015-10-19"):
        run_candidate(market, {}, (), c)
    with pytest.raises(DevWindowError, match="SPY has a bar on 2015-10-19"):
        run_registry(market, {}, (), (c,))


def test_entry_points_reject_fx_after_dev_end():
    market = short_market(fx=FX_SHORT + ((date(2015, 10, 19), Decimal("13500")),))
    c = cand("C-FX", allocator=SPY_HOLD)
    for call in (lambda: candidate_window(market, c),
                 lambda: run_candidate(market, {}, (), c),
                 lambda: run_registry(market, {}, (), (c,))):
        with pytest.raises(DevWindowError, match="usd_idr row on 2015-10-19"):
            call()


def test_run_entry_points_reject_dividends_after_dev_end():
    market = short_market()
    c = cand("C-DIV", allocator=SPY_HOLD)
    late_map = {"AAA": {date(2015, 10, 20): Decimal("0.25")}}
    late_spy = (Dividend(date(2015, 12, 18), Decimal("1.2")),)
    with pytest.raises(DevWindowError, match="AAA has a dividend on 2015-10-20"):
        run_candidate(market, late_map, SPY_DIVS, c)
    with pytest.raises(DevWindowError, match="SPY has a dividend on 2015-12-18"):
        run_candidate(market, DIVS, late_spy, c)
    with pytest.raises(DevWindowError, match="AAA has a dividend"):
        run_registry(market, late_map, SPY_DIVS, (c,))
    with pytest.raises(DevWindowError, match="SPY has a dividend"):
        run_registry(market, DIVS, late_spy, (c,))


def test_rows_reject_an_end_after_dev_end():
    s = stats(metrics())
    with pytest.raises(DevWindowError):
        make_row(cand("C-ROW"), date(2015, 6, 8), date(2015, 10, 19), s, spy_tr=SPY_TR, spy_price=SPY_TR)
    good = make_row(cand("C-ROW"), date(2015, 6, 8), DEV_END, s, spy_tr=SPY_TR, spy_price=SPY_TR)
    with pytest.raises(DevWindowError):
        replace(good, end=date(2016, 1, 4))


def test_dev_does_not_import_research():
    tree = ast.parse(Path(dev_module.__file__).read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
            imported += [f"{node.module}.{a.name}" for a in node.names]
    assert not [m for m in imported if m.startswith("seer_engine.research")]


# --------------------------------------------------------------------------- candidates


def test_candidate_validation():
    base = cand("F1-OK-1")
    assert base.owner_inputs == ()
    for bad in ("f1-lower", "F1_UNDERSCORE", "-F1", "F1-", ""):
        with pytest.raises(ValueError):
            replace(base, id=bad)
    for bad in ("F0", "F12", "f1", "REFX", "C"):
        with pytest.raises(ValueError):
            replace(base, family=bad)
    replace(base, family="F11")
    replace(base, family="REF")
    with pytest.raises(TypeError):
        replace(base, rules=DESIGN_V0)  # an Allocator under the bracket rules
    with pytest.raises(TypeError):
        replace(base, allocator=DipPicks())  # a Strategy under book rules
    with pytest.raises(TypeError):
        replace(base, rules="monthly-hold")
    replace(base, rules=DESIGN_V0, allocator=DipPicks())
    with pytest.raises(ValueError):
        replace(base, rationale="two\nlines")
    with pytest.raises(ValueError):
        replace(base, rationale="   ")
    with pytest.raises(TypeError):
        replace(base, added=datetime(2026, 10, 3))
    with pytest.raises(ValueError):
        replace(base, owner_inputs=("leverage", "etf:SSO"))  # unsorted
    with pytest.raises(ValueError):
        replace(base, owner_inputs=("etf:SSO", "etf:SSO"))
    with pytest.raises(TypeError):
        replace(base, owner_inputs=["etf:SSO"])
    # Declared owner inputs are not checked against the computed ones here (registry test does).
    assert replace(base, owner_inputs=("fee",)).owner_inputs == ("fee",)


def test_candidate_owner_inputs():
    assert candidate_owner_inputs(cand("A-1", allocator=HoldOne("Q", "QQQ"))) == ()
    assert candidate_owner_inputs(cand("A-2", allocator=HoldOne("S", "SSO"))) == ("etf:SSO", "leverage")
    assert candidate_owner_inputs(cand("A-3", allocator=HoldOne("I", "IEF"))) == ("etf:IEF",)
    assert candidate_owner_inputs(cand("A-4", rules=DAILY_SWITCH_TBILL)) == ("etf:BIL",)
    assert candidate_owner_inputs(cand("A-5", allocator=HoldOne("B", "BIL"), rules=DAILY_SWITCH_TBILL)) == ("etf:BIL",)
    frac = replace(MONTHLY_HOLD, id="monthly-frac", fractional=True)
    assert candidate_owner_inputs(cand("A-6", allocator=HoldOne("L", "QLD"), rules=frac)) == (
        "etf:QLD", "fractional", "leverage")
    assert candidate_owner_inputs(cand("A-7", "REF", allocator=DipPicks(), rules=DESIGN_V0)) == ()
    with pytest.raises(TypeError):
        candidate_owner_inputs("A-1")


# --------------------------------------------------------------------------- windows


def test_window_waits_for_the_latest_launch():
    market = short_market()
    assert candidate_window(market, cand("W-SPY", allocator=HoldOne("S5", "SPY", lookback=5))) == (
        date(2015, 6, 8), DEV_END)  # SPY's 5th bar is 06-05
    # XLK launches 07-01; its 5th bar is 07-08 (07-03 is a holiday), so the window opens 07-09.
    assert candidate_window(market, cand("W-XLK", allocator=HoldOne("X5", "XLK", reads=("SPY",), lookback=5))) == (
        date(2015, 7, 9), DEV_END)
    # SPY is always part of the rule, even when the allocator does not read it.
    assert candidate_window(market, cand("W-AAA", allocator=HoldOne("A1", "AAA", lookback=1))) == (
        date(2015, 6, 2), DEV_END)
    # The idle instrument is not part of the rule: BIL is absent from this market.
    assert candidate_window(market, cand("W-IDLE", allocator=HoldOne("S5B", "SPY", lookback=5),
                                         rules=DAILY_SWITCH_TBILL)) == (date(2015, 6, 8), DEV_END)


def test_window_respects_the_membership_start():
    days = dates.sessions(date(1995, 12, 1), date(1996, 1, 31))
    market = Market(history={"SPY": hist("SPY", sawtooth(len(days), 60.0, 0.5, 0.3), days=days)},
                    membership=Membership(()), fx=())
    # SPY's 3rd bar is 1995-12-05.
    assert candidate_window(market, cand("M-NO", allocator=HoldOne("N3", "SPY", lookback=3))) == (
        date(1995, 12, 6), DEV_END)
    assert candidate_window(market, cand("M-YES", allocator=HoldOne("Y3", "SPY", lookback=3, members=True))) == (
        date(1996, 1, 3), DEV_END)
    assert candidate_window(market, cand("M-V0", "REF", allocator=DipPicks(), rules=DESIGN_V0)) == (
        date(1996, 1, 3), DEV_END)


def test_window_errors():
    market = short_market()
    with pytest.raises(ValueError, match="QQQ has 0 bars"):
        candidate_window(market, cand("E-MISSING", allocator=HoldOne("MQ", "QQQ")))
    # SPY (98 bars) is checked first and has enough; XLK (76 bars) does not.
    with pytest.raises(ValueError, match="XLK has 76 bars in the market, the candidate needs 80"):
        candidate_window(market, cand("E-SHORT", allocator=HoldOne("SX", "XLK", lookback=80)))
    # SPY's 98th bar is DEV_END itself: the window would open on 2015-10-19.
    with pytest.raises(DevWindowError, match="would start on 2015-10-19"):
        candidate_window(market, cand("E-LATE", allocator=HoldOne("LS", "SPY", lookback=len(W_DAYS))))
    with pytest.raises(ValueError, match="lookback must be an int >= 1"):
        candidate_window(market, cand("E-ZERO", allocator=HoldOne("Z", "SPY", lookback=0)))


# --------------------------------------------------------------------------- runs


def test_design_v0_candidate_runs_through_run_backtest():
    market = short_market()
    strategy = DipPicks()
    c = cand("REF-DIP-V0", "REF", allocator=strategy, rules=DESIGN_V0)
    result, row = run_candidate(market, DIVS, SPY_DIVS, c)
    assert isinstance(result, RunResult)
    assert (row.start, row.end) == (date(2015, 6, 4), DEV_END)  # AAA/SPY 3rd bar 06-03
    assert result == run_backtest(market, strategy, None, row.start, row.end)
    assert result.usd_idr == Decimal("12500")
    assert row.stats == run_stats(result)
    assert len(result.closed) > 0  # the fake strategy really trades


def test_book_candidate_and_spy_curves():
    market = short_market()
    c = cand("F1-FLIP-D", allocator=HoldOne("FLIP", "SPY", flip=True), rules=DAILY_SWITCH)
    result, row = run_candidate(market, DIVS, SPY_DIVS, c)
    assert isinstance(result, BookResult)
    assert (row.start, row.end) == (date(2015, 6, 8), DEV_END)
    assert result.usd_idr == Decimal("12500")
    assert result.initial_cash == initial_cash_usd(INITIAL_IDR, Decimal("12500"))
    assert row.stats == run_stats(result)
    assert row.stats.metrics.trades > 0
    price, total = spy_curves(market.spy(), row.start, row.end, result.initial_cash, SPY_DIVS)
    assert row.spy_price == curve_metrics(price)
    assert row.spy_tr == curve_metrics(total)
    assert row.spy_tr.total_return > row.spy_price.total_return  # the 09-18 dividend is credited
    assert row == make_row(c, row.start, row.end, row.stats, spy_tr=row.spy_tr, spy_price=row.spy_price)
    assert row.candidate is c


def test_window_before_fx_start_converts_at_the_fx_start_rate():
    market = long_market()
    cash = initial_cash_usd(INITIAL_IDR, Decimal("8002"))
    book, book_row = run_candidate(market, {}, (), cand("F1-LONG", allocator=HoldOne("LONG", "SPY", lookback=1)))
    assert book_row.start == date(1998, 11, 3)
    assert isinstance(book, BookResult)
    assert (book.usd_idr, book.initial_cash) == (Decimal("8002"), cash)
    strategy = DipPicks()
    v0, v0_row = run_candidate(market, {}, (), cand("REF-LONG-V0", "REF", allocator=strategy, rules=DESIGN_V0))
    assert v0_row.start == date(1998, 11, 5)  # SPY's 3rd bar is 1998-11-04
    assert isinstance(v0, RunResult)
    assert (v0.usd_idr, v0.initial_cash) == (Decimal("8002"), cash)
    expected = run_backtest(
        Market(history=market.history, membership=market.membership, fx=((v0_row.start, Decimal("8002")),)),
        strategy, None, v0_row.start, DEV_END,
    )
    assert v0 == expected
    price, _ = spy_curves(market.spy(), v0_row.start, DEV_END, cash, ())
    assert v0_row.spy_price == curve_metrics(price)


# --------------------------------------------------------------------------- D8 rows


def metrics(*, total_return: float | None = 0.5, dd: float | None = 0.10, pf: float | None = 1.5,
            trades: int = 150, cagr: float | None = 0.08) -> Metrics:
    return Metrics(total_return=total_return, win_rate=0.5, profit_factor=pf, max_drawdown=dd,
                   trades=trades, months=230.0, cagr=cagr)


def stats(m: Metrics) -> RunStats:
    return RunStats(metrics=m, exposure=0.6, turnover=2.0, costs_usd=10.0, gross_pnl_usd=100.0,
                    cost_drag=0.1, dividends_usd=0.0, sharpe=0.8, daily_returns=(0.01, -0.005),
                    year_returns=((2010, 0.1),), worst_year=(2010, 0.1))


SPY_TR = Metrics(total_return=0.4, win_rate=None, profit_factor=None, max_drawdown=0.5, trades=0,
                 months=230.0, cagr=0.06)


def row(id: str, family: str = "F1", *, allocator: Any = None, **kw: Any) -> DevRow:
    return make_row(cand(id, family, allocator=allocator), date(2001, 1, 2), DEV_END, stats(metrics(**kw)),
                    spy_tr=SPY_TR, spy_price=SPY_TR)


@pytest.mark.parametrize("kw, failed", [
    (dict(), ()),
    (dict(dd=0.15), ()),
    (dict(dd=0.1500001), ("max DD <= 15%",)),
    (dict(dd=None), ("max DD <= 15%",)),
    (dict(pf=1.3), ()),
    (dict(pf=1.2999), ("PF >= 1.3",)),
    (dict(pf=math.inf), ()),
    (dict(pf=None), ("PF >= 1.3",)),
    (dict(trades=100), ()),
    (dict(trades=99), (">= 100 trades",)),
    (dict(total_return=0.4), ("beats SPY TR",)),  # equal is not beating
    (dict(total_return=0.4000001), ()),
    (dict(total_return=None), ("beats SPY TR",)),
    (dict(dd=0.2, trades=10), ("max DD <= 15%", ">= 100 trades")),
])
def test_eligibility_boundaries(kw, failed):
    r = row("B-1", **kw)
    assert r.failed == failed
    assert r.eligible is (failed == ())
    assert r.beats_spy is ("beats SPY TR" not in failed)


def test_every_failure_in_order():
    r = row("B-ALL", allocator=HoldOne("SSOH", "SSO"), total_return=0.3, dd=0.3, pf=1.0, trades=5)
    assert r.failed == FAILURE_LABELS
    assert r.eligible is False and r.beats_spy is False
    only_owner = row("B-OWN", allocator=HoldOne("IEFH", "IEF"))
    assert only_owner.failed == ("owner inputs",)
    # D8 reads the computed owner inputs, not the declared ones.
    lying = make_row(cand("B-LIE", allocator=HoldOne("SSOL", "SSO"), owner_inputs=()), date(2001, 1, 2), DEV_END,
                     stats(metrics()), spy_tr=SPY_TR, spy_price=SPY_TR)
    assert lying.failed == ("owner inputs",)


def test_thresholds_come_from_tuning(monkeypatch):
    assert row("T-1").eligible
    monkeypatch.setattr(tuning, "MAX_DRAWDOWN", 0.05)
    assert row("T-1").failed == ("max DD <= 15%",)
    monkeypatch.setattr(tuning, "MAX_DRAWDOWN", 0.15)
    monkeypatch.setattr(tuning, "MIN_PROFIT_FACTOR", 2.0)
    assert row("T-1").failed == ("PF >= 1.3",)


def test_mar():
    assert row("R-1", cagr=0.12, dd=0.10).mar == 0.12 / 0.10
    assert row("R-2", cagr=-0.03, dd=0.10).mar == -0.03 / 0.10
    assert row("R-3", dd=0.0).mar is None
    assert row("R-4", cagr=None).mar is None
    assert row("R-5", dd=None).mar is None


def test_dev_row_consistency():
    good = row("K-1")
    with pytest.raises(ValueError):
        replace(good, eligible=False)
    with pytest.raises(ValueError):
        replace(good, failed=(">= 100 trades", "PF >= 1.3"), eligible=False)  # out of order
    with pytest.raises(ValueError):
        replace(good, failed=("made up",), eligible=False)
    with pytest.raises(ValueError):
        replace(good, beats_spy=False)
    with pytest.raises(ValueError):
        replace(good, start=date(2016, 1, 4), end=DEV_END)
    with pytest.raises(TypeError):
        replace(good, mar=1)


# --------------------------------------------------------------------------- finalists


def test_finalists_d8():
    rows = [
        row("F5-X", "F5", cagr=0.05, dd=0.10),  # MAR 0.5: fourth family, cut by the cap of 3
        row("F1-B", "F1", cagr=0.12, dd=0.10),  # MAR 1.2, tied with F1-A, loses on id
        row("F4-X", "F4", cagr=0.30, dd=0.20),  # MAR 1.5 but DD > 15%: not eligible
        row("F3-X", "F3", cagr=0.09, dd=0.10),  # MAR 0.9
        row("F1-A", "F1", cagr=0.12, dd=0.10),  # MAR 1.2
        row("F2-X", "F2", cagr=0.10, dd=0.10),  # MAR 1.0
    ]
    assert [r.candidate.id for r in finalists(rows)] == ["F1-A", "F2-X", "F3-X"]
    assert finalists(rows) == finalists(list(reversed(rows)))
    # One per family: with only F1 rows eligible, one finalist.
    assert [r.candidate.id for r in finalists([rows[1], rows[4]])] == ["F1-A"]


def test_finalists_none_eligible():
    assert finalists([]) == ()
    assert finalists([row("N-1", trades=10), row("N-2", "F2", pf=1.0)]) == ()
    with pytest.raises(TypeError):
        finalists(["F1-A"])


def test_finalists_rank_rows_without_mar_last():
    flat = row("Z-FLAT", "F6", dd=0.0)
    assert flat.eligible and flat.mar is None
    ranked = finalists([flat, row("Z-LOW", "F2", cagr=0.01, dd=0.10)])
    assert [r.candidate.id for r in ranked] == ["Z-LOW", "Z-FLAT"]


# --------------------------------------------------------------------------- deflated Sharpe


def test_deflated_sharpe_hand_case():
    # SR = 0.1, N = 10, V = 0.001, T = 1000, skew 0, kurtosis 3:
    #   Φ⁻¹(0.9) = 1.2815516, Φ⁻¹(1 − 1/(10e)) = 1.7892418
    #   SR* = sqrt(0.001) × (0.4227843 × 1.2815516 + 0.5772157 × 1.7892418) = 0.0497932
    #   z = (0.1 − 0.0497932) × sqrt(999) / sqrt(1 + 0.5 × 0.01) = 1.5829329
    #   DSR = Φ(1.5829329) = 0.9432816
    assert deflated_sharpe(0.1, 10, 0.001, 1000, 0.0, 3.0) == pytest.approx(0.9432816, abs=1e-7)


def test_deflated_sharpe_second_case():
    # SR 0.05, N 54, V 0.0004, T 5000, skew −0.5, kurtosis 8: SR* = 0.0461129,
    # z = 0.0038871 × sqrt(4999) / sqrt(1 + 0.025 + 1.75 × 0.0025) = 0.2708825, DSR = 0.6067593.
    assert deflated_sharpe(0.05, 54, 0.0004, 5000, -0.5, 8.0) == pytest.approx(0.6067593, abs=1e-7)


def test_deflated_sharpe_at_the_threshold_is_one_half():
    assert deflated_sharpe(0.0, 20, 0.0, 300, 0.0, 3.0) == 0.5


@pytest.mark.parametrize("args", [
    (0.1, 1, 0.001, 1000, 0.0, 3.0),  # one trial: Φ⁻¹(0) undefined
    (0.1, 10, 0.001, 1, 0.0, 3.0),  # t < 2
    (0.1, 10, -0.001, 1000, 0.0, 3.0),  # negative variance
    (math.nan, 10, 0.001, 1000, 0.0, 3.0),
    (0.1, 10, 0.001, 1000, math.inf, 3.0),
    (0.1, 10, 0.001, 1000, 20.0, 3.0),  # 1 − 20 × 0.1 + 0.005 < 0
])
def test_deflated_sharpe_undefined(args):
    assert deflated_sharpe(*args) is None


def test_deflated_sharpe_types():
    with pytest.raises(TypeError):
        deflated_sharpe(0.1, 10.0, 0.001, 1000, 0.0, 3.0)
    with pytest.raises(TypeError):
        deflated_sharpe(0.1, 10, 0.001, True, 0.0, 3.0)
    with pytest.raises(TypeError):
        deflated_sharpe("0.1", 10, 0.001, 1000, 0.0, 3.0)
    assert deflated_sharpe(1, 10, 0, 1000, 0, 3) is not None  # ints are numbers


# --------------------------------------------------------------------------- run_registry


def short_registry() -> tuple[tuple[Candidate, ...], HoldOne, HoldOne, DipPicks]:
    flip = HoldOne("FLIP", "SPY", flip=True)
    xlk = HoldOne("XLKH", "XLK", reads=("SPY",))
    strategy = DipPicks()
    registry = (
        cand("C-ONE", "F1", allocator=flip, rules=DAILY_SWITCH),
        cand("C-TWO", "REF", allocator=strategy, rules=DESIGN_V0),
        cand("C-THREE", "F2", allocator=xlk, rules=MONTHLY_HOLD),
        cand("C-FOUR", "F1", allocator=flip, rules=MONTHLY_HOLD),
    )
    return registry, flip, xlk, strategy


def test_registry_runs_in_order_and_repeats_equal():
    market = short_market()
    registry, _, _, _ = short_registry()
    seen: list[tuple[int, str, str]] = []
    rows = run_registry(market, DIVS, SPY_DIVS, registry,
                        on_result=lambda i, result, r: seen.append((i, type(result).__name__, r.candidate.id)))
    assert [r.candidate.id for r in rows] == ["C-ONE", "C-TWO", "C-THREE", "C-FOUR"]
    assert seen == [(0, "BookResult", "C-ONE"), (1, "RunResult", "C-TWO"),
                    (2, "BookResult", "C-THREE"), (3, "BookResult", "C-FOUR")]
    assert [(r.start, r.end) for r in rows] == [
        (date(2015, 6, 8), DEV_END), (date(2015, 6, 4), DEV_END), (date(2015, 7, 9), DEV_END), (date(2015, 6, 8), DEV_END),
    ]
    assert run_registry(market, DIVS, SPY_DIVS, registry) == rows
    assert run_registry(market, DIVS, SPY_DIVS, ()) == ()


def test_registry_prepares_once_per_allocator_id_per_call():
    market = short_market()
    registry, flip, xlk, strategy = short_registry()
    run_registry(market, DIVS, SPY_DIVS, registry)
    assert (flip.prepare_calls, xlk.prepare_calls, strategy.prepare_calls) == (1, 1, 1)
    assert len(flip.prepared_seen) > 0 and len(set(flip.prepared_seen)) == 1  # C-ONE and C-FOUR share it
    run_registry(market, DIVS, SPY_DIVS, registry)
    assert (flip.prepare_calls, xlk.prepare_calls, strategy.prepare_calls) == (2, 2, 2)


def test_registry_refuses_shared_ids_duplicates_and_oversize():
    market = short_market()
    twin_a, twin_b = HoldOne("TWIN", "SPY"), HoldOne("TWIN", "XLK", reads=("SPY",))
    with pytest.raises(ValueError, match="share the id 'TWIN'"):
        run_registry(market, DIVS, SPY_DIVS, (cand("D-A", allocator=twin_a), cand("D-B", allocator=twin_b)))
    assert twin_a.prepare_calls == twin_b.prepare_calls == 0  # refused before anything ran
    with pytest.raises(ValueError, match="appears twice"):
        run_registry(market, DIVS, SPY_DIVS, (cand("D-SAME", allocator=twin_a), cand("D-SAME", allocator=twin_a)))
    big = tuple(cand(f"D-{i}", allocator=twin_a) for i in range(MAX_CANDIDATES + 1))
    with pytest.raises(ValueError, match="the cap is 60"):
        run_registry(market, DIVS, SPY_DIVS, big)
    with pytest.raises(TypeError):
        run_registry(market, DIVS, SPY_DIVS, ("C-ONE",))


def test_registry_rows_equal_unprepared_single_runs():
    market = short_market()
    registry, _, _, _ = short_registry()
    rows = run_registry(market, DIVS, SPY_DIVS, registry)
    assert rows == tuple(run_candidate(market, DIVS, SPY_DIVS, c)[1] for c in registry)
```
**Impact:** this adds 50 tests. The suite's collected count goes up by 50 over whatever phases
1–8 leave it at. The phase log records the exact number. The tests run in about 5–10 s, and
most of that is the two 4,267-session runs in
`test_window_before_fx_start_converts_at_the_fx_start_rate`.

Notes for the implementer on the tests:
- `test_eligibility_boundaries` has 14 cases and `test_deflated_sharpe_undefined` has 6.
  Count the collected tests after writing the file. If the count is not 50, recount the
  parametrize lists, then log the true number. Do not pad or trim the tests to hit 50.
- `test_design_v0_candidate_runs_through_run_backtest` asserts `len(result.closed) > 0`.
  AAA's sawtooth (+1.0/−0.9) puts the next day's low (`close − 0.5`) under a limit that sits
  1% below the previous close often enough. If phase 3's real run shows zero closed trades
  here, the fake is too tame: widen `hist(..., spread=...)` for AAA. Do not drop the assertion.
- `test_book_candidate_and_spy_curves` asserts `trades > 0`. Under `DAILY_SWITCH`, `flip=True`
  alternates in and out every session, and each exit is a signal sell at the next open.
- Equality between `RunStats` values (`row.stats == run_stats(result)`, `rows == rows`) relies
  on phase 3's `RunStats` being a frozen dataclass of floats and tuples, as the contract
  states, with no NaN.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/trade-rules-dev-search && engine/.venv/bin/python -c "import seer_engine.backtest.dev as d; print(d.DEV_END, d.MAX_CANDIDATES)"`
**Tests:**
- `cd /home/miftah/.worktrees/seer/trade-rules-dev-search && docker start seer-pg && PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests/test_backtest_dev.py engine/tests/test_strategy_purity.py -q`
- then the full suite: `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`
  (0 skipped).
- Use the **worktree's** `engine/.venv`, never `/home/miftah/seer/engine/.venv`.

**Manual check:**
- `git diff --stat 2546a92 -- engine/src/seer_engine/sim/model.py engine/src/seer_engine/sim/lifecycle.py engine/src/seer_engine/sim/sizing.py engine/src/seer_engine/sim/split_adjust.py engine/src/seer_engine/backtest/runner.py engine/src/seer_engine/backtest/market.py engine/src/seer_engine/backtest/benchmark.py engine/src/seer_engine/backtest/metrics.py engine/src/seer_engine/backtest/tuning.py engine/src/seer_engine/strategies/base.py`
  prints nothing.
- `git status` shows only the two new files from this phase.

**Exit criteria:**
- `tests/test_backtest_dev.py` passes: 50 tests, with the count recorded in the phase log.
- `test_strategy_purity.py` passes, now covering `seer_engine.backtest.dev`.
- The full suite is green with 0 skipped.
- `DevWindowError` is proven from `check_dev_session`, `candidate_window`, `run_candidate`,
  `run_registry`, `make_row` and `DevRow`.
- No existing file is modified.

## Handoffs

- **Phase 12 (owns the `research` ↔ `dev` equality, plan index D-I):**
  `tests/test_backtest_dev_command.py` asserts `research.DEV_END`, `MEMBERSHIP_START` and
  `FX_START` equal `dev`'s. Phase 9 does not depend on phase 4, so it cannot pin that equality
  (R4).
- **Phase 12:**
  - Use `run_registry(..., on_result=...)` to time each candidate (the clock lives in the
    command) and to keep each result's snapshots for `DevReport.curves`.
  - Every market and dividend map handed to `dev` must hold nothing after `DEV_END`, and
    that includes the command tests' synthetic markets.
  - The ≤ 60 cap is enforced at run time here, and phase 11's test enforces it at
    registry-definition time (R6/R8).
- **Phase 10:**
  - `deflated_sharpe` expects the **daily** Sharpe (`RunStats.sharpe / sqrt(252)`),
    `var_trials` over the trials' daily Sharpes, `t = len(daily_returns)`, and the
    **non-excess** kurtosis. Phase 10 computes skew and kurtosis from
    `RunStats.daily_returns`.
  - `FAILURE_LABELS` gives the fixed column wording.
  - `make_row` builds synthetic rows for its tests (R6, R7).
- **Phase 11:**
  - `Candidate` does not check the declared `owner_inputs` against the computed ones. Phase
    11's `test_declared_owner_inputs_match_the_computed_ones` stays the only check of that
    equality (R5).
  - `Candidate` rejects an Allocator under `DESIGN_V0`, a Strategy under book rules, a family
    outside F1..F11/REF, and an id outside `[A-Z0-9]+(-[A-Z0-9]+)*`. The registry table
    satisfies all four.
- **Phase 2 — settled, plan index D-D:** `BlendAllocator.prepare`, `VolTargetAllocator.prepare`
  and `PicksAllocator.prepare` return a param-independent `LazyPrepared(history)` (inner
  prepares keyed by object identity), and every family's `prepare(history)` is
  param-independent too, so one prepared value per allocator id is correct for every candidate.
  Phase 12 runs the registry through `run_registry(..., on_result=...)`, so this is the one
  keying rule in the plan set.

## Rollback

Delete `engine/src/seer_engine/backtest/dev.py` and `engine/tests/test_backtest_dev.py`, or
`git revert` the phase's commit. No other file is touched. Phases 10–12 import `dev`, so they
must be reverted first if they have landed.
