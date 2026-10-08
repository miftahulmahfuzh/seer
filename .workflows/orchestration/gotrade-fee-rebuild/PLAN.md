# Plan: rebuild the roster to pay Gotrade's real fees

**Slug:** `gotrade-fee-rebuild`
**Date:** 2026-10-08 09:13 WIB
**Analysis:** `20261008-091321-H3M8_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/gotrade-fee-rebuild`
**Branch:** `feature/gotrade-fee-rebuild` (base: `origin/main` @ `485d416`)
**Phases:** 12
**Status:** reconciled
**Coordinator:** —

---

## Why

The user's rationale, verbatim from the `/analyze` invocation:

> The thread running through all of it: Sean measured Gotrade real fees from the owner receipts and
> they are ~2.5x the 0.1%/side every lab trial assumed, and ~5.2x at the owner current $28 slots
> because of a $0.10 per-order floor. The roster has to be rebuilt to pay them.
>
> Four things that shape the work and are easy to miss:
>
> 1. PAPER IS PAUSED (PAPER_PAUSED true in .github/workflows/nightly.yml, commit d44fa78) and the
>    paper clock is frozen at ZERO stepped sessions. There is therefore NO deadline — the rebuild
>    stays free indefinitely. Optimise for getting it right once, not for speed. The resume
>    conditions are written above the switch in that file; do not resume until they hold.
>
> 2. C STAYS ON THE ROSTER PERMANENTLY. The owner requires a daily-trading method as the measured
>    counterfactual for the daily-trading plan he originally wanted. Never propose retiring it on
>    cost grounds — being expensive is the finding it exists to produce. That makes a gotrade branch
>    in the bracket path (sim/lifecycle.py, sim/sizing.py) a hard dependency, not an option.
>
> 3. Q3 and Q9 share a foundation and should be sequenced together. The owner adds 5,000,000 IDR
>    every month to a 10,000,000 IDR start, and NOTHING in the system models contributions — paper
>    cannot even accept a deposit. A recurring contribution schedule would serve both the lab model
>    (Q3) and Sean execution reminders (Q9). Q3 likely deserves its own plan set; it drags in
>    money-weighted returns and a dollar-cost-averaged SPY, because CAGR and beats-SPY-TR stop
>    meaning anything once deposits exist.
>
> 4. Q9 is small, high value, and mostly already built — extend web/lib/sean/reminders.ts rather than
>    rebuilding it. The only missing input is the owner cash balance.
>
> Also: main is RED for two unrelated reasons described in section 6 — expect that and do not chase
> it as something you broke.
>
> The owner is not a quant: prose stays plain, numbers carry their meaning. He prefers measuring to
> estimating — every figure in the handover was measured and yours should be too.

And the owner's own standing instruction, relayed 2026-10-08 and recorded in the handover §3b:

> *"we must always include a daily trading method like C in the roster because I want to see how bad
> it got if I had used daily trading on Gotrade like my initial plan"*

The specification is `docs/handover/2026-10-08-sean-shipped-red-main-and-the-vanishing-picks.md`
@ `485d416`. Its §8 is the nine questions; §10 is how every number in it was verified. Claims marked
**CORRECTED** there are not to be re-derived.

## Requirements

Final after reconciliation. Where a phase appears twice, the second is the phase that owns the
**production call site** — the wire that turns the first phase's capability on (Decision D10).

| ID | What the user asked for | Phases |
|---|---|---|
| R1 (Q1) | Rebuild the roster so **every** entry pays Gotrade's measured fees, SPY included — as new entries with fresh paper clocks | 3 (the benchmark's fee lever), 12 (the roster, and the wire that tells the live benchmark which model to pay) |
| R2 (Q2) | Decide how many names a monthly book holds **on the merits**, not on fee grounds — measured in the lab | 8 |
| R3 (Q3) | Measure what the owner will actually do: 10,000,000 IDR start, +5,000,000 IDR on the 25th of each month — contributions in backtest and paper, a money-weighted return, a dollar-cost-averaged SPY, every CAGR-phrased gate restated | 5 (the schedule + both backtest runners), 6 (paper's deposit, and paper's comparison), 7 (the money-weighted return + the DCA SPY), 12 (the wire: the night accrues and credits; the replay reconstructs it) |
| R4 (Q4) | Make the bracket path pay Gotrade's fees so the daily control C is honest. C **stays** permanently | 4 (the capability), 12 (the wire: the nightly job passes each entry's own rules) |
| R5 (Q5) | The blank pending-picks panel must say which of its five causes it is, and never read as a live instruction | 9 |
| R6 (Q6) | Narrow the CI skip-guard; put `COMMITTED_DEV_TRIALS` in a form that cannot age again | 1 |
| R7 (Q7) | Settle how a test-window look relates to the luck gate; make snapshot, pages and test agree | 2 |
| R8 (Q8) | One daily line: session stepped y/n, picks published y/n, CI green y/n, paper paused y/n | 11 |
| R9 (Q9) | The owner executes a rotation without arithmetic — Sean sizes buys from **cash** | 10 |

Every `R` is owned, and no phase does work outside its own `Satisfies` line. Phase 12's line widened
from `R1` to `R1, R4, R3` because the **steps** moved there under D10, not to legalise anything it
was already doing.

## Scope

**In scope.** All nine questions of handover §8. The three resume conditions written above
`PAPER_PAUSED` in `.github/workflows/nightly.yml`. The two causes of red `main` (§6a, §6b). The
contribution model in full — schedule, backtest, paper, money-weighted return and dollar-cost-averaged
benchmark together, because a half-built one is worse than none (see Decisions, D4).

**Out of scope, and why:**

- **Resuming paper.** No phase flips `PAPER_PAUSED`. See Decisions, D1.
- **Re-fitting `sim/costs.py`.** The schedule is validated against the owner's real receipts to the
  cent on both sides (analysis, *Measured Evidence*). It is not touched.
- **The orphaned nightly run `37655513074`.** Settled in handover §6c: it is stuck before job
  creation, outside the concurrency group's pending queue, and cannot delay a future nightly. No
  phase spends time on it.
- **Retiring C, or any proposal to.** Standing owner requirement. Being expensive is the finding it
  exists to produce.
- **Changing the name count on fee grounds.** Forbidden by handover §2b CORRECTED. Phase 8 measures
  the merits question; the rebuilt roster carries N = 20 regardless (Decisions, D3).

## Invariants

Every phase must hold all of these. They are checkable, not aspirational.

1. **The tree builds and both suites pass at the end of each phase.** Engine:
   `PYTHONPATH=engine/src PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres python -m pytest engine/tests -q -n auto`
   — `PYTHONPATH` is **required**: without it pytest silently tests the main checkout instead of this
   branch. Never pass `-o addopts`. Web: `cd web && npx vitest run` and `npx tsc --noEmit`.
2. **`PAPER_PAUSED` stays `'true'`.** No phase flips the switch. Phase 12 may only rewrite the
   comment above it to say what now holds.
3. **No started roster entry is edited.** `docs/runbooks/paper-trading.md:60-68` and
   `store.check_digest`. Roster change lands as new entries with new ids and fresh clocks.
4. **C stays on the roster.** No phase retires it, marks it retired, or recommends retiring it.
5. **`engine/src/seer_engine/sim/costs.py` is not modified.** It is a model validated against live
   money; changing it invalidates every figure in this plan set.
6. **Every number written into code, a comment, a doc or a commit message is measured**, with the
   command or call that measured it recoverable. No estimates presented as figures.
7. **Prose the owner reads stays plain.** Numbers carry their meaning; no jargon without a gloss;
   times stated in WIB beside UTC.
8. **No phase changes a pinned spec digest of a *started* entry.** New presets and new entries are
   fine; moving an existing live entry's digest fails the next paper night.

## Phases

Every **Files** count below was verified by the reconciler against the phase's own Files table, not
carried over from the draft.

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | The CI guard catches what it was written for | R6 | `.github`, `engine/tests`, `engine.lab` | 3 | — | NORMAL | `.workflows/plan/gotrade-fee-rebuild/phase-1.md` | — | — |
| 2 | A test-window look is not luck-gated, and says so | R7 | `engine.lab`, `web/lib/sera`, `web/app/sera` | 13 | — | HARD | `.workflows/plan/gotrade-fee-rebuild/phase-2.md` | — | — |
| 3 | The live SPY benchmark pays what the methods pay | R1 | `engine.paper` | 2 | — | NORMAL | `.workflows/plan/gotrade-fee-rebuild/phase-3.md` | — | — |
| 4 | The bracket path can express and charge Gotrade's fees | R4 | `engine.sim`, `engine.paper` | 13 | — | HARD | `.workflows/plan/gotrade-fee-rebuild/phase-4.md` | — | — |
| 5 | A contribution schedule, and the lab's real capital | R3 | `engine.sim`, `engine.backtest` | 11 | 4 | HARD | `.workflows/plan/gotrade-fee-rebuild/phase-5.md` | — | — |
| 6 | Paper accepts a deposit | R3 | `engine.paper`, `engine.commands`, `db` | 7 | 5 | HARD | `.workflows/plan/gotrade-fee-rebuild/phase-6.md` | — | — |
| 7 | Money-weighted return, and a SPY fed the same money | R3 | `engine.backtest`, `engine.lab` | 7 | 2, 5 | HARD | `.workflows/plan/gotrade-fee-rebuild/phase-7.md` | — | — |
| 8 | How many names, measured at real fees and real funding | R2 | `engine.lab`, `engine.commands`, `docs` | 5 | 7 | NORMAL | `.workflows/plan/gotrade-fee-rebuild/phase-8.md` | — | — |
| 9 | The blank panel says which of five things it means | R5 | `web/app/(app)`, `web/lib` | 8 | — | NORMAL | `.workflows/plan/gotrade-fee-rebuild/phase-9.md` | — | — |
| 10 | Sean sizes a rotation from cash, not from holdings | R9 | `web/lib/sean`, `web/app/sean` | 8 | 5 | NORMAL | `.workflows/plan/gotrade-fee-rebuild/phase-10.md` | — | — |
| 11 | One daily line: stepped, published, green, paused | R8 | `.github`, `docs` | 2 | — | NORMAL | `.workflows/plan/gotrade-fee-rebuild/phase-11.md` | — | — |
| 12 | The rebuilt roster, and the wiring layer | R1, R4, R3 | `engine.paper`, `engine.commands`, `db`, `docs`, `.github` | 10 | 3, 4, 6, 7 | HARD | `.workflows/plan/gotrade-fee-rebuild/phase-12.md` | — | — |

**Waves** (what `/analyze-orchestrator` will run concurrently):
W1 = 1, 2, 3, 4, 9, 11 · W2 = 5 · W3 = 6, 7, 10 · W4 = 8, 12

### Phase 1 — The CI guard catches what it was written for
**Satisfies:** R6
**Owns:** `.github/workflows/engine-ci.yml` (the `^SKIPPED` guard at :70);
`engine/tests/test_lab_npolicy.py` (the four `COMMITTED_*` constants);
`engine/src/seer_engine/lab/npolicy.py` — **comment-only**, assigned by D11: `:17` 110 → 126, `:21`
23 → 28, `:99-100` `ceil(2.44) = 3 against 23 methods` → `ceil(2.34) = 3 against 28 methods`. `:23`'s
"2 on the committed database" is still true and stays.
**Does not touch:** any other workflow, any other engine source file, `lab/lab.sqlite`,
`lab/store.py` (phases 2 and 7).
**Exit criteria:** the guard fails on `conftest._SKIP_REASON`'s own signature and passes over all
nine deliberate `skipif` sites; the pinned-evidence test asserts against the committed database
rather than skipping. **Measured input: the lab holds 126 dev + 2 test = 128 rows, and
`COMMITTED_DEV_TRIALS` is compared against `store.dev_trial_count`, which counts dev only — so the
number is 126, not the 128 the handover names.** The engine suite reports `0 failed`. And
`grep -n '110 on the committed\|23 on the committed\|ceil(2.44)' engine/src/seer_engine/lab/npolicy.py`
returns nothing, with every changed line in that file inside a docstring (D11).

### Phase 2 — A test-window look is not luck-gated, and says so
**Satisfies:** R7
**Owns:** `engine/src/seer_engine/lab/store.py` (`luck_gated()` at :1272, `SNAPSHOT_VERSION` 3→4 at
:1687, the `"luckGated"` key at :1791 — **and nothing else in that file**); `web/lib/sera/types.ts`,
`derive.ts`, `fixture.ts`, `lab.test.ts`, `derive.test.ts`; `web/app/sera/methods/view.ts`,
`view.test.ts`, `[id]/page.tsx`, `page.tsx`; `web/app/sera/overview.test.ts`; `web/data/lab.json`
(regenerated); `engine/tests/test_lab_snapshot.py` — **the `TRIAL_KEYS` set, the int `s["version"]`
pin at :280, and two new tests only**.
**Does not touch:** `published_verdict` / `verdict` / `dsr_at` — the engine's dev/test rule is
already correct and is the thing being published, not changed. Nothing under `web/app/(app)`.
**And not `SCHEMA_VERSION`:** the six `store.schema_version(...) == "3"` pins in
`test_lab_snapshot.py` (:86, :104, :113, :180, :207, :238) are the **sqlite schema** version, a
string, and belong to phase 7. This phase moves only the published-snapshot version, an int. Two
numbers, same file, both reading "3 to 4" — see Decision D14.
**Exit criteria:** `web/lib/sera/lab.test.ts` passes (today: 1 failed, 9 passed); a test-window row
renders "not applicable" rather than a green tick, and does not print `at N 126` beside a score that
was never computed at N; the marker is read by the test rather than re-derived.

### Phase 3 — The live SPY benchmark pays what the methods pay
**Satisfies:** R1
**Owns:** `engine/src/seer_engine/paper/benchmark.py`; `engine/tests/test_paper_benchmark.py`.
**Does not touch:** `backtest/benchmark.py` — it **already** carries a working `cost_model`
parameter on `_whole_shares:109`, `_fractional_shares:121`, `fractional_buy_cost:135` and
`_whole_buy_cost:143`. This phase passes the lever, it does not build it. Nothing in `sim/`.
**And neither `commands/paper.py` nor `paper/store.py`:** this phase's H1 wiring (`load_benchmark`'s
`cost_model` keyword and `_step_benchmark`'s call) is phase 12's, under D10. The capability lands
inert here — keyword-only, defaulted `"flat"` — and phase 12 turns it on.
**Exit criteria:** all **three** flat sites take the cost model — `:170` (the recorded `Fill.cost_usd`,
which the handover does not name), `:249-250` (the entry buy) and `:276-279` (the reinvestment buy) —
and the recorded fee equals the cash actually moved. `BenchmarkState` carries the model so it
survives between nights. This is **resume condition 1** of three.

### Phase 4 — The bracket path can express and charge Gotrade's fees
**Satisfies:** R4
**Owns:** `engine/src/seer_engine/sim/rules.py`, `model.py`, `sizing.py`, `lifecycle.py`,
`split_adjust.py`, `__init__.py`, and the **new** `sim/charges.py`;
`engine/src/seer_engine/paper/bracket.py`; the matching tests.
**Does not touch:** `sim/book.py` (already complies), `sim/costs.py` (invariant 5),
`paper/benchmark.py` (phase 3), `paper/roster.py` (phase 12). It does **not** add a roster entry —
it makes one expressible. **And not `commands/paper.py`, `commands/promote.py` or
`backtest/runner.py`:** the four `rules=e.rules` call sites and `promote`'s `is_bracket` dispatch
are phase 12's under D10 (this planner's Steps 10 and 11, moved intact to phase 12's Step 7a);
`run_backtest`'s own `rules` keyword is phase 5's. Every parameter this phase adds is keyword-only
with `DESIGN_V0` as its default, which is what makes the tree green with the wiring absent.
**Exit criteria:** `git diff --stat` shows **no file under `commands/`** and no change to
`backtest/runner.py`. A bracket rule set with `cost_model="gotrade"` constructs without raising, and a
bracket fill charges Gotrade's schedule including the $0.10 floor. **Three measured blockers, in the
order they are hit — the handover names only the third:** (a) `_ENGINES = ("bracket_v0", "book")`
has no non-v0 bracket engine; (b) `rules.py:136` reserves `bracket_v0` for `DESIGN_V0` by comparing
*every* field against `_V0_LEVERS`, so any bracket rule set differing in any field is refused at
construction; (c) `size_picks` and `step` take **no `rules` argument at all** and call
`sim.model.buy_cost` / `sell_proceeds`, which multiply the module-level `COST_RATE`, with
`sizing.py:31` precomputing `_ONE_PLUS_COST` at import. This is a signature change across the
bracket path, not a branch inside it. `DESIGN_V0` itself must still construct and still digest
identically. This is **resume condition 2** of three.

### Phase 5 — A contribution schedule, and the lab's real capital
**Satisfies:** R3
**Owns:** `engine/src/seer_engine/sim/contributions.py` (**new**: the schedule as a pure value
object — `ContributionSchedule(amount_idr, day_of_month=25)`, `OWNER_MONTHLY`, `dates_in`, `due`,
`usd_at`, `credit_usd`, `MAX_DAY_OF_MONTH`, and — added in round 2 under D18 — the alias
`Contributions` and the function `credit_for`, which let a runner be funded by a **record** of
deposits already made as well as by the **plan**); `engine/src/seer_engine/backtest/runner.py`
(`INITIAL_IDR`, the session loop, **and its `rules` keyword — phase 4's H1, assigned here**);
`engine/src/seer_engine/backtest/book_runner.py` (**and its `is_bracket` dispatch at :380 and
`order_fee` at :521-522 — phase 4's H1/H2**); `engine/tests/test_sim_contributions.py` (**new**),
`test_backtest_runner.py`; and the five test files the draft index claimed for nobody —
`test_book_runner.py`, `test_backtest_report.py`, `test_backtest_b_report.py`,
`test_backtest_wf_report.py`, `test_backtest_labels.py` (moving `INITIAL_IDR` breaks 10 tests across
them); `engine/package_readme.md`'s `sim/` tree line, `backtest.runner` bullet and `run_book`
signature.
**Does not touch:** `paper/` (phase 6), `metrics.py` / `benchmark.py` / `dev.py` (phase 7),
`web/` (phase 10), `sim/__init__.py` (phase 4 — `sim.contributions` is imported by module path, as
`sim.costs` already is).
**Exit criteria:** `+5,000,000 IDR on the 25th of each month` is expressible as a value object and
honoured by both backtest runners; `INITIAL_IDR` is the real 10,000,000 IDR. **The schedule deposits
on a calendar date and lets the NYSE calendar produce the lag** — measured, the gap from the 25th to
the next month's first session is a mean of 7.0 days ranging 4 to 10, so a baked-in 7-day lag is
wrong in ten months of twelve. **Why `INITIAL_IDR` must move:** `paper/capital.py:11` already holds
the real `PAPER_INITIAL_IDR = 10000000` and its comment justifies the 20M lab figure as "closed
records, where only percentages matter" — true under a flat percentage fee, false under Gotrade's
$0.10 floor, where a 20M book pays 0.737% and a 10M book pays 1.035% on the same strategy. **Also:**
`run_backtest(..., rules=DESIGN_V0_GOTRADE)` runs and ends with strictly less equity than the same
run at `DESIGN_V0`, and `run_rules` sends a `"bracket"` rule set to `run_backtest` rather than to
`step_book` — without which phase 12's `seer paper check` would replay C-GT at the flat rate.

### Phase 6 — Paper accepts a deposit
**Satisfies:** R3
**Owns:** `db/migrations/016_contributions.sql` (**this number, not another**);
`engine/src/seer_engine/paper/store.py` (a deposit path beside the write-once `initial_cash_usd`);
`engine/src/seer_engine/paper/book.py`; `engine/tests/test_paper_store.py`, `test_paper_book.py`;
and — assigned by the reconciler, Decision **D12** — `engine/src/seer_engine/paper/compare.py` plus
its impure edge `engine/src/seer_engine/commands/compare.py`, so a deposit is not read as a return
on the paper comparison.
**Does not touch:** `paper/roster.py` and `db/migrations/017_*` (phase 12), `paper/benchmark.py`
(phase 3), `paper/bracket.py` (phase 4), and **`paper/store.py:1127-1145` (`load_benchmark`)**,
which is phase 12's single hunk in this phase's file (D10 + D13). The two regions are line-disjoint
and phase 6 lands first.
**Exit criteria:** paper can record money arriving and apply it on its session. Today it cannot:
`initial_cash_usd` is written once at `store.py:417` and the only later UPDATE (`:449`) writes
`cash_usd`, `equity_usd` and `last_session`. Deposits reach every engine — the four quant books, C
and SPY — because the gap is below all of them, not per-method. A deposit landing between sessions
raises cash on its session and is **not** counted as a return. **A credit raises CASH AND EQUITY by
the same amount, and this is asserted, not assumed:** both engines size from the last snapshot's
equity (`sim/sizing.py:137` `slot_budget = q(portfolio.equity / SLOTS)`, `sim/book.py:536`
`equity = book.equity`), so crediting cash alone would leave every deposit permanently
under-deployed. `paper.book.deposit_book` does both; phase 12's two one-line adapters for
`sim.Portfolio` and `BenchmarkState` must match it. And `paper.compare._returns` removes the
session's deposit before taking the ratio, so a book that earns nothing and is handed $312.50
reports 0%, not +31% (D12).

### Phase 7 — Money-weighted return, and a SPY fed the same money
**Satisfies:** R3
**Owns:** `engine/src/seer_engine/backtest/metrics.py`; `backtest/benchmark.py` (the schedule reaches
`buy_and_hold` / `spy_curves`); `backtest/dev.py` (the gate restated);
`engine/src/seer_engine/lab/store.py` (the trial schema and `owner_failures`);
`engine/tests/test_backtest_metrics.py`, `test_backtest_benchmark.py`.
It also owns, by the reconciler's assignment: **`dev.run_registry` / `dev._run`'s `contributions`
keyword**, without which phase 8's sweep cannot run and the DCA SPY of this phase's own Step 10 is
unreachable; and `dev.py:185,:206,:223`'s `is_bracket` dispatch (phase 4's H3). Plus
`engine/tests/test_lab_snapshot.py`'s six **`SCHEMA_VERSION`** pins and the new v3→v4 migration test.
**Does not touch:** `runner.py` / `book_runner.py` / `contributions.py` (phase 5's, quoted as phase 5
leaves them), `commands/lab.py` (phase 8's alone), `paper/*` (phases 3, 6, 12), `_snapshot_trial` or
`TRIAL_KEYS` (phase 2's — the side table is why neither needs to move).
**Phase 2 also edits `lab/store.py`** — quote that file as phase 2 leaves it, and **locate the hunks
below `:1272` by symbol, not by line**: phase 2's `luck_gated()` insert shifts everything under it by
about +22 lines.
**Exit criteria:** a contribution-fed book reports a **money-weighted** return beside its CAGR, and
every gate phrased in CAGR terms is restated in it; SPY is dollar-cost-averaged on the **identical**
schedule, so "beats SPY TR" compares two books holding the same money at the same times. Without
this, contributions make every CAGR in the system a flattering lie — which is why phases 5, 6 and 7
ship as one unit (Decisions, D4).

### Phase 8 — How many names, measured at real fees and real funding
**Satisfies:** R2
**Owns:** `engine/src/seer_engine/lab/name_count.py` (**new** — the sweep as a report-only module,
not as registered lab variants, so the lab's N does not move); three additive hunks in
`engine/src/seer_engine/commands/lab.py` (**sole owner — phase 7 does not touch that file**);
`engine/tests/test_lab_name_count.py`; the measured answer written into `docs/backtests/` with its
CSV.
**Does not touch:** `paper/roster.py` — whatever this phase measures, the rebuilt roster still
carries N = 20 (Decisions, D3). It does not promote anything. `lab/lab.sqlite` is **not written**, so
`web/data/lab.json` does not go stale.
**Borrows three names, all now read off the landed plans rather than guessed:** phase 5's
`sim.contributions.OWNER_MONTHLY`, phase 7's `dev.run_registry(contributions=…)` keyword, and phase
7's `backtest.metrics.Metrics.mwr` field (D15).
**Exit criteria:** a measured comparison of name counts over the lab's window with `cost_model="gotrade"`
**and** the real contribution schedule both switched on, because the fee floor is size-dependent and
the two interact. The answer is written down in plain prose with the command that produced it.
**The fee argument is already settled and must not be re-run as the finding:** measured, by month 3
of the funding plan 20 names costs 0.614% and 11 names costs 0.612%. The merits question is whether
concentration helps or hurts the returns, not the fees. Calibration point from live money: the
owner's own 20 buys cost **$2.60 to deploy $558 — 0.47% before a single round trip**.

### Phase 9 — The blank panel says which of five things it means
**Satisfies:** R5
**Owns:** `web/lib/decision.ts` (**new** — the classifier, pure and tested) and
`web/lib/decision.test.ts`; `web/lib/session.ts` and `session.test.ts`;
`web/app/(app)/positions/page.tsx`; `web/app/(app)/page.tsx`; the two CSS modules.
**Does not touch:** anything under `web/app/sera` or `web/lib/sera` (phase 2), `web/lib/sean` or
`web/app/sean` (phase 10 — Sean is a **sibling** of `(app)`, not a child, so the two phases share no
directory at all), `web/lib/data.ts`'s query shape, `web/lib/format.ts` (nobody edits it — phase 10
imports the `signedUsd` that is already there), `.github/workflows/nightly.yml` (read-only, by a
test).
**Exit criteria:** the five states are distinguished in plain words — **(a) holding, nothing was due**
(the common case: roughly three weeks in four, and the state all four quant entries are in until
2026-11-02), (b) expired at the New York close, (c) never produced, (d) failed, and **(e) paper is
paused**, which is true today and which nothing in the UI says. The next decision's time is stated in
**WIB**. Nothing rendered is mistakable for a live instruction. The cadence vocabulary in
`web/lib/cadence.ts` and `positions/page.tsx`'s `noOrders()` / `emptyState()` is reused, not
duplicated. **And a sixth input the reconciler added (D16): a RETIRED strategy's pending decision
never renders as a live instruction** — `panelState(..., retired)` returns `spent` whatever the
session date says, and the panel says the strategy has been replaced. Phase 12 retires six entries
whose 80 `book_targets` rows and 4 `orders` dated 2026-10-07 still carry `pending_decision = true`
and are deliberately not deleted (invariant 3); this phase is in wave 1 and so handles retirement
generically, which is also correct for the four entries already retired today. **The flag is
defaulted but not optional at the call site:** `positions/page.tsx` passes
`strat?.status === 'retired'`, and an exit criterion greps for it — round 2 found the classifier
correct and the one production call still passing three arguments, which would have left D16 green
in its unit tests and absent from the page.

### Phase 10 — Sean sizes a rotation from cash, not from holdings
**Satisfies:** R9
**Owns:** `web/lib/sean/reminders.ts` and `reminders.test.ts`; `web/lib/sean/cash.ts` (**new**) and
`cash.test.ts`; `web/lib/sean/planData.ts` (claimed by no other phase — the wiring between `cash.ts`
and `buildReminders`); the Sean plan surface under `web/app/sean/plan/` (`view.ts`, `view.test.ts`,
`page.tsx`).
**Does not touch:** `web/lib/sean/ledger.ts`'s contract — cash is **derived** from the schedule and
the ledger, never read from a receipt, because receipts never show a balance. `web/lib/format.ts` —
`signedUsd` is **imported** from `format.ts:8`, not added; no phase edits that file. Nothing under
`web/app/(app)` at all (phase 9). No migration and no schema change: 016 is phase 6's and 017 is
phase 12's.
**Exit criteria:** `planSize` becomes holdings value **+ cash**, cash derived as deposits − net buys
+ net sells; `sean_link.budget_usd` survives as a manual override. **Extend this module, do not
rebuild it** — sells already render before buys, a dropped pick already produces a whole-position
sell, a new pick already produces a dollar-denominated buy, and screenshots already tick reminders
off. Three sub-decisions, settled: `MIN_TRADE_USD` is re-tuned against the measured fee curve (at $10
a corrective trade pays **2.5% round trip**; $25 pays 1.08%; $50 pays 0.62%); orders stay
dollar-denominated, never share counts; and settlement is **not a blocker** — the deposit lands on the
25th, settled cash a week before a month-start rotation, so the list must work whether or not
same-day reuse is permitted, treating it as a bonus.

### Phase 11 — One daily line: stepped, published, green, paused
**Satisfies:** R8
**Owns:** a new `.github/workflows/watch.yml`; a new `docs/runbooks/monitoring.md`.
**Does not touch:** `nightly.yml` (phase 12 owns its comment; this phase only `sed`s the
`PAPER_PAUSED` value out of it), any engine or web source, `engine-ci.yml` (phase 1 — this phase
reports CI's colour, it does not fix it), `docs/runbooks/paper-trading.md` (phase 12).
**Exit criteria:** one line a day reaches the owner carrying four facts — session stepped y/n, picks
published y/n, CI green y/n, paper paused y/n. **It must live outside `nightly.yml`**, because a step
inside the nightly structurally cannot report *"the nightly did not run"*. Times in WIB beside UTC.
It must not call a permanently-queued orphan run "running" (handover §6c). Its words for the two
states phase 9 also renders are **`none due`** and **`PAUSED`**, which is the vocabulary both
surfaces keep (D17).

### Phase 12 — The rebuilt roster, and the wiring layer
**Satisfies:** R1, and the production call sites of R4 and R3 (D10 — the capabilities stay with
phases 4, 6 and 7; the wires that turn them on are here)
**Owns, the roster proper:** `engine/src/seer_engine/paper/roster.py` (the successor `SEED_ROWS`
entries, `OWNER_FUNDING`, `BENCHMARK_COST_MODEL`, `PRE_FUNDING_IDS`);
`db/migrations/017_roster_real_fees.sql` (**this number**; phase 6 holds 016);
`engine/tests/test_paper_roster.py`; `docs/runbooks/paper-trading.md`;
`.github/workflows/nightly.yml` (**the comment block at :46-69 only — the `PAPER_PAUSED:` line keeps
its exact text, because phase 9's drift test and phase 11's `sed` both parse it**).

**Owns, the wiring layer** — assigned by Decision **D10** after three planners found these unowned,
extended by the reconciler to two more files for the same reason (D13):

| file | the wire | specified by |
|---|---|---|
| `engine/src/seer_engine/commands/paper.py` | four `rules=e.rules`; `_step_benchmark`'s cost model; `accrue_contributions` + `apply_contributions` + the three engines' deposits | phases 4, 3, 6 |
| `engine/src/seer_engine/commands/promote.py` | `:275` dispatches on `is_bracket` | phase 4 |
| `engine/src/seer_engine/paper/store.py` | **`load_benchmark` at `:1127-1145` only** — a keyword-only `cost_model` | phase 3 |
| `engine/src/seer_engine/paper/replay.py` | `:290` stops hard-coding `DESIGN_V0`; the three `expected_*` builders take the stored contributions — the **dated, already-converted rows**, never the schedule (D18) | phases 4, 6 |
| `engine/src/seer_engine/commands/paper_check.py` | `:200`'s `"initial_cash"` relabelled, `"deposited"` published beside it | phase 6 |

Phases 3, 4 and 6 each build a capability whose only production call site lives in these files, and
each states its required change as a handoff rather than editing the file; **read all three plan
files' Handoffs sections and apply every one**. Until this phase runs, the capabilities are complete,
tested and **inert** — which is safe only because every signature those phases add is
keyword-with-default and because the paper clock is frozen at zero stepped sessions. Specifically:
`paper/replay.py:290` hard-codes `DESIGN_V0`, so without this `seer paper check` would replay a
Gotrade C at the flat rate; `store.load_benchmark` would rebuild `BenchmarkState` at the `"flat"`
default, so the Gotrade SPY entry would still step at 0.1%; and nothing would call phase 6's deposit
path, so the successor entries would **not** carry the funding plan from their first night, which is
exactly the condition that would force a second rebuild.
**Does not touch:** `PAPER_PAUSED`'s value (invariant 2). It does not retire C (invariant 4). It does
not edit any started entry (invariant 3). It does not touch `paper/compare.py` (phase 6, D12),
`paper/book.py` or the rest of `paper/store.py` (phase 6), or anything under `web/` — including
phase 9's classifier, which it **verifies** and does not patch.
**Exit criteria:** successor entries for all six live rows — the four quant books, **C**, and SPY —
each paying Gotrade's measured fees and carrying the contribution schedule from their first night, as
new ids with fresh clocks in the 010/011/013 migration style. N stays 20 (Decisions, D3). The
predecessors are marked retired, not deleted. `docs/runbooks/paper-trading.md:76` still states a
schedule that no longer exists (`cron 23:00 UTC Mon-Fri (06:00 WIB)` against the real `17 6 * * 2-6`
= 13:17 WIB) — measured at `485d416`, and the documentary cause of one false alarm already; fix it
here. The resume-condition comment above `PAPER_PAUSED` is rewritten to state what now holds and what
remains. **The switch is not flipped** (Decisions, D1). Landing while paused is safe and deliberate:
`nightly.yml:48` confirms Migrate still runs while paused, so the migration applies, but no
`paper_start` is written and no session is stepped until the owner resumes.

**The wiring layer's own exit criteria**, each closing a handoff another phase left open:
`grep -c 'rules=e.rules' commands/paper.py` is **4** and `promote.py:275` reads `is_bracket(rules)`;
`_step_benchmark` gets `SPY-GT`'s model from the roster — through
`roster.benchmark_cost_model(e.id)`, which takes the **id** and raises rather than defaulting — so
the frozen spec and the fills state one thing; the night accrues once per entry and credits before
each session, **raising cash and equity together** on all three engines; `paper/replay.py` carries
no literal `DESIGN_V0` argument and replays the **stored dated deposits**, not the schedule (D18); and a
**retired** entry's pending decision renders as a record, never a live instruction — phase 9's
classifier, verified here against the six entries this phase retires (D16).

## Reconciliation Log

The twelve planners ran concurrently and could not see each other. **Thirty-three conflicts** were
found across the twelve plan files and the draft index — twenty-four in round 1 and nine more in
round 2's verification pass, below — and **all thirty-three are resolved in the plan files
themselves**: the losing side is deleted, not merely outranked. Nothing is deferred.

| # | Conflict | Class | Resolution |
|---|---|---|---|
| 1 | `commands/paper.py` wanted by phases **3, 4, 6 and 12**; given to none. Phases 3 and 4 are both in wave 1 — two concurrent sessions in one file | file collision | **D10 enforced.** Phase 4's Steps 10–11 deleted from its plan and moved verbatim into phase 12's new **Step 7a**; phases 3 and 6 state their call sites as handoffs with phase 12 named as owner. Every signature involved is keyword-with-default, so the tree is green at the end of 3, 4 and 6 with the wiring absent — asserted by phase 4's new exit criterion 4 |
| 2 | `commands/promote.py:275` — same collision, same phase 4 step | file collision | Moved to phase 12 Step 7a with D10 |
| 3 | `paper/store.py:1127` (`load_benchmark`) — phase 3 needs the `cost_model` keyword; phase 6 owns the file; neither claimed `:1127` | gap / ownership | **D13 (new).** To phase 12, with the rest of the wiring. Phase 6's plan now fences `:1127` off explicitly and its exit criteria check `git diff` there |
| 4 | `paper/replay.py:290` hard-codes `DESIGN_V0` and no `expected_*` builder takes a deposit — `seer paper check` would fail on the first night after resume | gap | Phase 12 **Step 7d**, under D10 |
| 5 | Nothing calls phase 6's `accrue_contributions` / `apply_contributions` / `deposit_book` in production — the successor entries would not carry the funding plan from their first night | gap | Phase 12 **Step 7c**, under D10. Phase 12's `Satisfies` gains **R3** with the step (rule: requirement ids follow the work) |
| 6 | `lab/npolicy.py`'s prose quotes 110 dev trials and 23 methods; no phase owned the file | gap | **D11 enforced.** Phase 1, comment-only, as its new **Step 4**. Measured replacements 126 and 28; `:23`'s "2" is still correct and stays. Phase 1's `Package` gains `engine.lab`, Files 2 → 3 |
| 7 | `test_lab_snapshot.py` has **two** version numbers pinned in it: `SNAPSHOT_VERSION` (int, phase 2) and `SCHEMA_VERSION` (string, phase 7, six sites) | file collision / ambiguity | **D14 (new).** Split by line and made explicit in both plans with a table. Phase 2 leaves the six `"3"` pins at `"3"`; phase 7 owns them plus the v3→v4 migration test. Phase 7's "this could move into phase 2" escape hatch is deleted |
| 8 | Phase 7's `lab/store.py` line numbers (`:1294`, `:1386`, `:1564`) are pre-phase-2; phase 2 inserts ~22 lines at `:1272` | later phase quotes pre-change state | Both plans now say so; phase 7 is instructed to locate those three hunks **by symbol, not by line** |
| 9 | `commands/lab.py` — phase 8 adds three hunks; phase 7 "restates the gate" and might also touch it | suspected collision | **Checked: phase 7 does not touch it** (its Files table names seven files; that is not one). Phase 8 recorded as sole owner |
| 10 | Five test files broken by `INITIAL_IDR` 20M → 10M, claimed by no phase in the draft index | gap | Phase 5, all five. `test_book_runner.py` checked against phase 4's Files table — not claimed there — so it stays with its `FIXTURE_IDR` pins in one commit |
| 11 | Phase 4's contract says `backtest/runner.py` is untouched; its own handoff says `run_backtest` needs a `rules` parameter | contract drift | Resolved **inside phase 4**: it leaves the file byte-identical. The `rules` keyword is assigned to **phase 5** (it owns the file and depends on 4) as its new **Step 2b**, together with `book_runner`'s `is_bracket` dispatch (`:380`) and `order_fee` (`:521-522`). Phase 5's "phase 4 may edit runner.py's call sites" paragraph is deleted |
| 12 | `backtest/dev.py:185,:206,:223` branch on `rules.engine == "bracket_v0"` — a trap once a second bracket engine exists; unowned | gap | Phase 7 (it owns `dev.py`), folded into Step 10b |
| 13 | Phase 8 requires `dev.run_registry(contributions=…)`; **phase 7 does not add it**. Phase 8's whole sweep is unrunnable, and phase 7's own DCA-SPY measurement is unreachable from the dev path | unmet assumption | Phase 7's new **Step 10b** adds the keyword to `run_registry` and `_run`, passed to `run_rules` |
| 14 | The contribution schedule's names: phase 5 defines `OWNER_MONTHLY` / `dates_in`; phase 6 assumed `OWNER_SCHEDULE` / `due_dates`; phase 8 `SCHEDULE_NAME = "OWNER_SCHEDULE"`; phase 12 `OWNER_PLAN`; phase 10 `OWNER_SCHEDULE` in TypeScript | contract drift (five-way) | **D15 (new).** Every reference rewritten to phase 5's actual names, including the TypeScript mirror — one name, both runtimes, `grep` finds both halves |
| 15 | Phase 8's `MWR_FIELD = "money_weighted_return"` — that is phase 7's **function**; the field is `Metrics.mwr` | contract drift | Corrected to `"mwr"` in phase 8, with phase 7's D7b (`mwr is None` on an unfunded run) explained so a dash in the `--lump` column reads as correct |
| 16 | The spec shape for the schedule: phase 5 wrote `{"amount_idr": "5000000", "day_of_month": 25}`; phase 12 writes `{"amount_idr", "cadence", "day_of_month"}`, all strings | contract drift | Phase 12's wins (rung 3: its own code block — `roster.spec` is strings-and-nulls because it is hashed into a frozen digest, so `"25"` is forced). Phase 5's contract point 8 rewritten to quote it; phase 12's test pins `OWNER_FUNDING` against `OWNER_MONTHLY` field by field, with `"cadence"` asserted as a literal because the object has no such field |
| 17 | The credit must raise **equity** as well as cash, or every deposit is permanently under-deployed (`sim/sizing.py:137`, `sim/book.py:536`). Phase 6's handoff snippet raised **cash only** for the bracket and benchmark adapters | deleted-then-used, in effect | Fixed in phase 6's handoff and in phase 12's Step 7c, and made an explicit exit criterion in phases 6, 7 and 12 |
| 18 | `paper/compare.py` reads returns straight off equity — wrong the first month a deposit lands; unowned | gap | **D12 (new).** Phase 6, as its new **Step 10**, with `commands/compare.py` as the impure edge. Phase 6 Files 5 → 7 |
| 19 | Phase 12 retires six entries whose pending rows stay in the database with `pending_decision = true`; phase 9's classifier has no input for "the entry that decided this is retired". Phase 9 is wave 1 and cannot depend on phase 12 | gap, cross-phase | **D16 (new).** Phase 9 handles retirement **generically** (`panelState(..., retired)`), which is already correct for the four entries retired today; phase 12 **verifies** it as its exit criterion 13 |
| 20 | Phases 9 and 11 report the same four facts to the owner in two surfaces; both planners asked to be aligned to the other | contract drift | **D17 (new).** Checked: they already agree on the two words that matter (`none due`, `PAUSED`). Both plans now carry the same table and the instruction that rewording one means rewording both |
| 21 | Four phases touch the `PAPER_PAUSED` line (9 mirrors it, 11 `sed`s it, 12 rewrites the comment above it, nobody edits it) | compatibility | Compatible. Phase 12 now carries an explicit constraint that the line's exact text and indentation survive, because phase 9's regex and phase 11's `sed` both key on them; it is an exit criterion there and a note in 9 and 11 |
| 22 | `web/lib/format.ts` — phase 10 routes negative cash through `signedUsd`; is it adding it? | suspected collision | **No.** `signedUsd` already exists at `format.ts:8`; phase 10 imports it. **No phase edits `format.ts`.** Recorded in phases 9 and 10 |
| 23 | `web/lib/sean/planData.ts` claimed by phase 10, named by the index nowhere | unowned file | Checked against all eleven other plan files: unclaimed everywhere else. Claim recorded in phase 10's **Owns** line |
| 24 | Phase 8's rationale says *"phase 1 re-pins `COMMITTED_DEV_TRIALS` from 110 to 126"* — phase 1 **deletes** all four constants and replaces the test with a recomputation | contract drift | Corrected in phase 8 (twice: its design note and its handoff). Its argument survives and is stronger — phase 1's replacement test asserts against the **live** `dev_trial_count` and its `basis` string, both of which `web/data/lab.json` publishes, so a sweep that wrote trials would move a published number on the night it ran |

**Four places where the analysis's Impact Points list and the plans deliberately differ.** All
checked; none is a gap:

| analysis impact point | what the plans do instead, and why |
|---|---|
| #14 `sim/model.py` — *"`buy_cost` / `sell_proceeds` take the cost model"* | **Not modified.** Phase 4 measured the cycle: `sim/costs.py` imports `sim.model.q`, so a rules-aware helper in `model.py` would have to import `costs` — and `costs.py` may not be edited (invariant 5). It creates `sim/charges.py` instead, the bracket twin of `sim/book.py`'s private helpers, with the flat branch pinned bit-identical to `model.buy_cost` / `sell_proceeds` over 20,000 random pairs. `model.py` stays exactly as it is, which is what keeps `backtest/benchmark.py`, `paper/benchmark.py` and their tests untouched |
| #20 `engine/tests/test_sim_scenario.py` | **Needs no edit** — measured. Every new parameter defaults to `DESIGN_V0`, so that file's numbers are unchanged; phase 4 runs it as part of the full suite and asserts the failing-node set is identical |
| #24 `engine/tests/test_backtest_dev.py` | **Needs no edit** — measured. Phase 5's `INITIAL_IDR` move breaks 10 tests in 5 files and that is not one of them; phase 7 runs it in its targeted subset |
| #34 *"the N sweep as registered lab variants"* | **A report, not registered variants.** Phase 8 measured the price: six registered dev trials take the lab from 126 to 132, and `store.DSR_POLICY` is `all-trials`, so **every** method in the lab is re-scored against a higher luck bar and `web/data/lab.json`'s `gate.dsrN` moves — a real cost that R2 does not need paid. It follows `lab/real_costs.py`'s existing contract instead: no `trials` row, no status, no pre-registration, `lab.sqlite` unwritten |

### Round 2 — the verification pass

Round 1 reported `contract_changed: true` because six creations and relocations had moved between
phases, so phases 5, 6, 7, 8 and 12 were written against a contract that had since changed. Round 2
re-read all twelve plans against the ledger and found **nine** further defects, every one of them a
leftover or a consequence of those moves. **All nine are fixed in the plan files; none is deferred,
and no round-1 decision is reversed.**

| # | Conflict | Class | Resolution (round 2) |
|---|---|---|---|
| 25 | `phase-3.md`'s Handoff H1 — which phase 12 is told to apply **verbatim** — calls `roster.benchmark_cost_model(e)`, passing the entry; phase 12 defines `benchmark_cost_model(entry_id: str)` and calls it with `e.id`. The same paragraph said `e.id` in its prose and `e` in its code | contract drift | Phase 3's code block corrected to `e.id`, with the signature and the `BadRosterRow`-rather-than-default behaviour quoted as phase 12 actually lands them |
| 26 | `phase-5.md`'s **Depends on** line still read *"phase 4 … may touch `backtest/runner.py`"* — the exact claim round 1's conflict 11 deleted everywhere else | contract drift (round-1 residue) | Deleted. The line now states that phase 4 leaves `runner.py` byte-identical and the file is wholly phase 5's |
| 27 | `phase-5.md` Step 2 still ordered *"**Do not touch** `runner.py:181` or `:186` — those lines are phase 4's"*, flatly contradicting its own Step 2b, which edits exactly those lines | contract drift (self-contradiction) | Deleted and inverted: those three lines are phase 5's, and Steps 2 and 2b land in one commit because they touch one function |
| 28 | `phase-5.md` Step 3 quoted `run_rules`'s bracket branch **without** Step 2b's `is_bracket` dispatch and `rules=rules`, leaving two versions of one hunk and a footnote asking the implementer to merge them | duplicate work | Step 3 now carries the final form; Step 2b points at it. One version of the hunk, nothing to merge |
| 29 | `phase-5.md`'s handoff to phase 6 still named the **losing** spec shape from round 1's conflict 16 (`{"amount_idr", "day_of_month": 25}`), and attributed a spec to phase 6, which persists dated rows and no spec at all | contract drift (round-1 residue) | Rewritten: phase 6 writes `paper_contributions` rows; the only serialization is phase 12's strings-only `roster.spec` |
| 30 | `phase-6.md` Step 10 credited `store.apply_contributions` to **phase 4** | contract drift | Corrected to this phase's Step 4, with phase 12's Step 7c named as the caller |
| 31 | `phase-6.md`'s handoff 2 ended *"Suggested owner: phase 12"* after round 1 had **assigned** it there | contract drift | Hardened to "phase 12's Step 7d — settled, not suggested" |
| 32 | **`phase-12.md` Step 7d contradicted itself**: its Interface Contract typed the replay's `contributions` as `ContributionSchedule \| None`, while its own prose said the dated dollars come from `store.read_contributions`. Underneath it, phase 7's `buy_and_hold` takes `Sequence[tuple[date, Decimal]]` while phase 5's runners took a schedule only — so the benchmark replay would not type-check and the book and bracket replays would **re-derive** each deposit at one rate, disagreeing with the record phase 6 deliberately froze at `usd_idr_on(landing session)` (its D6a). `judge` would then report a mismatch on every session after the first deposit — the exact failure Step 7d exists to prevent | contract drift → unmet assumption | **D18 (new).** Settled towards the **record**. Phase 5 gains `Contributions` and `credit_for` so all three runners accept either a plan or dated, already-converted deposits; phase 12's three `expected_*` builders take `Sequence[tuple[date, Decimal]]` off `store.read_contributions`, and its exit criterion 12 now greps `replay.py` for `OWNER_MONTHLY`/`ContributionSchedule` and requires **no** match. Phase 6's handoff 2 states the rule from the side that owns the frozen rate |
| 33 | `phase-9.md`'s classifier takes the `retired` flag (D16) and tests it six ways, but its **only production call site** — `positions/page.tsx` — was written `panelState(pending.sessionDate, pending.decision, now)`, three arguments. D16 would have passed its unit tests and never reached a page, and phase 12's exit criterion 13 would have failed against a correct classifier | contract drift (a defaulted parameter nobody passes) | Call site corrected to pass `strat?.status === 'retired'`, with the reason in a comment; phase 9's exit criterion 7 now also greps the call site, because a unit test on the classifier cannot prove the flag arrives |

**Swept and clean in round 2, stated so the checks are on the record:** every plan's Files table was
re-counted and all twelve match the table above (3, 13, 2, 13, 11, 7, 7, 5, 8, 8, 2, 10); the only
three files touched by two phases are `lab/store.py` and `test_lab_snapshot.py` (2 → 7) and
`paper/store.py` (6 → 12), **all three dependency-ordered and line-fenced**, so no pair of concurrent
sessions shares a file; `commands/paper.py`, `commands/promote.py`, `paper/compare.py` and
`load_benchmark` appear outside their owning phase only as citations or handoffs; phase 8's
`SCHEDULE_KEYWORD = "contributions"` matches phase 7's Step 10b keyword literally; phase 4's preset
`"design-v0-gotrade"` at `PRESETS[13]` agrees with phase 12's `BRACKET_GOTRADE_RULES_ID` and its
migration row; the two "3 → 4" bumps stay apart (phase 2 the int, phase 7 the string, each plan
fencing the other off by line); and phases 9 and 11 still share `none due` and `PAUSED` with neither
importing the other.

**Index corrections carried in, and verified rather than trusted:** deliberate skip sites are
**nine**, not eight (phase 1 measured it); Sean lives at `web/app/sean/`, not `web/app/(app)/sean/`
(phase 10 measured it). **File counts, every one re-counted against the phase's own Files table:**
1: 2→3 · 2: 8→13 · 3: 2 · 4: 10→13 (15 minus the two caller files moved to phase 12) · 5: 5→11 ·
6: 5→7 · 7: 6→7 · 8: 3→5 · 9: 6→8 · 10: 5→8 · 11: 2 · 12: 5→10.

**The DAG is unchanged** — no dependency was added or moved, and every dependency still points
backward only: `1,2,3,4,9,11 → 5 → 6,7,10 → 8,12`. Every conflict above was resolved by moving a
*step*, never by moving a *phase*.

## Decisions

Every fork settled here rather than passed to twelve sessions, with the rung of the precedence
ladder that settled it.

| Fork | Chosen | Rung |
|---|---|---|
| D1. Does the plan set resume paper when its phases are done? | **No. `PAPER_PAUSED` stays `'true'`; phase 12 only rewrites the comment to say what now holds.** The owner flips it. Resume condition 3 includes the lab's name-count answer, which phase 8 produces but which is a judgement the owner should see before live money follows it; and the user wrote that there is no deadline, so nothing is bought by flipping it unattended. | 5: the user's raw input — *"do not resume until they hold"*, *"optimise for getting it right once, not for speed"* |
| D2. Is Q3 (contributions) its own plan set, or phases here? | **Phases here (5, 6, 7).** The user wrote "likely deserves its own plan set", which is a judgement offered rather than an instruction given; and the handover's own Q3 says *"the rebuilt roster entries should carry the contribution schedule from their first night, or they will need rebuilding again"*. A separate set would have to land before phase 12 anyway, so splitting buys nothing and risks the roster being rebuilt twice. | 4: the index's Why and Requirements table, over 5: the user's "likely" |
| D3. What name count does the rebuilt roster carry, given Q2 is unanswered? | **N = 20, unchanged.** Handover §2b is marked **CORRECTED** precisely on this point: *"Do not plan a name-count reduction on fee grounds."* Measured here, by month 3 of the funding plan the two counts cost 0.614% and 0.612% — the fee case is gone. Phase 8 still measures the merits question; if its answer differs, it lands as a **further roster entry** under the rule that already governs roster change (`paper-trading.md:60-68`), which is how this system is designed to absorb exactly this. Phase 12 therefore does **not** depend on phase 8. | 5: the user's raw input / handover §2b CORRECTED |
| D4. May contributions ship before the money-weighted return? | **No — phases 5, 6 and 7 are one unit and phase 12 depends on all of them.** A deposit raises ending equity without being a return, so contributions without a money-weighted measure turn every CAGR in the system into a flattering number and "beats SPY TR" into a comparison of two books holding different money. That is strictly worse than having no contributions at all. | 1: stated invariant (6, every number measured) + handover §4's two consequences |
| D5. The bracket path: branch inside it, or change its signatures? | **Change the signatures.** Measured, not inferred: `replace(DESIGN_V0, cost_model='gotrade')` raises *"engine 'bracket_v0' is reserved for DESIGN_V0"*, and `engine='bracket'` raises *"unknown engine"*. `size_picks` and `step` take no `rules` at all. A branch cannot be added to a function that never receives the value it would branch on. The handover's `_ONE_PLUS_COST` is the third blocker, not the first. | 3: the plan's own measured code reading, over the handover's narrower §3b wording |
| D6. Where does the contribution date come from? | **The 25th of each month, as a calendar date, with the NYSE calendar producing the lag.** Decided by the owner 2026-10-08 and relayed mid-analysis. Measured: the gap to the next month's first session is a mean of 7.0 days, ranging 4 (Feb 2027) to 10 (Dec 2026), so a fixed lag is wrong in ten months of twelve. Reproducing that idle cash is required, not incidental — depositing at the rotation instead would overstate returns. | 5: the owner's decision, relayed; measured here |
| D7. Is T+1 settlement a blocker for the rotation reminders? | **No.** The 25th deposit is settled cash about a week before a month-start rotation, so the rotation's buys are funded from the deposit rather than from the day's sale proceeds. Phase 10 designs the list to work either way and treats same-day reuse as a bonus. The owner's 2026-10-07 sequence proves a sale does not *block* a buy but not that proceeds are spendable, and `sean/ledger.ts` says Sean can never settle it from receipts. | 5: the owner's decision, relayed |
| D8. Phase 2 and phase 7 both edit `lab/store.py`. | **Phase 7 depends on phase 2 and quotes the file as phase 2 leaves it.** The alternative — two concurrent sessions editing one file — is the collision the dependency column exists to prevent. | 1: stated invariant (1, the tree builds at the end of each phase) |
| D10. Who owns `commands/paper.py`, which phases 3, 4, 6 and 12 all need and **no phase was given**? | **Phase 12, together with `paper/replay.py` and `commands/promote.py`.** This was a gap in the decomposition, found by three planners independently. Phase 12 is last (wave 4) and already depends on 3, 4, 6 and 7, so it is the only phase that can quote every signature as it actually lands. Phases 3, 4 and 6 each state their required call-site change as a handoff instead of editing the file. This is safe because every signature they add is **keyword-with-default**, so the tree builds and the suites pass at the end of each of those phases with the wiring still absent — the capability is complete and inert until phase 12 turns it on, which is exactly the state the pause already holds the system in. | 1: stated invariant (1, the tree builds and tests pass at the end of each phase) |
| D11. Who owns `lab/npolicy.py`, whose prose quotes the aged numbers (110 dev trials, 23 methods)? | **Phase 1.** It is the same aged-number defect R6 exists to fix, phase 1 is already in that file's test, and no other phase touches `npolicy.py`. Measured replacements: 126 dev trials, 28 methods. | 4: the index's Requirements table — R6 is "a form that cannot age again", and prose that states a stale number ages the same way a constant does |
| D9. `COMMITTED_DEV_TRIALS` re-pins to what? | **126, not the 128 the handover names.** Measured: `lab/lab.sqlite` holds 128 rows = 126 dev + 2 test, and the constant is compared against `store.dev_trial_count`, which counts dev only. 128 would leave the test skipping exactly as it does today — the failure mode R6 exists to end. 126 is also what `web/data/lab.json`'s `gate.dsrN` already publishes. | 3: the plan's measured reading, over the handover's §6a wording |

Added by the reconciler, 2026-10-08. D1–D11 are unchanged; none is reversed.

| Fork | Chosen | Rung |
|---|---|---|
| D12. `paper/compare.py` reads a return straight off equity, so a deposit reads as performance. No phase owned it. | **Phase 6**, as its Step 10, with `commands/compare.py` as the impure edge: `_returns` subtracts the session's deposit before taking the ratio, and `_cagr` answers `None` for a window that received one rather than quoting a number that counts the owner's own money as growth. It is phase 6's because that phase owns `store.read_contributions` (the data), owns the deposit path (the cause), and has the fixtures; phase 7 never touches `paper/`, and phase 12 is already carrying the whole wiring layer. | 4: the index's **Scope** — *"the contribution model in full — schedule, backtest, **paper**, money-weighted return and dollar-cost-averaged benchmark together, because a half-built one is worse than none"* |
| D13. Who edits `paper/store.py:1127` (`load_benchmark`), which phase 3 needs and phase 6 owns the file around? | **Phase 12**, with the rest of the wiring, **not phase 6.** The regions are line-disjoint (phase 6 is at `:417`/`:449` and the new contributions section) and phase 12 depends on 6, so the two edits are sequential and never concurrent. Keeping every wire in one phase is the whole point of D10, and phase 6 has no test, no reason and no context for a benchmark fee keyword. Phase 6's plan fences `:1127` off and checks it in its exit criteria. | 1: stated invariant 1 (the tree builds and both suites pass at the end of each phase), applied through D10 |
| D14. `test_lab_snapshot.py` pins **two** different version numbers that both read "3 to 4". Who moves which? | **Split by line, and written out as a table in both plans.** `SNAPSHOT_VERSION` is the published JSON's version, an **int**, pinned once at `:280` — **phase 2**. `SCHEMA_VERSION` is `lab/lab.sqlite`'s schema version, a **string**, pinned at `:86`, `:104`, `:113`, `:180`, `:207`, `:238` — **phase 7**, which is the phase that moves it, together with the new v3→v4 migration test. Phase 7 depends on phase 2, so this is sequential. Phase 7's "this could move into phase 2 if the reconciler prefers" is deleted: it cannot be dropped without the suite going red, and phase 2 has no reason to know about `trial_funding`. | 2: the phases' exit criteria — phase 2's is about what the **web** renders, phase 7's is *"schema v4 exists and `trials` is byte-identical across the migration"* |
| D15. The contribution schedule's name and shape, guessed five different ways by five concurrent planners. | **Phase 5's actual definition, everywhere:** module `seer_engine.sim.contributions`, class `ContributionSchedule(amount_idr: Decimal, day_of_month: int = 25)`, instance **`OWNER_MONTHLY`**, methods `dates_in(first, last)` (inclusive both ends) / `due(after, through)` (exclusive of `after`) / `usd_at` / `credit_usd`. Phase 6's `OWNER_SCHEDULE`/`due_dates`, phase 8's `SCHEDULE_NAME`, phase 12's `OWNER_PLAN` and phase 10's TypeScript `OWNER_SCHEDULE` are all rewritten — the TypeScript mirror included, so one `grep -rn OWNER_MONTHLY` finds both halves of the system. Phase 7 was already correct: it reads `r.cashflows` through the single function `metrics.external_cashflows`. | 3: the plans' code blocks — phase 5 is the definer and the only one with the module in its Files table; rung 6 (the surrounding convention) for carrying the same name into TypeScript, which is what `RESIZING_RULES` and `RESIZE_BAND` already do |
| D16. A **retired** entry's pending decision can still be dated for the coming session. Does it render as a live instruction? | **No — phase 9's classifier takes a `retired` input and answers `spent`,** generically rather than against phase 12's rebuild. Phase 12 retires six entries whose 80 `book_targets` rows and 4 `orders` dated 2026-10-07 carry `pending_decision = true` and are deliberately **not** deleted (invariant 3). Phase 9 is wave 1 and cannot depend on phase 12, so the fix lives in phase 9 (its D9.6) and the check lives in phase 12 (its exit criterion 13). It is already correct today for the four entries retired by 010 and 013. | 4: the index's Requirements table — R5 is *"never read as a live instruction"*, and a retired strategy's order is the sharpest case of exactly that |
| D17. Phases 9 and 11 report the same four facts in two surfaces, and each asked to be aligned to the other. | **Both keep what they chose; the words already agree.** `none due` / *"Nothing was due for &lt;date&gt;"* and `PAUSED` / *"Paper trading is paused"*. The registers differ on purpose — one line on a phone against a sentence on a page — and neither side imports the other (different runtimes; a workflow cannot import TypeScript). Both plans now carry the same table and the standing instruction that rewording one means rewording both. | 1: stated invariant 7 — *"prose the owner reads stays plain"*; the thing that must agree is the words he reads, not the code |

Added by the reconciler in round 2, 2026-10-08. D1–D17 are unchanged; none is reversed.

| Fork | Chosen | Rung |
|---|---|---|
| D18. A paper **replay** has to re-fund the book. Does it hand the runner the owner's *schedule*, or the *deposits that actually happened*? The two give different dollars: phase 6 freezes each deposit at `usd_idr_on(its landing session)` (D6a) so a backfilled `fx_rates` can never move a stepped book's history, while a backtest converts at **one** rate per run (phase 5's contract point 4). Both are right for their own job, and `phase-12.md` asked for both in one step — typing the parameter as a `ContributionSchedule` while its prose read the dated rows out of `store.read_contributions`. | **The record, never the schedule.** All three `expected_*` builders take `Sequence[tuple[date, Decimal]]` straight off `store.read_contributions` (applied rows only, ascending), and phase 5's `contributions=` widens to `Contributions = ContributionSchedule \| Sequence[tuple[date, Decimal]]` with one new function, `credit_for`, which credits a record's dollars **unchanged** and computes a plan's at the run's rate. Phase 7's `buy_and_hold` already spoke the dated half, so the three runners now share one vocabulary and the benchmark replay type-checks. Phase 5 keeps the plan form, which is what phases 7 and 8 measure with — nothing about the lab moves. | 2: the phases' own exit criteria — phase 12's criterion 12 is *"`seer paper check` … would reconstruct the same record the night wrote"*, which a re-derived deposit cannot do once the rupiah has moved, and phase 6's D6a already forbids recomputing a recorded deposit. Rung 1 (invariant 6, every number measured and recoverable) says the same thing about a dollar figure that changes when you ask it twice |

## Open Questions

**None.** Every one of the thirty-three conflicts in the Reconciliation Log — twenty-four in round 1,
nine in round 2 — was decidable from the ladder and is recorded under **Decisions** with the rung
that settled it. Every requirement id R1–R9 is owned by at least one phase, so there is no coverage
gap to park here either.

And none of these forks is irreversible, which is the only thing that would justify parking one: a
roster entry that turns out wrong is superseded by another entry (the rule this system already runs
on), no migration deletes a row, `lab/lab.sqlite` is opened read-only by every phase that reads it,
and paper is paused with **zero sessions stepped** — so nothing in this plan set consumes history
that cannot be remade.

This section being empty is what lets `/analyze-orchestrator` launch the set unattended.

## Rollback

**Per phase.** Every phase is one commit on `feature/gotrade-fee-rebuild`; `git revert` it. Phases 1,
2, 3, 9, 10 and 11 are independently revertible. Phases 5, 6 and 7 are one unit (D4) — revert all
three or none, because contributions without the money-weighted measure is a worse state than either
end. Phase 4 changes signatures across `sim/`; reverting it also requires reverting 5, 6, 7 and 12.

**One consequence of the reconciliation, stated so it is not a surprise.** Phase 12 is now the
wiring layer as well as the roster (D10, D13), so reverting **phase 12 alone** also unwires phases 3,
4 and 6 — the capabilities go back to being complete, tested and inert, which is exactly the state
they are in before phase 12 lands and is a coherent tree, not a broken one. The reverse does not
hold: reverting 3, 4 or 6 while phase 12 stands leaves phase 12's wires calling signatures that no
longer exist, so **revert 12 first, then the phase underneath it**.

**As a whole.** The branch is never merged until the set is green, and `main` is unaffected until
then. After a merge: the roster migration (017) only inserts display rows and marks predecessors
retired — no paper clock starts while `PAPER_PAUSED` is `'true'`, so a full revert plus a `DELETE` of
the inserted rows restores the prior state exactly. **That property holds only while zero sessions
have been stepped**, which is what the pause preserves and what every night of an unpaused run would
spend.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f GOTRADE_FEE_REBUILD_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f GOTRADE_FEE_REBUILD_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan GOTRADE_FEE_REBUILD_PLAN.md
