"""Is the price band's worth a function of how often the gate is READ?

The 2026-10-19 gate-band study (`2026-10-19-gate-band-variants.py`, written up beside it) acts on
SPY's close EVERY DAY. No book in this lab does. Every lab book reads its gate at its own rank
session -- monthly for M0070, M0088, M0101, M0241 and M0245, weekly for M0063, M0072 and M0078 --
and holds that reading until the next one. A reading held for a month already suppresses every
flip shorter than a month, which is most of what a price band is for. So the study's headline
("a 3% band beats the bare gate on every axis") may be a statement about a cadence the lab never
runs, rather than about the band.

This script crosses the two axes the study held fixed: the SIGNAL (bare gate; band at 1.5%, 3%,
6%) against the CADENCE it is acted on (daily, weekly, monthly). Everything else is the study's,
deliberately, so that the only difference between the two tables is the `act_at` step:

    * the same `engine/.research/bars.csv` SPY closes, back-adjusted, 1993-01-29 -> 2015-10-16;
    * the same 200-bar warmup held flat in cash, so neither table claims a return it could not
      have computed a signal for;
    * the same one-session lag -- a signal read at the close of day i is acted on at day i+1 --
      so nothing here trades on a close it has not seen;
    * the same equity, CAGR and drawdown arithmetic, and the same two eras.

Two things this file is NOT. It is not the lab's band: `m0101.band_on` scans back at most 504
sessions for the last crossing, where the state machine below carries the state forward from the
first bar, and the two can differ in the opening months of a run. It is not a lab result: nothing
here is recorded -- no method, no trial, no N, no test-window look. It is a study on market data,
a prior for M0258's hypothesis, and the lab's gate accepts it as nothing more.

Run from the checkout root:

    engine/.venv/bin/python docs/backtests/2026-10-19-gate-band-cadence.py
"""
import csv
from datetime import date

import numpy as np

# ---------------------------------------------------------------- the tape
# SPY's own closes, which is what every one of the lab's gates reads. Sorted by date because the
# store writes bars grouped by symbol and a cumulative sum over an unsorted array is nonsense.
rows = [r for r in csv.DictReader(open('engine/.research/bars.csv')) if r['symbol'] == 'SPY']
rows.sort(key=lambda r: r['date'])
d = np.array([date.fromisoformat(r['date']) for r in rows])
c = np.array([float(r['close']) for r in rows])
n = len(c)


def sma(a, w):
    """The trailing w-bar mean, NaN until there are w bars. Cumulative-sum form, as the study's."""
    out = np.full(len(a), np.nan)
    cs = np.cumsum(np.insert(a, 0, 0.0))
    out[w - 1:] = (cs[w:] - cs[:-w]) / w
    return out


S200 = sma(c, 200)
ret = np.zeros(n)
ret[1:] = c[1:] / c[:-1] - 1.0
WARM = 200  # bars held flat before any signal is believed: the study's number, unchanged

# ---------------------------------------------------------------- the rank calendars
# A rank session is the last session of its period. `mon` keys a calendar month as a single
# integer so the month boundary is a plain inequality rather than a date comparison; `wd[i+1] <
# wd[i]` marks the last session of a calendar week, which is robust to a holiday Friday in a way
# that "is it a Friday" is not. The final bar of the tape is always a rank session so the last
# period is not silently dropped.
mon = np.array([x.year * 12 + x.month for x in d])
IS_MONTH_END = np.append(mon[1:] != mon[:-1], True)
wd = np.array([x.weekday() for x in d])
IS_WEEK_END = np.append(wd[1:] < wd[:-1], True)


# ---------------------------------------------------------------- the signals
def bare_gate():
    """The lab's shared gate: in while SPY closes above its 200-day average, out below it.

    NaN average (the warmup) reads OUT rather than IN, so the warmup can never be credited with a
    return. `run` zeroes those bars anyway; doing it here as well keeps the signal honest on its
    own, in case someone plots it.
    """
    return np.where(np.isnan(S200), 0.0, (c > S200).astype(float))


def band_state(b):
    """A price band around the same average: out only b below it, back in only b above it.

    The study's state machine verbatim. This is hysteresis in PRICE, not a lock in TIME -- the
    distinction matters, because the lab's measured failure of a time lock (M0148) was that it
    suppressed the 2008 exit, and a price band has no such failure mode.

    The loop is a loop because the state is path-dependent: whether bar i is in or out depends on
    which threshold was crossed most recently, which no vectorised form expresses cheaply.
    """
    on = np.zeros(n)
    cur = 0.0
    for i in range(n):
        if np.isnan(S200[i]):
            on[i] = 0.0
            continue
        if cur == 0.0 and c[i] > S200[i] * (1 + b):
            cur = 1.0
        elif cur == 1.0 and c[i] < S200[i] * (1 - b):
            cur = 0.0
        on[i] = cur
    return on


def act_at(sig, mask):
    """Hold the signal AS READ at the last rank session: the one thing this file adds.

    A book does not act on a signal it never looked at. At each rank session the book reads the
    signal and then holds that reading -- through every crossing, in both directions -- until the
    next rank session. `mask` is the rank calendar. Passing an all-True mask recovers the daily
    behaviour of the study this file corrects.
    """
    out = np.zeros(n)
    cur = 0.0
    for i in range(n):
        if mask[i]:
            cur = sig[i]
        out[i] = cur
    return out


# ---------------------------------------------------------------- scoring
def run(weight):
    """Equity from a weight path, lagged one session and with the warmup held flat."""
    w = np.zeros(n)
    w[1:] = weight[:-1]  # read at the close of i, acted on at i+1
    w[:WARM] = 0.0
    return np.cumprod(1.0 + ret * w), w


def stats(eq, w, lo, hi):
    """(CAGR, worst peak-to-trough fall, mean fraction invested) over the closed era [lo, hi]."""
    i = np.where((d >= lo) & (d <= hi))[0]
    yrs = (d[i[-1]] - d[i[0]]).days / 365.25
    e = eq[i] / eq[i[0]]
    return e[-1] ** (1 / yrs) - 1.0, (e / np.maximum.accumulate(e) - 1.0).min(), w[i].mean()


def flips(w):
    """How many times the book changed its mind. The cost axis, and the band's whole claim."""
    return int((np.diff(w) != 0).sum())


WHOLE = (date(1994, 1, 1), date(2015, 10, 16))
ERA_2009 = (date(2009, 1, 1), date(2015, 10, 16))

CADENCES = (
    ("daily", lambda s: s),
    ("weekly", lambda s: act_at(s, IS_WEEK_END)),
    ("monthly", lambda s: act_at(s, IS_MONTH_END)),
)
SIGNALS = [("bare gate", bare_gate())] + [
    (f"band {b * 100:g}%", band_state(b)) for b in (0.015, 0.03, 0.06)
]

# ---------------------------------------------------------------- the grid
print(f"{'signal':12s} {'acts':>8} {'whole':>8} {'wDD':>8} {'09-15':>8} {'inv':>7} {'flips':>6}")
print("-" * 62)
table = {}
for name, sig in SIGNALS:
    for how, at in CADENCES:
        eq, w = run(at(sig))
        cagr, dd, inv = stats(eq, w, *WHOLE)
        era, _, _ = stats(eq, w, *ERA_2009)
        table[(name, how)] = (cagr, dd, era)
        print(f"{name:12s} {how:>8} {cagr * 100:7.2f}% {dd * 100:7.1f}% "
              f"{era * 100:7.2f}% {inv * 100:6.1f}% {flips(w):6d}")

# ---------------------------------------------------------------- the paired differences
# The whole point: the band minus the bare gate, at each cadence, on both axes. A positive
# drawdown difference means the band fell LESS.
print()
print(f"{'gate read':>10}  {'band 3% - bare, return':>24}  {'band 3% - bare, drawdown':>26}")
print("-" * 64)
for how, _ in CADENCES:
    bc, bdd, _ = table[("band 3%", how)]
    gc, gdd, _ = table[("bare gate", how)]
    print(f"{how:>10}  {(bc - gc) * 100:+23.2f}  {(bdd - gdd) * 100:+25.1f}")

# ---------------------------------------------------------------- the reproduction check
# Why this grid is trusted at all: it independently reproduces four rows the lab has already
# recorded, with no shared code path -- those were produced by the full simulator, on the owner's
# monthly top-ups at Gotrade's real fees, and this is a weight path on raw closes. Figures read
# from lab/lab.sqlite trials n = 348, 349, 350, 351 (window 'dev').
RECORDED = (
    ("M0084-MONTHLY  bare gate, monthly", "bare gate", "monthly", 18.89),
    ("M0084-BAND3-M  3% band,   monthly", "band 3%", "monthly", 20.69),
    ("M0084-WEEKLY   bare gate, weekly ", "bare gate", "weekly", 33.13),
    ("M0084-BAND3-W  3% band,   weekly ", "band 3%", "weekly", 18.92),
)
print()
print("reproduction of the lab's own recorded SPY-only trials (worst fall, %):")
print(f"{'recorded trial':36s} {'recorded':>9} {'this grid':>10}")
print("-" * 58)
for label, name, how, recorded in RECORDED:
    print(f"{label:36s} {recorded:8.2f}% {-table[(name, how)][1] * 100:9.1f}%")
