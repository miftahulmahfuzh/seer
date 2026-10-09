# Code Analysis: rebuilding the roster to pay Gotrade's real fees

**Type:** Feature Implementation (with two bug fixes carried along: red `main`)
**Date:** 2026-10-08 09:13 WIB (2026-10-08T02:13:21Z)
**Session ID:** 20261008-091321-H3M8
**Plan:** `GOTRADE_FEE_REBUILD_PLAN.md` (12 phases)
**Worktree:** `/home/miftah/.worktrees/seer/gotrade-fee-rebuild` — branch `feature/gotrade-fee-rebuild`, base `origin/main` @ `485d416`

---

## User Input

### Original User Request

The invocation, verbatim:

```
/analyze feature --permission-mode bypassPermissions
Read docs/handover/2026-10-08-sean-shipped-red-main-and-the-vanishing-picks.md FIRST and treat it as the specification — it was rewritten this morning and is current as of main @ 6fd36f4. Its section 8 lists nine questions to settle; section 10 says how every number in it was verified. Claims I marked CORRECTED are ones an earlier session (mine) got wrong — the wrong version is stated beside the right one so you do not re-derive it.

The thread running through all of it: Sean measured Gotrade real fees from the owner receipts and they are ~2.5x the 0.1%/side every lab trial assumed, and ~5.2x at the owner current $28 slots because of a $0.10 per-order floor. The roster has to be rebuilt to pay them.

Four things that shape the work and are easy to miss:

1. PAPER IS PAUSED (PAPER_PAUSED true in .github/workflows/nightly.yml, commit d44fa78) and the paper clock is frozen at ZERO stepped sessions. There is therefore NO deadline — the rebuild stays free indefinitely. Optimise for getting it right once, not for speed. The resume conditions are written above the switch in that file; do not resume until they hold.

2. C STAYS ON THE ROSTER PERMANENTLY. The owner requires a daily-trading method as the measured counterfactual for the daily-trading plan he originally wanted. Never propose retiring it on cost grounds — being expensive is the finding it exists to produce. That makes a gotrade branch in the bracket path (sim/lifecycle.py, sim/sizing.py) a hard dependency, not an option.

3. Q3 and Q9 share a foundation and should be sequenced together. The owner adds 5,000,000 IDR every month to a 10,000,000 IDR start, and NOTHING in the system models contributions — paper cannot even accept a deposit. A recurring contribution schedule would serve both the lab model (Q3) and Sean execution reminders (Q9). Q3 likely deserves its own plan set; it drags in money-weighted returns and a dollar-cost-averaged SPY, because CAGR and beats-SPY-TR stop meaning anything once deposits exist.

4. Q9 is small, high value, and mostly already built — extend web/lib/sean/reminders.ts rather than rebuilding it. The only missing input is the owner cash balance.

Also: main is RED for two unrelated reasons described in section 6 — expect that and do not chase it as something you broke.

One leftover to be aware of, which I deliberately did not touch: a previous analyze session on this was killed mid-flight and left an UNCOMMITTED plan at /home/miftah/.worktrees/seer/red-main-and-real-fees (RED_MAIN_AND_REAL_FEES_PLAN.md, 20261008-082628-R7G4_code_analyzer.md, .workflows/plan/red-main-and-real-fees/). It is stale — it predates the corrections and the pause — but its analysis document cost real compute and may hold verified findings worth reusing. Read it if useful, do not trust its conclusions, and do not delete it without asking the owner.

The owner is not a quant: prose stays plain, numbers carry their meaning. He prefers measuring to estimating — every figure in the handover was measured and yours should be too.
```

### Mid-analysis correction, relayed by `orch-delisting-stress-roster-rules`

A peer session sent this while exploration was in progress. It supersedes the final paragraph above
and moves `main` two commits forward:

> CORRECTION to the prompt I launched you with: the leftover worktree is GONE. The owner decided to
> purge it rather than salvage it, so `/home/miftah/.worktrees/seer/red-main-and-real-fees` and branch
> `feature/red-main-and-real-fees` no longer exist. Do not go looking for them and do not ask about them.
>
> One thing was salvaged … It is now **section 6c** of the handover, and it is recorded as SETTLED:
> the nightly run `37655513074` is an ORPHAN stuck before job creation, not a `seer-db-writer`
> concurrency block. It cannot delay a future nightly. Do not spend a phase on it.
>
> Pull before you read: the handover is now at main @ `8be7117`, two commits newer than the `6fd36f4`
> I quoted to you.

Handled: the stale worktree *was* read before the purge message arrived, and its verified reference
lists were re-measured here rather than trusted (see **Measured Evidence**). `main` was pulled to
`8be7117` and the handover re-read; the only change is the new §6c, which removes a question rather
than adding one. Section 8's nine questions are unchanged.

### Second relay — owner decisions, `main` @ `485d416`

The same peer sent a second message during planning. It carries **two owner decisions** and one
validation, all of which change the work:

> **DECIDED by the owner, 2026-10-08: the monthly 5,000,000 IDR contribution lands on the 25th of
> each month**, not at the rotation. Use that date in whatever contribution schedule Q3 and Q9 build.
>
> 1. **The fee model is VALIDATED against real receipts — trust `sim/costs.py` completely.**
>    `costs.fee_parts` reproduces his actual 2026-10-07 Gotrade charges to the cent, both sides.
> 2. **Settlement is partly answered and mostly moot — do NOT make it a blocker.** … The 25th makes
>    it not matter. … Design the reminder list so a rotation works whether or not same-day reuse is
>    allowed; treat it as a bonus, never a dependency.
> 3. **A calibration point for Q2 and for the fee argument generally.** His 20 real buys cost $2.60
>    in fees to deploy $558 — 0.47% just to establish the book, before any round trip.
>
> One consequence for Q3's schedule object worth getting right: because the deposit lands on the 25th
> and the rank sessions are month-start, there is roughly a week of idle cash every month. The lab
> model must reproduce that idle week, or paper and reality diverge on cash drag — a schedule that
> deposits at the rotation would quietly overstate returns.

Handled: `main` pulled to `485d416`, the worktree re-based onto it, the handover re-read (§2 gained
the receipt validation, Q9's settlement and deposit-timing bullets were rewritten). All three claims
were re-measured here rather than trusted — see **Measured Evidence**; all three reproduce. The idle
week was measured too, because "roughly a week" is an estimate and the schedule object needs the
real distribution.

### User-Provided Context

`docs/handover/2026-10-08-sean-shipped-red-main-and-the-vanishing-picks.md` @ `8be7117` is the
specification. Its §§0–7 are verified fact with the verifying command; §8 is the nine questions;
§9 is owner context; §10 is the verification log. Two claims in it are marked **CORRECTED** and
those corrections are honoured here, not re-derived:

- §2b: the $0.10 fee floor self-resolves in about two months under the owner's funding plan. **Do
  not plan a name-count reduction on fee grounds.**
- §3: the `cost_model` lever *does* model a per-order minimum completely. The gap is narrower.

### User-Provided Files

- `docs/handover/2026-10-08-sean-shipped-red-main-and-the-vanishing-picks.md` (`8be7117`)
- `.github/workflows/nightly.yml` (the pause and its resume conditions)
- `web/lib/sean/reminders.ts` (named as the thing to extend, not rebuild)
- `engine/src/seer_engine/sim/lifecycle.py`, `engine/src/seer_engine/sim/sizing.py` (named as the
  bracket gap)

### Requirement IDs

The handover's §8 is the deliverable list. Its nine questions are numbered Q1–Q9 there and are
carried through with the same numbers — the user refers to them by Q number throughout, and
renumbering would cost more than it buys. §8 writes them in the order Q1, Q2, Q3, Q4, Q9, Q5, Q6,
Q7, Q8; the table below is in label order.

| ID | What the user asked for |
|---|---|
| R1 (Q1) | Rebuild the roster so **every** entry pays Gotrade's measured fees, SPY included — as new entries with fresh paper clocks, because a started entry cannot be edited |
| R2 (Q2) | Decide how many names a monthly book holds **on the merits**, not on fee grounds — a lab question, measured |
| R3 (Q3) | Make the whole system measure what the owner will actually do: 10,000,000 IDR start, +5,000,000 IDR every month — contributions in backtest and paper, a money-weighted return, a dollar-cost-averaged SPY, and every CAGR-phrased gate restated |
| R4 (Q4) | Make the bracket path pay Gotrade's fees so the daily control C is honest. C **stays** permanently |
| R5 (Q5) | The blank pending-picks panel must say which of its causes it is — holding/nothing due, expired, never produced, failed — plus *paused*, and never read as a live instruction |
| R6 (Q6) | Narrow the CI skip-guard to the signature it was written for, and put `COMMITTED_DEV_TRIALS` in a form that cannot age again |
| R7 (Q7) | Settle how a test-window look relates to the luck gate, and make the snapshot, the Sera pages and the test agree |
| R8 (Q8) | One daily line the owner actually receives: session stepped y/n, picks published y/n, CI green y/n, paper paused y/n |
| R9 (Q9) | The owner must execute a rotation without arithmetic — Sean's reminders must size buys from **cash**, which means knowing the wallet, which means the contribution schedule |

---

## Detailed Requirements Understanding

### The one sentence that explains the whole set

Every simulated fill in this repo has always paid one assumed number, 0.1% per side. Sean measured
what Gotrade actually charges against 30 of the owner's own receipts, and at the sizes the owner
trades it is **2.5× that at best and 5.2× that today**, because of a $0.10 per-order floor. The
roster was built on the wrong number, so it has to be rebuilt on the right one — and because a
started paper entry can never be edited, "rebuilt" means new entries with fresh clocks. That is free
only while zero sessions have been stepped, which is exactly what the pause preserves.

### R1 — the roster pays Gotrade

**Problem.** `cost_model` exists, defaults to `"flat"`, and no roster entry uses it. Three distinct
sub-problems, of very different sizes:

1. **The book engine already complies.** `sim/book.py` branches on `cost_model == "gotrade"` at
   every charge site. Nothing to build; the entries just have to ask for it.
2. **The live SPY benchmark cannot.** `paper/benchmark.py` calls `fractional_buy_cost(b.open, shares)`
   and `_fractional_shares(cash, b.open)` with no cost model, taking the `"flat"` default — and
   (**new, measured here**) also computes the fee it records as `q(price × n × COST_RATE)` at
   `:170`, a third site the handover does not name.
3. **The bracket engine cannot, and the reason is deeper than the handover states.** See R4.

**Success.** Every roster entry's simulated fills pay Gotrade's schedule, the benchmark included, so
"beats SPY TR" compares two books paying the same fees.

**Constraint.** `docs/runbooks/paper-trading.md:60-68` forbids editing a started entry, and
`cost_model` sits in `LEVERS_SINCE_PINS` at `"flat"`, so flipping a live entry moves its spec digest
and `store.check_digest` refuses the next night. Compliance therefore lands as new roster entries in
the 010/011/013 migration style.

### R2 — how many names

**Problem.** Every book entry holds 20. The fee argument for holding fewer is a two-month transient
under the owner's funding plan and the handover forbids acting on it. The open question is whether
concentration helps or hurts **on the merits**, over the lab's window, at real fees, under the real
funding ramp.

**Success.** A measured answer, produced by the lab, with the funding plan and Gotrade's fees both
switched on — because the fee floor is size-dependent, so name count and contribution schedule
interact and cannot be measured apart.

**Assumption stated:** the rebuilt roster carries **N = 20, unchanged**. See *Decisions* in the plan
index — this is settled from §2b CORRECTED, and Q2's answer, if it ever differs, lands as a further
roster entry under the rule that already governs roster change.

### R3 — the capital model matches reality

**Problem**, in two halves, the second much larger:

1. `backtest/runner.py:46` `INITIAL_IDR = Decimal("20000000")` — twice the real capital. Paper
   already has its own `PAPER_INITIAL_IDR = 10000000` (**measured here**;
   `engine/src/seer_engine/paper/capital.py:11`), so the lab and paper already disagree *on purpose*.
   The stated reason is *"closed records, where only percentages matter"* — and that reason is
   exactly what Gotrade's floor destroys. See *Measured Evidence*.
2. **Nothing models adding money.** Measured: `grep -rniE "deposit|contribut|top.?up|cashflow|add_cash"`
   over `engine/src`, `web/lib`, `web/app` and `db/migrations` returns six hits, every one the English
   word "contributes" in an unrelated docstring. `paper_state.initial_cash_usd` is written once at
   `paper/store.py:417` and never updated; the only later UPDATE (`:449`) writes `cash_usd`,
   `equity_usd` and `last_session` from stepping a session. Paper cannot accept a deposit.

**Success.** A contribution schedule is a first-class object; the backtest and paper both honour it;
the lab starts at the real 10,000,000 IDR; returns are reported money-weighted; the benchmark is
dollar-cost-averaged on the identical schedule; every gate phrased in CAGR terms is restated.

**The schedule's shape is decided, not open.** The owner has settled the deposit date: **5,000,000
IDR on the 25th of each month**. The rank sessions are month-start, so there is an idle gap every
month — measured here at a mean of **7.0 calendar days, ranging 4 to 10**. The schedule must deposit
on the *calendar date* and let the NYSE calendar produce the lag, because a fixed 7-day lag is wrong
in ten months out of twelve. Reproducing that idle cash is the point: a schedule that deposited at
the rotation would hold a week less idle cash every month and would overstate returns.

**The constraint that makes the measurement halves inseparable.** A deposit raises ending equity
without being a return. Build contributions without the money-weighted measure and every CAGR in the
system silently becomes a flattering lie — strictly worse than not having contributions at all. The
two ship together or not at all.

### R4 — the bracket path pays Gotrade

**Problem — and this is where the handover understates the work.** The handover says
`sim/lifecycle.py` and `sim/sizing.py` "need a `gotrade` branch", with `sizing.py:31`'s precomputed
`_ONE_PLUS_COST` as "the specific thing in the way". Both true. But **measured here, there is an
earlier blocker the handover does not have**: the bracket path cannot express `cost_model="gotrade"`
*at the rules layer at all*, and it never receives a `TradeRules` in the first place. Three facts,
each executed rather than read:

```
_ENGINES = ("bracket_v0", "book")                       # there is no non-v0 bracket engine
replace(DESIGN_V0, id='design-v0-gotrade', cost_model='gotrade')
  -> ValueError: engine 'bracket_v0' is reserved for DESIGN_V0 (the unchanged §5 simulator)
replace(DESIGN_V0, id='bracket-gotrade', engine='bracket', cost_model='gotrade')
  -> ValueError: unknown engine 'bracket'; expected one of ('bracket_v0', 'book')
```

`engine="bracket_v0"` is reserved for `DESIGN_V0` *exactly*: `rules.py:136` computes
`is_v0 = _lever_values(self) == _V0_LEVERS` over **every** field, so a bracket rule set differing in
any field — `cost_model` included — is rejected at construction. And the fill path takes no rules
anyway: `size_picks(portfolio, picks, session_date)` and `step(portfolio, session_date, bars)` have
no `rules` parameter; they call `sim.model.buy_cost` / `sell_proceeds`, which multiply the
**module-level** `COST_RATE = Decimal("0.001")`.

**So R4 is a signature change across the bracket path, not a branch inside it:** a third engine
value, a new preset, a `rules` argument threaded through `size_picks`, `step`, `close_unpriced`,
`split_adjust` and their `buy_cost`/`sell_proceeds` calls, plus every caller
(`backtest/runner.py`, `paper/bracket.py`) and their tests. That is the measured size of the hard
dependency the user flagged as easy to miss.

**Success.** C — which **stays permanently**, as the measured counterfactual for the daily-trading
plan the owner originally wanted — pays Gotrade's fees, on the same starting capital, the same
contributions and the same schedule as the monthly books. If that shows daily trading is ruinous,
that is the finding the entry exists to produce, reported and never acted on as a retirement.

### R5 — the blank panel

**Problem.** `positions/page.tsx:31` is `showOrders = !!strat && !strat.isBenchmark && !run.stale`,
and when it is false the page renders *nothing* in place of two whole sections. The same blank
covers five situations, and the common one is not an error:

- **(a) holding, nothing was due** — the normal state, roughly three weeks in four, running to
  2026-11-02 for all four quant entries;
- (b) the decision expired at the New York close — normal, daily;
- (c) nothing was ever produced; (d) the pipeline failed;
- (e) **paper is paused** — true right now, and nothing says so anywhere in the UI.

**Success.** The page names which one it is, in plain words, says when the next decision is due in
WIB, and is never mistakable for a live instruction. The cadence vocabulary already exists
(`web/lib/cadence.ts`'s `picksMonthlySizesWeekly`, `positions/page.tsx`'s `noOrders()`/`emptyState()`
write cadence-aware prose on the non-stale path) and should be reused, not duplicated.

### R6 — the skip-guard and the aged constant

**Problem.** `.github/workflows/engine-ci.yml:70` fails the build on any `^SKIPPED` line with the
message *"engine tests were skipped; PG_TEST_URL did not reach pytest"* — false, since the run
reports `3362 passed, 2 skipped`. It cannot tell a misconfiguration from a deliberate `skipif`, and
there are **nine** deliberate skip sites (measured, listed in the Reference List).

**Success.** The guard matches `conftest._SKIP_REASON`'s own signature. `COMMITTED_DEV_TRIALS` takes
a form derived from the committed database rather than a typed number.

**Measured, and it changes the number:** the handover says the lab "now holds 128". That is the
*total* trial count. `COMMITTED_DEV_TRIALS` is compared against `store.dev_trial_count`, which counts
**dev rows only**, and `lab/lab.sqlite` holds **126 dev + 2 test = 128**. Re-pinning to 128 would
leave the test skipping exactly as it does today. 126 is also what `web/data/lab.json`'s `gate.dsrN`
already publishes.

### R7 — the luck gate and the test window

**Problem.** `web/lib/sera/lab.test.ts:50` asserts a scored trial misses the luck check exactly when
its score is under the bar. The lab has produced its first two `window: "test"` rows, and the engine
deliberately does **not** luck-gate them — `store.published_verdict` runs `owner_failures` only for a
test row, because a pre-registered confirmatory look has no selection to deflate. So `failedNow`
correctly omits a DSR failure while `dsrNow` carries a number under the bar, and the assertion fails.

**The engine is right; the snapshot is the thing that is wrong.** `_snapshot_trial` publishes both
the record and the verdict but **no marker of whether the luck gate applied**, so every consumer has
to re-derive the rule and the web side derives it wrongly.

**Success.** The snapshot says, per trial, whether the luck gate applies; the Sera pages render "not
applicable" rather than a tick; the test reads the marker instead of re-deriving the rule.

### R8 — one daily line

**Problem.** Nothing watches anything. CI was red ~9 hours unnoticed; the roster's first paper night
produced picks and nobody was told; paper is paused now and nothing will announce it if that is
forgotten. The pause makes this worse, not better: a paused system produces no signal at all, so
silence stops being evidence of health.

**Success.** One line a day reaches the owner with four facts. It must be able to report *"the
nightly did not run"*, which a step inside `nightly.yml` structurally cannot do — so it lives in its
own workflow.

### R9 — a rotation without arithmetic

**Problem.** Most of this is built. `reminders.ts` already renders sells before buys
(`ACTION_ORDER = {sell:0, trim:1, buy:2, add:3}`), turns a dropped pick into a whole-position sell,
turns a new pick into a dollar-denominated buy at `weight × planSize`, fires adds/trims only when the
gap clears `max(MIN_TRADE_USD, RESIZE_BAND × planSize)`, and ticks reminders off from uploaded
screenshots.

**The gap is cash, and it is structural.** `planValue` is the sum of *holdings* value;
`planSize = budgetUsd ?? planValue`. Cash appears nowhere, and `sean/ledger.ts:3` says why it cannot:
*"receipts never show the cash balance."* Sean reconstructs positions from order screenshots, so it
can never know the wallet. On 2 November the owner's +5,000,000 IDR is invisible and every buy is
sized about $280 short, with `budget_usd` — a hand-edited column in `sean_link` — as the only lever.
That manual step is precisely what the owner is asking to remove.

**Success.** `planSize = holdings value + cash`, where cash is derived from the contribution schedule
(deposits) less net buys plus net sells from the ledger. `budgetUsd` stays as a manual override. A
schedule self-corrects when actual fills differ from plan; a pre-computed budget does not.

**Three sub-decisions the handover names**, all settled in the plan index's Decisions table:

- **`MIN_TRADE_USD`** re-tuned against the measured fee curve rather than left at a round $10. At $10
  a corrective trade pays **2.5% round trip**; at $25, 1.08%; at $50, 0.62%.
- **Settlement** — the owner's decision to deposit on the **25th** makes it a non-blocker. His
  5,000,000 IDR is settled cash about a week before a month-start rotation, so the rotation's buys
  are funded from the deposit rather than from that day's sale proceeds. The reminder list must work
  whether or not Gotrade permits same-day reuse; same-day reuse is a bonus, never a dependency.
  (His 2026-10-07 sequence — sell PLTR 21:55 WIB, 20 buys 21:57–22:08, all filled — proves a sale
  does not *block* buying, but not that the proceeds were spendable: the $560.60 of buys were covered
  by the ~$560.51 deposit alone.)
- **Orders stay dollar-denominated, never share counts.** Prices drift between the decision close and
  execution at the open; a fractional dollar order absorbs that drift and a share count does not.

---

## Analysis Scope

### Explicitly Mentioned Files

- `docs/handover/2026-10-08-sean-shipped-red-main-and-the-vanishing-picks.md`
- `.github/workflows/nightly.yml`
- `web/lib/sean/reminders.ts`
- `engine/src/seer_engine/sim/lifecycle.py`, `engine/src/seer_engine/sim/sizing.py`

### Discovered Related Files

| File | Why it is here |
|---|---|
| `engine/src/seer_engine/sim/costs.py` | the Gotrade schedule itself; `fee_parts`, `gotrade_cash`, `gotrade_shares_for` (R1, R4) |
| `engine/src/seer_engine/sim/rules.py` | `cost_rate`, `cost_model`, `_ENGINES`, `_V0_LEVERS`, `PRESETS`, `LEVERS_SINCE_PINS` (R1, R4) |
| `engine/src/seer_engine/sim/book.py` | the four gotrade branches — the book engine already complies (R1) |
| `engine/src/seer_engine/sim/model.py` | `COST_RATE`, `buy_cost`, `sell_proceeds`, `SLOTS` — the flat bracket primitives (R4) |
| `engine/src/seer_engine/sim/split_adjust.py` | calls `buy_cost` at :175; a third bracket charge site (R4) |
| `engine/src/seer_engine/backtest/benchmark.py` | `buy_and_hold`, `spy_curves`, `_fractional_shares`, `fractional_buy_cost` — all already take `cost_model` (R1, R3) |
| `engine/src/seer_engine/backtest/dev.py` | `:435` already passes the candidate's cost model into the benchmark (R1) |
| `engine/src/seer_engine/backtest/runner.py` | `INITIAL_IDR`, `run_backtest`, the session loop (R3, R4) |
| `engine/src/seer_engine/backtest/book_runner.py` | `run_book`, where a book backtest's cash lives (R3) |
| `engine/src/seer_engine/backtest/metrics.py` | `cagr_between`, the `Metrics` record (R3) |
| `engine/src/seer_engine/paper/capital.py` | `PAPER_INITIAL_IDR = 10000000` — paper already uses the real capital (R3) |
| `engine/src/seer_engine/paper/benchmark.py` | the live SPY stepper; three flat-cost sites (R1) |
| `engine/src/seer_engine/paper/bracket.py` | the live bracket stepper, C's path (R4) |
| `engine/src/seer_engine/paper/store.py` | `init_paper_state` (:417 write-once), `write_paper_state` (:449), `check_digest` (R1, R3) |
| `engine/src/seer_engine/paper/roster.py` | `SEED_ROWS`, `spec`, `rules_dict`, `spec_digest` (R1) |
| `engine/src/seer_engine/lab/store.py` | `published_verdict`, `verdict`, `_snapshot_trial`, `write_snapshot`, `dev_trial_count` (R6, R7) |
| `engine/src/seer_engine/lab/npolicy.py` | `effective_n`, `correlation` — what the aged pins measure (R6) |
| `engine/src/seer_engine/lab/real_costs.py` | the existing real-fee twin machinery, `-GT`/`-FLAT` (R1, R2) |
| `engine/tests/conftest.py` | `_SKIP_REASON` — the signature the CI guard should match (R6) |
| `engine/tests/test_lab_npolicy.py` | the four `COMMITTED_*` constants (R6) |
| `.github/workflows/engine-ci.yml` | the `^SKIPPED` guard at :70 (R6) |
| `web/lib/sera/types.ts`, `derive.ts`, `lab.test.ts` | `LabTrial`, `conditionOk`, the failing assertion (R7) |
| `web/app/sera/methods/[id]/page.tsx`, `view.ts` | the "Every variant" table and its marks (R7) |
| `web/data/lab.json` | the published snapshot (R7) |
| `web/app/(app)/positions/page.tsx`, `web/app/(app)/page.tsx` | the blank panel and the coral alarm (R5) |
| `web/lib/session.ts`, `web/lib/data.ts`, `web/lib/cadence.ts` | `isStale`, `runStatus`, the cadence vocabulary (R5) |
| `web/lib/sean/ledger.ts` | *"receipts never show the cash balance"* — why R9 needs a schedule |
| `db/migrations/015_sean.sql` | `sean_link.budget_usd`, `sean_reminder_marks`, `sean_marks` (R9) |
| `db/migrations/013_roster_first_night.sql` | the pattern a roster change follows (R1) |
| `docs/runbooks/paper-trading.md` | the roster rule at :60-68; a stale schedule line at :76 |

---

## Current Dataflow

### Entry Point A: a simulated fill's fee — the book path (R1)

**Location:** `engine/src/seer_engine/sim/book.py:339-370`
**Trigger:** every buy, sell and sizing decision of a book strategy, in both backtest and paper.

```python
def _buy_cash(rules, price, shares):
    if rules.cost_model == "gotrade": return gotrade_cash("buy", price, shares)[0]   # :339
    return q(price * shares * (_ONE + rules.cost_rate))                              # :341
def _sell_cash(...):  if gotrade -> gotrade_cash("sell", ...)[0]                     # :345
def _fee(...):        if gotrade -> gotrade_cash(side, ...)[1]                       # :352
def _shares_for(...): if gotrade -> gotrade_shares_for(budget, price, quantum)       # :367
```

`_shares_for` does not multiply a rate — it **solves** for the largest share count whose rounded buy
cash fits the budget, by bisection, precisely because the $0.10 minimum makes cost non-linear in
shares. **This path is complete.** The only thing missing is a roster entry that asks for it.

### Entry Point B: a simulated fill's fee — the bracket path (R4)

**Location:** `engine/src/seer_engine/sim/sizing.py`, `sim/lifecycle.py`, `sim/split_adjust.py`
**Trigger:** every fill and exit of a bracket strategy — today, only C.

```
sizing.size_picks(portfolio, picks, session_date)        # no `rules` parameter
  :31   _ONE_PLUS_COST = Decimal(1) + COST_RATE          # module-level, computed at import
  :99   unit = limit_price * _ONE_PLUS_COST
  :136  committed = Σ buy_cost(o.limit_price, o.shares)
  :166  committed += buy_cost(order.limit_price, order.shares)

lifecycle.step(portfolio, session_date, bars)            # no `rules` parameter
  :73   proceeds = sell_proceeds(exit_price, order.shares)
  :74   pnl = proceeds - buy_cost(order.fill_price, order.shares)
  :189  cost = buy_cost(fill_price, o.shares)

split_adjust  :175  pnl_usd = in_lieu - buy_cost(order.fill_price, order.shares)

sim/model.py  :76  buy_cost(price, shares)      -> q(price * shares * (1 + COST_RATE))
              :84  sell_proceeds(price, shares) -> q(price * shares * (1 - COST_RATE))
              :25  COST_RATE = Decimal("0.001")
```

**There is no `rules` anywhere in this chain.** The flat rate is a module constant, not a lever, and
the rules layer refuses to express the alternative (see R4 above). Every caller —
`backtest/runner.py`'s session loop, `paper/bracket.py`'s stepper — passes no rules either.

### Entry Point C: the live SPY benchmark's fee (R1)

**Location:** `engine/src/seer_engine/paper/benchmark.py`

```python
from seer_engine.backtest.benchmark import _fractional_shares, fractional_buy_cost   # :42
from seer_engine.sim import COST_RATE, Fill, Position, Snapshot, q                   # :44

:170  cost_usd=q(price * n * COST_RATE)        # the recorded fee — a THIRD flat site
:249  shares = _fractional_shares(cash, b.open)            # cost_model defaults to "flat"
:250  cost   = fractional_buy_cost(b.open, shares)         # cost_model defaults to "flat"
:276  more   = _fractional_shares(cash, b.close)           # "
:278  cost   = fractional_buy_cost(b.close, more)          # "
```

**The functions it calls already take the lever** — `backtest/benchmark.py:109,121,135,143` each have
a `cost_model: CostModel = "flat"` parameter with a working `"gotrade"` branch. The live path simply
never passes it. This is the cheapest of the three fee fixes, and it is resume condition 1.

**The lab already does this correctly.** `backtest/dev.py:433-435`:

```python
# The benchmark pays what the candidate pays: Gotrade's schedule for a cost_model="gotrade"
price, total = spy_curves(spy, start, end, result.initial_cash, spy_dividends,
                          cost_model=c.rules.cost_model)
```

So the asymmetry the owner worries about is solved for the lab and unsolved for live paper.

### Entry Point D: starting cash, and the money that is never added (R3)

**Location:** `engine/src/seer_engine/paper/store.py:417` and `backtest/runner.py:46`

```
backtest/runner.py:46   INITIAL_IDR       = Decimal("20000000")   # the lab
paper/capital.py:11     PAPER_INITIAL_IDR = Decimal("10000000")   # paper — the owner's real money
```

`capital.py`'s own comment states the split is deliberate: *"The backtests keep
`backtest.runner.INITIAL_IDR` (20,000,000 IDR; closed records, where only percentages matter)."*

```
store.init_paper_state  :417  INSERT INTO paper_state (..., cash_usd, equity_usd, initial_cash_usd, ...)
                              VALUES (..., cash0, cash0, cash0, ...)      # written once
store.write_paper_state :449  UPDATE paper_state SET cash_usd=%s, equity_usd=%s, last_session=%s,
                              pending_session=NULL, pending_decision=false ...
```

`initial_cash_usd` has exactly one writer and no updater. There is no deposit path, no cashflow
table, and no column that records money arriving. **Measured:** the grep for every spelling of the
concept across `engine/src`, `web/lib`, `web/app` and `db/migrations` returns only the English word
"contributes" in six unrelated docstrings.

### Entry Point E: the published lab snapshot and the luck check (R7)

**Location:** `lab/store.write_snapshot` → `web/data/lab.json` → `web/lib/sera/derive.ts`

1. `write_snapshot` resolves **one** gate and judges every row against the same N.
2. `published_verdict(conn, t, at=g)` splits on window: `dev` → `verdict(...)`, which decides the
   luck test on `dsr_at`; `test` → `owner_failures(trial)` **and nothing else**, `dsr` carried
   verbatim.
3. `_snapshot_trial` writes the record (`failed`/`eligible`/`dsr`/`nTrialsAtRun`) and the verdict
   (`failedNow`/`eligibleNow`/`dsrNow`). **It publishes no marker of whether the gate applied.**
4. `derive.ts:103` `conditionOk(trial,'dsr')` returns `!trial.failedNow.some(f => f.startsWith('DSR >= '))`
   — for a test row, `true`, i.e. a green tick on a score of 0.51 against a stated bar of 0.90.

### Entry Point F: the nightly, while paused (R5, R8)

**Location:** `.github/workflows/nightly.yml`
**Trigger:** `cron '17 6 * * 2-6'` (06:17 UTC = **13:17 WIB**) plus retries at 09:41 and 12:41 UTC.
**Concurrency:** `group: seer-db-writer`, `cancel-in-progress: false`.
**`PAPER_PAUSED: 'true'`** — skips Veto, Paper, Paper check, Explain. Migrate, Nightly (bars) and
Sean marks still run, so **a new migration still applies while paused**, but no `paper_start` is
written and no session is stepped. That is what makes a roster migration safe to land now.

The three resume conditions are written above the switch and map one-to-one onto this plan set:
(1) `paper/benchmark.py` threads `cost_model`; (2) C is decided — the bracket path has no gotrade
branch; (3) the lab has answered the name count and has a capital model matching reality.

### Entry Point G: a rotation reminder (R9)

**Location:** `web/lib/sean/reminders.ts:176` `buildReminders`

```
holdings  = Σ over input.held      -> {symbol, shares, price, value, picked}
planValue = Σ holdings.value                                             # :196
planSize  = budgetUsd > 0 ? budgetUsd : planValue > 0 ? planValue : null  # :197
  sell: a holding the picks no longer name     -> usd = h.value          # :205
  buy : a pick not held                        -> usd = weight × planSize # :213
  add/trim: only if resizes && |gap| >= max(MIN_TRADE_USD, RESIZE_BAND × planSize)  # :220
drafts.sort(ACTION_ORDER)  -> sell, trim, buy, add                       # :229
```

Cash is absent from every line. `planSize` can only ever be what the plan already holds, or a number
the owner typed into `sean_link.budget_usd`.

### Data Persistence

| Store | What | Written by |
|---|---|---|
| Neon (`DATABASE_URL_UNPOOLED`) | `runs`, `strategies`, `paper_state`, `book_targets`, `book_positions`, `orders`, `equity_snapshots`, `news_vetoes`, `sean_*` | the nightly and the other `seer-db-writer` workflows |
| `lab/lab.sqlite` | 45 methods, **128 trials (126 dev + 2 test)**, 53 insights | `engine/src/seer_engine/lab/store.py` |
| `web/data/lab.json` | the published snapshot the Sera pages import at build time | `store.write_snapshot`, committed by `lab stage` |
| `strategies.params->'spec'` | each entry's frozen spec, digest-checked every night | `paper/roster.py:spec` / `spec_digest` |

### Exit Points

- The nightly writes Neon in one transaction; a red Paper check turns the run red (GitHub emails the
  owner) but paper state is already committed.
- The site renders from Neon at request time (`force-dynamic`) and from `web/data/lab.json` at build.
- `seer sean calibrate` reports every receipt's residual against the fitted schedule.

---

## Key Data Structures

### `TradeRules`
**Location:** `engine/src/seer_engine/sim/rules.py:60-141`
**Fields of interest:** `engine: Literal["bracket_v0","book"]`, `cost_rate: Decimal = 0.001`,
`cost_model: CostModel = "flat"`.
**Invariants it enforces:** `cost_model == "gotrade"` requires `cost_rate` at its default (:131);
`engine == "bracket_v0"` requires *every* field to equal `_V0_LEVERS` (:136-138); `id == "design-v0"`
requires `engine == "bracket_v0"` (:139).
**Presets:** 15, of which exactly two are Gotrade — `MONTHLY_HOLD_FRAC_GOTRADE` and
`MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE`, both used by **no roster entry**.

### `FeeRegime` / `GotradeSchedule` / `FeeParts`
**Location:** `engine/src/seer_engine/sim/costs.py:93-238`
Current regime (since 2026-06-16): trading **0.2% half-up, minimum $0.10**; regulatory 0.054%
rounded up, capped $0.11, plus an uncapped 0.04% sell extra; **11% PPN** on trading+regulatory,
rounded half-down. Fitted to 30 receipts; the one that does not match is named rather than smoothed.

### `PaperState`
**Location:** `engine/src/seer_engine/paper/store.py:358`
**Fields:** `strategy_id`, `last_session`, `cash_usd`, `equity_usd`, **`initial_cash_usd`**,
`usd_idr`, `pending_session`, `pending_decision`.
**Note for R3:** `initial_cash_usd` is the only record of capital and it is write-once. There is no
field, table or code path that can record money arriving after the start.

### `ReminderInput` / `ReminderPlan`
**Location:** `web/lib/sean/reminders.ts:92,113`
**Note for R9:** `ReminderInput` carries `held`, `outside`, `closes`, `budgetUsd`, `orders`, `marks`
— no cash. `ReminderPlan.planSize` is therefore holdings-or-a-typed-number, and every buy is sized
from it.

### `LabTrial`
**Location:** `web/lib/sera/types.ts:99`
**Note for R7:** carries `window`, the record (`failed`, `eligible`, `dsr`, `nTrialsAtRun`) and the
verdict (`failedNow`, `eligibleNow`, `dsrNow`). No field says whether the luck gate applies.
`Verdict.derived` exists engine-side, is not published, and would not serve anyway — it is also
`False` for a *dev* row whose DSR could not be evaluated, which is a miss, not an exemption.

---

## Dependencies

### Configuration / Environment
- `DATABASE_URL_UNPOOLED`, `MASSIVE_API_KEY` — required by the nightly.
- `PG_TEST_URL` — required for the engine's DB tests; documented at `engine/tests/conftest.py:6`
  (`postgresql://postgres:pg@localhost:55432/postgres` locally).
- `SEER_LAB_COSTS_LIVE`, `SEER_RESEARCH_STORE` — opt-in for the live lab-costs test and the research
  store.
- `PAPER_PAUSED` — workflow-level env, `'true'` since `d44fa78`.

### External services
GitHub Actions, Neon, Massive (bars/splits/dividends), Finnhub, the LLM endpoint, Yahoo (Sean
marks), Vercel.

### Operational
- `engine/.research/` is needed for lab runs and takes ~30 min to rebuild from Neon; the
  `sync-research-store` skill moves it instead.
- The worktree's `web/node_modules` is **hardlinked**, not symlinked (a symlink passes vitest and
  tsc, then fails `next build` with a misleading "filesystem root" error).

---

## Reference List

### R1 / R4 — every site that charges a fee

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `GOTRADE` schedule | `sim/costs.py:199` | const | `engine.sim` |
| `fee_parts` / `gotrade_cash` / `gotrade_shares_for` | `sim/costs.py:241,248,260` | def | `engine.sim` |
| `TradeRules.cost_rate` / `.cost_model` | `sim/rules.py:87,88` | field | `engine.sim` |
| the gotrade/cost_rate guard | `sim/rules.py:131-134` | validation | `engine.sim` |
| `_ENGINES` (no bracket engine) | `sim/rules.py:45` | const | `engine.sim` |
| `Engine` literal | `sim/rules.py:35` | type | `engine.sim` |
| `_V0_LEVERS` / `_lever_values` | `sim/rules.py:148,143` | const/def — the reservation | `engine.sim` |
| the `bracket_v0` reservation | `sim/rules.py:136-140` | validation | `engine.sim` |
| `LEVERS_SINCE_PINS` (`cost_model: "flat"`) | `sim/rules.py:234-237` | const | `engine.sim` |
| `MONTHLY_HOLD_FRAC_GOTRADE` | `sim/rules.py:203` | preset — **unused by the roster** | `engine.sim` |
| `MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE` | `sim/rules.py:204-206` | preset — **unused** | `engine.sim` |
| `PRESETS` (15) | `sim/rules.py:208-224` | const | `engine.sim` |
| book charge sites (**already comply**) | `sim/book.py:339,345,352,367` | def | `engine.sim` |
| `COST_RATE` | `sim/model.py:25` | const — the flat bracket rate | `engine.sim` |
| `buy_cost` / `sell_proceeds` | `sim/model.py:76,84` | def — no rules parameter | `engine.sim` |
| `_ONE_PLUS_COST` | `sim/sizing.py:31` | const — computed at import | `engine.sim` |
| `size_picks` | `sim/sizing.py:108` | def — **no rules parameter** | `engine.sim` |
| `_whole_shares` | `sim/sizing.py:95` | def | `engine.sim` |
| sizing charge sites | `sim/sizing.py:136,166` | call | `engine.sim` |
| `step` | `sim/lifecycle.py:128` | def — **no rules parameter** | `engine.sim` |
| `close_unpriced` | `sim/lifecycle.py:208` | def | `engine.sim` |
| lifecycle charge sites | `sim/lifecycle.py:73,74,189` | call | `engine.sim` |
| split charge site | `sim/split_adjust.py:175` | call | `engine.sim` |
| `_whole_shares` / `_fractional_shares` / `fractional_buy_cost` / `_whole_buy_cost` | `backtest/benchmark.py:109,121,135,143` | def — **all already take `cost_model`** | `engine.backtest` |
| `buy_and_hold(cost_model=…)` | `backtest/benchmark.py:160-187` | def | `engine.backtest` |
| `spy_curves(cost_model=…)` | `backtest/benchmark.py:252-258` | def | `engine.backtest` |
| **the lab benchmark already complies** | `backtest/dev.py:433-435` | call | `engine.backtest` |
| live SPY: recorded fee | `paper/benchmark.py:170` | call — **flat, 3rd site** | `engine.paper` |
| live SPY: entry buy | `paper/benchmark.py:249,250` | call — **flat** | `engine.paper` |
| live SPY: reinvestment buy | `paper/benchmark.py:276,278` | call — **flat** | `engine.paper` |
| `SEED_ROWS` | `paper/roster.py:735` | const — the roster | `engine.paper` |
| `roster.spec` / `rules_dict` / `spec_digest` | `paper/roster.py` | def | `engine.paper` |
| `is_pinned_default` | `sim/rules.py:240` | def — why a flip moves the digest | `engine.sim` |
| the roster-change rule | `docs/runbooks/paper-trading.md:60-68` | doc | `docs` |
| migration pattern | `db/migrations/013_roster_first_night.sql` (also 010, 011) | sql | `db` |
| `real_costs` twin builder (`-GT`/`-FLAT`) | `lab/real_costs.py:146-164` | def | `engine.lab` |

### R3 — capital and contributions

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `INITIAL_IDR = 20000000` | `backtest/runner.py:46` | const — **twice the real capital** | `engine.backtest` |
| `PAPER_INITIAL_IDR = 10000000` | `paper/capital.py:11` | const — the real capital | `engine.paper` |
| `initial_cash_usd(idr, usd_idr)` | `sim/model.py` | def | `engine.sim` |
| `run_backtest(..., initial_idr=INITIAL_IDR)` | `backtest/runner.py` | def | `engine.backtest` |
| `run_book(..., initial_idr=INITIAL_IDR)` | `backtest/book_runner.py` | def | `engine.backtest` |
| `PaperState.initial_cash_usd` | `paper/store.py:358` | field | `engine.paper` |
| `init_paper_state` INSERT | `paper/store.py:417` | sql — **write-once** | `engine.paper` |
| `write_paper_state` UPDATE | `paper/store.py:449` | sql — never touches initial cash | `engine.paper` |
| `paper_state` table | `db/migrations/003_paper.sql` | sql | `db` |
| `cagr_between` | `backtest/metrics.py:100` | def | `engine.backtest` |
| `Metrics.cagr` | `backtest/metrics.py:77,145` | field | `engine.backtest` |
| `trials.cagr` / `spy_tr_cagr` | `lab/store.py:275,285` | schema | `engine.lab` |
| `beats SPY TR` condition | `lab/store.py:987` | def — `total_return > spy_tr_return` | `engine.lab` |
| **no deposit concept anywhere** | measured grep, 6 hits, all the word "contributes" | — | — |

### R6 — the guard and the pins

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| the `^SKIPPED` guard | `.github/workflows/engine-ci.yml:65-73` | ci | `.github` |
| `_SKIP_REASON` | `engine/tests/conftest.py:45-49` | const — the signature to match | `engine.tests` |
| `pg_url` fixture skip | `engine/tests/conftest.py:83` | call | `engine.tests` |
| `COMMITTED_DEV_TRIALS = 110` | `engine/tests/test_lab_npolicy.py:22` | const — **should be 126** | `engine.tests` |
| `COMMITTED_METHODS = 23` / `_PR = 2.442` / `_RHO = 0.595` | `test_lab_npolicy.py:23-25` | const | `engine.tests` |
| the skipping pinned test | `test_lab_npolicy.py:311-340` (skips at :319) | test | `engine.tests` |
| `dev_trial_count` | `lab/store.py:747` | def — **126 today** | `engine.lab` |
| `effective_n` / `correlation` | `lab/npolicy.py` | def | `engine.lab` |
| deliberate skips (9 sites) | `conftest.py:83`, `test_lab_costs.py:265`, `test_lab_npolicy.py:287,319`, `test_lab_methods.py:117`, `test_lab_status.py:277`, `test_paper_roster.py:651`, `test_cost_model_pins.py:38`, `test_lab_gate_policy.py:861` | test | `engine.tests` |

### R7 — every site that decides or renders the luck check

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `published_verdict` (the dev/test split) | `lab/store.py:1243` | def | `engine.lab` |
| `verdict` (dev only) | `lab/store.py:1175` | def | `engine.lab` |
| `dsr_at` | `lab/store.py:1100` | def | `engine.lab` |
| `_snapshot_trial` (**publishes no marker**) | `lab/store.py:1745` | def | `engine.lab` |
| `write_snapshot` single-gate resolution | `lab/store.py:1911-1915` | call | `engine.lab` |
| `LUCK_LABEL_PREFIX` / `DSR_LABEL` | `lab/store.py:131-132` | const | `engine.lab` |
| `lab export-json` / `lab stage` | `commands/lab.py:1583,1619` | cli | `engine.commands` |
| `LabTrial` | `web/lib/sera/types.ts:99` | type | `web/lib/sera` |
| `DSR_FAILURE_PREFIX` / `conditionOk` | `web/lib/sera/derive.ts:48,103` | const/def | `web/lib/sera` |
| `gateChecks` / `conditionsPassed` / `misses` / `funnel` / `bestVariant` | `derive.ts:152,164,169,196,188` | def | `web/lib/sera` |
| `marks` / `markLabel` / `conditionTip` / `conditionSentence` | `web/app/sera/methods/view.ts:150,154,165,186` | def | `web/app/sera` |
| "Every variant" table (**iterates `trials`, not `variants`**) | `web/app/sera/methods/[id]/page.tsx:293-345` | render | `web/app/sera` |
| DSR column + `at N {gate.dsrN}` | `[id]/page.tsx:334-337` | render | `web/app/sera` |
| the failing assertion | `web/lib/sera/lab.test.ts:50-67` | test | `web/lib/sera` |
| `lab.version` pin (3 today) | `web/lib/sera/lab.test.ts:8` | test | `web/lib/sera` |
| the snapshot | `web/data/lab.json` (128 trials) | data | `web/data` |

### R5 — the blank panel

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `showOrders` | `web/app/(app)/positions/page.tsx:31` | def — the whole defect | `web/app` |
| `pendingOrders` / `bookPreview` guarded away | `positions/page.tsx:34,35` | call | `web/app` |
| `noOrders` / `emptyState` (the vocabulary to reuse) | `positions/page.tsx:161,171` | def | `web/app` |
| `paperWarn` | `positions/page.tsx:46` | def — the "failed" state, already right | `web/app` |
| the coral `run.stale` alarm | `web/app/(app)/page.tsx:80` | render | `web/app` |
| `isStale` / `nextUsSession` / `wibDate` | `web/lib/session.ts:32,24` | def | `web/lib` |
| `runStatus` (the only producer of `stale`) | `web/lib/data.ts:132` | def | `web/lib` |
| `picksMonthlySizesWeekly` / `RESIZE_BAND` | `web/lib/cadence.ts:16,25` | def/const | `web/lib` |
| `PAPER_PAUSED` | `.github/workflows/nightly.yml:70` | ci — the 5th state, unshown | `.github` |

### R9 — the rotation reminders

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `buildReminders` | `web/lib/sean/reminders.ts:176` | def | `web/lib/sean` |
| `planValue` / `planSize` (**no cash**) | `reminders.ts:196,197` | def | `web/lib/sean` |
| `MIN_TRADE_USD = 10` | `reminders.ts:25` | const — re-tune against the fee curve | `web/lib/sean` |
| `ACTION_ORDER` (sell before buy) | `reminders.ts:126` | const — already correct | `web/lib/sean` |
| the add/trim band | `reminders.ts:220` | def | `web/lib/sean` |
| `ReminderInput` | `reminders.ts:92` | type — the shape that must gain cash | `web/lib/sean` |
| *"receipts never show the cash balance"* | `web/lib/sean/ledger.ts:3` | doc — why a schedule is needed | `web/lib/sean` |
| `sean_link.budget_usd` | `db/migrations/015_sean.sql:47-53` | schema — the manual lever | `db` |
| `sean_reminder_marks` / `sean_marks` | `db/migrations/015_sean.sql` | schema | `db` |

---

## Measured Evidence

Everything here was produced in this session, against the worktree's base `8be7117`. The owner
prefers measuring to estimating.

### The Gotrade fee curve, by calling `sim.costs.fee_parts` directly

```
   order     buy    sell  round trip  x vs 0.200%
      10    0.12    0.13      2.500%     12.50x
      25    0.13    0.14      1.080%      5.40x
      28    0.13    0.16      1.036%      5.18x   <- the owner's slot today
      50    0.14    0.17      0.620%      3.10x
      75    0.22    0.26      0.640%      3.20x
     100    0.29    0.33      0.620%      3.10x
     200    0.57    0.65      0.610%      3.05x
     560    1.37    1.62      0.534%      2.67x
    1000    2.34    2.79      0.513%      2.56x
    5000   11.22   13.44      0.493%      2.47x
```

Reproduces the handover's §2 table exactly. The asymptote is ~2.5× the assumed rate; everything above
it is the $0.10 floor, which binds below about $50 an order.

**One number worth naming for R9:** at `MIN_TRADE_USD = 10` a corrective trade pays **2.5% round
trip**. At $25 it pays 1.08%; at $50, 0.62%. A $10 add to fix a 1%-of-plan drift destroys more value
than it recovers. The constant needs re-tuning against this curve, not leaving at a round number.

### The funding ramp, at 17,841 IDR/USD

```
month  0    10M IDR  $  560.51  slot20 $  28.03 -> 1.035%   slot11 $  50.96 -> 0.628%
month  1    15M IDR  $  840.76  slot20 $  42.04 -> 0.737%   slot11 $  76.43 -> 0.641%
month  2    20M IDR  $ 1121.01  slot20 $  56.05 -> 0.660%   slot11 $ 101.91 -> 0.618%
month  3    25M IDR  $ 1401.27  slot20 $  70.06 -> 0.614%   slot11 $ 127.39 -> 0.612%
month  6    40M IDR  $ 2242.03  slot20 $ 112.10 -> 0.624%   slot11 $ 203.82 -> 0.618%
month 12    70M IDR  $ 3923.55  slot20 $ 196.18 -> 0.607%   slot11 $ 356.69 -> 0.558%
month 24   130M IDR  $ 7286.59  slot20 $ 364.33 -> 0.557%   slot11 $ 662.42 -> 0.525%
```

Reproduces §2b exactly. By month 3, 20 names costs 0.614% and 11 names costs 0.612% — a difference of
two thousandths of one percent. **The fee case for concentration is gone by month three**, which is
why §2b forbids planning a name-count cut on fee grounds, and why R2 is a merits question.

### The bracket path cannot express `gotrade` — executed, not read

```
DESIGN_V0: design-v0 engine=bracket_v0 cost_model=flat
replace(DESIGN_V0, id='design-v0-gotrade', cost_model='gotrade')
  -> ValueError: engine 'bracket_v0' is reserved for DESIGN_V0 (the unchanged §5 simulator)
replace(DESIGN_V0, id='bracket-gotrade', engine='bracket', cost_model='gotrade')
  -> ValueError: unknown engine 'bracket'; expected one of ('bracket_v0', 'book')
```

**This extends the handover.** §3b/Q4 name `sizing.py:31`'s `_ONE_PLUS_COST` as "the specific thing in
the way". It is *a* thing in the way, and the third one encountered. The first two are that there is
no bracket engine value other than the reserved `bracket_v0`, and that `size_picks` and `step` take
no rules at all. R4 is a signature change across the bracket path, not a branch inside it.

### The lab database, counted

```
total trials: 128
  window dev : 126
  window test: 2
methods: 45
methods with dev trials: 28
```

`COMMITTED_DEV_TRIALS = 110` is compared against `store.dev_trial_count`, which counts dev rows only.
**The re-pin target is 126, not the 128 the handover names** — 128 is the total. Re-pinning to 128
would leave `test_the_committed_evidence_at_110_dev_trials` skipping exactly as it does today, which
is the failure mode R6 exists to end. `web/data/lab.json`'s `gate.dsrN` already publishes 126.

### The published snapshot's two offending rows

```
version: 3
gate: dsrMin 0.9, dsrPolicy 'all-trials', dsrN 126, devStart 1993-01-29, devEnd 2015-10-16,
      testStart 2015-10-19, maxDrawdown 0.2, minProfitFactor 1.3, minTrades 100
summary: devTrials 126, testLooks 2, methods 45, byStatus{..., 'test-failed': 2, 'dev-eligible': 2}

TEST ROW trials[122]: M0021-B70-RAW       dsr=0.513013 dsrNow=0.513013
                      failedNow=['beats SPY TR']                      eligibleNow=False
TEST ROW trials[124]: M0029-B70-RAW-FRAC  dsr=0.388958 dsrNow=0.388958
                      failedNow=['beats SPY TR', 'max DD <= 20%']     eligibleNow=False
```

Both rows carry a score far under the 0.90 bar and neither lists a DSR failure — correct engine
behaviour, and the exact input that makes `conditionOk` return a green tick.

### The failing web test, reproduced

```
FAIL  lib/sera/lab.test.ts > publishes a verdict that agrees with the gate published beside it
AssertionError: expected [ 'M0021-B70-RAW', false ] to deeply equal [ 'M0021-B70-RAW', true ]
  lib/sera/lab.test.ts:57
Test Files  1 failed (1)
     Tests  1 failed | 9 passed (10)
```

Matches the handover's §10 exactly.

### No deposit concept exists — the grep, in full

`grep -rniE "deposit|contribut|top.?up|cashflow|add_cash"` over `engine/src`, `web/lib`, `web/app`,
`db/migrations` returns six hits, every one the English word "contributes" in an unrelated docstring
(`delisting.py:319`, `allocator.py:207,208`, `f_fundamental.py:72`, `coverage.py:164`,
`lab/runner.py:340,341`). There is no deposit path in the engine, the site or the schema.

### The two capital constants already disagree, deliberately

```
backtest/runner.py:46   INITIAL_IDR       = Decimal("20000000")
paper/capital.py:11     PAPER_INITIAL_IDR = Decimal("10000000")
```

`capital.py`'s comment states why: *"The backtests keep `backtest.runner.INITIAL_IDR` (20,000,000
IDR; closed records, where only percentages matter)."*

**That reason no longer holds, and this is the sharpest consequence of the fee measurement.** Under a
flat percentage fee, returns *are* scale-invariant and measuring at 20M to spend at 10M is harmless.
Under Gotrade's schedule the fee is **not** proportional — a $0.10 floor means a 20M book pays a
materially lower rate than a 10M book on the identical strategy (from the ramp table: 0.737% at 15M
against 1.035% at 10M). So the moment a lab method sets `cost_model="gotrade"`, the lab's 20M lump
measures a **cheaper** world than the owner lives in. Fixing `INITIAL_IDR` is not tidiness; it is a
correctness requirement that arrives with the fee model.

### The live paper benchmark has three flat sites, not two

The handover names `paper/benchmark.py:250` and `:278`. Measured, there is a third:
`:170` `cost_usd=q(price * n * COST_RATE)` — the fee recorded on every `Fill`. A fix that threads the
cost model through the two buy sites and leaves `:170` would record a fee that does not match the
cash actually moved.

### The functions the live benchmark calls already take the lever

`backtest/benchmark.py` `_whole_shares:109`, `_fractional_shares:121`, `fractional_buy_cost:135` and
`_whole_buy_cost:143` each carry `cost_model: CostModel = "flat"` with a working `"gotrade"` branch
(`gotrade_shares_for` / `gotrade_cash`). Resume condition 1 is therefore genuinely small: pass the
parameter at three sites and carry the model into `BenchmarkState`.

### The fee model reproduces the owner's real receipts, to the cent

Both sides of his 2026-10-07 Gotrade activity, recomputed through `costs.fee_parts`:

```
buy  $27.90 -> trading 0.10  reg 0.02  ppn 0.01  TOTAL 0.13   cash out  $28.0300   receipt: $28.03 paid
sell $72.51 -> trading 0.15  reg 0.07  ppn 0.02  TOTAL 0.24   proceeds  $72.2700   receipt: $72.27 received
```

Exact on both. **`sim/costs.py` is a fitted model that has now been validated out of sample against
live money, not an approximation.** Every fee number in this analysis inherits that standing.

### What it costs just to open the book — the owner's own 20 buys

```
20 buys of $27.90 = $558.00 deployed, fees $2.60 = 0.466%
```

Reproduces the owner's real $2.60 on $558 exactly. **0.47% of the book is gone before a single round
trip**, purely on the $0.10 floor at a $27.90 slot. This is the measured version of the whole
problem, taken from live money rather than a backtest, and it is the right calibration point for R2.

### The idle week the 25th deposit creates — measured, not "roughly a week"

Deposit on the 25th, first NYSE session of the following month (the rank session):

```
2026-10-25 -> 2026-11-02   8 days      2027-04-25 -> 2027-05-03   8 days
2026-11-25 -> 2026-12-01   6 days      2027-05-25 -> 2027-06-01   7 days
2026-12-25 -> 2027-01-04  10 days      2027-06-25 -> 2027-07-01   6 days
2027-01-25 -> 2027-02-01   7 days      2027-07-25 -> 2027-08-02   8 days
2027-02-25 -> 2027-03-01   4 days      2027-08-25 -> 2027-09-01   7 days
2027-03-25 -> 2027-04-01   7 days      2027-09-25 -> 2027-10-01   6 days
                                        mean 7.0 calendar days idle per month
```

**Mean 7.0 days, range 4–10.** The spread matters: a schedule that models "the 25th" as a fixed
7-day lag is wrong in ten months out of twelve, and December's 10-day gap is 2.5× February's 4. The
schedule object must deposit on the **calendar date** and let the session calendar produce the lag,
not bake a lag in. A schedule that deposited at the rotation instead would hold ~7 days less idle
cash every month and would quietly overstate returns.

### Paper's pause still applies migrations

`nightly.yml:48` — *"'true' skips Veto, Paper, Paper check and Explain; Migrate and Nightly (bars)
always run."* So a roster migration lands while paused, but no `paper_start` is written and no
session is stepped. **The roster rebuild can be merged now and will sit inert until the owner
resumes** — which is exactly the property that makes "optimise for getting it right once" possible.

---

## Impact Points (files that WILL need changes)

Grouped by the phase that owns them. No file appears under two phases.

**Phase 1 — R6, the CI guard and the aged pins**
1. `.github/workflows/engine-ci.yml` — the `^SKIPPED` guard at :70 must match `_SKIP_REASON`'s
   signature, not any skip.
2. `engine/tests/test_lab_npolicy.py` — the four `COMMITTED_*` constants, in a form derived from the
   committed database rather than typed.

**Phase 2 — R7, the luck gate and the test window**
3. `engine/src/seer_engine/lab/store.py` — `_snapshot_trial` publishes the gate-applies marker.
4. `web/lib/sera/types.ts` — `LabTrial` gains the marker; `lab.version` 3 → 4.
5. `web/lib/sera/derive.ts` — `conditionOk(trial,'dsr')` returns `null` for an ungated row.
6. `web/app/sera/methods/view.ts` — "not applicable" distinguished from "not measured".
7. `web/app/sera/methods/[id]/page.tsx` — the DSR column must not print `at N 126` on an ungated row.
8. `web/lib/sera/lab.test.ts` — the assertion reads the marker; the version pin moves.
9. `web/data/lab.json` — regenerated by `lab export-json`.
10. `engine/tests/test_lab_snapshot.py` — the engine-side snapshot-shape pin.

**Phase 3 — R1a, the live SPY benchmark pays Gotrade**
11. `engine/src/seer_engine/paper/benchmark.py` — `:170`, `:249-250`, `:276-279`; `BenchmarkState`
    carries the cost model.
12. `engine/tests/test_paper_benchmark.py` — the fee pins.

**Phase 4 — R4, the bracket path pays Gotrade**
13. `engine/src/seer_engine/sim/rules.py` — a third engine value, the reservation narrowed, a bracket
    Gotrade preset.
14. `engine/src/seer_engine/sim/model.py` — `buy_cost` / `sell_proceeds` take the cost model.
15. `engine/src/seer_engine/sim/sizing.py` — `size_picks` takes rules; `_ONE_PLUS_COST` goes.
16. `engine/src/seer_engine/sim/lifecycle.py` — `step` / `close_unpriced` take rules.
17. `engine/src/seer_engine/sim/split_adjust.py` — `:175`.
18. `engine/src/seer_engine/sim/__init__.py` — the re-exports.
19. `engine/src/seer_engine/paper/bracket.py` — the live caller.
20. `engine/tests/test_sim_sizing.py`, `test_sim_lifecycle.py`, `test_sim_rules.py`,
    `test_sim_scenario.py`, `test_paper_bracket.py`.

**Phase 5 — R3a, the contribution schedule and the lab's real capital**
21. `engine/src/seer_engine/sim/contributions.py` — **new**: the schedule as a pure value object.
22. `engine/src/seer_engine/backtest/runner.py` — `INITIAL_IDR` → the real 10M; the schedule reaches
    the session loop.
23. `engine/src/seer_engine/backtest/book_runner.py` — `run_book` takes the schedule.
24. `engine/tests/test_backtest_runner.py`, `test_backtest_dev.py`, new `test_sim_contributions.py`.

**Phase 6 — R3b, paper accepts a deposit**
25. `db/migrations/016_contributions.sql` — the cashflow record.
26. `engine/src/seer_engine/paper/store.py` — a deposit path beside the write-once `initial_cash_usd`.
27. `engine/src/seer_engine/paper/book.py` — the deposit applied on its session.
28. `engine/tests/test_paper_store.py`, `test_paper_book.py`.

**Phase 7 — R3c, money-weighted return and a dollar-cost-averaged SPY**
29. `engine/src/seer_engine/backtest/metrics.py` — a money-weighted measure beside `cagr`.
30. `engine/src/seer_engine/backtest/benchmark.py` — `buy_and_hold` / `spy_curves` take the schedule.
31. `engine/src/seer_engine/backtest/dev.py` — the gate restated.
32. `engine/src/seer_engine/lab/store.py` (schema + `owner_failures`) — **note: phase 2 also edits
    this file; phase 7 quotes it as phase 2 leaves it.**
33. `engine/tests/test_backtest_metrics.py`, `test_backtest_benchmark.py`.

**Phase 8 — R2, how many names, measured**
34. `engine/src/seer_engine/lab/` — the N sweep as registered lab variants at Gotrade fees under the
    funding plan.
35. `docs/` — the measured answer, written down.

**Phase 9 — R5, the blank panel's five states**
36. `web/lib/session.ts` or a new sibling — the classification and the next-decision time, pure.
37. `web/app/(app)/positions/page.tsx` — `showOrders` becomes a classified state.
38. `web/app/(app)/page.tsx` — routine expiry stops rendering as an alarm.
39. `web/app/(app)/positions/positions.module.css`, `web/app/(app)/today.module.css`.
40. `web/lib/session.test.ts` plus a new test for the classifier.

**Phase 10 — R9, Sean sizes a rotation from cash**
41. `web/lib/sean/reminders.ts` — `ReminderInput` gains cash; `planSize` becomes holdings + cash;
    `MIN_TRADE_USD` re-tuned.
42. `web/lib/sean/cash.ts` — **new**: cash from the schedule less net buys plus net sells.
43. `web/app/sean/` — the plan surface and the settlement note.
44. `web/lib/sean/reminders.test.ts`, new `cash.test.ts`.

**Phase 11 — R8, one daily line**
45. `.github/workflows/watch.yml` — **new**; it must live outside `nightly.yml`.
46. `docs/runbooks/monitoring.md` — **new**.

**Phase 12 — R1b, the rebuilt roster**
47. `engine/src/seer_engine/paper/roster.py` — the successor `SEED_ROWS` entries.
48. `db/migrations/017_roster_real_fees.sql` — the display rows, in 013's style.
49. `engine/tests/test_paper_roster.py` — the new digests.
50. `docs/runbooks/paper-trading.md` — the roster table, the fee section, and the stale schedule line
    at :76 (`23:00 UTC Mon-Fri (06:00 WIB)`, which no longer exists — measured, still present at
    `8be7117`).
51. `.github/workflows/nightly.yml` — the resume conditions rewritten to state what now holds. **The
    switch is not flipped** (see Decisions).

**This document describes. The plan files prescribe.**
