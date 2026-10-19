# Handover — the price band is a tool for a problem the books do not have

**Written:** 2026-10-19 · **Branch:** `feature/gate-price-band` (merged to `main`)
**Method spent:** M0258 · **Next free id:** M0261

**The lab after this run**

| | |
|---|---|
| dev trials | **830** (824 + 6) |
| test-window looks used | **4 — unchanged. None was spent.** |
| methods | 274 (271 + M0258 + two queued ideas) |
| insights | **465** (464 + 1) |
| N the luck gate judges at (policy: methods) | **163** (162 + 1) |
| next free id | **M0261** |

---

## What this session established

M0258 put a price band around the SPY 200-day gate on a book that actually holds stocks —
`M0072-Z2-RAWRANK`, carried verbatim — and crossed it against the cadence the gate is read at. Six
arms, one book, nothing moving but the band and the cadence. Every figure below is the
**money-weighted** return on the owner's own monthly deposits (`trial_funding.mwr`, what `lab show`
prints as "your money earned"), against **7.19%/yr** for the same deposits put into SPY TR. The
curve-shape columns are not quoted anywhere: these books are funded and `total_return` and `cagr`
count the deposits as gains.

| arm | band | gate read | money | worst fall | trades | turnover | PF | DSR | screen |
|---|---|---|---|---|---|---|---|---|---|
| `M0258-M-B0` | 0 | monthly | **12.33%** | 23.80% | 1208 | 6.529 | 1.98 | **0.928** | **eligible** |
| `M0258-M-B15` | 1.5% | monthly | 11.17% | 23.80% | 1241 | 6.584 | 1.94 | 0.865 | failed DSR |
| `M0258-M-B30` | 3% | monthly | 11.76% | 24.05% | 1205 | 6.487 | 1.93 | **0.910** | **eligible** |
| `M0258-M-B60` | 6% | monthly | 9.12% | 28.17% | 1182 | 6.277 | 1.65 | 0.788 | failed DSR |
| `M0258-W-B0` | 0 | weekly | 5.32% | 35.49% | 1923 | 10.002 | 1.28 | 0.416 | failed SPY, PF, DSR |
| `M0258-W-B30` | 3% | weekly | 10.03% | 29.74% | 1510 | 8.099 | 1.62 | 0.838 | failed DSR |

**The reproduction is exact.** `M0258-M-B0` came back bit-identical to `M0072-Z2-RAWRANK`'s
recorded row — 12.3314%, 23.8026%, 1208 trades, turnover 6.529, exposure 0.695, PF 1.98 — so every
paired difference below is the gate reading and nothing else. The lab's standing note that a re-run
of a recorded row drifts did **not** apply here; the overlay passes the host's own params to the
host's own target builder, and the only line that differs is the gate test.

### The four paired differences

| comparison | money | worst fall |
|---|---|---|
| monthly: 3% band − bare gate | **−0.57 pts/yr** | 0.25 deeper |
| weekly: 3% band − bare gate | **+4.71 pts/yr** | 5.75 shallower |
| **cadence alone: monthly − weekly, no band** | **+7.01 pts/yr** | **11.69 shallower** |
| 3% band: monthly − weekly | +1.73 pts/yr | 5.69 shallower |

**Difference-in-differences: +5.28 pts/yr and 6.00 points of worst fall.** The pre-registered
prediction — `(W-B30 − W-B0) ≫ (M-B30 − M-B0) ≈ 0` on both axes — **held in full**.

### The ladder is flat-to-falling, and the turnover premise was wrong

0 → 1.5 → 3 → 6 percent gives 12.33 → 11.17 → 11.76 → 9.12 on money and 23.80 → 23.80 → 24.05 →
28.17 on worst fall. **No rung beats zero on either axis.** Not humped, so it is not a signal
story; not monotone, so it is not a clean fee story either — on a monthly book the band simply
does nothing worth measuring.

The brief's premise that "the band cuts turnover sharply, so a control drawn at the bare gate's
trade count is mis-shaped by construction" is **false at monthly cadence on this book**: the four
monthly arms traded 1208 / 1241 / 1205 / 1182 on turnover 6.529 / 6.584 / 6.487 / 6.277, a spread
under 0.6%. The band changes *when* the gate acts, not *how often*. Even weekly it cut turnover
only **19%** (10.002 → 8.099), far short of the 75% cut the same band produced on SPY alone — so
the weekly gain is mostly timing, not fees.

### What is now the open question, and it is bigger than the band

**Reading the gate monthly instead of weekly, with no band at all, is worth +7.01 pts/yr and 11.69
points of worst fall on this book.** That is larger than the band was ever worth at either cadence,
larger than the constant 3.6 pts/yr gate premium, and it had been sitting unexamined in the record.
Every book in the lab reads its gate at whatever cadence it happens to re-pick stocks — nobody ever
chose it. **Queued as M0260.**

### The buy signal is the host's, not the band's

`lab walkforward M0258` prints `*** BUY SIGNAL ***` — dev-eligible, kin clean, 3 of 4 folds, +2.3
pts 2009-2015 edge. **Read it carefully before acting on it.** The arm that cleared is
`M0258-M-B0`, which is `M0072-Z2-RAWRANK` again under a new allocator id. The band earned none of
it. Folds: 1 picked `M-B30` and lost, 2 picked `M-B60` and won, 3 and 4 both picked **`M-B0`** and
won — so the folds did *not* drift toward the least-trading arm as the pre-registration warned they
would; two of four chose no band at all.

### D17 is clean

`lab control M0258` reports four `dose-response` rows, verdict `not-checked`, no ratio, **no
refuse**, and closes with *"every control arm shown matches the shape of the arm it controls"*. The
ladder with its zero rung is the control; no drawn arm exists by design. A drawn one would have
landed near 7× the arm it controlled and been refused.

---

## What is now dead, and must not be bought with another method id

**Add the price band to this list.** Measured three times now — on SPY alone read monthly (−0.40
pts/yr), on M0101's calm-raisers stock book (−0.18 at 3%, −0.52 at 5%), and now on M0072's
earnings-jump book across a four-rung ladder (−0.57 at 3%, −3.21 at 6%). It is only ever worth
something when the gate is read faster than monthly, and no promotable rule set reads it faster
than monthly. Do not spend another id widening, narrowing or asymmetrising it.

## What is now dead, and must not be bought with another method id

Every modification of the SPY 200-day gate below has been measured and buried. None should be
re-tested with a method id; the evidence is in the lab and in the committed studies.

- **Turning the gate off.** Helped 22 of 22 variants whole-window, 0 of 22 after 2009, and every
  gate-off arm was worse on return *and* drawdown at once.
- **A time lock on the switch.** Costs return and deepens the worst fall from 20% to 32%: the
  flips it suppressed included the 2008 exit. The standing rule is "stop hunting hysteresis here",
  and a price band is the one thing that is not that lock — it has no memory of time at all.
- **An account-reading drawdown brake.** Pays about 10 points a year of 2009-2015 to save 40 of
  2008. A volatility dial beats a drawdown dial on every axis.
- **A learned fall-sizing brake** (M0132). Beaten by the plain gate on both axes.
- **VIX-level confirmation of the exit.** Worse on both axes at 20, 25 and 30, and VIX3M only
  begins 2006-07-17, so it cannot be checked against the dot-com fall at all.
- **Exit-buffer-only, confirm-N-days, partial exposure, fast re-entry on the 50-day.** All in the
  committed variant grid, all worse than the symmetric band.

## Leftovers, in priority order

1. **The nine D17-blocked dev-eligible methods** — M0047, M0201, M0202, M0208, M0215, M0221,
   M0225, M0227, M0243 — each carrying a control arm whose trade count or turnover does not match
   the arm it controls. The remedy costs **no method id**: re-draw each control at the book's own
   shape and record it as an amendment under the existing id. This is the cheapest information
   left in the lab and it re-tests nine standing verdicts.
2. **The buyback holdability problem.** The cheap-buyback book led by 11.4 points a year in
   2009-2015 on honest prices and won all four out-of-sample stretches, but falls 55-85%, so it
   cannot be held. A containment problem, not a gate problem.
3. **Insight 457's practical conclusion still stands on the site** ("weight by company size"),
   withdrawn by 462 but, `insights` being append-only, still visible to the owner. Another
   correction row — same shape as the one this run queued, different subject.
4. **P2-ENG-N3LB** — `name_count.py`'s docstring still calls the dev trial count "the lab's N",
   which the 2026-10-08 policy move made wrong.
5. **P3-ENG-V2KQ** — append a dated §7.3 revision to the lab design doc recording the N policy
   move to methods.
6. **`sim.rules.PRESETS` has no weekly fractional Gotrade preset**, so this method's two weekly
   arms can never be promoted whatever they show. If the weekly band wins, queue a `feature-wish`
   insight for the preset rather than minting one mid-run.

Handover §6 item 3 — the correction row against insight 452's "eleven exits" — was **queued as
this run's next idea** and is no longer a leftover.

## Environment notes that save an hour

- **The worktree has no venv and no research store.** Use the main checkout's:
  `PY=/home/miftah/seer/engine/.venv/bin/python`,
  `SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research`. Never rebuild a store — it is 30
  minutes for nothing.
- **`PYTHONPATH=<worktree>/engine/src` or pytest silently tests the main checkout**, not the
  branch.
- **`SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite`.** A worktree copy must never be written, and
  even a read migrates the file on connect.
- **`lab stage` targets the MAIN checkout** — it regenerates and `git add`s `/home/miftah/seer`'s
  `lab/lab.sqlite` and `web/data/lab.json`. Commit them with `git -C /home/miftah/seer commit` and
  **no pathspec**: a pathspec re-reads the working tree and defeats the staging.
- **Never judge a `lab` command by a piped exit code.** Redirect to a file and echo `$?`; a
  `grep`/`head` owns the pipeline's status, and this shell prints a spurious
  `setValueForKeyFakeAssocArray:27: command not found: _encode` line at startup that appears at
  the head of every captured file.
- **One core.** Run pytest with `-n0`; never override `addopts`.
- **The DB tests need Postgres**: `docker start seer-pg`, and
  `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres`. CI fails if they skip.
- **The cadence study reads a relative store path**, so run it from the main checkout:
  `cd /home/miftah/seer && engine/.venv/bin/python docs/backtests/2026-10-19-gate-band-cadence.py`.
