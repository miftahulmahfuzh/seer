"""M0270: the whole exposure-return curve, on both copies of the price history, in one sweep.

Report only. It records no trial, moves no status and does not write to the lab database: the
lab's N and its test-window budget are exactly what they were. It exists because the two numbers
this method is about -- average EXPOSURE and TURNOVER -- are the two the lab's own cross-store
report does not carry. ``lab survivorship`` prints return, fall, profit factor, the luck inputs,
the era and the folds for each store, and no exposure column at all; but exposure is this method's
X AXIS, so without it there is no curve to draw on the second store. M0266 hit the same wall and
could only quote the check store's exposures because its own arms were aimed at a target.

What it does: load each store once, run all six recorded arms against it in ONE
``dev.run_registry`` sweep at the recorded capital and funding, and print exposure, turnover, the
fee bill, money-weighted return, worst fall and profit factor per rung per store. Then fit the
global straight line through each store's six points and report, for every rung pair, how far that
line is from the truth -- which is the method's pre-registered deliverable.

Reading both stores in one process is what makes the cross-store comparison legitimate: insight
482 says a ratio drawn across two store vintages is not a comparison, so both fingerprints are
printed and every arm within a store shares one load.

Run (from the checkout root):
    SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite \
    PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python \
        docs/backtests/2026-10-21-m0270-exposure-return-curve.py
"""

from __future__ import annotations

import gc
import itertools
import os
import sqlite3
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.lab import runner
from seer_engine.lab.method import discover

LAB_DB = Path(os.environ.get("SEER_LAB_DB", "/home/miftah/seer/lab/lab.sqlite"))
STORES = (
    ("dev", Path(os.environ.get("SEER_RESEARCH_STORE", "/home/miftah/seer/engine/.research"))),
    ("sv", Path(os.environ.get("SEER_SV_STORE", "/home/miftah/seer/engine/.research-sv"))),
)
#: The pre-registered tolerance: the largest exposure gap over which the global straight line may
#: mis-state a return difference. A tenth of a point a year, the precision M0266 quoted to.
TOLERANCE_PTS = 0.10


def _pct(x: float | None) -> float:
    return float("nan") if x is None else x * 100.0


def _fit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Least-squares ``y = a + s*x``. Six points, one dial; no weighting and nothing clever."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    s = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return my - s * mx, s


def main() -> None:
    method, _path = discover()["M0270"]
    arms = list(method.all_candidates())

    conn = sqlite3.connect(f"file:{LAB_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    trial = conn.execute(
        "select * from trials where method_id='M0270' and window='dev' order by n limit 1"
    ).fetchone()
    if trial is None:
        raise SystemExit("M0270 has no recorded dev trial yet: run `lab run M0270` first")
    contributions = runner.recorded_contributions(conn, int(trial["n"]))
    capital = runner.recorded_capital(conn, int(trial["n"]))
    recorded = {
        str(r["candidate_id"]): r
        for r in conn.execute(
            "select * from trials where method_id='M0270' and window='dev'"
        ).fetchall()
    }
    conn.close()

    print(f"capital {capital} IDR   funded {'yes' if contributions else 'no'}   "
          f"deposits {contributions}")
    print()

    curves: dict[str, list[tuple[float, float, float]]] = {}

    for label, store_dir in STORES:
        data = research.load_store(store_dir)
        # Zero-fee twins, the M0127 decomposition trick: the ONLY field that differs is the
        # cost model, so the gross curve answers the pre-registered worry that the bend is
        # Gotrade's per-order minimum biting harder on a smaller book rather than a market
        # effect. If the gross curve bends the same way, the shape is not the fee schedule.
        free = [
            replace(a, id=f"{a.id}-FREE",
                    rules=replace(a.rules, cost_model="flat", cost_rate=Decimal(0)))
            for a in arms
        ]
        rows = dev.run_registry(
            data.market, data.dividends, data.spy_dividends, [*arms, *free],
            contributions=contributions, initial_idr=capital,
        )
        by_id = {r.candidate.id: r for r in rows}
        spy = rows[0].spy_tr
        spy_y = _pct(spy.mwr if spy.mwr is not None else spy.cagr)

        print(f"=== {label}  store {data.fingerprint[:12]}  "
              f"prices {data.price_fingerprint[:12]}  SPY TR {spy_y:.2f}%/yr ===")
        hdr = (f"{'arm':10} {'scale':>6} {'expo%':>7} {'turn':>6} {'fees$':>9} "
               f"{'money%/yr':>10} {'vs SPY':>8} {'maxDD%':>7} {'PF':>5} {'trades':>7}")
        print(hdr)
        print("-" * len(hdr))

        points: list[tuple[float, float, float]] = []
        for a in arms:
            r = by_id[a.id]
            m = r.stats.metrics
            y = _pct(m.mwr if m.mwr is not None else m.cagr)
            x = float(r.stats.exposure) * 100.0
            points.append((x, y, m.max_drawdown * 100.0))
            print(f"{a.id:10} {a.params.scale!s:>6} {x:7.3f} "
                  f"{float(r.stats.turnover):6.2f} {float(r.stats.costs_usd):9,.0f} "
                  f"{y:10.3f} {y - spy_y:8.3f} {m.max_drawdown * 100:7.2f} "
                  f"{m.profit_factor if m.profit_factor else float('nan'):5.2f} "
                  f"{m.trades:7d}")
            if label == "dev" and a.id in recorded:
                t = recorded[a.id]
                same = abs(float(t["total_return"]) - m.total_return) < 1e-12
                if not same:
                    print(f"    !! does NOT reproduce recorded trial {t['n']}: "
                          f"{t['total_return']} vs {m.total_return}")
        curves[label] = points
        gross = [
            (float(by_id[a.id + '-FREE'].stats.exposure) * 100.0,
             _pct(by_id[a.id + '-FREE'].stats.metrics.mwr),
             by_id[a.id + '-FREE'].stats.metrics.max_drawdown * 100.0)
            for a in arms
        ]
        curves[label + '-gross'] = gross
        print('gross (zero-fee twins): ' + '  '.join(
            f'{x:.2f}%->{y:.3f}' for x, y, _ in gross))
        # Each store loads whole into memory (about 1.8 MB a symbol); holding both at once
        # is what takes this laptop down, so the first is dropped before the second loads.
        del data, rows, by_id
        gc.collect()
        print(flush=True)

    for label, points in curves.items():
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        dds = [p[2] for p in points]
        a, s = _fit(xs, ys)
        a_d, s_d = _fit(xs, dds)
        print(f"=== {label}: the shape ===")
        print(f"global return line: {a:+.3f} {s:+.4f} * expo   "
              f"(a point of exposure = {s:.4f} pts/yr)")
        print(f"global fall line:   {a_d:+.3f} {s_d:+.4f} * expo   "
              f"(a point of exposure = {s_d:.4f} pts of fall)")
        print("through the origin, return/exposure per rung: "
              + "  ".join(f"{y / x * 100:.3f}" for x, y in zip(xs, ys)))
        print("local slopes between consecutive rungs (pts/yr per point of exposure):")
        for i in range(len(xs) - 1):
            dx, dy = xs[i] - xs[i + 1], ys[i] - ys[i + 1]
            ddd = dds[i] - dds[i + 1]
            print(f"  {xs[i + 1]:6.2f} -> {xs[i]:6.2f}  ({dx:5.2f} pts)  "
                  f"return {dy / dx:+.4f}   fall {ddd / dx:+.4f}")
        print("straight-line error over every rung pair (pts/yr):")
        worst_ok = 0.0
        best_bad = 999.0
        for i, j in itertools.combinations(range(len(xs)), 2):
            gap = abs(xs[i] - xs[j])
            pred = s * (xs[i] - xs[j])
            err = abs((ys[i] - ys[j]) - pred)
            flag = "ok " if err < TOLERANCE_PTS else "OVER"
            print(f"  gap {gap:5.2f} pts  predicted {pred:+.3f}  measured "
                  f"{ys[i] - ys[j]:+.3f}  error {err:.3f}  {flag}")
            if err < TOLERANCE_PTS:
                worst_ok = max(worst_ok, gap)
            else:
                best_bad = min(best_bad, gap)
        print(f"  --> widest gap inside {TOLERANCE_PTS} pts/yr: {worst_ok:.2f} points of "
              f"exposure; narrowest gap outside it: "
              f"{'none' if best_bad > 900 else f'{best_bad:.2f}'}")
        print()


if __name__ == "__main__":
    main()
