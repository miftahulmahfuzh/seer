# Plan: the delisting stress test, the roster replacement rule, and two asymmetries put on the record

**Slug:** delisting-stress-roster-rules
**Date:** 2026-10-07 17:05:15
**Analysis:** `20261007-170515-0CU0_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/delisting-stress-roster-rules`
**Branch:** `feature/delisting-stress-roster-rules` (base: `origin/main` @ `3683d7b`; **merged up
to `origin/main` @ `ba8a05b`** on 2026-10-07, which brought in `seer-fc`'s go-live change — design
§13, `metrics.MIN_PAPER_MONTHS = 18` and the `dev.py` comment. Every plan in the set has been
re-checked against that tree.)
**Phases:** 5
**Status:** reconciled
**Coordinator:** —

---

## Why

The specification is §5 of `docs/handover/2026-10-07-roster-first-night-and-survivorship.md`,
whose preamble says to pass the file to `/analyze` and settle the four questions in it. Verbatim:

> **Q1 — the delisting stress test (the main open item).** §3 is an absence of evidence from an
> era contrast that is confounded with regime. The test that isolates the mechanism has not been
> run: inject synthetic delistings into the ranking universe at the historical rate and solve for
> the **break-even delisting return** — how bad the assumed loss must be before the edge vanishes
> — then judge whether that number is plausible. Framing it as break-even avoids having to guess a
> delisting return, which is the part no free source can give us. Open: where it lives (a lab
> method would spend a trial and move N, which is probably wrong for a diagnostic), and whether it
> needs the position level or can be approximated from the recorded curves.
>
> **Q2 — is go-live item 1 calibrated?** Item 1 asks for ≥ 3 months **and** ≥ 100 closed trades.
> Trades bind, not months, and by a wide margin… So "3 months of paper" is really 15–21 months,
> and every future roster swap resets that clock for the entry it replaces. This is the owner's
> dial (`backtest/dev.py:86`, `_MIN_TRADES = 100`), not the analysis's — but the owner may not
> realise the 3 months is decorative, and should be told before the clock has been running a year.
>
> **Q3 — is `MOM-FR` the weakest of the five?** Its era edge is +6.2 / +8.2 / **−2.3**, the least
> stable of the four quant entries, and it has the slowest path to a verdict (20.7 months). It was
> admitted as F4's bet inside the drawdown bar. Worth asking whether a better occupant of that
> slot exists in the lab, **but not before** reading the warning in Q4.
>
> **Q4 — do not churn the roster on lab results.** Every swap restarts a ~15-month clock (Q2), and
> DSR falls monotonically as Sera explores (§2), so "it no longer passes the luck test" will become
> true of *everything* on the board without any book changing. A rule for when a roster entry may
> be replaced — before the first one looks bad — would be worth more than any individual swap.

Two standing owner preferences from §6 bind every phase: the owner **is not a quant**, so prose
must stay plain — numbers only with their meaning, no jargon without a gloss; and the owner
**prefers measuring to estimating**, which is why this plan carries measured numbers rather than
estimated ones and why phase 2 runs a Monte Carlo instead of arguing about one.

## What changed under this plan while it was being written

Two messages from session `seer-fc` — the author of the handover — arrived mid-analysis. Both are
recorded because they move requirements, and both were verified rather than taken on trust.

1. **The owner decided Q2.** Design §1 item 1 becomes **"≥ 18 months of forward paper trading"**
   and the `≥ 100 closed trades` clause is **deleted**, not re-levelled. `seer-fc` is implementing
   it in the shared checkout and has claimed those files (listed under *Out of scope*). **R2 is
   therefore satisfied externally**, and what remains of it is the residue nobody owns — see
   phase 4.
2. **The dev-window gate keeps its trades bar.** `backtest/dev.py:86` `_MIN_TRADES = 100` is
   deliberately *not* changed, so from today design §1 item 1 has no trades clause while the dev
   gate still does. `seer-fc` asked for that asymmetry to be folded in as its own item.

**Verified here, independently, against `lab/lab.sqlite` (read-only, no trial, N unmoved at 110):**
dropping the dev trades bar would newly pass **exactly 2 of 110** trials — `F1-SPY-SMA200-M`
(11 trades, PF 75.45) and `F1-SPY-10MSMA-M` (13 trades, PF 14.48) — reproducing `seer-fc`'s
numbers exactly. **One fact it did not report:** both carry `dsr IS NULL` (they are P7a seed
trials), and under lab design §7.1 a luck test that cannot be evaluated is one that was not
passed. So dropping the dev trades bar changes **zero** eligibility verdicts today; the
sample-size argument binds future trials, not these two.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | **Q1** — settle where the delisting stress test lives and what it needs, build it, run it, and report the break-even delisting return with a judgement on whether that number is plausible | 1, 2 |
| R2 | **Q2** — settle whether go-live item 1 is calibrated and tell the owner. *Decided by the owner mid-analysis and implemented by `seer-fc` (design §13, landed at `ba8a05b`); the residue owned here is the **executable** guard on the dev-gate asymmetry that decision leaves behind — the prose half is §13's and is cancelled* | 4 |
| R3 | **Q3** — settle whether `MOM-FR` is the weakest of the five, and whether a better occupant of that slot exists in the lab | 5 |
| R4 | **Q4** — write the rule for when a roster entry may be replaced, before the first one looks bad | 3 |

Every `R` is owned, and no phase's steps serve an `R` outside its own **Satisfies** line — checked
both ways after reconciliation. Phase 3 explicitly refuses R3 (it may name no entry as replaceable);
phase 5 explicitly refuses R2 and R4 (it applies the rule, it does not amend it); phase 2 explicitly
refuses to reach for the roster with R1's finding.

## Scope

**In scope**

- A new, read-only delisting stress harness: a tested module plus a script, in the shape of
  `engine/scripts/survivorship_coverage.py` and under the same contract (records no trial, moves
  no N, spends no test-window look, writes nothing to `engine/.research`).
- The break-even delisting return per quant roster entry, and a plain-language judgement on
  whether that number is plausible, recorded in the design doc and as one lab `insights` row.
- The roster replacement rule, as a new section of the method-lab design doc.
- One executable guard and one dated note recording asymmetries a later session would otherwise
  "tidy" away: a test pinning the dev-gate trades bar (phase 4 — the prose half is already covered
  by the peer's design §13 and is **cancelled**, see the Reconciliation Log), and phase 5's
  document on MOM-FR.

**Out of scope, and why**

- **Design §1 and §5 — never edited here.** The lab skill's standing guardrails
  (`docs/plans/2026-10-04-method-lab-design.md` §4) forbid it, and item 1 is the owner's dial,
  now being moved by `seer-fc`.
- **Every file `seer-fc` claimed.** `docs/plans/2026-10-03-seer-design.md` §1 and its new §13;
  `backtest/metrics.py`, `tuning.py`, `report.py`, `b_report.py`, `wf_report.py`;
  `web/lib/golive.ts`, `web/lib/metrics.ts`, `web/lib/golive.test.ts`; and
  `engine/tests/test_backtest_{tuning,metrics,b_walkforward,report,b_report}.py`. Phase 2 appends
  a *new* section to the design doc at the file's tail and renumbers at write time; no phase
  edits §1.
- **`backtest/dev.py` `_MIN_TRADES` itself.** Changing it re-judges 110 recorded trials. Phase 4
  documents and guards the constant; it does not move it.
- **Rebuilding `engine/.research`.** It changes every `config_digest` and resets all 110 trials
  and their DSRs (handover §3). The stress test perturbs an in-memory `Market` only.
- **The leaderboard hero figure.** Handover §4: *"no work should be opened on it without
  re-checking the page first."* No phase opens any.
- **Buying survivorship-free data.** Decided against by the owner on 2026-10-07 (handover §3).
  Phase 2 may *inform* a revisit; it does not make one.

## Invariants

Every phase must hold all of these, and each phase's exit criteria restate the ones it can break:

1. **The tree builds and the full suite passes at the end of each phase**, with **both**
   `PG_TEST_URL` **and** `PYTHONPATH` in the command, every time. Without `PG_TEST_URL` pytest
   reports a confident green missing a third of the suite (2812 passed / 385 skipped instead of
   3197 / 0) — handover §7. Without `PYTHONPATH` pointing at **this worktree's** `engine/src`,
   pytest silently tests the main checkout rather than the branch, because the venv has
   `seer_engine` installed editable against `/home/miftah/seer`. The assertion is **`0 failed,
   0 skipped` at a count no lower than 3197** — never a specific total, because sibling phases add
   tests to the same shared worktree. Do not pass `-o addopts=…`: it drops `-n auto` and the suite
   goes from ~62 s to ~342 s.
2. **No phase records a lab trial and no phase moves the lab's N.** N is 110 and stays 110.
   Nothing may call `lab.store.insert_trials` or `lab.runner.run_method`.
   **The whole lab counter reads `110 / 0 / 37 / 32` before the set and `110 / 0 / 37 / 33` after**
   (dev trials / test-window looks / methods / insights) — re-measured on this branch at `ba8a05b`.
   The single `insights` row phase 2 appends is the **only** legal change to any of the four.
3. **No phase spends a test-window look.** 0 are used and 0 stay used.
4. **No phase writes to `engine/.research`**, and no phase changes any `config_digest` or any
   recorded trial. `trials` is append-only and stays untouched.
5. **No phase edits design §1, §5, §11, §12 or the peer's §13, the paper roster's `SEED_ROWS` for a
   started id, or the P7a registry.** Phase 2 **appends** a new §14 at the tail of
   `2026-10-03-seer-design.md` and phase 3 a new §8 at the tail of `2026-10-04-method-lab-design.md`
   — two different files, each resolving its own number at write time, neither inserting and
   neither renumbering an existing heading. **No phase edits `backtest/dev.py`.** A changed strategy needs a new id with its own paper clock, never an edited entry.
6. **No phase edits a file `seer-fc` claimed** (listed above).
7. **Prose the owner will read stays plain** — numbers with their meaning, no jargon without a
   gloss, no ids or digests in insight bodies (handover §6).
8. **Every commit uses an explicit path allowlist, never `git add -A`, and every branch update is
   `git merge`, never `git rebase`.** This worktree is shared with the other phases of this set and
   with peer sessions, so their edits appear in `git status` and their commits are live in this
   history. The check that a phase stayed in its lane is `git show --stat --name-only HEAD`
   *equalling* the allowlist, not `git status` being clean.
9. **Purity holds.** `tests/test_strategy_purity.py` globs `backtest/` and `sim/`; anything new
   under those paths must take no clock, no I/O and no randomness. The stress harness's randomness
   lives in the new module's own seeded generator, outside the globbed paths, and is passed in.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | The delisting stress harness | R1 | `engine/src/seer_engine`, `engine/scripts`, `engine/tests` | 3 | — | HARD | `.workflows/plan/delisting-stress-roster-rules/phase-1.md` | — | — |
| 2 | Run it, and record what it found | R1 | `docs/plans`, `lab`, `web/data` | **3** | 1 | NORMAL | `.workflows/plan/delisting-stress-roster-rules/phase-2.md` | — | — |
| 3 | The roster replacement rule | R4 | `docs/plans` | 1 | — | NORMAL | `.workflows/plan/delisting-stress-roster-rules/phase-3.md` | — | — |
| 4 | **A test that pins the dev gate's trades bar** | R2 | `engine/tests` | **1** | — | EASY | `.workflows/plan/delisting-stress-roster-rules/phase-4.md` | — | — |
| 5 | MOM-FR, judged under the rule | R3 | `docs/handover` | 1 | 3 | NORMAL | `.workflows/plan/delisting-stress-roster-rules/phase-5.md` | — | — |

Waves the `Depends on` column implies: **{1, 3, 4}** concurrently, then **{2, 5}** concurrently.

**Two file-count corrections the draft had wrong**, both verified rather than assumed:

- **Phase 2 is 3 files, not 2.** It must also regenerate `web/data/lab.json`, because
  `engine/tests/test_lab_snapshot.py:449` pins that file byte-for-byte to the export of
  `lab/lab.sqlite`, and the phase appends an `insights` row. Without the regeneration the suite is
  red for every session in the shared worktree.
- **Phase 4 is 1 file, not 2, and is test-only.** Its handover note
  (`docs/handover/2026-10-07-dev-gate-trades-bar.md`) is **cancelled, not deferred**: the peer's
  design §13 plus the comments at `backtest/dev.py:85-89` now say everything it was going to say,
  and a second record of the same decision is the kind that goes stale first and then misleads.
  **Nobody should write it.** The title changed to match.

**The whole set runs in one shared worktree**, concurrently with peer sessions. Two consequences
are now written into every phase: **every commit uses an explicit path allowlist** (never
`git add -A`), and **every branch update is `git merge`, never `git rebase`** — a rebase would
rewrite a sibling phase's commits out from under it. For the same reason **no phase asserts a
specific full-suite pass count**; each asserts `0 failed, 0 skipped` at a count no lower than the
branch baseline of **3197**, which the reconciler re-counted at `ba8a05b`.

### Phase 1 — The delisting stress harness
**Satisfies:** R1
**Owns:** a new tested module `engine/src/seer_engine/delisting.py` (the hazard estimator and the
`Market` perturbation), a new driver `engine/scripts/delisting_stress.py` (the Monte Carlo and the
break-even solver), and a new `engine/tests/test_delisting.py`.
**Does not touch:** `backtest/`, `sim/`, `lab/`, `paper/`, `web/`, any document, or
`engine/.research`. It adds files; it changes none.
**Exit criteria:** `delisting_stress.py --help` runs; a smoke run over one candidate, two assumed
delisting returns and 2 seeds completes and prints a table whose hazard block reproduces M2
(5.091%, 4.002%, 10,096 member-years); the new tests pass; the full suite passes with `PG_TEST_URL`
and `PYTHONPATH`, 0 failed and 0 skipped; `ruff check --no-cache src tests scripts` passes; a test
asserts the module imports neither `lab.store` nor `lab.runner`, so it can never record a trial;
and the commit lists exactly the three new paths. **Phase 1 owns the CLI spellings phase 2
consumes** — `--entry` (repeatable), `--hazard unserved|all|NUMBER`, `--returns`, `--seeds`,
`--seed0`, `--jobs` (default **1**), `--store`, `--csv`, `--decline-sessions`, `--smoke`. If an
implementer changes one, phase 2's Steps 1, 3 and 3b change with it. **It also owns the `--csv`
column names, their order and their units** (fractions for `cagr`/`max_drawdown`/`total_return`/
`spy_cagr`, percentage points for `edge_points_per_year`, an empty `delisting_return` and `seed`
on the unstressed row) — phase 2's Step 4 extraction script is written against them, and the
schema is now stated in phase 1's own Interface Contract rather than only in phase 2's.

### Phase 2 — Run it, and record what it found
**Satisfies:** R1
**Owns:** the actual Monte Carlo run and its results; a new section appended to
`docs/plans/2026-10-03-seer-design.md` in §12's voice, **numbered at write time** (§14 — `seer-fc`'s
§13 has landed and the file now ends at line 284); one `insights` row in `lab/lab.sqlite`
(`kind='risk'`, via `python -m seer_engine lab insight`); and **`web/data/lab.json`**, regenerated
with `lab export-json` because `engine/tests/test_lab_snapshot.py:449` pins it byte-for-byte to the
database.
**Does not touch:** design §1, §5, §11, §12 or `seer-fc`'s §13 — it **appends** a new section at
the file's tail rather than inserting, and renumbers nothing. No code. `trials` is not read-write.
**Exit criteria:** an answer to the break-even question is reported for each of RMW-FR, RAW-FR,
MOM-FR and MVW-FR — **either a break-even delisting return, or an explicit "not reached on this
grid", which is phase 1's `break_even(...) -> None` case and an expected, legitimate result, not a
failure to stop on** — with the assumed hazard stated and the Monte Carlo's seed count and spread
shown; **the
true unstressed run and the `r = 0` run are reported as separate rows, with the gap named as the
cost of a thinner ranking pool — `r = 0` is never presented as "no stress"**; the section says the
harness injects the historical *rate* into the ~409 priced survivors rather than restoring the
historical *count* of 404 unpriced exits; the new design section states plainly whether the
break-even is plausible and what the test cannot answer (the 118 names that never died in-window);
the lab insight is appended and `web/data/lab.json` regenerated **in the same breath**, since the
suite is red for the whole shared worktree in between; `lab status` reads 110 / 0 / 37 / **33**;
the full suite passes with 0 failed and 0 skipped.

### Phase 3 — The roster replacement rule
**Satisfies:** R4
**Owns:** a new section of `docs/plans/2026-10-04-method-lab-design.md` (expected §8) stating when
a paper roster entry may be replaced, extending §7.4's recorded paper-vs-lab divergence.
**Does not touch:** `paper/roster.py`, `lab/lab.sqlite`, design §1, or any code. The rule is
written before any swap and must not be written to justify one.
**Exit criteria:** the rule names its own trigger conditions and its own refusals; it is built on
**18 months flat** (the owner's new item 1), not on the superseded 14.9/19.4/20.7-month table; it
states explicitly that a falling DSR alone is never a reason to replace an entry, with lab design
§7.3's measured ratchet as the evidence; it says what happens to the replaced entry's record; and
it is dated and attributed. It names **no** roster entry as a thing to be replaced — judging MOM-FR
is phase 5's work under R3, and a rule that prejudged it is the failure Q4 warns about. The full
suite passes with 0 failed and 0 skipped.

### Phase 4 — A test that pins the dev gate's trades bar
**Satisfies:** R2
**Owns:** exactly one new file, `engine/tests/test_dev_trades_bar.py` — three tests pinning
`dev._MIN_TRADES == 100` with a failure message that explains why it differs from design §1 item 1,
and re-deriving §13's measurement from the committed lab database on every CI run instead of
restating it. **Test-only: this phase writes no documentation at all.**
**Does not touch:** `backtest/dev.py`, design §1 and §13, and every file `seer-fc` claimed — in
particular **not** `engine/tests/test_backtest_tuning.py`, which is why the guard gets its own new
file. It opens `lab/lab.sqlite` read-only (`mode=ro`) and writes nothing.
**Cancelled, not deferred:** the first draft also owned
`docs/handover/2026-10-07-dev-gate-trades-bar.md`. `seer-fc`'s design §13 and the comment at
`backtest/dev.py:85-89` now carry the asymmetry, the measurement and the `dsr IS NULL` finding in
full. **Nobody should write that note** — a duplicate record of one decision is the one that goes
stale first and then misleads.
**Exit criteria:** the three tests pass with **0 skipped** (CI fails on any skip); moving
`_MIN_TRADES` in memory produces prose a surprised engineer can act on, naming design §13 and the
comment above the constant and saying what the change costs; the third test re-derives exactly
`F1-SPY-SMA200-M` (11 trades) and `F1-SPY-10MSMA-M` (13 trades) held out by the bar alone, **both
with `dsr IS NULL` so zero eligibility verdicts change today**, from the database rather than from
a hardcoded claim; `backtest/dev.py` and every `seer-fc`-claimed file show no diff; the commit lists
exactly one path; the full suite passes with 0 failed and 0 skipped.

### Phase 5 — MOM-FR, judged under the rule
**Satisfies:** R3
**Owns:** a new `docs/handover/2026-10-07-mom-fr-under-the-replacement-rule.md` carrying the
verdict and the evidence. **Conditional:** it edits `paper/roster.py` only if the verdict is
"swap", and then only under a new id with its own paper clock.
**Does not touch:** phase 3's rule (it applies it, it does not amend it), `lab/lab.sqlite`, or any
started entry's `spec_digest`.
**Exit criteria:** the verdict is stated plainly with the lab evidence behind it (26 candidates
clear all five owner conditions today; MOM-FR is 12th by DSR and 8th by MAR); it records that one
of Q3's three indictments — "the slowest path to a verdict (20.7 months)" — **is now void**, since
under the owner's new item 1 every entry reaches a verdict at 18 months flat; it weighs the family
diversity MOM-FR is the only holder of against the higher lab scores of the weekly-brake
alternatives; and it applies phase 3's rule by name rather than re-deriving one, citing it by the
**real** section number read from the file (expected §8) with every `§<RULE>` / `<RULE-TITLE>`
placeholder resolved — `grep -n 'RULE'` on the committed document must return nothing. The full
suite passes with 0 failed and 0 skipped.

## Reconciliation Log

Round 1. Every row was verified against the tree merged to `origin/main` @ `ba8a05b` before being
resolved, and every resolution is an **edit to the plan files**, not a note.

| # | Conflict | Kind | Phases | Resolution |
|---|---|---|---|---|
| 1 | Phase 2's run commands used `--candidates id1,id2,id3`. Phase 1 defines **`--entry`**, `action="append"` — no `--candidates` flag exists, and a comma-joined value would be parsed as a single unknown candidate id and die at `_candidates()` | Contract drift | 1, 2 | **Phase 2 edited** (phase 1 is the producer and owns the spelling). Steps 1, 3 and 3b now pass four repeated `--entry` flags; the Interface Contract's Requires table was rewritten against phase 1's actual `_parse()`, flag by flag |
| 2 | Phase 2 passed `--hazard 0.040` / `0.051`, rounded from phase 1's measured 4.00158% / 5.09113%. Phase 1 accepts a number but prints its provenance as *"given on the command line"*; its design note says *"Nothing is hardcoded"* | Contract drift | 1, 2 | **Phase 2 edited** to `--hazard unserved` and `--hazard all`, which make the harness recompute both rates from the store's own membership and print them as measured. See Decisions |
| 3 | Phase 1's Handoffs name the `--csv` output as what phase 2 consumes; phase 2 never passed `--csv` and told its implementer to transcribe a terminal table by eye | Unmet assumption | 1, 2 | **Phase 2 edited**: `--csv` on every run, and Step 4 now extracts the numbers from the CSV with a script instead of by transcription |
| 4 | **`r = 0` is not the unstressed baseline.** Phase 1 measured ~1 point of CAGR a year lost to universe thinning alone (11.68% unstressed vs 10.72% at `r = 0`) and made it handoff #1. Phase 2's design section had no unstressed row, no `r = 0` row, and prose calling `r = 0` *"what the backtest has been assuming all along"* — exactly the conflation phase 1 warned against | Unmet assumption / correctness | 1, 2 | **Phase 2 edited**: Step 4's working table gained three columns (unstressed CAGR, `r = 0` CAGR, thinning cost); Step 6's section gained a first table showing all three and a paragraph saying *"no stress is the first column"*; the insight body gained a plain-words sentence; a new exit criterion pins it |
| 5 | Phase 1's handoff #3 (the harness injects the historical *rate* into ~409 priced survivors, ~151 deaths a draw, **not** the historical count of 404) was not carried into phase 2's write-up, so a reader could read 151 as "the missing 404" | Gap | 1, 2 | **Phase 2 edited**: a fourth stated limit in Step 6's section, and an exit criterion |
| 6 | **A wrong number propagated.** `phase-3.md` said MOM-FR is *"12th by DSR and 7th by MAR"* | Contract drift | 3 | **Phase 3 edited** to **8th of 26 by MAR**. Re-measured by the reconciler through `store.owner_failures` + `store.verdict` at N = 110: 26 clear all five, DSR rank 12 of 26, MAR rank 8 of 26, and the seven MARs strictly above 0.684030 are 0.856651, 0.816117, 0.792666, 0.791111, 0.768371, 0.763098, 0.749975 — reproducing phase 5's measurement exactly. **Phase 5's "7th by MAR" strings were left alone**: they are its own account of the correction, and deleting them would delete the correction |
| 7 | Phase 5's contract, §3 blockquote and handoffs asked the reconciler to fix the index's and the analysis's "7th by MAR" — both of which had already been corrected | Contract drift | 5 | **Phase 5 edited**: those three places now record the correction as *applied*, name `phase-3.md` as the last carrier, and warn the implementer not to "fix" the surviving "7th" strings inside phase 5's own narrative |
| 8 | The index's phase table said phase 2 is **2 files**. It must also regenerate `web/data/lab.json`: `engine/tests/test_lab_snapshot.py:449` pins that file byte-for-byte to the export of `lab/lab.sqlite`, and the phase appends an `insights` row | Gap | 2 | **Index edited** to 3 files, package `web/data` added, the regeneration written into the phase's Owns and exit criteria. Phase 2 already had the step; the index did not know |
| 9 | The index's phase table said phase 4 is **2 files** and titled it *"The dev gate keeps its trades bar, on the record"*. Phase 4 had already cancelled its handover note mid-planning, because the peer's design §13 and `dev.py:85-89` now cover it | Duplicate work | 4 | **Index edited**: 1 file, package `engine/tests` only, retitled **"A test that pins the dev gate's trades bar"**, and the cancellation recorded as *cancelled, not deferred* with "nobody should write it" |
| 10 | Analysis Impact Point 7 (`docs/handover/2026-10-07-go-live-item-1-calibration.md`, *"R2's briefing, both branches alive"*) is owned by **no phase** after that cancellation | Gap / unowned impact point | 4 | **Resolved as deliberately unowned, not dropped.** The owner has since *decided* Q2, so a briefing offering "both branches" would brief a closed question; design §13 is the record. R2 keeps its owner (phase 4) and its deliverable is the executable guard. See Decisions |
| 11 | Analysis Impact Point 4 says phase 2's design section is *"a new §13"*; §13 is now the peer's | Contract drift | 2 | **No plan change needed** — phase 2 already resolves the number by reading the file and never hardcodes it. The index and phase 2 now both say **§14**, verified: the file is 284 lines and ends at `## 13.` The analysis file is left as the historical record |
| 12 | **The two design-doc appends could not collide, but neither plan said so.** Phase 2 → `2026-10-03-seer-design.md` §14; phase 3 → `2026-10-04-method-lab-design.md` §8 | File collision (cleared) | 2, 3 | **Both plans edited** to state it explicitly: different files, no shared region, and neither hardcodes its number. Re-verified at `ba8a05b`: seer-design ends at §13/284 lines, method-lab-design ends at §7.6/281 lines |
| 13 | Phase 2's Step 0a/Step 5 were written for a world where `seer-fc`'s §13 had **not** landed, with a contingency for taking 13 and leaving a gap. It has landed | File collision (stale quote) | 2 | **Phase 2 edited**: §13 is present at line 232, `LAST` is 13, `NEXT` is 14, no contingency. The "§13 missing" branch is marked dead |
| 14 | Phase 5's Step 3, Files table and Requires said *"the worktree copy is still the old text"* and sent the reader to the **main checkout** to confirm design §1 item 1 | File collision (stale quote) | 5 | **Phase 5 edited**: the worktree's own copy now carries it (line 17, with §13 at line 232) and is the thing to grep. Still read-only to phase 5 |
| 15 | Phase 4's Step 1 said **`git rebase origin/main`**. The worktree is shared with concurrent sessions; a rebase rewrites a sibling phase's commits | Ordering violation | 4 | **Phase 4 edited** to `git merge --no-edit origin/main`, with the reason stated. Phase 2 already merged; the index now says merge-never-rebase for the whole set |
| 16 | **Phases 1, 3 and 5 had no commit step** — only phases 2 and 4 did. The standing invariant is an explicit path allowlist, never `git add -A`, because peers' edits show in `git status` | Gap | 1, 3, 5 | **All three edited**: each now has a commit with a named allowlist, a written message carrying the required `Co-Authored-By` trailer, and `git show --stat --name-only HEAD` as the check that the commit's file list *equals* the allowlist |
| 17 | Phases 1, 3 and 5 asserted **`git status` is clean / shows only my files**, unscoped. In a shared worktree that reads as a failure that is not one | Contract drift | 1, 3, 5 | **All three edited** to scope the check to their own paths and to say that peers' in-flight work is expected; the authoritative check moved to the commit's file list |
| 18 | Phases 3 and 5 asserted the full suite is exactly **3197 passed**; phase 4 asserted exactly 3200. In the swarm, phases 1 and 4 add tests to the same worktree, so wave-2 phases will legitimately see more | Broken-build phase (false red) | 1, 3, 4, 5 | **All four edited** to assert **`0 failed, 0 skipped` at a count no lower than 3197**. The baseline was re-counted by the reconciler at `ba8a05b`: **3197 collected**, unchanged by the peer's go-live commit |
| 19 | **A one-command window in which the shared worktree is red.** Between phase 2's Step 7 (the `insights` row) and Step 8 (regenerating `web/data/lab.json`), `test_lab_snapshot.py:449` fails for every session in the worktree — including phase 5, which runs in the same wave | Broken-build phase | 2, 5 | **Both edited**: phase 2 must run Steps 7 and 8 back to back with nothing between them and must not start a suite run inside the window; phase 5 is told that a lone snapshot failure is phase 2 mid-window, to be waited out rather than investigated |
| 20 | **The run-cost budget was 2–3 s a run** (analysis M1, a quiet machine) in the index and in phase 2, while phase 1's own P4 measured **5–11 s under concurrent load** — which is what a swarm sees. Phase 1 then told the reader to *"plan on M1's numbers"* | Contract drift | 1, 2 | **Both edited.** Phase 1 now says plan on 5–11 s and keeps 2–3 s only as the labelled idle figure; phase 2's Step 3 carries a two-column budget table (≈ 4.5–9.8 h single-threaded, ≈ 50 min – 1 h 45 at `--jobs 6`), Step 1's smoke is budgeted at 60–90 s, and the index's Decisions row is corrected. **`--jobs` keeps phase 1's default of 1**; phase 2 opts in to 6 explicitly after measuring RSS |
| 21 | Phase 3's Requires said the owner's 18-month item 1 *"is being made"* by `seer-fc`, and quoted base `3683d7b` headings | Unmet assumption (cleared) | 3 | **Phase 3 edited**: it has landed, verified at line 17 with §13 as the revision note; the heading expectations re-verified at `ba8a05b` (unchanged) |
| 22 | Phase 4's dual-world Step 1 ("landed" / "not landed") left the implementer to discover which world they were in | Contract drift | 4 | **Phase 4 edited**: the "landed" world is marked as the one the branch is already in, with the four verifications; the "not landed" branch is kept only so a revert cannot break the test, and is marked unreachable from the current `origin/main` |
| 23 | Phase 5's `§<RULE>` / `<RULE-TITLE>` placeholders and its `grep -n 'RULE'` must-be-empty gate against phase 3's promised handles | Cross-phase interface (cleared) | 3, 5 | **Verified, no change needed.** Phase 3's contract promises §x.1–§x.6 with named refusals `R1`–`R3` and triggers `T1`–`T5`, and resolves its own number at write time (§8 expected, §9 if something appended first). Phase 5 never hardcodes §8 inside its document text, reads the real number and title in Step 1, and none of phase 3's labels contains the string `RULE`, so the gate cannot false-positive |

Round 2 — **an independent verification pass over the phase-1 → phase-2 call surface only**, after
round 1 reported `contract_changed: true`. Every flag, every CSV column, every unit and every
reported quantity was re-derived from phase 1's actual code blocks against phase 2's actual
invocations. Four of round 1's five claims verified clean; one left a live defect behind it.

| # | Conflict | Kind | Phases | Resolution |
|---|---|---|---|---|
| 24 | **Phase 2 would have stopped on the expected result.** Step 3b read *"If either run fails **or produces no break-even for an entry**, the phase stops here and reports the failure."* But phase 1's `break_even(points)` returns `None` **by design** when the mean edge is still positive at `r = -100%`, its docstring says the solver *"refuses to extrapolate past the data it has"*, and phase 1's handoff #2 says the off-grid case **is the likely finding** (smoke: mean edge still **+0.32 pts/yr** at a total loss on `M0022-W-TV16`). Phase 2's own Step 4 and Step 6's first verdict branch already treat it as a strong result — so the phase contradicted itself, and the branch that would have fired first was the one that halts | Contract drift (phase 2 against phase 1 **and** against itself) | 1, 2 | **Phase 2 edited.** Step 3b now splits the two cases: a *failed* run (crash, unresolved id, missing store, truncated CSV) stops the phase; a *completed* run reporting `NONE on this grid` is named as a first-class expected result, carried into Step 4 as *"worse than −100%, i.e. never"* and written up through Step 6's first branch. Phase 2's exit criterion 1 and this index's phase-2 exit criteria were widened to accept it. See Decisions |
| 25 | **Two of phase 2's reported quantities are not CSV columns**, yet Step 4 told its implementer to read everything *"out of the two `--csv` files, not off the terminal by eye"*. The break-even and the per-seed spread are solved **across** runs and exist only in phase 1's stdout; `{{SURVIVORS}}` is likewise a stdout line (`eligible to be killed: …`). The CSV is one row per run and has no break-even column | Contract drift | 2 | **Phase 2 edited.** Step 4 now says which quantities come from the CSV (unstressed CAGR, `r = 0` CAGR, thinning cost, deaths per draw) and which from the tee'd stdout, with a `grep -E` that pulls the three stdout lines out of both transcripts. The extraction script gained a `deaths per draw` line so `{{DEATHS_PER_SEED}}` is measured, not eyeballed |
| 26 | **Phase 1 owned the `--csv` spellings but never stated them.** The column names, their order and — the dangerous part — their **units** lived only in phase 1's code block and in phase 2's restatement of it. A silent units drift here (fractions read as percent, or `edge_points_per_year` multiplied by 100 twice) puts a wrong number in the owner's design doc, which is this set's worst failure mode | Gap (unowned contract surface) | 1 | **Phase 1 edited**: its Interface Contract now carries the full `--csv` schema — 13 columns in order, fractions at 6 dp for `cagr`/`max_drawdown`/`total_return`/`spy_cagr`, percentage points for `edge_points_per_year`, empty `delisting_return` + `seed` on the unstressed row — and states that `break_even(...) -> None` is a contract value rather than an error. The index's phase-1 exit criteria say so too |
| 27 | Phase 2's **Files table** still read *"after the file's last line — today line 227, after `seer-fc`'s §13 lands it will be further down"*. Row 13 of round 1 fixed Steps 0a, 5 and 6 to the post-`ba8a05b` world (284 lines, §13 at line 232) but missed the Files table, which then disagreed with its own plan three steps later | File collision (stale quote) | 2 | **Phase 2 edited** to **284 lines, the tail of `seer-fc`'s §13**, with the 227 named as the pre-§13 figure and `wc -l` at write time kept as the authority |
| 28 | Phase 2's one-command red window (Steps 7 → 8) was stated in its **Handoffs** and in this index, but **not at Step 7 itself**, where the implementer actually is when the window opens | Gap | 2, 5 | **Phase 2 edited**: Step 7 now ends with *"Run Step 8 immediately after this command, with nothing in between — not a test run, not a commit, not a break"*, naming phase 5 as the other session it would turn red |

**Verified clean in round 2, no edit needed** (listed so a third pass does not re-derive them):
`--entry` is `action="append"` and phase 2 passes **four separate flags** carrying exactly phase 1's
four `ROSTER` candidate ids (`M0022-W-TV16`, `M0007-N20-RAW`, `M0002-REL-85`, `M0008-N30-C07`),
which `_entries()` resolves through `by_id` to the roster names the CSV's `entry` column then
carries; `--hazard unserved` / `--hazard all` are both literal branches of phase 1's `_rate()`;
`--returns 0.00,-0.10,…,-1.00` is phase 1's `RETURNS` default exactly and every value passes
`_returns()`'s `[-1, 0]` check (and `--returns -0.30` in Step 1's memory probe parses, because
argparse's negative-number matcher accepts it when no option string looks like a number);
`--seeds 100`, `--seed0` defaulted, `--jobs 6` and `--decline-sessions` defaulted all match type and
range; **`--store "$STORE"` is passed on every one of the four invocations** (Step 1 ×2, Step 3,
Step 3b), which is load-bearing because `config.REPO_ROOT` follows `PYTHONPATH` into a worktree that
has no `engine/.research`; `--csv` is on every run and the scratch path is outside both of
`_write_csv`'s forbidden roots; phase 2's restated 13-column CSV header matches `_write_csv`'s
`writerow` exactly, in order; Step 4's `$3==""` and `delisting_return == "0.0000"` tests match
`f"{r:.4f}"` formatting and the empty-field base rows that `main()` prepends via
`[bases[name] …] + outcomes`; the units in Step 4's arithmetic (`cagr * 100`, `edge` used raw) match
phase 1's fractions and its `(cagr - spy_cagr) * 100` property; the unstressed row, the `r = 0` row
and the derived thinning cost all exist; and the ~409 survivors / ~151 deaths / 404-vs-522 "rate,
not count" handoff is carried in phase 2's design section limits 2 and 3 and in its exit criteria 5
and 6. The round-1 side claims also hold: phase 3 says **8th of 26 by MAR**; phase 2 is 3 files
including `web/data/lab.json`; phase 4 is 1 test-only file; phases 1, 3 and 5 each carry a commit
with a named path allowlist and `git show --stat --name-only HEAD` as the check; `git rebase`
survives nowhere but as a prohibition; and no phase *asserts* an exact pass count (phase 4 line 470
prints 3200 as an illustration and then says in the same paragraph that what it asserts is
`0 failed`, `0 skipped` and exactly 3 passes from its own file).

**Dependency re-check after every edit:** `2 → 1` and `5 → 3` are the only edges and both point
backward. Nothing is deleted anywhere in the set, so there is no deleted-then-used case. Every
phase builds and tests green on its own. Every file with more than one reader has exactly one
writer: `2026-10-03-seer-design.md` (phase 2 writes, phases 4 and 5 read), `2026-10-04-method-lab-design.md`
(phase 3 writes, phase 5 reads), `lab/lab.sqlite` + `web/data/lab.json` (phase 2 writes, phases 4
and 5 read-only), and phase 1's three files (phase 1 writes, phase 2 runs).

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| Where the stress test lives: a lab method, or a script | **A script + a tested module**, recording no trial | 5: the user's raw input — Q1's own parenthetical, *"a lab method would spend a trial and move N, which is probably wrong for a diagnostic"* — plus 6: `survivorship_coverage.py`'s precedent |
| Whether it needs the position level or can be approximated from the recorded curves | **Position level; the backtest is re-run** | 6: measured — `trials.curve_json` is month-end equity only and carries no positions, so a perturbed path cannot be derived from an unperturbed one. Affordable because one run measures at 2–3 s on an idle machine and **5–11 s under swarm load** (phase 1's P4), which is what phase 2's budget now uses |
| How delistings are injected: kill served survivors, or resurrect the 404 missing names with synthetic price paths | **Kill served survivors at the measured hazard** | 5: the user's raw input — *"inject synthetic delistings into the ranking universe at the historical rate"*. Resurrection would fabricate every price in the test, which is the one thing no free source can supply |
| Whether an injected death is abrupt or preceded by a visible decline | **Abrupt, as the conservative base case**, with a forewarned variant as a stated sensitivity | 6: an abrupt death gives the strategy no chance to exit, so the break-even return it yields is an upper bound on the damage — the honest direction for a test meant to reassure |
| Which hazard rate to inject at | **4.0%/yr**, the measured unserved-exit rate, with the 5.1%/yr all-exit rate as the upper sensitivity | 6: measured from the store's own membership (analysis M2) |
| R2's deliverable, after the owner decided Q2 mid-analysis | **The dev-gate asymmetry only** — a briefing on item 1 would duplicate work `seer-fc` is already doing and has claimed the files for | 5: the user's raw input (Q2 asked for the owner to be told; they have since decided) + the peer's explicit file claim |
| Whether phase 4 changes `_MIN_TRADES` to match the new item 1 | **No — document and guard it** | 1: invariant 5 (no edit to the dev gate's recorded basis) + 6: measured, the change would alter zero verdicts today because both affected trials carry `dsr IS NULL` |
| Which section number phase 2's design-doc result takes | **Resolved at write time by reading the file**, expected §14 | 6: `seer-fc` has claimed §13; hardcoding a number would collide |
| Q3's "slowest path to a verdict" argument | **Void, and recorded as void** | 4: the index's own Requirements table, as revised by the owner's Q2 decision — 18 months flat applies to every entry equally |
| What Q4's rule is built on: the 14.9/19.4/20.7-month table, or 18 months flat | **18 months flat** | 5: the peer's measurement, which supersedes the handover's table, confirmed against the owner's own decision |

**Settled by the reconciler on 2026-10-07**, each on the highest rung that spoke. The losing side
was edited out of the plan file rather than left standing beside the winner.

| Fork | Chosen | Rung |
|---|---|---|
| Phase 2 passes the hazard as a **rounded number** (`--hazard 0.040`) or as phase 1's **symbol** (`--hazard unserved`) | **The symbol.** Phase 2's Steps 3 and 3b now pass `unserved` and `all`; the rounded numbers are edited out | **3: the plans' code blocks.** Phase 1's `_rate()` returns the *measured* `unserved_exit_rate` (4.00158%/yr) and labels it *"the measured unpriced-exit rate"*, while a numeric argument is labelled *"given on the command line"*. Phase 1's own P1 note says *"Nothing is hardcoded"*, and the owner's standing preference (index *Why*) is measuring over estimating. A rounded constant in a plan is an estimate wearing a measurement's clothes |
| Phase 4's cancelled handover note — **reinstate** it (the analysis's Impact Point 7 still demands a file) or leave the impact point **unowned** | **Unowned, deliberately, and recorded as cancelled.** No phase writes `docs/handover/2026-10-07-go-live-item-1-calibration.md` | **4: the index's own Why and Requirements table.** Impact Point 7 specified *"R2's briefing, **both branches alive**"* — a briefing that puts a fork to the owner. The owner has since **decided** that fork (index *What changed*, item 1), and `seer-fc` landed the decision as design §13 at `ba8a05b`. A document offering both branches of a closed question is not a gap in coverage, it is a stale record. R2 keeps its owner and its measurable deliverable: the executable guard nothing else provides |
| What phase 2's design section calls the `r = 0` column | **Not "no stress".** The unstressed run and the `r = 0` run are separate rows; the gap between them is named as the cost of a thinner ranking pool | **2: the phases' exit criteria**, via phase 1's Handoffs, which state the gap as measured (11.68% → 10.72% on `M0022-W-TV16`) and say *"phase 2 must report that as its own number"*. Phase 2's draft said the opposite by implication; the draft lost |
| Which pass count every phase asserts | **`0 failed, 0 skipped` at a count ≥ 3197**, never a specific total | **1: a stated invariant** (invariant 1 — *"the full suite passes at the end of each phase"*). In a shared worktree a specific total is not a statement about the suite passing, it is a statement about which siblings have landed, and it goes red for the wrong reason. 3197 re-counted at `ba8a05b` |
| How each phase brings its branch current: `rebase` (phase 4) or `merge` (phase 2) | **Merge, everywhere** | **1: a stated invariant**, in its spirit — the set's shared-worktree rule exists because concurrent sessions' work is live in this tree. A rebase rewrites a sibling's commits, which is the same hazard `git add -A` carries and the same answer. 6: phase 2's and phase 5's surrounding convention already said merge |
| Where phase 2's design section number comes from, now that §13 has landed | **§14, still resolved at write time by reading the file** | **6: measured** — the file at `ba8a05b` is 284 lines ending at `## 13.`, so 14 is free with no gap. The *expected* number is now stated as a fact rather than a contingency, but the read-at-write-time mechanism is kept, because a peer may append again before phase 2 runs |

**Settled in round 2 by the verifying reconciler on 2026-10-07.**

| Fork | Chosen | Rung |
|---|---|---|
| "No break-even on this grid": phase 2's Step 3b said **stop and report a failure**; its Step 4 and Step 6 said **write it up as the strongest possible answer**. Two branches, both live, in one plan file | **Write it up. It is an expected result, never a stop condition.** Step 3b's halt is narrowed to runs that actually fail; the losing branch is edited out rather than left beside the winner | **3: the plans' code blocks.** Phase 1's `break_even(points) -> float \| None` returns `None` deliberately — its docstring: *"None when the edge is still positive at the most negative point… the harness refuses to extrapolate past the data it has"* — and `_print_entry` has a written-out branch for it. Rung 2 agrees (phase 1's handoff #2 calls the off-grid case the likely finding, measured at **+0.32 pts/yr** at `r = -100%`), and so does rung 4 (the index's *Why*: Q1 asks for a break-even *and a judgement on whether it is plausible*; "it cannot be reached at all" answers both). A plan that halts on its own expected outcome strands an unattended phase session |

## Open Questions

*(**Empty, and verified empty after reconciliation.** Every fork above was decided — at planning on
the rung named beside it, or by the reconciler on 2026-10-07 on the rung named beside it. None is a
fork where every branch is irreversible: the stress harness adds files, both design-doc changes are
appends, every document is a document, and the one conditional code edit in phase 5 is gated behind
a verdict this plan expects to be "keep". Every requirement id has an owning phase, so there is no
unowned `R` to park here either.*

*One item is irreversible and is **not** a fork: phase 2's `insights` row, which the table refuses
to UPDATE or DELETE by trigger. It is not parked as a question because there is nothing to choose
— the lab's standing rule already says a wrong insight is corrected by appending a newer one, and
phase 2's Rollback says so in those words. Proofread the body before running the command.)*

## Rollback

**Per phase.** Phase 1 adds three files — delete them. Phase 2 appends one design-doc section
(revert the commit) and one `insights` row; `insights` is append-only by trigger, so a wrong
insight is corrected by appending a newer one, never by deleting it — that is the lab's rule and
this plan does not make an exception to it. Phase 3 appends one method-lab design section, phase 4 adds one
test file and phase 5 one document; revert the commits. No phase migrates a database, changes a `config_digest`, or writes a trial, so
no rollback needs to repair the lab's record.

**As a whole.** `git branch -D feature/delisting-stress-roster-rules` and remove the worktree. The
lab database, the research store and the paper roster are untouched by every phase except phase
2's appended insight and phase 5's conditional roster edit.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f DELISTING_STRESS_ROSTER_RULES_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f DELISTING_STRESS_ROSTER_RULES_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan DELISTING_STRESS_ROSTER_RULES_PLAN.md
