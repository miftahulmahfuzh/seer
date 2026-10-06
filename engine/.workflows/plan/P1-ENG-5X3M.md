> Adopted from `BUILD_PROMOTION_PATH_PLAN.md` phase 1. Source: `.workflows/plan/build-promotion-path/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: Make the backtest window a parameter, keeping D9 absolute

**Plan set:** `BUILD_PROMOTION_PATH_PLAN.md`
**Analysis:** `20261006-115723-B7K2_code_analyzer.md`
**Satisfies:** R1 (a test-window research store — this phase supplies the window object and the
generalized universe/membership helpers it is built from), R2 (`lab test` — this phase supplies
the `window=` parameter on `run_registry`/`run_candidate` that lets a run reach the test window)
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/backtest` (+ `engine/src/seer_engine/research.py`)

---

## Goal

After this phase a window is a value — `backtest.window.Window(name, start, end)` — instead of a
module constant. `backtest/dev.py` and the five window-bearing helpers in `research.py` take a
`window=` argument that **defaults to the dev window**, so every existing caller compiles and
behaves byte-identically, while a caller that passes a `test` window explicitly can run past
`DEV_END`. `DEV_END` keeps the literal value `date(2015, 10, 16)` in both modules, every test
that pins it passes unedited, and `research_membership`'s clamp becomes "clamp against *this*
window's end" so phase 2 can build a correct test-window store.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Creates:**

- module `seer_engine.backtest.window` (`engine/src/seer_engine/backtest/window.py`, new file)
- `backtest.window.Window` — frozen dataclass, fields in this order:
  `name: str` (`"dev"` or `"test"`), `start: date` (first session covered; `date.min` means
  *no lower bound*), `end: date` (hard bound — nothing dated after it may be read)
- `backtest.window.WINDOW_NAMES: tuple[str, ...] = ("dev", "test")`
- `Window.covers(self, d: date) -> bool`
- `Window.following(self, name: str, end: date) -> Window` — the window opening on
  `dates.next_session(self.end)`; `DEV_WINDOW.following("test", last_session)` is the P7b test
  window and its `.start` is `date(2015, 10, 19)`
- `backtest.dev.DEV_WINDOW = Window(name="dev", start=date.min, end=DEV_END)`
- `research.DEV_WINDOW = Window(name="dev", start=date.min, end=DEV_END)` — a duplicate of the
  above built from `research.DEV_END`, exactly as the two `DEV_END`s are duplicates; pinned
  equal by a new test
- `research.unserved_reason(start: date = STORE_START, end: date = DEV_END) -> str`
- test file `engine/tests/test_backtest_window.py`

**Signature changes** (every new parameter is keyword-only with a default, so no existing call
site changes):

| Before | After |
|---|---|
| `dev.check_dev_session(d)` | `dev.check_dev_session(d, window: Window = DEV_WINDOW)` |
| `dev._check_market(market)` | `dev._check_market(market, window: Window = DEV_WINDOW)` |
| `dev._check_dividends(dividends, spy_dividends)` | `dev._check_dividends(dividends, spy_dividends, window: Window = DEV_WINDOW)` |
| `dev.candidate_window(market, c)` | `dev.candidate_window(market, c, *, window: Window = DEV_WINDOW)` |
| `dev.make_row(candidate, start, end, stats, *, spy_tr, spy_price)` | `dev.make_row(candidate, start, end, stats, *, spy_tr, spy_price, window: Window = DEV_WINDOW)` |
| `dev._run(market, spy, dividends, spy_dividends, c, prepared)` | `dev._run(market, spy, dividends, spy_dividends, c, prepared, window)` (positional, private) |
| `dev.run_candidate(market, dividends, spy_dividends, c, *, prepared=None)` | `dev.run_candidate(market, dividends, spy_dividends, c, *, prepared=None, window: Window = DEV_WINDOW)` |
| `dev.run_registry(market, dividends, spy_dividends, registry, *, on_result=None)` | `dev.run_registry(market, dividends, spy_dividends, registry, *, on_result=None, window: Window = DEV_WINDOW)` |
| `research._overlaps_window(iv)` | `research._overlaps_window(iv, window: Window = DEV_WINDOW)` |
| `research.requested_symbols(data_dir=None)` | `research.requested_symbols(data_dir=None, *, window: Window = DEV_WINDOW)` |
| `research.research_membership(data_dir=None)` | `research.research_membership(data_dir=None, *, window: Window = DEV_WINDOW)` |
| `research.unserved_by_year(members, unserved)` | `research.unserved_by_year(members, unserved, *, window: Window = DEV_WINDOW)` |

**Field added:** `dev.DevRow.window: Window = DEV_WINDOW` — appended last, defaulted, so every
existing keyword construction and `dataclasses.replace` keeps working and two default-window
rows still compare equal. `row.window.name` is the string phase 4 writes into
`store.TrialRow.window`.

**Deletes:** nothing.
**Renames:** nothing. `DEV_END`, `MEMBERSHIP_START`, `FX_START`, `STORE_START`, `STORE_DIR`,
`UNSERVED_REASON`, `DevWindowError`, `check_dev_session` all keep their names and values.
`UNSERVED_REASON` keeps its exact current string.

**Requires (from earlier phases):** none.

**Leaves alone (owned by others):**

- `research.build_store`, `research.load_store`, `research._clip`, `research._manifest`,
  `ResearchData`, `MANIFEST_KEYS`, the `.tmp`/swap logic — **phase 2**. They keep compiling
  untouched because every new parameter is defaulted.
- `engine/src/seer_engine/commands/research_store.py` — **phase 2** (its
  `research.unserved_by_year(...)` call at `:261` keeps working on the default).
- `engine/src/seer_engine/lab/**` and `engine/src/seer_engine/commands/lab.py` — **phases 3, 4**.
- `engine/src/seer_engine/backtest/dev_report.py` — unchanged and still dev-only (see Handoffs).
- `.gitignore`, `docs/lab/prereg/` — phases 2, 3.

**Shared files, resolved by the reconciler (2026-10-06):** `engine/tests/test_research_store.py` —
this phase *appends* one new section and adds one import line; it edits no existing test function.
**Phase 2 does not touch this file at all** — it puts every addition of its own in the new
`engine/tests/test_research_test_store.py`. So this phase is the sole editor and there is no
sequencing to respect.

**Decided by the reconciler, and this phase's code is the winning side:** the membership lower
bound is `_members_start(window) = max(window.start, MEMBERSHIP_START)`, so the test window's
universe and `unserved_by_year` range are the **test window's own** (`2015-10-19..end`), not
`MEMBERSHIP_START..end`. Phase 2's draft asserted the opposite in prose and in two tests; phase 2
has been edited to match this phase. The dev results are byte-identical either way
(`DEV_WINDOW.start` is `date.min`). See the index's Decisions table, row "the test store's
universe".

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/backtest/window.py` | create | the `Window` value object, `WINDOW_NAMES`, `covers`, `following` |
| `engine/src/seer_engine/backtest/dev.py` | modify | module docstring D9 paragraph (`:7`–`:12`); `DEV_WINDOW` after `:55`; `DevWindowError` docstring `:73`; `check_dev_session` `:83`; `_check_market` `:90`; `_check_dividends` `:102`; `candidate_window` `:215`; `DevRow` `:251`; `make_row` `:302`; `_run` `:353`; `run_candidate` `:392`; `run_registry` `:413` |
| `engine/src/seer_engine/research.py` | modify | import `Window` (`:57` block); `DEV_WINDOW` after `:67`; `unserved_reason` + `UNSERVED_REASON` `:98`; `_overlaps_window` `:156`; `requested_symbols` `:160`; `research_membership` `:166`; `unserved_by_year` `:183` |
| `engine/tests/test_backtest_window.py` | create | `Window` unit tests and the two-`DEV_WINDOW` equality pin |
| `engine/tests/test_backtest_dev.py` | modify | two import lines (`:35`, `:51`); append a "test window" section at the end of the file |
| `engine/tests/test_research_store.py` | modify | one import line (`:19` block); append a "window parameter" section at the end of the file |

---

## Implementation Steps

### Step 1: The `Window` value object

**File:** `engine/src/seer_engine/backtest/window.py` (new)
**Change:** A new pure module holding one frozen dataclass and nothing else. It lives under
`backtest/` because `backtest/dev.py` is its primary user and `research.py` already imports
three other `backtest.*` modules; it deliberately holds **no date constant**, so no third copy
of `DEV_END` comes into existence.

`tests/test_strategy_purity.py` globs `seer_engine/backtest/*.py`, so this file is covered by
the purity test the moment it lands: no clock, no `logging`, no `time`, no `random`, no
`print`/`open`, and a fresh-interpreter import that pulls no psycopg/requests/yfinance.
`seer_engine.dates` is allowed — `backtest/dev.py` already imports it.

**Code:**

```python
"""The window a backtest or a research store is bound to (method lab design §3).

One frozen value object and nothing else. The dev window is a module constant in each of the
two modules that own a ``DEV_END`` -- ``backtest.dev.DEV_WINDOW`` and ``research.DEV_WINDOW``,
duplicates pinned equal by ``tests/test_backtest_window.py``, exactly as the two ``DEV_END``
constants are duplicates pinned equal by ``tests/test_fundamentals_coverage.py``. This module
holds no date of its own, so no third copy of ``DEV_END`` exists.

The test window has no constant: its end is whichever session the test store was built to, so
it is made from the dev window with :meth:`Window.following` once that session is known.

``start`` is the first session the window covers, and ``date.min`` means *no lower bound* --
that is the dev window, whose backtests open as early as the data allows (SPY's first session,
1993-01-29) and whose membership lower bound belongs to the vendored CSVs
(``MEMBERSHIP_START``), not to the window. ``end`` is the hard bound: nothing dated after it
may be read. For the dev window that is D9, the guard that keeps the test window unreachable
by accident; for the test window it is the store's own edge.

Pure (``tests/test_strategy_purity.py`` globs ``backtest/*.py``): no clock, no files, no
randomness. ``seer_engine.dates`` is the NYSE calendar, which ``backtest.dev`` already uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from seer_engine import dates

WINDOW_NAMES: tuple[str, ...] = ("dev", "test")
"""The two windows a trial can run on; ``lab.store.WINDOWS`` is the same pair."""


def _as_date(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    return d


@dataclass(frozen=True)
class Window:
    """A named session range: ``name`` ("dev" or "test"), its first session and its last.

    Compared by value, so the dev window built in ``backtest.dev`` and the one built in
    ``research`` are the same window and either may be passed to either module.

    ``start`` is ``date.min`` for the dev window: it has no lower bound, and a candidate's
    window opens wherever its lookback is satisfied (1993 for a long-lookback SPY candidate,
    which is before ``MEMBERSHIP_START``). For the test window ``start`` is a real session and
    is a floor: ``dev.candidate_window`` never opens a candidate before it.
    """

    name: str
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.name not in WINDOW_NAMES:
            raise ValueError(f"window name must be one of {WINDOW_NAMES}, got {self.name!r}")
        _as_date("start", self.start)
        _as_date("end", self.end)
        if self.start > self.end:
            raise ValueError(f"the {self.name} window starts on {self.start}, after its end {self.end}")

    def covers(self, d: date) -> bool:
        """``start <= d <= end``; ``TypeError`` for a non-date (a ``datetime`` included)."""
        return self.start <= _as_date("session", d) <= self.end

    def following(self, name: str, end: date) -> Window:
        """The window opening on the first session after this one and ending on ``end``.

        ``DEV_WINDOW.following("test", last_session)`` is the P7b test window: it starts on
        2015-10-19, the session after ``DEV_END``, and ends wherever the test store's data
        ends (method lab design §3: "2015-10-19 → data end"). ``ValueError`` when ``end``
        falls before that first session.
        """
        start = dates.next_session(self.end)
        if _as_date("end", end) < start:
            raise ValueError(
                f"a {name} window following the {self.name} window ends on or after {start}, got {end}"
            )
        return Window(name=name, start=start, end=end)
```

**Impact:** a new importable module. Nothing imports it yet.

---

### Step 2: `backtest/dev.py` — the module docstring and `DEV_WINDOW`

**File:** `engine/src/seer_engine/backtest/dev.py:7`–`:12` (docstring bullet) and `:42`–`:55`
(imports and constants)
**Change:** The docstring's D9 bullet currently ends "Nothing takes an ``end``: every candidate
runs to ``DEV_END``", which stops being true. Replace that bullet, add the import, and define
`DEV_WINDOW` immediately after the three date constants. `DEV_END` itself is **not touched**.

**Code** — replace the bullet at `:7`–`:12`:

```python
- **D9, the code-level guard.** ``DEV_END`` is 2015-10-16 and ``DEV_WINDOW`` is the window
  every entry point here defaults to. Every public entry point that is handed a date, a market
  or dividends raises ``DevWindowError`` (a ``ValueError``) when any of them is dated after
  that window's end: ``check_dev_session``, ``candidate_window``, ``run_candidate``,
  ``run_registry``, ``make_row`` and ``DevRow`` itself. A caller that passes nothing gets the
  dev window, so the refusal is absolute by default. The ``window=`` argument is the only way
  to reach the P7b test window (method lab design §3), and only ``lab test`` passes one.
  Nothing takes a bare ``end``: every candidate runs to its window's end.
```

**Code** — add the import to the `seer_engine` import block (after `:47`,
`from seer_engine.backtest.metrics import ...`, keeping alphabetical order within the block):

```python
from seer_engine.backtest.runner import RunResult
from seer_engine.backtest.window import Window
```

**Code** — replace `:53`–`:56` (the constants block) with:

```python
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
```

**Impact:** `DEV_END`'s line is byte-identical. `dev.DEV_WINDOW` becomes importable. Nothing
else changes yet.

---

### Step 3: `backtest/dev.py` — the four guards take a window

**File:** `engine/src/seer_engine/backtest/dev.py:73`–`:121`
**Change:** `DevWindowError`'s docstring, then `check_dev_session`, `_check_market` and
`_check_dividends` each gain `window: Window = DEV_WINDOW` and interpolate `window.name` /
`window.end` into the message. For `DEV_WINDOW` the rendered text is **character-for-character
what it is today** (`name="dev"`, `end=2015-10-16`), so every existing `pytest.raises(match=...)`
keeps matching.

**Code** — replace `:73`–`:121` (from `class DevWindowError` through the end of
`_check_dividends`):

```python
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
```

**Impact:** `backtest/dev_report.py:168` and `:202` call `check_dev_session(x)` with no window —
they keep the dev guard. Every message a dev path can emit is unchanged, so
`tests/test_backtest_dev.py:207`–`:253` passes untouched.

---

### Step 4: `candidate_window` takes a window and floors on `window.start`

**File:** `engine/src/seer_engine/backtest/dev.py:215`–`:244`
**Change:** The returned end becomes `window.end`; the computed start is floored at
`window.start`. **The floor is provably dead code on the dev window** — `DEV_WINDOW.start` is
`date.min`, so `start < window.start` is never true and `dates.is_session` is never called with
it. That is what keeps dev candidate windows, and therefore the `start`/`end` of every recorded
dev trial, byte-identical. For a test window the floor is what stops a candidate whose lookback
is satisfied in 1993 from opening its "test" run in 1993.

**Code** — replace the whole function:

```python
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
```

**Impact:** dev callers get the same two dates and the same message
(`"E-LATE: its dev window would start on 2015-10-19, after the dev window end 2015-10-16 (D9)"`),
so `tests/test_backtest_dev.py:333`–`:370` and `tests/test_registry.py:448` pass untouched.

---

### Step 5: `DevRow` carries its window; `make_row` passes it

**File:** `engine/src/seer_engine/backtest/dev.py:251`–`:300` (`DevRow`) and `:302`–`:351`
(`make_row`)
**Change:** `DevRow` gains a trailing, defaulted `window` field and validates against it instead
of against `DEV_END`. Without this the test window is unreachable no matter what the guards do:
`DevRow.__post_init__` currently calls `check_dev_session(self.end)` and would refuse every row
`run_registry` produces on the test window. The field is appended with a default, so every
existing construction (all keyword, `tests/test_backtest_dev_report.py:192`) and every
`dataclasses.replace` keeps working, and two default-window rows still compare equal — which is
what `tests/test_backtest_dev_command.py:427` relies on.

The three validations run in this order so that an existing failure keeps its existing message:
`check_dev_session(end, window)` first, then `start > end`, then the window floor.

**Code** — replace the dataclass body's docstring and `__post_init__`, leaving every other
field exactly where it is:

```python
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
```

**Code** — replace `make_row` (`:302`–`:351`):

```python
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
```

**Impact:** `repr(DevRow)` gains a `window=Window(name='dev', ...)` tail. Nothing serializes a
`DevRow` by `dataclasses.fields` — `dev_report`'s `fields()` calls are on `c.rules` and on
params (`dev_report.py:232`, `:289`, `:1090`), and `lab/runner.py` reads named attributes — so
no report column and no database column changes.

---

### Step 6: `_run`, `run_candidate` and `run_registry` thread the window

**File:** `engine/src/seer_engine/backtest/dev.py:353`–`:390` (`_run`), `:392`–`:411`
(`run_candidate`), `:413`–`:462` (`run_registry`)
**Change:** `_run` takes the window as a trailing positional (it is private and always called
with every argument); the two public entry points take `window` keyword-only.

**Code** — replace `_run`:

```python
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
```

**Code** — replace `run_candidate`:

```python
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
```

**Code** — replace `run_registry`:

```python
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
```

**Impact:** `lab/runner.py:218` and `commands/backtest_dev.py:345` call these with no `window`
and are unchanged in behaviour. Phase 4 adds `window=` at a new call site of its own.

---

### Step 7: `research.py` — import, `DEV_WINDOW`, `unserved_reason`

**File:** `engine/src/seer_engine/research.py:57` (import block), `:63`–`:67` (constants), `:98`
(`UNSERVED_REASON`)
**Change:** Import `Window`, define research's own `DEV_WINDOW` from its own `DEV_END`, and turn
the unserved reason into a function whose default call reproduces the current constant exactly.
`DEV_END`'s line at `:63` is **not touched**.

**Code** — add to the import block, after `:57`
(`from seer_engine.backtest.market import ...`):

```python
from seer_engine.backtest.market import EMPTY_FUNDAMENTALS, Market, Membership
from seer_engine.backtest.window import Window
```

**Code** — insert after `:67` (`STORE_DIR = ...`):

```python
STORE_DIR = config.REPO_ROOT / "engine" / ".research"  # gitignored

DEV_WINDOW = Window(name="dev", start=date.min, end=DEV_END)
"""The window every helper here defaults to; ``== backtest.dev.DEV_WINDOW`` (a test pins it).

``start`` is ``date.min`` -- the dev window has no lower bound. The membership lower bound is
``MEMBERSHIP_START``, a property of the vendored CSVs rather than of the window, and the
helpers below apply it with ``max(window.start, MEMBERSHIP_START)``.
"""
```

**Code** — replace `:98` (`UNSERVED_REASON = f"..."`) with the function plus the constant,
keeping the constant's value identical:

```python
def unserved_reason(start: date = STORE_START, end: date = DEV_END) -> str:
    """What ``unserved.csv`` records for a requested member yfinance returned no bars for."""
    return f"yfinance returned no bars for {start.isoformat()}..{end.isoformat()}"


UNSERVED_REASON = unserved_reason()  # the dev store's: "...for 1993-01-29..2015-10-16"
```

**Impact:** `UNSERVED_REASON` keeps its exact string, so `build_store` (`:337`) and
`tests/test_research_store.py:256`–`:257` are unaffected. Phase 2 calls
`unserved_reason(store_start, window.end)` for the test store.

---

### Step 8: `research.py` — the four window-bearing helpers

**File:** `engine/src/seer_engine/research.py:156`–`:197`
**Change:** Each helper takes `window: Window = DEV_WINDOW` and derives its membership lower
bound as `max(window.start, MEMBERSHIP_START)`. On the dev window that is `MEMBERSHIP_START`
(because `DEV_WINDOW.start` is `date.min`), so the dev results are identical symbol for symbol
and interval for interval. `research_membership`'s clamp becomes "clamp against **this**
window's end" — the generalization phase 2 needs so that a company which left the index in 2018
does not read as a member through 2026.

**Code** — replace the block from `_overlaps_window` through `unserved_by_year`:

```python
def _members_start(window: Window) -> date:
    """The window's membership lower bound: its own start, but never before the CSVs begin.

    ``DEV_WINDOW.start`` is ``date.min``, so for the dev window this is ``MEMBERSHIP_START``
    and every result below is exactly what it was before the window became a parameter.
    """
    return max(window.start, MEMBERSHIP_START)


def _overlaps_window(iv: membership.Interval, window: Window = DEV_WINDOW) -> bool:
    lo = _members_start(window)
    return iv.start_date <= window.end and (iv.end_date is None or iv.end_date > lo)


def requested_symbols(data_dir: Path | None = None, *, window: Window = DEV_WINDOW) -> tuple[str, ...]:
    """RESEARCH_ETFS ∪ every member whose interval overlaps the window, sorted.

    The overlap is ``[max(window.start, MEMBERSHIP_START), window.end]``, which is
    ``[MEMBERSHIP_START, DEV_END]`` for the dev window. The test window's members are a
    different set -- everything that joined after October 2015 is in it and everything that
    left before is not -- so a store must be built with its own window's universe.
    """
    members = {iv.symbol for iv in _universe(data_dir) if _overlaps_window(iv, window)}
    return tuple(sorted(set(RESEARCH_ETFS) | members))


def research_membership(data_dir: Path | None = None, *, window: Window = DEV_WINDOW) -> Membership:
    """Point-in-time membership for ``window``, from the vendored CSVs (no Neon).

    Only intervals overlapping the window are kept, and an end after ``window.end`` becomes
    None (the company is a member on every session of this window), so nothing dated after
    ``window.end`` is visible even through membership. An end *inside* the window is kept as
    it is -- that is what makes this correct for the test window, where a company that left
    the index in 2018 must stop being a member in 2018. Both indices are merged with
    ``io.merge_intervals``, exactly like ``io.read_intervals`` does for Neon's ``universe``.
    """
    rows: list[tuple[str, date, date | None]] = []
    for iv in _universe(data_dir):
        if not _overlaps_window(iv, window):
            continue
        end = iv.end_date if iv.end_date is not None and iv.end_date <= window.end else None
        rows.append((iv.symbol, iv.start_date, end))
    return Membership(intervals=merge_intervals(rows))


def unserved_by_year(
    members: Membership,
    unserved: Iterable[str],
    *,
    window: Window = DEV_WINDOW,
) -> tuple[tuple[int, int, int], ...]:
    """Per calendar year of the window: (year, distinct members that year, of which unserved).

    The years run ``max(window.start, MEMBERSHIP_START).year .. window.end.year`` -- 1996..2015
    for the dev window. A symbol counts in a year when one of its intervals overlaps that
    year's part of the window."""
    missing = set(unserved)
    lo_bound = _members_start(window)
    out: list[tuple[int, int, int]] = []
    for year in range(lo_bound.year, window.end.year + 1):
        lo = max(date(year, 1, 1), lo_bound)
        hi = min(date(year, 12, 31), window.end)
        seen = {
            symbol
            for symbol, start, end in members.intervals
            if start <= hi and (end is None or end > lo)
        }
        out.append((year, len(seen), len(seen & missing)))
    return tuple(out)
```

**Impact:** `build_store` (`:320` `requested_symbols(data_dir)`), `load_store` (`:684`
`research_membership(data_dir)`) and `commands/research_store.py:261`
(`unserved_by_year(members, unserved)`) all keep compiling and keep producing the dev results.
Phase 2 adds `window=` at those three call sites.

---

### Step 9: Tests for the window object and the two dev-window copies

**File:** `engine/tests/test_backtest_window.py` (new)
**Change:** A new test module. It is the file that pins `dev.DEV_WINDOW == research.DEV_WINDOW`,
in the same spirit as `tests/test_fundamentals_coverage.py:107` pins the two `DEV_END`s — and it
re-asserts that equality here too, without editing that file.

**Code:**

```python
"""The window value object (``backtest.window.Window``) and the two dev-window constants.

``backtest.dev.DEV_WINDOW`` and ``research.DEV_WINDOW`` are duplicates, like the two
``DEV_END``s they are built from; this file is what pins them equal. The test window has no
constant: it is ``DEV_WINDOW.following("test", <the store's last session>)``.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date, datetime

import pytest

from seer_engine import research
from seer_engine.backtest import dev, dev_report
from seer_engine.backtest.window import WINDOW_NAMES, Window


def test_window_validates_its_fields():
    w = Window(name="test", start=date(2015, 10, 19), end=date(2026, 8, 18))
    assert (w.name, w.start, w.end) == ("test", date(2015, 10, 19), date(2026, 8, 18))
    assert WINDOW_NAMES == ("dev", "test")
    with pytest.raises(ValueError, match="window name must be one of"):
        Window(name="prod", start=date(2015, 10, 19), end=date(2026, 8, 18))
    with pytest.raises(ValueError, match="starts on 2026-08-19, after its end"):
        Window(name="test", start=date(2026, 8, 19), end=date(2026, 8, 18))
    with pytest.raises(TypeError):
        Window(name="test", start=datetime(2015, 10, 19), end=date(2026, 8, 18))
    with pytest.raises(TypeError):
        Window(name="test", start="2015-10-19", end=date(2026, 8, 18))


def test_a_window_is_a_frozen_value():
    a = Window(name="dev", start=date.min, end=date(2015, 10, 16))
    b = Window(name="dev", start=date.min, end=date(2015, 10, 16))
    assert a == b and hash(a) == hash(b)
    with pytest.raises(FrozenInstanceError):
        a.end = date(2026, 1, 1)


def test_covers():
    w = Window(name="test", start=date(2015, 10, 19), end=date(2015, 11, 30))
    assert w.covers(date(2015, 10, 19)) and w.covers(date(2015, 11, 30))
    assert not w.covers(date(2015, 10, 16)) and not w.covers(date(2015, 12, 1))
    assert dev.DEV_WINDOW.covers(date(1993, 1, 29))  # date.min: no lower bound
    assert not dev.DEV_WINDOW.covers(date(2015, 10, 19))
    with pytest.raises(TypeError):
        w.covers(datetime(2015, 10, 19))


def test_the_two_dev_windows_are_equal_and_end_on_dev_end():
    assert dev.DEV_WINDOW == research.DEV_WINDOW
    assert dev.DEV_WINDOW.name == "dev"
    assert dev.DEV_WINDOW.start == date.min
    assert dev.DEV_WINDOW.end == dev.DEV_END == research.DEV_END == date(2015, 10, 16)


def test_the_test_window_follows_the_dev_window():
    w = dev.DEV_WINDOW.following("test", date(2026, 8, 18))
    assert w == Window(name="test", start=date(2015, 10, 19), end=date(2026, 8, 18))
    assert w.start == dev_report.TEST_START  # the P7b constant, unchanged
    assert dev.DEV_WINDOW.following("test", date(2015, 10, 19)).end == date(2015, 10, 19)
    with pytest.raises(ValueError, match="ends on or after 2015-10-19"):
        dev.DEV_WINDOW.following("test", dev.DEV_END)
```

**Impact:** a new test module; nothing existing is edited.

---

### Step 10: Tests that the dev refusal is still absolute and a test window is reachable

**File:** `engine/tests/test_backtest_dev.py` — two import lines and an appended section
**Change:** Add `DEV_WINDOW` to the existing `from seer_engine.backtest.dev import (...)` block
(`:35`–`:44`, alphabetically after `DEV_END`) and add
`from seer_engine.backtest.window import Window` after the
`from seer_engine.backtest.runner import ...` line (`:51` area). Then append the section below
at the end of the file; it reuses `HoldOne`, `cand`, `short_market`, `FX_SHORT`, `stats`,
`metrics` and `SPY_TR`, which are all already defined in the module.

**Code** — append:

```python
# --------------------------------------------------------------------------- the test window

ACROSS_DAYS = dates.sessions(date(2015, 6, 1), date(2015, 11, 30))  # spans DEV_END
TEST_WINDOW = Window(name="test", start=date(2015, 10, 19), end=date(2015, 11, 30))


def across_market() -> Market:
    """SPY and AAA from 2015-06-01 to 2015-11-30: a market that runs past DEV_END."""
    return Market(
        history={
            "AAA": hist("AAA", sawtooth(len(ACROSS_DAYS), 50.0, 1.0, 0.9), days=ACROSS_DAYS),
            "SPY": hist("SPY", sawtooth(len(ACROSS_DAYS), 200.0, 2.0, 1.5), days=ACROSS_DAYS),
        },
        membership=Membership((("AAA", date(1990, 1, 2), None),)),
        fx=FX_SHORT,
    )


def test_the_default_window_is_the_dev_window():
    assert DEV_WINDOW == Window(name="dev", start=date.min, end=DEV_END)
    assert DEV_WINDOW.end == DEV_END


def test_a_caller_that_passes_nothing_is_still_refused_past_dev_end():
    """The D9 refusal is absolute by default: the window argument does not weaken it."""
    market = across_market()
    c = cand("T-DEFAULT", allocator=HoldOne("TD", "SPY", lookback=5))
    for call in (lambda: candidate_window(market, c),
                 lambda: run_candidate(market, {}, (), c),
                 lambda: run_registry(market, {}, (), (c,))):
        with pytest.raises(DevWindowError, match="after the dev window end 2015-10-16"):
            call()


def test_an_explicit_test_window_runs_past_dev_end():
    market = across_market()
    c = cand("T-RUN", allocator=HoldOne("TR", "SPY", lookback=5))
    assert candidate_window(market, c, window=TEST_WINDOW) == (date(2015, 10, 19), date(2015, 11, 30))
    result, row = run_candidate(market, {}, (), c, window=TEST_WINDOW)
    assert (row.start, row.end) == (date(2015, 10, 19), date(2015, 11, 30))
    assert row.window == TEST_WINDOW and row.window.name == "test"
    assert run_registry(market, {}, (), (c,), window=TEST_WINDOW) == (row,)


def test_a_test_window_opens_no_earlier_than_its_own_start():
    """The floor: the lookback may be satisfied long before the window, the run may not start there."""
    c = cand("T-FLOOR", allocator=HoldOne("TF", "SPY", lookback=1))
    assert candidate_window(short_market(), c)[0] == date(2015, 6, 2)  # dev: as early as the data allows
    assert candidate_window(across_market(), c, window=TEST_WINDOW)[0] == TEST_WINDOW.start


def test_a_test_window_still_waits_for_the_lookback():
    market = across_market()
    n = ACROSS_DAYS.index(date(2015, 11, 2)) + 1  # SPY's n-th bar is 2015-11-02
    c = cand("T-LOOK", allocator=HoldOne("TL", "SPY", lookback=n))
    assert candidate_window(market, c, window=TEST_WINDOW) == (
        dates.next_session(date(2015, 11, 2)), date(2015, 11, 30))


def test_the_dividend_guard_follows_the_window_too():
    market = across_market()
    c = cand("T-DIV", allocator=HoldOne("TV", "SPY", lookback=5))
    late = date(2015, 11, 20)
    divs = {"SPY": {late: Decimal("1.03")}}
    spy_divs = (Dividend(late, Decimal("1.03")),)
    with pytest.raises(DevWindowError, match="after the dev window end"):
        run_candidate(market, divs, spy_divs, c)
    _, row = run_candidate(market, divs, spy_divs, c, window=TEST_WINDOW)
    assert row.end == date(2015, 11, 30)
    beyond = (Dividend(date(2015, 12, 18), Decimal("1.03")),)
    with pytest.raises(DevWindowError, match="after the test window end 2015-11-30"):
        run_candidate(market, divs, beyond, c, window=TEST_WINDOW)


def test_rows_carry_their_window():
    s = stats(metrics())
    with pytest.raises(DevWindowError, match="after the dev window end"):
        make_row(cand("T-ROW"), date(2015, 10, 19), date(2015, 11, 30), s, spy_tr=SPY_TR, spy_price=SPY_TR)
    row = make_row(cand("T-ROW"), date(2015, 10, 19), date(2015, 11, 30), s,
                   spy_tr=SPY_TR, spy_price=SPY_TR, window=TEST_WINDOW)
    assert row.window == TEST_WINDOW
    with pytest.raises(ValueError, match="is before the test window start"):
        make_row(cand("T-EARLY"), date(2015, 6, 8), date(2015, 11, 30), s,
                 spy_tr=SPY_TR, spy_price=SPY_TR, window=TEST_WINDOW)
    assert make_row(cand("T-DEV"), date(2015, 6, 8), DEV_END, s,
                    spy_tr=SPY_TR, spy_price=SPY_TR).window == DEV_WINDOW
    with pytest.raises(TypeError, match="window must be a Window"):
        make_row(cand("T-BAD"), date(2015, 6, 8), DEV_END, s,
                 spy_tr=SPY_TR, spy_price=SPY_TR, window="test")
```

**Impact:** no existing test function is edited. `test_check_dev_session`,
`test_entry_points_reject_a_bar_after_dev_end`, `test_entry_points_reject_fx_after_dev_end`,
`test_run_entry_points_reject_dividends_after_dev_end`, `test_rows_reject_an_end_after_dev_end`,
`test_window_waits_for_the_latest_launch`, `test_window_respects_the_membership_start` and
`test_window_errors` all keep passing as written.

---

### Step 11: Tests that the research helpers follow the window they are given

**File:** `engine/tests/test_research_store.py` — one import line and an appended section
**Change:** Add `from seer_engine.backtest.window import Window` to the import block (after
`from seer_engine.backtest.benchmark import Dividend`, `:19`), then append the section below at
the end of the file. The `members_dir` fixture already describes a universe that straddles
`DEV_END`: `GONE` leaves on 2000-01-03, `BBB` leaves on 2016-01-04, `NEW` joins on 2016-01-04.
Nothing in the file is edited — `test_constants_match_the_contract` (`:152`),
`test_requested_symbols_are_etfs_and_dev_window_members`,
`test_research_membership_is_clipped_to_the_dev_window` and `test_unserved_by_year` stay exactly
as they are and are the proof that the dev defaults did not move.

**Code** — append:

```python
# ---- the window parameter ------------------------------------------------------------------

TEST_WINDOW = Window(name="test", start=date(2015, 10, 19), end=date(2026, 8, 18))


def test_the_dev_window_is_what_every_helper_defaults_to(members_dir):
    assert research.DEV_WINDOW == Window(name="dev", start=date.min, end=research.DEV_END)
    assert research.requested_symbols(members_dir, window=research.DEV_WINDOW) == research.requested_symbols(members_dir)
    explicit = research.research_membership(members_dir, window=research.DEV_WINDOW)
    assert explicit.intervals == research.research_membership(members_dir).intervals
    members = research.research_membership(members_dir)
    assert research.unserved_by_year(members, ["DDD"], window=research.DEV_WINDOW) == research.unserved_by_year(
        members, ["DDD"])


def test_the_test_window_selects_its_own_universe(members_dir):
    symbols = research.requested_symbols(members_dir, window=TEST_WINDOW)
    assert "NEW" in symbols  # joined 2016-01-04: never a dev-window member
    assert "GONE" not in symbols  # left 2000-01-03: never a test-window member
    assert set(research.RESEARCH_ETFS) <= set(symbols)


def test_membership_is_clamped_against_this_windows_end(members_dir):
    m = research.research_membership(members_dir, window=TEST_WINDOW)
    # BBB leaves on 2016-01-04, inside this window: the end is kept, not opened up.
    assert ("BBB", date(1996, 1, 2), date(2016, 1, 4)) in m.intervals
    assert ("NEW", date(2016, 1, 4), None) in m.intervals
    assert all(end is None or end <= TEST_WINDOW.end for _, _, end in m.intervals)
    assert "NEW" in m.members_on(date(2016, 1, 5))
    assert "BBB" not in m.members_on(date(2016, 1, 5))
    # A window that ends before BBB leaves: open-ended again, exactly as the dev store has it.
    early = research.research_membership(
        members_dir, window=Window(name="test", start=date(2015, 10, 19), end=date(2015, 12, 31))
    )
    assert ("BBB", date(1996, 1, 2), None) in early.intervals


def test_unserved_by_year_follows_the_window(members_dir):
    m = research.research_membership(members_dir, window=TEST_WINDOW)
    table = research.unserved_by_year(m, ["DDD"], window=TEST_WINDOW)
    assert [y for y, _, _ in table] == list(range(2015, 2027))
    rows = {y: (n, u) for y, n, u in table}
    assert rows[2026][1] == 1  # DDD is still a member and still unserved


def test_unserved_reason_names_the_range_it_is_given():
    assert research.unserved_reason() == research.UNSERVED_REASON
    assert research.UNSERVED_REASON == "yfinance returned no bars for 1993-01-29..2015-10-16"
    assert research.unserved_reason(date(2015, 10, 19), date(2026, 8, 18)) == (
        "yfinance returned no bars for 2015-10-19..2026-08-18"
    )
```

**Impact:** `engine/tests/test_research_store.py` grows by one import and one section. Phase 2
does **not** edit this file (it adds `test_research_test_store.py` instead), so this phase is its
sole editor in the set.

---

## Verification

**Build:**

```
cd /home/miftah/.worktrees/seer/build-promotion-path/engine
python -m compileall -q src/seer_engine/backtest/window.py src/seer_engine/backtest/dev.py src/seer_engine/research.py
ruff check src tests
```

**Tests:**

```
cd /home/miftah/.worktrees/seer/build-promotion-path/engine
python -m pytest -q                      # the whole suite must be green
python -m pytest -q tests/test_backtest_window.py tests/test_backtest_dev.py \
                   tests/test_research_store.py tests/test_fundamentals_coverage.py \
                   tests/test_strategy_purity.py tests/test_backtest_dev_report.py \
                   tests/test_backtest_dev_command.py tests/test_registry.py \
                   tests/test_lab_runner.py tests/test_lab_methods.py \
                   tests/test_market_fundamentals.py tests/test_f_fundamental.py
```

**Manual check — the three things that could silently go wrong:**

1. **`DEV_END` untouched.** `git diff` must show no change on `backtest/dev.py:53` or
   `research.py:63`:
   ```
   git diff -U0 -- engine/src/seer_engine/backtest/dev.py engine/src/seer_engine/research.py | grep '^[-+].*DEV_END = '
   ```
   must print nothing.
2. **The pinned tests are unedited.**
   ```
   git diff --stat -- engine/tests/test_fundamentals_coverage.py
   ```
   must print nothing, and the diff of `engine/tests/test_research_store.py` must contain only
   the one import line and the appended section — no change inside
   `test_constants_match_the_contract`, `test_requested_symbols_are_etfs_and_dev_window_members`,
   `test_research_membership_is_clipped_to_the_dev_window` or `test_unserved_by_year`.
3. **`lab run` digests cannot have shifted.** `lab.method.config_digest` (`lab/method.py:40`)
   hashes `rules`, `allocator.id` and `params` only — no window, no dates — so no digest in
   `lab/lab.sqlite` can move. The only window-derived values a trial records are
   `trials.start`/`trials.end`, and both are unchanged on the dev window:
   `DEV_WINDOW.end == DEV_END` (so the end is literally the same expression), and
   `DEV_WINDOW.start == date.min`, so the new floor in `candidate_window` is unreachable on any
   dev call. Confirm the floor branch is never taken on the dev window:
   ```
   python - <<'PY'
   from datetime import date
   from seer_engine.backtest.dev import DEV_WINDOW
   assert DEV_WINDOW.start == date.min, DEV_WINDOW
   print("floor is dead code on the dev window")
   PY
   ```
   `tests/test_backtest_dev_command.py` already asserts byte-identical report files across two
   runs and `report.rows == dev.run_registry(...)`; both must stay green.

**Exit criteria:**

- `engine/` `pytest -q` is green with `DEV_END` unchanged in both modules and
  `tests/test_fundamentals_coverage.py` not touched at all.
- Every existing caller of `candidate_window`, `run_candidate`, `run_registry`,
  `requested_symbols`, `research_membership` and `unserved_by_year` compiles and runs with no
  argument change.
- `test_a_caller_that_passes_nothing_is_still_refused_past_dev_end` proves a market holding a
  post-`DEV_END` bar is still refused at all three entry points with the dev window in force,
  and `test_an_explicit_test_window_runs_past_dev_end` proves the same market runs when a
  `test` window is passed explicitly.
- `test_membership_is_clamped_against_this_windows_end` proves the clamp is against the passed
  window's end, not `DEV_END`.
- `dev.DEV_WINDOW == research.DEV_WINDOW` and `DEV_WINDOW.following("test", d).start ==
  date(2015, 10, 19)`.

## Handoffs

**To phase 2 (test-window store) — what is ready and what it must do:**

- The three call sites that keep the dev default today and need `window=` added for a test
  store: `research.py:320` `requested_symbols(data_dir)` in `build_store`, `research.py:684`
  `research_membership(data_dir)` in `load_store`, `commands/research_store.py:261`
  `unserved_by_year(members, unserved)`.
- `research.py:337` writes `UNSERVED_REASON`; for a test store use
  `unserved_reason(<its download start>, window.end)`.
- `research.py:370`–`:384` (FX range), `:406`–`:407`, `:443`, `:459`, `:479`–`:483` (`_clip`),
  `:510`–`:511` (manifest `dev_end`/`store_start`), `:728`–`:736` (manifest checks), `:762`,
  `:794`–`:799`, `:842`, `:860`, `:879`, `:895`–`:903` still hard-code `STORE_START`/`DEV_END`.
  They are phase 2's, deliberately untouched here.
- **Done by phase 2, as recommended:** `ResearchData` gains `window: Window = DEV_WINDOW`, and the
  manifest gains an optional `window_name` / `window_start` / `window_end` triple (absent means
  the dev window, so `engine/.research`'s nine-key manifest and its fingerprint `399d0d25…` do
  not move). `load_store` refuses a test store where a dev store is expected and the reverse,
  before reading any data file. This phase deliberately does not touch `ResearchData`.
- **The store's data range: settled, and settled the safe way.** `candidate_window` floors a
  candidate's start at `window.start`, so a test run cannot *open* before 2015-10-19 even if the
  store holds 1993 bars — and `_check_market` does **not** reject bars *before* a window's start
  (it cannot: the dev store legitimately holds 1993 bars and the dev window's start is
  `date.min`). **Phase 2 carries a coordinator decision that the test store is built over
  `STORE_START..window.end`** — the full run-up — so long-lookback candidates open on 2015-10-19
  rather than months later. This phase's floor is what makes that safe: the store may hold 1993
  bars without the run reaching back into them.

**To phase 4 (`lab test`):**

- Call `dev.run_registry(market, dividends, spy_dividends, candidates, on_result=..., window=<the test window>)`.
  Nothing else in `backtest/dev.py` needs to change.
- **The hard blocker phase 4 flagged is handled here.** `DevRow.__post_init__`'s
  `check_dev_session(self.end)` (`dev.py:280`) becomes `check_dev_session(self.end, self.window)`
  in Step 5, so a row produced on the test window is constructible. Phase 4 must not patch
  `backtest/dev.py` itself; it is out of its scope and nothing in it needs to change.
- Import `Window` from `seer_engine.backtest.window`, the module this phase creates. `dev.Window`
  happens to resolve because `dev.py` imports it, but that is an import line, not a contract.
- `store.TrialRow.window` should be `row.window.name` (`"test"`), not a literal, so the row and
  the run cannot disagree.
- **`backtest/dev_report.py` is dev-only and stays that way.** `_validate` (`:154`–`:208`) calls
  `check_dev_session(row.end)` with no window and compares `r.spy_window` to
  `(earliest, DEV_END)`, so feeding it a test row raises. Phase 4 must not route test rows
  through `dev_report`; if it wants a rendered test report, parameterizing `dev_report` is new
  work that belongs to phase 4 and should be called out there.
- `lab/runner.py:148` (`store.dev_trial_count`) and `:167` (`window="dev"`) stay dev-only —
  decision D2 in the index. Nothing in this phase touches them.

**Found and deliberately not done here:**

- `backtest/dev.py` still names its error `DevWindowError` even when a test window raises it.
  Renaming it would churn six test files for no behavioural gain; the docstring now says what it
  means. Left alone.
- `dev_report.TEST_START` (`dev_report.py:57`) is a third literal `date(2015, 10, 19)`. It is
  now pinned equal to `DEV_WINDOW.following("test", …).start` by
  `tests/test_backtest_window.py`, but it is not deduplicated — `dev_report` is not this phase's
  file. A later phase may collapse it.

## Rollback

One commit on `feature/build-promotion-path`; `git revert` it. Nothing in this phase writes to
`lab/lab.sqlite`, `web/data/lab.json`, `engine/.research/` or any file on disk outside the three
source files and three test files listed above, and no recorded trial, digest or fingerprint is
touched, so reverting restores the tree exactly. If only part of it must come out, the new module
`engine/src/seer_engine/backtest/window.py` plus the defaulted parameters are additive: deleting
`engine/tests/test_backtest_window.py` and the two appended test sections leaves a green tree
with the old behaviour intact.
