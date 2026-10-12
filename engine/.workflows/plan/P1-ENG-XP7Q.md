> Adopted from `/home/miftah/seer/.workflows/orchestration/lab-exposure-diagnostic/PLAN.md` phase 1. Source: `.workflows/plan/lab-exposure-diagnostic/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: `lab exposure`: the diagnostic

**Plan set:** `LAB_EXPOSURE_DIAGNOSTIC_PLAN.md`
**Analysis:** `docs/analyzer/20261012-100551-X4P9_code_analyzer.md`
**Satisfies:** R1 (the exposure diagnostic itself), R3 (report-only, proved in tests)
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab`

---

## Goal

After this phase the lab can answer, for any recorded book method, the question the
`stock-dividend-change-drift` family went three batches without being asked: how much of this
method's money was ever in its **own picks**, and what did those picks do alone, with the parked
market holding removed and the brakes off? A new report-only subcommand `lab exposure` runs every
recorded dev variant four times — as recorded, picks-only, picks-rescaled-to-the-whole-book, and
parked-money-only — at the variant's recorded capital and funding, and prints the whole-window and
per-era lead over SPY for each. No method file changes, no method id is minted, no trial row is
written, and `N` and the test-window look budget do not move.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- module `seer_engine.lab.exposure` (`engine/src/seer_engine/lab/exposure.py`, new file) exporting:
  `BOOK`, `PICKS`, `FULL`, `PARK`, `ARM_SUFFIX`, `ARM_LABEL`, `ARM_HEAD`, `WHOLE`, `ERAS`,
  `ERA_LABELS`, `CSV_HEADER`, `Tally`, `ExposureParams`, `ExposureAllocator`, `wrapper_for`,
  `reweight`, `park_set`, `arm_rules`, `arm_candidate`, `arms_for`, `Variant`, `MethodPlan`,
  `resolve_method`, `plan_method`, `plan_methods`, `load_dev_store`, `Arm`, `arm_of`, `StoreRun`,
  `measure`, `measure_store`, `VariantRow`, `MethodReport`, `compare`, `format_report`,
  `summary_line`, `insight_text`, `journal`, `csv_rows`, `write_csv`.
- CLI subcommand `lab exposure` (`engine/src/seer_engine/commands/lab.py`), handler
  `commands.lab._exposure`, `_HANDLERS["exposure"]`.
- `engine/tests/test_lab_exposure.py` (new).

**Signature changes:** none. No existing function's signature, behaviour, help text or output
moves.

**Requires (from earlier phases):** none — phase 1 is the base of the set.

**Leaves alone (owned by others / out of scope):**
- `lab/lab.sqlite`, `web/data/lab.json`, `docs/backtests/` (Phase 2 creates
  `2026-10-12-exposure-diagnostic.md` and its committed companion
  `2026-10-12-exposure-diagnostic-grid.csv` there), `.workflows/todos.md` — Phase 2.
- `engine/src/seer_engine/{sim,backtest,strategies,paper,sean,fundamentals}/**` — read only,
  never edited (plan invariant 5).
- `engine/src/seer_engine/lab/{methods,hardgate.py,runner.py,store.py,real_costs.py,
  survivorship_check.py,walkforward.py,method.py,npolicy.py,prereg.py,remeasure.py,seed.py,
  name_count.py}` — read only.
- `web/`, `db/`, `docs/` — untouched.

**Frozen CLI surface Phase 2 will type** (this must not change after this phase lands):

```
lab exposure M0030 [M0024 ...] [--only IDS] [--store DIR] [--csv PATH] [--no-journal]
```

Phase 2's exact command line, from the worktree, against the MAIN checkout's store. Its `--csv`
target is the committed grid Phase 2 owns — `docs/backtests/` keeps a `-grid.csv` beside every
write-up (`2026-10-08-how-many-names-grid.csv`), so the file is written straight into the repo:

```bash
PYTHONPATH=/home/miftah/.worktrees/seer/lab-exposure-diagnostic/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab exposure \
    M0024 M0028 M0030 M0044 M0053 \
    --store /home/miftah/seer/engine/.research \
    --csv /home/miftah/.worktrees/seer/lab-exposure-diagnostic/docs/backtests/2026-10-12-exposure-diagnostic-grid.csv
```

Add `--no-journal` for a first, write-nothing look; drop it for the run that journals. Flags:
`--only IDS` (alias `--candidate`) narrows to named recorded variants; `--store DIR` is the dev
store; `--csv PATH` writes the full variant × arm grid; `--no-journal` writes nothing at all.
Exit codes: 0 ok, 2 a lab refusal, 1 anything else.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/exposure.py` | create | the whole diagnostic: park set, `ExposureAllocator`, arms, `plan_methods`, `measure`, era table, report, journal, CSV |
| `engine/src/seer_engine/commands/lab.py` | modify | 4 additive hunks: docstring line after `:66`, subparser after `:370`, `_exposure` after `:2197`, `_HANDLERS` entry after `:2350` |
| `engine/tests/test_lab_exposure.py` | create | allocator contract, re-weighting arithmetic, refusals before any store loads, report-only invariant, CLI end-to-end on the smoke fixture |

---

## Implementation Steps

### Step 1: `engine/src/seer_engine/lab/exposure.py` — the diagnostic module

**File:** `engine/src/seer_engine/lab/exposure.py` (new; the whole file below)
**Change:** create the module. It mirrors `lab/survivorship_check.py`'s shape
(`plan_methods` / `measure_store` / `compare` / `format_report` / `summary_line` / `write_csv` /
`insight_text` / `journal`) and `lab/real_costs.py`'s report-only discipline.

**Code:**

```python
"""``lab exposure M0030 [M0024 ...]``: how much of a method's money was ever in its own picks.

Every number the lab records about a method is a number about the whole book -- total return,
CAGR, max drawdown, profit factor, ``exposure``. None of them separates the two different things
a book is made of: the names the method **picked**, and the money it **parked** -- in SPY or
another index instrument, or left as cash because a gate fired or a slot went unfilled. A method
whose picks have no edge can still post a good whole-book number when most of its money is parked
market beta, and until now the lab could not see the difference. ``stock-dividend-change-drift``
spent three batches and thirty-five variations inside exactly that blind spot (handover
``docs/plans/HANDOVER_20261012-picks-not-brakes.md`` section 1): its dividend picks filled about
four slots in ten, the rest sat in a timed SPY holding, and with the parked money stripped out the
picks lost to the market in every era. Nothing in the lab would have caught it.

**Four arms, one allocator.** For each recorded dev variant this runs the *same* allocator on the
*same* window at the *same* recorded capital and funding, four times, differing only in how the
allocator's targets are re-weighted on the way out:

================  =====================================================================
arm               what it prices
================  =====================================================================
(recorded)        the candidate used unchanged: the reference, and the reproduction
                  check against the number the lab recorded
``-PICKS``        the parked targets dropped, the survivors' weights kept -- the pick
                  sleeve as the method sized it, carrying its own cash drag. Its
                  ``RunStats.exposure`` **is** the share of the book that was in its
                  own picks, because ``book_runner._invested`` already counts only
                  non-idle positions
``-FULL``         the parked targets dropped and the survivors rescaled to fill the
                  book -- the picks with the brakes off and the whole book behind
                  them, which is the fair selection test against SPY
``-PARK``         only the parked targets, rescaled to fill the book -- what the
                  spare money in the market did, priced on its own
================  =====================================================================

The ``-PICKS`` / ``-FULL`` pair is the point: one carries the cash drag the method really had and
one removes it, so together they bracket the truth without either being a lie. For a method whose
only brake is a volatility target there is no park set at all, and ``-FULL`` is precisely "the
same picks with the brake switched off".

**Parked is detected generically**, from ``set(allocator.holds(params)) | {rules.idle_symbol}``.
``holds()`` is a mandatory ``Allocator`` member that already means "the fixed instruments this
allocator may hold", and ``dev.candidate_owner_inputs`` already reads it that way to decide which
ETFs the owner must be able to buy: ``BLEND`` unions its parts', ``VOLTARGET`` delegates to its
inner, ``f_index.TIMING`` returns the symbol it holds. So no method file changes and **no method
id is minted** -- which matters more here than convenience, because ``N`` for the deflated Sharpe
counts distinct methods and every new one raises the luck hurdle for the whole lab retroactively.

**What cannot be undone, and is reported instead.** A gate that fires by returning no targets at
all empties the book, and no re-weighting wrapper can invent the basket a gated-off allocator
would have produced. So the wrapper counts the decision sessions on which the inner returned
nothing, and the report prints that share per arm rather than faking a gate-free counterfactual.

**A report, not a trial.** Nothing is written but, unless ``--no-journal``, one ``observation``
per method: no ``trials``, ``trial_moments``, ``trial_funding`` or ``trial_provenance`` row, no
status, no pre-registration. ``store.dev_trial_count`` (the lab's N) and ``store.test_looks``
therefore cannot move, and the command prints both before and after so the invariant is visible
rather than merely asserted. Every refusal that needs no bars is made before the store is opened,
and ``dev.run_registry`` is called with **no** ``window=`` keyword, so the D9 dev default binds
and nothing here can name the test window.

**The arms are compared with each other, never with the recorded trial.** Measured 2026-10-12:
``M0030-C50T`` re-runs to 9.583603 against a recorded 9.583723, and its SPY TR to 3.466805 against
a recorded 3.514206, because the store's fingerprint moved. The reproduction check is printed as
information, the way ``lab costs`` prints it, and no conclusion rests on a recorded number beside
a re-run one.
"""

from __future__ import annotations

import csv
import gc
import logging
import math
import sqlite3
import time
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.dev import Candidate, DevRow
from seer_engine.backtest.metrics import DASH, fmt_num, fmt_pct, fmt_pf, fmt_signed_pct
from seer_engine.commands.backtest_dev import month_end_curve
from seer_engine.lab import hardgate, runner, store
from seer_engine.lab import walkforward as wf
from seer_engine.lab.method import METHOD_ID, Method, discover
from seer_engine.lab.real_costs import REPRO_TOL
from seer_engine.sim.book import Target
from seer_engine.sim.contributions import ContributionSchedule
from seer_engine.sim.rules import TradeRules, is_bracket
from seer_engine.strategies.allocator import Allocator, prepare_for, scale_weight
from seer_engine.strategies.base import History

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- the four arms

BOOK = "book"
PICKS = "picks"
FULL = "full"
PARK = "park"
MODES: tuple[str, ...] = (BOOK, PICKS, FULL, PARK)

#: Suffix appended to the recorded candidate id for each constructed arm. Candidate ids must
#: match ``dev._ID`` (``[A-Z0-9]+(-[A-Z0-9]+)*``), which these keep.
ARM_SUFFIX: Mapping[str, str] = {PICKS: "-PICKS", FULL: "-FULL", PARK: "-PARK"}
#: What each arm is, for a rationale line (one line, non-empty: ``Candidate`` requires both).
ARM_LABEL: Mapping[str, str] = {
    BOOK: "as recorded",
    PICKS: "its own picks only, at the weights it gave them",
    FULL: "its own picks only, rescaled to fill the book",
    PARK: "only the money it parks in the market",
}
#: Column heads in the terminal grid.
ARM_HEAD: Mapping[str, str] = {
    BOOK: "recorded", PICKS: "picks", FULL: "picks, full", PARK: "parked",
}

# --------------------------------------------------------------------------- the era table

WHOLE = "whole window"
#: M0107's split, because that is the split that exposed the problem (handover section 4.1).
#: 2008 sits deliberately inside 2003-2008: the crash is the year the parked holding earns its
#: keep, and burying it inside a six-year average hides exactly that.
ERAS: tuple[tuple[str, date, date], ...] = (
    ("1996-2002", date(1996, 1, 1), date(2002, 12, 31)),
    ("2003-2008", date(2003, 1, 1), date(2008, 12, 31)),
    ("2008", date(2008, 1, 1), date(2008, 12, 31)),
    ("2009-2015", date(2009, 1, 1), date(2015, 10, 16)),
)
ERA_LABELS: tuple[str, ...] = (WHOLE,) + tuple(label for label, _s, _e in ERAS)


# --------------------------------------------------------------------------- the wrapper


class Tally:
    """What the wrapper saw on the decision sessions of one arm.

    The wrapper is the only thing in the stack that sees the inner allocator's answer *before* it
    is re-weighted, so it is the only thing that can say how often the inner returned nothing at
    all -- a whole-book gate firing, which no re-weighting can undo. That share is a first-class
    number in the report instead of a faked gate-free counterfactual (decision D3).

    Mutable on purpose, and carried on the arm's own frozen params with ``compare=False`` so the
    params value stays a value. One ``Tally`` per arm, created with the arm, read after its run.
    """

    __slots__ = ("calls", "empty", "names")

    def __init__(self) -> None:
        self.calls = 0
        self.empty = 0
        self.names = 0

    def saw(self, inner: int, kept: int) -> None:
        """One decision session: ``inner`` targets in, ``kept`` targets out."""
        self.calls += 1
        if inner == 0:
            self.empty += 1
        self.names += kept

    @property
    def empty_share(self) -> float | None:
        """The share of decision sessions on which the inner allocator returned no targets."""
        return None if self.calls == 0 else self.empty / self.calls

    @property
    def mean_names(self) -> float | None:
        """The mean size of the basket this arm asked for, over its decision sessions."""
        return None if self.calls == 0 else self.names / self.calls


@dataclass(frozen=True)
class ExposureParams:
    """One arm's params: the mode, the inner allocator's own params, and the frozen park set.

    ``as_dict`` follows every other params value in the repo (``backtest/report.py`` renders
    params through it); it is never read on the run path, so a params value whose own ``as_dict``
    is missing renders as its repr rather than failing a measurement.
    """

    mode: str
    inner_params: Any
    park: frozenset[str]
    tally: Tally = field(default_factory=Tally, compare=False, repr=False)

    def __post_init__(self) -> None:
        if self.mode not in (PICKS, FULL, PARK):
            raise ValueError(f"mode must be one of {(PICKS, FULL, PARK)}, got {self.mode!r}")
        if not isinstance(self.park, frozenset):
            raise TypeError(f"park must be a frozenset, got {type(self.park).__name__}")

    def as_dict(self) -> dict[str, str]:
        out = {"mode": self.mode, "park": ",".join(sorted(self.park))}
        inner = getattr(self.inner_params, "as_dict", None)
        rendered = dict(inner()) if callable(inner) else {"repr": repr(self.inner_params)}
        for k, v in rendered.items():
            out[f"inner.{k}"] = v
        return out


def _params(params: object) -> ExposureParams:
    if not isinstance(params, ExposureParams):
        raise TypeError(f"params must be ExposureParams, got {type(params).__name__}")
    return params


def reweight(targets: Sequence[Target], mode: str, park: AbstractSet[str]) -> tuple[Target, ...]:
    """``targets`` re-weighted for one arm; rank order and prices are untouched.

    ``picks`` drops the parked targets and keeps the survivors' weights, so the weight the parked
    names held becomes cash -- the method's own cash drag, left in. ``full`` drops them and
    rescales the survivors to fill the book; ``park`` keeps only the parked ones and rescales
    those.

    Every rescale goes through ``strategies.allocator.scale_weight``, which is ``to_weight(w x
    factor)`` and floors to ``WEIGHT_QUANTUM``, dropping a target that floors to zero. That is
    what keeps the result a legal basket: each floored weight is at most its exact share, the
    exact shares sum to one, and every floored weight is a multiple of 1e-6, so the floored sum
    can never exceed one -- which is the ``Allocator`` contract ``allocatorkit`` checks.
    """
    if mode == PICKS:
        return tuple(t for t in targets if t.symbol not in park)
    if mode == PARK:
        kept = tuple(t for t in targets if t.symbol in park)
    elif mode == FULL:
        kept = tuple(t for t in targets if t.symbol not in park)
    else:
        raise ValueError(f"mode must be one of {(PICKS, FULL, PARK)}, got {mode!r}")
    if not kept:
        return ()
    total = Decimal(0)
    for t in kept:
        total += t.weight
    if total <= 0:
        return ()
    factor = Decimal(1) / total
    out: list[Target] = []
    for t in kept:
        w = scale_weight(t.weight, factor)
        if w is not None:
            out.append(replace(t, weight=w))
    return tuple(out)


class ExposureAllocator:
    """Re-weights whatever its inner allocator returns, for one diagnostic arm.

    The inner allocator lives on the **instance**, not in the params, and preparation goes through
    ``strategies.allocator.prepare_for``. That is deliberate and load-bearing: ``LazyPrepared`` --
    the mechanism ``BLEND`` and ``VOLTARGET`` use to prepare inner objects that live in their
    params -- calls ``inner.prepare(history)`` and so silently loses ``prepare_market``. Twenty
    method files implement ``prepare_market`` to read the point-in-time fundamentals panel, and a
    wrapper built on ``LazyPrepared`` would quietly measure a bar-only version of every one of
    them and report the difference as a finding about their picks.

    ``id`` is an instance attribute, ``EXPOSURE-<inner id>``. ``dev.run_registry`` prepares once
    per allocator id and refuses two different allocator objects that share one, so ``wrapper_for``
    hands out exactly one wrapper per inner allocator object and all of a method's arms share it.
    Two inner objects that already share an id are refused by ``run_registry`` for the recorded
    arms themselves, so this adds no new failure mode.
    """

    __slots__ = ("id", "inner")

    def __init__(self, inner: Allocator) -> None:
        if not isinstance(inner, Allocator):
            raise TypeError(f"inner must be an Allocator, got {type(inner).__name__}")
        self.inner = inner
        self.id = f"EXPOSURE-{inner.id}"

    # -- delegated, so every arm runs on the window the recorded variant ran on

    def lookback(self, params: Any) -> int:
        return self.inner.lookback(_params(params).inner_params)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return self.inner.symbols(_params(params).inner_params)

    def uses_members(self, params: Any) -> bool:
        return self.inner.uses_members(_params(params).inner_params)

    def holds(self, params: Any) -> tuple[str, ...]:
        """What this arm may hold: nothing for the pick arms, the parked instruments for ``park``."""
        p = _params(params)
        if p.mode == PARK:
            return tuple(sorted(set(self.inner.holds(p.inner_params)) & p.park))
        return ()

    # -- preparation: the MarketAware path, never LazyPrepared

    def prepare(self, history: Mapping[str, History]) -> Any:
        return self.inner.prepare(history)

    def prepare_market(self, market: Any) -> Any:
        return prepare_for(self.inner, market)

    # -- the re-weighting

    def targets(
        self,
        history: Mapping[str, History],
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _params(params)
        inner = self.inner.targets(history, members, data_date, held, p.inner_params)
        out = reweight(inner, p.mode, p.park)
        p.tally.saw(len(inner), len(out))
        return out

    def targets_prepared(
        self,
        prepared: Any,
        members: AbstractSet[str],
        data_date: date,
        held: frozenset[str],
        params: Any,
    ) -> tuple[Target, ...]:
        p = _params(params)
        inner = self.inner.targets_prepared(prepared, members, data_date, held, p.inner_params)
        out = reweight(inner, p.mode, p.park)
        p.tally.saw(len(inner), len(out))
        return out


#: One wrapper per inner allocator **object**, memoized by identity. Module-level because the
#: inner allocators are module singletons and the memo must survive across the chunks of one
#: command. ``lab/`` is not globbed by ``tests/test_strategy_purity.py``, so a lab module may hold
#: state and log, as ``lab/survivorship_check.py`` already does.
_WRAPPERS: list[tuple[Any, ExposureAllocator]] = []


def wrapper_for(inner: Allocator) -> ExposureAllocator:
    """The one ``ExposureAllocator`` over ``inner``, created on first ask.

    ``dev.run_registry`` refuses two different allocator objects that share an ``allocator.id``,
    and every wrapper's id is derived from its inner's, so two wrappers over one inner would be
    refused the moment two arms of the same method met in one registry call. Keyed by **identity**
    rather than equality: two allocator values may compare equal without being the object the
    registry prepared.
    """
    for obj, wrapped in _WRAPPERS:
        if obj is inner:
            return wrapped
    wrapped = ExposureAllocator(inner)
    _WRAPPERS.append((inner, wrapped))
    return wrapped


# --------------------------------------------------------------------------- building the arms


def park_set(candidate: Candidate) -> frozenset[str]:
    """The instruments ``candidate`` parks money in: ``holds(params)`` plus any idle instrument.

    ``Allocator.holds`` is the existing, mandatory, already-maintained declaration of "the fixed
    instruments this allocator may hold", and ``dev.candidate_owner_inputs`` already reads it that
    way. ``rules.idle_symbol`` is the other half, and a different shape: the runner, not the
    allocator, places the residual weight there (``book_runner._with_idle``, which raises if an
    allocator targets it), so it never appears as a target and is stripped from the arms' rules
    instead -- see ``arm_rules``.
    """
    if is_bracket(candidate.rules):
        raise ValueError(f"{candidate.id} runs the bracket engine; it has no allocator to ask")
    holds = frozenset(candidate.allocator.holds(candidate.params))
    idle = candidate.rules.idle_symbol
    return holds | ({idle} if idle else frozenset())


def arm_rules(rules: TradeRules) -> TradeRules:
    """``rules`` with no idle instrument, for the three constructed arms.

    The idle instrument is parked money by definition: ``book_runner._with_idle`` puts whatever
    weight the allocator left over into it. A ``-PICKS`` arm that freed the parked weight only to
    have the runner put it straight back into an index instrument would measure nothing, so the
    three measured arms run with it off and their freed weight is cash. The recorded arm keeps its
    rules exactly as they were, because it is the reproduction check.

    No lab method sets ``idle_symbol`` today -- checked 2026-10-12 across every file in
    ``lab/methods/`` -- so for every method the diagnostic can currently be pointed at this
    returns the object it was given, unchanged.
    """
    return rules if rules.idle_symbol is None else replace(rules, idle_symbol=None)


def arm_candidate(c: Candidate, mode: str, park: AbstractSet[str]) -> Candidate:
    """One re-weighted arm of ``c``: the same inner allocator, wrapped, at the same params.

    ``family`` stays the method id, so an arm can never be mistaken for another family's row, and
    the id is the recorded id plus the arm suffix, which keeps it inside ``dev._ID``.
    ``owner_inputs`` is recomputed because the pick arms hold no ETF the recorded variant did.
    """
    arm = Candidate(
        id=f"{c.id}{ARM_SUFFIX[mode]}",
        family=c.family,
        rules=arm_rules(c.rules),
        allocator=wrapper_for(c.allocator),
        params=ExposureParams(mode=mode, inner_params=c.params, park=frozenset(park)),
        rationale=f"{ARM_LABEL[mode]} -- {c.rationale}",
        added=c.added,
        owner_inputs=(),
    )
    return replace(arm, owner_inputs=dev.candidate_owner_inputs(arm))


def arms_for(v: Variant) -> tuple[tuple[str, Candidate], ...]:
    """``(mode, candidate)`` for every arm of one variant, the recorded one first.

    Fresh ``ExposureParams`` -- and so a fresh ``Tally`` -- on every call: an arm is measured once.

    ``-PARK`` is built only when the inner allocator declares something it may hold. That is the
    only parked money a re-weighting can keep: an idle instrument is never a target, so for a
    method that parks only there the parked arm would be an all-cash book, and the report says so
    in a sentence instead of printing a column of zeroes.
    """
    out: list[tuple[str, Candidate]] = [(BOOK, v.candidate)]
    for mode in (PICKS, FULL):
        out.append((mode, arm_candidate(v.candidate, mode, v.park)))
    if v.holds:
        out.append((PARK, arm_candidate(v.candidate, PARK, v.park)))
    return tuple(out)


# --------------------------------------------------------------------------- what to re-run


@dataclass(frozen=True)
class Variant:
    """One recorded dev variant, resolved against the database before any store loads."""

    candidate: Candidate
    trial_n: int
    trial: sqlite3.Row = field(compare=False, repr=False)
    capital: Decimal
    contributions: ContributionSchedule | None
    park: frozenset[str]   # holds() plus any idle instrument: what counts as parked
    holds: frozenset[str]  # holds() alone: what a re-weighting can actually keep
    recorded_total_return: float | None
    recorded_mar: float | None
    recorded_eligible: bool

    @property
    def funded(self) -> bool:
        return self.contributions is not None


@dataclass(frozen=True)
class MethodPlan:
    method: Method
    variants: tuple[Variant, ...]
    missing: tuple[str, ...]  # recorded candidate ids that are no longer in the method file


def resolve_method(method_id: str) -> Method:
    """The committed ``METHOD`` for a lab method id (``store.LabError`` otherwise)."""
    if not isinstance(method_id, str) or METHOD_ID.fullmatch(method_id) is None:
        raise store.LabError(
            f"{method_id!r} is not a lab method id; `lab exposure` takes methods like M0030"
        )
    methods = discover()
    if method_id not in methods:
        raise store.LabError(
            f"no method file for {method_id} in seer_engine/lab/methods/. `lab exposure` re-runs "
            f"the committed method file, not a database row"
        )
    return methods[method_id][0]


def _f(x: object) -> float | None:
    return None if x is None else float(x)


def plan_method(conn: sqlite3.Connection, method_id: str) -> MethodPlan:
    """Every recorded dev variant of ``method_id`` that is still in its method file.

    Resolves each variant's recorded capital, funding and park set now, so a trial that cannot be
    re-run as the measurement it was -- or that has no targets to re-weight -- is refused before a
    store is opened. A funded trial's schedule is checked against its recorded deposit count here
    too (``hardgate.trial_deposits`` with an empty curve buckets nothing but still raises on a
    moved schedule).
    """
    method = resolve_method(method_id)
    trials = [t for t in store.trials_of(conn, method.id) if t["window"] == "dev"]
    if not trials:
        raise store.LabError(
            f"{method.id} has no dev trial; `lab exposure` re-weights what the lab recorded. "
            f"Run it with `lab run {method.id}` first"
        )
    by_id = {c.id: c for c in method.candidates}
    seen: set[str] = set()
    variants: list[Variant] = []
    missing: list[str] = []
    for t in trials:  # trials_of orders by n: the first recording of a variant wins
        cid = str(t["candidate_id"])
        if cid in seen:
            continue
        seen.add(cid)
        candidate = by_id.get(cid)
        if candidate is None:
            missing.append(cid)
            continue
        if is_bracket(candidate.rules):
            raise store.LabError(
                f"{cid} runs the bracket engine ({candidate.rules.id}), whose strategies are not "
                f"allocators and have no target weights to re-weight. `lab exposure` measures "
                f"book methods; there is no pick-versus-parked split to make here"
            )
        n = int(t["n"])
        capital = runner.recorded_capital(conn, n)
        contributions = runner.recorded_contributions(conn, n)
        if contributions is not None:
            hardgate.trial_deposits(conn, t, [])
        holds = frozenset(candidate.allocator.holds(candidate.params))
        variants.append(
            Variant(
                candidate=candidate,
                trial_n=n,
                trial=t,
                capital=capital,
                contributions=contributions,
                park=park_set(candidate),
                holds=holds,
                recorded_total_return=_f(t["total_return"]),
                recorded_mar=_f(t["mar"]),
                recorded_eligible=bool(t["eligible"]),
            )
        )
    if not variants:
        raise store.LabError(
            f"{method.id}: none of its recorded variants ({', '.join(missing)}) is in its method "
            f"file any more; there is nothing to re-weight"
        )
    return MethodPlan(method, tuple(variants), tuple(missing))


def plan_methods(
    conn: sqlite3.Connection, ids: Sequence[str], only: str | None = None
) -> tuple[MethodPlan, ...]:
    """``plan_method`` for each id, upper-cased and de-duplicated in the order given.

    ``only`` is a comma-separated list of recorded candidate ids. Every plan is then narrowed to
    those, and an id that matches no planned variant is a refusal rather than a silently empty
    run -- a typo that measured nothing would read as a method with no variants.
    """
    out: list[MethodPlan] = []
    done: set[str] = set()
    for raw in ids:
        mid = str(raw).strip().upper()
        if mid in done:
            continue
        done.add(mid)
        out.append(plan_method(conn, mid))
    if not out:
        raise store.LabError("name at least one method, e.g. `lab exposure M0030`")
    if only is None:
        return tuple(out)
    wanted = {part.strip().upper() for part in str(only).split(",") if part.strip()}
    if not wanted:
        raise store.LabError("--only was given but names no candidate id")
    narrowed: list[MethodPlan] = []
    kept: set[str] = set()
    for plan in out:
        keep = tuple(v for v in plan.variants if v.candidate.id in wanted)
        kept.update(v.candidate.id for v in keep)
        if keep:
            narrowed.append(replace(plan, variants=keep))
    unknown = sorted(wanted - kept)
    if unknown:
        raise store.LabError(
            f"--only names {', '.join(unknown)}, which is not a recorded dev variant of "
            f"{', '.join(p.method.id for p in out)}"
        )
    return tuple(narrowed)


# --------------------------------------------------------------------------- the store


def load_dev_store(store_dir: Path) -> research.ResearchData:
    """Load the dev-window store, or ``store.LabError``.

    ``research.load_store`` refuses a test-window store on its own; the window is checked again
    here on the loaded ``ResearchData.window``, which is the authoritative one. A store that
    carries a ``purpose`` marker (the survivorship-check store) is allowed and named in the
    report: this command compares four arms measured on **one** store with each other, so a
    marked store is internally consistent in a way ``lab survivorship``'s two-store comparison is
    not.
    """
    try:
        data = research.load_store(Path(store_dir))
    except FileNotFoundError as e:
        raise store.LabError(
            f"research store {store_dir} is missing {e.filename or e}. `.research/` is gitignored, "
            f"so a fresh worktree never has one -- point --store at a checkout that does rather "
            f"than rebuilding it (about 30 minutes plus a yfinance crawl)"
        ) from e
    except ValueError as e:
        raise store.LabError(
            f"{store_dir}: {e}. `lab exposure` re-runs the dev window and nothing else, so a "
            f"test-window store is refused here"
        ) from e
    if data.window != research.DEV_WINDOW:
        raise store.LabError(
            f"{store_dir} was built for the {data.window.name!r} window; `lab exposure` re-runs "
            f"the dev window and nothing else, and never spends a look"
        )
    return data


# --------------------------------------------------------------------------- one arm's numbers


@dataclass(frozen=True)
class Arm:
    """One arm's numbers. Holds no market, result or DevRow.

    ``exposure`` is ``RunStats.exposure``: the mean over sessions of invested / equity, where
    ``book_runner._invested`` counts only the non-idle positions. On the ``picks`` arm that is
    exactly the share of the book that was in the method's own picks -- the quantity M0107's
    session reported by hand, and the reason nothing in ``sim/`` or ``backtest/`` has to change.

    Gate labels are deliberately absent: an arm is a measurement, never a candidate, so it is
    never eligible, never promotable and never scored for luck (decision D11).
    """

    mode: str
    candidate_id: str
    start: date
    end: date
    funded: bool
    exposure: float
    total_return: float | None
    yearly: float | None      # money-weighted when the run was fed deposits, else CAGR
    spy_yearly: float | None  # SPY TR's same measure, same money on the same days
    max_drawdown: float | None
    profit_factor: float | None
    trades: int
    sharpe: float | None
    empty_share: float | None  # decision sessions on which the inner returned no targets
    mean_names: float | None   # mean basket size on a decision session
    era_yearly: Mapping[str, float | None]
    era_spy_yearly: Mapping[str, float | None]
    era_lead: Mapping[str, float | None]
    curve: tuple[tuple[date, float], ...] = field(compare=False, repr=False)

    @property
    def lead(self) -> float | None:
        """Whole-window yearly return minus SPY TR's, in the same measure."""
        return self.era_lead[WHOLE]


def arm_of(
    mode: str,
    v: Variant,
    row: DevRow,
    curve: Sequence[tuple[date, float]],
    deposits: Mapping[date, float],
    bench: Sequence[tuple[date, float]],
) -> Arm:
    """One arm's ``Arm`` from its ``DevRow``, its own monthly curve and the benchmark's.

    **Whole window** comes from the ``DevRow``: the money-weighted return when the run was funded
    and the CAGR otherwise, against ``row.spy_tr``'s same measure -- which ``dev._run`` already
    makes deposit-matched by feeding ``spy_curves`` the run's own cashflows on the run's own
    sessions.

    **Per era** goes through ``wf.measure``, which de-funds the whole curve with
    ``regime.defunded`` *before* it cuts it, against the recorded ``REF-SPY-HOLD`` curve sliced
    the same way. That is the path ``lab survivorship`` already uses for its 2009-2015 lead; a
    second reconstruction would be a second chance to read the owner's deposits as edge.
    """
    m = row.stats.metrics
    yearly = m.mwr if m.mwr is not None else m.cagr
    spy_yearly = row.spy_tr.mwr if row.spy_tr.mwr is not None else row.spy_tr.cagr
    params = row.candidate.params
    tally = params.tally if isinstance(params, ExposureParams) else None
    mine: dict[str, float | None] = {WHOLE: yearly}
    theirs: dict[str, float | None] = {WHOLE: spy_yearly}
    for label, start, end in ERAS:
        got = wf.measure(curve, start, end, deposits)
        ref = wf.measure(bench, start, end)
        mine[label] = None if got is None else got.cagr
        theirs[label] = None if ref is None else ref.cagr
    lead = {
        label: (None if mine[label] is None or theirs[label] is None else mine[label] - theirs[label])
        for label in ERA_LABELS
    }
    return Arm(
        mode=mode,
        candidate_id=row.candidate.id,
        start=row.start,
        end=row.end,
        funded=v.funded,
        exposure=float(row.stats.exposure),
        total_return=m.total_return,
        yearly=yearly,
        spy_yearly=spy_yearly,
        max_drawdown=m.max_drawdown,
        profit_factor=m.profit_factor,
        trades=int(m.trades),
        sharpe=row.stats.sharpe,
        empty_share=None if tally is None else tally.empty_share,
        mean_names=None if tally is None else tally.mean_names,
        era_yearly=mine,
        era_spy_yearly=theirs,
        era_lead=lead,
        curve=tuple(curve),
    )


@dataclass(frozen=True)
class StoreRun:
    """What the store was. Strings only: the store itself is gone by the time this is read."""

    store_dir: str
    fingerprint: str
    price_fingerprint: str | None
    purpose: str | None


def measure(
    conn: sqlite3.Connection,
    plans: Sequence[MethodPlan],
    data: research.ResearchData,
    bench: Sequence[tuple[date, float]],
) -> dict[tuple[str, str], dict[str, Arm]]:
    """Every arm of every variant of every plan: ``{(method id, candidate id): {mode: Arm}}``.

    One ``dev.run_registry`` call per (method, recorded capital, recorded schedule), chunked so no
    call can exceed ``dev.MAX_CANDIDATES`` arms -- a variant contributes at most four, so at most
    ``MAX_CANDIDATES // 4`` variants go into a call, and a variant's arms are never split across
    calls. Never across methods: two method files may define different allocator objects under one
    allocator id, which ``run_registry`` refuses within a call.

    Called with **no** ``window=`` keyword, so D9's ``DEV_WINDOW`` default binds and no code path
    here can name the test window. All four arms of one variant share that variant's recorded
    capital and funding, or they stop being a comparison (``lab/runner.py``: a re-run at the live
    constant is a different measurement).
    """
    if data.window != research.DEV_WINDOW:
        raise store.LabError(
            f"the loaded store declares the {data.window.name!r} window; `lab exposure` measures "
            f"the dev window and nothing else"
        )
    out: dict[tuple[str, str], dict[str, Arm]] = {}
    per_chunk = max(1, dev.MAX_CANDIDATES // len(MODES))
    for plan in plans:
        mid = plan.method.id
        groups: dict[tuple[Decimal, ContributionSchedule | None], list[Variant]] = {}
        for v in plan.variants:
            groups.setdefault((v.capital, v.contributions), []).append(v)
        for (capital, contributions), group in groups.items():
            for i in range(0, len(group), per_chunk):
                chunk = group[i : i + per_chunk]
                registry: list[Candidate] = []
                owner: dict[str, tuple[str, Variant]] = {}
                for v in chunk:
                    for mode, cand in arms_for(v):
                        registry.append(cand)
                        owner[cand.id] = (mode, v)

                def on_result(
                    _i: int, result: Any, row: DevRow, *, _mid: str = mid,
                    _owner: Mapping[str, tuple[str, Variant]] = owner,
                ) -> None:
                    mode, v = _owner[row.candidate.id]
                    curve = month_end_curve(result.snapshots)
                    deposits = hardgate.trial_deposits(conn, v.trial, list(curve))
                    arm = arm_of(mode, v, row, curve, deposits, bench)
                    out.setdefault((_mid, v.candidate.id), {})[mode] = arm
                    log.info(
                        "%s [%s]: %s of the book in its own picks, yearly %s vs SPY %s, max DD %s",
                        row.candidate.id, mode, fmt_pct(arm.exposure),
                        fmt_signed_pct(arm.yearly), fmt_signed_pct(arm.spy_yearly),
                        fmt_pct(arm.max_drawdown),
                    )

                dev.run_registry(
                    data.market, data.dividends, data.spy_dividends, tuple(registry),
                    on_result=on_result, contributions=contributions, initial_idr=capital,
                )
    return out


def measure_store(
    conn: sqlite3.Connection,
    plans: Sequence[MethodPlan],
    store_dir: Path,
    bench: Sequence[tuple[date, float]],
) -> tuple[StoreRun, dict[tuple[str, str], dict[str, Arm]]]:
    """Load the dev store, measure every arm on it, free it, return the numbers.

    The store is about 2.5M bar rows; only small ``Arm`` records survive the call, so a long run
    over many methods does not hold two copies of it.
    """
    t0 = time.perf_counter()
    data = load_dev_store(Path(store_dir))
    run = StoreRun(
        store_dir=str(store_dir),
        fingerprint=str(data.fingerprint),
        price_fingerprint=data.price_fingerprint,
        purpose=data.purpose,
    )
    log.info("dev store %s loaded (%.1fs)", run.fingerprint[:12], time.perf_counter() - t0)
    try:
        return run, measure(conn, plans, data, bench)
    finally:
        del data  # the only reference: the store is freed before the caller formats anything
        gc.collect()
        log.info("dev store released (%.1fs)", time.perf_counter() - t0)


# --------------------------------------------------------------------------- the comparison


@dataclass(frozen=True)
class VariantRow:
    method_id: str
    variant: Variant
    arms: Mapping[str, Arm]

    @property
    def book(self) -> Arm:
        return self.arms[BOOK]

    @property
    def modes(self) -> tuple[str, ...]:
        return tuple(m for m in MODES if m in self.arms)

    @property
    def reproduced(self) -> bool | None:
        """Did the recorded arm land on the recorded total return? None when either is missing."""
        recorded, measured = self.variant.recorded_total_return, self.book.total_return
        if recorded is None or measured is None:
            return None
        return abs(measured - recorded) <= REPRO_TOL * max(1.0, abs(recorded))


@dataclass(frozen=True)
class MethodReport:
    method_id: str
    method_name: str
    missing: tuple[str, ...]
    rows: tuple[VariantRow, ...]

    @property
    def headline(self) -> VariantRow:
        """The best recorded **eligible** variant by MAR, falling back to the best by MAR (D5).

        Ties break on the trial number, so the choice is reproducible rather than dict-ordered.
        M0024 and M0030 have no eligible variant at all, which is why the fallback exists.
        """
        return sorted(
            self.rows,
            key=lambda r: (
                not r.variant.recorded_eligible,
                r.variant.recorded_mar is None,
                -(r.variant.recorded_mar or 0.0),
                r.variant.trial_n,
            ),
        )[0]

    @property
    def reproduced(self) -> bool:
        return all(r.reproduced is not False for r in self.rows)


def compare(
    plans: Sequence[MethodPlan], arms: Mapping[tuple[str, str], Mapping[str, Arm]]
) -> tuple[MethodReport, ...]:
    out: list[MethodReport] = []
    for plan in plans:
        mid = plan.method.id
        rows: list[VariantRow] = []
        for v in plan.variants:
            measured = arms.get((mid, v.candidate.id))
            want = tuple(mode for mode, _c in arms_for(v))
            if measured is None or any(mode not in measured for mode in want):
                got = () if measured is None else tuple(sorted(measured))
                raise store.LabError(
                    f"{v.candidate.id}: expected arms {want}, measured {got}. The registry run "
                    f"did not produce a row for every arm, so there is nothing to compare"
                )
            rows.append(VariantRow(mid, v, dict(measured)))
        out.append(MethodReport(mid, plan.method.name, plan.missing, tuple(rows)))
    return tuple(out)


# --------------------------------------------------------------------------- the terminal report


def _finite(x: float | None) -> bool:
    return x is not None and math.isfinite(x)


def _variant_block(row: VariantRow) -> list[str]:
    v = row.variant
    modes = row.modes
    measure_name = "money-weighted" if v.funded else "CAGR"
    out = [
        f"  {v.candidate.id}  (trial #{v.trial_n}, {'funded' if v.funded else 'lump sum'}, "
        f"capital {v.capital:,.0f} IDR, {row.book.start}..{row.book.end})",
    ]
    if v.park:
        out.append(f"    parks money in: {', '.join(sorted(v.park))}")
    else:
        out.append(
            "    parks nothing: every target is one of its own picks, so the picks column is the "
            "recorded book and the full column is the same picks with the brake off"
        )
    if not v.holds and v.park:
        out.append(
            "    its parked money is the runner's idle instrument, which is never a target, so "
            "there is no parked column to build by re-weighting"
        )
    if v.candidate.rules.idle_symbol is not None:
        out.append(
            f"    the three measured columns run with the idle instrument "
            f"{v.candidate.rules.idle_symbol} switched off, so their freed weight is cash"
        )
    grid: list[tuple[str, tuple[str, ...]]] = [
        ("money in its own picks", tuple(fmt_pct(row.arms[m].exposure) for m in modes)),
        ("names it asked for (mean)", tuple(fmt_num(row.arms[m].mean_names, 1) for m in modes)),
        ("decision days with no pick", tuple(fmt_pct(row.arms[m].empty_share) for m in modes)),
        ("total return", tuple(fmt_signed_pct(row.arms[m].total_return) for m in modes)),
        (f"yearly return ({measure_name})", tuple(fmt_signed_pct(row.arms[m].yearly) for m in modes)),
        (f"SPY TR yearly ({measure_name})", tuple(fmt_signed_pct(row.arms[m].spy_yearly) for m in modes)),
        ("max drawdown", tuple(fmt_pct(row.arms[m].max_drawdown) for m in modes)),
        ("profit factor", tuple(fmt_pf(row.arms[m].profit_factor) for m in modes)),
        ("trades", tuple(str(row.arms[m].trades) for m in modes)),
        ("Sharpe (annualized)", tuple(fmt_num(row.arms[m].sharpe) for m in modes)),
        ("lead over SPY a year, by era:", tuple("" for _m in modes)),
    ]
    for label in ERA_LABELS:
        grid.append((f"  {label}", tuple(fmt_signed_pct(row.arms[m].era_lead[label]) for m in modes)))
    width = max(len(label) for label, _cells in grid)
    out.append(f"    {'':<{width}}" + "".join(f"  {ARM_HEAD[m]:>14}" for m in modes))
    for label, cells in grid:
        out.append(f"    {label:<{width}}" + "".join(f"  {c:>14}" for c in cells))
    head = (
        f"    recorded dev trial #{v.trial_n}: total return "
        f"{fmt_signed_pct(v.recorded_total_return)}"
    )
    rep = row.reproduced
    if rep is None:
        out.append(f"{head}; there is no number to check the recorded column against")
    elif rep:
        out.append(f"{head}; the recorded column reproduces it")
    else:
        out.append(
            f"{head}; the recorded column measured {fmt_signed_pct(row.book.total_return)} -- the "
            f"store or the engine changed since it ran, so compare the columns with each other, "
            f"not with the recorded trial"
        )
    return out


def format_report(rep: MethodReport, run: StoreRun) -> str:
    """One method's terminal grid. Ids, arm names and symbols are fine here."""
    out = [
        f"lab exposure {rep.method_id} -- {rep.method_name}: {len(rep.rows)} recorded variant(s) "
        f"on dev store {run.fingerprint[:12]}"
        + (f" (purpose {run.purpose!r})" if run.purpose else ""),
        "report only: no trial row, no moments, no funding, no status change; no method file "
        "changed and no method id was minted, so the lab's N and the test-window looks do not move",
        "columns: recorded = the variant as the lab ran it; picks = the parked instruments "
        "dropped at the weights it gave the rest; picks, full = those picks rescaled to fill the "
        "book with every brake off; parked = only the money it parks, rescaled to fill the book",
    ]
    if rep.missing:
        out.append(
            f"not measured (recorded, but no longer in the method file): {', '.join(rep.missing)}"
        )
    for row in rep.rows:
        out.append("")
        out += _variant_block(row)
    return "\n".join(out)


def summary_line(rep: MethodReport) -> str:
    h = rep.headline
    book, picks, full = h.book, h.arms[PICKS], h.arms[FULL]
    park = h.arms.get(PARK)
    bits = [
        f"{rep.method_id} ({h.variant.candidate.id}): {fmt_pct(picks.exposure)} of the book in "
        f"its own picks",
        f"lead over SPY a year {fmt_signed_pct(book.lead)} as recorded, {fmt_signed_pct(full.lead)} "
        f"from its picks alone on the whole book",
        f"2009-2015 lead {fmt_signed_pct(book.era_lead['2009-2015'])} -> "
        f"{fmt_signed_pct(full.era_lead['2009-2015'])}",
        f"no pick on {fmt_pct(picks.empty_share)} of its decision days",
    ]
    if park is not None:
        bits.append(f"its parked money alone led SPY by {fmt_signed_pct(park.lead)} a year")
    if not rep.reproduced:
        bits.append("WARNING: a recorded column did not reproduce its trial")
    return "; ".join(bits)


# --------------------------------------------------------------------------- the journal


def _verdict(full: Arm) -> str:
    """Did the picks alone beat the market in every era, in some, or in none?"""
    leads = [full.era_lead[label] for label in ERA_LABELS[1:]]
    judged = [x for x in leads if _finite(x)]
    ahead = [x for x in judged if x is not None and x > 0]
    if not judged:
        return "There were not enough years to judge its own picks period by period."
    if len(ahead) == len(judged):
        return (
            f"Its own picks beat the market in all {len(judged)} of the periods they could be "
            f"judged on. The earnings come from the picking."
        )
    if not ahead:
        return (
            f"Its own picks lost to the market in all {len(judged)} of the periods they could be "
            f"judged on. Whatever this method earned came from the money it parks in the market, "
            f"and from when it chose to hold it, not from the names it picks."
        )
    return (
        f"Its own picks beat the market in {len(ahead)} of the {len(judged)} periods they could "
        f"be judged on, and lost in the rest. The picking is not reliably where the earnings "
        f"come from."
    )


def insight_text(rep: MethodReport) -> tuple[str, str]:
    """``(title, body)`` in plain words for a non-trader: no ids, no code, no column names."""
    h = rep.headline
    book, picks, full = h.book, h.arms[PICKS], h.arms[FULL]
    park = h.arms.get(PARK)
    years = f"{book.start.year}-{book.end.year}"
    money = (
        "the same starting money and the same monthly top-ups"
        if h.variant.funded else "the same starting money"
    )
    intro = (
        f"The lab took the {len(rep.rows)} version(s) of this method it had already tested and ran "
        f"each of them again over the same {years} history, with {money}, in three further ways: "
        f"holding only the names it picks for itself; holding those same names with the whole "
        f"book behind them and every brake off; and holding only the money it parks in the "
        f"market. Nothing about the method changed -- only how its money was spread. The numbers "
        f"below are for its best version."
    )
    bullets = [
        f"- Of all the money it held, {fmt_pct(picks.exposure)} was in names it picked itself. "
        f"The rest sat in cash or in the market.",
        f"- As the lab recorded it, it earned {fmt_signed_pct(book.yearly)} a year against the "
        f"market's {fmt_signed_pct(book.spy_yearly)}.",
        f"- Its own picks, given the whole book and no brakes, earned "
        f"{fmt_signed_pct(full.yearly)} a year, which is {fmt_signed_pct(full.lead)} against the "
        f"market.",
        f"- On {fmt_pct(picks.empty_share)} of the days it chose what to hold, it had no pick to "
        f"make at all.",
    ]
    if park is not None:
        bullets.append(
            f"- The money it parks in the market, on its own, earned "
            f"{fmt_signed_pct(park.yearly)} a year, {fmt_signed_pct(park.lead)} against the market."
        )
    eras = "\n".join(
        f"- {label}: {fmt_signed_pct(book.era_lead[label])} a year against the market as "
        f"recorded, {fmt_signed_pct(full.era_lead[label])} from its own picks alone."
        for label in ERA_LABELS
    )
    body = "\n\n".join(
        (
            intro,
            "\n".join(bullets),
            "Period by period, ahead of or behind the market:",
            eras,
            _verdict(full),
            "This was a measurement, not a new try: nothing was recorded, the lab's count of "
            "tries did not move, and no verdict changed.",
        )
    )
    title = f"{rep.method_name}: what its own picks did, apart from the money it parks"
    return title, body


def journal(conn: sqlite3.Connection, rep: MethodReport) -> int:
    """One ``observation`` on the method. The caller owns the transaction. Returns its id."""
    title, body = insight_text(rep)
    return store.add_insight(
        conn, kind="observation", title=title, body=body, method_id=rep.method_id
    )


# --------------------------------------------------------------------------- the CSV grid


def _slug(label: str) -> str:
    return label.replace(" ", "_").replace("-", "_")


CSV_HEADER: tuple[str, ...] = (
    "method_id", "candidate_id", "arm", "arm_candidate_id", "store_fingerprint",
    "price_fingerprint", "store_purpose", "trial_n", "funded", "capital_idr", "parked",
    "start", "end", "exposure", "mean_names", "empty_share", "total_return",
    "recorded_total_return", "reproduced", "yearly_return", "spy_yearly_return", "lead",
    "max_drawdown", "profit_factor", "trades", "sharpe",
    *(f"lead_{_slug(label)}" for label in ERA_LABELS),
    *(f"yearly_{_slug(label)}" for label in ERA_LABELS),
    *(f"spy_yearly_{_slug(label)}" for label in ERA_LABELS),
)


def _cell(x: object) -> str:
    if x is None:
        return ""
    if isinstance(x, bool):
        return "1" if x else "0"
    if isinstance(x, float):
        return repr(x)  # full precision; inf stays "inf"
    if isinstance(x, date):
        return x.isoformat()
    return str(x)


def csv_rows(reports: Sequence[MethodReport], run: StoreRun) -> list[list[str]]:
    out: list[list[str]] = [list(CSV_HEADER)]
    for rep in reports:
        for row in rep.rows:
            v = row.variant
            for mode in row.modes:
                arm = row.arms[mode]
                out.append([
                    _cell(x) for x in (
                        rep.method_id, v.candidate.id, mode, arm.candidate_id, run.fingerprint,
                        run.price_fingerprint, run.purpose, v.trial_n, v.funded, v.capital,
                        " ".join(sorted(v.park)), arm.start, arm.end, arm.exposure,
                        arm.mean_names, arm.empty_share, arm.total_return,
                        v.recorded_total_return,
                        row.reproduced if mode == BOOK else None,
                        arm.yearly, arm.spy_yearly, arm.lead, arm.max_drawdown,
                        arm.profit_factor, arm.trades, arm.sharpe,
                        *(arm.era_lead[label] for label in ERA_LABELS),
                        *(arm.era_yearly[label] for label in ERA_LABELS),
                        *(arm.era_spy_yearly[label] for label in ERA_LABELS),
                    )
                ])
    return out


def write_csv(reports: Sequence[MethodReport], run: StoreRun, path: Path) -> Path:
    """Write the full variant x arm grid to ``path`` (parents created). Returns the path written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(csv_rows(reports, run))
    return path
```

**Impact:** a new, self-contained lab module. Nothing else in the engine imports it yet; Step 2
wires it to the CLI. `lab/` is not globbed by `engine/tests/test_strategy_purity.py`, so the
`logging` import and the module-level `_WRAPPERS` memo are allowed, exactly as in
`lab/survivorship_check.py`.

---

### Step 2a: the module docstring's command list

**File:** `engine/src/seer_engine/commands/lab.py:66` — insert between the `lab survivorship`
block (lines 61-66) and `    lab idea --name ...` (line 67).
**Change:** one block in the command list, matching the surrounding indentation (4 spaces for the
command line, 36 for the description column).

**Code (insert exactly, as new lines after line 66):**

```
    lab exposure M0030 [M0024 ...] [--only IDS] [--store DIR] [--csv PATH] [--no-journal]
                                    report only: what share of a method's money was ever in its
                                    own picks rather than parked in the market, and what those
                                    picks did alone against SPY per era, with the parked holding
                                    removed and the brakes off. Four columns per recorded variant,
                                    no method file changed and no new method id. No trial row, no
                                    moments, no status change: N and the looks do not move
```

**Impact:** `lab --help` and the module docstring list the new subcommand. No existing line moves.

---

### Step 2b: the subparser

**File:** `engine/src/seer_engine/commands/lab.py:370` — insert after the `survivorship` parser's
last `s.add_argument("--csv", ...)` line (370) and the blank line, immediately before
`    s = sub.add_parser("idea", ...)` (line 372).
**Change:** one `sub.add_parser("exposure", ...)` block plus its arguments.

**Code:**

```python
    s = sub.add_parser(
        "exposure",
        # No literal `%` in any `help=` string below, and none may be added: argparse runs every
        # `help=` through %-interpolation (HelpFormatter._expand_help), so a bare `%` is read as a
        # format spec and `lab --help` dies. A doubled `%%` renders as one `%`. `description=` is
        # NOT interpolated and must stay single. See the `costs` parser above.
        help="report only: how much of a method's money was in its own picks, and what they did alone",
        description=(
            "Re-run every recorded dev variant of each named method at its recorded capital and "
            "funding, four times on the dev window: the candidate as the lab recorded it; its own "
            "picks with the parked instruments dropped at the weights it gave the rest; those "
            "picks rescaled to fill the whole book with every brake off; and the parked money "
            "alone. Prints the share of the book that was ever in its own picks, the share of "
            "decision days it had no pick to make, and the lead over SPY whole-window and per era "
            "(1996-2002, 2003-2008, 2008 alone, 2009-2015). Parked is read generically from the "
            "allocator's own holds(), so no method file changes and no method id is minted. "
            "Records no trial, no moments, no funding and no status, so the lab's N and the "
            "test-window looks do not move and the test window is never read; one plain-words "
            "observation per method is journaled unless --no-journal."
        ),
    )
    s.add_argument("method", nargs="+", metavar="M0030", help="the methods to measure")
    s.add_argument(
        "--only", "--candidate", default=None, metavar="IDS",
        help="measure only these recorded variants (comma-separated candidate ids, e.g. "
             "M0030-C50T) instead of every recorded dev variant of each method",
    )
    s.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR),
        help=f"the dev store the trials were recorded on (default: {research.STORE_DIR}, or "
             "$SEER_RESEARCH_STORE); a test-window store is refused. The store is gitignored, so "
             "a fresh worktree has none -- point this at a checkout that does",
    )
    s.add_argument("--no-journal", action="store_true",
                   help="print the report and write nothing at all, not even the observation")
    s.add_argument("--csv", type=Path, default=None, metavar="PATH",
                   help="also write the full grid (variant x column) to PATH as CSV, full precision")
```

**Impact:** `lab exposure --help` renders. `--only` and `--candidate` share the dest `only`.

---

### Step 2c: the handler

**File:** `engine/src/seer_engine/commands/lab.py:2197` — insert after `_survivorship` ends and
before `def _idea(conn, args) -> int:` (line 2199), separated by two blank lines like every other
handler.
**Change:** one handler, mirroring `_survivorship` (`commands/lab.py:2148`).

**Code:**

```python
def _exposure(conn, args) -> int:
    """``lab exposure M0030 [M0024 ...]``: a method's own picks, apart from what it parks.

    Report only. Every refusal that needs no bars -- the method ids, their files, their recorded
    trials, a bracket-engine variant with no targets to re-weight, the recorded capital and
    funding, an unknown --only id, the benchmark geometry -- is made before the research store is
    loaded. Then four arms per recorded variant run on the dev window and the grid is printed.
    Nothing is written except one observation per method (none with --no-journal); N and the
    test-window looks are printed before and after so the invariant is visible, not just tested.
    """
    from seer_engine.lab import exposure as exp
    from seer_engine.lab import hardgate

    if research.DEV_END != dev.DEV_END:
        raise store.LabError("research.DEV_END differs from dev.DEV_END; refusing to run")
    plans = exp.plan_methods(conn, args.method, args.only)
    geo = hardgate.geometry(conn)  # the recorded SPY hold: the per-era benchmark, before any load
    n_before = store.dev_trial_count(conn)
    looks_before = store.test_looks(conn)
    t0 = time.perf_counter()
    run, arms = exp.measure_store(conn, plans, Path(args.store), geo.bench)
    reports = exp.compare(plans, arms)
    for rep in reports:
        print(exp.format_report(rep, run))
        print()
    print("summary (best recorded eligible variant by MAR, else the best by MAR):")
    for rep in reports:
        print(f"  {exp.summary_line(rep)}")
    if args.csv is not None:
        written = exp.write_csv(reports, run, Path(args.csv))
        print(f"\ngrid written to {written}")
    if args.no_journal:
        tail = "No journal entry (--no-journal), so `lab stage` is not needed."
    else:
        with conn:
            entries = [exp.journal(conn, rep) for rep in reports]
        tail = (
            f"journal entries {', '.join(f'#{e}' for e in entries)} written (one observation per "
            f"method). Solo: `python -m seer_engine lab stage` so seertrade.site/sera shows them."
        )
    print(
        f"\nNo trial was recorded and no method id was minted. Lab N (dev trials): {n_before} "
        f"before, {store.dev_trial_count(conn)} after; test-window looks used: {looks_before} "
        f"before, {store.test_looks(conn)} after. {tail}"
    )
    log.info("lab exposure: %d method(s) done (%.1fs)", len(reports), time.perf_counter() - t0)
    return 0
```

**Impact:** uses only names already imported at the top of `commands/lab.py` (`research`, `dev`,
`store`, `Path`, `time`, `log`), plus the two function-local imports, exactly as `_survivorship`
does.

---

### Step 2d: the `_HANDLERS` entry

**File:** `engine/src/seer_engine/commands/lab.py:2350` — insert immediately after
`    "survivorship": _survivorship,`.
**Change:** one dict entry.

**Code:**

```python
    "exposure": _exposure,
```

**Impact:** `lab exposure` dispatches. `store.LabError` -> exit 2, anything else -> exit 1, via
the existing `run()` at `commands/lab.py:420`.

---

### Step 3: `engine/tests/test_lab_exposure.py`

**File:** `engine/tests/test_lab_exposure.py` (new; the whole file below)
**Change:** create the test module. Shape copied from `engine/tests/test_lab_survivorship.py`.

**Code:**

```python
"""``lab exposure``: a method's own picks, measured apart from the money it parks.

Report only: N, the looks and every trial-side table stay as they were; every refusal comes before
a store loads; the wrapper keeps the Allocator contract; and a method that parks half its book
reads differently with the parked half removed.
"""

from __future__ import annotations

import csv
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from allocatorkit import assert_p4_identity, assert_valid_targets, everyone, upto
from labkit import smoke_data, smoke_test_data

from seer_engine import cli, research
from seer_engine.backtest.dev import Candidate
from seer_engine.lab import exposure as exp
from seer_engine.lab import hardgate, runner, store
from seer_engine.lab.method import Method
from seer_engine.lab.seed import seed
from seer_engine.sim.book import WEIGHT_QUANTUM, Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC, MONTHLY_HOLD_TBILL
from seer_engine.strategies.allocator import (
    BLEND,
    Allocator,
    BlendParams,
    BlendPart,
    last_close,
    target_from_close,
)
from seer_engine.strategies.f_factor import FACTOR, FactorParams
from seer_engine.strategies.f_index import TIMING, TimingParams

HERE = Path(__file__)
PARKED = "SPY"
PARAMS_A = FactorParams(rank="lowvol", top=6, mom_n=60, mom_skip=0, vol_n=20, trend=None)
PARAMS_B = FactorParams(rank="momentum", top=6, mom_n=40, mom_skip=0, vol_n=20, trend=None)
ALWAYS_SPY = TimingParams(hold=PARKED, signal=PARKED, rule="always")


def _blend(params: FactorParams) -> BlendParams:
    """Half a timed-off-never SPY core, half a stock sleeve: M0030's shape on the smoke fixture."""
    return BlendParams((
        BlendPart(TIMING, ALWAYS_SPY, Decimal("0.5")),
        BlendPart(FACTOR, params, Decimal("0.5")),
    ))


def _cand(cid: str, params: FactorParams, *, parks: bool = True) -> Candidate:
    allocator: Any = BLEND if parks else FACTOR
    return Candidate(
        id=cid, family="M0001", rules=MONTHLY_HOLD_FRAC, allocator=allocator,
        params=_blend(params) if parks else params,
        rationale="test", added=date(2026, 10, 12), owner_inputs=(),
    )


def _method(cands=None) -> Method:
    return Method(
        id="M0001", name="Half the market, half quiet stocks", family="factor",
        source_kind="knowledge", source_ref="", hypothesis="h", expected_failure="f",
        candidates=cands or (_cand("M0001-A", PARAMS_A), _cand("M0001-B", PARAMS_B)),
    )


# ---- a tiny parking allocator, for the contract checks -------------------------------------------


class ParkingFake:
    """Half its weight in one fixed instrument, half split between two members with a bar on d."""

    id = "FAKE_PARK"

    def lookback(self, params: Any) -> int:
        return 1

    def symbols(self, params: Any) -> tuple[str, ...]:
        return tuple(sorted({PARKED, "AAA", "BBB"}))

    def holds(self, params: Any) -> tuple[str, ...]:
        return (PARKED,)

    def uses_members(self, params: Any) -> bool:
        return False

    def targets(self, history, members, data_date, held, params) -> tuple[Target, ...]:
        out: list[Target] = []
        for symbol, weight in ((PARKED, "0.5"), ("AAA", "0.25"), ("BBB", "0.25")):
            h = history.get(symbol)
            close = last_close(h, data_date)
            if close is None or (h.index_of(data_date) is None and symbol not in held):
                continue
            t = target_from_close(symbol, close, Decimal(weight))
            if t is not None:
                out.append(t)
        return tuple(out)

    def prepare(self, history):
        return dict(history)

    def targets_prepared(self, prepared, members, data_date, held, params) -> tuple[Target, ...]:
        return self.targets(prepared, members, data_date, held, params)


PARKING = ParkingFake()


# ---- fixtures ------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def dev_data():
    return smoke_data()


@pytest.fixture()
def lab(tmp_path):
    path = tmp_path / "lab.sqlite"
    c = store.connect(path)
    seed(c)
    yield c, path
    c.close()


@pytest.fixture()
def recorded(lab, dev_data, monkeypatch):
    conn, _ = lab
    m = _method()
    runner.run_method(conn, m, HERE, dev_data, git_sha="x", require_commit=False)
    monkeypatch.setattr(exp, "discover", lambda: {"M0001": (m, HERE)})
    return m


def _dir(tmp_path) -> Path:
    d = tmp_path / "dev-store"
    d.mkdir()
    return d


def _loader(by_dir):
    def load(store_dir, **kw):
        got = by_dir[Path(store_dir)]
        if isinstance(got, BaseException):
            raise got
        return replace(got)

    return load


def _untouched(conn):
    """Everything `lab exposure` must leave as it found it (insights excepted)."""
    return (
        store.dev_trial_count(conn),
        store.test_looks(conn),
        conn.execute("SELECT count(*) FROM trials").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_funding").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_provenance").fetchone()[0],
        tuple(tuple(r) for r in conn.execute(
            "SELECT id, status, verdict, source_sha FROM methods ORDER BY id")),
    )


def _insights(conn) -> int:
    return conn.execute("SELECT count(*) FROM insights").fetchone()[0]


def _measure(conn, dev_data, tmp_path, monkeypatch, only=None):
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data}))
    plans = exp.plan_methods(conn, ["M0001"], only)
    geo = hardgate.geometry(conn)
    run, arms = exp.measure_store(conn, plans, d, geo.bench)
    return exp.compare(plans, arms), run


# ---- the wrapper keeps the Allocator contract ----------------------------------------------------


def _cases(dev_data):
    """The fixture's histories and its last twelve sessions.

    ``History.dates`` is ``datetime64[D]``; ``.tolist()`` already yields ``datetime.date``.
    """
    history = dev_data.market.history
    return history, list(history[PARKED].dates.tolist())[-12:]


@pytest.mark.parametrize("mode", [exp.PICKS, exp.FULL, exp.PARK])
def test_the_wrapper_keeps_the_allocator_contract(dev_data, mode):
    history, days = _cases(dev_data)
    wrapper = exp.wrapper_for(PARKING)
    assert isinstance(wrapper, Allocator)
    params = [exp.ExposureParams(mode=mode, inner_params=None, park=frozenset({PARKED}))]
    nonempty = assert_p4_identity(
        wrapper, history, everyone(history), days,
        [frozenset(), frozenset({PARKED, "AAA"})], params,
    )
    assert nonempty > 0  # the check was not vacuous


def test_one_wrapper_per_inner_object():
    """``dev.run_registry`` refuses two allocator objects sharing an id, so the memo is required."""
    assert exp.wrapper_for(PARKING) is exp.wrapper_for(PARKING)
    other = ParkingFake()
    assert exp.wrapper_for(other) is not exp.wrapper_for(PARKING)
    assert exp.wrapper_for(PARKING).id == "EXPOSURE-FAKE_PARK"


def test_the_wrapper_delegates_preparation_to_prepare_for(dev_data):
    """A MarketAware inner must keep its market: LazyPrepared would silently drop it."""
    seen: list[Any] = []

    class MarketAwareFake(ParkingFake):
        id = "FAKE_MARKET"

        def prepare_market(self, market):
            seen.append(market)
            return dict(market.history)

    wrapper = exp.wrapper_for(MarketAwareFake())
    prepared = wrapper.prepare_market(dev_data.market)
    assert seen == [dev_data.market]
    assert set(prepared) == set(dev_data.market.history)


# ---- the re-weighting arithmetic -----------------------------------------------------------------


def _targets(dev_data, data_date):
    return PARKING.targets(dev_data.market.history, frozenset(), data_date, frozenset(), None)


def test_reweight_drops_rescales_and_stays_a_legal_basket(dev_data):
    history, days = _cases(dev_data)
    d = days[-1]
    full_basket = _targets(dev_data, d)
    assert [t.symbol for t in full_basket] == [PARKED, "AAA", "BBB"]
    park = frozenset({PARKED})

    picks = exp.reweight(full_basket, exp.PICKS, park)
    assert [t.symbol for t in picks] == ["AAA", "BBB"]
    assert [t.weight for t in picks] == [Decimal("0.25"), Decimal("0.25")]  # weights kept

    full = exp.reweight(full_basket, exp.FULL, park)
    assert [t.symbol for t in full] == ["AAA", "BBB"]
    assert sum(t.weight for t in full) == Decimal("1.000000")

    parked = exp.reweight(full_basket, exp.PARK, park)
    assert [(t.symbol, t.weight) for t in parked] == [(PARKED, Decimal("1.000000"))]

    for got in (picks, full, parked):
        assert_valid_targets(got, history, d, frozenset())
        for t in got:
            assert t.weight.quantize(WEIGHT_QUANTUM) == t.weight

    assert exp.reweight((), exp.FULL, park) == ()
    assert exp.reweight(full_basket, exp.PARK, frozenset()) == ()


def test_reweight_with_an_empty_park_set_changes_nothing_on_the_picks_arm(dev_data):
    _history, days = _cases(dev_data)
    basket = _targets(dev_data, days[-1])
    assert exp.reweight(basket, exp.PICKS, frozenset()) == basket


def test_reweight_rescales_an_awkward_sum_without_exceeding_one(dev_data):
    """Three equal thirds rescale to 0.333333 each: floored down, so Σ is 0.999999, never > 1."""
    _history, days = _cases(dev_data)
    d = days[-1]
    close = last_close(dev_data.market.history["AAA"], d)
    third = Decimal("0.111111")
    basket = tuple(
        target_from_close(s, close, third) for s in ("AAA", "BBB", "CCC")
    )
    got = exp.reweight(basket, exp.FULL, frozenset())
    assert sum(t.weight for t in got) <= Decimal(1)
    assert all(t.weight == Decimal("0.333333") for t in got)


# ---- the park set and the arms -------------------------------------------------------------------


def test_the_park_set_is_read_from_holds_and_the_idle_instrument():
    c = _cand("M0001-A", PARAMS_A)
    assert exp.park_set(c) == frozenset({PARKED})
    plain = _cand("M0001-C", PARAMS_A, parks=False)
    assert exp.park_set(plain) == frozenset()
    idle = replace(plain, rules=MONTHLY_HOLD_TBILL)  # the one shipped rules value with an idle leg
    assert exp.park_set(idle) == frozenset({"BIL"})
    assert exp.arm_rules(idle.rules).idle_symbol is None
    assert exp.arm_rules(plain.rules) is plain.rules


def test_four_arms_when_it_parks_and_three_when_it_does_not(lab, dev_data, recorded):
    conn, _ = lab
    (plan,) = exp.plan_methods(conn, ["M0001"])
    modes = [mode for mode, _c in exp.arms_for(plan.variants[0])]
    assert modes == [exp.BOOK, exp.PICKS, exp.FULL, exp.PARK]
    ids = [c.id for _m, c in exp.arms_for(plan.variants[0])]
    assert ids == ["M0001-A", "M0001-A-PICKS", "M0001-A-FULL", "M0001-A-PARK"]
    for _mode, c in exp.arms_for(plan.variants[0]):
        assert c.family == "M0001"
    bare = replace(plan.variants[0], park=frozenset(), holds=frozenset())
    assert [m for m, _c in exp.arms_for(bare)] == [exp.BOOK, exp.PICKS, exp.FULL]


# ---- the measurement -----------------------------------------------------------------------------


def test_the_parked_half_is_separated_and_nothing_is_written(lab, dev_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    before, notes = _untouched(conn), _insights(conn)
    (rep,), run = _measure(conn, dev_data, tmp_path, monkeypatch)
    assert [r.variant.candidate.id for r in rep.rows] == ["M0001-A", "M0001-B"]
    row = rep.rows[0]
    assert row.modes == (exp.BOOK, exp.PICKS, exp.FULL, exp.PARK)
    assert row.reproduced is True
    book, picks, full, park = (row.arms[m] for m in row.modes)
    # Half the book is a fixed SPY holding, so the picks sleeve holds about half the money.
    assert picks.exposure < book.exposure
    assert full.exposure > picks.exposure
    assert park.exposure > 0.0
    assert picks.empty_share == 0.0 and picks.mean_names is not None
    assert book.empty_share is None  # the recorded arm runs unwrapped, so nothing counted it
    assert set(book.era_lead) == set(exp.ERA_LABELS)
    assert run.fingerprint == "smoke"
    assert _untouched(conn) == before and _insights(conn) == notes


def test_the_picks_arm_reproduces_the_book_when_nothing_is_parked(lab, dev_data, tmp_path, monkeypatch):
    conn, _ = lab
    m = _method((_cand("M0001-C", PARAMS_A, parks=False),))
    runner.run_method(conn, m, HERE, dev_data, git_sha="x", require_commit=False)
    monkeypatch.setattr(exp, "discover", lambda: {"M0001": (m, HERE)})
    (rep,), _run = _measure(conn, dev_data, tmp_path, monkeypatch)
    row = rep.rows[0]
    assert row.modes == (exp.BOOK, exp.PICKS, exp.FULL)  # no park column
    assert row.arms[exp.PICKS].total_return == row.arms[exp.BOOK].total_return
    assert row.arms[exp.PICKS].exposure == row.arms[exp.BOOK].exposure


def test_every_arm_runs_at_the_recorded_capital_and_funding(lab, dev_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    seen: list = []
    real = exp.dev.run_registry

    def spy(*a, **k):
        seen.append((k.get("initial_idr"), k.get("contributions"), "window" in k, len(a[3])))
        return real(*a, **k)

    monkeypatch.setattr(exp.dev, "run_registry", spy)
    _measure(conn, dev_data, tmp_path, monkeypatch)
    n = int(store.trials_of(conn, "M0001")[0]["n"])
    want = (runner.recorded_capital(conn, n), runner.recorded_contributions(conn, n))
    assert len(seen) == 1  # both variants share capital and schedule: one call
    assert seen[0][:3] == (*want, False)  # and NO window= keyword, so the dev default binds
    assert seen[0][3] == 8  # two variants x four arms


# ---- refusals ------------------------------------------------------------------------------------


def _boom(*a, **k):
    raise AssertionError("a store must not be loaded for a refusal")


def test_cli_refuses_unknown_or_unrun_methods_before_loading(lab, recorded, tmp_path, monkeypatch):
    _, path = lab
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _boom)
    for mid in ("M9999", "H-P7A", "nonsense"):
        assert cli.main(["lab", "--db", str(path), "exposure", mid, "--store", str(d)]) == 2


def test_an_unknown_only_id_is_refused_before_loading(lab, recorded, tmp_path, monkeypatch):
    conn, path = lab
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _boom)
    with pytest.raises(store.LabError, match="not a recorded dev variant"):
        exp.plan_methods(conn, ["M0001"], "M0001-ZZZ")
    assert cli.main(["lab", "--db", str(path), "exposure", "M0001",
                     "--only", "M0001-ZZZ", "--store", str(d)]) == 2
    (plan,) = exp.plan_methods(conn, ["M0001"], "m0001-a")
    assert [v.candidate.id for v in plan.variants] == ["M0001-A"]


def test_a_bracket_variant_is_refused_before_loading(lab, dev_data, monkeypatch):
    conn, _ = lab
    from seer_engine.sim.rules import DESIGN_V0
    from seer_engine.strategies.a import DESIGN_PARAMS, STRATEGY_A

    m = _method()
    runner.run_method(conn, m, HERE, dev_data, git_sha="x", require_commit=False)
    bracket = Candidate(id="M0001-A", family="M0001", rules=DESIGN_V0, allocator=STRATEGY_A,
                        params=DESIGN_PARAMS, rationale="t", added=date(2026, 10, 12),
                        owner_inputs=())
    monkeypatch.setattr(exp, "discover", lambda: {"M0001": (_method((bracket,)), HERE)})
    with pytest.raises(store.LabError, match="bracket engine"):
        exp.plan_methods(conn, ["M0001"])


def test_a_trial_with_no_recorded_capital_is_refused_before_loading(lab, recorded, monkeypatch):
    conn, _ = lab
    monkeypatch.setattr(store, "provenance_of", lambda c, n: None)
    with pytest.raises(store.LabError, match="no recorded starting capital"):
        exp.plan_methods(conn, ["M0001"])


def test_a_variant_gone_from_the_file_is_listed_not_run(lab, dev_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    monkeypatch.setattr(exp, "discover", lambda: {"M0001": (_method((_cand("M0001-A", PARAMS_A),)), HERE)})
    (rep,), run = _measure(conn, dev_data, tmp_path, monkeypatch)
    assert rep.missing == ("M0001-B",)
    assert "no longer in the method file): M0001-B" in exp.format_report(rep, run)


def test_a_test_window_store_is_refused(lab, recorded, tmp_path, monkeypatch):
    conn, path = lab
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: smoke_test_data()}))
    with pytest.raises(store.LabError, match="dev window"):
        exp.load_dev_store(d)
    monkeypatch.setattr(research, "load_store", _loader({d: ValueError("declares the 'test' window")}))
    with pytest.raises(store.LabError, match="test-window store is refused"):
        exp.load_dev_store(d)
    before = _untouched(conn)
    assert cli.main(["lab", "--db", str(path), "exposure", "M0001", "--store", str(d)]) == 2
    assert _untouched(conn) == before


# ---- the command ---------------------------------------------------------------------------------


def test_cli_reports_journals_and_writes_the_grid(lab, dev_data, recorded, tmp_path, monkeypatch, capsys):
    conn, path = lab
    before, notes = _untouched(conn), _insights(conn)
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data}))
    grid = tmp_path / "out" / "grid.csv"
    argv = ["lab", "--db", str(path), "exposure", "m0001", "M0001", "--store", str(d),
            "--csv", str(grid)]
    assert cli.main(argv) == 0
    out = capsys.readouterr().out
    assert "report only" in out and "money in its own picks" in out
    assert "parks money in: SPY" in out
    assert "lead over SPY a year, by era:" in out and "2009-2015" in out
    assert f"Lab N (dev trials): {before[0]} before, {before[0]} after" in out
    assert "no method id was minted" in out
    assert _untouched(conn) == before
    assert _insights(conn) == notes + 1  # one method, named twice: one observation
    rows = list(csv.reader(grid.open(encoding="utf-8")))
    assert rows[0] == list(exp.CSV_HEADER)
    assert [(r[1], r[2]) for r in rows[1:]] == [
        ("M0001-A", "book"), ("M0001-A", "picks"), ("M0001-A", "full"), ("M0001-A", "park"),
        ("M0001-B", "book"), ("M0001-B", "picks"), ("M0001-B", "full"), ("M0001-B", "park"),
    ]


def test_no_journal_writes_nothing(lab, dev_data, recorded, tmp_path, monkeypatch, capsys):
    conn, path = lab
    before, notes = _untouched(conn), _insights(conn)
    d = _dir(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data}))
    assert cli.main(["lab", "--db", str(path), "exposure", "M0001", "--store", str(d),
                     "--no-journal"]) == 0
    assert "No journal entry" in capsys.readouterr().out
    assert _untouched(conn) == before and _insights(conn) == notes


def test_the_journal_entry_is_plain_words(lab, dev_data, recorded, tmp_path, monkeypatch):
    conn, _ = lab
    (rep,), _run = _measure(conn, dev_data, tmp_path, monkeypatch)
    before = _untouched(conn)
    with conn:
        entry = exp.journal(conn, rep)
    row = conn.execute("SELECT * FROM insights WHERE id = ?", (entry,)).fetchone()
    assert row["kind"] == "observation" and row["method_id"] == "M0001"
    assert row["title"].endswith("what its own picks did, apart from the money it parks")
    for text in (row["title"], row["body"]):
        for banned in ("M0001", "-PICKS", "-FULL", "-PARK", "`", "DSR", "MAR", "exposure"):
            assert banned not in text, banned
    assert "count of tries did not move" in row["body"]
    assert _untouched(conn) == before


def test_the_help_strings_still_format(capsys):
    """argparse %-interpolates every help= string; a bare % there kills `lab --help`."""
    with pytest.raises(SystemExit) as e:
        cli.main(["lab", "exposure", "--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "--only" in out and "--no-journal" in out and "--csv" in out
    with pytest.raises(SystemExit):
        cli.main(["lab", "--help"])
    assert "exposure" in capsys.readouterr().out
```

**Impact:** the new module is covered end to end on the smoke fixture. Three details the
implementer must confirm against the tree while writing the file, and adjust the test (never the
module) if the tree disagrees:

1. `sim.rules.MONTHLY_HOLD_TBILL` (`sim/rules.py:185`) is `MONTHLY_HOLD` with
   `idle_symbol="BIL"` — the one shipped rules value with an idle leg, and the only reason the
   idle branch of `park_set`/`arm_rules` is testable at all.
2. `strategies.a.STRATEGY_A` and `strategies.a.DESIGN_PARAMS` (`a.py:96`) with
   `sim.rules.DESIGN_V0` (`rules.py:169`) build the one bracket candidate the refusal test needs.
   Verified present 2026-10-12 (`engine/tests/test_backtest_metrics.py:47` imports both).
3. `assert_p4_identity` passes `params` straight through, so `ExposureParams(inner_params=None)`
   is fine for `ParkingFake`, which ignores its params.
4. The smoke fixture's window is 473 sessions from 2013-12-02, so only the `whole window` and
   `2009-2015` eras land in it; the other three era cells are the dash. That is correct behaviour
   (`wf.measure` returns None below two months) and the tests assert the era **labels**, never
   their values.

---

## Verification

**Build:**
```bash
/home/miftah/seer/engine/.venv/bin/ruff check /home/miftah/.worktrees/seer/lab-exposure-diagnostic/engine
```
(CI lint is bugs only: E9 and F, minus F401.)

**Tests** — Postgres first, because CI fails if the DB tests skip:
```bash
docker start seer-pg
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
cd /home/miftah/.worktrees/seer/lab-exposure-diagnostic
PYTHONPATH=/home/miftah/.worktrees/seer/lab-exposure-diagnostic/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests -n auto
```
Without `PYTHONPATH` pytest silently tests the main checkout, not this branch. Never pass
`-o addopts`.

Then the new file alone, serially, while iterating:
```bash
PYTHONPATH=/home/miftah/.worktrees/seer/lab-exposure-diagnostic/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests/test_lab_exposure.py -n0 -q
```

**Manual check** — the help renders and one real method runs end to end against the main
checkout's store, writing nothing:
```bash
cd /home/miftah/.worktrees/seer/lab-exposure-diagnostic
PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab exposure --help
PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine -v lab exposure M0030 \
  --store /home/miftah/seer/engine/.research --no-journal
```
Look for: four columns per variant (`recorded`, `picks`, `picks, full`, `parked`); the
`parks money in: SPY` line; the per-era block with all five rows; and the closing line showing N
and the looks identical before and after.

**A `lab` subcommand migrates `lab/lab.sqlite` on connect, so even this read dirties it.** Restore
it before committing, and commit by explicit pathspec:
```bash
cd /home/miftah/.worktrees/seer/lab-exposure-diagnostic
git checkout -- lab/lab.sqlite
git status --porcelain   # must show only the three files of this phase
git add -- engine/src/seer_engine/lab/exposure.py \
            engine/src/seer_engine/commands/lab.py \
            engine/tests/test_lab_exposure.py
```

**Exit criteria:**
- This phase's own commit holds exactly three files, and nothing outside `engine/` differs from
  `origin/main`:
  ```bash
  git show --stat HEAD        # exactly engine/src/seer_engine/lab/exposure.py (new),
                              # engine/src/seer_engine/commands/lab.py (four additive hunks),
                              # engine/tests/test_lab_exposure.py (new)
  git diff --name-only origin/main -- engine/ lab/ web/ db/ docs/backtests/ .workflows/todos.md
                              # exactly those same three engine paths
  ```
  The branch may also carry the planning artifacts committed before this phase ran —
  `docs/plans/LAB_EXPOSURE_DIAGNOSTIC_PLAN.md`, `.workflows/plan/lab-exposure-diagnostic/*.md`,
  `docs/analyzer/*.md` — so a bare `git diff --stat origin/main` is **not** the check; the
  pathspec'd form above is. `lab/lab.sqlite` is clean (restore it after the smoke run: a `lab`
  subcommand migrates it on connect).
- `ruff check engine` is clean and `pytest engine/tests` is green with Postgres up and no DB test
  skipping.
- `lab exposure --help` renders and `lab exposure M0030 --store /home/miftah/seer/engine/.research
  --no-journal` prints four columns for every recorded variant plus the per-era grid, and its
  closing line shows N and the test-window looks unchanged.
- A direct `sqlite3` count of `trials`, `trial_moments`, `trial_funding`, `trial_provenance` and
  `insights` is unchanged across that run.

## Handoffs

- **Running it over the five and journalling the answer (R2) is Phase 2.** This phase writes no
  journal row of its own, creates no `docs/backtests/` write-up and does not touch
  `.workflows/todos.md`. The CLI surface Phase 2 types is frozen in the Interface Contract above.
- **The whole-book reproduction gap is information, not a bug to fix here.** `M0030-C50T` re-runs
  to `9.583603` against a recorded `9.583723` because the store's fingerprint moved on 2026-10-12.
  The report prints it and says to compare the columns with each other. If Phase 2 wants that
  chased, it is a separate investigation, not an amendment to this module.
- **Backfilling all 130 methods** is one command away (`lab exposure` takes ids) and is not in
  this set at all — decision D4.
- **A per-session record of what the book actually held**, which would give an exact
  picks/parked/cash split rather than the `-PICKS` arm's `RunStats.exposure`, was ruled out by
  decision D10: it would change `backtest/book_runner.py` and could move recorded results. If a
  later session wants it, it is a change to `BookSnapshot` and belongs in its own plan set.
- **The idle-instrument path is written but unexercised.** No lab method sets
  `rules.idle_symbol` (checked 2026-10-12 across `lab/methods/`), so `arm_rules` returns its
  argument unchanged for every method today. The first method that does set one should have its
  `-PICKS` column read with the report's idle-instrument sentence in hand.
- **`-PARK` for a method that parks only in the idle instrument** cannot be built by re-weighting
  (the idle symbol is never a target). The report says so in a sentence; building it would need an
  arm whose rules keep the idle symbol and whose allocator returns nothing, which is a different
  shape and is not in this phase.

## Rollback

```bash
cd /home/miftah/.worktrees/seer/lab-exposure-diagnostic
git revert <this phase's commit>
```

Or by hand: delete `engine/src/seer_engine/lab/exposure.py` and
`engine/tests/test_lab_exposure.py`, then undo the four additive hunks in
`engine/src/seer_engine/commands/lab.py` (docstring block, `exposure` subparser, `_exposure`
handler, `_HANDLERS` entry). Nothing else in the engine imports the new module — `commands/lab.py`
imports it inside `_exposure` only — so removal is total and no recorded result, no method file and
no row in `lab/lab.sqlite` is affected either way.
