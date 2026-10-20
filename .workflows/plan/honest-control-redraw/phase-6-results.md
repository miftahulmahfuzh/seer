# Phase 6 result: M0208, the 4.41x extreme — the lead NARROWED, and the draw missed the band low

**Method:** M0208, capital-gains overhang (Grinblatt and Han 2005)
**Arm added:** `M0208-CGO-N20-PLC`, amendment 1, trial **853**
**Pre-registration:** `b824ded` (committed before the run; the run refuses a dirty digest)
**Verdict of this phase: a recorded STOP on shape (invariant 13), with the money reported anyway.**

Two sentences, up front, because they point in opposite directions and both are the finding:

1. **The margin moved the way the family-B prediction said.** The honest placebo earned **more**
   than the handicapped one and the lab's biggest quoted placebo lead **narrowed**, from
   **+5.872** to **+4.346** points a year. This is the first arm in the set whose pre-registered
   *direction* came out right.
2. **The draw missed the match band on both axes, low** — 0.73x trades, 0.76x turnover — so the
   new arm is `warn`, not `ok`, it supersedes nothing, and **M0208 is still refused by D17 after
   all the measuring.** The +4.346 is therefore *provisional*, and it is a lower bound on the
   honest margin, not a measurement of it.

---

## The shape, measured by `lab control M0208`

    method  control            kind     controls       resolved by     trades x  turnover x  verdict
    M0208   M0208-HASH-N20     placebo  M0208-CGO-N20  first-declared      4.41        5.20   refuse
    M0208   M0208-CGO-N20-PLC  placebo  M0208-CGO-N20  sibling-stem        0.73        0.76     warn

The match band is `[0.80, 1.25]`; the refuse band is `[0.50, 2.00]`. The new arm is **inside**
the refuse band and **outside** the match band on **both** axes. Raw counts, against the arm it
controls:

| | trades | turnover | exposure | max DD | PF |
|---|---|---|---|---|---|
| `M0208-CGO-N20` (677) | 624 | 3.061 | 0.699 | 0.249 | 3.13 |
| `M0208-HASH-N20` (680), the handicapped control | 2749 | 15.910 | 0.692 | 0.239 | 1.47 |
| `M0208-CGO-N20-PLC` (853), the honest one | **455** | **2.313** | 0.688 | 0.222 | 3.14 |

Exposure 0.688 against 0.699 confirms there is no third effect hiding in the SPY-remainder leg:
the switch is off for the same months in all three arms and the slots are the same 1/20. The only
thing that differs is which twenty names are in the book, which is what the arm was built to be.

**This is the set's only miss on the TRADES axis.** Of the thirteen re-drawn arms now recorded,
ten land inside the band, and the other two miss on turnover alone (`M0201-Y20-MV10-PLC1` at
0.79, short by 0.006; `M0221-C50-PLC` at 1.95, the cap-weighted structural case invariant 13
predicted). M0208 is the only one where the *entry count itself* came out wrong, so it is a
distinct, fifth cause of a missing supersession and not another instance of the weight-vector
problem.

### Invariant 13 binds: the miss is recorded and the phase stops

No seed was re-rolled, no second arm was minted, no weight vector was copied, and the draw was
not re-tuned until it landed. One re-draw of one book is what was pre-registered and one is what
was run. The pre-registration said so in its own `expected_failure`, before any number existed:
*"A shape miss is reported as a shape miss and the quoted margin stays provisional; it is not a
reason to try another seed."*

---

## Why it undershot — measured, not argued

The pre-registration named the shape risk correctly and then **predicted the wrong sign**. Its
`expected_failure` says the arm would land *"above 1.25x on trades"* if *"the real hysteresis is
stronger than that unroll says"*. It landed at 0.73x: the real hysteresis is **weaker** than the
unroll says, not stronger.

The cause is in the stand-in. `_targets` has no record of what the real book actually held — no
allocator does — so it reconstructs `CGO-N20`'s churn from **one unrolled step of its own band**,
using the previous month's **plain top twenty** as the stand-in for the real held set. A replay of
every monthly decision of the dev window (read-only; the lab was not opened and nothing was
written) measures exactly what that costs:

    decision months with the switch on and a scored pool: 169
    real book's entries  (held set carried forward): 624
    matched draw's estimate (one unrolled step):     304
    ratio est/real: 0.487

    era         real   est   ratio  months
    1996-2002    180    80   0.444    52
    2003-2008    226   115   0.509    52
    2009-2015    218   109   0.500    65

The replay reproduces the real book's **624** entries exactly — the same 624 closed trades trial
677 recorded — so the measurement is faithful and not a re-derivation that happens to agree.

**The estimator halves the real churn, uniformly.** The reason is that the two stand-ins are not
the same kind of set. A freshly-taken top-20 is, by construction, ranked 1–20; the band drops a
name only when it falls past rank 40, so almost none of a fresh top-20 is dropped in one month.
The *real* held set is not fresh — it accumulates names that entered at rank <20 and have since
drifted toward 40, and those sit much closer to the band's edge and fall out at a far higher rate.
One unrolled step cannot see that drift, so it systematically under-counts.

**And pool attrition partly compensates, which is why 0.487 came out as 0.73 and not as 0.49.**
`matched_names` keeps at most `len(real_now) - e` of its own held names *that are still in the
pool*; a held name that has left the index or stopped scoring is forced out regardless, and the
book tops back up to twenty. Those involuntary replacements are entries the estimator never asked
for, and they lift the realised count from 304 to 455. The miss is therefore the net of two
effects pulling opposite ways, which is also why it could not have been predicted by inspection.

**The era table also refutes the pre-registration's other shape worry.** It expected the early
window to *churn harder* — *"the band is weaker early in the window, when the pool is small"*. The
ratio is in fact **lowest** early (0.444 in 1996–2002) and flat thereafter. The miss is uniform
across twenty years, not an early-window artifact, which is what makes it a property of the rule
rather than of the data.

**The fix, for whoever plans it — not applied here.** The stand-in has to be the drifted set, not
a fresh one: carry a shadow of the real book's held set forward across decisions instead of
re-deriving `real_prev` from the plain top-N each month. That is a change to
`control_draw.matched_names`' contract, which phase 1 owns and five other arms already depend on,
so it is a later plan set's job and not an edit this phase gets to make. It belongs beside
invariant 13's weight-vector remedy in phase 8's list of carried options.

---

## The money, in `trial_funding.mwr` (SPY TR on the same deposits: **7.188 %/yr**)

| arm | n | mwr %/yr | vs SPY TR |
|---|---|---|---|
| `M0208-CGO-N20`, the book | 677 | **13.879** | +6.691 |
| `M0208-HASH-N20`, the handicapped control | 680 | 8.007 | +0.819 |
| `M0208-CGO-N20-PLC`, the honest control | **853** | **9.532** | **+2.344** |

- **The standing margin, +5.872 points, becomes +4.346.** It narrowed by **1.526** points.
- The honest placebo earned **+1.525 points more** than the handicapped one, on the same book,
  the same slots, the same band and the same switch. Paying a quarter of the fee bill is worth
  about a point and a half a year here.
- **Direction: pre-registered and correct.** The hypothesis predicted the honest placebo would
  *earn more* and the margin would *narrow*. Both happened.
- **Magnitude: pre-registered and missed.** It predicted the placebo would land *"in 10–13% a
  year"* and the margin would narrow *"to under 3 points"*. It landed at 9.532% and 4.346 points —
  short of its own band on both counts, in the direction of a smaller move than predicted.

### Why +4.346 is a lower bound and not the honest number

The new arm trades **0.73x** the book. A control that traded the full 1.00x would pay the rest of
the fee bill and the rest of the slippage, and would therefore earn **less** than 9.532 — so the
correctly-shaped margin is **at least 4.346 and probably somewhat more**. The miss does not
threaten the sign of the finding (the lead narrowed) but it does bound how much of the narrowing
is real. Quote the +4.346 as provisional and say which way it can only move.

### What this re-attributes, and it is the part worth carrying

Of `CGO-N20`'s +6.691 points over SPY TR, the split between "the shape of the book" and "the
picking inside it" reads very differently once the opponent is honest:

| | against `HASH-N20` | against `CGO-N20-PLC` |
|---|---|---|
| what the shape alone earns over SPY | +0.819 | **+2.344** |
| what the overhang ranking adds on top | +5.872 | **+4.346** |

A blind draw of twenty equal-slot names from the same screened pool, behind the same SPY 200-day
switch, beats SPY TR by **2.3 points a year**. The handicapped control said it beat SPY by 0.8,
because it was burning the difference in fees. That is the same direction as the lab's recorded
gate premium, and it moves about a point and a half of M0208's lead out of the "picking" column
and into the "shape" column — while still leaving the picking column the larger of the two.

---

## What M0208's success condition now says

> *"beats the placebo by at least 2 points a year"* — `METHOD.hypothesis`, the success list

**PASS, and it was a PASS before.** 13.879 − 9.532 = **4.346 ≥ 2**. The honest control does not
move this condition's verdict, it only halves the headroom: the margin was 2.9x the bar against
the handicapped opponent and is 2.2x the bar against the honest one. No condition moved
FAIL→PASS or PASS→FAIL in this phase.

That makes M0208 unlike M0047, M0201 and M0202, where honest controls moved four conditions
FAIL→PASS, and unlike M0215, where the honest control made the failure worse.

## What is withdrawn

The sentence **"the overhang book beats its placebo by +5.87 points a year"** — the method's own
analysis, `lab insight`, and anything downstream quoting it. It was measured against an opponent
trading 4.41 times as often and turning over 5.20 times as much, which is the widest handicap in
the lab. Replace it with:

> Against an honestly drawn control the lead is **+4.35 points a year** — and that reading is
> itself provisional, because the honest control still trades only 0.73x the book, so the true
> figure is at least 4.35 and the correctly-shaped number has not been measured.

Nothing above the amendment paragraph in the method file was edited. `HASH-N20`'s trial stays
exactly as it was recorded (D15).

---

## D17: **M0208 is still blocked**, and this is the phase's most important line

`control_shape.superseding_arm` supersedes a refusal only when the superseding arm's verdict is
**`OK`** — inside `WARN_BAND` on every axis, not merely inside `REFUSE_BAND`. `M0208-CGO-N20-PLC`
is `warn`. So:

- `M0208-HASH-N20` keeps its `refuse` and its `superseded by` column reads `—`;
- `hardgate` D17 still raises on M0208;
- **`lab promote M0208` is still refused**, exactly as it was before this phase ran.

The measurement was taken and the method was not unblocked. That is a legitimate outcome of
invariant 13 — the alternative was to tune the draw until it landed, which design §4 forbids —
but it must not be reported as a success.

### Where that leaves the nine (read-only sweep, 2026-10-20)

| method | status after this phase | why |
|---|---|---|
| M0047 | **unblocked** | both refusals superseded (0.99/0.92, 0.98/0.89) |
| M0202 | **unblocked** | all three refusals superseded |
| M0215 | **unblocked** | both refusals superseded (0.99/0.98, 0.97/0.96) |
| M0227 | **unblocked** | superseded (0.99/0.99) |
| M0243 | **unblocked** | superseded (1.03/1.03) |
| M0201 | blocked | `PLC1` is `warn` at 0.79 turnover, so `M0201-PLC1-MV10` is not superseded |
| M0208 | **blocked — this phase** | `PLC` is `warn` at 0.73/0.76 |
| M0221 | blocked | `PLC` is `warn` at 1.95 turnover (cap-weighted, invariant 13) |
| M0225 | blocked | no honest control drawn at all — phase 3's remaining work |

Five of nine unblocked; four still refused, three of them on a shape miss of the re-drawn arm and
one for want of an arm. Phase 8 should state that as the set's headline rather than "nine
unblocked", which was the plan's hope and is not what happened.

---

## Invariant compliance

| # | | |
|---|---|---|
| 1 | no recorded `config_digest` moves | all four M0208 digests pinned by test; `test_lab_methods.py` green (1757 passed) |
| 2 | the commit is the pre-registration | `b824ded` precedes the run; `why`/`hypothesis`/`expected_failure` carry the predicted direction |
| 3 | not phrased as dose-response | rationale carries `"placebo"` and `"hash order"`, none of `DOSE_MARKERS`; a test asserts it |
| 4 | one re-draw per book | one arm, one run; the miss is reported, not re-drawn |
| 5 | money is `trial_funding.mwr` | every figure above; SPY TR 7.188 |
| 6 | no test-window look | `lab test` never invoked; looks 4 → 4 |
| 7 | lab DB touched by `lab` commands only | every reporting read via `?mode=ro`; hashes below |
| 8 | no `lab stage` | not run; `lab.sqlite` and `web/data/lab.json` not committed |
| 9 | commits by pathspec | `git commit -- <paths>`, two files |
| 10 | tree green | `pytest engine/tests` and `ruff check engine` below |
| 11 | lookback ≤ 473 | `lookback_for(factor_lookback(N20))`, asserted ≤ 473 by test |
| 12 | one params value, one new allocator id | `OverhangParams(N20, keep=40)` reused; `M0208-A1`; **the set's one exception lives here** — it reuses the value of the arm it CONTROLS, because `scored` branches on `p.signal` and a `"hash"` value would match a placebo's churn instead of the book's. `_targets` raises on any other signal and a test proves it |
| 13 | names and churn matched, weight vector not | no weight vector copied; the miss is this file's recorded STOP |
| 14 | declares what it supersedes | `supersedes=("M0208-HASH-N20",)`, from the index's mapping |
| 15 | writes `phase-6-results.md` | this file |
| 16 | venv + `PYTHONPATH` | `/home/miftah/seer/engine/.venv/bin/python`, worktree `engine/src` |

## Database

| point | `git hash-object lab/lab.sqlite` |
|---|---|
| before `lab run` (max trial n = 852) | `994467ca6df0f8aa0e1250e47c51b3638e996761` |
| after `lab run --amend` (trial 853 recorded) | `58d9601887db8e9b57ecf90b2f6e26fe22431767` |
| after both `lab control` reads | `58d9601887db8e9b57ecf90b2f6e26fe22431767` — unmoved |

The before-hash matches the coordinator's recorded value byte for byte. `lab run M0208 --amend`
exited **0** (status read directly, never through a pipe). One row each in `trials`,
`trial_funding`, `trial_provenance` and `method_amendments` (M0208 seq 1, source sha
`1f7e1ce59a2a…`). Recorded dev trials 849 → 849 by the N policy, which counts methods: M0208 was
already counted, so **no method id and no extra N were spent**. Status `dev-eligible`, unchanged —
an amendment appends trials and never moves a verdict.

## Tree

- `PYTHONPATH=<worktree>/engine/src pytest engine/tests/test_lab_m0208_matched_draw.py
  engine/tests/test_lab_methods.py -n0` → **1757 passed**
- `ruff check engine` → **All checks passed!**
- committed by pathspec: `engine/src/seer_engine/lab/methods/m0208_capital_gains_overhang.py`,
  `engine/tests/test_lab_m0208_matched_draw.py`, and this file. **Not** `lab/lab.sqlite`, **not**
  `web/data/lab.json`.

## For phase 8

1. **M0208 is not unblocked.** Do not count it among the methods D17 clears. Four of the nine are
   still refused; the table above is the current reading.
2. **The set's direction is still not one direction, but it is no longer unanimous the other
   way.** Phase 5 found every lead widened; this phase found a lead that narrowed, by 1.526
   points, exactly as pre-registered. Both are real, and the difference is that this book's
   handicapped control was burning five times the fee bill rather than twice.
3. **A fifth distinct cause of a missing supersession:** the entry-count estimator itself, not the
   weight vector. One unrolled step of the band off a fresh top-N halves the churn of a band whose
   held set drifts, measured at 0.487x over 169 decisions and uniform across three eras.
4. **Carry the remedy, do not apply it:** `matched_names` should take a carried-forward shadow of
   the real book's held set as `real_prev` rather than a freshly-derived top-N. That is phase 1's
   module and five other arms depend on its current contract, so it is a later plan set's change.
   File it beside invariant 13's weight-vector remedy.
5. **Withdraw** the +5.87 sentence; publish +4.35 **as provisional**, with the reason.
6. The re-attribution in *What this re-attributes* is worth keeping: the blind book beats SPY TR
   by 2.344 points a year, not the 0.819 the handicapped control reported.
