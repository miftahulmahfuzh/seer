# Handover — thirteen honest controls, and which of nine verdicts survived them

**Written:** 2026-10-20 · **Branch:** `feature/honest-control-redraw` (merged by the set's
coordinator, not by this phase)
**Method ids spent:** **none.** Eight new `Amendment` blocks under eight existing ids ·
**Next free id:** unchanged

**The lab after this run**

| | |
|---|---|
| dev trials | **849** (836 + 13) |
| test-window looks used | **4 — unchanged. None was spent.** |
| methods | **275 — unchanged.** An amendment appends under an existing id |
| amendments | **11** (3 before this set + 8 written by it) |
| insights | **470 — unchanged.** This phase journalled none; see *What this close-out did not do* |
| N the luck gate judges at (policy: methods) | **164 — unchanged**, because no method was added |
| trial ids | 1..853, **contiguous** (count 853 = span 853) |

*Every count re-derived on 2026-10-20 by a read-only `sqlite3
"file:/home/miftah/seer/lab/lab.sqlite?mode=ro"` query, which never migrates the file.
`git hash-object lab/lab.sqlite` was `58d9601887db8e9b57ecf90b2f6e26fe22431767` before this
close-out's first read and the same after its last: `lab control`, `store.connect_readonly` and
every `sqlite3 … mode=ro` query left it untouched. **This phase wrote nothing to the database.**
Every percentage in this document is `trial_funding.mwr` — the money-weighted return on the
owner's own monthly deposits, what `lab show` prints as "your money earned" — against **7.188
%/yr** for the same deposits put into SPY TR, which is the recorded `spy_tr_mwr` of every one of
the sixty-two rows read. `total_return` and `cagr` are not quoted anywhere: these books are
funded and those columns count the owner's deposits as gains.*

---

## What this session established

Nine dev-eligible methods were blocked by D17 — fourteen control arms whose trade count or
turnover did not match the arm they controlled. **Thirteen were re-drawn** at the book's own
shape as `Amendment`s under the existing method ids; the fourteenth (`M0225-C50-PLC`) was
deliberately never drawn. Each re-draw costs no method id, no extra N and no test-window look.

**The headline is not the one the plan hoped for, and it has two halves.**

**D17 now refuses five of the nine and did refuse all nine — and the hard gate takes none of
them.** Of the nine, **five** hold a band-clean honest control that retires the handicapped arm
it replaced (M0047, M0202, M0215, M0227, M0243); **four** do not (M0201, M0208, M0221, M0225).
But every one of the nine is still refused by `hardgate.check`, and for **eight of them the
refusal was never D17's to clear**: they lose the walk-forward fold majority, which this plan set
never touched and never promised to. R4 is served exactly as narrowly as it was written — "`lab
promote` must stop refusing the nine *on D17*" — and that buys zero promotions.

**And the most surprising measured result: an honest control does not move a margin in a known
direction. It makes the margin's opponent *defined*.** The thirteen handicapped controls earned
between **4.38 % and 11.38 %** a year (spread 7.00 points, sd 1.918); their thirteen honest
replacements earn between **6.05 % and 9.53 %** (spread 3.49, sd 0.988) — a **3.77× collapse in
variance**. On the two chassis that carry two seeds of the same control, the handicapped seeds sit
**2.19** and **1.74** points apart and the honest ones **0.079** and **0.187** — **27.6× and 9.3×
tighter**. The handicap did not bias each control by a knowable amount. It made each control's
return close to arbitrary, and the direction a margin moved when the handicap was removed is
mostly a record of where that particular arbitrary draw had landed.

### The thirteen arms, before and after

| method | the book | old control (ratios) | old margin | new control | new margin | Δ | the verdict's fate |
|---|---|---|---|---|---|---|---|
| M0047 | `M0047-MV10` (11.152) | `M0047-PLC1-MV10` (9.870) 0.55/0.50 | **+1.283** | `M0047-MV10-PLC` (7.819) 0.99/0.92 **ok** | **+3.333** | +2.050 | published "+1.3, short of the 2-point bar" is **reversed** — it now clears |
| M0047 | `M0047-MV20` (10.417) | `M0047-PLC1-MV20` (9.884) 0.55/0.51 | **+0.533** | `M0047-MV20-PLC` (7.989) 0.98/0.89 **ok** | **+2.427** | +1.895 | same clause, same reversal |
| M0201 | `M0201-Y20-MV10` (9.543) | `M0201-PLC1-MV10` (10.255) 2.27/2.13 | **−0.712** | `M0201-Y20-MV10-PLC1` (7.148) 0.95/**0.79** warn | **+2.395** | +3.107 | sign flipped; arm is `warn`, so it retires nothing |
| M0201 | `M0201-Y20-MV10` (9.543) | `M0201-PLC2-MV10` (8.065) 2.26/2.12 | **+1.479** | `M0201-Y20-MV10-PLC2` (7.069) 0.96/0.84 **ok** | **+2.475** | +0.996 | the book is now **above both** honest seeds |
| M0202 | `M0202-Y20-HALF` (12.653) | `M0202-PLC1-HALF` (11.301) 2.25/2.01 | **+1.352** | `M0202-Y20-HALF-PLC1` (9.037) 0.96/0.87 **ok** | **+3.616** | +2.263 | the published "1.4 points" is withdrawn |
| M0202 | `M0202-Y20-HALF` (12.653) | `M0202-PLC2-HALF` (9.563) 2.25/1.99 | **+3.089** | `M0202-Y20-HALF-PLC2` (8.850) 0.97/0.89 **ok** | **+3.803** | +0.714 | the two honest seeds are 0.19 apart |
| M0202 | `M0202-Y20-HALF-FAST` (12.141) | `M0202-PLC1-HALF-FAST` (11.381) 2.25/2.20 *(1.91 vs its true target)* | **+0.760** | `M0202-Y20-HALF-FAST-PLC1` (8.610) 0.96/0.89 **ok** | **+3.531** | +2.771 | re-aimed as well as re-drawn |
| M0208 | `M0208-CGO-N20` (13.879) | `M0208-HASH-N20` (8.007) **4.41/5.20** | **+5.872** | `M0208-CGO-N20-PLC` (9.532) **0.73/0.76** warn | **+4.346** | **−1.526** | **provisional, and a lower bound** |
| M0215 | `M0215-CTRL` (10.624) | `M0215-HASH` (8.662) 0.34/0.43 | **+1.962** | `M0215-CTRL-PLC` (8.461) 0.99/0.98 **ok** | **+2.163** | +0.201 | "about 2 points" survives, now honestly |
| M0215 | `M0215-CAP4` (10.342) | `M0215-HASH-CAP4` (8.615) 0.34/0.43 | **+1.727** | `M0215-CAP4-PLC` (8.729) 0.97/0.96 **ok** | **+1.613** | **−0.114** | the cap condition fails **by twice as much** |
| M0221 | `M0221-C50` (5.627) | `M0221-R50` (6.718) 0.21/0.50 | **−1.090** | `M0221-C50-PLC` (6.047) 1.03/**1.95** warn | **−0.420** | +0.671 | deficit narrows; control now over-pays turnover |
| M0225 | `M0225-C50` (5.849) | `M0225-R50` (6.739) 0.19/0.42 | **−0.890** | — **never drawn** — | — | — | **still quoted against a 0.19× arm** |
| M0227 | `M0227-S20` (12.953) | `M0227-R20` (7.732) **0.07/0.12** | **+5.220** | `M0227-S20-PLC` (9.050) 0.99/0.99 **ok** | **+3.903** | **−1.318** | the published "+5.2" is withdrawn |
| M0243 | `M0243-NEAR20` (10.449) | `M0243-NEAR20-R` (4.381) 3.01/2.98 | **+6.068** | `M0243-NEAR20-PLC` (8.830) 1.03/1.03 **ok** | **+1.619** | **−4.449** | **its own 2-point bar moves PASS → FAIL** |

*Every `mwr` at full precision from a read-only query over `trials ⋈ trial_funding`; every ratio
pair from `lab control M0047 M0201 M0202 M0208 M0215 M0221 M0225 M0227 M0243`, re-run read-only
on 2026-10-20 (exit 0, database hash unmoved). A positive margin means the book earned more than
its control.*

---

## The reconciliation this close-out owes: is there a crossover?

Phases 4, 5, 6 and 7 disagreed about the pre-registered direction. Phase 5 measured **every lead
widened**, 0 for 5, on controls that burned about twice the book's fee bill. Phase 6 measured a
lead that **narrowed**, exactly as pre-registered, on a control that burned 5.2×. Phase 6
proposed that these are not two directions but **one mechanism either side of a crossover** —
a blind monthly re-draw buys a lottery ticket on a survivorship-biased dev store, that ticket is
worth 1–3 points a year, the fee bill rises with churn, and above some churn the ticket stops
paying for itself.

**Tested against all thirteen arms. The sign split on the over-trading side is real. The single
crossover is not supported, and the claim should not be published as one mechanism.**

### What does hold, and it is clean

Order the seven family-B arms by how much their handicapped control over-traded:

| old control | trades × | turnover × | Δ margin |
|---|---|---|---|
| `M0202-PLC1-HALF` | 2.25 | 2.01 | **+2.263** |
| `M0202-PLC2-HALF` | 2.25 | 1.99 | **+0.714** |
| `M0202-PLC1-HALF-FAST` | 2.25 | 2.20 | **+2.771** |
| `M0201-PLC2-MV10` | 2.26 | 2.12 | **+0.996** |
| `M0201-PLC1-MV10` | 2.27 | 2.13 | **+3.107** |
| `M0243-NEAR20-R` | 3.01 | 2.98 | **−4.449** |
| `M0208-HASH-N20` | 4.41 | 5.20 | **−1.525** |

Five positive, two negative, **perfectly separated**, with the crossover between **2.27× and
3.01×** on trades and between **2.20× and 2.98×** on turnover. Within family B the correlation of
Δ margin with the handicap ratio is **−0.621**; within family A it is **+0.903**. Both signs are
what a single-peaked "churn pays, then stops paying" curve predicts. That much of phase 6's
reading is right and is worth keeping.

### What refutes it, in three independent ways

**1. The under-trading side's *signs* contradict it, 4 times out of 6.** Under one curve peaking
above 1.0×, every family-A arm's honest control — which *adds* churn — should earn more and every
lead should **narrow** (Δ negative). Measured: four of six are **positive**.

| old control | trades × | Δ margin | where the peak would have to sit |
|---|---|---|---|
| `M0227-R20` | **0.07** | **−1.318** | at or above 1.0× |
| `M0221-R50` | 0.21 | +0.671 | at or below 0.21× |
| `M0215-HASH` | 0.34 | +0.201 | at or below 0.34× |
| `M0215-HASH-CAP4` | 0.34 | **−0.114** | at or above 1.0× |
| `M0047-PLC1-MV10` | 0.55 | +2.050 | at or below 0.55× |
| `M0047-PLC1-MV20` | 0.55 | +1.895 | at or below 0.55× |

`M0047`'s two arms put the peak **below 0.55×**. `M0202`'s and `M0201`'s five put it **above
2.25×**. One curve cannot do both. And `M0227-R20`, the stickiest control in the lab at 0.07×,
is where a single curve demands the **largest positive** move of all thirteen — it came out
**negative**. Pooled over all thirteen arms, the correlation of Δ margin with the handicap ratio
is **−0.215**, and with its logarithm **+0.043**: the handicap ratio predicts essentially nothing
across the set.

**2. The seed noise at a fixed handicap is as large as the whole effect.** `M0202-PLC1-HALF` and
`M0202-PLC2-HALF` are the same book, the same guard, the same 2.25× handicap, differing only in
the draw seed — and their Δ margins are **+2.263 and +0.714**, 1.55 points apart. `M0201`'s two
seeds, both at 2.26–2.27×, are **+0.996 and +3.107**, **2.11 points apart**. The gap the whole
family-B split rests on — from the smallest widening (+0.714) to the largest narrowing (−1.525) —
is **2.24 points**. The crossover's signal is the same size as the noise sitting underneath it.

**3. It is a two-chassis-versus-two-chassis split, not seven arms versus two.** Arms within a
method are not independent observations. The five widening arms are **two** chassis (M0202,
M0201); the two narrowing arms are **two** chassis (M0243, M0208). A random 2/2 assignment lands
the two narrowings on the two highest-handicap chassis with probability **1/6 ≈ 0.17**. That is
not evidence; it is a coin landing the same way twice.

### What the whole set does support instead

Not a direction, and not a crossover — a **collapse of variance**. State it this way and all
thirteen arms agree:

| | handicapped controls | honest controls |
|---|---|---|
| range of the control's own `mwr` | 4.381 – 11.381 (**7.00 pts**) | 6.047 – 9.532 (**3.49 pts**) |
| standard deviation | **1.918** | **0.988** |
| variance ratio | — | **3.77× smaller** |
| seed spread, M0201's pair | **2.190** | **0.079** (27.6× tighter) |
| seed spread, M0202's pair | **1.737** | **0.187** (9.3× tighter) |
| what the control says the *frame* earns over SPY TR | −2.807 to +4.193 (**7.00 pts**) | −1.141 to +2.344 (**3.49 pts**) |

A handicapped control is not a weaker or a stronger opponent. It is an **arbitrary** one, and its
arbitrariness is of the same order as the margins it was being used to measure. That is why
phases 5 and 6 could both be measuring faithfully and reach opposite conclusions, and it is the
sentence worth carrying out of this set.

**The one directional reading that does survive, narrowly:** the two arms whose handicapped
control over-traded by **3× or more** both narrowed, and they are also the two whose handicapped
control was the furthest from what an honest one earns (`M0243-NEAR20-R` at 4.381 % against its
honest twin's 8.830; `M0208-HASH-N20` at 8.007 against 9.532). Worth one line in a future
pre-registration as a prior, never as a finding. **At 2.25× the fee argument has no measurable
sign at all.**

---

## The second reconciliation: the causes, and the success-condition scoreboard

### A missing supersession has four causes, not five

The set's running count reached "five distinct causes" by numbering rows in a table that included
two methods with **no** missing supersession, and it never numbered M0225 at all. Corrected:

| | method | cause | superseded? |
|---|---|---|---|
| — | M0047 | *no missing supersession* | yes, both |
| — | M0215 | *no missing supersession* | yes, both |
| — | M0202 | *no missing supersession* | yes, all three |
| — | M0227, M0243 | *no missing supersession* | yes |
| **1** | **M0221** | **structural** — turnover on a cap-weighted book is a property of the weight *vector*, not the names: 1.95× on 1.03× name changes, and `M0221-E50` already pays 1.60× on **identical** names and **identical** trades | no |
| **2** | **M0201** | **near miss** — 0.79410 turnover against a 0.80000 bar, 0.0059 short, on one of two seeds | one of two |
| **3** | **M0208** | **estimator** — the only miss on the *trades* axis: one unrolled step of the keep band off a fresh top-N under-counts a drifted held set by 0.487×, uniformly across three eras | no |
| **4** | **M0225** | **never drawn** — phase 3 stopped on invariant 13 after its twin missed, so no arm exists to supersede anything | no |

Three of the four are **measurements**, not mistakes: each names a property of a chassis that a
name-and-churn-matched draw cannot reach. The fourth is a deliberate, recorded stop.

### Four conditions moved FAIL → PASS. One moved PASS → FAIL. The set only ever counted the first.

This is the reconciliation that matters most for how the lab reads itself, because the running
tally was drifting toward "honest controls make methods look better."

| method | its own written success condition | handicapped | honest | move |
|---|---|---|---|---|
| **M0047** | beats its size-weighted placebo by ≥2 pts/yr | +1.283 / +0.533 **FAIL** | **+3.333 / +2.427 PASS** | **FAIL → PASS** (both arms) |
| **M0201** | ≥2 pts over **both** placebo seeds | −0.712 / +1.479 **FAIL** | **+2.395 / +2.475 PASS** | **FAIL → PASS** (both seeds) |
| **M0202** | ≥2 pts over its same-guard placebo seeds | +1.352 on the better seed **FAIL** | **+3.616 / +3.803 PASS** | **FAIL → PASS** (both guard speeds) |
| **M0208** | beats the placebo by ≥2 pts/yr | +5.872 PASS | +4.346 PASS | **unchanged**, headroom 2.9× → 2.2× the bar |
| **M0215** | the cap's gain over CTRL exceeds the placebo pair's | FALSE by **0.235** | FALSE by **0.550** | **made worse**, and the placebo half flips sign −0.047 → **+0.268** |
| **M0243** | NEAR20 beats its placebo by ≥2 pts/yr | +6.068 PASS | **+1.619 FAIL** | **PASS → FAIL** |

So: **three methods better, one worse, one unchanged, one made worse without changing its
verdict.** Phases 4, 5 and 6 each wrote a sentence about honest controls being the rare thing
that improves a verdict; none of them put **M0243** beside it, and M0243 is the method whose own
bar the honest control *broke*. The honest scoreboard is mixed, and that is the correct
impression to leave.

Two notes that keep the FAIL → PASS column from being over-read:

- **None of the three promotes anything.** M0047 wins 1 of 4 folds; M0201 wins 2 of 4 and fails
  the drawdown screen at 55.2 % and DSR at 0.643; M0202 wins 2 of 4. A method's own written bar
  passing is a statement about its *ranking*, never about promotability.
- **M0215's is the only one read between two placebos**, so re-drawing the pair re-states a
  verdict rather than a margin. Measured: `(CAP4 − CTRL) = −0.282` (unchanged, neither book
  moved), `(CAP4-PLC − CTRL-PLC) = +0.268`, so the difference-in-differences goes from
  `−0.282 − (−0.047) = −0.235` to `−0.282 − (+0.268) = **−0.550**`. A cap of four **helps** an
  arbitrary blind twenty-name book by 0.27 points a year and **costs** the raise book 0.28 —
  opposite signs, which is the strongest form the condition can fail in.

---

## Does the gate take the nine? No — and for eight of them D17 was never the blocker

Measured on 2026-10-20 through `store.connect_readonly` (`mode=ro`, no migration, no write), one
call each to `hardgate.mis_shaped_controls`, `fold_record`, `variant_record`,
`survivorship_record.over_bar`, `failed_kin` and `hardgate.check`. `lab promote` was **not**
invoked and no status moved.

| method | D17 refusals still live | what `hardgate.check` says today | the clause that reports it |
|---|---|---|---|
| M0047 | **0** `[]` | REFUSED | wins **1 of 4** folds, pick changed (also: kin M0021/M0022/M0029 test-failed) |
| M0201 | 1 `['M0201-PLC1-MV10']` | REFUSED | wins **2 of 4** folds — **raised before D17** |
| M0202 | **0** `[]` | REFUSED | wins **2 of 4** folds, pick changed |
| M0208 | 1 `['M0208-HASH-N20']` | REFUSED | **D17 — the only method in the nine where D17 is the operative clause** |
| M0215 | **0** `[]` | REFUSED | wins **2 of 4** folds, pick changed |
| M0221 | 1 `['M0221-R50']` | REFUSED | wins **1 of 4** folds — **raised before D17** |
| M0225 | 1 `['M0225-R50']` | REFUSED | wins **1 of 4** folds — **raised before D17** |
| M0227 | **0** `[]` | REFUSED | wins **2 of 4** folds, pick changed |
| M0243 | **0** `[]` | REFUSED | 3 of 4 on the picks, but `M0243-NEAR20-SW` wins only **2 of 4** on its own curve (D11) |

Three things follow, and the first two were not visible to any single phase:

1. **`hardgate.check` tests the folds *before* D17.** So for **M0201, M0221 and M0225** the live
   D17 refusal is **inert**: it is never the sentence `lab promote` prints, and clearing it would
   change nothing about any of the three. Of the four methods carrying a live D17 refusal, only
   one is actually blocked by it.
2. **M0208 is that one** — and it is the only method of the nine that clears the fold majority
   (3 of 4) *and* its promoted variant's own folds (`M0208-CGO-N40`, 3 of 4) *and* the
   survivorship drawdown bar. Behind D17 stands the **kin rule**: `failed_kin(M0208)` returns
   `('M0002',)`, which already read test-failed. So had M0208's draw landed inside the band, the
   refusal message would have changed and the answer would not have.
3. **Five of the nine now hold a band-clean honest control and D17 refuses none of them** — which
   is R4, proven, and worth exactly what it is worth: the clause D17's own refusal message named
   as "the way back" now works, and the lab can never again be in a state where a recorded,
   append-only arm blocks a book that has already replaced it. **Nothing was promoted and nothing
   became promotable.** That was never this set's promise and the handover should not be read as
   implying it.

---

## What is withdrawn — including four sentences the phases missed

The six results files named four withdrawals. A sweep of `methods.analysis` and `methods.verdict`
on 2026-10-20 found **four more**, and three of those four are the sentences the owner actually
reads on `/sera`, because they live in the **verdict** string rather than in the analysis body.

### Named by the phases

1. **M0221's −1.09 deficit** → **−0.42**. It was quoted against `M0221-R50`, trading 0.21× and
   turning over 0.50×. The replacement is itself `warn` (1.95× turnover), so the honest reading is
   *"C50 trails a blind draw of its own shape by between 0 and 0.4 points a year, with the control
   over-paying turnover by 1.95×"* — not a clean number.
2. **M0202's "a placebo passed the dev screen too, and that is the real result."** Re-scored at a
   common N = 164, both placebos that cleared are **handicapped** (0.9449, 0.9165); the three
   honest ones read 0.770, 0.756 and 0.651 against a 0.90 bar. The original comparison mixed
   N = 133 and N = 164 scores and was never valid. The **policy** recommendation built on it —
   every method in this frame must beat its same-guard placebo by a margin set in advance —
   survives; its evidence does not.
3. **M0047-EQ's +3.80.** Withdrawn, **not re-measured**. Both of EQ's placebos were size-weighted
   arms the ladder mis-aimed at it on `first-declared`; both are now aimed at `MV10` and `MV20`,
   where they belong, so **`M0047-EQ` ends this set with no control arm at all.** That is correct
   and not a gap: an arm with no placebo yields an empty findings tuple, which
   `control_shape.findings` documents as the right answer, so EQ is not refused for having none.
4. **M0208's +5.87** → **+4.35, published as PROVISIONAL and as a lower bound.** The honest
   control still trades only 0.73×, so a correctly-shaped one would pay the rest of the fee bill
   and earn less: the true figure is **at least** 4.35 and has not been measured.

### Missed by the phases, found here

5. **M0201's verdict string — the owner-facing one — is now wrong.** It reads: *"Weighted by
   company size, the bond-like picks **did no better than random picks of the same shape**."* That
   was true of the handicapped pair, which straddled the book (8.065 and 10.255 around 9.543).
   Against honest ones the book sits **above both**, by **+2.395 and +2.475**, with the two seeds
   **0.079** apart. The analysis body carries the same claim — *"The idea now sits inside the
   placebo's range. +9.5 % against +8.1 % to +10.3 % for random picks of the same shape. It is
   below placebo seed 1."* — and it is withdrawn with it. **Both are the central claim of M0201's
   published rejection, and the honest control reverses them.** The rejection itself survives on
   other grounds (55.2 % worst fall, DSR 0.643, 2 of 4 folds), which is why this is a correction
   and not a reopening.
6. **M0202's verdict string carries both withdrawn claims at once:** *"the half-size guard passed
   the dev screen, but **a meaningless book under the same guard passed it too**; the bond-like
   picks led it by only **1.4 points a year**."* Phase 5 withdrew the analysis headline and the
   1.4; neither withdrawal reached the verdict. Replace with: the lead over an honestly-shaped
   same-guard placebo is **+3.616** (seed 1) and **+3.803** (seed 2), and no honest placebo comes
   within 0.13 of the screen's luck bar.
7. **M0208's verdict string** says the book *"beat SPY on the deposits (+13.9 % vs +7.2 % a year)
   and a meaningless book **by 6 points**."* That is the +5.87 rounded, and it needs the same
   replacement and the same *provisional* flag as (4).
8. **M0243's analysis makes a claim about fees that is measurably false.** It reads: *"The buyback
   signal is genuinely informative. A blind draw from the same pool, **paying the same fees**,
   loses by six points a year. **That is the strongest control result in this family.**"*
   `M0243-NEAR20-R` traded **3.01×** and turned over **2.98×** — it did not pay the same fees, it
   paid three times them. Against a draw that does pay the same fees the gap is **+1.619**, and
   that is now the **weakest** control margin of any band-clean arm in this set. Both sentences
   are withdrawn.

### One that survived, and deserves saying

**M0215's published "the raise signal beats random names at the same exposure by about two points
a year" is unchanged and is now honestly supported** — +2.163 against a 0.99/0.98 control, where
it had been +1.962 against a 0.34/0.43 one. M0215's analysis is also the **only** file in the nine
that wrote its own handicap caveat down at the time (*"the placebo keeps its holdings much longer,
179 trades against 528"*). The author saw it, said so, and the number turned out to be right. That
is the pattern worth copying.

### And one correction to a phase's own claim

Phase 4 recorded M0047's old true-target margin as *"a number no published sentence ever used."*
It was used: `methods.analysis` for M0047 says *"beat the random picks sized the same way by **1.3
points a year** (11.2 % against 9.9 %). The success bar written before the run was 2 points. So
under size weights the ranking adds less than the bar demands."* That conclusion is **reversed**
by the honest control (+3.333 ≥ 2), so this is a withdrawal, not merely an unquoted figure.

---

## The rule that did it, and where it reaches

`control_draw.py` does not imitate a control's churn, it **derives** it. At each decision session
it recomputes the real arm's own selection now and at the previous decision session, takes the
entry count `e` as the size of the set difference, keeps `n − e` of its own held names in a
date-free hash order, and draws `e` fresh names from the same eligible pool — with every non-held
name sorted ahead of every just-dropped holding, so a dropped name is never taken straight back.
The entry count is matched **by construction**, not empirically.

Measured against the lab's previous best, M0241's cohort mirror at **1.372× / 1.131×** — a `warn`:

| | trades × | turnover × |
|---|---|---|
| the 0.07× pole, `M0227-S20-PLC` | **0.99** | **0.99** |
| the 3.01× pole, `M0243-NEAR20-PLC` | **1.03** | **1.03** |
| ten of thirteen arms | 0.95 – 1.03 | 0.84 – 1.03 |

**Where it reaches:** every equal-slot chassis, on both axes, from a 0.07× pole to a 3.01× pole.
On those the turnover ratio follows the trade ratio arithmetically and nothing else is needed.

**Where it does not, measured three ways:**

- **Weight-varying chassis.** Turnover is a property of the weight *vector*. A blind draw from a
  sized pool is flatter than the real top-N, so its weights cross the book engine's 1 %-of-equity
  resize band at a different rate on the same names — `M0221-E50` pays **1.60×** turnover holding
  `C50`'s **exact** names and recording its **exact** 360 trades. The matched draw closes the
  trade axis there (1.03×, pre-run probe 1.000) and not the turnover axis (1.95×). On M0201's
  market-value-sized chassis the same residual appears in the **low** direction, with two seeds at
  **0.794 and 0.839** straddling the bar on identical rules.
- **Books whose churn cannot be reconstructed from one unrolled step.** `matched_names` has no
  record of what the real book held — no allocator does — so it re-derives the previous held set
  from the plain top-N. For a keep band that drops a name only past rank 40, a *fresh* top-N is
  ranked 1–20 and almost nothing falls out, while the *real* held set has drifted toward the edge
  and falls out far faster. Measured over all 169 of M0208's decisions: **304 estimated entries
  against 624 real, 0.487×, uniform across 1996–2002 / 2003–2008 / 2009–2015** (0.444 / 0.509 /
  0.500). Pool attrition forcing out unscorable holdings pulls the realised count back to 455,
  which is why it landed at 0.73× rather than 0.49×.

**The transferable rule:** a control's re-key period must be derived from the book it controls,
each rebalance, from that book's own calendar. Choosing it by hand produced **both** families of
failure in this lab — 0.07× and 5.20× — from the same author correcting the first by hand and
overshooting into the second.

---

## What is now dead, and must not be bought with another method id

- **Hand-choosing a control's re-key period.** Measured at both poles; derived churn beats it on
  both axes at once. Do not spend an id re-deriving this.
- **M0241's cohort mirror as the state of the art.** 1.372× / 1.131× is a `warn`. Its docstring's
  claim that "the monthly draws are stable between rebalances, so the turnover matches too" is
  measured and wrong, and the file is a closed record that must not be edited to say so.
- **Reading a margin quoted against a handicapped control as evidence about a signal, in either
  direction.** The handicap's effect on a control's return is not a bias of known sign; it is
  **arbitrary to within 7 points a year**, and on the two chassis where it can be measured
  directly the seed alone moves it 1.7–2.2 points. There is no correction factor and there never
  will be; the only repair is a re-draw.
- **"The nearness filter plus the buyback signal is the strongest control result in this family"
  (M0243).** It was +6.07 against a 3.01× opponent; it is **+1.62**, below the method's own
  2-point bar.
- **Claiming a single direction for what an honest control does to a margin.** Phases 4, 5, 6 and
  7 each had a clean within-phase story and the four stories do not compose. The crossover
  synthesis that would have composed them is not supported (above). Record per chassis.

---

## Leftovers, in priority order

1. **`M0225-C50-PLC` was never drawn.** M0225 stays blocked on `M0225-R50` (0.19× / 0.42×) and its
   **−0.890** deficit stays quoted against an arm trading a fifth as often. Phase 3 stopped on
   invariant 13 after the identical chassis missed on M0221, and invariant 13 already carries
   M0225's own `E50` figure at **1.68×** — so the structural miss is measured and a second `-PLC`
   trial would spend a run to re-observe it. **Do not draw it under `control_draw` as it stands**;
   it is work for item 2.
2. **The weight-vector remedy, for cap-weighted and size-weighted chassis — carried, not applied.**
   Give the drawn names the real arm's own weight *vector*, the k-th drawn name taking the k-th
   largest weight the real book holds that month. The two numbers that make the case: `E50` pays
   **1.60×** turnover on **identical names and identical trades**, against `C50-PLC`'s **1.95×** on
   matched churn — so about three-quarters of the excess was never the matched draw's to close.
   It is a **second mechanism**, it applies to only three of the nine chassis (M0221/M0225
   cap-weighted, M0047 size-weighted under a ceiling, M0201 market-value-sized and re-sized
   monthly), and R1's deliverable was ONE reusable rule — so a rule needing a per-chassis patch
   has already failed R1. **A later plan set, not an edit to `control_draw`.**
3. **`control_draw.matched_names` should carry a shadow of the real held set forward — carried, not
   applied.** Replace the freshly-derived top-N stand-in for `real_prev` with a held set carried
   across decisions, so a drifted book's churn is estimated from a drifted set. Measured cost of
   not doing it: **0.487×** on M0208, uniform across eras. **This is phase 1's module and five
   recorded arms depend on its current contract**, so changing it is a plan set of its own, and it
   must be applied to every chassis at once rather than to one file.
4. **Four `lab insight` rows are written and not journalled.** See the next section; the bodies are
   on the branch at `.workflows/plan/honest-control-redraw/insights/`.
5. **Eight published sentences need correcting on `/sera`** — the four the phases named and the
   four found here, three of which live in `methods.verdict` and are therefore what the owner
   reads first. `methods.verdict` and `methods.analysis` are not append-only; `insights` is.
6. **Whether to promote any of the nine.** This set unblocked the D17 clause on five of them and
   nothing else. **The gate takes none**, and for eight of the nine the operative refusal is the
   walk-forward fold majority, which no amount of control re-drawing touches. Promotion is the
   owner's call on a separate day and is not implied by anything here.
7. **M0261, already queued** — *"Does the safety gate's best reading speed hold on a second book,
   or was the zig-zag luck about calendar dates?"* Carried forward from the gate-reading-cadence
   handover, item 2, unchanged.
8. **The two-month gate rung (`k = 2`), deferred to an `Amendment` under M0260 — free in method
   ids.** Carried forward, item 3. **This set is the proof that amendments are cheap and work:**
   thirteen trials, eight amendments, zero method ids, zero extra N, zero test-window looks.
9. **Insight 457's practical conclusion still stands on the site** ("weight by company size"),
   withdrawn by 462 but, `insights` being append-only, still visible to the owner. Carried
   forward, item 6.
10. **P2-ENG-N3LB** — `name_count.py`'s docstring still calls the dev trial count "the lab's N",
    which the 2026-10-08 policy move made wrong. Carried forward, item 7.
11. **P3-ENG-V2KQ** — append a dated §7.3 revision to the lab design doc recording the N policy
    move to methods. Carried forward, item 8.
12. **`sim.rules.PRESETS` has no weekly fractional Gotrade preset.** Carried forward, item 9.
13. **The buyback holdability problem.** Carried forward, item 5: an 11.4 pt/yr lead that falls
    55–85 % is a containment problem, not a gate problem.

---

## What this close-out did NOT do, and why

The phase-8 plan had this session merge the branch, run `lab stage` twice, journal four insights,
commit the database and push. **The set has a live coordinator (`orch-honest-control-redraw`) and
the coordinator lands the set**, so this phase measured, reconciled and wrote, and touched
neither `main` nor the database.

Three consequences, each of which is work for whoever lands this:

- **No merge, no push, no worktree or branch deletion.** `feature/honest-control-redraw` is 22
  commits ahead of `main` and intact.
- **`lab stage` was not run and neither `lab/lab.sqlite` nor `web/data/lab.json` was committed**
  (invariant 8). The coordinator has already staged the shared database on `main` through trial
  853; `git hash-object lab/lab.sqlite` is `58d9601887db8e9b57ecf90b2f6e26fe22431767` and this
  phase left it exactly there.
- **The four insights are written but not journalled.** `insights` carries append-only triggers on
  update and delete, so a row written now and invalidated by a later re-stage could never be
  removed — and writing them would move the database hash past the snapshot the coordinator has
  already staged, turning
  `test_the_committed_snapshot_is_the_export_of_the_committed_database` red on `main` with no
  `lab stage` available to this phase to repair it. **Choosing the reversible option**, the four
  bodies are on the branch, measurement slots filled, ready to run verbatim **after** the merge
  and **before** the final `lab stage`:

      .workflows/plan/honest-control-redraw/insights/A-family.txt
      .workflows/plan/honest-control-redraw/insights/B-family.txt
      .workflows/plan/honest-control-redraw/insights/D17-supersede.txt
      .workflows/plan/honest-control-redraw/insights/matched-draw.txt

  Their titles and `--kind` values, and the one-command-each form with no pipe, are in
  `insights/README.md` beside them. **Never retry one on a non-zero exit without reading the
  journal first** — a piped `lab` command hides its status and a retried append-only write is
  permanent.

---

## Environment notes that save an hour

- **The worktree has no venv and no research store.** `PY=/home/miftah/seer/engine/.venv/bin/python`,
  `SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research`. Never rebuild a store.
- **`PYTHONPATH=<checkout>/engine/src` decides which code AND which `lab.sqlite` the tests read.**
  `config.REPO_ROOT = Path(__file__).resolve().parents[3]`, so `store.COMMITTED_DB` follows
  PYTHONPATH. `main` does **not** yet carry `control_draw.py` or phase 2's `control_shape` change,
  so every sweep in this document was run with the **worktree** on PYTHONPATH and `SEER_LAB_DB`
  pointing at the main checkout's database. After the merge, use `$MAIN/engine/src`.
- **A `sqlite3 "file:…?mode=ro"` query never migrates the database; any `lab` command can** — even
  a read. Here the migration had already been applied, so `lab control` left the hash unmoved;
  hash before and after anyway. `store.connect_readonly` is the Python equivalent and is what the
  hard-gate sweep used.
- **`hardgate.check` short-circuits at the first failing clause, in this order:** fold count →
  fold majority → the promoted variant's own folds → survivorship drawdown → **D17** → kin. A
  method can carry a live D17 refusal that `lab promote` never prints. Read
  `mis_shaped_controls` directly rather than inferring D17's state from the refusal message.
- **`lab stage` targets the checkout that owns the database**, and its commit takes **no
  pathspec**: a pathspec re-reads the working tree and defeats the staging.
- **Merge before you stage.** A lab database committed ahead of the method files it refers to puts
  `main` in a state where a fresh clone fails the sha freeze.
