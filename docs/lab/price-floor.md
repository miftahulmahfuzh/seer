# The five-dollar price floor: where it is repaired, and where it is frozen

**Written:** 2026-10-27, landing R1 of `FLOOR_RESERVATION_YARDSTICK_PLAN.md`.
**Measurement of record:** M0383 (the hole) and M0387 (the price of repairing it).

## The defect, in one paragraph

Every stock screen in this lab asks whether a member's close is at least five dollars. The close
it reads is the research store's, and the store's closes are back-adjusted for every split the
vendor applied since. So the floor has never asked "did this share trade above five dollars"; it
has asked "did this share trade above five dollars after dividing by every split between then
and now". A company that split often reads far cheaper in the old years than it ever traded, and
the companies that split often are the companies that went up. M0383 measured the hole on the dev
store over the 238 month-ends from 1996-01-31 to 2015-10-16: 1293 of 62923 member-months, 2.05%,
across 40 companies — Nvidia at 168 month-ends, Apple at 149, KLA at 137, CSX at 132, then
Aimco, TJX, Lam Research, Amphenol, Amazon, Netflix, O'Reilly, Broadcom, Starbucks, Monster and
Fastenal.

The repair is `close × Market.shares.raw_factor(symbol, d)`, the product of every split the
vendor applied after `d`. It became possible only when split dates reached the store on
2026-10-17/18.

## The six sites

| # | Site | Status |
|---|---|---|
| 1 | `strategies/f_factor.py` `_eligible_mask` | **repaired as an option** — `factor_rows(..., price_basis=...)`, default `"adjusted"` |
| 2 | `strategies/f_fundamental.py` the comparison in `fundamental_rows` | **repaired as an option** — same argument, same default |
| 3 | `lab/methods/m0052_turn_of_month_tilt.py:145` | **frozen** — `rejected`, `source_sha` `601cb089`, 5 trials |
| 4 | `lab/methods/m0109_book_drawdown_brake.py:213` | **frozen** — `rejected`, `source_sha` `95421df4`, 6 trials |
| 5 | `lab/methods/m0117_index_tenure_exclusion.py:200` | **frozen** — `rejected`, `source_sha` `7ea65e61`, 5 trials |
| 6 | `lab/methods/m0276_cheap_financial_health.py:294` (its own `MIN_PRICE = 5.0` at `:108`) | **frozen** — `rejected`, `source_sha` `e18ee7c9`, 5 trials |

Three more modules declare a `min_price` of their own and hand it to m0109's screen, and contain
no comparison at all: `m0119_deposit_deployment.py:147`, `m0127_slot_relative_resize_band.py:165`
and `m0266_exposure_matched_rebalance.py:214`. Each builds m0109's `BrakeParams` (`m0119:173`,
`m0127:192`, `m0266:247`) and inherits whatever site 4 does. They need no change, and
`grep -n "min_price" <file>` over all three shows a declaration, a validation, a digest key and
a hand-off, and no `<` or `>=` against a close.

## Why sites 3-6 are not repaired

All four are committed pre-registrations with a recorded `methods.source_sha` and a verdict.

1. `engine/tests/test_lab_methods.py::test_a_method_that_ran_is_frozen_to_its_latest_recorded_sha`
   asserts each such file's sha256 equals `store.latest_source_sha`, and tolerates a mismatch on
   exactly one condition: a committed, unrecorded `Amendment` that `runner.pending_amendment`
   resolves. A floor repair is not an amendment. Any byte change turns the test red.
2. Worse than red: a repair there would silently change what those methods' **recorded** arms do
   while their `config_digest` stayed byte-identical, because the digest canonicalizes params and
   rules, not the file. That is precisely the thing the freeze exists to stop. The rejected
   verdicts in `lab.sqlite` would then describe a book nothing in the tree can reproduce.

## The one legal route

A **new variation method** that inherits the repaired shared screen, or an **`Amendment`** on one
of the four, pre-registered by the commit that writes it and run with `lab run --amend MNNNN`.
Either way the arms are declared before they run and the old rows keep describing the old book.
Which of the two, and whether it is worth a method id at all, is a future decision and was not
taken by this phase.

## Why the default did not move

`factor_rows` is reached by 186 of the 243 method files and called directly by 119 of them
(re-measured 2026-10-27 with `grep -rln` over `engine/src/seer_engine/lab/methods/`). An
amendment exists to ask one more question of an idea *under the same conditions as its recorded
arms*. Moving the pool under `factor_rows` would make every future amendment arm of every
recorded method incomparable with the arms it was written to be measured against. The repair is
therefore landed as a reachable, tested option and the default stays `"adjusted"`.

Nor could the basis become a `FactorParams` or `FundamentalParams` field.
`lab.method.config_text` canonicalizes `c.params` through `backtest.registry._canon`, which
enumerates every `compare=True` dataclass field; the pinned-default drop-out is applied to
`TradeRules` only (`registry.py:323`). A new field would move every recorded `config_digest` that
embeds one. A plain keyword argument is invisible to `_canon`.

## The standing blocker on ever running it live

The printed close needs `Market.shares`. The paper night builds its `Market` with history,
membership, fx and fundamentals and **no shares** (`paper/store.py:1523`), so `shares` is
`EMPTY_SHARES` and `raw_factor` answers 1.0 for every symbol. A printed-basis screen would
degrade back to the adjusted basis live, with no error (insights 778, 779). Supplying share
counts to the paper night is a table, a migration, a loader and a nightly job, and it is not
built.

Two guards stand in for it until it is:

- `strategies/price_floor.check_market` raises `PrintedBasisUnavailable` when the printed basis
  is asked for on a market with no splits. Both shared screens call it once before their loop.
- An allocator reading the printed basis must declare `market_fields = ("shares",)`, which makes
  `lab run` refuse it on a research store with no `splits.csv`.

Neither implies the other, so both are required.
