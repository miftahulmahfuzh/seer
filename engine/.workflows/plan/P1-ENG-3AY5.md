> Adopted from `/home/miftah/seer/.workflows/orchestration/sera-signal-panel/PLAN.md` phase 4. Source: `.workflows/plan/sera-signal-panel/phase-4.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 4: Replay the recorded stock-signal methods

**Plan set:** `SERA_SIGNAL_PANEL_PLAN.md`
**Analysis:** `.workflows/analyze/20261113-200537-K7P2_code_analyzer.md`
**Satisfies:** R3 — the already-run stock-signal methods are replayed through the panel in one pass, giving a ranked map of the explored space, without touching a digest or a frozen record
**Criteria:** R3.1
**Depends on:** Phase 3 (and through it Phases 1 and 2)
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab`, `engine/src/seer_engine/commands`

---

## Goal

After this phase `lab panel-replay` takes every recorded dev arm of every method whose
`methods.family` begins `stock-` and records it as a pick-set panel. It calls the arm's own
allocator at each panel decision date with nothing held, drops the arm's fixed instruments and
names outside the pool, and hands the rest to `panel.measure(mode="picks")` on the dev store and
then the survivorship-check store. Each arm goes into `panel_signals` (kind `replay`, id = the
candidate id, `method_id` set) and `panel_results` in one transaction, through phase 3's
`panel_run.record`. The sweep resumes after a stop (a whole run with no `--limit`, repeated until it records 0; `--limit` is for a first timing batch only, since it counts previously skipped arms), survives any one
allocator failing, and reports every arm it could not replay with the reason. No `trials` row,
config digest, `methods.source_sha` or method file changes.

Facts measured this session (planner, 2026-11-13, read-only on a copy of `/home/miftah/seer/lab/lab.sqlite`,
which matches the worktree's `lab/lab.sqlite`: 2,271 trials in both):

- 1,720 dev trials belong to 321 methods whose family is like `stock-%`. `UNIQUE(candidate_id, window)`
  means one trial per arm. None uses bracket rules: 1,409 are `monthly-hold-frac-gotrade`, and the
  rest are other book rule sets. 41 are `BLEND`, and 317 distinct allocator ids appear.
- Allocator cost, planner-measured on 20 random arms of the dev store (`prepare_for` plus
  `targets_prepared` at 237 month ends, `panel.measure` excluded, since phase 1 had not landed):
  load_store 11.6 s, `prepare_for` 0.0-0.2 s, the month loop 0.0-4.1 s per arm (about 1.4 s
  mean), max RSS 1.3 GB with one process. Two of the 20 (`M0052-Q100`, `M0164-C70-YB-SW`) never
  picked 5 pool names in a month. These figures set the `--jobs` default (1, cap 2). They are not
  for the runbook: the runbook takes only the timings this phase's Proof journeys measure.

## Interface Contract

**Deletes:** none
**Renames:** none
**Creates:**
- `engine/src/seer_engine/lab/panel_replay.py` (new): constants `COMMAND`, `FAMILY_LIKE`, the skip
  categories `NO_IMPORT`, `NOT_IN_FILE`, `DRIFTED`, `BRACKET`, `NO_MEMBERS`, `NO_DATA`, `RAISED`,
  `TOO_FEW`; type alias `MethodLoader`; dataclasses `Recorded`, `Work`, `Skip`,
  `Outcome`, `StorePass`, `Report`; class `PickScorer`; functions `select`, `unfinished`,
  `module_loader`, `resolve`, `prereg_text`, `data_gap`, `groups_of`, `run_group`, `outcomes`,
  `subject_of`, `run`, `format_report`.
- `engine/src/seer_engine/commands/lab.py`: subparser `panel-replay`, handler `_panel_replay`, one
  `_HANDLERS` entry, one docstring entry, and `lab panel-replay` added to the `SEER_SV_STORE` sentence.
- `engine/tests/test_lab_panel_replay.py` (new).
- `docs/runbooks/signal-panel.md` (new): the operator half (replay and sweep, with measured timings).
- A `## Replay: lab panel-replay` section appended to `.claude/skills/verify-seer/features/signal-panel.md`.
**Signature changes:** none
**Requires (from earlier phases):**
- Phase 1 `lab/panel.py`: `RULE_ID`, `ERAS` (`ERAS[0] == "all"`), `MIN_PICKS`, `build_frame(data)`,
  `measure(frame, scorer, *, mode="picks")`. In picks mode `measure` calls `scorer(market, pool, d)`,
  where `d` is the decision date (the last NYSE session of the month) and `pool` is an
  `AbstractSet[str]` of the members that pass `tree_rank.SCREEN` on `d`. It treats the returned
  keys as the pick set, skips a month with fewer than `MIN_PICKS` picks, and returns a
  `PanelReading` whose `stats` may be empty when no month qualifies. It does not raise in that case.
  `PanelReading` and `EraStats` are frozen dataclasses that pickle, because they come back from a
  forked worker.
- Phase 2 `lab/store.py`: `PanelSignalRow` constructible by keyword with the `panel_signals` column
  names; `has_panel(conn, signal_id, rule_id, store_fingerprint) -> bool`; `panel_signals(conn)`
  and `panel_results(conn, signal_id=None)` rows readable by column name. `insert_panel_signal`
  returns False, and does not raise, when the id already exists **from the same `source_sha`**
  (it raises `LabError` for a different sha). A replay recorded on an old dev store keeps its
  `panel_signals` row when it is re-measured on a new one. `insert_panel_results` skips a repeated
  primary key and returns the number inserted, so a re-measure with the survivorship store
  unchanged records the new dev rows and skips the old survivorship rows. `insert_panel_*` do not
  commit.
- Phase 3 `lab/panel_run.py`: `DEV`, `SURVIVORSHIP`, `Subject(row, scorer, mode)`,
  `StoreRun(role, fingerprint, readings)`, `check_stores(dev_dir, sv_dir, *, command) -> StorePair`
  (with `dev_dir`, `sv_dir`, `dev_fingerprint`), `open_store(conn, pair, role, *, command) -> ResearchData`
  (load, D10 pin and fingerprint check for dev), `has_whole_window(reading)`, `record(conn, subject, dev_run, sv_run, *, git_sha, measured) -> bool`,
  `Counts.read(conn)`, `footer(conn, before, *, lead)`. Also the `panel` / `panel-map` /
  `next-signal-id` parsers, handlers and `_HANDLERS` entries in `commands/lab.py`, and
  `.claude/skills/verify-seer/features/signal-panel.md`.
**Leaves alone (owned by others):** every file under `engine/src/seer_engine/lab/methods/` (no
phase touches them); `lab/panel.py`, `lab/signal.py`, `lab/signals/*` (Phase 1); `lab/store.py`,
`lab/panel_verdict.py`, the snapshot (Phase 2); `lab/panel_run.py` and the three phase-3
subcommands, which this phase only calls and sits beside (Phase 3); `lab/method.py`,
`lab/runner.py`, `lab/hardgate.py`, `features/lab-cli.md` (Phase 5); `web/**` (Phase 6); the
skills, `CLAUDE.md`, `README.md`, and the Sera-facing half of `docs/runbooks/signal-panel.md` (Phase 7).

**Deliberate deviation from phase 3's handoff.** Phase 3's handoff suggests replaying through
`panel_run.measure_stores`. This phase does not call it, for three reasons in its code:
`scorers = [s.scorer(data) for s in subjects]` would run `prepare_for` for about 1,700 arms before
measuring any of them and hold every prepared value at once; one raising allocator would abort the
whole store pass; and nothing could be written until both full passes ended. `panel_replay` keeps
phase 3's shape (dev store first, then survivorship, never both in memory, one transaction per
subject through `panel_run.record`), but it measures in groups that share one allocator object and
catches each arm's exceptions. It loads each store through phase 3's `panel_run.open_store`
(reconciled: the load, D10 pin and fingerprint check exist once, in phase 3's module).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/panel_replay.py` | create | select, resolve, grouped fork-pool measurement, per-arm record, report |
| `engine/src/seer_engine/commands/lab.py` | modify | docstring entry (after phase 3's `lab next-signal-id` entry, which phase 3 inserts after today's `:186`); `SEER_SV_STORE` sentence (today `:207-210`, as phase 3 leaves it); parser (after phase 3's `next-signal-id` parser, which phase 3 inserts before today's `:1062` `s = sub.add_parser("idea", ...)`); handler (after phase 3's `_next_signal_id`, before `_HANDLERS = {`, today `:4780`); `_HANDLERS` entry (after phase 3's `"next-signal-id": _next_signal_id,`, which follows today's `:4814` `"next-id": _next_id,`) |
| `engine/tests/test_lab_panel_replay.py` | create | behaviour on a scratch lab DB, real allocators, phase 1's real evaluator |
| `docs/runbooks/signal-panel.md` | create | how to run a replay and a signal sweep, with timings measured in J2, J3, J4 and the neighbor check |
| `.claude/skills/verify-seer/features/signal-panel.md` | modify (append) | a `## Replay: lab panel-replay` section at the end of phase 3's file |

## Implementation Steps

### Step 1: `lab/panel_replay.py`
**File:** `engine/src/seer_engine/lab/panel_replay.py` (new)
**Change:** The whole replay. The selection is pure SQL over `trials` joined to `methods`. A
tolerant per-module loader stands in for `method.discover()`, which raises on the first file that
fails to import. A candidate is used only when its `config_digest` equals the recorded one. A
`PickScorer` wraps the arm's own allocator. Arms are grouped by allocator object and each group is
prepared once per store. A fork pool follows the `yardstick._outcomes` pattern
(`yardstick.py:637-649`), but uses `imap_unordered` so results are written as groups finish. The
dev store is measured first and its readings kept; each arm is written as soon as its
survivorship reading arrives.
**Code:**
```python
"""Replay the recorded stock-signal methods through the signal panel (``lab panel-replay``).

The lab has judged about seventeen hundred stock-picking arms, each only as a whole book through
the full simulator, where the SPY switch, the weighting and Gotrade's fees sit on top of whatever
the picking did. The panel (``lab.panel``) asks the question underneath: did the names a ranking
chose beat the rest of the pool the next month, after momentum, beta, size and volatility? This
module puts every recorded dev arm of every ``stock-*`` method through that question once, so the
explored space becomes one ranked map (``lab panel-map --kind replay``) instead of seventeen
hundred separate book verdicts.

**No score is extracted, and nothing recorded is touched.** There is no shared score seam: most
method files define their own ``targets`` and return names already cut to the book's width. So the
replay does not reach inside an allocator. It calls the arm's own allocator the way
``book_runner.run_book`` does -- ``prepare_for`` once per store, then ``targets_prepared`` at each
decision date with that date's index members -- and treats the names returned as a pick set
(``panel.measure(..., mode="picks")``, every pick weighted 1.0). The ``Candidate`` used is the very
object the committed method file builds, and its ``config_digest`` must equal the digest its trial
recorded before it is used; one that drifted is skipped and reported. This module never writes
``trials`` or ``methods`` and never opens a method file for writing.

**What the replay deliberately leaves out.**

* *Holdings.* Every call passes ``held=frozenset()``. An allocator whose picks depend on what the
  book holds (a keep band, ``m0509.choose``) is therefore read from an empty book every month, an
  approximation. One probe per arm, on its first month with enough picks, hands it a holding and
  checks whether its picks move. The report prints how many did. They are not special-cased.
* *Timing.* A month in which the arm's switch is off returns no names, or only its fixed instruments
  (``allocator.holds``), which are dropped here along with every name outside the panel's pool. So
  that month has fewer than ``panel.MIN_PICKS`` picks and the panel skips it. The panel measures
  the picking, not the switch (index Decisions).
* *Roles.* Control arms, hash-draw placebos, blends and adapter arms are replayed like any other.
  ``trial_roles`` is sparse, and two arms that pick the same names are collapsed later, as twins,
  by ``panel_verdict`` through ``picks_hash``.

**Two stores, one at a time, one transaction per arm.** This follows ``panel_run.measure_stores``'
order: the dev store is loaded and pinned to the benchmark's prices (D10), every arm is measured,
and the small readings are kept while the store and its frame are dropped. Then the
survivorship-check store is loaded, and each arm is written through ``panel_run.record`` as soon as
its second reading arrives: both stores in one transaction, or nothing. An arm the survivorship
store cannot feed (it lacks the dividends, series, shares or fundamentals the allocator declares it
reads) is therefore recorded on neither store. ``measure_stores`` itself is not used. It builds
every subject's scorer before measuring the first, which for a replay means preparing every
allocator at once. One raising allocator would abort its pass, and nothing would be written until
both passes ended.

**Allocators are prepared once per store, not once per arm.** Arms are grouped by allocator object,
and each group is one unit of work: ``prepare_for`` once, then every arm of the group. With
``jobs > 1`` the groups go to forked workers, which inherit the loaded store copy-on-write. Measured
timings are in ``docs/runbooks/signal-panel.md``.

**Resumable, and never aborted by one arm.** An arm already recorded on the current dev store is
not measured again (``store.has_panel``, the rule ``panel_run.split_recorded`` applies to
signals; ``record`` writes both stores together, so a dev row means the arm is done). A re-run
therefore picks up where a stopped one ended. ``--limit`` takes the first N unfinished arms,
previously skipped ones included, so it times a first batch; a full sweep runs without it. An arm
that cannot be replayed is reported with the reason, and the sweep goes on. The reasons are: its
file no longer imports, it vanished from its file, its configuration drifted, it is a bracket
strategy, it picks no index members, a store lacks its data, its allocator raises, or it never
picks enough names. Such an arm is attempted again on the next run, since a fixed file or store
may now feed it.
"""

from __future__ import annotations

import gc
import importlib
import logging
import multiprocessing
import pkgutil
import sqlite3
import time
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import Market
from seer_engine.lab import panel, panel_run, store
from seer_engine.lab.method import (
    METHOD_ID,
    MODULE_NAME,
    Method,
    config_digest,
    methods_package,
    source_sha,
)
from seer_engine.lab.runner import market_fields
from seer_engine.strategies.allocator import Allocator, prepare_for

log = logging.getLogger(__name__)

COMMAND = "lab panel-replay"

FAMILY_LIKE = "stock-%"
"""The methods replayed by default: every family named for what it picks among stocks (SQL LIKE)."""

# Why an arm was not recorded. Fixed phrases, so the report can count them.
NO_IMPORT = "method file does not import"
NOT_IN_FILE = "arm is no longer in its method file"
DRIFTED = "arm's configuration differs from the recorded one"
BRACKET = "bracket strategy, not an allocator"
NO_MEMBERS = "does not pick index members"
NO_DATA = "a store lacks data the allocator reads"
RAISED = "allocator raised"
TOO_FEW = f"never picked {panel.MIN_PICKS} pool names in a month"
# No "the database refused the record" category: phase 2's ``insert_panel_results`` skips a
# repeated key and ``insert_panel_signal`` returns False for the same id and sha, so a re-measure
# never collides (reconciled, Decisions). Any other refusal is a ``LabError`` and stops the run.

MethodLoader = Callable[[str], tuple[Method, Path]]
"""Method id -> (its committed ``METHOD``, its file). Raises when the file cannot be loaded."""

_PRESENT: dict[str, Callable[[Market], bool]] = {
    "fundamentals": lambda m: len(m.fundamentals) > 0,
    "dividends": lambda m: len(m.dividends) > 0,
    "announcements": lambda m: m.dividends.declared_count() > 0,
    "series": lambda m: len(m.series) > 0,
    "shares": lambda m: len(m.shares) > 0,
}
"""Whether a loaded market carries each ``market_fields`` entry, the presence half of
``runner.preflight_data``. ``preflight_data`` itself is not called: it judges a whole method for a
book run, so it also refuses on a candidate's cash yield and on the fundamentals coverage floor.
Neither of those bears on which names an allocator picks."""


# --------------------------------------------------------------------------- values


@dataclass(frozen=True)
class Recorded:
    """One recorded dev trial of a selected method: what the record says the arm was."""

    trial_n: int
    method_id: str
    family: str
    candidate_id: str
    config_digest: str


@dataclass(frozen=True)
class Work:
    """A recorded arm resolved to the ``Candidate`` its committed file builds today."""

    trial_n: int
    family: str  # methods.family, the column the selection matched
    method: Method
    sha: str  # the method file's sha256, recorded as the replay's source_sha
    candidate: Candidate


@dataclass(frozen=True)
class Skip:
    candidate_id: str
    category: str
    detail: str


@dataclass(frozen=True)
class Outcome:
    """One arm on one store: its reading, or why there is none. Crosses a fork, so it pickles."""

    candidate_id: str
    reading: panel.PanelReading | None
    held_sensitive: bool | None
    error: str | None
    seconds: float


@dataclass(frozen=True)
class StorePass:
    role: str
    fingerprint: str
    wall_seconds: float  # load, frame and every arm on this store
    measured: int  # arms handed to their allocator on this store
    arm_seconds: float  # per-arm allocator plus panel time, summed across workers


@dataclass(frozen=True)
class Report:
    selected: int  # recorded dev arms of the selected methods
    already: int  # of those, already recorded on the current dev store before this run
    attempted: int  # arms this run tried (after --limit)
    recorded: tuple[str, ...]
    lost: tuple[str, ...]  # recorded first by a parallel session; theirs kept
    skipped: tuple[Skip, ...]
    held_sensitive: tuple[str, ...]  # recorded arms whose picks move when handed a holding
    passes: tuple[StorePass, ...]


def _why(e: BaseException) -> str:
    """An exception as one short line for the skip table."""
    text = " ".join(f"{type(e).__name__}: {e}".split())
    return text if len(text) <= 240 else text[:237] + "..."


# --------------------------------------------------------------------------- what to replay


def select(
    conn: sqlite3.Connection, *, method_ids: Sequence[str] = (), family_like: str = FAMILY_LIKE
) -> tuple[Recorded, ...]:
    """Every recorded dev trial of a method whose family is LIKE ``family_like``, in trial order.

    ``method_ids`` narrows the selection. A named method with no dev trial in the family is
    refused (``store.LabError``) before anything loads, so a typo is never read as "nothing to do".
    """
    if not isinstance(family_like, str) or not family_like.strip():
        raise store.LabError(f"{COMMAND}: --family-like must be a non-empty SQL LIKE pattern")
    wanted: list[str] = []
    for raw in method_ids:
        mid = str(raw).strip().upper()
        if METHOD_ID.fullmatch(mid) is None:
            raise store.LabError(f"{COMMAND}: {raw!r} is not a lab method id; name methods like M0614")
        if mid not in wanted:
            wanted.append(mid)
    rows = conn.execute(
        "SELECT t.n, t.method_id, m.family, t.candidate_id, t.config_digest FROM trials t "
        "JOIN methods m ON m.id = t.method_id "
        "WHERE t.window = 'dev' AND m.family LIKE ? ORDER BY t.n",
        (family_like,),
    ).fetchall()
    out = [Recorded(int(r[0]), str(r[1]), str(r[2]), str(r[3]), str(r[4])) for r in rows]
    if wanted:
        have = {r.method_id for r in out}
        missing = [m for m in wanted if m not in have]
        if missing:
            raise store.LabError(
                f"{COMMAND}: {', '.join(missing)} has no recorded dev trial in a method whose family "
                f"is like {family_like!r}. The replay reads what the lab recorded; nothing was "
                f"loaded or recorded"
            )
        keep = set(wanted)
        out = [r for r in out if r.method_id in keep]
    return tuple(out)


def unfinished(
    conn: sqlite3.Connection, selected: Sequence[Recorded], dev_fingerprint: str
) -> tuple[list[Recorded], int]:
    """(arms still to replay, how many are already recorded on this dev store).

    ``panel_run.record`` writes both stores in one transaction, so a row on the dev fingerprint
    means the arm is finished. This is the rule ``panel_run.split_recorded`` applies to signals,
    asked here before any method file is imported.
    """
    todo: list[Recorded] = []
    done = 0
    for r in selected:
        if dev_fingerprint and store.has_panel(conn, r.candidate_id, panel.RULE_ID, dev_fingerprint):
            done += 1
        else:
            todo.append(r)
    return todo, done


def module_loader() -> MethodLoader:
    """A loader over ``seer_engine.lab.methods`` that imports one method file at a time.

    ``method.discover()`` imports every file and raises on the first failure, so one method file
    that no longer imports would stop the whole sweep. This makes the same checks per file
    (``MODULE_NAME``, ``METHOD`` is a ``Method``, its id matches the file number) and raises only
    for the file asked for, which ``resolve`` turns into a skip.
    """
    pkg = methods_package()
    names: dict[str, list[str]] = {}
    for info in pkgutil.iter_modules(pkg.__path__):
        m = MODULE_NAME.fullmatch(info.name)
        if m is not None:
            names.setdefault(f"M{m.group(1)}", []).append(f"{pkg.__name__}.{info.name}")

    def load(method_id: str) -> tuple[Method, Path]:
        found = names.get(method_id, [])
        if len(found) != 1:
            raise LookupError(f"{len(found)} method files claim {method_id}")
        module = importlib.import_module(found[0])
        method = getattr(module, "METHOD", None)
        if not isinstance(method, Method):
            raise TypeError(f"{found[0]} has no METHOD = Method(...)")
        if method.id != method_id:
            raise ValueError(f"{found[0]}: file number {method_id} != METHOD.id {method.id}")
        return method, Path(str(module.__file__)).resolve()

    return load


def resolve(selected: Sequence[Recorded], load: MethodLoader) -> tuple[list[Work], list[Skip]]:
    """Each recorded arm as the ``Candidate`` its committed file builds, or the reason it cannot be."""
    works: list[Work] = []
    skips: list[Skip] = []
    files: dict[str, tuple[Method, str] | str] = {}
    for r in selected:
        if r.method_id not in files:
            try:
                method, path = load(r.method_id)
                files[r.method_id] = (method, source_sha(path))
            except Exception as e:  # a file that no longer imports must not stop the sweep
                files[r.method_id] = _why(e)
        got = files[r.method_id]
        if isinstance(got, str):
            skips.append(Skip(r.candidate_id, NO_IMPORT, got))
            continue
        method, sha = got
        candidate = next((c for c in method.all_candidates() if c.id == r.candidate_id), None)
        if candidate is None:
            skips.append(Skip(r.candidate_id, NOT_IN_FILE, f"{method.id}'s file no longer declares it"))
            continue
        digest = config_digest(candidate)
        if digest != r.config_digest:
            skips.append(Skip(
                r.candidate_id, DRIFTED,
                f"digest {digest[:12]} on disk, {r.config_digest[:12]} recorded",
            ))
            continue
        if not isinstance(candidate.allocator, Allocator):
            skips.append(Skip(r.candidate_id, BRACKET, type(candidate.allocator).__name__))
            continue
        try:
            picks_members = bool(candidate.allocator.uses_members(candidate.params))
        except Exception as e:  # a broken params object is this arm's problem, not the sweep's
            skips.append(Skip(r.candidate_id, RAISED, _why(e)))
            continue
        if not picks_members:
            skips.append(Skip(
                r.candidate_id, NO_MEMBERS, f"{candidate.allocator.id} reads fixed instruments only",
            ))
            continue
        works.append(Work(r.trial_n, r.family, method, sha, candidate))
    return works, skips


def prereg_text(method: Method, candidate_id: str) -> tuple[str, str]:
    """(hypothesis, expected failure) pre-registered with the batch that declared this arm."""
    for a in method.amendments:
        if any(c.id == candidate_id for c in a.candidates):
            return a.hypothesis, a.expected_failure
    return method.hypothesis, method.expected_failure


def data_gap(candidate: Candidate, market: Market) -> str | None:
    """Why ``market`` cannot feed this arm's allocator, or None when it can."""
    for name in market_fields(candidate.allocator):
        present = _PRESENT.get(name)
        if present is None:
            return f"cannot be checked for Market.{name}, which the allocator declares it reads"
        if not present(market):
            return f"carries no {name} (the allocator reads Market.{name})"
    return None


# --------------------------------------------------------------------------- the scorer


class PickScorer:
    """One arm's own allocator as a ``panel.Scorer`` in ``picks`` mode.

    Called as ``scorer(market, pool, d)`` at each panel decision date ``d``. It asks the allocator
    for its targets with the index members of ``d`` and nothing held, drops the arm's fixed
    instruments (``holds``) and every name outside ``pool``, and returns each remaining name at
    1.0. ``held_sensitive`` is None until the first month with ``panel.MIN_PICKS`` picks. From then
    on it records whether handing the allocator a holding changed its picks that month.
    """

    def __init__(self, allocator: Allocator, prepared: Any, params: Any) -> None:
        self.allocator = allocator
        self.prepared = prepared
        self.params = params
        self.fixed = frozenset(allocator.holds(params))
        self.held_sensitive: bool | None = None

    def picks(
        self, market: Market, pool: AbstractSet[str], d: date, held: frozenset[str] = frozenset()
    ) -> tuple[str, ...]:
        members = market.membership.members_on(d)
        targets = self.allocator.targets_prepared(self.prepared, members, d, held, self.params)
        return tuple(t.symbol for t in targets if t.symbol not in self.fixed and t.symbol in pool)

    def __call__(self, market: Market, pool: AbstractSet[str], d: date) -> dict[str, float]:
        chosen = self.picks(market, pool, d)
        if self.held_sensitive is None and len(chosen) >= panel.MIN_PICKS:
            self.held_sensitive = self._moves_with_holdings(market, pool, d, chosen)
        return {s: 1.0 for s in chosen}

    def _moves_with_holdings(
        self, market: Market, pool: AbstractSet[str], d: date, chosen: tuple[str, ...]
    ) -> bool:
        others = sorted(set(pool) - set(chosen))[: panel.MIN_PICKS]
        if not others:
            return False
        try:
            again = self.picks(market, pool, d, frozenset(others))
        except Exception:  # an allocator that cannot take a holding is not blind to holdings
            return True
        return set(again) != set(chosen)


# --------------------------------------------------------------------------- measuring


@dataclass(frozen=True)
class _Group:
    allocator: Allocator
    works: tuple[Work, ...]


def groups_of(works: Sequence[Work]) -> tuple[_Group, ...]:
    """Arms sharing one allocator object, each group in the order its object first appears."""
    order: dict[int, tuple[Allocator, list[Work]]] = {}
    for w in works:
        key = id(w.candidate.allocator)
        if key not in order:
            order[key] = (w.candidate.allocator, [])
        order[key][1].append(w)
    return tuple(_Group(alloc, tuple(ws)) for alloc, ws in order.values())


def run_group(market: Market, frame: Any, group: _Group) -> list[Outcome]:
    """Prepare the group's allocator once on ``market``, then measure each of its arms.

    Every exception is caught and becomes that arm's ``Outcome.error``: one allocator failing must
    not cost the sweep the other arms.
    """
    try:
        prepared = prepare_for(group.allocator, market)
    except Exception as e:  # the whole group shares this prepared value
        why = f"prepare: {_why(e)}"
        return [Outcome(w.candidate.id, None, None, why, 0.0) for w in group.works]
    out: list[Outcome] = []
    for w in group.works:
        t0 = time.perf_counter()
        try:
            scorer = PickScorer(group.allocator, prepared, w.candidate.params)
            reading = panel.measure(frame, scorer, mode="picks")
        except Exception as e:  # this arm only
            out.append(Outcome(w.candidate.id, None, None, _why(e), time.perf_counter() - t0))
            continue
        out.append(Outcome(w.candidate.id, reading, scorer.held_sensitive, None, time.perf_counter() - t0))
    return out


_CHILD_WORK: tuple[Market, Any, tuple[_Group, ...]] | None = None  # set only inside a forked worker


def _adopt(work: tuple[Market, Any, tuple[_Group, ...]]) -> None:
    global _CHILD_WORK
    _CHILD_WORK = work


def _group_in_child(i: int) -> list[Outcome]:
    if _CHILD_WORK is None:
        raise RuntimeError("a replay worker ran before it was handed its work")
    market, frame, groups = _CHILD_WORK
    return run_group(market, frame, groups[i])


def outcomes(market: Market, frame: Any, groups: Sequence[_Group], jobs: int) -> Iterator[list[Outcome]]:
    """Each group's outcomes as the group finishes.

    ``jobs > 1`` forks workers after the store and its frame are in memory. The pages are shared
    copy-on-write, and the work rides the pool initializer, which a fork does not pickle, as in
    ``yardstick._outcomes``. Only the small ``Outcome`` lists come back, in completion order. The
    caller keys them by candidate id, so the order never reaches the record.
    """
    if jobs <= 1 or len(groups) <= 1:
        for g in groups:
            yield run_group(market, frame, g)
        return
    ctx = multiprocessing.get_context("fork")
    procs = min(jobs, len(groups))
    with ctx.Pool(processes=procs, initializer=_adopt, initargs=((market, frame, tuple(groups)),)) as pool:
        yield from pool.imap_unordered(_group_in_child, range(len(groups)), chunksize=1)


def _unusable(o: Outcome, role: str) -> Skip | None:
    if o.error is not None:
        return Skip(o.candidate_id, RAISED, f"on the {role} store: {o.error}")
    if o.reading is None or not panel_run.has_whole_window(o.reading):
        # ``panel.measure`` returns empty stats (never raises) when no month has MIN_PICKS picks,
        # and leaves out an era with fewer than MIN_ERA_MONTHS measured months.
        return Skip(
            o.candidate_id, TOO_FEW,
            f"too few months with {panel.MIN_PICKS} or more picks in the pool on the {role} store "
            f"for a whole-window reading",
        )
    return None


def _store_pass(
    conn: sqlite3.Connection,
    pair: panel_run.StorePair,
    role: str,
    works: Sequence[Work],
    jobs: int,
    skips: list[Skip],
    on_reading: Callable[[Work, Outcome, str], None],
) -> StorePass:
    """Load ``role``'s store, measure every arm it can feed, hand each usable reading on, drop it."""
    t0 = time.perf_counter()
    data = panel_run.open_store(conn, pair, role, command=COMMAND)
    fingerprint = str(data.fingerprint)
    fed: list[Work] = []
    for w in works:
        gap = data_gap(w.candidate, data.market)
        if gap is None:
            fed.append(w)
        else:
            skips.append(Skip(w.candidate.id, NO_DATA, f"the {role} store {gap}"))
    measured, arm_seconds = 0, 0.0
    if fed:
        frame = panel.build_frame(data)
        by_id = {w.candidate.id: w for w in fed}
        groups = groups_of(fed)
        for done, batch in enumerate(outcomes(data.market, frame, groups, jobs), start=1):
            for o in batch:
                measured += 1
                arm_seconds += o.seconds
                bad = _unusable(o, role)
                if bad is None:
                    on_reading(by_id[o.candidate_id], o, fingerprint)
                else:
                    skips.append(bad)
            log.info(
                "%s %s store: %d of %d allocator group(s), %d of %d arm(s)",
                COMMAND, role, done, len(groups), measured, len(fed),
            )
        del frame
    del data
    gc.collect()
    return StorePass(
        role=role,
        fingerprint=fingerprint,
        wall_seconds=time.perf_counter() - t0,
        measured=measured,
        arm_seconds=arm_seconds,
    )


# --------------------------------------------------------------------------- recording


def subject_of(work: Work, *, created: str) -> panel_run.Subject:
    """The arm as a phase-3 panel subject: a ``replay`` row under its candidate id."""
    method, c = work.method, work.candidate
    hypothesis, expected_failure = prereg_text(method, c.id)
    row = store.PanelSignalRow(
        id=c.id,
        kind="replay",
        # The method's own name, already owner-facing on /sera/methods (Decisions). The page tells
        # one method's arms apart as "(variant k of n)"; the rationale is not owner text.
        name=method.name,
        family=work.family,
        hypothesis=hypothesis,
        expected_failure=expected_failure,
        source_kind=method.source_kind,
        source_ref=method.source_ref,
        method_id=method.id,
        source_sha=work.sha,
        created=created,
    )
    alloc, params = c.allocator, c.params
    return panel_run.Subject(
        row=row,
        scorer=lambda data: PickScorer(alloc, prepare_for(alloc, data.market), params),
        mode="picks",
    )


def run(
    conn: sqlite3.Connection,
    dev_dir: Path,
    sv_dir: Path,
    *,
    git_sha: str,
    method_ids: Sequence[str] = (),
    family_like: str | None = None,
    limit: int | None = None,
    jobs: int = 1,
    load: MethodLoader | None = None,
    now: Callable[[], str] = store.now_iso,
) -> Report:
    """Replay the selected arms and record each one that both stores could measure.

    Order: the selection (refusals need only the database), both manifests
    (``panel_run.check_stores``), what is already finished on the dev store, ``limit``, the method
    files. Only then is a store loaded, and only when some arm survived all of that. Writes
    ``panel_signals`` and ``panel_results`` through ``panel_run.record`` and nothing else.
    """
    selected = select(conn, method_ids=method_ids,
                      family_like=FAMILY_LIKE if family_like is None else family_like)
    pair = panel_run.check_stores(Path(dev_dir), Path(sv_dir), command=COMMAND)
    todo, already = unfinished(conn, selected, pair.dev_fingerprint)
    if limit is not None:
        todo = todo[:limit]
    works, skips = resolve(todo, module_loader() if load is None else load)
    passes: list[StorePass] = []
    recorded: list[str] = []
    lost: list[str] = []
    held: list[str] = []
    if works:
        first: dict[str, Outcome] = {}

        def keep(w: Work, o: Outcome, _fingerprint: str) -> None:
            first[w.candidate.id] = o

        passes.append(_store_pass(conn, pair, panel_run.DEV, works, jobs, skips, keep))
        dev_fingerprint = passes[0].fingerprint

        def write(w: Work, o: Outcome, sv_fingerprint: str) -> None:
            cid = w.candidate.id
            stamp = now()
            dev_run = panel_run.StoreRun(
                role=panel_run.DEV, fingerprint=dev_fingerprint, readings={cid: first[cid].reading},
            )
            sv_run = panel_run.StoreRun(
                role=panel_run.SURVIVORSHIP, fingerprint=sv_fingerprint, readings={cid: o.reading},
            )
            wrote = panel_run.record(
                conn, subject_of(w, created=stamp), dev_run, sv_run, git_sha=git_sha, measured=stamp,
            )
            if not wrote:
                lost.append(cid)
                return
            recorded.append(cid)
            if first[cid].held_sensitive:
                held.append(cid)

        second = sorted((w for w in works if w.candidate.id in first), key=lambda w: w.trial_n)
        if second:
            passes.append(_store_pass(conn, pair, panel_run.SURVIVORSHIP, second, jobs, skips, write))
    order = {r.candidate_id: r.trial_n for r in selected}

    def by_trial(cid: str) -> int:
        return order.get(cid, 0)

    return Report(
        selected=len(selected),
        already=already,
        attempted=len(todo),
        recorded=tuple(sorted(recorded, key=by_trial)),
        lost=tuple(sorted(lost, key=by_trial)),
        skipped=tuple(sorted(skips, key=lambda s: by_trial(s.candidate_id))),
        held_sensitive=tuple(sorted(held, key=by_trial)),
        passes=tuple(passes),
    )


# --------------------------------------------------------------------------- printing


def format_report(rep: Report) -> str:
    """What the run did, the per-store timings, the held-aware count and every skipped arm."""
    lines = [
        f"panel replay ({panel.RULE_ID}): {rep.selected} recorded dev arm(s) selected, "
        f"{rep.already} already recorded on this dev store, {rep.attempted} attempted this run",
    ]
    if rep.attempted == 0:
        lines.append("nothing to replay: no store was loaded")
    for p in rep.passes:
        per = p.arm_seconds / p.measured if p.measured else 0.0
        lines.append(
            f"  {p.role} store {p.fingerprint[:12]}: {p.measured} arm(s) measured in "
            f"{p.wall_seconds:.1f}s wall (load and frame included), {per:.2f}s of allocator and "
            f"panel time per arm"
        )
    lines.append(f"recorded {len(rep.recorded)} replay panel(s), one transaction each")
    if rep.lost:
        lines.append(f"{len(rep.lost)} arm(s) recorded first by a parallel session; theirs kept")
    if rep.recorded:
        lines.append(
            f"held-aware: {len(rep.held_sensitive)} of the {len(rep.recorded)} recorded arm(s) "
            f"change their picks when handed a holding; their panel is read from an empty book, "
            f"an approximation"
        )
    if rep.skipped:
        lines.append(f"skipped {len(rep.skipped)} arm(s), attempted again on the next run:")
        for reason, n in Counter(s.category for s in rep.skipped).most_common():
            lines.append(f"  {n:>5}  {reason}")
        width = max(len(s.candidate_id) for s in rep.skipped)
        for s in rep.skipped:
            lines.append(f"  {s.candidate_id:<{width}}  {s.category}: {s.detail}")
    return "\n".join(lines)
```
**Impact:** A new module. Nothing imports it until Step 2. It imports `lab.runner` only for
`market_fields`, as `survivorship_check` already does, so it adds no import cycle.
**Check:** `cd /home/miftah/.worktrees/seer/sera-signal-panel && PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -c "import seer_engine.lab.panel_replay as r; print(r.TOO_FEW)"` prints `never picked 5 pool names in a month`; `/home/miftah/seer/engine/.venv/bin/ruff check engine` is clean.

### Step 2: the `panel-replay` subcommand in `commands/lab.py`
**File:** `engine/src/seer_engine/commands/lab.py` (four insertion points, quoted as the file reads
after phase 3)

**2a. Module docstring entry.** Insert directly after phase 3's entry
`    lab next-signal-id              the next free signal id: one past both the record and the`
`                                    committed signal files` (phase 3 puts its three entries after
today's `:186`):
```text
    lab panel-replay [M0614 ...] [--family-like PATTERN] [--limit N] [--store DIR]
                     [--sv-store DIR] [--jobs 1|2]
                                    stage one's first job: every recorded dev arm of each method
                                    whose family is like PATTERN (default stock-%) as a pick-set
                                    panel. The arm's own allocator is called at each month end
                                    with nothing held, and the names it returns are measured on
                                    the dev store, then the survivorship-check store, and recorded
                                    in one transaction per arm (panel_signals kind replay, id =
                                    the candidate id). An arm already recorded on the dev store is
                                    not measured again; an arm that cannot be replayed is reported
                                    with the reason and the sweep goes on. Never a trial: N, the
                                    luck gate's N and the looks do not move
```
**2b. The `SEER_SV_STORE` sentence.** Phase 3 rewrites today's `:207-210` to end "...sets the
--sv-store of lab survivorship and lab panel. A worktree has none of the three stores of its own,
so a child exports all three to the main checkout's." Replace that paragraph with:
```text
Parallel sessions (sera-the-explorer) share one database: SEER_LAB_DB sets --db,
SEER_RESEARCH_STORE sets --store, and SEER_SV_STORE sets the --sv-store of lab survivorship,
lab panel and lab panel-replay. A worktree has none of the three stores of its own, so a child
exports all three to the main checkout's.
```
**2c. Parser.** Insert directly after phase 3's
`    sub.add_parser("next-signal-id", help="the next free signal id: one past the record and the committed signal files")`
(which phase 3 places before today's `:1062` `s = sub.add_parser("idea", ...)`):
```python
    s = sub.add_parser(
        "panel-replay",
        # `help=` strings are %-interpolated by argparse: the one `%` below is written `%%`.
        help="record a pick-set panel for every recorded dev arm of the stock-picking methods",
        description=(
            "Replay every recorded dev arm of each method whose family is like --family-like "
            "(default stock-%) through the signal panel. The arm's own allocator is called at "
            "each month end of the dev window with that month's index members and nothing held; "
            "its fixed instruments and any name outside the panel's pool are dropped, and the "
            "rest are its picks. The panel measures them on the dev store and then on the "
            "survivorship-check store (never both in memory), and each arm is recorded in one "
            "transaction once both have measured it: a panel_signals row of kind replay under "
            "the arm's candidate id, and its panel_results rows. An arm already recorded on the "
            "dev store is not measured again, so a stopped run resumes. An arm that cannot be "
            "replayed (its file no longer imports, its configuration drifted from the recorded "
            "digest, a store lacks data it reads, its allocator raises, it never picks enough "
            "names) is reported with the reason and the sweep goes on. No trial, no moment, no "
            "status and no journal entry: the lab's N, the luck gate's N and the test-window "
            "looks do not move."
        ),
    )
    s.add_argument("method", nargs="*", metavar="M0614",
                   help="replay only these methods (default: every method in the family)")
    s.add_argument("--family-like", default=None, metavar="PATTERN",
                   help="SQL LIKE pattern on methods.family (default: stock-%%)")
    s.add_argument("--limit", type=_positive_count, default=None, metavar="N",
                   help="attempt at most N unfinished arms, in trial order, then stop; run again "
                        "for the next batch")
    s.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR),
        help=f"dev-window research store (default: {research.STORE_DIR}, or "
             "$SEER_RESEARCH_STORE); a store declaring another window, or carrying a purpose "
             "marker, is refused from its manifest",
    )
    s.add_argument(
        "--sv-store",
        type=Path,
        default=Path(os.environ.get("SEER_SV_STORE") or research.SV_STORE_DIR),
        help=f"the survivorship-check store (default: {research.SV_STORE_DIR}, or "
             "$SEER_SV_STORE); required, and refused unless its manifest says purpose "
             "survivorship-check. From a worktree, export SEER_SV_STORE to the main checkout's "
             "engine/.research-sv",
    )
    s.add_argument("--jobs", type=int, choices=(1, 2), default=1, metavar="J",
                   help="worker processes forked after each store loads, one allocator group at a "
                        "time (1 or 2, default 1). Each worker prepares its own allocators, so two "
                        "is the ceiling on this machine; the records are identical for either")
```
**2d. Handler.** Insert directly after phase 3's `_next_signal_id` (which ends with `return 0`) and
before `_HANDLERS = {`:
```python
def _panel_replay(conn, args) -> int:
    """``lab panel-replay [M0614 ...]``: every recorded stock-signal arm as a pick-set panel.

    ``lab.panel_replay`` holds the replay. This handler only wires the flags, prints the report,
    and prints N, the luck gate's N and the looks before and after (``panel_run.footer``), so the
    invariant shows on every run. It writes ``panel_signals`` (kind ``replay``) and
    ``panel_results`` rows and nothing else. It exits 1 when the run attempted arms and the
    selection still holds no replay panel at all, so nothing could be replayed. A re-run whose
    remaining arms are all unreplayable exits 0, because the sweep itself is complete.
    """
    from seer_engine.lab import panel_replay, panel_run, runner

    if research.DEV_END != dev.DEV_END:
        raise store.LabError("research.DEV_END differs from dev.DEV_END; refusing to run")
    before = panel_run.Counts.read(conn)
    t0 = time.perf_counter()
    rep = panel_replay.run(
        conn,
        Path(args.store),
        Path(args.sv_store),
        git_sha=runner.git_head(config.REPO_ROOT),
        method_ids=args.method,
        family_like=args.family_like,
        limit=args.limit,
        jobs=args.jobs,
    )
    print(panel_replay.format_report(rep))
    print()
    stage = (" Read the map with `python -m seer_engine lab panel-map --kind replay`; solo, "
             "`python -m seer_engine lab stage` so seertrade.site/sera shows it."
             if rep.recorded else "")
    print(panel_run.footer(conn, before, lead="No trial was recorded.") + stage)
    log.info("lab panel-replay: %d recorded, %d skipped (%.1fs)",
             len(rep.recorded), len(rep.skipped), time.perf_counter() - t0)
    if rep.attempted and not (rep.recorded or rep.already or rep.lost):
        log.error("lab panel-replay: none of the %d attempted arm(s) could be replayed, and the "
                  "selection holds no replay panel", rep.attempted)
        return 1
    return 0
```
**2e. `_HANDLERS` entry.** After phase 3's `"next-signal-id": _next_signal_id,`:
```python
    "next-signal-id": _next_signal_id,
    "panel-replay": _panel_replay,
```
**Impact:** `lab --help` lists `panel-replay`. `config`, `dev`, `os`, `research`, `store`, `time`,
`Path`, `log` and `_positive_count` are already defined at the top of `commands/lab.py`
(`:214-283`). A `store.LabError` from `select` or `check_stores` becomes exit 2 through `run()`
(`:1140-1148`).
**Check:** `PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab panel-replay --help` exits 0 and shows `(default: stock-%)` for `--family-like`.

### Step 3: the tests
**File:** `engine/tests/test_lab_panel_replay.py` (new)
**Change:** Every test runs the replay against a scratch lab database (`store.connect` on
`tmp_path`, `seed()` so N is non-zero). The arms are real `Candidate`s on real allocators: a toy
whose params pick its behaviour, a market-aware toy that declares `series`, and F4's own `FACTOR`.
They run over a synthetic 40-member market from 2005 to `DEV_END` through phase 1's real
`build_frame`/`measure`; nothing in `panel` or `panel_replay` is stubbed. Stores are tmp
directories holding only `manifest.json`, and `research.load_store` answers from memory, the seam
`test_lab_panel_cli.py` uses. The method files are injected through `run(load=...)` and, for the
CLI, by replacing `panel_replay.module_loader`.
**Code:**
```python
"""``lab panel-replay`` (lab/panel_replay.py): recorded stock-signal arms become pick-set panels.

Driven against a scratch lab database with real allocators -- a toy whose params choose its
behaviour, a market-aware toy that declares Market.series, and F4's ``FACTOR`` -- over a synthetic
40-member market from 2005, through phase 1's real ``panel.build_frame`` and ``panel.measure``.
Stores are manifest-only tmp directories with ``research.load_store`` answered from memory, the
seam ``test_lab_panel_cli.py`` uses. What is asserted is what the lab holds afterwards: which rows,
of which kind, under which ids, the skip report, and the frozen records byte for byte.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from labkit import SMOKE_T13W, smoke_history

from seer_engine import cli, dates, research
from seer_engine.backtest.dev import DEV_END, Candidate
from seer_engine.backtest.market import Market, Membership
from seer_engine.lab import panel, panel_replay, store
from seer_engine.lab.method import Method, config_digest
from seer_engine.lab.seed import seed
from seer_engine.research import ResearchData
from seer_engine.sim.book import equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import target_from_close
from seer_engine.strategies.f_factor import FACTOR, FactorParams

SV = research.SURVIVORSHIP_PURPOSE
# 2005, not 2007: F4's screen (and FACTOR) needs 253 bars, so a 2007 start leaves the pre-2009
# era exactly panel.MIN_ERA_MONTHS (12) months; 2005 gives about 36 (reconciled).
FIRST = date(2005, 1, 3)
STOCKS = tuple(f"S{k:02d}" for k in range(40))
ADDED = date(2026, 11, 13)
STAMP = "2026-11-13T00:00:00+00:00"


@pytest.fixture(autouse=True)
def _clean_gate_cache():
    store._GATE_CACHE.clear()
    yield
    store._GATE_CACHE.clear()


# ---- allocators whose params say what they do -------------------------------------------------


@dataclass(frozen=True)
class Rule:
    kind: str  # top | keep | cash | boom | etf
    n: int = 6
    tag: str = ""  # moves the config digest and nothing else: two rules differing here are one book


class Toy:
    """Ranks the members with a bar on d by that close, highest first; ``Rule.kind`` decides the rest.

    top: the first n. keep: what is held first, then the ranking, n in all (a keep band).
    cash: nothing (a switch that is always off). boom: raises. etf: SPY (a fixed holding) plus the
    first n.
    """

    id = "TOY"

    def lookback(self, params: Any) -> int:
        return 1

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ("SPY",) if params.kind == "etf" else ()

    def holds(self, params: Any) -> tuple[str, ...]:
        return ("SPY",) if params.kind == "etf" else ()

    def uses_members(self, params: Any) -> bool:
        return True

    def prepare(self, history):
        return dict(history)

    def targets(self, history, members, data_date, held, params):
        cut = {s: h.upto(data_date) for s, h in history.items()}
        return self.targets_prepared(cut, members, data_date, held, params)

    def targets_prepared(self, prepared, members, data_date, held, params):
        if params.kind == "boom":
            raise RuntimeError("toy allocator failure")
        if params.kind == "cash":
            return ()

        def close(s):
            h = prepared.get(s)
            i = None if h is None else h.index_of(data_date)
            return None if i is None else float(h.close[i])

        ranked = sorted((s for s in members if close(s) is not None), key=lambda s: (-close(s), s))
        if params.kind == "keep":
            kept = [s for s in sorted(held) if close(s) is not None]
            ranked = kept + [s for s in ranked if s not in kept]
        names = ranked[: params.n]
        if params.kind == "etf":
            names = ["SPY", *names]
        if not names:
            return ()
        w = equal_weight(len(names))
        out = (target_from_close(s, close(s), w) for s in names)
        return tuple(t for t in out if t is not None)


class SeriesToy(Toy):
    """The same ranking, declared as reading Market.series: a store without series cannot feed it."""

    id = "TOYSERIES"
    market_fields = ("series",)

    def prepare_market(self, market):
        return dict(market.history)


TOY = Toy()
SERIES_TOY = SeriesToy()


def _arm(mid: str, suffix: str, allocator, params, rationale: str = "toy arm") -> Candidate:
    return Candidate(id=f"{mid}-{suffix}", family=mid, rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=allocator, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=())


def _method(mid: str, name: str, family: str, *arms: Candidate) -> Method:
    return Method(id=mid, name=name, family=family, source_kind="knowledge", source_ref="",
                  hypothesis=f"{name} hypothesis", expected_failure=f"{name} failure",
                  candidates=tuple(arms))


TOYS = _method(
    "M9001", "Toy picks", "stock-toy",
    _arm("M9001", "TOP", TOY, Rule("top")),
    _arm("M9001", "TOPB", TOY, Rule("top", tag="b")),
    _arm("M9001", "KEEP", TOY, Rule("keep")),
    _arm("M9001", "CASH", TOY, Rule("cash")),
    _arm("M9001", "BOOM", TOY, Rule("boom")),
    _arm("M9001", "ETF", TOY, Rule("etf")),
)
MOMENTUM = _method(
    "M9002", "Momentum", "stock-momentum",
    _arm("M9002", "MOM", FACTOR, FactorParams(rank="momentum", top=10, trend=None),
         "twelve-minus-one momentum, ten names"),
    _arm("M9002", "SER", SERIES_TOY, Rule("top", tag="series")),
)
ROTATION = _method("M9003", "Rotation", "etf-rotation", _arm("M9003", "ROT", TOY, Rule("top", tag="rot")))
DRIFT = _method("M9005", "Drifted", "stock-drift", _arm("M9005", "A", TOY, Rule("top", tag="drift")))

RECORDABLE = ("M9001-TOP", "M9001-TOPB", "M9001-KEEP", "M9001-ETF", "M9002-MOM", "M9002-SER")


# ---- a scratch lab ----------------------------------------------------------------------------


@dataclass
class Lab:
    conn: Any
    path: Path
    files: dict[str, tuple[Method, Path]]

    def load(self, method_id: str) -> tuple[Method, Path]:
        if method_id not in self.files:
            raise ImportError(f"No module named 'seer_engine.lab.methods.{method_id.lower()}_broken'")
        return self.files[method_id]


def _trial(method_id: str, candidate_id: str, digest: str) -> store.TrialRow:
    return store.TrialRow(
        method_id=method_id, candidate_id=candidate_id, config_digest=digest, config_text="t",
        rules_id="r", allocator_id="a", window="dev", start="2008-01-02", end="2015-10-16",
        store_fingerprint="fp", git_sha="abc", run_at=STAMP,
        total_return=1.0, cagr=0.1, max_drawdown=0.3, profit_factor=1.2, trades=200,
        sharpe=0.5, exposure=0.9, turnover=1.0, worst_year=2008, worst_year_return=-0.2,
        spy_tr_return=0.5, spy_tr_cagr=0.07, mar=0.3, failed="", eligible=False,
        dsr=0.5, n_trials_at_run=5, curve_json="[]",
    )


def _make_lab(root: Path) -> Lab:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "lab.sqlite"
    conn = store.connect(path)
    seed(conn)
    files: dict[str, tuple[Method, Path]] = {}
    for m in (TOYS, MOMENTUM, ROTATION, DRIFT):
        f = root / f"{m.id.lower()}_test.py"
        f.write_text(f"# {m.id} {m.name}\n", encoding="utf-8")
        files[m.id] = (m, f)
    with conn:
        for mid, name, family in (("M9001", "Toy picks", "stock-toy"),
                                  ("M9002", "Momentum", "stock-momentum"),
                                  ("M9003", "Rotation", "etf-rotation"),
                                  ("M9004", "Broken", "stock-broken"),
                                  ("M9005", "Drifted", "stock-drift")):
            store.add_method(conn, id=mid, name=name, family=family, source_kind="knowledge",
                             hypothesis="h")
        trials = [_trial(m.id, c.id, config_digest(c))
                  for m in (TOYS, MOMENTUM, ROTATION) for c in m.all_candidates()]
        trials += [_trial("M9004", "M9004-A", "d-broken"),
                   _trial("M9005", "M9005-A", "stale-digest"),
                   _trial("M9001", "M9001-GONE", "d-gone")]
        store.insert_trials(conn, trials)
    return Lab(conn, path, files)


@pytest.fixture()
def lab(tmp_path):
    made = _make_lab(tmp_path / "lab")
    yield made
    made.conn.close()


# ---- stores -----------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def market() -> Market:
    days = dates.sessions(FIRST, DEV_END)
    history = {s: smoke_history(s, k, days) for k, s in enumerate(("SPY", *STOCKS))}
    membership = Membership(intervals=tuple((s, days[0], None) for s in STOCKS))
    return Market(history=history, membership=membership, fx=((days[0], Decimal("2000")),))


def _data(market: Market, fingerprint: str, purpose: str | None = None) -> ResearchData:
    return ResearchData(market=market, dividends={}, spy_dividends=(), fingerprint=fingerprint,
                        manifest={} if purpose is None else {"purpose": purpose},
                        price_fingerprint=fingerprint, purpose=purpose)


@dataclass
class Stores:
    dev: Path
    sv: Path
    loads: list[str]


def _stores(root: Path, monkeypatch, market: Market, *, sv_series: bool = True) -> Stores:
    d, s = root / "dev-store", root / "sv-store"
    d.mkdir(parents=True, exist_ok=True)
    s.mkdir(parents=True, exist_ok=True)
    (d / research.MANIFEST_FILE).write_text(json.dumps({"fingerprint": "smoke-dev"}))
    (s / research.MANIFEST_FILE).write_text(json.dumps({"fingerprint": "smoke-sv", "purpose": SV}))
    with_series = market.with_series(SMOKE_T13W)
    by_dir = {d: _data(with_series, "smoke-dev"),
              s: _data(with_series if sv_series else market, "smoke-sv", SV)}
    loads: list[str] = []

    def load_store(store_dir, **kw):
        loads.append(Path(store_dir).name)
        return by_dir[Path(store_dir)]

    monkeypatch.setattr(research, "load_store", load_store)
    return Stores(d, s, loads)


@pytest.fixture()
def stores(tmp_path, monkeypatch, market) -> Stores:
    return _stores(tmp_path / "stores", monkeypatch, market)


def _replay(lab: Lab, stores: Stores, **kw) -> panel_replay.Report:
    return panel_replay.run(lab.conn, stores.dev, stores.sv, git_sha="abc", load=lab.load,
                            now=lambda: STAMP, **kw)


def _frozen(conn) -> tuple[str, str]:
    trials = repr([tuple(r) for r in conn.execute("SELECT * FROM trials ORDER BY n")])
    shas = repr([tuple(r) for r in conn.execute("SELECT id, source_sha FROM methods ORDER BY id")])
    return hashlib.sha256(trials.encode()).hexdigest(), hashlib.sha256(shas.encode()).hexdigest()


def _whole(conn, cid: str) -> set[tuple[str, str]]:
    """(store role, picks hash) of the arm's whole-window rows."""
    return {(str(r["store_role"]), str(r["picks_hash"]))
            for r in store.panel_results(conn, signal_id=cid) if str(r["era"]) == panel.ERAS[0]}


def _panels(conn) -> list[tuple]:
    return sorted((str(r["signal_id"]), str(r["store_role"]), str(r["era"]), int(r["months"]),
                   str(r["picks_hash"]), round(float(r["fm_slope"]), 12))
                  for r in store.panel_results(conn))


def _lab_cli(lab: Lab, stores: Stores, *argv: str) -> int:
    return cli.main(["lab", "--db", str(lab.path), "panel-replay", *argv,
                     "--store", str(stores.dev), "--sv-store", str(stores.sv)])


# ---- recording --------------------------------------------------------------------------------


def test_every_recorded_stock_arm_gets_one_replay_panel_on_both_stores(lab, stores):
    rep = _replay(lab, stores)
    assert rep.selected == 11 and rep.already == 0 and rep.attempted == 11
    assert rep.recorded == RECORDABLE
    rows = {str(r["id"]): r for r in store.panel_signals(lab.conn) if str(r["kind"]) == "replay"}
    assert set(rows) == set(RECORDABLE)
    for cid, r in rows.items():
        method, path = lab.files[cid.split("-")[0]]
        assert r["method_id"] == method.id
        assert r["source_sha"] == hashlib.sha256(path.read_bytes()).hexdigest()
        roles = {(str(x["store_role"]), str(x["store_fingerprint"]))
                 for x in store.panel_results(lab.conn, signal_id=cid)}
        assert roles == {("dev", "smoke-dev"), ("survivorship", "smoke-sv")}
        assert {x[0] for x in _whole(lab.conn, cid)} == {"dev", "survivorship"}
    assert rows["M9001-TOP"]["name"] == "Toy picks"  # the method's own name (Decisions)
    assert rows["M9001-TOP"]["hypothesis"] == "Toy picks hypothesis"
    assert rows["M9002-MOM"]["family"] == "stock-momentum"
    assert "M9003-ROT" not in rows  # an etf-* method is outside the default family
    assert stores.loads == ["dev-store", "sv-store"]  # each store once, dev first


def test_trials_and_recorded_method_shas_are_byte_identical_after_a_replay(lab, stores):
    before = _frozen(lab.conn)
    _replay(lab, stores)
    assert _frozen(lab.conn) == before


def test_two_arms_that_pick_the_same_names_record_the_same_pick_set(lab, stores):
    _replay(lab, stores)
    assert _whole(lab.conn, "M9001-TOP") == _whole(lab.conn, "M9001-TOPB")
    assert _whole(lab.conn, "M9001-TOP") != _whole(lab.conn, "M9002-MOM")


def test_a_fixed_holding_is_not_a_pick(lab, stores):
    _replay(lab, stores)
    # SPY plus the same six names as TOP: with the fixed holding dropped, the pick set is TOP's.
    assert _whole(lab.conn, "M9001-ETF") == _whole(lab.conn, "M9001-TOP")


def test_the_scorer_drops_fixed_holdings_and_names_outside_the_pool(market):
    d = date(2015, 9, 30)
    prepared = TOY.prepare(market.history)
    targets = TOY.targets_prepared(prepared, market.membership.members_on(d), d, frozenset(), Rule("etf"))
    named = [t.symbol for t in targets if t.symbol != "SPY"]
    pool = frozenset(STOCKS) - {named[0]}
    scorer = panel_replay.PickScorer(TOY, prepared, Rule("etf"))
    assert scorer(market, pool, d) == {s: 1.0 for s in named[1:]}


def test_an_arm_that_reads_its_holdings_is_counted_not_special_cased(lab, stores):
    rep = _replay(lab, stores)
    assert "M9001-KEEP" in rep.recorded
    assert rep.held_sensitive == ("M9001-KEEP",)


# ---- skipping ---------------------------------------------------------------------------------


def test_one_failing_allocator_does_not_stop_the_sweep(lab, stores):
    rep = _replay(lab, stores)
    why = {s.candidate_id: s.category for s in rep.skipped}
    assert why["M9001-BOOM"] == panel_replay.RAISED
    assert why["M9001-CASH"] == panel_replay.TOO_FEW
    assert "M9001-ETF" in rep.recorded  # after BOOM in trial order, same allocator object


def test_unimportable_vanished_and_drifted_arms_are_skipped_before_any_store_loads(lab, stores):
    rep = _replay(lab, stores, method_ids=["M9004", "M9005"])
    why = {s.candidate_id: s.category for s in rep.skipped}
    assert why == {"M9004-A": panel_replay.NO_IMPORT, "M9005-A": panel_replay.DRIFTED}
    assert stores.loads == []
    full = _replay(lab, stores)
    assert {s.candidate_id: s.category for s in full.skipped}["M9001-GONE"] == panel_replay.NOT_IN_FILE


def test_an_arm_the_survivorship_store_cannot_feed_is_recorded_on_neither_store(lab, tmp_path, monkeypatch, market):
    stores = _stores(tmp_path / "no-series", monkeypatch, market, sv_series=False)
    rep = _replay(lab, stores)
    skip = {s.candidate_id: s for s in rep.skipped}["M9002-SER"]
    assert skip.category == panel_replay.NO_DATA and "survivorship" in skip.detail
    assert store.panel_results(lab.conn, signal_id="M9002-SER") == []
    assert "M9002-SER" not in {str(r["id"]) for r in store.panel_signals(lab.conn)}
    assert "M9002-MOM" in rep.recorded


# ---- resuming ---------------------------------------------------------------------------------


def test_limit_takes_the_unfinished_arms_in_trial_order(lab, stores):
    first = _replay(lab, stores, limit=2)
    assert first.recorded == ("M9001-TOP", "M9001-TOPB")
    second = _replay(lab, stores, limit=2)
    assert second.already == 2
    assert second.recorded == ("M9001-KEEP",)
    assert [s.candidate_id for s in second.skipped] == ["M9001-CASH"]


def test_a_finished_selection_measures_nothing_and_loads_no_store(lab, stores):
    first = _replay(lab, stores, method_ids=["M9002"])
    assert first.recorded == ("M9002-MOM", "M9002-SER")
    loads = list(stores.loads)
    again = _replay(lab, stores, method_ids=["M9002"])
    assert (again.attempted, again.already, again.recorded) == (0, 2, ())
    assert stores.loads == loads
    assert len(store.panel_results(lab.conn, signal_id="M9002-MOM")) == len(
        store.panel_results(lab.conn, signal_id="M9002-SER"))


def test_two_jobs_record_the_same_panels_as_one(tmp_path, stores):
    one, two = _make_lab(tmp_path / "one"), _make_lab(tmp_path / "two")
    try:
        _replay(one, stores, jobs=1)
        _replay(two, stores, jobs=2)
        assert _panels(one.conn) == _panels(two.conn)
        assert _panels(one.conn)
    finally:
        one.conn.close()
        two.conn.close()


# ---- the command ------------------------------------------------------------------------------


def test_the_command_replays_through_the_real_handler(lab, stores, monkeypatch, capsys):
    monkeypatch.setattr(panel_replay, "module_loader", lambda: lab.load)
    assert _lab_cli(lab, stores, "M9002") == 0
    out = capsys.readouterr().out
    assert "recorded 2 replay panel(s), one transaction each" in out
    m = re.search(r"Lab N \(dev trials\): (\d+) before, (\d+) after; luck gate N = (\d+) before, (\d+) after", out)
    assert m is not None and m.group(1) == m.group(2) and m.group(3) == m.group(4)
    assert {str(r["id"]) for r in store.panel_signals(lab.conn)} >= {"M9002-MOM", "M9002-SER"}


def test_a_method_outside_the_family_exits_2_and_loads_nothing(lab, stores, monkeypatch):
    monkeypatch.setattr(panel_replay, "module_loader", lambda: lab.load)
    assert _lab_cli(lab, stores, "M9003") == 2
    assert stores.loads == []
    assert store.panel_signals(lab.conn) == []


def test_a_run_that_can_replay_nothing_exits_1(lab, stores, monkeypatch):
    monkeypatch.setattr(panel_replay, "module_loader", lambda: lab.load)
    assert _lab_cli(lab, stores, "M9004") == 1
    assert stores.loads == []


def test_jobs_above_two_is_refused_by_the_parser(lab, stores):
    with pytest.raises(SystemExit) as e:
        _lab_cli(lab, stores, "--jobs", "3")
    assert e.value.code == 2


def test_the_help_formats_and_names_the_default_family(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["lab", "panel-replay", "--help"])
    assert e.value.code == 0
    assert "stock-%" in capsys.readouterr().out
```
**Impact:** A new test file. It touches no shared file and never opens `/home/miftah/seer/lab/lab.sqlite`.
**Check:** `cd /home/miftah/.worktrees/seer/sera-signal-panel && PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest -n 2 engine/tests/test_lab_panel_replay.py` is green.

Note for the implementer: the fixture starts in 2005 because phase 1 leaves out an era with fewer
than `MIN_ERA_MONTHS = 12` measured months and F4's screen needs 253 bars; every member passes the
screen, so 40 names clear `MIN_SCORED = 30` and `MIN_PICKS = 5` is met by every arm but CASH. Do not stub
`panel.measure`: these tests exist to show the real pick-set path end to end. If phase 2's
`panel_signals(conn)` returns signal rows of every kind, `test_a_method_outside_the_family_exits_2`
still holds because the lab has none.

### Step 4: the feature-map section
**File:** `.claude/skills/verify-seer/features/signal-panel.md` (append at the end of the file phase 3 creates, after its `## Gotchas` list)
**Change:** One section with its own driving block and gotchas.
**Code:**
````markdown

## Replay: `lab panel-replay`

- `lab panel-replay [M0614 ...] [--family-like PATTERN] [--limit N] [--store DIR] [--sv-store DIR] [--jobs 1|2]`: every recorded dev arm of every method whose family is like PATTERN (default `stock-%`) becomes a pick-set panel. The arm's own allocator is called at each month end with nothing held, its fixed instruments and names outside the pool are dropped, and the rest are measured on the dev store and then the survivorship-check store. Each arm is recorded in one transaction: a `panel_signals` row of kind `replay` under the candidate id with `method_id` set, plus its `panel_results` rows.
- The report prints how many arms were selected, already recorded and attempted; per store, the arms measured, the wall time and the time per arm; `recorded K replay panel(s), one transaction each`; the held-aware count; and a skipped table, counted by reason with one line per arm. The reasons are: method file does not import, arm no longer in its file, configuration drifted, bracket strategy, picks no index members, a store lacks its data, allocator raised, or never picked 5 pool names in a month. It ends with the same N / luck gate N / looks footer as `lab panel`.
- A re-run measures only arms with no panel on the current dev store, plus the ones it skipped before. With nothing left it prints "nothing to replay: no store was loaded".
- Refused, exit 2, nothing loaded: a named method with no dev trial in the family, a malformed id, and every store refusal `lab panel` makes. `--jobs` above 2 is refused by argparse (exit 2). Exit 1 only when the run attempted arms and the selection holds no replay panel at all.

### Driving it with verify.sh

```sh
$V up --no-web --empty
SV=/home/miftah/seer/engine/.research-sv
DB=$HOME/.local/state/seer-verify/RUN/lab.sqlite
sqlite3 "file:$DB?mode=ro" "select * from trials order by n" | sha256sum                 # keep
sqlite3 "file:$DB?mode=ro" "select id, source_sha from methods order by id" | sha256sum   # keep
$V lab RUN panel-replay --sv-store $SV --limit 20      # minutes: "20 attempted this run", "recorded K replay panel(s)", a skipped table; exit 0
$V labsql RUN "select count(*) from panel_signals where kind = 'replay'"                                   # K
$V labsql RUN "select count(*) from (select distinct signal_id, store_role from panel_results where signal_id in (select id from panel_signals where kind = 'replay'))"   # 2K
$V lab RUN panel-replay --sv-store $SV --jobs 2        # the rest of the sweep: run it in the background (see docs/runbooks/signal-panel.md for its measured time)
$V lab RUN panel-replay --sv-store $SV                 # "recorded 0"; every finished arm counted as already recorded; exit 0
$V lab RUN panel-replay M0205 --sv-store $SV           # exit 2: M0205 is not a stock-* method
$V lab RUN panel-replay --jobs 3                       # exit 2 (argparse)
$V lab RUN panel-map --kind replay --top 15            # the replays ranked by controlled slope, twins marked
sqlite3 "file:$DB?mode=ro" "select * from trials order by n" | sha256sum                 # same as kept
sqlite3 "file:$DB?mode=ro" "select id, source_sha from methods order by id" | sha256sum   # same as kept
git status --short engine/src/seer_engine/lab/methods                                    # nothing
```

### Gotchas (replay)

- Pass `--sv-store` every time: `$V lab` starts from `env -i` and does not export `SEER_SV_STORE`.
- The full sweep loads both stores and runs every recorded stock arm's allocator on each. Run it with Bash `run_in_background`, never under a foreground timeout, and never beside another store-loading command (invariant 6: at most two such sessions on this machine).
- An arm that was skipped is attempted again on every run, so a re-run after a complete sweep still loads both stores whenever any arm was skipped. That is by design: a fixed file or store may now feed it.
- Never run it against `/home/miftah/seer/lab/lab.sqlite` from a phase session. The production replay is run once from the main checkout by Sera (phase 7).
- `held-aware` arms (keep bands, rules that read what is held) are measured from an empty book every month. Their panel is an approximation, and the report says how many there are.
- Counts here are examples. Read them back with `labsql` (CLAUDE.md, Claim verification).
````
**Impact:** Documentation only. The README row stays phase 3's. It already points at this file.

### Step 5: the runbook, filled from this phase's measured runs
**File:** `docs/runbooks/signal-panel.md` (new)
**Change:** Run the Verification journeys J2, J3 and J4 and the neighbor check first. Then write
this file, replacing every `{{...}}` token with the figure from the named evidence file
(`/usr/bin/time -v`'s "Elapsed (wall clock)" and "Maximum resident set size", and the report's own
lines). Do not round a figure into a different one, and do not estimate one that a journey did not
produce. Phase 7 appends its Sera-facing section under a new heading at the end.
**Code:**
````markdown
# The signal panel: running a replay and a signal sweep

Stage one of the lab measures a stock-picking idea on a stock-by-month panel of the dev window
before it can become a book. This runbook is the operator's half: how to run `lab panel` on new
signal files and `lab panel-replay` over the recorded stock-signal methods, what they cost on this
machine, and how to check that nothing frozen moved. The Sera-facing procedure (sweeps, syntheses,
when to launch a child session) is the last section.

Every figure below was measured on {{DATE}} in the phase-4 proof run (verify-seer run
{{RUN}}), with `/usr/bin/time -v`, against a copy of the lab database and the main checkout's
stores. Re-measure after a store or panel-rule change; do not scale these by hand.

## Before you start

- Stores: `SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research` and
  `SEER_SV_STORE=/home/miftah/seer/engine/.research-sv` (or `--store` / `--sv-store`). A worktree
  has neither and never rebuilds one. Both commands refuse a test-window store from its manifest
  and never read `engine/.research-test`.
- Database: a session that is not the production replay points `SEER_LAB_DB` at a scratch copy
  (`cp /home/miftah/seer/lab/lab.sqlite "$SCRATCH/lab.sqlite"`). Lab commands migrate the file on
  connect, so even a read dirties the shared one.
- Machine: one store-loading command at a time beside at most one other session. Five
  concurrent sessions took WSL down twice.

## A signal sweep (`lab panel`)

```sh
python -m seer_engine lab next-signal-id                      # the id for the next signal file
# write engine/src/seer_engine/lab/signals/sNNNN_<slug>.py, commit it (the commit is the pre-registration)
python -m seer_engine lab panel SNNNN [SNNNN ...]             # or --pending for every committed, unpanelled signal
python -m seer_engine lab panel-map --kind signal             # ranked, with the published verdict
```

Measured: `lab panel S0001 S0002` took {{SWEEP_WALL}} wall at {{SWEEP_RSS}} maximum resident
memory. That covers both store loads and both frames, so most of the time is fixed per run, not
per signal: panel several signals in one command rather than one command each.

## The replay (`lab panel-replay`)

The first job of the panel: every recorded dev arm of every `stock-*` method as a pick-set panel,
so the explored space reads as one ranked map. The arm's own allocator is called at each month end
with nothing held, and its picks are measured on both stores. Nothing in `trials`, no config
digest and no method file changes.

```sh
python -m seer_engine lab panel-replay --limit 20 --jobs 1    # a first batch, to time this machine
python -m seer_engine lab panel-replay --jobs 2               # the rest; run in the background
python -m seer_engine lab panel-replay                        # resume or confirm: finished arms are not re-measured
python -m seer_engine lab panel-map --kind replay --top 40    # the explored space, ranked, twins marked
```

Measured:

| Run | Arms | Wall | Per arm (dev / survivorship) | Max RSS |
|---|---|---|---|---|
| `--limit 20 --jobs 1` (J2) | 20 attempted | {{J2_WALL}} | {{J2_DEV_PER_ARM}} / {{J2_SV_PER_ARM}} | {{J2_RSS}} |
| full sweep `--jobs 2` (J3) | {{J3_ATTEMPTED}} attempted of {{J3_SELECTED}} selected | {{J3_WALL}} | {{J3_DEV_PER_ARM}} / {{J3_SV_PER_ARM}} | {{J3_RSS}} |
| re-run after the sweep (J4) | {{J4_ATTEMPTED}} attempted | {{J4_WALL}} | n/a | {{J4_RSS}} |

The full sweep recorded {{J3_RECORDED}} replay panels and skipped {{J3_SKIPPED}} arms. Of the
recorded arms, {{J3_HELD}} change their picks when handed a holding (keep bands, rules that read
what is held). Their panels are read from an empty book every month, an approximation.

`--jobs 2` forks two workers after each store loads; each prepares its own allocators. Do not go
above two on this machine. If memory is tight, run `--jobs 1` instead of `--jobs 2`.

`--limit N` takes the first N **unfinished** arms in trial order, and an arm skipped on an earlier
run is still unfinished. Once N or more skipped arms sit at the front of the queue, a `--limit N`
batch attempts only them and records nothing while work remains. Use `--limit` for the first
timing batch only; run the rest without it. A full run is done when a re-run prints
`recorded 0 replay panel(s)`.

### Reading the skipped table

| Reason | What it means | What to do |
|---|---|---|
| method file does not import | the committed file raises on import today | nothing; a frozen file is not edited to make it replayable |
| arm is no longer in its method file | the recorded candidate id is not declared any more | nothing |
| arm's configuration differs from the recorded one | `config_digest` moved, usually through an imported params class | report it: this is the frozen-record drift `test_every_recorded_configuration_still_digests_to_its_recorded_digest` guards |
| bracket strategy, not an allocator | a `DESIGN_V0` bracket arm | nothing; the panel reads book allocators |
| does not pick index members | the allocator trades fixed instruments only | nothing; there is no pick set |
| a store lacks data the allocator reads | the named store has no dividends, series, shares or fundamentals | repair the store (`docs/runbooks/survivorship-store.md`) and re-run |
| allocator raised | the allocator failed on this store; the detail names the exception | read the detail; the arm is attempted again next run |
| never picked 5 pool names in a month | the switch was never on, or the picks were never in the pool | nothing; it has no pick set to measure |

A skipped arm is attempted again on every run, so a re-run after a complete sweep still loads both
stores whenever anything was skipped (J4 above).

## Checking that nothing frozen moved

Run before and after any replay on a copy, and compare:

```sh
sqlite3 "file:$SEER_LAB_DB?mode=ro" "select * from trials order by n" | sha256sum
sqlite3 "file:$SEER_LAB_DB?mode=ro" "select id, source_sha from methods order by id" | sha256sum
git status --short engine/src/seer_engine/lab/methods        # must print nothing
```

Both hashes must match, and the git status must be empty. In the phase-4 proof both hashes were
unchanged across J2, J3 and J4.

## Who runs the production replay

Sera's preflight, once, from the main checkout, against the shared `lab/lab.sqlite`, when the
panel holds no replay rows. The procedure, including how its `lab stage` commit is made, is in
"The first replay" below. A phase session never runs it.
````
**Impact:** Documentation only.
**Check:** `grep -c '{{' docs/runbooks/signal-panel.md` prints `0`, and each filled figure appears in
the evidence file its journey names.

## Principles applied

- Laziness protocol: no score seam and no edit to any allocator or method file. The replay calls each arm's own `targets_prepared`. It reuses phase 3's `check_stores`, `open_store` (which holds the load, the D10 pin and the fingerprint check), `Subject`, `StoreRun`, `record`, `has_whole_window`, `Counts` and `footer`, plus `runner.market_fields`, `method.MODULE_NAME`/`methods_package`/`config_digest` and yardstick's fork-pool shape. The only new structure is what the replay forces: grouping by allocator object, and a tolerant loader, because `discover()` raises on the first bad file.
- Boundary discipline: method ids, the family pattern, `--limit` and `--jobs` are validated once, at the parser (`_positive_count`, `choices=(1, 2)`) and in `select`. Both manifests are checked once, in `panel_run.check_stores`. After that the code trusts the typed `Recorded`/`Work`/`StorePair` and does not re-check them.
- Make illegal states unrepresentable: a replay is written only through `panel_run.record`, which takes both stores' runs. So the replay holds dev readings in memory and writes nothing until the survivorship reading exists, and "recorded on one store only" has no code path. That is also how "the survivorship store lacks its data" becomes "recorded on neither store" with no extra check.
- Build the lever: frozen-record safety is proven by a script-shaped check (two `sha256sum` hashes plus `git status`) that the runbook, the feature map and every proof journey repeat, and by a unit test that hashes the same two queries. It is not proven by reading the diff.
- Test behavior, not implementation: the tests drive `panel_replay.run` and `cli.main` against a real scratch database, with real allocators (a toy and `FACTOR`) and phase 1's real evaluator. They read the rows back. Only the I/O edges are replaced: `research.load_store` and the method-file loader.
- Prove it works: Proof runs the replay through `verify.sh` on the real dev and survivorship stores, against a lab copy, first on 20 arms and then on every stock arm. Each run checks the row counts and the two frozen hashes.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/sera-signal-panel && /home/miftah/seer/engine/.venv/bin/ruff check engine`
**Tests:** `cd /home/miftah/.worktrees/seer/sera-signal-panel && PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest -n 2 engine/tests/test_lab_panel_replay.py engine/tests/test_lab_panel_cli.py engine/tests/test_lab_methods.py`
**Proof:** On a lab copy with the real dev and survivorship stores, `lab panel-replay` records one replay panel per replayable recorded stock arm on both stores. It reports every other arm with its reason, resumes without re-measuring, refuses a non-stock method, and leaves the `trials` rows, the recorded source shas and the method files byte-identical.
- Harness: `.claude/skills/verify-seer` (`V=.claude/skills/verify-seer/scripts/verify.sh`, run from the worktree root `/home/miftah/.worktrees/seer/sera-signal-panel`; `$V up --no-web --empty` prints `RUN=`). Set `SV=/home/miftah/seer/engine/.research-sv`, `DB=$HOME/.local/state/seer-verify/$RUN/lab.sqlite` (the run's private lab copy) and `P=$HOME/.local/state/seer-verify/$RUN/p4` (`mkdir -p $P`). Define `frozen() { sqlite3 "file:$DB?mode=ro" "select * from trials order by n" | sha256sum; sqlite3 "file:$DB?mode=ro" "select id, source_sha from methods order by id" | sha256sum; }`, then run `frozen > $P/frozen-before.txt` right after `up`, before any lab command.
- Feature-map entries: `.claude/skills/verify-seer/features/signal-panel.md` (the `## Replay` section)
- Journeys:
  - **J1** · traces R3.1 — `PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest -n 2 engine/tests/test_lab_panel_replay.py -v` → passes when every test passes, including `test_every_recorded_stock_arm_gets_one_replay_panel_on_both_stores`, `test_trials_and_recorded_method_shas_are_byte_identical_after_a_replay`, `test_an_arm_the_survivorship_store_cannot_feed_is_recorded_on_neither_store` and `test_two_jobs_record_the_same_panels_as_one`
  - **J2** · traces R3.1 — `/usr/bin/time -v $V lab $RUN panel-replay --sv-store $SV --limit 20 --jobs 1 > $P/j2.txt 2>&1`; `$V labsql $RUN "select count(*) from panel_signals where kind = 'replay'"`; `$V labsql $RUN "select count(*) from (select distinct signal_id, store_role from panel_results where signal_id in (select id from panel_signals where kind = 'replay'))"`; `$V labsql $RUN "select count(*) from panel_signals p where p.kind = 'replay' and (p.method_id is null or not exists (select 1 from trials t where t.candidate_id = p.id and t.window = 'dev' and t.method_id = p.method_id))"`; `frozen > $P/frozen-j2.txt`; `git status --short engine/src/seer_engine/lab/methods` → passes when `$P/j2.txt` shows exit code 0, `20 attempted this run`, two store lines (`dev store`, then `survivorship store`), and `recorded K replay panel(s)` with K ≥ 1, where K plus the `skipped N arm(s)` count plus any parallel-session count equals 20; when the first query returns K, the second 2K and the third 0; when the footer's `Lab N (dev trials)` and `luck gate N` before/after pairs are equal; when `diff $P/frozen-before.txt $P/frozen-j2.txt` is empty; and when the git status prints nothing
  - **J3** · traces R3.1 — `sqlite3 "file:$DB?mode=ro" "select count(*) from trials t join methods m on m.id = t.method_id where t.window = 'dev' and m.family like 'stock-%'"` (note S); then, with Bash `run_in_background`, `/usr/bin/time -v $V lab $RUN panel-replay --sv-store $SV --jobs 2 > $P/j3.txt 2>&1`; when it ends, J2's three `labsql` queries again; `frozen > $P/frozen-j3.txt`; `git status --short engine/src/seer_engine/lab/methods` → passes when `$P/j3.txt` shows exit code 0 and `S recorded dev arm(s) selected, K already recorded on this dev store` (K from J2); when the run's `recorded R`, its skipped count and its parallel-session count add up to S − K; when the first query returns K + R, the second 2(K + R) and the third 0; when the footer's N pairs are equal; when `diff $P/frozen-before.txt $P/frozen-j3.txt` is empty; and when the git status prints nothing
  - **J4** · traces R3.1 — `/usr/bin/time -v $V lab $RUN panel-replay --sv-store $SV --jobs 2 > $P/j4.txt 2>&1`; `$V labsql $RUN "select count(*) from panel_signals where kind = 'replay'"`; `frozen > $P/frozen-j4.txt` → passes when `$P/j4.txt` shows exit code 0, `K + R already recorded on this dev store`, `attempted this run` equal to J3's skipped count, and `recorded 0 replay panel(s)`; when the query still returns K + R; and when `diff $P/frozen-before.txt $P/frozen-j4.txt` is empty
  - **J5** · traces R3.1 — `$V lab $RUN panel-replay M0205 --sv-store $SV > $P/j5a.txt 2>&1`; `$V lab $RUN panel-replay --jobs 3 > $P/j5b.txt 2>&1`; `$V lab $RUN panel-map --kind replay --top 15 > $P/j5c.txt 2>&1`; `$V labsql $RUN "select count(*) from panel_signals where kind = 'replay'"` → passes when `j5a` shows exit code 2 and "has no recorded dev trial in a method whose family is like 'stock-%'" with no "store ... loaded" log line; when `j5b` shows exit code 2 and an argparse "invalid choice" message; when `j5c` shows exit code 0, a header naming "Benjamini-Hochberg", 15 ranked rows of kind `replay` whose panel ids are candidate ids (`M\d{4}-...`), and a tail reading `15 of K + R panel(s) shown`; and when the count still equals K + R
- Neighbor check: phase 3's `lab panel` shares `panel_run`, both tables and the `commands/lab.py` neighborhood. `/usr/bin/time -v $V lab $RUN panel S0001 S0002 --sv-store $SV > $P/neighbor.txt 2>&1` (in the background), then `PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest -n 2 engine/tests/test_lab_panel_cli.py engine/tests/test_lab_methods.py engine/tests/test_lab_survivorship.py`. Passes when the panel run exits 0 and prints "2 signal(s) recorded" (or "already panelled" if phase 3's proof ran on this copy), `frozen` still matches `$P/frozen-before.txt`, and all three test files pass. Its wall time and max RSS are the runbook's `{{SWEEP_*}}` figures.
- Cost: no paid call and no network. J3 is the long drive: both stores load once, and every recorded stock arm's allocator runs at every month end on each store. The planner's allocator-only figure (about 1.4 s per arm per store on one process) is why it runs in the background with `--jobs 2`. Do not start any other store-loading command while J2, J3, J4 or the neighbor check runs (invariant 6). `$V down $RUN` afterwards.
**Exit criteria:** On a lab copy with the real stores, the full `lab panel-replay` exits 0 with every selected stock arm either recorded on both stores or listed with a reason. A re-run records nothing new. A non-stock method is refused with exit 2. `panel-map --kind replay` prints the ranked replays. The sha256 of `select * from trials order by n` and of `select id, source_sha from methods order by id` is unchanged, and `git status --short engine/src/seer_engine/lab/methods` is empty. `test_lab_panel_replay.py` passes, `ruff check engine` is clean, and `docs/runbooks/signal-panel.md` holds no `{{` token.

## Handoffs

- **Phase 3 (reconciled):** the load, D10 pin and fingerprint check live once, in
  `panel_run.open_store`, which this phase calls. `panel_replay.unfinished` applies
  `split_recorded`'s rule to `Recorded` values, before any method file is imported
  (`split_recorded` takes `Subject`s, which need the file). `panel_run.measure_stores` is
  deliberately not used; the reasons are in the Interface Contract.
- **Phase 2 (reconciled):** `insert_panel_signal` returns False for the same id and sha (a replay
  re-measured on a new dev store) and raises `LabError` for a different sha; `insert_panel_results`
  skips a repeated key. So the IntegrityError catch and the "database refused the record" skip
  category are gone: exactly one mechanism (phase 2's skip) handles the unchanged survivorship
  store.
- **Phase 1 (reconciled):** in picks mode `panel.measure` returns a reading with empty `stats`
  and never raises when no month has `MIN_PICKS` picks, so an always-cash arm is reported as
  `never picked 5 pool names in a month` and nothing is recorded for it.
- **Phase 7:** the Sera-facing half of `docs/runbooks/signal-panel.md` goes under new headings
  appended at the end ("A sweep, step by step", "The first replay"); this phase's headings do not
  use those names. `--limit` counts previously skipped arms, so Sera runs the replay without it. Sera's preflight runs the production replay once from the main checkout, as
  `lab panel-replay` against the shared DB when `lab panel-map --kind replay` prints "no replay
  panel recorded yet", followed by `lab stage` and an explicit-path commit. `CLAUDE.md` and the
  skills name `lab panel-replay` and `--sv-store`.
- **R3.2** (twins collapse in the correction and show in `lab panel-map`) belongs to phase 2's
  `published` and phase 3's map. This phase only produces replay rows whose `picks_hash` makes the
  twins visible. Its J5 shows the map but traces only R3.1.
- **Cosmetic, left alone:** none.
- No criterion is untraced.

## Rollback

Revert this phase's commit. It adds `lab/panel_replay.py`, `test_lab_panel_replay.py`, the runbook
and one feature-map section. It also adds one parser, one handler, one `_HANDLERS` entry and two
docstring lines in `commands/lab.py`; nothing else imports any of them. No proof run touched the
shared `lab/lab.sqlite`: every replay row this phase wrote lives in a verify-seer run's private
copy, which `$V down` deletes. If a replay had been recorded in the shared database, its
`panel_signals`/`panel_results` rows are append-only and would stay after a revert, unread by the
reverted code.
