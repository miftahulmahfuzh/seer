> Adopted from `/home/miftah/seer/.workflows/orchestration/gate-reading-cadence/PLAN.md` phase 1. Source: `.workflows/plan/gate-reading-cadence/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: Measure the prior and prove the anchor

**Plan set:** `GATE_READING_CADENCE_PLAN.md`
**Analysis:** `docs/analyzer/20261019-152028-SSYJ_code_analyzer.md`
**Satisfies:** R6 — separate the gate's reading cadence from the book's re-pick frequency, or
state exactly how far it can be separated on this chassis
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `docs/backtests`

---

## Goal

After this phase there is a committed, standalone study that answers two questions nothing in the
lab has answered yet: **what a SPY-alone gate does when it is read every 1, 2, 3, 6 and 12 months**
(the prior M0260's hypothesis is allowed to quote), and **whether Appendix C's month-end anchor is
sound on the real dev store** — that it always resolves to a bar the book actually holds, that
every resolved anchor has at least 200 SPY bars behind it, that it is never later than `data_date`,
that on a monthly rule set `k = 1` is the identity, and that on a weekly rule set `k = 1` reads
exactly the bar the monthly arm is reading.

**Why it must land before the method file is written.** The pre-registration *is* the method file's
commit (CLAUDE.md, the lab). Once `lab run M0260` records a trial the file is frozen by invariant 6
and cannot be corrected — not a number, not a docstring. So every number the method file's
hypothesis quotes must already be measured, and every structural claim its arm table rests on must
already be proved. Appendix A drops the anchored `k = 1` monthly arm *on the grounds that it is the
identity*, and Appendix B's decomposition is exact *on the grounds that arm C reuses arm A's
reading*. Both are claims about dates, and both are unverified until this phase runs. If either is
false, phase 2's arm table is wrong and a method id burns. This phase is the cheapest possible place
to find that out: it writes no source, records nothing, and spends nothing.

## Interface Contract

**Deletes:** none
**Renames:** none
**Creates:**
- `docs/backtests/2026-10-19-gate-reading-cadence.py` (new file)
- `docs/backtests/2026-10-19-gate-reading-cadence.md` (new file, the committed output)

**Signature changes:** none
**Requires (from earlier phases):** none — this phase is the root of the set.
**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py` (Phase 2)
- `engine/tests/test_lab_m0260_cadence.py` (Phase 2)
- `lab/lab.sqlite`, `web/data/lab.json` (Phase 3) — **no `lab` command of any kind runs in this
  phase, not even a read**: a read migrates the file on connect.
- `docs/plans/HANDOVER_20261019-the-gate-reading-cadence.md`, `.workflows/todos.md` (Phase 4)
- every file under `engine/src` and `engine/tests` — this phase edits none of them and imports
  only `seer_engine.dates` and `seer_engine.strategies.base.History`.
- `docs/plans/GATE_READING_CADENCE_PLAN.md`, `docs/analyzer/20261019-152028-SSYJ_code_analyzer.md`
  and every file under `.workflows/plan/gate-reading-cadence/` — **the coordinator committed all
  six of these on `feature/gate-reading-cadence` before phase 1 starts.** This phase neither
  creates nor commits them, and must not `git add` them. Phase 4 edits the index in the worktree,
  where it is already a tracked file.

**Numbers phase 2 will quote from the `.md`** (their names are fixed here so phase 2 can cite them
without re-running anything):

| name in the `.md` | shape | what phase 2 does with it |
|---|---|---|
| `PRIOR[k].cagr` / `PRIOR[k].dd` for `k ∈ {1,2,3,6,12}` | the "monthly book, gate read every k months" rows of **Table 1**, whole-window CAGR and worst fall, **both unfunded** | the hypothesis's predicted shape of the ladder. **The `k = 2` row is a prior only: M0260 declares six arms and `k = 2` is not one of them** (`lab.method.MAX_VARIANTS = 6`), so phase 2 quotes it as grid evidence and never as a rung it will record |
| `PRIOR.native_monthly`, `PRIOR.native_weekly` | the two native rows of Table 1, **unfunded** | the two reproduction arms' expected direction |
| `DECOMP.spy` | **Table 3**: `A−B`, `A−C`, `C−B` on SPY alone, **unfunded** | the predicted split of M0258's +7.01 pts/yr |
| `ANCHOR.fallbacks` | **Table 4**, per rung per rule set; expected `0` | the method file's claim that the anchor always resolves |
| `ANCHOR.min_bars` | Table 4, per rung; expected `≥ 200` | the claim that no anchored arm is spuriously all-cash |
| `ANCHOR.max_stale_days` | Table 4, per rung | the docstring's "a yearly arm's reading is up to N days old" |
| `ANCHOR.reads` | Table 4, distinct anchor dates per rung | the docstring's "a k=12 arm re-reads the gate N times in 20 years" |
| `IDENTITY.disagreements` | **Table 5**; expected `0` | justifies Appendix A dropping the monthly `k=1` arm |
| `DECOMP_DATES.disagreements` | **Table 6**; expected `0` | justifies Appendix B's exactness claim |

**Measured values of all of the above** (the script was run against the real dev store while this
plan was written; see Step 2's "Expected output"). Phase 2 may quote these directly and the
reconciler may treat them as settled:

- `PRIOR` monthly ladder, unfunded CAGR / worst fall: native `9.08% / 19.0%`, k=1 `9.08% / 19.0%`,
  k=2 `8.56% / 19.7%`, k=3 `6.71% / 24.5%`, k=6 `8.39% / 25.9%`, k=12 `7.06% / 19.4%`;
  native weekly `5.51% / 34.6%`; weekly k=1 `8.49% / 19.0%`. **All unfunded.**
- `DECOMP.spy`: `A−B = +3.58 pts/yr and 15.5 points of fall`, split `A−C = +0.59 / +0.0`
  (re-pick frequency) and `C−B = +2.99 / +15.5` (gate reading cadence). **All unfunded.**
- `ANCHOR.fallbacks = 0` and `ANCHOR.late = 0` on all ten rows; `ANCHOR.min_bars = 738`
  (760 on monthly k=1); `ANCHOR.max_stale_days` monthly `0 / 33 / 64 / 154 / 336`, weekly
  `29 / 59 / 91 / 182 / 364`; `ANCHOR.reads` `237 / 119 / 80 / 40 / 20`.
- `IDENTITY.disagreements = 0` over 237 monthly decision sessions.
- `DECOMP_DATES.disagreements = 0` over 1032 weekly decision sessions.

**One substantive note for phase 2's hypothesis.** On SPY alone the ladder **falls**: no rung above
monthly beats monthly on return, and k=3 and k=6 fall deeper. The hypothesis must be written as
"find where it turns", and the prior's honest answer is "at or near the fastest rung" — not
"slower is better". Writing a pre-registration that predicts a slow-gate win would be predicting
against the only prior that exists.

## Files

| File | Action | What changes |
|---|---|---|
| `docs/backtests/2026-10-19-gate-reading-cadence.py` | create | the whole study: the SPY-alone prior grid (Job A) and the anchor probe on the real dev store (Job B) |
| `docs/backtests/2026-10-19-gate-reading-cadence.md` | create | its captured output, with the invocation, the date and a short reading |

Neither file exists today. Confirm with `ls docs/backtests/2026-10-19-gate-reading-cadence.*`
before Step 1 — it must print "No such file".

---

## Implementation Steps

### Step 1: Write the study script

**File:** `docs/backtests/2026-10-19-gate-reading-cadence.py` (new file, whole contents)

**Change:** A standalone study in the genre of `docs/backtests/2026-10-19-gate-band-cadence.py`:
it shares no code path with the simulator, so that agreeing with recorded trials is evidence
rather than tautology. It imports `seer_engine.dates` (the published NYSE calendar is not
reimplementable and is not the thing being cross-checked) and `seer_engine.strategies.base.History`
(so the probe holds the very object the allocator will hold). **It imports nothing from
`seer_engine.lab.methods`, nothing from `seer_engine.sim.rules`, and nothing from
`seer_engine.strategies.f_factor`:** the anchor arithmetic, the rank-session calendar and the gate
test are all written out here in plain numpy and plain Python, because being a second pair of eyes
on phase 2 is this file's whole purpose.

It takes an **absolute `--store`** (defaulting to `$SEER_RESEARCH_STORE`, then to the relative
`engine/.research`), deliberately unlike the M0258 precedent, which read a relative path and so had
to be run from the main checkout. This one runs from the worktree.

**Code:**

```python
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
```

**Impact:** adds one file under `docs/backtests/`. Nothing imports it, nothing runs it in CI, and
`ruff check engine` does not see it (it lints `engine`, not `docs`). The tree builds and
`pytest -n0 engine/tests` is unchanged by this step — run it anyway at the end of the phase to
discharge invariant 1.

---

### Step 2: Run it and capture the output

**File:** none (a shell step)
**Change:** run the script from the worktree, against the main checkout's store and venv, with the
output captured to a file so the exit code is read from `$?` rather than from a pipeline.

**Code:**

```bash
set -u
WT=/home/miftah/.worktrees/seer/gate-reading-cadence
PY=/home/miftah/seer/engine/.venv/bin/python
STORE=/home/miftah/seer/engine/.research
OUT=${CLAUDE_SCRATCHPAD:-/tmp/seer-m0260}
mkdir -p "$OUT"

PYTHONPATH="$WT/engine/src" "$PY" \
  "$WT/docs/backtests/2026-10-19-gate-reading-cadence.py" \
  --store "$STORE" > "$OUT/phase1.out" 2>&1
echo "exit=$?"
```

Then read the captured file. **Never judge this by a piped exit code** — `echo "exit=$?"` on its
own line is the only trustworthy status, and this shell prints a spurious
`setValueForKeyFakeAssocArray:27: command not found: _encode` line at the head of every captured
file, which is noise and must be stripped before the output is committed:

```bash
sed -i '/FakeAssocArray/d' "$OUT/phase1.out"
cat "$OUT/phase1.out"
```

Expect roughly 40-70 seconds: most of it is the one pass over the store's 135 MB `bars.csv`.

**Expected output — this script was run against `/home/miftah/seer/engine/.research` while this
plan was being written, so the numbers below are measured, not predicted.** They are reproduced
here so the implementer can tell a correct run from a broken one at a glance. If the run differs
in any digit, **the script was transcribed wrongly or the store moved** — find out which before
committing anything.

```text
SPY from /home/miftah/seer/engine/.research/bars.csv: 5722 bars, 1993-01-29 .. 2015-10-16

gate read                  book acts    CAGR*    worst   09-15*     inv  flips
native (at data_date)        monthly    9.08%   -19.0%   10.07%   71.9%     22
k=1  every month end         monthly    9.08%   -19.0%   10.07%   71.9%     22
k=2  Feb/Apr/.../Dec         monthly    8.56%   -19.7%    7.86%   72.7%     20
k=3  calendar quarters       monthly    6.71%   -24.5%    6.31%   70.0%     20
k=6  Jun/Dec                 monthly    8.39%   -25.9%    7.88%   72.5%     11
k=12 December only           monthly    7.06%   -19.4%    7.25%   67.9%      9
native (at data_date)         weekly    5.51%   -34.6%    5.82%   70.8%     80
k=1  every month end          weekly    8.49%   -19.0%    8.98%   71.9%     22

A - B   total (M0258's number)           +3.58             +15.5
A - C   re-pick frequency                +0.59              +0.0
C - B   gate reading cadence             +2.99             +15.5

M0084-MONTHLY  bare gate, read monthly      18.89%      19.0%
M0084-WEEKLY   bare gate, read weekly       33.13%      34.6%

rule set  rung                        sessions  reads  fallbacks  late  min bars  max stale
monthly   k=1  every month end             237    237          0     0       760         0d
monthly   k=2  Feb/Apr/.../Dec             237    119          0     0       738        33d
monthly   k=3  calendar quarters           237     80          0     0       738        64d
monthly   k=6  Jun/Dec                     237     40          0     0       738       154d
monthly   k=12 December only               237     20          0     0       738       336d
weekly    k=1  every month end            1032    238          0     0       738        29d
weekly    k=2  Feb/Apr/.../Dec            1032    119          0     0       738        59d
weekly    k=3  calendar quarters          1032     80          0     0       738        91d
weekly    k=6  Jun/Dec                    1032     40          0     0       738       182d
weekly    k=12 December only              1032     20          0     0       738       364d

Table 5  monthly k=1 identity : 237 sessions checked, 0 disagreements
Table 6  weekly decomposition : 1032 sessions checked, 1032 agreements, 0 disagreements
Table 7  bars vs calendar     : 5721 bars compared, 0 disagreements

6 of 6 structural checks passed.
```

**What that already settles, before phase 2 writes a line:**

- **Every structural claim the plan's arm table rests on holds.** Zero fall-backs, zero late
  anchors, a minimum of 738 SPY bars behind any reading (against the gate's 200), the monthly `k=1`
  identity exact across all 237 decision sessions, and the weekly decomposition exact across all
  1032. **Appendix A and Appendix B are both confirmed. Phase 2 may proceed as written.**
- **The SPY-alone ladder is falling, not humped.** 9.08 → 8.56 → 6.71 → 8.39 → 7.06 on unfunded
  CAGR, and the fall deepens 19.0 → 25.9 before recovering. Nothing above monthly beats monthly on
  SPY alone. Phase 2's hypothesis must therefore be framed as "find where it turns", not "slower is
  better" — the prior says the turn is at or near the fastest rung.
- **The decomposition splits the right way on SPY alone:** of the +3.58 pts/yr between a monthly
  and a weekly reading, **+2.99 is the gate's reading cadence and +0.59 is the re-pick frequency**,
  and the entire 15.5 points of worst fall is the gate cadence. That is the prediction phase 3's
  funded stock-book split is measured against.
- **A yearly gate reads 20 times in 20 years and its reading is up to 336 days old** (364 on a
  weekly book). "Barely a gate at all" is now a number.

**Impact:** none on the tree. If `exit=1`, **stop and read the failed check before writing
anything else** — a failing Table 5 or Table 6 means the plan index's Appendix A or Appendix B is
wrong and the reconciler and phase 2 must be told before the method file is written. That outcome
is a finding, not a defeat; record it in the `.md` in the same plain words the script printed it in,
and say in the Handoffs section of the committed `.md` exactly which appendix it contradicts.

---

### Step 3: Turn the stdout into the committed `.md`

**File:** `docs/backtests/2026-10-19-gate-reading-cadence.md` (new file)

**Change:** the committed output. It is a record, not an essay: the invocation that produced it,
the date it was produced, every table verbatim inside one fenced block, and a short reading of what
the grid predicts for M0260's six arms. No number in it is reformatted, rounded or re-typed by
hand — the tables are the script's own stdout, pasted.

**Code (the file's skeleton; fill the fenced block with the captured stdout verbatim):**

```markdown
# The SPY-200 gate's reading cadence — the prior, and the anchor proved

**Produced:** 2026-10-19 · **Script:** `docs/backtests/2026-10-19-gate-reading-cadence.py`
**Store:** `/home/miftah/seer/engine/.research` (the dev store, 1993-01-29 .. 2015-10-16)
**Records nothing in the lab.** No method, no trial, no N, no test-window look.

    PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
      /home/miftah/seer/engine/.venv/bin/python \
      docs/backtests/2026-10-19-gate-reading-cadence.py \
      --store /home/miftah/seer/engine/.research

**Every return below is UNFUNDED.** This is a weight path on SPY's own closes — no monthly top-up,
no Gotrade fee, no fills. The lab's money number is `trial_funding.mwr`, what `lab show` prints as
"your money earned", and nothing on this page is that. The figures here are a prior for M0260's
hypothesis and a feasibility table for its anchor, in the same genre as M0245's episode ledger and
M0241's split-count table.

## Output

```text
<the captured stdout, verbatim, with the setValueForKeyFakeAssocArray noise stripped>
```

## What the grid predicts for M0260's six arms

<Three to six short paragraphs, plain language, no ids or digests in the owner-facing sentences.
They must cover, in this order:>

1. **The shape of the ladder.** Whether the SPY-alone rungs rise, fall, hump or stay flat from
   k=1 to k=12, and where the turn is if there is one. State it as a prediction for the stock book,
   not as a result: SPY alone has no stock picking in it, and the +3.6 pts/yr gate premium that
   makes this question worth asking was measured on books that hold stocks.
1b. **`k = 2` is measured here as a prior only, and is NOT one of M0260's arms.** This grid runs
   five monthly rungs (k = 1, 2, 3, 6, 12) because a prior may be wider than the ladder it informs,
   and because the k=2 row is what tells a reader whether the fall from k=1 to k=3 is a cliff or a
   slope. But `lab.method.MAX_VARIANTS = 6` caps a `Method` at six candidates
   (`engine/src/seer_engine/lab/method.py:40`, enforced in `Method.__post_init__`), and M0260
   spends its six on `M-NATIVE`, `M-G3`, `M-G6`, `M-G12`, `W-NATIVE` and `W-G1`. **So say in this
   `.md`, in one sentence, that the two-month rung is measured here and deferred to an `Amendment`
   under the same method id** — an amendment costs no method id and is the right home for it if
   phase 3's ladder comes back humped between `M-NATIVE` and `M-G3`. Do not let the `.md` imply
   that a `k = 2` trial is coming.
2. **The yearly rung.** How many times a k=12 arm actually re-reads the gate across the window
   (Table 4's `reads`), and how stale its reading gets (Table 4's `max stale`). This is the number
   behind "a gate read yearly is barely a gate at all" — now measured instead of asserted.
3. **The decomposition.** Table 3's `A − C` and `C − B` on SPY alone, and the explicit warning that
   the real split will be measured on the funded stock book in phase 3 and may differ in size, but
   cannot differ in *structure*, because Table 6 proved arm C reads arm A's bar.
4. **What the anchor probe settles.** Zero fall-backs, zero late anchors, the minimum bar count
   behind any reading, and therefore: no anchored arm is all-cash for a reason the market never
   gave, and Appendix A is right to drop the monthly k=1 arm.
5. **What this page is not.** It is not a lab result and must not be cited as one. It is unfunded,
   it is SPY alone, and it was produced before any trial was recorded — which is the point.
```

**Impact:** adds one file under `docs/backtests/`. Nothing reads it automatically; phase 2's
method-file docstring cites it by path and quotes the named figures in the Interface Contract above.

---

### Step 4: Discharge invariant 1, then commit both files

**File:** none (a shell step), then the commit.

**Change:** the phase edits no source, so the suite cannot have moved — run it anyway, because
invariant 1 binds every phase and a green run here is what lets phase 2 attribute any later
breakage to itself.

**Code:**

```bash
set -u
WT=/home/miftah/.worktrees/seer/gate-reading-cadence
PY=/home/miftah/seer/engine/.venv/bin/python
OUT=${CLAUDE_SCRATCHPAD:-/tmp/seer-m0260}

docker start seer-pg >/dev/null 2>&1 || true
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
PYTHONPATH="$WT/engine/src" "$PY" -m pytest "$WT/engine/tests" -n0 -q \
  > "$OUT/phase1-pytest.out" 2>&1
echo "exit=$?"
tail -5 "$OUT/phase1-pytest.out"

PYTHONPATH="$WT/engine/src" "$PY" -m ruff check "$WT/engine" > "$OUT/phase1-ruff.out" 2>&1
echo "exit=$?"
```

Then commit, by pathspec (the worktree shares one index with every other session in this swarm —
never `git add -A`, never `reset --hard`):

```bash
git -C /home/miftah/.worktrees/seer/gate-reading-cadence add \
  docs/backtests/2026-10-19-gate-reading-cadence.py \
  docs/backtests/2026-10-19-gate-reading-cadence.md

git -C /home/miftah/.worktrees/seer/gate-reading-cadence commit -m "$(cat <<'MSG'
docs: measure the gate's reading cadence on SPY alone, and prove the month-end anchor

M0258 found that reading the SPY 200-day gate monthly rather than weekly was worth more than
the price band it was bought to test. M0260 will sweep that axis on a book that holds stocks,
and a pre-registration may not quote a number nobody measured, so this is the prior: the gate
read at anchored intervals of one, two, three, six and twelve months on SPY alone, against the
two native readings the lab already has.

The same file proves the thing the method's arm table rests on. It walks every decision session
of the dev window, for a monthly and a weekly rule set, resolves the month-end anchor at every
rung and checks that it always lands on a bar the book holds, never lands after the date the
book is deciding at, always has at least two hundred days of SPY behind it, is the identity on
a monthly book at the fastest rung, and reads exactly the bar the monthly book is reading when
a weekly book uses it. The last two are why one arm costs no trial and why the decomposition is
exact.

The grid is unfunded and SPY alone, and says so on every line it prints. It records nothing in
the lab.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

**Impact:** two new files on `feature/gate-reading-cadence`. Nothing leaves the branch.

---

## Verification

**Build:** nothing to build. `PYTHONPATH=<worktree>/engine/src <PY> -m ruff check <worktree>/engine`
must be clean (it does not lint `docs/`, so this is a no-change confirmation).

**Syntax of the new file:**
`<PY> -m py_compile /home/miftah/.worktrees/seer/gate-reading-cadence/docs/backtests/2026-10-19-gate-reading-cadence.py`

**Tests:** `PG_TEST_URL=... PYTHONPATH=<worktree>/engine/src <PY> -m pytest <worktree>/engine/tests -n0 -q`
— green, and with the DB tests **not skipped** (CI fails if they skip).

**Manual check:** read `$OUT/phase1.out` end to end. The `CHECKS` block at the foot is the thing to
read first.

**Exit criteria**, from the plan index, restated as assertions against the captured output:

| # | Assertion | Where to read it |
|---|---|---|
| E1 | `docs/backtests/2026-10-19-gate-reading-cadence.py` and `.md` both exist and are committed on `feature/gate-reading-cadence` | `git -C <wt> show --stat HEAD` |
| E2 | the script exits 0 | the `exit=` line of Step 2 |
| E3 | Table 3b's "this grid" worst fall for `M0084-MONTHLY` is near 18.89% and for `M0084-WEEKLY` near 33.13% — **same sign, same order of magnitude, monthly shallower than weekly**, exactly the standard M0258's grid was held to. Measured while this plan was written: **19.0% and 34.6%** | Table 3b |
| E4 | `fallbacks = 0` on every one of the ten rows of Table 4 | Table 4 |
| E5 | `late = 0` on every row of Table 4 (plan invariant 9) | Table 4 |
| E6 | `min bars >= 200` on every row of Table 4 | Table 4 |
| E7 | Table 5 reports `disagreements : 0` | Table 5 |
| E8 | Table 6 reports `disagreements : 0` and `agreements = sessions checked` | Table 6 |
| E9 | the `CHECKS` block reports `6 of 6 structural checks passed` | foot of the output |
| E10 | the committed `.md` carries the invocation, the date, every table verbatim, and the five-part reading | the file |
| E11 | `pytest -n0 engine/tests` green with `PYTHONPATH=<worktree>/engine/src`, DB tests not skipped | Step 4 |
| E12 | the word **unfunded** appears beside every return quoted in the `.md`'s prose, and `trial_funding.mwr` is named as the thing these figures are not (plan invariant 4) | the file |
| E13 | the `.md`'s reading says in one sentence that `k = 2` is **measured here as a prior only** and is deferred to an `Amendment`, because `MAX_VARIANTS = 6` caps M0260 at six arms; and the reading speaks of **six** arms, never seven | the file |
| E14 | Table 4's `min bars` column is carried into the `.md`'s reading as the measurement that makes phase 2's widened lookback safe, with the ceiling stated as **`lookback <= 739`** rather than as "do not widen" | the file |

**If E4–E9 do not all hold**, the phase is still complete — but the committed `.md` must say so in
its own words, the exact dates the script printed must be in it, and the plan's Appendix A or
Appendix B is wrong. Raise it to the reconciler and to phase 2 before the method file is written.
That is the entire reason this phase runs first.

---

## Handoffs

- **Six arms, not seven** — Phase 2 (R1). `lab.method.MAX_VARIANTS = 6` caps a `Method` at six
  candidates, so M0260 declares `M-NATIVE`, `M-G3`, `M-G6`, `M-G12`, `W-NATIVE`, `W-G1`. The
  `k = 2` rung measured in this phase's grid is a **prior only**, deferred to an `Amendment`.
- **The lookback is 454, not 253** — Phase 2 (R1). This phase's probe reports a minimum of 738 SPY
  bars behind every resolved anchor, which is the measurement that makes a widened lookback safe:
  the binding rule is **`lookback <= 739`** (SPY's 739th bar on the dev store is 1996-01-02 and its
  740th is 1996-01-03, so any lookback up to 739 leaves `dev.candidate_window` binding on
  `MEMBERSHIP_START` and the first scored session at 1996-01-03), with the 473-session smoke
  fixture as the operative ceiling. Nothing in this phase's output argues for 253.
- **The production anchor, and the test module that pins it** — Phase 2 (R1, R3, R6). This phase
  deliberately writes a *second* implementation and imports none of phase 2's. Phase 2 must write
  its own inside `m0260_gate_reading_cadence.py` and assert the same five claims in
  `engine/tests/test_lab_m0260_cadence.py` against `labkit.smoke_market`. Agreement between the two
  is evidence precisely because neither is the other.
- **The `PRESETS` promotability check** — Phase 2 (R4). This phase reads `sim/rules.py` only to
  establish that `monthly-hold-frac-gotrade` carries `resize_cadence=None` (which is why a rank
  session is the only decision session, and hence why the probe walks rank sessions alone). The
  promotability table itself belongs in the method file's docstring.
- **Everything about money** — Phase 3 (R5). Every figure this phase produces is unfunded and SPY
  alone. The funded, fee-paying, deposit-matched numbers come from `lab run` and are quoted as
  `trial_funding.mwr`. Nothing on this phase's page may be re-used as a return on the owner's money.
- **The walk-forward folds read arm by arm** — Phase 3 (R2). Not touched here.
- **The handover's "environment notes" entry for this script** — Phase 4. Worth one line there,
  because this script takes an absolute `--store` and so, unlike M0258's, does **not** have to be
  run from the main checkout. That is a deliberate correction of the precedent and the next session
  should be told.
- **A possible upstream cleanup, not done here:** `docs/backtests/2026-10-19-gate-band-cadence.py`
  hard-codes a relative `engine/.research` path and its `IS_MONTH_END` marks the tape's final bar a
  month end unconditionally. Neither is wrong for what that file concluded, and it is a committed
  record of a finished study. **Do not edit it.** If anyone ever wants it parameterised, that is a
  new file, not a change to that one.

## Rollback

`git -C /home/miftah/.worktrees/seer/gate-reading-cadence revert <this phase's commit>`, or simply
delete the two files — nothing imports them, nothing in CI runs them, and no later phase breaks
without them except that phase 2's docstring loses the numbers it quotes. This phase touches no
source, no test, no database and no lab row, so there is nothing else to undo.
