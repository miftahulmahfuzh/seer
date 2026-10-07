# Handover: the first paper night's roster, and what the survivorship check found

Written 2026-10-07 on `main` at `6c3bf56`, after migration 013 was applied to Neon and before the
first paper session has ever run. Pass this file straight to `/analyze` in a fresh session and read
all of it first. Like the earlier handovers it separates:

- decisions that are **already made** (and shipped — see §1 and §2);
- facts that were **verified** (with `file:line` or a reproducible command);
- questions the analysis still has to settle (§5).

**Nothing here is blocked.** The roster shipped and the measurement is recorded. This exists so a
fresh session can pick up the open threads in §5 without re-deriving the state, and so the two
findings in §3 are not lost in a transcript.

---

## 0. In plain words

Yesterday the app had five strategies on its paper roster, three of which could never have reached
real money: one had failed its own backtest twice, one had a drawdown outside the owner's limit,
and one traded so rarely it would need two centuries to reach the 100 closed trades the rules ask
for. They were replaced with three that can. Paper trading starts from a clean slate — nothing has
ever traded — so no track record was lost.

Separately, the owner asked whether the price data's missing companies (half the index, in the
early years) were flattering the backtests, and whether fixing that needs a paid subscription. It
was measured instead of guessed. The answer appears to be no, and the measurement turned up
something more useful: these strategies earn their advantage almost entirely during crashes, and
give some of it back in calm markets. That changes how their results should be read, and it is
the main thing a reader of this file should carry forward.

---

## 1. The roster, as it now stands (verified, shipped)

Commit `e92748f`; migration `db/migrations/013_roster_first_night.sql` applied to Neon 2026-10-07.

| id | object | from lab | why it is there |
|---|---|---|---|
| `SPY` | `buy_and_hold` | — | the yardstick |
| `C` | `STRATEGY_C` | — | the LLM news veto; forward-only by design (§1 item 5 n/a) |
| `RMW-FR` | `WEEKLYBRAKE` | M0022-W-TV16 | the lab's best risk-adjusted book |
| `RAW-FR` | `RESIDMOM` | M0007-N20-RAW | RMW's **own engine with the brake removed** — the controlled test of whether the brake pays |
| `MOM-FR` | `REGIME` | M0002-REL-85 | total-return momentum, inside the 20% drawdown bar |
| `MVW-FR` | `MINVAR` | M0008-N30-C07 | the only passer that changes **sizing** rather than ranking |

Retired, never traded: `A`, `F4-MOM12-N20-TREND(-FR)`, `F1-SPY-SMA200-M(-FR)`, `FND`, `RM-FR`.

- `paper/roster.py:146-148` — the three new id constants; `:351` `RESOLVER`; `:393`
  `LAB_PROVENANCE`; `:732` `SEED_ROWS`; `:997` `MAX_LOOKBACK_BARS` (still 426, unchanged).
- `strategies/evidence.py` — `residmom_evidence`, `regime_evidence`, `minvar_evidence`, all three
  exercised against the real research store before shipping.
- **Why the three went** (the screen is design §1 item 5 read literally — *can this ever satisfy
  the five conditions at all?*): `A` failed its own gate twice out of sample (−15.0% and +9.1%
  against SPY TR's +71.9% and +187.6%); `F4-FR`'s 22.2% drawdown is outside the revised 20% bar so
  item 4 refuses it permanently; `F1-FR` closed **11 trades in 22 dev-window years** against item
  1's 100.
- `web/lib/data.ts:101` — `WHERE NOT (status = 'retired' AND paper_start IS NULL)`. Every retired
  entry has a null `paper_start`, so the app shows exactly SPY + the five. Verified against Neon.

---

## 2. What the DSR correction changed (verified)

**None of the three new entries passes the lab's luck test at today's N**, and each `gate_note` and
`LAB_PROVENANCE` line says so with both numbers.

`trials.dsr` is the score at that trial's **own** `n_trials_at_run`, not at the lab's current N.
Comparing it to `store.DSR_MIN` (`lab/store.py:121`, 0.90) gives a wrong verdict. Re-score with
`store.published_verdict`:

| candidate | recorded | at its N | re-scored at N=110 | eligible now |
|---|---|---|---|---|
| M0022-W-TV16 | 0.9156 | 110 | 0.9156 | yes |
| M0007-N20-RAW | 0.9138 | 85 | **0.8985** | no |
| M0002-REL-85 | 0.8542 | 80 | 0.8278 | no |
| M0008-N30-C07 | 0.8172 | 74 | 0.7802 | no |

This did **not** change the roster, and the reasoning should survive into any future promotion: DSR
is not one of design §1's five conditions, roster admission has never been the lab's gate
(`paper/roster.py` module docstring), and a score that falls purely because the lab kept searching
is a statement about selection, not about the book. All three are `owner-override`.

---

## 3. The survivorship measurement (verified, recorded as design §12)

Reproduce with `engine/.venv/bin/python engine/scripts/survivorship_coverage.py` — read-only, runs
no backtest, records no trial, does not move the lab's N.

**The hole is large.** 522 of 1,041 point-in-time members have no bars (`engine/.research/
unserved.csv`). Coverage of the index as it actually stood: **48.5% (1996) → 77.6% (2015)**, rising
monotonically. 32 missing symbols carry the `Q` bankruptcy suffix.

**It does not appear to be what produces the edge.** If missing bankruptcies flattered the results,
the flattery would be largest where coverage is worst. It is not:

| | SPY | RMW | RAW | MOM | MVW |
|---|---|---|---|---|---|
| 1996–2001 (~50%) | +11.9%/yr, fall 30.4% | +12.8%, 12.4% | +17.8%, 16.1% | +18.1%, 11.1% | +12.6%, 14.0% |
| 2002–2008 (~60%) | **−1.4%**/yr, fall 40.5% | +8.4%, 10.1% | +9.4%, 15.2% | +6.8%, 11.7% | +7.4%, 11.6% |
| 2009–2015 (~70%) | **+16.7%**/yr, fall 16.2% | +14.6%, 9.0% | +19.3%, 10.7% | +14.4%, 10.0% | +14.6%, 10.0% |

**The confound, stated rather than buried:** coverage rises with time, so it is collinear with
market regime. This cannot separate "better data" from "different market" and has limited power.
It is evidence against the simple bias story, never proof the hole is harmless.

**Two findings that outrank the question we asked:**

1. **The edge is crash insurance.** It lives in 2002–2008. In 2009–2015 — a bull with no crash —
   three of the four *trail* SPY by ~2 points a year at ~60% of its drawdown. That is the trend
   gate's price, not a defect.
2. **`RAW-FR` is the only entry ahead of SPY in all three eras**, at a third to two-thirds of the
   drawdown throughout. It is also the one that most deserves suspicion for exactly that reason.

**Not buying survivorship-free data** (owner, 2026-10-07): the check did not find the damage a paid
feed would repair; it costs money monthly; and rebuilding `engine/.research` from another source
changes every `config_digest`, resetting all 110 trials and their DSRs. Revisit if a decision turns
on it.

---

## 4. One correction to carry forward

During this session I twice asserted something about the leaderboard that is **false**, and a fresh
session should not inherit it: I claimed the board reports total return only, and that three of the
five would therefore read as failures in a bull market.

Verified otherwise:

- `web/app/(app)/leaderboard/view.ts:215-217` — `rankCmp` sorts on **annualised Sharpe**, matching
  `paper/compare.py:27` and its `MIN_COMMON_SESSIONS = 63` (`compare.py:61`).
- `web/app/(app)/leaderboard/page.tsx:252` — **max drawdown is already rendered** beside total
  return on every row.
- `web/lib/metrics.ts:58-77` — the go-live checklist already shows trades, profit factor and the
  drawdown bar.

The board already reports the trade these strategies make. The residual risk is only that the hero
figure at `page.tsx:83` is `best.totalReturn`. That is a much smaller concern than I described, and
**no work should be opened on it without re-checking the page first.**

---

## 5. Questions the analysis must settle

**Q1 — the delisting stress test (the main open item).** §3 is an absence of evidence from an
era contrast that is confounded with regime. The test that isolates the mechanism has not been run:
inject synthetic delistings into the ranking universe at the historical rate and solve for the
**break-even delisting return** — how bad the assumed loss must be before the edge vanishes — then
judge whether that number is plausible. Framing it as break-even avoids having to guess a delisting
return, which is the part no free source can give us. Open: where it lives (a lab method would spend
a trial and move N, which is probably wrong for a diagnostic), and whether it needs the position
level or can be approximated from the recorded curves.

**Q2 — is go-live item 1 calibrated?** Item 1 asks for ≥ 3 months **and** ≥ 100 closed trades.
Trades bind, not months, and by a wide margin:

| | trades/yr | months to 100 |
|---|---|---|
| `RMW-FR` | 80.3 | **14.9** |
| `RAW-FR` | 80.7 | **14.9** |
| `MOM-FR` | 58.0 | **20.7** |
| `MVW-FR` | 61.8 | **19.4** |

So "3 months of paper" is really 15–21 months, and every future roster swap resets that clock for
the entry it replaces. This is the owner's dial (`backtest/dev.py:86`, `_MIN_TRADES = 100`), not the
analysis's — but the owner may not realise the 3 months is decorative, and should be told before
the clock has been running a year.

**Q3 — is `MOM-FR` the weakest of the five?** Its era edge is +6.2 / +8.2 / **−2.3**, the least
stable of the four quant entries, and it has the slowest path to a verdict (20.7 months). It was
admitted as F4's bet inside the drawdown bar. Worth asking whether a better occupant of that slot
exists in the lab, **but not before** reading the warning in Q4.

**Q4 — do not churn the roster on lab results.** Every swap restarts a ~15-month clock (Q2), and
DSR falls monotonically as Sera explores (§2), so "it no longer passes the luck test" will become
true of *everything* on the board without any book changing. A rule for when a roster entry may be
replaced — before the first one looks bad — would be worth more than any individual swap.

---

## 6. Owner context

- Roster picks approved 2026-10-07: *"i trust your judgement fully. let's go with your picks."*
  Then, on the one open swap: *"keep RAW-FR then, no swap."*
- Drawdown bar moved 15% → 20% by the owner 2026-10-07 (design §11); DSR bar 0.95 → 0.90.
- On the leaderboard: *"please keep it clean. remove all methods except SPY and the 5 roster"* —
  already satisfied by `data.ts:101`, no change was needed.
- The owner is not a quant. Analysis prose on seertrade.site/sera must stay plain: numbers only with
  their meaning, no jargon without a gloss, no ids or digests in insight bodies.
- The owner prefers measuring to estimating — §3 exists because of that preference, and it paid.

---

## 7. Verification

At `6c3bf56`, working tree clean:

```
cd engine
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  ../engine/.venv/bin/python -m pytest tests -q      # 3197 passed, 0 skipped
../engine/.venv/bin/ruff check --no-cache src tests  # All checks passed
cd ../web && npx vitest run                          # 363 passed
```

**`pytest` without `PG_TEST_URL` reports `2812 passed, 385 skipped`** — a confident green missing a
third of the suite, including every test that reads the `strategies` table. This bit a concurrent
session in this very session. Always export it.

The lab: N = 110 dev trials, 32 insights, **0 test-window looks used**. The test window
(2015-10-19 → today) is still completely unspent.
