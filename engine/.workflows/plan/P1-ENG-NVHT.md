> Adopted from `/home/miftah/seer/.workflows/orchestration/lab-shortfall-and-control-shape/PLAN.md` phase 1. Source: `.workflows/plan/lab-shortfall-and-control-shape/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: The shortfall decomposition, and `lab shortfall`

**Plan set:** `LAB_SHORTFALL_AND_CONTROL_SHAPE_PLAN.md`
**Analysis:** `docs/analyzer/20261019-110502-S4KQ_code_analyzer.md`
**Satisfies:** **R1** — the lab can say where a trial's gap to SPY went, instead of naming the
whole gap after whichever ingredient the author had in mind. This phase **builds** the
decomposition and runs it on trial 828 as its own manual check; **phase 4 owns R1's written
acceptance** — `docs/backtests/2026-10-19-trial-828-shortfall.md`, which quotes this phase's
output beside the `lab control` table. Hand phase 4 the exact numbers this phase measures.
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab`

---

## Goal

After this phase `lab shortfall <TRIAL>` exists. Given any recorded dev trial and an era it prints
that era's gap to SPY TR and splits it into a gate premium, a modelled fee drag and one explicitly
labelled residual that sums the three back to the gap exactly. Run on trial 828 with the dev store
it reproduces gap −8.24, gate −3.60, fees −3.78, residual −0.87 pts/yr — which bounds the
"equal-weight handicap" under one point a year and retires the published 8.2.

**These four numbers are the reconciled ones for the whole plan set.** The analysis document and
the plan index's first draft carried −3.76 / −0.88, computed from the rate at one month offset
(month 236, `0.2498%`); this phase measured the mean over the era's own offsets (156..237,
`0.251041%`), which is what the implementation computes. The analysis document now says so, and
phase 4's backtest note quotes −3.78 / −0.87. Nothing the plan rests on moves: the gate and the
fees still account for ~7.4 of the 8.2.

Nothing is written: no trial, no moment, no funding, no provenance, no insight, no status, no
journal. The test window is never read.

---

## Measurements this plan rests on

Every number below was **measured during planning** against the worktree's committed
`lab/lab.sqlite` and `/home/miftah/seer/engine/.research`, not taken from the analysis document.
They are the implementer's acceptance targets.

**The gap, through `walkforward.measure` + `hardgate.trial_deposits` against `REF-SPY-HOLD`
(trial #1), 2009-01-01..2015-10-16:**

```
REF-SPY-HOLD slice   months 82   cagr 16.6031%
M0244-PLACEBO30 (n=828)  me  8.3598%   gap  -8.24 pts/yr   236 deposits
M0244-FRESH30   (n=823)  me  8.7730%   gap  -7.83
M0244-STALE30   (n=827)  me 12.3011%   gap  -4.30
M0248-R         (n=810)  me 17.6959%   gap  +1.09
M0248-D100      (n=809)  me 39.8608%   gap +23.26
```

**The shared gate's on-share, via `f_factor.trend_on` on the dev store's own `SPY` bars** (not a
re-implementation — `trend_on` is the lab's definition of the gate and was called directly):

```
whole 1996-01-03..2015-10-16   4983 sessions   0.711620
1996-2002                      1763            0.640386
2003-2008                      1511            0.688286
2008                            253            0.003953
2009-2015                      1710            0.805848
```

**The fee model**, `(buy.total + sell.total) / (2 x slot)` at `turnover.round_trip` on the owner's
funding, 30 names:

```
month   0  0.722559%     month 120  0.254892%
month  24  0.298494%     month 156  0.252710%
month 236  0.249849%     month 237  0.249923%
mean over months 156..237 (the 2009-2015 era): 0.251041%
mean over months   0..237 (the whole window):  0.266656%
```

**The headline, assembled:**

```
                                      era-resolved exposure    whole-window exposure
gap to SPY TR                              -8.24                   -8.24
  gate premium                             -3.60   (1-0.7836)      -5.11   (1-0.6919)
  fee drag   15.05 x 0.2510%               -3.78                   -3.78
  pool + weighting residual                -0.87                   +0.65
```

That 1.5-point swing is why era resolution is load-bearing and not polish.

**The same model across M0244's four arms** — the cross-check that it is not nonsense:

```
                     gap     gate     fee   residual
M0244-PLACEBO30    -8.24   -3.59   -3.78     -0.87
M0244-FRESH30      -7.83   -3.60   -3.84     -0.39
M0244-STALE30      -4.30   -3.70   -0.90     +0.29
M0244-HARD30       -6.69   -3.59   -2.93     -0.18
```

The 3.94-point PLACEBO30/STALE30 gap difference is 2.88 of modelled fees plus small terms, and
every residual lands inside ±0.9 pts/yr.

**Whole-window, trial 828:** gap −0.58, gate −2.44, fee −4.01, residual **+5.87**. The book's pool
and selection really did earn ~6 pts/yr whole-window and gave it back to the gate and the fees.

**The name count is not load-bearing.** The fee drag for turnover 15.05 over 2009-2015 at 10 / 20 /
30 / 50 names is 3.71 / 3.74 / 3.78 / 3.85 pts/yr, and over 1996-2002 is 3.95 / 4.17 / 4.39 / 4.79.
So the report prints a sensitivity band and the guess is visibly bounded rather than hidden.

**And trial 828 resolves its own count — the headline run does NOT fall back to `DEFAULT_NAMES`.**
Checked by the reconciler against the committed `lab/lab.sqlite`, trial 828's recorded
`config_text` reads:

```
params=GestureParams(window_days=380,top=30,cap=0.2,kinds=('split','init','raise','buyback'),
                     arm='placebo',seed=244,
                     screen=FactorParams(rank='momentum',top=1000,...,trend=('SPY',200)))
```

`names_in` takes the **shallowest** bracket depth that carries a `top=`, so `top=30` (depth 1)
wins over the screen's `top=1000` (depth 2) and the answer is **30**. `DEFAULT_NAMES`
(`turnover.ROSTER_NAMES`, 20) is a labelled fallback for a configuration this report cannot read,
and trial 828 is not one — `0.2510%` and `-3.78` above are the 30-name numbers, consistent with
the 30-name rate table two blocks up. **Phase 4 therefore runs the backtest-note command with no
`--names` flag**, and the report's own `names_from` line is what proves which number was used.
(Had it silently used 20 the drag would read `-3.74`, a 0.04 pt difference — bounded either way,
which is why the sensitivity band is printed.)

**D10 for trial 828:** `hardgate.mismatches(conn, 1, [828, 823, 827, 810, 809])` returns `()`. The
expected trial-828 run prints **no** WARNING line. `benchmark_n(conn)` is 1. The committed lab
holds 824 dev trials and 4 test-window looks.

---

## Interface Contract

The reconciler reads this section. Phases 2–4 may assume every name below and nothing else.

**Creates — new module `engine/src/seer_engine/lab/shortfall.py`:**

Constants
- `shortfall.DEFAULT_ERA` = `"2009-2015"` (str)
- `shortfall.DEFAULT_NAMES` = `turnover.ROSTER_NAMES` (int, 20)
- `shortfall.SENSITIVITY_NAMES` = `(10, 20, 30, 50)`
- `shortfall.MAX_GATE_FILL` = `1.0`
- `shortfall.ERA_BASIS` = `"era-resolved"`, `shortfall.WHOLE_BASIS` = `"whole-window"`
- `shortfall.CASH_NOTE: Mapping[str, str]` — one plain sentence per era label
- `shortfall.RATE_Q` = `Decimal("0.00000001")`

Dataclasses (all `frozen=True, slots=True`)
- `shortfall.GateShare(symbol, n, whole, era, whole_sessions, era_sessions, store_dir)`
- `shortfall.Exposure(value, recorded, basis, why, fill)`
- `shortfall.Fees(names, names_from, first_month, last_month, rate, drag, sensitivity)`
- `shortfall.Split(candidate_id, trial_n, shared, own)`
- `shortfall.Shortfall(trial_n, candidate_id, method_id, window, era_label, era, months, deposits,
  mine, theirs, gap, exposure, gate, gate_premium, fees, residual, against, warnings)`

Functions
- `shortfall.pts(v, digits=2) -> str`
- `shortfall.curve_of(row) -> list[tuple[date, float]]`
- `shortfall.trial_window(row) -> tuple[date, date]`
- `shortfall.resolve_trial(conn, token) -> sqlite3.Row`
- `shortfall.era_bounds(label, window) -> tuple[str, date, date]`
- `shortfall.carries_shared_gate(config_text) -> bool`
- `shortfall.names_in(config_text) -> int | None`
- `shortfall.month_offset(window_start, when) -> int`
- `shortfall.round_trip_rate(month, names) -> Decimal`
- `shortfall.mean_round_trip_rate(first_month, last_month, names) -> Decimal`
- `shortfall.gate_history(store_dir, symbol=GATE_SYMBOL) -> History`
- `shortfall.gate_shares(history, window, era, store_dir="") -> GateShare`
- `shortfall.gate_on_share(store_dir, window, era) -> GateShare`
- `shortfall.era_exposure(recorded, gate, carries_gate, store_given) -> Exposure`
- `shortfall.fee_model(turnover_per_year, window_start, era, names, names_from) -> Fees`
- `shortfall.benchmark(conn) -> tuple[list[tuple[date, float]], int]`
- `shortfall.check_against(conn, row, other) -> None`
- `shortfall.measure(conn, row, era_label, *, gate=None, names=None, against=None,
  store_given=False) -> Shortfall`
- `shortfall.format_report(sf) -> str`
- `shortfall.csv_rows(sf) -> list[list[str]]`
- `shortfall.write_csv(sf, path) -> Path`

**Creates — `engine/src/seer_engine/commands/lab.py`:**
- one `sub.add_parser("shortfall", ...)` block, inserted **between** the existing `walkforward`
  parser block (ends at `:441`) and the `survivorship` parser block (begins `:442`)
- `_shortfall(conn, args) -> int`, inserted immediately after `_walkforward` ends and before
  `#: The era in which the store can price the most of the index` / the next handler
- one `"shortfall": _shortfall,` entry in `_HANDLERS` (`:2867`), between `"walkforward"` and
  `"luck"`
- one `lab shortfall ...` entry in the module docstring, after the `lab turnover` entry

**Creates — `engine/tests/test_lab_shortfall.py`** (new file).

**Deletes:** nothing.
**Renames:** nothing.
**Signature changes:** none. No existing function changes shape.

**Requires (from earlier phases):** none. This is the first phase.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/control_shape.py` (Phase 2, not yet created)
- `engine/src/seer_engine/lab/store.py` (Phase 3 — `append_analysis`)
- `commands/lab.py::_note` (Phase 3) — this phase does not touch it
- `commands/lab.py::_run`, the `control` parser (Phase 4)
- `engine/src/seer_engine/lab/hardgate.py` (Phase 4 — D17). This phase **imports** `hardgate`
  (`trial_deposits`, `benchmark_n`, `mismatches`, `describe`) and edits nothing in it.
- every `lab/methods/mNNNN_*.py`, every recorded `lab.sqlite` row, `backtest/registry.py`, `web/`

**Note for Phases 3 and 4, which also edit `commands/lab.py`:** this phase's edit is exactly four
insertions — a docstring line, a parser block between `walkforward` and `survivorship`, a handler
function after `_walkforward`, and one `_HANDLERS` key. Quote the file with those present.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/shortfall.py` | **create** | the whole decomposition: era gap, gate premium, fee drag, residual, the `--against` split, the report |
| `engine/src/seer_engine/commands/lab.py` | modify | docstring entry after the `lab turnover` block (`:71`); `shortfall` parser between `:441` and `:442`; `_shortfall` handler after `_walkforward`; `_HANDLERS` key at `:2870` |
| `engine/tests/test_lab_shortfall.py` | **create** | the arithmetic rules on synthetic rows, plus one pinned test on the committed lab |

---

## Implementation Steps

### Step 1: Create `engine/src/seer_engine/lab/shortfall.py`

**File:** `engine/src/seer_engine/lab/shortfall.py` (new, no line reference)
**Change:** the whole module. Write it exactly as below.

**Code:**

```python
"""``lab shortfall``: where one trial's gap to SPY went, with the residual left a residual.

**The failure this exists to stop.** The lab measures a trial's shortfall to SPY total return over
an era and prints one number. Whoever writes the analysis then names that number after whichever
ingredient they happened to be thinking about. For trial 828 (``M0244-PLACEBO30``) the name was
"equal-weight handicap", and it was promoted from one matched pair's shortfall to a universal
constant -- insight 461, a memory note, and the ``/sera`` synthesis page all carry it. The arm that
produced the number is a gated, fifteen-turns-a-year book drawn from the fifty strongest momentum
names. Three ingredients the name does not mention are inside the 8.2 points, and two of them can
be priced from rows the lab already has.

**What this module does.** It splits the era gap into two separately-computed named terms and one
residual::

    gap  =  -(gate premium)  -(fee drag)  +(pool + weighting residual)

and the residual is the term the other two do not explain. It is never named after a cause. That
is the whole discipline: a residual small enough to ignore says the named terms account for the
gap; it does not say the residual's own ingredients are zero, and this module's output says so in
words rather than leaving a reader to infer it.

**An attribution under stated assumptions, not an identity.** The three terms do not come from one
decomposition of one quantity. The gap is measured; the gate premium and the fee drag are each
modelled from a different source; the residual absorbs the error of both. The report says this on
screen every time, because an attribution that forgets it is how the 8.2 became a constant.

**Rule 1: the gap is not recomputed.** It comes from :func:`walkforward.measure` over the recorded
``curve_json``, de-funded by :func:`hardgate.trial_deposits`, against the recorded
``REF-SPY-HOLD`` curve sliced the same way -- the identical path ``lab exposure``, ``lab gate``,
``lab survivorship`` and ``lab walkforward`` already take. ``trial_deposits``'s own docstring says
why: *a second reconstruction is a second chance to read a deposit as edge.* A trial whose curves
were measured on prices other than the benchmark's gets a WARNING line and its numbers anyway --
a report warns where the promotion gate refuses (hardgate D10) -- except under ``--against``,
where a split across two price fingerprints would be cross-store arithmetic and is refused.

**Rule 2: era exposure is era-resolved when it can be, and labelled when it cannot.**
``trials.exposure`` is a whole-window scalar and there is no per-era exposure anywhere in the
schema. Measured on the dev store, the shared SPY 200-day gate was on 71.2% of the whole window's
sessions and 80.6% of 2009-2015's. Trial 828 records exposure 0.692, so the book was about 97%
invested whenever the gate let it in, and its 2009-2015 exposure is ``0.692 x (0.806 / 0.712) =
0.784``. Pricing the gate at the recorded 0.692 instead gives 5.11 pts/yr where the era-resolved
figure gives 3.60 -- a 1.5 point error on an 8.2 point headline, and the residual flips sign with
it. The ratio carries the gate's era shape; the recorded exposure carries the book's own slot-fill
drag. When no store is given, when the book carries no shared gate, or when the recorded exposure
is *above* the gate's own on-share (so the book held money while the gate was off and the gate
does not govern all of it), the whole-window figure is used and the output says so, every time.

**Rule 3: the fee drag is modelled, not recovered.** The fees a run really paid live in
``RunStats.costs_usd``, which is not a ``trials`` column and cannot be recovered from one.
``trials.turnover`` is defined in ``book_runner._turnover`` as the sum of fill notionals -- buys
**and** sells -- over mean session equity over years, so it is a per-dollar-of-notional quantity
and composes directly with a per-dollar fee rate. That rate is one round trip of one slot through
:func:`turnover.round_trip`, divided by the two dollars of notional a round trip moves, averaged
over the era's own month offsets into the dev window so the ``$0.10`` floor's shrinking bite is
carried rather than averaged away. The book's name count is not in the row; it is read from the
recorded configuration when that is unambiguous and defaulted otherwise, the output always says
which, and a sensitivity band at 10, 20, 30 and 50 names is printed beside it -- measured, the
2009-2015 drag moves from 3.71 to 3.85 pts/yr across that whole range, so the guess is bounded and
visibly not what the answer rests on.

**Rule 4: the pool cannot be separated from one row, and this refuses to pretend.** Nothing in a
trials row names the pool the book was drawn from, so by default the two ingredients nobody can
price are reported as **one** ``pool + weighting`` residual. ``--against`` splits it by subtraction
against a sibling arm of the same method that shares the pool, the gate and the frame: that arm's
own residual is what the two have in common and goes to pool and frame, and only the remainder is
this arm's own weighting and selection. An ``--against`` from another method, or across a price
fingerprint the benchmark does not share, is refused rather than printed.

**Cash earns nothing -- after 2008.** The gate premium assumes money out of the market earned zero.
Memory (``seer-idle-cash-credit-worth-08-before-2008-only``) measured that this is right for
2009-2015 and wrong before 2008, when T-bills paid a real rate. So the caveat is carried **per
era** in :data:`CASH_NOTE` rather than one model being applied silently to all of them.

**A report, not a trial.** Nothing is written: no ``trials``, ``trial_moments``, ``trial_funding``,
``trial_provenance``, ``insights`` or ``method_folds`` row, no status, no journal. The test window
is never named and ``window = 'test'`` is refused at the door. The command prints
``store.dev_trial_count`` and ``store.test_looks`` before and after, the way ``lab turnover`` and
``lab regime`` do, so the invariant is visible on the terminal rather than merely asserted in a
test.

Pure but for one optional read: with ``--store`` it streams the gate symbol's rows out of the
store's own ``bars.csv`` and asks :func:`f_factor.trend_on` -- the lab's own definition of the
gate -- whether it was on, session by session. It opens no database but the lab's, runs no
backtest, and loads no market.
"""

from __future__ import annotations

import csv
import json
import logging
import re
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import numpy as np

from seer_engine import research
from seer_engine.backtest import regime
from seer_engine.backtest.metrics import DASH, to_fixed
from seer_engine.lab import hardgate, store, turnover
from seer_engine.lab import walkforward as wf
from seer_engine.lab.exposure import ERA_LABELS, ERAS, WHOLE
from seer_engine.lab.gate_probe import GATE_N, GATE_RULE, GATE_SYMBOL
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams, trend_on

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- the knobs

#: The era this answers when the caller names none. It is the era the lab quotes its modern-era
#: verdicts over, and the era the published 8.2 was measured on.
DEFAULT_ERA = "2009-2015"

#: The book size the fee model assumes when the recorded configuration does not name one
#: unambiguously. The roster's own count, imported rather than restated.
DEFAULT_NAMES = turnover.ROSTER_NAMES

#: The band the report prints beside the fee drag, so a wrong book size is visibly bounded.
#: Measured 2026-10-19 at turnover 15.05 over 2009-2015: 3.71, 3.74, 3.78, 3.85 pts/yr.
SENSITIVITY_NAMES: tuple[int, ...] = (10, 20, 30, 50)

#: ``recorded exposure / the gate's own whole-window on-share``. Above 1 the book held money while
#: the gate was off -- a blend with an ungated leg, say -- so the gate does not govern the whole
#: book and scaling its exposure by the gate's era shape would be a different book's arithmetic.
MAX_GATE_FILL = 1.0

ERA_BASIS = "era-resolved"
WHOLE_BASIS = "whole-window"

#: Eight decimals, the precision ``lab turnover`` reports its own rates at.
RATE_Q = Decimal("0.00000001")

#: What the gate premium's "money out of the market earned nothing" assumption is worth, per era.
#: From the measurement in ``seer-idle-cash-credit-worth-08-before-2008-only``: T-bills paid a real
#: rate before 2008 and about nothing after it, so the assumption is right for one era and
#: generous to the book in the others. Keyed by the labels in ``exposure.ERA_LABELS``.
CASH_NOTE: Mapping[str, str] = {
    WHOLE: (
        "this era spans both: before 2008 the money the gate held back earned a real rate in "
        "T-bills, and after 2008 it earned about nothing. So the gate premium here is somewhat "
        "larger than the truth"
    ),
    "1996-2002": (
        "money out of the market really did earn something in these years -- T-bills paid a real "
        "rate -- so the gate premium below is LARGER than the truth and the residual beside it "
        "is correspondingly more negative"
    ),
    "2003-2008": (
        "T-bills still paid a real rate for most of these years, so the gate premium below is "
        "somewhat larger than the truth"
    ),
    "2008": (
        "T-bills still paid something through most of 2008, so the gate premium below is "
        "somewhat larger than the truth"
    ),
    "2009-2015": (
        "the assumption holds here: T-bills paid about nothing after 2008, so money out of the "
        "market really did earn nothing and the gate premium below is the right size"
    ),
}

#: The shared gate as a recorded configuration renders it. ``method.config_text`` writes a params
#: tree through ``registry._canon``, so the gate appears either as a ``trend`` pair on a
#: ``FactorParams`` or as the ``TimingParams`` that *is* the gate. Both patterns are built from
#: ``gate_probe``'s own constants so they cannot drift from the thing they detect. Whitespace is
#: tolerated because the renderer's spacing is not part of this module's contract with it.
_TREND_SITE = re.compile(
    r"\btrend=\(\s*'" + re.escape(GATE_SYMBOL) + r"'\s*,\s*" + str(GATE_N) + r"\s*\)"
)
_TIMING_SITE = re.compile(
    r"signal='" + re.escape(GATE_SYMBOL) + r"'\s*,\s*rule='" + re.escape(GATE_RULE)
    + r"'\s*,\s*n=" + str(GATE_N) + r"\b"
)

#: ``top=<n>`` in a rendered params tree. The book size is read from the SHALLOWEST bracket depth
#: that carries one, because a screen's own ``top`` (``FactorParams(top=1000)``) is always nested
#: inside the allocator's.
_TOP = re.compile(r"\btop=(\d+)\b")


# --------------------------------------------------------------------------- small helpers


def pts(v: float | None, digits: int = 2) -> str:
    """A points-a-year figure with an ASCII sign: ``-8.24``, ``+0.65``; the dash for None.

    ``metrics.fmt_signed_pct`` renders the web's U+2212 minus, which is right on a page and wrong
    in a line the owner may paste into a note or a commit message. Two decimals because the whole
    argument of this report is about tenths of a point.
    """
    if v is None:
        return DASH
    return ("+" if v >= 0 else "-") + to_fixed(abs(v * 100.0), digits)


def curve_of(row: sqlite3.Row) -> list[tuple[date, float]]:
    """One recorded trial's monthly equity curve, as ``walkforward.measure`` wants it."""
    return [(date.fromisoformat(d), float(v)) for d, v in json.loads(row["curve_json"])]


def trial_window(row: sqlite3.Row) -> tuple[date, date]:
    """The dates the trial ran between, from its own recorded columns."""
    return date.fromisoformat(row["start"]), date.fromisoformat(row["end"])


def month_offset(window_start: date, when: date) -> int:
    """Whole months from the window's first month to ``when``'s, never negative.

    The fee model walks the owner's funding plan by month offset, and the dev window's first month
    is month 0 of that plan: ``turnover.equity_usd(0)`` is the opening 10,000,000 IDR.
    """
    months = (when.year - window_start.year) * 12 + (when.month - window_start.month)
    return max(0, months)


# --------------------------------------------------------------------------- reading the lab


def resolve_trial(conn: sqlite3.Connection, token: object) -> sqlite3.Row:
    """The dev trial ``token`` names: a ``trials.n``, or a candidate id. Raises ``LabError``.

    A ``window = 'test'`` row is refused by name rather than quietly reported on. This command
    reads recorded rows, so reading one would spend no new look -- but the lab's rule is that
    nothing in a report path may so much as name the test window, and a refusal here is cheaper
    than a reader who learns that it can.
    """
    text = str(token).strip()
    if not text:
        raise store.LabError("name a trial: its number (`lab shortfall 828`) or its candidate id")
    if text.isdigit():
        row = conn.execute("SELECT * FROM trials WHERE n = ?", (int(text),)).fetchone()
        if row is None:
            raise store.LabError(f"no trial #{text} in this lab")
    else:
        cid = text.upper()
        rows = conn.execute(
            "SELECT * FROM trials WHERE candidate_id = ? ORDER BY n", (cid,)
        ).fetchall()
        if not rows:
            raise store.LabError(
                f"no trial for candidate {cid}; `lab show <method>` lists a method's variants"
            )
        dev = [r for r in rows if r["window"] == "dev"]
        if not dev:
            raise store.LabError(
                f"{cid} has only a test-window trial; `lab shortfall` reads the dev window "
                f"and nothing else"
            )
        row = dev[0]
    if row["window"] != "dev":
        raise store.LabError(
            f"trial #{row['n']} ({row['candidate_id']}) is a {row['window']}-window trial. "
            f"`lab shortfall` reads the dev window and nothing else: the one counted look is "
            f"never spent on a report, and never re-read by one"
        )
    if not row["curve_json"] or not json.loads(row["curve_json"]):
        raise store.LabError(
            f"trial #{row['n']} ({row['candidate_id']}) records no equity curve, so no era can "
            f"be sliced out of it"
        )
    return row


def benchmark(conn: sqlite3.Connection) -> tuple[list[tuple[date, float]], int]:
    """The recorded ``REF-SPY-HOLD`` dev curve and its ``trials.n``. Raises ``LabError``.

    The same row by the same rule as ``hardgate.benchmark_n`` -- the first ``REF-SPY-HOLD`` dev
    trial carrying a curve -- so this report and the promotion gate can never be talking about
    two different benchmarks. A test asserts the two agree.
    """
    row = conn.execute(
        'SELECT n, start, "end", curve_json FROM trials '
        "WHERE window = 'dev' AND candidate_id = ? AND curve_json IS NOT NULL ORDER BY n LIMIT 1",
        (regime.BENCH_CANDIDATE,),
    ).fetchone()
    if row is None:
        raise store.LabError(
            f"no {regime.BENCH_CANDIDATE} dev trial, so there is no gap to decompose. This is "
            f"the lab's fixture missing, not your trial failing"
        )
    curve = curve_of(row)
    if len(curve) < 2:
        raise store.LabError(
            f"the recorded {regime.BENCH_CANDIDATE} dev curve has {len(curve)} point(s); no era "
            f"can be sliced from it"
        )
    return curve, int(row["n"])


def era_bounds(label: object, window: tuple[date, date]) -> tuple[str, date, date]:
    """``(canonical label, start, end)`` for ``label``, clipped to the trial's own window.

    The era table is ``exposure.ERAS`` and is imported, never restated: ``lab exposure``,
    ``lab gate`` and ``lab survivorship`` all cut the same four eras, and a fifth definition here
    would make two reports of the same trial disagree about what "2009-2015" means. ``whole`` (or
    ``whole window``) is the trial's own window.
    """
    text = str(label).strip().lower()
    if text in ("whole", WHOLE):
        return WHOLE, window[0], window[1]
    for name, start, end in ERAS:
        if text == name.lower():
            lo, hi = max(start, window[0]), min(end, window[1])
            if lo >= hi:
                raise store.LabError(
                    f"era {name} ({start}..{end}) does not overlap this trial's window "
                    f"({window[0]}..{window[1]})"
                )
            return name, lo, hi
    known = ", ".join(ERA_LABELS)
    raise store.LabError(
        f"unknown era {label!r}; this lab knows {known} (say 'whole' for the whole window). The "
        f"era table is lab/exposure.py's ERAS and is not redefined here"
    )


def carries_shared_gate(config_text: object) -> bool:
    """Does this recorded configuration carry the shared SPY 200-day gate, anywhere in it?

    Generic, from the recorded text rather than from the candidate's name: a recorded row holds no
    params object, so ``gate_probe.gate_off``'s walk cannot be run on it, but ``config_text`` is
    exactly ``registry._canon``'s rendering of the same ``compare=True`` fields that walk visits.
    Both of the gate's two forms are matched -- a ``trend`` pair and the ``TimingParams`` that is
    the gate -- using ``gate_probe``'s own constants.

    True means *the gate is present somewhere in this book*, which is not the same as *the gate
    governs all of this book*: a blend with one gated leg answers True. :func:`era_exposure` makes
    that distinction separately, from the recorded exposure against the gate's own on-share.
    """
    text = str(config_text or "")
    return bool(_TREND_SITE.search(text) or _TIMING_SITE.search(text))


def names_in(config_text: object) -> int | None:
    """The book's name count read from a recorded configuration, or None when it is ambiguous.

    The shallowest bracket depth that carries a ``top=`` wins, because an allocator's own book
    size sits outside the screen it wraps: ``GestureParams(top=30, screen=FactorParams(top=1000))``
    reads 30. None when the params name no ``top`` at all, or when two different ones sit at that
    same shallowest depth.

    **Measured across the committed lab (824 dev rows, 2026-10-19): 686 resolve and 138 do not,
    and at least two that resolve are wrong** -- ``M0241-STALE`` reads 1000 and ``M0226-CORE``
    reads 1000, because those allocators carry no book size of their own. So this is a suggestion
    the report labels as a guess and never a fact: the caller can override it, the output always
    says where the number came from, and the fee drag is printed with a sensitivity band across
    :data:`SENSITIVITY_NAMES` so a wrong guess is visibly bounded. Measured, the 2009-2015 drag
    moves by 0.14 pts/yr across 10 to 50 names, so it is bounded very tightly indeed.
    """
    text = str(config_text or "")
    line = next((ln for ln in text.splitlines() if ln.startswith("params=")), None)
    if line is None:
        return None
    found: dict[int, set[int]] = {}
    depth, i = 0, 0
    while i < len(line):
        ch = line[i]
        if ch in "([":
            depth += 1
            i += 1
            continue
        if ch in ")]":
            depth -= 1
            i += 1
            continue
        m = _TOP.match(line, i)
        if m is not None:
            found.setdefault(depth, set()).add(int(m.group(1)))
            i = m.end()
            continue
        i += 1
    if not found:
        return None
    shallowest = found[min(found)]
    return next(iter(shallowest)) if len(shallowest) == 1 else None


# --------------------------------------------------------------------------- the gate's shape


@dataclass(frozen=True, slots=True)
class GateShare:
    """How often the shared gate was on, over the whole window and over one era."""

    symbol: str
    n: int
    whole: float
    era: float
    whole_sessions: int
    era_sessions: int
    store_dir: str


def gate_history(store_dir: Path, symbol: str = GATE_SYMBOL) -> History:
    """``symbol``'s bars, streamed out of a research store's own ``bars.csv``.

    ``research.load_store`` would answer the same question and costs roughly a gigabyte of memory
    and half a minute, because it builds the whole market. This report needs one symbol's closes,
    so it reads the one file and keeps the one symbol. The store is still checked -- see
    :func:`gate_on_share` -- through ``research.declared_window`` and ``research.declared_purpose``,
    which read the manifest and nothing else.
    """
    path = Path(store_dir) / research.BARS_FILE
    if not path.is_file():
        raise store.LabError(
            f"{store_dir}: no {research.BARS_FILE}. The research stores are gitignored, so a "
            f"worktree has none -- point --store at a checkout that does rather than rebuilding "
            f"one"
        )
    days: list[np.datetime64] = []
    cols: tuple[list[float], ...] = ([], [], [], [], [])
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if header is None or ",".join(header) != research.BARS_HEADER:
            raise store.LabError(
                f"{path}: header is {header!r}, expected {research.BARS_HEADER!r}"
            )
        for rec in reader:
            if not rec or rec[0] != symbol:
                continue
            days.append(np.datetime64(rec[1]))
            for k in range(5):
                cols[k].append(float(rec[2 + k]))
    if len(days) < GATE_N:
        raise store.LabError(
            f"{path}: {symbol} has {len(days)} bar(s), fewer than the {GATE_N} the gate needs "
            f"before it can be read at all"
        )
    arrays = [np.array(c, dtype=np.float64) for c in cols]
    return History(symbol, np.array(days, dtype="datetime64[D]"), *arrays)


def gate_shares(
    history: History,
    window: tuple[date, date],
    era: tuple[date, date],
    store_dir: str = "",
) -> GateShare:
    """The share of sessions the shared gate was on, over ``window`` and over ``era``.

    The gate is read by :func:`f_factor.trend_on`, the lab's own definition of it -- strictly
    ``close > SMA(n)``, with the first ``n-1`` bars counting as off -- rather than by a rolling
    mean written out again here. A second definition of the gate is how two reports of the same
    book end up disagreeing about when it was in the market.

    Pure: no I/O. :func:`gate_on_share` is the one that opens a store.
    """
    params = FactorParams(rank="momentum", trend=(history.symbol, GATE_N))
    hist = {history.symbol: history}
    days = [d.astype(object) for d in history.dates]
    on = np.array([trend_on(hist, d, params) for d in days], dtype=bool)

    def share(lo: date, hi: date) -> tuple[float, int]:
        idx = [i for i, d in enumerate(days) if lo <= d <= hi]
        if not idx:
            raise store.LabError(
                f"{history.symbol} has no bar between {lo} and {hi}, so the gate's share of that "
                f"span cannot be measured"
            )
        return float(on[idx].mean()), len(idx)

    whole, whole_n = share(*window)
    era_share, era_n = share(*era)
    return GateShare(
        symbol=history.symbol,
        n=GATE_N,
        whole=whole,
        era=era_share,
        whole_sessions=whole_n,
        era_sessions=era_n,
        store_dir=str(store_dir),
    )


def gate_on_share(
    store_dir: Path, window: tuple[date, date], era: tuple[date, date]
) -> GateShare:
    """:func:`gate_shares` over the gate symbol's bars in the store at ``store_dir``.

    The store is refused unless it declares the dev window and no special purpose. The era shape
    has to be measured on the prices the trial was recorded against (hardgate D10's reasoning),
    and a survivorship-check or test-window store is a different tape.
    """
    path = Path(store_dir)
    try:
        declared = research.declared_window(path)
        purpose = research.declared_purpose(path)
    except (ValueError, FileNotFoundError) as e:
        raise store.LabError(f"{path}: {e}") from e
    if declared.name != research.DEV_WINDOW.name:
        raise store.LabError(
            f"{path} declares the {declared.name!r} window; `lab shortfall` measures the gate's "
            f"era shape on the dev window and nothing else, and never opens the test window"
        )
    if purpose is not None:
        raise store.LabError(
            f"{path} declares purpose {purpose!r}; the gate's era shape must come from the same "
            f"prices the trial was recorded on, not from another tape"
        )
    return gate_shares(gate_history(path), window, era, store_dir=str(path))


# --------------------------------------------------------------------------- the three terms


@dataclass(frozen=True, slots=True)
class Exposure:
    """The exposure the gate premium is priced at, and why it is that one."""

    value: float
    recorded: float
    basis: str  # ERA_BASIS or WHOLE_BASIS
    why: str
    fill: float | None  # recorded / the gate's whole-window on-share, when it was computed


def era_exposure(
    recorded: float,
    gate: GateShare | None,
    carries_gate: bool,
    store_given: bool,
) -> Exposure:
    """The era's exposure, era-resolved when it can be and the recorded figure when it cannot.

    Four ways it cannot be, each with its own sentence in the output: no store was given, the book
    carries no shared gate, the gate was never on over the window, or the book held money while
    the gate was off -- the recorded exposure above the gate's own on-share -- which means the gate
    does not govern all of it and the ratio would be a different book's arithmetic.
    """
    if not store_given:
        return Exposure(
            recorded, recorded, WHOLE_BASIS,
            "no --store was given, so the gate's era shape could not be measured and the "
            "recorded whole-window exposure is used as it stands",
            None,
        )
    if gate is None or not carries_gate:
        return Exposure(
            recorded, recorded, WHOLE_BASIS,
            f"this book carries no shared {GATE_SYMBOL} {GATE_N}-day gate, so there is no gate "
            f"shape to resolve per era and the recorded whole-window exposure stands",
            None,
        )
    if gate.whole <= 0.0:
        return Exposure(
            recorded, recorded, WHOLE_BASIS,
            f"the {GATE_SYMBOL} {GATE_N}-day gate was never on over this trial's window, so its "
            f"era shape cannot be scaled and the recorded whole-window exposure stands",
            None,
        )
    fill = recorded / gate.whole
    if fill > MAX_GATE_FILL:
        return Exposure(
            recorded, recorded, WHOLE_BASIS,
            f"the recorded exposure {recorded:.3f} is above the gate's own whole-window on-share "
            f"{gate.whole:.3f}, so this book held money while the gate was off and the gate does "
            f"not govern all of it; the recorded whole-window exposure stands",
            fill,
        )
    value = min(1.0, fill * gate.era)
    return Exposure(
        value, recorded, ERA_BASIS,
        f"the gate was on {gate.era * 100:.1f}% of this era's sessions against "
        f"{gate.whole * 100:.1f}% of the whole window's, and the book was about "
        f"{fill * 100:.1f}% invested whenever the gate let it in",
        fill,
    )


def round_trip_rate(month: int, names: int) -> Decimal:
    """Gotrade's cost of one round trip, as a share of the two dollars of notional it moves.

    ``book_runner._turnover`` sums buy **and** sell notionals, so one unit of recorded turnover is
    one dollar of notional, and the rate that composes with it divides the round trip's fees by
    ``2 x slot`` rather than by the slot. The slot is the owner's funded equity at ``month``
    months of his real plan, split ``names`` ways. Every fee comes from
    :func:`turnover.round_trip`, which calls ``sim.costs.fee_parts``; none is re-derived here.
    """
    slot = turnover.slot_usd(turnover.equity_usd(month), names)
    buy, sell = turnover.round_trip(slot)
    return ((buy.total + sell.total) / (2 * slot)).quantize(RATE_Q)


def mean_round_trip_rate(first_month: int, last_month: int, names: int) -> Decimal:
    """:func:`round_trip_rate` averaged over every month of an era, inclusive.

    An average rather than one month's figure because the ``$0.10`` per-order floor's bite shrinks
    as the owner's deposits arrive: the rate is 0.7226% in month 0 and 0.2498% in month 236, and a
    single endpoint would be wrong in one direction or the other. Measured over months 156..237 --
    2009-2015 of the dev window -- it is 0.251041%.
    """
    if last_month < first_month:
        raise ValueError(f"last_month {last_month} is before first_month {first_month}")
    rates = [round_trip_rate(m, names) for m in range(first_month, last_month + 1)]
    return (sum(rates) / len(rates)).quantize(RATE_Q)


@dataclass(frozen=True, slots=True)
class Fees:
    """The modelled fee drag, and everything a reader needs to argue with it."""

    names: int
    names_from: str
    first_month: int
    last_month: int
    rate: Decimal
    drag: float  # a fraction of equity a year, positive
    sensitivity: tuple[tuple[int, float], ...]


def fee_model(
    turnover_per_year: float,
    window_start: date,
    era: tuple[date, date],
    names: int,
    names_from: str,
) -> Fees:
    """``turnover x the era's mean round-trip rate``, with its own sensitivity band.

    Modelled, never recovered: the fees a run really paid are ``RunStats.costs_usd`` and are not a
    ``trials`` column. The band across :data:`SENSITIVITY_NAMES` is printed beside the answer so a
    guessed book size is visibly bounded rather than quietly load-bearing.
    """
    first = month_offset(window_start, era[0])
    last = month_offset(window_start, era[1])
    rate = mean_round_trip_rate(first, last, names)
    band = tuple(
        (n, turnover_per_year * float(mean_round_trip_rate(first, last, n)))
        for n in SENSITIVITY_NAMES
    )
    return Fees(
        names=int(names),
        names_from=names_from,
        first_month=first,
        last_month=last,
        rate=rate,
        drag=turnover_per_year * float(rate),
        sensitivity=band,
    )


# --------------------------------------------------------------------------- the whole report


@dataclass(frozen=True, slots=True)
class Split:
    """The residual split against a sibling arm that shares the pool, the gate and the frame."""

    candidate_id: str
    trial_n: int
    shared: float  # pool and frame: what the sibling's own residual also carries
    own: float  # this arm's own weighting and selection: the remainder


@dataclass(frozen=True, slots=True)
class Shortfall:
    """One trial's era gap, and where it went. ``gap == -gate_premium - fees.drag + residual``."""

    trial_n: int
    candidate_id: str
    method_id: str
    window: tuple[date, date]
    era_label: str
    era: tuple[date, date]
    months: int
    deposits: int
    mine: float
    theirs: float
    gap: float
    exposure: Exposure
    gate: GateShare | None
    gate_premium: float  # positive: what the gate cost
    fees: Fees
    residual: float  # signed, and never named after a cause
    against: Split | None
    warnings: tuple[str, ...]


def check_against(conn: sqlite3.Connection, row: sqlite3.Row, other: sqlite3.Row) -> None:
    """Refuse an ``--against`` arm the split would be meaningless across. Raises ``LabError``.

    The split only says anything when the two arms share a pool, a gate and a frame, and the only
    evidence of that this module has is that they are two arms of one method. Across methods, or
    across two price fingerprints the benchmark does not share, the subtraction is a number nobody
    can trust -- so it is refused rather than printed with a caveat. That is the one place this
    report refuses rather than warns, and it is deliberate: a warning on the main row still leaves
    a reader a measured number, where a bad split leaves them a fabricated one.
    """
    if int(other["n"]) == int(row["n"]):
        raise store.LabError(
            f"--against {other['candidate_id']} is the trial itself; an arm cannot be its own "
            f"control"
        )
    if str(other["method_id"]) != str(row["method_id"]):
        raise store.LabError(
            f"--against {other['candidate_id']} belongs to {other['method_id']} and "
            f"{row['candidate_id']} belongs to {row['method_id']}. The split attributes what two "
            f"arms have in common to their shared pool and frame, and two different methods share "
            f"neither; this will not print a number nobody can trust"
        )
    bench_n = hardgate.benchmark_n(conn)
    if bench_n is None:
        raise store.LabError(
            f"no {regime.BENCH_CANDIDATE} dev trial, so neither arm can be compared with anything"
        )
    problems = hardgate.mismatches(conn, bench_n, [row, other])
    if problems:
        raise store.LabError(
            f"{row['candidate_id']} and {other['candidate_id']} cannot be compared with "
            f"{regime.BENCH_CANDIDATE}: {hardgate.describe(problems)}. That is the promotion "
            f"gate's own rule (lab/hardgate.py, D10), and a residual split across two price "
            f"fingerprints is cross-store arithmetic"
        )


def measure(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    era_label: object = DEFAULT_ERA,
    *,
    gate: GateShare | None = None,
    names: int | None = None,
    against: sqlite3.Row | None = None,
    store_given: bool = False,
) -> Shortfall:
    """One trial's era gap and its decomposition. Reads the lab; writes nothing; no store.

    ``gate`` is :func:`gate_on_share`'s answer when the caller opened a store, and None otherwise;
    ``store_given`` distinguishes "no store" from "a store, but this book has no shared gate", so
    the output can say which. The residual is computed last, as ``gap + gate premium + fee drag``,
    which makes the three terms sum back to the gap by construction rather than by luck.
    """
    bench, bench_n = benchmark(conn)
    window = trial_window(row)
    label, lo, hi = era_bounds(era_label, window)
    curve = curve_of(row)
    deposits = hardgate.trial_deposits(conn, row, curve)
    mine = wf.measure(curve, lo, hi, deposits)
    theirs = wf.measure(bench, lo, hi)
    if mine is None or mine.cagr is None:
        raise store.LabError(
            f"trial #{row['n']} ({row['candidate_id']}) has too little curve between {lo} and "
            f"{hi} to measure a return over"
        )
    if theirs is None or theirs.cagr is None:
        raise store.LabError(
            f"the recorded {regime.BENCH_CANDIDATE} curve has too little between {lo} and {hi} "
            f"to measure a return over"
        )
    gap = mine.cagr - theirs.cagr

    carries = carries_shared_gate(row["config_text"])
    exposure = era_exposure(float(row["exposure"]), gate, carries, store_given)
    gate_premium = (1.0 - exposure.value) * theirs.cagr

    if names is not None:
        book, how = int(names), "given on the command line"
    else:
        guessed = names_in(row["config_text"])
        if guessed is None:
            book = DEFAULT_NAMES
            how = (
                f"the roster's {DEFAULT_NAMES}, because the recorded configuration names no book "
                f"size this report can read"
            )
        else:
            book = guessed
            how = "read from the recorded configuration's outermost `top=`, which is a guess"
    fees = fee_model(float(row["turnover"]), window[0], (lo, hi), book, how)

    residual = gap + gate_premium + fees.drag

    split: Split | None = None
    if against is not None:
        check_against(conn, row, against)
        peer = measure(
            conn, against, label, gate=gate, names=names, against=None, store_given=store_given
        )
        split = Split(
            candidate_id=str(against["candidate_id"]),
            trial_n=int(against["n"]),
            shared=peer.residual,
            own=residual - peer.residual,
        )

    warnings: list[str] = []
    problems = hardgate.mismatches(conn, bench_n, [row])
    if problems:
        warnings.append(
            f"WARNING {row['candidate_id']} is not comparable with {regime.BENCH_CANDIDATE}: "
            f"{hardgate.describe(problems)}. Every number below is cross-store arithmetic, and "
            f"`lab promote` refuses it (lab/hardgate.py, D10)"
        )

    return Shortfall(
        trial_n=int(row["n"]),
        candidate_id=str(row["candidate_id"]),
        method_id=str(row["method_id"]),
        window=window,
        era_label=label,
        era=(lo, hi),
        months=int(mine.months),
        deposits=len(deposits),
        mine=float(mine.cagr),
        theirs=float(theirs.cagr),
        gap=gap,
        exposure=exposure,
        gate=gate,
        gate_premium=gate_premium,
        fees=fees,
        residual=residual,
        against=split,
        warnings=tuple(warnings),
    )


# --------------------------------------------------------------------------- what it prints


def format_report(sf: Shortfall) -> str:
    """The whole report, in plain words. The owner reads lab output and is not a quant."""
    out: list[str] = []
    for line in sf.warnings:
        out.append(line)
    if sf.warnings:
        out.append("")

    out.append(
        f"Trial #{sf.trial_n}  {sf.candidate_id}  (method {sf.method_id}), dev window "
        f"{sf.window[0]} to {sf.window[1]}."
    )
    out.append(
        f"Era {sf.era_label}: {sf.era[0]} to {sf.era[1]}, {sf.months} months of the recorded "
        f"monthly curve."
    )
    if sf.deposits:
        out.append(
            f"The owner's {sf.deposits} deposits are removed from the curve before it is cut, so "
            f"a deposit is never read as a gain."
        )
    out.append("")
    out.append(f"  what this book earned a year                 {pts(sf.mine):>10}%")
    out.append(f"  what SPY total return earned a year          {pts(sf.theirs):>10}%")
    out.append(f"  gap to SPY TR                                {pts(sf.gap):>10} pts/yr")
    out.append("")
    out.append(
        "Where the gap went. Each line below is computed on its own -- one from the recorded "
        "exposure,"
    )
    out.append(
        "one from the recorded turnover and the fee schedule -- and the residual is whatever "
        "those two"
    )
    out.append("do not explain. It is a residual and is never named after a cause.")
    out.append("")
    out.append(
        f"  gate premium    (1 - {sf.exposure.value:.3f}) x {sf.theirs * 100:.2f}%"
        f"{pts(-sf.gate_premium):>13} pts/yr"
    )
    out.append(
        f"  fee drag        {sf.fees.drag / float(sf.fees.rate):.2f} turns x "
        f"{float(sf.fees.rate) * 100:.4f}%{pts(-sf.fees.drag):>12} pts/yr"
    )
    if sf.against is None:
        out.append(f"  pool + weighting residual                  {pts(sf.residual):>10} pts/yr")
    else:
        out.append(
            f"  pool + frame (shared with {sf.against.candidate_id})"
            f"{pts(sf.against.shared):>10} pts/yr"
        )
        out.append(
            f"  this arm's own weighting and selection     {pts(sf.against.own):>11} pts/yr"
        )
    out.append("  " + "-" * 58)
    out.append(f"  these add back to the gap                  {pts(sf.gap):>10} pts/yr")
    out.append("")

    out.append(
        f"Exposure. The row records {sf.exposure.recorded:.3f} for the whole window, and this "
        f"report prices the"
    )
    out.append(f"gate at {sf.exposure.value:.3f} for this era -- {sf.exposure.basis}, because")
    out.append(f"{sf.exposure.why}.")
    if sf.exposure.basis == ERA_BASIS:
        flat = (1.0 - sf.exposure.recorded) * sf.theirs
        out.append(
            f"Using the whole-window {sf.exposure.recorded:.3f} instead would price the gate at "
            f"{pts(-flat)} pts/yr"
        )
        out.append(
            f"and leave a residual of {pts(sf.gap + flat + sf.fees.drag)} -- which is why this "
            f"distinction is made at all."
        )
    out.append("")

    band = ", ".join(f"{n}: {pts(-d)}" for n, d in sf.fees.sensitivity)
    out.append(
        "Fees. Modelled, not recovered: what the run really paid is not a column in the trials"
    )
    out.append(
        f"table. The model takes {sf.fees.names} names ({sf.fees.names_from}), the owner's real "
        f"funding plan at"
    )
    out.append(
        f"months {sf.fees.first_month} to {sf.fees.last_month} of the dev window, and prices one "
        f"round trip of one slot through"
    )
    out.append(
        f"Gotrade's schedule. At {', '.join(str(n) for n in SENSITIVITY_NAMES)} names the drag "
        f"would be {band} pts/yr,"
    )
    out.append("so the book size is not what this answer rests on.")
    out.append("")

    out.append("Cash. The gate premium assumes money out of the market earned nothing. For")
    out.append(f"{sf.era_label}, {CASH_NOTE.get(sf.era_label, 'this caveat is not recorded')}.")
    out.append("")

    out.append(
        "Read this as an attribution under stated assumptions, not an identity. The two named "
        "terms"
    )
    out.append(
        "are worked out independently and the residual absorbs the error of both, so a small "
        "residual"
    )
    out.append(
        "means the two named causes account for the gap -- not that the residual's own "
        "ingredients are"
    )
    out.append("zero.")
    return "\n".join(out)


def csv_rows(sf: Shortfall) -> list[list[str]]:
    """The report's terms at full precision, for ``--csv``."""
    head = ["trial", "candidate", "method", "era", "term", "value_per_year", "how"]
    rows = [
        head,
        [str(sf.trial_n), sf.candidate_id, sf.method_id, sf.era_label, "book_cagr",
         repr(sf.mine), f"{sf.months} months, de-funded"],
        [str(sf.trial_n), sf.candidate_id, sf.method_id, sf.era_label, "spy_tr_cagr",
         repr(sf.theirs), f"{regime.BENCH_CANDIDATE}, same slice"],
        [str(sf.trial_n), sf.candidate_id, sf.method_id, sf.era_label, "gap",
         repr(sf.gap), "book minus SPY TR"],
        [str(sf.trial_n), sf.candidate_id, sf.method_id, sf.era_label, "gate_premium",
         repr(-sf.gate_premium),
         f"(1 - {sf.exposure.value!r}) x spy, exposure {sf.exposure.basis}"],
        [str(sf.trial_n), sf.candidate_id, sf.method_id, sf.era_label, "fee_drag",
         repr(-sf.fees.drag),
         f"turnover x {sf.fees.rate}, {sf.fees.names} names ({sf.fees.names_from})"],
    ]
    if sf.against is None:
        rows.append([str(sf.trial_n), sf.candidate_id, sf.method_id, sf.era_label,
                     "pool_weighting_residual", repr(sf.residual), "the term the two above "
                     "do not explain"])
    else:
        rows.append([str(sf.trial_n), sf.candidate_id, sf.method_id, sf.era_label,
                     "pool_frame_shared", repr(sf.against.shared),
                     f"also carried by {sf.against.candidate_id} (trial #{sf.against.trial_n})"])
        rows.append([str(sf.trial_n), sf.candidate_id, sf.method_id, sf.era_label,
                     "own_weighting_selection", repr(sf.against.own),
                     f"the remainder over {sf.against.candidate_id}"])
    return rows


def write_csv(sf: Shortfall, path: Path) -> Path:
    """Write :func:`csv_rows` to ``path``. The one file this module touches."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(csv_rows(sf))
    return path
```

**Impact:** a new module. Nothing imports it yet. `ruff check engine` must stay clean.

---

### Step 2: Add the `shortfall` entry to `commands/lab.py`'s module docstring

**File:** `engine/src/seer_engine/commands/lab.py:71` — immediately after the `lab turnover`
entry (which ends with `the looks do not move`) and before `    lab survivorship M0069 ...`
**Change:** insert the block below.

**Code:**

```
    lab shortfall 828 | M0244-PLACEBO30 [--era 2009-2015] [--store DIR] [--against CID]
                  [--names N] [--csv PATH]
                                    report only: where one recorded trial's gap to SPY TR over one
                                    era went -- the gate premium it paid for being out of the
                                    market, the fee drag its turnover bought, and ONE residual for
                                    the pool and the weighting, which is labelled a residual and
                                    never named after a cause. The gap itself is not recomputed:
                                    it comes from the same de-funded walk-forward slice against
                                    REF-SPY-HOLD that lab exposure and lab gate use. With --store
                                    the era's exposure is resolved from the shared SPY 200-day
                                    gate's own on-share per era; without one the recorded
                                    whole-window figure is used and the output says so.
                                    --against names a sibling arm of the same method and splits
                                    the residual into what the two share and what this arm owns.
                                    No trial row, no moments, no status change: N and the looks do
                                    not move
```

**Impact:** documentation only.

---

### Step 3: Add the `shortfall` subparser

**File:** `engine/src/seer_engine/commands/lab.py` — insert between line 441 (the blank line after
`s.add_argument("--eval-years", type=int, default=None, metavar="N")`) and line 442
(`    s = sub.add_parser(` for `"survivorship"`).
**Change:** insert the parser block below, verbatim. Note the doubled `%%` in every `help=`
string and the single `%` in `description=`.

**Code:**

```python
    s = sub.add_parser(
        "shortfall",
        # Every `%` in a `help=` below is doubled: argparse runs each one through
        # %-interpolation (HelpFormatter._expand_help), so a bare `%` is read as a format spec
        # and `lab --help` dies with "unsupported format character". A doubled `%%` renders as
        # one `%`. `description=` is NOT interpolated and must stay single. Same rule as the
        # `costs`, `exposure`, `gate` and `turnover` parsers above.
        help="report only: where one trial's gap to SPY TR over an era went (gate, fees, residual)",
        description=(
            "Split one recorded dev trial's gap to SPY total return over one era into a gate "
            "premium, a modelled fee drag and one residual for the pool and the weighting. The "
            "gap is not recomputed: it comes from walkforward.measure over the recorded monthly "
            "curve, de-funded through hardgate.trial_deposits, against the recorded REF-SPY-HOLD "
            "curve sliced the same way -- the path lab exposure, lab gate and lab survivorship "
            "already take. With --store the era's exposure is resolved by scaling the recorded "
            "whole-window figure by the shared SPY 200-day gate's own on-share in that era "
            "against its on-share over the whole window; without --store, for a book that "
            "carries no shared gate, or for a book that held money while the gate was off, the "
            "recorded whole-window exposure is used and the report says so. The fee drag is a "
            "MODEL -- what a run really paid is not a trials column -- and is printed with a "
            "sensitivity band across book sizes so a guessed name count is visibly bounded. The "
            "residual is a residual: it is the term the two named ones do not explain and it is "
            "never named after a cause. This is an attribution under stated assumptions, not an "
            "identity. Records no trial, no moments, no funding, no provenance, no insight and "
            "no status, so the lab's N and the test-window looks do not move; the test window is "
            "never read, and a test-window trial is refused by name."
        ),
    )
    s.add_argument(
        "trial", metavar="828",
        help="the trial to decompose: a trials.n, or a candidate id like M0244-PLACEBO30",
    )
    s.add_argument(
        "--era", default=None, metavar="2009-2015",
        help="the era to decompose over (default: 2009-2015). One of the eras in "
             "lab/exposure.py's ERAS, or `whole` for the trial's whole window",
    )
    s.add_argument(
        "--store", type=Path,
        default=(Path(os.environ["SEER_RESEARCH_STORE"])
                 if os.environ.get("SEER_RESEARCH_STORE") else None),
        help="a dev-window research store, read for the shared SPY 200-day gate's on-share per "
             "era (default: $SEER_RESEARCH_STORE, else none). Without it the recorded "
             "whole-window exposure is used instead, which measured 5.11 against 3.60 pts/yr of "
             "gate premium on trial 828 -- so pass it when you have one. The stores are "
             "gitignored, so a worktree has none: point this at a checkout that does rather "
             "than rebuilding one. Only the gate symbol's rows of bars.csv are read; no market "
             "is loaded and no backtest is run",
    )
    s.add_argument(
        "--against", default=None, metavar="M0244-FRESH30",
        help="split the pool+weighting residual against this sibling arm of the SAME method: "
             "what that arm's own residual also carries is attributed to the shared pool and "
             "frame, and only the remainder to this arm's own weighting and selection. An arm "
             "of another method, or one whose prices are not the benchmark's (hardgate D10), is "
             "refused rather than reported",
    )
    s.add_argument(
        "--names", type=int, default=None, metavar="30",
        help="the book's name count for the fee model (default: read from the recorded "
             "configuration's outermost `top=`, else the roster's 20). The slot size sets how "
             "hard Gotrade's $0.10 per-order floor bites; measured, the 2009-2015 drag moves "
             "only from 3.71 to 3.85 pts/yr across 10 to 50 names, and the report prints that "
             "band beside its answer",
    )
    s.add_argument(
        "--csv", type=Path, default=None, metavar="PATH",
        help="also write the terms to PATH as CSV, at full precision",
    )
```

**Impact:** `lab shortfall --help` renders. No other parser moves.

---

### Step 4: Add the `_shortfall` handler

**File:** `engine/src/seer_engine/commands/lab.py` — insert immediately **after** `_walkforward`'s
final `return 0` (the function begins at `:2352`) and before the next top-level definition.
**Change:** insert the function below.

**Code:**

```python
def _shortfall(conn, args) -> int:
    """``lab shortfall``: where one recorded trial's gap to SPY TR over one era went.

    A report in the sense ``lab regime`` and ``lab turnover`` are reports: it re-runs nothing,
    inserts no trial, moves no status and spends no look, and it prints the lab's N and the
    test-window looks before and after so the invariant is visible on the terminal rather than
    merely asserted in a test.

    The one optional read is ``--store``, and it is narrow: the gate symbol's rows out of the
    store's own ``bars.csv``, so the shared SPY 200-day gate's on-share can be measured per era.
    No market is built and no backtest runs. The store is opened only when the recorded
    configuration actually carries that gate, because for a book that does not there is nothing
    for it to say.

    A trial whose curves were measured on prices other than the benchmark's gets a ``WARNING``
    line and its numbers anyway (D10 in ``lab/hardgate.py``): a report warns, the gate refuses.
    ``--against`` is the exception and refuses, because a residual split across two price
    fingerprints is a fabricated number rather than a caveated one.
    """
    from seer_engine.lab import shortfall

    row = shortfall.resolve_trial(conn, args.trial)
    against = None if args.against is None else shortfall.resolve_trial(conn, args.against)
    era = shortfall.DEFAULT_ERA if args.era is None else args.era
    window = shortfall.trial_window(row)
    _label, lo, hi = shortfall.era_bounds(era, window)

    n_before = store.dev_trial_count(conn)
    looks_before = store.test_looks(conn)

    gate = None
    store_given = args.store is not None
    if store_given:
        if shortfall.carries_shared_gate(row["config_text"]):
            t0 = time.perf_counter()
            gate = shortfall.gate_on_share(Path(args.store), window, (lo, hi))
            log.info(
                "gate on-share measured from %s: %.4f whole, %.4f era (%.1fs)",
                args.store, gate.whole, gate.era, time.perf_counter() - t0,
            )
        else:
            log.info(
                "%s carries no shared %s %d-day gate; the store is not read",
                row["candidate_id"], shortfall.GATE_SYMBOL, shortfall.GATE_N,
            )

    report = shortfall.measure(
        conn, row, era, gate=gate, names=args.names, against=against, store_given=store_given
    )
    print(shortfall.format_report(report))
    if args.csv is not None:
        print(f"\nterms written to {shortfall.write_csv(report, Path(args.csv))}")
    print(
        f"\nNothing was recorded. Lab N (dev trials): {n_before} before, "
        f"{store.dev_trial_count(conn)} after; test-window looks used: {looks_before} before, "
        f"{store.test_looks(conn)} after. No journal entry, so seertrade.site/sera is unchanged "
        f"and `lab stage` is not needed."
    )
    return 0
```

**Impact:** `time`, `Path`, `log` and `store` are already imported at the top of
`commands/lab.py`; no new top-level import is added.

---

### Step 5: Register the handler

**File:** `engine/src/seer_engine/commands/lab.py:2870` — inside `_HANDLERS`, between
`"walkforward": _walkforward,` and `"luck": _luck,`.
**Change:** add the single line.

**Code:**

```python
    "shortfall": _shortfall,
```

**Impact:** `lab shortfall` dispatches. `store.LabError` is already caught by `run` and returns 2.

---

### Step 6: Create `engine/tests/test_lab_shortfall.py`

**File:** `engine/tests/test_lab_shortfall.py` (new)
**Change:** the whole file.

**Why this mix of fixtures, decided deliberately.** The *rules* are tested on synthetic rows in a
temp database: they must hold for any input, they must not depend on what the lab happens to
contain, and they must keep passing on the day the lab contains something different. The
*headline* is pinned against the committed `lab/lab.sqlite`, because trial 828 is a frozen,
append-only row whose numbers cannot move, and because the only thing that would otherwise notice
an unrelated change to `walkforward.measure` or `turnover.round_trip` silently re-pricing the
published answer is nobody. That pinned test opens the committed file through
`store.connect_readonly`, which runs no migration, so reading it cannot dirty the file (every
ordinary `lab` subcommand migrates on connect and does). It reads `store.COMMITTED_DB` explicitly
rather than `store.DB_PATH`, so a parallel session's `SEER_LAB_DB` cannot swing the pin, and it
skips rather than fails when trial 828 is absent. The gate's era shape is tested on a synthetic
`History` built in the test module, because the research stores are gitignored and absent from
every worktree.

**Code:**

```python
"""The shortfall decomposition (lab/shortfall.py): the gap, the terms, and the residual.

The rules are tested on synthetic rows in a temp database, so they hold for any input and keep
holding on the day the real lab contains something different. The headline -- trial 828's
2009-2015 gap and its decomposition -- is pinned against the committed lab.sqlite, because that
row is frozen and append-only and nothing else would notice if an unrelated change re-priced the
published answer. The committed file is opened read-only (no migration, so no dirtying) and the
pin skips when the row is absent.

The research stores are gitignored and absent from every worktree, so the gate's era shape is
measured on a synthetic History built here instead.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import pytest

from labkit import LAB_PRICE_FINGERPRINT, stamp_provenance
from seer_engine.backtest import regime
from seer_engine.lab import hardgate, shortfall, store, turnover
from seer_engine.lab import walkforward as wf
from seer_engine.lab.exposure import WHOLE
from seer_engine.lab.gate_probe import GATE_N, GATE_SYMBOL
from seer_engine.strategies.base import History

BENCH_SPAN = (date(1993, 2, 1), date(2015, 10, 16))
DEV_SPAN = (date(1996, 1, 2), date(2015, 10, 16))

GATED_CONFIG = (
    "rules=TradeRules(id='monthly-hold-frac-gotrade')\n"
    "allocator=<M0244>\n"
    "params=GestureParams(top=30,screen=FactorParams(rank='momentum',top=1000,"
    "trend=('SPY',200)))\n"
)
UNGATED_CONFIG = (
    "rules=TradeRules(id='monthly-hold-frac-gotrade')\n"
    "allocator=<M0248>\n"
    "params=CheapBuybackParams(top=20,w_pct=50,pick='random',seed=1)\n"
)


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    yield c
    c.close()


def _months(start: date, end: date) -> list[date]:
    out, d = [], date(start.year, start.month, 1)
    while True:
        nxt = date(d.year + (d.month == 12), (d.month % 12) + 1, 1)
        last = nxt - timedelta(days=1)
        if last > end:
            return out
        if last >= start:
            out.append(last)
        d = nxt


def _curve(months: list[date], annual: float) -> str:
    out, v = [], 1.0
    for d in months:
        out.append([d.isoformat(), round(v, 8)])
        v *= (1.0 + annual) ** (1.0 / 12.0)
    return json.dumps(out)


def _trial(**kw) -> store.TrialRow:
    base = dict(
        method_id="M0001", candidate_id="M0001-A", config_digest="d1",
        config_text=GATED_CONFIG, rules_id="MONTHLY_HOLD", allocator_id="M0001", window="dev",
        start=DEV_SPAN[0].isoformat(), end=DEV_SPAN[1].isoformat(),
        store_fingerprint="399d0d25", git_sha="abc123", run_at="2026-10-19T00:00:00+00:00",
        total_return=3.0, cagr=0.12, max_drawdown=0.11, profit_factor=1.6, trades=250,
        sharpe=0.9, exposure=0.69, turnover=15.0, worst_year=2008, worst_year_return=-0.1,
        spy_tr_return=2.0, spy_tr_cagr=0.08, mar=0.8, failed="", eligible=False, dsr=0.5,
        n_trials_at_run=60, curve_json=_curve(_months(*DEV_SPAN), 0.09),
    )
    base.update(kw)
    return store.TrialRow(**base)


def _lab(conn, *, arms=(("M0001", "M0001-A", 0.09, GATED_CONFIG),), prices=LAB_PRICE_FINGERPRINT):
    """The benchmark plus one dev trial per arm, all stamped on the same price fingerprint."""
    with conn:
        store.add_method(conn, id="H-REF", name="SPY buy and hold", family="reference",
                         source_kind="seed", hypothesis="h", status="registered")
        ns = store.insert_trials(conn, [_trial(
            method_id="H-REF", candidate_id=regime.BENCH_CANDIDATE, config_digest="ref",
            config_text="params=None\n", start=BENCH_SPAN[0].isoformat(),
            exposure=1.0, turnover=0.0,
            curve_json=_curve(_months(*BENCH_SPAN), 0.08),
        )])
        stamp_provenance(conn, ns, price_fingerprint=prices)
        seen: set[str] = set()
        for mid, cid, annual, cfg in arms:
            if mid not in seen:
                store.add_method(conn, id=mid, name=f"n{mid}", family="momentum",
                                 source_kind="knowledge", hypothesis="h", status="registered")
                seen.add(mid)
            ns = store.insert_trials(conn, [_trial(
                method_id=mid, candidate_id=cid, config_digest=f"d-{cid}", config_text=cfg,
                curve_json=_curve(_months(*DEV_SPAN), annual),
            )])
            stamp_provenance(conn, ns, price_fingerprint=prices)


def _spy_history(first: date, days: int, *, rise_after: int) -> History:
    """A SPY-shaped history that falls for ``rise_after`` sessions and then rises.

    Deterministic and hand-checkable: the gate can only be on once the 200-day mean is behind the
    close, which is exactly what the rise produces and the fall does not.
    """
    dates = np.array(
        [np.datetime64(first + timedelta(days=i)) for i in range(days)], dtype="datetime64[D]"
    )
    t = np.arange(days, dtype=np.float64)
    close = np.where(t < rise_after, 100.0 - 0.05 * t, 100.0 - 0.05 * rise_after + 0.4 * (t - rise_after))
    close = np.maximum(close, 1.0)
    return History(GATE_SYMBOL, dates, close.copy(), close * 1.01, close * 0.99, close,
                   np.full(days, 1e6))


# --------------------------------------------------------------------------- the gap


def test_the_era_slice_is_walkforwards_own_and_is_not_recomputed(conn):
    _lab(conn)
    row = shortfall.resolve_trial(conn, "M0001-A")
    sf = shortfall.measure(conn, row, "2009-2015")
    bench, _n = shortfall.benchmark(conn)
    curve = shortfall.curve_of(row)
    deposits = hardgate.trial_deposits(conn, row, curve)
    mine = wf.measure(curve, sf.era[0], sf.era[1], deposits)
    theirs = wf.measure(bench, sf.era[0], sf.era[1])
    assert sf.mine == pytest.approx(mine.cagr)
    assert sf.theirs == pytest.approx(theirs.cagr)
    assert sf.gap == pytest.approx(mine.cagr - theirs.cagr)
    assert sf.months == mine.months


def test_the_benchmark_row_is_the_hard_gates_own(conn):
    _lab(conn)
    assert shortfall.benchmark(conn)[1] == hardgate.benchmark_n(conn)


def test_the_terms_sum_back_to_the_gap(conn):
    _lab(conn)
    row = shortfall.resolve_trial(conn, "M0001-A")
    sf = shortfall.measure(conn, row, "2009-2015")
    assert sf.gap == pytest.approx(-sf.gate_premium - sf.fees.drag + sf.residual, abs=1e-12)


def test_the_split_sums_back_to_the_residual(conn):
    _lab(conn, arms=(("M0001", "M0001-A", 0.09, GATED_CONFIG),
                     ("M0001", "M0001-B", 0.12, GATED_CONFIG)))
    row = shortfall.resolve_trial(conn, "M0001-A")
    peer = shortfall.resolve_trial(conn, "M0001-B")
    sf = shortfall.measure(conn, row, "2009-2015", against=peer)
    assert sf.against is not None
    assert sf.against.shared + sf.against.own == pytest.approx(sf.residual, abs=1e-12)
    alone = shortfall.measure(conn, peer, "2009-2015")
    assert sf.against.shared == pytest.approx(alone.residual)


# --------------------------------------------------------------------------- what is refused


def test_a_test_window_trial_is_refused_by_name(conn):
    _lab(conn)
    with conn:
        ns = store.insert_trials(conn, [_trial(
            method_id="M0001", candidate_id="M0001-T", config_digest="d-t", window="test",
            start="2015-10-19", end="2026-10-01",
            curve_json=_curve(_months(date(2015, 11, 1), date(2026, 1, 31)), 0.07),
        )])
        stamp_provenance(conn, ns)
    with pytest.raises(store.LabError, match="dev window and nothing else"):
        shortfall.resolve_trial(conn, "M0001-T")


def test_an_against_from_another_method_is_refused(conn):
    _lab(conn, arms=(("M0001", "M0001-A", 0.09, GATED_CONFIG),
                     ("M0002", "M0002-A", 0.12, GATED_CONFIG)))
    row = shortfall.resolve_trial(conn, "M0001-A")
    other = shortfall.resolve_trial(conn, "M0002-A")
    with pytest.raises(store.LabError, match="two different methods share neither"):
        shortfall.measure(conn, row, "2009-2015", against=other)


def test_an_against_on_other_prices_is_refused(conn):
    """D10: a residual split across two price fingerprints is cross-store arithmetic."""
    _lab(conn)
    with conn:
        store.add_method(conn, id="M0001-X", name="x", family="momentum",
                         source_kind="knowledge", hypothesis="h", status="registered")
        ns = store.insert_trials(conn, [_trial(
            method_id="M0001", candidate_id="M0001-B", config_digest="d-b",
            curve_json=_curve(_months(*DEV_SPAN), 0.12),
        )])
        stamp_provenance(conn, ns, price_fingerprint="e" * 64)
    row = shortfall.resolve_trial(conn, "M0001-A")
    other = shortfall.resolve_trial(conn, "M0001-B")
    with pytest.raises(store.LabError, match="D10"):
        shortfall.measure(conn, row, "2009-2015", against=other)


def test_an_arm_cannot_be_its_own_control(conn):
    _lab(conn)
    row = shortfall.resolve_trial(conn, "M0001-A")
    with pytest.raises(store.LabError, match="its own control"):
        shortfall.measure(conn, row, "2009-2015", against=row)


def test_an_unknown_era_names_the_ones_that_exist(conn):
    with pytest.raises(store.LabError, match="2009-2015"):
        shortfall.era_bounds("2016-2020", DEV_SPAN)


def test_whole_is_the_trials_own_window():
    label, lo, hi = shortfall.era_bounds("whole", DEV_SPAN)
    assert (label, lo, hi) == (WHOLE, DEV_SPAN[0], DEV_SPAN[1])


def test_a_store_without_bars_is_refused(tmp_path):
    with pytest.raises(store.LabError, match="bars.csv"):
        shortfall.gate_history(tmp_path)


# --------------------------------------------------------------------------- the gate's shape


def test_the_gate_share_is_measured_with_the_labs_own_trend_rule():
    """A long fall then a long rise: off through the fall, on well into the rise."""
    first = date(2000, 1, 1)
    h = _spy_history(first, 900, rise_after=400)
    window = (first, first + timedelta(days=899))
    early = (first, first + timedelta(days=399))
    late = (first + timedelta(days=700), window[1])
    gate = shortfall.gate_shares(h, window, early)
    assert gate.era == 0.0  # the first 199 bars cannot be read, and the rest are falling
    assert gate.era_sessions == 400
    late_gate = shortfall.gate_shares(h, window, late)
    assert late_gate.era == 1.0
    assert 0.0 < late_gate.whole < 1.0


def test_era_exposure_scales_by_the_gates_own_era_shape():
    gate = shortfall.GateShare(GATE_SYMBOL, GATE_N, 0.711620, 0.805848, 4983, 1710, "s")
    got = shortfall.era_exposure(0.691941, gate, carries_gate=True, store_given=True)
    assert got.basis == shortfall.ERA_BASIS
    assert got.value == pytest.approx(0.691941 * (0.805848 / 0.711620), abs=1e-9)
    assert got.value == pytest.approx(0.7836, abs=5e-4)


def test_without_a_store_the_whole_window_figure_is_used_and_labelled():
    got = shortfall.era_exposure(0.691941, None, carries_gate=True, store_given=False)
    assert got.basis == shortfall.WHOLE_BASIS
    assert got.value == 0.691941
    assert "no --store" in got.why


def test_a_book_with_no_shared_gate_falls_back_and_says_so():
    gate = shortfall.GateShare(GATE_SYMBOL, GATE_N, 0.711620, 0.805848, 4983, 1710, "s")
    got = shortfall.era_exposure(0.915296, gate, carries_gate=False, store_given=True)
    assert got.basis == shortfall.WHOLE_BASIS
    assert "carries no shared" in got.why


def test_a_book_that_held_money_with_the_gate_off_falls_back_and_says_so():
    """M0248-R's shape: exposure 0.915 against a gate that was on 0.712 of the window."""
    gate = shortfall.GateShare(GATE_SYMBOL, GATE_N, 0.711620, 0.805848, 4983, 1710, "s")
    got = shortfall.era_exposure(0.915296, gate, carries_gate=True, store_given=True)
    assert got.basis == shortfall.WHOLE_BASIS
    assert got.fill is not None and got.fill > shortfall.MAX_GATE_FILL
    assert "above the gate's own whole-window on-share" in got.why


# --------------------------------------------------------------------------- the fee model


@pytest.mark.parametrize(
    "month, rate",
    [(0, "0.00722559"), (24, "0.00298494"), (120, "0.00254892"), (236, "0.00249849")],
)
def test_the_fee_model_reproduces_the_measured_per_dollar_rates(month, rate):
    """Measured 2026-10-19 at 30 names on the owner's funding: 0.7226%, 0.2985%, 0.2549%, 0.2498%."""
    assert shortfall.round_trip_rate(month, 30) == Decimal(rate)


def test_the_era_mean_rate_is_the_measured_one():
    """Months 156..237 are 2009-2015 of the dev window; measured 0.251041%."""
    assert shortfall.mean_round_trip_rate(156, 237, 30) == Decimal("0.00251041")


def test_the_rate_divides_by_both_sides_of_the_round_trip():
    """trials.turnover counts buys AND sells (book_runner._turnover), so the rate must too."""
    slot = turnover.slot_usd(turnover.equity_usd(200), 30)
    buy, sell = turnover.round_trip(slot)
    assert shortfall.round_trip_rate(200, 30) == (
        (buy.total + sell.total) / (2 * slot)
    ).quantize(shortfall.RATE_Q)


def test_the_month_offsets_are_the_eras_own():
    fees = shortfall.fee_model(
        15.054823476049172, date(1996, 1, 3), (date(2009, 1, 1), date(2015, 10, 16)),
        30, "test",
    )
    assert (fees.first_month, fees.last_month) == (156, 237)
    assert fees.rate == Decimal("0.00251041")
    assert fees.drag == pytest.approx(0.0378, abs=5e-5)
    assert [n for n, _d in fees.sensitivity] == list(shortfall.SENSITIVITY_NAMES)


def test_the_book_size_is_read_from_the_outermost_top():
    assert shortfall.names_in(GATED_CONFIG) == 30  # not the screen's top=1000
    assert shortfall.names_in(UNGATED_CONFIG) == 20
    assert shortfall.names_in("params=None\n") is None
    assert shortfall.names_in("") is None


def test_an_unreadable_book_size_falls_back_to_the_roster_and_says_so(conn):
    _lab(conn, arms=(("M0001", "M0001-A", 0.09, "params=None\n"),))
    row = shortfall.resolve_trial(conn, "M0001-A")
    sf = shortfall.measure(conn, row, "2009-2015")
    assert sf.fees.names == shortfall.DEFAULT_NAMES == turnover.ROSTER_NAMES
    assert "roster" in sf.fees.names_from
    assert "roster" in shortfall.format_report(sf)


# --------------------------------------------------------------------------- the gate detector


def test_the_gate_is_detected_from_the_recorded_configuration_generically():
    assert shortfall.carries_shared_gate(GATED_CONFIG)
    assert not shortfall.carries_shared_gate(UNGATED_CONFIG)
    timing = "params=BlendParams(parts=(BlendPart(params=TimingParams(hold='SPY',signal='SPY',rule='sma',n=200)),))\n"
    assert shortfall.carries_shared_gate(timing)
    off = timing.replace("rule='sma'", "rule='always'")
    assert not shortfall.carries_shared_gate(off)
    other = "params=FactorParams(rank='momentum',top=20,trend=('QQQ',200))\n"
    assert not shortfall.carries_shared_gate(other)


# --------------------------------------------------------------------------- what it says


def test_the_report_says_what_it_is_and_what_it_assumed(conn):
    _lab(conn)
    row = shortfall.resolve_trial(conn, "M0001-A")
    text = shortfall.format_report(shortfall.measure(conn, row, "2009-2015"))
    assert "attribution under stated assumptions, not an identity" in text
    assert "never named after a cause" in text
    assert "T-bills paid about nothing after 2008" in text
    assert shortfall.WHOLE_BASIS in text  # which exposure figure was used
    assert "Modelled, not recovered" in text


def test_the_pre_2008_cash_caveat_is_carried_per_era(conn):
    _lab(conn)
    row = shortfall.resolve_trial(conn, "M0001-A")
    text = shortfall.format_report(shortfall.measure(conn, row, "1996-2002"))
    assert "T-bills paid a real rate" in text
    assert "LARGER than the truth" in text


def test_the_csv_carries_every_term(conn):
    _lab(conn)
    row = shortfall.resolve_trial(conn, "M0001-A")
    rows = shortfall.csv_rows(shortfall.measure(conn, row, "2009-2015"))
    terms = [r[4] for r in rows[1:]]
    assert terms == ["book_cagr", "spy_tr_cagr", "gap", "gate_premium", "fee_drag",
                     "pool_weighting_residual"]


# --------------------------------------------------------------------------- the pinned headline


def _committed():
    """The committed lab, read-only (no migration, so the file is not dirtied), or None."""
    path = store.COMMITTED_DB
    if not path.is_file():
        return None
    try:
        return store.connect_readonly(path)
    except store.LabError:
        return None


def test_trial_828_decomposes_the_way_it_was_measured():
    """The phase's own headline, pinned on a frozen append-only row.

    No research store, so this is the whole-window-exposure reading: gap -8.24, gate -5.11,
    fees -3.78, residual +0.65. The era-resolved reading -- gate -3.60, residual -0.87 -- needs
    the dev store and is checked by hand in the backtest note, not here.
    """
    c = _committed()
    if c is None:
        pytest.skip("no committed lab database")
    try:
        row = c.execute("SELECT * FROM trials WHERE n = 828").fetchone()
        if row is None or row["candidate_id"] != "M0244-PLACEBO30":
            pytest.skip("trial 828 is not M0244-PLACEBO30 in this lab")
        sf = shortfall.measure(c, row, "2009-2015")
        assert sf.gap == pytest.approx(-0.0824, abs=5e-4)
        assert sf.theirs == pytest.approx(0.16603, abs=5e-5)
        assert sf.exposure.basis == shortfall.WHOLE_BASIS
        assert sf.gate_premium == pytest.approx(0.0511, abs=5e-4)
        assert sf.fees.names == 30
        assert sf.fees.rate == Decimal("0.00251041")
        assert sf.fees.drag == pytest.approx(0.0378, abs=5e-4)
        assert sf.residual == pytest.approx(0.0065, abs=5e-4)
        assert sf.gap == pytest.approx(-sf.gate_premium - sf.fees.drag + sf.residual, abs=1e-12)
        assert sf.warnings == ()  # measured: D10 clean against REF-SPY-HOLD
    finally:
        c.close()


def test_the_era_resolved_reading_of_trial_828_is_the_one_that_retires_the_82():
    """With the gate's measured era shape the residual is -0.87, not +0.65.

    The gate shares are the measured ones (lab/shortfall.py's docstring); only the scaling is
    exercised here, because the store that produced them is gitignored.
    """
    c = _committed()
    if c is None:
        pytest.skip("no committed lab database")
    try:
        row = c.execute("SELECT * FROM trials WHERE n = 828").fetchone()
        if row is None or row["candidate_id"] != "M0244-PLACEBO30":
            pytest.skip("trial 828 is not M0244-PLACEBO30 in this lab")
        gate = shortfall.GateShare(GATE_SYMBOL, GATE_N, 0.711620, 0.805848, 4983, 1710, "measured")
        sf = shortfall.measure(c, row, "2009-2015", gate=gate, store_given=True)
        assert sf.exposure.basis == shortfall.ERA_BASIS
        assert sf.exposure.value == pytest.approx(0.7836, abs=5e-4)
        assert sf.gate_premium == pytest.approx(0.0360, abs=5e-4)
        assert sf.residual == pytest.approx(-0.0087, abs=5e-4)
        assert abs(sf.residual) < 0.01  # pool and weighting together, under one point a year
    finally:
        c.close()
```

**Impact:** a new test module. It adds no DB (Postgres) test, so the `PG_TEST_URL` CI rule is
unaffected. The autouse `_isolated_env` fixture in `conftest.py` is untouched.

---

## Verification

**Build — `engine/.venv` ALREADY EXISTS in this worktree. Do not create it, and do not
`pip install` into it.** The plan index's "Working environment" section is binding: it was built
and verified before any phase ran precisely so that two concurrent phases cannot race to create
the same virtualenv, and `python3.11` is **not on this machine's PATH** at all (the interpreter is
`/home/miftah/miniconda3/bin/python3.12`). If it is genuinely broken, say so in the phase report
rather than rebuilding it under another phase's feet.

```bash
cd /home/miftah/.worktrees/seer/lab-shortfall-and-control-shape
PYTHONPATH=engine/src engine/.venv/bin/python -c "import seer_engine.lab.shortfall as s; print(s.DEFAULT_ERA)"
```

`PYTHONPATH=engine/src` is required on every run from this worktree — without it pytest and python
silently use the main checkout instead of this branch.

**Lint:**

```bash
engine/.venv/bin/ruff check engine      # CI is bugs only: E9 and F, minus F401
```

**Tests:**

```bash
cd /home/miftah/.worktrees/seer/lab-shortfall-and-control-shape
PYTHONPATH=engine/src engine/.venv/bin/pytest engine/tests/test_lab_shortfall.py
PYTHONPATH=engine/src engine/.venv/bin/pytest engine/tests      # the whole suite, -n auto
```

Never pass `-o addopts`: it drops `-n auto` and the suite goes from ~62s to ~342s.

**Manual check — the headline, and the one thing the phase exists to answer.**
`lab/lab.sqlite` is migrated on connect by every `lab` subcommand, so **hash it first**:

```bash
cd /home/miftah/.worktrees/seer/lab-shortfall-and-control-shape
BEFORE=$(sha256sum lab/lab.sqlite | cut -d' ' -f1)

PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab shortfall 828 \
  --store /home/miftah/seer/engine/.research

PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab shortfall 828 \
  --store /home/miftah/seer/engine/.research --against M0244-FRESH30

PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab shortfall M0244-PLACEBO30 \
  --era whole --store /home/miftah/seer/engine/.research

PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab shortfall 828   # no store

AFTER=$(sha256sum lab/lab.sqlite | cut -d' ' -f1)
[ "$BEFORE" = "$AFTER" ] || git checkout -- lab/lab.sqlite
git status --short lab/ web/data/      # must be empty
```

Do **not** pipe any of those into `grep`/`head`: a piped `lab` command hides its exit code
(`seer-lab-note-double-append-from-grep-exit-code`). Read the output directly.

`lab/lab.sqlite` is never committed from this branch, and `web/data/lab.json` must not move
(nothing is journaled, so `lab stage` is not run by this phase at all).

**What the first run must print** (measured during planning; these are targets, not assumptions):

```
gap to SPY TR                                  -8.24 pts/yr
  gate premium    (1 - 0.784) x 16.60%         -3.60 pts/yr
  fee drag        15.05 turns x 0.2510%        -3.78 pts/yr
  pool + weighting residual                    -0.87 pts/yr
```

with no `WARNING` line, 30 names read from the configuration, a sensitivity band of
`10: -3.71, 20: -3.74, 30: -3.78, 50: -3.85`, the 2009-2015 cash note, and
`Lab N (dev trials): 824 before, 824 after; test-window looks used: 4 before, 4 after.`

`--against M0244-FRESH30` must print `pool + frame (shared with M0244-FRESH30) -0.39` and
`this arm's own weighting and selection -0.48`.

`--era whole` must print gap −0.58, gate −2.44, fee −4.01, residual **+5.87**.

The no-store run must print gate −5.11, residual **+0.65**, and the sentence
`no --store was given, so the gate's era shape could not be measured`.

**If any of those numbers disagree with the implementation**, the implementation's number is the
finding. Do not tune the code until it matches. Record the discrepancy — what was expected, what
came out, and the one line of arithmetic that differs — at the bottom of this plan file under a
`## Measured, not assumed` heading, and carry it into Phase 4's backtest note. The arithmetic is
the deliverable; the agreement is only evidence.

**Exit criteria**

1. `lab shortfall 828`, `lab shortfall M0244-PLACEBO30`, `--era whole`, `--era 1996-2002`,
   `--store`, `--against`, `--names` and `--csv` all work and exit 0.
2. `lab shortfall <a test-window trial>` exits 2 with a message naming the dev window.
3. `lab shortfall 828 --against M0248-R` exits 2 (another method).
4. The three terms sum back to the gap, asserted by a test.
5. The report states, in words a non-quant reads: that it is an attribution under stated
   assumptions and not an identity; that the residual is a residual; that cash earned nothing
   after 2008 and something before it, carried per era; and which exposure figure it used.
6. With the dev store, trial 828 reads gap −8.24, gate ≈ −3.60, fees ≈ −3.78, residual ≈ −0.87,
   **or** the discrepancy is recorded as above.
7. `ruff check engine` clean; `pytest engine/tests` green; `git status --short lab/ web/data/`
   empty.

---

## Handoffs

Found while planning, deliberately not done here.

- **R2, Phase 2's.** `M0243-NEAR20-R` trades 2.2–3.4× every sibling and is a third mis-shaped
  control the handover did not know about. It belongs to the control-shape check, not here.
- **R2, Phase 4's.** `M0248-R`'s exposure is 0.915 against a gate that was never in its
  configuration at all — it carries no shared gate, so this report correctly falls back to the
  whole-window figure for it. That is also the arm whose turnover is 3.1× the book it controls,
  which is Phase 2's finding and Phase 4's refusal (phase 2 measures it at 3.180× trades and 3.078× turnover against `M0248-EQ`, the arm it actually controls).
- **R1, Phase 4's to write down.** Phase 4 owns
  `docs/backtests/2026-10-19-trial-828-shortfall.md` and the three corrections (MEMORY.md line,
  insight 461, the `/sera` synthesis page). This phase produces the numbers it quotes and writes
  none of those files. Specifically Phase 4 should record: **the "8.2 pt equal-weight handicap"
  is retired** — of 8.24 pts/yr, 3.60 is the SPY-200 gate, 3.78 is Gotrade's fees at 15 turns a
  year, and pool and weighting together are bounded at 0.87, of which at most 0.48 is this arm's
  own weighting (split against `M0244-FRESH30`).
- **Not taken: a `--credit-cash` knob.** The pre-2008 cash caveat is carried as prose, not as a
  model. Crediting idle cash the short rate is a real change to the lab's arithmetic
  (`seer-idle-cash-credit-worth-08-before-2008-only` measured it at 0.8 pts/yr before 2008 and
  nothing after), and it belongs in the simulator, not in a report's assumption switch.
- **Not taken: era-resolving `turnover` as well as `exposure`.** `trials.turnover` is also a
  whole-window scalar and has no gate-shaped proxy to scale it by. The fee term therefore assumes
  the book traded at its whole-window rate in every era, which the report does not currently say.
  A one-line caveat would be a fair addition; it was left out rather than guessed at, and a future
  phase that wants it should measure a per-era turnover proxy first.
- **Not taken: a drive-by `_regime` / `_walkforward` refactor.** `_comparability_warnings`
  (`commands/lab.py:2217`) does almost what `measure`'s warning block does, but it takes a row
  list and a `wanted` set shaped for a table report. Reusing it would mean changing a function
  Phases 3 and 4 also quote. Left alone.

---

## Rollback

`git revert` this phase's commit. Everything it adds is additive — one new module, one new
subcommand, one new test file — and nothing it touches is a recorded row, a method file, a frozen
record, `web/`, or `lab/lab.sqlite`. Reverting restores `lab --help` and every other subcommand
exactly as they were; no other phase depends on `lab/shortfall.py` existing.

If the revert happens after Phases 3 or 4 have also edited `commands/lab.py`, revert by hand
instead: delete the four insertions named in the Interface Contract (the docstring entry, the
parser block, `_shortfall`, the `_HANDLERS` key) and delete the two new files.
