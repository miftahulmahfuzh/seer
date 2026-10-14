# The next tier down is worse on both axes

*Measured 2026-10-14. A report: no trial, no method id, no status, no journal row, no
test-window look. `store.dev_trial_count` and `store.test_looks` cannot have moved — the probe
never opens the lab for writing. Grid: `probe.csv`.*

## What was asked

The index lab has 81 methods and nothing promotable, and the kin measurement says why: the books
it would actually test correlate **0.93-0.96** with books that already spent a test look and
failed. The universe — twenty of the most-traded large caps — looked like the binding constraint
rather than the rules. The published research these ideas come from finds most of its edge further
down the size ladder, and the lab's own journal names small companies as never tested.

So a second universe was built from a paid EODHD month (7,556 US common stocks, dollar-volume
ranks 500-2000, 1998-2015, **dead companies included**) and the lab's *existing* strategies were
run on it unchanged. The identical rule — top N by dollar volume — picks ranks ~500-520 there: the
next tier down, still liquid enough for a retail book at Gotrade's real fees.

## What came back

| candidate | yearly index → band | worst fall index → band |
|---|---|---|
| M0007-N20 | 9.71 → **9.47** | 14.40 → **17.32** |
| M0007-N10 | 9.81 → **8.17** | 18.56 → **22.17** |
| M0007-N30 | 10.09 → **9.65** | 14.66 → **16.84** |
| M0007-N20-RAW | 14.24 → **11.49** | 18.66 → 18.77 |
| M0007-N20-NOTREND | 9.05 → **8.88** | 49.53 → **54.87** |
| M0022-W-TV14 | 9.64 → **7.39** | 11.09 → **13.07** |
| M0022-W-TV16 | 10.59 → **8.34** | 13.55 → **14.89** |
| M0022-W-TV14-SW | 7.98 → **5.97** | 14.17 → **15.89** |
| M0030-C70T | 11.48 → **10.57** | 18.77 → 18.29 |
| M0030-C50T | 12.66 → **11.11** | 18.56 → 18.59 |
| M0030-C50A | 11.91 → **10.37** | 33.98 → 33.85 |

SPY total return is 7.86%/yr on the same window, both sides.

**Every one of the eleven earns less. Nine of the eleven fall further.** Two stop beating SPY at
all (`M0022-W-TV14`, `M0022-W-TV14-SW`). Only `M0030`'s core-satellite variants hold their
drawdown roughly level, and they still give up a point of return to do it.

## The reading

**The universe was not the answer either.** The hypothesis was that the lab is trapped in large
caps and the edge lives further down. Moving down the ladder made the books worse on **return and
drawdown simultaneously** — the same double failure the learned fall model produced against the
SPY 200-day gate, and the same one every gate-off arm produced.

This is worth knowing precisely because it was the most plausible remaining idea. It cost a report.

## What this does NOT say

- It tests ranks ~500-520, not micro caps. Rank 2000+ is a different claim and an untradeable one
  at Gotrade's fees — `docs/backtests/2026-10-13-chart-model-turnover.md` prices why.
- It tests the lab's **existing** rules carried onto new names, not rules designed for smaller
  companies. The honest statement is *these* strategies do not travel down, not that nothing does.
- The store has no fundamentals (EDGAR is keyed to the index universe and starts 2009), so nothing
  value-shaped was tried here.

## The stores, for anyone re-running this

| | |
|---|---|
| `engine/.research-dv` | ranks 1-2000, 7,693 symbols, 15,693,461 bars, fingerprint `ed59dbf6…` |
| `engine/.research-dv500` | ranks 500-2000, 7,556 symbols, 15,016,079 bars, fingerprint `18f0f39b…` |

Both carry `purpose: dollar-volume-universe`, so `lab run`, `lab test` and `lab remeasure` refuse
them: a trial measured here can never join a method whose other trials came from the index store.
Backups are in Vercel Blob under `seer/research-store/dv/`, and the raw EODHD cache under
`seer/eodhd-cache/`. Reproduce with:

    python -m seer_engine universe_probe --csv docs/lab/universe/probe.csv
