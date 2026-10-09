"""How much of the index we can actually price, and whether the gap explains the lab's results.

Reproduces the two tables in `docs/plans/2026-10-03-seer-design.md` section 12. Read-only: it
loads the research store and the lab database, writes nothing, records no trial, and does not
move the lab's N -- the era split is sliced from each trial's ALREADY RECORDED monthly curve
rather than re-run, which is the whole reason this costs nothing to repeat.

    engine/.venv/bin/python engine/scripts/survivorship_coverage.py

Two questions, in order:

1. **How big is the hole?** Point-in-time S&P 500 / Nasdaq-100 membership is in the store; prices
   are not, for any company that has since merged, delisted or gone bankrupt, because the free
   source that backfilled them keeps only what still trades. Coverage is members-with-bars over
   members, on a date.

2. **Is the hole what produces the edge?** If missing bankruptcies flatter a momentum book, the
   flattery is largest where coverage is worst. So compare the edge over total-return SPY across
   eras of rising coverage. NOTE the confound, which no amount of care removes: coverage rises
   monotonically with time, so it is collinear with market regime. A flat or rising edge as
   coverage improves is evidence against the simple bias story, never proof the hole is harmless.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import numpy as np

from seer_engine import config
from seer_engine.research import load_store

STORE = config.REPO_ROOT / "engine" / ".research"
LAB = config.REPO_ROOT / "lab" / "lab.sqlite"

#: (label, start, end). Three eras of rising coverage over the dev window.
ERAS = (
    ("1996-2001", date(1996, 1, 1), date(2001, 12, 31)),
    ("2002-2008", date(2002, 1, 1), date(2008, 12, 31)),
    ("2009-2015", date(2009, 1, 1), date(2015, 10, 16)),
)

#: The quant roster entries, by the lab variant each was promoted from.
ROSTER = (("RMW-FR", "M0022-W-TV16"), ("RAW-FR", "M0007-N20-RAW"),
          ("MOM-FR", "M0002-REL-85"), ("MVW-FR", "M0008-N30-C07"))


def spy_total_return(market, dividends, dates: list[date]) -> list[float]:
    """SPY with dividends reinvested, valued on each of ``dates``.

    Units grow on every ex-date strictly inside a step, at that step's closing price -- the same
    convention as the simulator's `dividends=True`, so the comparison is like for like.
    """
    spy = market.history["SPY"]
    divs = dict(dividends.get("SPY", {}))
    out: list[float] = []
    units, prev = 1.0, None
    for d in dates:
        i = int(np.searchsorted(spy.dates, np.datetime64(d), side="right")) - 1
        price = float(spy.close[i])
        if prev is not None:
            for ex, amount in divs.items():
                if prev < ex <= d:
                    units *= 1.0 + float(amount) / price
        out.append(units * price)
        prev = d
    return out


def defund(conn, trial_n: int, start: date, end: date,
           curve: list[tuple[date, float]]) -> list[tuple[date, float]]:
    """``curve`` with the owner's deposits taken back out, or unchanged for a lump-sum trial.

    A funded curve rises because money arrived as well as because the book earned, and the SPY
    curve it is compared against here receives nothing. Slicing it raw therefore reads the owner's
    own deposits as edge: on the batch of 2026-10-09 that was seventy to eighty points a year in
    the early era, on 148,000 dollars of his money. Every trial from M0032 on is funded, so this is
    the normal case now, not an edge case.

    A recorded curve is normalised to the opening cash, so one deposit is
    ``amount_idr / INITIAL_IDR`` and no exchange rate enters: the run converted both at one rate.
    The rebuilt series is ``value - deposits_in_step``, compounded forward from the same opening.
    """
    from seer_engine import dates as nyse
    from seer_engine.backtest.regime import bucket
    from seer_engine.backtest.runner import INITIAL_IDR
    from seer_engine.lab.runner import recorded_contributions

    schedule = recorded_contributions(conn, trial_n)
    if schedule is None:
        return curve
    unit = float(schedule.amount_idr / INITIAL_IDR)
    credited: dict[date, float] = {}
    for d in schedule.dates_in(start, end):
        session = d if nyse.is_session(d) else nyse.next_session(d)
        if session <= end:
            credited[session] = credited.get(session, 0.0) + unit
    per_step = bucket(curve, credited)
    out, v = [curve[0]], curve[0][1]
    for i in range(1, len(curve)):
        d = curve[i][0]
        v *= (curve[i][1] - per_step.get(d, 0.0)) / curve[i - 1][1]
        out.append((d, v))
    return out


def cagr_and_fall(values: list[float], years: float) -> tuple[float, float]:
    """Compound annual growth and the worst peak-to-trough fall over ``values``."""
    peak, fall = values[0], 0.0
    for v in values:
        peak = max(peak, v)
        fall = max(fall, 1.0 - v / peak)
    return (values[-1] / values[0]) ** (1.0 / years) - 1.0, fall


def main() -> None:
    data = load_store(STORE)
    market, served = data.market, set(data.market.history)
    members = {s for s, _, _ in market.membership.intervals}

    print("=== 1. how much of the index we can price ===")
    print(f"point-in-time members over the window: {len(members)}")
    print(f"of those, missing bars entirely:       {len(members - served)} "
          f"({len(members - served) / len(members):.1%})\n")
    print(f"{'date':12}{'members':>9}{'priced':>8}{'coverage':>10}")
    for year in range(1996, 2016, 2):
        d = date(year, 6, 30)
        on = market.membership.members_on(d)
        print(f"{d.isoformat():12}{len(on):9}{len(on & served):8}{len(on & served) / len(on):9.1%}")

    conn = sqlite3.connect(f"file:{LAB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        print("\n=== 2. edge over total-return SPY, by era of rising coverage ===")
        print("(edge = strategy CAGR minus SPY CAGR, in points a year; 'fall' is the worst drop)\n")
        for label, start, end in ERAS:
            print(f"--- {label} ---")
            shown = False
            for roster_id, candidate in ROSTER:
                row = conn.execute(
                    'SELECT n, start, end, curve_json FROM trials '
                    'WHERE window = "dev" AND candidate_id = ?',
                    (candidate,),
                ).fetchone()
                if row is None:
                    print(f"   {roster_id:10} no recorded dev trial for {candidate}")
                    continue
                curve = [(date.fromisoformat(d), v) for d, v in json.loads(row["curve_json"])]
                curve = defund(conn, int(row["n"]), date.fromisoformat(row["start"]),
                               date.fromisoformat(row["end"]), curve)
                seg = [(d, v) for d, v in curve if start <= d <= end]
                if len(seg) < 24:
                    print(f"   {roster_id:10} too few months in this era")
                    continue
                years = (seg[-1][0] - seg[0][0]).days / 365.25
                s_cagr, s_fall = cagr_and_fall([v for _, v in seg], years)
                if not shown:
                    b_cagr, b_fall = cagr_and_fall(
                        spy_total_return(market, data.dividends, [d for d, _ in seg]), years
                    )
                    print(f"   {'SPY':10} {b_cagr * 100:+7.1f}%/yr  fall {b_fall * 100:5.1f}%")
                    shown = True
                print(f"   {roster_id:10} {s_cagr * 100:+7.1f}%/yr  fall {s_fall * 100:5.1f}%"
                      f"   edge {(s_cagr - b_cagr) * 100:+6.1f}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
