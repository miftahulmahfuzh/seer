"""Is the slow end of the gate-reading ladder an INTERVAL, or is it a DATE?

M0260 swept how often a book reads its SPY 200-day safety gate, from weekly to yearly, on one
host. Above monthly the ladder did not behave like a dial. Reading the gate twice a year
(June/December) earned 12.10% a year of the owner's money against 8.78% for reading it four times
a year (March/June/September/December) -- and the twice-a-year grid is a STRICT SUBSET of the
four-times grid. Reading strictly fewer dates cannot beat reading those same dates plus others on
any theory where the interval is what matters. So past monthly the axis stopped being a speed, and
M0260 could not say what it had become, because every rung of its ladder carried exactly one phase.

This file measures the thing M0260 could not: the SAME interval read at DIFFERENT dates.

    month_index(d) = (d.year - 1970) * 12 + (d.month - 1)

    anchor(h, data_date, k, phase) = the newest bar a of h with a <= data_date such that
                                       (i)  a is the last session of its calendar month, and
                                       (ii) month_index(a) % k == phase
                                     falling back to data_date when no such bar is on hand

M0260's anchor is this one at ``phase = k - 1``, which is why its k=3 reads the calendar quarters
and its k=12 reads Decembers. Holding ``k`` and moving ``phase`` changes NOTHING about how often
the gate is read and EVERYTHING about which dates it is read on. If the slow rungs are an interval
effect the phases of one k must land near each other; if they are a date effect they will not.

Three jobs.

**Job A, the phase grid.** SPY alone, the dev store's own closes, a 200-bar average, a one-session
lag, the reading held exactly as it was taken at each monthly decision session. Every phase of
k=3, k=6 and k=12 -- 3 + 6 + 12 = 21 readings of the same gate at the same interval -- beside the
native reading every book in the lab already runs.

This is a FEASIBILITY TABLE AND A PRIOR, not a result, and it is **UNFUNDED**: no monthly top-up,
no Gotrade fee, no deposits, no stock picking. Every return in it is a price-return CAGR on a
weight path and none of them is comparable with the money-weighted returns the lab records. The
word UNFUNDED is printed beside each one for that reason. Nothing here is recorded -- no method,
no trial, no N, no test-window look -- and nothing here touches ``lab/lab.sqlite``, not even a
read, because a read migrates the file on connect.

**Job B, the nesting identity.** M0260's k=3 grid is exactly the union of its k=6 grid (Jun/Dec)
and the phase-shifted k=6 grid (Mar/Sep): 2 mod 3 over the months {2,5,8,11} splits into
{5,11} and {2,8}. So the quarterly arm's anchor at any moment is simply whichever of the two
half-yearly arms' anchors is NEWER -- it is the "read both phases" arm, and the two half-yearly
phases are its halves. This job proves that session by session rather than asserting it, because
the method file's prediction rests on it: a quarterly reading that loses to BOTH of its own halves
is a paradox no interval story survives.

**Job C, the anchor probe.** At every monthly decision session of the dev window, for every
(k, phase) the method will run: does the anchor resolve without the fall-back, does it ever sit
later than the data date, how many SPY bars stand behind it, and how stale does it get? The last
number sets the method's lookback, and the method file may not guess it.

The arithmetic is written out here rather than imported from the method file, so that agreement
between this prior and the production allocator is a check and not a tautology. The only things
imported are the published NYSE calendar, which is a fact rather than a claim, and ``History``, so
that the probe holds exactly the object the allocator will hold.

Run it from the checkout root with an absolute store path, following M0260's precedent rather than
M0258's relative one:

    engine/.venv/bin/python docs/backtests/2026-10-20-gate-reading-phase.py \\
        --store /home/miftah/seer/engine/.research

Exit status is 0 when every structural check in Jobs B and C passed and 1 when any failed, so that
a careless reader cannot skim past a broken anchor. The grid itself has no pass or fail: it is a
prior, and a prior cannot be wrong, only surprising.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path
from typing import Callable, NamedTuple

import numpy as np

from seer_engine import dates as nyse
from seer_engine.strategies.base import History

# ------------------------------------------------------------------ constants
DEV_END = date(2015, 10, 16)  # the dev window's last session; copied, not imported, on purpose
WARM = 200  # bars held flat in cash before any signal is believed: M0260's study's number
TREND_N = 200  # the gate's window, == f_factor's ("SPY", 200) for every book on this chassis
WHOLE = (date(1994, 1, 1), DEV_END)  # M0260's study's window, unchanged, so the rows compare
PROBE_START = date(1996, 1, 3)  # the dev window's first scored session; the probe walks from here
ERA_2009 = (date(2009, 1, 1), DEV_END)
MONTH = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def months_of(k: int, phase: int) -> str:
    """The calendar months a (k, phase) grid reads, as the names a human checks it by."""
    return "/".join(MONTH[m] for m in range(12) if m % k == phase % k)


# ------------------------------------------------------------------ the tape
def load_spy(store: Path) -> History:
    """SPY's own bars from the store's ``bars.csv``, as the ``History`` an allocator would hold."""
    path = store / "bars.csv"
    with path.open(newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["symbol"] == "SPY"]
    if not rows:
        raise SystemExit(f"no SPY bars in {path}")
    rows.sort(key=lambda r: r["date"])
    col: Callable[[str], np.ndarray] = lambda name: np.array(
        [float(r[name]) for r in rows], dtype=np.float64
    )
    return History(
        "SPY",
        np.array([date.fromisoformat(r["date"]) for r in rows], dtype="datetime64[D]"),
        col("open"), col("high"), col("low"), col("close"), col("volume"),
    )


def sma(a: np.ndarray, w: int) -> np.ndarray:
    """The trailing ``w``-bar mean, NaN until there are ``w`` bars."""
    out = np.full(len(a), np.nan)
    cs = np.cumsum(np.insert(a, 0, 0.0))
    out[w - 1:] = (cs[w:] - cs[:-w]) / w
    return out


def bare_gate(close: np.ndarray, avg: np.ndarray) -> np.ndarray:
    """The lab's shared gate: in while SPY closes above its 200-day average, out below it."""
    return np.where(np.isnan(avg), 0.0, (close > avg).astype(float))


# ------------------------------------------------------------------ the calendars
def month_index(d: date) -> int:
    """Calendar months since January 1970, as one integer."""
    return (d.year - 1970) * 12 + (d.month - 1)


def month_end_by_bars(h: History) -> np.ndarray:
    """Is bar j the last of its month, decided from the bars the allocator already holds?"""
    months = h.dates.astype("datetime64[M]")
    flags = np.zeros(len(h), dtype=bool)
    flags[:-1] = months[1:] != months[:-1]
    return flags


class Anchor(NamedTuple):
    at: date
    index: int
    found: bool


def anchor(h: History, data_date: date, k: int, phase: int, me_bars: np.ndarray) -> Anchor:
    """The newest qualifying month-end bar on or before ``data_date``, at this k and this phase.

    A literal backward transcription of the definition rather than a vectorised lookup, because
    this function is a second pair of eyes on the production allocator and clarity is worth more
    here than speed. Even k=12 walks about 250 bars.
    """
    j = int(np.searchsorted(h.dates, np.datetime64(data_date, "D"), side="right")) - 1
    for i in range(j, -1, -1):
        a = h.dates[i].item()
        is_month_end = (nyse.next_session(a).month != a.month) if i == j else bool(me_bars[i])
        if is_month_end and month_index(a) % k == phase % k:
            return Anchor(a, i, True)
    idx = h.index_of(data_date)
    return Anchor(data_date, -1 if idx is None else idx, False)


def monthly_decisions(lo: date, hi: date) -> list[date]:
    """Every session in [lo, hi] on which a MONTHLY book calls its allocator.

    Written out rather than imported from ``sim.rules.is_rank_session``: a rank session is the
    first NYSE session of its calendar month.
    """
    out: list[date] = []
    for s in nyse.sessions(lo, hi):
        p = nyse.prev_session(s)
        if (s.year, s.month) != (p.year, p.month):
            out.append(s)
    return out


# ------------------------------------------------------------------ Job A: the weight paths
def read_at(signal: np.ndarray, act: np.ndarray, h: History, me_bars: np.ndarray,
            k: int | None, phase: int) -> np.ndarray:
    """Hold the gate AS READ at each decision session, until the next one."""
    out = np.zeros(len(signal))
    current = 0.0
    for i in range(len(signal)):
        if act[i]:
            if k is None:
                current = signal[i]
            else:
                a = anchor(h, h.dates[i].item(), k, phase, me_bars)
                current = signal[a.index] if a.index >= 0 else 0.0
        out[i] = current
    return out


def equity(weight: np.ndarray, ret: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Equity from a weight path, lagged one session, with the warmup held flat in cash."""
    w = np.zeros(len(weight))
    w[1:] = weight[:-1]
    w[:WARM] = 0.0
    return np.cumprod(1.0 + ret * w), w


def stats(eq: np.ndarray, w: np.ndarray, days: np.ndarray, lo: date, hi: date
          ) -> tuple[float, float, float]:
    """(CAGR, worst peak-to-trough fall, mean fraction invested) over [lo, hi]. UNFUNDED."""
    i = np.where((days >= lo) & (days <= hi))[0]
    years = (days[i[-1]] - days[i[0]]).days / 365.25
    e = eq[i] / eq[i[0]]
    return (e[-1] ** (1 / years) - 1.0,
            float((e / np.maximum.accumulate(e) - 1.0).min()),
            float(w[i].mean()))


def flips(w: np.ndarray) -> int:
    return int((np.diff(w) != 0).sum())


class Row(NamedTuple):
    label: str
    months: str
    cagr: float
    dd: float
    era: float
    invested: float
    flips: int


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--store", type=Path, required=True)
    args = ap.parse_args()

    h = load_spy(args.store)
    days = np.array([d.item() for d in h.dates], dtype=object)
    close = np.asarray(h.close, dtype=float)
    ret = np.zeros(len(close))
    ret[1:] = close[1:] / close[:-1] - 1.0
    signal = bare_gate(close, sma(close, TREND_N))
    me_bars = month_end_by_bars(h)

    decisions = monthly_decisions(PROBE_START, DEV_END)  # what the METHOD will actually walk
    acting = monthly_decisions(days[0], DEV_END)  # the whole tape, for the weight paths
    dec_set = set(acting)
    act = np.array([bool(d in dec_set) for d in days])

    grid: list[tuple[str, int | None, int]] = [("native (every book today)", None, 0)]
    for k in (3, 6, 12):
        for p in range(k):
            grid.append((f"k={k:<2d} phase {p}", k, p))

    print("=" * 100)
    print("JOB A -- THE PHASE GRID.  SPY ALONE, MONTHLY ACTING, 200-bar gate, one-session lag.")
    print("ALL RETURNS UNFUNDED: price returns on a weight path, no deposits, no fees, no picking.")
    print(f"whole window {WHOLE[0]}..{WHOLE[1]};  era {ERA_2009[0]}..{ERA_2009[1]}")
    print("=" * 100)
    print(f"{'reading':<22} {'months read':<26} {'CAGR':>8} {'worst':>8} {'2009-15':>8} "
          f"{'invest':>7} {'flips':>6}")
    rows: dict[tuple[int | None, int], Row] = {}
    weights: dict[tuple[int | None, int], np.ndarray] = {}
    for label, k, p in grid:
        wpath = read_at(signal, act, h, me_bars, k, p)
        eq, w = equity(wpath, ret)
        cagr, dd, inv = stats(eq, w, days, *WHOLE)
        era, _, _ = stats(eq, w, days, *ERA_2009)
        months = "every month end" if k is None else months_of(k, p)
        r = Row(label, months, cagr, dd, era, inv, flips(w))
        rows[(k, p)] = r
        weights[(k, p)] = w
        print(f"{r.label:<22} {r.months:<26} {r.cagr:>7.2%} {r.dd:>7.1%} {r.era:>7.2%} "
              f"{r.invested:>6.1%} {r.flips:>6d}")

    print()
    print("SPREAD WITHIN ONE INTERVAL -- the whole question, in one block:")
    for k in (3, 6, 12):
        cs = [rows[(k, p)].cagr for p in range(k)]
        ds = [rows[(k, p)].dd for p in range(k)]
        best = max(range(k), key=lambda p: rows[(k, p)].cagr)
        worst = min(range(k), key=lambda p: rows[(k, p)].cagr)
        print(f"  k={k:<2d}  CAGR {min(cs):>6.2%} .. {max(cs):>6.2%}  spread {100*(max(cs)-min(cs)):>5.2f} pts"
              f"   fall {min(ds):>6.1%} .. {max(ds):>6.1%}"
              f"   best phase {best} ({months_of(k,best)}), worst phase {worst} ({months_of(k,worst)})")
    nat = rows[(None, 0)]
    print(f"  native CAGR {nat.cagr:.2%}, fall {nat.dd:.1%} -- the rung every book in the lab runs today")

    # ---------------------------------------------------------------- Job B
    print()
    print("=" * 100)
    print("JOB B -- THE NESTING IDENTITY.  k=3 phase 2  ==  (k=6 phase 5)  UNION  (k=6 phase 2)")
    print("=" * 100)
    ok = True
    bad: list[date] = []
    for s in decisions:
        dd = nyse.prev_session(s)
        a3 = anchor(h, dd, 3, 2, me_bars)
        a6 = anchor(h, dd, 6, 5, me_bars)
        a6s = anchor(h, dd, 6, 2, me_bars)
        newer = a6 if a6.at >= a6s.at else a6s
        if a3.at != newer.at:
            bad.append(dd)
    if bad:
        ok = False
        print(f"  FAILED on {len(bad)} decision sessions, first {bad[:6]}")
    else:
        print(f"  HOLDS on all {len(decisions)} monthly decision sessions of "
              f"{PROBE_START}..{DEV_END} -- every session the method will score.")
        print("  So the quarterly arm is the 'read both half-yearly phases' arm, and the two")
        print("  half-yearly phases are its halves. A quarterly reading that loses to BOTH of its")
        print("  own halves is a paradox no interval story survives.")

    print()
    print("  WHERE THE THREE DISAGREE -- months in which the quarterly and the two half-yearly")
    print("  phases do not all hold the same weight (UNFUNDED SPY return over each stretch):")
    w3, w6, w6s = weights[(3, 2)], weights[(6, 5)], weights[(6, 2)]
    disagree = (w3 != w6) | (w3 != w6s)
    runs: list[tuple[int, int]] = []
    i = 0
    while i < len(disagree):
        if disagree[i]:
            j = i
            while j + 1 < len(disagree) and disagree[j + 1]:
                j += 1
            runs.append((i, j))
            i = j + 1
        else:
            i += 1
    print(f"  {len(runs)} disagreement stretches, {int(disagree.sum())} sessions "
          f"({disagree.mean():.1%} of the tape)")
    print(f"  {'from':<12} {'to':<12} {'sessions':>8} {'SPY':>8}   {'q':>3} {'JD':>3} {'MS':>3}")
    for a, b in runs:
        if days[a] < WHOLE[0]:
            continue
        spy = close[b] / close[a] - 1.0
        print(f"  {str(days[a]):<12} {str(days[b]):<12} {b-a+1:>8} {spy:>7.1%}   "
              f"{w3[a]:>3.0f} {w6[a]:>3.0f} {w6s[a]:>3.0f}")

    # ---------------------------------------------------------------- Job C
    print()
    print("=" * 100)
    print("JOB C -- THE ANCHOR PROBE, at every monthly decision session the method will run.")
    print("=" * 100)
    print(f"{'reading':<22} {'sessions':>8} {'fallbacks':>10} {'late':>6} {'min bars':>9} "
          f"{'max stale':>10} {'dates read':>11}")
    worst_stale = 0
    min_bars_overall = 10 ** 9
    for label, k, p in grid:
        if k is None:
            continue
        fallbacks = late = 0
        min_bars, max_stale, max_stale_at = 10 ** 9, -1, None
        seen: set[date] = set()
        for s in decisions:
            dd = nyse.prev_session(s)
            a = anchor(h, dd, k, p, me_bars)
            if not a.found:
                fallbacks += 1
            if a.at > dd:
                late += 1
            seen.add(a.at)
            min_bars = min(min_bars, a.index + 1)
            stale_sessions = int(np.searchsorted(h.dates, np.datetime64(dd, "D"), side="right")) - 1 - a.index
            if stale_sessions > max_stale:
                max_stale, max_stale_at = stale_sessions, dd
        worst_stale = max(worst_stale, max_stale)
        min_bars_overall = min(min_bars_overall, min_bars)
        if fallbacks or late:
            ok = False
        print(f"{label:<22} {len(decisions):>8} {fallbacks:>10} {late:>6} {min_bars:>9} "
              f"{max_stale:>7} ({str(max_stale_at)[:10]}) {len(seen):>5}")

    print()
    ident = [nyse.prev_session(s) for s in decisions
             if anchor(h, nyse.prev_session(s), 1, 0, me_bars).at != nyse.prev_session(s)]
    if ident:
        ok = False
        print(f"  THE k=1 IDENTITY IS BROKEN on {len(ident)} sessions, first {ident[:6]} -- "
              f"the ladder's fastest rung is NOT the native arm and the arm table is wrong.")
    else:
        print(f"  k=1 identity HOLDS on all {len(decisions)} monthly decision sessions: a monthly")
        print("  book's data_date is always a calendar month end, so the k=1 anchor IS the data")
        print("  date and the native arm IS the ladder's fastest rung. No trial is owed to it.")
    print()
    print(f"  WORST STALENESS ACROSS THE WHOLE GRID: {worst_stale} sessions.")
    print(f"  So a {TREND_N}-bar gate read at the worst anchor needs {TREND_N + worst_stale} bars "
          f"on hand; the method's lookback must cover that.")
    print(f"  Fewest SPY bars behind any anchor at any decision session: {min_bars_overall}.")
    print()
    print("STRUCTURAL CHECKS:", "ALL PASSED" if ok else "FAILED -- read the lines above")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
