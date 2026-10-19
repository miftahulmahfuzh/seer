# Phase 6: M0208 — the 4.41x extreme

**Plan set:** `HONEST_CONTROL_REDRAW_PLAN.md`
**Analysis:** `docs/analyzer/20261019-181712-C4K9_code_analyzer.md`
**Satisfies:** R2 (re-draw the mis-shaped arm as an Amendment under the existing id), R3 (re-state
the margin in `trial_funding.mwr`, including a margin that worsens or reverses), R4 (the arm's own `supersedes` declaration — without it phase 2's D17 rule fires on nothing and the method stays blocked after the measurement)
**Depends on:** Phase 1 — `engine/src/seer_engine/lab/control_draw.py` must exist and be green
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab/methods`

---

## Goal

`M0208` gains one pre-registered amendment arm, `M0208-CGO-N20-PLC`: the capital-gains-overhang
book's own shape — same pool, same twenty equal slots, same keep-40 band, same SPY 200-day switch,
same monthly entry count — with none of its identity. After this phase the lab holds a recorded
dev trial for that arm, and the sentence "the overhang book beats its placebo by +5.87 points a
year" has been re-measured against an opponent that is not paying five times the fee bill.

M0208's old control, `M0208-HASH-N20`, trades **4.41x** and turns over **5.20x** the arm it
controls — the widest shape miss anywhere in the set, against the biggest quoted margin in it.
This phase does not delete it, edit it, or re-run it. It adds the honest one beside it.

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:** nothing. No candidate, no params field, no allocator, no recorded row.

**Renames:** nothing.

**Creates:**
- `M0208.MatchedDrawAllocator` (`m0208_capital_gains_overhang.py`), allocator `id = "M0208-A1"` —
  new, unique lab-wide (verified: the only `id = "M0208…"` in `engine/src` today is
  `OverhangAllocator.id = "M0208"` at `m0208_capital_gains_overhang.py:300`).
- `M0208.MATCHED` — the module-level instance of it.
- `M0208._banded_picks`, `M0208._book`, `M0208.previous_month_end`, `M0208._a1` — new
  module-level helpers, all private to the amendment section except `previous_month_end`.
- `M0208.A1_ADDED`, `M0208.MATCHED_DRAW` — the `Amendment` block (seq 1) and its date.
- candidate `M0208-CGO-N20-PLC` (one arm, inside the amendment).

**Signature changes:** none. `OverhangParams`, `overhangs`, `draw`, `scored`, `choose`,
`OverhangAllocator`, `OverhangPrepared`, `build_week_grid` and `WeekGrid` are all left
**byte-identical**. The new allocator subclasses `OverhangAllocator` and overrides `_targets`
and `id` only.

**No params dataclass is created and none is touched.** `M0208-CGO-N20-PLC` reuses
`OverhangParams(N20, keep=40)` unchanged — the *same value* `M0208-CGO-N20` runs on. See
*Why no new params dataclass* below for the digest argument.

**Requires (from earlier phases):**
- Phase 1 — `seer_engine.lab.control_draw.matched_book(...)` exists with the contract stated in
  *Assumed helper contract* below, and phase 1's `lab control M0227 M0243` landed both pilot arms
  inside `WARN_BAND`. **If phase 1 stopped, this phase does not start** (plan index, Decisions:
  "what happens if the pilot misses the band").

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/control_draw.py` (Phase 1) — consumed unchanged, never edited.
- `engine/src/seer_engine/lab/control_shape.py`, `hardgate.py`, `commands/lab.py` (Phase 2).
  In particular: this phase does **not** try to make `M0208-HASH-N20`'s refusal go away.
  D17 still refuses M0208 at the end of this phase; phase 2's supersession rule is what clears it.
- Every other `mNNNN_*.py` (Phases 1, 3, 4, 5, 7).
- `lab stage`, `web/data/lab.json`, `lab.sqlite` staging, the merge, the handover (Phase 8).
- `METHOD.hypothesis` and `METHOD.expected_failure` on M0208 — frozen pre-registration prose.
  The sentence *"beats the placebo by at least 2 points a year"* at `:393` is the thing being
  re-measured; it is **not** edited. The amendment's own `hypothesis` re-states it.
- The four original candidates' ids, params and rationales (`:411-421`).
- `lab test`, `SEER_RESEARCH_TEST_STORE`, `engine/.research-test`, `engine/.research-sv`.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/methods/m0208_capital_gains_overhang.py` | modify | docstring paragraph after `:50`; `Sequence` added to the `collections.abc` import at `:59`; `Amendment` added to the `lab.method` import at `:69`; new `control_draw` import after `:69`; a new amendment section inserted between `:361` and `:363`; `amendments=(MATCHED_DRAW,)` added to `METHOD` after `:421` |

One file. No test file is added: the rule's session-by-session proof is phase 1's
`engine/tests/test_lab_control_draw.py`, and M0208's own smoke fixture cannot exercise the draw
at all (see *Verification*).

---

## Where the 4.41x / 5.20x actually comes from

The task requires this written down, because a matched-draw rule that only fixes part of it will
miss the band. Three candidate sources; the code settles all three.

### 1. The re-key period — this is essentially the whole of it

`M0208-HASH-N20` scores with `m0208.draw` (`:235-238`), a **local copy of M0187's month-keyed
hash**:

```python
key = f"{seed}|{symbol}|{data_date.year:04d}-{data_date.month:02d}".encode()
```

A monthly rank session is the first NYSE session of a calendar month (`sim/rules.py:368-379`) and
the allocator is handed the session before it, so **every decision gets a fresh, independent
permutation of the pool**. Last month's ordering carries no information about this month's.

The real arm's score is the opposite. `overhangs` (`:198-232`) is a 156-to-260-week
turnover-weighted reference price against today's close. Between two month-ends 21 sessions apart
the weekly grid gains four or five week-blocks out of 260 and drops the same number; the reference
price barely moves. A name in the top 40 one month is overwhelmingly in the top 40 the next.

So the band (next section) retains almost every held name for `CGO-N20` and almost none for
`HASH-N20`. That is the mechanism, and the arithmetic is the measurement: `trials` for
`M0208-CGO-N20` is 624 closed trades over 1996-01-03 → 2015-10-16 against 2749 for
`M0208-HASH-N20`.

### 2. Slot sizing — contributes **nothing**, verified in the code

Both arms are `OverhangParams(N20, keep=40, …)` with the same `inner = FactorParams(rank=
"momentum", top=20, trend=("SPY", 200))`. `choose` (`:252-277`) never reads `p.signal`: it takes
`equal_weight(p.inner.top)` = 1/20 for every pick and puts the remainder in SPY, identically for
both arms. There is no size branch anywhere between `scored` and the Targets.

The counter-example in the same method proves slot size *would* have shown up if it differed:
`M0208-CGO-N40` records **more** trades (952) at **lower** turnover (2.439) than `CGO-N20`
(624 / 3.061), because its slots are 1/40. Turnover is notional-weighted
(`backtest/book_runner.py:699`: fill notional / mean session equity / years); the trade count is
not. Two arms whose slots differ move the two numbers in opposite directions. `CGO-N20` and
`HASH-N20` move them in the same direction, which is what equal slots look like.

Exposure confirms there is no third effect hiding: `CGO-N20` 0.699, `HASH-N20` 0.692 — the switch
is off for the same months in both arms and the SPY-remainder leg is the same size.

### 3. The band's interaction with a hash score — the same mechanism, amplified, and it is the part the fix must not get wrong

`choose`'s band is

```python
kept = sorted((s for s in held if rank.get(s, p.keep) < p.keep), key=lambda s: rank[s])
```

On a persistent score this is hysteresis: a held name leaves only when its own overhang has
genuinely decayed past rank 40. On a freshly-permuted score it is a **lottery**: a held name
survives only if this month's independent draw happens to put it inside the top 40 of a pool of
roughly 400 scorable members, about a 1-in-10 chance. The band is not a second mechanism — it is
the multiplier that turns a re-keyed order into a near-total monthly rebuild of the book.

Why this matters for the fix: a rule that only *slowed the re-key down* — holding the hash order
fixed between rebalances — would overshoot into family A. That is exactly M0227-R20's 0.07x, and
M0243's own file says the author saw it and over-corrected (`m0243:50-52`). The rule has to match
**entries per rebalance**, derived from the real arm's own banded selection on its own calendar,
which is what Rule A does and what this phase consumes. Matching the entry count matches the
trade count by construction, and because the slots are the real arm's own 1/20 and the exposure
is the same, it matches turnover too.

### Why turnover misses by more than trades (5.20x against 4.41x)

Not a fourth mechanism. A `trades` row is a count of **closed round trips**; `turnover` is a sum
of **fill notionals** on both sides, divided by mean equity and by years, and it also prices the
SPY-remainder leg and the monthly deposit deployment. The two measure the same churn in different
units, and a book that rebuilds itself monthly re-prices every leg at a full 1/20 slot while a
book that holds for seven months on average closes some positions that were never resized up. The
rule addresses both at once because it works on entry counts at identical slot sizes: fix the
count and the notional follows.

**Conclusion the plan commits to:** the 4.41x / 5.20x is one defect — a hand-chosen monthly re-key
against a signal that persists for months, amplified by a band that is hysteresis for one arm and
a lottery for the other. There is no slot-sizing component and no band-shape component that a
churn-matched draw fails to reach.

---

## The helper contract (phase 1 owns this — reconciled against its actual module)

Reconciled 2026-10-19 against `phase-1.md`. This phase calls **one** function, keyword-only:

```python
# engine/src/seer_engine/lab/control_draw.py  (phase 1)
def matched_names(
    *,
    pool: Sequence[str],
    held: AbstractSet[str],
    real_now: Sequence[str],
    real_prev: Sequence[str],
    tag: str,
    seed: int,
    data_date: date,
) -> list[str]:
    ...
```

Semantics this phase relies on, and nothing else:

1. `e = churn(real_now, real_prev) = len(set(real_now) - set(real_prev))` — the real arm's entry
   count at this decision.
2. `keep_n = max(0, len(real_now) - e)`; at most that many names of `held & pool` are kept, first
   under a **date-free** hash of `(tag, seed, symbol)`, ties by symbol.
3. The book is filled to exactly `len(real_now)` from the rest of the pool in a **month-keyed**
   hash order of `(tag, seed, symbol, data_date`'s year-month`)` — the same keying `m0208.draw`
   already uses — taking names the control does **not** hold first and the holdings it is
   dropping only once those run out. Ties by symbol.
4. The return is a list of symbols, every one drawn from `pool`, no duplicates, deterministic,
   and it reads nothing but its arguments (pure: no clock, no randomness).

**Three differences from this plan's first draft, applied at the one call site below.** The name
is `matched_names`, not `matched_book` (Phase 1's `matched_book` takes a `select` callable, which
this chassis does not need because it already has both selections in hand). The arguments are
keyword-only and are `real_now` / `real_prev` / `tag`, not positional `picks_now` / `picks_prev`
/ `seed`. And the return is a `list`, not a `tuple` — `_book` iterates it, so nothing else moves.

`tag` is the **book's** method id, `"M0208"`, and `pool` is passed **in symbol order**, never in
score order, so the real arm's ranking cannot leak into the control through a tie-break.

---

## Why no new params dataclass, and why no digest moves

`registry._canon` renders a dataclass by `dataclasses.fields()` (`backtest/registry.py:323-332`),
not by `as_dict()`. Adding any `compare=True` field to `OverhangParams` — even defaulted, even
local to this file — would move the recorded `config_digest` of all four M0208 trials (677–680)
and of nothing else, but that is already fatal:
`test_every_recorded_configuration_still_digests_to_its_recorded_digest` fails and
`prereg.check_source` refuses. Adding a `compare=False` field would instead make the new arm's
configuration *identical* to `M0208-CGO-N20`'s, which `Method.__post_init__` refuses as
*"repeats another variant's configuration"*.

The route taken avoids both: **the new arm reuses `OverhangParams` untouched and changes only the
allocator id.** That is now the rule for all nine methods (index invariant "One params value, one
new allocator id"), and this phase is where it was first argued.

**One thing is specific to M0208, and the index records it as the set's single exception.** Every
other phase reuses the params value of **the arm it replaces**; this one reuses the value of the
arm it **controls**, `OverhangParams(N20, keep=40)` with `signal="high"`, rather than
`HASH-N20`'s `signal="hash"`. The reason is functional, not stylistic: `_targets` calls the
shared `scored(grid, rows, data_date, p)` to compute the **real** overhang ranking, and `scored`
branches on `p.signal` — handed `"hash"` it would return a hash order and the allocator would be
matching the churn of a placebo instead of the churn of the book. So `signal` must read `"high"`
here, and `_targets` raises if it does not. The honesty argument the other phases make with the
opposite choice (`side="random"`, `pick="random"`, `picks="placebo"`, `order="hash"` — the
config text must not claim a ranking the allocator never performs) is satisfied differently
here: on this chassis `signal` names *which arm is being shadowed*, and the blind draw is in the
allocator id.

`config_text` (`lab/method.py:44-52`) is

```
rules=<_canon(MONTHLY_HOLD_FRAC_GOTRADE)>
allocator=<M0208>            <- the only line that differs
params=<_canon(OverhangParams(inner=N20, keep=40, signal='high', seed=1, market='SPY'))>
```

- **No recorded digest moves.** `OverhangParams` gains, loses and reorders no field, so `_canon`
  renders it exactly as it did for trials 677–680. Recorded digests, for the record:
  `13d7396048e9…` (CGO-N20), `37badf26e71f…` (CGO-N40), `12d558b814a4…` (CGO-LOW-N20),
  `b9a9daff33d2…` (HASH-N20). All four must be unchanged after this phase.
- **`Method.__post_init__` uniqueness holds.** The id `M0208-CGO-N20-PLC` is not among
  `{M0208-CGO-N20, M0208-CGO-N40, M0208-CGO-LOW-N20, M0208-HASH-N20}`. The configuration differs
  from `CGO-N20`'s on the `allocator=` line (`<M0208-A1>` against `<M0208>`), and from the other
  three on both the `allocator=` and `params=` lines. One differing line changes the sha256.
- **Allocator id uniqueness holds.** `test_allocator_ids_are_unique_across_methods` keys on the
  string; `grep -rn 'id = "M0208' engine/src/seer_engine/` returns exactly one line today.

The amendment is **seq 1**: a read-only query of `method_amendments` on 2026-10-19 returns rows
for `M0030` (seq 1), `M0053` (seq 1) and `M0225` (seq 1) only. M0208 carries none.

---

## The `resolve_target` walk for `M0208-CGO-N20-PLC`

`control_shape.resolve_target` (`:359-385`) with `arms = METHOD.all_candidates()`, which is
`(CGO-N20, CGO-N40, CGO-LOW-N20, HASH-N20, CGO-N20-PLC)`.

1. **`declared`** — `declared_target` reads `getattr(arm, "controls", None)`. No `Candidate` in
   the lab carries that attribute. → fall through.
2. **`_eligible_targets(CGO-N20-PLC, arms)`** drops itself and every arm whose `kind_of` is
   `KIND_PLACEBO` or `KIND_DOSE`:

   | arm | rationale (lowercased, as `kind_of` reads it) | kind | eligible |
   |---|---|---|---|
   | `M0208-CGO-N20` | "20 largest capital-gains overhangs, held while inside the top 40, behind the spy 200-day switch" | `KIND_NONE` | **yes** |
   | `M0208-CGO-N40` | "same signal, 40 names, band 80: does width help a slow, crowded signal?" | `KIND_NONE` | yes |
   | `M0208-CGO-LOW-N20` | "contrast: the 20 largest paper losses in the same frame; the paper says these trail" | `KIND_NONE` | yes |
   | `M0208-HASH-N20` | "**placebo**: the same pool, band, slots and switch in a fixed **hash order**" | `KIND_PLACEBO` | no |
   | `M0208-CGO-N20-PLC` | itself | — | no |

   None of the three eligible rationales contains any of `DOSE_MARKERS`
   (`"dose-response"`, `"dose:"`, `"and not since"`, `"and none since"`,
   `"does the date do any work"`, `"on the date itself"`), any of `DRAW_MARKERS`
   (`"placebo"`, `"hash-drawn"`, `"hash order"`), or `ABLATION_MARKERS`
   (`"within-frame control"`). Checked word for word against `:192-213`.
3. **`sibling-stem`** — `"M0208-CGO-N20-PLC".rsplit("-", 1)[0]` = `"M0208-CGO-N20"`, which is
   `eligible[0].id`. → **returns `("M0208-CGO-N20", RUNG_STEM)`**, the strongest rung after
   `declared`. The `declared-idea` and `first-declared` rungs are never reached.

**And the target is not itself a control.** `M0208-CGO-N20` is the method's own idea arm:
`KIND_NONE`, so it is not excluded by `_eligible_targets`, and it is not a dose arm, so its
ratios are real and not `not-checked`.

**The new arm must not disturb the old one's resolution.** `M0208-HASH-N20`'s stem is
`"M0208-HASH"`, which names no arm; no eligible rationale carries an `IDEA_MARKER`
(`"the idea:"`, `"the yardstick:"`); so it falls to `first-declared` = `eligible[0]` =
`M0208-CGO-N20`, unchanged — `CGO-N20-PLC` is classified `KIND_PLACEBO` by the word "placebo"
in its rationale and is excluded from `_eligible_targets` for every arm. Its arrival moves no
existing finding.

---

## Implementation Steps

### Step 1: Record the pre-run state

**File:** none — a read, written into the phase's notes.
**Change:** before touching anything, capture the database hash and the four recorded rows
read-only, so the close-out has a before picture that no `lab` command has migrated.

```bash
git -C /home/miftah/seer hash-object lab/lab.sqlite
# expected on 2026-10-19: 3969f1fa5d2066a42ed47716dd05a66050073592 (will differ once a
# sibling phase has run; record whatever it is, do not assume)

sqlite3 -header -column "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" "
SELECT t.n, t.candidate_id, t.trades, round(t.turnover,3) AS turnover,
       round(t.exposure,3) AS expo, round(t.max_drawdown,3) AS dd,
       round(t.profit_factor,2) AS pf, substr(t.config_digest,1,12) AS digest,
       round(f.mwr*100,2) AS mwr_pct, round(f.spy_tr_mwr*100,2) AS spy_pct
FROM trials t LEFT JOIN trial_funding f ON f.trial_n = t.n
WHERE t.method_id='M0208' AND t.window='dev' ORDER BY t.n;"
```

Measured 2026-10-19, and the baseline this phase is judged against:

| n | candidate | trades | turnover | expo | dd | pf | digest | mwr % | SPY TR % |
|---|---|---|---|---|---|---|---|---|---|
| 677 | `M0208-CGO-N20` | 624 | 3.061 | 0.699 | 0.249 | 3.13 | `13d7396048e9` | **13.88** | 7.19 |
| 678 | `M0208-CGO-N40` | 952 | 2.439 | 0.684 | 0.208 | 3.08 | `37badf26e71f` | 11.98 | 7.19 |
| 679 | `M0208-CGO-LOW-N20` | 713 | 3.706 | 0.681 | 0.347 | 1.54 | `12d558b814a4` | 8.03 | 7.19 |
| 680 | `M0208-HASH-N20` | 2749 | 15.910 | 0.692 | 0.239 | 1.47 | `b9a9daff33d2` | **8.01** | 7.19 |

The standing margin: **13.88 − 8.01 = +5.87 points a year**, on `trial_funding.mwr`.
The band this phase must hit: trades in `[0.80 × 624, 1.25 × 624] = [499, 780]` and turnover in
`[0.80 × 3.061, 1.25 × 3.061] = [2.449, 3.826]`.

**Impact:** none. A `?mode=ro` URI never migrates the database; the hash must be identical before
and after this step.

---

### Step 2: Widen three import lines

**File:** `engine/src/seer_engine/lab/methods/m0208_capital_gains_overhang.py:56-83`
**Change:** `Sequence` for the new helpers' signatures, `Amendment` for the block, and phase 1's
helper. Nothing is removed and nothing is reordered.

**Code** — the import block becomes, in full:

```python
from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.lab.control_draw import matched_names
from seer_engine.lab.method import Amendment, Method
from seer_engine.sim.book import Target, equal_weight
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.allocator import last_close, target_from_close
from seer_engine.strategies.base import History, as_day
from seer_engine.strategies.f_factor import (
    EXCLUDED,
    FactorParams,
    FactorPrepared,
    FactorRow,
    factor_lookback,
    factor_rows,
    prepare_factor,
    trend_on,
)
```

**Impact:** `config_text` reads rules, allocator id and params only, so no digest moves. The
purity test (`test_method_source_is_pure`) bans the import roots
`psycopg requests yfinance time random logging urllib socket subprocess sqlite3 os` and the
modules `seer_engine.research` / `seer_engine.lab.store`; `seer_engine.lab.control_draw` is none
of them.

---

### Step 3: Add the amendment's paragraph to the module docstring

**File:** `engine/src/seer_engine/lab/methods/m0208_capital_gains_overhang.py:50` (between the
paragraph ending *"…against the lab's recorded real-fee momentum books."* and the
*"Rules are ``monthly-hold-frac-gotrade``…"* line at `:52`)
**Change:** insert one paragraph. Prose docstrings that say *why* are the house style
(`CLAUDE.md`, Conventions) and M0225's file does the same for its own amendment.

**Code:**

```
Amendment 1 (2026-10-19). ``HASH-N20`` above is the placebo this method quoted its margin
against, and it is mis-shaped: it trades 4.41 times and turns over 5.20 times ``CGO-N20``, the
widest miss of the fourteen D17 refuses. The cause is in ``draw`` below -- M0187's hash is re-keyed
on the decision's month, so the placebo's whole ordering is independent from one month to the
next, while the overhang score it stands in for moves by four weekly blocks out of 260 and
scarcely changes. The ``keep`` band is then hysteresis for the real book and a one-in-ten lottery
for the placebo, and the placebo rebuilds itself every month. ``CGO-N20-PLC`` replaces it with the
same pool, the same twenty 1/20 slots, the same band and the same switch, drawing each month only
as many fresh names as ``CGO-N20``'s own banded selection replaced that month
(``lab.control_draw``). Nothing above this paragraph changes: ``HASH-N20``'s trial is recorded and
stays exactly as it was measured.
```

**Impact:** the file's sha256 moves, which is what an amendment is allowed to do and what
`runner.record(amend=True)` appends to `method_amendments`. No digest moves.

---

### Step 4: Insert the amendment section

**File:** `engine/src/seer_engine/lab/methods/m0208_capital_gains_overhang.py` — after `_v`
(ends at `:361`) and before `METHOD = Method(` (`:364`).
**Change:** the complete new section. Everything in it is new code; nothing above `:361` is
edited.

**Code:**

```python
# ------------------------------------------------------------- amendment 1: the matched draw
#
# Why a copy of the band and not a refactor of ``choose``. ``choose`` above is the rule four
# recorded trials (677-680) ran under. Its body is outside ``config_digest`` -- a digest is rules,
# allocator id and params -- so Python would let it be refactored and nothing would complain, and
# that is exactly the trap: a recorded arm's behaviour would have moved because a later amendment
# wanted to share its lines. The band is therefore written out again here, used only by the
# matched draw, and ``choose`` is left byte-identical.

A1_ADDED = date(2026, 10, 19)


def _banded_picks(order: Sequence[str], held: AbstractSet[str], top: int, keep: int) -> list[str]:
    """``choose``'s band as a plain symbol list: who the real book would hold, given ``held``.

    Identical rule, written out rather than shared (see the note above): a held name ranked inside
    ``keep`` stays, in rank order, at most ``top`` of them, and the free slots are filled from the
    top of ``order``. A name ``order`` does not score is not held (``rank.get(s, keep)``).
    """
    rank = {s: i for i, s in enumerate(order)}
    kept = sorted((s for s in held if rank.get(s, keep) < keep), key=lambda s: rank[s])
    picks = kept[:top]
    for s in order:
        if len(picks) >= top:
            break
        if s not in picks:
            picks.append(s)
    return picks


def _book(history: Mapping[str, History], rows: list[FactorRow], picks: Sequence[str],
          data_date: date, p: OverhangParams) -> tuple[Target, ...]:
    """``choose``'s tail for an already-chosen list: 1/``top`` each, the remainder in the market.

    The same slots, the same SPY fill and the same unfilled-slot behaviour as the arm this draw
    controls, so the only thing that differs between the two books is which names are in them.
    """
    close = {r.symbol: r.close for r in rows}
    w = equal_weight(p.inner.top)
    out: list[Target] = []
    for s in picks:
        c = close.get(s)
        if c is None:
            continue
        t = target_from_close(s, c, w)
        if t is not None:
            out.append(t)
    rest = Decimal(1) - w * len(out)
    mh = history.get(p.market)
    if rest > 0 and mh is not None and mh.index_of(data_date) is not None:
        t = target_from_close(p.market, last_close(mh, data_date), rest)
        if t is not None:
            out.append(t)
    return tuple(out)


def previous_month_end(grid: WeekGrid, data_date: date) -> date | None:
    """The last session before ``data_date``'s calendar month, on the market symbol's calendar.

    A monthly rank session is the first NYSE session of a calendar month (``sim.rules._first_of``)
    and the allocator is handed the session before it, so on this chassis every decision's
    ``data_date`` is a month's last session and the previous decision's is the last session of the
    month before. Derived from the calendar rather than stepped back a fixed 21 sessions, so a
    short month and a holiday both land right.

    Only columns strictly before the first of ``data_date``'s month are read, so the answer is the
    same on a history cut at ``data_date`` as on the whole history (the P4 identity), and it can
    see nothing ``data_date`` could not. None before the calendar starts.
    """
    first = np.datetime64(date(data_date.year, data_date.month, 1))
    i = int(np.searchsorted(grid.dates, first, side="left")) - 1
    if i < 0:
        return None
    out = grid.dates[i].astype(object)  # datetime64[D] -> datetime.date
    return out if isinstance(out, date) else None


class MatchedDrawAllocator(OverhangAllocator):
    """``CGO-N20``'s shape with none of its identity: the honest placebo (D17, 2026-10-19).

    Everything but the names is the arm it controls, and it inherits that literally:
    ``OverhangAllocator``'s own ``lookback``, ``symbols``, ``holds``, ``uses_members``, ``prepare``
    and both target entry points, so the screen, the SPY 200-day switch, the weekly grid and the
    SPY-remainder fill are the same code and not a re-implementation of it. Only ``_targets``
    differs, and only in which twenty names come out.

    The draw, each decision session:

        * the pool is ``scored``'s -- the screened members with an overhang value on ``data_date``,
          exactly the pool ``CGO-N20`` picks from;
        * ``picks_prev`` is the real signal's plain top ``top`` at the previous decision session
          (``previous_month_end``), and ``picks_real`` is the real band applied to it, so
          ``len(set(picks_real) - set(picks_prev))`` is how many names ``CGO-N20``'s own hysteresis
          lets through this month. One step of the band unrolled: enough to carry the hysteresis,
          and it needs no record of what the real book actually held, which no allocator has;
        * ``control_draw.matched_names`` keeps that many fewer of its own ``held`` names in a
          date-free hash order and draws the rest blind in a month-keyed one, taking names it
          does not hold ahead of the ones it is dropping so a just-released name is not
          immediately taken back.

    The pool goes to the helper in **symbol** order, never in score order, so no part of the real
    ranking can reach the draw through a tie-break.

    Membership is ``data_date``'s at both dates: ``rows`` is read once, at ``data_date``, and used
    for the previous session's score too. Deliberate, and it looks ahead at nothing -- today's
    member list is known today. It means the entry count measures the *signal's* churn and not the
    index's, which is the right thing, because the control draws from today's pool either way.

    ``signal`` must be ``"high"``: this arm shadows the paper's long side, and the params say which
    arm it shadows. A ``"hash"`` or ``"low"`` params value would be a placebo of a placebo or of
    the contrast, which is not what was pre-registered.
    """

    id = "M0208-A1"

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
        sc = scored(grid, rows, data_date, p)
        if not sc:
            return _book(history, rows, (), data_date, p)
        order = sorted(sc, key=lambda s: (-sc[s], s))
        picks_prev: tuple[str, ...] = ()
        before_date = previous_month_end(grid, data_date)
        if before_date is not None:
            before = scored(grid, rows, before_date, p)
            picks_prev = tuple(sorted(before, key=lambda s: (-before[s], s))[: p.inner.top])
        picks_real = _banded_picks(order, frozenset(picks_prev), p.inner.top, p.keep)
        drawn = matched_names(
            pool=tuple(sorted(sc)),
            held=held,
            real_now=picks_real,
            real_prev=picks_prev,
            tag="M0208",
            seed=p.seed,
            data_date=data_date,
        )
        return _book(history, rows, drawn, data_date, p)


MATCHED = MatchedDrawAllocator()


def _a1(suffix: str, params: OverhangParams, rationale: str,
        supersedes: tuple[str, ...]) -> Candidate:
    """An amendment candidate, with the declaration of which recorded arm it replaces.

    ``supersedes`` is what D17 reads (``control_shape.SUPERSEDES_ATTR``): declared, never
    inferred from the target, and outside ``config_digest`` because ``config_text`` names its
    three attributes by hand. An arm that declares nothing retires nothing, so omitting it would
    leave M0208 blocked on HASH-N20 after the measurement had been taken."""
    return Candidate(id=f"M0208-{suffix}", family="M0208", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=MATCHED, params=params, rationale=rationale, added=A1_ADDED,
                     owner_inputs=(), supersedes=supersedes)


MATCHED_DRAW = Amendment(
    added=A1_ADDED,
    why=(
        "HASH-N20 trades 4.41 times and turns over 5.20 times the book it controls, so the margin "
        "quoted against it is not evidence; draw the same book blind at CGO-N20's own monthly "
        "entry count instead"
    ),
    hypothesis=(
        "Written before the run, and before any result for this arm was seen. The standing "
        "sentence about this method is that CGO-N20 beats its placebo by +5.87 points a year on "
        "the owner's deposits -- 13.88% against HASH-N20's 8.01%, where SPY TR on the same "
        "deposits earned 7.19% -- and the method's own success condition asks for at least 2 "
        "points. That margin was quoted against an opponent carrying a different fee bill: "
        "HASH-N20's hash order is re-keyed every month, so its whole book is redrawn at each "
        "decision while the overhang ranking it stands in for scarcely moves, and it recorded "
        "2749 trades and 15.910 turnover against 624 and 3.061. CGO-N20-PLC is the same pool, the "
        "same twenty 1/20 slots, the same keep-40 band and the same SPY 200-day switch, drawing "
        "each month only as many fresh names as CGO-N20's own band let through. Predicted "
        "direction, which is the whole point of writing this first: the honest placebo trades "
        "about a quarter as often, pays about a quarter of the fees, holds its names long enough "
        "to collect the market's own drift, and therefore EARNS MORE. Its money return rises from "
        "8.01% to somewhere in 10-13% a year and the +5.87 point margin NARROWS to under 3 "
        "points -- below the 2-point bar this method set itself as often as not. A reversal, the "
        "blind draw beating CGO-N20 outright, is an admissible outcome of this prediction and "
        "would say the overhang adds nothing to a twenty-name equal-slot book behind the SPY "
        "switch. Whatever the number is, it is reported and the arm is not drawn again: this is "
        "one re-draw of one book, and a second one would only ever be justified by the shape "
        "missing its band, never by the margin coming out wrong."
    ),
    expected_failure=(
        "The way this prediction is wrong, stated so it can be recognised: CGO-N20-PLC lands near "
        "8% again and the margin stays above 5 points. That would mean the overhang signal "
        "carries the whole gap and the fee bill was a side-show -- that HASH-N20's five times "
        "turnover was costing it almost nothing a quarter-speed draw recovers, and the "
        "handicap was cosmetic rather than real. The second way to fail is on shape rather than "
        "on money: CGO-N20's churn is read through one unrolled step of its own band, with the "
        "previous month's plain top twenty standing in for what the real book actually held, and "
        "if the real hysteresis is stronger than that unroll says, the new arm lands above 1.25x "
        "on trades and the match is not clean. The band is also weaker early in the window, when "
        "the pool is small and 156 weeks of history exclude many members, so the first years may "
        "churn harder than the last. A shape miss is reported as a shape miss and the quoted "
        "margin stays provisional; it is not a reason to try another seed."
    ),
    candidates=(
        _a1("CGO-N20-PLC", OverhangParams(N20, keep=40),
            "Placebo for CGO-N20: the same pool, slots, band and switch, filled in a hash order "
            "at the real book's own monthly entry count",
            supersedes=("M0208-HASH-N20",)),
    ),
)
```

**Impact:**
- The rationale carries `"placebo"` and `"hash order"` (both `DRAW_MARKERS`) and none of
  `DOSE_MARKERS` — checked phrase by phrase against `control_shape.py:192-213`. `kind_of` returns
  `KIND_PLACEBO`, so the arm **is** shape-checked. Invariant 3 holds and the check is not gamed.
- `N20` is reused; `OverhangParams(N20, keep=40)` is the same value `CGO-N20` runs on, so the
  params line of `config_text` is identical and the digest differs on the allocator line alone.
- `previous_month_end` is module-level and public-looking because phase 8's close-out may want to
  cite it; nothing outside this file imports it.

---

### Step 5: Hang the amendment on `METHOD`

**File:** `engine/src/seer_engine/lab/methods/m0208_capital_gains_overhang.py:421-427` (the tail
of the `METHOD = Method(` call)
**Change:** one new keyword argument between `candidates=` and `seen_keys=`. Nothing inside
`candidates=` is touched.

**Code** — the tail of the call becomes:

```python
    candidates=(
        _v("CGO-N20", OverhangParams(N20, keep=40),
           "20 largest capital-gains overhangs, held while inside the top 40, behind the SPY "
           "200-day switch"),
        _v("CGO-N40", OverhangParams(N40, keep=80),
           "Same signal, 40 names, band 80: does width help a slow, crowded signal?"),
        _v("CGO-LOW-N20", OverhangParams(N20, keep=40, signal="low"),
           "Contrast: the 20 largest paper losses in the same frame; the paper says these trail"),
        _v("HASH-N20", OverhangParams(N20, keep=40, signal="hash"),
           "Placebo: the same pool, band, slots and switch in a fixed hash order"),
    ),
    amendments=(MATCHED_DRAW,),
    seen_keys=(
        "concept:capital-gains-overhang",
        "concept:disposition-effect",
        "concept:turnover-weighted-reference-price",
    ),
)
```

**Impact:** `all_candidates()` now returns five arms; `Method.__post_init__` validates the new id
and digest against the four originals at import. If it raises, the configuration collided and the
phase stops before anything is committed.

---

### Step 6: Prove the tree is green, then commit — the commit is the pre-registration

**File:** none (verification + git).
**Change:** run the suite, then commit **only** this one file, by pathspec. Invariant 9: the
checkout is shared with up to four concurrent phases, so no `git add -A`, no `git reset --hard`,
no `git pull --rebase`.

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
export PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
PY=/home/miftah/seer/engine/.venv/bin/python

$PY -m ruff check engine
$PY -m pytest engine/tests/test_lab_methods.py -n0 -q
$PY -m pytest engine/tests -q
```

`test_lab_methods.py` must be green **before** the run as well as after: it reads the *committed*
lab database and its sha check falls back to `runner.pending_amendment`, so a committed-but-unrun
`Amendment` keeps it green (analysis, *Concurrency facts*). The three checks that matter here:

- `test_every_recorded_configuration_still_digests_to_its_recorded_digest` — the four recorded
  M0208 digests are unmoved;
- `test_allocator_ids_are_unique_across_methods` — `M0208-A1` is free;
- `test_allocator_contract` / `test_candidate_runs_a_smoke_window` for `M0208-CGO-N20-PLC`.

Then:

```bash
git -C /home/miftah/.worktrees/seer/honest-control-redraw status --porcelain -- \
  engine/src/seer_engine/lab/methods/m0208_capital_gains_overhang.py

git -C /home/miftah/.worktrees/seer/honest-control-redraw add \
  engine/src/seer_engine/lab/methods/m0208_capital_gains_overhang.py

git -C /home/miftah/.worktrees/seer/honest-control-redraw commit \
  -m "lab: M0208 amendment 1 pre-registered -- an honest placebo for CGO-N20

HASH-N20 trades 4.41x and turns over 5.20x the arm it controls, the widest
shape miss D17 refuses, and the +5.87 point margin quoted against it is not
evidence. CGO-N20-PLC is the same pool, slots, band and switch, drawn blind
at CGO-N20's own monthly entry count (lab.control_draw, phase 1).

No recorded config_digest moves: OverhangParams is untouched and the new arm
is a new allocator id (M0208-A1) over the identical params value.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>" \
  -- engine/src/seer_engine/lab/methods/m0208_capital_gains_overhang.py

git -C /home/miftah/.worktrees/seer/honest-control-redraw status --porcelain -- \
  engine/src/seer_engine/lab/methods/m0208_capital_gains_overhang.py   # must print nothing
```

**Impact:** `runner.preflight(amend=True)` calls `registry_problem(path)`, which runs
`git status --porcelain -- <basename>` and `git ls-files --error-unmatch` with
`cwd=path.parent` — that is, inside the worktree's `lab/methods/` directory, checking **this one
file only**. It must come back clean, and a sibling phase's dirty method file does not block it.
Nothing is pushed here; phase 8 owns the push.

---

### Step 7: Run the amendment

**File:** none.
**Change:** one `lab run --amend` on the dev window. `lab test` is never invoked and
`SEER_RESEARCH_TEST_STORE` is never set.

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
export SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite
export SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research
export PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src
PY=/home/miftah/seer/engine/.venv/bin/python
LOG=/tmp/claude-1000/-home-miftah-seer/phase6-m0208-run.log

git -C /home/miftah/seer hash-object lab/lab.sqlite          # BEFORE -- write it down

$PY -m seer_engine -v lab run M0208 --amend > "$LOG" 2>&1
echo "exit=$?"                                                # the real status, not a pipe's

git -C /home/miftah/seer hash-object lab/lab.sqlite          # AFTER -- write it down
tail -60 "$LOG"
```

Rules that bind this step:

- **Never judge the command by a piped exit code.** A redirect preserves the status; `| tee`,
  `| grep` and `| tail` do not (memory `seer-lab-note-double-append-from-grep-exit-code`). The
  `echo "exit=$?"` on its own line is the status.
- Exit 0 means it ran; **2 means the lab refused the request** (dirty file, a configuration that
  already ran, a closed status, a test trial); 1 means an error. A 2 is read and obeyed, never
  worked around.
- `SEER_RESEARCH_STORE` points at the **main checkout's** store. Worktrees have none and a rebuild
  is 30 minutes for nothing (memory `seer-research-store-not-in-worktrees`). Never rebuild.
- The database hash changes here, and that is expected: `lab run` migrates on connect and then
  writes `trials`, `trial_funding` and one `method_amendments` row under `BEGIN IMMEDIATE`. Do not
  restore it by path afterwards — the write is the product of this phase.
- The status of M0208 is **not** moved by an amendment; the run prints it unchanged. That is
  correct and is not a failure.
- `lab stage` is **not** run (invariant 8). The snapshot test being red mid-batch is by design.

**Impact:** one new row each in `trials`, `trial_funding`, `trial_provenance` and
`method_amendments` (M0208 seq 1). The luck gate's N does not move: the N policy counts methods,
not rows, and M0208 is already counted (memory `seer-lab-n-policy-overcounts-looks`).

---

### Step 8: Read the shape, read the money, and decide whether to stop

**File:** none.
**Change:** `lab control M0208` for the official reading, plus a read-only cross-check so the
numbers in the handover are derived twice.

```bash
git -C /home/miftah/seer hash-object lab/lab.sqlite          # BEFORE lab control
$PY -m seer_engine lab control M0208 > /tmp/claude-1000/-home-miftah-seer/phase6-control.log 2>&1
echo "exit=$?"
git -C /home/miftah/seer hash-object lab/lab.sqlite          # AFTER
cat /tmp/claude-1000/-home-miftah-seer/phase6-control.log

sqlite3 -header -column "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" "
WITH a AS (SELECT trades, turnover FROM trials
           WHERE window='dev' AND candidate_id='M0208-CGO-N20')
SELECT t.candidate_id,
       t.trades,
       round(t.trades * 1.0 / (SELECT trades FROM a), 3)      AS trades_x,
       round(t.turnover, 3)                                   AS turnover,
       round(t.turnover / (SELECT turnover FROM a), 3)        AS turnover_x,
       round(t.exposure, 3)                                   AS expo,
       round(f.mwr * 100, 2)                                  AS mwr_pct,
       round((SELECT f2.mwr FROM trial_funding f2
              JOIN trials t2 ON t2.n = f2.trial_n
              WHERE t2.candidate_id='M0208-CGO-N20') * 100 - f.mwr * 100, 2) AS margin_pts
FROM trials t JOIN trial_funding f ON f.trial_n = t.n
WHERE t.window='dev' AND t.method_id='M0208' ORDER BY t.n;"
```

**Impact:** `lab control` is a `lab` command, so it migrates on connect and the hash may move even
though it writes no row. Record both hashes and say so; do not try to restore the file.

**The decision, and it is written before the number is seen:**

| what `lab control M0208` says about `M0208-CGO-N20-PLC` | what this phase does |
|---|---|
| `ok` on both axes (trades and turnover both in `[0.80, 1.25]`) | record the margin, hand to phase 8, done |
| `warn` or `refuse` on either axis | **record the measured ratios and STOP.** Write the miss into this plan file and into the phase's report. Do **not** change the seed, the keep order, the unroll depth or anything else and run again. One re-draw per book (invariant 4). A second attempt, if the set ever wants one, is a new rule in phase 1's `control_draw.py` applied to every method at once, never a tuned arm here |
| the margin collapses to nothing, or goes negative | **that is the finding.** Report it in exactly those words. `M0208`'s own success condition says "beats the placebo by at least 2 points a year", and a book that no longer clears it has been disproved by its own pre-registered bar. Re-drawing until a margin survives is design §4's prohibition and invariant 4's; the +5.87 points reading was the handicapped one, and the honest number replaces it whatever it is |

---

## Verification

**Build:** `/home/miftah/seer/engine/.venv/bin/python -m ruff check engine`
(CI lint is E9 and F minus F401.)

**Tests:**
```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  /home/miftah/seer/engine/.venv/bin/pytest engine/tests -q
```
`PYTHONPATH` is not optional: without it pytest silently tests the main checkout instead of the
branch (memory `seer-worktree-tests-need-pythonpath`). The suite runs under xdist by default;
`-n0` only for the lab-methods module when a failure needs reading.

**Manual check — and the honest limit on what the smoke fixture can prove.**
`labkit.SMOKE_FIRST = date(2013, 12, 2)` gives the fixture **473 NYSE sessions** through
`DEV_END`. `overhangs` needs `(j + 1) // 5 >= MIN_WEEKS` — 780 sessions — so on the fixture
`scored` returns `{}` for every probe, `sc` is empty, and `_targets` falls straight to
`_book(history, rows, (), …)`, which puts the whole book in SPY. That is already true of all four
recorded M0208 arms and is why they pass `test_allocator_contract`'s `nonempty > 0`; the new arm
takes the same path and passes the same way.

So **the smoke tests prove the new allocator does not crash, does not look ahead and satisfies the
P4 identity — they do not exercise the matched draw at all.** The entry-count match is proven
session by session in phase 1's `engine/tests/test_lab_control_draw.py`, against the helper; on
M0208 the only evidence the shape matched is the `lab control M0208` reading after the run. Say
this out loud in the phase report rather than implying the green suite checked the draw.

Three things to read by hand in the run log:
1. the run's own control-shape print (`commands/lab.py:1751-1798`) — it refuses nothing (D15), but
   it is the first sight of the ratio;
2. the amendment block print (`:1799-1811`) — seq **1**, status printed as unchanged;
3. the trial's `trades` and `turnover`, against `[499, 780]` and `[2.449, 3.826]`.

**Exit criteria:**
- `m0208_capital_gains_overhang.py` is committed before `lab run --amend` and clean after it.
- One new dev trial exists for `M0208-CGO-N20-PLC`; `method_amendments` holds `('M0208', 1)`.
- The four recorded digests `13d7396048e9… / 37badf26e71f… / 12d558b814a4… / b9a9daff33d2…` are
  unchanged and `test_every_recorded_configuration_still_digests_to_its_recorded_digest` is green.
- `lab control M0208` resolves `M0208-CGO-N20-PLC` to `M0208-CGO-N20` on the **`sibling-stem`**
  rung and reports it **`ok`** on both axes — or the phase has stopped and said why.
- The margin is re-stated in `trial_funding.mwr` and compared to the pre-registered direction.
- `M0208-HASH-N20`'s row, rationale, params and verdict are untouched; D17 still refuses M0208
  (phase 2's job, not this one's).
- `pytest engine/tests` and `ruff check engine` green.
- The test-window look count is still 4. `lab test` was not invoked.

---

## What to record for phase 8

A block in exactly this shape, so the close-out's table can be assembled without re-deriving it:

```
M0208 -- capital-gains overhang, CGO-N20

  book            M0208-CGO-N20        trial 677   624 trades   3.061 turnover   13.88% mwr
  old control     M0208-HASH-N20       trial 680  2749 trades  15.910 turnover    8.01% mwr
                  shape 4.41x trades / 5.20x turnover  -> REFUSE
                  old margin  +5.87 pts/yr
  new control     M0208-CGO-N20-PLC    trial ___  ____ trades  ______ turnover   _____% mwr
                  shape ____x trades / ____x turnover  -> ok | warn | refuse
                  new margin  _____ pts/yr        (SPY TR on the same deposits: 7.19%/yr)

  verdict sentence: M0208's own bar is "beats the placebo by at least 2 points a year".
                    It [does | does not] survive its honest control.
  pre-registered direction: the margin NARROWS. Outcome: [narrowed | held | reversed].
  lab.sqlite git hash-object  before: ____________________  after: ____________________
```

Both the shape numbers and the money numbers must be inside `WARN_BAND` **on both axes** for the
arm to count as clean — `[0.80, 1.25]`, not merely inside D17's `[0.50, 2.00]` refuse band.

Money is `trial_funding.mwr` and nothing else: never `total_return`, never `cagr`. These books are
funded with the owner's monthly top-up and the curve-shape columns count his deposits as gains
(invariant 5, memory `seer-funded-book-cagr-is-a-lie`).

---

## Handoffs

- **Phase 2 — D17 supersession (R4).** This phase does not unblock `lab promote M0208`.
  `mis_shaped_controls` returns every recorded arm outside the band and `M0208-HASH-N20`'s row is
  append-only and permanent, so D17 will still refuse M0208 after this phase lands. The
  supersession rule — a refused arm is excused when a band-clean placebo **declares** it — is
  phase 2's and only phase 2's. `M0208-CGO-N20-PLC` is deliberately built to be the arm that
  supersedes `M0208-HASH-N20`: classified `KIND_PLACEBO`, inside the match band, and carrying
  `supersedes=("M0208-HASH-N20",)`. (It also happens to resolve to the same `target_id`,
  `M0208-CGO-N20`, which on this method is true but is **not** what the rule reads — on M0047 and
  M0202 the targets deliberately differ, which is why the rule is a declaration.)
- **Phase 8 — the close-out (R3, R4).** The block above, written to
  `.workflows/plan/honest-control-redraw/phase-6-results.md` and committed by pathspec — that is
  the set's one results-file convention (`phase-N-results.md`, N in 1..7) and the only place
  Phase 8 collects this phase's numbers from. Phase 8 also owns the `lab insight` rows, the
  `lab control` sweep over all nine, the single `lab stage`, the merge and the push. This phase
  writes no handover document and stages nothing.
- **Phase 1 — the rule.** Reconciled: the call is `control_draw.matched_names(...)`, keyword-only,
  at the one site in `MatchedDrawAllocator._targets`. Nothing else in this phase depends on the
  helper's shape.
- **This chassis is one of the six where the turnover axis is NOT the risk**, and that is worth
  stating because three of the nine are. `choose` gives every pick `equal_weight(p.inner.top)` =
  1/20 and puts the remainder in SPY, identically for the real arm and for this one, so equal
  slots of the same count move the same fraction of the book per name and the turnover ratio
  follows the trade ratio arithmetically. The weight-vector risk Phase 3 measured on
  `M0221-E50` (C50's exact names, C50's exact 360 trades, 1.60x turnover) lives on the
  weight-varying chassis — M0221/M0225, M0047 and M0201 — and not here. Index invariant 12 is
  the set-wide policy either way: names and churn only, and a turnover miss is a recorded STOP.
- **Not done, deliberately, and not this phase's to do:**
  - `M0208`'s `hypothesis` still contains the sentence "beats the placebo by at least 2 points a
    year", which after this phase may be measured against two different placebos. It is frozen
    pre-registration prose and stays. If the lab wants the standing sentence corrected, that is a
    `lab insight`, which is phase 8's.
  - `m0208.draw` is a local copy of `m0187.draw` (`:235-238`) rather than an import, unlike
    M0243 which imports it. Harmless duplication, noticed while reading; de-duplicating it would
    change no digest but would touch frozen signal code for no measurement. Left alone.
  - `choose` and `_banded_picks` now hold the same band in two places. Deliberate — see the
    comment at the head of the amendment section — and it must stay that way while trials 677-680
    are on the books.
  - The lab's **other** mis-shaped arms on other methods. Phases 3, 4, 5, 7.

---

## Rollback

**Before `lab run --amend` (step 7):** fully reversible.

```bash
git -C /home/miftah/.worktrees/seer/honest-control-redraw revert --no-edit <the step-6 commit>
```

The `Amendment` block is pre-registration and nothing else until the run executes; the database
has not been touched.

**After `lab run --amend`:** **not reversible, by design.** `trials`, `trial_funding` and
`method_amendments` all carry append-only triggers on update *and* delete. The recorded trial for
`M0208-CGO-N20-PLC` is permanent, and the `Amendment` block must therefore stay in the file
forever — `store.latest_source_sha` reads the newest `method_amendments` row, so removing the
block would break `test_lab_methods.py`'s sha check for M0208 immediately.

The correct rollback after the run is a journalled `lab insight` saying the arm was run and what
it showed, written by phase 8. This is precisely why invariant 2 puts the whole pre-registration —
`why`, `hypothesis` and `expected_failure`, including the predicted direction — in the commit that
precedes the run.

**Never:** `git reset --hard`, `git pull --rebase` or `git checkout --` across this shared
worktree while sibling phases are running; a rebase replays a stale `lab.sqlite` over the live one
the other phases are writing (memory `seer-rebase-replays-stale-lab-sqlite`).
