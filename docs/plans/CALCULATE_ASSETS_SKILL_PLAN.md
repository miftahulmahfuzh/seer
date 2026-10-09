# Plan: `/calculate-assets` — what my money would have done if I had started earlier

**Slug:** calculate-assets
**Date:** 2026-10-09
**Branch:** `calculate-assets` (base: `main` @ `1d28db6`)
**Status:** in progress

---

## Why

The owner, verbatim:

> so i graduated university on april 2018 and started working and earned my first salary at that
> time. i am wondering, may we create a new skill, "/calculate-assets <method> <start-date>
> <end-date-optional>" … then, you will run paper trading using exactly this method and be
> realistic about it. starting funds is 10 mil , +5 mil monthly , and use real Gotrade fees.
> then you will tell me how much it grows at the end-date-optional .
>
> my reasons:
> 1. curiousity.
> 2. the most important thing for investing is time. people talk about "compounding interest" all
> the time. so, i would like to see for myself, what is the reality would be if i started
> investing much earlier in the past.

The second reason is the real one, and it is a question about *time*, not about a method. The
method is how the money is deployed; the eight and a half years are what the question is about.
The design keeps those two separable so the answer can say which did the work.

## What already exists

Nearly all of it. This skill is plumbing, not new machinery:

- `sim/contributions.py` is the owner's plan as a frozen value — 10,000,000 IDR to open and
  5,000,000 IDR on the 25th of every month, with a deposit credited at the OPEN of the first NYSE
  session on or after its date, so a deposit sits idle until the next month-start rotation
  instead of being invested the instant it lands.
- `cost_model="gotrade"` in `sim/costs.py` is the real fee schedule fitted to the owner's own
  order receipts: a trading fee with a $0.10 minimum, a regulatory fee, and 11% VAT on both.
- `MONTHLY_HOLD_FRAC_GOTRADE` is the fractional-share book at those fees.
- `backtest/benchmark.py` already builds a SPY total-return curve fed the **identical deposits on
  the identical days**, which is the only fair comparison for a book that is topped up monthly.
- `dev.run_registry(..., window=, contributions=)` already takes both. `lab test` is currently its
  only caller that passes a window.

## Decisions

**D1 — Money only; no gate panel.** The run reads the held-out test window. The owner chose to
accept that and to see the outcome without the diagnostics that would let him re-tune against it.
So the output carries ending balance, money-weighted return, total deposited, the deposit-matched
SPY and the worst fall; and it does **not** carry DSR, eligibility, the five owner conditions, or
the `failed` labels.

**D2 — The id given is resolved to its honest twin.** `M0007-N20-RAW` is the flat-cost,
whole-share, lump-sum variant — the one the lab recorded. The owner asked for real Gotrade fees,
so the skill resolves the id and then forces the three realism switches on: `fractional=True`,
`cost_model="gotrade"`, and the monthly contribution schedule. Where a registered real-fee twin of
that exact configuration already exists it is used **by name** and named in the output, rather
than a lookalike being constructed silently. For `M0007-N20-RAW` that twin is
`M0032-N20-RAW-FRAC-GT`, which M0032's own file describes as "M0007-N20-RAW verbatim, in
fractional shares at Gotrade's real fees".

**D3 — Both FX treatments, as two lines.** `book_runner.py:307` resolves one USD/IDR rate at the
window start and uses it for the whole run, including every deposit. `contributions.py` says why:
so the result is about the strategy rather than about the rupiah. That assumption is load-bearing
for a 2018→2026 question — the owner deposits rupiah and holds US stocks, so the rupiah's slide is
part of what his assets did, and it cuts both ways, since each later 5,000,000 buys fewer dollars.
The skill runs it twice, once at real daily USD/IDR and once at the fixed start-date rate, and
plots both. The gap between them is how much of the growth was the strategy and how much was the
rupiah.

**D4 — The lab database is never connected to, not merely never written.** `lab` commands migrate
`lab.sqlite` on connect, so even a read dirties the file. Methods and candidates come from
`lab.method.discover()`, which reads committed method files on disk. If a bare method id ever
needs the trials table to choose a best variant, it opens `file:lab/lab.sqlite?mode=ro`.

**D5 — Every recorded trial must still reproduce bit-identically.** D3 is the one real engine
change. It must be strictly additive and default to today's behaviour. The test is the one
`real_costs` already uses: re-run a recorded dev candidate and assert its recorded total return to
`REPRO_TOL`.

## Shape

```
/calculate-assets M0007-N20-RAW 16-4-2018 [31-12-2025]
```

1. Parse dates as D-M-Y. An absent end date means the store's last completed NYSE session.
2. Resolve the candidate (`runner.resolve_candidate`): a candidate id, a bare method id, or a
   seertrade.site method URL.
3. Apply D2's realism swap. Refuse a `design-v0` bracket candidate — it has no real-fee model,
   the same reason `real_costs.twins` refuses one.
4. Load `engine/.research-test`, the `lab test` idiom: `research.declared_window` first, refuse a
   dev store by name, then `load_store`. Simulate on a **narrower** window inside the store's
   declared span.
5. Run twice per D3.
6. Print the summary; publish the chart.

## Risks

- **The narrowing in step 4 is unproven.** `load_store` compares the store's declared window with
  the caller's. Whether it accepts a sub-range, or only the exact declared window, is the first
  thing to verify rather than assume.
- **The answer may be unflattering, and that is a result.** M0032's pre-registered
  `expected_failure` predicts the money-weighted return comes in at or below the deposit-matched
  SPY, because "a money-weighted return rewards being invested when the money arrives" and the
  SPY-200 trend gate sits in cash precisely when a monthly buyer's new money buys cheapest. Over
  2018–2026 that is March 2020 and most of 2022. If the method loses to SPY here, that is the
  honest answer to the owner's question and is reported as such.
- **The drawdown and any luck-style figure will flatter the book**, for the reason M0032 wrote
  down in advance: monthly deposits keep topping the account up, so a fall reads shallower than it
  was, and every deposit day looks like an enormous up day. The output says so rather than
  printing a drawdown that quietly means something else.
