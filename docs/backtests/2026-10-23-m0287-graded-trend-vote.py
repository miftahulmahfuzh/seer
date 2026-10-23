"""M0287's analysis: what does GRADING a trend gate cost, once the centre is held fixed?

Six arms, both stores, net and gross of Gotrade's fees, era by era, with realised exposure read
per era rather than taken from the whole-window average a trial records.

Report only: no trial, no look, N unchanged. ``lab.sqlite`` is opened read-only, for the recorded
contributions, the recorded capital and the shared SPY benchmark curve.

    PYTHONPATH=engine/src engine/.venv/bin/python \
        docs/backtests/2026-10-23-m0287-graded-trend-vote.py
"""

from __future__ import annotations

import gc
import os
import sqlite3
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.commands.backtest_dev import month_end_curve
from seer_engine.lab import hardgate, runner, shortfall
from seer_engine.lab import walkforward as wf
from seer_engine.lab.exposure import ERAS, WHOLE
from seer_engine.lab.method import discover

LAB_DB = Path(os.environ.get("SEER_LAB_DB", "/home/miftah/seer/lab/lab.sqlite"))
STORES = (
    ("dev", Path(os.environ.get("SEER_RESEARCH_STORE", "/home/miftah/seer/engine/.research"))),
    ("sv", Path(os.environ.get("SEER_SV_STORE", "/home/miftah/seer/engine/.research-sv"))),
)

#: M0270's measured price of one point of cash on THIS chassis and store, per era, and M0271's
#: price of the same point bought in all-or-nothing EPISODES. Copied, not re-derived.
EVEN_SLOPE = {WHOLE: 0.0623, "1996-2002": 0.0756, "2003-2008": 0.0051, "2009-2015": 0.1732}
EPISODIC_2009 = 0.2832

ARMS = ("M0287-FULL", "M0287-K1", "M0287-K4", "M0287-K8", "M0287-LIT4", "M0287-DIL")
LADDER = ("M0287-K1", "M0287-K4", "M0287-K8")  # the graininess ladder, matched centre
INCUMBENT, FINEST = "M0287-K1", "M0287-K8"
CONFIRM, FALSIFY = 0.3, 1.0  # the pre-registered thresholds on G, copied from the method file


def era_exposure(snapshots, start: date, end: date) -> float:
    vals = [
        float(s.invested_usd) / float(s.equity_usd)
        for s in snapshots[1:]
        if start <= s.date <= end and float(s.equity_usd) > 0.0
    ]
    return sum(vals) / len(vals) if vals else float("nan")


def main() -> None:
    method, _ = discover()["M0287"]
    arms = list(method.all_candidates())

    conn = sqlite3.connect(f"file:{LAB_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    trials = {
        str(r["candidate_id"]): r
        for r in conn.execute(
            "select * from trials where method_id='M0287' and window='dev'"
        ).fetchall()
    }
    if not trials:
        raise SystemExit("M0287 has no recorded dev trial yet")
    any_trial = trials[INCUMBENT]
    contributions = runner.recorded_contributions(conn, int(any_trial["n"]))
    capital = runner.recorded_capital(conn, int(any_trial["n"]))
    bench_curve, bench_n = shortfall.benchmark(conn)
    print(f"capital {capital} IDR   deposits {contributions}")
    print(f"benchmark: the recorded REF-SPY-HOLD dev curve, trial {bench_n}\n")

    table: dict[str, dict[str, dict[str, dict[str, float]]]] = {}
    meta: dict[str, dict[str, dict[str, float]]] = {}

    for store_label, store_dir in STORES:
        data = research.load_store(store_dir)
        free = [
            replace(a, id=f"{a.id}-FREE",
                    rules=replace(a.rules, cost_model="flat", cost_rate=Decimal(0)))
            for a in arms
        ]
        got: dict[str, tuple[object, object]] = {}

        def on_result(_i: int, result: object, row: object, *, _g=got) -> None:
            _g[row.candidate.id] = (result, row)

        dev.run_registry(
            data.market, data.dividends, data.spy_dividends, [*arms, *free],
            on_result=on_result, contributions=contributions, initial_idr=capital,
        )

        print(f"=== {store_label}  store {data.fingerprint[:12]}  "
              f"prices {data.price_fingerprint[:12]} ===")
        hdr = (f"{'arm':20} {'expo%':>7} {'turn':>6} {'fees$':>9} {'money%/yr':>10} "
               f"{'maxDD%':>7} {'PF':>5} {'trades':>7}  reproduces")
        print(hdr)
        print("-" * len(hdr))
        for net in (True, False):
            key = store_label if net else store_label + "-gross"
            table[key], meta[key] = {}, {}
            for a in arms:
                aid = a.id if net else a.id + "-FREE"
                result, row = got[aid]
                m = row.stats.metrics
                curve = month_end_curve(result.snapshots)
                trial = trials[a.id]
                deposits = hardgate.trial_deposits(conn, trial, list(curve))
                y = (m.mwr if m.mwr is not None else m.cagr) * 100.0
                repro = ""
                if net and store_label == "dev":
                    same = abs(float(trial["total_return"]) - m.total_return) < 1e-12
                    repro = f"trial {trial['n']}" + ("" if same else "  !! MISMATCH")
                print(f"{aid:20} {float(row.stats.exposure) * 100:7.3f} "
                      f"{float(row.stats.turnover):6.2f} {float(row.stats.costs_usd):9,.0f} "
                      f"{y:10.3f} {m.max_drawdown * 100:7.3f} "
                      f"{m.profit_factor if m.profit_factor else float('nan'):5.2f} "
                      f"{m.trades:7d}  {repro}")
                cells: dict[str, dict[str, float]] = {}
                for label, s, e in ((WHOLE, row.start, row.end), *ERAS):
                    g = wf.measure(curve, s, e, deposits)
                    r = wf.measure(bench_curve, s, e)
                    if g is None or r is None or g.cagr is None or r.cagr is None:
                        continue
                    cells[label] = {
                        "expo": era_exposure(result.snapshots, s, e) * 100.0,
                        "lead": (g.cagr - r.cagr) * 100.0,
                        "fall": g.max_drawdown * 100.0,
                    }
                table[key][a.id] = cells
                meta[key][a.id] = {"turnover": float(row.stats.turnover),
                                   "fees": float(row.stats.costs_usd),
                                   "trades": float(m.trades),
                                   "expo": float(row.stats.exposure) * 100.0}
            print()
        del data, got
        gc.collect()
    conn.close()

    for key, rows in table.items():
        print(f"=== {key}: every arm, era by era ===")
        for label in (WHOLE, *(l for l, _s, _e in ERAS)):
            if label not in rows[INCUMBENT]:
                continue
            print(f"\n-- {label} --")
            print(f"{'arm':20} {'expo%':>7} {'lead %/yr':>10} {'fall%':>8}")
            for aid in ARMS:
                c = rows[aid][label]
                print(f"{aid:20} {c['expo']:7.3f} {c['lead']:10.3f} {c['fall']:8.3f}")
            k1, k4, k8 = (rows[a][label] for a in LADDER)
            g = k8["lead"] - k1["lead"]
            gap = k8["expo"] - k1["expo"]
            slope = EVEN_SLOPE.get(label)
            corr = f"{-gap * slope:+.3f}" if slope is not None else "n/a"
            print(f"  G = lead(K8) - lead(K1) = {g:+.3f} pts/yr   "
                  f"exposure gap {gap:+.3f} pts, worth {corr} at the era price of cash")
            print(f"  K4 - K1 = {k4['lead'] - k1['lead']:+.3f}   "
                  f"K8 - K4 = {k8['lead'] - k4['lead']:+.3f}   "
                  f"monotone in k: {'yes' if k1['lead'] >= k4['lead'] >= k8['lead'] or k1['lead'] <= k4['lead'] <= k8['lead'] else 'NO'}")
            print(f"  fall spread across the matched ladder: "
                  f"{max(c['fall'] for c in (k1, k4, k8)) - min(c['fall'] for c in (k1, k4, k8)):.3f} pts")
            lit, dil = rows["M0287-LIT4"][label], rows["M0287-DIL"][label]
            print(f"  LIT4 - K4 (centre of gravity, same k) = {lit['lead'] - k4['lead']:+.3f}   "
                  f"LIT4 - DIL (dilution, matched exposure) = {lit['lead'] - dil['lead']:+.3f} "
                  f"at an exposure gap of {lit['expo'] - dil['expo']:+.3f} pts")
            full = rows["M0287-FULL"][label]
            print(f"  the HABIT: K1 - FULL = {k1['lead'] - full['lead']:+.3f} pts/yr, "
                  f"fall {k1['fall'] - full['fall']:+.3f} pts, "
                  f"at {full['expo'] - k1['expo']:.3f} pts of cash")
            if label == "2009-2015":
                cash = full["expo"] - k1["expo"]
                print(f"    cash model: evenly spread {-cash * EVEN_SLOPE[label]:+.3f}, "
                      f"episodic {-cash * EPISODIC_2009:+.3f}, measured "
                      f"{k1['lead'] - full['lead']:+.3f}")
        print()

    print("=== what grading costs, split into churn and market (dev) ===")
    print(f"{'arm':20} {'net':>9} {'gross':>9} {'fee bill':>10} {'turn':>7} {'trades':>7}")
    for aid in ARMS:
        n = table["dev"][aid][WHOLE]["lead"]
        g = table["dev-gross"][aid][WHOLE]["lead"]
        m = meta["dev"][aid]
        print(f"{aid:20} {n:9.3f} {g:9.3f} {g - n:10.3f} {m['turnover']:7.2f} "
              f"{int(m['trades']):7d}")
    gn = table["dev"][FINEST][WHOLE]["lead"] - table["dev"][INCUMBENT][WHOLE]["lead"]
    gg = table["dev-gross"][FINEST][WHOLE]["lead"] - table["dev-gross"][INCUMBENT][WHOLE]["lead"]
    print(f"\n  G net {gn:+.3f}   G gross {gg:+.3f}   fees explain {gn - gg:+.3f} of it")
    print(f"  sign agrees between net and gross: {'yes' if gn * gg > 0 else 'NO'}")
    verdict = ("CONFIRMS: grading is the single switch in a finer dress" if abs(gn) <= CONFIRM
               else "FALSIFIES one way or the other" if abs(gn) >= FALSIFY
               else "too small to tune against")
    print(f"  pre-registered reading at |G| <= {CONFIRM} / >= {FALSIFY}: {verdict}")


if __name__ == "__main__":
    main()
