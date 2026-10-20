# Phase 5 results — The weight rule, and the arms it earns

**Branch key: `G-bottom` (phase 4's rule D). GO, for M0221 and M0225 only.**

**Date:** 2026-10-20
**Plan set:** `docs/plans/CONTROL_DRAW_REMEDIES_PLAN.md`, phase 5 of 6 (`P1-ROOT-M4HV`)
**Status:** COMPLETE. Two arms drawn, both band-clean, both landed and pushed. The key above was
written before an editor was opened (§0 of the phase plan).
**Environment:** `main`, research store `640fc25e…` (`engine/.research`), `engine/.venv`
(Python 3.11). Main checkout, no worktree, nothing else running.

## The key, and the numbers behind it

Phase 4 swept six arms of M0221 in one `dev.run_registry` call on store `640fc25e…`, re-run
against re-run (invariant I8), and measured:

| arm | rule | trades | turnover | trades × | turnover × | verdict |
|---|---|---|---|---|---|---|
| `PROTO-M0221-C50` | — the book — | 375 | 0.4568 | 1.000 | 1.000 | — |
| `PROTO-M0221-PLC` | the shipped matched draw | 371 | 0.8681 | 0.989 | **1.900** | miss: turnover |
| `PROTO-M0221-WA` | **A** month-keyed entry order | 372 | 6.8341 | 0.992 | 14.960 | miss: turnover |
| `PROTO-M0221-WB` | **B** date-free keep ladder | 372 | 0.4612 | 0.992 | 1.010 | OK |
| `PROTO-M0221-WC` | **C** own values re-shaped | 372 | 0.8054 | 0.992 | 1.763 | miss: turnover |
| `PROTO-M0221-WD` | **D** keeps first, entrants last | 372 | 0.4620 | 0.992 | **1.011** | **OK** |

Both halves of §0's additional `G-*` requirement hold: the winning ratio was measured inside one
sweep (I8), and the winning rule's trade ratio is 0.992, inside 0.80–1.25.

**Two rules cleared, which phase 5's own §0 would read as ambiguity resolving to S.** That fork
was taken out of this phase's hands: the coordinator settled it in
`.workflows/orchestration/control-draw-remedies/DECISION-phase4-go.md` before this session started
— GO, key `G-bottom`, on the exit criteria (which outrank a handoff contract on the precedence
ladder) and on the tie-break being *checked* rather than accepted. B acquires "entrants rank below
keeps" as a side effect of `matched_partition` keeping the smallest `keep_key` holdings; D builds
it explicitly from `picks − held`, and M0201 is the direct evidence that the difference is real (B
degrades to 0.6865 there, D only to 0.7352). **This phase does not re-open that and does not
re-measure.**

**M0201 is NOT drawn**, and not because a rule failed it — see the section below.

---

## 1. What this phase did, in one paragraph

`lab.control_weight` is written, tested and shipped — the second rule on the second axis, in its
own module because that is what it is. `M0221-C50-PLCW` and `M0225-C50-PLC` are recorded dev
trials **#861** and **#862** under new allocator ids `M0221-A2` and `M0225-A2`, each
pre-registered by a commit that precedes its own run. Both read **`ok`** on D17, and all three
supersessions fired. **M0201 was not drawn** (§6), and the reason is not that a rule failed it.

**The gate takes neither method and this phase implies no promotion.** For M0221 and M0225 alike,
`hardgate.check` raises on the walk-forward fold majority (1 of 4 folds) **before** D17 is ever
reached, so their D17 refusals were inert and always were. What changed is a message and two
published sentences, not an answer. Nothing here is a reason to buy anything.

---

## 2. The shape — measured re-run against re-run, in one sweep each

Both arms were measured inside a single `dev.run_registry` call with their own book, on store
`640fc25e…`, `initial_idr = 10,000,000`, `contributions = OWNER_MONTHLY` (invariant I8). The
recorded rows appear only as context.

| arm | trades | turnover | exposure | trades × | turnover × | verdict |
|---|---|---|---|---|---|---|
| `M0221-C50` (re-run) | 375 | 0.4568 | 0.8141 | 1.000 | 1.000 | — the book — |
| **`M0221-C50-PLCW`** (#861) | **372** | **0.4620** | 0.8768 | **0.992** | **1.011** | **OK** |
| `M0225-C50` (re-run) | 375 | 0.4568 | 0.8141 | 1.000 | 1.000 | — the book — |
| **`M0225-C50-PLC`** (#862) | **372** | **0.4620** | 0.8768 | **0.992** | **1.011** | **OK** |

**The shipped arms reproduce phase 4's prototype to four decimal places.** Phase 4 predicted
`372 / 0.4620` and said *"a shipped arm landing far from 0.4620 is a wiring bug, not a finding."*
Both landed exactly there — and the free pre-run probe said so **before** either pre-registration
was committed, which is what invariant I7 is for. The Decimal-and-quantize path this phase ships
and the float path the prototype used agree to every digit the trial records.

For comparison, `lab control`'s own table reads the new arms against the **recorded** book rows,
which for M0221 sit on an older store:

| method | control | resolved by | trades × | turnover × | verdict | superseded by |
|---|---|---|---|---|---|---|
| M0221 | `M0221-R50` | first-declared | 0.21 | 0.50 | refuse | `M0221-C50-PLCW` |
| M0221 | `M0221-C50-PLC` | sibling-stem | 1.03 | 1.95 | warn | `M0221-C50-PLCW` |
| M0221 | **`M0221-C50-PLCW`** | sibling-stem | **1.03** | **1.04** | **ok** | — |
| M0225 | `M0225-R50` | first-declared | 0.19 | 0.42 | refuse | `M0225-C50-PLC` |
| M0225 | **`M0225-C50-PLC`** | sibling-stem | **0.99** | **1.01** | **ok** | — |

Both new arms resolve on `sibling-stem`, the strongest rung, exactly as the pre-write check said
they would. **`controls=` was not declared on either** (Decision D9): `sibling-stem` resolves them
correctly, no method file in the lab sets `DECLARATION_ATTR`, and a `Candidate` field exercised
for the first time inside a recorded trial is the wrong place to find out it is wrong. It would be
safe to add — `config_text` names its attributes by hand, so the field is outside `config_digest`
by construction — it is simply not needed.

### The cross-store cost, measured rather than assumed

The coordinator's rule was to re-run before quoting, because `M0221-C50` (#713) sits on
`b683da41…` and the store in the checkout is `640fc25e…`. It mattered:

| | recorded (#713, `b683da41…`) | re-run (`640fc25e…`) | boundary |
|---|---|---|---|
| `M0221-C50` trades | 360 | **375** | +15 |
| `M0221-C50` turnover | 0.4450 | **0.4568** | +0.0118 |
| `M0221-C50` money-weighted return | 5.63 % | **5.85 %** | **+0.22 points** |

So the turnover ratio reads **1.04×** against the recorded row and **1.011×** re-run against
re-run, and the published margin moves by **0.22 points** depending on which is used. Both
readings clear the band, so no verdict turns on it here — but the margin does, and §4 quotes the
one-sweep number. **Phase 3 measured this cost at exactly zero on M0208; it is 0.0067 of ratio on
M0201 and 0.22 points of money here.** The rule phase 3 refined is confirmed a third time: *a
ratio across two store fingerprints is not a comparison until it is re-measured in one sweep, and
whether re-measuring moves it is chassis-dependent.*

**On M0225 the boundary costs nothing**, and the reason is the strongest instance of the finding
in the set — see §5.

---

## 3. Rule D as shipped, and what the module actually owns

Phase 4's §11 specification, implemented as a shared contract rather than copied from the
prototype. **Nothing in `phase-4-weight-probe.py` was carried into `engine/src`**: the prototype
overrides whole methods for measurement speed and works in float; the shipped rule is a contract
with the chassis handing over its own vector.

`engine/src/seer_engine/lab/control_weight.py` owns exactly two things and can produce neither a
vector nor a name:

- **the ordering** — `bottom_entry_order(names, *, held, tag, seed, data_date)`: keeps (`picks ∩
  held`) first in `control_draw.keep_key`'s date-free order, entrants (`picks − held`) last in
  `control_draw.entry_key`'s month-keyed order. `rung_order` is the keep ladder alone and is what
  `bottom_entry_order` builds its first half from, so it has a real user rather than being kept
  for a future one;
- **the renormalisation** — `rescaled(vector, *, slots, total)`: trimmed or padded to the control's
  own length (padding repeats the **smallest** rung, which is what a real top-N does with one more
  name) and renormalised to the **shipped control's own weight sum**, so the rule changes the
  vector's shape and never how much of the book is invested.

`assigned(order, vector)` pays the k-th name of the ladder the k-th largest rung. It reads the
vector's **multiset of values** and never its order, so which real name held which weight never
crosses. Fifty numbers cross, names stripped: a shape, exactly as `matched_names` takes a size and
an entry count.

**Purity (I9) is asserted, not argued.** Neither entry point takes a clock, keeps anything, or
touches a store; `held` is the only thing the allocator knows about its own past and the entrants
are `picks − held` by definition. A test asserts the module imports nothing but `__future__`,
`collections.abc`, `datetime`, `decimal` and `control_draw` — so if it ever reaches for a market
or a store, the contract has quietly become something else and the suite says so.

**What it does not own, and the honest R1 answer carried into the docstring:** a shared module
cannot produce a weight vector, because every chassis computes its own (`m0221.weights`,
`m0047.size_weights`, `m0201.sized_weights` + `resize`). What is shared is the *assignment* of a
vector the chassis hands over — the same shape `matched_partition` already has. Phase 6 writes the
R1 verdict; this phase supplies its second structural fact as a built, tested, two-chassis
contract rather than an argument.

### Two defects the plan's own code block carried, found and fixed

- **`supersedes` must be sorted.** The plan's §3b wrote `("M0221-R50", "M0221-C50-PLC")`;
  `Candidate.__post_init__` (`backtest/dev.py:244`) requires the tuple sorted and unique, so the
  method file would not have imported. Shipped as `("M0221-C50-PLC", "M0221-R50")`, with the
  reason pinned in the test. *(Rung 6, the code.)*
- **The plan shipped no wiring for the branch key it was given.** §3b offers `G-ladder`, `G-size`
  and `G-entry` and **no `G-bottom`** — reconciliation added the fifth key (C12) without adding the
  fifth code block. Rule D's ordering and its renormalisation were therefore built from phase 4's
  §11 specification, which is explicit and complete, and the plan's `rung_order` and `assigned`
  blocks were kept verbatim beside them. *(Rung 2, the exit criteria: branch G requires "the
  weight-assignment contract in its own module … and the per-chassis adapter in each method file",
  and the coordinator named the rule.)*

### Phase 2's shadow: considered, and deliberately not used — a no-op here by two independent reads

The phase-1 handoff asked that this be stated rather than assumed. It is not used, and would
change nothing if it were:

1. **The chassis cannot read it.** Phase 1 measured M0221 and M0225 as `reads_held: false` with a
   shadow ratio of **1.000 at every K from 1 to 15** and a shipped/true ratio of 0.998 — *measured
   no-op*, the cleanest in the table. The real book here is the top fifty of the sized pool, which
   is a function of the data and not of what the book held.
2. **The weight axis never asks the shadow's question.** The shadow reconstructs the real book's
   held set at the **previous** decision, which is what `real_prev` needs. The vector this phase
   assigns is read from `now` — the chassis's own selection **at `data_date`** — which is exact and
   needs no reconstruction at any depth. There is no previous-decision estimate anywhere on the
   weight axis to improve.

So `control_weight` imports exactly one name from `control_draw` (`keep_key`) plus `entry_key`,
both on the frozen-v1 list, and **never reads the v2 shadow**. `SHADOW_DEPTH` appears in neither
method file.

---

## 4. The money — and the magnitude is four times the pre-registered range

All figures money-weighted on the owner's real deposits (237 deposits, 148,088 USD), against the
same **7.19 %/yr** SPY total return on the same deposits.

| arm | money-weighted | vs its book | max DD | PF | DSR |
|---|---|---|---|---|---|
| `M0221-C50` (re-run, one sweep) | **5.85 %** | — | 44.9 % | 1.23 | — |
| `M0221-R50` (recorded, 76 trades) | 6.72 % | +0.87 | 46.2 % | 2.68 | 0.528 |
| `M0221-C50-PLC` (recorded, 1.95× turnover) | 6.05 % | +0.20 | 55.2 % | 1.67 | 0.452 |
| **`M0221-C50-PLCW`** (#861) | **9.94 %** | **+4.09** | 43.6 % | 1.98 | 0.758 |
| `M0225-C50` (re-run, one sweep) | **5.85 %** | — | 44.9 % | 1.23 | — |
| `M0225-R50` (recorded, 73 trades) | 6.74 % | +0.89 | 46.2 % | 2.35 | — |
| **`M0225-C50-PLC`** (#862) | **9.94 %** | **+4.09** | 43.6 % | 1.98 | 0.759 |

**Scored against the pre-registration, honestly.** Both amendments predicted the deficit would
**widen** past −0.42 (M0221) and past −0.89 (M0225). The direction held on both. The **magnitude
did not**: M0221's block named a range of −0.4 to −1.0 and the measurement is **−4.09**, four
times outside it. M0225's block — written after M0221's arm had run — named "somewhere near −4"
and landed on it.

**The mechanism, named and not measured, and this is the most portable thing the phase produced.**
A control matched on trades and turnover is still a **fixed-weight book rebalanced monthly**: its
rungs are set by a date-free hash and re-imposed every decision, so it is perpetually trimming
whatever rose and topping up whatever fell. The book it controls does the exact opposite by
construction — a cap-weighted top-N lets its biggest companies grow into larger slots and never
trims them. Rebalancing is a return source in its own right, and **this chassis already carried a
smaller, independent instance of it**: `M0221-E50` holds C50's identical fifty names and records
its identical 360 trades and earns **6.91 %** against C50's 5.63 % — +1.28 points for the weight
arrangement alone, with the names and the trade count held fixed. The new arm is that effect with
a steeper, stickier ladder.

So: **D17 bands on trades and turnover, and this is the clearest case the lab has recorded that
matching both does not make a control return-neutral.** The 4 points are not evidence that blind
picking beats size ranking, and both published notes say so in plain language. Two caveats belong
beside it and are in both notes:

- **Exposure is not matched.** The control sits at 0.8768 invested against the book's 0.8141 —
  about 6 points more money at work, which at this window's equity return is worth a few tenths of
  a point on its own. D17 does not band on exposure.
- **One blind draw is one sample.** Seed 1 is the only seed either twin has, and the top rung
  (~10 %, where the ceiling binds) sits on a single hash-chosen name for twenty years. A second
  seed would settle how much of the 4 points is luck. **It was not run, and the arms were not
  re-drawn for a better number** — the plan forbids it and so does the lab.

**Turnover-matched is not cost-matched either.** Phase 4 measured its rule-D prototype paying
≈ 1.47× the book's fee bill while matching turnover to 1.1 %, because turnover is notional over
mean equity and Gotrade's fee carries a per-trade minimum. That figure is phase 4's, on the
prototype, and was **not** re-measured here. Phase 6 should carry it as phase 4 stated it.

---

## 5. What M0225's first honest control says

**M0225 has never had a shape-matched control, and this is where it gets one.** Verified
read-only with this phase's own sweep across every method's `verdict` and `analysis`: **no
owner-facing string on M0225 quotes the −0.890 deficit.** The page prints "top 50 earned 5.8 % a
year … blind picks 6.7 %" in a table and leaves the subtraction to the reader; it never states a
margin. So there was no wrong sentence to correct and **none was invented**. What `lab note`
added is the method's first honest margin sentence: the book trails a fair opponent of its own
shape by about 4 points a year, with the rebalancing mechanism printed beside it.

The old opponent is worth stating plainly for the record: `M0225-R50` traded **73 times in twenty
years** against the book's 375 and moved 0.42× the money. It was not the same book with the idea
removed; it was a far stiller book, and stillness is nearly free here.

### The twin's own before-and-after has closed on the current store

The sharpest finding of §4 is not about weights at all. On store `640fc25e…`:

| | `M0221` | `M0225` |
|---|---|---|
| book re-run, trades / turnover | 375 / 0.4568 | 375 / 0.4568 |
| book re-run, money-weighted | 5.85 % | 5.85 % |
| new control, trades / turnover | 372 / 0.4620 | 372 / 0.4620 |
| new control, money-weighted | 9.94 % | 9.94 % |

**Identical to four decimal places on every column**, because the repaired share counts the twin
exists to measure now sit in the shared store that *both* methods read. The two methods differ
only by allocator id — which is precisely why `trials` carries a global
`UNIQUE(config_digest, window)` and why `M0225-A2` has to exist as a subclass at all.

So the difference still recorded between the two pages — `M0221-C50` at 5.63 % on `b683da41…`
against `M0225-C50` at 5.85 % on `704a21fc…` — is **a difference between two vintages of the
data, not between two books.** A reader who subtracts one page's figure from the other's is
measuring a store rebuild. This is the strongest case in the set for the coordinator's general
rule, and it goes to phase 6 with the numbers attached.

---

## 6. M0201 was not drawn, and not because a rule failed it

The index's condition for appending to `m0201` is that phase 4 showed the rule closing its gap.
Phase 4 showed something better and the conditional clause resolves to **no arm at all**:

- **`M0201-Y20-MV10-PLC1` is already inside the band.** Measured re-run against re-run in one
  sweep it is **0.8008**, inside `WARN_BAND`'s 0.80 floor. The published **0.7941** was
  `1.9228 / 2.4213` — a control on `640fc25e…` divided by a book on `b683da41…`. **The boundary is
  worth 0.0067 of ratio, more than the 0.0059 gap it was blamed for.** The "near miss on one of
  two seeds" was measurement error, not draw error.
- **Its entrant rung is already right.** Phase 4 measured M0201's entrant weight at **0.966×** its
  book's, against M0221's 1.884× — the defect rule D exists to repair is simply not present.
- **Both rules that fix M0221 would break it.** Rule B takes M0201 from 0.8008 to **0.6865** and
  rule D to **0.7352**, both out of the band on the low side it was already nearest. Only rule C
  moves it toward 1.0, and rule C is the rule that fails M0221.
- **M0201 is not control-less.** `M0201-Y20-MV10-PLC2` reads 0.961 / 0.839, `ok`, and already
  supersedes `M0201-PLC2-MV10`.
- **And D17 is not M0201's operative refusal anyway** — the walk-forward fold majority raises
  first.

**That asymmetry is evidence, not a defect to fix.** A weight rule's scope is per-chassis **by
measurement** and not only by construction: rule D is a repair for a chassis that *has* an
entrant-rung defect and is harmful where there is none. That is a third measured reason R1 as
literally written is unreachable, and it belongs in phase 6's verdict beside the two structural
ones. One further fact a reader should not have to go looking for: M0201's real weight vector
**cannot be read exactly** on that chassis — `resize` sizes the book the chassis actually holds,
the real held set sits behind M0197's 40 % keep band at a quarterly re-pick, and an allocator is
handed only its own `held` — so any vector there would be the fresh top-20's, an estimate whose
error is measured at 0.955 on the entry count and unmeasured on the vector.

---

## 7. Decision D6 recorded: M0047 is excluded on measurement

**M0047 is not re-drawn, and the reason is measured.** The brief lists three weight-varying
chassis and M0047 is one of them — `size_weights(sizes, top, p)` over the picks' market values
under a ceiling. It is excluded anyway, on two independent readings:

1. **Its honest arms are already clean.** M0047's re-drawn controls read **0.99 / 0.92** and
   **0.98 / 0.89** — inside `WARN_BAND` on both axes, and both already superseding. A weight rule
   applied here would retire nothing, move no verdict, change no published sentence, and spend a
   full dev sweep to re-observe a match the lab already holds.
2. **It has almost no lookback left.** `M0047-A1` declares **427 bars** against the 473-bar
   `labkit.smoke_market` cap — **46 bars of headroom, one extra monthly step**. It is the single
   most constrained allocator in the set.

Reading (1) alone settles it; (2) is why no cheaper variant was looked for either. This is an
exclusion on measurement, not an omission. M0202, M0215, M0227 and M0243 are untouched for the
same first reason: their honest arms are already `OK`.

---

## 8. The published sentences

| method | before | after |
|---|---|---|
| **M0221** | *"a small amount that this lab has not pinned down, somewhere around 0.4 points a year, measured against a control that over-pays turnover by about twice"* | **about 4 points a year**, against a control matching on both axes — withdrawn and replaced, with the rebalancing mechanism printed beside it |
| **M0225** | *(no margin sentence ever existed; the page printed 5.8 % and 6.7 % and left the subtraction to the reader)* | **its first honest margin sentence**: about 4 points a year, same mechanism caveat, plus the note that the twin's before-and-after has closed on the current store |
| **M0201** | 0.949 / 0.794 `warn` on PLC1; `PLC2` already `ok` | unchanged — not drawn, §6 |

Both notes hold invariant I12: no ids, no digests, no code, no band names, no ratios dressed as
jargon. Both were **rehearsed on a `SEER_LAB_DB` copy first** and read back before the real
command — `--dry-run` does not protect `lab note`, which commits inside `with conn:` regardless —
and both exit codes were read directly, never through a pipe. Neither was retried.

Neither method's **verdict** was touched: M0221's and M0225's standing summaries are about the
ruler and the data repair, and neither rests on a control. `lab note --file` appends; no
`--verdict` was passed.

---

## 9. Database, looks, and the record

| | value |
|---|---|
| `git hash-object lab/lab.sqlite` **before the phase** | `7a701f11c3f069513149779e696c52a7c570c279` |
| after `lab run M0221 --amend` | `31676181e3d30175e0b9539ebf3717410661bdda` |
| after M0221's note + `lab stage` | `99f3c85d436f09b85ac1deb54b1613bf360617d6` |
| after `lab run M0225 --amend` | `dbaeacee60227ff1a50b1992d49dd12589b0140f` |
| **after M0225's note + `lab stage`** (final) | `5a4011f1950871364a77cd3744849b0769865cd0` |
| `select count(*) from trials where window='test'` | **4 → 4** |
| trial ids | `1 … 862`, **contiguous**, 862 rows |
| new trials | **#861** `M0221-C50-PLCW`, **#862** `M0225-C50-PLC` |
| new `method_amendments` | `M0221` seq 2, `M0225` seq 2 (both `2026-10-20`) |
| luck gate at both runs | `N = 165` (policy `methods`) |

**`lab test` was never invoked and `SEER_RESEARCH_TEST_STORE` was never read.** Every read above
went through `sqlite3 "file:…?mode=ro"`, which never migrates the file.

Commit order, which is what makes a fresh clone pass the sha freeze — **every pre-registration
precedes its own run**:

```
4b2f67e lab: M0221 pre-registered — the blind book paid the real book's own weight vector
35125bf lab: M0221 — the blind opponent now holds its money like the book, and the gap is 4 points
95c2f54 lab: M0225 pre-registered — the honest control the twin never got
c32d1a5 lab: M0225 — the first fair opponent this book has ever had, and it is 4 points ahead
```

Source commits took a pathspec; both `lab stage` commits took **none**. The suite was run at each
`lab stage` boundary and at the end — **6,241 passed, 3 skipped** (the three live-store opt-ins),
`ruff check engine` clean — and never in the window between a `lab run --amend` and its stage,
where the snapshot test is red by construction. No push was rejected, so no merge was needed.

---

## 10. For phase 6

- **R2 is answered with a rule, not a number.** The weight vector exists, ships, and closes the
  axis on the chassis it was proposed for: 1.900× → 1.011×, 98.8 % of the excess. Leftover 2 of
  `HANDOVER_20261019-the-honest-control` closes **with a rule**; leftover 1 (`M0225-C50-PLC` never
  drawn) closes **with an arm**.
- **R1's third measured reason.** A weight rule's scope is per-chassis by *measurement*: rule D
  repairs a chassis with an entrant-rung defect and **harms** one without (M0201, 0.8008 → 0.7352).
  Add it to the two structural reasons in the index's "honest answer on R1".
- **The headline caveat, and it outranks the margins.** A control matched on trades and turnover
  is **not** return-neutral: it is a fixed-weight book rebalanced monthly against a book that never
  trims its winners, and the independent `E50` datum (identical names, identical trades, +1.28
  points) prices the same effect without any control in it. State this beside both 4-point
  margins, or the numbers will be read as "blind picking beats size ranking".
- **Also not matched: exposure (0.8768 vs 0.8141) and cost** (phase 4's prototype paid ≈ 1.47× the
  fee bill at matched turnover). D17 bands on neither.
- **One seed is one sample** — a second seed on either twin is a new leftover, cheap, and would
  settle how much of the 4 points is luck. Not run here by design.
- **The cross-store finding, now with a third and a fourth data point.** Phase 3 measured the
  boundary at exactly zero on M0208; it is 0.0067 of ratio on M0201, **0.22 points of money on
  M0221**, and on M0225 it is the whole of the twin's recorded before-and-after — the two books are
  now identical to four decimals on the shared store. Phase 3's wording is confirmed: *re-measure
  before quoting*, not *discard every cross-store number*.
- **`entry_w` is reusable and nothing else in the lab computes it** (phase 4): it predicted
  M0221's excess to within 1 % and M0201's absence of one. A `control_shape` change, and neither
  this phase's nor phase 4's.
- **Rule A is the literal reading of leftover 2's own sentence and the worst of the four**
  (14.96× on M0221). Do not quote that sentence forward as if it described the fix.
- **This phase journalled nothing.** `lab insight` is append-only and a double append is
  permanent; every finding above is phase 6's to journal, one command at a time, exit code read
  directly.
- **The gate takes neither method.** Both are refused on the walk-forward fold majority before
  D17, so both D17 refusals were inert. Say it plainly, as phase 3 did.
