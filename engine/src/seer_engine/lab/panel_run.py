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
