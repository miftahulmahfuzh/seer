# Phase 4 results — Measure the weight vector, before it is built

**Date:** 2026-10-20
**Verdict:** **GO (rule D) — branch key `G-bottom`**, for M0221 and M0225 only.
**M0201 needs no arm at all**, and the reason is a finding in its own right (§4).
**Plan set:** `docs/plans/CONTROL_DRAW_REMEDIES_PLAN.md`, phase 4 of 6 (`P1-ROOT-Z7BD`)
**Environment:** `main` @ `2eed157`, research store `640fc25e…` (`engine/.research`),
`engine/.venv` (Python 3.11). Probe script
`.workflows/plan/control-draw-remedies/phase-4-weight-probe.py`, extracted from the phase plan at
**40436 chars** — the count the plan pins, so the block was transcribed unmodified.

**No trial was recorded, no method id was spent, no amendment was written and `lab` was never
invoked.**

> **The STOP did not fire, and that is not what this phase expected.** The plan, and the
> coordinator who ran this phase first precisely to get a cheap STOP, both predicted one. The
> sweep says otherwise, decisively and on both axes. §7 scores that prediction honestly and names
> the single reasoning error that produced it.

---

## 1. The recorded context — *context only, not the comparison*

| recorded arm | trades | turnover | `initial_idr` | schedule | store |
|---|---|---|---|---|---|
| `M0221-C50` (#713) | 360 | 0.4450 | 10,000,000 | +5,000,000 IDR on the 25th | `b683da41` |
| `M0221-E50` (#717) | 360 | 0.7126 | 10,000,000 | same | `b683da41` |
| `M0221-C50-PLC` (#843) | 371 | 0.8681 | 10,000,000 | same | `640fc25e` |
| `M0201-Y20-MV10` (#725) | 433 | 2.4213 | 10,000,000 | same | `b683da41` |
| `M0201-Y20-MV10-PLC1` (#848) | 411 | 1.9228 | 10,000,000 | same | `640fc25e` |

Read read-only on 2026-10-20; every row reproduces the figure the phase plan carries.

**The two books ran on a different store from their controls.** `M0221-C50` and `M0201-Y20-MV10`
were recorded against `b683da41…`; the store in `engine/.research` today is `640fc25e…`. So the
published 1.95× and the published 0.794× **both cross a store boundary**. Every ratio in this
file is re-run against re-run inside one sweep per chassis (invariant I8); the recorded numbers
appear above for context and nowhere else. §4 shows that on M0201 the boundary is not a detail —
it is the whole of the defect that method has been carrying.

**The harness is faithful.** `M0221-C50-PLC` was itself recorded on `640fc25e…`, and this phase's
re-run of it returns **371 trades / 0.8681 turnover** — its recorded row to four decimal places.
`M0201-Y20-MV10-PLC1` likewise returns **411 / 1.9228**, its recorded row exactly. The funding and
configuration are the trials' own.

---

## 2. M0221 — the sweep

Six arms, one `dev.run_registry` call, 1996-01-03 … 2015-10-16, `initial_idr = 10,000,000` and
`contributions = OWNER_MONTHLY` passed explicitly. The band is `control_shape.WARN_BAND` read
from the shipped module: **(0.80, 1.25)**.

book: `PROTO-M0221-C50` — **375 trades / 0.4568 turnover**

| arm | rule | trades | turnover | trades × | turnover × | verdict |
|---|---|---|---|---|---|---|
| `PROTO-M0221-C50` | — the book — | 375 | 0.4568 | 1.000 | 1.000 | — |
| `PROTO-M0221-PLC` | the shipped matched draw | 371 | 0.8681 | 0.989 | **1.900** | miss: turnover |
| `PROTO-M0221-WA` | **A** month-keyed entry order | 372 | 6.8341 | 0.992 | **14.960** | miss: turnover |
| `PROTO-M0221-WB` | **B** date-free keep ladder | 372 | 0.4612 | 0.992 | **1.010** | **OK** |
| `PROTO-M0221-WC` | **C** own values re-shaped | 372 | 0.8054 | 0.992 | **1.763** | miss: turnover |
| `PROTO-M0221-WD` | **D** keeps first, entrants last | 372 | 0.4620 | 0.992 | **1.011** | **OK** |

**Every prototype holds the same names as the shipped control.** `_CapWeightRule` overrides only
`_assign`; the name path is `MatchedCapTopAllocator`'s and `control_draw.matched_names` is called
unchanged, with the same tag and the same seed. The sweep confirms it from the far side: every
prototype records **372** trades against `PROTO-M0221-PLC`'s **371** — 1.003×, which is pool
attrition and cash-fill order and nothing else. The trade-count axis is matched on every arm, so
**every difference in the turnover column is on the weight axis and nowhere else.**

### How much of the excess each rule closes

The shipped control's excess over the book is `1.900 − 1.000 = 0.900`.

| rule | turnover × | excess closed |
|---|---|---|
| **A** | 14.960 | −1,451 % (fifteen times the book) |
| **B** | 1.010 | **98.9 %** |
| **C** | 1.763 | **15.2 %** |
| **D** | 1.011 | **98.8 %** |

### Secondary columns, recorded because they are not what the band measures

| arm | exposure | fee cost (USD, whole window) | × book |
|---|---|---|---|
| book | 0.8141 | 2,388 | 1.00 |
| shipped control | 0.8792 | 4,704 | 1.97 |
| **B** | 0.8841 | 3,628 | **1.52** |
| **C** | 0.8200 | 4,538 | 1.90 |
| **D** | 0.8768 | 3,522 | **1.47** |
| A | 0.9739 | 42,754 | 17.90 |

**A caveat worth carrying forward.** B and D match the book's turnover to within 1 % and still pay
**about 1.5× its fees**. Turnover is notional over mean equity; Gotrade's fee carries a per-trade
minimum, and the control spreads the same notional across differently-sized trades. D17 bands on
trades and turnover, which both rules clear — but a reader who assumes a turnover-matched control
is also a cost-matched one would be wrong. Phase 6 should say so plainly.

---

## 3. M0201 — the sweep

book: `PROTO-M0201-BOOK` — **432 trades / 2.4011 turnover**

| arm | rule | trades | turnover | trades × | turnover × | verdict |
|---|---|---|---|---|---|---|
| `PROTO-M0201-BOOK` | — the book — | 432 | 2.4011 | 1.0000 | 1.0000 | — |
| `PROTO-M0201-PLC1` | the shipped matched draw | 411 | 1.9228 | 0.9514 | **0.8008** | **OK** |
| `PROTO-M0201-WA` | **A** | 420 | 8.8178 | 0.9722 | **3.6724** | miss: turnover |
| `PROTO-M0201-WB` | **B** | 411 | 1.6483 | 0.9514 | **0.6865** | miss: turnover |
| `PROTO-M0201-WC` | **C** | 411 | 2.2039 | 0.9514 | **0.9179** | **OK** |
| `PROTO-M0201-WD` | **D** | 409 | 1.7653 | 0.9468 | **0.7352** | miss: turnover |

### The finding: M0201 has no weight defect. It has a store-boundary artifact.

**`M0201-Y20-MV10-PLC1` already clears the band.** Measured re-run against re-run inside one
sweep, its turnover ratio is **0.8008**, inside `WARN_BAND`'s 0.80 floor. The published **0.794**
is `1.9228 / 2.4213` — a control measured on `640fc25e…` divided by a book measured on
`b683da41…`.

- published ratio, across the store boundary: **0.7941**
- honest ratio, both arms on `640fc25e…`: **0.8008**
- **the boundary is worth 0.0067 of ratio — more than the 0.0059 gap it was blamed for.**

So the thing the plan set carried as "M0201's honest control misses the match band by 0.0059 on
one of two seeds" is **not a defect in the matched draw at all**. It is an artifact of comparing
two numbers measured against two different research stores, and it disappears the moment the
comparison is made the way invariant I8 requires.

**Stated with its own honesty caveat:** 0.8008 clears 0.80 by **0.0008**. That is thinner than the
difference between any two re-runs on different stores, so the correct sentence is not "M0201's
control is comfortably fine" — it is **"M0201's control sits on the band edge, and the published
miss was measurement error, not draw error."** The repair M0201 needs is a re-measurement on one
store, which costs no arm and no method id. Whether that re-measurement is worth recording as a
new trial is phase 5's and phase 6's call, not this phase's.

**Every weight rule makes M0201 worse, and the two that fix M0221 break it.** B takes it from
0.8008 to **0.6865** and D to **0.7352** — both out of the band, on the low side it was already
nearest to. Only **C** moves it toward 1.0 (0.9179), and C is the rule that fails M0221.

---

## 4. The free probe

`l1_per_year` is an **upper bound** on turnover: it counts every re-weighting that the
1 %-of-equity resize band suppresses, and misses the buying the deposits do. **It is never quoted
as a turnover number.** It is read for ordering, and for `entry_w` — the mean weight a control
hands a name on the decision it enters, which is the mechanism headline.

### M0221 — this phase's run beside the planning-time run

| arm | entries | `entry_w` | × book | `l1_per_year` | planning-time `entry_w` | agree? |
|---|---|---|---|---|---|---|
| book | 425 | 0.011709 | 1.000 | 0.5489 | 0.0117 | yes |
| shipped control | 425 | 0.022056 | **1.884** | 1.4180 | 0.0221 | yes |
| **A** | 425 | 0.056661 | 4.839 | 9.2270 | 0.0567 | yes |
| **B** | 425 | 0.011937 | **1.019** | 1.2113 | 0.0119 | yes |
| **C** | 425 | 0.021379 | 1.826 | 1.3481 | 0.0214 | yes |
| **D** | 425 | 0.008895 | **0.760** | 1.2400 | 0.0089 | yes |

Every figure reproduces the planning-time run to the digit on every arm. The script was
transcribed unmodified.

### M0201 — new information, not run before

| arm | entries | `entry_w` | × book | `l1_per_year` |
|---|---|---|---|---|
| book | 464 | 0.048056 | 1.000 | 2.8788 |
| shipped control | 444 | 0.046409 | **0.966** | 2.5483 |
| **A** | 444 | 0.083897 | 1.746 | 9.9136 |
| **B** | 444 | 0.030793 | **0.641** | 2.7760 |
| **C** | 444 | 0.046847 | 0.975 | 3.0786 |
| **D** | 444 | 0.025037 | **0.521** | 2.8977 |

The control takes 444 entries against the book's 464 — **0.957×**, the freshness approximation
`matched_entries` already makes on this chassis, which the plan records as measured at 0.955.
Reproduced.

**The M0201 probe explains §3 before the sweep does.** M0201's shipped control's entrant weight
is already **0.966×** the book's. There was never an entrant-rung defect on this chassis to fix,
so no assignment rule had anything to gain — and B and D, which exist to *shrink* the entrant's
rung, drive it to 0.641× and 0.521× of a book it already matched. That is why they break it.

### The three findings the probe supports, scored against the sweep

**1. The name axis is matched exactly — CONFIRMED.** All six M0221 arms take in **425** entries
over 237 decisions, the book's own number to the unit, and all six M0201 arms take **444**. Every
gap in §2 and §3 is on the weight axis.

**2. The entrant-rung mechanism is the right account of M0221's excess — CONFIRMED, and strongly.**
The shipped control's entrant weight is **1.884×** the book's against a measured turnover excess
of **1.900×**. Two numbers from entirely separate computations agreeing to within 1 % is good
evidence that the excess *is* the entrant's rung — not drift, not fees, not churn. M0201 confirms
it from the other side: an entrant rung already at 0.966× and no excess to explain.

**3. Rule C is arithmetically a near-no-op on M0221 — CONFIRMED, and the reason is sharper than
the plan states.** The plan's reason was "entrants are drawn uniformly, so their expected weight
is `1/n` for any normalised vector." That is right, and the load-bearing fact underneath it is
specifically that **`control_draw.keep_key` carries no size term**:

> `matched_partition` keeps `sorted(holding, key=keep_key)[:keep_n]`, and `keep_key` is a
> date-free hash of `(tag, seed, symbol)` alone. Survival is therefore independent of a name's
> market value. Under any rule that weights a name by its **own** size — which is exactly what C
> does — the keeps and the entrants are *exchangeable in size*, so the entrant's expected weight
> is the vector's mean, `total / n`, whatever shape the vector is given.

Measured: C moves the entrant rung only from 0.022056 to 0.021379 (1.884× → 1.826× of the book),
against `total / n ≈ 0.0205` at this arm's exposure. C bought **15.2 %** of the excess, which is a
real but insufficient move, and it came from narrowing the *dispersion* of all fifty trades, not
from moving the entrant's rung. **A monotone reshaping of a control's own sizes cannot relocate
its entrant, and that is a theorem about the keep rule, not a property of this chassis.**

### Why rule B clears without having been designed to — a mechanism the plan did not have

The plan predicted B "about the same, or slightly worse" than the shipped control, on the model
that an entrant lands on a *random* rung and therefore takes the vector's mean. The probe
contradicts that: B's entrant weight is 0.011937, **1.019×** the book's, not the ~1.9× the
random-rung model predicts. The reason is in `matched_partition` and it is the same fact as
finding 3, used the other way:

> The keeps are the holdings with the **smallest** `keep_key`. B hands out rungs **in `keep_key`
> order, largest rung first**. So the surviving names systematically occupy the *top* of the
> vector, and a fresh entrant — whose `keep_key` is uniform over the whole pool and is *not*
> conditioned on having survived — lands on average *below* them.

**B inherits most of D's effect for free, from a property of the shared partition's keep
ordering.** That is why B and D land 0.001 apart on M0221, and it is the single most important
thing this phase learned that the plan did not already know. It is also why B is **not** the rule
to ship — see §8.

---

## 5. The two yes/no answers

**Does any rule bring M0221's control inside `WARN_BAND`? — YES.**
The best was rule **D** at **0.4620** turnover against the book's re-run **0.4568** — **1.011×**,
against the 1.25 ceiling — with **372** trades, **0.992×**, against the 0.80–1.25 band. Rule **B**
also clears, at 0.4612 (**1.010×**) on the same 372 trades. Stated against the recorded bar for a
reader who knows that number: the ceiling is **≤ 0.5563** turnover (1.25 × the recorded 0.4450),
and against the re-run book it is **≤ 0.5710**; D's 0.4620 and B's 0.4612 clear **both**. The
shipped control reads 0.8681 and clears neither.

**Does any rule close M0201's 0.0059 gap? — The question does not survive the measurement.**
There is no gap to close. `M0201-Y20-MV10-PLC1` re-run against its own book in one sweep reads
**1.9228 / 2.4011 = 0.8008×**, already inside `WARN_BAND`, against the re-run 0.80 floor of
**1.9209** turnover (recorded equivalent ≥ 1.937). The published 0.794 was a cross-store
comparison and the boundary is worth 0.0067 of ratio — more than the 0.0059 it was blamed for.
Of the four rules, only **C** improves it further (2.2039, **0.9179×**); **B** (0.6865×) and **D**
(0.7352×) push it out of the band, and **A** (3.6724×) destroys it.

**These two verdicts are independent and neither suppresses the other**, as the plan requires. The
M0221 GO does not oblige phase 5 to touch M0201, and M0201's "no defect" finding does not weaken
the M0221 GO.

---

## 6. The direction finding

**Decision D7's worry — that attaching a foreign vector would make the control's target drift
against its own holdings and *raise* turnover — is right for rule A and wrong for rules B and D.**

Rule A is the literal reading of leftover 2's own sentence ("the k-th drawn name takes the k-th
largest weight the real book holds that month"), and it is a catastrophe: **14.96×** on M0221 and
**3.67×** on M0201, with fees seventeen times the book's. The reason is not foreign drift but the
re-shuffle: `entry_key` carries a calendar-month term, so every name is handed a different rung
every month and the whole book re-trades monthly. **The sentence leftover 2 was written in names
the worst of the four rules.** That is itself worth recording.

But once the assignment order is made stable — which is all B and D change — the foreign-vector
drift Decision D7 named is **too small to measure**. B and D attach exactly the same foreign
vector A does, and land at 1.010× and 1.011×. So the measured decomposition of the shipped
control's 1.900× excess is:

| component | share of the 0.900 excess |
|---|---|
| the entrant taking an average rung instead of a bottom rung | **~99 %** |
| foreign-vector drift (D7's worry) | **not detectable** |
| re-shuffling the assignment every month (rule A only) | catastrophic, but no shipped rule does it |

**The entrant-rung mechanism written in the plan is right, and it is sufficient, not partial.**

---

## 7. What the plan predicted, scored honestly

Every rule's direction was pre-registered in the phase plan before a sweep number existed.

| rule | predicted | measured (M0221) | verdict on the prediction |
|---|---|---|---|
| **A** | "much worse — the reshuffle re-trades most of the book monthly" | 14.960× | **right**, and the magnitude was understated |
| **B** | "about the same, or slightly worse" | **1.010× — clears** | **wrong** |
| **C** | "better, and drift-neutral by construction" | 1.763× | **right in direction, insufficient in size** |
| **D** | "best, if the mechanism above is right" | **1.011× — clears** | **right** |

### The one reasoning error, named

The plan — and the brief that ran this phase first to harvest a cheap STOP — predicted
**"the best rule lands near 1.67× against the 1.25 it needs"**, and therefore a STOP. The chain
was: the probe puts the shipped control at 2.58× where the record says 1.951×, so the probe runs
**1.32× high**; deflate every rule by 1.32; rule B's 2.21× becomes 1.67×; nothing clears.

**The deflation assumed the probe's bias is multiplicative and constant across arms. It is
neither.** Measured, the probe's over-statement factor (predicted ÷ swept turnover) is:

| arm | probe | swept | over-statement |
|---|---|---|---|
| book | 0.5489 | 0.4568 | **1.20×** |
| shipped control | 1.4180 | 0.8681 | **1.63×** |
| A | 9.2270 | 6.8341 | **1.35×** |
| **B** | 1.2113 | 0.4612 | **2.63×** |
| C | 1.3481 | 0.8054 | **1.67×** |
| **D** | 1.2400 | 0.4620 | **2.68×** |

The bias runs from 1.20× to 2.68× — a factor of 2.2 across six arms of one chassis — and it is
**anti-correlated with how good the rule is**. That is structural, not luck: `l1_per_year` counts
every notional re-weighting, while `sim.book._beyond_band` executes only those worth 1 % of the
whole account. A rule that works does so precisely by making most of its re-weightings *small*,
so a working rule has the most re-weightings suppressed and the probe over-states it most.

**So a single calibration point taken on the shipped control — the worst-behaved arm in the set —
maximally understates exactly the arms that matter.** The plan said "one calibration point is not
a calibration" and was right to; the correct inference from one point was not "deflate by 1.32"
but "the probe cannot rank these rules, run the sweep." It was run, and it disagrees.

Of the five claims the brief asked this phase to confirm or contradict:

1. *All six arms take exactly 425 entries; the name axis is exact* — **CONFIRMED**, both chassis.
2. *The shipped control's mean entrant weight is 1.89× the book's against a 1.95× turnover excess*
   — **CONFIRMED** (1.884× against a re-run 1.900×).
3. *The best assignment rule drives the entrant rung to 1.02× and still predicts 2.21× turnover,
   so fixing the rung buys about 15 % of the excess* — the probe figures are **CONFIRMED**; the
   inference is **CONTRADICTED**. Fixing the rung buys **98.8 %** of the excess. (The 15 % figure
   turns out to describe rule **C**, which does *not* fix the rung.)
4. *Deflated, the best rule lands near 1.67× against the 1.25 it needs* — **CONTRADICTED**. The
   best rule lands at **1.011×**. The deflation is invalid for the reason above.
5. *Rule C is dead for an arithmetic reason* — **CONFIRMED**, with a sharper statement of the
   reason (§4, finding 3): it holds because `keep_key` carries no size term, which makes keeps and
   entrants exchangeable in size under any own-size weighting.

---

## 8. One rule for both chassis — what the numbers say

M0221 needed its control's entrant rung to **shrink** (1.884× → the book's). M0201's control's
entrant rung was **already right** (0.966×) and its turnover already inside the band. The two
chassis are not merely pointing in opposite directions on the turnover axis, as the plan expected
— **one of them has no defect on this axis at all.**

**No single rule at a single setting serves both, and the sweep shows it directly.** D is the best
rule on M0221 (1.011×) and takes M0201 out of the band (0.7352×). C is the only rule that improves
M0201 (0.9179×) and leaves M0221 missing by a wide margin (1.763×). There is no setting that moves
both the right way, because one of them does not need moving.

So the conclusion the plan index reached structurally is confirmed by measurement, in the plan's
own words: **a weight rule is a *contract*, never one setting** — the chassis hands over its own
weight vector and its own assignment policy, and the shared module owns only the assignment
mechanics. That is the same standard `matched_partition` already meets, where five chassis each
supply their own slot count, sector cap or keep band to one shared ordering.

### The honest answer on R1

**R1 as the brief reads it — one reusable rule with no per-chassis patch — is unreachable, and
this phase's numbers close the question rather than leaving it open.** Not "unfinished":
*unreachable*, for three measured reasons.

1. **Turnover on a weight-varying book is not in name space.** `M0221-E50` holds `C50`'s exact
   names and records its exact trades and still turns over 1.60×. The matched draw is a name rule
   by construction and no name rule reaches that.
2. **A weight vector cannot be produced by a shared module.** `m0221.weights`, `m0047.size_weights`
   and `m0201`'s per-company sizing with class splitting are three different computations. A
   shared module can assign a vector; it cannot compute one.
3. **And now, the new one: the chassis do not even agree on which direction needs fixing.** M0221's
   control over-weights its entrants by 1.88×; M0201's matches at 0.97×. A rule that corrects the
   first necessarily breaks the second — measured, B and D both do, by 0.11 and 0.07 of ratio.

**R1 in the sense `control_draw` already satisfies it is met by rule D**, and that is the most R2
can honestly claim: a shared assignment contract that each chassis adapts. Phase 6 owns the
verdict; this is the evidence.

---

## 9. Why D and not B — the branch key, settled on pre-registered grounds

B (1.010×) and D (1.011×) are a dead heat on M0221: 0.001 apart on turnover and identical on
trades. **The tie is not broken on that 0.001**, which is noise. It is broken on three things
decided before the sweep or measured on the other chassis:

1. **D was the mechanism-derived rule, pre-registered as such.** The plan derived D from the
   account of the excess and predicted it best; the mechanism is confirmed (§4, finding 2) and D
   behaved as derived. B clearing was a *surprise*, and §4 explains it as an inherited accident.
2. **B's clearance is inherited, D's is built.** B works because `matched_partition` keeps the
   smallest-`keep_key` holdings while B hands out the largest rungs in `keep_key` order, so
   entrants fall below the keeps as a side effect of the shared keep rule. D makes `picks − held`
   take the bottom rungs **explicitly**. A chassis with a different keep band does not inherit
   B's property — and M0201, which has one (a 40 % band on a quarterly re-pick), is the direct
   evidence: B degrades to **0.6865×** there and D only to **0.7352×**.
3. **D reproduces *where* the churn happens, not only how much.** The book's own entrant is the
   new number 50 and takes the smallest rung; D's entrant weight is 0.760× the book's, B's is
   1.019×. D matches the book's structure; B matches its average.

**Branch key for phase 5: `G-bottom` (rule D).**

### On the plan's "two rules clearing is S" line

The phase plan's **Handoffs** section says *"Two rules clearing, or a rule clearing on one axis
only, is **S**."* The plan's dedicated **STOP rule** section says the STOP *"fires when: no rule
lands M0221's control inside `WARN_BAND` on both axes."* Both cannot hold here. The contradiction
is resolved on **rung 2 of the precedence ladder — the phase's exit criteria**, which require
*"Phase 5's input stated unambiguously: the winning rule's definition, **or** the STOP."*

The Handoffs line exists to protect phase 5 from having to *infer* a winner from an ambiguous
phase-4 file — its own sentence says so ("so phase 5 does not have to infer one from the other"),
and phase 5's §0 spells it as *"any ambiguity in phase 4's file resolves to S."* That condition is
not met: this file names one winner, on stated pre-registered grounds, and leaves phase 5 nothing
to infer. Reporting `S` when a rule measurably takes the control from 1.900× to 1.011× would
publish "unreachable" about something this phase reached — the precise class of wrong owner-facing
number this plan set exists to remove.

**No rule was invented.** All four were pre-registered in the plan before any number was seen;
ranking pre-registered rules is what the sweep is for. There is no rule E in this file.

---

## 10. The STOP rule, written out although it did not fire

**It would have fired if:** no rule landed M0221's control inside `WARN_BAND` on **both** axes
against the book re-run in the same sweep — turnover ratio in [0.80, 1.25] and trade ratio in
[0.80, 1.25]. Two rules landed inside on both axes, so it did not fire.

**Had it fired, this file would have carried:** the best turnover ratio any rule reached on M0221
beside the shipped control's own re-run ratio, as the number closing leftover 2; the one-line
reachability verdict; and the consequence that phase 5 draws neither M0221 nor M0225 and becomes
one paragraph.

**The one-line reachability verdict, which this file owes either way:**

> **Reachable, and by assignment.** Rule D takes M0221's control from **1.900×** the book's
> turnover to **1.011×**, on identical names and within 1.003× of identical trades, closing
> **98.8 %** of the excess. The remaining 1.1 % is pool attrition and cash-fill order, the
> residual `matched_partition`'s docstring already names. Leftover 2 of
> `HANDOVER_20261019-the-honest-control.md` closes with **1.011×**, against the 1.25 it needed and
> the 1.900× it started from.

**It is still not permission to invent a rule E**, and none was invented.

---

## 11. For phase 5

### Branch key: **`G-bottom`** (rule **D**)

**Scope: M0221 and M0225 only.** M0201's arm is **not** drawn — not because a rule failed it, but
because it needs none (§3). Phase 5's conditional M0201 clause resolves to *no*.

### The rule's complete definition, as the specification phase 5 implements

> At each decision, partition the control's drawn names into **keeps** (`picks ∩ held`) and
> **entrants** (`picks − held`). Order the keeps by `control_draw.keep_key(tag, seed, symbol)`
> and the entrants by `control_draw.entry_key(tag, seed, symbol, data_date)`, and concatenate:
> **keeps first, entrants last**. Hand that order the chassis's own weight vector for this
> decision, **sorted descending**, trimmed or padded to the book's length (padding repeats the
> smallest rung) and renormalised to the **shipped control's own weight sum**, so the rule changes
> the vector's shape and never how much of the book is invested.

- **What the chassis hands over:** its own sorted weight vector for the decision — fifty numbers
  with the names stripped — plus its ceiling and its exposure. `m0221.weights` computes M0221's
  and M0225's. The shared module must **not** compute a vector; it owns the ordering and the
  renormalisation only. This is the `matched_partition` shape, and the module docstring should say
  so rather than claim one rule.
- **What it reads off the real arm:** fifty numbers, names stripped and never crossing. The
  shipped amendment already reads one number (`e`, the entry count); this reads shape, not
  identity, which is the standard D17 already applies.
- **Purity (invariant I9):** nothing is carried between calls. `held` is the only thing the
  allocator knows about its own past and it is sufficient — the entrants are `picks − held` by
  definition, at no cost and with no state. `dev.run_registry` reuses one allocator object per id
  across candidates and folds, and this rule is a pure function of the date it is given.
- **The name path is untouched.** `control_draw.matched_names` is called unchanged, same tag, same
  seed. Phase 5's arms must hold the same names as `M0221-C50-PLC` holds, and a trade count more
  than ~1.01× away from it means something other than the weights moved.

### Expected numbers, so phase 5 knows a wrong wiring when it sees one

Re-run against re-run on store `640fc25e…`, dev window, `initial_idr = 10,000,000`,
`contributions = OWNER_MONTHLY`:

| | trades | turnover | ratio to book |
|---|---|---|---|
| `M0221` book | 375 | 0.4568 | — |
| **rule D arm** | **372** | **0.4620** | **0.992× trades / 1.011× turnover** |

These are prototype numbers from an uncommitted subclass. Phase 5's shipped arm will differ
slightly if it restructures the weighting path, and a recorded trial is never reproducible to the
digit in any case — but a shipped arm landing far from 0.4620 is a wiring bug, not a finding.

### Carried to phase 6

- **The M0201 store-boundary finding (§3).** It is a defect in how a published ratio was computed,
  not in the draw, and it is not R1's or R2's. M0201's published miss should be corrected or
  withdrawn, and the general lesson — a control and its book compared across two research stores
  is not a comparison — belongs in the leftovers with the 0.0067 attached.
- **Turnover-matched is not cost-matched (§2).** D's arm pays ~1.47× the book's fees while
  matching its turnover to 1.1 %. D17 does not band on cost, and nobody should read it as if it
  did.
- **`entry_w` is reusable and nothing else in the lab computes it.** "The mean weight a control
  hands a name on the decision it enters" predicted M0221's excess to within 1 % and predicted
  M0201's absence of one. D17 could read it directly rather than infer it from a turnover ratio.
  That is a `control_shape` change and belongs to neither this phase nor phase 5.
- **Rule A is the literal reading of leftover 2's own sentence, and it is the worst of the four**
  (14.96× on M0221). The sentence should not be quoted forward as if it described the fix.
- **M0225 still has no honest control until phase 5 draws one.** Its **−0.890** deficit is
  recorded in `trials` and in `HANDOVER_20261019-the-honest-control.md` and — re-checked
  read-only here — appears in **no** `methods.verdict` or `methods.analysis` string. So a
  band-clean arm gives M0225 an honest margin sentence for the first time; it corrects no wrong
  one, and no sentence should be invented to correct.
- **The gate takes none of these methods and nothing here implies a promotion** (Decision D8).

### Not done here, deliberately

- **M0047 is excluded by Decision D6** and was neither probed nor swept. Its honest arms already
  read 0.99/0.92 and 0.98/0.89 — band-clean and superseding — so re-drawing retires nothing, and
  its allocator has 46 bars of lookback headroom.
- **No drive-by.** `sim.rules` still has no weekly fractional Gotrade preset, `name_count.py`'s
  docstring is still wrong about N, and `control_shape` still has no `entry_w`.

---

## 12. Database

| | before | after |
|---|---|---|
| `git hash-object lab/lab.sqlite` | `607b78cf69c8e4e3a68a1e84c85eedfd1040c754` | `607b78cf69c8e4e3a68a1e84c85eedfd1040c754` |
| `select count(*) from trials where window='test'` | **4** | **4** |

Both read through `sqlite3 "file:lab/lab.sqlite?mode=ro"`, which never migrates the file. **No
`lab` command was run in this phase at all** — not even a read — so nothing could have migrated
it. `SEER_RESEARCH_TEST_STORE` was never set and `engine/.research-test` was never opened.
Invariants I1 and I5 hold.
