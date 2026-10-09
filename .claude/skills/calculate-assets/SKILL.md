---
name: calculate-assets
description: Use when the owner asks what his money would have become had he started investing earlier — "/calculate-assets M0007-N20-RAW 16-4-2018", "what if I'd started when I got my first salary", "run this method from 2018 to today", "how much would 10 million plus 5 million a month have grown into", "what did compounding actually give me", "paper-trade M0032 from 2019 with real fees". Runs one lab method over any window inside the test-window store on the owner's real funding plan at Gotrade's real fees, and reports the money — never the gate numbers.
---

# What the money would have become

The owner graduated in April 2018 and started earning then. This answers, with his real method,
his real deposits and his real fees, what the account would say today if he had started that
month — and how much of the answer was the strategy, how much was the rupiah, and how much was
simply time.

```bash
S="$(git rev-parse --show-toplevel)/.claude/skills/calculate-assets/calculate_assets.py"
PYTHONPATH="$(git rev-parse --show-toplevel)/engine/src" \
  "$(git rev-parse --show-toplevel)/engine/.venv/bin/python" "$S" \
  M0007-N20-RAW 16-4-2018 --out /tmp/assets.json
```

Arguments: a candidate id (`M0007-N20-RAW`), a bare method id, or a `seertrade.site` method URL;
a start date day-month-year; optionally an end date, defaulting to the store's last session.

## The money model, which is not a choice

10,000,000 IDR to open, 5,000,000 IDR on the 25th of every month, fractional shares, Gotrade's
measured fee schedule. None of this is invented here — `sim/contributions.py` already holds the
owner's plan as a frozen value, including the detail that a deposit on the 25th sits as idle cash
until the next month-start rotation, so the result does not quietly overstate returns by
investing money the instant it lands.

## Four rules this skill does not bend

**1. The id you give is not what runs.** `M0007-N20-RAW` is the lab's record of a flat-fee,
whole-share, lump-sum run. The question is about real money, so the skill swaps in fractional
shares and Gotrade's fees. Where a method already registers exactly that configuration it runs
**by name** — for `M0007-N20-RAW` that is `M0032-N20-RAW-FRAC-GT`, which was pre-registered, so
somebody wrote down in advance what it was expected to do. The output always says which.

**2. The headline is the money-weighted return, never CAGR.** On a book fed monthly deposits,
CAGR counts the owner's own deposits as growth — the engine calls that "the +600.9% lie". The
money-weighted return is the rate a savings account would have had to pay on the same deposits,
on the same days, to reach the same balance. That is the question being asked.

**3. It prints no gate numbers.** The window it reads is the held-out test window. The owner
chose to see the outcome without the diagnostics — DSR, eligibility, the owner conditions,
failure labels — that would let a method be tuned against data it was supposed to be judged on
once. Do not add them back, and do not go looking them up afterwards to "complete" the report.

**4. It never connects to the lab database.** `lab` commands migrate `lab.sqlite` on connect, so
even a read dirties the file. Methods come from `lab.method.discover()`, reading committed method
files on disk. Nothing is recorded: no trial, no observation, no status move. It is a report, in
the sense `lab costs` is a report.

## The store

Needs `engine/.research-test`, which `lab test` needs too. If it is missing the skill says so and
prints the build command:

```bash
python -m seer_engine research_store --test-window --with-fundamentals
```

About half an hour and a yfinance crawl. Use `--with-fundamentals` — without it the lab ranks on
bars alone, **silently**, and the answer would be wrong in a way nothing announces.

The test window opens 2015-10-19. A start date before that is refused: earlier is the dev window,
which every method here was built on, and a result there is the method marking its own homework.

## Reading the answer honestly

- **The drawdown reads shallower than it was.** Monthly deposits keep topping the account up. The
  output says so; keep the caveat when you summarise it.
- **Losing to SPY is a real result, not a bug.** `M0032`'s pre-registered `expected_failure` says
  a money-weighted return "rewards being invested when the money arrives", and a trend-gated book
  sits in cash precisely when a monthly buyer's new money buys cheapest — March 2020, most of
  2022. If the method loses here, report that it lost.
- **Two rupiah lines.** The real-FX run converts each deposit at the rate of the day it was
  credited; the fixed-rate run uses the start date's rate throughout, which is what every recorded
  lab trial does. The gap between them is the rupiah's contribution, and it belongs in the answer
  — the owner holds US stocks and earns rupiah.

## The chart

`--out FILE` writes the series as JSON: `book_real`, `book_fixed`, `spy`, `deposited`, monthly
points in rupiah. Publish it as an Artifact — four lines over the whole span, with the ending
balances called out. Load the `artifact-design` skill before writing the page, as always.
