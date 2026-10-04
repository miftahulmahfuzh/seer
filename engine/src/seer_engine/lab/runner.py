"""``lab run``: one method's variants on the dev window, into the lab database (design §2, §3).

1. Refuse when the method file is not committed (its commit is the pre-registration), when
   the method has already run, or when any variant's configuration already has a dev trial.
2. Run the variants through ``dev.run_registry`` on the research store (every D9 guard).
3. Deflated Sharpe per trial with N = every dev trial in the lab, this batch included, and the
   variance of the daily Sharpe across those trials.
4. Eligible = the five P7a D8 conditions and DSR >= 0.95. Insert the trials, set the method's
   ``source_sha`` and status (``dev-eligible`` when any trial is eligible, else ``rejected``),
   all in one transaction.
"""

from __future__ import annotations

import logging
import sqlite3
import statistics
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.dev import DevRow
from seer_engine.commands.backtest_dev import daily_moments, month_end_curve, registry_problem
from seer_engine.lab import store
from seer_engine.lab.method import Method, config_digest, config_text, source_sha

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Ran:
    """One finished variant: its database row and dev row."""

    trial: store.TrialRow
    row: DevRow


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
    """The trial rows for one method's dev results (``results``: (row, month-end curve))."""
    prior = store.dev_daily_sharpes(conn)
    new_sharpes = [m[0] for m in (daily_moments(r.stats.daily_returns) for r, _ in results) if m is not None]
    all_sharpes = prior + new_sharpes
    n_trials = store.dev_trial_count(conn) + len(results)
    var_trials = statistics.variance(all_sharpes) if len(all_sharpes) >= 2 else None
    run_at = store.now_iso()
    out: list[Ran] = []
    for row, curve in results:
        c = row.candidate
        m = row.stats.metrics
        dsr = _dsr(row, n_trials, var_trials)
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
            failed="; ".join(failed),
            eligible=not failed,
            dsr=dsr,
            n_trials_at_run=n_trials,
            curve_json=store.curve_json(curve),
        )
        out.append(Ran(trial, row))
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
        store.insert_trials(conn, [r.trial for r in ran])
        store.update_method(conn, method.id, source_sha=source_sha(path), status=status)
        for key in method.seen_keys:
            store.mark_seen(conn, key, method.id)
    return ran


def _hypothesis(method: Method) -> str:
    return f"{method.hypothesis.strip()}\n\nExpected failure: {method.expected_failure.strip()}"
