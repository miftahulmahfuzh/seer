# Phase 1: Measure the shadow on every chassis, before it is built

**Plan set:** `CONTROL_DRAW_REMEDIES_PLAN.md`
**Analysis:** `docs/analyzer/20261020-113306-C7K4_code_analyzer.md`
**Satisfies:** R1 — the held-set shadow. This phase is the *measurement* half of it: which chassis
the shadow actually moves, and how deep a bounded replay has to go to recover the real entry count.
**Depends on:** none
**Difficulty:** NORMAL
**Package:** scratchpad (`/tmp/claude-1000/-home-miftah-seer/<session>/scratchpad/`) +
`.workflows/plan/control-draw-remedies/`

---

## Goal

After this phase, "the shadow is a no-op on this chassis" is a measured number on all nine of them
instead of an inference from a code-reading table, and the replay depth `K` that phase 2 implements
is read off the dev window rather than guessed. The phase also prices, for free, the one thing
nobody has separated yet: how much of each chassis's estimator error is the *fresh stand-in* and
how much is the *membership convention* each file already documents. It writes no engine code,
records no trial, opens no database for writing, and spends no test-window look.

**The shape of the answer, stated before it is measured.** The estimator the method files feed
`control_draw` today is exactly a **one-step backward replay**: seed an empty book at the previous
decision, apply the chassis's own band once, read the entry count off that. So the remedy is not a
new mechanism — it is the same mechanism run **K steps** instead of one, and the only question is
how large K has to be and whether the 473-bar lookback cap can pay for it. That framing is what
makes this phase cheap: every K shares its chains' prefixes, so all of K = 1…K_max cost one band
application each per decision on top of the one ranking the probe already computes.

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** none
**Renames:** none
**Creates:**
- `/tmp/claude-1000/-home-miftah-seer/<session>/scratchpad/shadow_probe.py` (scratchpad, **not the
  repo** — the phase scope forbids a repo file and nothing later imports it)
- `.workflows/plan/control-draw-remedies/phase-1-results.md` (new, committed)
- `.workflows/plan/control-draw-remedies/phase-1-probe.log` (new, committed — the raw run output,
  so phase 2 and phase 6 can re-read the numbers without re-running the sweep)

**Signature changes:** none
**Requires (from earlier phases):** nothing. Phase 1 is a root of the dependency graph and runs
against `main` @ `e3aeeff` exactly as it stands.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/control_draw.py` — Phase 2
- `engine/tests/test_lab_control_draw*.py` — Phase 2
- `engine/src/seer_engine/lab/methods/m0208_capital_gains_overhang.py` — Phase 3
- `engine/src/seer_engine/lab/control_weight.py`, `m0221`, `m0225`, `m0201` weight work — Phases 4, 5
- `lab/lab.sqlite`, `web/data/lab.json` — Phases 3, 5, 6
- every other file under `engine/src` — read only, never written

**Hands forward to Phase 2 (the contract, in this exact YAML block, inside
`phase-1-results.md` under a heading `## Contract for phase 2`):**

```yaml
probe_run: "<ISO timestamp>"
store_fingerprint: "640fc25e5c7b8f422b1c9ea408ab54f100d82a244eacef3e3dcba67b9ffa1170"
lookback_cap: 473
verdict_band: [0.90, 1.10]
chassis:
  M0047:  {allocator: M0047-A1, reads_held: false, step_bars: 26, k_max: 2,  decisions: NNN, true: NNN, shipped: NNN, ratio: 0.000, k_ratio: {1: 0.000, 2: 0.000}, verdict: "no-op", k_chosen: null}
  M0201:  {allocator: M0201-A1, reads_held: true,  step_bars: 70, k_max: 3,  ...}
  M0202:  {allocator: M0202-A1, reads_held: true,  step_bars: 70, k_max: 3,  ...}
  M0208:  {allocator: M0208-A1, reads_held: true,  step_bars: 26, k_max: 8,  ...}
  M0215:  {allocator: M0215-A1, reads_held: true,  step_bars: 26, k_max: 8,  ...}
  M0221:  {allocator: M0221-A1, reads_held: false, step_bars: 26, k_max: 15, ...}
  M0225:  {allocator: M0221-A1, reads_held: false, step_bars: 26, k_max: 15, ...}
  M0227:  {allocator: M0227-A1, reads_held: false, step_bars: 26, k_max: 15, ...}
  M0243:  {allocator: M0243-A1, reads_held: false, step_bars: 26, k_max: 8,  ...}
shadow_needed: [<the chassis whose ratio falls outside verdict_band>]
redraw_list:   [<the subset of shadow_needed whose chosen K is affordable>]
k_proposed:    {M0208: N, ...}          # the depth this phase PROPOSES, per chassis
lookback_after: {M0208: NNN, ...}       # inner + K * step_bars, each <= 473
m0208_true_entries: NNN                 # the (a) TRUE column's absolute, for phase 3's anchor
m0208_shipped_entries: NNN              # the (b) SHIPPED column's absolute (expect ~304)
stop: false                             # true only if M0208 has no affordable K at 0.90
```

**Phase 2 consumes exactly two things from that block**: `shadow_needed` (which chassis get a v2
adapter at all) and `lookback_after` (the number each new `lookback` must return, asserted against
473). **Phase 2 bakes no K.** `control_draw.shadow_selection` and `shadow_book` take `depth` as a
required keyword-only argument with no default, so the number lives in the **method file**, never
in the shared module.

**Phase 3 consumes `redraw_list`, `k_proposed`, `m0208_true_entries` and
`m0208_shipped_entries`.** The K chain is explicit and it has three links:

1. **Phase 1 proposes.** `k_proposed[M0208]` is the smallest K whose ratio reaches ≥ 0.90 here.
2. **Phase 3 verifies on its own probe and uses its own number.** Phase 3's probe applies
   `CGO-N20`'s own SPY 200-day switch inside the replay, and this probe's `(b) SHIPPED` column
   deliberately reproduces amendment 1's **unguarded** reading. **The two may therefore differ, and
   that is expected, not an error.** Where they disagree, phase 3's number is the one that ships
   and phase 3's results file reports both.
3. **Phase 2 is indifferent to both.** It implements the depth *parameter*, not a depth.

`m0208_true_entries` is carried forward because phase 3 anchors its own forward replay against it
rather than against the literal 624 — see Step 4. No other phase reads this file's numbers.

---

## Files

| File | Action | What changes |
|---|---|---|
| `<scratchpad>/shadow_probe.py` | create | the whole probe; never enters the repo |
| `<scratchpad>/phase-1-probe.log` | create | raw stdout of the full nine-chassis run |
| `.workflows/plan/control-draw-remedies/phase-1-results.md` | create | the table, the verdicts, the contract block |
| `.workflows/plan/control-draw-remedies/phase-1-probe.log` | create | a copy of the raw log, committed beside the results |

No file under `engine/`, `lab/`, `web/` or `db/` is written by this phase.

---

## The measurement, defined before it is taken

Three columns per chassis, over the whole dev window (`MEMBERSHIP_START` = 1996-01-02 to
`DEV_END` = 2015-10-16), on decision dates derived exactly as `book_runner` derives them —
`dates.prev_session(S)` for every `S` where `is_rank_session(MONTHLY_HOLD_FRAC_GOTRADE, S)`:

**(a) TRUE.** A full forward replay of the chassis's own band from the window's start, carrying the
real held set decision by decision. `entries(d) = |book(d) − held(d−1)|`. This is what the real book
does and it is the denominator of every ratio.

**(b) SHIPPED.** A byte-faithful reproduction of the entry count the method file feeds
`control_draw` **today** — including each file's own membership convention, which is today's member
list read at the earlier date. This is the column that has to reproduce the close-out's measured
**0.487×** on M0208; if it does not, the probe is measuring something other than the defect and the
phase stops and says so.

**(c) K.** A K-step backward replay: seed an **empty** book K decisions back, run the chassis's own
band forward to the previous decision, and take the entry count off that. **K = 1 is the shipped
rule with its own-membership convention**, so `(b) − (c@K=1)` prices the membership convention on
its own and the rest of the K curve prices the shadow.

**Three definitions that decide whether the numbers mean anything, each written down because
getting one wrong silently changes the answer:**

1. **Coverage.** A depth-K chain does not exist until K decisions have passed. Comparing a K total
   against the *whole* true total therefore reads low for a reason that has nothing to do with the
   replay — a 40-decision smoke of this probe had M0208's K=8 reading 0.265× purely from that, and
   the curve ran **backwards**. Every ratio in this phase is taken over the decisions that column
   actually covers, and the covered count is printed next to it. This is not a nicety; it inverted
   the conclusion once already.
2. **A cash month resets everything.** Where the chassis's own gate is off (M0208's and M0215's SPY
   200-day switch) or its pool is empty, the real book holds nothing, so the true held set and
   every chain reset to empty and no entry is counted. A bounded replay that crosses a cash month
   is **exact** from there — a real property of the remedy, and the reason the K curve is better
   than K alone suggests. The chains are reset, not discarded, so coverage is not lost.
3. **M0201/M0202 move quarterly.** `m0197.choose` re-picks only when `data_date.month in
   REPICK_MONTHS`, so that chassis's decisions are its 79 re-picks and its backward step is a
   quarter. Its true replay carries the whole previous re-pick's book and does **not** model the
   between-quarter membership attrition `choose`'s else-branch applies. That is a stated
   limitation, it biases the true count slightly **low**, and it must appear in the results file.

### K_max, measured rather than quoted

`allocator.lookback(params)` already pays for one backward step, so the signal's own need is
`inner = lookback − step` and a depth-K replay costs `inner + K × step`, capped at 473.

| chassis | allocator | `lookback` today | step bars | `inner` | **K_max** | cost at K_max |
|---|---|---|---|---|---|---|
| M0047 | `M0047-A1` | 427 | 26 | 401 | **2** | 453 |
| M0201 | `M0201-A1` | 331 | **70** | 261 | **3** | 471 |
| M0202 | `M0202-A1` | 331 | **70** | 261 | **3** | 471 |
| M0208 | `M0208-A1` | 279 | 26 | 253 | **8** | 461 |
| M0215 | `M0215-A1` | 279 | 26 | 253 | **8** | 461 |
| M0221 | `M0221-A1` | 86 | 26 | 60 | **15** | 450 |
| M0225 | `M0221-A1` | 86 | 26 | 60 | **15** | 450 |
| M0227 | `M0227-A1` | 86 | 26 | 60 | **15** | 450 |
| M0243 | `M0243-A1` | 278 | 26 | 252 | **8** | 460 |

**Measured 2026-10-20 by calling `allocator.lookback(params)` on this branch, and it corrects the
analysis in one place:** the analysis's dependency table gives M0201/M0202's quarterly step as 78
bars and one affordable extra step. The constant in the code is `m0201.PREV_SPAN = 70`
(`m0201:346`, `m0202:276`), so the step is **70** and **two** extra steps are affordable — K_max 3,
not 2. The probe computes K_max at run time from `allocator.lookback` and never from this table, so
the table is documentation; the run is the authority. **Record the correction in the results file.**

### The verdict band, and why it is not D17's

`VERDICT_BAND = (0.90, 1.10)`. The 0.90 is the floor the index's own exit criteria already name for
M0208's K search, mirrored to catch an over-count too. It is deliberately **tighter** than D17's
`WARN_BAND` (0.80–1.25): the entry count is one input into a shape that pool attrition then moves,
so an estimator inside ±10 % cannot on its own push a control out of the band D17 judges.

**A ratio within 0.02 of either edge is reported as `borderline`, with both the number and the
sentence "this chassis's verdict would flip on a different window", and is NOT silently rounded
into a verdict.** A 79-decision validation run put M0201 at 0.920 — twenty thousandths off the
edge — so this is a case that exists, not a hypothetical.

---

## Implementation Steps

### Step 1: Record the two invariants' baselines, before anything runs

**File:** none — shell only.
**Change:** capture `lab/lab.sqlite`'s hash and the test-window look count, read through a
read-only URI so nothing can migrate the file (I5, I1).
**Code:**

```bash
cd /home/miftah/seer
git hash-object lab/lab.sqlite | tee /tmp/claude-1000/-home-miftah-seer/$SESSION/scratchpad/db.before
sqlite3 "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" \
  "SELECT count(*) FROM trials WHERE window = 'test';" \
  | tee /tmp/claude-1000/-home-miftah-seer/$SESSION/scratchpad/looks.before
```

Expected at `e3aeeff`: hash `607b78cf69c8e4e3a68a1e84c85eedfd1040c754`, looks `4`.

**Impact:** nothing. A `sqlite3 "file:…?mode=ro"` query never migrates the database; **a `lab`
command can, even a read** — so no `lab` command is run anywhere in this phase.

---

### Step 2: Write the probe to the scratchpad

**File:** `/tmp/claude-1000/-home-miftah-seer/<session>/scratchpad/shadow_probe.py` (new)
**Change:** the whole probe, complete and runnable. It is deliberately **not** a repo file: it
imports private helpers (`m0208._banded_picks`, `m0221.MATCHED._selection`, `m0215._raise_picks`)
that a committed module must not depend on, and nothing in the delivered work imports it.

**Verified:** this file was run against `/home/miftah/seer/engine/.research` on 2026-10-20 before
this plan was written — all nine adapters execute, `ruff check --select E9,F --ignore F401` is
clean, the store loads in ~20 s and each chassis takes 2–4 s for 40–80 decisions. The numbers below
are a **smoke on a truncated window and are not the phase's result**; they are here only as the
signature the implementer should see so a broken adapter is obvious immediately:

| smoke | decisions | true | shipped | ratio | K curve |
|---|---|---|---|---|---|
| M0208 (first 40) | 36 | 132 | 60 | **0.455** | rises monotonically, K=3 → 0.961 |
| M0215 (first 40) | 37 | 32 | 32 | 1.000 | 1.000 at every K |
| M0047 (first 80) | 53 | 477 | 461 | 0.966 | **K=1 → 1.000** (so the 0.034 is membership alone) |
| M0201 (all 79 re-picks) | 79 | 460 | 423 | 0.920 | K=1 → 0.966 |
| M0221/M0225 (first 80) | 79 | 186 | 185 | 0.995 | 1.000 |
| M0227/M0243 (first 80) | 67 | 176 / 363 | 176 / 363 | 1.000 | 1.000 |

**Code:**

```python
"""How wrong is the matched draw's entry count, chassis by chassis, and what would fix it?

`control_draw.matched_names` reads `real_prev` -- the book it controls, as that book stood at the
previous decision -- and no allocator has a record of what any book held. Every caller therefore
substitutes a *freshly derived* selection at the previous decision. On a chassis with a keep band
that stand-in is too fresh: a just-taken top-20 is ranked 1-20 and nothing falls past rank 40,
while a real held set has drifted toward the edge and falls out far faster. The honest-control
close-out measured the cost on M0208 at 0.487x (304 estimated entries against 624 real) and
carried the repair rather than applying it.

This probe measures that gap on every chassis that calls the rule, and prices the only repair a
stateless allocator can make: a BOUNDED BACKWARD REPLAY. It computes three things per chassis.

  (a) TRUE   -- a full forward replay of the chassis's own band from the start of the dev window,
                carrying the real held set from decision to decision. This is what the real book
                actually does, and it is the number the estimator is trying to hit.
  (b) SHIPPED-- a byte-faithful reproduction of what the method file feeds `control_draw` TODAY,
                including each file's own membership convention (today's member list read at the
                earlier date). This is the column that must reproduce the recorded 304 on M0208;
                if it does not, the probe is measuring something else and the phase stops.
  (c) K      -- a K-step backward replay: seed an empty book K decisions back, run the chassis's
                own band forward to the previous decision, and read the entry count off that.
                K = 1 IS the shipped rule with its own-membership convention, so the (b)-(c@1)
                difference prices the membership convention on its own, for free.

K is bounded by the 473-bar lookback cap (`labkit.smoke_market`'s fixture size, absolute): a
backward step costs `PREVIOUS_DECISION_BARS` = 26 bars on a monthly chassis and `PREV_SPAN` = 70
on M0201/M0202's quarterly one, so `K_max = (473 - inner) // step` where `inner` is the
allocator's lookback minus the one step it already pays for. Nothing is hardcoded: K_max is read
off `allocator.lookback(params)` at run time and printed.

The chains for different K share their prefixes -- the chain for (decision i, depth K) starts at
i-K with an empty book, and so does the chain for (i-1, K-1) -- so the probe keeps one live chain
per start index and costs K_max+1 cheap band applications per decision, not sum(K). The expensive
part, the chassis's own ranking, is computed once per decision and reused by every chain.

Four of the nine chassis derive their real book from a function that cannot read `held` at all.
For those the estimator is exact by construction and every column must print 1.000. The probe does
not take that on trust from the analysis: it inspects each real-book function's signature and
prints the evidence, and then runs the replay anyway so a surprise would show.

Writes nothing. Opens no database. Computes no return and models no fee: every number here is an
ENTRY COUNT off the chassis's own calendar, a shape input to `control_draw` and never a trade
count. `trials.trades` includes fills, resizes and pool attrition this does not model.
"""

from __future__ import annotations

import argparse
import gc
import inspect
import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from seer_engine import dates, research
from seer_engine.backtest.dev import DEV_END, MEMBERSHIP_START
from seer_engine.lab.control_draw import PREVIOUS_DECISION_BARS, churn
from seer_engine.lab.methods import m0047_market_value_residual as m0047
from seer_engine.lab.methods import m0201_treasury_beta_size_weighted as m0201
from seer_engine.lab.methods import m0202_treasury_beta_half_guard as m0202
from seer_engine.lab.methods import m0208_capital_gains_overhang as m0208
from seer_engine.lab.methods import m0215_sector_capped_calm_raisers as m0215
from seer_engine.lab.methods import m0221_cap_weighted_top_n as m0221
from seer_engine.lab.methods import m0227_net_share_shrinkers as m0227
from seer_engine.lab.methods import m0243_shrinkers_near_high as m0243
from seer_engine.lab.methods.m0197_treasury_yield_beta import REPICK_MONTHS
from seer_engine.lab.methods.m0197_treasury_yield_beta import choose as yb_choose
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, is_rank_session
from seer_engine.strategies.allocator import prepare_for
from seer_engine.strategies.f_factor import EXCLUDED, trend_on

LOOKBACK_CAP = 473
"""`labkit.smoke_market`'s fixture size. Absolute: an allocator whose lookback exceeds it fails
`test_allocator_contract`, and widening the fixture is not available (invariant I10)."""

VERDICT_BAND = (0.90, 1.10)
"""The band inside which the shipped estimator is called a measured no-op.

The 0.90 is the floor the phase's exit criteria already name for M0208's K search, mirrored. It is
deliberately TIGHTER than D17's `WARN_BAND` (0.80-1.25): the entry count is one input into a shape
that pool attrition then moves, so an estimator inside +/-10% cannot on its own push a control out
of the band D17 judges."""

ERAS: tuple[tuple[str, date, date], ...] = (
    ("1996-2002", date(1996, 1, 1), date(2002, 12, 31)),
    ("2003-2008", date(2003, 1, 1), date(2008, 12, 31)),
    ("2009-2015", date(2009, 1, 1), DEV_END),
)
"""The close-out's own three eras, so 0.444 / 0.509 / 0.500 can be checked against this probe."""


def monthly_decisions() -> list[date]:
    """Every `data_date` a monthly allocator is handed over the dev window.

    `book_runner` ranks on a rank session S and hands the allocator `prev_session(S)`
    (`backtest/book_runner.py:368,393-403`), so the decision dates are the sessions before the
    monthly rank sessions. Identical derivation to the honest-control set's shape probe."""
    return [
        dates.prev_session(s)
        for s in dates.sessions(MEMBERSHIP_START, DEV_END)
        if is_rank_session(MONTHLY_HOLD_FRAC_GOTRADE, s)
    ]


def quarterly_decisions() -> list[date]:
    """The monthly decisions on which M0201/M0202's basket actually moves.

    `m0197.choose` re-picks when `data_date.month in REPICK_MONTHS`; on every other month `_run`
    passes an empty `frac` and the book holds. There is no monthly entry count on that chassis, so
    its decisions are its re-picks and its backward step is a quarter (`PREV_SPAN` bars)."""
    return [d for d in monthly_decisions() if d.month in REPICK_MONTHS]


# --------------------------------------------------------------------------- the chassis table


@dataclass(frozen=True)
class Chassis:
    """One chassis under probe, with its three adapters written out rather than abstracted.

    `rank(prepared, members, d)` returns whatever the band needs at `d` -- a ranked order, a
    fraction map, a row list -- or None when the chassis's own gate is off, which means the real
    book holds nothing that month and its held set resets to empty.

    `book(state, held)` applies the chassis's own band to that state and returns the real book.
    For a chassis whose real book does not read `held`, it ignores the argument.

    `shipped(prepared, members, d)` reproduces the entry count the method file feeds
    `control_draw` TODAY, byte for byte, including that file's own membership convention. None
    when the chassis made no decision that month.

    `real_fn` is the chassis's real-book function, named so the probe can inspect its signature
    for a `held` parameter instead of taking the analysis's table on trust.
    """

    name: str
    allocator: Any
    params: Any
    step_bars: int
    decisions: Callable[[], list[date]]
    prepared: Callable[[Any], Any]
    rank: Callable[[Any, frozenset[str], date], Any]
    book: Callable[[Any, frozenset[str]], tuple[str, ...]]
    shipped: Callable[[Any, frozenset[str], date], int | None]
    real_fn: Any

    def k_max(self) -> int:
        """The deepest replay this chassis can afford under the 473-bar cap.

        `allocator.lookback(params)` already pays for ONE backward step, so the signal's own need
        is `lookback - step_bars` and a depth-K replay costs `inner + K * step_bars`."""
        inner = self.allocator.lookback(self.params) - self.step_bars
        return max(1, (LOOKBACK_CAP - inner) // self.step_bars)

    def reads_held(self) -> bool:
        """True when the chassis's real-book function takes a `held` argument at all."""
        return "held" in inspect.signature(self.real_fn).parameters


# ----- M0208: the keep band, and the whole 0.487x --------------------------------------------

P0208 = m0208.OverhangParams(m0208.N20, keep=40)


def _m0208_rank(prep: Any, members: frozenset[str], d: date) -> tuple[str, ...] | None:
    if not trend_on(prep.history, d, P0208.inner):
        return None
    grid = prep.grid(P0208.market)
    if grid is None:
        return None
    rows = prep.factor.rows_on(members, d, P0208.inner)
    if not rows:
        return None
    sc = m0208.scored(grid, rows, d, P0208)
    if not sc:
        return None
    return tuple(sorted(sc, key=lambda s: (-sc[s], s)))


def _m0208_book(order: tuple[str, ...], held: frozenset[str]) -> tuple[str, ...]:
    return tuple(m0208._banded_picks(order, held, P0208.inner.top, P0208.keep))


def _m0208_shipped(prep: Any, members: frozenset[str], d: date) -> int | None:
    """`MatchedDrawAllocator._targets`, lines 1-9, with nothing else.

    Note the membership: `rows` is read ONCE, at `d`, and the previous session is scored off those
    same rows -- today's member list used at the earlier date, which the file documents and which
    this reproduces exactly."""
    if not trend_on(prep.history, d, P0208.inner):
        return None
    grid = prep.grid(P0208.market)
    if grid is None:
        return None
    rows = prep.factor.rows_on(members, d, P0208.inner)
    if not rows:
        return None
    sc = m0208.scored(grid, rows, d, P0208)
    if not sc:
        return None
    order = sorted(sc, key=lambda s: (-sc[s], s))
    picks_prev: tuple[str, ...] = ()
    before_date = m0208.previous_month_end(grid, d)
    if before_date is not None:
        before = m0208.scored(grid, rows, before_date, P0208)
        picks_prev = tuple(sorted(before, key=lambda s: (-before[s], s))[: P0208.inner.top])
    picks_real = m0208._banded_picks(order, frozenset(picks_prev), P0208.inner.top, P0208.keep)
    return churn(picks_real, picks_prev)


# ----- M0215: calm raisers, where `held` only reorders ---------------------------------------

P0215 = m0215.CapParams(m0215.C63, None, "hash", 1)
B0215 = P0215.calm.ann.base


def _m0215_rank(prep: Any, members: frozenset[str], d: date) -> tuple[date, list[Any]] | None:
    if len(prep.calendar) == 0:
        return None
    if not trend_on(prep.history, d, B0215.inner):
        return None
    rows = m0215._rows_on(prep, members, d, B0215.inner)
    return (d, rows) if rows else None


def _m0215_book(prep: Any, state: tuple[date, list[Any]], held: frozenset[str]) -> tuple[str, ...]:
    d, rows = state
    return tuple(m0215._raise_picks(prep, rows, d, held, P0215))


def _m0215_shipped(prep: Any, members: frozenset[str], d: date) -> int | None:
    """`MatchedCapPlaceboAllocator._run`'s own two lines: `_target_shape` then `churn`."""
    if len(prep.calendar) == 0 or not trend_on(prep.history, d, B0215.inner):
        return None
    rows = m0215._rows_on(prep, members, d, B0215.inner)
    if not rows:
        return None
    now, prev = m0215._target_shape(prep, members, rows, d, P0215)
    return churn(now, prev)


# ----- M0201 / M0202: the quarterly 40% keep band --------------------------------------------

P0201 = m0201._p("placebo", seed=1)
P0202 = m0202._p("placebo", "half", seed=1)


def _yb_book(frac: dict[str, float], held: frozenset[str], top: int,
             keep_pct: int, market: str) -> tuple[str, ...]:
    """`m0197.choose`'s re-pick selection, names only -- its first ten lines, written out.

    `choose` is a closed record of six recorded trials and is never imported for its targets here;
    only its SELECTION is reproduced, which is what an entry count reads."""
    stocks = sorted(s for s in held if s != market and s not in EXCLUDED)
    order = [s for _, s in sorted((v, s) for s, v in frac.items())]
    cut = keep_pct / 100.0
    kept = sorted((s for s in stocks if frac.get(s, 1.0) < cut), key=lambda s: (frac[s], s))
    picks = kept[:top]
    for s in order:
        if len(picks) >= top:
            break
        if s not in picks:
            picks.append(s)
    return tuple(picks)


def _m0201_rank(prep: Any, members: frozenset[str], d: date) -> dict[str, float] | None:
    frac = m0201.real_frac_at(prep, members, d, P0201)
    return frac or None


def _m0201_book(frac: dict[str, float], held: frozenset[str]) -> tuple[str, ...]:
    yb = P0201.yb
    return _yb_book(frac, held, yb.inner.top, yb.keep_pct, yb.market)


def _m0201_shipped(prep: Any, members: frozenset[str], d: date) -> int | None:
    now = m0201.real_frac_at(prep, members, d, P0201)
    if not now:
        return None
    return m0201.matched_entries(prep, members, d, now, P0201)


def _m0202_rank(prep: Any, members: frozenset[str], d: date) -> dict[str, float] | None:
    frac = m0202.real_frac_at(prep, members, d, P0202)
    return frac or None


def _m0202_book(frac: dict[str, float], held: frozenset[str]) -> tuple[str, ...]:
    yb = P0202.yb
    return _yb_book(frac, held, yb.inner.top, yb.keep_pct, yb.market)


def _m0202_shipped(prep: Any, members: frozenset[str], d: date) -> int | None:
    now = m0202.real_frac_at(prep, members, d, P0202)
    if not now:
        return None
    return m0202.matched_entries(prep, members, d, now, P0202)


# ----- the four that cannot read `held` -------------------------------------------------------

P0047 = m0047.SizeParams(m0047.RANKING, picks="placebo", weighting="size", cap=0.10, seed=1)
P0221 = m0221.CapTopParams(50, pick="random", seed=1, trend=None)
P0227 = m0227.IssuanceParams(20, side="random", seed=1, trend=None)
P0243 = m0243.NearShrinkParams(20, cut=2, side="near", pick="random", seed=1, trend=None)


def _m0047_rank(prep: Any, members: frozenset[str], d: date) -> tuple[str, ...] | None:
    if prep.market is None or len(prep.market.shares) == 0:
        return None
    now, _ = m0047.MATCHED._real_book(prep, members, d, P0047)
    return now or None


def _m0047_shipped(prep: Any, members: frozenset[str], d: date) -> int | None:
    from seer_engine.lab.control_draw import previous_decision_date
    now = _m0047_rank(prep, members, d)
    if now is None:
        return None
    before, _ = m0047.MATCHED._real_book(prep, members, previous_decision_date(d), P0047)
    return churn(now, before)


def _m0221_rank(prep: Any, members: frozenset[str], d: date) -> tuple[str, ...] | None:
    if prep.market is None:
        return None
    if not trend_on(prep.history, d, m0221._gate(P0221)):
        return None
    now, pool = m0221.MATCHED._selection(prep, members, d, P0221)
    return now or None


def _m0221_shipped(prep: Any, members: frozenset[str], d: date) -> int | None:
    from seer_engine.lab.control_draw import previous_decision_date
    now = _m0221_rank(prep, members, d)
    if now is None:
        return None
    before, _ = m0221.MATCHED._selection(prep, members, previous_decision_date(d), P0221)
    return churn(now, before)


def _sel_rank(alloc: Any, params: Any, prep: Any, members: frozenset[str],
              d: date) -> tuple[str, ...] | None:
    """M0227's and M0243's shared shape: `_select` behind the same momentum-screen gate."""
    from seer_engine.strategies.f_factor import FactorParams
    if prep.market is None:
        return None
    gate = FactorParams(rank="momentum", top=params.top, trend=params.trend)
    if not trend_on(prep.history, d, gate):
        return None
    _, now = alloc._select(prep, members, d, params)
    return now or None


def _sel_shipped(alloc: Any, params: Any, prep: Any, members: frozenset[str],
                 d: date) -> int | None:
    from seer_engine.lab.control_draw import previous_decision_date
    now = _sel_rank(alloc, params, prep, members, d)
    if now is None:
        return None
    _, before = alloc._select(prep, members, previous_decision_date(d), params)
    return churn(now, before)


CHASSIS: tuple[Chassis, ...] = (
    Chassis("M0047", m0047.MATCHED, P0047, PREVIOUS_DECISION_BARS, monthly_decisions,
            lambda mk: prepare_for(m0047.MATCHED, mk),
            _m0047_rank, lambda st, held: st, _m0047_shipped,
            m0047.MatchedDrawAllocator._real_book),
    Chassis("M0201", m0201.MATCHED, P0201, m0201.PREV_SPAN, quarterly_decisions,
            lambda mk: prepare_for(m0201.MATCHED, mk),
            _m0201_rank, _m0201_book, _m0201_shipped, yb_choose),
    Chassis("M0202", m0202.MATCHED, P0202, m0202.PREV_SPAN, quarterly_decisions,
            lambda mk: prepare_for(m0202.MATCHED, mk),
            _m0202_rank, _m0202_book, _m0202_shipped, yb_choose),
    Chassis("M0208", m0208.MATCHED, P0208, PREVIOUS_DECISION_BARS, monthly_decisions,
            lambda mk: prepare_for(m0208.MATCHED, mk),
            _m0208_rank, _m0208_book, _m0208_shipped, m0208._banded_picks),
    Chassis("M0215", m0215.MATCHED, P0215, PREVIOUS_DECISION_BARS, monthly_decisions,
            lambda mk: prepare_for(m0215.MATCHED, mk),
            _m0215_rank, None, _m0215_shipped, m0215._raise_picks),  # book bound in run()
    Chassis("M0221", m0221.MATCHED, P0221, PREVIOUS_DECISION_BARS, monthly_decisions,
            lambda mk: prepare_for(m0221.MATCHED, mk),
            _m0221_rank, lambda st, held: st, _m0221_shipped,
            m0221.MatchedCapTopAllocator._selection),
    Chassis("M0225", m0221.MATCHED, P0221, PREVIOUS_DECISION_BARS, monthly_decisions,
            lambda mk: prepare_for(m0221.MATCHED, mk),
            _m0221_rank, lambda st, held: st, _m0221_shipped,
            m0221.MatchedCapTopAllocator._selection),
    Chassis("M0227", m0227.MATCHED, P0227, PREVIOUS_DECISION_BARS, monthly_decisions,
            lambda mk: prepare_for(m0227.MATCHED, mk),
            lambda p, m, d: _sel_rank(m0227.MATCHED, P0227, p, m, d),
            lambda st, held: st,
            lambda p, m, d: _sel_shipped(m0227.MATCHED, P0227, p, m, d),
            m0227.MatchedDrawAllocator._select),
    Chassis("M0243", m0243.MATCHED_NEAR, P0243, PREVIOUS_DECISION_BARS, monthly_decisions,
            lambda mk: prepare_for(m0243.MATCHED_NEAR, mk),
            lambda p, m, d: _sel_rank(m0243.MATCHED_NEAR, P0243, p, m, d),
            lambda st, held: st,
            lambda p, m, d: _sel_shipped(m0243.MATCHED_NEAR, P0243, p, m, d),
            type(m0243.MATCHED_NEAR)._select),
)


# --------------------------------------------------------------------------- the replay


def era_of(d: date) -> str:
    for name, lo, hi in ERAS:
        if lo <= d <= hi:
            return name
    return "outside"


@dataclass
class Row:
    """One decision: the true entry count, the shipped estimate, and each depth's estimate.

    `k` is sparse on purpose. A depth-K chain does not exist until K decisions have passed, so
    the K column covers fewer decisions than the true column does, and a K total compared against
    the WHOLE true total would read low for a reason that has nothing to do with the replay. Every
    ratio below is therefore taken over the decisions that column actually covers.
    """

    d: date
    true: int
    shipped: int | None
    k: dict[int, int]


def run(ch: Chassis, market: Any, limit: int | None, verbose: bool) -> dict[str, Any]:
    """One chassis: the true forward replay, the shipped estimator, and every affordable K."""
    t0 = time.monotonic()
    prep = ch.prepared(market)
    book = ch.book
    if ch.name == "M0215":
        def book(st, held, _p=prep):  # noqa: ANN001
            return _m0215_book(_p, st, held)
    k_max = ch.k_max()
    ds = ch.decisions()
    if limit is not None:
        ds = ds[:limit]

    rows: list[Row] = []
    true_held: frozenset[str] = frozenset()
    chains: dict[int, frozenset[str]] = {}  # start index -> that chain's held after decision i-1
    gate_off = 0

    for i, d in enumerate(ds):
        members = frozenset(market.membership.members_on(d))
        state = ch.rank(prep, members, d)
        if state is None:
            # The chassis's own gate is off (or its pool is empty): the real book holds nothing,
            # so every held set resets to empty, exactly as the book engine empties a book on an
            # empty target tuple. The chains are RESET rather than dropped -- a bounded replay
            # that crosses a cash month is exact from there, and that is a real property of the
            # remedy, not an artefact.
            true_held = frozenset()
            chains = dict.fromkeys(chains, frozenset())
            gate_off += 1
            continue

        now = frozenset(book(state, true_held))
        row = Row(d=d, true=len(now - true_held), shipped=ch.shipped(prep, members, d), k={})
        true_held = now

        for start in sorted(chains):
            depth = i - start
            if depth > k_max:
                continue
            prev_est = chains[start]
            now_est = frozenset(book(state, prev_est))
            row.k[depth] = len(now_est - prev_est)
            chains[start] = now_est
        chains[i] = frozenset(book(state, frozenset()))
        for start in [s0 for s0 in list(chains) if i - s0 > k_max]:
            del chains[start]

        rows.append(row)
        if verbose and len(rows) <= 5:
            print(f"    {d}: true={row.true} shipped={row.shipped} k={row.k}")

    out = {
        "name": ch.name, "allocator": ch.allocator.id, "decisions": len(rows),
        "gate_off": gate_off, "k_max": k_max, "reads_held": ch.reads_held(),
        "lookback": ch.allocator.lookback(ch.params), "step": ch.step_bars,
        "rows": rows, "seconds": time.monotonic() - t0,
    }
    del prep
    gc.collect()
    return out


def ratio(a: int, b: int) -> float:
    return a / b if b else float("nan")


def column(rows: Sequence[Row], pick) -> tuple[int, int, int]:  # noqa: ANN001
    """(the column's entries, the true entries on the SAME decisions, how many decisions)."""
    est = true = n = 0
    for r in rows:
        v = pick(r)
        if v is None:
            continue
        est += v
        true += r.true
        n += 1
    return est, true, n


def era_column(rows: Sequence[Row], pick, era: str) -> tuple[int, int]:  # noqa: ANN001
    est, true, _ = column([r for r in rows if era_of(r.d) == era], pick)
    return est, true


def report(r: dict[str, Any]) -> None:
    rows: list[Row] = r["rows"]
    t_all = sum(x.true for x in rows)
    print(f"\n=== {r['name']}  ({r['allocator']}, lookback {r['lookback']}, step {r['step']} bars, "
          f"K_max {r['k_max']})")
    print(f"    real book reads `held`: "
          f"{'YES' if r['reads_held'] else 'NO -- exact by construction'}")
    print(f"    decisions {r['decisions']} (no book on {r['gate_off']})   "
          f"elapsed {r['seconds']:.1f}s")
    print(f"    (a) TRUE forward replay        {t_all:6d} entries over {len(rows)} decisions")
    se, st, sn = column(rows, lambda x: x.shipped)
    print(f"    (b) SHIPPED estimator          {se:6d} entries   ratio {ratio(se, st):.3f}"
          f"   ({sn} decisions)")
    for k in range(1, r["k_max"] + 1):
        ke, kt, kn = column(rows, lambda x, k=k: x.k.get(k))
        print(f"    (c) K={k:<2d} backward replay      {ke:6d} entries   ratio {ratio(ke, kt):.3f}"
              f"   ({kn} decisions)")
    print("    eras, shipped against true on the same decisions:")
    for name, _, _ in ERAS:
        e, t = era_column(rows, lambda x: x.shipped, name)
        print(f"      {name}  true {t:5d} | shipped {e:5d} | {ratio(e, t):.3f}")
    lo, hi = VERDICT_BAND
    rr = ratio(se, st)
    verdict = "no-op" if lo <= rr <= hi else "SHADOW-NEEDED"
    print(f"    VERDICT: {verdict}  (shipped/true = {rr:.3f}, band {lo}-{hi})")
    if verdict != "no-op":
        best = None
        for k in range(1, r["k_max"] + 1):
            ke, kt, _ = column(rows, lambda x, k=k: x.k.get(k))
            if ratio(ke, kt) >= 0.90:
                best = k
                break
        inner = r["lookback"] - r["step"]
        if best is not None:
            ke, kt, _ = column(rows, lambda x, k=best: x.k.get(k))
            print(f"    smallest K reaching >= 0.90 of true: K={best} (ratio "
                  f"{ratio(ke, kt):.3f}, lookback {inner + best * r['step']} of {LOOKBACK_CAP})")
        else:
            print(f"    NO affordable K reaches 0.90 of true on {r['name']} "
                  f"(K_max {r['k_max']} costs {inner + r['k_max'] * r['step']} of {LOOKBACK_CAP})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--store", default=os.environ.get("SEER_RESEARCH_STORE",
                                                      "/home/miftah/seer/engine/.research"))
    ap.add_argument("--chassis", default="", help="comma-separated subset, e.g. M0208,M0215")
    ap.add_argument("--limit", type=int, default=None, help="first N decisions only (smoke)")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    want = {x.strip().upper() for x in a.chassis.split(",") if x.strip()}
    chosen = [c for c in CHASSIS if not want or c.name in want]

    print(f"store {a.store}")
    t0 = time.monotonic()
    data = research.load_store(Path(a.store))
    market = data.market
    print(f"loaded {len(market.history)} symbols in {time.monotonic() - t0:.1f}s; "
          f"shares={len(market.shares)} series={'yes' if len(market.series) else 'NO'} "
          f"dividends={'yes' if len(market.dividends) else 'NO'}")

    results = []
    for ch in chosen:
        print(f"\n--- probing {ch.name} ...", flush=True)
        results.append(run(ch, market, a.limit, a.verbose))
        report(results[-1])

    print("\n\n=== SUMMARY =================================================================")
    print(f"{'chassis':8} {'held?':6} {'dec':>4} {'true':>6} {'shipped':>8} {'ratio':>7} "
          f"{'Kmax':>5} {'K@0.90':>7}  verdict")
    for r in results:
        rows = r["rows"]
        se, st, _ = column(rows, lambda x: x.shipped)
        rr = ratio(se, st)
        lo, hi = VERDICT_BAND
        verdict = "no-op" if lo <= rr <= hi else "SHADOW-NEEDED"
        best = "none"
        for k in range(1, r["k_max"] + 1):
            ke, kt, _ = column(rows, lambda x, k=k: x.k.get(k))
            if ratio(ke, kt) >= 0.90:
                best = str(k)
                break
        print(f"{r['name']:8} {'yes' if r['reads_held'] else 'no':6} {r['decisions']:4d} "
              f"{sum(x.true for x in rows):6d} {se:8d} {rr:7.3f} {r['k_max']:5d} {best:>7}  "
              f"{verdict}")


if __name__ == "__main__":
    main()
```

**Impact:** nothing outside the scratchpad. The probe imports nine method modules and the research
store; it writes no file, opens no database and calls no `lab` command.

**The three adapter shapes, so a reviewer can check them against the method files without reading
the whole script:**

| chassis | `rank(d)` returns | `book(state, held)` is | `shipped(d)` reproduces |
|---|---|---|---|
| M0208 | the full overhang order at `d` (`scored` → sorted) | `m0208._banded_picks(order, held, 20, 40)` | `MatchedDrawAllocator._targets`' first nine lines, `previous_month_end` and all |
| M0215 | `(d, rows)` from `m0215._rows_on` | `m0215._raise_picks(prep, rows, d, held, P)` | `m0215._target_shape` then `control_draw.churn` |
| M0201 / M0202 | `real_frac_at(d)` | `m0197.choose`'s selection, written out (names only) | `m0201.matched_entries` / `m0202.matched_entries`, unchanged |
| M0047 | `MATCHED._real_book(d)` | `held` ignored | `churn(real(d), real(previous_decision_date(d)))` |
| M0221 / M0225 | `MATCHED._selection(d)` | `held` ignored | same |
| M0227 / M0243 | `MATCHED._select(d)` | `held` ignored | same |

`m0197.choose`'s selection is **written out** in `_yb_book` rather than imported, for the same
reason M0208's own file writes its band out twice: `choose` is the recorded path of six closed
trials, and a probe that reached into it would be one refactor away from moving a closed record.
Only the *selection* is reproduced; its targets, weights and SPY filler are never touched.

**The `reads_held` column is evidence, not an assumption.** `Chassis.reads_held()` inspects the
signature of each chassis's own band function and reports whether it takes a `held` parameter at
all. Four of the nine do not, and for those every column must print `1.000` or the probe has a bug.
The analysis's "How each chassis supplies `real_prev` today" table is thereby confirmed by the run
instead of carried forward on trust — which the phase scope asked for explicitly.

---

### Step 3: Run the full sweep, once, redirected and never piped

**File:** none — shell only.
**Change:** one process, all nine chassis, whole dev window.

```bash
cd /home/miftah/seer
S=/tmp/claude-1000/-home-miftah-seer/$SESSION/scratchpad
SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
PYTHONPATH=/home/miftah/seer/engine/src \
/home/miftah/seer/engine/.venv/bin/python $S/shadow_probe.py \
    > $S/phase-1-probe.log 2>&1
echo "exit=$?"
tail -40 $S/phase-1-probe.log
```

**Redirection, never a pipe** (I4): `grep` or `tee` in a pipeline owns the exit status and a
non-zero run would read as a clean one.

**Cost and budget, measured not guessed.** The store loads in ~20 s and holds 539 symbols at
roughly 1.79 MB each (~965 MB resident); each chassis then takes **2–4 s per 40–80 decisions**, so
the whole nine-chassis sweep over 238 monthly decisions is **well under five minutes**. One process
only: the probe reuses a single loaded `Market` across all nine chassis and frees each `prepared`
with `gc.collect()` after use. **Never run two sweeps at once** — a parallel wave took this laptop
down twice in the twenty-four hours before this plan was written, and this probe plus any
`dev.run_registry` sweep is two copies of the store.

If the machine is tight, run it in three passes with `--chassis` and concatenate the logs:
`--chassis M0221,M0225,M0227` (cheapest), then `--chassis M0047,M0201,M0202`, then
`--chassis M0208,M0215,M0243`. The SUMMARY block is per-run, so a split run needs the per-chassis
`===` blocks read instead; say in the results file that it was split.

**Impact:** read-only. Nothing is written but the log.

---

### Step 4: Check the probe against the one number that already exists

**File:** none — judgement, recorded in Step 5's results file.
**Change:** before any verdict is believed, M0208's SHIPPED column is checked against the
honest-control close-out's recorded measurement.

The close-out measured, over all **169** of M0208's decisions: **304 estimated entries against 624
real, 0.487×, uniform across eras at 0.444 / 0.509 / 0.500**
(`docs/plans/HANDOVER_20261019-the-honest-control.md:384-386`).

**What must be true:** M0208's `(b) SHIPPED / (a) TRUE` lands at **0.487 ± 0.03**, its three era
ratios bracket 0.444–0.509, and its decision count is near 169.

**Two ways it can legitimately differ, and what each means:**

- **The decision count.** The probe counts a decision only where the chassis produced a book; the
  SPY 200-day switch is off for some months and the first years are short of the 156 weeks the
  overhang needs. A count of 160–175 is the expected band. A count far outside it means the
  decision-date derivation is wrong, and the phase stops and fixes that before reading anything.
- **The absolute totals. This is a live possibility, not a hypothetical, and the plan set treats
  "624 real entries" as *624 as the close-out recorded it, to be confirmed here*.**
  `M0208-CGO-N20`'s recorded `trials.trades` is **also 624**, and an entry count and a trade count
  are not the same quantity: a book that takes in `e` names and lets `e` go makes about `2e` basket
  changes before fills and resizes. If the probe's TRUE lands near **1248** rather than 624 while
  the **ratio** still reads ~0.487, then the close-out's "624 real" was a trade count standing in
  for an entry count, the *ratio* is unaffected, and the results file **says so in one plain
  sentence**. **The ratio is the finding; the absolute is a cross-check.** Whatever the probe
  reads, it goes into the contract block as `m0208_true_entries`: **phase 3 anchors against that
  number, not against 624**, and **phase 6 owns the correction of any published sentence that
  quotes the figure** (R3). This phase corrects nothing the owner reads.

**If the ratio is not near 0.487 at all** — say it reads 0.9 — then the probe is not measuring the
defect the set exists to fix. **Stop.** Write `phase-1-results.md` with verdict `STOP (probe does
not reproduce the recorded 0.487)`, the numbers, and the three candidate causes (decision dates,
membership convention, the band adapter), and do not run phase 2.

**Impact:** this is the phase's own self-check and it gates everything downstream.

---

### Step 5: Write `phase-1-results.md`

**File:** `.workflows/plan/control-draw-remedies/phase-1-results.md` (new)
**Change:** the deliverable. It must contain, in this order:

1. **The header** — date, branch and base commit, store fingerprint
   (`640fc25e5c7b8f422b1c9ea408ab54f100d82a244eacef3e3dcba67b9ffa1170`), the probe's path, and the
   command that produced the log.
2. **The 0.487 cross-check from Step 4**, pass or fail, with the three era ratios beside the
   close-out's 0.444 / 0.509 / 0.500 — and the "entries vs trades" sentence if the absolutes
   disagree while the ratio holds.
3. **The main table**, one row per chassis, columns: `reads_held`, decisions, **true**,
   **shipped**, `shipped/true`, then one column per K from 1 to that chassis's K_max (ratio and
   covered-decision count), and the verdict word.
4. **The per-chassis verdict**, one word each — `shadow needed` / `measured no-op` / `borderline` —
   **with the ratio that decides it**, in the same sentence. Nine rows, no chassis omitted. The
   four signature-confirmed no-held chassis say so explicitly: *"confirmed by signature and by
   replay, not by coincidence."*
5. **M0208's K answer**: the smallest K whose ratio reaches **≥ 0.90** of true, the ratio at that
   K, the lookback it costs (`253 + 26K`) and the headroom left to 473. Plus the whole K curve, so
   phase 2 can see whether the gain is still rising at K_max.
6. **The K answer for every other chassis the verdict marks `shadow needed` or `borderline`** — the
   same three numbers. A chassis marked `measured no-op` needs no K and the file says `n/a`.
7. **The lookback correction** — M0201/M0202's step is `PREV_SPAN = 70`, not the 78 the analysis
   quotes, so K_max is 3 and not 2.
8. **The membership decomposition** — for every chassis, `shipped` against `K=1`. Where they differ
   the gap is the membership convention alone (today's member list read at the earlier date), and
   **no amount of shadow depth closes it**. This is a free finding of this phase and phase 2 must
   not try to fix it: it is a different defect, and it goes in Handoffs.
9. **The stated limitations**, verbatim: the M0201/M0202 between-quarter attrition simplification;
   that entry counts are not trade counts and pool attrition moves the realised figure at run time
   (M0208's 0.487 estimate landed at 0.73× realised); and that `lab control`'s recorded-vs-recorded
   verdict is the only thing that settles a shape, never this probe.
10. **`## Contract for phase 2`** — the YAML block given in the Interface Contract above, filled in.
11. **The invariant line**: `git hash-object lab/lab.sqlite` before and after, and looks 4 → 4.

Copy the raw log in beside it:

```bash
cp /tmp/claude-1000/-home-miftah-seer/$SESSION/scratchpad/phase-1-probe.log \
   /home/miftah/seer/.workflows/plan/control-draw-remedies/phase-1-probe.log
```

**Impact:** phases 2 and 3 are written against this file. A verdict missing from it is a chassis
phase 2 will not implement.

---

### Step 6: Apply the STOP rule, then commit

**File:** none — judgement, then one commit.
**Change:**

**The STOP rule, in full.** *If no affordable K reaches 0.90 of the true entry count on M0208*
— that is, if every K from 1 to 8 reads below 0.90 and `253 + 26×8 = 461` is already the deepest
replay the 473-bar cap allows — **then a bounded replay is not the remedy, and phases 2 and 3 do
not run as designed.**

In that case `phase-1-results.md` must contain, and must contain nothing that softens them:

- A top line reading exactly **`VERDICT: STOP — a bounded backward replay does not recover M0208's
  entry count inside the lookback cap.`**
- The full K curve for M0208, K = 1…8, each with its ratio and covered-decision count, so the
  reader can see whether it was still climbing at K_max or had flattened. **These are two different
  findings** and the file must say which: *still climbing* means the cap is the binding constraint
  and a future change to `labkit.smoke_market` would reopen it; *flattened below 0.90* means depth
  is not the mechanism and no cap change would help.
- The lookback arithmetic: `253 + 26×8 = 461`, headroom 12 bars, which is less than one more step.
- The sentence **"M0208's published lead stays a floor"** — its verdict today says the book beat a
  meaningless book *"by at least 4.3 points a year — provisional, and a floor rather than a
  measurement"*, and a STOP here means nothing in this set turns that into a number.
- An explicit instruction to the coordinator: **run phase 4 next**, not phase 2. Phase 4 depends on
  nothing, carries its own STOP, and is the remaining half of the set.
- The other eight chassis's verdicts anyway. A STOP on M0208 does not void the measurement on the
  rest, and "the shadow is a measured no-op on eight of nine chassis" is itself a result that
  closes most of leftover 3.

A STOP here costs no method id, no trial, no N and no test-window look. **It is a legitimate
outcome and the phase must not invent a ninth or tenth K to avoid it** — K_max is set by the cap,
not by preference.

**Commit, by pathspec, on `main`** (the checkout is shared; never `git add -A`, never
`reset --hard`, never `pull --rebase` while another phase is running).

**If the push is rejected, merge — never rebase.** `git fetch origin` then
`git merge origin/main`, then push again. A `pull --rebase` replays a stale `lab/lab.sqlite` over
the live shared file other sessions in this set are writing
(`seer-rebase-replays-stale-lab-sqlite`). This phase writes no lab row, but it shares the checkout
with phases that do.

```bash
cd /home/miftah/seer
git add .workflows/plan/control-draw-remedies/phase-1.md \
        .workflows/plan/control-draw-remedies/phase-1-results.md \
        .workflows/plan/control-draw-remedies/phase-1-probe.log
git commit -m "lab: the held-set shadow, measured on all nine chassis before it is built"
git push
```

No `lab stage` runs in this phase — it writes no lab row, so there is nothing to stage, and
`lab stage` would regenerate `web/data/lab.json` for no reason.

**Impact:** `.workflows/plan/` only.

---

## Verification

**Build:** nothing is built. `engine/.venv/bin/ruff check --select E9,F --ignore F401
<scratchpad>/shadow_probe.py` — clean (verified 2026-10-20).

**Tests:** the phase changes no engine code, so the suite's state is the baseline's. Run it once at
the end anyway, because I11 asks every phase to leave the tree green and because it is the cheapest
possible proof that nothing was edited by accident:

```bash
cd /home/miftah/seer
PYTHONPATH=/home/miftah/seer/engine/src /home/miftah/seer/engine/.venv/bin/pytest engine/tests -q
PYTHONPATH=/home/miftah/seer/engine/src /home/miftah/seer/engine/.venv/bin/ruff check engine
git status --porcelain engine lab web db     # must print nothing
```

**Manual check:** the four `reads_held: false` chassis (M0047, M0221, M0225, M0227, M0243 — five
rows, four chassis families) must print `1.000` at **K = 1**. Any other number there is a probe bug,
not a finding, because their real-book functions take no `held` argument at all. Note that their
**shipped** column may still differ from 1.000 — that is the membership convention, and M0047's
0.966/1.000 split in the validation run is exactly that.

**Exit criteria** — the index's Phase 1 block, quoted verbatim, each expanded into something
checkable:

> *"A table, one row per chassis (M0047, M0201, M0202, M0208, M0215, M0221, M0225, M0227, M0243),
> giving over the whole dev window: the true cumulative entry count of the real book from a full
> forward replay of its own band; the current estimator's count; and a K-step backward replay's
> count for every K from 1 to that chassis's affordable maximum."*

→ `grep -c '^| M0' phase-1-results.md` is **9**; the SUMMARY block of
`phase-1-probe.log` lists nine rows; each chassis's `===` block prints `(c) K=1` through
`(c) K=<its K_max>` with no gap.

> *"A per-chassis verdict in one word: shadow needed or shadow is a measured no-op, with the ratio
> that decides it."*

→ nine lines of the form `M0208 — shadow needed (shipped/true = 0.4xx)`. `borderline` is the third
admissible word and carries the extra sentence Step 5 requires.

> *"For M0208, the smallest K whose estimate reaches ≥ 0.90 of the true entry count — and the bars
> that K costs, checked against 473 − lookback."*

→ the results file names `K`, the ratio at `K`, `253 + 26K`, and asserts `253 + 26K ≤ 473`. The
probe prints this line itself.

> *"`git hash-object lab/lab.sqlite` identical before and after. Looks 4 → 4."*

→
```bash
cd /home/miftah/seer
test "$(git hash-object lab/lab.sqlite)" = "$(cat $S/db.before)" && echo "I5 ok"
test "$(sqlite3 "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" \
     "SELECT count(*) FROM trials WHERE window='test';")" = "4" && echo "I1 ok: looks 4 -> 4"
```
Both must print. The before-hash at `e3aeeff` is `607b78cf69c8e4e3a68a1e84c85eedfd1040c754`.

> *"STOP rule: if no affordable K reaches 0.90 on M0208, the phase records that and stops. A
> bounded replay is then not the remedy, and phases 2 and 3 do not run as designed."*

→ Step 6 above gives the exact contents the results file must carry in that case.

**Exit criteria (the observable statement that this phase is done):** `phase-1-results.md` exists on
`main`, carries nine verdicts with their ratios, carries M0208's K curve and its chosen K (or the
STOP sentence), carries the filled-in `## Contract for phase 2` YAML block, and
`git hash-object lab/lab.sqlite` plus the test-window look count are both unchanged from Step 1.

---

## Handoffs

Work this phase found or will find and deliberately leaves alone:

- **The membership convention is a second, independent defect, and it is not R1's.** Every method
  file reads *today's* member list at the earlier date; the validation run priced it at **0.034 on
  M0047 alone** (shipped 0.966 against an exactly-1.000 K=1), and the analysis notes M0201's own
  file measured it at 0.955 against 1.0045 with true historical sets. **No replay depth closes it.**
  It is not in this phase's `satisfies` list, it is not in phase 2's scope, and it must be carried
  to phase 6's leftovers as its own item with this phase's number attached — not folded into the
  shadow.
- **M0201's 2009-2015 era ratio.** The validation run read **0.827** for that era against 0.929 and
  1.034 for the other two, while the whole-window figure sits at 0.920 and inside the band. If the
  full run reproduces that, it is a finding worth a sentence — an estimator can be band-clean
  whole-window and badly off in the era the owner cares most about — but **drawing a new M0201 arm
  on it belongs to phase 5**, which already owns that method file conditionally.
- **The `trials.trades` = 624 coincidence on M0208.** If Step 4 shows the close-out's "624 real
  entries" was a trade count, correcting the published sentence is **phase 6's** (R3), not this
  phase's. Record the number here; do not `lab note` anything.
- **Widening `labkit.smoke_market` past 473 bars.** If M0208's K curve is still climbing at K=8,
  that is the constraint worth naming — but the cap is absolute for this set (I10) and a dedicated
  test module beats shrinking a frozen feature window. Leave it as a leftover for phase 6.
- **Everything about weights.** Phase 4 owns the weight-vector measurement and shares no file with
  this phase.

Nothing found in this phase serves a requirement other than R1. If the implementer finds something
that does, it goes here with the requirement id named, not into the steps.

---

## Rollback

Nothing to back out. The phase writes to the scratchpad and to
`.workflows/plan/control-draw-remedies/`, opens the lab database only through a read-only URI,
runs no `lab` command, and touches no file under `engine/`, `lab/`, `web/` or `db/`.

To undo it entirely:

```bash
cd /home/miftah/seer
git revert --no-edit <the phase-1 commit>     # or, before the commit:
rm -f .workflows/plan/control-draw-remedies/phase-1-results.md \
      .workflows/plan/control-draw-remedies/phase-1-probe.log
```

The scratchpad is session-scoped and needs no cleanup. `lab/lab.sqlite` is unmoved by construction
and Step 1's recorded hash is the proof.
