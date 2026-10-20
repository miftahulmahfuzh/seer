"""M0127: what the resize band costs in FEES, separated from what it pays in RETURN.

Report only. It records no trial, moves no status and does not touch the lab database: the lab's
N and its test-window budget are exactly what they were. It is `lab costs`' trick applied to a
different question -- run the five recorded arms again on the identical store, in ONE sweep, at
Gotrade's real fees and again at zero fees, so the fee bill is read off the engine rather than
inferred from turnover.

Why it is needed. The five arms differ in one field, the resize band, and they record the
IDENTICAL trade count (1338) because the lab's trade counter counts entries and exits, not the
trims and top-ups a band controls. So the only visible levers are exposure and turnover, and
neither says how much of the extra return a tighter band earned was handed straight back to the
broker. The zero-fee column answers that directly: gross return at a given band, minus net
return, is the fee bill, in money and in points a year.

Run (from the checkout root, with the engine's venv):
    PYTHONPATH=engine/src python docs/backtests/2026-10-20-m0127-band-fee-decomposition.py
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.lab import runner
from seer_engine.lab.method import discover

STORE = Path("/home/miftah/seer/engine/.research")
LAB_DB = Path("/home/miftah/seer/lab/lab.sqlite")
ZERO = Decimal("0")


def main() -> None:
    method, _path = discover()["M0127"]
    arms = list(method.all_candidates())

    conn = sqlite3.connect(LAB_DB)
    conn.row_factory = sqlite3.Row
    trials = {
        str(t["candidate_id"]): t
        for t in conn.execute(
            "select * from trials where method_id='M0127' and window='dev'"
        ).fetchall()
    }
    first = trials[arms[0].id]
    contributions = runner.recorded_contributions(conn, int(first["n"]))
    capital = runner.recorded_capital(conn, int(first["n"]))
    conn.close()

    # Zero-fee twins: the ONLY field that differs is the cost model. cost_model="flat" at
    # cost_rate=0 charges nothing at all, so gross minus net is the whole fee bill.
    free = [
        replace(a, id=f"{a.id}-FREE", rules=replace(a.rules, cost_model="flat", cost_rate=ZERO))
        for a in arms
    ]

    data = research.load_store(STORE, window=research.DEV_WINDOW)
    rows = dev.run_registry(
        data.market,
        data.dividends,
        data.spy_dividends,
        [*arms, *free],
        contributions=contributions,
        initial_idr=capital,
    )

    paid = {r.candidate.id: r for r in rows if not r.candidate.id.endswith("-FREE")}
    gross = {r.candidate.id[: -len("-FREE")]: r for r in rows if r.candidate.id.endswith("-FREE")}

    print(f"store {data.fingerprint[:12]}  capital {capital} IDR  "
          f"funded {'yes' if contributions else 'no'}")
    print()
    hdr = (f"{'arm':6} {'expo':>7} {'turn':>7} {'net CAGR':>9} {'gross CAGR':>11} "
           f"{'fee pts/yr':>11} {'fees USD':>11} {'net maxDD':>10} {'gross maxDD':>12}")
    print(hdr)
    print("-" * len(hdr))
    for a in arms:
        p, g = paid[a.id], gross[a.id]
        pc, gc = p.stats.metrics.cagr, g.stats.metrics.cagr
        print(f"{a.id[6:]:6} {float(p.stats.exposure):7.4f} {float(p.stats.turnover):7.4f} "
              f"{pc * 100:8.2f}% {gc * 100:10.2f}% {(gc - pc) * 100:10.2f}  "
              f"{float(p.stats.costs_usd):11,.0f} "
              f"{p.stats.metrics.max_drawdown * 100:9.2f}% {g.stats.metrics.max_drawdown * 100:11.2f}%")


if __name__ == "__main__":
    main()
