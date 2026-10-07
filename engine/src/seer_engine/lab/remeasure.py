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
import sqlite3
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.book_runner import TRADING_DAYS
from seer_engine.backtest.dev import Candidate, DevRow
from seer_engine.commands.backtest_dev import daily_moments, registry_problem
from seer_engine.lab import store
from seer_engine.lab.method import METHOD_ID, Method, config_digest, source_sha

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

    ``H-*`` ids -- the P7a seed families -- are refused by shape. Their trials carry
    ``dsr IS NULL`` by construction (``lab/seed.py:136``, "P7a reported it for one row only"), so
    there is no recorded verdict for a re-run to reproduce and no method file to re-run.
    """
    from seer_engine.lab.method import discover

    if METHOD_ID.fullmatch(method_id) is None:
        raise store.LabError(
            f"{method_id!r} is not a lab method id; `lab remeasure` takes a method like M0022. "
            f"The P7a seed families (H-*) recorded no DSR and have no method file, so there is "
            f"nothing to re-run and nothing to reproduce"
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
    2. ``count(dev trials with n < the batch's first n) + len(batch) == n_trials_at_run``. That
       equality *is* ``store.dev_trial_count(conn) + len(results)``, the line that produced the
       recorded N. If it does not hold, the recorded N does not describe this batch and no honest
       ``var_trials`` can be rebuilt from it.
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
        if before + len(ns) != n_at_run:
            raise store.LabError(
                f"{method_id}: trial #{first} records N = {n_at_run}, but {before} dev trials "
                f"precede it and its batch holds {len(ns)}. The recorded N does not describe this "
                f"batch, so the var_trials it was deflated by cannot be reconstructed honestly. "
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
    """
    if data.window != research.DEV_WINDOW:
        w = data.window
        raise store.LabError(
            f"{method.id}: this research store was built for the {w.name!r} window "
            f"({w.start}..{w.end}); `lab remeasure` re-runs the dev window and nothing else. "
            f"Build it with `python -m seer_engine research_store`"
        )
    rows: dict[str, DevRow] = {}

    def on_result(i: int, result: Any, row: DevRow) -> None:
        rows[config_digest(row.candidate)] = row

    dev.run_registry(
        data.market, data.dividends, data.spy_dividends, plan.candidates, on_result=on_result
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


def _moments_row(r: Reproduced, measured: str) -> "store.MomentsRow":
    """One ``trial_moments`` row from a reproduced trial (phase 2 owns the dataclass).

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
