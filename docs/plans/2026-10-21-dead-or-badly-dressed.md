# Dead, or only badly dressed? The back catalogue's reversed arms, split

Read-only. Committed `lab/lab.sqlite` (887 dev trials, journal to 522), copied and opened
read-only, never in place. No lab command that journals was run. No method id spent, no backtest,
no research store, no test-window look: still 4. Journal content digest over rows 1-500 unmoved at
`04af4687…1673ed` (recipe: `docs/runbooks/journal-content-digest.md`).

Feature-wish 492 asked for one report: for every method that ran a reversed arm beside its
straight one, print what the **opinion** is worth apart from what the **habits** cost, and say
which of the lab's rejected timing rules are dead and which were only badly dressed. It is now
`lab dressing` (`engine/src/seer_engine/lab/dressing.py`).

```
direction = (straight - reversed) / 2                 what the opinion knows, one-sided
toll      = (straight + reversed) / 2 - endpoint      what the arrangement costs
ratio     = direction / |toll|                        >= 1 is badly dressed, < 1 is dead
```

---

## 1. It reproduces all three answers the lab derived by hand

| hand answer | where | recomputed | agrees |
|---|---|---|---|
| M0254 floor 50: +1.76 / −2.51 / **0.701** | insight 490 | +1.76 / −2.51 / **0.701** | exactly |
| M0254 floor 0: +3.59 / −5.26 / **0.682** | insight 490 | +3.59 / −5.26 / **0.682** | exactly |
| M0265: 0.9 against 2.75, ratio **0.33** | insight 511 | 0.90 (money) and −2.78 (paper) | see §2 |
| M0267: opinion **+2.38** one-sided, toll ≪ M0265's | commit `3bdc3a9` | **+2.42**, toll −0.70 at 13 flips | to rounding |

Two details the reproduction turns on, both now pinned in `engine/tests/test_lab_dressing.py`:

- **Floor 0 is M0251-LADDER, priced against M0254-HOLD.** `M0254-FLOOR00` and `M0251-LADDER`
  recorded a byte-identical curve (asserted), and the hand decomposition reached across the
  method boundary for the endpoint, taking the **child's** re-run of the always-invested arm
  rather than `M0251-HOLD`, whose window starts thirteen months earlier. Against `M0251-HOLD` the
  same pair reads 0.657, not 0.682. The endpoint ladder therefore prefers an exactly-matching
  window over a sliced one even when the sliced one is in the pair's own method — which is the
  preference M0254's own file argues for in prose: *"a paired difference across two windows is
  not a paired difference."*
- **M0267's +2.38 came from a separate price-level pipeline.** The third-fund study already
  reproduced it at +2.41 and called the 0.03 rounding; off the recorded curves it is +2.42, and
  the two-sided gap is 4.83 against insight 515's published 4.84.

## 2. The 0.33 everyone has been quoting is a cross-column ratio

The lab records two return columns and they disagree in sign on thirty trials
(`seer-lab-has-two-return-columns`). Insight 511's `0.9 / 2.75 = 0.33` takes its numerator from
the money column and its denominator from the paper column:

| M0265-ROTATE vs M0265-MIRROR | knows | costs | ratio |
|---|---|---|---|
| on the prices (de-funded CAGR) | +0.55 | −2.78 | **0.199** |
| on the owner's money (MWR) | +0.90 | −2.85 | **0.315** |
| the published mix | +0.90 | −2.78 | 0.33 |

Both published halves reproduce in the column they came from. Inside one column the answer is
0.20 or 0.32. **Dead either way** — the verdict never depended on it — but 0.33 should not be
re-quoted, and `lab dressing` cannot produce it: each column owns both of its halves.

## 3. The chassis toll is a per-flip price, and now it always prints its flip count

| pair | toll (prices) | round trips | turnover/yr | pts per unit of churn |
|---|---|---|---|---|
| M0251-LADDER (cash ladder) | −5.81 | 55 | 5.44 | 1.07 |
| M0254-FLOOR50 (cash ladder) | −2.80 | 0 | 2.76 | 1.01 |
| M0265-ROTATE (fund swap) | −2.78 | 80 | 11.59 | 0.24 |
| M0267-GATE (fund swap) | −0.70 | 13 | 1.57 | 0.44 |

Seven times M0267's churn buys four times its toll. **2.75 is not a constant** and quoting it
without a flip count will mis-price the next method that leans on it. Note also that the price per
unit of churn is **not** equal across habits: sitting in cash costs ~1.0 points per unit, swapping
funds ~0.2-0.4. Two different habits, two different prices.

`trades` alone would not do: M0254's floor arms and M0267's half arms record `trades 0` while
turning over 2.76 and 0.83 a year, because they trim one holding forever instead of closing out
(`seer-partial-weight-book-records-zero-trades`). The report prints both and divides by both.

---

## 4. The sweep: 28 reversed-arm pairs across 23 methods

Pairs are found **structurally**, from recorded `config_text`: two arms of one method that differ
in exactly one reversing setting and in nothing else. `control_shape.role_of` decides *which* of
the two is the mirror -- its first rung, and it carries 17 of the 28; the structural flag carries
5, a `mode='mirror'` value 2, prose 1, and 3 stay `unresolved` and say so -- but it never decides
*which pairs exist*. Measured over all 833 recorded candidates, `role_of` calls every mirror of
M0251, M0254, M0265 and M0267 a `treatment`, because they open `Falsification:` — a phrase that
must not be added to `ROLE_CONTROL_OPENERS`, which feeds D17 on nine dev-eligible methods.

### The first finding is a gap in the method, not in any method

**Only 6 of the 28 pairs can be priced at all.** The other 22 belong to methods that never
registered an always-invested, opinion-free arm, so their *direction* is measurable and their
*toll* is not. A reversed arm on its own is half an experiment: it proves the signal carries
information and says nothing about whether the arrangement can afford it, which is exactly the
distinction wish 492 exists to draw.

> **Actionable:** any future method that registers a mirror should register a never-leave arm
> beside it. It costs no method id — it is one more variant inside the same pre-registration —
> and without it the lab cannot tell a dead rule from a badly dressed one.

### Nothing in the catalogue is badly dressed in both columns

| verdict | pairs | |
|---|---|---|
| **split** | 2 | M0267-GATE, M0267-GATE-HALF |
| **dead** | 4 | M0251-LADDER, M0251-BINARY, M0254-FLOOR50, M0265-ROTATE |
| unpriced, signal present | 11 | M0058, M0069, M0083 (×2), M0088, M0093, M0185, M0188, M0191, M0192, M0208 |
| no signal | 7 | M0118, M0179, M0184 (×2), M0185-S20, M0194, M0243 |
| backwards (the mirror won) | 4 | M0057, M0071, M0091, M0210 |

Every timing rule the lab *can* price is dead by arithmetic, not by bad luck. The
volatility-risk-premium family (M0251 → M0254 → M0265) sits at 0.20-0.70 on every rung of every
dose, and because dilution halves the direction and the toll together the ratio is invariant down
the ladder — which is the thing that closes the family rather than inviting a gentler setting.

### M0267 is the one case worth re-reading, and the two columns disagree about it

| M0267-GATE vs M0267-MIRROR | knows | costs | ratio | verdict |
|---|---|---|---|---|
| whole window, on the prices | +2.42 | −0.70 | **3.472** | badly dressed |
| whole window, on the money | +0.52 | −0.53 | **0.981** | dead |
| 2009-2015, on the prices | +0.37 | −0.57 | 0.643 | dead |
| 2009-2015, on the money | +0.66 | −0.56 | **1.176** | badly dressed |

That is insight 515 showing up as a verdict rather than as a caveat. On the prices the trend gate
moved into the fund choice is the cheapest chassis the lab has found for it, worth three and a
half times what it costs. On the owner's deposit schedule it is a wash, because everything it was
worth landed in 2000-2002, before four fifths of his money existed. Collapsing that to either word
would throw away the only thing about M0267 worth knowing, so the report prints `split` and names
both numbers.

The 2009-2015 row is the inverse and is new: in the era the owner's money actually lived in, the
money column reads 1.18 and 1.01 — the only rows in the whole catalogue above the bar on the
column he spends. It is one era of one method and it is a hypothesis, not a result; the honest
next step is a fold majority, not a new method id.

### Eleven unpriced pairs whose signal is real

`M0093-LO5-S60-N20-T` (+3.04 prices / +2.96 money) and `M0208-CGO-N20` (+3.15 / +2.93) beat their
own mirrors by more than M0267's gate beats its own, in both columns; `M0058-ILL20-T`
(+1.76 / +2.32) and `M0192-S-N20` (+1.05 / +1.78) beat it on the money and not on the prices.
They are stock screens rather than timing rules, so "the habit" for them is
the gate and the churn rather than cash, and pricing it needs a 2×2 — the pair run with the habit
on and with it off. Several methods (M0184, M0185) already recorded both halves of that square.
That is a clean follow-up wish and it needs no new data either.

### Four pairs are backwards

`M0057-HIGH-N20`, `M0071-WEEK-T`, `M0091-LO5-N20-T` and `M0210-RESID-N20` lose to their own
registered opposites in **both** columns. Those are not weak signals; they are signals read upside
down, and each is a one-line amendment away from being tested the other way up. Three of the four
already registered the winning side as their control arm, which is how the orientation ladder's
`role` rung knew which way round to read them; `M0210`'s pair is `unresolved` (both arms open
"Contrast:"), so its sign is the one of the four a reader should check by hand.

---

## What was built

- `engine/src/seer_engine/lab/dressing.py` — the module. Pure arithmetic over recorded rows: no
  store, no backtest, no market, no clock. **Journals nothing on any path** (asserted), writes no
  trial, moments, funding, provenance, insight, fold or status, and never reads `window = 'test'`.
- `lab dressing M0254 | M0254-FLOOR50 [--against …] [--csv …]` and `lab dressing --all [M…] …`
  in `engine/src/seer_engine/commands/lab.py`.
- `engine/tests/test_lab_dressing.py` — 55 tests. The rules on synthetic rows; the three hand
  answers pinned against the committed lab; the blend construction checked against the one blend
  the lab actually recorded (`M0265-BLEND`, 0.0015 pts); the money column checked against every
  one of the 761 recorded `trial_funding.mwr` figures (worst gap 0.019 pts, one-signed on 736);
  and `lab.sqlite`'s sha256 asserted unmoved by reading it.
