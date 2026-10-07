"""`lab`: the method lab (docs/plans/2026-10-04-method-lab-design.md).

    lab status                      N, test looks, near misses, backlog, blocked ideas
    lab show M0007                  one method and its trials
    lab run M0007 [--store DIR] [--allow-coverage F]
                                    run a committed method on the dev window, record its trials;
                                    a method with a MarketAware allocator is refused when the
                                    store's fundamental panel covers less than 80% of the window
    lab promote M0007               pre-register the best dev-eligible variant by MAR in
                                    docs/lab/prereg/M0007.md and move the method to promoted;
                                    commit that file before `lab test` will spend the one look
    lab reevaluate [M0022 ...]      re-judge recorded dev trials against the bars in force now
                                    (store.DSR_MIN, store.DSR_POLICY, tuning.MAX_DRAWDOWN) and
                                    move a method they unblock from rejected to dev-eligible.
                                    Reads only: no store, no backtest, no trial row, no look. A
                                    trial whose DSR cannot be evaluated at the gate's N fails the
                                    luck test and is reported as such
    lab test M0007-A [--store DIR] [--roster-id ID] [--dry-run]
                                    the one counted look: run a promoted method's pre-registered
                                    variant once on the test window, record a `test` trial and set
                                    test-passed / test-failed (both final). Refuses without a
                                    committed pre-registration, refuses a method that is not
                                    promoted, and the database refuses a second look. --dry-run
                                    prints what would run and spends nothing
    lab remeasure M0022 | H-P7A | H-P7A-F9 [--store DIR] [--only IDS] [--chunk N]
                                    re-run a recorded method's variants on the dev window and
                                    write back the DSR inputs (trial_moments) its trials predate.
                                    Writes nothing else: no trials row, no status, no
                                    pre-registration. Idempotent, and refuses a method that has
                                    already had its test-window look
                                    H-P7A re-measures all 54 P7a seed trials out of the frozen
                                    registry and reports the DSR each now computes at the current
                                    gate N; H-P7A-F9 does one family. A seed trial has no recorded
                                    DSR, so the re-run is verified against the six metrics the lab
                                    did record, and a trial that does not reproduce them is
                                    reported and not written (exit 1)
    lab idea --name ... --hypothesis ...   queue an idea (prints its id)
    lab note M0007 --file F [--verdict V]  append analysis / set the verdict
    lab block M0007 --on "what data"       an idea the store cannot test
    lab drop M0007 --why "..."             an idea dropped before running
    lab seen KEY [--method M] [--note N] | lab seen --find TEXT
    lab insight --kind K --title T (--body B | --file F) [--method M]   the lab journal
    lab stage                       under the write lock: write web/data/lab.json, git-add it and the database
    lab next-id                     the next free method id
    lab export [--out F]            the lab as an xlsx workbook (gitignored)
    lab export-json [--out F]       the web snapshot (default: web/data/lab.json beside the database's repo)
    lab seed                        one-time import of the pre-lab record

Parallel sessions (sera-the-explorer) share one database: SEER_LAB_DB sets --db and
SEER_RESEARCH_STORE sets --store.

Exit 0 on success; 2 when the lab's rules refuse the request; 1 on any other error.
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from pathlib import Path

from seer_engine import config, research
from seer_engine.backtest import dev
from seer_engine.backtest.metrics import fmt_num, fmt_pct, fmt_pf, fmt_signed_pct
from seer_engine.fundamentals import coverage
from seer_engine.lab import store

log = logging.getLogger(__name__)

HELP = "The method lab: run, record and review strategy experiments (lab/lab.sqlite)"


def _coverage_floor(text: str) -> float:
    try:
        value = float(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from exc
    if not 0.0 <= value <= 1.0:
        raise argparse.ArgumentTypeError(f"must be a fraction between 0 and 1, got {value}")
    return value


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--db", type=Path, default=store.DB_PATH, help="lab database (default: lab/lab.sqlite)")
    sub = p.add_subparsers(dest="lab_command", metavar="<lab command>", required=True)

    sub.add_parser("status", help="the lab at a glance")
    s = sub.add_parser("show", help="one method and its trials")
    s.add_argument("method")

    s = sub.add_parser("run", help="run a committed method on the dev window")
    s.add_argument("method")
    s.add_argument("--store", type=Path, default=Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR))
    s.add_argument(
        "--allow-coverage",
        type=_coverage_floor,
        default=coverage.MIN_DEV_COVERAGE,
        metavar="F",
        help=(
            f"lower the dev-window panel-coverage floor from {coverage.MIN_DEV_COVERAGE:.2f} to F "
            "(0..1) for this run. An acknowledgement, not a silencer: the measured fraction and "
            "the per-year table are printed either way. Only methods with a MarketAware "
            "allocator are gated at all"
        ),
    )

    s = sub.add_parser(
        "promote", help="pre-register a dev-eligible method's best variant for the test window"
    )
    s.add_argument("method")
    s.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="where the pre-registration file goes (default: docs/lab/prereg/ in this checkout)",
    )

    s = sub.add_parser(
        "reevaluate",
        help="re-judge recorded dev trials against the current luck bar; moves a method "
             "rejected -> dev-eligible when the bars in force today clear every condition",
    )
    s.add_argument(
        "method", nargs="*", metavar="M0022",
        help="methods to re-evaluate (default: every method that reads rejected)",
    )

    s = sub.add_parser("test", help="the one counted look at the test window (design §3)")
    s.add_argument("candidate", metavar="M0007-A",
                   help="the pre-registered variant, not the method: one variant per method "
                        "is pre-registered and it is the one that gets the look")
    s.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("SEER_RESEARCH_TEST_STORE") or research.TEST_STORE_DIR),
        help=f"test-window research store (default: {research.TEST_STORE_DIR}, or "
             "$SEER_RESEARCH_TEST_STORE); a dev store here is refused",
    )
    s.add_argument("--roster-id", default=None, metavar="ID",
                   help="the paper-roster id to propose in the promote command printed on a pass "
                        "(default: the method id)")
    s.add_argument("--dry-run", action="store_true",
                   help="print what would run -- the window, the store, the pre-registration and "
                        "the conditions that decide the verdict -- and stop. Loads nothing, runs "
                        "nothing, records nothing; the look is not spent")

    s = sub.add_parser(
        "remeasure",
        help="recover the DSR inputs (trial_moments) of a method whose trials predate them",
    )
    s.add_argument("method", metavar="M0022|H-P7A",
                   help="the lab method whose recorded dev trials get their moments back, or "
                        "H-P7A for all 54 P7a seed trials / H-P7A-F9 for one seed family")
    s.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR),
        help=f"dev-window research store (default: {research.STORE_DIR}, or "
             "$SEER_RESEARCH_STORE). A test store is refused by research.load_store before a "
             "byte is read: this command never names a test window and never spends a look",
    )
    s.add_argument("--only", default=None, metavar="IDS",
                   help="seed path only: a comma-separated list of candidate ids to re-measure "
                        "instead of the whole set, for re-trying a handful after a divergence")
    s.add_argument("--chunk", type=int, default=dev.MAX_CANDIDATES, metavar="N",
                   help="seed path only: commit after every N backtests, so an interrupted job "
                        f"loses at most N (default: {dev.MAX_CANDIDATES}, i.e. one call). "
                        "Chunking is bit-identical to one call and costs only allocator "
                        "re-preparation; the whole 54-trial batch takes about a minute")

    s = sub.add_parser("idea", help="queue an idea in the backlog")
    s.add_argument("--name", required=True)
    s.add_argument("--family", required=True)
    s.add_argument("--hypothesis", required=True)
    s.add_argument("--source-kind", required=True, choices=[k for k in store.SOURCE_KINDS if k != "seed"])
    s.add_argument("--source-ref", default="")
    s.add_argument("--parent", default=None)

    s = sub.add_parser("note", help="append analysis and/or set the verdict")
    s.add_argument("method")
    s.add_argument("--file", type=Path, default=None)
    s.add_argument("--verdict", default=None)

    s = sub.add_parser("block", help="mark an idea blocked on missing data")
    s.add_argument("method")
    s.add_argument("--on", required=True)

    s = sub.add_parser("drop", help="drop an idea before it runs")
    s.add_argument("method")
    s.add_argument("--why", required=True)

    s = sub.add_parser("seen", help="record or find a dedupe key")
    s.add_argument("key", nargs="?")
    s.add_argument("--method", default=None)
    s.add_argument("--note", default="")
    s.add_argument("--find", default=None)

    s = sub.add_parser("insight", help="append to the lab journal (food for thought)")
    s.add_argument("--kind", required=True, choices=store.INSIGHT_KINDS)
    s.add_argument("--title", required=True)
    s.add_argument("--body", default=None)
    s.add_argument("--file", type=Path, default=None)
    s.add_argument("--method", default=None)

    sub.add_parser("stage", help="write the web snapshot and git-add it with the database, under the write lock")
    sub.add_parser("next-id", help="the next free method id")
    s = sub.add_parser("export", help="write the lab as an xlsx workbook")
    s.add_argument("--out", type=Path, default=store.XLSX_PATH)
    s = sub.add_parser("export-json", help="write the web snapshot (seertrade.site/sera)")
    s.add_argument("--out", type=Path, default=None,
                   help="output file (default: web/data/lab.json in the database's repo)")
    sub.add_parser("seed", help="one-time import of the pre-lab record")


def run(args: argparse.Namespace) -> int:
    conn = store.connect(args.db)
    try:
        return _HANDLERS[args.lab_command](conn, args)
    except store.LabError as e:
        log.error("%s", e)
        return 2
    finally:
        conn.close()


# --------------------------------------------------------------------------- handlers


def _status(conn, args) -> int:
    out: list[str] = []
    for label, value in store.summary_rows(conn):
        out.append(f"{label}: {value}")
    out.append("")
    out.append("Families (best dev MAR):")
    for r in conn.execute(
        "SELECT m.family, count(t.n) AS trials, max(t.mar) AS best, group_concat(DISTINCT m.id) AS ids "
        "FROM methods m LEFT JOIN trials t ON t.method_id = m.id AND t.window = 'dev' "
        "WHERE m.status NOT IN ('idea', 'blocked-data') GROUP BY m.family ORDER BY best IS NULL, best DESC"
    ):
        out.append(f"  {r['family']:<28} trials {r['trials']:>3}  best MAR {fmt_num(r['best'])}  ({r['ids']})")
    out.append("")
    out.append("Near misses (beat SPY TR on dev, by MAR):")
    for r in conn.execute(
        "SELECT * FROM trials WHERE window = 'dev' AND total_return > spy_tr_return AND mar IS NOT NULL "
        "ORDER BY mar DESC LIMIT 12"
    ):
        out.append(
            f"  {r['candidate_id']:<28} MAR {fmt_num(r['mar'])}  CAGR {fmt_signed_pct(r['cagr'])} vs "
            f"{fmt_signed_pct(r['spy_tr_cagr'])}  maxDD {fmt_pct(r['max_drawdown'])}  PF {fmt_pf(r['profit_factor'])}  "
            f"trades {r['trades']}  DSR {fmt_num(r['dsr'], 3)}  failed: {r['failed'] or '-'}"
        )
    out.append("")
    out.append("Closest to eligible (fewest failed go-live conditions, DSR aside, then MAR):")
    rows = conn.execute("SELECT * FROM trials WHERE window = 'dev' AND mar IS NOT NULL").fetchall()

    def misses(r) -> list[str]:
        # The row, not its `failed` string. `trials` is append-only, so that string names the
        # bars in force on the run date -- "DSR >= 0.95", "max DD <= 15%" -- and both have since
        # moved. `store.owner_failures` re-derives the four threshold conditions from this row's
        # recorded columns against the bars in force now, and carries `owner inputs`.
        return list(store.owner_failures(r))

    for r in sorted(rows, key=lambda r: (len(misses(r)), -r["mar"], r["n"]))[:8]:
        out.append(
            f"  {r['candidate_id']:<28} misses {len(misses(r))}: {'; '.join(misses(r)) or '-'}  "
            f"CAGR {fmt_signed_pct(r['cagr'])} vs {fmt_signed_pct(r['spy_tr_cagr'])}  maxDD "
            f"{fmt_pct(r['max_drawdown'])}  PF {fmt_pf(r['profit_factor'])}  trades {r['trades']}  DSR {fmt_num(r['dsr'], 3)}"
        )
    for title, status in (("Backlog (idea)", "idea"), ("Blocked on data", "blocked-data"),
                          ("Dev-eligible", "dev-eligible"), ("Promoted (pre-registered)", "promoted"),
                          ("Test-passed", "test-passed"), ("Test-failed", "test-failed")):
        rows = conn.execute("SELECT * FROM methods WHERE status = ? ORDER BY id", (status,)).fetchall()
        if rows:
            out.append("")
            out.append(f"{title}:")
            for m in rows:
                extra = f" [needs: {m['blocked_on']}]" if m["blocked_on"] else ""
                out.append(f"  {m['id']} {m['name']} ({m['family']}, {m['source_kind']}){extra}")
    out.append("")
    out.append("Latest insights:")
    for i in conn.execute("SELECT * FROM insights ORDER BY id DESC LIMIT 8"):
        out.append(f"  [{i['kind']}] {i['title']}" + (f" ({i['method_id']})" if i["method_id"] else ""))
    out.append("")
    out.append("Latest verdicts:")
    for m in conn.execute(
        "SELECT * FROM methods WHERE verdict <> '' AND id GLOB 'M*' ORDER BY updated DESC LIMIT 8"
    ):
        out.append(f"  {m['id']} {m['name']}: {m['verdict']}")
    print("\n".join(out))
    return 0


def _show(conn, args) -> int:
    m = store.get_method(conn, args.method)
    if m is None:
        raise store.LabError(f"no method {args.method}")
    print(f"{m['id']} {m['name']}  [{m['status']}]  family {m['family']}  source {m['source_kind']} {m['source_ref']}")
    if m["parent_id"]:
        print(f"parent: {m['parent_id']}")
    print(f"\nHypothesis:\n{m['hypothesis']}\n")
    if m["blocked_on"]:
        print(f"Blocked on: {m['blocked_on']}\n")
    print("Trials:")
    for t in store.trials_of(conn, m["id"]):
        print(
            f"  #{t['n']} {t['candidate_id']} [{t['window']}] {t['start']}..{t['end']}: return "
            f"{fmt_signed_pct(t['total_return'])} vs SPY TR {fmt_signed_pct(t['spy_tr_return'])}, CAGR "
            f"{fmt_signed_pct(t['cagr'])}, maxDD {fmt_pct(t['max_drawdown'])}, PF {fmt_pf(t['profit_factor'])}, "
            f"trades {t['trades']}, Sharpe {fmt_num(t['sharpe'])}, MAR {fmt_num(t['mar'])}, DSR "
            f"{fmt_num(t['dsr'], 3)} (N={t['n_trials_at_run']}), worst year {t['worst_year']} "
            f"{fmt_signed_pct(t['worst_year_return'])}; {'ELIGIBLE' if t['eligible'] else 'failed: ' + t['failed']}"
        )
    if m["verdict"]:
        print(f"\nVerdict: {m['verdict']}")
    if m["analysis"]:
        print(f"\nAnalysis:\n{m['analysis']}")
    return 0


def _run(conn, args) -> int:
    from seer_engine.lab import runner
    from seer_engine.lab.method import discover

    methods = discover()
    if args.method not in methods:
        raise store.LabError(f"no method file for {args.method} in seer_engine/lab/methods/")
    method, path = methods[args.method]
    runner.preflight(conn, method, path)
    if research.DEV_END != dev.DEV_END:
        raise store.LabError("research.DEV_END differs from dev.DEV_END; refusing to run")
    t0 = time.perf_counter()
    try:
        data = research.load_store(Path(args.store))
    except FileNotFoundError as e:
        raise store.LabError(
            f"research store {args.store} is missing {e.filename or e}; build it with "
            "`python -m seer_engine research_store`"
        ) from e
    log.info("research store %s loaded (%.1fs)", data.fingerprint[:12], time.perf_counter() - t0)
    # The second checkpoint: runner.preflight ran before the store existed and could not see the
    # panel. Nothing here is reached for a price-only method.
    floor = float(getattr(args, "allow_coverage", coverage.MIN_DEV_COVERAGE))
    cov = runner.preflight_data(data, method, min_coverage=floor)
    if cov is not None:
        print(coverage.format_report(cov, floor=floor))
        if floor < coverage.MIN_DEV_COVERAGE:
            print(
                f"--allow-coverage {floor:.2f}: {method.id} runs against a panel that can rank on "
                f"{cov.fraction:.1%} of the dev window, below the "
                f"{coverage.MIN_DEV_COVERAGE:.0%} floor. These trials measure the panel, not the "
                "hypothesis, and the method id is spent either way."
            )
    ran = runner.run_method(conn, method, path, data, git_sha=runner.git_head(config.REPO_ROOT))
    status = store.get_method(conn, method.id)["status"]
    log.info("%s: %d trial(s) recorded, status %s (%.1fs)", method.id, len(ran), status, time.perf_counter() - t0)
    _show(conn, argparse.Namespace(method=method.id))
    print(f"\nLab N (dev trials) is now {store.dev_trial_count(conn)}; test-window looks used: {store.test_looks(conn)}")
    return 0


def _promote(conn, args) -> int:
    """`lab promote M0007`: pre-register the best dev-eligible variant and move it to promoted.

    Writes one markdown file and one status transition. It loads no research store, runs no
    backtest and inserts no trial, so the test-window look count it prints is the one it found.

    Like every other `lab` subcommand, the global `--dry-run` is ignored: there is no roll-back
    half of this to show, and a dry run that printed a pre-registration without writing it would
    be exactly the artefact design §3 exists to prevent.
    """
    from seer_engine.lab import prereg
    from seer_engine.lab.runner import git_head

    done = prereg.promote_method(
        conn,
        args.method,
        git_sha=git_head(config.REPO_ROOT),
        directory=None if args.dir is None else Path(args.dir),
    )
    p = done.prereg
    rel = prereg.repo_path(done.path)
    print(f"wrote {rel}" if done.wrote_file else f"{rel} already pre-registers {p.candidate}")
    print(f"{p.method} is {done.status}" + ("" if done.moved_status else " (already)"))
    print(f"  candidate      {p.candidate}  (dev trial #{p.dev_trial})")
    print(f"  config digest  {p.config_digest}")
    print(f"  dev window     {p.dev_window}  MAR {p.mar}  DSR {p.dsr} at N = {p.n_trials_at_run}")
    print(f"  test window    {p.test_window}")
    print(f"  gate           {p.gate}")
    print()
    print(f"Commit and push {rel} before the look is spent (design §3):")
    print(f"    git add {rel}")
    print(f"    git commit -m 'lab: pre-register {p.candidate} for the test window'")
    print(f"    python -m seer_engine lab test {p.candidate}")
    print(f"\ntest-window looks used: {store.test_looks(conn)}")
    return 0


def _reevaluate(conn, args) -> int:
    """`lab reevaluate [M0022 ...]`: re-judge recorded dev trials against the current luck bar
    and move anything the moved bars were blocking to dev-eligible.

    No research store is loaded, no backtest runs, no trial row is inserted: this reads the dev
    trials the lab already has, re-decides every condition for each, and takes at most the one
    edge `rejected -> dev-eligible`. The test window is not touched and the look count it prints
    is the one it found.

    Every trial with a recorded DSR is re-judged **at the gate's current N**, either exactly from
    `trial_moments` or by re-evaluating the recorded DSR there (`store.dsr_at`). A trial whose
    DSR cannot be evaluated at all -- the 54 P7a seed rows, whose `dsr` is NULL by construction --
    fails the luck test, exactly as a new trial with no computable DSR does, and is counted and
    named per method rather than passed over in silence.

    Neither the threshold nor the policy is a flag: the write path always uses `store.DSR_MIN`
    and `store.DSR_POLICY`, so the gate cannot be loosened per invocation. To see what another
    policy would say without changing anything, use the read-only `lab luck`.

    The pairing is deliberate and the names are deliberately not neighbours: **`lab reevaluate`
    writes** (it can move a method across `rejected -> dev-eligible`) and **`lab luck` reads**
    (it prints the gate's state and its sensitivity to N, and touches nothing).

    Like every other `lab` subcommand, the global `--dry-run` is ignored. The whole sweep is one
    transaction: either every method it unblocks moves, or none does.
    """
    store.begin_immediate(conn)
    with conn:
        results = store.reevaluate(conn, args.method or None)
    if not results:
        print("nothing to re-evaluate: no method reads rejected")
        return 0
    g = results[0].gate
    print(f"luck bar: {store.DSR_LABEL}   N policy: {g.policy}, N = {g.n}   "
          f"({store.dev_trial_count(conn)} dev trial rows on the books)")
    print()
    moved = 0
    for r in results:
        if r.moved:
            moved += 1
            print(f"  {r.method_id}: {r.status_before} -> {r.status_after}  "
                  f"({', '.join(r.unblocked)})")
        elif r.dev_trials == 0:
            print(f"  {r.method_id}: no dev trial (dropped before running); unchanged")
        elif r.derived == 0:
            print(f"  {r.method_id}: none of its {r.dev_trials} dev trial(s) has an evaluable "
                  f"DSR (the P7a seed recorded none), so each fails the luck test and the "
                  f"verdict is unchanged ({r.status_before})")
        else:
            extra = (
                "" if r.unjudgeable == 0
                else f" ({r.unjudgeable} have no recorded DSR and so fail the luck test)"
            )
            print(f"  {r.method_id}: re-judged {r.derived} of {r.dev_trials} dev trial(s) at "
                  f"N = {r.gate.n} against {store.DSR_LABEL}{extra}; still {r.status_before}")
    print()
    print(f"{moved} method(s) moved rejected -> dev-eligible; "
          f"test-window looks used: {store.test_looks(conn)}")
    if moved:
        # `export-json`, not `stage`: `lab stage` also `git add`s, and the swarm shares one
        # worktree, so this phase stages its own path allowlist by hand (Decision D10).
        print("Re-export the web snapshot with "
              "`python -m seer_engine lab export-json`, and commit it with lab/lab.sqlite.")
    return 0


def _test_plan(method, candidate, pre, store_dir: Path) -> str:
    """What ``lab test`` would do, printed by ``--dry-run``. Nothing is loaded or run.

    ``pre`` is a ``lab.prereg.Prereg`` (phase 3): every field is a ``str`` and it carries no
    path, so the file is named with ``prereg.path_for(pre.method)``.
    """
    from seer_engine.lab.method import config_digest
    from seer_engine.lab.prereg import path_for, repo_path

    return "\n".join((
        f"lab test {candidate.id}  (dry run: nothing is loaded, run or recorded)",
        "",
        f"  method            {method.id} {method.name}  [promoted]",
        f"  variant           {candidate.id}  rules {candidate.rules.id}  allocator "
        f"<{candidate.allocator.id}>",
        f"  config digest     {config_digest(candidate)}",
        f"  pre-registration  {repo_path(path_for(pre.method))}  (committed; digest "
        f"{pre.config_digest[:12]})",
        f"  pre-registered    {pre.candidate} on {pre.date}, for the test window {pre.test_window}",
        f"  test store        {store_dir}",
        "",
        "  the verdict is the five design §1 go-live conditions on the test window:",
        "    " + ", ".join(dev.FAILURE_LABELS),
        "  DSR is recorded, not a condition: the look is pre-registered, so there is nothing to",
        "  deflate. The lab's N does not move -- a test trial is a look, not a search.",
        "",
        "  on a pass  -> test-passed (final), and the promote command is printed",
        "  on a fail  -> test-failed (final)",
        "",
        "  Run it for real without --dry-run. There is exactly one look per configuration and the",
        "  database refuses a second.",
    ))


def _gate_note(conn, tested) -> str:
    """The honest backtest-gate sentence for ``promote --gate-note``.

    Every roster entry's gate note says what the backtest gate actually did; no entry has ever
    passed one. A method that reaches here is the first kind that can say otherwise, and the
    sentence says exactly what it passed and what it still has not: forward paper time.
    """
    t = tested.trial
    d = conn.execute(
        "SELECT * FROM trials WHERE config_digest = ? AND window = 'dev'", (t.config_digest,)
    ).fetchone()
    dev_part = (
        "no recorded dev trial"
        if d is None
        else (f"dev window {d['start']}..{d['end']}: MAR {fmt_num(d['mar'])}, DSR "
              f"{fmt_num(d['dsr'], 3)} at N={d['n_trials_at_run']}, all five conditions met")
    )
    test_part = (
        f"test window {t.start}..{t.end}, one pre-registered look: return "
        f"{fmt_signed_pct(t.total_return)} vs SPY TR {fmt_signed_pct(t.spy_tr_return)}, max DD "
        f"{fmt_pct(t.max_drawdown)}, PF {fmt_pf(t.profit_factor)}, {t.trades} trades, MAR "
        f"{fmt_num(t.mar)} -- all five conditions met"
    )
    return (
        f"Passed the quant backtest gate. {dev_part}; {test_part}. No forward paper record yet: "
        f"design §1 still needs >= 3 months and >= 100 closed paper trades before real money."
    )


def _promote_argv(method, tested, *, roster_id: str, gate_note: str, lab_db: Path) -> list[str]:
    """The exact ``promote`` command for a passed method. Pure: builds argv, runs nothing.

    ``lab test`` does not call ``commands/promote.py`` in-process. It reads a research store and a
    SQLite file and must stay offline; ``promote`` opens Neon, and the two writes cannot share a
    transaction (``promote.py`` module docstring). Design §6's "never ask" is satisfied by the
    skill running this line immediately, which is what it does.
    """
    sub = method.hypothesis.strip().splitlines()[0].strip()
    if len(sub) > 80:
        sub = sub[:77].rstrip() + "..."
    return [
        "python", "-m", "seer_engine", "promote",
        "--method", method.id,
        "--candidate", tested.trial.candidate_id,
        "--id", roster_id,
        "--name", f"{roster_id} · {method.name}",
        "--sub", sub,
        "--gate-note", gate_note,
        "--lab-db", str(lab_db),
    ]


def _verdict_report(conn, method, tested, *, roster_id: str, lab_db: Path) -> str:
    """What the owner (or the skill) reads after the look: the verdict and the one next step."""
    import shlex

    t = tested.trial
    head = [
        "",
        f"{t.candidate_id} on the test window {t.start}..{t.end}: {tested.status.upper()}",
        f"  return {fmt_signed_pct(t.total_return)} vs SPY TR {fmt_signed_pct(t.spy_tr_return)}, "
        f"CAGR {fmt_signed_pct(t.cagr)}, maxDD {fmt_pct(t.max_drawdown)}, "
        f"PF {fmt_pf(t.profit_factor)}, trades {t.trades}, MAR {fmt_num(t.mar)}",
        f"  DSR {fmt_num(t.dsr, 3)} at N={t.n_trials_at_run} (recorded, not a condition)",
    ]
    if tested.status == "test-failed":
        return "\n".join(head + [
            f"  failed: {t.failed}",
            "",
            "test-failed is final. There is no second look at this configuration, on any window.",
            "Queue a variation (lab idea --source-kind variation --parent "
            f"{method.id} ...) if the evidence supports one, and journal what the test window said",
            "that the dev window did not.",
        ])
    argv = _promote_argv(method, tested, roster_id=roster_id,
                         gate_note=_gate_note(conn, tested), lab_db=lab_db)
    return "\n".join(head + [
        "",
        "test-passed. Next, without asking anyone (design §6): put it on the paper roster under a",
        "new id with its own clock, then stage and commit the lab.",
        "",
        f"  {shlex.join(argv)}",
        "",
        "  lab stage      # writes web/data/lab.json and git-adds it with the database",
        "",
        "promote writes the roster row with no paper_start, so the next paper night freezes the",
        "spec and starts the clock there: the paper record begins at the promotion and claims",
        "nothing earlier. Real money still needs all of design §1.",
    ])


def _test(conn, args) -> int:
    """``lab test <candidate>``: the one counted look at the test window (design §3)."""
    from seer_engine.lab import runner

    method, path, candidate = runner.resolve_candidate(args.candidate)
    store_dir = Path(args.store)
    pre = runner.preflight_test(conn, method, path, candidate)
    if args.dry_run:
        print(_test_plan(method, candidate, pre, store_dir))
        return 0
    t0 = time.perf_counter()
    # Phase 2's idiom: ask the store which window it is for, then ask load_store for exactly
    # that one. load_store compares the two before it reads a single data file, so a dev store
    # here is refused by name; the `window.name != "test"` test below is the second of the two
    # independent noes `run_test` wants, and it names the fix.
    try:
        window = research.declared_window(store_dir)
        if window.name != "test":
            raise store.LabError(
                f"{store_dir} declares the {window.name} window; `lab test` needs the test-window "
                f"store. Build it with `python -m seer_engine research_store --test-window` and "
                f"point --store at {research.TEST_STORE_DIR}"
            )
        data = research.load_store(store_dir, window=window)
    except FileNotFoundError as e:
        raise store.LabError(
            f"test-window research store {store_dir} is missing {e.filename or e}; build it with "
            f"`python -m seer_engine research_store --test-window --store {store_dir}`"
        ) from e
    except ValueError as e:
        raise store.LabError(f"{store_dir}: {e}") from e
    log.info("test store %s loaded, window %s..%s (%.1fs)", data.fingerprint[:12],
             data.window.start, data.window.end, time.perf_counter() - t0)
    tested = runner.run_test(conn, method, path, candidate, data,
                             git_sha=runner.git_head(config.REPO_ROOT))
    _show(conn, argparse.Namespace(method=method.id))
    print(_verdict_report(conn, method, tested,
                          roster_id=args.roster_id or method.id, lab_db=Path(args.db)))
    print(f"\nLab N (dev trials) is still {store.dev_trial_count(conn)}; "
          f"test-window looks used: {store.test_looks(conn)}")
    return 0


def _remeasure(conn, args) -> int:
    """``lab remeasure M0022``: recover the DSR inputs of trials recorded before they were kept.

    Re-runs the method's recorded variants on the **dev** window through the same
    ``dev.run_registry`` path ``lab run`` uses, proves the re-run reproduces each trial's recorded
    Sharpe and DSR, and appends ``trial_moments`` rows -- nothing else. No ``trials`` row is
    inserted, updated or deleted; no status moves; no pre-registration is written.

    The test window is unreachable from here by construction, not by care: a method with a
    ``window='test'`` trial is refused by ``remeasure.preflight`` before this function opens
    anything, ``research.load_store`` is called with no ``window`` so it defaults to ``DEV_WINDOW``
    and refuses a test store by name, and ``remeasure.measure`` refuses a loaded store that is not
    the dev window and calls ``dev.run_registry`` with no window argument at all.

    When every dev trial already has its moments, this prints what it skipped and returns without
    loading a research store: re-loading a 135 MB store and re-running backtests to write nothing
    is not idempotence. (For scale, measured: the store load is ~11s and all 54 P7a seed
    candidates re-run in ~52s. A method's two to five variants are seconds. Nothing here is an
    hours-long job, and no doc in this set may say it is.)
    """
    from seer_engine.lab import remeasure as rm

    if rm.is_seed_id(args.method):
        return _remeasure_seed(conn, args)
    method, path = rm.resolve_method(args.method)
    plan = rm.preflight(conn, method, path)
    if plan.nothing_to_do:
        print(f"{method.id}: every dev trial already has its moments; nothing to do.")
        print("  already recorded: " + ", ".join(f"#{n}" for n in plan.present))
        print(f"\nLab N (dev trials) is still {store.dev_trial_count(conn)}; "
              f"test-window looks used: {store.test_looks(conn)}")
        return 0
    if research.DEV_END != dev.DEV_END:
        raise store.LabError("research.DEV_END differs from dev.DEV_END; refusing to run")
    t0 = time.perf_counter()
    try:
        data = research.load_store(Path(args.store))
    except FileNotFoundError as e:
        raise store.LabError(
            f"research store {args.store} is missing {e.filename or e}; build it with "
            "`python -m seer_engine research_store`"
        ) from e
    except ValueError as e:
        raise store.LabError(
            f"{args.store}: {e}. `lab remeasure` asks load_store for the dev window and nothing "
            f"else, so a test-window store is refused here rather than re-measured"
        ) from e
    log.info("research store %s loaded (%.1fs)", data.fingerprint[:12], time.perf_counter() - t0)
    report = rm.remeasure(conn, method, path, data)
    print(rm.format_report(report))
    print(f"\nLab N (dev trials) is still {store.dev_trial_count(conn)}; "
          f"test-window looks used: {store.test_looks(conn)}")
    return 0


def _remeasure_seed(conn, args) -> int:
    """``lab remeasure H-P7A``: give the 54 P7a seed trials their DSR inputs, and say what follows.

    The lab's first 54 dev trials were imported from P7a's report files as summary rows, so their
    daily moments were never captured and ``trials.dsr`` is NULL for every one. They count toward
    N all the same -- 54 of the lab's 110 dev trials -- so they pay the full multiple-testing
    penalty and, under the rule that a DSR which cannot be evaluated fails the luck test, can
    never pass it. This re-runs them out of the frozen registry so the luck test they pay for is
    one they actually receive.

    **It writes ``trial_moments`` rows and nothing else.** No ``trials`` row is inserted, updated
    or deleted; ``trials.dsr`` stays NULL on these rows forever; no ``methods.status`` moves; no
    pre-registration is written. The verdict is not recorded here -- it is phase 4's
    ``store.verdict`` computing it from the moments at the current gate N, which is why there is
    no DSR backfill and why re-running this command can never change a recorded number.

    **N does not move.** Adding ``trial_moments`` rows adds no ``trials`` row, so
    ``store.dev_trial_count`` and ``npolicy.effective_n(conn, "all-trials")`` read the same before
    and after; and ``store.dev_daily_sharpes`` reads ``trials.sharpe``, which these rows already
    carry, so the trial-Sharpe variance does not move either. Both are printed at the end, before
    and after, so the invariant is visible rather than merely asserted in a test.

    The test window is unreachable from here by construction, not by care: ``seed_preflight``
    refuses before anything is opened if any seed family has a test trial, ``research.load_store``
    is called with no ``window`` so it defaults to ``DEV_WINDOW`` and refuses a test store by name,
    and ``remeasure_seed`` refuses a loaded store that is not the dev window and reaches
    ``dev.run_registry`` through ``run_chunk``, which has no window argument at all.

    Exit 0 when every re-run reproduced; **1 when any trial diverged** and was therefore not
    written -- the run is not a failure (the rest were written and the finding is printed per
    trial), but it is not a clean success either and an unattended caller should notice.
    """
    from seer_engine.lab import npolicy, remeasure as rm

    only = tuple(x for x in (args.only or "").split(",") if x.strip())
    plan = rm.seed_preflight(conn, args.method, only=only)
    n_before = store.dev_trial_count(conn)
    var_before = store.dev_sharpe_variance(conn)
    if plan.nothing_to_do:
        print(f"{plan.method_id}: every seed trial already has its moments; nothing to do.")
        print("  already recorded: " + ", ".join(f"#{n}" for n in plan.present))
        print(f"\nLab N (dev trials) is still {n_before}; test-window looks used: "
              f"{store.test_looks(conn)}")
        return 0
    if research.DEV_END != dev.DEV_END:
        raise store.LabError("research.DEV_END differs from dev.DEV_END; refusing to run")
    t0 = time.perf_counter()
    try:
        data = research.load_store(Path(args.store))
    except FileNotFoundError as e:
        raise store.LabError(
            f"research store {args.store} is missing {e.filename or e}; build it with "
            "`python -m seer_engine research_store`"
        ) from e
    except ValueError as e:
        raise store.LabError(
            f"{args.store}: {e}. `lab remeasure` asks load_store for the dev window and nothing "
            f"else, so a test-window store is refused here rather than re-measured"
        ) from e
    log.info("research store %s loaded (%.1fs)", data.fingerprint[:12], time.perf_counter() - t0)
    log.info(
        "re-measuring %d seed trial(s); the P7a trials recorded store %s, this store is %s",
        len(plan.todo), "5451195f", data.fingerprint[:8],
    )

    def progress(index: int, total: int, written: int, blocked: int) -> None:
        log.info("chunk %d/%d committed: %d written, %d blocked", index, total, written, blocked)

    report = rm.remeasure_seed(conn, plan, data, chunk=args.chunk, on_chunk=progress)
    print(rm.format_seed_report(conn, report, rm.seed_verdicts(conn, report)))
    n_after = store.dev_trial_count(conn)
    var_after = store.dev_sharpe_variance(conn)
    print(
        f"\nLab N (dev trials): {n_before} before, {n_after} after "
        f"({npolicy.effective_n(conn, 'all-trials').n} under the all-trials policy); "
        f"trial-Sharpe variance: {var_before!r} before, {var_after!r} after; "
        f"test-window looks used: {store.test_looks(conn)}"
    )
    return 1 if report.blocked else 0


def _idea(conn, args) -> int:
    store.begin_immediate(conn)  # the next id and its insert, atomic against parallel sessions
    with conn:
        mid = store.next_method_id(conn)
        store.add_method(
            conn, id=mid, name=args.name, family=args.family, source_kind=args.source_kind,
            source_ref=args.source_ref, hypothesis=args.hypothesis, parent_id=args.parent,
        )
    print(mid)
    return 0


def _note(conn, args) -> int:
    if args.file is None and args.verdict is None:
        raise store.LabError("give --file and/or --verdict")
    with conn:
        if args.file is not None:
            store.append_analysis(conn, args.method, Path(args.file).read_text(encoding="utf-8"))
        if args.verdict is not None:
            store.update_method(conn, args.method, verdict=args.verdict.strip())
    return 0


def _block(conn, args) -> int:
    with conn:
        store.update_method(conn, args.method, status="blocked-data", blocked_on=args.on.strip())
    return 0


def _drop(conn, args) -> int:
    with conn:
        store.update_method(conn, args.method, status="rejected", verdict=f"dropped before running: {args.why.strip()}")
    return 0


def _seen(conn, args) -> int:
    if args.find is not None:
        for r in store.seen(conn, args.find):
            print(f"{r['key']}\t{r['method_id'] or '-'}\t{r['note']}")
        return 0
    if not args.key:
        raise store.LabError("give a KEY to record, or --find TEXT")
    with conn:
        added = store.mark_seen(conn, args.key, args.method, args.note)
    print("added" if added else "already seen")
    return 0


def _insight(conn, args) -> int:
    if (args.body is None) == (args.file is None):
        raise store.LabError("give exactly one of --body or --file")
    body = args.body if args.body is not None else Path(args.file).read_text(encoding="utf-8")
    with conn:
        n = store.add_insight(conn, kind=args.kind, title=args.title, body=body, method_id=args.method)
    print(n)
    return 0


def _stage(conn, args) -> int:
    """Write the web snapshot and ``git add`` it with the database, both while holding an
    exclusive lock: a parallel session's half-written transaction can never be what gets
    committed, and the staged ``web/data/lab.json`` is always the export of the staged database.
    The snapshot goes beside the database's own repo (``store.snapshot_path``), so a worktree
    session with ``SEER_LAB_DB`` stages both files in the checkout that owns the database."""
    import subprocess

    path = Path(args.db).resolve()
    snap = store.snapshot_path(path)
    conn.execute("BEGIN EXCLUSIVE")
    try:
        store.write_snapshot(conn, snap)
        out = subprocess.run(
            ["git", "add", "--", str(path), str(snap)], cwd=path.parent, capture_output=True, text=True
        )
    finally:
        conn.rollback()
    if out.returncode != 0:
        raise store.LabError(f"git add {path} {snap} failed: {out.stderr.strip()}")
    print(f"staged {path}")
    print(f"staged {snap}")
    return 0


def _next_id(conn, args) -> int:
    print(store.next_method_id(conn))
    return 0


def _export(conn, args) -> int:
    path = store.export_xlsx(conn, args.out)
    print(path)
    return 0


def _export_json(conn, args) -> int:
    path = Path(args.out) if args.out is not None else store.snapshot_path(args.db)
    if not store.write_snapshot(conn, path):
        log.info("%s already up to date", path)
    print(path)
    return 0


def _seed(conn, args) -> int:
    from seer_engine.lab.seed import seed

    n = seed(conn)
    print(f"seeded {n} trials; N = {store.dev_trial_count(conn)}")
    return 0


_HANDLERS = {
    "status": _status,
    "show": _show,
    "run": _run,
    "promote": _promote,
    "reevaluate": _reevaluate,
    "test": _test,
    "remeasure": _remeasure,
    "idea": _idea,
    "note": _note,
    "block": _block,
    "drop": _drop,
    "seen": _seen,
    "insight": _insight,
    "stage": _stage,
    "next-id": _next_id,
    "export": _export,
    "export-json": _export_json,
    "seed": _seed,
}
