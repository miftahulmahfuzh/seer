> Adopted from `LAB_LUCK_GATE_PLAN.md` phase 9. Source: `.workflows/plan/lab-luck-gate/phase-9.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 9: Luck-test the P7a seed

**Plan set:** `LAB_LUCK_GATE_PLAN.md`
**Analysis:** `20261007-085606-D3K1_code_analyzer.md`
**Satisfies:** R6 — the 54 P7a seed trials pay the full multiple-testing penalty but receive no
luck verdict in return, because their daily moments were never captured. After this phase they are
judged on a measured number instead of excluded by a data gap.
**Depends on:** **2, 3, 4** — Phase 2 (`trial_moments`, `MomentsRow`, `insert_moments`,
`moments_of`), Phase 3 (`seer_engine.lab.remeasure`, the `remeasure` subcommand) and **Phase 4**
(`store.verdict`, `store.gate`, `store.dev_sharpe_variance`, `store.DSR_MIN`), which the
mandated eligibility report cannot be written without. **Accepted by the reconciler in round 2**;
the brief said `[2, 3]`. Waves are unchanged — 3 and 4 are both W2, so this phase is W3 either
way — but a coordinator must **not** release it when phase 3 alone reports done. See
**Dependency correction** below. Phase 8 is not a code dependency, only a dependency of the
report's eligibility *column*.
**Difficulty:** NORMAL
**Package:** `engine/src/seer_engine/lab` (+ the existing `remeasure` subcommand in
`engine/src/seer_engine/commands`)

---

## Goal

`lab remeasure H-P7A` re-runs all 54 P7a seed candidates on the dev window straight out of the
frozen `backtest/registry.py`, proves each re-run reproduces the six metrics the lab actually
recorded for that trial, and appends one `trial_moments` row per trial that clears the bar. After
this phase the 54 rows that have paid into `dev_trial_count` since the lab was seeded can finally
be luck-tested by phase 4's `store.verdict` at the current gate N, instead of failing it for
having no DSR to test. Nothing about `trials`, `methods.status`, the REGISTRY, `DEV_END`, the gate
constants or the test window changes, and N does not move.

---

## What was measured before this plan was written

Every number below was produced against the committed `lab/lab.sqlite` and the real dev store in
`/home/miftah/seer/engine/.research`. They are facts, not estimates, and the plan is built on them.

### 1. All 54 reproduce, and the tolerance falls out of the data

The 54 seed rows were imported from `docs/backtests/2026-10-04-p7a-dev-exploration-rows.csv`,
whose every float is **rounded to 6 decimal places** (verified: no seed row carries a 7th
decimal in any metric column). Decimal rounding to 6 dp bounds the recorded-vs-true error at
**5e-7 absolute**, independent of magnitude.

Re-running all 54 through `dev.run_registry` on today's store and differencing against the
recorded columns:

| metric | worst absolute delta over 54 | on |
|---|---|---|
| `sharpe` | 4.933e-07 | `F4-MOM12-N10-TREND-IVOL` |
| `cagr` | 4.762e-07 | `F9-SPY200M70-MOM30` |
| `max_drawdown` | 4.907e-07 | `F4-MOM12-N10` |
| `profit_factor` | 4.986e-07 | `F7-RSI2-T20-DIP` |
| `total_return` | 4.809e-07 | `F7-RSI2-T10-DIP` |
| `trades` | **0** (exact, all 54) | — |

Every delta sits under the 5e-7 rounding bound with none to spare and none over. **Zero trials
diverge.** The only NULL pair is `REF-SPY-HOLD`'s `profit_factor`, recorded NULL and measured
`None` — a match, not a divergence (it is a 0-trade buy-and-hold reference).

**The tolerance this phase adopts: `METRIC_TOL = 1e-6`, absolute, on the five float metrics;
exact equality on `trades`; `None` reproduces `None` and nothing else.** Justified in full under
*Decision: the tolerance* below.

### 2. The store changed under them, and it did not matter

The 54 seed trials record `store_fingerprint = 5451195f…`; the store on disk today is
`399d0d25…` (two rebuilds since, both touching `fundamentals.csv`). The re-run above was done on
`399d0d25…` and still reproduced every metric to the rounding bound. So the phase does **not**
refuse on a fingerprint mismatch — the reproduction check is the real gate, and it passes. The
report prints both fingerprints so the difference is on the record rather than hidden.

### 3. The batch is ~65 seconds, not hours

`research.load_store` 10.8s, then all 54 candidates in **51.5s** inside one `run_registry` call.
Slowest three: `F9-SPY200D50-SWING50` 7.8s, `F7-RSI2-T20-DIP` 7.1s, `REF-A-V0` 6.7s. Median 0.4s.

The brief budgeted for "a long job … design for it being killed halfway". The resumable, chunked,
idempotent design is built anyway — it is cheap and the brief requires it — but the plan records
the true cost so nobody waits for an hour that will not happen.

### 4. Chunking is bit-identical to one call

`F1-SPY-SMA200-M`, `F3-SEC-TOP3-6M-TREND`, `F4-MOM12-N20-TREND` and `F9-SPY200M70-MOM30` were run
once alone and once inside the full 54-candidate call. The measured `sharpe` values are
**bit-identical** across both (`0.8076441459700493`, `0.6933529779771368`, `0.8896704729955996`,
`0.8729428790685417`), as is `t`. `run_registry`'s per-allocator `prepare_for` cache is
rebuilt per call but produces the same object, so splitting the batch costs re-preparation time
and nothing else. **Resumability is therefore free of correctness cost**, which is what makes
chunk-at-any-boundary safe.

### 5. The REGISTRY still matches, exactly

`len(REGISTRY) == 54`; the 54 seed rows' `candidate_id` list equals `[c.id for c in REGISTRY]` in
order; and `config_digest(candidate) == trials.config_digest` for **all 54**, zero mismatches. So
the trial-defining parts of every candidate are provably unchanged since the import, and the
re-run measures the same configuration. This per-trial digest equality is the guard this phase
uses — stronger than a file hash, and immune to the registry legitimately gaining entries 55+.

### 6. The outcome: one candidate, and it lands on the bar

All 54 re-measured, with exact moments. Owner conditions re-derived at phase 8's 20% drawdown bar
(`beats SPY TR`, `max DD <= 20%`, `PF >= 1.3`, `>= 100 trades`, `no owner inputs`):

**Exactly one of the 54 passes every owner condition: `F9-SPY200M70-MOM30`** (trial #53).

```
#53 F9-SPY200M70-MOM30
    measured: t=4983  sr_daily=0.054990233  skew=-0.398685892  kurt=10.209918596
    recorded: sharpe 0.872943  cagr 12.2188%  maxDD 19.2373%  PF 4.281346  trades 635  MAR 0.635
    DSR @ N=110, var_trials = 2.006691e-04 (the P7a search's own)  ->  0.903053
    DSR @ N=110, var_trials = 2.395048e-04 (all 110 dev trials)    ->  0.856651
```

It straddles the 0.90 bar **on the variance question alone**, and the skew/kurtosis it was missing
turn out to be worth only ±0.005.

> **SETTLED BY THE RECONCILER, 2026-10-07 — Decision D12.** The fork this phase surfaced is
> closed: **both of `store.dsr_at`'s routes deflate by today's `store.dev_sharpe_variance(conn)`**,
> and the `var_trials` column recorded beside a trial is historical record only, never an input to
> a live verdict. Phase 4's route-1 code has been corrected to match its own docstring.
> **So `F9-SPY200M70-MOM30` reads 0.856651 at N = 110 and stays ineligible** — but on a luck test
> it finally *received*, rather than on a data gap. That is R6 satisfied, and it is exactly what
> the owner asked for in saying they would rather re-run than wonder.
>
> **The eligible set is therefore unchanged at THREE** — `M0022-W-TV14`, `M0022-W-TV16`,
> `M0020-W-NOSTOP` — and this phase adds none. Its deliverable is the *verdict*, not a fourth
> candidate.
>
> The report still prints **both** figures side by side (now: the gate's number first, the
> as-of-P7a one beside it), so the fork stays visible on the terminal rather than buried in a
> constant. `test_the_report_names_both_variances` pins that.

**Correction to the phase brief.** The brief states `F3-SEC-TOP3-6M-TREND` "also passes the owner
conditions". It does not. Its recorded `failed` is `"max DD <= 15%; owner inputs"`, and
`candidate_owner_inputs` returns the nine sector ETFs (`etf:XLB` … `etf:XLY`). Phase 8's drawbar
move clears `max DD` (19.5% ≤ 20%) but `owner inputs` is not a threshold and no constant
re-decides it — phase 4's `verdict` carries it from the recorded string. So `F3-SEC-TOP3-6M-TREND`
stays ineligible on owner inputs regardless of its DSR (0.6777 stored-var / 0.5989 today-var).
The report prints it in the near-miss block with the reason, which is the honest outcome.

Top of the 54 by DSR at N=110 (today's variance), with the owner-condition column:

| # | candidate | t | sr_daily | skew | kurt | DSR (stored var) | DSR (today var) | owner |
|---|---|---|---|---|---|---|---|---|
| 37 | `F4-MOM6-N10-TREND` | 4983 | 0.059346 | -0.0582 | 9.4299 | 0.9470 | 0.9163 | fails max DD (30.4%) |
| 52 | `F7-RSI2-T20-NOSTOP` | 4983 | 0.057272 | -0.0952 | 16.3352 | 0.9286 | 0.8908 | fails max DD, PF |
| 41 | `F5-LV60-N20-TREND` | 4983 | 0.056187 | -0.0463 | 9.9466 | 0.9186 | 0.8769 | fails beats SPY, max DD |
| 42 | `F5-LV252-N20-TREND` | 4983 | 0.056230 | -0.1558 | 10.5067 | 0.9183 | 0.8767 | fails beats SPY, max DD |
| 35 | `F4-MOM12-N20-TREND` | 4983 | 0.056044 | -0.1893 | 9.6485 | 0.9162 | 0.8739 | fails max DD (22.2%) |
| **53** | **`F9-SPY200M70-MOM30`** | 4983 | 0.054990 | -0.3987 | 10.2099 | **0.9031** | **0.8567** | **all pass** |

Clearing 0.90 at N=110: 6 of 54 under the stored variance, 1 of 54 under today's.
**Eligible (owner-ok and luck-ok): `['F9-SPY200M70-MOM30']` under the stored variance, `[]` under
today's.** Under D12 the gate uses today's, so **this phase makes nothing eligible**; it prints
both columns so the reader can see how close the call was.

---

## Decision: the tolerance for verifying a seed re-run

**`METRIC_TOL = 1e-6`, absolute, applied independently to `sharpe`, `cagr`, `max_drawdown`,
`profit_factor` and `total_return`. `trades` must be exactly equal. A metric recorded NULL
reproduces only as `None`, and a metric recorded non-NULL reproduces only as non-`None`.**

**Why absolute and not relative.** Phase 3 checks `sharpe` at `1e-9` *relative* because its trials
came out of the engine as full-precision floats, so the only expected difference is a last-ulp
libm wobble. These 54 did not: they came through a CSV written to 6 decimal places by
`seed.py`'s importer. The error source is therefore decimal rounding, whose bound is **absolute**
(5e-7) and has nothing to do with the value's magnitude. A relative tolerance would be the wrong
shape in both directions: `cagr = 0.031191` needs 1.6e-5 relative to survive the same rounding,
while `total_return = 18.648246` at 1e-6 relative would admit 1.9e-5 — 37× the rounding bound, a
window wide enough for a real divergence to slip through. One absolute number does the job
correctly at every magnitude present.

**Why 1e-6 and not 5e-7.** 5e-7 is the exact theoretical bound and the worst measured delta is
4.986e-07 — 0.3% of headroom. That is too tight to ship: a libm or platform difference of a few
ulps on an already-rounded comparison would flip a trial to "divergent" for no real reason. 1e-6
is exactly 2× the rounding bound, which leaves room for the ulps and is still two to four orders
of magnitude tighter than any genuine divergence. For scale: a changed research store moved
`M0011`'s metrics in the third decimal, and swapping the dev window moves them by whole units.
1e-6 cannot confuse those with rounding.

**Why six metrics and not one.** Phase 3 can assert the single strongest thing — reproduce the
recorded `dsr` to 1e-6 — because a recorded `dsr` exists. A seed trial has `dsr IS NULL` by
construction, so that check is simply unavailable. Six independent metrics, each measuring a
different property of the same equity curve (risk-adjusted return, compounding, worst peak-to-
trough, gross win/loss ratio, terminal wealth, and the exact count of closed positions) is the
available substitute. `trades` being an **exact integer match** is the sharpest of the six: it
pins the trade sequence itself, so a changed universe, a changed signal or a changed fill rule
cannot pass it. The other five then pin the magnitudes.

`mar`, `spy_tr_return` and `spy_tr_cagr` are deliberately **not** gated: `mar` is
`cagr / max_drawdown`, algebraically implied by two metrics already checked, and the two
`spy_tr_*` columns are the benchmark, identical across all 54 and therefore carrying no
per-candidate information. Gating on them would add arithmetic, not evidence.

**What a failure does.** Per the brief: a divergent metric is **a finding reported per trial, not
a crash**, and it **blocks the write for that trial only**. The other trials in the chunk are
written. The command prints every divergent trial with the metric, the recorded value, the
measured value and the delta, and exits **1** so an unattended caller notices. This is the one
deliberate departure from phase 3's `check`, which aborts the whole command — phase 3 can be
all-or-nothing because one method is 2–5 trials measured together; here 54 trials across 11
families would mean one drifted ETF sinking fifty-three good re-measurements.

---

## Decision: what goes in `var_trials`, and the cross-phase conflict it surfaces

**This phase writes `var_trials = statistics.variance` of the 54 seed trials' recorded daily
Sharpes (`trials.sharpe / sqrt(252)`) — measured: `2.006690619e-04`.**

**Why that value is the honest one.** `runner.trial_rows` computes `var_trials` as
`statistics.variance(prior + new_sharpes)` where `prior` is every dev trial that already existed.
The seed import is the lab's first batch: `prior` is empty and the batch is all 54. So the
variance of the 54 seed daily Sharpes is literally the number `lab run` would have computed had
P7a been run through the lab. It is a reconstruction of a historical fact, not a substitute for
one — the same thing phase 3's `batches_of` reconstructs, arrived at the same way. (Checked:
`batches_of` would in fact accept the seed rows unmodified — they are contiguous `n = 1..54`, all
carry `run_at = 2026-10-04T00:00:00+00:00` and `n_trials_at_run = 54`, and `0 + 54 == 54`. This
phase still does not use it, for the reason in the next paragraph.)

**Why it is read off the recorded column and not off the re-run.** Three reasons, and the first is
decisive:

1. **It makes the batch chunk-invariant, and therefore resumable.** Reading it from the database
   makes it a constant settled in preflight, identical whether you run 54 candidates at once or
   one at a time across six interrupted sessions. Computing it from fresh daily Sharpes would
   require all 54 re-runs to be in hand before the first row could be written, which is exactly
   the shape the brief forbids.
2. `trials.sharpe` **is** P7a's measurement of record. The fresh re-run is evidence that the
   record is sound, not a replacement for it.
3. The difference is immaterial: variance of the recorded column `2.006690619e-04` vs variance of
   the fresh daily Sharpes `2.006691421e-04`, a gap of **8.0e-11**, four orders of magnitude below
   anything the DSR can see.

### The cross-phase conflict this phase surfaced — RESOLVED, Decision D12

> **Status: closed by the reconciler, 2026-10-07.** Phase 4's route 1 has been rewritten to read
> `dev_sharpe_variance(conn)` **once, before either route branches**, so `moments["var_trials"]`
> is no longer referenced anywhere in `dsr_at`. The record of how the fork was found and settled
> is kept below because the measurement is what justifies the choice; nothing in it is still open.
>
> **Rung 4 — the index's Requirements table, R2:** *"a trial's verdict is frozen at the N of its
> run date, so verdicts are not comparable across time and the leaderboard mixes bars."* The
> hurdle is `SR* = sqrt(var_trials) × E[max over N]`; using each trial's as-of-run variance
> freezes half that hurdle at its run date and reintroduces exactly the incoherence R2 exists to
> remove. It is the same rung and the same principle on which `M0007-N20-RAW` was settled
> (re-evaluate at the current N, not the recorded one, Decision D11) — the two must agree or the
> gate is incoherent.

**What was found.** Phase 4's `store.dsr_at` contradicted its own docstring. The docstring said,
emphatically:

> **Both routes use `dev_sharpe_variance(conn)` — the trial-Sharpe variance as the lab stands
> now — and never the `var_trials` recorded beside the trial.** … The recorded `var_trials` stays
> in `trial_moments` as history.

The code immediately below it did the opposite on route 1 (**since corrected**):

```python
    moments = moments_of(conn, int(trial["n"]))
    if moments is not None and moments["var_trials"] is not None:
        return dev.deflated_sharpe(
            float(moments["sr_daily"]), n_trials, float(moments["var_trials"]),   # <-- stored
            int(moments["t"]), float(moments["skew"]), float(moments["kurt"]),
        )
```

Route 2 uses `dev_sharpe_variance(conn)`. Verified arithmetically: route 2 with
`dev_sharpe_variance` reproduces phase 4's own quoted figure for `M0007-N20-RAW` at N=110 —
**0.8985**, to four decimals — while the as-of-run variance gives 0.8962. So phase 4's measured
numbers were taken under its docstring, and its route-1 code is the outlier.

**Why it matters here and nowhere else.** For a trial run recently, the stored `var_trials` and
today's variance are the same number, so route 1's choice is invisible. The 54 seed rows are the
only place in the lab where the two differ materially (2.0067e-04 vs 2.3950e-04), and they differ
by enough to move `F9-SPY200M70-MOM30` from **0.903053** (passes 0.90) to **0.856651** (fails).

**The resolution, applied in phase 4:** route 1 now uses `dev_sharpe_variance(conn)`, matching the
docstring. Deflating by today's N = 110 while scaling by a variance measured over a 54-trial
search mixes bars on the two axes of the same formula — the exact defect R2 names, one column
over, and the reason phase 4 refuses to use `n_trials_at_run`. Under it `F9-SPY200M70-MOM30` reads
**0.8567** and stays ineligible — on a measured luck test it finally received, which is the whole
of R6, rather than on a missing column.

**What this phase does, unchanged by the resolution.** It writes the honest historical
`var_trials`, which is correct under either reading and which no live verdict reads, and its
report prints the DSR **both ways**, labelled — the gate's number (today's variance) first, and
the as-of-P7a number beside it in brackets — so a candidate sitting on the bar is visibly sitting
on the bar. A test (`test_the_report_names_both_variances`) pins that both appear.

---

## Dependency correction — the brief says `[2, 3]`, the report needs `4`

The brief's own fourth bullet requires "a report at the end: for every remeasured seed trial, the
DSR it now computes at the current gate N, whether it passes the luck bar, and whether it passes
every owner condition". "The current gate N", "the luck bar" and "owner conditions re-derived at
today's thresholds" are `store.gate`, `store.DSR_MIN` and `store.verdict` — all three created by
phase 4. There is no honest way to write that report from phases 2 and 3 alone, and
re-implementing the policy here would guarantee the two drift.

So: **`Depends on: 2, 3, 4`.** Phase 4 is in wave W2 beside phase 3, so this phase is a natural W3
member alongside 5 and 7. Phase 8 is **not** a code dependency — `verdict`'s `owner_failures`
reads `tuning.MAX_DRAWDOWN` at call time — only a dependency of the eligibility *column's value*:
without phase 8 the report's owner column reads "fails max DD <= 15%" for
`F9-SPY200M70-MOM30` (19.24% > 15%) and nothing is eligible.

---

## Phase 4's state-dependent tests — read this before running the batch

Phase 4 pins `F9-SPY200M70-MOM30` as ineligible-by-NULL, and `F3-SEC-TOP3-6M-TREND` separately as
ineligible-on-`owner inputs` — **two tests, two different reasons** (corrected in reconciliation
round 2; an earlier brief called both NULL-DSR traps, which is wrong about F3). Only the F9 one
describes the **pre-remeasure** state, and it stays valid as written — but only because of *how*
it is written. Running this phase's batch against a database changes that
runtime state, and the distinction is:

- **Safe, and must stay safe:** any phase-4 test that builds its own fixture database (`seed(conn)`
  into a `tmp_path`, no `trial_moments` written) and asserts `dsr_at(...) is None` /
  `verdict(...).derived is False` for a seed row. Nothing this phase does touches a fresh fixture;
  the seed import writes no moments. These are unconditionally safe.
- **State-dependent, and will break the day the batch is run against the committed database:** any
  phase-4 test that opens the *committed* `lab/lab.sqlite` (via `store.connect_readonly` /
  `store.COMMITTED_DB`) and asserts that `F9-SPY200M70-MOM30` has no DSR, or that
  `trial_moments` holds some fixed count. **Reconciled, round 2:** phase 4 now has exactly one
  such test, `test_f9_the_one_seed_row_held_out_by_the_luck_test_alone`, and it skips itself when
  F9 already has a moments row. Phase 4's F3 test
  (`test_f3_stays_ineligible_on_owner_inputs_whatever_its_luck_test_says`) is **not**
  state-dependent and must stay that way: F3 is out on `owner inputs`, which no DSR touches.
  Phase 4's eligible-set assertion (`== ["M0020-W-NOSTOP", "M0022-W-TV14", "M0022-W-TV16"]`,
  three) is also safe: under D12 this phase's measurements add no fourth member.

**This phase does not run the batch against the committed database and does not commit
`lab/lab.sqlite`** (invariant 6, decision D5: phase 4 is the binary's sole writer). It ships the
command, the tests and the verification recipe against a copy. So no phase-4 test breaks when this
phase lands. The handoff below names what must happen before anyone runs it for real.

---

## Interface Contract

**Creates** — all in `engine/src/seer_engine/lab/remeasure.py`, appended to phase 3's module:

- `remeasure.METRIC_TOL`, `remeasure.SEED_PREFIX`, `remeasure.SEED_METHOD`, `remeasure.SEED_ALL`,
  `remeasure.SEED_METRICS`, `remeasure.REGISTRY_FILE`
- `remeasure.Observed`, `remeasure.MetricCheck`, `remeasure.SeedTrial`, `remeasure.SeedReproduced`,
  `remeasure.SeedPlan`, `remeasure.SeedReport`, `remeasure.SeedVerdict`
- `remeasure.is_seed_id`, `remeasure.seed_var_trials`, `remeasure.seed_preflight`,
  `remeasure.observe`, `remeasure.run_chunk`, `remeasure.reproduce`, `remeasure.remeasure_seed`,
  `remeasure.seed_verdicts`, `remeasure.format_seed_report`
- `engine/tests/test_lab_remeasure_seed.py` (new, **16 tests**)

**Signature changes:** **one, annotation-only.**
`remeasure._moments_row(r: Reproduced, measured: str)` -> `_moments_row(r: Reproduced |
SeedReproduced, measured: str)`. No call site changes, no runtime behaviour changes; the module
has `from __future__ import annotations`, so the annotation is never evaluated. Phase 3 asked that
`_moments_row` be reused rather than forked, and this is the cost.

**Text-only changes to phase-3 symbols (no signature, no behaviour):**
- `remeasure.resolve_method`'s docstring and its `LabError` message, which today assert that the
  `H-*` seed families "recorded no DSR and have no method file, so there is nothing to re-run and
  nothing to reproduce". That sentence is false after this phase. It is replaced with a pointer to
  the seed path. Presented as an exact diff in Step 2.
- `commands/lab.py`'s `remeasure` subparser gains `--only` and `--chunk`; its `method` positional's
  `metavar`/`help` widen; `_remeasure` gains a two-line dispatch at its top. All three are edits to
  regions phase 3 created and no other phase touches.

**Deletes:** none. **Renames:** none.

**Requires (from earlier phases):**

| symbol | phase | shape assumed |
|---|---|---|
| `store.MomentsRow(trial_n, sr_daily, t, skew, kurt, var_trials, n_at_run, measured)` | 2 | frozen dataclass, keyword-constructible, `measured` has no default |
| `store.insert_moments(conn, rows)` | 2 | caller holds the transaction; empty sequence is a no-op |
| `store.moments_of(conn, trial_n)` | 2 | `sqlite3.Row \| None` |
| `remeasure._moments_row`, `remeasure._g`, `remeasure._e`, `remeasure.daily_moments` (the re-export phase 3 imports) | 3 | as phase 3 defines them |
| `remeasure.resolve_method`, `remeasure.preflight`, `remeasure.remeasure` | 3 | unchanged; the lab-method path this phase dispatches around |
| `commands.lab._remeasure`, the `remeasure` subparser, the `"remeasure"` `_HANDLERS` entry | 3 | exist; this phase edits them in place |
| `store.verdict(conn, trial, *, at=None, policy=None) -> Verdict(dsr, failed, eligible, n, policy, derived)` | 4 | report only |
| `store.gate(conn, policy=None) -> Gate(n, policy)` | 4 | report only |
| `store.dev_sharpe_variance(conn) -> float \| None` | 4 | **the variance the gate deflates by** (D12); the report prints it and the recorded one side by side |
| `store.DSR_MIN` | 4 | report only (0.90 after phase 4) |
| `npolicy.effective_n(conn, policy) -> NCount` | 1 | tests only, for the N-invariance assertion |

**Leaves alone (owned by others):**
- `backtest/registry.py` — the frozen P7a record (design §2). Read only; never imported for write,
  never edited, never re-ordered.
- `lab/seed.py` — read for its constants in the report header only.
- `trials`, `methods`, `methods.status`, `insights`, `prereg` — no INSERT, UPDATE or DELETE
  anywhere in this phase's code against anything but `trial_moments`.
- `store.verdict`, `store.dsr_at`, `store.DSR_MIN`, `store.DSR_POLICY`, `TRANSITIONS`, the
  committed `lab/lab.sqlite` (Phase 4)
- `tuning.MAX_DRAWDOWN` (Phase 8), `dev.deflated_sharpe`, `DEV_END`, the D9 guard (frozen)
- `commands/lab.py`'s `_status`, `_luck`, `_reevaluate` and their subparsers (Phases 4, 5)
- `lab/npolicy.py` (Phase 1), `paper/roster.py` (Phase 6), `docs`, `web` (Phase 7)

**Invariants this phase could break, and the structure that stops it:**

- **N MUST NOT MOVE (the brief's CRITICAL).** The module's only write is `store.insert_moments`
  into `trial_moments`, whose rows are not `trials` rows. `store.dev_trial_count` counts
  `trials WHERE window='dev'`; `npolicy.effective_n("all-trials").n` is that count. Neither can
  observe a `trial_moments` insert. `test_a_full_batch_does_not_move_n` asserts both, before and
  after, on a database where all 54 are written.
- **`var_trials` must not move either.** `store.dev_daily_sharpes` reads `trials.sharpe`, which
  these 54 rows already have and which this phase never writes.
  `test_a_full_batch_does_not_move_the_trial_sharpe_variance` asserts
  `store.dev_sharpe_variance` and `store.dev_daily_sharpes` are identical before and after.
- **Invariant 2 (no test-window look).** Five noes, four structural: (1) `seed_preflight` refuses
  any seed method with a `window='test'` trial before a store is opened; (2) the CLI hands
  `research.load_store` no `window`, so it defaults to `DEV_WINDOW` and refuses a test store by
  name; (3) `remeasure_seed` refuses `data.window != research.DEV_WINDOW`; (4) `run_chunk` calls
  `dev.run_registry` with no `window` keyword, and neither `run_chunk`, `measure`-side helper nor
  `remeasure_seed` has a `window` parameter to pass one; (5) a test asserts both the absent
  signatures and the absent kwarg in the captured call.
- **Invariant 3 (`trials` append-only).** `test_a_full_batch_writes_only_trial_moments` snapshots
  every column of all 110 `trials` rows and all 14 `methods` rows and asserts byte-equality.
- **Invariant 6 (one writer for `lab.sqlite`).** This phase commits source and tests only. Its
  manual verification runs against `SEER_LAB_DB` pointed at a copy.

---

## Files

| File | Action | What changes |
|---|---|---|
| `engine/src/seer_engine/lab/remeasure.py` | modify | +3 imports; `_moments_row`'s annotation widened; `resolve_method`'s docstring and message corrected; a new `the P7a seed` section appended (constants, 7 dataclasses, 9 functions) |
| `engine/src/seer_engine/commands/lab.py` | modify | the `remeasure` subparser gains `--only`/`--chunk` and a widened `method` positional; `_remeasure` gains a 2-line dispatch; one usage-docstring line |
| `engine/tests/test_lab_remeasure_seed.py` | create | 16 tests |

---

## Implementation Steps

### Step 1: three imports at the top of `remeasure.py`

**File:** `engine/src/seer_engine/lab/remeasure.py`, the import block phase 3 wrote
(immediately after `from __future__ import annotations`).

**Change:** add `re`, widen the `collections.abc` import, and import the frozen REGISTRY.
Presented as a diff against phase 3's block:

```diff
 from __future__ import annotations
 
 import logging
 import math
+import re
 import sqlite3
 import statistics
-from collections.abc import Sequence
+from collections.abc import Iterable, Iterator, Sequence
 from dataclasses import dataclass
 from pathlib import Path
 from typing import Any
 
 from seer_engine import research
 from seer_engine.backtest import dev
 from seer_engine.backtest.book_runner import TRADING_DAYS
 from seer_engine.backtest.dev import Candidate, DevRow
+from seer_engine.backtest.registry import REGISTRY
 from seer_engine.commands.backtest_dev import daily_moments, registry_problem
 from seer_engine.lab import store
 from seer_engine.lab.method import METHOD_ID, Method, config_digest, source_sha
```

**Impact:** `lab/seed.py` already imports `REGISTRY` into the lab package, so this closes no new
cycle. `registry.py` is pure and imports nothing from `lab`.

---

### Step 2: two text corrections to phase-3 symbols

**File:** `engine/src/seer_engine/lab/remeasure.py` — `resolve_method`.

**Change:** phase 3's docstring and error message assert that the `H-*` families can never be
re-run. After this phase they can. Diff against phase 3's text:

```diff
 def resolve_method(method_id: str) -> tuple[Method, Path]:
     """``(METHOD, its file)`` for a lab method id (``store.LabError`` otherwise).
 
-    ``H-*`` ids -- the P7a seed families -- are refused by shape. Their trials carry
-    ``dsr IS NULL`` by construction (``lab/seed.py:136``, "P7a reported it for one row only"), so
-    there is no recorded verdict for a re-run to reproduce and no method file to re-run.
+    ``H-*`` ids -- the P7a seed families -- are refused *here* by shape, because they have no
+    method file: their candidates live in the frozen ``backtest/registry.py``, not in
+    ``lab/methods/``. They are not unreachable. ``seed_preflight`` below takes them, re-runs them
+    out of the REGISTRY and verifies the re-run against the six metrics the lab recorded, because
+    their ``dsr`` is NULL by construction (``lab/seed.py:136``) and cannot be the check.
     """
     from seer_engine.lab.method import discover
 
     if METHOD_ID.fullmatch(method_id) is None:
         raise store.LabError(
             f"{method_id!r} is not a lab method id; `lab remeasure` takes a method like M0022. "
-            f"The P7a seed families (H-*) recorded no DSR and have no method file, so there is "
-            f"nothing to re-run and nothing to reproduce"
+            f"For the P7a seed families, name them instead: `lab remeasure H-P7A` re-measures all "
+            f"54 seed trials out of the frozen registry, and `lab remeasure H-P7A-F9` one family"
         )
```

**File:** same module — `_moments_row`.

**Change:** widen the annotation and say why, so a reader of the seed path finds it.

```diff
-def _moments_row(r: Reproduced, measured: str) -> "store.MomentsRow":
+def _moments_row(r: Reproduced | SeedReproduced, measured: str) -> "store.MomentsRow":
     """One ``trial_moments`` row from a reproduced trial (phase 2 owns the dataclass).
 
+    Takes either kind of reproduction: a lab-method one, verified by reproducing the recorded
+    ``dsr``, or a P7a seed one, verified by reproducing the six recorded metrics. Both expose the
+    same seven attributes, and the row this builds says nothing about which check was used --
+    deliberately, because the row is the measurement, not the audit of it.
+
     ``n_at_run`` is the trial's **recorded** ``n_trials_at_run``, not today's dev trial count: the
     row documents the measurement that was made, and phase 4 derives a verdict under the current
     policy from the moments beside it.
```

**Impact:** none at runtime. `from __future__ import annotations` makes every annotation a string,
so the forward reference to `SeedReproduced` (defined later in the file) is never evaluated.

---

### Step 3: the seed path, appended to `remeasure.py`

**File:** `engine/src/seer_engine/lab/remeasure.py` — appended after phase 3's `format_report`,
at the end of the module.

**Code:**

```python
# =========================================================================== the P7a seed
#
# The lab's first 54 dev trials were not run by the lab. `lab seed` imported them from P7a's
# committed report files as summary rows (`lab/seed.py`), so their daily moments -- the Sharpe,
# the number of returns, the skew and the kurtosis the deflated Sharpe needs -- were never
# captured, and `trials.dsr` is NULL for every one of them ("P7a reported it for one row only",
# `seed.py:136`). They nonetheless count toward N: `dev_trial_count` is 110, and 54 of those 110
# are these. They pay the full multiple-testing penalty and receive no luck verdict in return.
# Under phase 4's rule a NULL DSR fails the luck test, so they are permanently ineligible by data
# gap rather than by merit.
#
# This section closes the gap the only honest way: re-run them. Every one of the 54 is still in
# the frozen `backtest/registry.py` (design §2), and every one of their `config_digest` values
# still matches the candidate there, so the configuration is provably the one that was measured.
#
# **The check cannot be phase 3's.** A lab-method re-run is verified by reproducing the recorded
# `dsr` to 1e-6; a seed trial has no recorded `dsr`, so that check does not exist. It is replaced
# by reproduction of the six metrics the lab *did* record -- `sharpe`, `cagr`, `max_drawdown`,
# `profit_factor`, `total_return` and `trades` -- at `METRIC_TOL`, and a trial that misses on any
# of them is reported and **not written**. A trial whose re-run does not reproduce its recorded
# numbers is not the same measurement, and luck-testing it as though it were would launder a
# different backtest into the lab's history.
#
# **What it writes:** `trial_moments` rows, and nothing else -- the same single write phase 3
# makes. `trials.dsr` stays NULL on these rows forever. There is no DSR backfill: the verdict is
# phase 4's `store.verdict` computing it from the moments at the current gate N, which is the
# whole point of deriving a verdict instead of recording one.
#
# **N does not move.** These 54 trials are already inside `dev_trial_count`. Adding
# `trial_moments` rows adds no `trials` row, so neither `store.dev_trial_count` nor
# `npolicy.effective_n(conn, "all-trials")` can observe this command. Nor does the trial-Sharpe
# variance: `store.dev_daily_sharpes` reads `trials.sharpe`, which these rows already carry and
# this code never writes.


SEED_PREFIX = "H-P7A"
SEED_ALL = SEED_PREFIX  # `lab remeasure H-P7A` = every seed family
SEED_METHOD = re.compile(r"H-P7A(?:-([A-Z0-9]+))?\Z")

# The file the 54 candidates come out of. Frozen and append-only by its own rules (handover D6);
# this module reads it and never writes it.
REGISTRY_FILE = Path(dev.__file__).with_name("registry.py")

# The tolerance on a seed re-run, and the reason for its shape.
#
# These rows were imported from `docs/backtests/2026-10-04-p7a-dev-exploration-rows.csv`, whose
# every float is written to six decimal places. Decimal rounding to 6 dp bounds the
# recorded-vs-true error at 5e-7 **absolute**, independent of magnitude -- which is why this is an
# absolute tolerance and not the relative one phase 3's `SHARPE_TOL` uses on full-precision
# engine output. A relative bound would be the wrong shape at both ends of the range present here:
# `cagr = 0.031191` needs 1.6e-5 relative to survive the same rounding, while `total_return =
# 18.648246` at 1e-6 relative would admit 1.9e-5, which is 37x the rounding bound and wide enough
# for a real divergence to pass.
#
# 1e-6 is 2x the rounding bound. Measured across all 54 on the committed database and today's dev
# store, the worst delta on any metric is 4.986e-07 -- under the bound, with no exceptions -- so
# the headroom exists for a libm or platform ulp and for nothing larger. A genuine divergence is
# orders of magnitude bigger: a changed research store moves these metrics in the third decimal.
METRIC_TOL = 1e-6  # absolute, per metric

# The six recorded metrics a seed re-run must reproduce, each paired with how to read it off a
# fresh `Observed`. `trades` is compared exactly, as an integer; the five floats at METRIC_TOL.
#
# `mar`, `spy_tr_return` and `spy_tr_cagr` are deliberately absent. `mar` is
# `cagr / max_drawdown`, algebraically implied by two entries already here; the two `spy_tr_*`
# columns are the benchmark and are identical across all 54, so they carry no per-candidate
# information. Checking them would add arithmetic, not evidence.
SEED_METRICS: tuple[str, ...] = (
    "sharpe",
    "cagr",
    "max_drawdown",
    "profit_factor",
    "total_return",
    "trades",
)


@dataclass(frozen=True)
class Observed:
    """What one re-run says about one candidate: the four DSR inputs and the six checked metrics.

    This is the seam the tests replace (``run_chunk``), so the whole verification, chunking,
    idempotence and reporting path can be exercised without a 135 MB research store. ``t``,
    ``sr_daily``, ``skew`` and ``kurt`` are ``daily_moments`` on the run's daily returns; the six
    metrics are read straight off ``DevRow.stats``.
    """

    t: int
    sr_daily: float
    skew: float
    kurt: float
    sharpe: float | None
    cagr: float | None
    max_drawdown: float | None
    profit_factor: float | None
    total_return: float | None
    trades: int


@dataclass(frozen=True)
class MetricCheck:
    """One recorded metric against its re-measured value.

    ``ok`` is the whole rule, in one place:

    - ``trades`` is an **exact** integer comparison. It is the sharpest of the six, because it
      pins the trade sequence itself: a changed universe, signal or fill rule cannot reproduce a
      trade count by coincidence.
    - a metric recorded NULL reproduces only as ``None``, and one recorded non-NULL only as
      non-``None``. ``REF-SPY-HOLD`` is the real case -- a 0-trade buy-and-hold reference whose
      ``profit_factor`` is NULL in the P7a file and ``None`` on the re-run. That is a match.
    - every other float: ``abs(measured - recorded) <= METRIC_TOL``.
    """

    name: str
    recorded: float | int | None
    measured: float | int | None

    @property
    def delta(self) -> float | None:
        if self.recorded is None or self.measured is None:
            return None
        return abs(float(self.measured) - float(self.recorded))

    @property
    def ok(self) -> bool:
        if (self.recorded is None) != (self.measured is None):
            return False
        if self.recorded is None:
            return True
        if self.name == "trades":
            return int(self.measured) == int(self.recorded)
        delta = self.delta
        return delta is not None and delta <= METRIC_TOL


@dataclass(frozen=True)
class SeedTrial:
    """One recorded seed trial beside the frozen REGISTRY candidate that produced it."""

    trial: sqlite3.Row
    candidate: Candidate

    @property
    def n(self) -> int:
        return int(self.trial["n"])

    @property
    def candidate_id(self) -> str:
        return str(self.trial["candidate_id"])


@dataclass(frozen=True)
class SeedReproduced:
    """One seed trial, re-measured: its fresh moments and every metric check.

    Exposes the same seven attributes ``_moments_row`` reads off phase 3's ``Reproduced``
    (``trial_n``, ``sr_daily``, ``t``, ``skew``, ``kurt``, ``var_trials``, ``n_at_run``), so the
    one row-builder serves both paths.
    """

    trial_n: int
    candidate_id: str
    n_at_run: int
    t: int
    sr_daily: float
    skew: float
    kurt: float
    var_trials: float | None
    checks: tuple[MetricCheck, ...]

    @property
    def ok(self) -> bool:
        """True when every one of the six recorded metrics was reproduced."""
        return all(c.ok for c in self.checks)

    @property
    def misses(self) -> tuple[MetricCheck, ...]:
        return tuple(c for c in self.checks if not c.ok)


@dataclass(frozen=True)
class SeedPlan:
    """What a seed re-measurement would do, decided from the database and the REGISTRY alone."""

    method_id: str  # "H-P7A" for all families, "H-P7A-F9" for one
    todo: tuple[SeedTrial, ...]  # trials with no moments row yet, in trial order
    present: tuple[int, ...]  # trial numbers that already have one
    var_trials: float | None  # the P7a search's own trial-Sharpe variance (see seed_var_trials)
    n_at_run: int  # the N every seed row records: 54

    @property
    def nothing_to_do(self) -> bool:
        return not self.todo


@dataclass(frozen=True)
class SeedReport:
    """What one seed re-measurement did."""

    method_id: str
    measured: tuple[SeedReproduced, ...]
    written: tuple[int, ...]
    blocked: tuple[int, ...]  # re-ran, did not reproduce, deliberately not written
    skipped: tuple[int, ...]  # already had moments when this started
    var_trials: float | None
    chunks: int


@dataclass(frozen=True)
class SeedVerdict:
    """One re-measured seed trial as the gate now reads it (phase 4 decides; this only prints)."""

    trial_n: int
    candidate_id: str
    dsr: float | None  # store.verdict's number: today's lab-wide variance, at the gate's N (D12)
    dsr_recorded_var: float | None  # the same moments deflated by the recorded var_trials, for
    #                                 contrast only -- never a verdict (D12)
    luck_ok: bool
    owner_misses: tuple[str, ...]  # every failure label that is not the luck label
    eligible: bool
    mar: float | None


def is_seed_id(method_id: str) -> bool:
    """True for ``H-P7A`` and ``H-P7A-<FAM>``: the ids ``lab remeasure`` routes to the seed path."""
    return SEED_METHOD.fullmatch(method_id.strip().upper()) is not None


def seed_var_trials(conn: sqlite3.Connection) -> float | None:
    """The trial-Sharpe variance the P7a search was its own population of: the 54 seed trials'
    recorded daily Sharpes.

    ``runner.trial_rows`` computes ``var_trials`` as ``statistics.variance(prior + new_sharpes)``
    where ``prior`` is every dev trial that already existed. The seed import is the lab's first
    batch -- ``prior`` is empty and the batch is all 54 -- so this is literally the number
    ``lab run`` would have computed had P7a been run through the lab. It is a reconstruction of a
    historical fact, the same quantity phase 3's ``batches_of`` rebuilds for a lab method.

    **Read off the recorded ``trials.sharpe`` column, not off the re-run**, for three reasons and
    the first is decisive:

    1. it makes the value a constant settled in ``seed_preflight``, identical whether the batch
       runs as one call or as six interrupted ones. That is what makes this command resumable:
       computing it from fresh daily Sharpes would require all 54 re-runs in hand before the first
       row could be written;
    2. ``trials.sharpe`` *is* P7a's measurement of record. The re-run is evidence that the record
       is sound, not a replacement for it;
    3. the difference is immaterial -- measured, the recorded column gives 2.006690619e-04 and the
       fresh daily Sharpes give 2.006691421e-04, a gap of 8.0e-11, four orders of magnitude below
       anything the deflated Sharpe can resolve.

    None when fewer than two seed rows carry a Sharpe -- the same condition under which
    ``trials.dsr`` is NULL, and under which phase 2's ``MomentsRow.var_trials`` is None.
    """
    sharpes = [
        float(r[0]) / math.sqrt(TRADING_DAYS)
        for r in conn.execute(
            "SELECT sharpe FROM trials WHERE window = 'dev' AND dsr IS NULL AND sharpe IS NOT NULL "
            "ORDER BY n"
        )
    ]
    return statistics.variance(sharpes) if len(sharpes) >= 2 else None


def seed_preflight(
    conn: sqlite3.Connection,
    method_id: str,
    *,
    only: Sequence[str] = (),
    require_commit: bool = True,
) -> SeedPlan:
    """Every refusal the seed path makes from the database and the REGISTRY alone.

    Nothing here opens a research store, runs a backtest or writes a row, and the test-window
    refusal is made first -- the mirror of ``preflight``'s, and of ``runner.run_test`` refusing a
    dev store.

    ``method_id`` is ``H-P7A`` (every family) or ``H-P7A-<FAM>`` (one). ``only`` further narrows
    to named candidate ids, for re-trying a handful after a divergence.

    The guard that the re-run measures the same configuration is **per-trial
    ``config_digest`` equality** against the REGISTRY candidate, not a hash of the registry file.
    That is both stronger and more durable: the digest covers the candidate's trial-defining parts
    exactly (``lab/method.py``'s ``config_text``), and it stays true when the registry legitimately
    gains entries 55 and beyond, which a file hash would not.

    ``require_commit=False`` skips only the git cleanliness check on ``registry.py``; it never
    relaxes the digest comparison, which is the stronger of the two.
    """
    wanted = method_id.strip().upper()
    match = SEED_METHOD.fullmatch(wanted)
    if match is None:
        raise store.LabError(
            f"{method_id!r} is not a P7a seed id. `lab remeasure H-P7A` re-measures all 54 seed "
            f"trials; `lab remeasure H-P7A-F9` re-measures one family"
        )
    family = match.group(1)
    looks = conn.execute(
        "SELECT candidate_id, run_at FROM trials WHERE window = 'test' "
        "AND method_id LIKE 'H-P7A%' ORDER BY n"
    ).fetchall()
    if looks:
        spent = ", ".join(f"{r['candidate_id']} on {r['run_at']}" for r in looks)
        raise store.LabError(
            f"a P7a seed family has already had a look at the test window ({spent}). "
            f"`lab remeasure` re-runs the dev window and will not run anything beside a spent "
            f"look: the one look is never given back"
        )
    if family is None:
        rows = conn.execute(
            "SELECT * FROM trials WHERE window = 'dev' AND method_id LIKE 'H-P7A-%' ORDER BY n"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM trials WHERE window = 'dev' AND method_id = ? ORDER BY n", (wanted,)
        ).fetchall()
    if not rows:
        known = ", ".join(
            str(r[0])
            for r in conn.execute(
                "SELECT DISTINCT method_id FROM trials WHERE method_id LIKE 'H-P7A-%' "
                "ORDER BY method_id"
            )
        )
        raise store.LabError(
            f"no dev trial for {wanted} in this lab. Seed families present: {known or '(none)'}"
        )
    if only:
        picked = {c.strip().upper() for c in only}
        unknown = picked - {str(r["candidate_id"]).upper() for r in rows}
        if unknown:
            raise store.LabError(
                f"--only names {', '.join(sorted(unknown))}, which {wanted} has no trial for"
            )
        rows = [r for r in rows if str(r["candidate_id"]).upper() in picked]
    scored = [r for r in rows if r["dsr"] is not None]
    if scored:
        names = ", ".join(str(r["candidate_id"]) for r in scored)
        raise store.LabError(
            f"{wanted}: {names} already has a recorded DSR, so it is not a seed row and the seed "
            f"path's metric check is the wrong verification for it. `lab remeasure <method>` "
            f"re-measures a recorded lab method against its recorded DSR"
        )
    unverifiable = [r for r in rows if r["sharpe"] is None]
    if unverifiable:
        names = ", ".join(str(r["candidate_id"]) for r in unverifiable)
        raise store.LabError(
            f"{wanted}: {names} recorded no Sharpe, so a re-run cannot be checked against what "
            f"the lab recorded. Nothing is backfilled for a trial whose numbers cannot be "
            f"reproduced"
        )
    if require_commit:
        problem = registry_problem(REGISTRY_FILE)
        if problem is not None:
            raise store.LabError(
                f"{wanted}: {problem}. `lab remeasure` re-runs the committed registry -- the same "
                f"frozen file the P7a trials ran under (design §2) -- and nothing else"
            )
    by_id = {c.id: c for c in REGISTRY}
    pairs: list[SeedTrial] = []
    for row in rows:
        cid = str(row["candidate_id"])
        cand = by_id.get(cid)
        if cand is None:
            raise store.LabError(
                f"{wanted}: {cid} is recorded as a trial but is not in backtest/registry.py, so "
                f"there is nothing to re-run. The registry is append-only (handover D6); an entry "
                f"has gone missing and that is a bigger problem than this command"
            )
        if config_digest(cand) != str(row["config_digest"]):
            raise store.LabError(
                f"{wanted}: {cid}'s registry entry hashes {config_digest(cand)[:12]} but its trial "
                f"ran under {str(row['config_digest'])[:12]}. The registry entry changed after it "
                f"ran, so the re-run would measure a different configuration"
            )
        pairs.append(SeedTrial(trial=row, candidate=cand))
    n_at_run = {int(r["n_trials_at_run"]) for r in rows}
    if len(n_at_run) != 1:
        raise store.LabError(
            f"{wanted}: the seed rows record more than one N ({sorted(n_at_run)}), but the seed "
            f"import writes one batch with one N. The database has been edited"
        )
    have = {p.n for p in pairs if store.moments_of(conn, p.n) is not None}
    return SeedPlan(
        method_id=wanted,
        todo=tuple(p for p in pairs if p.n not in have),
        present=tuple(sorted(have)),
        var_trials=seed_var_trials(conn),
        n_at_run=n_at_run.pop(),
    )


def observe(row: DevRow) -> Observed | None:
    """``Observed`` for one fresh ``DevRow``; None when it produced no usable daily moments."""
    moments = daily_moments(row.stats.daily_returns)
    if moments is None:
        return None
    sr, skew, kurt = moments
    m = row.stats.metrics
    return Observed(
        t=len(row.stats.daily_returns),
        sr_daily=sr,
        skew=skew,
        kurt=kurt,
        sharpe=None if row.stats.sharpe is None else float(row.stats.sharpe),
        cagr=None if m.cagr is None else float(m.cagr),
        max_drawdown=None if m.max_drawdown is None else float(m.max_drawdown),
        profit_factor=None if m.profit_factor is None else float(m.profit_factor),
        total_return=None if m.total_return is None else float(m.total_return),
        trades=int(m.trades),
    )


def run_chunk(
    data: research.ResearchData, candidates: Sequence[Candidate]
) -> dict[str, Observed | None]:
    """Re-run ``candidates`` on the dev window; ``{candidate id: Observed}``.

    The dev window is not a parameter and not a choice: this function has no ``window``
    parameter, and ``dev.run_registry`` is called with no ``window`` keyword, so the run is
    bounded by ``DEV_WINDOW`` by construction. ``remeasure_seed`` has already refused any ``data``
    that is not the dev window before this is reached.

    Splitting the 54 into chunks is free of correctness cost. ``run_registry`` rebuilds its
    per-allocator ``prepare_for`` cache per call, so a chunk pays re-preparation time, but the
    measurement is identical: re-running ``F1-SPY-SMA200-M``, ``F3-SEC-TOP3-6M-TREND``,
    ``F4-MOM12-N20-TREND`` and ``F9-SPY200M70-MOM30`` alone and inside the full 54-candidate call
    gives **bit-identical** annualized Sharpes and ``t``. That is what makes it safe for the batch
    to be interrupted and resumed at any boundary.

    This is the seam the tests replace. Everything above it -- the refusals, the digest guard --
    and everything below it -- the metric checks, the chunked write, the report -- is exercised
    against a substituted ``run_chunk`` without a research store.
    """
    out: dict[str, Observed | None] = {}

    def on_result(i: int, result: Any, row: DevRow) -> None:
        out[row.candidate.id] = observe(row)

    dev.run_registry(
        data.market, data.dividends, data.spy_dividends, list(candidates), on_result=on_result
    )
    return out


def reproduce(seed: SeedTrial, obs: Observed, var_trials: float | None) -> SeedReproduced:
    """One recorded seed trial beside its re-run, with every metric check decided.

    The recorded ``dsr`` is NULL by construction, so phase 3's check -- reproduce the recorded
    DSR to 1e-6 -- does not exist here. These six metrics are its replacement: six independent
    properties of one equity curve, each of which a changed store, method or engine would move far
    outside ``METRIC_TOL``.
    """
    t = seed.trial
    checks = tuple(
        MetricCheck(name=name, recorded=t[name], measured=getattr(obs, name))
        for name in SEED_METRICS
    )
    return SeedReproduced(
        trial_n=seed.n,
        candidate_id=seed.candidate_id,
        n_at_run=int(t["n_trials_at_run"]),
        t=obs.t,
        sr_daily=obs.sr_daily,
        skew=obs.skew,
        kurt=obs.kurt,
        var_trials=var_trials,
        checks=checks,
    )


def remeasure_seed(
    conn: sqlite3.Connection,
    plan: SeedPlan,
    data: research.ResearchData,
    *,
    chunk: int = 54,
    on_chunk: Any = None,
) -> SeedReport:
    """Re-run ``plan.todo`` on the dev window in chunks and append the ``trial_moments`` rows.

    **Resumable and idempotent, by construction.** Each chunk is re-run, verified and committed
    before the next begins, so an interrupt loses at most the chunk in flight and nothing that was
    already written. ``plan.todo`` holds only trials with no moments row, and the set is re-read
    inside each chunk's write lock, so a parallel explorer session that wrote the same rows in
    between is a skip rather than a conflict -- ``trial_moments`` is append-only (phase 2's
    triggers) and "already there" is always the answer. Running the whole command a second time
    writes nothing and loads no research store (``commands/lab.py`` checks ``nothing_to_do``
    first).

    ``plan.var_trials`` is the same number for every chunk because it is read off the database in
    ``seed_preflight``, never off the re-run. That is what makes the output independent of where
    the chunk boundaries fall, and independent of how many times the job was interrupted.

    **A divergent trial is reported, not raised, and is not written.** This is the one deliberate
    difference from phase 3's ``check``, which aborts the whole command on one bad trial. Phase 3
    can be all-or-nothing because a lab method is two to five trials measured together; here one
    drifted ETF would sink fifty-three sound re-measurements across eleven unrelated families. The
    rule the brief sets is kept exactly: a trial whose re-run does not reproduce its recorded
    numbers is not the same measurement and **must not** be luck-tested as though it were -- so it
    is named in the report, counted in ``blocked``, and no moments row is written for it.

    ``on_chunk(index, total, written, blocked)``, when given, is called after each chunk commits;
    ``commands/lab.py`` uses it to print progress on a job that has no other output until the end.
    """
    if data.window != research.DEV_WINDOW:
        w = data.window
        raise store.LabError(
            f"{plan.method_id}: this research store was built for the {w.name!r} window "
            f"({w.start}..{w.end}); `lab remeasure` re-runs the dev window and nothing else. "
            f"Build it with `python -m seer_engine research_store`"
        )
    size = max(1, min(int(chunk), dev.MAX_CANDIDATES))
    groups: list[tuple[SeedTrial, ...]] = [
        tuple(plan.todo[i : i + size]) for i in range(0, len(plan.todo), size)
    ]
    stamp = store.now_iso()  # when this backfill measured, not when P7a ran
    measured: list[SeedReproduced] = []
    written: list[int] = []
    blocked: list[int] = []
    for index, group in enumerate(groups):
        fresh = run_chunk(data, [s.candidate for s in group])
        here: list[SeedReproduced] = []
        for seed in group:
            obs = fresh.get(seed.candidate_id)
            if obs is None:
                raise store.LabError(
                    f"{plan.method_id}: {seed.candidate_id} produced no usable daily moments on "
                    f"the re-run but recorded a Sharpe of {_g(seed.trial['sharpe'])}; the re-run "
                    f"is not the recorded measurement. Nothing is written for this chunk"
                )
            here.append(reproduce(seed, obs, plan.var_trials))
        good = [r for r in here if r.ok]
        bad = [r for r in here if not r.ok]
        store.begin_immediate(conn)
        with conn:
            have = {
                r.trial_n for r in good if store.moments_of(conn, r.trial_n) is not None
            }  # a parallel session may have won the race
            rows = [_moments_row(r, stamp) for r in good if r.trial_n not in have]
            store.insert_moments(conn, rows)
        measured.extend(here)
        written.extend(r.trial_n for r in rows)
        blocked.extend(r.trial_n for r in bad)
        if on_chunk is not None:
            on_chunk(index + 1, len(groups), len(rows), len(bad))
    return SeedReport(
        method_id=plan.method_id,
        measured=tuple(measured),
        written=tuple(written),
        blocked=tuple(blocked),
        skipped=plan.present,
        var_trials=plan.var_trials,
        chunks=len(groups),
    )


def seed_verdicts(
    conn: sqlite3.Connection, report: SeedReport
) -> tuple[SeedVerdict, ...]:
    """How the gate now reads every seed trial this run wrote moments for.

    Phase 4 decides; this only asks and prints. ``store.verdict`` re-derives the four threshold
    owner conditions from the trial's recorded columns against today's constants (so phase 8's 20%
    drawdown bar applies), carries ``owner inputs`` from the recorded string, and decides the luck
    test on the trial's DSR **at the gate's current N** -- which, now that these rows have moments,
    is a real number for the first time.

    ``v.dsr`` is **the gate's number**: `store.dsr_at` deflates by
    ``store.dev_sharpe_variance(conn)`` -- the trial-Sharpe variance over all 110 dev trials as the
    lab stands now -- on both of its routes, at the gate's current N (**Decision D12**).

    ``dsr_recorded_var`` is the same measured moments deflated instead by the ``var_trials``
    written beside the trial (the P7a search's own 54). **It is not a verdict and must never be
    read as one.** It is printed only so the size of the choice is on the terminal: the 54 seed
    rows are the only place in the lab where the two variances differ materially -- 2.0067e-04
    against 2.3950e-04 -- and they differ by enough to move ``F9-SPY200M70-MOM30`` from 0.8567
    (the gate's number, which fails) to 0.9031 (which would have passed). D12 settled that on the
    index's R2: pairing today's N with a variance frozen at the run date mixes bars on the other
    axis of the same formula. Showing both is what keeps the settled choice inspectable rather
    than buried in a constant nobody looked at.
    """
    g = store.gate(conn)
    out: list[SeedVerdict] = []
    for n in sorted(set(report.written)):
        trial = conn.execute("SELECT * FROM trials WHERE n = ?", (n,)).fetchone()
        if trial is None:  # unreachable: trial_moments has a foreign key onto trials(n)
            continue
        v = store.verdict(conn, trial, at=g)
        moments = store.moments_of(conn, n)
        alt: float | None = None
        if moments is not None and moments["var_trials"] is not None:
            alt = dev.deflated_sharpe(
                float(moments["sr_daily"]),
                g.n,
                float(moments["var_trials"]),
                int(moments["t"]),
                float(moments["skew"]),
                float(moments["kurt"]),
            )
        out.append(
            SeedVerdict(
                trial_n=n,
                candidate_id=str(trial["candidate_id"]),
                dsr=v.dsr,
                dsr_recorded_var=alt,
                luck_ok=v.dsr is not None and v.dsr >= store.DSR_MIN,
                owner_misses=tuple(f for f in v.failed if not f.startswith("DSR ")),
                eligible=v.eligible,
                mar=None if trial["mar"] is None else float(trial["mar"]),
            )
        )
    return out


def format_seed_report(
    conn: sqlite3.Connection, report: SeedReport, verdicts: Sequence[SeedVerdict]
) -> str:
    """The seed re-measurement report: what reproduced, what did not, and what the gate now says.

    The outcome is whatever it is. Nothing here rounds a candidate toward eligibility, and the
    second DSR column exists so that a candidate sitting on the bar is visibly sitting on the bar
    rather than quietly on one side of it.
    """
    from seer_engine.lab import seed as seed_mod

    g = store.gate(conn)
    today_var = store.dev_sharpe_variance(conn)
    out: list[str] = [
        f"{report.method_id}: {len(report.measured)} P7a seed trial(s) re-measured on the dev "
        f"window in {report.chunks} chunk(s)",
        "",
        f"  reproduction: the six recorded metrics ({', '.join(SEED_METRICS)}), "
        f"{METRIC_TOL:g} absolute on the floats and exact on trades. These rows came from "
        f"{seed_mod.P7A_REPORT} rounded to 6 dp, so the rounding bound is 5e-07 and the tolerance "
        f"is twice it",
        f"  store: the seed trials recorded {seed_mod.P7A_FINGERPRINT[:12]}..., this re-run "
        f"measured on a store the loader reported to the caller; a metric that did not reproduce "
        f"is listed below and was not written",
        f"  variance the GATE uses: {_e(today_var)} -- all {g.n} dev trials as the lab stands "
        f"now. Both of store.dsr_at's routes deflate by this (Decision D12)",
        f"  var_trials WRITTEN:     {_e(report.var_trials)} -- the 54 seed trials' own "
        f"daily-Sharpe variance, the number `lab run` would have computed for P7a's batch. "
        f"Historical record; shown in brackets below for contrast and never used as a verdict",
        f"  gate: N = {g.n} under policy {g.policy!r}, luck bar DSR >= {store.DSR_MIN:g}",
        "",
    ]
    if report.written:
        out.append(f"  wrote {len(report.written)} trial_moments row(s):")
        by_n = {v.trial_n: v for v in verdicts}
        for r in report.measured:
            if r.trial_n not in set(report.written):
                continue
            out.append(
                f"    #{r.trial_n} {r.candidate_id}  t={r.t}  sr_daily={_g(r.sr_daily)}  "
                f"skew={_g(r.skew)}  kurt={_g(r.kurt)}  N_at_run={r.n_at_run}"
            )
            v = by_n.get(r.trial_n)
            if v is None:
                continue
            luck = "PASS" if v.luck_ok else "fail"
            out.append(
                f"          DSR @ N={g.n} = {_g(v.dsr)}  luck: {luck} (bar {store.DSR_MIN:g})"
                f"   [with the recorded as-of-P7a variance: {_g(v.dsr_recorded_var)}]"
            )
            owner = "all pass" if not v.owner_misses else "; ".join(v.owner_misses)
            out.append(
                f"          owner conditions: {owner}   MAR {_g(v.mar)}   "
                f"-> {'ELIGIBLE' if v.eligible else 'not eligible'}"
            )
    if report.blocked:
        out.append("")
        out.append(
            f"  {len(report.blocked)} trial(s) did NOT reproduce what the lab recorded and were "
            f"deliberately NOT written -- a re-run that does not land on the recorded numbers is "
            f"not the same measurement:"
        )
        for r in report.measured:
            if r.ok:
                continue
            out.append(f"    #{r.trial_n} {r.candidate_id}")
            for c in r.misses:
                out.append(
                    f"          {c.name}: recorded {_g(c.recorded)}, measured {_g(c.measured)} "
                    f"(delta {_e(c.delta)}, tolerance "
                    f"{'exact' if c.name == 'trades' else f'{METRIC_TOL:g} absolute'})"
                )
        out.append(
            "    Rebuild the dev store these were measured on and try again, or leave them: a "
            "trial with no moments keeps the verdict it already has."
        )
    if report.skipped:
        out.append("")
        out.append(
            "  already recorded, left alone: " + ", ".join(f"#{n}" for n in report.skipped)
        )
    eligible = [v for v in verdicts if v.eligible]
    passing = [v for v in verdicts if v.luck_ok]
    out.append("")
    out.append(
        f"  of {len(report.written)} written: {len(passing)} now pass the luck bar, "
        f"{len(eligible)} pass every owner condition as well and are eligible"
        + (": " + ", ".join(v.candidate_id for v in eligible) if eligible else "")
    )
    out.append(
        f"  no trials row was inserted, updated or deleted; no method status moved; "
        f"trials.dsr is still NULL on every seed row and stays that way"
    )
    return "\n".join(out)
```

**Impact:** a new section in an existing module. Its only write is `store.insert_moments`. It
contains no INSERT, UPDATE or DELETE against `trials`, `methods` or anything else.

---

### Step 4: the subcommand's three edits in `commands/lab.py`

**Shared-file protocol.** Phases 3, 4 and 5 all write `commands/lab.py` at disjoint anchors (see
phase-3.md Step 2). **Every edit in this step is inside the region phase 3 created** — the
`remeasure` subparser, the `_remeasure` handler, and phase 3's own usage-docstring block. No other
phase touches any of them, and this phase touches nothing outside them. The `_HANDLERS` dict is
**not** edited: `"remeasure": _remeasure` is already there from phase 3.

Anchor on the quoted text, not on line numbers: whichever of phases 3, 4, 5 and 9 lands first
moves the others.

#### 4a — the usage docstring

**File:** `engine/src/seer_engine/commands/lab.py` — phase 3's `lab remeasure` block.
**Change:** widen the one line that names the argument.

```diff
-    lab remeasure M0022 [--store DIR]
+    lab remeasure M0022 | H-P7A | H-P7A-F9 [--store DIR] [--only IDS] [--chunk N]
                                     re-run a recorded method's variants on the dev window and
                                     write back the DSR inputs (trial_moments) its trials predate.
                                     Writes nothing else: no trials row, no status, no
                                     pre-registration. Idempotent, and refuses a method that has
                                     already had its test-window look
+                                    H-P7A re-measures all 54 P7a seed trials out of the frozen
+                                    registry and reports the DSR each now computes at the current
+                                    gate N; H-P7A-F9 does one family. A seed trial has no recorded
+                                    DSR, so the re-run is verified against the six metrics the lab
+                                    did record, and a trial that does not reproduce them is
+                                    reported and not written (exit 1)
```

**Impact:** documentation only.

#### 4b — the subparser

**File:** `engine/src/seer_engine/commands/lab.py` — phase 3's `remeasure` subparser.
**Change:** widen the positional's metavar and help, and add two options. The `--store` argument
phase 3 wrote is unchanged.

```diff
     s = sub.add_parser(
         "remeasure",
         help="recover the DSR inputs (trial_moments) of a method whose trials predate them",
     )
-    s.add_argument("method", metavar="M0022",
-                   help="the lab method whose recorded dev trials get their moments back")
+    s.add_argument("method", metavar="M0022|H-P7A",
+                   help="the lab method whose recorded dev trials get their moments back, or "
+                        "H-P7A for all 54 P7a seed trials / H-P7A-F9 for one seed family")
     s.add_argument(
         "--store",
         type=Path,
         default=Path(os.environ.get("SEER_RESEARCH_STORE") or research.STORE_DIR),
         help=f"dev-window research store (default: {research.STORE_DIR}, or "
              "$SEER_RESEARCH_STORE). A test store is refused by research.load_store before a "
              "byte is read: this command never names a test window and never spends a look",
     )
+    s.add_argument("--only", default=None, metavar="IDS",
+                   help="seed path only: a comma-separated list of candidate ids to re-measure "
+                        "instead of the whole set, for re-trying a handful after a divergence")
+    s.add_argument("--chunk", type=int, default=dev.MAX_CANDIDATES, metavar="N",
+                   help="seed path only: commit after every N backtests, so an interrupted job "
+                        f"loses at most N (default: {dev.MAX_CANDIDATES}, i.e. one call). "
+                        "Chunking is bit-identical to one call and costs only allocator "
+                        "re-preparation; the whole 54-trial batch takes about a minute")
```

**Impact:** `--only` and `--chunk` exist and are ignored by the lab-method path. `dev` is already
imported (`commands/lab.py:42`).

#### 4c — the handler

**File:** `engine/src/seer_engine/commands/lab.py` — phase 3's `_remeasure`.
**Change:** two lines at the top of the body dispatch to the seed path; everything phase 3 wrote
below stays exactly as it is. The new `_remeasure_seed` goes immediately after `_remeasure`.

```diff
     from seer_engine.lab import remeasure as rm
 
+    if rm.is_seed_id(args.method):
+        return _remeasure_seed(conn, args)
     method, path = rm.resolve_method(args.method)
     plan = rm.preflight(conn, method, path)
```

and, appended after `_remeasure`'s `return 0`:

```python
def _remeasure_seed(conn, args) -> int:
    """``lab remeasure H-P7A``: give the 54 P7a seed trials their DSR inputs, and say what follows.

    The lab's first 54 dev trials were imported from P7a's report files as summary rows, so their
    daily moments were never captured and ``trials.dsr`` is NULL for every one. They count toward
    N all the same -- 54 of the lab's 110 dev trials -- so they pay the full multiple-testing
    penalty and, under the rule that a DSR which cannot be evaluated fails the luck test, can
    never pass it. This re-runs them out of the frozen registry so the luck test they pay for is
    one they actually receive.

    **It writes ``trial_moments`` rows and nothing else.** No ``trials`` row is inserted, updated
    or deleted; ``trials.dsr`` stays NULL on these rows forever; no ``methods.status`` moves; no
    pre-registration is written. The verdict is not recorded here -- it is phase 4's
    ``store.verdict`` computing it from the moments at the current gate N, which is why there is
    no DSR backfill and why re-running this command can never change a recorded number.

    **N does not move.** Adding ``trial_moments`` rows adds no ``trials`` row, so
    ``store.dev_trial_count`` and ``npolicy.effective_n(conn, "all-trials")`` read the same before
    and after; and ``store.dev_daily_sharpes`` reads ``trials.sharpe``, which these rows already
    carry, so the trial-Sharpe variance does not move either. Both are printed at the end, before
    and after, so the invariant is visible rather than merely asserted in a test.

    The test window is unreachable from here by construction, not by care: ``seed_preflight``
    refuses before anything is opened if any seed family has a test trial, ``research.load_store``
    is called with no ``window`` so it defaults to ``DEV_WINDOW`` and refuses a test store by name,
    and ``remeasure_seed`` refuses a loaded store that is not the dev window and reaches
    ``dev.run_registry`` through ``run_chunk``, which has no window argument at all.

    Exit 0 when every re-run reproduced; **1 when any trial diverged** and was therefore not
    written -- the run is not a failure (the rest were written and the finding is printed per
    trial), but it is not a clean success either and an unattended caller should notice.
    """
    from seer_engine.lab import npolicy, remeasure as rm

    only = tuple(x for x in (args.only or "").split(",") if x.strip())
    plan = rm.seed_preflight(conn, args.method, only=only)
    n_before = store.dev_trial_count(conn)
    var_before = store.dev_sharpe_variance(conn)
    if plan.nothing_to_do:
        print(f"{plan.method_id}: every seed trial already has its moments; nothing to do.")
        print("  already recorded: " + ", ".join(f"#{n}" for n in plan.present))
        print(f"\nLab N (dev trials) is still {n_before}; test-window looks used: "
              f"{store.test_looks(conn)}")
        return 0
    if research.DEV_END != dev.DEV_END:
        raise store.LabError("research.DEV_END differs from dev.DEV_END; refusing to run")
    t0 = time.perf_counter()
    try:
        data = research.load_store(Path(args.store))
    except FileNotFoundError as e:
        raise store.LabError(
            f"research store {args.store} is missing {e.filename or e}; build it with "
            "`python -m seer_engine research_store`"
        ) from e
    except ValueError as e:
        raise store.LabError(
            f"{args.store}: {e}. `lab remeasure` asks load_store for the dev window and nothing "
            f"else, so a test-window store is refused here rather than re-measured"
        ) from e
    log.info("research store %s loaded (%.1fs)", data.fingerprint[:12], time.perf_counter() - t0)
    log.info(
        "re-measuring %d seed trial(s); the P7a trials recorded store %s, this store is %s",
        len(plan.todo), "5451195f", data.fingerprint[:8],
    )

    def progress(index: int, total: int, written: int, blocked: int) -> None:
        log.info("chunk %d/%d committed: %d written, %d blocked", index, total, written, blocked)

    report = rm.remeasure_seed(conn, plan, data, chunk=args.chunk, on_chunk=progress)
    print(rm.format_seed_report(conn, report, rm.seed_verdicts(conn, report)))
    n_after = store.dev_trial_count(conn)
    var_after = store.dev_sharpe_variance(conn)
    print(
        f"\nLab N (dev trials): {n_before} before, {n_after} after "
        f"({npolicy.effective_n(conn, 'all-trials').n} under the all-trials policy); "
        f"trial-Sharpe variance: {var_before!r} before, {var_after!r} after; "
        f"test-window looks used: {store.test_looks(conn)}"
    )
    return 1 if report.blocked else 0
```

**Impact:** `lab remeasure H-P7A` becomes reachable through the `"remeasure"` handler phase 3
registered. `time`, `dev`, `research`, `store`, `Path` and `log` are already imported.

---

### Step 5: the tests

**File:** `engine/tests/test_lab_remeasure_seed.py` (new)

**Change:** 14 tests. They replace one named seam — `remeasure.run_chunk` — so the whole path runs
against the real seeded database (`seed(conn)` imports the actual 54 P7a rows from the committed
CSVs) without a 282 MB research store. The headline tests are
`test_a_full_batch_does_not_move_n` and
`test_a_full_batch_does_not_move_the_trial_sharpe_variance`: the brief's CRITICAL, asserted on all
54 rows.

**Code:**

```python
"""``lab remeasure H-P7A`` (plan phase 9): the P7a seed's DSR inputs, recovered and luck-tested.

The 54 seed trials are real: ``seed(conn)`` imports them from the committed P7a report files, so
every test here runs against the lab's actual starting record rather than a fixture that resembles
it. What is faked is the backtest -- ``remeasure.run_chunk``, the one named seam -- because
re-running 54 candidates needs a 282 MB research store. ``perfect()`` builds the re-run that
reproduces each recorded row exactly; ``rounded()`` adds the 5e-07 decimal-rounding error the real
re-run exhibits; ``drifted()`` moves one metric past the tolerance.
"""

from __future__ import annotations

import inspect
import math
import statistics

import pytest

from seer_engine import research
from seer_engine.backtest import dev
from seer_engine.backtest.registry import REGISTRY
from seer_engine.lab import npolicy, remeasure, store
from seer_engine.lab.seed import seed

TD = math.sqrt(252)


@pytest.fixture()
def conn(tmp_path):
    c = store.connect(tmp_path / "lab.sqlite")
    seed(c)
    yield c
    c.close()


def _recorded(conn):
    return {
        str(r["candidate_id"]): r
        for r in conn.execute("SELECT * FROM trials WHERE window = 'dev' ORDER BY n")
    }


def perfect(conn, *, error: float = 0.0, drift: dict[str, tuple[str, float]] | None = None):
    """A ``run_chunk`` substitute that reproduces every recorded row, optionally imperfectly.

    ``error`` is added to every float metric (use 4.9e-07 for the real rounding error, 2e-06 to
    break the tolerance). ``drift`` moves one named metric of one named candidate by a delta,
    which is how a single divergent trial is produced without touching the other fifty-three.
    """
    rows = _recorded(conn)
    drift = drift or {}

    def run_chunk(data, candidates):
        out = {}
        for c in candidates:
            r = rows[c.id]
            bump = {}
            if c.id in drift:
                name, delta = drift[c.id]
                bump[name] = delta

            def val(name, base=None):
                v = r[name] if base is None else base
                if v is None:
                    return None
                return float(v) + error + bump.get(name, 0.0)

            out[c.id] = remeasure.Observed(
                t=4983,
                sr_daily=float(r["sharpe"]) / TD,
                skew=-0.3,
                kurt=9.0,
                sharpe=val("sharpe"),
                cagr=val("cagr"),
                max_drawdown=val("max_drawdown"),
                profit_factor=val("profit_factor"),
                total_return=val("total_return"),
                trades=int(r["trades"]) + int(bump.get("trades", 0)),
            )
        return out

    return run_chunk


class FakeData:
    """The dev window, and nothing else a re-run would reach: ``run_chunk`` is substituted."""

    window = research.DEV_WINDOW
    fingerprint = "399d0d254c7a"
    market = dividends = spy_dividends = None


class FakeTestData(FakeData):
    window = research.TEST_WINDOW


def _plan(conn, method_id="H-P7A", **kw):
    return remeasure.seed_preflight(conn, method_id, require_commit=False, **kw)


# ---- N must not move: the brief's CRITICAL --------------------------------------------------


def test_a_full_batch_does_not_move_n(conn, monkeypatch):
    """54 trial_moments rows, and the multiple-testing N is the same integer it was."""
    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn))
    n_before = store.dev_trial_count(conn)
    policy_before = npolicy.effective_n(conn, "all-trials").n
    assert n_before == 54 and policy_before == 54  # a freshly seeded lab is the 54 alone

    report = remeasure.remeasure_seed(conn, _plan(conn), FakeData())

    assert len(report.written) == 54
    assert report.blocked == ()
    assert store.dev_trial_count(conn) == n_before
    assert npolicy.effective_n(conn, "all-trials").n == policy_before
    assert conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0] == 54


def test_a_full_batch_does_not_move_the_trial_sharpe_variance(conn, monkeypatch):
    """var_trials cannot move: dev_daily_sharpes reads trials.sharpe, which this never writes."""
    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn))
    sharpes_before = store.dev_daily_sharpes(conn)
    var_before = statistics.variance(sharpes_before)

    remeasure.remeasure_seed(conn, _plan(conn), FakeData())

    assert store.dev_daily_sharpes(conn) == sharpes_before
    assert statistics.variance(store.dev_daily_sharpes(conn)) == var_before


def test_a_full_batch_writes_only_trial_moments(conn, monkeypatch):
    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn))
    trials_before = [tuple(r) for r in conn.execute("SELECT * FROM trials ORDER BY n")]
    methods_before = [tuple(r) for r in conn.execute("SELECT * FROM methods ORDER BY id")]

    remeasure.remeasure_seed(conn, _plan(conn), FakeData())

    assert [tuple(r) for r in conn.execute("SELECT * FROM trials ORDER BY n")] == trials_before
    assert [tuple(r) for r in conn.execute("SELECT * FROM methods ORDER BY id")] == methods_before
    assert store.test_looks(conn) == 0
    nulls = conn.execute("SELECT count(*) FROM trials WHERE window='dev' AND dsr IS NULL").fetchone()
    assert nulls[0] == 54  # trials.dsr is still NULL on every seed row, and stays that way


# ---- the var_trials written ------------------------------------------------------------------


def test_var_trials_is_the_seed_set_s_own_variance(conn, monkeypatch):
    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn))
    want = statistics.variance(
        [float(r[0]) / TD for r in conn.execute(
            "SELECT sharpe FROM trials WHERE window='dev' AND dsr IS NULL ORDER BY n")]
    )
    assert remeasure.seed_var_trials(conn) == want

    remeasure.remeasure_seed(conn, _plan(conn), FakeData())

    written = {r[0] for r in conn.execute("SELECT DISTINCT var_trials FROM trial_moments")}
    assert written == {want}
    # and n_at_run is the trial's recorded N, not today's count
    assert {r[0] for r in conn.execute("SELECT DISTINCT n_at_run FROM trial_moments")} == {54}


def test_var_trials_does_not_depend_on_the_chunk_size(conn, tmp_path, monkeypatch):
    """The whole point of reading it off the database: chunking cannot change what is written."""
    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn))
    one = remeasure.remeasure_seed(conn, _plan(conn), FakeData(), chunk=54)
    assert one.chunks == 1
    rows_one = {r["trial_n"]: tuple(r) for r in conn.execute("SELECT * FROM trial_moments")}

    other = store.connect(tmp_path / "other.sqlite")
    seed(other)
    monkeypatch.setattr(remeasure, "run_chunk", perfect(other))
    many = remeasure.remeasure_seed(other, _plan(other), FakeData(), chunk=7)
    assert many.chunks == 8
    rows_many = {r["trial_n"]: tuple(r) for r in other.execute("SELECT * FROM trial_moments")}
    other.close()

    assert set(rows_one) == set(rows_many)
    for n, row in rows_one.items():
        assert row[:-1] == rows_many[n][:-1]  # every column but the `measured` stamp


def test_the_report_names_both_variances(conn, monkeypatch):
    """**Decision D12, kept visible.** The report shows the gate's number and the contrast number.

    `store.dsr_at` deflates by `store.dev_sharpe_variance(conn)` -- today's, over all dev trials
    -- on both of its routes, so `SeedVerdict.dsr` is the number that decides. The recorded
    `var_trials` (the P7a search's own 54) is history and never a verdict; it is printed beside
    the gate's number only so a candidate sitting on the bar is *visibly* sitting on it. On the
    committed lab those two variances are 2.0067e-04 and 2.3950e-04, far enough apart to move
    `F9-SPY200M70-MOM30` from 0.8567 (fails) to 0.9031 (would pass). A report that printed one of
    them is how that choice gets made silently by a constant nobody looked at.
    """
    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn))
    report = remeasure.remeasure_seed(conn, _plan(conn), FakeData())
    verdicts = remeasure.seed_verdicts(conn, report)
    assert verdicts, "nothing was written, so there is nothing to report"

    today = store.dev_sharpe_variance(conn)
    assert today is not None
    assert report.var_trials is not None
    assert today != pytest.approx(report.var_trials), (
        "this fixture must keep the two variances apart, or the test proves nothing"
    )

    # The verdict's own DSR is the GATE's: today's variance, at the gate's N.
    g = store.gate(conn)
    for v in verdicts:
        m = store.moments_of(conn, v.trial_n)
        assert v.dsr == pytest.approx(
            dev.deflated_sharpe(float(m["sr_daily"]), g.n, today, int(m["t"]),
                                float(m["skew"]), float(m["kurt"]))
        ), v.candidate_id
        assert v.dsr_recorded_var == pytest.approx(
            dev.deflated_sharpe(float(m["sr_daily"]), g.n, float(m["var_trials"]), int(m["t"]),
                                float(m["skew"]), float(m["kurt"]))
        ), v.candidate_id
        assert v.dsr != pytest.approx(v.dsr_recorded_var), v.candidate_id

    text = remeasure.format_seed_report(conn, report, verdicts)
    assert "variance the GATE uses" in text and "var_trials WRITTEN" in text
    assert f"{today:.6g}"[:6] in text.replace(" ", "") or f"{today:e}"[:5] in text
    assert "recorded as-of-P7a variance" in text, "the contrast column must be labelled"
    for v in verdicts:
        assert f"{v.dsr:.6f}"[:6] in text, v.candidate_id


# ---- resumable and idempotent ----------------------------------------------------------------


def test_an_interrupted_batch_keeps_what_it_wrote_and_resumes(conn, monkeypatch):
    """Kill it mid-job: the committed chunks survive and the re-run picks up exactly the rest."""
    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn))

    class Stop(Exception):
        pass

    def die(index, total, written, blocked):
        if index == 3:
            raise Stop

    with pytest.raises(Stop):
        remeasure.remeasure_seed(conn, _plan(conn), FakeData(), chunk=10, on_chunk=die)
    assert conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0] == 30
    first = {r["trial_n"]: tuple(r) for r in conn.execute("SELECT * FROM trial_moments")}

    resumed = remeasure.remeasure_seed(conn, _plan(conn), FakeData(), chunk=10)

    assert sorted(resumed.skipped) == sorted(first)
    assert len(resumed.written) == 24 and len(resumed.measured) == 24
    assert conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0] == 54
    kept = {r["trial_n"]: tuple(r) for r in conn.execute("SELECT * FROM trial_moments")}
    for n, row in first.items():
        assert kept[n] == row  # nothing written before the interrupt was rewritten
    assert store.dev_trial_count(conn) == 54


def test_remeasure_seed_is_idempotent(conn, monkeypatch):
    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn))
    remeasure.remeasure_seed(conn, _plan(conn), FakeData())
    before = {r["trial_n"]: tuple(r) for r in conn.execute("SELECT * FROM trial_moments")}

    plan = _plan(conn)
    assert plan.nothing_to_do and len(plan.present) == 54

    second = remeasure.remeasure_seed(conn, plan, FakeData())
    assert second.written == () and second.measured == () and second.chunks == 0
    assert {r["trial_n"]: tuple(r) for r in conn.execute("SELECT * FROM trial_moments")} == before


# ---- the tolerance ---------------------------------------------------------------------------


def test_the_real_rounding_error_reproduces(conn, monkeypatch):
    """4.9e-07 on every metric is what the real re-run shows; it must not read as divergence."""
    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn, error=4.9e-07))
    report = remeasure.remeasure_seed(conn, _plan(conn), FakeData())
    assert len(report.written) == 54 and report.blocked == ()


def test_a_divergent_trial_is_reported_and_not_written_and_the_rest_are(conn, monkeypatch):
    """The brief's rule: a finding per trial, not a crash -- and it blocks that trial's write."""
    monkeypatch.setattr(
        remeasure, "run_chunk",
        perfect(conn, drift={"F9-SPY200M70-MOM30": ("max_drawdown", 2e-05)}),
    )
    report = remeasure.remeasure_seed(conn, _plan(conn), FakeData())

    bad = next(r for r in report.measured if r.candidate_id == "F9-SPY200M70-MOM30")
    assert not bad.ok
    assert [c.name for c in bad.misses] == ["max_drawdown"]
    assert bad.trial_n in report.blocked and bad.trial_n not in report.written
    assert store.moments_of(conn, bad.trial_n) is None
    assert len(report.written) == 53  # every other trial was written
    assert conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0] == 53


def test_a_trade_count_must_match_exactly(conn, monkeypatch):
    """The sharpest of the six: one extra closed trade is a different trade sequence."""
    monkeypatch.setattr(
        remeasure, "run_chunk", perfect(conn, drift={"F9-SPY200M70-MOM30": ("trades", 1)})
    )
    report = remeasure.remeasure_seed(conn, _plan(conn), FakeData())
    bad = next(r for r in report.measured if r.candidate_id == "F9-SPY200M70-MOM30")
    assert [c.name for c in bad.misses] == ["trades"]
    assert report.blocked == (bad.trial_n,)


def test_a_null_metric_reproduces_only_as_none(conn):
    """REF-SPY-HOLD's profit_factor is NULL in the P7a file; None is a match, a number is not."""
    both_null = remeasure.MetricCheck(name="profit_factor", recorded=None, measured=None)
    assert both_null.ok and both_null.delta is None
    assert not remeasure.MetricCheck(name="profit_factor", recorded=None, measured=1.0).ok
    assert not remeasure.MetricCheck(name="profit_factor", recorded=1.0, measured=None).ok
    assert remeasure.MetricCheck(name="cagr", recorded=1.0, measured=1.0 + 9e-07).ok
    assert not remeasure.MetricCheck(name="cagr", recorded=1.0, measured=1.0 + 2e-06).ok


# ---- the refusals ----------------------------------------------------------------------------


def test_the_seed_path_is_refused_once_any_seed_family_has_had_its_look(conn, monkeypatch):
    import dataclasses

    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn))
    row = conn.execute("SELECT * FROM trials WHERE n = 53").fetchone()
    with conn:
        conn.execute(
            "INSERT INTO trials (method_id, candidate_id, config_digest, config_text, rules_id, "
            "allocator_id, window, start, end, store_fingerprint, git_sha, run_at, trades, "
            "failed, eligible, n_trials_at_run) "
            "VALUES (?, ?, ?, '', '', '', 'test', ?, ?, '', '', '', 0, '', 0, 54)",
            (row["method_id"], row["candidate_id"] + "-T", "0" * 64, row["start"], row["end"]),
        )
    assert store.test_looks(conn) == 1
    with pytest.raises(store.LabError, match="look at the test window"):
        _plan(conn)
    assert conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0] == 0


def test_a_lab_method_id_and_an_unknown_family_are_refused(conn):
    assert remeasure.is_seed_id("H-P7A") and remeasure.is_seed_id("H-P7A-F9")
    assert not remeasure.is_seed_id("M0022") and not remeasure.is_seed_id("H-A")
    with pytest.raises(store.LabError, match="not a P7a seed id"):
        _plan(conn, "M0022")
    with pytest.raises(store.LabError, match="no dev trial"):
        _plan(conn, "H-P7A-F99")
    with pytest.raises(store.LabError, match="has no trial for"):
        _plan(conn, only=("NOT-A-CANDIDATE",))


def test_a_changed_registry_entry_is_refused(conn, monkeypatch):
    with conn:
        conn.execute(  # the shape of "the registry entry changed after it ran"
            "UPDATE trials SET config_digest = ? WHERE n = 53", ("f" * 64,)
        )
    with pytest.raises(store.LabError, match="ran under ffffffffffff"):
        _plan(conn)


# ---- the test window is unreachable, structurally ---------------------------------------------


def test_no_window_can_be_selected_anywhere_in_the_seed_path(conn, monkeypatch):
    for fn in (remeasure.run_chunk, remeasure.remeasure_seed, remeasure.seed_preflight):
        assert "window" not in inspect.signature(fn).parameters
    monkeypatch.setattr(remeasure, "run_chunk", perfect(conn))
    with pytest.raises(store.LabError, match="re-runs the dev window"):
        remeasure.remeasure_seed(conn, _plan(conn), FakeTestData())
    assert conn.execute("SELECT count(*) FROM trial_moments").fetchone()[0] == 0
    assert store.test_looks(conn) == 0
    calls: list[dict] = []
    monkeypatch.setattr(
        remeasure.dev, "run_registry",
        lambda *a, **k: (calls.append(dict(k)), [])[1],
    )
    remeasure.run_chunk(FakeData(), [])
    assert calls and all("window" not in k for k in calls)
```

**Note for the test author.** `test_the_seed_path_is_refused_once_any_seed_family_has_had_its_look`
writes a raw `INSERT` into `trials` to build the "a look was spent" shape; use
`store.insert_trials` with a `dataclasses.replace(..., window="test")` `TrialRow` instead if
phase 2's `TrialRow` makes that cleaner. Either way the row's purpose is to make `test_looks`
read 1, and the test asserts the refusal happens before anything is written.

**Impact:** `pytest engine/tests/test_lab_remeasure_seed.py` is green and no other test changes.
Phase 3's `test_lab_remeasure.py` is untouched except for
`test_a_seed_family_is_refused_by_name`, whose `match="not a lab method id"` still matches the
corrected message in Step 2 (the phrase is preserved verbatim at the front of it).

---

## Verification

**Build:**

```
cd /home/miftah/.worktrees/seer/lab-luck-gate/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/lab-luck-gate/engine/src \
/home/miftah/seer/engine/.venv/bin/python -c \
"from seer_engine.lab import remeasure as r; print(r.METRIC_TOL, r.SEED_METRICS, r.is_seed_id('H-P7A'), len(r.REGISTRY))"
```

**Tests:**

```
cd /home/miftah/.worktrees/seer/lab-luck-gate/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/lab-luck-gate/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m pytest \
  tests/test_lab_remeasure_seed.py tests/test_lab_remeasure.py tests/test_lab_store.py \
  tests/test_lab_runner.py tests/test_lab_test_window.py tests/test_registry.py -q
```

then the whole suite:

```
cd /home/miftah/.worktrees/seer/lab-luck-gate/engine && \
PYTHONPATH=/home/miftah/.worktrees/seer/lab-luck-gate/engine/src \
/home/miftah/seer/engine/.venv/bin/python -m pytest -q
```

(The worktree has no `engine/.venv`; the main checkout's venv plus `PYTHONPATH` shadowing the
editable install is this repo's established way to run the suite from a swarm worktree.)

**Manual check — against a COPY of the committed database, never the committed file.** Invariant 6
and decision D5 give `lab/lab.sqlite` to phase 4 alone; this phase commits source and tests only.

```
cd /home/miftah/.worktrees/seer/lab-luck-gate && cp lab/lab.sqlite /tmp/lab-seed-check.sqlite && \
SEER_LAB_DB=/tmp/lab-seed-check.sqlite PYTHONPATH=engine/src \
/home/miftah/seer/engine/.venv/bin/python -m seer_engine lab remeasure H-P7A \
  --store /home/miftah/seer/engine/.research
```

Expect, from the measurements above: ~11s to load the store, ~52s of backtests, 54
`trial_moments` rows written, **zero blocked**, exit 0, and in the report

```
  variance the GATE uses: 2.395e-04 ... var_trials WRITTEN: 2.007e-04
  gate: N = 110 under policy 'all-trials', luck bar DSR >= 0.9

    #53 F9-SPY200M70-MOM30  t=4983  sr_daily=0.0549902...  skew=-0.398685...  kurt=10.20991...
          DSR @ N=110 = 0.856651  luck: fail (bar 0.9)   [with the recorded as-of-P7a variance: 0.903053]
          owner conditions: all pass   MAR 0.635164   -> not eligible
```

**That is the expected line under Decision D12**, and `-> not eligible` is the correct outcome,
not a failure of this phase: F9 is now held out by a luck test it *received*, which is R6. The
final eligible set stays **three** (`M0022-W-TV14`, `M0022-W-TV16`, `M0020-W-NOSTOP`) and this
phase adds none. What must be true is that the number is *there*, computed from measured moments,
that it is the today's-variance one, and that the as-of-P7a figure is printed beside it so the
closeness of the call is visible.

Then run it again — it prints "every seed trial already has its moments; nothing to do", loads no
research store, and writes nothing. Then:

```
PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python - <<'PY'
import sqlite3
c = sqlite3.connect("/tmp/lab-seed-check.sqlite")
print("dev trials  ", c.execute("select count(*) from trials where window='dev'").fetchone()[0])
print("test looks  ", c.execute("select count(*) from trials where window='test'").fetchone()[0])
print("moments     ", c.execute("select count(*) from trial_moments").fetchone()[0])
print("seed dsr null", c.execute("select count(*) from trials where window='dev' and dsr is null").fetchone()[0])
print("statuses    ", sorted(c.execute("select distinct status from methods where id like 'H-P7A%'")))
PY
```

Expect `dev trials 110`, `test looks 0`, `moments 54`, `seed dsr null 54`,
`statuses [('rejected',)]`.

Finally, prove N did not move, against the untouched committed file and the copy:

```
PYTHONPATH=engine/src /home/miftah/seer/engine/.venv/bin/python - <<'PY'
from seer_engine.lab import npolicy, store
for path in ("lab/lab.sqlite", "/tmp/lab-seed-check.sqlite"):
    c = store.connect(__import__("pathlib").Path(path))
    print(path, store.dev_trial_count(c), npolicy.effective_n(c, "all-trials").n,
          store.dev_sharpe_variance(c))
    c.close()
PY
```

Both lines must read `110 110 0.00023950479947117267`.

**Exit criteria:**

1. `lab remeasure H-P7A` against a copy of the committed database populates **54**
   `trial_moments` rows, zero blocked, exit 0.
2. `store.dev_trial_count` and `npolicy.effective_n(conn, "all-trials").n` read **110** before and
   after, identically; `store.dev_sharpe_variance` and `store.dev_daily_sharpes` are unchanged.
3. `trials` and `methods` are byte-identical before and after — every column of every row.
   `trials.dsr` is still NULL on all 54 seed rows. No `methods.status` moved.
4. The report names `F9-SPY200M70-MOM30`'s resolved DSR at the current gate N — **0.856651**,
   deflated by today's lab-wide variance per Decision D12 — prints the as-of-P7a figure
   (**0.903053**) beside it in brackets, and says whether it passes the luck bar and every owner
   condition. It reads `luck: fail` / `-> not eligible`, and that is the pass condition.
8. **This phase makes nothing eligible.** The eligible set is still exactly
   `M0022-W-TV14`, `M0022-W-TV16`, `M0020-W-NOSTOP` — three — before and after the batch. What
   changes is that 54 trials now fail the luck test on a measured number instead of on a NULL.
5. Interrupting a chunked run and re-running it writes exactly the remaining rows and rewrites
   none of the earlier ones; running the complete command twice writes nothing the second time and
   loads no research store.
6. `store.test_looks(conn)` reads `0`.
7. `pytest` green in `engine/`.

---

## Handoffs

- **Phase 4 — the `dsr_at` route-1 variance. CLOSED, Decision D12.** The reconciler applied this
  phase's recommendation: phase 4's route 1 now reads `dev_sharpe_variance(conn)`, the same
  variance as route 2, hoisted above the branch so the two cannot drift apart again, and
  `moments["var_trials"]` is no longer referenced in `dsr_at` at all. Rung 4, the index's R2.
  **This phase still does not change `dsr_at`** — it is phase 4's symbol — and needs no further
  action; `seed_verdicts` and `format_seed_report` above are already written against the settled
  rule, with the as-of-P7a figure kept as the contrast column.
- **Phase 4 — its state-dependent tests.** Enumerated in full under *Phase 4's state-dependent
  tests* above. Nothing breaks when this phase lands, because this phase does not touch the
  committed database; what breaks is any phase-4 test reading `lab/lab.sqlite` directly for
  "F9-SPY200M70-MOM30 has no DSR" **on the day someone runs the batch for real**. Those tests
  should assert against a fixture database, or assert the pre-remeasure property as "no
  `trial_moments` row" rather than as "no DSR".
- **Running the batch against the committed `lab/lab.sqlite`.** Deliberately **not** done here:
  invariant 6 and decision D5 give that binary to phase 4's migration commit alone, and two
  concurrent swarm phases cannot both write a file git cannot merge. Whoever owns the committed
  database afterwards runs `lab remeasure H-P7A` once, commits the binary, and re-runs `lab stage`
  so `web/data/lab.json` reflects it.
- **Phase 5 — surfacing it in `lab status`.** `lab status` could say "54 dev trials are P7a seed
  rows; k of them now have moments; `lab remeasure H-P7A` recovers the rest". Phase 5 owns
  `_status`; this phase adds nothing to it.
- **Phase 7 — documentation.** The design doc's §1 "DSR is NULL for the seed" and `SKILL.md`'s
  promotion step both predate this command. Phase 7 owns every doc in the set; this phase edits
  only `commands/lab.py`'s own usage docstring.
- **Phase 8 — the eligibility column's value.** Without the 15% -> 20% drawdown move,
  `F9-SPY200M70-MOM30` (19.24%) fails `max DD` and the report's eligible set is empty. No code
  dependency; `verdict`'s `owner_failures` reads `tuning.MAX_DRAWDOWN` at call time.
- **The brief's claim about `F3-SEC-TOP3-6M-TREND` was wrong. CLOSED.** It fails `owner inputs`
  (the nine sector ETFs), which is not a threshold and which no constant re-decides. It cannot
  become eligible at any drawdown bar until the owner verifies those ETFs. Its DSR is
  0.6777 (as-of-P7a variance) / 0.5989 (today's) regardless. Applied: phase 4 now pins F9 and F3
  as **two separate tests with two different reasons** —
  `test_f9_the_one_seed_row_held_out_by_the_luck_test_alone` (the NULL-DSR rule, state-dependent
  and self-skipping once this phase has run) and
  `test_f3_stays_ineligible_on_owner_inputs_whatever_its_luck_test_says` (unconditional, and
  takes no view on F3's DSR). Phase 7's design §7.5 wording was corrected the same way.
- **The index's Scope line and phase table. CLOSED.** The "they keep their recorded verdicts
  forever" line was moved from Out-of-scope to In-scope; the index now carries nine phases, R5 and
  R6, invariant 7, and recomputed waves.
- **Not done, deliberately:** no `--dry-run` (nothing is spent, and `nothing_to_do` already prints
  without loading a store); no gating on `exposure`, `turnover` or `worst_year` (available, but
  they add arithmetic rather than independent evidence — see the tolerance decision); no
  `trials.dsr` backfill in any form, per the brief and per invariant 3; no touch to
  `backtest/registry.py`, `lab/seed.py` or any P7a report file.

---

## Rollback

One commit over three paths, purely additive, reverts cleanly on its own:

```
git revert <phase-9 commit>
```

`test_lab_remeasure_seed.py` is a new file nothing imports. The `remeasure.py` addition is one
appended section plus three import lines, one annotation and two message strings — removing it
leaves phase 3's module exactly as phase 3 wrote it, with the single caveat that
`resolve_method`'s restored message again claims the seed families can never be re-run, which is
true again once this code is gone. The `commands/lab.py` edits are confined to the `remeasure`
subparser, `_remeasure`'s first two lines and the new `_remeasure_seed`; they remove without
touching a line phase 4 or phase 5 wrote.

**If the command has already been run against a database**, the `trial_moments` rows it wrote
stay, and that is correct: they are a true record of a verified re-measurement, `trial_moments` is
append-only by phase 2's triggers, and reverting this phase's *code* does not invalidate the
*data*. The visible consequence is that phase 4's `verdict` keeps computing a real DSR for those
54 rows — which is the thing the owner asked for, and which no longer depends on this command
existing. If a backfilled database must be restored anyway,
`git checkout origin/main -- lab/lab.sqlite` replaces the binary wholesale, as the plan index's
rollback section already prescribes. Nothing in `trials`, `methods`, the REGISTRY or any P7a
report file was ever written, so there is nothing else to undo.
