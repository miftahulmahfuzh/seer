# Handover: 2026-10-12 — the hurdle counts methods, and the brakes are the drag

**Written by:** `orch-lab-exposure-diagnostic`, after landing the exposure diagnostic plan set.
**Branch state:** everything is on `main` at `e9715b2`. No branch, no worktree, nothing uncommitted.
**Predecessor:** `docs/plans/HANDOVER_20261012-picks-not-brakes.md` — read it for the dividend
family's story, which is the question this session answered.

---

## 1. What landed

The exposure diagnostic from §4.1 of the predecessor handover, built and run as a two-phase
swarm and merged to `main`.

| Commit | What |
|---|---|
| `625098f` | `lab exposure` — the report-only diagnostic (3 files, 1760 lines, 23 tests) |
| `bd65a8e` | the run over the five, the journal, the write-up and its grid |
| `989383e` | merge of the set into `main` |
| `4818884` | `package_readme.md`: corrected a stale reproduction claim, added the write-up pointer |
| `ef04fcc` | dated the stale dev-store fingerprint across three plans and two engine modules |
| `e9715b2` | the luck gate's N is 74 methods, not 354 trial rows |

`lab exposure MNNNN [...]` re-runs every recorded dev variant four times on one store — as
recorded; its own picks at the weights it gave them; those picks rescaled with the brakes off;
and the parked money alone — and reports how much of the book was ever in the method's own picks,
plus the lead over SPY whole-window and per era. Parked instruments are read generically off the
allocator's `holds()`, so **no method file changed and no method id was minted**.

Write-up: `docs/backtests/2026-10-12-exposure-diagnostic.md`, grid beside it as `-grid.csv`.
Journal: insights 185–189 (one observation per method) and 190 (the synthesis).

---

## 2. The answer, and it is not the one §2 expected

**The lab's live space is not empty.** Four of the five park nothing at all — every name they
hold is their own pick — so the dividend family's disease is simply absent there. Picks at full
size, whole-window lead over deposit-matched SPY: **+4.4, +3.6, +7.5, +4.8, +7.2** points a year
for M0024, M0028, M0030, M0044, M0053.

**M0030 is the dividend family's inverse.** Only 35.6% of its book was ever in its own names, and
its picks alone lead by +7.5 against +4.7 for the whole book. There the parked SPY *dilutes* the
edge rather than carrying it.

### Two cautions that matter more than the good news

**The five books are far less independent than five method ids suggest.** `empty_share` came back
**bit-identical at 67/237 (28.3%)** across four of them. That was investigated as a suspected bug
before a word of the write-up was written; it is genuine. They share one SPY 200-day gate read on
the same monthly dates — the two variants that drop it (`M0024-SAME-N20-NOTREND`, `M0030-C50A`)
correctly report 0.0%, and M0053's weekly cadence has its own denominator, 328/1157. That single
gate produced the **+34.8 2008 lead for every book**: one trade shared five ways, not five
discoveries.

**From 2009 to the end of the dev window the best version of all five trails the market.** Only
two recover with the brakes off, by under three points a year.

---

## 3. The number that prices every decision from here

Measured 2026-10-12, and it corrects an assumption several plans carry:

```
store.gate(conn)                                 ->  N = 74, policy "methods"
store.dev_trial_count                            ->  354 dev trial ROWS
pending_gate, 4 variants on an EXISTING method   ->  74   (free)
pending_gate, a brand-new method                 ->  75   (+1, retroactively,
                                                           for all 130 methods)
```

**Variants are free. Method ids are what the hurdle counts.** A `sera-the-explorer` batch is
therefore the most expensive thing on the board, and adding variants to methods that already
exist costs nothing.

This matters doubly given §2's independence finding: a fresh batch drawn from the same idea pool
likely reuses the same 200-day gate, so you would pay +1 N per method for information that is not
independent of what the lab already holds. That is the exact shape of the trap the dividend
family cost three batches to find.

---

## 4. What I would do next, in this order

### 4.1 Brakes-off variants on M0030 and M0053 — free in N

The diagnostic's `-FULL` arm found the only post-2009 edge anywhere in the grid: **M0030 +2.7**
and **M0053 +0.5** a year from 2009, where every recorded variant of all five trails. Those arms
are diagnostic columns, not methods the lab holds — there is no candidate for "M0030 with the
brakes off."

Turning them into real pre-registered **variants of the existing method files** costs **zero N**
(§3) and tests the single hypothesis the data actually produced. This is the cheapest high-value
work available.

### 4.2 Interrogate the shared 200-day gate — highest leverage

The lab's own recorded control prices it: **gated +2.7/yr whole-window vs ungated +1.0**, but
after 2009 the gated version **trails by 5.4** while the ungated one **leads by 1.5**. Nearly all
of its value is a single year (2008) and it has been a drag for six.

It is a *shared component* across the roster, so changing it moves every book at once. That is
the highest-leverage item on the board, and it is a variant-level question — free in N.

### 4.3 New data sources — gated, and not yet

The standing rule is to buy survivorship-free data only when a method clears **dev-eligible + a
majority of walk-forward folds + a positive 2009–2015 edge**. Nothing currently clears the third
condition. §4.1's variants are the only live candidates that might, so they are the precondition
for the data spend being worth evaluating at all. Revisit after 4.1, not before.

### 4.4 A new `sera-the-explorer` batch — not now

See §3. It is the most expensive option, and §2 says the marginal method is likely correlated
with what the lab already holds. Prefer it only once 4.1 and 4.2 have either produced an edge or
closed the question.

---

## 5. Open tasks this session created

### 5.1 `commands/lab.py` tells the owner the wrong N — a decision, not a fix

**Ten printed lines** read `Lab N (dev trials) is now <count>`:

```
engine/src/seer_engine/commands/lab.py:1399, 1684, 1718, 1739, 1785, 1817, 1870, 1923, 2238, 2287
```

That is `store.dev_trial_count` — **354 rows** — and it is the number the owner reads as the luck
hurdle on every lab command. The gate's actual N is **74** (§3). So the owner currently sees a new
method priced at 1/354 of the hurdle when it is 1/74, and sees variants as costly when they are
free.

I did not change these: altering what the owner reads is a decision about his mental model, not a
docstring fix, and it touches a command surface that several runbooks quote. The options are to
print both numbers, to print the gate's N and label the row count separately, or to leave it and
fix the labelling in the docs only. **This is the first thing I would put to the owner.**

The docs are already corrected: `lab/exposure.py`'s docstring and the exposure plan's invariant 3
and Reconciliation Log C8 now say plainly that the two are different numbers (`e9715b2`).

### 5.2 Deliberately left alone

- `DELISTING_STRESS_ROSTER_RULES_PLAN.md` — "N is 110 and stays 110" (live: 74 / 354). Left
  because it names its own branch (`ba8a05b`) and bounds the claim to its own set, so it reads as
  a record rather than a standing claim. Same for the suite baselines (374, 970, 761, 31, 3197),
  each tied to a named commit.
- The `BACKFILL_PRICE_FINGERPRINTS` map in `lab/store.py` lists four store fingerprints while the
  lab's trials carry seven. **This is not a gap** and is now documented as a closed historical
  record: a trial recorded since trial-reproducibility writes its own `price_fingerprint` and
  never reads the map. Do not extend it.

---

## 6. Things that will bite you

- **The dev store's fingerprint is `77c37d553508…`, not `399d0d25…`.** Three plans and two engine
  modules asserted the old value in the present tense; all are dated now (`ef04fcc`). The store is
  **not** clobbered — the move came from `fundamentals.csv` and `market_series.csv` joining the
  file map (six files now, four at P7a), and an optional file moves the full fingerprint by
  design. Verified 2026-10-12: **2,490,793 bar rows, 539 symbols**, and
  `price_fingerprint_of()` over today's manifest still returns `5451195f…`, the value all 354 dev
  trials are recorded against. **Never rebuild the store on a fingerprint mismatch alone** — a
  rebuild costs ~30 minutes and drops the optional files, destroying the market series.

- **Reproduction is currently clean, and an older measurement said otherwise.** All 23 recorded
  dev variants of the five reproduce their recorded total return digit for digit on
  `77c37d553508…`. The exposure plan's invariant 8 cites `M0030-C50T` at `9.583603` vs a recorded
  `9.583723`; that was measured on an earlier store build and reached `package_readme.md` as a
  present-tense claim before anyone re-ran it. Both are dated now. Re-measure rather than
  carrying any such figure forward.

- **`lab exposure` is report-only and proven so.** Verified twice independently — once from the
  committed `lab.sqlite` blobs before and after, once by a full re-run — the only table that moves
  is `insights`. `lab.sqlite` came back byte-identical (md5 `4a34ddb8`) from a complete run with
  `--no-journal`.

- **A lab command migrates `lab/lab.sqlite` on connect**, even for a read. Hash it before, and
  restore by explicit path afterwards if you only meant to read.

- **The suite is 4364 passed / 3 skipped** with Postgres up (`docker start seer-pg`,
  `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres`). The three skips are opt-in
  live-store tests, not DB tests. A worktree needs `PYTHONPATH=<worktree>/engine/src` and the main
  checkout's venv, or it silently tests `main`.

---

## 7. The pattern worth carrying forward

Every correction this session made was the same failure: **a measured number phrased as a standing
invariant, with no mechanism tying it to the thing it measured.** One benign store change
falsified a line in three plans and two source files at once, and nothing noticed for six days
because nothing executable depended on it. The `N` conflation is the same shape and is still live
in ten strings the owner reads (§5.1).

Corrections are dated rather than overwritten, so a plan still records what was believed when it
was written. Keep doing that.
