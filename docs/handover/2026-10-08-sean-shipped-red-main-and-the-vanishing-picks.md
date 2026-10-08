# Handover: paper is paused, the roster must be rebuilt to pay Gotrade's real fees

**Date:** 2026-10-08 (rewritten 09:10 WIB, superseding this file's first version)
**Branch:** `main` @ `d44fa78`
**Pass this file to `/analyze`.** Section 8 is the list of questions to settle. Everything above it
is verified fact with the command that verified it. Where an earlier claim of mine was wrong, the
correction is marked **CORRECTED** and the wrong version is stated too, so nobody re-derives it.

---

## 0. State of play, in plain words

**Paper trading is paused and the clock is frozen at zero stepped sessions.** Nothing is broken and
nothing was lost. The pause is deliberate: the roster has to be rebuilt so every method pays
Gotrade's real fees, that rebuild costs no paper history *only while zero sessions have been
stepped*, and three inputs the rebuild needs are not ready yet. Pausing buys unlimited time at
zero cost.

The owner's own Gotrade receipts (via Sean) showed the fees are far higher than every lab trial has
assumed. That is the thread that runs through everything below.

Two unrelated things are also broken and are described here: CI has been red since the Sean merge,
and the lab's published snapshot contradicts itself on two rows.

---

## 1. The operational state right now (verified)

`PAPER_PAUSED: 'true'` in `.github/workflows/nightly.yml` (commit `d44fa78`, pushed 2026-10-08
08:55 WIB, before that day's 13:17 WIB run).

- **Skipped while paused:** Veto, Paper, Paper check, Explain.
- **Still running:** Migrate, Nightly (bars), Sean marks. Market data stays current.

Frozen state, which the rebuild depends on staying frozen:

```
paper_state.last_session   = 2026-10-06   (no session has been stepped)
paper_state.pending_session= 2026-10-07   pending_decision = true for the four quant entries
book_targets               = 80 rows for 2026-10-07 (20 per quant method)
orders                     = 4 rows for 2026-10-07
equity_snapshots           = starting rows only, 560.5067 USD
```

The resume conditions are written into the workflow above the switch. Do not resume until all three
hold, or the rebuilt roster is not actually clean — they are sections 3 and 8 below.

## 2. Gotrade's real fees, measured (verified)

Sean fitted `engine/src/seer_engine/sim/costs.py` to 30 of the owner's real order receipts. Current
regime (since 2026-06-16): trading **0.2% with a $0.10 minimum**, regulatory 0.054% capped $0.11,
sell adds 0.04% uncapped, then **11% PPN** on trading+regulatory. Earlier regimes charged 0.3%, so
Gotrade has got *cheaper*.

**The rate is not the main problem. The per-order floor is.** Computed by calling
`costs.fee_parts` directly:

| order | round trip | vs the assumed 0.200% |
|---|---|---|
| $10 | 2.500% | 12.5× |
| **$28** ← the owner's slot today | **1.036%** | **5.2×** |
| $50 | 0.620% | 3.1× |
| $100 | 0.620% | 3.1× |
| $560 | 0.534% | 2.7× |
| $5,000 | 0.493% | 2.5× |

Gotrade's genuine asymptotic cost is ~2.5× the assumed 0.1%/side. Everything above that is the
$0.10 minimum, which binds below ~$50 an order. The owner's book is 560.5067 USD across 20 names =
$28 a slot.

### 2a. Turnover is about one third, not full (verified)

`sim.book.Trade` is *"one closed holding episode: shares went 0 → >0 → 0"*, i.e. a completed round
trip. Design §14's committed trade counts over the 237.4-month dev window:

| entry | closed trades | exits/month | monthly turnover |
|---|---|---|---|
| RAW-FR `M0007-N20-RAW` | 1596 | 6.72 | **33.6%** |
| RMW-FR `M0022-W-TV16` | 1589 | 6.69 | 33.5% |
| MVW-FR `M0008-N30-C07` | 1223 | 5.15 | 25.8% |
| MOM-FR `M0002-REL-85` | 1148 | 4.83 | 24.2% |

So a monthly rotation moves ~13–14 orders, not 40. Realistic drag at today's slot size is **~4%/yr**,
not the ~12% a full-turnover assumption gives. The owner predicted this unprompted and was right.

### 2b. The floor self-resolves in about two months (verified) — **CORRECTED**

The owner is adding **5,000,000 IDR monthly to a 10,000,000 IDR start**. Nobody had modelled this.
At 17,841 IDR/USD, holding 20 names:

| month | IDR | slot | round trip | same at 11 names |
|---|---|---|---|---|
| 0 | 10M | $28 | **1.035%** | 0.628% |
| 1 | 15M | $42 | 0.737% | 0.641% |
| 2 | 20M | $56 | 0.660% | 0.618% |
| 3 | 25M | $70 | 0.614% | 0.612% |
| 6 | 40M | $112 | 0.624% | 0.618% |
| 12 | 70M | $196 | 0.607% | 0.558% |

**The $0.10 floor stops binding around month 2–3**, and from there 20 names costs essentially what
11 names costs.

**CORRECTED.** I earlier told the owner that the floor "stops binding at $50 an order, which means
roughly 11 names maximum", and suggested cutting the book to 10–12 names to save ~40% of cost. That
is wrong once the funding plan is included: it optimises a two-month transient and pays for it with
permanently worse diversification. **Do not plan a name-count reduction on fee grounds.** If the lab
tests concentration, test it on the merits.

## 3. What complies with Gotrade fees today, and what does not (verified) — **CORRECTED**

**CORRECTED.** I earlier speculated that the `cost_model` lever might be unable to express a
per-order minimum, and said that if so it was "the real gap". **It models the floor completely.**
`sim/book.py` branches on `cost_model == "gotrade"` at `_buy_cash:339`, `_sell_cash:345`,
`_fee:352` and `_shares_for:367`, and `_shares_for` does not multiply a rate — it *solves* for the
largest share count whose rounded buy cash fits the budget, precisely because the fee is not
proportional (`sim.costs.gotrade_shares_for`). The gap is narrower and more mundane:

| path | state | evidence |
|---|---|---|
| book engine (the four quant methods) | **can comply** | the four branches above |
| lab benchmark symmetry | **already complies** | `backtest/dev.py:435` passes `cost_model=c.rules.cost_model` into `spy_curves` — *"The benchmark pays what the candidate pays"* |
| **live paper benchmark (SPY)** | **cannot** | `paper/benchmark.py:250,278` call `fractional_buy_cost(b.open, shares)` with no third argument; the signature defaults to `"flat"` |
| **bracket engine (C)** | **cannot, at all** | `grep -nE "cost_model|gotrade" sim/lifecycle.py sim/sizing.py` returns nothing; `sizing.py:31` precomputes `_ONE_PLUS_COST` from the flat `COST_RATE` |
| every active roster entry | **not using it** | `params->'spec'->'rules'->>'cost_model'` is NULL for all six |

### 3a. Why compliance means NEW roster entries

`cost_model` sits in `sim.rules.LEVERS_SINCE_PINS` at its no-op `"flat"`, so moving a **started**
entry to `"gotrade"` changes its spec digest and `store.check_digest` refuses its next night.
`docs/runbooks/paper-trading.md:60-68` forbids editing a started entry. So compliance lands as new
roster entries with fresh paper clocks, migration-style (010/011/013 are the precedents).

That rebuild is **free while zero sessions are stepped**, which is exactly what the pause preserves.

### 3b. C stays, deliberately, as the daily-trading control — **OWNER REQUIREMENT**

C is the only daily entry (`design-v0`, cadence daily), and daily trading costs roughly **26%/yr**
on a $560 book at $28 slots (~4 orders/night × 250 nights × ~$0.145). That is not a reason to drop
it. The owner's standing instruction, 2026-10-08:

> *"we must always include a daily trading method like C in the roster because I want to see how bad
> it got if I had used daily trading on Gotrade like my initial plan"*

Daily trading was the owner's original plan. Keeping a daily entry on the board turns "that would
have been expensive" from an estimate into a measured number, forward, against the monthly books
running beside it on the same money and the same fees. It is a control, and it is the only way the
counterfactual ever gets answered.

**So the bracket path's missing `cost_model` support is a hard dependency of the rebuild, not an
optional extra.** A daily control that pays the assumed 0.1% while the monthly books pay Gotrade
measures nothing — it would make daily trading look *better* than it is, which is the opposite of
what this entry exists to show. `sim/lifecycle.py` and `sim/sizing.py` need a `gotrade` branch, and
`sizing.py:31`'s precomputed `_ONE_PLUS_COST = Decimal(1) + COST_RATE` is the specific thing in the
way. See Q4.

## 4. The capital model does not match reality (verified) — the biggest modelling gap

Two separate problems, and the second is larger:

1. `backtest/runner.py:46` `INITIAL_IDR = Decimal("20000000")`. The owner actually started with
   **10,000,000 IDR** (`paper_state.initial_cash_usd` = 560.5067 USD at 17,841). The lab measures at
   twice the real capital, and because the fee floor is size-dependent, that is the wrong cost
   curve.
2. **Nothing in the engine models adding money at all.**
   `grep -rniE "deposit|contribution|top.?up|cashflow|add_cash" engine/src/seer_engine/` returns
   nothing. Every lab result assumes a lump sum that never grows, while the owner's real plan is
   10M + 5M monthly, forever.

The owner's words: *"we should finetune the lab to do the experiment as close as possible to the way
I plan to do the real trade (so, the lab must consider my plan to put in 5 million monthly as
well)"*.

Note for whoever plans this: **CAGR is not well defined once contributions exist.** A deposit raises
ending equity without being a return. This needs a money-weighted measure (IRR / modified Dietz),
and every gate phrased against CAGR or "beats SPY TR" has to be restated in whatever measure is
chosen, for the methods *and* the benchmark. That is a design question, not an implementation
detail.

## 5. The picks did not vanish, and they are absent 3 weeks in 4 by design (verified)

**What happened.** At ~20:30 WIB on 2026-10-07 the roster published recommendations; by morning the
page was blank and it read as data loss. The data was never touched — section 1 lists the 80 rows.

**Why the page was blank.** `web/app/(app)/positions/page.tsx:30` is
`showOrders = !!strat && !strat.isBenchmark && !run.stale`, and `web/lib/session.ts:32` —
*"Picks are stale when the latest successful run targets an earlier session."* Executed, not read:

```
now = 2026-10-08T01:17Z (08:17 WIB, 21:17 ET)
nextUsSession(now)         = 2026-10-08
isStale('2026-10-07', now) = true      ->  showOrders = false
```

The picks were a decision for the 2026-10-07 US session, which closed at 03:00 WIB. A spent decision
must not look actionable. That part is the design working.

**The part that is NOT just expiry.** Running the engine's own predicates against each entry's real
rules:

```
2026-10-07 (Wed)  all four quant: rank=False resize=False  -> published only because it was the KICKOFF
2026-10-08 (Thu)  all four:       rank=False resize=False  -> no decision
2026-10-09 (Fri)  all four:       rank=False resize=False
2026-10-12 (Mon)  RMW-FR only:    resize=True
2026-11-02 (Mon)  all four:       rank=True                -> first real re-rank
```

`decide_book`'s contract: *"Otherwise `(None, False)` and the allocator is not called: a session that
is neither."* No `book_targets` written, `pending_decision` stays false.

Cadences from `strategies.rules_id`: RAW-FR / MOM-FR / MVW-FR = `monthly-hold-frac`; RMW-FR =
`monthly-rank-weekly-resize-frac`; C = `design-v0` daily; SPY = benchmark buy-and-hold.

So the pending-picks panel renders the same blank for **four** different situations:

- **(a) holding, nothing was due** — the normal state, ~3 weeks out of 4, running to 2026-11-02
- (b) the decision expired at the NY close — normal, daily
- (c) nothing was ever produced
- (d) the pipeline failed

The owner read (a)/(b) as data loss once already. (a) is the common case, not an edge case.

## 6. `main` is red, two independent causes (verified)

Failing runs `37654291246`, `37697386965`, `37698865353`, `37711466542`. Neither cause is Sean.

**6a. The engine skip-guard misfires.** `.github/workflows/engine-ci.yml:70` fails the build on any
`^SKIPPED` line, with the message *"engine tests were skipped; PG_TEST_URL did not reach pytest"* —
now false, since the run reports `3362 passed, 2 skipped`. Two deliberate `skipif`s trip it:
`test_lab_costs.py:265` (needs `SEER_LAB_COSTS_LIVE`, unset in CI) and `test_lab_npolicy.py:319`
(skips because `COMMITTED_DEV_TRIALS = 110` while `lab/lab.sqlite` now holds **128**).

**6b. A real lab-snapshot inconsistency.** `web/lib/sera/lab.test.ts:50` asserts a scored trial
misses the luck check exactly when its score is under the bar. Two rows violate it:

| candidateId | dsrNow | failedNow | window |
|---|---|---|---|
| `M0021-B70-RAW` | 0.513013 | `['beats SPY TR']` | **test** |
| `M0029-B70-RAW-FRAC` | 0.388958 | `['beats SPY TR', 'max DD <= 20%']` | **test** |

Both are `window: "test"` rows; the published gate is `dsrMin 0.90, dsrPolicy "all-trials",
dsrN 126`. This assertion has never seen a test-window trial before — the lab went from 0 test looks
to 2. The DSR bar is a *dev-window* multiple-testing correction; a pre-registered confirmatory look
is not luck-gated the same way, which is why `failedNow` correctly omits a DSR failure. The data
looks right and the test encodes a dev-only assumption that has expired.

## 7. Sean, as shipped (verified)

7 phases, 116 files, ~40k insertions, merged `b16cffd`, migration 015 applied, set pruned. `/sean`
in the web app (Overview / Trades / Plan), `engine/src/seer_engine/sean/` (ledger, marks, equity,
calibrate), a GLM-4.6V screenshot reader, a nightly `sean marks` step (currently *"no orders yet"*).

Its real contribution is `sim/costs.py` and what it revealed. `449fa34` re-measured the roster at
real fees, **report only**, lab N unchanged:

| method | assumed fees | real Gotrade fees |
|---|---|---|
| RAW `M0007-N20-RAW` | +1502% | **+1126%** |
| MOM `M0002-REL-85` | +940% | **+763%** |
| MVW `M0008-N30-C07` | +727% | **+536%** |
| RMW `M0022-W-TV16` | +789% | **+543%** |
| SPY at the same fees | — | +350% |

All four still beat SPY, so no verdict is overturned. **Caveat that must travel with these figures:**
they average over a growth path from a 20M IDR lump to +1126%, so the floor binds hard in the early
years and is irrelevant later. The owner sits at the expensive end of that path today, so these
numbers understate his near-term drag.

## 8. Questions the analysis must settle

**Q1 — rebuild the roster so every entry pays Gotrade fees.** The owner's instruction:
*"every method in Seer roster including SPY, comply to Gotrade fees"*, and *"let's replace the
roster now, I want it clean"* — he chose replace-once-properly over replace-now-partially after
being shown the three blockers. Settle: the migration that retires the six entries and creates their
successors; threading `cost_model` through `paper/benchmark.py` so SPY is symmetric (the lab already
is — §3); what happens to C (§3b); and the new entries' parameters, which depend on Q2 and Q3. The
pause holds the clock at zero stepped sessions for as long as this takes, so optimise for getting it
right once.

**Q2 — how many names, decided on the merits.** The fee argument for concentration is a two-month
transient under the owner's funding plan (§2b) and should not drive this. The real question is
whether concentration helps or hurts a monthly momentum book over 18 months, and it is a lab
question. Note `M0007-N20-RAW`'s `N20` is a parameter, so variants are cheap to express.

**Q3 — make the lab measure what the owner will actually do.** 10,000,000 IDR start, 5,000,000
monthly, Gotrade fees with the floor. Requires: contribution support in the backtest (none exists),
`INITIAL_IDR` matching reality, and a money-weighted return measure plus the restatement of every
gate that is phrased in CAGR terms — for methods and benchmark alike (§4). This is the largest piece
of work in this handover and the one the owner asked for most directly.

**Q4 — make the bracket path pay Gotrade fees, so the daily control is honest.** C **stays** — the
owner requires a daily entry on the roster permanently, as the measured counterfactual for the
daily-trading plan he started with (§3b). That makes this a build, not a decision: `sim/lifecycle.py`
and `sim/sizing.py` have no `gotrade` branch, and `sizing.py:31` precomputes `_ONE_PLUS_COST` from
the flat `COST_RATE`, so a bracket fill cannot charge a per-order minimum today. Until that exists,
C would understate daily trading's cost and the control would be worse than useless. Settle also
what the control is *compared against* — it only answers the owner's question if it runs on the same
starting capital, the same monthly contributions and the same fee schedule as the monthly books.

**Q5 — the blank panel has four causes and one rendering.** §5. Whatever is shown must distinguish
(a) holding/nothing due — the common case — from (b) expired, (c) never produced and (d) failed, and
must never be mistakable for a live instruction. While paper is paused there is a fifth state to
show honestly: *paused*.

**Q6 — the CI skip-guard, and a constant that aged.** §6a. Narrow the guard to the signature it was
written for, and decide what `COMMITTED_DEV_TRIALS` should be now the lab holds 128 — prefer a form
derived from the committed database over a typed number, since it will age again.

**Q7 — the luck gate and the test window.** §6b. Options: the assertion excludes `window === 'test'`;
or the exporter stops publishing `dsrNow` on test rows; or test rows carry an explicit
"not luck-gated" marker both the UI and the test read. The deeper question is whether a test-window
look should carry a DSR at all.

**Q8 — nobody is watching.** The roster's first paper night produced picks and nobody was told; CI
went red for ~9 hours unnoticed; paper is now paused and nothing will announce it if that is
forgotten. Price a single daily line — session stepped y/n, picks published y/n, CI green y/n,
paper paused y/n — over a dashboard nobody opens.

## 9. Owner context

- The owner **is not a quant**. Prose stays plain: numbers with their meaning, no jargon without a
  gloss.
- The owner **prefers measuring to estimating**. Every number in this file was measured; do likewise.
- The owner reads times in **WIB**; every schedule in this repo is **UTC**. `nightly.yml`'s
  `'17 6 * * 2-6'` is 13:17 WIB, not 06:17. This mismatch already caused one alarm.
- Funding plan, which is now a modelling requirement: 10,000,000 IDR start, **+5,000,000 IDR every
  month**, indefinitely.
- **The roster must always carry a daily-trading method** (C today). Standing instruction, 2026-10-08:
  the owner's original plan was to trade daily on Gotrade, and he wants the cost of that measured
  forward rather than argued. Never retire the daily entry on cost grounds — being expensive is the
  finding it exists to produce.

## 10. Verification

- Production Neon, read-only, 2026-10-08 — `book_targets`, `orders`, `paper_state`,
  `equity_snapshots`, `strategies`. No write was issued.
- `isStale('2026-10-07', now)` executed against `web/lib/session.ts` via `npx tsx`: **true**.
- `is_rank_session` / `is_resize_session` executed against each entry's real `TradeRules`.
- `costs.fee_parts` called directly for the fee tables.
- Engine suite on `main`: `3362 passed, 2 skipped` with `PG_TEST_URL`
  (`postgresql://postgres:pg@localhost:55432/postgres`, documented at `engine/tests/conftest.py:6`)
  and `PYTHONPATH`. **Note:** an earlier run of mine reported 385 errors because I invented a
  connection string instead of reading that file. Read it.
- `lib/sera/lab.test.ts` reproduced locally: 1 failed, 9 passed.
- CI failures read from `gh run view --log-failed`.
- The `cost_model` code map in §3 read at each cited line.

## 11. What landed just before this

- `delisting-stress-roster-rules`, 5 phases, merged `3f112cf` — design §14 (the delisting stress
  test: no break-even at the measured hazard; at the pessimistic 5.091%/yr rate MVW-FR breaks even
  at −85.8% and RMW-FR sits at +0.01 pts/yr), method-lab §8 (the roster replacement rule), the
  dev-gate trades-bar guard, and the MOM-FR verdict (**keep**).
- `8a6c13d` — P3, P3b and P6a in `engine/package_readme.md` now state that design §14 does **not**
  cover them (different strategies, window and data source).
- `4cbdab0` — this file's first version, now superseded.
- `d44fa78` — the pause described in §1.
