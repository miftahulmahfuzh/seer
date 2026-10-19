# Phase 2: The method file, its dedicated tests, and the pre-registration commit

**Plan set:** `GATE_READING_CADENCE_PLAN.md`
**Analysis:** `docs/analyzer/20261019-152028-SSYJ_code_analyzer.md`
**Satisfies:** R1 (sweep the gate's reading cadence as a dose-response ladder under M0260), R3 (a
host whose event hold is counted in sessions), R4 (check `sim.rules.PRESETS` before calling an arm
promotable), R6 (separate the cadence from the re-pick frequency, or state the confound), R7 (no
test-window look)
**Depends on:** Phase 1
**Difficulty:** HARD
**Package:** `engine/src/seer_engine/lab/methods`, `engine/tests`

---

## Goal

After this phase the worktree holds a committed, pre-registered lab method `M0260` that reads
M0072-Z2-RAWRANK's own 200-day SPY gate at a *k*-month anchor instead of at the data date, with a
dedicated test module proving the five claims the generic `allocatorkit` kit cannot reach: that the
native rung is the host book target for target, that the anchor grid is the one the plan's Appendix
C defines, that `k = 1` on a monthly book is the data date itself, that the weekly decomposition
arm literally reuses the monthly arm's own gate reading, and that every rung actually moves the
gate. Nothing is run against the lab: phase 3 owns `lab run`.

---

## THREE DECISIONS THIS PHASE MAKES, AND WHY (read before the steps)

These are deviations from the brief, each forced by something measured in the code. The reconciler
needs all three.

### D-A. **Six candidates, not seven. `lab.method.MAX_VARIANTS = 6`.**

`engine/src/seer_engine/lab/method.py:40` sets `MAX_VARIANTS = 6`, and
`Method.__post_init__` (`method.py:170-171`) raises on anything outside `1..6`:

```
if not isinstance(self.candidates, tuple) or not 1 <= len(self.candidates) <= MAX_VARIANTS:
    raise ValueError(f"{self.id}: 1..{MAX_VARIANTS} candidates, got {len(self.candidates)}")
```

Appendix A's seven arms therefore cannot be declared in one `Method.candidates` tuple. `lab run`
executes `method.candidates` only (`runner.py:705`); the seventh would need an `Amendment` block, a
second pre-registration commit and a separate `lab run --amend` — scope nobody asked for, and an
amendment written in the same commit as the originals is a workaround of design §2's deliberate
"one idea with 1-6 fixed variants per run" cap rather than a use of it.

**The arm dropped is `M0260-M-G2`.** The surviving ladder — `None` (= k 1), 3, 6, 12 — is the
calendar-natural one (monthly, quarterly, half-yearly, yearly), it is the set of speeds a person
would actually choose between, and it spans the full weekly→yearly range the request names. Both
reproduction anchors (`M-NATIVE`, `W-NATIVE`) and the decomposition arm (`W-G1`) are kept, because
they are the three ends of the identity the method exists to measure. If the run comes back humped
near `k = 1`, `k = 2` is the obvious amendment and costs no method id.

### D-B. **`lookback` IS widened, to 454. The brief's "NOTHING added" is not implementable, and
M0258's reason does not transfer. Both halves measured.**

The brief says `lookback` must be `ZJUMP.lookback(p.book)` = 253 and nothing more, quoting M0258's
reason. Measured on 2026-10-19, in this worktree, against the real code:

1. **At 253 the ladder fails the allocator contract.** `test_lab_methods.test_allocator_contract`
   calls `allocatorkit.assert_p4_identity` with `check_lookback=True`
   (`allocatorkit.py:118, 143-145`), which re-runs `targets` on histories cut to
   `lookback(params)` bars and demands the identical result. A `k`-month anchor sits up to `k`
   months behind the data date, and reading a 200-bar average *at* that anchor needs
   `200 + gap` bars. Run against the smoke fixture with lookback 253:

   ```
   P4 + no-lookahead per rung (lookback 253):
     k= None: OK nonempty=16
     k=    1: OK nonempty=16
     k=    2: OK nonempty=12
     k=    3: FAIL lookback too short: M0260X on 2015-03-26, held=[], ...
     k=    6: FAIL lookback too short: M0260X on 2015-03-26, held=[], ...
     k=   12: FAIL lookback too short: M0260X on 2015-03-26, held=[], ...
   ```

   Three of the four ladder rungs go red. This is not negotiable by rewording.

2. **The anchor gap is bounded, and measured.** Walking the dev store's whole SPY tape
   (`engine/.research/bars.csv`, 5722 bars, 1993-01-29 → 2015-10-16) and resolving Appendix C's
   anchor at every bar:

   ```
   k= 1: max anchor gap   22 sessions (1993-02-26 -> 1993-03-30)   fallback sessions   0
   k= 2: max anchor gap   43 sessions (1993-02-26 -> 1993-04-29)   fallback sessions  19
   k= 3: max anchor gap   63 sessions (1993-06-30 -> 1993-09-29)   fallback sessions  42
   k= 6: max anchor gap  127 sessions (1993-06-30 -> 1993-12-30)   fallback sessions 105
   k=12: max anchor gap  253 sessions (1995-12-29 -> 1996-12-30)   fallback sessions 233
   ```

   So the worst case is `200 + 253 = 453` bars. `MAX_ANCHOR_GAP = 254` gives one session of
   margin and the lookback becomes `max(253, 200 + 254) = 454`, the **same for every rung**, so no
   arm's scored window differs from any other's.

3. **Widening does NOT move the dev window's first scored session, because `MEMBERSHIP_START`
   binds, not SPY.** `dev.candidate_window` (`dev.py:268-309`) sets
   `ready = MEMBERSHIP_START if uses_members else date.min`, then raises it to
   `h.dates[lookback - 1]` for each symbol in `allocator.symbols(params)` ∪ `{SPY}`.
   `ZJUMP.symbols(BOOK)` is `('SPY',)` and `ZJUMP.uses_members(BOOK)` is `True`.
   `MEMBERSHIP_START = date(1996, 1, 2)` (`dev.py:75`). Measured against the store's SPY tape:

   ```
   lookback  253 -> SPY's 253th bar 1994-01-27   (membership start 1996-01-02)
   lookback  454 -> SPY's 454th bar 1994-11-14   (membership start 1996-01-02)
   lookback  739 -> SPY's 739th bar 1996-01-02   (membership start 1996-01-02)
   lookback  740 -> SPY's 740th bar 1996-01-03   <- the first value that moves the start
   ```

   Any lookback up to **739** leaves `ready` at `MEMBERSHIP_START`, so the window still opens at
   `next_session(1996-01-02) = 1996-01-03` — M0072's and M0258's recorded start, unchanged. 454 is
   comfortably inside that. **M0258's warning was correct for M0258**: its `m0101.SCAN` would have
   made the lookback `253 + 504 = 757`, and SPY's 757th bar is 1996-01-26, which *would* have moved
   the start to 1996-01-29. The rule is not "never widen"; the rule is "never cross 739", and this
   method states the ceiling it measured instead of inheriting a number it did not.

   **The rule, stated once for the whole plan set, and now a plan invariant (index invariant 11):**
   *a lab allocator on an index-member book may set any `lookback <= 739` without moving the dev
   window's first scored session; `253` is M0072's number, not a law.* `dev.candidate_window`
   (`dev.py:292-306`) checks only the candidate's FIXED symbols — `ZJUMP.symbols(BOOK) == ("SPY",)`
   — and index members are handled by the separate `MEMBERSHIP_START = 1996-01-02` floor, so SPY's
   `lookback`-th bar is the only thing that can raise `ready`, and it does not until bar 740.

   **The check that proves it, and it is an exit criterion of this phase, not a comment:** the
   first scored session of every M0260 arm must read **1996-01-03** — identical to M0072 at
   lookback 253 and to M0258 at lookback 253. Phase 3 reads it back off `trials.start`; the
   implementer can read it earlier and cheaper off the step-3 probe's `row.start`. If it is not
   1996-01-03, the paired comparison with M0258's recorded rows is broken and **nothing in this
   method may be quoted as a reproduction**.

   **The original brief said `lookback` must be `ZJUMP.lookback(p.book)` with nothing added.** That
   instruction was written from M0258's reasoning and is wrong for this method: it was measured
   against the real code and three of the four ladder rungs go red under it (point 1 above). The
   measured fact outranks the instruction; the instruction is struck.

4. **The ceiling from the other side is the smoke fixture, and 454 clears it.**
   `labkit.SMOKE_FIRST = 2013-12-02` gives 473 sessions, so `candidate_window` on the smoke market
   refuses any lookback above 473. At 454 every rung still runs:

   ```
   smoke run_candidate per rung (lookback 454):
     k= None monthly-hold-frac-gotrade    window 2015-09-22..2015-10-16 snapshots 20 end 2015-10-16
     k=    3 monthly-hold-frac-gotrade    window 2015-09-22..2015-10-16 snapshots 20 end 2015-10-16
     k=   12 monthly-hold-frac-gotrade    window 2015-09-22..2015-10-16 snapshots 20 end 2015-10-16
     k= None weekly-hold-frac-gotrade     window 2015-09-22..2015-10-16 snapshots 20 end 2015-10-16
     k=    1 weekly-hold-frac-gotrade     window 2015-09-22..2015-10-16 snapshots 20 end 2015-10-16
   ```

   and `assert_p4_identity` + `assert_no_lookahead` pass for every rung at 454.

### D-B2. **Every one of the six `rationale` strings carries the literal phrase `dose-response`.**

Added by the reconciler, and it is not a stylistic choice. `lab/control_shape.py:191-200` holds
`DOSE_MARKERS`, and `control_shape.kind_of(arm)` classifies an arm **by searching its lowercased
`rationale` for one of those literal phrases** — `"dose-response"` is the one that matches in this
lab today. An arm that carries it is `KIND_DOSE` and is listed `not-checked`: *"a dose-response arm
is supposed to differ in shape -- the different date or mix is the dose -- so its shape is the
measurement and not a match to be checked"* (`_not_checked_reason`). An arm that carries nothing is
`KIND_NONE` and D17 does not see it as part of a ladder at all.

The four monthly rungs already said "dose-response ladder" in their prose. The two weekly arms did
not, so D17 would have read a six-arm dose-response ladder as a four-arm one with two unclassified
strangers beside it. The fix is two words of English inside sentences that already existed, not a
keyword bolted on: `W-NATIVE` is now *"the fast end of the same dose-response ladder"* and `W-G1`
*"the decomposition arm of the dose-response ladder"*. Both read as what they are.

**Check it mechanically before the commit** — phase 3's step 1 prints a `dose=` column per arm and
every row must read `True`. **The method file is frozen the moment phase 3 records a trial**, so a
missing marker is unfixable afterwards and nine dev-eligible methods already sit D17-blocked for
exactly this class of mistake.

Nothing else in the six strings trips another marker family: no `"placebo"`, no `"hash-drawn"`, no
`"hash order"` (`DRAW_MARKERS`), no `"within-frame control"` (`ABLATION_MARKERS`), no `"the idea:"`
or `"the yardstick:"` (`IDEA_MARKERS`). `kind_of` tests dose first in any case.

### D-C. **`family = "market-trend-switch"`.**

`lab/runner.py:756-762` overwrites an `idea` row's name, family, source_kind and hypothesis from the
method file, so the file is authoritative. The analysis establishes that **both** candidate families
are kin-clean on (D12): the only `test-failed` methods in the lab are M0002
(`stock-momentum-risk-managed`), M0021 and M0029 (`stock-multi-factor-blend`) and M0022
(`stock-residual-momentum`); `market-trend-switch` holds M0084, M0113, M0136, M0245 (all
`rejected`) and M0234, M0255, M0259, M0260 (ideas), with no test-failed member; and M0260's
ancestry M0258 → M0072 → M0063 is entirely `stock-event-drift` and also test-failed-free. **So the
choice is editorial, not a gate decision.** `market-trend-switch` is chosen because it matches the
queued `idea` row M0258's run already created, and because the method is about the market-trend
switch itself — the host book is the measuring instrument, not the subject.

---

## Interface Contract

**Creates:**
- module `seer_engine.lab.methods.m0260_gate_reading_cadence`
  (`engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py`)
- `m0260_gate_reading_cadence.ADDED` = `date(2026, 10, 19)`
- `m0260_gate_reading_cadence.MAX_GATE_MONTHS` = `12`
- `m0260_gate_reading_cadence.MAX_ANCHOR_GAP` = `254`
- `m0260_gate_reading_cadence.LADDER` = `(None, 3, 6, 12)`
- `m0260_gate_reading_cadence.G1`, `.G3`, `.G6`, `.G12` = `1, 3, 6, 12`
- `m0260_gate_reading_cadence.month_index(d: date) -> int`
- `m0260_gate_reading_cadence.gate_anchor(h: History | None, data_date: date, k: int) -> date`
- `m0260_gate_reading_cadence.CadenceParams` (frozen, slots: `book: ZParams`,
  `gate_months: int | None = None`)
- `m0260_gate_reading_cadence.SlowGateAllocator` with `id = "M0260"`
- `m0260_gate_reading_cadence.SLOWGATE` (the allocator instance)
- `m0260_gate_reading_cadence.BOOK` (`ZParams(JUMP20, z_min=Decimal("2"), rank="raw")`)
- `m0260_gate_reading_cadence.METHOD` (`Method`, id `M0260`, parent `M0258`,
  family `market-trend-switch`, **six** candidates)
- test module `engine/tests/test_lab_m0260_cadence.py`

**Candidate ids (six, in declaration order):**
`M0260-M-NATIVE`, `M0260-M-G3`, `M0260-M-G6`, `M0260-M-G12`, `M0260-W-NATIVE`, `M0260-W-G1`

**Also creates (and this phase owns it):** the **pre-registration commit** carrying exactly those
two files. CLAUDE.md: *"The method file must be committed before `lab run MNNNN`. That commit is
the pre-registration."* Phase 3 **verifies** that commit and runs against it; phase 3 does not make
it, does not amend it and does not rebase over it. See Step 3.

**Deletes:** none.
**Renames:** none.
**Signature changes:** none.

**Requires (from earlier phases):**
- Phase 1's `docs/backtests/2026-10-19-gate-reading-cadence.md` exists and carries the SPY-alone
  prior grid and the anchor probe. The method file's docstring **quotes that grid by value**; the
  values written into the file below were measured independently in this worktree on the same dev
  store (`engine/.research/bars.csv`) with the same arithmetic as
  `docs/backtests/2026-10-19-gate-band-cadence.py`. **The implementer must diff the table in the
  docstring against phase 1's committed `.md` before committing and, on any disagreement, take
  phase 1's numbers** — phase 1 owns that measurement and this file only quotes it. The method file
  must not import from the study script.

**Leaves alone (owned by others):**
- `engine/src/seer_engine/lab/methods/m0258_gate_price_band.py` (frozen, Phase 3's parent record)
- `engine/src/seer_engine/lab/methods/m0072_standardised_earnings_jump.py` (frozen host; import only)
- `engine/src/seer_engine/lab/methods/m0063_earnings_day_jump.py` (frozen; import only)
- `engine/src/seer_engine/sim/rules.py` (no new `Cadence` member, no new preset)
- `engine/tests/test_lab_m0258_band.py`, `engine/src/seer_engine/commands/cli.py`
- `lab/lab.sqlite`, `web/data/lab.json` (Phase 3)
- `docs/backtests/2026-10-19-gate-reading-cadence.{py,md}` (Phase 1)

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py` | create | the whole method: `CadenceParams`, `gate_anchor`, `SlowGateAllocator` (id `M0260`), six candidates, `METHOD` |
| `engine/tests/test_lab_m0260_cadence.py` | create | the nine claims the generic kit cannot check |

Both files are new; there is no line reference to land on. Method discovery is automatic
(`lab/method.py:discover()` globs `mNNNN_*.py`), and test discovery is pytest's, so no existing
file is edited anywhere in this phase.

---

## Pre-verification (already run; do not take it on trust, but do not expect surprises)

Both code blocks below were extracted verbatim from this plan file and executed out of tree on
2026-10-19 against `/home/miftah/seer/engine/src` and `/home/miftah/seer/engine/tests`, with the
method module registered under its real dotted name so the test module imported the real text:

```
docstring lines: 318   (as first drafted; the reconciler's D-B2 and C6 edits add a few)
METHOD ok: M0260 market-trend-switch 6
ids: ['M0260-M-NATIVE', 'M0260-M-G3', 'M0260-M-G6', 'M0260-M-G12', 'M0260-W-NATIVE', 'M0260-W-G1']
distinct digests: 6
as_dict gate_months: 3 | native: native
lookback: 454 454          (identical at the native rung and at k = 12)
symbols/holds/members: ('SPY',) ('SPY',) True
purity violations: []      (the same AST check test_lab_methods runs)

test_lab_m0260_cadence.py: 9 passed in 1.20s

  M0260-M-NATIVE     contract OK nonempty= 16  smoke 2015-09-22..2015-10-16 snapshots 20
  M0260-M-G3         contract OK nonempty= 12  smoke 2015-09-22..2015-10-16 snapshots 20
  M0260-M-G6         contract OK nonempty= 12  smoke 2015-09-22..2015-10-16 snapshots 20
  M0260-M-G12        contract OK nonempty= 20  smoke 2015-09-22..2015-10-16 snapshots 20
  M0260-W-NATIVE     contract OK nonempty= 16  smoke 2015-09-22..2015-10-16 snapshots 20
  M0260-W-G1         contract OK nonempty= 16  smoke 2015-09-22..2015-10-16 snapshots 20
owner_inputs match: ()

ruff check --select E9,F --ignore F401 <both files>  ->  All checks passed!
```

The docstring is a little over 318 lines rather than the 150-250 the brief suggested. Every block in it is one
the brief requires — the money-weighted M0258 figures, the unfunded prior grid, the confound in
full, the decomposition with its reason, the promotability table, the M0072-not-M0197 argument, the
lookback measurement, the pre-registered prediction, the walk-forward caution, the no-test-look
rule and the standing dead list — so length was spent rather than substance cut. Trim it only by
deleting something, never by abbreviating it into vagueness; this is the artifact a human reads in
a year.

---

## Implementation Steps

### Step 1: Write the method file

**File:** `engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py` (new)
**Change:** the complete method, below, written verbatim.
**Impact:** adds one `Allocator` id (`M0260`) and six candidates to `discover()`, which means
`test_lab_methods` grows six `test_candidate_runs_a_smoke_window` cases and six
`test_allocator_contract` cases. It records nothing.

**Code:**

```python
"""M0260 -- How often should a book read its safety gate?

Source: variation of M0258-M-B0, whose book -- M0072-Z2-RAWRANK's, carried whole -- and whose bare
200-day SPY gate are both kept unchanged; Faber (2007), "A Quantitative Approach to Tactical Asset
Allocation", JWM 9(4), for the long-moving-average switch itself and for the observation that the
rule is evaluated at a fixed interval rather than continuously. The switch is nineteen years old
and nothing in it is a new anomaly, so no fade argument applies to the rule. What is new is the
question: not whether to use the gate, but HOW OFTEN TO LOOK AT IT.

WHY THIS METHOD EXISTS, AND WHAT IT COSTS TO NOT ASK. M0258 ran on 2026-10-19 to settle whether a
price band around the SPY-200 gate is worth anything on a book that holds stocks. The answer was
no. But it carried, as the paired zero rung of its band ladder, two arms that differed in one thing
only -- the rule set's cadence -- and those two arms measured the largest single effect in the
method and one nobody was looking for.

Every figure in this file is the MONEY-WEIGHTED return on the owner's own monthly deposits -- what
`lab show` prints as "your money earned" -- because these books are funded with a monthly top-up
and the curve-shape columns beside them, as `backtest/metrics.py` says outright, "are not returns
at all". SPY's figure is the SAME deposits put into SPY over the same window. No total return and
no CAGR appears anywhere below as a return.

    * M0258-M-B0, trial 829: the book behind its own bare gate, re-picked MONTHLY. Your money
      earned 12.33% a year; worst fall 23.80%; gains 1.98x losses on 1208 trades.
    * M0258-W-B0, trial 833: the SAME book, the SAME bare gate, re-picked WEEKLY. Your money
      earned 5.32% a year; worst fall 35.49%; gains 1.28x losses on 1923 trades.
    * The same deposits put into SPY over that window earned 7.19% a year.

So the monthly reading beat the weekly reading by +7.01 points a year and 11.69 points of worst
fall, on one book with nothing else moving. For scale: the price band M0258 was bought to measure
is worth -0.40 points a year at the monthly cadence; the lab's whole measured gate premium after
2009 is a constant 3.6 points a year (the 824-trial sweep of 2026-10-19). The cadence is worth
roughly twice the gate itself, and the weekly arm lost to its own deposits in SPY by nearly two
points while falling thirty-five.

And NOBODY EVER CHOSE IT. There is no cadence lever on a gate anywhere in this lab. A book reads
its gate at its rank session because that is the only moment the allocator is called, so every book
in the lab inherits its gate's reading interval from however often it happens to re-pick stocks.
That is a free decision the lab has been making by accident for its entire history. This method
costs one id to find out where the axis turns, because a gate read yearly is barely a gate at all
and gating is worth 3.6 points a year after 2009, so a best speed must exist between weekly and
yearly.

THE PRIOR GRID. Measured on the dev store before any of this prose was written, by
`docs/backtests/2026-10-19-gate-reading-cadence.py`, in the same spirit as M0258's band grid and
M0245's episode ledger: SPY ALONE, 200-bar warmup held flat, one-session lag, the gate's reading
held as read at each rank session. **This is a FEASIBILITY TABLE AND A PRIOR, NOT A RESULT, AND IT
IS UNFUNDED** -- it is a weight path on raw closes with no deposits, no fees and no stock picking,
so its percentages are plain CAGRs and are NOT comparable with the money-weighted figures above.
"k" is the anchor's phase in months (see THE ANCHOR below); "native" is the gate read at the data
date, which is what every lab book does today.

    gate read at        whole CAGR   worst fall   2009-2015   invested   flips
    monthly, native         9.08%      -19.0%        10.07%     71.9%       22
    monthly, k = 1          9.08%      -19.0%        10.07%     71.9%       22
    monthly, k = 2          8.56%      -19.7%         7.86%     72.7%       20
    monthly, k = 3          6.71%      -24.5%         6.31%     70.0%       20
    monthly, k = 6          8.39%      -25.9%         7.88%     72.5%       11
    monthly, k = 12         7.06%      -19.4%         7.25%     67.9%        9
    weekly,  native         5.51%      -34.6%         5.82%     70.8%       80
    weekly,  k = 1          8.49%      -19.0%         8.98%     71.9%       22

The grid is trusted for the same reason M0258's was: it independently reproduces trials the lab has
already recorded through the full simulator, sharing no code with it. Its monthly bare gate falls
19.0% against M0084-MONTHLY's recorded 18.89%, and its weekly bare gate falls 34.6% against
M0084-WEEKLY's recorded 33.13%.

Two things in that table are the whole design. First, **the monthly native row and the monthly
k = 1 row are identical to the digit**, which is an identity and not a coincidence: see THE K = 1
IDENTITY below. Second, **weekly k = 1 recovers almost all of the gap between weekly and monthly**
-- 8.49% against the weekly native's 5.51% and the monthly native's 9.08% -- which is the
decomposition this method is built to measure, visible on SPY alone before any stock is picked.

THE CONFOUND, IN FULL AND IN PLAIN WORDS. This is the hard part of the design and it is written
down here rather than worked around.

**The two axes are the same event as the chassis stands.** `backtest/book_runner.run_book` calls
the allocator only on decision sessions, with `data_date = prev_session(session)`, and the gate is
read inside that call at `data_date`. So "how often the gate is read" is DEFINED BY the rule set's
`cadence`, which is also what sets how often the book re-picks stocks. M0258's +7.01 points a year
is the sum of those two effects and names neither.

**Slower than the re-pick is separable, and promotable.** Nothing stops an allocator evaluating the
gate at a date EARLIER than its data date. Anchoring the reading to a month-end grid leaves
`TradeRules` untouched, so every slow arm here still runs on `monthly-hold-frac-gotrade`, which IS
a member of `sim.rules.PRESETS` and so can reach paper.

**Faster than the re-pick is NOT separable, by construction, and that is a property of the
simulator rather than a gap in this design.** A monthly book cannot act on a gate reading taken
between its rank sessions; a reading it never acts on changes no target and no trade. Making the
book act weekly IS changing the rule set's cadence, which also re-picks weekly. The sub-monthly
rung of this ladder is inseparably confounded on this chassis, and no arrangement of allocator
params can unconfound it.

**So the confound is DECOMPOSED rather than papered over.** Three of the six arms are an exact
split of the +7.01. With A = M-NATIVE (monthly re-pick, monthly gate), B = W-NATIVE (weekly
re-pick, weekly gate) and C = W-G1 (weekly re-pick, MONTHLY gate):

    (A - B)   =   (A - C)                  +   (C - B)
     +7.01         re-pick frequency            gate reading cadence
     measured      (the gate held monthly)      (the re-pick held weekly)

and the first bracket is clean for a reason worth stating exactly. At a weekly rank session in
month M, arm C's anchor is the newest month end on or before its data date, which is THE SAME
MONTH-END SESSION arm A read at its own rank session that month. Arm C does not approximate arm A's
gate reading; it literally reuses it, bar for bar. So `A - C` moves re-pick frequency and nothing
else, and `C - B` moves the gate's reading cadence and nothing else. `test_lab_m0260_cadence.py`
asserts that session by session on the smoke tape rather than asserting it in prose.

On the unfunded SPY-alone prior above the split is `A - B` = +3.57, of which `A - C` = +0.59 is
re-pick frequency and `C - B` = +2.98 is the gate's reading cadence -- 84% of the gap is the gate.
SPY alone has no stock picking, so the re-pick term there is near zero by construction and the real
book's will be larger; the prediction below commits to how much larger.

THE ANCHOR. With `month_index(d) = (d.year - 1970) * 12 + (d.month - 1)`:

    anchor(h, data_date, k) = the newest bar a of h with a <= data_date such that
                                (i)  a is the last session of its calendar month, and
                                (ii) month_index(a) % k == k - 1
                              falling back to data_date when no such bar is on hand

Phase `k - 1` makes the grid calendar-natural: k = 1 is every month end, k = 2 is
Feb/Apr/.../Dec, k = 3 is Mar/Jun/Sep/Dec (the calendar quarters), k = 6 is Jun/Dec, k = 12 is
December only. Condition (i) is decidable point-in-time: for a bar older than the data date it is
`month(dates[j]) != month(dates[j+1])`, which reads only bars at or before the data date; for the
bar dated the data date itself it is the calendar question
`dates.next_session(d).month != d.month`, which reads the published NYSE calendar and no price at
all. A calendar read inside a lab allocator is established practice --
`m0052_turn_of_month_tilt.py` does exactly this, as do `m0120_calendar_clock.py` and seven others
-- and `allocatorkit.assert_no_lookahead` perturbs BARS, not the calendar, which is why both of its
futures agree here.

**The anchor is never later than the data date**, so every anchored arm is strictly SAFER on
look-ahead than the native reading the lab already runs.

**The fallback never fires inside the dev window.** Measured on the dev store's whole SPY tape
(5722 bars, 1993-01-29 to 2015-10-16): the k = 12 anchor is unresolvable on the first 233 sessions
only -- every one of them before 1993-12-31, the tape's first December month end -- and on none
after; k = 6 on the first 105, k = 3 on the first 42, k = 2 on the first 19, k = 1 on none. The dev
window's first scored session is 1996-01-03, more than two years later, so no arm of this method
ever reads the fallback. On the 473-session smoke fixture it does fire, for the k = 12 and k = 6
rungs, on the sessions before the fixture's first December month end, and the test module asserts
its exact shape there rather than pretending it cannot happen.

THE K = 1 IDENTITY, AND THE TRIAL IT SAVES. `sim.rules._first_of("monthly", s)` is true on the
first NYSE session of a calendar month, so a monthly book's `data_date = prev_session(s)` is ALWAYS
the last NYSE session of the previous month. The k = 1 anchor on a monthly book therefore resolves
to the data date itself, and the anchored k = 1 arm IS the native arm. That is why the ladder's
fastest rung is `M-NATIVE` with `gate_months = None` and not a seventh trial: the identity is
asserted in `test_lab_m0260_cadence.py` on every decision session of the smoke tape instead of
being bought with a row. The prior grid's first two lines are the same claim, measured.

THE SIX ARMS. All six hold M0072-Z2-RAWRANK's book verbatim -- M0063's standardised earnings-day
jump kept only when the jump is at least two of the stock's own daily swings and ranked by the raw
jump, F4's five-dollar and twenty-million-dollar screen, 20 slots at 5%, SPY in the empty ones, a
60-session hold, fractional shares at Gotrade's real fees on the owner's monthly top-ups. ONLY the
rule set's cadence and the gate's reading interval move.

    arm        rule set                  gate_months   what it is                    promotable
    M-NATIVE   monthly-hold-frac-gotrade   None        the ladder's fastest rung;    yes
                                                       must reproduce M0258-M-B0
    M-G3       monthly-hold-frac-gotrade      3        quarterly                     yes
    M-G6       monthly-hold-frac-gotrade      6        half-yearly                   yes
    M-G12      monthly-hold-frac-gotrade     12        yearly: barely a gate at all  yes
    W-NATIVE   weekly-hold-frac-gotrade    None        must reproduce M0258-W-B0     NEVER
    W-G1       weekly-hold-frac-gotrade       1        the decomposition arm:        NEVER
                                                       weekly re-pick, monthly gate

THE PROMOTABILITY TABLE IS A FACT ABOUT `sim.rules`, NOT AN OPINION. `lab promote` requires a rule
set that is a member of `sim.rules.PRESETS`. `MONTHLY_HOLD_FRAC_GOTRADE` is a member, so all four
monthly arms -- the whole slow ladder -- can reach paper if one of them wins.
`WEEKLY_HOLD_FRAC_GOTRADE` is NOT a member: it is M0063's one-off rule set, declared in
`m0063_earnings_day_jump.py` under its own comment, "No preset of this id exists yet: it runs on
dev, and `promote` would need one (a feature-wish if it wins)". **So both weekly arms are
diagnostic forever, whatever they show, and minting a preset mid-run would be scope nobody asked
for.** They are here to measure the decomposition, not to be adopted.

And the slow rungs are params rather than a cadence for a reason that is also a fact about the
code: `sim.rules.Cadence` is `Literal["daily", "weekly", "monthly"]`. **There is no "quarterly" and
no "yearly" rule set, and there cannot be one without moving `_CADENCE_ORDER`, `_first_of`,
`is_rank_session`, every `TradeRules` canonical text and the web mirror in `cadence.ts`.** The slow
rungs live in the allocator's params precisely so that they need none of that -- which is exactly
what keeps them promotable, because the rule set they run on is still the preset.

WHY M0072 AND NOT M0197. The cadence axis is only clean on a book whose event hold is counted in
SESSIONS. M0072's is: `live_event` keeps the newest event with `i - hold < t <= i - 1` for
`hold = 60` sessions, so the same event is live for the same 60 sessions whether the book looks at
it four times or sixty. M0197's chooser keys its re-pick on `data_date.month`, so changing the
cadence changes which events the book can even see, and the axis would measure two things at once.
M0072 is also one of only three books the lab reads as promotable and kin-clean, and its parent
M0063 already ran the identical book both weekly and monthly, so the weekly arms are a cadence the
book's own family has run before.

WHY A NEW ALLOCATOR ID AND NOT A WIDER PARAMETER. `f_factor.FactorParams.trend` is
`tuple[str, int] | None` and `registry._canon` renders it inside every candidate that carries it.
Giving it a third element for the reading interval would move every recorded config digest in the
lab. The interval therefore lives in a new dataclass behind a new allocator id. That costs one
method id, and that is the correct price.

HOW THE OVERLAY WORKS, AND THE ONE THING IT REPLACES. `SlowGateAllocator` delegates `symbols`,
`holds`, `uses_members` and `prepare` to `ZJUMP` and runs M0072's own target builder on M0072's own
prepared panel. Exactly one thing differs: the DATE at which the gate is read.

    * `gate_months is None`: `f_factor.trend_on(history, data_date, inner)`, unchanged. Not
      `trend_on` at an anchor computed to equal the data date -- although on a monthly book the two
      are provably the same thing and the test module asserts it session by session, the native
      rungs' job is to REPRODUCE recorded trials, and a reproduction runs the host's own code.
    * `gate_months = k`: `f_factor.trend_on(history, gate_anchor(h, data_date, k), inner)` -- the
      SAME function, the same symbol and the same 200-bar average, read at an earlier date. The
      gate's logic is not re-implemented anywhere in this file; only the date it is asked about
      moves.

`ZJUMP._targets` is called directly because M0072 exposes no seam between its gate test and its
target builder, and the obvious alternative is wrong in a way that matters to the record: handing
`ZJUMP` a gate-free twin of its params (`trend=None`) runs, but `config_text` digests
`CadenceParams`, which holds the book UNMODIFIED, so the recorded row would say `trend=SPY:200`
while the allocator ran something else. Calling the builder with the host's own params keeps the
book provably identical and replaces exactly the gate. The private call is safe because `m0072.py`
is frozen against its recorded source sha, and M0258 established the precedent on this same host.

THE LOOKBACK, AND WHY IT IS 454 AND NOT M0072'S 253. This is the one place this method departs from
M0258's shape, and the departure is measured rather than argued.

Reading a 200-bar average AT an anchor up to k months old needs `200 + gap` bars on hand. The gap
was measured on the dev store's whole SPY tape: 22 sessions at k = 1, 43 at k = 2, 63 at k = 3, 127
at k = 6 and **253 at k = 12** (1995-12-29 to 1996-12-30, the worst case in twenty-three years). So
453 bars is the true requirement and `MAX_ANCHOR_GAP = 254` carries one session of margin:
`lookback = max(ZJUMP.lookback(book), 200 + 254) = 454`, THE SAME FOR EVERY RUNG, so no arm's
scored window differs from another's. At M0072's 253 the three slow rungs fail
`allocatorkit.assert_p4_identity`'s lookback cut outright, which was measured before this number
was chosen.

M0258's file says its lookback must not be widened, "because it would move the dev window's first
scored session off M0072's 1996-01-03 and turn the band = 0 arm from a reproduction into an
approximation". That reason is correct for M0258 and does not transfer here, and the difference is
arithmetic. `dev.candidate_window` takes `ready = MEMBERSHIP_START` (1996-01-02, because this book
reads index members) and raises it to SPY's `lookback`-th bar date. SPY's 454th bar is 1994-11-14
and SPY's **739th** is 1996-01-02, so any lookback up to 739 leaves the window opening at
`next_session(1996-01-02) = 1996-01-03` -- M0072's and M0258's own first scored session, unchanged.
SPY's 740th bar is 1996-01-03, which is where the start would begin to move. M0258's proposed
addition was `m0101.SCAN = 504`, giving 757, and SPY's 757th bar is 1996-01-26: that genuinely
would have moved the start, which is why its file was right to refuse it. **The rule is not "never
widen"; it is "never cross 739", and this method measured the ceiling instead of inheriting a
number.** 454 is also under the 473-session smoke fixture's hard cap, and every arm still runs a
smoke window to DEV_END.

THE PRE-REGISTERED PREDICTION, WRITTEN DOWN BEFORE THE RUN, WITH SIGNS AND SIZES.

    1. THE LADDER DOES NOT HUMP. No rung above k = 1 beats M-NATIVE on money-weighted return. The
       turn is AT k = 1 -- which is to say the lab has been running the best available cadence by
       accident, and the honest headline is "monthly is already right", not "slower is better".
       Concretely: M-NATIVE highest of the four monthly arms; M-G3, M-G6 and M-G12 each at least a
       point a year below it; the ladder flat-to-falling rather than rising then turning, and not
       necessarily monotone in the middle (the unfunded prior is a sawtooth, 9.08 / 6.71 / 8.39 /
       7.06, and a sawtooth on a funded stock book would not surprise me). Stated as a SHAPE rather
       than as a rung: THE AXIS TURNS AT MONTHLY AND FALLS AWAY ON BOTH SIDES. M0258 already
       measured the fast side -- weekly cost -7.01 points a year and 11.69 points of worst fall --
       and this ladder predicts the slow side falls too. That is a sharper claim than "a best speed
       exists somewhere between weekly and yearly", and it is falsified outright by a single slow
       rung beating M-NATIVE on money.
    2. THE FALL DEEPENS BEFORE IT SHALLOWS. M-G3 and M-G6 fall DEEPER than M-NATIVE's 23.80%,
       because a quarterly or half-yearly reading is late to both of the window's exits; M-G12
       falls no shallower than M-NATIVE, because a December-only reading is close to no gate at all
       and its fall is the market's. I expect at least one slow rung past 28%.
    3. THE DECOMPOSITION SPLITS TOWARD THE GATE. Both brackets are positive and the gate-reading
       term is the larger: `C - B` at least half of the +7.01, and my point estimate is 4 to 6
       points a year, leaving `A - C` at 1 to 3. On worst fall I expect the same ordering, with
       `C - B` carrying the majority of the 11.69 points.
    4. W-G1 BEATS W-NATIVE ON BOTH AXES, BY A LOT -- at least 3 points a year and at least 6 points
       of worst fall. If it does not, the anchor is not doing what this file says it does, and the
       reproduction checks below are what would catch that.
    5. THE REPRODUCTIONS ARE EXACT. M-NATIVE returns M0258-M-B0's recorded row to the digit --
       12.3314% a year, a 23.8026% worst fall, 1208 trades -- and W-NATIVE returns M0258-W-B0's.
       They run under new config digests because the allocator id and the params class differ, but
       nothing else about them differs, and if either drifts then every paired difference this
       method reports is void and the run must be read as a null.

SUCCESS IS A MEASUREMENT, NOT ELIGIBILITY. This method is bought to name a lever the lab has been
setting by accident since its first trial. Prediction 1 coming true is the most useful outcome for
the owner even though it changes nothing he does: it converts an accident into a decision, and it
retires "read the gate less often" as a direction. Prediction 1 failing -- a slow rung beating
monthly on a stock book -- would be worth far more than one id, because every monthly book in the
lab would then be leaving points on the table for free, through a change that needs no new rule set
and no new preset.

THE WALK-FORWARD MUST BE READ ARM BY ARM. `lab walkforward` picks each fold's variant by MAR, and
MAR favours whichever arm trades least. The slow rungs flip the gate less (the unfunded prior:
22 flips at k = 1 against 9 at k = 12) and a book that stays invested trades less at the margins,
so the folds are structurally biased toward M-G12. **M0245's folds picked its slowest rung in three
of four, and the lab has written that down.** A fold majority won by M-G12 is therefore evidence
about turnover FIRST and about the cadence second, and the folds must be read arm by arm rather
than by their headline. M0258's folds are the counter-example that keeps this honest: they chose
its no-band arm twice of four, so the bias is real but not fatal.

NO TEST-WINDOW LOOK IS SPENT HERE, UNDER ANY OUTCOME. Four are spent and all four failed. `lab
test` is not invoked by this method under any result, including a slow rung that clears every
condition; the follow-up to that would be its own decision with its own owner conversation.

WHAT IS ALREADY DEAD AROUND THIS GATE, AND WHY A CADENCE SWEEP IS NONE OF IT. The handover of
2026-10-19 lists every modification of this gate the lab has measured and buried, and none of them
is re-tested here. Turning the gate OFF: helped 22 of 22 variants whole-window, 0 of 22 after 2009,
and every gate-off arm was worse on return AND drawdown at once. A TIME LOCK on the switch: costs
return and deepens the fall from 20% to 32%, because the flips it suppressed included the
2008-05-21 exit, and the standing rule after it reads "stop hunting hysteresis here". An
account-reading DRAWDOWN BRAKE: pays 10 points a year of 2009-2015 to save 40 of 2008. M0132's
LEARNED fall-sizing brake: beaten by the plain gate on both axes. VIX-LEVEL CONFIRMATION of the
exit: worse on both axes at 20, 25 and 30, and VIX3M only begins 2006-07-17 so it cannot be checked
against the dot-com at all. EXIT-BUFFER-ONLY, CONFIRM-N-DAYS, PARTIAL EXPOSURE and FAST RE-ENTRY on
the 50-day: all in the committed grid, all worse. And now the PRICE BAND, measured three times and
buried by M0258.

A cadence sweep is none of those, and the distinction is structural rather than rhetorical. Every
dead modification above changes WHAT THE GATE SAYS -- it adds a second condition, a memory, a
threshold or a confirmation, and the lab's record is that each one costs more in 2009-2015 than it
saves in 2008. **This method changes nothing about what the gate says. The rule is Faber's,
untouched: SPY above its 200-day average or below it. Only the DATE the book asks is moved, and
moved strictly backwards, which cannot add information and cannot look ahead.** It is the one dial
on this gate that has never been turned, and the only one every book in the lab already carries at
a value nobody picked.

Pure: no clock, no randomness, no network, no file, no printing. Reads only bars dated on or before
`data_date`, plus the published NYSE calendar. `held` is read only where M0072 reads it -- to let a
name keep its slot -- and the anchor lives in the calendar and the price path, never in the book,
so a deposit cannot move it.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from seer_engine import dates
from seer_engine.backtest.dev import Candidate
from seer_engine.lab.method import Method
from seer_engine.lab.methods.m0063_earnings_day_jump import WEEKLY_HOLD_FRAC_GOTRADE
from seer_engine.lab.methods.m0072_standardised_earnings_jump import (
    JUMP20,
    ZJUMP,
    ZParams,
    ZPrepared,
)
from seer_engine.sim.book import Target
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE
from seer_engine.strategies.base import History
from seer_engine.strategies.f_factor import factor_rows, trend_on

ADDED = date(2026, 10, 19)

#: The slowest reading this method will accept. Twelve months is "December only", which the brief
#: calls "barely a gate at all"; anything slower is a different question than the one asked.
MAX_GATE_MONTHS = 12

#: The furthest behind the data date a ``MAX_GATE_MONTHS`` anchor can sit, in sessions. Measured on
#: the dev store's whole SPY tape (5722 bars, 1993-01-29 to 2015-10-16): the worst case is 253
#: sessions, 1995-12-29 to 1996-12-30. 254 carries one session of margin. See THE LOOKBACK above
#: for why widening the lookback by this much is safe here and was not safe in M0258.
MAX_ANCHOR_GAP = 254

#: The gate's reading interval, in months, at each rung of the ladder. ``None`` is the native
#: reading -- the gate read at the data date, which is what every book in the lab does today -- and
#: on a monthly book it is also the k = 1 rung, by the identity the test module asserts.
G1 = 1
G3 = 3
G6 = 6
G12 = 12
LADDER: tuple[int | None, ...] = (None, G3, G6, G12)


def month_index(d: date) -> int:
    """Calendar months since January 1970: the grid condition (ii) counts on this."""
    return (d.year - 1970) * 12 + (d.month - 1)


def gate_anchor(h: History | None, data_date: date, k: int) -> date:
    """The newest bar of ``h`` on or before ``data_date`` that opens a ``k``-month gate reading.

    The newest bar ``a <= data_date`` that is the last session of its calendar month AND whose
    ``month_index(a) % k == k - 1``; ``data_date`` itself when no such bar is on hand. Phase
    ``k - 1`` makes the grid calendar-natural (k = 3 is Mar/Jun/Sep/Dec, k = 12 is December).

    **Never later than ``data_date``**, which makes every anchored reading strictly safer on
    look-ahead than the native one the lab already runs.

    **Point-in-time.** "Last session of its calendar month" is answered two ways, and which one
    applies depends only on the bar's position relative to the data date, never on how much history
    the caller happens to hold -- which is why the prepared path (full history) and the single
    window path (``h.upto(data_date)``) agree bar for bar, and why the kit's lookback cut agrees
    too. For a bar older than the data date it is ``month(dates[j]) != month(dates[j + 1])``, and
    ``dates[j + 1]`` is itself on or before the data date. For the bar dated the data date it is
    the calendar question ``dates.next_session(d).month != d.month``, which reads the published
    NYSE calendar and no price at all -- established practice in a lab allocator
    (``m0052_turn_of_month_tilt.py``), and untouched by ``allocatorkit.assert_no_lookahead``, which
    perturbs bars.
    """
    if h is None:
        return data_date
    i = h.index_of(data_date)
    if i is None:
        return data_date
    for j in range(i, -1, -1):
        a = h.dates[j].item()
        if month_index(a) % k != k - 1:
            continue
        nxt = h.dates[j + 1].item() if j < i else dates.next_session(a)
        if (nxt.year, nxt.month) != (a.year, a.month):
            return a
    return data_date


@dataclass(frozen=True, slots=True)
class CadenceParams:
    """``book`` is M0072's book, carried whole; ``gate_months`` is how often its gate is READ.

    ``gate_months = None`` is the native reading -- the gate read at the data date, exactly as
    every book in the lab reads it -- and is legal here because the ladder needs a fastest rung
    that runs through the same allocator id as its slower ones. ``k`` months anchors the reading to
    the newest qualifying month end on or before the data date (``gate_anchor``).
    """

    book: ZParams
    gate_months: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.book, ZParams):
            raise TypeError(f"book must be ZParams, got {type(self.book).__name__}")
        if self.book.jump.inner.trend is None:
            raise ValueError("book must carry a trend symbol and length for the anchor to read")
        if self.gate_months is None:
            return
        if isinstance(self.gate_months, bool) or not isinstance(self.gate_months, int):
            raise ValueError(f"gate_months must be an int or None, got {self.gate_months!r}")
        if not 1 <= self.gate_months <= MAX_GATE_MONTHS:
            raise ValueError(
                f"gate_months must lie in [1, {MAX_GATE_MONTHS}], got {self.gate_months}"
            )

    def as_dict(self) -> dict[str, str]:
        """Every field as a plain string, the book's prefixed ``book.`` -- M0258's shape exactly.

        ``None`` renders "native" rather than "None" because this is the text a human reads on the
        method's page beside "3" and "12", and "the gate read natively" is what the arm is. The
        digest does not depend on this choice -- ``registry._canon`` walks the dataclass's fields
        and renders ``None`` and ``3`` apart on its own -- but the recorded row does, and a row
        that says "None" would read as a missing value rather than as a rung.
        """
        out = {"gate_months": "native" if self.gate_months is None else str(self.gate_months)}
        for k, v in self.book.as_dict().items():
            out[f"book.{k}"] = v
        return out


def _check(params: object) -> CadenceParams:
    if not isinstance(params, CadenceParams):
        raise TypeError(f"params must be CadenceParams, got {type(params).__name__}")
    return params


class SlowGateAllocator:
    """M0072's standardised-jump book, with its own 200-day gate read at a k-month anchor."""

    id = "M0260"

    def lookback(self, params: Any) -> int:
        """454 bars: the host's 253, raised to cover a twelve-month anchor plus its 200-bar average.

        THE SAME VALUE AT EVERY RUNG, so no arm's scored window differs from another's -- which is
        what keeps every paired difference this method reports a difference in the gate alone. The
        worst anchor gap was measured at 253 sessions on the dev store's SPY tape and
        ``MAX_ANCHOR_GAP`` carries one more. Widening to 454 does NOT move the dev window's first
        scored session, because ``dev.candidate_window`` binds on ``MEMBERSHIP_START`` (1996-01-02)
        for any lookback up to 739 -- SPY's 739th bar is 1996-01-02 and its 740th is 1996-01-03 --
        and 454 is far inside that. The module docstring carries the measurement and the contrast
        with M0258, whose proposed widening would have reached 757 and moved the start.
        """
        p = _check(params)
        return max(ZJUMP.lookback(p.book), p.book.jump.inner.trend[1] + MAX_ANCHOR_GAP)

    def symbols(self, params: Any) -> tuple[str, ...]:
        return ZJUMP.symbols(_check(params).book)

    def holds(self, params: Any) -> tuple[str, ...]:
        return ZJUMP.holds(_check(params).book)

    def uses_members(self, params: Any) -> bool:
        return ZJUMP.uses_members(_check(params).book)

    def _on(self, history: Mapping[str, History], data_date: date, p: CadenceParams) -> bool:
        """The single thing this allocator exists to replace: the DATE the gate is read at.

        The gate itself is ``f_factor.trend_on`` in both branches -- the lab's own function, the
        same symbol, the same 200-bar average. Nothing about what the gate SAYS is re-implemented
        here. At ``gate_months = None`` the date is the data date, which is the host's own code
        path verbatim; the native rungs' job is to reproduce recorded trials, and a reproduction
        runs the host's code rather than an anchor computed to equal it.
        """
        inner = p.book.jump.inner
        if p.gate_months is None:
            return trend_on(history, data_date, inner)
        at = gate_anchor(history.get(inner.trend[0]), data_date, p.gate_months)
        return trend_on(history, at, inner)

    def targets(self, history: Mapping[str, History], members: AbstractSet[str], data_date: date,
                held: frozenset[str], params: Any) -> tuple[Target, ...]:
        """The history-only path, kept target-for-target identical to M0072's at the native rung.

        ``ZJUMP._targets`` is reached directly because M0072 exposes no seam between its gate test
        and its target builder, and the obvious alternative is wrong: handing ``ZJUMP`` a gate-free
        twin of its params (``trend=None``) runs, but it would make the recorded row a lie --
        ``config_text`` digests ``CadenceParams``, which holds the book UNMODIFIED, so the row
        would say ``trend=SPY:200`` while the allocator ran something else. Calling the builder
        with the host's own params keeps the book provably identical and replaces exactly the gate.
        The private call is safe because ``m0072.py`` is frozen against its recorded source sha,
        and M0258 established the precedent on this same host.
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


SLOWGATE = SlowGateAllocator()

#: M0072-Z2-RAWRANK's configuration, verbatim: the Z2 filter ranked by the raw jump.
BOOK = ZParams(JUMP20, z_min=Decimal("2"), rank="raw")


def _v(suffix: str, gate_months: int | None, rules: Any, rationale: str) -> Candidate:
    return Candidate(id=f"M0260-{suffix}", family="M0260", rules=rules, allocator=SLOWGATE,
                     params=CadenceParams(BOOK, gate_months), rationale=rationale, added=ADDED,
                     owner_inputs=())


METHOD = Method(
    id="M0260",
    name="How often should a book read its safety gate? A dose-response ladder in the SPY-200 "
         "gate's reading interval, from weekly to yearly, on a book that holds stocks",
    family="market-trend-switch",
    source_kind="variation",
    source_ref=(
        "variation of M0258-M-B0 (its book and its bare gate unchanged; M0258-M-B0 is itself "
        "M0072-Z2-RAWRANK); Faber (2007), A Quantitative Approach to Tactical Asset Allocation, "
        "JWM 9(4), for the long-moving-average switch and for evaluating it at a fixed interval "
        "rather than continuously"
    ),
    parent_id="M0258",
    hypothesis=(
        "Published 2007 (the long-moving-average switch), so nothing in the rule is a new anomaly "
        "and no fade argument applies to it; what is new is the question, which is not whether to "
        "use the gate but HOW OFTEN TO LOOK AT IT. Every figure here is the MONEY-WEIGHTED return "
        "on the owner's own monthly deposits -- what the lab prints as 'your money earned' -- "
        "because these books are funded with a monthly top-up and the curve-shape columns beside "
        "them are not returns at all; SPY's figure is the SAME deposits put into SPY. M0258 ran on "
        "2026-10-19 to settle whether a price band helps this gate, and the answer was no, but it "
        "carried two arms that differed in one thing only -- the rule set's cadence -- and those "
        "two measured the largest single effect in the method. M0258-M-B0, the book behind its own "
        "bare gate re-picked MONTHLY, earned 12.33% a year of the owner's money and fell 23.80%, "
        "on 1208 trades with gains 1.98 times losses. M0258-W-B0, the SAME book and the SAME bare "
        "gate re-picked WEEKLY, earned 5.32% a year and fell 35.49% on 1923 trades. The same "
        "deposits in SPY earned 7.19%. So reading the gate monthly rather than weekly was worth "
        "+7.01 points a year and 11.69 points of worst fall with nothing else moving -- against "
        "-0.40 points for the price band at the monthly cadence and a constant 3.6 points a year "
        "for the whole gate premium after 2009, measured across all 824 trials. The cadence is "
        "worth roughly twice the gate itself. AND NOBODY EVER CHOSE IT: there is no cadence lever "
        "on a gate anywhere in this lab, because the allocator is only called on decision sessions, "
        "so every book inherits its gate's reading interval from however often it happens to "
        "re-pick stocks. The prior grid measured for this file on the dev store (SPY ALONE, 200-bar "
        "warmup, one-session lag, the reading held as read at each rank session; UNFUNDED, so "
        "plain CAGRs that are NOT comparable with the money-weighted figures above) reads: monthly "
        "native 9.08% a year and a 19.0% fall; monthly anchored at k = 1 the identical 9.08% and "
        "19.0%; k = 2 8.56% and 19.7%; k = 3 6.71% and 24.5%; k = 6 8.39% and 25.9%; k = 12 7.06% "
        "and 19.4%; weekly native 5.51% and 34.6%; weekly anchored at k = 1 8.49% and 19.0%. It "
        "reproduces the lab's own recorded SPY-only trials -- its monthly fall of 19.0% against "
        "M0084-MONTHLY's recorded 18.89%, its weekly 34.6% against M0084-WEEKLY's 33.13% -- and "
        "shares no code with the simulator. THE CONFOUND, STATED RATHER THAN PAPERED OVER. The two "
        "axes are the same event as the chassis stands: run_book calls the allocator only on "
        "decision sessions, with data_date = prev_session(session), and the gate is read inside "
        "that call, so the rule set's cadence sets BOTH how often the gate is read and how often "
        "the book re-picks, and M0258's +7.01 is the sum of the two and names neither. Slower than "
        "the re-pick IS separable and promotable: nothing stops an allocator reading the gate at an "
        "earlier date, and anchoring it to a month-end grid leaves TradeRules untouched, so every "
        "slow arm still runs on monthly-hold-frac-gotrade, which IS in sim.rules.PRESETS. Faster "
        "than the re-pick is NOT separable, by construction: a monthly book cannot act on a reading "
        "taken between its rank sessions, and a reading it never acts on changes no target and no "
        "trade, so making it act weekly IS a rule-set change which also re-picks weekly. That is a "
        "property of the simulator rather than a gap in this design, and no arrangement of params "
        "can undo it. So the confound is DECOMPOSED. With A = M-NATIVE (monthly re-pick, monthly "
        "gate), B = W-NATIVE (weekly re-pick, weekly gate) and C = W-G1 (weekly re-pick, MONTHLY "
        "gate): (A - B) = (A - C) + (C - B), where the first bracket is re-pick frequency with the "
        "gate held monthly and the second is the gate's reading cadence with the re-pick held "
        "weekly. The first bracket is clean because at a weekly rank session in month M, arm C's "
        "anchor is the newest month end on or before its data date -- THE SAME MONTH-END SESSION "
        "arm A read at its own rank session that month. Arm C does not approximate arm A's reading; "
        "it reuses it, and the dedicated test module asserts that session by session rather than "
        "asserting it in prose. On the unfunded SPY-alone prior the split is +3.57 total, of which "
        "+0.59 is re-pick frequency and +2.98 is the gate's reading cadence -- 84% of the gap is "
        "the gate, on an instrument with no stock picking at all. THE ANCHOR, with month_index(d) = "
        "(d.year - 1970) * 12 + (d.month - 1): the newest bar a <= data_date that is the last "
        "session of its calendar month and has month_index(a) % k == k - 1, falling back to "
        "data_date when none is on hand. Phase k - 1 makes the grid calendar-natural: k = 3 is the "
        "calendar quarters, k = 12 is December only. It is never later than data_date, so every "
        "anchored arm is strictly SAFER on look-ahead than the native reading the lab already runs, "
        "and the fallback never fires inside the dev window -- measured on the store's whole SPY "
        "tape, k = 12 is unresolvable only on the first 233 sessions, all of them before "
        "1993-12-31, and the dev window opens on 1996-01-03. SIX ARMS hold M0072-Z2-RAWRANK's book "
        "verbatim -- the standardised earnings-day jump kept at two of the stock's own daily swings "
        "and ranked by the raw jump, F4's five-dollar and twenty-million screen, 20 slots at 5%, "
        "SPY in the empty ones, a 60-session hold, fractional at Gotrade's real fees on the owner's "
        "monthly top-ups -- and move only the cadence and the reading interval: M-NATIVE (monthly, "
        "native: the ladder's fastest rung, which must reproduce M0258-M-B0), M-G3 (quarterly), "
        "M-G6 (half-yearly), M-G12 (yearly, barely a gate at all), W-NATIVE (weekly, native: must "
        "reproduce M0258-W-B0) and W-G1 (weekly re-pick with a MONTHLY gate: the decomposition "
        "arm). The anchored k = 1 rung on a monthly book is NOT an arm and costs no trial: a "
        "monthly book's data_date is always a calendar month end, so it resolves to data_date "
        "itself and is identical to M-NATIVE, which the test module asserts on every decision "
        "session and the prior grid's first two lines show measured. PROMOTABILITY IS A FACT ABOUT "
        "sim.rules, NOT AN OPINION: lab promote requires membership of sim.rules.PRESETS, "
        "MONTHLY_HOLD_FRAC_GOTRADE is a member so all four monthly arms can reach paper, and "
        "WEEKLY_HOLD_FRAC_GOTRADE is NOT a member -- it is M0063's one-off rule set, declared under "
        "its own comment saying no preset of its id exists -- so BOTH WEEKLY ARMS ARE DIAGNOSTIC "
        "FOREVER whatever they show, and minting a preset mid-run would be scope nobody asked for. "
        "And the slow rungs live in the allocator's params rather than in a cadence because "
        "sim.rules.Cadence is Literal['daily', 'weekly', 'monthly']: there is no quarterly and no "
        "yearly rule set, and there cannot be one without moving _CADENCE_ORDER, _first_of, "
        "is_rank_session, every TradeRules canonical text and the web mirror -- which is exactly "
        "what keeps the slow rungs promotable, since the rule set they run on is still the preset. "
        "M0072 IS THE HOST because the cadence axis is only clean on a book whose event hold is "
        "counted in SESSIONS: M0072 keeps the newest event with i - hold < t <= i - 1 for 60 "
        "sessions, so the same event is live for the same 60 sessions whether the book looks four "
        "times or sixty, while M0197's chooser keys its re-pick on data_date.month and would "
        "measure two things at once. THE PRE-REGISTERED PREDICTION, written before the run: (1) THE "
        "LADDER DOES NOT HUMP -- no rung above k = 1 beats M-NATIVE on money, the turn is AT k = 1, "
        "and M-G3, M-G6 and M-G12 each come in at least a point a year below M-NATIVE, flat-to- "
        "falling rather than rising then turning and not necessarily monotone in the middle; as a "
        "SHAPE, THE AXIS TURNS AT MONTHLY AND FALLS AWAY ON BOTH SIDES, since M0258 already "
        "measured the fast side at -7.01 points a year and 11.69 points of worst fall, which is a "
        "sharper and more falsifiable claim than 'a best speed exists somewhere between weekly and "
        "yearly' -- one slow rung beating M-NATIVE on money falsifies it outright; (2) "
        "THE FALL DEEPENS BEFORE IT SHALLOWS -- M-G3 and M-G6 fall deeper than M-NATIVE's 23.80% "
        "because a quarterly or half-yearly reading is late to both of the window's exits, with at "
        "least one slow rung past 28%, while M-G12 falls no shallower than M-NATIVE because a "
        "December-only reading is close to no gate at all; (3) THE DECOMPOSITION SPLITS TOWARD THE "
        "GATE -- both brackets positive and (C - B) at least half of the +7.01, point estimate 4 to "
        "6 points a year, leaving (A - C) at 1 to 3, with the same ordering on worst fall; (4) W-G1 "
        "BEATS W-NATIVE ON BOTH AXES by at least 3 points a year and at least 6 points of worst "
        "fall; (5) THE REPRODUCTIONS ARE EXACT -- M-NATIVE returns M0258-M-B0's recorded row to the "
        "digit, 12.3314% a year and a 23.8026% worst fall on 1208 trades, and W-NATIVE returns "
        "M0258-W-B0's, and if either drifts then every paired difference here is void and the run "
        "is a null. SUCCESS IS A MEASUREMENT, NOT ELIGIBILITY. Prediction 1 coming true is the most "
        "useful outcome even though it changes nothing the owner does: it converts an accident into "
        "a decision and retires 'read the gate less often' as a direction. Prediction 1 failing "
        "would be worth far more than one id, because every monthly book in the lab would then be "
        "leaving points on the table through a change that needs no new rule set and no new preset. "
        "Assumed without asking: that the right host is M0072-Z2-RAWRANK, because it is the book "
        "M0258 already measured the +7.01 on, so this method's two native arms are reproductions "
        "rather than new baselines."
    ),
    expected_failure=(
        "First and most likely: the ladder is simply FLAT-TO-FALLING and the headline is 'monthly "
        "is already right'. M-G3, M-G6 and M-G12 all come in under M-NATIVE, no rung turns, and the "
        "method has bought the knowledge that a lever nobody chose happens to sit near its best "
        "value. That is a null in the sense that nothing changes, and it is still worth the id, "
        "because the lab is currently carrying a recorded analysis whose closing paragraph asks "
        "this exact question and a journalled insight that reports gate-flip counts without saying "
        "how often the gate was being checked -- and nothing short of a pre-registered ladder "
        "closes either. Second, THE WALK-FORWARD WILL FLATTER THE SLOWEST RUNG. lab walkforward "
        "picks each fold's variant by MAR, and MAR favours whichever arm trades least; the slow "
        "rungs flip the gate less -- 22 flips at k = 1 against 9 at k = 12 on the unfunded prior -- "
        "so the folds are structurally biased toward M-G12. M0245's folds picked its slowest rung "
        "in three of four and the lab has written that down. A fold majority won by M-G12 is "
        "therefore evidence about turnover FIRST and about the cadence second, and the folds must "
        "be read arm by arm rather than by their headline; M0258's folds, which chose its no-band "
        "arm twice of four, are the counter-example that keeps this honest. Third, THE WEEKLY ARMS "
        "CAN NEVER BE PROMOTED. They run on weekly-hold-frac-gotrade, which is not in "
        "sim.rules.PRESETS, so whatever the decomposition shows lives in a measurement the lab "
        "cannot act on; only the four monthly arms could ever reach paper, and the decomposition's "
        "value is explanatory rather than operational. Fourth, A SLOW RUNG THAT WINS MAY BE WINNING "
        "ON FEES RATHER THAN ON TIMING. A gate that flips less trades less, and on a 20-name book "
        "every flip is around forty orders at Gotrade's real schedule; the fee term was the "
        "second-largest container in the 824-trial shortfall sweep. The ladder is the only defence "
        "against that reading -- a fee story improves monotonically as the reading slows and "
        "trading falls, while a timing story peaks and turns -- so the trade counts and turnover of "
        "the four monthly arms must be reported beside their returns and not after them. Note what "
        "the unfunded prior already says about this: the share of time invested barely moves across "
        "the ladder, 71.9% at k = 1 against 67.9% at k = 12, so the slow rungs are not simply "
        "sitting in the market more. Fifth, THE DEV WINDOW HOLDS EXACTLY TWO CRASHES AND BOTH WERE "
        "SLOW. A reading interval's whole effect is WHEN it notices, and a quarterly reading that "
        "looks fine against two slow falls could be catastrophic against a fast one; 1987 and 2020 "
        "are what fast looks like and neither is in this window. Nothing measured on dev can settle "
        "that, the folds are the only within-window check, and no test-window look is spent here "
        "under any outcome -- four are spent and all four failed. Sixth, THE 2009-2015 ERA IS WHERE "
        "A SLOW GATE SHOULD LOOK BEST AND IT IS THE ERA THAT MATTERS LEAST FOR SAFETY. A nearly "
        "always-on gate wins a window with no crash in it, so M-G12 flattering itself on the second "
        "half while falling hard in 2008 would be the expected shape of a bad answer, not a good "
        "one, and the two eras must be read together. Seventh, the host book's own recorded worst "
        "fall is 23.80%, already at the real-money bar, so no arm of this method is expected to "
        "clear every go-live condition and the cadence is not being asked to fix that. Eighth, the "
        "k = 1 identity is load-bearing and asserted on a 473-session synthetic fixture rather than "
        "on the dev tape: if sim.rules._first_of ever stopped making a monthly book's data_date a "
        "calendar month end, M-NATIVE would silently stop being the ladder's k = 1 rung and the "
        "ladder would have a hole at its fastest end. The test module asserts the identity on every "
        "decision session it can see, which is the strongest check available without spending a "
        "trial on a rung that is provably a duplicate. Finally, as in every switch method the lab "
        "has run: interest on the cash held while the gate is off is not modelled, which flatters "
        "SPY and penalises every gated arm equally -- and it penalises the FAST readings most, "
        "since they sit out most often, so each gap this method reports between a fast and a slow "
        "reading is a LOWER bound on how well the fast reading really did. The paired differences "
        "within one cadence are unaffected."
    ),
    candidates=(
        _v("M-NATIVE", None, MONTHLY_HOLD_FRAC_GOTRADE,
           "The dose-response ladder's fastest rung and the paired reproduction: "
           "M0072-Z2-RAWRANK's own book behind its own unchanged 200-day switch, read at the data "
           "date as every book in the lab reads it, which on a monthly book is the k = 1 rung"),
        _v("M-G3", G3, MONTHLY_HOLD_FRAC_GOTRADE,
           "Second rung of the dose-response ladder: the same switch read once a calendar quarter "
           "-- Mar, Jun, Sep, Dec -- while the book goes on re-picking monthly"),
        _v("M-G6", G6, MONTHLY_HOLD_FRAC_GOTRADE,
           "Third rung of the dose-response ladder: the same switch read half-yearly, at the June "
           "and December month ends, while the book goes on re-picking monthly"),
        _v("M-G12", G12, MONTHLY_HOLD_FRAC_GOTRADE,
           "Top rung of the dose-response ladder: the same switch read once a year, at the "
           "December month end -- barely a gate at all, and the end the ladder has to reach"),
        _v("W-NATIVE", None, WEEKLY_HOLD_FRAC_GOTRADE,
           "The fast end of the same dose-response ladder: the same book and the same bare "
           "200-day switch re-picked WEEKLY, so the switch is read weekly too -- and the arm that "
           "must reproduce M0258-W-B0"),
        _v("W-G1", G1, WEEKLY_HOLD_FRAC_GOTRADE,
           "The decomposition arm of the dose-response ladder: the book re-picks WEEKLY but reads "
           "the switch at the month end, reusing the monthly arm's own reading, so the measured "
           "weekly-monthly gap splits exactly into re-pick frequency and gate reading cadence"),
    ),
    seen_keys=(
        "concept:gate-reading-cadence-ladder",
        "concept:anchored-gate-reading",
        "concept:repick-frequency-versus-signal-cadence",
    ),
)
```

### Step 2: Write the dedicated test module

**File:** `engine/tests/test_lab_m0260_cadence.py` (new)
**Change:** the complete module, below, written verbatim.
**Impact:** nine new tests. It imports `labkit` and `allocatorkit` from `engine/tests/`, which is
on `sys.path` for pytest through the existing `conftest.py` arrangement that
`test_lab_m0258_band.py` already relies on.

**Code:**

```python
"""M0260's anchored gate: the claims the generic kit cannot check.

``test_lab_methods`` already drives every lab allocator through ``allocatorkit`` -- valid targets,
the P4 identity, no look-ahead -- and runs every candidate on a smoke window. These are the
properties specific to reading somebody else's gate at a date earlier than the data date:

1. **The native rung IS the host book**, target for target, on both the history-only and the
   prepared path. That is what earns the right to call M-NATIVE a reproduction of M0258-M-B0 (and
   so of M0072-Z2-RAWRANK) rather than an approximation, and it is why the decomposition's A end is
   a recorded row the lab can be held to.
2. **The overlay declares the host's shape** -- symbols, holds and membership unchanged, and a
   lookback that is the SAME at every rung. Equal lookbacks are what keep every arm scored over the
   same sessions; an arm with its own lookback would be a different window wearing a rung's name.
3. **The anchor grid is the one the method file defines**: never later than the data date, and
   always a calendar month end whose ``month_index % k == k - 1`` unless the documented fallback
   fired.
4. **On a monthly book the k = 1 anchor IS the data date.** This identity is why the ladder's
   fastest rung is the native arm and costs no trial. If it ever broke, the ladder would have a
   silent hole at its fast end.
5. **The decomposition identity.** On a weekly rule set, the k = 1 anchor is the same month-end
   session a monthly rule set read in that month. This is what makes ``A - C`` pure re-pick
   frequency instead of an approximation of it.
6. **The params round-trip and every arm digests apart.** ``config_text`` reads the rules, the
   allocator id and the params only, so a dropped field would make two arms share one digest and
   the second would be refused as already run.
7. **Every rung is actually wired in.** Each k must move the gate's reading somewhere on the tape,
   or an arm that looks like a rung is running the native gate under another name.
8. **The fallback never fires silently.** The smoke fixture's 473 sessions are about two years, so
   a twelve-month anchor genuinely cannot resolve at the start of it. Its exact shape is asserted
   here; that it never fires inside the DEV window is phase 1's measurement on the real store
   (k = 12 unresolvable on the first 233 sessions, all before 1993-12-31, against a window that
   opens on 1996-01-03).

A dedicated module rather than more cases inside the shared lab tests: the smoke fixture's 473
sessions are a fixed budget every lab method is measured against, and a new method must fit it
rather than stretch it.
"""

from __future__ import annotations

from datetime import date

import pytest
from labkit import MEMBER_STOCKS, SMOKE_FIRST, smoke_market

from seer_engine import dates
from seer_engine.backtest.dev import DEV_END, Candidate
from seer_engine.lab.method import config_digest
from seer_engine.lab.methods.m0063_earnings_day_jump import WEEKLY_HOLD_FRAC_GOTRADE
from seer_engine.lab.methods.m0072_standardised_earnings_jump import ZJUMP
from seer_engine.lab.methods.m0260_gate_reading_cadence import (
    ADDED,
    G1,
    G3,
    G6,
    G12,
    LADDER,
    MAX_ANCHOR_GAP,
    MAX_GATE_MONTHS,
    SLOWGATE,
    BOOK,
    CadenceParams,
    gate_anchor,
    month_index,
)
from seer_engine.sim.rules import MONTHLY_HOLD_FRAC_GOTRADE, is_rank_session
from seer_engine.strategies.f_factor import trend_on

BENCH = "SPY"
SMA_N = 200
MEMBERS = frozenset(MEMBER_STOCKS)
PROBES = dates.sessions(date(2014, 12, 1), DEV_END)[::40]
NATIVE = CadenceParams(BOOK)
KS = (G1, 2, G3, G6, G12)


@pytest.fixture(scope="module")
def market():
    return smoke_market((BENCH,))


def _spy_sessions(market):
    """Every smoke session SPY has a bar for, which on this fixture is all 473 of them."""
    h = market.history[BENCH]
    return [d for d in dates.sessions(SMOKE_FIRST, DEV_END) if h.index_of(d) is not None]


def _is_month_end(h, d):
    """True when the bar dated ``d`` is the last bar of its calendar month in ``h``."""
    i = h.index_of(d)
    assert i is not None, d
    if i + 1 < len(h):
        nxt = h.dates[i + 1].item()
    else:
        nxt = dates.next_session(d)
    return (nxt.year, nxt.month) != (d.year, d.month)


def _decision_data_dates(rules):
    """``prev_session(S)`` for every rank session S of ``rules`` inside the smoke window."""
    return [dates.prev_session(s) for s in dates.sessions(SMOKE_FIRST, DEV_END)
            if is_rank_session(rules, s)]


def test_the_native_rung_is_the_host_book_target_for_target(market):
    """At ``gate_months = None`` M0260 equals M0072-Z2-RAWRANK, on both paths, at every probe.

    The generic kit checks each allocator against ITSELF -- the P4 identity and look-ahead -- and
    never against another allocator, so nothing in it can tell a reproduction from a near miss.
    This is what earns M-NATIVE the right to be read as M0258-M-B0's row run again, which is the A
    end of the decomposition the whole method reports.
    """
    prepared_host = ZJUMP.prepare(market.history)
    prepared_slow = SLOWGATE.prepare(market.history)
    seen = 0
    for session in PROBES:
        d = dates.prev_session(session)
        for held in (frozenset(), frozenset(MEMBER_STOCKS[:2]) & frozenset(market.history)):
            host = ZJUMP.targets(market.history, MEMBERS, d, held, BOOK)
            slow = SLOWGATE.targets(market.history, MEMBERS, d, held, NATIVE)
            host_p = ZJUMP.targets_prepared(prepared_host, MEMBERS, d, held, BOOK)
            slow_p = SLOWGATE.targets_prepared(prepared_slow, MEMBERS, d, held, NATIVE)
            assert slow == host, (d, sorted(held))
            assert slow_p == host_p == host, (d, sorted(held))
            seen += len(host)
    assert seen > 0, "every probe was empty, so the comparison proved nothing"


def test_the_overlay_declares_the_host_books_shape(market):
    """Symbols, holds and membership are M0072's at every rung, and the lookback is one number.

    The generic kit calls ``lookback`` but never compares one params value's against another's, and
    a ladder whose rungs had different lookbacks would be scored over different windows -- every
    paired difference the method reports would then be partly a window difference. The lookback is
    deliberately NOT the host's 253: it must cover a twelve-month anchor plus its 200-bar average,
    which is measured in the method file's docstring.
    """
    want = SLOWGATE.lookback(NATIVE)
    assert want == max(ZJUMP.lookback(BOOK), SMA_N + MAX_ANCHOR_GAP)
    assert want > ZJUMP.lookback(BOOK), "a 12-month anchor needs more than the host's lookback"
    for k in (None,) + KS:
        p = CadenceParams(BOOK, k)
        assert SLOWGATE.lookback(p) == want, k
        assert SLOWGATE.symbols(p) == ZJUMP.symbols(BOOK), k
        assert SLOWGATE.holds(p) == ZJUMP.holds(BOOK), k
        assert SLOWGATE.uses_members(p) is ZJUMP.uses_members(BOOK), k


def test_the_anchor_grid_is_a_phased_month_end_grid(market):
    """Every resolved anchor is a month end on the k-grid, and never later than the data date.

    Nothing in ``allocatorkit`` knows this method has an anchor at all; it perturbs bars and checks
    targets. This walks the grid directly, on every session of the tape and every rung, because the
    grid's phase (``% k == k - 1``) is the whole reason k = 3 means calendar quarters rather than
    whichever month the tape happened to start in.
    """
    h = market.history[BENCH]
    sessions = _spy_sessions(market)
    assert len(sessions) > 400, "the smoke fixture shrank; this check needs a tape to walk"
    for k in KS:
        resolved = 0
        for d in sessions:
            a = gate_anchor(h, d, k)
            assert a <= d, (k, d, a)
            if a == d and not (_is_month_end(h, d) and month_index(d) % k == k - 1):
                continue  # the documented fallback; its shape is asserted separately
            assert _is_month_end(h, a), (k, d, a)
            assert month_index(a) % k == k - 1, (k, d, a)
            resolved += 1
        assert resolved > len(sessions) // 2, f"k={k}: the anchor almost never resolved"


def test_on_a_monthly_book_the_k1_anchor_is_the_data_date(market):
    """``gate_anchor(h, data_date, 1) == data_date`` on every monthly decision session.

    This identity is why the ladder's fastest rung is the NATIVE arm and costs no trial: a monthly
    book's ``data_date`` is ``prev_session(first session of the month)``, which is always the last
    session of the previous month. Nothing in the generic kit checks a relationship between the
    allocator and the rule set it will be run under, and this one is load-bearing.
    """
    h = market.history[BENCH]
    checked = 0
    for d in _decision_data_dates(MONTHLY_HOLD_FRAC_GOTRADE):
        assert gate_anchor(h, d, G1) == d, d
        checked += 1
    assert checked >= 20, "too few monthly decision sessions on the fixture to prove the identity"


def test_the_weekly_k1_anchor_is_the_monthly_books_own_reading(market):
    """On a weekly rule set the k = 1 anchor is the month-end session a monthly book read.

    This is the whole claim behind ``(A - C)`` being pure re-pick frequency: arm C does not
    approximate arm A's gate reading, it reuses the identical session. Asserted against the set of
    data dates a MONTHLY rule set actually produces, so the two arms are compared through the
    simulator's own calendar rather than through a restatement of it.
    """
    h = market.history[BENCH]
    monthly = _decision_data_dates(MONTHLY_HOLD_FRAC_GOTRADE)
    monthly_set = set(monthly)
    checked = 0
    for d in _decision_data_dates(WEEKLY_HOLD_FRAC_GOTRADE):
        a = gate_anchor(h, d, G1)
        if a == d and d not in monthly_set:
            continue  # the fallback, before the tape's first month end
        assert a in monthly_set, (d, a)
        newest = max(m for m in monthly if m <= d)
        assert a == newest, (d, a, newest)
        checked += 1
    assert checked >= 40, "too few weekly decision sessions resolved to prove the identity"


def test_the_params_round_trip_and_every_arm_digests_apart():
    """``as_dict`` carries every field, and each of the six arms is its own configuration."""
    p = CadenceParams(BOOK, G3)
    rendered = p.as_dict()
    assert set(rendered) == {"gate_months"} | {f"book.{k}" for k in BOOK.as_dict()}
    assert rendered["gate_months"] == "3"
    assert all(isinstance(v, str) for v in rendered.values())
    for k, v in BOOK.as_dict().items():
        assert rendered[f"book.{k}"] == v
    assert CadenceParams(BOOK).as_dict()["gate_months"] == "native"
    assert CadenceParams(BOOK, G12).as_dict()["gate_months"] == "12"

    def candidate(suffix, gate_months, rules):
        return Candidate(id=f"M0260-{suffix}", family="M0260", rules=rules, allocator=SLOWGATE,
                         params=CadenceParams(BOOK, gate_months), rationale="a rung", added=ADDED,
                         owner_inputs=())

    digests = {
        config_digest(candidate("M-NATIVE", None, MONTHLY_HOLD_FRAC_GOTRADE)),
        config_digest(candidate("M-G3", G3, MONTHLY_HOLD_FRAC_GOTRADE)),
        config_digest(candidate("M-G6", G6, MONTHLY_HOLD_FRAC_GOTRADE)),
        config_digest(candidate("M-G12", G12, MONTHLY_HOLD_FRAC_GOTRADE)),
        config_digest(candidate("W-NATIVE", None, WEEKLY_HOLD_FRAC_GOTRADE)),
        config_digest(candidate("W-G1", G1, WEEKLY_HOLD_FRAC_GOTRADE)),
    }
    assert len(digests) == 6, "two arms share a configuration digest"
    assert LADDER == (None, G3, G6, G12)


def test_every_rung_actually_moves_the_gate(market):
    """Each k changes the gate's reading somewhere on the tape, or it is the native gate renamed.

    A rung whose anchor always landed on the data date would record a trial that looks like a dose
    and is the control. The gate is compared through ``trend_on`` at the anchor against ``trend_on``
    at the data date, which is exactly the one line the allocator replaces.
    """
    h = market.history[BENCH]
    inner = BOOK.jump.inner
    sessions = _spy_sessions(market)
    for k in KS:
        moved = sum(
            1 for d in sessions
            if trend_on(market.history, gate_anchor(h, d, k), inner)
            != trend_on(market.history, d, inner)
        )
        assert moved > 0, f"k={k} never differs from the native reading on the smoke tape"


def test_the_fallback_fires_only_before_the_first_qualifying_month_end(market):
    """The fallback's shape is asserted, not assumed: it fires only where no anchor can exist.

    The smoke fixture is 473 sessions, about two years, so a twelve-month grid genuinely has no
    qualifying bar at the start of it. That is a property of a two-year fixture and not of the dev
    window: on the real store the k = 12 anchor is unresolvable on the first 233 sessions only,
    every one of them before 1993-12-31, against a dev window that opens on 1996-01-03 -- phase 1's
    probe. The lookback is NOT widened further to make this go away: the smoke fixture's 473
    sessions are a fixed budget every lab method is measured against.
    """
    h = market.history[BENCH]
    sessions = _spy_sessions(market)
    for k in KS:
        qualifying = [d for d in sessions if _is_month_end(h, d) and month_index(d) % k == k - 1]
        assert qualifying, f"k={k}: the fixture holds no qualifying month end at all"
        first = qualifying[0]
        for d in sessions:
            a = gate_anchor(h, d, k)
            if d < first:
                assert a == d, f"k={k}: expected the fallback on {d}, got {a}"
            else:
                assert a <= d and a >= first, (k, d, a)
                assert _is_month_end(h, a) and month_index(a) % k == k - 1, (k, d, a)
    # k = 12 is the rung that genuinely falls back on this fixture; k = 1 never does.
    assert all(gate_anchor(h, d, G1) <= d for d in sessions)
    assert any(gate_anchor(h, d, G12) == d and not _is_month_end(h, d) for d in sessions)
    # No history at all, and a data date the symbol has no bar for, both fall back to the date.
    probe = sessions[len(sessions) // 2]
    assert gate_anchor(None, probe, G12) == probe


def test_the_params_refuse_what_they_say_they_refuse():
    """The validator is part of the pre-registration: a reading outside [1, 12] is not this method."""
    with pytest.raises(ValueError):
        CadenceParams(BOOK, 0)
    with pytest.raises(ValueError):
        CadenceParams(BOOK, MAX_GATE_MONTHS + 1)
    with pytest.raises(ValueError):
        CadenceParams(BOOK, -1)
    with pytest.raises(ValueError):
        CadenceParams(BOOK, True)  # a bool is an int in Python and is not a reading interval
    with pytest.raises(ValueError):
        CadenceParams(BOOK, 3.0)  # a float, not an int
    with pytest.raises(TypeError):
        CadenceParams(object(), G3)
    with pytest.raises(TypeError):
        SLOWGATE.lookback(BOOK)
```

### Step 3: Verify, then commit

**File:** none (verification and the pre-registration commit)
**Change:** run the commands in **Verification** below, then commit exactly the two new files.
**Impact:** **this commit IS the pre-registration, and it is made HERE, in phase 2.**
`lab/runner.preflight` requires the method file committed and clean, and the sha of this commit is
what `methods.source_sha` will record when phase 3 runs. Phase 3's step 1 asserts that this commit
exists and that `git status --porcelain` for the method file is empty; phase 3 never creates it. From the moment phase 3's `lab run M0260` records a trial the file is FROZEN — not a
typo, not a docstring word. **Phase 3 must not amend this commit** (no `git commit --amend`, no
rebase that rewrites it): a later addition is an `Amendment` block with its own commit, and a
correction before the run is a new commit, never a rewrite of this one.

**Commit message:**

```
lab: M0260 pre-registered — how often should a book read its safety gate?

M0258 measured the same book behind the same bare 200-day gate earning 12.33%/yr
of the owner's money read monthly against 5.32%/yr read weekly, falling 23.80%
against 35.49%, with nothing moving but the rule set's cadence — larger than the
price band is worth at any cadence and larger than the whole 3.6 pts/yr gate
premium. No book in this lab ever chose its gate's reading interval; each one
inherits it from however often it happens to re-pick stocks.

Six arms on M0072-Z2-RAWRANK's book, moving only the cadence and the reading
interval: M-NATIVE (reproduces M0258-M-B0), M-G3, M-G6 and M-G12 anchor the gate
to the calendar quarters, the half-years and December while the book goes on
re-picking monthly; W-NATIVE (reproduces M0258-W-B0) and W-G1 split the measured
+7.01 pts/yr exactly into re-pick frequency and gate reading cadence, because
W-G1 reuses M-NATIVE's own month-end reading rather than approximating it.

The sub-monthly rung is inseparably confounded on this chassis and the file says
so in those words. Both weekly arms run on weekly-hold-frac-gotrade, which is not
in sim.rules.PRESETS, so they are diagnostic forever; all four monthly arms stay
promotable, which is why the slow rungs live in the allocator's params and not in
a cadence sim.rules.Cadence does not have.

The lookback is 454, not M0072's 253: a twelve-month anchor sits up to 253
sessions back (measured on the store's SPY tape) and needs its 200-bar average
behind it. Widening does not move the first scored session — candidate_window
binds on MEMBERSHIP_START for any lookback up to 739 — which is why M0258's
"never widen" was right for its +504 and does not apply at +201.

No test-window look is spent, under any outcome.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

Stage by pathspec only — the swarm shares this worktree's index:

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
  git add engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py \
          engine/tests/test_lab_m0260_cadence.py && \
  git status --porcelain -- engine/ > /tmp/m0260_staged.txt 2>&1; echo $?
```

Then commit with the message above. **Never `git add -A`, never `git reset --hard`.**

---

## Verification

Run from the worktree root, `/home/miftah/.worktrees/seer/gate-reading-cadence`. Redirect every
command to a file and echo `$?`; a pipe's exit code belongs to the last stage and would hide a
failure.

**Lint:**

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
  /home/miftah/seer/engine/.venv/bin/ruff check engine > /tmp/m0260_ruff.txt 2>&1; echo $?
tail -20 /tmp/m0260_ruff.txt
```

**The two modules that matter, serial:**

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
  PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
  /home/miftah/seer/engine/.venv/bin/pytest -n0 \
    engine/tests/test_lab_m0260_cadence.py engine/tests/test_lab_methods.py \
    > /tmp/m0260_pytest.txt 2>&1; echo $?
tail -40 /tmp/m0260_pytest.txt
```

**The full suite, with Postgres up (CI fails if the DB tests skip):**

```bash
docker start seer-pg > /tmp/m0260_pg.txt 2>&1; echo $?
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
  PYTHONPATH=/home/miftah/.worktrees/seer/gate-reading-cadence/engine/src \
  PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  /home/miftah/seer/engine/.venv/bin/pytest -n0 engine/tests \
    > /tmp/m0260_full.txt 2>&1; echo $?
tail -40 /tmp/m0260_full.txt
```

`PYTHONPATH` is not optional: without it pytest silently tests `/home/miftah/seer`, not this
branch. The worktree has no venv of its own; the main checkout's interpreter is the one to use.

**Manual check:** `grep -c '' engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py`
and confirm the docstring's prior-grid table matches phase 1's committed
`docs/backtests/2026-10-19-gate-reading-cadence.md` row for row. On any disagreement take phase
1's numbers and re-commit before phase 3 runs anything — after `lab run` the file is frozen and a
wrong number is permanent.

**Nothing in this phase touches the lab.** No `lab` subcommand is invoked, `SEER_LAB_DB` is never
set, `lab/lab.sqlite` and `web/data/lab.json` must still be clean in `git status` at the end.

**Exit criteria, as checkable assertions:**

1. `ruff check engine` exits 0.
2. `pytest -n0 engine/tests/test_lab_m0260_cadence.py engine/tests/test_lab_methods.py` exits 0,
   with 9 passing tests in the new module and 6 new `M0260-*` ids in both
   `test_candidate_runs_a_smoke_window` and `test_allocator_contract`.
3. `pytest -n0 engine/tests` with `PG_TEST_URL` exits 0 and reports no skipped DB tests.
4. `python -c "from seer_engine.lab.method import discover; m,_ = discover()['M0260'];
   print(m.family, len(m.candidates), [c.id for c in m.candidates])"` prints
   `market-trend-switch 6 ['M0260-M-NATIVE', 'M0260-M-G3', 'M0260-M-G6', 'M0260-M-G12',
   'M0260-W-NATIVE', 'M0260-W-G1']`.
5. `git status --porcelain` shows exactly two added files and nothing under `lab/` or `web/data/`.
6. The method file's docstring states, in its own words: the confound and that the sub-monthly rung
   is inseparably confounded by the simulator; the three-arm decomposition and why arm C reuses arm
   A's reading; the promotability table with `WEEKLY_HOLD_FRAC_GOTRADE` absent from `PRESETS` and
   `Cadence` holding no quarterly or yearly; why M0072 and not M0197; a pre-registered prediction
   with signs and sizes; the walk-forward MAR caution; that no test-window look is spent; and the
   standing dead list with the reason a cadence sweep is none of it.
7. One commit exists containing exactly those two files, and it has not been amended. **This
   phase makes the pre-registration commit** — phase 3 verifies it and runs against it.
8. **Every one of the six `rationale` strings contains the literal lowercase substring
   `dose-response`** (decision D-B2). Check it, do not eyeball it:
   `python -c "from seer_engine.lab.method import discover; m,_ = discover()['M0260'];
   print([(c.id, 'dose-response' in c.rationale.lower()) for c in m.candidates])"` must print
   `True` for all six. A `False` here is unfixable after phase 3's run, because the file is frozen.
9. **The first scored session is `1996-01-03`** (decision D-B). Cheapest check before the commit:
   run one arm through `backtest.dev.run_registry` on the real dev store and print `row.start` —
   phase 3's step-3 probe does exactly this and prints `row.start..row.end`. Anything other than
   `1996-01-03` means the widened lookback moved the window and the two reproduction arms are no
   longer reproductions.
10. **The docstring's prior-grid table matches phase 1's committed
    `docs/backtests/2026-10-19-gate-reading-cadence.md` row for row**, and on any disagreement
    phase 1's numbers are taken and this file re-committed *before* phase 3 runs. The two
    measurements are deliberately independent implementations — phase 2 measured `+3.57 = +0.59 +
    +2.98` and phase 1 `+3.58 = +0.59 + +2.99`, agreement to rounding, which is the evidence — but
    **phase 1's `.md` is the citable record and wins any disagreement.** Every figure in that
    table is SPY alone and **UNFUNDED** and is labelled so in the same sentence (index invariant 4).

---

## Handoffs

- **The seventh arm, `M0260-M-G2` (R1).** Dropped under decision D-A because
  `lab.method.MAX_VARIANTS = 6`. If phase 3's ladder comes back humped between `M-NATIVE` and
  `M-G3`, `k = 2` is the obvious follow-up and costs no method id: an `Amendment` block committed
  on its own and run with `lab run --amend M0260`. **Phase 3 must not add it by editing
  `candidates`** — that moves the file's sha after the run and trips
  `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha`.
- **Reading the folds arm by arm (R2).** Phase 3's. The method file writes the caution down; it
  does not run `lab walkforward`.
- **Quoting `trial_funding.mwr` in the recorded analysis (R5).** Phase 3's and phase 4's. This
  phase quotes money-weighted figures only inside the pre-registration prose, and labels the
  SPY-alone prior grid UNFUNDED in the same sentence it appears in.
- **The standing correction to the two site documents that count gate flips without saying at what
  cadence they were counted (R4/R5).** M0258's analysis asks for it; it belongs to phase 4's
  handover and the memory write, not here.
- **A `weekly-hold-frac-gotrade` preset.** Explicitly out of scope by the plan index. The method
  file states that the weekly arms can never be promoted instead of working around it.
- **A `"quarterly"` member of `sim.rules.Cadence`.** Out of scope, and the method file explains
  that the slow rungs live in params *because* of that — which is what keeps them promotable.
- **The lookback ceiling of 739 is a fact about the dev store's SPY tape and `MEMBERSHIP_START`,
  not a constant anywhere in the code.** Worth a memory note in phase 4: "a lab allocator on an
  index-member book may widen its lookback up to 739 bars without moving the dev window's first
  scored session, because `candidate_window` binds on `MEMBERSHIP_START` (1996-01-02) until SPY's
  740th bar (1996-01-03); the real ceiling is the 473-session smoke fixture."

---

## Rollback

Both files are new and nothing else is touched, so this phase undoes cleanly on its own:

```bash
cd /home/miftah/.worktrees/seer/gate-reading-cadence && \
  git revert --no-edit <this phase's commit> > /tmp/m0260_revert.txt 2>&1; echo $?
```

or, before the commit exists:

```bash
rm -f /home/miftah/.worktrees/seer/gate-reading-cadence/engine/src/seer_engine/lab/methods/m0260_gate_reading_cadence.py \
      /home/miftah/.worktrees/seer/gate-reading-cadence/engine/tests/test_lab_m0260_cadence.py
```

Nothing has been recorded in `lab.sqlite`, so there is nothing append-only to undo. **This stops
being true the moment phase 3 runs**: once a trial exists the method file is frozen and the only
rollback is the lab's own (leave the trials, record a correcting `lab note` and `lab insight`), so
every correction to this file has to happen before phase 3 starts.
