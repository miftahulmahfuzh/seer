# Handover — the held-set shadow, the weight vector, and the R1 verdict

**Written:** 2026-10-20 · **Branch:** `main` (no worktree — Decision D1: pre-registration and the
database must be committed on the same branch)
**Method ids spent:** **none.** Three new `Amendment` blocks under three existing ids (M0208 seq 2,
M0221 seq 2, M0225 seq 2) · **Next free id:** unchanged
**Plan set:** `docs/plans/CONTROL_DRAW_REMEDIES_PLAN.md`, six phases, all complete

**The lab after this run**

| | |
|---|---|
| dev trials | **858** (855 + 3) |
| test-window looks used | **4 — unchanged. None was spent.** |
| methods | **276 — unchanged.** An amendment appends under an existing id |
| amendments | **14** (11 + 3) |
| insights | **484** (478 + 6, journalled here) |
| N the luck gate judges at (policy: methods) | **165 — unchanged**, because no method was added |
| trial ids | 1..862, **contiguous** (count 862 = span 862) |
| `git hash-object lab/lab.sqlite` | `607b78cf…` before phase 3 → `5a4011f1…` after phase 5 → **`fe8978fb…`** after this phase's six insights |

*Every count re-derived on 2026-10-20 by a read-only `sqlite3
"file:/home/miftah/seer/lab/lab.sqlite?mode=ro"` query, which never migrates the file, and by
`npolicy.effective_n` through `store.connect_readonly`. The only command in this phase that could
have migrated the database was `lab control`, and it did not — the hash was identical either side
of it. Every percentage in this document is `trial_funding.mwr` — the money-weighted return on the
owner's own monthly deposits, what `lab show` prints as "your money earned" — against **7.188 %/yr**
for the same deposits in SPY TR, the recorded `spy_tr_mwr` of every row read. `total_return` and
`cagr` are not quoted anywhere: these books are funded and those columns count the owner's deposits
as gains.*

*One bookkeeping correction while re-deriving: `phase-3-results.md` records the luck-gate N moving
**164 → 165** across its own run. That cannot be right. `npolicy.dev_method_count` counts distinct
`method_id` values holding a dev trial, M0208 already held several, and an amendment creates no
method — so no run in this set could move N. The plan index measured 165 at `e3aeeff` before the
set and this phase measures 165 after it. The database is right and that one line of phase 3's file
is a slip; nothing downstream of it used the figure.*

---

## What this session established

Two defects in the lab's one matched-draw rule were measured on 2026-10-19 and deliberately
carried. Both are now closed, and neither closed the way the set expected.

**The held-set shadow was real, needed in exactly one place of nine, and bought more than it was
proposed for.** The draw was estimating a real book's monthly churn from a freshly-taken top-N
stand-in. On the paper-gains book that stand-in read **304 entries against a true 624 — 0.487×**.
Replaying the book's own rule two steps backwards instead reads 0.95 of the truth, and the arm
drawn under it is the first in that book's three-arm chain to match on both axes. But the biggest
single piece of the shortfall turned out not to be freshness at all: **44 % of it was the market
switch**, nine decisions following a cash month where the old stand-in scored a phantom book that
never existed. The replay closes that for free. On the other eight books the old estimator was
already right — 0.988 to 1.001 — so the remedy cost one re-draw, not nine.

**The weight vector was real too, and the direction was not known in advance.** Four assignment
rules were pre-registered and swept before a line of shipped code was written. The literal reading
of the original proposal — hand the k-th drawn name the k-th largest weight, keyed by month — is
the **worst** of the four at **14.96×** the book's turnover. The rule derived from the mechanism —
keeps first, entrants last, so a new name takes a bottom rung as a real top-N's new name does —
took the opponent from **1.900× to 1.011×**, closing 98.8 % of the excess on identical names.

**And the finding that outranks every margin in the set: a control matched on trades and turnover
is still not return-neutral.** Both new weight arms beat the books they were drawn to test, by
about four points a year. That is not evidence that blind picking beats ranking by size. A
fixed-weight book rebalanced monthly perpetually trims what rose and tops up what fell; the
cap-weighted book it controls does the opposite by construction and never trims. The lab already
had that effect priced with no control in it at all: the equal-weight version of the same top fifty
holds the **identical** fifty names and records the **identical** 360 trades, and earns **+1.28
points** more. Shape-matching is necessary and demonstrably not sufficient.

**What it all bought: honest controls. It bought no promotions, and it could not.** The hard gate
refuses all nine, re-read live after every write.

---

## The R1 verdict: two rules on two axes

### R1 as the brief reads it cannot be met — and no further work will make it meetable

The brief asked for **one reusable rule, applied to every chassis at once, never to one file**.
Three measured reasons it is unreachable as literally written.

**1. Turnover on a weight-varying book is not in name space at all.** `M0221-E50` holds
`M0221-C50`'s **exact** fifty names and records its **exact** 360 trades, and still turns over
**0.7126 against 0.4450 — 1.60×**. No rule that decides *which names* a control holds can reach
that, however the entry count is derived. The matched draw is a name rule by construction. Phase 4's
four assignment rules confirm it from the far side: every prototype recorded **372** trades against
the shipped control's **371** — 1.003×, pool attrition and cash-fill order and nothing else — while
their turnover ran from 0.4612 to 6.8341, a factor of fifteen. The name axis was pinned and the
whole spread was on the weight axis.

**2. A weight vector cannot be produced by a shared module.** Each chassis computes its own:
`m0221.weights` (market value under a 10 % ceiling), `m0047.size_weights` (size under a ceiling),
`m0201`'s per-company sizing with class splitting and a monthly resize. A shared module has no way
to produce any of them; only the chassis can. **Whatever is shared is the *assignment* of a vector
the chassis hands over, never the vector.**

**3. New, and measured rather than argued: a weight rule's scope is per-chassis BY MEASUREMENT.**
The chassis do not even agree on which direction needs fixing. M0221's control hands a brand-new
name **1.884×** the weight the real book gives a brand-new name, and that single fact accounts for
essentially all of its turnover excess (1.884 against a re-run excess of 1.900 — two numbers from
entirely separate computations agreeing to within 1 %). M0201's control's entrant rung is already
**0.966×** its book's: there is no defect there to repair. So the rule that fixes the first *harms*
the second — applied to M0201, rule D takes a compliant **0.8008** arm to **0.7352**, out of the
band on the low side it was already nearest. Rule B, the other clearing rule, takes it to **0.6865**.
Only rule C improves M0201 (0.9179), and rule C is the rule that fails M0221 (1.763).

### R1 in the sense `control_draw` already satisfies it is met, and is the most remedy 2 can aim at

`matched_partition` is one shared, tested ordering contract that five chassis each adapt with their
own slot count, sector cap or keep band — and the lab already calls that one rule. `control_weight`
is built to exactly that standard: it owns the **ordering** (keeps first in the date-free keep
order, entrants last in the month-keyed entry order) and the **renormalisation** (trimmed or padded
to the control's own length, renormalised to the control's own weight sum), and it can produce
neither a vector nor a name. The chassis hands over fifty numbers with the names stripped. By the
standard already in force in this module, one shared contract plus a thin per-chassis adapter **is**
one reusable rule, and **R1 in that sense is met, by rule D as a shared assignment contract**.

### So: two rules on two axes. A name rule and a weight rule. Said plainly.

A fair opponent has to match its book on two separate things, and they are not reachable by one
mechanism. Which names it holds is one question, answered in `control_draw.py`. How it holds its
money is a different question, answered in `control_weight.py`. The layout says what the prose
says, which is the point: a single module named after one of them would have been a paper-over of
exactly the kind the brief forbade. A future set should not spend effort trying to collapse them.

---

## Remedy 1 — the held-set shadow

**What it was.** `control_draw.matched_names` estimated the real book's churn from a
freshly-derived top-N stand-in for the previous held set. That stand-in is too fresh: a just-taken
top twenty is ranked 1–20, and a band that only drops a name past rank 40 almost never drops one
from there, while a real held set has accumulated names that drifted to the edge and sheds them far
faster. On M0208 the estimator read **304 entries against a true 624 — 0.487×**, uniform across
eras at 0.444 / 0.509 / 0.500.

**The replay depth.** `SHADOW_DEPTH = 2`, costing **305 bars** of the 473-bar `labkit.smoke_market`
ceiling, with **168 bars of headroom**. Two steps is the smallest depth clearing 0.90 and the curve
is flat above it — K = 3…8 sit in [0.941, 0.955] on phase 3's own ladder and never beat K = 2 by
enough to pay for 156 more bars. **The 473-bar cap is therefore not the binding constraint here**,
and widening `labkit.smoke_market` would buy nothing.

### What the shadow changed, chassis by chassis

Phase 1's probe, whole dev window, one store, one process — so every ratio is re-run against
re-run. `VERDICT_BAND = (0.90, 1.10)`.

| chassis | decisions | true entries | v1 estimate | v1 ratio | shadow at K=1 | K=2 | verdict | re-drawn? |
|---|---|---|---|---|---|---|---|---|
| M0047 | 170 | 1610 | 1591 | 0.988 | 1.000 | 1.000 | shadow is a measured no-op | no |
| M0201 | 79 | 460 | 423 | **0.920** | 0.966 | 0.947 | **borderline** — see leftover 15 | no |
| M0202 | 79 | 460 | 423 | **0.920** | 0.966 | 0.947 | **borderline** — see leftover 15 | no |
| **M0208** | 169 | **624** | **304** | **0.487** | 0.689 | **0.989** | **shadow needed** | **yes** |
| M0215 | 170 | 519 | 515 | 0.992 | 0.996 | 0.996 | shadow is a measured no-op | no |
| M0221 | 237 | 425 | 424 | 0.998 | 1.000 | 1.000 | shadow is a measured no-op | no |
| M0225 | 237 | 425 | 424 | 0.998 | 1.000 | 1.000 | shadow is a measured no-op | no |
| M0227 | 225 | 628 | 624 | 0.994 | 1.000 | 1.000 | shadow is a measured no-op | no |
| M0243 | 225 | 1308 | 1309 | 1.001 | 1.000 | 1.000 | shadow is a measured no-op | no |

**The four chassis whose real books cannot read their own holdings — M0047, M0221/M0225, M0227,
M0243 — read exactly 1.000 at every depth**, and phase 2 made that structural rather than
statistical: a test asserts they draw the identical control at depths 1, 2, 5 and 8, name for name.
Nobody has to repeat that sweep.

**Where M0208's 320 missing entries actually went**, decomposed two independent ways that agree:

| component | entries | share | does a replay close it? |
|---|---|---|---|
| **the cash-month convention** | 140 | **44 %** | **yes**, for free — the chain empties itself on a cash month |
| the freshness defect (what the shadow was proposed for) | 138 | 43 % | **yes**, at K = 2 |
| the membership convention | 42 | 13 % | **no — no depth closes it.** Leftover 14 |

The cash-month half had never been separated before. M0208's SPY 200-day switch holds the real book
in cash for 69 of the window's 238 months; the old stand-in scored a phantom top twenty at the
previous month end regardless, and on the nine decisions following a cash month it read **38 entries
against a truth of 180 — 0.211×**. Phase 3 priced the same thing from the other direction: closing
the switch inside a one-step replay carries the estimate from 304 to **446**, a difference of 142
against phase 1's 140. **So the shadow buys more than the freshness fix it was proposed for.**

### M0208, re-drawn — `M0208-CGO-N20-PLC2`, trial #860

| | trades | turnover | ratio | verdict | its own `mwr` | margin |
|---|---|---|---|---|---|---|
| the book `M0208-CGO-N20` | 624 | 3.0614 | — | — | 13.879 % | — |
| `M0208-HASH-N20`, the first control | 2749 | 15.9095 | 4.41 / 5.20 | refuse | 8.007 % | +5.871 (meaningless) |
| `M0208-CGO-N20-PLC`, amendment 1 | 455 | 2.3130 | 0.73 / 0.76 | warn | 9.532 % | +4.346 (provisional) |
| **`M0208-CGO-N20-PLC2`, amendment 2** | **596** | **3.1447** | **0.96 / 1.03** | **ok** | **10.130 %** | **+3.749 — measured** |

**The bar:** `WARN_BAND` is 0.80–1.25 on both axes and `band_verdict` is **inclusive**, so
`0.80 × 624 = 499.2` means the arm needed **≥ 500 trades** (499 reads `warn`) and **≥ 2.4492
turnover**. Turnover runs 1.0362× trades on this equal-slot chassis, so the high side binds on
turnover: **the band-clean window is 500 … 752 trades / 2.4492 … 3.8268 turnover.** The arm landed
at 596 and 3.1447, near the middle, with neither axis binding.

**This is the lab's first three-arm supersession chain** — a superseded `warn` arm itself
superseded. Every row still prints with its own ratios and its own verdict, and D17 drops both.

### What happened to the thirteen arms drawn under the old contract

**Nothing**, and that was the constraint the brief set. v1 keeps its body byte for byte (I3), every
recorded arm keeps its allocator id, and the v2 block was written **beside** v1 with a second rule
id (`SHADOW_RULE_ID = "matched-draw-v2"`) rather than bumping `RULE_ID`. Phase 2 added a
golden-vector test pinning v1's output, which is now the only thing in the tree that would go red
on an accidental in-place edit — see *What was believed to be a guard and was not*, below.

---

## Remedy 2 — the weight vector

Four assignment rules, all pre-registered in the plan before a number was seen, all swept in **one**
`dev.run_registry` call per chassis so every comparison is re-run against re-run. Phase 4's book
re-run: **375 trades / 0.4568 turnover**.

| rule | what it assigns | M0221 trades × | M0221 turnover × | inside the band? | excess closed |
|---|---|---|---|---|---|
| the shipped matched draw | the control's own sizes | 0.989 | **1.900** | no | — |
| **(A)** the real book's sorted vector, month-keyed order | the literal reading of the original proposal | 0.992 | **14.960** | no | −1451 % |
| **(B)** the same vector in the date-free keep order | | 0.992 | **1.010** | **yes** | 98.9 % |
| **(C)** the control's own sizes, ceiling re-shaped | | 0.992 | 1.763 | no | 15.2 % |
| **(D)** keeps first, entrants last down the sorted vector | **the winner** | **0.992** | **1.011** | **yes** | **98.8 %** |

**The bar was ≤ 0.5563 turnover (1.25× the recorded book) with trades inside 0.8–1.25×.** Rule D
reached **0.4620**. Two rules cleared; the coordinator broke the tie on pre-registered grounds
rather than on the 0.001 between them, and the reason is in the numbers rather than the taste:
B acquires "entrants rank below keeps" as a *side effect* of `matched_partition` keeping the
smallest-`keep_key` holdings, while D builds it **explicitly** from `picks − held`. A chassis with a
different keep band does not inherit B's property, and M0201 is the direct evidence — B degrades to
0.6865 there and D only to 0.7352.

**Rule A deserves its own sentence, because it is the literal reading of leftover 2's own proposal**
("the k-th drawn name taking the k-th largest weight the real book holds that month") and it is the
worst of the four by an order of magnitude, with fees seventeen times the book's. `entry_key`
carries a calendar-month term, so A re-shuffles every rung every month and re-trades the whole book.
**That sentence should not be quoted forward as if it described the fix.**

### The arms it earned

| arm | trial | trades | turnover | trades × | turnover × | verdict | its `mwr` | vs its book |
|---|---|---|---|---|---|---|---|---|
| `M0221-C50`, the book (re-run, one sweep) | — | 375 | 0.4568 | — | — | — | 5.85 % | — |
| `M0221-R50`, the old opponent | 718 | 76 | 0.2216 | 0.21 | 0.50 | refuse | 6.718 % | +0.87 |
| `M0221-C50-PLC`, amendment 1 | 843 | 371 | 0.8681 | 1.03 | 1.95 | warn | 6.047 % | +0.20 |
| **`M0221-C50-PLCW`, amendment 2** | **861** | **372** | **0.4620** | **1.03** | **1.04** | **ok** | **9.943 %** | **+4.09** |
| `M0225-C50`, the book | 742 | 375 | 0.4568 | — | — | — | 5.849 % | — |
| `M0225-R50`, the old opponent | 747 | 73 | 0.1935 | 0.19 | 0.42 | refuse | 6.739 % | +0.89 |
| **`M0225-C50-PLC`, its first honest control** | **862** | **372** | **0.4620** | **0.99** | **1.01** | **ok** | **9.943 %** | **+4.09** |

Both resolve on the `sibling-stem` rung, the strongest, and `controls=` was declared on neither
(D9): the rung resolves them correctly, no method file in the lab sets `DECLARATION_ATTR`, and a
`Candidate` field exercised for the first time inside a recorded trial is the wrong place to find
out it is wrong.

**M0201 was not drawn, and not because a rule failed it.** Its control already clears the band when
measured honestly (§ *the cross-store finding*), its entrant rung is already right at 0.966×, both
clearing rules would break it, and `M0201-Y20-MV10-PLC2` already reads 0.96 / 0.84 `ok`. The
conditional clause in the plan resolved to *no arm at all*.

**M0047 was excluded on measurement, not omitted** (D6). Its honest arms already read 0.99 / 0.92
and 0.98 / 0.89 — band-clean and superseding — so a weight rule there would retire nothing, move no
verdict and change no published sentence. Its allocator also has only 46 bars of lookback headroom,
the most constrained in the set. M0202, M0215, M0227 and M0243 are untouched for the same first
reason: their honest arms already read `ok`.

---

## The finding that outranks every margin in this set

**A control matched on trades and turnover is still not return-neutral.**

Both weight arms beat the books they were drawn to test by about four points a year. Read naively
that says blind picking beats ranking by company size. **It does not, and the mechanism is named
rather than guessed.**

A blind control hands each of its fifty names a slot decided once by a fixed hash, and re-imposes
those slots at every decision. So it is perpetually selling a little of whatever rose and buying a
little of whatever fell. A cap-weighted top-N does the exact opposite by construction: it lets its
biggest companies grow into bigger slots and never trims them. Rebalancing is a return source in
its own right, entirely separate from which names are held.

**The lab already had that priced independently, with no control in it at all.** `M0221-E50` holds
`M0221-C50`'s identical fifty names and records its identical 360 trades, and earns **6.905 %
against 5.627 % — +1.28 points for the weighting arrangement alone**, with names and trade count
held fixed. The new arm is that same effect with a steeper, stickier ladder.

**Two more things D17 does not band on, and neither is small:**

- **Exposure.** The control sits **0.8768** invested against the book's **0.8141** — about six
  points more money at work, worth a few tenths of a point a year by itself.
- **Cost.** At turnover matched to within 1 %, phase 4's rule-D prototype still paid **≈ 1.47×** the
  book's fee bill (3,522 USD against 2,388 over the whole window), because turnover is notional over
  mean equity while Gotrade's fee carries a per-trade minimum and the control spreads the same
  notional across differently-sized trades. *(That figure is phase 4's, measured on the prototype;
  it was not re-measured on the shipped arm.)*

**So: shape-matching is necessary and demonstrably not sufficient.** When a margin against a
shape-matched control is published, say which of trades, turnover, weighting, exposure and cost were
matched and which were not. Journalled as insight **479**.

---

## An under-shaped control's margin is an estimate of unknown sign, never a bound

The same lesson arrived twice this week from independent directions, and the two belong together.

M0208's lead was published as *"at least 4.3 points a year — provisional, and a floor rather than a
measurement"*. The word **floor** had an argued mechanism behind it: the only opponent the lab could
draw traded a quarter less often than the book, so it under-paid the broker; a correctly busy
opponent would pay the full fee bill, earn less, and the true lead could therefore only widen.

The correctly busy opponent trades **596** against the old one's 455 and the book's 624. It earned
**10.130 %** against 9.532 % — **more, not less**. The lead is **3.749 points — below the floor.**

**The mechanism is measured false.** On this chassis, how much a blind draw happens to earn varies
by more than the entire fee difference between 455 and 596 trades. The fee argument was sound as far
as it went; it was simply the smaller of the two effects, and the larger one has no sign.

The honest-control close-out reached the same conclusion from the *other* end and from thirteen arms
— *"an over-trading control's handicap is arbitrary, not a fee drag of known sign"* (insight 472),
and *"an under-trading control is a cheaper strategy, not a shape-matched one"* (471). This is a
fourteenth arm, on the under-trading side, and the first time the prediction was pre-registered and
then scored. It fired the `expected_failure` clause written before the run.

> **A margin measured against a control that does not match its book's shape is an estimate of
> unknown sign. It is not a floor, it is not a ceiling, and it is not conservative.**

So never write "at least" in front of such a number. Write the number, say which axis the control
misses and by how much, and say plainly that the true figure may be larger or smaller. **Any
sentence already in the lab calling a control-shape caveat a floor or a bound is suspect by this
argument** — the sweep below found none still standing. Journalled as insight **481**.

---

## The cross-store finding — stated as narrowly as the measurements earn

A control is always drawn and run **later** than the book it controls, and the research store is
rebuilt in between. So the lab compares across data vintages by default.

- **Twelve distinct `store_fingerprint` values across the 862 recorded trials** — re-derived here,
  read-only.
- **Ten of the fifteen recorded `-PLC` shape comparisons cross a boundary.**

This is structural, not an accident of one batch. **But it does not follow that those ratios are
wrong**, and an earlier coordinator note said so too strongly. Four measurements this week, and they
disagree with each other by design:

| chassis | what the boundary cost | how it was measured |
|---|---|---|
| **M0208** | **exactly zero** | book and both controls re-run in one sweep on one store reproduced every recorded figure **to every digit, money included** — 0.1387873198052101 against a recorded 0.13878731980521 |
| **M0201** | **0.0067 of ratio — and it flipped a verdict** | the published 0.7941 is **0.8008** re-run against re-run, **inside** the 0.80 floor. The "near miss by 0.0059" was measurement error, not draw error |
| **M0221** | **0.22 points of money** | the book reads 5.63 % recorded on `b683da41…` and **5.85 %** re-run on `640fc25e…` |
| **M0225** | **the whole of the twin's recorded before-and-after** | on the shared current store M0221's and M0225's books are identical to four decimals on *every* column |

**M0225's is the strongest case in the set.** The twin exists to measure a share-count repair, and
the difference still recorded between the two pages — 5.63 % against 5.85 % — is **a difference
between two vintages of the data, not between two books.** A reader subtracting one page's figure
from the other's is measuring a store rebuild.

Why the four disagree is itself readable: M0208 declares only SPY and reads its members through a
screen, which is about as store-insensitive as a lab chassis gets; M0201 holds its names directly
and sat on a band edge, which is exactly where a boundary is decisive. **So the rule is the narrow
one:**

> **A shape ratio or a margin computed across two store fingerprints is not a comparison until it
> has been re-measured in one sweep. Whether re-measuring moves it is chassis-dependent and must be
> measured, not assumed.**

Not *"every cross-store number is wrong"*. And the reason it is worth more than the one verdict it
moved: `store_fingerprint` is recorded on **every** trial, so a cross-boundary comparison is
**mechanically detectable**. `control_shape` could refuse one, or flag it, instead of quietly
reporting it as a number. **That is a separate plan set and it was deliberately not attempted here**
— leftover 16. Journalled as insight **482**.

---

## Does the gate take any of the nine? No — and this set never claimed it would

Re-read live through `store.connect_readonly` after every write in this set, by calling
`hardgate.check` itself.

| method | D17 refusals still live | `hardgate.check` | the clause that reports it |
|---|---|---|---|
| M0047 | — | REFUSED | wins **1 of 4** folds, pick changed |
| M0201 | `M0201-PLC1-MV10` (2.27× / 2.13×) | REFUSED | wins **2 of 4** folds — **raised before D17** |
| M0202 | — | REFUSED | wins **2 of 4** folds, pick changed |
| M0208 | **none** | REFUSED | **the kin rule** — `failed_kin` returns `('M0002',)` |
| M0215 | — | REFUSED | wins **2 of 4** folds, pick changed |
| M0221 | **none** | REFUSED | wins **1 of 4** folds — **raised before D17** |
| M0225 | **none** | REFUSED | wins **1 of 4** folds — **raised before D17** |
| M0227 | — | REFUSED | wins **2 of 4** folds, pick changed |
| M0243 | — | REFUSED | wins 3 of 4 on the picks, but `M0243-NEAR20-SW` wins only **2 of 4** on its own curve (D11) |

**`hardgate.check` short-circuits at the first failing clause, in this order: fold count → fold
majority → the promoted variant's own folds → survivorship drawdown → D17 → kin.** Three of the four
D17 refusals this set started with — M0201's, M0221's and M0225's — were therefore **inert all
along**: never the sentence `lab promote` prints, and clearing one changes nothing about any of
them. **M0208 was the only method of the nine whose operative clause was D17** — and immediately
behind D17 stands the kin rule, where `failed_kin("M0208")` returns `('M0002',)`, a method that has
already spent and **failed** its one look at the test window. M0208-CGO-N20 moves with M0002-REL-85
at 0.90 residual correlation, above the 0.85 line.

**So what this set changed is messages and sentences, not answers.** Three of the four live D17
refusals are now cleared — only M0201's `M0201-PLC1-MV10` remains, and it is one of the inert ones.
M0208's refusal moved from D17 to the kin rule. Nothing moved a verdict.

**This set bought honest controls. It bought no promotions, and it could not.** Promotion is the
owner's call on a separate day and nothing in this document implies it.

---

## What is withdrawn — every owner-facing sentence this set moved

*Found by sweeping `methods.verdict` **and** `methods.analysis` across **all 276** methods, in three
passes: the figures this set moved, the vocabulary of a control comparison, and bound-or-floor
language near that vocabulary. The previous close-out's lesson is that a phase-named list is a
floor — it missed four, three of them in the verdict string, which is what the owner reads first.*

### Named by the phases, and already corrected by them

1. **M0208, VERDICT and ANALYSIS.** Was *"a meaningless book by **at least 4.3 points a year** —
   provisional, and a floor rather than a measurement, because even the fairest control the lab can
   draw here still trades a quarter less than the book"*. Now *"a meaningless book of the same shape
   by **3.7 points a year** — measured now rather than a floor, because the fairest control the lab
   can draw finally trades as often as the book does; the earlier figures of 6 points and of at
   least 4.3 are both withdrawn."* Corrected by phase 3.
2. **M0221, ANALYSIS.** Was *"a small amount that this lab has not pinned down, somewhere around
   **0.4 points a year**, measured against a control that over-pays turnover by about twice."* A
   dated section now reads *"The gap is no longer 'somewhere around 0.4 points'. It is about 4 points
   a year"*, with the rebalancing mechanism printed beside it. Corrected by phase 5.
3. **M0225, ANALYSIS.** No margin sentence had ever existed — the page printed 5.8 % and 6.7 % and
   left the subtraction to the reader. A dated section now carries **its first honest margin
   sentence**, with the same mechanism caveat. Written by phase 5.

**This phase re-corrected none of the three** — they were already correct when it swept — and wrote
**no `lab note` at all**.

### Found by the sweep

**None.** Three passes over 276 verdicts and 276 analyses turned up no sentence the phases had
missed. The bound-language pass found exactly one owner-facing string calling a control-shape caveat
a floor, and it is M0208's, already withdrawn. The other "at least" hits are **pre-registered
success bars** written before a run (M0130, M0113, M0136, M0216 — *"had to beat the control by at
least 2 points"*), which are promises, not margin estimates, and are not this set's to touch.

*That is a result worth stating rather than a blank: the previous close-out's six phases missed four
sentences, and this one's missed none. The difference is that phases 3 and 5 each swept the whole
`methods` table themselves before writing, instead of correcting only what their own plan named.*

### Sentences that stand, and why

- **M0202** — *"led a meaningless book of the same shape by about 3.6 to 3.8 points a year"*. Its
  honest arms read 0.96 / 0.87 and 0.97 / 0.89, band-clean. Stands.
- **M0215** — *"beats random names at the same exposure by about 2 points a year"*. Its arm reads
  0.99 / 0.98. Stands.
- **M0047, M0227, M0243** — arms at 0.99 / 0.92, 0.99 / 0.99 and 1.03 / 1.03. Stand.
- **M0201** — *"beat random picks of the same shape by about 2.4 points a year"*. This was checked
  closely because M0201 is the one chassis the cross-store finding moved. The 2.4 holds against
  **both** its controls, including the band-clean one: 9.5435 − 7.1483 = **2.395** against PLC1, and
  9.5435 − 7.0689 = **2.475** against the `ok` PLC2. The sentence stands. **But both subtractions
  cross a store boundary** — the book sits on `b683da41…` and both controls on `640fc25e…` — and
  nothing in this set re-measured M0201's *money* in one sweep. Carried as leftover 17 with the
  arithmetic attached; **no number was invented and no note was written**.
- **M0221's and M0225's VERDICTS** — untouched, and correctly. Both are about the ruler and the data
  repair; neither rests on a control.

### Still unmeasured

**Nothing, for the first time in this family of sets.** M0225's −0.890 deficit against a
fifth-as-active arm was the standing example, and M0225 now has a shape-matched control. The deficit
appears in no `methods.verdict` or `methods.analysis` string — verified by this phase's own sweep,
not assumed — so there was no wrong sentence to correct and **none was invented**.

---

## What was believed to be a guard and was not

Three checks that look informative and are not. Each was verified by trying to break it. Journalled
as insight **484**.

1. **The recorded-digest test is not a guard on the draw rule.**
   `test_every_recorded_configuration_still_digests_to_its_recorded_digest` reads like protection
   for `control_draw`. It is not: `registry._canon` builds the digest from the rules, the allocator
   id and `dataclasses.fields()`, and **a module body is outside it entirely**. Two perturbations
   were applied — changing `keep_key`'s hash input, and changing `matched_names`' fill order — each
   of which silently rewrites all thirteen recorded matched-draw arms (trials 841–853). **Under both,
   that test passed**, and so did the other 46 in the three relevant modules. Phase 2's golden-vector
   test is now the only thing in the tree that goes red, and it fails on exactly one assertion.
2. **`trials.trades` is not an independent check on an entry count** for any constant-name-count
   book. `metrics.strategy_metrics` counts **closed round trips**, so on a book holding twenty names
   every entry becomes exactly one round trip and the two agree **by construction**. M0208's 624
   entries and 624 trades looked like evidence of a conflation; it is a tautology carrying no
   information. The 624 was confirmed instead by a forward replay that never reads the `trials`
   table — **so the close-out's "304 against 624" is right as published, and the 0.487× ratio was
   never in doubt.** No published string quotes the figure, so no `lab note` was warranted for it.
3. **A live D17 refusal may be one the gate never prints** — the clause-order fact above. Read
   `mis_shaped_controls` directly rather than inferring D17's state from the refusal message.

**And a warning for anyone re-running phase 2's perturbation check or quoting the plan's
verification shape:** the phase plans' perturbation blocks end with
`git checkout -- <file>` **at a point where nothing is committed**, which would discard the whole
phase rather than the perturbation. Phase 2 reverted by the exact inverse string replacement and
verified it with `sha256sum` both times. Do that instead.

---

## Leftovers, in priority order

### Closed by this set, with a result each

1. **`M0225-C50-PLC` was never drawn** (honest-control leftover 1) — **closed with an arm.** Trial
   #862, 0.99 / 1.01, `ok`. M0225's first shape-matched control in its history, and its first honest
   margin sentence.
2. **The weight-vector remedy** (leftover 2) — **closed with a rule.** `control_weight.py`, rule D,
   taking M0221's control from **1.900× to 1.011×** on identical names and within 1.003× of
   identical trades. Not a dead end; the STOP the plan built in did not fire.
3. **`control_draw.matched_names` should carry a shadow of the real held set forward** (leftover 3)
   — **closed with a rule and a measurement.** The v2 block ships beside v1; the shadow was needed on
   **one chassis of nine** and is a measured no-op on the other eight.
4. **Four `lab insight` rows written and not journalled** (leftover 4) — **closed before this set
   began.** Verified read-only here: insights **471–474**, added 2026-10-20. Commit `316c5cc`.
5. **Eight published sentences needed correcting on `/sera`** (leftover 5) — **closed before this set
   began.** Verified by reading `methods.verdict` for M0201, M0202, M0208 and M0227, each carrying
   its correction. Commits `a8c07de` and `ef972c1`.
6. **M0261** (leftover 7) — **closed.** Six recorded trials; commits `7cb6201` and `e3aeeff`.

### Carried forward, unchanged

7. **Whether to promote any of the nine.** The gate takes none, and for eight of the nine the
   operative refusal is the walk-forward fold majority, which no amount of control re-drawing
   touches. The owner's call on a separate day. *(was 6)*
8. **The two-month gate rung (`k = 2`), deferred to an `Amendment` under M0260 — free in method
   ids.** *(was 8)*
9. **Insight 457's practical conclusion still stands on the site** ("weight by company size"),
   withdrawn by 462 but, `insights` being append-only, still visible to the owner. *(was 9)*
10. **P2-ENG-N3LB** — `name_count.py`'s docstring still calls the dev trial count "the lab's N",
    which the 2026-10-08 policy move made wrong. *(was 10)*
11. **P3-ENG-V2KQ** — append a dated §7.3 revision to the lab design doc recording the N policy move
    to methods. *(was 11)*
12. **`sim.rules.PRESETS` has no weekly fractional Gotrade preset.** *(was 12)*
13. **The buyback holdability problem** — an 11.4 pt/yr lead that falls 55–85 % is a containment
    problem, not a gate problem. *(was 13)*

### New, from this set

14. **The membership convention is a second, independent defect of the matched draw, and it is NOT
    what R1 asked for.** Every method file that feeds `control_draw` reads **today's** member list at
    the earlier date. **Priced at 0.067 of ratio on M0208** — *not* the 0.202 the raw
    shipped-against-K=1 gap reads, which over-counts it threefold by absorbing the cash-month and
    freshness components; phase 1 isolated it with a third estimator that agrees with the one-step
    chain to the unit (306 against 306) on the 160 decisions both cover. Its upper bound elsewhere is
    0.046 on M0201/M0202 and **0.012 on M0047** — and note the plan's and the brief's quoted *"0.034
    on M0047"* is that chassis's **1996-2002 era**, not its whole window. **No replay depth closes
    it**, because the replay reads the same member list the shipped rule does, which is why phase 2
    was forbidden from folding it in and the v2 block takes no `members` argument.
15. **M0201 and M0202 read a borderline 0.920 on the shadow axis, and the verdict would flip on a
    different window.** They sit inside the band by exactly 0.020. **Their 2009-2015 era reads 0.827
    — outside the band on its own, in the era every owner-facing judgement in this lab is made in** —
    averaged away by a 1.034 in 2003-2008. They got no shadow, and for a reason stronger than
    "borderline": **their K curve runs backwards** (0.966 → 0.947 → 0.946), so a shadow would be an
    *active harm* there. Phase 4 reached the same place independently from the weight axis. Recorded,
    not acted on.
16. **`control_shape` could detect a cross-store comparison mechanically, and could compute
    `entry_w`.** Two changes to one module, both out of scope here and both worth a plan set:
    (a) `store_fingerprint` is on every trial, so a ratio crossing a boundary can be refused or
    flagged rather than reported as a number; (b) **`entry_w`** — the mean weight a control hands a
    name on the decision it enters — predicted M0221's turnover excess to within 1 % (1.884 against
    1.900) and predicted M0201's **absence** of one (0.966). **Nothing else in the lab computes it**,
    and D17 currently infers it from a turnover ratio instead of reading it.
17. **M0201's published 2.4-point lead is a subtraction across two data vintages, unverified.** The
    book sits on `b683da41…` and both controls on `640fc25e…`. The sentence stands — it holds against
    the band-clean control too (2.475) — but the boundary cost **0.22 points of money on M0221** and
    **zero on M0208**, so on this chassis it is simply unknown. Re-measuring is one sweep and no
    method id. **No caveat was written into the owner's text on a guess**, which is the rule this set
    itself established.
18. **One seed is one sample.** Both weight twins were drawn on seed 1 only, and the top rung —
    about 10 %, where the ceiling binds — sits on a single hash-chosen name for twenty years. A
    second seed would settle how much of the four points is luck. Cheap, and deliberately not run:
    the arms must never be re-drawn for a better number.
19. **`SMOKE_BARS = 473` is still duplicated** at `test_lab_control_draw.py:43` and
    `test_lab_control_draw_twins.py:36`. `control_draw.FIXTURE_BARS` now exists and is asserted
    against the fixture's own session count, so both could point at it. Left as a drive-by across two
    files owned by different phases.

---

## What this close-out did NOT do, and why

- **It promoted nothing and implied no promotion.** The gate refuses all nine, re-read live. No
  sentence in this document, in any phase's results file, or in any `methods` string this set wrote
  may be read as implying one (D8).
- **It spent no test-window look.** `lab test` and `lab promote` were never invoked in any phase and
  `SEER_RESEARCH_TEST_STORE` was never read. **Looks read 4 before and 4 after, asserted.**
- **It edited no recorded trial, no recorded `Amendment` block and no closed record.** Every re-draw
  is a **new** arm under a **new** amendment appended after the existing ones, and v1 keeps its body
  byte for byte.
- **It wrote no `lab note`** — the three sentences this set moved were already corrected by phases 3
  and 5, and the sweep found no fourth. Writing a note to re-say a correct sentence would have grown
  `methods.analysis`, which is append-only, for nothing.
- **It did not re-draw the eight chassis the shadow was a measured no-op on.** A measured no-op is
  not a second rule, and drawing one spends compute to measure nothing (D4).
- **It did not re-draw M0047's honest arms.** 0.99 / 0.92 and 0.98 / 0.89, band-clean and
  superseding; re-drawing retires nothing (D6).
- **It did not repair the membership convention, re-measure M0201's money in one sweep, add
  `entry_w` to `control_shape`, or run a second seed.** All four are sized, numbered and carried
  above. Growing this set to absorb them is what leftovers exist to prevent.

---

## Environment notes that save an hour

- **No worktree.** Planned and run in the main checkout, `/home/miftah/seer`, on `main`.
  `PY=/home/miftah/seer/engine/.venv/bin/python`, `PYTHONPATH=/home/miftah/seer/engine/src`,
  `SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research` (`640fc25e…`). **Never rebuild a store.**
- **`--dry-run` does not protect a `lab note` or a `lab insight`.** Only `lab test` and
  `lab gate-probe` read `args.dry_run`; `_note` and `_insight` commit inside `with conn:` regardless.
  Rehearse on a copy with `SEER_LAB_DB` pointed at it. All six insights here were rehearsed that way
  first and the live hash was confirmed unmoved by the rehearsal.
- **A `sqlite3 "file:…?mode=ro"` query never migrates the database; any `lab` command can** — even a
  read. `store.connect_readonly` is the Python equivalent and leaves `git hash-object` unmoved.
- **No pipe on a `lab` command.** `grep -v` owns a pipeline's exit status, and a retried
  `lab insight` is permanent. Redirect, echo `$?` on its own line, read the capture with `cat`.
- **`hardgate.check` short-circuits at the first failing clause** — fold count → fold majority → the
  promoted variant's own folds → survivorship drawdown → D17 → kin.
- **`lab stage` targets the checkout that owns the database, and its commit takes no pathspec.** A
  pathspec re-reads the working tree and defeats the staging.
- **The snapshot test is red by construction between a lab write and the `lab stage` that follows
  it.** Run the suite at the stage boundary and at the end, never inside that window (I11).
- **`methods.analysis` is append-only and `insights` is append-only; only `methods.verdict` can be
  replaced.** `append_analysis` refuses a section identical to the newest one — that guard is the
  only thing standing between a confused retry and a permanent duplicate.
- **The honest-control handover's count table is stale.** It reads 849 / 275 / 11 / 470 / 853 /
  N=164; at `e3aeeff`, before this set, the lab read **855 / 276 / 11 / 478 / 859 / N=165**.
  Re-derive, never copy.
- **On a rejected push: fetch and MERGE `origin/main`, never rebase.** A rebase replays a stale
  `lab.sqlite` over the live shared file. Then re-run `lab stage`, re-check that trial `n` is
  contiguous, commit the re-stage with no pathspec, and push again.

---

## The insights this set journalled

| id | kind | what it says |
|---|---|---|
| **479** | synthesis | A control matched on trades and turnover is still not return-neutral: it re-balances monthly and the book it controls never trims |
| **480** | synthesis | A fair opponent needs two rules on two axes, and the weight one was never buildable as a single shared rule |
| **481** | observation | An under-shaped control's margin is an estimate of unknown sign, never a floor |
| **482** | observation | A shape ratio across two research-store vintages is not a comparison until it is re-measured in one sweep |
| **483** | observation | A blind opponent's churn must be read off a replayed held set, not a freshly-taken one, and the market switch is the bigger half |
| **484** | risk | Three checks that carry no information: a digest test that passes under the edit it guards, a trade count that agrees by construction, and a refusal the gate never prints |

Bodies are committed beside the plan set at
`.workflows/plan/control-draw-remedies/insights/`, with the exact unpiped form each was run in.
