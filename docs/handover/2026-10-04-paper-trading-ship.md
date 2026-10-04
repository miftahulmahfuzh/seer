# Handover: run Seer on paper every night, show it month by month, and ship it (roadmap P4 + P5 + v0.1.0)

Written 2026-10-04, after P7a landed on `main` @ `251d632` (pruned at `fc9c5d9`) with **"none
eligible"**. P7b does not run.

The owner chose to keep building:

> *"i still don't want to give up developing this app. how about we just keep going with our major
> plan, then we'll ship it. and we will see how it performs this month WITHOUT MY REAL MONEY …
> the app should be able to show us how seer performs month by month on paper"*

This is the ROADMAP's option **(b)**:
- SPY buy-and-hold is the honest champion;
- Seer recommends no real buys;
- research strategies still paper-trade every night, and the app shows how they do.

Pass this file straight to `/analyze` in a fresh session, and read all of it first. Like the
earlier handovers, it separates:
- decisions that are **already made**;
- facts that were **verified**;
- questions the analysis still has to settle.

---

## 0. In plain words

Until now Seer has only been tested on the past (backtests). This step makes it **live, on
paper**:
- Every night after the US market closes, Seer fetches the day's prices.
- It settles yesterday's paper orders and makes tomorrow's paper decisions for each strategy.
- It records each strategy's paper money.

No real money moves. The owner opens the app and sees, month by month, how each paper strategy
did next to SPY.

What one month can and cannot tell:
- **One month is mostly luck.** The monthly table is for watching, not for deciding.
- Design §1 still asks for ≥ 3 months and ≥ 100 closed trades of forward paper trading, plus a
  passed backtest, before any strategy may touch real money. **No strategy has passed the
  backtest gate.** So nothing in this handover leads to real money, whatever the paper results
  show.

---

## 1. Where we are

| Phase | State |
|---|---|
| P0 Foundations | Mostly done. CI (`.github/workflows/engine-ci.yml`) runs engine pytest and web vitest on push, and it is green on `main` (verified 2026-10-04). ROADMAP still says "CI still open": the analysis checks whether lint is the missing part, then closes P0 or finishes it |
| P1 Data pipeline | Done. `nightly` fetches bars (Massive grouped-daily), splits and USD/IDR, and writes a `runs` row. `.github/workflows/nightly.yml` runs at 23:00 UTC Mon–Fri with a 01:00 retry. Repo secrets `DATABASE_URL_UNPOOLED` and `MASSIVE_API_KEY` are set (2026-10-03). One manual run succeeded (2026-10-03) |
| P2 Fill simulator | Done (`seer_engine/sim`, bracket engine) |
| P3, P3b, P6a | Strategies A, A2 and B all **failed** the backtest gate. `STRATEGY_A_PARAMS` is frozen; `STRATEGY_A2_PARAMS` and `STRATEGY_B_FROZEN` are `None` |
| P7a | Done. `TradeRules`, the book engine (`sim/book.py`), allocators and families F1–F11, the research store and `backtest_dev`. 54 candidates, **none eligible** (all 54 failed max DD ≤ 15%) |
| P4 Nightly paper trading | **Not started.** It was blocked by "no strategy passed". **This handover unblocks it as paper-only** |
| P5 Web app | Done on demo data (`npm run db:seed-demo`): Sign-in, Today, Positions, Leaderboard, History. Not deployed. seertrade.site DNS pending |
| v0.1.0 | "P0–P5 done. The 3-month forward clock starts on the first live paper day." |

Read before planning:
- `docs/plans/2026-10-03-seer-design.md`: all of it. **§1 stays law.** §3 (architecture), §6 (UI)
  and §8 (failure handling) apply directly.
- `docs/ROADMAP.md`: P4, P5, P7a, P7b and "Later".
- `engine/package_readme.md`:
  - `sim` (the bracket engine and the book engine);
  - `strategies` (A, the allocators, F1 and FAC);
  - `backtest` (`run_backtest`, `run_book`, `run_rules`);
  - `nightly`, `## Performance`.
- `docs/backtests/2026-10-04-p7a-dev-exploration.md` ("Results", "Survivorship bias", "Plain
  statements").
- `docs/runbooks/data-pipeline.md`.
- `web/lib/data.ts`, `web/lib/metrics.ts`, `web/app/(app)/*/page.tsx`, `web/scripts/seed-demo.mjs`.
- The Seer v2 design that P5 implemented: `docs/plans/claude-design-brief.md` and
  `docs/plans/2026-10-03-web-v2-implementation.md`.

---

## 2. Decisions

### Law: do not reopen

| Topic | Rule |
|---|---|
| Go-live | **Design §1, unchanged.** Paper results never unlock real money unless every §1 item holds, including a passed backtest gate (none has). The UI must never present a paper strategy as something to buy for real |
| Same code path | Paper trading runs the **same** pure code the backtests ran: `sim.size_picks` + `sim.step` for bracket strategies, `sim.step_book` for book strategies, and the strategy or allocator's `*_prepared` path or its single-window path (they are proven identical). No re-implementation of trade logic in the nightly job or in the web app |
| No look-ahead | Decisions for session S use data through `prev_session(S)` only, and point-in-time membership from `universe` |
| Closed records | A, A2, B and the P7a reports and registry stay as they are. `backtest/registry.py` is not edited |
| Read-only UI | Vercel only renders (design §3). Every computation that changes state happens in the GitHub Actions job |
| UI design | Seer v2 design exactly. Every button is icon-only (Lucide) with `aria-label` and a tooltip. No generic-looking UI |
| Honest reporting | Losing paper results are shown like winning ones. The repo is public on purpose |

### Decided by the owner (2026-10-04)
- Keep developing. Ship v0.1.0. Run Seer **on paper only, with no real money**.
- The app must show **month-by-month paper performance** next to SPY.
- The owner may hold SPY directly with their own money. That needs no Seer approval and is not
  modelled in Seer.

### Decided in this handover (each can be overturned by a one-line change before planning)

| # | Topic | Decision | Why |
|---|---|---|---|
| D1 | **Paper roster** (fixed now, before any paper result) | Four portfolios, each starting from 20,000,000 IDR at the first paper day's USD/IDR (see the table after this one) | The best-known options across both engines and both horizons. Few enough to read on one screen |
| D2 | **Champion** | `SPY` is the champion (`is_champion = true`, `is_benchmark = true`). No research strategy is champion. Today therefore shows **no buy recommendations**: a clear "SPY buy-and-hold is the champion; Seer recommends no buys" state, following the Seer v2 design's empty-state style | Option (b); design §3 "Home shows only the champion strategy's picks" |
| D3 | **Paper picks are visible but labelled** | Each research strategy's orders and positions are visible in Positions and History (and per strategy where the design has a switcher), marked as **paper**. They never appear on Today | The owner wants to see what Seer does without it reading as advice |
| D4 | **Frozen strategies, honest clock** | Each roster entry is frozen: its id, params and rules. Changing anything creates a **new strategy id** whose paper clock starts on its own first day. The `strategies` row records `paper_start` (first paper session) and the frozen spec (`params` jsonb: registry id or `STRATEGY_A_PARAMS.as_dict()`, plus the rules id) | ROADMAP "Later: parameter versioning so changes reset the forward clock honestly", pulled forward because results are now live |
| D5 | **Month-by-month view** | A per-strategy, per-calendar-month table, with the SPY row for comparison. Columns: return, SPY return over the same month, closed trades, worst drop within the month. Plus a since-start row and a "partial month" marker for the first and current months. Computed in `web/lib` from `equity_snapshots` and `orders`/book trades, with the same definitions as `web/lib/metrics.ts`. It lives on the Leaderboard screen or its own tab, following the Seer v2 design. **The analysis picks the placement and states it** | The owner's request; engine-agnostic because every strategy writes `equity_snapshots` |
| D6 | **Book-strategy persistence** | A migration `003` adds tables for book strategies: a book state (cash, equity, last session), positions (`Position` fields: fractional-capable shares, stop/take, days held, episode cost/income, exit pending), fills and closed trades (`Trade`). The existing `orders` table keeps serving bracket strategy A, and every strategy writes `equity_snapshots`. **The analysis may choose a different shape if it states why** (see §6) | `orders` cannot hold book positions: `slot` 1..4, int shares, `exit_reason` limited to tp/sl/time/gap |
| D7 | **System-level replay check** | A command (or test) re-runs each roster strategy with `run_rules` over `[paper_start, last session]` on Neon's bars, and asserts that the DB state written night by night equals the replay. The same holds for every snapshot, closed trade and open position | The strongest proof that "backtest and live share one code path" (design §9) |
| D8 | **Dividends while holding** | Book strategies with `dividends=True` (F4, F1) and the SPY benchmark are credited cash dividends on the ex-date, as in P7a. The nightly job therefore needs ex-dividend data for held symbols and SPY. **The source is for the analysis to verify** (§6) | D11 of the P7a handover; otherwise long holds are understated against SPY total return |
| D9 | **LLM explanations** | Optional and failure-tolerant (design §8): an explanation per new paper entry when `LLM_*` is configured, otherwise "unavailable". Paper correctness never depends on it. The analysis may schedule it as the last engine phase | Design §4; not on the critical path |
| D10 | **One nightly writer** | The paper step runs after the bars step in the same scheduled job (`nightly.yml`, concurrency group `seer-db-writer`), in its own command (for example `paper`). It is idempotent per (strategy, session): a re-run of a session that already succeeded writes nothing | Design §8 "idempotent on (strategy, date)"; the existing `runs` uniqueness |
| D11 | **Start date** | Paper trading starts at the first scheduled nightly run after P4 lands on `main` with the migration applied. October 2026 will be a **partial month**, and the UI says so | No back-dated "paper" results: anything before the start is a backtest, not forward evidence |
| D12 | **No real-money surface** | No "buy this" for research strategies. The go-live checklist (Leaderboard) shows each strategy's real §1 status, including "backtest gate: not passed" | Design §1 law; owner memory "proof before money" |

**The paper roster (D1):**

| Strategy id | What it is | Engine | Rules | Why it is on the roster |
|---|---|---|---|---|
| `SPY` | Buy-and-hold SPY with dividends reinvested (`benchmark.buy_and_hold` semantics, from paper start) | benchmark | — | The champion and the yardstick |
| `A` | Strategy A, `STRATEGY_A_PARAMS` (frozen in P3) | bracket (`run_backtest` path) | `DESIGN_V0` | P4 was designed around it. It trades several times a week, so the month shows activity. It failed its gate, so it is research only |
| `F4-MOM12-N20-TREND` | 12-1 momentum, top 20 S&P 500 ∪ NDX members, SPY 200-day filter | book | `MONTHLY_HOLD` | P7a's best MAR. On 1993–2015 it made CAGR +16.2% vs SPY TR +7.9%, max DD 22.2%, PF 2.27, 1,154 trades. **Survivorship-flattered** (522 of 1,061 dev members unserved), so forward paper is its honest test |
| `F1-SPY-SMA200-M` | Hold SPY while it closes above its 200-day average, checked monthly; else cash | book | `MONTHLY_HOLD` | The simplest drawdown cutter. ETF-only, so it has no survivorship bias. Dev: CAGR +9.8% vs +8.9%, max DD 18.7%, only 11 trades |

Ids are the P7a registry ids where they exist, and `strategies.params` names the registry entry.
Monthly strategies make one decision per month, so a single month shows little; that is
expected.

---

## 3. Verified facts (2026-10-04): trust these

- `main` @ `fc9c5d9`. CI is green on `251d632`.
- **Neon schema** (`db/migrations/001_init.sql`, `002_engine.sql`):
  - tables `strategies`, `runs`, `orders`, `bars`, `equity_snapshots`, `fx_rates`,
    `action_dismissals`, `schema_migrations`, `universe`, `split_adjustments`, `backfill_log`;
  - `orders.slot` is 1..4, `shares` is int > 0, and `exit_reason` is in (tp, sl, time, gap);
  - `runs` has `is_demo`, and a unique index on `session_date` for non-demo runs;
  - there is **no dividends table**.
- **`nightly`** (`commands/nightly.py`):
  - purges demo data when a demo run exists;
  - computes `run_dates(now)`;
  - fetches the missing sessions (≤ 30), splits and FX;
  - writes bars, splits, FX and `finish_run` in one transaction.
  - It makes **no picks** and writes no orders or snapshots yet.
- `bars`: 1,817,429 rows through 2026-10-02 (663 symbols); the nightly appends from Mon
  2026-10-05.
- **The web** (`web/lib/data.ts`):
  - `strategies()`, `champion()`, `runStatus()`, `picks()`, `positions()`, `closedTrades()` and
    `leaderboard()` read `strategies`, `orders`, `equity_snapshots` and `runs`;
  - there is no monthly view;
  - the leaderboard computes metrics from all snapshots and closed `orders`;
  - `web/lib/slots.ts` assumes 4 slots.
- **The book engine** (`sim/book.py`) is pure and Decimal-only, and covers signal exits,
  rebalancing, dividends, fractional shares and an idle instrument. `run_book` and `run_rules` are
  in `backtest/book_runner.py`.
- The bracket path has `sim.apply_split` for live orders. **The book engine has no split
  handling for live positions** (P7a never needed it: backtest bars are pre-adjusted).
- **Families:**
  - F1 (`strategies/f_index.py`, `TIMING`) needs only SPY's bars;
  - FAC (`strategies/f_factor.py`, `FACTOR`) needs members' bars and SPY, all in Neon;
  - neither needs an ETF other than SPY.
- **Dividends:** `engine/data/spy_dividends.csv` (vendored, from 2015-03-20) feeds the backtest
  benchmark. `seer_engine/yahoo.py` has `download_actions` (yfinance with dividends, P7a).
  `massive.py` has no dividends call today.
- Repo secrets set: `DATABASE_URL_UNPOOLED` and `MASSIVE_API_KEY`. **Not verified:** `LLM_*`
  secrets, Vercel project and env, and the seertrade.site DNS.

---

## 4. Scope

**In scope:**
1. **Engine, paper step.** A new impure command and its pure core. Per roster strategy, per new
   session:
   - load its state;
   - apply splits that executed on the session (bracket: `apply_split`; book: a new pure split
     rule for positions);
   - step the session (settle);
   - credit dividends (book, SPY);
   - force-close symbols whose bars ended (as the runners do);
   - compute targets or picks for the next session;
   - persist orders, positions, fills, trades and the equity snapshot;
   - write the SPY benchmark snapshot.
2. **Migration `003`** (D6), plus the `strategies` rows for the roster with `paper_start` and the
   frozen spec (D4). The demo seed (`seed-demo.mjs`) is updated so the demo matches the new shape.
3. **Replay check** (D7) and the failure handling of design §8:
   - a failed bars run means no paper step;
   - stale data means the UI shows "do not trade";
   - holidays mean no session.
4. **Web:**
   - the Today champion state (D2);
   - paper labelling (D3);
   - book positions and trades in Positions and History;
   - the month-by-month table (D5);
   - leaderboard metrics including book strategies;
   - go-live checklist honesty (D12);
   - `slots.ts` no longer assuming 4 slots for book strategies.
5. **Optional LLM explanations** (D9).
6. **Ship:**
   - P0 CI closed (lint if that is the gap);
   - deployed to Vercel;
   - the owner steps for DNS and secrets written into a runbook;
   - the README written at release (owner rule: the README comes at the end, right before the
     GitHub release);
   - the `v0.1.0` release once the acceptance below holds.
7. **Docs:** `engine/package_readme.md`, `docs/ROADMAP.md` (P4 unblocked as paper-only, P5, and
   v0.1.0) and a runbook for paper operations.

**Out of scope:**
- Real money of any kind.
- Editing design §1.
- New strategies or registry appends (a later handover).
- P7b.
- Strategy C.
- Changes to the closed backtest reports.
- Notifications, and the real-trade journal (ROADMAP "Later").

---

## 5. Acceptance criteria

1. **Same path, proven.** For every roster strategy, the replay check (D7) equals the DB state
   after ≥ 5 consecutive nightly sessions. This holds on synthetic data in tests, and on Neon once
   live.
2. **No look-ahead and idempotency.**
   - Changing any bar dated ≥ S leaves S's decisions unchanged.
   - Re-running a session that already succeeded writes nothing.
   - A failed run leaves no partial paper state, because everything happens in one transaction.
3. **Splits and dividends.**
   - Synthetic tests cover a split on a held book position and on a pending or open bracket order.
   - They cover a dividend credited on the ex-date to a held book position, and to the SPY
     benchmark.
4. **Monthly view.**
   - The values are hand-checked against a fixture: month boundaries, the partial first and
     current months, months with no trades, and SPY on the same months.
   - It renders on the iPhone XS Max width and on desktop, in light and dark, in the Seer v2
     design with icon-only buttons.
5. **Today** shows the SPY-champion, no-buys state. Research picks never appear there.
   Stale-data and failed-run states still work.
6. **P4 done** (ROADMAP): 5 consecutive trading days run unattended on GitHub Actions with
   correct settlement. That means correct per the replay check, and it is verified in the run
   logs and the UI.
7. **Ship:**
   - The app is live on Vercel, signed in with Google for `ALLOWED_EMAIL` only, and installable as
     a PWA.
   - seertrade.site is connected, or the runbook says exactly which owner step remains.
   - CI is green with engine tests at 0 skipped, and web tests pass.
8. **Docs:**
   - the readme sections;
   - a ROADMAP P4 entry stating "paper-only (owner option (b), 2026-10-04); no real-money
     recommendations; §1 unchanged";
   - the runbook;
   - the README and `v0.1.0` release, last.

---

## 6. Open questions for the analysis to settle (recommend, don't ask)

- **Persistence shape for book strategies.** Recommended: separate `book_*` tables (D6) rather
  than widening `orders`. The web reads both through one data layer. Alternative: one generic
  positions table for both engines. Pick one, state why, and keep migrations additive (no
  destructive change to `orders`).
- **The pure "nightly step" core.** Recommended: a pure function per engine,
  `(state, session, bars, members, history, dividends, splits) -> (new state, writes)`, built from
  the same calls `run_backtest` and `run_book` make. The replay check (D7) is then a loop over the
  same function. Consider refactoring the runners to call it only if their outputs stay
  byte-identical: the closed reports must still re-render exactly. Otherwise duplicate the loop
  body and let D7 prove equality.
- **History for strategies at night.** A needs 200 bars and FACTOR about 253, read from Neon. Load
  only the needed window per night, or reuse `backtest.io.load_market`'s cache? Measure on the
  real table.
- **Dividend source going forward** (D8). Check whether Massive's free tier serves ex-dividend
  data. Otherwise use yfinance `download_actions` for held symbols plus SPY each night. Then
  decide whether to persist dividends in a new table (recommended, so the replay check is
  reproducible) or refetch.
- **Book-engine splits.** Pick the rule, mirroring `sim.apply_split`:
  - shares × factor, floored for whole shares;
  - stop, take, mark and entry price divided by the factor;
  - cash in lieu for the fraction.
- **SPY benchmark persistence.** Recommended: an `equity_snapshots` series for `SPY` from paper
  start, computed nightly with the `buy_and_hold` rules (whole shares, dividends reinvested at the
  ex-date close).
- **Where the monthly view lives** (D5), and how the leaderboard handles strategies whose paper
  start differs. Recommended: every roster entry starts on the same first paper day.
- **Engine-level metrics for book strategies in the web.** `strategyMetrics` takes snapshots plus
  closed-trade P/L. Book trades (holding episodes, idle episodes excluded) must feed it the same
  way `run_stats` does.
- **Phase split.** This spans:
  - migration and seeding;
  - the pure nightly cores (bracket and book);
  - splits and dividends;
  - the paper command and its workflow step;
  - the replay check;
  - the web data layer;
  - the monthly view;
  - the Today, Positions and History changes;
  - LLM explanations;
  - ship and docs.

  Make it many small phases, as P7a did. The live 5-day run (acceptance 6) has to wait for real
  sessions, so the final phase may be an operational check that spans days. Plan for that rather
  than blocking on it: land the code, start the clock, and leave the 5-day verification and the
  release as a clearly stated final step.

---

## 7. Environment

Unchanged from `docs/handover/2026-10-03-trade-rules-revision.md` §6:
- **Shell:** WSL2 Ubuntu, zsh. Python 3.11. A worktree needs its own `engine/.venv`:
  `python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'`.
- **Engine tests:** `docker start seer-pg`, then
  `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`.
  0 skipped.
- **Web:** `cd web && npm ci && npx vitest run`.
- **Real runs:** set `SEER_ENV_FILE=/home/miftah/seer/.env.local`, and never `source` it.
- **Owner steps** need the owner, so document them in a runbook instead of waiting:
  - Vercel project and env (`DATABASE_URL`, `AUTH_*`, `ALLOWED_EMAIL`);
  - DNS at Domainesia;
  - `LLM_*` repo secrets.
- **Neon free tier:** measure storage before adding tables, and keep the new tables lean.
- The repo is public on purpose. Paper losses are shown too.
