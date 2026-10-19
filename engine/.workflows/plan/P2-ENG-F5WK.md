> Adopted from `/home/miftah/seer/.workflows/orchestration/honest-control-redraw/PLAN.md` phase 5. Source: `.workflows/plan/honest-control-redraw/phase-5.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 5: M0201 and M0202 — the rate-beta chassis, five arms

**Plan set:** `HONEST_CONTROL_REDRAW_PLAN.md`
**Analysis:** `docs/analyzer/20261019-181712-C4K9_code_analyzer.md`
**Satisfies:** R2 (re-draw the mis-shaped controls as amendments under the existing ids), R3 (re-state the margins in `trial_funding.mwr`, including those that worsen or reverse), R4 (the arm's own `supersedes` declaration — without it phase 2's D17 rule fires on nothing and the method stays blocked after the measurement)
**Depends on:** Phase 1 — `engine/src/seer_engine/lab/control_draw.py` must exist and export `matched_book`
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab/methods`

---

## Goal

M0201 and M0202 each hold a placebo pair (and M0202 a third arm) that trades about 2.25x the book
it controls, because M0187's `draw` is keyed on the month and re-draws the whole book at every
quarterly re-pick while the real book's 40% keep band holds most of its names. After this phase
each of the five has a re-drawn twin whose entry count is derived from the bond book's own
quarterly calendar, recorded under the same two method ids as amendment seq 1 on each, and five
margins are re-stated in `trial_funding.mwr` against the arm each twin actually controls —
including `M0202-Y20-HALF-FAST`, which the resolution ladder cannot reach today.

---

## Interface Contract

**Creates:**

- `m0201.MatchedSizedPlaceboAllocator` with `id = "M0201-A1"` (`m0201_treasury_beta_size_weighted.py`)
- `m0201.MATCHED`, `m0201.MATCHED_CONTROL_AMENDMENT`, `m0201.prev_repick_session`,
  `m0201.real_frac_at`, `m0201.matched_entries`, `m0201.matched_frac`, `m0201._vm`,
  `m0201.PREV_SPAN`, `m0201.MATCHED_LOOKBACK`, `m0201.REAL_SIDE`, `m0201.AMENDED`
- `m0202.MatchedHalfGuardPlaceboAllocator` with `id = "M0202-A1"` (`m0202_treasury_beta_half_guard.py`)
- `m0202.MATCHED`, `m0202.MATCHED_CONTROL_AMENDMENT`, `m0202.prev_repick_session`,
  `m0202.real_frac_at`, `m0202.matched_entries`, `m0202.matched_frac`, `m0202._vm`,
  `m0202.PREV_SPAN`, `m0202.MATCHED_LOOKBACK`, `m0202.REAL_SIDE`, `m0202.AMENDED`
- five candidates: `M0201-Y20-MV10-PLC1`, `M0201-Y20-MV10-PLC2`, `M0202-Y20-HALF-PLC1`,
  `M0202-Y20-HALF-PLC2`, `M0202-Y20-HALF-FAST-PLC1`
- two `method_amendments` rows, both **seq 1** (verified read-only 2026-10-19: the only amendment
  rows in the lab are M0030/1, M0053/1, M0225/1) and five `trials` + `trial_funding` rows

**Deletes:** nothing.
**Renames:** nothing.
**Signature changes:** none. `SizedYieldBetaParams` (`m0201:106-141`) and `HalfGuardParams`
(`m0202:84-115`) are **not touched** — no field added, removed or reordered. Both new allocators
reuse the existing params classes unchanged.

**Requires (from earlier phases):**

- Phase 1's `engine/src/seer_engine/lab/control_draw.py`, exporting

  ```python
  def matched_partition(
      *,
      pool: Sequence[str],
      held: AbstractSet[str],
      keep_n: int,
      tag: str,
      seed: int,
      data_date: date,
  ) -> tuple[list[str], list[str]]:
      """``(keep, tail)``.

      ``keep`` is at most ``keep_n`` names of ``held & pool`` in a **date-free** hash order of
      ``(tag, seed, symbol)``, so a name the control already holds keeps the same key from
      quarter to quarter and the keep set never churns on its own. ``tail`` is every other name
      of ``pool`` in the order the control would take it: the names it does **not** hold first,
      in a hash order keyed on ``(tag, seed, symbol, data_date``'s month``)`` -- M0187's
      ``draw``, generalised by ``tag`` -- and the holdings it is dropping **last**. Together they
      cover ``set(pool)`` exactly once.
      """
  ```

  **Reconciled 2026-10-19 against Phase 1's actual module.** Three differences from this plan's
  first draft, all applied below: the function is `matched_partition`, not `matched_book` (which
  in Phase 1's module takes a `select` callable and returns a finished book of a known size,
  which is not what a keep-band chassis can use); it takes `keep_n` rather than `size` and
  `entries`, so this file computes `keep_n = top - matched_entries(...)` at the call site; and it
  takes a `tag` naming the hash namespace, which is the **book's** method id, so M0201 passes
  `tag="M0201"` and M0202 passes `tag="M0202"`.

  **The `tail` ordering this phase depends on is now a guarantee of the module, and Phase 1 was
  edited to provide it.** Phase 1's first draft filled its book from the whole eligible pool in
  entry order, which could take a just-dropped holding straight back; the reconciled
  `matched_partition` sorts every non-held name ahead of every dropped holding, documents that as
  its contract, and `test_a_dropped_holding_is_never_re_taken_ahead_of_a_fresh_name` pins it.
  This phase's measured **0.9549** was taken on a walk with that ordering, so the measurement
  stands.

- Phase 1's `control_draw.churn(now, prev)` -- `len(set(now) - set(prev))`, used nowhere in this
  phase's entry count (which is a keep-band count, not a set difference) but imported for the
  one place `matched_entries`'s docstring contrasts the two.

- Phase 1's `backtest.dev.Candidate.supersedes` field, which each of the five new arms carries.

**Leaves alone (owned by others):**

- `engine/src/seer_engine/lab/control_draw.py` (Phase 1 — consumed unchanged, never edited)
- `engine/src/seer_engine/lab/control_shape.py`, `hardgate.py`, `commands/lab.py` (Phase 2)
- every other method file, including `m0197_treasury_yield_beta.py` and
  `m0187_placebo_hash_order.py`, which are imported and never modified
- `lab stage`, `web/data/lab.json`, `lab/lab.sqlite`'s staging (Phase 8)
- `M0201-OPP-MV10` and `M0202-N20-HALF` — paired contrasts, not placebos, never shape-checked

---

## The measured state this phase starts from

Read-only `sqlite3 "file:/home/miftah/seer/lab/lab.sqlite?mode=ro"`, 2026-10-19.
`git hash-object lab/lab.sqlite` = `3969f1fa5d2066a42ed47716dd05a66050073592` before and after.
SPY TR on the same deposits is **7.188%/yr** for all twelve rows.

| arm | trial | trades | turnover | `mwr` % | ratio vs its target |
|---|---|---|---|---|---|
| `M0201-Y20-MV10` | 725 | 433 | 2.4213 | **9.543** | — |
| `M0201-PLC1-MV10` | 729 | 981 | 5.1687 | 10.255 | 2.266 / 2.134 **refuse** |
| `M0201-PLC2-MV10` | 730 | 979 | 5.1260 | 8.065 | 2.261 / 2.117 **refuse** |
| `M0202-Y20-HALF` | 662 | 440 | 2.3529 | **12.653** | — |
| `M0202-Y20-HALF-FAST` | 663 | 440 | 2.7063 | **12.141** | — |
| `M0202-PLC1-HALF` | 665 | 989 | 4.7185 | 11.301 | 2.248 / 2.006 **refuse** |
| `M0202-PLC2-HALF` | 666 | 988 | 4.6888 | 9.564 | 2.245 / 1.993 **refuse** |
| `M0202-PLC1-HALF-FAST` | 667 | 989 | 5.1764 | 11.381 | see below |

`M0202-PLC1-HALF-FAST` resolves today to `M0202-Y20-HALF` (2.248 / 2.200) because its stem
`M0202-PLC1-HALF` is itself a placebo and `_eligible_targets` excludes it. Against its **true**
target `M0202-Y20-HALF-FAST` it is **2.248 / 1.913** — still a refusal, on trades. Both numbers go
in the report (care point (b)).

**The five standing margins, in `mwr`, as they read today:**

| book | control | margin |
|---|---|---|
| `M0201-Y20-MV10` 9.543 | `PLC1-MV10` 10.255 | **−0.712 pts — the book LOSES** |
| `M0201-Y20-MV10` 9.543 | `PLC2-MV10` 8.065 | +1.478 pts |
| `M0202-Y20-HALF` 12.653 | `PLC1-HALF` 11.301 | +1.352 pts |
| `M0202-Y20-HALF` 12.653 | `PLC2-HALF` 9.564 | +3.089 pts |
| `M0202-Y20-HALF-FAST` 12.141 | `PLC1-HALF-FAST` 11.381 | +0.760 pts |

**M0201's placebo spread already straddles its book**, before the shape is repaired: seed 1 earns
10.255 against the book's 9.543 and seed 2 earns 8.065. M0201's own success condition —
*"Y20-MV10 keeps a clear gap (2+ points a year on the deposits) over both OPP-MV10 and the sized
placebo seeds"* — is therefore **already failed on the handicapped pair**, and the pre-registered
direction says an honest control earns more, which can only make it worse. M0202's condition
(*"beats its own same-guard placebo seeds by at least 2 points a year"*) is likewise already failed
by `PLC1-HALF` (+1.352) and by `PLC1-HALF-FAST` (+0.760). Say both of these plainly in the report;
neither is a new finding of this phase, and both must not be presented as one.

---

## The rule, and why it is applied once for both files

### Why these five trade 2.25x

`SizedYieldBetaAllocator._run` (`m0201:261-276`) and `HalfGuardAllocator._run` (`m0202:193-206`)
are the same chassis: `repick = not stocks or data_date.month in REPICK_MONTHS` (3, 6, 9, 12), and
on a re-pick `frac` goes to M0197's `choose` (`m0197:182-213`), which keeps a holding whose rank
fraction is under `keep_pct/100 = 0.40` and fills the rest of the twenty slots from the top of the
order.

For the bond side the yield loadings persist, so a held name is almost always still in the top 40%
of a ~400-name pool and the band keeps it. For the placebo, `ranked` (`m0201:160-167`,
`m0202:151-160`) orders by `draw(seed, symbol, data_date)` — M0187's hash **re-keyed on the month**
(`m0187:98-101`) — so a held name's new fraction is uniform and it survives the band with
probability 0.40. Twelve of twenty names turn over every quarter instead of five or six. That is
the whole of the 2.25x.

### The rule

Rule A, churn-matched, as the analysis describes it: at each re-pick, recompute the real bond
book's own selection at **this** date and at the **previous** re-pick, derive how many names the
real book takes in, keep that many fewer of the control's own holdings, and draw the rest blind.

The one chassis-specific step — and the reason it is stated here rather than inside
`control_draw.py` — is that this chassis's churn is governed by the **keep band**, not by the
symmetric difference of two top-20 lists. `|top20_now \ top20_prev|` over-counts badly, because a
name that slips from rank 18 to rank 40 is kept by the band and is not an entry. So:

> `entries` = 20 − (how many of the bond book's previous-quarter top 20 are still under the 40%
> band today), floored at 0.

`control_draw.matched_book` then turns `entries` into a book, and the book is expressed back to
`choose` as a `frac` dict: the names to keep laid out **under** 0.40 in keep order, everything else
**above** it in the order the control would take it. `choose` is called unchanged, so the band, the
quarterly calendar, the SPY filler, the sizing and the guard are all byte-identical to the arm
being controlled.

### Measured, not estimated (2026-10-19, read-only, dev store)

A symbol-only walk of the chassis over the dev window's 79 re-picks
(`/tmp/.../scratchpad/churn.py`, `control_path.py`, `control_path2.py`; no lab command, no write,
`lab.sqlite` hash unchanged):

| book | re-picks | entries | mean/quarter | ratio vs the real book |
|---|---|---|---|---|
| real bond book (`Y20`) | 79 | 443 | 5.608 | — |
| today's `PLC1` (month-keyed) | 79 | 992 | 12.557 | **2.239** |
| today's `PLC2` (month-keyed) | 79 | 983 | 12.443 | **2.219** |
| matched draw, **true** historical membership at the previous quarter | 79 | 445 | 5.633 | **1.0045** |
| matched draw, **today's** member set at the previous quarter | 79 | 423 | 5.354 | **0.9549** |

Two things this establishes.

1. The walk reproduces the recorded refusals (2.239 / 2.219 against the recorded 2.266 / 2.261 —
   the small gap is the monthly resize trades a symbol-only walk cannot see), so it is measuring
   the right thing.
2. The matched draw lands at **0.955**, inside `WARN_BAND = (0.80, 1.25)` with room on both sides.

**Why 0.955 and not 1.0045.** An allocator is handed `members` for its own session only; there is
no membership object on `YieldBetaPrepared` (`m0197:116-120`), which M0202 uses. Reading the
previous quarter with today's member set is look-ahead-safe (it uses no data the session does not
already have) and costs 4.5 points of match quality. The alternative — M0201 could reach
`prepared.market.membership` because `SizedPrepared` carries the Market (`m0201:150-155`), M0202
could not — would make the two amendments use **different** rules on the same chassis, which is
exactly what pairing them in one phase exists to prevent. The 0.955 rule is taken, in both files,
and the 1.0045 alternative is recorded here as the measurement that was not used.

**Both files get the same number.** M0201 and M0202 share M0197's `scored`, `choose`, `top = 20`,
`keep_pct = 40` and `REPICK_MONTHS`; their recorded book arms are 433 and 440 trades, the same book.
The walk above was run on M0201's prepared data and applies unchanged to M0202.

### The lookback, and why raising it moves no window

`loadings` (`m0197:122-162`) needs `WEEKS * STEP = 260` bars before the date it reads. The control
reads the previous re-pick, ~63 sessions back, so it needs 260 + 70 + 1 = **331** bars where the
base allocators declare 253.

`lookback` does not truncate history — it is read **only** by `backtest.dev.candidate_window`
(`dev.py:291-298`) to decide where the window opens. Measured on the dev store: SPY's 253rd bar is
1994-01-27 and its **331st is 1994-05-19**, both far before `MEMBERSHIP_START = 1996-01-02`
(`dev.py:75`), and both allocators set `uses_members → True`, so

    ready = max(MEMBERSHIP_START, SPY.dates[lookback - 1]) = 1996-01-02 either way.

**The re-drawn arm runs over exactly the same window as the arm it controls.** On the smoke fixture
(473 SPY bars, 2013-12-02 … 2015-10-16) the 331st bar is 2015-03-26, leaving 142 sessions — enough
for `test_candidate_runs_a_smoke_window`'s `len(result.snapshots) >= 2`, and 331 ≤ 473 clears
invariant 11 with 142 bars to spare.

### `config_digest` safety

`registry._canon` (`registry.py:323-332`) renders a dataclass by `dataclasses.fields()`, so **any**
change to a params class moves every recorded digest that used it. This phase changes **no params
class at all**. Both new allocators reuse `SizedYieldBetaParams` / `HalfGuardParams` exactly as
built by the existing `_p` helpers; the configuration differs only in `config_text`'s
`allocator=<...>` line.

Verified by computing `sha256(config_text)` for all five planned candidates, 2026-10-19:

```
M0201-Y20-MV10-PLC1        daed999f5194b577...   M0201-A1 + _p("placebo", seed=1)
M0201-Y20-MV10-PLC2        28a3551df619fc35...   M0201-A1 + _p("placebo", seed=2)
M0202-Y20-HALF-PLC1        71008457d57ddfd4...   M0202-A1 + _p("placebo", "half", seed=1)
M0202-Y20-HALF-PLC2        eb0dec81b553de7e...   M0202-A1 + _p("placebo", "half", seed=2)
M0202-Y20-HALF-FAST-PLC1   24509603ad007e66...   M0202-A1 + _p("placebo", "half-fast", seed=1)

five distinct: True
collision with any existing M0201/M0202 candidate: none
collision with any recorded trial digest: none
```

### `Method.__post_init__` uniqueness (`method.py:157+`)

One shared `ids` set and one shared `digests` set across the originals and every amendment.

- **ids:** `M0201-Y20-MV10-PLC1/-PLC2` and `M0202-Y20-HALF-PLC1/-PLC2/-Y20-HALF-FAST-PLC1` appear
  nowhere in either file's six originals (verified by enumerating `all_candidates()`).
- **configurations:** the five digests above are distinct from each other and from all twelve
  recorded ones. Note the three M0202 arms are distinct from **each other** by params alone —
  `(guard="half", seed=1)`, `(guard="half", seed=2)`, `(guard="half-fast", seed=1)` — so they would
  be distinct even under one allocator id; the new id is what separates them from the originals.
- `MAX_VARIANTS = 6` is **per amendment**: 2 for M0201, 3 for M0202. Both clear it.
- `test_allocator_ids_are_unique_across_methods` (`test_lab_methods.py:108`): `M0201-A1` and
  `M0202-A1` are free — grep over `engine/src/seer_engine/` finds only `id = "M0201"`
  (`m0201:241`) and `id = "M0202"` (`m0202:177`).

---

## The `resolve_target` walk for all five ids

Run against the projected arm list (six originals + the new ones) with
`control_shape.resolve_target`, 2026-10-19:

| new id | stem | stem arm exists | stem's `kind_of` | resolved | rung |
|---|---|---|---|---|---|
| `M0201-Y20-MV10-PLC1` | `M0201-Y20-MV10` | yes | `''` (not placebo, not dose) | `M0201-Y20-MV10` | **sibling-stem** |
| `M0201-Y20-MV10-PLC2` | `M0201-Y20-MV10` | yes | `''` | `M0201-Y20-MV10` | **sibling-stem** |
| `M0202-Y20-HALF-PLC1` | `M0202-Y20-HALF` | yes | `''` | `M0202-Y20-HALF` | **sibling-stem** |
| `M0202-Y20-HALF-PLC2` | `M0202-Y20-HALF` | yes | `''` | `M0202-Y20-HALF` | **sibling-stem** |
| `M0202-Y20-HALF-FAST-PLC1` | `M0202-Y20-HALF-FAST` | yes | `''` | `M0202-Y20-HALF-FAST` | **sibling-stem** |

All five land on the strongest rung, on the arm intended, with no guess. Care point (b) is
discharged by the id: `M0202-Y20-HALF-FAST-PLC1`'s stem is a real, non-placebo, non-dose arm, so
the ladder reaches `Y20-HALF-FAST` where `M0202-PLC1-HALF-FAST` could not.

`kind_of` on each new rationale returns `placebo` with `DOSE_MARKERS` hits `[]` and `DRAW_MARKERS`
hits `['placebo', 'hash order']`. None of the five carries `"dose-response"`, `"dose:"`,
`"and not since"`, `"and none since"`, `"does the date do any work"` or `"on the date itself"`
(invariant 3).

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/methods/m0201_treasury_beta_size_weighted.py` | modify | docstring paragraph; three import lines; a 95-line amendment block between `_v` (:316) and `METHOD` (:319); `amendments=` on `METHOD` |
| `engine/src/seer_engine/lab/methods/m0202_treasury_beta_half_guard.py` | modify | docstring paragraph; four import lines; a 95-line amendment block between `_v` (:243) and `METHOD` (:246); `amendments=` on `METHOD` |
| `.workflows/plan/honest-control-redraw/phase-5-results.md` | create | the block in **What to record for phase 8**, filled in |

Nothing else. Two commits, two runs, in that order, one file each, then the results file.

**No new params dataclass, by the set's one rule.** This phase already reused
`SizedYieldBetaParams` and `HalfGuardParams`, which is now the rule for all nine methods (index
invariant: "One params value, one new allocator id"). Phases 1, 4 and 7 each minted one in their
first drafts and all three were deleted in reconciliation; this phase's approach is the one the
set adopted.

### Why the ~45-line chassis adapter is duplicated and not shared

`prev_repick_session`, `real_frac_at`, `matched_entries` and `matched_frac` are written out in
**both** files rather than imported from one into the other. Importing M0202's copy from M0201
would make M0202's recorded trials depend on M0201's file contents while only M0201's
`method_amendments.source_sha` moved — a later edit to M0201 would silently change what M0202's
arms mean, and `store.latest_source_sha` would not notice. One amendment, one file, one sha. The
genuinely shared part — the draw itself — lives in `control_draw.py`, which is where phase 1 put it.

---

## Implementation Steps

### Step 1: M0201 — the docstring paragraph

**File:** `engine/src/seer_engine/lab/methods/m0201_treasury_beta_size_weighted.py:45` (inside the
module docstring, replacing the paragraph that begins "Controls in the same frame:")

**Change:** say what the amendment is and why, in the file's own prose style.

**Code:**

```python
Controls in the same frame: ``side="opp"`` (M0197's rate-rising side, the paired control) and
``side="placebo"``, M0202's hash order over exactly the names M0197's loadings could score that
day (M0187's ``draw``), sized the same way -- the meaningless book of the same shape.

Amendment 1 (2026-10-19), the shape-matched placebo. The two placebo seeds above trade 2.27x and
2.26x the book they control and turn over 2.13x and 2.12x it, so the gap they were quoted for was
read against an opponent paying twice the fees, and D17 refuses the method on it. The cause is the
re-key period, chosen by hand: M0187's ``draw`` is keyed on the month, so the whole book is re-drawn
at every quarterly re-pick, while the real book's 40% keep band holds a name unless it slips out of
the top 40% of the pool. ``Y20-MV10-PLC1`` and ``Y20-MV10-PLC2`` keep the frame, the sizing, the
ceiling and the seeds and derive the re-key from the bond book's own calendar instead: at each
re-pick the allocator re-reads M0197's bond ranking at this date and at the previous quarter's
re-pick, counts how many of that quarter's twenty are still under the band, and lets the blind draw
replace exactly the rest. Measured over the dev window's 79 re-picks before any of this ran: 423
entries against the real book's 443, a ratio of 0.955, where the recorded pair sits at 2.24. The
cost is the lookback -- 331 bars instead of 253, a year of weekly marks before the previous
re-pick -- which moves no window, because SPY's 331st bar is 1994-05-19 and the member index opens
1996-01-02.
```

**Impact:** the file's sha moves, which is what the amendment commit is for. No behaviour change.

---

### Step 2: M0201 — the imports

**File:** `engine/src/seer_engine/lab/methods/m0201_treasury_beta_size_weighted.py:67-76`

**Change:** add `Amendment`, `matched_book`, and `STEP`/`WEEKS`.

**Code:** replace lines 67-76 with

```python
from seer_engine.lab.control_draw import matched_partition
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0034_size_tilt_residual import _apply_ceiling, _floor_weight
from seer_engine.lab.methods.m0187_placebo_hash_order import draw
from seer_engine.lab.methods.m0197_treasury_yield_beta import (
    REPICK_MONTHS,
    STEP,
    WEEKS,
    YieldBetaParams,
    choose,
    loadings,
)
from seer_engine.lab.methods.m0197_treasury_yield_beta import scored as yb_scored
```

**Impact:** `draw` and `loadings` stay — the original `ranked` still uses both. `numpy as np`
(:63), `Mapping`/`AbstractSet` (:56-57), `replace` (:58), `date` (:59), `Target` (:78),
`MONTHLY_HOLD_FRAC_GOTRADE` (:79), `Candidate` (:65), `EXCLUDED`/`factor_rows`/`trend_on` (:82-91)
are all already imported. `test_method_source_is_pure` (`test_lab_methods.py:62`) forbids only
`seer_engine.research` and `seer_engine.lab.store`; `seer_engine.lab.control_draw` is neither.

---

### Step 3: M0201 — the amendment block

**File:** `engine/src/seer_engine/lab/methods/m0201_treasury_beta_size_weighted.py` — insert
between `_v` (ends :316) and `METHOD = Method(` (:319)

**Change:** the allocator, its adapter, the candidate factory and the `Amendment`.

**Code:**

```python
# ------------------------------------------------------------------ amendment 1 (2026-10-19)
#
# The shape-matched placebo. See the module docstring for why the recorded pair trades 2.27x the
# book it controls; what follows is the repair. Nothing above this line changes: a new allocator
# id is the only safe way to add an arm, because `registry._canon` renders a params dataclass by
# `dataclasses.fields()` and a field added to `SizedYieldBetaParams` -- even a defaulted one --
# would move every recorded config_digest that used it.

AMENDED = date(2026, 10, 19)
PREV_SPAN = 70  # sessions in a quarter, with room for the longest one in the dev window
MATCHED_LOOKBACK = WEEKS * STEP + PREV_SPAN + 1  # 331: a year of weekly marks before the previous
                                                 # re-pick, which the matched draw re-reads
REAL_SIDE = "bond"  # the side of the book these two arms are the controls for


def prev_repick_session(history: Mapping[str, History], data_date: date,
                        market: str) -> date | None:
    """The session this chassis last re-picked on, or None when the history does not reach it.

    Derived from the calendar, never carried in state: an allocator is called once per session and
    holds nothing between calls. The rules are ``monthly-hold-frac-gotrade``, so a decision session
    is the first session of a month and the ``data_date`` the allocator is handed is the last
    session of the month before it; a re-pick month is one of ``REPICK_MONTHS``, three apart. So
    the previous re-pick's data date is the last session ``market`` printed in the month three
    calendar months back. The search is bounded by ``data_date``'s own index, so it can see no bar
    the session cannot.
    """
    h = history.get(market)
    if h is None:
        return None
    i = h.index_of(data_date)
    if i is None:
        return None
    year, month = data_date.year, data_date.month - 3
    if month <= 0:
        year, month = year - 1, month + 12
    after = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    k = int(np.searchsorted(h.dates[: i + 1], np.datetime64(after, "D"), side="left")) - 1
    if k < 0:
        return None
    out = h.dates[k].item()
    return out if (out.year, out.month) == (year, month) else None


def real_frac_at(prepared: SizedPrepared, members: AbstractSet[str], data_date: date,
                 p: SizedYieldBetaParams) -> dict[str, float]:
    """M0197's own bond-side rank fractions on ``data_date``, over ``members``.

    ``members`` is the set the allocator was handed for its own session and is used unchanged at
    the previous quarter: a control is never given the membership of a past date, and reading
    today's set backwards uses no data the session does not already have. It costs match quality
    and the cost was measured before this ran -- 0.955 against 1.0045 with the true historical
    sets -- and is paid so that M0201 and M0202, whose ``prepared`` types differ, run the identical
    rule.
    """
    inner = p.yb.inner
    if prepared.factor is None:
        rows = factor_rows(prepared.history, members, data_date, inner)
    else:
        rows = prepared.factor.rows_on(members, data_date, inner)
    return yb_scored(prepared.history, prepared.series, rows, data_date,
                     replace(p.yb, side=REAL_SIDE))


def matched_entries(prepared: SizedPrepared, members: AbstractSet[str], data_date: date,
                    now: Mapping[str, float], p: SizedYieldBetaParams) -> int:
    """How many names the bond book itself takes in on ``data_date``.

    Its own keep band, applied to the book it would have held at the previous quarter's re-pick:
    every name of that book still under ``keep_pct`` stays, and the rest of the twenty slots are
    entries. The band and not a symmetric difference, because a name that slips from rank 18 to
    rank 40 is kept by this chassis and is not an entry; counting ``|top20_now \\ top20_prev||``
    would over-state the churn and re-make the error this amendment exists to undo. With no
    previous re-pick in reach the whole book is an entry, which is what the chassis does on its
    first session anyway.
    """
    top = p.yb.inner.top
    before_date = prev_repick_session(prepared.history, data_date, p.yb.market)
    if before_date is None:
        return top
    before = real_frac_at(prepared, members, before_date, p)
    if not before:
        return top
    book = [s for _, s in sorted((v, s) for s, v in before.items())][:top]
    cut = p.yb.keep_pct / 100.0
    kept = min(sum(1 for s in book if now.get(s, 1.0) < cut), top)
    return max(0, top - kept)


def matched_frac(prepared: SizedPrepared, members: AbstractSet[str], data_date: date,
                 held: frozenset[str], p: SizedYieldBetaParams) -> dict[str, float]:
    """Rank fractions that drive M0197's ``choose`` to a blind book of the bond book's own shape.

    ``choose`` keeps a holding whose fraction is under ``keep_pct`` and fills the rest of the
    twenty slots from the top of the order, so a fraction below the band is an instruction to hold
    and one above it an instruction to enter. The names the matched draw keeps are laid out under
    the band in keep order, and every other name above it in the order the control would take it.
    ``choose`` itself is called unchanged, so the band, the quarterly calendar, the ceiling, the
    sizing and the SPY filler are byte-identical to the arm this controls; the only thing that
    differs is which names fill the slots.
    """
    now = real_frac_at(prepared, members, data_date, p)
    if not now:
        return {}
    cut = p.yb.keep_pct / 100.0
    top = p.yb.inner.top
    keep, tail = matched_partition(
        pool=sorted(now),
        held=held,
        keep_n=max(0, top - matched_entries(prepared, members, data_date, now, p)),
        tag="M0201",
        seed=p.seed,
        data_date=data_date,
    )
    out: dict[str, float] = {s: cut * (i + 1) / (len(keep) + 1) for i, s in enumerate(keep)}
    for j, s in enumerate(tail):
        out[s] = cut + (1.0 - cut) * (j + 1) / (len(tail) + 1)
    return out


class MatchedSizedPlaceboAllocator(SizedYieldBetaAllocator):
    """M0201's sized book filled by a blind draw of the bond book's own shape, under its own id.

    Everything but the order is ``SizedYieldBetaAllocator``'s: the screen, the band, the quarterly
    calendar, the sizing by company, the 10% ceiling and the SPY filler. Two things change. The
    order on a re-pick comes from ``matched_frac`` instead of ``ranked``. And the lookback rises to
    ``MATCHED_LOOKBACK``, because this control re-reads the bond ranking at the previous quarter's
    re-pick and ``loadings`` wants a year of weekly marks before whatever date it is given; the
    rise moves no window, since ``candidate_window`` floors at the member index's 1996-01-02 and
    SPY's 331st bar is 1994-05-19.
    """

    id = "M0201-A1"

    def lookback(self, params: Any) -> int:
        return max(super().lookback(params), MATCHED_LOOKBACK)

    def _run(self, prepared: SizedPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: SizedYieldBetaParams) -> tuple[Target, ...]:
        if len(prepared.series) == 0 or prepared.market is None:  # market-aware contract
            return ()
        inner = p.yb.inner
        if not trend_on(prepared.history, data_date, inner):
            return ()
        stocks = [s for s in held if s != p.yb.market and s not in EXCLUDED]
        repick = not stocks or data_date.month in REPICK_MONTHS
        frac = matched_frac(prepared, members, data_date, held, p) if repick else {}
        equal = choose(prepared.history, members, frac, data_date, held, p.yb)
        return resize(prepared, equal, data_date, p)


MATCHED = MatchedSizedPlaceboAllocator()


def _vm(suffix: str, params: SizedYieldBetaParams, rationale: str,
        supersedes: tuple[str, ...]) -> Candidate:
    """An amendment candidate, with the declaration of which recorded arm it replaces.

    ``supersedes`` is what D17 reads (``control_shape.SUPERSEDES_ATTR``): declared, never
    inferred from the target, and outside ``config_digest`` because ``config_text`` names its
    three attributes by hand. An arm that declares nothing retires nothing, so omitting it would
    leave M0201 blocked after the measurement was taken."""
    return Candidate(id=f"M0201-{suffix}", family="M0201", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=MATCHED, params=params, rationale=rationale, added=AMENDED,
                     owner_inputs=(), supersedes=supersedes)


MATCHED_CONTROL_AMENDMENT = Amendment(
    added=AMENDED,
    why=(
        "The sized placebo re-drawn to the bond book's own churn, because the recorded pair "
        "trades 2.27x and 2.26x the book it controls and the gap was quoted against it"
    ),
    hypothesis=(
        "Written before any result. PLC1-MV10 and PLC2-MV10 order the same scoreable names by a "
        "hash re-keyed every month, so the whole book is re-drawn at every quarterly re-pick "
        "while Y20-MV10's own 40% keep band holds about fourteen of its twenty names; measured, "
        "they trade 2.27x and 2.26x it and turn over 2.13x and 2.12x it, outside D17's refuse "
        "band. These two arms keep the frame, the sizing, the 10% ceiling and the seeds and "
        "change only where the re-key comes from: at each re-pick the blind draw replaces exactly "
        "as many names as the bond book's own band lets go, counted by re-reading M0197's bond "
        "ranking at this date and at the previous quarter's re-pick. The direction, "
        "pre-registered: a control that traded 2.25x was over-paying Gotrade's fees on about "
        "twelve entries a quarter instead of five or six, so an honestly-shaped replacement pays "
        "less and earns MORE, and every lead quoted against the old pair NARROWS or REVERSES. "
        "Concretely, against Y20-MV10's 9.54% a year on the deposits (SPY TR 7.19%): PLC1-MV10's "
        "10.26% rises further, so the book's recorded -0.71 point deficit against seed 1 gets "
        "worse; PLC2-MV10's 8.06% rises, so the +1.48 point lead over seed 2 shrinks and may "
        "cross zero. The two-seed spread is kept deliberately, so the lead is read against a "
        "spread and not a single draw, and the spread already straddles the book before this "
        "runs. Success for the amendment is only this: both new arms land inside 0.80x-1.25x on "
        "trades and on turnover against Y20-MV10. Whatever the margin then says is the finding "
        "and is reported as it comes; no seed is tuned and no arm is re-drawn for a better one."
    ),
    expected_failure=(
        "The shape may match and the lead may still move the other way, and if it does the cause "
        "is not fees but name identity: a blind book of twenty members drawn with the real book's "
        "churn still holds a different twenty, and over 1996-2015 the dev store's surviving "
        "members earned enough that a random slow-turning book can beat a utilities-and-REITs "
        "book on luck alone -- seed 2's 8.06% against seed 1's 10.26% is already a 2.2 point "
        "spread between two draws of the same rule. Second, the match itself may miss: the "
        "entry count is derived by re-reading the bond ranking at the previous quarter with "
        "today's member set, which the walk put at 0.955 of the real book's entries, and the "
        "turnover axis carries an extra risk this trade-count derivation does not control -- "
        "M0201 re-sizes monthly by company size, and a blind book holds mega-caps the bond book "
        "never does, so its weight dispersion and its monthly resize trades differ even when its "
        "entries match. If either arm lands outside the band on turnover the amendment has failed "
        "its own test and the number is recorded as the failure, not corrected."
    ),
    candidates=(
        _vm("Y20-MV10-PLC1", _p("placebo", seed=1),
            "Placebo, shape-matched: the same scoreable names in a hash order (seed 1), re-drawn "
            "only as often as the bond book's own picks turn over, sized by market value",
            supersedes=("M0201-PLC1-MV10",)),
        _vm("Y20-MV10-PLC2", _p("placebo", seed=2),
            "Placebo, shape-matched: hash order seed 2, the same matched churn, sized by market "
            "value",
            supersedes=("M0201-PLC2-MV10",)),
    ),
)
```

**Impact:** two new candidates under `M0201`, a new allocator id, no existing arm touched. Note
`matched_entries`'s docstring escapes the backslash (`\\`) so the set-difference reads literally
and the docstring is not a deprecated escape; `ruff` E9/F is clean either way.

---

### Step 4: M0201 — hang the amendment on `METHOD`

**File:** `engine/src/seer_engine/lab/methods/m0201_treasury_beta_size_weighted.py:388-392`

**Change:** add `amendments=`.

**Code:** replace lines 388-392 with

```python
    seen_keys=(
        "concept:treasury-beta-size-weighted",
        "concept:market-value-weighting",
    ),
    amendments=(MATCHED_CONTROL_AMENDMENT,),
)
```

**Impact:** `Method.all_candidates()` now returns eight; `runner.pending_amendment` finds
`amendments[0]` because M0201 has no recorded `method_amendments` row.

---

### Step 5: M0201 — verify, then commit, then run

**Change:** the commit is the pre-registration (invariant 2). Nothing below is run before the file
is committed.

**Code:**

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
export SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite
export SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research
export PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src
PY=/home/miftah/seer/engine/.venv/bin/python
LOG=/tmp/claude-1000/-home-miftah-seer/phase5
mkdir -p "$LOG"

# (a) the file imports, the digests did not move, the five ids resolve
$PY -m pytest engine/tests/test_lab_methods.py -q
$PY -m ruff check engine

# (b) the rationales carry a draw marker and no dose marker
$PY - <<'EOF'
from seer_engine.lab import control_shape as cs
from seer_engine.lab.methods.m0201_treasury_beta_size_weighted import METHOD
arms = METHOD.all_candidates()
for c in arms[6:]:
    assert cs.kind_of(c) == cs.KIND_PLACEBO, (c.id, cs.kind_of(c))
    assert not [m for m in cs.DOSE_MARKERS if m in c.rationale.lower()], c.id
    print(c.id, cs.resolve_target(c, arms))
EOF
# expect: ('M0201-Y20-MV10', 'sibling-stem') for both

# (c) the database's hash before anything touches it
git hash-object /home/miftah/seer/lab/lab.sqlite    # expect 3969f1fa5d2066a42ed47716dd05a66050073592

# (d) the pre-registration commit -- by pathspec, this file only, no `git add`:
#     the checkout is shared and `git commit -- <path>` commits the working tree at that path
#     and ignores whatever another session has staged (invariant 9).
git commit -m "$(cat <<'EOF'
lab: M0201 amendment 1 pre-registered — the sized placebo re-drawn to the bond book's own churn

PLC1-MV10 and PLC2-MV10 trade 2.27x and 2.26x the book they control and turn over 2.13x and
2.12x it: M0187's hash is re-keyed every month, so the whole book is re-drawn at every quarterly
re-pick while Y20-MV10's 40% keep band holds most of its names. D17 refuses the method on it.
Y20-MV10-PLC1 and Y20-MV10-PLC2 keep the frame, the sizing, the ceiling and the seeds and derive
the re-key from the bond book's own calendar. Measured on the dev window's 79 re-picks before
this ran: 423 entries against the real book's 443, 0.955, where the recorded pair sits at 2.24.
Family B, so the pre-registered direction is that an honestly-shaped control pays less, earns
more, and every lead narrows or reverses.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)" -- engine/src/seer_engine/lab/methods/m0201_treasury_beta_size_weighted.py

git status --porcelain -- engine/src/seer_engine/lab/methods/m0201_treasury_beta_size_weighted.py
# must print nothing: `runner.preflight` refuses a dirty or untracked method file

# (e) the run. NEVER through a pipe -- grep would own the exit status.
$PY -m seer_engine lab run M0201 --amend > "$LOG/m0201_run.log" 2>&1
echo "lab run M0201 --amend exit=$?"      # 0 ok, 2 the lab refused, 1 an error
cat "$LOG/m0201_run.log"

# (f) the hash after, and the shape
git hash-object /home/miftah/seer/lab/lab.sqlite    # expect a NEW hash; record it
$PY -m seer_engine lab control M0201 > "$LOG/m0201_control.log" 2>&1
echo "lab control M0201 exit=$?"
cat "$LOG/m0201_control.log"
```

**Impact:** two `trials` rows, two `trial_funding` rows, one `method_amendments` row (M0201, seq 1).
Irreversible — `trials`, `trial_funding` and `method_amendments` all carry append-only triggers on
update **and** delete.

**Stop condition:** if either new arm reads outside `0.80x-1.25x` on trades **or** on turnover,
record the two ratios and **stop**. Do not change a seed, do not re-derive the entry count, do not
add a second amendment to chase the band (invariant 4, design §4). Report the miss and hand it to
phase 8.

---

### Step 6: M0202 — the docstring paragraph

**File:** `engine/src/seer_engine/lab/methods/m0202_treasury_beta_half_guard.py:30-34` (replacing
the "Controls on the same frame" paragraph)

**Code:**

```python
Controls on the same frame and the same guard: ``side="neutral"`` (M0197's rate-neutral ranking,
smallest absolute loading; M0197 showed it carries no information) and ``side="placebo"``, which
orders exactly the names M0197's loadings could score by M0187's hash of (seed, symbol, month) --
the frame with no idea in it. Two placebo seeds under "half" and one under "half-fast", so the
idea's lead is read against a spread and not a single draw.

Amendment 1 (2026-10-19), the shape-matched placebo. Those three arms trade about 2.25x the book
each controls and turn over 1.99x to 2.20x it, so every gap quoted against them was read against an
opponent paying twice the fees, and D17 refuses the method on it. The cause is the re-key period,
chosen by hand: M0187's hash is keyed on the month, so the whole book is re-drawn at every
quarterly re-pick, while M0197's 40% keep band holds a name unless it slips out of the top 40% of
the pool. ``Y20-HALF-PLC1``, ``Y20-HALF-PLC2`` and ``Y20-HALF-FAST-PLC1`` keep the frame, the
guard and the seeds and derive the re-key from the bond book's own calendar: at each re-pick the
allocator re-reads M0197's bond ranking at this date and at the previous quarter's re-pick, counts
how many of that quarter's twenty are still under the band, and lets the blind draw replace exactly
the rest. Measured over the dev window's 79 re-picks before any of this ran: 423 entries against
the real book's 443, a ratio of 0.955, where the recorded arms sit at 2.24. The names also change:
``PLC1-HALF-FAST`` is resolved by ``lab control`` against ``Y20-HALF`` rather than its real target
``Y20-HALF-FAST``, because its stem is itself a placebo and the ladder steps past it;
``Y20-HALF-FAST-PLC1`` puts the target's whole name in the control's, so the strongest rung reaches
the right arm. The cost is the lookback -- 331 bars instead of 253 -- which moves no window.
```

**Impact:** docstring only.

---

### Step 7: M0202 — the imports

**File:** `engine/src/seer_engine/lab/methods/m0202_treasury_beta_half_guard.py:42-74`

**Change:** add `numpy` (this file does not import it today), `matched_book`, `Amendment`, and
`STEP`/`WEEKS`.

**Code:** replace lines 42-62 with

```python
from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_DOWN, Decimal
from typing import Any

import numpy as np

from seer_engine.backtest.dev import Candidate
from seer_engine.backtest.market import EMPTY_SERIES, MarketSeries
from seer_engine.lab.control_draw import matched_partition
from seer_engine.lab.method import Amendment, Method
from seer_engine.lab.methods.m0187_placebo_hash_order import draw
from seer_engine.lab.methods.m0197_treasury_yield_beta import (
    REPICK_MONTHS,
    STEP,
    WEEKS,
    YieldBetaParams,
    YieldBetaPrepared,
    choose,
    loadings,
)
from seer_engine.lab.methods.m0197_treasury_yield_beta import scored as yb_scored
```

**Impact:** lines 63-74 (`Target`, rules, `History`, `f_factor`, `indicators`) are unchanged and
already supply `EXCLUDED`, `factor_rows` and `FactorRow`. `draw` and `loadings` stay: the original
`ranked` (:151-160) still uses both.

---

### Step 8: M0202 — the amendment block

**File:** `engine/src/seer_engine/lab/methods/m0202_treasury_beta_half_guard.py` — insert between
`_v` (ends :243) and `METHOD = Method(` (:246)

**Code:**

```python
# ------------------------------------------------------------------ amendment 1 (2026-10-19)
#
# The shape-matched placebo. See the module docstring for why the recorded arms trade 2.25x the
# book each controls; what follows is the repair. Nothing above this line changes: a new allocator
# id is the only safe way to add an arm, because `registry._canon` renders a params dataclass by
# `dataclasses.fields()` and a field added to `HalfGuardParams` -- even a defaulted one -- would
# move every recorded config_digest that used it.

AMENDED = date(2026, 10, 19)
PREV_SPAN = 70  # sessions in a quarter, with room for the longest one in the dev window
MATCHED_LOOKBACK = WEEKS * STEP + PREV_SPAN + 1  # 331: a year of weekly marks before the previous
                                                 # re-pick, which the matched draw re-reads
REAL_SIDE = "bond"  # the side of the book these three arms are the controls for


def prev_repick_session(history: Mapping[str, History], data_date: date,
                        market: str) -> date | None:
    """The session this chassis last re-picked on, or None when the history does not reach it.

    Derived from the calendar, never carried in state: an allocator is called once per session and
    holds nothing between calls. The rules are ``monthly-hold-frac-gotrade``, so a decision session
    is the first session of a month and the ``data_date`` the allocator is handed is the last
    session of the month before it; a re-pick month is one of ``REPICK_MONTHS``, three apart. So
    the previous re-pick's data date is the last session ``market`` printed in the month three
    calendar months back. The search is bounded by ``data_date``'s own index, so it can see no bar
    the session cannot.
    """
    h = history.get(market)
    if h is None:
        return None
    i = h.index_of(data_date)
    if i is None:
        return None
    year, month = data_date.year, data_date.month - 3
    if month <= 0:
        year, month = year - 1, month + 12
    after = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    k = int(np.searchsorted(h.dates[: i + 1], np.datetime64(after, "D"), side="left")) - 1
    if k < 0:
        return None
    out = h.dates[k].item()
    return out if (out.year, out.month) == (year, month) else None


def real_frac_at(prepared: YieldBetaPrepared, members: AbstractSet[str], data_date: date,
                 p: HalfGuardParams) -> dict[str, float]:
    """M0197's own bond-side rank fractions on ``data_date``, over ``members``.

    ``members`` is the set the allocator was handed for its own session and is used unchanged at
    the previous quarter: a control is never given the membership of a past date, and reading
    today's set backwards uses no data the session does not already have. ``YieldBetaPrepared``
    carries no Market and so could not reach a past membership even if that were wanted, and M0201
    runs the identical rule on purpose, so the two amendments are one rule and not two.
    """
    inner = p.yb.inner
    if prepared.factor is None:
        rows = factor_rows(prepared.history, members, data_date, inner)
    else:
        rows = prepared.factor.rows_on(members, data_date, inner)
    return yb_scored(prepared.history, prepared.series, rows, data_date,
                     replace(p.yb, side=REAL_SIDE))


def matched_entries(prepared: YieldBetaPrepared, members: AbstractSet[str], data_date: date,
                    now: Mapping[str, float], p: HalfGuardParams) -> int:
    """How many names the bond book itself takes in on ``data_date``.

    Its own keep band, applied to the book it would have held at the previous quarter's re-pick:
    every name of that book still under ``keep_pct`` stays, and the rest of the twenty slots are
    entries. The band and not a symmetric difference, because a name that slips from rank 18 to
    rank 40 is kept by this chassis and is not an entry; counting ``|top20_now \\ top20_prev||``
    would over-state the churn and re-make the error this amendment exists to undo. With no
    previous re-pick in reach the whole book is an entry, which is what the chassis does on its
    first session anyway.
    """
    top = p.yb.inner.top
    before_date = prev_repick_session(prepared.history, data_date, p.yb.market)
    if before_date is None:
        return top
    before = real_frac_at(prepared, members, before_date, p)
    if not before:
        return top
    book = [s for _, s in sorted((v, s) for s, v in before.items())][:top]
    cut = p.yb.keep_pct / 100.0
    kept = min(sum(1 for s in book if now.get(s, 1.0) < cut), top)
    return max(0, top - kept)


def matched_frac(prepared: YieldBetaPrepared, members: AbstractSet[str], data_date: date,
                 held: frozenset[str], p: HalfGuardParams) -> dict[str, float]:
    """Rank fractions that drive M0197's ``choose`` to a blind book of the bond book's own shape.

    ``choose`` keeps a holding whose fraction is under ``keep_pct`` and fills the rest of the
    twenty slots from the top of the order, so a fraction below the band is an instruction to hold
    and one above it an instruction to enter. The names the matched draw keeps are laid out under
    the band in keep order, and every other name above it in the order the control would take it.
    ``choose`` itself is called unchanged, and so is the guard that halves what it returns, so the
    band, the quarterly calendar, the SPY filler and the half-size rule are byte-identical to the
    arm this controls; the only thing that differs is which names fill the slots.
    """
    now = real_frac_at(prepared, members, data_date, p)
    if not now:
        return {}
    cut = p.yb.keep_pct / 100.0
    top = p.yb.inner.top
    keep, tail = matched_partition(
        pool=sorted(now),
        held=held,
        keep_n=max(0, top - matched_entries(prepared, members, data_date, now, p)),
        tag="M0202",
        seed=p.seed,
        data_date=data_date,
    )
    out: dict[str, float] = {s: cut * (i + 1) / (len(keep) + 1) for i, s in enumerate(keep)}
    for j, s in enumerate(tail):
        out[s] = cut + (1.0 - cut) * (j + 1) / (len(tail) + 1)
    return out


class MatchedHalfGuardPlaceboAllocator(HalfGuardAllocator):
    """M0202's guarded book filled by a blind draw of the bond book's own shape, under its own id.

    Everything but the order is ``HalfGuardAllocator``'s: the screen, the band, the quarterly
    calendar, the SPY filler and the half-size guard in both its speeds. Two things change. The
    order on a re-pick comes from ``matched_frac`` instead of ``ranked``. And the lookback rises to
    ``MATCHED_LOOKBACK``, because this control re-reads the bond ranking at the previous quarter's
    re-pick and ``loadings`` wants a year of weekly marks before whatever date it is given; the
    rise moves no window, since ``candidate_window`` floors at the member index's 1996-01-02 and
    SPY's 331st bar is 1994-05-19.
    """

    id = "M0202-A1"

    def lookback(self, params: Any) -> int:
        return max(super().lookback(params), MATCHED_LOOKBACK)

    def _run(self, prepared: YieldBetaPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: HalfGuardParams) -> tuple[Target, ...]:
        if len(prepared.series) == 0:  # no series: target nothing (market-aware contract)
            return ()
        stocks = [s for s in held if s != p.yb.market and s not in EXCLUDED]
        repick = not stocks or data_date.month in REPICK_MONTHS
        frac = matched_frac(prepared, members, data_date, held, p) if repick else {}
        out = choose(prepared.history, members, frac, data_date, held, p.yb)
        return out if full_size(prepared.history, data_date, p) else halved(out)


MATCHED = MatchedHalfGuardPlaceboAllocator()


def _vm(suffix: str, params: HalfGuardParams, rationale: str,
        supersedes: tuple[str, ...]) -> Candidate:
    """An amendment candidate, with the declaration of which recorded arm it replaces.

    It matters most on the third arm: ``PLC1-HALF-FAST`` resolves to ``Y20-HALF`` while its
    replacement resolves to ``Y20-HALF-FAST``, so a supersession rule that matched targets would
    retire nothing there. D17's rule is a declaration, and this is where it is made."""
    return Candidate(id=f"M0202-{suffix}", family="M0202", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=MATCHED, params=params, rationale=rationale, added=AMENDED,
                     owner_inputs=(), supersedes=supersedes)


MATCHED_CONTROL_AMENDMENT = Amendment(
    added=AMENDED,
    why=(
        "The guarded placebo re-drawn to the bond book's own churn, because the recorded three "
        "trade about 2.25x the book each controls and the gaps were quoted against them"
    ),
    hypothesis=(
        "Written before any result. PLC1-HALF, PLC2-HALF and PLC1-HALF-FAST order the same "
        "scoreable names by a hash re-keyed every month, so the whole book is re-drawn at every "
        "quarterly re-pick while the bond book's own 40% keep band holds about fourteen of its "
        "twenty names; measured, they trade 2.25x, 2.25x and 2.25x the arms they control and turn "
        "over 2.01x, 1.99x and 1.91x, outside or at the edge of D17's refuse band. These three "
        "arms keep the frame, the guard and the seeds and change only where the re-key comes "
        "from: at each re-pick the blind draw replaces exactly as many names as the bond book's "
        "own band lets go, counted by re-reading M0197's bond ranking at this date and at the "
        "previous quarter's re-pick. The direction, pre-registered: a control that traded 2.25x "
        "was over-paying Gotrade's fees on about twelve entries a quarter instead of five or six, "
        "so an honestly-shaped replacement pays less and earns MORE, and every lead quoted "
        "against the old three NARROWS or REVERSES. Concretely, on the deposits (SPY TR 7.19% a "
        "year): Y20-HALF's 12.65% against PLC1-HALF's 11.30% is a 1.35 point lead that shrinks "
        "and may cross zero; against PLC2-HALF's 9.56% the 3.09 point lead shrinks; "
        "Y20-HALF-FAST's 12.14% against PLC1-HALF-FAST's 11.38% is a 0.76 point lead that is the "
        "likeliest of the three to reverse. The third arm is also re-aimed: PLC1-HALF-FAST is "
        "resolved today against Y20-HALF rather than Y20-HALF-FAST, and Y20-HALF-FAST-PLC1 puts "
        "the target's whole name in the control's so the margin is read against the arm it "
        "actually controls. Two seeds under the slow guard are kept deliberately, so the lead is "
        "read against a spread and not a single draw. Success for the amendment is only this: all "
        "three new arms land inside 0.80x-1.25x on trades and on turnover against the arm each "
        "resolves to. Whatever the margin then says is the finding and is reported as it comes; "
        "no seed is tuned and no arm is re-drawn for a better one."
    ),
    expected_failure=(
        "The shape may match and the leads may still move the other way, and if they do the cause "
        "is not fees but name identity: a blind book of twenty members drawn with the real book's "
        "churn still holds a different twenty, and over 1996-2015 the dev store's surviving "
        "members earned enough that a random slow-turning book can beat a bond-like book on luck "
        "alone -- PLC1-HALF's 11.30% against PLC2-HALF's 9.56% is already a 1.7 point spread "
        "between two draws of the same rule. Second, the match itself may miss on the fast guard "
        "rather than the slow one: HALF-FAST flips between full and half size far more often than "
        "HALF (2.71 turnover against 2.35 on the same 440 trades), those flips are resize trades "
        "the entry-count derivation does not control, and a blind book's weights sit differently "
        "under a halving than a bond book's. Third, the entry count is derived by re-reading the "
        "bond ranking at the previous quarter with today's member set, which the walk put at "
        "0.955 of the real book's entries rather than 1.00. If any arm lands outside the band the "
        "amendment has failed its own test and the number is recorded as the failure, not "
        "corrected."
    ),
    candidates=(
        _vm("Y20-HALF-PLC1", _p("placebo", "half", seed=1),
            "Placebo, shape-matched: the same scoreable names in a hash order (seed 1), re-drawn "
            "only as often as the bond book's own picks turn over, same half-size guard",
            supersedes=("M0202-PLC1-HALF",)),
        _vm("Y20-HALF-PLC2", _p("placebo", "half", seed=2),
            "Placebo, shape-matched: hash order seed 2, the same matched churn, same half-size "
            "guard",
            supersedes=("M0202-PLC2-HALF",)),
        _vm("Y20-HALF-FAST-PLC1", _p("placebo", "half-fast", seed=1),
            "Placebo, shape-matched: hash order seed 1, the same matched churn, under the fast "
            "guard",
            supersedes=("M0202-PLC1-HALF-FAST",)),
    ),
)
```

**Impact:** three new candidates under `M0202`, a new allocator id, no existing arm touched.

---

### Step 9: M0202 — hang the amendment on `METHOD`

**File:** `engine/src/seer_engine/lab/methods/m0202_treasury_beta_half_guard.py:305-309`

**Code:** replace lines 305-309 with

```python
    seen_keys=(
        "concept:treasury-beta",
        "concept:half-size-trend-guard",
    ),
    amendments=(MATCHED_CONTROL_AMENDMENT,),
)
```

**Impact:** `all_candidates()` returns nine; `pending_amendment` finds `amendments[0]`.

---

### Step 10: M0202 — verify, then commit, then run

**Code:**

```bash
cd /home/miftah/.worktrees/seer/honest-control-redraw
# same four exports and $PY/$LOG as step 5

$PY -m pytest engine/tests/test_lab_methods.py -q
$PY -m ruff check engine

$PY - <<'EOF'
from seer_engine.lab import control_shape as cs
from seer_engine.lab.methods.m0202_treasury_beta_half_guard import METHOD
arms = METHOD.all_candidates()
for c in arms[6:]:
    assert cs.kind_of(c) == cs.KIND_PLACEBO, (c.id, cs.kind_of(c))
    assert not [m for m in cs.DOSE_MARKERS if m in c.rationale.lower()], c.id
    print(c.id, cs.resolve_target(c, arms))
EOF
# expect ('M0202-Y20-HALF','sibling-stem') twice and ('M0202-Y20-HALF-FAST','sibling-stem') once

git hash-object /home/miftah/seer/lab/lab.sqlite        # record it

git commit -m "$(cat <<'EOF'
lab: M0202 amendment 1 pre-registered — the guarded placebo re-drawn to the bond book's own churn

PLC1-HALF, PLC2-HALF and PLC1-HALF-FAST trade about 2.25x the book each controls: M0187's hash is
re-keyed every month, so the whole book is re-drawn at every quarterly re-pick while M0197's 40%
keep band holds most of its names. D17 refuses the method on it. Y20-HALF-PLC1, Y20-HALF-PLC2 and
Y20-HALF-FAST-PLC1 keep the frame, the guard and the seeds and derive the re-key from the bond
book's own calendar. Measured on the dev window's 79 re-picks before this ran: 423 entries against
the real book's 443, 0.955, where the recorded arms sit at 2.24. The third arm is also re-aimed:
PLC1-HALF-FAST resolves against Y20-HALF today because its stem is itself a placebo, and
Y20-HALF-FAST-PLC1 names the arm it actually controls. Family B, so the pre-registered direction
is that an honestly-shaped control pays less, earns more, and every lead narrows or reverses.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)" -- engine/src/seer_engine/lab/methods/m0202_treasury_beta_half_guard.py

git status --porcelain -- engine/src/seer_engine/lab/methods/m0202_treasury_beta_half_guard.py

$PY -m seer_engine lab run M0202 --amend > "$LOG/m0202_run.log" 2>&1
echo "lab run M0202 --amend exit=$?"
cat "$LOG/m0202_run.log"

git hash-object /home/miftah/seer/lab/lab.sqlite        # record it
$PY -m seer_engine lab control M0202 > "$LOG/m0202_control.log" 2>&1
echo "lab control M0202 exit=$?"
cat "$LOG/m0202_control.log"
```

**Impact:** three `trials` rows, three `trial_funding` rows, one `method_amendments` row (M0202,
seq 1). Irreversible.

**Stop condition:** identical to step 5, per arm.

---

### Step 11: read the five margins, read-only

**Change:** nothing is written. A `lab` command migrates the database on connect; this does not.

**Code:**

```bash
sqlite3 "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" <<'SQL'
.mode column
.headers on
select t.candidate_id, t.n, t.trades, round(t.turnover,4) turnover,
       round(f.mwr*100,3) mwr_pct, round(f.spy_tr_mwr*100,3) spy_pct
from trials t join trial_funding f on f.trial_n = t.n
where t.window = 'dev'
  and (t.candidate_id like 'M0201%' or t.candidate_id like 'M0202%')
order by t.n;
SQL
git hash-object /home/miftah/seer/lab/lab.sqlite    # must equal the hash recorded after step 10
```

**Impact:** none.

---

## Verification

**Build / import:** `PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src
/home/miftah/seer/engine/.venv/bin/python -c "import seer_engine.lab.method as m; m.discover()"`

**Tests:**

```
PYTHONPATH=/home/miftah/.worktrees/seer/honest-control-redraw/engine/src \
  /home/miftah/seer/engine/.venv/bin/pytest engine/tests
/home/miftah/seer/engine/.venv/bin/ruff check engine
```

`engine/tests/test_lab_methods.py` is the one that matters and must be run **before** each commit:
`test_every_recorded_configuration_still_digests_to_its_recorded_digest` (:187),
`test_allocator_ids_are_unique_across_methods` (:108), `test_allocator_contract` (:88) and
`test_candidate_runs_a_smoke_window` (:79). The sha check (:154) stays green across the batch
because it falls back to `runner.pending_amendment` for a committed-but-unrun block.

`test_allocator_contract` requires `nonempty == 0` for a market-aware allocator. Both new
allocators inherit `market_fields` from their base (`("series", "shares")` and `("series",)`) and
both overridden `_run`s return `()` on the history-only path at the first branch, so the contract
holds and the 473-bar fixture never exercises the 331-bar lookback.

**Manual check:** `lab control M0201` and `lab control M0202` — read the `trades x` and
`turnover x` columns and the `controls` column for all five new arms.

**Exit criteria:**

1. `lab control M0201 M0202` reports all five new arms resolved by `sibling-stem` to
   `M0201-Y20-MV10`, `M0202-Y20-HALF` (×2) and `M0202-Y20-HALF-FAST`, each **inside
   `WARN_BAND` (0.80–1.25) on both trades and turnover**. Prediction, from the pre-run walk:
   trades ≈ 0.95 on all five.
2. Five margins read from `trial_funding.mwr` against SPY TR 7.188%/yr, each stated beside the
   number it replaces.
3. Two `method_amendments` rows, both seq 1; five new `trials` rows with five new `trial_funding`
   rows; `window = 'test'` count for M0201 and M0202 still **0**.
4. `pytest engine/tests` and `ruff check engine` green.
5. `git hash-object lab/lab.sqlite` recorded before and after each of the two runs, and unchanged
   across every read-only query.

---

## What to record for phase 8

**Write it to `.workflows/plan/honest-control-redraw/phase-5-results.md` and commit it by
pathspec.** That path is the set's one results-file convention (`phase-N-results.md`, N in 1..7)
and the only place Phase 8 collects this phase's numbers from. Nothing else in this phase writes
a number anywhere a later reader will look: no `lab note`, no `lab insight`, no edit to the plan
index, no `lab stage`.

A single block, to be pasted into that file and from there into the handover:

```
M0201 (amendment seq 1, two arms)
  control                     controls              trades x  turnover x  verdict
  M0201-Y20-MV10-PLC1         M0201-Y20-MV10        ____      ____        ____
  M0201-Y20-MV10-PLC2         M0201-Y20-MV10        ____      ____        ____

  margin, trial_funding.mwr, SPY TR 7.188%/yr, book M0201-Y20-MV10 = 9.543%
    old vs PLC1-MV10 10.255%  =  -0.712 pts      new vs Y20-MV10-PLC1 ____%  =  ____ pts
    old vs PLC2-MV10  8.065%  =  +1.478 pts      new vs Y20-MV10-PLC2 ____%  =  ____ pts
  DOES THE SPREAD STILL STRADDLE THE BOOK?  (today it does: 8.065 < 9.543 < 10.255)  yes / no
  M0201's success condition was "2+ points over both OPP-MV10 and the sized placebo seeds".
  It was already failed on the handicapped pair; state whether the honest pair changes that.

M0202 (amendment seq 1, three arms)
  control                     controls              trades x  turnover x  verdict
  M0202-Y20-HALF-PLC1         M0202-Y20-HALF        ____      ____        ____
  M0202-Y20-HALF-PLC2         M0202-Y20-HALF        ____      ____        ____
  M0202-Y20-HALF-FAST-PLC1    M0202-Y20-HALF-FAST   ____      ____        ____

  margin, trial_funding.mwr, SPY TR 7.188%/yr
    Y20-HALF 12.653%      old vs PLC1-HALF      11.301% = +1.352 pts   new ____% = ____ pts
    Y20-HALF 12.653%      old vs PLC2-HALF       9.564% = +3.089 pts   new ____% = ____ pts
    Y20-HALF-FAST 12.141% old vs PLC1-HALF-FAST 11.381% = +0.760 pts   new ____% = ____ pts
  RE-AIMING: M0202-PLC1-HALF-FAST is reported by lab control against M0202-Y20-HALF
  (2.248 / 2.200). Against its TRUE target M0202-Y20-HALF-FAST it is 2.248 / 1.913.
  Both numbers belong in the close-out; the new arm is read only against Y20-HALF-FAST.
  M0202's success condition was "beats its own same-guard placebo seeds by at least 2 points".
  PLC1-HALF (+1.352) and PLC1-HALF-FAST (+0.760) already failed it; state whether that changes.

  lab.sqlite git hash-object:  before M0201 ____  after M0201 ____  after M0202 ____
  test-window looks spent by this phase: 0
```

Phase 8 also needs, from this phase: both amendments are **seq 1** (not seq 2 — only M0030, M0053
and M0225 carried a recorded amendment row before this batch, so M0225's new block is the only
seq 2 in the set), the two new allocator ids `M0201-A1` and `M0202-A1`, and the five
`supersedes` declarations verbatim — `Y20-MV10-PLC1`->`PLC1-MV10`, `Y20-MV10-PLC2`->`PLC2-MV10`,
`Y20-HALF-PLC1`->`PLC1-HALF`, `Y20-HALF-PLC2`->`PLC2-HALF`, `Y20-HALF-FAST-PLC1`->`PLC1-HALF-FAST`
— so Phase 8 can check them against the index's supersession mapping.

**And the turnover risk, named here because this chassis carries it.** M0201 re-sizes monthly by
company size, so a blind book holds mega-caps the bond book never does and its weight dispersion
differs even when its entries match — exactly the effect Phase 3 measured on the cap-weighted
twins, where `M0221-E50` holds C50's exact names and records C50's exact 360 trades while turning
over 1.60x. Index invariant 12 settles the policy for the whole set: **match names and churn
only; a turnover miss is a recorded STOP**, never patched by giving the drawn names the real
arm's weight vector. That patch would apply to three of the nine chassis and leave them running
a different rule from the other six, which fails R1 rather than rescuing it. Record both ratios
and the axis that missed.

---

## Handoffs

- **R4 is not served here.** `mis_shaped_controls` returns every recorded arm outside the band, and
  `M0201-PLC1/2-MV10` and `M0202-PLC1/2-HALF` / `PLC1-HALF-FAST` keep their recorded trials
  forever. After this phase `lab promote M0201` and `lab promote M0202` still refuse on D17. The
  supersession rule that fixes that is **phase 2**'s, and it is the only thing that unblocks these
  two. Nothing in this phase may touch `control_shape.py` or `hardgate.py` to get there.
- **The matched-draw helper is phase 1's, and the reconciliation already aligned it.** The call
  is `control_draw.matched_partition(pool=, held=, keep_n=, tag=, seed=, data_date=)`, one per
  file, and the `tail` ordering this phase depends on — dropped holdings **after** fresh names —
  is now a documented guarantee of that function with a test pinning it
  (`test_a_dropped_holding_is_never_re_taken_ahead_of_a_fresh_name`). Phase 1's first draft did
  **not** have it, which is the one real bug this reconciliation found in the set: its book was
  filled from the whole eligible pool in entry order and could take a just-dropped holding
  straight back, sagging the trade ratio below 1.00 while every size assertion stayed green.
  This phase's 0.9549 was measured with the correct ordering and stands.
- **This chassis does NOT call `control_draw.previous_decision_date`, and must not.** That helper
  answers the previous *monthly* decision. M0201's and M0202's shared `_run` passes an empty
  `frac` on every non-`REPICK_MONTHS` month, so the basket moves only quarterly behind M0197's
  40% keep band and there is no monthly entry count to match. `prev_repick_session` in each file
  is the chassis-specific derivation, it stays, and Phase 1's docstring carries the split so
  nobody later "simplifies" it into the monthly helper. (Phase 4's M0047 is the opposite case:
  genuinely monthly, and the brief that called it quarterly was wrong.)
- **The 1.0045 variant is left on the table.** Reading the previous quarter with its *true*
  historical membership lands at 1.0045 instead of 0.9549, and M0201 could do it because
  `SizedPrepared` carries the Market. It is deliberately not done, so that M0201 and M0202 run one
  rule. If a later session wants it, it is a new amendment on M0201 alone and it costs a method's
  variant slot, not a method id.
- **`lab stage` is not run here** (invariant 8). `web/data/lab.json` will disagree with
  `lab.sqlite` from the moment the first run lands until phase 8 stages them; the snapshot test is
  red mid-batch by design and no attempt is made to fix it.
- **Not re-drawn, and not in scope:** `M0201-OPP-MV10` and `M0202-N20-HALF`. Both are paired
  contrasts, not placebos — `kind_of` returns `''` for each — so D17 never shape-checks them and
  neither blocks promotion.
- **Drive-by not taken:** `m0201:45` and `m0201:160-161` describe the placebo as "M0202's hash
  order", which is a reference to a sibling method rather than to M0187 where `draw` actually
  lives. It is accurate enough (M0202 was added 2026-10-17, M0201 2026-10-18) and rewording a
  frozen prose line is not this phase's work.

---

## Rollback

- **Before a file's own `lab run --amend`:** `git revert` that file's pre-registration commit, or
  `git checkout HEAD~1 -- <that one path>` and commit by pathspec. The block is pre-registration
  and nothing else until the run executes. The two files are independent: M0201 can be reverted
  with M0202 already run, and the reverse.
- **After a file's run: not reversible.** `trials`, `trial_funding` and `method_amendments` all
  carry append-only triggers on update **and** delete. The `Amendment` block must stay in the file
  forever — `runner.pending_amendment` compares every recorded row field by field and demands the
  record stay a prefix of the file, so deleting the block would break `lab run` for M0201/M0202
  permanently. The correct rollback after a run is a journalled `lab insight` saying the arms ran
  and what they showed. **This is why the whole pre-registration is in the commit that precedes the
  run.**
- **Whole phase, before phase 8:** the branch can be dropped; the amendments that ran stay in the
  shared database, which is correct — they are measurements, and the files that produced them are
  recoverable by re-merging the branch. Never by editing the database.
