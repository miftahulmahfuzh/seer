"""The lab's two runners: ``lab run`` on the dev window, ``lab test`` on the test window.

``lab run`` (design §2, §3) -- the search:

1. Refuse when the method file is not committed (its commit is the pre-registration), when the
   method has already run, or when any variant's configuration already has a dev trial.
2. Run the variants through ``dev.run_registry`` on the research store (every D9 guard).
3. Deflated Sharpe per trial with N resolved by ``store.DSR_POLICY`` through
   ``store.pending_gate`` -- shipped as ``all-trials``, so N = every dev trial in the lab, this
   batch included -- and the variance of the daily Sharpe across those trials.
4. Eligible = the five P7a D8 conditions and ``store.DSR_LABEL`` (DSR >= 0.90 since 2026-10-07;
   LAB_LUCK_GATE_PLAN.md Decision D1). Insert the trials, set the method's ``source_sha`` and
   status (``dev-eligible`` when any trial is eligible, else ``rejected``), all in one
   transaction. ``store.verdict`` re-reads a recorded trial against the same threshold and N, so
   a verdict is comparable across time rather than frozen at its run date.

``lab test`` (design §3) -- the one counted look:

1. Refuse a method that is not ``promoted``, a method file that is not committed or no longer
   hashes to the ``source_sha`` it ran under, a pre-registration that is missing, uncommitted or
   names another configuration, a configuration with no dev trial, and a configuration that has
   already been looked at.
2. Run the one pre-registered variant through the same ``dev.run_registry`` on the **test**-window
   store, between the bounds that store carries.
3. Append one ``trials`` row with ``window='test'`` and move the method to ``test-passed`` or
   ``test-failed``, both final, in one transaction.

**The look does not move the lab's N.** ``store.dev_trial_count`` and ``store.dev_daily_sharpes``
are dev-only and stay dev-only: design §1 makes ``trials`` the multiple-testing count of the
*search*, and §3 makes the test window a *look* at one already-counted configuration. A dev trial
recorded tomorrow is deflated by exactly the N it would have had if no look had ever been spent,
so every recorded dev trial stays reproducible.

Since LAB_LUCK_GATE_PLAN.md phase 4, *what* N counts is ``store.DSR_POLICY``'s business and need
not be a row count at all; *which* trials it counts over is still dev trials only, and that is
what this paragraph is about.
"""

from __future__ import annotations

import logging
import sqlite3
import statistics
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.dev import Candidate, DevRow
from seer_engine.commands.backtest_dev import daily_moments, month_end_curve, registry_problem
from seer_engine.fundamentals import coverage
from seer_engine.lab import store
from seer_engine.lab.method import METHOD_ID, Method, config_digest, config_text, source_sha
from seer_engine.strategies.allocator import MarketAware

if TYPE_CHECKING:  # typing only: prereg is imported inside the functions that use it, so
    from seer_engine.lab import prereg  # importing `runner` never pulls in git or the docs tree

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Ran:
    """One finished variant: its database row, its dev row, and the DSR's inputs.

    ``moments`` carries ``trial_n=0`` until ``insert_trials`` assigns the real trial number;
    ``run_method`` stamps it and records it. It is None exactly when ``daily_moments`` returned
    None for this variant, which is exactly when ``trial.dsr`` is None -- a trial that never had
    a deflated Sharpe has no inputs to keep. It defaults to None so a caller that only cares
    about the trial can still build a ``Ran`` positionally.
    """

    trial: store.TrialRow
    row: DevRow
    moments: store.MomentsRow | None = None


def git_head(cwd: Path) -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def preflight(conn: sqlite3.Connection, method: Method, path: Path, *, require_commit: bool = True) -> None:
    """Every refusal ``lab run`` makes before loading data (``store.LabError``)."""
    if require_commit:
        problem = registry_problem(path)
        if problem is not None:
            raise store.LabError(
                f"{method.id}: {problem}. Commit the method file first: the commit is its pre-registration"
            )
    row = store.get_method(conn, method.id)
    if row is not None and row["status"] not in ("idea", "registered"):
        raise store.LabError(
            f"{method.id} is already {row['status']}: a method runs once. A change is a new "
            "variation method (source_kind='variation', parent_id=...)"
        )
    if method.parent_id is not None and store.get_method(conn, method.parent_id) is None:
        raise store.LabError(f"{method.id}: parent {method.parent_id} is not in the lab")
    for c in method.candidates:
        if store.has_trial(conn, config_digest(c), "dev"):
            hit = conn.execute(
                "SELECT candidate_id FROM trials WHERE config_digest = ? AND window = 'dev'",
                (config_digest(c),),
            ).fetchone()
            raise store.LabError(f"{c.id} repeats {hit[0]}, which already ran on the dev window")


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


def _dsr(row: DevRow, n_trials: int, var_trials: float | None) -> float | None:
    m = daily_moments(row.stats.daily_returns)
    if m is None or var_trials is None:
        return None
    sr, skew, kurt = m
    return dev.deflated_sharpe(sr, n_trials, var_trials, len(row.stats.daily_returns), skew, kurt)


def _f(x: Any) -> float | None:
    return None if x is None else float(x)


def trial_rows(
    conn: sqlite3.Connection,
    method: Method,
    results: list[tuple[DevRow, Any]],
    *,
    fingerprint: str,
    git_sha: str,
) -> list[Ran]:
    """The trial rows for one method's dev results (``results``: (row, month-end curve)).

    The luck test's N is ``store.pending_gate(conn, method.id, len(results)).n`` -- the N the
    lab's ``store.DSR_POLICY`` resolves to, projected over this batch, which is the same N
    ``store.verdict`` re-reads these trials under. A trial run tonight and one recorded six weeks
    ago are therefore judged by one bar, which is R2. Under the shipped ``all-trials`` policy it
    is ``dev_trial_count(conn) + len(results)``, exactly the expression this function used before
    the policy existed.

    ``n_trials_at_run`` records **the N the DSR was computed at**, which is what it has always
    meant (``lab promote`` prints it as "DSR ... at N = ..."). The raw dev row count is always
    ``store.dev_trial_count``. The variance is still the sample variance of the daily Sharpe
    across every recorded dev trial plus this batch: only the *count* of looks is
    policy-dependent, not the dispersion the expected maximum is drawn from. The threshold the
    DSR is compared against is ``store.DSR_MIN`` -- 0.90 since 2026-10-07.

    Each ``Ran`` also carries the deflated Sharpe's inputs (``store.MomentsRow``) so
    ``run_method`` can record them beside the trial they judged: the daily Sharpe, the number of
    daily returns, the skew and the kurtosis of the variant, plus the ``var_trials`` and the N
    this batch was deflated by. ``trials`` is append-only and its ``dsr`` is frozen at the N of
    its run date, so these are the only way a verdict can ever be recomputed without re-running
    the backtest.

    **The verdict is not changed by that bookkeeping.** ``n_trials`` and ``var_trials`` are the
    same values, read the same way, in the same order; ``dsr`` is the same
    ``dev.deflated_sharpe`` call on the same six arguments; ``failed`` and ``eligible`` are
    unchanged. The only difference from the previous version is that ``daily_moments`` is
    evaluated once per variant and reused, instead of once for the batch Sharpe and again inside
    ``_dsr`` -- it is a pure function of the variant's daily returns, so hoisting it cannot move
    a number.
    """
    prior = store.dev_daily_sharpes(conn)
    moments = [daily_moments(r.stats.daily_returns) for r, _ in results]
    new_sharpes = [m[0] for m in moments if m is not None]
    all_sharpes = prior + new_sharpes
    gate = store.pending_gate(conn, method.id, len(results))
    n_trials = gate.n
    var_trials = statistics.variance(all_sharpes) if len(all_sharpes) >= 2 else None
    run_at = store.now_iso()
    out: list[Ran] = []
    for (row, curve), m in zip(results, moments, strict=True):
        c = row.candidate
        met = row.stats.metrics
        t = len(row.stats.daily_returns)
        if m is None or var_trials is None:
            dsr = None
            mom = None
        else:
            dsr = dev.deflated_sharpe(m[0], n_trials, var_trials, t, m[1], m[2])
            mom = store.MomentsRow(
                trial_n=0,  # insert_trials assigns it; run_method stamps this row with it
                sr_daily=float(m[0]),
                t=t,
                skew=float(m[1]),
                kurt=float(m[2]),
                var_trials=float(var_trials),
                n_at_run=n_trials,
                measured=run_at,
            )
        failed = list(row.failed)
        if dsr is None or dsr < store.DSR_MIN:
            failed.append(store.DSR_LABEL)
        worst = row.stats.worst_year
        trial = store.TrialRow(
            method_id=method.id,
            candidate_id=c.id,
            config_digest=config_digest(c),
            config_text=config_text(c),
            rules_id=c.rules.id,
            allocator_id=str(c.allocator.id),
            window="dev",
            start=row.start.isoformat(),
            end=row.end.isoformat(),
            store_fingerprint=fingerprint,
            git_sha=git_sha,
            run_at=run_at,
            total_return=_f(met.total_return),
            cagr=_f(met.cagr),
            max_drawdown=_f(met.max_drawdown),
            profit_factor=_f(met.profit_factor),
            trades=int(met.trades),
            sharpe=_f(row.stats.sharpe),
            exposure=_f(row.stats.exposure),
            turnover=_f(row.stats.turnover),
            worst_year=None if worst is None else int(worst[0]),
            worst_year_return=None if worst is None else float(worst[1]),
            spy_tr_return=_f(row.spy_tr.total_return),
            spy_tr_cagr=_f(row.spy_tr.cagr),
            mar=row.mar,
            failed="; ".join(failed),
            eligible=not failed,
            dsr=dsr,
            n_trials_at_run=n_trials,
            curve_json=store.curve_json(curve),
        )
        out.append(Ran(trial=trial, row=row, moments=mom))
    return out


def run_method(
    conn: sqlite3.Connection,
    method: Method,
    path: Path,
    data: research.ResearchData,
    *,
    git_sha: str,
    require_commit: bool = True,
) -> list[Ran]:
    """Run ``method`` on the dev window and record it (see the module docstring)."""
    preflight(conn, method, path, require_commit=require_commit)
    results: list[tuple[DevRow, Any]] = []

    def on_result(i: int, result: Any, row: DevRow) -> None:
        results.append((row, month_end_curve(result.snapshots)))
        m = row.stats.metrics
        log.info(
            "[%d/%d] %s %s..%s: return %s vs SPY TR %s, max DD %s, PF %s, trades %d",
            i + 1, len(method.candidates), row.candidate.id, row.start, row.end,
            m.total_return, row.spy_tr.total_return, m.max_drawdown, m.profit_factor, m.trades,
        )

    dev.run_registry(data.market, data.dividends, data.spy_dividends, method.candidates, on_result=on_result)
    store.begin_immediate(conn)  # lab-wide N and the inserts, atomic against parallel sessions
    with conn:
        preflight(conn, method, path, require_commit=False)  # a parallel session may have won a race
        ran = trial_rows(conn, method, results, fingerprint=data.fingerprint, git_sha=git_sha)
        status = "dev-eligible" if any(r.trial.eligible for r in ran) else "rejected"
        if store.get_method(conn, method.id) is None:
            store.add_method(
                conn,
                id=method.id,
                name=method.name,
                family=method.family,
                source_kind=method.source_kind,
                source_ref=method.source_ref,
                hypothesis=_hypothesis(method),
                parent_id=method.parent_id,
                status="registered",
            )
        else:
            row = store.get_method(conn, method.id)
            if row["status"] == "idea":
                store.update_method(
                    conn, method.id, hypothesis=_hypothesis(method), name=method.name,
                    family=method.family, source_kind=method.source_kind,
                    source_ref=method.source_ref, parent_id=method.parent_id,
                )
                store.update_method(conn, method.id, status="registered")
        ns = store.insert_trials(conn, [r.trial for r in ran])
        # The DSR's inputs, stamped with the trial numbers SQLite just assigned, in this same
        # transaction: a trial and the measurement that judged it are recorded together or not
        # at all. A variant with no computable moments contributes no row, exactly as it
        # contributes no dsr.
        store.insert_moments(conn, [
            replace(r.moments, trial_n=n)
            for n, r in zip(ns, ran, strict=True)
            if r.moments is not None
        ])
        store.update_method(conn, method.id, source_sha=source_sha(path), status=status)
        for key in method.seen_keys:
            store.mark_seen(conn, key, method.id)
    return ran


def _hypothesis(method: Method) -> str:
    return f"{method.hypothesis.strip()}\n\nExpected failure: {method.expected_failure.strip()}"


# --------------------------------------------------------------------------- the test window


@dataclass(frozen=True)
class Tested:
    """The one counted look at the test window: its trial row, its dev row and its verdict."""

    trial: store.TrialRow
    row: DevRow
    status: str  # "test-passed" | "test-failed", both final


def resolve_candidate(candidate_id: str) -> tuple[Method, Path, Candidate]:
    """``(METHOD, its file, the named Candidate)`` for a candidate id like ``M0007-RESID``.

    ``lab test`` is addressed by *candidate*, not by method, because one variant per method is
    pre-registered and it is that variant -- not the method -- that gets the look. The method id
    is the part before the first hyphen (``method.Method`` enforces that shape at ``method.py:84``).

    ``store.LabError`` when the id is not a candidate id, when no method file carries it, or when
    the method has no such variant.
    """
    method_id, sep, _suffix = candidate_id.partition("-")
    if not sep or METHOD_ID.fullmatch(method_id) is None:
        raise store.LabError(
            f"{candidate_id!r} is not a candidate id; `lab test` takes the pre-registered variant, "
            f"which looks like M0007-RESID (<method>-<suffix>)"
        )
    from seer_engine.lab.method import discover

    methods = discover()
    if method_id not in methods:
        raise store.LabError(
            f"no method file for {method_id} in seer_engine/lab/methods/. The test window runs the "
            f"committed method file, not a database row. Known: {', '.join(methods) or '(none)'}"
        )
    method, path = methods[method_id]
    found = [c for c in method.candidates if c.id == candidate_id]
    if len(found) != 1:
        raise store.LabError(
            f"{method_id} has no variant {candidate_id!r}; its variants are "
            f"{', '.join(c.id for c in method.candidates)}"
        )
    return method, path, found[0]


def preflight_test(
    conn: sqlite3.Connection,
    method: Method,
    path: Path,
    candidate: Candidate,
    *,
    pre: "prereg.Prereg | None" = None,
    require_commit: bool = True,
) -> "prereg.Prereg":
    """Every refusal ``lab test`` makes before any data is loaded (``store.LabError``).

    The look at the test window is spent once and never given back, so each of these is checked
    before the store is even opened:

    1. **the method is ``promoted``.** ``lab promote`` (phase 3) is the only thing that moves it
       there, and the lab's ``TRANSITIONS`` give ``promoted`` only two exits, both of them final.
    2. **the method file is committed and still hashes to the ``source_sha`` recorded when it
       ran.** The dev trial measured one file; the test window must measure the same one. A
       changed file is a new variation method, not a second look.
    3. **a pre-registration exists, is committed, and names this candidate and this configuration
       digest** (``lab.prereg``, phase 3). This is design §3's "pre-registered ... before any test
       number exists": the thing pre-registered is the thing that runs. Both halves are phase 3's
       functions -- ``require_committed`` (git state, and that the file names *this* method and
       *this* candidate) and ``check_digest`` (that the configuration has not drifted since) --
       and neither is reimplemented here.
    4. **this configuration has a recorded ``dev`` trial.** The test window confirms a dev result;
       it never discovers one.
    5. **this configuration has no ``test`` trial.** The database refuses a second look on its own
       (``UNIQUE(config_digest, window)`` plus the append-only triggers, ``store.py:169``,
       ``:186``, ``:189``); this is the early, readable form of the same no, made before a store
       is loaded and a backtest is run.

    Returns the pre-registration, so the caller can print what it is about to honour.

    ``pre`` is an already-read pre-registration. ``require_committed`` shells out to git, so the
    caller reads it once and hands it back for the re-check inside the write lock; ``check_digest``
    and the two database refusals still run every time. ``require_commit=False`` skips 2's git
    checks on the *method file*; it never relaxes 1, 3's digest comparison, 4 or 5. Tests pass
    both.
    """
    from seer_engine.lab import prereg

    row = store.get_method(conn, method.id)
    if row is None:
        raise store.LabError(
            f"no method {method.id} in the lab database; nothing reaches the test window that the "
            f"lab has not run"
        )
    status = str(row["status"])
    if status != "promoted":
        raise store.LabError(
            f"{method.id} is {status!r}; only a 'promoted' method reaches the test window. "
            f"`lab promote {method.id}` pre-registers the best dev-eligible variant by MAR and "
            f"moves it there. From {status!r} the lab's TRANSITIONS have no edge to 'promoted', "
            f"and the test window stays shut"
        )
    if require_commit:
        problem = registry_problem(path)
        if problem is not None:
            raise store.LabError(
                f"{method.id}: {problem}. The test window is spent once; it runs only against the "
                f"committed method file"
            )
        recorded = row["source_sha"]
        actual = source_sha(path)
        if recorded is not None and recorded != actual:
            raise store.LabError(
                f"{method.id}: the method file hashes {actual[:12]} but its dev trials ran under "
                f"{recorded[:12]}; the file changed after it ran. A changed method is a new "
                f"variation method (source_kind='variation', parent_id={method.id}), not a second look"
            )
    # Phase 3 owns both halves of refusal 3. require_committed checks git AND that the file
    # names this method and this candidate; check_digest checks what the candidate *does*.
    if pre is None:
        pre = prereg.require_committed(candidate.id)
    digest = config_digest(candidate)
    prereg.check_digest(pre, digest)
    if not store.has_trial(conn, digest, "dev"):
        raise store.LabError(
            f"{candidate.id}: this configuration has no dev trial. The test window confirms a dev "
            f"result; it never discovers one"
        )
    if store.has_trial(conn, digest, "test"):
        hit = conn.execute(
            "SELECT candidate_id, run_at, eligible FROM trials WHERE config_digest = ? AND window = 'test'",
            (digest,),
        ).fetchone()
        raise store.LabError(
            f"{candidate.id}: this configuration already had its look at the test window as "
            f"{hit[0]} on {hit[1]} ({'passed' if hit[2] else 'failed'}). There is no second look: "
            f"the database holds at most one test trial per configuration and trials are "
            f"append-only"
        )
    return pre


def test_trial_row(
    conn: sqlite3.Connection,
    method: Method,
    row: DevRow,
    curve: Any,
    *,
    fingerprint: str,
    git_sha: str,
) -> store.TrialRow:
    """The one ``window='test'`` trial row for ``row`` (``curve``: its month-end equity curve).

    **It does not move the lab's N.** ``n_trials_at_run`` is ``store.dev_trial_count(conn)`` as it
    stands, unchanged by this row: design §1 makes ``trials`` the multiple-testing count of the
    *search*, and §3 makes the test window a look at one already-counted configuration, not a new
    search. ``store.dev_trial_count`` and ``store.dev_daily_sharpes`` are dev-only and stay
    dev-only, so a dev trial recorded afterwards is deflated by exactly the N it would have had if
    this look had never happened and every recorded dev trial stays reproducible.

    ``dsr`` is recorded and **does not decide the verdict**: the out-of-sample Sharpe deflated by
    the N that selected this configuration and by the variance of the dev trials' daily Sharpe. It
    is worth keeping in the column the web already renders, but it is not a condition, because the
    look was pre-registered -- there is no selection among test results to deflate, and
    ``store.DSR_LABEL`` never appears in a test trial's ``failed``.

    The verdict is the five design §1 go-live conditions, which ``dev.make_row`` already applied to
    ``row``; ``failed`` and ``eligible`` are the row's own.
    """
    n_trials = store.dev_trial_count(conn)
    sharpes = store.dev_daily_sharpes(conn)
    var_trials = statistics.variance(sharpes) if len(sharpes) >= 2 else None
    c = row.candidate
    m = row.stats.metrics
    worst = row.stats.worst_year
    return store.TrialRow(
        method_id=method.id,
        candidate_id=c.id,
        config_digest=config_digest(c),
        config_text=config_text(c),
        rules_id=c.rules.id,
        allocator_id=str(c.allocator.id),
        window="test",
        start=row.start.isoformat(),
        end=row.end.isoformat(),
        store_fingerprint=fingerprint,
        git_sha=git_sha,
        run_at=store.now_iso(),
        total_return=_f(m.total_return),
        cagr=_f(m.cagr),
        max_drawdown=_f(m.max_drawdown),
        profit_factor=_f(m.profit_factor),
        trades=int(m.trades),
        sharpe=_f(row.stats.sharpe),
        exposure=_f(row.stats.exposure),
        turnover=_f(row.stats.turnover),
        worst_year=None if worst is None else int(worst[0]),
        worst_year_return=None if worst is None else float(worst[1]),
        spy_tr_return=_f(row.spy_tr.total_return),
        spy_tr_cagr=_f(row.spy_tr.cagr),
        mar=row.mar,
        failed="; ".join(row.failed),
        eligible=row.eligible,
        dsr=_dsr(row, n_trials, var_trials),
        n_trials_at_run=n_trials,
        curve_json=store.curve_json(curve),
    )


def run_test(
    conn: sqlite3.Connection,
    method: Method,
    path: Path,
    candidate: Candidate,
    data: research.ResearchData,
    *,
    git_sha: str,
    require_commit: bool = True,
) -> Tested:
    """Spend the one counted look at the test window and record it (design §3).

    ``data`` must be a **test**-window store. The window it was built for travels on it
    (``ResearchData.window``, phase 2), the candidate runs between that window's bounds, and a dev
    store is refused here as well as by ``load_store``: a mis-pointed ``SEER_RESEARCH_STORE`` must
    never produce a ``window='test'`` trial measured on dev data, because the row can never be
    corrected.

    The candidate goes through ``dev.run_registry`` -- the same path, the same ``prepare_for``
    dispatch and the same D8 row ``lab run`` uses, with the window as the only difference -- then
    one ``trials`` row is appended and the method moves to ``test-passed`` or ``test-failed``, both
    final, in one transaction. Every refusal is made before the store is loaded except the two the
    store itself makes possible, and all of them spend nothing.
    """
    window = data.window
    if window.name != "test":
        raise store.LabError(
            f"{candidate.id}: this research store was built for the {window.name!r} window "
            f"({window.start}..{window.end}); `lab test` runs on the test window and nothing else. "
            f"Build it with `python -m seer_engine research_store --test-window`"
        )
    aware = market_aware_candidates(method)
    if candidate.id in aware and len(data.market.fundamentals) == 0:
        raise store.LabError(
            f"{candidate.id} ranks on Market.fundamentals and this test store carries no panel; "
            f"the look would measure the missing panel, not the hypothesis. Build the test store "
            f"with `research_store --test-window --with-fundamentals` and run it again -- nothing "
            f"has been spent"
        )
    pre = preflight_test(conn, method, path, candidate, require_commit=require_commit)

    captured: list[tuple[DevRow, Any]] = []

    def on_result(i: int, result: Any, row: DevRow) -> None:
        captured.append((row, month_end_curve(result.snapshots)))

    dev.run_registry(
        data.market,
        data.dividends,
        data.spy_dividends,
        (candidate,),
        on_result=on_result,
        window=window,
    )
    (row, curve), = captured
    m = row.stats.metrics
    log.info(
        "%s on the test window %s..%s: return %s vs SPY TR %s, max DD %s, PF %s, trades %d",
        candidate.id, row.start, row.end, m.total_return, row.spy_tr.total_return,
        m.max_drawdown, m.profit_factor, m.trades,
    )
    store.begin_immediate(conn)  # the look and the status move, atomic against parallel sessions
    with conn:
        # A parallel session may have won the race to this configuration's one look. `pre` is
        # the pre-registration git already vouched for above, so this re-check costs no
        # subprocess and still re-runs check_digest and both database refusals.
        preflight_test(conn, method, path, candidate, pre=pre, require_commit=False)
        trial = test_trial_row(conn, method, row, curve, fingerprint=data.fingerprint, git_sha=git_sha)
        status = "test-passed" if row.eligible else "test-failed"
        store.insert_trials(conn, [trial])
        store.update_method(conn, method.id, status=status)
    return Tested(trial=trial, row=row, status=status)
