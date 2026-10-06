# Plan: Build the promotion path

**Slug:** build-promotion-path
**Date:** 2026-10-06 11:57:23
**Analysis:** `20261006-115723-B7K2_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/build-promotion-path`
**Branch:** `feature/build-promotion-path` (base: `origin/main` @ `2d03fd1`)
**Phases:** 4
**Status:** reconciled
**Coordinator:** —
**Reconciled:** 2026-10-06 (round 1) — 11 conflicts found, 11 resolved; see **Reconciliation Log**

---

## Why

The user's request, verbatim:

```
the unbuilt promotion path
```

The specification is `docs/plans/2026-10-04-method-lab-design.md` §3, §5, §6. §5 scheduled this
work rather than omitting it:

> `lab test` and the test-window store are specified here and built on first promotion.

Batch `sera-20261006-1137` closed with three methods rejected and the closest-ever result
(residual momentum, MAR 0.77, DSR 0.914) one condition short of eligible. The next batch may
produce an eligible trial, and on that day the lab must be able to pre-register it, spend one
counted look, and record the outcome. Building it now, off the critical path, is the point.

The guardrail "never edit `DEV_END`" (design §4) is read as *never change its value and never
weaken what it guards*. Every phase below keeps `DEV_END = 2015-10-16`, keeps the three tests
that pin it passing unchanged, and keeps the D9 refusal absolute on every dev path. The window
becomes a parameter; the guard does not become optional.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | A test-window research store (2015-10-19 → latest session), built like the dev store, with the same files, manifest and checks | 1, 2 |
| R2 | `lab test <candidate>`: refuses without a committed pre-registration, runs once, records a `test` trial, sets `test-passed`/`test-failed` | 1, 4 |
| R3 | Pre-registration of the best dev-eligible variant by MAR in `docs/lab/prereg/MNNNN.md`, committed before any test number exists | 3 |

Final after reconciliation; no requirement moved between phases. One edit was examined for
requirement creep and cleared: phase 4's rewrite of `SKILL.md`'s `## Promotion` section now names
`lab promote` as step 1, which looks like R3 work in a phase that satisfies R2. It is not.
`lab test` **refuses** without a committed pre-registration, so an agent that is never told how to
produce one has a `lab test` that cannot run; documenting the precondition of the subcommand this
phase ships is R2. The mechanism that writes the file stays entirely in phase 3. Neither
**Satisfies** line was widened.

## Scope

**In scope:** parameterizing the backtest/research window without changing `DEV_END`; building
and loading `engine/.research-test`; the `lab promote` and `lab test` subcommands; the
pre-registration file format and its enforcement; tests for all of it.

**Out of scope, and why:**
- **The paper roster.** `commands/promote.py` and `lab.store.record_promotion` already exist,
  are tested, and were exercised on M0005/FND. Phase 4 hands off to them; it does not rebuild them.
- **Running an actual promotion.** No method is `dev-eligible` today. This plan builds the
  mechanism; it spends no test-window look. The counter must still read 0 when the set lands.
- **Changing the eligibility gate**, design §1/§5, the P7a registry, or any recorded trial.
- **ML refit wrappers** (design §2) — unrelated, built when first needed.

## Invariants

Every phase must hold all of these, and each phase's exit criteria restate the ones it can break:

1. **The tree builds and `pytest -q` passes in `engine/` at the end of every phase.**
2. **`DEV_END` keeps the value `2015-10-16` in both modules, and the equality
   `coverage.WINDOW_END == dev.DEV_END == research.DEV_END`
   (`tests/test_fundamentals_coverage.py:107`) holds.** No test that pins it may be edited.
3. **No dev path may read data after `DEV_END`.** A window parameter defaults to the dev window
   everywhere; a caller must pass the test window explicitly and can only do so through
   `lab test`.
4. **`lab run` is behaviourally unchanged** — same candidate windows, same `config_digest`s,
   same refusals. A recorded dev trial must stay reproducible, so digests must not shift.
5. **Trials stay append-only** and the test-look count stays enforced in the database
   (`UNIQUE(config_digest, window)`), not only in a command.
6. **`test-window looks used` reads 0 when this set lands.** Building the mechanism spends nothing.
7. **No phase commits `lab/lab.sqlite` or `web/data/lab.json`.** This set changes code, not the lab record.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Make the backtest window a parameter, keeping D9 absolute | R1, R2 | `engine/src/seer_engine/backtest`, `research.py` | 6 | — | HARD | `.workflows/plan/build-promotion-path/phase-1.md` | P1-ENG-5X3M | — |
| 2 | Build and load the test-window store | R1 | `research.py`, `commands/research_store.py` | 5 | 1 | NORMAL | `.workflows/plan/build-promotion-path/phase-2.md` | P1-ENG-8OLO | — |
| 3 | Pre-registration: `lab promote` and `docs/lab/prereg/` | R3 | `lab/`, `commands/lab.py` | 6 | — | NORMAL | `.workflows/plan/build-promotion-path/phase-3.md` | P1-ENG-AZ81 | — |
| 4 | `lab test`: one counted look, recorded and final | R2 | `lab/runner.py`, `commands/lab.py`, `SKILL.md` | 5 | 2, 3 | HARD | `.workflows/plan/build-promotion-path/phase-4.md` | P1-ENG-YJDW | — |

Phases 1 and 3 share no edge and run concurrently. Phase 1 serves two requirements because the
window parameter is a single foundation both the store (R1) and the runner (R2) need; splitting
it would leave one half unable to build green, so the coupling is real and stated rather than
decomposed away.

Every dependency points backward. Phase 4 is the only phase that shares a source file with a
phase it depends on (`commands/lab.py`, with phase 3), and its plan now quotes that file in its
post-phase-3 state rather than as it stands at `2d03fd1`.

**File ownership, one owner per region:**

| File | Owner | Also touched by |
|---|---|---|
| `backtest/window.py`, `backtest/dev.py` | 1 | — |
| `research.py` — the five window-bearing helpers, `unserved_reason` | 1 | — |
| `research.py` — `build_store` / `load_store` / `refresh_fundamentals` / manifest / `ResearchData` | 2 | — |
| `commands/research_store.py`, `.gitignore`, `engine/pyproject.toml` | 2 | — |
| `lab/prereg.py`, `lab/store.py` (`best_dev_eligible`), `docs/lab/prereg/README.md` | 3 | — |
| `lab/runner.py` (appended test-window section) | 4 | — |
| `commands/lab.py` | 3 (`promote`), then 4 (`test`) | sequenced; phase 4 quotes post-phase-3 |
| `tests/test_research_store.py` | 1 | nobody — phase 2 writes `test_research_test_store.py` |
| `tests/labkit.py` | 4 | — |
| `.claude/skills/explore-and-experiment-new-method/SKILL.md` | 4 (whole `## Promotion` section) | — |

### Phase 1 — Make the backtest window a parameter, keeping D9 absolute
**Satisfies:** R1, R2
**Owns:** `backtest/window.py` (new); `backtest/dev.py` guards, `candidate_window`,
`run_candidate`, `run_registry`, and `DevRow`'s new `window` field **including the relaxation of
`DevRow.__post_init__` to `check_dev_session(self.end, self.window)`** (`dev.py:280`) — without
which no test row can be constructed at all; the window-bearing helpers in `research.py`
(`_members_start`, `_overlaps_window`, `requested_symbols`, `research_membership`,
`unserved_by_year`, `unserved_reason`). Introduces the window value object and threads it
through, defaulting to the dev window. Sole editor of `engine/tests/test_research_store.py`.
**Does not touch:** store building or loading on disk (phase 2), any `lab/` module, any CLI,
`dev_report.py`, `fundamentals/coverage.py`, `tests/test_fundamentals_coverage.py`.
**Exit criteria:** `DEV_END` unchanged in both modules and the equality test passes untouched;
**no manifest key is added** (so `test_research_store.py:235`'s `set(manifest) == MANIFEST_KEYS`
holds); `unserved_reason()` is byte-identical to the retired `UNSERVED_REASON` constant, so the
dev store's fingerprint `399d0d25…` cannot move; every existing caller compiles with no argument
changes; a unit test proves a market holding a post-`DEV_END` bar is still refused when the dev
window is in force, and accepted only when a test window is passed explicitly; the membership
clamp is against the passed window's end; the universe is `[max(window.start, MEMBERSHIP_START),
window.end]`; `lab run`'s digests are byte-identical to before.

### Phase 2 — Build and load the test-window store
**Satisfies:** R1
**Owns:** `research.build_store` / `load_store` / `refresh_fundamentals` window plumbing;
`ResearchData.window`; the manifest's optional window identity (`window_name`, `window_start`,
`window_end`) and `declared_window`; `TEST_STORE_DIR`, `TEST_WINDOW_START`, `test_window`,
`latest_session`; the deletion of `research._after_dev_end` in favour of `_after_window_end`
(three call sites, all inside `research.py`); `commands/research_store.py`'s `--test-window` and
`--window-end`; `.gitignore` and the ruff exclude for `engine/.research-test`.
**Does not touch:** `backtest/dev.py` or `backtest/window.py` (phase 1), `commands/lab.py` or any
`lab/` module (phases 3, 4), `engine/tests/test_research_store.py` (phase 1 — phase 2 adds
`engine/tests/test_research_test_store.py` instead), `tests/test_fundamentals_coverage.py` or
`fundamentals/coverage.py`.
**Exit criteria:** a test store can be built into `engine/.research-test` with
`research_store --test-window`; `load_store` verifies it by fingerprint and **refuses to load a
test store where a dev store is expected and vice versa**, before any data file is read;
membership intervals are clamped against the test window's end, not `DEV_END`; the universe is
the test window's members at **both** ends — every post-2015 joiner in, every company that left
before 2015-10-19 out; the store's *data* still runs from `STORE_START` (1993-01-29) so the
lookback run-up is present; **`MANIFEST_KEYS` is unchanged and a dev build writes no window key**,
so the dev store loads bit-identically (fingerprint `399d0d25…` unchanged) and
`test_research_store.py:235` passes unedited.

### Phase 3 — Pre-registration: `lab promote` and `docs/lab/prereg/`
**Satisfies:** R3
**Owns:** `lab/prereg.py` — the `docs/lab/prereg/MNNNN.md` format, its writer, its parser and the
committed-file gate (`require_committed(candidate_id, *, directory=None) -> Prereg` and
`check_digest(p, digest, *, directory=None)`, raising `PreregError(store.LabError)`);
`store.best_dev_eligible`; a `lab promote <method>` subcommand writing the prereg file and moving
`dev-eligible → promoted`; `docs/lab/prereg/README.md`. **Lands before phase 4 in
`commands/lab.py`** and is the earlier owner of that file's three insertion regions.
**Does not touch:** `backtest/`, `research.py`, the test store, the test runner,
`record_promotion`, `commands/promote.py`, or any skill file (phase 4 owns `SKILL.md` outright).
**Exit criteria:** `lab promote` refuses a method that is not `dev-eligible`; writes exactly one
prereg file carrying `method`, `candidate`, `config_digest`, `gate`, `test_window` and `date`
(every field a `str`); is idempotent and never rewrites a committed file, not even its `date`;
refuses to change its mind about which variant is pre-registered; a test proves the prereg file's
digest is **copied from** the recorded dev trial's digest, so the thing pre-registered is the
thing that will be tested; the file's prose states that the test look is judged by the five
go-live conditions alone, with DSR recorded and not applied, so the `gate` field (the **dev**
gate) cannot be read as the test gate; `store.test_looks` stays 0 and no `trials` row is written.

### Phase 4 — `lab test`: one counted look, recorded and final
**Satisfies:** R2
**Owns:** the test-window runner in `lab/runner.py` (`Tested`, `resolve_candidate`,
`preflight_test`, `test_trial_row`, `run_test`, all appended — nothing above `:253` changes) and
the `lab test <candidate>` subcommand; the `promoted → test-passed|test-failed` transition; the
printed hand-off to `commands/promote.py` on a pass; `tests/labkit.py`'s test-window fixtures;
**the whole `## Promotion` section of
`.claude/skills/explore-and-experiment-new-method/SKILL.md`, which must document `lab promote`
as well as `lab test`.**
**Does not touch:** `backtest/dev.py` (phase 1 — including `DevRow.__post_init__`); `research.py`
or `commands/research_store.py` (phase 2); `lab/prereg.py` or the `promote` subcommand (phase 3);
`lab/store.py` (no schema change, no migration); `commands/lab.py:237`'s
`research.load_store(Path(args.store))` dev default; `record_promotion`; the eligibility gate;
`fundamentals/coverage.py`; `lab/lab.sqlite`; `web/data/lab.json`.
**Exit criteria:** `lab test` refuses a candidate with no committed prereg file (via phase 3's
`require_committed`), one whose digest drifted (via phase 3's `check_digest`), one whose method
is not `promoted`, one with no dev trial, and a second look (proven against the database with raw
SQL, not only in the command); refuses a dev store pointed at it, by name, before anything runs;
records one `trials` row with `window='test'` that **does not increment the lab's dev N**
(`dev_trial_count` and `dev_daily_sharpes` byte-identical before and after); DSR is recorded and
never appears in `failed`; sets `test-passed`/`test-failed`, both final; on a pass prints a
ready-to-run `promote` command with every argument filled in; `SKILL.md` names both subcommands
and tells the agent to run that printed line; `lab status` and the web snapshot report
`test-window looks used: 1` after a simulated look in a temp database, and **0 in the real one**.

## Reconciliation Log

Round 1, 2026-10-06. Eleven conflicts found, eleven resolved by editing the plan files. Four
further points were checked and found to be **non-conflicts**; they are logged too, because a
verified non-conflict is what stops the same alarm being raised again downstream.

| # | Conflict | Class | Resolution |
|---|---|---|---|
| 1 | Phase 4 coded against an assumed `prereg.read_committed(method_id, *, require_commit=True)` returning `.candidate_id` / `.config_digest` / `.path`. Phase 3 built `require_committed(candidate_id, *, directory=None)` + a **separate** `check_digest(p, digest)`, a `Prereg` whose field is `candidate` (not `candidate_id`) with **no `.path`**, and **no `require_commit` parameter anywhere**. | Unmet assumption / contract drift | **Phase 4 edited to phase 3's real API**, never the reverse — phase 3 owns the module. `preflight_test` now calls `prereg.require_committed(candidate.id)` then `prereg.check_digest(p, config_digest(candidate))`. Its two hand-rolled comparisons (candidate id, digest) are **deleted**, not duplicated: both already live inside phase 3's functions. The path is `prereg.path_for(p.method)`. |
| 2 | Phase 4 needed `require_commit=False` for its in-transaction re-check and its tests, and phase 3 offers no such flag. | Unmet assumption | `preflight_test` gained `pre: prereg.Prereg \| None = None` instead. `require_committed` shells out to git, so it runs once up front and its answer is handed back into the re-check inside the write lock, where `check_digest` and both database refusals still run. **No change to phase 3.** |
| 3 | Phase 4's tests stubbed `prereg.read_committed` with a local `_Prereg` dataclass carrying the wrong field names. | Contract drift | Replaced with a `_prereg(candidate)` helper that builds a **real** `prereg.Prereg` (fifteen `str` fields, no behaviour), and the monkeypatch now targets `require_committed`. `check_digest` is deliberately **not** stubbed, which turns the stale-digest test into a real test of phase 3's code. Unused `dataclass` / `Path` imports dropped so ruff stays green. |
| 4 | **Phase 1 and phase 2 disagreed about the membership lower bound, each with passing-looking tests.** Phase 1: `_members_start(window) = max(window.start, MEMBERSHIP_START)` with `assert "GONE" not in symbols`. Phase 2: "the lower bound stays `MEMBERSHIP_START` for both windows" with `assert set(dev) < set(test)` and `assert "GONE" in test`. The two cannot both pass. | Contract drift (two owners, one rule) | **Phase 1 wins; phase 2 edited.** See Decisions, row "the test store's universe". Phase 2's property statement, `build_store`'s docstring, `test_a_test_build_requests_the_test_windows_members`, `test_a_test_store_is_a_superset_of_the_dev_stores_date_range` (now a per-symbol comparison) and exit criteria 2b and 4 were all rewritten. Phase 2 was also internally inconsistent here — its exit criterion said "the test window's members" *and* "a strict superset of the dev universe", which are different sets. |
| 5 | Phase 4 said the test store's build flag is `research_store --test`; phase 2 built `--test-window`. Three user-facing refusal strings. | Contract drift | All three edited to `--test-window` in phase 4, plus the `--with-fundamentals` sentence. Phase 2's Handoffs now spell the three names phase 4 must not re-invent. |
| 6 | Phase 4 called `research.load_store(store_dir, window="test")` — a **name string**. Phase 2's signature is `load_store(store_dir, *, data_dir=None, window: Window = DEV_WINDOW)` — a **value**. | Contract drift | Phase 4's `_test` rewritten to phase 2's own documented idiom: `window = research.declared_window(store_dir)`, refuse when `window.name != "test"`, then `research.load_store(store_dir, window=window)`. The `declared_window` refusal names the fix and the right directory. |
| 7 | **Gap: nothing documented `lab promote`.** Phase 3 deliberately handed all of `SKILL.md` to phase 4; phase 4 edited only the `lab test` bullet and steps 2 and 4, leaving step 1 ("Pre-register … in `docs/lab/prereg/MNNNN.md`") with no command — and `lab test` refuses without that file. The section also still told the agent to **build** `lab test` and the test store. | Gap | Phase 4's Step 10 now replaces the **whole `## Promotion` section** (`SKILL.md:123`–`:143`): both subcommands described, `lab promote` + the commit as step 1, `lab test --dry-run` then `lab test` as step 2, the printed `promote` command to **run** as step 4, and the test store named with its real build flag. Phase 3's handoff updated to record that phase 4 owns the file outright. Checked for requirement creep and cleared as R2 work (see **Requirements**). |
| 8 | **Missed by the orchestrator: phases 3 and 4 both insert into `commands/lab.py` at the same three regions** — a subparser after `run`'s, a handler after `_run` ends at `:262`, and `_HANDLERS` at `:375`. Phase 4's anchors were line numbers from `2d03fd1`, which phase 3 invalidates. | File collision | Phase 3 is the earlier owner and keeps its anchors. Phase 4's Steps 6a, 6b, 7 and 7b re-anchored on **phase 3's blocks** — after the `promote` docstring block, after the `promote` subparser, after `_promote`, after `"promote": _promote,` — so the file reads `run → promote → test` in all four places. Both plans now carry the sequencing note. |
| 9 | Phase 4's "cross-phase question the reconciler must settle": does `engine/.research-test` hold the lookback run-up? Left open in phase 4 and in its Handoff 1. | Duplicate work / stale open question | Already settled by phase 2's coordinator decision: the store is built over `STORE_START..window.end` and the window's `start` floors the *run*. The question and the handoff were **edited out** of phase 4 and replaced with the settled answer, so no phase session meets the fork at 3am. |
| 10 | Phase 4's Handoff 2 asked phase 3 to make the prereg's `gate` field name the gate the look will be judged by. Phase 3's `gate_text()` records the **dev** gate (five D8 conditions **and** DSR ≥ 0.95); phase 4 decided the test verdict is the five alone with DSR recorded, not applied. A reader of the file could take one for the other. | Contract drift | **Phase 3 edited, minimally:** `gate_text()`'s docstring now says it is the dev gate and not the test gate, and `render`'s prose gains a paragraph stating what the look is judged by, written down before it happens. No field, no signature and no test in phase 3 changed. Phase 4's handoff rewritten as settled. |
| 11 | Phase 4 referenced `dev.Window` (resolving only because `dev.py` imports it) in its Assumed-interfaces table and in `labkit`. | Contract drift | Changed to `from seer_engine.backtest.window import Window`, the module phase 1 creates and owns. `labkit`'s `smoke_test_data` also had `manifest={"window": "test"}`; corrected to phase 2's real `window_name` / `window_start` / `window_end` keys. |

**Checked and found to be non-conflicts** (no edit needed; recorded so they are not re-raised):

| Point | Verdict |
|---|---|
| `DevRow.__post_init__` calling `check_dev_session(self.end)` (`dev.py:280`) — phase 4 called this a hard blocker and a possible phase-1 gap | **Not a gap.** Verified in `phase-1.md` Step 5: phase 1 appends `window: Window = DEV_WINDOW` *and* changes the call to `check_dev_session(self.end, self.window)`, plus a `start < window.start` floor. Phase 4 needs no change to `backtest/dev.py` and makes none. Both plans now say so explicitly. |
| `_overlaps_window`'s **upper** bound and `research_membership`'s clamp | **Both correct in phase 1.** The upper bound is `iv.start_date <= window.end`, so post-2015 joiners are in the test universe; the clamp is `end = iv.end_date if iv.end_date <= window.end else None`, so a company that left in 2018 stops being a member in 2018 rather than reading as one through 2026. Phase 2 consumes both unchanged (`research_membership(data_dir, window=window)` inside `load_store`). Only the *lower* bound was in dispute — conflict 4. |
| Dev fingerprint `399d0d25…` | **Cannot move.** Phase 1 adds **no** manifest key (`test_research_store.py:235`'s `set(manifest) == MANIFEST_KEYS` holds) and keeps `UNSERVED_REASON = unserved_reason()` byte-identical at `(STORE_START, DEV_END)`. Phase 2 puts the window identity in a *separate* `OPTIONAL_MANIFEST_KEYS` that a dev build never writes, and `fingerprint_of` hashes the `files` map alone. `research._after_dev_end` has exactly three references, all inside `research.py` (`:796`, `:843`, `:861`) — all phase 2's — and `_after_window_end` reproduces the dev message verbatim, so `test_research_store.py:412` stays green. (`tests/test_research_store.py:405` is a test *name* containing the string, not a reference.) |
| `commands/lab.py:237`'s `research.load_store(Path(args.store))` dev default | **Untouched by every phase.** Phase 2 does not edit `commands/lab.py` at all; phase 4 adds a `--store` only to its own `test` subparser, with its own `SEER_RESEARCH_TEST_STORE` env var and `research.TEST_STORE_DIR` default. A mis-pointed `SEER_RESEARCH_STORE` still fails loudly on `lab run`. Both plans now state it. |
| `test_research_store.py` as a shared file (phases 1 and 2) | **Not shared.** The orchestrator's summary said phase 2 also adds to it; the plan says the opposite — phase 2 puts everything in a new `test_research_test_store.py` precisely to avoid the collision. Phase 1 is the sole editor; both plans corrected to say so. |
| `/sera-the-explorer`'s SKILL.md | **No edit needed by any phase.** Its only mention is `:11`, "promotes eligible methods", which names no command and is already accurate. Phase 3's handoff updated to say so rather than leaving it dangling. |

**Coverage, re-verified after the edits.** Every entry in the analysis's **Reference List** and
all eight **Impact Points** have an owner: `backtest/dev.py` → 1; `research.py` → 1 (helpers) and
2 (store); `commands/research_store.py`, `.gitignore` → 2; `docs/lab/prereg/` → 3;
`lab/runner.py` → 4; `commands/lab.py` → 3 then 4; `engine/tests/` → all four. `lab/store.py`'s
`test_looks`, `record_promotion`, `WINDOWS`, the UNIQUE constraints and the append-only triggers
already exist and are consumed, not rebuilt. No requirement id moved; no `Satisfies` line was
widened.

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| §3 "a paper roster entry is the owner's call" vs §6 "never ask, including the paper-roster entry" | §6 governs — the roster entry is autonomous | 5: the user's specification (§6 is the later owner revision of the same document) |
| A test trial's `n_trials_at_run` / DSR: count it in the lab's N, or not | **Not counted.** A test trial is the out-of-sample check on an already-counted configuration, not a new search. `store.dev_trial_count` stays dev-only and N does not move. | 4: design §1 — `trials` "is the multiple-testing count", and §3 makes the test a *look*, not a search |
| Test window end: a fixed date vs the latest available session | **Latest available at build time, recorded in the manifest.** §3 says "2015-10-19 → data end"; a fixed end goes stale and silently changes what a recorded test trial meant. | 5: design §3 wording |
| Generalise `DEV_END` vs add a window parameter beside it | **Parameter beside it.** The value stays, the pinning test stays, the guard stays absolute by default. Changing the constant would break the equality test and weaken D9. | 1: plan invariant 2 |

### Added by the reconciler, 2026-10-06

| Fork | Chosen | Rung |
|---|---|---|
| **The test store's universe.** `research._overlaps_window`'s *lower* bound: phase 1 wrote `max(window.start, MEMBERSHIP_START)` (the test universe is the test window's own members); phase 2 wrote "stays `MEMBERSHIP_START` for both windows" (the test universe is a strict superset of the dev one). Each had a passing-looking test asserting the other's is wrong. | **`max(window.start, MEMBERSHIP_START)` — phase 1's.** The test universe is every company that is an index member on some session of `[2015-10-19, end]`: every post-2015 joiner is in, every company that left the index before 2015-10-19 is out. **Phase 2's two tests and four prose passages were edited out.** The decision costs the look nothing: `members_on(t)` is identical under both bounds for every `t` in the test window, because an interval that closed before 2015-10-19 contributes no member on any test-window session — so the recorded trial would be the same number either way. Only the size of the crawl and the `unserved_by_year` range differ. Phase 2's stated reason for the wider bound ("still needed for the deep history") conflated two things the coordinator decision already separates: run-up is a **date-range** property (`STORE_START..window.end`, on both stores) and not a **symbol-selection** property. The dev window is byte-identical either way, since `DEV_WINDOW.start` is `date.min`. | 2: the phases' exit criteria — this index's phase-2 criterion reads "the universe is the test window's members, **not the dev window's**", and a strict superset of the dev universe is by construction the dev window's members plus more. Reinforced by phase 2's own internal contradiction, which stated both halves in one sentence. |
| **The promote hand-off.** `lab test` invoking `commands/promote.py` in-process vs printing the fully-filled command for the agent to run. | **Print it; the agent runs it.** `lab test` stays offline — a research store and a SQLite file — and the counted look never risks failing on a network. SKILL.md step 4 tells the agent to run the printed line, so design §6's "never ask" still holds: an agent, not a human, runs it. Accepted by the set's owner. | 6: the surrounding code's convention — `record_promotion`'s own docstring states that the roster (Neon) and the lab (SQLite) cannot share one transaction, which is exactly why it was built idempotent and re-runnable. |
| **Which phase documents `lab promote` in `SKILL.md`.** Phase 3 (the R3 owner, which builds the command) vs phase 4 (the R2 owner, which lands last and can describe both commands in one coherent section). | **Phase 4, as one section replacement, and it stays an R2 step.** Phase 3 touches no skill file. `lab test` *refuses* without a committed pre-registration, so documenting how to produce one is the precondition of phase 4's own subcommand, not the pre-registration mechanism — which is why this is not requirement creep and no `Satisfies` line was widened. Splitting the section between two phases would have put two owners in one 21-line region for no gain. | 6: the surrounding code's convention — one owner per file region, the same rule that sequences `commands/lab.py` between phases 3 and 4. |

## Open Questions

_None._ Every fork above was decided on a stated rung, and the reconciler added three more rather
than parking any of them. No branch of any of them is irreversible: each is a code change on a
feature branch, revertible in one commit, and **this plan set spends no test-window look** — the
one genuinely irreversible act in this area (a `test` trial is append-only and there is exactly
one per configuration) is an operator action taken after the set lands, not part of it. The
universe decision, the only one with a data consequence, costs nothing even if revisited: it
changes which symbols the crawl downloads, not what a recorded trial would say, and the store is
gitignored and rebuildable.

Every requirement id has at least one phase serving it (R1 → 1, 2; R2 → 1, 4; R3 → 3), so there
is no unowned `R` to park here either.

## Rollback

**Per phase:** each phase is one commit on `feature/build-promotion-path`; `git revert` it.
Phases 2–4 add new files and new code paths behind new flags and subcommands, so reverting any
of them leaves `lab run` untouched.
**As a whole:** delete the branch. Nothing in this set writes to `lab/lab.sqlite`, spends a
test-window look, or changes a recorded trial, so there is no lab state to unwind. Delete
`engine/.research-test/` (gitignored) to reclaim the disk.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f BUILD_PROMOTION_PATH_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f BUILD_PROMOTION_PATH_PLAN.md
