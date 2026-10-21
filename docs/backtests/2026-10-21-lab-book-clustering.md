# How many distinct books does the lab actually contain?

A pairwise residual-correlation pass over every recorded dev curve in the lab, 2026-10-21.
Read-only, against a copy of `lab/lab.sqlite`. No method id spent, no test look, nothing written.

## What was measured, and with which functions

Every function below is `lab/hardgate.py`'s own. Nothing was re-defined.

| step | function reused |
|---|---|
| the benchmark curve and the trial it came from | `hardgate.geometry` |
| comparability of two curves (D10, price fingerprint) | `hardgate.mismatches` |
| a funded trial's deposits in curve units | `hardgate.trial_deposits` |
| de-funded month-on-month returns | `hardgate.monthly_returns` |
| market share removed (OLS on SPY's monthly return) | `hardgate.residual` |
| Pearson over shared months, `MIN_KIN_MONTHS`, flat guard | `hardgate.correlation` |
| the bar | `hardgate.KIN_CORRELATION = 0.85` |

The 397,386 pairs were computed as one vectorised matrix and spot-checked against
`hardgate.correlation` on 400 random pairs: **max absolute difference 1.2e-15**.

**(D10) excluded nothing.** All 893 dev curves and the benchmark carry price fingerprint
`5451195fd552`; `hardgate.mismatches` returned zero problems, so **0 of 397,386 pairs** were
refused as incomparable. No pair fell below `MIN_KIN_MONTHS` either. One curve is not
measurable — `REF-SPY-HOLD` itself, whose residual against its own fit is flat by construction.

## Two things had to be corrected before the clustering meant anything

**1. Single linkage chains, so "one giant cluster" is an artefact.** At 0.85 the transitive
closure puts 147 of 171 methods in one component — but only **12.1%** of the pairs inside that
component actually clear 0.85, the internal median is 0.712, and the minimum is **−0.372**: two
members of the "same" cluster that move in opposite directions. That is a chain, not a book.
Every count below is therefore reported both ways: single linkage (what (D14)'s one-hop rule
implies if you made it transitive) and complete linkage (a cluster forms only when **every**
pair in it clears the bar).

Complete linkage here is greedy — seed on the highest-degree method, add any method that clears
the bar against everything already in the cluster, repeat. The partition is therefore not
unique and the cluster count is an approximation; the *memberships* are exact in the sense that
every pair inside every cluster really does clear the bar.

**2. Twenty-seven recorded curves are byte-identical across methods.** 893 dev curves, **843
distinct**. 27 curves appear under more than one method — 77 rows across 59 methods — because a
method's control or host arm is often another method's book verbatim (`M0215-CTRL` =
`M0262-NATIVE` = `M0168-CTRL` = six others; `M0182-SPY200` = `M0205-SPY200`). Their
`config_digest` differs (the allocator id is in it), so the digest cannot detect this; the curve
can. Those 107 variant pairs are dropped from every cross-method maximum. Doing so moved the
count by 3 clusters, so it was not what drove the result — but the measurement is now honest.

## The cluster count at four thresholds

Method-level link = the highest residual correlation between any pair of their dev variants
(exactly (D14)'s "best twin" semantics), identical curves excluded.

| bar | single linkage | largest | singletons | complete linkage | largest | singletons |
|---|---|---|---|---|---|---|
| 0.80 | 9 | 162 | 7 | **52** | 28 | 27 |
| **0.85** | **19** | **147** | **15** | **67** | **21** | **40** |
| 0.90 | 36 | 125 | 28 | 79 | 18 | 49 |
| 0.95 | 74 | 57 | 60 | 103 | 14 | 75 |

**At the lab's own bar: 67 clusters, the largest holding 21 methods, 40 of them singletons.**
Not six books — but not 171 either. Twenty-seven clusters hold more than one method and between
them account for 131 of the 171; the remaining 40 methods are each alone.

## The clusters, in plain words

Fourteen clusters hold three or more methods. "gated" is all/mixed/none — how many members run
the SPY 200-day trend filter in every variant, in some, in none.

| # | n | med ρ | gated | holds up<br>without<br>the gate | what the members actually do |
|---|---|---|---|---|---|
| C01 | 21 | 0.965 | 17/3/1 | 17/21 | **Residual momentum behind the trend gate** — rank on market-model residual return, hold ~20 names, monthly. Plus the real-fee fractional re-runs, the size tilts, the stop-loss, shortfall and single-name brakes, and the width sweeps. Holds **M0021, M0022, M0029**. |
| C02 | 17 | 0.944 | 7/3/7 | 4/17 | **The safety switch itself, wearing a dividend book** — half the members only vary how the 200-day exit leaves and re-enters (M0245, M0113, M0136, M0261); the other half are dividend-raise books that happen to sit behind it. |
| C03 | 15 | 0.934 | 9/4/2 | 13/15 | **Twelve-month price momentum behind the trend gate** — plain momentum, overnight-only momentum, drizzle momentum, volatility- and drawdown-braked momentum, the relative-strength book, and the capital-gains-overhang book. Holds **M0002** and **M0208**. |
| C04 | 10 | 0.958 | 8/2/0 | 5/10 | **The earnings-day jump book** — buy big caps after a high-volume up gap, hold two months; plus its filtered, size-weighted, sector-capped, brake-fitted and gate-cadence descendants. Holds all three firings: **M0072, M0092, M0258**. |
| C05 | 9 | 0.942 | 4/2/3 | 3/9 | **Timed index exposure, and the dividend-raise book beside it** — SPY or a leveraged index above its trend line priced on its own, a VIX-term-structure gate, and four dividend-raise books of the same shape. |
| C06 | 5 | 0.975 | 0/0/5 | 5/5 | **Ungated large-cap books that barely trade** — index-shaped holdings under different rebalancing triggers, an account-drawdown brake, the mildest-drawdown names, and an index that skips new members. |
| C07 | 4 | 0.879 | 2/2/0 | 1/4 | **Dividend calendar and board discipline** — buy before the pay month, prefer boards that declare on schedule, buy confident corporate actions; and a low-correlation screen that lands in the same place. |
| C08 | 4 | 0.922 | 0/0/4 | 4/4 | **Ungated construction and clock experiments** — hold-the-shortlist vs resample it, the market-shape weighting, where the monthly top-up goes, and a stand-down by calendar rather than chart. |
| C09 | 4 | 0.944 | 1/2/1 | 3/4 | **Coskewness** — own the stocks that crash hardest with the market, in four framings. |
| C10 | 4 | 0.890 | 3/1/0 | 2/4 | **Lottery and salience avoidance** — rank big members on their biggest recent daily move, their worst standout day, or their own residual bounce. |
| C11 | 3 | 0.944 | 2/1/0 | 2/3 | **One-off corporate events** — the laggard of a pair, a raise landing on an earnings jump, a first-ever dividend. |
| C12 | 3 | 0.911 | 0/2/1 | 3/3 | **Bond-sensitive stocks** — rank members by sensitivity to the 10-year Treasury yield, three framings. |
| C13 | 3 | 0.919 | 1/1/1 | 1/3 | **Market-shaped books under a breadth or cadence switch** — hold SPY and step aside on breadth, the same gate read on different calendars, a size-weighted book tilted to raisers. |
| C14 | 3 | 0.991 | 0/1/2 | 3/3 | **Share-count shrinkers** — buybacks, cheap buybacks, and buybacks as a tilt inside a market-shaped book. |

The forty singletons are the lab's genuinely lonely books — no other method in the lab moves
with them at 0.85. Among them: the SEC-panel pickers (M0005, M0153), the split calendar (M0241),
the illiquidity premium (M0058), the dividend-streak and high-yield books (M0102, M0163), the
VIX-sensitivity book (M0191), the sticky placebo (M0193), the turn-of-month books (M0052,
H-P7A-F11), sector rotation (H-P7A-F3), RSI(2) swing trades (H-P7A-F7) and dual momentum
(H-P7A-F2). That list is the honest evidence that the search *is* reaching new ground.

## The sceptic's finding: most of the apparent sameness is the gate

Two books that both sit out the same crashes correlate even after SPY's share is removed,
because **a trend gate is a non-linear function of SPY that a linear fit cannot subtract**. Split
the 395,331 cross-method variant pairs by whether each side runs the SPY-200 filter:

| | n | median ρ | ≥ 0.85 |
|---|---|---|---|
| gated × gated | 109,336 | **+0.633** | 5.13% |
| gated × ungated | 198,085 | +0.156 | 1.40% |
| ungated × ungated | 87,910 | **+0.064** | 0.87% |
| *(calibration)* variants of the **same** method | 2,055 | +0.778 | 39.37% |

Two unrelated gated methods reach +0.633 — most of the way to the +0.778 that two variants of
one method reach. Two ungated methods reach +0.064, which is nothing.

**So the clustering is substantially measuring "has a gate / does not", and that is said
plainly here because it is the more interesting finding.**

### How much is the gate? Subtract it and see

Supplementary, and **not the lab's rule**: a second regressor was added — the lab's own recorded
gate-alone book `F1-SPY-SMA200-M` (H-P7A-F1, trial #4), its stage-1 residual projected out. By
Frisch–Waugh this is the two-regressor OLS on [SPY, the gate].

| | median ρ, all cross-method pairs | ≥ 0.85 | gated × gated median |
|---|---|---|---|
| SPY removed (the lab's own residual) | +0.288 | 2.31% | +0.633 |
| SPY **and the gate** removed | **+0.070** | **0.66%** | **+0.146** |

Removing one shared ingredient collapses the lab's apparent co-movement by three quarters. The
complete-linkage count goes 67 → 96 clusters at 0.85, singletons 40 → 64.

The per-cluster version of that test is the "holds up without the gate" column above — the
largest share of each cluster that stays together once the gate is subtracted:

- **Real books**, intact without the gate: C01 (17 of 21), C03 (13 of 15), C06, C08, C12, C14 (all).
- **Largely gate artefacts**: C02 (4 of 17), C05 (3 of 9), C07 (1 of 4), C13 (1 of 3).
- **Half and half**: C04 (5 of 10).

## The decisive cross-tab

Four test-failed methods, three buy-signal firings. Figures are the highest residual correlation
between any dev variant of each pair — the "are these the same book" question. (D14) itself is
stricter: it compares only against the *tested* variant, so its numbers are lower or equal.
`hardgate.behavioural_kin` was run directly on the copy to confirm each verdict below.

**The four test looks were spent on two books, not four.**

| | M0021 | M0022 | M0029 |
|---|---|---|---|
| M0021 | — | +0.927 | **+0.992** |
| M0022 | | — | +0.925 |
| **M0002** | +0.731 | +0.764 | +0.726 |

M0021/M0022/M0029 are one book (0.93–0.99; M0021 and M0029 are 0.992 apart, and M0029 *is*
M0021's child). M0002 sits 0.73 away from all three — a genuinely second book. **The lab's
0-for-4 out-of-sample record is 0-for-2 on distinct books**, and three of those looks bought
nearly the same information.

**The three buy-signal firings are one book, and it is not a failed one.**

| firing | vs M0002 | vs M0021 | vs M0022 | vs M0029 | best | ≥ 0.85? |
|---|---|---|---|---|---|---|
| M0072 | +0.646 | +0.746 | +0.673 | +0.763 | +0.763 | **no** |
| M0092 | +0.716 | +0.729 | +0.701 | +0.758 | +0.758 | **no** |
| M0258 | +0.646 | +0.692 | +0.636 | +0.703 | +0.703 | **no** |

`hardgate.behavioural_kin` returns **zero twins** for all three — none of them is kin of a
failure by behaviour. But against each other: **M0072 × M0258 = +1.0000**, M0072 × M0092 =
+0.975, M0092 × M0258 = +0.975.

So the hypothesis in the brief — *every firing sits in a cluster that already contains a
failure* — is **false**, and the truth is a different problem. All three firings are cluster C04,
which contains no test-failed method; the nearest failure is 0.76 away, comfortably under the
bar. But the three are not three signals. `M0258-M-B0` is literally `M0072-Z2-RAWRANK`'s curve
with `band=0` (the identical `ZParams`, a no-op band), and both M0092 and M0258 record M0072 as
`parent_id`. **The owner is shown three live buy signals and owns one book.** The lineage was
already declared; what is new is that the behaviour confirms it, and that the site presents it
as three.

**M0208 is refused for a real reason, not a chained one.** `hardgate.behavioural_kin` returns
exactly one twin: *M0002 (M0208-CGO-N20 moves with M0002's tested M0002-REL-85 at 0.90 residual
correlation)*. Its two *eligible* arms read 0.897 and 0.882 against that same tested variant —
both independently above the bar, so the one-twin sentence is not what refuses it. Worth
recording precisely: once the gate is also subtracted they fall to 0.843 and 0.840, just under
0.85. That is a measurement, not a recommendation; the lab's rule is stage 1 and stage 1 refuses
it.

**How much of the lab is within reach of a failure?** At 0.85, **37 of 167** methods (22%) move
with at least one test-failed book. Not 74 of 78 — most of the dev-eligible refusals are (D4),
(D12), (D17) or the folds, not (D14).

## The behavioural_kin defect, quantified — and it has hidden nothing

`behavioural_kin` returns one `Twin` per *failed method*, naming the best-correlated variant, so
a refusal computed on one variant is applied to all of them.

- The gate prints **84** Twin sentences across the 37 refused methods.
- The full pairwise matrix holds **270** variant-level links at or above 0.85 — the report
  understates the matrix **3.2×**.
- Those 37 methods carry 184 dev variants. **54 (29%) are clean against every test-failed book.**

That 29% looks alarming and is not. Restricted to **eligible** arms — which is what (D11) reads
when it asks whether the variant `lab promote` would pre-register clears the bar on its own:

- 48 eligible variants, **3 clean (6%)**.
- **0 methods** are refused purely on an ineligible arm.
- Exactly **1 method** has most of its eligible arms clean — M0047 (2 of 3) — and both clean
  arms are its placebos (`M0047-PLC1-MV10`, `-PLC1-MV20`, marked eligible); its idea arm
  `M0047-EQ` reads 0.965, and `behavioural_kin` names it against all three of M0021, M0022 and
  M0029 (0.96 / 0.92 / 0.97).
- The same applies to M0208: its four clean variants are its hash placebo, its mirror and two
  placebo arms. Both idea arms are over the bar.

**Recommendation: change nothing in the gate.** The one-twin sentence is a reporting weakness,
not a decision weakness — every method (D14) refuses has its idea arm independently above the
bar. If the sentence is ever improved, the honest form is "k of n variants above the bar, best
X", which costs no behaviour change. This was not implemented here.

## The straight answer

**The lab is searching more broadly than it looks, and spending its looks more narrowly than it
should.**

- Not six books. At its own bar the lab holds **67 clusters, 40 of them singletons**, and the
  biggest genuine book has 21 members. Raise the bar to 0.95 and it is 103 clusters. The "one
  component of 147" reading is single-linkage chaining and should not be quoted.
- But the ideas are not what binds the big clusters. **The SPY-200 gate is**: two unrelated
  gated books already correlate +0.633 after the market is removed, two ungated ones +0.064, and
  subtracting the gate-alone book collapses the lab-wide median from +0.288 to +0.070. The
  200-day gate is doing more to make these books look alike than any idea in them.
- The real narrowness is in the **spending**, not the searching. Four test looks bought two
  books. Three live buy signals are one book, declared as parent and child. That is where the
  budget leaks.

Two things follow that cost no method id. First, **the firings panel should collapse a lineage
to one row** — three rows for M0072 and its two children overstates what is live. Second,
**before a test look is spent, check it against the books already spent**: 0.992 between M0021
and M0029 was knowable before M0029's look, from curves the lab already held.

## Integrity

- **Snapshot.** Measured against a `.backup` copy taken 2026-10-21 11:22 — 893 dev curves,
  171 methods, trials through `n=893`, journal through insight 500. The sibling session
  `explore-M0270` landed M0270 (rejected) into `lab/lab.sqlite` at 11:32, taking it to `n=903`
  and insight 528. Nothing here reads those rows; the counts above are as of the snapshot.
- The first stage of the measurement is `docs/backtests/2026-10-21-lab-book-clustering.py`
  (reads a copy, writes a pickle, verifies itself against `hardgate.correlation`).
- Worked read-only against a `.backup` copy. The working tree is clean; nothing was written to
  `lab.sqlite`, and no lab command was run against it.
- Journal content digest over insight rows 1–500, recipe in `docs/runbooks/journal-content-digest.md`,
  computed before and after on both the original and the copy:
  `04af46875bef3498f783a3154265b760cd2c4471d018a740d82e0113721673ed` — unchanged, matching the anchor.
- Test-window looks: **4 trials, 4 methods** — unchanged.
- No `lab survivorship`, no `lab costs`, no backtest, no research store.
