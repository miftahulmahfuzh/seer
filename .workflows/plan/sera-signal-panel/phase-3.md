# Phase 3: `lab panel`, `lab panel-map`, `lab next-signal-id`

**Plan set:** `SERA_SIGNAL_PANEL_PLAN.md`
**Analysis:** `.workflows/analyze/20261113-200537-K7P2_code_analyzer.md`
**Satisfies:** R1, R2, R3, R4 — a committed signal file is measured on both stores and recorded with one command, and the ranked map can be read, without moving the luck gate's N
**Criteria:** R1.2, R2.1, R2.2, R2.3, R3.2, R4.3
**Depends on:** Phase 1, 2
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/commands`, `engine/src/seer_engine/lab`

---

## Goal

After this phase an agent can run `lab panel S0001 S0002` (or `--pending`). It refuses an
uncommitted signal, a non-dev store or a missing survivorship store before loading a bar. It
measures every requested signal on the dev store, then on the survivorship-check store, never
holding both, and records each signal in one transaction only once both stores have measured it.
`lab panel-map` prints the recorded panels ranked by controlled slope, with phase 2's published
verdict. `lab next-signal-id` gives the next free `S` id. None of the three moves N, the luck gate's
N or the test-window looks, and each prints them before and after.

## Interface Contract

**Deletes:** none
**Renames:** none
**Creates:**
- `engine/src/seer_engine/lab/panel_run.py` (new module): constants `DEV`, `SURVIVORSHIP`; dataclasses `Subject`, `StorePair`, `StoreRun`, `Selection`, `Counts`, `MapRow`; functions `check_stores`, `load`, `open_store(conn, pair, role, *, command) -> ResearchData` (the one loader: `load` + the D10 pin and manifest-fingerprint check for the dev store; phase 4 calls it too), `signal_subject`, `select_signals`, `split_recorded`, `measure_stores`, `has_whole_window`, `result_rows`, `record`, `format_reading`, `panel_map`, `format_map`, `next_signal_id`, `footer`; type alias `ScorerFactory`.
- `engine/src/seer_engine/commands/lab.py`: subparsers `panel`, `panel-map`, `next-signal-id`; handlers `_panel`, `_panel_map`, `_next_signal_id`; three `_HANDLERS` entries; three docstring entries.
- `engine/tests/test_lab_panel_cli.py` (new).
- `.claude/skills/verify-seer/features/signal-panel.md` (new) and its row in `features/README.md`.
**Signature changes:** none
**Requires (from earlier phases):**
- Phase 1 (`lab/signal.py`): `Signal` with the contract's fields (`id, name, family, source_kind, source_ref, hypothesis, expected_failure, lookback, score, ...`), `discover() -> dict[str, tuple[Signal, Path]]`, `source_sha(path) -> str`.
- Phase 1 (`lab/panel.py`): `RULE_ID`, `ERAS == ("all", "pre2009", "2009-2015")`, `Scorer`, `EraStats` with fields `era, months, mean_pool, mean_scored, ic_mean, ic_t, spread_top, spread_t, fm_slope, fm_t, top_turnover`, `PanelReading` with `stats, picks_hash, dropped_exits`, `build_frame(data)`, `signal_scorer(signal)`, and `measure(frame, scorer, *, mode="score")` (mode passed by keyword).
- Phase 2 (`lab/store.py`): `PanelSignalRow` and `PanelResultRow` constructible by keyword with field names equal to the column names in the index's SQL; `insert_panel_signal(conn, row) -> bool` and `insert_panel_results(conn, rows) -> int`, which **do not commit** (the caller opens `begin_immediate` and commits, as `insert_yardstick` is used at `commands/lab.py:4214-4216`); `panel_signals(conn)` and `panel_results(conn, signal_id=None)` returning rows that can be read by column name (`row["id"]`, like `sqlite3.Row`); `has_panel(conn, signal_id, rule_id, store_fingerprint) -> bool`; `next_signal_id(conn, taken=()) -> str` (one above every recorded signal id and every id in `taken`; `"S0001"` on an empty record). `insert_panel_signal` returns False (writes nothing) for an id already recorded from the same `source_sha` and raises `LabError` for a different sha; `insert_panel_results` skips a repeated primary key and returns how many it inserted. `store_fingerprint` is the store's full `ResearchData.fingerprint` (= the manifest's `"fingerprint"`, which `check_stores` reads).
- Phase 2 (`lab/panel_verdict.py`) and phase 1 (`lab/panel.py`) both define the rule id and the eras (`panel_verdict.RULE_ID`, `store.PANEL_ERAS`); this phase owns the test that pins them equal.
- Phase 2 (`lab/panel_verdict.py`): `published(conn, *, dev_fingerprint=...) -> dict[str, Verdict]` with `Verdict.clears, q, reasons, twin_of`.
**Leaves alone (owned by others):** `lab/panel.py`, `lab/signal.py`, `lab/signals/*` (Phase 1); `lab/store.py`, `lab/panel_verdict.py`, the snapshot (Phase 2); `lab/panel_replay.py` and the `panel-replay` subcommand (Phase 4); `lab/method.py`, `lab/runner.py`, `lab/hardgate.py`, `features/lab-cli.md` (Phase 5); `web/**`, `features/sera.md` (Phase 6); `CLAUDE.md`, `README.md`, the skills (Phase 7).

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/panel_run.py` | create | load-both-stores, measure, record-once helpers; the map and next-id logic; shared with phase 4 |
| `engine/src/seer_engine/commands/lab.py` | modify | docstring entries (after `:186`, and `:208`), three parsers (before `:1062`), three handlers (before `_HANDLERS` at `:4780`), three `_HANDLERS` entries (after `:4814`) |
| `engine/tests/test_lab_panel_cli.py` | create | CLI behaviour on tmp lab DBs and synthetic stores; the `RULE_ID`/`ERAS` equality pin between phases 1 and 2 |
| `.claude/skills/verify-seer/features/signal-panel.md` | create | four-section feature-map entry |
| `.claude/skills/verify-seer/features/README.md` | modify | one table row after the `lab-cli.md` row (line 15) |

## Implementation Steps

### Step 1: `lab/panel_run.py`, the shared run-and-record module
**File:** `engine/src/seer_engine/lab/panel_run.py` (new)
**Change:** One module that owns the steps `lab panel` takes and phase 4's `lab panel-replay` will
reuse: refuse the stores from their manifests, pick the subjects, load each store in turn and
measure every subject on it, then record each subject once. It also holds the map and next-id
logic, so the three handlers stay a few lines each and the tests can read the behaviour through
`cli.main`. It writes no SQL of its own: every read and write goes through phase 2's API.

Two shapes come from principles (see **Principles applied**):
- `record()` takes both `StoreRun`s. It cannot be called after one store, so a half record has no
  code path.
- `open_store()` is the only function that loads a store (phase 4's replay calls it too), and
  `measure_stores()` deletes each store and its frame before the next load. So the D10 pin and the
  fingerprint check exist once, and "never both in memory" is enforced in one loop for `lab panel`.

**Code:**
```python
"""``lab panel``: measure registered signals on the dev store and the survivorship store, and record both.

Stage one of the two-stage lab (SERA_SIGNAL_PANEL_PLAN.md). A signal is cheap to measure and cheap
to record, so this module's job is mostly to keep what it records honest:

* **Every refusal comes before a bar is read.** An unknown id, a signal file that is not committed
  exactly as it stands (the commit is the pre-registration, as it is for a method file), a signal
  whose file changed after it was panelled, a dev store that declares any window but dev, a dev
  store carrying a purpose marker, a missing or unmarked survivorship-check store: each is decided
  from git and the two manifests alone. ``engine/.research-test`` is refused by its manifest and
  never loaded.
* **The two stores are never alive together.** Each is about 1 GB on a 15 GB laptop.
  :func:`measure_stores` loads the dev store, builds the panel frame once, measures every subject,
  and drops both before it loads the survivorship-check store. Every load goes through
  :func:`open_store`.
* **No half record.** :func:`record` takes the dev run and the survivorship run together and writes
  the subject's ``panel_signals`` row and all of its ``panel_results`` rows in one transaction, so
  a panel either has both stores or does not exist. A store that fails to load after the other was
  measured leaves nothing behind.
* **A repeat is free.** ``store.has_panel`` on the dev store's fingerprint decides what is already
  measured, *before* any store loads, and is asked again under the write lock for a parallel
  session that got there first.
* **Nothing here is a trial.** No ``trials`` row, no moment, no status, no journal entry: the lab's
  N, the luck gate's N and the test-window looks cannot move, and :func:`footer` prints all three
  before and after so the invariant is visible on every run.

Phase 4's replay reuses :class:`Subject` (``mode="picks"``), :class:`StoreRun`,
:func:`check_stores`, :func:`open_store`, :func:`has_whole_window`, :func:`record`,
:class:`Counts` and :func:`footer`. It runs its own store loop (grouped, per-arm error handling)
rather than :func:`measure_stores`, but loads each store through :func:`open_store`, so the D10 pin
and the fingerprint check exist once.
"""

from __future__ import annotations

import gc
import json
import logging
import multiprocessing
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from seer_engine import research
from seer_engine.commands.backtest_dev import registry_problem
from seer_engine.lab import hardgate, panel, panel_verdict, signal, store

log = logging.getLogger(__name__)

DEV = "dev"
SURVIVORSHIP = "survivorship"

ScorerFactory = Callable[[research.ResearchData], panel.Scorer]
"""Builds a subject's scorer on one loaded store. A registered signal ignores the store; a replay
(phase 4) prepares its allocator on it, once per store."""


@dataclass(frozen=True)
class Subject:
    """One panel to measure: the row it is recorded under, and how to score it on a loaded store."""

    row: store.PanelSignalRow
    scorer: ScorerFactory
    mode: Literal["score", "picks"] = "score"

    @property
    def id(self) -> str:
        return str(self.row.id)


@dataclass(frozen=True)
class StorePair:
    """Two stores whose manifests passed :func:`check_stores`. ``dev_fingerprint`` is what the dev
    manifest declares; ``research.load_store`` verifies it, and :func:`measure_stores` checks the
    loaded store still carries it."""

    dev_dir: Path
    sv_dir: Path
    dev_fingerprint: str


@dataclass(frozen=True)
class StoreRun:
    """Every subject's reading on one loaded store."""

    role: str
    fingerprint: str
    readings: Mapping[str, panel.PanelReading]


@dataclass(frozen=True)
class Selection:
    """What ``lab panel`` was asked to measure, after the refusals.

    ``skipped`` is ``--pending`` only: a signal file that is not committed is somebody's draft and
    is listed, not measured. A named one is refused instead (:func:`select_signals`)."""

    subjects: tuple[Subject, ...]
    skipped: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Counts:
    """The three numbers a panel must never move."""

    dev_trials: int
    gate_n: int
    looks: int

    @classmethod
    def read(cls, conn) -> Counts:
        return cls(store.dev_trial_count(conn), store.gate(conn).n, store.test_looks(conn))


@dataclass(frozen=True)
class MapRow:
    """One recorded panel as ``lab panel-map`` ranks it."""

    id: str
    kind: str
    name: str
    slope: float
    slope_t: float
    spreads: Mapping[str, float | None]  # dev era -> annualised top-minus-pool spread
    sv_slope: float | None
    verdict: panel_verdict.Verdict | None


# --------------------------------------------------------------------------- the two stores


def _manifest(store_dir: Path, role: str, command: str) -> tuple[research.Window, str | None, str]:
    """(declared window, purpose, declared fingerprint) from the manifest alone; ``store.LabError``
    when it is missing or unreadable. Reads no data file."""
    try:
        window = research.declared_window(store_dir)
        purpose = research.declared_purpose(store_dir)
        raw = json.loads((store_dir / research.MANIFEST_FILE).read_text(encoding="utf-8"))
    except OSError as e:
        raise store.LabError(
            f"{command}: cannot read the {role} store's manifest in {store_dir} ({e}). Nothing was "
            f"measured or recorded"
        ) from e
    except ValueError as e:
        raise store.LabError(
            f"{command}: {e}. The {role} store is missing or unreadable, so nothing was measured or "
            f"recorded. Both stores live in the main checkout (engine/.research and "
            f"engine/.research-sv); from a worktree, export SEER_RESEARCH_STORE and SEER_SV_STORE "
            f"to them"
        ) from e
    fingerprint = raw.get("fingerprint")
    return window, purpose, "" if fingerprint is None else str(fingerprint)


def check_stores(dev_dir: Path, sv_dir: Path, *, command: str) -> StorePair:
    """Refuse a wrong pair of stores from their manifests, before either loads (``store.LabError``).

    The dev side must declare the dev window and carry no purpose marker: it is the store every
    recorded trial was compared on. The survivorship side must exist, be marked
    ``research.SURVIVORSHIP_PURPOSE`` and declare the dev window too. A test-window store is refused
    by its manifest's own window keys here, so no command in this module ever reads its bars.
    """
    dev_dir, sv_dir = Path(dev_dir), Path(sv_dir)
    if dev_dir.resolve() == sv_dir.resolve():
        raise store.LabError(
            f"{command}: --store and --sv-store both name {dev_dir.resolve()}; the panel is "
            f"measured on the dev store and on the survivorship-check store, so it needs two "
            f"different stores. Nothing was measured or recorded"
        )
    window, purpose, fingerprint = _manifest(dev_dir, "dev", command)
    if window.name != research.DEV_WINDOW.name:
        raise store.LabError(
            f"{command}: {dev_dir} declares the {window.name} window ({window.start.isoformat()}.."
            f"{window.end.isoformat()}). The panel measures the dev window and nothing else, so "
            f"this store is refused before a bar of it is read. Nothing was measured or recorded"
        )
    if purpose is not None:
        raise store.LabError(
            f"{command}: {dev_dir} is marked {purpose!r} in its manifest. --store must be the dev "
            f"store the lab's trials were recorded on; the survivorship-check store goes to "
            f"--sv-store. Nothing was measured or recorded"
        )
    sv_window, sv_purpose, _ = _manifest(sv_dir, "survivorship-check", command)
    if sv_purpose != research.SURVIVORSHIP_PURPOSE:
        raise store.LabError(
            f"{command}: {sv_dir} is not a survivorship-check store (its manifest's purpose is "
            f"{sv_purpose!r}, not {research.SURVIVORSHIP_PURPOSE!r}). Every panel is measured on "
            f"both stores or not at all. Build one with `python -m seer_engine survivorship_store "
            f"--build`, or export SEER_SV_STORE to the main checkout's engine/.research-sv. "
            f"Nothing was measured or recorded"
        )
    if sv_window.name != research.DEV_WINDOW.name:
        raise store.LabError(
            f"{command}: {sv_dir} declares the {sv_window.name} window; the survivorship-check "
            f"store must cover the dev window. Nothing was measured or recorded"
        )
    return StorePair(dev_dir=dev_dir, sv_dir=sv_dir, dev_fingerprint=fingerprint)


def load(store_dir: Path, *, role: str, command: str) -> research.ResearchData:
    """Load one store on the dev window and check its purpose matches ``role``."""
    t0 = time.perf_counter()
    try:
        data = research.load_store(Path(store_dir))
    except FileNotFoundError as e:
        raise store.LabError(
            f"{command}: the {role} store {store_dir} is missing {e.filename or e}. Nothing was "
            f"recorded"
        ) from e
    except ValueError as e:
        raise store.LabError(
            f"{command}: {store_dir}: {e}. The panel reads the dev window and nothing else. "
            f"Nothing was recorded"
        ) from e
    want = research.SURVIVORSHIP_PURPOSE if role == SURVIVORSHIP else None
    if data.purpose != want:
        raise store.LabError(
            f"{command}: {store_dir} loaded with purpose {data.purpose!r}, not {want!r}, so it "
            f"cannot be the {role} store. Nothing was recorded"
        )
    if data.window.name != research.DEV_WINDOW.name:
        raise store.LabError(
            f"{command}: {store_dir} loaded the {data.window.name} window; the panel reads the dev "
            f"window and nothing else. Nothing was recorded"
        )
    log.info("%s store %s loaded (%.1fs)", role, str(data.fingerprint)[:12], time.perf_counter() - t0)
    return data


def open_store(conn, pair: StorePair, role: str, *, command: str) -> research.ResearchData:
    """``role``'s store of ``pair``, loaded (:func:`load`) and, for the dev store, checked.

    The dev store must pass ``hardgate.pin_dev_store`` (D10) exactly as ``lab run``'s does: a panel
    measured on prices other than the benchmark's would rank signals on a store no trial was
    compared on. It must also still carry the full fingerprint its manifest declared, the value
    every panel row is keyed on. The one loader :func:`measure_stores` and phase 4's replay share.
    """
    store_dir = pair.dev_dir if role == DEV else pair.sv_dir
    data = load(store_dir, role=role, command=command)
    if role == DEV:
        hardgate.pin_dev_store(conn, data.price_fingerprint)
        if pair.dev_fingerprint and str(data.fingerprint) != pair.dev_fingerprint:
            raise store.LabError(
                f"{command}: {store_dir} loaded as {str(data.fingerprint)[:12]} but its manifest "
                f"declared {pair.dev_fingerprint[:12]}; the store changed while this command "
                f"ran. Nothing was recorded"
            )
    return data


# --------------------------------------------------------------------------- what to measure


def signal_subject(sig: signal.Signal, path: Path) -> Subject:
    """A registered signal as a panel subject, recorded under its own id with its file's sha."""
    row = store.PanelSignalRow(
        id=sig.id,
        kind="signal",
        name=sig.name,
        family=sig.family,
        hypothesis=sig.hypothesis,
        expected_failure=sig.expected_failure,
        source_kind=sig.source_kind,
        source_ref=sig.source_ref,
        method_id=None,
        source_sha=signal.source_sha(path),
        created=store.now_iso(),
    )
    return Subject(row=row, scorer=lambda _data, _sig=sig: panel.signal_scorer(_sig))


def select_signals(conn, ids: Sequence[str], *, pending: bool, command: str) -> Selection:
    """The signals ``lab panel`` will consider, refusing before any store loads (``store.LabError``).

    Named ids: an id with no signal file is refused, and so is a file that ``registry_problem``
    reports as untracked, modified or staged. Committing the file is what pre-registers the idea.
    ``--pending``: every discovered signal, with an uncommitted file listed in ``skipped``, so a
    parallel session's draft never blocks a sweep. Either way, a signal whose committed file no
    longer has the sha recorded with its panel is refused: the record would describe an idea the
    file no longer holds, and a changed idea needs a new id.
    """
    found = signal.discover()
    if pending:
        wanted = list(found)
    else:
        unknown = [sid for sid in ids if sid not in found]
        if unknown:
            raise store.LabError(
                f"{command}: no signal file for {', '.join(unknown)} in seer_engine/lab/signals/ "
                f"(a signal is sNNNN_<slug>.py exporting SIGNAL). Nothing was measured or recorded"
            )
        wanted = list(dict.fromkeys(ids))
    recorded_sha = {
        str(r["id"]): str(r["source_sha"]) for r in store.panel_signals(conn) if str(r["kind"]) == "signal"
    }
    subjects: list[Subject] = []
    skipped: list[tuple[str, str]] = []
    refused: list[str] = []
    for sid in wanted:
        sig, path = found[sid]
        problem = registry_problem(path)
        if problem is not None:
            if pending:
                skipped.append((sid, problem))
            else:
                refused.append(f"{sid}: {problem}")
            continue
        sha = signal.source_sha(path)
        if sid in recorded_sha and recorded_sha[sid] != sha:
            refused.append(
                f"{sid}: its file changed after it was panelled (recorded {recorded_sha[sid][:12]}, "
                f"now {sha[:12]}); a changed idea is a new signal, so give it the id `lab "
                f"next-signal-id` prints"
            )
            continue
        subjects.append(signal_subject(sig, path))
    if refused:
        raise store.LabError(
            f"{command} refused before any store was loaded: {'; '.join(refused)}. A signal is "
            f"pre-registered by committing its file exactly as it will run. Nothing was measured "
            f"or recorded"
        )
    return Selection(subjects=tuple(subjects), skipped=tuple(skipped))


def split_recorded(
    conn, subjects: Sequence[Subject], dev_fingerprint: str
) -> tuple[tuple[Subject, ...], tuple[str, ...]]:
    """(subjects still to measure, ids already panelled on this dev store under ``panel.RULE_ID``)."""
    todo: list[Subject] = []
    already: list[str] = []
    for s in subjects:
        if dev_fingerprint and store.has_panel(conn, s.id, panel.RULE_ID, dev_fingerprint):
            already.append(s.id)
        else:
            todo.append(s)
    return tuple(todo), tuple(already)


# --------------------------------------------------------------------------- measuring


_CHILD_WORK: tuple[object, list, list] | None = None  # set only inside a forked worker, by _adopt


def _adopt(work: tuple[object, list, list]) -> None:
    global _CHILD_WORK
    _CHILD_WORK = work


def _measure_in_child(i: int) -> panel.PanelReading:
    if _CHILD_WORK is None:
        raise RuntimeError("a panel worker ran before it was handed its work")
    frame, scorers, modes = _CHILD_WORK
    return panel.measure(frame, scorers[i], mode=modes[i])


def _measure_all(frame, scorers: list, modes: list, jobs: int) -> list[panel.PanelReading]:
    """One reading per scorer, in input order, whatever ``jobs`` is.

    ``jobs > 1`` forks workers after the frame is built (copy-on-write; the work is the pool
    initializer's argument, which a fork does not pickle), as ``yardstick._outcomes`` does.
    ``Pool.map`` keeps input order, so completion order never reaches the result.
    """
    if jobs <= 1 or len(scorers) <= 1:
        return [panel.measure(frame, sc, mode=m) for sc, m in zip(scorers, modes)]
    ctx = multiprocessing.get_context("fork")
    procs = min(jobs, len(scorers))
    with ctx.Pool(processes=procs, initializer=_adopt, initargs=((frame, scorers, modes),)) as pool:
        return pool.map(_measure_in_child, range(len(scorers)), chunksize=1)


def measure_stores(
    conn, subjects: Sequence[Subject], pair: StorePair, *, command: str, jobs: int = 1
) -> tuple[StoreRun, StoreRun]:
    """Measure every subject on the dev store, release it, then on the survivorship-check store.

    Each store is loaded through :func:`open_store` (D10 pin and fingerprint check for dev).
    ``panel.build_frame`` runs once per store, whatever the number of subjects.
    """
    runs: list[StoreRun] = []
    for role in (DEV, SURVIVORSHIP):
        data = open_store(conn, pair, role, command=command)
        t0 = time.perf_counter()
        frame = panel.build_frame(data)
        scorers = [s.scorer(data) for s in subjects]
        readings = _measure_all(frame, scorers, [s.mode for s in subjects], jobs)
        runs.append(StoreRun(role=role, fingerprint=str(data.fingerprint),
                             readings={s.id: r for s, r in zip(subjects, readings)}))
        log.info("%s store: %d panel(s) measured (%.1fs)", role, len(subjects), time.perf_counter() - t0)
        del frame, scorers, readings, data
        gc.collect()
    return runs[0], runs[1]


def has_whole_window(reading: panel.PanelReading) -> bool:
    """True when the reading has a whole-window era: the one every verdict condition reads."""
    return any(s.era == panel.ERAS[0] for s in reading.stats)


# --------------------------------------------------------------------------- recording


def result_rows(
    subject_id: str, run: StoreRun, *, git_sha: str, measured: str
) -> list[store.PanelResultRow]:
    """One ``panel_results`` row per era the reading on ``run`` has."""
    reading = run.readings[subject_id]
    return [
        store.PanelResultRow(
            signal_id=subject_id,
            rule_id=panel.RULE_ID,
            store_role=run.role,
            store_fingerprint=run.fingerprint,
            era=s.era,
            months=s.months,
            mean_pool=s.mean_pool,
            mean_scored=s.mean_scored,
            ic_mean=s.ic_mean,
            ic_t=s.ic_t,
            spread_top=s.spread_top,
            spread_t=s.spread_t,
            fm_slope=s.fm_slope,
            fm_t=s.fm_t,
            top_turnover=s.top_turnover,
            picks_hash=reading.picks_hash,
            git_sha=git_sha,
            measured=measured,
        )
        for s in reading.stats
    ]


def record(
    conn, subject: Subject, dev_run: StoreRun, sv_run: StoreRun, *, git_sha: str, measured: str
) -> bool:
    """Write ``subject``'s panel on both stores in one transaction. False when a parallel session
    recorded it on this dev store first; theirs is kept and nothing is written."""
    rows = result_rows(subject.id, dev_run, git_sha=git_sha, measured=measured)
    rows += result_rows(subject.id, sv_run, git_sha=git_sha, measured=measured)
    store.begin_immediate(conn)
    with conn:
        if store.has_panel(conn, subject.id, panel.RULE_ID, dev_run.fingerprint):
            return False
        store.insert_panel_signal(conn, subject.row)
        store.insert_panel_results(conn, rows)
    return True


# --------------------------------------------------------------------------- printing


def _num(x: float | None, spec: str) -> str:
    return "-" if x is None else format(float(x), spec)


def _pct(x: float | None) -> str:
    return "-" if x is None else f"{float(x) * 100:+.1f}%"


# Units (reconciled, Decisions): the spread is annualised, the controlled slope is MONTHLY (next
# month's return per 1 sd of score, or per pick). The headers say so, so the two are never read as
# one unit.
_READING_HEAD = (
    f"  {'store':<14}{'era':<11}{'months':>7}{'IC':>8}{'IC t':>7}{'sprd/yr':>9}{'sprd t':>8}"
    f"{'slope/mo':>10}{'slope t':>8}{'turn':>6}"
)


def format_reading(subject: Subject, dev_run: StoreRun, sv_run: StoreRun) -> str:
    """The subject's readings on both stores, one line per store and era."""
    lines = [f"{subject.id}  {subject.row.name}", _READING_HEAD]
    for run in (dev_run, sv_run):
        for s in run.readings[subject.id].stats:
            lines.append(
                f"  {run.role:<14}{s.era:<11}{s.months:>7}{_num(s.ic_mean, '+.3f'):>8}"
                f"{_num(s.ic_t, '+.2f'):>7}{_pct(s.spread_top):>9}{_num(s.spread_t, '+.2f'):>8}"
                f"{_num(s.fm_slope, '+.4f'):>10}{_num(s.fm_t, '+.2f'):>8}{_num(s.top_turnover, '.2f'):>6}"
            )
    return "\n".join(lines)


def footer(conn, before: Counts, *, lead: str) -> str:
    """N, the luck gate's N and the looks, before and after: the invariant, printed."""
    after = Counts.read(conn)
    return (
        f"{lead} Lab N (dev trials): {before.dev_trials} before, {after.dev_trials} after; luck "
        f"gate N = {before.gate_n} before, {after.gate_n} after; test-window looks used: "
        f"{before.looks} before, {after.looks} after. A panel is not a trial."
    )


# --------------------------------------------------------------------------- the map


def panel_map(conn, *, kind: str = "all") -> tuple[str | None, list[MapRow], int]:
    """(dev fingerprint, rows ranked by dev whole-window controlled slope, panels on other stores).

    The map is read on one dev store: the one the most recent dev panel was measured on. A panel
    measured only on an older dev store is counted, not ranked, because its numbers and its
    verdict's population belong to other prices. The verdict is ``panel_verdict.published`` on that
    same fingerprint, computed on read and never stored.
    """
    results = sorted(
        (r for r in store.panel_results(conn) if str(r["rule_id"]) == panel.RULE_ID),
        key=lambda r: (str(r["measured"]), str(r["signal_id"])),
    )
    dev_rows = [r for r in results if str(r["store_role"]) == DEV]
    if not dev_rows:
        return None, [], 0
    fingerprint = str(dev_rows[-1]["store_fingerprint"])
    cells: dict[str, dict[tuple[str, str], object]] = {}
    for r in results:
        if str(r["store_role"]) == DEV and str(r["store_fingerprint"]) != fingerprint:
            continue
        # sorted by measured, so a later survivorship reading of the same era overwrites an older one
        cells.setdefault(str(r["signal_id"]), {})[(str(r["store_role"]), str(r["era"]))] = r
    elsewhere = len({str(r["signal_id"]) for r in dev_rows} - {
        sid for sid, c in cells.items() if (DEV, panel.ERAS[0]) in c
    })
    meta = {str(r["id"]): r for r in store.panel_signals(conn)}
    verdicts = panel_verdict.published(conn, dev_fingerprint=fingerprint)
    rows: list[MapRow] = []
    for sid, c in cells.items():
        head = c.get((DEV, panel.ERAS[0]))
        if head is None:
            continue
        info = meta.get(sid)
        row_kind = "signal" if info is None else str(info["kind"])
        if kind != "all" and row_kind != kind:
            continue
        sv = c.get((SURVIVORSHIP, panel.ERAS[0]))
        rows.append(MapRow(
            id=sid,
            kind=row_kind,
            name="" if info is None else str(info["name"]),
            slope=float(head["fm_slope"]),
            slope_t=float(head["fm_t"]),
            spreads={
                era: (float(c[(DEV, era)]["spread_top"]) if (DEV, era) in c else None)
                for era in panel.ERAS
            },
            sv_slope=None if sv is None else float(sv["fm_slope"]),
            verdict=verdicts.get(sid),
        ))
    rows.sort(key=lambda m: (-m.slope, m.id))
    return fingerprint, rows, elsewhere


_MAP_HEAD = (
    f"{'#':>4}  {'panel':<16}{'kind':<8}{'slope/mo':>10}{'t':>7}{'q':>7}  {'verdict':<8}{'twin of':<16}"
    f"{'sprd/yr':>11}{'pre-2009':>10}{'2009-15':>9}{'sv slp/mo':>10}  name"
)


def format_map(
    fingerprint: str | None, rows: Sequence[MapRow], elsewhere: int, *, top: int | None, kind: str
) -> str:
    """The ranked map, or the empty-state line when there is nothing to rank."""
    if fingerprint is None or not rows:
        what = "panel" if kind == "all" else f"{kind} panel"
        line = (
            f"no {what} recorded yet. Write and commit a signal file, then run `lab panel SNNNN`"
            if kind != "replay" else
            "no replay panel recorded yet. `lab panel-replay` records one per recorded stock-picking arm"
        )
        if elsewhere:
            line += f" ({elsewhere} panel(s) are recorded only on an older dev store)"
        return line
    shown = list(rows) if top is None else list(rows)[:top]
    lines = [
        f"Signal panel map, rule {panel.RULE_ID}, dev store {fingerprint[:12]}, ranked by the dev "
        f"whole-window slope after momentum, beta, size and volatility (FDR "
        f"{panel_verdict.FDR:.2f}, Benjamini-Hochberg across every distinct pick set on this store). "
        f"Slopes are monthly next-month returns per 1 sd of score (or per pick); spreads are "
        f"top bucket minus pool, annualised",
        _MAP_HEAD,
    ]
    for i, m in enumerate(shown, start=1):
        v = m.verdict
        verdict = "-" if v is None else ("clears" if v.clears else "no")
        q = "-" if v is None or v.q is None else f"{v.q:.3f}"
        twin = "" if v is None or v.twin_of is None else str(v.twin_of)
        lines.append(
            f"{i:>4}  {m.id:<16}{m.kind:<8}{m.slope:>+10.4f}{m.slope_t:>+7.2f}{q:>7}  {verdict:<8}"
            f"{twin:<16}{_pct(m.spreads.get('all')):>11}{_pct(m.spreads.get('pre2009')):>10}"
            f"{_pct(m.spreads.get('2009-2015')):>9}{_num(m.sv_slope, '+.4f'):>10}  {m.name}"
        )
        if v is not None and not v.clears and v.reasons:
            lines.append(f"{'':>6}why not: {'; '.join(v.reasons)}")
    tail = f"{len(shown)} of {len(rows)} panel(s) shown"
    if elsewhere:
        tail += f"; {elsewhere} more recorded only on an older dev store and not ranked here"
    lines.append(tail)
    return "\n".join(lines)


# --------------------------------------------------------------------------- next id


def next_signal_id(conn) -> str:
    """One past the highest id either the record or a signal file holds.

    A signal that is committed but not yet panelled has no row, yet its file already owns its id,
    so every discovered signal id is handed to ``store.next_signal_id`` as ``taken`` (phase 2's
    contract): one rule, in the store, for both halves.
    """
    return store.next_signal_id(conn, taken=signal.discover())
```
**Impact:** New module; nothing imports it until Step 2. `ruff check engine` must pass (no unused names: `Mapping`, `Callable`, `Sequence`, `Literal` are all used).

### Step 2: the module docstring entries in `commands/lab.py`
**File:** `engine/src/seer_engine/commands/lab.py:186` (insert after the last `lab yardstick` line, before `lab idea` at `:187`), and `:208`
**Change:** Add three entries in the docstring's column layout, and name `lab panel` beside
`lab survivorship` in the paragraph about `SEER_SV_STORE`. The docstring is not argparse text, so
`%` would be harmless here, but the entries do not use it anyway.
**Code:** insert after line 186 (`                                    written for it`):
```text
    lab panel S0001 [S0002 ...] | --pending [--store DIR] [--sv-store DIR] [--jobs J]
                                    stage one: measure committed signal files (lab/signals/) on a
                                    stock-by-month panel of the dev window, first on the dev store
                                    and then on the survivorship-check store, never both in
                                    memory, and record each signal's three eras on both stores in
                                    one transaction (panel_signals, panel_results). Refused before
                                    any store loads, exit 2: an unknown id, a named signal file
                                    that is not committed as it stands, a file changed since its
                                    panel, a dev store declaring any window but dev, a missing or
                                    unmarked survivorship-check store. A signal already panelled on
                                    the dev store is not measured again. Never a trial: N, the luck
                                    gate's N and the looks do not move
    lab panel-map [--top K] [--kind signal|replay|all]
                                    report only: every recorded panel ranked by its controlled
                                    slope, with the published verdict (Benjamini-Hochberg across
                                    every distinct pick set), its q, the panel it is a twin of and
                                    the three eras' spread. Writes nothing
    lab next-signal-id              the next free signal id: one past both the record and the
                                    committed signal files
```
and replace lines 207-210:
```text
Parallel sessions (sera-the-explorer) share one database: SEER_LAB_DB sets --db,
SEER_RESEARCH_STORE sets --store, and SEER_SV_STORE sets lab survivorship's --sv-store. A
worktree has none of the three stores of its own, so a child exports all three to the main
checkout's.
```
with:
```text
Parallel sessions (sera-the-explorer) share one database: SEER_LAB_DB sets --db,
SEER_RESEARCH_STORE sets --store, and SEER_SV_STORE sets the --sv-store of lab survivorship and
lab panel. A worktree has none of the three stores of its own, so a child exports all three to
the main checkout's.
```
**Impact:** Text only.

### Step 3: the three parsers
**File:** `engine/src/seer_engine/commands/lab.py:1061` (insert after the `yardstick` parser's last argument, the `--dry-run` at `:1057-1059`, and before `s = sub.add_parser("idea", ...)` at `:1062`)
**Change:** Three flat subcommands, as the contract names them. No `%` in any `help=` (argparse
%-interpolates them); `description=` is not interpolated but carries no `%` either. `--jobs`
reuses `_positive_count` (`:252`).
**Code:**
```python
    s = sub.add_parser(
        "panel",
        # No literal `%` in any `help=` string below: argparse %-interpolates every `help=`.
        help="screen committed signals on a stock-by-month panel, on both stores; no trial, no N",
        description=(
            "Stage one of the lab. For every index member and month-end of the dev window, score "
            "each named signal file (seer_engine/lab/signals/sNNNN_<slug>.py) and set it against "
            "the next month's total return: rank correlation, the top bucket's spread over the "
            "pool and the slope after momentum, beta, size and volatility, each with its "
            "t-statistic, for the whole window, before 2009 and 2009-2015. Measured on the dev "
            "store and then on the survivorship-check store (never both in memory), and recorded "
            "once per signal in one transaction only after both are measured. Refused before any "
            "store loads (exit 2, nothing recorded): an unknown id, a named signal file that is "
            "not committed exactly as it stands, a file changed since its panel, a dev store that "
            "declares any window but dev or carries a purpose marker, a missing or unmarked "
            "survivorship-check store. The dev store must carry the benchmark's prices (D10). A "
            "signal already panelled on this dev store is not measured again. Nothing here is a "
            "trial: the lab's N, the luck gate's N and the test-window looks do not move."
        ),
    )
    s.add_argument("signal", nargs="*", metavar="S0001",
                   help="signal ids to measure; each must be a committed file under "
                        "seer_engine/lab/signals/")
    s.add_argument("--pending", action="store_true",
                   help="every committed signal file with no panel on this dev store yet; an "
                        "uncommitted file is listed and skipped, not refused")
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
    s.add_argument("--jobs", type=_positive_count, default=1, metavar="J",
                   help="worker processes across signals (default 1). The readings are identical "
                        "for any J; only the time changes")

    s = sub.add_parser(
        "panel-map",
        help="report only: every recorded signal panel ranked by its controlled slope, with its verdict",
        description=(
            "Read the recorded panels and print one row per panel, ranked by the dev store's "
            "whole-window slope after momentum, beta, size and volatility, with the published "
            "verdict (a Benjamini-Hochberg correction across every distinct pick set recorded on "
            "that dev store, computed on read), its q, the earlier panel it is a twin of, and the "
            "top bucket's spread over the pool in each era. Loads no research store and writes "
            "nothing: the lab's N, the luck gate's N and the looks do not move."
        ),
    )
    s.add_argument("--top", type=_positive_count, default=None, metavar="K",
                   help="print only the K highest-ranked panels (default: all of them)")
    s.add_argument("--kind", choices=("signal", "replay", "all"), default="all",
                   help="registered signals, replays of recorded methods, or both (default: all)")

    sub.add_parser("next-signal-id",
                   help="the next free signal id: one past the record and the committed signal files")
```
**Impact:** `lab --help` lists three more commands. `cli.main` dispatches through `_HANDLERS`
(Step 5), so a parser without a handler would raise `KeyError`. Steps 3-5 land together.

### Step 4: the three handlers
**File:** `engine/src/seer_engine/commands/lab.py:4779` (insert after `_seed`, which ends at `:4777`, and before `_HANDLERS = {` at `:4780`)
**Change:** Thin handlers over `panel_run`. Every refusal raises `store.LabError`, which `run()`
(`:1140-1148`) turns into exit 2. `_panel` exits 2 at the end, after recording the rest, when a
signal could not be measured on a store. Its readings are printed and nothing is recorded for it,
so `--pending` keeps picking it up. `_next_signal_id` prints only the id on stdout, so
`$(lab next-signal-id)` captures it cleanly, and the N line goes to stderr, as `lab idea` does
with its neighbours.
**Code:**
```python
def _panel(conn, args) -> int:
    """``lab panel S0001 [S0002 ...] | --pending``: stage one, the signal panel (lab/panel_run.py).

    Order is the contract: ids and git first (``select_signals``), then the two manifests
    (``check_stores``), then what is already recorded on the dev store (``split_recorded``). All
    of that runs before a bar is read. Only then is each store loaded in turn
    (``measure_stores``), and each signal recorded once both stores have measured it
    (``record``). A repeat loads nothing. N, the luck gate's N and the looks are printed before
    and after.
    """
    from seer_engine.lab import panel, panel_run, runner

    command = "lab panel"
    if research.DEV_END != dev.DEV_END:
        raise store.LabError("research.DEV_END differs from dev.DEV_END; refusing to run")
    if bool(args.signal) == bool(args.pending):
        raise store.LabError(
            "lab panel: name the signals to measure (lab panel S0001 S0002) or pass --pending, "
            "not both and not neither"
        )
    selection = panel_run.select_signals(conn, args.signal, pending=args.pending, command=command)
    pair = panel_run.check_stores(Path(args.store), Path(args.sv_store), command=command)
    todo, already = panel_run.split_recorded(conn, selection.subjects, pair.dev_fingerprint)
    before = panel_run.Counts.read(conn)
    for sid, why in selection.skipped:
        print(f"skipped {sid}: {why} (--pending measures committed signal files only)")
    for sid in already:
        print(f"{sid}: already panelled on dev store {pair.dev_fingerprint[:12]} under "
              f"{panel.RULE_ID}; not measured again")
    if not todo:
        print("\nnothing to measure.")
        print(panel_run.footer(conn, before, lead="Nothing was recorded."))
        return 0

    t0 = time.perf_counter()
    jobs = int(getattr(args, "jobs", 1) or 1)
    dev_run, sv_run = panel_run.measure_stores(conn, todo, pair, command=command, jobs=jobs)
    git_sha = runner.git_head(config.REPO_ROOT)
    measured = store.now_iso()
    recorded, lost, unmeasurable = 0, 0, []
    for s in todo:
        print()
        print(panel_run.format_reading(s, dev_run, sv_run))
        empty = [
            run.role for run in (dev_run, sv_run)
            if not panel_run.has_whole_window(run.readings[s.id])
        ]
        if empty:
            unmeasurable.append(
                f"{s.id}: no month could be measured on the {' and '.join(empty)} store(s), so "
                f"there is no whole-window reading to record; check its lookback and what it "
                f"scores. Nothing was recorded for it"
            )
            print("  not recorded: no whole-window reading on " + " and ".join(empty))
            continue
        if panel_run.record(conn, s, dev_run, sv_run, git_sha=git_sha, measured=measured):
            recorded += 1
            print(f"  recorded on dev store {dev_run.fingerprint[:12]} and survivorship-check "
                  f"store {sv_run.fingerprint[:12]}")
        else:
            lost += 1
            print("  already recorded by a parallel session; kept theirs")
    print()
    print(
        f"{recorded} signal(s) recorded, {len(already)} already panelled, "
        f"{len(selection.skipped)} skipped, {lost} recorded first by a parallel session, "
        f"{len(unmeasurable)} not measurable"
    )
    stage = (" Solo: `python -m seer_engine lab stage` so seertrade.site/sera shows it."
             if recorded else "")
    print(panel_run.footer(conn, before, lead="No trial was recorded.") + stage)
    log.info("lab panel: %d signal(s) measured (%.1fs)", len(todo), time.perf_counter() - t0)
    if unmeasurable:
        for msg in unmeasurable:
            log.error("%s", msg)
        return 2
    return 0


def _panel_map(conn, args) -> int:
    """``lab panel-map``: the recorded panels, ranked, with the published verdict. Writes nothing."""
    from seer_engine.lab import panel_run

    before = panel_run.Counts.read(conn)
    fingerprint, rows, elsewhere = panel_run.panel_map(conn, kind=args.kind)
    print(panel_run.format_map(fingerprint, rows, elsewhere, top=args.top, kind=args.kind))
    print()
    print(panel_run.footer(conn, before, lead="Nothing was recorded."))
    return 0


def _next_signal_id(conn, args) -> int:
    """``lab next-signal-id``: the id alone on stdout; the N line on stderr."""
    from seer_engine.lab import panel_run

    before = panel_run.Counts.read(conn)
    print(panel_run.next_signal_id(conn))
    print(panel_run.footer(conn, before, lead="Nothing was recorded."), file=sys.stderr)
    return 0
```
**Impact:** `config`, `dev`, `research`, `store`, `sys`, `time`, `Path`, `log` are already imported
at the top of `commands/lab.py` (`:214-238`).

### Step 5: register the handlers
**File:** `engine/src/seer_engine/commands/lab.py:4814` (`"next-id": _next_id,`)
**Change:** Add three entries right after `"next-id": _next_id,`.
**Code:**
```python
    "next-id": _next_id,
    "panel": _panel,
    "panel-map": _panel_map,
    "next-signal-id": _next_signal_id,
```
**Impact:** The three subcommands dispatch. Phase 4 adds `"panel-replay"` after `"next-signal-id"`.

### Step 6: the CLI tests
**File:** `engine/tests/test_lab_panel_cli.py` (new)
**Change:** Every test drives `cli.main(["lab", "--db", <tmp>, ...])` against a tmp lab DB seeded
with `seed()`, so N is non-zero and its constancy means something. Synthetic stores are a
`manifest.json` per tmp directory, with `research.load_store` replaced by a loader keyed on the
directory, the same seam `test_lab_survivorship.py:122-138` uses. Signal files are real files in a
tmp git repo, so `registry_problem` runs real `git`. Most tests replace `panel.build_frame`,
`panel.signal_scorer` and `panel.measure` with canned readings. Phase 1's real evaluator skips any
month with fewer than `MIN_SCORED = 30` scored names, and `labkit.smoke_market` has 8 members, so
those tests are about what the CLI selects, refuses and records. Two tests run phase 1's real
`build_frame`/`measure` on a 40-member synthetic market from 2005 to `DEV_END`: one checks the
recorded rows equal a direct call, the other that `--jobs 2` records what `--jobs 1` does. One
test pins `panel.RULE_ID == panel_verdict.RULE_ID` and `panel.ERAS == store.PANEL_ERAS`, the two
pairs phases 1 and 2 each define (Decisions). No test opens `/home/miftah/seer/lab/lab.sqlite`.
**Code:**
```python
"""``lab panel``, ``lab panel-map`` and ``lab next-signal-id`` (SERA_SIGNAL_PANEL_PLAN.md phase 3).

What is proven here is the command, not the statistics (``test_lab_panel.py`` owns those): which
signals it measures, what it refuses before a store loads, that the two stores are never alive at
once, that a panel is recorded on both stores in one transaction or not at all, that a repeat loads
nothing, and that none of it moves the lab's N, the luck gate's N or the test-window looks.
"""

from __future__ import annotations

import json
import subprocess
import weakref
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from labkit import BASE_ETFS, smoke_data, smoke_history

from seer_engine import cli, dates, research
from seer_engine.backtest.dev import DEV_END
from seer_engine.backtest.market import Market, Membership
from seer_engine.lab import panel, signal, store
from seer_engine.lab.seed import seed

SV = research.SURVIVORSHIP_PURPOSE
# 2005, not 2007: F4's screen needs 253 bars, so a 2007 start gives the pre-2009 era exactly
# panel.MIN_ERA_MONTHS (12) months, one short of losing it. 2005 gives about 36.
WIDE_FIRST = date(2005, 1, 3)


# ---- fixtures ----------------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, check=True, capture_output=True)


def _last_close(history, market, pool, data_date):
    return {s: float(history[s].close[-1]) for s in pool if s in history and len(history[s].close)}


def _low_close(history, market, pool, data_date):
    return {s: -float(history[s].close[-1]) for s in pool if s in history and len(history[s].close)}


def _signal(sid: str, name: str, score=_last_close) -> signal.Signal:
    return signal.Signal(
        id=sid, name=name, family="test-family", source_kind="knowledge", source_ref="",
        hypothesis="h", expected_failure="f", lookback=1, score=score,
    )


@pytest.fixture()
def lab(tmp_path):
    path = tmp_path / "lab.sqlite"
    conn = store.connect(path)
    seed(conn)
    yield conn, path
    conn.close()


@pytest.fixture()
def signals(tmp_path, monkeypatch):
    """Three committed signal files in a tmp git repo; ``signal.discover`` answers with them."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "test")
    found: dict[str, tuple[signal.Signal, Path]] = {}
    for sid, name, score in (
        ("S0901", "Recent winners", _last_close),
        ("S0902", "Cheap names", _low_close),
        ("S0903", "Recent winners again", _last_close),
    ):
        path = repo / f"s{sid[1:]}_test.py"
        path.write_text(f"# {sid}\n", encoding="utf-8")
        found[sid] = (_signal(sid, name, score), path)
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "signals")
    monkeypatch.setattr(signal, "discover", lambda: dict(found))
    return repo, found


def _dirs(tmp_path: Path, dev_manifest=None, sv_manifest=None) -> tuple[Path, Path]:
    d, s = tmp_path / "dev-store", tmp_path / "sv-store"
    d.mkdir(exist_ok=True)
    s.mkdir(exist_ok=True)
    (d / "manifest.json").write_text(json.dumps({"fingerprint": "smoke"} if dev_manifest is None else dev_manifest))
    (s / "manifest.json").write_text(json.dumps(
        {"fingerprint": "smoke-sv", "purpose": SV} if sv_manifest is None else sv_manifest
    ))
    return d, s


def _sv(data: research.ResearchData, fingerprint: str = "smoke-sv") -> research.ResearchData:
    return replace(data, fingerprint=fingerprint, price_fingerprint=fingerprint,
                   manifest={"purpose": SV}, purpose=SV)


def _loader(by_dir, alive_at_load=None):
    """research.load_store, keyed on the directory; a fresh object per call so a test can watch
    the previous store die before the next is handed out."""
    returned: list[weakref.ref] = []

    def load(store_dir, **kw):
        got = by_dir[Path(store_dir)]
        if isinstance(got, BaseException):
            raise got
        if alive_at_load is not None:
            alive_at_load.append(sum(1 for r in returned if r() is not None))
        fresh = replace(got)
        returned.append(weakref.ref(fresh))
        return fresh

    return load


def _boom(*a, **k):
    raise AssertionError("a store must not be loaded here")


def _reading(slope: float, picks: str) -> panel.PanelReading:
    stats = tuple(
        panel.EraStats(era=era, months=months, mean_pool=400.0, mean_scored=380.0, ic_mean=0.02,
                       ic_t=2.1, spread_top=0.03, spread_t=1.8, fm_slope=slope, fm_t=2.5,
                       top_turnover=0.4)
        for era, months in zip(panel.ERAS, (237, 168, 69))
    )
    return panel.PanelReading(stats=stats, picks_hash=picks, dropped_exits=0)


@pytest.fixture()
def fake_panel(monkeypatch):
    """Canned readings per signal id; every measure call is logged as (store fingerprint, id)."""
    readings = {"S0901": _reading(0.004, "a" * 64), "S0902": _reading(0.001, "b" * 64),
                "S0903": _reading(0.002, "a" * 64)}
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(panel, "build_frame", lambda data: ("frame", str(data.fingerprint)))
    monkeypatch.setattr(panel, "signal_scorer", lambda sig: sig.id)

    def measure(frame, scorer, *, mode="score"):
        calls.append((frame[1], scorer))
        return readings[scorer]

    monkeypatch.setattr(panel, "measure", measure)
    return readings, calls


@pytest.fixture()
def stores(tmp_path, monkeypatch):
    d, s = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store", _loader({d: smoke_data(), s: _sv(smoke_data())}))
    return d, s


def _lab(path: Path, *argv: str) -> int:
    return cli.main(["lab", "--db", str(path), *argv])


def _panel(path: Path, d: Path, s: Path, *argv: str) -> int:
    return _lab(path, "panel", *argv, "--store", str(d), "--sv-store", str(s))


def _results(conn) -> list[tuple]:
    return [tuple(r) for r in conn.execute(
        "SELECT signal_id, store_role, store_fingerprint, era FROM panel_results ORDER BY 1, 2, 4"
    )]


def _signal_ids(conn) -> list[str]:
    return [r[0] for r in conn.execute("SELECT id FROM panel_signals ORDER BY id")]


def _counts(conn) -> tuple[int, int, int]:
    return store.dev_trial_count(conn), store.gate(conn).n, store.test_looks(conn)


# ---- lab panel: recording ----------------------------------------------------------------------


def test_panel_records_both_stores_and_every_era_once(lab, signals, stores, fake_panel, capsys):
    conn, path = lab
    d, s = stores
    before = _counts(conn)
    assert _panel(path, d, s, "S0901") == 0
    out = capsys.readouterr().out
    assert _signal_ids(conn) == ["S0901"]
    assert _results(conn) == sorted(
        [("S0901", "dev", "smoke", era) for era in panel.ERAS]
        + [("S0901", "survivorship", "smoke-sv", era) for era in panel.ERAS],
        key=lambda r: (r[0], r[1], r[3]),
    )
    row = conn.execute(
        "SELECT months, ic_mean, ic_t, spread_top, spread_t, fm_slope, fm_t FROM panel_results "
        "WHERE signal_id = 'S0901' AND store_role = 'dev' AND era = 'all'"
    ).fetchone()
    assert tuple(row) == (237, 0.02, 2.1, 0.03, 1.8, 0.004, 2.5)
    sha = conn.execute("SELECT source_sha FROM panel_signals WHERE id = 'S0901'").fetchone()[0]
    assert sha == signal.source_sha(signals[1]["S0901"][1])
    assert _counts(conn) == before
    assert "1 signal(s) recorded" in out
    assert f"Lab N (dev trials): {before[0]} before, {before[0]} after" in out
    assert f"luck gate N = {before[1]} before, {before[1]} after" in out


def test_a_repeat_loads_no_store_and_records_nothing(lab, signals, stores, fake_panel, monkeypatch, capsys):
    conn, path = lab
    d, s = stores
    assert _panel(path, d, s, "S0901") == 0
    rows = _results(conn)
    monkeypatch.setattr(research, "load_store", _boom)
    capsys.readouterr()
    assert _panel(path, d, s, "S0901") == 0
    out = capsys.readouterr().out
    assert "already panelled" in out and "nothing to measure" in out
    assert _results(conn) == rows


def test_the_real_evaluator_records_what_it_measures(lab, signals, tmp_path, monkeypatch):
    conn, path = lab
    d, s = _dirs(tmp_path, {"fingerprint": "wide"}, {"fingerprint": "wide-sv", "purpose": SV})
    dev_data, sv_data = _wide_data(), _sv(_wide_data(), "wide-sv")
    monkeypatch.setattr(research, "load_store", _loader({d: dev_data, s: sv_data}))
    assert _panel(path, d, s, "S0901") == 0
    sig = signals[1]["S0901"][0]
    for role, data in (("dev", dev_data), ("survivorship", sv_data)):
        want = panel.measure(panel.build_frame(data), panel.signal_scorer(sig))
        got = conn.execute(
            "SELECT era, months, fm_slope, picks_hash FROM panel_results "
            "WHERE signal_id = 'S0901' AND store_role = ? ORDER BY era", (role,)
        ).fetchall()
        assert sorted((r[0], r[1], r[2], r[3]) for r in got) == sorted(
            (e.era, e.months, e.fm_slope, want.picks_hash) for e in want.stats
        )
        assert any(r[0] == "all" for r in got)


def test_jobs_change_only_the_time(signals, tmp_path, monkeypatch):
    d, s = _dirs(tmp_path, {"fingerprint": "wide"}, {"fingerprint": "wide-sv", "purpose": SV})
    monkeypatch.setattr(research, "load_store",
                        _loader({d: _wide_data(), s: _sv(_wide_data(), "wide-sv")}))
    got = []
    for jobs in ("1", "2"):
        path = tmp_path / f"lab-{jobs}.sqlite"
        conn = store.connect(path)
        assert _panel(path, d, s, "S0901", "S0902", "--jobs", jobs) == 0
        got.append([tuple(r) for r in conn.execute(
            "SELECT signal_id, store_role, era, months, ic_mean, spread_top, fm_slope, fm_t, "
            "picks_hash FROM panel_results ORDER BY 1, 2, 3"
        )])
        conn.close()
    assert got[0] == got[1] and got[0]


def test_the_two_stores_are_never_alive_at_once(lab, signals, tmp_path, fake_panel, monkeypatch):
    conn, path = lab
    d, s = _dirs(tmp_path)
    alive: list[int] = []
    monkeypatch.setattr(research, "load_store",
                        _loader({d: smoke_data(), s: _sv(smoke_data())}, alive))
    assert _panel(path, d, s, "S0901", "S0902") == 0
    assert alive == [0, 0]


def test_the_frame_is_built_once_per_store_and_every_signal_measured_on_both(lab, signals, stores, fake_panel):
    conn, path = lab
    d, s = stores
    _, calls = fake_panel
    assert _panel(path, d, s, "S0901", "S0902") == 0
    assert calls == [("smoke", "S0901"), ("smoke", "S0902"), ("smoke-sv", "S0901"), ("smoke-sv", "S0902")]


def test_a_survivorship_store_that_fails_after_the_dev_store_leaves_no_half_record(lab, signals, tmp_path, fake_panel, monkeypatch):
    conn, path = lab
    d, s = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store",
                        _loader({d: smoke_data(), s: ValueError("a file's sha256 does not match")}))
    before = _counts(conn)
    assert _panel(path, d, s, "S0901") == 2
    assert _signal_ids(conn) == [] and _results(conn) == []
    assert _counts(conn) == before


def test_an_unmeasurable_signal_is_printed_not_recorded_and_exits_2(lab, signals, stores, fake_panel):
    conn, path = lab
    d, s = stores
    readings, _ = fake_panel
    readings["S0902"] = panel.PanelReading(stats=(), picks_hash="c" * 64, dropped_exits=0)
    assert _panel(path, d, s, "S0901", "S0902") == 2
    assert _signal_ids(conn) == ["S0901"]


def test_pending_measures_only_committed_signals_with_no_panel(lab, signals, stores, fake_panel, capsys):
    conn, path = lab
    d, s = stores
    repo, found = signals
    _, calls = fake_panel
    assert _panel(path, d, s, "S0901") == 0
    draft = repo / "s0904_draft.py"
    draft.write_text("# draft\n", encoding="utf-8")
    found["S0904"] = (_signal("S0904", "A draft"), draft)
    calls.clear()
    capsys.readouterr()
    assert _panel(path, d, s, "--pending") == 0
    out = capsys.readouterr().out
    assert {sid for _, sid in calls} == {"S0902", "S0903"}
    assert "skipped S0904" in out
    assert _signal_ids(conn) == ["S0901", "S0902", "S0903"]


# ---- lab panel: refusals (exit 2, nothing loaded, nothing recorded) -----------------------------


def test_a_named_signal_that_is_not_committed_exits_2_and_records_nothing(lab, signals, stores, monkeypatch):
    conn, path = lab
    d, s = stores
    repo, found = signals
    monkeypatch.setattr(research, "load_store", _boom)
    draft = repo / "s0904_draft.py"
    draft.write_text("# draft\n", encoding="utf-8")
    found["S0904"] = (_signal("S0904", "A draft"), draft)
    assert _panel(path, d, s, "S0904") == 2                      # untracked
    found["S0901"][1].write_text("# S0901, edited\n", encoding="utf-8")
    assert _panel(path, d, s, "S0901") == 2                      # tracked, modified
    _git(repo, "add", found["S0901"][1].name)
    assert _panel(path, d, s, "S0901") == 2                      # staged, not committed
    assert _panel(path, d, s, "S0902", "S0904") == 2             # one bad name refuses the run
    assert _signal_ids(conn) == [] and _results(conn) == []


def test_a_signal_changed_after_its_panel_is_refused(lab, signals, stores, fake_panel, tmp_path, monkeypatch):
    conn, path = lab
    d, s = stores
    repo, found = signals
    assert _panel(path, d, s, "S0901") == 0
    found["S0901"][1].write_text("# S0901, a different idea\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "edit")
    d2, s2 = tmp_path / "dev-2", tmp_path / "sv-2"
    for p, m in ((d2, {"fingerprint": "smoke-2"}), (s2, {"fingerprint": "smoke-sv", "purpose": SV})):
        p.mkdir()
        (p / "manifest.json").write_text(json.dumps(m))
    monkeypatch.setattr(research, "load_store", _boom)
    assert _panel(path, d2, s2, "S0901") == 2
    assert _signal_ids(conn) == ["S0901"]


def test_an_unknown_signal_or_no_selection_exits_2(lab, signals, stores, monkeypatch):
    _, path = lab
    d, s = stores
    monkeypatch.setattr(research, "load_store", _boom)
    assert _panel(path, d, s, "S0999") == 2
    assert _panel(path, d, s) == 2
    assert _panel(path, d, s, "S0901", "--pending") == 2


@pytest.mark.parametrize(
    ("dev_manifest", "sv_manifest"),
    [
        ({"fingerprint": "t", "window_name": "test", "window_start": "2015-10-19",
          "window_end": "2026-11-13"}, None),                                   # a test-window store
        ({"fingerprint": "smoke-sv", "purpose": SV}, None),                     # the check store as --store
        (None, {"fingerprint": "smoke-sv"}),                                    # check store unmarked
        (None, {"fingerprint": "u", "purpose": research.UNIVERSE_PURPOSE}),     # another marked store
    ],
)
def test_a_wrong_store_exits_2_before_loading(lab, signals, tmp_path, monkeypatch, dev_manifest, sv_manifest):
    conn, path = lab
    d, s = _dirs(tmp_path, dev_manifest, sv_manifest)
    monkeypatch.setattr(research, "load_store", _boom)
    assert _panel(path, d, s, "S0901") == 2
    assert _signal_ids(conn) == [] and _results(conn) == []


def test_a_missing_survivorship_store_or_the_same_store_twice_exits_2(lab, signals, tmp_path, monkeypatch):
    conn, path = lab
    d, _ = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store", _boom)
    assert _panel(path, d, tmp_path / "nowhere", "S0901") == 2
    assert _panel(path, d, d, "S0901") == 2
    assert _signal_ids(conn) == [] and _results(conn) == []


def test_a_dev_store_whose_prices_are_unknown_is_refused_by_d10(lab, signals, tmp_path, fake_panel, monkeypatch):
    conn, path = lab
    d, s = _dirs(tmp_path)
    monkeypatch.setattr(research, "load_store",
                        _loader({d: replace(smoke_data(), price_fingerprint=None), s: _sv(smoke_data())}))
    assert _panel(path, d, s, "S0901") == 2
    assert _results(conn) == []


# ---- lab panel-map -----------------------------------------------------------------------------


def test_panel_map_prints_an_empty_state_and_writes_nothing(lab, capsys):
    conn, path = lab
    before = _counts(conn)
    assert _lab(path, "panel-map") == 0
    out = capsys.readouterr().out
    assert "no panel recorded yet" in out
    assert f"luck gate N = {before[1]} before, {before[1]} after" in out
    assert _counts(conn) == before


def test_panel_map_ranks_by_controlled_slope_with_verdict_and_twin(lab, signals, stores, fake_panel, capsys):
    conn, path = lab
    d, s = stores
    assert _panel(path, d, s, "S0901", "S0902") == 0
    assert _panel(path, d, s, "S0903") == 0          # same pick set as S0901, recorded later
    before = _counts(conn)
    rows = _results(conn)
    capsys.readouterr()
    assert _lab(path, "panel-map") == 0
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if ln[:6].strip().isdigit()]
    assert [ln.split()[1] for ln in lines] == ["S0901", "S0903", "S0902"]
    assert all(ln.split()[6] in ("clears", "no") for ln in lines)
    assert "S0901" in lines[1].split()[7:8]          # S0903's twin-of column
    assert "3 of 3 panel(s) shown" in out
    assert _counts(conn) == before and _results(conn) == rows


def test_panel_map_top_and_kind(lab, signals, stores, fake_panel, capsys):
    _, path = lab
    d, s = stores
    assert _panel(path, d, s, "S0901", "S0902") == 0
    capsys.readouterr()
    assert _lab(path, "panel-map", "--top", "1") == 0
    out = capsys.readouterr().out
    assert "1 of 2 panel(s) shown" in out and "S0902" not in out
    assert _lab(path, "panel-map", "--kind", "replay") == 0
    assert "no replay panel recorded yet" in capsys.readouterr().out


# ---- lab next-signal-id ------------------------------------------------------------------------


def test_next_signal_id_is_one_past_the_record_and_the_files(lab, signals, stores, fake_panel, monkeypatch, capsys):
    conn, path = lab
    d, s = stores
    capsys.readouterr()
    assert _lab(path, "next-signal-id") == 0
    assert capsys.readouterr().out.strip() == "S0904"            # files only
    assert _panel(path, d, s, "S0903") == 0
    monkeypatch.setattr(signal, "discover", lambda: {})
    capsys.readouterr()
    assert _lab(path, "next-signal-id") == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "S0904"                       # the record alone
    assert "Lab N (dev trials)" in captured.err


def test_next_signal_id_on_an_empty_lab_is_s0001(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(signal, "discover", lambda: {})
    assert _lab(tmp_path / "lab.sqlite", "next-signal-id") == 0
    assert capsys.readouterr().out.strip() == "S0001"


# ---- phase 1 and phase 2 name the rule and the eras once each ----------------------------------


def test_the_record_and_the_evaluator_agree_on_the_rule_and_the_eras():
    """Phase 2 duplicates ``panel.RULE_ID`` and ``panel.ERAS`` so it need not import phase 1; this
    is the first module that sees both, so the pin lives here. A drift would record rows under a
    rule the verdict never reads, or an era the table's CHECK refuses."""
    from seer_engine.lab import panel_verdict

    assert panel.RULE_ID == panel_verdict.RULE_ID
    assert panel.ERAS == store.PANEL_ERAS


# ---- argparse ----------------------------------------------------------------------------------


@pytest.mark.parametrize("argv", [["lab", "--help"], ["lab", "panel", "--help"],
                                  ["lab", "panel-map", "--help"], ["lab", "next-signal-id", "--help"]])
def test_help_formats(argv, capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(argv)
    assert e.value.code == 0


# ---- the wide synthetic market -----------------------------------------------------------------


def _wide_data() -> research.ResearchData:
    """Forty members priced like labkit's smoke names, 2005 through DEV_END: every one passes F4's
    screen (smoke volume x price is far above its 20M floor), so 40 >= phase 1's MIN_SCORED (30)
    names are scored each month, the top bucket is TOP_MIN (10), and every era has well over
    MIN_ERA_MONTHS (12) months. Built in memory."""
    days = dates.sessions(WIDE_FIRST, DEV_END)
    members = tuple(f"W{k:02d}" for k in range(40))
    symbols = tuple(BASE_ETFS) + members
    history = {sym: smoke_history(sym, k, days) for k, sym in enumerate(symbols)}
    membership = Membership(intervals=tuple((sym, days[0], None) for sym in members))
    market = Market(history=history, membership=membership, fx=((days[0], Decimal("2000")),))
    return replace(smoke_data(), market=market, fingerprint="wide", price_fingerprint="wide")
```
**Impact:** New test file. It runs with `-n 2` alongside the rest. The two real-evaluator tests
build an in-memory market of 56 symbols x about 2,210 sessions, well under 100 MB.

### Step 7: the feature-map entry
**File:** `.claude/skills/verify-seer/features/signal-panel.md` (new)
**Change:** A four-section entry in `lab-cli.md`'s format. Phase 4 appends a `panel-replay`
section to it.
**Code:**
````markdown
# The signal panel (stage one of the lab)

## Sub-features

- `lab panel S0001 [S0002 ...] | --pending [--store DIR] [--sv-store DIR] [--jobs J]`: measures committed signal files (`engine/src/seer_engine/lab/signals/sNNNN_<slug>.py`) on a stock-by-month panel of the dev window, first on the dev store and then on the survivorship-check store, and records each signal's whole-window, pre-2009 and 2009-2015 readings on both stores in one transaction (`panel_signals`, `panel_results`). Per store and era it prints months, rank correlation (IC) and its t, the top bucket's annualised spread over the pool and its t, and the slope after momentum, beta, size and volatility and its t. A repeat prints "already panelled ... not measured again", loads no store and records nothing. `--pending` takes every committed signal with no panel on the dev store and lists an uncommitted file as `skipped`.
- `lab panel-map [--top K] [--kind signal|replay|all]`: every recorded panel ranked by the dev whole-window slope, with the published verdict (`clears` / `no` plus a `why not:` line), its q, the earlier panel it is a twin of, the three eras' spread and the survivorship-check slope. When nothing is recorded it prints "no panel recorded yet". It writes nothing.
- `lab next-signal-id`: the id alone on stdout, one past both the record and the committed signal files. The N line goes to stderr.
- Every one of the three ends with `Lab N (dev trials): X before, X after; luck gate N = G before, G after; test-window looks used: L before, L after`.
- Refused, exit 2, nothing loaded and nothing recorded: an unknown id; a named signal file that is untracked, modified or staged; a signal whose file changed after it was panelled; a dev store that declares the test window or carries a purpose marker; a missing, unmarked or other-purpose survivorship-check store; `--store` equal to `--sv-store`; neither ids nor `--pending`, or both. After the load: a dev store whose prices are not the benchmark's (D10).

## How to get to it (user POV)

The owner sees the panel on `/sera/signals` (phase 6) after a `lab stage`. The CLI is what an exploration session drives: write and commit a signal file, `lab panel` it, read `lab panel-map`.

## Driving it with verify.sh

```sh
$V up --no-web --empty
SV=/home/miftah/seer/engine/.research-sv          # verify.sh exports SEER_RESEARCH_STORE but not SEER_SV_STORE
$V labsql RUN "select count(*) from trials"       # T
$V lab RUN panel S0001 S0002 --sv-store $SV       # minutes: two store loads plus two frames; run in the background
                                                  # two blocks, each with dev and survivorship rows for all, pre2009, 2009-2015
                                                  # "2 signal(s) recorded"; "luck gate N = G before, G after"; exit 0
$V labsql RUN "select signal_id, store_role, era, months, ic_t, spread_t, fm_t from panel_results order by 1, 2, 3"   # 12 rows
$V lab RUN panel S0001 S0002 --sv-store $SV       # seconds: "already panelled", "nothing to measure"; exit 0
$V lab RUN panel-map                              # S0001 and S0002 ranked by slope, verdict and q on each row
$V lab RUN panel-map --kind replay                # "no replay panel recorded yet"
$V lab RUN next-signal-id                         # S0003
$V lab RUN panel S0001 --store /nonexistent --sv-store $SV    # exit 2: no manifest
$V lab RUN panel S0001 --sv-store /nonexistent                # exit 2: the survivorship-check store is required
$V labsql RUN "select count(*) from trials"       # T, unchanged
```

## Gotchas

- `$V lab` starts from `env -i` and does not export `SEER_SV_STORE`. Pass `--sv-store /home/miftah/seer/engine/.research-sv` every time, or the default resolves inside the worktree, where no store exists, and the run is refused.
- Never point `--store` at `engine/.research-test` to "check" the refusal. Use a scratch directory whose `manifest.json` declares `{"window_name": "test", "window_start": "2015-10-19", "window_end": "2026-11-13"}`. The command refuses it from the manifest, and nothing reads the real test store.
- The uncommitted-file refusal is driven by adding an untracked `sNNNN_*.py` (a copy of a seed signal with its id changed) to the checkout under test, running `lab panel` on it, then deleting it. Remove the file before anything else runs: `lab next-signal-id` counts it while it exists.
- A panel is keyed on the dev store's fingerprint. After a dev store change every signal is pending again, which is intended.
- Counts in this file are examples. Read them back with `labsql` (CLAUDE.md, Claim verification).
````
**Impact:** Documentation only.

### Step 8: the feature-map README row
**File:** `.claude/skills/verify-seer/features/README.md:15` (after the `lab-cli.md` row)
**Change:** One row.
**Code:**
```markdown
| The signal panel: `lab panel`, `lab panel-map`, `lab next-signal-id` | [signal-panel.md](signal-panel.md) | lab, labsql | none |
```
**Impact:** Documentation only.

## Principles applied

- Laziness protocol: no new store API, no SQL in `panel_run`, and no new refusal machinery. The phase reuses `registry_problem`, `research.declared_window`/`declared_purpose`, `hardgate.pin_dev_store`, `runner.git_head` and yardstick's fork-pool shape. `panel_run.py` exists only because phase 4 is a second caller of the same load, measure and record steps. Otherwise the code would sit in the handler.
- Boundary discipline: ids, git state and both manifests are checked once, in `select_signals` and `check_stores`, before any store loads. Everything after that trusts the typed `Selection`/`StorePair` and does not re-check purpose or window, apart from the post-load check `load` makes on what `load_store` actually returned.
- Make illegal states unrepresentable: `record()` takes the dev `StoreRun` and the survivorship `StoreRun` together and writes both in one transaction. A one-store record has no call shape. `open_store()` is the only loader, and `measure_stores()` deletes the store and frame before the next load, so no caller can hold both.
- Test behavior, not implementation: every test drives `cli.main` and reads the tables back. The `panel.measure` stub is a seam on phase 1's code, not on the unit under test, and two tests run the real evaluator end to end.
- Prove it works: Proof drives `lab panel` through `verify.sh` on the real dev and survivorship stores against a lab copy, and reads the rows back with `labsql`.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/sera-signal-panel && /home/miftah/seer/engine/.venv/bin/ruff check engine`
**Tests:** `cd /home/miftah/.worktrees/seer/sera-signal-panel && PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest -n 2 engine/tests/test_lab_panel_cli.py engine/tests/test_lab_panel.py engine/tests/test_lab_signals.py engine/tests/test_lab_panel_record.py engine/tests/test_lab_survivorship.py`
**Proof:** `lab panel` measured and recorded the two seed signals on the real dev and survivorship stores in a lab copy, refused every bad input with exit 2 and an unchanged record, and `panel-map` read the result back ranked.
- Harness: `.claude/skills/verify-seer` (`V=.claude/skills/verify-seer/scripts/verify.sh`, run from the worktree root; `$V up --no-web --empty` prints `RUN=`; `SV=/home/miftah/seer/engine/.research-sv`; `SCR` is the session scratchpad directory)
- Feature-map entries: `.claude/skills/verify-seer/features/signal-panel.md`
- Journeys:
  - **J1** · traces R2.1, R4.3 — `$V labsql RUN "select count(*) from trials"` (note T) and `$V lab RUN status` (note the "dev trials" and luck-gate N lines); then `$V lab RUN panel S0001 S0002 --sv-store $SV` (Bash `run_in_background`; minutes); then `$V labsql RUN "select signal_id, store_role, era, months, ic_mean, ic_t, spread_top, spread_t, fm_slope, fm_t from panel_results order by 1, 2, 3"`; then `$V lab RUN panel S0001 S0002 --sv-store $SV` again; then `$V labsql RUN "select count(*) from trials"` and `$V lab RUN status` → passes when the first panel run exits 0 and prints "2 signal(s) recorded" and `luck gate N = G before, G after` with equal numbers; when the query returns, for each of S0001 and S0002 and for both `dev` and `survivorship`, a row for each of `all`, `pre2009` and `2009-2015` (12 rows) with `months` > 0 and non-null `ic_mean`, `ic_t`, `spread_top`, `spread_t`, `fm_slope`, `fm_t`; when the second run exits 0 within seconds, printing "already panelled" twice and "nothing to measure"; and when the trial count still equals T and `lab status` shows the same dev-trial count and luck-gate N as before
  - **J2** · traces R1.2 — `cp engine/src/seer_engine/lab/signals/s0001_*.py engine/src/seer_engine/lab/signals/s0999_verify_draft.py && sed -i 's/"S0001"/"S0999"/' engine/src/seer_engine/lab/signals/s0999_verify_draft.py`; `$V lab RUN panel S0999 --sv-store $SV`; `rm engine/src/seer_engine/lab/signals/s0999_verify_draft.py`; `echo '# verify draft' >> engine/src/seer_engine/lab/signals/s0002_*.py`; `$V lab RUN panel S0002 --sv-store $SV`; `git checkout -- engine/src/seer_engine/lab/signals/`; `$V labsql RUN "select count(*) from panel_results"`; `$V labsql RUN "select id from panel_signals where id = 'S0999'"`; `$V lab RUN next-signal-id`; `git status --porcelain engine/src/seer_engine/lab/signals` → passes when both panel runs exit 2 within seconds, naming the file as "not tracked" or "uncommitted changes" and saying "Nothing was measured or recorded"; when the result count equals J1's 12 and the S0999 query returns no row; when `next-signal-id` prints `S0003`; and when the git status prints nothing
  - **J3** · traces R2.2 — `mkdir -p $SCR/fake-test && echo '{"fingerprint":"x","window_name":"test","window_start":"2015-10-19","window_end":"2026-11-13"}' > $SCR/fake-test/manifest.json`; `$V lab RUN panel S0001 --store $SCR/fake-test --sv-store $SV`; `$V lab RUN panel S0001 --sv-store $SCR/no-such-store`; `$V lab RUN panel S0001 --store $SV --sv-store $SV`; `$V lab RUN panel S0001 --store $SV --sv-store /home/miftah/seer/engine/.research`; `$V labsql RUN "select count(*) from panel_results"` → passes when all four runs exit 2 within seconds, with no "store ... loaded" log line, and the messages read "declares the test window", "survivorship-check store is missing or unreadable", "both name" and "is marked 'survivorship-check'"; and when the count still equals 12
  - **J4** · traces R2.3, R4.3 — `$V lab RUN panel-map`; `$V labsql RUN "select signal_id, fm_slope from panel_results where store_role = 'dev' and era = 'all' order by fm_slope desc"`; `$V lab RUN panel-map --kind replay`; `$V lab RUN panel-map --top 1`; `$V labsql RUN "select count(*) from trials"` → passes when `panel-map` exits 0 and lists S0001 and S0002 in the same order as the query, each row carrying `clears` or `no`, a numeric q and its three era spreads, with a `why not:` line under any `no`, the header naming "Benjamini-Hochberg" and the tail reading "2 of 2 panel(s) shown"; when `--kind replay` prints "no replay panel recorded yet"; when `--top 1` prints only the first-ranked id and "1 of 2 panel(s) shown"; and when every footer shows equal before and after N and luck-gate N, with the trial count still T
  - **J5** · traces R3.2 — `PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest -n 0 -v engine/tests/test_lab_panel_cli.py -k "twin or rule_and_the_eras"` → passes when `test_panel_map_ranks_by_controlled_slope_with_verdict_and_twin` and `test_the_record_and_the_evaluator_agree_on_the_rule_and_the_eras` are both `PASSED`: two recorded panels with the identical pick set print as one ranked pair whose later row names the first in the twin-of column (the printing half of R3.2; phase 2's J3-J5 prove the correction counts them once)
- Neighbor check: argparse and the other lab subcommands, the code most exposed to the three new parsers. `PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab --help`, then `$V lab RUN next-id` and `$V lab RUN status`. Passes when help exits 0 and lists `panel`, `panel-map` and `next-signal-id`, `next-id` prints an `M` id and `status` exits 0.
- Cost: no paid call. J1's first run loads both research stores (about 12 s and 1 GB each, one at a time) and builds two panel frames. Run it in the background and do not start a second store-loading command alongside it (invariant 6).
**Exit criteria:** On a lab copy with the real stores, `lab panel S0001 S0002` records 2 signals x 2 stores x 3 eras, a repeat records nothing and loads nothing, an uncommitted signal and a non-dev or missing store each exit 2 with the record unchanged, `panel-map` ranks the two by slope with verdicts, and N and the luck gate's N are equal before and after every run. `test_lab_panel_cli.py` passes, and `ruff check engine` is clean.

## Handoffs

- **Phase 4 (`panel-replay`)** (reconciled): reuse `panel_run.Subject` with `mode="picks"`, `StoreRun`, `check_stores`, `open_store` (load each store through it; do not repeat the D10 pin or the fingerprint check), `has_whole_window`, `record`, `Counts`/`footer`. Phase 4 runs its own grouped store loop rather than `measure_stores`, for the reasons in its Interface Contract. Build the replay's `store.PanelSignalRow` with `kind="replay"`, `id=<candidate id>` and `method_id=<method id>`. Insert the `panel-replay` parser after the `next-signal-id` parser (Step 3), the handler after `_next_signal_id` (Step 4), and the `_HANDLERS` entry after `"next-signal-id"`. Append its section to `features/signal-panel.md`. `format_map`'s replay empty state already names `lab panel-replay`.
- **Phase 2 (confirmed by the reconciler)**: (a) `insert_panel_signal`/`insert_panel_results` do not commit; `record()` wraps both in `begin_immediate` + `with conn:`. (b) Rows from `panel_signals`/`panel_results` are dicts readable by column name. (c) `panel_verdict.published` is called with an explicit `dev_fingerprint`, the one on which the most recent dev panel was measured (`panel_run.panel_map`); phase 2's snapshot uses `current_dev_fingerprint`, the same rule, so the site and the CLI agree. (d) Resolved: `insert_panel_results` skips a repeated primary key and returns the number inserted, so a re-measure after a dev store change, with the survivorship store unchanged, records the new dev rows and skips the existing survivorship rows. `insert_panel_signal` returns False for the same id and sha.
- **R2.3's correction itself** (Benjamini-Hochberg over distinct pick sets, twin collapse R3.2) is phase 2's `published`. This phase only prints it, and J4 proves the print.
- **Phase 7**: `CLAUDE.md` (The lab: "Get the next free signal id with `lab next-signal-id`") and the skills name these three commands and `--sv-store`. Confirmed: `lab next-signal-id` counts committed-but-unpanelled signal files, so no `ls` workaround is needed. `lab panel-map`'s verdict column reads `clears` or `no`, with a `why not:` line under a `no`; its empty replay state reads "no replay panel recorded yet".
- No criterion is left untraced.

## Rollback

Revert this phase's commit. It adds `lab/panel_run.py`, the test file and the feature-map entry, and touches only additive blocks of `commands/lab.py` and one README row. Panel rows already recorded in a lab DB stay; they are append-only and phase 2's reader ignores nothing. Phase 4 must be reverted first if it has landed, because it imports `panel_run`.
