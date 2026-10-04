"""`lab`: the method lab (docs/plans/2026-10-04-method-lab-design.md).

    lab status                      N, test looks, near misses, backlog, blocked ideas
    lab show M0007                  one method and its trials
    lab run M0007 [--store DIR]     run a committed method on the dev window, record its trials
    lab idea --name ... --hypothesis ...   queue an idea (prints its id)
    lab note M0007 --file F [--verdict V]  append analysis / set the verdict
    lab block M0007 --on "what data"       an idea the store cannot test
    lab drop M0007 --why "..."             an idea dropped before running
    lab seen KEY [--method M] [--note N] | lab seen --find TEXT
    lab next-id                     the next free method id
    lab export [--out F]            the lab as an xlsx workbook (gitignored)
    lab seed                        one-time import of the pre-lab record

Exit 0 on success; 2 when the lab's rules refuse the request; 1 on any other error.
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from seer_engine import config, research
from seer_engine.backtest import dev
from seer_engine.backtest.metrics import fmt_num, fmt_pct, fmt_pf, fmt_signed_pct
from seer_engine.lab import store

log = logging.getLogger(__name__)

HELP = "The method lab: run, record and review strategy experiments (lab/lab.sqlite)"


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--db", type=Path, default=store.DB_PATH, help="lab database (default: lab/lab.sqlite)")
    sub = p.add_subparsers(dest="lab_command", metavar="<lab command>", required=True)

    sub.add_parser("status", help="the lab at a glance")
    s = sub.add_parser("show", help="one method and its trials")
    s.add_argument("method")

    s = sub.add_parser("run", help="run a committed method on the dev window")
    s.add_argument("method")
    s.add_argument("--store", type=Path, default=research.STORE_DIR)

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

    sub.add_parser("next-id", help="the next free method id")
    s = sub.add_parser("export", help="write the lab as an xlsx workbook")
    s.add_argument("--out", type=Path, default=store.XLSX_PATH)
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
    for title, status in (("Backlog (idea)", "idea"), ("Blocked on data", "blocked-data"),
                          ("Dev-eligible / promoted", "dev-eligible"), ("Promoted", "promoted")):
        rows = conn.execute("SELECT * FROM methods WHERE status = ? ORDER BY id", (status,)).fetchall()
        if rows:
            out.append("")
            out.append(f"{title}:")
            for m in rows:
                extra = f" [needs: {m['blocked_on']}]" if m["blocked_on"] else ""
                out.append(f"  {m['id']} {m['name']} ({m['family']}, {m['source_kind']}){extra}")
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
    ran = runner.run_method(conn, method, path, data, git_sha=runner.git_head(config.REPO_ROOT))
    status = store.get_method(conn, method.id)["status"]
    log.info("%s: %d trial(s) recorded, status %s (%.1fs)", method.id, len(ran), status, time.perf_counter() - t0)
    _show(conn, argparse.Namespace(method=method.id))
    print(f"\nLab N (dev trials) is now {store.dev_trial_count(conn)}; test-window looks used: {store.test_looks(conn)}")
    return 0


def _idea(conn, args) -> int:
    mid = store.next_method_id(conn)
    with conn:
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


def _next_id(conn, args) -> int:
    print(store.next_method_id(conn))
    return 0


def _export(conn, args) -> int:
    path = store.export_xlsx(conn, args.out)
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
    "idea": _idea,
    "note": _note,
    "block": _block,
    "drop": _drop,
    "seen": _seen,
    "next-id": _next_id,
    "export": _export,
    "seed": _seed,
}
