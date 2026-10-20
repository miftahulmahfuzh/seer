> Adopted from `docs/plans/CONTROL_DRAW_REMEDIES_PLAN.md` phase 3. Source: `.workflows/plan/control-draw-remedies/phase-3.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 3: M0208's honest control, re-drawn under the shadow

**Plan set:** `CONTROL_DRAW_REMEDIES_PLAN.md`
**Analysis:** `docs/analyzer/20261020-113306-C7K4_code_analyzer.md`
**Satisfies:** R1 (the held-set shadow, applied on the one chassis that needs it), R3 (state plainly
that this buys an honest control and no promotion), R4 (frozen records; a re-draw is a NEW arm
under an amendment; no test-window look)
**Depends on:** Phase 2 — `control_draw.py`'s v2 additions. Phase 1 hands over the replay depth `K`
and the list of chassis that need the shadow.
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab/methods` + `lab/lab.sqlite` + `web/data/lab.json`

---

## Goal

M0208's honest control is a `warn`: 455 trades against the book's 624 (0.729×) and 2.3130 turnover
against 3.0614 (0.756×), because the matched draw estimates the book's churn from a *fresh* top-20
instead of the drifted set the book actually holds. After this phase a second honest control exists
— a new allocator id, a new `Amendment`, a new trial — drawn against a **replayed shadow** of the
real held set, and the lab knows by measurement whether that control is band-clean. If it is, the
owner-facing sentence stops saying *"at least 4.3 points a year"* and names a number. If it is not,
the sentence stays a floor and this phase says so in plain words.

**What it does not do, and the phase must say so out loud (R3 / Decision D8).** `hardgate.check`
short-circuits at the first failing clause in this order — fold count → fold majority → the
promoted variant's own folds → survivorship drawdown → **D17** → **kin**. M0208 is the only one of
the nine whose operative clause is D17, and the clause immediately behind it is the kin rule, where
`failed_kin("M0208")` returns `('M0002',)` — a method that has already read **test-failed**. So a
band-clean arm here changes the **refusal message** and not the **answer**. **No sentence this
phase writes may imply a promotion.**

---

## Interface Contract

**Creates:**
- `m0208_capital_gains_overhang.A2_ADDED` (`m0208_…:~601`)
- `m0208_capital_gains_overhang.SHADOW_DEPTH` (`m0208_…:~603`) — **the set's one spelling for this
  constant**; an earlier draft of this phase called it `REPLAY_STEPS` and that name is withdrawn
- `m0208_capital_gains_overhang.ShadowDrawAllocator` + `SHADOW = ShadowDrawAllocator()`,
  allocator id **`M0208-A2`** (`m0208_…:~630`)
- `m0208_capital_gains_overhang._a2` (`m0208_…:~740`)
- `m0208_capital_gains_overhang.SHADOW_DRAW` — `Amendment`, appended to `METHOD.amendments`
  **after** `MATCHED_DRAW` (`m0208_…:~760`)
- candidate **`M0208-CGO-N20-PLC2`**, `supersedes=("M0208-CGO-N20-PLC", "M0208-HASH-N20")`
- lab rows: one `trials` row (dev), one `method_amendments` row (M0208 seq 2), one `trial_funding`
  row, `trial_moments`/`method_folds` as `lab run` writes them; `web/data/lab.json` regenerated

**Deletes:** nothing.
**Renames:** nothing.
**Signature changes:** none. `OverhangParams` gains **no field** — adding one moves all five
recorded M0208 digests (`seer-shared-params-cannot-gain-a-field`; `registry._canon` renders a
dataclass by `dataclasses.fields()`).

**Modifies (beyond pure append):**
- `m0208_capital_gains_overhang.py:81` — the `control_draw` import line grows two names. This is an
  import-block edit, not an edit to a recorded body; amendment 1 did the same.
- `m0208_capital_gains_overhang.py:660` — `amendments=(MATCHED_DRAW,)` becomes
  `amendments=(MATCHED_DRAW, SHADOW_DRAW)`. The recorded block stays first and byte-identical:
  `runner.pending_amendment` requires the record to be an exact **prefix** of the file.
- `m0208_capital_gains_overhang.py:52-62` — the module docstring gains an "Amendment 2" paragraph
  **after** the "Amendment 1" paragraph. Nothing above it is touched.
- **`engine/tests/test_lab_m0208_matched_draw.py`** — see *Files*. This is the one file outside the
  phase brief's literal ownership list that this phase must touch, and it is named here so the
  reconciler sees it. Measured at `e3aeeff`: `test_m0208_carries_exactly_one_amendment_of_one_arm`
  asserts `len(METHOD.amendments) == 1` and `len(all_candidates()) == 5` and goes **red** the
  moment the amendment is appended. No other phase owns this module (phase 2 owns
  `test_lab_control_draw.py` and the new `test_lab_control_draw_shadow.py`).

**Requires (from earlier phases):** `engine/src/seer_engine/lab/control_draw.py`, **after phase 2**,
exports these names beside the frozen v1 bodies. **This is phase 2's contract quoted verbatim and
this phase invents no sibling of its own** (reconciliation, 2026-10-20 — an earlier draft of this
phase assumed `shadow_held(*, dates, step, start)` and `lookback_for_replay(inner, steps)`; both
names are withdrawn):

```python
Replay = Callable[[date, AbstractSet[str]], tuple[Sequence[str], Sequence[str]]]
# replay(d, held) -> (the eligible pool on d, the controlled arm's book on d given `held`)


class ShadowReading(NamedTuple):
    pool: list[str]
    real_now: list[str]
    real_prev: list[str]


def max_shadow_depth(inner: int) -> int: ...
def shadow_lookback_for(inner: int, depth: int) -> int: ...          # inner + depth * 26, raises past 473
def shadow_decision_dates(data_date: date, depth: int, cadence: str = "monthly") -> list[date]: ...
def shadow_selection(replay: Replay, data_date: date, *, depth: int,
                     cadence: str = "monthly") -> ShadowReading: ...
def shadow_book(replay: Replay, data_date: date, held: AbstractSet[str], *, tag: str, seed: int,
                depth: int, cadence: str = "monthly") -> list[str]: ...

SHADOW_RULE_ID = "matched-draw-v2"
FIXTURE_BARS = 473
```

**Two things that follow from phase 2's shape and that this phase accepted rather than fought.**

1. **`shadow_selection` owns the calendar, and this phase does not supply one.** It derives
   `[d_depth … d_1, d_0]` by iterating `control_draw.previous_decision_date`. An earlier draft of
   this phase wanted to hand in its own list built from `m0208.previous_month_end(grid, d)`,
   because that reads the market symbol's own grid rather than the NYSE calendar.
   **Read against the code, the two agree inside the dev window**: `previous_decision_date` returns
   `dates.prev_session(first of data_date's month)` and `previous_month_end` returns the last
   column of SPY's own history strictly before the first of that month — the same session wherever
   SPY trades, which is every session from 1993 on. The one place they differ is before SPY's
   history opens, where `previous_month_end` returns `None` and truncates while `shadow_selection`
   simply reads an empty book and reseeds the shadow — the same effective answer. **Step 1's probe
   asserts the agreement over every decision of the dev window before anything is committed**, and
   stops the phase if it ever fails. `previous_month_end` therefore keeps its existing callers and
   is not deleted; this phase just does not call it for the replay calendar.
2. **`Replay` returns a pair, so the band closure also hands back the pool.** That is what lets the
   entry count and the draw be counted against the *same* pool; phase 2's own contract section
   gives the reason. This phase's closure returns `(tuple(sorted(scored_names)), banded_picks)` —
   **the pool in symbol order, never in score order**, so no part of the real ranking can reach the
   draw through a tie-break.

`shadow_lookback_for` is a **sibling** of `lookback_for`, not a widening of it: I3 freezes
`lookback_for`'s body, and phase 2 honours that.

**If phase 2 has not landed, this phase does not run.** There is no inline fallback: writing the
replay into the method file would be R1's "one shared rule" abandoned in the one phase that exists
to apply it. Stop and report to the coordinator instead.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/control_draw.py` — phase 2. **Quoted, never edited.**
- `MatchedDrawAllocator` (id `M0208-A1`), the `MATCHED_DRAW` `Amendment` block, `_a1`, `choose`,
  `_banded_picks`, `_book`, `previous_month_end`, `overhangs`, `draw`, `scored`,
  `build_week_grid`, `OverhangParams`, `OverhangAllocator`, `METHOD.candidates` — all frozen.
- `m0201_treasury_beta_size_weighted.py`, `m0221_cap_weighted_top_n.py`,
  `m0225_cap_weighted_top_n_repaired.py` — phases 4 and 5 (the weight axis).
- `m0047`, `m0202`, `m0215`, `m0227`, `m0243` — no re-draw here (see *The conditional second
  chassis*).
- `docs/plans/HANDOVER_20261020-control-draw-remedies.md`, `lab insight` — phase 6. **This phase
  journals no insight.**

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/methods/m0208_capital_gains_overhang.py` | modify (append + 3 pin-point edits) | `:81` import line; `:52-62` docstring gains an Amendment-2 paragraph after Amendment 1; new section appended after `MATCHED_DRAW` ends at `:599`; `:660` `amendments=` tuple grows |
| `engine/tests/test_lab_m0208_matched_draw.py` | modify | `test_m0208_carries_exactly_one_amendment_of_one_arm` (`:148-154`) inverted to the post-run truth; six new tests for the A2 arm; module docstring updated |
| `$SCRATCH/m0208_shadow_probe.py` | create | the free go/no-go probe (step 1). Scratchpad, never committed |
| `lab/lab.sqlite` | append (by `lab run`) | 1 trial, 1 amendment row, funding/moments/folds |
| `web/data/lab.json` | regenerate (by `lab stage`) | must agree with the database row for row |
| `.workflows/plan/control-draw-remedies/phase-3-results.md` | create | this phase's write-up |

---

## The conditional second chassis, decided before the phase runs

The brief says: *"PLUS: a new arm on any OTHER chassis that phase 1 named 'shadow needed'."* The
decision rule, so the phase does not grow scope at 3am:

**Re-draw a chassis only when all three hold.**

1. Phase 1 names it *shadow needed*; **and**
2. its current honest control is **not already `OK`** — a band-clean arm retires nothing further,
   and D4/D6 forbid spending compute on a measured no-op; **and**
3. no other phase of this set owns its method file.

Applied to the analysis's measured table (`20261020-113306-C7K4`, *How each chassis supplies
`real_prev` today`*), that resolves to **M0208 and nothing else**, and here is the whole working so
a phase session does not have to redo it:

| chassis | phase 1 is likely to say | current honest arm | rule |
|---|---|---|---|
| M0047, M0221, M0225, M0227, M0243 | *no-op by construction* — the real book never reads `held` | M0047/M0227/M0243 already `OK`; M0221/M0225 miss on **turnover** | fails (1), and M0221/M0225 fail (3) |
| M0202 | 0.955, probably a no-op | all three arms `OK` | fails (2) |
| M0215 | 0.996 / 0.969, probably a no-op | `M0215-CTRL-PLC` 0.99/0.98 `OK`, `M0215-CAP4-PLC` 0.97/0.96 `OK` | fails (2) even if phase 1 says *needed* |
| M0201 | 0.955, probably a no-op | `PLC1` misses on **turnover** by 0.0059 | fails (3) — **phase 5's file**, and a shadow is the wrong instrument for a turnover miss on a size-weighted chassis |
| **M0208** | **needed — 0.487×** | `M0208-CGO-N20-PLC` 0.73/0.76 `warn` | **passes all three** |

**If phase 1 names a chassis this table does not cover, or names M0201 explicitly:** do **not**
grow this phase. Record it in `phase-3-results.md` under *Handoffs*, name the owning phase, and
report it to the coordinator. A phase that quietly grows a second method file grows a second
amendment, a second pre-registration commit and a second set of frozen records, and this set is
being driven by hand, one phase at a time, on a laptop a parallel wave has already taken down
twice.

---

## The numbers this phase is measured against

Read read-only from `lab/lab.sqlite` on 2026-10-20 (`git hash-object lab/lab.sqlite` =
`607b78cf69c8e4e3a68a1e84c85eedfd1040c754`):

| arm | trial | trades | turnover | ratio vs the book |
|---|---|---|---|---|
| `M0208-CGO-N20` — **the book** | 677 | 624 | 3.06140631276508 | — |
| `M0208-HASH-N20` — the handicapped control | 680 | 2749 | 15.9095349281504 | 4.405 / 5.197 **refuse** |
| `M0208-CGO-N20-PLC` — amendment 1's honest control | 853 | 455 | 2.31301056528188 | **0.729 / 0.756 warn** |

**The band-clean window, derived, not guessed.** `control_shape.band_verdict` is **inclusive** at
the edges and `WARN_BAND = (0.80, 1.25)`. A superseding arm must be `OK` on **both** axes — a
`warn` arm retires nothing (`control_shape.superseding_arm`).

- trades: `0.80 × 624 = 499.2`, so **≥ 500** trades. *(The brief's "≥ 499" is the rounded figure;
  499/624 = 0.79968 reads `warn`. Use 500.)* High side `1.25 × 624 = 780`.
- turnover: `0.80 × 3.06140631 = 2.4492`; high side `1.25 × 3.06140631 = 3.8268`.
- **Which axis binds.** On this equal-slot chassis turnover follows trades arithmetically: the
  recorded pair gives turnover-per-trade `2.31301/455 = 0.0050835` against the book's
  `3.06141/624 = 0.0049061`, a factor of **1.0362**. So the **low** side is set by trades
  (≥ 500) and the **high** side by turnover (ratio ≤ 1.25 ⇒ trades ratio ≤ 1.2063 ⇒ **≤ 752**
  trades). **The band-clean trade window is 500 … 752.**

**The estimator's defect, and why the lift is not linear.** Over all 169 decision months with the
switch on and a scored pool, the real book made **624** entries — *624 as the honest-control
close-out recorded it, to be confirmed by phase 1's probe* — and amendment 1's one-unrolled-step
estimator read **304**, 0.487×, uniform across eras (0.444 / 0.509 / 0.500).

**Why that figure is flagged rather than quoted flat.** `M0208-CGO-N20`'s recorded `trials.trades`
is **also 624**, and an entry count and a trade count are not the same quantity: a book that takes
in `e` names and lets `e` go makes about `2e` basket changes before fills and resizes. If phase 1's
forward replay reads near **1248** while the ratio still lands at ~0.487, the close-out conflated
the two. **The ratio is the finding; the absolute is a cross-check.** This phase's Step 1 anchor
therefore tests against **phase 1's measured `m0208_true_entries`**, not against the literal 624,
and **phase 6 owns the correction of any published sentence that quotes the figure** — this phase
corrects nothing the owner reads about it.

**None of this touches the band arithmetic below.** The 500 … 752 window is derived from
`trials.trades = 624`, which *is* a trade count and is the right quantity for a shape comparison. The *realised* figure
is not the estimate: `matched_names` keeps at most `len(real_now) − e` of its own held names **that
are still in the pool**, so a control name that leaves the index is forced out whatever `e` says,
and the book tops back up. Realised entries are therefore `Σ max(e_t, a_t)` over decisions, which
lifted 304 → 455. As `e` rises, `max(e, a)` rises **less than `e` does**, because `a` stops being
the binding term. **A shadow that recovers 0.90 of the true entry count does not deliver 0.90 × 624
realised trades.** The hypothesis below must say that and must not predict 1.00.

---

## The replay depth `K`, and the hard cap

`ShadowDrawAllocator.lookback(p) = shadow_lookback_for(factor_lookback(p.inner), SHADOW_DEPTH)`
`= 253 + 26 × K`. Measured on this tree:

| K | lookback | fits the 473-bar smoke fixture? |
|---|---|---|
| 1 | 279 (= `M0208-A1` today) | yes |
| 7 | 435 | yes |
| **8** | **461** | **yes — and this is the cap** |
| 9 | 487 | **no** |

`K = 8` is the maximum. Verified on the smoke fixture at every rung: at 461 bars
`test_candidate_runs_a_smoke_window` still produces **13 snapshots** and `row.end == DEV_END`; at
473 it raises `DevWindowError`. On the real dev run the window does **not** move: the candidate
declares only SPY, whose store history opens in 1993, and `backtest.dev.candidate_window` floors a
member-reading candidate at `MEMBERSHIP_START` (1996-01-02) — ~735 SPY sessions of slack against a
461-bar need. So trial `M0208-CGO-N20-PLC2` runs the **same window** as trials 677 and 853 and is
comparable to both.

**Where K comes from — the chain, in three links, agreed with phases 1 and 2.**

1. **Phase 1 proposes.** Its contract block hands over `k_proposed["M0208"]`: the smallest depth
   whose replayed entry count reached ≥ 0.90 of its own measured true count.
2. **This phase verifies on its own probe (Step 1) and ships its own number.** `SHADOW_DEPTH` is
   set to the smallest `K ≤ 8` whose ratio reaches ≥ 0.90 **on this phase's ladder**. The code
   below is written with `SHADOW_DEPTH = 8`; **substitute the verified number before committing.**
3. **Phase 2 never sees a K.** `shadow_selection` and `shadow_book` take `depth` as a required
   keyword-only argument with no default, so `control_draw` hardcodes nothing and `SHADOW_DEPTH`
   lives in this file only. It must **not** become a field on `OverhangParams`.

If this phase's smallest qualifying `K` is greater than 8, or phase 1 handed over `stop: true`,
**this phase does not run** — see *The no-op branch* below.

**One honest discrepancy to expect, and it is why link 2 exists.** This phase's `Replay` closes the
switch: on a decision where `trend_on` is false the real book held nothing of the pool, so the
replay returns an empty book and `shadow_selection` reseeds the shadow to empty. Amendment 1's
estimator has no such guard — it takes a fresh top-20 at the previous month-end whether or not the
switch was on, so every switch-off→on re-entry month (the book re-enters all twenty names) is read
as two or three entries instead of twenty. **Part of the gap between the true count and the 304 is
that guard and not the drift.** Phase 1's probe resets its chains on a gate-off month but its
`(b) SHIPPED` column deliberately reproduces the unguarded reading, so **phase 1's K and this
phase's K may legitimately differ.** Where they do, **this phase uses its own** and the results
file reports both side by side with one sentence saying why.

### The no-op branch, stated before the phase starts

**This phase is conditional on phase 1 not stopping.** If `phase-1-results.md` carries
`stop: true` — no affordable K reached 0.90 on M0208 — or if this phase's own Step 1 probe returns
its NO-GO exit code, then:

- **no file is edited, no amendment is written, no `lab` command is run, nothing is committed to
  `engine/`**;
- `.workflows/plan/control-draw-remedies/phase-3-results.md` is written anyway, with the verdict
  word **STOP** on its first line, the whole K ladder, both anchors, and the sentence **"M0208's
  published lead stays a floor"**;
- the results file states that `methods.verdict` for M0208 is **unchanged** and hands phase 6 that
  fact in the `published_sentence_moved: false` slot;
- the results file is committed to `.workflows/plan/` by pathspec and the coordinator is told to
  run phase 4 next.

A STOP here costs no method id, no trial, no N and no test-window look, and it closes most of
leftover 3 with a measurement. It is a legitimate outcome and the phase must not deepen K past 8
to avoid it — 8 is set by the 473-bar cap, not by preference.

---

## Implementation Steps

> Environment for every command below. Each `Bash` call is a fresh shell, so export these every
> time or inline them:
>
> ```bash
> PY=/home/miftah/seer/engine/.venv/bin/python
> export PYTHONPATH=/home/miftah/seer/engine/src
> export SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research   # NEVER rebuild a store
> SCRATCH=/tmp/claude-1000/-home-miftah-seer/<session-id>/scratchpad
> ```
>
> `SEER_RESEARCH_TEST_STORE` is never set and `lab test` is never invoked (I1). **Never pipe a
> `lab` command** — `grep -v` owns the exit status (I4). Redirect to a file and `cat` it.

### Step 0: Record the starting state

**File:** none.
**Change:** the two numbers every later claim is checked against (I5, I1).
**Code:**
```bash
cd /home/miftah/seer
git rev-parse --short HEAD
git status --porcelain
git hash-object lab/lab.sqlite
sqlite3 "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" \
  "select count(*) from trials where window='test';
   select count(*) from trials;
   select seq, added from method_amendments where method_id='M0208';"
```
**Expected:** test-window looks **4**. `method_amendments` holds M0208 **seq 1 only**. A
`sqlite3 … mode=ro` query never migrates the file, so the hash is unmoved after it.
**Impact:** none. Read-only.

---

### Step 1: The free pre-run probe — go/no-go before anything is committed

**File:** `$SCRATCH/m0208_shadow_probe.py` (new, scratchpad only — never committed)
**Change:** replay M0208's real band forward over the whole dev window to get the **true** entry
count, then replay the `K`-step shadow at every decision and count what it estimates. No trial, no
lab database, no write, no fee model. It imports only names the method file **already** has, so it
runs **before** the allocator is written.

**Code:**
```python
"""M0208's held-set shadow: how close does a K-step replay get to the book's real churn?

Free and read-only. The lab database is never opened, no trial is recorded, no return or fee is
modelled. It walks every monthly decision of the dev window, replays M0208's own band forward to
get the TRUE entry count, then -- at each decision -- replays the band backward K steps from an
empty book to get the SHADOW's estimate of the held set the book is coming into that decision
with, and counts the entries that estimate implies.

Two anchors make the measurement checkable rather than merely plausible:

  * the forward replay must read 624 entries, which is the trade count trial 677 recorded;
  * the K=1 ladder WITHOUT the switch guard must read 304, which is what amendment 1's estimator
    was measured at on 2026-10-20.

If either anchor misses, the probe is not measuring what it claims and the phase stops.
"""

from __future__ import annotations

import os
import time
from datetime import date
from pathlib import Path

from seer_engine import dates, research
from seer_engine.backtest.dev import DEV_END, MEMBERSHIP_START
from seer_engine.lab.methods import m0208_capital_gains_overhang as m0208
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, is_rank_session
from seer_engine.strategies.f_factor import trend_on

STORE = Path(os.environ["SEER_RESEARCH_STORE"])
MAX_K = 8  # 253 + 26*8 = 461 <= 473, the smoke fixture's size and the absolute lookback cap
ERAS = ((1996, 2002), (2003, 2008), (2009, 2015))


def decision_dates() -> list[date]:
    """The data dates book_runner hands the allocator: prev_session of every monthly rank session."""
    return [
        dates.prev_session(s)
        for s in dates.sessions(MEMBERSHIP_START, DEV_END)
        if is_rank_session(MONTHLY_HOLD_FRAC_GOTRADE, s)
    ]


def era_of(d: date) -> tuple[int, int]:
    for lo, hi in ERAS:
        if lo <= d.year <= hi:
            return (lo, hi)
    return (0, 0)


def replay_dates(grid, data_date: date, steps: int) -> list[date]:
    """The ``steps`` decision dates before ``data_date``, oldest first, truncated at the calendar.

    THE PROBE'S OWN helper, on the chassis's own grid -- not a module name, and not what the
    shipped arm uses. The shipped arm calls ``control_draw.shadow_selection``, which derives the
    same calendar off ``previous_decision_date``; anchor 0 above is what proves the two agree on
    every decision of the dev window, which is why the probe's ladder and the arm's replay measure
    the same thing.
    """
    out: list[date] = []
    cur = data_date
    for _ in range(steps):
        prev = m0208.previous_month_end(grid, cur)
        if prev is None:
            break
        out.append(prev)
        cur = prev
    out.reverse()
    return out


def main() -> int:
    p = m0208.OverhangParams(m0208.N20, keep=40)
    data = research.load_store(STORE)
    market = data.market
    prepared = m0208.OVERHANG.prepare(market.history)
    grid = prepared.grid(p.market)
    if grid is None:
        print("no week grid: the store has no market symbol history")
        return 1

    # --- anchor 0: phase 2's calendar IS this chassis's calendar. ------------------------------
    # `shadow_selection` derives its replay dates with `control_draw.previous_decision_date`,
    # while this file's own `previous_month_end` reads the market symbol's grid. They must be the
    # same session on every decision of the dev window, or the shadow would be replaying a
    # calendar the book never used. Checked here, for free, BEFORE anything is committed.
    from seer_engine.lab.control_draw import previous_decision_date
    mismatches = []
    for d in decision_dates():
        a = previous_decision_date(d)
        b = m0208.previous_month_end(grid, d)
        if b is not None and a != b:
            mismatches.append((d, a, b))
    print(f"ANCHOR 0  calendar agreement over {len(decision_dates())} decisions: "
          f"{len(mismatches)} mismatches   [must be 0]")
    if mismatches:
        for row in mismatches[:10]:
            print("   mismatch:", row)
        print("NO-GO: control_draw.previous_decision_date and m0208.previous_month_end disagree; "
              "shadow_selection would replay a calendar the book never used.")
        return 2

    # One pass over the window, caching each decision's own pool and order, so the ladder costs
    # one `scored` call per (decision, replay date) and not one per (decision, K, replay date).
    live: list[tuple[date, list[str]]] = []
    order_at: dict[date, list[str]] = {}
    on_at: dict[date, bool] = {}
    for d in decision_dates():
        members = market.membership.members_on(d)
        switch = bool(trend_on(prepared.history, d, p.inner))
        on_at[d] = switch
        if not switch:
            continue
        rows = prepared.factor.rows_on(members, d, p.inner)
        sc = m0208.scored(grid, rows, d, p)
        if not sc:
            continue
        order = sorted(sc, key=lambda s: (-sc[s], s))
        order_at[d] = order
        live.append((d, order))

    # --- anchor 1: the forward replay of the real band. Must read 624. -------------------------
    held: frozenset[str] = frozenset()
    real_total = 0
    real_era: dict[tuple[int, int], int] = {e: 0 for e in ERAS}
    months_era: dict[tuple[int, int], int] = {e: 0 for e in ERAS}
    for d in decision_dates():
        if not on_at.get(d) or d not in order_at:
            held = frozenset()
            continue
        picks = m0208._banded_picks(order_at[d], held, p.inner.top, p.keep)
        entered = len(set(picks) - held)
        real_total += entered
        real_era[era_of(d)] += entered
        months_era[era_of(d)] += 1
        held = frozenset(picks)
    print(f"decisions with the switch on and a scored pool: {len(live)}")
    print(f"ANCHOR 1  real book entries (forward replay): {real_total}   "
          f"[must equal phase 1's m0208_true_entries; the close-out recorded 624]")

    # --- the backward-replay ladder -------------------------------------------------------------
    def order_on(d: date, rows_today) -> list[str] | None:
        """The real signal's order at an EARLIER date, read with TODAY's membership and rows.

        Deliberate and identical to amendment 1: today's member list is known today, and the
        earlier reading uses only prices dated on or before the earlier date.
        """
        sc = m0208.scored(grid, rows_today, d, p)
        if not sc:
            return None
        return sorted(sc, key=lambda s: (-sc[s], s))

    def ladder(steps: int, guard: bool) -> tuple[int, dict[tuple[int, int], int]]:
        total = 0
        per_era = {e: 0 for e in ERAS}
        for d, order in live:
            members = market.membership.members_on(d)
            rows_today = prepared.factor.rows_on(members, d, p.inner)
            shadow: frozenset[str] = frozenset()
            for e in replay_dates(grid, d, steps):
                if guard and not trend_on(prepared.history, e, p.inner):
                    shadow = frozenset()
                    continue
                back = order_on(e, rows_today)
                if back is None:
                    shadow = frozenset()
                    continue
                shadow = frozenset(m0208._banded_picks(back, shadow, p.inner.top, p.keep))
            picks_real = m0208._banded_picks(order, shadow, p.inner.top, p.keep)
            entered = len(set(picks_real) - shadow)
            total += entered
            per_era[era_of(d)] += entered
        return total, per_era

    t0 = time.monotonic()
    bare, _ = ladder(1, guard=False)
    print(f"ANCHOR 2  K=1 without the switch guard: {bare}   [must be 304]")
    print(f"          one ladder pass took {time.monotonic() - t0:.1f}s")

    print()
    print(f"{'K':>2}  {'entries':>8}  {'ratio':>6}   " + "  ".join(f"{lo}-{hi}" for lo, hi in ERAS))
    best = None
    for k in range(1, MAX_K + 1):
        total, per_era = ladder(k, guard=True)
        ratio = total / real_total if real_total else float("nan")
        eras = "  ".join(
            f"{per_era[e] / real_era[e]:.3f}" if real_era[e] else "  -  " for e in ERAS
        )
        print(f"{k:>2}  {total:>8}  {ratio:>6.3f}   {eras}      lookback {253 + 26 * k}")
        if best is None and ratio >= 0.90:
            best = (k, total, ratio)

    print()
    print("era months:", {f"{lo}-{hi}": months_era[(lo, hi)] for lo, hi in ERAS})
    print("real entries by era:", {f"{lo}-{hi}": real_era[(lo, hi)] for lo, hi in ERAS})
    if best is None:
        print("NO-GO: no K <= 8 reaches 0.90 of the real entry count. Phase 1's STOP rule fires.")
        return 2
    k, total, ratio = best
    print(f"smallest K reaching 0.90: K={k}, {total} entries, {ratio:.3f}")
    if ratio > 1.05:
        print("NO-GO: the replay OVER-counts the real churn, which it cannot do. Find the bug.")
        return 2
    print(f"GO: set SHADOW_DEPTH = {k} (lookback {253 + 26 * k} <= 473)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**Run it — redirection, never a pipe:**
```bash
cd /home/miftah/seer
SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
PYTHONPATH=/home/miftah/seer/engine/src \
/home/miftah/seer/engine/.venv/bin/python "$SCRATCH/m0208_shadow_probe.py" \
    > "$SCRATCH/m0208_shadow_probe.log" 2>&1
echo "exit=$?"
cat "$SCRATCH/m0208_shadow_probe.log"
```
**Expected exit code:** **0** (GO). `2` is the probe's own NO-GO; `1` is an error.
**Expected cost:** loading the dev store is one to two minutes. One ladder pass is ~169 decisions ×
K `scored` calls; the whole ladder (K = 1…8) is about 36 passes' worth of work. Budget 15–40
minutes and run it once.

**The go/no-go band, stated before the number exists:**

| reading | verdict |
|---|---|
| anchor 0 reports any calendar mismatch | **STOP.** `shadow_selection`'s calendar is not this chassis's. Report to the coordinator; it is a phase 2 contract question, not a thing to work around here. |
| anchor 1 ≠ phase 1's `m0208_true_entries` (± 2 %) | **STOP.** The two probes disagree about the real book. Nothing is committed. *(Anchor 1 is **not** tested against the literal 624 — see C6 above: 624 is the close-out's figure and the recorded `trials.trades` is also 624. If phase 1 measured ~1248, anchor 1 must read ~1248 too.)* |
| anchor 2 ≠ 304 (± 2 %) | **STOP.** The unguarded `K = 1` ladder is supposed to reproduce amendment 1's shipped estimator exactly. If it does not, the probe is measuring something else. |
| no `K ≤ 8` reaches **0.90** of anchor 1 | **STOP.** A bounded replay is not the remedy. Write `phase-3-results.md` with the ladder, and the sentence stays a floor. |
| the smallest qualifying `K` reads ratio **> 1.05** | **STOP.** The replay cannot exceed the real churn; this is a bug, not a finding. |
| smallest qualifying `K ≤ 8` with ratio in **[0.90, 1.05]** | **GO.** Set `SHADOW_DEPTH = K` and continue to step 2. |

**Impact:** none on the tree, none on the database. Record the whole ladder in the results file
whatever the verdict — the ladder is itself a measurement R1 wanted.

---

### Step 2a: The import line

**File:** `engine/src/seer_engine/lab/methods/m0208_capital_gains_overhang.py:81`
**Change:** add the two v2 names phase 2 ships — **phase 2's spellings, verbatim.**
**Code:**
```python
from seer_engine.lab.control_draw import (
    lookback_for,
    matched_names,
    shadow_lookback_for,
    shadow_selection,
)
```
**Impact:** none on any recorded digest — `config_text` is rules, allocator id and params, and an
import is in none of them. `test_method_source_is_pure` checks the import roots and
`seer_engine.lab.control_draw` is already there.

---

### Step 2b: The module docstring gains an Amendment-2 paragraph

**File:** `engine/src/seer_engine/lab/methods/m0208_capital_gains_overhang.py` — inserted between
line 62 (the end of the Amendment-1 paragraph) and line 64 (`Rules are …`).
**Change:** the file's prose record of what the second amendment asks. Nothing above it moves.
**Code:**
```
Amendment 2 (2026-10-20). ``CGO-N20-PLC`` above is an honest draw and it is still not a match: it
trades 455 times against ``CGO-N20``'s 624 and turns over 2.313 against 3.061, 0.73x and 0.76x,
inside D17's refuse band and outside its match band. The cause is in the stand-in, not in the
draw. ``MatchedDrawAllocator`` has no record of what ``CGO-N20`` actually held -- no allocator
does -- so it reconstructs the previous held set from the plain top twenty at the previous month
end. A freshly taken top twenty is ranked 1-20 and the band drops a name only past rank 40, so
almost nothing falls out of it; the real held set has accumulated names that entered near the top
and have since drifted toward the edge, and those fall out far faster. Measured over all 169
decisions with the switch on and a scored pool: 304 estimated entries against 624 real, 0.487x,
uniform across 1996-2002, 2003-2008 and 2009-2015 (0.444 / 0.509 / 0.500). ``CGO-N20-PLC2``
replaces the stand-in with a bounded replay: start from an empty book a fixed number of decisions
back and apply ``CGO-N20``'s own band, its own switch and its own ranking forward, one decision at
a time, to reconstruct the drifted set the book is actually coming into this decision with. The
draw itself, the pool, the twenty 1/20 slots, the band, the switch and the SPY fill are all
unchanged. Nothing above this paragraph changes: ``HASH-N20``'s and ``CGO-N20-PLC``'s trials are
recorded and stay exactly as they were measured.
```
**Impact:** prose only. The file's sha moves, which is the point — the commit is the
pre-registration and the new sha is appended to `method_amendments`, never to `methods.source_sha`.

---

### Step 2c: The shadow allocator

**File:** `engine/src/seer_engine/lab/methods/m0208_capital_gains_overhang.py` — appended **after**
the `MATCHED_DRAW` block ends (line 599) and **before** `METHOD = Method(` (line 602).
**Change:** a new allocator id, its replay, its candidate factory and the new `Amendment`.
**Code (complete — paste as one block):**

```python
# --------------------------------------------- amendment 2: the matched draw, under the shadow
#
# Why a second allocator id and not a widened A1. ``MatchedDrawAllocator`` drew trial 853 and is
# part of the record. Its body is outside ``config_digest`` -- a digest is rules, allocator id and
# params -- so Python would let it be widened and nothing would complain, and the recorded arm's
# behaviour would have moved because a later amendment wanted its lines. So the shadow gets its
# own id, exactly as the matched draw copied ``choose``'s band rather than refactoring it, and A1
# is left byte-identical.
#
# ``_banded_picks``, ``_book`` and ``previous_month_end`` are now read by TWO recorded allocators
# instead of one. They were already frozen; this makes them doubly so.

A2_ADDED = date(2026, 10, 20)

SHADOW_DEPTH = 8
"""How many decisions back the shadow starts from an empty book before replaying forward.

The number is a measurement, not a taste: it is the smallest depth whose replayed entry count
reaches 0.90 of ``CGO-N20``'s real entry count, read off the dev store before this amendment was
committed. It is also capped from above and the cap is absolute. ``lookback`` below is
``control_draw.shadow_lookback_for(factor_lookback(inner), SHADOW_DEPTH)`` = 253 + 26K, and
``labkit.smoke_market``'s fixture is 473 sessions, so K = 8 (461) fits and K = 9 (487) cannot run
at all -- ``shadow_lookback_for`` raises rather than returning a number no test can drive. It
costs this arm no window: it declares only SPY, whose store history opens in 1993, and
``backtest.dev.candidate_window`` floors a member-reading candidate at ``MEMBERSHIP_START``, so
the trial's window is ``CGO-N20``'s own and the number is comparable to trials 677 and 853.

It lives HERE and not in ``control_draw`` on purpose. ``shadow_selection`` takes ``depth`` as a
required keyword-only argument with no default, because how far back a chassis's band has to be
rolled before its shadow stops moving is a property of that band and that ranking. The shared
module owns the mechanism; the method file owns the number.

It is deliberately a module constant and NOT a params field. ``OverhangParams`` is the dataclass
all five recorded M0208 arms are digested through, and ``registry._canon`` renders a dataclass by
``dataclasses.fields()``: one more field would move every one of those five recorded digests. The
record of this number is therefore the pre-registering commit's source sha, which
``method_amendments`` holds, plus this docstring -- which is the same record ``RATE`` and
``TAU_MAX`` have had since the method's first run.
"""


class ShadowDrawAllocator(OverhangAllocator):
    """``CGO-N20``'s shape with none of its identity, drawn against a REPLAYED held set.

    Everything but the stand-in is ``MatchedDrawAllocator``'s rule and most of it is literally
    ``OverhangAllocator``'s: this class inherits ``symbols``, ``holds``, ``uses_members``,
    ``prepare`` and both target entry points, so the screen, the SPY 200-day switch, the weekly
    grid and the SPY-remainder fill are the same code and not a re-implementation of it. Only
    ``_targets``, ``lookback`` and ``id`` differ, and ``_targets`` differs from A1's in exactly
    one place: where A1 reads a fresh top twenty at the previous month end, this reads a replay.

    **The replay, and why it is a fold and not carried state.** At each decision
    ``control_draw.shadow_selection`` walks ``SHADOW_DEPTH`` decisions back, starts from an empty
    book there, and applies ``CGO-N20``'s own band forward one decision at a time. The result is
    what the real book would hold coming into the previous decision, given that it had been
    running for ``SHADOW_DEPTH`` months. It is a PURE FUNCTION of the dates it is handed:
    ``backtest.dev.run_registry`` reuses one allocator object per id across candidates and across
    walk-forward folds, so any per-instance memory of a previous decision would leak between them
    and the arm would not be reproducible. Nothing is stored on ``self``.

    **The switch is part of the band, and that is the half A1 was missing.** On a decision where
    ``trend_on`` is false the real book holds nothing of the pool -- ``targets_prepared`` returns
    no targets and the book sells out -- so the replay resets the shadow to the empty set there,
    and the month the switch comes back on the real book re-enters its whole twenty. A1's fresh
    top twenty cannot see that: it hands the draw a full book at a date the real book was in cash,
    and reads two or three entries where the truth is twenty.

    **The ``Replay`` seam.** ``shadow_selection`` wants a ``(date, held) -> (pool, book)``
    callable and derives its own calendar from ``control_draw.previous_decision_date``, which on
    this chassis is the same session ``previous_month_end`` returns -- the last session before the
    first of the month, read off the NYSE calendar instead of off SPY's own grid. The phase's
    pre-registration probe asserted that agreement over every decision of the dev window before
    this file was committed.

    **The pool goes back through ``Replay`` in symbol order, never in score order**, so no part of
    the real ranking can reach the draw through a tie-break, and the entry count and the draw are
    counted against the SAME pool because one callable hands back both. ``rows`` is read once, at ``data_date``, and
    used for every replayed date too -- deliberate, and it looks ahead at nothing, because today's
    member list is known today and every earlier reading uses only prices dated at or before that
    earlier date. It means the entry count measures the SIGNAL's churn and not the index's, which
    is right: the control draws from today's pool either way.

    **No memo.** Consecutive decisions replay overlapping dates and a cache would pay for itself
    several times over. It is not written, because the only places to hang one are the allocator
    (forbidden -- see above) or ``OverhangPrepared`` (which ``targets`` does not have), and a draw
    that is cheap and reproducible beats a draw that is cheaper and conditionally reproducible.
    The cost is about ``SHADOW_DEPTH / 2`` times A1's, paid once.

    ``signal`` must be ``"high"``: this arm shadows the paper's long side, and the params say
    which arm it shadows. A ``"hash"`` or ``"low"`` value would be a placebo of a placebo or of
    the contrast, which is not what was pre-registered.
    """

    id = "M0208-A2"

    def lookback(self, params: Any) -> int:
        return shadow_lookback_for(factor_lookback(_check(params).inner), SHADOW_DEPTH)

    def _targets(self, history: Mapping[str, History], rows: list[FactorRow],
                 grid: WeekGrid | None, data_date: date, held: frozenset[str],
                 p: OverhangParams) -> tuple[Target, ...]:
        if not rows or grid is None:
            return ()
        if p.signal != "high":
            raise ValueError(
                f"the matched draw shadows the high-overhang book, so signal must be 'high', "
                f"got {p.signal!r}"
            )

        def replay(d: date, carried: AbstractSet[str]) -> tuple[Sequence[str], Sequence[str]]:
            """``CGO-N20``'s own decision at ``d``, given what the replay says it held before it.

            ``control_draw.Replay``: it hands back the pool it actually ranked AND the book it
            ranked out of it, so the entry count and the draw can never be counted against two
            different pools. The pool goes back in SYMBOL order so no part of the real ranking can
            reach the draw through a tie-break.

            The SPY 200-day switch is part of the band here and that is the half amendment 1 was
            missing: on a month where ``trend_on`` is false the real book held nothing of the pool,
            so this returns an empty book and ``shadow_selection`` reseeds the shadow to empty. A1's
            fresh top twenty cannot see that -- it hands the draw a full book at a date the real
            book was in cash, and reads two or three entries where the truth is twenty.
            """
            if not trend_on(history, d, p.inner):
                return (), ()
            at_d = scored(grid, rows, d, p)
            if not at_d:
                return (), ()
            back = sorted(at_d, key=lambda s: (-at_d[s], s))
            return tuple(sorted(at_d)), _banded_picks(back, carried, p.inner.top, p.keep)

        reading = shadow_selection(replay, data_date, depth=SHADOW_DEPTH)
        if not reading.real_now:
            return _book(history, rows, (), data_date, p)
        drawn = matched_names(
            pool=reading.pool,
            held=held,
            real_now=reading.real_now,
            real_prev=reading.real_prev,
            tag="M0208",
            seed=p.seed,
            data_date=data_date,
        )
        return _book(history, rows, drawn, data_date, p)


SHADOW = ShadowDrawAllocator()


def _a2(suffix: str, params: OverhangParams, rationale: str,
        supersedes: tuple[str, ...]) -> Candidate:
    """An amendment-2 candidate, with the declaration of which recorded arms it replaces.

    **This arm does NOT declare ``controls=`` (Decision D9), and the reason is measured.**
    ``control_shape.DECLARATION_ATTR = "controls"`` exists but no method file in the lab sets it,
    so the ``declared`` resolver rung never fires today. On M0208 it does not need to: a third
    placebo cannot become anybody's target, because ``_eligible_targets`` excludes placebo arms,
    and the step 2e test asserts the arm still resolves to ``M0208-CGO-N20`` on the ``stem`` rung
    while neither earlier control's resolution moves. A ``controls=`` declaration here would be a
    new ``Candidate`` field exercised for the first time inside a recorded trial, which is a
    strictly worse place to find out it is wrong. *(It would be SAFE to add -- ``Candidate``
    already carries ``supersedes``, added the same way, and ``lab.method.config_text`` renders only
    rules + allocator id + params, so a new ``Candidate`` field is outside ``config_digest`` by
    construction. It is simply not needed here.)*

    ``supersedes`` is what D17 reads (``control_shape.SUPERSEDES_ATTR``): declared, never inferred
    from the target, and outside ``config_digest`` because ``config_text`` names its three
    attributes by hand. It names BOTH earlier controls, because D17 supersedes a ``warn`` finding
    as well as a ``refuse`` one -- every margin written against either was quoted against an
    opponent of the wrong shape, and leaving one of a re-drawn pair unmarked would say the
    opposite. It retires neither unless this arm reads ``OK`` on both axes."""
    return Candidate(id=f"M0208-{suffix}", family="M0208", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=SHADOW, params=params, rationale=rationale, added=A2_ADDED,
                     owner_inputs=(), supersedes=supersedes)


SHADOW_DRAW = Amendment(
    added=A2_ADDED,
    why=(
        "CGO-N20-PLC is an honest draw that is still not a match -- 455 trades against 624 and "
        "2.313 turnover against 3.061, 0.73x and 0.76x -- because it reconstructs the book's "
        "previous holdings from a fresh top twenty instead of the drifted set the book actually "
        "holds; replay the band forward from an empty book instead and draw against that"
    ),
    hypothesis=(
        "Written before the run, and before any result for this arm was seen. The standing "
        "sentence about this method is that CGO-N20 beat a meaningless book by AT LEAST 4.3 "
        "points a year - 13.879% against CGO-N20-PLC's 9.532% on the owner's deposits, where SPY "
        "TR on the same deposits earned 7.188% - published as a floor rather than a measurement, "
        "because even the fairest control the lab could draw still traded a quarter less than the "
        "book. This arm exists to turn that floor into a number, and the bar it has to clear is "
        "arithmetic and is written here before it runs: D17's match band is 0.80-1.25 inclusive "
        "on BOTH axes, so against 624 trades and 3.0614 turnover the arm must record AT LEAST "
        "500 trades and 2.4492 turnover, and at most 780 trades and 3.8268 turnover. On an "
        "equal-slot chassis turnover follows trades arithmetically - the recorded pair gives "
        "1.0362 turnover per trade against the book's - so the low side is set by the trade count "
        "and the high side by turnover, and the clean window is 500 to 752 trades. A warn arm "
        "retires nothing, so anything outside that window leaves the published sentence a floor. "
        "Predicted direction. The estimator was measured at 304 entries against the real book's "
        "624 - 0.487x, uniform across 1996-2002, 2003-2008 and 2009-2015 - and the replay "
        "recovers at least 0.90 of the real count on the dev store before this block was "
        "committed. The realised trade count will NOT rise in proportion, and that is the "
        "prediction's most falsifiable part: the draw keeps at most as many of its own names as "
        "are still in the pool, so a control name that leaves the index is forced out whatever "
        "the entry count says, and the realised figure is the sum over decisions of the larger of "
        "the two. That attrition already did half the work at 304 entries, lifting the recorded "
        "arm from 0.49 to 0.73, and it stops binding as the entry count rises. So the predicted "
        "landing is a RANGE and not a point: 560 to 700 trades, 0.90x to 1.12x, and 2.85 to 3.55 "
        "turnover, 0.93x to 1.16x - band-clean on both axes, with the high side the live risk and "
        "not the low one. Money: the arm trades more than CGO-N20-PLC did, pays more of Gotrade's "
        "fees for it, and therefore EARNS LESS than its 9.532%, somewhere in 8.5% to 9.5%, so the "
        "margin WIDENS from +4.346 to between 4.4 and 5.4 points and the word 'at least' comes "
        "out of the published sentence. A reversal - the control earning MORE than 9.532% - is an "
        "admissible outcome of this prediction and would say that the extra churn bought more of "
        "the dev store's survivorship lottery than it paid in fees, which is a mechanism this lab "
        "has already measured and declined to assign a sign to. Whatever the number is, it is "
        "reported and the arm is not drawn again: this is one re-draw of one book at one replay "
        "depth, and a second one would only ever be justified by the shape missing its band, "
        "never by the margin coming out wrong. And none of it promotes anything: hardgate.check "
        "tests the walk-forward folds, the promoted variant's own folds and the survivorship "
        "drawdown before D17, and immediately behind D17 stands the kin rule, where M0208's kin "
        "is M0002, which has already spent and failed its test-window look. A clean arm here "
        "changes the refusal message and not the answer."
    ),
    expected_failure=(
        "The ways this is wrong, stated so each can be recognised. First, on shape and high: the "
        "replay recovers the drift AND pool attrition stacks on top of it, so the arm lands above "
        "752 trades or above 3.8268 turnover and misses the band from the other side - the "
        "mirror of amendment 1's miss, and it would say the two effects are additive where this "
        "hypothesis says the larger of the two binds. Second, on shape and low: the replay depth "
        "is too shallow for a book whose names drift toward the band's edge over more months than "
        "the lookback can pay for, the arm lands under 500 trades again, and the honest reading "
        "is that a bounded replay is not the remedy on this chassis at all - at which point the "
        "published sentence stays a floor and the right next move is a different mechanism, not a "
        "deeper replay, because 8 steps is already the absolute lookback cap. Third, on money: "
        "the margin barely moves, which would say the fee bill between 455 and 620 trades is "
        "worth well under a point a year and the whole 'floor' caveat was about a quantity too "
        "small to matter - a useful and slightly embarrassing result that should be written down "
        "as such. Fourth, the direction reverses and the honest control earns more rather than "
        "less; the lab has measured that an honest control's effect on a margin is not a bias of "
        "known sign but an arbitrary one, so this is the outcome the prediction is least "
        "entitled to be surprised by. A shape miss is reported as a shape miss and the quoted "
        "margin stays provisional; it is not a reason to try another seed, another depth, or "
        "another draw."
    ),
    candidates=(
        _a2("CGO-N20-PLC2", OverhangParams(N20, keep=40),
            "Placebo for CGO-N20, re-drawn: the same pool, slots, band and switch, filled in a "
            "hash order at the entry count of a replayed shadow of the real book's own holdings",
            supersedes=("M0208-CGO-N20-PLC", "M0208-HASH-N20")),
    ),
)
```

**Impact:**
- A new allocator object with a new id. `test_allocator_ids_are_unique_across_methods` passes:
  `M0208-A2` is used nowhere else.
- `hardgate._INGREDIENT` is `<(M\d{4})>`, so `allocator=<M0208-A2>` matches nothing and D12's
  ingredient map does not move.
- No recorded `config_digest` moves: `OverhangParams` is untouched and `config_text` differs from
  trial 853's on the `allocator=` line alone.
- `control_shape` classification, verified on this tree before the file was written:
  `kind_of(M0208-CGO-N20-PLC2)` is `placebo`; `resolve_target` is
  `('M0208-CGO-N20', 'sibling-stem')`. **Nothing existing moves**:
  `M0208-CGO-N20-PLC` still resolves `('M0208-CGO-N20', 'sibling-stem')` and `M0208-HASH-N20`
  still resolves `('M0208-CGO-N20', 'first-declared')`, because `_eligible_targets` excludes
  placebo arms and the new arm is one.
- The rationale carries `"placebo"` and `"hash order"` (both in `control_shape.DRAW_MARKERS`) and
  none of `DOSE_MARKERS`. Wording it as a dose-response arm would make D17's refusal vanish with
  the handicap still in place; `control_draw`'s own docstring forbids that outright.

---

### Step 2d: Register the amendment

**File:** `engine/src/seer_engine/lab/methods/m0208_capital_gains_overhang.py:660`
**Change:**
```python
    amendments=(MATCHED_DRAW, SHADOW_DRAW),
```
**Impact:** `runner.pending_amendment` compares the recorded rows field for field against the
file's blocks and requires the record to be an exact **prefix**. `MATCHED_DRAW` stays first and
unedited, so seq 1 still matches and seq 2 is what `--amend` will run.

---

### Step 2e: The test module, inverted to the post-run truth

**File:** `engine/tests/test_lab_m0208_matched_draw.py`
**Change:** replace the one test that pins the amendment count, and add the A2 guards beside the
A1 ones. The existing A1 tests are **not** touched.

Replace lines 148-154 — the whole of `test_m0208_carries_exactly_one_amendment_of_one_arm` — with:

```python
def test_m0208_carries_two_amendments_of_one_arm_each():
    """This used to pin "exactly one amendment", which is a pre-run fact about the database and
    goes red the moment the next amendment is pre-registered. Inverted to the post-run truth,
    which is the stronger assertion: both blocks exist, in order, the recorded one is still FIRST
    and still carries its own date, and neither grew a second arm. ``runner.pending_amendment``
    requires the record to be an exact prefix of the file, so an amendment that was reordered or
    reworded would refuse the next run; this is the import-time half of that check."""
    amendments = m0208.METHOD.amendments
    assert len(amendments) == 2
    assert amendments[0].added == date(2026, 10, 19)
    assert amendments[1].added == date(2026, 10, 20)
    assert [c.id for c in amendments[0].candidates] == [NEW]
    assert [c.id for c in amendments[1].candidates] == [SHADOW]
    assert len(m0208.METHOD.candidates) == 4
    assert len(m0208.METHOD.all_candidates()) == 6


def test_the_shadow_arm_reads_as_a_placebo_on_the_book_it_means_to_control():
    """Same guard as the A1 arm's, for the same reason: D17 tests dose BEFORE draw, so an arm
    worded as a dose-response one would carry no ratio at all and its refusal would vanish with
    the handicap still in place."""
    arms = list(m0208.METHOD.all_candidates())
    arm = _arm(SHADOW)
    text = arm.rationale.lower()
    assert cs.kind_of(arm) == cs.KIND_PLACEBO
    assert any(m in text for m in cs.DRAW_MARKERS)
    assert not any(m in text for m in cs.DOSE_MARKERS)
    assert cs.resolve_target(arm, arms) == (TARGET, cs.RUNG_STEM)


def test_the_shadow_arm_moves_neither_earlier_controls_resolution():
    """What makes this amendment additive. ``_eligible_targets`` excludes placebo arms, so a third
    placebo arriving cannot become anybody's target and no existing finding moves."""
    arms = list(m0208.METHOD.all_candidates())
    assert cs.resolve_target(_arm(OLD), arms) == (TARGET, cs.RUNG_FIRST)
    assert cs.resolve_target(_arm(NEW), arms) == (TARGET, cs.RUNG_STEM)


def test_the_shadow_allocator_is_a_third_id_and_names_no_ingredient():
    assert m0208.SHADOW.id == "M0208-A2"
    assert m0208.MATCHED.id == "M0208-A1" and m0208.OVERHANG.id == "M0208"
    assert _INGREDIENT.findall("allocator=<M0208-A2>") == []


def test_the_shadow_replay_fits_the_fixture_and_pays_for_every_step_it_takes():
    """The lookback is ``PREVIOUS_DECISION_BARS`` per replayed decision, through the module's own
    arithmetic and never a number guessed per file, and the cap is absolute: ``labkit.smoke_market``
    is 473 sessions, so 8 steps (461) is the deepest replay that can run at all."""
    p = _arm(SHADOW).params
    inner = factor_lookback(p.inner)
    assert m0208.SHADOW.lookback(p) == cd.shadow_lookback_for(inner, m0208.SHADOW_DEPTH)
    assert m0208.SHADOW.lookback(p) == inner + m0208.SHADOW_DEPTH * cd.PREVIOUS_DECISION_BARS
    assert cd.shadow_lookback_for(inner, 1) == cd.lookback_for(inner)
    assert 1 <= m0208.SHADOW_DEPTH <= cd.max_shadow_depth(inner) == 8
    assert m0208.SHADOW.lookback(p) <= SMOKE_BARS == cd.FIXTURE_BARS


def test_the_shadow_replays_the_calendar_this_chassis_actually_decides_on():
    """``shadow_selection`` derives its dates with ``control_draw.previous_decision_date``, while
    this file's own ``previous_month_end`` reads the market symbol's grid. On this chassis they are
    the same session -- the last one before the first of the month -- and the arm would be replaying
    a calendar the book never used if they were not. The free pre-run probe asserted it over every
    decision of the dev window before this file was committed; this pins the one-step identity so a
    later calendar change goes red here rather than inside a recorded trial."""
    for d in (date(2015, 6, 30), date(2009, 1, 30), date(2001, 2, 28)):
        assert cd.shadow_decision_dates(d, 1)[0] == cd.previous_decision_date(d)
        assert cd.shadow_decision_dates(d, 3) == [
            cd.previous_decision_date(cd.previous_decision_date(cd.previous_decision_date(d))),
            cd.previous_decision_date(cd.previous_decision_date(d)),
            cd.previous_decision_date(d),
            d,
        ]


def test_the_shadow_arm_declares_both_controls_it_replaces():
    """D17 supersedes a ``warn`` finding as well as a ``refuse`` one, so both earlier draws are
    named. Declared, never inferred: an arm that declares nothing retires nothing."""
    assert _arm(SHADOW).supersedes == ("M0208-CGO-N20-PLC", "M0208-HASH-N20")
    assert _arm(NEW).supersedes == (OLD,)
    for c in m0208.METHOD.candidates:
        assert c.supersedes == (), f"{c.id}: an original arm declares nothing"


def test_the_shadow_arm_minted_no_params_dataclass_and_moved_no_recorded_digest():
    """The set's one params rule. ``registry._canon`` renders a dataclass by
    ``dataclasses.fields()``, so one more field on ``OverhangParams`` would move all FIVE recorded
    M0208 digests, trial 853's included."""
    assert [f.name for f in fields(m0208.OverhangParams)] == [
        "inner", "keep", "signal", "seed", "market"
    ]
    assert not hasattr(m0208, "ShadowParams"), "no new params dataclass: reuse, do not mint"
    shadow, target, prior = _arm(SHADOW), _arm(TARGET), _arm(NEW)
    assert shadow.params == target.params == prior.params
    assert config_digest(shadow) not in {config_digest(target), config_digest(prior)}
    one, other = config_text(shadow).splitlines(), config_text(prior).splitlines()
    assert [a == b for a, b in zip(one, other, strict=True)].count(False) == 1


def test_the_shadow_draw_refuses_to_shadow_anything_but_the_high_side():
    import pytest

    p = m0208.OverhangParams(m0208.N20, keep=40, signal="hash")
    rows = [m0208.FactorRow("AAA", 1.0, 0.0, 0.0, 0.0)]
    grid = object.__new__(m0208.WeekGrid)
    with pytest.raises(ValueError, match="signal must be 'high'"):
        m0208.SHADOW._targets({}, rows, grid, date(2015, 6, 30), frozenset(), p)
```

And add, beside `NEW`/`OLD`/`TARGET` at the top of the module (`:30-32`):

```python
SHADOW = "M0208-CGO-N20-PLC2"
```

and extend the module docstring's first line to read `M0208's two re-drawn controls`.

**Impact:** `pytest engine/tests/test_lab_m0208_matched_draw.py` green. **Measured at `e3aeeff`,
this is the only test module the amendment turns red** — `test_lab_control_shape.py`'s
`BLOCKED_NINE` still asserts `M0208-HASH-N20` reads `REFUSE` with ratios 4.405/5.197, which stays
true (a superseded finding keeps its verdict and its row; only `refusals` drops it), and
`test_lab_methods.py`'s sweeps are parameterised over `all_candidates()` and simply gain one case.
**That measurement was taken at the base commit; phase 2 lands first, so re-run the full suite
and treat any further red as phase 2's contract moving under this file** (`seer-plan-impact-measurements-go-stale`).

---

### Step 3: COMMIT — the commit is the pre-registration (I7)

**File:** none.
**Change:** the method file and the test module go in **before** anything runs. `lab run --amend`
refuses an uncommitted or dirty file through `registry_problem`, and a lab database committed ahead
of the method files it refers to puts `main` in a state where a fresh clone fails the sha freeze.

**Code:**
```bash
cd /home/miftah/seer
/home/miftah/seer/engine/.venv/bin/ruff check engine
PYTHONPATH=/home/miftah/seer/engine/src /home/miftah/seer/engine/.venv/bin/pytest \
  engine/tests/test_lab_m0208_matched_draw.py engine/tests/test_lab_methods.py \
  engine/tests/test_lab_control_shape.py engine/tests/test_lab_control_draw.py -q
PYTHONPATH=/home/miftah/seer/engine/src /home/miftah/seer/engine/.venv/bin/pytest engine/tests -q

git add engine/src/seer_engine/lab/methods/m0208_capital_gains_overhang.py \
        engine/tests/test_lab_m0208_matched_draw.py
git commit -m "$(cat <<'EOF'
lab: M0208 pre-registered — the honest control re-drawn against a replayed shadow of the book's own holdings

CGO-N20-PLC is an honest draw and still not a match: 455 trades against 624 and
2.313 turnover against 3.061, 0.73x and 0.76x, outside D17's 0.80-1.25 match band
on both axes. The cause is the stand-in, not the draw — the matched draw has no
record of what CGO-N20 held, so it reads a fresh top twenty at the previous month
end, and a fresh top twenty is ranked 1-20 while the band drops a name only past
rank 40. Measured over all 169 live decisions: 304 estimated entries against 624
real, 0.487x, uniform across eras.

Amendment 2 adds M0208-A2, which replays CGO-N20's own band, switch and ranking
forward from an empty book a fixed number of decisions back, and draws against
that drifted set instead. A new allocator id, not a wider A1: A1 drew trial 853
and its body is outside config_digest.

The bar, written before the run: at least 500 trades and 2.4492 turnover, at most
752 and 3.8268. A warn arm retires nothing and leaves the published sentence a
floor. This buys an honest control and no promotion — the gate tests the folds
before D17 and the kin rule stands behind it.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
git rev-parse --short HEAD
```
**Expected exit code:** `ruff` **0**, `pytest` **0**, `git commit` **0**.
**Impact:** the pre-registration exists. **Nothing is pushed yet** — a push before the run is
harmless but a push *after* the run must carry the database, and keeping them in one push keeps
`main` self-consistent. Record the commit sha; the trial will record it as its `git_sha`.

> **Shared-index discipline.** This checkout is `main` and other sessions may be using it. Commit
> by pathspec here (this is a source commit, not `lab stage`), never `git add -A`, never
> `git reset --hard`, never `git pull --rebase` while a lab batch is in flight
> (`seer-rebase-replays-stale-lab-sqlite`).

---

### Step 4: `lab run M0208 --amend`

**File:** none — the database.
**Change:** one dev trial under `M0208-A2`, one `method_amendments` row (seq 2).
**Code:**
```bash
cd /home/miftah/seer
git hash-object lab/lab.sqlite                      # before
SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
PYTHONPATH=/home/miftah/seer/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab run M0208 --amend \
    > "$SCRATCH/m0208_amend2_run.log" 2>&1
echo "exit=$?"
cat "$SCRATCH/m0208_amend2_run.log"
git hash-object lab/lab.sqlite                      # after — it MUST have moved
```
**Expected exit code:** **0**. **2** means the lab's rules refused the request — an uncommitted or
dirty file, a digest already run, all amendments already run, or a status that forbids amending;
read the message, do **not** retry blind. **1** is an error.
**Expected cost:** M0208's dev sweep with `SHADOW_DEPTH` extra `scored` passes per decision. A1's
arm paid two passes; this pays `1 + K`. At `K = 8` budget roughly four to five times amendment 1's
wall clock. **Do not run anything else heavy at the same time** — one `dev.run_registry` sweep
holds the whole research store in memory and a parallel wave has taken this laptop down twice.
**Impact:** the trial is **part of the record the moment it lands**. `trials` is append-only by
trigger. There is no rollback after this point; the repair for anything wrong is a further
amendment, never a revert. This is why steps 1 and 3 come first.

---

### Step 5: `lab control M0208`

**File:** none.
**Change:** none — it is a reader. No trial, moments, funding, status or journal row is written.
**Code:**
```bash
cd /home/miftah/seer
git hash-object lab/lab.sqlite
PYTHONPATH=/home/miftah/seer/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab control M0208 \
    > "$SCRATCH/m0208_control.log" 2>&1
echo "exit=$?"
cat "$SCRATCH/m0208_control.log"
git hash-object lab/lab.sqlite
```
**Expected exit code:** **0**.
**Expected shape of the output:** four control rows for M0208 —
`M0208-HASH-N20` (4.41 / 5.20, refuse), `M0208-CGO-N20-PLC` (0.73 / 0.76, warn) and
`M0208-CGO-N20-PLC2` with its measured pair. If the new arm reads `ok`, both earlier rows print as
**superseded by** it and keep their own verdicts and ratios — a supersession narrows what a gate
acts on and never removes a row.
**Impact:** none. Any `lab` command may migrate the file on connect; hash before and after and
record both (I5).

**Also re-read D17's live state directly, not through the refusal message** — `hardgate.check`
short-circuits before D17 for most methods, so its message is not evidence about D17:
```bash
cd /home/miftah/seer
PYTHONPATH=/home/miftah/seer/engine/src /home/miftah/seer/engine/.venv/bin/python - <<'PY' \
    > "$SCRATCH/m0208_d17.log" 2>&1
from seer_engine.lab import hardgate, store
conn = store.connect_readonly()
try:
    print("mis_shaped_controls:", hardgate.mis_shaped_controls(conn, "M0208"))
    print("failed_kin:", hardgate.failed_kin(conn, "M0208"))
    print("check:", hardgate.check(conn, "M0208"))
finally:
    conn.close()
PY
echo "exit=$?"; cat "$SCRATCH/m0208_d17.log"
```
**Expected:** `mis_shaped_controls` returns `()` if the new arm is `OK` and
`('M0208-HASH-N20',)` if it is not. **`check` still REFUSES either way** — on `OK` the operative
clause moves from D17 to the **kin rule**, `failed_kin` returning `('M0002',)`. Record both lines
verbatim. If this script's helper names differ on this tree, read them off
`engine/src/seer_engine/lab/hardgate.py` rather than guessing; the point is the three values, not
the script.

---

### Step 6: `lab note` — **only** if the arm is band-clean

**File:** `$SCRATCH/m0208_note.md` (scratchpad, read by `lab note --file`).
**Change:** `methods.verdict` (the sentence the owner reads first) and an appended dated
`methods.analysis` section.

**The condition, and it is not negotiable.** Run this step **only** when `lab control` reads **ok**
on **both** axes. A `warn` arm retires nothing and the floor is still a floor. If the arm is
`warn` or `refuse`:

- **do not run `lab note` at all**;
- the verdict keeps its current wording — *"...a meaningless book by at least 4.3 points a year -
  provisional, and a floor rather than a measurement, because even the fairest control the lab can
  draw here still trades a quarter less than the book..."*;
- `phase-3-results.md` says in one sentence that the sentence did not move and why, and phase 6
  carries it as an open row rather than as a phase that forgot.

**I12 — owner-facing text carries no ids, digests, code or jargon.** No `M0208`, no
`M0208-CGO-N20-PLC2`, no `D17`, no `WARN_BAND`, no allocator names, no sha.

**Code — the verdict (one line, substitute the measured numbers):**
```bash
cd /home/miftah/seer
PYTHONPATH=/home/miftah/seer/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab note M0208 \
  --file "$SCRATCH/m0208_note.md" \
  --verdict "Dev-eligible but refused by the hard gate: beat SPY on the deposits (+13.9% vs +7.2% a year) and a meaningless book of the same shape by <MARGIN> points a year - measured now rather than a floor, because the fairest control the lab can draw finally trades as often as the book does; the earlier figures of 6 points and of at least 4.3 are both withdrawn. It still moves with the momentum book that already failed its test and trailed SPY in 2009-2015." \
  > "$SCRATCH/m0208_note.log" 2>&1
echo "exit=$?"; cat "$SCRATCH/m0208_note.log"
```

**Code — the analysis body, `$SCRATCH/m0208_note.md` (substitute every `<…>`):**
```markdown
**The margin over a meaningless book is now a measurement rather than a floor.**

The last entry said the lead was *at least* 4.3 points a year, and explained why it could be no
more precise than that: the fairest control the lab could draw still traded only 455 times against
the book's 624, so it was still under-paying the fee bill, and a control that paid the whole bill
would earn less and the true lead would be wider.

A control that does pay the whole bill has now been drawn. It trades <TRADES> times against the
book's 624 and turns the book over at <TURNOVER_RATIO> times the book's rate - inside the match
band on both counts, which is what "the same shape" has to mean before a margin is worth quoting.
It earned **<CONTROL_MWR>% a year** on the same deposits, against the book's **13.9%**. So the
lead is **<MARGIN> points a year**, and the word "at least" comes off it.

**What changed in the drawing.** The old control had to guess what the book was holding before
each month's decision, because nothing in the machinery records it, and it guessed with a freshly
taken list of the twenty best names. That list is far too tidy: a name only leaves this book once
it has slipped out of the top forty, and a freshly taken top twenty is nowhere near that edge,
while the book's real holdings have been drifting toward it for months. The new control replays
the book's own rule forward from an empty book <STEPS> months back, so it is holding a drifted set
by the time it has to count. <DIRECTION_SENTENCE>

**The promise written before the run was a lead of at least 2 points, and it is still met.**

**Nothing else changes.** The method is still dev-eligible and still refused by the hard gate, for
the reasons given above: it moves with the momentum book that already failed its one look at the
later years, it trailed SPY in 2009-2015, and it falls past the drawdown limit once dead companies
are added back. No look was spent on the later years and the book itself was not re-run: this is
the same book, read against a fairer opponent.
```

where `<DIRECTION_SENTENCE>` is one plain sentence saying which way the money went and is written
**after** the number is known — e.g. *"Trading more means paying more, and the control duly earned
less than the old one did."* or, on a reversal, *"Trading more cost it fees and yet it earned more
than the old one, which is a reminder that a blind draw's return is close to arbitrary and that the
only honest fix is to match the shape, not to guess the direction."*

**Rehearse on a COPY first. `--dry-run` is not a safety net for this command.** Measured in
`commands/lab.py`: only `lab test` and `lab gate-probe` read `args.dry_run`; `_note` and
`_insight` commit inside `with conn:` regardless, so `lab note --dry-run` would write for real.
The only safe rehearsal is a copy of the database pointed at by `SEER_LAB_DB`:

```bash
cp /home/miftah/seer/lab/lab.sqlite "$SCRATCH/rehearse.sqlite"
SEER_LAB_DB="$SCRATCH/rehearse.sqlite" PYTHONPATH=/home/miftah/seer/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab note M0208 \
  --file "$SCRATCH/m0208_note.md" --verdict "<the string>" \
  > "$SCRATCH/m0208_note_rehearsal.log" 2>&1
echo "exit=$?"; cat "$SCRATCH/m0208_note_rehearsal.log"
sqlite3 "file:$SCRATCH/rehearse.sqlite?mode=ro" \
  "select verdict from methods where id='M0208';"       # read it as the owner will
git -C /home/miftah/seer hash-object lab/lab.sqlite      # MUST be unmoved by the rehearsal
```

Only once the rehearsal reads right does the real command run against `lab/lab.sqlite`.

**Expected exit code:** **0**. The command prints one confirmation line
(`M0208: analysis appended (N characters); verdict set to "…"`).
**Impact:** both writes are irreversible in practice — the analysis is append-only
(`store.append_analysis`) and the verdict is the method's standing summary. **Never pipe this
command** and **never retry it on a non-zero exit without reading the journal first** (I4): the
same ten-thousand-character note was once appended to M0245 twice because a filter owned the exit
code. If it does fail, read `methods.analysis` read-only before doing anything else.

---

### Step 7: `lab stage`, commit, push

**File:** `web/data/lab.json`, `lab/lab.sqlite`.
**Change:** the web snapshot is regenerated and git-added together with the database, under the
write lock.
**Code:**
```bash
cd /home/miftah/seer
PYTHONPATH=/home/miftah/seer/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab stage \
    > "$SCRATCH/m0208_stage.log" 2>&1
echo "exit=$?"; cat "$SCRATCH/m0208_stage.log"
git status --porcelain
git hash-object lab/lab.sqlite

# NO PATHSPEC. A pathspec re-reads the working tree and defeats `lab stage`'s own staging.
git commit -m "$(cat <<'EOF'
lab: M0208 — <the plain one-line outcome, e.g. "the honest control now trades like the book, and the lead is X points a year">

The re-drawn control recorded <TRADES> trades and <TURNOVER> turnover against the
book's 624 and 3.0614 — <T_RATIO>x and <TO_RATIO>x, <inside|outside> the 0.80-1.25
match band. Replaying the book's own band forward from an empty book <STEPS>
decisions back recovers <RATIO> of its real entry count, against the fresh top-N
stand-in's 0.487.

<If band-clean:> The arm supersedes both earlier controls, D17 no longer refuses
M0208, and the published sentence stops saying "at least".

The gate still refuses M0208 and this changes nothing about that: the kin rule
stands immediately behind D17, and M0208's kin M0002 has already spent and failed
its test-window look. Honest control, not a promotion.

Test-window looks 4 -> 4. No look was spent.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
git push origin main
```
**Expected exit code:** `lab stage` **0**, `git commit` **0**, `git push` **0**.
**Impact:** `lab/lab.sqlite` and `web/data/lab.json` agree row for row — CI checks it with
`test_the_committed_snapshot_is_the_export_of_the_committed_database`.

**If the push is rejected, MERGE — never rebase.** `git fetch origin` then
`git merge origin/main`; a `git pull --rebase` replays a stale `lab.sqlite` over the live shared
database other sessions in this set are writing (`seer-rebase-replays-stale-lab-sqlite`). After
the merge, **re-run `lab stage`** so the snapshot matches the merged database, check
`select n from trials order by n` is still contiguous, commit the re-stage with **no pathspec**,
and push again. Phases 5 and 6 carry the identical rule.

> **The snapshot test is expected RED between Step 4 (`lab run`) and Step 7 (`lab stage`), and the
> suite must not be run in that window.**
> `test_lab_snapshot.py::test_the_committed_snapshot_is_the_export_of_the_committed_database`
> compares the committed snapshot to the committed database and reads the **working tree**, so a
> freshly-run trial that has not been staged makes it fail by construction. That is not a failure
> to chase. **Invariant I11 asks for a green suite at the END of the phase, after `lab stage` —
> not in the middle of it.** Phases 5 and 6 have the same window and say the same thing.

---

### Step 8: `phase-3-results.md`

**File:** `.workflows/plan/control-draw-remedies/phase-3-results.md` (new).
**Change:** the write-up, in the shape this lab's results files take
(`.workflows/plan/honest-control-redraw/phase-3-results.md` and `phase-6-results.md` are the
models). It must contain, at minimum:

1. **Header block** — written date, verdict in one word, the rule and allocator id
   (`M0208-A2`, `control_draw` v2 via `shadow_selection`, `SHADOW_DEPTH = K`), the
   pre-registration commit sha, the trial
   number, and what ran.
2. **The go/no-go probe** — the full `K` ladder, both anchors (624 and 304), the era table, the
   chosen `K` and why, and the switch-guard discrepancy against phase 1's number if there is one.
3. **The shape** — the `lab control M0208` table verbatim, raw counts beside the book's 624 /
   3.0614, the two ratios, and the band arithmetic (500 … 752 trades, 2.4492 … 3.8268 turnover).
   Say which axis bound and by how much.
4. **The money** — `trial_funding.mwr` for the book, both earlier controls and the new one, against
   SPY TR's 7.188 %/yr on the same deposits; the old margin (+4.346), the new one, and the delta.
   Score the pre-registered prediction honestly, including the parts that came out wrong.
5. **D17's live state** — `mis_shaped_controls`, `failed_kin` and `check`, verbatim, read through
   `store.connect_readonly`.
6. **R3, in its own section with its own heading** — see below.
7. **Database** — `git hash-object lab/lab.sqlite` before and after every command that could move
   it; trials added; amendments added; luck-gate N (unchanged — an amendment appends under an
   existing id); **test-window looks 4 → 4, asserted**; M0208's status (unchanged — an amendment
   never moves a verdict; only `lab reevaluate` does).
8. **Tree** — `ruff check engine` and `pytest engine/tests` output.
9. **For phase 6** — the measured ratios, D17's state, whether the published sentence moved, and
   any handoff.

**The R3 section, written out so it cannot be softened in the writing:**

```markdown
## The gate still refuses M0208, and this phase bought no promotion

`hardgate.check` short-circuits at the first failing clause, in this order:

    fold count -> fold majority -> the promoted variant's own folds -> survivorship drawdown
      -> D17 -> kin

M0208 is the **only** one of the nine methods the honest-control set re-drew whose operative
clause is D17: it is the only one that clears the fold majority (3 of 4), its promoted variant's
own folds (CGO-N40, 3 of 4) and the survivorship drawdown bar. And the clause immediately behind
D17 is the **kin rule**: `failed_kin("M0208")` returns `('M0002',)`, and M0002 has already spent
and **failed** its one look at the test window. M0208-CGO-N20's market-neutral monthly return
moves with M0002-REL-85 at 0.90 residual correlation, above the 0.85 line.

So clearing D17 changes the **refusal message** and not the **answer**. Nothing in this phase
makes M0208 promotable, nothing here is an argument that it should be promoted, and no sentence
written by this phase may be read as implying one. What the phase buys is an honest control: a
number where there was a floor.

Separately: this phase spent **no** test-window look. `lab test` was never invoked and
`SEER_RESEARCH_TEST_STORE` was never read. Looks: 4 before, 4 after.
```

**Impact:** documentation only. Commit it with step 7's commit or in a follow-up source commit —
it is not part of the staged database.

---

## Verification

**Build:** `/home/miftah/seer/engine/.venv/bin/ruff check engine` — *All checks passed!*
(CI lints bugs only: E9 and F, minus F401.)

**Tests:**
```bash
cd /home/miftah/seer
PYTHONPATH=/home/miftah/seer/engine/src /home/miftah/seer/engine/.venv/bin/pytest engine/tests
```
The whole suite, not a subset, and with `PYTHONPATH` set — without it pytest silently tests the
main checkout's `seer_engine` and `config.REPO_ROOT` resolves a different `lab.sqlite`
(`seer-worktree-tests-need-pythonpath`). The suite runs under `-n auto`; use `-n0` only to chase a
specific failure, and never `-o addopts`. Must include green:

- `test_lab_m0208_matched_draw.py` (all of it, old tests and new)
- `test_lab_methods.py::test_every_recorded_configuration_still_digests_to_its_recorded_digest`
- `test_lab_methods.py::test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha`
- `test_lab_methods.py::test_candidate_runs_a_smoke_window[M0208-CGO-N20-PLC2]` and
  `::test_allocator_contract[M0208-CGO-N20-PLC2]`
- `test_lab_methods.py::test_allocator_ids_are_unique_across_methods`
- `test_lab_control_shape.py` (the `BLOCKED_NINE` snapshot and the supersession-shape test)
- `test_lab_control_draw.py` and phase 2's `test_lab_control_draw_shadow.py`

**Manual checks:**
- `git hash-object lab/lab.sqlite` recorded at six points: before step 1, before and after `lab
  run`, before and after `lab control`, after `lab stage`. Only `lab run` and `lab stage` may move
  it; the `sqlite3 … mode=ro` reads never do.
- `sqlite3 "file:lab/lab.sqlite?mode=ro" "select count(*) from trials where window='test'"` reads
  **4** before and **4** after.
- `select n from trials order by n` is contiguous — a rebase that replayed a stale database would
  show a gap.
- `select seq, added from method_amendments where method_id='M0208'` reads seq 1 (2026-10-19) **and**
  seq 2 (2026-10-20); seq 1's `why`/`hypothesis`/`expected_failure` are byte-identical to what they
  were.
- `web/data/lab.json` and `lab/lab.sqlite` committed together, in one commit, with **no pathspec**.

**Exit criteria:**
1. The free probe ran on the real store, printed the full `K` ladder with both anchors, and gave a
   recorded **GO** or **STOP** — before any file was edited.
2. A new allocator id `M0208-A2` and a new `Amendment` block exist, appended **after** the recorded
   one, with `why`, `hypothesis` and `expected_failure` written and committed **before** the run.
3. `M0208-CGO-N20-PLC2` is recorded as a dev trial under method id M0208, and its trades and
   turnover are reported against the required **≥ 500 trades / ≥ 2.4492 turnover** (and ≤ 752 /
   ≤ 3.8268), with the band verdict stated.
4. D17's live state for M0208 is re-read through `store.connect_readonly` and recorded verbatim.
5. The published sentence is updated by `lab note` **if and only if** the arm reads `ok` on both
   axes; otherwise the results file states that it stays a floor and why.
6. `lab stage` ran, database and snapshot are committed together and pushed.
7. `ruff` clean, `pytest engine/tests` green.
8. **Test-window looks 4 → 4, asserted and written down.** `lab test` never invoked.
9. **The results file states, in its own section, that the gate still refuses M0208 whatever D17
   now says**, and no sentence anywhere implies a promotion.

---

## Handoffs

**To phase 5 (the weight axis):**
- **M0201 is not touched here.** `M0201-Y20-MV10-PLC1` misses on **turnover** (0.794 against the
  0.800 bar, 0.0059 short) and its entry-count estimator was measured at 0.955 — a shadow is the
  wrong instrument for it. The file is phase 5's, and phase 4's measurement decides whether it is
  re-drawn at all. **R2, not R1.**
- **M0221 and M0225 are not touched here** for the same reason, structurally: `M0221-E50` pays
  1.60× turnover on `C50`'s identical names and identical trades, so no rule that chooses *which
  names* a control holds can reach their miss.

**To phase 6 (the close-out):**
- This phase **journals no insight** (I4 / the plan's phase-6 ownership). Two candidate insights
  are handed over as prose in `phase-3-results.md`, unjournalled, for phase 6 to write with
  `lab insight` one command at a time: (a) a control's stand-in for *what the real book held* must
  carry the switch as well as the band — part of the 0.487× was switch-off re-entry months read as
  two or three entries instead of twenty; (b) the lift from a better entry-count estimate is
  **sublinear**, because realised entries are `Σ max(e, attrition)` and attrition stops binding as
  `e` rises.
- The owner-facing sentences this phase may move: M0208's **verdict** string ("by at least 4.3
  points a year - provisional, and a floor") and the 2026-10-20 **analysis** section that explains
  the floor. Phase 6 still owns M0221's "between 0 and 0.4" and M0225's "−0.890".
- The `M0208-HASH-N20` → `M0208-CGO-N20-PLC` → `M0208-CGO-N20-PLC2` supersession chain is a
  **three-arm** chain and the first genuine one in the lab. Worth a line in the close-out: a
  superseded `warn` arm can itself be superseded, and every row stays printed with its own ratios.

**Deliberately left undone (drive-bys, not scope):**
- `engine/tests/test_lab_m0208_matched_draw.py`'s module docstring says the smoke fixture never
  exercises the draw (473 sessions, `overhangs` needs 780). That is still true of the shadow and
  is worth saying in the docstring, but it is not re-engineered here.
- A memo over the replay's repeated `scored` calls would cut the run's cost materially. Considered
  and rejected (I9 and `targets()`'s missing `prepared`); recorded here so the next reader does not
  rediscover it as a bug.
- `control_draw.RULE_ID` is **not** stamped into M0208's `params.as_dict()` — this chassis never
  stamped it — so there is nothing to bump here. The v2 rule's record is the allocator id.

---

## Rollback

| up to | how |
|---|---|
| **before step 4 (`lab run`)** | `git revert` the pre-registration commit, or `git reset` it if unpushed. Nothing is recorded; the probe wrote only to the scratchpad. This costs no method id, no trial, no N and no look — which is exactly why I7 puts the commit before the run and why step 1 probes for free first. |
| **after step 4** | **The trial cannot be rolled back.** `trials` is append-only by trigger and that is the point. `method_amendments` likewise. The repair for anything wrong in the arm is a **further amendment**, never a revert — and reverting the method-file commit after the run would leave the database referring to a file that no longer hashes to its recorded `source_sha`, failing `store.latest_source_sha` on a fresh clone. |
| **the `lab note`** | `methods.verdict` is not append-only and can be rewritten by a later `lab note --verdict`. `methods.analysis` **is** append-only: a wrong section can only be superseded by a later dated one, never removed. |
| **the staged snapshot** | re-run `lab stage` and commit again, with no pathspec. |
| **the whole phase, as the set sees it** | `main` carries it. The engine commit is cleanly revertible; the lab rows stay, as every lab row does. |
