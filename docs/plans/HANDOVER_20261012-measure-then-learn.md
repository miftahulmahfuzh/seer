# Handover: 2026-10-12 — fix the measuring tape, then let a model rank

**Written by:** a brainstorm session with the owner. No code changed in it.
**Branch state:** `main` at `d9585e1`, clean. No branch, no worktree.
**Predecessor:** the Sera 20261012-1842 synthesis (lab insight 211, "the lab has been losing a
race it never knew it had entered"). Read it first; this handover acts on it.

---

## 1. What the owner asked, and what was decided

The owner asked whether to (1) find another data source, (2) keep running Sera, or (3) start a
machine-learning approach (supervised, RL, CNN, LSTM), and offered to keep a laptop on 24/7.

The recommendation given (the owner then asked for this handover and an `/analyze` session, so
treat it as the direction to build):

- **Step 0 first: fix the measurement flaws** that bias every result, ML included.
- **Step 1: ML, the tabular kind.** One pre-registered gradient-boosted-tree cross-sectional
  ranker, not deep learning or RL.
- **Data:** no new purchase. But the EODHD key expires **2026-11-10**: pull what we still need
  from it (delisted prices for the survivorship check) before then.
- **Sera:** continue, aimed at the portfolio-shape questions it already queued, after Step 0.

Why not deep learning or RL: the limit is signal-to-noise and the number of independent samples
(~500 names × ~20 years monthly, strongly correlated), not model capacity. Gu, Kelly & Xiu (2020)
find that trees and small nets beat linear ranking, but the edge is mostly small-cap and
long-short, before costs. Price-chart CNNs find short-horizon, high-turnover signal that Gotrade
fees eat. RL overfits noisy markets. This machine (Ryzen AI 9 HX 370, 24 threads, Radeon 890M,
**no CUDA**, ~11 GB RAM in WSL) trains trees on the CPU in minutes. A trained model is a small
committed file, and daily inference fits the existing GitHub Actions cron, so **no 24/7 laptop
and no GPD↔Lenovo sync beyond `sync-research-store`**. `scikit-learn` is already a dependency.

The honest caveat, also told to the owner: ML does not change the binding constraint. A long-only
book must beat SPY *and* keep its worst fall ≤ 20% through 2008. Most near misses die on
drawdown, not return. Design §1 is not to be bent (owner revision only).

## 2. Leftover tasks

### Step 0: the measuring tape (do first)

1. **Resize band measured against the whole account.** `engine/src/seer_engine/sim/book.py:561`
   and `:617` trim and add only when `excess × price ≥ RESIZE_BAND × equity`. In a 50-name book
   (2% each) a holding has to drift by half before anything trades, so "weekly vs monthly" arms
   measured nothing. Fix: make the band relative to the holding's own target (or add a
   per-method choice) **without changing past results**. Closed records are frozen, so this needs a
   new rules id or knob, not an edit that rewrites old trials. `RESIZE_BAND` is mirrored in `web/`
   and asserted by a test, and live paper trading uses the same simulator, so decide explicitly
   whether paper changes.
2. **Interest on idle cash.** Cash earns nothing in tests. That understates every rule that steps
   aside by ~1.5–2.5 points a year in risk-off years. Add a T-bill/cash-rate accrual (EODHD yields
   are cached on this PC; see the memory note `eodhd-one-month`). Make it a versioned, explicit
   simulator input.
3. **Survivorship check data restored on this machine** (insight from M0117: "the check that adds
   back the companies that died is missing from this machine"). Pull delisted prices from EODHD
   **before 2026-11-10** and make the check runnable here.
4. **Re-price the near misses under the fixed tape**, as new pre-registered variation twins, never
   by editing old rows: M0030-SAT100 (worst fall 20.6% vs the 20% limit, luck test 0.96),
   M0007-N20-RAW, M0021-B70-RAW, M0020-W-NOSTOP. Also answer Sera's question: were they winning on
   their picking, or on the equal-weight shape?

### Step 1: one tree ranker in the lab

5. A new method family (e.g. `stock-ml-ranker`), id from `lab next-id`, **committed before
   `lab run`** like any method:
   - **Model:** gradient-boosted trees (sklearn `HistGradientBoosting`, or LightGBM if added).
   - **Training:** walk-forward retrains inside the dev window only (ends 2015-10-16), with a
     fixed seed.
   - **Target:** forward 1-month return rank.
   - **Features:** only what we already compute: momentum 12-1, residual momentum, volatility,
     52-week-high distance, dividend events, SEC EDGAR fundamentals, all point-in-time.
   - **Book:** monthly, top-N long-only, Gotrade fees, fractional shares, the owner's real funding
     plan.
   - **Counting:** every hyperparameter setting tried counts toward N for the luck gate.
   - **Never touch the test window** while tuning.
6. If the trees show something, only then consider a small neural net. Deep learning and RL stay
   out of scope.
7. Daily inference: the model artifact is committed, and the nightly Actions job loads it.
   Design this only once a method passes the dev gate.

### Owner side

8. The owner is running `/calculate-assets <id> 1-4-2018` by hand on three methods:
   `M0030-SAT100`, `M0007-N20-RAW` and `M0021-B70-RAW` (runner-up: `M0020-W-NOSTOP`). This is
   curiosity, not a spent test look (memory note `calculate-assets-not-contamination`). All three
   lean on the residual-momentum engine. That is a finding in itself: the lab's best is
   effectively one idea.

## 3. Rules that bind this work

- Lab: pre-register by commit, exit code 2 means the lab refused, `lab stage` after lab changes,
  commit style `lab: M00NN …`.
- Tests never reach production. DB tests need `PG_TEST_URL`.
- Mirror any engine constant change into `web/`.
- Owner-facing text stays plain: no ids or digests on the site.
- Commit and push to `main` once verified.
