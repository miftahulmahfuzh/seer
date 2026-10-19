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

## Running it without wasting the owner's time

One run takes about a minute when the store is complete, and several minutes when it has to fetch
split lists first. A bare family id with several variants is refused and lists
them; when the owner gave no variant, run the method's main variant and its switch variant
(the docstring names them) side by side instead of asking.

**Across a batch of methods, use one tmux window each** (the owner's "a" request). One window per
method keeps its own scrollback and stops one failure hiding the others:

```bash
python3 ~/.claude/skills/swarm/swarm.py launch --name assets-MNNNN --cwd "$REPO" --repo "$REPO" \
  --permission-mode bypassPermissions --model opus \
  --prompt "/calculate-assets MNNNN 1-4-2018"
```

Pass the bare method id so the skill runs the main arm and its switch arm together. Read the
answers from the panes; a child's `SendMessage` has no coordinator to reach outside a Claude
coordinator session, so do not wait for a report.

Run several variants as plain background jobs and `wait` for them, all in one command:

```bash
for v in S20 S40-SW; do
  PYTHONPATH=engine/src engine/.venv/bin/python "$S" M0185-$v 1-4-2018 \
    --out "$D/assets-$v.json" > "$D/out-$v.txt" 2>&1 &
done
wait
```

**Never wait with `while pgrep -f calculate_assets.py`.** The loop's own shell command line
contains that string, so `pgrep -f` matches the shell itself and the loop never ends. It sat
there for 20 minutes after the runs had already finished. If you have to poll, check that the
`--out` JSON files exist.

## The store

Needs `engine/.research-test`, which `lab test` needs too. If it is missing the skill says so and
prints the build command:

```bash
python -m seer_engine research_store --test-window --with-fundamentals
```

About half an hour and a yfinance crawl. Use `--with-fundamentals` — without it the lab ranks on
bars alone, **silently**, and the answer would be wrong in a way nothing announces.

**A store that exists can still be incomplete.** A rebuild can drop the optional files —
`shares.csv` and `splits.csv` — and the run then records zero trades, which looks exactly like a
strategy that bought nothing. The missing-input message names `market_series.csv` even when that
file is present, so do not trust it: list the store directory and check for `shares.csv` and
`splits.csv` first. Restore them without rebuilding and without moving the price fingerprint:

```bash
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine shares fetch-splits \
  --store engine/.research-test
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine shares store \
  --store engine/.research-test --basis <today, YYYY-MM-DD>
```

The fetch is network, resumable, and only asks for symbols the cache lacks; the store step is
offline. A buyback book, a split book, or any method reading company size will otherwise report
zero trades — and a zero-trade run is a data answer, never a strategy answer.

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
points in rupiah. `build_page.py` turns that JSON into the artifact page:

```bash
python3 .claude/skills/calculate-assets/build_page.py /tmp/assets.json /tmp/assets.html
```

Then publish `/tmp/assets.html` with the Artifact tool. Every figure on the page is computed from
the JSON — no number is ever retyped, so the page cannot drift from the run that produced it.

The chart's palette is validated, not eyeballed: teal `#0d9488` / burnt orange `#c2410c` on light,
`#19a89a` / `#d4731f` on dark, all four checks passing in both modes under the `dataviz` skill's
`validate_palette.js`. The two rupiah treatments are one hue split by a dash pattern, because they
are the same book under different assumptions — not two different things.

If you change the page, note that SVG text lives in viewBox units: tick labels need their own
larger sizes under the phone media query or they render at about 4px.
