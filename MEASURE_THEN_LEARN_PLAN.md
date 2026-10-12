# Plan: Fix the measuring tape, then let a tree model rank

**Slug:** measure-then-learn
**Date:** 2026-10-12 20:55 WIB
**Analysis:** `20261012-205553-M7T1_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/measure-then-learn`
**Branch:** `feature/measure-then-learn` (base: `origin/main` @ `5faa3cb`)
**Phases:** 7
**Status:** planned
**Coordinator:** —

---

## Why

The user's request, verbatim:

> Read docs/plans/HANDOVER_20261012-measure-then-learn.md and plan and build its leftover tasks (Step 0 then Step 1).

The handover (`docs/plans/HANDOVER_20261012-measure-then-learn.md`) is the specification. Its core, verbatim:

> - **Step 0 first: fix the measurement flaws** that bias every result, ML included.
> - **Step 1: ML, the tabular kind.** One pre-registered gradient-boosted-tree cross-sectional
>   ranker, not deep learning or RL.
> - **Data:** no new purchase. But the EODHD key expires **2026-11-10**: pull what we still need
>   from it (delisted prices for the survivorship check) before then.

> 1. **Resize band measured against the whole account.** … Fix: make the band relative to the
>    holding's own target (or add a per-method choice) **without changing past results**. Closed
>    records are frozen, so this needs a new rules id or knob, not an edit that rewrites old trials.
>    `RESIZE_BAND` is mirrored in `web/` and asserted by a test, and live paper trading uses the same
>    simulator, so decide explicitly whether paper changes.
> 2. **Interest on idle cash.** … Add a T-bill/cash-rate accrual … Make it a versioned, explicit
>    simulator input.
> 3. **Survivorship check data restored on this machine** … Pull delisted prices from EODHD
>    **before 2026-11-10** and make the check runnable here.
> 4. **Re-price the near misses under the fixed tape**, as new pre-registered variation twins, never
>    by editing old rows: M0030-SAT100 …, M0007-N20-RAW, M0021-B70-RAW, M0020-W-NOSTOP. Also answer
>    Sera's question: were they winning on their picking, or on the equal-weight shape?
> 5. A new method family (e.g. `stock-ml-ranker`), id from `lab next-id`, **committed before
>    `lab run`** … gradient-boosted trees … walk-forward retrains inside the dev window only (ends
>    2015-10-16), with a fixed seed … Target: forward 1-month return rank … Features: only what we
>    already compute … all point-in-time … monthly, top-N long-only, Gotrade fees, fractional shares,
>    the owner's real funding plan … every hyperparameter setting tried counts toward N … **Never
>    touch the test window** while tuning.

> The honest caveat … ML does not change the binding constraint. … Design §1 is not to be bent
> (owner revision only).

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Resize band measured against the holding's own target, past results unchanged, explicit paper/web decision | 1, 3 |
| R2 | Interest on idle cash from the cached T-bill yield, as a versioned explicit simulator input | 2, 3 |
| R3 | Survivorship check runnable on this machine; EODHD top-up before 2026-11-10 | 4 |
| R4 | Near misses re-priced under the fixed tape as new pre-registered twins; "picking or shape?" answered | 5 |
| R5 | One pre-registered gradient-boosted-tree ranker method, run on the dev window | 6, 7 |

## Scope

**In scope:** handover §2 items 1–5.
**Out of scope:** item 6 (a small neural net — conditional on the trees showing something, which
is not known until phase 7 has run); item 7 (daily inference — explicitly "design this only once a
method passes the dev gate"); item 8 (owner-side `/calculate-assets`); the Sera batch that follows
Step 0 (an owner/skill run, not code); any `lab promote` or `lab test` (the test window is never
touched by this set).

## Invariants

1. The tree builds, `ruff check engine` is clean and `pytest engine/tests` passes (with
   `PG_TEST_URL` set; DB tests must not skip) at the end of every phase. Web phases also pass
   `npx tsc --noEmit && npm test` in `web/`.
2. **Closed records are frozen.** Every recorded lab config digest
   (`test_every_recorded_configuration_still_digests_to_its_recorded_digest`), every pinned paper
   spec digest (`tests/test_paper_roster.py` PINS), every backtest registry digest and every
   existing preset's behaviour stay byte-identical. New levers enter `sim.rules.LEVERS_SINCE_PINS`
   at their no-op default. `RESIZE_BAND` keeps its value `Decimal("0.01")`.
3. Live paper trading changes nothing: no `SEED_ROWS` entry changes its rules.
4. Tests never reach production (the autouse fixture stays as is).
5. The test window is never run: no `lab promote`, no `lab test`, no test-store read of a new method.
6. A lab method file is committed before its `lab run`; existing lab rows are never edited;
   `lab stage` after every lab change; commit style `lab: M00NN pre-registered — …` /
   `lab: M00NN rejected (plain reason)`.
7. Owner-facing text (lab notes, insights, site summaries) is plain language: no ids, digests or code.
8. Design §1 is not touched.
9. argparse help strings escape `%` as `%%`.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Resize band relative to the holding's target (`resize_basis` lever) | R1 | `engine/sim` | 7 | — | NORMAL | `.workflows/plan/measure-then-learn/phase-1.md` | P1-ENG-0L6E (done 2026-10-12) | — |
| 2 | Interest on idle cash (`cash_yield` lever) | R2 | `engine/sim`, `engine/backtest`, `engine/paper`, `engine/commands`, `engine/lab`, `engine/tests` | 14 | 1 | HARD | `.workflows/plan/measure-then-learn/phase-2.md` | P1-ENG-0JM2 (done 2026-10-12) | — |
| 3 | Fixed-tape presets and the web mirror | R1, R2 | `engine/sim`, `web/lib` | 11 | 1, 2 | NORMAL | `.workflows/plan/measure-then-learn/phase-3.md` | P1-ENG-03JM | — |
| 4 | Survivorship check runnable here; EODHD top-up | R3 | `engine/commands`, `engine/lab`, skills, runbook, data | 9 | — | NORMAL | `.workflows/plan/measure-then-learn/phase-4.md` | P1-ENG-ESU5 (done 2026-10-12) | — |
| 5 | Near-miss twins under the fixed tape (lab method + run) | R4 | `engine/lab/methods`, `lab/` | 3 | 3, 4 | HARD | `.workflows/plan/measure-then-learn/phase-5.md` | P1-ENG-FON5 | — |
| 6 | Tree-ranker allocator (features, walk-forward model, tests) | R5 | `engine/lab` (`lab/tree_rank.py`) | 2 | — | HARD | `.workflows/plan/measure-then-learn/phase-6.md` | P1-ENG-H3RM | — |
| 7 | Tree-ranker method: pre-register and run on the dev window | R5 | `engine/lab/methods`, `lab/` | 3 | 3, 5, 6 | NORMAL | `.workflows/plan/measure-then-learn/phase-7.md` | P1-ENG-SHJJ | — |

Plan: 7 phases — 49 files across engine sim/backtest/paper/commands/lab, web/lib, skills, a runbook and lab data; levers before presets before runs. R1 -> 1,3 · R2 -> 2,3 · R3 -> 4 · R4 -> 5 · R5 -> 6,7.

Phase 3 serves R1 and R2 together on purpose: a preset that carries both fixes, and the
`RESIZING_RULES` web mirror test that fails the moment any resize preset is added, cannot be split
without leaving one phase red.

Phase 5 → 7 is a true edge: both mint a lab id with `lab idea` at run time and both write
`lab/lab.sqlite` and `web/data/lab.json`, which cannot be merged concurrently. Phase 7 starts only
after phase 5 has landed the set on `main`, run, staged and queued its next idea, so phase 7's id is
the one after both.

### Phase 1 — Resize band relative to the holding's target
**Satisfies:** R1
**Owns:** `sim/rules.py` (new field `resize_basis: Literal["equity","target"] = "equity"`, new
constant `TARGET_RESIZE_BAND = Decimal("0.20")`, `LEVERS_SINCE_PINS["resize_basis"] = "equity"`,
validation, the Rebalance line of `describe_rules` for the target basis); `sim/book.py` (one helper
deciding "is this gap big enough", used at all three sites :561, :617, :654; docstring step 3/4);
`sim/__init__.py` exports; tests.
**Does not touch:** `PRESETS` (phase 3), web (phase 3), cash (phase 2), any existing preset.
**Exit criteria:** with `resize_basis="equity"` every existing test and digest is unchanged; with
`"target"` a holding is traded when `|gap shares| × last ≥ TARGET_RESIZE_BAND × target weight × equity`;
unit tests prove both; full engine suite green.

### Phase 2 — Interest on idle cash
**Satisfies:** R2
**Owns:** `sim/rules.py` (`CASH_YIELD_SERIES = ("T13W",)`; field `cash_yield: str | None = None`,
the last field, after phase 1's `resize_basis`; validation (book engine only, never with
`idle_symbol`); `_V0_LEVERS` 15th element; `LEVERS_SINCE_PINS["cash_yield"] = None`;
`rule_owner_inputs` adds `"cash-yield"`; the "Idle cash" line, index 10, of `describe_rules`);
`sim/__init__.py` export; `sim/book.py` (`accrued_interest`; keywords `cash_rate` and `deposited`
on `step_book`; accrual step 0; `BookStep.interest`); `backtest/book_runner.py` (`cash_rate_on`,
`BookResult.interest_usd`; `run_book` reads the rate point in time and refuses a market without the
series); `backtest/dev.py` docstring; the paper refusal in `paper/book.py` (`decide_book`,
`settle_book`) and `commands/promote.py` (`_check_rules`); `lab/runner.py` (`missing_cash_yield`,
refusal in `preflight_data` and `run_test`); the opt-in smoke fixture `tests/labkit.SMOKE_T13W` and
its use in `tests/test_lab_methods.py`; the golden tests `test_sim_rules.py:416` and
`test_backtest_dev_report.py:567-571` as phase 1 leaves them; `tests/test_cash_yield.py`,
`tests/test_lab_runner.py`.
**Does not touch:** `PRESETS`, web, the resize logic from phase 1 (quotes `sim/book.py` as phase 1
leaves it).
**Exit criteria:** default rules credit nothing (all digests and results unchanged); with
`cash_yield="T13W"`, positive cash at the previous close earns `q(cash × rate/100 × calendar days / 365)`
at the open of S, rate read point-in-time; paper and promote refuse such rules with a plain message;
a cash-yield candidate runs the lab smoke window given `SMOKE_T13W`; suite green.

### Phase 3 — Fixed-tape presets and the web mirror
**Satisfies:** R1, R2
**Owns:** new presets in `sim/rules.py` `PRESETS`: `monthly-hold-frac-gotrade-tband`
(target basis), `monthly-hold-frac-gotrade-tband-cash` (target basis + T13W),
`weekly-hold-frac-gotrade-tband-cash` (weekly, fractional, gotrade, target basis + T13W);
`web/lib/cadence.ts` (`TARGET_RESIZE_BAND = 0.2` mirror, a `TARGET_BAND_RULES` set, `sizeChange`
taking the basis), `web/lib/sean/reminders.ts` `RESIZING_RULES` gains the three ids, their vitest
tests; `web/lib/sean/planData.ts` passes the new required `ReminderInput.resizeBasis` (its only
non-test constructor); `engine/tests/test_sean_mirrors.py` guards the two new mirrors; the
`PRESETS`-enumerating tests (`test_sim_rules.py` id list and owner inputs, `test_lab_costs.py:306`,
`test_cost_model_pins.py:86-90`); new `test_sim_rules_fixed_tape.py`, which also proves promote
refuses the two cash presets.
**Does not touch:** `SEED_ROWS` (paper roster), any existing preset, the simulator logic,
`sim/__init__.py`, `web/app/(app)/positions/page.tsx` (no split-cadence target-basis preset exists,
so its size cell is unaffected).
**Exit criteria:** engine suite and web `tsc` + vitest green; the mirror test covers the new constant
and set; no pinned digest moves.

### Phase 4 — Survivorship check runnable here; EODHD top-up
**Satisfies:** R3
**Owns:** `commands/lab.py` `--sv-store` default honours `$SEER_SV_STORE` (like `--store` honours
`$SEER_RESEARCH_STORE`); `commands/survivorship_store.py` `--out`/`--source`/`--cache` honour
`SEER_SV_STORE`/`SEER_RESEARCH_STORE`/`SEER_EODHD_CACHE`; `lab/survivorship_check.py` refusal text;
`tests/test_sv_store_env.py`; `research.py` stays untouched (the env lookup is inline in the
commands); the explore and sera skills export
`SEER_SV_STORE=/home/miftah/seer/engine/.research-sv`; a runbook note; data operations on the main
checkout: `survivorship_store --fetch-aliases` (EODHD, before 2026-11-10) then `--build` against the
current dev store, and a smoke `lab survivorship` of an existing method from this worktree.
**Does not touch:** the survivorship cleaning rules, `lab/hardgate.py`, the dev store.
**Exit criteria:** from a worktree with `SEER_SV_STORE` set, `lab survivorship <existing method>
--no-journal` runs to a report; the rebuilt sv store's manifest names the current dev store and its
`market_series.csv` (with `T13W`) is byte-identical to the dev store's; coverage before/after
recorded in the runbook; suite green.

### Phase 5 — Near-miss twins under the fixed tape
**Satisfies:** R4
**Owns:** one new lab method file (id from `lab next-id`, `source_kind="variation"`,
`parent_id="M0030"`), its pre-registration commit, `lab run`, `lab survivorship` on it, `lab note`,
`lab insight` answering "picking or shape?", `lab stage`, commits; landing the set on `main` before
`lab run` (Decisions).
**Does not touch:** any existing method file or lab row; the test window; test fixtures (phase 2
owns `SMOKE_T13W`).
**Exit criteria:** the method has dev trials for all its variants, an sv-check observation, a
plain-words note and insight; `lab stage` committed; CI's lab.json/lab.sqlite agreement holds.

### Phase 6 — Tree-ranker allocator
**Satisfies:** R5
**Owns:** the new pure allocator module `engine/src/seer_engine/lab/tree_rank.py` (point-in-time
features from existing feature code, forward-21-session return rank labels, walk-forward annual
refits of a fixed-seed `HistGradientBoostingRegressor`, top-N equal-weight targets; exports
`TREE_RANK`, `TREE_RANK_FUND`, `TreeRankParams`, `TreeRankPrepared.model_on`, `anchor_for`,
`month_ends`, `label_end`, `SCREEN`, `FEATURE_LOOKBACK`) and `engine/tests/test_tree_rank.py`.
**Does not touch:** lab methods, lab data, `strategies/b*.py` (closed Strategy B record, imported
only), `strategies/f_*.py` and `m0007`/`m0015`/`m0070` (imported only).
**Exit criteria:** allocator contract tests (prepared == unprepared, reads only ≤ d), determinism
test (two fits bit-identical), no-lookahead test (labels never extend past d); purity test green.

### Phase 7 — Tree-ranker method: pre-register and run
**Satisfies:** R5
**Owns:** one new lab method file (id from `lab idea` at run time, taken after phase 5's method and
phase 5's queued idea; family `stock-ml-ranker`; rules `monthly-hold-frac-gotrade-tband`; its own
calendar `model_ready` rule, checked against phase 6's `model_on` before the commit),
pre-registration commit, landing on `main`, `lab run --allow-coverage 0.31`, `lab survivorship`,
`lab note`, `lab insight`, `lab stage`, commits.
**Does not touch:** the test window; any existing lab row.
**Exit criteria:** dev trials recorded for every variant; a survivorship observation; note and
insight in plain words; staged and committed.

## Reconciliation Log

| # | Conflict | Class | Resolution |
|---|---|---|---|
| 1 | `test_sim_rules.py:416` (`LEVERS_SINCE_PINS` equality), the `test_backtest_dev_report.py:567-571` `TradeRules(...)` literal, `_V0_LEVERS` and `LEVERS_SINCE_PINS` are edited by phases 1 and 2 | File collision | Phase 1 owns the `resize_basis` edits; phase 2 quotes them as phase 1 leaves them. Fixed phase 2's quote of phase 1's `LEVERS_SINCE_PINS` comment to phase 1's exact text, fixed `CASH_YIELD_SERIES`'s placement to "after phase 1's `TARGET_RESIZE_BAND`", and removed phase 2's "if phase 1 spelled it differently" fork |
| 2 | Phase 1's `test_resize_basis_defaults_to_equity_everywhere` and phase 2's `test_cash_yield_defaults_to_none_and_is_a_pinned_no_op` assert over all of `PRESETS`; phase 3 appends target-basis and cash presets | Broken-build phase (phase 3 red) | Both assertions now cover `PRESETS[:16]`, the presets that predate the levers (phases 1 and 2 edited); phase 3 notes it needs no edit there |
| 3 | Phase 3 vs phase 2 on `test_owner_inputs_of_the_presets`, `test_lab_costs` `PRESETS[-2:]`, `test_preset_ids_are_unique_and_in_order`, `test_cost_model_pins`; phase 2's pin-coverage test; `idle_symbol` with `cash_yield`; `describe_rules` 12 lines with index 7 (phase 1) and 10 (phase 2) | Collision check | Verified consistent: phase 3 is sole editor of those four tests (removed its "if phase 2 generalised it" fork), phase 2's coverage test excludes presets with either lever, all three presets keep `idle_symbol=None`, and both plans keep 12 lines with phase 1 on index 7 and phase 2 on index 10 (checked against `describe_rules` source) |
| 4 | Phase 3 asked whether phase 2's paper/promote refusal fires for the real cash preset ids, and hedged on a refusal inside `rules_for` | Unmet assumption | Phase 2's refusal is in `promote._check_rules` and `paper.book.decide_book`/`settle_book`; added `test_promote_takes_the_band_preset_and_refuses_the_cash_presets` to phase 3's `test_sim_rules_fixed_tape.py`; removed the `rules_for` hedge |
| 5 | `tests/labkit` smoke markets carry no `T13W`; phase 2's `run_book` refuses such a market, so phase 5's `-CASH` variants would fail `test_candidate_runs_a_smoke_window`; phase 5 carried a contingency fixture patch | Gap / unmet assumption | Assigned to phase 2 (new Step 11): opt-in `labkit.SMOKE_T13W`, attached by `test_lab_methods` to any candidate whose rules set `cash_yield`, plus a smoke-market test in `test_cash_yield.py`. Phase 5's contingency, Files row and Requires hedge removed |
| 6 | Phase 5 (and phase 7 via `lab survivorship`) need `T13W` in the rebuilt sv store | Unmet assumption | Phase 4 Step 7.6 now checks `market_series.csv` is byte-identical to the dev store's after the rebuild; added to its exit criteria and Provides line |
| 7 | Phases 5 and 7 both land the set on `main` mid-run, each with an "if the orchestrator forbids it, pause" branch | Contract drift vs Decisions | Already decided (Decisions); removed both pause branches; phase 7 depends on phase 5's landing and takes its id after phase 5's method and queued idea |
| 8 | Phase 7's imports from `seer_engine.lab.tree_rank` vs phase 6's exports; phase 7 defines its own `model_ready` | Contract check | Every imported name and attribute exists in phase 6's module code. Phase 6 exports no calendar-only readiness helper (its `model` counts months with a finite label, which reads data), so `model_ready` stays in phase 7 as planned, with Step 4 proving agreement before the commit |
| 9 | `TARGET_RESIZE_BAND` value | Contract check | Stays 0.20 (Decisions); phase 5 Step 1's guard and its handoff text made consistent with that |
| 10 | Phase 3 makes `ReminderInput.resizeBasis` required | Contract check | `grep` of `web/` finds two constructors only, `lib/sean/planData.ts:187` and the `input()` helper in `reminders.test.ts`; both are in phase 3. `positions/page.tsx` calls `orderSizeChange`/`sizeTip`, whose new `basis` argument defaults to `'equity'` |
| 11 | On a stale survivorship-check store at run time, phase 5 said "stop, never skip the check" and phase 7 said "record that it did not run and add a risk insight" | Contract drift (behavioural fork) | Decided (Decisions): both phases rebuild the sv store offline with phase 4's runbook command and run the check again; a second refusal is a phase 4 defect. Phase 7's exit criterion now requires the observation |
| 12 | Index drifted from the plans: phase 6's module is `lab/tree_rank.py`, not `engine/strategies`; phase 2 also owns `lab/runner.py` and both `paper/book.py` and `commands/promote.py`; file counts were estimates | Index drift | Phase table, Owns, Does-not-touch and exit criteria rewritten from the plans; file counts 7/14/11/9/3/2/3 |
| 13 | Analysis impact point 9 names `research.py` for `SEER_SV_STORE`; reference list names `web/app/(app)/positions/page.tsx:608` | Gap check | Both owned: phase 4 puts the env lookup inline in the commands (no `research.py` change needed); phase 3 owns web and leaves `positions/page.tsx` unchanged on purpose (no split-cadence target-basis preset, so the size cell never meets one). Every other reference-list entry and impact point has an owning phase |
| 14 | Round 2 verification: `SMOKE_T13W` (phase 2 Step 11) vs its users in phases 5 and 7; `tree_rank` names 6→7; preset ids 3→5,7; `SEER_SV_STORE` 4→5,7 | Contract check | All match as named. Phase 2 Step 11 provides `labkit.SMOKE_T13W` and the `test_lab_methods` attach (`Market.with_series` exists in `backtest/market.py`); phase 5 relies on it and patches no fixture; phase 7 uses the non-cash preset so does not need it. Phase 6's contract now names `TreeRankPrepared.inputs` and the history-only `prepare` path, which phase 7 Requires (already in phase 6's code). Index status set to reconciled |

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| How to make the band relative without moving past results | a new lever `resize_basis` ("equity" default, in `LEVERS_SINCE_PINS`) plus `TARGET_RESIZE_BAND = 0.20` of the holding's own target value; `RESIZE_BAND` untouched | 1: invariant 2 (closed records frozen) + handover item 1 ("new rules id or knob") |
| Band size for the target basis | 20% of the holding's target value, no absolute floor (Gotrade's minimum fee is charged by the simulator anyway); fixed before any result | 6: convention (a common tolerance-band width); pre-registered so it cannot be tuned |
| Does live paper change? | No. No roster entry changes rules; the new presets are only available to future `promote` | 1: invariant 3; handover item 1 asks for an explicit decision |
| Cash rate source | the store's existing `T13W` series (EODHD `IRX.INDX`, 13-week T-bill yield), read point-in-time at the previous session; simple ACT/365 accrual on positive cash at the open | 5: handover item 2 ("EODHD yields are cached"); the series is already in the dev store |
| Is idle-cash interest free of owner input? | No: `cash_yield` raises the owner input `cash-yield`, as an unverified idle ETF raises `etf:BIL`; Gotrade paying interest on idle USD (or the owner sweeping into a T-bill fund) is not verified | 6: convention (`rule_owner_inputs`) |
| Paper and cash-yield rules | paper refuses rules with `cash_yield` (no nightly rate feed yet) | 1: invariant 3 |
| How many twin methods for the near misses | one variation method (parent M0030) with up to 6 variants; M0030-SAT100 and M0007-N20-RAW are the same allocator+params (RESIDMOM RAW20), so one twin covers both; costs +1 N, not +4 | 6: convention (lab N policy counts methods) |
| How "picking or shape?" is answered | equal-weight controls of the same size on the same tape inside the same method; a twin's edge over its control is the picking | 5: handover item 4 / insight 211 |
| ML library | scikit-learn `HistGradientBoostingRegressor` (already pinned); no LightGBM | 5: handover ("sklearn HistGradientBoosting, or LightGBM if added") + no new dependency |
| "Every hyperparameter setting counts toward N" | every setting tried is a variant in the committed method file (≤6); no off-book tuning runs on the dev window; the lab's N policy counts the method and the variants enter `var_trials` | 1: invariant 6 + lab N policy |
| Ranker's rules | the target-band preset without cash yield (`monthly-hold-frac-gotrade-tband`), so the ranker carries no owner input and stays gate-eligible | 6: convention |
| Phase 5 found 20% of a 5% slot = the old 1% of equity: the band fix is a no-op for 20-name equal-weight books | keep `TARGET_RESIZE_BAND = 0.20`; the old flaw only bites books of ~25+ names, which is itself the finding; phase 5's hypothesis states it before the run | 5: handover item 1 (relative to the holding's own target) — changing the width after seeing which books it affects would be tuning the tape to the twins |
| Phases 5 and 7 must land the set's code on `main` before `lab run` (a staged DB on main without the method file breaks `test_a_method_that_ran_is_frozen`) | allowed: before each `lab run`, rebase the feature branch onto `origin/main`, verify, and push `HEAD:main`, as the explore skill already pushes every pre-registration | 6: convention (CLAUDE.md "commit and push to main once verified"; explore skill) |
| Ranker's fundamentals variant vs the coverage gate (fundamentals start 2009; coverage 0.315) | phase 7 runs with `--allow-coverage 0.31` stated in the hypothesis; one fundamentals variant only | 5: handover item 5 lists SEC fundamentals as a feature; the gate is honoured explicitly, not bypassed silently |
| Ranker control | a signal-free dollar-volume book of identical shape, not 12-1 momentum (a momentum variant would make every variant behavioural kin of test-failed books) | 6: convention (hardgate D14) |
| Lab DB the runs write | the shared main-checkout DB and stores via `SEER_LAB_DB` / `SEER_RESEARCH_STORE` / `SEER_SV_STORE`, exactly as the explore skill does | 6: convention (explore skill) |
| A stale survivorship-check store when phase 5 or 7 runs `lab survivorship` (phase 5: stop; phase 7: skip and record) | rebuild it offline with phase 4's runbook command (`survivorship_store --build`, atomic swap, backup outside the repo) and run the check again; never skip it; a second refusal is a phase 4 defect | 2: phase 5's exit criterion requires the sv-check observation; settled by 4: R3 and insight 208 (the promised check that was skipped) |
| Where the smoke market gets its `T13W` series | an opt-in `labkit.SMOKE_T13W` that `test_lab_methods` attaches only to candidates whose rules set `cash_yield`, owned by phase 2; the shared smoke markets keep `EMPTY_SERIES` | 3: the plans' code blocks (phase 2's runner test asserts the smoke `data` fixture has no `T13W`) and the existing `test_market_series` pin on `EMPTY_SERIES` |

## Open Questions

(none)

## Rollback

- Phases 1–3: revert the commits; the new levers default to no-ops, so nothing recorded depends on them until phase 5 runs.
- Phase 4: revert the env fallback; the old sv store can be rebuilt with the same command.
- Phases 5, 7: lab rows are append-only by design; a mistaken run is recorded as is and explained in a note, never deleted.
- Whole set: do not merge `feature/measure-then-learn`; lab rows already written to the shared DB stay (append-only) and must be explained in a note.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f MEASURE_THEN_LEARN_PLAN.md --phase 1

Or run the whole set as a swarm:

    /analyze-orchestrator -f MEASURE_THEN_LEARN_PLAN.md
