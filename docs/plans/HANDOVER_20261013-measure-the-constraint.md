# Handover: 2026-10-13 — walk-forward on every run, then learn the fall, not the pick

**Written by:** a review session with the owner. No code changed in it.
**Branch state:** `main` at `260292d`, clean. No branch, no worktree.
**Predecessor:** `HANDOVER_20261012-measure-then-learn.md` and the measure-then-learn plan set
(landed `29f9cd7`). Read that first; this handover reacts to its result.

---

## 1. What the owner asked, and what was decided

The owner read the measure-then-learn summary and pushed back on one sentence in it: that "ML did
not change the binding constraint" after trying **one** method. He is right, and the claim was
too broad. He then asked what to do next.

### What M0130 actually licenses

M0130 tested one model family (`HistGradientBoostingRegressor`), one label (21-session forward
return rank), one universe (top 20 of a large-cap screen), long-only, equal weight, and seven
price features plus four EDGAR factors **that the lab already computes and that had each already
failed on their own**. A tree can only recombine what it is given.

Gu, Kelly & Xiu's edge is mostly small-cap and long-short, before costs — exactly the regime
M0130 excludes. So M0130 confirmed a null where the literature predicted one.

The honest sentence is: *gradient-boosted recombination of the lab's existing signals, in large
caps, long-only, after Gotrade fees, adds no picking skill.* Not "ML does not work."

### What the lab's own record says (measured this session, read-only on `lab.sqlite`)

394 dev trials with a recorded return:

| Bar | Trials clearing it |
|---|---|
| Beats SPY TR | **256 (65%)** |
| Max DD <= 20% | **92 (23%)** |
| Both | 69 |
| Fully eligible | 22 (across 11 methods) |

Beating SPY on return is not hard on dev — two thirds of everything does it. **The fall is what
kills methods there.**

Out of sample it inverts. All four test looks failed on `beats SPY TR`, and not narrowly:

| Candidate | Return | SPY TR | DSR dev -> test |
|---|---|---|---|
| M0021-B70-RAW | +42.5% | +306.1% | — |
| M0029-B70-RAW-FRAC | +118.1% | +306.1% | — |
| M0022-W-TV14 | +79.2% | +167.0% | 0.912 -> 0.136 |
| M0002-REL-85 | +94.8% | +167.0% | 0.854 -> 0.204 |

A 65%-hit-rate dev advantage that vanishes out of sample is the signature of **selection**, not of
a model lacking capacity. More architectures add more selection, and N now counts methods (145
rows, 80 at the last gate reading), so every added method raises the DSR hurdle for everything we
might ever promote.

Also measured: of the 302 dev trials breaching 20%, the worst year is 2008 for 103 of them (avg DD
53.9%), **but 2011 for 51 and 2015 for 50**. The drawdown problem is broader than one crash, so it
cannot be gated away by a 2008-shaped rule.

### The direction decided

Stop adding model families. Do (1) then (2) below; (3) and (4) are cheap and can run beside them.

## 2. Leftover tasks

1. **Make walk-forward part of every `lab run` verdict.** `engine/src/seer_engine/lab/walkforward.py`
   exists and already gates `lab promote` (`majority of folds`), and `lab walkforward` is a report —
   but it is **not** part of `lab run`. Methods are still judged on one 20-year dev average and then
   handed a single out-of-sample observation, spent *after* the promote decision. The fold record
   would have flagged M0022 and M0002 before they burned test looks. Decide explicitly whether a
   lost fold majority makes a method ineligible or only annotates it; closed trial rows are frozen,
   so this is a new column/report path, never an edit of recorded rows. This is the highest-value,
   lowest-cost item and should land before another test look is spent.
2. **Learn the fall, not the pick.** The constraint that binds is drawdown, and the lab has exactly
   one risk control — the SPY 200-day gate — which has never been improved on. Re-point the model at
   *exposure* instead of *selection*: label on forward downside (drawdown over the next quarter, or
   realised downside vol) rather than forward return rank, and let the output size the book.
   `lab/tree_rank.py` (832 lines, 20 tests) already has the walk-forward, point-in-time,
   no-look-ahead plumbing and a real-store fit in ~11.6s; only the label and the head change.
   Pre-register as a new method id from `lab next-id`. Every hyperparameter setting tried counts
   toward N.
3. **Price the short-horizon chart model instead of building it.** Before any CNN/LSTM work, compute
   the turnover such a model would need and run that turnover through the fee schedule the simulator
   already prices (`sim/costs.py`). That is a number that either kills the idea or does not, for
   about an hour of work. Deep learning and RL otherwise stay out of scope: the limit is
   signal-to-noise and ~500 names x 20 years of strongly correlated monthly samples, not capacity.
4. **Append a correcting insight to the lab journal.** Insight 217 (M0130) ends "Learning tools do
   not fix this lab's real problem, the 2008-sized fall, and here they did not even pick better
   stocks." The second clause is supported; the first is an overreach from one configuration.
   Insights are append-only — add a newer one narrowing the claim to what M0130 tested, in the
   owner's plain language, no ids or digests.

### Not in scope

- No new data purchase. The rule stands: survivorship-free data only after a method clears
  dev-eligible **and** a majority of walk-forward folds **and** a positive 2009-2015 edge. Nothing
  has. The EODHD alias top-up is already exhausted (phase 4 returned 0 calls).
- The §1 real-money bar does not move. Owner revision only.

## 3. Rules that bind this work

- Lab: pre-register by commit, `lab next-id` for the id, exit code 2 means the lab refused,
  `lab stage` after any lab change, commit style `lab: M00NN ...`.
- `lab.sqlite` migrates on connect even for a read — query it read-only
  (`sqlite3 'file:lab/lab.sqlite?mode=ro'`) or restore by path afterwards and commit only `lab.json`.
- Closed records are frozen: past trials, registry rows and backtest reports are never edited or
  reformatted.
- Never peek at the test window. Four looks are spent; treat the rest as a budget.
- Tests never reach production. DB tests need `PG_TEST_URL`.
- Mirror any engine constant change into `web/`, where a test asserts the two agree.
- Owner-facing text stays plain: no ids, digests or code.
- Commit and push to `main` once verified.
