# Plan: Recorded trials reproduce, and the gate compares like with like

**Slug:** trial-reproducibility
**Date:** 2026-10-09T12:38Z
**Analysis:** `20261009-192826-T7RQ_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/trial-reproducibility`
**Branch:** `feature/trial-reproducibility` (base: `origin/main` @ `e5eda52`)
**Phases:** 4
**Status:** planned
**Coordinator:** —

---

## Why

From `docs/plans/HANDOVER_20261009.md` §5.1, verbatim in the analysis document. The core of it:

> **Why it is not a fire today, and why it will be.** […] the hard gate now makes real promotion
> decisions out of cross-store arithmetic, and the margin only has to be thin once.
>
> **Questions to answer with measurement, not assumption** […] state the options, measure what
> each costs, pick, and say why.
>
> **Hard constraints.** `trials` is append-only — triggers refuse UPDATE and DELETE. `test-failed`
> and `test-passed` are final; `TRANSITIONS` has no edge out of either. Do not invent one.

**What the measurement found (analysis M1–M6), which reshapes the answer:**

- The three dev fingerprints carry **byte-identical price data**; they differ only in
  `fundamentals.csv`. Recomputing the current store's fingerprint without that file yields exactly
  `5451195fd552…`. The store never drifted.
- The real break is the engine's **starting capital**: `d79fc83` moved `INITIAL_IDR` from 20M to
  10M IDR on 2026-10-08, nothing records it per trial, and whole-share rounding makes it
  result-moving. With 20M restored, `lab remeasure M0007`, `M0011` and all 54 `H-P7A` seed trials
  reproduce **exactly** on today's store.
- Rule, exact on all 152 trials (checked against git ancestry): lump-sum → 20M, funded → 10M.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Choose the policy among (a) pin store / (b) re-run benchmark / (c) refuse on fingerprint mismatch / (d) record enough to re-derive — measured by what each strands, and say why | 1, 2, 3, 4 |
| R2 | Is `trials.store_fingerprint` enough to detect it; should `lab walkforward`, `lab regime`, `hardgate` warn or refuse | 3, 4 |
| R3 | Quantify the drift on a method curve, not just the benchmark | 4 (measured in the analysis; re-verified on the finished code and recorded here) |
| R4 | Does the 58-trial `5451195fd552` cohort need re-running or marking (append-only) | 2, 4 |

Phase 4 serves R1 and R2 for their written half only — the options, their measured cost, the
choice and the why (handover note, runbook, lab insight) — see Decisions.

## Scope

**In scope:** a per-trial provenance record (starting capital + price fingerprint) in a new
append-only table, backfilled by migration; every re-run of a recorded trial at its recorded
capital; de-funding by recorded capital; a price-fingerprint comparability refusal in the hard gate,
warnings in `lab walkforward` / `lab regime`, a dev-store pin on `lab run`; the lab insight, docs,
the three skills that told a session to build a missing store, and `lab stage`.

**Out of scope:** writing any recovered `trial_moments` (M6 — it changes readings, e.g. makes
`H-P7A-F9` re-evaluable; the explore loop owns that judgement); `lab reevaluate` of anything;
§5.2 market-cap; §5.3 syncing the test store; `walkforward.buy_signal`; any hard-gate override;
changing `INITIAL_IDR`; a path for re-recording the benchmark on a rebuilt store.

## Invariants

1. The tree builds and the full engine suite passes at the end of every phase
   (`cd engine && PYTHONPATH=$PWD/src /home/miftah/seer/engine/.venv/bin/python -m pytest -q`
   from the worktree — the worktree has no venv of its own).
2. `trials`, `trial_moments`, `trial_funding` are never UPDATEd or DELETEd; provenance is an
   **added** table with its own no-update / no-delete triggers.
3. No new trial row, no test-window look, no `methods.status` move, no `trial_moments` row is
   written to the committed `lab/lab.sqlite` by any phase. Experiments run on scratch copies.
4. No override path of any kind on the hard gate or the store pin.
5. `lab status` on the committed database still prints `Promotable now: (none)`, and the hard
   gate's refusal reason for each of the seven dev-eligible methods is unchanged (M5: the new
   rule strands 0).
6. Live behaviour of a new `lab run` is byte-identical: default capital stays `INITIAL_IDR`.
7. The worktree has no research store: pass `--store /home/miftah/seer/engine/.research`.
8. Commit by pathspec; never `git add -A`; `lab/lab.sqlite` is committed only through `lab stage`.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Starting capital is a run input | R1 | `backtest` | 2 | — | EASY | `.workflows/plan/trial-reproducibility/phase-1.md` | — | — |
| 2 | Per-trial provenance, and re-runs at the recorded capital | R1, R4 | `lab`, `research`, `commands` (`_costs` only), `tests/labkit` | 18 | 1 | HARD | `.workflows/plan/trial-reproducibility/phase-2.md` | — | — |
| 3 | Compare like with like: gate refuses, reports warn, `lab run` pins the store | R1, R2 | `lab` (`hardgate`), `commands` | 5 | 2 | NORMAL | `.workflows/plan/trial-reproducibility/phase-3.md` | — | — |
| 4 | Verify on copies, record the finding, stage the migrated lab | R1, R2, R3, R4 | docs, skills, `lab/lab.sqlite` | 8 | 2, 3 | NORMAL | `.workflows/plan/trial-reproducibility/phase-4.md` | — | — |

Every dependency points backward. Phases run strictly 1 → 2 → 3 → 4: phase 3 quotes
`hardgate.py`, `commands/lab.py` and `test_lab_hardgate.py` as phase 2 leaves them.

### Phase 1 — Starting capital is a run input
**Satisfies:** R1 (policy (d): the input that was missing becomes passable)
**Owns:** `engine/src/seer_engine/backtest/dev.py` — an `initial_idr: Decimal = INITIAL_IDR`
keyword on `_run`, `run_candidate`, `run_registry`, passed to `run_rules`; seven tests in
`engine/tests/test_backtest_dev.py`.
**Does not touch:** `INITIAL_IDR`'s value; anything under `lab/` or `commands/`.
**Exit criteria:** a call without the keyword `==` a call with `initial_idr=INITIAL_IDR` on both
engines; `initial_idr=Decimal("20000000")` reaches `run_rules` and changes a whole-share run's
result; the full engine suite passes.

### Phase 2 — Per-trial provenance, and re-runs at the recorded capital
**Satisfies:** R1 (d), R4 (marking the cohort by annotation)
**Owns:**
- `research.py`: `price_fingerprint_of(files)` (= `fingerprint_of` over the four `DATA_FILES`,
  fundamentals excluded) and the dataclass field `ResearchData.price_fingerprint: str | None =
  None` (last field; `load_store` always sets it; None = unknown).
- `lab/store.py`: `SCHEMA_VERSION = "5"`; table `trial_provenance(trial_n PK FK, initial_idr TEXT
  NOT NULL, price_fingerprint TEXT NULL, source TEXT NOT NULL CHECK IN ('recorded','backfill'),
  measured TEXT NOT NULL)` with `trial_provenance_no_update` / `_no_delete` triggers;
  `ProvenanceRow` (`initial_idr: Decimal`), `PROVENANCE_COLUMNS`, `insert_provenance`,
  `provenance_of`, `P7A_PRICE_FINGERPRINT`, `BACKFILL_*` constants; migration `_v4_to_v5`
  backfilling every trial lacking a row (capital by the funding rule M3; price fingerprint by the
  known-fingerprint map, else NULL), `source='backfill'`.
- `lab/runner.py`: `recorded_capital(conn, n)` (refuses with `store.LabError` when no row);
  `run_method` / `run_test` pass `initial_idr=INITIAL_IDR` explicitly and write a
  `source='recorded'` row per trial in the same transaction.
- `lab/seed.py`: `P7A_INITIAL_IDR`; the 54 seed trials get `source='backfill'` rows.
- `lab/remeasure.py`: `plan_capital`; `Plan.initial_idr`; `preflight` **and** `seed_preflight`
  refuse missing or mixed recorded capital before any store loads; `measure` / `run_chunk`
  re-run at the recorded capital; the METRIC_TOL comment corrected with M4.
- `lab/real_costs.py`: `measure(..., initial_idr=...)`; `commands/lab.py:_costs` (only) resolves
  `runner.recorded_capital` before the store loads.
- `lab/hardgate.py:trial_deposits` (only): `unit = amount_idr / recorded_capital`.
- `engine/tests/labkit.py`: smoke fixtures' `price_fingerprint` (`"smoke"`, `"smoke-test"`);
  `LAB_PRICE_FINGERPRINT` and the plan set's **one** fixture stamping helper,
  `stamp_provenance(conn, ns, *, price_fingerprint=..., initial_idr=Decimal("10000000"))`,
  idempotent.
- Tests for all of the above.
**Does not touch:** comparability checks, `lab run`'s store check, `commands/lab.py` `_run` /
`_walkforward` / `_regime` (phase 3); docs, skills and the committed database (phase 4).
**Exit criteria:** on a scratch copy of the committed DB migrated to v5, exactly 152 provenance
rows by the rule; `lab remeasure M0011`, `lab remeasure M0007` and `lab remeasure H-P7A` exit 0 on
today's store at today's `INITIAL_IDR`; the committed DB untouched; the full engine suite passes.

### Phase 3 — Compare like with like
**Satisfies:** R2, R1 (policies (a) and (c′))
**Owns:**
- `lab/hardgate.py`: module-docstring decision **(D10)**; `Geometry.bench_n`; `benchmark_n`,
  `mismatches`, `describe`, `comparability`, `pin_dev_store(conn, price_fingerprint: str | None)`;
  `fold_record` (hence `check`, `fold_summary`, `summary`) refuses with `store.LabError` when the
  benchmark's or any method dev trial's price fingerprint is missing, NULL, or different. Fail
  closed, no override.
- `commands/lab.py`: usage text; `_run` calls `hardgate.pin_dev_store` after the store loads and
  before any backtest (refuses an unknown store fingerprint always, a different one when the lab
  has a benchmark); `_comparability_warnings`; `_walkforward` / `_regime` print one `WARNING`
  line per incomparable method and still report.
- Tests: `test_lab_hardgate.py` (fixtures stamp via `labkit.stamp_provenance`; D10 gate, pin,
  report and CLI tests), `test_lab_prereg.py` and `test_lab_status.py` fixtures stamp.
**Does not touch:** `walkforward.py` (pure; the buy signal is the owner's), `trial_deposits`,
the provenance schema and `labkit.py` (phase 2), docs and skills (phase 4).
**Exit criteria:** on a scratch copy of the committed DB, `lab status` and `lab walkforward` are
byte-identical to the base commit's (0 stranded, no `WARNING`); `hardgate.comparability` is `()`
for all seven dev-eligible methods; a fixture on other prices is refused by `lab promote` and
warned by `lab walkforward`; `lab run` on other prices exits 2 before any backtest and
`pin_dev_store(conn, None)` refuses; the full engine suite passes.

### Phase 4 — Verify on copies, record the finding, stage the migrated lab
**Satisfies:** R3, R4; R1 and R2 (their written answer)
**Owns:** the end-to-end verification on scratch copies (M2/M4 reproduced at today's
`INITIAL_IDR`; `lab costs M0011` flat column = trial #90; `lab status` identical to `e5eda52`);
one `lab insight --kind observation` on the committed database; `lab stage` (which migrates the
committed DB to v5 with its backfill and regenerates `web/data/lab.json`);
`docs/runbooks/data-pipeline.md`, `engine/package_readme.md`, a dated "Resolved" note under
`docs/plans/HANDOVER_20261009.md` §5.1; the store-acquisition guidance in
`.claude/skills/sync-research-store/SKILL.md`, `explore-and-experiment-new-method/SKILL.md` and
`redo-sera-experiments/SKILL.md`.
**Does not touch:** any file under `engine/src/` or `engine/tests/`; any `trial_moments` row on the
committed DB.
**Exit criteria:** committed DB at schema 5 with 152 provenance rows (all `backfill`), 38
`trial_moments`, 24 `trial_funding`; `lab status` still `Promotable now: (none)`;
`test_lab_snapshot` passes; the full engine suite passes; one commit holding exactly the eight
paths of its Step 10.

## Reconciliation Log

Round 1, 2026-10-09. Every row is resolved in the plan files named.

| # | Conflict class | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | Contract drift | P2 ↔ P3 | P2 defines `ResearchData.price_fingerprint` as a dataclass field `str \| None = None`; P3 assumed a `str` property and typed `pin_dev_store(conn, price_fingerprint: str)` | P3 Requires corrected; `pin_dev_store` takes `str \| None` and refuses None first (fail closed); new test `test_the_dev_store_pin_refuses_a_store_whose_prices_are_unknown`; P3 exit criteria and Step 8 impact updated |
| 2 | Contract drift (would fail at runtime) | P2 ↔ P3 | P3's `stamp_provenance` passed `initial_idr="10000000"` (str); P2's `insert_provenance` refuses a non-`Decimal` capital with `LabError` — every P3 gate fixture would have raised | The helper takes `initial_idr: Decimal = Decimal("10000000")`; P3 Requires lists `ProvenanceRow.initial_idr: Decimal` |
| 3 | Duplicate work | P2 `test_lab_hardgate.py` `_capital` / `_funded_trial`, P3 `labkit.stamp_provenance` | Two fixture stamping sites on an append-only one-row-per-trial table | One helper, `labkit.stamp_provenance`, idempotent (skips a trial with a row), **created in P2** (earliest phase needing it). P2's `_capital` deleted; its funded tests and `_funded_trial`, and P2's remeasure / remeasure-seed tests, call the helper. P3 Step 12 replaced by a no-change note |
| 4 | File collision | `engine/tests/labkit.py` (P2 smoke fingerprints, P3 helper) | Two phases editing one file | P2 owns every `labkit.py` edit; P3 no longer touches it (Files table updated) |
| 5 | File collision / later quotes pre-change state | `test_lab_hardgate.py` (P2 imports + funded tests, P3 imports + fixtures) | P3 quoted `e5eda52` imports (:15-18) and `_benchmark`/`_method` at :79-110 | P2's import block written out in full; P3 quotes it as P2 leaves it (:15-20, extends `from labkit import stamp_provenance`), fixtures at :81-112, appends at end of file |
| 6 | File collision | `commands/lab.py` (P2 `_costs`, P3 `_run`/`_regime`/`_walkforward`/usage) | P3 line numbers were `e5eda52`'s; P2 adds 5 lines in `_costs` | P3 anchors moved to post-P2 (`_regime` :1817, `_walkforward` :1908); no region overlaps |
| 7 | File collision | `lab/hardgate.py` (P2 `trial_deposits`, P3 everything after it) | P2 grows `trial_deposits` 45 → 55 lines | P3 anchors moved +10 (`Geometry` :240, `geometry` :258, `_dev_curves` ends :314, `fold_record` :317); P3 leaves `trial_deposits` alone |
| 8 | Unmet assumption (checked) | P2 handoff: smoke data vs P3 pin | Smoke data's price fingerprint is `"smoke"`, a seeded lab's benchmark is P7a — a CLI `lab run` test would be refused | Grepped `e5eda52`: no test reaches `commands/lab.py:_run`; runner-level tests call the unpinned `runner.run_method`; P3's own `_run` tests stub `load_store` with explicit fingerprints. No fixture change needed; recorded in P2 Handoffs and P3's fixture audit |
| 9 | Broken-build phase (checked) | P2 `test_every_committed_trial_gets_exactly_one_provenance_row_by_the_rule` | Its `dev_fps == {P7A}` clause holds for future recorded dev trials only because of P3's pin | Green in P2 alone: the branch's committed DB stays v4 with no new trial until P4 (Invariant 3), so every row is a backfill. Docstring now names P3's `pin_dev_store` as what keeps it true afterwards |
| 10 | Unmet assumption | P1 handoff → P2 seed path | `run_registry` takes one capital; P2 refused a mixed **seed** set only per chunk, after the store loaded and after earlier chunks committed | `seed_preflight` calls `plan_capital` over the whole to-do set (missing **or** mixed → refuse before any store loads), as `preflight` does for the dev path; the per-chunk call stays as a second refusal. Test rewritten to `test_seed_trials_recorded_at_two_capitals_are_refused_before_any_store_is_loaded`. P1 handoff marked resolved |
| 11 | Contract drift (docs) | P4 doc text vs P2/P3 | P4 said reports reuse `hardgate.comparability` (they use `hardgate.mismatches` via `_comparability_warnings`); did not name `pin_dev_store`, `benchmark_n`, `Geometry.bench_n`, D10; said `lab seed` writes `recorded` rows (P2 writes `backfill`) | P4 Requires lists the real names; readme subsection and runbook text rewritten to match; `plan_capital` mixed-capital refusal documented |
| 12 | Gap | `.claude/skills/{explore-and-experiment-new-method,redo-sera-experiments,sync-research-store}/SKILL.md` | They tell an unattended session to build a missing dev store (or rebuild for newer data); after P3 a store on other prices is refused by `lab run` — the explore loop would walk into the refusal | Assigned to P4 (owner of docs; P3 lists skills as P4's): new Step 6d, Files table, pathspec (8 paths), exit criteria. `calculate-assets` builds a test-window store, which nothing pins — left alone |
| 13 | Requirement creep | P4 | P4's handover note / runbook / insight answer R1 and R2 (options, cost, choice, why), and Step 6d serves R1's pin; P4's Satisfies said R3, R4 only | P4 Satisfies is R1, R2 (written half), R3, R4; Requirements table updated (see Decisions D5) |
| 14 | Contract drift (counts) | P1 Verification | Full-suite expectation hard-coded `3249 passed, 411 skipped` | Replaced by "0 failed; baseline + 7, measured on the same machine"; every phase's exit criterion is "the full engine suite passes" (Invariant 1) |
| 15 | Gap (declined) | `engine/src/seer_engine/paper/capital.py:9` | Stale "20,000,000 IDR" comment, noticed by P2 | Not taken: a source comment in `paper/`, named by no requirement or impact point, and P4 edits no source. Left for its own card |

Round 2 (verification), 2026-10-09. Checked against `e5eda52` and against the other plans: every symbol a later
phase uses exists with that signature in an earlier phase's code blocks (`labkit.stamp_provenance(conn, trial_ns, *,
price_fingerprint=LAB_PRICE_FINGERPRINT, initial_idr: Decimal = Decimal("10000000"))` in P2 Step 11, used by P2's own
tests and by P3's three fixture files; `pin_dev_store(conn, price_fingerprint: str | None)` refusing None first;
`plan_capital` called by `seed_preflight` and per chunk); P3's `_run`, `_regime`, `_walkforward` and `fold_record`
replacements diffed against `e5eda52` differ only in the intended lines; P2's tests use nothing P3 adds (its
`test_lab_hardgate.py` edits need only the labkit helper and stamp the funded trials themselves; every other
funded-trial test gets provenance from `run_method`), so P2 is green on its own. No contract moved this round.

| # | Conflict class | Where | Finding | Resolution |
|---|---|---|---|---|
| 16 | Contract drift (docs) | P1 Provides | Said P2 calls `run_registry(initial_idr=runner.recorded_capital(...))` from `real_costs.py`; `real_costs` cannot import `runner`, and `remeasure` uses `plan.initial_idr` / `plan_capital` | P1 Provides rewritten to the real call shapes: `remeasure` via `plan_capital`, `real_costs.measure(initial_idr=...)` resolved in `_costs`, `runner` passing `INITIAL_IDR` explicitly |
| 17 | File collision (line anchors) | P2 Step 10 / Files ↔ P3 Files note | P2 quoted `trial_deposits` as `hardgate.py:183-225`; at `e5eda52` it is :183-227 (45 lines), which is what P3's +10 shift assumes | P2 corrected to :183-227 with the 45 → 55 line count stated |
| 18 | Plan defect (format) | P3 Files table | The post-P2 line-number note was pasted inside the table, splitting it; `test_lab_prereg.py` / `test_lab_status.py` rows sat outside it | Table made whole (5 rows); note moved below it, and it now says P3 Step 1's docstring insert moves every later `hardgate.py` line again |
| 19 | Stale anchor | P4 Step 6c / Files | Handover anchors were off by one (`e5eda52`: :141 `**Hard constraints.**`, :142 `and test-passed…`, :143 blank, :144 `### 5.2`) | Insert after line 143; the step quotes the anchor text |
| 20 | Contract drift (internal) | P4 Interface Contract, Step 6 intro, Rollback | Step 6d (round 1) was not reflected in "Creates", in "see Steps 6a–6c", or in Rollback ("the three docs") | All three name the three skills |
| 21 | Contract drift (verification) | P2 Verification step 3 vs P4 Step 4 | P2 ran `lab costs M0011` with no `--candidate`, which reports the best-by-MAR variant, not necessarily trial #90 | P2 passes `--candidate M0011-RAW20-TV14-N21`, as P4 does |
| 22 | Index | Status line | Still `planned` after round 1 | `reconciled` |

## Decisions

| # | Fork | Choice | Rung |
|---|---|---|---|
| D1 | `ResearchData.price_fingerprint`: P3's `str` property vs P2's `str \| None = None` field | P2's field. A None reaches `trial_provenance` as NULL and every reader treats it as unknown, never a match | plan code blocks (P2 Step 1 defines it; P3 only assumed it) |
| D2 | `pin_dev_store` given None: silent on a lab with no benchmark (P3's "silent when no benchmark") vs refuse | Refuse, checked first, benchmark or not: a trial recorded with NULL prices is refused by the gate forever, and `load_store` always sets the field, so the refusal can only catch a hand-built store | plan code blocks (P3's own `mismatches` docstring: "nobody recorded the prices is not evidence that they match"; D10 "an unknown fails closed") |
| D3 | Fixture stamping: P2's guarded local `_capital` + direct `insert_provenance` vs P3's `labkit.stamp_provenance` with a str capital | One `labkit.stamp_provenance`, created in P2, idempotent, `initial_idr: Decimal = Decimal("10000000")`, price fingerprint `store.P7A_PRICE_FINGERPRINT`. Store-level tests of `insert_provenance` itself still build rows directly | plan code blocks (P2's `insert_provenance` refuses non-`Decimal`; P2's `_capital` was already guarded for exactly this collision) |
| D4 | Seed-path mixed capital: refused per chunk after the store loads (P2 draft) vs in `seed_preflight` before it | `seed_preflight` refuses missing or mixed capital over the whole to-do set; the per-chunk resolution stays as a second refusal | plan code blocks (P2's dev-path `preflight` and its own seed comments: "Refused here, before any store is loaded") |
| D5 | P4 Satisfies R3, R4 only, while its steps answer R1/R2 in writing and fix skill guidance R1's pin would otherwise trip | P4 Satisfies R1, R2 (written half), R3, R4 — moving the handover/runbook answers out of the only docs phase is not possible | plan index Why / Requirements (§5.1: "state the options, measure what each costs, pick, and say why") |
| D6 | Store acquisition in the skills: "build it" (today) vs "pull it" | Pull with `/sync-research-store` first; build only when no copy exists (a refused build records nothing and spends no id); a fundamentals-only refresh stays safe | plan code blocks (P3's `pin_dev_store` refusal: "A store is copied between machines, never rebuilt") |
| D7 | Phase exit counts: hard-coded pass counts vs "suite passes" | "The full engine suite passes", with any count derived per phase from that machine's baseline | stated invariant (Invariant 1) |

## Open Questions

(none)

## Rollback

Per phase: revert the phase's commit, newest first (phase 3 reverts alone; phase 2 needs phase 3
and 4 reverted first; phase 1 needs phase 2 reverted first). Phase 4 is the only one that touches
the committed database; reverting its commit restores the v4 `lab/lab.sqlite`,
`web/data/lab.json`, the three docs and the three skills byte for byte (the migration only added a
table and rows). As a whole: revert the merge.

## Next

    /implement -f TRIAL_REPRODUCIBILITY_PLAN.md --phase 1

Or run the whole set as a swarm:

    /analyze-orchestrator -f TRIAL_REPRODUCIBILITY_PLAN.md
