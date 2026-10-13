> Adopted from `docs/plans/FOLD_VERDICT_AND_FALL_LABEL_PLAN.md` phase 4. Source: `.workflows/plan/fold-verdict-and-fall-label/phase-4.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 4: Price the chart model's turnover

**Plan set:** `FOLD_VERDICT_AND_FALL_LABEL_PLAN.md`
**Analysis:** `docs/analyzer/20261013-082101-K09L_code_analyzer.md`
**Satisfies:** R3 — price the short-horizon chart model's turnover through `sim/costs.py` instead
of building the model
**Depends on:** Phase 1 (hard precondition — see *Before you start*)
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab`

---

## Goal

After this phase the lab can answer, without a backtest and without a research store, what
Gotrade's measured fee schedule charges a book for trading at a given cadence — and the answer is
on the record in `docs/backtests/2026-10-13-chart-model-turnover.md`. The number kills the
short-horizon CNN/LSTM idea before an hour of model code is written: at the owner's real funding,
the **cheapest possible daily book — one name of twenty swapped per session — must add 7.0% a year
just to be level with doing nothing**, and a book that genuinely re-picks itself every session
must add **290% a year**. The lab's own monthly cadence on the same book costs **1.6% a year**.
Nothing is recorded: N and the test-window look count are printed before and after and are equal.

---

## Before you start — phase 1 is a hard precondition

Phase 1 moves the committed `lab/lab.sqlite` from schema v6 to v7 and edits
`engine/src/seer_engine/commands/lab.py` (`_run` and `_show`). `store._migrate` **refuses a version
it does not know**, so any `lab` command running pre-phase-1 code against a v7 database raises
`LabError` and exits 2. Verify phase 1 has landed before writing a line:

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label
git log --oneline -20
grep -n 'SCHEMA_VERSION' engine/src/seer_engine/lab/store.py        # must read "7"
grep -n 'def fold_verdict' engine/src/seer_engine/lab/hardgate.py   # must exist
grep -n 'method_folds' engine/src/seer_engine/lab/store.py | head   # must exist
```

If `SCHEMA_VERSION` is still `"6"` or `fold_verdict` is absent, **stop and wait**. Do not work
around it, do not add the subparser against the old file, and do not touch `store.py`.

When it has landed, re-read `engine/src/seer_engine/commands/lab.py` before editing: this phase
quotes that file **as it looks after phase 1**, and the line numbers below are the pre-phase-1
ones (phase 1 adds lines to `_run`/`_show`, which sit *after* the subparser block this phase edits
and *before* `_HANDLERS`, so expect the `_HANDLERS` table to have drifted downward by a few dozen
lines). Anchor every edit on the quoted text, never on the line number alone.

**Naming correction the reconciler should note:** the index and the analysis both call the
dispatch table `COMMANDS`. In the source it is **`_HANDLERS`** (`commands/lab.py:2637`). This plan
uses the real name.

---

## Interface Contract

**Deletes:** none.
**Renames:** none.
**Creates:**
- module `seer_engine.lab.turnover` (`engine/src/seer_engine/lab/turnover.py`), public names:
  - constants `CADENCES`, `REPICKS_PER_YEAR`, `CONTROL_CADENCE`, `ROSTER_NAMES`, `NAMES`,
    `CHURNS`, `YEARS`, `USD_IDR`, `INITIAL_IDR`, `SCHEDULE`, `FLOOR_MONTHS`, `MIN_NAMES`,
    `MAX_NAMES`, `MIN_YEARS`, `MAX_YEARS`, `MAX_GROWTH`, `CSV_HEAD`
  - validators `check_cadences`, `check_names`, `check_churns`, `check_years`, `check_usd_idr`,
    `check_growth`
  - pricing `equity_usd`, `slot_usd`, `replaced_names`, `floor_binds`, `round_trip`, `price_one`,
    `floor_table`
  - types `Point`, `FloorRow`, `Sweep`
  - `measure`, `format_report`, `csv_rows`, `write_csv`
- subcommand **`lab turnover`** with flags
  `--cadence`, `--names`, `--churn`, `--years`, `--usd-idr`, `--growth`, `--csv`
  (**no `--store`** — it opens no research store)
- handler `commands.lab._turnover` (`engine/src/seer_engine/commands/lab.py`)
- `engine/tests/test_lab_turnover.py`
- `docs/backtests/2026-10-13-chart-model-turnover.md`
- `docs/backtests/2026-10-13-chart-model-turnover-grid.csv`

**Signature changes:** none.

**Requires (from earlier phases):**
- Phase 1: `store.SCHEMA_VERSION == "7"`, the committed `lab/lab.sqlite` migrated and committed,
  and `commands/lab.py` already carrying phase 1's `_run`/`_show` edits.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/sim/costs.py` and every fee constant — this phase **prices with** the
  schedule and never edits it. If the schedule looks wrong, say so in the write-up's *What this
  could not see* section and stop.
- `commands/lab.py` beyond: one line in the module docstring's command list, one subparser block,
  one `_turnover` handler and one `_HANDLERS` row. `_run`, `_show`, `_names`, `_costs`, `_gate`
  and every other handler are Phase 1's or nobody's.
- `lab/store.py`, `lab/hardgate.py`, `lab/runner.py`, `lab/walkforward.py` (Phase 1).
- `lab/tree_rank.py` (Phase 2). Any `lab/methods/*` file (Phase 5). `lab/lab.sqlite` beyond a
  read (Phases 1, 3, 5). `web/` (nobody).

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/turnover.py` | create | the whole pure module (Step 1) |
| `engine/src/seer_engine/commands/lab.py` | modify | one docstring line after `:70` (Step 2); one subparser block inserted after the `names` block ends at `:351` (Step 3); `_turnover` inserted after `_names` ends at `:2039` (Step 4); one `_HANDLERS` row at `:2646` (Step 5) |
| `engine/tests/test_lab_turnover.py` | create | 16 tests (Step 6) |
| `docs/backtests/2026-10-13-chart-model-turnover.md` | create | the write-up (Step 8) |
| `docs/backtests/2026-10-13-chart-model-turnover-grid.csv` | create | the grid at full precision, written by `--csv` (Step 7) |

All line numbers are at base commit `a737aff`; re-anchor on the quoted text after phase 1.

---

## Settled design decisions

These are decided. Do not re-litigate them while implementing; if one turns out to be wrong,
record it in the write-up's *What this could not see* and finish the phase.

**P4-D1 — The equity path is the owner's DEPOSITS, not a simulated return path.**
`equity(month m) = (10,000,000 + 5,000,000 × m) IDR / usd_idr`. No market, no clock, no store.
This is deliberately the *conservative* path: a book that earns nothing stays small, slots stay
small, and the `$0.10` floor bites hardest. A `--growth` knob compounds the deposit path at an
annual rate for sensitivity; it defaults to zero. Measured: growth makes almost no difference
(daily/20/1.0 ten-year breakeven is 290.45% at 0% growth, 280.58% at 10%, 275.47% at 20%) —
because the fee is a near-constant *share* of equity once the floor stops binding.

**P4-D2 — The FX rate is `17,841 IDR/USD` by default, and that is a reconciliation handle.**
It is the rate the frozen production book started at (`tests/test_paper_store.py:715`) and the
rate `lab/name_count.py`'s docstring measured its 1.035% / 0.614% figures at. `--usd-idr`
overrides. Using the same rate is what lets this phase reproduce those four numbers exactly
(see P4-D6).

**P4-D3 — A re-pick that replaces a name is a SELL plus a BUY.** `fee_parts` is called once per
side. The sell side pays the uncapped `sell_extra_rate` of 0.04% on top, so a sell always costs
more than the matching buy. Never price a round trip as "two buys" or as "one order at double
the amount".

**P4-D4 — The horizons are the lab's own, not invented.** `sim/rules.py` offers exactly three rank
cadences (`Cadence = Literal["daily", "weekly", "monthly"]`, `rules.py:53`), and
`rules.describe_rules` spells each out: daily = every session, weekly = the first session of each
ISO week, monthly = the first session of each calendar month. Re-picks a year are therefore
`{daily: 252, weekly: 52, monthly: 12}`, with 252 taken from `paper.compare.SESSIONS_PER_YEAR`
rather than written fresh. **Monthly is the control**: it is the cadence every live roster book
(`MONTHLY_HOLD_FRAC_GOTRADE`) already pays for.

**P4-D5 — The book sizes are the lab's own: 10, 20, 30.** The roster holds 20
(`name_count.ROSTER_NAMES`) and `lab names` sweeps 5..30. **This phase prices a CADENCE, not a
name count.** The name axis exists only because the floor's bite depends on slot size; the
write-up must not drift into recommending a smaller book. The owner's standing instruction,
recorded in `name_count.py`'s docstring, binds here: *"do not plan a name-count reduction on fee
grounds; if the lab tests concentration, test it on the merits."* Quote it in the write-up.

**P4-D6 — The floor is a transient, and saying otherwise would be the misleading single number.**
The analysis says "the `$0.10` floor is the whole of R3's answer". **Measured, that is true only
for the first two months.** At 17,841 IDR/USD on the owner's deposit path:

| names | floor binds through | first month it does not |
|---|---|---|
| 10 | never (month 0 slot is $56.05; 0.2% of that is $0.112 > $0.10) | month 0 |
| 20 | months 0–1 | month 2 |
| 30 | months 0–3 | month 4 |

The floor's exact boundary is a slot of **$47.49** (floor binds) versus **$47.50** (it does not):
`(amount × 0.002).quantize(cent, HALF_UP) < $0.10` is true up to $47.49 and false from $47.50,
because $47.50 × 0.002 = $0.095 rounds half-up to exactly $0.10.

So the module surfaces the floor as **its own table and its own column**, and the write-up says
both halves of the truth: the floor dominates the opening months, and after that the plain rate —
0.2% + an uncapped 0.04% on the sell + 11% PPN, **0.503% per round trip at a large slot** — is
what kills the idea. Multiplied by 252 round trips a year, the plain rate alone is fatal. This is
the honest correction to the analysis note, and it belongs in the write-up, not in a code change.

**P4-D7 — "Break even" means the compounded annual drag.** Each re-pick event `k` costs `f_k`
when the book holds `E_k`, so the book keeps a factor `(1 − f_k/E_k)`. Over the horizon the
survival factor is `S = Π (1 − f_k/E_k)`, and the annual return a strategy must add to be level
with doing nothing is `S^(−1/years) − 1`. No extra assumption, exactly the number the handover
asked for. `breakeven_first_year` is the same product over the first year's events only, un-
annualised — the owner's near-term world, where the floor still bites.

**P4-D8 — Report only (D7 in the set's decisions).** The module opens no database; the command
connects (every `lab` subcommand does, through `run()`) and reads `store.dev_trial_count` and
`store.test_looks` twice, and that is all. Nothing writes a trial, moments, funding, provenance, a
status, or a journal row. The module docstring must argue this in its own words: a free sweep over
a 27-cell grid is exactly the search the luck gate exists to charge for, so the grid may *inform*
a decision and may never *be* one.

---

## Implementation Steps

### Step 1: the pure module

**File:** `engine/src/seer_engine/lab/turnover.py` (new)
**Change:** create it with exactly the content below. It is complete and runnable.

```python
"""``lab turnover``: what Gotrade's schedule charges a book for trading often. Report only.

The handover of 2026-10-13 (section 2, item 3) asked for a number before any CNN/LSTM work:
*compute the turnover a short-horizon chart model would need, and run that turnover through the
fee schedule the simulator already prices.* That is this module. It builds no model, runs no
backtest, opens no research store and reads no database. It takes a **book shape** -- how many
names, how often the book is re-picked, what share of it turns over at each re-pick -- plus the
owner's real funding plan, and prices every single order through ``sim.costs.fee_parts``.

**Why this is arithmetic and not a backtest.** A backtest would answer "what would this model
have returned", which nobody can know before the model exists. The question that can be answered
today is the other one: *how much must it return before it is merely level with doing nothing.*
That question needs only the order count, the order size and the fee schedule, all three of which
are known. If the answer is larger than any plausible edge, the idea is dead and no model has to
be written. It was, and it is.

**The shape of an order.** A re-pick that replaces a name is a SELL plus a BUY, never one trade:
the sell pays an extra uncapped ``sell_extra_rate`` on top of everything the buy pays, so a round
trip is strictly dearer than twice a buy. Both sides go through :func:`sim.costs.fee_parts`, which
owns the half-up trading fee with its ``$0.10`` minimum, the rounded-up regulatory fee with its
``$0.11`` cap, the uncapped sell extra, and PPN at 11% of the two rounded HALF-DOWN. None of that
arithmetic is re-derived here; it is called.

**The floor is a transient, and pretending otherwise would be the misleading number.** At the
owner's funding -- 10,000,000 IDR to start and 5,000,000 IDR more on the 25th of every month --
a twenty-name book opens with slots of about $28, and 0.2% of $28 is $0.06, below the $0.10
minimum. That order pays the floor, and the effective rate is not 0.2% but $0.10 a slot: a round
trip costs **1.035%** of the slot in month 0. But the owner keeps depositing. By month 2 the slot
has passed $47.50 -- the exact point where 0.2% of the amount rounds up to $0.10 and the floor
stops winning -- and by month 3 the round trip is down to **0.614%**, which is where
``lab/name_count.py``'s docstring left it. Those four numbers reproduce here digit for digit, and
``tests/test_lab_turnover.py`` pins them, so the two reports can never quietly disagree.

So the floor's bite **shrinks**, and a single static fee rate would be wrong in both directions.
This module therefore reports the floor as its own column and its own month-by-month table, and
the thing that actually kills a short-horizon model is the *other* half: once the floor is gone,
a round trip settles at about **0.503%** of the slot -- 0.2% a side, plus the sell's uncapped
0.04%, plus PPN -- and a model that re-picks its book every session pays that 252 times a year.

**This prices a CADENCE, not a name count.** The name axis is here only because the floor's bite
depends on slot size. The owner's standing instruction, recorded in ``lab/name_count.py``, binds
this module too: *"do not plan a name-count reduction on fee grounds; if the lab tests
concentration, test it on the merits."* Nothing here recommends a smaller book, and nothing here
may be read as doing so.

**The horizons are the lab's own.** ``sim.rules.Cadence`` offers exactly three rank cadences, and
``sim.rules.describe_rules`` says what each means: daily is every session, weekly the first
session of each ISO week, monthly the first session of each calendar month. So the re-pick counts
are 252, 52 and 12 a year, with 252 taken from ``paper.compare.SESSIONS_PER_YEAR`` rather than
invented. Monthly is the CONTROL: it is what every live roster book already pays for, so the
grid's own baseline is a cost the lab has already accepted rather than a number chosen to flatter.

**A report, not a trial.** Nothing here writes a ``trials`` row, a ``trial_moments`` row, an
``insights`` row or a status, so ``store.dev_trial_count`` (the lab's N) and ``store.test_looks``
are exactly what they were. That is also its limit, and it is the same limit ``lab names``,
``lab exposure`` and ``lab gate`` carry: a free sweep over twenty-seven cells is exactly the
search the luck gate exists to charge for, so this grid may *inform* a decision and may never
*be* one. Nothing it prints makes any configuration eligible, and the only way a cadence is ever
judged is a new method that pre-registers it and pays for its trials like everything else.

Pure: no clock, no randomness, no network, no database, no research store, no printing. The one
file it touches is the CSV the caller explicitly asks for.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from seer_engine.lab import store
from seer_engine.paper.capital import PAPER_INITIAL_IDR
from seer_engine.paper.compare import SESSIONS_PER_YEAR
from seer_engine.sim import costs
from seer_engine.sim.contributions import OWNER_MONTHLY
from seer_engine.sim.model import q

# --------------------------------------------------------------------------- what is swept

CENT = costs.CENT
_ONE = Decimal(1)
_ZERO = Decimal(0)
_EIGHT = Decimal("0.00000001")

#: The rank cadences ``sim.rules`` offers, slowest last. A chart model would trade at the first
#: two; the third is what the lab already pays for and is the control.
CADENCES: tuple[str, ...] = ("daily", "weekly", "monthly")

#: How often each cadence re-picks the book in a year. ``sim.rules.describe_rules`` defines each:
#: daily is every session, weekly the first session of each ISO week, monthly the first session of
#: each calendar month. 252 is ``paper.compare.SESSIONS_PER_YEAR``, the lab's own session year,
#: imported rather than restated so the two can never drift.
REPICKS_PER_YEAR: dict[str, int] = {"daily": SESSIONS_PER_YEAR, "weekly": 52, "monthly": 12}

#: The control: what every live roster book (``MONTHLY_HOLD_FRAC_GOTRADE``) already pays for.
CONTROL_CADENCE = "monthly"

#: What the paper roster holds, and what it keeps holding whatever this measures.
ROSTER_NAMES = 20

#: The book sizes the lab actually uses, bracketing the roster's 20 on both sides. This axis is
#: here because the fee FLOOR depends on slot size -- not because a name count is being chosen.
NAMES: tuple[int, ...] = (10, ROSTER_NAMES, 30)

#: The share of the book replaced at each re-pick: a quarter, a half, and the whole thing.
CHURNS: tuple[Decimal, ...] = (Decimal("0.25"), Decimal("0.50"), Decimal("1.00"))

#: The horizon, in years. Ten is the design's own §1 bar ("a 10-year backtest").
YEARS = 10

#: The rate the frozen production book started at, and the rate ``lab/name_count.py``'s docstring
#: measured its 1.035% / 0.614% figures at. Keeping it lets the two reports be reconciled.
USD_IDR = Decimal("17841")

#: The owner's opening capital. Imported from ``paper.capital`` rather than ``backtest.runner``
#: because the two hold the same number and ``paper.capital`` is stdlib-only, so this module stays
#: import-light and pure. ``tests/test_lab_turnover.py`` asserts the two still agree.
INITIAL_IDR = PAPER_INITIAL_IDR

#: The owner's real top-up: 5,000,000 IDR on the 25th of every month, indefinitely.
SCHEDULE = OWNER_MONTHLY

#: How many months of the funding ramp the floor table prints. Fourteen covers the whole of the
#: period in which the floor binds at any book size this module sweeps, with room to spare.
FLOOR_MONTHS = 14

MIN_NAMES, MAX_NAMES = 2, 60
MIN_YEARS, MAX_YEARS = 1, 50

#: A sanity bound on ``--growth``: this is a fee report, not a return forecast.
MAX_GROWTH = Decimal("1")


# --------------------------------------------------------------------------- validators


def check_cadences(cadences: str | Iterable[str] | None = None) -> tuple[str, ...]:
    """The swept cadences, in ``CADENCES`` order. Accepts ``"daily,weekly"`` or an iterable."""
    if cadences is None:
        return CADENCES
    if isinstance(cadences, str):
        parts = [p.strip().lower() for p in cadences.split(",") if p.strip()]
    else:
        parts = [str(c).strip().lower() for c in cadences]
    if not parts:
        raise store.LabError("--cadence is empty; give cadences like daily,weekly,monthly")
    for p in parts:
        if p not in REPICKS_PER_YEAR:
            raise store.LabError(
                f"unknown cadence {p!r}; sim.rules offers {', '.join(CADENCES)} and nothing else, "
                f"so those are the only horizons this prices"
            )
    return tuple(c for c in CADENCES if c in set(parts))


def check_names(ns: str | Iterable[int] | None = None) -> tuple[int, ...]:
    """The swept book sizes as a sorted, unique tuple. Accepts ``"10,20"`` or an iterable."""
    if ns is None:
        return NAMES
    if isinstance(ns, str):
        parts = [p.strip() for p in ns.split(",") if p.strip()]
        if not parts:
            raise store.LabError("--names is empty; give counts like 10,20,30")
        try:
            values = [int(p) for p in parts]
        except ValueError as e:
            raise store.LabError(f"--names must be whole numbers separated by commas, got {ns!r}") from e
    else:
        values = [int(n) for n in ns]
    out = tuple(sorted(set(values)))
    if not out:
        raise store.LabError("no book sizes to sweep")
    for n in out:
        if not MIN_NAMES <= n <= MAX_NAMES:
            raise store.LabError(
                f"a book size of {n} is outside {MIN_NAMES}..{MAX_NAMES}; this prices a book, "
                f"not a single stock or the whole index"
            )
    return out


def check_churns(churns: str | Iterable[object] | None = None) -> tuple[Decimal, ...]:
    """The swept turnover fractions as a sorted, unique tuple in (0, 1]."""
    if churns is None:
        return CHURNS
    if isinstance(churns, str):
        parts = [p.strip() for p in churns.split(",") if p.strip()]
        if not parts:
            raise store.LabError("--churn is empty; give fractions like 0.25,0.5,1.0")
    else:
        parts = [str(c).strip() for c in churns]
    try:
        values = [Decimal(p) for p in parts]
    except Exception as e:  # ArithmeticError and friends; Decimal is picky about junk
        raise store.LabError(f"--churn must be decimal fractions separated by commas, got {churns!r}") from e
    out = tuple(sorted(set(values)))
    if not out:
        raise store.LabError("no turnover fractions to sweep")
    for c in out:
        if not c.is_finite() or not (_ZERO < c <= _ONE):
            raise store.LabError(
                f"a turnover fraction of {c} is outside (0, 1]; 1.0 means the whole book is "
                f"replaced at every re-pick, and 0 means nothing is traded and there is no fee "
                f"to price"
            )
    return out


def check_years(years: object | None = None) -> int:
    """The horizon in whole years. ``None`` is :data:`YEARS`."""
    if years is None:
        return YEARS
    try:
        value = int(years)
    except (TypeError, ValueError) as e:
        raise store.LabError(f"--years must be a whole number of years, got {years!r}") from e
    if not MIN_YEARS <= value <= MAX_YEARS:
        raise store.LabError(f"--years must be {MIN_YEARS}..{MAX_YEARS}, got {value}")
    return value


def check_usd_idr(rate: object | None = None) -> Decimal:
    """The IDR/USD rate the owner's deposits are converted at. ``None`` is :data:`USD_IDR`."""
    if rate is None:
        return USD_IDR
    try:
        value = Decimal(str(rate))
    except Exception as e:
        raise store.LabError(f"--usd-idr must be a number of rupiah per dollar, got {rate!r}") from e
    if not value.is_finite() or value <= 0:
        raise store.LabError(f"--usd-idr must be > 0, got {value}")
    return value


def check_growth(growth: object | None = None) -> Decimal:
    """The annual rate the deposit path compounds at. ``None`` and ``0`` both mean no growth.

    Zero is the conservative default and the one the report is read at: a book that earns nothing
    stays small, its slots stay small, and the ``$0.10`` floor bites as hard as it ever will. The
    knob exists so the reader can check that the answer does not hinge on it. It does not.
    """
    if growth is None:
        return _ZERO
    try:
        value = Decimal(str(growth))
    except Exception as e:
        raise store.LabError(f"--growth must be an annual rate like 0.10, got {growth!r}") from e
    if not value.is_finite() or not (-_ONE < value <= MAX_GROWTH):
        raise store.LabError(
            f"--growth must be greater than -1 and at most {MAX_GROWTH}, got {value}; this is a "
            f"fee report, not a return forecast"
        )
    return value


# --------------------------------------------------------------------------- the money


def equity_usd(months: int, *, usd_idr: Decimal = USD_IDR, growth: Decimal = _ZERO) -> Decimal:
    """What the owner's book holds after ``months`` of his real funding plan, in dollars.

    The opening 10,000,000 IDR plus one 5,000,000 IDR deposit per elapsed month, converted at one
    rate -- the same single-rate convention ``backtest.runner`` uses, so the answer is about the
    schedule and not about the rupiah. ``growth`` compounds that deposit path at an annual rate;
    at the default of zero this is a pure deposit path, which is the conservative reading.
    """
    if isinstance(months, bool) or not isinstance(months, int):
        raise TypeError(f"months must be an int, got {type(months).__name__}")
    if months < 0:
        raise ValueError(f"months must be >= 0, got {months}")
    base = q((INITIAL_IDR + SCHEDULE.amount_idr * months) / usd_idr)
    if growth == _ZERO:
        return base
    return q(base * (_ONE + growth) ** (Decimal(months) / Decimal(12)))


def slot_usd(equity: Decimal, names: int) -> Decimal:
    """One slot of an equal-weight book of ``names`` holding ``equity`` dollars."""
    if names <= 0:
        raise ValueError(f"names must be > 0, got {names}")
    return q(equity / names)


def replaced_names(names: int, churn: Decimal) -> int:
    """How many names one re-pick replaces: ``names x churn``, half-up, at least one.

    At least one, because a model that re-picks and changes nothing is not re-picking. That floor
    matters: it is what makes the cheapest possible daily book -- one name of twenty swapped a
    session -- still cost 7% a year, which is the number that kills the idea even at its gentlest.
    """
    if churn <= _ZERO:
        return 0
    k = int((Decimal(names) * churn).quantize(_ONE, rounding=ROUND_HALF_UP))
    return max(1, min(int(names), k))


def floor_binds(amount: Decimal, *, regime: costs.FeeRegime | None = None) -> bool:
    """Does this order pay the ``$0.10`` trading-fee MINIMUM rather than the rate?

    This is the one line of ``FeeRegime.fees`` read back out -- the rate applied to the amount and
    compared with the minimum -- and nothing else here re-derives any fee arithmetic. The boundary
    under the current regime is a slot of $47.49 (the floor wins) against $47.50 (it does not):
    0.2% of $47.50 is exactly $0.095, which rounds half-up to $0.10 and ties the minimum.
    """
    r = costs.GOTRADE.current if regime is None else regime
    if r.trading_rate <= _ZERO:
        return False
    cents = max(Decimal(amount).quantize(CENT, rounding=ROUND_HALF_UP), CENT)
    return (cents * r.trading_rate).quantize(CENT, rounding=ROUND_HALF_UP) < r.trading_min


def round_trip(amount: Decimal) -> tuple[costs.FeeParts, costs.FeeParts]:
    """``(buy, sell)`` fees for replacing one slot of ``amount`` dollars, at the current regime.

    Two orders, not one: a re-pick that swaps a name sells the old one and buys the new one, and
    the sell pays an uncapped ``sell_extra_rate`` the buy does not. ``on=None`` means the current
    regime, which is what every backtest uses and so what every comparison in the lab is against.
    """
    return costs.fee_parts("buy", amount), costs.fee_parts("sell", amount)


# --------------------------------------------------------------------------- one priced cell


@dataclass(frozen=True)
class Point:
    """One (cadence, book size, turnover) cell: everything the grid and the CSV print."""

    cadence: str
    names: int
    churn: Decimal
    repicks_per_year: int
    replaced_per_repick: int
    orders: int
    floor_orders: int
    fees_usd: Decimal
    notional_usd: Decimal
    round_trip_rate: Decimal      # fees / slot notional: the 1.035%-style number
    breakeven_per_year: Decimal   # the headline: what it must add to be level with doing nothing
    breakeven_first_year: Decimal

    @property
    def floor_share(self) -> Decimal:
        """The share of orders that paid the floor rather than the rate."""
        if self.orders == 0:
            return _ZERO
        return (Decimal(self.floor_orders) / Decimal(self.orders)).quantize(_EIGHT)

    @property
    def orders_per_year(self) -> int:
        return 2 * self.replaced_per_repick * self.repicks_per_year


def price_one(
    cadence: str,
    names: int,
    churn: Decimal,
    *,
    years: int = YEARS,
    usd_idr: Decimal = USD_IDR,
    growth: Decimal = _ZERO,
) -> Point:
    """Price one book shape over ``years`` of the owner's funding. Writes nothing, reads nothing.

    The loop walks every re-pick EVENT rather than every month, because the fee depends on the
    cadence and the equity depends on the calendar, and only an event-by-event walk gets both
    right at once. At event ``k`` the elapsed months are ``k x 12 // repicks_per_year``.

    The break-even is the compounded one (plan P4-D7): each event costs ``f`` out of ``E``, so the
    book keeps ``(1 - f/E)``, and the annual return needed to be level with doing nothing is the
    product's reciprocal annualised. There is no extra assumption in it -- in particular no
    assumed return, which is the thing nobody knows yet.
    """
    if cadence not in REPICKS_PER_YEAR:
        raise store.LabError(f"unknown cadence {cadence!r}; expected one of {', '.join(CADENCES)}")
    repicks = REPICKS_PER_YEAR[cadence]
    replaced = replaced_names(names, churn)
    if replaced == 0:
        raise store.LabError(f"a turnover of {churn} replaces no names, so there is no fee to price")

    fees = _ZERO
    notional = _ZERO
    orders = 0
    floor_orders = 0
    survival = _ONE
    survival_year_one = _ONE
    for k in range(repicks * years):
        equity = equity_usd((k * 12) // repicks, usd_idr=usd_idr, growth=growth)
        slot = slot_usd(equity, names)
        buy, sell = round_trip(slot)
        event = (buy.total + sell.total) * replaced
        if event >= equity:
            raise store.LabError(
                f"a {cadence} re-pick of a {names}-name book at turnover {churn} costs "
                f"${event} out of ${equity} in one go, which is not a book but a bonfire; "
                f"this report cannot price it"
            )
        fees += event
        notional += slot * replaced
        orders += 2 * replaced
        if floor_binds(slot):
            floor_orders += 2 * replaced
        survival *= _ONE - event / equity
        if k < repicks:
            survival_year_one *= _ONE - event / equity

    breakeven = ((_ONE / survival) ** (_ONE / Decimal(years)) - _ONE).quantize(_EIGHT)
    breakeven_one = (_ONE / survival_year_one - _ONE).quantize(_EIGHT)
    return Point(
        cadence=cadence,
        names=int(names),
        churn=churn,
        repicks_per_year=repicks,
        replaced_per_repick=replaced,
        orders=orders,
        floor_orders=floor_orders,
        fees_usd=fees.quantize(CENT),
        notional_usd=notional.quantize(CENT),
        round_trip_rate=(fees / notional).quantize(_EIGHT),
        breakeven_per_year=breakeven,
        breakeven_first_year=breakeven_one,
    )


# --------------------------------------------------------------------------- the floor, explicitly


@dataclass(frozen=True)
class FloorRow:
    """One month of the owner's funding ramp at one book size: does the floor still win?"""

    month: int
    names: int
    equity_usd: Decimal
    slot_usd: Decimal
    buy_fee: Decimal
    sell_fee: Decimal
    round_trip_rate: Decimal
    floor: bool


def floor_table(
    names: Sequence[int],
    *,
    months: int = FLOOR_MONTHS,
    usd_idr: Decimal = USD_IDR,
    growth: Decimal = _ZERO,
) -> tuple[FloorRow, ...]:
    """The first ``months`` of the funding ramp, per book size: slot, both fees, and the floor.

    This is the part a single average would hide. The owner's book opens small enough that the
    ``$0.10`` minimum beats the 0.2% rate, and then it does not, and the month it stops depends on
    how many names the book holds. Printing the ramp is the only honest way to show a rate that
    changes by a factor of nearly two in three months.
    """
    out: list[FloorRow] = []
    for n in names:
        for m in range(int(months)):
            equity = equity_usd(m, usd_idr=usd_idr, growth=growth)
            slot = slot_usd(equity, n)
            buy, sell = round_trip(slot)
            out.append(FloorRow(
                month=m,
                names=int(n),
                equity_usd=equity,
                slot_usd=slot,
                buy_fee=buy.total,
                sell_fee=sell.total,
                round_trip_rate=((buy.total + sell.total) / slot).quantize(_EIGHT),
                floor=floor_binds(slot),
            ))
    return tuple(out)


# --------------------------------------------------------------------------- the whole grid


@dataclass(frozen=True)
class Sweep:
    """Every priced cell, plus the floor ramp, plus enough provenance to reproduce it."""

    cadences: tuple[str, ...]
    names: tuple[int, ...]
    churns: tuple[Decimal, ...]
    years: int
    usd_idr: Decimal
    growth: Decimal
    regime_since: date
    points: tuple[Point, ...]
    floor_rows: tuple[FloorRow, ...]

    def of(self, cadence: str) -> tuple[Point, ...]:
        """This cadence's cells, by book size then turnover."""
        return tuple(sorted(
            (p for p in self.points if p.cadence == cadence),
            key=lambda p: (p.names, p.churn),
        ))

    def at(self, cadence: str, names: int, churn: Decimal) -> Point | None:
        for p in self.points:
            if p.cadence == cadence and p.names == names and p.churn == churn:
                return p
        return None

    def control(self) -> Point | None:
        """The lab's own cadence on the roster's own book, at the gentlest turnover swept.

        The baseline every other cell is read against: a cost the lab has already accepted,
        rather than a number picked to make the comparison look good.
        """
        cells = [p for p in self.of(CONTROL_CADENCE) if p.names == ROSTER_NAMES]
        return min(cells, key=lambda p: p.churn) if cells else None

    def cheapest(self, cadence: str) -> Point | None:
        """The least a book can be traded at this cadence: the lowest break-even cell."""
        cells = self.of(cadence)
        return min(cells, key=lambda p: p.breakeven_per_year) if cells else None

    def dearest(self, cadence: str) -> Point | None:
        cells = self.of(cadence)
        return max(cells, key=lambda p: p.breakeven_per_year) if cells else None

    def floor_ends(self, names: int) -> int | None:
        """The first month at which the floor no longer binds for this book size.

        ``0`` means it never binds at all; ``None`` means it still binds at the end of the ramp
        the table covers, which would mean :data:`FLOOR_MONTHS` is too short.
        """
        rows = [r for r in self.floor_rows if r.names == names]
        for r in sorted(rows, key=lambda r: r.month):
            if not r.floor:
                return r.month
        return None


def measure(
    *,
    cadences: Sequence[str] | None = None,
    names: Sequence[int] | None = None,
    churns: Sequence[Decimal] | None = None,
    years: int = YEARS,
    usd_idr: Decimal = USD_IDR,
    growth: Decimal = _ZERO,
    floor_months: int = FLOOR_MONTHS,
) -> Sweep:
    """Price the whole grid. Opens nothing, writes nothing, anywhere."""
    cads = check_cadences(cadences)
    ns = check_names(names)
    chs = check_churns(churns)
    yrs = check_years(years)
    rate = check_usd_idr(usd_idr)
    g = check_growth(growth)
    points = tuple(
        price_one(c, n, ch, years=yrs, usd_idr=rate, growth=g)
        for c in cads for n in ns for ch in chs
    )
    return Sweep(
        cadences=cads,
        names=ns,
        churns=chs,
        years=yrs,
        usd_idr=rate,
        growth=g,
        regime_since=costs.GOTRADE.current.since,
        points=points,
        floor_rows=floor_table(ns, months=floor_months, usd_idr=rate, growth=g),
    )


# --------------------------------------------------------------------------- the report


def _pct(x: Decimal, places: int = 2) -> str:
    return f"{x * 100:.{places}f}%"


def _usd(x: Decimal) -> str:
    return f"${x:,.0f}"


_HEAD: tuple[str, ...] = (
    "cadence", "names", "turnover", "re-picks/yr", "names/re-pick", "orders",
    "fees", "round trip", "floor orders", "break-even/yr", "break-even yr 1",
)

_FLOOR_HEAD: tuple[str, ...] = (
    "month", "names", "equity", "slot", "buy fee", "sell fee", "round trip", "pays the floor",
)


def _cells(p: Point) -> tuple[str, ...]:
    return (
        p.cadence,
        str(p.names),
        _pct(p.churn, 0),
        str(p.repicks_per_year),
        str(p.replaced_per_repick),
        f"{p.orders:,}",
        _usd(p.fees_usd),
        _pct(p.round_trip_rate, 3),
        _pct(p.floor_share, 1),
        _pct(p.breakeven_per_year),
        _pct(p.breakeven_first_year),
    )


def _floor_cells(r: FloorRow) -> tuple[str, ...]:
    return (
        str(r.month),
        str(r.names),
        f"${r.equity_usd:,.2f}",
        f"${r.slot_usd:,.2f}",
        f"${r.buy_fee}",
        f"${r.sell_fee}",
        _pct(r.round_trip_rate, 3),
        "yes" if r.floor else "no",
    )


def _table(head: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    body = [tuple(head), *(tuple(r) for r in rows)]
    widths = [max(len(r[i]) for r in body) for i in range(len(head))]
    out: list[str] = []
    for k, row in enumerate(body):
        out.append("    " + "  ".join(row[i].rjust(widths[i]) for i in range(len(head))))
        if k == 0:
            out.append("    " + "  ".join("-" * w for w in widths))
    return out


def _findings(sweep: Sweep) -> list[str]:
    """The mechanical readings. The prose a human reads is the write-up in docs/backtests/."""
    out = ["findings (mechanical; the write-up is docs/backtests/2026-10-13-chart-model-turnover.md)"]
    control = sweep.control()
    if control is not None:
        out.append(
            f"  the control -- the {CONTROL_CADENCE} cadence the lab already pays for, "
            f"{control.names} names, {_pct(control.churn, 0)} of the book re-picked -- costs "
            f"{_pct(control.breakeven_per_year)} a year"
        )
    for cadence in sweep.cadences:
        if cadence == CONTROL_CADENCE:
            continue
        cheap, dear = sweep.cheapest(cadence), sweep.dearest(cadence)
        if cheap is None or dear is None:
            continue
        out.append(
            f"  {cadence}: the gentlest cell swept ({cheap.names} names, "
            f"{_pct(cheap.churn, 0)}, {cheap.replaced_per_repick} name(s) a re-pick) must add "
            f"{_pct(cheap.breakeven_per_year)} a year just to be level with doing nothing; the "
            f"heaviest ({dear.names} names, {_pct(dear.churn, 0)}) must add "
            f"{_pct(dear.breakeven_per_year)}"
        )
        if control is not None and cheap.breakeven_per_year > control.breakeven_per_year:
            out.append(
                f"    even at its gentlest that is "
                f"{(cheap.breakeven_per_year / control.breakeven_per_year):.1f}x the control"
            )
    for n in sweep.names:
        ends = sweep.floor_ends(n)
        if ends == 0:
            out.append(f"  a {n}-name book never pays the $0.10 floor: its opening slot is already above $47.50")
        elif ends is None:
            out.append(f"  a {n}-name book still pays the floor at the end of the ramp printed above")
        else:
            out.append(f"  a {n}-name book pays the $0.10 floor through month {ends - 1} and not after")
    out.append(
        "  the floor is therefore a transient of the first months; once it is gone a round trip "
        "settles near 0.503% of the slot, and it is THAT rate, multiplied by the cadence, that "
        "decides a short-horizon model"
    )
    return out


def format_report(sweep: Sweep) -> str:
    """The terminal report. Ids and labels are fine here; the owner reads the docs page."""
    out = [
        f"lab turnover -- what Gotrade charges a book for trading often, over {sweep.years} years "
        f"of the owner's real funding plan",
        f"funding: {INITIAL_IDR:,.0f} IDR at the start, +{SCHEDULE.amount_idr:,.0f} IDR on the "
        f"{SCHEDULE.day_of_month}th of every month, at {sweep.usd_idr:,.0f} IDR/USD"
        + (f", compounded at {_pct(sweep.growth)} a year" if sweep.growth else ", no growth assumed"),
        f"fees: sim.costs.GOTRADE's current regime (since {sweep.regime_since}); every order "
        f"priced through sim.costs.fee_parts, a re-pick being one sell plus one buy",
        "report only: no trial row, no moments, no journal entry, no status change; the lab's N "
        "and the test-window looks do not move. A free sweep over this grid is the search the "
        "luck gate exists to charge for, so it informs a decision and is never one: acting on it "
        "means a new method that pre-registers the cadence and pays its trials.",
        "",
        "  the grid",
    ]
    out += _table(_HEAD, [_cells(p) for p in sweep.points])
    out += ["", "  the $0.10 floor, month by month, as the owner's deposits arrive"]
    out += _table(_FLOOR_HEAD, [_floor_cells(r) for r in sweep.floor_rows])
    out += [""] + _findings(sweep)
    return "\n".join(out)


# --------------------------------------------------------------------------- the grid as CSV


CSV_HEAD: tuple[str, ...] = (
    "kind", "cadence", "names", "churn", "month", "repicks_per_year", "replaced_per_repick",
    "orders", "floor_orders", "floor_share", "equity_usd", "slot_usd", "buy_fee", "sell_fee",
    "fees_usd", "notional_usd", "round_trip_rate", "breakeven_per_year", "breakeven_first_year",
    "pays_the_floor",
)


def csv_rows(sweep: Sweep) -> list[list[str]]:
    """The grid and the floor ramp as text rows, header first; every number at full precision."""
    rows: list[list[str]] = [list(CSV_HEAD)]
    for p in sweep.points:
        rows.append([
            "cell", p.cadence, str(p.names), str(p.churn), "",
            str(p.repicks_per_year), str(p.replaced_per_repick), str(p.orders),
            str(p.floor_orders), str(p.floor_share), "", "", "", "",
            str(p.fees_usd), str(p.notional_usd), str(p.round_trip_rate),
            str(p.breakeven_per_year), str(p.breakeven_first_year), "",
        ])
    for r in sweep.floor_rows:
        rows.append([
            "floor", "", str(r.names), "", str(r.month),
            "", "", "", "", "", str(r.equity_usd), str(r.slot_usd), str(r.buy_fee),
            str(r.sell_fee), "", "", str(r.round_trip_rate), "", "",
            "yes" if r.floor else "no",
        ])
    return rows


def write_csv(sweep: Sweep, path: Path) -> Path:
    """Write the grid to ``path`` (parents created). Returns the path written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(csv_rows(sweep))
    return path
```

**Impact:** a new, self-contained pure module. Nothing imports it yet. `ruff` must be clean. The
only non-stdlib imports are `lab.store` (for `LabError`, exactly as `name_count.py` does — the
module never connects), `paper.capital`, `paper.compare`, `sim.costs`, `sim.contributions`,
`sim.model`; all five are import-light and none pulls numpy or the market layer.

---

### Step 2: list the command in `commands/lab.py`'s module docstring

**File:** `engine/src/seer_engine/commands/lab.py:70` (the end of the `names` entry in the
docstring's command list; re-anchor on the quoted text)
**Change:** insert the block below immediately **after** the `lab names` entry, which ends with
`... move` on the line before `    lab survivorship M0069 ...`. The docstring is prose, not
argparse `help=`, so a literal `%` is fine here.

**Code:** insert exactly these lines:

```
    lab turnover [--cadence daily,weekly,monthly] [--names 10,20,30] [--churn 0.25,0.5,1.0]
                 [--years 10] [--usd-idr 17841] [--growth 0] [--csv PATH]
                                    report only: what Gotrade's measured schedule charges a book
                                    for re-picking itself at each cadence, on the owner's real
                                    funding plan. Arithmetic over sim/costs.py's fee_parts: no
                                    backtest, no research store, no model. Prints the annual
                                    return a strategy must add just to be level with doing
                                    nothing, and the month the $0.10 per-order floor stops
                                    binding. No trial row, no moments, no status change: N and
                                    the looks do not move
```

**Impact:** documentation only. **Merge note:** phase 1 does not edit this docstring, but if it
has, re-anchor rather than overwriting its lines.

---

### Step 3: the subparser

**File:** `engine/src/seer_engine/commands/lab.py:351` — immediately **after** the `names`
subparser's final `s.add_argument("--store", ...)` block (the one whose help ends
`"none -- point this at a checkout that does rather than rebuilding it"`) and **before**
`    s = sub.add_parser(\n        "regime",`.
**Change:** insert the block below.

Every literal `%` in a `help=` string is written `%%`: argparse runs `help=` through
%-interpolation (`HelpFormatter._expand_help`) and a bare `%` makes `lab --help` die.
`description=` is **not** interpolated and keeps single `%`. The comment below says so in place,
matching the two existing comments in this file.

**Code:**

```python
    s = sub.add_parser(
        "turnover",
        # `$0.10` is safe but every `%` below is doubled: argparse runs each `help=` through
        # %-interpolation (HelpFormatter._expand_help), so a bare `%` is read as a format spec
        # and `lab --help` dies. `description=` is NOT interpolated and must stay single. Same
        # rule as the `costs` and `exposure` parsers above.
        help="report only: what Gotrade charges a book for re-picking itself, by cadence",
        description=(
            "Price a book shape -- how many names, how often it is re-picked, what share of it "
            "turns over each time -- against sim/costs.py's measured Gotrade schedule, over the "
            "owner's real funding plan (10,000,000 IDR at the start, +5,000,000 IDR on the 25th "
            "of every month). Arithmetic, not a backtest: it builds no model, opens no research "
            "store and runs no simulator, and every order goes through sim.costs.fee_parts with "
            "a re-pick counted as one sell plus one buy. Prints, per cell, the fees paid, the "
            "share of orders that paid the $0.10 trading-fee floor rather than the 0.2% rate, "
            "the round-trip cost as a share of a slot, and the annual return the strategy must "
            "add just to be level with doing nothing. Also prints the floor month by month as "
            "the owner's deposits arrive, because the floor's bite shrinks as the book grows and "
            "a single average would hide that. Records no trial, so the lab's N and the "
            "test-window looks do not move; the test window is never read. This prices a "
            "CADENCE, not a name count: the owner's standing instruction is that a name count is "
            "tested on the merits and never on fee grounds."
        ),
    )
    s.add_argument(
        "--cadence", default=None, metavar="daily,weekly,monthly",
        help="the re-pick cadences to price (default: all three). sim.rules offers these and no "
             "others, so these are the only horizons there are",
    )
    s.add_argument(
        "--names", default=None, metavar="10,20,30",
        help="the book sizes to price (default: 10,20,30). This axis is here because the "
             "per-order floor depends on slot size, NOT because a name count is being chosen",
    )
    s.add_argument(
        "--churn", default=None, metavar="0.25,0.5,1.0",
        help="the share of the book replaced at each re-pick, in (0, 1] (default: 0.25,0.5,1.0). "
             "1.0 means the whole book is swapped every time",
    )
    s.add_argument(
        "--years", type=int, default=None, metavar="N",
        help="how many years of the funding plan to price (default: 10, the design's own bar)",
    )
    s.add_argument(
        "--usd-idr", default=None, metavar="17841",
        help="rupiah per dollar for the owner's deposits (default: 17841, the rate the frozen "
             "production book started at and the rate `lab names` was measured at)",
    )
    s.add_argument(
        "--growth", default=None, metavar="0.10",
        help="compound the deposit path at this annual rate (default: 0). Zero is the "
             "conservative reading -- a book that earns nothing keeps the smallest slots and so "
             "pays the floor the longest. The knob is for checking the answer does not hinge on "
             "it; measured, it does not",
    )
    s.add_argument(
        "--csv", type=Path, default=None, metavar="PATH",
        help="also write the grid and the floor ramp to PATH as CSV, at full precision",
    )
```

**Impact:** `lab turnover --help` renders; `lab --help` still renders (the `%%` rule). No `--store`
flag, which is itself the signal that this command loads nothing.

---

### Step 4: the handler

**File:** `engine/src/seer_engine/commands/lab.py:2039` — immediately **after** `_names` returns
(`    log.info("lab names: %d runs done (%.1fs)", ...)` / `    return 0`) and **before**
`def _comparability_warnings(conn, bench_n, rows, wanted) -> list[str]:`.
**Change:** insert the handler below. `time`, `Path`, `log` and `store` are already imported at the
top of this file; add no imports.

**Code:**

```python
def _turnover(conn, args) -> int:
    """``lab turnover``: what Gotrade charges a book for trading often. Report only.

    Every refusal that needs no arithmetic -- a bad cadence, a turnover outside (0, 1], a
    nonsensical horizon or rate -- is made first, so a typo costs nothing. Then
    ``turnover.measure`` prices the grid, which is pure arithmetic over ``sim.costs.fee_parts``:
    no research store is opened and no simulator runs, which is the whole point of the item this
    answers -- the number arrives before the model is built, not after.

    Nothing is written to the lab database. N and the test-window looks are printed before and
    after so the invariant is visible on the terminal, not merely asserted in a test.
    """
    from seer_engine.lab import turnover

    cadences = turnover.check_cadences(args.cadence)
    names = turnover.check_names(args.names)
    churns = turnover.check_churns(args.churn)
    years = turnover.check_years(args.years)
    usd_idr = turnover.check_usd_idr(args.usd_idr)
    growth = turnover.check_growth(args.growth)
    n_before = store.dev_trial_count(conn)
    looks_before = store.test_looks(conn)
    t0 = time.perf_counter()
    sweep = turnover.measure(
        cadences=cadences, names=names, churns=churns,
        years=years, usd_idr=usd_idr, growth=growth,
    )
    print(turnover.format_report(sweep))
    if args.csv is not None:
        written = turnover.write_csv(sweep, Path(args.csv))
        print(f"\ngrid written to {written}")
    print(
        f"\nnothing was recorded. Lab N (dev trials): {n_before} before, "
        f"{store.dev_trial_count(conn)} after; test-window looks used: {looks_before} before, "
        f"{store.test_looks(conn)} after. No journal entry, so seertrade.site/sera is unchanged "
        f"and `lab stage` is not needed."
    )
    log.info("lab turnover: %d cells priced (%.1fs)", len(sweep.points), time.perf_counter() - t0)
    return 0
```

**Impact:** the "nothing was recorded" sentence is byte-for-byte the one `_names` prints, so the
output contract is the lab's existing one and the tests can assert the same strings.

---

### Step 5: the dispatch row

**File:** `engine/src/seer_engine/commands/lab.py:2646` — the `_HANDLERS` dict, in the
`"names": _names,` line's block.
**Change:** insert one row immediately after `"names": _names,`:

```python
    "turnover": _turnover,
```

so that region reads:

```python
    "costs": _costs,
    "names": _names,
    "turnover": _turnover,
    "survivorship": _survivorship,
```

**Impact:** `lab turnover` dispatches. **Merge note:** the index and the analysis call this table
`COMMANDS`; it is `_HANDLERS` in the source.

---

### Step 6: the tests

**File:** `engine/tests/test_lab_turnover.py` (new)
**Change:** create it with exactly the content below. Sixteen tests; what each proves is in its
name and its docstring.

**Code:**

```python
"""``lab turnover``: pricing a book shape against Gotrade's schedule. Report only, N never moves.

The two properties this file exists to defend. First, the arithmetic is the SIMULATOR'S: every
order goes through ``sim.costs.fee_parts``, a re-pick is a sell plus a buy, and the numbers
reproduce the ones ``lab/name_count.py``'s docstring already put on the record -- so the lab can
never hold two different answers to "what does an order cost". Second, the command RECORDS
NOTHING: it is a free sweep over a grid, which is exactly the search the luck gate exists to
charge for, so it may inform a decision and may never be one.
"""

from __future__ import annotations

import ast
from decimal import Decimal as D
from pathlib import Path

import pytest

from seer_engine import cli
from seer_engine.backtest import runner as backtest_runner
from seer_engine.lab import store, turnover
from seer_engine.lab.seed import seed
from seer_engine.paper.compare import SESSIONS_PER_YEAR
from seer_engine.sim import costs
from seer_engine.sim.contributions import OWNER_MONTHLY
from seer_engine.sim.model import q
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE


@pytest.fixture()
def lab(tmp_path):
    path = tmp_path / "lab.sqlite"
    conn = store.connect(path)
    seed(conn)
    yield conn, path
    conn.close()


def _untouched(conn):
    """Everything `lab turnover` must leave exactly as it found it -- insights included."""
    return (
        store.dev_trial_count(conn),
        store.test_looks(conn),
        conn.execute("SELECT count(*) FROM trials").fetchone()[0],
        conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0],
        conn.execute("SELECT count(*) FROM insights").fetchone()[0],
        conn.execute("SELECT count(*) FROM method_amendments").fetchone()[0],
        tuple(tuple(r) for r in conn.execute(
            "SELECT id, status, verdict, source_sha FROM methods ORDER BY id")),
    )


# ---- the arithmetic is the simulator's --------------------------------------------------------


def test_the_opening_round_trip_reproduces_the_recorded_name_count_measurement():
    """1.035% in month 0 and 0.614% by month 3 at twenty names, 0.628% and 0.612% at eleven.

    Those four numbers are on the record in ``lab/name_count.py``'s docstring, measured at
    17,841 IDR/USD. If this module computed anything else, the lab would be holding two
    incompatible answers to the same question and one of them would be wrong.
    """
    cases = {
        (20, 0): D("0.01035"), (20, 3): D("0.00614"),
        (11, 0): D("0.00628"), (11, 3): D("0.00612"),
    }
    for (names, month), expected in cases.items():
        slot = turnover.slot_usd(turnover.equity_usd(month), names)
        buy, sell = turnover.round_trip(slot)
        rate = (buy.total + sell.total) / slot
        assert abs(rate - expected) < D("0.00001"), (names, month, rate)


def test_the_opening_fees_are_the_cents_gotrade_prints():
    """A twenty-name book opens with $28.0253 slots: $0.13 to buy, $0.16 to sell, to the cent."""
    slot = turnover.slot_usd(turnover.equity_usd(0), 20)
    assert slot == D("28.0253")
    buy, sell = turnover.round_trip(slot)
    assert (buy.trading, buy.regulatory, buy.ppn, buy.total) == (D("0.10"), D("0.02"), D("0.01"), D("0.13"))
    assert (sell.trading, sell.regulatory, sell.ppn, sell.total) == (D("0.10"), D("0.04"), D("0.02"), D("0.16"))


def test_a_repick_is_a_sell_plus_a_buy_and_the_sell_is_dearer():
    """P4-D3: the sell pays an uncapped 0.04% the buy does not, at every slot on the ramp."""
    for row in turnover.floor_table([10, 20, 30]):
        assert row.sell_fee > row.buy_fee, row
        assert row.buy_fee == costs.fee_parts("buy", row.slot_usd).total
        assert row.sell_fee == costs.fee_parts("sell", row.slot_usd).total


def test_every_order_in_a_cell_is_priced_through_fee_parts():
    """The cell's total fee equals the hand-computed sum of its own fee_parts calls."""
    p = turnover.price_one("monthly", 20, D("0.50"), years=2)
    expected = D(0)
    for k in range(turnover.REPICKS_PER_YEAR["monthly"] * 2):
        slot = turnover.slot_usd(turnover.equity_usd(k), 20)
        expected += (costs.fee_parts("buy", slot).total + costs.fee_parts("sell", slot).total) * 10
    assert p.fees_usd == expected.quantize(D("0.01"))
    assert p.replaced_per_repick == 10
    assert p.orders == 2 * 10 * 24


def test_ppn_is_never_re_derived_only_called():
    """The module calls fee_parts; it must not reimplement the 11% half-down PPN rounding.

    Grepping is the honest test here: a second implementation of the rounding would be a silent
    second fee schedule, which is exactly what sim/costs.py exists to prevent.
    """
    src = Path(turnover.__file__).read_text(encoding="utf-8")
    body = src.split('"""', 2)[2]  # skip the module docstring, which talks about PPN on purpose
    assert "ROUND_HALF_DOWN" not in body
    assert "0.11" not in body
    assert "ppn" not in body.lower()


# ---- the floor --------------------------------------------------------------------------------


def test_the_floor_boundary_is_forty_seven_dollars_fifty():
    """0.2% of $47.50 is exactly $0.095, which rounds half-up to the $0.10 minimum and ties it."""
    assert turnover.floor_binds(D("47.48")) is True
    assert turnover.floor_binds(D("47.49")) is True
    assert turnover.floor_binds(D("47.50")) is False
    assert turnover.floor_binds(D("47.51")) is False


def test_the_floor_binds_for_two_months_at_twenty_names_and_never_at_ten():
    """P4-D6: the floor is a transient, and how long it lasts depends on the book size."""
    sweep = turnover.measure(cadences=["monthly"], names=[10, 20, 30], churns=[D("1.0")], years=1)
    assert sweep.floor_ends(10) == 0     # the opening slot is $56.05, already above $47.50
    assert sweep.floor_ends(20) == 2     # binds in months 0 and 1 only
    assert sweep.floor_ends(30) == 4     # binds in months 0..3


def test_the_round_trip_rate_falls_as_the_floor_lets_go():
    """The twenty-name ramp goes 1.035% -> 0.737% -> 0.660% -> 0.614% over four months.

    A single static fee number would be wrong by a factor of nearly two across those months,
    which is the reason the floor gets its own table rather than an average.
    """
    rows = [r for r in turnover.floor_table([20]) if r.month < 4]
    rates = [r.round_trip_rate for r in rows]
    assert rates == sorted(rates, reverse=True)
    assert abs(rates[0] - D("0.01035")) < D("0.00001")
    assert abs(rates[3] - D("0.00614")) < D("0.00001")


def test_a_large_slot_pays_the_plain_rate_and_nothing_more():
    """Once the floor is gone a round trip settles near 0.503%: 0.2% a side + 0.04% + PPN."""
    buy, sell = turnover.round_trip(D("1710.00"))
    rate = (buy.total + sell.total) / D("1710.00")
    assert abs(rate - D("0.00503")) < D("0.00001")


# ---- the headline -----------------------------------------------------------------------------


def test_a_daily_chart_model_must_add_more_than_the_market_returns():
    """The number the handover asked for, and the one that kills the idea.

    The cheapest daily book this grid can express -- one name of twenty swapped per session --
    must add about 7% a year to be level with doing nothing, which is roughly what the market
    itself returns. A book that genuinely re-picks itself every session must add about 290%.
    """
    cheapest = turnover.price_one("daily", 20, D("0.05"))
    full = turnover.price_one("daily", 20, D("1.00"))
    assert cheapest.replaced_per_repick == 1
    assert abs(cheapest.breakeven_per_year - D("0.0703")) < D("0.0010")
    assert abs(full.breakeven_per_year - D("2.9045")) < D("0.0100")


def test_the_lab_s_own_monthly_cadence_is_the_cheap_control():
    """The control is a cost the lab already pays, not a number chosen to flatter the comparison."""
    assert MONTHLY_HOLD_FRAC_GOTRADE.cadence == turnover.CONTROL_CADENCE
    control = turnover.price_one("monthly", 20, D("0.25"))
    assert abs(control.breakeven_per_year - D("0.0163")) < D("0.0010")
    weekly = turnover.price_one("weekly", 20, D("0.25"))
    assert abs(weekly.breakeven_per_year - D("0.0727")) < D("0.0010")


def test_break_even_rises_as_the_cadence_shortens():
    """Monotone in the only direction it can be: more re-picks, more orders, more fees."""
    be = [turnover.price_one(c, 20, D("0.50")).breakeven_per_year for c in ("monthly", "weekly", "daily")]
    assert be[0] < be[1] < be[2]


def test_the_answer_does_not_hinge_on_assumed_growth():
    """Zero growth is the default and the conservative one; 10% and 20% move it by under 6%."""
    base = turnover.price_one("daily", 20, D("1.00")).breakeven_per_year
    for g in (D("0.10"), D("0.20")):
        grown = turnover.price_one("daily", 20, D("1.00"), growth=g).breakeven_per_year
        assert abs(grown - base) / base < D("0.06")


# ---- purity and provenance --------------------------------------------------------------------


def test_the_module_opens_nothing():
    """Pure: no clock, no randomness, no network, no database, no research store.

    The one file it may touch is the CSV a caller explicitly names, which is why ``csv`` and
    ``pathlib`` are allowed and nothing else is.
    """
    tree = ast.parse(Path(turnover.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not imported & {"random", "time", "sqlite3", "urllib", "requests", "numpy", "os"}
    src = Path(turnover.__file__).read_text(encoding="utf-8")
    body = src.split('"""', 2)[2]
    for banned in ("date.today", "datetime.now", "research.load_store", "store.connect", "print("):
        assert banned not in body, banned


def test_the_funding_plan_is_the_owners_real_one():
    """Not a restatement of it: the same objects the runner and the paper book use."""
    assert turnover.SCHEDULE is OWNER_MONTHLY
    assert turnover.SCHEDULE.amount_idr == D("5000000")
    assert turnover.SCHEDULE.day_of_month == 25
    assert turnover.INITIAL_IDR == backtest_runner.INITIAL_IDR == D("10000000")
    assert turnover.REPICKS_PER_YEAR["daily"] == SESSIONS_PER_YEAR == 252
    assert turnover.equity_usd(0) == q(D("10000000") / turnover.USD_IDR)
    assert turnover.equity_usd(3) == q(D("25000000") / turnover.USD_IDR)


@pytest.mark.parametrize("bad", ["daily,hourly", "", "fortnightly"])
def test_check_cadences_refuses_a_horizon_sim_rules_does_not_offer(bad):
    with pytest.raises(store.LabError):
        turnover.check_cadences(bad)


@pytest.mark.parametrize("bad", ["0", "1.5", "-0.2", ""])
def test_check_churns_refuses_a_turnover_outside_zero_to_one(bad):
    with pytest.raises(store.LabError):
        turnover.check_churns(bad)


def test_check_names_refuses_a_single_stock_or_the_whole_index():
    with pytest.raises(store.LabError):
        turnover.check_names("1")
    with pytest.raises(store.LabError):
        turnover.check_names("500")
    assert turnover.check_names("30,10,10") == (10, 30)
    assert turnover.check_names(None) == turnover.NAMES


# ---- the command records nothing ---------------------------------------------------------------


def test_cli_lab_turnover_reports_without_moving_n(lab, capsys, tmp_path):
    """The whole contract in one test: it prints the grid and the lab is byte-identical after."""
    conn, path = lab
    before = _untouched(conn)
    csv_path = tmp_path / "grid.csv"
    assert cli.main([
        "lab", "--db", str(path), "turnover",
        "--cadence", "daily,monthly", "--names", "20", "--churn", "1.0",
        "--years", "2", "--csv", str(csv_path),
    ]) == 0
    out = capsys.readouterr().out
    assert "lab turnover -- what Gotrade charges a book for trading often" in out
    assert "report only" in out
    assert "nothing was recorded" in out
    assert "`lab stage` is not needed" in out
    assert "the $0.10 floor, month by month" in out
    assert csv_path.exists()
    assert _untouched(conn) == before


def test_cli_refuses_a_bad_cadence_with_exit_2(lab):
    _conn, path = lab
    assert cli.main(["lab", "--db", str(path), "turnover", "--cadence", "hourly"]) == 2
    assert cli.main(["lab", "--db", str(path), "turnover", "--churn", "2.0"]) == 2
    assert cli.main(["lab", "--db", str(path), "turnover", "--years", "0"]) == 2


def test_lab_help_still_formats(capsys):
    """Invariant 11: a literal `%` in any `help=` string makes argparse's help renderer die."""
    with pytest.raises(SystemExit) as e:
        cli.main(["lab", "--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "turnover" in out
    with pytest.raises(SystemExit) as e:
        cli.main(["lab", "turnover", "--help"])
    assert e.value.code == 0
    assert "--cadence" in capsys.readouterr().out
```

**Impact:** 16 test functions (plus 7 parametrised cases). The expected values in
`test_a_daily_chart_model_must_add_more_than_the_market_returns`,
`test_the_lab_s_own_monthly_cadence_is_the_cheap_control` and
`test_the_floor_binds_for_two_months_at_twenty_names_and_never_at_ten` were **measured** against
the real `fee_parts` while this plan was written, at base commit `a737aff`. If one of them fails,
the first suspicion is that `sim/costs.py` gained a regime — **do not adjust the fee schedule**;
re-measure, update the expected value, and say so in the write-up.

---

### Step 7: produce the numbers

Run from the worktree root. **Use a COPY of the lab database**, in the scratchpad, so the shared
`lab/lab.sqlite` is never opened: it migrates on connect even for a read, and phases 3 and 5 may
be writing it from a concurrent session.

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label
mkdir -p /tmp/claude-1000/seer-p4
cp lab/lab.sqlite /tmp/claude-1000/seer-p4/lab.sqlite

PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab \
  --db /tmp/claude-1000/seer-p4/lab.sqlite turnover \
  --csv docs/backtests/2026-10-13-chart-model-turnover-grid.csv \
  | tee /tmp/claude-1000/seer-p4/report.txt
```

That is **the exact command line the write-up must name** (with `--db lab/lab.sqlite` in the
write-up's own text, since that is the default a reader would use). The full default grid is
3 cadences x 3 book sizes x 3 turnovers = 27 cells plus a 42-row floor ramp.

Then prove the real database was untouched — it was never opened, so this is a check, not a fix:

```bash
git status --short lab/ web/data/      # must print nothing
```

If it prints something, a **peer phase** dirtied it, not you: leave it alone, say so in the
commit body, and do not `lab stage` on their behalf. **Do not** run this command against
`lab/lab.sqlite` directly while another phase session may be mid-write.

Optional second run, only if `git status --short lab/ web/data/` was already clean and no peer
session is live, to satisfy the index's exit criterion on the real file:

```bash
sha256sum lab/lab.sqlite
PYTHONPATH=.../engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab turnover --years 1 --names 20 --churn 1.0 --cadence monthly
sha256sum lab/lab.sqlite
git status --short lab/ web/data/      # must print nothing
```

Quote both hashes and the N/looks before-and-after line in the commit body. If the hash moved (a
connect-time migration touch), **do not** hand-fix it: run
`python -m seer_engine lab stage`, check `git status --short`, and commit `lab/lab.sqlite` plus
`web/data/lab.json` **together with a bare `git commit` and no pathspec** (set invariant 7 — a
pathspec commit re-reads the working tree and can pick up a newer database beside an older JSON).

**Expected values** (measured at `a737aff`; the write-up quotes the command's own output, and any
disagreement is the finding):

| cadence | names | turnover | names a re-pick | fees over 10y | round trip | floor orders | break-even/yr |
|---|---|---|---|---|---|---|---|
| daily | 20 | 100% | 20 | $224,230 | 0.516% | 1.7% | **290.45%** |
| daily | 20 | 25% | 5 | $56,057 | 0.516% | 1.7% | 40.47% |
| daily | 20 | 5% (`--churn 0.05`) | 1 | — | — | — | **7.03%** |
| weekly | 20 | 100% | 20 | $46,214 | 0.516% | 1.7% | 32.49% |
| weekly | 20 | 25% | 5 | $11,553 | 0.516% | 1.7% | 7.27% |
| monthly | 20 | 100% | 20 | $10,678 | 0.516% | 1.7% | 6.70% |
| monthly | 20 | 25% | 5 | $2,669 | 0.516% | 1.7% | **1.63%** |

First-year break-evens at 20 names, 100% turnover: daily 443.66%, weekly 42.13%, monthly 8.40%.

The floor ramp at 20 names: month 0 slot $28.03, buy $0.13, sell $0.16, round trip 1.035%, floor
**yes**; month 1 slot $42.04, 0.737%, **yes**; month 2 slot $56.05, 0.660%, **no**; month 3 slot
$70.06, 0.614%, **no**. The floor never binds at 10 names and stops at month 4 for 30.

---

### Step 8: the write-up

**File:** `docs/backtests/2026-10-13-chart-model-turnover.md` (new)
**Change:** write it to the house format of `docs/backtests/2026-10-12-exposure-diagnostic.md` —
read that file first. Headings in order, with the content each must carry:

```markdown
# What a short-horizon chart model would pay Gotrade

**Measured:** 2026-10-13 · **Window:** ten years of the owner's funding plan, forward
**Fees:** `sim/costs.py`'s current Gotrade regime (since 2026-06-16), fitted to 30 of the owner's
own order receipts · **Rate:** 17,841 IDR/USD
**Grid:** [`2026-10-13-chart-model-turnover-grid.csv`](2026-10-13-chart-model-turnover-grid.csv) —
the same rows at full precision
**Command:** `lab turnover --csv docs/backtests/2026-10-13-chart-model-turnover-grid.csv`

## The short answer

<The number, first sentence. The cheapest daily book the owner could run — one name of twenty
swapped per session — must earn 7.0% a year before it has made him a single rupiah, which is
roughly what simply owning the market returns. A model that actually re-picks its book every
session must earn 290% a year. Weekly is 32%. The cadence the lab already trades, on the same
book, costs 1.6%. So the short-horizon chart model is dead on arrival: not because the model
could not learn anything, but because the owner's account is small enough that trading it often
costs more than any plausible edge is worth. No CNN and no LSTM was written, and none needs to
be.>

## Why this was measured instead of built

<The handover's own reasoning: an hour of arithmetic against a schedule we already have, versus
weeks of model code whose answer the arithmetic settles. State that the limit on deep learning
here is signal-to-noise and ~500 names x 20 years of strongly correlated monthly samples, not
capacity — and that this measurement is about the *other* constraint, the fee one, which is the
cheaper one to settle.>

## How it was measured

<The deposit path (10,000,000 IDR + 5,000,000 IDR on the 25th), one FX rate, equal-weight slots,
a re-pick as a sell plus a buy, every order through `fee_parts`. The break-even definition in
plain words: each trade takes a slice out of the account, the slices compound, and the number
quoted is the yearly return that exactly undoes them. State that no return is assumed anywhere —
that is the point.>

## The $0.10 floor, and why it is only the first chapter

<The ramp table at 20 names, months 0-3. The floor binds while a slot is under $47.50, which at
twenty names is the first two months and at thirty the first four, and at ten names never. Quote
`lab names`' own 1.035% and 0.614% and say they reproduce here digit for digit. Then the turn:
once the floor lets go, a round trip settles at 0.503% of the slot — 0.2% a side, the sell's
extra 0.04%, and 11% tax on both — and it is that, multiplied by 252, that does the killing.
Say plainly that the earlier reading which called the floor "the whole answer" was right about
the owner's first two months and wrong about his tenth year.>

## The grid

<The full 27-cell table, as the command printed it. Cadence down, turnover across, break-even in
each cell, with the monthly control marked.>

## What this changes

<1. The short-horizon chart model is not pursued; the handover's item 3 is answered with a "no"
and the reason. 2. Nothing else: the roster's cadence and book size do not move. Quote the
owner's standing instruction verbatim — *"do not plan a name-count reduction on fee grounds; if
the lab tests concentration, test it on the merits"* — and say that this report prices a cadence
and recommends no change to the number of names. 3. If a future method wants a faster cadence, it
must pre-register it and clear a bar this report now puts a number on.>

## What this could not see

<It assumes equal-weight slots and a constant replacement count; a real model would trade in
uneven sizes. It assumes no price impact and no spread, both of which make the answer worse, not
better. It assumes the current fee regime holds, which is what every backtest assumes. It cannot
say whether a chart model would have an edge — only how large that edge would have to be.>

## What was and was not recorded

<Nothing. No trial, no moments, no funding, no status, no journal row. The lab's N and its four
spent test-window looks were printed before and after the run and were equal; quote both numbers.
Say that this is a report and may inform a decision but never be one.>
```

**Rules for the prose:** owner-facing text is plain (set invariant 10) — no method ids, no
digests, no "DSR", no "walk-forward", no code identifiers in the narrative sections. Module and
file names are fine in the header block and in *How it was measured*, the way the exposure
write-up uses them. Every number in the document must come from the command's own output.

**Impact:** R3 is answered on the record, with the number the handover asked for.

---

### Step 9: the todo row

**File:** `.workflows/todos.md`
**Change:** add one task row for this phase only, in the file's existing format, marked done. Mint
your own TaskID; do not touch any other phase's row. Commit it by pathspec with the write-up.

---

## Verification

Run every command from the paths given. **There is no `engine/.venv` in this worktree** — the
interpreter is the main checkout's, and `PYTHONPATH` is mandatory (without it pytest silently
imports the main checkout and tests the wrong code).

**Postgres first** (CI fails a run where the DB tests skip):

```bash
docker start seer-pg 2>/dev/null || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
```

**Lint:**

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label
/home/miftah/seer/engine/.venv/bin/ruff check engine
```
Expected: `All checks passed!` (CI is bugs only: E9 and F, minus F401).

**This phase's tests first:**

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
/home/miftah/seer/engine/.venv/bin/python -m pytest -q tests/test_lab_turnover.py tests/test_lab_name_count.py tests/test_sim_costs.py tests/test_cli.py
```
Expected: all pass, 0 failures. `test_sim_costs.py` and `test_lab_name_count.py` are in the list
because this phase must not have perturbed either.

**Build / full suite:**

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/fold-verdict-and-fall-label/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
/home/miftah/seer/engine/.venv/bin/python -m pytest -q
```
Expected: the suite green, with **the skip count quoted beside the pass count** in the commit
body (e.g. `N passed, M skipped`). A skip count near 385 means `PG_TEST_URL` did not take —
fix that before claiming green.

**Manual check:**

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label
PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab --help | head -40
PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab \
  --db /tmp/claude-1000/seer-p4/lab.sqlite turnover --help
git status --short lab/ web/data/
```
Expected: `lab --help` renders without an argparse `%` crash and lists `turnover`;
`lab turnover --help` shows the seven flags and **no `--store`**; `git status --short lab/
web/data/` prints nothing.

**Exit criteria:**

1. `lab turnover` runs with no `--store`, prints a 27-cell grid and a 42-row floor ramp, and ends
   with `nothing was recorded. Lab N (dev trials): X before, X after; test-window looks used:
   Y before, Y after.` with the two pairs equal.
2. `git status --short lab/ web/data/` is empty after the run (the committed database was never
   opened), or the database was staged with `lab stage` and committed with a bare commit.
3. `docs/backtests/2026-10-13-chart-model-turnover.md` names the command that produced it, states
   plainly that the fee burden **kills** a short-horizon chart model, and quotes the annual return
   such a model must add to be level with doing nothing — the 7.0% floor case and the 290% full
   case — against the lab's 1.6% monthly control.
4. `sim/costs.py` is byte-identical: `git diff --stat -- engine/src/seer_engine/sim/costs.py`
   prints nothing.
5. `commands/lab.py`'s diff touches only the docstring block, the new subparser block, the new
   `_turnover` handler and the one `_HANDLERS` row:
   `git diff -- engine/src/seer_engine/commands/lab.py | grep '^-' | grep -v '^---'` prints
   **nothing** (this phase only adds lines).
6. `ruff` clean; the suite green with the skip count quoted.

---

## Handoffs

- **R1's `method_folds` and the fold verdict (Phase 1).** This phase assumes it has landed and
  touches none of it. If `lab turnover` is ever wanted as a column on a recorded trial, that is a
  new table and a new phase, not this one.
- **The analysis's claim that "the `$0.10` floor is the whole of R3's answer"
  (`docs/analyzer/20261013-082101-K09L_code_analyzer.md:313`)** is, measured, true only for the
  owner's first two months. This phase corrects it **in the write-up's prose**. The analysis
  document itself is a record of what was believed when it was written and is **not edited**.
  Flagging it for the reconciler.
- **A plain-language journal entry about this finding** would be natural, and this phase
  deliberately does not write one: journal rows move nothing about N, but they are database
  writes, and phase 3 owns the lab journal in this set (R4). If the owner wants one, it is a
  follow-up append after phase 3 lands.
- **`sim/costs.py`'s single sell receipt.** The uncapped 0.04% `sell_extra_rate` rests on one
  observation (PLTR, 2026-10-07) and is deliberately conservative. Every sell this phase prices
  inherits that. It is noted in the write-up's *What this could not see* and **not changed**.
- **A `turnover` column on `/sera`.** Out of scope: `web/` is untouched in this set and
  `store.SNAPSHOT_VERSION` stays at 5 (set Decision D3).
- **Price impact and spread.** Not modelled, and modelling them would need the research store,
  which would make this a backtest. Noted in the write-up; a separate measurement if ever wanted.

---

## Rollback

This phase is two commits (code+tests, then write-up+todo), each bounded by an explicit pathspec,
so `git revert <sha>` backs it out — newest first. Reverting leaves the lab database and every
recorded row untouched, because this phase never wrote one.

`git reset --hard`, `git clean`, `git checkout .` and every bare-path form are **banned** in this
worktree: it and its git index are shared by concurrent phase sessions and a peer's work in
progress lives in the same tree.

---

## Commit sequence

Set invariant 8: `git add -- <newfile>` first for each new file, then `git commit` with `-m`
**before** `--`, then verify.

```bash
cd /home/miftah/.worktrees/seer/fold-verdict-and-fall-label

# 1. the code and its tests
git add -- engine/src/seer_engine/lab/turnover.py engine/tests/test_lab_turnover.py
git commit -m "lab: price a book's turnover against Gotrade's measured schedule (lab turnover)

A pure module plus a report-only subcommand: given how many names a book holds, how
often it is re-picked and what share of it turns over, it prices every order through
sim.costs.fee_parts and reports the annual return the strategy must add just to be
level with doing nothing. No backtest, no research store, no model, no database write.

Reproduces lab/name_count.py's recorded figures digit for digit: 1.035% a round trip
in month 0 of the owner's funding plan at twenty names, 0.614% by month 3.

Suite: <N> passed, <M> skipped. ruff clean.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  -- engine/src/seer_engine/lab/turnover.py \
     engine/src/seer_engine/commands/lab.py \
     engine/tests/test_lab_turnover.py

git show --stat HEAD   # exactly the three files above
git log -1             # your own message

# 2. the write-up and the grid
git add -- docs/backtests/2026-10-13-chart-model-turnover.md \
           docs/backtests/2026-10-13-chart-model-turnover-grid.csv
git commit -m "docs: a short-horizon chart model would pay 7% a year at its cheapest, 290% at full churn

Answers handover 2026-10-13 section 2 item 3 with a number instead of a model. At the
owner's funding, the least a daily book can be traded -- one name of twenty swapped a
session -- must earn 7.0% a year before it has made him anything; re-picking the whole
book daily needs 290%. The monthly cadence the lab already trades costs 1.6%.

The \$0.10 per-order floor binds only for the owner's first two months at twenty names
and never at ten; after that the plain rate, 0.503% a round trip, is what does the
killing at 252 round trips a year.

Nothing recorded: N and the four spent test-window looks were equal before and after.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" \
  -- docs/backtests/2026-10-13-chart-model-turnover.md \
     docs/backtests/2026-10-13-chart-model-turnover-grid.csv \
     .workflows/todos.md

git show --stat HEAD
```

If you dispatch the `pusher` subagent, put this in its prompt **verbatim**:

> This worktree and its git index are shared by concurrent phase sessions. Commit by explicit
> pathspec only, with `-m` BEFORE `--`. `git reset --hard`, `git clean`, `git checkout .`,
> `git add -A`, `git add .` and every bare-path form are BANNED. Do not stage, unstage or revert
> anything you were not given a path for. End the commit message with exactly
> `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` — do not substitute your own model name.

---

## Assumptions

- **Phase 1 has landed** before a line of this phase is written: `store.SCHEMA_VERSION == "7"`,
  `hardgate.fold_verdict` exists, the committed `lab/lab.sqlite` is at v7 and committed, and
  `commands/lab.py` already carries phase 1's `_run`/`_show` edits. All `commands/lab.py` line
  numbers in this plan are pre-phase-1; anchor on the quoted text.
- Phase 1 does **not** add a `turnover` subparser, a `_turnover` handler or an
  `engine/src/seer_engine/lab/turnover.py`. If it has, stop and report rather than merging two
  versions.
- Phases 3 and 5 own every write to `lab/lab.sqlite` and `web/data/lab.json` in this set. This
  phase never stages either unless its own run dirtied the file, and then only by
  `lab stage` + a bare commit.
- `sim/costs.py` is unchanged from `a737aff`. Every expected value in Step 6 and Step 7 was
  measured against it.
