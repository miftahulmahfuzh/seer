# Plan: Hold thirty-five, and close the four questions 2026-10-14 opened

**Slug:** `roster-35-four-methods`
**Date:** 2026-10-14 15:07:38 WIB
**Analysis:** `docs/analyzer/20261014-150738-B7K4_code_analyzer.md`
**Worktree:** none — the main checkout `/home/miftah/seer`
**Branch:** `main` (base: `origin/main` @ `661870d`)
**Phases:** 5
**Status:** complete (2026-10-14)
**Reconciled:** 2026-10-14, one round, 11 conflicts found and resolved
**Coordinator:** `orch-roster-35-four-methods`

---

## Why

The `/analyze` invocation, verbatim:

> `docs/plans/HANDOVER_20261014-the-bar-the-screen-and-the-width.md` — pick up where 2026-10-14
> left off. Read the handover first; it carries the state, the findings not to re-derive, the
> decisions not to silently reverse, and the traps. The owner's live decision (hold 35 names
> rather than 20) is his to accept or decline and is NOT yours to implement. The research work
> worth planning is M0155 (a single-name brake, which attacks the one hole both existing defences
> leave open), M0156 (survivorship-check M0002-REL-85, the roster book that has never been checked
> at all), M0149 (the asymmetry book braked by its own falling account rather than the market's
> trend) and M0148 (a time-lock on the switch). Test-window looks are 4 and must stay 4.

The owner, mid-analysis:

> let's change our seer roster to hold 35 stocks instead of 20

The first message reserved the width decision to the owner. The second is the owner making it. So
the width change is in scope and is R1; the four method ideas are R2–R5 unchanged.

The evidence behind R1, from M0152 on the survivorship-check store — the price history that keeps
the companies that went bankrupt, were bought or were renamed:

| | worst fall | yearly |
|---|---|---|
| 20 names (the roster today) | **25.05%** — outside the owner's 25% bar | 11.98% |
| 35 names | **20.11%** | **12.11%** |

The wider book is safer *and* earns slightly more on the honest tape. MAR peaks at 35 on both
stores. The mechanism is dated, not inferred: spring 2006, when SPY dipped 2% and made a new high
by September while the 20-name book lost 21.8% — a single holding collapsing in a rising market,
the only width-sensitive episode in twenty years, and the ordinary kind of accident rather than a
crisis that may not repeat.

**Two caveats the table does not carry, added at reconciliation so the index does not claim more
than was measured.** First, the 35-name row above is `M0139-N35-TBAND`, and the variant phase 2
admits is `M0139-N35-EBAND` — the same picks and the same width on the rule preset `RAW-FR-GT`
runs today, because taking the tband twin would move the width *and* the rebalance basis at once
and break the controlled comparison against `RMW-FR-GT`. On the dev store the two differ by 0.012
points of drawdown and 0.19 points of CAGR, so the width conclusion transfers, but **the
check-store reading is the twin's and the admission note and migration 021 must say so.** Second,
the post-2009 column of the same curve reads `era_2009_2015_edge` of −0.0022 at 20 names and
−0.0168 at 35 on the check store: over the years most like today both widths lose to SPY on the
honest tape and the wider one loses by more. **The width case is a drawdown case, not a return
case**, and nothing written for the owner may let the 12.11% headline hide that.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Change the Seer roster to hold 35 stocks instead of 20 | 2 |
| R2 | M0155 — a single-name brake: trim a holding falling apart while the market is fine | 3 |
| R3 | M0156 — survivorship-check M0002-REL-85, the roster book never checked at all | 1 |
| R4 | M0149 — the asymmetry book braked by its own falling account, not the market's trend | 4 |
| R5 | M0148 — a time-lock on the safety switch | 5 |
| R6 | Do not spend a test-window look: the count is 4 and must stay 4 | 1, 2, 3, 4, 5 |

Reconciliation moved no step between phases, so no `R` moved: the map above is the draft's and the
plans' alike, re-checked against every phase's **Satisfies** line after the edits.

## Scope

**In scope**

- One new paper roster entry holding 35 names, replacing `RAW-FR-GT`, with its own paper clock:
  `paper/roster.py`, `strategies/evidence.py`, a `db/migrations/021_*.sql`, the digest pins and
  the roster id lists in `engine/tests/`, the runbook's roster table, `web/lib/sera/paper.test.ts`
  and a regenerated `web/data/lab.json`.
- Four lab method ideas carried from `idea` to a written verdict: M0156 (free survivorship read,
  then a width sweep if the read warrants it), M0155, M0149, M0148. Each is a method file
  committed *before* its run, a `lab run`, an analysis, a verdict and a `lab stage`.
- One post-set `lab reevaluate`, owned by whichever lab phase lands last.

**Out of scope, and why**

- **`MOM-FR-GT` is not re-widened.** It is the roster's other 20-name book and it has never been
  measured at any width on any store — that is precisely what phase 1 exists to find out. Widening
  it on M0152's number would apply a measurement of the residual-momentum picking rule to a
  different picking rule. Phase 1 produces its own number and records acting on it as a **future**
  decision; a second roster change is then its own argued commit, not a retrofit into phase 2's
  migration. Checked at reconciliation: phase 1 plans no roster edit and phase 2 plans no
  `MOM-FR-GT` edit.
- **`RMW-FR-GT` is not re-widened.** Same picks as `RAW` plus a volatility brake, and its recorded
  fall is 14.3% — well inside the bar. No 35-name variant of it has ever run.
- **`MVW-FR-GT` is not touched.** It already holds 30.
- **`backtest/registry.py` is not appended to.** It is the P7a dev-run candidate set, fixed before
  the run with `candidate_digest` pinned; `promote` never writes it and neither does this plan.
- **`docs/lab/survivorship/grid.csv` is not appended to.** `survivorship_record.GRID_PATH` points
  the hard gate's D16 at that exact file; appending would change which promotions the gate refuses
  as a side effect of a research run. New measurements land as their own dated files. This is a
  2026-10-14 decision being upheld, not re-opened. Checked at reconciliation: no phase appends to
  it, and phases 1 and 3 assert it is byte-identical to `661870d` in their exit criteria.
- **`lab test` is never called.** No phase reads the test window. Checked at reconciliation: no
  plan contains a `lab test` invocation and no plan points a `--store` at `engine/.research-test`.
- **No shared params dataclass gains a field.** `ResidParams`, `FactorParams`, `TradeRules`,
  `AsymParams` and every other shared params type are imported, never extended
  (`seer-shared-params-cannot-gain-a-field`); each new method's state lives in its own file behind
  its own allocator id. Checked at reconciliation across all four method plans.
- **No frozen method file is edited.** `m0002`, `m0007`, `m0011`, `m0088`, `m0101`, `m0109`,
  `m0110`, `m0113`, `m0128`, `m0133`, `m0139`, `m0143` and `m0152` are imported read-only by one
  or more phases and edited by none. Checked at reconciliation.
- **Closed records are not edited.** M0139's recorded verdict ("Twenty names still wins") was true
  of the dev store and is frozen; the correction is stated in the new entry's admission note and
  in migration 021's prose.

## Invariants

Rules every phase holds. A phase that cannot hold one stops and says so rather than working around
it. Invariants 7, 12 and 13 were written at reconciliation and are the ones the parallel planners
could not have agreed on by themselves.

1. **The tree is green at the end of every phase.** `engine/.venv/bin/ruff check engine`,
   `engine/.venv/bin/pytest engine/tests`, and for phase 2 also `cd web && npx tsc --noEmit && npm test`.
   DB tests need Postgres and **CI fails if they skip** — export `PG_TEST_URL` before the suite.
2. **Test-window looks stay at 4.** Check it before and after:
   `engine/.venv/bin/python -m seer_engine lab status`. No phase runs `lab test`, and no phase
   points any `--store` at `engine/.research-test`.
3. **The commit is the pre-registration.** A method file is committed and pushed *before*
   `lab run MNNNN`. The runner refuses an uncommitted or dirty file, and refuses a `config_digest`
   already recorded. Never write the file after seeing a result.
4. **No started roster entry's spec digest moves.** Phase 2 adds a `PINS` entry; it may not change
   one. A moved digest fails the next paper night with `SpecMismatch` and rolls the whole night
   back.
5. **Commit by explicit pathspec, never `git add -A` and never `reset --hard`.** Sessions share
   this one checkout and one index (`seer-swarm-shared-worktree`). The sole exception is the lab
   pair below.
6. **The lab pair commits through the index.** `lab stage` writes `web/data/lab.json` and
   `git add`s it with `lab/lab.sqlite`; `git commit -- <paths>` re-reads the working tree and
   defeats it (`seer-lab-stage-commit-needs-the-index`). Commit those two with a bare
   `git commit -m …` right after `lab stage`, and nothing else in that commit.
7. **The lab write lock — one mechanism, defined here, and identical in all five phase plans.**
   The draft said "serialise the stage+commit+push" and never defined a lock; `lab stage`'s own
   `BEGIN EXCLUSIVE` (`commands/lab.py:2824`) covers only `write_snapshot` + `git add` and is
   released before the commit, so it is **not** the lock meant.

   ```bash
   LAB_LOCK=/home/miftah/seer/.git/seer-lab.lock   # inside .git/: no `git add` can ever reach it

   # TAKE IT. fd 9 is the handle; the kernel drops it when this shell exits, even on a crash.
   exec 9>"$LAB_LOCK"
   flock -w 21600 9 || { echo "lab lock still held after 6h -- find out who has it; do NOT force"; exit 1; }
   echo "phase-N pid $$ $(date -Is)" >&9        # who holds it, for a human who opens the file

   # PROVE THE PAIR IS CLEAN. When nobody holds the lock this must pass. If it fails, a session
   # died inside its window and the tree is in an unknown state -- STOP and report, do not repair.
   cd /home/miftah/seer
   git fetch origin && git merge --ff-only origin/main
   git diff --quiet HEAD -- lab/lab.sqlite web/data/lab.json || {
     echo "the lab pair is dirty and nobody held the lock -- STOP"; flock -u 9; exit 1; }

   #   ... the critical section ...

   flock -u 9
   ```

   **The rule, in one line: you may not release the lock with `lab/lab.sqlite` or
   `web/data/lab.json` differing from `HEAD`.**

   **What is inside a hold:** every command that writes a lab row — `lab survivorship` (it
   journals an `observation`), `lab run`, `lab note`, `lab insight`, `lab seen`, `lab reevaluate`
   — plus the `lab stage` (or, for phase 2, `lab export-json`), `git commit` and `git push` that
   return the pair to clean. **`lab run` is inside the hold**, so the four lab phases' runs queue
   rather than overlap. That reverses the draft's "the runs may overlap", and the reason is
   build-green: a run leaves the shared binary `lab/lab.sqlite` dirty for its whole duration, and
   while it is dirty (a) no other session can export a snapshot that matches the committed
   database, so phase 2's `web/data/lab.json` commit cannot be made correct, and (b) any other
   phase's `lab stage` would `git add` the half-finished run's rows into its own commit, because
   `lab stage` stages the whole file. Two independent measurements agree with the choice:
   `lab run`s contend on one sqlite file (phase 1 Step 5), and each run loads a whole research
   store at ~1 GB (`seer-research-store-memory-budget`), so four at once is RAM pressure on a
   16 GB machine. **The cost is honest and accepted: the four lab runs are serial and the set
   takes as long as their sum.**

   **Take short holds, not one long one.** A hold that spans writing a method file starves every
   other session for nothing. Phase 1 takes two holds (Step 1, then Step 5→8); phases 3, 4 and 5
   take one each (their run through their push); phase 2 takes one, around its snapshot export.

   **What the lock buys:** when no session holds it,
   `git diff --quiet HEAD -- lab/lab.sqlite web/data/lab.json` is true — the only condition under
   which an exported snapshot matches the database committed beside it, which is exactly what
   `engine/tests/test_lab_snapshot.py:1054` byte-compares.

8. **On a rejected push, never `git pull --rebase`.** It replays a stale `lab.sqlite` over whatever
   the other phases wrote (`seer-rebase-replays-stale-lab-sqlite`). Fetch, check whether the
   incoming commits touch `lab/` or `web/data/lab.json`, and use a **mixed** `git reset` plus
   `git merge --ff-only` — never `--hard`. Re-run `lab stage` against the merged database and
   check trial `n` is contiguous before committing again.
9. **Any `lab` command opens `lab.sqlite` read-write and migrates it on connect, even a read.**
   Measured at reconciliation: at the current schema version (v7) `store.connect` leaves the bytes
   identical, so the note names a hazard rather than a certainty — but hash the file before a
   read-only command and restore it by path if the hash moved
   (`seer-lab-commands-migrate-lab-sqlite-on-connect`). `sqlite3.connect("file:…?mode=ro", uri=True)`
   is the only path that genuinely cannot touch it.
10. **Both stores, or the measurement does not count** — for any claim about width or a
    single-name fall. The dev store misses ~4 in 10 of the days companies sat in the index, so it
    is structurally blind to a holding that collapsed and left. Dev-only evidence for R2 is not
    evidence.
11. **Plain language in anything the owner reads.** No ids, digests or code in a site summary, a
    Sera page, an admission note or a verdict. And escape `%` as `%%` in argparse `help=` strings;
    never put a backtick inside a double-quoted `git commit -m` — it is command substitution and
    has silently eaten commit text here before.
12. **`web/data/lab.json` has one generator, one commit shape, and one recovery.** This replaces
    the draft's treatment of the snapshot as the lab phases' private artifact, which phase 2
    measured to be impossible.
    - It is **never hand-edited** and never `git checkout --`'d back. It is generated output; the
      only correct copy is the export of the `lab/lab.sqlite` committed beside it.
    - **Lab phases (1, 3, 4, 5) regenerate it with `lab stage`** and commit the pair with a bare
      `git commit -m …` (invariant 6).
    - **Phase 2 regenerates it with `lab export-json` and commits it ALONE by pathspec.**
      `export-json` writes the same bytes to the same path and never touches the git index
      (`commands/lab.py:_export_json` vs `_stage`); `lab stage` would `git add lab/lab.sqlite`
      too, and phase 2 writes no lab row, so staging it would sweep another phase's in-flight
      trials into phase 2's commit. `commands/lab.py:1757-1761` names `export-json` for exactly
      this situation.
    - **Phase 2 must regenerate it.** `lab/store.py:2966-2977` builds the snapshot's `paper` block
      from `roster.LAB_PROVENANCE` filtered by `roster.active()`. Retiring `RAW-FR-GT` changes the
      snapshot's bytes — measured: the `paper` array loses one element and gains another — and
      `engine/tests/test_lab_snapshot.py:1054` byte-compares the committed file against a live
      export. CI runs that test.
    - **Either generator runs inside the lab write lock**, whose precondition has already proved
      `lab/lab.sqlite` is identical to `HEAD`. So the snapshot committed is always the export of
      the database committed.
    - **Finding it ahead of your own commit is normal, not an error.** Another phase landed trials
      after you took your reading. Bring `HEAD` forward with `git merge --ff-only` (invariant 8),
      re-run your generator, and commit what comes out. If `git diff` is then empty, the other
      phase's commit already carries your change: commit nothing and say so in the close-out.
      **Whoever lands last is right, and that is by design** — the snapshot is a pure function of
      the database and the roster, so the last regeneration over the merged state is the only one
      that can be correct.
13. **`lab reevaluate` runs once, after the fourth lab run lands, and the last lab phase owns it.**
    All four lab phases move the lab's N by one **method** each, retroactively, on every published
    verdict. The draft left this unowned. A phase is last if, immediately after its own push, all
    four of `M0148`, `M0149`, `M0155`, `M0156` have left `idea` (a phase that decides not to run
    its method records that with `lab drop`, which keeps the check total). The last phase runs
    `lab reevaluate` inside the same lock hold, stages, commits and pushes; if it reports
    `0 method(s) moved`, it commits nothing and says so. The full step, with its runnable check, is
    written into all four lab phase plans.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | M0156 — the roster's other book on the honest tape | R3, R6 | `engine/lab` | 6 | — | NORMAL | `.workflows/plan/roster-35-four-methods/phase-1.md` | `P1-ENG-W35A` (done 2026-10-14) | — |
| 2 | Hold thirty-five: a new roster entry, and `RAW-FR-GT` retired | R1, R6 | `engine/paper`, `db`, `engine/tests`, `web` | 13 | — | HARD | `.workflows/plan/roster-35-four-methods/phase-2.md` | `P1-ENG-W35B` (done 2026-10-14) | — |
| 3 | M0155 — trim a holding falling apart while the market is fine | R2, R6 | `engine/lab` | 6 | — | HARD | `.workflows/plan/roster-35-four-methods/phase-3.md` | `P2-ENG-N60A` (done 2026-10-14) | — |
| 4 | M0149 — braked by its own falling account, not the market's trend | R4, R6 | `engine/lab` | 4 | — | HARD | `.workflows/plan/roster-35-four-methods/phase-4.md` | `P1-ENG-W35D` (done 2026-10-14) | — |
| 5 | M0148 — a time-lock on the switch | R5, R6 | `engine/lab` | 4 | — | NORMAL | `.workflows/plan/roster-35-four-methods/phase-5.md` | `P1-ENG-W35E` (done 2026-10-14) | — |

**No phase reads another's output, and no `Depends on` edge exists or was created.** What the five
share is mutable state, not interfaces: `lab/lab.sqlite` (phases 1, 3, 4, 5) and
`web/data/lab.json` (all five, phase 2 included). Invariants 6–9, 12 and 13 govern that state, and
they are the whole of the coupling. **Phases 2 and any one lab phase can run at the same time;
the four lab phases queue on the write lock** (invariant 7), so wall-clock for the set is one
phase-2 plus the sum of four lab runs.

### Phase 1 — M0156: the roster's other book on the honest tape
**Satisfies:** R3, R6
**Owns:** `lab survivorship M0002` and its report; the two dated CSVs and the dated `.md` under
`docs/lab/survivorship/`; the method file `m0156_regime_book_width.py`, its pre-registration
commit, its `lab run`, its five dev trials and its verdict.
**Does not touch:** `docs/lab/survivorship/grid.csv`. The roster — including `MOM-FR-GT`, whose
width this phase measures and deliberately does not act on. Any other method's files. `m0002`,
`m0007`, `m0128`, `m0152` are imported, never edited.
**Lock holds:** two — A around Step 1's `lab survivorship`, B from Step 5's `lab run` through
Step 8's push.
**Exit criteria:** the paired dev/check numbers for every recorded `M0002` variant are reported
and committed; if the check-store fall breaches the owner's 25% bar, that is stated plainly at the
top of the verdict as a live fact about half of what the owner holds; step two has either run and
produced a paired width curve, or is recorded as not warranted with its reason **and the method
row moved off `idea` with `lab drop`**; `grid.csv` is byte-identical to `661870d`; `lab status`
reads 4 test looks; the lock is released with `lab/lab.sqlite` and `web/data/lab.json` identical
to `HEAD`; the last-lab-phase check has been run and acted on (invariant 13).

### Phase 2 — Hold thirty-five: a new roster entry, and `RAW-FR-GT` retired
**Satisfies:** R1, R6
**Owns:** `paper/roster.py` (new params constant, `RESOLVER["RESIDMOM35"]`, `LAB_PROVENANCE`
entry, `SEED_ROWS` row, `RAW-FR-GT` retired), `strategies/evidence.py` (one key), the new
`db/migrations/021_roster_width_35.sql`, the `PINS` entry and the roster id lists in
`engine/tests/`, `engine/tests/test_promote_command.py`, `engine/tests/test_evidence.py`,
`web/lib/sera/paper.test.ts`, `.claude/skills/calculate-assets/build_audit.py`, the runbook's
roster table — and the `web/data/lab.json` regeneration that its own roster edit forces.
**Does not touch:** `backtest/registry.py`. **`lab/lab.sqlite` — nothing at all, not one row.**
The draft's boundary allowed for a `record_promotion` note; `promote` is unusable for this change
(see Decisions), `record_promotion` is therefore never called, and this phase writes no lab row
and stages no lab database. Any lab method file. `MOM-FR-GT`, `RMW-FR-GT`, `MVW-FR-GT`.
`docs/lab/survivorship/` — read only.
**Lock holds:** one, around Step 11's `lab export-json` + snapshot commit + push.
**Exit criteria:** `test_digests_are_pinned` green with exactly one new pin and no moved pin; the
migration-equality pair green against a migrated scratch Postgres (this is what replaces
`promote --dry-run`, which is **not** available and must not be attempted — see Decisions); the
whole engine suite and the `web` suite green with no DB test skipped;
`web/data/lab.json`'s `paper` block holds `RAW35-FR-GT` and no longer holds `RAW-FR-GT`, and
`test_the_committed_snapshot_is_the_export_of_the_committed_database` is green;
`lab status` reads 4 test looks and `lab/lab.sqlite` is byte-identical to `HEAD`; the runbook
records the retirement.

### Phase 3 — M0155: trim a holding falling apart while the market is fine
**Satisfies:** R2, R6
**Owns:** `engine/src/seer_engine/lab/methods/m0155_single_name_shortfall_brake.py` (allocator id
`"M0155"`), `engine/tests/test_lab_m0155_brake.py`, two dated files under
`docs/lab/survivorship/`, its pre-registration commit, its `lab run`, its measurement on **both**
stores, its verdict and its journalled insight.
**Does not touch:** any other method file. The roster. `grid.csv`. No shared params dataclass
gains a field; all new state is in `ShortfallBrakeParams` behind allocator id `"M0155"`.
**Lock holds:** one, from Step 4's `lab run` through Step 9's push.
**Exit criteria:** the method is pre-registered and run; the 2006 episode is measured at **twenty**
names on the check store against M0152's recorded curve, so the brake is priced against the width
answer rather than instead of it; the verdict says plainly whether the brake closes the hole, costs
more than a point a year, or is width in disguise; `grid.csv` unchanged; `lab status` reads 4 test
looks; the lock is released with the pair clean; the last-lab-phase check has been run and acted on.

### Phase 4 — M0149: braked by its own falling account, not the market's trend
**Satisfies:** R4, R6
**Owns:** `engine/src/seer_engine/lab/methods/m0149_own_account_brake.py` (allocator id `"M0149"`),
`engine/tests/test_m0149_own_account_brake.py`, its pre-registration commit, its `lab run`, the kin
reading that must come first, its three `seen` keys, its verdict.
**Does not touch:** any other method file. The roster. `grid.csv`. `M0133`'s frozen file —
`AsymParams` gains no field.
**Lock holds:** one, from Step 6's `lab run` through Step 9's push.
**Exit criteria:** the kin reading is taken **before** any analysis is written, per variant and not
only on the best twin; the method is pre-registered and run; the verdict states the fall, the
funded return against SPY TR, and the residual kin against all four test-failed books;
`lab status` reads 4 test looks; the lock is released with the pair clean; the last-lab-phase check
has been run and acted on.

### Phase 5 — M0148: a time-lock on the switch
**Satisfies:** R5, R6
**Owns:** `engine/src/seer_engine/lab/methods/m0148_switch_time_lock.py` (allocator id `"M0148"`),
`engine/tests/test_m0148_switch_time_lock.py`, its pre-registration commit, its `lab run`, its
three `seen` keys, its verdict.
**Does not touch:** any other method file. `m0143`'s and `m0113`'s frozen files. The roster.
`grid.csv`.
**Lock holds:** one, from Step 3's pre-registration push through Step 7's push.
**Exit criteria:** the K=0 arm reproduces `M0143-CALM-UP63` to the digit, or the time-lock
machinery is declared wrong and every other number in the batch unreadable; the verdict says how
often the lock actually bound, since a lock that binds on almost no sessions is a null result and
should be reported as one; `lab status` reads 4 test looks; the lock is released with the pair
clean; the last-lab-phase check has been run and acted on.

### Disjointness, checked at reconciliation

| | phase 1 | phase 3 | phase 4 | phase 5 |
|---|---|---|---|---|
| allocator id | `M0002` (reused, read-only import) | `M0155` | `M0149` | `M0148` |
| candidate prefix | `M0156-` | `M0155-` | `M0149-` | `M0148-` |
| `seen_keys` | `regime-vol-book-name-count`, `roster-relative-strength-book-width-on-the-check-store` | `per-holding-relative-shortfall-brake`, `single-name-exit-gated-on-a-rising-market`, `brake-reading-the-window-the-momentum-skip-hides` | `own-account-drawdown-brake-on-a-picked-book`, `ungated-asymmetry-book-own-vol-target`, `book-reading-brake-as-a-kin-escape` | `time-locked-trend-switch`, `switch-cooloff-hysteresis`, `hysteresis-in-the-time-domain` |

All four columns are disjoint, so `test_allocator_ids_are_unique_across_methods` holds and no
second `lab run` can be refused on a dedupe key after its backtest has been paid for. Phases 3 and
4 are both brakes on stock books and were the collision risk; their ids, prefixes and keys share
no token.

## Reconciliation Log

One round, 2026-10-14. Eleven conflicts required an edit; six checks the planners did not report
came back clean and are recorded so nobody re-runs them.

| # | Conflict | Phases | Resolution |
|---|---|---|---|
| 1 | **Contract drift / file collision — the index forbade what phase 2 must do.** The draft treated `web/data/lab.json` as the lab phases' artifact and phase 2's boundary excluded it. Verified against the code: `lab/store.py:2966-2977` builds the snapshot's `paper` block from `roster.LAB_PROVENANCE` filtered by `roster.active()`, and `engine/tests/test_lab_snapshot.py:1054` byte-compares the committed file against a live export. Retiring `RAW-FR-GT` changes the snapshot's bytes — reproduced, the `paper` array drops from four entries to three. | 1, 2, 3, 4, 5 | The old boundary is **withdrawn**. New invariant 12 is the single rule, written into the index and into all five plans: one generator, one commit shape, one recovery. Phase 2 regenerates with `lab export-json` and commits the snapshot **alone by pathspec**; lab phases use `lab stage` and commit the pair. Both run inside the write lock. |
| 2 | **File collision — whoever lands last wins, and the earlier commits can leave the snapshot disagreeing with the database.** All five phases regenerate `web/data/lab.json`; none of the drafts said what to do on finding it ahead. | 1, 2, 3, 4, 5 | Invariant 12's recovery clause, in all five plans: never hand-edit it, never `git checkout --` it back. Bring `HEAD` forward with `git merge --ff-only` (never `--rebase`), re-run your own generator, commit what comes out; if the diff is then empty, the other phase's commit already carries your change — commit nothing and say so. **Last-lands-wins is correct by construction**, because the snapshot is a pure function of the database and the roster. |
| 3 | **Contract drift — three tests encode an invariant phase 2 must move.** `test_promote_command.py:155`, `test_paper_roster.py:685` and `:724`. The riskiest edit in the set: loosening a passing test can erase a real guard. | 2 | **Scrutinised and upheld, with one addition.** `:155` is not an admissions test at all — it asserts `object_name_of` is a *total* inverse of `RESOLVER`, which is narrower than the production code has always implemented; phase 2's restatement brings the test up to the code and adds the consequence. `:685` is self-labelling as a census and its own comment instructs its successor. `:724`'s `dev["eligible"] == 0` **is** a historical accident — see Decisions, three independent proofs. Addition: phase 2's restated test-window query gains `AND method_id = ?`, and the plan now records on the page that 8h's `{sid … lab_status != "rejected"} == {RAW35_GT}` is the compensating control and may not be weakened alongside it. |
| 4 | **Broken step — the index's phase-2 exit criteria required `promote --dry-run`, which cannot run.** | 2 | Confirmed by reproduction: `promote.py:104 object_name_of` scans `RESOLVER` by object **identity** and raises `NotPromotable` for an object two keys name; a second width on `RESIDMOM` is exactly that, and no flag overrides it. The requirement is **removed** from phase 2's exit criteria and replaced by the migration-equality pair against a scratch Postgres, which is the same round trip `promote._insert` performs inside its transaction. No other phase plans to call `promote`; phases 3 and 5 state explicitly that promotion is never sought. |
| 5 | **Unmet assumption — the lab write lock was asserted five times and defined nowhere.** `lab stage`'s own `BEGIN EXCLUSIVE` covers only `write_snapshot` + `git add` and is released before the commit, so it is not the lock the plans meant. | 1, 2, 3, 4, 5 | One concrete mechanism, written out as runnable commands and pasted **identically** into the index (invariant 7) and all five plans: `flock -w 21600` on fd 9 over `/home/miftah/seer/.git/seer-lab.lock` — inside `.git/` so no `git add` can reach it. Every holder proves `git diff --quiet HEAD -- lab/lab.sqlite web/data/lab.json` on entry and may not release until it is true again. |
| 6 | **Broken-build — "the runs may overlap" cannot coexist with a byte-compared snapshot.** A `lab run` leaves the shared binary `lab/lab.sqlite` dirty for its whole duration; while it is dirty no session can commit a snapshot that matches the committed database, and another phase's `lab stage` would `git add` the half-finished run's rows into its own commit. | 1, 2, 3, 4, 5 | **The draft's invariant 7 is reversed: `lab run` is inside the lock and the four lab runs queue.** Build-green wins. Two independent measurements agree with the choice — two `lab run`s contend on one sqlite file (phase 1's own Step 5), and each run loads a whole research store at ~1 GB, so four at once is RAM pressure on a 16 GB machine. The cost is stated in the index rather than hidden: wall-clock for the set is one phase 2 plus the sum of four lab runs. |
| 7 | **Ordering / starvation — phase 1's single lock hold would have spanned Step 1 to Step 8**, including writing a 270-line method file, blocking phases 3, 4 and 5 for hours for nothing. | 1, 3, 4, 5 | "Take short holds, not one long one" is written into invariant 7, and each phase's hold boundaries are named in the index and in its own plan. Phase 1 now takes **two** holds — A around Step 1's `lab survivorship` (which journals an observation and so dirties the database), ending with its own commit and push; B from Step 5's `lab run` through Step 8's push. |
| 8 | **Contract drift — the index's phase-2 boundary allowed a `lab/lab.sqlite` write that cannot happen.** It carved out "the single `record_promotion` note" for the `promote` path. | 2 | `promote` is unusable (conflict 4), so `record_promotion` is never called. The boundary is tightened to **"`lab/lab.sqlite` — nothing at all, not one row"**, and phase 2's lock hold is for the snapshot only. |
| 9 | **Gap — `lab reevaluate` after the four runs was owned by nobody.** Phase 5 handed it to "whoever closes the plan set". | 1, 3, 4, 5 | Assigned by a rule that identifies exactly one session with no coordinator: **the last lab phase to land owns it**, determined by a runnable read-only check that all four of `M0148`, `M0149`, `M0155`, `M0156` have left `idea` immediately after its own push. Written as a full step into all four lab plans and as invariant 13 here. A phase that decides not to run its method moves the row off `idea` with `lab drop`, which keeps the check total. |
| 10 | **Contract drift — the index's Files counts and phase-2 Package were stale** against the plans the planners actually wrote (`~3/~9/~3/~3/~3`). | 1, 2, 3, 4, 5 | Recounted from each plan's own Files table: 6 / 13 / 6 / 4 / 4. Phase 2's Package gains `engine/tests` and `web`; its Owns line gains `test_promote_command.py`, `test_evidence.py` and `web/lib/sera/paper.test.ts`, which the draft's boundary did not name. |
| 11 | **Contract drift — the index's R1 evidence names a variant other than the one phase 2 admits.** The headline 20.11% / 12.11% is `M0139-N35-TBAND`; phase 2 admits `M0139-N35-EBAND`. Phase 2 states the caveat honestly in its own plan; the index did not. | 2 | The caveat is folded into the index's **Why**, together with the second one phase 2 found: `era_2009_2015_edge` reads −0.0022 at 20 names and −0.0168 at 35 on the check store, so the width case is a drawdown case and not a return case. Neither caveat changes the choice; both must travel into the admission note and migration 021. |
| — | **Checked, no conflict: phases 3 and 4 are both brakes on stock books.** A collision would make the second `lab run` refuse after the backtest was paid for. | 3, 4 | Allocator ids `M0155`/`M0149`, candidate prefixes `M0155-`/`M0149-` and all six `seen_keys` are disjoint, and share no token. The full matrix, including phases 1 and 5, is tabulated above. |
| — | **Checked, no conflict: phases 1 and 2 both concern roster books.** | 1, 2 | Phase 1 plans no roster edit; phase 2 plans no `MOM-FR-GT` edit. Phase 1's `MOM-FR-GT` widening is recorded in its **Handoffs** as a future, separately argued commit after the owner has seen the finding — work this set does **not** perform — and phase 2's Handoffs says the same from the other side. |
| — | **Checked, no conflict: "test-window looks stay at 4".** | all | No plan contains a `lab test` invocation, and no plan points any `--store` at `engine/.research-test`; every mention of that store is a prohibition. All five restate the before/after `lab status` check. |
| — | **Checked, no conflict: `docs/lab/survivorship/grid.csv`.** | all | No plan appends to it. Phases 1 and 3 assert it is byte-identical to `661870d` in their exit criteria; phases 2, 4 and 5 name it as read-only or untouched. |
| — | **Checked, no conflict: no shared params dataclass gains a field** (`seer-shared-params-cannot-gain-a-field`). | 1, 3, 4, 5 | Every new field lives in a new frozen dataclass inside the method's own file, behind a new allocator id. Phase 3 and phase 4 each state the hazard explicitly in their Interface Contracts. |
| — | **Checked, no conflict: no frozen method file is edited.** | all | `m0002`, `m0007`, `m0011`, `m0088`, `m0101`, `m0109`, `m0110`, `m0113`, `m0128`, `m0133`, `m0139`, `m0143`, `m0152` appear only as read-only imports. Every plan names the test that would catch an edit (`test_every_recorded_configuration_still_digests_to_its_recorded_digest`, `test_lab_methods.py`'s source-sha check). |

## Decisions

Behavioural forks settled at reconciliation, with the precedence rung that settled each. **Every
fork was settled and the losing side was edited out of the plan file** — an executor meeting one of
these at 3am reads the answer here instead of asking.

| Fork | Chosen | Rung |
|---|---|---|
| May phase 2 regenerate and commit `web/data/lab.json`, when the draft's phase-2 boundary says it touches none of the lab's artifacts? | **Yes, and it must.** The boundary is withdrawn; invariant 12 replaces it. | **1 — stated invariant.** Invariant 1, "the tree is green at the end of every phase", outranks a phase boundary line. The boundary was not a rule but a guess, and `test_lab_snapshot.py:1054` makes it unholdable: the test is red from the moment `roster.py` is edited until the snapshot is regenerated. |
| `lab stage` or `lab export-json` for phase 2's regeneration? | **`lab export-json`.** It writes identical bytes to the identical path and never touches the git index. | **3 — the plans' code blocks.** `_stage` `git add`s `lab/lab.sqlite` as well; this swarm shares one index and phase 2 writes no lab row, so staging the database would sweep another phase's in-flight trials into phase 2's commit. `commands/lab.py:1757-1761` names `export-json` for exactly this situation, in a comment about this swarm. |
| May the four lab runs overlap, as the draft's invariant 7 said, or do they queue? | **They queue.** `lab run` is inside the write lock. | **1 — stated invariant.** Invariant 1 (build-green) against invariant 7's prose; build-green wins. A dirty `lab/lab.sqlite` makes a correct snapshot commit impossible for every other session, and makes any `lab stage` sweep a half-finished run. |
| Is `test_paper_roster.py:724`'s `dev["eligible"] == 0` the real invariant, or is phase 2 bending a test to fit? | **A historical accident. The invariant is "an owner-override has no PASSED test-window trial", and phase 2's restatement is upheld.** | **1 — stated invariant.** Three independent proofs: `lab/store.py:216 promotion_basis` already computes `owner-override` for every status but `test-passed` and `paper`, `dev-eligible` included, so the old assertion contradicted the implementation; the governing prose ties the basis to the **test window** and never to the dev gate (`roster.py` module docstring, `LabProvenance`'s docstring, `BASES`, method-lab design §7.4 and §8 — a dated amendment); and the roster already violates the old reading in substance, since `M0007-N20-RAW` passes the dev gate under the bars in force today and sits on the roster as an override, the assertion surviving only because its frozen trial row carries a superseded 15% drawdown label. The only case the restatement stops catching is a *correct* override, i.e. a false positive. |
| Does moving `:724` erase a guard? | **It reduces the cross-database teeth on one fact — "every entry up to 017 was admitted at `rejected`" — and 8h is the compensating control.** `{sid … p.lab_status != "rejected"} == {RAW35_GT}` names the single permitted exception, so a second dev-eligible admission cannot slip in unremarked. 8h may not be weakened alongside `:724`. | **2 — phase exit criteria.** Phase 2's exit criteria require *exactly one* new admission and zero moved pins; 8h is the assertion that states that in the suite. |
| Does `test_paper_roster.py:685` get loosened? | **No — it stays a census and gets sharper.** Its own comment is an instruction to its successor: *"When that stops being true, this assertion is the place to say so."* | **6 — surrounding convention.** The test instructs its own update; following it is the convention, not a bend. |
| Is `promote` the path for R1, or the migration? | **The migration, alone.** `promote --dry-run` is not available and must not be attempted. | **3 — the plans' code blocks.** `object_name_of`'s identity scan raises for an object two `RESOLVER` keys name, reproduced against the tree with the second key injected; no flag overrides it. Note the collateral cost, recorded here so it is not rediscovered at 23:00: once `RESIDMOM` has two keys, `promote` can place **neither** width. Recovering it would mean giving the 35-name book its own allocator instance behind a new pre-registered method id — a bigger change than 021, and a future session's, not this set's. |
| Who owns `lab reevaluate` after the four runs? | **The last lab phase to land**, by a runnable self-check on the four ids' statuses. | **4 — the index's Why.** The Why names R2–R5 as one batch of four questions; the N move is the batch's shared cost, so the batch's closing chore is the batch's, and the only session that can see the batch is complete is the one that completes it. |
| Does this set widen `MOM-FR-GT` as well, now that phase 1 measures it? | **No.** Phase 1 produces the number; acting on it is a separately argued commit after the owner has seen it. | **4 — the index's Scope.** "Out of scope, and why" names it, and both plans' Handoffs agree from either side. Widening it on M0152's number would apply a measurement of the residual-momentum picking rule to a different picking rule. |
| `M0139-N35-EBAND` or `M0139-N35-TBAND` for the roster — given that phase 3 quotes TBAND's numbers and the index's headline is TBAND's? | **EBAND for the roster entry; TBAND stays the right control for phase 3's own question.** Not a contradiction to be "fixed": phase 2 needs the preset `RAW-FR-GT` runs today so the width is the only thing that moves and the comparison against `RMW-FR-GT` survives; phase 3's arms run on tband, so tband is its control. | **3 — the plans' code blocks.** The two name different rule presets for different purposes and each is right for its own. The honest caveat — that the check-store 20.11% / 12.11% is the twin's reading, with the dev-store twins 0.012 points of drawdown and 0.19 points of CAGR apart — is now stated in the index's Why as well as in phase 2 and must travel into the admission note and migration 021. |

## Open Questions

**None.** Every fork above was settled and recorded; nothing in this set has a branch that destroys
data, rewrites published history or performs an unrepeatable migration, and every requirement id
R1–R6 is owned by at least one phase. This section is empty because the set is launchable
unattended, not because anything was waved through.

## Rollback

**Per phase.** Phases 1, 3, 4 and 5 append to an append-only database: a trial row cannot be
deleted and a method's status moves forward only. "Rolling back" a lab phase means writing a
further note, never editing a row. The method file itself can be reverted by `git revert` **only
before its `lab run`** — afterwards `methods.source_sha` pins it and `test_lab_methods.py` goes red
the moment the file no longer hashes to it, so after the run the file is frozen and stays.

**Phase 2** is the one that is genuinely reversible, and the reversal is the same shape as the
change: a further migration flipping the new entry to `status='retired'` and `RAW-FR-GT` back to
`'active'`, plus the matching `paper/roster.py` edit and a re-run of the snapshot export. Neither
entry's spec digest moves, because `status`, `sort` and `paper_end` are deliberately outside the
spec, so `PINS` is untouched by the rollback as it was by the change. The `RESOLVER` key
`"RESIDMOM35"`, the `EVIDENCE` key, the `LAB_PROVENANCE` entry and the pin **stay**: keys are
stable forever and a stored spec names one, so removing `"RESIDMOM35"` would be the one genuinely
destructive act available here. What is **not** recoverable is the new entry's paper clock: once it
has had a first night it has a `paper_start`, and the runbook forbids resetting a clock by deleting
rows. So the cost of being wrong here is one restarted 18-month paper record, not a corrupted one —
and it is zero for as long as `nightly.yml`'s `PAPER_PAUSED` reads `true`.

> **Correction, 2026-10-14 (coordinator, at set close).** That last clause was already false when
> it was written, and the sentence is kept rather than tidied away because the rest of the
> paragraph is right. `nightly.yml` sets `PAPER_PAUSED: 'false'` — the owner resumed paper trading
> on 2026-10-08, and the workflow's own comment records the consequence: *"From here the clock
> runs. A full revert is no longer exact once a session has stepped — that property belonged to
> the pause and is now spent, by intent."*
>
> So the free-rollback window this paragraph assumed **does not exist for this change**. On the
> first nightly after migration 021 applies, `RAW35-FR-GT` takes a `paper_start` and begins its
> 18-month record, and `RAW-FR-GT`'s record stops where it stops. The cost of being wrong is
> therefore one restarted 18-month paper record, full stop — not "zero". Nothing else in the
> Rollback section changes: the migration is data-only, no spec digest moves, and `PINS`, the
> `RESOLVER` key and the `LAB_PROVENANCE` entry are all untouched either way.
>
> This is a correction to the plan's risk analysis, not to the decision. Widening the roster to
> thirty-five is the owner's own call and the clock starting is that call taking effect.

**The lab write lock** leaves nothing to roll back: `/home/miftah/seer/.git/seer-lab.lock` is an
empty advisory file inside `.git/`, untracked and unreachable by `git add`, and the kernel releases
the lock when the holding shell exits even on a crash. A stale *file* is harmless; a stale *hold*
is impossible.

**The whole set.** Nothing in this plan is a schema change and nothing is destructive. The
migration is additive plus two status flips; every method file is new.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f docs/plans/ROSTER_35_FOUR_METHODS_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, resumable on any machine. Every phase has
`Depends on: —`, so all five may be spawned at once; the lab write lock (invariant 7) is what
serialises them, not a dependency edge:

    /analyze-orchestrator -f docs/plans/ROSTER_35_FOUR_METHODS_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan docs/plans/ROSTER_35_FOUR_METHODS_PLAN.md
