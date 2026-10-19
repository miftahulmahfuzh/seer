# The lab's modern-era record is one decision, not a hundred failed ideas

**Measured:** 2026-10-19 · **Trials:** all 824 recorded dev trials, 162 methods
**Era:** 2009-01-01 → 2015-10-16 (82 months, identical for every trial)
**Research store:** `engine/.research` (dev, unmarked) · **Data:** `2026-10-19-shortfall-sweep.csv`
**Method:** `lab.shortfall.measure` driven in one process, with `gate_history` loaded once and
`gate_shares` called per trial. The CLI does the same thing one trial at a time; 824 subprocesses
each re-parsing a 129MB `bars.csv` is ~44 minutes on this one-core machine, and the in-process
loop is minutes. Spot-checked against the CLI: trial 828 reproduces to all eight decimals.
**Nothing was recorded.** The sweep ran against a throwaway copy of the database
(`SEER_LAB_DB`); `lab/lab.sqlite` is byte-identical and git-clean. N did not move, no
test-window look was spent, no trial, insight or status was written by the sweep itself.
**Outcome:** 824 decomposed, **0 refused, 0 errored**. The benchmark against itself
(`REF-SPY-HOLD`, trial 1) returns a gap of exactly `0.00000000`, which is the pipeline's own
proof of correctness. It is excluded from every figure below, leaving 823.

## The short answer

About **3.6 points a year** of a typical **4.5 to 5.4 point** shortfall is the 200-day trend rule
standing in cash. That one number is very nearly the same for every book that carries the rule,
and it has nothing to do with any signal. What is left over for the stock-picking itself is close
to zero. The lab has spent 823 trials measuring ideas, and the biggest single term in its
modern-era record is a constant none of those ideas controls.

## The gate premium is close to a constant

439 of the 823 trials carry the shared SPY 200-day gate. Their era-resolved exposure barely
varies, which is why the premium barely varies:

| | p10 | median | p90 |
|---|---|---|---|
| 2009-2015 exposure | 0.668 | **0.782** | 0.795 |
| gate premium, pts/yr | 3.40 | **3.62** | 5.52 |

It is not an empirical coincidence. SPY total return over the era is 16.60%/yr, and
(1 − 0.782) × 16.60 = **3.62**. The gate holds about a fifth of the book out of a market that
rose almost without interruption for six and a half years, and the bill is arithmetic.

The 384 trials with no shared gate are priced at their recorded whole-window exposure (median
0.882), giving a median cash-drag term of 1.96 pts/yr. That term is real but differently sourced,
and it is reported separately for that reason.

## Where the shortfall goes, and the cut that matters

The residual is defined as `gap + gate premium + fee drag`, so **any error in the modelled fee
term lands in the residual with the opposite sign.** The fee drag is a model — what a run really
paid is not a column in `trials` — and the high-turnover families turn over 60 to 119 times a
year, where the model alone produces 20 to 30 pts/yr. A first reading of the whole population
therefore reported a *positive* median residual and concluded the signals had been ahead all
along. **That conclusion does not survive the cut where the fee model is too small to cause it,
and it is withdrawn here.**

| cut | n | median gap | gate | fees | residual | container share of gap | residual positive |
|---|---|---|---|---|---|---|---|
| all losing trials | 626 | −4.48 | −3.65 | −1.33 | **+0.74** | 121% | 63% |
| turnover < 4/yr | 221 | −4.71 | −3.68 | −0.51 | **−0.11** | 98% | 48% |
| turnover < 1/yr | 56 | −5.38 | −3.73 | −0.20 | **−0.76** | 86% | 32% |
| gated, turnover < 4 | 100 | −5.13 | −3.67 | −0.62 | **−0.33** | 93% | 40% |
| turnover ≥ 10/yr | 141 | −6.47 | −3.62 | −3.81 | **+1.03** | 116% | 62% |

Read the `turnover < 1` row as the honest one: there the fee term contributes 0.20 points and
cannot manufacture anything, the container still explains **86%** of the gap, and the residual is
**mildly negative**. The picking was roughly neutral — not secretly good, and not catastrophic.

Among losing trials below 4 turns a year, the **gate is the larger of the two container terms in
95%** of cases (median 3.68 against 0.51). Fees only dominate in the high-turnover families.

## What this does and does not say

- It does **not** say the gate should be removed. It bought the dot-com and 2008 exits, and it
  helped 22 of 22 variants over the whole window. This measures the premium, not the policy.
- It does **not** say the signals were good. At low turnover the median residual is negative.
  The honest claim is that stock-picking is a small term either way, dwarfed by the container.
- It does **not** re-run anything or spend a method id. Every figure comes from rows the lab had
  already recorded.
- 197 trials (24%) **beat** SPY TR in the era. Only 32% of those carry the gate, against 53% of
  all trials — consistent with the premium being the dominant handicap.
- The fee term is a model throughout. Every conclusion above is stated in the cut where it is
  small, precisely because the residual absorbs its error.

## The question this leaves

Can the insurance be kept without paying ~3.6 points a year of premium in a calm decade? That is
now the best-posed open problem in the lab: it is a containment question, it is worth more than
any single signal the lab has measured, and it is the same shape as the buyback book's
unholdability. Insight 452 is its other half — nine of the rule's eleven exits were false alarms,
and every exit after 2009 was one, because the era contained no bear market to claim on.
