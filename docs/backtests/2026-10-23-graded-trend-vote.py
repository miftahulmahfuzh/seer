"""Does a vote across four trend horizons grade exposure, or just dilute one switch?

The prior grid for M0287, measured on SPY's own closes before the method file was written and
reading no return the lab records. Three jobs.

**Job A, the calendars.** At every monthly decision session of the dev window, what share of the
four horizons (50, 100, 200, 252) has SPY closing above its own simple moving average? That share
IS the vote's exposure. Beside it, the plain 200-day gate's 0/1. This job fixes the x axis of the
whole method -- average exposure whole window and over 2009-2015 -- and it costs no backtest.

**Job B, the dilution constant.** The method's control arm is the single 200-day switch run at the
vote's own average exposure, so that the vote and the control differ ONLY in the shape of their
cash. The constant that does it is computed here, from Job A's shares alone.

**Job C, the unfunded feasibility prior.** SPY alone, a one-session lag, the reading held as taken
at each monthly decision. UNFUNDED: no deposits, no fees, no stock picking, so every percentage is
a plain price-return CAGR and none of them is comparable with the money-weighted returns the lab
records. A prior cannot be wrong, only surprising.

Nothing here is recorded: no method, no trial, no N, no look, and lab.sqlite is never opened.

    engine/.venv/bin/python docs/backtests/2026-10-23-graded-trend-vote.py \
        --store /home/miftah/seer/engine/.research
"""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path

import numpy as np

from seer_engine import dates as nyse
from seer_engine.strategies.base import History

DEV_END = date(2015, 10, 16)
WARM = 252
HORIZONS = (50, 100, 200, 252)
PROBE_START = date(1996, 1, 3)
ERA = (date(2009, 1, 1), DEV_END)


def load_spy(store: Path) -> History:
    with (store / "bars.csv").open(newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["symbol"] == "SPY"]
    rows.sort(key=lambda r: r["date"])
    col = lambda n: np.array([float(r[n]) for r in rows], dtype=np.float64)
    return History("SPY", np.array([date.fromisoformat(r["date"]) for r in rows], dtype="datetime64[D]"),
                   col("open"), col("high"), col("low"), col("close"), col("volume"))


def sma(a: np.ndarray, w: int) -> np.ndarray:
    out = np.full(len(a), np.nan)
    cs = np.cumsum(np.insert(a, 0, 0.0))
    out[w - 1:] = (cs[w:] - cs[:-w]) / w
    return out


def monthly_decisions(lo: date, hi: date) -> list[date]:
    out = []
    for s in nyse.sessions(lo, hi):
        p = nyse.prev_session(s)
        if (s.year, s.month) != (p.year, p.month):
            out.append(s)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", type=Path, required=True)
    args = ap.parse_args()
    h = load_spy(args.store)
    close = h.close
    above = {n: np.where(np.isnan(sma(close, n)), 0.0, (close > sma(close, n)).astype(float)) for n in HORIZONS}
    ready = {n: ~np.isnan(sma(close, n)) for n in HORIZONS}

    decisions = monthly_decisions(PROBE_START, DEV_END)
    idx = [int(np.searchsorted(h.dates, np.datetime64(d, "D"))) for d in decisions]
    for d, i in zip(decisions, idx):
        assert h.dates[i].item() == d, (d, h.dates[i])

    print(f"SPY bars {h.dates[0].item()} .. {h.dates[-1].item()}  n={len(h)}")
    print(f"monthly decision sessions {decisions[0]} .. {decisions[-1]}  n={len(decisions)}")
    notready = [str(d) for d, i in zip(decisions, idx) if not all(ready[n][i] for n in HORIZONS)]
    print(f"decisions where some horizon has no average yet: {len(notready)} {notready[:5]}")

    vote = np.array([sum(above[n][i] for n in HORIZONS) / len(HORIZONS) for i in idx])
    g200 = np.array([above[200][i] for i in idx])
    era_mask = np.array([ERA[0] <= d <= ERA[1] for d in decisions])

    print()
    print("JOB A -- the calendars, as shares of monthly decisions")
    print(f"{'':16s} {'whole window':>14s} {'2009-2015':>12s}")
    for n in HORIZONS:
        a = np.array([above[n][i] for i in idx])
        print(f"  above {n:3d}-day {a.mean()*100:13.2f}% {a[era_mask].mean()*100:11.2f}%")
    print(f"  VOTE4 mean   {vote.mean()*100:13.2f}% {vote[era_mask].mean()*100:11.2f}%")
    print(f"  G200 mean    {g200.mean()*100:13.2f}% {g200[era_mask].mean()*100:11.2f}%")
    print()
    print("  vote level histogram (whole window / 2009-2015), share of decisions:")
    for lev in (0.0, 0.25, 0.5, 0.75, 1.0):
        print(f"    {lev:4.2f}  {np.mean(vote == lev)*100:6.2f}%  {np.mean(vote[era_mask] == lev)*100:6.2f}%")
    print(f"  decisions where vote and G200 disagree in direction (vote in (0,1) exclusive): "
          f"{np.mean((vote > 0) & (vote < 1))*100:.2f}% whole, {np.mean((vote[era_mask] > 0) & (vote[era_mask] < 1))*100:.2f}% era")

    print()
    print("JOB B -- the dilution constant, from Job A alone")
    for label, m in (("whole window", np.ones(len(vote), dtype=bool)), ("2009-2015", era_mask)):
        ev, eg = vote[m].mean(), g200[m].mean()
        print(f"  {label}: E_vote={ev:.6f}  E_g200={eg:.6f}  ratio={ev/eg:.6f}")
        if ev <= eg:
            print(f"      dilute by CAPPING the on-weight: c = E_v/E_g = {ev/eg:.6f}")
        else:
            c = (ev - eg) / (1 - eg)
            print(f"      dilute by a cash FLOOR when off: c = (E_v-E_g)/(1-E_g) = {c:.6f}")

    print()
    print("JOB C -- UNFUNDED SPY-only feasibility prior (price-return CAGR on a weight path)")
    ret = np.zeros(len(close))
    ret[1:] = close[1:] / close[:-1] - 1.0
    act = np.zeros(len(close), dtype=bool)
    for i in idx:
        act[i] = True

    def path(signal_at: np.ndarray) -> np.ndarray:
        w = np.zeros(len(close))
        cur = 0.0
        for i in range(len(close)):
            if act[i]:
                cur = signal_at[i]
            w[i] = cur
        return w

    def run(w: np.ndarray) -> tuple[float, float]:
        lag = np.zeros(len(close))
        lag[1:] = w[:-1]
        lag[:WARM] = 0.0
        lo = int(np.searchsorted(h.dates, np.datetime64(PROBE_START, "D")))
        hi = int(np.searchsorted(h.dates, np.datetime64(DEV_END, "D"), side="right"))
        eq = np.cumprod(1.0 + lag[lo:hi] * ret[lo:hi])
        yrs = (h.dates[hi - 1].item() - h.dates[lo].item()).days / 365.25
        peak = np.maximum.accumulate(eq)
        return (eq[-1] ** (1 / yrs) - 1) * 100, (1 - eq / peak).max() * 100

    votefull = np.array([sum(above[n][i] for n in HORIZONS) / len(HORIZONS) for i in range(len(close))])
    ev, eg = vote.mean(), g200.mean()
    c = ev / eg if ev <= eg else None
    arms = {
        "FULL (always invested)": np.ones(len(close)),
        "G200 (the incumbent)": above[200],
        "VOTE4 (the ensemble)": votefull,
        "VOTE2 (50/200)": (above[50] + above[200]) / 2.0,
    }
    if c is not None:
        arms[f"G200-DIL (x{c:.4f})"] = above[200] * c
    for name, sig in arms.items():
        cagr, dd = run(path(sig))
        print(f"  {name:28s} UNFUNDED CAGR {cagr:6.2f}%   worst fall {dd:6.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
