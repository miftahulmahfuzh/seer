> Adopted from `.workflows/orchestration/roster-35-four-methods/PLAN.md` phase 3. Source: `.workflows/plan/roster-35-four-methods/phase-3.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 3: M0155 — trim a holding falling apart while the market is fine

**Plan set:** `ROSTER_35_FOUR_METHODS_PLAN.md`
**Analysis:** `docs/analyzer/20261014-150738-B7K4_code_analyzer.md`
**Satisfies:** R2 (a single-name brake measured against M0152's width curve), R6 (no test-window look is spent)
**Depends on:** none
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab`

---

## Goal

`M0155` moves from an `idea` row to a recorded, pre-registered method with six run arms and a
written verdict. After this phase the lab can answer, with numbers on **both** price histories,
whether letting go of a holding that has fallen hard against the index while the market is fine
closes the spring-2006 hole at twenty names — or whether it is width in disguise and the honest
answer stays the thirty-five names M0152 recommended. Nothing in the roster, in `grid.csv`, or in
any other method file moves, and the test-window look count stays at 4.

## Interface Contract

**Creates:**
- `engine/src/seer_engine/lab/methods/m0155_single_name_shortfall_brake.py` — new file
  - `m0155_single_name_shortfall_brake.ShortfallBrakeParams` (new frozen dataclass)
  - `m0155_single_name_shortfall_brake.ShortfallBrakeAllocator` with **allocator id `"M0155"`**
  - module-level `SHORTFALL`, `HOST`, `METHOD`, `ADDED`, `ZERO`, `K15`, `K20`, `K25`
  - helpers `shortfall_z`, `market_calm`, `braked_names`, `brake_targets`, `_window`, `_priced`, `_check`
- `engine/tests/test_lab_m0155_brake.py` — new test module (9 tests)
- `docs/lab/survivorship/single-name-brake-eras-2026-10-14.csv` — new dated grid
- `docs/lab/survivorship/single-name-brake-2026-10-14.md` — new dated report
- lab rows: method `M0155` moves `idea` → `registered` → (`dev-eligible` | `rejected`); six
  `trials` rows with `candidate_id` in `M0155-Z2`, `M0155-Z2-FILL`, `M0155-Z15-FILL`,
  `M0155-Z25-FILL`, `M0155-Z2-HALF`, `M0155-Z2-FILL-UP`; one `method_folds` row; one
  `insights` observation from `lab survivorship`; one `insights` feature wish; one verdict.

**Deletes:** nothing.
**Renames:** nothing.
**Signature changes:** none. No existing symbol gains, loses or changes a field.

**Requires (from earlier phases):** nothing. This phase reads only things that are already on
`main` at `661870d`.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/methods/m0149_*.py`, `m0148_*.py`, `m0156_*.py` (Phases 4, 5, 1)
- `engine/src/seer_engine/paper/roster.py`, `strategies/evidence.py`, `db/migrations/` (Phase 2)
- `docs/lab/survivorship/grid.csv` — `survivorship_record.GRID_PATH` points hard-gate D16 at that
  exact file. Never appended to.
- `engine/src/seer_engine/lab/methods/m0007_residual_momentum.py`,
  `m0011_raw_residual_own_vol.py`, `m0128_near_miss_fixed_tape.py`,
  `m0152_roster_width_rungs.py` — imported, never edited. All four have recorded trials and an
  edit to any of them moves a frozen `config_digest`.
- `engine/src/seer_engine/strategies/f_factor.py`, `allocator.py`, `sim/rules.py` — imported
  only. **Adding a field to `ResidParams`, `FactorParams` or `TradeRules` would move every
  recorded config digest in the lab** (`seer-shared-params-cannot-gain-a-field`); all new state
  lives in `ShortfallBrakeParams` inside this method's own file, behind the new allocator id.

**Shared mutable artifact:** `lab/lab.sqlite` and `web/data/lab.json`, written by Phases 1, 4
and 5 too, and regenerated alone by Phase 2. Every DB-writing command — `lab run` included — is
inside a lab-write-lock hold that ends with `lab stage` + commit + push. The lock is defined in
Step 9 and in the plan index's invariant 7; this phase takes **one** hold, from Step 4 through
Step 9. Step 5's `lab survivorship` and Step 8's `lab note`/`lab insight` are inside it.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/methods/m0155_single_name_shortfall_brake.py` | create | the whole method: params, signal, allocator, six candidates, `METHOD` |
| `engine/tests/test_lab_m0155_brake.py` | create | the three claims `allocatorkit` cannot make |
| `docs/lab/survivorship/single-name-brake-eras-2026-10-14.csv` | create | the era grid, same columns as the width curve |
| `docs/lab/survivorship/single-name-brake-2026-10-14.md` | create | the report the verdict is drawn from |
| `lab/lab.sqlite` | append | method row, 6 trials, moments, funding, provenance, folds, insights, verdict |
| `web/data/lab.json` | regenerate | `lab stage` writes it; CI checks it matches row for row |

Scratchpad only, **not committed**: `m0155_eras.py` (the era script) and the raw
`lab survivorship --csv` grid.

## What is already measured — quote it, never re-derive it

From `docs/lab/survivorship/roster-width-curve-2026-10-14.csv`, committed at `48c285f`. Every
number below is funded identically to what this phase runs (10,000,000 IDR opening, 5,000,000 IDR
on the 25th, 237 deposits) on `monthly-hold-frac-gotrade-tband`, so the arms line up against them
to the last digit. Worst falls are de-funded; era columns are month-end.

| names | id | store | daily fall | month-end fall | dated | %/yr | trades | 1998 | 2000-02 | **2006** | 2008-09 | 2010-15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 20 | `M0128-RAW20` (#388) | dev | 20.65% | 20.03% | 1998-06→08 | +13.68 | 1607 | 20.03% | 5.61% | 16.25% | 10.86% | 10.81% |
| 20 | `M0128-RAW20` (#388) | **check** | **25.05%** | 21.82% | **2006-03→07** | +11.98 | 1640 | 21.57% | 9.38% | **21.82%** | 9.08% | 9.92% |
| 35 | `M0139-N35-TBAND` (#437) | dev | 19.60% | 18.64% | 1998-06→09 | +13.05 | 2548 | 18.64% | 3.93% | 13.38% | 10.56% | 11.05% |
| 35 | `M0139-N35-TBAND` (#437) | **check** | 20.11% | 19.67% | 1998-06→08 | +12.11 | 2671 | 19.67% | 4.98% | **16.18%** | 10.08% | 10.37% |

Deposit-matched SPY TR earns **+7.19%/yr** on both stores. The 2006 row across all seven recorded
widths on the check store: **21.8 / 18.9 / 18.8 / 16.2 / 15.1 / 14.8 / 12.9** at 20/25/30/35/45/50/70.

Prior art this method must be read against, and must not repeat:

- **M0019** (dev-eligible, verdict): a 20% protective stop under each holding *made things worse* —
  the fall did not shrink and return dropped 0.7–2.4 pts/yr, because the stops fired together in
  market-wide falls, sold near the bottom and missed the rebound.
- **M0020**: the same stop with weekly re-entry still trailed; "per-stock exits are closed for this book".
- **M0035**: a whole-**book** relative-shortfall brake was *switched off throughout the fall it was
  built to cap*, because the book was 11.8 points ahead when that fall began.

M0155 differs on three axes, and the method docstring states each: the trigger is **relative** (a
market-wide fall moves the index too, so nothing fires — the exact failure that killed M0019); it
is **per holding**, not per book (M0035's aggregate was healthy while one name inside it died); and
it can only act on sessions the host's SPY-200 gate has already judged calm, with `market_up`
tightening that further.

## Hard constraints this phase works under

1. **The commit is the pre-registration.** The method file is committed **and pushed** before
   `lab run M0155`. `runner.preflight` → `registry_problem(path)` refuses an uncommitted or dirty
   file, and refuses a `config_digest` already recorded. **Never write or edit the file after
   seeing a result.**
2. **`lab test` is never called and no `--store` ever points at `engine/.research-test`.**
   `lab status` reads 4 test-window looks before and after.
3. **Never append to `docs/lab/survivorship/grid.csv`.**
4. **Commit by explicit pathspec**, never `git add -A`, never `reset --hard`. Sessions share one
   checkout and one index. There is an untracked stray named `.schema trial_provenance` in the
   working tree — leave it; do not stage it.
5. **The lab pair commits through the index, inside the lab write lock.** `lab stage` `git add`s
   `web/data/lab.json` with `lab/lab.sqlite`; `git commit -- <paths>` re-reads the working tree
   and defeats it. Commit those two with a bare `git commit -m …` and nothing else in that
   commit. The lock (Step 9) is held from `lab run M0155` through the push, and **may not be
   released while either of those two files differs from `HEAD`**.
6. **Any `lab` command migrates `lab.sqlite` on connect, even a read.** Hash before a read-only
   command, restore by path afterwards if the hash moved.
7. **Promotion is not sought and `lab promote` is never run.** M0007 is test-failed; the hard gate
   refuses this line on kin whatever it scores.

---

## Implementation Steps

### Step 0: read the idea row, and record the two look counts

**File:** none — read-only
**Change:** The frozen hypothesis in `lab/lab.sqlite` is the specification. `lab run` will
**overwrite** `methods.hypothesis` from the method file (`runner.run_method`, the `status == "idea"`
branch), and the `methods_hypothesis_frozen` trigger then seals it, so the file's hypothesis must
carry the idea's success and failure conditions in substance. Read it from a copy, because any
`lab` command migrates the database on connect.

**Code:**
```bash
cd /home/miftah/seer
cp lab/lab.sqlite /tmp/lab-ro-p3.sqlite
sqlite3 -line /tmp/lab-ro-p3.sqlite \
  "select id,name,family,source_kind,parent_id,status,hypothesis from methods where id='M0155';"

# the look count, before anything. It must read 4 here and 4 at the end.
md5sum lab/lab.sqlite
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab status | grep -i "look"
md5sum lab/lab.sqlite   # if it moved: git checkout -- lab/lab.sqlite
```

**Impact:** none. Confirms `M0155` is `idea`, `parent_id` is `M0152` (which `preflight` requires to
be in the lab), and that the test-window budget is 4.

---

### Step 1: write the method file

**File:** `engine/src/seer_engine/lab/methods/m0155_single_name_shortfall_brake.py:1` (new file)
**Change:** The whole method. Six arms, all on `MONTHLY_TBAND`
(`monthly-hold-frac-gotrade-tband`) with `RAW20` — M0007-N20-RAW's params verbatim — so an arm
here and a rung of M0152's curve differ in the brake and in nothing else.

Design decisions already taken, so they are not re-opened during implementation:

- **No control arm.** `M0128-RAW20` (trial #388) *is* the unbraked twenty-name book, recorded and
  funded identically; `lab run` would accept a brake-off arm (the allocator id differs, so the
  digest differs) but it would buy a number the lab already holds. Step 2's test module proves the
  brake-off path is target-for-target identical to `RESIDMOM`, which is strictly stronger: it is
  permanent, it costs no trial, and it is what earns the right to quote #388 as this method's control.
- **The brake filters the ranking, not the held set.** Applying it only to `held` would buy on one
  rank session the very name it would sell at the next, and would make the targets depend on
  `held`. Filtering every ranked candidate keeps the targets a pure function of bars and
  membership, so the P4 identity is trivially true.
- **A freed slot is cash under `fill=False`.** `factor_weights` with `sizing="equal"` returns
  `equal_weight(params.top)` for every row regardless of list length, so dropping a name leaves
  `1/20` of the account unspent and the survivors at their original size. `fill=True` removes
  braked names from the ranking *before* `[:top]`, so the book still holds twenty names and stays
  fully invested. Those are two different questions and the arms keep them apart.
- **`lookback()` is `max(resid_lookback(inner), look_n + 1)` = 401** for every arm — exactly
  `RESIDMOM.lookback(RAW20)`. The brake's own depth is 64 bars, so it is warm from the first
  session of the dev window and never stands down there, and the dev window opens on the same
  session as #388's. 401 is also well inside the 473-bar smoke fixture
  (`seer-lab-method-lookback-capped-by-smoke-fixture`).
- **The clock is monthly and that is a stated ceiling.** `MONTHLY_TBAND` has no `resize_cadence`,
  so `is_decision_session` is true on rank sessions only. The mid-month exit the idea also named
  would need `monthly-rank-weekly-resize-frac-gotrade`, whose band is measured against whole-account
  equity — a band the lab has measured as barely firing (`seer-resize-band-never-fires`) — so a
  result on it would not be comparable to any of the seven recorded widths. Staying on M0152's tape
  wins; a feature wish is journalled in Step 7.
- **A braked name's exit always executes; a half-cut clears the band.** In `sim/book.py:640`, a
  position missing from `wanted` is a signal exit at the open, not band-gated. A cut to half weight
  is 50% off target against `TARGET_RESIZE_BAND` of 20% under `resize_basis="target"`, so it trades.

**Code:** the complete file.

```python
"""M0155 — Let go of the one holding that is falling apart on its own, while the market is fine.

Source: a variation of M0152, which dated this account's damage for the first time.
Idea: the roster's book has exactly two defences against a fall, and M0152 measured both. The
SPY 200-day gate handles MARKET falls and handles them well -- the dot-com collapse cost this
book 4-9% and the 2008 crisis 9%, its two mildest stretches in twenty years. Width handles the
SINGLE-HOLDING blowup, and it does so by dilution: own more names and any one of them matters
less. What neither does is notice that one holding has stopped behaving like the others while
nothing at all is wrong with the market. That is spring 2006, and spring 2006 is the whole of
the roster's width problem.

**THE HOLE, dated and measured, and not re-derived here** (M0152, trial #388 and the paired
curve in ``docs/lab/survivorship/roster-width-curve-2026-10-14.csv``). On the
survivorship-check store -- the price history that keeps the companies that went bankrupt, were
bought or were renamed -- this exact book's worst fall is **2006-03-31 to 2006-07-31, 21.82%
month-end and 25.05% daily**, against an owner bar of 25%. Over that window the benchmark went
3.71 to 3.62: the market dipped about 2% and made a new high by September. The 200-day gate
never fired and was right not to. And 2006 is the ONLY width-sensitive episode in the window:

===== ===== ===== ===== ===== ===== ===== =====
names  20    25    30    35    45    50    70
===== ===== ===== ===== ===== ===== ===== =====
2006   21.8  18.9  18.8  16.2  15.1  14.8  12.9
1998   21.6  19.2  19.9  19.7  19.4  18.7  18.0
===== ===== ===== ===== ===== ===== ===== =====

Nearly nine points across the 2006 row against 3.6 across the 1998 one, and none at all in the
crisis years. For a narrow book the single-holding blowup is therefore the LARGER of the two
remaining risks, and the lab has spent most of its ids on market timing and almost none on this.

**WHAT THIS METHOD ASKS.** Width is one answer and M0152 priced it: 35 names, five points of
fall for no return cost on the honest tape. This asks whether a cheaper and more direct answer
exists -- a per-holding brake that lets go of a name which has fallen hard RELATIVE TO THE
MARKET while the market itself is fine. The deliverable is a POINT PLOTTED ON M0152'S CURVE:
the braked twenty-name book's 2006 fall and its funded return, read against the seven recorded
widths, on both stores. If the point sits inside the curve -- a gentler 2006 than 35 names at a
return no worse -- the brake buys something width cannot. If it lands on the curve, it is width
in disguise and the honest answer stays 35 names, which is the result this method expects.

**WHY THIS IS NOT A STOP-LOSS, and the lab has the receipts.** M0019 put a 20% protective stop
under each holding: the worst fall did not shrink and return dropped 0.7-2.4 points a year,
because the stops fired together in market-wide falls, sold near the bottom and missed the
rebound. M0020 added weekly re-entry and still trailed. M0035 read the whole BOOK against the
market and was switched off throughout the fall it was built to cap, because the book was
eleven points AHEAD when that fall began. Three differences, each aimed at one of those
failures:

  * **It is relative, not absolute.** The trigger is the holding's return against the index's
    over the same sessions. When the whole market drops, the index drops with the holding and
    the shortfall barely moves -- so the brake does not fire, which is exactly what killed
    M0019's stop.
  * **It is per holding, not per book.** M0035's switch read an aggregate, and an aggregate was
    healthy while one name inside it was dying. This reads the names one at a time.
  * **It is gated on the market being fine, twice over.** The host book is already all-cash
    while SPY closes under its 200-day average, so the brake can only ever act on a session the
    gate has judged calm -- the 2006 signature, enforced by construction rather than by a
    parameter. The ``market_up`` arm tightens that further and insists the index's own
    ``look_n``-session return is not negative, so the brake is silent even in the stretches
    where the slow average lags a fall that has already begun.

**THE SIGNAL, in full, and it reads only bars dated <= the data date.** On a decision session
``d`` at calendar index ``j``, take the ``look_n`` sessions ``j - look_n + 1 .. j`` of the
market symbol's calendar. For each candidate name, over the sessions in that window on which
BOTH it and the index have a usable daily return:

  * ``cum_r`` is the name's compounded return and ``cum_m`` the index's, each compounded over
    exactly those shared sessions;
  * ``sd_window`` is the standard deviation of the name's daily EXCESS return over the index,
    scaled by the square root of the number of shared sessions -- the natural yardstick for how
    far apart two series that move together normally drift over a window of that length;
  * ``z = (cum_r - cum_m) / sd_window``, and the name is braked when ``z <= -k``.

Three things about that are worth stating plainly, because they are what could fool us:

  * **The index's return is recomputed per name.** Two names with different gaps in their bars
    see slightly different ``cum_m``, because each is compared with the index over the days it
    actually traded. The alternative -- one index number for everyone -- would charge a name
    for days it was not listed.
  * **A name with less than ``MIN_FRAC`` of the window usable is NEVER braked.** The brake acts
    on evidence or it stands down; it never guesses. This matters most for a name that has just
    joined the index, which is precisely the one whose history is thin.
  * **The yardstick is the name's own drift, not a fixed percentage.** A quiet utility and a
    volatile biotech reach ``-2`` standard deviations at very different losses, which is the
    point: the question is "has this stopped behaving like itself", not "has it fallen x%".

**WHAT THE BRAKE DOES, and the two shapes that are not the same question.** ``fill=False``
drops the braked name (or cuts it to ``cut`` of its weight) and **leaves the slot in cash**: the
book holds less. ``fill=True`` removes the braked names from the ranking BEFORE the top
``top`` are taken, so the book still holds ``top`` names and stays fully invested -- the
nineteenth collapsing name is replaced by the twenty-first ranked one. These separate two
answers that would otherwise be confounded: "holding less is safer" is not a finding about
single-name risk, it is a finding about exposure, and M0109 already prices that. Only the
``fill=True`` arms can answer whether swapping the bad name out, at constant exposure and
constant width, closes the 2006 hole.

**A FILTER ON THE RANKING, NOT ON WHAT IS HELD.** The brake is applied to every ranked
candidate, not only to the names the book already owns. The alternative would buy on one rank
session the very name it would sell at the next, which is not a rule anyone would follow with
real money; and keeping it a function of bars and membership alone leaves the P4 identity
trivially true. A braked name re-enters as soon as its shortfall recovers: there is no cooling
period and no memory, deliberately, because memory is where a brake quietly becomes a strategy.

**THE CLOCK, and the limitation this method accepts rather than hides.** The book engine reads
an allocator on rank sessions and resize sessions only. ``monthly-hold-frac-gotrade-tband`` is
the tape M0152's whole curve is measured on and it has no resize cadence, so the brake here is
read ONCE A MONTH. The idea that spawned this asked for a mid-month exit; that is not available
without leaving the curve, because the only preset with a faster resize
(``monthly-rank-weekly-resize-frac-gotrade``) measures its band against whole-account equity, a
band the lab has since measured as barely firing, and no result on it would be comparable to the
seven recorded widths. Staying on M0152's tape was judged worth more than reading the brake
sooner. A feature wish is journalled for a monthly-rank / weekly-resize preset on the fixed
tape, and the monthly clock is written into the hypothesis as a known ceiling on what this can
measure, not discovered afterwards.

**WHAT THE RANKING CANNOT SEE, and why a 63-session window is not redundant with it.** The host
ranks on twelve months of cumulative market-model residual, SKIPPING the most recent 21
sessions. A name that collapsed inside the last month is invisible to the ranking by
construction, and a name that collapsed inside the last quarter is still outvoted by the nine
good months behind it. ``look_n = 63`` is one quarter: the window the ranking skips, plus the
two months it dilutes. It was fixed before the run from that construction and not from any
result.

**CALIBRATION, stated before the run.** Nothing here was tuned on an outcome. ``k`` takes 1.5,
2.0 and 2.5 because two standard deviations is the conventional line and the two neighbours
bracket it, so "did we pick a lucky threshold" is answerable from the batch itself rather than
from a second method id. ``look_n = 63`` is the skip-plus-dilution argument above. ``cut = 0.5``
is a half position, the idea's own second shape. ``MIN_FRAC`` is M0007's, unchanged, so the
evidence bar for braking a name is the evidence bar for scoring one.

**PROMOTION IS NOT AVAILABLE AND IS NOT SOUGHT.** This line runs through M0007, which is
test-failed, so the hard gate refuses it on kin whatever it scores, and the kin bar refuses the
family. Promotion would only be available for a brake built on a book whose ancestry is clean,
which this is not. Accepted before the run; any arm that reads eligible against the dev screen
is a by-product and must not be reported as a candidate.

Every piece reads only bars dated <= ``data_date``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0007_residual_momentum import (
    MIN_FRAC,
    RESIDMOM,
    ResidParams,
    ResidPrepared,
    ReturnGrid,
    build_grid,
    resid_lookback,
    residual_scores,
    targets_from_scores,
)
from seer_engine.lab.methods.m0011_raw_residual_own_vol import RAW20
from seer_engine.lab.methods.m0128_near_miss_fixed_tape import MONTHLY_TBAND
from seer_engine.sim.book import Target
from seer_engine.sim.rules import rule_owner_inputs
from seer_engine.strategies.allocator import scale_weight, target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorRow,
    factor_rows,
    factor_weights,
    trend_on,
)

ADDED = date(2026, 10, 14)

ZERO = Decimal(0)


# --------------------------------------------------------------------------- params


@dataclass(frozen=True, slots=True)
class ShortfallBrakeParams:
    """M0007-N20-RAW's picks, plus one per-holding relative-shortfall brake on top of them.

    ``inner`` is the host book verbatim and is never varied: the whole point of the measurement
    is that an arm here and a rung of M0152's width curve differ in the brake and in nothing
    else. Every field below is the brake.
    """

    inner: ResidParams
    k: Decimal | None = None  # brake at z <= -k standard deviations; None = no brake at all
    look_n: int = 63  # sessions the shortfall is measured over (one quarter)
    cut: Decimal = ZERO  # the share of its weight a braked name keeps; 0 = let it go entirely
    fill: bool = False  # True: drop braked names from the ranking, so the book still holds `top`
    market_up: bool = False  # True: act only while the index's own look_n return is not negative

    def __post_init__(self) -> None:
        if not isinstance(self.inner, ResidParams):
            raise TypeError(f"inner must be ResidParams, got {type(self.inner).__name__}")
        if self.k is not None:
            if not isinstance(self.k, Decimal) or not self.k.is_finite():
                raise TypeError(f"k must be None or a finite Decimal, got {self.k!r}")
            if self.k <= 0:
                raise ValueError(f"k must be > 0, got {self.k}")
        if isinstance(self.look_n, bool) or not isinstance(self.look_n, int):
            raise TypeError(f"look_n must be an int, got {type(self.look_n).__name__}")
        if self.look_n < 20:
            raise ValueError(f"look_n must be >= 20, got {self.look_n}")
        if not isinstance(self.cut, Decimal) or not self.cut.is_finite():
            raise TypeError(f"cut must be a Decimal, got {self.cut!r}")
        if not 0 <= self.cut < 1:
            raise ValueError(f"cut must be a Decimal in [0, 1), got {self.cut}")
        for name in ("fill", "market_up"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool, got {type(getattr(self, name)).__name__}")
        # One spelling per behaviour. A configuration that does nothing, or whose fields
        # contradict each other, would otherwise get its own config_digest and could be run
        # twice under two names as though it were two measurements.
        if self.fill and self.cut != ZERO:
            raise ValueError(
                "fill=True removes the braked name from the ranking, so there is no weight left "
                f"to cut: cut must be 0, got {self.cut}"
            )
        if self.k is None and (self.cut != ZERO or self.fill or self.market_up):
            raise ValueError(
                "with k None there is no brake, so cut, fill and market_up must be at their "
                "defaults: that configuration is the host book and has exactly one spelling"
            )

    def as_dict(self) -> dict[str, str]:
        out = {
            "k": "none" if self.k is None else str(self.k),
            "look_n": str(self.look_n),
            "cut": str(self.cut),
            "fill": "yes" if self.fill else "no",
            "market_up": "yes" if self.market_up else "no",
        }
        for key, value in self.inner.as_dict().items():
            out[f"inner.{key}"] = value
        return out


def _check(params: object) -> ShortfallBrakeParams:
    if not isinstance(params, ShortfallBrakeParams):
        raise TypeError(f"params must be ShortfallBrakeParams, got {type(params).__name__}")
    return params


# --------------------------------------------------------------------------- the signal


def _window(grid: ReturnGrid, data_date: date, look_n: int) -> tuple[int, int] | None:
    """``(w0, j)`` -- the ``look_n`` calendar columns ending at ``data_date``, or None.

    None means "not measurable here": ``data_date`` is not a session of the market symbol's
    calendar, or the calendar does not reach back ``look_n`` sessions from it. The caller then
    leaves the book unbraked, which is the control.
    """
    day = as_day(data_date)
    j = int(np.searchsorted(grid.dates, day, side="right")) - 1
    if j < 0 or grid.dates[j] != day:
        return None
    w0 = j - look_n + 1
    if w0 < 0:
        return None
    return w0, j


def shortfall_z(
    grid: ReturnGrid, symbols: list[str], data_date: date, p: ShortfallBrakeParams
) -> dict[str, float]:
    """Each symbol's shortfall against the index over the window, in its own standard deviations.

    Negative means the name trailed the index. A symbol is absent when it is not measurable: no
    row in the grid, fewer than ``MIN_FRAC`` of the window's sessions shared with the index, or
    a zero excess-return spread. Reads only calendar columns at or before ``data_date``.
    """
    bounds = _window(grid, data_date, p.look_n)
    if bounds is None:
        return {}
    w0, j = bounds
    mrow = grid.row.get(p.inner.market)
    if mrow is None:
        return {}
    names = [s for s in symbols if s in grid.row]
    if not names:
        return {}
    idx = np.asarray([grid.row[s] for s in names], dtype=np.int64)

    m = grid.rets[mrow, w0 : j + 1]
    r = grid.rets[idx, w0 : j + 1]
    ok = np.isfinite(r) & np.isfinite(m)[None, :]
    count = ok.sum(axis=1)
    enough = count >= max(3, math.ceil(MIN_FRAC * p.look_n))
    safe = np.where(count > 0, count, 1).astype(np.float64)

    with np.errstate(divide="ignore", invalid="ignore"):
        cum_r = np.prod(1.0 + np.where(ok, r, 0.0), axis=1) - 1.0
        cum_m = np.prod(1.0 + np.where(ok, np.broadcast_to(m, r.shape), 0.0), axis=1) - 1.0
        excess = np.where(ok, r - m[None, :], 0.0)
        mean = excess.sum(axis=1) / safe
        spread = np.where(ok, excess - mean[:, None], 0.0)
        sd_window = np.sqrt((spread * spread).sum(axis=1) / safe) * np.sqrt(safe)
        usable = enough & np.isfinite(sd_window) & (sd_window > 0.0)
        z = np.where(usable, (cum_r - cum_m) / np.where(usable, sd_window, 1.0), np.nan)

    live = usable & np.isfinite(z)
    return {names[k]: float(z[k]) for k in (int(v) for v in np.flatnonzero(live))}


def market_calm(grid: ReturnGrid, data_date: date, p: ShortfallBrakeParams) -> bool:
    """Is the index's own ``look_n``-session return not negative? True always when ``market_up`` is off.

    False whenever the answer cannot be established from bars at or before ``data_date``: the
    brake stands down rather than guessing, so an unmeasurable session is a session the variant
    behaves as its control.
    """
    if not p.market_up:
        return True
    bounds = _window(grid, data_date, p.look_n)
    if bounds is None:
        return False
    w0, j = bounds
    mrow = grid.row.get(p.inner.market)
    if mrow is None:
        return False
    m = grid.rets[mrow, w0 : j + 1]
    ok = np.isfinite(m)
    if int(ok.sum()) < max(3, math.ceil(MIN_FRAC * p.look_n)):
        return False
    with np.errstate(divide="ignore", invalid="ignore"):
        cum = float(np.prod(1.0 + np.where(ok, m, 0.0)) - 1.0)
    return math.isfinite(cum) and cum >= 0.0


def braked_names(
    grid: ReturnGrid, symbols: list[str], data_date: date, p: ShortfallBrakeParams
) -> frozenset[str]:
    """The symbols the brake acts on at ``data_date``; empty when the brake is off or stood down."""
    if p.k is None or not market_calm(grid, data_date, p):
        return frozenset()
    limit = -float(p.k)
    return frozenset(s for s, z in shortfall_z(grid, symbols, data_date, p).items() if z <= limit)


# --------------------------------------------------------------------------- the book


def _priced(
    chosen: list[FactorRow], inner: FactorParams, braked: frozenset[str], cut: Decimal
) -> tuple[Target, ...]:
    """``chosen`` at F4's weights, with each braked name cut to ``cut`` of its weight (0 = dropped).

    The weight of a dropped or trimmed name is NOT redistributed: under ``sizing="equal"``
    ``factor_weights`` gives every row ``1/top`` whatever the list length, so the freed slot is
    cash and the survivors keep the size they would have had. That is deliberate -- a brake that
    re-concentrated into the names it kept would be measuring concentration, not braking.
    """
    out: list[Target] = []
    for row, weight in zip(chosen, factor_weights(chosen, inner), strict=True):
        if weight is None:
            continue
        if row.symbol in braked:
            if cut <= ZERO:
                continue
            scaled = scale_weight(weight, cut)
            if scaled is None:
                continue
            weight = scaled
        target = target_from_close(row.symbol, row.close, weight)
        if target is not None:
            out.append(target)
    return tuple(out)


def brake_targets(
    rows: list[FactorRow],
    scores: Mapping[str, float],
    grid: ReturnGrid,
    data_date: date,
    p: ShortfallBrakeParams,
) -> tuple[Target, ...]:
    """The host book's targets with the brake applied; exactly the host's when nothing is braked.

    The fall-through to ``targets_from_scores`` is not an optimisation: it is the guarantee that
    a session on which no name is braked trades identically to the recorded control, so any
    difference between an arm and M0152's rung is a session the brake acted on and nothing else.
    """
    if p.k is None:
        return targets_from_scores(rows, scores, p.inner)
    scorable = [r for r in rows if r.symbol in scores and r.symbol not in EXCLUDED]
    ranked = sorted(scorable, key=lambda r: (-scores[r.symbol], r.symbol))
    braked = braked_names(grid, [r.symbol for r in ranked], data_date, p)
    if not braked:
        return targets_from_scores(rows, scores, p.inner)
    inner = p.inner.inner
    if p.fill:
        kept = [r for r in ranked if r.symbol not in braked][: inner.top]
        return _priced(kept, inner, frozenset(), ZERO)
    return _priced(ranked[: inner.top], inner, braked, p.cut)


class ShortfallBrakeAllocator:
    """M0007-N20-RAW's book, with each holding read against the index over the last quarter.

    Held symbols get no special treatment and the brake keeps no state: every decision session
    re-ranks, re-measures and re-decides from bars alone, so a braked name returns the moment
    its shortfall does.
    """

    id = "M0155"

    def lookback(self, params: Any) -> int:
        p = _check(params)
        # The picks need `resid_lookback` (401 bars for the host's params) and the brake needs
        # `look_n + 1` (64). The max is the honest figure and, for every variant this method
        # declares, it is exactly the host's -- so the dev window opens on the same session as
        # M0128-RAW20's and the two are comparable trade for trade.
        return max(resid_lookback(p.inner), p.look_n + 1)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return RESIDMOM.symbols(_check(params).inner)

    def holds(self, params: Any) -> tuple[str, ...]:
        _check(params)
        return ()

    def uses_members(self, params: Any) -> bool:
        _check(params)
        return True

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        p = _check(params)
        inner = p.inner
        if not trend_on(history, data_date, inner.inner):
            return ()
        rows = factor_rows(history, members, data_date, inner.inner)
        if not rows:
            return ()
        grid = build_grid(history, inner.market)
        if grid is None:
            return ()
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, inner)
        return brake_targets(rows, scores, grid, data_date, p)

    def prepare(self, history: Mapping[str, History]) -> ResidPrepared:
        return RESIDMOM.prepare(history)

    def targets_prepared(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: frozenset[str], params: Any) -> tuple[Target, ...]:
        if not isinstance(prepared, ResidPrepared):
            raise TypeError(f"prepared must be ResidPrepared, got {type(prepared).__name__}")
        p = _check(params)
        inner = p.inner
        if not trend_on(prepared.history, data_date, inner.inner):
            return ()
        rows = prepared.factor.rows_on(members, data_date, inner.inner)
        if not rows:
            return ()
        grid = prepared.grid(inner.market)
        if grid is None:
            return ()
        scores = residual_scores(grid, [r.symbol for r in rows], data_date, inner)
        return brake_targets(rows, scores, grid, data_date, p)


SHORTFALL = ShortfallBrakeAllocator()

#: The host book, imported and never rebuilt: M0007-N20-RAW's params exactly as M0128-RAW20,
#: M0139 and M0152 use them, so an arm here and a rung of the width curve differ only in the brake.
HOST = RAW20


def _v(suffix: str, params: ShortfallBrakeParams, rationale: str) -> Candidate:
    return Candidate(id=f"M0155-{suffix}", family="M0155", rules=MONTHLY_TBAND,
                     allocator=SHORTFALL, params=params, rationale=rationale, added=ADDED,
                     owner_inputs=rule_owner_inputs(MONTHLY_TBAND))


K15 = Decimal("1.5")
K20 = Decimal("2.0")
K25 = Decimal("2.5")

METHOD = Method(
    id="M0155",
    name="Let go of the one holding that is falling apart on its own, while the market is fine",
    family="stock-single-name-brake",
    source_kind="variation",
    source_ref=(
        "M0152 for the dated hole this attacks, its seven-rung paired width curve and the 2006 "
        "episode (docs/lab/survivorship/roster-width-curve-2026-10-14.csv); M0128-RAW20 (trial "
        "#388) for the unbraked twenty-name control, which is the roster's own book at real fees "
        "on the fixed tape and is quoted here rather than re-run; M0019, M0020 and M0035 for the "
        "three per-stock and per-book exits that already failed, and which this is shaped to "
        "differ from; M0109 for the shadow-reconstruction and stand-down conventions"
    ),
    parent_id="M0152",
    hypothesis=(
        "M0152 dated this account's damage for the first time and found that the SPY 200-day "
        "market gate already handles market falls well -- the dot-com collapse cost this book "
        "4-9 percent and the 2008 crisis 9 percent, its two mildest stretches in twenty years. "
        "Its two real holes are 1998, a crash too fast for a 200-day average and essentially "
        "unfixable by width (about 19-21 percent at every width from 20 to 70 names), and SPRING "
        "2006, where the market index dipped 2 percent and recovered to a new high by September "
        "while the twenty-name book lost 21.8 percent on the survivorship-check store and 16.3 "
        "on dev. 2006 is the ONLY width-sensitive episode in the window: 21.8 / 18.9 / 18.8 / "
        "16.2 / 15.1 / 14.8 / 12.9 across 20/25/30/35/45/50/70 names on the check store, nearly "
        "nine points, against 3.6 points in 1998 and none at all in the crisis years. So for a "
        "narrow book the single-holding blowup is now the LARGER of the two risks by a wide "
        "margin, and the lab has spent most of its ids on market timing and almost none on this. "
        "Width is one answer and M0152 priced it (35 names, five points of fall for no return "
        "cost on the check store). This asks whether a cheaper and more direct answer exists: a "
        "per-holding brake that lets go of a position which has fallen hard RELATIVE TO THE "
        "MARKET while the market itself is fine -- precisely the 2006 signature, and deliberately "
        "not a stop-loss, which M0020 already showed fires on the market falls the gate has "
        "handled. THE RULE, fixed before the run. On each monthly decision, for every ranked "
        "candidate, measure its compounded return over the last 63 sessions against the index's "
        "over the sessions they share, divide by the standard deviation of its own daily excess "
        "return over that window scaled by the square root of the window length, and act when "
        "that z-score is at or below minus k. A name with less than 80 percent of the window "
        "usable is never braked. Six arms, all on M0007-N20-RAW's picks verbatim at twenty names "
        "on monthly-hold-frac-gotrade-tband, the tape M0152's whole curve is measured on, so an "
        "arm here and a rung there differ in the brake and in nothing else: Z2 and Z2-HALF let "
        "the braked name go or cut it to half weight and leave the slot IN CASH; Z15-FILL, "
        "Z2-FILL and Z25-FILL remove the braked names from the ranking before the top twenty are "
        "taken, so the book still holds twenty names and stays fully invested; Z2-FILL-UP is "
        "Z2-FILL with the further condition that the index's own 63-session return is not "
        "negative. The unbraked control is NOT re-run: M0128-RAW20 (trial #388) is that book, "
        "recorded, funded identically at 10,000,000 IDR opening and 5,000,000 IDR on the 25th "
        "across 237 deposits, and a dedicated test module proves this allocator with the brake "
        "off is target-for-target identical to it rather than spending a trial to show the same "
        "thing. WHAT IS PREDICTED, in numbers, before any result. (1) THE BRAKE FIRES RARELY AND "
        "THE BOOK BARELY MOVES. Predicted trade count 1,650 to 1,900 against the control's 1,607 "
        "-- a handful of extra round trips a year, not dozens -- and a whole-window funded return "
        "within 1.0 point a year of the control's 13.68 percent on dev and 11.98 on the check "
        "store. If an arm trades more than 2,300 times it has become a short-horizon strategy "
        "wearing a brake's name and must be reported as one. (2) THE FILL ARMS CLOSE MORE OF 2006 "
        "THAN THE CASH ARMS, AT LESS COST. Predicted check-store 2006 fall: 16 to 19 percent for "
        "Z2-FILL against the control's 21.8 and the 35-name book's 16.2. (3) THE THRESHOLD CURVE "
        "IS MONOTONE AND SHALLOW. Z15-FILL should fire most and cost most, Z25-FILL least of "
        "both, with under 2 points of 2006 fall and under 0.5 of a point a year separating 1.5 "
        "from 2.5. A steep or non-monotone threshold curve means the result is a threshold "
        "accident and the verdict says so instead of naming a k. (4) THE DECISION RULE, FIXED NOW "
        "SO THE RESULT CANNOT CHOOSE IT. The brake is worth something only if it beats WIDTH, not "
        "only the control. An arm SUCCEEDS when, on the check store at twenty names, its 2006 "
        "fall is at or below 17.8 percent -- the control's 21.8 less the 4 points the idea asked "
        "for -- AND its funded return is within 1.0 point a year of the control's 11.98 percent. "
        "An arm is WIDTH IN DISGUISE when it reaches that 2006 number but sits on or outside the "
        "line M0152's seven rungs trace through (2006 fall, funded return) -- that is, when 35 "
        "names already gives the same pair -- and then the honest answer is 35 names and the "
        "verdict leads with it. An arm FAILS when it trades the fall away for more than a point a "
        "year, or when its 1998, 2000-02, 2008-09 and 2010-15 era falls get worse by more than "
        "they gain in 2006. (5) BOTH STORES OR IT DOES NOT COUNT. The dev store cannot price "
        "roughly 4 in 10 of the days companies spent in the index, and the ones it cannot price "
        "are overwhelmingly the companies that went bankrupt or were bought -- which is the exact "
        "event this brake exists to catch. Predicted dev-store 2006 falls: 14 to 16 percent for "
        "every arm against the control's 16.3, a difference too small to read. A dev-only result "
        "here is not weak evidence, it is no evidence, and the run on dev exists to record the "
        "trials and price the return cost, not to answer the question. (6) THE CLOCK IS A CEILING "
        "AND IS ACCEPTED BEFORE THE RUN. monthly-hold-frac-gotrade-tband has no resize cadence, "
        "so this brake is read once a month; the mid-month exit the idea also named is not "
        "available without leaving the curve every number here is measured against, and a feature "
        "wish is journalled for a monthly-rank weekly-resize preset on the fixed tape. "
        "PROMOTION IS NOT AVAILABLE AND IS NOT SOUGHT. This line runs through M0007, which is "
        "test-failed, so the hard gate refuses it on kin whatever it scores and the kin bar "
        "refuses the family; promotion would only be open to a brake built on a book whose "
        "ancestry is clean. Accepted before the run. Any arm that reads eligible against the dev "
        "screen is a by-product and must not be reported as a candidate or as a near miss."
    ),
    expected_failure=(
        "The likely failure, and the idea named it in advance: the brake sells into noise, fires "
        "dozens of times a year at Gotrade's real fees, and gives back more in whipsaw than one "
        "episode in twenty years was worth; or it is simply width in disguise, and the honest "
        "answer stays 35 names. Four specific shapes, written now. (1) THE BRAKE IS SHORT-TERM "
        "REVERSAL WITH THE SIGN WRONG. 'Sell what has fallen most against the market over the "
        "last quarter' is the inverse of the best-documented anomaly at this horizon: short-horizon "
        "losers bounce. If that dominates, every arm trails the control by 1 to 3 points a year "
        "with a 2006 fall barely better, and the brake is a reversal bet nobody pre-registered. "
        "This is the single most likely way the method dies and it is checked first: the 2010-15 "
        "era column, where there is no episode for the brake to catch, prices the drag alone. "
        "(2) IT IS WIDTH IN DISGUISE. Dropping a name from a twenty-name book and leaving the "
        "slot in cash is holding nineteen names, and the fill arms exist precisely so that "
        "'safer because it holds less' cannot be mistaken for 'safer because it let go of the "
        "right name'. If Z2 improves 2006 and Z2-FILL does not, the finding is about exposure, "
        "M0109 already owns that question, and this id bought nothing new. (3) ONE EPISODE IS "
        "DOING ALL THE WORK, AND IT IS THE EPISODE THE BRAKE WAS DESIGNED AGAINST. Spring 2006 is "
        "a single five-month stretch in a twenty-year window, and a rule aimed at it will improve "
        "it by construction. The result is only evidence if 1998, 2000-02, 2008-09 and 2010-15 do "
        "not get worse to pay for it, and if the dev store -- a genuinely different tape -- moves "
        "in the same direction even though it cannot see the episode. If 2006 improves and "
        "everything else degrades, the honest reading is overfitting to one spring and the verdict "
        "must lead with that rather than with the headline. (4) THE MONTHLY CLOCK MAY BE TOO SLOW "
        "TO MATTER. A name can collapse and be gone inside one month, and this brake reads once a "
        "month. If the braked names turn out to be ones the ranking would have dropped at the same "
        "session anyway, the brake changes nothing and the correct report is a null result with "
        "the overlap counted, not a thin improvement dressed up. (5) THE CHECK STORE IS A "
        "CROSS-CHECK, NOT TRUTH. It adds most of the members the dev store cannot price and not "
        "all of them, and real collapses were kept while data errors were cleaned, which is a "
        "judgement call. A 4-point claim that rests on half a point of margin is not a claim, and "
        "the verdict says so rather than rounding in its own favour. (6) DEPOSITS SOFTEN EVERY "
        "FALL IN THIS FILE ALIKE, so every figure lines up against M0128's, M0139's and M0152's, "
        "which are funded identically, and against no unfunded trial anywhere."
    ),
    candidates=(
        _v("Z2", ShortfallBrakeParams(HOST, k=K20),
           "Let a holding go once it is two standard deviations behind the index over a quarter, "
           "and leave its slot in cash"),
        _v("Z2-FILL", ShortfallBrakeParams(HOST, k=K20, fill=True),
           "The same trigger with the slot refilled from the ranking: twenty names and fully "
           "invested, so only the swap is being priced"),
        _v("Z15-FILL", ShortfallBrakeParams(HOST, k=K15, fill=True),
           "The sensitive rung of the threshold curve: one and a half standard deviations, "
           "refilled"),
        _v("Z25-FILL", ShortfallBrakeParams(HOST, k=K25, fill=True),
           "The patient rung of the threshold curve: two and a half standard deviations, "
           "refilled"),
        _v("Z2-HALF", ShortfallBrakeParams(HOST, k=K20, cut=Decimal("0.5")),
           "A half position rather than an exit: prices the gentler shape of the same trigger"),
        _v("Z2-FILL-UP", ShortfallBrakeParams(HOST, k=K20, fill=True, market_up=True),
           "Z2-FILL that acts only while the index's own quarter is not negative: insists the "
           "market is really fine, not merely above a slow average"),
    ),
    seen_keys=(
        "concept:per-holding-relative-shortfall-brake",
        "concept:single-name-exit-gated-on-a-rising-market",
        "concept:brake-reading-the-window-the-momentum-skip-hides",
    ),
)
```

**Impact:** a new allocator id `M0155`, unique across the lab and the P7a registry
(`test_allocator_ids_are_unique_across_methods`). No existing symbol changes, so no recorded
`config_digest` moves. `test_lab_methods.py` picks the file up automatically through `discover()`
and gives it, for free: the purity check, the `allocatorkit` contract (valid targets, the P4
identity, no look-ahead, the declared lookback) and a smoke window per candidate — 13 new cases,
all verified green while this plan was written.

---
### Step 2: write the test module

**File:** `engine/tests/test_lab_m0155_brake.py:1` (new file)
**Change:** The three claims the shared lab tests cannot make: that the brake off **is** the host
book target for target (which is what replaces a control arm), that the trigger is relative rather
than absolute (M0019's failure), and that the two shapes do different things.

The refill check deliberately runs on a **four-name** book: the method's own arms hold twenty and
the smoke market serves eight members, so at the configured width `fill=True` and `fill=False`
give the same book and the refill is unobservable. The fall it injects is confined to the 21
sessions the 12-1 ranking skips, so the ranking does not move and the only thing that can change
the book is the brake — which is also the mechanism the method claims makes a 63-session window
non-redundant with a 12-1 ranking.

**Code:** the complete file.

```python
"""M0155's single-name brake: the three claims the method file makes about it.

``test_lab_methods`` already drives every lab allocator through ``allocatorkit`` (valid targets,
the P4 identity, no look-ahead, the declared lookback) and runs every candidate on a smoke
window. These are the checks that are specific to this brake and that the generic kit cannot
make:

1. **With the brake off this allocator IS the host book**, target for target, on every probe.
   That is why M0155 does not spend a trial on a control arm: M0128-RAW20 (trial #388) is the
   unbraked twenty-name book, recorded, and this test is what earns the right to quote it.
2. **The trigger is relative, not absolute.** A name that collapses on its own is braked; the
   same collapse happening to the whole market, index included, is not. This is the exact
   failure M0019's protective stop died of and the one thing the method claims to have fixed.
3. **The two shapes do different things.** ``fill=False`` leaves the braked name's slot in cash
   and the survivors at their original weight; ``fill=True`` refills it from the ranking, so the
   book still holds ``top`` names and still weighs 1.

A dedicated module rather than more cases inside the shared lab tests, because the fixtures here
are hand-built falls and the smoke market is deliberately not.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import numpy as np
import pytest
from labkit import MEMBER_STOCKS, smoke_market

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END
from seer_engine.lab.methods.m0007_residual_momentum import RESIDMOM, TREND, build_grid
from seer_engine.lab.methods.m0155_single_name_shortfall_brake import (
    HOST,
    SHORTFALL,
    ShortfallBrakeParams,
    braked_names,
    market_calm,
    shortfall_z,
)
from seer_engine.strategies.allocator import scale_weight
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import FactorParams

PROBES = dates.sessions(date(2015, 1, 2), DEV_END)[::20]
MEMBERS = frozenset(MEMBER_STOCKS)
OFF = ShortfallBrakeParams(HOST)
K2 = Decimal("2.0")


@pytest.fixture(scope="module")
def market():
    return smoke_market(("SPY",))


def test_the_brake_off_is_the_host_book_target_for_target(market):
    """M0155 with k None equals M0007-N20-RAW exactly: the control M0128-RAW20 recorded."""
    prepared_host = RESIDMOM.prepare(market.history)
    prepared_brake = SHORTFALL.prepare(market.history)
    seen = 0
    for session in PROBES:
        d = dates.prev_session(session)
        host = RESIDMOM.targets(market.history, MEMBERS, d, frozenset(), HOST)
        brake = SHORTFALL.targets(market.history, MEMBERS, d, frozenset(), OFF)
        assert brake == host, d
        host_p = RESIDMOM.targets_prepared(prepared_host, MEMBERS, d, frozenset(), HOST)
        brake_p = SHORTFALL.targets_prepared(prepared_brake, MEMBERS, d, frozenset(), OFF)
        assert brake_p == host_p == host, d
        seen += len(host)
    assert seen > 0, "every probe was empty, so the comparison proved nothing"


def test_the_brake_off_declares_the_hosts_lookback(market):
    assert SHORTFALL.lookback(OFF) == RESIDMOM.lookback(HOST)
    assert SHORTFALL.symbols(OFF) == RESIDMOM.symbols(HOST)
    assert SHORTFALL.holds(OFF) == ()
    assert SHORTFALL.uses_members(OFF) is True


def _falling(history: dict[str, History], symbols: tuple[str, ...], d: date, drop: float,
             n: int = 63) -> dict[str, History]:
    """``history`` with the last ``n`` sessions through ``d`` of each named symbol ramped to ``drop``.

    ``n = 21`` confines the fall to the sessions the host's 12-1 ranking SKIPS, so the ranking is
    unmoved and any change in the book is the brake's doing and nothing else. ``n = 63`` fills
    the whole brake window and moves the ranking too, which is the realistic case.
    """
    out = dict(history)
    for symbol in symbols:
        h = out[symbol]
        end = int(np.searchsorted(h.dates, np.datetime64(d, "D"), side="right"))
        close = h.close.copy()
        close[end - n : end] = close[end - n : end] * np.linspace(1.0, drop, n)
        out[symbol] = History(h.symbol, h.dates, h.open, h.high, h.low, close, h.volume)
    return out


def test_a_name_that_collapses_alone_is_braked(market):
    d = dates.prev_session(PROBES[-1])
    history = _falling(dict(market.history), ("AAA",), d, 0.45)
    grid = build_grid(history, "SPY")
    z = shortfall_z(grid, list(MEMBER_STOCKS), d, ShortfallBrakeParams(HOST, k=K2))
    assert z["AAA"] < -2.0, z["AAA"]
    assert braked_names(grid, list(MEMBER_STOCKS), d, ShortfallBrakeParams(HOST, k=K2)) == {"AAA"}


def test_a_fall_the_whole_market_shares_is_not_braked(market):
    """The same collapse, happening to every name AND to the index: nothing is braked."""
    d = dates.prev_session(PROBES[-1])
    history = _falling(dict(market.history), (*MEMBER_STOCKS, "SPY"), d, 0.45)
    grid = build_grid(history, "SPY")
    p = ShortfallBrakeParams(HOST, k=K2)
    assert braked_names(grid, list(MEMBER_STOCKS), d, p) == frozenset()


def test_market_up_stands_down_when_the_index_quarter_is_negative(market):
    d = dates.prev_session(PROBES[-1])
    history = _falling(dict(market.history), ("AAA", "SPY"), d, 0.45)
    grid = build_grid(history, "SPY")
    assert market_calm(grid, d, ShortfallBrakeParams(HOST, k=K2)) is True
    up = ShortfallBrakeParams(HOST, k=K2, fill=True, market_up=True)
    assert market_calm(grid, d, up) is False
    assert braked_names(grid, list(MEMBER_STOCKS), d, up) == frozenset()


def test_a_braked_name_leaves_its_slot_in_cash_and_the_survivors_untouched():
    """``fill=False``: the book holds one fewer name and every survivor keeps its original weight."""
    market = smoke_market(("SPY",))
    d = dates.prev_session(PROBES[-1])
    history = _falling(dict(market.history), ("AAA",), d, 0.45)
    base = SHORTFALL.targets(history, MEMBERS, d, frozenset(), OFF)
    assert any(t.symbol == "AAA" for t in base), "nothing to brake on this session"
    cash = SHORTFALL.targets(history, MEMBERS, d, frozenset(), ShortfallBrakeParams(HOST, k=K2))
    assert "AAA" not in {t.symbol for t in cash}
    assert len(cash) == len(base) - 1
    # the survivors are untouched: a brake must not re-concentrate into the names it kept
    assert {(t.symbol, t.weight) for t in cash} == {(t.symbol, t.weight) for t in base if t.symbol != "AAA"}


def test_a_half_cut_keeps_the_name_at_a_smaller_weight():
    market = smoke_market(("SPY",))
    d = dates.prev_session(PROBES[-1])
    history = _falling(dict(market.history), ("AAA",), d, 0.45)
    base = SHORTFALL.targets(history, MEMBERS, d, frozenset(), OFF)
    assert any(t.symbol == "AAA" for t in base), "nothing to brake on this session"
    half = SHORTFALL.targets(history, MEMBERS, d, frozenset(),
                             ShortfallBrakeParams(HOST, k=K2, cut=Decimal("0.5")))
    assert len(half) == len(base)
    was = next(t for t in base if t.symbol == "AAA").weight
    now = next(t for t in half if t.symbol == "AAA").weight
    assert now == scale_weight(was, Decimal("0.5"))


def test_fill_refills_the_slot_from_the_ranking():
    """``fill=True``: the book still holds ``top`` names, so only the swap is being priced.

    The method's own arms hold twenty names and the smoke market serves eight, so the refill
    cannot be seen at the configured width -- with fewer eligible names than slots ``fill=True``
    and ``fill=False`` give the same book. A four-name book on the same bars leaves four spare
    ranked names and makes the difference observable.
    """
    market = smoke_market(("SPY",))
    d = dates.prev_session(PROBES[-1])
    narrow = replace(HOST, inner=FactorParams(rank="momentum", top=4, trend=TREND))
    base = SHORTFALL.targets(market.history, MEMBERS, d, frozenset(), ShortfallBrakeParams(narrow))
    assert len(base) == 4
    worst = base[-1].symbol
    # The fall is confined to the 21 sessions the 12-1 ranking skips, so the ranking does not
    # move and the only thing that can change the book is the brake.
    history = _falling(dict(market.history), (worst,), d, 0.45, n=21)
    unbraked = SHORTFALL.targets(history, MEMBERS, d, frozenset(), ShortfallBrakeParams(narrow))
    assert [t.symbol for t in unbraked] == [t.symbol for t in base], "the ranking moved"
    cash = SHORTFALL.targets(history, MEMBERS, d, frozenset(), ShortfallBrakeParams(narrow, k=K2))
    full = SHORTFALL.targets(history, MEMBERS, d, frozenset(),
                             ShortfallBrakeParams(narrow, k=K2, fill=True))
    assert worst not in {t.symbol for t in cash}
    assert worst not in {t.symbol for t in full}
    assert len(cash) == 3, "the braked slot is cash"
    assert len(full) == 4, "the braked slot is refilled from the ranking"
    assert {t.weight for t in full} == {t.weight for t in base}
    assert set(t.symbol for t in full) - set(t.symbol for t in base), "nothing new was bought"


def test_a_contradictory_configuration_is_refused():
    with pytest.raises(ValueError, match="cut must be 0"):
        ShortfallBrakeParams(HOST, k=K2, fill=True, cut=Decimal("0.5"))
    with pytest.raises(ValueError, match="exactly one spelling"):
        ShortfallBrakeParams(HOST, fill=True)
    with pytest.raises(ValueError, match="k must be > 0"):
        ShortfallBrakeParams(HOST, k=Decimal("0"))
```

**Impact:** 9 new tests, all verified green while this plan was written. No production code is
touched, so nothing else in the suite can move.

---

### Step 3: verify green, then commit and push — this commit IS the pre-registration

**File:** none — commands
**Change:** The tree must be green before the commit, because the commit is the pre-registration
and the file cannot be edited afterwards.

**Code:**
```bash
cd /home/miftah/seer
engine/.venv/bin/ruff check engine

# DB tests need Postgres and CI fails if they skip.
docker start seer-pg 2>/dev/null || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
PYTHONPATH=engine/src engine/.venv/bin/python -m pytest engine/tests -q

# the new work on its own, for a fast read
PYTHONPATH=engine/src engine/.venv/bin/python -m pytest \
  engine/tests/test_lab_m0155_brake.py engine/tests/test_lab_methods.py -q

# explicit pathspec: this checkout is shared with phases 1, 2, 4 and 5
git add engine/src/seer_engine/lab/methods/m0155_single_name_shortfall_brake.py \
        engine/tests/test_lab_m0155_brake.py
git commit -m "lab: M0155 pre-registered — let go of the one holding falling apart while the market is fine

Six arms on M0007-N20-RAW's picks at twenty names on the fixed tape, so each one
and a rung of M0152's width curve differ in the brake and in nothing else. The
trigger is a holding's 63-session return against the index's, in standard
deviations of its own daily excess return: Z2 and Z2-HALF let the name go or cut
it to half weight and leave the slot in cash, Z15-FILL/Z2-FILL/Z25-FILL refill the
slot from the ranking so the book stays twenty names and fully invested, and
Z2-FILL-UP additionally insists the index's own quarter is not negative.

Not a stop-loss: M0019 and M0020 showed an absolute stop fires on the market falls
the 200-day gate already handles, and M0035 showed a book-level shortfall switch
was off throughout the fall it was built to cap. This is relative, per holding, and
can only act on a session the gate has judged calm. No control arm is run:
M0128-RAW20 (trial #388) is that book, recorded, and a dedicated test module proves
this allocator with the brake off is target-for-target identical to it.

Promotion is refused on kin and is not sought.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

git push origin main
```

If the push is rejected, **do not `git pull --rebase`** — it replays a stale `lab.sqlite` over
whatever Phases 1, 4 and 5 have written (`seer-rebase-replays-stale-lab-sqlite`). Fetch, check
whether the incoming commits touch any `lab/` file, and if they do not use a mixed reset plus a
fast-forward merge:

```bash
git fetch origin main
git log --oneline --name-only HEAD..origin/main | grep -E '^(lab/|web/data/lab.json)' || echo "no lab files incoming"
git reset --mixed HEAD~1                       # keeps the working tree; stages nothing
git merge --ff-only origin/main
git add engine/src/seer_engine/lab/methods/m0155_single_name_shortfall_brake.py \
        engine/tests/test_lab_m0155_brake.py
git commit -m "lab: M0155 pre-registered — …"   # the same message
git push origin main
```

**Impact:** `registry_problem` now passes for this file. `lab run M0155` becomes possible, and the
file is frozen against the sha this commit gives it the moment the run records `source_sha`.

---

### Step 4: run the six arms on the dev window

**File:** none — commands. Writes `lab/lab.sqlite`.
**Change:** Six dev trials under `M0155`, funded on the owner's plan at `INITIAL_IDR`.
`run_method` moves the method `idea` → `registered` and then to `dev-eligible` or `rejected`, and
records one `method_folds` row.

**Take the lab write lock before the run — this opens this phase's single hold**, which runs
through Step 9's push and covers Step 5's `lab survivorship` and Step 8's `lab note` and
`lab insight` as well. `lab run` leaves the shared binary `lab/lab.sqlite` dirty for its whole
duration, so it is inside the hold and the four lab phases' runs queue. The lock's exact commands,
its preconditions and its release are in Step 9 and in the plan index's invariant 7.

**Code:**
```bash
cd /home/miftah/seer

# open the hold (full protocol and preconditions: Step 9)
exec 9>/home/miftah/seer/.git/seer-lab.lock
flock -w 21600 9 || { echo "lab lock still held after 6h -- find out who has it; do NOT force"; exit 1; }
echo "phase-3 pid $$ $(date -Is)" >&9
git fetch origin && git merge --ff-only origin/main
git diff --quiet HEAD -- lab/lab.sqlite web/data/lab.json || { echo "pair dirty, nobody held the lock -- STOP"; exit 1; }

export SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research   # the dev store; NEVER .research-test
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine -v lab run M0155 2>&1 \
  | tee /tmp/claude-1000/-home-miftah-seer/9564e44d-59f1-41ce-befb-0745f6332dfc/scratchpad/m0155-run.log
```

Expect tens of minutes: six twenty-year backtests over the whole index, each re-running the host's
market-model OLS plus one extra 63-column slice per decision session. Exit code 2 means the lab's
rules refused the request — read the message, do not work around it. The two refusals to expect
are an uncommitted file (go back to Step 3) and a repeated configuration (impossible here: no
recorded trial uses allocator id `M0155`).

**Impact:** the lab's N moves by one method. The test-window look count does **not** move.

---

### Step 5: the free whole-window read on the check store

**File:** none — commands. Appends one observation to `lab/lab.sqlite`.
**Change:** `lab survivorship` re-runs every recorded `M0155` variant at its recorded capital and
funding, once on the dev store and once on the survivorship-check store, never holding both in
memory. It records no trial, no moments, no funding and no status, so N and the look count cannot
move. It also prints the dev **re-run** beside each recorded trial: **an arm whose dev re-run does
not reproduce its recorded trial has a meaningless side-by-side and must be dropped from the
report rather than quoted.**

**Code:**
```bash
cd /home/miftah/seer
SCRATCH=/tmp/claude-1000/-home-miftah-seer/9564e44d-59f1-41ce-befb-0745f6332dfc/scratchpad
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine -v lab survivorship M0155 \
  --store engine/.research \
  --sv-store engine/.research-sv \
  --csv "$SCRATCH/m0155-survivorship-2026-10-14.csv" 2>&1 | tee "$SCRATCH/m0155-survivorship.log"
```

`--sv-store` is refused unless the manifest reads `purpose: survivorship-check`, and
`load_checked` refuses a test-window store on its own — the look count is safe by construction.
The `era_edge` column of that CSV is the 2009–2015 lead over the deposit-matched benchmark; it is
quoted into the report in Step 7 and is **not** recomputed by the era script, which has no
benchmark of its own.

**Impact:** one plain-words `insights` observation on `M0155`. Nothing else.

---

### Step 6: the era grid — the two columns `lab survivorship` does not give

**File:** scratchpad script + `docs/lab/survivorship/single-name-brake-eras-2026-10-14.csv` (new)
**Change:** `lab survivorship` gives the whole-window pair. It does not give **when** each worst
fall happened or how deep the fall was inside each era, and those are the two columns this
method's question turns on. M0152 computed them by hand for the width curve; this is that
computation written down.

**It validates itself before it reports.** The first candidate it runs is `M0128-RAW20`, and its
era numbers must land on the ones M0152 committed (21.82% in 2006 and 21.57% in 1998 on the check
store, 20.03% and 16.25% on dev). If they do not, the era windows or the de-funding here are not
M0152's, nothing else in the grid is comparable to the width curve, and the script exits non-zero
rather than printing a grid that looks right. It also cross-checks its own de-funded daily fall
against the run's `metrics.max_drawdown` on every row.

The script is **not committed** — it is a one-off measurement, and the phase index gives this
phase its method file and its dated outputs, not a new engine module. Write it to the scratchpad.

**Code:** the complete script, at
`/tmp/claude-1000/-home-miftah-seer/9564e44d-59f1-41ce-befb-0745f6332dfc/scratchpad/m0155_eras.py`.

```python
"""M0155's arms and the unbraked control, read era by era on both price histories.

``lab survivorship M0155`` gives the whole-window pair -- fall, funded return, trades, the
2009-2015 edge and the walk-forward record -- and journals a plain-words observation. It does
not give the two columns this method's question actually turns on: **when** each worst fall
happened, and how deep the fall was inside each era. M0152 computed those by hand for the width
curve (``docs/lab/survivorship/roster-width-curve-2026-10-14.csv``); this script is that
computation, written down, so the brake's point can be plotted on the same axes as the seven
widths.

**It validates itself before it reports.** The first candidate it runs is ``M0128-RAW20`` -- the
recorded, unbraked twenty-name control -- and its era numbers must land on the ones M0152
committed (21.82% in 2006 and 21.57% in 1998 on the check store). If they do not, the era
windows or the de-funding here are not M0152's and nothing else in the output is comparable to
the width curve; the script says so and exits non-zero rather than printing a grid that looks
right.

**It records nothing.** No trial, no moments, no funding, no status, no insight. It opens the dev
store and the survivorship-check store one at a time, never both, exactly as
``lab survivorship`` does, and it refuses a test-window store through the same ``load_checked``.

Run it from the repository root with the engine venv::

    engine/.venv/bin/python docs/…/m0155_eras.py --out docs/lab/survivorship/single-name-brake-eras-2026-10-14.csv
"""

from __future__ import annotations

import argparse
import csv
import gc
import math
import sys
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.dev import Candidate, DevRow
from seer_engine.backtest.metrics import external_cashflows, flow_map
from seer_engine.lab import survivorship_check as sc
from seer_engine.lab.method import discover
from seer_engine.lab.runner import INITIAL_IDR
from seer_engine.sim.contributions import OWNER_MONTHLY

#: The eras M0152's width curve uses, as calendar spans. The 2010-15 span ends with the dev
#: window. Changing one of these makes this file's rows incomparable with the width curve's, so
#: the control's reproduction check below is what keeps them honest.
ERAS: tuple[tuple[str, date, date], ...] = (
    ("era_1998", date(1998, 1, 1), date(1998, 12, 31)),
    ("era_2000_02", date(2000, 1, 1), date(2002, 12, 31)),
    ("era_2006", date(2006, 1, 1), date(2006, 12, 31)),
    ("era_2008_09", date(2008, 1, 1), date(2009, 12, 31)),
    ("era_2010_15", date(2010, 1, 1), date(2015, 12, 31)),
)

#: What M0152 recorded for the control on each store, to four decimals: (store, column, value).
#: Anything here that does not reproduce means this script is not measuring what that file did.
CONTROL = "M0128-RAW20"
CONTROL_EXPECTED: Mapping[tuple[str, str], float] = {
    ("dev", "max_drawdown_monthend"): 0.200263,
    ("dev", "era_2006"): 0.162517,
    ("dev", "era_1998"): 0.200263,
    ("check", "max_drawdown_monthend"): 0.218194,
    ("check", "era_2006"): 0.218194,
    ("check", "era_1998"): 0.215678,
    ("check", "era_2008_09"): 0.090762,
}
TOL = 5e-5

HEADER: tuple[str, ...] = (
    "names", "candidate_id", "store", "max_drawdown_daily", "max_drawdown_monthend",
    "mdd_peak_month", "mdd_trough_month", "funded_yearly", "spy_yearly", "mar_funded", "trades",
    *(name for name, _, _ in ERAS),
)


def wealth_index(snaps: Sequence[tuple[date, float]],
                 cashflows: Sequence[tuple[date, float]]) -> list[tuple[date, float]]:
    """The de-funded curve: what one unchanging dollar would have traced through this book.

    The same construction ``backtest.metrics.strategy_metrics`` uses for a funded run's drawdown
    -- each session's growth taken against the previous equity PLUS whatever was deposited that
    morning -- so a 5,000,000 IDR top-up neither lifts the peak nor refills the trough.
    """
    flows = flow_map(cashflows)
    out: list[tuple[date, float]] = [(snaps[0][0], 1.0)]
    index = 1.0
    for (_, prev), (day, cur) in zip(snaps, snaps[1:], strict=False):
        base = prev + flows.get(day, 0.0)
        if base > 0.0:
            index *= cur / base
        out.append((day, index))
    return out


def month_ends(curve: Sequence[tuple[date, float]]) -> list[tuple[date, float]]:
    """The last value of each calendar month, ascending (M0152 read the era falls month-end)."""
    last: dict[tuple[int, int], tuple[date, float]] = {}
    for day, value in curve:
        last[(day.year, day.month)] = (day, value)
    return [last[key] for key in sorted(last)]


def worst_fall(curve: Sequence[tuple[date, float]], lo: date | None = None,
               hi: date | None = None) -> tuple[float, date | None, date | None]:
    """``(fall, peak date, trough date)`` -- the deepest peak-to-trough inside ``[lo, hi]``.

    The peak is taken inside the span too, so an era column answers "how far did it fall during
    this stretch", not "how far below an older high did it get".
    """
    peak = -math.inf
    peak_day: date | None = None
    fall, at_peak, at_trough = 0.0, None, None
    for day, value in curve:
        if (lo is not None and day < lo) or (hi is not None and day > hi):
            continue
        if value > peak:
            peak, peak_day = value, day
        if peak > 0.0:
            drop = (peak - value) / peak
            if drop > fall:
                fall, at_peak, at_trough = drop, peak_day, day
    return fall, at_peak, at_trough


def _month(day: date | None) -> str:
    return "" if day is None else f"{day.year:04d}-{day.month:02d}"


def slots(params: object) -> int | None:
    """How many names the candidate holds: walk ``.inner`` down to the screen's ``top``.

    The control's params are ``ResidParams`` and this method's wrap them one layer deeper, so the
    walk is what lets one row shape carry both without the script knowing either type.
    """
    seen = 0
    while params is not None and seen < 5:
        top = getattr(params, "top", None)
        if isinstance(top, int) and not isinstance(top, bool):
            return top
        params = getattr(params, "inner", None)
        seen += 1
    return None


def row_for(label: str, row: DevRow, result: object) -> dict[str, object]:
    """One CSV row from one finished run."""
    snaps = [(s.date, float(s.equity_usd)) for s in result.snapshots]
    curve = wealth_index(snaps, external_cashflows(result))
    monthly = month_ends(curve)
    daily_fall, _, _ = worst_fall(curve)
    fall, peak_day, trough_day = worst_fall(monthly)
    metrics = row.stats.metrics
    yearly = metrics.mwr
    out: dict[str, object] = {
        "names": slots(row.candidate.params),
        "candidate_id": row.candidate.id,
        "store": label,
        "max_drawdown_daily": daily_fall,
        "max_drawdown_monthend": fall,
        "mdd_peak_month": _month(peak_day),
        "mdd_trough_month": _month(trough_day),
        "funded_yearly": yearly,
        "spy_yearly": row.spy_tr.mwr,
        "mar_funded": None if yearly is None or daily_fall <= 0 else yearly / daily_fall,
        "trades": metrics.trades,
    }
    for name, lo, hi in ERAS:
        out[name], _, _ = worst_fall(monthly, lo, hi)
    # The lab's own de-funded daily drawdown, rebuilt independently above: they must agree, or
    # this script's curve is not the curve the trial was judged on.
    if metrics.max_drawdown is not None and abs(metrics.max_drawdown - daily_fall) > TOL:
        raise SystemExit(
            f"{row.candidate.id} on {label}: this script's daily fall {daily_fall:.6f} does not "
            f"match the run's own {metrics.max_drawdown:.6f}"
        )
    return out


def measure(candidates: Sequence[Candidate], store_dir: Path, *, survivorship: bool,
            label: str) -> list[dict[str, object]]:
    """Run every candidate on one store and free it before returning."""
    data = sc.load_checked(store_dir, survivorship=survivorship)
    rows: list[dict[str, object]] = []
    try:
        def on_result(_i: int, result: object, row: DevRow) -> None:
            out = row_for(label, row, result)
            rows.append(out)
            print(f"[{label}] {row.candidate.id}: fall {out['max_drawdown_daily']:.4f} daily / "
                  f"{out['max_drawdown_monthend']:.4f} month-end "
                  f"({out['mdd_peak_month']} to {out['mdd_trough_month']}), "
                  f"2006 {out['era_2006']:.4f}, yearly {out['funded_yearly']:.4f}, "
                  f"trades {out['trades']}", flush=True)

        dev.run_registry(
            data.market, data.dividends, data.spy_dividends, tuple(candidates),
            on_result=on_result, contributions=OWNER_MONTHLY, initial_idr=INITIAL_IDR,
        )
    finally:
        del data
        gc.collect()
    return rows


def check_control(rows: Sequence[Mapping[str, object]]) -> list[str]:
    """Every control column that did not reproduce M0152's committed number."""
    bad: list[str] = []
    for (store, column), expected in sorted(CONTROL_EXPECTED.items()):
        hit = [r for r in rows if r["candidate_id"] == CONTROL and r["store"] == store]
        if not hit:
            bad.append(f"{store}/{column}: the control did not run")
            continue
        got = float(hit[0][column])
        if abs(got - expected) > TOL:
            bad.append(f"{store}/{column}: got {got:.6f}, M0152 recorded {expected:.6f}")
    return bad


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--store", type=Path, default=research.STORE_DIR)
    ap.add_argument("--sv-store", type=Path, default=research.SV_STORE_DIR)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    methods = discover()
    control = next(c for c in methods["M0128"][0].all_candidates() if c.id == CONTROL)
    arms = list(methods["M0155"][0].all_candidates())
    candidates = [control, *arms]
    print(f"{len(candidates)} candidates: {', '.join(c.id for c in candidates)}", flush=True)

    rows = measure(candidates, args.store, survivorship=False, label="dev")
    rows += measure(candidates, args.sv_store, survivorship=True, label="check")

    bad = check_control(rows)
    if bad:
        print("\nThe control did not reproduce M0152's era numbers, so nothing here is "
              "comparable to the width curve:", file=sys.stderr)
        for line in bad:
            print(f"  {line}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(HEADER)
        for row in sorted(rows, key=lambda r: (str(r["candidate_id"]), str(r["store"]))):
            writer.writerow(["" if row[k] is None else
                             (repr(row[k]) if isinstance(row[k], float) else row[k])
                             for k in HEADER])
    print(f"\nwrote {args.out} ({len(rows)} rows); the control reproduced M0152's era numbers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run it:

```bash
cd /home/miftah/seer
SCRATCH=/tmp/claude-1000/-home-miftah-seer/9564e44d-59f1-41ce-befb-0745f6332dfc/scratchpad
PYTHONPATH=engine/src engine/.venv/bin/python "$SCRATCH/m0155_eras.py" \
  --store engine/.research \
  --sv-store engine/.research-sv \
  --out docs/lab/survivorship/single-name-brake-eras-2026-10-14.csv 2>&1 \
  | tee "$SCRATCH/m0155-eras.log"
```

**Impact:** one new dated CSV under `docs/lab/survivorship/`. **`grid.csv` is not touched** —
`survivorship_record.GRID_PATH` points hard-gate D16 at that exact file, and appending would
change which promotions the gate refuses as a side effect of a research run.

---
### Step 7: read the result against the pre-registered rule, and write the report

**File:** `docs/lab/survivorship/single-name-brake-2026-10-14.md:1` (new)
**Change:** The decision rule was fixed in the hypothesis before the run and the result does not
get to choose it. Apply it in this order and let the answer fall out.

**(a) Reproduction first.** Any arm whose dev re-run in Step 5 did not land on its recorded trial
is dropped from the report, not quoted.

**(b) The success test, on the check store at twenty names.**

| test | threshold | source |
|---|---|---|
| the 2006 episode shrinks by 4 points or more | `era_2006` ≤ **17.8%** | control 21.82% − 4.0 |
| and does not cost more than a point a year | `funded_yearly` ≥ **10.98%/yr** | control 11.98% − 1.0 |

**(c) The width-in-disguise test, which is the one that decides whether this id bought anything.**
Plot each arm as a point `(era_2006, funded_yearly)` on the check store against the seven recorded
widths — 20/25/30/35/45/50/70 at 2006 falls of 21.8/18.9/18.8/16.2/15.1/14.8/12.9 and returns of
11.98/11.85/12.20/12.11/11.84/11.89/10.88. An arm earns its id only if it sits **inside** that
line: a gentler 2006 than thirty-five names at a return no worse. An arm that lands on the line
is width in disguise, **the honest answer stays 35 names, and the verdict leads with that.**

**(d) The exposure test.** If `Z2` improves 2006 and `Z2-FILL` does not, the finding is about
holding less, not about letting go of the right name. M0109 already owns that question and this id
bought nothing new. Say so plainly.

**(e) The overfitting test.** 2006 is one five-month stretch in twenty years and a rule aimed at it
improves it by construction. Read `era_1998`, `era_2000_02`, `era_2008_09` and `era_2010_15`. If
2006 improves and the others degrade to pay for it, the honest reading is overfitting to one
spring and **the verdict leads with that**, not with the headline. `era_2010_15` is the cleanest
read of the drag alone: there is no episode there for the brake to catch.

**(f) The reversal test.** "Sell what has fallen most against the market over a quarter" is the
inverse of the best-documented anomaly at this horizon. If every arm trails the control by 1–3
pts/yr with 2006 barely moved, the brake is an unwitting reversal bet and must be reported as one.

**(g) The churn test.** Trade counts against the control's 1,607 (dev) / 1,640 (check). Over 2,300
and the arm has become a short-horizon strategy wearing a brake's name.

**(h) The threshold test.** `Z15-FILL` / `Z2-FILL` / `Z25-FILL` should be monotone and shallow. A
steep or non-monotone threshold curve means the result is a threshold accident, and the verdict
says so instead of naming a `k`.

Write the report in the shape of `docs/lab/survivorship/roster-width-curve-2026-10-14.md`: a
"report only" banner, why the file sits beside `grid.csv` rather than inside it, the paired table,
the era table beside the width curve's, and a Limits section that carries (e), (f), the monthly
clock and the fact that the check store is a cross-check and not truth.

**Code:**
```bash
cd /home/miftah/seer
git add docs/lab/survivorship/single-name-brake-eras-2026-10-14.csv \
        docs/lab/survivorship/single-name-brake-2026-10-14.md
git commit -m "lab: M0155 — the brake's point plotted on the width curve, on both price histories

Six arms of the single-name shortfall brake on M0007-N20-RAW at twenty names,
measured era by era on the dev store and the survivorship-check store, against
M0152's seven recorded widths. The control M0128-RAW20 reproduces its committed
era numbers, which is what makes the two files one curve.

grid.csv is untouched: hard-gate D16 reads that exact file.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push origin main
```

**Impact:** two new dated docs. No lab row yet.

---

### Step 8: the verdict, the journalled insight and the feature wish

**File:** none — commands. Writes `lab/lab.sqlite`.
**Change:** `lab note M0155 --file <path> --verdict "…"` appends the file's whole text to the
analysis (append-only; it may be added to, never rewritten) and sets the verdict. `--file` and/or
`--verdict` — there is no `--analysis` flag. **Plain language only: the owner reads it. No ids, no digests, no code.**
Lead with whichever of (c), (d), (e) or (f) the result actually supports — if the answer is "the
honest answer is still thirty-five names", that is the first sentence.

**Code:**
```bash
cd /home/miftah/seer
SCRATCH=/tmp/claude-1000/-home-miftah-seer/9564e44d-59f1-41ce-befb-0745f6332dfc/scratchpad

# `lab note` takes --file (a path whose whole text is APPENDED to the analysis) and --verdict.
# There is no --analysis flag; write the reading to a file first.
cat > "$SCRATCH/m0155-analysis.txt" <<'EOF'
<the full reading: the paired table, the era table, each of tests (a) to (h) answered
with its number, and what the brake cost in the years where there was nothing to catch>
EOF
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab note M0155 \
  --file "$SCRATCH/m0155-analysis.txt" \
  --verdict "<one or two sentences, plain language, leading with the strongest true finding>"

# The clock ceiling, journalled as a wish rather than left in a docstring.
# --kind must be one of store.INSIGHT_KINDS: observation, hypothesis, data-wish,
# feature-wish, risk, synthesis.
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab insight \
  --kind "feature-wish" \
  --method M0155 \
  --title "A monthly-rank, weekly-resize preset on the fixed tape" \
  --body "A brake that reads one holding at a time can only act as often as the book is \
re-read, and on the tape every width result is measured on that is once a month. The faster \
preset that exists measures its rebalance band against the whole account, a band that has been \
measured as barely firing, so a result on it would not line up with anything. A preset that \
re-reads weekly on the fixed band would let a per-holding rule be priced at the speed it was \
meant to run."
```

**Impact:** `methods.verdict` and `methods.analysis` for `M0155`; one `insights` row.

---

### Step 9: stage and commit the lab pair — serialised against Phases 1, 4 and 5

**File:** `lab/lab.sqlite`, `web/data/lab.json`
**Change:** `lab stage` regenerates `web/data/lab.json` and `git add`s it together with
`lab/lab.sqlite`, under the lab's own write lock. CI checks the two agree row for row.

Phases 1, 4 and 5 all write this database. **This step closes the lock-hold opened at Step 4,
before `lab run M0155`.** The draft plan said "the runs may overlap"; reconciliation reversed
that — a run leaves the shared binary `lab/lab.sqlite` dirty for its whole duration, and while it
is dirty no other session can commit a snapshot that matches the committed database, and any
other phase's `lab stage` would sweep this run's half-finished rows into its own commit. The four
lab runs therefore queue.

#### The lab write lock — one mechanism, defined, identical in every phase of this set

Reconciled 2026-10-14. Every phase plan and the plan index carry these exact commands. Earlier
drafts said "take the write lock" without ever defining one; `lab stage`'s own `BEGIN EXCLUSIVE`
(`commands/lab.py:2824`) covers only `write_snapshot` + `git add` and is released before the
commit, so it is **not** the lock meant here.

```bash
LAB_LOCK=/home/miftah/seer/.git/seer-lab.lock   # inside .git/: no `git add` can ever reach it

# TAKE IT. fd 9 is the handle; the kernel drops it when this shell exits, even on a crash.
exec 9>"$LAB_LOCK"
flock -w 21600 9 || { echo "lab lock still held after 6h -- find out who has it; do NOT force"; exit 1; }
echo "phase-N pid $$ $(date -Is)" >&9        # who holds it, for a human who opens the file

# PROVE THE PAIR IS CLEAN. When nobody holds the lock this must pass. If it fails, a session
# died inside its window and the tree is in an unknown state -- STOP and report, do not repair.
cd /home/miftah/seer
git fetch origin && git merge --ff-only origin/main
git diff --quiet HEAD -- lab/lab.sqlite web/data/lab.json || {
  echo "the lab pair is dirty and nobody held the lock -- STOP"; flock -u 9; exit 1; }

#   ... the critical section ...

# RELEASE.
flock -u 9
```

**The rule, in one line: you may not release the lock with `lab/lab.sqlite` or
`web/data/lab.json` differing from `HEAD`.**

**What is inside a hold.** Every command that writes a lab row — `lab survivorship` (it journals
an `observation`), `lab run`, `lab note`, `lab insight`, `lab seen`, `lab reevaluate` — plus the
`lab stage` (or, for phase 2, `lab export-json`), `git commit` and `git push` that return the pair
to clean. **`lab run` is inside the hold**, which means the four lab phases' runs queue rather
than overlap. That reverses the draft index's "the runs may overlap", and the reason is
build-green: a run leaves the shared binary `lab/lab.sqlite` dirty for its whole duration, and
while it is dirty (a) no other session can export a snapshot that matches the committed database,
so phase 2's `web/data/lab.json` commit cannot be made correct, and (b) any other phase's
`lab stage` would `git add` the half-finished run's rows into its own commit, because `lab stage`
stages the whole file. Two independent measurements agree: `lab run`s contend on one sqlite file
(phase 1 Step 5), and each run loads a whole research store at ~1 GB
(`seer-research-store-memory-budget`), so four at once is RAM pressure on a 16 GB machine. The
cost is honest and accepted: the four lab runs are serial, and the set takes as long as their sum.

**Take short holds, not one long one.** A hold that spans writing a method file starves every
other session for nothing. Each phase's plan names its own hold boundaries below; where a phase
has two or three DB-writing windows separated by file-writing work, it takes two or three holds,
each ending with a stage, a commit and a push.

**What the lock buys:** when no session holds it,
`git diff --quiet HEAD -- lab/lab.sqlite web/data/lab.json` is true. That is the only condition
under which an exported snapshot matches the database committed beside it — which is exactly what
`engine/tests/test_lab_snapshot.py:1054
test_the_committed_snapshot_is_the_export_of_the_committed_database` byte-compares, and CI runs it.


**Code:**
```bash
cd /home/miftah/seer

# `lab stage` targets the MAIN checkout and needs PYTHONPATH (seer-lab-stage-targets-the-main-checkout)
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab stage

# bare -m: `git commit -- <paths>` re-reads the working tree and defeats `lab stage`
# (seer-lab-stage-commit-needs-the-index). No backticks inside a double-quoted -m.
git commit -m "lab: M0155 — <the verdict's own first clause, plain words>

<two or three sentences: what was measured, on which two histories, and the
decision it supports. No ids, no digests.>

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

git push origin main
```

Nothing but the two lab files may be in that commit. On a rejected push, use the mixed-reset
recipe from Step 3 — never `git pull --rebase`. After any merge, re-run `lab stage` and check the
trial `n` values are contiguous before committing again: a rebase that replayed a stale database
leaves gaps.

If the verdict is a rejection, the message style is
`lab: M0155 rejected (the brake sold into noise and gave back more than it saved)` — the plain
reason in the parentheses, no code.

---

### Step 10: close out

**File:** none
**Change:** Confirm the budget did not move and the tree is green.

**Code:**
```bash
cd /home/miftah/seer
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab status   # must read 4 looks
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab show M0155
engine/.venv/bin/ruff check engine
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
PYTHONPATH=engine/src engine/.venv/bin/python -m pytest engine/tests -q
git status --short      # only the untracked strays from other phases should remain
git log --oneline -4
```

**Impact:** none.

---

### The two shared artifacts, and the rules that govern them

#### `web/data/lab.json` — one generator, one commit shape, one recovery

Reconciled 2026-10-14, settling a contradiction between the index's old phase-2 boundary and
phase 2's own measurement. The whole rule, binding on all five phases:

1. **It is never hand-edited, and never `git checkout --`'d back.** It is generated output. The
   only correct copy is the export of the `lab/lab.sqlite` committed beside it.
2. **Lab phases (1, 3, 4, 5) regenerate it with `lab stage`**, which `git add`s it *together with*
   `lab/lab.sqlite`, and commit the pair with a bare `git commit -m …` and nothing else in that
   commit (`seer-lab-stage-commit-needs-the-index`).
3. **Phase 2 regenerates it with `lab export-json` and commits it ALONE by pathspec.**
   `export-json` writes the same bytes to the same path and never touches the git index
   (`commands/lab.py:_export_json` vs `_stage`); `lab stage` would `git add lab/lab.sqlite` too,
   and phase 2 writes no lab row, so staging it would sweep another phase's in-flight trials into
   phase 2's commit. `commands/lab.py:1757-1761` names `export-json` for exactly this situation.
4. **Phase 2 must regenerate it — "phase 2 does not touch the lab's artifacts" cannot hold and is
   withdrawn.** `lab/store.py:2966-2977` builds the snapshot's `paper` block from
   `roster.LAB_PROVENANCE` filtered by `roster.active()`. Retiring `RAW-FR-GT` changes the
   snapshot's bytes (measured: the `paper` array loses one element), and
   `engine/tests/test_lab_snapshot.py:1054` byte-compares the committed file against a live
   export. CI runs that test.
5. **Either generator runs inside the lab write lock**, and the holder has already proved
   `git diff --quiet HEAD -- lab/lab.sqlite`. So the snapshot committed is always the export of
   the database committed.
6. **Finding it ahead of your own commit is normal, not an error.** Another phase landed trials
   after you took your reading. Do not revert it and do not hand-merge it: bring `HEAD` forward
   with `git fetch origin && git merge --ff-only origin/main` — **never `git pull --rebase`**,
   which replays a stale `lab.sqlite` over what the other phases wrote
   (`seer-rebase-replays-stale-lab-sqlite`) — then re-run your generator and commit what comes
   out. If `git diff` is then empty, the other phase's commit already carries your change: commit
   nothing and say so in the close-out. **Whoever lands last is right, and that is by design** —
   the snapshot is a pure function of the database and the roster, so the last regeneration over
   the merged state is the only one that can be correct.

---

### Post-set step: `lab reevaluate` — owned by the last lab phase to land

Reconciled 2026-10-14. Phase 5's draft handed this off to "whoever closes the plan set"; nobody
was "whoever", so it is assigned here by a rule that picks out exactly one session and needs no
coordinator.

All four lab phases move the lab's N by one **method** each, retroactively, on every published
verdict (`seer-lab-n-policy-overcounts-looks`). N rising makes the luck bar harder, never easier,
so nothing can be wrongly loosened by waiting — but `lab reevaluate` is the command that re-judges
every `rejected` method against the bars in force now, and running it once after the fourth run
lands is what keeps the published lab honest. **Once, after all four — not four times.**

**You are the last if, immediately after your own push, all four ids have left `idea`:**

```bash
cd /home/miftah/seer
engine/.venv/bin/python - <<'PY'
import sqlite3
c = sqlite3.connect("file:lab/lab.sqlite?mode=ro", uri=True)   # ro: cannot migrate or dirty it
c.row_factory = sqlite3.Row
rows = {r["id"]: r["status"] for r in c.execute(
    "SELECT id, status FROM methods WHERE id IN ('M0148','M0149','M0155','M0156')")}
print(rows)
print("I AM LAST" if len(rows) == 4 and all(s != "idea" for s in rows.values())
      else "not last -- another lab phase still owes a run")
PY
```

A phase that decides **not** to run its method records that with
`lab drop <id> --reason "<plain reason>"`, which moves the row off `idea`. That is what keeps this
check total: an id can never sit at `idea` forever and leave the set with no last phase.

**If you are last, run it inside the same lock hold** — `lab reevaluate` writes (it can take the
one edge `rejected -> dev-eligible`, `commands/lab.py:1699`) and the whole sweep is one
transaction:

```bash
engine/.venv/bin/python -m seer_engine lab reevaluate

# only if it printed a non-zero "N method(s) moved"; otherwise commit nothing
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab stage
git commit -m "lab: re-judged every rejected method at the new luck bar

Four questions were asked this week, so the bar's multiple-testing count moved by four and
every recorded verdict is read against it. Nothing was re-run and no new measurement was
taken: this is the lab re-reading what it already holds.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push origin main
```

`lab reevaluate` loads no research store, runs no backtest, inserts no trial and cannot reach the
test window — **the look count stays 4**, and it prints the count it found. If it prints
`0 method(s) moved`, that is a result: commit nothing and say so in the close-out.

**If you are not last, do nothing** — and name in your close-out which of the four ids were still
`idea`, so the next phase to finish can see it is becoming the last.

---

## Verification

**Build:** `engine/.venv/bin/ruff check engine` — CI lint is bugs only (E9 and F, minus F401).

**Tests:**
```bash
docker start seer-pg || docker run -d --name seer-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
PYTHONPATH=engine/src engine/.venv/bin/python -m pytest engine/tests -q
```
DB tests need Postgres and **CI fails if they skip**. `PYTHONPATH=engine/src` is not optional —
without it pytest silently tests the main checkout's installed package rather than the working
tree (`seer-worktree-tests-need-pythonpath`).

Measured while this plan was written, with the two new files in place:
`test_lab_methods.py` + `test_lab_m0155_brake.py` + `test_strategy_purity.py` = **941 passed**,
and `ruff check engine` clean. The 13 new `test_lab_methods` cases are 6 smoke windows, 6
allocator contracts and 1 purity check; the 9 new cases are the dedicated module.

**Manual checks:**
1. `lab status` reads **4** test-window looks before Step 4 and after Step 9. This is R6 and it is
   the one number that cannot be put back if it moves.
2. The era script's own control check passed — the line
   `the control reproduced M0152's era numbers` is printed, and its exit code is 0. Without it,
   nothing in the grid may be set beside the width curve.
3. Every arm in the Step 5 report shows a dev re-run that reproduced its recorded trial.
4. `git show --stat` on the Step 9 commit lists exactly `lab/lab.sqlite` and `web/data/lab.json`.
5. `docs/lab/survivorship/grid.csv` is unchanged: `git log --oneline -1 -- docs/lab/survivorship/grid.csv`
   still names `53d5b47`.
6. `git diff 661870d --stat -- engine/src/seer_engine/lab/methods/` lists only the new
   `m0155_*.py` file — no frozen method file moved.

**Exit criteria:** `M0155` is pre-registered by a pushed commit, run on the dev window with six
recorded trials, re-read on the survivorship-check store, and carries a verdict that states
plainly — in the owner's language — whether the brake closes the spring-2006 hole at **twenty**
names against M0152's recorded curve, whether it costs more than a point a year, and whether it is
width in disguise. `lab status` reads 4 test-window looks. `ruff` and the full engine suite are
green.

## Handoffs

- **R3 / Phase 1 (M0156).** `MOM-FR-GT` (`M0002-REL-85`) is the roster's other twenty-name book
  and has no survivorship row at all. This phase does not read it, does not widen it, and does not
  name a width for it. Phase 1 owns that.
- **R1 / Phase 2 (the roster).** Nothing here changes what the owner holds. Even an arm that
  cleared every test in Step 7 would be a lab measurement on a test-failed line; moving the roster
  is Phase 2's commit and its decision, taken on M0152's width number, not on this.
- **R4 / Phase 4 (M0149).** That is also a brake method and the two must not collide: M0155 reads a
  **single holding against the market**, M0149 reads the **whole account's own fall**. The
  allocator ids (`M0155` vs Phase 4's own) and the concept `seen_keys` are disjoint — this phase
  claims `concept:per-holding-relative-shortfall-brake`,
  `concept:single-name-exit-gated-on-a-rising-market` and
  `concept:brake-reading-the-window-the-momentum-skip-hides`, none of which is in `ideas_seen`
  today and none of which describes an account-level brake.
- **A faster clock, left as a journalled feature wish, not built.** A
  `monthly-rank-weekly-resize-frac-gotrade-tband` preset would let a per-holding rule be priced at
  the speed it was designed to run. Adding a preset to `sim/rules.py` is outside this phase: it is
  a shared file that Phase 2's roster pins and every recorded trial reads, and it belongs in its
  own argued commit.
- **A second run on a clean-ancestry book, not attempted.** The idea itself says promotion is not
  available on this line unless the brake is built on a book whose ancestry is clean. If the brake
  survives Step 7, the follow-up is a new method id that mounts the same brake on a non-M0007
  book — a new idea, a new pre-registration, and not an amendment to this one.
- **Not a drive-by.** `lab survivorship --csv` has no era or trough-date columns, which is why
  Step 6 exists as a scratchpad script. Promoting that into a real `lab` subcommand would be a
  genuine improvement and is **not** done here: it would touch `commands/lab.py` and
  `lab/survivorship_check.py`, both shared with every other lab phase running concurrently.

## Rollback

The lab is append-only by trigger: a trial row cannot be deleted, a method's status moves forward
only, and `analysis` may only grow. **Rolling this phase back means writing a further dated note,
never editing a row** — which is the point of the lab.

- **Before Step 4** (the run): fully reversible. `git revert` the Step 3 commit; the method stays
  an `idea` and nothing was recorded. The only cost is that the `M0155` id is still reserved.
- **After Step 4**: the six trials are permanent, and so is the one method the luck gate's N now
  counts. If the method file turns out to be wrong, the correction is a `lab note` appending the
  correction and, if a new configuration is needed, a **new variation method id** — not an edit to
  this file, which `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` would catch and
  which would move a recorded `config_digest`.
- **The two docs files** (Step 7) can be `git revert`ed freely: nothing reads them programmatically.
  `grid.csv` is never touched, so hard-gate D16 cannot be affected either way.
- **Nothing here is destructive and nothing is a schema change.** No migration, no roster row, no
  pinned digest, no test-window look.
