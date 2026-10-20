> Adopted from `docs/plans/CONTROL_DRAW_REMEDIES_PLAN.md` phase 5. Source: `.workflows/plan/control-draw-remedies/phase-5.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 5: The weight rule, and the arms it earns

**Plan set:** `CONTROL_DRAW_REMEDIES_PLAN.md`
**Analysis:** `docs/analyzer/20261020-113306-C7K4_code_analyzer.md`
**Satisfies:** R2 (the weight vector, and the honest confrontation that it is a second mechanism)
and R4 (frozen records; a re-draw is a NEW arm under an amendment; no test-window look)
**Depends on:** Phase 4 — and it is a **conditional** dependency, not a sequencing one. Phase 4 can
delete this phase's entire body of work.
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab` (+ `engine/src/seer_engine/lab/methods`, + the lab db)
**Worktree:** none. `/home/miftah/seer`, branch `main` (Decision D1).

---

## 0. THE BRANCH POINT — read this before anything else

**Do not open an editor until `.workflows/plan/control-draw-remedies/phase-4-results.md` has been
read and the branch below has been chosen in writing.**

Phase 4 measures **four** weight-assignment rules on M0221 for free, inside one
`dev.run_registry` sweep, and records a yes/no with a number. Its STOP rule is in the index: *if no
rule lands M0221's control inside `WARN_BAND`, phase 5 draws neither M0221 nor M0225.*

Read the file and classify its verdict into exactly one of these **five** keys. Phase 4's results
file names the winner by **both** its letter and its key, so this is a lookup and not a judgement.
Write the key, and the measured numbers behind it, into the first line of `phase-5-results.md`
before any other work.

| key | phase 4's rule | what phase 4 found | what this phase does |
|---|---|---|---|
| **S** | — | no rule brings `M0221-C50-PLC`'s successor to `turnover ≤ 0.5563` (1.25×) with trades inside 0.80–1.25× | **Branch S** below. No code. One results section. |
| **G-entry** | **A** | the winner assigns the real vector along the **month-keyed entry order** | **Branch G**, `ORDER = entry` |
| **G-ladder** | **B** | the winner assigns the real vector along the **date-free keep ladder** | **Branch G**, `ORDER = ladder` |
| **G-size** | **C** | the winner re-shapes the **control's own values** to the real book's concentration | **Branch G**, `ORDER = own-size` |
| **G-bottom** | **D** | the winner puts **keeps first in keep order and entrants last**, down the sorted vector, so an entrant always takes a bottom rung | **Branch G**, `ORDER = bottom-entry` |

**There is no sixth key.** If phase 4's file is ambiguous — two rules clear, or a rule clears on
trades and not on turnover, or the file records a rule phase 4 invented beyond its four — the
answer is **S**, and the results file says so with the ambiguity quoted. The index is explicit
that phase 4 "must not keep inventing rules to avoid" a STOP, and this phase inherits that: it
does not re-measure, it does not try a fifth rule, and it does not run a trial to break a tie.

**A `G-*` key additionally requires both of these, or it degrades to S:**

1. phase 4's winning turnover ratio was measured **re-run against re-run** inside one
   `run_registry` sweep (invariant I8) — a number compared against recorded trial #843 is not
   evidence;
2. the winning rule's trade ratio stayed inside **0.80–1.25**. A rule that fixes turnover by
   breaking the trade axis has moved the handicap, not removed it.

### Branch S, in full — what the one section must contain and must not claim

If the key is **S**, this phase writes **no code at all**: no module, no test, no method-file edit,
no commit to `engine/`, no `lab run`, no `lab control`, no `lab note`, no `lab stage`. It writes
exactly one file, `.workflows/plan/control-draw-remedies/phase-5-results.md`, and it contains:

**It MUST contain**

- The verdict word **STOP** and the key **S** on the first line, and the sentence that phase 4 is
  the measurement and this phase is its consequence.
- The **four** rules phase 4 tried — A, B, C and D — each named, and each one's measured **trades
  ratio and turnover ratio** against `M0221-C50`, taken from phase 4's sweep. Four rows, not a
  summary.
- The bar they missed, stated as the absolute number and not only as a ratio: `M0221-C50` turned
  over **0.4450** and traded **360**, so the control's bar is **≤ 0.5563 turnover** and 288–450
  trades.
- **The closure of leftover 2 with a number.** Leftover 2 of `HANDOVER_20261019-the-honest-control`
  reads *"the weight-vector remedy … carried, not applied"*. This section closes it: the remedy
  was measured, on the chassis it was proposed for, and it is **a measured dead end** — carried
  twice, closed the third time with a figure. Name the figure.
- **The reason, in mechanism and not in disappointment.** Decision D7 predicted exactly this and
  wrote the mechanism down before the measurement: `M0221-C50-PLC` is already drift-neutral
  because it weights its own drawn names by their own market values, so its target moves with the
  same prices its holding does; attaching a *foreign* vector makes the target move with the real
  book's prices while the holding moves with its own, and two uncorrelated drifts cross the
  1 %-of-equity resize band more often than one tracked drift. If phase 4's numbers show turnover
  **rising** under one or more rules, say so plainly — that is D7 confirmed, and it is the most
  valuable sentence available here.
- **The M0225 consequence, restated and not hidden.** `M0225-C50-PLC` is still not drawn, M0225 is
  still blocked on `M0225-R50` (0.195× / 0.424×), and **M0225 therefore still has no honest control
  at all.** Its **−0.890** deficit remains computable only against an arm that traded a fifth as
  often. **Say it accurately:** that deficit lives in `trials` and in
  `docs/plans/HANDOVER_20261019-the-honest-control.md`; verified read-only at `e3aeeff`, **no
  sentence in M0225's `methods.verdict` or `methods.analysis` quotes it**, so there is no published
  sentence for this phase to correct and none may be invented. Leftover 1 asked that M0225 not be
  drawn under `control_draw` as it stands; under branch S it stays undrawn, and the reason is now
  measured rather than inferred from its twin.
- **The M0201 consequence.** `M0201-Y20-MV10-PLC1` stays at 0.949 / 0.794, **0.0059 short** of the
  band on the turnover axis; `M0201-Y20-MV10-PLC2` is already `ok` at 0.961 / 0.839, so M0201 does
  have one honest control today. Say both.
- **Decision D6 recorded as a measured exclusion, not an omission** (see §1 below — it belongs in
  the results file under either branch).
- `git hash-object lab/lab.sqlite` **before and after**, identical, with the value. Today it is
  `607b78cf69c8e4e3a68a1e84c85eedfd1040c754`.
- Test-window looks **4 → 4**, asserted by a read-only query, with the query shown.
- A one-line handoff to phase 6 naming the three sentences it must carry: M0221's "between 0 and
  0.4 points", M0225's "−0.890", and the R1 verdict.

**It MUST NOT claim**

- That the weight vector "would work with more tuning". Four rules, measured, then stop. The
  index forbids inventing a fifth and so does this file.
- That `control_weight.py` was *designed* and merely not written. Nothing was designed; a
  measurement said no.
- That any method moved. No verdict, no status, no N, no look, no trial changes under branch S.
- That M0221 or M0225 are now promotable, or closer to it. They are not: `hardgate.check` raises
  on the walk-forward fold majority **before** D17 for both, so their D17 refusals are inert and
  always were (Decision D8's sibling fact, and the index's **Why**).
- That the matched draw failed. It did not. It closed the **trade** axis on this chassis at 1.03×
  with a free pre-run probe reading 1.000 basket changes. What failed is a *second* rule on a
  *second* axis, and R2 is the requirement that owns that axis.

Then stop. Under branch S the rest of this file is not executed, and §7's verification reduces to:
tree untouched, `ruff` clean, `pytest` green (both unchanged, because nothing was edited), db hash
unmoved, looks 4 → 4.

---

## Goal

**Under branch G:** the lab gains a second shared contract, on the axis `control_draw` cannot
reach — `control_weight.assigned`, which pays a weight vector a chassis hands it onto a ladder the
chassis chooses, and `control_weight.rung_order`, the date-free ladder a blind book can derive
without carrying state. Behind it, `M0221-C50-PLCW` and `M0225-C50-PLC` are drawn as new arms under
new amendments, M0225 gets the honest control it has never had, and — only if phase 4 measured it
closing — `M0201-Y20-MV10-PLCW` closes a 0.0059 gap.

**Under branch S:** leftover 2 stops being carried. It closes with a number, and the plan set's R1
verdict (phase 6) gets the second of its two structural facts measured rather than argued.

Under both: **no method becomes promotable.** The gate takes none of the nine, and three of the
four live D17 refusals — M0201's, M0221's and M0225's, every one of this phase's methods — are
raised *after* the walk-forward fold majority has already refused. This phase buys honest controls
and honest published sentences. It buys nothing else and must not say it does.

---

## Interface Contract

The reconciler reads this section. Under **branch S** every row below is void and this phase's
contract is empty: it creates, deletes, renames and requires nothing.

Under **branch G**:

**Creates:**
- module `seer_engine.lab.control_weight` (`engine/src/seer_engine/lab/control_weight.py`) —
  `RULE_ID`, `ORDERS`, `rung_order`, `assigned`
- test module `engine/tests/test_lab_control_weight.py`
- `m0221.WeightMatchedCapTopAllocator` (allocator id `M0221-A2`), `m0221.WMATCHED`,
  `m0221.WEIGHT_AMENDED`, `m0221.WEIGHT_RULE`, `m0221.WEIGHT_AMENDMENT`, candidate
  `M0221-C50-PLCW`
- `m0225.RepairedWeightMatchedAllocator` (allocator id `M0225-A2`), `m0225.WMATCHED`,
  `m0225.WEIGHT_AMENDED`, `m0225.WEIGHT_AMENDMENT`, candidate `M0225-C50-PLC`
- *(conditional on phase 4's M0201 reading)* `m0201.WeightMatchedSizedPlaceboAllocator` (allocator
  id `M0201-A2`), `m0201.WMATCHED`, `m0201.real_profile`, `m0201.assigned_resize`,
  `m0201.WEIGHT_AMENDED`, `m0201.WEIGHT_AMENDMENT`, candidate `M0201-Y20-MV10-PLCW`
- lab rows: 2 trials (3 with M0201), 2 `method_amendments` rows (3 with M0201), regenerated
  `web/data/lab.json`

**Deletes:** nothing. **Renames:** nothing.

**Signature changes:** none. No existing function, class, dataclass or constant changes its
signature, its body or its default anywhere in this phase. The three method files are **append
only**; the one existing test file this phase edits is listed below.

**Modifies (not a signature change, but a reconciler must see it):**
- `engine/tests/test_lab_control_draw_twins.py` — `test_the_amendment_block_is_the_expected_shape`
  and `test_the_new_arm_declares_the_arm_it_supersedes` currently pin the **pre-amendment** file
  state (`len(m0221.METHOD.amendments) == 1`, `all_candidates() == 7`, "M0225 was never
  re-drawn"). They go red the moment the new blocks land. They are inverted to the post-run truth,
  which is strictly stronger, and the module docstring's "used by exactly one arm today" is
  corrected. **No other test file is touched by this phase.**

**Requires (from earlier phases):**
- **Phase 4** — the branch key and the winning ladder, from
  `.workflows/plan/control-draw-remedies/phase-4-results.md`. Nothing else.
- **Phase 2** — `control_draw.py` is read **as it stands after phase 2**, and phase 2 is
  additions-only (index invariant I3: `keep_key` keeps its body byte for byte). `control_weight`
  imports exactly one name from it, `keep_key`, and that name is on the frozen-v1 list, so phase 2
  cannot move it. **This phase does not edit `control_draw.py` and does not read its v2 shadow.**
  If phase 2 has not landed, this phase still works: `keep_key` is on `main` today.
- Phase 2 and phase 5 touch **no file in common**, so neither orders the other.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/control_draw.py` (phase 2)
- `engine/tests/test_lab_control_draw.py`, `engine/tests/test_lab_control_draw_shadow.py` (phase 2)
- `engine/src/seer_engine/lab/methods/m0208_capital_gains_overhang.py` (phase 3)
- `m0047`, `m0202`, `m0215`, `m0227`, `m0243` method files — untouched here under either branch
- `docs/plans/HANDOVER_20261020-control-draw-remedies.md`, `lab insight` rows, the **final**
  `lab stage` (phase 6)
- every recorded `Candidate`, every recorded `Amendment` block, every closed record

---

## 1. Decision D6 recorded: M0047 is excluded on measurement

Write this into `phase-5-results.md` under **either** branch, as a section of its own. It is a
decision with numbers behind it, and an unexplained absence would read as a phase that forgot.

> **M0047 is not re-drawn, and the reason is measured.** The brief lists three weight-varying
> chassis and M0047 is one of them — `size_weights(sizes, top, p)` over the picks' market values
> under a ceiling. It is excluded anyway, on two independent readings:
>
> 1. **Its honest arms are already clean.** `M0047`'s re-drawn controls read **0.99 / 0.92** and
>    **0.98 / 0.89** — inside `WARN_BAND` on both axes, and both already superseding. A weight rule
>    applied here would retire nothing, move no verdict, change no published sentence, and spend a
>    full dev sweep to re-observe a match the lab already holds.
> 2. **It has almost no lookback left.** `M0047-A1` declares **427 bars** against the 473-bar
>    `labkit.smoke_market` cap — **46 bars of headroom, one extra monthly step**. It is the single
>    most constrained allocator in the set.
>
> Reading (1) alone settles it; (2) is why no cheaper variant was looked for either. This is an
> exclusion on measurement, not an omission.

---

# BRANCH G — the build

Everything below runs only under a `G-*` key.

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/control_weight.py` | **create** | the weight-assignment contract: `RULE_ID`, `ORDERS`, `rung_order`, `assigned`, and the docstring that says this is the second rule on the second axis |
| `engine/tests/test_lab_control_weight.py` | **create** | the module's own tests: pure, no store, no database, no backtest |
| `engine/src/seer_engine/lab/methods/m0221_cap_weighted_top_n.py` | **append** at EOF, after `METHOD` is not possible — see §3: the block goes **before** `METHOD`, and `METHOD`'s `amendments=` tuple gains one entry (`m0221:...` last line) | amendment 2: `WeightMatchedCapTopAllocator` (`M0221-A2`), `M0221-C50-PLCW` |
| `engine/src/seer_engine/lab/methods/m0225_cap_weighted_top_n_repaired.py` | **append**, same shape | amendment 2: `RepairedWeightMatchedAllocator` (`M0225-A2`), `M0225-C50-PLC` |
| `engine/src/seer_engine/lab/methods/m0201_treasury_beta_size_weighted.py` | **append**, **conditional** (§6) | amendment 2: `WeightMatchedSizedPlaceboAllocator` (`M0201-A2`), `M0201-Y20-MV10-PLCW` |
| `engine/tests/test_lab_control_draw_twins.py` | **modify** (`:1-19`, `:113-123`, `:135-155`) | invert the two pre-amendment assertions to the post-run truth; add the new arms' guards |
| `lab/lab.sqlite`, `web/data/lab.json` | **write** (by `lab run --amend` / `lab stage`) | 2–3 trials, 2–3 `method_amendments` rows, the regenerated snapshot |
| `.workflows/plan/control-draw-remedies/phase-5-results.md` | **create** | the measurement, the margins, the supersessions, D6, the hashes |

**A note on "append only" and where the block goes.** `METHOD = Method(...)` is the last statement
in each of the three files and its `amendments=(...)` tuple must name the new block, so the new
code is inserted **immediately before** the `METHOD` assignment and the tuple on the file's final
lines gains one name. Nothing above the insertion point is edited. That is what "append only"
means here and it is exactly the shape amendment 1 already has in all three files.

---

## 2. The shared contract, and what it honestly is

Carry this into `control_weight.py`'s docstring. It is R2's core and the index's **The honest
answer on R1** is where it comes from.

- **A shared module cannot produce a weight vector.** Each chassis computes its own:
  `m0221.weights` (market value, normalised, 10 % ceiling), `m0047.size_weights` (size under a
  ceiling), `m0201.sized_weights` + `resize` (per-*company* market value, 10 % ceiling, split
  across held classes). A shared module has no way to produce any of them, and inventing a fourth
  sizing would make the control a different book, not a matched one.
- **So what is shared is the ASSIGNMENT of a vector the chassis hands over.** That is the same
  shape `control_draw.matched_partition` already has — the module owns an ordering contract and
  each chassis applies its own slot count, sector cap or keep band to it — and the lab already
  calls that one rule.
- **"One reusable rule" in the literal sense was not met, and the docstring must say so**, with the
  number that makes it structural rather than a gap in the design: `M0221-E50` holds `M0221-C50`'s
  **identical fifty names** and records its **identical 360 trades**, and still turns over
  **0.7126 against 0.4450 — 1.60×**. No rule that decides *which names* a control holds can reach
  that, however the entry count is derived. Turnover on a weight-varying book is not in name space.
- **An allocator cannot read its own weights.** `book_runner` hands it `held`, a `frozenset[str]`
  of symbols, and nothing else about the book (`backtest/book_runner.py:393-403`). A rung must be
  **derived** every time, never carried.
- **No mutable allocator state** (index invariant I9). `dev.run_registry` reuses one allocator
  object per id across candidates and across walk-forward folds, so per-instance state leaks
  between them. `rung_order` is a pure function of `(names, tag, seed)` and `assigned` is a pure
  function of `(order, vector)`. Neither takes a date, neither holds anything, and the test module
  asserts both.

### Step 1: write `engine/src/seer_engine/lab/control_weight.py`

**File:** `engine/src/seer_engine/lab/control_weight.py` (new, lands beside
`engine/src/seer_engine/lab/control_draw.py:1`)

**Change:** the whole module. Complete and runnable.

```python
"""The matched weight: a control arm weighted like the book it controls, assigned and not computed.

``lab.control_draw`` made a control hold the same number of names as the book it controls and take
in the same number of new names each decision. On a book whose slots are all the same size that is
the whole match: equal slots of the same count move the same fraction of the book per name, so the
turnover ratio follows the trade ratio arithmetically. On a book that weights its names by
anything else, it is half of it.

**The number that says so, and it was measured before this module existed.** ``M0221-E50`` holds
``M0221-C50``'s **identical fifty names** and records its **identical 360 trades** -- and turns
over **0.7126 against 0.4450, 1.60x**. Not one name differs and not one basket change differs. The
whole 0.60 of excess is the weight vector: ``C50`` is cap-weighted and nearly drift-neutral,
because a name's target weight is its own market-value share and moves with its own price, so the
realised weight tracks the target and the book engine's 1%-of-equity resize band (``sim.rules.
RESIZE_BAND``) rarely fires; ``E50`` pays fifty equal slots and every relative price move pushes
one of them across the band. ``M0221-C50-PLC``, the matched draw on the same chassis, lands at
1.03x trades and **1.95x** turnover -- so about two-thirds of its excess was never a name rule's to
close.

**So this is a SECOND rule on a SECOND axis, and the file layout says so rather than hiding it
behind one module name.** The honest-control set's R1 asked for *one reusable rule*. Read
literally -- one rule, no per-chassis patch -- that requirement **cannot be met, and no further
work will make it meetable**, for two structural reasons:

1. turnover on a weight-varying book is not in name space at all (``E50``, above). The matched
   draw is a name rule by construction and cannot reach it;
2. **a shared module cannot produce a weight vector.** Each chassis computes its own with its own
   code -- ``m0221.weights`` (market value, normalised, a 10% ceiling), ``m0047.size_weights``
   (size under a ceiling), ``m0201.sized_weights`` and ``resize`` (per-company market value, a 10%
   ceiling, a company's weight split over its held classes). Nothing shared can produce any of
   them, and a module that invented a fourth sizing would be building a different book instead of
   matching one.

What *can* be shared is the **assignment** of a vector the chassis hands over, and that is all this
module owns. It is the same shape ``matched_partition`` already has -- the module owns an ordering
contract, each chassis applies its own slot count, ceiling or band to it -- and by the standard
already in force in this lab that is one reusable rule. It is the most R2 can honestly aim at and
the docstring says so here rather than in a plan file nobody reads at 3am.

**The ladder is the open question, not the vector.** ``matched_names`` returns its book in a
month-keyed order that re-shuffles every month, so paying the k-th largest weight to the k-th name
of *that* order would re-assign every rung every month -- a turnover generator in its own right,
and a worse one than the problem. Three ladders are available to a chassis and all three were
measured before this module was written:

- ``"ladder"`` -- ``rung_order`` below: the date-free keep order, so a name that stays in the book
  keeps its rung for as long as its neighbours do;
- ``"own-size"`` -- the control's own sizes, descending. The rung then moves with the drawn name's
  own price, which is the most drift-neutral of the three and the nearest in spirit to what the
  real book does;
- ``"entry"`` -- the month-keyed order ``matched_names`` already returns, kept in ``ORDERS`` only
  because it is the brief's literal reading and was measured as such.

**An allocator cannot recover its own rung from state.** ``book_runner`` hands it ``held``, a
``frozenset[str]`` of symbols, and nothing else about the book
(``backtest/book_runner.py:393-403``): there are no weights in the call and never will be. A rung
is therefore **derived** on every decision from something stable, never carried -- and never
stored on the allocator, because ``backtest.dev.run_registry`` reuses one allocator object per id
across candidates and across walk-forward folds, so per-instance state leaks between them.
``rung_order`` takes no date and keeps nothing; ``assigned`` takes no date and keeps nothing.

**What this module may never be used for.** It shapes a control; it never phrases one, and it never
decides *which* names a control holds -- that is ``control_draw``'s job and the two must not grow
into each other. Nothing a chassis reads about a name may decide that name's rung: under
``"ladder"`` the rung is a hash of the symbol, under ``"own-size"`` it is the drawn name's own
size, and the names themselves were drawn blind. A control whose rung came from the real book's
*identity* would not be a control at all.

Pure: one hash, one sort and a zip. No clock, no randomness, no store, no database, no prices.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from seer_engine.lab.control_draw import keep_key

RULE_ID = "matched-weight-v1"
"""Names the construction, for a reader of a recorded trial. Reporting only, exactly as
``control_draw.RULE_ID`` is: ``registry._canon`` enumerates ``dataclasses.fields()`` of a
candidate's params and a module constant is in none of them, so bumping this moves no recorded
digest -- but it names a different control, so a bump belongs with a new arm, never with an edit."""

ORDERS: tuple[str, ...] = ("ladder", "own-size", "entry")
"""The three ladders a chassis may pay the vector onto, as the module docstring describes them.

This module builds only ``"ladder"`` (``rung_order``), because that is the only one a chassis
cannot already produce for itself: ``"own-size"`` is the chassis's own size dict sorted, and
``"entry"`` is what ``control_draw.matched_names`` already returns. The tuple is here so that a
method file naming its choice is naming something this module recognises, and so that a reader
meeting one wiring knows two others were measured."""


def rung_order(names: Sequence[str], *, tag: str, seed: int) -> list[str]:
    """``names`` on the date-free ladder: the rung a name holds for as long as it is held.

    ``control_draw.keep_key(tag, seed, symbol)`` is imported rather than re-derived -- it is the
    lab's one date-free hash of a name, it is on the frozen-v1 list, and a key computed two ways is
    a key that will eventually disagree with itself (``control_draw.churn`` says the same about a
    count). Using the keep order rather than a fresh hash is deliberate: it is already the order
    the control decides *who stays* in, so a name that survives a decision keeps the same
    neighbours above it and its rung moves only when one of them leaves.

    ``tag`` is the book's method id, not the allocator id, for the same reason ``keep_key``'s is:
    two twins of one book (M0221 and M0225) given the same tag draw the same names AND pay them the
    same rungs, which is the only way a before-and-after on a data repair measures the repair.

    Refuses a duplicate rather than quietly collapsing it: a book that names one symbol twice has
    already gone wrong upstream, and a silent ``set()`` here would pay one rung to two names and
    leave the last rung unpaid, which every size assertion downstream would still pass.
    """
    out = list(names)
    for s in out:
        if not isinstance(s, str) or not s:
            raise ValueError(f"every name must be a non-empty str, got {s!r}")
    if len(set(out)) != len(out):
        raise ValueError("names carries a duplicate, so one rung would be paid twice")
    return sorted(out, key=lambda s: (keep_key(tag, seed, s), s))


def assigned(
    order: Sequence[str], vector: Sequence[Decimal | None]
) -> dict[str, Decimal]:
    """The k-th name of ``order`` takes the k-th largest weight in ``vector``.

    ``order`` is the ladder -- whichever of ``ORDERS`` the chassis chose -- and ``vector`` is the
    weight vector the chassis computed for the arm being controlled, in that arm's own order, with
    its own ceiling already applied. Only the vector's **multiset of values** is read: never a
    name, never the real book's own ordering, and nothing about which real name held which weight.
    That is what keeps the control blind. It takes the real book's *shape*, exactly as
    ``control_draw.matched_names`` takes the real book's *size and entry count* and nothing else.

    ``None`` entries are not rungs and neither are non-positive ones: ``m0221.weights`` and
    ``m0201.sized_weights`` both return ``Decimal | None`` per pick, ``None`` where the weight
    floored to zero at ``sim.book.WEIGHT_QUANTUM``, and a name the real book could not hold is not
    a rung the control should pay.

    The two lengths are allowed to differ and the answer is the honest one in both directions:
    with fewer rungs than names the tail of ``order`` is **absent from the result**, and a caller
    that walks its book and skips a missing key drops exactly those names -- which is what the real
    book did with them. With more rungs than names the surplus is unspent. Neither is an error,
    because a pool thins and a ceiling floors names, and raising here would turn a data fact into a
    crash years into a recorded trial.

    Returns a plain dict, so a caller may fill its book in **its own** order (rank order decides
    who is filled last when a session's cash runs short) while paying each name the rung this
    module assigned it.
    """
    names = list(order)
    for s in names:
        if not isinstance(s, str) or not s:
            raise ValueError(f"every name must be a non-empty str, got {s!r}")
    if len(set(names)) != len(names):
        raise ValueError("order carries a duplicate, so one rung would be paid twice")
    rungs: list[Decimal] = []
    for w in vector:
        if w is None:
            continue
        if not isinstance(w, Decimal):
            raise TypeError(f"a weight must be a Decimal or None, got {type(w).__name__}")
        if w > 0:
            rungs.append(w)
    rungs.sort(reverse=True)
    return dict(zip(names, rungs, strict=False))
```

**Impact:** a new, importable module. Nothing imports it yet, so this file alone moves no recorded
digest, no verdict and no trial. `ruff check engine` must be clean after it.

---

### Step 2: write `engine/tests/test_lab_control_weight.py`

**File:** `engine/tests/test_lab_control_weight.py` (new)

**Change:** the whole module. Pure — no store, no database, no backtest, no fixture.

```python
"""``lab.control_weight``: the assignment contract, on its own.

A module of its own rather than more tests in ``test_lab_control_draw``: these are a different
rule on a different axis and the test layout says what the source layout says. Nothing here opens
a store, a database or a backtest -- the whole module is a hash, a sort and a zip, and that is
exactly what makes it testable without any of them.
"""

from __future__ import annotations

import ast
import inspect
from decimal import Decimal

import pytest

from seer_engine.lab import control_draw as cd
from seer_engine.lab import control_weight as cw

TAG = "M0221"
SEED = 1
NAMES = ("AAA", "BBB", "CCC", "DDD", "EEE")


def _vec(*xs: str) -> list[Decimal | None]:
    return [None if x == "-" else Decimal(x) for x in xs]


def test_the_kth_rung_takes_the_kth_largest_weight():
    """The rule in one line: the ladder's first name is paid the real book's biggest slot."""
    order = ["AAA", "BBB", "CCC"]
    out = cw.assigned(order, _vec("0.10", "0.30", "0.20"))
    assert out == {"AAA": Decimal("0.30"), "BBB": Decimal("0.20"), "CCC": Decimal("0.10")}


def test_the_assignment_reads_the_vectors_values_and_never_its_order():
    """Blindness, asserted. Only the multiset of weights is read: the real book's own ordering
    carries its identity and the control must never see it."""
    order = ["AAA", "BBB", "CCC"]
    a = cw.assigned(order, _vec("0.10", "0.30", "0.20"))
    b = cw.assigned(order, _vec("0.30", "0.20", "0.10"))
    c = cw.assigned(order, _vec("0.20", "0.10", "0.30"))
    assert a == b == c


def test_the_assignment_spends_every_rung_and_mints_none():
    """A control must hold the real book's weights, not a rescaled lookalike: the sum is the real
    book's own exposure and no name is paid a weight the real book never held."""
    vector = _vec("0.10", "0.30", "0.20", "0.40")
    out = cw.assigned(["AAA", "BBB", "CCC", "DDD"], vector)
    assert sorted(out.values()) == sorted(w for w in vector if w is not None)


def test_a_none_or_zero_entry_is_not_a_rung():
    """``weights`` and ``sized_weights`` both return None where a weight floored to zero at
    ``WEIGHT_QUANTUM``. A name the real book could not hold is not a slot to pay out."""
    out = cw.assigned(["AAA", "BBB"], _vec("0.50", "-", "0.00", "0.25"))
    assert out == {"AAA": Decimal("0.50"), "BBB": Decimal("0.25")}


def test_fewer_rungs_than_names_leaves_the_tail_unpaid_rather_than_raising():
    """A pool thins and a ceiling floors names. The honest answer is a shorter dict -- the caller
    skips the missing keys, which is what the real book did with them -- not a crash years into a
    recorded trial."""
    out = cw.assigned(["AAA", "BBB", "CCC"], _vec("0.60", "0.40"))
    assert out == {"AAA": Decimal("0.60"), "BBB": Decimal("0.40")}
    assert "CCC" not in out


def test_more_rungs_than_names_leaves_the_surplus_unspent():
    out = cw.assigned(["AAA"], _vec("0.60", "0.40"))
    assert out == {"AAA": Decimal("0.60")}


def test_a_duplicate_name_is_refused_on_both_entry_points():
    """A silent ``set()`` would pay one rung twice and leave the last unpaid, and every size
    assertion downstream would still pass. That class of bug is why this raises."""
    with pytest.raises(ValueError, match="duplicate"):
        cw.assigned(["AAA", "AAA"], _vec("0.60", "0.40"))
    with pytest.raises(ValueError, match="duplicate"):
        cw.rung_order(["AAA", "AAA"], tag=TAG, seed=SEED)


def test_a_float_weight_is_refused():
    """``sim.book.Target.weight`` is a Decimal and a float there is a TypeError. The vector that
    feeds it is held to the same rule rather than silently quantized here."""
    with pytest.raises(TypeError, match="Decimal"):
        cw.assigned(["AAA"], [0.5])  # type: ignore[list-item]


def test_the_ladder_is_the_keep_order_and_carries_no_date():
    """Date-free by construction: the ladder IS ``control_draw.keep_key``'s order, so a rung moves
    only when a neighbour leaves the book and never on the calendar alone."""
    order = cw.rung_order(NAMES, tag=TAG, seed=SEED)
    assert order == sorted(NAMES, key=lambda s: (cd.keep_key(TAG, SEED, s), s))
    assert "data_date" not in inspect.signature(cw.rung_order).parameters
    assert "data_date" not in inspect.signature(cw.assigned).parameters


def test_a_name_that_stays_keeps_its_rung_when_its_neighbours_do():
    """What the ladder buys, stated as a test: drop the last name of the book and every survivor
    is paid the same rung it was paid before."""
    before = cw.assigned(cw.rung_order(NAMES, tag=TAG, seed=SEED), _vec(
        "0.30", "0.25", "0.20", "0.15", "0.10"))
    last = cw.rung_order(NAMES, tag=TAG, seed=SEED)[-1]
    rest = [s for s in NAMES if s != last]
    after = cw.assigned(cw.rung_order(rest, tag=TAG, seed=SEED), _vec(
        "0.30", "0.25", "0.20", "0.15"))
    for s in rest:
        assert after[s] == before[s], s


def test_the_tag_separates_two_books_so_a_twin_pair_can_share_one():
    """``tag`` is the book's method id, not the allocator id: M0221 and M0225 pass the same tag on
    purpose, so the twin pair draws the same names AND pays them the same rungs wherever both
    stores size the same company."""
    assert cw.rung_order(NAMES, tag="M0221", seed=SEED) != cw.rung_order(
        NAMES, tag="M0225", seed=SEED
    ) or True  # the orders MAY coincide on five names; the keys must not
    assert cd.keep_key("M0221", SEED, "AAA") != cd.keep_key("M0225", SEED, "AAA")


def test_the_module_computes_no_vector_and_reads_no_market():
    """The honest core of R2, asserted rather than argued: this module owns the ASSIGNMENT of a
    vector a chassis hands over, and it has no way to produce one. If it ever imports a store, a
    market or a strategy, the contract has quietly become something else."""
    src = ast.parse(inspect.getsource(cw))
    imported = set()
    for node in ast.walk(src):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
    assert imported == {"__future__", "collections.abc", "decimal",
                        "seer_engine.lab.control_draw"}


def test_the_rule_id_and_the_three_measured_ladders_are_named():
    """``ORDERS`` is the record that three ladders were measured and one was chosen. A method file
    naming its wiring must be naming something this module recognises."""
    assert cw.RULE_ID == "matched-weight-v1"
    assert cw.ORDERS == ("ladder", "own-size", "entry")
```

**Impact:** `pytest engine/tests/test_lab_control_weight.py` green. Still no engine behaviour
anywhere: nothing imports `control_weight` yet.

---

## 3. M0221 — the first arm

**Run the whole of §3 before touching M0225. One method at a time, one `lab run` at a time. A
parallel wave of lab phases took this laptop down twice on 2026-10-19.**

### Step 3a: the free pre-run probe, on the real store

**File:** `/tmp/claude-1000/-home-miftah-seer/<session>/scratchpad/weight_probe.py` (scratchpad,
**never** the repo)

This is index invariant I7 step 1 and it is not optional. Phase 4 measured the rule in a
scratchpad prototype; this confirms the rule as it is actually written in `control_weight.py` and
`m0221`, on the real store, **before** a trial exists. It records nothing, opens no lab database
and spends no look. It is also invariant I8 in its strongest form: both arms are measured inside
**one** `run_registry` sweep, so the ratio is re-run against re-run and not against recorded
trial #713.

```python
"""Does the weight-matched control land inside WARN_BAND on the real store, before any trial?

Two candidates, one `dev.run_registry` sweep, on the funding every lab trial runs on
(OWNER_MONTHLY, the default INITIAL_IDR). Writes nothing, opens no lab database, spends no
test-window look. The numbers it prints are `RunStats.turnover` and `Metrics.trades` -- the SAME
two columns `trials` records and `control_shape` reads -- so unlike a basket-change proxy this
predicts the recorded ratio rather than standing in for it.

Re-run against re-run (plan invariant I8): the real arm is re-run here beside the control instead
of being read out of `trials`, because a recorded row is not reproducible to the digit.
"""

from __future__ import annotations

import os
from pathlib import Path

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.lab.control_shape import WARN_BAND
from seer_engine.lab.methods import m0221_cap_weighted_top_n as m0221
from seer_engine.sim.contributions import OWNER_MONTHLY

STORE = Path(os.environ["SEER_RESEARCH_STORE"])

REAL = next(c for c in m0221.METHOD.all_candidates() if c.id == "M0221-C50")
CTRL = next(c for c in m0221.METHOD.all_candidates() if c.id == "M0221-C50-PLCW")


def main() -> int:
    data = research.load_store(STORE)
    rows = dev.run_registry(
        data.market, data.dividends, data.spy_dividends, (REAL, CTRL),
        contributions=OWNER_MONTHLY,
    )
    by = {r.candidate.id: r for r in rows}
    real, ctrl = by[REAL.id], by[CTRL.id]
    rt = ctrl.stats.metrics.trades / real.stats.metrics.trades
    ro = ctrl.stats.turnover / real.stats.turnover
    for r in (real, ctrl):
        print(f"{r.candidate.id}: trades {r.stats.metrics.trades}, "
              f"turnover {r.stats.turnover:.4f}")
    print(f"ratios: trades {rt:.3f}x, turnover {ro:.3f}x  (band {WARN_BAND[0]}-{WARN_BAND[1]})")
    lo, hi = WARN_BAND
    ok = lo <= rt <= hi and lo <= ro <= hi
    print("GO" if ok else "STOP: outside WARN_BAND on at least one axis")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

Run it — **redirection, never a pipe**: a pipe hands the exit code to the last stage.

```bash
SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
PYTHONPATH=/home/miftah/seer/engine/src \
/home/miftah/seer/engine/.venv/bin/python \
  /tmp/claude-1000/-home-miftah-seer/<session>/scratchpad/weight_probe.py \
  > /tmp/claude-1000/-home-miftah-seer/<session>/scratchpad/weight_probe.log 2>&1
echo "exit=$?"
cat /tmp/claude-1000/-home-miftah-seer/<session>/scratchpad/weight_probe.log
```

The probe needs `M0221-C50-PLCW` to exist, so **step 3b is written first and this probe is run
before step 3c's commit.** Nothing is pre-registered until the probe passes, which costs no method
id, no trial, no N and no look.

**STOP rule, and it is the same one phase 4 carries:** if the probe prints `STOP`, do **not**
commit the method file. Revert the working-tree change to `m0221` (`git checkout --
engine/src/seer_engine/lab/methods/m0221_cap_weighted_top_n.py`), keep `control_weight.py` and its
test (they are a mechanism, not a pre-registration, and they are correct either way), and write
`phase-5-results.md` with verdict **STOP**, the probe's two ratios, and the observation that
phase 4's prototype did not survive contact with the real chassis. **Do not re-ladder.** Three
ladders were measured in phase 4; a fourth chosen after seeing a miss is tuning a control until
the margin looks right, which this lab has written down twice as forbidden.

**Expected cost:** loading the dev store is one to two minutes; two full dev sweeps of a 50-name
monthly book are a few minutes each.

### Step 3b: the amendment, written before any result

**File:** `engine/src/seer_engine/lab/methods/m0221_cap_weighted_top_n.py` — inserted immediately
**before** `METHOD = Method(` (today `m0221:506`), i.e. after `MATCHED_AMENDMENT`'s closing `)`.

**Change:** a new imports line, a new allocator under a new id, a new `Amendment` block, and one
name added to `METHOD`'s `amendments=` tuple on the file's last lines.

**Code — the import, added to the existing import block** (`m0221:63`, beside
`from seer_engine.lab import control_draw`):

```python
from seer_engine.lab import control_draw, control_weight
```

**Code — the new block, in full:**

```python
# ---- amendment 2 (2026-10-20): the weight vector ----------------------------------------------
#
# Amendment 1 closed one of the two axes and said in its own `expected_failure` that it might not
# close the other: "E50 holds C50's exact names and trades C50's exact 360 times, yet turns over
# 1.60x as much, because a flatter weight vector crosses the resize band more often -- and a blind
# draw from the sized pool is flatter than the top fifty are". It landed at 1.03x trades and 1.95x
# turnover, and that is exactly what happened. The names are matched; the weights are not.
#
# This block changes one thing and nothing else: the fifty drawn names are paid C50's OWN weight
# vector -- the fifty weights C50 holds that month, sorted, the biggest paid to the first name of a
# date-free ladder -- instead of being weighted by their own market values. The draw, the pool, the
# churn match, the hash namespace, the seed, the ceiling and the params value are all amendment 1's,
# untouched. `MatchedCapTopAllocator` and its `_matched` are a recorded arm's code (trial #843) and
# are NOT refactored: a module body is outside `config_digest`, so editing A1 to share a helper
# with A2 would silently change what a recorded trial means while every test stayed green. The new
# `_matched` is therefore a full copy with one step replaced, and this comment is why.

WEIGHT_AMENDED = date(2026, 10, 20)

#: Which of ``control_weight.ORDERS`` this chassis pays the vector onto. Phase 4 measured all
#: three on this chassis before a line of this block was written; this is the one it chose.
WEIGHT_RULE = "ladder"


class WeightMatchedCapTopAllocator(MatchedCapTopAllocator):
    """Amendment 1's matched draw, paid the real arm's own weight vector instead of its own sizes.

    ``M0221-C50-PLC`` matched C50's entry count by construction and recorded 371 trades against
    360 -- 1.03x, with a free pre-run probe reading 1.000 basket changes -- and still turned over
    0.8681 against 0.4450, **1.95x**. Turnover on a cap-weighted book is a property of the weight
    vector and not of the names: ``E50`` holds C50's exact fifty names and records C50's exact 360
    trades and still pays 1.60x, because fifty equal slots cross the book engine's 1%-of-equity
    resize band on every relative price move while C50's market-value weights track their own
    prices and rarely cross it. A blind draw from the sized pool is flatter still -- it almost never
    holds a name big enough for the 10% ceiling to bind -- so it pays the 1.60x and then some.

    So this arm takes C50's **shape** as well as C50's size and churn. Each month it computes C50's
    own fifty weights with ``weights`` -- the identical function, the identical ceiling, over C50's
    own picks -- sorts them, and pays the largest to the first name of ``control_weight.rung_order``
    and so on down. ``control_weight`` owns that assignment and nothing else; the vector is this
    chassis's own, because no shared module can produce one (see that module's docstring).

    **It is still blind, and the blindness is narrower than amendment 1's rather than wider.**
    Amendment 1 took from the real arm how many names changed. This one additionally takes the
    multiset of weights the real arm holds -- a shape, never an identity. ``control_weight.assigned``
    reads the vector's VALUES and never its order, so which real name held which weight is not
    something this arm can see; and the rung a drawn name takes is a date-free hash of its own
    symbol, so nothing it reads about a name decides that name's weight either.

    **No state and no extra lookback.** The real arm's vector is computed from the selection
    ``_matched`` already takes at ``data_date``, so this costs one extra ``weights`` call per
    decision and not one extra pass of the pool; ``lookback`` is amendment 1's, unchanged at
    ``control_draw.lookback_for(DV_N)``. ``rung_order`` is a pure function of (names, tag, seed)
    and holds nothing: ``dev.run_registry`` reuses one allocator object per id across candidates
    and across folds, so an allocator that remembered a rung would leak it between them.

    The hash namespace is ``DRAW_KEY`` for amendment 1's reason, which now covers two axes: M0225's
    twin inherits this class and must draw the same names AND pay them the same rungs wherever both
    stores size the same company, or the before-and-after would carry a draw change on top of the
    data change it exists to measure.

    No share counts (the history-only path): no size, no vector and no targets.
    """

    id = "M0221-A2"

    def _matched(self, prepared: CapTopPrepared, members: AbstractSet[str], data_date: date,
                 held: frozenset[str], p: CapTopParams) -> tuple[Target, ...]:
        if prepared.market is None:
            return ()
        if not trend_on(prepared.history, data_date, _gate(p)):
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
            tag=DRAW_KEY,
            seed=p.seed,
            data_date=data_date,
        )
        if not picks:
            return ()
        rungs = control_weight.assigned(
            control_weight.rung_order(picks, tag=DRAW_KEY, seed=p.seed),
            weights([pool[s] for s in now], p),
        )
        out: list[Target] = []
        for s in picks:
            w = rungs.get(s)
            if w is None:
                continue
            t = target_from_close(s, last_close(prepared.history[s], data_date), w)
            if t is not None:
                out.append(t)
        return tuple(out)


WMATCHED = WeightMatchedCapTopAllocator()


WEIGHT_AMENDMENT = Amendment(
    added=WEIGHT_AMENDED,
    why=(
        "C50-PLC matched C50's names and entries (1.03x) and missed its turnover (1.95x); pay the "
        "same blind book C50's own weight vector and re-state the margin against a control that "
        "matches on both axes"
    ),
    hypothesis=(
        "Written before any result. C50-PLC is the honest control on the name axis and a "
        "handicapped one on the weight axis: it trades 1.03x and turns over 1.95x, so the -0.42 "
        "point deficit it re-stated is quoted against an opponent paying roughly twice C50's "
        "trading cost per trade. The cause was measured before either arm ran -- E50 holds C50's "
        "exact fifty names and records its exact 360 trades and still turns over 1.60x -- so most "
        "of the excess is the weight vector and none of it is the draw. C50-PLCW changes exactly "
        "one thing from C50-PLC: the fifty drawn names are paid C50's own fifty weights that "
        "month, largest to the first name of a date-free hash ladder, instead of being weighted by "
        "their own market values. Prediction, and the shape half decides whether the money half is "
        "readable at all: C50-PLCW lands inside 0.80x-1.25x of C50 on BOTH trades and turnover, "
        "because its entry count is still matched by construction and its weight vector is now "
        "C50's own, so the 1%-of-equity resize band fires on the same dispersion. On money: a "
        "control that stops over-paying turnover pays less of Gotrade's bill than C50-PLC did, so "
        "it earns MORE than C50-PLC's 6.05% a year of the owner's money and C50's -0.42 deficit "
        "WIDENS, to somewhere between -0.4 and -1.0 against the same 7.19% SPY total return. That "
        "is a deficit growing, and it is predicted deliberately: no arm of this method is for "
        "promotion and this one is a measuring stick, not a candidate. Success is a yardstick "
        "whose control is honest on both axes; the margin is whatever it comes out as."
    ),
    expected_failure=(
        "The remedy may push turnover the other way, and the direction was argued before it ran. "
        "C50 turns over only 0.445 because a cap-weighted book is nearly drift-neutral: a name's "
        "target weight is its own market-value share, so the target moves with the same price the "
        "holding does and the resize band rarely fires. C50-PLC is drift-neutral too, for the same "
        "reason on its own drawn names. Paying a FOREIGN vector breaks that: the control's target "
        "for a rung moves with the real book's k-th name's price while its holding moves with its "
        "own, and two uncorrelated drifts cross a 1% band more often than one tracked drift does. "
        "If C50-PLCW turns over MORE than C50-PLC's 1.95x, the weight-vector remedy is measured "
        "dead on the chassis it was proposed for, that is the finding, it is reported as one, and "
        "no fourth assignment ladder is tried. Second, the ladder is itself a turnover generator: "
        "the rung order is date-free, but a name leaving the book shifts every rung below it, so a "
        "month with several exits re-prices the survivors even though they did not move. Third, "
        "the real vector is computed with TODAY's membership at both dates, as amendment 1's "
        "selection is, so a name that joined the index in between is sized as though it had always "
        "been there; the effect is one or two names a year on a fifty-name book. Fourth, if the "
        "shape lands clean and the money moves the other way from the prediction, the direction is "
        "wrong and the number is the record -- the arm is not re-drawn for a better one."
    ),
    candidates=(
        _a("C50-PLCW", WMATCHED, CapTopParams(50, pick="random", seed=1, trend=None),
           "Placebo, shape-matched on both axes: the same fifty-name blind book hash-drawn at "
           "C50's own monthly churn, and paid C50's own weight vector instead of its own sizes",
           supersedes=("M0221-R50", "M0221-C50-PLC")),
    ),
)
```

**And the final statement's tuple** (`m0221:524`, the last line of the file):

```python
    amendments=(MATCHED_AMENDMENT, WEIGHT_AMENDMENT),
```

**The three wirings, and taking exactly one.** `WEIGHT_RULE` and the two lines inside `_matched`
that build `rungs` are the only thing that differs between phase 4's three outcomes. Paste the one
whose key §0 chose and delete the other two from your working copy — **do not ship dead branches**;
`control_weight.ORDERS` is the record that three were measured.

- **`G-ladder`** (as written above):
  ```python
  WEIGHT_RULE = "ladder"
  ```
  ```python
          rungs = control_weight.assigned(
              control_weight.rung_order(picks, tag=DRAW_KEY, seed=p.seed),
              weights([pool[s] for s in now], p),
          )
  ```
- **`G-size`** — the rung moves with the drawn name's own price, the most drift-neutral ladder:
  ```python
  WEIGHT_RULE = "own-size"
  ```
  ```python
          rungs = control_weight.assigned(
              sorted(picks, key=lambda s: (-pool[s], s)),
              weights([pool[s] for s in now], p),
          )
  ```
  (and the docstring's "first name of ``control_weight.rung_order``" becomes "biggest of its own
  drawn names"; `control_weight.rung_order` is then unused by this chassis and stays in the module
  for the next one.)
- **`G-entry`** — the brief's literal reading, `matched_names`' own month-keyed order:
  ```python
  WEIGHT_RULE = "entry"
  ```
  ```python
          rungs = control_weight.assigned(picks, weights([pool[s] for s in now], p))
  ```

**Impact:**

- A new allocator id `M0221-A2`. `hardgate._INGREDIENT` is `<(M\d{4})>`, so `<M0221-A2>` matches
  nothing and D12's ingredient map is exactly what it was — the same reason `M0221-A1` was safe.
- A new `config_digest`: rules and params are byte-identical to `M0221-R50`'s and `M0221-C50-PLC`'s
  (`CapTopParams(50, pick="random", seed=1, trend=None)`), and the `allocator=<M0221-A2>` line is
  the whole difference. That satisfies `Method.__post_init__`'s configuration-uniqueness check and
  `trials`' global `UNIQUE(config_digest, window)`.
- **No params dataclass is minted and no field is added.** `CapTopParams` is shared with M0225 and
  a field added to it would move every recorded M0221 **and** M0225 digest
  (`registry._canon` renders a dataclass by `dataclasses.fields()`).
  `test_the_amendment_added_no_field_to_the_params_the_recorded_arms_use` already asserts this and
  must stay green.
- **The resolver, checked before writing the id.** `control_shape.resolve_target` takes the
  control's id with its last `-` segment removed: `"M0221-C50-PLCW".rsplit("-", 1)[0]` is
  `"M0221-C50"`, which is a real arm whose rationale carries no `DRAW_MARKERS` and no
  `DOSE_MARKERS`, so it is eligible and the rung is `sibling-stem` — the strongest rung, the same
  one `M0221-C50-PLC` resolves on. **Two placebos resolving to one target is not a collision:**
  `findings` builds one `Finding` per control arm and `_eligible_targets` excludes placebos from
  being targets, so `C50-PLC` and `C50-PLCW` can never resolve to each other. The memory note
  *"promote breaks on a second resolver key"* is about `paper.roster.RESOLVER` and
  `commands/promote.py:104 object_name_of`, which scans that mapping by object identity; it has no
  bearing on `control_shape`'s ladder and nothing in this phase touches the roster. **Checked and
  does not apply — say so in the results file so the next reader does not re-check it.**
- **`controls=` is NOT declared on any arm this phase writes (Decision D9), and the reason is
  measured.** `control_shape.DECLARATION_ATTR = "controls"` exists but **no method file in the lab
  sets it**, so the `declared` rung of the resolver ladder has never fired. On both M0221 and M0225
  it is not needed: the bullet above shows `sibling-stem` resolves `C50-PLCW` to `C50` correctly,
  and a declaration would be a `Candidate` field exercised for the first time inside a recorded
  trial. *(It would be **safe** to add — `Candidate` already carries `supersedes`, added the same
  way, and `lab.method.config_text` renders only rules + allocator id + params, so a new
  `Candidate` field sits outside `config_digest` by construction. It is simply not needed here,
  and the results file says so in one line so the next reader does not re-derive it.)* **M0201 is
  the one place to re-check before writing its id** (§6): if `"M0201-Y20-MV10-PLCW".rsplit("-",1)[0]`
  does not resolve to a real eligible arm on the `stem` rung, declare `controls=("M0201-Y20-MV10",)`
  rather than renaming the arm, and record that this is the first use of the `declared` rung.
- `supersedes=("M0221-R50", "M0221-C50-PLC")` declares **both**: the `REFUSE` arm that blocks D17
  and the `WARN` arm that does not. `control_shape`'s own rule is that a `WARN` is superseded too
  — *"a reader meeting the honest number has to be told the old one was answered"* — and leaving
  one of a re-drawn pair unmarked would say the opposite. Supersession is **declared, never
  inferred**, and it is outside `config_digest`.
- **Neither supersession fires unless `C50-PLCW` reads `OK`.** `superseding_arm` requires the
  superseder's verdict to be `OK`, not merely inside `REFUSE_BAND`. A `warn` arm retires nothing —
  that is exactly why `M0221-C50-PLC`'s correct declaration is inert today.

### Step 3c: commit the pre-registration — **the commit is the pre-registration**

Only after the probe printed `GO`.

```bash
cd /home/miftah/seer
git hash-object lab/lab.sqlite          # record it; expect 607b78cf69c8e4e3a68a1e84c85eedfd1040c754
/home/miftah/seer/engine/.venv/bin/ruff check engine
PYTHONPATH=/home/miftah/seer/engine/src \
  /home/miftah/seer/engine/.venv/bin/pytest engine/tests -x -q \
  engine/tests/test_lab_control_weight.py engine/tests/test_lab_control_draw_twins.py \
  engine/tests/test_lab_methods.py

git add engine/src/seer_engine/lab/control_weight.py \
        engine/tests/test_lab_control_weight.py \
        engine/src/seer_engine/lab/methods/m0221_cap_weighted_top_n.py \
        engine/tests/test_lab_control_draw_twins.py
git commit -m "lab: M0221 pre-registered — the blind book paid the real book's own weight vector

C50-PLC matched C50's names and its entry count by construction (371 trades against 360,
1.03x, a free probe reading 1.000 basket changes) and still turned over 1.95x. That half
was never the matched draw's to close: E50 holds C50's exact fifty names and records its
exact 360 trades and turns over 1.60x, so turnover on a cap-weighted book is a property of
the weight vector and not of the names.

control_weight is the second rule on the second axis, in its own module because that is
what it is. It owns the assignment of a vector the chassis hands over and nothing else --
no shared module can produce a weight vector, because every chassis computes its own. The
original 'one reusable rule' requirement, read literally, cannot be met and the module
docstring says so with the E50 number behind it.

C50-PLCW is C50-PLC with one thing changed: the fifty drawn names are paid C50's own fifty
weights that month, largest to the first name of a date-free ladder. The draw, the pool,
the churn match, the hash namespace, the seed, the ceiling and the params value are
amendment 1's, untouched. A1's recorded code is copied rather than refactored: a module
body is outside config_digest, so sharing a helper would silently move what trial #843
means while every test stayed green.

It is pre-registered against C50-PLC's 1.95x and against the possibility that it goes the
wrong way: a foreign vector breaks the drift-neutrality that makes C50 cheap, and if
turnover rises the remedy is measured dead and reported as such. No arm of this method is
for promotion.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

**Commit by pathspec, never `git add -A`, never `git reset --hard`, never `git pull --rebase`
while anything in this set is running** — the checkout is shared and a rebase replays a stale
`lab.sqlite` over the live one.

### Step 3d: run it

```bash
cd /home/miftah/seer
SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
PYTHONPATH=/home/miftah/seer/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab run M0221 --amend
echo "exit=$?"
git hash-object lab/lab.sqlite
```

**Never pipe it.** `grep -v` owns a pipeline's status and a lab command's exit code is the whole
answer: 0 ok, **2 the lab's rules refused the request**, 1 an error. Redirect to a file and `cat`
it if the output is long.

`--amend` runs `pending_amendment`, which is `method.amendments[len(recorded)]` — M0221 has one
recorded row (seq 1, 2026-10-19), so this resolves seq 2 and refuses outright if any byte of
amendment 1's `added`/`why`/`hypothesis`/`expected_failure` moved. That is the check that keeps a
recorded batch of trials from being filed under a hypothesis nobody committed to.

### Step 3e: read the shape

```bash
cd /home/miftah/seer
PYTHONPATH=/home/miftah/seer/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab control M0221
echo "exit=$?"
```

Record, in `phase-5-results.md`:

- `M0221-C50-PLCW` → `M0221-C50`, rung `sibling-stem`, **trades ×** and **turnover ×**, verdict.
  The bar is `WARN_BAND` on **both** axes: `M0221-C50` recorded 360 trades / 0.4450 turnover, so
  the control must land in **288–450 trades** and **0.3560–0.5563 turnover**.
- whether `M0221-R50` and `M0221-C50-PLC` now print `superseded by M0221-C50-PLCW`. They do **only
  if** the new arm read `OK`. A `warn` retires neither, and then the honest sentence is that M0221
  has two measured controls and no clean one.
- the probe's prediction beside the recorded number. On the two pilots of the previous set the
  probe predicted the recorded ratio to within 0.01; say whether it did here.
- `trial_funding.mwr` for `M0221-C50` (5.63), `M0221-R50` (6.72), `M0221-C50-PLC` (6.05) and the
  new arm, against SPY TR **7.19 %/yr** on the same deposits, and whether the pre-registered
  direction (the deficit **widens** past −0.42) held. **A margin that moves the other way is the
  finding and is reported as one** — it is never a reason to re-draw.

### Step 3f: the owner-facing sentence, only if it moved

The standing published reading of M0221, from the previous set's phase 3, is **"C50 trails a blind
draw of the same shape by something between 0 and 0.4 points a year, with the control over-paying
turnover by 1.95×"**. If `C50-PLCW` read `OK`, that range collapses to a number and `lab note` is
how the owner sees it; if it read `warn` or `refuse`, the range stands and the phase says so.

```bash
cd /home/miftah/seer
# write the body first, then one command, exit code read directly
PYTHONPATH=/home/miftah/seer/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab note M0221 \
  --file /tmp/claude-1000/-home-miftah-seer/<session>/scratchpad/m0221_note.txt
echo "exit=$?"
```

**Rehearse on a COPY first. `--dry-run` is NOT a safety net for `lab note` or `lab insight`.**
Measured in `commands/lab.py`: only `lab test` and `lab gate-probe` read `args.dry_run`; `_note`
and `_insight` commit inside `with conn:` regardless, so `lab note --dry-run` writes for real. The
only safe rehearsal is a copy pointed at by `SEER_LAB_DB`:

```bash
S=/tmp/claude-1000/-home-miftah-seer/<session>/scratchpad
cp /home/miftah/seer/lab/lab.sqlite "$S/rehearse.sqlite"
SEER_LAB_DB="$S/rehearse.sqlite" PYTHONPATH=/home/miftah/seer/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab note M0221 \
  --file "$S/m0221_note.txt" > "$S/m0221_note_rehearsal.log" 2>&1
echo "exit=$?"; cat "$S/m0221_note_rehearsal.log"
sqlite3 "file:$S/rehearse.sqlite?mode=ro" "select verdict from methods where id='M0221';"
git -C /home/miftah/seer hash-object lab/lab.sqlite   # MUST be unmoved by the rehearsal
```

Only once it reads right does the real command run. The same applies to M0225's and M0201's notes.

**Invariant I12: no ids, no digests, no code in anything the owner reads.** Not "M0221-C50-PLCW",
not "0.8681", not "WARN_BAND". Plain language: *"the yardstick's blind opponent now holds its
money the same way the yardstick does, as well as changing hands as often, so the gap between them
is finally a like-for-like number."* **Never retry a `lab note` on a non-zero exit without reading
the journal first** — a piped lab command hides its status and a retried append is permanent.

### Step 3g: stage, commit, push

```bash
cd /home/miftah/seer
PYTHONPATH=/home/miftah/seer/engine/src \
  /home/miftah/seer/engine/.venv/bin/python -m seer_engine lab stage
echo "exit=$?"
git status --short
git commit -m "lab: M0221 — <the one-line finding, plain, no ids>

<what the arm measured, what the margin now is, whether the supersessions fired>

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push
git hash-object lab/lab.sqlite
```

**`lab stage` targets the checkout that owns the database — here, this one — and its commit takes
NO pathspec.** A pathspec re-reads the working tree and defeats the staging;
`test_the_committed_snapshot_is_the_export_of_the_committed_database` is what goes red if it is
used. `lab stage` git-adds `lab/lab.sqlite` and `web/data/lab.json` together, so `git commit` with
no paths is correct and deliberate here even though every other commit in this phase is by
pathspec.

> **The snapshot test is expected RED between `lab run --amend` and `lab stage`, and the suite must
> not be run in that window.** `test_the_committed_snapshot_is_the_export_of_the_committed_database`
> reads the **working tree**, so a freshly-run trial that has not been staged fails it by
> construction. **Invariant I11 asks for a green suite at the END of the phase, after the last
> `lab stage` — not in the middle of it.** Phases 3 and 6 have the same window and say the same
> thing. Under branch G this phase has that window **twice or three times** (once per `lab run`),
> and the suite is run at each `lab stage` boundary and again at the end.

**If the push is rejected, MERGE — never rebase.** `git fetch origin` then `git merge origin/main`;
a `git pull --rebase` replays a stale `lab.sqlite` over the live shared database other sessions in
this set are writing (`seer-rebase-replays-stale-lab-sqlite`). After the merge, **re-run
`lab stage`** so the snapshot matches the merged database, check `select n from trials order by n`
is still contiguous, commit the re-stage with **no pathspec**, and push again. Phases 3 and 6 carry
the identical rule.

---

## 4. M0225 — the honest control it has never had

**Only after §3 is committed and pushed. One `lab run` at a time.**

M0225 is the whole reason remedy 2 exists as a plan phase rather than a footnote: leftover 1 of the
honest-control handover says *"do not draw it under `control_draw` as it stands; it is work for
item 2"*, and item 2 is this. Its `−0.890` deficit is still quoted against `M0225-R50`, which
traded **0.195×** and turned over **0.424×** the book it controls.

### Step 4a: the probe

The same script as step 3a with three lines changed — `m0225` instead of `m0221`, `"M0225-C50"`
and `"M0225-C50-PLC"`. Run it before committing. Same STOP rule.

### Step 4b: the amendment

**File:** `engine/src/seer_engine/lab/methods/m0225_cap_weighted_top_n_repaired.py` — inserted
immediately before `METHOD = Method(` (today `m0225:101`), after `E100_AMENDMENT`'s closing `)`.

**Change — the import** (`m0225:51`):

```python
from seer_engine.lab.methods.m0221_cap_weighted_top_n import (
    CapTopAllocator,
    CapTopParams,
    WeightMatchedCapTopAllocator,
)
```

**Change — the new block, in full:**

```python
# ---- amendment 2 (2026-10-20): the honest control this method has never had --------------------
#
# M0225 has no shape-matched control at all. Its margin is still quoted against R50, which trades
# 0.195x and turns over 0.424x what C50 does -- a stone, not a measuring stick. The previous set
# deliberately did not draw one: the identical chassis had just missed on M0221 at 1.95x turnover,
# and drawing the twin under the same rule would have spent a run to re-observe the same structural
# miss under a different id. The rule that closes that axis now exists (`lab.control_weight`), so
# the twin is drawn with both halves at once: M0221's matched draw for the names and the weight
# assignment for the vector.
#
# The hash namespace stays M0221's (`DRAW_KEY`, inherited through `WeightMatchedCapTopAllocator`),
# so this arm draws the same names AND pays them the same rungs as M0221's wherever both stores
# size the same company -- which is the only way the before-and-after measures the data repair and
# nothing else. That is the same reason `draw` hardcodes "M0221" and it now covers two axes.

WEIGHT_AMENDED = date(2026, 10, 20)


class RepairedWeightMatchedAllocator(WeightMatchedCapTopAllocator):
    """M0221's weight-matched blind book, recorded under M0225: the same rule on the repaired data.

    Not one line of behaviour differs from ``M0221-A2``. A new allocator id is the honest way to
    record the same rule measured on new data -- a trial's configuration is its rules, its
    allocator id and its params, and M0221's is already recorded -- and it is also the only way,
    since ``trials`` carries a global ``UNIQUE (config_digest, window)``.
    """

    id = "M0225-A2"


WMATCHED = RepairedWeightMatchedAllocator()


def _aw(suffix: str, allocator: Any, params: CapTopParams, rationale: str,
        supersedes: tuple[str, ...]) -> Candidate:
    """An amendment candidate: its own ``added``, its own allocator, and the declaration of which
    recorded arm it replaces.

    ``supersedes`` is what D17 reads (``control_shape.SUPERSEDES_ATTR``). It is DECLARED and never
    inferred from the target, and it sits outside ``config_digest`` because ``config_text`` names
    its three attributes by hand. An arm that declares nothing retires nothing, so leaving this off
    would leave M0225 blocked after the measurement was taken."""
    return Candidate(id=f"M0225-{suffix}", family="M0225", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=allocator, params=params, rationale=rationale, added=WEIGHT_AMENDED,
                     owner_inputs=(), supersedes=supersedes)


WEIGHT_AMENDMENT = Amendment(
    added=WEIGHT_AMENDED,
    why=(
        "M0225 has no shape-matched control at all: its margin is quoted against R50, which trades "
        "0.195x and turns over 0.424x the book it controls, and the twin was deliberately not "
        "drawn until a rule existed that closes the weight axis as well as the name axis"
    ),
    hypothesis=(
        "Written before any result. C50 earned 5.85% a year of the owner's money on the dev window "
        "and R50 earned 6.74% against the same 7.19% SPY total return, so the recorded reading is "
        "that the blind draw BEATS the book by 0.89 points -- and R50 got there on 73 trades where "
        "C50 paid for 375. R50's hash carries no date term, so it drew fifty names once in 1996 "
        "and held them for twenty years; the only fees it ever paid were the ones membership "
        "forced on it. C50-PLC is the same fifty-name blind book with two things changed and "
        "nothing else: the number of names it re-draws each month is C50's own number of entrants "
        "that month, and the weights it pays them are C50's own weights that month, largest to the "
        "first name of a date-free hash ladder. Predictions. Shape, and it is the one that decides "
        "whether the money reading is admissible: C50-PLC lands inside 0.80x-1.25x of C50 on both "
        "trades and turnover. Money: an honest control trades about five times as often as R50 and "
        "pays those fees, so it earns LESS than R50's 6.74% and C50's deficit NARROWS from -0.89 "
        "toward zero, landing between -0.5 and +0.2. Twin: the whole point of M0225 is a "
        "before-and-after on the share-count repair, so this arm and M0221's must land within "
        "about 0.1x of each other on both axes -- they draw the same names and pay the same rungs "
        "wherever both stores size the same company, and a wider gap than that is the repair "
        "showing up in the control, which is itself worth knowing. No arm of this method is for "
        "promotion; it is a yardstick."
    ),
    expected_failure=(
        "M0221's own matched draw on this identical chassis landed at 1.03x trades and 1.95x "
        "turnover, so the name axis is the half already known to work here and the weight axis is "
        "the half on trial. If the weight assignment misses on M0221 it misses here, and this arm "
        "exists partly to say whether the repaired size data changes that -- M0225's E50 pays "
        "1.68x against M0221's 1.60x on identical names and identical trades, so the repaired "
        "store is slightly MORE dispersed and the control has slightly further to travel. Second, "
        "paying a foreign vector can raise turnover rather than lower it: C50 is cheap because a "
        "cap-weighted book is nearly drift-neutral, and a control whose target moves with the real "
        "book's prices while its holding moves with its own crosses the 1%-of-equity resize band "
        "more often, not less. If that is what happens, it is the finding, it is recorded, and no "
        "fourth assignment rule is tried. Third, the money direction may invert: re-keying the "
        "draw monthly changes WHICH names the control holds for twenty years, and a draw resampled "
        "every month converges on the sized pool's own mean return instead of resting on one lucky "
        "1996 sample; if that mean is above what R50's single sticky draw earned, the honest "
        "control earns MORE and the deficit WIDENS past -0.89. That is reported, not re-drawn for."
    ),
    candidates=(
        _aw("C50-PLC", WMATCHED, CapTopParams(50, pick="random", seed=1, trend=None),
            "Placebo, shape-matched on both axes: the same fifty-name blind book hash-drawn at "
            "C50's own monthly churn, and paid C50's own weight vector instead of its own sizes",
            supersedes=("M0225-R50",)),
    ),
)
```

**And the final statement's tuple** (`m0225:162`):

```python
    amendments=(E100_AMENDMENT, WEIGHT_AMENDMENT),
```

**The `Any` import.** `m0225` does not import `Any` today. Add it to the existing `typing` usage:
`from typing import Any` beside `from datetime import date` (`m0225:47`). `ruff check engine` will
catch it if it is missed.

**Impact:**

- Allocator id `M0225-A2` is free (M0225's only allocator today is `M0225` itself; `E100` reuses
  it). `test_allocator_ids_are_unique_across_methods` must stay green.
- `config_digest` differs from `M0225-R50`'s on the `allocator=<M0225-A2>` line alone; params are
  R50's own value, reused verbatim.
- Resolver: `"M0225-C50-PLC".rsplit("-", 1)[0]` is `"M0225-C50"` — a real, non-placebo arm, so
  `sibling-stem`. M0225 has exactly one other placebo (`M0225-R50`, which resolves to `M0225-C50`
  on `first-declared`), and two placebos sharing one target is not a collision.
- `supersedes=("M0225-R50",)` — one arm, because M0225 has only ever had one control.
- M0225's pre-amendment-2 state is pinned by `test_the_new_arm_declares_the_arm_it_supersedes`
  and `test_the_amendment_block_is_the_expected_shape` in the twins module; both are updated in
  §5.

### Steps 4c–4f

Identical in form to 3c–3g, with `M0225` throughout:

- commit `lab: M0225 pre-registered — the honest control the twin never got`, by pathspec;
- `lab run M0225 --amend` (M0225 has one recorded amendment, E100 seq 1, so this resolves seq 2);
- `lab control M0221 M0225` — both methods, so the twin comparison is printed side by side and the
  within-0.1× prediction is readable;
- `lab note M0225` **only if** the new arm read `OK`. Note what is actually true here: M0225's
  **−0.890** is **not** quoted in any owner-facing string today (verified read-only at `e3aeeff`),
  so there is no wrong sentence to correct — what M0225 has is **no honest control at all**, and a
  band-clean arm is the first time the method can carry an honest margin sentence at all. If the
  arm reads `OK`, write that sentence; if it does not, write nothing and say so. I12 applies to
  every word either way;
- `lab stage`, commit with **no pathspec**, push.

The bar: `M0225-C50` recorded **375 trades / 0.4568 turnover**, so the control must land in
**300–469 trades** and **0.3654–0.5710 turnover**.

---

## 5. The one existing test file this phase edits

**File:** `engine/tests/test_lab_control_draw_twins.py`

Two of its tests pin the **pre-amendment** file state and go red the moment §3b lands. They are
inverted to the post-run truth, which is strictly stronger — the lab has written this down:
*"lab tests that pin pre-run DB state go red when the run phase succeeds; invert to the post-run
truth."* Edited as part of §3c's commit, so the tree is never red between commits.

**Change 1** — the module docstring's last paragraph (`:8-18`). Its closing sentence currently
reads *"That is a recorded STOP (plan invariant 13), so M0225's block was never written and the
shared `MatchedCapTopAllocator` is used by exactly one arm today."* Replace that one sentence with:

```
That was a recorded STOP (plan invariant 13) and M0225's block was never written under it.
Amendment 2 is what closes it: ``lab.control_weight`` pays the drawn names C50's own weight vector,
``WeightMatchedCapTopAllocator`` carries both halves, and M0225's twin finally rides on it under
``M0225-A2`` -- which is what ``test_the_matched_allocator_is_reusable_by_a_twin`` was keeping
intact.
```

**Change 2** — `test_the_new_arm_declares_the_arm_it_supersedes` (`:113-122`), replaced in full:

```python
def test_the_new_arms_declare_the_arms_they_supersede():
    """D17's supersession is DECLARED, never inferred from target equality, so an arm that
    declares nothing retires nothing.

    C50-PLC's own declaration stands and still retires nothing: it came out `warn`, and
    `superseding_arm` requires an `OK` superseder, so what blocks M0221 was the measured turnover
    and not a missing tuple. C50-PLCW declares BOTH the arms it answers -- the `refuse` R50 that
    blocks D17 and the `warn` C50-PLC that does not -- because `control_shape` supersedes a warn
    too: a reader meeting the honest number has to be told the old one was answered.
    """
    assert _arm(m0221.METHOD, "M0221-C50-PLC").supersedes == ("M0221-R50",)
    assert _arm(m0221.METHOD, "M0221-C50-PLCW").supersedes == (
        "M0221-R50", "M0221-C50-PLC",
    )
    assert _arm(m0225.METHOD, "M0225-C50-PLC").supersedes == ("M0225-R50",)
    for c in m0221.METHOD.candidates:
        assert c.supersedes == (), f"{c.id}: an original arm declares nothing"
    for c in m0225.METHOD.candidates + tuple(m0225.E100_AMENDMENT.candidates):
        assert c.supersedes == (), f"{c.id}: an original or E100 arm declares nothing"
```

**Change 3** — `test_the_matched_allocator_is_reusable_by_a_twin` (`:135-142`), docstring only;
the three assertions are unchanged and still correct:

```python
def test_the_matched_allocator_is_reusable_by_a_twin():
    """``DRAW_KEY`` is the hash namespace and not the allocator id, so a subclass recorded under
    another method id draws the same names -- and, from amendment 2, pays them the same rungs --
    wherever both stores size the same company. M0225's ``M0225-A2`` is that subclass; this test
    is what kept the piece intact in the year it had no user."""
```

**Change 4** — `test_the_amendment_block_is_the_expected_shape` (`:145-155`), replaced in full:

```python
def test_the_amendment_blocks_are_the_expected_shape():
    """Two amendments each, in declaration order, which is the order `pending_amendment` resolves
    them in: the record must be an exact prefix of the file, so a reordered or reworded block is a
    refusal and a recorded batch of trials can never be filed under a hypothesis nobody committed
    to before seeing it."""
    assert len(m0221.METHOD.amendments) == 2
    assert m0221.METHOD.amendments[0].added == date(2026, 10, 19)
    assert [c.id for c in m0221.METHOD.amendments[0].candidates] == ["M0221-C50-PLC"]
    assert m0221.METHOD.amendments[1].added == date(2026, 10, 20)
    assert [c.id for c in m0221.METHOD.amendments[1].candidates] == ["M0221-C50-PLCW"]
    assert len(m0221.METHOD.candidates) == 6
    assert len(m0221.METHOD.all_candidates()) == 8

    assert len(m0225.METHOD.amendments) == 2
    assert m0225.METHOD.amendments[0] is m0225.E100_AMENDMENT
    assert m0225.METHOD.amendments[1] is m0225.WEIGHT_AMENDMENT
    assert [c.id for c in m0225.METHOD.amendments[1].candidates] == ["M0225-C50-PLC"]
    assert len(m0225.METHOD.all_candidates()) == 8
```

**Change 5** — four new tests appended at the foot of the module:

```python
def test_the_weight_matched_arms_read_as_placebos_on_the_books_they_control():
    """D17 classifies by prose and tests dose BEFORE draw, so an arm that read as dose-response
    would carry no ratio and its refusal would vanish with the handicap still in place. The rung
    matters as much as the kind: `sibling-stem` is what the `<target>-PLC...` name buys, and both
    new ids keep it -- `"M0221-C50-PLCW".rsplit("-", 1)[0]` is `"M0221-C50"`."""
    for method, cid, target in (
        (m0221.METHOD, "M0221-C50-PLCW", "M0221-C50"),
        (m0225.METHOD, "M0225-C50-PLC", "M0225-C50"),
    ):
        arm = _arm(method, cid)
        text = arm.rationale.lower()
        assert cs.kind_of(arm) == cs.KIND_PLACEBO
        assert any(m in text for m in cs.DRAW_MARKERS)
        assert not any(m in text for m in cs.DOSE_MARKERS)
        assert cs.resolve_target(arm, list(method.all_candidates())) == (target, cs.RUNG_STEM)


def test_the_weight_allocators_are_new_ids_that_name_no_ingredient():
    r"""``hardgate._INGREDIENT`` is ``<(M\d{4})>``, so ``<M0221-A2>`` and ``<M0225-A2>`` match
    nothing and D12's ingredient map is exactly what it was."""
    assert m0221.WMATCHED.id == "M0221-A2"
    assert m0225.WMATCHED.id == "M0225-A2"
    assert _INGREDIENT.findall("allocator=<M0221-A2> <M0225-A2>") == []


def test_the_weight_rule_costs_no_extra_lookback():
    """The real arm's vector comes from the selection the matched draw already takes at
    ``data_date``, so amendment 2 reads no bar amendment 1 did not: one extra ``weights`` call per
    decision, not one extra pass of the pool. 473 is ``labkit.smoke_market``'s fixture and the cut
    every lab allocator clears."""
    assert m0221.WMATCHED.lookback(CONTROL_PARAMS) == m0221.MATCHED.lookback(CONTROL_PARAMS)
    assert m0221.WMATCHED.lookback(CONTROL_PARAMS) == cd.lookback_for(m0221.DV_N)
    assert m0225.WMATCHED.lookback(CONTROL_PARAMS) <= SMOKE_BARS


def test_the_weight_arms_reuse_the_params_value_and_mint_no_dataclass():
    """The set's one params rule, carried into the second amendment: no new dataclass anywhere,
    the allocator id is the whole difference. ``CapTopParams`` is shared by M0221 and M0225, so one
    added field -- even a defaulted one -- would move every recorded digest of both."""
    for method, cid in ((m0221.METHOD, "M0221-C50-PLCW"), (m0225.METHOD, "M0225-C50-PLC")):
        new = _arm(method, cid)
        assert new.params == CONTROL_PARAMS
        assert new.params.pick == "random", "a blind book must not describe itself as a ranked one"
    assert [f.name for f in fields(m0221.CapTopParams)] == [
        "top", "weighting", "cap", "pick", "seed", "trend"
    ]
    assert config_digest(_arm(m0221.METHOD, "M0221-C50-PLCW")) != config_digest(
        _arm(m0221.METHOD, "M0221-C50-PLC")
    )
    assert config_digest(_arm(m0225.METHOD, "M0225-C50-PLC")) != config_digest(
        _arm(m0221.METHOD, "M0221-C50-PLCW")
    )
```

**Impact:** `test_lab_control_draw_twins.py` is green before and after each of this phase's two
engine commits. It is the only existing test file this phase touches.

---

## 6. M0201 — conditional, and the gate is tight

**Run this only if phase 4's results file records, with numbers, that the chosen rule brings
`M0201-Y20-MV10-PLC1`'s successor inside `WARN_BAND` on BOTH axes, measured re-run against re-run
on M0201's own chassis.** The index's phase-5 scope is explicit: *append, **only** if phase 4
showed the rule closes its gap.* If phase 4 did not measure M0201 at all, or measured it and it
missed, **skip this section entirely** and write §6's "what was not drawn" paragraph instead.

### Why the gate is tighter here than on M0221

- **The gap is 0.0059.** `M0201-Y20-MV10-PLC1` is at 0.949 trades / **0.794** turnover against a
  0.80 floor. It needs ≥ **1.937** turnover and has 1.923 — short by 0.014 absolute. This is the
  one arm in the set that needs **more** turnover, the opposite direction to M0221's.
- **M0201 already has one clean control.** `M0201-Y20-MV10-PLC2` reads **0.961 / 0.839, `ok`**, and
  already supersedes `M0201-PLC2-MV10`. The method is not control-less the way M0225 is.
- **M0201's real weight vector cannot be read exactly — only estimated**, and the estimation error
  is R1's defect appearing on the weight axis. `resize` sizes the book the chassis *actually
  holds*, and the real held set is behind M0197's 40 % keep band at a quarterly re-pick; an
  allocator is handed only its **own** `held`. So `real_profile` below sizes the **fresh** bond
  top-20 at `data_date`, exactly as `matched_entries` already sizes the fresh top-20 at the
  previous re-pick. That approximation is measured at **0.955** on the entry count and is
  **unmeasured on the weight vector**. It must be stated in `expected_failure` before the run, and
  it is the strongest single reason to let M0201 stand.
- **D17's refusal on M0201 is inert.** `hardgate.check` raises on the walk-forward fold majority
  **before** it reaches D17, so clearing PLC1 changes the refusal *message* and not the answer.
  Nothing about promotion rides on this.

**If in doubt, do not draw it.** An amendment is cheap in method ids and is not free in compute,
in risk to a frozen record, or in the credibility of a control whose vector is an estimate.

### Step 6a: the code, in full

**File:** `engine/src/seer_engine/lab/methods/m0201_treasury_beta_size_weighted.py` — inserted
immediately before `METHOD = Method(` (today `m0201:585`), after `MATCHED_CONTROL_AMENDMENT`'s
closing `)`.

**Change — the import** (`m0201`'s import block, beside `matched_partition`):

```python
from seer_engine.lab import control_weight
```

**Change — the new block:**

```python
# ------------------------------------------------------------------ amendment 2 (2026-10-20)
#
# PLC1-MV10 landed at 0.949x trades and 0.794x turnover -- short of the 0.80 match band by 0.0059
# in ratio, 0.014 in absolute turnover -- and PLC2-MV10 at 0.961/0.839 cleared it. Amendment 1's
# own `expected_failure` named this before it ran: "M0201 re-sizes monthly by company size, and a
# blind book holds mega-caps the bond book never does, so its weight dispersion and its monthly
# resize trades differ even when its entries match." This block pays the blind book the bond
# book's own weight vector instead of its own company sizes, which is the one lever that acts on
# dispersion without touching the entry count the matched draw already got right.
#
# The honest caveat, written before the run: the real book's vector CANNOT be read exactly here.
# `resize` sizes the book the chassis actually holds, and the real held set sits behind M0197's 40%
# keep band at a quarterly re-pick, while an allocator is handed only its OWN `held`. So
# `real_profile` sizes the FRESH bond top-20 at this date, exactly as `matched_entries` sizes the
# fresh top-20 at the previous re-pick. That substitution costs 0.045 on the entry count (measured)
# and an unmeasured amount on the vector.

WEIGHT_AMENDED = date(2026, 10, 20)
WEIGHT_RULE = "ladder"


def real_profile(prepared: SizedPrepared, members: AbstractSet[str], data_date: date,
                 p: SizedYieldBetaParams) -> list[Decimal | None]:
    """The weight vector the bond book itself pays its stock slots on ``data_date``.

    ``resize``'s own arithmetic over the bond side's fresh top-20: one size per company, unknown
    sizes at the median, the exposure the equal book holds, the 10% ceiling, a company's weight
    split equally over its held classes. The only thing it does not reproduce is WHICH twenty --
    the real book's are behind the keep band and an allocator cannot see them -- so this is the
    fresh top-20 and the substitution is the amendment's stated residual.

    Returned in the picks' own order; ``control_weight.assigned`` reads only the multiset of
    values, never the order, so the real book's identity does not leak through it.
    """
    now = real_frac_at(prepared, members, data_date, p)
    if not now:
        return []
    top = p.yb.inner.top
    picks = [s for _, s in sorted((v, s) for s, v in now.items())][:top]
    size = sizes(prepared, picks, data_date, p)
    keys = list(size)
    cw = sized_weights([size[k] for k in keys], len(picks) / top, float(p.cap))
    weight = dict(zip(keys, cw, strict=True))
    out: list[Decimal | None] = []
    for s in picks:
        w = weight[company(s)]
        if w is None:
            out.append(None)
            continue
        n = sum(1 for x in picks if company(x) == company(s))
        out.append(_floor_weight(float(w) / n) if n > 1 else w)
    return out


def assigned_resize(prepared: SizedPrepared, members: AbstractSet[str],
                    equal: tuple[Target, ...], data_date: date,
                    p: SizedYieldBetaParams) -> tuple[Target, ...]:
    """``resize`` with the stock slots paid the bond book's own sorted weights.

    ``resize``'s body is a recorded arm's code (``M0201`` and ``M0201-A1``) and is not refactored:
    a module body is outside ``config_digest``, so threading a flag through it would move what four
    recorded trials mean while every test stayed green. This is a sibling, and the SPY filler, the
    market symbol and the exposure arithmetic are reproduced rather than shared for that reason.
    """
    market = p.yb.market
    picks = [t.symbol for t in equal if t.symbol != market]
    rungs = control_weight.assigned(
        control_weight.rung_order(picks, tag="M0201", seed=p.seed),
        real_profile(prepared, members, data_date, p),
    ) if picks else {}
    out: list[Target] = []
    for s in picks:
        w = rungs.get(s)
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


class WeightMatchedSizedPlaceboAllocator(MatchedSizedPlaceboAllocator):
    """Amendment 1's matched draw, its stock slots paid the bond book's own weight vector.

    Everything else is ``MatchedSizedPlaceboAllocator``'s and therefore M0197's: the screen, the
    40% keep band, the quarterly re-pick calendar, the SPY filler, the seed and the matched entry
    count. ``lookback`` is amendment 1's ``MATCHED_LOOKBACK`` unchanged -- the vector is read at
    ``data_date``, which ``matched_frac`` already reaches -- so no window moves.

    ``real_frac_at`` is computed twice per decision, once inside ``matched_frac`` and once inside
    ``real_profile``. That is a cost and not a correctness problem, and it is paid rather than
    threaded through amendment 1's recorded code, which must not be edited.
    """

    id = "M0201-A2"

    def _run(self, prepared: SizedPrepared, members: AbstractSet[str], data_date: date,
             held: frozenset[str], p: SizedYieldBetaParams) -> tuple[Target, ...]:
        p = _check_control(p)
        if len(prepared.series) == 0 or prepared.market is None:  # market-aware contract
            return ()
        inner = p.yb.inner
        if not trend_on(prepared.history, data_date, inner):
            return ()
        stocks = [s for s in held if s != p.yb.market and s not in EXCLUDED]
        repick = not stocks or data_date.month in REPICK_MONTHS
        frac = matched_frac(prepared, members, data_date, held, p) if repick else {}
        equal = choose(prepared.history, members, frac, data_date, held, p.yb)
        return assigned_resize(prepared, members, equal, data_date, p)


WMATCHED = WeightMatchedSizedPlaceboAllocator()


def _vw(suffix: str, params: SizedYieldBetaParams, rationale: str,
        supersedes: tuple[str, ...]) -> Candidate:
    return Candidate(id=f"M0201-{suffix}", family="M0201", rules=MONTHLY_HOLD_FRAC_GOTRADE,
                     allocator=WMATCHED, params=params, rationale=rationale, added=WEIGHT_AMENDED,
                     owner_inputs=(), supersedes=supersedes)


WEIGHT_AMENDMENT = Amendment(
    added=WEIGHT_AMENDED,
    why=(
        "Y20-MV10-PLC1 matched the bond book's entries (0.949x) and missed its turnover by 0.0059 "
        "in ratio; pay the blind book the bond book's own weight vector, which is the one lever "
        "that moves dispersion without touching the entry count"
    ),
    hypothesis=(
        "Written before any result. PLC1-MV10's successor landed at 0.949x trades and 0.794x "
        "turnover against Y20-MV10's 433 trades and 2.4213 turnover -- 0.014 of absolute turnover "
        "short of the 0.80 match band, while its seed-2 twin cleared it at 0.961/0.839. The cause "
        "was pre-registered in amendment 1: a blind book of twenty members holds mega-caps the "
        "bond book never does, so its weight dispersion is flatter, its 10% ceiling binds less "
        "often and its monthly resize trades are fewer even when its entries match. This arm keeps "
        "the screen, the band, the quarterly calendar, the ceiling, the SPY filler, the seed and "
        "the matched entry count, and changes one thing: the twenty blind names are paid the bond "
        "book's own twenty weights that month, largest to the first name of a date-free hash "
        "ladder, instead of being sized by their own company sizes. Prediction, shape first: "
        "Y20-MV10-PLCW lands inside 0.80x-1.25x on BOTH axes against Y20-MV10, and its turnover "
        "rises from 0.794x toward 0.95x, because it now pays the real book's own dispersion and "
        "re-sizes on the real book's own drift. Money: a control that turns over more pays more of "
        "Gotrade's bill and earns LESS than PLC1's recorded figure, so Y20-MV10's deficit against "
        "seed 1 NARROWS from its re-stated value toward zero. Success for the amendment is the "
        "shape alone; the margin is whatever it comes out as and no seed is touched."
    ),
    expected_failure=(
        "The vector this arm pays is an ESTIMATE and the estimate's error is unmeasured. The bond "
        "book's real weights are the weights of the twenty names it actually holds, and those sit "
        "behind M0197's 40% keep band at a quarterly re-pick; an allocator is handed only its own "
        "holdings, so this arm sizes the FRESH bond top-20 at each date instead. The same "
        "substitution on the entry count was measured at 0.955 of the truth; on the weight vector "
        "it is not measured at all, and a held book that has drifted toward the edge of the band is "
        "flatter than a fresh top-20, so this arm may pay a vector steeper than the one it is "
        "matching and overshoot past 1.25x. Second, the direction may invert outright: Y20-MV10 is "
        "cheap in turnover terms partly because its own sizes drift with its own prices, and a "
        "control whose target moves with the bond book's prices while its holding moves with its "
        "own crosses the 1%-of-equity resize band more often -- the remedy can add turnover past "
        "the band rather than into it. Third, a ladder re-prices every survivor below a name that "
        "leaves, so a quarter with several exits moves weights the book did not move. Fourth, "
        "M0201's seed-2 arm is already clean at 0.961/0.839 and is not re-drawn, so if this one "
        "misses the method keeps exactly the one honest control it has today and nothing is worse "
        "than before. Fifth, whatever this does, D17 is not M0201's operative refusal: the hard "
        "gate raises on the walk-forward fold majority first, so nothing here moves a promotion."
    ),
    candidates=(
        _vw("Y20-MV10-PLCW", _p("placebo", seed=1),
            "Placebo, shape-matched on both axes: the same scoreable names in a hash order "
            "(seed 1), re-drawn only as often as the bond book's own picks turn over, and paid "
            "the bond book's own weight vector instead of their own company sizes",
            supersedes=("M0201-PLC1-MV10", "M0201-Y20-MV10-PLC1")),
    ),
)
```

**And the final statement's tuple** (`m0201:658`):

```python
    amendments=(MATCHED_CONTROL_AMENDMENT, WEIGHT_AMENDMENT),
```

**Resolver check:** `"M0201-Y20-MV10-PLCW".rsplit("-", 1)[0]` is `"M0201-Y20-MV10"` — a real,
non-placebo arm. `sibling-stem`, the same rung `M0201-Y20-MV10-PLC1` and `-PLC2` already take.
M0201 will then carry four placebo arms all resolving to the same two books; that is the ladder
working, not a collision.

**Imports to check:** `AbstractSet`, `Decimal`, `Target`, `target_from_close`, `last_close`,
`EXCLUDED`, `REPICK_MONTHS`, `choose`, `trend_on`, `sizes`, `sized_weights`, `company`,
`_floor_weight` and `real_frac_at` are all already imported or defined in `m0201`. Only
`control_weight` is new. `ruff check engine` is the check.

### Step 6b–6f

Probe (the §3a script with `m0201`, `"M0201-Y20-MV10"` and `"M0201-Y20-MV10-PLCW"`), commit the
pre-registration by pathspec, `lab run M0201 --amend` (M0201 has one recorded amendment, so this
resolves seq 2), `lab control M0201`, `lab note` only if `OK`, `lab stage`, commit with no
pathspec, push.

The bar: `M0201-Y20-MV10` recorded **433 trades / 2.4213 turnover**, so the control must land in
**346–541 trades** and **1.9370–3.0266 turnover**.

### If M0201 is not drawn

Write this paragraph into `phase-5-results.md` instead, and do not leave it to phase 6 to infer:

> **M0201 was not re-drawn, and the reason is the measurement.** Phase 4 did not show the weight
> rule closing `Y20-MV10-PLC1`'s 0.0059 gap on M0201's own chassis, so the index's condition for
> appending to that file was not met. What M0201 has today stands: `Y20-MV10-PLC1` at 0.949 /
> **0.794** (`warn`, 0.0059 short on turnover) and `Y20-MV10-PLC2` at 0.961 / 0.839 (`ok`, and
> already superseding `M0201-PLC2-MV10`). So the method does hold one honest control and the arm
> it is still partly quoted against is a warn, not a refusal. Two further facts, so a reader does
> not go looking: the real book's weight vector is not readable on this chassis — the bond book's
> twenty names sit behind a 40 % keep band and an allocator is handed only its own holdings, so any
> vector here would be the fresh top-20's, an estimate whose error is measured at 0.955 on the
> entry count and unmeasured on the vector; and D17 is not M0201's operative refusal anyway, since
> `hardgate.check` raises on the walk-forward fold majority first.

---

## 7. Verification

**Build / lint** (after every engine edit, before every commit):

```bash
cd /home/miftah/seer
/home/miftah/seer/engine/.venv/bin/ruff check engine
```
CI's lint is bugs only — `E9` and `F`, minus `F401` — and it must print `All checks passed!`.

**Tests** (the whole suite, green, at the end of the phase — index invariant I11):

```bash
cd /home/miftah/seer
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
PYTHONPATH=/home/miftah/seer/engine/src \
  /home/miftah/seer/engine/.venv/bin/pytest engine/tests
```

`PYTHONPATH` decides which code **and** which `lab.sqlite` is read (`config.REPO_ROOT =
Path(__file__).resolve().parents[3]`). The DB tests need Postgres and CI fails if they skip.

Specifically green:

- the whole of `engine/tests/test_lab_control_weight.py` (new)
- the whole of `engine/tests/test_lab_control_draw_twins.py` (updated)
- `test_lab_methods.py::test_every_recorded_configuration_still_digests_to_its_recorded_digest`
- `test_lab_methods.py::test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha`
- `test_lab_methods.py::test_allocator_ids_are_unique_across_methods`
- `test_lab_methods.py::test_allocator_contract[M0221-C50-PLCW]`, `[M0225-C50-PLC]` (and
  `[M0201-Y20-MV10-PLCW]` if drawn) — all three allocators are **market-aware**, so the contract
  check requires them to target **nothing** on the history-only path; `targets()` inherits
  amendment 1's `return ()` and that is what satisfies it
- `test_lab_methods.py::test_candidate_runs_a_smoke_window[...]` for the same ids — this is the
  473-bar fixture, and it is where a vector/ladder length mismatch would surface
- `test_lab_snapshot`'s `test_the_committed_snapshot_is_the_export_of_the_committed_database`,
  **after** each `lab stage` commit. It reads the working tree, so it is legitimately red between
  `lab run --amend` and `lab stage`; it must be green at each commit boundary and at the end.

**Manual check:**

- `lab control M0221 M0225` prints both new arms, both resolved by `sibling-stem` to `M0221-C50`
  and `M0225-C50`, both with a measured ratio on **both** axes, and prints `superseded by` on
  `M0221-R50`, `M0221-C50-PLC` and `M0225-R50` **if and only if** the new arms read `OK`.
- `lab status` / `lab show M0221` — the method's status has not moved. An amendment appends trials
  and never moves a verdict; `lab reevaluate` is a separate decision and is **not** run here.
- `git hash-object lab/lab.sqlite` recorded **four** times under branch G (before §3, after §3,
  after §4, after §6-or-skip) and written into the results file. Under branch S, twice and
  identical.
- Test-window looks **4 → 4**, read without migrating the file:
  ```bash
  sqlite3 "file:/home/miftah/seer/lab/lab.sqlite?mode=ro" \
    "select count(*) from trials where window='test';"
  ```
  **`lab test` is never invoked in this phase and `SEER_RESEARCH_TEST_STORE` is never read.**
- `git log --oneline -6` shows, in order: the M0221 pre-registration, the M0221 stage, the M0225
  pre-registration, the M0225 stage (and M0201's pair if drawn). **Every pre-registration commit
  precedes its own run**, which is what makes a fresh clone pass the sha freeze.

**Exit criteria:**

1. §0's branch key is written, with phase 4's numbers behind it, as the first line of
   `.workflows/plan/control-draw-remedies/phase-5-results.md`.
2. **Branch S:** no engine file changed, no lab row written, `lab/lab.sqlite` hashed identically
   before and after, and the results file carries every bullet §0 lists — including leftover 2
   closed with a number and D6 recorded.
3. **Branch G:** `control_weight.py` exists with its own tests; `M0221-C50-PLCW` and
   `M0225-C50-PLC` are recorded dev trials under `M0221-A2` and `M0225-A2`; each was
   pre-registered by a commit that precedes its own `lab run --amend`; `lab control` reports both
   measured ratios; the supersession declarations are on the arms and their firing (or not) is
   stated with the verdict that decides it.
4. M0225's **−0.890** is re-stated against an honest control **or** recorded as still unavailable,
   with the reason — and the results file says explicitly that the figure appears in `trials` and
   in the previous handover and in **no** owner-facing string, so a `lab note` on M0225 is only
   warranted if this phase actually drew it an honest control.
5. The three published sentences this phase can move are each either moved by `lab note` in plain
   owner language, or explicitly left standing with the measured reason — M0221's "between 0 and
   0.4 points", M0225's "−0.890", and M0201's status.
6. `ruff check engine` clean and `pytest engine/tests` green at the end.
7. `lab stage` run in this checkout, committed with **no pathspec**, pushed; `lab/lab.sqlite` and
   `web/data/lab.json` agree row for row.
8. Looks **4 → 4**, asserted and stated. No `lab test`, ever.
9. The results file states, in one sentence and under both branches, that **the gate takes none of
   these methods and this phase implies no promotion** — for M0201, M0221 and M0225 the
   walk-forward fold majority raises before D17 is ever reached.

---

## 8. Handoffs

- **Phase 6 (R2, R3, R4) — the R1 verdict.** This phase supplies the second of its two structural
  facts as a *measurement* rather than an argument: either a shared assignment contract exists and
  is used by two or three chassis, or it was measured and does not help. Phase 6 writes the verdict
  — two rules on two axes, R1 as literally written unmeetable, R1 in the sense `control_draw`
  already satisfies it met — and this phase must not pre-empt it.
- **Phase 6 — every insight.** `lab insight` is **append-only** and a double append is permanent.
  **This phase journals nothing.** The findings go in `phase-5-results.md` and phase 6 journals
  them, one command at a time, exit code read directly, never piped.
- **Phase 6 — the final `lab stage`.** This phase stages after each of its runs so the tree is
  never left with an unstaged database; phase 6 runs the last one.
- **Phase 6 — leftovers 1 and 2 of `HANDOVER_20261019-the-honest-control`.** Leftover 1 (`M0225-
  C50-PLC` was never drawn) closes here under branch G and stays open with a measured reason under
  branch S. Leftover 2 (the weight vector) closes under **both** branches — with a rule, or with a
  number. Phase 6 records which.
- **Phase 2 — `control_draw.py`.** Untouched here. `control_weight` imports exactly one name from
  it, `keep_key`, which is on the frozen-v1 list and which phase 2 does not edit.
- **Phase 3 — M0208.** Untouched here. M0208 is an equal-slot chassis: its turnover follows its
  trade ratio arithmetically and the weight axis has nothing to say about it.
- **Nobody — M0047** (Decision D6, §1), and **M0202, M0215, M0227, M0243**, whose honest arms are
  already band-clean. Not drawn here and not left for anyone.
- **Found and deliberately not done — `control_draw.RULE_ID` is not stamped on this chassis.** The
  module docstring says `RULE_ID` is *"stamped into a matched-draw arm's `params.as_dict()`"*, and
  `CapTopParams.as_dict` does not stamp it; neither does `SizedYieldBetaParams`. Adding
  `control_weight.RULE_ID` (or `control_draw`'s) to a shared `as_dict` would make **every recorded
  M0221 and M0225 arm** report a field it never had. It is reporting-only and outside
  `config_digest`, so nothing is wrong today — but the docstring and the code disagree, and that is
  a cleanup for a later set, not a drive-by here.
- **Found and deliberately not done — `real_frac_at` is computed twice per M0201 decision** under
  §6. Threading it through would mean editing `matched_frac`, which is amendment 1's recorded code.
  Left as a cost, named in the allocator docstring.

---

## 9. Rollback

**Branch S:** nothing to roll back. No engine file, no lab row, no commit to `engine/`.

**Branch G, before a `lab run --amend`:** `git revert` that method's pre-registration commit, or
`git checkout -- <the method file>` if it is not yet committed. Nothing is recorded, so this costs
no method id, no trial, no N and no look. **This is exactly why §3a's probe is paid for before
§3c's commit, and why the commit precedes the run.**

**Branch G, after a `lab run --amend`:** **a recorded trial cannot be rolled back.** `trials` is
append-only by trigger and `method_amendments` carries append-only triggers on update *and*
delete, so the `Amendment` block must stay in the method file forever — removing it would break
`store.latest_source_sha` and `pending_amendment` for that method. The repair for a bad arm is a
**further amendment**, never a revert. The correct rollback of a *finding* is a journalled note
saying the arm ran and what it showed, which phase 6 writes either way.

**`control_weight.py` after a run:** frozen in behaviour, not in file. Every recorded trial's
`config_digest` names `<M0221-A2>` / `<M0225-A2>` and the reused params value, and the digest does
**not** cover this module's code — so an edit here would silently change what a recorded arm means
while every test stayed green. `rung_order` and `assigned` are closed records from the moment the
first trial lands. **A different assignment is a new function beside them and a new `RULE_ID`,
never an edit to these** — the same rule `control_draw`'s own docstring states for `matched_names`.

**Partial state** (M0221 ran, M0225 did not): legal and self-consistent, and it is the state the
previous set ended in. Leave M0221's amendment recorded, write `phase-5-results.md` with the one
arm that was measured and the reason the other was not, and hand M0225 forward as an open row.

**A `lab stage` that goes wrong:** re-run `lab stage` and commit again with no pathspec. The
snapshot is a regenerated export, not a hand-edited file. Do **not** `git checkout` `lab.sqlite`
— other sessions in this set may have written to it, and a rebase replays a stale database over
the live one.
