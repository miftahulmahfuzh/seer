# Phase 1: The coverage gate: a pure measure, a CLI surface, a `lab run` refusal

**Plan set:** `FUNDAMENTAL_PANEL_COVERAGE_PLAN.md`
**Analysis:** `20261005-133648-2XUM_code_analyzer.md`
**Satisfies:** R3 — the coverage check moves out of a runbook snippet and into the engine, so no
future method can be run against a panel that cannot rank.
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/fundamentals` (plus `commands` and `lab`)

---

## Runtime preamble — run this before every command in this phase

Reconciled set-wide (see the index's `## Decisions`, row C2). The worktree has **no venv of its
own**, and `/home/miftah/seer/engine/.venv` is an *editable* install whose
`__editable__.seer_engine-0.1.0.pth` contains the literal `/home/miftah/seer/engine/src` — the
**main checkout**. `engine/pyproject.toml`'s `[tool.pytest.ini_options]` sets only
`testpaths = ["tests"]` and **no `pythonpath`**, so pytest resolves `seer_engine` through that
same editable install. Without the block below, every command in this phase — `pytest`
included — silently exercises `main`'s code and reads `main`'s `engine/data/`.

```bash
export SEER_WT=/home/miftah/.worktrees/seer/fundamental-panel-coverage
export SEER_PY=/home/miftah/seer/engine/.venv/bin/python
export PYTHONPATH=$SEER_WT/engine/src          # searched before anything `site` adds
cd "$SEER_WT"
"$SEER_PY" -c 'import seer_engine, pathlib; print(pathlib.Path(seer_engine.__file__).resolve())'
# must print $SEER_WT/engine/src/seer_engine/__init__.py
```

**Reuse main's venv; do not build one in the worktree.** `PYTHONPATH` wins over the `.pth`
(measured), carries `cik.DATA_DIR` (`Path(cik.__file__).parents[2] / "data"`) to the worktree
with it, and applies uniformly to `pytest` and to `python -m seer_engine`. A second venv would
mean a second dependency resolution, and invariant 1 pins this set to the `2dad9ff` baseline of
2216 passed / 332 skipped measured in *this* interpreter.
`engine/scripts/build_ticker_cik.py:40` does its own
`sys.path.insert(0, Path(__file__).resolve().parents[1] / "src")`, so the generator
self-resolves when invoked by its worktree path — that rescues the generator and nothing else.

This phase touches no database and no network. The preamble is still mandatory: without it the
`research_store --coverage` smoke run and the whole pytest run execute `main`'s `seer_engine`,
which has no `coverage.py`, and the failure reads as "the module was not created".

---

## Goal

After this phase the tree can answer, in pure code, *"on how many sampled dev-window dates can
this panel rank at least `top` symbols?"* — using `Snapshot.observations` as the emptiness test
and `f_fundamental`'s own 400-day staleness gate, so the number predicts rankability rather than
fact-existence. `python -m seer_engine research_store --coverage` prints that number and a
per-year table for any store on disk, and `lab run` refuses a method with a `MarketAware`
allocator when the number is below `MIN_DEV_COVERAGE = 0.80`, unless `--allow-coverage F` is
given — which lowers the floor and still prints the measurement. M0005 was spent because no such
check existed; this is that check.

## Interface Contract

**Creates:**

- `seer_engine.fundamentals.coverage` (new module, `engine/src/seer_engine/fundamentals/coverage.py`)
  - `coverage.CoverageError` (a `ValueError`)
  - `coverage.WINDOW_START` = `date(1996, 1, 2)`, `coverage.WINDOW_END` = `date(2015, 10, 16)`
  - `coverage.DEFAULT_TOP` = `20`, `coverage.MIN_DEV_COVERAGE` = `0.80`
  - `coverage.YearCoverage`, `coverage.Coverage` (frozen dataclasses)
  - `coverage.default_max_stale_days()`, `coverage.is_rankable()`,
    `coverage.rankable_symbols()`, `coverage.rankable_count()`, `coverage.monthly_dates()`,
    `coverage.measure()`, `coverage.format_report()`
- `seer_engine.lab.runner.market_aware_candidates(method)` (`engine/src/seer_engine/lab/runner.py`)
- `seer_engine.lab.runner.preflight_data(data, method, *, min_coverage=...)` (same file)
- `seer_engine.commands.research_store._coverage(store)` (`engine/src/seer_engine/commands/research_store.py`)
- `seer_engine.commands.lab._coverage_floor(text)` (`engine/src/seer_engine/commands/lab.py`)
- CLI flag `research_store --coverage`
- CLI flag `lab run --allow-coverage FLOAT` (on the `run` subparser only)

**Deletes:** nothing.
**Renames:** nothing.
**Signature changes:** none. `runner.preflight` keeps its exact signature; `preflight_data` is a
new, separate function. `commands/lab._run` reads `args.allow_coverage` through `getattr` with a
default, so a `Namespace` built without it still works.

**Requires (from earlier phases):** nothing. This phase must work against the **current**
store (measured 0.0378 under this phase's own monthly sample; see **Exit criteria**) and its
tests must not touch a store, a database or the network.

**Depended on by (reconciled):** **Phase 4** now lists this phase in its `Depends on`. Both
phases edit `engine/src/seer_engine/commands/research_store.py`'s `run()` and
`add_arguments()`, and phase 4's own required branch order
(`guards -> --coverage -> --verify -> --refresh-fundamentals -> build`) can only be produced by
a serialisation. This phase lands first and rewrites `run()` wholesale (step 3d); phase 4 quotes
**that** body verbatim and appends one branch to it. Nothing in this phase anticipates phase 4:
the `run()` written here is final for this phase and compiles and passes on its own.

**Leaves alone (owned by others):**

- `engine/src/seer_engine/cik.py`, `engine/scripts/build_ticker_cik.py`,
  `engine/data/ticker_cik.csv`, `engine/data/SOURCES.md` (Phase 2)
- `engine/src/seer_engine/commands/fundamentals.py` (Phase 3)
- `engine/src/seer_engine/research.py` entirely — `build_store`, `_seal`, `_swap_in`,
  `load_store`, `MANIFEST_KEYS`, `_COUNT_KEYS` (Phase 4)
- in `engine/src/seer_engine/commands/research_store.py`: `_build`, `_read_facts`,
  `--with-fundamentals`, `_verify`, `format_summary` — **unchanged** (Phase 4 lands *after* this
  phase and appends its fundamentals-only refresh flag and branch to what this phase leaves
  behind; see **Handoffs**)
- `engine/src/seer_engine/fundamentals/panel.py`, `ladder.py`, `sue.py` — read, not changed
- `engine/src/seer_engine/lab/methods/m0005_fundamental_factors.py` (Phase 5)
- every `docs/` file, `engine/package_readme.md` (Phase 5)
- every database, and `engine/.research/` on disk

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/fundamentals/coverage.py` | create | the whole pure measure |
| `engine/src/seer_engine/fundamentals/__init__.py` | modify | re-export the new names (import block at `:18`, `__all__` at `:66`) |
| `engine/src/seer_engine/commands/research_store.py` | modify | `--coverage` (`:34`, `:12`, `:72`, `:84`, `:129`) |
| `engine/src/seer_engine/lab/runner.py` | modify | `market_aware_candidates`, `preflight_data` (`:23`, `:69`) |
| `engine/src/seer_engine/commands/lab.py` | modify | `--allow-coverage` and the call in `_run` (`:34`, `:40`, `:52`, `:217`) |
| `engine/tests/test_fundamentals_coverage.py` | create | the measure's own tests |
| `engine/tests/test_lab_runner.py` | modify | the refusal's tests (additions only, after `:116`) |

---

## Design notes the implementer must not re-litigate

Three facts were established by reading the tree; getting any of them wrong breaks the phase.

**1. `coverage.py` lands inside the purity glob.** `engine/tests/test_strategy_purity.py:33`
globs `seer_engine/fundamentals/*.py` with no allow-list, so the new file is policed the moment
it exists. It may not import `time`, `random`, `logging`, `urllib`, `socket`, `psycopg`,
`requests`, `yfinance` or `seer_engine.bars`; it may not call `print`, `open` or `input`; and it
may not touch an attribute named `now`, `utcnow`, `today`, `fromtimestamp` or `random`. Hence
`format_report` **returns** a string and the CLI prints it.

**2. The `f_fundamental` import must be deferred, and this is not a style choice.**
`strategies/f_fundamental.py:96` is `from seer_engine.fundamentals import EMPTY_PANEL`. If
`coverage.py` imported `FundamentalParams` at module scope, then
`import seer_engine.strategies.f_fundamental` in a fresh interpreter would run f_fundamental to
line 96 → `fundamentals/__init__` → `coverage` → back into the half-executed
`seer_engine.strategies.f_fundamental`, where `FundamentalParams` (line 204) does not exist yet
→ `ImportError`. So the import lives inside `default_max_stale_days()`. The purity AST test
walks nested nodes too, but `seer_engine` is not a forbidden root, so a deferred import is legal.
A test in `test_fundamentals_coverage.py` pins this by importing each module first in a
subprocess.

The module-scope import `from seer_engine.fundamentals.panel import FundamentalPanel, Snapshot`
**is** safe, including when `__init__.py` imports `coverage` before `ladder` and `panel`:
`from package.submodule import name` falls back to importing the submodule when the package is
only partially initialised. `panel.py`'s own `from seer_engine.fundamentals import ladder`
resolves the same way.

**3. The window constants are duplicated, not imported — on purpose.**
`backtest/dev.py` imports `backtest/market.py`, which imports `seer_engine.fundamentals`; and
`research.py` imports `yfinance` through `seer_engine.yahoo`. Importing either from
`coverage.py` would be a hard cycle (dev/market first) or a purity failure (research). The tree
already has this exact pattern: `research.py:63` carries `DEV_END = date(2015, 10, 16)  # ==
backtest.dev.DEV_END` and `backtest/dev.py`'s docstring says the duplicate is *"pinned equal to
this one by a test"*. `coverage.WINDOW_START`/`WINDOW_END` follow it, with the same pinning test.

**Cost, measured during planning.** The measure as written below was run against the real store
(`/home/miftah/seer/engine/.research/fundamentals.csv`, 780 panel symbols) on 2026-10-05: 238
monthly samples took **2.7 s** after the panel was in memory. The sparse era is cheap because
`SymbolFundamentals._visible` bisects to an empty prefix, so `as_of` does almost no work. No
short-circuit or cache is needed, and none may be added — the per-date counts are themselves part
of the report.

---

## Implementation Steps

### Step 1: The pure measure

**File:** `engine/src/seer_engine/fundamentals/coverage.py` (new file, whole contents)
**Change:** the module. Nothing in it reads a clock, a file, a socket or a database.
**Code:**

```python
"""Can the panel rank? The dev-window coverage measure, and the floor ``lab run`` enforces.

M0005 was spent against a store whose panel held no fact filed before 2013, on a dev window that
opens in 1996. The check that was meant to catch that asked ``panel.as_of(symbol, t) is not
None`` -- and that question is vacuous. ``FundamentalPanel.as_of`` returns None only for a symbol
with no fact at ALL, ever, and ``SymbolFundamentals.as_of`` always answers with a ``Snapshot``: an
empty husk whose ``observations`` is ``{}`` when nothing is visible at ``t``. All 780 symbols of
the measured panel therefore passed that check on every date in 1996, and the number it produced
measured nothing. **The honest emptiness test is ``Snapshot.observations``.** The anti-pattern
must not appear anywhere in this tree except in this paragraph, which documents it.

What this module answers instead: *on how many sampled dev-window dates can the panel rank at
least ``top`` symbols?* A symbol counts on date ``t`` only when both

1. ``panel.as_of(symbol, t)`` has a **non-empty** ``observations``, and
2. that snapshot's newest ``filed`` is within ``max_stale_days`` days of ``t``.

(2) is ``strategies.f_fundamental``'s own eligibility gate, restated here deliberately so the
number predicts *rankability* rather than mere fact-existence: a symbol whose newest filing is
three years old is in the panel and is in no cross-section ``FUNDAMENTAL`` ever builds. The
window itself is read off ``FundamentalParams`` rather than written down again -- see
``default_max_stale_days``.

**The measure is an upper bound.** ``f_fundamental.eligible_rows`` additionally requires index
membership, a close at or above ``min_price``, twenty sessions of history and dollar volume above
``min_dollar_volume``; every one of those can only remove symbols. So a number below the floor is
conclusive -- the panel cannot rank -- while a number above it is necessary and not sufficient.
Bars are deliberately not read: this module is pure and takes a panel, nothing else.

Pure: no database, network, clock, randomness or file IO (tests/test_strategy_purity.py globs
``fundamentals/*.py``, so this file is policed automatically). Two consequences worth stating:

* ``format_report`` **returns** a string. ``print`` is forbidden here; the CLI prints.
* ``seer_engine.strategies.f_fundamental`` is imported **inside** ``default_max_stale_days``, not
  at module scope. That module imports this package at its own module scope
  (``f_fundamental.py:96``), so a module-scope import here would make
  ``import seer_engine.strategies.f_fundamental`` fail in a fresh interpreter.

``WINDOW_START`` and ``WINDOW_END`` are duplicated constants, pinned to ``backtest.dev`` and
``research`` by a test, for the same reason ``research.DEV_END`` duplicates ``dev.DEV_END``:
``backtest.dev`` imports ``backtest.market``, which imports this package, and ``research``
imports yfinance.
"""

from __future__ import annotations

import calendar
from collections.abc import Sequence
from dataclasses import dataclass, fields
from datetime import date, datetime

from seer_engine.fundamentals.panel import FundamentalPanel, Snapshot

WINDOW_START = date(1996, 1, 2)
"""First sampled date: the first ``sp500_history.csv`` row.

== ``backtest.dev.MEMBERSHIP_START`` == ``research.MEMBERSHIP_START``, pinned by
``test_fundamentals_coverage.py``. Not imported; see the module docstring.
"""

WINDOW_END = date(2015, 10, 16)
"""Last sampled date: the last dev session.

== ``backtest.dev.DEV_END`` == ``research.DEV_END``, pinned by the same test.
"""

DEFAULT_TOP = 20
"""How many symbols the panel must be able to rank for a date to count as covered.

``FundamentalParams.top``'s own default, and what every M0005 variant asked for. A date on which
fewer than this many symbols are rankable cannot fill the book from fundamentals.
"""

MIN_DEV_COVERAGE = 0.80
"""The fraction of sampled dev-window dates a ``MarketAware`` method's store must cover.

``lab run`` refuses below this (``lab.runner.preflight_data``). It is a floor on the *data*, not
on the hypothesis: a method whose panel can rank on four dates in five still has to beat SPY.
"""


class CoverageError(ValueError):
    """A coverage measurement was asked for on an impossible window or an invalid parameter."""


def _check_date(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise CoverageError(f"{name} must be a date, got {type(d).__name__}")
    return d


def _check_int(name: str, v: object) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise CoverageError(f"{name} must be an int, got {type(v).__name__}")
    if v < 1:
        raise CoverageError(f"{name} must be >= 1, got {v}")
    return v


def default_max_stale_days() -> int:
    """``FundamentalParams.max_stale_days``'s own default, read off the dataclass.

    Read rather than restated: if the strategy's staleness window ever moves, the coverage
    measure moves with it and no second literal has to be found. The import is deliberately
    deferred -- ``strategies.f_fundamental`` imports this package at module scope, so importing
    it at module scope here would be a cycle. See the module docstring.
    """
    from seer_engine.strategies.f_fundamental import FundamentalParams

    for f in fields(FundamentalParams):
        if f.name == "max_stale_days":
            return _check_int("max_stale_days", f.default)
    raise CoverageError("FundamentalParams has no max_stale_days field")


def is_rankable(snapshot: Snapshot | None, t: date, max_stale_days: int) -> bool:
    """Can ``f_fundamental`` put this snapshot into its cross-section on ``t``?

    Mirrors ``strategies/f_fundamental.py``'s eligibility gate, in its order:

    * None means the panel has no fact for the symbol at all -- not rankable.
    * An **empty ``observations``** means nothing was visible at ``t``. This is the check, and
      the only honest one: a ``Snapshot`` exists for every symbol the panel knows, on every date
      in the window, whether or not anything had been filed.
    * ``filed is None`` cannot happen with non-empty observations, and ``filed > t`` would be a
      point-in-time bug rather than a stale fact. Both are refused anyway: this is the one
      assertion standing between a look-ahead and a backtest that looks wonderful.
    * A newest filing older than ``max_stale_days`` is stale -- in the panel, not in the book.
    """
    if snapshot is None:
        return False
    if not snapshot.observations:
        return False
    filed = snapshot.filed
    if filed is None or filed > t:
        return False
    return (t - filed).days <= max_stale_days


def rankable_symbols(
    panel: FundamentalPanel,
    t: date,
    *,
    max_stale_days: int | None = None,
) -> tuple[str, ...]:
    """Every symbol ``panel`` could rank on ``t``, sorted.

    ``max_stale_days`` defaults to ``default_max_stale_days()``. Membership, price and liquidity
    are not applied -- they are the caller's bars, and they can only shorten this list.
    """
    _check_date("t", t)
    stale = default_max_stale_days() if max_stale_days is None else _check_int("max_stale_days", max_stale_days)
    return tuple(s for s in panel.names() if is_rankable(panel.as_of(s, t), t, stale))


def rankable_count(panel: FundamentalPanel, t: date, *, max_stale_days: int | None = None) -> int:
    """How many symbols ``panel`` could rank on ``t``."""
    return len(rankable_symbols(panel, t, max_stale_days=max_stale_days))


def monthly_dates(start: date = WINDOW_START, end: date = WINDOW_END) -> tuple[date, ...]:
    """``start``, then the same day of month in every later month, through ``end``.

    A month shorter than ``start.day`` contributes its last day, so the sample is exactly one
    date per calendar month with no gaps and no dependence on a trading calendar. The default
    window gives 238 dates, 1996-01-02 .. 2015-10-02.
    """
    _check_date("start", start)
    _check_date("end", end)
    if end < start:
        raise CoverageError(f"end {end} is before start {start}")
    out: list[date] = []
    year, month = start.year, start.month
    while True:
        d = date(year, month, min(start.day, calendar.monthrange(year, month)[1]))
        if d > end:
            break
        if d >= start:
            out.append(d)
        month = month + 1
        if month == 13:
            year, month = year + 1, 1
    return tuple(out)


@dataclass(frozen=True, slots=True)
class YearCoverage:
    """One calendar year of a sample: dates sampled, dates covered, and the best date's count."""

    year: int
    sampled: int
    covered: int
    most_rankable: int


@dataclass(frozen=True, slots=True)
class Coverage:
    """What a panel can rank across a sampled window. Build it with :func:`measure`.

    ``counts[i]`` is how many symbols were rankable on ``dates[i]``. A date is *covered* when
    that count is at least ``top``. ``symbols`` is how many symbols the panel holds at all --
    reported next to the fraction precisely so that a large panel with a tiny coverage cannot be
    mistaken for a small one.
    """

    top: int
    max_stale_days: int
    dates: tuple[date, ...]
    counts: tuple[int, ...]
    symbols: int

    def __post_init__(self) -> None:
        if not self.dates:
            raise CoverageError("a coverage measurement needs at least one sampled date")
        if len(self.dates) != len(self.counts):
            raise CoverageError(f"{len(self.dates)} dates but {len(self.counts)} counts")

    @property
    def start(self) -> date:
        """The first sampled date."""
        return self.dates[0]

    @property
    def end(self) -> date:
        """The last sampled date."""
        return self.dates[-1]

    @property
    def covered_dates(self) -> int:
        """Sampled dates on which at least ``top`` symbols were rankable."""
        return sum(1 for c in self.counts if c >= self.top)

    @property
    def fraction(self) -> float:
        """``covered_dates`` over sampled dates: the one number the floor is compared against."""
        return self.covered_dates / len(self.dates)

    def by_year(self) -> tuple[YearCoverage, ...]:
        """One :class:`YearCoverage` per calendar year present in the sample, ascending."""
        rows: dict[int, list[int]] = {}
        for d, c in zip(self.dates, self.counts, strict=True):
            row = rows.setdefault(d.year, [0, 0, 0])
            row[0] = row[0] + 1
            if c >= self.top:
                row[1] = row[1] + 1
            if c > row[2]:
                row[2] = c
        return tuple(YearCoverage(y, rows[y][0], rows[y][1], rows[y][2]) for y in sorted(rows))


def measure(
    panel: FundamentalPanel,
    *,
    start: date = WINDOW_START,
    end: date = WINDOW_END,
    top: int = DEFAULT_TOP,
    max_stale_days: int | None = None,
    dates: Sequence[date] | None = None,
) -> Coverage:
    """How much of ``start..end`` ``panel`` can rank, sampled monthly.

    ``dates`` replaces the monthly sample outright (``start`` and ``end`` are then unused); it
    exists for tests and for a caller that wants a denser look. ``max_stale_days`` defaults to
    ``default_max_stale_days()``, i.e. to whatever ``f_fundamental`` currently enforces.

    An empty panel is a normal input and measures 0.0; it is not an error. An empty *sample* is.
    """
    if not isinstance(panel, FundamentalPanel):
        raise CoverageError(f"panel must be a FundamentalPanel, got {type(panel).__name__}")
    _check_int("top", top)
    stale = default_max_stale_days() if max_stale_days is None else _check_int("max_stale_days", max_stale_days)
    if dates is None:
        sample = monthly_dates(start, end)
    else:
        sample = tuple(dates)
        for i, d in enumerate(sample):
            _check_date(f"dates[{i}]", d)
    if not sample:
        raise CoverageError("a coverage measurement needs at least one sampled date")
    counts = tuple(len(rankable_symbols(panel, d, max_stale_days=stale)) for d in sample)
    return Coverage(top=top, max_stale_days=stale, dates=sample, counts=counts, symbols=len(panel))


def format_report(cov: Coverage, *, floor: float = MIN_DEV_COVERAGE) -> str:
    """``cov`` as a per-year table and one fraction, as a string. Prints nothing (this module is pure).

    The last two lines are the point of the whole phase: the number, whether it clears the floor,
    and the reminder that it is an upper bound.
    """
    lines = [
        f"panel coverage {cov.start} .. {cov.end}: {len(cov.dates)} monthly samples, "
        f"{cov.symbols} symbols in the panel",
        f"  rankable: non-empty observations AND a filing within {cov.max_stale_days} days; "
        f"covered: at least {cov.top} rankable symbols",
        "  year    covered/sampled    most rankable",
    ]
    for row in cov.by_year():
        lines.append(f"  {row.year}    {row.covered:>5}/{row.sampled:<5}      {row.most_rankable:>8}")
    verdict = "at or above" if cov.fraction >= floor else "BELOW"
    lines.append(
        f"  covered {cov.covered_dates} of {len(cov.dates)} sampled dates = {cov.fraction:.4f} "
        f"({verdict} the {floor:.2f} floor)"
    )
    lines.append(
        "  an upper bound: index membership, min_price and min_dollar_volume can only remove symbols"
    )
    return "\n".join(lines)
```

**Impact:** a new pure module. Nothing imports it yet, so the tree still builds and the full
suite still passes after this step alone — `test_strategy_purity.py` picks it up by glob and must
stay green.

---

### Step 2: Export it from the package

**File:** `engine/src/seer_engine/fundamentals/__init__.py:18` (the import block) and `:66`
(`__all__`)
**Change:** add a `coverage` import block **before** the existing `ladder` block (alphabetical,
matching the file's existing order), and the new names into `__all__`, also alphabetically.
`ruff` here selects only `E9` and `F`, so ordering is a convention, not a lint rule — but see the
design note: `coverage.py` imports `seer_engine.fundamentals.panel` as a *submodule*, which
resolves correctly even while this `__init__` is only partly executed.

**Code** — insert immediately after the module docstring's closing `"""` on line 16 and the blank
line 17, i.e. as the first import block:

```python
from seer_engine.fundamentals.coverage import (
    DEFAULT_TOP,
    MIN_DEV_COVERAGE,
    WINDOW_END,
    WINDOW_START,
    Coverage,
    CoverageError,
    YearCoverage,
    default_max_stale_days,
    format_report,
    is_rankable,
    measure,
    monthly_dates,
    rankable_count,
    rankable_symbols,
)
```

**Code** — the `__all__` list becomes exactly this (the fourteen new entries merged in
alphabetically; every pre-existing entry is unchanged and none is removed):

```python
__all__ = [
    "ASSETS",
    "CONCEPTS",
    "COST_OF_REVENUE",
    "DEFAULT_TOP",
    "DILUTED_EPS",
    "DILUTED_SHARES",
    "DURATION",
    "DURATION_CONCEPTS",
    "EMPTY_PANEL",
    "EQUITY",
    "FACT_COLUMNS",
    "GROSS_PROFIT",
    "GROSS_PROFIT_DERIVED",
    "GROSS_PROFIT_NONE",
    "GROSS_PROFIT_REPORTED",
    "INSTANT",
    "INSTANT_CONCEPTS",
    "KIND_ANNUAL",
    "KIND_INSTANT",
    "KIND_QUARTER",
    "LADDER",
    "LADDER_TAGS",
    "MIN_DEV_COVERAGE",
    "NET_INCOME",
    "OPERATING_CASH_FLOW",
    "OPERATING_INCOME",
    "REVENUE",
    "SHARES_OUTSTANDING",
    "WINDOW_END",
    "WINDOW_START",
    "ConceptSpec",
    "Coverage",
    "CoverageError",
    "Fact",
    "FundamentalPanel",
    "FundamentalsError",
    "LadderError",
    "Obs",
    "Snapshot",
    "SymbolFundamentals",
    "YearCoverage",
    "accrual_ratio",
    "book_value_per_share",
    "concepts_for",
    "default_max_stale_days",
    "fact_from_row",
    "facts_from_rows",
    "format_report",
    "gross_profitability",
    "is_rankable",
    "measure",
    "monthly_dates",
    "rankable_count",
    "rankable_symbols",
    "return_on_assets",
    "return_on_equity",
    "spec",
]
```

**Change (docstring):** add one bullet to the module docstring's list, between the `ladder` bullet
(`:7`) and the `panel` bullet (`:9`) — replace the `ladder` bullet block's trailing line so the
list reads:

```python
* ``ladder`` -- which ``us-gaap``/``dei`` tags carry each metric, in preference order, and the
  measured coverage behind that list.
* ``coverage`` -- can the panel rank? The dev-window coverage measure, its ``MIN_DEV_COVERAGE``
  floor, and the ``Snapshot.observations`` emptiness test that a non-None ``as_of`` is not.
* ``panel`` -- ``Fact``, the point-in-time selection rule (``filed <= t``, never ``period_end``),
  ``Snapshot``, and ``FundamentalPanel``, which is what ``Market.fundamentals`` holds.
```

**Impact:** `from seer_engine.fundamentals import coverage` and the flat names both work. The
package attribute `seer_engine.fundamentals.coverage` is set by this import, which is what
`commands/research_store.py` and `lab/runner.py` rely on.

---

### Step 3: `research_store --coverage`

**File:** `engine/src/seer_engine/commands/research_store.py`

**3a. Imports — line 34.** Replace:

```python
from seer_engine.fundamentals import Fact
```

with:

```python
from seer_engine.fundamentals import Fact, coverage
```

**3b. Docstring — lines 12–21.** Replace the usage block and the paragraph after it with:

```python
    python -m seer_engine research_store [--store DIR] [--batch-size N] [--verify]
                                        [--coverage] [--with-fundamentals]

``--verify`` loads an existing store only (no network). ``--coverage`` also loads an existing
store only and measures what its fundamental panel can rank across the dev window
(``fundamentals.coverage``): a per-year table and one fraction, printed whatever the number is.
It needs no network and no database, and it wins when both it and ``--verify`` are given. It
exits 0 when the fraction is at or above ``coverage.MIN_DEV_COVERAGE`` and 1 when it is below --
the same convention ``--verify`` uses for a failed check. ``--with-fundamentals`` additionally
reads the SEC point-in-time fact panel from the database (``DATABASE_URL_UNPOOLED``, the one
place in this command that needs it) and writes it as the store's optional fifth file, so
``lab run`` sees a non-empty ``Market.fundamentals``; without the flag the store carries no
fundamentals and the lab ranks on bars alone, silently. The global ``--dry-run`` builds into a
temporary directory and discards it. Exit codes: 0 ok; 1 build failed, a check failed or
coverage is below the floor; 2 the store is missing or invalid.
```

**3c. The flag — insert after line 71 (after the `--verify` block, before
`--with-fundamentals`).** Phase 4 runs after this phase and appends its own flag *after*
`--with-fundamentals`; this one takes the slot directly after `--verify`, so the two edits do
not overlap even though they are now serialised.

```python
    p.add_argument(
        "--coverage",
        action="store_true",
        help=(
            "load an existing store and measure what its fundamental panel can rank over the "
            "dev window (no network, no database); exit 1 when it is below the lab's floor"
        ),
    )
```

**3d. Dispatch — `run`, lines 82–97.** Replace the function with the body below. This is the
whole-function form phase 4 will quote and extend, so it is settled here: `--coverage` is tested
**first**, so that it wins when both it and `--verify` are given (the Interface Contract's rule,
and the reconciled precedence — see the index's `## Decisions`, row C1).

```python
def run(args: argparse.Namespace) -> int:
    store = Path(args.store)
    if getattr(args, "coverage", False):
        return _coverage(store)
    if args.verify:
        return _verify(store, note="")
    facts = _read_facts() if getattr(args, "with_fundamentals", False) else None
    if getattr(args, "dry_run", False):
        with tempfile.TemporaryDirectory(prefix="seer-research-") as tmp:
            target = Path(tmp) / "store"
            code = _build(target, int(args.batch_size), facts)
            if code != 0:
                return code
            return _verify(target, note=" (dry run: built in a temporary directory and discarded)")
    code = _build(store, int(args.batch_size), facts)
    if code != 0:
        return code
    return _verify(store, note="")
```

**3e. The handler — insert after `_verify` (after line 128), before `format_summary`.**

```python
def _coverage(store: Path) -> int:
    """``--coverage``: load the store and measure what its panel can rank. No network, no database.

    Deliberately does **not** run ``research.run_checks``: this mode answers one question and
    answers it cheaply. It is the replacement for the copy-paste snippet in
    ``docs/runbooks/data-pipeline.md``, and the reason M0005's successor cannot be run blind.

    Exit 0 when the measured fraction is at or above ``coverage.MIN_DEV_COVERAGE``, 1 when it is
    below (``--verify``'s convention for a failed check), 2 when the store will not load. The
    number is printed either way: this command reports, it never hides.
    """
    try:
        data = research.load_store(store)
    except ValueError as exc:
        log.error("research_store: %s", exc)
        return 2
    cov = coverage.measure(data.market.fundamentals)
    print(f"research store {store}")
    print(f"  fingerprint: {data.fingerprint}")
    print(coverage.format_report(cov))
    return 0 if cov.fraction >= coverage.MIN_DEV_COVERAGE else 1
```

**Impact:** a new read-only mode. `_build`, `_read_facts`, `_verify` and `format_summary` are
untouched, so `test_research_store.py` keeps passing unchanged, including
`test_no_neon_and_no_database_url_needed` (which AST-scans this file for `seer_engine.db` and
`psycopg` — neither name is introduced).

---

### Step 4: The post-load refusal in the runner

**File:** `engine/src/seer_engine/lab/runner.py`

**4a. Imports — lines 23–28.** The import block becomes:

```python
from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.dev import DevRow
from seer_engine.commands.backtest_dev import daily_moments, month_end_curve, registry_problem
from seer_engine.fundamentals import coverage
from seer_engine.lab import store
from seer_engine.lab.method import Method, config_digest, config_text, source_sha
from seer_engine.strategies.allocator import MarketAware
```

**4b. The two new functions — insert after `preflight` (after line 68, before `_dsr`).**

```python
def market_aware_candidates(method: Method) -> tuple[str, ...]:
    """The ids of ``method``'s candidates whose allocator reads the whole ``Market``, in order.

    ``strategies.allocator.MarketAware`` is ``runtime_checkable``, so this tests for a
    ``prepare_market`` attribute and nothing more -- which is exactly the dispatch
    ``allocator.prepare_for`` makes, and therefore exactly the set of candidates whose ranking
    can see ``Market.fundamentals``. ``f_fundamental.FUNDAMENTAL`` satisfies it structurally; a
    price-only allocator such as ``f_index.TIMING`` or ``f_rotation.ROTATION`` does not, and a
    bracket ``Strategy`` does not either.
    """
    return tuple(c.id for c in method.candidates if isinstance(c.allocator, MarketAware))


def preflight_data(
    data: research.ResearchData,
    method: Method,
    *,
    min_coverage: float = coverage.MIN_DEV_COVERAGE,
) -> coverage.Coverage | None:
    """The refusal that can only be made once the research store is loaded (``store.LabError``).

    ``preflight`` runs *before* ``research.load_store``, so it cannot see the panel. This is the
    second checkpoint and it exists for one reason: M0005 was spent on a store whose panel held
    no fact filed before 2013, over a dev window that opens in 1996, and nothing refused it.

    Returns None for a method with no ``MarketAware`` candidate -- a price-only method ranks on
    bars and must stay runnable against a store with no panel at all. Otherwise it returns the
    measurement, so the caller can print it whether or not it cleared the floor, and raises
    ``store.LabError`` when the measured fraction is below ``min_coverage``.

    ``min_coverage`` is lowered by ``lab run --allow-coverage F``. That is an acknowledgement,
    not a silencer: the caller prints the table either way.
    """
    aware = market_aware_candidates(method)
    if not aware:
        return None
    cov = coverage.measure(data.market.fundamentals)
    if cov.fraction >= min_coverage:
        return cov
    raise store.LabError(
        f"{method.id}: {', '.join(aware)} rank on Market.fundamentals, and this store's panel "
        f"can rank at least {cov.top} symbols on only {cov.fraction:.1%} of the dev window "
        f"({cov.covered_dates} of {len(cov.dates)} monthly samples, {cov.start}..{cov.end}), "
        f"below the {min_coverage:.0%} floor. Running it would spend the method id on a "
        f"measurement of the panel rather than of the hypothesis.\n"
        f"{coverage.format_report(cov, floor=min_coverage)}\n"
        "Refresh the store's fundamental panel, or re-run with --allow-coverage F to record the "
        "trials against this panel knowingly."
    )
```

**Impact:** `preflight`, `run_method`, `trial_rows` and `_dsr` are untouched. `run_method` does
**not** call `preflight_data` — the call site is `commands/lab._run`, so a direct
`runner.run_method(...)` from a test (which is how every existing `test_lab_runner.py` test calls
it) keeps working against the `smoke_data` market with its empty panel.

---

### Step 5: Wire it into `lab run`, with `--allow-coverage`

**File:** `engine/src/seer_engine/commands/lab.py`

**5a. Imports — lines 32–35.** The block becomes:

```python
from seer_engine import config, research
from seer_engine.backtest import dev
from seer_engine.backtest.metrics import fmt_num, fmt_pct, fmt_pf, fmt_signed_pct
from seer_engine.fundamentals import coverage
from seer_engine.lab import store
```

**5b. The argument type — insert after `HELP` (after line 39), before `add_arguments`.**

```python
def _coverage_floor(text: str) -> float:
    try:
        value = float(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from exc
    if not 0.0 <= value <= 1.0:
        raise argparse.ArgumentTypeError(f"must be a fraction between 0 and 1, got {value}")
    return value
```

**5c. The `run` subparser — lines 50–52.** Replace with:

```python
    s = sub.add_parser("run", help="run a committed method on the dev window")
    s.add_argument("method")
    s.add_argument("--store", type=Path, default=Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR))
    s.add_argument(
        "--allow-coverage",
        type=_coverage_floor,
        default=coverage.MIN_DEV_COVERAGE,
        metavar="F",
        help=(
            f"lower the dev-window panel-coverage floor from {coverage.MIN_DEV_COVERAGE:.2f} to F "
            "(0..1) for this run. An acknowledgement, not a silencer: the measured fraction and "
            "the per-year table are printed either way. Only methods with a MarketAware "
            "allocator are gated at all"
        ),
    )
```

**5d. The call — `_run`, between `load_store` and `run_method`.** Insert after line 217 (the
`log.info("research store %s loaded ...")` call), before the `ran = runner.run_method(...)` line.
`_run` becomes:

```python
def _run(conn, args) -> int:
    from seer_engine.lab import runner
    from seer_engine.lab.method import discover

    methods = discover()
    if args.method not in methods:
        raise store.LabError(f"no method file for {args.method} in seer_engine/lab/methods/")
    method, path = methods[args.method]
    runner.preflight(conn, method, path)
    if research.DEV_END != dev.DEV_END:
        raise store.LabError("research.DEV_END differs from dev.DEV_END; refusing to run")
    t0 = time.perf_counter()
    try:
        data = research.load_store(Path(args.store))
    except FileNotFoundError as e:
        raise store.LabError(
            f"research store {args.store} is missing {e.filename or e}; build it with "
            "`python -m seer_engine research_store`"
        ) from e
    log.info("research store %s loaded (%.1fs)", data.fingerprint[:12], time.perf_counter() - t0)
    # The second checkpoint: runner.preflight ran before the store existed and could not see the
    # panel. Nothing here is reached for a price-only method.
    floor = float(getattr(args, "allow_coverage", coverage.MIN_DEV_COVERAGE))
    cov = runner.preflight_data(data, method, min_coverage=floor)
    if cov is not None:
        print(coverage.format_report(cov, floor=floor))
        if floor < coverage.MIN_DEV_COVERAGE:
            print(
                f"--allow-coverage {floor:.2f}: {method.id} runs against a panel that can rank on "
                f"{cov.fraction:.1%} of the dev window, below the "
                f"{coverage.MIN_DEV_COVERAGE:.0%} floor. These trials measure the panel, not the "
                "hypothesis, and the method id is spent either way."
            )
    ran = runner.run_method(conn, method, path, data, git_sha=runner.git_head(config.REPO_ROOT))
    status = store.get_method(conn, method.id)["status"]
    log.info("%s: %d trial(s) recorded, status %s (%.1fs)", method.id, len(ran), status, time.perf_counter() - t0)
    _show(conn, argparse.Namespace(method=method.id))
    print(f"\nLab N (dev trials) is now {store.dev_trial_count(conn)}; test-window looks used: {store.test_looks(conn)}")
    return 0
```

**5e. Docstring — line 6.** Replace the `lab run` usage line:

```python
    lab run M0007 [--store DIR]     run a committed method on the dev window, record its trials
```

with:

```python
    lab run M0007 [--store DIR] [--allow-coverage F]
                                    run a committed method on the dev window, record its trials;
                                    a method with a MarketAware allocator is refused when the
                                    store's fundamental panel covers less than 80% of the window
```

**Impact:** `store.LabError` is already caught by `run` (line 102) and mapped to exit 2, so the
refusal surfaces as the lab's standard "the rules refuse this" exit code. Every other
subcommand is untouched. No test in the suite drives `cli.main(["lab", "run", ...])`, so nothing
existing changes behaviour.

---

### Step 6: Tests for the measure

**File:** `engine/tests/test_fundamentals_coverage.py` (new file, whole contents)

```python
"""The dev-window coverage measure (``fundamentals/coverage.py``) and the bug it exists to prevent.

No store, no database, no network, no clock: every panel here is built from a handful of
synthetic ``us-gaap:Assets`` facts.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

import seer_engine
from seer_engine.fundamentals import EMPTY_PANEL, Fact, FundamentalPanel, coverage


def fact(symbol: str, filed: date, *, val: float = 1.0e9) -> Fact:
    """One ``us-gaap:Assets`` instant for ``symbol``, filed on (and dated) ``filed``."""
    return Fact(
        symbol=symbol,
        taxonomy="us-gaap",
        tag="Assets",
        unit="USD",
        period_start=None,
        period_end=filed,
        val=val,
        accn=f"0000000000-{filed.year % 100:02d}-{filed.toordinal():06d}",
        form="10-K",
        fy=filed.year,
        fp="FY",
        filed=filed,
    )


def panel_of(symbols, filings) -> FundamentalPanel:
    """A panel in which every symbol filed on every date in ``filings``."""
    return FundamentalPanel.from_facts([fact(s, d) for s in symbols for d in filings])


def names(n: int) -> list[str]:
    return [f"S{i:02d}" for i in range(n)]


ANNUAL = [date(1995, 1, 2) + timedelta(days=365 * k) for k in range(22)]
"""A filing roughly every year from 1995 to 2015: never more than 365 days apart, so a 400-day
staleness window is satisfied on every monthly sample of the dev window."""


# ---- the bug this module exists to prevent -------------------------------------------------


def test_a_snapshot_is_not_coverage():
    """Invariant 9: ``as_of(...) is not None`` is vacuous, and that is what spent M0005."""
    t = date(1996, 1, 2)
    panel = panel_of(names(30), [date(2015, 1, 5)])
    # The M0005 check, in one line. All thirty pass it, in 1996, against 2015 filings.
    assert all(panel.as_of(s, t) is not None for s in panel.names())
    # The honest test. All thirty fail it.
    assert all(panel.as_of(s, t).observations == {} for s in panel.names())
    assert coverage.rankable_symbols(panel, t) == ()
    assert coverage.rankable_count(panel, t) == 0


def test_an_empty_husk_is_not_rankable():
    t = date(1996, 1, 2)
    panel = panel_of(["AAA"], [date(2015, 1, 5)])
    assert coverage.is_rankable(panel.as_of("AAA", t), t, 400) is False
    assert coverage.is_rankable(None, t, 400) is False


# ---- the staleness gate ---------------------------------------------------------------------


def test_rankable_needs_a_filing_inside_the_staleness_window():
    t = date(2015, 6, 1)
    stale = coverage.default_max_stale_days()
    panel = FundamentalPanel.from_facts(
        [
            fact("FRESH", t - timedelta(days=stale)),
            fact("STALE", t - timedelta(days=stale + 1)),
            fact("FUTURE", t + timedelta(days=1)),
        ]
    )
    assert coverage.rankable_symbols(panel, t) == ("FRESH",)
    assert coverage.rankable_symbols(panel, t, max_stale_days=stale + 1) == ("FRESH", "STALE")


def test_the_staleness_window_is_f_fundamentals_own():
    from seer_engine.strategies.f_fundamental import FundamentalParams

    assert coverage.default_max_stale_days() == FundamentalParams(rank="value").max_stale_days


# ---- the window and the sample --------------------------------------------------------------


def test_the_sampled_window_is_the_dev_window():
    """``WINDOW_START``/``WINDOW_END`` are duplicated constants; this is what pins them."""
    from seer_engine import research
    from seer_engine.backtest import dev

    assert coverage.WINDOW_START == dev.MEMBERSHIP_START == research.MEMBERSHIP_START
    assert coverage.WINDOW_END == dev.DEV_END == research.DEV_END


def test_the_monthly_sample_is_one_date_per_calendar_month():
    sample = coverage.monthly_dates()
    assert len(sample) == 238
    assert sample[0] == date(1996, 1, 2)
    assert sample[-1] == date(2015, 10, 2)
    assert len({(d.year, d.month) for d in sample}) == len(sample)
    assert all(coverage.WINDOW_START <= d <= coverage.WINDOW_END for d in sample)


def test_a_short_month_contributes_its_last_day():
    assert coverage.monthly_dates(date(2015, 1, 31), date(2015, 4, 30)) == (
        date(2015, 1, 31),
        date(2015, 2, 28),
        date(2015, 3, 31),
        date(2015, 4, 30),
    )


def test_monthly_dates_refuses_a_backwards_window():
    with pytest.raises(coverage.CoverageError, match="before start"):
        coverage.monthly_dates(date(2015, 2, 1), date(2015, 1, 1))


# ---- the measure ----------------------------------------------------------------------------


def test_a_panel_whose_facts_all_postdate_the_window_covers_nothing():
    panel = panel_of(names(50), [date(2015, 11, 2)])
    cov = coverage.measure(panel)
    assert cov.symbols == 50
    assert cov.counts == (0,) * len(cov.dates)
    assert cov.covered_dates == 0
    assert cov.fraction == 0.0
    assert [r.most_rankable for r in cov.by_year()] == [0] * 20


def test_a_panel_filed_through_the_window_covers_all_of_it():
    panel = panel_of(names(25), ANNUAL)
    cov = coverage.measure(panel)
    assert min(cov.counts) == 25
    assert cov.covered_dates == len(cov.dates)
    assert cov.fraction == 1.0
    assert cov.start == date(1996, 1, 2) and cov.end == date(2015, 10, 2)


def test_covered_means_at_least_top_rankable():
    panel = panel_of(names(19), ANNUAL)
    assert coverage.measure(panel).fraction == 0.0  # 19 < DEFAULT_TOP
    assert coverage.measure(panel, top=19).fraction == 1.0


def test_an_empty_panel_measures_zero_and_does_not_raise():
    cov = coverage.measure(EMPTY_PANEL)
    assert cov.symbols == 0
    assert cov.fraction == 0.0
    assert len(cov.dates) == 238


def test_the_per_year_table_locates_the_coverage():
    panel = panel_of(names(50), [date(2015, 3, 2)])
    cov = coverage.measure(panel)
    rows = cov.by_year()
    assert [r.year for r in rows] == list(range(1996, 2016))
    assert all(r.sampled == 12 for r in rows if r.year < 2015)
    assert all(r.covered == 0 and r.most_rankable == 0 for r in rows if r.year < 2015)
    last = rows[-1]
    assert (last.year, last.sampled, last.covered, last.most_rankable) == (2015, 10, 8, 50)
    assert cov.covered_dates == 8


def test_an_explicit_sample_overrides_the_monthly_one():
    panel = panel_of(names(25), [date(2015, 3, 2)])
    cov = coverage.measure(panel, dates=(date(2015, 1, 2), date(2015, 4, 2)))
    assert cov.counts == (0, 25)
    assert cov.fraction == 0.5


def test_measure_refuses_what_it_cannot_measure():
    with pytest.raises(coverage.CoverageError, match="FundamentalPanel"):
        coverage.measure(object())
    with pytest.raises(coverage.CoverageError, match="top"):
        coverage.measure(EMPTY_PANEL, top=0)
    with pytest.raises(coverage.CoverageError, match="at least one sampled date"):
        coverage.measure(EMPTY_PANEL, dates=())
    with pytest.raises(coverage.CoverageError, match="dates\\[1\\]"):
        coverage.measure(EMPTY_PANEL, dates=(date(2015, 1, 2), "2015-02-02"))
    with pytest.raises(coverage.CoverageError, match="t must be a date"):
        coverage.rankable_symbols(EMPTY_PANEL, "2015-01-02")


# ---- the report ------------------------------------------------------------------------------


def test_the_report_names_the_number_and_the_floor():
    cov = coverage.measure(panel_of(names(50), [date(2015, 3, 2)]))
    text = coverage.format_report(cov)
    assert "BELOW" in text
    assert "0.80" in text
    assert f"{cov.fraction:.4f}" in text
    assert "upper bound" in text
    for year in (1996, 2005, 2015):
        assert f"  {year}  " in text


def test_a_covered_panel_reports_no_refusal():
    cov = coverage.measure(panel_of(names(25), ANNUAL))
    text = coverage.format_report(cov)
    assert "BELOW" not in text
    assert "at or above" in text


def test_a_lowered_floor_changes_only_the_verdict():
    cov = coverage.measure(panel_of(names(50), [date(2015, 3, 2)]))
    assert "BELOW" not in coverage.format_report(cov, floor=0.0)
    assert f"{cov.fraction:.4f}" in coverage.format_report(cov, floor=0.0)


# ---- purity and the import cycle --------------------------------------------------------------


def test_the_measure_is_covered_by_the_purity_glob():
    from test_strategy_purity import _module_name, _pure_sources

    assert "seer_engine.fundamentals.coverage" in {_module_name(p) for p in _pure_sources()}


def test_no_import_cycle_whichever_module_is_imported_first():
    """``coverage`` defers its ``f_fundamental`` import; ``f_fundamental`` imports this package
    at module scope. A module-scope import in ``coverage.py`` makes one of these orders fail."""
    env = dict(os.environ)
    root = Path(seer_engine.__file__).resolve().parent.parent
    env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
    expected = str(coverage.default_max_stale_days())
    for first in (
        "seer_engine.strategies.f_fundamental",
        "seer_engine.fundamentals",
        "seer_engine.fundamentals.coverage",
        "seer_engine.backtest.market",
        "seer_engine.backtest.dev",
    ):
        out = subprocess.run(
            [
                sys.executable,
                "-c",
                f"import {first}\n"
                "from seer_engine.fundamentals import coverage\n"
                "import sys; sys.stdout.write(str(coverage.default_max_stale_days()))\n",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert out.returncode == 0, f"{first} imported first: {out.stderr}"
        assert out.stdout.strip() == expected
```

**Impact:** a new test file. `from test_strategy_purity import ...` works because `engine/tests`
is on `sys.path` for the suite — `test_lab_runner.py:10` already does `from labkit import
smoke_data`.

---

### Step 7: Tests for the refusal

**File:** `engine/tests/test_lab_runner.py`

**7a. Imports — lines 3–18.** The header becomes (three new imports, one new stdlib import):

```python
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from labkit import smoke_data

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import Market
from seer_engine.fundamentals import Fact, FundamentalPanel, coverage
from seer_engine.lab import runner, store
from seer_engine.lab.method import Method, config_digest
from seer_engine.lab.seed import seed
from seer_engine.sim.rules import DAILY_SWITCH, MONTHLY_HOLD
from seer_engine.strategies.f_fundamental import FUNDAMENTAL, FundamentalParams
from seer_engine.strategies.f_index import TIMING, TimingParams
from seer_engine.strategies.f_rotation import ROTATION, RotationParams
```

**7b. New helpers and tests — append after line 116 (the end of the file).**

```python
# ---- the post-load coverage refusal (phase 1 of fundamental-panel-coverage) -------------------


def _fund_cand(cid: str, family: str, rank: str = "value") -> Candidate:
    """One ``FUNDAMENTAL`` variant: the only allocator in the tree that is ``MarketAware``."""
    return Candidate(
        id=cid, family=family, rules=MONTHLY_HOLD, allocator=FUNDAMENTAL,
        params=FundamentalParams(rank=rank, top=20),
        rationale="fundamental variant for the coverage gate", added=date(2026, 10, 5),
        owner_inputs=(),
    )


def _dense_panel(n: int = 25) -> FundamentalPanel:
    """A panel that can rank ``n`` symbols on every monthly sample of the dev window."""
    filings = [date(1995, 1, 2) + timedelta(days=365 * k) for k in range(22)]
    facts = [
        Fact(symbol=f"S{i:02d}", taxonomy="us-gaap", tag="Assets", unit="USD", period_start=None,
             period_end=d, val=1.0e9 + i, accn=f"0000000000-{k:02d}-{i:06d}", form="10-K",
             fy=d.year, fp="FY", filed=d)
        for i in range(n)
        for k, d in enumerate(filings)
    ]
    return FundamentalPanel.from_facts(facts)


def _with_panel(data, panel: FundamentalPanel):
    """``data`` with ``panel`` on its market. The module-scoped ``data`` fixture is not mutated."""
    market = Market(
        history=data.market.history,
        membership=data.market.membership,
        fx=data.market.fx,
        fundamentals=panel,
    )
    return dataclasses.replace(data, market=market)


def test_only_a_market_aware_allocator_is_gated():
    m = _method("M0010", cands=(_fund_cand("M0010-VAL", "M0010"), _cand("M0010-T", "M0010")))
    assert runner.market_aware_candidates(m) == ("M0010-VAL",)
    assert runner.market_aware_candidates(_method()) == ()


def test_a_price_only_method_is_never_refused(data):
    """M0001 and M0004 rank on bars; the smoke market carries EMPTY_PANEL and must stay runnable."""
    assert len(data.market.fundamentals) == 0
    assert runner.preflight_data(data, _method()) is None


def test_a_market_aware_method_is_refused_against_a_panel_that_cannot_rank(data):
    m = _method("M0011", cands=(_fund_cand("M0011-VAL", "M0011"),))
    with pytest.raises(store.LabError, match="M0011-VAL") as exc:
        runner.preflight_data(data, m)
    text = str(exc.value)
    assert "0.0%" in text
    assert "--allow-coverage" in text
    assert "BELOW" in text  # the per-year table travels with the refusal


def test_allow_coverage_lifts_the_refusal_and_still_measures(data):
    m = _method("M0012", cands=(_fund_cand("M0012-VAL", "M0012"),))
    cov = runner.preflight_data(data, m, min_coverage=0.0)
    assert cov is not None
    assert cov.fraction == 0.0
    assert cov.top == coverage.DEFAULT_TOP
    assert cov.max_stale_days == coverage.default_max_stale_days()
    assert "BELOW" in coverage.format_report(cov, floor=coverage.MIN_DEV_COVERAGE)


def test_a_market_aware_method_runs_when_the_panel_can_rank(data):
    rich = _with_panel(data, _dense_panel())
    m = _method("M0013", cands=(_fund_cand("M0013-VAL", "M0013"),))
    cov = runner.preflight_data(rich, m)
    assert cov is not None
    assert cov.fraction == 1.0
    assert cov.symbols == 25


def test_the_gate_measures_content_not_presence(data):
    """A panel of 50 symbols whose every fact is filed after the dev window covers nothing."""
    late = FundamentalPanel.from_facts([
        Fact(symbol=f"L{i:02d}", taxonomy="us-gaap", tag="Assets", unit="USD", period_start=None,
             period_end=date(2015, 11, 2), val=1.0e9, accn=f"0000000000-15-{i:06d}", form="10-K",
             fy=2015, fp="FY", filed=date(2015, 11, 2))
        for i in range(50)
    ])
    thin = _with_panel(data, late)
    assert len(thin.market.fundamentals) == 50  # the panel is not empty
    m = _method("M0014", cands=(_fund_cand("M0014-VAL", "M0014"),))
    with pytest.raises(store.LabError, match="0.0%"):
        runner.preflight_data(thin, m)


def test_run_method_itself_does_not_gate(conn, data):
    """The gate lives in ``commands/lab._run``; ``run_method`` stays callable from a test."""
    ran = runner.run_method(conn, _method(), Path(__file__), data, git_sha="x", require_commit=False)
    assert len(ran) == 2
```

**7c.** `_with_panel` uses `dataclasses.replace`, so add `import dataclasses` to the stdlib
import block in 7a (between `from __future__ import annotations` and `import json`):

```python
import dataclasses
import json
```

`research.ResearchData` is a plain frozen dataclass with no `init=False` fields, so `replace`
is safe on it; `Market` has two, which is why `_with_panel` constructs a `Market` explicitly
instead of replacing one.

**Impact:** additions only. Every existing test in the file is unchanged, including
`test_run_records_trials_with_lab_wide_n`, which keeps calling `runner.run_method` directly
against the empty-panel smoke market.

---

## Verification

Run the **Runtime preamble** first; every command below assumes `$SEER_PY`, `$PYTHONPATH` and
`cd "$SEER_WT"`.

**Build (import check, and the purity gate first — it is the one most likely to fail):**

```bash
"$SEER_PY" -m ruff check engine/src engine/tests
"$SEER_PY" -m pytest engine/tests/test_strategy_purity.py -q
"$SEER_PY" -c "import seer_engine.strategies.f_fundamental; from seer_engine.fundamentals import coverage; print(coverage.default_max_stale_days(), len(coverage.monthly_dates()))"
```

The last line must print `400 238`.

**Tests:**

```bash
"$SEER_PY" -m pytest engine/tests/test_fundamentals_coverage.py engine/tests/test_lab_runner.py engine/tests/test_research_store.py -q
"$SEER_PY" -m pytest engine/tests -q
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres "$SEER_PY" -m pytest engine/tests -q
```

**The test delta, not an absolute.** This phase adds **27** collected tests — 20 in
`engine/tests/test_fundamentals_coverage.py` and 7 in `engine/tests/test_lab_runner.py`, counted
from the code blocks above. Against the `2dad9ff` baseline of 2216 passed / 332 skipped that is
**2243 passed, 332 skipped** *when this phase runs first*. Report the delta, not the absolute:
phases land in a swarm and the inherited count depends on what has already merged. The rule that
binds is invariant 1 — the passing count may only go up, and no test may change its result.
With `PG_TEST_URL` set the 332 skips become passes.

**CLI surface (no store needed):**

```bash
"$SEER_PY" -m seer_engine research_store --help | grep -A2 -- --coverage
"$SEER_PY" -m seer_engine lab run --help | grep -A3 -- --allow-coverage
"$SEER_PY" -m seer_engine research_store --coverage --store /tmp/nope; echo "exit $?"   # must be 2
```

**Manual check (read-only, against the real store).** The store exists only in the main checkout
(`/home/miftah/seer/engine/.research/`); the worktree has none. With the preamble exported, the
worktree's code reads the main checkout's store when `--store` names it explicitly — so stay in
`$SEER_WT` and pass the path. Do **not** `cd` to the main checkout: that would put main's
`engine/data/` back in reach for `load_store`'s membership read.

```bash
"$SEER_PY" -m seer_engine research_store --coverage --store /home/miftah/seer/engine/.research
echo "exit $?"
```

Expect: a table whose 1996–2014 rows read `0/12` with `most rankable` 0, a 2015 row that is
non-zero, a fraction well below `0.80`, and **exit 1**. Measured during planning on 2026-10-05
with exactly the algorithm above: 780 panel symbols, 238 monthly samples, 2.7 s, 2015 covering
9 of its 10 samples with a best date of 519 rankable symbols, **fraction 0.0378**.

This phase's **monthly, top=20, max_stale_days=400** sample is the set's one definition of
coverage, and the index's phase-1 exit criterion has been corrected to `0.0378` to match. Two
older figures are retired and must not be quoted as this measure: the analysis's `0.025` was a
**semiannual** sample (1 of 40 dates), and the decision doc §4's `4%` is a **span estimate**
(9 months of 19.8 years). See **Handoffs** and the index's `## Decisions`, row C4a.

Do **not** run `lab run`.

**Exit criteria:**

1. `engine/src/seer_engine/fundamentals/coverage.py` exists, passes `test_strategy_purity.py`,
   and contains the string `as_of` only inside `is_rankable`/`rankable_symbols` and inside the
   docstrings that name the anti-pattern. `grep -n "is not None" engine/src/seer_engine/fundamentals/coverage.py`
   returns only the `snapshot is None` guard and the docstring line.
2. `python -m seer_engine research_store --coverage --store /home/miftah/seer/engine/.research`
   prints the per-year table and one fraction — **0.0378** on the 2026-10-05 store under this
   phase's monthly/top=20/400-day definition — and exits 1.
3. `runner.preflight_data` raises `store.LabError` for a `FUNDAMENTAL` method on an empty or
   thin panel, returns `None` for a price-only method, and returns a `Coverage` when the panel
   covers the window or when `min_coverage` is lowered.
4. `"$SEER_PY" -m pytest engine/tests -q` is green, the passing count has only gone up, and the
   phase reports its delta (+27) rather than an absolute.
5. `git status` shows exactly the seven files in the **Files** table and nothing else — no
   `engine/.research/`, no database change, no `docs/` change.

## Handoffs

- **Phase 4, `commands/research_store.py` (shared file) — RECONCILED into the DAG.** Phase 4
  now `Depends on: Phase 1`. This phase inserts exactly two blocks: the `--coverage` argument
  **immediately after the `--verify` block** (today's lines 67–71) and the `_coverage` function
  **immediately after `_verify`** (today's line 128), plus one word on the import line 34 and the
  docstring rewrite of lines 12–21. `run`'s dispatch is rewritten here as a whole function
  (step 3d). Phase 4 appends its flag **after `--with-fundamentals`**, its `_run_refresh` /
  `_refresh` **after `_build`** (before `_verify`, so this phase's `_coverage` is untouched), and
  its branch into **this** `run()` body, which phase 4's plan now quotes verbatim.
- **Phase 5, the reported number — RECONCILED.** The index's phase-1 exit criterion has been
  corrected from `~0.025` to **0.0378** and now names the sampling definition. `0.025` was the
  analysis's semiannual figure and `4%` is the decision doc's span estimate; neither is this
  measure. Phase 5 reports whatever `--coverage` prints after phases 2–4 land, and quotes it as
  an **upper bound** (see the next bullet).
- **Phase 5, `m0005_fundamental_factors.py`.** Its "READ THIS BEFORE RUNNING" preamble still
  points at a `python -c` one-liner over `manifest.json`. After this phase the honest command is
  `python -m seer_engine research_store --coverage`, and `lab run` refuses on its own. Phase 5
  owns that docstring; this phase does not touch it.
- **Phase 5, the runbook.** `docs/runbooks/data-pipeline.md:208-232`'s snippet is now redundant.
  Phase 5 replaces it with the command.
- **Phase 5, the words "upper bound".** The measure reads no bars, so it applies neither index
  membership on the date nor `min_price`/`min_dollar_volume`; every one of those can only remove
  symbols. The number is therefore an **upper bound**, and `format_report`'s last line says so in
  the output phase 5 pastes. Phase 5 must carry those words into its own prose wherever it quotes
  the number, so the set cannot overstate its own result (index `## Decisions`, row C8).
- **Not done, deliberately.** The measure reads no bars, so it applies neither index membership
  nor `min_price`/`min_dollar_volume`, and is therefore an upper bound. Making it exact would
  require a `Market`, which would make it impure and would make `lab run` pay for a second pass
  over the history. If a later phase ever wants the exact number, it belongs in `backtest/`, not
  here, and it is out of scope for this plan set.
- **Not done, deliberately.** `MIN_DEV_COVERAGE` gates `lab run` only. `backtest_dev` and the
  paper path are untouched; a paper run against a thin panel is §6.1's problem and landed in
  `2dad9ff`.

## Rollback

Every file in this phase is new or purely additive, and nothing outside git is written.

```bash
cd "$SEER_WT"
git revert --no-edit <this phase's commit>
```

Or, before the commit exists:

```bash
rm engine/src/seer_engine/fundamentals/coverage.py engine/tests/test_fundamentals_coverage.py
git checkout -- engine/src/seer_engine/fundamentals/__init__.py \
                engine/src/seer_engine/commands/research_store.py \
                engine/src/seer_engine/commands/lab.py \
                engine/src/seer_engine/lab/runner.py \
                engine/tests/test_lab_runner.py
```

No database row, no store file, no `docs/` file and no method id is touched by this phase, so
there is nothing else to undo.
