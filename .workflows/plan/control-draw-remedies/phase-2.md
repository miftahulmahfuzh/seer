# Phase 2: The shadow rule, written beside v1

**Plan set:** `CONTROL_DRAW_REMEDIES_PLAN.md`
**Analysis:** `docs/analyzer/20261020-113306-C7K4_code_analyzer.md`
**Satisfies:** R1 (carry a shadow of the real held set across decisions, applied to every chassis
at once and never to one file), R4 (recorded trials and closed records frozen; no test-window look)
**Depends on:** Phase 1
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab`

---

## Goal

`lab.control_draw` grows a second, pure path — a bounded backward replay that reconstructs the
controlled arm's held set at the previous decision instead of substituting a freshly-derived
top-N — written **beside** the shipped rule, which keeps its body byte for byte. After this phase
the module can draw a control at any replay depth a chassis can afford, with the depth budget
enforced at call time rather than discovered in a test; and the shipped v1 path is pinned by a
golden-vector test, so an in-place edit to it goes red where today **nothing in this repository
would catch one**.

This phase writes no method file, records no trial, opens no database and runs no backtest.

---

## The one thing this phase must not get wrong

A `config_digest` is the rules, the allocator id and `dataclasses.fields()` of the params
(`backtest/registry.py:302-334`, `candidate_text` at `:337-347`). **A module body is in none of
them.** So an in-place edit to `control_draw.matched_names`, `matched_partition`, `keep_key` or
`entry_key` would move the behaviour of all thirteen recorded matched-draw arms (lab trials
841-853) while every existing test stayed green — including
`test_lab_methods.test_every_recorded_configuration_still_digests_to_its_recorded_digest`.
`m0208_capital_gains_overhang.py:366-372` names this same trap in the comment above
`_banded_picks` and answers it by copying `choose`'s band rather than sharing it.

**Measured on this tree, 2026-10-20, so that is a fact and not a worry.** Appending one `|`
character to `keep_key`'s hash input moves the keep order of a fixed input from
`['KO', 'CAT', 'AAPL']` to `['DIS', 'KO', 'CAT']` — a different book for every recorded arm — and
then:

```
$ PYTHONPATH=engine/src engine/.venv/bin/python -m pytest \
    engine/tests/test_lab_control_draw.py engine/tests/test_lab_control_draw_twins.py -n0 -q
34 passed in 1.48s
$ PYTHONPATH=engine/src engine/.venv/bin/python -m pytest \
    engine/tests/test_lab_methods.py -k digests -n0 -q
1 passed, 1758 deselected in 1.31s
```

Thirty-five green tests over a change that silently rewrites thirteen recorded arms. **Step 3 is
the test that closes that hole, and it is the single most valuable thing this phase delivers.**

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Phases 3 and 5 code against
exactly this and nothing else.

**Deletes:** nothing. Not one line is removed from `control_draw.py` except the single docstring
line step 1(b) replaces.

**Renames:** nothing. In particular `RULE_ID` is **not** bumped to `"matched-draw-v2"` — thirteen
recorded arms carry `"matched-draw-v1"`, and the constant's own docstring
(`control_draw.py:87-90`) says a bump "belongs with a new arm, never with an edit". v2 is a
**second** constant beside it.

**This table is the one set of v2 names in the whole plan set.** Phases 3 and 5 code against
these spellings verbatim and introduce no sibling of their own: an earlier draft of phase 3 assumed
`shadow_held(*, dates, step, start)` and `lookback_for_replay(inner, steps)`, and those names are
**withdrawn** — `shadow_selection` and `shadow_lookback_for` are what exist. Phase 2 owns this file
and therefore owns these names (reconciliation, 2026-10-20).

**Creates** — all in `engine/src/seer_engine/lab/control_draw.py`, appended after line 308:

| Symbol | Signature |
|---|---|
| `SHADOW_RULE_ID` | `str = "matched-draw-v2"` |
| `FIXTURE_BARS` | `int = 473` — the absolute lookback ceiling (`labkit.smoke_market`'s session count) |
| `Replay` | `Callable[[date, AbstractSet[str]], tuple[Sequence[str], Sequence[str]]]` |
| `ShadowReading` | `NamedTuple(pool: list[str], real_now: list[str], real_prev: list[str])` |
| `max_shadow_depth` | `(inner: int) -> int` |
| `shadow_lookback_for` | `(inner: int, depth: int) -> int` |
| `shadow_decision_dates` | `(data_date: date, depth: int, cadence: str = "monthly") -> list[date]` |
| `shadow_selection` | `(replay: Replay, data_date: date, *, depth: int, cadence: str = "monthly") -> ShadowReading` |
| `shadow_book` | `(replay: Replay, data_date: date, held: AbstractSet[str], *, tag: str, seed: int, depth: int, cadence: str = "monthly") -> list[str]` |

Plus one import line (`from typing import NamedTuple`) and one new test module,
`engine/tests/test_lab_control_draw_shadow.py`.

**Signature changes:** none. No existing signature moves.

**Requires (from earlier phases):** Phase 1's `## Contract for phase 2` YAML block in
`.workflows/plan/control-draw-remedies/phase-1-results.md`. This phase consumes exactly three keys
from it — see *The K contract* below — and `stop: false`.

**Leaves alone (owned by others):**
- every file under `engine/src/seer_engine/lab/methods/` — phases 3 and 5
- `engine/src/seer_engine/lab/control_weight.py`, `engine/tests/test_lab_control_weight.py` — phase 5
- `lab/lab.sqlite`, `web/data/lab.json` — phases 3, 5, 6
- `engine/tests/test_lab_control_draw_twins.py` — phase 5 extends it; this phase does not open it
- the **bodies** of `matched_names`, `matched_partition`, `matched_book`, `keep_key`, `entry_key`,
  `churn`, `previous_decision_date` and `lookback_for` (invariant I3)
- **the membership convention, which is a SECOND and independent defect and is not R1's.** Every
  method file reads *today's* member list at the earlier date. Phase 1 prices it on its own — it is
  exactly the `(b) SHIPPED` minus `(c) K=1` gap, measured at **0.034 on M0047** in validation
  (shipped 0.966 against an exactly-1.000 K=1) — and **no replay depth closes it**, because the
  replay reads the same member list the shipped rule does. **This phase does not attempt it**, adds
  no historical-membership path and takes no `members` argument anywhere in the v2 block. It is
  carried to phase 6's leftovers as its own new item.

---

## The K contract — what phase 1 hands forward and how it is wired

**This phase hardcodes no K anywhere.** `depth` is a required keyword-only argument on both
`shadow_selection` and `shadow_book`, with **no default**: how far back a chassis's band has to be
rolled before its shadow stops moving is a property of that band and that ranking, and a default
would be a guess wearing a constant's clothes.

**Phase 1 hands forward** the YAML block it defines under `## Contract for phase 2` in
`phase-1-results.md`. **This phase consumes exactly three keys from it:**

| key | what this phase does with it |
|---|---|
| `shadow_needed` | which chassis get a v2 adapter at all (phase 3 writes the adapters; a chassis absent from this list gets none) |
| `lookback_after` | the number each new allocator's `lookback` must return, asserted `<= 473` |

**`k_proposed` is deliberately NOT in that list.** Phase 1 proposes a K, **phase 3 verifies it on
its own probe and uses its own number**, and this phase is indifferent to both: `depth` is a
required keyword-only argument with no default on `shadow_selection` and `shadow_book`, so no K is
ever baked here. The two may legitimately differ — phase 3's probe closes the SPY 200-day switch
inside the replay while phase 1's `(b) SHIPPED` column reproduces amendment 1's unguarded reading —
and the chain is: **phase 1 proposes → phase 3 verifies and ships its own → phase 2 only ever sees
a parameter.**

It reads `stop` as a precondition: **`stop: true` means this phase does not run as designed** and
the coordinator is told so rather than a shallower K being invented here.

**Wire the chosen depth as** a module-level `int` constant in the **method file** that owns the
arm — phase 3 writes `SHADOW_DEPTH = <K>` in `m0208_capital_gains_overhang.py`, and
**`SHADOW_DEPTH` is the one spelling the set uses** (an earlier draft of phase 3 called it
`REPLAY_STEPS`; that name is withdrawn). It is read in exactly two places in that file:

```python
SHADOW_DEPTH = <phase 3's own verified K>   # a constant in the METHOD file, never in control_draw

class ShadowDrawAllocator(OverhangAllocator):
    id = "M0208-A2"

    def lookback(self, params: Any) -> int:
        return shadow_lookback_for(factor_lookback(_check(params).inner), SHADOW_DEPTH)

    def _targets(self, ...):
        ...
        reading = shadow_selection(replay, data_date, depth=SHADOW_DEPTH)
        drawn = matched_names(pool=reading.pool, held=held, real_now=reading.real_now,
                              real_prev=reading.real_prev, tag="M0208", seed=p.seed,
                              data_date=data_date)
```

**`SHADOW_DEPTH` must NOT become a field on a params dataclass.** `registry._canon` renders a
dataclass by `dataclasses.fields()`, so one more field on `OverhangParams` moves every recorded
M0208 digest; `CapTopParams` is shared by M0221 **and** M0225 and would move both. The allocator
id is the whole difference between a v1 arm and a v2 arm — the rule the honest-control set already
proved in `test_each_new_arm_reuses_the_params_value_of_the_arm_it_replaces`.

**The off-by-one, named because it is the one that will bite.** The analysis's *extra monthly
steps affordable* column counts steps **on top of** the one `lookback_for` already pays. A chassis
with 194 bars of headroom affords 7 extra steps, which is `depth = 8`, not `depth = 7`.
`max_shadow_depth` exists so no method file does that subtraction by hand, and its answers agree
with phase 1's `k_max` column chassis for chassis:

| allocator | lookback today | `inner` | `max_shadow_depth(inner)` | phase 1's `k_max` | analysis's "extra steps" |
|---|---|---|---|---|---|
| `M0221-A1` / `M0227-A1` | 86 | 60 | **15** | 15 | 14 |
| `M0208-A1` | 279 | 253 | **8** | 8 | 7 |
| `M0215-A1` | 279 | 253 | **8** | 8 | 7 |
| `M0243-A1` | 278 | 252 | **8** | 8 | 7 |
| `M0047-A1` | 427 | 401 | **2** | 2 | 1 |
| `M0201-A1` / `M0202-A1` | 331 | 305 *(see note)* | 6 *(monthly — meaningless here)* | 3 *(quarterly, 70-bar steps)* | 2 |

Measured on this tree: `factor_lookback(m0208.N20) == 253`, `lookback_for(253) == 279`,
`max_shadow_depth(253) == 8`, `shadow_lookback_for(253, 8) == 461 <= 473`,
`shadow_lookback_for(253, 9)` raises.

**The M0201/M0202 row's two `inner` figures are both right and neither is this module's.**
`max_shadow_depth` subtracts `PREVIOUS_DECISION_BARS = 26`, giving 305 — a *monthly* reading of a
*quarterly* chassis, and that is exactly why a quarterly chassis must not call it. The chassis's
real backward step is `m0201.PREV_SPAN = **70**` bars (not the 78 an earlier draft of the analysis
quoted, now corrected there), so its honest `inner` is `331 − 70 = 261` and its `K_max` is
`(473 − 261) // 70 = **3**` — **two** extra quarterly steps, not one. Phase 1's probe computes that
at run time; this module never does.

**The M0201/M0202 row disagrees on purpose, and phase 3 must not paper over it.** Those two move
their basket on a quarterly clock, derive their own previous re-pick in their own method files and
never call `previous_decision_date` — which is why `CADENCES` is `("monthly",)` and the function
refuses anything else. `shadow_lookback_for` and `max_shadow_depth` are **monthly-only**: they
multiply by `PREVIOUS_DECISION_BARS = 26`. A quarterly chassis must not call either, and this
phase adds no quarterly cadence (see Handoffs). Phase 1 measured M0201's stand-in at 0.955, so the
expected answer there is *no-op* and the question does not arise.

**If phase 1 reports a chassis as a measured no-op, phase 3 draws nothing for it**, and this
phase's `test_a_book_that_does_not_read_what_it_held_draws_the_identical_control_at_every_depth`
is the proof that the no-op is structural on the four `reads_held: false` chassis rather than a
sampling result.

---

## The seam: why `Replay` and not a second callable beside `Select`

`Select` (`control_draw.py:109`) is `(date) -> (pool, the controlled arm's book)`. A shadow needs
the chassis's **band**: on M0208 a held name stays while it still ranks inside the top 40, so the
real book at the previous decision cannot be read at all without knowing what it held. `Select`
has nowhere to put that.

**The choice made, and it is the contract phases 3 and 5 code against:**

```python
Replay = Callable[[date, AbstractSet[str]], tuple[Sequence[str], Sequence[str]]]
```

`replay(d, held) -> (the eligible pool on d, the book on d given it held ``held`` coming in)`.

**Why one callable rather than two (a `Select` plus a band).** Two callables can disagree about
the pool — and then the entry count is counted against one pool while the draw is made from
another, silently, with every size assertion still passing. That is the same failure mode the
module docstring already warns about for the tail ordering. `Replay` hands back the pool it
actually ranked, every time it is asked.

**Why it is a strict generalisation and not a parallel rule.** A chassis whose book does not read
`held` — M0047's fresh `one_per_company`, M0221/M0225's fresh top-N of the sized pool, M0227's and
M0243's fresh top-N, four of the eight — has a `Replay` that ignores its second argument, and then
every reading in the replay is the reading `Select` would have given. Measured on the smoke
fixture at depths 1, 2, 5 and 8: `shadow_book` returns **the identical control, name for name**,
as `matched_book`. So for those four the shadow is provably a no-op at any depth, asserted as a
test rather than left to a sweep.

**And on a banded chassis, v2 at depth 1 is v1.** `m0208.MatchedDrawAllocator` reads its plain
top-N at the previous month end and applies the band to it once — *"one step of the band
unrolled"*, as its own docstring says. That pair **is** `shadow_selection(..., depth=1)`, asserted
decision for decision on the fixture. v2 therefore contains v1, which is what lets phase 3 argue
that the only thing its new arm changes is the depth.

---

## What the replay does, and why it is a replay

Let `d_0 = data_date` and `d_i = previous_decision_date(d_{i-1})`. For `depth = K`:

```
d_K     ── the band applied to an EMPTY book ──▶ shadow_K   (= the plain top-N: the fresh stand-in)
d_{K-1} ── the band applied to shadow_K ───────▶ shadow_{K-1}
   ...                                              (K-1 rolls of accumulated drift)
d_1     ── the band applied to shadow_2 ───────▶ real_prev
d_0     ── the band applied to real_prev ──────▶ real_now
```

`matched_names` then receives that `(real_now, real_prev)` pair and does **v1's** arithmetic on
it, unchanged. The shadow is only a better `real_prev`; the partition, the two hashes, the tail
ordering and the pool-attrition residual are all the shipped rule.

**Why not carry the held set on the allocator**, which is the obvious design. Invariant I9:
`backtest.dev.run_registry` reuses **one allocator object per allocator id** across every candidate
in a sweep and across every walk-forward fold. An attribute holding "what the real book held last
month" would be written by one candidate and read by the next, and by fold 3 while fold 1 was
still being scored. The numbers would depend on sweep order, differ between a sweep and a single
run, and differ between a parallel pytest and a serial one. `shadow_selection` holds the shadow in
a local and nowhere else, so it is a pure function of `(replay, data_date, depth, cadence)` —
asserted by asking it for every date in reverse and in a shuffle and getting the same reading.

**What it costs.** `depth + 1` passes of the controlled arm's own ranking per decision, where v1
pays 2. At M0208's affordable maximum that is eight passes over 169 decisions instead of two. In
bars: `shadow_lookback_for(inner, depth) = inner + depth * PREVIOUS_DECISION_BARS`, which at
`depth = 1` is exactly `lookback_for(inner)` — the same two decisions, so the same calendar.

**The defect, reproduced on the fixture.** Measured 2026-10-20 over 23 monthly decisions of a
banded synthetic chassis (top 3 of 8, keep band 5): a full forward replay of the band enters **15**
names; the one-step reading sees **3** of them — **0.200×**; the backward replay reads 10 at depth
2, 13 at depth 3 and **15 at depth 4 — 1.000×**. Held-set agreement with the true book runs
**0.190, 0.667, 0.810, 0.905, 0.905, 0.905, 0.905, 0.952** for depths 1 through 8. The real-store
figure this mirrors is M0208's 304 entries against 624 — 0.487×, uniform across eras. The fixture
is harsher than the store because eight members behind a five-wide band drift faster than a
screened universe; the direction is the point, not the magnitude.

---

## Files

| File | Action | What changes | Line |
|---|---|---|---|
| `engine/src/seer_engine/lab/control_draw.py` | modify (**additions only**) | one import; the module docstring gains a dated section; the v2 block appended whole | `:82` (import), `:74` (docstring), `:308` (append) |
| `engine/tests/test_lab_control_draw.py` | modify (**one test appended**) | the golden vector; nothing above it is touched | append after `:404` |
| `engine/tests/test_lab_control_draw_shadow.py` | create | the replay's own module: calendar, equivalences, the defect, purity | new |

---

## Implementation Steps

### Step 1: One import, and the module docstring gains its v2 section
**File:** `engine/src/seer_engine/lab/control_draw.py:82` and `:74`

**Change (a), the import.** Line 82 reads `from datetime import date, datetime`. Add one line
immediately after it:

```python
from typing import NamedTuple
```

The import block then reads, in full:

```python
from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from collections.abc import Set as AbstractSet
from datetime import date, datetime
from typing import NamedTuple

from seer_engine import dates
```

**Change (b), the docstring.** The module docstring currently ends:

```
place. That is gaming the check, not passing it, and it is forbidden outright.

Pure: a calendar, two hashes and set arithmetic. No clock, no randomness, no store, no database.
"""
```

Replace that final `Pure:` paragraph with the five paragraphs below plus an amended `Pure:`
line. Nothing above the `**What this module may never be used for.**` paragraph is touched.

```
**The shadow (v2, 2026-10-20), and the half of the match this rule was shipped without.** The
reading above is honest about where the entry count comes from and quietly wrong about what it
measures. ``matched_book`` asks ``select`` for the controlled arm twice, and on a chassis whose
real book has a KEEP BAND -- a held name stays while it still ranks inside a wider threshold --
the earlier reading is a FRESHLY DERIVED top-N, because no allocator holds a record of what the
arm it controls actually held. A fresh top-20 is ranked 1 through 20 and M0208's band only drops
a name past rank 40, so almost nothing falls out of it. A real held set has been drifting toward
that edge for months and falls out far faster. Measured over all 169 of M0208's decisions on the
real store: the fresh stand-in reads **304 entries against the real book's 624 -- 0.487x, uniform
across eras** (0.444 / 0.509 / 0.500); the 624 is the figure the close-out recorded, and the RATIO
is the finding -- an entry count and a trade count are not the same quantity and the recorded
``trials.trades`` is also 624, so phase 1's forward replay is what settles the absolute. The
control then enters half as many names as the book it controls, pool attrition drags the realised
figure back to 0.73x trades and 0.76x turnover, and
the sentence M0208 publishes about its own margin is quoted against an opponent paying three
quarters of the fee bill. It is a floor, not a measurement, and its own verdict says so.

**The repair is a bounded backward replay, and the module keeps both rules.** ``shadow_selection``
starts ``depth`` decisions back with the band applied to an EMPTY book -- which is the plain
top-N, exactly the fresh stand-in -- and rolls the chassis's own band forward one decision at a
time. After ``depth - 1`` rolls the shadow carries ``depth - 1`` months of accumulated drift and
stands at the previous decision, which is what ``real_prev`` wanted all along; one more
application gives ``real_now``, and ``matched_names`` does v1's arithmetic on the pair unchanged.
At ``depth = 1`` the replay IS the shipped rule, decision for decision, so v2 contains v1 rather
than competing with it. On a chassis whose book does not read what it held -- M0047's fresh
``one_per_company``, M0221/M0225's and M0227's and M0243's fresh top-N, four of the eight -- every
reading in the replay is the same reading and the shadow is provably a no-op at any depth.

**Why a replay and not a held set carried forward on the allocator**, which is the obvious design
and the wrong one. ``backtest.dev.run_registry`` reuses ONE allocator object per allocator id
across every candidate in a sweep and across every walk-forward fold. An attribute holding "what
the real book held last month" would be written by one candidate and read by the next, and by fold
3 while fold 1 was still being scored: the answer would depend on sweep order, differ between a
sweep and a single run, and differ between a parallel pytest and a serial one. The replay holds
its shadow in a local and nowhere else, so it is a pure function of the dates it is given and can
be asked for any decision in any order. It costs ``depth + 1`` passes of the controlled arm's own
ranking per decision where the shipped rule pays 2, and ``depth * PREVIOUS_DECISION_BARS`` of
lookback -- bounded by ``FIXTURE_BARS``, which ``shadow_lookback_for`` refuses to exceed rather
than handing back a number no test can drive.

**What the shadow is NOT, stated because the next reader will assume it is.** It is a NAME rule
and it moves the entry count only. Turnover on a chassis that weights its names by anything other
than equal slots is a property of the weight VECTOR and is not in name space at all:
``M0221-E50`` holds ``M0221-C50``'s exact fifty names and records its exact 360 trades and still
turns over 1.60x. No depth of replay reaches that, and a deeper one will not either. The weight
axis is a second rule on a second axis, it lives in ``control_weight``, and nothing in this module
ever touches a weight.

**Both constructions stay, and the recorded arms keep theirs.** v1's functions are not edited --
not refactored, not shared, not re-blessed. Thirteen recorded arms (lab trials 841-853) ran under
them and a module body is outside ``config_digest``, so an edit here would move all thirteen
without failing a single digest test. ``test_lab_control_draw``'s golden vector is what makes such
an edit go red; it pins a fixed input to a fixed output and it is the only test in the tree that
would catch one.

Pure: a calendar, two hashes, set arithmetic and a bounded replay of a band the caller owns. No
clock, no randomness, no store, no database, and no state held anywhere between calls.
"""
```

**Impact:** documentation and one import. No behaviour. Land it together with step 2 — the
import is used only there.

---

### Step 2: The v2 block, appended whole after line 308
**File:** `engine/src/seer_engine/lab/control_draw.py:308` (end of file, after `matched_book`)

**Change:** append the block below verbatim. It adds two constants, one callable type, one
named tuple and five functions. **Not one existing line is edited.**

```python
# ============================================================================================
# The shadow (v2, 2026-10-20): the same rule, with the real book's own drift under it.
# Added BESIDE v1. Nothing above this line changes.
# ============================================================================================

SHADOW_RULE_ID = "matched-draw-v2"
"""``RULE_ID``'s sibling, stamped by an arm drawn through ``shadow_book``/``shadow_selection``.

``RULE_ID`` is NOT bumped to "matched-draw-v2", and that is the point of having two names.
``RULE_ID``'s own docstring sets the rule: "it names a different control, so a bump belongs with
a new arm, never with an edit." Thirteen recorded arms (lab trials 841-853) were drawn under
``RULE_ID``; renaming it would re-label every one of them as something they were not. A v2 arm
carries this constant and a v1 arm keeps that one, and a reader of either trial can tell from the
recorded ``params.as_dict()`` which construction drew it."""

FIXTURE_BARS = 473
"""The hard ceiling on any lab allocator's ``lookback``, in sessions.

``labkit.smoke_market`` generates exactly this many NYSE sessions (``labkit.SMOKE_FIRST``
2013-12-02 through ``backtest.dev.DEV_END`` 2015-10-16), and ``test_lab_methods``' allocator
contract drives every lab allocator over that fixture. An allocator asking for more bars than the
fixture carries is not testable there, and the fixture cannot be widened -- it is the window a
long list of recorded feature tests is written against. The number is therefore absolute and it
is what bounds how deep a backward replay may go. ``test_lab_control_draw_shadow`` asserts this
constant against the fixture's own session count rather than trusting the 473."""

Replay = Callable[[date, AbstractSet[str]], tuple[Sequence[str], Sequence[str]]]
"""``replay(d, held) -> (the eligible pool on d, the controlled arm's book on d given ``held``)``.

``Select``'s sibling, and a strict generalisation of it: ``Select(d)`` is the reading of a book
that does not depend on what it held, which is ``Replay(d, anything)`` on such a chassis. A
chassis whose real book has a KEEP BAND -- a held name stays while it still ranks inside a wider
threshold -- cannot be read by ``Select`` at all without knowing what it held, and that is the
whole defect the shadow exists to repair.

**One callable and not two.** The obvious alternative was to keep ``Select`` and add a separate
band callable beside it. It is rejected: two callables can disagree about the pool, and then the
entry count is counted against one pool and the draw made from another, silently. ``Replay``
hands back the pool it actually ranked, every time it is asked.

The caller closes over ``prepared`` and ``members`` exactly as it does for ``Select``; see
``shadow_selection``."""


class ShadowReading(NamedTuple):
    """What a replay reads: today's pool, today's book, and the book at the previous decision.

    A named tuple rather than a bare triple because the two book fields are the same type and the
    same length and nothing but the name tells them apart -- and swapping them would silently
    invert the entry count rather than raising anything."""

    pool: list[str]
    real_now: list[str]
    real_prev: list[str]


def max_shadow_depth(inner: int) -> int:
    """The deepest replay an allocator whose own signal needs ``inner`` bars can afford.

    ``(FIXTURE_BARS - inner) // PREVIOUS_DECISION_BARS``, floored at 0. One place, because the
    arithmetic has an off-by-one in it that is easy to get wrong in a method file: a chassis with
    194 bars of headroom can afford SEVEN EXTRA steps on top of the one ``lookback_for`` already
    pays, which is ``depth = 8`` and not ``depth = 7``. M0208 measures 253 inner bars, so this
    returns 8 and ``shadow_lookback_for(253, 8)`` is 461."""
    if isinstance(inner, bool) or not isinstance(inner, int) or inner < 1:
        raise ValueError(f"inner must be an int >= 1, got {inner!r}")
    return max(0, (FIXTURE_BARS - inner) // PREVIOUS_DECISION_BARS)


def shadow_lookback_for(inner: int, depth: int) -> int:
    """``lookback_for``'s sibling: ``inner`` bars widened by ``depth`` monthly steps.

    An allocator replaying ``depth`` decisions back reads its own signal at the oldest of them, so
    the history it is handed must reach ``inner`` bars back from THERE. ``depth = 1`` returns
    exactly ``lookback_for(inner)``, which is not a coincidence: a one-step replay reads the same
    two decisions the shipped rule reads, and it is the same number of bars because it is the same
    calendar.

    **It refuses to outgrow the fixture rather than returning a number that cannot be tested.**
    ``FIXTURE_BARS`` is absolute, the failure it prevents is an allocator that no test can drive,
    and the alternative -- returning 487 and finding out in ``test_lab_methods`` -- hides which
    method file asked for it."""
    if isinstance(inner, bool) or not isinstance(inner, int) or inner < 1:
        raise ValueError(f"inner must be an int >= 1, got {inner!r}")
    if isinstance(depth, bool) or not isinstance(depth, int) or depth < 1:
        raise ValueError(f"depth must be an int >= 1, got {depth!r}")
    bars = inner + depth * PREVIOUS_DECISION_BARS
    if bars > FIXTURE_BARS:
        raise ValueError(
            f"a depth-{depth} replay over {inner} inner bars needs {bars} bars, past the "
            f"{FIXTURE_BARS}-bar fixture; max_shadow_depth({inner}) is "
            f"{max_shadow_depth(inner)}"
        )
    return bars


def shadow_decision_dates(data_date: date, depth: int, cadence: str = "monthly") -> list[date]:
    """The replay's calendar, OLDEST FIRST, ``depth + 1`` dates ending at ``data_date``.

    ``[d_depth, ..., d_1, d_0]`` where ``d_0`` is ``data_date`` and each earlier one is
    ``previous_decision_date`` of the one after it. Built by iterating the shipped derivation
    rather than stepping back a fixed number of sessions, so a short month and a holiday both land
    on the date the runner actually used -- the property
    ``test_previous_decision_date_is_the_previous_decisions_own_data_date`` already proves one
    step at a time, extended by induction to ``depth`` of them and asserted again here over the
    whole dev window.

    It raises where ``previous_decision_date`` raises: an unsupported cadence, or a calendar that
    runs out. Neither happens inside the dev window -- the earliest decision is 1995-12-29 and the
    deepest affordable replay is eight months, which lands in 1995."""
    d = _as_plain_date("data_date", data_date)
    if isinstance(depth, bool) or not isinstance(depth, int) or depth < 1:
        raise ValueError(f"depth must be an int >= 1, got {depth!r}")
    out = [d]
    for _ in range(depth):
        out.append(previous_decision_date(out[-1], cadence))
    out.reverse()
    return out


def shadow_selection(
    replay: Replay,
    data_date: date,
    *,
    depth: int,
    cadence: str = "monthly",
) -> ShadowReading:
    """The controlled arm's book at this decision and at the previous one, with its drift in it.

    **The defect this repairs, measured.** ``matched_book`` reads the controlled arm twice with
    ``Select``, and on a keep-band chassis the earlier reading is a FRESHLY DERIVED top-N. A fresh
    top-20 is ranked 1 through 20 and the band only drops a name past rank 40, so almost nothing
    falls out of it; a real held set has been drifting toward the edge for months and falls out far
    faster. Over all 169 of M0208's decisions the fresh stand-in reads **304 entries against the
    real book's 624 -- 0.487x, uniform across eras** (0.444 / 0.509 / 0.500). The 624 is as the
    close-out recorded it and the RATIO is the finding: the recorded ``trials.trades`` is also 624
    and the two are different quantities, so the absolute is a cross-check and not a load-bearing
    number here. The control then enters half as many names as the book it controls, and the
    sentence the method publishes about its own margin is quoted against an opponent paying half
    the fee bill.

    **The repair: a bounded backward replay, and not a carried held set.** Start ``depth``
    decisions back with the band applied to an EMPTY book -- which is the plain top-N, the same
    thing the fresh stand-in was -- and roll the chassis's own band forward one decision at a time.
    After ``depth - 1`` rolls the shadow has accumulated ``depth - 1`` months of drift and stands
    at the previous decision, which is what ``real_prev`` wanted all along. One more application
    gives ``real_now``.

    **Why a replay and not state carried on the allocator**, which is the obvious and wrong design.
    ``backtest.dev.run_registry`` reuses ONE allocator object per allocator id across every
    candidate in a sweep and across every walk-forward fold, so an attribute holding "what the real
    book held last month" would be written by one candidate and read by the next, and by fold 3
    while fold 1 was still being scored. The numbers would depend on sweep order, be irreproducible
    between a sweep and a single run, and differ between a parallel and a serial pytest. This
    function holds the shadow in a local and nowhere else: it is a pure function of ``(replay,
    data_date, depth, cadence)``, it can be called in any order on any date, and
    ``test_the_replay_is_a_pure_function_of_the_date_it_is_given`` asserts exactly that.

    **What it costs.** ``depth + 1`` passes of the controlled arm's own ranking per decision, where
    the shipped rule pays 2. At M0208's affordable maximum that is eight passes over 169 decisions
    instead of two. The lookback it costs is ``shadow_lookback_for(inner, depth)``, and the ceiling
    on ``depth`` is ``max_shadow_depth(inner)``.

    **What it does NOT touch, stated because the next reader will assume it does.** This is a NAME
    rule and it moves the entry count only. Turnover on a chassis that weights its names by
    anything other than equal slots is a property of the weight VECTOR, not of the names:
    ``M0221-E50`` holds ``M0221-C50``'s exact fifty names and records its exact 360 trades and
    still turns over 1.60x. No depth of replay reaches that. The weight axis is ``control_weight``
    and a separate rule; this module never touches a weight.

    **An era where the chassis scores nothing simply reseeds the shadow.** ``replay`` returns an
    empty book, the shadow becomes empty, and the next decision starts fresh from the band applied
    to nothing -- which is the correct reading, because a book that held nothing did hold nothing.
    """
    calendar = shadow_decision_dates(data_date, depth, cadence)
    shadow: frozenset[str] = frozenset()
    pool_now: list[str] = []
    real_now: list[str] = []
    real_prev: list[str] = []
    last = len(calendar) - 1
    for i, d in enumerate(calendar):
        pool, book = replay(d, shadow)
        if i == last:
            pool_now, real_now = list(pool), list(book)
        else:
            real_prev = list(book)
            shadow = frozenset(book)
    return ShadowReading(pool_now, real_now, real_prev)


def shadow_book(
    replay: Replay,
    data_date: date,
    held: AbstractSet[str],
    *,
    tag: str,
    seed: int,
    depth: int,
    cadence: str = "monthly",
) -> list[str]:
    """``matched_book`` with the replay in front of it: the call a v2 method file makes.

    The draw itself is v1's, byte for byte -- this hands ``matched_names`` a better ``real_prev``
    and changes nothing else. The partition, the two hashes, the tail ordering and the
    pool-attrition residual are all the shipped rule, which is why a v2 arm needs no new argument
    about any of them and why the only thing that can differ between a v1 arm and a v2 arm of the
    same chassis is how many names the controlled book is seen to have entered.

    ``depth`` is keyword-only and has NO DEFAULT on purpose. It is the one number this rule cannot
    derive -- how far back a chassis's band has to be rolled before the shadow has stopped moving
    is a property of that chassis's band and its ranking, measured per chassis and not guessed
    here. A default would be a guess wearing a constant's clothes."""
    reading = shadow_selection(replay, data_date, depth=depth, cadence=cadence)
    if not reading.real_now:
        return []
    return matched_names(
        pool=reading.pool, held=held, real_now=reading.real_now, real_prev=reading.real_prev,
        tag=tag, seed=seed, data_date=data_date,
    )
```

**Impact:**

- `control_draw.py` goes from 308 lines to about 525. Nothing above line 308 calls anything
  below it, so no recorded arm's code path is reached by any of it.
- `shadow_book` calls `matched_names`, so v1's arithmetic is reused rather than reimplemented
  and the two paths can never disagree about the partition, the hashes or the tail ordering.
- `shadow_lookback_for` **raises** above `FIXTURE_BARS`. Deliberate: the alternative is
  returning 487 and discovering it in `test_lab_methods`' allocator contract, which does not
  say which method file asked for it. An over-deep `depth` in phase 3's file therefore fails
  loudly at the first `lookback` call.
- `depth` is keyword-only with no default on both public entry points, so no caller can take a
  K this module invented.

---

### Step 3: The golden vector — the test that makes an in-place edit go red
**File:** `engine/tests/test_lab_control_draw.py` — append after line 404. **Nothing above
line 404 is changed.**

**Change:** append verbatim.

```python
# ---- the golden vector: the frozen path, pinned where nothing else would catch it ----------------

GOLD_POOL = ("AAPL", "ADBE", "AMGN", "BAC", "CAT", "CSCO", "DIS", "GE", "IBM", "JNJ", "KO", "MSFT")
GOLD_HELD = frozenset({"AAPL", "CAT", "DIS", "IBM", "KO"})
GOLD_TAG = "M0208"
GOLD_SEED = 1
GOLD_DATE = date(2015, 6, 30)


def test_the_shipped_draw_still_produces_the_vector_the_recorded_arms_were_drawn_from():
    r"""A frozen input and its frozen output, so an in-place edit to v1's body goes red.

    **Nothing else in this repository would catch one.** A ``config_digest`` is the rules, the
    allocator id and ``dataclasses.fields()`` of the params (``backtest.registry._canon``); a
    module BODY is in none of them, so
    ``test_lab_methods.test_every_recorded_configuration_still_digests_to_its_recorded_digest``
    stays green while the thirteen recorded matched-draw arms (lab trials 841-853) quietly
    describe a different book than the one they ran. ``m0208``'s own file names the same trap
    above ``_banded_picks`` and answers it by copying ``choose``'s band rather than sharing it.

    **Measured, 2026-10-20.** Appending one ``"|"`` to ``keep_key``'s hash input moves this keep
    order from ``['KO', 'CAT', 'AAPL']`` to ``['DIS', 'KO', 'CAT']`` -- a different book for every
    recorded arm -- and all thirty-four tests in this module and its twin, and the recorded-digest
    test, pass anyway. Under this test the same edit fails on the first assertion.

    **The other tests here are relative and this one is absolute, and that is the difference.**
    ``test_the_keep_hash_is_date_free_and_the_entry_hash_turns_with_the_month`` asserts that a key
    equals itself and differs from its neighbours; every such property survives a re-keying of the
    whole hash. Only a literal survives nothing.

    The literals are the shipped functions' own output on ``main`` @ ``e3aeeff``. A deliberate
    change to the rule belongs in a NEW path beside this one -- ``shadow_book``, and whatever
    comes after it -- never in an edit that re-blesses these numbers.
    """
    assert cd.keep_key(GOLD_TAG, GOLD_SEED, "AAPL") == 11772521752773708193
    assert cd.keep_key(GOLD_TAG, GOLD_SEED, "MSFT") == 14969734582403058465
    assert cd.entry_key(GOLD_TAG, GOLD_SEED, "AAPL", GOLD_DATE) == 8778277638079604380
    assert cd.entry_key(GOLD_TAG, GOLD_SEED, "MSFT", GOLD_DATE) == 26777536067865861

    keep, tail = cd.matched_partition(pool=GOLD_POOL, held=GOLD_HELD, keep_n=3,
                                      tag=GOLD_TAG, seed=GOLD_SEED, data_date=GOLD_DATE)
    assert keep == ["KO", "CAT", "AAPL"]
    assert tail == ["MSFT", "BAC", "AMGN", "GE", "CSCO", "ADBE", "JNJ", "IBM", "DIS"]

    assert cd.churn(("X1", "X2", "X3", "X4", "X5"), ("X1", "X2", "X3", "X9", "X8")) == 2
    book = cd.matched_names(pool=GOLD_POOL, held=GOLD_HELD,
                            real_now=("X1", "X2", "X3", "X4", "X5"),
                            real_prev=("X1", "X2", "X3", "X9", "X8"),
                            tag=GOLD_TAG, seed=GOLD_SEED, data_date=GOLD_DATE)
    assert book == ["MSFT", "CAT", "BAC", "AAPL", "KO"]

    assert cd.previous_decision_date(GOLD_DATE) == date(2015, 5, 29)
    assert cd.PREVIOUS_DECISION_BARS == 26
    assert cd.lookback_for(279) == 305
    assert cd.RULE_ID == "matched-draw-v1"
```

**Impact:** this is as much the phase's deliverable as the replay is. Verified on this tree,
2026-10-20, with two independent perturbations of v1's frozen body, each applied and reverted:

| perturbation | what it silently moves | red **without** this test | red **with** it |
|---|---|---|---|
| `keep_key`: `"{tag}\|keep\|{seed}\|{symbol}"` -> `"{tag}\|keep\|{seed}\|{symbol}\|"` | the keep order of every recorded arm (`['KO','CAT','AAPL']` -> `['DIS','KO','CAT']`) | **0 of 35** | 1 — this one |
| `matched_names`: final `sorted(book, key=(entry_key, s))` -> `sorted(book)` | the fill order under a cash shortage, for nineteen years | **0 of 35** | 1 — this one |

In both runs `test_every_recorded_configuration_still_digests_to_its_recorded_digest` passed
and the other 45 tests in the three control-draw modules passed. The golden vector is the only
thing in the tree that fails. The literals are the shipped functions' own output on `main` @
`e3aeeff`.

---

### Step 4: The replay's own test module
**File:** `engine/tests/test_lab_control_draw_shadow.py` — new.

**Why a module of its own rather than more cases in `test_lab_control_draw.py`.** That
module's own docstring gives the precedent: a calendar-and-replay check walks every monthly
decision of the dev window and drives a synthetic selector, neither of which belongs in a
per-candidate parametrization. The 473-bar smoke fixture cannot be widened to make room for
one either — it is the window a long list of recorded feature tests is written against — so a
dedicated module is the only place a depth sweep fits. It is also what keeps phase 5 from
editing a file phase 2 owns.

**Change:** create the file with exactly this content.

```python
"""``lab.control_draw``'s shadow: the backward replay, proved on the calendar and the fixture.

A module of its own rather than more cases in ``test_lab_control_draw``, for the reason that
module's own docstring gives for existing: a calendar-and-replay check walks every monthly
decision of the dev window and drives a synthetic selector, neither of which belongs in a
per-candidate parametrization. The 473-bar smoke fixture cannot be widened to make room for one
either -- it is the window a long list of recorded feature tests is written against -- so a
dedicated module is the only place a depth sweep fits.

**What is proved here, and why each one is worth a test.**

* The replay's calendar is the runner's own decision sequence, ``depth`` steps of it rather than
  one. ``test_lab_control_draw`` proves one step against ``is_rank_session``; this extends it.
* **The shipped rule is the one-step replay.** On the chassis that unrolls one step of its band by
  hand -- M0208's ``picks_prev``/``picks_real`` -- ``shadow_selection(depth=1)`` returns that exact
  pair. v2 is therefore a strict generalisation of v1 and not a different rule wearing its name,
  which is what lets phase 3 reason that the only thing a new arm changes is the depth.
* **A chassis whose book does not read what it held draws the IDENTICAL control at every depth**,
  name for name, against ``matched_book`` itself. Four of the eight chassis are that shape
  (M0047, M0221/M0225, M0227, M0243), and "the shadow is a no-op here" is therefore a proved
  property of those chassis and not a measurement anyone has to repeat.
* **The defect, reproduced.** On a banded fixture the fresh stand-in reads **3 entries against the
  real book's 15** -- 0.200x, the same failure measured at 0.487x on M0208's real store -- and the
  replay closes it to 1.000x by depth 4.
* **Purity.** ``run_registry`` reuses one allocator object across candidates and across
  walk-forward folds, so the replay is asserted to give the same answer whatever order its dates
  are asked for in. This is the test that forbids the carried-state design.

Everything here costs nothing and sees no return: a calendar, the smoke fixture's eight synthetic
members, two hashes and set arithmetic.
"""

from __future__ import annotations

from datetime import date

import pytest
from labkit import MEMBER_STOCKS, SMOKE_FIRST, smoke_market

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END
from seer_engine.lab import control_draw as cd
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, is_rank_session

TAG = "TEST"
SEED = 1
TOP = 3
KEEP = 5  # the band: a held name stays while it ranks inside the top five of eight
MOM_BARS = 5  # the ranking window that makes the synthetic book churn; see test_lab_control_draw
JUNE = date(2015, 6, 30)


@pytest.fixture(scope="module")
def market():
    return smoke_market()


def _decision_dates(start: date, end: date) -> list[date]:
    """Every ``data_date`` a monthly rule set hands the allocator between ``start`` and ``end``."""
    return [
        dates.prev_session(s)
        for s in dates.sessions(start, end)
        if is_rank_session(MONTHLY_HOLD_FRAC_GOTRADE, s)
    ]


def _ranked(market, d: date) -> tuple[list[str], list[str]]:
    """``(the pool on d in symbol order, the pool on d in rank order)``.

    Ranked on the trailing ``MOM_BARS``-bar change, for the reason ``test_lab_control_draw``'s own
    selector gives: the fixture's eight members run on smooth, well-separated paths, so a book of
    the three highest closes is very nearly constant and would let a control that matched nothing
    pass every assertion below."""
    pool: list[str] = []
    change: dict[str, float] = {}
    for s in MEMBER_STOCKS:
        h = market.history.get(s)
        i = None if h is None else h.index_of(d)
        if i is None:
            continue
        pool.append(s)
        change[s] = h.close[i] / h.close[max(0, i - MOM_BARS)]
    return sorted(pool), sorted(pool, key=lambda s: (-change[s], s))


def _banded(market, top: int = TOP, keep: int = KEEP):
    """A ``Replay`` with M0208's band: a held name stays while it ranks inside ``keep``.

    The same arithmetic as ``m0208._banded_picks``, written out here rather than imported, because
    the fixture carries no share counts and M0208's own pool is empty on it."""

    def replay(d: date, held) -> tuple[tuple[str, ...], tuple[str, ...]]:
        pool, order = _ranked(market, d)
        if not pool:
            return (), ()
        rank = {s: i for i, s in enumerate(order)}
        picks = sorted((s for s in held if rank.get(s, keep) < keep), key=lambda s: rank[s])[:top]
        for s in order:
            if len(picks) >= top:
                break
            if s not in picks:
                picks.append(s)
        return tuple(pool), tuple(picks)

    return replay


def _unbanded(market, top: int = TOP):
    """A ``Replay`` that ignores ``held``: the shape four of the eight chassis actually have."""

    def replay(d: date, held) -> tuple[tuple[str, ...], tuple[str, ...]]:
        pool, order = _ranked(market, d)
        if not pool:
            return (), ()
        return tuple(pool), tuple(order[:top])

    return replay


def _true_held(replay, ds: list[date]) -> dict[date, frozenset[str]]:
    """The real book's held set at every decision, from a full forward replay of its own band.

    This is the thing the shadow estimates, and the only way to get it is to roll the band forward
    from the beginning of the window -- which is exactly what no allocator can afford to do and
    what the bounded replay approximates."""
    out: dict[date, frozenset[str]] = {}
    real: frozenset[str] = frozenset()
    for d in ds:
        _, book = replay(d, real)
        if not book:
            continue
        out[d] = real = frozenset(book)
    return out


# ---- the calendar, extended to depth --------------------------------------------------------


def test_the_fixture_is_the_bars_the_lookback_ceiling_is_measured_from():
    """``FIXTURE_BARS`` is asserted against the fixture, never trusted to the literal 473.

    The whole depth budget hangs off this number, and a labkit change that moved ``SMOKE_FIRST``
    would otherwise leave every method file's affordable depth quietly wrong."""
    assert cd.FIXTURE_BARS == len(dates.sessions(SMOKE_FIRST, DEV_END))


def test_the_replay_calendar_is_the_runners_own_decision_sequence():
    """Exact, over every monthly decision of the dev window, against ``is_rank_session`` itself.

    ``test_lab_control_draw`` proves one step; a replay takes ``depth`` of them, and an induction
    that is right in the abstract can still be off by one in the loop that writes it."""
    ds = _decision_dates(date(1996, 1, 2), DEV_END)
    assert len(ds) > 230, f"only {len(ds)} monthly decisions in the dev window"
    for depth in (1, 2, 5, 8):
        for i in range(depth, len(ds)):
            assert cd.shadow_decision_dates(ds[i], depth) == ds[i - depth : i + 1], (
                f"{ds[i]}: a depth-{depth} replay derived a calendar the runner never used"
            )


def test_the_lookback_pays_one_month_a_step_and_refuses_to_outgrow_the_fixture():
    """M0208's real numbers, because the off-by-one here is the one that would bite.

    Its own signal needs 253 bars and it has 194 to spare, which is SEVEN EXTRA steps on top of
    the one ``lookback_for`` already pays -- ``depth = 8``, not ``depth = 7``. ``max_shadow_depth``
    exists so no method file has to do that subtraction itself."""
    assert cd.shadow_lookback_for(253, 1) == cd.lookback_for(253) == 279
    assert cd.shadow_lookback_for(253, 8) == 461 <= cd.FIXTURE_BARS
    assert cd.max_shadow_depth(253) == 8
    with pytest.raises(ValueError, match="past the 473-bar fixture"):
        cd.shadow_lookback_for(253, 9)
    for bad in (0, -1, True, 2.0):
        with pytest.raises(ValueError):
            cd.shadow_lookback_for(60, bad)
        with pytest.raises(ValueError):
            cd.shadow_decision_dates(JUNE, bad)


# ---- v2 contains v1 --------------------------------------------------------------------------


def test_the_shipped_rule_is_the_one_step_replay(market):
    """v2 at ``depth = 1`` is exactly what M0208 does by hand today, decision for decision.

    ``m0208.MatchedDrawAllocator`` reads its plain top-N at the previous month end and applies the
    band to it once -- "one step of the band unrolled", as its docstring says. That pair IS the
    depth-1 replay, so the shadow is a generalisation of the shipped rule and not a replacement
    for it, and the only thing a v2 arm changes is how many steps it rolls."""
    replay = _banded(market)
    for d in _decision_dates(SMOKE_FIRST, DEV_END):
        _, prev_plain = replay(cd.previous_decision_date(d), frozenset())
        _, now_banded = replay(d, frozenset(prev_plain))
        reading = cd.shadow_selection(replay, d, depth=1)
        assert reading.real_prev == list(prev_plain), f"{d}: depth 1 is not the hand-unrolled step"
        assert reading.real_now == list(now_banded), f"{d}: depth 1 moved the book it reads"


def test_a_book_that_does_not_read_what_it_held_draws_the_identical_control_at_every_depth(
    market,
):
    """The measured no-op, proved instead of measured.

    Four of the eight chassis that call this module derive a real book that does not depend on
    what it held -- M0047's fresh ``one_per_company``, M0221/M0225's fresh top-N of the sized
    pool, M0227's and M0243's fresh top-N. On such a chassis ``replay`` ignores ``held``, every
    reading in the replay is the same reading, and the shadow cannot move the entry count however
    deep it goes. Asserted against ``matched_book`` itself, name for name, so "the shadow is a
    no-op here" needs no sweep to establish."""
    replay = _unbanded(market)

    def select(d: date):
        return replay(d, frozenset())

    ds = _decision_dates(SMOKE_FIRST, DEV_END)
    for depth in (1, 2, 5, 8):
        v1: frozenset[str] = frozenset()
        v2: frozenset[str] = frozenset()
        for d in ds:
            a = cd.matched_book(select, d, v1, tag=TAG, seed=SEED)
            b = cd.shadow_book(replay, d, v2, tag=TAG, seed=SEED, depth=depth)
            assert a == b, f"{d}: depth {depth} moved a control on a chassis with no band"
            v1, v2 = frozenset(a), frozenset(b)


# ---- the defect, and the repair ---------------------------------------------------------------


def test_the_fresh_stand_in_under_reads_a_banded_books_entries_and_the_replay_repairs_it(market):
    """The whole reason this code exists, reproduced on the fixture.

    Measured on the smoke fixture 2026-10-20 over 23 monthly decisions: a full forward replay of
    the band enters **15** names; the one-step reading sees **3** of them (0.200x); the backward
    replay reads 10 at depth 2, 13 at depth 3 and **15 at depth 4** (1.000x). The real-store
    figure this mirrors is M0208's 304 against 624 -- 0.487x, uniform across eras. The fixture's
    ratio is harsher than the store's because eight members and a five-wide band drift faster than
    a screened universe does; the direction is the point, not the magnitude.

    The bars are loose on purpose. These are small counts on a synthetic fixture and a labkit
    change may legitimately move them a name or two; what must not change is that one step
    under-reads badly and that a few steps close it."""
    replay = _banded(market)
    ds = _decision_dates(SMOKE_FIRST, DEV_END)
    truth = _true_held(replay, ds)
    real_entries = 0
    previous: frozenset[str] = frozenset()
    for d in ds:
        if d not in truth:
            continue
        real_entries += len(truth[d] - previous)
        previous = truth[d]
    assert real_entries >= 12, (
        f"the banded fixture book entered only {real_entries} names over {len(ds)} decisions, so "
        f"there is no defect here to reproduce"
    )

    def seen(depth: int) -> int:
        total = 0
        for d in ds:
            reading = cd.shadow_selection(replay, d, depth=depth)
            if reading.real_now:
                total += cd.churn(reading.real_now, reading.real_prev)
        return total

    one = seen(1)
    assert one * 2 <= real_entries, (
        f"the one-step reading saw {one} of {real_entries} entries; it is supposed to under-read "
        f"a banded book by about half, and this fixture no longer shows that"
    )
    deep = seen(4)
    assert 0.80 <= deep / real_entries <= 1.25, (
        f"a depth-4 replay saw {deep} of {real_entries} entries, outside the 0.80-1.25 band the "
        f"whole remedy exists to reach"
    )


def test_the_shadow_agrees_with_the_real_held_set_more_often_the_deeper_it_goes(market):
    """The statistic the entry count is downstream of, which is steadier than the count itself.

    Measured on the fixture 2026-10-20, the fraction of decisions whose ``real_prev`` equals the
    real book's actual held set at that decision: **0.190 at depth 1, 0.667, 0.810, then 0.905
    from depth 4 through depth 7 and 0.952 at depth 8.** Non-decreasing, which is a measured
    property of this fixture and not a theorem -- a deeper replay reseeds from further back and
    could in principle land worse -- so it is pinned here rather than argued."""
    replay = _banded(market)
    ds = _decision_dates(SMOKE_FIRST, DEV_END)
    truth = _true_held(replay, ds)

    def agreement(depth: int) -> float:
        hits = seen = 0
        for d in ds:
            earlier = cd.previous_decision_date(d)
            if earlier not in truth:
                continue
            seen += 1
            hits += 1 if frozenset(cd.shadow_selection(replay, d, depth=depth).real_prev) == truth[
                earlier
            ] else 0
        assert seen >= 15, f"only {seen} comparable decisions on the fixture"
        return hits / seen

    scores = [agreement(k) for k in range(1, 7)]
    assert scores[0] <= 0.30, f"depth 1 agreed with the real held set {scores[0]:.3f} of the time"
    assert scores[3] >= 0.85, f"depth 4 only reached {scores[3]:.3f}"
    for shallower, deeper in zip(scores, scores[1:]):
        assert deeper >= shallower, f"a deeper replay agreed less often: {scores}"


# ---- purity, which is the design ---------------------------------------------------------------


def test_the_replay_is_a_pure_function_of_the_date_it_is_given(market):
    """Plan invariant I9, which is why this is a replay and not a held set carried on the object.

    ``backtest.dev.run_registry`` reuses one allocator object per allocator id across every
    candidate in a sweep and across every walk-forward fold. A shadow held as instance state would
    be written by one candidate and read by the next; the answer would depend on sweep order and
    differ between a parallel and a serial run. Asked in reverse, in a shuffle, and twice over,
    this returns the same reading every time."""
    replay = _banded(market)
    ds = _decision_dates(SMOKE_FIRST, DEV_END)
    want = {d: cd.shadow_selection(replay, d, depth=5) for d in ds}
    for d in reversed(ds):
        assert cd.shadow_selection(replay, d, depth=5) == want[d], f"{d}: read back differently"
    for d in sorted(ds, key=lambda x: (x.day, x.month)):
        assert cd.shadow_selection(replay, d, depth=5) == want[d], f"{d}: order changed the answer"


def test_an_era_with_no_book_reseeds_the_shadow_rather_than_carrying_a_stale_one():
    """A chassis that scores nothing early -- a fundamentals panel that opens in 2009, say.

    The replay reads an empty book, the shadow becomes empty, and the next decision starts from
    the band applied to nothing. That is the right answer: a book that held nothing did hold
    nothing, and carrying the last non-empty set forward would invent a holding the book never
    had."""
    opened = date(2015, 5, 29)
    pool = ("AAA", "BBB", "CCC", "DDD")

    def replay(d: date, held):
        if d < opened:
            return (), ()
        return pool, ("AAA", "BBB")

    reading = cd.shadow_selection(replay, JUNE, depth=5)
    assert reading.real_prev == ["AAA", "BBB"], "the one scored earlier decision was not read"
    assert reading.real_now == ["AAA", "BBB"]
    assert reading.pool == list(pool)
    book = cd.shadow_book(replay, JUNE, frozenset(), tag=TAG, seed=SEED, depth=5)
    assert len(book) == 2 and set(book) <= set(pool)

    def silent(d: date, held):
        return (), ()

    assert cd.shadow_book(silent, JUNE, frozenset(), tag=TAG, seed=SEED, depth=5) == [], (
        "a chassis with no book at this decision must draw no control, exactly as matched_book "
        "returns [] on an empty real_now"
    )


def test_the_shadow_book_is_the_books_size_and_takes_in_the_books_entries(market):
    """``shadow_book`` is ``matched_names`` with a better ``real_prev`` and nothing else, so the
    match it claims is still the match v1 claims -- asserted here on the banded chassis where v1's
    own test could not run."""
    replay = _banded(market)
    held: frozenset[str] = frozenset()
    checked = moved = 0
    for d in _decision_dates(SMOKE_FIRST, DEV_END):
        reading = cd.shadow_selection(replay, d, depth=4)
        if not reading.real_now:
            continue
        book = cd.shadow_book(replay, d, held, tag=TAG, seed=SEED, depth=4)
        entries = len(set(book) - held)
        assert len(book) == len(set(book)), f"{d}: the control holds a name twice"
        assert len(book) == len(reading.real_now), f"{d}: the control is not the book's size"
        assert set(book) <= set(reading.pool), f"{d}: the control left the pool it draws from"
        assert entries == cd.churn(reading.real_now, reading.real_prev) or entries > 0, (
            f"{d}: {entries} entries against the replay's "
            f"{cd.churn(reading.real_now, reading.real_prev)}"
        )
        held = frozenset(book)
        checked += 1
        moved += 1 if entries else 0
    assert checked >= 20, f"only {checked} decisions on the fixture; that proves nothing"
    assert moved * 2 >= checked, f"the control moved on only {moved} of {checked} decisions"


# ---- the two rule ids ----------------------------------------------------------------------------


def test_the_v2_rule_id_is_a_second_name_and_v1s_is_left_where_it_was():
    """Thirteen recorded arms (lab trials 841-853) carry ``matched-draw-v1`` in their recorded
    ``params.as_dict()``. Renaming ``RULE_ID`` would re-label every one of them as a construction
    they were not drawn under, which is why v2 is a second constant and not a bumped one."""
    assert cd.RULE_ID == "matched-draw-v1"
    assert cd.SHADOW_RULE_ID == "matched-draw-v2"
    assert cd.RULE_ID != cd.SHADOW_RULE_ID
```

**Impact:** 12 tests, no store, no database, no return. Measured runtime 1.6 s for all three
control-draw modules together (46 tests).

---

## Verification

Run from `/home/miftah/seer`. These are the commands, not a description of them.

**Build / lint** (CI's P0 is bugs only: E9 and F, minus F401):

```bash
cd /home/miftah/seer && engine/.venv/bin/ruff check engine
```
Expect `All checks passed!`.

**The three control-draw modules, with the golden vector and the replay:**

```bash
cd /home/miftah/seer && PYTHONPATH=engine/src engine/.venv/bin/python -m pytest \
  engine/tests/test_lab_control_draw.py \
  engine/tests/test_lab_control_draw_shadow.py \
  engine/tests/test_lab_control_draw_twins.py -n0 -q
```
Expect `46 passed` — 33 existing in the first module, 1 golden vector, 12 new, and the twins'.

**The recorded-digest test, named explicitly because it is the invariant:**

```bash
cd /home/miftah/seer && PYTHONPATH=engine/src engine/.venv/bin/python -m pytest \
  engine/tests/test_lab_methods.py \
  -k test_every_recorded_configuration_still_digests_to_its_recorded_digest -n0 -q
```
Expect `1 passed`. It must pass — **and that is not evidence of anything**, because it passes
under a perturbation too. It is here so the phase cannot be said to have moved a digest, not
as proof the bodies are intact. Step 3 is that proof.

**Every allocator still fits 473 bars:**

```bash
cd /home/miftah/seer && PYTHONPATH=engine/src engine/.venv/bin/python -m pytest \
  engine/tests/test_lab_methods.py -k lookback -n0 -q
```

**Tests — the whole suite, in parallel, with Postgres up so the DB tests do not skip** (CI
fails if they skip):

```bash
docker start seer-pg 2>/dev/null || docker run -d --name seer-pg \
  -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
cd /home/miftah/seer && PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  PYTHONPATH=engine/src engine/.venv/bin/python -m pytest engine/tests -q
```
Measured on this tree with all four steps applied: **6195 passed, 3 skipped in 116.41s**. The
three skips are the pre-existing env-gated live sweeps (`test_lab_costs.py:314`,
`test_lab_name_count.py:240`, `test_lab_survivorship.py:387`), not DB tests.

**The golden vector demonstrably fails when v1 is perturbed.** This is the perturbation used
to verify it; run it, read the output, then confirm the revert:

```bash
cd /home/miftah/seer
python3 - <<'PY'
import pathlib
p = pathlib.Path('engine/src/seer_engine/lab/control_draw.py')
t = p.read_text()
old = r'''key = f"{tag}|keep|{seed}|{symbol}".encode()'''
new = r'''key = f"{tag}|keep|{seed}|{symbol}|".encode()'''
assert old in t
p.write_text(t.replace(old, new))
print('perturbed')
PY
PYTHONPATH=engine/src engine/.venv/bin/python -m pytest \
  engine/tests/test_lab_control_draw.py engine/tests/test_lab_control_draw_shadow.py \
  engine/tests/test_lab_control_draw_twins.py -n0 -q
# expect: 1 failed, 45 passed -- and the one failure is
#   test_the_shipped_draw_still_produces_the_vector_the_recorded_arms_were_drawn_from
git checkout -- engine/src/seer_engine/lab/control_draw.py
git diff --stat engine/src/seer_engine/lab/control_draw.py   # expect: no output
```

**REVERT IT.** `git checkout` above restores the file; re-run the three modules and see
`46 passed` before going any further. A perturbation left in place is thirteen recorded arms
silently rewritten.

**The lab database is untouched:**

```bash
cd /home/miftah/seer && git hash-object lab/lab.sqlite
```
Expect `607b78cf69c8e4e3a68a1e84c85eedfd1040c754`, the value measured at the start of this
phase. No `lab` command is run in this phase at all — not even a read, because any `lab`
command may migrate the file on connect.

**Test-window looks 4 -> 4:**

```bash
cd /home/miftah/seer && sqlite3 "file:lab/lab.sqlite?mode=ro" \
  "select count(*) from trials where window='test';"
```
Read before and after; both 4. `lab test` is never invoked and `SEER_RESEARCH_TEST_STORE` is
never read in this phase.

**Manual check — the I3 audit, and it is not optional.** `git diff --stat` must show exactly
three paths. Then:

```bash
cd /home/miftah/seer && git diff -U0 engine/src/seer_engine/lab/control_draw.py \
  | grep '^-' | grep -v '^---'
```
Expect **exactly one line**, and it is the `Pure: a calendar, two hashes and set arithmetic...`
docstring line step 1(b) replaces. Any other `-` line is an invariant I3 violation and the
phase stops and reports rather than continuing.

**Exit criteria:**

1. `engine/.venv/bin/ruff check engine` clean.
2. `pytest engine/tests` green in parallel with `PG_TEST_URL` set — DB tests running, not
   skipping.
3. `test_every_recorded_configuration_still_digests_to_its_recorded_digest` green.
4. The golden vector fails under the `keep_key` perturbation above and passes after the revert,
   with the perturbation shown and reverted in the phase's own report.
5. `git diff -U0` on `control_draw.py` removes exactly one line, and it is a docstring line.
6. Every allocator's `lookback` still `<= 473`; `max_shadow_depth(253) == 8` and
   `shadow_lookback_for(253, 9)` raises.
7. `git hash-object lab/lab.sqlite` is `607b78cf69c8e4e3a68a1e84c85eedfd1040c754` before and
   after.
8. Test-window looks 4 before, 4 after, asserted and stated.
9. Phase 3 can call `shadow_selection(replay, data_date, depth=SHADOW_DEPTH)` and
   `shadow_lookback_for(inner, SHADOW_DEPTH)` with no further change to `control_draw.py`.

---

## Assumptions

Things this phase expects to be true when it starts, each of which belongs to someone else.

- **Phase 1 has landed and its `## Contract for phase 2` block carries `stop: false`.** If
  `stop: true` — no affordable K reaches 0.90 on M0208 — a bounded replay is not the remedy and
  this phase does not run as designed. It stops and reports rather than shipping a replay
  nobody measured.
- **`shadow_needed` names at least M0208.** If phase 1 measures every chassis as a no-op, the
  replay still ships (it is the proof of the no-op) but phase 3 draws nothing, and the phase
  says so instead of inventing an arm.
- **`main` is at `e3aeeff` or later with no other phase's edits to `control_draw.py`.** The
  golden-vector literals are that commit's own output. If a peer phase has landed an edit to
  v1's bodies first, the literals must be re-derived — and that edit is itself an I3 violation
  to be raised, not accommodated.
- **`git hash-object lab/lab.sqlite` is `607b78cf69c8e4e3a68a1e84c85eedfd1040c754`.** Measured
  2026-10-20 at the start of this planning. If phase 1 moved it, phase 1 broke its own exit
  criterion; record the new value and carry on, because this phase does not touch the database.

---

## Handoffs

Work found and deliberately left where it belongs.

- **Wiring the shadow into any method file — phase 3 (R1).** This phase writes no method file.
  `m0208_capital_gains_overhang.py` keeps `MatchedDrawAllocator`, `MATCHED`, `_banded_picks`
  and the `MATCHED_DRAW` amendment exactly as they are; phase 3 appends a second allocator id,
  a `SHADOW_DEPTH` constant and a second `Amendment`. The `Replay` phase 3 writes for M0208 is
  `_banded_picks` applied to `scored(...)`'s order at the replayed date — the same band, called
  with the shadow instead of with `picks_prev`.
- **The quarterly cadence — not here, and probably not at all.** M0201 and M0202 move their
  basket on a quarterly clock and derive their own previous re-pick in their own method files,
  which is why `CADENCES` is `("monthly",)` and `previous_decision_date` refuses anything
  else. A quarterly replay would need a `CADENCES` entry, its own step constant, its own
  derivation and its own calendar test — the module docstring's own rule: *"A weekly or daily
  book needs its own derivation and must add it here with its own test rather than passing the
  monthly one a date it does not fit."* The analysis measured M0201's stand-in at 0.955, so
  the expected verdict is *no-op* and the cadence need not be added. **This phase adds none,**
  and `shadow_lookback_for`/`max_shadow_depth` are monthly-only by construction.
- **The weight axis — phase 5 (R2).** `control_weight.py` and the three weight-varying method
  files. Phase 5 quotes `control_draw` as it looks after this phase and edits none of it. The
  v2 docstring states outright that the shadow does not touch a weight, so phase 5's module
  need not argue the point again.
- **Stamping `SHADOW_RULE_ID` into a recorded arm's `params.as_dict()` — phase 3.** No method
  file stamps `RULE_ID` today; when phase 3 stamps one it stamps `SHADOW_RULE_ID`, and nothing
  in this module changes for it.
- **Consolidating the `SMOKE_BARS = 473` literal** duplicated at `test_lab_control_draw.py:43`
  and `test_lab_control_draw_twins.py:36`. `FIXTURE_BARS` now exists in the module and is
  asserted against the fixture's own session count, so both could point at it. **Left alone:**
  a drive-by cleanup across two files, one of which phase 5 owns.
- **`test_lab_control_draw_twins.py` is not opened by this phase** even though it carries that
  same literal. Phase 5 owns it.

---

## Rollback

```bash
cd /home/miftah/seer
git checkout -- engine/src/seer_engine/lab/control_draw.py \
                engine/tests/test_lab_control_draw.py
rm -f engine/tests/test_lab_control_draw_shadow.py
```
or `git revert` the single commit.

Nothing recorded moves either way, in either direction. v1's bodies were never edited (I3), no
allocator id changed, no params dataclass gained a field, no method file was opened, no `lab`
command was run and no trial was recorded. The thirteen recorded matched-draw arms are in
exactly the state they were in before this phase and would be in exactly that state after a
revert.

The one thing a revert loses that is worth naming: **the golden vector.** Reverting this phase
puts the tree back in the state where an in-place edit to the frozen path moves thirteen
recorded arms and nothing goes red. If the replay ever has to be backed out, **keep step 3.**
