> Adopted from `/home/miftah/seer/.workflows/orchestration/random-twin-yardstick/PLAN.md` phase 2. Source: `.workflows/plan/random-twin-yardstick/phase-2.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 2: The random-twin engine

**Plan set:** `RANDOM_TWIN_YARDSTICK_PLAN.md`
**Analysis:** `.workflows/analyze/20261113-125454-Y7RT_code_analyzer.md`
**Satisfies:** R1 — a few hundred no-skill books of the arm's own shape, measured once, counting against nothing (the engine half: a pure function from an arm and a market to a `Measurement`)
**Criteria:** R1.1, R1.3, R1.4, R1.5
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab`

---

## Goal

A new pure module `lab/yardstick.py` can take any book-engine dev arm, run it once while recording
every allocator decision, replay those decisions `draws` times with every picked name swapped for a
random index member of similar trading size, and return a `Measurement`: the share of twins the arm
out-earned, the twins' shape relative to the arm, and a status (`measured`, `unmatched`,
`not-applicable`). The result is a pure function of (candidate, market, capital, contributions) and
is identical for every `jobs` value. Nothing is written anywhere: phase 3 stores it, phase 4 gates on it.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates (all in `engine/src/seer_engine/lab/yardstick.py`, a new file):**

- `RULE_ID: str = "yardstick-v1"`, `DRAWS: int = 200`, `LIQUIDITY_BARS: int = 63`, `NEIGHBOUR_RANKS: int = 25`, `REPRODUCE_TOLERANCE: float = 1e-9`
- `STATUS_MEASURED = "measured"`, `STATUS_NOT_APPLICABLE = "not-applicable"`, `STATUS_UNMATCHED = "unmatched"`, `STATUSES: tuple[str, ...]` (those three, in that order)
- `@dataclass(frozen=True) class Decision(data_date: date, members: frozenset[str], targets: tuple[Target, ...], rank: bool = True)`
- `class Recorder(inner: Allocator, rules: TradeRules)` — an `Allocator` (and `MarketAware`) with `.decisions -> tuple[Decision, ...]`
- `class Replay(inner: Allocator, schedule: Mapping[date, Sequence[Target]], seed: int | None = None)` — an `Allocator`; `id` is `"yardstick-v1-replay"` when `seed` is None, else `f"yardstick-v1-twin-{seed:016x}"`
- `def seed_for(config_digest: str, i: int) -> int`
- `def fixed_symbols(candidate: Candidate) -> frozenset[str]`
- `def record(market, dividends, spy_dividends, candidate, *, initial_idr: Decimal, contributions: ContributionSchedule | None) -> tuple[tuple[Decision, ...], DevRow]`
- `def twin_schedule(market: Market, decisions: Sequence[Decision], fixed: AbstractSet[str], seed: int, *, ranks: dict[date, tuple[tuple[str, float], ...]] | None = None) -> dict[date, tuple[Target, ...]]`
- `@dataclass(frozen=True) class Measurement(status: str, draws: int, arm_rate: float | None, beaten: int, percentile: float | None, rates: tuple[float, ...], trade_ratio: float | None, turnover_ratio: float | None, reproduced: bool | None)`
- `class Unreproducible(Exception)`
- `def measure(market: Market, dividends: DividendMap, spy_dividends: Sequence[Dividend], candidate: Candidate, *, initial_idr: Decimal, contributions: ContributionSchedule | None, draws: int = DRAWS, jobs: int = 1, expect: tuple[int, float | None] | None = None) -> Measurement`
- `engine/tests/test_lab_yardstick.py` (new)

**Signature changes against the index's Interface Contract (additive; flagged for the reconciler):**

- `Decision` gains a fourth field `rank: bool = True`, and `Recorder` takes `rules` as its second
  argument. Reason: on a resize-only session `book_runner.run_book` (book_runner.py:432-436) reads
  only the *total weight* of the allocator's answer (`_rescaled`, book_runner.py:148-195), never its
  symbols. Without the flag, a resize call whose fresh ranking drops a held name would end that
  name's spell and redraw its twin at the next rank, which trades a twin the real book never trades.
- `twin_schedule` gains a keyword-only `ranks` cache (default None). Liquidity ranks depend on the
  date and the members only, not on the seed, so `measure` computes them once for all draws.
- New public names not in the index: `fixed_symbols`, `record`, `STATUSES`, `REPRODUCE_TOLERANCE`.
  Phase 3/4 may use `STATUSES`; nobody is required to.

**Field semantics phases 3, 4 and 5 rely on:**

| Field | `measured` / `unmatched` | `not-applicable` |
|---|---|---|
| `draws` | number of twins simulated (= the `draws` argument) | `0` |
| `arm_rate` | the arm's money-weighted return when funded, else CAGR (`dev.make_row`'s rule, dev.py:463); None only if the run has neither | same; None for a bracket arm (it is not run) |
| `beaten` | twins whose rate is strictly below `arm_rate` (ties and unknown rates count against the arm) | `0` |
| `percentile` | `beaten / draws` | `None` |
| `rates` | sorted twin rates (twins with no rate left out) | `()` |
| `trade_ratio`, `turnover_ratio` | median twin trades (turnover) / the arm's; None when the arm's is 0 | `None` |
| `reproduced` | `True` when `expect` was given and matched; `None` when `expect` was None | same; `None` for a bracket arm |

`status == STATUS_UNMATCHED` exactly when a non-None ratio lies outside
`control_shape.REFUSE_BAND` (inclusive edges, as `control_shape.band_verdict`). A None ratio is
unknown and never refuses, the convention `control_shape._ratio` (control_shape.py:713) set.

**Requires (from earlier phases):** nothing.
**Leaves alone (owned by others):** `lab/store.py`, `lab/runner.py`, `commands/` (phases 1, 3, 4);
`lab/control_draw.py`, `lab/control_weight.py`, `lab/control_shape.py` (imported, never edited);
`lab/hardgate.py` (phase 4); every `lab/methods/*.py`; `web/` (phase 5); `.claude/skills/verify-seer/features/lab-cli.md` (phases 1, 3, 4).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/yardstick.py` | create (line 1) | the whole module: constants, `Decision`, `Recorder`, `Replay`, the draw, `twin_schedule`, `record`, `measure` |
| `engine/tests/test_lab_yardstick.py` | create (line 1) | synthetic-market tests for every claim below |

No existing file is modified.

## Implementation Steps

### Step 1: Set up the worktree's own environment
**File:** `engine/.venv` (not committed)
**Change:** every seer worktree needs its own venv; main's venv tests the wrong tree.
**Code:**
```bash
cd /home/miftah/.worktrees/seer/random-twin-yardstick
python3.11 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'
```
**Impact:** none on the tree.

### Step 2: Create the module
**File:** `engine/src/seer_engine/lab/yardstick.py:1` (new)
**Change:** the complete module below. Facts it is built on, read in the code this session:

- `run_book` calls `allocator.targets_prepared(prepared, members, data_date, mine, params)` (or
  `targets(...)` when `prepared is None`) once per rank or resize session (book_runner.py:421-428);
  `data_date` is the previous session, so the session is `dates.next_session(data_date)` and
  `rank = is_rank_session(rules, session)` (kickoff is None on every dev run).
- On a resize-only session the runner keeps `last_rank` and uses only `sum(fresh weights)`
  (book_runner.py:432-436, 175-195). The idle target is appended by the runner; an allocator that
  targets the idle symbol is a ValueError (book_runner.py:211-213).
- `Target(symbol, weight, last, limit=None, stop=None, take=None)` (sim/book.py:220): prices are
  quantized to 4 dp and `stop < ref < take` with `ref = limit or last`, else ValueError. `last` is
  the sizing price (`_desired_shares(equity, t.weight, t.last, rules)`, sim/book.py:674-779) and
  the reference for `open_limit` (`q(t.last × (1 + OPEN_LIMIT_BAND))`, sim/book.py:485-490).
- `dev.run_candidate(market, dividends, spy_dividends, c, *, prepared, window, initial_idr,
  contributions, contribution_fx)` (dev.py:607); with `prepared=None` the runner re-cuts every
  history on every decision, so both the recorder and the replay are always given a non-None
  `prepared`. `candidate_window` reads `allocator.lookback/symbols/uses_members(params)` (dev.py:250),
  so a replay that delegates those gets the identical window.
- `Candidate.__post_init__` (dev.py:216) requires a non-bracket arm's allocator to pass
  `isinstance(x, Allocator)`, so `Recorder` and `Replay` implement every protocol member.
- `prepare_for(obj, market)` (allocator.py:116) dispatches on attribute presence of
  `prepare_market`; `Recorder` always defines it and forwards to `prepare_for(inner, market)`, so
  a plain inner allocator still gets `prepare(market.history)` and a `MarketAware` one gets
  `prepare_market(market)`.
- `trials.trades` is `int(row.stats.metrics.trades)` and `trials.total_return` is
  `float(row.stats.metrics.total_return)`; `trials.turnover` is `row.stats.turnover`
  (runner.py:627-634).

**Code:**
```python
"""The random-twin yardstick: what a no-skill book of exactly this arm's shape would have earned.

WHY A TWIN AND NOT A RANDOM BOOK PER "SETUP". The request was a distribution of random books per
setup -- pool, book size, cadence, weighting, safety switch. The lab has no machine-readable setup:
every method file defines its own allocator and its own params dataclass, so nothing can enumerate
those five for an arbitrary arm. What every book-engine arm does expose, uniformly, is its sequence
of decisions: ``book_runner.run_book`` asks the allocator for targets on each rank or resize
session and gets ``Target(symbol, weight, last, limit, stop, take)`` values back. A twin replays
those decisions with every *picked* name swapped for a random index member of similar trading size.
It therefore has the arm's decision dates, weights, entries, exits, cash months and safety switch
by construction, for any allocator and with no per-method code: the setup is matched because it is
copied, not described. The code analysis of 2026-11-13 (session 20261113-125454-Y7RT) measured the
premise on M0562-W60-B100: recording the allocator and replaying the record reproduced the plain run
exactly. ``test_lab_yardstick`` re-proves it on every run, on a synthetic market.

This is not ``lab.twins``. That module finds *repeated* books among recorded arms; this one builds
random ones.

WHAT IS PICKED AND WHAT IS FIXED. A target is fixed -- copied into the twin unchanged -- when its
symbol is one the allocator declares it may hold or read (``holds(params)``, ``symbols(params)``),
SPY, or the rules' idle instrument. Everything else is a name the arm *picked* from the pool, and
only picks are what the yardstick asks about: an ETF-only or cash-only arm has no picks, reads
``not-applicable`` and simulates no twin. So does a bracket (``DESIGN_V0``) arm: it has no book
decisions to replay.

RESIZE DECISIONS PASS THROUGH. On a resize-only session ``run_book`` keeps the last rank session's
basket and uses only the *total weight* of the allocator's fresh answer (``_rescaled``). The
symbols of that answer are never traded, so the twin keeps them exactly as recorded, and holding
spells are tracked across *rank* decisions only. Treating a resize answer as a re-pick would end a
spell whenever the fresh ranking dropped a held name and trade a twin the real book never traded.

THE DRAW. At the rank decision where a picked name X enters the book (it was not in the previous
rank decision's targets) X gets a twin: the decision's index members with at least
``LIQUIDITY_BARS`` bars on or before the data date are ranked by the median of close x volume over
their trailing ``LIQUIDITY_BARS`` bars (most traded first, ties by symbol); the candidates are the
members within ``NEIGHBOUR_RANKS`` ranks of X's own rank (X's rank where its own trailing dollar
volume would sit when X is not a rankable member; the whole ranked list when X has no bars at all);
names the twin book already holds, names the arm picks at this decision and fixed symbols are
excluded; and the candidate with the smallest blake2b hash of (``RULE_ID``, seed, X, the decision's
month, candidate) that has a bar on the data date wins. When the neighbourhood has no usable
candidate the whole ranked list is used; when that has none either it is a ValueError, never a
silent fallback to X. When no member at all has ``LIQUIDITY_BARS`` bars (a window that opens right
at the start of the store) the members are ranked on the bars they have.

The twin keeps its name for the whole spell -- every later rank decision that still targets X --
and is redrawn only at a decision where it has no bar on the data date (or its scaled prices cannot
form a valid ``Target``). Each twin target copies X's weight; its ``last`` is the twin's own close on
the data date, and ``limit``, ``stop`` and ``take``, when present, are scaled by twin last / X's
last, so a limit 2% under X's close is a limit 2% under the twin's.

WHAT "NONE OF ITS NAMES" CAN AND CANNOT GUARANTEE. The neighbour pool is the same index the arm
picks from, so it overlaps the real book by design. What holds by construction:

- at the rank decision where a twin is drawn, it is none of the names the arm picks at that same
  decision, and never X itself;
- at every rank decision, the twin's targets have unique symbols, none of them a fixed symbol, and
  every substituted name is an index member of that decision with a bar on its data date.

What cannot be guaranteed: a twin kept for a spell can later coincide with a name the arm newly
picks (the arm buys T while the twin book still holds T as X's stand-in; T's own twin is then
drawn elsewhere), and across the whole run twins can and do hold names the arm held at other
times. Forbidding either would shrink the pool exactly where the arm is concentrated and make the
"random" book systematically avoid what the arm likes.

THE STATISTIC. Each twin is run through ``dev.run_candidate`` at the arm's capital and
contributions, and judged on the rate ``dev.make_row`` ranks on: the money-weighted return when
funded, else CAGR. ``beaten`` counts twins strictly below the arm; ties and twins with no rate count
against the arm. The twins' median trade count and turnover are compared with the arm's; outside
``control_shape.REFUSE_BAND`` the reading is ``unmatched``, because a twin that trades twice as
often is paying a different cost and the comparison stops being about the picks.

DETERMINISM. Seeds are ``seed_for(config_digest(candidate), i)``: no clock, no global random state,
no dependence on which trial row asked. With ``jobs > 1`` the twins run in forked processes (the
market is already in memory, so nothing large is pickled) and results are collected by seed index,
never by completion order, so every ``jobs`` value gives the identical ``Measurement``.

PURE. No database, no ``lab.store``, no clock, no network. The caller loads the market and decides
what to do with the result.
"""

from __future__ import annotations

import hashlib
import math
import multiprocessing
import statistics
from bisect import bisect_left, bisect_right
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any, NamedTuple

import numpy as np

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend
from seer_engine.backtest.book_runner import DividendMap
from seer_engine.backtest.dev import Candidate, DevRow, run_candidate
from seer_engine.backtest.market import SPY, Market
from seer_engine.lab import method as lab_method
from seer_engine.lab.control_shape import REFUSE_BAND
from seer_engine.sim import q
from seer_engine.sim.book import Target
from seer_engine.sim.contributions import ContributionSchedule
from seer_engine.sim.rules import TradeRules, is_bracket, is_rank_session
from seer_engine.strategies.allocator import Allocator, prepare_for
from seer_engine.strategies.base import History, as_day

RULE_ID = "yardstick-v1"
"""The draw rule's name. Phase 3 keys stored readings on it: any change to the draw, the ranking or
the statistic is a new id, never an edit, so an old reading is never compared with a new one."""

DRAWS = 200
"""Twins per measurement: "a few hundred random books". One twin moves the percentile by 0.005."""

LIQUIDITY_BARS = 63
"""Trading size is the median dollar volume over this many trailing bars (a quarter of sessions)."""

NEIGHBOUR_RANKS = 25
"""A twin is drawn from the members within this many liquidity ranks of the real pick."""

REPRODUCE_TOLERANCE = 1e-9
"""How far a re-run's total return may sit from the recorded one and still be the same run."""

STATUS_MEASURED = "measured"
STATUS_NOT_APPLICABLE = "not-applicable"
STATUS_UNMATCHED = "unmatched"
STATUSES: tuple[str, ...] = (STATUS_MEASURED, STATUS_NOT_APPLICABLE, STATUS_UNMATCHED)


class Unreproducible(Exception):
    """Re-running the arm did not give its recorded trade count and total return.

    A twin replays the decisions of *this* run. If this run is not the recorded one -- a different
    store, capital or funding -- the yardstick would measure a book nobody recorded, so the caller
    is refused instead of being handed a number about something else.
    """


@dataclass(frozen=True)
class Decision:
    """One allocator call the arm made: its data date, the index members it was shown, its answer.

    ``rank`` is False for a resize-only session, whose answer the runner reads for its total weight
    alone (see the module docstring).
    """

    data_date: date
    members: frozenset[str]
    targets: tuple[Target, ...]
    rank: bool = True


@dataclass(frozen=True)
class Measurement:
    """One yardstick reading of one arm. See the module docstring for every field's meaning.

    The constructor refuses contradictory readings: a not-applicable reading carries no twin
    figures, and a measured or unmatched one has at least one twin and a percentile that is exactly
    ``beaten / draws``.
    """

    status: str
    draws: int
    arm_rate: float | None
    beaten: int
    percentile: float | None
    rates: tuple[float, ...]
    trade_ratio: float | None
    turnover_ratio: float | None
    reproduced: bool | None

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}, got {self.status!r}")
        if self.status == STATUS_NOT_APPLICABLE:
            if (
                self.draws != 0
                or self.beaten != 0
                or self.percentile is not None
                or self.rates
                or self.trade_ratio is not None
                or self.turnover_ratio is not None
            ):
                raise ValueError("a not-applicable reading simulates no twin and carries no twin figures")
            return
        if self.draws < 1:
            raise ValueError(f"a {self.status} reading needs at least one twin, got draws={self.draws}")
        if not 0 <= self.beaten <= self.draws:
            raise ValueError(f"beaten must be in [0, {self.draws}], got {self.beaten}")
        if self.percentile != self.beaten / self.draws:
            raise ValueError(f"percentile must be beaten / draws, got {self.percentile!r}")
        if len(self.rates) > self.draws:
            raise ValueError(f"{len(self.rates)} rates for {self.draws} twins")


# --------------------------------------------------------------------------- record and replay


class Recorder:
    """An ``Allocator`` that answers exactly as ``inner`` does and logs every answer as a ``Decision``.

    Every protocol member is delegated, so the run it sits in is the arm's own run, byte for byte.
    It always defines ``prepare_market`` and forwards it to ``prepare_for(inner, market)``: a plain
    inner allocator still gets ``prepare(market.history)``, a ``MarketAware`` one gets
    ``prepare_market(market)``. ``id`` is the inner id, so the result carries the arm's own id.
    """

    def __init__(self, inner: Allocator, rules: TradeRules) -> None:
        if not isinstance(inner, Allocator):
            raise TypeError(f"inner must be an Allocator, got {type(inner).__name__}")
        if not isinstance(rules, TradeRules):
            raise TypeError(f"rules must be a TradeRules, got {type(rules).__name__}")
        self.id = inner.id
        self._inner = inner
        self._rules = rules
        self._log: list[Decision] = []

    @property
    def decisions(self) -> tuple[Decision, ...]:
        return tuple(self._log)

    def lookback(self, params: Any) -> int:
        return self._inner.lookback(params)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return self._inner.symbols(params)

    def holds(self, params: Any) -> tuple[str, ...]:
        return self._inner.holds(params)

    def uses_members(self, params: Any) -> bool:
        return self._inner.uses_members(params)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return self._inner.prepare(history)

    def prepare_market(self, market: Market) -> Any:
        return prepare_for(self._inner, market)

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        return self._note(data_date, members, self._inner.targets(history, members, data_date, held, params))

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        return self._note(
            data_date, members, self._inner.targets_prepared(prepared, members, data_date, held, params)
        )

    def _note(self, data_date: date, members: AbstractSet[str], wanted: Sequence[Target]) -> tuple[Target, ...]:
        out = tuple(wanted)
        rank = is_rank_session(self._rules, dates.next_session(data_date))
        self._log.append(Decision(data_date=data_date, members=frozenset(members), targets=out, rank=rank))
        return out


class Replay:
    """An ``Allocator`` that answers every call with the schedule entry dated on or before it.

    ``lookback``, ``symbols``, ``holds`` and ``uses_members`` are the real allocator's, so
    ``dev.candidate_window`` gives the replay the arm's own window. ``prepare`` returns the schedule
    itself -- never None -- so ``run_book`` takes the prepared path and never re-cuts every history
    on every decision. ``id`` is unique per seed because ``dev.run_registry`` refuses two different
    objects that share one.
    """

    def __init__(
        self, inner: Allocator, schedule: Mapping[date, Sequence[Target]], seed: int | None = None
    ) -> None:
        if not isinstance(inner, Allocator):
            raise TypeError(f"inner must be an Allocator, got {type(inner).__name__}")
        self.id = f"{RULE_ID}-replay" if seed is None else f"{RULE_ID}-twin-{seed:016x}"
        self._inner = inner
        days = sorted(schedule)
        self._days: tuple[date, ...] = tuple(days)
        self._answers: tuple[tuple[Target, ...], ...] = tuple(tuple(schedule[d]) for d in days)

    def lookback(self, params: Any) -> int:
        return self._inner.lookback(params)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return self._inner.symbols(params)

    def holds(self, params: Any) -> tuple[str, ...]:
        return self._inner.holds(params)

    def uses_members(self, params: Any) -> bool:
        return self._inner.uses_members(params)

    def prepare(self, history: Mapping[str, History]) -> Any:
        return self._answers

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        return self._at(data_date)

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        return self._at(data_date)

    def _at(self, data_date: date) -> tuple[Target, ...]:
        i = bisect_right(self._days, data_date) - 1
        return () if i < 0 else self._answers[i]


def record(
    market: Market,
    dividends: DividendMap,
    spy_dividends: Sequence[Dividend],
    candidate: Candidate,
    *,
    initial_idr: Decimal,
    contributions: ContributionSchedule | None,
) -> tuple[tuple[Decision, ...], DevRow]:
    """Run ``candidate`` once, as ``lab run`` does, and return its decisions and its ``DevRow``.

    The allocator is wrapped in a ``Recorder`` and prepared through ``prepare_for``, which is what
    ``dev.run_registry`` does for a recorded trial; the run is therefore the recorded run.
    """
    recorder = Recorder(candidate.allocator, candidate.rules)
    arm = replace(candidate, allocator=recorder)
    _, row = run_candidate(
        market,
        dividends,
        spy_dividends,
        arm,
        prepared=prepare_for(recorder, market),
        initial_idr=initial_idr,
        contributions=contributions,
    )
    return recorder.decisions, row


# --------------------------------------------------------------------------- the draw


def _hash(*parts: str) -> int:
    digest = hashlib.blake2b("|".join((RULE_ID, *parts)).encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def seed_for(config_digest: str, i: int) -> int:
    """The ``i``-th twin's seed for the arm whose ``lab.method.config_digest`` is ``config_digest``.

    A pure function of the arm's configuration, so two runs of the same arm on the same store draw
    the same twins, whoever asks and whenever.
    """
    if not isinstance(config_digest, str) or not config_digest:
        raise ValueError("config_digest must be a non-empty str")
    if isinstance(i, bool) or not isinstance(i, int) or i < 0:
        raise ValueError(f"i must be an int >= 0, got {i!r}")
    return _hash("seed", config_digest, str(i))


def _draw_order(seed: int, real: str, month: str, pool: Sequence[str]) -> list[str]:
    """``pool`` in draw order for ``real``'s twin: ascending hash, ties by symbol."""
    return sorted(pool, key=lambda name: (_hash("draw", str(seed), real, month, name), name))


def fixed_symbols(candidate: Candidate) -> frozenset[str]:
    """The symbols a twin never substitutes: what the allocator declares, SPY and the idle instrument."""
    if is_bracket(candidate.rules):
        raise ValueError(f"{candidate.id}: a bracket arm has no book decisions to replay")
    allocator, params = candidate.allocator, candidate.params
    out = set(allocator.holds(params)) | set(allocator.symbols(params)) | {SPY}
    if candidate.rules.idle_symbol is not None:
        out.add(candidate.rules.idle_symbol)
    return frozenset(out)


def _dollar_volume(h: History | None, day: np.datetime64, need: int) -> float | None:
    """Median close x volume over the trailing ``LIQUIDITY_BARS`` bars dated on or before ``day``.

    None when the symbol has fewer than ``need`` such bars or the median is not finite.
    """
    if h is None:
        return None
    end = int(np.searchsorted(h.dates, day, side="right"))
    if end < need:
        return None
    start = max(0, end - LIQUIDITY_BARS)
    value = float(np.median(h.close[start:end] * h.volume[start:end]))
    return value if math.isfinite(value) else None


def _ranked(market: Market, members: AbstractSet[str], d: date) -> tuple[tuple[str, float], ...]:
    """``members`` by trailing median dollar volume on ``d``, most traded first, ties by symbol.

    Only members with ``LIQUIDITY_BARS`` bars count; when none has that many, every member with at
    least one bar does (a window that opens at the very start of the store).
    """
    day = as_day(d)
    for need in (LIQUIDITY_BARS, 1):
        rows: list[tuple[float, str]] = []
        for symbol in members:
            dv = _dollar_volume(market.history.get(symbol), day, need)
            if dv is not None:
                rows.append((-dv, symbol))
        if rows:
            rows.sort()
            return tuple((symbol, -neg) for neg, symbol in rows)
    return ()


def _position(market: Market, ranked: tuple[tuple[str, float], ...], real: str, d: date) -> int | None:
    """``real``'s rank in ``ranked``, or where its own dollar volume would sit, or None without bars."""
    for i, (symbol, _) in enumerate(ranked):
        if symbol == real:
            return i
    own = _dollar_volume(market.history.get(real), as_day(d), 1)
    if own is None:
        return None
    return bisect_left([(-dv, symbol) for symbol, dv in ranked], (-own, real))


def _scaled(price: Decimal | None, ratio: Decimal) -> Decimal | None:
    return None if price is None else q(price * ratio)


def _twin_target(market: Market, real: Target, twin: str, d: date) -> Target | None:
    """``real`` re-pointed at ``twin``: same weight, the twin's own close, prices scaled; or None.

    None when ``twin`` has no bar on ``d`` or the scaled prices cannot form a valid ``Target``
    (a price that rounds to zero, a stop or take that no longer brackets the reference).
    """
    bar = market.bar(twin, d)
    if bar is None:
        return None
    last = q(bar.close)
    ratio = last / real.last
    try:
        return Target(
            symbol=twin,
            weight=real.weight,
            last=last,
            limit=_scaled(real.limit, ratio),
            stop=_scaled(real.stop, ratio),
            take=_scaled(real.take, ratio),
        )
    except ValueError:
        return None


def _draw(
    market: Market,
    decision: Decision,
    real: Target,
    seed: int,
    excluded: AbstractSet[str],
    ranks: dict[date, tuple[tuple[str, float], ...]],
) -> Target:
    """A fresh twin target for ``real`` at ``decision`` (see THE DRAW in the module docstring)."""
    d = decision.data_date
    ranked = ranks.get(d)
    if ranked is None:
        ranked = _ranked(market, decision.members, d)
        ranks[d] = ranked
    everyone = [symbol for symbol, _ in ranked]
    pos = _position(market, ranked, real.symbol, d)
    near = everyone if pos is None else everyone[max(0, pos - NEIGHBOUR_RANKS) : pos + NEIGHBOUR_RANKS + 1]
    month = f"{d.year:04d}-{d.month:02d}"
    for pool in (near, everyone):
        for name in _draw_order(seed, real.symbol, month, [s for s in pool if s not in excluded]):
            built = _twin_target(market, real, name, d)
            if built is not None:
                return built
    raise ValueError(
        f"no index member on {d} can stand in for {real.symbol}: every ranked member is excluded "
        "or has no usable bar that day"
    )


def twin_schedule(
    market: Market,
    decisions: Sequence[Decision],
    fixed: AbstractSet[str],
    seed: int,
    *,
    ranks: dict[date, tuple[tuple[str, float], ...]] | None = None,
) -> dict[date, tuple[Target, ...]]:
    """The twin's answer for every recorded decision date, for one seed.

    Same dates, same weights in the same rank order; on every rank decision each picked target is
    replaced by its twin, and resize decisions are copied unchanged (see the module docstring for the
    spell rule and exactly what the substitution guarantees). ``ranks`` caches the liquidity ranking
    per date; it depends on the market and the members only, so one cache serves every seed.
    """
    if ranks is None:
        ranks = {}
    fixed = frozenset(fixed)
    ordered = sorted(decisions, key=lambda x: x.data_date)
    if len({x.data_date for x in ordered}) != len(ordered):
        raise ValueError("two decisions share a data date; a run asks its allocator once per session")
    out: dict[date, tuple[Target, ...]] = {}
    spells: dict[str, str] = {}  # real picked name -> its twin, as of the last rank decision
    for decision in ordered:
        d = decision.data_date
        if not decision.rank:
            out[d] = decision.targets
            continue
        picked = [t for t in decision.targets if t.symbol not in fixed]
        real_names = frozenset(t.symbol for t in picked)
        twins: dict[str, Target] = {}
        taken: set[str] = set()
        for t in picked:  # continuing spells keep their twin while it still trades
            name = spells.get(t.symbol)
            if name is None or name in taken:
                continue
            kept = _twin_target(market, t, name, d)
            if kept is not None:
                twins[t.symbol] = kept
                taken.add(name)
        for t in picked:  # new spells, and spells whose twin stopped trading, draw in rank order
            if t.symbol in twins:
                continue
            drawn = _draw(market, decision, t, seed, fixed | real_names | taken, ranks)
            twins[t.symbol] = drawn
            taken.add(drawn.symbol)
        spells = {real: twin.symbol for real, twin in twins.items()}
        out[d] = tuple(t if t.symbol in fixed else twins[t.symbol] for t in decision.targets)
    return out


def _draw_decisions(decisions: Sequence[Decision], fixed: AbstractSet[str]) -> list[Decision]:
    """The rank decisions at which a picked name enters the book: where twins are certainly drawn.

    Empty exactly when no rank decision holds a picked name, which is what not-applicable means.
    """
    out: list[Decision] = []
    previous: frozenset[str] = frozenset()
    for decision in sorted(decisions, key=lambda x: x.data_date):
        if not decision.rank:
            continue
        picked = frozenset(t.symbol for t in decision.targets if t.symbol not in fixed)
        if picked - previous:
            out.append(decision)
        previous = picked
    return out


# --------------------------------------------------------------------------- measuring


class _Outcome(NamedTuple):
    rate: float | None
    trades: int
    turnover: float | None


@dataclass(frozen=True, eq=False)
class _Work:
    """Everything one twin run needs. Inherited by forked workers, never pickled."""

    market: Market
    dividends: DividendMap
    spy_dividends: tuple[Dividend, ...]
    candidate: Candidate
    initial_idr: Decimal
    contributions: ContributionSchedule | None
    decisions: tuple[Decision, ...]
    fixed: frozenset[str]
    ranks: dict[date, tuple[tuple[str, float], ...]]


def _float(x: Any) -> float | None:
    return None if x is None else float(x)


def _rate(row: DevRow) -> float | None:
    """The rate ``dev.make_row`` ranks on: money-weighted return when funded, else CAGR."""
    m = row.stats.metrics
    return _float(m.cagr if m.mwr is None else m.mwr)


def _outcome(row: DevRow) -> _Outcome:
    return _Outcome(rate=_rate(row), trades=int(row.stats.metrics.trades), turnover=_float(row.stats.turnover))


def _twin_outcome(work: _Work, seed: int) -> _Outcome:
    """Build seed's twin schedule, run it at the arm's capital and funding, and read it."""
    schedule = twin_schedule(work.market, work.decisions, work.fixed, seed, ranks=work.ranks)
    replay = Replay(work.candidate.allocator, schedule, seed=seed)
    twin = replace(work.candidate, allocator=replay)
    _, row = run_candidate(
        work.market,
        work.dividends,
        work.spy_dividends,
        twin,
        prepared=prepare_for(replay, work.market),
        initial_idr=work.initial_idr,
        contributions=work.contributions,
    )
    return _outcome(row)


_CHILD_WORK: _Work | None = None  # set only inside a forked worker, by _adopt


def _adopt(work: _Work) -> None:
    global _CHILD_WORK
    _CHILD_WORK = work


def _twin_in_child(seed: int) -> _Outcome:
    if _CHILD_WORK is None:
        raise RuntimeError("a yardstick worker ran before it was handed its work")
    return _twin_outcome(_CHILD_WORK, seed)


def _outcomes(work: _Work, seeds: Sequence[int], jobs: int) -> list[_Outcome]:
    """One outcome per seed, in seed order, whatever ``jobs`` is.

    ``jobs > 1`` forks workers after the market is in memory (copy-on-write; the work is passed as
    the pool initializer's argument, which a fork does not pickle). ``Pool.map`` returns results in
    input order, so completion order can never reach the result.
    """
    if jobs == 1 or len(seeds) == 1:
        return [_twin_outcome(work, seed) for seed in seeds]
    procs = min(jobs, len(seeds))
    ctx = multiprocessing.get_context("fork")
    with ctx.Pool(processes=procs, initializer=_adopt, initargs=(work,)) as pool:
        return pool.map(_twin_in_child, list(seeds), chunksize=max(1, len(seeds) // (procs * 4)))


def _ratio(mine: float | None, theirs: float | None) -> float | None:
    """``mine / theirs``; None when either is unknown or ``theirs`` is zero (undefined, not large)."""
    if mine is None or theirs is None or float(theirs) == 0.0:
        return None
    return float(mine) / float(theirs)


def _in_band(ratio: float | None) -> bool:
    """True unless ``ratio`` is known and outside ``REFUSE_BAND`` (edges inclusive)."""
    low, high = REFUSE_BAND
    return ratio is None or low <= ratio <= high


def _check(row: DevRow, expect: tuple[int, float | None] | None, candidate_id: str) -> bool | None:
    """None without an expectation; True when the run matches it; ``Unreproducible`` otherwise."""
    if expect is None:
        return None
    trades, total_return = expect
    m = row.stats.metrics
    same_trades = int(m.trades) == int(trades)
    if m.total_return is None or total_return is None:
        same_return = m.total_return is None and total_return is None
    else:
        same_return = abs(float(m.total_return) - float(total_return)) <= REPRODUCE_TOLERANCE
    if not (same_trades and same_return):
        raise Unreproducible(
            f"{candidate_id}: the re-run made {m.trades} trades and returned {m.total_return!r}; the "
            f"record says {trades} trades and {total_return!r}"
        )
    return True


def _summarise(arm: _Outcome, outcomes: Sequence[_Outcome], reproduced: bool | None) -> Measurement:
    draws = len(outcomes)
    beaten = sum(1 for o in outcomes if arm.rate is not None and o.rate is not None and o.rate < arm.rate)
    trade_ratio = _ratio(statistics.median([o.trades for o in outcomes]), arm.trades)
    turnovers = [o.turnover for o in outcomes if o.turnover is not None]
    turnover_ratio = _ratio(statistics.median(turnovers), arm.turnover) if turnovers else None
    matched = _in_band(trade_ratio) and _in_band(turnover_ratio)
    return Measurement(
        status=STATUS_MEASURED if matched else STATUS_UNMATCHED,
        draws=draws,
        arm_rate=arm.rate,
        beaten=beaten,
        percentile=beaten / draws,
        rates=tuple(sorted(o.rate for o in outcomes if o.rate is not None)),
        trade_ratio=trade_ratio,
        turnover_ratio=turnover_ratio,
        reproduced=reproduced,
    )


def _not_applicable(arm_rate: float | None, reproduced: bool | None) -> Measurement:
    return Measurement(
        status=STATUS_NOT_APPLICABLE,
        draws=0,
        arm_rate=arm_rate,
        beaten=0,
        percentile=None,
        rates=(),
        trade_ratio=None,
        turnover_ratio=None,
        reproduced=reproduced,
    )


def measure(
    market: Market,
    dividends: DividendMap,
    spy_dividends: Sequence[Dividend],
    candidate: Candidate,
    *,
    initial_idr: Decimal,
    contributions: ContributionSchedule | None,
    draws: int = DRAWS,
    jobs: int = 1,
    expect: tuple[int, float | None] | None = None,
) -> Measurement:
    """The yardstick reading of ``candidate`` on ``market`` at this capital and funding.

    Runs the arm once (recorded), checks it against ``expect`` -- the recorded trial's
    ``(trades, total_return)`` -- when one is given (``Unreproducible`` on a mismatch), then runs
    ``draws`` twins and summarises them. A bracket arm, or one whose rank decisions hold no picked
    name, is ``not-applicable`` and simulates no twin. ``jobs`` is the number of worker processes;
    the result does not depend on it. The caller passes the trial's own capital and contributions
    (``runner.recorded_capital``, ``runner.recorded_contributions``) for a recorded arm.
    """
    if not isinstance(candidate, Candidate):
        raise TypeError(f"expected a Candidate, got {type(candidate).__name__}")
    if isinstance(draws, bool) or not isinstance(draws, int) or draws < 1:
        raise ValueError(f"draws must be an int >= 1, got {draws!r}")
    if isinstance(jobs, bool) or not isinstance(jobs, int) or jobs < 1:
        raise ValueError(f"jobs must be an int >= 1, got {jobs!r}")
    if expect is not None and (not isinstance(expect, tuple) or len(expect) != 2):
        raise TypeError(f"expect must be a (trades, total_return) pair or None, got {expect!r}")
    if is_bracket(candidate.rules):
        return _not_applicable(None, None)
    decisions, row = record(
        market, dividends, spy_dividends, candidate, initial_idr=initial_idr, contributions=contributions
    )
    reproduced = _check(row, expect, candidate.id)
    arm = _outcome(row)
    fixed = fixed_symbols(candidate)
    draw_at = _draw_decisions(decisions, fixed)
    if not draw_at:
        return _not_applicable(arm.rate, reproduced)
    work = _Work(
        market=market,
        dividends=dividends,
        spy_dividends=tuple(spy_dividends),
        candidate=candidate,
        initial_idr=initial_idr,
        contributions=contributions,
        decisions=decisions,
        fixed=fixed,
        ranks={x.data_date: _ranked(market, x.members, x.data_date) for x in draw_at},
    )
    digest = lab_method.config_digest(candidate)
    seeds = [seed_for(digest, i) for i in range(draws)]
    return _summarise(arm, _outcomes(work, seeds, jobs), reproduced)
```
**Impact:** new module, imported by nothing yet. `lab.method` imports `backtest.dev` and
`backtest.registry` only, and `lab.control_shape` imports `sqlite3` and `backtest.metrics` only,
so the module pulls in no `lab.store`. Check after writing:
`engine/.venv/bin/python -c "import sys, seer_engine.lab.yardstick; assert 'seer_engine.lab.store' not in sys.modules"`.

### Step 3: Create the tests
**File:** `engine/tests/test_lab_yardstick.py:1` (new)
**Change:** synthetic markets only (built in memory from `labkit.smoke_history`), no store, no
network, no database. Three test allocators: `TopMomentum` (a stock picker), `AwareTopMomentum`
(its `MarketAware` twin) and `HoldTwo` (holds two picked names forever, so spells never end). The
unmatched reading is *constructed*, not mocked: a market where every other member misses its bar on
alternate rank dates forces a twin redraw at every decision, which multiplies the twins' turnover
far past the band. The golden values were computed this session with `hashlib.blake2b` on the
exact key strings the module builds.
**Code:**
```python
"""``lab.yardstick``: the random-twin engine, on synthetic dev-window markets only.

Every market here is built in memory from ``labkit.smoke_history``: no research store, no network,
no database. The allocators are small stand-ins written for this file, so a test fails because the
yardstick broke, never because a method file moved.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal

import numpy as np
import pytest
from labkit import BASE_ETFS, SMOKE_FIRST, SPY_EX_DATE, smoke_history

from seer_engine import dates
from seer_engine.backtest.benchmark import Dividend
from seer_engine.backtest.dev import DEV_END, Candidate, run_candidate
from seer_engine.backtest.market import Market, Membership
from seer_engine.lab import yardstick as ys
from seer_engine.lab.control_shape import REFUSE_BAND
from seer_engine.prices import to_decimal
from seer_engine.sim import q
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.contributions import OWNER_MONTHLY
from seer_engine.sim.rules import (
    DESIGN_V0,
    MONTHLY_HOLD,
    MONTHLY_HOLD_FRAC_GOTRADE,
    MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE,
)
from seer_engine.strategies.a import STRATEGY_A, STRATEGY_A_PARAMS
from seer_engine.strategies.allocator import prepare_for
from seer_engine.strategies.base import History
from seer_engine.strategies.f_index import TIMING, TimingParams

CAPITAL = Decimal("10000000")
SPY_DIV = Decimal("1.0300")
DIVIDENDS = {"SPY": {SPY_EX_DATE: SPY_DIV}}
SPY_DIVIDENDS = (Dividend(SPY_EX_DATE, SPY_DIV),)
LOOKBACK = ys.LIQUIDITY_BARS + 1  # every member is rankable at the arm's first decision
ZERO_DIGEST = "0" * 64


# --------------------------------------------------------------------------- synthetic markets


def _member(i: int) -> str:
    return f"S{i:02d}"


def _drop(h: History, days: Iterable[date]) -> History:
    gone = np.array(sorted(days), dtype="datetime64[D]")
    if gone.size == 0:
        return h
    keep = ~np.isin(h.dates, gone)
    return History(h.symbol, h.dates[keep], h.open[keep], h.high[keep], h.low[keep], h.close[keep], h.volume[keep])


def _market(members: int = 40, gaps: Mapping[str, Iterable[date]] | None = None) -> Market:
    """The labkit ETFs plus ``members`` index members S00, S01, ... with ``gaps`` bars removed."""
    days = dates.sessions(SMOKE_FIRST, DEV_END)
    history = {s: smoke_history(s, k, days) for k, s in enumerate(BASE_ETFS)}
    names = tuple(_member(i) for i in range(members))
    for j, name in enumerate(names):
        history[name] = _drop(smoke_history(name, len(BASE_ETFS) + j, days), (gaps or {}).get(name, ()))
    membership = Membership(intervals=tuple((s, days[0], None) for s in names))
    return Market(history=history, membership=membership, fx=((days[0], Decimal("2000")),))


def _close_target(h: History, d: date, weight: Decimal) -> Target | None:
    i = h.index_of(d)
    if i is None:
        return None
    return Target(symbol=h.symbol, weight=weight, last=q(to_decimal(float(h.close[i]))))


# --------------------------------------------------------------------------- stand-in allocators


@dataclasses.dataclass(frozen=True)
class TopParams:
    k: int


class TopMomentum:
    """Equal-weight top ``k`` members by 20-session return on the data date: a stand-in picker."""

    id = "test-top-momentum"

    def lookback(self, params):
        return LOOKBACK

    def symbols(self, params):
        return ()

    def holds(self, params):
        return ()

    def uses_members(self, params):
        return True

    def prepare(self, history):
        return history

    def targets(self, history, members, data_date, held, params):
        return self.targets_prepared(history, members, data_date, held, params)

    def targets_prepared(self, prepared, members, data_date, held, params):
        scored = []
        for s in sorted(members):
            h = prepared.get(s)
            i = None if h is None else h.index_of(data_date)
            if i is None or i < 20:
                continue
            scored.append((-(float(h.close[i]) / float(h.close[i - 20])), s))
        scored.sort()
        w = equal_weight(params.k)
        return tuple(_close_target(prepared[s], data_date, w) for _, s in scored[: params.k])


class AwareTopMomentum(TopMomentum):
    """The same picker, prepared from the whole market (the ``MarketAware`` path)."""

    id = "test-aware-top-momentum"

    def __init__(self):
        self.market_prepares = 0

    def prepare_market(self, market):
        self.market_prepares += 1
        return market.history


class HoldTwo:
    """Holds S00 and S01, half each, at every decision: two picked names in one endless spell."""

    id = "test-hold-two"

    def lookback(self, params):
        return LOOKBACK

    def symbols(self, params):
        return ()

    def holds(self, params):
        return ()

    def uses_members(self, params):
        return True

    def prepare(self, history):
        return history

    def targets(self, history, members, data_date, held, params):
        return self.targets_prepared(history, members, data_date, held, params)

    def targets_prepared(self, prepared, members, data_date, held, params):
        w = equal_weight(2)
        out = (_close_target(prepared[s], data_date, w) for s in (_member(0), _member(1)))
        return tuple(t for t in out if t is not None)


def _cand(cid, allocator, params, rules=MONTHLY_HOLD_FRAC_GOTRADE) -> Candidate:
    return Candidate(
        id=cid, family="M0001", rules=rules, allocator=allocator, params=params,
        rationale="yardstick test arm", added=date(2026, 11, 13), owner_inputs=(),
    )


def _plain(market, c):
    return run_candidate(
        market, DIVIDENDS, SPY_DIVIDENDS, c,
        prepared=prepare_for(c.allocator, market), initial_idr=CAPITAL, contributions=OWNER_MONTHLY,
    )


def _record(market, c):
    return ys.record(market, DIVIDENDS, SPY_DIVIDENDS, c, initial_idr=CAPITAL, contributions=OWNER_MONTHLY)


def _measure(market, c, **kw):
    return ys.measure(market, DIVIDENDS, SPY_DIVIDENDS, c, initial_idr=CAPITAL, contributions=OWNER_MONTHLY, **kw)


def _same_run(a, b):
    ma, mb = a.stats.metrics, b.stats.metrics
    assert (ma.trades, ma.total_return, ma.mwr, ma.cagr, ma.max_drawdown) == (
        mb.trades, mb.total_return, mb.mwr, mb.cagr, mb.max_drawdown
    )
    assert a.stats.turnover == b.stats.turnover
    assert (a.start, a.end) == (b.start, b.end)


@pytest.fixture(scope="module")
def market():
    return _market(40)


@pytest.fixture(scope="module")
def top3():
    return _cand("T-TOP3", TopMomentum(), TopParams(3))


def _gapped_hold_two():
    """``HoldTwo`` on a 20-member market where, from the second rank decision on, every other
    member misses its bar on alternate rank data dates (even members on one, odd on the next).

    A twin drawn on one rank date belongs to the half that trades that day, so it misses the next
    rank date's bar and is redrawn there: from the third decision on, every decision redraws.
    """
    c = _cand("T-HOLD2", HoldTwo(), None)
    decisions, _ = _record(_market(20), c)
    rank_days = [d.data_date for d in decisions if d.rank]
    gaps: dict[str, list[date]] = {}
    for j, d in enumerate(rank_days[1:]):
        for i in range(2, 20):
            if i % 2 == j % 2:
                gaps.setdefault(_member(i), []).append(d)
    return _market(20, gaps), c


# --------------------------------------------------------------------------- R1.1: the twin


@pytest.mark.parametrize("rules", [MONTHLY_HOLD_FRAC_GOTRADE, MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE])
def test_recording_and_replaying_an_arm_reproduces_it_exactly(market, rules):
    """The premise of the whole yardstick: a recorded run IS the arm's run, and replaying the
    record through a second allocator gives the identical book, resize sessions included."""
    c = _cand("T-TOP3", TopMomentum(), TopParams(3), rules)
    plain_result, plain = _plain(market, c)
    decisions, recorded = _record(market, c)
    replay = ys.Replay(c.allocator, {d.data_date: d.targets for d in decisions})
    replay_result, replayed = run_candidate(
        market, DIVIDENDS, SPY_DIVIDENDS, dataclasses.replace(c, allocator=replay),
        prepared=prepare_for(replay, market), initial_idr=CAPITAL, contributions=OWNER_MONTHLY,
    )
    assert plain.stats.metrics.trades > 0
    _same_run(recorded, plain)
    _same_run(replayed, plain)
    assert replay_result.snapshots == plain_result.snapshots
    assert len({d.data_date for d in decisions}) == len(decisions)
    if rules is MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE:
        assert any(not d.rank for d in decisions) and any(d.rank for d in decisions)
    else:
        assert all(d.rank for d in decisions)
    assert ys.Replay(c.allocator, {}, seed=1).id != ys.Replay(c.allocator, {}, seed=2).id


def test_a_market_aware_allocator_is_recorded_through_prepare_market(market):
    aware = AwareTopMomentum()
    c = _cand("T-AWARE", aware, TopParams(3))
    _, plain = _plain(market, c)
    before = aware.market_prepares
    decisions, recorded = _record(market, c)
    assert aware.market_prepares == before + 1
    assert decisions
    _same_run(recorded, plain)


def test_a_twin_keeps_every_decision_date_and_weight_and_swaps_every_picked_name(market, top3):
    decisions, _ = _record(market, top3)
    fixed = ys.fixed_symbols(top3)
    schedule = ys.twin_schedule(market, decisions, fixed, ys.seed_for(ZERO_DIGEST, 0))
    assert sorted(schedule) == sorted(d.data_date for d in decisions)
    previous: dict[str, str] = {}  # real name -> its twin at the previous rank decision
    swapped = 0
    for d in sorted(decisions, key=lambda x: x.data_date):
        twin = schedule[d.data_date]
        assert len(twin) == len(d.targets)
        assert sorted(t.weight for t in twin) == sorted(t.weight for t in d.targets)
        assert len({t.symbol for t in twin}) == len(twin)
        real_names = {t.symbol for t in d.targets if t.symbol not in fixed}
        now: dict[str, str] = {}
        for r, t in zip(d.targets, twin):
            if r.symbol in fixed:
                assert t == r
                continue
            swapped += 1
            assert t.weight == r.weight
            assert t.symbol in d.members and t.symbol not in fixed
            assert t.last == q(market.bar(t.symbol, d.data_date).close)
            if previous.get(r.symbol) != t.symbol:  # drawn at this decision
                assert t.symbol not in real_names
            now[r.symbol] = t.symbol
        previous = now
    assert swapped > 0


def test_a_resize_decision_is_copied_unchanged(market):
    c = _cand("T-TOP3R", TopMomentum(), TopParams(3), MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE)
    decisions, _ = _record(market, c)
    schedule = ys.twin_schedule(market, decisions, ys.fixed_symbols(c), ys.seed_for(ZERO_DIGEST, 0))
    resizes = [d for d in decisions if not d.rank]
    assert resizes
    for d in resizes:
        assert schedule[d.data_date] == d.targets


def _dollar_volume_ranks(market, members, d):
    """The test's own ranking: median close x volume over the 63 bars on or before d."""
    day = np.datetime64(d, "D")
    rows = []
    for s in members:
        h = market.history[s]
        end = int(np.searchsorted(h.dates, day, side="right"))
        if end >= ys.LIQUIDITY_BARS:
            rows.append((-float(np.median(h.close[end - 63 : end] * h.volume[end - 63 : end])), s))
    return [s for _, s in sorted(rows)]


def test_a_twin_is_drawn_from_the_real_picks_trading_size_neighbourhood():
    wide = _market(60)
    c = _cand("T-TOP3W", TopMomentum(), TopParams(3))
    decisions, _ = _record(wide, c)
    schedule = ys.twin_schedule(wide, decisions, ys.fixed_symbols(c), ys.seed_for(ZERO_DIGEST, 3))
    checked = 0
    previous: frozenset[str] = frozenset()
    for d in sorted(decisions, key=lambda x: x.data_date):
        order = _dollar_volume_ranks(wide, d.members, d.data_date)
        for r, t in zip(d.targets, schedule[d.data_date]):
            if r.symbol not in previous:  # a new spell: its twin was drawn here
                assert abs(order.index(t.symbol) - order.index(r.symbol)) <= ys.NEIGHBOUR_RANKS
                checked += 1
        previous = frozenset(t.symbol for t in d.targets)
    assert checked > 0


def test_a_twin_keeps_its_name_for_the_whole_holding_spell(market):
    c = _cand("T-HOLD2", HoldTwo(), None)
    decisions, _ = _record(market, c)
    schedule = ys.twin_schedule(market, decisions, ys.fixed_symbols(c), ys.seed_for(ZERO_DIGEST, 0))
    firsts = {tuple(t.symbol for t in schedule[d.data_date]) for d in decisions}
    assert len(decisions) > 3
    assert len(firsts) == 1, "one spell, one pair of twins, from the first decision to the last"
    (pair,) = firsts
    assert len(set(pair)) == 2 and not set(pair) & {_member(0), _member(1)}


def test_a_twin_that_stops_trading_is_redrawn_at_that_decision():
    gapped, c = _gapped_hold_two()
    decisions, _ = _record(gapped, c)
    schedule = ys.twin_schedule(gapped, decisions, ys.fixed_symbols(c), ys.seed_for(ZERO_DIGEST, 0))
    days = sorted(d.data_date for d in decisions if d.rank)
    assert len(days) > 4
    for before, after in zip(days[1:], days[2:]):
        assert schedule[before][0].symbol != schedule[after][0].symbol
        for t in schedule[after]:
            assert gapped.bar(t.symbol, after) is not None


def test_the_measurement_counts_the_twins_the_arm_out_earned(market, top3):
    _, plain = _plain(market, top3)
    m = _measure(market, top3, draws=6)
    assert m.status == ys.STATUS_MEASURED
    assert m.draws == 6 and len(m.rates) == 6 and list(m.rates) == sorted(m.rates)
    assert m.arm_rate == plain.stats.metrics.mwr  # funded: the money-weighted return
    assert m.beaten == sum(1 for r in m.rates if r < m.arm_rate)
    assert m.percentile == m.beaten / 6
    assert REFUSE_BAND[0] <= m.turnover_ratio <= REFUSE_BAND[1]
    assert m.reproduced is None


# --------------------------------------------------------------------------- R1.3: unmatched


def test_twins_whose_shape_leaves_the_band_are_unmatched():
    gapped, c = _gapped_hold_two()
    m = _measure(gapped, c, draws=4)
    assert m.status == ys.STATUS_UNMATCHED
    assert m.turnover_ratio is not None and m.turnover_ratio > REFUSE_BAND[1]
    assert m.draws == 4 and m.percentile == m.beaten / 4  # the reading is kept, it just never clears


# --------------------------------------------------------------------------- R1.4: not applicable


def test_an_etf_only_arm_is_not_applicable_and_simulates_no_twin(market, monkeypatch):
    def no_twin(work, seed):
        raise AssertionError("a not-applicable arm must not simulate a twin")

    monkeypatch.setattr(ys, "_twin_outcome", no_twin)
    c = _cand("T-SPY", TIMING, TimingParams(hold="SPY", signal="SPY", rule="sma", n=50), MONTHLY_HOLD)
    m = _measure(market, c)
    assert m.status == ys.STATUS_NOT_APPLICABLE
    assert (m.draws, m.beaten, m.percentile, m.rates) == (0, 0, None, ())
    assert m.arm_rate is not None


def test_a_bracket_arm_is_not_applicable(market):
    c = _cand("T-BRACKET", STRATEGY_A, STRATEGY_A_PARAMS, DESIGN_V0)
    m = _measure(market, c)
    assert m.status == ys.STATUS_NOT_APPLICABLE and m.draws == 0 and m.reproduced is None


# --------------------------------------------------------------------------- R1.5: determinism


def test_the_result_is_identical_for_any_number_of_jobs(market, top3):
    one = _measure(market, top3, draws=4, jobs=1)
    two = _measure(market, top3, draws=4, jobs=2)
    again = _measure(market, top3, draws=4, jobs=1)
    assert one == two == again
    assert one.draws == 4


def test_the_draw_rule_is_pinned():
    """Golden vector: any edit to the seed or the draw hash goes red here, and must become a new
    ``RULE_ID`` instead of a quiet change to what every stored reading meant."""
    assert ys.RULE_ID == "yardstick-v1"
    assert (ys.DRAWS, ys.LIQUIDITY_BARS, ys.NEIGHBOUR_RANKS) == (200, 63, 25)
    s0, s1 = ys.seed_for(ZERO_DIGEST, 0), ys.seed_for(ZERO_DIGEST, 1)
    assert s0 == 11146197528017810122
    assert s1 == 1086165951305291315
    pool = ("BBB", "CCC", "DDD", "EEE", "FFF")
    assert ys._draw_order(s0, "AAA", "2014-01", pool)[0] == "FFF"
    assert ys._draw_order(s0, "AAA", "2014-02", pool)[0] == "CCC"
    assert ys._draw_order(s1, "AAA", "2014-02", pool)[0] == "DDD"


# --------------------------------------------------------------------------- the reproduce check


def test_a_wrong_expectation_is_refused_and_a_right_one_is_reported(market, top3):
    _, plain = _plain(market, top3)
    trades, total = plain.stats.metrics.trades, plain.stats.metrics.total_return
    with pytest.raises(ys.Unreproducible):
        _measure(market, top3, draws=1, expect=(trades + 1, total))
    with pytest.raises(ys.Unreproducible):
        _measure(market, top3, draws=1, expect=(trades, total + 1e-6))
    assert _measure(market, top3, draws=1, expect=(trades, total)).reproduced is True
```
**Impact:** new test file; runs in parallel under the default `-n auto`. `jobs=2` forks inside an
xdist worker, which is supported on Linux.

## Principles applied

- Laziness protocol: no machine-readable "setup" model and no per-method twin code. The twin reuses
  `dev.run_candidate`, `prepare_for`, `lab.method.config_digest` and `control_shape.REFUSE_BAND`;
  the only new machinery is a recorder, a replay and the draw.
- Fix root causes: resize-only answers are copied unchanged and spells are tracked over rank
  decisions only (`Decision.rank`, read from `is_rank_session` in `Recorder._note`). Without that,
  the twin would sell names the real book never sells.
- Make illegal states unrepresentable: `Measurement.__post_init__` refuses a status outside
  `STATUSES`, a not-applicable reading that carries twin figures, and a percentile that is not
  `beaten / draws`. Phase 3 cannot store a contradictory row.
- Boundary discipline: `measure` validates `candidate`, `draws`, `jobs` and `expect` once; the
  helpers below it trust their inputs.
- Test behavior, not implementation: the unmatched reading comes from a constructed market whose
  gaps force redraws, not from patching `_twin_outcome`. The neighbourhood test ranks dollar volume
  itself rather than calling `_ranked`. The only patch is a spy that proves a not-applicable arm
  simulates no twin.

## Verification

**Build:**
```bash
cd /home/miftah/.worktrees/seer/random-twin-yardstick
test -x engine/.venv/bin/python || (python3.11 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]')
engine/.venv/bin/ruff check engine
engine/.venv/bin/python -c "import sys, seer_engine.lab.yardstick; assert 'seer_engine.lab.store' not in sys.modules"
```
**Tests:**
```bash
engine/.venv/bin/pytest engine/tests/test_lab_yardstick.py -n0 -q
engine/.venv/bin/pytest engine/tests/test_lab_yardstick.py -q          # again under xdist (-n auto), as CI runs it
engine/.venv/bin/pytest engine/tests/test_lab_*.py -q                  # invariant 1: every lab test file
```
**Proof:** the phase ships a library, not a command. Its real artifact is the `Measurement`
`measure` returns for a real arm on a market, and these pytest journeys drive exactly that (the
same `dev.run_candidate` that `lab run` uses), on synthetic markets built in memory. Phase 3 proves
the same engine through `lab yardstick` against the verify-seer lab copy.
- Harness: `.claude/skills/verify-seer` exists, but this phase adds no CLI or page for it to drive,
  so the proof is pytest against the engine, run from the worktree root with the worktree's own venv
- Feature-map entries: none (no user-facing change; `features/lab-cli.md` gains `lab yardstick` in phase 3)
- Journeys:
  - **J1** · traces R1.1 — `engine/.venv/bin/pytest -n0 -q "engine/tests/test_lab_yardstick.py::test_recording_and_replaying_an_arm_reproduces_it_exactly" engine/tests/test_lab_yardstick.py::test_a_market_aware_allocator_is_recorded_through_prepare_market` → passes when 3 tests pass: the recorded run and the replayed run report the plain run's trades, total return, money-weighted return, CAGR, drawdown, turnover and window, and the replay's equity snapshots equal the plain run's, on monthly rules and on monthly-rank-weekly-resize rules
  - **J2** · traces R1.1 — `engine/.venv/bin/pytest -n0 -q engine/tests/test_lab_yardstick.py::test_a_twin_keeps_every_decision_date_and_weight_and_swaps_every_picked_name engine/tests/test_lab_yardstick.py::test_a_resize_decision_is_copied_unchanged engine/tests/test_lab_yardstick.py::test_a_twin_is_drawn_from_the_real_picks_trading_size_neighbourhood engine/tests/test_lab_yardstick.py::test_a_twin_keeps_its_name_for_the_whole_holding_spell engine/tests/test_lab_yardstick.py::test_a_twin_that_stops_trading_is_redrawn_at_that_decision` → passes when 5 tests pass: the twin has the arm's decision dates and per-decision weight multiset, every picked name is replaced by an index member with a bar that day, never by a name the arm picks at the decision where the twin is drawn, within ±25 liquidity ranks of the real pick; resize answers are copied unchanged; a twin is kept for its whole spell and redrawn only when it stops trading
  - **J3** · traces R1.1 — `engine/.venv/bin/pytest -n0 -q engine/tests/test_lab_yardstick.py::test_the_measurement_counts_the_twins_the_arm_out_earned` → passes when `measure(..., draws=6)` returns status `measured`, 6 sorted rates, `arm_rate` equal to the plain run's money-weighted return, `beaten` equal to the count of rates strictly below it, and `percentile == beaten / 6`
  - **J4** · traces R1.3 — `engine/.venv/bin/pytest -n0 -q engine/tests/test_lab_yardstick.py::test_twins_whose_shape_leaves_the_band_are_unmatched` → passes when, on the constructed gapped market, `measure` returns status `unmatched` with `turnover_ratio > 2.0` and still carries `percentile == beaten / 4`
  - **J5** · traces R1.4 — `engine/.venv/bin/pytest -n0 -q engine/tests/test_lab_yardstick.py::test_an_etf_only_arm_is_not_applicable_and_simulates_no_twin engine/tests/test_lab_yardstick.py::test_a_bracket_arm_is_not_applicable` → passes when an SPY-only timing arm and a bracket arm both return status `not-applicable` with `draws == 0`, `rates == ()`, `percentile is None`, and the spy that replaces the twin runner never fires
  - **J6** · traces R1.5 — `engine/.venv/bin/pytest -q engine/tests/test_lab_yardstick.py::test_the_result_is_identical_for_any_number_of_jobs engine/tests/test_lab_yardstick.py::test_the_draw_rule_is_pinned` (run once with `-n0` and once without, so the `jobs=2` fork is exercised inside an xdist worker too) → passes when `measure` at `jobs=1`, `jobs=2` and `jobs=1` again returns three equal `Measurement` values, and `seed_for` and the draw order match the pinned golden values (`seed_for("0"*64, 0) == 11146197528017810122`)
- Neighbor check (traces nothing): the dev runner, book runner and lab runner this module drives are untouched, and must stay green with the new module present — `engine/.venv/bin/pytest -q engine/tests/test_backtest_dev.py engine/tests/test_book_runner.py engine/tests/test_allocator.py engine/tests/test_lab_runner.py engine/tests/test_lab_control_draw.py engine/tests/test_lab_control_shape.py` → passes when every test passes; and `git status --short` lists only the two new files (plus the ignored venv), with `lab/lab.sqlite` and `web/data/lab.json` unchanged
- Cost: none (no LLM or network calls)
**Exit criteria:** `ruff check engine` is clean; `test_lab_yardstick.py` passes serially and under
xdist; every `test_lab_*.py` passes; importing `seer_engine.lab.yardstick` does not import
`seer_engine.lab.store`; the commit contains exactly `engine/src/seer_engine/lab/yardstick.py` and
`engine/tests/test_lab_yardstick.py`.

**Commit (explicit paths only; never `git commit -a`; `lab/lab.sqlite` is never staged — invariant 2):**
```bash
cd /home/miftah/.worktrees/seer/random-twin-yardstick
git status --porcelain lab web/data   # must print nothing; if lab.sqlite shows: git checkout -- lab/lab.sqlite
git add engine/src/seer_engine/lab/yardstick.py engine/tests/test_lab_yardstick.py
git commit -m "lab: the random-twin engine (random-twin-yardstick phase 2)"
```

## Handoffs

- **Phase 3 (R1.1 command half, R1.2, R1.5 no-second-row half, R1.6):** call
  `yardstick.measure(data.market, data.dividends, data.spy_dividends, candidate,
  initial_idr=runner.recorded_capital(conn, n), contributions=runner.recorded_contributions(conn, n),
  draws=yardstick.DRAWS, jobs=J, expect=(trial["trades"], trial["total_return"]))`, catch
  `yardstick.Unreproducible` and exit 2 with nothing written (R1.6 is proved there, through the
  command; this phase's `test_a_wrong_expectation_is_refused_and_a_right_one_is_reported` only
  covers the engine raise). Store `rule_id=yardstick.RULE_ID` and `rates_json=json.dumps(list(m.rates))`.
  A bracket arm returns `not-applicable` with `reproduced=None` and is never re-run, so R1.6's
  reproduce check cannot fire for it. Settled at reconcile (Decision D12): phase 3 records it
  `not-applicable` with `reproduced` NULL, no refusal, and tests that.
- **All phases (settled at reconcile, Decision D11):** this module's `Measurement.__post_init__` is
  the one source of truth for the shape of a reading, and phase 3's table CHECKs, `insert_yardstick`
  and `YardstickRow.from_measurement`, phase 4's fixtures and phase 5's snapshot tests mirror it:
  `not-applicable` is `draws=0, beaten=0, percentile=None, rates=(), trade_ratio=None,
  turnover_ratio=None`; `measured` and `unmatched` are `draws>=1, 0<=beaten<=draws,
  percentile=beaten/draws` (never None), `len(rates)<=draws`.
- **Phase 3 / 4 (`yardstick_clears`):** `percentile` is None exactly when `status ==
  STATUS_NOT_APPLICABLE`. Compare `percentile >= YARDSTICK_MIN_PERCENTILE` only for `measured`;
  `unmatched` never clears even with a high percentile (R1.3).
- **Phase 4:** `runner.run_method` must call `measure` with the same capital and contributions the
  arm is about to be recorded at (`INITIAL_IDR`, `OWNER_MONTHLY`), and it can pass `expect` from the
  `DevRow` it already holds or leave it None; at 200 draws a measurement runs the arm 201 times, so it
  belongs outside `store.begin_immediate`, as the index already says.
- **Phase 5:** `rates` excludes twins with no rate, so `medianRate` should be the median of `rates`
  (None when empty), not of `draws` values.
- **Reconciler:** the three additive signature differences against the index are listed under
  Interface Contract (`Decision.rank`, `Recorder(inner, rules)`, `twin_schedule(..., *, ranks=None)`).
  One design addition: the draw also excludes the names the arm picks at the drawing decision, not
  only the names the twin book holds. That is what makes the index's phase-2 exit criterion ("none of
  its picked names by construction") true at the decision where each twin is drawn. The module
  docstring states what it cannot guarantee (a kept twin can later match a new real pick).

## Rollback

Delete the two new files (`git rm engine/src/seer_engine/lab/yardstick.py
engine/tests/test_lab_yardstick.py`) or `git revert` the phase commit. Nothing imports the module
until phase 3, no table, schema or recorded file is touched, and no lab or web artifact changes.
