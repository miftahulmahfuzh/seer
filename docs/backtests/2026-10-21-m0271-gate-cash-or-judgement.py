"""M0271: is the SPY 200-day switch's premium anything but its time in cash?

Report only. It records no trial, moves no status and writes nothing to the lab database: the
lab's N and its test-window budget are exactly what they were. It exists because the three
quantities this method is about -- 2009-2015 EXPOSURE, 2009-2015 DE-FUNDED LEAD and TURNOVER --
are not all carried by any one lab command. A recorded trial stores whole-window exposure only,
and the claim under test is an era claim, so the era's exposure is recomputed here from each
run's own session snapshots (mean of invested / equity over the era's sessions, which is exactly
``RunStats.exposure``'s definition restricted to a date range).

WHAT IT DOES. For each store, in ONE ``dev.run_registry`` sweep (insight 482: a ratio drawn
across two store vintages is not a comparison), run the six recorded arms plus a zero-fee twin of
each -- twelve arms, one load. The zero-fee twins answer the one confound this design cannot
avoid: the no-gate arm never pays a gate round trip, so the step from it to the plain gate mixes
the gate's cash with the gate's fees, and insight 462 already split an equal-weight book's
post-2009 shortfall into 3.6 points of gate and 3.8 of fees.

Then, per era and per store:
  * fit the straight line through the FIVE DELAY RUNGS in points of cash against de-funded lead;
  * extrapolate it back to the no-gate arm's own cash and compare with that arm's measured lead;
  * report the residual of the plain gate against M0270's measured era price of a point of cash,
    on this identical chassis (0.0756 in 1996-2002, 0.0051 in 2003-2008, 0.1732 in 2009-2015);
  * report the root-mean-square residual of the rungs about their own line, which is the only
    honest noise band here.

Run (from the checkout root):
    SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
    SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
    SEER_SV_STORE=/home/miftah/seer/engine/.research-sv \
    PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python \
        docs/backtests/2026-10-21-m0271-gate-cash-or-judgement.py
"""

from __future__ import annotations

import gc
import os
import sqlite3
from dataclasses import replace
from datetime import date
from decimal import Decimal
from itertools import pairwise
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

#: M0270's measured price of one point of cash on THIS chassis, THIS store, per era
#: (docs/backtests/2026-10-21-m0270-exposure-return-curve.md). The whole-window figure is the
#: global fit through its six rungs; the era figures are its era table.
M0270_SLOPE = {
    WHOLE: 0.0623,
    "1996-2002": 0.0756,
    "2003-2008": 0.0051,
    "2008": None,          # a single year: M0270 published no slope for it
    "2009-2015": 0.1732,
}

#: The arm the ladder is anchored on, and the five rungs the line is fitted through.
OFF = "M0271-OFF"
RUNGS = ("M0271-D000", "M0271-D006", "M0271-D016", "M0271-D030", "M0271-D042")
PLAIN = "M0271-D000"

#: The pre-registered thresholds, copied from the method file so the script cannot soften them.
CONFIRM = 0.5   # |residual| at or under this confirms: the switch is a cash dial
FALSIFY = 1.0   # |residual| at or over this, with a tight rung scatter, falsifies


def _fit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Least-squares ``y = a + s*x``. Five points, one dial; no weighting and nothing clever."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    s = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return my - s * mx, s


def _rms(vals: list[float]) -> float:
    return (sum(v * v for v in vals) / len(vals)) ** 0.5


def era_exposure(snapshots, start: date, end: date) -> float:
    """``RunStats.exposure`` restricted to one era: mean of invested / equity over its sessions."""
    vals = [
        float(s.invested_usd) / float(s.equity_usd)
        for s in snapshots[1:]
        if start <= s.date <= end and float(s.equity_usd) > 0.0
    ]
    return sum(vals) / len(vals) if vals else float("nan")


def main() -> None:
    method, _path = discover()["M0271"]
    arms = list(method.all_candidates())

    conn = sqlite3.connect(f"file:{LAB_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    trials = {
        str(r["candidate_id"]): r
        for r in conn.execute(
            "select * from trials where method_id='M0271' and window='dev'"
        ).fetchall()
    }
    if not trials:
        raise SystemExit("M0271 has no recorded dev trial yet: run `lab run M0271` first")
    any_trial = trials[OFF]
    contributions = runner.recorded_contributions(conn, int(any_trial["n"]))
    capital = runner.recorded_capital(conn, int(any_trial["n"]))
    bench_curve, bench_n = shortfall.benchmark(conn)

    print(f"capital {capital} IDR   funded {'yes' if contributions else 'no'}   "
          f"deposits {contributions}")
    print(f"benchmark: the recorded REF-SPY-HOLD dev curve, trial {bench_n}\n")

    # label -> arm id -> (cash points, lead pts/yr, era exposure, maxDD pts)
    table: dict[str, dict[str, dict[str, float]]] = {}
    meta: dict[str, dict[str, dict[str, float]]] = {}

    for store_label, store_dir in STORES:
        data = research.load_store(store_dir)
        free = [
            replace(a, id=f"{a.id}-FREE",
                    rules=replace(a.rules, cost_model="flat", cost_rate=Decimal(0)))
            for a in arms
        ]
        got: dict[str, tuple[object, object]] = {}

        def on_result(_i: int, result: object, row: object, *, _got=got) -> None:
            _got[row.candidate.id] = (result, row)

        dev.run_registry(
            data.market, data.dividends, data.spy_dividends, [*arms, *free],
            on_result=on_result, contributions=contributions, initial_idr=capital,
        )

        print(f"=== {store_label}  store {data.fingerprint[:12]}  "
              f"prices {data.price_fingerprint[:12]} ===")
        hdr = (f"{'arm':16} {'expo%':>7} {'turn':>6} {'fees$':>9} {'money%/yr':>10} "
               f"{'maxDD%':>7} {'PF':>5} {'trades':>7}  reproduces")
        print(hdr)
        print("-" * len(hdr))

        for net in (True, False):
            key = store_label if net else store_label + "-gross"
            table[key] = {}
            meta[key] = {}
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
                print(f"{aid:16} {float(row.stats.exposure) * 100:7.3f} "
                      f"{float(row.stats.turnover):6.2f} {float(row.stats.costs_usd):9,.0f} "
                      f"{y:10.3f} {m.max_drawdown * 100:7.2f} "
                      f"{m.profit_factor if m.profit_factor else float('nan'):5.2f} "
                      f"{m.trades:7d}  {repro}")

                cells: dict[str, dict[str, float]] = {}
                for label, s, e in ((WHOLE, row.start, row.end), *ERAS):
                    got_s = wf.measure(curve, s, e, deposits)
                    ref_s = wf.measure(bench_curve, s, e)
                    if got_s is None or ref_s is None or got_s.cagr is None or ref_s.cagr is None:
                        continue
                    cells[label] = {
                        "cash": 100.0 - era_exposure(result.snapshots, s, e) * 100.0,
                        "lead": (got_s.cagr - ref_s.cagr) * 100.0,
                        "fall": got_s.max_drawdown * 100.0,
                    }
                table[key][a.id] = cells  # type: ignore[assignment]
                meta[key][a.id] = {"turnover": float(row.stats.turnover),
                                   "fees": float(row.stats.costs_usd),
                                   "trades": float(m.trades)}
            print()

        del data, got
        gc.collect()

    conn.close()

    for key, rows in table.items():
        print(f"=== {key}: the ladder, era by era ===")
        for label in (WHOLE, *(l for l, _s, _e in ERAS)):
            if label not in rows[OFF]:
                continue
            print(f"\n-- {label} --")
            print(f"{'arm':12} {'cash pts':>9} {'lead %/yr':>10} {'fall%':>7}")
            for aid in (OFF, *RUNGS):
                c = rows[aid][label]
                print(f"{aid:12} {c['cash']:9.3f} {c['lead']:10.3f} {c['fall']:7.2f}")

            xs = [rows[a][label]["cash"] for a in RUNGS]
            ys = [rows[a][label]["lead"] for a in RUNGS]
            if len({round(x, 6) for x in xs}) < 2:
                print("  rungs do not separate on cash: nothing to fit")
                continue
            a0, s = _fit(xs, ys)
            resid = [y - (a0 + s * x) for x, y in zip(xs, ys)]
            scatter = _rms(resid)
            off_cash = rows[OFF][label]["cash"]
            off_lead = rows[OFF][label]["lead"]
            pred = a0 + s * off_cash
            print(f"  delay line: lead = {a0:+.3f} {s:+.4f} * cash   "
                  f"(a point of episodic cash = {-s:.4f} pts/yr)")
            print("  rung residuals: " + "  ".join(f"{r:+.3f}" for r in resid)
                  + f"   rms {scatter:.3f}")
            print(f"  monotone in cash: "
                  f"{'yes' if all(x < y for x, y in pairwise(xs)) else 'NO -- x axis broken'}")
            print(f"  extrapolated to the no-gate arm ({off_cash:.2f} pts of cash): "
                  f"P {pred:+.3f}   measured A {off_lead:+.3f}   A - P {off_lead - pred:+.3f}")
            print("    A above P => the gate's own cash was DEARER than the delay's: it sat "
                  "out at better moments than the delay waited through (anti-skill)")
            print("    A below P => the gate's own cash was CHEAPER: its exits carry information")

            slope = M0270_SLOPE.get(label)
            plain_cash = rows[PLAIN][label]["cash"]
            plain_lead = rows[PLAIN][label]["lead"]
            measured_cost = off_lead - plain_lead
            dcash = plain_cash - off_cash
            print(f"  the plain gate against the no-gate arm: {dcash:+.2f} pts of cash, "
                  f"{measured_cost:+.3f} pts/yr of cost")
            if slope is not None:
                r = measured_cost - slope * dcash
                # The sign is the whole content: a NEGATIVE residual is a gate that cost less
                # than its cash, which is timing skill; a POSITIVE one is a gate that cost MORE,
                # which is a gate that chose worse moments to sit out than chance would have.
                verdict = (
                    "CONFIRMS (a cash dial with a story attached)" if abs(r) <= CONFIRM
                    else ("FALSIFIES: the gate cost LESS than its cash -- real timing skill"
                          if r < 0 else
                          "FALSIFIES: the gate cost MORE than its cash -- it sat out at "
                          "better-than-average moments")
                    if abs(r) >= FALSIFY
                    else "mostly cash, residual too small to tune against")
                print(f"  M0270's price of a point of cash here: {slope:.4f} pts/yr  "
                      f"=> predicted cost {slope * dcash:+.3f}")
                print(f"  RESIDUAL R = {r:+.3f} pts/yr against a rung scatter of {scatter:.3f}"
                      f"   -> {verdict}")
                print(f"  episodic cash costs {-s / slope:.2f}x what evenly-spread cash costs "
                      f"on this chassis in this era")
        print()

    print("=== turnover and fees, the confound the zero-fee twins price ===")
    for key in table:
        print(f"  {key:12} " + "  ".join(
            f"{a.split('-')[1]}:{meta[key][a]['turnover']:.2f}" for a in (OFF, *RUNGS)))


if __name__ == "__main__":
    main()
