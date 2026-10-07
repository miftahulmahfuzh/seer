> Adopted from `DELISTING_STRESS_ROSTER_RULES_PLAN.md` phase 1. Source: `.workflows/plan/delisting-stress-roster-rules/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: The delisting stress harness

**Plan set:** `DELISTING_STRESS_ROSTER_RULES_PLAN.md`
**Analysis:** `20261007-170515-0CU0_code_analyzer.md`
**Satisfies:** R1 — Q1's harness: inject synthetic delistings at the historical rate and solve for the break-even delisting return
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine`, `engine/scripts`, `engine/tests`

---

## Goal

After this phase the tree holds a tested, read-only harness that can inject synthetic delistings
into the dev-window ranking universe at the hazard the research store's own membership records,
re-run any lab candidate against the perturbed market, and solve for the **break-even delisting
return** — the assumed loss at which a roster entry stops beating total-return SPY. It adds three
files and changes none. It records no lab trial, moves no `config_digest`, writes nothing to
`engine/.research`, and spends no test-window look; a test enforces the first of those
structurally by asserting the module imports neither `lab.store` nor `lab.runner`.

Phase 2 runs it and writes down what it found. Phase 1 does not run the Monte Carlo and reports no
number beyond what the smoke run prints.

---

## Measurements taken while planning this phase

Read-only, against the main checkout's store at `/home/miftah/seer/engine/.research`. No trial
recorded, N unmoved at 110, nothing written. These are not estimates; they decided the design.

**P1 — the analysis's M2 hazard reproduces exactly from `membership.intervals` alone.**

```
intervals: 1084
ever 1041  served 519  unserved 522
exits 514  unserved-exits 404  served-exits 110
mean members on 20 mid-year dates 510.2500   window years 19.7864   member_years 10096
all-exit hazard 5.09113%/yr      unserved-exit hazard 4.00158%/yr
recorded unserved.csv 522, symmetric difference against (ever-members − priced): 0
served survivors eligible to be killed: 409
```

M2 printed the unserved rate as `4.001%`; the arithmetic above gives `4.00158%`, which rounds to
`4.002%` at three decimals. Same number, different rounding in the printing. The module computes
`exits / member_years` with `member_years = round(mean_members × window_years)`, which is what
reproduces 5.091% and 404/10096 exactly. **Nothing is hardcoded.**

**P2 — `Membership` rebuild costs 0.011 s.** Measured over 1,084 intervals, three repeats. So the
perturbation can retire a dead symbol from the index as well as from the price history, and the
harness never has to rely on an allocator's internal filtering to drop a dead name.

**P3 — the whole perturbation works end to end, and the engine needs no change.** A prototype of
exactly the design below, run against the real store with `M0022-W-TV16`:

```
base             start=1996-01-03  cagr=0.1168  dd=0.1431  trades=1589  total=7.892  spy_tr=3.514
r=+0.00  deaths=162  draw 0.00s  kill 0.02s  prepare 0.35s  run 7.06s  cagr=0.1034 dd=0.1314 total=6.013
r=-0.50  deaths=162  draw 0.00s  kill 0.02s  prepare 0.33s  run 7.76s  cagr=0.0958 dd=0.1543 total=5.106
r=-1.00  deaths=162  draw 0.00s  kill 0.03s  prepare 0.30s  run 8.88s  cagr=0.0856 dd=0.1778 total=4.082
```

No crash, no exception, the candidate window is unmoved at `1996-01-03`, and the base run
reproduces design §11's book to four decimals. **The force-close path at `book_runner.py:317-326`
→ `sim/book.py:742` absorbs a mid-window disappearance with no engine edit**, exactly as the
analysis predicted. Two things the brief did not anticipate fall out of it and are recorded under
*Handoffs*.

**P4 — all four roster entries reproduce M3 at today's bars, and the store costs ~1 GB.**

```
after load_store                                              peak RSS 942 MB
M0022-W-TV16  prepare 0.35s  run 11.22s  cagr=0.1168 dd=0.1431 trades=1589  peak 1010 MB
M0007-N20-RAW prepare 0.40s  run  5.82s  cagr=0.1505 dd=0.1959 trades=1596  peak 1010 MB
M0002-REL-85  prepare 0.00s  run  5.18s  cagr=0.1256 dd=0.1837 trades=1148  peak 1010 MB
M0008-N30-C07 prepare 0.00s  run  7.33s  cagr=0.1127 dd=0.1997 trades=1223  peak 1010 MB
SPY total-return CAGR over the same window: 7.9151%
```

Every CAGR, drawdown and trade count matches the analysis's M3 table. The run times are 2–4×
M1's 2–3 s because this machine was carrying several swarm sessions at the time (`load_store` took
23–28 s against M1's 11.3 s, the same factor).

**Plan on 5–11 s a run, not 2–3.** M1's 2–3 s was taken on an idle box; this plan set runs as a
swarm, so the loaded number above is the one a phase-2 implementer will actually meet. Phase 2's
budgets have been written against 5–11 s for exactly that reason. The quiet-machine figure is
recorded here only so the two are not confused. Memory:
the store is 942 MB and a prepared panel adds at most ~70 MB, so `--jobs 6` on a fork-based pool
costs roughly 942 MB shared plus ~6 × 150 MB private.

---

## Interface Contract

**Creates (module `seer_engine.delisting`, new file `engine/src/seer_engine/delisting.py`):**

- `delisting.YEAR_DAYS: float` — 365.25
- `delisting.MIN_PRICE: float` — 1e-4, one 4-dp price quantum
- `delisting.WINDOW_START: date` — re-exported `backtest.dev.MEMBERSHIP_START`
- `delisting.WINDOW_END: date` — re-exported `backtest.dev.DEV_END`
- `delisting.Hazard` — frozen dataclass; fields `window_start, window_end, ever_members, served,
  unserved, exits, served_exits, unserved_exits, mean_members, member_years, exits_by_year,
  unrecorded_unserved, unserved_but_priced`; properties `window_years, exit_rate,
  unserved_exit_rate`
- `delisting.Exposure` — frozen dataclass; fields `symbol, spans`; properties `days, years`
- `delisting.Death` — frozen dataclass; fields `symbol, last_bar`
- `delisting.measure_hazard(market, *, unserved=(), window_start=WINDOW_START, window_end=WINDOW_END) -> Hazard`
- `delisting.survivors(market, *, window_start=WINDOW_START, window_end=WINDOW_END) -> tuple[Exposure, ...]`
- `delisting.draw_deaths(market, exposures, hazard_per_year, rng) -> tuple[Death, ...]`
- `delisting.kill(market, deaths, delisting_return, *, decline_sessions=1) -> Market`
- `delisting.stressed(market, exposures, *, hazard_per_year, delisting_return, rng, decline_sessions=1) -> tuple[Market, tuple[Death, ...]]`

**Creates (script `engine/scripts/delisting_stress.py`, new file):**

- `delisting_stress.ROSTER: tuple[tuple[str, str], ...]` — the four quant entries as
  `(roster name, lab candidate id)`
- `delisting_stress.RETURNS: tuple[float, ...]` — the default eight-point grid
- `delisting_stress.Outcome` — frozen dataclass; fields `entry, candidate, delisting_return, seed,
  deaths, start, cagr, max_drawdown, total_return, trades, spy_cagr, beats_spy`; property `edge`
- `delisting_stress.break_even(points) -> float | None` — **`None` is a contract value, not an
  error**: it means the mean edge is still positive at the most negative point on the grid, so
  there is no break-even inside the data and the solver refuses to extrapolate. `_print_entry`
  renders it as `break-even delisting return: NONE on this grid`. Phase 2 must handle it as an
  expected result.
- `delisting_stress.main(argv=None) -> int`
- **The `--csv` schema — phase 1 owns these column names and this order**, and phase 2's extraction
  script is written against them:
  `entry, candidate, delisting_return, seed, deaths, start, cagr, max_drawdown, total_return,
  trades, spy_cagr, edge_points_per_year, beats_spy`. One header row; one row per run; the
  **unstressed reference run per entry is the row whose `delisting_return` and `seed` are empty**.
  `delisting_return` is a fraction at 4 dp (`0.0000`, `-1.0000`); `cagr`, `max_drawdown`,
  `total_return` and `spy_cagr` are fractions at 6 dp (not percentages);
  `edge_points_per_year` is already in **percentage points per year** (`(cagr - spy_cagr) * 100`);
  `beats_spy` is `yes`/`no`. The break-even and the per-seed spread are **not** columns — they are
  solved across runs and printed to stdout only.

**Creates (tests, new file `engine/tests/test_delisting.py`):** no public symbols.

**Deletes:** none.
**Renames:** none.
**Signature changes:** none.
**Requires (from earlier phases):** none — this phase is a wave-1 root.

**Leaves alone (owned by others, or by nobody):**

- `engine/src/seer_engine/backtest/**` and `engine/src/seer_engine/sim/**` — P3 proves no edit is
  needed. **If an implementer finds themselves wanting one, stop and say so loudly rather than
  making it:** an engine edit re-judges 110 recorded trials and is out of this phase's scope.
- `engine/src/seer_engine/lab/**`, `engine/src/seer_engine/paper/**`, `web/**`, every document.
- `engine/.research` and `lab/lab.sqlite` — opened read-only at most; never written.
- `backtest/metrics.py`, `backtest/tuning.py`, `backtest/report.py`, `b_report.py`,
  `wf_report.py`, `web/lib/*`, `engine/tests/test_backtest_{tuning,metrics,b_walkforward,report,b_report}.py`,
  `docs/plans/2026-10-03-seer-design.md` — claimed by session `seer-fc`.
- `docs/plans/2026-10-03-seer-design.md` §13/§14 — Phase 2.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/delisting.py` | create | the hazard estimator and the `Market` perturbation |
| `engine/scripts/delisting_stress.py` | create | the Monte Carlo driver and the break-even solver |
| `engine/tests/test_delisting.py` | create | hazard arithmetic, perturbation correctness, the engine's force-close, the read-only guard |

No existing file is touched, so there is no line reference to give for a modification. The three
new files land at the paths above; `delisting.py` sits beside `research.py` at the top of
`seer_engine/` (deliberately **not** under `backtest/` or `sim/`, both of which
`tests/test_strategy_purity.py` globs for "no randomness" — this module's whole job is seeded
randomness, and invariant 8 of the plan index says it must live outside those paths).

---

## Implementation Steps

### Step 1: `engine/src/seer_engine/delisting.py`

**File:** `engine/src/seer_engine/delisting.py` (new, whole file)
**Change:** the measuring and perturbing half of the harness.
**Code:**

```python
"""The delisting stress harness: the hazard the store records, and a Market with deaths injected.

Handover section 5 Q1; plan `DELISTING_STRESS_ROSTER_RULES_PLAN.md` phase 1. This module is the
measuring and perturbing half. `engine/scripts/delisting_stress.py` is the driver that runs a
Monte Carlo over it and solves for the break-even delisting return.

**Read-only, and structurally unable to be anything else.** It imports neither
``seer_engine.lab.store`` nor ``seer_engine.lab.runner``, so it cannot record a trial or move the
lab's N -- tests/test_delisting.py asserts that in the source and again in a fresh interpreter. It
opens no file, no database and no socket, and it writes nothing to ``engine/.research``: every
perturbation is a new in-memory ``Market``, so no ``config_digest`` moves and none of the 110
recorded trials is disturbed.

WHY THIS EXISTS. ``engine/scripts/survivorship_coverage.py`` measured how much of the index the
store can price -- 522 of 1,041 ever-members have no bars at all -- and compared the edge over
total-return SPY across eras of rising coverage. That contrast is confounded with market regime,
so it is evidence against the simple survivorship story and never proof the hole is harmless. The
test that isolates the mechanism injects the deaths the store is missing and asks how bad the
assumed loss has to be before the edge disappears.

WHY THE INJECTION NEEDS NO ENGINE CHANGE. Three facts, each verified in the running tree:

1. ``book_runner`` forms the ranking universe from ``membership.members_on(data_date)``, and the
   allocator keeps only the members with a bar on that date. A symbol whose bars stop is silently
   absent from every later ranking.
2. ``book_runner`` force-closes a held position whose bars have stopped, at its mark, reason
   "forced" (``sim.book.close_book_unpriced``). **The engine therefore already models a delisting,
   at a delisting return of exactly 0%**: the holder is paid the last price anyone saw. That
   assumption is invisible today only because no symbol in the store disappears mid-window.
3. ``Market`` is frozen and ``dataclasses.replace`` already swaps one of its fields inside
   ``backtest.dev._run`` (``fx``, for a window that opens before the first FX row). :func:`kill`
   swaps two: ``history`` and ``membership``.

So the whole perturbation is: truncate a symbol's ``History`` at its death date, rewrite that last
bar to ``close x (1 + r)``, and retire the symbol from the index the day after. The unchanged
engine does the rest.

TWO DELIBERATE CHOICES, both in the conservative direction (plan Decisions):

- **Who dies.** The priced survivors, at the measured hazard -- not the 404 missing names brought
  back with invented price paths. Fabricating 404 price histories would make up the one thing no
  free source can supply, and the invented prices, not the data, would drive the answer.
- **How they die.** Abruptly. The final bar is flat (open = high = low = close), so no stop, limit
  or intraday exit can fill above the death price and the book gets no chance to leave. That makes
  the resulting break-even return an upper bound on the damage, which is the honest direction for
  a test whose purpose is reassurance. ``decline_sessions > 1`` spreads the same loss over the
  last few bars as a visible decline -- the forewarned sensitivity, supported but not the default.

WHAT THE HAZARD IS, AND WHAT IT IS NOT. :func:`measure_hazard` counts the symbols whose last
membership interval ends inside the window and divides by the window's member-years. The hole
decomposes into two populations and only one of them is simulable: the names that left the index
inside the window and have no bars (the survivorship case proper, what this harness injects), and
the names that were still members at the window's end and have no bars at all (a thinner ranking
pool for twenty years, which no delisting injection can model, because the missing thing there is
a price path and not a death).

RANDOMNESS IS PASSED IN, NEVER MODULE-GLOBAL. Every entry point that draws takes a
``random.Random``, so a (seed, r) pair is reproducible on any machine, and the same seed kills the
same names on the same days at every assumed return -- which is what makes a grid of returns a
paired comparison rather than a pile of unrelated runs.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from random import Random

import numpy as np

from seer_engine.backtest.dev import DEV_END, MEMBERSHIP_START
from seer_engine.backtest.market import SPY, Market, Membership
from seer_engine.strategies.base import History

__all__ = [
    "Death",
    "Exposure",
    "Hazard",
    "MIN_PRICE",
    "WINDOW_END",
    "WINDOW_START",
    "YEAR_DAYS",
    "draw_deaths",
    "kill",
    "measure_hazard",
    "stressed",
    "survivors",
]

YEAR_DAYS = 365.25
"""Days in a year, Actual/365.25 -- the same convention as ``backtest.metrics.YEAR_DAYS``."""

MIN_PRICE = 1e-4
"""The floor every perturbed price is held at: one 4-dp price quantum.

``r = -1`` would otherwise produce a zero close, and the simulator divides by prices. A total loss
is therefore modelled as a hundredth of a cent, not as nothing, which costs four decimal places of
realism and buys an engine that cannot divide by zero.
"""

WINDOW_START = MEMBERSHIP_START
"""The first membership snapshot, 1996-01-02. Imported, never duplicated."""

WINDOW_END = DEV_END
"""The last dev session, 2015-10-16. Imported, never duplicated -- this harness never looks past it."""

ONE_DAY = timedelta(days=1)


def _as_date(name: str, d: object) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise TypeError(f"{name} must be a date, got {type(d).__name__}")
    return d


def _frozen(arr: np.ndarray) -> np.ndarray:
    """``arr`` made read-only, as ``strategies.base.history_from_bars`` makes its columns."""
    arr.setflags(write=False)
    return arr


# --------------------------------------------------------------------------- the hazard


@dataclass(frozen=True)
class Hazard:
    """What the store's own membership says about how often a member stops being priceable.

    Counted over ``[window_start, window_end]``. ``exits`` is the number of symbols whose LAST
    membership interval ends inside the window; ``unserved_exits`` is the subset with no bars at
    all, which is the population a free price feed drops and the one this harness re-injects.
    ``member_years`` is ``round(mean_members x window_years)``, with ``mean_members`` the mean
    membership count on 30 June of every year the window spans -- that is the arithmetic that
    reproduces the analysis's M2 measurement exactly.

    ``unrecorded_unserved`` and ``unserved_but_priced`` are cross-checks against the store's own
    ``unserved.csv``: the first lists ever-members with no bars that the file does not mention,
    the second lists symbols the file calls unserved that nevertheless have bars. Both are empty
    for the store on disk today. ``unrecorded_unserved`` is empty when no list was passed in,
    because silence is not a disagreement.
    """

    window_start: date
    window_end: date
    ever_members: int
    served: int
    unserved: int
    exits: int
    served_exits: int
    unserved_exits: int
    mean_members: float
    member_years: int
    exits_by_year: tuple[tuple[int, int], ...]
    unrecorded_unserved: tuple[str, ...] = ()
    unserved_but_priced: tuple[str, ...] = ()

    @property
    def window_years(self) -> float:
        """The window's length, Actual/365.25."""
        return (self.window_end - self.window_start).days / YEAR_DAYS

    @property
    def exit_rate(self) -> float:
        """Exits per member-year, counting every exit (the upper sensitivity, 5.1%/yr today)."""
        return self.exits / self.member_years

    @property
    def unserved_exit_rate(self) -> float:
        """Exits per member-year counting only the names with no bars (the base case, 4.0%/yr)."""
        return self.unserved_exits / self.member_years


def _last_end(
    intervals: Sequence[tuple[str, date, date | None]],
) -> dict[str, date | None]:
    """Symbol -> the latest end over its intervals; None when any one of them is still open.

    ``Membership`` holds one row per ``universe`` row, so a symbol in both indices appears twice
    and its intervals may overlap. A symbol has left the index only when every interval has closed.
    """
    out: dict[str, date | None] = {}
    for symbol, _start, end in intervals:
        if symbol not in out:
            out[symbol] = end
            continue
        seen = out[symbol]
        out[symbol] = None if (seen is None or end is None) else max(seen, end)
    return out


def measure_hazard(
    market: Market,
    *,
    unserved: Iterable[str] = (),
    window_start: date = WINDOW_START,
    window_end: date = WINDOW_END,
) -> Hazard:
    """How often an index member stopped being priceable, from ``market``'s own membership.

    ``unserved`` is the store's recorded ``unserved.csv`` list (``ResearchData.unserved``), used
    only for the two cross-check fields: the counting itself is done from
    ``market.membership.intervals`` and ``market.history``, so the result holds for any market,
    including a synthetic one in a test.

    Nothing here is hardcoded. Against the research store on disk it returns
    ``exit_rate == 5.091%`` and ``unserved_exit_rate == 4.002%`` over 10,096 member-years, which
    is the analysis's M2 measurement.
    """
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    _as_date("window_start", window_start)
    _as_date("window_end", window_end)
    if window_end <= window_start:
        raise ValueError(f"window_end {window_end} must be after window_start {window_start}")
    recorded = frozenset(unserved)
    ends = _last_end(market.membership.intervals)
    priced = frozenset(market.history)
    served = frozenset(s for s in ends if s in priced)
    missing = frozenset(ends) - served
    exits = {s: e for s, e in ends.items() if e is not None and window_start <= e <= window_end}
    by_year: Counter[int] = Counter(e.year for e in exits.values())
    counts = [
        len(market.membership.members_on(d))
        for d in (date(y, 6, 30) for y in range(window_start.year, window_end.year + 1))
        if window_start <= d <= window_end
    ]
    if not counts:
        raise ValueError(
            f"[{window_start}, {window_end}] spans no 30 June; the hazard needs at least one "
            "mid-year membership count"
        )
    mean_members = sum(counts) / len(counts)
    member_years = round(mean_members * ((window_end - window_start).days / YEAR_DAYS))
    if member_years <= 0:
        raise ValueError("the window holds no member-years; nothing can be measured over it")
    return Hazard(
        window_start=window_start,
        window_end=window_end,
        ever_members=len(ends),
        served=len(served),
        unserved=len(missing),
        exits=len(exits),
        served_exits=sum(1 for s in exits if s in served),
        unserved_exits=sum(1 for s in exits if s in missing),
        mean_members=mean_members,
        member_years=member_years,
        exits_by_year=tuple(sorted(by_year.items())),
        unrecorded_unserved=tuple(sorted(missing - recorded)) if recorded else (),
        unserved_but_priced=tuple(sorted(recorded & priced)),
    )


# --------------------------------------------------------------------------- who can die


@dataclass(frozen=True)
class Exposure:
    """One priced survivor's member-time: when it was both an index member and priceable.

    ``spans`` are inclusive ``[first, last]`` day ranges, ascending and disjoint, clipped to the
    measuring window and to the symbol's own bars. A hazard applies to ``years``; a death date is
    drawn uniformly over ``days``.
    """

    symbol: str
    spans: tuple[tuple[date, date], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol:
            raise ValueError(f"symbol must be a non-empty str, got {self.symbol!r}")
        if not isinstance(self.spans, tuple) or not self.spans:
            raise ValueError(f"{self.symbol}: spans must be a non-empty tuple")
        previous: date | None = None
        for item in self.spans:
            if not (isinstance(item, tuple) and len(item) == 2):
                raise TypeError(f"{self.symbol}: a span is (first, last), got {item!r}")
            first, last = item
            _as_date("span first", first)
            _as_date("span last", last)
            if last <= first:
                raise ValueError(f"{self.symbol}: span last {last} must be after first {first}")
            if previous is not None and first <= previous:
                raise ValueError(f"{self.symbol}: spans must be ascending and disjoint")
            previous = last

    @property
    def days(self) -> int:
        """Total member-days over every span."""
        return sum((last - first).days for first, last in self.spans)

    @property
    def years(self) -> float:
        """``days`` over 365.25 -- what a per-year hazard is applied to."""
        return self.days / YEAR_DAYS


def survivors(
    market: Market,
    *,
    window_start: date = WINDOW_START,
    window_end: date = WINDOW_END,
) -> tuple[Exposure, ...]:
    """The priced index members that never left the index inside the window, sorted by symbol.

    These are the names a synthetic delisting can be given to. Excluded, each for its own reason:

    - a member with no bars -- it is already absent from every ranking, so killing it changes
      nothing;
    - a member whose last interval ends inside the window -- it already left, and injecting a
      second exit would double-count the historical rate;
    - a member with fewer than two bars inside its member-time -- there is no bar to truncate at
      that still leaves the symbol priced beforehand.

    ETFs are never index members, so SPY and the idle instrument can never appear here. Exposure
    is clipped to the window and then to the symbol's own first and last bar, because a member we
    could not price was never in the ranking pool and must not contribute member-years.
    """
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    _as_date("window_start", window_start)
    _as_date("window_end", window_end)
    if window_end <= window_start:
        raise ValueError(f"window_end {window_end} must be after window_start {window_start}")
    ends = _last_end(market.membership.intervals)
    raw: dict[str, list[tuple[date, date]]] = {}
    for symbol, start, end in market.membership.intervals:
        first = max(start, window_start)
        last = min(window_end if end is None else end - ONE_DAY, window_end)
        if last >= first:
            raw.setdefault(symbol, []).append((first, last))
    out: list[Exposure] = []
    for symbol in sorted(raw):
        end = ends[symbol]
        if end is not None and window_start <= end <= window_end:
            continue  # it already left the index inside the window
        h = market.history.get(symbol)
        if h is None or len(h) < 2:
            continue  # unserved: already absent from every ranking
        bars_first, bars_last = h.dates[0].item(), h.dates[-1].item()
        spans: list[tuple[date, date]] = []
        for first, last in sorted(raw[symbol]):
            first, last = max(first, bars_first), min(last, bars_last)
            if last <= first:
                continue
            if spans and first <= spans[-1][1] + ONE_DAY:
                spans[-1] = (spans[-1][0], max(spans[-1][1], last))
            else:
                spans.append((first, last))
        if not spans:
            continue
        out.append(Exposure(symbol, tuple(spans)))
    return tuple(out)


# --------------------------------------------------------------------------- who does die


@dataclass(frozen=True)
class Death:
    """One injected delisting: ``symbol``'s last bar is ``last_bar``; it is gone the next session."""

    symbol: str
    last_bar: date

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol:
            raise ValueError(f"symbol must be a non-empty str, got {self.symbol!r}")
        _as_date("last_bar", self.last_bar)


def _uniform_day(exposure: Exposure, rng: Random) -> date:
    """A day drawn uniformly over ``exposure``'s member-days, strictly before its last day."""
    u = rng.random() * exposure.days
    for first, last in exposure.spans:
        width = (last - first).days
        if u < width:
            return first + timedelta(days=int(u))
        u -= width
    return exposure.spans[-1][1] - ONE_DAY


def _death_bar(h: History, when: date) -> date | None:
    """The last bar on or before ``when`` that still leaves a later bar, or None when there is none.

    A death on a symbol's very last bar would be a no-op -- the symbol never becomes "gone" inside
    the window and no position is ever force-closed -- so the index is pulled back by one.
    """
    i = int(np.searchsorted(h.dates, np.datetime64(when), side="right")) - 1
    i = min(i, len(h) - 2)
    if i < 0:
        return None
    return h.dates[i].item()


def draw_deaths(
    market: Market,
    exposures: Sequence[Exposure],
    hazard_per_year: float,
    rng: Random,
) -> tuple[Death, ...]:
    """Who dies and when, under a constant annual hazard: ``P(death) = 1 - exp(-hazard x years)``.

    One ``rng`` draw per exposure for the Bernoulli, and one more for each death's date, taken in
    ``exposures`` order. So the draw is reproducible from the seed alone, and -- because no part of
    it looks at the assumed delisting return -- the same seed kills the same names on the same days
    at every ``r`` on a grid. That is what makes a grid of returns a paired comparison.

    The death date is uniform over the symbol's member-days, then snapped back to the last bar on
    or before it. A symbol can die at most once: its hazard is integrated over its whole exposure
    rather than resampled, so the realised count is below ``hazard x total member-years`` by the
    usual competing-risk amount, and the driver prints both numbers.
    """
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    if not isinstance(rng, Random):
        raise TypeError(f"rng must be a random.Random, got {type(rng).__name__}")
    if isinstance(hazard_per_year, bool) or not isinstance(hazard_per_year, (int, float)):
        raise TypeError(f"hazard_per_year must be a number, got {type(hazard_per_year).__name__}")
    rate = float(hazard_per_year)
    if not 0.0 <= rate <= 1.0:
        raise ValueError(f"hazard_per_year must be in [0, 1] per year, got {rate}")
    out: list[Death] = []
    for exposure in exposures:
        if not isinstance(exposure, Exposure):
            raise TypeError(f"expected an Exposure, got {type(exposure).__name__}")
        h = market.history.get(exposure.symbol)
        if h is None:
            raise ValueError(f"{exposure.symbol} has no bars in this market")
        if rng.random() >= 1.0 - math.exp(-rate * exposure.years):
            continue
        when = _death_bar(h, _uniform_day(exposure, rng))
        if when is not None:
            out.append(Death(exposure.symbol, when))
    return tuple(out)


# --------------------------------------------------------------------------- the perturbation


def _decline(h: History, delisting_return: float, sessions: int) -> History:
    """``h`` with its last ``sessions`` bars marked down so the final close is ``close x (1 + r)``.

    The final bar is flat -- open = high = low = close -- so nothing can fill above the death
    price: a stop placed the day before gets the gap-down open, which is the death price, and the
    force-close the next session gets the same mark. That is what "abrupt" means here. With
    ``sessions > 1`` the earlier decline bars keep their own shape, scaled by the running factor,
    so a forewarned death is visible and tradable in the days before it.

    Every price is floored at :data:`MIN_PRICE`; ``r = -1`` would otherwise write a zero close.
    """
    n = len(h)
    k = min(sessions, n)
    step = (1.0 + delisting_return) ** (1.0 / k)
    factors = np.ones(n, dtype=np.float64)
    for j in range(k):
        factors[n - k + j] = step ** (j + 1)
    columns: list[np.ndarray] = []
    for name in ("open", "high", "low", "close"):
        scaled = np.asarray(getattr(h, name), dtype=np.float64) * factors
        columns.append(np.maximum(scaled, MIN_PRICE))
    open_, high, low, close = columns
    open_[-1] = high[-1] = low[-1] = close[-1]
    return History(
        h.symbol,
        _frozen(np.array(h.dates, dtype="datetime64[D]")),
        _frozen(open_),
        _frozen(high),
        _frozen(low),
        _frozen(close),
        _frozen(np.array(h.volume, dtype=np.float64)),
    )


def _retired(membership: Membership, cuts: Mapping[str, date]) -> Membership:
    """``membership`` with every dead symbol leaving the index the day after its last bar.

    ``Membership`` ends are exclusive, so a symbol whose last bar is ``d`` is a member through
    ``d`` and gone from ``d + 1``. An interval that opens on or after the death never happens and
    is dropped; one that had already closed before it is left exactly as it was.

    This is belt and braces over the truncation: a ranking allocator drops a symbol with no bar on
    the data date anyway (``f_factor.FactorPrepared.rows_on`` selects the rows dated exactly
    ``data_date``), but retiring the symbol from the index makes the harness correct for any
    allocator, present or future, rather than only for the ones whose internals were read. It cost
    0.011 s per rebuild when measured over the store's 1,084 intervals.
    """
    out: list[tuple[str, date, date | None]] = []
    for symbol, start, end in membership.intervals:
        cut = cuts.get(symbol)
        if cut is None:
            out.append((symbol, start, end))
            continue
        stop = cut + ONE_DAY
        if start >= stop:
            continue
        out.append((symbol, start, stop if end is None or end > stop else end))
    return Membership(tuple(out))


def kill(
    market: Market,
    deaths: Iterable[Death],
    delisting_return: float,
    *,
    decline_sessions: int = 1,
) -> Market:
    """A NEW ``Market`` in which every named symbol is delisted on its death date at return ``r``.

    For each death: the symbol's ``History`` is truncated at ``death.last_bar``, that bar is
    rewritten to ``close x (1 + delisting_return)`` (flat, see :func:`_decline`), and the symbol
    leaves the index the next day. ``market`` is untouched -- ``Market`` is frozen and this is
    ``dataclasses.replace``, the same move ``backtest.dev._run`` already makes on ``fx``.

    The engine does the rest with no change: the name is absent from every later ranking, and any
    position still held is force-closed at the rewritten mark, reason "forced"
    (``book_runner.py`` steps 1 and 4, ``sim.book.close_book_unpriced``).

    ``delisting_return`` is in ``[-1, 0]``: 0 is the assumption every recorded backtest already
    makes (sold whole at the last price anyone saw) and -1 is a total loss. ``decline_sessions``
    is 1 for an abrupt death, the conservative base case, and larger for the forewarned
    sensitivity, which spreads the same total loss geometrically over the last that many bars.

    ValueError for a symbol with no bars, a repeated symbol, SPY, or a return outside ``[-1, 0]``.
    """
    if not isinstance(market, Market):
        raise TypeError(f"market must be a Market, got {type(market).__name__}")
    if isinstance(delisting_return, bool) or not isinstance(delisting_return, (int, float)):
        raise TypeError(f"delisting_return must be a number, got {type(delisting_return).__name__}")
    r = float(delisting_return)
    if not -1.0 <= r <= 0.0:
        raise ValueError(f"delisting_return must be in [-1, 0], got {r}")
    if isinstance(decline_sessions, bool) or not isinstance(decline_sessions, int):
        raise TypeError(f"decline_sessions must be an int, got {type(decline_sessions).__name__}")
    if decline_sessions < 1:
        raise ValueError(f"decline_sessions must be >= 1, got {decline_sessions}")
    history = dict(market.history)
    cuts: dict[str, date] = {}
    for death in deaths:
        if not isinstance(death, Death):
            raise TypeError(f"expected a Death, got {type(death).__name__}")
        if death.symbol in cuts:
            raise ValueError(f"{death.symbol} is given two death dates")
        if death.symbol == SPY:
            raise ValueError("SPY cannot be delisted; it is the benchmark every run is scored against")
        h = market.history.get(death.symbol)
        if h is None:
            raise ValueError(f"{death.symbol} has no bars in this market, so it cannot be delisted")
        cut = h.upto(death.last_bar)
        if len(cut) == 0:
            raise ValueError(f"{death.symbol} has no bar on or before {death.last_bar}")
        history[death.symbol] = _decline(cut, r, decline_sessions)
        cuts[death.symbol] = death.last_bar
    if not cuts:
        return market
    return replace(market, history=history, membership=_retired(market.membership, cuts))


def stressed(
    market: Market,
    exposures: Sequence[Exposure],
    *,
    hazard_per_year: float,
    delisting_return: float,
    rng: Random,
    decline_sessions: int = 1,
) -> tuple[Market, tuple[Death, ...]]:
    """One Monte Carlo draw: ``(the perturbed market, who died)``.

    :func:`draw_deaths` then :func:`kill`. The deaths are returned as well as applied because the
    driver reports how many names a seed killed, and because two calls with equal seeds must be
    checkable for equal deaths at different assumed returns.
    """
    deaths = draw_deaths(market, exposures, hazard_per_year, rng)
    return kill(market, deaths, delisting_return, decline_sessions=decline_sessions), deaths
```

**Impact:** adds one importable module. Nothing imports it yet except the new script and the new
test, so no existing behaviour changes. The module is outside
`tests/test_strategy_purity.py`'s glob (which covers `strategies/`, `backtest/`, `fundamentals/`
and `paper/`), which is why its seeded randomness is allowed to exist at all.

---

### Step 2: `engine/scripts/delisting_stress.py`

**File:** `engine/scripts/delisting_stress.py` (new, whole file)
**Change:** the Monte Carlo driver and the break-even solver, in `survivorship_coverage.py`'s
shape and under its contract.
**Code:**

```python
"""How bad an assumed delisting would have to be before the lab's edge disappears.

Handover section 5 Q1. Injects synthetic delistings into the dev-window ranking universe at the
hazard the store's own membership records, re-runs each roster entry's backtest against the
perturbed market, and solves for the **break-even delisting return** -- the assumed loss at which
the entry stops beating total-return SPY.

    engine/.venv/bin/python engine/scripts/delisting_stress.py --smoke
    engine/.venv/bin/python engine/scripts/delisting_stress.py --seeds 100 --jobs 6

Read-only, exactly like `survivorship_coverage.py`: it loads the research store, writes nothing,
records no trial, does not move the lab's N and spends no test-window look. `backtest.dev` is
pure -- a trial is written by `lab.runner.run_method`, never by `dev` -- so calling
`dev.run_candidate` here costs nothing and changes nothing. The only lab module this script
touches is `lab.method.discover`, which reads the method files and opens no database; neither it
nor `seer_engine.delisting` imports `lab.store` or `lab.runner`, and a test asserts the second half
of that.

WHY THE BACKTEST IS RE-RUN RATHER THAN THE RECORDED CURVE RE-SLICED. `trials.curve_json` is a
month-end equity curve and carries no positions, no symbols and no trades. An injection changes
WHICH names are held, so a perturbed path cannot be derived from an unperturbed one.
`survivorship_coverage.py` could slice; this cannot. One full dev-window run measures at 2-3 s on
an idle machine and 5-11 s under concurrent load, so four entries x eight assumed returns x a
hundred seeds is hours, not days -- budget against the loaded number.

WHAT THE BREAK-EVEN NUMBER MEANS. The edge is strategy CAGR minus total-return SPY CAGR, in points
a year -- the handover's own unit. For each assumed return r the harness runs every seed, takes the
mean edge, and reports the r at which that mean first reaches zero, interpolated linearly between
the two grid points that straddle it. When the mean edge is still positive at the most negative r
on the grid there is no break-even inside it, and the harness says so rather than extrapolating.
It also reports the per-seed distribution of the same crossing, because a mean of a hundred
Monte Carlo paths hides how many of them disagree with it.

WHAT IT CANNOT ANSWER. Two things, both worth saying out loud wherever the number is quoted:

1. The r = 0 row is not the unstressed row. Removing names from the ranking pool at the historical
   rate costs something all by itself, even when every delisted holder is paid the last price
   anyone saw. The table prints the unstressed run and the r = 0 run as separate lines so that
   universe-thinning cost and delisting-loss cost are never read as one number.
2. 118 of the store's 522 unserved ever-members were still index members at the window's end. They
   did not die inside the window; a free feed dropped them afterwards. No delisting injection can
   model them, because what is missing there is a price path and not a death.
"""

from __future__ import annotations

import argparse
import csv
import multiprocessing
import os
import sys
import time
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from random import Random

import numpy as np

from seer_engine import config, research
from seer_engine.backtest.dev import Candidate, run_candidate
from seer_engine.backtest.market import Market
from seer_engine.delisting import Exposure, Hazard, measure_hazard, stressed, survivors
from seer_engine.lab.method import discover
from seer_engine.research import ResearchData, load_store
from seer_engine.strategies.allocator import prepare_for

#: The quant roster entries, by the lab variant each was promoted from (== survivorship_coverage).
ROSTER: tuple[tuple[str, str], ...] = (
    ("RMW-FR", "M0022-W-TV16"),
    ("RAW-FR", "M0007-N20-RAW"),
    ("MOM-FR", "M0002-REL-85"),
    ("MVW-FR", "M0008-N30-C07"),
)

#: The default grid of assumed delisting returns: 0 is what every recorded backtest already
#: assumes (sold whole at the last price seen), -1 is a total loss.
RETURNS: tuple[float, ...] = (0.0, -0.10, -0.20, -0.30, -0.50, -0.70, -0.90, -1.00)

BANNER = (
    "delisting stress -- read-only. No lab trial is recorded, the lab's N does not move, no "
    "test-window look is spent, and nothing is written to the research store."
)


@dataclass(frozen=True)
class Outcome:
    """One run's result: a roster entry at one assumed delisting return under one seed.

    ``delisting_return`` and ``seed`` are None for the unstressed reference run. ``edge`` is in
    points of CAGR a year over total-return SPY, which is the unit the handover's era table uses.
    """

    entry: str
    candidate: str
    delisting_return: float | None
    seed: int | None
    deaths: int
    start: date
    cagr: float | None
    max_drawdown: float | None
    total_return: float | None
    trades: int
    spy_cagr: float | None
    beats_spy: bool

    @property
    def edge(self) -> float | None:
        if self.cagr is None or self.spy_cagr is None:
            return None
        return (self.cagr - self.spy_cagr) * 100.0


@dataclass(frozen=True)
class _Shared:
    """Everything a worker needs, set once in the parent and inherited across ``fork``."""

    data: ResearchData
    exposures: tuple[Exposure, ...]
    candidates: dict[str, Candidate]
    hazard: float
    decline: int


_SHARED: _Shared | None = None


# --------------------------------------------------------------------------- running


def _run_one(
    entry: str,
    market: Market,
    delisting_return: float | None,
    seed: int | None,
    deaths: int,
) -> Outcome:
    """Run one candidate against one market and fold the result into an :class:`Outcome`."""
    assert _SHARED is not None, "_SHARED must be set before any run"
    candidate = _SHARED.candidates[entry]
    prepared = prepare_for(candidate.allocator, market)
    _result, row = run_candidate(
        market, _SHARED.data.dividends, _SHARED.data.spy_dividends, candidate, prepared=prepared
    )
    m = row.stats.metrics
    return Outcome(
        entry=entry,
        candidate=candidate.id,
        delisting_return=delisting_return,
        seed=seed,
        deaths=deaths,
        start=row.start,
        cagr=m.cagr,
        max_drawdown=m.max_drawdown,
        total_return=m.total_return,
        trades=m.trades,
        spy_cagr=row.spy_tr.cagr,
        beats_spy=row.beats_spy,
    )


def _base(entry: str) -> Outcome:
    """The unstressed reference run for ``entry``."""
    assert _SHARED is not None, "_SHARED must be set before any run"
    return _run_one(entry, _SHARED.data.market, None, None, 0)


def _stressed_one(job: tuple[str, float, int]) -> Outcome:
    """One (entry, assumed return, seed) cell. The Pool's work unit; must be module level."""
    assert _SHARED is not None, "_SHARED must be set before any run"
    entry, delisting_return, seed = job
    market, deaths = stressed(
        _SHARED.data.market,
        _SHARED.exposures,
        hazard_per_year=_SHARED.hazard,
        delisting_return=delisting_return,
        rng=Random(seed),
        decline_sessions=_SHARED.decline,
    )
    return _run_one(entry, market, delisting_return, seed, len(deaths))


def _progress(results: Iterable[Outcome], total: int) -> Iterator[Outcome]:
    """Pass results through, printing a one-line counter to stderr (stdout stays a clean table)."""
    started = time.perf_counter()
    for i, outcome in enumerate(results, start=1):
        elapsed = time.perf_counter() - started
        left = elapsed / i * (total - i)
        print(
            f"\r  {i}/{total} runs  {elapsed / 60:.1f} min elapsed, ~{left / 60:.1f} min left   ",
            end="",
            file=sys.stderr,
            flush=True,
        )
        yield outcome
    print("", file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- the solver


def break_even(points: Sequence[tuple[float, float]]) -> float | None:
    """The assumed delisting return at which ``edge`` first reaches zero, or None.

    ``points`` is ``(assumed return, edge in points a year)``, in any order. Searched from the
    least negative return downwards; the crossing is linear between the two grid points that
    straddle it. None when the edge is still positive at the most negative point -- there is no
    break-even inside the grid, and the harness refuses to extrapolate past the data it has.
    """
    ordered = sorted(points, key=lambda p: -p[0])
    if not ordered:
        return None
    if ordered[0][1] <= 0.0:
        return ordered[0][0]
    for (r0, e0), (r1, e1) in zip(ordered, ordered[1:]):
        if e1 <= 0.0:
            return r0 + (r1 - r0) * (e0 / (e0 - e1))
    return None


def _per_seed_break_even(by_seed: dict[int, list[tuple[float, float]]]) -> tuple[list[float], int]:
    """Each seed's own break-even, and how many seeds never break even on the grid."""
    found: list[float] = []
    never = 0
    for seed in sorted(by_seed):
        value = break_even(by_seed[seed])
        if value is None:
            never += 1
        else:
            found.append(value)
    return found, never


# --------------------------------------------------------------------------- printing


def _pct(x: float | None) -> str:
    """A signed percentage -- a return, which may go either way."""
    return "       -" if x is None else f"{x * 100:+7.2f}%"


def _fall(x: float | None) -> str:
    """An unsigned percentage -- a drawdown, which only ever goes one way."""
    return "      -" if x is None else f"{x * 100:6.2f}%"


def _print_hazard(hazard: Hazard, exposures: Sequence[Exposure], rate: float, label: str) -> None:
    print("=== 1. the delisting hazard the store's own membership records ===")
    print(f"window {hazard.window_start} .. {hazard.window_end}  ({hazard.window_years:.2f} years)")
    print(f"ever-members {hazard.ever_members}   priced {hazard.served}   unpriced {hazard.unserved}")
    print(f"left the index inside the window: {hazard.exits}"
          f"   of those unpriced {hazard.unserved_exits}, priced {hazard.served_exits}")
    print(f"mean members on a mid-year date {hazard.mean_members:.2f}"
          f"   member-years {hazard.member_years}")
    print(f"  annual exit hazard, every exit:        {hazard.exit_rate:.3%}")
    print(f"  annual exit hazard, the unpriced ones: {hazard.unserved_exit_rate:.3%}")
    if hazard.unrecorded_unserved or hazard.unserved_but_priced:
        print(f"  NOTE unserved.csv disagrees with the bars: missing from the file "
              f"{hazard.unrecorded_unserved}, listed but priced {hazard.unserved_but_priced}")
    years = sum(e.years for e in exposures)
    print(f"\neligible to be killed: {len(exposures)} priced survivors over {years:,.0f} member-years")
    print(f"injecting at {rate:.3%}/yr ({label})")
    print(f"  expected deaths, competing risks included: "
          f"{sum(1.0 - np.exp(-rate * e.years) for e in exposures):.1f}")
    print(f"  (a memoryless process over the same member-years would give {rate * years:.1f})")
    print("\nNOT modelled, and no injection can model it: the unpriced names that were STILL index\n"
          "members at the window's end. They did not die inside the window; a free feed dropped\n"
          "them afterwards, and what is missing for them is a price path, not a death.\n")


def _print_entry(entry: str, candidate: str, base: Outcome, outcomes: Sequence[Outcome],
                 returns: Sequence[float], seeds: int) -> None:
    print(f"=== {entry}  ({candidate}) ===")
    print(f"unstressed:   CAGR {_pct(base.cagr)}/yr   worst fall {_fall(base.max_drawdown)}"
          f"   trades {base.trades:5}   edge over SPY TR {base.edge:+6.2f} pts/yr")
    print("\n  assumed r   deaths     CAGR/yr    worst fall    trades"
          "      edge pts/yr  (p10 .. p90)    beats SPY")
    mean_points: list[tuple[float, float]] = []
    by_seed: dict[int, list[tuple[float, float]]] = {}
    for r in returns:
        rows = [o for o in outcomes if o.delisting_return == r]
        if not rows:
            continue
        edges = [o.edge for o in rows if o.edge is not None]
        cagrs = [o.cagr for o in rows if o.cagr is not None]
        falls = [o.max_drawdown for o in rows if o.max_drawdown is not None]
        mean_edge = float(np.mean(edges)) if edges else 0.0
        mean_points.append((r, mean_edge))
        for o in rows:
            if o.seed is not None and o.edge is not None:
                by_seed.setdefault(o.seed, []).append((r, o.edge))
        beats = sum(1 for o in rows if o.beats_spy)
        print(f"   {r * 100:+6.0f}%   {float(np.mean([o.deaths for o in rows])):6.1f}"
              f"    {float(np.mean(cagrs)) * 100 if cagrs else float('nan'):+7.2f}%"
              f"      {float(np.mean(falls)) * 100 if falls else float('nan'):6.2f}%"
              f"     {float(np.mean([o.trades for o in rows])):6.0f}"
              f"      {mean_edge:+6.2f}"
              f"  ({float(np.percentile(edges, 10)):+6.2f} .. {float(np.percentile(edges, 90)):+6.2f})"
              f"      {beats:4}/{len(rows)}")
    crossing = break_even(mean_points)
    print()
    if crossing is None:
        worst_r, worst_edge = min(mean_points, key=lambda p: p[0])
        print(f"break-even delisting return: NONE on this grid. The mean edge is still "
              f"{worst_edge:+.2f} pts/yr at r = {worst_r * 100:.0f}%, so even a total loss on every "
              f"injected delisting leaves {entry} ahead of total-return SPY.")
    else:
        print(f"break-even delisting return: {crossing * 100:.1f}%  "
              f"(the mean edge over {seeds} seeds crosses zero there)")
    found, never = _per_seed_break_even(by_seed)
    if found:
        tail = "" if not never else f", and {never} of {len(by_seed)} seeds never break even on this grid"
        print(f"  per seed: median {float(np.median(found)) * 100:.1f}%, "
              f"p10 {float(np.percentile(found, 10)) * 100:.1f}%, "
              f"p90 {float(np.percentile(found, 90)) * 100:.1f}%{tail}")
    elif by_seed:
        print(f"  per seed: none of the {len(by_seed)} seeds breaks even anywhere on this grid")
    print()


def _write_csv(path: Path, outcomes: Sequence[Outcome]) -> None:
    """One row per run, for whoever has to quote these numbers later."""
    resolved = path.resolve()
    for forbidden in (config.REPO_ROOT / "engine" / ".research", config.REPO_ROOT / "lab"):
        if resolved == forbidden or forbidden in resolved.parents:
            raise SystemExit(f"--csv must not write inside {forbidden}; this harness writes nothing there")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8", newline="\n") as fh:
        writer = csv.writer(fh)
        writer.writerow(("entry", "candidate", "delisting_return", "seed", "deaths", "start",
                         "cagr", "max_drawdown", "total_return", "trades", "spy_cagr",
                         "edge_points_per_year", "beats_spy"))
        for o in outcomes:
            writer.writerow((o.entry, o.candidate,
                             "" if o.delisting_return is None else f"{o.delisting_return:.4f}",
                             "" if o.seed is None else o.seed, o.deaths, o.start.isoformat(),
                             "" if o.cagr is None else f"{o.cagr:.6f}",
                             "" if o.max_drawdown is None else f"{o.max_drawdown:.6f}",
                             "" if o.total_return is None else f"{o.total_return:.6f}",
                             o.trades,
                             "" if o.spy_cagr is None else f"{o.spy_cagr:.6f}",
                             "" if o.edge is None else f"{o.edge:.4f}",
                             "yes" if o.beats_spy else "no"))
    print(f"wrote {len(outcomes)} rows to {resolved}")


# --------------------------------------------------------------------------- the command line


def _parse(argv: Sequence[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="delisting_stress.py",
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--entry", action="append", default=None, metavar="NAME",
                   help="a roster name (RMW-FR) or a lab candidate id (M0022-W-TV16); repeatable. "
                        "Default: all four quant roster entries.")
    p.add_argument("--returns", default=None, metavar="LIST",
                   help="comma-separated assumed delisting returns in [-1, 0], e.g. "
                        "'0,-0.25,-0.5,-1'. Default: " + ",".join(f"{r:g}" for r in RETURNS))
    p.add_argument("--seeds", type=int, default=100, metavar="N",
                   help="Monte Carlo seeds per (entry, return) cell (default 100)")
    p.add_argument("--seed0", type=int, default=0, metavar="N",
                   help="the first seed; seeds are seed0 .. seed0 + seeds - 1 (default 0)")
    p.add_argument("--hazard", default="unserved", metavar="RATE",
                   help="the annual hazard to inject: 'unserved' (the measured unpriced-exit "
                        "rate, ~4.0%%/yr, the base case), 'all' (every exit, ~5.1%%/yr, the upper "
                        "sensitivity), or a number such as 0.04 (default: unserved)")
    p.add_argument("--decline-sessions", type=int, default=1, metavar="N",
                   help="1 = abrupt death, the conservative base case; N > 1 spreads the same "
                        "total loss over the last N bars as a visible decline (the forewarned "
                        "sensitivity)")
    p.add_argument("--jobs", type=int, default=1, metavar="N",
                   help="worker processes (fork; Linux only). The store is ~940 MB shared and "
                        "each worker adds roughly 150 MB. Default 1.")
    p.add_argument("--store", type=Path,
                   default=Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR),
                   help="the research store directory ($SEER_RESEARCH_STORE). In a worktree this "
                        "must point at the MAIN checkout: the store is gitignored and is not "
                        "copied into a worktree.")
    p.add_argument("--csv", type=Path, default=None, metavar="PATH",
                   help="also write one row per run to this file (never inside engine/.research "
                        "or lab/)")
    p.add_argument("--smoke", action="store_true",
                   help="one entry, two returns, two seeds: proves the harness runs end to end. "
                        "About 30-45 s on an idle machine, 60-90 s under swarm load; almost all "
                        "of it load_store.")
    args = p.parse_args(argv)
    if args.smoke:
        args.entry = args.entry or ["RMW-FR"]
        args.returns = args.returns or "0,-1"
        args.seeds = min(args.seeds, 2)
        args.jobs = 1
    return args


def _entries(chosen: Sequence[str] | None) -> tuple[tuple[str, str], ...]:
    if not chosen:
        return ROSTER
    by_name = {name: cid for name, cid in ROSTER}
    by_id = {cid: name for name, cid in ROSTER}
    out: list[tuple[str, str]] = []
    for item in chosen:
        if item in by_name:
            out.append((item, by_name[item]))
        elif item in by_id:
            out.append((by_id[item], item))
        else:
            out.append((item, item))  # any lab candidate id, named after itself
    return tuple(out)


def _returns(text: str | None) -> tuple[float, ...]:
    if text is None:
        return RETURNS
    out: list[float] = []
    for piece in text.split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            value = float(piece)
        except ValueError:
            raise SystemExit(f"--returns: {piece!r} is not a number") from None
        if not -1.0 <= value <= 0.0:
            raise SystemExit(f"--returns: {value} is outside [-1, 0]")
        out.append(value)
    if not out:
        raise SystemExit("--returns must name at least one assumed delisting return")
    return tuple(sorted(set(out), reverse=True))


def _rate(choice: str, measured: Hazard) -> tuple[float, str]:
    if choice == "unserved":
        return measured.unserved_exit_rate, "the measured unpriced-exit rate"
    if choice == "all":
        return measured.exit_rate, "the measured all-exit rate, the upper sensitivity"
    try:
        value = float(choice)
    except ValueError:
        raise SystemExit(f"--hazard must be 'unserved', 'all' or a number, got {choice!r}") from None
    if not 0.0 <= value <= 1.0:
        raise SystemExit(f"--hazard must be in [0, 1] per year, got {value}")
    return value, "given on the command line"


def _candidates(wanted: Iterable[tuple[str, str]]) -> dict[str, Candidate]:
    """Roster name -> the lab Candidate it was promoted from, via lab.method.discover()."""
    by_id: dict[str, Candidate] = {}
    for method, _path in discover().values():
        for c in method.candidates:
            by_id[c.id] = c
    out: dict[str, Candidate] = {}
    for name, candidate_id in wanted:
        if candidate_id not in by_id:
            raise SystemExit(f"no lab candidate {candidate_id!r}; run `python -m seer_engine lab list`")
        out[name] = by_id[candidate_id]
    return out


def main(argv: Sequence[str] | None = None) -> int:
    global _SHARED
    args = _parse(argv)
    entries = _entries(args.entry)
    returns = _returns(args.returns)
    seeds = tuple(range(args.seed0, args.seed0 + max(args.seeds, 1)))
    if args.jobs < 1:
        raise SystemExit(f"--jobs must be >= 1, got {args.jobs}")
    if args.decline_sessions < 1:
        raise SystemExit(f"--decline-sessions must be >= 1, got {args.decline_sessions}")

    print(BANNER)
    print(f"store {args.store}\n")
    started = time.perf_counter()
    data = load_store(args.store)
    print(f"loaded {len(data.market.history)} symbols in {time.perf_counter() - started:.1f}s"
          f"   fingerprint {data.fingerprint[:12]}\n")

    hazard = measure_hazard(data.market, unserved=data.unserved)
    exposures = survivors(data.market)
    rate, label = _rate(args.hazard, hazard)
    _print_hazard(hazard, exposures, rate, label)

    _SHARED = _Shared(
        data=data,
        exposures=exposures,
        candidates=_candidates(entries),
        hazard=rate,
        decline=args.decline_sessions,
    )

    print("=== 2. the stressed runs ===")
    print(f"{len(entries)} entries x {len(returns)} assumed returns x {len(seeds)} seeds "
          f"= {len(entries) * len(returns) * len(seeds)} runs"
          f"   ({'abrupt death' if args.decline_sessions == 1 else f'decline over {args.decline_sessions} sessions'})\n")

    bases = {name: _base(name) for name, _cid in entries}
    jobs = [(name, r, seed) for name, _cid in entries for r in returns for seed in seeds]
    if args.jobs == 1:
        outcomes = list(_progress((_stressed_one(j) for j in jobs), len(jobs)))
    else:
        ctx = multiprocessing.get_context("fork")
        with ctx.Pool(args.jobs) as pool:
            outcomes = list(_progress(pool.imap_unordered(_stressed_one, jobs, chunksize=1), len(jobs)))

    for name, _cid in entries:
        base = bases[name]
        wrong = [o for o in outcomes if o.entry == name and o.start != base.start]
        if wrong:
            raise SystemExit(
                f"{name}: a stressed run opened on {wrong[0].start} but the unstressed run opens on "
                f"{base.start}; the comparison is not like for like. No ETF or SPY should ever be "
                "killed -- check survivors()."
            )

    print()
    for name, _cid in entries:
        _print_entry(name, _SHARED.candidates[name].id, bases[name],
                     [o for o in outcomes if o.entry == name], returns, len(seeds))

    if args.csv is not None:
        _write_csv(args.csv, [bases[name] for name, _cid in entries] + outcomes)
    print(f"total {(time.perf_counter() - started) / 60:.1f} min. {BANNER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**Impact:** adds one runnable script. Nothing imports it. It reads `engine/.research` and the lab
method files; it writes only the optional `--csv` file, and refuses to write that inside
`engine/.research` or `lab/`.

---

### Step 3: `engine/tests/test_delisting.py`

**File:** `engine/tests/test_delisting.py` (new, whole file)
**Change:** the phase's tests. Everything synthetic and in memory — the research store lives in
the main checkout and is gitignored, so a test that needed it would be a test that did not run.
**Code:**

```python
"""The delisting stress harness: hazard arithmetic, the perturbation, and its read-only contract.

Everything is synthetic: no research store, no lab database, no Postgres. The store is gitignored
and lives in the main checkout, so a test that needed it would be a test that quietly did not run.

Four groups:

1. ``measure_hazard`` on a market small enough to count by hand, including the two cross-checks
   against the store's recorded ``unserved`` list.
2. ``survivors`` picks the right population -- priced, still in the index at the window's end --
   and clips its exposure to both the window and the symbol's own bars.
3. ``draw_deaths`` is reproducible from its seed, identical at every assumed return, and matches
   the hazard it was given; ``kill`` truncates, marks the last bar down, retires the symbol from
   the index the next day, and leaves the original Market alone.
4. The unchanged engine does the rest: a killed symbol is force-closed at the rewritten mark by
   ``book_runner.run_book``. And the module imports nothing from ``seer_engine.lab``, in its own
   source and in a fresh interpreter, so it can never record a trial or move the lab's N.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from random import Random

import numpy as np
import pytest
from allocatorkit import FIXED, FixedParams
from stratkit import hist, session_days

import seer_engine
from seer_engine import delisting
from seer_engine.backtest.book_runner import run_book
from seer_engine.backtest.dev import DEV_END, MEMBERSHIP_START
from seer_engine.backtest.market import Market, Membership
from seer_engine.delisting import (
    MIN_PRICE,
    Death,
    draw_deaths,
    kill,
    measure_hazard,
    stressed,
    survivors,
)
from seer_engine.prices import to_decimal
from seer_engine.sim.rules import DAILY_SWITCH

SOURCE = Path(seer_engine.__file__).resolve().parent / "delisting.py"

# --------------------------------------------------------------------------- fixtures
#
# One hand-countable market. Window 2001-01-01 .. 2003-01-01 = 730 days = 1.99863 years.
#   AAA  member 2001-01-01 -> open, priced          -- the only survivor that can be killed
#   BBB  member 2001-01-01 -> 2002-01-01, priced    -- already left the index inside the window
#   CCC  member 2001-01-01 -> 2002-07-01, unpriced  -- an unpriced exit (what the harness injects)
#   DDD  member 2001-01-01 -> open, unpriced        -- unpriced and never died: not modellable
#   SPY  never a member, priced
# Mid-year counts: 2001-06-30 -> {AAA,BBB,CCC,DDD} = 4; 2002-06-30 -> {AAA,CCC,DDD} = 3.
# mean 3.5, member_years = round(3.5 x 1.99863) = 7. exits 2 -> 2/7; unpriced exits 1 -> 1/7.

W_START, W_END = date(2001, 1, 1), date(2003, 1, 1)
DAYS = session_days(400, date(2001, 1, 2))
INTERVALS = (
    ("AAA", date(2001, 1, 1), None),
    ("BBB", date(2001, 1, 1), date(2002, 1, 1)),
    ("CCC", date(2001, 1, 1), date(2002, 7, 1)),
    ("DDD", date(2001, 1, 1), None),
)


def counted_market() -> Market:
    return Market(
        history={
            "AAA": hist("AAA", [100.0] * 400, days=DAYS),
            "BBB": hist("BBB", [50.0] * 400, days=DAYS),
            "SPY": hist("SPY", [200.0] * 400, days=DAYS),
        },
        membership=Membership(INTERVALS),
        fx=(),
    )


def flat_market(n: int = 20, symbols: tuple[str, ...] = ("AAA", "BBB")) -> tuple[Market, list[date]]:
    """``n`` sessions of flat 100.00 for each of ``symbols``, all members from the first day."""
    days = session_days(n, date(2001, 1, 2))
    intervals = tuple((s, days[0], None) for s in symbols)
    return (
        Market(
            history={s: hist(s, [100.0] * n, days=days) for s in symbols},
            membership=Membership(intervals),
            fx=(),
        ),
        days,
    )


def uniform_market(count: int, years: int = 10) -> Market:
    """``count`` identical priced survivors, each a member for the whole window."""
    days = session_days(years * 252, date(2001, 1, 2))
    symbols = tuple(f"S{i:03d}" for i in range(count))
    return Market(
        history={s: hist(s, [100.0] * len(days), days=days) for s in symbols},
        membership=Membership(tuple((s, days[0], None) for s in symbols)),
        fx=(),
    )


# --------------------------------------------------------------------------- 1. the hazard


def test_the_window_constants_are_the_dev_windows_own():
    assert (delisting.WINDOW_START, delisting.WINDOW_END) == (MEMBERSHIP_START, DEV_END)


def test_measure_hazard_counts_both_populations_of_the_hole():
    h = measure_hazard(counted_market(), window_start=W_START, window_end=W_END)
    assert (h.ever_members, h.served, h.unserved) == (4, 2, 2)
    assert (h.exits, h.served_exits, h.unserved_exits) == (2, 1, 1)
    assert h.exits_by_year == ((2002, 2),)


def test_member_years_is_the_mid_year_mean_times_the_window_length():
    h = measure_hazard(counted_market(), window_start=W_START, window_end=W_END)
    assert h.mean_members == pytest.approx(3.5)
    assert h.window_years == pytest.approx(730 / 365.25)
    assert h.member_years == 7
    assert h.exit_rate == pytest.approx(2 / 7)
    assert h.unserved_exit_rate == pytest.approx(1 / 7)


def test_an_open_interval_anywhere_means_the_symbol_never_left():
    # AAA in both indices: one interval closes inside the window, the other is still open.
    market = Market(
        history={"AAA": hist("AAA", [100.0] * 400, days=DAYS)},
        membership=Membership((("AAA", date(2001, 1, 1), date(2002, 1, 1)),
                               ("AAA", date(2001, 6, 1), None))),
        fx=(),
    )
    h = measure_hazard(market, window_start=W_START, window_end=W_END)
    assert h.exits == 0


def test_the_unserved_cross_checks_name_both_kinds_of_disagreement():
    market = counted_market()
    silent = measure_hazard(market, window_start=W_START, window_end=W_END)
    assert silent.unrecorded_unserved == ()  # no list passed in is not a disagreement
    assert silent.unserved_but_priced == ()
    partial = measure_hazard(market, unserved=("CCC",), window_start=W_START, window_end=W_END)
    assert partial.unrecorded_unserved == ("DDD",)
    wrong = measure_hazard(market, unserved=("AAA", "CCC", "DDD"),
                           window_start=W_START, window_end=W_END)
    assert wrong.unserved_but_priced == ("AAA",)


def test_measure_hazard_refuses_a_backwards_or_too_short_window():
    market = counted_market()
    with pytest.raises(ValueError, match="must be after"):
        measure_hazard(market, window_start=W_END, window_end=W_START)
    with pytest.raises(ValueError, match="30 June"):
        measure_hazard(market, window_start=date(2001, 7, 1), window_end=date(2002, 6, 1))


# --------------------------------------------------------------------------- 2. who can die


def test_survivors_keeps_only_the_priced_names_still_in_the_index():
    out = survivors(counted_market(), window_start=W_START, window_end=W_END)
    assert [e.symbol for e in out] == ["AAA"]  # BBB left, CCC and DDD have no bars, SPY is no member


def test_survivor_exposure_is_clipped_to_the_window_and_to_the_bars():
    market = counted_market()
    out = survivors(market, window_start=date(2001, 6, 1), window_end=date(2002, 6, 1))
    (exposure,) = out
    bars = market.history["AAA"]
    first = max(date(2001, 6, 1), bars.dates[0].item())
    last = min(date(2002, 6, 1), bars.dates[-1].item())
    assert exposure.spans == ((first, last),)
    assert exposure.days == (last - first).days
    assert exposure.years == pytest.approx(exposure.days / 365.25)


def test_two_touching_intervals_merge_into_one_span():
    days = session_days(400, date(2001, 1, 2))
    market = Market(
        history={"AAA": hist("AAA", [100.0] * 400, days=days)},
        membership=Membership((("AAA", date(2001, 1, 1), date(2001, 7, 1)),
                               ("AAA", date(2001, 7, 1), None))),
        fx=(),
    )
    (exposure,) = survivors(market, window_start=W_START, window_end=W_END)
    assert len(exposure.spans) == 1


def test_a_symbol_with_one_bar_cannot_be_killed():
    days = session_days(1, date(2001, 1, 2))
    market = Market(
        history={"AAA": hist("AAA", [100.0], days=days)},
        membership=Membership((("AAA", date(2001, 1, 1), None),)),
        fx=(),
    )
    assert survivors(market, window_start=W_START, window_end=W_END) == ()


# --------------------------------------------------------------------------- 3. who does die


def test_a_zero_hazard_kills_nobody():
    market = uniform_market(50)
    assert draw_deaths(market, survivors(market, window_start=W_START, window_end=date(2011, 1, 1)),
                       0.0, Random(1)) == ()


def test_the_draw_is_reproducible_from_the_seed_alone():
    market = uniform_market(80)
    pool = survivors(market, window_start=W_START, window_end=date(2011, 1, 1))
    assert draw_deaths(market, pool, 0.05, Random(11)) == draw_deaths(market, pool, 0.05, Random(11))
    assert draw_deaths(market, pool, 0.05, Random(11)) != draw_deaths(market, pool, 0.05, Random(12))


def test_the_same_seed_kills_the_same_names_at_every_assumed_return():
    market = uniform_market(60)
    pool = survivors(market, window_start=W_START, window_end=date(2011, 1, 1))
    _m0, deaths0 = stressed(market, pool, hazard_per_year=0.08, delisting_return=0.0, rng=Random(5))
    _m1, deaths1 = stressed(market, pool, hazard_per_year=0.08, delisting_return=-0.9, rng=Random(5))
    assert deaths0 == deaths1 != ()


def test_the_share_that_dies_matches_the_hazard_it_was_given():
    market = uniform_market(150)
    pool = survivors(market, window_start=W_START, window_end=date(2011, 1, 1))
    expected = 1.0 - np.exp(-0.1 * pool[0].years)
    shares = [len(draw_deaths(market, pool, 0.1, Random(seed))) / len(pool) for seed in range(20)]
    assert float(np.mean(shares)) == pytest.approx(expected, abs=0.05)


def test_every_death_lands_on_a_bar_inside_the_exposure_with_a_later_bar_left():
    market = uniform_market(120)
    pool = survivors(market, window_start=W_START, window_end=date(2011, 1, 1))
    by_symbol = {e.symbol: e for e in pool}
    deaths = draw_deaths(market, pool, 0.3, Random(3))
    assert deaths
    for death in deaths:
        h = market.history[death.symbol]
        assert h.index_of(death.last_bar) is not None  # it is a real bar
        assert death.last_bar < h.dates[-1].item()  # something is always left to force-close
        assert death.last_bar <= by_symbol[death.symbol].spans[-1][1]  # inside the member-time


def test_draw_deaths_refuses_a_bad_rate_or_a_rng_that_is_not_a_Random():
    market = uniform_market(5)
    pool = survivors(market, window_start=W_START, window_end=date(2011, 1, 1))
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        draw_deaths(market, pool, 1.5, Random(0))
    with pytest.raises(TypeError, match="random.Random"):
        draw_deaths(market, pool, 0.1, np.random.default_rng(0))


# --------------------------------------------------------------------------- 3b. the perturbation


def test_kill_truncates_the_history_and_rewrites_the_last_bar():
    market, days = flat_market()
    out = kill(market, (Death("AAA", days[9]),), -0.5)
    h = out.history["AAA"]
    assert len(h) == 10
    assert h.last_date() == days[9]
    bar = out.bar("AAA", days[9])
    assert bar.close == to_decimal(50.0)
    assert bar.open == bar.high == bar.low == bar.close  # flat: nothing can fill above the death
    assert out.bar("AAA", days[10]) is None
    assert list(h.close[:9]) == [100.0] * 9  # every earlier bar is exactly what it was


def test_kill_floors_a_total_loss_at_one_price_quantum():
    market, days = flat_market()
    out = kill(market, (Death("AAA", days[5]),), -1.0)
    assert out.bar("AAA", days[5]).close == to_decimal(MIN_PRICE)


def test_a_zero_return_still_flattens_the_last_bar_but_moves_no_price():
    market, days = flat_market()
    out = kill(market, (Death("AAA", days[5]),), 0.0)
    bar = out.bar("AAA", days[5])
    assert bar.close == to_decimal(100.0)
    assert bar.open == bar.high == bar.low == bar.close


def test_kill_retires_the_symbol_from_the_index_the_day_after_its_last_bar():
    market, days = flat_market()
    out = kill(market, (Death("AAA", days[9]),), -0.3)
    assert out.membership.members_on(days[9]) == frozenset({"AAA", "BBB"})
    assert out.membership.members_on(days[10]) == frozenset({"BBB"})
    assert market.membership.members_on(days[10]) == frozenset({"AAA", "BBB"})  # the original stands


def test_kill_leaves_the_market_it_was_given_untouched():
    market, days = flat_market()
    before = len(market.history["AAA"])
    out = kill(market, (Death("AAA", days[9]),), -0.5)
    assert len(market.history["AAA"]) == before
    assert market.history["AAA"].last_date() == days[-1]
    assert out is not market
    assert out.history["BBB"] is market.history["BBB"]  # untouched symbols are shared, not copied


def test_kill_with_no_deaths_returns_the_same_market():
    market, _days = flat_market()
    assert kill(market, (), -0.5) is market


def test_the_forewarned_variant_spreads_the_loss_over_the_last_sessions():
    market, days = flat_market()
    out = kill(market, (Death("AAA", days[9]),), -0.75, decline_sessions=3)
    h = out.history["AAA"]
    step = 0.25 ** (1 / 3)
    assert float(h.close[-1]) == pytest.approx(25.0)
    assert float(h.close[-2]) == pytest.approx(100.0 * step**2)
    assert float(h.close[-3]) == pytest.approx(100.0 * step)
    assert float(h.high[-3]) > float(h.close[-3])  # the decline bars keep their shape: tradable
    assert float(h.high[-1]) == float(h.close[-1])  # the death bar does not
    assert float(h.close[-4]) == pytest.approx(100.0)


def test_kill_refuses_spy_a_missing_symbol_a_repeat_and_a_bad_return():
    market, days = flat_market(symbols=("AAA", "SPY"))
    with pytest.raises(ValueError, match="SPY cannot be delisted"):
        kill(market, (Death("SPY", days[5]),), -0.5)
    with pytest.raises(ValueError, match="no bars in this market"):
        kill(market, (Death("ZZZ", days[5]),), -0.5)
    with pytest.raises(ValueError, match="two death dates"):
        kill(market, (Death("AAA", days[5]), Death("AAA", days[7])), -0.5)
    with pytest.raises(ValueError, match=r"\[-1, 0\]"):
        kill(market, (Death("AAA", days[5]),), 0.5)
    with pytest.raises(ValueError, match="decline_sessions"):
        kill(market, (Death("AAA", days[5]),), -0.5, decline_sessions=0)


# --------------------------------------------------------------------------- 4. the engine, unchanged


def test_the_engine_force_closes_a_killed_symbol_at_the_rewritten_mark():
    """The whole point: no edit to backtest/ or sim/ is needed for any of this to work.

    AAA is killed on day 9 at -50%. `book_runner` finds it gone on day 10 and
    `sim.book.close_book_unpriced` sells it at its mark -- which is the rewritten close.
    """
    market, days = flat_market(n=20, symbols=("AAA", "BBB"))
    stressed_market = kill(market, (Death("AAA", days[9]),), -0.5)
    params = FixedParams(weights=(("AAA", Decimal("0.4")), ("BBB", Decimal("0.4"))))
    result = run_book(stressed_market, FIXED, params, DAILY_SWITCH,
                      days[1], days[-1], usd_idr=Decimal("16000"))
    forced = [t for t in result.trades if t.exit_reason == "forced"]
    assert [(t.symbol, t.exit_date, t.exit_price) for t in forced] == [
        ("AAA", days[10], to_decimal(50.0))
    ]
    assert sorted(p.symbol for p in result.open_at_end) == ["BBB"]


def test_the_unstressed_market_force_closes_nothing():
    market, days = flat_market(n=20, symbols=("AAA", "BBB"))
    params = FixedParams(weights=(("AAA", Decimal("0.4")), ("BBB", Decimal("0.4"))))
    result = run_book(market, FIXED, params, DAILY_SWITCH,
                      days[1], days[-1], usd_idr=Decimal("16000"))
    assert [t for t in result.trades if t.exit_reason == "forced"] == []


# --------------------------------------------------------------------------- 4b. the read-only guard


def _imported_names() -> set[str]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    return names


def test_the_source_imports_no_lab_module_and_no_database_driver():
    """A harness that cannot import the lab's writer cannot record a trial or move N."""
    names = _imported_names()
    assert not {n for n in names if n.startswith("seer_engine.lab")}, names
    assert not {"sqlite3", "psycopg"} & names, names


def _fresh_python(code: str) -> str:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(seer_engine.__file__).resolve().parent.parent) + os.pathsep + env.get("PYTHONPATH", "")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         env=env, check=True, timeout=180)
    return out.stdout.strip()


def test_importing_the_module_loads_nothing_from_the_lab():
    loaded = _fresh_python(
        "import json, sys; import seer_engine.delisting; "
        "print(json.dumps(sorted(m for m in sys.modules if m.startswith('seer_engine.lab'))))"
    )
    assert json.loads(loaded) == []
```

**Impact:** adds roughly 30 tests, none of which needs Postgres or the research store. The two
`run_book` tests exercise `backtest/` and `sim/` without editing either.

---

## Verification

Every command below is absolute, assumes the worktree, and spells out the two environment
variables the handover §7 insists on. `PYTHONPATH` must point at the **worktree's** `engine/src`
or pytest silently tests the main checkout instead of the branch; `PG_TEST_URL` must be exported or
the suite reports a confident green missing a third of its tests (2812 passed / 385 skipped instead
of 3197 / 0).

**Build (import check):**

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules && \
PYTHONPATH=/home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine/src \
/home/miftah/seer/engine/.venv/bin/python -c \
  "import seer_engine.delisting as d; print(d.WINDOW_START, d.WINDOW_END, len(d.__all__))"
```

Expected: `1996-01-02 2015-10-16 12`.

**Lint:**

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine && \
/home/miftah/seer/engine/.venv/bin/ruff check --no-cache src tests scripts
```

Expected: `All checks passed!`. (The plan index's exit criterion names `src tests`; `scripts` is
added because this phase puts a new file there.)

**The new tests alone:**

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules && \
PG_TEST_URL="${PG_TEST_URL:?export PG_TEST_URL first}" \
PYTHONPATH=/home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests/test_delisting.py -q
```

Expected: all pass, 0 skipped. (These tests need no database; `PG_TEST_URL` is in the line so the
habit never lapses.)

**The full suite:**

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules && \
PG_TEST_URL="${PG_TEST_URL:?export PG_TEST_URL first}" \
PYTHONPATH=/home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests -q
```

Expected: **3197 + (this phase's new tests) passed, 0 failed, 0 skipped.** 3197 is the branch
baseline, re-counted by the reconciler at `ba8a05b`. Phase 4 runs concurrently in this same
worktree and adds 3 more, so a higher total is correct and only `0 failed, 0 skipped` is the
assertion. A non-zero skip count means `PG_TEST_URL` did not reach pytest; fix that before reading
the result. Do **not** pass `-o addopts=...`: it
drops `-n auto` and the suite goes from ~62 s to ~342 s.

**`--help` runs:**

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules && \
PYTHONPATH=/home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine/src \
/home/miftah/seer/engine/.venv/bin/python engine/scripts/delisting_stress.py --help
```

**Smoke run** (the store is gitignored and lives in the MAIN checkout, never in a worktree):

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules && \
SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
PYTHONPATH=/home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine/src \
/home/miftah/seer/engine/.venv/bin/python engine/scripts/delisting_stress.py --smoke
```

Expected shape — one entry, two assumed returns, two seeds; **about 30–45 s on an idle machine and
60–90 s if other swarm sessions are running**, almost all of it `load_store`:

```
delisting stress -- read-only. No lab trial is recorded, ...
store /home/miftah/seer/engine/.research

loaded 539 symbols in 11.3s   fingerprint <12 hex chars>

=== 1. the delisting hazard the store's own membership records ===
window 1996-01-02 .. 2015-10-16  (19.79 years)
ever-members 1041   priced 519   unpriced 522
left the index inside the window: 514   of those unpriced 404, priced 110
mean members on a mid-year date 510.25   member-years 10096
  annual exit hazard, every exit:        5.091%
  annual exit hazard, the unpriced ones: 4.002%

eligible to be killed: 409 priced survivors over 5,416 member-years
injecting at 4.002%/yr (the measured unpriced-exit rate)
  expected deaths, competing risks included: 158.6
  (a memoryless process over the same member-years would give 216.7)

NOT modelled, and no injection can model it: ...

=== 2. the stressed runs ===
1 entries x 2 assumed returns x 2 seeds = 4 runs   (abrupt death)

=== RMW-FR  (M0022-W-TV16) ===
unstressed:   CAGR  +11.68%/yr   worst fall  14.31%   trades  1589   edge over SPY TR  +3.76 pts/yr

  assumed r   deaths     CAGR/yr    worst fall    trades      edge pts/yr  (p10 .. p90)    beats SPY
       +0%    151.0     +10.72%       14.95%       1526       +2.80  ( +2.68 ..  +2.92)         2/2
     -100%    151.0      +8.23%       14.91%       1530       +0.32  ( -0.47 ..  +1.11)         1/2

break-even delisting return: NONE on this grid. The mean edge is still +0.32 pts/yr at
r = -100%, so even a total loss on every injected delisting leaves RMW-FR ahead of
total-return SPY.
  per seed: median -81.5%, p10 -81.5%, p90 -81.5%, and 1 of 2 seeds never break even on this grid

total 0.5 min. delisting stress -- read-only. ...
```

**That block is not an illustration — it is the real output of the planned script, run against the
real store while this plan was written.** Two seeds is far too few to conclude anything from, which
is why phase 2 and not this phase owns the number; but the shape, the hazard block and the
unstressed line are what phase 1 is done when it reproduces.

The three numbers to check against the analysis before trusting anything else: `ever-members 1041 /
priced 519 / unpriced 522`, `5.091%` and `4.002%` (M2), and `unstressed CAGR +11.68%, worst fall
14.31%, trades 1589` (M1 and M3). If any of those three disagrees, the store on disk is not the one
the 110 trials were run against and nothing downstream is comparable.

**Manual check — prove nothing moved.** Run before and after the smoke run and compare:

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules && \
git status --porcelain -- engine/src engine/scripts engine/tests && \
sha256sum /home/miftah/seer/engine/.research/manifest.json lab/lab.sqlite
```

Expected: **scoped to this phase's own paths**, `git status` shows only the three new files; both
checksums are identical before and after. Additionally `python -m seer_engine lab status` must
still report **N = 110** and **0 test-window looks**.

**The scoping is not cosmetic.** This worktree is shared with the other phases of the set running
concurrently, so an unscoped `git status` will show phases 2, 3, 4 and 5's in-flight work and an
unscoped expectation would read as a failure that is not one.

**Commit with an explicit path allowlist** — never `git add -A`, for the same reason:

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules
git add engine/src/seer_engine/delisting.py \
        engine/scripts/delisting_stress.py \
        engine/tests/test_delisting.py
git commit -F - <<'MSG'
feat(delisting): a read-only harness for the break-even delisting return

Injects synthetic delistings into the dev-window ranking universe at the hazard the
research store's own membership records, re-runs a lab candidate against the perturbed
market, and solves for the assumed loss at which the book stops beating total-return
SPY. Three new files; no existing file is touched and the engine needs no change --
book_runner's force-close path already absorbs a mid-window disappearance.

Records no lab trial, moves no config_digest, writes nothing to engine/.research and
spends no test-window look. A test asserts the module imports neither lab.store nor
lab.runner, so it cannot record a trial even by accident.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
git show --stat --name-only HEAD   # must list exactly those three paths
```

**Exit criteria:**

1. `delisting_stress.py --help` runs.
2. The smoke run completes and prints a table whose hazard block reproduces M2 (`5.091%`,
   `4.002%`, 10,096 member-years) and whose unstressed line reproduces M1/M3 for `M0022-W-TV16`.
3. `engine/tests/test_delisting.py` passes; the whole suite passes with `PG_TEST_URL` and 0 skips.
4. `ruff check --no-cache src tests scripts` passes.
5. A test asserts `seer_engine.delisting` imports nothing from `seer_engine.lab`, in its source and
   in a fresh interpreter.
6. `lab status` reports N = 110 and 0 test-window looks; `lab/lab.sqlite` and
   `engine/.research/manifest.json` are byte-identical before and after.
7. `git status --porcelain -- engine/src engine/scripts engine/tests` shows exactly three new
   files and no modified one, and the commit's file list **equals** that three-path allowlist.
   (An unscoped `git status` will also show peer phases' work; the worktree is shared.)

---

## Handoffs

**To phase 2 (R1, the run and the write-up).** Phase 2 is the only consumer of this surface; it
needs nothing from this phase but the `Interface Contract` above and the `--csv` output.

> **Reconciled 2026-10-07.** Phase 2's commands were written against guessed flag names and have
> been corrected to this phase's actual `_parse()`: `--entry` (repeatable, **not** a comma-separated
> `--candidates`), `--hazard unserved` / `--hazard all` rather than rounded numbers, and `--csv` on
> every run so Step 4 reads numbers from a file instead of a terminal. **Phase 1 owns these
> spellings; if the implementer changes one, phase 2's Steps 1, 3 and 3b must change with it** —
> say so loudly rather than letting phase 2 discover it at `--help` time.

Four things this phase found that phase 2 must not re-derive, and must not let a reader conflate:

1. **The `r = 0` row is not the unstressed row, and the gap between them is not small.** Measured
   by the planned script itself, `M0022-W-TV16`, two seeds: unstressed CAGR 11.68%/yr; at `r = 0`
   — every delisted holder paid the last price anyone saw, which is what every recorded backtest
   already assumes — 10.72%/yr. **About one point of CAGR a year is the cost of thinning the
   ranking pool alone, before any delisting loss is assumed.** Phase 2 must report that as its own
   number. It is not a loss on a delisting; it is the price of having 151 fewer names to choose
   from over twenty years, and it is a large share of everything this test moves.
2. **The break-even is likely to be off the bottom of the grid, and that is the finding.** Same
   candidate and seeds: at `r = -100%` — a total loss on every injected delisting — CAGR is
   8.23%/yr against SPY's total-return 7.92%/yr, a mean edge of **+0.32 points a year**, still
   positive. One of the two seeds did cross (at −81.5%) and the other did not, so the answer at
   two seeds is genuinely on the knife edge and a hundred seeds will settle it. If the mean holds,
   R1's honest answer to "how bad must the delisting return be before the edge vanishes" is *"worse
   than a total loss on every injected name"* — which is both a strong result and a plain-language
   one. The solver prints that case rather than extrapolating past its data. Phase 2 should expect
   a close call on RMW-FR and should report the per-seed spread, not only the mean.
3. **The hazard applies to 409 survivors over 5,416 member-years, not to the whole index.** At
   4.0%/yr with competing risks that is 158.6 expected deaths per seed (151 realised at seed 0),
   against the 404 unpriced exits history actually had. The harness injects the historical *rate*
   into the universe the backtest can actually rank; it does not restore the historical *count*,
   and it cannot, because there are only 409 names left to kill. Phase 2 must say so in the
   design-doc section rather than let a reader read 151 as "the missing 404".
4. **The 118 names that were still index members at `DEV_END` and have no bars at all are outside
   every version of this test.** The script prints that paragraph on every run so it cannot be lost
   between the harness and the write-up.

**Left for somebody else, deliberately not done here:**

- **No engine change, and none is needed.** The force-close path at `book_runner.py:317-326` →
  `sim/book.py:742` already models a delisting at exactly `r = 0`. P3 proves a mid-window
  disappearance runs clean through the unchanged engine. Had one been needed this plan would have
  said so loudly instead of planning it; it was not.
- **No `--jobs` default above 1.** Memory was measured (942 MB shared store, ~70 MB per prepared
  panel), so `--jobs 6` is safe on this machine, but the default stays 1 so that a careless run on
  a smaller box cannot swap. Phase 2 should pass `--jobs 6` and watch RSS once.
- **No roster entry is judged here.** Phase 5 does that, under phase 3's rule.
- **`survivorship_coverage.py` is untouched**, even though `spy_total_return` and `cagr_and_fall`
  look reusable: this harness takes its SPY comparison from `DevRow.spy_tr`, which is the same
  `benchmark.spy_curves` both go through, and refactoring a committed precedent harness is scope
  creep. If a later phase wants a shared module for the two scripts, that is a new phase.

---

## Rollback

```bash
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules && \
rm -f engine/src/seer_engine/delisting.py \
      engine/scripts/delisting_stress.py \
      engine/tests/test_delisting.py
```

Three new files, nothing else. No existing file is modified, no migration is run, no database row
is written, no `config_digest` moves and no trial is recorded, so there is nothing to repair in the
lab's record and nothing in `engine/.research` to rebuild. If the phase was already committed,
`git revert` the commit; the tree returns to `3683d7b`'s behaviour exactly.
