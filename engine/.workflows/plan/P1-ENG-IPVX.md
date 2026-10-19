> Adopted from `docs/plans/GATE_PRICE_BAND_PLAN.md` phase 1. Source: `.workflows/plan/gate-price-band/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: M0258: pre-register, run and record the banded gate

**Plan set:** `GATE_PRICE_BAND_PLAN.md`
**Analysis:** `docs/analyzer/20261019-135550-B4K2_code_analyzer.md`
**Satisfies:** R1, R2, R3, R4, R5, R6 — the owner gets a measured answer to *is a price band around
the SPY-200 gate worth anything on a book that holds stocks, and does that worth depend on how
often the gate is read?*, recorded in the lab, with no test-window look spent.
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab`

---

## Goal

After this phase the lab holds one new pre-registered method, **M0258**, whose six recorded dev
trials put a price band around the SPY 200-day gate on `M0072-Z2-RAWRANK`'s stock book and cross
the band against the cadence the gate is read at. The lab can then say, from paired differences on
one book rather than by inference across its history, whether the 2026-10-19 gate-band finding
survives contact with a book that holds stocks — and whether what that study measured was the band
or the daily reading. Two re-runnable study files, an analysis, a verdict, at least one journalled
insight and at least one queued idea are committed beside it, and `web/data/lab.json` agrees with
`lab/lab.sqlite` row for row.

---

## Named invariants

A step that breaks one of these is not done. Each is checkable.

- **I1 — Import only, never edit.** `m0101.py`, `m0084.py`, `m0072.py`, `m0063.py`,
  `strategies/f_factor.py`, `sim/rules.py`, `lab/hardgate.py` and `lab/control_shape.py` are read
  and imported, never modified. `band_on` is the band the lab priced twice, byte for byte.
- **I2 — No shared params dataclass gains a field.** `FactorParams`, `JumpParams` and `ZParams`
  are untouched. Adding a field to any of them moves every recorded config digest in the lab.
  The band lives in a NEW dataclass (`BandParams`) behind a NEW allocator id (`M0258`). This is R5.
- **I3 — `lookback` equals the host's exactly.** `BANDED.lookback(p) == ZJUMP.lookback(p.book)`,
  measured at **253**. `m0101.SCAN` is never added to it. This is what makes M0258's dev window
  start `1996-01-03` like M0072's, so the `b = 0` arm is a reproduction and not an approximation.
- **I4 — The method file is pure.** No clock, randomness, network, file or print; it reads only
  bars dated `<= data_date`. `test_method_source_is_pure` enforces it.
- **I5 — The commit is the pre-registration.** `hypothesis` and `expected_failure` are written and
  committed *before* `lab run` sees a number, and are never edited afterwards.
- **I6 — No test-window look.** `lab test` is never invoked, not even with `--dry-run`.
  `lab status` must still read **test-window looks used: 4** at the end.
- **I7 — Exactly six candidates.** `method.MAX_VARIANTS = 6`.
- **I8 — Never judge a `lab` command by a piped exit code.** Redirect to a file and echo the
  command's own `$?`. A `grep`/`head` owns the pipeline's status, and this shell prints a spurious
  `setValueForKeyFakeAssocArray:27: command not found: _encode` line at startup.
- **I9 — Never weaken a test to make the method pass.** Fix the method.
- **I10 — No recorded row moves.** `test_every_recorded_configuration_still_digests_to_its_recorded_digest`
  and `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` stay green.
- **I11 — `lab stage` targets the MAIN checkout**, and the staged pair is committed **from the
  index** (`git commit` with no pathspec). A pathspec re-reads the working tree and defeats
  `lab stage`.
- **I12 — No literal `%` reaches argparse.** Nothing this phase writes is an argparse help string,
  so simply do not introduce one.

---

## Interface Contract

**Deletes:** none.
**Renames:** none.
**Creates:**
- `seer_engine.lab.methods.m0258_gate_price_band.BandParams` (`engine/src/seer_engine/lab/methods/m0258_gate_price_band.py`)
- `…m0258_gate_price_band.BandedGateAllocator` with `id = "M0258"` (same file)
- `…m0258_gate_price_band.BANDED`, `BOOK`, `MAX_BAND`, `ADDED`, `METHOD` (same file)
- `engine/tests/test_lab_m0258_band.py`
- `docs/backtests/2026-10-19-gate-band-cadence.py`
- `docs/backtests/2026-10-19-gate-band-cadence.md`
- `docs/plans/HANDOVER_20261019-the-gate-price-band.md`
- six `trials` rows, one `method_folds` row, one `methods` row, two `ideas_seen` rows, ≥1
  `insights` row, ≥1 idea row — all append-only, written by `lab run` / `lab insight` / `lab idea`
- regenerated `web/data/lab.json`

**Signature changes:** none.
**Requires (from earlier phases):** none — this is the only phase.
**Leaves alone (owned by nobody; frozen):**
`engine/src/seer_engine/lab/methods/m0101_calm_raisers_banded_switch.py`,
`…/m0084_trend_switch_price.py`, `…/m0072_standardised_earnings_jump.py`,
`…/m0063_earnings_day_jump.py`, `engine/src/seer_engine/strategies/f_factor.py`,
`engine/src/seer_engine/sim/rules.py`, `engine/src/seer_engine/lab/hardgate.py`,
`engine/src/seer_engine/lab/control_shape.py`, every recorded row in `lab/lab.sqlite`,
the test window.

---

## Files

| File | Action | What changes |
|---|---|---|
| `docs/backtests/2026-10-19-gate-band-cadence.py` | create | the re-runnable cadence grid the hypothesis cites |
| `docs/backtests/2026-10-19-gate-band-cadence.md` | create | the writeup; corrects the framing of the gate-band study and insight 464 |
| `engine/src/seer_engine/lab/methods/m0258_gate_price_band.py` | create | the overlay allocator (`id = "M0258"`), `BandParams`, `METHOD` with six candidates |
| `engine/tests/test_lab_m0258_band.py` | create | the five properties the generic contract test cannot see |
| `lab/lab.sqlite` (main checkout) | append | six trials, one folds row, method row, seen keys, insight, idea, analysis, verdict |
| `web/data/lab.json` (main checkout) | regenerate | `lab stage` |
| `docs/plans/HANDOVER_20261019-the-gate-price-band.md` | create | the next session's brief |

---

## What was measured for this plan, so no step is guesswork

Every number below was read off the running system in the course of writing this plan, not
estimated. Quote them; do not re-derive them.

**Recorded rows** (`lab/lab.sqlite`, read-only `sqlite3`, `window = 'dev'`, joined to
`trial_funding`).

**Quote the money-weighted return and nothing else as a headline.** Every one of these books is
**funded** — the owner tops it up by 5,000,000 IDR on the 25th of each month, 237 or 260 deposits
over these windows — and `backtest/metrics.py` says of the curve-shape columns that they are
*"deliberately left as they are ... they are not returns at all"*. `trials.total_return` is a
**fraction** (`last/first - 1`), so the lab's own renderer prints `M0084-MONTHLY` as
`return +39319.3%`; and `trials.cagr` is the funded CAGR, which the lab's standing note calls a
lie. The honest number is `trial_funding.mwr`, the money-weighted return, which `lab show`
surfaces as **"your money earned"**, beside `spy_tr_mwr` — the *same deposits* into SPY. The
curve-shape column is dropped here rather than carried with a disclaimer.

| trial | rules | funded %/yr | SPY, same deposits | worst fall | trades | turnover |
|---|---|---|---|---|---|---|
| `M0084-MONTHLY` (bare gate, SPY only) | monthly | **9.13** | 7.69 | 18.89 | 11 | 0.826 |
| `M0084-BAND3-M` (3% band, SPY only) | monthly | 8.73 | 7.69 | **20.69** | 9 | 0.826 |
| `M0084-WEEKLY` (bare gate, SPY only) | weekly | 4.35 | 7.69 | **33.13** | 40 | 3.383 |
| `M0084-BAND3-W` (3% band, SPY only) | weekly | **7.78** | 7.69 | **18.92** | 10 | 0.861 |
| `M0101-CTRL` (bare gate, calm-raisers stock book) | monthly | **10.62** | 7.19 | 18.71 | 528 | 4.780 |
| `M0101-BAND-3` (3% band, same stock book) | monthly | 10.44 | 7.19 | **20.39** | 525 | 4.727 |
| `M0101-BAND-5` (5% band, same stock book) | monthly | 10.10 | 7.19 | 20.39 | 516 | 4.620 |
| `M0072-Z2-RAWRANK` (**the host book**) | monthly | **12.33** | 7.19 | 23.80 | 1208 | 6.529 |

Windows: the `M0084` rows run 1994-01-28 → 2015-10-16, the rest 1996-01-03 → 2015-10-16, which is
why SPY's own deposit-matched figure differs between the two blocks. `M0072-Z2-RAWRANK` also
records exposure 0.695, PF 1.98, MAR 0.518 and DSR 0.914 at its run-date N. `lab status` today
reads it **Promotable now**: `MAR 0.52  DSR 0.928 at N=162 (methods)  3 of 4 folds;
M0072-Z2-RAWRANK alone 3 of 4 folds; kin clean`.

### The difference-in-differences this method proposes is ALREADY RECORDED on SPY alone

This is the single strongest prior M0258 has, it is in money, and nobody has ever named it. From
the table above, the band minus the bare gate, at each cadence:

| gate read | band − bare gate, money | band − bare gate, worst fall |
|---|---|---|
| **monthly** | **−0.40 pts/yr** | **1.80 points deeper** |
| **weekly** | **+3.42 pts/yr** | **14.22 points shallower** |
| **the swing** | **3.82 points, from cadence alone** | **16.02 points** |

(Those differences are taken at full precision from `trial_funding.mwr`; differencing the
two-decimal table above instead gives +3.43, 14.21 and 3.83 — the same facts, one hundredth apart.)

**And the predicted null has already been observed once, on a book that holds stocks.** On
`M0101`'s calm-big-raisers book at monthly cadence the band *costs* **0.18 pts/yr** at 3% and
**0.52 pts/yr** at 5%, and falls **1.68 points deeper** at both. That is exactly the shape M0258's
monthly pair is predicted to show, on a different book.

**The brief's premise about turnover is a weekly fact, not a monthly one — and it matters.** The
handover says *"the band cuts turnover sharply, so a control drawn at the bare gate's trade count
is mis-shaped by construction"*. Measured, the band cut turnover **only** at weekly cadence: 0.861
against 3.383 on the weekly SPY book, a 75% cut. On **both** monthly books it cut essentially
nothing — 4.727 against 4.780 on the stock book (1.1%) and 0.826 against 0.826 on SPY (0.07%),
with trades 525 against 528 and 9 against 11. So M0258's four monthly arms should be expected to
differ from one another in shape by **well under 1%**, which means (a) any difference between them
is the gate's timing and not its cost, and (b) a drawn control matched on the bare gate's trade
count would not in fact have been mis-shaped at monthly cadence — the ladder is still the better
control, for the reasons in Decision D1, but not for the reason the brief gives.

**The lab's state, read on a throwaway copy** (`lab status`, `lab control`, `lab next-id`,
`lab seen --find`):
- `dev trials 824 · test-window looks used 4 · methods 271 · insights 464`
- `N the luck gate judges at (policy methods): 162` — **quote N = 162, not 271**
- next free id: **M0258**
- `lab control M0101 M0084 M0245 M0197 M0072` prints exactly one row across all five methods:
  `M0245-FALL63  dose-response  —  —  —  —  not-checked`, and *"every control arm shown matches
  the shape of the arm it controls"*. No gate method in the lab has ever been near a D17 refusal.
- `concept:gate-cadence-dose-response` → 0 rows. `concept:banded-gate-on-an-event-book` → 0 rows.
  `concept:banded-trend-switch` → **1 row, held by M0101.** Both new keys are free; do not reuse
  M0101's.
- `lab seen --find "gate cadence"` → nothing, exit 0.

**`control_shape.py`, quoted from the source**, because the rationales below are written against it:

```python
DOSE_MARKERS: tuple[str, ...] = (
    "dose-response",             # 4: M0230-C70, M0230-C30, M0241-STALE, M0245-FALL63
    "dose:",                     # 1: M0243-NEAR20-T3 ("A stricter dose:")
    "and not since",             # 1: M0241-STALE
    "and none since",            # 1: M0244-STALE30
    "does the date do any work",  # 1: M0244-STALE30
    "on the date itself",        # 1: M0241-STALE
)
DRAW_MARKERS: tuple[str, ...] = (
    "placebo",      # 18
    "hash-drawn",   # 7
    "hash order",   # 34
)
```

`kind_of` lowercases the rationale and tests **dose before draw**. So: **no rationale written in
this phase may contain `placebo`, `hash-drawn` or `hash order` in any case**, and every ladder rung
carries the literal phrase `dose-response`.

**`hardgate.py` D17, *What it does not do*, quoted:** *"It does not refuse a method with no
control arm — most of the lab has none, and the rule makes no claim about a book nobody drew a
control for."* And: *"A dose-response arm is not a control. … Both are classified dose-response,
carry the verdict `not-checked`, hold no ratio at all, and this rule never reads them."* That is
Decision D1 verified in code, and it is why R4 is satisfied by the ladder and not by a drawn arm.

**The screen the run is judged against** (`backtest/metrics.py`, `backtest/dev.py:445`):
dev eligibility uses `DEV_MAX_DRAWDOWN = 0.50`, **not** the real-money `MAX_DRAWDOWN = 0.25`,
plus `beats SPY TR`, `PF >= MIN_PROFIT_FACTOR`, `>= 100 trades` and `DSR >= 0.90`. Do not collapse
the two drawdown numbers.

**Rule presets, diffed field by field** (`dataclasses.fields`):
`MONTHLY_HOLD_FRAC_GOTRADE` and `m0063.WEEKLY_HOLD_FRAC_GOTRADE` differ in exactly **two** fields —
`id` (`monthly-hold-frac-gotrade` → `weekly-hold-frac-gotrade`) and `cadence` (`monthly` →
`weekly`). `MONTHLY_HOLD_FRAC_GOTRADE.id` is in `sim.rules.PRESETS`; the weekly one is **not**, so
a weekly arm can never be promoted. The cadence axis is therefore clean, and the weekly arms are
diagnostic by design.

**The overlay was prototyped and driven through the real contract kit before this plan was
written.** On `labkit.smoke_market`, with `BOOK = ZParams(JUMP20, z_min=Decimal("2"), rank="raw")`:
- `assert_p4_identity` + `assert_no_lookahead` pass at `band` = 0, 0.015, 0.03 and 0.06, returning
  **16, 16, 16 and 20** non-empty target sets. `ZJUMP` is **not** `MarketAware`, so
  `test_allocator_contract` demands `nonempty > 0`; all four arms clear it.
- `run_candidate` completes for all six arms: `end=2015-10-16`, `snapshots=221`,
  `start=2014-12-03`.
- `BANDED.lookback(p) == ZJUMP.lookback(BOOK) == 253` for every band.
- `band_on(SPY, d, 200, 0.0) == trend_on(history, d, inner)` on **all 473** smoke sessions, 0
  differences, 163 of them reading on.
- The band is genuinely wired in: against `b = 0`, `b = 0.015` differs on 9 sessions, `b = 0.03` on
  22 and `b = 0.06` on 25, of 473.
- `config_digest` is distinct for `(b=0, monthly)`, `(b=0.03, monthly)` and `(b=0, weekly)`.

**The one seam that had to be chosen, and the route that was measured wrong.** `M0072` exposes no
public hook between its gate test and its target builder: `targets` and `targets_prepared` each do
*gate → rows → `_targets`*. The alternative — hand `ZJUMP` a gate-free twin of its params
(`replace(inner, trend=None)`, whose `trend_on` reads True) and gate it ourselves — is **rejected
on the record, not on the lookback**. An earlier draft of this plan justified the rejection by
claiming a `trend=None` twin drops `f_factor.factor_lookback` from 253 to 21; **that claim is
false and was re-measured for this plan**: `factor_lookback`, `jump_lookback`, `ZJUMP.lookback`
and `ZJUMP.symbols` all return exactly the same values on the twin as on `BOOK` (253, 253, 253,
`('SPY',)`). The twin would have run.

The real reason is the record. `config_text` digests `BandParams`, which holds `BOOK` **unmodified**,
so `as_dict()` reports `book.inner.trend = SPY:200` whatever the allocator does internally. An
overlay that secretly ran a `trend=None` twin would record a configuration describing a book it
does not run, and the recorded row is the lab's only permanent artefact. Passing the host's own
params through untouched is what makes "this is M0072's book" a fact rather than a claim that
depends on `trend` being unread elsewhere. So the overlay calls `ZJUMP._targets(...)` directly and
says why in a comment. The private call is safe in a way it would not normally be: `m0072.py` is
frozen against its recorded `source_sha`, so its private surface cannot move under this file. Ruff's selected
rules are `E9` and `F` only (`engine/pyproject.toml`), so the private call is not a lint problem.

---

## Implementation Steps

### Step 0: Environment — set this up once, in every shell

**File:** none (shell)
**Change:** the worktree has no venv and no research store, and `python3.11` does not exist on this
machine. Every command below assumes these four lines have been run in the current shell.
**Code:**
```bash
export WT=/home/miftah/.worktrees/seer/gate-price-band
export MAIN=/home/miftah/seer
export SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite
export SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research
export PYTHONPATH=$WT/engine/src
export PY=/home/miftah/seer/engine/.venv/bin/python
export PYTEST=/home/miftah/seer/engine/.venv/bin/pytest
export RUFF=/home/miftah/seer/engine/.venv/bin/ruff
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
export OUT=/tmp/claude-1000/-home-miftah-seer/m0258
mkdir -p "$OUT"
docker start seer-pg >/dev/null 2>&1 || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
```
**Impact:** `SEER_LAB_DB` points every `lab` command at the shared, committed database in the main
checkout — a worktree's own copy must never be written. `SEER_RESEARCH_STORE` points at the dev
store, which is gitignored and not in a worktree (memory: *research store is not in worktrees*);
never rebuild one, it is 30 minutes for nothing. One CPU core: anything timing-sensitive runs
`pytest -n0`. CI fails if the DB tests skip, so `seer-pg` must be up.

---

### Step 1: `docs/backtests/2026-10-19-gate-band-cadence.py`

**File:** `$WT/docs/backtests/2026-10-19-gate-band-cadence.py` (new file)
**Change:** the re-runnable cadence grid, in the exact register of the committed
`2026-10-19-gate-band-variants.py` beside it — same bars, same 200-bar warmup, same one-session
lag between reading a close and acting on it, same equity and drawdown arithmetic. The only new
machinery is `act_at`, and the file says so. Verified to reproduce the grid in the analysis
document to the digit.
**Code:**
```python
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
    print(f"{how:>10}  {(bc - gc) * 100:+23.2f}  {(gdd - bdd) * 100:+25.1f}")

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
```
**Impact:** adds one study file. Nothing else reads it; it is cited by the method file's docstring
and by the writeup. It takes a few seconds and parses the 129 MB `bars.csv` once.
**Verification of this step:**
```bash
cd "$WT" && "$PY" docs/backtests/2026-10-19-gate-band-cadence.py > "$OUT/cadence.txt" 2>&1; echo "RC=$?"
cat "$OUT/cadence.txt"
```
The grid must print, to the digit:

| signal | acts | whole | wDD | 09-15 | inv | flips |
|---|---|---|---|---|---|---|
| bare gate | daily | 6.05% | −28.7% | 6.96% | 71.6% | 152 |
| bare gate | weekly | 5.51% | −34.6% | 5.82% | 70.8% | 80 |
| bare gate | monthly | 9.08% | −19.0% | 10.07% | 71.9% | 22 |
| band 1.5% | daily | 7.35% | −19.5% | 9.44% | 70.8% | 46 |
| band 1.5% | weekly | 6.95% | −24.5% | 8.42% | 70.9% | 46 |
| band 1.5% | monthly | 7.94% | −19.0% | 10.07% | 70.4% | 32 |
| band 3% | daily | 7.87% | −20.3% | 8.83% | 72.4% | 20 |
| band 3% | weekly | 8.03% | −19.0% | 8.84% | 72.4% | 20 |
| band 3% | monthly | 8.96% | −20.7% | 9.46% | 72.4% | 18 |
| band 6% | daily | 7.91% | −20.4% | 7.02% | 70.3% | 12 |
| band 6% | weekly | 8.15% | −21.8% | 6.91% | 70.4% | 12 |
| band 6% | monthly | 7.86% | −20.7% | 6.72% | 69.7% | 12 |

and the paired differences `daily +1.82 / +8.4`, `weekly +2.52 / +15.6`, `monthly −0.12 / −1.7`.
**If a number differs, stop and find out why before writing anything else** — the method file's
docstring quotes this grid, and a pre-registration that quotes a number nobody can reproduce is
worse than no pre-registration.

---

### Step 2: `docs/backtests/2026-10-19-gate-band-cadence.md`

**File:** `$WT/docs/backtests/2026-10-19-gate-band-cadence.md` (new file)
**Change:** the writeup, in the register of `2026-10-19-gate-band-study.md` beside it: a dated
header block naming the instrument, window, script and the "nothing was recorded" disclaimer; then
the question, the grid, the mechanism, the reproduction, and what it does not establish.
**Code:**
```markdown
# The band's worth is a function of how often the gate is read, and at the lab's own cadence it is zero

**Measured:** 2026-10-19 · **Instrument:** SPY alone, no stock picking
**Window:** 1993-01-29 → 2015-10-16 (dev store `engine/.research`), 200-bar warmup
**Script:** `2026-10-19-gate-band-cadence.py` (re-runnable)
**Nothing was recorded.** No method, no trial, no N, no test-window look. This is a study on
market data, not a lab result. It is a prior, and the method that tests it is M0258.

**This note corrects the framing of `2026-10-19-gate-band-study.md` and of insight 464.** Neither
is wrong about what it measured. Both compared a price band against a gate read **every day**, and
no book in this lab reads its gate every day. Against the gate the lab actually runs, the band's
advantage is gone.

## The question

The gate-band study acts on SPY's close daily: 151 flips, 76 off-episodes, and a 3% band that beats
the bare gate on every axis. But every lab book reads its gate at its own rank session — monthly
for M0070, M0088, M0101, M0241 and M0245, weekly for M0063, M0072 and M0078 — and holds that
reading until the next one. A reading held for a month already suppresses every flip shorter than a
month. That is most of what a band does. So: how much of the study's finding is the band, and how
much is the daily reading nobody runs?

Cross the two axes. Same bars, same warmup, same one-session lag, same arithmetic; only the cadence
moves.

## The grid

| signal | gate read | whole CAGR | whole worst fall | 2009-2015 | invested | flips |
|---|---|---|---|---|---|---|
| bare gate | daily | 6.05% | −28.7% | 6.96% | 71.6% | 152 |
| bare gate | weekly | 5.51% | −34.6% | 5.82% | 70.8% | 80 |
| **bare gate** | **monthly** | **9.08%** | **−19.0%** | **10.07%** | 71.9% | 22 |
| band 1.5% | daily | 7.35% | −19.5% | 9.44% | 70.8% | 46 |
| band 1.5% | weekly | 6.95% | −24.5% | 8.42% | 70.9% | 46 |
| band 1.5% | monthly | 7.94% | −19.0% | 10.07% | 70.4% | 32 |
| band 3% | daily | 7.87% | −20.3% | 8.83% | 72.4% | 20 |
| band 3% | weekly | 8.03% | −19.0% | 8.84% | 72.4% | 20 |
| band 3% | monthly | 8.96% | −20.7% | 9.46% | 72.4% | 18 |
| band 6% | daily | 7.91% | −20.4% | 7.02% | 70.3% | 12 |
| band 6% | weekly | 8.15% | −21.8% | 6.91% | 70.4% | 12 |
| band 6% | monthly | 7.86% | −20.7% | 6.72% | 69.7% | 12 |

The band's worth is monotone in how often the gate is read, and it reaches zero at the lab's own
monthly cadence:

| gate read | band 3% − bare gate, return | band 3% − bare gate, worst fall |
|---|---|---|
| daily | **+1.82 pts/yr** | **8.4 pts better** |
| weekly | **+2.52 pts/yr** | **15.6 pts better** |
| monthly | **−0.12 pts/yr** | **1.7 pts worse** |

And the sentence that matters: **the monthly bare gate beats the daily 3% band on every axis in the
original study's own table** — return 9.08% against 7.87%, worst fall −19.0% against −20.3%, and
2009-2015 10.07% against 8.83%.

## The mechanism is not new, it is the same one

A band suppresses flips shorter than the band is wide. A monthly reading suppresses flips shorter
than a month. They are two ways of doing one thing, and once one of them is in place the other has
almost nothing left to do. The study's own numbers say so and it read them the other way round: its
3% band leaves "exactly 11 episodes — the number insight 452 reports", and insight 452 counted the
gate **at its monthly checks**. The study took that coincidence as evidence that the lab had been
reasoning about a cleaner gate than the one it runs. It is the reverse. The monthly reading *is*
the cleaner gate, and it is already cleaner than the band.

## Why this grid is trusted: it reproduces four recorded trials it shares no code with

The lab has already run both signals at both cadences on SPY alone, through the full simulator, on
the owner's monthly top-ups at Gotrade's real fees. This grid is a weight path on raw closes and
shares nothing with that machinery. The worst falls line up anyway:

| recorded trial | recorded worst fall | this grid |
|---|---|---|
| the bare gate read monthly | 18.89% | 19.0% |
| the 3% band read monthly | 20.69% | 20.7% |
| the bare gate read weekly | 33.13% | 34.6% |
| the 3% band read weekly | 18.92% | 19.0% |

And the money agrees, which is what matters. Those four trials are funded with the owner's real
monthly top-ups, so the number to read is what his money earned — against the same deposits put
into SPY, which earned 7.69% a year over that window:

| gate read | bare gate | 3% band | the band is worth | and on worst fall |
|---|---|---|---|---|
| weekly | 4.35%/yr | **7.78%/yr** | **+3.42 pts/yr** | **14.22 points shallower** |
| monthly | **9.13%/yr** | 8.73%/yr | **−0.40 pts/yr** | **1.80 points deeper** |

**A 3.82-point swing in what the band is worth, from the reading cadence alone — already recorded,
in money, and never named.** Read weekly, the bare gate loses to its own deposits in SPY by more
than three points a year and the band rescues it. Read monthly, the bare gate is the better of the
two and the band is a small, consistent cost. That is this note's claim, measured twice by
machinery that shares no code.

One more thing those rows settle. **The band did not cut turnover at monthly cadence.** It cut it
by 75% on the weekly SPY book (0.861 against 3.383), and by essentially nothing on the monthly one
(0.826 against 0.826). On M0101's monthly stock book the same holds: 4.727 against 4.780, 525
trades against 528. So "a band trades less" is a weekly-cadence fact. At monthly cadence a band
changes *when* the gate acts, not *how often*.

## What this does not establish

- **It is SPY only.** So was the study it corrects. Whether a band helps a book that holds stocks
  is the open question, and it is the question M0258 was built to answer.
- **It is the dev window**, in-sample for this lab. No test-window look was spent and none should
  be until a method exists and clears the dev screen.
- **It does not say the band is useless.** It says the band and a slow reading are substitutes, and
  the lab already has the slow reading. A book that must read its gate often — one re-picking
  weekly, say — is exactly where a band should still pay, and the recorded weekly pair agrees, by
  3.42 points a year of the owner's own money.
- **The curve-shape columns are not quoted here at all.** These books are funded, and the lab's own
  note on that is blunt: a funded book's CAGR is a lie, and `total_return` on a funded curve is not
  a return. Every figure above is either an unfunded study path (the grid) or the money-weighted
  return on the owner's deposits (the recorded trials). The two are never mixed in one sentence.
- **It is not the lab's band.** `m0101.band_on` scans back at most 504 sessions for the last
  crossing; the state machine here carries state from the first bar. The two can differ in the
  opening months of a run and agree thereafter.
```
**Impact:** adds one writeup. It is the document the method's hypothesis points at.

---

### Step 3: `engine/src/seer_engine/lab/methods/m0258_gate_price_band.py`

**File:** `$WT/engine/src/seer_engine/lab/methods/m0258_gate_price_band.py` (new file)
**Change:** the whole method. The complete file follows; paste it as it stands.
**Code:**
```python
"""M0258 -- A price band on the SPY 200-day gate, on a book that actually holds stocks.

Source: variation of M0072-Z2-RAWRANK, whose book is carried here unchanged; the band is
``m0101.band_on``, imported verbatim, as M0084 already imports it; Brock, Lakonishok & LeBaron
(1992), "Simple technical trading rules and the stochastic properties of stock returns", JF 47(5),
for the banded moving-average rule. The rule is thirty-four years old and nothing in it is a new
anomaly, so no fade argument applies to the band itself. What is new is the question.

WHY THIS METHOD EXISTS. On 2026-10-19 a study of the SPY 200-day gate found that a price band --
leave only once SPY closes b% UNDER its 200-day average, return only once it closes b% OVER --
beat the bare gate on every axis measured, and the handover written from it asked for a method.
Two things about that request are already answered in the lab's own record, and a third is not.

Every figure below is the MONEY-WEIGHTED return on the owner's own deposits -- what `lab show`
calls "your money earned" -- because these books are funded with a monthly top-up and the
curve-shape columns beside it, as `backtest/metrics.py` says outright, "are not returns at all".
SPY's figure is the SAME deposits into SPY over the same window.

    * Does a band help a book that holds stocks? The lab ran it. M0101-BAND-3 against M0101-CTRL,
      the same calm-big-raisers book either side, SPY taking the same deposits at 7.19%/yr: the
      band earned 10.44%/yr against 10.62% and fell 20.39% against 18.71%, on 525 trades against
      528. M0101-BAND-5 was worse again, 10.10%/yr and 20.39%. The band cost 0.18 points a year
      at 3% and 0.52 at 5%, and fell 1.68 points deeper at both.
    * Does a band help SPY alone, read monthly? The lab ran that too. M0084-BAND3-M earned
      8.73%/yr and fell 20.69%; M0084-MONTHLY, the bare gate, earned 9.13%/yr and fell 18.89%,
      against 7.69%/yr for the same deposits in SPY. The band cost 0.40 points a year and fell
      1.80 points deeper. Again it earned less and fell further.
    * And then the pair nobody has read in this light. M0084-WEEKLY, the SAME bare gate read
      WEEKLY, earned 4.35%/yr and fell 33.13% -- it lost to its own deposits in SPY by more than
      three points. M0084-BAND3-W, the same band read weekly, earned 7.78%/yr and fell 18.92%.
      Read weekly the band is worth +3.42 points a year and 14.22 points of worst fall. Read
      monthly it is worth -0.40 and 1.80 points WORSE.

So the lab has already recorded a 3.82-POINT SWING in what the band is worth, in money, between
two reading cadences on one instrument -- and it has never named it. That is this method's
question: **is the band's worth a function of how often the gate is READ, and does that hold on a
book that holds stocks?**

THE CADENCE GRID (measured on the dev store before this file was written, by
``docs/backtests/2026-10-19-gate-band-cadence.py``; this is a FEASIBILITY TABLE and a PRIOR, not a
result, in the same spirit as M0245's episode ledger and M0241's split-count table). SPY alone,
200-bar warmup, one-session lag, the signal held as read at each rank session:

    signal        gate read   whole CAGR   worst fall   2009-2015   invested   flips
    bare gate     daily           6.05%       -28.7%        6.96%      71.6%     152
    bare gate     weekly          5.51%       -34.6%        5.82%      70.8%      80
    bare gate     monthly         9.08%       -19.0%       10.07%      71.9%      22
    band 1.5%     daily           7.35%       -19.5%        9.44%      70.8%      46
    band 1.5%     weekly          6.95%       -24.5%        8.42%      70.9%      46
    band 1.5%     monthly         7.94%       -19.0%       10.07%      70.4%      32
    band 3%       daily           7.87%       -20.3%        8.83%      72.4%      20
    band 3%       weekly          8.03%       -19.0%        8.84%      72.4%      20
    band 3%       monthly         8.96%       -20.7%        9.46%      72.4%      18
    band 6%       daily           7.91%       -20.4%        7.02%      70.3%      12
    band 6%       weekly          8.15%       -21.8%        6.91%      70.4%      12
    band 6%       monthly         7.86%       -20.7%        6.72%      69.7%      12

    gate read    band 3% minus bare gate, return    the same, worst fall
    daily                       +1.82 pts/yr            8.4 pts better
    weekly                      +2.52 pts/yr           15.6 pts better
    monthly                     -0.12 pts/yr            1.7 pts WORSE

The grid reproduces the four recorded M0084 trials above in both sign and magnitude, which is why
it is trusted here; it shares no code with the simulator that produced them. And the monthly bare
gate beats the daily 3% band on every axis in the original study's own table.

THE MECHANISM IS NOT NEW, IT IS THE SAME ONE. A band suppresses flips shorter than the band is
wide. A monthly reading suppresses flips shorter than a month. They are substitutes, and the lab
already owns the second one. The study's own numbers said so and were read the other way round:
its band left "exactly 11 episodes -- the number insight 452 reports", and insight 452 counted the
gate at its MONTHLY checks. The monthly reading is not a coarser version of the gate the lab
reasons about; it IS the gate the lab reasons about, and it is already cleaner than the band.

WHAT IS ALREADY DEAD, AND WHY A BAND IS NOT ONE OF THEM. The handover lists every modification of
this gate the lab has measured and buried, and none of them is re-tested here: turning the gate
off (helped 22 of 22 variants whole-window, 0 of 22 after 2009, and every gate-off arm was worse
on return AND drawdown at once); a TIME lock on the switch (costs return and deepens the fall from
20% to 32%, because the flips it suppressed included the 2008-05-21 exit, one day after the
previous episode ended); an account-reading drawdown brake (pays 10 points a year of 2009-2015 to
save 40 of 2008); a learned fall-sizing brake (M0132, beaten by the plain gate on both axes);
VIX-level confirmation of the exit (worse on both axes at 20, 25 and 30, and VIX3M only begins
2006-07-17 so it cannot be checked against the dot-com at all); and exit-buffer-only,
confirm-N-days, partial exposure and fast re-entry on the 50-day, all in the committed grid and
all worse than the symmetric band. The standing rule after the time lock reads "stop hunting
hysteresis here". A band in PRICE is not that lock: the lock suppressed an exit because of WHEN
the previous one ended, and the band has no memory of time at all -- it reads only where price
stands against the average. The handover says this explicitly, and the lab's own weekly pair above
is the evidence that the two are different animals.

THE HOST BOOK, AND WHY IT IS THIS ONE. M0072-Z2-RAWRANK, carried verbatim: M0063's earnings-day
jump event kept only when the jump is at least two of the stock's own daily swings and ranked by
the raw jump, F4's five-dollar and twenty-million-dollar screen, 20 slots at 5%, SPY in the empty
ones, re-picked at the rule set's cadence, fractional shares at Gotrade's real fees on the owner's
monthly top-ups. It is one of only three books the lab reads as promotable and kin-clean, and the
only one of the three whose engine is cadence-robust: its event hold is counted in SESSIONS, not
calendar months, and its parent M0063 ran the identical book weekly and monthly. The other two
cannot carry a cadence axis -- M0197's chooser keys its re-pick on the calendar month itself.
Its recorded trial earned 12.33%/yr on the owner's deposits against 7.19% for the same deposits in
SPY, fell 23.80% at worst, and made gains 1.98 times its losses on 1208 trades and 6.53 turns a
year.

WHY A NEW ALLOCATOR ID AND NOT A WIDER PARAMETER. ``f_factor.FactorParams.trend`` is
``tuple[str, int] | None`` and ``config_text`` renders it "SPY:200". Widening it to carry a band
would move every recorded config digest in the lab. The band therefore lives in a new dataclass
behind a new allocator id. That costs one method id, and that is the correct price.

HOW THE OVERLAY WORKS, AND THE ONE LINE IT REPLACES. ``BandedGateAllocator`` delegates lookback,
symbols, holds, uses_members and prepare to ``ZJUMP`` and runs M0072's own target builder on
M0072's own prepared panel. Exactly one line differs: the gate reading.

    * ``band = 0``: ``f_factor.trend_on`` unchanged. Not ``band_on`` at zero -- although the two
      are provably the same thing on this tape (``test_lab_m0258_band.py`` asserts it session by
      session), the zero rung's job is to REPRODUCE the host's recorded trial, and a reproduction
      should run the host's own code.
    * ``band > 0``: ``m0101.band_on(history.get(symbol), data_date, n, float(band))`` with
      ``(symbol, n)`` taken from the book's own ``jump.inner.trend``, so the band is read on the
      same symbol and the same average the bare gate reads. Scanning back from the data date, the
      newest session under 1-band turns it off and the newest over 1+band turns it on, whichever
      is newer; with no crossing inside ``m0101.SCAN`` sessions it falls back to the strict test.
      The state is read on DAILY closes and the book acts on it only at its own rank session,
      which is exactly the thing the cadence pair is measuring.

``lookback`` is ``ZJUMP.lookback(p.book)`` and nothing else -- 253 bars. ``SCAN`` is deliberately
NOT added, for M0101's recorded reason: it would move the dev window's first scored session off
the host's and break the paired comparison. On the dev store SPY has years of run-up before
1996-01-03, so a crossing older than the bars on hand cannot arise.

THE SIX ARMS. All six hold M0072-Z2-RAWRANK's book, unchanged. Only the band and the cadence move.

    * M-B0  monthly, band 0     the paired bare gate and the ladder's zero dose; must reproduce
                                the host's recorded trial through a new digest
    * M-B15 monthly, band 1.5%  the measured plateau's lower edge
    * M-B30 monthly, band 3%    the band arm, at the handover's own value
    * M-B60 monthly, band 6%    the plateau's upper edge
    * W-B0  weekly,  band 0     the same book and the same bare gate, read weekly
    * W-B30 weekly,  band 3%    the same band, read weekly

Arms one to four are a dose-response ladder in the band, and the ladder with its zero rung IS the
control: the lab's own standing finding is that a dose-response beats a drawn control, because
more of the treatment giving more of the effect excludes a frame effect by construction. No arm is
a drawn control, and hard gate D17 refuses only drawn arms and never refuses a method that has
none. Arms five and six turn a predicted null into a difference-in-differences with a sign written
down before the run.

THE WEEKLY ARMS CAN NEVER BE PROMOTED, AND THAT IS DELIBERATE. ``WEEKLY_HOLD_FRAC_GOTRADE`` is
M0063's one-off rule set and is not a member of ``sim.rules.PRESETS``, which ``lab promote``
requires. It differs from the monthly preset in exactly two fields, ``id`` and ``cadence``, so the
cadence axis is clean. The promotable arms are the four monthly ones; the weekly pair is
diagnostic. Minting a preset to make them promotable would be scope nobody asked for, and the
honest thing is to say so here rather than work around it.

Pure: no clock, no randomness, no network, no file, no printing. Reads only bars dated on or
before ``data_date``. ``held`` is read only where M0072 reads it -- to let a name keep its slot --
and the band's state lives in the price path, never in the book, so a deposit cannot move it.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0063_earnings_day_jump import WEEKLY_HOLD_FRAC_GOTRADE
from seer_engine.lab.methods.m0072_standardised_earnings_jump import (
    JUMP20,
    ZJUMP,
    ZParams,
    ZPrepared,
)
from seer_engine.lab.methods.m0101_calm_raisers_banded_switch import band_on
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import factor_rows, trend_on

ADDED = date(2026, 10, 19)

#: The widest half-band this method will accept. M0101 and M0084 both use 0.2 and both forbid 0;
#: here 0 is the ladder's zero dose and must be allowed, so the bound is half-open at the bottom.
MAX_BAND = Decimal("0.2")


@dataclass(frozen=True, slots=True)
class BandParams:
    """``book`` is M0072's book, carried whole; ``band`` is the gate's hysteresis half-width.

    ``band = 0`` is the bare gate and is legal here, unlike in M0101's ``SwitchParams``, because
    this method's ladder needs a zero dose that runs through the same allocator id as its rungs.
    """

    book: ZParams
    band: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        if not isinstance(self.book, ZParams):
            raise TypeError(f"book must be ZParams, got {type(self.book).__name__}")
        if self.book.jump.inner.trend is None:
            raise ValueError("book must carry a trend symbol and length for the band to read")
        if not isinstance(self.band, Decimal) or not self.band.is_finite():
            raise ValueError(f"band must be a finite Decimal, got {self.band!r}")
        if not Decimal(0) <= self.band < MAX_BAND:
            raise ValueError(f"band must lie in [0, {MAX_BAND}), got {self.band}")

    def as_dict(self) -> dict[str, str]:
        """Every field as a plain string, the book's prefixed ``book.`` -- M0101's shape exactly."""
        out = {"band": format(self.band.normalize(), "f")}
        for k, v in self.book.as_dict().items():
            out[f"book.{k}"] = v
        return out


def _check(params: object) -> BandParams:
    if not isinstance(params, BandParams):
        raise TypeError(f"params must be BandParams, got {type(params).__name__}")
    return params


class BandedGateAllocator:
    """M0072's standardised-jump book, with a price band around the gate it already runs behind."""

    id = "M0258"

    def lookback(self, params: Any) -> int:
        """The host's lookback and nothing else -- 253 bars. ``m0101.SCAN`` is never added.

        Widening this would move the dev window's first scored session off M0072's 1996-01-03 and
        turn the ``band = 0`` arm from a reproduction into an approximation, which is the one
        thing this method cannot afford: every claim it makes is a paired difference.
        """
        return ZJUMP.lookback(_check(params).book)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ZJUMP.symbols(_check(params).book)

    def holds(self, params: Any) -> tuple[str, ...]:
        return ZJUMP.holds(_check(params).book)

    def uses_members(self, params: Any) -> bool:
        return ZJUMP.uses_members(_check(params).book)

    def _on(self, history: Mapping[str, History], data_date: date, p: BandParams) -> bool:
        """The single line this allocator exists to replace: how the gate reads SPY.

        At ``band = 0`` this is the lab's gate, run through the lab's own function rather than
        through ``band_on`` at zero. The two agree on every session of the dev tape -- the test
        module asserts it -- but the zero rung's job is to reproduce the host, and a reproduction
        runs the host's code.
        """
        inner = p.book.jump.inner
        if p.band == 0:
            return trend_on(history, data_date, inner)
        symbol, n = inner.trend
        return band_on(history.get(symbol), data_date, n, float(p.band))

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path, kept target-for-target identical to M0072's at ``band = 0``.

        ``ZJUMP._targets`` is reached directly because M0072 exposes no seam between its gate test
        and its target builder, and the obvious alternative is wrong: handing ``ZJUMP`` a
        gate-free twin of its params (``trend=None``) runs -- its lookback and symbols are
        identical, measured -- but it would make the recorded row a lie: ``config_text`` digests
        ``BandParams``, which holds the book UNMODIFIED, so the row would say ``trend=SPY:200``
        while the allocator ran something else. Calling the builder with the host's own params
        keeps the book provably identical and replaces exactly the gate. The private call is safe
        because ``m0072.py`` is frozen against its recorded source sha.
        """
        p = _check(params)
        if not self._on(history, data_date, p):
            return ()
        rows = factor_rows(history, members, data_date, p.book.jump.inner)
        return ZJUMP._targets(ZPrepared(history, None), rows, data_date, held, p.book)

    def prepare(self, history: Mapping[str, History]) -> ZPrepared:
        return ZJUMP.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ZPrepared) or prepared.factor is None:
            raise TypeError(f"prepared must be a prepared ZPrepared, got {type(prepared).__name__}")
        p = _check(params)
        if not self._on(prepared.history, data_date, p):
            return ()
        rows = prepared.factor.rows_on(members, data_date, p.book.jump.inner)
        return ZJUMP._targets(prepared, rows, data_date, held, p.book)


BANDED = BandedGateAllocator()

#: M0072-Z2-RAWRANK's configuration, verbatim: the Z2 filter ranked by the raw jump.
BOOK = ZParams(JUMP20, z_min=Decimal("2"), rank="raw")

B15 = Decimal("0.015")
B30 = Decimal("0.03")
B60 = Decimal("0.06")


def _v(suffix: str, band: Decimal, rules: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0258-{suffix}", family="M0258", rules=rules, allocator=BANDED,
                     params=BandParams(BOOK, band), rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0258",
    name="A price band on the 200-day safety gate, on a book that holds stocks: is the band worth "
         "anything once the gate is only read once a month?",
    family="stock-event-drift",
    source_kind="variation",
    source_ref=(
        "variation of M0072-Z2-RAWRANK (its book unchanged); the band is m0101.band_on verbatim, "
        "as M0084 already reuses it; Brock, Lakonishok & LeBaron (1992), Simple technical trading "
        "rules and the stochastic properties of stock returns, JF 47(5), for the banded "
        "moving-average rule"
    ),
    parent_id="M0072",
    hypothesis=(
        "Published 1992 (the banded moving-average rule), so nothing in the band is a new anomaly "
        "and no fade argument applies to it; what is new is the question. A study on 2026-10-19 "
        "found that a price band around the SPY 200-day gate -- leave only once SPY closes b "
        "percent under its 200-day average, return only once it closes b percent over -- beat the "
        "bare gate on every axis, and asked for a method. The lab has already answered half of "
        "that twice and recorded the answers, and every figure here is the MONEY-WEIGHTED return "
        "on the owner's own monthly deposits, which is the only honest headline for a funded "
        "book -- what the lab prints as 'your money earned', against the SAME deposits put into "
        "SPY, which earned 7.19% a year over M0101's and M0072's window and 7.69% over M0084's. "
        "On a book that holds stocks, M0101-BAND-3 earned 10.44% a year against M0101-CTRL's "
        "10.62% and fell 20.39% against 18.71%, on 525 trades against 528 and turnover 4.727 "
        "against 4.780; M0101-BAND-5 earned 10.10%. So on a stock book the band COST 0.18 points "
        "a year at 3% and 0.52 at 5%, fell 1.68 points deeper at both, and barely changed how "
        "much the book traded. On SPY alone read monthly, M0084-BAND3-M earned 8.73% against "
        "M0084-MONTHLY's 9.13% and fell 20.69% against 18.89%: the band cost 0.40 points and fell "
        "1.80 deeper. But the lab also recorded, and never read, the other half. On SPY alone "
        "read WEEKLY the bare gate earned just 4.35% a year -- more than three points BELOW its "
        "own deposits in SPY -- and fell 33.13%, while the same band read weekly earned 7.78% and "
        "fell 18.92%, on turnover 0.861 against 3.383. Read weekly the band is worth +3.42 points "
        "a year and 14.22 points of worst fall; read monthly it is worth -0.40 and 1.80 points "
        "worse. That is a 3.82-point swing in the band's worth, in money, from the reading "
        "cadence alone, already recorded. (Every difference in this paragraph is taken at full "
        "precision from the recorded money-weighted returns, so it can be re-derived exactly; "
        "differencing their two-decimal printed forms instead gives +3.43, 14.21 and 3.83.) The "
        "cadence grid measured for this file (SPY alone, dev store, "
        "one-session lag, signal held as read at each rank session) says the same thing as a "
        "smooth function: band 3% minus bare gate is +1.82 points a year and 8.4 points of worst "
        "fall better when the gate is read daily, +2.52 and 15.6 better read weekly, and -0.12 "
        "and 1.7 points WORSE read monthly. The monthly bare gate beats the daily 3% band on "
        "every axis in the original study's own table. The mechanism is not new: a band "
        "suppresses flips shorter than the band is wide, a monthly reading suppresses flips "
        "shorter than a month, and they are substitutes -- which is why the study's band left "
        "exactly the eleven episodes insight 452 counted AT ITS MONTHLY CHECKS. So the question "
        "worth one method id is not 'does the band win', which the lab has answered twice, but "
        "'IS THE BAND'S WORTH A FUNCTION OF HOW OFTEN THE GATE IS READ, ON A BOOK THAT HOLDS "
        "STOCKS'. Six arms hold M0072-Z2-RAWRANK's book verbatim -- the standardised earnings-day "
        "jump kept at two of the stock's own daily swings and ranked by the raw jump, F4's "
        "five-dollar and twenty-million screen, 20 slots at 5%, SPY in the empty ones, fractional "
        "at Gotrade's real fees on the owner's monthly top-ups -- and move only the band and the "
        "cadence: M-B0 (monthly, no band: the paired bare gate and the ladder's zero dose, which "
        "must reproduce the host's recorded trial), M-B15, M-B30 and M-B60 (monthly, 1.5%, 3% and "
        "6%: the dose-response ladder across the measured plateau), W-B0 and W-B30 (the same book "
        "and the same two signals read weekly). The lookback is M0072's 253 bars exactly, so "
        "every arm is scored from 1996-01-03 on the same sessions and each paired difference is "
        "the gate alone. THE PRE-REGISTERED PREDICTION, written before the run: (W-B30 minus "
        "W-B0) much greater than (M-B30 minus M-B0), which is itself about zero, on return AND on "
        "worst fall; and the monthly ladder flat or gently downward in the band across 0, 1.5, 3 "
        "and 6 percent rather than humped. SUCCESS IS A MEASUREMENT, NOT ELIGIBILITY. This method "
        "is bought to settle a cadence question the lab has been reasoning past, and a null on "
        "the monthly pair is a result that corrects a standing document. If instead the monthly "
        "pair shows a real gap on a book of stocks, then the handover's finding survived contact "
        "with stock selection and the lab has a genuinely better gate, which would be worth far "
        "more than one id. Assumed without asking: that M0072 is the right host because it is one "
        "of three promotable, kin-clean books and the only one whose engine counts its hold in "
        "sessions rather than calendar months, so it can carry a weekly arm honestly."
    ),
    expected_failure=(
        "The most likely outcome is simply NOTHING on the monthly pair -- M-B30 within a few "
        "tenths of a point of M-B0 on return and within a point or two on worst fall, and the "
        "ladder across 0, 1.5, 3 and 6 percent flat or drifting down rather than rising. That is "
        "what the cadence grid predicts and what M0101 already recorded on a different book, and "
        "if it happens this method has bought a null. The null is still worth the id, because the "
        "lab is currently carrying a committed study and a journalled insight whose headline "
        "compares the band against a baseline no book in the lab runs, and nothing short of a "
        "pre-registered paired measurement on a real book corrects that. Second, the walk-forward "
        "folds pick each fold's variant by MAR, so they will favour whichever arm trades least -- "
        "M0245's folds picked its slowest rung in three of four, and the lab has written that "
        "down. A fold majority won by M-B60 is therefore weak evidence for the band and should be "
        "read as evidence about turnover; read the folds arm by arm, not just the headline. "
        "Third, the weekly arms run on a rule set that is not in the promotion presets, so they "
        "can never be promoted no matter what they show; they are diagnostic, and a result that "
        "lives only in them is a measurement the lab cannot act on. Fourth, even if the weekly "
        "band does win, it may be a FEE story rather than a signal story: the band cuts the "
        "gate's own flips by about a factor of four, a weekly book pays Gotrade on every re-pick, "
        "and the fee term was the second-largest container in the 824-trial shortfall sweep. The "
        "ladder is the only defence against that reading -- a fee story should keep improving "
        "monotonically as the band widens and trading falls, while a signal story should peak and "
        "turn. But note what is already measured about that: the band cut turnover only at the "
        "WEEKLY cadence, 0.861 against 3.383 on the weekly SPY book, a 75% cut. On both recorded "
        "MONTHLY books it cut essentially nothing -- 4.727 against 4.780 on M0101's stock book, a "
        "1.1% difference on 525 trades against 528, and 0.826 against 0.826 on SPY. So the "
        "brief's premise that the band cuts turnover sharply is a weekly-cadence fact and not a "
        "monthly one, the four monthly arms here are expected to differ from each other in shape "
        "by well under 1%, and any difference between them is therefore the gate's TIMING rather "
        "than its cost. If instead the monthly arms do separate on turnover, something in this "
        "book interacts with the band that SPY alone and M0101's book did not, and that itself is "
        "the finding. Fifth, the dev window holds exactly TWO crashes, and the whole of the band's "
        "measured advantage comes from holding each of them as one exit instead of fragmenting it "
        "and buying back inside the fall. Two is not a sample; both of this window's crashes "
        "happened to be slow, and a fast crash is what 1987 and 2020 were. Nothing measured on "
        "dev can settle that, the folds are the only within-window check, and no test-window look "
        "is spent here. Sixth, the host book's own recorded worst fall is 23.80%, over the "
        "real-money bar already, so no arm is expected to clear every go-live condition and the "
        "band is not being asked to fix that. Finally, as in every switch method the lab has run: "
        "interest on the cash held while the gate is off is not modelled, which flatters SPY and "
        "penalises every gated arm equally, so each gap reported is an upper bound on the gate's "
        "cost and the paired differences are unaffected."
    ),
    candidates=(
        _v("M-B0", Decimal(0), MONTHLY_HOLD_FRAC_GOTRADE,
           "The dose-response ladder's zero rung and the paired bare gate: M0072-Z2-RAWRANK's own "
           "book behind its own unchanged 200-day switch, read monthly"),
        _v("M-B15", B15, MONTHLY_HOLD_FRAC_GOTRADE,
           "First rung of the dose-response ladder: leave 1.5% under the 200-day average, return "
           "1.5% over, read monthly"),
        _v("M-B30", B30, MONTHLY_HOLD_FRAC_GOTRADE,
           "Middle rung of the dose-response ladder and the idea itself: leave 3% under the "
           "average, return 3% over, read monthly"),
        _v("M-B60", B60, MONTHLY_HOLD_FRAC_GOTRADE,
           "Top rung of the dose-response ladder: leave 6% under the average, return 6% over, "
           "read monthly"),
        _v("W-B0", Decimal(0), WEEKLY_HOLD_FRAC_GOTRADE,
           "The same book and the same bare 200-day switch read WEEKLY: the cadence axis, and the "
           "weekly pair's own zero dose"),
        _v("W-B30", B30, WEEKLY_HOLD_FRAC_GOTRADE,
           "The same 3% band read WEEKLY: with the three arms above, the difference-in-differences "
           "whose sign was written down before the run"),
    ),
    seen_keys=(
        "concept:gate-cadence-dose-response",
        "concept:banded-gate-on-an-event-book",
    ),
)
```
**Impact:** one new method file, one new allocator id. Nothing imports it except `method.discover()`
and the new test module. The two `seen_keys` were verified free against `ideas_seen` before this
plan was written; `concept:banded-trend-switch` is M0101's and must **not** be reused.
**Checks that are easy to get wrong, listed so they are not:**
- `_v` builds `BandParams(BOOK, band)` internally, so no candidate can accidentally run a
  different book.
- The rationales contain `dose-response` (four of them) and none contains `placebo`, `hash-drawn`
  or `hash order` in any case. `control_shape.kind_of` lowercases and tests dose before draw.
- `Decimal(0)` not `Decimal("0.0")`: `format(Decimal(0).normalize(), "f")` renders `0`, which is
  what `as_dict` must emit and what the test module asserts.
- Six candidates, exactly. `method.MAX_VARIANTS = 6` (I7).

---

### Step 4: `engine/tests/test_lab_m0258_band.py`

**File:** `$WT/engine/tests/test_lab_m0258_band.py` (new file)
**Change:** the dedicated module, in the register of `engine/tests/test_lab_m0155_brake.py`: a
docstring saying what the generic kit already covers and what these five checks add, then the
checks. A dedicated module rather than wider cases in the shared lab tests, because the shared
smoke fixture's 473 sessions are a frozen budget (memory:
*lab method lookback is capped at 473 bars*) and must not be stretched to suit a new method.
**Code:**
```python
"""M0258's banded gate: the five claims the method file makes that the generic kit cannot check.

``test_lab_methods`` already drives every lab allocator through ``allocatorkit`` -- valid targets,
the P4 identity, no look-ahead -- and runs every candidate on a smoke window. These are the
properties specific to putting a price band around a gate on somebody else's book:

1. **A zero band IS the lab's gate**, session for session on the smoke tape. The method routes
   ``band = 0`` through ``f_factor.trend_on`` rather than through ``band_on`` at zero, and this is
   the test that earns the right to call the zero rung a reproduction rather than an approximation.
2. **The overlay declares the host's shape** -- above all the same lookback. A wider lookback would
   move the dev window's first scored session off M0072's 1996-01-03 and break every paired
   difference the method reports, and ``m0101.SCAN`` is the obvious thing someone would add.
3. **The params round-trip and the doses digest apart.** ``config_text`` reads the rules, the
   allocator id and the params only, so if ``as_dict`` dropped a field two different bands would
   record under one digest and the second would be refused as already run.
4. **With the band off this allocator IS the host book**, target for target, on both the
   history-only and the prepared path. That is why M0258 spends no trial on a separate control:
   M0072-Z2-RAWRANK is recorded, and this test is what earns the right to quote it.
5. **The band is actually wired in.** Every rung must change the gate's reading somewhere on the
   tape, or an arm that looks like a dose is running the bare gate under another name.

A dedicated module rather than more cases inside the shared lab tests: the smoke fixture's 473
sessions are a fixed budget every lab method is measured against, and a new method must fit it
rather than stretch it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from labkit import MEMBER_STOCKS, SMOKE_FIRST, smoke_market

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END, Candidate
from seer_engine.lab.method import config_digest
from seer_engine.lab.methods.m0063_earnings_day_jump import WEEKLY_HOLD_FRAC_GOTRADE
from seer_engine.lab.methods.m0072_standardised_earnings_jump import ZJUMP
from seer_engine.lab.methods.m0101_calm_raisers_banded_switch import band_on
from seer_engine.lab.methods.m0258_gate_price_band import (
    ADDED,
    BANDED,
    BOOK,
    B15,
    B30,
    B60,
    BandParams,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.f_factor import trend_on

BENCH = "SPY"
SMA_N = 200
MEMBERS = frozenset(MEMBER_STOCKS)
PROBES = dates.sessions(date(2014, 12, 1), DEV_END)[::40]
OFF = BandParams(BOOK, Decimal(0))


@pytest.fixture(scope="module")
def market():
    return smoke_market((BENCH,))


def _spy_sessions(market):
    """Every smoke session SPY has a bar for, which on this fixture is all 473 of them."""
    h = market.history[BENCH]
    return [d for d in dates.sessions(SMOKE_FIRST, DEV_END) if h.index_of(d) is not None]


def test_a_zero_band_is_the_lab_gate_on_every_session(market):
    """``band_on(..., 0.0)`` equals ``trend_on`` on every smoke session, both readings seen.

    The method routes the zero rung through ``trend_on``, so this is not how M0258 runs -- it is
    the proof that the ladder has a genuine zero dose and that the rungs above it differ from the
    host by the band and by nothing else. ``band_on``'s fallback and its ``isfinite`` guard are
    one edge case away from ``trend_on``, which is exactly why this is asserted and not assumed.
    """
    h = market.history[BENCH]
    sessions = _spy_sessions(market)
    assert len(sessions) > 400, "the smoke fixture shrank; this check needs a tape to walk"
    on = 0
    for d in sessions:
        gate = trend_on(market.history, d, BOOK.jump.inner)
        assert band_on(h, d, SMA_N, 0.0) is gate, d
        on += int(gate)
    assert 0 < on < len(sessions), "the gate never changed its mind: the comparison proved nothing"


def test_the_overlay_declares_the_host_books_shape(market):
    """Lookback, symbols, holds and membership are M0072's, unchanged, at every band."""
    for band in (Decimal(0), B15, B30, B60):
        p = BandParams(BOOK, band)
        assert BANDED.lookback(p) == ZJUMP.lookback(BOOK), band
        assert BANDED.symbols(p) == ZJUMP.symbols(BOOK), band
        assert BANDED.holds(p) == ZJUMP.holds(BOOK), band
        assert BANDED.uses_members(p) is ZJUMP.uses_members(BOOK), band


def test_the_params_round_trip_and_the_doses_digest_apart():
    """``as_dict`` carries every field, and each arm is its own configuration."""
    p = BandParams(BOOK, B30)
    rendered = p.as_dict()
    assert set(rendered) == {"band"} | {f"book.{k}" for k in BOOK.as_dict()}
    assert rendered["band"] == "0.03"
    assert all(isinstance(v, str) for v in rendered.values())
    for k, v in BOOK.as_dict().items():
        assert rendered[f"book.{k}"] == v
    assert BandParams(BOOK, Decimal(0)).as_dict()["band"] == "0"

    def candidate(suffix, band, rules):
        return Candidate(id=f"M0258-{suffix}", family="M0258", rules=rules, allocator=BANDED,
                         params=BandParams(BOOK, band), rationale="a rung", added=ADDED,
                         owner_inputs=())

    digests = {
        config_digest(candidate("M-B0", Decimal(0), MONTHLY_HOLD_FRAC_GOTRADE)),
        config_digest(candidate("M-B15", B15, MONTHLY_HOLD_FRAC_GOTRADE)),
        config_digest(candidate("M-B30", B30, MONTHLY_HOLD_FRAC_GOTRADE)),
        config_digest(candidate("M-B60", B60, MONTHLY_HOLD_FRAC_GOTRADE)),
        config_digest(candidate("W-B0", Decimal(0), WEEKLY_HOLD_FRAC_GOTRADE)),
        config_digest(candidate("W-B30", B30, WEEKLY_HOLD_FRAC_GOTRADE)),
    }
    assert len(digests) == 6, "two arms share a configuration digest"


def test_the_band_off_is_the_host_book_target_for_target(market):
    """At ``band = 0`` M0258 equals M0072-Z2-RAWRANK, on both paths, at every probe."""
    prepared_host = ZJUMP.prepare(market.history)
    prepared_band = BANDED.prepare(market.history)
    seen = 0
    for session in PROBES:
        d = dates.prev_session(session)
        host = ZJUMP.targets(market.history, MEMBERS, d, frozenset(), BOOK)
        band = BANDED.targets(market.history, MEMBERS, d, frozenset(), OFF)
        host_p = ZJUMP.targets_prepared(prepared_host, MEMBERS, d, frozenset(), BOOK)
        band_p = BANDED.targets_prepared(prepared_band, MEMBERS, d, frozenset(), OFF)
        assert band == host, d
        assert band_p == host_p == host, d
        seen += len(host)
    assert seen > 0, "every probe was empty, so the comparison proved nothing"


def test_every_rung_actually_moves_the_gate(market):
    """Each band changes the reading somewhere, or it is the bare gate wearing a dose's name."""
    h = market.history[BENCH]
    sessions = _spy_sessions(market)
    for band in (B15, B30, B60):
        moved = sum(
            1 for d in sessions
            if band_on(h, d, SMA_N, float(band)) != band_on(h, d, SMA_N, 0.0)
        )
        assert moved > 0, f"band {band} never differs from the bare gate on the smoke tape"


def test_the_params_refuse_what_they_say_they_refuse():
    """The validator is part of the pre-registration: a band outside [0, 0.2) is not this method."""
    with pytest.raises(ValueError):
        BandParams(BOOK, Decimal("0.2"))
    with pytest.raises(ValueError):
        BandParams(BOOK, Decimal("-0.01"))
    with pytest.raises(ValueError):
        BandParams(BOOK, Decimal("NaN"))
    with pytest.raises(ValueError):
        BandParams(BOOK, 0.03)  # a float band, not a Decimal: ValueError, as M0101 raises it
    with pytest.raises(TypeError):
        BandParams(object(), Decimal(0))
    with pytest.raises(TypeError):
        BANDED.lookback(BOOK)
```
**Impact:** adds one test module, ~130 lines, runs in a second or two on the smoke fixture. It
asserts the three things the plan index calls invariants (equivalence at `b = 0`, lookback equality,
digest separation) plus the two that make the ladder meaningful.
**Measured expectations** (so a failure is recognised as a real failure, not a fixture surprise):
`len(sessions) == 473`, 163 of them reading on; `moved` is 9 at 1.5%, 22 at 3% and 25 at 6%;
`seen == 4` at the six probes.

---

### Step 5: Run the tests and the linter, in the worktree

**File:** none
**Change:** prove the method before committing it. I9 — if the contract test fails, fix the method.
**Code:**
```bash
cd "$WT"
"$PYTEST" -n0 -q engine/tests/test_lab_m0258_band.py > "$OUT/t_band.txt" 2>&1; echo "RC=$?"
tail -20 "$OUT/t_band.txt"

"$PYTEST" -n0 -q engine/tests/test_lab_methods.py -k "M0258 or unique or pure or frozen or digest" \
  > "$OUT/t_methods_m0258.txt" 2>&1; echo "RC=$?"
tail -20 "$OUT/t_methods_m0258.txt"

"$RUFF" check engine > "$OUT/ruff.txt" 2>&1; echo "RC=$?"
cat "$OUT/ruff.txt"
```
**Expected:** both pytest runs exit `0`. The `-k` selection picks up `test_method_source_is_pure[M0258]`,
`test_candidate_runs_a_smoke_window[M0258-*]` (six of them),
`test_allocator_contract[M0258-*]` (six), `test_allocator_ids_are_unique_across_methods`,
`test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` and
`test_every_recorded_configuration_still_digests_to_its_recorded_digest`. Ruff prints
`All checks passed!`.
**Impact:** none on the tree. `test_lab_snapshot.py` is **not** run here — it is green at this
point and will go red the moment `lab run` writes, by design, until `lab stage`.

---

### Step 6: Commit the pre-registration and push it to `main`

**File:** `$WT` git index
**Change:** the commit of the method file **is** the pre-registration (I5). `lab run`'s preflight
(`runner.preflight` → `registry_problem`) refuses a method file that is untracked or has staged or
unstaged changes **in the current checkout**, so this must land before Step 7. Commit by pathspec —
this worktree shares one index with the main checkout and with any sibling swarm session, so never
`git add -A` and never `git reset --hard` (memory: *Seer swarms share one worktree*).
**Code:**
```bash
cd "$WT"
git add engine/src/seer_engine/lab/methods/m0258_gate_price_band.py \
        engine/tests/test_lab_m0258_band.py \
        docs/backtests/2026-10-19-gate-band-cadence.py \
        docs/backtests/2026-10-19-gate-band-cadence.md \
        docs/plans/GATE_PRICE_BAND_PLAN.md \
        docs/analyzer/20261019-135550-B4K2_code_analyzer.md \
        .workflows/plan/gate-price-band/phase-1.md
git commit -m "$(cat <<'MSG'
lab: M0258 pre-registered — a price band on the 200-day gate, on a book that holds stocks

The 2026-10-19 gate-band study compared a price band against a gate read every day, and no
book in this lab reads its gate every day. The committed cadence grid beside it crosses the
signal with the cadence: the band is worth +1.82 points a year read daily, +2.52 read weekly
and -0.12 read monthly, which is the cadence the lab actually runs. The lab had already
recorded the same sign flip on SPY alone and never named it, in money: read weekly, the band
earned the owner 7.78% a year against the bare gate's 4.35% and fell 18.92% against 33.13%;
read monthly, 8.73% against 9.13% and a fall 1.80 points deeper. A 3.82-point swing in what
the band is worth, from the reading cadence alone.

So M0258 asks the question that is still open: is the band's worth a function of how often
the gate is read, on a book that holds stocks? Six arms hold M0072-Z2-RAWRANK's book verbatim
and move only the band and the cadence — a dose-response ladder at 0, 1.5, 3 and 6 percent
read monthly, plus the bare gate and the 3% band read weekly. The zero rung is the paired
control and must reproduce the host's recorded trial. The prediction is written down before
the run: the weekly pair separates and the monthly pair does not.

Success here is a measurement, not eligibility. No test-window look is spent.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
git fetch origin && git rebase origin/main && git push origin HEAD:main
echo "push RC=$?"
```
**Then bring the main checkout up to the same commit, while its tree is still clean of lab writes:**
```bash
git -C "$MAIN" fetch origin && git -C "$MAIN" merge --ff-only origin/main
echo "main ff RC=$?"
git -C "$MAIN" log --oneline -1
```
**Impact:** the method file is on `main` and present in the main checkout, which matters because
`test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` runs there and demands a file for
every method with a `source_sha`. Doing the fast-forward **before** `lab run` keeps it away from a
dirty `lab/lab.sqlite` (memory: *a rebase replays a stale lab.sqlite*; this is a fast-forward of a
commit that touches no lab file, with the main tree clean, which is the safe shape).
**If `git rebase origin/main` pulls in a sibling session's lab commit:** re-check that trial `n` is
contiguous in `lab/lab.sqlite` before running, and never `reset --hard`.

---

### Step 7: `lab run M0258`

**File:** `lab/lab.sqlite` (main checkout, via `SEER_LAB_DB`)
**Change:** six dev trials, one `method_folds` row, the `methods` row with its `source_sha`, and
two `ideas_seen` rows — all in one transaction. **This is the irreversible step** (see Rollback).
**Code:**
```bash
cd "$WT"
"$PY" -m seer_engine lab run M0258 > "$OUT/run.txt" 2>&1 &
echo "started; poll $OUT/run.txt"
```
Run it in the background and poll; a six-arm member-wide book on one core takes minutes to tens of
minutes, and two of the arms re-pick weekly. When it finishes:
```bash
tail -60 "$OUT/run.txt"
```
**Judging it (I8):** do **not** pipe this command. The shell prints a spurious
`setValueForKeyFakeAssocArray:27: command not found: _encode` line at startup that will appear at
the head of the file; ignore it. Read the exit status from the backgrounded job, or re-derive it:
```bash
"$PY" -m seer_engine lab show M0258 > "$OUT/show.txt" 2>&1; echo "show RC=$?"
```
`show RC=0` with six trials listed is the confirmation that the run landed.
**Exit codes:** `0` ok · `2` the lab's rules refused the request · `1` an error. A `2` is almost
certainly one of: the method file is uncommitted or dirty in this checkout (Step 6 did not land);
a configuration has already run (impossible here — the allocator id is new); or a flat-cost rule
set (impossible — both presets are `gotrade`).
**Impact:** the lab's N moves by exactly **one method** (162 → 163 under `DSR_POLICY = "methods"`),
dev trials 824 → 830, test-window looks stay at 4. `web/data/lab.json` is now stale, so
`engine/tests/test_lab_snapshot.py` is **red by design** until Step 11.

---

### Step 8: Read the result back, before writing a word of analysis

**File:** none (all report-only; none writes a row, moves a status or touches the test window)
**Change:** gather every number the analysis must quote.
**Code:**
```bash
cd "$WT"
for cmd in "show M0258" "control M0258" "walkforward M0258" "status"; do
  f="$OUT/$(echo $cmd | tr ' ' '_').txt"
  "$PY" -m seer_engine lab $cmd > "$f" 2>&1; echo "$cmd RC=$?"
done
grep -n "M0258" "$OUT/status.txt"
```
And the comparison against the host, at matched fees — never against M0072's recorded row directly
if the fee basis differs. M0072 ran from 2026-10-11 and is already on the `-gotrade` preset, so the
recorded row **is** comparable; `lab costs` is the tool only if that ever stops being true:
```bash
"$PY" -m seer_engine lab costs M0072 --candidate M0072-Z2-RAWRANK > "$OUT/costs_m0072.txt" 2>&1
echo "costs RC=$?"
```
**What each one must show:**
- `lab show M0258`: six arms. **Read the money-weighted return first** — "your money earned",
  `trial_funding.mwr`, beside `spy_tr_mwr` for the same deposits into SPY. Then worst fall, PF,
  trades, turnover, exposure, DSR and the `failed` labels. The curve-shape columns
  (`total_return`, `cagr`) are contaminated by the monthly top-ups on every one of these books
  and must not be quoted as a result anywhere.
- `lab control M0258`: four `dose-response` rows (`M0258-M-B0`, `-M-B15`, `-M-B30`, `-M-B60`) with
  verdict `not-checked`, no ratio, and **no `refuse`**. If any row reads `placebo`, a rationale
  picked up a `DRAW_MARKER` and the method file would need an amendment — check it in Step 5 by
  reading the rationales, not here.
- `lab walkforward M0258`: the fold record, which variant each fold picked, and the kin reading.
- `lab status`: `test-window looks used: 4` (I6), dev trials 830, and M0258 under one of
  `Promotable now` / `Refused by the hard gate` / the rejected list.
- `M0258-M-B0` against `M0072-Z2-RAWRANK`: the reproduction check. The two run the same book over
  the same window under different allocator ids, so the trials should agree closely on trades
  (1208), turnover (6.53), exposure (0.695) and worst fall (23.80%). They will **not** be
  bit-identical — the funding path, the fee rounding and the fill simulator are re-run — and the
  lab's own memory says a re-run of a recorded row is not reproducible to the digit (*old trial
  returns are not reproducible*: a recorded +660% re-ran at +545%). **Compare the re-run to the
  re-run**: every claim in the analysis is M0258 arm against M0258 arm, and `M0072-Z2-RAWRANK` is
  quoted only as "the host's recorded row, for orientation".
**Impact:** none. Every command above is a reader.

---

### Step 9: `lab note` — the analysis and the verdict

**File:** `$OUT/analysis.md`, then `lab/lab.sqlite` (`methods.analysis`, append-only)
**Change:** the audit record and the one-line verdict the owner reads on
`seertrade.site/sera/methods/M0258`.
**Shape and content the analysis must have.** The owner is not a quant and reads this on the site.
Plain language, short sentences, markdown is fine; **no ids, no candidate ids, no digests, no
backticks, no code, no file paths**, every number with its meaning ("lost at most 24% from a peak,
where the lab's research screen allows 50%"). Name the arms by what they do — "the version with no
band", "the version that waits for a 3% break, checked once a month" — never by suffix. It must
report, in this order:

1. **What was asked and what was done**, in two or three sentences.
2. **The four paired differences**, each on return *and* worst fall, with the sign stated in words:
   - the monthly 3% band minus the monthly no-band version,
   - the weekly 3% band minus the weekly no-band version,
   - the monthly no-band version minus the weekly no-band version (the cadence alone),
   - the monthly 3% band minus the weekly 3% band.
3. **The ladder's monotonicity**: the four monthly rungs at 0, 1.5, 3 and 6 percent in order, and
   whether the response rises, falls, is flat, or is humped. Say plainly that a hump is a signal
   story and a straight line is a turnover story, because that is the pre-registered reading.
4. **The difference-in-differences**, in one sentence with its number: whether the band's worth at
   the weekly cadence exceeds its worth at the monthly cadence, and by how much, on both axes.
   This is the pre-registered prediction and it must be scored out loud as held or not held.
5. **The reproduction**: whether the no-band monthly arm came back at the host book's recorded
   trade count, turnover, exposure and worst fall, and by how much it differs. If it does not,
   say so first and treat every paired difference in the note as suspect.
6. **Result against SPY** for each arm, **stated as what his money earned** — the money-weighted
   return on his own deposits against the same deposits put into SPY — because that is the only
   figure on a funded book that means what it says; never the curve's total return or CAGR, which
   the monthly top-ups inflate. Then which go-live conditions each arm failed and by how much, and
   the **DSR in words**: how likely the result is real rather than luck after N tries — say the N
   (`lab status` prints it; it will read **163** after this run, under the methods policy) and the
   bar, `DSR ≥ 0.90`, the owner's risk appetite since 2026-10-07. Every paired difference in
   points 2 to 4 above is a difference of money-weighted returns, not of curve returns.
7. **The worst year and when the fall happened**, judged on the book **without** its deposits: the
   monthly top-ups refill a falling account, so a funded fall reads gentler than it was.
8. **The fold verdict**: how many folds, which variant each fold picked, and whether the folds
   favoured the least-trading arm — and if they did, say that the lab already knew they would
   (walk-forward picks each fold's variant by MAR) and that it is weak evidence for the band.
9. **The D17 reading**: that the ladder's rungs are classified as a dose-response and therefore
   carry no shape ratio and cannot be refused, that this method carries no drawn control arm by
   design, and why a drawn one would have been mis-shaped by construction on a monthly stock book
   (a random switch at the gate's own out-rate flips about four times a year against the gate's
   half, and on a twenty-name book each flip is about forty trades, so it would land near seven
   times the arm it controls, far outside the refusal band).
10. **Why** — the mechanism, not the numbers. If the band bought nothing monthly, say that a band
    and a slow reading suppress the same thing and the lab already owns the slow reading.
11. **Whether the hypothesis held and whether the expected failure happened**, each answered
    directly.
12. **A final paragraph starting `My opinion:`** — commit to a view, no hedging: whether this
    direction is worth more trials, what you would try next, and why.

**Code:**
```bash
cd "$WT"
# write $OUT/analysis.md first, then:
"$PY" -m seer_engine lab note M0258 --file "$OUT/analysis.md" \
  --verdict "<one plain line: what the band did to this book, and at which cadence>" \
  > "$OUT/note.txt" 2>&1; echo "note RC=$?"
cat "$OUT/note.txt"
```
**Impact:** `methods.analysis` and `methods.verdict`. **Never pipe this** (I8): since 2026-10-19
`lab note` prints a confirmation line and refuses a byte-identical re-append with exit 2, but a
piped exit code hides whether the first attempt worked and a retried `--file` is how the lab once
got a permanent duplicate the append-only trigger made unremovable.

---

### Step 10: `lab insight` and `lab idea`

**File:** `lab/lab.sqlite` (`insights`, append-only; the ideas backlog)
**Change:** at least one journalled insight and at least one queued idea. A run that queues nothing
is the only real failure the skill recognises.
**The insight to journal.** Kind `observation`, and its point is the thing this method exists to
settle, written for a curious non-trader: *the safety rule's "wait for a clear break" idea and the
habit of only checking once a month do the same job, so doing both buys little.* Name methods by
what they do ("the earnings-jump picker", "the safety rule"), never by id. No code, paths, column
names, hashes or backticks at all, and no number without its meaning. Whatever the run shows, the
body must carry: that the earlier study checked the market every day and the owner's books check
once a month; the measured difference at each checking speed; what this method found on a book that
actually holds stocks; and what to do about it.
**The next idea to queue** — the strongest candidate, and the one this method's cadence grid
actually settles, is the handover's §6 item 3: **the correction row against insight 452's "eleven
exits"**. 452 counted the gate's exits at its monthly checks and reported eleven; insight 464
reported 151 flips across 76 episodes and recorded the discrepancy, but no correction was ever
appended against 452 itself, and `insights` is append-only so an edit is impossible. This method's
grid settles it: **both counts are right, at different reading speeds**, and the number a reader
should use is the one for the cadence their book runs. Queue it as a `feature-wish`-flavoured
`observation` idea or as a plain idea row; the point is that it is cheap, costs no method id, and
removes a standing contradiction two documents on the site currently show the owner.
**Code:**
```bash
cd "$WT"
"$PY" -m seer_engine lab insight --kind observation --method M0258 \
  --title "<a title that says the point, in plain words>" \
  --file "$OUT/insight.md" > "$OUT/insight.txt" 2>&1; echo "insight RC=$?"
cat "$OUT/insight.txt"

"$PY" -m seer_engine lab idea \
  --name "Say how often the safety rule was checked whenever its exits are counted" \
  --family "market-trend-switch" --source-kind variation --parent M0258 \
  --hypothesis "<the correction: eleven exits and seventy-six episodes are the same rule read at two speeds, and every past count should carry the speed it was read at>" \
  > "$OUT/idea.txt" 2>&1; echo "idea RC=$?"
cat "$OUT/idea.txt"
```
**Impact:** one insight row, one idea row. Both append-only. **Never piped** (I8).

---

### Step 11: `lab stage`, and commit the staged pair from the index

**File:** `lab/lab.sqlite` and `web/data/lab.json`, **in the main checkout**
**Change:** regenerate the web snapshot under the database write lock and `git add` both files,
then commit them **from the index**.
**Code:**
```bash
cd "$WT"
"$PY" -m seer_engine lab stage > "$OUT/stage.txt" 2>&1; echo "stage RC=$?"
cat "$OUT/stage.txt"

git -C "$MAIN" status --short lab/lab.sqlite web/data/lab.json
git -C "$MAIN" commit -m "$(cat <<'MSG'
lab: M0258 <rejected|dev-eligible> — <the verdict line, verbatim>

<two or three plain sentences: what the six arms showed, whether the pre-registered
prediction held, and the insight journalled.>

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
git -C "$MAIN" push origin HEAD:main
echo "push RC=$?"
```
**Impact:** this is the commit Vercel redeploys `seertrade.site/sera` from.
**I11, and it is the single easiest thing to get wrong here:** `lab stage` runs from the worktree
but **targets the main checkout** — it regenerates and `git add`s `/home/miftah/seer`'s
`lab/lab.sqlite` and `web/data/lab.json` (memory: *`lab stage` targets the main checkout*). So the
commit must be issued with `-C "$MAIN"` and with **no pathspec**. `git commit -- lab/lab.sqlite
web/data/lab.json` re-reads the working tree and defeats `lab stage`'s staging (memory: *commit the
lab by index, not pathspec*). Never `git add lab/lab.sqlite` by hand.
**If `git -C "$MAIN" status` shows other staged paths** from a sibling session, do not sweep them
in: stash nothing, reset nothing, and ask the coordinator — a shared index is the recorded hazard.

---

### Step 12: `docs/plans/HANDOVER_20261019-the-gate-price-band.md`

**File:** `$WT/docs/plans/HANDOVER_20261019-the-gate-price-band.md` (new file)
**Change:** the next session's brief, in the register of
`HANDOVER_20261019-the-gate-is-out-on-the-wrong-days.md`. It must carry: the dated header with the
lab's state after this run (N, dev trials, test-window looks still 4, insights, next free id
M0259); what this session established, with the six arms' numbers; what is now dead and must not be
re-tested with a method id; the leftovers in priority order, carrying forward the handover's §6
items that remain untouched (the nine D17-blocked methods, the buyback holdability problem,
insight 457's standing text on `/sera`, P2-ENG-N3LB, P3-ENG-V2KQ) and noting that §6 item 3 was
queued as this run's next idea; and the environment notes that save an hour.
**Code:** write it after Step 11 so its header can quote the lab's true post-run state. Commit it
in the worktree by pathspec and push to `main` as in Step 6.
**Impact:** docs only.

---

### Step 13: The full suite, green, at the end

**File:** none
**Change:** prove nothing else moved.
**Code:**
```bash
cd "$MAIN"
PYTHONPATH="$MAIN/engine/src" PG_TEST_URL="$PG_TEST_URL" "$PYTEST" engine/tests \
  > "$OUT/suite.txt" 2>&1; echo "RC=$?"
tail -15 "$OUT/suite.txt"
"$RUFF" check engine > "$OUT/ruff_final.txt" 2>&1; echo "RC=$?"; cat "$OUT/ruff_final.txt"
```
**Expected:** the baseline at `84123cb` was **6028 passed, 3 skipped**. This phase adds six tests in
`test_lab_m0258_band.py` plus thirteen parametrised cases in `test_lab_methods.py` (one purity, six
smoke, six contract), so expect **6047 passed, 3 skipped** — and **zero skips beyond the recorded
three**, because CI fails if the DB tests skip. Ruff prints `All checks passed!`.
**Run it from the MAIN checkout**, with `PYTHONPATH` pointing at the main checkout's `engine/src`
(memory: *worktree tests need PYTHONPATH* — without it pytest silently tests the wrong tree), because
`test_lab_snapshot.py` reads the main checkout's `lab/lab.sqlite` and `web/data/lab.json`, which
Step 11 has just brought back into agreement. Running it before Step 11 is pointless: that one test
is red by design between a lab write and `lab stage`.

---

## Verification

**Build:** there is nothing to build; the gate is the linter.
```bash
/home/miftah/seer/engine/.venv/bin/ruff check /home/miftah/seer/engine
```
→ `All checks passed!`

**Tests:**
```bash
cd /home/miftah/seer && PYTHONPATH=/home/miftah/seer/engine/src \
  PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  engine/.venv/bin/pytest engine/tests -n0
```
→ `6047 passed, 3 skipped` (baseline 6028 + 19). `-n0` because this machine has one core;
`-n auto` is the default in `pyproject.toml` and buys nothing here. Never override `addopts`.

**The study reproduces:**
```bash
cd /home/miftah/seer && engine/.venv/bin/python docs/backtests/2026-10-19-gate-band-cadence.py
```
→ the twelve-row grid in Step 1, to the digit, and the paired differences `+1.82 / +8.4`,
`+2.52 / +15.6`, `−0.12 / −1.7`.

**The run landed:**
```bash
cd /home/miftah/seer && PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab show M0258 \
  > /tmp/claude-1000/-home-miftah-seer/m0258/v_show.txt 2>&1; echo "RC=$?"
```
→ `RC=0`, six arms listed (`M0258-M-B0`, `-M-B15`, `-M-B30`, `-M-B60`, `-W-B0`, `-W-B30`), an
analysis, a verdict.

**The control reading is clean:**
```bash
cd /home/miftah/seer && PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab control M0258 \
  > /tmp/claude-1000/-home-miftah-seer/m0258/v_control.txt 2>&1; echo "RC=$?"
```
→ `RC=0`, four `dose-response` / `not-checked` rows, **no `refuse`**, and the closing line
`every control arm shown matches the shape of the arm it controls`.

**No test-window look was spent, and N moved by exactly one method:**
```bash
cd /home/miftah/seer && PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab status \
  > /tmp/claude-1000/-home-miftah-seer/m0258/v_status.txt 2>&1; echo "RC=$?"
head -8 /tmp/claude-1000/-home-miftah-seer/m0258/v_status.txt
```
→ `test-window looks used: 4` (unchanged), `dev trials … 830` (824 + 6),
`N the luck gate judges at (policy methods): 163` (162 + 1), `insights: 465` or more.

**The database and the web snapshot agree:**
```bash
cd /home/miftah/seer && PYTHONPATH=engine/src engine/.venv/bin/pytest -n0 -q engine/tests/test_lab_snapshot.py
```
→ passed. Red before `lab stage` is expected; red after it is a real failure.

**The staged pair was committed from the index:**
```bash
git -C /home/miftah/seer status --short lab/lab.sqlite web/data/lab.json
git -C /home/miftah/seer log --oneline -3
```
→ no output from `status` (both committed), and the newest commit is the `lab: M0258 …` one.

**Manual check:** read `lab show M0258`'s analysis as the owner would — no ids, no digests, no
backticks, every number with its meaning, ending in a `My opinion:` paragraph.

**Exit criteria** (the plan index's, verbatim, each now bound to a command above):
- `pytest engine/tests -n0` green and `ruff check engine` clean
- `lab run M0258` exited **0** and recorded six dev trials plus one `method_folds` row
- `lab show M0258` prints the six arms; `lab control M0258` reports no `refuse`
- a `lab note` analysis ending in `My opinion:`, a verdict line, ≥1 insight, ≥1 queued idea
- `lab stage` run and both `lab/lab.sqlite` and `web/data/lab.json` committed **from the index**
  in the main checkout
- test-window looks still read **4**; `lab status` N moved by exactly one method
- the handover written

---

## Handoffs

Work found while planning this phase, deliberately left to someone else. None of it belongs in
these steps, and none of it serves R1–R6.

1. **The analysis document quotes a contaminated field, and mislabels it as well.**
   `docs/analyzer/20261019-135550-B4K2_code_analyzer.md`, *Key Considerations* §1, prints
   `M0084-MONTHLY … 393.19%` and `M0101-CTRL … 384.01%`. Two separate problems, and the second
   matters far more than the first.
   - **The units.** `trials.total_return` is `last/first - 1`, a **fraction** — neither a
     percentage nor quite a multiple. The lab's own renderer prints that row as
     `return +39319.3%`, and the multiple is **394.19x**, not 393.19x. An earlier draft of this
     plan called them multiples; that was off by one and is corrected.
   - **The field itself should not be quoted at all.** Every one of these books is funded with the
     owner's monthly top-up, and `backtest/metrics.py` says of `total_return` and `cagr` that they
     are *"deliberately left as they are ... they are not returns at all"* on a funded curve —
     which is the lab's standing note that a funded book's CAGR is a lie. The number to quote is
     `trial_funding.mwr`, the money-weighted return, which `lab show` surfaces as *"your money
     earned"*, beside `spy_tr_mwr` for the same deposits into SPY.
   This plan now quotes `mwr` everywhere — in *What was measured*, in the method-file docstring, in
   the `hypothesis`, and in the cadence writeup — and the curve-shape column is dropped rather than
   carried with a disclaimer. **The analysis document itself has been corrected to quote `mwr`
   too.** No *committed* document upstream was edited: the handover and
   `docs/backtests/2026-10-19-gate-band-study.md` still read as they were written, and correcting
   those is a later session's call, not this phase's. Flagged, not silently fixed.
2. **The nine D17-blocked dev-eligible methods** — M0047, M0201, M0202, M0208, M0215, M0221,
   M0225, M0227, M0243 — each carrying a control arm whose trade count or turnover does not match
   the arm it controls. The remedy costs **no method id**: re-draw the control at the book's own
   shape and record it as an amendment under the existing id. The handover calls this the cheapest
   information left in the lab, and it re-tests nine standing verdicts. Out of scope here, carried
   forward in the Step 12 handover.
3. **The buyback holdability problem** (handover §6 item 2): the cheap-buyback book led by 11.4
   points a year in 2009-2015 on honest prices and won all four out-of-sample stretches, but falls
   55-85% so it cannot be held. A containment problem, not a gate problem.
4. **Insight 457's practical conclusion still stands on `/sera`** ("weight by company size"),
   withdrawn by 462 but, `insights` being append-only, still visible to the owner. Another
   correction row, same shape as the one this phase queues, different subject.
5. **P2-ENG-N3LB** (`name_count.py`'s docstring still calls the dev trial count "the lab's N") and
   **P3-ENG-V2KQ** (append a dated §7.3 revision recording the N policy move to the lab design
   doc). Both pre-existing, both untouched.
6. **`sim.rules.PRESETS` has no weekly fractional Gotrade preset**, so M0258's two weekly arms can
   never be promoted whatever they show. This phase states that in the method file rather than
   minting a preset — that is scope nobody asked for. If the weekly band wins, the next session
   should queue a `feature-wish` insight for the preset, not add one mid-run.
7. **`m0101.band_on` and the study scripts' `band` state machine are not the same function.**
   `band_on` scans back at most `SCAN = 504` sessions for the last crossing and falls back to the
   strict test; the scripts carry state from the first bar. They agree after the opening months of
   a run and can differ before. Noted in both the script and the writeup; nobody should "fix" one
   to match the other, because they serve different purposes.

---

## Rollback

**Before `lab run` (Steps 1–6): everything is reversible.** Nothing was recorded, no method id was
spent.
```bash
cd /home/miftah/.worktrees/seer/gate-price-band
git checkout -- .
rm -f engine/src/seer_engine/lab/methods/m0258_gate_price_band.py \
      engine/tests/test_lab_m0258_band.py \
      docs/backtests/2026-10-19-gate-band-cadence.py \
      docs/backtests/2026-10-19-gate-band-cadence.md
```
If the pre-registration commit was already pushed, revert it on `main` with a new commit; the id
`M0258` is still free until `lab run` touches the database.

**After `lab run` (Step 7 onward): there is no rollback.** `trials`, `method_amendments`,
`insights` and `ideas_seen` are append-only and trigger-protected, and the method id is spent.
That is the design, and it is precisely why the pre-registration is committed first. The
corrections that do exist:
- a wrong **verdict** is corrected by a further `lab note` with a new verdict line;
- a wrong **insight** is corrected by appending a correction row, never by an edit;
- a further question about the same idea is an `Amendment` (committed first, run with
  `lab run --amend`), which spends no method id; a different idea is a new variation method.

**The worktree and branch**, once the work is on `main`:
```bash
git worktree remove /home/miftah/.worktrees/seer/gate-price-band
git branch -D feature/gate-price-band
```
The method file and the staged lab pair will already be on `main` by then, by the lab's own
protocol. That is intended, not a leak.
