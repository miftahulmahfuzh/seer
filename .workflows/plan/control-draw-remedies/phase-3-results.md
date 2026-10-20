# Phase 3 results — M0208's honest control, re-drawn under the shadow

**Date:** 2026-10-20
**Verdict:** **GO, and band-clean.** `M0208-CGO-N20-PLC2` reads **0.955x trades / 1.027x
turnover** — `ok` on both axes, the first arm in M0208's three-arm supersession chain to clear
D17's match band. **M0208's floor became a number, and the number is lower than the floor was:
3.7 points a year, not "at least 4.3".**
**Plan set:** `docs/plans/CONTROL_DRAW_REMEDIES_PLAN.md`, phase 3 of 6 (`P1-ROOT-E9QL`)
**Environment:** `main`, main checkout, no worktree, `engine/.venv` (Python 3.11).
Research store **`640fc25e5c7b8f422b1c9ea408ab54f100d82a244eacef3e3dcba67b9ffa1170`**
(`engine/.research`, 539 symbols, 2,490,793 bar rows).
**Rule:** `control_draw` v2 via `shadow_selection` (phase 2's), allocator id **`M0208-A2`**,
**`SHADOW_DEPTH = 2`**, lookback **305** of 473.
**Pre-registration commit:** `280aca6`. **Lab commit:** `6d3b14f`. **Trial: #860.**
**Recorded source sha:** `023cfd2f9bfa016972ff3226c47b3a9c800faa8387f90b8f4994dc538f157aaa`.

**No test-window look was spent.** `lab test` was never invoked, `lab promote` was never invoked
and `SEER_RESEARCH_TEST_STORE` was never read. Looks **4 → 4**.

---

## 1. The gate still refuses M0208, and this phase bought no promotion

`hardgate.check` short-circuits at the first failing clause, in this order:

    fold count -> fold majority -> the promoted variant's own folds -> survivorship drawdown
      -> D17 -> kin

M0208 is the **only** one of the nine methods the honest-control set re-drew whose operative
clause is D17: it is the only one that clears the fold majority (3 of 4), its promoted variant's
own folds and the survivorship drawdown bar. And the clause immediately behind D17 is the **kin
rule**: `failed_kin("M0208")` returns `('M0002',)`, and M0002 has already spent and **failed** its
one look at the test window. M0208-CGO-N20's market-neutral monthly return moves with M0002-REL-85
at 0.90 residual correlation, above the 0.85 line.

So clearing D17 changes the **refusal message** and not the **answer**. Read live through
`store.connect_readonly` after the run, verbatim:

```
mis_shaped_controls: ()
failed_kin: ('M0002',)
check: LabError: M0208 is not promoted: M0002 already read test-failed, and it is kin -- same
family ('stock-capital-gains-overhang'), an ancestor through parent_id, an ingredient one of its
variants runs (or that ingredient's family or ancestry, D12), or a tested book one of its variants
moves with (D14). By behaviour (D14): M0002 (M0208-CGO-N20 moves with M0002's tested M0002-REL-85
at 0.90 residual correlation) -- at or above 0.85 ... There is no override
```

`mis_shaped_controls` is **`()`** after this phase. The plan predicted it read
`('M0208-HASH-N20',)` before it — amendment 1's `CGO-N20-PLC` declared it superseded, but a `warn`
arm retires nothing, so the refusal stayed live — and that reading is the plan set's, not this
phase's: an attempt to re-measure it on a throwaway copy with trial 860 removed did not take, and
the number is not asserted here on the strength of a failed reconstruction. **What this phase did
measure is the post-run value, which is the one the gate acts on, and it is `()`. That is the
whole of what D17's clearance buys.** Nothing in this phase makes M0208 promotable, nothing
here is an argument that it should be promoted, and no sentence written by this phase may be read
as implying one. What the phase buys is an honest control: a number where there was a floor.

---

## 2. The free pre-run probe — GO, with all three anchors exact

`m0208_shadow_probe.py`, run from the scratchpad and never committed; raw output committed beside
this file as `phase-3-probe.txt`. Exit **0**, 36s including the store load. No trial, no database,
no fee model, nothing written.

| anchor | required | measured | |
|---|---|---|---|
| **0** — `control_draw.previous_decision_date` == `m0208.previous_month_end` | 0 mismatches | **0 mismatches over 238 decisions** | exact |
| **1** — forward replay of the real band | phase 1's `m0208_true_entries` = 624 | **624** | exact |
| **2** — the K=1 ladder *without* the switch guard | amendment 1's shipped estimator = 304 | **304** | exact |

Anchor 0 is what makes `shadow_selection`'s calendar usable on this chassis without handing it one:
the NYSE-derived date and SPY's own grid date are the same session on every decision of the dev
window. Anchor 2 reproducing 304 to the unit is the proof the ladder is measuring the shipped rule
and not something else.

### The K ladder, guarded, over all 169 live decisions

| K | entries | ratio | 1996-2002 | 2003-2008 | 2009-2015 | lookback |
|---|---|---|---|---|---|---|
| 1 | 446 | 0.715 | 0.656 | 0.743 | 0.734 | 279 |
| **2** | **592** | **0.949** | **0.856** | **0.991** | **0.982** | **305** |
| 3 | 587 | 0.941 | 0.850 | 0.947 | 1.009 | 331 |
| 4 | 593 | 0.950 | 0.867 | 0.991 | 0.977 | 357 |
| 5 | 591 | 0.947 | 0.889 | 0.960 | 0.982 | 383 |
| 6 | 593 | 0.950 | 0.900 | 0.973 | 0.968 | 409 |
| 7 | 596 | 0.955 | 0.894 | 0.978 | 0.982 | 435 |
| 8 | 595 | 0.954 | 0.900 | 0.960 | 0.991 | 461 |

Coverage is **169 of 169 at every depth** — the chassis's own grid reaches back to 1993, so no
chain is truncated even at K = 8.

**`SHADOW_DEPTH = 2`, this phase's own number.** It is the smallest K clearing 0.90, which is the
criterion, and the ladder is flat above it: K = 3…8 sit in **[0.941, 0.955]** and the best of them
(0.955) beats K = 2 by 0.006, which buys nothing and costs 156 more bars of lookback and three
times the run time per decision. Three reasons beyond "smallest": the curve has converged; the
lookback cost is linear in K and the headroom is not free (168 bars spare at K = 2, 12 at K = 8);
and every step is an extra band application per decision, repeated for every candidate and every
walk-forward fold inside `dev.run_registry`.

### Where this phase's K ladder differs from phase 1's, and why both say 2

Phase 1 proposed K = 2 at **0.989**; this phase measures K = 2 at **0.949**. The two are different
ladders and the plan said in advance they might differ:

- **This phase's `Replay` closes the SPY 200-day switch inside the replay** — a cash month reseeds
  the shadow to empty. Phase 1's `(b) SHIPPED` column deliberately reproduces amendment 1's
  *unguarded* reading, so its K-chains reset on a scoring failure but not on a gate-off month.
- **Phase 1 scored its ratio over the decisions a full depth-K chain covers** (153 at K = 2 of 169);
  this phase scores over all 169, because its chains are never truncated.

**Both ladders independently name K = 2 as the smallest depth clearing 0.90 and both show the
curve flat above it.** The number shipped is this phase's, per the three-link chain.

### The switch guard is worth 142 entries on its own, confirming phase 1's decomposition

Unguarded K = 1 reads **304**. Guarded K = 1 reads **446**. The difference, **142 entries**, is the
cash-month convention alone — phase 1's independent decomposition priced it at **140** (the 9
decisions following a cash month reading 38 entries against a truth of 180). Two different methods,
two entries apart. The second step of drift then carries 446 → 592.

So M0208's 320 missed entries split as phase 1 measured them: **44 % cash-month convention, 43 %
freshness, 13 % membership** — and the shadow closes the first two together, the cash-month half
falling out of `shadow_selection`'s loop with no special case (phase 2 §3). The membership
convention is **not** closed and is not this phase's: it stays phase 6's leftover at **0.067 of
ratio**.

---

## 3. The shape — band-clean on both axes

`lab control M0208`, verbatim:

```
    method  control             kind     controls       resolved by     trades x  turnover x  verdict  superseded by
    ------  ------------------  -------  -------------  --------------  --------  ----------  -------  ------------------
    M0208   M0208-HASH-N20      placebo  M0208-CGO-N20  first-declared      4.41        5.20   refuse  M0208-CGO-N20-PLC2
    M0208   M0208-CGO-N20-PLC   placebo  M0208-CGO-N20  sibling-stem        0.73        0.76     warn  M0208-CGO-N20-PLC2
    M0208   M0208-CGO-N20-PLC2  placebo  M0208-CGO-N20  sibling-stem        0.96        1.03       ok  —

recorded dev trials 856 -> 856; test-window looks 4 -> 4. Nothing was written, no research store
was opened and no method id was minted.
```

### The band arithmetic, and which axis bound

`control_shape.band_verdict` is **inclusive** and `WARN_BAND = (0.80, 1.25)`. Against the book's
624 trades and 3.06140631 turnover:

| axis | low bar | high bar | measured | ratio | headroom |
|---|---|---|---|---|---|
| trades | **≥ 500** (0.80 × 624 = 499.2) | ≤ 780 | **596** | **0.9551** | 96 above the floor, 184 below the ceiling |
| turnover | **≥ 2.4492** | **≤ 3.8268** | **3.14472** | **1.0272** | 0.6955 above the floor, 0.6821 below the ceiling |

**Neither axis bound.** The plan derived the band-clean trade window as **500 … 752** (the high side
set by turnover, since turnover-per-trade runs 1.0362× the book's on this equal-slot chassis). The
arm landed at 596, near the middle of that window, with the turnover ratio sitting almost exactly
at parity. The realised turnover-per-trade came out at `3.14472 / 596 = 0.0052764` against the
book's `0.0049061`, a factor of **1.0755** — a little higher than the 1.0362 the recorded pair
implied, which is why the turnover ratio (1.027) sits above the trade ratio (0.955) rather than
below it. The direction of that gap was anticipated; its size was slightly under-estimated and it
cost nothing.

### Re-run against re-run, inside one sweep on one store (invariant I8)

**This matters here more than in any previous phase of the set.** `M0208-CGO-N20` (trial 677) was
recorded on store **`77c37d55`**; both its honest controls were recorded on **`640fc25e`**. The
`lab control` table above therefore divides a control measured on one store by a book measured on
another — the defect the coordinator promoted to a first-class finding (twelve distinct
fingerprints across 859 trials; ten of the fifteen recorded `-PLC` comparisons cross a boundary;
it already moved M0201's 0.794 to 0.8008).

So the ratio was recomputed from scratch: all three arms run in **one** `dev.run_registry` call
against **one** loaded Market on `640fc25e`, funded explicitly as `lab.runner.run_method` funds
them. Raw output committed beside this file as `phase-3-onesweep.txt`.

| arm | re-run trades | re-run turnover | recorded trades | recorded turnover | agree? |
|---|---|---|---|---|---|
| `M0208-CGO-N20` (store `77c37d55`) | 624 | 3.061406 | 624 | 3.06140631 | **to every digit** |
| `M0208-CGO-N20-PLC` (`640fc25e`) | 455 | 2.313011 | 455 | 2.31301057 | **to every digit** |
| `M0208-CGO-N20-PLC2` (`640fc25e`) | 596 | 3.144720 | 596 | 3.14472 | **to every digit** |

**The store boundary costs exactly zero on this chassis**, and the money agrees too — the re-run
book earns `0.1387873198052101` against the recorded `0.13878731980521`. So the re-run-against-re-run
ratios are **0.9551 / 1.0272**, identical to the recorded ones, and `lab control`'s reading for
M0208 is a true comparison rather than a cross-store artefact. **That is now measured, not
assumed** — which is the point. A chassis declaring only SPY and reading members through a screen
is insensitive to the store rebuilds that move other books; a chassis holding the names themselves
need not be, and phase 6 should not generalise this zero.

*(Phase 1's reproduction of the close-out's 304 / 624 / 0.487 and its era split, and this phase's
anchors 1 and 2 against the same figures, are **reproduction checks and not shape comparisons**:
they set a freshly measured quantity beside a previously measured quantity of the same thing. No
figure in this file divides anything fresh by anything recorded.)*

---

## 4. The money — and the prediction, scored honestly

All four arms on the owner's real funding (237 deposits, +5,000,000 IDR on the 25th, 148,087.98
USD total), against SPY TR's **7.188 %/yr** on the same deposits.

| arm | trial | trades | turnover | MWR | margin over the book |
|---|---|---|---|---|---|
| `M0208-CGO-N20` — the book | 677 | 624 | 3.061406 | **13.879 %** | — |
| `M0208-HASH-N20` — the handicapped control | 680 | 2749 | 15.909535 | 8.007 % | 5.871 pt (meaningless: 4.41× / 5.20×) |
| `M0208-CGO-N20-PLC` — amendment 1 | 853 | 455 | 2.313011 | 9.532 % | 4.346 pt (provisional: 0.73× / 0.76×) |
| **`M0208-CGO-N20-PLC2`** — **amendment 2** | **860** | **596** | **3.144720** | **10.130 %** | **3.749 pt — measured** |

Trial 860's full line: `return +36218.3% vs SPY TR +25724.5%, CAGR +34.7%, maxDD 21.6%, PF 2.87,
Sharpe 0.79, MAR 0.47, DSR 0.891 (N=165), worst year 2011 −7.0%`.

### Scoring the pre-registered hypothesis

**The shape half was right in every particular, including its own caveats.**

| predicted | landed | |
|---|---|---|
| 560 – 700 trades | **596** | hit |
| 0.90× – 1.12× trades | **0.955×** | hit |
| 2.85 – 3.55 turnover | **3.1447** | hit |
| 0.93× – 1.16× turnover | **1.027×** | hit |
| band-clean on both axes | **yes** | hit |
| "the high side is the live risk, not the low one" | landed mid-window, closer to the low side | the framing was right, the asymmetry over-stated |
| "the realised count will NOT rise in proportion" | entries 304 → 592 is **1.95×**; trades 455 → 596 is **1.31×** | **hit, and it is the prediction's most falsifiable part** |

**The money half reversed, and the pre-registration named that reversal as admissible.** It
predicted the control would earn **less** than 9.532 % (somewhere in 8.5 – 9.5 %) because it pays
more of Gotrade's fees, so the margin would **widen** from 4.346 to 4.4 – 5.4 points and "at least"
would come off a *larger* number. The control earned **10.130 %** — more, not less — and the margin
**narrowed** to **3.749 points**.

The `expected_failure` block's fourth clause is the one that fired, written before the run:

> *"the direction reverses and the honest control earns more rather than less; the lab has measured
> that an honest control's effect on a margin is not a bias of known sign but an arbitrary one, so
> this is the outcome the prediction is least entitled to be surprised by."*

**So the headline finding is not the one the set expected to buy.** "At least 4.3 points a year"
was presented as a floor, with an argued mechanism behind it (a control paying the full fee bill
must earn less). **The mechanism is wrong, and the floor was not a floor — it was simply the number
one badly-shaped draw produced.** The fairly shaped draw produces 3.7. The extra churn cost the
control fees and still left it ahead of the under-trading one, which says the fee bill between 455
and 596 trades is worth less than the arbitrary variation in what a blind draw happens to hold.

**The pre-registered promise of a lead of at least 2 points is still met, comfortably.** The arm is
not drawn again: a second re-draw would only ever be justified by the shape missing its band, never
by the margin coming out wrong, and the shape is clean.

Two smaller readings worth keeping: the new control's **worst fall is 21.6 %**, shallower than both
the book's 24.9 % and the old control's 22.2 %, and its **PF is 2.87** against the book's 3.13 — so
on the risk axes the fairer opponent is a slightly *harder* one than the old control was, not a
softer one.

---

## 5. The owner-facing sentences, moved

The arm reads `ok` on both axes, so the step-6 condition was met and `lab note` ran. Rehearsed
first on a copy of the database through `SEER_LAB_DB` — `--dry-run` does **not** protect `lab note`
(`commands/lab.py`: only `lab test` and `lab gate-probe` read `args.dry_run`; `_note` commits
inside `with conn:` regardless) — and the live hash was confirmed unmoved by the rehearsal.

**`methods.verdict`, before:**

> ... and a meaningless book **by at least 4.3 points a year - provisional, and a floor rather than
> a measurement**, because even the fairest control the lab can draw here still trades a quarter
> less than the book; the earlier figure of 6 points came from a control that traded four times as
> often and is withdrawn.

**`methods.verdict`, after:**

> ... and a meaningless book of the same shape **by 3.7 points a year - measured now rather than a
> floor**, because the fairest control the lab can draw finally trades as often as the book does;
> **the earlier figures of 6 points and of at least 4.3 are both withdrawn.**

A dated `### 2026-10-20` analysis section was appended (3,930 characters), after — not replacing —
the earlier 2026-10-20 section that set the floor. `methods.analysis` is append-only, so the floor
sentence stays on the record with its reasoning and the new section says which half of that
reasoning was wrong. Verified by heading sweep: the section appended **once**, not twice (I4).

The note carries no ids, digests, code or jargon (I12).

---

## 6. Database and invariants

| | before the phase | after the phase |
|---|---|---|
| `git hash-object lab/lab.sqlite` | `607b78cf69c8e4e3a68a1e84c85eedfd1040c754` | **`7a701f11c3f069513149779e696c52a7c570c279`** |
| trials | 859 | **860** (`select n` contiguous, 1…860) |
| test-window looks | **4** | **4** |
| M0208 `method_amendments` | seq 1 (2026-10-19) | seq 1 (2026-10-19) **and** seq 2 (2026-10-20) |
| M0208 status | dev-eligible | dev-eligible (an amendment never moves a verdict) |
| luck-gate N | 164 | **165** (policy methods) |

The hash at each point it could move, recorded as I5 asks:

| command | before | after | moved? |
|---|---|---|---|
| step 0, step 1 (probe), targeted + whole suite | `607b78cf` | `607b78cf` | no |
| `lab run M0208 --amend` | `607b78cf` | `88c78dc5` | **yes** |
| `lab control M0208` | `88c78dc5` | `88c78dc5` | no |
| D17 read through `store.connect_readonly` | `88c78dc5` | `88c78dc5` | no |
| the one-sweep shape measurement | `88c78dc5` | `88c78dc5` | no |
| `lab note` rehearsal on the copy | `88c78dc5` | `88c78dc5` | no |
| **`lab note` for real** | `88c78dc5` | **`7a701f11`** | **yes** |
| `lab stage` | `7a701f11` | `7a701f11` | no (it stages, it does not write) |

- **I1** — no test-window look. `lab test` and `lab promote` were never invoked and
  `SEER_RESEARCH_TEST_STORE` was never read. Looks **4 → 4**, asserted read-only before and after.
- **I2** — recorded records frozen. Trials 677-680 and 853 are untouched; amendment seq 1's
  `why` / `hypothesis` / `expected_failure` are byte-identical; `MATCHED_DRAW` stays the file's
  first amendment block and `runner.pending_amendment`'s prefix check passed, which is the
  mechanical proof. The re-draw is a **new** arm under a **new** amendment, never an edit.
- **I3** — v1's body untouched. This phase edited no line of `control_draw.py`; `MatchedDrawAllocator`,
  `_a1`, `choose`, `_banded_picks`, `_book`, `previous_month_end`, `overhangs`, `draw`, `scored`,
  `build_week_grid`, `OverhangParams`, `OverhangAllocator` and `METHOD.candidates` are all as they
  were. `_banded_picks`, `_book` and `previous_month_end` are now read by two recorded allocators
  instead of one.
- **I4** — every `lab` command was redirected to a file and its exit code read directly. Nothing
  was piped. `lab note` exited 0 once and was not retried; the single append is verified above.
- **I5** — the table above. `sqlite3 "file:…?mode=ro"` never moved the hash.
- **I6** — `lab stage` ran in the checkout that owns the database and its commit took **no
  pathspec**. `git diff --cached --name-only` was exactly `lab/lab.sqlite` and `web/data/lab.json`;
  the coordinator's unstaged `ledger.json` was therefore not swept in.
- **I7** — pre-registration before the run. `280aca6` committed the method file and the test module;
  `lab run --amend` came after it and recorded `023cfd2f…` as the amendment's source sha.
- **I8** — re-run against re-run. §3 above, inside one sweep on one store.
- **I9** — no mutable allocator state. `ShadowDrawAllocator` stores nothing on `self`; the shadow
  lives in `shadow_selection`'s local, which phase 2's purity test pins.
- **I11** — the suite was run at the `lab stage` boundary and at the end, never in the red window
  between `lab run` and `lab stage`.

---

## 7. Tree

| check | result |
|---|---|
| `ruff check engine` | **All checks passed!** |
| targeted modules (m0208 draw, methods, control shape, control draw, control draw shadow) | **1861 passed** in 19.60s |
| whole suite before the pre-registration commit, `PG_TEST_URL` set | **6206 passed, 3 skipped** in 111.22s |
| whole suite after `lab stage`, `PG_TEST_URL` set | **6206 passed, 3 skipped** in 116.16s |
| the 3 skips | the pre-existing env-gated live sweeps (`test_lab_costs.py:314`, `test_lab_name_count.py:240`, `test_lab_survivorship.py:387`) — **no DB test skipped** |

6196 (phase 2) → 6206 is this phase's **8 new tests** plus the two sweeps parameterised over
`all_candidates()` gaining a `M0208-CGO-N20-PLC2` case each (`test_candidate_runs_a_smoke_window`
and `test_allocator_contract`).

`test_m0208_carries_exactly_one_amendment_of_one_arm` was inverted to
`test_m0208_carries_two_amendments_of_one_arm_each` rather than deleted — the post-run truth is the
stronger assertion, and it is the import-time half of `runner.pending_amendment`'s prefix check.
This is the same pattern as `seer-lab-tests-that-pin-pre-run-db-state`.

---

## 8. Decisions taken on the ladder, not asked

| fork | decided | rung |
|---|---|---|
| Ship phase 1's K = 2, or this phase's own? The two ladders read 0.989 and 0.949 at K = 2 | **this phase's own ladder**, which independently names 2; both numbers reported side by side with the reason they differ (the switch guard, and the covered-decision denominator) | 2 — the exit criteria name "the smallest K ≤ 8 whose ratio reaches ≥ 0.90 **on this phase's ladder**" |
| `lab control`'s 0.96 / 1.03 crosses a store boundary (book on `77c37d55`, controls on `640fc25e`) | **re-measure all three arms in one sweep on one store** before quoting anything; report the recorded figures as a reproduction check | 1 — invariant I8, plus the coordinator's standing rule |
| The note template assumes the margin WIDENS; it narrowed | **write what happened**, and say explicitly which half of the floor's reasoning was wrong | 4 — the Why's deliverable is an honest number, not a bigger one; and the tie-break *"a failing prediction is never settled by relaxing the claim"* |
| The probe's ladder scores over all 169 decisions while phase 1 scored over covered ones | **report both**; the probe prints a covered-decision ratio column beside the whole-window one | 6 — the surrounding convention; it changed no answer (coverage is 169/169 at every depth here) |
| Commit the two raw probe outputs as `.txt` or `.log`? | **`.txt`** | 6 — the repo's root `.gitignore` ignores `*.log`; phase 1 made the same call |

---

## 9. Handoffs

**To phase 6 (the close-out) — the owner-facing sentences:**

- **M0208's verdict moved.** `published_sentence_moved: true`. The new figure is **3.7 points a
  year, measured**, and **both** earlier figures (6 points, and "at least 4.3") are withdrawn in
  the verdict string itself. Phase 6's sweep should find this one already corrected and must not
  re-correct it — but should check the rest of the lab for any *other* sentence quoting M0208's
  margin, which this phase did not sweep for.
- **The "floor" framing is itself a correction phase 6 should publish**, and it is more interesting
  than the number: a margin quoted against an under-trading control was presented as a *lower
  bound* with an argued mechanism (more trades ⇒ more fees ⇒ less return ⇒ wider true margin).
  **The mechanism is measured false here.** A blind draw's return is arbitrary enough to swamp the
  fee difference between 455 and 596 trades on this chassis, so an under-shaped control's margin is
  an *estimate of unknown sign*, never a floor. Any other sentence in the lab calling a
  control-shape caveat a floor or a bound is suspect by the same argument.
- **The three-arm supersession chain is the lab's first.** `M0208-HASH-N20` → `M0208-CGO-N20-PLC`
  → `M0208-CGO-N20-PLC2`: a superseded `warn` arm was itself superseded, every row still prints
  with its own ratios and its own verdict, and `refusals` drops both. Worth a line.
- **The 624 is settled and the ratio is unaffected** — phase 1 confirmed it by forward replay and
  this phase's anchor 1 reproduced it independently. Phase 6 should carry phase 1's caution where
  it records the figure: `trials.trades` counts closed round trips, so it equals the entry count by
  construction on a constant-name-count book and is **not** independent evidence.

**To phase 6 — two candidate insights, handed over as prose and deliberately NOT journalled**
(this phase journals no insight; `lab insight` is phase 6's, one command at a time, exit code read
directly):

- **(a) A control's stand-in for *what the real book held* must carry the switch as well as the
  band.** Measured here: closing the SPY 200-day switch inside a one-step replay carries M0208's
  entry estimate from 304 to **446** before any extra depth is paid for — 44 % of the whole
  shortfall, from nine decisions. A stand-in that imagines a full book in a month the book was in
  cash reads a handful of entries where the truth is a full refill.
- **(b) The lift from a better entry-count estimate is sublinear, and the second-order effect is
  the one to quote.** Estimated entries rose **1.95×** (304 → 592) and realised trades only
  **1.31×** (455 → 596), because realised entries are `Σ max(e, attrition)` and attrition stops
  binding as `e` rises. A phase predicting a realised count from an entry-count ratio must divide,
  not multiply.
- **(c), new and arguably the most portable:** *an under-shaped control's margin is not a bound in
  either direction.* See the second bullet above. If phase 6 journals only one of these, this is
  the one that changes how the next margin is written up.

**To phase 5 (the weight axis) — nothing was touched, and the reasons are structural:**

- **M0201 is not touched here.** Its control misses on turnover, its entry-count estimator was
  measured at 0.955, and its K curve runs **backwards** (0.966 → 0.947 → 0.946), so a shadow would
  be an active harm. The coordinator has already settled that it gets no shadow; phase 4 reached
  the same place from the weight axis. **R2, not R1.**
- **M0221 and M0225 are not touched here**, structurally: `M0221-E50` pays 1.60× turnover on
  `C50`'s identical names and identical trades, so no rule choosing *which names* a control holds
  can reach their miss.
- Phase 3's three-condition rule resolved to **M0208 and nothing else**, exactly as the plan's
  table predicted, and no chassis outside that table came up.

**The store-boundary finding, sharpened by one data point:** on M0208 the boundary
`77c37d55` → `640fc25e` costs **exactly zero** — all three arms reproduce to every digit, money
included. That does not weaken the coordinator's finding; it sharpens its statement. The defect is
that a shape ratio across two fingerprints is **not known to be a comparison**, not that it is
always wrong. M0208 declares only SPY and reads its members through a screen, which is about as
store-insensitive as a lab chassis gets; M0201, which sits near a band edge and holds its names
directly, is where the boundary was worth 0.0067. Phase 6 should state it as "a ratio across two
fingerprints must be re-measured before it is quoted", never as "every cross-store ratio is wrong".

**Deliberately left undone (drive-bys, not scope):**

- `engine/tests/test_lab_m0208_matched_draw.py`'s module docstring note that the smoke fixture
  never exercises the draw (473 sessions, `overhangs` needs 780) was **extended** to cover the
  shadow replay as well, since the sentence was already being touched — but nothing was
  re-engineered around it.
- A memo over the replay's repeated `scored` calls would cut the run's cost materially. Considered
  and rejected (I9, and `targets()` has no `prepared` to hang one on). At K = 2 the run cost 16.1s
  of sweep, so the case for it is weak anyway.
- `control_draw.RULE_ID` is **not** stamped into M0208's `params.as_dict()` — this chassis never
  stamped it — so `SHADOW_RULE_ID` had nothing to bump here. The v2 rule's record is the allocator
  id `M0208-A2` plus the amendment's source sha.
- The membership convention (0.067 of ratio on M0208) was **not** attempted. No replay depth closes
  it; it is phase 6's leftover.

---

## 10. What this phase cost, and what it bought

**Cost:** one trial (#860), one amendment row (M0208 seq 2), one luck-gate N (164 → 165), one
allocator id, **no method id**, **no test-window look**, and about 17 minutes of wall clock across
the probe, the run, the one-sweep check and two full suites.

**Bought:** M0208's published margin is a **measurement** and not a floor; the lab's first
band-clean honest control on a keep-band chassis; the first three-arm supersession chain; a
measured answer to "is a bounded replay the remedy" (**yes, at depth two, and no deeper**); a
measured price on the switch-guard half of the defect (142 entries, confirming phase 1's 140 from
an independent direction); and the correction that an under-shaped control's margin is not a bound.

**Did not buy, and cannot:** any promotion. `hardgate.check` still refuses M0208, now on the kin
rule, and M0002 has already spent and failed its look.
