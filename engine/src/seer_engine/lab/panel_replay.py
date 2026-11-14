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
