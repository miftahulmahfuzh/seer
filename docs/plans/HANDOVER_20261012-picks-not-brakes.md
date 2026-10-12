# Handover: 2026-10-12 — measure the picks, not the brakes

**For:** an `/analyze` session that plans this work and then builds it.
**Target:** **§4.1**, an exposure diagnostic that measures a method's own picks separately from
the spare money it parks in the market. That is the whole point of this handover; everything
else in §5 is context or smaller follow-on work.
**State at handover:** `main` @ `fb0b57f`. Clean tree, nothing unpushed, no worktrees, no running
Sera children. 4,341 engine tests passing with Postgres up (`PG_TEST_URL`), 3 opt-in skips,
`ruff check engine` green. Lab: 130 methods, 354 dev trials, 184 insights, 4 test-window looks
used (none spent today).

---

## 1. Why this exists

Batch `sera-20261012-0832` ran four methods at the lab's binding constraint — the rule that a
strategy may never lose more than a fifth of its value from its peak. All four drawdown machines
worked. None of them paid. That part is finished and journaled (synthesis insight 183).

The batch's *accidental* finding is what this handover is about.

M0107 included a control arm that stripped the parked SPY out of the calm dividend-raiser book.
The result: the dividend picks filled only about four slots in ten; the rest of the money sat in
SPY, timed by the 200-day switch. Measured with that parked money removed, **the picks lose to
the market in every era** — behind 4.4 points a year in 1996–2002, ahead ~1 point in 2003–2008,
behind 5.7 points from 2009. The timed SPY holding was worth about 9 points a year early on; the
switch on top of it about 0.4.

So a family of six methods and thirty-five variations, which the lab spent three batches tuning,
never had a picking edge at all. It is now closed (risk insight 175).

**Nothing in the lab would have caught this.** No method reports how much of its money is in its
own picks, or what those picks did alone. It took a deliberately-built control arm, thirty-five
variations late. That is feature-wish 174 and it is the work to plan.

## 2. The stake

Clean families (no test-failed kin) that still hold a dev-eligible method:

| Family | Dev-eligible |
|---|---|
| `stock-dividend-change-drift` | 5 — **closed 2026-10-12**, the parked-SPY finding |
| `stock-short-term-reversal` | 1 |
| `stock-seasonality` | 1 |
| `stock-overnight-intraday` | 1 |
| `stock-momentum-attention` | 1 |
| `stock-core-satellite` | 1 |

That is the lab's entire live space: five methods. Every family with a *demonstrated* picking
edge (momentum, residual momentum, multi-factor blend) is permanently closed by the hard gate's
kin walk, and cannot be reopened. One of the five, `stock-core-satellite`, is parked SPY **by
construction**. The others may carry the same hole — M0107's book filled 42% of its slots and
nobody knew until a control arm was built for an unrelated question.

**If the remaining four are also mostly parked market money, the lab has no live candidate at
all, and should be told so plainly rather than discovering it one family at a time.**

## 3. The constraint that shapes the design

`N` for the deflated Sharpe counts **distinct methods** (`lab/npolicy.py`), so every new method
raises the luck hurdle for every method already recorded. Measured today: N=74 gives a hurdle of
z=2.4228; N=78 gives z=2.4419 — **0.79% higher SR\* for the whole lab, retroactively**, including
near-misses sitting at 0.884 and 0.898.

So this diagnostic **must not be built as new lab methods.** The established pattern is
`lab costs`: re-runs a method, prints a report, records no trial, leaves N unmoved, spends no
test-window look. Follow it.

Evidence it is computable: M0107's session already produced exposure figures from a run
(HOST 70.4% invested, NONE 41.9%) and per-era de-funded leads. Nothing new has to be invented;
it has to be made routine and applied to every method instead of hand-built once.

## 4. The work

### 4.1 The exposure diagnostic (the target)

Roughly — the planning session should decide the real shape:

- For a given method and variant, report **what share of the book's money was actually in its own
  picks**, over the whole window and per era, versus parked in the market or in cash.
- Report **what the picks alone did**, with the parked holding removed and every gate off, against
  SPY TR on deposit-matched money, split by era (1996–2002, 2003–2008, 2008 alone, 2009–2015) —
  the same split M0107 used, because that is the split that exposed the problem.
- Report-only. No trial recorded, N unmoved, no test look, nothing written to `lab.sqlite`
  except — if the planning session judges it worth it — a note or insight.
- Then **run it over the five surviving clean candidates** and journal the answer.

Open design questions for the planner, not for me to pre-empt:

- Whether this is a new `lab` subcommand or an extension of an existing one.
- Whether "parked" can be detected generically (a holding in SPY or another index ETF, or an
  unfilled slot held as cash) or has to be declared per method.
- Whether the naked-picks run can reuse the method's own allocator with gates disabled, or needs
  each method to expose a hook. M0107 did it by adding variant arms; doing that for five methods
  would cost five method ids and the N inflation above, so prefer a generic path.
- Whether to backfill the report across all 130 methods or only the live five.

### 4.2 Why not the alternatives (decided 2026-10-12, with the owner)

- **Another Sera batch — not yet.** It would explore families this diagnostic may be about to
  invalidate, and it costs the N inflation in §3. Run one *after*, with a slate informed by what
  survives.
- **Another data source — no.** The batch showed data is not the binding constraint, and insight
  59's caveat has aged well: adding datasets without changing how methods are evaluated mostly
  buys new ways to overfit.
- **The idle-cash interest rule — second, not first.** See §5.1.

## 5. Everything else left open

### 5.1 Interest on idle cash — half done (insight 184)

**Done today** (commit `4ed7d71`): the ten market-wide series are back in **both** research stores
from a **free** source. `python -m seer_engine market_series --source yfinance --fetch --refresh
[--store <dir>]`. Dev window: T13W covers 4,969/4,984 days (99.7%), VIX 100%, 41,777 rows. Test
window: 69,352 rows, 100% on the yields and VIX. Price fingerprints unchanged on both
(`5451195f`, `bfd3ca85`), so none of the 354 recorded trials is stranded, and both stores rebuild
byte-identically from one cache. This also restores reproducibility for M0039 and M0085.

**Not done:** nothing in the simulator credits interest on money not held in shares. Idle cash
still earns zero. Over the dev window the bill rate averaged 2.6%/yr (5.5% through the 1990s,
~0% after 2009); M0084's switch sat in cash 29% of the time, so it was charged roughly three
quarters of a point a year for nothing.

**Why it was not simply switched on.** `sim/` is shared by the lab's backtests *and* the live
paper books, and the lab compares trials on the price files alone — a change in how cash behaves
is invisible to that check. Credit interest unconditionally and every new trial silently stops
being comparable with the 354 recorded, with nothing marking the break. That is the shape of the
2026-10-08 funding bug. It should be an **opt-in named rule** like the real Gotrade fee presets,
defaulting to off, so old trials keep meaning what they meant. **That design choice is the
owner's and has not been made.**

Expect honesty, not rescue: the era this helps most (1990s) is the era those books already won.

### 5.2 A guard against rebuilds dropping optional store files

`build_store` writes the price files plus `fundamentals.csv`. The other two optional files —
`market_series.csv` and `dividend_announcements.csv` — are written by their own commands and are
**silently lost on every rebuild**. That is exactly how the lab came to score idle cash at zero
for its whole history and how M0039's and M0085's trials stopped being reproducible. Nothing
warns; the store just quietly has less in it.

Distinct from `RESEARCH_STORE_CLOBBER_GUARD_PLAN.md`, which guards a store against being
overwritten from another checkout.

### 5.3 EODHD — a time-boxed opportunity, if the owner still has the key

`HANDOVER_20261010-eodhd.md` records a paid month whose key was **valid until 2026-11-10** — still
in the future. But on this machine (`pc`, the one that handover says held the ~215 MB cache):
`engine/.cache/eodhd/` is **gone**, and `.env.local` **no longer contains `EODHD_API_TOKEN`**.

If the owner still has that token anywhere, `dividend_announcements --fetch` could be re-run for
free before 2026-11-10 and would restore the declaration dates (insight 109: event books could act
weeks earlier than the ex-date). After 2026-11-10 it costs another subscription. **Worth asking
the owner before that date.** Do not plan work that assumes the key exists.

### 5.4 The research store on the other laptop is stale

Both store fingerprints moved today (`399d0d25`→`77c37d55` dev, `bbe7abfb`→`2f8d291b` test). The
`sync-research-store` skill is content-addressed on the fingerprint, so the GPD's copy is behind
and will not have the market series.

### 5.5 Lab ideas queued by the batch, not yet run

`M0110` downside participation · `M0111` market-weighting vs equal slots · `M0113` slow to leave,
quick to return · `M0114` re-frame the one book measuring its frame · `M0115` dead-zone brake ·
`M0116` asymmetric fall brake.

**`M0112` is journaled as refused, with reasoning on the method.** Its family *and* its parent are
`M0022`, which reads test-failed, so the hard gate's kin walk closes it before any number it
produces is read. A child proposed it as "the lab's best live shot"; it is the one shot that
cannot clear the gate. Do not resurrect it without changing the rule in `lab/hardgate.py` and
arguing for that in the commit.

### 5.6 Remaining data jobs, in the order I would take them

All free unless marked. None is the binding constraint (§4.2).

1. **RSP**, equal-weight S&P 500, one ticker since 2003. Partly answered already — M0108's
   equal-weight yardstick measured equal slots costing ~1.4 pts/yr and roughly doubling crash
   damage (insight 171) — so this is now cheap confirmation rather than discovery.
2. **FRED credit spreads** (`BAA10Y`, `T10Y2Y`) — free, different loader from the yfinance path;
   unblocks the macro-regime gate idea `M0038`. The Treasury yields themselves are now in.
3. **FINRA short interest**, twice monthly, needs a real loader and a point-in-time join on the
   settlement date, never the publication date. Blocks `M0040`.
4. **Point-in-time share counts before 2009** — blocks `M0047`, and the lab's market-cap figure is
   *actively wrong today* (unadjusted share count × split-adjusted close). EDGAR XBRL starts ~2009.
5. **Survivorship-free prices** — the one purchase worth arguing for (522 of 1,041 index members
   have no prices; 1996 coverage 236/487). **The standing rule says do not buy until a method
   clears dev-eligible + a majority of walk-forward folds + a positive 2009–2015 edge.** Nothing
   has. This batch produced no buy signal.

### 5.7 Smaller feature wishes still open

182 (a safety rule can only be checked weekly, never daily) · 101 (dividend withholding tax is not
simulated) · 98, 73, 72, 63, 42, 38, 4.

## 6. Things that will bite you

- **`lab stage` is the only way to commit `lab/lab.sqlite`**, and every such commit must include
  `web/data/lab.json`. CI fails a database commit without it.
- **Mid-batch, never `git pull --rebase --autostash`.** It rewrites `lab.sqlite` under a running
  child's open connection. Use `git fetch` + `git merge --ff-only`.
- **Reading the lab with a `lab` subcommand dirties `lab.sqlite`** (it migrates on connect), even
  for a pure read.
- **The research store is not in worktrees.** Point `SEER_RESEARCH_STORE` at
  `/home/miftah/seer/engine/.research`; a rebuild is ~30 minutes for nothing.
- **Worktree tests need `PYTHONPATH`**, or pytest silently tests the main checkout.
- **DB tests need Postgres**, and CI fails if they skip:
  `docker start seer-pg` then `export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres`.
- **The hard gate has no override.** No flag, no environment variable. A refusal is a finding to
  record, not an obstacle to route around.

## 7. Where to read the batch

- Synthesis insight **183** — the owner-facing account of the whole batch.
- Risk insight **175** — the dividend family's edge was parked SPY, and what that implies.
- Insights **176–182** — the switch priced alone, the weekly/monthly cadence cost and its
  mid-run correction (179), the idle-cash gap (178), the proportional brake (180–182).
- Scrollback of all four children: `.workflows/sera/sera-20261012-0832/` (gitignored).
- Design doc **§13** carries a dated re-measurement from today: the dev trades bar now holds out
  five trials rather than two, its conclusion survives but its reasoning changed, and every trial
  it has ever held out is a market-timing book.
