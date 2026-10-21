"""M0271, the across-the-lab half: does the gate's price hold where the lab actually lives?

Report only. No trial, no status, no journal entry, no look: it uses ``lab gate``'s own transform
and planner as a library and writes nothing at all, not even the observation ``lab gate`` would
write. (``lab gate`` journals on every invocation unless told not to, and insight 500 is a
permanent duplicate made by exactly that.)

WHY IT EXISTS. M0271's ladder prices the shared SPY 200-day gate precisely, on ONE deliberately
opinion-free book. That book picks nothing, so the price it measures is the gate's alone -- which
is the point, and also the limitation: the gate's cost depends on the book it is bolted onto,
because what it costs to sit out a month is whatever that book would have earned in it. The lab's
3.6-points-a-year figure (insight 463) is a statement about REAL books with real picking, so the
ladder's finding has to be checked there before it is generalised.

WHAT IT MEASURES. For a sample of recorded gated variants, one per method, spanning the families
the lab has actually explored: run the variant as recorded and the same variant with the shared
gate switched off and nothing else moved, at its recorded capital and funding, in ONE sweep on one
store load. Then, per era and per variant:

    measured gate cost = (the gate-off arm's lead) - (the gated arm's lead)
    points of cash     = (the gate-off arm's exposure) - (the gated arm's exposure), IN THAT ERA
    predicted cost     = points of cash x M0270's measured price of a point of cash in that era

and report the ratio of measured to predicted. The hypothesis under test (insight 532) says that
ratio is 1: the gate's premium is nothing but its time in cash. M0271's ladder says it is about 2
in 2009-2015 and NEGATIVE whole window, on a book with no picking in it.

Era exposure is recomputed from each run's own session snapshots -- ``RunStats.exposure``'s
definition restricted to a date range -- because a recorded trial stores the whole-window average
only, and the gate sits out a quite different share of 2009-2015 than of the whole window (18.3
percent of monthly decisions against 26.5), so the whole-window number would understate every
2009-2015 ratio by about half.
"""

from __future__ import annotations

import gc
import math
import os
import sqlite3
from collections import defaultdict
from datetime import date
from pathlib import Path

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.commands.backtest_dev import month_end_curve
from seer_engine.lab import gate_probe, hardgate, shortfall
from seer_engine.lab import walkforward as wf
from seer_engine.lab.exposure import ERAS, WHOLE

LAB_DB = Path(os.environ.get("SEER_LAB_DB", "/home/miftah/seer/lab/lab.sqlite"))
STORE = Path(os.environ.get("SEER_RESEARCH_STORE", "/home/miftah/seer/engine/.research"))

#: M0270's measured price of one point of cash per era, on its opinion-free 50-name chassis.
SLOPE = {WHOLE: 0.0623, "1996-2002": 0.0756, "2003-2008": 0.0051, "2009-2015": 0.1732}

#: One recorded gated variant per method, chosen to span the ideas the lab has explored rather
#: than to flatter the result: momentum of every shape, seasonality, the 52-week high, long-term
#: reversal, lottery avoidance, a machine-learned ranker, coskewness, treasury beta, a blend and
#: a core-satellite. Each is its method's best-MAR recorded dev variant.
SAMPLE = (
    ("M0007", "M0007-N20-RAW"),            # residual momentum: the roster's own book
    ("M0001", "M0001-TV12"),               # momentum, risk-managed
    ("M0008", "M0008-C10"),                # portfolio construction
    ("M0015", "M0015-N20-BLEND"),          # the 52-week high
    ("M0024", "M0024-SAME-N20-RANKSUM"),   # seasonality
    ("M0028", "M0028-BLEND-RM"),           # short-term reversal
    ("M0069", "M0069-L60-N20-T"),          # long-term reversal
    ("M0091", "M0091-HI5-N20-T"),          # lottery avoidance
    ("M0169", "M0169-D20-SW"),             # the price-delay screen
    ("M0179", "M0179-N40-SW"),             # coskewness
    ("M0197", "M0197-Y20-SW"),             # treasury beta
    ("M0030", "M0030-C50T"),               # core-satellite blend
)


def era_exposure(snapshots, start: date, end: date) -> float:
    vals = [
        float(s.invested_usd) / float(s.equity_usd)
        for s in snapshots[1:]
        if start <= s.date <= end and float(s.equity_usd) > 0.0
    ]
    return sum(vals) / len(vals) if vals else float("nan")


def main() -> None:
    conn = sqlite3.connect(f"file:{LAB_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    before = (conn.execute("select count(*) from trials").fetchone()[0],
              conn.execute("select count(*) from insights").fetchone()[0])

    problems, checked = gate_probe.control_problems()
    if problems:
        raise SystemExit("the gate transform does not reproduce the lab's own controls: "
                         + "; ".join(problems))
    print(f"the gate transform reproduced all {checked} recorded gate-off controls\n")

    wanted: dict[str, str] = {}
    plans = []
    for mid, cid in SAMPLE:
        plan = gate_probe.plan_methods(conn, [mid], only=cid, gated_only=True)
        plans.extend(plan)
        wanted[cid] = mid
    bench_curve, bench_n = shortfall.benchmark(conn)

    data = research.load_store(STORE)
    print(f"dev store {data.fingerprint[:12]}  prices {data.price_fingerprint[:12]}  "
          f"benchmark REF-SPY-HOLD trial {bench_n}\n")

    # label -> candidate id -> mode -> (cash points, lead pts/yr)
    cells: dict[str, dict[str, dict[str, tuple[float, float]]]] = defaultdict(
        lambda: defaultdict(dict))

    for plan in plans:
        for v in plan.variants:
            registry = [cand for _mode, cand in gate_probe.arms_for(v)]
            owner = {cand.id: mode for mode, cand in gate_probe.arms_for(v)}

            def on_result(_i, result, row, *, _v=v, _owner=owner):
                mode = _owner[row.candidate.id]
                curve = month_end_curve(result.snapshots)
                deposits = hardgate.trial_deposits(conn, _v.trial, list(curve))
                for label, s, e in ((WHOLE, row.start, row.end), *ERAS):
                    if label not in SLOPE:
                        continue
                    got = wf.measure(curve, s, e, deposits)
                    ref = wf.measure(bench_curve, s, e)
                    if got is None or ref is None or got.cagr is None or ref.cagr is None:
                        continue
                    cells[label][_v.candidate.id][mode] = (
                        100.0 - era_exposure(result.snapshots, s, e) * 100.0,
                        (got.cagr - ref.cagr) * 100.0,
                    )

            dev.run_registry(
                data.market, data.dividends, data.spy_dividends, registry,
                on_result=on_result, contributions=v.contributions, initial_idr=v.capital,
            )
            print(f"  measured {v.candidate.id}", flush=True)

    del data
    gc.collect()
    after = (conn.execute("select count(*) from trials").fetchone()[0],
             conn.execute("select count(*) from insights").fetchone()[0])
    conn.close()
    print(f"\ntrials {before[0]} -> {after[0]}, journal entries {before[1]} -> {after[1]}: "
          f"this script wrote nothing\n")

    for label in (WHOLE, *(l for l, _s, _e in ERAS if l in SLOPE)):
        slope = SLOPE[label]
        print(f"=== {label}: the gate's cost against its time in cash "
              f"(a point of cash = {slope:.4f} pts/yr) ===")
        hdr = (f"{'variant':24} {'cash pts':>9} {'measured':>9} {'predicted':>10} "
               f"{'ratio':>7} {'residual':>9}")
        print(hdr)
        print("-" * len(hdr))
        ratios, resids = [], []
        for cid in wanted:
            arms = cells[label].get(cid, {})
            if gate_probe.GATED not in arms or gate_probe.UNGATED not in arms:
                continue
            g_cash, g_lead = arms[gate_probe.GATED]
            u_cash, u_lead = arms[gate_probe.UNGATED]
            dcash = g_cash - u_cash
            measured = u_lead - g_lead
            predicted = slope * dcash
            if not math.isfinite(dcash) or abs(dcash) < 1.0:
                print(f"{cid:24} {dcash:9.2f}   the two arms barely differ in cash: no ratio")
                continue
            ratio = measured / predicted if predicted else float("nan")
            resid = measured - predicted
            ratios.append(ratio)
            resids.append(resid)
            print(f"{cid:24} {dcash:9.2f} {measured:+9.3f} {predicted:+10.3f} "
                  f"{ratio:7.2f} {resid:+9.3f}")
        if ratios:
            srt = sorted(ratios)
            mid = srt[len(srt) // 2] if len(srt) % 2 else (srt[len(srt) // 2 - 1]
                                                           + srt[len(srt) // 2]) / 2
            print(f"{'median ratio':24} {mid:33.2f}")
            print(f"{'range':24} {min(srt):26.2f} to {max(srt):.2f}")
            print(f"{'median residual pts/yr':24} "
                  f"{sorted(resids)[len(resids) // 2]:+33.3f}")
            print(f"{'ratio of 1 would mean':24} the gate is nothing but its time in cash")
        print()


if __name__ == "__main__":
    main()
