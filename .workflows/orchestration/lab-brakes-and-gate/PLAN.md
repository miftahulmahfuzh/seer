# Plan: the brakes-off variants (§4.1) and the shared SPY 200-day gate (§4.2)

**Slug:** `lab-brakes-and-gate`
**Date:** 2026-10-12 12:42:47 +07
**Analysis:** `docs/analyzer/20261012-124247-B4K9_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/lab-brakes-and-gate`
**Branch:** `feature/lab-brakes-and-gate` (base: `origin/main` @ `d3c1ec4`)
**Phases:** 6
**Status:** planned
**Coordinator:** —

---

## Why

The user's rationale, verbatim:

> Read the whole handover first, then plan and build §4.1 and §4.2: the brakes-off variants on
> M0030 and M0053 that the exposure diagnostic found carry the only post-2009 edge in the grid,
> and the interrogation of the shared SPY 200-day gate that §2 showed is nearly all one year of
> value and a drag since 2009.
>
> The hard constraint is §3: the luck gate N is 74 under the methods policy, so these must be
> VARIANTS of the existing method files (free in N) and not new method ids. Verify that with
> store.pending_gate before you commit to a shape. Hold the usual lab rules: pre-register by
> committing the method file before lab run, lab stage for any database commit, Postgres for DB
> tests, no hard-gate override, and never touch the test window.
>
> Do not act on §5.1 (the ten Lab N strings in commands/lab.py) -- that is the owners decision,
> not yours. Surface it, do not fix it.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Build §4.1: the brakes-off variants on M0030 and M0053 — the exposure diagnostic's `-FULL` arms, turned into real pre-registered, recorded lab variants | 3, 4, 5 |
| R2 | Build §4.2: interrogate the shared SPY 200-day gate that is nearly all one year of value and a drag since 2009 | 2, 3, 4, 5 |
| R3 | Hold the hard constraint: VARIANTS of the existing method files, free in N, never new method ids — verified with `store.pending_gate` before committing to a shape | 1, 5 |
| R4 | Hold the usual lab rules: pre-register by committing the method file before `lab run`; `lab stage` for any database commit; Postgres for DB tests; no hard-gate override; never touch the test window | 1, 5 |
| R5 | Surface §5.1 (the ten `Lab N (dev trials)` strings) to the owner as a decision. Do not fix it | 6 |

**R3 gained phase 5** in reconciliation. Phase 1 *builds* the mechanism that makes a variant free
in N and proves it on a fixture; phase 5 is where the constraint is actually held against the real
committed database — its Step 2 and Step 8 read `store.gate`, `store.pending_gate` and
`npolicy.dev_method_count` before and after six real trials, and that before/after pair is R3's
only end-to-end evidence. The index's draft credited phase 1 alone, which would have left R3
unverified on anything but a tmp fixture. No step moved; the requirement id followed the work that
already existed.

## Scope

**In scope**

- A lab mechanism for **amendments**: additional pre-registered variants of a method that has
  already run, recorded under that method's own id so the gate's N does not move.
- One amendment on `M0030` and one on `M0053`, each carrying both the §4.1 brakes-off candidate(s)
  and the §4.2 gate-off candidate(s), with their own dated hypothesis and expected failure.
- A report-only `lab gate` diagnostic that prices the shared SPY 200-day gate across every
  recorded dev variant that carries it.
- Running the two amendments on the dev window, recording the trials, the journal, the verdicts,
  the staged snapshot and a write-up.
- Two documents for the owner: the dated design revision that records the amendment rule, and a
  decision memo carrying §5.1 and the amendment's own integrity trade-off.

**Out of scope, and why**

- **The ten `Lab N (dev trials)` strings in `commands/lab.py`** (§5.1). The user said plainly:
  surface, do not fix. R5 writes them up; no phase edits them, and no phase adds an eleventh
  (D11).
- **Any new method id.** `lab next-id` is not run. R3 forbids it, and `pending_gate` prices it at
  +1 N retroactively for all 130 methods.
- **The test window.** No `lab test`, no `lab promote`, no `--dir` into `docs/lab/prereg/`.
  `research.DEV_WINDOW` only; `engine/.research-test` is not opened.
- **The hard gate.** `lab walkforward` may be *read*; `hardgate` is never overridden and no
  promotion is attempted.
- **`npolicy` and the `methods` policy itself.** The gate's definition is not touched. Only what
  gets recorded under which `method_id` changes.
- **Any recorded trial, method file candidate, params dataclass or allocator that a recorded
  `config_digest` depends on.** Frozen records stay frozen.
- **Rebuilding the research store.** The dev store is used as it is (handover §6).

## Invariants

Every phase holds all of these. A phase that cannot is a phase that stops and says so.

1. **The tree builds and `pytest engine/tests` passes at the end of each phase**, with Postgres
   up (`docker start seer-pg`;
   `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres`) and
   `PYTHONPATH=<worktree>/engine/src` using the **main checkout's venv**
   (`/home/miftah/seer/engine/.venv/bin/python`). CI fails if DB tests skip.
   Baseline on `main` @ `d3c1ec4`: **4364 passed / 3 skipped** (the three skips are opt-in
   live-store tests). Re-measure rather than carrying that figure forward.
2. **N does not move.** After everything lands,
   `store.gate(conn) == Gate(n=74, policy='methods')` and
   `store.pending_gate(conn, 'M0030', k) == store.pending_gate(conn, 'M0053', k) == Gate(74)`.
   `npolicy.dev_method_count(conn)` is still 74. No phase mints a method id.
3. **Every configuration recorded before today still digests to exactly the `config_digest` the
   lab has on file.** No existing params dataclass gains, loses or renames a `compare=True`
   field; no existing allocator's `id` changes; no existing `Candidate`'s `rules`, `allocator`
   or `params` changes. `registry._canon` enumerates every compare field, so a single added
   field silently rewrites history.
4. **`trials`, `trial_moments`, `trial_funding`, `trial_provenance` stay append-only.** No row is
   edited or deleted. `methods.source_sha` is never rewritten — the trigger
   `methods_source_sha_once` stays in place and keeps meaning what it says.
5. **The commit is the pre-registration.** A method file's amendment is committed *before* the
   `lab run` that executes it, and `registry_problem` still refuses an uncommitted or dirty file.
   Hypothesis and expected failure are written before any result is seen.
6. **The test window is never named.** `dev.run_registry` is called with no `window=` keyword
   everywhere; the test store is not opened; `lab test` and `lab promote` are not run.
7. **Any commit that includes `lab/lab.sqlite` goes through `lab stage`**, which writes
   `web/data/lab.json` and git-adds both under the write lock. CI checks the two agree row for
   row. A read-only probe hashes `lab/lab.sqlite` first and restores it by explicit path
   afterwards, because a lab command migrates it on connect.
8. **The research store is the main checkout's.** `--store /home/miftah/seer/engine/.research`
   (dev, fingerprint `77c37d553508…`, prices `5451195f…`). It is **not** rebuilt, whatever a
   fingerprint comparison says.
9. **`commands/lab.py`'s ten `Lab N (dev trials)` strings are not edited by any phase**, and no
   phase adds an eleventh (reconciler, D11). Phase 1 reproduces `:1399` verbatim; phase 2's new
   `lab gate` prints the hurdle and the row count under separate labels; phase 5 quotes them in
   its transcript and never in its write-up; phase 6 writes them up and edits none. After the
   whole set lands, `grep -c 'Lab N (dev trials)' engine/src/seer_engine/commands/lab.py` still
   returns **10**. Their *line numbers* shift — phases 1 and 2 both add code above them — so
   every quotation of those numbers is labelled as being at base commit `d3c1ec4`.
10. **Measured numbers are written as measurements, not invariants** — every figure quoted in a
    docstring, plan or write-up carries the date it was measured and what it was measured on.
    This is the pattern §7 of the handover asks to carry forward.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Method amendments: pre-registered variants of a method that has already run | R3, R4 | `engine/src/seer_engine/lab` | 18 | — | HARD | `.workflows/plan/lab-brakes-and-gate/phase-1.md` | — | — |
| 2 | `lab gate`: price the shared SPY 200-day gate across the lab, report only | R2 | `engine/src/seer_engine/lab` | 4 | 1 | HARD | `.workflows/plan/lab-brakes-and-gate/phase-2.md` | — | — |
| 3 | M0030's amendment: the satellite at full size, with and without the gate | R1, R2 | `engine/src/seer_engine/lab/methods` | 2 | 1 | NORMAL | `.workflows/plan/lab-brakes-and-gate/phase-3.md` | — | — |
| 4 | M0053's amendment: the weekly brake off, and the gate off | R1, R2 | `engine/src/seer_engine/lab/methods` | 2 | 1 | HARD | `.workflows/plan/lab-brakes-and-gate/phase-4.md` | — | — |
| 5 | Pre-register, run, record, stage and write up | R1, R2, R3, R4 | `lab/`, `docs/backtests` | 7 | 2, 3, 4 | NORMAL | `.workflows/plan/lab-brakes-and-gate/phase-5.md` | — | — |
| 6 | The owner's two decisions: §5.1's N strings, and the amendment rule | R5 | `docs/plans` | 2 | 1 | NORMAL | `.workflows/plan/lab-brakes-and-gate/phase-6.md` | — | — |

Waves, by `Depends on`: **{1}** → **{2, 3, 4, 6}** → **{5}**.

Phase 2 was moved out of the first wave by the reconciler (C4). It needs no symbol phase 1 creates,
but both phases edit `engine/src/seer_engine/commands/lab.py`, and this set runs its phases
concurrently in **one shared worktree with one git index**. Two sessions editing one file that way
is the failure this set must not have, so they are serialised. The cost is one wave of wall-clock;
the benefit is that phase 2 can quote `commands/lab.py` as it will actually look when it runs.

### Phase 1 — Method amendments: pre-registered variants of a method that has already run

**Satisfies:** R3, R4
**Owns:** `lab/method.py` (`Amendment`, `Method.amendments`, `all_candidates()`, the per-amendment
cap, the docstring), `lab/store.py` (the `method_amendments` table, its append-only triggers,
`AmendmentRow` / `insert_amendment` / `amendments_of` / `latest_source_sha`, `SCHEMA_VERSION` →
`"6"` and `_v5_to_v6`), `lab/runner.py` (`AMEND_CLOSED`, `pending_amendment`, `preflight`'s
amendment path, `run_method`'s amendment record, `preflight_test`'s sha check), `lab/prereg.py`
(`check_source`, whose signature becomes `(conn, method_id, trial)`), `lab/remeasure.py` (the sha
comparison), **`lab/real_costs.py`** (`real_cost_problem` and `pick_candidate` read
`all_candidates()`, so the M0031 real-fee rule governs an amendment — R4; recorded here rather
than left undeclared, C10), **`lab/exposure.py:500` only** (`by_id` reads `all_candidates()`;
nothing else in that module, C6), **`lab/survivorship_check.py:133`** and
**`commands/promote.py:205-213`** (the same one-line migration, C6), `commands/lab.py`'s `run`
subcommand (`--amend`) and `_run`'s amendment summary, `lab/hardgate.py`'s freeze docstring, and
every test that pins the freeze — `test_lab_methods.py`, `test_lab_store.py`,
`test_lab_prereg.py`, `test_lab_runner.py`, **`test_lab_snapshot.py`** (it pins
`SCHEMA_VERSION == "5"` at `:116` and `:357` and derives its V2/V4 fixtures from `store._SCHEMA`,
so the version bump is unavoidable and no other phase touches it, C9), the four lab-state snapshot
asserts, and the new `engine/tests/test_lab_amendments.py` (14 tests).
**Does not touch:** any `lab/methods/mNNNN_*.py` file; `npolicy.py`; `store.gate` / `pending_gate`;
the ten §5.1 strings; `lab/gate_probe.py` and the `gate` subparser (phase 2);
`engine/package_readme.md` (phase 2 writes this phase's readme lines, C5); `lab/exposure.py`
**beyond the single `by_id` line at `:500`** — `ERAS`, `load_dev_store`, `ExposureAllocator`,
`reweight` and every message string are untouched, so phase 2, which imports them, is unaffected;
`lab/lab.sqlite` and `web/data/lab.json`.
**Exit criteria:** a committed, already-run method whose file gains an `Amendment` can be run
again through `lab run --amend MNNNN`; only never-run digests execute; the trials land under the
existing `method_id`; `pending_gate` returns `Gate(74)` for the batch; `methods.status` is **not**
written on the amendment path (P2) and `methods.source_sha` is unchanged; every recorded candidate
still digests to its recorded digest; **the freeze test is green on a tree carrying a committed
`Amendment` that has no `method_amendments` row** — the state phases 3 and 4 leave behind, proved
by exercising it against a real amended file before handing off (C1); no reader of "what variants
does this method have" is left on `method.candidates`; the suite is green.

### Phase 2 — `lab gate`: price the shared SPY 200-day gate across the lab, report only

**Satisfies:** R2
**Owns:** `engine/src/seer_engine/lab/gate_probe.py` (new), its `lab gate` subcommand in
`commands/lab.py` (the docstring stanza, the `gate` subparser, `_gate`, the `_HANDLERS` entry),
`engine/tests/test_lab_gate_probe.py` (new, 26 tests), and **all of `engine/package_readme.md`'s
changes for this plan set** — both the `gate_probe.py` line and phase 1's `lab run --amend` /
`method_amendments` / schema-v6 clauses on the `method.py`, `store.py` and `runner.py` module-map
lines, plus the `Last Updated` line naming both landings (C5: one phase touches the file, which is
safe now that phase 2 depends on phase 1).
**Does not touch:** `lab/exposure.py` (it is **imported** — `ERAS`, the stat and grid helpers —
never edited; phase 1's one-line change at `:500` is invisible here); any method file; the `run`
subparser or `_run`; `trials` or any other recorded table beyond `insights`; **the ten §5.1
strings, and it adds no eleventh** (C8).
**Exit criteria:** `lab gate [IDS…] | --all` re-runs every recorded dev variant that carries the
SPY-200 trend gate with the gate off, prints and CSVs the whole-window and per-era lead against
deposit-matched SPY, writes at most journal `observation` rows, and leaves
`store.dev_trial_count`, `store.test_looks` and `store.gate` unchanged — proved by reading them
before and after, and by `lab/lab.sqlite` coming back byte-identical under `--no-journal`;
`control_problems()` returns `((), 6)` and the command refuses with exit 2 if it does not; the six
variants the transform refuses are named and have **no** gate-off arm;
`grep -c 'Lab N (dev trials)' engine/src/seer_engine/commands/lab.py` still returns **10**.

### Phase 3 — M0030's amendment: the satellite at full size, with and without the gate

**Satisfies:** R1, R2
**Owns:** `engine/src/seer_engine/lab/methods/m0030_spy_core_momentum_satellite.py` (the
amendment block only — the existing three candidates, `TIMED_SPY`, `ALWAYS_SPY`, `_blend` and
`_v` are untouched) and `engine/tests/test_lab_m0030_amendment.py` (new).
**Does not touch:** the method's recorded `candidates` tuple, its `hypothesis`, its
`expected_failure`, its module docstring, `m0007_*.py`, `m0011_*.py`, `lab/` engine modules, or
`engine/tests/test_lab_methods.py` (phase 1 owns every test that pins the freeze).
**Exit criteria:** `M0030`'s `METHOD` carries one `Amendment` dated 2026-10-12, built with phase
1's exact signature `Amendment(added=, why=, hypothesis=, expected_failure=, candidates=)` (C3),
with the three candidates named under **Decisions** and `amendments=` as the call's last keyword
after `seen_keys`; the three new digests are `542c1b9e…`, `5d00ec7c…` and `b7cdc121…`, all free;
the method still validates; the three recorded candidates still digest to `ca034400…`,
`4508e558…` and `acbab0ed…`; the amendment's `hypothesis` and `expected_failure` state the
20.4% drawdown prediction **as the unfunded re-weighting it is**, with the funded caveat named
before the run (C7); the suite is green. **No `lab run` here** — phase 5 runs it.

### Phase 4 — M0053's amendment: the weekly brake off, and the gate off

**Satisfies:** R1, R2
**Owns:** `engine/src/seer_engine/lab/methods/m0053_overnight_winners_weekly_brake.py` (a **new**
params dataclass `NoBrakeOnParams`, a **new** allocator `FULLON` with `id = "M0053-NOBRAKE"` for
the no-brake arm, `NOGATE20`, and the amendment block) and `engine/tests/test_m0053_amendment.py`
(new, 6 tests).
**Does not touch:** `WeeklyOnParams`, `WeeklyOnPrepared`, `WeeklyOvernightAllocator`, `WEEKLYON`,
`TOTON20`, `TOTON30`, `PoolBy`, the recorded five candidates, `m0050_*.py`, `m0007_*.py`,
`m0030_*.py`, `lab/` engine modules, or `engine/tests/test_lab_methods.py`.
**Exit criteria:** `M0053`'s `METHOD` carries one `Amendment` dated 2026-10-12, built with phase
1's exact five-field signature including `why=` (C3), with the three candidates named under
**Decisions** and `amendments=` as the call's last keyword; the new allocator's id is unique
across the lab; the three new digests are `d8e94b62…`, `150eb251…` and `76de74aa…`, all free;
the five recorded candidates still digest to their recorded digests; `allocatorkit`'s contract
checks pass for the new allocator; **no existing params dataclass gains, loses or renames a
`compare=True` field and no existing allocator id changes** (invariant 3); the suite is green.
**No `lab run` here.**

### Phase 5 — Pre-register, run, record, stage and write up

**Satisfies:** R1, R2, R3, R4
**Owns:** the two pre-registration commits, the two `lab run --amend` executions, `lab gate`'s
run, `lab walkforward`'s read, the journal entries, the two verdicts, `lab stage`,
`lab/lab.sqlite`, `web/data/lab.json`, `docs/backtests/2026-10-12-brakes-and-gate.md`,
`docs/backtests/2026-10-12-brakes-and-gate-grid.csv` and
`docs/backtests/2026-10-12-brakes-and-gate-gate-grid.csv` (**unconditional** — phase 2 ships
`--csv`, C11).
**Does not touch:** any engine source or test (phases 1–4 own it — **hard stop rule:** a bug the
runs expose is reported, never patched from here); the test window (no `lab test`, no
`lab promote`, `engine/.research-test` never named); the hard gate; `docs/plans/` (phase 6 and the
reconciler); `.workflows/todos.md`.
**Exit criteria:** M0030 and M0053 each carry their amendment's three trials under their own
`method_id` (`n` 359–364), with their `trial_provenance`, `trial_moments`, `trial_funding` and
one `method_amendments` row each; **R3's end-to-end proof** — `store.gate(conn)` reads
`Gate(n=74, policy='methods')` and `npolicy.dev_method_count` reads 74 on **both** sides of the
six new trials, recorded in the write-up; `store.test_looks(conn) == 4` unchanged and
`git status --short docs/lab/` empty; the coverage gate was **measured** over `all_candidates()`
before the runs rather than assumed (C15); the write-up states the result against the
pre-registered hypothesis and expected failure **both ways round**, carries the M0030 funding
caveat before any table that could be misread (C7), and carries the finding that
`M0001-TV10-NOTREND` was never a clean gate control (C14); `lab stage` has run and CI's
`lab.sqlite`/`lab.json` row-for-row check passes; trial `n` is contiguous; the suite is green.

### Phase 6 — The owner's two decisions: §5.1's N strings, and the amendment rule

**Satisfies:** R5
**Owns:** `docs/plans/2026-10-12-lab-n-and-amendments-owner-decision.md` (new) and the dated
`## 9.` revision appended to `docs/plans/2026-10-04-method-lab-design.md`.
**Does not touch:** `engine/src/seer_engine/commands/lab.py` — **not one of the ten strings**; no
engine source at all; `docs/backtests/2026-10-12-brakes-and-gate.md` (phase 5's; this memo is a
**policy** document and must state no result from those runs, so the two can land in either
order).
**Exit criteria:** the memo states §5.1 exactly as the handover does — **ten** line numbers,
labelled as being at base commit `d3c1ec4`, 354 vs 74, the three options the previous session
named — and recommends nothing the owner has not asked for; it notes that the set's one new
command (`lab gate`) deliberately prints the clear form, **as evidence the owner can weigh, not as
a recommendation, and without touching the ten** (C8); it states the amendment mechanism's own
integrity trade-off and the one open policy question it raises — whether amendments should be
capped — as a question put to him, not answered; the design doc carries a dated revision
recording the new rule beside the 2026-10-04 one it qualifies, with no existing line edited;
`grep -c 'Lab N (dev trials)' engine/src/seer_engine/commands/lab.py` returns 10 on the branch,
not only at `d3c1ec4`; `git diff HEAD -- engine/` is empty. No source file changes.

## Reconciliation Log

The six phase planners ran concurrently and could not see each other. Every row below is a
conflict the reconciler found or was handed, **verified against the plan files themselves**, and
**resolved by editing them** — not merely reported. Rows marked ★ were found by the reconciler
and were not on the list it was given.

| # | Conflict | Class | Phases | Resolution |
|---|---|---|---|---|
| C1 | The replacement freeze test asserted `source_sha(path) == latest_source_sha(conn, mid)` unconditionally. M0030's and M0053's files hash to **exactly** their recorded `methods.source_sha` today, so the moment phase 3 or 4 writes its amendment block the tree is red — and the row that would fix it is written by phase 5, which cannot start until those blocks exist. **The set would have deadlocked.** | Broken-build phase | 1 (owner), 3, 4 | **Phase 1's Step 10 rewritten.** The test now tolerates a sha mismatch **iff** `runner.pending_amendment(conn, method)` resolves — the file declares an `Amendment` with no `method_amendments` row, and every amendment that *does* have a row still matches its block field for field. The digest half (`test_every_recorded_configuration_still_digests_to_its_recorded_digest`) stays unconditional and has no window. Added a 14th test, `test_a_committed_but_unrun_amendment_is_the_one_tolerated_sha_mismatch`, and an exit criterion that the branch be exercised against a real amended file. `prereg.check_source`, `remeasure.preflight` and `runner.preflight_test` keep the strict comparison **on purpose** — each is about to spend something irreversible — and no step of this set reaches them. Phases 3 and 4's "this may be red through no fault of our own" sections rewritten to say it is resolved and where. |
| C2 | Phase 5 filed as BLOCKING that `run_method`'s `status = "rejected"` would hit `methods_status_forward` and abort the whole insert, since `TRANSITIONS` has no `dev-eligible -> rejected` edge and D5 predicts exactly that input for all six candidates. | Unmet assumption (already met) | 5, 1 | **Verified: phase 1's Decision P2 already closes it.** `run_method` calls `update_method(..., status=status)` only on the `if amendment is None` branch; the amendment branch writes a `method_amendments` row and touches neither `status` nor `source_sha`, and `test_an_amendment_records_its_sha_and_leaves_methods_source_sha_alone` asserts it. Phase 5's Requires bullet 4 rewritten from a live blocking risk into a **check that P2 held** — Steps 6 and 7 read the status back and assert `dev-eligible`. The failure-table row is kept, relabelled "should be unreachable", as a verification rather than a predicted outcome. |
| C3 | The `Amendment` constructor disagreed three ways. Phase 1 (the owner) ships `Amendment(added, why, hypothesis, expected_failure, candidates)`; phase 3 guessed `date=` / `title=`; phase 4 guessed four fields with **no `why`**. | Contract drift | 1 (owner), 3, 4 | **Phase 1's shape wins** — it is the module that defines the type. Phase 3's call rewritten `date=`→`added=`, `title=`→`why=`. Phase 4's call gained a real `why=` line. Both `why` strings are the exposure diagnostic's `-FULL` arm finding on the respective book, as the task required. No `Candidate` value changed, so **no digest moved** — `config_digest` reads `rules`, `allocator.id` and `params` and never the amendment wrapper. Both phases' `amendments=` keyword moved to last position, after `seen_keys`, matching phase 1's field declaration order. |
| C4 | Phases 1 and 2 both edit `engine/src/seer_engine/commands/lab.py` and both had `depends_on: []`, so both were in wave 1 — two concurrent sessions editing one file in one shared worktree with one git index. | File collision | 1, 2 | **Edge `2 depends_on [1]` added.** Waves become **{1} → {2, 3, 4, 6} → {5}**. Phase 2's `Depends on` line, its `Requires` block, its subparser note and its "take both hunks" guidance all rewritten to say it quotes the file **as phase 1 leaves it**, with a paragraph on which of its line numbers shift and by roughly how much. Its suite baseline was also re-scoped: 4364 was measured before phase 1, so the figure that matters is **+26 and 0 new skips**, not an absolute. |
| C5 | Phase 1 handed its `lab run --amend` readme line to phase 2 — but named a file (`lab/package_readme.md`) that does not exist, and phase 2's Step 7 wrote only its own `lab gate` line. | Gap | 1, 2 | **Phase 2 owns `engine/package_readme.md` for the whole set and writes both.** Step 7 split into 7a (the `gate_probe.py` module-map line), **7b (new: clauses on the `method.py`, `store.py` and `runner.py` module-map lines for the amendment mechanism, `method_amendments` and schema v6)** and 7c (a `Last Updated` line naming both landings, phase 1 first). Safe because C4's edge now guarantees phase 1 has landed. The non-existent path is corrected in phase 1's Handoffs. |
| C6 | Three readers of `method.candidates` meaning "every variant this method has" were migrated by nobody: `lab/exposure.py:500`, `commands/promote.py:205-213`, `lab/survivorship_check.py:133`. Phase 1 flagged them as out of scope and handed them off. | Gap | 1 (now owner), 2 | **Phase 1's scope widened to include all three.** They are one-line reads, mechanically identical to the five it was already doing, and leaving them is a correctness bug with a delayed fuse — after phase 5, `lab exposure` on an amended method would report an incomplete book and `lab promote` could resolve against a stale candidate set. Added to phase 1's Interface Contract, Files table, Step 8 (with code) and Owns line; `exposure.py` removed from its MUST-NOT-TOUCH list **for that one line only**, with an explicit note that phase 2 imports `exposure.py` and is unaffected. Step 8 now ends with a `grep` that must come back to exactly two deliberate hits in `runner.py`. |
| C7 | Phase 5 found a comparability error belonging in phase 3's **pre-registration text**, which is committed before phase 5 ever runs: M0030's three recorded trials carry no `trial_funding` row and ran unfunded at 20,000,000 IDR, so the committed grid's 20.4% worst fall is an **unfunded** figure — while the amendment runs funded at 10,000,000 with 237 deposits. | Contract drift | 3, 5, index | **Phase 3's amendment text rewritten.** Its banner comment now states that every grid figure it quotes is unfunded and why; its `hypothesis` states the prediction with the funded caveat **in front of it**, says the funded run may land either side of the bar, and says M0030's numbers must never share a column with C70T/C50T/C50A; its `expected_failure` names the drawdown prediction as the **weakest** claim in the pre-registration and says a 19.6% reading is not a refutation. Phase 4 gained a note that M0053's five recorded trials **are** funded at 10,000,000 and genuinely comparable, so the caveat must **not** be copied there. Index **D5 corrected in place** (see Decisions). |
| C8 | Phase 2's `_gate` handler printed an **eleventh** copy of the exact `Lab N (dev trials)` wording §5.1 documents as misleading, while phase 6's memo (correctly) says there are ten. | Duplicate work / contract drift | 2, 6 | **Phase 2's new command must not add an eleventh.** Invariant 9 forbids editing the ten; it does not oblige a brand-new command to reproduce a known-wrong label in front of the owner while the memo asking him about it is still unanswered. `_gate`'s closing print now gives two numbers under two labels — `Luck hurdle N: <store.gate(conn).n> (policy ...)` and `Dev trial rows: <before> before, <after> after`. Phase 2's CLI test now asserts `"Lab N (dev trials)" not in out`. Phase 6's memo keeps **ten**, and gained a short section presenting the one new command as **evidence the owner can weigh, not a recommendation**. |
| C9 | `engine/tests/test_lab_snapshot.py` was in no phase's stated Owns line, but phase 1 must edit it — it pins `SCHEMA_VERSION == "5"` at `:116` and `:357` and derives its V2/V4 fixtures from `store._SCHEMA`, and phase 1 moves the version to `"6"`. | Gap | 1 | **Verified no other phase touches it** (`grep -l 'SCHEMA_VERSION\|_SCHEMA' engine/tests/` returns that file alone) and **recorded explicitly in phase 1's Owns line**, here and in its own plan. It was already in phase 1's Files table with the right line numbers; only the ownership declaration was missing. |
| C10 | `engine/src/seer_engine/lab/real_costs.py` was in neither phase 1's Owns nor its Does-not-touch list, yet phase 1 changes two lines there so the M0031 real-fee rule governs amendment candidates — which R4 requires. | Gap | 1 | **Recorded in phase 1's Owns line**, with the reason (R4) attached. The change itself was already correct and already in phase 1's Files table and Step 8; it was simply undeclared. |
| C11 | Phase 5 made its second grid CSV **conditional** on `lab gate --csv` existing, and quoted a flag surface it had not seen. | Unmet assumption (already met) | 5, 2 | **Verified `--csv` against phase 2's Step 3 subparser and its `_gate` handler's `gp.write_csv(...)` call, and made it unconditional.** Phase 5's Creates bullet, Files table, Step 9 branches and Step 13 `git add` all drop the conditional; Step 13 now expects exactly three paths. Phase 5's Requires now quotes phase 2's actual surface: `lab [--db PATH] gate [IDS...] [--all] [--only IDS] [--store DIR] [--csv PATH] [--gated-only] [--no-journal] [--dry-run]`. Step 9 still reads `--help` first — as a cheap check that what landed matches what was planned — but no longer branches on it, and now says explicitly not to pass `--no-journal`, `--gated-only` or `--all`. |
| C12 | Phase 1 changes `prereg.check_source(method_id, row, trial)` to `(conn, method_id, trial)`. | Ordering / contract | 1 | **Verified no other phase's plan calls it**, with the old signature or the new (`grep` across all six plan files: zero hits outside phase 1). The one production caller, `prereg.promote_method` at `prereg.py:667`, is inside phase 1's own scope and its plan already rewrites it. No edit needed; recorded so the check is not repeated. |
| C13 | `exposure.load_dev_store`'s refusal text hardcodes "lab exposure" and will mislead a `lab gate` caller. C6 gave phase 1 a line in `exposure.py`, so an owner was available. | Gap | 2, 1 | **Recorded as a deliberate non-fix, with its reason** (see Decisions D12). Fixing it means giving `load_dev_store` a command-name parameter — a signature change on a function phase 2 only imports and three other call sites pass through — while the refusal's exit code, reason and store path are all already correct and only the command name in the sentence is wrong. Noted in phase 1's and phase 2's Handoffs and in the index's Decisions, so it is owned-as-declined rather than unowned and unmentioned. |
| C14 | Phase 2 measured a real finding with nowhere to land: `M0001-TV10-NOTREND` is **not** a clean gate control — `M0001-TV10` runs its own-vol window at 63 sessions and the "no trend filter" sibling at 126, so the recorded pair moves two things at once. | Gap | 2, 5 | **Phase 5's write-up skeleton gained a slot for it**, `### One of the lab's "controls" was never a control`, inside *The market switch, priced across the roster*, written in the owner's language with the instruction to source it from `gate_probe.IMPURE_CONTROLS`'s own dated comment rather than from a plan file. A second slot, `### What the gate probe could not price`, carries the 225 / 69 / 6 / 54 classification so the refusals are visible rather than silently absent. Phase 2's Handoff bullet now points at that slot instead of saying "phase 5's or phase 6's". |
| C15 | Phase 1 widened `preflight_data`'s fundamentals coverage gate to run over `all_candidates()`. Phase 5 *asserted* M0030's allocators are price-only rather than measuring it, and `--allow-coverage` is an acknowledgement, not a silencer. | Unmet assumption | 5, 1 | **Phase 5's Step 6 gained an explicit read-only check**, run before the first `lab run --amend`: `runner.market_aware_candidates(m, "fundamentals")` and `(m, "series")` over both methods, expecting `(none)` on all four lines. Non-empty means the gate will fire against **today's** store fingerprint rather than the one the recorded trials ran on, and the step now says to stop and report rather than reach for `--allow-coverage`. |
| C16 ★ | Phase 5 contradicted itself on what the §5.1 string will print: its *Leaves alone* section said "**360** and then **366**", its Steps 6 and 7 said 357 and 360. The baseline (354 dev rows, +3 per run) makes 357 / 360 correct. | Contract drift (internal) | 5 | **Corrected to 357 and 360 in place**, with "(354 dev trial rows today, plus three per run)" and "not the gate's N (74)" spelled out so the next reader can check the arithmetic rather than trust it. |
| C17 ★ | Phase 2's rollback instructs `git checkout -- engine/src/seer_engine/commands/lab.py engine/package_readme.md`. After C4 and C5, **both files carry phase 1's work too**, so a `checkout` from the wrong ref would silently revert phase 1 along with phase 2. | Ordering violation | 2, 1 | **Phase 2's Rollback gained the warning and the correct procedure**: `git checkout --` is right only while phase 2's work is uncommitted; once committed, `git revert` phase 2's commit instead. |
| C18 ★ | Phase 3 wrote `amendments=` **between** `candidates` and `seen_keys`; phase 4 wrote it **after** `seen_keys`. Phase 1 declares the field last, after `seen_keys`. Both run (they are keyword arguments), but the two method files would have disagreed with each other and with the dataclass. | Duplicate work / style drift | 1, 3, 4 | **Phase 3 moved to match**, with a one-line note on why declaration order is the convention every other method file follows. |
| C19 ★ | R3 was credited to phase 1 alone. Phase 1 proves the N property on a tmp fixture; the only end-to-end evidence against the real committed database is phase 5's before/after reading of `store.gate`, `store.pending_gate` and `npolicy.dev_method_count` around six real trials. | Unowned requirement (partial) | 1, 5 | **R3 now maps to phases 1 and 5** in the Requirements table and in phase 5's `Satisfies` line and exit criteria. No step moved — the requirement id followed work phase 5 was already doing but was not being credited for, which is what `create-task` needs to shape the board correctly. |

**Not conflicts, checked and cleared:**

- Phase 2's `gate_off(M0030-C50T)` and phase 3's hand-written `M0030-C50A-NOGATE` params converge
  on the same value — measured independently by both planners, agreeing by construction. Phase 3
  re-derived its own digest (`b7cdc121…`) rather than taking phase 2's word, which is right.
- Both phase 3 and phase 4 **import** `N20_NOTREND` from `m0007_residual_momentum.py:346`; it
  already exists and neither phase adds it. No file collision.
- Phase 1's Step 9 print reads a local `status` in `_run`; verified it is defined at
  `commands/lab.py:1396`, immediately before the lines phase 1 replaces.
- The ten §5.1 strings: verified untouched by every phase. Phase 1 reproduces `:1399` verbatim and
  its own plan says so; phase 2 now adds no eleventh (C8); phase 6 edits none.

## Decisions

These were settled before the planners ran and are **binding on every phase**. Each names the
rung of the precedence ladder that settled it — stated invariant → phase exit criteria → the
plan's code blocks → the index's Why and Requirements table → the user's raw input → surrounding
convention.

| # | Fork | Chosen | Rung |
|---|---|---|---|
| D1 | A new variation method id (what the lab does today) vs. a variant of the existing method | **A variant of the existing method.** `store.pending_gate(conn, 'M0030', k)` → `Gate(74)`; a new id → `Gate(75)`, retroactively for all 130 methods. Measured in this session on a copy of the committed database | 5: the user's raw input — "these must be VARIANTS of the existing method files (free in N) and not new method ids" |
| D2 | Relax the freeze vs. build a mechanism that keeps an equivalent property | **A mechanism.** `methods.source_sha` is never rewritten and `methods_source_sha_once` stays; each amendment appends a row to a new append-only `method_amendments` table carrying its own `source_sha`, date and git sha. The freeze test becomes two checks, both stronger together than the one it replaces: the file hashes to the **latest** recorded sha, **and** every recorded candidate still digests to the `config_digest` the lab has on file | 1: invariants 3 and 4 |
| D3 | `MAX_VARIANTS = 6` per method lifetime vs. per run | **Per run.** `candidates` keeps its own 1..6; each `Amendment` carries its own 1..6. M0053 already holds 5 recorded candidates, so a per-lifetime cap would silence §4.2 on that book | 6: the owner's own wording in design §2 — "scope = one idea with 1–6 fixed variants **per run**" |
| D4 | Which candidates | **Pinned below.** Three per method, one amendment per method, both §4.1 and §4.2 in the same pre-registration — splitting them would be two runs of the same method, which is more fishing, not less | 4: the Requirements table (R1 and R2 are one measurement per book) |
| D5 | Add an intermediate brake setting so something might clear the 20% drawdown bar | **No.** The committed grid puts every `-FULL` arm at 20.4% (M0030) and 22.4–22.8% (M0053) against a 20% bar, so the brakes-off candidates are **predicted ineligible**. That prediction is written into each amendment's `expected_failure` before the run. Searching for a passing brake setting after seeing results is exactly what the design forbids. **— corrected 2026-10-12 by the reconciler (C7): M0030's 20.4% is an UNFUNDED figure and the prediction must be stated as such.** `lab exposure` re-runs each trial at its own recorded capital and funding; M0030's three recorded trials (126, 127, 128) carry no `trial_funding` row and ran lump-sum at 20,000,000 IDR, so the `-FULL` arm's 20.4% is a re-weighting of an unfunded book. The amendment runs **funded** at 10,000,000 IDR plus 237 deposits of 5,000,000, and the funded run may land **either side** of the 20% bar — a 0.4-point margin is well inside what that change alone can move. The decision not to add an intermediate setting is unaffected; the *prediction* is weaker than the draft stated, and phase 3's pre-registration text now says so before the run rather than after it. **M0053's 22.4–22.8% needs no such caveat:** its five recorded trials ARE funded at 10,000,000 on the same schedule and the same real fees, so its figures are like-for-like | 6: design §4 — "never tune after seeing a result within a method"; the correction at 1: invariant 10 — a measured number carries what it was measured on, and "unfunded 20M lump sum" is part of what 20.4% was measured on |
| D6 | §4.2 as gate-off candidates on two books vs. as a lab-wide diagnostic | **Both.** Two candidates cannot measure "a shared component across the roster … changing it moves every book at once", and a report-only diagnostic cannot be promoted. Phase 2 prices the gate everywhere for free; phases 3–4 make it a recorded candidate on the two books that have a post-2009 edge | 5: the handover §4.2 text the user quoted back |
| D7 | M0030's amendment at Gotrade's real fees vs. its recorded flat cost | **Flat (`MONTHLY_HOLD_FRAC`).** `real_costs.requires_real_cost` is keyed on the method id and exempts ≤ M0030, so `preflight` will not refuse it, and the new candidates stay comparable with M0030's three recorded ones. M0053's amendment keeps `MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE`, already real | 6: `real_costs.py:54-69`, the M0031 rule as written |
| D8 | Invent a lifetime cap on amendments as an anti-fishing guard vs. rely on the shipped policy | **Rely on the shipped policy, and surface the gap.** The `methods` policy already prices a family of variants of one idea at zero and guards it with `max(distinct_methods, ceil(participation_ratio))`. Measured today that floor is `ceil(2.19) = 3` against 74 methods, so **it does not bind** — amendments are free and nothing charges for them. Phase 6 states this plainly for the owner rather than inventing a number here | 6: `npolicy.py`'s own docstring and the measured ratio |

### Settled by the reconciler, 2026-10-12

These four were forks the concurrent planners left open or answered differently. Each was decided
on the highest rung of the ladder that speaks, the losing side was **edited out of the plan
files**, and the rung is named here so no phase session re-litigates it at 3am.

| # | Fork | Chosen | Rung |
|---|---|---|---|
| D9 | Phases 1 and 2 both in wave 1, both editing `commands/lab.py`, vs. serialising them | **Serialise: `2 depends_on [1]`.** Waves become {1} → {2, 3, 4, 6} → {5}. Phase 2 needs no symbol phase 1 creates, so the edge buys nothing semantically — it buys the one thing that matters here, which is that two concurrent sessions never hold one file. The alternative considered and rejected was keeping them parallel and trusting the hunks not to overlap (~230 and ~2100 lines apart): true of the text, irrelevant to a shared git index, and it would also have left phase 2 quoting a `_run` and a `run` subparser that no longer exist by the time it runs. Cost: one wave of wall-clock. Benefit: phase 2 quotes post-change code (C4) | 1: a stated invariant — invariant 1, "the tree builds and `pytest engine/tests` passes **at the end of each phase**", which a mid-edit shared file cannot guarantee; reinforced by MEMORY's *Seer swarms share one worktree — and one index* |
| D10 | Leave `exposure.py:500`, `promote.py:205-213` and `survivorship_check.py:133` on `method.candidates` as flagged follow-ups vs. widen phase 1's scope to finish the migration | **Widen phase 1's scope.** All three are one-line reads of "every variant this method has", mechanically identical to the five phase 1 was already migrating. Left behind, they become wrong the moment phase 5 records an amendment: `lab exposure` would report an incomplete book with no sign that it had, `lab survivorship` would skip the amendment's variants, and `lab promote` would resolve against a stale candidate set. A deliberately half-finished migration is a worse artefact than either a whole one or none. `exposure.py` is opened for that **one line only**, so phase 2 — which imports the module and edits none of it — is unaffected (C6) | 2: the phases' exit criteria — phase 1's own criterion is that the amendment mechanism *works*, and a reader that silently drops amendment candidates is that criterion failing quietly rather than loudly |
| D11 | Phase 2's new `lab gate` prints an eleventh `Lab N (dev trials)` string "so the inconsistency is easier to find" vs. prints the clear form | **Prints the clear form, and adds no eleventh.** Invariant 9 forbids **editing** the ten; it says nothing about writing another one, and nothing obliges a brand-new command to reproduce a label the lab already knows is wrong while the memo asking the owner about it is still unanswered. `_gate` now prints `Luck hurdle N: <gate.n> (policy ...)` beside `Dev trial rows: <before> before, <after> after`. The grep count stays at ten, which is what phase 6's memo and its own exit check assert. Phase 6 presents the one new command as **evidence the owner can weigh, not a recommendation** — he can see what option 1 reads like on a surface nothing depends on, and the ten are exactly as they were (C8) | 4: the index's Why and Requirements table — R5 is "surface it, do not fix it", and an eleventh misleading line is neither surfacing nor fixing; it is quietly making the thing being surfaced one unit worse |
| D12 | Fix `exposure.load_dev_store`'s "lab exposure" refusal text for `lab gate` callers, give it to phase 1 (which now has a line in that file), or decline it on the record | **Decline it, on the record.** Fixing the message means giving `load_dev_store` a command-name parameter — a signature change on a function phase 2 only imports and that three other call sites pass through — for a cosmetic gain. The refusal's exit code, its reason and the store path it names are all correct; only the command name in the sentence is wrong, and `lab gate`'s own `--store` help already says which store it wants. Phase 1's single line in `exposure.py` is an unrelated comprehension and widening it further would reopen the file-collision question D9 just closed. Recorded in both phases' Handoffs so it is **owned-as-declined**, not unowned and unmentioned; the proper fix belongs with the `arm_of` duplication phase 2 also found, in a later landing that owns `exposure.py` outright (C13) | 6: the surrounding code's convention — the lab's other report-only diagnostics each name themselves in their own refusals and none of them parameterises a shared loader; nothing above this rung speaks to a message string |

### D4 in full — the pre-registered candidate set

Every digest below was computed in this session against the committed `lab/lab.sqlite` and is
**free**: no recorded trial claims it. A planner that changes a parameter must re-check its
digest before writing the file.

**`M0030` amendment, dated 2026-10-12 — "the parked market money is the drag"**

| candidate | rules | allocator | params | what it prices | digest |
|---|---|---|---|---|---|
| `M0030-SAT100` | `MONTHLY_HOLD_FRAC` | `RESIDMOM` (imported from `m0007`) | `RAW20` (imported from `m0011`) | §4.1 — the diagnostic's `-FULL` arm made real: the residual-momentum satellite alone, filling the book. Grid: +7.5/yr whole window, **+2.7 for 2009–2015**, 20.4% worst fall | `542c1b9e439a…` free |
| `M0030-SAT100-NOGATE` | `MONTHLY_HOLD_FRAC` | `RESIDMOM` | `ResidParams(N20_NOTREND, scaled=False)` | §4.2 — the same book with the shared SPY 200-day gate removed | `5d00ec7cafc0…` free |
| `M0030-C50A-NOGATE` | `MONTHLY_HOLD_FRAC` | `BLEND` | `BlendParams((BlendPart(TIMING, ALWAYS_SPY, 0.5), BlendPart(RESIDMOM, ResidParams(N20_NOTREND, scaled=False), 0.5)))` | §4.2 — the recorded book with the gate off on **both** legs, against the recorded `C50A` (always-on core, gated satellite) and `C50T` | re-check before writing |

**`M0053` amendment, dated 2026-10-12 — "the brake sells the jumpiness that pays"**

| candidate | rules | allocator | params | what it prices | digest |
|---|---|---|---|---|---|
| `M0053-TOTON20-NOBRAKE` | `MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE` | the **new** no-brake allocator | the total-momentum pool, `TOTON20`'s selection | §4.1 — the grid's strongest post-2009 arm: +7.7/yr whole window, **+0.8 for 2009–2015**, 22.8% worst fall | re-check before writing |
| `M0053-RESON20-NOBRAKE` | same | the **new** no-brake allocator | the residual pool, `RESON20`'s selection | §4.1 — the headline version's `-FULL` arm: +7.2/yr whole window, **+0.5 for 2009–2015**, 22.4% worst fall | re-check before writing |
| `M0053-RESON20-TV16-NOGATE` | same | `WEEKLYON` (unchanged) | `WeeklyOnParams(OnParams(N20_NOTREND, rank="total-overnight", pool=40), Decimal("0.16"), 21, pool_by="residual")` | §4.2 — the recorded headline version with the gate removed and everything else held fixed | `76de74aab178…` free |

**The no-brake arm must not be expressed by widening `target_vol`.** `WeeklyOnParams` requires a
positive `Decimal` and a sentinel like `99` is unreadable a year from now. It must not be
expressed by adding a field to `WeeklyOnParams` either — `registry._canon` enumerates every
`compare=True` field, so that would rewrite the `config_digest` of all five recorded M0053
candidates (invariant 3). It therefore needs a **new** frozen params dataclass and a **new**
allocator object with its own unique `id`, both living in `m0053_*.py` beside the untouched
originals.

## Open Questions

**None.** Every fork the six concurrent planners left was settled — D9–D12 above — and every
requirement id maps to at least one phase. This section is empty because the reconciliation
finished, not because anything was swept into it.

Three candidates were considered for this section and **rejected**, each with its reason, so a
later reader does not re-open them:

- **Whether amendments should be capped over a method's lifetime.** This is a real, live policy
  gap: the `methods` N policy charges nothing for an amendment, and its participation-ratio floor
  (`ceil(2.19) = 3` against 74 methods, measured 2026-10-12) does not bind. But Decision D8
  already settled what *this set* does about it — rely on the shipped policy and surface the gap —
  and phase 6 puts the question to the owner as a written document. It is **surfaced, reversible
  and owned**, so it is not an open question for this set. Parking it here would refuse the set's
  unattended launch over something a phase is already delivering.
- **Whether `lab gate` should print the clear form.** Settled as D11, on R5's own wording. Nothing
  about it is irreversible: it is one print statement in a command that does not exist yet.
- **`exposure.load_dev_store`'s refusal text.** Settled as D12, declined on the record. A message
  string, reversible in one line by whoever next owns that file.

**The bar this section holds to:** only a fork where **every** branch is irreversible — destroying
data, rewriting published history, an unrepeatable look at the test window — or a requirement id
no phase serves. This set has neither. Its three genuinely one-way acts are all **forbidden** by
the user's own instruction and by the phase plans: no method id is minted, the test window is
never opened (no `lab test`, no `lab promote`), and the hard gate is never overridden. The only
irreversible thing any phase does is append rows to an append-only database, which is the point.

## Rollback

Per phase: each phase is one or more commits on `feature/lab-brakes-and-gate`; `git revert` the
phase's commits. Phases 3, 4 and 6 are text-only and revert cleanly.

**Phases 1 and 2 share two files** — `engine/src/seer_engine/commands/lab.py` and
`engine/package_readme.md` — and phase 2 lands second (D9). Revert them newest-first, and use
`git revert` rather than `git checkout -- <path>`: a checkout from an older ref would take phase
1's work out along with phase 2's. Reverting phase 1 while phase 2 stands leaves `lab gate`
importing nothing it needs (it imports no phase-1 symbol) but leaves `engine/package_readme.md`
describing a mechanism that is gone; fix the readme in the same revert.

Phase 5 is the only phase that writes `lab/lab.sqlite`, and the lab is append-only: a revert of
its commit restores the previous database file wholesale (the committed blob is the record), and
`lab stage` must be re-run so `web/data/lab.json` agrees row for row again. Check that trial `n`
is contiguous afterwards.

As a whole: delete the branch and the worktree. Nothing outside the branch is written —
`engine/.research` is read-only to every phase, and no phase touches `main`.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f docs/plans/LAB_BRAKES_AND_GATE_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f docs/plans/LAB_BRAKES_AND_GATE_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan docs/plans/LAB_BRAKES_AND_GATE_PLAN.md
