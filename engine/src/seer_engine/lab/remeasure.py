"""``lab remeasure <method>``: recover the DSR inputs of dev trials recorded before they were kept.

The lab's 56 lab-method dev trials predate the ``trial_moments`` table, so the four numbers a
re-evaluation needs -- the daily Sharpe, the number of returns, the skew and the kurtosis -- were
computed, used once and discarded. This module gets them back for one method at a time, on demand
(plan decision D4), by re-running that method's recorded variants on the dev window and proving
the re-run is the same measurement before it writes anything.

**What it writes:** ``trial_moments`` rows, and nothing else. There is no INSERT, UPDATE or DELETE
against ``trials`` or ``methods`` anywhere in this module; no status moves; no pre-registration is
written. ``trials`` stays append-only and every recorded ``dsr``, ``eligible``, ``failed`` and
``n_trials_at_run`` is left exactly as it is.

**Why a re-run can be trusted.** Two checks, both asserted, both aborting the whole command before
a single row is written:

1. the freshly measured annualized Sharpe reproduces the recorded ``trials.sharpe`` column to
   ``SHARPE_TOL`` relative. This asks the prior question -- has the research store, the method file
   or the engine changed since the trial ran? -- and it is the one a failure should name first.
2. the DSR recomputed from the fresh moments, at the trial's **recorded** ``n_trials_at_run`` and
   the **reconstructed** ``var_trials`` of its run, reproduces the recorded ``trials.dsr`` to
   ``DSR_TOL``. This is the phase's justification: a re-run that does not land on the recorded
   verdict is not the measurement that produced it, and backfilling it would launder a different
   number into the row's history.

**Reconstructing ``var_trials``.** It was never recorded, and it is still recoverable exactly.
``runner.trial_rows`` computes it as ``statistics.variance(prior + new_sharpes)`` where ``prior``
is ``store.dev_daily_sharpes`` -- the ``trials.sharpe`` column of every dev trial that existed --
and ``new_sharpes`` is the batch's own measured daily Sharpes. ``trials.n`` is a monotone
AUTOINCREMENT and ``run_method`` writes a whole batch inside one ``BEGIN IMMEDIATE``, so a batch's
trial numbers are contiguous and "every dev trial that existed then" is exactly "every dev row with
a lower ``n``". ``batches_of`` rebuilds that list from the column and checks it against the recorded
``n_trials_at_run`` before handing it back; the batch's own daily Sharpes come from the re-run,
which is what the original run used too. ``statistics.variance`` sums in exact Fraction arithmetic,
so the concatenation order is immaterial.

**The test window.** This command cannot spend a look, by construction rather than by care:

- a method with any ``window='test'`` trial is refused in ``preflight``, before a store is opened
  -- the mirror of ``runner.run_test`` refusing a dev store;
- the caller hands ``research.load_store`` no window, so it defaults to ``DEV_WINDOW`` and refuses
  a test store by name before reading a byte (``research.load_store``'s docstring);
- ``measure`` refuses a loaded store whose window is not ``research.DEV_WINDOW``;
- ``dev.run_registry`` is called with no ``window`` keyword, and neither ``measure`` nor
  ``remeasure`` has a ``window`` parameter with which to pass one.
"""

from __future__ import annotations

import logging
import math
import re
import sqlite3
import statistics
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.book_runner import TRADING_DAYS
from seer_engine.backtest.dev import Candidate, DevRow
from seer_engine.backtest.registry import REGISTRY
from seer_engine.commands.backtest_dev import daily_moments, registry_problem
from seer_engine.lab import npolicy, store
from seer_engine.lab.method import METHOD_ID, Method, config_digest, source_sha
from seer_engine.sim.contributions import OWNER_MONTHLY

log = logging.getLogger(__name__)

# The freshly measured annualized Sharpe against the recorded column. Same code, same store, same
# inputs: in practice this is bit-identical, and the tolerance exists only so a numpy or libm
# version bump in the last ulp does not read as a changed measurement.
#
# **Relative, deliberately, and the reason matters because phase 9's seed check is ABSOLUTE at
# 1e-6 and a reader will otherwise think one of the two is a mistake.** These values came out of
# the engine as full-precision IEEE doubles and went straight into `trials.sharpe`, so the only
# expected difference is a last-ulp wobble -- an error proportional to the magnitude, which is
# exactly the shape a relative bound has. Phase 9's 54 P7a seed rows did not come from the engine:
# they were imported from a CSV written to six decimal places, so their error source is decimal
# rounding, whose bound (5e-7) is ABSOLUTE and independent of magnitude. Same intent, two
# different error sources, two correctly different shapes of tolerance.
SHARPE_TOL = 1e-9  # relative -- full-precision engine floats; ulp-scaled error

# The recomputed DSR against the recorded column. The plan's mandated bar. Absolute because the
# DSR is a probability in [0, 1]: a relative bound would be meaninglessly tight near 0 and
# meaninglessly loose near 1.
DSR_TOL = 1e-6  # absolute


def _g(x: float | int | None) -> str:
    return "-" if x is None else f"{x:.12g}"


def _e(x: float | None) -> str:
    return "-" if x is None else f"{x:.3e}"


# --------------------------------------------------------------------------- what a re-run yields


@dataclass(frozen=True)
class Batch:
    """One ``lab run``'s dev trials and the lab-wide state they were deflated against.

    ``prior_sharpes`` is the daily Sharpe (``trials.sharpe`` / sqrt(252)) of every dev trial that
    preceded this batch, in trial-number order -- that is, ``store.dev_daily_sharpes`` as it read
    the instant before the batch was inserted.
    """

    run_at: str
    n_at_run: int
    trials: tuple[sqlite3.Row, ...]  # this batch's dev trials, by ``n``
    prior_sharpes: tuple[float, ...]


@dataclass(frozen=True)
class Reproduced:
    """One recorded trial, re-measured: its fresh moments beside what the lab recorded."""

    trial_n: int
    candidate_id: str
    n_at_run: int
    t: int
    sr_daily: float
    skew: float
    kurt: float
    var_trials: float | None
    recorded_sharpe: float | None
    measured_sharpe: float | None
    recorded_dsr: float | None
    recomputed_dsr: float | None

    @property
    def sharpe_delta(self) -> float | None:
        if self.recorded_sharpe is None or self.measured_sharpe is None:
            return None
        return abs(self.measured_sharpe - self.recorded_sharpe)

    @property
    def sharpe_ok(self) -> bool:
        delta = self.sharpe_delta
        if delta is None or self.recorded_sharpe is None:
            return False
        return delta <= SHARPE_TOL * max(abs(self.recorded_sharpe), 1.0)

    @property
    def dsr_delta(self) -> float | None:
        if self.recorded_dsr is None or self.recomputed_dsr is None:
            return None
        return abs(self.recomputed_dsr - self.recorded_dsr)

    @property
    def dsr_ok(self) -> bool:
        delta = self.dsr_delta
        return delta is not None and delta <= DSR_TOL

    @property
    def ok(self) -> bool:
        return self.sharpe_ok and self.dsr_ok


@dataclass(frozen=True)
class Plan:
    """What ``remeasure`` would do, decided from the database alone: no store, no backtest."""

    method_id: str
    batches: tuple[Batch, ...]
    candidates: tuple[Candidate, ...]  # the variants to re-run, in trial order
    missing: tuple[int, ...]  # trial numbers with no trial_moments row
    present: tuple[int, ...]  # trial numbers that already have one

    @property
    def nothing_to_do(self) -> bool:
        return not self.missing


@dataclass(frozen=True)
class Report:
    """What one ``lab remeasure`` did."""

    method_id: str
    measured: tuple[Reproduced, ...]
    written: tuple[int, ...]
    skipped: tuple[int, ...]


# --------------------------------------------------------------------------- refusals


def resolve_method(method_id: str) -> tuple[Method, Path]:
    """``(METHOD, its file)`` for a lab method id (``store.LabError`` otherwise).

    ``H-*`` ids -- the P7a seed families -- are refused *here* by shape, because they have no
    method file: their candidates live in the frozen ``backtest/registry.py``, not in
    ``lab/methods/``. They are not unreachable. ``seed_preflight`` below takes them, re-runs them
    out of the REGISTRY and verifies the re-run against the six metrics the lab recorded, because
    their ``dsr`` is NULL by construction (``lab/seed.py:136``) and cannot be the check.
    """
    from seer_engine.lab.method import discover

    if METHOD_ID.fullmatch(method_id) is None:
        raise store.LabError(
            f"{method_id!r} is not a lab method id; `lab remeasure` takes a method like M0022. "
            f"For the P7a seed families, name them instead: `lab remeasure H-P7A` re-measures all "
            f"54 seed trials out of the frozen registry, and `lab remeasure H-P7A-F9` one family"
        )
    methods = discover()
    if method_id not in methods:
        raise store.LabError(
            f"no method file for {method_id} in seer_engine/lab/methods/. `lab remeasure` re-runs "
            f"the committed method file, not a database row. Known: {', '.join(methods) or '(none)'}"
        )
    return methods[method_id]


def batches_of(conn: sqlite3.Connection, trials: Sequence[sqlite3.Row]) -> tuple[Batch, ...]:
    """``trials`` (one method's dev rows, by ``n``) grouped into the ``lab run`` batches that
    wrote them, each carrying the daily Sharpes of every dev trial that preceded it.

    Two checks stand between the recorded rows and the reconstruction, and either one refuses:

    1. a batch's trial numbers are contiguous. One ``lab run`` writes its whole batch inside one
       ``BEGIN IMMEDIATE`` transaction (``runner.run_method``), so a gap means the rows were not
       written by one run and "what existed then" cannot be read off ``n``.
    2. ``1 <= n_trials_at_run <= count(dev trials with n < the batch's first n) + len(batch)``.
       The upper bound is the number of looks that existed when the batch was judged, which is
       exactly what the ``all-trials`` policy resolves to and is the ceiling of every other
       policy (``methods`` is ``max(distinct methods, ceil(participation ratio))`` and
       ``effective`` is ``max(2, round(participation ratio))``, and neither counts more than one
       look per row). A recorded N above it cannot describe this batch.

       **This was an equality until 2026-10-08** and had to stop being one when
       ``store.DSR_POLICY`` moved to ``"methods"`` (lab-realistic-gate R1): the row-count
       expression is the all-trials projection, so every batch recorded under any other policy
       would be refused by a guard that is testing the policy rather than the batch. The quantity
       this function actually reconstructs -- ``prior_sharpes``, and through it ``var_trials`` --
       is read from the rows with ``n < first`` and never from ``n_trials_at_run``, so widening
       the bound loses nothing: the recorded N is carried through verbatim into the rebuilt
       ``MomentsRow``, and ``remeasure`` already refuses and writes nothing when the DSR it
       recomputes from it does not reproduce the recorded one (``SHARPE_TOL``/``DSR_TOL``).
       ``npolicy.DSR_MIN_N`` widens the ceiling on the degenerate one-trial lab, where
       ``effective`` floors at 2 and the row count is 1.
    """
    groups: dict[tuple[str, int], list[sqlite3.Row]] = {}
    for row in trials:
        groups.setdefault((str(row["run_at"]), int(row["n_trials_at_run"])), []).append(row)
    out: list[Batch] = []
    for (run_at, n_at_run), group in groups.items():
        method_id = str(group[0]["method_id"])
        ns = [int(r["n"]) for r in group]
        first = ns[0]
        if ns != list(range(first, first + len(ns))):
            raise store.LabError(
                f"{method_id}: the dev trials {ns} recorded at {run_at} are not contiguous, so the "
                f"batch that deflated them cannot be reconstructed from the trial numbers. "
                f"Nothing is backfilled"
            )
        before = int(
            conn.execute(
                "SELECT count(*) FROM trials WHERE window = 'dev' AND n < ?", (first,)
            ).fetchone()[0]
        )
        ceiling = max(before + len(ns), npolicy.DSR_MIN_N)
        if not 1 <= n_at_run <= ceiling:
            raise store.LabError(
                f"{method_id}: trial #{first} records N = {n_at_run}, but only {before} dev "
                f"trials precede it and its batch holds {len(ns)}, so at most {ceiling} looks "
                f"existed when it was judged. The recorded N does not describe this batch, so "
                f"the var_trials it was deflated by cannot be reconstructed honestly. "
                f"Nothing is backfilled"
            )
        prior = tuple(
            float(r[0]) / math.sqrt(TRADING_DAYS)
            for r in conn.execute(
                "SELECT sharpe FROM trials WHERE window = 'dev' AND n < ? AND sharpe IS NOT NULL "
                "ORDER BY n",
                (first,),
            )
        )
        out.append(Batch(run_at=run_at, n_at_run=n_at_run, trials=tuple(group), prior_sharpes=prior))
    return tuple(out)


def preflight(
    conn: sqlite3.Connection, method: Method, path: Path, *, require_commit: bool = True
) -> Plan:
    """Every refusal ``lab remeasure`` makes from the database and the file alone.

    Nothing here opens a research store, runs a backtest or writes a row, and the test-window
    refusal is made first so a method that has had its look is told so before anything is loaded.
    ``require_commit=False`` skips the git check on the method file; it never relaxes the
    ``source_sha`` comparison, which is the stronger of the two.
    """
    row = store.get_method(conn, method.id)
    if row is None:
        raise store.LabError(
            f"no method {method.id} in the lab database; `lab remeasure` recovers the inputs of "
            f"trials the lab already recorded, and this method has none"
        )
    looks = conn.execute(
        "SELECT candidate_id, run_at FROM trials WHERE method_id = ? AND window = 'test' ORDER BY n",
        (method.id,),
    ).fetchall()
    if looks:
        spent = ", ".join(f"{r['candidate_id']} on {r['run_at']}" for r in looks)
        raise store.LabError(
            f"{method.id} has already had its look at the test window ({spent}). `lab remeasure` "
            f"re-runs the dev window, and it will not re-run anything for a method whose test "
            f"trial exists: the one look is spent, it is never given back, and nothing in this "
            f"command may stand near it"
        )
    trials = conn.execute(
        "SELECT * FROM trials WHERE method_id = ? AND window = 'dev' ORDER BY n", (method.id,)
    ).fetchall()
    if not trials:
        raise store.LabError(
            f"{method.id} has no dev trial, so there is nothing to re-measure. "
            f"`lab run {method.id}` records the trials and their moments in one transaction"
        )
    unverifiable = [r for r in trials if r["dsr"] is None or r["sharpe"] is None]
    if unverifiable:
        names = ", ".join(str(r["candidate_id"]) for r in unverifiable)
        raise store.LabError(
            f"{method.id}: {names} recorded no DSR or no Sharpe, so a re-run cannot be checked "
            f"against what the lab recorded. `lab remeasure` only backfills trials whose recorded "
            f"verdict it can reproduce"
        )
    if require_commit:
        problem = registry_problem(path)
        if problem is not None:
            raise store.LabError(
                f"{method.id}: {problem}. `lab remeasure` re-runs the committed method file -- the "
                f"same file the trials ran under -- and nothing else"
            )
    recorded_sha = row["source_sha"]
    if recorded_sha is None:
        raise store.LabError(
            f"{method.id} has no recorded source_sha, so nothing proves the method file on disk is "
            f"the one its trials ran under; a re-run would measure a different thing"
        )
    actual = source_sha(path)
    if actual != recorded_sha:
        raise store.LabError(
            f"{method.id}: the method file hashes {actual[:12]} but its trials ran under "
            f"{str(recorded_sha)[:12]}; the file changed after it ran. Re-running it would measure "
            f"a different configuration, not recover the recorded one"
        )
    by_digest = {config_digest(c): c for c in method.candidates}
    drifted = [r for r in trials if str(r["config_digest"]) not in by_digest]
    if drifted:
        names = ", ".join(str(r["candidate_id"]) for r in drifted)
        raise store.LabError(
            f"{method.id}: {names} has a configuration the method file no longer defines. The "
            f"recorded trials and the file have diverged, so the re-run would not be the same "
            f"measurement"
        )
    have = {int(r["n"]) for r in trials if store.moments_of(conn, int(r["n"])) is not None}
    return Plan(
        method_id=method.id,
        batches=batches_of(conn, trials),
        candidates=tuple(by_digest[str(r["config_digest"])] for r in trials),
        missing=tuple(int(r["n"]) for r in trials if int(r["n"]) not in have),
        present=tuple(sorted(have)),
    )


# --------------------------------------------------------------------------- the re-run


def measure(
    conn: sqlite3.Connection, method: Method, plan: Plan, data: research.ResearchData
) -> tuple[Reproduced, ...]:
    """Re-run ``plan.candidates`` on the dev window and reproduce each trial's recorded numbers.

    ``conn`` is read from only (``plan`` already carries every row this needs); it is taken so the
    signature matches the rest of the module and a future check can reach the database without a
    call-site change.

    The dev window is not a parameter and not a choice. ``data`` is refused unless it *is* the dev
    window -- the mirror of ``runner.run_test``'s refusal of a dev store -- and ``dev.run_registry``
    is called with no ``window`` keyword, so the run is bounded by ``DEV_WINDOW`` by construction.

    The **funding** is not a parameter either: it is read off the trials being reproduced. A trial
    with a ``trial_funding`` row was run on ``sim.contributions.OWNER_MONTHLY`` and is re-run on
    it; a trial without one was run on a lump sum and is re-run on a lump sum. Getting this wrong
    is not a small error -- measured, an unfunded re-run of a funded trial reports an annualized
    Sharpe of 0.26 against a recorded 2.65 and this module correctly refuses to write anything. A
    plan that mixes the two is refused outright, because one ``run_registry`` call runs every
    candidate on one schedule and there is no answer that reproduces both.
    """
    if data.window != research.DEV_WINDOW:
        w = data.window
        raise store.LabError(
            f"{method.id}: this research store was built for the {w.name!r} window "
            f"({w.start}..{w.end}); `lab remeasure` re-runs the dev window and nothing else. "
            f"Build it with `python -m seer_engine research_store`"
        )
    ns = tuple(sorted(plan.missing + plan.present))
    funded = tuple(n for n in ns if store.funding_of(conn, n) is not None)
    if funded and len(funded) != len(ns):
        raise store.LabError(
            f"{method.id}: trials {funded} received deposits and "
            f"{tuple(n for n in ns if n not in funded)} did not, so one re-run cannot reproduce "
            f"both. Nothing is backfilled"
        )
    contributions = OWNER_MONTHLY if funded else None
    rows: dict[str, DevRow] = {}

    def on_result(i: int, result: Any, row: DevRow) -> None:
        rows[config_digest(row.candidate)] = row

    dev.run_registry(
        data.market, data.dividends, data.spy_dividends, plan.candidates,
        on_result=on_result, contributions=contributions,
    )
    out: list[Reproduced] = []
    for batch in plan.batches:
        moments: dict[int, tuple[float, float, float]] = {}
        fresh: list[float] = []
        for t in batch.trials:
            row = rows.get(str(t["config_digest"]))
            if row is None:
                raise store.LabError(
                    f"{method.id}: {t['candidate_id']} produced no row on the re-run. "
                    f"Nothing is backfilled"
                )
            m = daily_moments(row.stats.daily_returns)
            if m is None:
                raise store.LabError(
                    f"{method.id}: {t['candidate_id']} has no daily moments on the re-run but "
                    f"recorded a Sharpe of {_g(t['sharpe'])}; the re-run is not the recorded "
                    f"measurement. Nothing is backfilled"
                )
            moments[int(t["n"])] = m
            fresh.append(m[0])
        sharpes = list(batch.prior_sharpes) + fresh
        var_trials = statistics.variance(sharpes) if len(sharpes) >= 2 else None
        for t in batch.trials:
            row = rows[str(t["config_digest"])]
            sr, skew, kurt = moments[int(t["n"])]
            observations = len(row.stats.daily_returns)
            out.append(
                Reproduced(
                    trial_n=int(t["n"]),
                    candidate_id=str(t["candidate_id"]),
                    n_at_run=batch.n_at_run,
                    t=observations,
                    sr_daily=sr,
                    skew=skew,
                    kurt=kurt,
                    var_trials=var_trials,
                    recorded_sharpe=None if t["sharpe"] is None else float(t["sharpe"]),
                    measured_sharpe=row.stats.sharpe,
                    recorded_dsr=None if t["dsr"] is None else float(t["dsr"]),
                    recomputed_dsr=(
                        None
                        if var_trials is None
                        else dev.deflated_sharpe(
                            sr, batch.n_at_run, var_trials, observations, skew, kurt
                        )
                    ),
                )
            )
    return tuple(out)


def check(method_id: str, measured: Sequence[Reproduced]) -> None:
    """Raise ``store.LabError`` naming every trial the re-run failed to reproduce, and by how much.

    All or nothing: one divergent trial aborts the whole command. A partial backfill would put
    moments measured on one store beside moments measured on another, inside a table whose entire
    point is that a verdict can be recomputed from it.
    """
    bad = [r for r in measured if not r.ok]
    if not bad:
        return
    lines = [
        f"{method_id}: the re-run does not reproduce what the lab recorded, so it is not the same "
        f"measurement. Nothing was written."
    ]
    for r in bad:
        if not r.sharpe_ok:
            lines.append(
                f"  #{r.trial_n} {r.candidate_id}: annualized Sharpe {_g(r.recorded_sharpe)} "
                f"recorded, {_g(r.measured_sharpe)} measured (delta {_e(r.sharpe_delta)}, "
                f"tolerance {SHARPE_TOL:g} relative)"
            )
        else:
            lines.append(
                f"  #{r.trial_n} {r.candidate_id}: DSR {_g(r.recorded_dsr)} recorded, "
                f"{_g(r.recomputed_dsr)} recomputed at N={r.n_at_run} with var_trials "
                f"{_g(r.var_trials)} (delta {_e(r.dsr_delta)}, tolerance {DSR_TOL:g})"
            )
    lines.append(
        "  The research store, the method file or the engine has changed since those trials ran. "
        "Rebuild the dev store they were measured on and try again, or leave them un-remeasured: "
        "a trial with no moments keeps the verdict it already has."
    )
    raise store.LabError("\n".join(lines))


def _moments_row(r: Reproduced | SeedReproduced, measured: str) -> "store.MomentsRow":
    """One ``trial_moments`` row from a reproduced trial (phase 2 owns the dataclass).

    Takes either kind of reproduction: a lab-method one, verified by reproducing the recorded
    ``dsr``, or a P7a seed one, verified by reproducing the six recorded metrics. Both expose the
    same seven attributes, and the row this builds says nothing about which check was used --
    deliberately, because the row is the measurement, not the audit of it.

    ``n_at_run`` is the trial's **recorded** ``n_trials_at_run``, not today's dev trial count: the
    row documents the measurement that was made, and phase 4 derives a verdict under the current
    policy from the moments beside it.

    ``measured`` is **this backfill's** stamp, not the old trial's ``run_at``. A row written by
    ``lab run`` carries the trial's own ``run_at`` because the trial and its moments are one
    measurement with one stamp; a row written here was measured today, on today's research store
    and today's engine, and saying otherwise would claim a provenance it does not have. The two
    checks above are what tie it back to the original verdict; the stamp records when the tie was
    made.
    """
    return store.MomentsRow(
        trial_n=r.trial_n,
        sr_daily=r.sr_daily,
        t=r.t,
        skew=r.skew,
        kurt=r.kurt,
        var_trials=r.var_trials,
        n_at_run=r.n_at_run,
        measured=measured,
    )


def remeasure(
    conn: sqlite3.Connection,
    method: Method,
    path: Path,
    data: research.ResearchData,
    *,
    require_commit: bool = True,
) -> Report:
    """Re-measure ``method``'s recorded dev trials and append their ``trial_moments`` rows.

    Idempotent: when every dev trial already has its moments, this returns a Report that wrote
    nothing and names what it skipped. ``trial_moments`` is append-only, so "already there" is the
    answer, never a rewrite. The caller (``commands/lab.py``) runs ``preflight`` first and skips
    loading a research store at all in that case.

    The write is the last thing that happens and it is one statement: ``store.insert_moments``
    inside one ``BEGIN IMMEDIATE``, after both checks have passed for every trial. ``preflight``
    runs again inside the lock because a parallel explorer session may have backfilled the same
    method in between -- the same race ``runner.run_method`` guards.
    """
    plan = preflight(conn, method, path, require_commit=require_commit)
    if plan.nothing_to_do:
        return Report(method_id=method.id, measured=(), written=(), skipped=plan.present)
    measured = measure(conn, method, plan, data)
    check(method.id, measured)
    stamp = store.now_iso()  # when this backfill measured, not when the trial ran
    store.begin_immediate(conn)
    with conn:
        fresh = preflight(conn, method, path, require_commit=False)
        have = set(fresh.present)
        rows = [_moments_row(r, stamp) for r in measured if r.trial_n not in have]
        store.insert_moments(conn, rows)
    return Report(
        method_id=method.id,
        measured=measured,
        written=tuple(r.trial_n for r in rows),
        skipped=tuple(sorted(have)),
    )


# --------------------------------------------------------------------------- what it prints


def format_report(report: Report) -> str:
    """The per-trial reproduction report: what was recorded, what was measured, the difference."""
    out: list[str] = [
        f"{report.method_id}: {len(report.measured)} dev trial(s) re-measured on the dev window",
        "",
    ]
    for r in report.measured:
        mark = "wrote" if r.trial_n in report.written else "kept "
        out.append(
            f"  {mark} #{r.trial_n} {r.candidate_id}  N={r.n_at_run}  t={r.t}  "
            f"sr_daily={_g(r.sr_daily)}  skew={_g(r.skew)}  kurt={_g(r.kurt)}  "
            f"var_trials={_g(r.var_trials)}"
        )
        out.append(
            f"        Sharpe {_g(r.recorded_sharpe)} recorded vs {_g(r.measured_sharpe)} measured "
            f"(delta {_e(r.sharpe_delta)}, tolerance {SHARPE_TOL:g} relative)"
        )
        out.append(
            f"        DSR    {_g(r.recorded_dsr)} recorded vs {_g(r.recomputed_dsr)} recomputed "
            f"at N={r.n_at_run} (delta {_e(r.dsr_delta)}, tolerance {DSR_TOL:g})"
        )
    if report.skipped:
        out.append("")
        out.append(
            "  already recorded, left alone: " + ", ".join(f"#{n}" for n in report.skipped)
        )
    out.append("")
    out.append(
        f"  wrote {len(report.written)} trial_moments row(s). No trials row was inserted, updated "
        f"or deleted; no method status moved; no pre-registration was written"
    )
    return "\n".join(out)


# =========================================================================== the P7a seed
#
# The lab's first 54 dev trials were not run by the lab. `lab seed` imported them from P7a's
# committed report files as summary rows (`lab/seed.py`), so their daily moments -- the Sharpe,
# the number of returns, the skew and the kurtosis the deflated Sharpe needs -- were never
# captured, and `trials.dsr` is NULL for every one of them ("P7a reported it for one row only",
# `seed.py:136`). They nonetheless count toward N: `dev_trial_count` is 110, and 54 of those 110
# are these. They pay the full multiple-testing penalty and receive no luck verdict in return.
# Under phase 4's rule a NULL DSR fails the luck test, so they are permanently ineligible by data
# gap rather than by merit.
#
# This section closes the gap the only honest way: re-run them. Every one of the 54 is still in
# the frozen `backtest/registry.py` (design §2), and every one of their `config_digest` values
# still matches the candidate there, so the configuration is provably the one that was measured.
#
# **The check cannot be phase 3's.** A lab-method re-run is verified by reproducing the recorded
# `dsr` to 1e-6; a seed trial has no recorded `dsr`, so that check does not exist. It is replaced
# by reproduction of the six metrics the lab *did* record -- `sharpe`, `cagr`, `max_drawdown`,
# `profit_factor`, `total_return` and `trades` -- at `METRIC_TOL`, and a trial that misses on any
# of them is reported and **not written**. A trial whose re-run does not reproduce its recorded
# numbers is not the same measurement, and luck-testing it as though it were would launder a
# different backtest into the lab's history.
#
# **What it writes:** `trial_moments` rows, and nothing else -- the same single write phase 3
# makes. `trials.dsr` stays NULL on these rows forever. There is no DSR backfill: the verdict is
# phase 4's `store.verdict` computing it from the moments at the current gate N, which is the
# whole point of deriving a verdict instead of recording one.
#
# **N does not move.** These 54 trials are already inside `dev_trial_count`. Adding
# `trial_moments` rows adds no `trials` row, so neither `store.dev_trial_count` nor
# `npolicy.effective_n(conn, "all-trials")` can observe this command. Nor does the trial-Sharpe
# variance: `store.dev_daily_sharpes` reads `trials.sharpe`, which these rows already carry and
# this code never writes.


SEED_PREFIX = "H-P7A"
SEED_ALL = SEED_PREFIX  # `lab remeasure H-P7A` = every seed family
SEED_METHOD = re.compile(r"H-P7A(?:-([A-Z0-9]+))?\Z")

# The file the 54 candidates come out of. Frozen and append-only by its own rules (handover D6);
# this module reads it and never writes it.
REGISTRY_FILE = Path(dev.__file__).with_name("registry.py")

# The tolerance on a seed re-run, and the reason for its shape.
#
# These rows were imported from `docs/backtests/2026-10-04-p7a-dev-exploration-rows.csv`, whose
# every float is written to six decimal places. Decimal rounding to 6 dp bounds the
# recorded-vs-true error at 5e-7 **absolute**, independent of magnitude -- which is why this is an
# absolute tolerance and not the relative one phase 3's `SHARPE_TOL` uses on full-precision
# engine output. A relative bound would be the wrong shape at both ends of the range present here:
# `cagr = 0.031191` needs 1.6e-5 relative to survive the same rounding, while `total_return =
# 18.648246` at 1e-6 relative would admit 1.9e-5, which is 37x the rounding bound and wide enough
# for a real divergence to pass.
#
# 1e-6 is 2x the rounding bound. Measured across all 54 on the committed database and today's dev
# store, the worst delta on any metric is 4.986e-07 -- under the bound, with no exceptions -- so
# the headroom exists for a libm or platform ulp and for nothing larger. A genuine divergence is
# orders of magnitude bigger: a changed research store moves these metrics in the third decimal.
METRIC_TOL = 1e-6  # absolute, per metric

# The six recorded metrics a seed re-run must reproduce, each paired with how to read it off a
# fresh `Observed`. `trades` is compared exactly, as an integer; the five floats at METRIC_TOL.
#
# `mar`, `spy_tr_return` and `spy_tr_cagr` are deliberately absent. `mar` is
# `cagr / max_drawdown`, algebraically implied by two entries already here; the two `spy_tr_*`
# columns are the benchmark and are identical across all 54, so they carry no per-candidate
# information. Checking them would add arithmetic, not evidence.
SEED_METRICS: tuple[str, ...] = (
    "sharpe",
    "cagr",
    "max_drawdown",
    "profit_factor",
    "total_return",
    "trades",
)


@dataclass(frozen=True)
class Observed:
    """What one re-run says about one candidate: the four DSR inputs and the six checked metrics.

    This is the seam the tests replace (``run_chunk``), so the whole verification, chunking,
    idempotence and reporting path can be exercised without a 135 MB research store. ``t``,
    ``sr_daily``, ``skew`` and ``kurt`` are ``daily_moments`` on the run's daily returns; the six
    metrics are read straight off ``DevRow.stats``.
    """

    t: int
    sr_daily: float
    skew: float
    kurt: float
    sharpe: float | None
    cagr: float | None
    max_drawdown: float | None
    profit_factor: float | None
    total_return: float | None
    trades: int


@dataclass(frozen=True)
class MetricCheck:
    """One recorded metric against its re-measured value.

    ``ok`` is the whole rule, in one place:

    - ``trades`` is an **exact** integer comparison. It is the sharpest of the six, because it
      pins the trade sequence itself: a changed universe, signal or fill rule cannot reproduce a
      trade count by coincidence.
    - a metric recorded NULL reproduces only as ``None``, and one recorded non-NULL only as
      non-``None``. ``REF-SPY-HOLD`` is the real case -- a 0-trade buy-and-hold reference whose
      ``profit_factor`` is NULL in the P7a file and ``None`` on the re-run. That is a match.
    - every other float: ``abs(measured - recorded) <= METRIC_TOL``.
    """

    name: str
    recorded: float | int | None
    measured: float | int | None

    @property
    def delta(self) -> float | None:
        if self.recorded is None or self.measured is None:
            return None
        return abs(float(self.measured) - float(self.recorded))

    @property
    def ok(self) -> bool:
        if (self.recorded is None) != (self.measured is None):
            return False
        if self.recorded is None:
            return True
        if self.name == "trades":
            return int(self.measured) == int(self.recorded)
        delta = self.delta
        return delta is not None and delta <= METRIC_TOL


@dataclass(frozen=True)
class SeedTrial:
    """One recorded seed trial beside the frozen REGISTRY candidate that produced it."""

    trial: sqlite3.Row
    candidate: Candidate

    @property
    def n(self) -> int:
        return int(self.trial["n"])

    @property
    def candidate_id(self) -> str:
        return str(self.trial["candidate_id"])


@dataclass(frozen=True)
class SeedReproduced:
    """One seed trial, re-measured: its fresh moments and every metric check.

    Exposes the same seven attributes ``_moments_row`` reads off phase 3's ``Reproduced``
    (``trial_n``, ``sr_daily``, ``t``, ``skew``, ``kurt``, ``var_trials``, ``n_at_run``), so the
    one row-builder serves both paths.
    """

    trial_n: int
    candidate_id: str
    n_at_run: int
    t: int
    sr_daily: float
    skew: float
    kurt: float
    var_trials: float | None
    checks: tuple[MetricCheck, ...]

    @property
    def ok(self) -> bool:
        """True when every one of the six recorded metrics was reproduced."""
        return all(c.ok for c in self.checks)

    @property
    def misses(self) -> tuple[MetricCheck, ...]:
        return tuple(c for c in self.checks if not c.ok)


@dataclass(frozen=True)
class SeedPlan:
    """What a seed re-measurement would do, decided from the database and the REGISTRY alone."""

    method_id: str  # "H-P7A" for all families, "H-P7A-F9" for one
    todo: tuple[SeedTrial, ...]  # trials with no moments row yet, in trial order
    present: tuple[int, ...]  # trial numbers that already have one
    var_trials: float | None  # the P7a search's own trial-Sharpe variance (see seed_var_trials)
    n_at_run: int  # the N every seed row records: 54

    @property
    def nothing_to_do(self) -> bool:
        return not self.todo


@dataclass(frozen=True)
class SeedReport:
    """What one seed re-measurement did."""

    method_id: str
    measured: tuple[SeedReproduced, ...]
    written: tuple[int, ...]
    blocked: tuple[int, ...]  # re-ran, did not reproduce, deliberately not written
    skipped: tuple[int, ...]  # already had moments when this started
    var_trials: float | None
    chunks: int


@dataclass(frozen=True)
class SeedVerdict:
    """One re-measured seed trial as the gate now reads it (phase 4 decides; this only prints)."""

    trial_n: int
    candidate_id: str
    dsr: float | None  # store.verdict's number: today's lab-wide variance, at the gate's N (D12)
    dsr_recorded_var: float | None  # the same moments deflated by the recorded var_trials, for
    #                                 contrast only -- never a verdict (D12)
    luck_ok: bool
    owner_misses: tuple[str, ...]  # every failure label that is not the luck label
    eligible: bool
    mar: float | None


def is_seed_id(method_id: str) -> bool:
    """True for ``H-P7A`` and ``H-P7A-<FAM>``: the ids ``lab remeasure`` routes to the seed path."""
    return SEED_METHOD.fullmatch(method_id.strip().upper()) is not None


def seed_var_trials(conn: sqlite3.Connection) -> float | None:
    """The trial-Sharpe variance the P7a search was its own population of: the 54 seed trials'
    recorded daily Sharpes.

    ``runner.trial_rows`` computes ``var_trials`` as ``statistics.variance(prior + new_sharpes)``
    where ``prior`` is every dev trial that already existed. The seed import is the lab's first
    batch -- ``prior`` is empty and the batch is all 54 -- so this is literally the number
    ``lab run`` would have computed had P7a been run through the lab. It is a reconstruction of a
    historical fact, the same quantity phase 3's ``batches_of`` rebuilds for a lab method.

    **Read off the recorded ``trials.sharpe`` column, not off the re-run**, for three reasons and
    the first is decisive:

    1. it makes the value a constant settled in ``seed_preflight``, identical whether the batch
       runs as one call or as six interrupted ones. That is what makes this command resumable:
       computing it from fresh daily Sharpes would require all 54 re-runs in hand before the first
       row could be written;
    2. ``trials.sharpe`` *is* P7a's measurement of record. The re-run is evidence that the record
       is sound, not a replacement for it;
    3. the difference is immaterial -- measured, the recorded column gives 2.006690619e-04 and the
       fresh daily Sharpes give 2.006691421e-04, a gap of 8.0e-11, four orders of magnitude below
       anything the deflated Sharpe can resolve.

    None when fewer than two seed rows carry a Sharpe -- the same condition under which
    ``trials.dsr`` is NULL, and under which phase 2's ``MomentsRow.var_trials`` is None.
    """
    sharpes = [
        float(r[0]) / math.sqrt(TRADING_DAYS)
        for r in conn.execute(
            "SELECT sharpe FROM trials WHERE window = 'dev' AND dsr IS NULL AND sharpe IS NOT NULL "
            "ORDER BY n"
        )
    ]
    return statistics.variance(sharpes) if len(sharpes) >= 2 else None


def seed_preflight(
    conn: sqlite3.Connection,
    method_id: str,
    *,
    only: Sequence[str] = (),
    require_commit: bool = True,
) -> SeedPlan:
    """Every refusal the seed path makes from the database and the REGISTRY alone.

    Nothing here opens a research store, runs a backtest or writes a row, and the test-window
    refusal is made first -- the mirror of ``preflight``'s, and of ``runner.run_test`` refusing a
    dev store.

    ``method_id`` is ``H-P7A`` (every family) or ``H-P7A-<FAM>`` (one). ``only`` further narrows
    to named candidate ids, for re-trying a handful after a divergence.

    The guard that the re-run measures the same configuration is **per-trial
    ``config_digest`` equality** against the REGISTRY candidate, not a hash of the registry file.
    That is both stronger and more durable: the digest covers the candidate's trial-defining parts
    exactly (``lab/method.py``'s ``config_text``), and it stays true when the registry legitimately
    gains entries 55 and beyond, which a file hash would not.

    ``require_commit=False`` skips only the git cleanliness check on ``registry.py``; it never
    relaxes the digest comparison, which is the stronger of the two.
    """
    wanted = method_id.strip().upper()
    match = SEED_METHOD.fullmatch(wanted)
    if match is None:
        raise store.LabError(
            f"{method_id!r} is not a P7a seed id. `lab remeasure H-P7A` re-measures all 54 seed "
            f"trials; `lab remeasure H-P7A-F9` re-measures one family"
        )
    family = match.group(1)
    looks = conn.execute(
        "SELECT candidate_id, run_at FROM trials WHERE window = 'test' "
        "AND method_id LIKE 'H-P7A%' ORDER BY n"
    ).fetchall()
    if looks:
        spent = ", ".join(f"{r['candidate_id']} on {r['run_at']}" for r in looks)
        raise store.LabError(
            f"a P7a seed family has already had a look at the test window ({spent}). "
            f"`lab remeasure` re-runs the dev window and will not run anything beside a spent "
            f"look: the one look is never given back"
        )
    if family is None:
        rows = conn.execute(
            "SELECT * FROM trials WHERE window = 'dev' AND method_id LIKE 'H-P7A-%' ORDER BY n"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM trials WHERE window = 'dev' AND method_id = ? ORDER BY n", (wanted,)
        ).fetchall()
    if not rows:
        known = ", ".join(
            str(r[0])
            for r in conn.execute(
                "SELECT DISTINCT method_id FROM trials WHERE method_id LIKE 'H-P7A-%' "
                "ORDER BY method_id"
            )
        )
        raise store.LabError(
            f"no dev trial for {wanted} in this lab. Seed families present: {known or '(none)'}"
        )
    if only:
        picked = {c.strip().upper() for c in only}
        unknown = picked - {str(r["candidate_id"]).upper() for r in rows}
        if unknown:
            raise store.LabError(
                f"--only names {', '.join(sorted(unknown))}, which {wanted} has no trial for"
            )
        rows = [r for r in rows if str(r["candidate_id"]).upper() in picked]
    scored = [r for r in rows if r["dsr"] is not None]
    if scored:
        names = ", ".join(str(r["candidate_id"]) for r in scored)
        raise store.LabError(
            f"{wanted}: {names} already has a recorded DSR, so it is not a seed row and the seed "
            f"path's metric check is the wrong verification for it. `lab remeasure <method>` "
            f"re-measures a recorded lab method against its recorded DSR"
        )
    unverifiable = [r for r in rows if r["sharpe"] is None]
    if unverifiable:
        names = ", ".join(str(r["candidate_id"]) for r in unverifiable)
        raise store.LabError(
            f"{wanted}: {names} recorded no Sharpe, so a re-run cannot be checked against what "
            f"the lab recorded. Nothing is backfilled for a trial whose numbers cannot be "
            f"reproduced"
        )
    if require_commit:
        problem = registry_problem(REGISTRY_FILE)
        if problem is not None:
            raise store.LabError(
                f"{wanted}: {problem}. `lab remeasure` re-runs the committed registry -- the same "
                f"frozen file the P7a trials ran under (design §2) -- and nothing else"
            )
    by_id = {c.id: c for c in REGISTRY}
    pairs: list[SeedTrial] = []
    for row in rows:
        cid = str(row["candidate_id"])
        cand = by_id.get(cid)
        if cand is None:
            raise store.LabError(
                f"{wanted}: {cid} is recorded as a trial but is not in backtest/registry.py, so "
                f"there is nothing to re-run. The registry is append-only (handover D6); an entry "
                f"has gone missing and that is a bigger problem than this command"
            )
        if config_digest(cand) != str(row["config_digest"]):
            raise store.LabError(
                f"{wanted}: {cid}'s registry entry hashes {config_digest(cand)[:12]} but its trial "
                f"ran under {str(row['config_digest'])[:12]}. The registry entry changed after it "
                f"ran, so the re-run would measure a different configuration"
            )
        pairs.append(SeedTrial(trial=row, candidate=cand))
    n_at_run = {int(r["n_trials_at_run"]) for r in rows}
    if len(n_at_run) != 1:
        raise store.LabError(
            f"{wanted}: the seed rows record more than one N ({sorted(n_at_run)}), but the seed "
            f"import writes one batch with one N. The database has been edited"
        )
    have = {p.n for p in pairs if store.moments_of(conn, p.n) is not None}
    return SeedPlan(
        method_id=wanted,
        todo=tuple(p for p in pairs if p.n not in have),
        present=tuple(sorted(have)),
        var_trials=seed_var_trials(conn),
        n_at_run=n_at_run.pop(),
    )


def observe(row: DevRow) -> Observed | None:
    """``Observed`` for one fresh ``DevRow``; None when it produced no usable daily moments."""
    moments = daily_moments(row.stats.daily_returns)
    if moments is None:
        return None
    sr, skew, kurt = moments
    m = row.stats.metrics
    return Observed(
        t=len(row.stats.daily_returns),
        sr_daily=sr,
        skew=skew,
        kurt=kurt,
        sharpe=None if row.stats.sharpe is None else float(row.stats.sharpe),
        cagr=None if m.cagr is None else float(m.cagr),
        max_drawdown=None if m.max_drawdown is None else float(m.max_drawdown),
        profit_factor=None if m.profit_factor is None else float(m.profit_factor),
        total_return=None if m.total_return is None else float(m.total_return),
        trades=int(m.trades),
    )


def run_chunk(
    data: research.ResearchData, candidates: Sequence[Candidate]
) -> dict[str, Observed | None]:
    """Re-run ``candidates`` on the dev window; ``{candidate id: Observed}``.

    The dev window is not a parameter and not a choice: this function has no ``window``
    parameter, and ``dev.run_registry`` is called with no ``window`` keyword, so the run is
    bounded by ``DEV_WINDOW`` by construction. ``remeasure_seed`` has already refused any ``data``
    that is not the dev window before this is reached.

    Splitting the 54 into chunks is free of correctness cost. ``run_registry`` rebuilds its
    per-allocator ``prepare_for`` cache per call, so a chunk pays re-preparation time, but the
    measurement is identical: re-running ``F1-SPY-SMA200-M``, ``F3-SEC-TOP3-6M-TREND``,
    ``F4-MOM12-N20-TREND`` and ``F9-SPY200M70-MOM30`` alone and inside the full 54-candidate call
    gives **bit-identical** annualized Sharpes and ``t``. That is what makes it safe for the batch
    to be interrupted and resumed at any boundary.

    This is the seam the tests replace. Everything above it -- the refusals, the digest guard --
    and everything below it -- the metric checks, the chunked write, the report -- is exercised
    against a substituted ``run_chunk`` without a research store.
    """
    out: dict[str, Observed | None] = {}

    def on_result(i: int, result: Any, row: DevRow) -> None:
        out[row.candidate.id] = observe(row)

    dev.run_registry(
        data.market, data.dividends, data.spy_dividends, list(candidates), on_result=on_result
    )
    return out


def reproduce(seed: SeedTrial, obs: Observed, var_trials: float | None) -> SeedReproduced:
    """One recorded seed trial beside its re-run, with every metric check decided.

    The recorded ``dsr`` is NULL by construction, so phase 3's check -- reproduce the recorded
    DSR to 1e-6 -- does not exist here. These six metrics are its replacement: six independent
    properties of one equity curve, each of which a changed store, method or engine would move far
    outside ``METRIC_TOL``.
    """
    t = seed.trial
    checks = tuple(
        MetricCheck(name=name, recorded=t[name], measured=getattr(obs, name))
        for name in SEED_METRICS
    )
    return SeedReproduced(
        trial_n=seed.n,
        candidate_id=seed.candidate_id,
        n_at_run=int(t["n_trials_at_run"]),
        t=obs.t,
        sr_daily=obs.sr_daily,
        skew=obs.skew,
        kurt=obs.kurt,
        var_trials=var_trials,
        checks=checks,
    )


def remeasure_seed(
    conn: sqlite3.Connection,
    plan: SeedPlan,
    data: research.ResearchData,
    *,
    chunk: int = 54,
    on_chunk: Any = None,
) -> SeedReport:
    """Re-run ``plan.todo`` on the dev window in chunks and append the ``trial_moments`` rows.

    **Resumable and idempotent, by construction.** Each chunk is re-run, verified and committed
    before the next begins, so an interrupt loses at most the chunk in flight and nothing that was
    already written. ``plan.todo`` holds only trials with no moments row, and the set is re-read
    inside each chunk's write lock, so a parallel explorer session that wrote the same rows in
    between is a skip rather than a conflict -- ``trial_moments`` is append-only (phase 2's
    triggers) and "already there" is always the answer. Running the whole command a second time
    writes nothing and loads no research store (``commands/lab.py`` checks ``nothing_to_do``
    first).

    ``plan.var_trials`` is the same number for every chunk because it is read off the database in
    ``seed_preflight``, never off the re-run. That is what makes the output independent of where
    the chunk boundaries fall, and independent of how many times the job was interrupted.

    **A divergent trial is reported, not raised, and is not written.** This is the one deliberate
    difference from phase 3's ``check``, which aborts the whole command on one bad trial. Phase 3
    can be all-or-nothing because a lab method is two to five trials measured together; here one
    drifted ETF would sink fifty-three sound re-measurements across eleven unrelated families. The
    rule the brief sets is kept exactly: a trial whose re-run does not reproduce its recorded
    numbers is not the same measurement and **must not** be luck-tested as though it were -- so it
    is named in the report, counted in ``blocked``, and no moments row is written for it.

    ``on_chunk(index, total, written, blocked)``, when given, is called after each chunk commits;
    ``commands/lab.py`` uses it to print progress on a job that has no other output until the end.
    """
    if data.window != research.DEV_WINDOW:
        w = data.window
        raise store.LabError(
            f"{plan.method_id}: this research store was built for the {w.name!r} window "
            f"({w.start}..{w.end}); `lab remeasure` re-runs the dev window and nothing else. "
            f"Build it with `python -m seer_engine research_store`"
        )
    size = max(1, min(int(chunk), dev.MAX_CANDIDATES))
    groups: list[tuple[SeedTrial, ...]] = [
        tuple(plan.todo[i : i + size]) for i in range(0, len(plan.todo), size)
    ]
    stamp = store.now_iso()  # when this backfill measured, not when P7a ran
    measured: list[SeedReproduced] = []
    written: list[int] = []
    blocked: list[int] = []
    for index, group in enumerate(groups):
        fresh = run_chunk(data, [s.candidate for s in group])
        here: list[SeedReproduced] = []
        for seed in group:
            obs = fresh.get(seed.candidate_id)
            if obs is None:
                raise store.LabError(
                    f"{plan.method_id}: {seed.candidate_id} produced no usable daily moments on "
                    f"the re-run but recorded a Sharpe of {_g(seed.trial['sharpe'])}; the re-run "
                    f"is not the recorded measurement. Nothing is written for this chunk"
                )
            here.append(reproduce(seed, obs, plan.var_trials))
        good = [r for r in here if r.ok]
        bad = [r for r in here if not r.ok]
        store.begin_immediate(conn)
        with conn:
            have = {
                r.trial_n for r in good if store.moments_of(conn, r.trial_n) is not None
            }  # a parallel session may have won the race
            rows = [_moments_row(r, stamp) for r in good if r.trial_n not in have]
            store.insert_moments(conn, rows)
        measured.extend(here)
        written.extend(r.trial_n for r in rows)
        blocked.extend(r.trial_n for r in bad)
        if on_chunk is not None:
            on_chunk(index + 1, len(groups), len(rows), len(bad))
    return SeedReport(
        method_id=plan.method_id,
        measured=tuple(measured),
        written=tuple(written),
        blocked=tuple(blocked),
        skipped=plan.present,
        var_trials=plan.var_trials,
        chunks=len(groups),
    )


def seed_verdicts(
    conn: sqlite3.Connection, report: SeedReport
) -> tuple[SeedVerdict, ...]:
    """How the gate now reads every seed trial this run wrote moments for.

    Phase 4 decides; this only asks and prints. ``store.verdict`` re-derives the four threshold
    owner conditions from the trial's recorded columns against today's constants (so phase 8's 20%
    drawdown bar applies), carries ``owner inputs`` from the recorded string, and decides the luck
    test on the trial's DSR **at the gate's current N** -- which, now that these rows have moments,
    is a real number for the first time.

    ``v.dsr`` is **the gate's number**: `store.dsr_at` deflates by
    ``store.dev_sharpe_variance(conn)`` -- the trial-Sharpe variance over all 110 dev trials as the
    lab stands now -- on both of its routes, at the gate's current N (**Decision D12**).

    ``dsr_recorded_var`` is the same measured moments deflated instead by the ``var_trials``
    written beside the trial (the P7a search's own 54). **It is not a verdict and must never be
    read as one.** It is printed only so the size of the choice is on the terminal: the 54 seed
    rows are the only place in the lab where the two variances differ materially -- 2.0067e-04
    against 2.3950e-04 -- and they differ by enough to move ``F9-SPY200M70-MOM30`` from 0.8567
    (the gate's number, which fails) to 0.9031 (which would have passed). D12 settled that on the
    index's R2: pairing today's N with a variance frozen at the run date mixes bars on the other
    axis of the same formula. Showing both is what keeps the settled choice inspectable rather
    than buried in a constant nobody looked at.
    """
    g = store.gate(conn)
    out: list[SeedVerdict] = []
    for n in sorted(set(report.written)):
        trial = conn.execute("SELECT * FROM trials WHERE n = ?", (n,)).fetchone()
        if trial is None:  # unreachable: trial_moments has a foreign key onto trials(n)
            continue
        v = store.verdict(conn, trial, at=g)
        moments = store.moments_of(conn, n)
        alt: float | None = None
        if moments is not None and moments["var_trials"] is not None:
            alt = dev.deflated_sharpe(
                float(moments["sr_daily"]),
                g.n,
                float(moments["var_trials"]),
                int(moments["t"]),
                float(moments["skew"]),
                float(moments["kurt"]),
            )
        out.append(
            SeedVerdict(
                trial_n=n,
                candidate_id=str(trial["candidate_id"]),
                dsr=v.dsr,
                dsr_recorded_var=alt,
                luck_ok=v.dsr is not None and v.dsr >= store.DSR_MIN,
                owner_misses=tuple(f for f in v.failed if not f.startswith("DSR ")),
                eligible=v.eligible,
                mar=None if trial["mar"] is None else float(trial["mar"]),
            )
        )
    return out


def format_seed_report(
    conn: sqlite3.Connection, report: SeedReport, verdicts: Sequence[SeedVerdict]
) -> str:
    """The seed re-measurement report: what reproduced, what did not, and what the gate now says.

    The outcome is whatever it is. Nothing here rounds a candidate toward eligibility, and the
    second DSR column exists so that a candidate sitting on the bar is visibly sitting on the bar
    rather than quietly on one side of it.
    """
    from seer_engine.lab import seed as seed_mod

    g = store.gate(conn)
    today_var = store.dev_sharpe_variance(conn)
    out: list[str] = [
        f"{report.method_id}: {len(report.measured)} P7a seed trial(s) re-measured on the dev "
        f"window in {report.chunks} chunk(s)",
        "",
        f"  reproduction: the six recorded metrics ({', '.join(SEED_METRICS)}), "
        f"{METRIC_TOL:g} absolute on the floats and exact on trades. These rows came from "
        f"{seed_mod.P7A_REPORT} rounded to 6 dp, so the rounding bound is 5e-07 and the tolerance "
        f"is twice it",
        f"  store: the seed trials recorded {seed_mod.P7A_FINGERPRINT[:12]}..., this re-run "
        f"measured on a store the loader reported to the caller; a metric that did not reproduce "
        f"is listed below and was not written",
        f"  variance the GATE uses: {_e(today_var)} -- all {g.n} dev trials as the lab stands "
        f"now. Both of store.dsr_at's routes deflate by this (Decision D12)",
        f"  var_trials WRITTEN:     {_e(report.var_trials)} -- the 54 seed trials' own "
        f"daily-Sharpe variance, the number `lab run` would have computed for P7a's batch. "
        f"Historical record; shown in brackets below for contrast and never used as a verdict",
        f"  gate: N = {g.n} under policy {g.policy!r}, luck bar DSR >= {store.DSR_MIN:g}",
        "",
    ]
    if report.written:
        out.append(f"  wrote {len(report.written)} trial_moments row(s):")
        by_n = {v.trial_n: v for v in verdicts}
        for r in report.measured:
            if r.trial_n not in set(report.written):
                continue
            out.append(
                f"    #{r.trial_n} {r.candidate_id}  t={r.t}  sr_daily={_g(r.sr_daily)}  "
                f"skew={_g(r.skew)}  kurt={_g(r.kurt)}  N_at_run={r.n_at_run}"
            )
            v = by_n.get(r.trial_n)
            if v is None:
                continue
            luck = "PASS" if v.luck_ok else "fail"
            out.append(
                f"          DSR @ N={g.n} = {_g(v.dsr)}  luck: {luck} (bar {store.DSR_MIN:g})"
                f"   [with the recorded as-of-P7a variance: {_g(v.dsr_recorded_var)}]"
            )
            owner = "all pass" if not v.owner_misses else "; ".join(v.owner_misses)
            out.append(
                f"          owner conditions: {owner}   MAR {_g(v.mar)}   "
                f"-> {'ELIGIBLE' if v.eligible else 'not eligible'}"
            )
    if report.blocked:
        out.append("")
        out.append(
            f"  {len(report.blocked)} trial(s) did NOT reproduce what the lab recorded and were "
            f"deliberately NOT written -- a re-run that does not land on the recorded numbers is "
            f"not the same measurement:"
        )
        for r in report.measured:
            if r.ok:
                continue
            out.append(f"    #{r.trial_n} {r.candidate_id}")
            for c in r.misses:
                out.append(
                    f"          {c.name}: recorded {_g(c.recorded)}, measured {_g(c.measured)} "
                    f"(delta {_e(c.delta)}, tolerance "
                    f"{'exact' if c.name == 'trades' else f'{METRIC_TOL:g} absolute'})"
                )
        out.append(
            "    Rebuild the dev store these were measured on and try again, or leave them: a "
            "trial with no moments keeps the verdict it already has."
        )
    if report.skipped:
        out.append("")
        out.append(
            "  already recorded, left alone: " + ", ".join(f"#{n}" for n in report.skipped)
        )
    eligible = [v for v in verdicts if v.eligible]
    passing = [v for v in verdicts if v.luck_ok]
    out.append("")
    out.append(
        f"  of {len(report.written)} written: {len(passing)} now pass the luck bar, "
        f"{len(eligible)} pass every owner condition as well and are eligible"
        + (": " + ", ".join(v.candidate_id for v in eligible) if eligible else "")
    )
    out.append(
        "  no trials row was inserted, updated or deleted; no method status moved; "
        "trials.dsr is still NULL on every seed row and stays that way"
    )
    return "\n".join(out)
