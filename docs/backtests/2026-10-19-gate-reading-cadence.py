"""How often should a book READ its safety gate -- and is the month-end anchor sound?

M0258 measured one paired difference it was not looking for. The same book, the same bare SPY
200-day gate, nothing moving but the rule set's cadence: 12.33%/yr of the owner's own money and a
23.80% fall read MONTHLY, against 5.32%/yr and a 35.49% fall read WEEKLY. +7.01 points a year and
11.69 points of worst fall, from a dial nobody in this lab has ever turned on purpose. Every book
here inherits its gate cadence from however often it happens to re-pick stocks. M0260 asks where
that axis turns, and this file is what has to exist before M0260's hypothesis can be written down,
because a pre-registration is frozen by its own commit and may not quote a number that was guessed.

Two jobs, in one file, because they answer one question between them.

**Job A, the prior grid.** SPY alone, the dev store's own closes, a 200-bar average, a one-session
lag, the signal held exactly as it was read at each decision session. Rows: the gate read at
anchored intervals of 1, 2, 3, 6 and 12 months on a book that acts MONTHLY, against the two native
readings M0258's own grid produced (acted monthly, acted weekly), plus the weekly book reading a
monthly-anchored gate -- Appendix B's decomposition arm, in its SPY-alone shadow.

This is a FEASIBILITY TABLE AND A PRIOR, not a result. It stands beside M0245's episode ledger and
M0241's split-count table: something measured on market data so that a method's hypothesis is a
prediction rather than a hope. Nothing here is recorded -- no method, no trial, no N, no
test-window look -- and the lab's gate accepts it as nothing more. It is also SPY alone and
therefore **UNFUNDED**: no monthly top-up, no Gotrade fee, no deposits. Every return in it is a
price-return CAGR on a weight path, and the word UNFUNDED is printed beside each one so that no
figure from this file can wander into a sentence about the owner's money. The lab's own headline
number is `trial_funding.mwr`, and nothing in this file is that.

**Job B, the anchor probe.** The ladder above monthly only exists because an allocator may read the
gate at a date EARLIER than its `data_date`. Anchor that reading to a month-end grid and the rule
set never moves, so the book still re-picks monthly, still runs on `monthly-hold-frac-gotrade`,
and stays promotable. The anchor is:

    month_index(d) = (d.year - 1970) * 12 + (d.month - 1)

    anchor(h, data_date, k) = the newest bar a of h with a <= data_date such that
                                (i)  a is the last session of its calendar month, and
                                (ii) month_index(a) % k == k - 1
                              falling back to data_date when no such bar is on hand

Phase `k - 1` makes the grid calendar-natural: k=1 every month end, k=2 Feb/Apr/.../Dec, k=3 the
calendar quarters, k=6 Jun/Dec, k=12 December alone.

That definition carries four structural claims, and the method file's arm table rests on all four.
This job walks every decision session of the dev window, for both a monthly and a weekly rule set,
and checks each one by name rather than by argument:

  1. the anchor always RESOLVES -- the fall-back to `data_date` is never taken;
  2. every resolved anchor has at least 200 SPY bars behind it, or the gate reads False and the
     arm is spuriously all-cash for reasons that have nothing to do with the market;
  3. the anchor is never later than `data_date` (plan invariant 9);
  4. on a MONTHLY rule set, anchor(h, data_date, 1) == data_date on every single decision session
     -- because a monthly book's `data_date` is `prev_session(first session of month M)`, which is
     the last session of month M-1, which is a month end. This is why the plan's arm table does NOT
     spend a trial on an anchored k=1 monthly arm: it would be the native arm under another digest.
     **If this is ever false the arm table is wrong**, and the output says so in capitals;
  5. on a WEEKLY rule set, anchor(h, data_date, 1) equals the bar the MONTHLY arm is reading at
     that moment. This is the sentence Appendix B's decomposition rests on: arm C literally reuses
     arm A's gate reading, so (A - C) moves re-pick frequency and nothing else.

**Why the anchor is written out here instead of imported.** Phase 2 writes the production anchor
inside the method file. If this file imported it, agreement would be a tautology. So the arithmetic
below is independent: the rank-session calendar is re-derived from `seer_engine.dates` rather than
taken from `sim.rules.is_rank_session`, the month-end test is re-derived from the bars rather than
taken from the allocator, and the gate is a plain comparison against a plain trailing mean. The
only things imported are the published NYSE calendar, which is a fact rather than a claim, and
`History`, so that the probe holds exactly the object the allocator will hold.

**What is NOT checked here, deliberately.** Nothing in this file touches `lab/lab.sqlite` -- not
even a read, because a read migrates the file on connect. Nothing here runs the simulator, so the
grid's returns are price returns on SPY's own closes, not the funded, fee-paying, deposit-matched
returns a trial records. The reproduction table at the foot compares WORST FALL only, against two
SPY-only trials the lab already holds, for exactly the reason M0258's study did: a drawdown on a
weight path and a drawdown on a funded book are the same shape, and a CAGR on a price series and a
money-weighted return on a deposit schedule are not.

Run it from the worktree -- unlike the M0258 study, this one takes an absolute store path:

    PYTHONPATH=<worktree>/engine/src /home/miftah/seer/engine/.venv/bin/python \\
        docs/backtests/2026-10-19-gate-reading-cadence.py \\
        --store /home/miftah/seer/engine/.research

Exit status is 0 when every structural check in Job B passed and 1 when any failed, so that a
careless reader cannot skim past a broken anchor. The grid itself has no pass or fail: it is a
prior, and a prior cannot be wrong, only surprising.
"""

from __future__ import annotations

import argparse
import csv
import os
from datetime import date
from pathlib import Path
from typing import Callable, NamedTuple

import numpy as np

from seer_engine import dates as nyse
from seer_engine.strategies.base import History

# ------------------------------------------------------------------ constants
DEV_END = date(2015, 10, 16)  # the dev window's last session; copied, not imported, on purpose
PROBE_START = date(1996, 1, 3)  # the first session the probe walks; membership opens 1996-01-02
WARM = 200  # bars held flat in cash before any signal is believed: M0258's study's number
TREND_N = 200  # the gate's window, == f_factor's ("SPY", 200) for every book on this chassis
WHOLE = (date(1994, 1, 1), DEV_END)  # M0258's study's window, unchanged, so the rows compare
ERA_2009 = (date(2009, 1, 1), DEV_END)
RUNGS = (1, 2, 3, 6, 12)
RUNG_LABEL = {
    1: "k=1  every month end",
    2: "k=2  Feb/Apr/.../Dec",
    3: "k=3  calendar quarters",
    6: "k=6  Jun/Dec",
    12: "k=12 December only",
}
MAX_LISTED = 12  # how many offending dates a failed check prints before it says "and N more"


# ------------------------------------------------------------------ the tape
def load_spy(store: Path) -> History:
    """SPY's own bars from the store's ``bars.csv``, as the ``History`` an allocator would hold.

    Sorted by date because the store writes bars grouped by symbol, and every cumulative form
    below is nonsense on an unsorted array. ``History`` itself refuses a non-ascending date array,
    so this is belt and braces rather than trust.
    """
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
        col("open"),
        col("high"),
        col("low"),
        col("close"),
        col("volume"),
    )


def sma(a: np.ndarray, w: int) -> np.ndarray:
    """The trailing ``w``-bar mean, NaN until there are ``w`` bars. Cumulative-sum form."""
    out = np.full(len(a), np.nan)
    cs = np.cumsum(np.insert(a, 0, 0.0))
    out[w - 1:] = (cs[w:] - cs[:-w]) / w
    return out


def bare_gate(close: np.ndarray, avg: np.ndarray) -> np.ndarray:
    """The lab's shared gate: in while SPY closes above its 200-day average, out below it.

    A NaN average -- the warmup -- reads OUT rather than IN, so a warmup bar can never be credited
    with a return. ``equity`` zeroes those bars anyway; doing it here too keeps the signal honest
    on its own, for anyone who plots it.
    """
    return np.where(np.isnan(avg), 0.0, (close > avg).astype(float))


# ------------------------------------------------------------------ the calendars
def month_index(d: date) -> int:
    """Appendix C's month index: calendar months since January 1970, as one integer."""
    return (d.year - 1970) * 12 + (d.month - 1)


def month_end_by_bars(h: History) -> np.ndarray:
    """Appendix C's condition (i) decided from the BARS: is bar j the last of its month?

    For an interior bar this is a comparison with the next bar on hand, which is a bar the
    allocator already holds dated on or before its ``data_date``, so it leaks nothing. The final
    entry is left False because the bars alone cannot decide it -- that one is the calendar's
    question, and ``month_end_by_calendar`` answers it.
    """
    months = h.dates.astype("datetime64[M]")
    flags = np.zeros(len(h), dtype=bool)
    flags[:-1] = months[1:] != months[:-1]
    return flags


def month_end_by_calendar(h: History) -> np.ndarray:
    """The same question asked of the published NYSE calendar: is the next SESSION a new month?

    This is the form an allocator must use for the newest bar it holds, where there is no next bar.
    A calendar read inside a lab allocator is established practice -- m0052, m0120, m0024, m0051,
    m0079, m0085, m0086, m0204 and m0020 all do it -- and ``allocatorkit.assert_no_lookahead``
    perturbs bars, never the calendar. Computing it for EVERY bar here is not waste: comparing the
    two arrays is what proves the cheap interior test is safe on this symbol.
    """
    out = np.zeros(len(h), dtype=bool)
    for i in range(len(h)):
        d = h.dates[i].item()
        out[i] = nyse.next_session(d).month != d.month
    return out


class Anchor(NamedTuple):
    """Where a gate reading was taken, and what stood behind it.

    ``index`` is the anchor's row in the history, or -1 when the anchor has no bar at all (only
    reachable through the fall-back). ``found`` is False exactly when Appendix C's fall-back to
    ``data_date`` was taken, which is the thing Job B exists to prove never happens.
    """

    at: date
    index: int
    found: bool


def anchor(h: History, data_date: date, k: int, me_bars: np.ndarray) -> Anchor:
    """Appendix C, written out: the newest qualifying month-end bar on or before ``data_date``.

    The scan is a backward scan rather than a vectorised lookup because this function is a second
    pair of eyes on phase 2's production anchor, and a literal transcription of the definition is
    worth more here than speed. It is cheap anyway: even k=12 walks at most about 250 bars.

    The month-end test is split exactly as the definition splits it. For the newest bar on hand it
    asks the calendar, because there is no next bar to compare against and the allocator will be in
    the same position. For every older bar it compares months with the next bar, which is on hand.
    """
    j = int(np.searchsorted(h.dates, np.datetime64(data_date, "D"), side="right")) - 1
    for i in range(j, -1, -1):
        a = h.dates[i].item()
        is_month_end = (nyse.next_session(a).month != a.month) if i == j else bool(me_bars[i])
        if is_month_end and month_index(a) % k == k - 1:
            return Anchor(a, i, True)
    idx = h.index_of(data_date)
    return Anchor(data_date, -1 if idx is None else idx, False)


def decision_sessions(cadence: str, lo: date, hi: date) -> list[date]:
    """Every session in [lo, hi] on which a book of this cadence calls its allocator.

    Written out rather than imported from ``sim.rules.is_rank_session``, because the point of this
    file is to be a second pair of eyes on the chassis and not an echo of it. The two are the same
    sentence: a rank session is the FIRST NYSE session of its period -- its calendar month for a
    monthly rule set, its ISO (year, week) for a weekly one.

    A rank session is the only session that matters here. Both rule sets this method runs on carry
    ``resize_cadence=None``, so ``is_resize_session`` is always False, and no backtest passes
    ``kickoff`` (it is paper trading's first decision, ``book_runner`` line 393).
    """
    out: list[date] = []
    for s in nyse.sessions(lo, hi):
        p = nyse.prev_session(s)
        if cadence == "monthly":
            opens = (s.year, s.month) != (p.year, p.month)
        elif cadence == "weekly":
            opens = s.isocalendar()[:2] != p.isocalendar()[:2]
        else:
            raise ValueError(f"unknown cadence {cadence!r}")
        if opens:
            out.append(s)
    return out


def monthly_reading_for(s: date) -> date:
    """The date a MONTHLY book's gate reading in force on session ``s`` was taken at.

    A monthly book re-picks on the first NYSE session of each calendar month and reads the gate at
    ``data_date = prev_session(that session)``. So on any session in month M the reading in force
    was taken at the last NYSE session of month M-1, and it is held, untouched, all month.
    """
    first_of_month = nyse.sessions(date(s.year, s.month, 1), s)[0]
    return nyse.prev_session(first_of_month)


# ------------------------------------------------------------------ Job A: the weight paths
def read_at(
    signal: np.ndarray,
    act: np.ndarray,
    h: History,
    me_bars: np.ndarray,
    k: int | None,
) -> np.ndarray:
    """Hold the signal AS READ at each decision session: the one thing this file adds to the gate.

    A book does not act on a signal it never looked at. At each act bar it takes one reading and
    holds it -- through every crossing, in both directions -- until the next act bar. ``k`` None is
    the native reading, taken at the act bar itself; an integer ``k`` is the anchored reading,
    taken at the newest qualifying month end on or before it, which is never later.
    """
    out = np.zeros(len(signal))
    current = 0.0
    for i in range(len(signal)):
        if act[i]:
            if k is None:
                current = signal[i]
            else:
                a = anchor(h, h.dates[i].item(), k, me_bars)
                current = signal[a.index] if a.index >= 0 else 0.0
        out[i] = current
    return out


def equity(weight: np.ndarray, ret: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Equity from a weight path, lagged one session, with the warmup held flat in cash.

    A signal read at the close of bar i is acted on at bar i+1. Nothing here trades on a close it
    has not seen, which is the same one-session lag the simulator gives every allocator.
    """
    w = np.zeros(len(weight))
    w[1:] = weight[:-1]
    w[:WARM] = 0.0
    return np.cumprod(1.0 + ret * w), w


def stats(
    eq: np.ndarray, w: np.ndarray, days: np.ndarray, lo: date, hi: date
) -> tuple[float, float, float]:
    """(CAGR, worst peak-to-trough fall, mean fraction invested) over the closed era [lo, hi].

    UNFUNDED, every one of them: this is a weight path on SPY's own closes, with no deposits, no
    fees and no fills. The lab's money number is ``trial_funding.mwr`` and this is not it.
    """
    i = np.where((days >= lo) & (days <= hi))[0]
    years = (days[i[-1]] - days[i[0]]).days / 365.25
    e = eq[i] / eq[i[0]]
    return e[-1] ** (1 / years) - 1.0, float((e / np.maximum.accumulate(e) - 1.0).min()), float(w[i].mean())


def flips(w: np.ndarray) -> int:
    """How many times the book changed its mind. The cost axis, and the cadence's whole claim."""
    return int((np.diff(w) != 0).sum())


class Row(NamedTuple):
    """One line of the prior grid. Every return in it is UNFUNDED."""

    label: str
    acts: str
    cagr: float
    dd: float
    era: float
    invested: float
    flips: int


def grid_row(
    label: str,
    acts: str,
    signal: np.ndarray,
    act_mask: np.ndarray,
    h: History,
    me_bars: np.ndarray,
    k: int | None,
    ret: np.ndarray,
    days: np.ndarray,
) -> Row:
    """Score one reading of the gate over both eras."""
    eq, w = equity(read_at(signal, act_mask, h, me_bars, k), ret)
    cagr, dd, invested = stats(eq, w, days, *WHOLE)
    era, _, _ = stats(eq, w, days, *ERA_2009)
    return Row(label, acts, cagr, dd, era, invested, flips(w))


# ------------------------------------------------------------------ Job B: the probe
class Probe(NamedTuple):
    """What one rung of the anchor grid did across one rule set's decision sessions."""

    cadence: str
    k: int
    sessions: int
    fallbacks: list[date]
    late: list[date]
    min_bars: int
    min_bars_at: date | None
    max_stale_days: int
    max_stale_at: date | None
    reads: int


def probe(h: History, me_bars: np.ndarray, cadence: str, k: int, decisions: list[date]) -> Probe:
    """Resolve the anchor at every decision session of one rule set, and collect what it did.

    Pure: it counts and returns, and prints nothing. Every number it carries is one the method
    file's docstring is allowed to quote, which is why they are named rather than printed.
    """
    fallbacks: list[date] = []
    late: list[date] = []
    min_bars, min_bars_at = -1, None
    max_stale, max_stale_at = -1, None
    seen: set[date] = set()
    for s in decisions:
        data_date = nyse.prev_session(s)
        a = anchor(h, data_date, k, me_bars)
        if not a.found:
            fallbacks.append(data_date)
        if a.at > data_date:
            late.append(data_date)
        seen.add(a.at)
        bars = a.index + 1
        if min_bars < 0 or bars < min_bars:
            min_bars, min_bars_at = bars, data_date
        stale = (data_date - a.at).days
        if stale > max_stale:
            max_stale, max_stale_at = stale, data_date
    return Probe(
        cadence, k, len(decisions), fallbacks, late, min_bars, min_bars_at, max_stale, max_stale_at, len(seen)
    )


def identity_check(h: History, me_bars: np.ndarray, decisions: list[date]) -> list[date]:
    """The sessions where a MONTHLY book's k=1 anchor was NOT its own ``data_date``.

    Expected empty. A monthly book's ``data_date`` is ``prev_session(first session of month M)``,
    the last session of month M-1, which is a month end and so qualifies at k=1 on the spot. Every
    date this returns is a hole in the plan's arm table, not a curiosity.
    """
    out: list[date] = []
    for s in decisions:
        data_date = nyse.prev_session(s)
        if anchor(h, data_date, 1, me_bars).at != data_date:
            out.append(data_date)
    return out


def decomposition_check(
    h: History, me_bars: np.ndarray, decisions: list[date]
) -> tuple[int, list[tuple[date, date, date]]]:
    """Does a WEEKLY book's k=1 anchor read the same bar the MONTHLY book is reading?

    Returns (agreements, disagreements as (weekly data_date, anchor, the monthly arm's reading)).
    Expected: every weekly decision session agrees. This is the sentence Appendix B's decomposition
    rests on -- arm C reuses arm A's reading, so (A - C) moves re-pick frequency and nothing else.
    """
    agree = 0
    bad: list[tuple[date, date, date]] = []
    for s in decisions:
        data_date = nyse.prev_session(s)
        mine = anchor(h, data_date, 1, me_bars).at
        theirs = monthly_reading_for(s)
        if mine == theirs:
            agree += 1
        else:
            bad.append((data_date, mine, theirs))
    return agree, bad


# ------------------------------------------------------------------ reporting
def listed(ds: list[date]) -> str:
    """Up to MAX_LISTED dates, then a count. A failed check must name names, not just a number."""
    if not ds:
        return "-"
    head = ", ".join(d.isoformat() for d in ds[:MAX_LISTED])
    return head if len(ds) <= MAX_LISTED else f"{head}, and {len(ds) - MAX_LISTED} more"


def report_prior(rows: list[Row]) -> None:
    print("Table 1 -- the prior grid: SPY alone, bare 200-day gate, read at a month-end anchor")
    print("ALL FIGURES UNFUNDED: a weight path on SPY's own closes. No deposits, no fees, no fills.")
    print()
    print(f"{'gate read':26s} {'book acts':>9} {'CAGR*':>8} {'worst':>8} {'09-15*':>8} {'inv':>7} {'flips':>6}")
    print("-" * 78)
    for r in rows:
        print(
            f"{r.label:26s} {r.acts:>9} {r.cagr * 100:7.2f}% {r.dd * 100:7.1f}% "
            f"{r.era * 100:7.2f}% {r.invested * 100:6.1f}% {r.flips:6d}"
        )
    print()
    print("* unfunded price-return CAGR. The lab's money number is trial_funding.mwr; this is not it.")


def report_ladder(rows: dict[str, Row]) -> None:
    print()
    print("Table 2 -- each anchored rung minus the native monthly reading (UNFUNDED)")
    print("A positive drawdown difference means the anchored rung fell LESS.")
    print()
    base = rows["native/monthly"]
    print(f"{'rung':26s} {'CAGR diff':>12} {'worst-fall diff':>18} {'flips':>8}")
    print("-" * 68)
    for k in RUNGS:
        r = rows[f"k{k}/monthly"]
        print(
            f"{RUNG_LABEL[k]:26s} {(r.cagr - base.cagr) * 100:+11.2f} "
            f"{(r.dd - base.dd) * 100:+17.1f} {r.flips - base.flips:+8d}"
        )


def report_decomposition(rows: dict[str, Row]) -> None:
    print()
    print("Table 3 -- Appendix B's decomposition, in its SPY-alone shadow (UNFUNDED)")
    print("A = monthly book, native reading.  B = weekly book, native reading.")
    print("C = weekly book, monthly-anchored reading (k=1): the decomposition arm.")
    print("(A - C) is re-pick frequency with the gate held; (C - B) is gate cadence with the")
    print("re-pick held; they sum to (A - B) by construction, not by luck.")
    print()
    a, b, c = rows["native/monthly"], rows["native/weekly"], rows["k1/weekly"]
    print(f"{'term':34s} {'CAGR diff':>12} {'worst-fall diff':>18}")
    print("-" * 66)
    for name, x, y in (
        ("A - B   total (M0258's number)", a, b),
        ("A - C   re-pick frequency", a, c),
        ("C - B   gate reading cadence", c, b),
    ):
        print(f"{name:34s} {(x.cagr - y.cagr) * 100:+11.2f} {(x.dd - y.dd) * 100:+17.1f}")


def report_reproduction(rows: dict[str, Row]) -> None:
    """Why the grid is trusted at all: it reproduces two recorded SPY-only trials, with no shared code.

    The recorded figures come from ``docs/backtests/2026-10-19-gate-band-cadence.py``'s own
    reproduction block, which read them from ``lab/lab.sqlite`` trials n = 348 and 350, window
    'dev'. They are quoted from that committed file rather than re-queried, because a lab read
    migrates ``lab.sqlite`` on connect and this phase writes nothing to the lab.

    Worst fall only, deliberately. A drawdown on a weight path and a drawdown on a funded book are
    the same shape; a price CAGR and a money-weighted return on a deposit schedule are not.
    """
    print()
    print("Table 3b -- reproduction of the lab's own recorded SPY-only trials (worst fall, %)")
    print()
    print(f"{'recorded trial':40s} {'recorded':>9} {'this grid':>10}")
    print("-" * 62)
    for label, key, recorded in (
        ("M0084-MONTHLY  bare gate, read monthly", "native/monthly", 18.89),
        ("M0084-WEEKLY   bare gate, read weekly ", "native/weekly", 33.13),
    ):
        print(f"{label:40s} {recorded:8.2f}% {-rows[key].dd * 100:9.1f}%")


def report_probe(probes: list[Probe]) -> None:
    print()
    print("Table 4 -- the anchor probe on the real dev store, every decision session 1996-01-03..2015-10-16")
    print()
    print(
        f"{'rule set':9s} {'rung':26s} {'sessions':>9} {'reads':>6} {'fallbacks':>10} "
        f"{'late':>5} {'min bars':>9} {'max stale':>10}"
    )
    print("-" * 92)
    for p in probes:
        print(
            f"{p.cadence:9s} {RUNG_LABEL[p.k]:26s} {p.sessions:9d} {p.reads:6d} "
            f"{len(p.fallbacks):10d} {len(p.late):5d} {p.min_bars:9d} {p.max_stale_days:9d}d"
        )
    print()
    print("reads      = distinct anchor dates used, i.e. how often the gate was actually re-read")
    print("fallbacks  = sessions where no qualifying month end was on hand (MUST be 0)")
    print("late       = sessions where the anchor was later than data_date (MUST be 0: invariant 9)")
    print("min bars   = fewest SPY bars behind any resolved anchor (MUST be >= 200, or trend_on")
    print("             returns False and the arm is all-cash for a reason the market never gave)")
    for p in probes:
        if p.fallbacks:
            print(f"  FALLBACKS {p.cadence} {RUNG_LABEL[p.k]}: {listed(p.fallbacks)}")
        if p.late:
            print(f"  LATE ANCHOR {p.cadence} {RUNG_LABEL[p.k]}: {listed(p.late)}")
        if p.min_bars < TREND_N:
            print(
                f"  THIN ANCHOR {p.cadence} {RUNG_LABEL[p.k]}: {p.min_bars} bars at "
                f"{p.min_bars_at}, below the gate's {TREND_N}"
            )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("SEER_RESEARCH_STORE", "engine/.research")),
        help="the research store to read SPY's bars from; absolute is preferred (default: "
        "$SEER_RESEARCH_STORE, else engine/.research relative to the working directory)",
    )
    args = ap.parse_args()

    h = load_spy(args.store)
    days = h.dates.astype(object)
    me_bars = month_end_by_bars(h)
    me_cal = month_end_by_calendar(h)

    print(f"SPY from {args.store}/bars.csv: {len(h)} bars, {days[0]} .. {days[-1]}")
    print()

    # --- Job A ------------------------------------------------------------
    close = h.close
    ret = np.zeros(len(h))
    ret[1:] = close[1:] / close[:-1] - 1.0
    signal = bare_gate(close, sma(close, TREND_N))

    months = h.dates.astype("datetime64[M]")
    act_monthly = np.zeros(len(h), dtype=bool)
    act_monthly[:-1] = months[1:] != months[:-1]
    weekday = np.array([d.weekday() for d in days])
    act_weekly = np.zeros(len(h), dtype=bool)
    act_weekly[:-1] = weekday[1:] < weekday[:-1]

    rows: dict[str, Row] = {}
    rows["native/monthly"] = grid_row(
        "native (at data_date)", "monthly", signal, act_monthly, h, me_bars, None, ret, days
    )
    for k in RUNGS:
        rows[f"k{k}/monthly"] = grid_row(
            RUNG_LABEL[k], "monthly", signal, act_monthly, h, me_bars, k, ret, days
        )
    rows["native/weekly"] = grid_row(
        "native (at data_date)", "weekly", signal, act_weekly, h, me_bars, None, ret, days
    )
    rows["k1/weekly"] = grid_row(RUNG_LABEL[1], "weekly", signal, act_weekly, h, me_bars, 1, ret, days)

    order = ["native/monthly"] + [f"k{k}/monthly" for k in RUNGS] + ["native/weekly", "k1/weekly"]
    report_prior([rows[key] for key in order])
    report_ladder(rows)
    report_decomposition(rows)
    report_reproduction(rows)

    # --- Job B ------------------------------------------------------------
    monthly = decision_sessions("monthly", PROBE_START, DEV_END)
    weekly = decision_sessions("weekly", PROBE_START, DEV_END)
    probes = [probe(h, me_bars, "monthly", k, monthly) for k in RUNGS]
    probes += [probe(h, me_bars, "weekly", k, weekly) for k in RUNGS]
    report_probe(probes)

    bad_identity = identity_check(h, me_bars, monthly)
    print()
    print("Table 5 -- the identity the arm table rests on: on a MONTHLY book, anchor(k=1) == data_date")
    print()
    print(f"  decision sessions checked : {len(monthly)}")
    print(f"  disagreements             : {len(bad_identity)}")
    if bad_identity:
        print()
        print("  *** THE ARM TABLE IS WRONG. An anchored k=1 monthly arm is NOT the native arm. ***")
        print("  *** Phase 2 must add it as an eighth candidate, or the ladder has no zero rung. ***")
        print(f"  offending data_dates: {listed(bad_identity)}")
    else:
        print()
        print("  Every monthly decision session reads the gate at its own data_date at k=1, so the")
        print("  anchored k=1 monthly arm would collide with M0260-M-NATIVE. Appendix A is right to")
        print("  drop it and assert it in the test module instead of spending a trial on it.")

    agree, bad_decomp = decomposition_check(h, me_bars, weekly)
    print()
    print("Table 6 -- the decomposition: a WEEKLY book's k=1 anchor vs the MONTHLY book's reading")
    print()
    print(f"  decision sessions checked : {len(weekly)}")
    print(f"  agreements                : {agree}")
    print(f"  disagreements             : {len(bad_decomp)}")
    if bad_decomp:
        print()
        print("  *** APPENDIX B IS WRONG. Arm C does not reuse arm A's reading, so (A - C) is not")
        print("  *** a clean re-pick-frequency term and the decomposition must not be published. ***")
        for dd, mine, theirs in bad_decomp[:MAX_LISTED]:
            print(f"    weekly data_date {dd}: anchor {mine}, monthly arm reading {theirs}")
        if len(bad_decomp) > MAX_LISTED:
            print(f"    and {len(bad_decomp) - MAX_LISTED} more")
    else:
        print()
        print("  Arm C literally reuses arm A's gate reading at every weekly decision session, so")
        print("  (A - C) moves re-pick frequency and nothing else, and (A - C) + (C - B) = (A - B).")

    cal_mismatch = int((me_bars[:-1] != me_cal[:-1]).sum())
    print()
    print("Table 7 -- the two month-end tests agree (the cheap interior test is safe on this symbol)")
    print()
    print(f"  bars compared                     : {len(h) - 1}")
    print(f"  bars-vs-calendar disagreements    : {cal_mismatch}")
    if cal_mismatch:
        idx = np.where(me_bars[:-1] != me_cal[:-1])[0]
        print(f"  offending bars: {listed([days[i] for i in idx])}")
        print("  SPY has a gap: the interior month-end test is NOT equivalent to the calendar one,")
        print("  and phase 2's allocator must use the calendar form for every bar, not only the last.")

    # --- the verdict ------------------------------------------------------
    checks = [
        ("anchor always resolves (no fall-back)", not any(p.fallbacks for p in probes)),
        ("anchor never later than data_date", not any(p.late for p in probes)),
        (f"every anchor has >= {TREND_N} SPY bars behind it", all(p.min_bars >= TREND_N for p in probes)),
        ("monthly k=1 anchor == data_date", not bad_identity),
        ("weekly k=1 anchor == the monthly arm's reading", not bad_decomp),
        ("bars and calendar month-end tests agree", cal_mismatch == 0),
    ]
    print()
    print("CHECKS")
    print("-" * 56)
    for name, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    failed = [name for name, ok in checks if not ok]
    print()
    print(f"{len(checks) - len(failed)} of {len(checks)} structural checks passed.")
    if failed:
        print("FAILED: " + "; ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
