"""M0271, the mechanism: WHERE the gate's 2009-2015 cost actually comes out.

Report only; writes nothing to the lab, records no trial, spends no look.

The ladder says the plain SPY 200-day gate cost this book 6.71 points a year over 2009-2015 while
its 20.1 points of cash should have cost 3.49 at the era's own measured price of cash. A residual
of that size has to be explained before it is believed, and there are only two places it can come
from. Either the gate sat out in months the book would have been paid unusually well for holding
-- which is a statement about the gate's judgement -- or the two arms diverge in the months they
are BOTH invested, because a book that liquidates and rebuilds does not come back owning what it
left. The second would mean the residual is not about cash or judgement at all.

So this decomposes the gap exactly, in logs, which add. Run the no-gate arm and the plain-gate arm
on the dev store in one sweep, de-fund both month-end curves the way every era figure in this lab
is de-funded, label each month by whether the gated arm actually held anything (read off its own
session snapshots, not off a re-derived gate calendar), and split

    ln(no-gate growth) - ln(gated growth)  =  the OUT months  +  the IN months

The out-month total is the market return the gate gave up. The in-month total is everything else:
fees, and the different book it owns after each round trip. Then the out-episodes one at a time,
because five re-entries is not a sample and the pre-registered expected failure says to check
whether one of them carries the whole residual.
"""

from __future__ import annotations

import math
import os
import sqlite3
from datetime import date
from itertools import pairwise
from pathlib import Path

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.regime import defunded
from seer_engine.commands.backtest_dev import month_end_curve
from seer_engine.lab import hardgate, runner, shortfall
from seer_engine.lab.method import discover

LAB_DB = Path(os.environ.get("SEER_LAB_DB", "/home/miftah/seer/lab/lab.sqlite"))
STORE = Path(os.environ.get("SEER_RESEARCH_STORE", "/home/miftah/seer/engine/.research"))
ERA_START, ERA_END = date(2009, 1, 1), date(2015, 10, 16)
ARMS = ("M0271-OFF", "M0271-D000")


def invested_months(snapshots) -> dict[date, bool]:
    """Month end -> did this arm hold anything at any session of that month?"""
    out: dict[tuple[int, int], bool] = {}
    for s in snapshots[1:]:
        key = (s.date.year, s.date.month)
        out[key] = out.get(key, False) or float(s.invested_usd) > 0.0
    return out  # type: ignore[return-value]


def main() -> None:
    method, _ = discover()["M0271"]
    arms = [c for c in method.all_candidates() if c.id in ARMS]

    conn = sqlite3.connect(f"file:{LAB_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    trials = {
        str(r["candidate_id"]): r
        for r in conn.execute(
            "select * from trials where method_id='M0271' and window='dev'"
        ).fetchall()
    }
    contributions = runner.recorded_contributions(conn, int(trials[ARMS[0]]["n"]))
    capital = runner.recorded_capital(conn, int(trials[ARMS[0]]["n"]))
    bench_curve, _n = shortfall.benchmark(conn)

    data = research.load_store(STORE)
    got: dict[str, object] = {}

    def on_result(_i: int, result: object, row: object) -> None:
        got[row.candidate.id] = result

    dev.run_registry(data.market, data.dividends, data.spy_dividends, arms,
                     on_result=on_result, contributions=contributions, initial_idr=capital)
    conn_rows = {}
    for c in arms:
        res = got[c.id]
        curve = month_end_curve(res.snapshots)
        deposits = hardgate.trial_deposits(conn, trials[c.id], list(curve))
        conn_rows[c.id] = (dict(defunded(list(curve), deposits)), invested_months(res.snapshots))
    conn.close()

    off_curve, _ = conn_rows["M0271-OFF"]
    gate_curve, gate_in = conn_rows["M0271-D000"]
    bench = dict(defunded(list(bench_curve), None))

    months = sorted(d for d in off_curve if d in gate_curve and ERA_START <= d <= ERA_END)
    years = (months[-1] - months[0]).days / 365.25

    rows = []
    for d0, d1 in pairwise(months):
        if off_curve[d0] <= 0 or gate_curve[d0] <= 0:
            continue
        held = gate_in.get((d1.year, d1.month), False)
        rows.append((
            d1,
            math.log(off_curve[d1] / off_curve[d0]),
            math.log(gate_curve[d1] / gate_curve[d0]),
            math.log(bench[d1] / bench[d0]) if d0 in bench and d1 in bench else 0.0,
            held,
        ))

    def ann(total_log: float) -> float:
        return (math.exp(total_log / years) - 1.0) * 100.0

    out_rows = [r for r in rows if not r[4]]
    in_rows = [r for r in rows if r[4]]
    gap_out = sum(r[1] - r[2] for r in out_rows)
    gap_in = sum(r[1] - r[2] for r in in_rows)

    print(f"2009-2015, {len(rows)} months, {years:.2f} years, de-funded, dev store "
          f"{data.fingerprint[:12]}")
    print(f"  the gated arm held nothing in {len(out_rows)} of them\n")
    print(f"{'':34}{'no-gate':>10} {'gated':>10} {'SPY TR':>10}")
    for label, sel in (("months the gate stayed IN", in_rows),
                       ("months the gate sat OUT", out_rows),
                       ("the whole era", rows)):
        print(f"{label + f' ({len(sel)})':34}{ann(sum(r[1] for r in sel)):9.2f}% "
              f"{ann(sum(r[2] for r in sel)):9.2f}% {ann(sum(r[3] for r in sel)):9.2f}%")
    print()
    print("THE DECOMPOSITION (logs add, so these are exact and sum to the whole gap):")
    print(f"  the gap, no-gate minus gated, over the era: {ann(gap_out + gap_in):+8.3f} pts/yr")
    print(f"    of which the OUT months -- market return the gate gave up: "
          f"{ann(gap_out):+8.3f} pts/yr")
    print("    of which the IN  months -- fees, and the different book it")
    print(f"                               owns after each round trip:    "
          f"{ann(gap_in):+8.3f} pts/yr")
    print()
    print("  for reference: a book that simply held the same share of cash every day would have")
    print("  paid 0.1732 points a year per point of cash (M0270, this chassis, this era).")

    print("\nTHE OUT-EPISODES ONE AT A TIME")
    episodes: list[list] = []
    for i, r in enumerate(rows):
        if r[4]:
            continue
        if episodes and i > 0 and rows[i - 1] is episodes[-1][-1]:
            episodes[-1].append(r)
        else:
            episodes.append([r])
    typical = sum(r[1] for r in in_rows) / len(in_rows)  # the book's mean gate-in log month
    print(f"{'from':>12} {'to':>12} {'months':>7} {'the book would have earned':>28} "
          f"{'a typical month pays':>22} {'episode judgement, pts/yr':>27}")
    tot = 0.0
    worst = ("", 0.0)
    for ep in episodes:
        got_log = sum(r[1] for r in ep)
        base = typical * len(ep)
        drag = ann(got_log - base)
        tot += drag
        if abs(drag) > abs(worst[1]):
            worst = (f"{ep[0][0]} to {ep[-1][0]}", drag)
        print(f"{ep[0][0]!s:>12} {ep[-1][0]!s:>12} {len(ep):7d} "
              f"{(math.exp(got_log) - 1) * 100:27.2f}% {(math.exp(base) - 1) * 100:21.2f}% "
              f"{drag:27.3f}")
    print(f"{'':12} {'':12} {'':>7} {'':>28} {'total':>22} {tot:27.3f}")
    print(f"{'':12} {'':12} {'':>7} {'':>28} {'largest single episode':>22} {worst[1]:27.3f}"
          f"   ({worst[0]})")
    print()
    print("Each episode is priced against what an AVERAGE month of the book would have paid over")
    print("the same number of months, so the last column is the cost of that episode's judgement")
    print("rather than of being in cash at all. If one line carries the total, five re-entries")
    print("were never a sample and this era has settled nothing.")


if __name__ == "__main__":
    main()
