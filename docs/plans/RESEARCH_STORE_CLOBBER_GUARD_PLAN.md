# Plan: Make the research-store clobber guard checkout-independent

**Slug:** research-store-clobber-guard
**Date:** 2026-10-06 14:30:38 +0700
**Analysis:** `20261006-143038-C4R9_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/research-store-clobber-guard`
**Branch:** `feature/research-store-clobber-guard` (base: `origin/main` @ `542ef5d`)
**Phases:** 1
**Status:** complete — the single phase is implemented, verified (2480 passed, 360 skipped, 0 failed) and committed on `feature/research-store-clobber-guard`. Landing was not attempted by the phase session: the calling session reserved the swarm-ledger check and the merge decision for itself.
**Coordinator:** —

---

## Why

The handover's request, verbatim:

```
research_store's clobber guard compares the --store path against the running checkout's own
research.STORE_DIR, so it does not refuse a dev store belonging to a different checkout or
worktree. Close that gap without weakening the guard that already works.
```

Its statement of the stake, verbatim:

```
The dev store is the measurement baseline for every recorded trial. ... The realistic damage is
destroying a 2.49M-row store that costs ~30 minutes plus a yfinance crawl to rebuild, and
breaking the sync-research-store skill's content-addressed identity until it is rebuilt.
```

And its own framing of what it is not:

```
So this is not a silent-wrong-numbers bug.
```

`research.load_store` still refuses a store whose declared window is not the one requested, in
both directions, before any data file is read. That protection is unaffected by this defect and
must not be duplicated by the fix.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Close the gap: a `--test-window` build must refuse a dev store belonging to **any** checkout or worktree, not only the running one — and symmetrically for a dev build aimed at another checkout's test store. | 1 |
| R2 | Do it **without weakening the guard that already works**: the existing same-checkout refusals keep firing with exit code 2 and their current messages; the sibling paths (`--verify`, `--coverage`, `--refresh-fundamentals`, `lab test --store`) are either fixed the same way or shown — with a regression test — to be already covered. | 1 |

> **R1 and R2 are deliberately served by one phase.** Both land in
> `engine/src/seer_engine/commands/research_store.py` and `engine/tests/test_research_test_store.py`,
> and R2's share is ~40 lines of regression test over code R1 does not change. Splitting them
> would put two phases on the same two files and force the later one to quote the earlier one's
> output, for no reviewable gain. The coupling is real and is stated rather than hidden.

## Scope

**In scope**
- `engine/src/seer_engine/commands/research_store.py` — a content-based window check on the build
  path, additive to the two existing name checks; plus the module docstring's two-stores paragraph.
- `engine/tests/test_research_test_store.py` — refusal tests for the cross-checkout case in both
  directions, fall-through tests for the four "cannot tell" shapes, and R2's sibling-path
  regression tests.
- `engine/package_readme.md:2372` — the one sentence describing the guard.

**Out of scope, and why**
- `engine/src/seer_engine/research.py` — `declared_window` is already exactly the right call and
  is already used this way by `_store_window` and by `lab test`. No new helper. Touching
  `research.py` risks the dev store's manifest shape, which an invariant below forbids.
- `engine/src/seer_engine/config.py` — `REPO_ROOT`'s module-relative derivation is the *cause* of
  the checkout-locality but is not itself a defect: a default path has to come from somewhere, and
  `lab.py`/`backtest_dev.py` depend on it. The fix stops *using* it as the definition of "a dev
  store"; it does not change it.
- `engine/src/seer_engine/commands/lab.py`, `lab/runner.py`, `commands/backtest_dev.py` — measured
  as already content-guarded (analysis, Q3 table). R2 pins this with a test rather than an edit.
- `engine/tests/test_research_store.py` and `engine/tests/test_fundamentals_coverage.py` — the
  handover forbids editing them and the fix does not require it.
- Both skills (`sync-research-store`, `explore-and-experiment-new-method`) — `sync_store.py`
  resolves its own path and never passes `--store`; Sera's cross-checkout `SEER_RESEARCH_STORE`
  reaches `lab run`, which this plan does not touch.
- **No blanket refusal of out-of-checkout `--store`.** See Decisions, fork 2.

## Invariants

Every one of these is a measured baseline from the analysis, re-checkable by command.

1. **`MANIFEST_KEYS` stays at 9 and a dev build writes no window key.** `engine/.research` must
   keep loading at fingerprint `399d0d254c7a90b8cdb49f7ce598269087d38730f795cae90453eeb580b07cf8`
   with 2,490,793 bar rows and 539 symbols served.
   `engine/tests/test_research_store.py:236` and `:622` assert `set(manifest) == research.MANIFEST_KEYS`
   and **must pass unedited**.
2. **`DEV_END` keeps the value `2015-10-16`** in `backtest/dev.py:57` and `research.py:64`, and
   `coverage.WINDOW_END == dev.DEV_END == research.DEV_END`
   (`engine/tests/test_fundamentals_coverage.py:107`) holds. **That test must not be edited.**
3. **The existing same-checkout refusals keep working in both directions** — `research_store.py:219`
   and `:227` — with exit code 2 and messages naming the same directories they name today.
   Specifically, `engine/tests/test_research_test_store.py:449-452` **must pass unedited, in a
   worktree where `research.STORE_DIR` does not exist.** This is the invariant that forces the
   content check to be additive rather than a replacement (Decisions, fork 1).
4. **No recorded trial changes and no test-window look is spent.** `lab/lab.sqlite` reads 85 `dev`
   trials and **0** `test` trials; both unchanged when the work lands. Nothing in this phase runs
   `lab run`, `lab test`, or a real `research_store` build.
5. **`engine/.research` and `engine/.research-test` stay gitignored** (`.gitignore:20-29`) and
   neither is created, moved, or written by this work. `engine/.research-test` must still be absent
   when the phase ends.
6. **No Neon, no `DATABASE_URL`.** `research_store.py` and `research.py` may name neither
   `seer_engine.db` nor `psycopg`; `test_research_store.py::test_no_neon_and_no_database_url_needed`
   AST-scans both and must stay green.
7. **`pytest -q` green in `engine/`.** Baseline on `main` @ `542ef5d`, measured this session:
   **2469 passed, 360 skipped** in 161s without `PG_TEST_URL`; the skips are all PG-gated and
   pre-existing. The phase must end at **2480 passed, 360 skipped, 0 failed**.
8. **The tree builds and tests pass at the end of the phase.** (Trivially satisfied at N=1, stated
   so the exit criterion is explicit.)

### How to run anything in this worktree

A worktree has **no venv and no research store**. Use the main checkout's interpreter and put the
engine sources on the path explicitly:

```bash
cd /home/miftah/.worktrees/seer/research-store-clobber-guard
PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python -m pytest engine/tests -q
```

Running `pytest` from `engine/` with the main venv also works. Do **not** create a venv here and
do **not** copy a research store in — invariant 5, and the absent store is what invariant 3 tests.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 ✅ | Content-based clobber guard on the build path | R1, R2 | `seer_engine.commands` | 3 | — | NORMAL | `.workflows/plan/research-store-clobber-guard/phase-1.md` | P1-ENG-G4TQ | — |

### Phase 1 — Content-based clobber guard on the build path

**Satisfies:** R1, R2

**Owns:**
- `engine/src/seer_engine/commands/research_store.py`: a helper that answers "which window does
  the store at this path declare, if it can be told?" from `research.declared_window`, and its
  use in `run()` on the build path only — **after** the two existing `_same_dir` guards, which
  are left exactly as they are. Refuse with exit 2 when the target holds a store declaring the
  other window. Fall through (do not refuse) when the window cannot be determined. Plus the
  module docstring's two-stores paragraph (`:28-31`).
- `engine/tests/test_research_test_store.py`: new tests for R1 (cross-checkout refusal both
  directions, built under `tmp_path` so no real store is involved), for the four fall-through
  shapes (missing directory, empty directory, unparseable `manifest.json`, a same-window store
  being legitimately rebuilt), and for R2 (the sibling paths refuse a cross-checkout
  wrong-window store already — `--verify`, `--refresh-fundamentals`, `--coverage`, and
  `lab test --store`).
- `engine/package_readme.md:2372`: the sentence describing the guard.

**Does not touch:**
`engine/src/seer_engine/research.py` · `engine/src/seer_engine/config.py` ·
`engine/src/seer_engine/commands/lab.py` · `engine/src/seer_engine/lab/runner.py` ·
`engine/src/seer_engine/commands/backtest_dev.py` · `engine/tests/test_research_store.py` ·
`engine/tests/test_fundamentals_coverage.py` · `.gitignore` · either skill ·
the real `engine/.research` or `engine/.research-test` on disk.

**Exit criteria:**
1. `research_store --test-window --store <dir holding a dev-window store>` exits 2 and writes
   nothing, for a directory **outside** the running checkout (test uses `tmp_path`, which is).
2. `research_store --store <dir holding a test-window store>` exits 2 the same way.
3. A build into a path that does not exist yet still proceeds; so does a rebuild over a store of
   the same window.
4. `engine/tests/test_research_test_store.py:449-452` passes **unedited**, in this worktree,
   where `research.STORE_DIR` does not exist.
5. R2's sibling-path regression tests pass against unchanged sibling code.
6. `pytest -q` in `engine/` is green: **2480 passed, 360 skipped, 0 failed** (baseline 2469/360
   plus the 11 tests phase 1 adds).
7. `engine/.research/manifest.json` on the main checkout is byte-identical and
   `engine/.research-test` is still absent; `lab/lab.sqlite` still reads 85 dev / 0 test trials.

## Reconciliation Log

single phase — nothing to reconcile.

Two findings the phase planner measured against the unchanged worktree, recorded here because
they are facts about the defect rather than choices:

- **The defect reproduces in both directions, confirmed by running it.**
  `research_store --test-window --store <dev store under tmp_path>` completes the build and
  replaces the manifest; `research_store --store <test store under tmp_path>` strips `window_end`
  out of a test store. The handover demonstrated the guard not firing; this demonstrates the
  clobber that follows. Both are now R1 tests.
- **`patched_build`'s FX fake asserts its date range.** A CLI *dev* build left at the helper's
  default `end=TEST_END` dies inside the FX fetch and returns 1 having written nothing, so a
  "same-window rebuild still proceeds" test written that way passes vacuously. Every dev-build
  test in phase 1 passes `end=research.DEV_END`, and the phase plan says why so `/implement` does
  not reintroduce it.

## Decisions

The handover posed three forks explicitly "for `/analyze` to decide". All three are decided here
and the losing side is gone from the plan, not merely outranked. None is irreversible; each costs
one commit to overturn.

| Fork | Chosen | Rung |
|---|---|---|
| **1. What identifies a dev store** — content (`manifest.json`) vs name (`_same_dir`) | **Both, in sequence: the name check stays as the first gate, the content check is added as a second, and "cannot tell" falls through rather than refusing.** A content-*only* guard is undefined for a directory with no manifest — and that is not hypothetical: `research.STORE_DIR` does not exist in any worktree (the store is gitignored), while `test_research_test_store.py:451` asserts a refusal at exactly that path. Measured: that test passes in the worktree cut for this plan *only because* `_same_dir` is pure path comparison. Replacing the name check turns it red in the very environment `/implement` runs in. | **1: stated invariant** — invariant 3 ("the existing same-checkout refusals keep working", from the handover's own constraint list) is decided by measurement, not preference. |
| **2. Refuse `--store` outside the current checkout outright?** | **No — content check only, no blanket refusal.** The handover said to check before assuming, and the check finds a live consumer: `.claude/skills/explore-and-experiment-new-method/SKILL.md:31` tells Sera's child sessions — each in its own worktree — to `export SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research`, a cross-checkout store path by absolute reference, in daily use. `sync-research-store` is unaffected either way: `sync_store.py:54-67` resolves the main checkout itself with `git rev-parse --git-common-dir` and never passes `--store`. A blanket refusal would also weaken the tool in a second direction — refusing `--verify` against a sound store in another checkout, which destroys nothing. | **5: the user's raw input (Step 0)** — "Close that gap **without weakening the guard that already works**", plus the handover's own instruction to "check whether anything actually relies on it before assuming". The check was run; something does. |
| **3. Do the siblings have the same gap?** | **No — build only.** `--verify` and `--refresh-fundamentals` both route through `_store_window` → `research.declared_window`, which reads the *target's* manifest and was therefore never checkout-local. `--coverage` refuses `--test-window` outright at `:189` and only loads. `lab test --store` is content-guarded twice — `lab.py:484` and again in `runner.run_test` (`runner.py:501`). Only the build path is destructive (`_swap_in` replaces the directory) and only it had no content check. **They get regression tests, not edits** — so the coverage is asserted rather than inferred from reading. | **5: the user's raw input (Step 0)** — the fork is posed as a question of fact ("does the gap exist there"), and the fact was measured; R2 then carries the test that pins it. |

**On "cannot tell", stated once so phase 1 does not re-derive it.** `research.declared_window`
raises `ValueError` uniformly for a missing directory, an empty directory and an unparseable
`manifest.json` (measured; see the analysis table), and returns `DEV_WINDOW` for any manifest
lacking `window_end`. Phase 1 catches `(OSError, ValueError)` — strictly more lenient than the
`ValueError` those three shapes raise, so an unreadable directory falls through too rather than
crashing. Falling through is correct: a store whose manifest will not parse is already unusable, so rebuilding over
it destroys nothing, while refusing would block the workflow that most needs to run. A *partial*
manifest cannot occur in a swapped-in store — `build_store` writes `<store>.tmp` and `_swap_in`
publishes it with `os.replace` (`research.py:739`).

## Open Questions

None. All three forks the handover raised are decided above, each on a stated rung, and none is
irreversible.

## Rollback

One phase, one branch, nothing published and nothing migrated.

- **The whole set:** `git -C /home/miftah/seer worktree remove /home/miftah/.worktrees/seer/research-store-clobber-guard --force && git -C /home/miftah/seer branch -D feature/research-store-clobber-guard`. Nothing outside the worktree was written.
- **After a merge to `main`:** `git revert` the merge commit. The change is additive refusal logic
  plus tests; reverting restores the current behaviour exactly, and no data, store, manifest or lab
  row was ever touched by it.
- **No data rollback exists or is needed.** The phase writes no research store, spends no
  test-window look, and makes no lab-database write. Invariants 4, 5 and 7 are the checks that
  this held.

## Next

Execute the single phase:

    /implement -f RESEARCH_STORE_CLOBBER_GUARD_PLAN.md --phase 1

Or put it on the board first (GitHub repos only):

    /create-task --from-plan RESEARCH_STORE_CLOBBER_GUARD_PLAN.md
