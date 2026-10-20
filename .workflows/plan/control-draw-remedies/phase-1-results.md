# Phase 1 results — Measure the shadow on every chassis, before it is built

**Date:** 2026-10-20
**Verdict:** **GO.** `stop: false`. The shadow is needed on **one** chassis of nine — **M0208** —
and the depth that fixes it is **K = 2**, costing 305 of the 473 available bars.
**Plan set:** `docs/plans/CONTROL_DRAW_REMEDIES_PLAN.md`, phase 1 of 6 (`P1-ROOT-J6WT`)
**Environment:** `main` @ `ab01577`, no worktree. Research store
**`640fc25e5c7b8f422b1c9ea408ab54f100d82a244eacef3e3dcba67b9ffa1170`** (`engine/.research`),
`engine/.venv` (Python 3.11).
**Probe:** `shadow_probe.py`, extracted verbatim from the phase plan (lines 248–858, 611 lines,
27,283 chars), run from the scratchpad and never committed to the repo. Raw output committed
beside this file as `phase-1-probe.txt`; the decomposition's output as `phase-1-decomp.txt`.
(Both are the raw redirected stdout. They carry a `.txt` extension and not `.log` because the
repo's root `.gitignore` ignores `*.log`; the predecessor set's committed artefacts under
`.workflows/plan/honest-control-redraw/insights/` use `.txt` for the same reason.)

```
SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research \
PYTHONPATH=/home/miftah/seer/engine/src \
engine/.venv/bin/python shadow_probe.py > phase-1-probe.log 2>&1      # exit 0, 36s
# committed as phase-1-probe.txt; see the note above on the *.log ignore
```

**No trial was recorded, no method id was spent, no amendment was written, no test-window look was
spent and `lab` was never invoked.** `lab/lab.sqlite` is byte-identical before and after.

> **Every figure in this file comes from one probe run on one store.** The three columns (a) TRUE,
> (b) SHIPPED and (c) K are computed inside a single process against a single loaded `Market`, so
> every ratio here is re-run against re-run and invariant I8 is satisfied by construction. The one
> place this file compares against a number it did not measure is §2, and that comparison is
> labelled there as a **reproduction check, not a comparison**.

---

## 1. The headline, in three sentences

**M0208's estimator reads 304 entries where its real book takes 624 — 0.487×, confirmed to the
unit.** A two-step backward replay reads 461 against 466 on the same decisions, **0.989×**, which
is inside the ±10 % band and costs 305 of 473 bars. **On the other eight chassis the estimator is
a measured no-op** (0.988 to 1.001), two of them *borderline* rather than comfortably clean.

**So the remedy is real, it is cheap, and it is needed in exactly one place.**

---

## 2. The 0.487 cross-check — PASS, on all five figures

The honest-control close-out recorded, over M0208's decisions:
**304 estimated entries against 624 real, 0.487×, uniform across eras at 0.444 / 0.509 / 0.500**
(`docs/plans/HANDOVER_20261019-the-honest-control.md:384-386`), over **169** decisions.

| figure | close-out | this probe | |
|---|---|---|---|
| decisions | 169 | **169** | exact |
| shipped entries | 304 | **304** | exact |
| true entries | 624 | **624** | exact |
| ratio | 0.487 | **0.487** | exact |
| era 1996-2002 | 0.444 | **0.444** (80 / 180) | exact |
| era 2003-2008 | 0.509 | **0.509** (115 / 226) | exact |
| era 2009-2015 | 0.500 | **0.500** (109 / 218) | exact |

**This is a reproduction check and not a shape comparison.** It divides nothing fresh by anything
recorded: it sets a freshly measured ratio beside a previously measured ratio of the same two
quantities. That all seven figures agree *to the unit* is itself evidence the close-out's probe
ran against this same store — which is the only way they could.

---

## 3. The provisional number, settled: **624 is an entry count, and the published figure is right**

The plan set flagged "304 entries against the real book's 624" as possibly conflating **entries**
with **trades**, because `M0208-CGO-N20`'s recorded `trials.trades` is **also 624**. This phase was
named as the one that confirms or corrects it.

**Confirmed. The figure stands, and the remedy's headline number is correct as published.**
This probe's 624 is a *full forward replay* of M0208's own band from 1996 — it counts
`|book(d) − held(d−1)|` at each of 169 decisions and never reads the `trials` table at all. It is
an entry count by construction and it lands on 624.

**But the coincidence is not a coincidence, and that is the finding worth carrying forward.**
`trials.trades` is the number of **closed round trips** (`metrics.strategy_metrics` takes
`n = len(pnls)`, one P/L per closed position). On a book that holds a constant twenty names and
closes almost everything by the window's end, every entry eventually becomes exactly one closed
round trip, so **`trades ≈ entries` by construction on this chassis** — the two numbers agree
because they are measuring nearly the same thing, not because one was mistaken for the other.

The consequence is a caution, not a correction:

> **`trials.trades` cannot be used as an independent check on an entry count for any
> constant-name-count book.** It will agree, and it will agree for a reason that carries no
> information. Phase 6 should state that where it records the figure.

**And a store note:** `M0208-CGO-N20` (trial #677) was recorded on store **`77c37d55`** — neither
this probe's `640fc25e` nor the honest-control set's `b683da41`. Any ratio that divided this
phase's entry count by that trial's trade count would cross **two** store boundaries as well as a
definitional one. No such ratio appears anywhere in this file.

---

## 4. The main table — all nine chassis, whole dev window

Decisions are `dates.prev_session(S)` for every monthly rank session `S` in
1996-01-02 … 2015-10-16, exactly as `book_runner` derives them; M0201/M0202 use their 79 quarterly
re-picks. Ratios are each taken over the decisions that column actually covers.

| chassis | allocator | reads `held`? | decisions | (a) TRUE | (b) SHIPPED | shipped/true | K=1 | K=2 | K=3 | K=K_max | K_max | **verdict** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M0047 | `M0047-A1` | no | 170 | 1610 | 1591 | **0.988** | 1.000 | 1.000 | — | 1.000 | 2 | measured no-op |
| M0201 | `M0201-A1` | yes | 79 | 460 | 423 | **0.920** | 0.966 | 0.947 | 0.946 | 0.946 | 3 | **borderline** |
| M0202 | `M0202-A1` | yes | 79 | 460 | 423 | **0.920** | 0.966 | 0.947 | 0.946 | 0.946 | 3 | **borderline** |
| M0208 | `M0208-A1` | yes | 169 | 624 | 304 | **0.487** | 0.689 | **0.989** | 0.987 | 0.995 | 8 | **shadow needed** |
| M0215 | `M0215-A1` | yes | 170 | 519 | 515 | **0.992** | 0.996 | 0.996 | 1.002 | 1.000 | 8 | measured no-op |
| M0221 | `M0221-A1` | no | 237 | 425 | 424 | **0.998** | 1.000 | 1.000 | 1.000 | 1.000 | 15 | measured no-op |
| M0225 | `M0221-A1` | no | 237 | 425 | 424 | **0.998** | 1.000 | 1.000 | 1.000 | 1.000 | 15 | measured no-op |
| M0227 | `M0227-A1` | no | 225 | 628 | 624 | **0.994** | 1.000 | 1.000 | 1.000 | 1.000 | 15 | measured no-op |
| M0243 | `M0243-A1` | no | 225 | 1308 | 1309 | **1.001** | 1.000 | 1.000 | 1.000 | 1.000 | 8 | measured no-op |

`VERDICT_BAND = (0.90, 1.10)`. K_max is computed at run time from `allocator.lookback(params)`,
never from a table.

### The full K curves, every K with its covered-decision count

| chassis | the curve |
|---|---|
| M0047 | K1 1.000 (161) · K2 1.000 (154) |
| M0201 / M0202 | K1 0.966 (78) · K2 0.947 (77) · K3 0.946 (76) |
| **M0208** | **K1 0.689 (160) · K2 0.989 (153) · K3 0.987 (147) · K4 1.019 (142) · K5 1.004 (138) · K6 1.000 (135) · K7 0.994 (133) · K8 0.995 (130)** |
| M0215 | K1 0.996 (161) · K2 0.996 (154) · K3 1.002 (148) · K4 1.000 (143) · K5 1.000 (139) · K6 1.000 (136) · K7 1.000 (134) · K8 1.000 (131) |
| M0221 / M0225 | 1.000 at every K from 1 to 15 |
| M0227 | 1.000 at every K from 1 to 15 |
| M0243 | 1.000 at every K from 1 to 8 |

---

## 5. The nine verdicts, one line each, with the ratio that decides it

1. **M0047 — measured no-op** (shipped/true = 0.988). Real book cannot read `held`:
   **confirmed by signature and by replay, not by coincidence** — `K=1` reads exactly 1.000.
2. **M0201 — borderline** (0.920). Inside the band, and **0.020 from its lower edge**.
   *This chassis's verdict would flip on a different window.* See §7.
3. **M0202 — borderline** (0.920). Identical chassis, identical numbers to the unit. Same sentence.
4. **M0208 — shadow needed** (0.487). The only chassis outside the band, and outside it by a
   wide margin, not a rounding.
5. **M0215 — measured no-op** (0.992). Reads `held`, and the shadow still changes nothing:
   `held` only *reorders* its raise-picks, it does not gate survival.
6. **M0221 — measured no-op** (0.998). Real book cannot read `held`:
   **confirmed by signature and by replay, not by coincidence.**
7. **M0225 — measured no-op** (0.998). Shares M0221's allocator; same evidence, run separately.
8. **M0227 — measured no-op** (0.994). Real book cannot read `held`:
   **confirmed by signature and by replay, not by coincidence.**
9. **M0243 — measured no-op** (1.001). Real book cannot read `held`:
   **confirmed by signature and by replay, not by coincidence.** The only chassis whose estimator
   reads marginally *high*.

**The four `reads_held: false` families all print 1.000 at K = 1**, which is the manual check the
phase plan asks for. Their **shipped** columns differ from 1.000 by 0.002–0.012, and that residue
is the membership convention of §8, not the shadow.

---

## 6. M0208's K answer — **K = 2**, and the depth phases 2 and 3 inherit

**The smallest K whose estimate reaches ≥ 0.90 of true is K = 2, at 0.989** (461 entries against
466 true on the 153 decisions it covers).

| | |
|---|---|
| chosen K | **2** |
| ratio at that K | **0.989** |
| lookback it costs | `inner 253 + 2 × 26` = **305 bars** |
| cap | 473 |
| **headroom left** | **168 bars** |

**Four reasons K = 2 and not more, stated because phases 2 and 3 are built on this number:**

1. **It is the smallest K that clears**, which is the criterion the exit conditions name.
2. **The curve has converged there.** From K = 2 onward it oscillates inside **[0.987, 1.019]** and
   never improves on K = 2's 0.989 — K=3 reads 0.987, K=4 overshoots to 1.019, K=8 reads 0.995.
   There is no depth that buys accuracy over two steps, so a deeper default would pay lookback,
   coverage and run time for nothing.
3. **Coverage falls with depth.** A depth-K chain does not exist until K decisions have passed:
   K=2 covers 153 of M0208's 169 decisions, K=8 covers 130. Shallower is strictly better here.
4. **Run-time cost.** Each step is one extra band application per decision, repeated for every
   candidate and every walk-forward fold inside `dev.run_registry`.

**Why the jump from 0.689 to 0.989 happens between one step and two, which is the mechanism and
not an accident.** M0208 holds the top 20 and drops a name only when it falls past rank 40. A
one-step replay seeds an *empty* book one decision back, so its stand-in previous book is a fresh
top-20 ranked 1–20 — and almost nothing falls from there past 40 in a single month. Two steps give
the intermediate book one month to drift toward the edge of the band, which is all the band needs
to start evicting at the real book's rate. **This is exactly the defect leftover 3 names, and two
steps is the whole of it.**

**The three-link K chain, restated so no phase has to infer it.** Phase 1 **proposes** K = 2.
Phase 3 **verifies on its own probe and ships its own number** — its `Replay` closes the SPY
200-day switch inside the replay, while this probe's `(b) SHIPPED` column deliberately reproduces
amendment 1's *unguarded* reading, so the two may legitimately differ and that is expected, not an
error. Phase 2 **never sees a K at all**: `depth` is keyword-only with no default and the number
lives in the method file as `SHADOW_DEPTH`.

### No other chassis needs a K

M0201 and M0202 are the only non-no-op verdicts besides M0208, and **their K curves run the wrong
way**: 0.966 at K=1, falling to 0.947 and 0.946. A deeper replay makes their estimate *worse*, so
there is no K to propose and the contract block records `null`. See §7 for why — and note that a
shadow would therefore be an active harm on that chassis, not merely unnecessary.

---

## 7. M0201 / M0202 — borderline, and a second finding inside it

The whole-window ratio is **0.920**, inside the band and **exactly 0.020 above its floor**. Under
the phase plan's own rule (a ratio within 0.02 of either edge), both read **borderline**, and the
required sentence is: ***this chassis's verdict would flip on a different window.***

**The era split is where it actually lives:**

| era | true | shipped | ratio |
|---|---|---|---|
| 1996-2002 | 182 | 169 | 0.929 |
| 2003-2008 | 116 | 120 | **1.034** |
| **2009-2015** | **162** | **134** | **0.827** |

**An estimator can be band-clean whole-window and badly off in the era the owner cares most
about.** 0.827 in 2009-2015 is outside the ±10 % band on its own, and it is the era every
owner-facing judgement in this lab is made in. The whole-window 0.920 averages it away against a
1.034 in 2003-2008.

**This is handed to the coordinator, not absorbed.** Phase 3's three-condition rule resolves to
M0208 and nothing else; M0201's method file belongs to phase 5, and phase 4 has since measured
that **M0201 needs no arm at all** (its control already reads 0.8008× re-run against re-run and
every weight rule makes it worse). So this is a recorded observation with a number attached, and
no phase of this set acts on it.

**And note the direction of the K curve before anyone proposes acting on it later:** depth makes
M0201 *worse* (0.966 → 0.946). The quarterly chassis's true replay carries the whole previous
re-pick's book and does not model the between-quarter membership attrition `choose`'s else-branch
applies — see §9 — so part of this gap is a known limitation of the measurement, biasing **true**
slightly low and therefore the ratio slightly high. The honest reading is that M0201's estimator
is *approximately* right whole-window, demonstrably off in the last era, and **not a case a
bounded backward replay improves**.

---

## 8. The membership decomposition — priced, and corrected

The phase plan prices the membership convention as the gap between **(b) SHIPPED** and
**(c) K = 1**, on the model that K=1 *is* the shipped rule carrying its own membership convention.
**On eight of nine chassis that reading holds and the gap is a rounding error. On M0208 it does
not, and the raw gap overstates the convention by a factor of three.**

| chassis | (b) shipped | (c) K=1 | raw gap — an **upper bound** |
|---|---|---|---|
| M0047 | 0.988 | 1.000 | 0.012 |
| M0201 | 0.920 | 0.966 | 0.046 |
| M0202 | 0.920 | 0.966 | 0.046 |
| **M0208** | **0.487** | **0.689** | **0.202** ← decomposed below |
| M0215 | 0.992 | 0.996 | 0.004 |
| M0221 | 0.998 | 1.000 | 0.002 |
| M0225 | 0.998 | 1.000 | 0.002 |
| M0227 | 0.994 | 1.000 | 0.006 |
| M0243 | 1.001 | 1.000 | −0.001 |

### M0208, isolated properly

A second probe (`m0208_decomp.py`, output in `phase-1-decomp.txt`) runs a third estimator,
`shipped_hist`: `MatchedDrawAllocator._targets` byte for byte, **except** that the previous month
is scored off that earlier date's **own** member list and factor rows instead of today's. The only
thing that differs from `shipped` is the membership convention, so the difference is its price and
nothing else. It also splits every column by whether the previous calendar month had a book.

```
  ALL DECISIONS                     shipped       304 / 624 = 0.487   (169)
                                    shipped_hist  346 / 624 = 0.554   (169)
                                    k1            306 / 444 = 0.689   (160)

  AFTER A CASH MONTH (9 decisions)  shipped        38 / 180 = 0.211
                                    shipped_hist   40 / 180 = 0.222

  AFTER A BOOK MONTH (160)          shipped       266 / 444 = 0.599
                                    shipped_hist  306 / 444 = 0.689
                                    k1            306 / 444 = 0.689     <-- identical
```

**`shipped_hist` and `k1` agree exactly — 306 against 306 — on the 160 decisions both cover.**
That is the proof the isolation is clean: on a decision following a month that had a book, the
*only* difference between the shipped estimator and a one-step backward chain is the membership
convention. Which leaves M0208's 320 missed entries splitting three ways:

| component | entries | share | does a replay close it? |
|---|---|---|---|
| **the cash-month convention** | **140** | **44 %** | **yes** — the chain resets to empty exactly as the real book does |
| **the membership convention** | **42** | **13 %** | **no — no depth closes it** |
| **the freshness defect** (what the shadow is for) | **138** | **43 %** | **yes**, at K = 2 |

**The cash-month component, named, because nobody had separated it before.** M0208's SPY 200-day
switch has the real book in cash for 69 of the window's 238 months. `previous_month_end` does not
know that: it scores a *phantom* top-20 at the previous month end regardless, so on the 9
decisions that follow a cash month the estimator measures churn against a book that never existed
and reads **38 entries where the truth is a full 180-name refill, 0.211×**. Nine decisions carry
**44 %** of the whole window's shortfall. A bounded replay fixes it for free, because the chain
resets to empty on a cash month exactly as the book engine empties a book on an empty target.

### The number phase 6 inherits

> **The membership convention on M0208 is worth 42 entries, 0.067 of ratio — not the 0.202 the
> raw `shipped`-against-`K=1` gap reads.** Its upper bound on every other chassis is in the table
> above, the largest being 0.046 on M0201/M0202 and 0.012 on M0047.

**And the plan's own quoted figure needs one correction.** The validation run's *"0.034 on M0047"*
is M0047's **1996-2002 era** (shipped 461 against true 477 = 0.966), not its whole-window number.
Over the whole dev window M0047's gap is **0.012** — a shipped ratio of 0.988 against a K=1
ratio of exactly 1.000. The brief, the plan index and phase 6's leftover 14 all quote 0.034; the era it describes
should be named, or the figure changed to 0.012.

**This is a second, independent defect and no phase of this set repairs it.** It is not R1's, the
v2 block takes no `members` argument, phase 2 is explicitly forbidden from attempting it, and
phase 6 carries it as a leftover of its own with these numbers attached.

---

## 9. Stated limitations

1. **M0201/M0202's between-quarter attrition is not modelled.** Their true replay carries the
   whole previous re-pick's book forward and does not apply the membership attrition
   `m0197.choose`'s else-branch applies between quarters. This biases the **true** count slightly
   **low**, and therefore the ratio slightly **high**. Their 0.920 is, if anything, optimistic.
2. **Entry counts are not trade counts, and this probe computes no return, models no fee and
   simulates no fill.** Pool attrition, resizes and cash-fill order all move the realised figure at
   run time — M0208's 0.487 estimate landed at **0.73× realised** on the recorded arm. Every number
   here is a shape *input* to `control_draw`.
3. **`lab control`'s verdict is the only thing that settles a shape, never this probe.** Nothing in
   this file is a band verdict; D17 reads recorded trials.
4. **K=1 is not exactly the shipped rule**, which §8 is the correction for. The phase plan's
   framing holds on eight chassis and fails on the one that matters.
5. **One store only.** Everything here is `640fc25e…`. A chassis's ratio on `b683da41…` or on the
   survivorship store is not measured and should not be assumed equal — §3's store note is the
   standing example of what crossing one costs.

---

## 10. The lookback correction

**`m0201.PREV_SPAN = 70`, not 78.** Confirmed in the source at `m0201:346` and `m0202:276`
(`PREV_SPAN = 70  # sessions in a quarter, with room for the longest one in the dev window`), and
recomputed at run time by the probe, which printed `step 70 bars, K_max 3` for both.

So for M0201/M0202: `inner = 331 − 70 = 261`, a depth-K replay costs `261 + 70K`, and **K_max = 3**
(471 bars of 473) — **two** affordable extra quarterly steps, not the one the analysis's dependency
table gave. The analysis was corrected during reconciliation (C2); this run is the authority and it
confirms the correction.

Every other chassis's K_max in §4 was likewise read off `allocator.lookback(params)` at run time
and matches the plan's table exactly.

---

## 11. Contract for phase 2

```yaml
probe_run: "2026-10-20"
store_fingerprint: "640fc25e5c7b8f422b1c9ea408ab54f100d82a244eacef3e3dcba67b9ffa1170"
lookback_cap: 473
verdict_band: [0.90, 1.10]
chassis:
  M0047:  {allocator: M0047-A1, reads_held: false, step_bars: 26, k_max: 2,  decisions: 170, true: 1610, shipped: 1591, ratio: 0.988, k_ratio: {1: 1.000, 2: 1.000}, verdict: "no-op", k_chosen: null}
  M0201:  {allocator: M0201-A1, reads_held: true,  step_bars: 70, k_max: 3,  decisions:  79, true:  460, shipped:  423, ratio: 0.920, k_ratio: {1: 0.966, 2: 0.947, 3: 0.946}, verdict: "borderline", k_chosen: null}
  M0202:  {allocator: M0202-A1, reads_held: true,  step_bars: 70, k_max: 3,  decisions:  79, true:  460, shipped:  423, ratio: 0.920, k_ratio: {1: 0.966, 2: 0.947, 3: 0.946}, verdict: "borderline", k_chosen: null}
  M0208:  {allocator: M0208-A1, reads_held: true,  step_bars: 26, k_max: 8,  decisions: 169, true:  624, shipped:  304, ratio: 0.487, k_ratio: {1: 0.689, 2: 0.989, 3: 0.987, 4: 1.019, 5: 1.004, 6: 1.000, 7: 0.994, 8: 0.995}, verdict: "shadow-needed", k_chosen: 2}
  M0215:  {allocator: M0215-A1, reads_held: true,  step_bars: 26, k_max: 8,  decisions: 170, true:  519, shipped:  515, ratio: 0.992, k_ratio: {1: 0.996, 2: 0.996, 3: 1.002, 4: 1.000, 5: 1.000, 6: 1.000, 7: 1.000, 8: 1.000}, verdict: "no-op", k_chosen: null}
  M0221:  {allocator: M0221-A1, reads_held: false, step_bars: 26, k_max: 15, decisions: 237, true:  425, shipped:  424, ratio: 0.998, k_ratio: {1: 1.000, 15: 1.000}, verdict: "no-op", k_chosen: null}
  M0225:  {allocator: M0221-A1, reads_held: false, step_bars: 26, k_max: 15, decisions: 237, true:  425, shipped:  424, ratio: 0.998, k_ratio: {1: 1.000, 15: 1.000}, verdict: "no-op", k_chosen: null}
  M0227:  {allocator: M0227-A1, reads_held: false, step_bars: 26, k_max: 15, decisions: 225, true:  628, shipped:  624, ratio: 0.994, k_ratio: {1: 1.000, 15: 1.000}, verdict: "no-op", k_chosen: null}
  M0243:  {allocator: M0243-A1, reads_held: false, step_bars: 26, k_max: 8,  decisions: 225, true: 1308, shipped: 1309, ratio: 1.001, k_ratio: {1: 1.000, 8: 1.000}, verdict: "no-op", k_chosen: null}
shadow_needed: [M0208]
redraw_list:   [M0208]
k_proposed:    {M0208: 2}
lookback_after: {M0208: 305}        # inner 253 + 2 * 26, against the 473 cap; headroom 168
m0208_true_entries: 624
m0208_shipped_entries: 304
stop: false
borderline: [M0201, M0202]          # 0.920, inside the band by 0.020; handed to the coordinator
membership_price: {M0208: 0.067, M0047: 0.012, M0201: 0.046, M0202: 0.046, M0215: 0.004, M0221: 0.002, M0225: 0.002, M0227: 0.006, M0243: -0.001}
```

**Phase 2 consumes exactly two things:** `shadow_needed` — **`[M0208]`**, so one chassis gets a v2
adapter — and `lookback_after` — **`{M0208: 305}`**, the number M0208's new `lookback` must return,
asserted against 473. **Phase 2 bakes no K.**

**Phase 3 consumes** `redraw_list`, `k_proposed`, `m0208_true_entries` (**624**) and
`m0208_shipped_entries` (**304**), and anchors its own probe against 624 rather than against the
close-out's literal figure — which §3 has now shown to be the same number anyway.

**`borderline` and `membership_price` are for phase 6**, not for phase 2 or 3. No phase of this set
acts on either.

---

## 12. Invariants

| | before | after |
|---|---|---|
| `git hash-object lab/lab.sqlite` | `607b78cf69c8e4e3a68a1e84c85eedfd1040c754` | `607b78cf69c8e4e3a68a1e84c85eedfd1040c754` |
| test-window looks (`SELECT count(*) FROM trials WHERE window='test'`) | 4 | 4 |

- **I1** — no test-window look. `lab test` was never invoked and `SEER_RESEARCH_TEST_STORE` was
  never read. Looks 4 → 4.
- **I2 / I3** — nothing recorded or frozen was touched. The phase wrote no engine file at all.
- **I4** — the probe's exit code was read directly from a redirected run, never through a pipe.
  Both runs exited 0. No `lab` command was run in this phase, so I4's `lab note` clause is moot.
- **I5** — the database was opened only through `sqlite3 "file:…?mode=ro"`. Hash unmoved, proven
  above.
- **I9 / I10** — the probe carries no allocator state and allocates no lookback; the K=2 proposal
  costs 305 of 473 bars and the arithmetic is in §6.
- **I11** — `engine/.venv/bin/pytest engine/tests` with `PG_TEST_URL` set:
  **6183 passed, 3 skipped** (the three live-store opt-ins) in 134.71s.
  `engine/.venv/bin/ruff check engine`: **All checks passed.**
  `git status --porcelain engine lab web db`: **empty.**

---

## 13. Handoffs

- **The membership convention** — §8. A second, independent defect, **0.067 of ratio on M0208**
  and no more than 0.046 anywhere else, that **no replay depth closes**. Not R1's, not phase 2's,
  carried to phase 6's leftovers. The plan's quoted *"0.034 on M0047"* is that chassis's
  **1996-2002 era**; whole-window it is **0.012**.
- **The cash-month convention** — §8. Newly separated here: 44 % of M0208's whole shortfall, from
  nine decisions, and the bounded replay closes it for free. Worth a sentence in phase 6 because
  it means **the shadow buys more than the freshness fix it was proposed for**.
- **`trials.trades` is not an independent check on an entry count** for a constant-name-count book
  — §3. Phase 6 should say so where it records the 624.
- **M0201/M0202's 2009-2015 era reads 0.827** while the whole window reads a band-clean 0.920 —
  §7. Handed to the coordinator. Phase 4 has since measured that M0201 needs no arm; this is
  recorded, not acted on, and a shadow would make it worse, not better.
- **M0208's K curve is flat, not still climbing, from K=2** — so the 473-bar cap is **not** the
  binding constraint here and widening `labkit.smoke_market` would buy nothing. That closes one of
  the leftovers the phase plan anticipated raising.
- **Everything about weights** belongs to phases 4 and 5, which share no file with this phase.
  Phase 4 has already run and returned `G-bottom` (rule D).

---

## 14. The STOP rule — it did not fire

It would have fired if no affordable K reached 0.90 of M0208's true entry count. **K = 2 reaches
0.989 at 305 of 473 bars, with 168 bars of headroom.** The STOP is not close, and the phase did
not have to choose between it and inventing a deeper K.

`stop: false`. **Phase 2 runs as designed, with `shadow_needed = [M0208]`.** The recommended next
command is the plan's own:

    /implement -f docs/plans/CONTROL_DRAW_REMEDIES_PLAN.md --phase 2
