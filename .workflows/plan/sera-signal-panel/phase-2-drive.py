"""Phase 2 proof drive: record panels in a COPY of a lab database, print the published verdicts,
then export the snapshot through the real `lab export-json` CLI and print its `panel` block.

usage: PYTHONPATH=<worktree>/engine/src python phase-2-drive.py SOURCE_DB OUT_DIR --crowd twins|nulls

SOURCE_DB is opened read-only (sqlite backup into OUT_DIR/lab.sqlite) and never written.
--crowd twins  adds 30 panels with S0003's exact pick set: the correction still counts 3 sets.
--crowd nulls  adds 30 distinct do-nothing panels: the correction counts 33 sets.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from seer_engine.lab import panel_verdict, store

DEV_FP, SV_FP = "dev-fp-proof", "sv-fp-proof"


def rows(sid, *, role, fp, t, slope, recent, picks, ic=True):
    return [
        store.PanelResultRow(
            signal_id=sid, rule_id=panel_verdict.RULE_ID, store_role=role, store_fingerprint=fp,
            era=era, months=200 if era == "all" else 100, mean_pool=480.0, mean_scored=470.0,
            ic_mean=0.02 if ic else None, ic_t=t if ic else None,
            spread_top=recent if era == "2009-2015" else 0.03, spread_t=t, fm_slope=slope,
            fm_t=t, top_turnover=0.3, picks_hash=picks, git_sha="proof",
            measured="2026-11-13T00:00:00+00:00",
        )
        for era in store.PANEL_ERAS
    ]


def record(conn, sid, second, *, t, slope, recent, sv_slope, picks, kind="signal",
           method_id=None, source_kind="knowledge"):
    row = store.PanelSignalRow(
        id=sid, kind=kind, name=f"proof idea {second}", family="proof", hypothesis="h",
        expected_failure="f", source_kind=source_kind, source_ref="", method_id=method_id,
        source_sha="0" * 64, created=f"2026-11-13T00:00:{second:02d}+00:00",
    )
    assert store.insert_panel_signal(conn, row)
    ic = kind == "signal"
    store.insert_panel_results(conn, rows(sid, role="dev", fp=DEV_FP, t=t, slope=slope,
                                          recent=recent, picks=picks, ic=ic))
    store.insert_panel_results(conn, rows(sid, role="survivorship", fp=SV_FP, t=t,
                                          slope=sv_slope, recent=recent, picks=picks, ic=ic))
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source_db")
    ap.add_argument("out_dir")
    ap.add_argument("--crowd", choices=("twins", "nulls"), required=True)
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    db = out / "lab.sqlite"
    db.unlink(missing_ok=True)
    src = sqlite3.connect(f"{Path(args.source_db).resolve().as_uri()}?mode=ro", uri=True)
    dst = sqlite3.connect(db)
    src.backup(dst)
    src.close()
    dst.close()

    conn = store.connect(db)
    arm = conn.execute(
        "SELECT t.candidate_id, t.method_id, m.source_kind FROM trials t "
        "JOIN methods m ON m.id = t.method_id WHERE t.window = 'dev' AND m.family LIKE 'stock-%' "
        "ORDER BY t.n LIMIT 1"
    ).fetchone()
    trials_before = conn.execute("SELECT count(*) FROM trials").fetchone()[0]
    store.begin_immediate(conn)
    first = record(conn, "S0001", 1, t=4.0, slope=0.004, recent=0.03, sv_slope=0.003, picks="A")
    record(conn, "S0002", 2, t=4.0, slope=0.004, recent=0.03, sv_slope=0.003, picks="A")
    record(conn, "S0003", 3, t=2.2, slope=0.002, recent=0.01, sv_slope=0.001, picks="C")
    for i in range(4, 34):
        if args.crowd == "twins":
            record(conn, f"S{i:04d}", i, t=2.2, slope=0.002, recent=0.01, sv_slope=0.001, picks="C")
        else:
            record(conn, f"S{i:04d}", i, t=0.0, slope=0.0, recent=0.0, sv_slope=0.0,
                   picks=f"N{i}")
    record(conn, str(arm["candidate_id"]), 34, t=0.0, slope=0.0, recent=0.0, sv_slope=0.0,
           picks="R", kind="replay", method_id=str(arm["method_id"]),
           source_kind=str(arm["source_kind"]))
    conn.commit()
    print("repeat insert of S0001 ->", store.insert_panel_signal(conn, first))
    print("trials before", trials_before, "after", conn.execute("SELECT count(*) FROM trials").fetchone()[0])
    print("panel_signals", len(store.panel_signals(conn)), "panel_results", len(store.panel_results(conn)))
    for sid, v in panel_verdict.published(conn).items():
        if sid in ("S0001", "S0002", "S0003", "S0004", "S0033") or sid == arm["candidate_id"]:
            q = "-" if v.q is None else f"{v.q:.4f}"
            print(f"{sid} clears={v.clears} q={q} twin_of={v.twin_of} reasons={' | '.join(v.reasons)}")
    conn.close()

    env = dict(os.environ, SEER_LAB_DB=str(db), SEER_ENV_FILE=str(out / "no.env"))
    code = subprocess.run(
        [sys.executable, "-m", "seer_engine", "lab", "--db", str(db), "export-json",
         "--out", str(out / "lab.json")],
        env=env,
    ).returncode
    print("export-json exit", code)
    snap = json.loads((out / "lab.json").read_text(encoding="utf-8"))
    panel = snap["panel"]
    by = {s["id"]: s for s in panel["signals"]}
    rid = str(arm["candidate_id"])
    print("version", snap["version"], "last key", list(snap)[-1])
    print("rule", panel["rule"], "fdr", panel["fdr"], "signals", len(panel["signals"]))
    print("first ranked", panel["signals"][0]["id"], "clears", panel["signals"][0]["clears"])
    print("S0002 twinOf", by["S0002"]["twinOf"], "S0003 clears", by["S0003"]["clears"])
    print("S0001 dev eras", list(by["S0001"]["dev"]))
    print("replay", rid, "kind", by[rid]["kind"], "methodId", by[rid]["methodId"],
          "ic", by[rid]["dev"]["all"]["ic"])
    return 0 if code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
