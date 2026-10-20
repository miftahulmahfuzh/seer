"""Is the gate's slow-reading spread a CALENDAR problem or a RARITY problem?

M0261 measured, on a real funded book, that two readings of the SPY 200-day safety gate taken
EXACTLY as often as each other but on different calendar months differ by 3.21 points a year of
the owner's money (Jun/Dec 10.57% against Mar/Sep 7.36%), and that two once-a-year readings six
months apart differ by 8.2 points of worst fall. Both gaps are LARGER than the whole
weekly-to-yearly interval ladder, which spans 2.21 points of money and 4.5 of fall on the same
book. So past monthly the gate's reading axis is not a speed. The open question is what it is, and
two sentences fit the same evidence while prescribing opposite things:

    (A) THE CALENDAR IS THE PROBLEM. A month-end grid is an arbitrary human convention; the dev
        window's two crashes happen to sit at particular places in it; a rule that fired on a
        SESSION COUNT instead -- every 126 trading days, with no calendar anywhere in it -- would
        show a much smaller spread as its starting point slides. If so, the lesson generalises far
        past this gate: several lab books re-pick monthly and several measure calm or strength over
        windows that end at month ends, and every one of them stands on a grid nobody chose.

    (B) RARITY IS THE PROBLEM. A gate asked twice a year is a stale promise whatever grid it sits
        on; the spread is the irreducible variance of reading rarely; a session grid will spread
        just as wide. If so the lesson is narrow and already known -- read the gate every month --
        and no other book needs auditing.

This file measures the session grid that separates them.

    session_index(d) = the number of NYSE sessions in [1990-01-01, d], minus one

    anchor(h, data_date, period, offset) = the newest bar a of h with a <= data_date such that
                                             session_index(a) % period == offset
                                           falling back to data_date when no such bar is on hand

That is M0261's anchor with its calendar coordinate -- "the last session of a calendar month whose
month_index is right" -- replaced by a pure session count. Nothing else moves. The gate is still
Faber's: SPY above its 200-day average or below it. Only the DATE the question is asked moves, and
it moves strictly backwards, so no arm can look ahead.

**Why a fixed calendar epoch rather than "the symbol's first bar".** The idea row that reserved
M0262 wrote the count as starting from the symbol's first bar. That cannot be used: in a lab run
the allocator is handed a LOOKBACK WINDOW on the single-symbol path and a FULL history on the
prepared path, so "the first bar" is a different bar in the two paths and the anchor would move
between them. Counting NYSE sessions from a fixed epoch is path-independent, point-in-time, and
reads the published exchange calendar rather than any price. It also loses nothing: sliding the
epoch only relabels which offset is called zero, and this file sweeps every offset.

Four jobs, all in ONE sweep on ONE store, because a spread measured on one tape and compared with
a spread measured on another is not a comparison at all.

**Job A, the session grid.** SPY alone, the dev store's own closes, a 200-bar average, a
one-session lag, the reading held exactly as taken at each monthly decision session. All 126
offsets of a 126-session period, beside the native reading every book in the lab runs today.

**Job B, the calendar grid, recomputed here.** M0261's own month-end anchor, transcribed, at all
six phases of its half-yearly reading and all twelve of its yearly one. Recomputed rather than
quoted so that the two grids are measured by the same code on the same bars in the same process.
The printed numbers must reproduce M0261's prior; if they do not, nothing below is a comparison.

**Job C, the fair comparison.** A 126-offset range is not comparable with a 6-phase range: more
draws spread wider for free. So this job reports the STANDARD DEVIATION across offsets, which does
not grow with the draw count, and the EXPECTED RANGE OF A 5-DRAW SUBSAMPLE of each grid, computed
exhaustively over every 5-subset of the calendar grid and over every evenly-spaced 5-subset of the
session grid. Those two numbers are what (A) and (B) actually disagree about.

**Job D, the anchor probe.** At every monthly decision session of the dev window, for the five
anchored arms the method will run: does the anchor resolve without the fall-back, does it ever sit
later than the data date, how many SPY bars stand behind it, how stale does it get. The last
number sets the method's lookback and the method file may not guess it.

**Job E, the drift, and the reason this file has two periods instead of one.** M0262's idea row
specified a 126-session period, "about half a year, with no calendar anywhere in it". That
sentence is false, and this job is what proved it before a line of the method file was written.
The NYSE runs 250 to 254 sessions a year and averages 252.0 over the dev window, so 126 sessions
is 252/2 to within a fraction of a session and a 126-session grid does not drift: measured here,
its offset 0 reads ONLY in June, July and December across twenty-two years, and its offset 50
reads ONLY in March, August and September. A 126-session grid is a CALENDAR GRID WEARING A
SESSION LABEL. Running it alone could only have produced "the session grid spreads like the
calendar grid", which would have been a near-tautology dressed as a finding. A period coprime with
the year's session count does drift: 131 sessions sweeps all twelve calendar months twice over the
same window. So the method runs BOTH -- 126 as the calendar-locked control and the bridge back to
M0261, 131 as the genuinely calendar-free grid -- and the comparison the method is bought for is
between those two, not between a session grid and a month grid.

Everything here is UNFUNDED: price returns on a weight path, no monthly top-up, no Gotrade fee, no
stock picking. None of these CAGRs is comparable with the money-weighted figures the lab records.
Nothing here is recorded -- no method, no trial, no N, no test-window look -- and nothing here
touches ``lab/lab.sqlite``, not even a read, because a read migrates the file on connect.

The arithmetic is written out here rather than imported from the method file, so that agreement
between this prior and the production allocator is a check and not a tautology. The only things
imported are the published NYSE calendar, which is a fact rather than a claim, and ``History``, so
the probe holds exactly the object the allocator will hold.

    engine/.venv/bin/python docs/backtests/2026-10-20-gate-reading-sessions.py \\
        --store /home/miftah/seer/engine/.research

Exit status is 0 when every structural check in Jobs B and D passed and 1 when any failed. The
grids themselves have no pass or fail: they are a prior, and a prior cannot be wrong, only
surprising.
"""

from __future__ import annotations

import argparse
import csv
from collections.abc import Callable
from datetime import date
from functools import cache
from pathlib import Path
from typing import NamedTuple

import numpy as np
from seer_engine import dates as nyse
from seer_engine.strategies.base import History

# ------------------------------------------------------------------ constants
DEV_END = date(2015, 10, 16)  # the dev window's last session; copied, not imported, on purpose
WARM = 200  # bars held flat in cash before any signal is believed: M0260's and M0261's number
TREND_N = 200  # the gate's window, == f_factor's ("SPY", 200) for every book on this chassis
WHOLE = (date(1994, 1, 1), DEV_END)  # M0260's and M0261's window, so every row compares
PROBE_START = date(1996, 1, 3)  # the dev window's first scored session; the probe walks from here
ERA_2009 = (date(2009, 1, 1), DEV_END)
EPOCH_YEAR = 1990  # session_index counts NYSE sessions from the first session of this year
#: The two periods. 126 is M0262's idea row's number, about half a year of sessions. 131 is the
#: period the DRIFT JOB forced into the design: see that job's header. Both are swept whole.
PERIODS = (126, 131)
#: The offsets the method's five anchored arms run, per period. Maximally separated pairs, plus
#: one third point on the free grid. See the method file's ARM TABLE.
OFFSETS = {126: (0, 63), 131: (0, 33, 65)}
MONTH = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def months_of(k: int, phase: int) -> str:
    return "/".join(MONTH[m] for m in range(12) if m % k == phase % k)


# ------------------------------------------------------------------ the session coordinate
@cache
def _year_sessions(year: int) -> tuple[date, ...]:
    return tuple(nyse.sessions(date(year, 1, 1), date(year, 12, 31)))


@cache
def _year_base(year: int) -> int:
    """NYSE sessions from the epoch up to, but not including, 1 January of ``year``."""
    if year <= EPOCH_YEAR:
        return 0
    return _year_base(year - 1) + len(_year_sessions(year - 1))


def session_index(d: date) -> int:
    """The number of NYSE sessions in [EPOCH_YEAR-01-01, d], minus one.

    Absolute, point-in-time and independent of whatever slice of history the caller holds --
    which is the whole reason the method's grid is defined on this and not on a bar position.
    """
    if d.year < EPOCH_YEAR:
        raise ValueError(f"{d} is before the session epoch {EPOCH_YEAR}")
    ys = _year_sessions(d.year)
    lo, hi = 0, len(ys)
    while lo < hi:  # bisect_left on a tuple of dates, written out to keep the file importless
        mid = (lo + hi) // 2
        if ys[mid] < d:
            lo = mid + 1
        else:
            hi = mid
    return _year_base(d.year) + lo


# ------------------------------------------------------------------ the tape
def load_spy(store: Path) -> History:
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
    out = np.full(len(a), np.nan)
    cs = np.cumsum(np.insert(a, 0, 0.0))
    out[w - 1:] = (cs[w:] - cs[:-w]) / w
    return out


def bare_gate(close: np.ndarray, avg: np.ndarray) -> np.ndarray:
    return np.where(np.isnan(avg), 0.0, (close > avg).astype(float))


# ------------------------------------------------------------------ the two anchors
def month_index(d: date) -> int:
    return (d.year - 1970) * 12 + (d.month - 1)


def month_end_by_bars(h: History) -> np.ndarray:
    months = h.dates.astype("datetime64[M]")
    flags = np.zeros(len(h), dtype=bool)
    flags[:-1] = months[1:] != months[:-1]
    return flags


class Anchor(NamedTuple):
    at: date
    index: int
    found: bool


def cal_anchor(h: History, data_date: date, k: int, phase: int, me_bars: np.ndarray) -> Anchor:
    """M0261's month-end anchor, transcribed from its prior so the two grids share one process."""
    j = int(np.searchsorted(h.dates, np.datetime64(data_date, "D"), side="right")) - 1
    for i in range(j, -1, -1):
        a = h.dates[i].item()
        is_month_end = (nyse.next_session(a).month != a.month) if i == j else bool(me_bars[i])
        if is_month_end and month_index(a) % k == phase % k:
            return Anchor(a, i, True)
    idx = h.index_of(data_date)
    return Anchor(data_date, -1 if idx is None else idx, False)


def ses_anchor(h: History, data_date: date, period: int, offset: int,
               sidx: np.ndarray) -> Anchor:
    """The newest bar on or before ``data_date`` whose session index is ``offset`` mod ``period``.

    ``sidx`` is the precomputed session index of every bar, which is what the allocator will
    recompute per call; this file keeps the array so the 126-offset sweep finishes in seconds.
    """
    j = int(np.searchsorted(h.dates, np.datetime64(data_date, "D"), side="right")) - 1
    want = offset % period
    for i in range(j, -1, -1):
        if sidx[i] % period == want:
            return Anchor(h.dates[i].item(), i, True)
    idx = h.index_of(data_date)
    return Anchor(data_date, -1 if idx is None else idx, False)


def monthly_decisions(lo: date, hi: date) -> list[date]:
    out: list[date] = []
    for s in nyse.sessions(lo, hi):
        p = nyse.prev_session(s)
        if (s.year, s.month) != (p.year, p.month):
            out.append(s)
    return out


# ------------------------------------------------------------------ the weight paths
def read_with(signal: np.ndarray, act: np.ndarray,
              pick: Callable[[int], int] | None) -> np.ndarray:
    """Hold the gate AS READ at each decision session, until the next one.

    ``pick`` maps a decision bar index to the bar index its reading is taken at; ``None`` is the
    native reading, which takes it at the decision bar itself.
    """
    out = np.zeros(len(signal))
    current = 0.0
    for i in range(len(signal)):
        if act[i]:
            if pick is None:
                current = signal[i]
            else:
                k = pick(i)
                current = signal[k] if k >= 0 else 0.0
        out[i] = current
    return out


def equity(weight: np.ndarray, ret: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
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
    cagr: float
    dd: float
    era: float
    invested: float
    flips: int


def spread(xs: list[float]) -> tuple[float, float]:
    """(range, population standard deviation) of a grid, both in points."""
    a = np.asarray(xs, dtype=float)
    return float(a.max() - a.min()) * 100.0, float(a.std()) * 100.0


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
    sidx = np.array([session_index(d) for d in days], dtype=np.int64)

    decisions = monthly_decisions(PROBE_START, DEV_END)
    acting = monthly_decisions(days[0], DEV_END)
    dec_set = set(acting)
    act = np.array([bool(d in dec_set) for d in days])

    def ses_pick(period: int, offset: int) -> Callable[[int], int]:
        want = offset % period
        idx = np.full(len(days), -1, dtype=np.int64)
        last = -1
        for i in range(len(days)):
            if sidx[i] % period == want:
                last = i
            idx[i] = last
        return lambda i: int(idx[i]) if idx[i] >= 0 else i

    def cal_pick(k: int, phase: int) -> Callable[[int], int]:
        want = phase % k
        idx = np.full(len(days), -1, dtype=np.int64)
        last = -1
        for i in range(len(days)):
            if me_bars[i] and month_index(days[i]) % k == want:
                last = i
            idx[i] = last
        return lambda i: (i if (me_bars[i] or nyse.next_session(days[i]).month != days[i].month)
                          and month_index(days[i]) % k == want
                          else (int(idx[i]) if idx[i] >= 0 else i))

    def row_for(pick: Callable[[int], int] | None, label: str) -> Row:
        eq, w = equity(read_with(signal, act, pick), ret)
        c, d, inv = stats(eq, w, days, *WHOLE)
        e, _, _ = stats(eq, w, days, *ERA_2009)
        return Row(label, c, d, e, inv, flips(w))

    # ---------------------------------------------------------------- Job E first
    print("=" * 102)
    print("JOB E -- THE DRIFT.  Which calendar months does a session grid actually read?")
    print("This job runs FIRST because it decides whether the method's question can be asked at")
    print("all.  A session grid whose period divides the year's session count is a CALENDAR grid.")
    print("=" * 102)
    yrs = [y for y in sorted({d.year for d in days}) if 1994 <= y <= 2014]  # whole years only
    counts = [sum(1 for d in days if d.year == y) for y in yrs]
    print(f"  NYSE sessions in the whole years {yrs[0]}..{yrs[-1]}: min {min(counts)}, "
          f"max {max(counts)}, mean {np.mean(counts):.1f}")
    for period in PERIODS:
        print(f"    period {period} against that mean: {np.mean(counts)/period:.3f} readings a "
              f"year, so a reading drifts {np.mean(counts) - period*round(np.mean(counts)/period):+.1f} "
              f"sessions a year through the calendar")
    print(f"  {'grid':<18} {'readings':>9} {'readings/yr':>12} {'months read':<42} {'doy span':>9}")
    for period in PERIODS:
        for off in OFFSETS[period]:
            g = [d for i, d in enumerate(days)
                 if WHOLE[0] <= d <= WHOLE[1] and sidx[i] % period == off]
            if not g:
                continue
            doy = [d.timetuple().tm_yday for d in g]
            months = "/".join(MONTH[m - 1] for m in sorted({d.month for d in g}))
            yrsp = (g[-1] - g[0]).days / 365.25
            print(f"  p={period:<4d} off {off:<6d} {len(g):>9} {len(g)/yrsp:>12.2f} "
                  f"{months:<42} {max(doy)-min(doy):>9}")
    locked = {p: max(len({d.month for i, d in enumerate(days)
                          if WHOLE[0] <= d <= WHOLE[1] and sidx[i] % p == o})
                     for o in range(p)) for p in PERIODS}
    for p_, m_ in locked.items():
        verdict = "CALENDAR-LOCKED" if m_ <= 6 else "calendar-free"
        print(f"  period {p_}: the widest any offset spreads is {m_} of 12 months -> {verdict}")

    # ---------------------------------------------------------------- Job A
    print()
    print("=" * 102)
    print("JOB A -- THE SESSION GRIDS.  SPY ALONE, MONTHLY ACTING, 200-bar gate, one-session lag.")
    print("ALL RETURNS UNFUNDED: price returns on a weight path, no deposits, no fees, no picking.")
    print(f"whole window {WHOLE[0]}..{WHOLE[1]};  era {ERA_2009[0]}..{ERA_2009[1]}")
    print("=" * 102)
    native = row_for(None, "native (every month end)")
    print(f"{'reading':<26} {'CAGR':>8} {'worst':>8} {'2009-15':>8} {'invest':>7} {'flips':>6}")
    print(f"{native.label:<26} {native.cagr:>7.2%} {native.dd:>7.1%} {native.era:>7.2%} "
          f"{native.invested:>6.1%} {native.flips:>6d}   <- the rung every book in the lab runs")
    ses: dict[tuple[int, int], Row] = {}
    for period in PERIODS:
        for off in range(period):
            ses[(period, off)] = row_for(ses_pick(period, off), f"p={period} off {off}")
    for period in PERIODS:
        print(f"  -- period {period}: the arms the method runs --")
        for off in OFFSETS[period]:
            r = ses[(period, off)]
            print(f"{r.label:<26} {r.cagr:>7.2%} {r.dd:>7.1%} {r.era:>7.2%} "
                  f"{r.invested:>6.1%} {r.flips:>6d}")
        best = max(range(period), key=lambda o: ses[(period, o)].cagr)
        worst = min(range(period), key=lambda o: ses[(period, o)].cagr)
        print(f"  -- period {period}: the extremes of the whole {period}-offset grid --")
        for off in (best, worst):
            r = ses[(period, off)]
            print(f"{r.label:<26} {r.cagr:>7.2%} {r.dd:>7.1%} {r.era:>7.2%} "
                  f"{r.invested:>6.1%} {r.flips:>6d}")

    # ---------------------------------------------------------------- Job B
    print()
    print("=" * 102)
    print("JOB B -- THE CALENDAR GRID, RECOMPUTED HERE by M0261's own anchor, same bars, same")
    print("process.  These rows must reproduce M0261's prior or nothing below is a comparison.")
    print("=" * 102)
    cal: dict[tuple[int, int], Row] = {}
    for k in (6, 12):
        for p_ in range(k):
            cal[(k, p_)] = row_for(cal_pick(k, p_),
                                   f"k={k:<2d} phase {p_:<2d} {months_of(k, p_)}")
    print(f"{'reading':<26} {'CAGR':>8} {'worst':>8} {'2009-15':>8} {'invest':>7} {'flips':>6}")
    for k in (6, 12):
        for p_ in range(k):
            r = cal[(k, p_)]
            print(f"{r.label:<26} {r.cagr:>7.2%} {r.dd:>7.1%} {r.era:>7.2%} "
                  f"{r.invested:>6.1%} {r.flips:>6d}")

    ok = True
    checks = [("native CAGR", native.cagr, 0.0819, 0.0015),
              ("native fall", native.dd, -0.190, 0.004),
              ("k=6 best CAGR", max(cal[(6, p_)].cagr for p_ in range(6)), 0.0976, 0.0015),
              ("k=6 worst CAGR", min(cal[(6, p_)].cagr for p_ in range(6)), 0.0603, 0.0015),
              ("k=12 best CAGR", max(cal[(12, p_)].cagr for p_ in range(12)), 0.0902, 0.0015),
              ("k=12 worst CAGR", min(cal[(12, p_)].cagr for p_ in range(12)), 0.0447, 0.0015),
              ("k=12 worst fall", min(cal[(12, p_)].dd for p_ in range(12)), -0.518, 0.006)]
    print()
    print("  REPRODUCTION OF M0261'S PRIOR (its hypothesis quotes these):")
    for name, got, want, tol in checks:
        hit = abs(got - want) <= tol
        ok = ok and hit
        print(f"    {name:<18} got {got:>8.2%}  want {want:>8.2%}  {'OK' if hit else 'MISMATCH'}")

    # ---------------------------------------------------------------- Job C
    print()
    print("=" * 102)
    print("JOB C -- THE FAIR COMPARISON.  A 131-offset range is not a 6-phase range: more draws")
    print("spread wider for free.  So: the standard deviation, which does not grow with the draw")
    print("count, and the MEAN PAIRWISE GAP, which is the 2-draw statistic M0261 reported funded.")
    print("=" * 102)

    def pairgap(xs: list[float]) -> float:
        a = np.asarray(xs, dtype=float)
        return float(np.abs(a[:, None] - a[None, :]).sum() / (len(a) * (len(a) - 1))) * 100.0

    print(f"{'grid':<36} {'draws':>6} {'range':>8} {'sd':>7} {'mean pair gap':>14} "
          f"{'fall sd':>8}")
    grids: list[tuple[str, list[float], list[float]]] = []
    for period in PERIODS:
        grids.append((f"SESSION period {period}, all offsets",
                      [ses[(period, o)].cagr for o in range(period)],
                      [ses[(period, o)].dd for o in range(period)]))
    grids.append(("CALENDAR half-yearly, all phases",
                  [cal[(6, p_)].cagr for p_ in range(6)], [cal[(6, p_)].dd for p_ in range(6)]))
    grids.append(("CALENDAR yearly, all phases",
                  [cal[(12, p_)].cagr for p_ in range(12)], [cal[(12, p_)].dd for p_ in range(12)]))
    for label, cs, ds in grids:
        rc, sc = spread(cs)
        _, sd = spread(ds)
        print(f"{label:<36} {len(cs):>6} {rc:>7.2f}p {sc:>6.2f}p {pairgap(cs):>13.2f}p "
              f"{sd:>7.1f}p")

    print()
    print("  THE ARMS THE METHOD RUNS, and the matched 2-draw gaps it will report funded:")
    for period in PERIODS:
        offs = OFFSETS[period]
        cs = [ses[(period, o)].cagr for o in offs]
        ds = [ses[(period, o)].dd for o in offs]
        print(f"    p={period} offsets {offs}: CAGR range {spread(cs)[0]:.2f}p, mean pair gap "
              f"{pairgap(cs):.2f}p, fall range {spread(ds)[0]:.1f}p")
    gap126 = abs(ses[(126, 0)].cagr - ses[(126, 63)].cagr) * 100
    gap131 = abs(ses[(131, 0)].cagr - ses[(131, 65)].cagr) * 100
    print("    THE HEADLINE PAIR, maximally separated at each period:")
    print(f"      locked p=126 off 0 vs off 63 : {gap126:.2f} points of UNFUNDED CAGR")
    print(f"      free   p=131 off 0 vs off 65 : {gap131:.2f} points of UNFUNDED CAGR")
    print(f"      M0261's calendar Jun/Dec vs Mar/Sep, same bars: "
          f"{abs(cal[(6,5)].cagr - cal[(6,2)].cagr)*100:.2f} points UNFUNDED "
          f"(3.21 points FUNDED on its real book)")

    # ---------------------------------------------------------------- Job D
    print()
    print("=" * 102)
    print("JOB D -- THE ANCHOR PROBE, at every monthly decision session the method will run.")
    print("=" * 102)
    print(f"{'reading':<18} {'sessions':>8} {'fallbacks':>10} {'late':>6} {'min bars':>9} "
          f"{'max stale':>22} {'dates':>6}")
    worst_stale = 0
    min_bars_overall = 10 ** 9
    for period in PERIODS:
        for off in OFFSETS[period]:
            fallbacks = late = 0
            min_bars, max_stale, max_stale_at = 10 ** 9, -1, None
            seen: set[date] = set()
            for s_ in decisions:
                dd = nyse.prev_session(s_)
                a = ses_anchor(h, dd, period, off, sidx)
                if not a.found:
                    fallbacks += 1
                if a.at > dd:
                    late += 1
                seen.add(a.at)
                min_bars = min(min_bars, a.index + 1)
                j = int(np.searchsorted(h.dates, np.datetime64(dd, "D"), side="right")) - 1
                if j - a.index > max_stale:
                    max_stale, max_stale_at = j - a.index, dd
            worst_stale = max(worst_stale, max_stale)
            min_bars_overall = min(min_bars_overall, min_bars)
            if fallbacks or late:
                ok = False
            print(f"p={period} off {off:<6d} {len(decisions):>8} {fallbacks:>10} {late:>6} "
                  f"{min_bars:>9} {max_stale:>8} ({str(max_stale_at)[:10]}) {len(seen):>6}")

    print()
    print(f"  WORST STALENESS ACROSS THE FIVE ANCHORED ARMS: {worst_stale} sessions.")
    print(f"  So a {TREND_N}-bar gate read at the worst anchor needs {TREND_N + worst_stale} "
          f"bars on hand.")
    print("  M0261's lookback is 454 (200 + 254), carried here so the two ladders are scored")
    print(f"  under identical arithmetic.  Fits with {454 - TREND_N - worst_stale} to spare: "
          f"{'YES' if 454 >= TREND_N + worst_stale else 'NO'}")
    print(f"  Fewest SPY bars behind any anchor at any decision session: {min_bars_overall}.")

    print()
    print("  THE PERIOD-1 IDENTITY: at period 1 every bar is a grid bar, so the anchor must BE")
    print("  the data date and the session ladder's fastest rung must be the native arm.")
    broken = [nyse.prev_session(s_) for s_ in decisions
              if ses_anchor(h, nyse.prev_session(s_), 1, 0, sidx).at != nyse.prev_session(s_)]
    if broken:
        ok = False
        print(f"    BROKEN on {len(broken)} sessions, first {broken[:6]}")
    else:
        print(f"    HOLDS on all {len(decisions)} monthly decision sessions.")

    print()
    print("STRUCTURAL CHECKS:", "ALL PASSED" if ok else "FAILED -- read the lines above")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
