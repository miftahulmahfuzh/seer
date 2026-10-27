# Code Analysis: the three unlanded items from sera-20261026-1320

**Type:** Bug Investigation (R1, R2) + Feature Implementation (R3)
**Date:** 2026-10-27 08:26:13
**Session ID:** 20261027-082613-F3K9
**Plan:** `docs/plans/FLOOR_RESERVATION_YARDSTICK_PLAN.md` (3 phases)
**Worktree:** `/home/miftah/.worktrees/seer/floor-reservation-yardstick`, branch `feature/floor-reservation-yardstick` (base `origin/main` @ `35b41bd`)

---

## User Input

### Original User Request

```
docs/plans/2026-10-27-sera-20261026-1320-handover.md

This handover is from the Sera coordinator session that just finished. Read it in full first; it
carries the leftover tasks, the open decision, and a list of traps that cost the previous session
real time.

Priorities as the handover states them, highest value first:
1. The printed-price floor repair, six code sites, measured and unlanded. The handover names all
   six and the three modules that merely delegate.
2. The order-reservation bug, which silently makes any unequal-weight book skip some of its own
   picks.
3. M0396, retrofitting the never-step-aside arm by amendment to the thirteen timing methods
   lacking one. No method id and no test look.

Do NOT act on the M0392 roster question. It was cancelled deliberately and the handover explains
why it must stay cancelled.

Two standing constraints from CLAUDE.md that bind you: never commit lab/lab.sqlite or
web/data/lab.json outside of `lab stage`, and commit explicit file paths only, never
`git commit -a`, because other sessions share this checkout.
```

### User-Provided Context

The handover `docs/plans/2026-10-27-sera-20261026-1320-handover.md` (179 lines), read in full.
Its load-bearing content for this analysis:

- the six price-floor sites and the three delegating modules, with line numbers (insight 773);
- the order-reservation description: *"Orders are reserved in rank order at the limit price and
  the budget counts the RESERVATION, never the fill. 98.3% of fills land under their limit and the
  slack is never handed back down the list. Six times in twenty years the unequal-weight book
  failed to buy a pick it had chosen... Not affordability: 2010-03-01 it held $11,936 cash against
  $251,853 equity and declined a $7,431 order."*;
- the M0396 queue row: *"Retrofit the never-step-aside yardstick by amendment to every recorded
  timing method that lacks one. No method id, no look."*, scoped by *"of the 21 methods with dev
  trials across `market-trend-switch`, `volatility-term-structure-gate`, `macro-regime-gate` and
  `stock-switch-timing`, 8 carry an arm invested >= 98% of the time and 13 do not"*;
- the explicit cancellation of the M0392 roster swap (insight 778), which this analysis does not
  touch;
- the trap list (funded-curve, backticks in `git commit -m`, never pipe a lab command through
  `grep`, `lab stage` targets the main checkout, a lab command migrates `lab.sqlite` on connect).

### User-Provided Files

- `docs/plans/2026-10-27-sera-20261026-1320-handover.md`

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Land the printed-price floor repair at the six code sites the handover names, and account for the three modules that merely delegate. |
| R2 | Fix the order-reservation bug that silently makes an unequal-weight book skip picks it has chosen. |
| R3 | M0396: retrofit the never-step-aside arm, by amendment, to the timing methods that lack one. No method id and no test look. |

R3's population as the handover states it is **thirteen**. Re-measured against `lab.sqlite` on
2026-10-27 it is **ten**: see §R3 below for the three methods that already carry the arm and why
the `max(trials.exposure) < 0.98` cutoff that produced thirteen is the wrong detector.

Explicitly out of scope by the user's own words: the M0392 roster question.

---

## Detailed Requirements Understanding

### R1 — the printed-price floor

**Problem statement.** Every stock screen in this lab compares a share price against a five-dollar
floor. The price it reads is the research store's **back-adjusted** close, which the vendor has
divided by every split applied since. The floor therefore removes the companies that split the
most — the companies that went up the most — instead of removing penny stocks. M0387 measured the
repair at +1.05 pts/yr money-weighted on dev, +0.87 on `.research-sv`, against +0.10 for a matched
blind draw, and it recovers 97% of what deleting the floor entirely recovers.

**What "landing it" can and cannot mean.** Two of the six sites are shared strategy modules
(`strategies/f_factor.py`, `strategies/f_fundamental.py`). The other four are **committed lab
method files** — `m0052`, `m0109`, `m0117`, `m0276` — all four of them recorded with a non-NULL
`methods.source_sha` and a verdict. `engine/tests/test_lab_methods.py::test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha`
asserts each such file's sha256 equals `store.latest_source_sha`, and the only tolerated mismatch
is a committed, unrecorded `Amendment` block that `runner.pending_amendment` resolves. **Editing
any of those four files to repair the floor turns that test red**, and it would also silently
change what their *recorded* arms do while their `config_digest` stays byte-identical — which is
exactly the thing the freeze exists to prevent.

**And the repair cannot be unconditional in the shared screens either.** `factor_rows` is reached
by 186 of the 243 lab method files, and `factor_rows` is called directly by 119 of them
(re-measured by the phase-1 planner with `grep -rln` restricted to
`engine/src/seer_engine/lab/methods/`; this session's wider pattern, which also matches a bare
mention in a comment, gives 187 and 120). An amendment exists to ask one more question of an idea *under
the same conditions as its recorded arms*; moving the pool under `factor_rows` would make every
future amendment arm of every recorded method incomparable with the arms it was written to be
measured against. R3 is itself exactly such a retrofit, and four of its ten methods
(`M0260`, `M0261`, `M0262`, `M0334`) call `factor_rows` directly. (`M0338` also calls it, but it
is one of the three methods the corrected census removes from R3's population — see §R3.)

**Nor can the basis become a params field.** `lab.method.config_text` canonicalizes `c.params`
through `backtest.registry._canon`, which enumerates every `compare=True` dataclass field; the
pinned-default drop-out is applied to `TradeRules` **only** (`pinned = isinstance(value, TradeRules)`,
`registry.py:323`). A new field on `FactorParams` or `FundamentalParams` therefore moves every
recorded `config_digest` that embeds one, and every pinned candidate digest in
`tests/test_registry.py`.

**Success criteria.** The printed basis becomes a supported, tested, reusable option of the two
shared screens, reachable without a dataclass field and without moving one byte of recorded
state; the five known real-world closes M0383 checked are pinned as a regression test; the four
frozen sites and the three delegating modules are documented, with the one legal route to
repairing them named.

**A standing dependency, recorded not solved here.** The printed close is
`close x Market.shares.raw_factor(symbol, d)`. The paper night's `Market`
(`paper/store.py:1523`) is built with history, membership, fx and fundamentals and **no shares**,
so `shares` is `EMPTY_SHARES`, `raw_factor` returns 1.0 for every symbol, and a repaired screen
would degrade silently back to the adjusted basis live (insights 778, 779). Supplying share counts
to the paper night is a table + migration + loader + nightly job; it is not in this plan set.

### R2 — the order-reservation bug

**Problem statement.** `sim/book.py` `step_book` step (4) sizes buys against a night-before budget
`available = book.cash + planned`, running a `committed` tally down the rank-ordered target list.
`committed` is incremented at `book.py:776` with `_buy_cash(price, shares, rules)` where `price` is
`_sizing_price(t, rules)` — the **limit**, `q(t.last x 1.02)` under `open_limit`. The actual fill
is computed afterwards at `book.py:789` as `_buy_cash(fill_price, shares, rules)` with
`fill_price = min(open, limit)`, and `committed` is never reconciled to it.

Two distinct leaks sit in that one line:

1. **Over-reservation.** Every fill under its limit leaves the difference reserved for the rest of
   the night. The handover measures 98.3% of fills landing under their limit.
2. **Never released.** `committed` is incremented *before* the bar lookup, so a target rejected
   `no_bar` (`book.py:779-781`) — an order that was never placed at all — keeps a full reservation
   against every later pick, and so does one rejected `unfilled` (`:787`) or shrunk by the cash
   clamp (`:791`).

The consequence the handover measured: six times in twenty years the unequal-weight book declined
a pick it had chosen, while the equal-weight and shuffled arms declined none — because under equal
weights `q(equity x t.weight)` is the binding term in `budget = min(q(equity * t.weight), available - committed)`,
and under unequal weights `available - committed` becomes binding first.

**The realism constraint this fix must respect, and the fork it creates.** Reserving at the limit
is what a live book has to do: the owner places the whole night's orders in the morning and cannot
know an early fill price before sizing a later order. Handing slack back down the list *within one
session* is therefore not free — it is information the night-before sizing does not have. Leak (2)
has no such defence: an order with no bar was never placed, and reserving cash for it is pure
accounting error.

**Success criteria.** The accounting is repaired so that a reservation tracks what the night
actually commits; a regression test reproduces a skipped pick on an unequal-weight book and shows
it bought after the fix; **no recorded trial, no pinned candidate digest and no live paper spec
digest moves**, which in this repo means the repair arrives as a `TradeRules` lever whose default
is the present behaviour (`LEVERS_SINCE_PINS`, four precedents: `resize_cadence`, `cost_model`,
`resize_basis`, `cash_yield`, `resize_band`).

### R3 — M0396, the never-step-aside yardstick

**Problem statement.** M0389 measured that the lab has been under-charging stacked safety rules by
about half, because the habitual quote (stacked minus switch) is 55% and 40% of each brake's true
standalone price. Reading a timing method's bill correctly needs an arm that never steps aside.

**The exposure read, and what it gets wrong.** Read back from `lab/lab.sqlite` opened `mode=ro`,
over methods whose `family` is one of `market-trend-switch`, `volatility-term-structure-gate`,
`macro-regime-gate`, `stock-switch-timing`, taking `max(trials.exposure)` over `window='dev'`:

| | methods |
|---|---|
| with dev trials in those four families | 21 |
| carrying an arm at exposure >= 0.98 | 8 — M0084, M0267, M0271, M0287, M0291, M0352, M0381, M0389 |
| lacking one *by that cutoff* | 13 — M0038, M0039, M0113, M0136, M0167, M0173, M0245, M0260, M0261, M0262, M0334, M0336, M0338 |

That reproduces the handover's 8/13 split exactly — and **the split is wrong**, because the cutoff
is the wrong detector.

**The corrected census: thirteen by the `exposure >= 0.98` read, ten in fact.** `exposure` is
`mean(invested / equity)` over the sessions (`backtest/book_runner.py:568, :801`). A long-only
stock book that *never* steps aside still reads about 0.97, because a slot-limited book funded by
a monthly deposit always carries residual cash. The 0.98 line therefore only detects a
SPY-at-full-weight chassis, and reads a stock book's genuine never-step-aside arm as a gated one.
Three of the thirteen already carry an explicit never-step-aside arm, confirmed in both the
database and the method files (re-measured 2026-10-27):

| candidate | rationale, verbatim from its method file | trades | turnover | exposure | maxDD |
|---|---|---|---|---|---|
| `M0173-EXP100` | "Control: the dividend book never stepping aside for the curve watch" | 576 | 4.2962 | 0.9746 | 0.5765 |
| `M0336-NEVER` | "Control: the dividend book never stepping aside for the curve" | 576 | 4.2962 | 0.9746 | 0.5765 |
| `M0338-NOSW` | "no opinion: same book, switch off, always invested" | 1474 | 7.3482 | 0.9713 | 0.6087 |

`M0038-DIV-OPEN`, `M0173-EXP100` and `M0336-NEVER` are the identical book to every recorded digit
— 576 trades, turnover 4.296218435760635, exposure 0.9745847525069085, max_drawdown
0.5764932745904585 — reached through three different allocator ids and run on two dates eight days
apart.

So the population that lacks an arm is **10 — M0038, M0039, M0113, M0136, M0167, M0245, M0260,
M0261, M0262, M0334**, and M0173, M0336 and M0338 are not in it. M0038 is in it on its `spy` half
only: its `div` half's yardstick is `M0038-DIV-OPEN`.

The thirteen figure is kept here rather than deleted because it is what the handover, the first
draft of this document and every artifact built from them say, and a reader meeting "thirteen"
elsewhere needs to find the correction.

**What an amendment costs and what it requires.** An `Amendment` (`lab/method.py:55`) appends
variants under the method's existing id, so it costs no method id and moves no N. The commit that
adds the block **is** the pre-registration; `runner.preflight(..., amend=True)` refuses an
uncommitted file, refuses a method that has not run, refuses one whose status is in
`AMEND_CLOSED = ("promoted", "test-passed", "test-failed", "paper")`, and refuses one that already
has a `window='test'` trial. All ten are `dev-eligible` or `rejected`, carry a non-NULL
`source_sha`, and have zero rows in `method_amendments` and zero `window='test'` trials
(re-measured 2026-10-27), so all ten are amendable. `Method.__post_init__` refuses a candidate id or a configuration any other variant of
that method already uses, and `real_cost_problem` holds an amendment's candidates to Gotrade's real
fees exactly as the originals.

**Where this phase stops, and why.** Writing the ten blocks is pre-registration and is pure
source. *Running* them (`lab run --amend MNNNN`, ten times) writes to the shared, committed
`lab/lab.sqlite`, needs `lab stage`, and is the one action in this plan set that is neither
reversible nor safely concurrent (memory: a concurrent `lab run` can silently lose trials; a lab
swarm wave has twice taken this laptop down). The tree stays green with ten *pending*
amendments — `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` tolerates exactly that
state, by name — and `test_lab_methods.py` smoke-runs every amendment candidate through
`dev.run_candidate`, so the arms are verified without spending any lab state.

**Success criteria.** Ten committed `Amendment` blocks, one per method, each declaring one
never-step-aside arm of that method's own chassis with its own `why` / `hypothesis` /
`expected_failure`; the full engine suite green, including the per-candidate smoke run; a runbook
naming the exact ten `lab run --amend` invocations and their environment, for the deliberate
session that executes them, and recording the corrected census so the three un-amended methods
read as a finding rather than an omission.

### Key Considerations

- `docs/plans/2026-10-27-sera-20261026-1320-handover.md` is the specification of record and is
  quoted, not paraphrased, wherever it decides something.
- Two standing constraints from the user bind every phase: **`lab/lab.sqlite` and
  `web/data/lab.json` are only ever committed through `lab stage`**, and **every commit names
  explicit file paths — never `git commit -a`**, because sessions share this checkout.
- The M0392 roster question is not touched by any phase.

---

## Analysis Scope

### Explicitly Mentioned Files

- `docs/plans/2026-10-27-sera-20261026-1320-handover.md`

### Discovered Related Files

| File | Why it is here |
|---|---|
| `engine/src/seer_engine/strategies/f_factor.py` | site 1 of the floor; `_eligible_mask:190`, `factor_rows`, `FactorParams.min_price:100` |
| `engine/src/seer_engine/strategies/f_fundamental.py` | site 2; `:403`, `FundamentalParams.min_price:213` |
| `engine/src/seer_engine/lab/methods/m0052_turn_of_month_tilt.py` | site 3, `:145` — frozen |
| `engine/src/seer_engine/lab/methods/m0109_book_drawdown_brake.py` | site 4, `:213` — frozen, and the screen three more files delegate to |
| `engine/src/seer_engine/lab/methods/m0117_index_tenure_exclusion.py` | site 5, `:200` — frozen |
| `engine/src/seer_engine/lab/methods/m0276_cheap_financial_health.py` | site 6, `:294`, private `MIN_PRICE = 5.0` at `:108` — frozen |
| `engine/src/seer_engine/lab/methods/m0383_nominal_price_level_tilt.py` | holds the verified `printed_close` helper, `:163` — frozen |
| `engine/src/seer_engine/lab/methods/m0387_printed_price_floor_repair.py` | holds `passes_floor`, `:181`, and the measurement — frozen |
| `engine/src/seer_engine/backtest/market.py` | `ShareCounts.raw_factor:454`, `EMPTY_SHARES:471`, `Market:536` |
| `engine/src/seer_engine/sim/book.py` | R2: `step_book:571`, the buy loop `:736-815`, `_sizing_price:472`, `_shares_for:416` |
| `engine/src/seer_engine/sim/rules.py` | R2: `TradeRules:118`, `LEVERS_SINCE_PINS:380`, `is_pinned_default:389`, `PRESETS:349` |
| `engine/src/seer_engine/sim/sizing.py` | R2: the bracket path's own cap, `size_picks:101` — a separate engine, same idea |
| `engine/src/seer_engine/backtest/registry.py` | `_canon:300` — the one place a pinned default drops out, and it is `TradeRules`-only |
| `engine/src/seer_engine/paper/roster.py` | `rules_dict:1696`, `_PRESETS:878` — the live spec digests a lever must not move |
| `engine/src/seer_engine/lab/method.py` | `config_text:42`, `Amendment:55`, `Method.all_candidates:145` |
| `engine/src/seer_engine/lab/runner.py` | `preflight:261`, `AMEND_CLOSED:211`, `pending_amendment:214` |
| `engine/tests/test_lab_methods.py` | the two halves of the freeze, `:134` and `:188` |
| `engine/tests/test_sim_rules.py` | `:429` pins `LEVERS_SINCE_PINS` exactly |
| `engine/tests/test_sim_rules_fixed_tape.py`, `test_resize_band_pins.py`, `test_cost_model_pins.py`, `test_lab_costs.py`, `test_sean_mirrors.py` | every test that enumerates `PRESETS` or the lever table |

---

## Current Dataflow

### R1 — how a five-dollar floor is read today

**Entry point:** an allocator's `prepare`/`prepare_market`, then its `targets_for(prepared, members, data_date)`.

1. **`strategies/f_factor.py` — the shared screen.**
   - `factor_rows(history, members, data_date, params)` (`:193`) iterates sorted members, reads each
     `History`'s last `factor_lookback(params)` bars, and calls `_eligible_mask(close, mom, vol, dv, params)` (`:179`).
   - `_eligible_mask` returns `... & (close >= params.min_price)` (`:190`). `close` is
     `History.close`, built by `history_from_bars` from `prices.Bar` — the research store's
     **back-adjusted** close.
   - `FactorParams.min_price` defaults to `5.0` (`:100`), is validated `>= 0.01` (`:129`), and is
     rendered into `as_dict()` at `:150`, which is what `config_digest` canonicalizes.
   - **Exit:** `list[FactorRow]`, the eligible pool. No `Market`, no splits, no share counts: the
     function signature has no market in it.

2. **`strategies/f_fundamental.py` — the fundamentals screen.** Same shape inline:
   `close = float(h.close[i])`, then `if not math.isfinite(close) or close < p.min_price: continue`
   (`:403`). `FundamentalParams.min_price` at `:213`.

3. **The four frozen method files.** Each re-implements the same comparison against the same
   adjusted close: `m0052:145` (`c[-1] < params.min_price`), `m0109:213` (`& (close >= p.min_price)`),
   `m0117:200` (`& (close >= p.min_price)`), `m0276:294` (`close < MIN_PRICE`, reading the file's
   own `MIN_PRICE = 5.0` at `:108` rather than the shared parameter — which is why a sweep of the
   shared screen misses it).

4. **The three delegating modules.** `m0119:147`, `m0127:165` and `m0266:214` each declare
   `min_price: float = 5.0` on their own params and hand it to `m0109`'s screen
   (`from seer_engine.lab.methods.m0109_book_drawdown_brake import ...` at `:115`, `:133`, `:160`).
   They contain no comparison of their own and need no change; they inherit whatever `m0109` does.

5. **The repaired path, as it exists today inside two frozen method files.**
   - `m0383.printed_close(h, market, symbol, data_date)` (`:163`): `adj = float(h.close[i])`, then
     `return adj * market.shares.raw_factor(symbol, data_date)`.
   - `ShareCounts.raw_factor(symbol, d)` (`market.py:454`): the product of every split the vendor
     applied **after** `d`. Reads nothing dated after `data_date`.
   - `m0387.passes_floor(h, market, symbol, data_date, basis)` (`:181`): the three-rung dial
     `"adjusted" | "printed" | "none"`.
   - Both live in files frozen by `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha`, so
     `m0387` importing from `m0383` is a frozen file importing a frozen file.

**State the repair depends on.** `Market.shares` is `EMPTY_SHARES` unless `research.load_store`
found a `shares.csv`/`splits.csv`. The paper night builds its `Market` without shares
(`paper/store.py:1523`), so `raw_factor` answers 1.0 there and the printed basis collapses to the
adjusted one with no error and no warning.

### R2 — how a night's buy budget is spent

**Entry point:** `backtest.book_runner` / the paper night, calling `sim.book.step_book(book, targets, bars, session, rules, ...)` (`:571`).

**The night-before budget is formed first** (`:642-658`): `planned` accumulates `_sell_cash` for
every position the targets drop or trim beyond the band, and `slots_used` is counted as of the
previous close.

**Step (4), the buy loop** (`:736-815`), targets in rank order with the idle instrument last:

```
available = book.cash + planned                      # :740  the night-before budget
committed = _ZERO                                    # :741
for t in ordered:
    ...
    price  = _sizing_price(t, rules)                 # :767  the LIMIT, q(last * 1.02) under open_limit
    budget = min(q(equity * t.weight), available - committed)   # :768
    shares = _shares_for(budget, price, rules)       # :769
    if shares <= 0: rejected "too_small"; continue   # :770-772
    committed += _buy_cash(price, shares, rules)     # :776  <-- reserved at the LIMIT, before any bar is seen

    b = day.get(symbol)
    if b is None: rejected "no_bar"; continue        # :778-781  reservation leaks
    if rules.entry == "open":   fill_price = q(b.open)
    elif b.low < price:         fill_price = q(min(b.open, price))
    else: rejected "unfilled"; continue              # :786-788  reservation leaks
    cost = _buy_cash(fill_price, shares, rules)      # :789  the REAL cash
    if cost > cash:
        shares = _shares_for(cash, fill_price, rules)   # :791  shrunk; reservation not reduced
        ...
    cash -= cost                                     # :796
```

**The gap.** `committed` is a tally of reservations priced at `_sizing_price`; `cash` is a tally of
fills priced at `fill_price`. Nothing reconciles them, so `available - committed` understates the
budget available to every later pick by the sum of (limit − fill) over every earlier pick, plus the
whole reservation of every pick that was rejected after `:776`.

**Why only unequal-weight books skip.** `budget = min(q(equity * t.weight), available - committed)`.
Under equal weights the first term binds and the drift in the second is invisible. Under unequal
weights the heavy early slots consume most of `available` at an inflated price and the second term
binds for the tail — the handover's 2010-03-01 case, $11,936 cash against $251,853 equity,
declining a $7,431 order.

**The bracket engine has the same idea and does not have the bug.** `sim/sizing.py:140` seeds
`committed` from the orders *already pending* and increments it at `:170` by
`buy_cash(order.limit_price, order.shares, rules)` — but there the limit **is** what the order will
pay at most, nothing is filled inside the loop, and `size_picks` is genuinely a night-before
function. The book engine's loop interleaves sizing and filling, which is what makes the mismatch
visible and also what makes "hand the slack back" a design question rather than an obvious repair.

**What a change here touches.** `step_book` is the engine for every rule set with
`engine="book"` — every lab method from M0001 on except the `bracket` ones, plus the live paper
roster. `backtest/registry.py` pins candidate *digests*, not results, so a behaviour change moves
no pinned digest; it moves what a re-run produces, and what the owner's board shows tomorrow.

### R3 — how an amendment reaches the lab

1. **Pre-registration.** An `Amendment(added, why, hypothesis, expected_failure, candidates)` is
   appended to `METHOD.amendments` in the method file and **committed**. `Method.__post_init__`
   (`method.py:177-200`) walks the originals and each amendment sharing one id set and one digest
   set, refusing a repeated candidate id or a repeated configuration.
2. **The tolerated window.** From that commit until the run, the file hashes to something no row
   holds. `test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha` accepts the mismatch on
   exactly one condition: `runner.pending_amendment(conn, method)` resolves, i.e. the file declares
   an `Amendment` the lab has not recorded and every amendment it *has* recorded still matches its
   row field for field.
3. **The run.** `lab run --amend MNNNN` → `runner.preflight(conn, method, path, amend=True)`
   (`:261`), which requires a committed clean file, `source_sha` present, status not in
   `AMEND_CLOSED`, no `window='test'` trial, and a resolvable pending amendment; then runs **only**
   the amendment's candidates and appends one `method_amendments` row.
4. **Nothing else moves.** Status is explicitly unchanged (`commands/lab.py:2093`), and N does not
   move because `store.DSR_POLICY` counts methods.
5. **Free verification before any of that.** `tests/test_lab_methods.py` builds
   `CANDIDATES = [(mid, c) for mid, (m, _) in METHODS.items() for c in m.all_candidates()]` — so
   every amendment candidate is purity-checked, `allocatorkit`-checked and smoke-run through
   `dev.run_candidate` by the ordinary suite, with no lab state spent.

---

## Key Data Structures

### `History` — `strategies/base.py:34`
`symbol`, `dates` (datetime64[D], strictly ascending), `open/high/low/close/volume` (float64).
`close` is the research store's **back-adjusted** close. This is the array every one of the six
floor comparisons reads.

### `FactorParams` — `strategies/f_factor.py:100` (and `FundamentalParams` — `f_fundamental.py:213`)
Frozen dataclass; `min_price: float = 5.0`. Rendered by `as_dict()` into the config text that
`lab.method.config_digest` hashes. **Cannot gain a field** without moving every recorded digest
that embeds it — `registry._canon` drops pinned defaults for `TradeRules` only.

### `ShareCounts` — `backtest/market.py:305`
`raw_factor(symbol, d) -> float` (`:454`): the product of every split applied after `d`.
`EMPTY_SHARES` (`:471`) is what a market without a `shares.csv`/`splits.csv` carries — including
every paper night.

### `TradeRules` — `sim/rules.py:118`
Sixteen fields today. `LEVERS_SINCE_PINS` (`:380`) maps a post-pin lever to its no-op value;
`is_pinned_default` (`:389`) is read by `registry._canon` (`:323`) and `roster.rules_dict` (`:1704`),
both of which enumerate fields generically — so an appended lever at a no-op default moves no
pinned digest anywhere. Five precedents: `resize_cadence`, `cost_model`, `resize_basis`,
`cash_yield`, `resize_band`.

### `Amendment` / `Method` — `lab/method.py:55` / `:118`
`Method.all_candidates()` (`:145`) is the originals then each amendment's, in declaration order.
Every reader that asks "what variants does this method have" must use it, not `candidates`.

---

## Dependencies

### Configuration / Environment

- `SEER_LAB_DB` and `SEER_RESEARCH_STORE` — how parallel sessions share lab state.
- `engine/.venv` per worktree; `PYTHONPATH=engine/src` when invoking from a worktree, or pytest
  silently tests the main checkout.
- `PG_TEST_URL` for the DB tests; CI fails if they skip.

Three measurements of this machine, taken 2026-10-27, that differ from what `CLAUDE.md` says or
from what an earlier draft of the phase plans assumed:

| | what is written | what is here |
|---|---|---|
| interpreter | `CLAUDE.md`: `python3.11 -m venv engine/.venv` | **`python3.11` does not exist.** `python3` is CPython **3.12.7** from `/home/miftah/miniconda3/bin`; the main checkout's venv is 3.12.7 |
| worktree venv | phase 1's draft: `engine/.venv` is empty, `import numpy` fails | **built and working** — 3.12.7, numpy 2.5.4, pytest 9.1.1, `import seer_engine` ok. True when looked at, repaired since |
| `PG_TEST_URL` | `CLAUDE.md` exports it in the DB-test recipe | **not exported by default**, and the `seer-pg` container had been stopped for 26 hours. Restarted. A stopped container turns the DB tests into a silent skip, which CI fails on |

### External Services

None reached by this plan set. No network, no Postgres write, no Neon, no Vercel.

### Research stores

`engine/.research` (dev), `engine/.research-sv` (survivorship-check), `engine/.research-test`
(test window). None is read by any phase of this plan set: every phase is source + the ordinary
test suite.

---

## Reference List

Every site that touches the five-dollar floor, re-measured this session by
`grep -rn "min_price\|MIN_PRICE" engine/src/seer_engine/`:

| Symbol / key | File:line | Kind | Status |
|---|---|---|---|
| `_eligible_mask` `close >= params.min_price` | `strategies/f_factor.py:190` | comparison | **site 1 — editable** |
| `FactorParams.min_price = 5.0` | `strategies/f_factor.py:100` | declaration | editable |
| `close < p.min_price` | `strategies/f_fundamental.py:403` | comparison | **site 2 — editable** |
| `FundamentalParams.min_price = 5.0` | `strategies/f_fundamental.py:213` | declaration | editable |
| `c[-1] < params.min_price` | `lab/methods/m0052_turn_of_month_tilt.py:145` | comparison | **site 3 — FROZEN** (rejected, sha `601cb089`, 5 trials) |
| `close >= p.min_price` | `lab/methods/m0109_book_drawdown_brake.py:213` | comparison | **site 4 — FROZEN** (rejected, sha `95421df4`, 6 trials) |
| `close >= p.min_price` | `lab/methods/m0117_index_tenure_exclusion.py:200` | comparison | **site 5 — FROZEN** (rejected, sha `7ea65e61`, 5 trials) |
| `close < MIN_PRICE` | `lab/methods/m0276_cheap_financial_health.py:294` | comparison | **site 6 — FROZEN** (rejected, sha `e18ee7c9`, 5 trials) |
| `MIN_PRICE = 5.0` (private copy) | `lab/methods/m0276_cheap_financial_health.py:108` | declaration | FROZEN |
| `min_price: float = 5.0` → m0109's screen | `lab/methods/m0119_deposit_deployment.py:147` | delegation | no change needed |
| `min_price: float = 5.0` → m0109's screen | `lab/methods/m0127_slot_relative_resize_band.py:165` | delegation | no change needed |
| `min_price: float = 5.0` → m0109's screen | `lab/methods/m0266_exposure_matched_rebalance.py:214` | delegation | no change needed |
| `printed_close` (already correct) | `lab/methods/m0383_nominal_price_level_tilt.py:163` | helper | FROZEN (dev-eligible, sha `2fe3ddea`) |
| `passes_floor` (already correct) | `lab/methods/m0387_printed_price_floor_repair.py:181` | helper | FROZEN (dev-eligible, sha `5e4b9bdd`) |
| `MIN_PRICE = 1e-4` | `delisting.py:96` | unrelated | a zero-close floor, not the penny-stock screen |
| `min_price` in `as_dict()` | `m0241:158`, `m0244:251`, `m0352:82` | digest text | frozen, read-only |

The R2 reference list:

| Symbol | File:line | Kind |
|---|---|---|
| `committed += _buy_cash(price, shares, rules)` | `sim/book.py:776` | the defect |
| `_sizing_price` | `sim/book.py:472` | def |
| `_shares_for` | `sim/book.py:416` | def |
| `budget = min(q(equity * t.weight), available - committed)` | `sim/book.py:768` | call |
| `shares = min(gap, _shares_for(available - committed, price, rules))` | `sim/book.py:758` | call (adds) |
| `TradeRules` fields | `sim/rules.py:118-128` | def |
| `LEVERS_SINCE_PINS` | `sim/rules.py:380` | config |
| `is_pinned_default` | `sim/rules.py:389` | def |
| `_canon` pinned-default drop | `backtest/registry.py:323` | reader |
| `rules_dict` | `paper/roster.py:1696` | reader |
| `assert LEVERS_SINCE_PINS == {...}` | `tests/test_sim_rules.py:429` | test — moves |
| `assert len(PRESETS) == 20` | `tests/test_sim_rules_fixed_tape.py:74` | test — only if a preset is added |

The R3 reference list. Thirteen method files by the `exposure >= 0.98` read; **ten in fact**,
because that cutoff cannot see a stock book's never-step-aside arm (§R3). The last three rows need
no `Amendment` block and are kept in the table so the correction is visible where the old figure
was read:

| Method | Family | Status | dev trials | max dev exposure | reaches `f_factor` | needs an `Amendment` |
|---|---|---|---|---|---|---|
| M0038 | macro-regime-gate | dev-eligible | 6 | 0.9746 | no | yes — its `spy` half only; its `div` half's yardstick is `M0038-DIV-OPEN` |
| M0039 | volatility-term-structure-gate | rejected | 6 | 0.9333 | no | yes |
| M0113 | market-trend-switch | rejected | 6 | 0.8047 | `FactorParams` only | yes |
| M0136 | market-trend-switch | rejected | 6 | 0.7488 | `FactorParams` only | yes |
| M0167 | macro-regime-gate | dev-eligible | 6 | 0.8006 | no | yes |
| M0245 | market-trend-switch | rejected | 6 | 0.9308 | `FactorParams` only | yes |
| M0260 | market-trend-switch | dev-eligible | 6 | 0.7221 | `factor_rows` | yes |
| M0261 | market-trend-switch | dev-eligible | 6 | 0.7811 | `factor_rows` | yes |
| M0262 | market-trend-switch | dev-eligible | 6 | 0.7479 | `factor_rows` | yes |
| M0334 | market-trend-switch | rejected | 4 | 0.7564 | `FACTOR`, `factor_lookback` | yes |
| M0173 | macro-regime-gate | dev-eligible | 4 | 0.9746 | no | **no — already carries `M0173-EXP100`** |
| M0336 | macro-regime-gate | dev-eligible | 5 | 0.9746 | no | **no — already carries `M0336-NEVER`** |
| M0338 | stock-switch-timing | dev-eligible | 5 | 0.9713 | `factor_rows` | **no — already carries `M0338-NOSW`** |

---

## Impact Points (files that WILL need changes)

**Phase 1 — R1**

1. `engine/src/seer_engine/strategies/price_floor.py` *(new)* — the shared, supported printed-price
   helper; the canonical home for what `m0383.printed_close` and `m0387.passes_floor` prove works.
2. `engine/src/seer_engine/strategies/f_factor.py` — `_eligible_mask` and `factor_rows` gain a
   keyword-only basis (and the market it needs) defaulting to today's behaviour. **Function
   arguments, not dataclass fields**: no digest moves.
3. `engine/src/seer_engine/strategies/f_fundamental.py` — the same, at `:403`.
4. `engine/tests/test_price_floor.py` *(new)* — the five real-world closes M0383 verified, the
   agreement with the two frozen copies, and the no-digest-moved assertions.
5. `docs/` — one note recording sites 3-6 as frozen, why, and the one legal route to repairing them.
   **No lab method file is edited in this phase.**

**Phase 2 — R2**

6. `engine/src/seer_engine/sim/rules.py` — one appended `TradeRules` lever, its validation, its
   `LEVERS_SINCE_PINS` entry, its docstring paragraph.
7. `engine/src/seer_engine/sim/book.py` — the buy loop's `committed` accounting, `:776` onwards,
   gated on the lever.
8. `engine/tests/test_sim_rules.py:429` — the pinned lever table gains one line.
9. `engine/tests/test_sim_book.py` *(extend)* — the regression: an unequal-weight book that skips a
   pick at the default and buys it under the lever; and the proof that every existing preset's
   canonical text is byte-identical.

**Phase 3 — R3**

10. **Ten** method files under `engine/src/seer_engine/lab/methods/` — `m0038`, `m0039`, `m0113`,
    `m0136`, `m0167`, `m0245`, `m0260`, `m0261`, `m0262`, `m0334` — each gaining exactly one
    `Amendment` block declaring one never-step-aside arm. Thirteen by the `exposure >= 0.98` read;
    ten in fact, because `m0173`, `m0336` and `m0338` already carry the arm (§R3). Those three are
    **not** impact points: a second registration of the same configuration would be refused by
    `store.has_trial`.
11. `docs/runbooks/` — the ten `lab run --amend` invocations, their environment, the order to run
    them in, and the corrected census.

**This document describes. The plan files prescribe.**
