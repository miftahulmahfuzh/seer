# Handover — 2026-10-19: the placebo is a control, not a constant

**Session:** review of the Sera `20261019-1014` batch synthesis (insight 461). No code written,
no lab rows added, no test look spent.
**Branch:** `main` @ `ad8792d` — pushed. Three skill files were already dirty on arrival
(`.claude/skills/{calculate-assets,explore-and-experiment-new-method,sera-the-explorer}/SKILL.md`);
they are not this session's work, leave them alone.
**Lab:** 828 trials · 271 methods · N = 162 · **test-window looks 4, unchanged.**

This session only read the database. Everything below is a finding about numbers the lab has
already published — to `web/data/lab.json`, to insight 461, and to three memory notes. Two of
those published numbers are wrong in a way that will steer the next batch into the wrong
experiment, so this handover is mostly about retractions.

---

## 1. The 8.2-point "equal-weight handicap" is mislabelled (highest value)

Insight 461 says *"an equal-weight book starts eight points behind before it picks a single
company… that number now explains more of the lab's record than any signal failure."* It is also
memory note `seer-equal-weight-shape-costs-8pts-since-2009`. It rests on exactly one trial:

```
n=828  M0244-PLACEBO30   cagr 31.7  dd 22.8  trades 3687  turnover 15.05  exposure 0.692
params: top=30, sizing='equal', arm='placebo', seed=244,
        screen=FactorParams(rank='momentum', top=1000, mom_n=252, mom_skip=21,
                            pool=50, min_dollar_volume=2e7, min_price=5.0, trend=('SPY',200))
```

It is **not** "thirty index members in equal slices." It is thirty names drawn from the **fifty
strongest 12-1 momentum stocks**, turning over **15× a year**, **behind the SPY-200 gate at 0.692
exposure**. Its 2009-2015 shortfall has three causes that have nothing to do with weighting:

- **The gate.** Out of the market ~31% of the time across a window this same batch (M0245) just
  proved contained **no bear market at all** — every post-2009 exit a false alarm. At ~15%/yr for
  SPY that is roughly 4-5 pts/yr, and cash earned ~nothing post-2008
  (`seer-idle-cash-credit-worth-08-before-2008-only`). **The batch measured the gate's false-alarm
  premium directly and then attributed the same money to equal weighting in the same document.**
- **Turnover.** 15.05 turns/yr at Gotrade fees, ~1.5-3 pts/yr. The batch's own evidence agrees:
  `M0244-STALE30` turned 3.57× and earned the **most** of all six arms (33.3 vs 31.7-33.2).
- **The momentum pool.** A book drawn from the top-50 momentum names and measured from 2009 sits
  on the single worst documented factor event in modern markets — the March 2009 momentum crash.

External check pointing the other way: equal-weight S&P 500 **beat** cap-weight over 2009-2015 by
roughly 2-3 pts/yr in the real world. If a coin-flip book loses 8, equal weighting is the one
ingredient that probably helped.

**What survives.** As a *control for M0244* the placebo is sound — turnover 15.05 against
FRESH30's 15.3 is a genuinely good match, so "+1.5 and +3.9 against the placebo" stands. The error
is lifting one matched pair's absolute shortfall and promoting it to a universal constant.
**It is a good control and a bad constant.**

**Do:** run the decomposition — the same placebo with `trend=None`; again at STALE-like turnover;
again on a non-momentum pool. Prediction: the residual attributable to weighting is near zero. If
it dies, correct in all three places: `MEMORY.md` line 70 + the note, insight 461, and the
`/sera` synthesis page (`update-stale-sera-methods-page`).

## 2. M0248's control trades 3.6× more than the book it controls

```
M0248-D100   cagr 42.3  dd 73.2  trades 1117  turnover  6.73
M0248-R      cagr 32.8  dd 54.2  trades 4074  turnover 21.60   <-- the "blind draw"
```

This is the exact sticky-vs-redrawn trap the lab wrote down after M0230
(`seer-placebo-sticky-vs-redrawn`: *"line the trade counts of all arms up against each other"*).
The control pays ~15 extra turns of fees a year. The claim now standing in
`seer-buyback-signal-lives-in-cheap-repurchases` — *"all six arms beat the blind draw by 3.6-13.5
pts, so the buyback signal itself is real"* — is quoted against a handicapped opponent. The gap is
probably still real; the margin is overstated by something like 1.5-3 pts/yr.

**Do:** re-draw R at the real book's turnover before that sentence is relied on again.

## 3. M0251's follow-up has the wrong bar written down

```
M0251-HOLD         29.7  dd 55.0   (buy and hold)
M0251-LADDER       29.4  dd 33.2
M0251-LADDER-CASH  30.0  dd 29.9
M0251-SPY-200      31.5  dd 18.9   <-- the plain 200-day rule
```

The ladder loses to buy-and-hold outright, and even after the cash credit it is beaten by the
dumb 200-day gate on **both** return and drawdown. "The signal is real, the switch wasted it" is
well supported by MIRROR (24.5%) — the inverse losing money is the strongest evidence in the
batch — but the queued weight-dial variant must clear **31.5 / 18.9**, not buy-and-hold.
**Do:** write that bar into its pre-registration hypothesis so it is not re-litigated after the run.

## 4. The headline on the live site now contradicts the newest measurement

Insight 461 calls cheap buybacks *"the strongest modern-era result this lab has recorded"* and
*"making it holdable is now the single most valuable problem in the lab."* The `calculate-assets`
run over 2018-04 → 2026-10 (recorded in `seer-buyback-signal-lives-in-cheap-repurchases`) found
M0248's ladder **monotone and backwards** out of sample: pure buyback +21.1% at a 38.3% fall,
every unit of cheapness added costing return *and* depth, down to +11.2% at 60.1%. SPY on the same
deposits: +20.4%.

So the discount leg is a dev-window artefact and only the **pure-buyback** end beat SPY, by 0.7
pts. This is also what the start-date objection predicted: an 11.4-pt 2009-2015 lead measured from
near the March 2009 bottom by a book that falls 55-85% in 2008 is the drawdown read forward, not
an edge the drawdown spoils.

**Do:** correct the `/sera` synthesis before the next batch reads it as a direction. The sleeve
idea below should be built on **pure buyback**, not cheap buyback.

## 5. Smaller, still worth doing

- **The piped-exit-code bug is a repeat offender.** M0245's duplicate note is the *second*
  occurrence; the first is already memory (`seer-lab-note-double-append-from-grep-exit-code`).
  Filing it as feature-wish 460 and moving on buys a third. One-line fix: check `PIPESTATUS`, or
  don't pipe. Separately, `lab note` should recognise an identical body before writing it.
- **Credit cash the short rate in backtests** — correct for accuracy, but scope the claim.
  "Every rule rejected for stepping aside was judged too harshly" is true of 20-year verdicts and
  false of 2009-2015 ones, where T-bills paid nothing. It will not reopen a single modern-era
  rejection; say so, or the next batch expects reversals.
- **Promote to a standing rule: compose screens sequentially, never by averaging scores.** Each
  ranking earns at its own extreme and averaging flattens both (M0248: 10.5 against 13.3 and
  19.0). The configuration that won was sequential. This is a lab rule, not a batch finding.
- **The regime point belongs in the design doc, not a batch note.** 2009-2015 contains no bear
  market, so *every* defensive feature the lab has ever judged on that window was scored on a
  window with no claim to pay out. That biases every rejection of every protective rule, well
  past the 200-day gate.
- **Insight 461 says "Seven next ideas queued (M0252-M0257)"** — that is six ids and six listed
  ideas.

## 6. The one constructive idea, revised

A standalone cheap-buyback book cannot reach §1: at 60% even after an industry cap it is 2.4× over
the 25% bar. As a **sleeve** the arithmetic works, and given §4 it should be the *pure-buyback*
book:

```
25% pure-buyback (38% fall) + 75% gated core (14% fall)  ->  ~20% blended fall
```

That clears the bar with room, and it composes this batch's two surviving findings — the buyback
signal and the rehabilitated gate — instead of queueing them separately. Worth running before
M0239's industry cap, which the updated memory note now explicitly closes off for the cheap half.

---

## The task for the next session

**Build the tooling that makes §1 and §2 impossible to repeat.** Two pieces:

1. **A shortfall decomposition** — given any trial, split its gap to SPY TR over an era into
   *gate premium* (exposure × era return), *fee drag* (turnover × cost model), *pool* and
   *residual weighting*. Today the lab reports one number and the residual gets named after
   whichever ingredient the author was thinking about. The components are already in the row
   (`exposure`, `turnover`, `curve_json`, `spy_tr_cagr`).
2. **A control-shape check** — when a method declares a placebo/control arm, compare its trade
   count and turnover against the arm it controls and refuse or loudly flag a mismatch. M0230 and
   M0248 are the two cases it would have caught; `seer-placebo-matched-to-a-books-exact-shape`
   and `seer-placebo-sticky-vs-redrawn` are the written rules it would enforce.

Fold in the `PIPESTATUS` / duplicate-note fix from §5 as a small phase.

**Rules that bind** (CLAUDE.md): closed records are frozen — do not reformat `lab.sqlite` rows,
past reports, or `backtest/registry.py`. Commit the lab by index through `lab stage`, never by
pathspec (`seer-lab-stage-commit-needs-the-index`); every database commit includes
`web/data/lab.json`. Tests must not reach production; DB tests need `PG_TEST_URL`. Escape `%` as
`%%` in argparse help.

**Done means:** a decomposition command exists and is run on trial 828, the 8.2 figure is either
confirmed with its components named or retired from the memory note, insight 461 and the `/sera`
page; a mismatched control arm fails loudly; and `lab note` cannot double-append.
