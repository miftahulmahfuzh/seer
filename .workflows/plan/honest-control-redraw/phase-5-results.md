# Phase 5 result: the rate-beta chassis, five arms — every lead widened, and one turnover missed by 0.006

**Written:** 2026-10-20
**Verdict:** **M0202 repaired and D17-clear on all three arms. M0201 half-repaired: one arm `warn`
at 0.794 turnover, so `M0201-PLC1-MV10` is never superseded and M0201 stays D17-blocked.**
**The pre-registered direction MISSED on all five arms, in the same direction on both methods.**
**Rule:** `seer_engine.lab.control_draw`, `RULE_ID = "matched-draw-v1"`, allocators `M0201-A1`, `M0202-A1`
**TaskID:** `P2-ENG-F5WK` · **Branch:** `feature/honest-control-redraw`
**Pre-registrations:** `4e5359a` (M0201, `method_amendments` seq 1) · `5e794af` (M0202, seq 1)
**Trials:** `#848 M0201-Y20-MV10-PLC1`, `#849 M0201-Y20-MV10-PLC2` (ran 2026-10-19),
`#850 M0202-Y20-HALF-PLC1`, `#851 M0202-Y20-HALF-PLC2`, `#852 M0202-Y20-HALF-FAST-PLC1`
(ran 2026-10-20 by this session). All five `window='dev'`.

> The two M0201 arms were measured on the night of 2026-10-19 by this phase's earlier session,
> which the tmux crash killed before it could commit or report. Their trials are recorded and
> `lab run` refuses their digests; this file writes them up rather than re-running them. The
> three M0202 arms were pre-registered and run by this session, and their database hashes are
> captured below — the first run-time hashes any phase in this set has been able to supply.

## The shape, measured by `lab control M0201 M0202`

| | `M0201-Y20-MV10-PLC1` | `M0201-Y20-MV10-PLC2` | `M0202-Y20-HALF-PLC1` | `M0202-Y20-HALF-PLC2` | `M0202-Y20-HALF-FAST-PLC1` |
|---|---|---|---|---|---|
| resolves to (rung) | `M0201-Y20-MV10` (**sibling-stem**) | `M0201-Y20-MV10` (**sibling-stem**) | `M0202-Y20-HALF` (**sibling-stem**) | `M0202-Y20-HALF` (**sibling-stem**) | `M0202-Y20-HALF-FAST` (**sibling-stem**) |
| trades, ratio | 411 / 433 = **0.949** | 416 / 433 = **0.961** | 423 / 440 = **0.961** | 425 / 440 = **0.966** | 423 / 440 = **0.961** |
| turnover, ratio | 1.9228 / 2.4213 = **0.794** | 2.0316 / 2.4213 = **0.839** | 2.0484 / 2.3529 = **0.871** | 2.0994 / 2.3529 = **0.892** | 2.4004 / 2.7063 = **0.887** |
| verdict | **warn** | **ok** | **ok** | **ok** | **ok** |
| `mwr` % | 7.148 | 7.069 | 9.037 | 8.850 | 8.610 |
| worst fall % | 47.4 | 56.8 | 39.6 | 46.5 | 51.2 |
| profit factor | 1.607 | 1.768 | 1.937 | 1.862 | 1.704 |
| exposure | 0.9594 | 0.9629 | 0.8198 | 0.8226 | 0.8655 |

**Four of five clear `WARN_BAND = [0.80, 1.25]` on both axes. The fifth misses turnover by
0.0059** — `M0201-Y20-MV10-PLC1` at **0.79410** against a 0.80000 bar. The trade axis is right on
all five (0.949–0.966, against a pre-run walk that predicted ≈0.95), so the entry-count derivation
did exactly what it was built to do; what missed is the second axis, which that derivation does
not control.

### The miss is invariant 12's recorded STOP, and it is not patched

Index invariant 12: *match names and churn only; a turnover miss is a recorded STOP, never patched
by giving the drawn names the real arm's weight vector.* That is what happened and that is where
it is left. `M0201-Y20-MV10-PLC1` is reported at 0.794, no seed was re-rolled, no weight vector was
copied, and no fourth M0201 arm was minted to find a luckier draw.

**Why this chassis and not M0202's.** `M0201-Y20-MV10` re-sizes its book **monthly by market
value** behind a 10% ceiling; `M0202-Y20-HALF` is flat 1/20. On a weight-varying chassis a blind
book that takes in the same *number* of names still holds different *companies*, and each one's
weight drifts on its own market cap between re-picks, so the dollar turnover the rebalance
generates is a property of which names were drawn and not of how many. This is the third
appearance of the same structural effect in this set and the first in the low direction:

| phase | arm | trades x | turnover x | direction |
|---|---|---|---|---|
| 3 | `M0221-E50` (cap-weighted) | 1.00 (identical names, identical 360 trades) | **1.60** | too much |
| 3 | `M0221-C50-PLC` | 1.03 | **1.95** | too much |
| 5 | `M0201-Y20-MV10-PLC1` | 0.95 | **0.794** | **too little** |
| 5 | `M0201-Y20-MV10-PLC2` | 0.96 | 0.839 | inside, barely |

Memory already records this as a general law — *a matched draw cannot match turnover on a
weight-varying book* — and M0201 is now its fourth measurement. The two M0201 seeds landing at
0.794 and 0.839 around the same derivation is the clearest evidence that the residual is a draw
property, not a rule defect: **the same rule, the same book, two seeds, 0.045 apart, straddling
the bar.**

### What that costs M0201, concretely

A superseder must be `ok` on **both** axes (phase 2's predicate). `warn` is not enough. So:

```
M0201   M0201-PLC1-MV10      placebo  M0201-Y20-MV10  first-declared  2.27  2.13  refuse  —
M0201   M0201-PLC2-MV10      placebo  M0201-Y20-MV10  first-declared  2.26  2.12  refuse  M0201-Y20-MV10-PLC2
M0201   M0201-Y20-MV10-PLC1  placebo  M0201-Y20-MV10  sibling-stem    0.95  0.79    warn  —
M0201   M0201-Y20-MV10-PLC2  placebo  M0201-Y20-MV10  sibling-stem    0.96  0.84      ok  —
```

Checked directly against the gate, not inferred from the table:

| method | `hardgate.mis_shaped_controls` | D17 |
|---|---|---|
| **M0201** | `['M0201-PLC1-MV10']` | **still refuses** |
| **M0202** | `[]` | **clear** |

So **R4 is served for M0202 and not for M0201**, and the reason is 0.0059 of turnover on one arm.
`lab promote M0201` will still exit 2 on D17 after phase 2 lands. This is the fourth distinct
cause of a missing supersession in this set, and the first that is a near miss rather than a
structural one:

| method | cause | superseded? |
|---|---|---|
| M0047 | — | yes, both |
| M0215 | — | yes, both |
| M0221 | structural: cap-weighted book, 1.95x turnover | **no** |
| **M0201** | **near miss: 0.794 vs the 0.800 bar, one of two seeds** | **one of two** |
| **M0202** | — | **yes, all three** |

## The margins, in `trial_funding.mwr` (SPY TR on the same deposits: 7.188 %/yr)

| book | book `mwr` | old control | old `mwr` | old margin | new control | new `mwr` | **new margin** | move |
|---|---|---|---|---|---|---|---|---|
| `M0201-Y20-MV10` | 9.543 | `M0201-PLC1-MV10` | 10.255 | **−0.712** | `M0201-Y20-MV10-PLC1` | **7.148** | **+2.395** | **widened 3.107, sign flipped** |
| `M0201-Y20-MV10` | 9.543 | `M0201-PLC2-MV10` | 8.065 | +1.478 | `M0201-Y20-MV10-PLC2` | **7.069** | **+2.475** | widened 0.996 |
| `M0202-Y20-HALF` | 12.653 | `M0202-PLC1-HALF` | 11.301 | +1.352 | `M0202-Y20-HALF-PLC1` | **9.037** | **+3.616** | widened 2.263 |
| `M0202-Y20-HALF` | 12.653 | `M0202-PLC2-HALF` | 9.564 | +3.089 | `M0202-Y20-HALF-PLC2` | **8.850** | **+3.803** | widened 0.714 |
| `M0202-Y20-HALF-FAST` | 12.141 | `M0202-PLC1-HALF-FAST` | 11.381 | +0.760 | `M0202-Y20-HALF-FAST-PLC1` | **8.610** | **+3.531** | widened 2.771 |

**All five widened. Not one narrowed and not one reversed.** That is the exact opposite of what
both amendments pre-registered, and it is the largest and cleanest directional miss in this set.

### Does the M0201 spread still straddle the book? **No.**

| | lower control | book | upper control |
|---|---|---|---|
| old (handicapped) | `PLC2-MV10` 8.065 | **`Y20-MV10` 9.543** | `PLC1-MV10` 10.255 — *above the book* |
| new (honest) | `PLC2` 7.069 · `PLC1` 7.148 | **`Y20-MV10` 9.543** | — nothing above |

The straddle is gone. The handicapped pair bracketed the book, which is the signature of a
margin that depends on which placebo you pick; the honest pair sits entirely below it, 2.4
points down, with the two seeds only 0.079 apart. **The sized bond ranking's lead over a blind
book of its own shape is not seed-dependent, and the old reading that it was is an artifact of
the handicap.**

### The pre-registered direction, and why it missed

Both amendments pre-registered the same mechanism in the same words: a control trading 2.25x was
over-paying Gotrade's fees, so an honestly-shaped replacement *pays less, earns MORE, and every
lead NARROWS or REVERSES.*

| arm | pre-registered | observed | |
|---|---|---|---|
| `Y20-MV10-PLC1` earns more than 10.255 | yes | **7.148** | ✗ **−3.11** |
| `Y20-MV10-PLC2` earns more than 8.065 | yes | **7.069** | ✗ **−1.00** |
| `Y20-HALF-PLC1` earns more than 11.301 | yes | **9.037** | ✗ **−2.26** |
| `Y20-HALF-PLC2` earns more than 9.564 | yes | **8.850** | ✗ **−0.71** |
| `Y20-HALF-FAST-PLC1` earns more than 11.381 | yes | **8.610** | ✗ **−2.77** |
| every lead narrows or reverses | 5 of 5 | **0 of 5** | ✗ |
| shape inside 0.80–1.25 on both axes | 5 of 5 | **4 of 5** | ✗ (one at 0.794) |

**The fee argument is simply wrong on this chassis, and the amendment's own
`expected_failure` named the right reason:** *"a blind book of twenty members drawn with the real
book's churn still holds a different twenty."* Halving a control's trade count saves a fee bill
that is small next to what the extra monthly re-draws were *earning* it. The handicapped placebos
were not merely over-paying — they were buying a fresh 989-trade lottery ticket every month over
a 539-symbol survivorship-biased dev store, and on this store that is worth 1 to 3 points a year.
Slowing them to the real book's quarterly cadence takes that away, and the fee saving does not
come close to replacing it.

That re-reads every handicapped margin in this set in one direction: **a sticky, honestly-slow
control is a weaker opponent than a churning one on the dev store, so every lead quoted against
a 2.25x placebo was quoted against an opponent that was too strong, not too weak.** Phases 4 and
7 found the opposite sign on their chassis (M0047 FAIL→PASS, M0215 one widened and one narrowed),
so the direction is chassis-dependent and phase 8 cannot state one rule for the set.

## The 2009–2015 era, where the two methods split

De-funded CAGR over `HIGH_COVERAGE = 2009-01-01 .. 2015-10-16`, reconstructed from each trial's
recorded `curve_json` and `hardgate.trial_deposits` through `lab.walkforward.measure` — the same
path `survivorship_check.era_edge` takes. SPY's own era CAGR is not a recorded row, so it is
anchored on M0202's **published** Y20-HALF edge of +3.2 pts, giving **16.568 %/yr**.
**That anchor is validated by five independent published figures it was not fitted to**, every one
reproduced to rounding: `Y20-HALF-FAST` +4.57 (published +4.5), `N20-HALF` −3.16 (−3.2),
`PLC1-HALF` −1.18 (−1.2), `PLC2-HALF` −0.47 (−0.5), `PLC1-HALF-FAST` +0.78 (+0.7).

| arm | era CAGR | edge vs SPY | old control's edge | margin then | **margin now** |
|---|---|---|---|---|---|
| `M0201-Y20-MV10` | 16.892 % | **+0.32** | | | |
| `M0201-PLC1-MV10` | 16.745 % | +0.18 | | +0.14 | |
| `M0201-Y20-MV10-PLC1` | 12.022 % | **−4.55** | | | **+4.87** |
| `M0201-PLC2-MV10` | 18.423 % | +1.85 | | −1.53 | |
| `M0201-Y20-MV10-PLC2` | 14.538 % | **−2.03** | | | **+2.35** |
| `M0202-Y20-HALF` | 19.768 % | **+3.20** | | | |
| `M0202-PLC1-HALF` | 15.391 % | −1.18 | | +4.38 | |
| `M0202-Y20-HALF-PLC1` | 16.671 % | **+0.10** | | | **+3.10** |
| `M0202-PLC2-HALF` | 16.094 % | −0.47 | | +3.67 | |
| `M0202-Y20-HALF-PLC2` | 17.654 % | **+1.09** | | | **+2.11** |
| `M0202-Y20-HALF-FAST` | 21.140 % | **+4.57** | | | |
| `M0202-PLC1-HALF-FAST` | 17.350 % | +0.78 | | +3.79 | |
| `M0202-Y20-HALF-FAST-PLC1` | 19.088 % | **+2.52** | | | **+2.05** |

**The two methods split, and M0202's split runs opposite to its own whole-window result.**

- On **M0202**, the honest controls are *better* in 2009–2015 than the ones they replace
  (+0.10 vs −1.18, +1.09 vs −0.47, +2.52 vs +0.78), so every era margin **narrows** — 4.38→3.10,
  3.67→2.11, 3.79→2.05 — while the whole-window margin widened. A slow quarterly blind book rode
  the post-2009 recovery better than a monthly re-drawn one; over the full twenty years the
  monthly re-draw's early-years lottery more than paid that back.
- On **M0201**, the honest controls are much *worse* in the era (−4.55 and −2.03 against +0.18 and
  +1.85) and the era margin widens like the whole-window one. The difference is the market-value
  sizing: a blind book sized by market cap in 2009–2015 is a book of whatever large names the hash
  drew, and it trailed SPY badly.

All three M0202 era margins still clear 2 points. All five whole-window margins clear 2 points.

## What the two success conditions now say

### M0201 — `m0201:618-620`

> "Success: `Y20-MV10` keeps a clear gap (**2+ points a year on the deposits**) over **both**
> `OPP-MV10` and the sized placebo seeds, and does not trail SPY in 2009-2015."

| clause | against the handicapped pair | **against the honest pair** |
|---|---|---|
| ≥2 pts over `OPP-MV10` (6.234) | +3.310 ✓ | +3.310 ✓ (untouched) |
| ≥2 pts over placebo seed 1 | `PLC1-MV10` **−0.712** ✗ | `Y20-MV10-PLC1` **+2.395** ✓ |
| ≥2 pts over placebo seed 2 | `PLC2-MV10` +1.478 ✗ | `Y20-MV10-PLC2` **+2.475** ✓ |
| does not trail SPY 2009-2015 | +0.32 ✓ | +0.32 ✓ (untouched) |
| **the condition as a whole** | **FAILED on both seeds** | **PASSES on all four clauses** |

**M0201's own written success condition moves FAIL → PASS on its honest controls.** That is the
second FAIL→PASS in this set, after M0047 — and a stronger one, because M0047's flipped on one
arm and this flips on both seeds at once, by margins of 2.4 points rather than a hair.

**It changes no verdict and unblocks nothing.** `M0201-Y20-MV10` itself is `eligible=0`, failing
`max DD <= 50%` (55.2 %) and `DSR >= 0.90` (0.643 at today's N=164), and neither is a placebo
question. D17 still refuses the method on `M0201-PLC1-MV10`. The success condition passing is a
statement about the *ranking*, not about promotability.

### M0202 — `m0202` hypothesis, final sentence

> "Success …: `Y20-HALF` or `Y20-HALF-FAST` beats total-return SPY on dev with a worst fall under
> the screen's 50% bar, a positive lead over SPY in 2009-2015, and **beats its own same-guard
> placebo seeds by at least 2 points a year on the deposits**."

| clause | handicapped | **honest** |
|---|---|---|
| `Y20-HALF` beats SPY TR | ✓ 12.653 vs 7.188 | ✓ |
| worst fall under 50 % | ✓ 38.0 % | ✓ |
| positive 2009-2015 lead | ✓ +3.20 | ✓ |
| ≥2 pts over placebo seed 1 | **+1.352 ✗** | **+3.616 ✓** |
| ≥2 pts over placebo seed 2 | +3.089 ✓ | **+3.803 ✓** |
| *(same, for `Y20-HALF-FAST`)* | **+0.760 ✗** | **+3.531 ✓** |
| **the condition as a whole** | **FAILED on the better seed** | **PASSES on both arms, both seeds** |

**M0202's success condition also moves FAIL → PASS**, on both guard speeds. The published
sentence — *"That is 1.4 points over the better seed, short of the 2 points written down in
advance … against the average of the two seeds it is 2.2, so it depends on which placebo you pick,
and that is exactly the kind of gap that is not evidence"* — is withdrawn. Against honest controls
the two seeds give +3.616 and +3.803, **0.19 points apart**, and the dependence on which placebo
you pick is gone with the handicap that caused it.

### And M0202's published headline is withdrawn outright

M0202's recorded Analysis leads with:

> "**But a placebo passed it too, and that is the real result.** PLC1-HALF … also passed the
> screen, with a *higher* luck score (0.937) and a smaller worst fall (31%). PLC1-HALF-FAST passed
> as well. The half guard plus the 20-name equal-weight frame is enough to clear the screen with
> no idea in it."

Re-scored at **today's** N for every arm, so the comparison is like for like — the recorded DSRs
were taken at N=133 (old arms) and N=164 (new), and a raw comparison across them is not valid
(`store.published_verdict` with `at=gate(conn)`, `Gate(n=164, policy='methods')`):

| arm | DSR @ run | N @ run | **DSR @ N=164** | eligible @ N=164 |
|---|---|---|---|---|
| `M0202-Y20-HALF` | 0.9143 | 133 | **0.9244** | **yes** |
| `M0202-Y20-HALF-FAST` | 0.8436 | 133 | 0.8592 | no |
| `M0202-PLC1-HALF` *(handicapped)* | 0.9369 | 133 | **0.9449** | **yes** |
| `M0202-PLC1-HALF-FAST` *(handicapped)* | 0.9056 | 133 | **0.9165** | **yes** |
| `M0202-PLC2-HALF` *(handicapped)* | 0.7644 | 133 | 0.7847 | no |
| **`M0202-Y20-HALF-PLC1`** *(honest)* | 0.7701 | 164 | **0.7701** | **no** |
| **`M0202-Y20-HALF-PLC2`** *(honest)* | 0.7560 | 164 | **0.7560** | **no** |
| **`M0202-Y20-HALF-FAST-PLC1`** *(honest)* | 0.6513 | 164 | **0.6513** | **no** |

**Both placebos that cleared M0202's dev screen were handicapped ones. No honestly-shaped
placebo comes near it** — 0.770, 0.756 and 0.651 against a 0.90 bar, a gap of 0.13 to 0.25, far
too wide to be an N artifact. The finding *"a half-size guard on a 20-name equal-weight frame lets
a placebo pass the dev screen with a luck score of 0.937"* is **an artifact of a control that
re-drew its whole book monthly**, and the policy recommendation built on it — *"every future
method in this frame must beat its same-guard placebo by a margin set in advance"* — survives, but
its evidence does not.

What does survive, and should be said plainly: **the half guard's own contribution is still most
of M0202's lead over SPY.** `Y20-HALF` beats SPY by 5.465 points on the deposits, of which
**+3.616 is signal** (over its honest control) and **+1.849 is the frame** (the honest control's
own 9.037 vs SPY's 7.188). The ranking is worth more than the published 1.4 points and less than
the whole lead. Nothing here reopens the survivorship result (the lead halves on `.research-sv`)
or the folds (2 of 4), and both remain the reasons M0202 is not promotable.

## Invariant 12 and `config_digest` safety

Every new arm's `config_text` `params=` line is character-identical to the arm it replaces; the
whole of the difference is `allocator=<M0201>` → `<M0201-A1>` and `<M0202>` → `<M0202-A1>`. No
params dataclass gained a field — which would have moved every recorded `config_digest` on this
chassis — and `test_every_recorded_configuration_still_digests_to_its_recorded_digest` is green.
Both new arms keep their `placebo` / `hash order` draw markers, so both classify `KIND_PLACEBO`
and **are** shape-checked rather than silently exempt.

`M0202-A1`'s lookback rises to `MATCHED_LOOKBACK = 331` (a year of weekly marks before the
previous quarter's re-pick). It moves no window: `candidate_window` floors at the member index's
1996-01-02 and SPY's 331st bar is 1994-05-19. Both trials start 1996-01-03, the same date as the
six arms they sit beside.

## The five supersession declarations, verbatim

| new arm | `supersedes=` | superseded arm's verdict | superseder's own target | fired? |
|---|---|---|---|---|
| `M0201-Y20-MV10-PLC1` | `("M0201-PLC1-MV10",)` | `refuse` | `M0201-Y20-MV10` | **NO — superseder is `warn`** |
| `M0201-Y20-MV10-PLC2` | `("M0201-PLC2-MV10",)` | `refuse` | `M0201-Y20-MV10` | yes |
| `M0202-Y20-HALF-PLC1` | `("M0202-PLC1-HALF",)` | `refuse` | `M0202-Y20-HALF` | yes |
| `M0202-Y20-HALF-PLC2` | `("M0202-PLC2-HALF",)` | `refuse` | `M0202-Y20-HALF` | yes |
| `M0202-Y20-HALF-FAST-PLC1` | `("M0202-PLC1-HALF-FAST",)` | `refuse` | **`M0202-Y20-HALF-FAST`** — a re-point | yes |

All five match the index's supersession mapping row for row. Four fired; the fifth is correctly
withheld, which is phase 2's predicate working as designed — a `warn` superseder does not retire
a `refuse`, and the alternative (letting it) would have retired a 2.27x opponent on the strength
of a 0.79x one.

**The re-aiming worked.** `M0202-PLC1-HALF-FAST` resolves to `M0202-Y20-HALF` on `first-declared`,
because its own stem `M0202-PLC1-HALF` is itself a placebo and `_eligible_targets` steps past it.
Putting the target's whole name in the control's id — `Y20-HALF-FAST-PLC1` — puts the new arm on
`sibling-stem` against `M0202-Y20-HALF-FAST`, the arm it actually controls, and `lab control`
prints the re-point explicitly as `M0202-Y20-HALF-FAST-PLC1 -> M0202-Y20-HALF-FAST`. Both numbers
for the old arm belong in the close-out: **2.25 / 2.20 against `Y20-HALF` as reported, and
2.25 / 1.91 against its true target `Y20-HALF-FAST`.**

## Database

`git hash-object lab/lab.sqlite`, on the live shared database at `/home/miftah/seer/lab/lab.sqlite`:

| point | hash |
|---|---|
| before M0201's run (2026-10-19) | **not captured** — that session was killed before it could report |
| after M0201's run / at this session's start (DB committed on `main` at `fb1af1a`) | `288b7e478ba120145d0aa4189a3756cd75c9a248` |
| **before `lab run M0202 --amend`** | `288b7e478ba120145d0aa4189a3756cd75c9a248` |
| **after `lab run M0202 --amend`** | `994467ca6df0f8aa0e1250e47c51b3638e996761` |
| after `lab control M0201 M0202` (read-only; unchanged) | `994467ca6df0f8aa0e1250e47c51b3638e996761` |

The two M0202 run hashes are the first in this set that are not a crash casualty. Every read-only
query since left the hash at `994467ca…`, including `lab control`, which the memory note warns can
dirty the file by migrating on connect — it did not here.

Provenance of the three new rows, all identical:

- `git_sha = 5e794af48a4d…` — **this phase's own M0202 pre-registration commit**, which is branch
  HEAD at run time. Unlike M0215's rows, there is no cross-phase mix-up to explain.
- `store_fingerprint = 640fc25e5c7b…` (dev store, 539 symbols), `run_at = 2026-10-20T02:35:36+00:00`.
- `method_amendments` M0202 seq 1: `added = 2026-10-19`,
  `source_sha = adb7087f3eb5926e7ca53310270eb3b2eabf449c8bc03313ae3ec05213e084cd`, which is
  `sha256` of the committed method file byte for byte (verified with `sha256sum` against the
  worktree). The pre-registration is the file that ran.

| | |
|---|---|
| Trials added by this session | **3** (`#850`, `#851`, `#852`), all `window='dev'` |
| Trials added by this phase in total | **5** (`#848`–`#852`) |
| Amendments added | **1 by this session** (M0202 seq 1); **2 by this phase** (M0201 seq 1 at `4e5359a`) |
| Both amendments are | **seq 1**, not seq 2 |
| New allocator ids | **`M0201-A1`**, **`M0202-A1`** |
| Luck gate N at run | **164 policy methods, unchanged** — an amendment appends under the existing id |
| M0201 / M0202 status | **unchanged** (`dev-eligible`) — an amendment appends trials, it never moves a verdict |
| **Test-window looks spent by this phase** | **0 — still 4 lifetime** (`trials WHERE window='test'` is 4, before and after) |

`lab test` was never invoked, `SEER_RESEARCH_TEST_STORE` was never read, and `engine/.research-test`
was never named. `lab stage` was **not** run and neither `lab/lab.sqlite` nor `web/data/lab.json`
was committed from this branch (invariant 8 — the coordinator stages the shared DB on `main`).

Walk-forward, re-read at this run: M0202 **2 of 4 folds, pick changed** — unchanged, and the
reason `lab promote M0202` refuses independently of D17.

## Tree

`ruff check engine` — **All checks passed!**
`PYTHONPATH=<worktree>/engine/src pytest engine/tests -q` — **5748 passed, 413 skipped** in 88s
(the skips are `PG_TEST_URL` and the live-store opt-ins; no DB test skipped for any other reason).
`test_lab_methods.py` alone is **1746 passed in 17s**, run before the pre-registration commit as
the plan requires, with the four tests this phase turns on green by name:
`test_every_recorded_configuration_still_digests_to_its_recorded_digest`,
`test_allocator_ids_are_unique_across_methods`, `test_allocator_contract`
(both new allocators return `()` on the history-only path, so the 473-bar fixture never exercises
the 331-bar lookback), and `test_candidate_runs_a_smoke_window`.

## For phase 8

1. **All five leads WIDENED. Zero narrowed, zero reversed.** The pre-registered direction — shared
   word for word by both amendments — is a clean 0-for-5 miss, and the largest in the set.
2. **The fee mechanism is backwards on the dev store.** A 989-trade monthly re-draw over 539
   survivorship-biased symbols *earns* 1–3 points a year more than the fees it burns, so the
   handicapped placebos were opponents that were **too strong**, not too weak. Phases 4 and 7
   found the opposite sign; **there is no single direction for this set** and the close-out must
   say so per chassis.
3. **Two more FAIL→PASS success conditions.** M0201's (2+ pts over both seeds) was failed on both
   handicapped seeds and passes on both honest ones. M0202's (2+ pts over its same-guard seeds) was
   failed on the better seed for both guard speeds and now passes on all four pairings. With
   M0047 that is **three of the set's five methods whose own written bar flips on an honest
   control.** Neither flip promotes anything.
4. **M0202's published headline is withdrawn.** *"A placebo passed the dev screen too, and that is
   the real result"* is false of an honestly-shaped placebo: re-scored at a common N=164, the two
   placebos that cleared (0.9449, 0.9165) are both handicapped, and the three honest ones sit at
   0.770 / 0.756 / 0.651 against a 0.90 bar. `Y20-HALF`'s +5.465 over SPY decomposes as
   **+1.849 frame, +3.616 signal**, not the published ~1.4.
5. **A fourth distinct cause of a missing supersession, and the first near miss.**
   `M0201-Y20-MV10-PLC1` is `warn` at **0.79410** turnover against a 0.80000 bar — 0.0059 short —
   so `M0201-PLC1-MV10` is never retired and **`hardgate.mis_shaped_controls(M0201)` still returns
   `['M0201-PLC1-MV10']`.** R4 is served for M0202 and **not** for M0201.
6. **Invariant 12 held and the miss is left standing.** No seed re-rolled, no weight vector copied,
   no extra arm minted. The two M0201 seeds at 0.794 and 0.839 straddling the bar on the same rule
   is the measurement that says the residual is a draw property of a weight-varying chassis — the
   fourth such measurement in this set, and the first in the *low* direction (phase 3's two were
   1.60x and 1.95x, too high).
7. **The era split is worth a paragraph.** On M0202 the honest controls are *better* in 2009–2015
   (+0.10, +1.09, +2.52 against −1.18, −0.47, +0.78), so the era margins **narrow** (4.38→3.10,
   3.67→2.11, 3.79→2.05) while the whole-window margins widen. On M0201 they are far worse
   (−4.55, −2.03) and both widen. SPY's era CAGR of 16.568 % is derived, not recorded — anchored
   on M0202's published +3.2 and validated against five other published figures it was not fitted
   to.
8. **The M0201 spread no longer straddles the book**, and the two honest seeds are 0.079 apart
   against the handicapped pair's 2.190. "It depends which placebo you pick" was the handicap
   talking.
9. The five `supersedes` tuples are verbatim in the two files as the index's mapping specifies.
   `M0202-PLC1-HALF-FAST`'s two ratio pairs both belong in the close-out: **2.25 / 2.20** against
   `Y20-HALF` as `lab control` resolves it, **2.25 / 1.91** against its true target
   `Y20-HALF-FAST`.
10. `M0201-Y20-MV10-SW`, `M0201-Y20-DV10` and `M0202-N20-HALF` have no control of their own and
    are deliberately left that way — pricing them against matched blind books is new measurement,
    outside R2.
