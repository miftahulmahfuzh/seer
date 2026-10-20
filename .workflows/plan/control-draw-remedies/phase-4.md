# Phase 4: Measure the weight vector, before it is built

**Plan set:** `CONTROL_DRAW_REMEDIES_PLAN.md`
**Analysis:** `docs/analyzer/20261020-113306-C7K4_code_analyzer.md`
**Satisfies:** R2 — the owner-facing thing this phase serves is that **M0221's "between 0 and 0.4
points" stops being quoted against a control nobody can defend, and that M0225 stops having no
honest control at all**, either because a weight rule fixes the shape or because this phase proves
no weight rule can and the sentence is rewritten to say so with a number.

*(On M0225: its **−0.890** deficit is recorded in `trials` and quoted in
`docs/plans/HANDOVER_20261019-the-honest-control.md`. Verified read-only at `e3aeeff`, **no
sentence in `methods.verdict` or `methods.analysis` quotes it** — so there is no owner-facing
string for this phase to move. What M0225 has is **no honest control at all**, and that is the
thing this phase can change. Phase 6 confirms this with its own sweep rather than assuming it.)*
**Depends on:** none
**Difficulty:** HARD
**Package:** `.workflows/plan/control-draw-remedies/` (no package under `engine/src` is touched)

---

## Goal

After this phase the lab knows, as a measured number rather than a guess, whether attaching a
weight vector to a blind draw moves a weight-varying control's turnover **toward** the book it
controls or **away** from it — on M0221, where the control turns over 1.95× too much, and on
M0201, where it turns over 0.79× too little, which are opposite directions on the same axis.
Four assignment rules are measured side by side against both books inside one sweep each, nothing
is recorded in the lab, no method id is spent, and the phase is allowed — expected, even — to end
in a STOP that closes leftover 2 of the honest-control handover with a figure instead of carrying
it a third time.

This phase writes **no repo code**. The prototypes are a single script under
`.workflows/plan/control-draw-remedies/` and are handed to `dev.run_registry` as ordinary
`Candidate`s. `run_registry` checks no git state, no digest and no database, so an uncommitted
prototype measures fine and costs no pre-registration, no N and no test-window look.

---

## What is already known, and what is genuinely open

Read this before writing a line. Two of the four rules below are in the sweep because the brief
names them, not because they are expected to win, and knowing which is which keeps the phase from
reading a predictable failure as a surprise.

### The mechanism, derived from the code rather than assumed

`sim.book._beyond_band` (`engine/src/seer_engine/sim/book.py:445-463`) trades a held name only when
its gap is worth **1 % of the whole account** — `MONTHLY_HOLD_FRAC_GOTRADE` leaves
`resize_basis="equity"`. On a 50-name book the average target is 2 % of equity, so a held name must
drift **half its own target** before a single resize fires. The lab has already measured that this
makes the band close to inert (`seer-resize-band-never-fires`).

So turnover on M0221's chassis is **not** drift. `turnover` is
`Σ fill notional / mean equity / years` (`book_runner.py:699`), and on a book whose band rarely
fires almost every dollar of that sum is an **entry or an exit**. The trade *count* is matched
already — 371 against 360, 1.03× — so the whole 1.95× excess is in the **size of each entry and
exit trade**:

- `M0221-C50`'s entrant is the new number 50 by market value. In a cap-weighted top-50 that name
  carries the **smallest** weight in the book, well under 1 % of the account.
- `M0221-C50-PLC`'s entrant is a name drawn blind from the sized pool. Its weight is its own
  market-value share among fifty arbitrary names, which averages **1/50 = 2 %**.
- An entry trade three to four times too large, taken 371 times, is the excess.

`M0221-E50` is the control experiment for exactly this and it fits: identical names, identical 360
trades, every entrant at 2 % instead of its cap weight, **1.60×**. The shipped control pays that
1.60× plus 1.03× of extra name changes, and lands at 1.95×.

A second consequence, and it is the one that makes the brief's worry about drift smaller than it
looks: **a cap-weighted book is exactly drift-neutral between decisions.** A name's target share is
`market_value_i / Σ market_value`, and its holding's share moves identically with its own price
while shares outstanding are unchanged. `M0221-C50-PLC` uses the same code on its own names, so it
is drift-neutral too. That is why both numbers are small in absolute terms.

### What this predicts for each rule, written before the sweep

| rule | what it does to the entrant's rung | predicted direction |
|---|---|---|
| **A** — real vector down the control's month-keyed order | every name is re-assigned a rung every month | **much worse.** The reshuffle alone re-trades most of the book monthly |
| **B** — same vector down the date-free keep order | an entrant lands on a random rung; kept names shift one rung when a name above them leaves | **about the same, or slightly worse** |
| **C** — the control's own values re-shaped to the real book's concentration | the median name shrinks, so a random entrant's rung shrinks | **better**, and drift-neutral by construction |
| **D** — keeps first in keep order, entrants last, down the sorted vector | an entrant always takes a bottom rung, as a real top-N's entrant does | **best**, if the mechanism above is right |

**Rule D is pre-registered here, in the plan, before any number is seen**, because the brief
permits a fourth rule "if the three suggest one" and it is strictly better to derive it from the
mechanism now than to invent it at 2am after watching A, B and C miss. **Rules A, B, C and D are
the whole sweep. There is no rule E, under any result.** If all four miss, that is the STOP, and
the STOP is the deliverable.

### What the free probe already measured, while this plan was being written

The probe of Step 4 was built and **run on M0221 during planning**, on `main` @ `e3aeeff` against
the live store (`640fc25e…`), on 2026-10-20. It is an upper bound on turnover and not a turnover
number, but it costs nothing and it is already decisive about three things. **These are real
measurements, not predictions, and the phase session should expect the sweep to agree with them.**

| arm | entries | mean entrant weight | × book | predicted turnover | × book |
|---|---|---|---|---|---|
| `M0221-C50` (the book) | 425 | **0.0117** | 1.00 | 0.5489 | 1.00 |
| the shipped control | 425 | **0.0221** | **1.89** | 1.4180 | **2.58** |
| rule A | 425 | 0.0567 | 4.85 | **9.2270** | **16.81** |
| rule B | 425 | 0.0119 | **1.02** | 1.2113 | **2.21** |
| rule C | 425 | 0.0214 | 1.83 | 1.3481 | 2.46 |
| rule D | 425 | **0.0089** | 0.76 | 1.2400 | **2.26** |

**One calibration point, and only one.** The shipped control's recorded turnover ratio is 1.951
and the probe puts it at 2.58, so the probe runs about **1.32× high** on this chassis — it counts
every re-weighting the 1 %-of-equity band suppresses. Deflating the rules by that single factor
puts the best of them (rule B) near **1.67×** and rule D near **1.71×**, against the **1.25**
they need. One calibration point is not a calibration; the sweep is the record. But it is enough
to say the phase should prepare to write a STOP.

**Three findings the probe already supports:**

1. **The name axis is matched exactly.** All six arms take in **425** entries over 237 decisions —
   the book's own number, to the unit. Every gap below is on the weight axis and nowhere else.
2. **The entrant-rung mechanism is real, and it is not sufficient.** The shipped control's
   entrant is **1.89×** the book's, against a recorded turnover excess of **1.95×** — the two
   numbers agree almost exactly, which is strong evidence the mechanism written above is the right
   one. And yet rule B drives the entrant rung to **1.02×** of the book's and still predicts
   **2.21×** turnover. **Fixing the entrant's rung buys about 15 % of the excess, not the excess.**
   The residual is Decision D7's own worry, now with evidence behind it: under A, B and D the
   control's target vector is the *real book's*, which moves with the *real book's* prices while
   the control's holding moves with its own, and that foreign drift costs more than the entrant
   fix saves.
3. **Rule C cannot work, and the reason is arithmetic rather than empirical.** The control's
   entrants are drawn uniformly from its own book, so their expected weight is the mean of the
   weight vector — which is `1/n` for **any** normalised vector. No monotone reshaping of the
   control's own values can change that, which is why C's entrant weight moves only from 0.0221 to
   0.0214. It is in the sweep because the brief names it and because a measured no-op is a result;
   it is not in the sweep because it might win.

   *(The first cut of rule C was worse than a no-op — it was byte-identical to the shipped
   control, because a blind draw from M0221's sized pool is **more** concentrated than the real
   top 50, so a one-sided exponent range clamped at 1.0 every month. The range is two-sided for
   that reason; see `GAMMA_MIN`.)*

**None of this cancels the sweep.** The probe does not model the resize band, the fees, the
deposits or the pool attrition, and the exit criteria are written against `trials`-comparable
numbers from `dev.run_registry`. Run all six arms on each chassis regardless. What the probe buys
is that the phase session starts with the mechanism understood, knows which row to read first, and
is not surprised into inventing a rule E when the four land where this table says they will.

### The direction on M0201 is the opposite one, and that is the finding

`M0201-Y20-MV10` turns over **2.4213** and its honest control **1.9228** — 0.794×, short of the
0.80 floor by 0.0059 in ratio. It needs **more** turnover, not less. Any rule that helps M0221 by
shrinking the typical entrant's rung moves M0201 the wrong way, and any rule that helps M0201 by
flattening or de-stabilising its vector moves M0221 the wrong way. **A single weight rule with a
single setting cannot serve both**; what can be shared is the *contract* (the chassis hands over
its own vector; the module assigns it), which is the only sense of "one rule" the plan index
already concedes is reachable. The phase must say this in those words whatever the numbers are.

### Blindness — why reading a vector is allowed at all

The shipped amendment already takes **one number** off the real arm: `e`, how many names changed.
`control_draw`'s docstring calls that "shape, not identity", and D17 agrees. Rules A, B and D read
fifty numbers (a sorted vector, names stripped) and rule C reads **one** (the vector's Herfindahl
index). None of them reads a name, and none of them lets anything about a candidate decide whether
that candidate is drawn — `control_draw.matched_names` is called unchanged, with the same tag and
the same seed, so **every arm in the M0221 sweep holds exactly the same names in exactly the same
months as `M0221-C50-PLC`**. That identity is the experiment's control and the script asserts it.

---

## Interface Contract

**Deletes:** nothing
**Renames:** nothing
**Creates:** `.workflows/plan/control-draw-remedies/phase-4-weight-probe.py` (prototypes + probe +
sweep harness, **outside `engine/`**, imported by nothing); `.workflows/plan/control-draw-remedies/phase-4-results.md`
**Signature changes:** none
**Requires (from earlier phases):** none. Phase 4 depends on nothing and must be runnable at
`main` @ `e3aeeff` exactly as it stands.
**Leaves alone (owned by others):** every file under `engine/src` — in particular
`lab/control_draw.py` (Phase 2), `lab/control_weight.py` (Phase 5, does not yet exist),
`lab/methods/m0221_cap_weighted_top_n.py`, `m0225_cap_weighted_top_n_repaired.py`,
`m0201_treasury_beta_size_weighted.py`, `m0208_capital_gains_overhang.py` (Phases 3 and 5);
`lab/lab.sqlite`; `web/data/lab.json`; `engine/tests/*`.

The prototypes **subclass** the shipped allocators and override only the weighting step. They
never mutate a shipped class, never rebind a module attribute, and never share an allocator id
with a recorded arm.

---

## Files

| File | Action | What changes |
|---|---|---|
| `.workflows/plan/control-draw-remedies/phase-4-weight-probe.py` | create | the four prototype weight rules for each chassis, the free L1 probe, the self-check and the `run_registry` sweep |
| `.workflows/plan/control-draw-remedies/phase-4-results.md` | create | the measured table, the two yes/no answers, and the STOP or the winning rule's definition for Phase 5 |

No other file in the repository is written. Logs and JSONL land in the session scratchpad.

---

## Implementation Steps

### Step 0: Record the invariants, before anything runs

**File:** none (shell)
**Change:** capture the two numbers invariants I1 and I5 are asserted against. Read the database
read-only so nothing migrates it.

**Code:**
```bash
cd /home/miftah/seer
git hash-object lab/lab.sqlite
sqlite3 "file:lab/lab.sqlite?mode=ro" "select count(*) from trials where window='test';"
```

At `main` @ `e3aeeff` these read `607b78cf69c8e4e3a68a1e84c85eedfd1040c754` and `4`. Write both
into `phase-4-results.md` under *Database* as the "before" row. **A `lab` command — any of them,
including a read — may migrate the file on connect; `sqlite3 "file:…?mode=ro"` never does.** This
phase runs no `lab` command at all.

**Impact:** nothing. Two reads.

---

### Step 1: The recorded baselines, and why they are not the comparison

**File:** none (shell)
**Change:** read the recorded rows once, for the results file's context column only.

**Code:**
```bash
cd /home/miftah/seer
sqlite3 -header -column "file:lab/lab.sqlite?mode=ro" "
select t.candidate_id, t.trades, round(t.turnover,4) turnover,
       p.initial_idr, f.schedule, substr(t.store_fingerprint,1,8) store
from trials t
left join trial_provenance p on p.trial_n = t.n
left join trial_funding    f on f.trial_n = t.n
where t.candidate_id in ('M0221-C50','M0221-E50','M0221-C50-PLC',
                         'M0201-Y20-MV10','M0201-Y20-MV10-PLC1')
order by t.n;"
```

Measured 2026-10-20, and this is what the sweep must be funded to match:

| recorded arm | trades | turnover | `initial_idr` | schedule | store |
|---|---|---|---|---|---|
| `M0221-C50` (#713) | 360 | 0.4450 | 10,000,000 | `+5,000,000 IDR on the 25th of each month` | `b683da41` |
| `M0221-E50` (#717) | 360 | 0.7126 | 10,000,000 | same | `b683da41` |
| `M0221-C50-PLC` (#843) | 371 | 0.8681 | 10,000,000 | same | `640fc25e` |
| `M0201-Y20-MV10` (#725) | 433 | 2.4213 | 10,000,000 | same | `b683da41` |
| `M0201-Y20-MV10-PLC1` (#848) | 411 | 1.9228 | 10,000,000 | same | `640fc25e` |

**So the capital is `backtest.runner.INITIAL_IDR` (10,000,000 IDR) and the funding is
`sim.contributions.OWNER_MONTHLY`** — exactly what `lab.runner.run_method` passes, and exactly what
the sweep passes. Both are passed **explicitly** rather than left to a default, so a later change to
`INITIAL_IDR` cannot silently re-point this measurement.

**And the two books ran on a different store from their controls.** `M0221-C50` was recorded
against store fingerprint `b683da41…`; the store in `engine/.research` today is `640fc25e…`
(`manifest.json`, checked 2026-10-20). A re-run of `M0221-C50` today **will not** reproduce 360 /
0.4450, and `lab control`'s 1.95× was computed across that store boundary. This is invariant I8 in
the concrete: **the ratios this phase reports are re-run against re-run, inside one sweep, and the
recorded numbers above appear in the results file only as context.**

**Impact:** nothing. One read.

---

### Step 2: Write the prototype, the probe and the harness

**File:** `.workflows/plan/control-draw-remedies/phase-4-weight-probe.py` (new, created at line 1)
**Change:** one script, four subcommands: `selfcheck`, `probe`, `sweep`, `report`.

**Do not retype it — extract it.** The block below is the whole file, it was run during planning
(`selfcheck: OK`, both registries construct, the M0221 probe completed), and a transcription typo
would be measured rather than caught:

```bash
cd /home/miftah/seer
python3 - <<'PYEOF'
import re, pathlib
src = pathlib.Path(".workflows/plan/control-draw-remedies/phase-4.md").read_text()
blocks = re.findall(r"\n```python\n(.*?)\n```\n", src, re.S)
assert len(blocks) == 1, f"expected one python block, found {len(blocks)}"
out = pathlib.Path(".workflows/plan/control-draw-remedies/phase-4-weight-probe.py")
out.write_text(blocks[0] + "\n")
print(f"wrote {out} ({len(blocks[0])} chars)")
PYEOF
```

It must report **40436 chars**. A different count means this plan file was edited after the block
was verified; run `selfcheck` (Step 3) before trusting it either way.

**Code:**

```python
"""Phase 4 of control-draw-remedies: measure the weight-vector remedy before it is built.

Nothing here is lab code. It is a scratchpad prototype, it writes no trial, it opens no database
and it is imported by nothing under ``engine/``. It exists to answer one question for free:

    does attaching a weight vector to the lab's matched draw move a weight-varying control's
    turnover TOWARD the book it controls, or AWAY from it?

The direction is not known. ``M0221-C50-PLC`` already weights its drawn names by their own market
values with the chassis's own code, so it is already drift-neutral in the same way the book is;
its 1.95x excess is not drift. Measured from ``sim.book._beyond_band``, which under
``monthly-hold-frac-gotrade`` trades a held name only when its gap is worth 1% of the WHOLE
account, the resize band on a 50-name book is close to inert -- a name must drift half its own
target to move. So the excess is in the SIZE of the entry and exit trades, not in their number
(371 against 360, 1.03x) and not in drift. A cap-weighted top-50's entrant is the new number 50
and carries the smallest weight in the book; a blind draw's entrant carries about 1/50 of the
account. ``M0221-E50`` is that effect alone -- identical names, identical trades, every entrant at
1/50 -- and it reads 1.60x.

Four assignment rules are prototyped against that model, and all four are pre-registered in this
file's plan before any of them ran:

  A  the real book's sorted weight vector, down the control's own month-keyed order
  B  the same vector, down the date-free keep order
  C  the control's OWN market values, raised to a power fitted so the vector has the real book's
     Herfindahl index, then the chassis's own ceiling -- drift-neutral by construction
  D  keeps first in the keep order, this month's entrants last, down the same sorted vector, so an
     entrant always takes a BOTTOM rung, as a real top-N's entrant does

There is no rule E. If all four miss, the phase STOPs and that is the deliverable.

Every arm holds the SAME NAMES as the shipped control: ``control_draw.matched_names`` is called
unchanged, with the same tag and the same seed, and only the weight each drawn name is handed
differs. Every arm also holds the same TOTAL exposure as the shipped control: each rule is
renormalised to the shipped control's own weight sum, so a rule changes the shape of the vector
and never how much of the book is invested.

The same four rules are prototyped on M0201, where the gap runs the other way: that control needs
MORE turnover (1.9228 against the book's 2.4213, 0.794x, short of D17's 0.80 floor by 0.0059).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np

from seer_engine import dates, research
from seer_engine.backtest.dev import DEV_END, MEMBERSHIP_START, Candidate, run_registry
from seer_engine.backtest.runner import INITIAL_IDR
from seer_engine.lab import control_draw
from seer_engine.lab.methods import m0201_treasury_beta_size_weighted as m0201
from seer_engine.lab.methods import m0221_cap_weighted_top_n as m0221
from seer_engine.lab.methods.m0034_size_tilt_residual import _apply_ceiling, _floor_weight
from seer_engine.sim.contributions import OWNER_MONTHLY
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, is_rank_session
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.f_factor import trend_on

STORE = Path(os.environ.get("SEER_RESEARCH_STORE", "/home/miftah/seer/engine/.research"))

#: Bisection bounds for rule C's exponent. 1.0 reproduces the chassis's own weighting exactly,
#: and the range is TWO-SIDED on purpose: measured on the dev store during planning, a blind draw
#: from M0221's sized pool is MORE concentrated than the real top 50 is, not less -- the draw
#: spans the whole size range while the top 50 are all mega-caps under a 10% ceiling. A
#: one-sided [1, 24] range therefore clamped at 1.0 every single month and made rule C a
#: byte-identical copy of the shipped control, which measures nothing. Below 1 the transform
#: flattens; above 1 it sharpens; the fit picks whichever side the month needs.
GAMMA_MIN = 0.05
GAMMA_MAX = 24.0
GAMMA_STEPS = 48


# --------------------------------------------------------------------------- shared shaping


def _hhi(w) -> float:
    """Herfindahl index of a weight vector: the one number rule C matches."""
    a = np.asarray(list(w), dtype=np.float64)
    return float(np.square(a).sum())


def _rescale(v: list[float], n: int, total: float) -> list[float]:
    """``v`` trimmed or padded to ``n`` rungs and renormalised to sum to ``total``.

    The control's book can be shorter than the real book's when the eligible pool is thin, and
    ``matched_names`` already handles that on the name axis; this handles it on the weight axis.
    Padding repeats the smallest rung, which is what a real top-N would do with one more name.
    ``total`` is always the SHIPPED control's own weight sum, so a rule never changes how much of
    the book is invested -- only its shape.
    """
    if n <= 0 or total <= 0.0:
        return [0.0] * max(0, n)
    if not v:
        return [total / n] * n
    out = list(v[:n]) if n <= len(v) else list(v) + [v[-1]] * (n - len(v))
    s = float(sum(out))
    if not np.isfinite(s) or s <= 0.0:
        return [total / n] * n
    return [x / s * total for x in out]


def _powered(values: list[float], gamma: float) -> np.ndarray:
    """``values`` scaled to a max of 1 and raised to ``gamma``, as a normalised vector.

    The scaling is there only so ``v ** 24`` cannot overflow on raw market values; normalising
    afterwards makes it exactly scale-invariant, so ``gamma == 1.0`` returns ``v / sum(v)``
    bit-for-bit as the chassis computes it.
    """
    v = np.asarray(values, dtype=np.float64)
    if len(v) == 0:
        return v
    top = float(v.max())
    if not np.isfinite(top) or top <= 0.0:
        return np.full(len(v), 1.0 / len(v))
    v = np.power(v / top, float(gamma))
    s = float(v.sum())
    if not np.isfinite(s) or s <= 0.0:
        return np.full(len(v), 1.0 / len(v))
    return v / s


def _capped(values: list[float], gamma: float, cap: float | None, *,
            exposure: float = 1.0, floor_to_equal: bool = True) -> np.ndarray:
    """``_powered``, scaled to ``exposure``, with the chassis's own ceiling applied.

    ``floor_to_equal`` is the one place the two chassis genuinely differ, and it is not a choice
    made here: ``m0221.weights`` caps at ``max(cap, 1/len)`` and ``m0201.sized_weights`` caps at
    ``cap`` flat, and each rule below passes the flag its own chassis uses. ``exposure`` is scaled
    in BEFORE the ceiling for the same reason -- ``sized_weights`` does, and the cap is an
    absolute share of the account, not a share of the invested part. At ``gamma == 1.0`` this
    returns exactly what that chassis's own function returns, which ``selfcheck`` asserts on two
    hundred random vectors.
    """
    w = _powered(values, gamma) * float(exposure)
    if cap is None or len(w) == 0:
        return w
    c = float(cap)
    if floor_to_equal:
        c = max(c, float(exposure) / len(w))
    return _apply_ceiling(w, c)


def fitted_gamma(values: list[float], cap: float | None, target_hhi: float, *,
                 exposure: float = 1.0, floor_to_equal: bool = True) -> float:
    """The exponent whose capped vector, NORMALISED, has Herfindahl index ``target_hhi``.

    Bisection on [GAMMA_MIN, GAMMA_MAX]. The index is non-decreasing in the exponent -- raising a
    normalised vector to a higher power moves mass to its largest entries, and the ceiling only
    flattens the result from above -- so bisection is well posed. The range straddles 1.0 because
    the control's own values can be either flatter or sharper than the real book's: on M0221 the
    probe measured them SHARPER every month, so a one-sided range would silently return 1.0 and
    rule C would be the shipped control under another name. The index is taken on the normalised
    vector so that it compares like with like whatever ``exposure`` is.
    """
    if len(values) < 2:
        return 1.0

    def hhi_at(g: float) -> float:
        w = np.asarray(_capped(values, g, cap, exposure=exposure, floor_to_equal=floor_to_equal))
        s = float(w.sum())
        return _hhi(w / s) if s > 0.0 else 0.0

    lo, hi = GAMMA_MIN, GAMMA_MAX
    if hhi_at(lo) >= target_hhi:
        return lo
    if hhi_at(hi) <= target_hhi:
        return hi
    for _ in range(GAMMA_STEPS):
        mid = 0.5 * (lo + hi)
        if hhi_at(mid) < target_hhi:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# --------------------------------------------------------------------------- M0221 prototypes


class _CapWeightRule(m0221.MatchedCapTopAllocator):
    """``M0221-A1`` with the weight step replaced by ``_assign`` and nothing else touched.

    The sized pool, the two selections, the ``control_draw.matched_names`` call, its tag, its
    seed and its month-keyed return order are the shipped allocator's. So every subclass below
    holds the identical names in the identical months as ``M0221-C50-PLC`` and differs from it
    only in which weight each drawn name is given -- which is the whole experiment.
    """

    id = "PROTO"

    def _assign(self, picks: list[str], pool: dict[str, float], real_now: list[str],
                held: AbstractSet[str], data_date: date, p: Any) -> list[float]:
        raise NotImplementedError

    def _base(self, picks: list[str], pool: dict[str, float], p: Any) -> float:
        """The shipped control's own weight sum on these names: the exposure every rule keeps."""
        w = m0221.weights([pool[s] for s in picks], p)
        return float(sum(0.0 if x is None else float(x) for x in w))

    def _rungs(self, picks: list[str], pool: dict[str, float], p: Any) -> list[float]:
        """The real arm's own weight vector this month, biggest rung first.

        The real arm is the top ``p.top`` of the sized pool by market value and ``m0221.weights``
        is the chassis's own weighting code, so this is the vector the book actually holds. The
        NAMES are dropped here and never reach the control: only the numbers cross.
        """
        order = sorted(pool, key=lambda s: (-pool[s], s))[: p.top]
        w = m0221.weights([pool[s] for s in order], p)
        v = sorted((0.0 if x is None else float(x) for x in w), reverse=True)
        return _rescale(v, len(picks), self._base(picks, pool, p))

    def _matched(self, prepared: Any, members: AbstractSet[str], data_date: date,
                 held: frozenset[str], p: Any) -> tuple[Any, ...]:
        if prepared.market is None:
            return ()
        if not trend_on(prepared.history, data_date, m0221._gate(p)):
            return ()
        now, pool = self._selection(prepared, members, data_date, p)
        if not pool:
            return ()
        prev, _ = self._selection(
            prepared, members, control_draw.previous_decision_date(data_date), p
        )
        picks = control_draw.matched_names(
            pool=tuple(sorted(pool)),
            held=held,
            real_now=now,
            real_prev=prev,
            tag=m0221.DRAW_KEY,
            seed=p.seed,
            data_date=data_date,
        )
        if not picks:
            return ()
        ws = self._assign(list(picks), pool, list(now), held, data_date, p)
        out = []
        for s, x in zip(picks, ws, strict=True):
            w = _floor_weight(float(x))
            if w is None:
                continue
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)


class CapRuleA(_CapWeightRule):
    """A: the real book's sorted vector straight down ``matched_names``' own return order.

    That order is keyed on the calendar month (``control_draw.entry_key``), so it re-shuffles at
    every decision and every name is expected to be handed a different rung every month. This is
    the literal reading of the sentence leftover 2 was written in -- "the k-th drawn name takes
    the k-th largest weight the real book holds that month" -- and it is in the sweep because the
    brief asks for it, not because it is expected to win.
    """

    id = "PROTO-M0221-WA"

    def _assign(self, picks, pool, real_now, held, data_date, p):
        return self._rungs(picks, pool, p)


class CapRuleB(_CapWeightRule):
    """B: the same vector down the DATE-FREE keep order (``control_draw.keep_key``).

    ``keep_key`` carries no date term, so a name's position among the control's holdings is the
    same at every decision it survives: a held name keeps its rung, and moves only when a name
    ordered above it leaves. An entrant takes whatever rung its own hash puts it on, which is on
    average the middle of the vector.
    """

    id = "PROTO-M0221-WB"

    def _assign(self, picks, pool, real_now, held, data_date, p):
        order = sorted(picks, key=lambda s: (control_draw.keep_key(m0221.DRAW_KEY, p.seed, s), s))
        by = dict(zip(order, self._rungs(order, pool, p), strict=True))
        return [by[s] for s in picks]


class CapRuleC(_CapWeightRule):
    """C: the control's OWN market values, re-shaped to the real book's concentration.

    The shipped control already weights by its drawn names' own market values, which is what makes
    it drift-neutral: a name's target share is its own market-value share, which moves with its own
    price, so the realised weight tracks the target and the 1%-of-equity band rarely fires. This
    rule keeps that property -- every weight stays a monotone function of that name's OWN size --
    and changes only how steep the function is, by raising each value to an exponent fitted that
    month so the resulting capped vector has the same Herfindahl index as the real book's.

    It reads ONE number off the real arm where A, B and D read fifty. Both are shape and neither
    is identity, which is the standard the entry count ``e`` already passes; C simply reads less.
    """

    id = "PROTO-M0221-WC"

    def _assign(self, picks, pool, real_now, held, data_date, p):
        rungs = self._rungs(picks, pool, p)
        total = float(sum(rungs))
        if total <= 0.0:
            return [0.0] * len(picks)
        target = _hhi([x / total for x in rungs])
        values = [pool[s] for s in picks]
        g = fitted_gamma(values, p.cap, target, exposure=total)
        return [float(x) for x in _capped(values, g, p.cap, exposure=total)]


class CapRuleD(_CapWeightRule):
    """D: keeps first in the keep order, this month's entrants last, down the sorted vector.

    Designed from the mechanism and pre-registered before the sweep: on a cap-weighted top-N the
    name that ENTERS is the new number ``top``, so it enters at the smallest weight in the book,
    and the name that left, left from there too. Under the shipped control and under rules A and B
    a blind entrant takes an average rung instead -- about 1/top of the account against the real
    book's rank-``top`` weight -- and an entry trade three or four times too large, taken 371
    times, is the whole excess. This rule reproduces WHERE the churn happens as well as how much
    of it there is.

    ``held`` is the only thing an allocator knows about its own past and it is enough: the
    entrants are ``picks - held`` by definition, at no cost and with no state. Nothing here is
    carried between calls, so the rule is a pure function of the date it is given (invariant I9).
    """

    id = "PROTO-M0221-WD"

    def _assign(self, picks, pool, real_now, held, data_date, p):
        keeps = sorted(
            (s for s in picks if s in held),
            key=lambda s: (control_draw.keep_key(m0221.DRAW_KEY, p.seed, s), s),
        )
        fresh = sorted(
            (s for s in picks if s not in held),
            key=lambda s: (control_draw.entry_key(m0221.DRAW_KEY, p.seed, s, data_date), s),
        )
        order = keeps + fresh
        by = dict(zip(order, self._rungs(order, pool, p), strict=True))
        return [by[s] for s in picks]


CAP_A, CAP_B, CAP_C, CAP_D = CapRuleA(), CapRuleB(), CapRuleC(), CapRuleD()


# --------------------------------------------------------------------------- M0201 prototypes

#: One prepared value per Market for every M0201 PROTOTYPE arm. ``dev.run_registry`` caches
#: ``prepare_for`` per ALLOCATOR ID, and this sweep runs four prototype ids on a chassis whose
#: ``prepare_market`` builds M0197's whole factor panel, so without this the sweep would build
#: that panel four times. It is a memo about DATA, keyed on the market object's identity; nothing
#: in it depends on a date, a candidate or a fold, so it is not the mutable allocator state the
#: lab forbids. The two SHIPPED baselines are deliberately left on their own singletons and build
#: their own, so the baseline rows come off the shipped code path untouched.
_PANEL: dict[int, Any] = {}


def _shared_panel(market: Any) -> Any:
    key = id(market)
    got = _PANEL.get(key)
    if got is None:
        got = m0201.SIZEDYB.prepare_market(market)
        _PANEL[key] = got
    return got


class _SizedWeightRule(m0201.MatchedSizedPlaceboAllocator):
    """``M0201-A1`` with ``resize``'s weighting replaced by ``_company_weights``.

    Everything that decides WHICH names the control holds is the shipped allocator's, unchanged:
    ``matched_frac``, ``matched_entries``, the 40% keep band, the quarterly calendar and
    ``m0197.choose``. The re-sizing step is re-implemented here line for line from
    ``m0201.resize`` -- the company collapse, the split of a company's weight over its held
    classes, the SPY filler and the exposure -- with one substitution: where ``resize`` calls
    ``m0201.sized_weights``, this calls ``_company_weights``.
    """

    id = "PROTO-SIZED"

    def prepare_market(self, market: Any) -> Any:
        return _shared_panel(market)

    def _company_weights(self, prepared: Any, members: AbstractSet[str], data_date: date,
                         held: AbstractSet[str], keys: list[str], size: dict[str, float],
                         exposure: float, p: Any) -> list[Decimal | None]:
        raise NotImplementedError

    def _base(self, keys: list[str], size: dict[str, float], exposure: float,
              p: Any) -> float:
        """The shipped control's own company-weight sum: the exposure every rule keeps."""
        cw = m0201.sized_weights([size[k] for k in keys], exposure, float(p.cap))
        return float(sum(0.0 if x is None else float(x) for x in cw))

    def _rungs(self, prepared: Any, members: AbstractSet[str], data_date: date,
               keys: list[str], size: dict[str, float], exposure: float,
               p: Any) -> list[float]:
        """The bond book's own company-weight vector this month, biggest rung first.

        A FRESH top-20 of M0197's bond ranking stands in for the real held book, sized by the
        chassis's own ``sizes`` and ``sized_weights``. That stand-in carries exactly the freshness
        approximation this chassis's entry count already carries -- ``matched_entries`` derives
        ``e`` from a fresh re-pick too, and the walk measured it at 0.955 of the real entries --
        so the weight axis inherits the same bias the trade axis already has, and phase 5 inherits
        it with the rule if it builds one. Only numbers cross; the names are dropped here.
        """
        base = self._base(keys, size, exposure, p)
        now = m0201.real_frac_at(prepared, members, data_date, p)
        if not now:
            return _rescale([], len(keys), base)
        book = [s for _, s in sorted((v, s) for s, v in now.items())][: p.yb.inner.top]
        rsize = m0201.sizes(prepared, book, data_date, p)
        rkeys = list(rsize)
        cw = m0201.sized_weights(
            [rsize[k] for k in rkeys], len(book) / p.yb.inner.top, float(p.cap)
        )
        v = sorted((0.0 if x is None else float(x) for x in cw), reverse=True)
        return _rescale(v, len(keys), base)

    def _held_company(self, held: AbstractSet[str], keys: list[str]) -> set[str]:
        """The company keys the control already holds through any of their listed classes."""
        return {m0201.company(s) for s in held} & set(keys)

    def _resize(self, prepared: Any, members: AbstractSet[str], equal: tuple[Any, ...],
                data_date: date, held: AbstractSet[str], p: Any) -> tuple[Any, ...]:
        market = p.yb.market
        picks = [t.symbol for t in equal if t.symbol != market]
        if not picks:
            return tuple(equal)
        size = m0201.sizes(prepared, picks, data_date, p)
        keys = list(size)
        exposure = len(picks) / p.yb.inner.top
        cw = self._company_weights(prepared, members, data_date, held, keys, size, exposure, p)
        weight = dict(zip(keys, cw, strict=True))
        out = []
        for s in picks:
            w = weight[m0201.company(s)]
            if w is None:
                continue
            n = sum(1 for x in picks if m0201.company(x) == m0201.company(s))
            if n > 1:
                w = _floor_weight(float(w) / n)
                if w is None:
                    continue
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        rest = Decimal(1) - sum((t.weight for t in out), Decimal(0))
        mh = prepared.history.get(market)
        if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
            t = target_from_close(market, last_close(mh, data_date), rest)
            if t is not None:
                out.append(t)
        return tuple(out)

    def _run(self, prepared: Any, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: Any) -> tuple[Any, ...]:
        p = m0201._check_control(p)
        if len(prepared.series) == 0 or prepared.market is None:
            return ()
        if not trend_on(prepared.history, data_date, p.yb.inner):
            return ()
        stocks = [s for s in held if s != p.yb.market and s not in m0201.EXCLUDED]
        repick = not stocks or data_date.month in m0201.REPICK_MONTHS
        frac = m0201.matched_frac(prepared, members, data_date, held, p) if repick else {}
        equal = m0201.choose(prepared.history, members, frac, data_date, held, p.yb)
        return self._resize(prepared, members, equal, data_date, held, p)


class SizedRuleA(_SizedWeightRule):
    """A on M0201: the bond book's sorted vector down the month-keyed entry order."""

    id = "PROTO-M0201-WA"

    def _company_weights(self, prepared, members, data_date, held, keys, size, exposure, p):
        order = sorted(keys, key=lambda k: (control_draw.entry_key("M0201", p.seed, k, data_date), k))
        rungs = self._rungs(prepared, members, data_date, order, size, exposure, p)
        by = dict(zip(order, rungs, strict=True))
        return [_floor_weight(by[k]) for k in keys]


class SizedRuleB(_SizedWeightRule):
    """B on M0201: the same vector down the date-free keep order."""

    id = "PROTO-M0201-WB"

    def _company_weights(self, prepared, members, data_date, held, keys, size, exposure, p):
        order = sorted(keys, key=lambda k: (control_draw.keep_key("M0201", p.seed, k), k))
        rungs = self._rungs(prepared, members, data_date, order, size, exposure, p)
        by = dict(zip(order, rungs, strict=True))
        return [_floor_weight(by[k]) for k in keys]


class SizedRuleC(_SizedWeightRule):
    """C on M0201: the control's own company sizes, re-shaped to the bond book's concentration.

    ``m0201.sized_weights``' own steps in its own order -- the median fill for an unknown size,
    the scaling to ``exposure``, then the ceiling -- with the sizes raised to a fitted exponent
    first. At exponent 1.0 this is ``sized_weights`` exactly, which ``selfcheck`` asserts.
    """

    id = "PROTO-M0201-WC"

    def _company_weights(self, prepared, members, data_date, held, keys, size, exposure, p):
        rungs = self._rungs(prepared, members, data_date, keys, size, exposure, p)
        total = float(sum(rungs))
        if total <= 0.0:
            return [None] * len(keys)
        target = _hhi([x / total for x in rungs])
        raw = [size[k] for k in keys]
        known = [x for x in raw if x > 0.0]
        med = float(np.median(known)) if known else 1.0
        filled = [x if x > 0.0 else med for x in raw]
        g = fitted_gamma(filled, float(p.cap), target, exposure=total, floor_to_equal=False)
        w = _capped(filled, g, float(p.cap), exposure=total, floor_to_equal=False)
        return [_floor_weight(float(x)) for x in w]


class SizedRuleD(_SizedWeightRule):
    """D on M0201: kept companies first in the keep order, entrants last, down the vector."""

    id = "PROTO-M0201-WD"

    def _company_weights(self, prepared, members, data_date, held, keys, size, exposure, p):
        mine = self._held_company(held, keys)
        keeps = sorted((k for k in keys if k in mine),
                       key=lambda k: (control_draw.keep_key("M0201", p.seed, k), k))
        fresh = sorted((k for k in keys if k not in mine),
                       key=lambda k: (control_draw.entry_key("M0201", p.seed, k, data_date), k))
        order = keeps + fresh
        rungs = self._rungs(prepared, members, data_date, order, size, exposure, p)
        by = dict(zip(order, rungs, strict=True))
        return [_floor_weight(by[k]) for k in keys]


SIZED_A, SIZED_B, SIZED_C, SIZED_D = SizedRuleA(), SizedRuleB(), SizedRuleC(), SizedRuleD()


# --------------------------------------------------------------------------- the registries

CAP_CTL = m0221.CapTopParams(50, pick="random", seed=1, trend=None)
CAP_BOOK = m0221.CapTopParams(50, trend=None)
SIZED_CTL = m0201._p("placebo", seed=1)
SIZED_BOOK = m0201._p("bond")


def _c(cid: str, family: str, allocator: Any, params: Any, why: str) -> Candidate:
    return Candidate(id=cid, family=family, rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=allocator, params=params, rationale=why,
                     added=date(2026, 10, 20), owner_inputs=())


def registry_m0221() -> list[Candidate]:
    """The book, the shipped control, and the four rules -- in that order, one sweep.

    Every id carries a PROTO- prefix. Nothing here is recorded and nothing here is a lab arm; the
    prefix is so a reader of the results file can never mistake a row for a recorded trial.
    """
    return [
        _c("PROTO-M0221-C50", "M0221", m0221.CAPTOP, CAP_BOOK,
           "Baseline: the book, re-run on today's store"),
        _c("PROTO-M0221-PLC", "M0221", m0221.MATCHED, CAP_CTL,
           "Baseline: the shipped matched draw, re-run on today's store"),
        _c("PROTO-M0221-WA", "M0221", CAP_A, CAP_CTL,
           "Rule A: the real vector down the month-keyed order"),
        _c("PROTO-M0221-WB", "M0221", CAP_B, CAP_CTL,
           "Rule B: the real vector down the date-free keep order"),
        _c("PROTO-M0221-WC", "M0221", CAP_C, CAP_CTL,
           "Rule C: the control's own values re-shaped to the real concentration"),
        _c("PROTO-M0221-WD", "M0221", CAP_D, CAP_CTL,
           "Rule D: keeps in keep order, entrants last, down the real vector"),
    ]


def registry_m0201() -> list[Candidate]:
    """The bond book, the shipped seed-1 control, and the four rules, in that order.

    The two baselines run FIRST and on the shipped singletons, so ``run_registry`` frees their
    factor panels before the four prototypes share one through ``_shared_panel``.
    """
    return [
        _c("PROTO-M0201-BOOK", "M0201", m0201.SIZEDYB, SIZED_BOOK,
           "Baseline: the bond book, re-run on today's store"),
        _c("PROTO-M0201-PLC1", "M0201", m0201.MATCHED, SIZED_CTL,
           "Baseline: the shipped matched draw, seed 1, re-run on today's store"),
        _c("PROTO-M0201-WA", "M0201", SIZED_A, SIZED_CTL,
           "Rule A: the bond vector down the month-keyed order"),
        _c("PROTO-M0201-WB", "M0201", SIZED_B, SIZED_CTL,
           "Rule B: the bond vector down the date-free keep order"),
        _c("PROTO-M0201-WC", "M0201", SIZED_C, SIZED_CTL,
           "Rule C: the control's own company sizes re-shaped to the bond concentration"),
        _c("PROTO-M0201-WD", "M0201", SIZED_D, SIZED_CTL,
           "Rule D: kept companies in keep order, entrants last, down the bond vector"),
    ]


REGISTRIES = {"m0221": registry_m0221, "m0201": registry_m0201}


# --------------------------------------------------------------------------- self-check


def cmd_selfcheck(_args: argparse.Namespace) -> int:
    """Assert the shaping machinery is the chassis's own code at exponent 1, and that the four
    M0221 rules hand out the same total exposure as the shipped control.

    No store, no market, no database: pure arithmetic, under a second. If this is red the sweep
    is measuring something other than the rules it claims to.
    """
    rng = np.random.default_rng(20261020)
    bad = 0
    # The chassis's own functions quantise DOWN to ``sim.book.WEIGHT_QUANTUM`` (1e-6) and return
    # None below it; these helpers do not quantise at all, because the caller floors afterwards.
    # So the tolerance is the quantum, not float noise, and a None is compared as 0.0.
    tol = dict(rtol=1e-6, atol=2e-6)
    for _ in range(200):
        n = int(rng.integers(10, 60))  # CapTopParams needs cap >= 1/top, and cap is 0.10
        values = [float(x) for x in rng.lognormal(mean=10.0, sigma=2.0, size=n)]
        p = m0221.CapTopParams(n, pick="random", seed=1, trend=None)
        want = [0.0 if x is None else float(x) for x in m0221.weights(values, p)]
        got = [float(x) for x in _capped(values, 1.0, p.cap)]
        if not np.allclose(want, got, **tol):
            bad += 1
            print(f"FAIL cap: n={n} max|d|={max(abs(a - b) for a, b in zip(want, got)):.3e}")
        exposure = float(rng.uniform(0.3, 1.0))
        wl = [0.0 if x is None else float(x)
              for x in m0201.sized_weights(values, exposure, 0.10)]
        gl = [float(x) for x in
              _capped(values, 1.0, 0.10, exposure=exposure, floor_to_equal=False)]
        if not np.allclose(wl, gl, **tol):
            bad += 1
            print(f"FAIL sized: n={n} max|d|={max(abs(a - b) for a, b in zip(wl, gl)):.3e}")
        v = sorted((float(x) for x in rng.random(n)), reverse=True)
        r = _rescale(list(v), n, 0.97)
        if abs(sum(r) - 0.97) > 1e-9:
            bad += 1
            print(f"FAIL rescale: n={n} sum={sum(r)}")
    print("selfcheck: OK" if bad == 0 else f"selfcheck: {bad} FAILURES")
    return 0 if bad == 0 else 1


# --------------------------------------------------------------------------- the free probe


def decision_dates() -> list[date]:
    return [
        dates.prev_session(s)
        for s in dates.sessions(MEMBERSHIP_START, DEV_END)
        if is_rank_session(MONTHLY_HOLD_FRAC_GOTRADE, s)
    ]


def _targets_of(market: Any, allocator: Any, params: Any, prepared: Any, d: date,
                held: frozenset[str]) -> dict[str, float]:
    members = market.membership.members_on(d)
    ts = allocator.targets_prepared(prepared, members, d, held, params)
    return {t.symbol: float(t.weight) for t in ts}


def _closes(market: Any, symbols, d: date) -> dict[str, float]:
    out = {}
    for s in symbols:
        c = last_close(market.history.get(s), d)
        if c is not None and np.isfinite(c) and c > 0.0:
            out[s] = float(c)
    return out


def probe_arm(market: Any, allocator: Any, params: Any, prepared: Any, label: str) -> dict:
    """A free, backtest-free estimate of annual turnover, plus the entrant's mean weight.

    At each monthly decision the previous decision's weights are drifted forward by their own
    price moves and compared with today's weights; the L1 distance is the fraction of the book
    the decision asks to trade. Summed over the window and divided by the years, that is an
    UPPER BOUND on ``trials.turnover`` -- the 1%-of-equity band suppresses small moves this
    counts, and deposits buy shares this does not. It is triage and ordering only: the recorded
    answer is the sweep, and the results file says so.

    ``entry_w`` is the mechanism headline: the mean weight handed to a name on the decision it
    enters the book.
    """
    prev_w: dict[str, float] = {}
    prev_c: dict[str, float] = {}
    l1 = 0.0
    entry_w: list[float] = []
    entries = 0
    months = 0
    held: frozenset[str] = frozenset()
    ds = decision_dates()
    for d in ds:
        now = _targets_of(market, allocator, params, prepared, d, held)
        if not now:
            held = frozenset()
            prev_w, prev_c = {}, {}
            continue
        cnow = _closes(market, set(now) | set(prev_w), d)
        drifted: dict[str, float] = {}
        if prev_w:
            grown = {}
            for s, w in prev_w.items():
                a, b = prev_c.get(s), cnow.get(s)
                grown[s] = w * (b / a) if (a and b) else w
            tot = sum(grown.values())
            scale = (sum(prev_w.values()) / tot) if tot > 0 else 1.0
            drifted = {s: v * scale for s, v in grown.items()}
        for s in set(now) | set(drifted):
            l1 += abs(now.get(s, 0.0) - drifted.get(s, 0.0))
        fresh = [s for s in now if s not in held]
        entries += len(fresh)
        entry_w.extend(now[s] for s in fresh)
        held = frozenset(now)
        prev_w = dict(now)
        prev_c = {s: cnow[s] for s in now if s in cnow}
        months += 1
    years = (ds[-1] - ds[0]).days / 365.25 if len(ds) > 1 else 1.0
    out = {
        "label": label,
        "months": months,
        "entries": entries,
        "entry_w": float(np.mean(entry_w)) if entry_w else 0.0,
        "l1_per_year": l1 / years,
    }
    print(f"{label:22s} months {out['months']:3d}  entries {out['entries']:4d}  "
          f"mean entrant weight {out['entry_w']:.4f}  predicted turnover {out['l1_per_year']:.4f}")
    return out


def cmd_probe(args: argparse.Namespace) -> int:
    data = research.load_store(STORE)
    market = data.market
    rows = []
    if args.chassis in ("m0221", "both"):
        prep = m0221.CAPTOP.prepare_market(market)
        rows.append(probe_arm(market, m0221.CAPTOP, CAP_BOOK, prep, "M0221-C50 book"))
        rows.append(probe_arm(market, m0221.MATCHED, CAP_CTL, prep, "M0221 shipped control"))
        for a, name in ((CAP_A, "M0221 rule A"), (CAP_B, "M0221 rule B"),
                        (CAP_C, "M0221 rule C"), (CAP_D, "M0221 rule D")):
            rows.append(probe_arm(market, a, CAP_CTL, prep, name))
    if args.chassis in ("m0201", "both"):
        prep = _shared_panel(market)
        rows.append(probe_arm(market, m0201.SIZEDYB, SIZED_BOOK, prep, "M0201 bond book"))
        rows.append(probe_arm(market, m0201.MATCHED, SIZED_CTL, prep, "M0201 shipped control"))
        for a, name in ((SIZED_A, "M0201 rule A"), (SIZED_B, "M0201 rule B"),
                        (SIZED_C, "M0201 rule C"), (SIZED_D, "M0201 rule D")):
            rows.append(probe_arm(market, a, SIZED_CTL, prep, name))
    Path(args.out).write_text(json.dumps(rows, indent=2) + "\n")
    print(f"wrote {args.out}")
    return 0


# --------------------------------------------------------------------------- the sweep


def cmd_sweep(args: argparse.Namespace) -> int:
    """One ``dev.run_registry`` call over one chassis's six arms, funded as the trials were.

    ``contributions=OWNER_MONTHLY`` and ``initial_idr=INITIAL_IDR`` are passed EXPLICITLY, as
    ``lab.runner.run_method`` passes them and as ``trial_funding`` and ``trial_provenance`` record
    them for every arm in play (10,000,000 IDR, +5,000,000 on the 25th, 237 deposits). A later
    change to ``INITIAL_IDR`` therefore cannot silently re-point this measurement.

    Every row is appended to the JSONL as it finishes, so a kill loses only the arms that had not
    run and the file is still the record of the ones that had.
    """
    data = research.load_store(STORE)
    out = Path(args.out)
    out.write_text("")
    candidates = REGISTRIES[args.chassis]()

    def on_result(i: int, _result: Any, row: Any) -> None:
        rec = {
            "id": row.candidate.id,
            "allocator": row.candidate.allocator.id,
            "start": row.start.isoformat(),
            "end": row.end.isoformat(),
            "trades": int(row.stats.metrics.trades),
            "turnover": float(row.stats.turnover),
            "exposure": float(row.stats.exposure),
            "costs_usd": float(row.stats.costs_usd),
            "mwr": None if row.stats.metrics.mwr is None else float(row.stats.metrics.mwr),
            "spy_tr_mwr": None if row.spy_tr.mwr is None else float(row.spy_tr.mwr),
            "max_drawdown": None if row.stats.metrics.max_drawdown is None
                            else float(row.stats.metrics.max_drawdown),
        }
        with out.open("a") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(f"[{i + 1}/{len(candidates)}] {rec['id']:20s} trades {rec['trades']:4d}  "
              f"turnover {rec['turnover']:.4f}", flush=True)

    run_registry(
        data.market,
        data.dividends,
        data.spy_dividends,
        candidates,
        on_result=on_result,
        contributions=OWNER_MONTHLY,
        initial_idr=INITIAL_IDR,
    )
    print(f"wrote {out}")
    return 0


# --------------------------------------------------------------------------- the report


WARN_LO, WARN_HI = 0.80, 1.25


def cmd_report(args: argparse.Namespace) -> int:
    """The markdown table phase-4-results.md carries, built from a sweep's JSONL.

    The first row of the file is the BOOK and every ratio is taken against it, inside the same
    sweep -- re-run against re-run (invariant I8). Recorded columns are never mixed in here.
    """
    rows = [json.loads(line) for line in Path(args.jsonl).read_text().splitlines() if line.strip()]
    if not rows:
        print("no rows", file=sys.stderr)
        return 1
    book = rows[0]
    print(f"book: {book['id']}  {book['trades']} trades / {book['turnover']:.4f} turnover")
    print()
    print("| arm | trades | turnover | trades x | turnover x | verdict |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        tx = r["trades"] / book["trades"] if book["trades"] else float("nan")
        ux = r["turnover"] / book["turnover"] if book["turnover"] else float("nan")
        ok = WARN_LO <= tx <= WARN_HI and WARN_LO <= ux <= WARN_HI
        miss = []
        if not WARN_LO <= tx <= WARN_HI:
            miss.append("trades")
        if not WARN_LO <= ux <= WARN_HI:
            miss.append("turnover")
        verdict = "**OK**" if ok else "miss: " + "+".join(miss)
        if r is book:
            verdict = "— the book —"
        print(f"| `{r['id']}` | {r['trades']} | {r['turnover']:.4f} | {tx:.3f} | {ux:.3f} | {verdict} |")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("selfcheck", help="assert the shaping is the chassis's own code at gamma 1")
    s.set_defaults(fn=cmd_selfcheck)
    s = sub.add_parser("probe", help="free L1 triage, no backtest")
    s.add_argument("--chassis", choices=("m0221", "m0201", "both"), required=True)
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_probe)
    s = sub.add_parser("sweep", help="one dev.run_registry sweep over one chassis")
    s.add_argument("--chassis", choices=("m0221", "m0201"), required=True)
    s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_sweep)
    s = sub.add_parser("report", help="the markdown ratio table from a sweep's JSONL")
    s.add_argument("--jsonl", required=True)
    s.set_defaults(fn=cmd_report)
    args = ap.parse_args()
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
```

**Impact:** creates one file outside `engine/`. `ruff check engine` does not see it and `pytest
engine/tests` does not collect it. Nothing imports it.

---

### Step 3: Self-check, before paying for anything

**File:** none (shell)
**Change:** run the pure-arithmetic assertions.

**Code:**
```bash
cd /home/miftah/seer
export PY=/home/miftah/seer/engine/.venv/bin/python
export PYTHONPATH=/home/miftah/seer/engine/src
export SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research
SCRATCH=/tmp/claude-1000/-home-miftah-seer/<session>/scratchpad
mkdir -p "$SCRATCH"

$PY .workflows/plan/control-draw-remedies/phase-4-weight-probe.py selfcheck \
    > "$SCRATCH/selfcheck.log" 2>&1
echo "exit=$?"
cat "$SCRATCH/selfcheck.log"
```

Redirection, never a pipe: a pipe hands the exit code to the last stage (invariant I4's reason,
and it applies to every command in this phase, not only to `lab` ones).

**Exit condition:** `selfcheck: OK`. If it is not, the shaping helpers are not the chassis's own
code at exponent 1 and the whole sweep would measure the wrong thing. **Fix the helper, never the
assertion.**

**Impact:** nothing. Under a second, no store.

---

### Step 4: The free probe — triage, and the mechanism number

**File:** none (shell)
**Change:** run the backtest-free L1 probe on each chassis.

**Code:**
```bash
cd /home/miftah/seer
$PY .workflows/plan/control-draw-remedies/phase-4-weight-probe.py probe \
    --chassis m0221 --out "$SCRATCH/probe-m0221.json" \
    > "$SCRATCH/probe-m0221.log" 2>&1
echo "exit=$?"; cat "$SCRATCH/probe-m0221.log"

$PY .workflows/plan/control-draw-remedies/phase-4-weight-probe.py probe \
    --chassis m0201 --out "$SCRATCH/probe-m0201.json" \
    > "$SCRATCH/probe-m0201.log" 2>&1
echo "exit=$?"; cat "$SCRATCH/probe-m0201.log"
```

**What it is for, and what it is not.** `l1_per_year` is an upper bound on turnover — it counts
every re-weighting the band would suppress and misses the buying the deposits do — so **it is
never quoted as a turnover number.** It is read for two things only:

1. **Ordering.** If rule A's predicted turnover is five times the book's, the sweep will say the
   same thing more expensively, and the results file can say so twice as confidently.
2. **`entry_w`, the mechanism headline.** The mean weight handed to a name on the decision it
   enters. **The M0221 half of this probe has already been run** (see *What the free probe
   already measured* above): book `0.0117`, shipped control `0.0221`, A `0.0567`, B `0.0119`,
   C `0.0214`, D `0.0089`, with 425 entries on every arm. Re-run it anyway — it costs ten minutes
   and it confirms the prototype file was transcribed correctly — and **if any number differs,
   stop and find out why before the sweep**: the two runs are the same code on the same store and
   a difference means the transcription moved something.

   The M0201 half has **not** been run. Its `entry_w` column is new information and the results
   file reports it in full.

**Do not drop an arm from the sweep on the probe's evidence.** All six arms run on each chassis
whatever the probe says; the probe orders the write-up, it does not prune the experiment.

**Expected cost:** loading the store is one to two minutes and is paid once per invocation.
M0221's six arms are about a minute each (237 decisions × two `sized_pool` passes). M0201's six
are slower — each decision re-reads M0197's bond ranking — budget ten to twenty minutes for that
chassis. Run the two commands **one at a time**; never both at once.

**Impact:** nothing is written outside the scratchpad.

---

### Step 5: The sweep — one chassis at a time

**File:** none (shell)
**Change:** two `dev.run_registry` sweeps, in two separate processes, sequentially.

**Code:**
```bash
cd /home/miftah/seer
$PY .workflows/plan/control-draw-remedies/phase-4-weight-probe.py sweep \
    --chassis m0221 --out "$SCRATCH/sweep-m0221.jsonl" \
    > "$SCRATCH/sweep-m0221.log" 2>&1
echo "exit=$?"; tail -20 "$SCRATCH/sweep-m0221.log"

# Only after the first has exited. Never two sweeps at once on this laptop.
$PY .workflows/plan/control-draw-remedies/phase-4-weight-probe.py sweep \
    --chassis m0201 --out "$SCRATCH/sweep-m0201.jsonl" \
    > "$SCRATCH/sweep-m0201.log" 2>&1
echo "exit=$?"; tail -20 "$SCRATCH/sweep-m0201.log"
```

**Why two sweeps and not one, and why that still satisfies I8.** Invariant I8 binds the
*comparison*: "any pre-run shape comparison measures both arms inside one `dev.run_registry`
sweep". M0221's six arms are compared only with each other and M0201's six only with each other,
so each comparison is inside one sweep and no ratio in this phase ever crosses a process boundary.
Running them as one twelve-arm sweep would hold two research panels and one market in memory at
once on a 15 GB laptop that a parallel wave has already taken down twice; the store alone loads
whole at roughly 1.79 MB per symbol and this store serves 539. **One sweep at a time, cheapest
first (M0221), and never a second process while one is running.** `phase-4-weight-probe.py sweep
--chassis both` is deliberately not offered.

**Expected cost:** M0221, six arms × 237 monthly decisions over 1996-01-03..2015-10-16, around
fifteen to thirty minutes including the store load. M0201, six arms on a chassis that builds
M0197's factor panel and re-reads the bond ranking at every decision, **one to three hours**. Start
M0221, write up its half of the results file while M0201 runs.

**If a sweep is killed:** the JSONL holds every arm that finished. Re-run only the remaining arms
by editing `registry_m0201()` to the short list — **keeping the book first**, because every ratio
is taken against it and a sweep without its own book is not a comparison. Record in the results
file that the arms came from two processes and which.

**Impact:** nothing is written outside the scratchpad. No lab database is opened: `run_registry`
touches `market`, `dividends` and `spy_dividends` and nothing else.

---

### Step 6: The ratio tables

**File:** none (shell)
**Change:** build the two markdown tables the results file carries.

**Code:**
```bash
cd /home/miftah/seer
$PY .workflows/plan/control-draw-remedies/phase-4-weight-probe.py report \
    --jsonl "$SCRATCH/sweep-m0221.jsonl" > "$SCRATCH/table-m0221.md" 2>&1
echo "exit=$?"; cat "$SCRATCH/table-m0221.md"

$PY .workflows/plan/control-draw-remedies/phase-4-weight-probe.py report \
    --jsonl "$SCRATCH/sweep-m0201.jsonl" > "$SCRATCH/table-m0201.md" 2>&1
echo "exit=$?"; cat "$SCRATCH/table-m0201.md"
```

**Impact:** none.

---

### Step 7: Write `phase-4-results.md`

**File:** `.workflows/plan/control-draw-remedies/phase-4-results.md` (new, created at line 1)
**Change:** the phase's whole deliverable.

**It must contain, in this order:**

1. **Header** — date, verdict in one word (`GO (rule X)` or `STOP`), the plan set, the environment
   (`main` @ the commit it ran on, store fingerprint `640fc25e…`, `engine/.venv`), and the sentence
   *"No trial was recorded, no method id was spent, no amendment was written and `lab` was never
   invoked."*
2. **The recorded context table** from Step 1, labelled *context only — not the comparison*, with
   the store-fingerprint column and the explicit note that `M0221-C50` ran on `b683da41…` and its
   control on `640fc25e…`, so the recorded 1.95× crosses a store boundary and this phase's ratios
   do not.
3. **The M0221 table** from Step 6: six rows, trades, turnover, trades ×, turnover ×, verdict.
4. **The M0201 table**, same shape.
5. **The probe table**: `entry_w` and `l1_per_year` per arm, with the sentence that the probe is an
   upper bound and is quoted for ordering and for the mechanism, never as turnover — and, for
   M0221, the planning-time run beside the phase's own so the two can be seen to agree.
   **Then the sentence the probe earns:** the shipped control's entrant weight is 1.89× the
   book's against a recorded turnover excess of 1.95×, so the entrant-rung mechanism is the right
   account of where the excess comes from; and rule B drives that ratio to 1.02× while still
   predicting 2.21× turnover, so **fixing it buys about 15 % of the excess and not the excess.**
   Say which of those two sentences the sweep confirmed and which it did not.
6. **The two yes/no answers, each with its number**, in these exact shapes:
   - *"Does any rule bring M0221's control inside `WARN_BAND`? **<yes/no>.** The best was rule
     `<X>` at `<u>` turnover against the book's re-run `<u_book>` — `<ratio>`×, against the 1.25
     ceiling — with `<t>` trades, `<ratio>`×, against the 0.80–1.25 band."* State the absolute bar
     both ways: against the re-run book (the real test) and against the recorded 0.4450 (≤ 0.5563,
     for the reader who knows that number).
   - *"Does any rule close M0201's 0.0059 gap? **<yes/no>.** The best was rule `<X>` at `<u>`
     against the book's re-run `<u_book>` — `<ratio>`×, against the 0.80 floor — with trades at
     `<ratio>`×."* The recorded bar is ≥ 1.937 turnover.
7. **The direction finding, stated plainly**, whichever way it came out. If the rules raised
   M0221's turnover, say that Decision D7's worry was right and name the mechanism the numbers
   support. If they lowered it, say the entrant-rung mechanism in this plan was right and name the
   margin.
8. **What a single rule serving both chassis would have to do** — the paragraph the brief asks
   for. M0221 needs its control's entrant rung to shrink; M0201 needs its control to move more.
   Report whether any one rule landed both inside the band at the same setting, and if not, say in
   one sentence that a weight rule is a **contract** (the chassis hands over its own vector; the
   shared module assigns it), never one setting, and that this is the same standard
   `matched_partition` already meets.
9. **The STOP rule, written out even if it did not fire** (see the next section).
10. **Database**: `git hash-object lab/lab.sqlite` before and after — identical — and test-window
    looks 4 → 4, with the read-only query that produced both.
11. **For phase 5**: either the winning rule's complete definition (the class, the assignment
    order, the vector the chassis must hand over, and the one number or fifty it reads), or the
    STOP and what phase 5 therefore is.

**Impact:** the file phases 5 and 6 read.

---

## The STOP rule, in full

**It fires when:** no rule lands M0221's control inside `WARN_BAND` on **both** axes against the
book re-run in the same sweep — turnover ratio in [0.80, 1.25] and trade ratio in [0.80, 1.25].

**When it fires, phase 4 is still a success**, and the results file must say so in those words.
What it must then contain, in addition to everything above:

- **The number that closes leftover 2.** The best turnover ratio any of the four rules achieved on
  M0221, named with its rule, beside the shipped control's own re-run ratio. "Leftover 2 closes at
  `<best>`×, against the 1.25 it needed and the `<shipped>`× it started from."
- **A one-line verdict on whether a weight rule is reachable at all**, which is not the same
  question as whether these four reached it. It must answer, from the measured `entry_w` column
  and the four turnover ratios, one of exactly these three:
  - *"Reachable, and not by assignment."* — a rule moved the number substantially toward the band
    but stopped short, and `entry_w` separated as the model predicted. Then the remaining gap is
    named (pool attrition, the ceiling, the promotion jump a kept entrant makes when it moves from
    the bottom rung into the keep block, and the foreign-vector drift Decision D7 named) and
    carried as a sized, specific leftover.

    **This is the branch the planning-time probe points at**, and if the sweep lands there the
    results file must carry the decomposition the probe already supports: *the entrant's rung is
    1.89× too large and explains the 1.95× excess; driving it to 1.02× recovers about 15 % of
    that excess; the rest is the control tracking a vector whose prices are not its own.* Name
    the share each half carries from the sweep's own numbers, not from the probe's.
  - *"Unreachable by any assignment rule."* — every rule moved the number the wrong way or barely
    at all, and `entry_w` did not separate. Then say that the turnover of a weight-varying control
    is not a property the control can be given, and that the lab's honest option on this chassis is
    to quote the margin with its measured handicap attached rather than to keep drawing arms.
  - *"Not settled here, and what would settle it."* — only if a sweep could not be completed. Name
    what did not run and what it would cost.
- **The consequence, spelled out**, because phases 5 and 6 act on it:
  - **Phase 5 draws neither M0221 nor M0225.** No `control_weight.py`, no amendment on
    `m0221_cap_weighted_top_n.py`, none on `m0225_cap_weighted_top_n_repaired.py`. Phase 5 becomes
    the one paragraph its own exit criteria already allow.
  - **M0201 is decided separately.** The STOP is M0221's. If M0201's gap closed, phase 5 may still
    draw M0201's arm alone — the plan index's phase 5 lists M0201 as conditional on exactly this
    measurement. The results file must state the two verdicts independently and must not let
    M0221's STOP suppress an M0201 GO or the reverse.
  - **Phase 6 writes it up as the answer**, not as a gap: leftover 2 of
    `HANDOVER_20261019-the-honest-control.md` closes with a number, and **M0225 still has no honest
    control** — its **−0.890** deficit stays computable only against `M0225-R50`, an arm that
    traded 0.195× and turned over 0.424×. That deficit lives in `trials` and in the previous
    handover, **not in any sentence the owner reads** (verified read-only at `e3aeeff`), so phase 6
    writes the new handover to say plainly, with no ids, that the lab publishes no owner-facing
    claim resting on it and why. It does not invent a sentence to correct.

**What the STOP is not.** It is not permission to invent a rule E. Four rules, measured, then stop.
A fifth rule invented after seeing four results is a rule chosen by the data, and this lab does not
record those.

---

## Verification

**Build:** nothing is built. The phase adds no file under `engine/`, so
`engine/.venv/bin/ruff check engine` and `engine/.venv/bin/pytest engine/tests` are unchanged by
it — run both once at the end anyway and record that they are green and that the tree is clean
except for this phase's two files (invariant I11).

```bash
cd /home/miftah/seer
engine/.venv/bin/ruff check engine
PYTHONPATH=/home/miftah/seer/engine/src engine/.venv/bin/pytest engine/tests -q
git status --porcelain
```

**Tests:** the phase's own correctness gate is `selfcheck` (Step 3), which must print
`selfcheck: OK`, plus one assertion the results file states explicitly: **every M0221 prototype
holds the same names as the shipped control.** It follows by construction — `_CapWeightRule`
overrides only `_assign` and the name path is `MatchedCapTopAllocator`'s — and the sweep confirms
it from the far side: if a rule's **trade count** differs from `PROTO-M0221-PLC`'s by more than
pool attrition can explain, something other than the weights moved and the row is not evidence.
Report `PROTO-M0221-PLC`'s trade count beside each rule's.

**Manual check:** the probe's `entry_w` column against the model written at the top of this file.

**Exit criteria** (all of them, and the phase is not done until each is a line in the results file):

- A table of trades and turnover for **every arm in each sweep**, with the ratio to its **own
  sweep's** book.
- **Yes/no with the number** for M0221: does any rule reach ≤ 1.25× turnover against the re-run
  book (recorded equivalent ≤ 0.5563) with trades inside 0.80–1.25×?
- **Yes/no with the number** for M0201: does any rule reach ≥ 0.80× turnover against the re-run
  book (recorded equivalent ≥ 1.937) with trades still inside the band?
- The opposite-directions paragraph, and what it implies about one rule serving both.
- `git hash-object lab/lab.sqlite` identical before and after — `607b78cf69c8e4e3a68a1e84c85eedfd1040c754`
  at `main` @ `e3aeeff` — and `select count(*) from trials where window='test'` reading **4** both
  times (invariants I1, I5).
- The STOP rule stated in the results file whether or not it fired, including the one-line verdict
  on reachability.
- Phase 5's input stated unambiguously: the winning rule's definition, or the STOP.

---

## Handoffs

- **Phase 5's branch key, named here so there is one vocabulary.** This phase measures **four**
  rules — A (month-keyed entry order), B (date-free keep ladder), C (the control's own values
  re-shaped), D (keeps first in keep order, entrants last down the sorted vector) — and phase 5's
  §0 table reads the winner as exactly one of **S** (no rule cleared), **G-entry** (A),
  **G-ladder** (B), **G-size** (C) or **G-bottom** (D). The results file must name the winner by
  **both** its letter and its key, so phase 5 does not have to infer one from the other. Two rules
  clearing, or a rule clearing on one axis only, is **S**.

- **Phase 5 owns every line of repo code this phase's measurement implies.** `control_weight.py`,
  its tests and the amendments on `m0221`, `m0225` and (conditionally) `m0201` are its, and nothing
  in the prototype file is intended to be copied into `engine/src` unexamined: the prototypes
  override whole methods for speed of measurement, where a shipped rule must be a shared contract
  with the chassis handing over its vector. The prototype is the **specification** of the rule,
  not its implementation.
- **The M0201 weight vector uses a fresh top-20 stand-in for the real bond book.** That is the same
  freshness approximation `matched_entries` already makes on this chassis (measured 0.955 of the
  real entries), and it is the *weight*-axis twin of the held-set shadow phases 1–3 are building on
  the *name* axis. **It serves R1, not R2, so it is not this phase's to fix.** If phase 2's shadow
  lands, phase 5 should consider feeding it the same shadow rather than a fresh re-pick, and
  re-measure. Recorded here so it is not discovered later as a defect.
- **The `entry_w` number is reusable and nothing else in the lab computes it.** If the mechanism in
  this plan holds, "the mean weight a control hands a name on the decision it enters" is the single
  diagnostic that predicts a weight-varying control's turnover excess, and D17 could one day read
  it directly instead of inferring it from a ratio. That is a `control_shape` change and belongs to
  neither this phase nor phase 5; carry it to phase 6's leftovers.
- **M0047 is excluded by Decision D6 and this phase honours it.** Its honest arms already read
  0.99/0.92 and 0.98/0.89, and its allocator has 46 bars of lookback headroom. It is not probed, not
  swept and not mentioned in the results beyond one line saying why.
- **No drive-by.** `sim.rules` still has no weekly fractional Gotrade preset, `name_count.py`'s
  docstring is still wrong about N, and `control_shape` still has no `entry_w`. None of those is
  touched here.

---

## Rollback

```bash
cd /home/miftah/seer
rm -f .workflows/plan/control-draw-remedies/phase-4-weight-probe.py \
      .workflows/plan/control-draw-remedies/phase-4-results.md
```

That is the whole of it. The phase writes two files under `.workflows/plan/`, writes nothing under
`engine/`, opens no database for writing, records no trial, spends no method id and spends no
test-window look. If the phase's commit has already landed, `git revert` it; nothing recorded moves
either way, because nothing was recorded.
