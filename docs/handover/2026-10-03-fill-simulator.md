# Handover — Seer fill simulator (roadmap P2)

Written 2026-10-03, after P1 (data pipeline) landed on `main` @ `c81c1e8`. This file is meant to
be passed straight to `/analyze` in a fresh session. Read all of it first: it separates decisions
that are **already made**, facts that were **verified**, and the few questions the analysis
still has to settle.

## 1. What Seer is (one paragraph)

Seer is a personal web app. Every night it proposes up to 4 US stocks (slots S-E-E-R) to buy in
the next US session. Each pick comes with a **Limit Buy, Take Profit, Stop Loss and whole-share
count**, which the owner types into a Gotrade bracket order. Several strategies paper-trade side
by side on 20,000,000 IDR each. Real money only goes in once the champion strategy passes a fixed
go-live checklist. The owner is new to trading. What matters is **measured profit against buying
and holding SPY**, not how elegant the method is.

Read before planning:
- `docs/plans/2026-10-03-seer-design.md`: **§5 trade rules are law**; §8 and §9 also apply.
- `docs/ROADMAP.md`: P0–P6. **This handover covers P2 only.**
- `db/migrations/001_init.sql`: the `orders` and `equity_snapshots` tables the simulator's state
  must map onto (P4 persists it; P2 does not write to the database).
- `web/lib/data.ts`, `web/app/(app)/page.tsx:26`, `web/app/(app)/history/page.tsx:16`: how the UI
  reads `days_held` and `exit_reason`.
- `engine/package_readme.md` and `docs/runbooks/data-pipeline.md`: what P1 built.

## 2. Goal of this task (P2 — fill simulator)

Build the order-lifecycle and portfolio simulator in `engine/` as **pure, deterministic Python**:
no database and no network in the core. **One code path** must serve both the 10-year backtest
(P3) and nightly forward paper trading (P4). The ROADMAP calls this the critical path, and design
§9 calls it "the highest-priority code in the repo".

It must:
1. Take pending bracket orders through `pending → open → closed` or `pending → expired`, exactly
   as in design §5 plus the decisions in §3 below.
2. Size orders with whole shares across 4 slots, using equity ÷ 4 recomputed daily.
3. Keep cash and equity per strategy portfolio, with 0.1% costs per side, and produce a
   per-session equity snapshot.
4. Give P3/P4 a small API: advance a portfolio through one session's bars, report the events
   (fill, expire, exit), and size new picks for the next session.

**Done when:** every edge case in design §5 and in §3 below has a passing test on synthetic bars
(ROADMAP P2), the full engine suite stays green with 0 skipped, and the API is documented in
`engine/package_readme.md`.

**Out of scope, don't build:** strategies and signals (P3), the backtest runner and report (P3),
the SPY buy-and-hold benchmark curve (P3), writing to `orders`/`equity_snapshots` and wiring into
`nightly` (P4), LLM explanations (P4), any web change.

## 3. Decisions already made — do not reopen

From design §5 (law):

| Topic | Rule |
|---|---|
| Place | Limit + TP + SL for the next US session |
| Fill | Filled only if session **low < limit** (strict). If **open < limit**, fill at **open**; otherwise fill at limit |
| Unfilled | Expires at the end of its session; the slot is freed |
| TP / SL | Evaluated **from the session after the fill**. If both are in range on the same day → **SL first**. A gap through either → fill at the open |
| Time stop | Not exited by the close of trading day 5 → exit at the next open (in real life the owner cancels the bracket and market-sells) |
| Costs | 0.1% of notional per side (fees + slippage) |
| Portfolio | 20,000,000 IDR converted to USD at the start-date FX rate; tracked in USD. 4 slots; slot size = equity ÷ 4, recomputed daily; shares = floor(slot / limit); ineligible if < 1 share fits; no adding to an existing holding; 0 picks is valid |
| Prices | Split-adjusted bars only (P1); the simulator never sees dividend-adjusted prices |
| Holidays | No session, no day counted (NYSE calendar via `seer_engine.dates`) |

Decided in this handover. These are recommendations for an owner who is new to trading; each one
can be overturned with a one-line change before planning:

| Topic | Decision | Why |
|---|---|---|
| Day counting | The **fill session is day 1**. TP/SL run on days 2–5. If the position is still open after day 5's close → exit at the **open of the next session**, reason `time`. That exit happens at the open, before any TP/SL check that day | Matches the UI: `page.tsx:26` shows the action item when `day >= 5`, worded "day 5 of 5. Cancel bracket and sell at market". The demo seed also counted the fill session as day 1 |
| TP trigger | Intraday **high > TP** (strict, like the entry). Exit at TP | A sell limit only fills for certain when price trades through it; this is conservative, mirroring the entry rule |
| SL trigger | Intraday **low ≤ SL** (touch). Exit at SL | A stop triggers on touch; this is conservative |
| Gap at the open | **open ≤ SL** → exit at the open, reason **`gap`** (the UI labels `gap` "Gapped past stop at open"). **open ≥ TP** → exit at the open, reason **`tp`** | Keeps `gap` meaning "loss beyond the stop", as `history/page.tsx:16` already shows |
| Costs in P/L | `pnl_usd = (exit − fill) × shares − 0.001 × (exit + fill) × shares` | Same formula the demo seed used; the web's profit factor and win rate read it |
| Sizing budget | `budget = min(equity ÷ 4, cash not already committed to other pending orders that night)`; `shares = floor(budget / (limit × 1.001))` so the buy cost fits; `< 1` → ineligible | Without the cash cap, positions that rose in value would let new picks spend cash that doesn't exist |
| Equity | `cash + Σ shares × close` at each session's close; a missing close uses the last known close. Pending orders reserve nothing in equity | Equity matches `equity_snapshots.equity_usd`, and `cash_usd` is real cash |
| Session order | For each session: (1) time-stop exits at the open, (2) gap exits at the open, (3) intraday SL, then TP (SL first), (4) fills of pending orders, (5) expiry of the unfilled ones, (6) mark to close. A position filled today is not checked against TP/SL today | Follows design §5 exactly |
| Slot reuse | A slot freed during session S (exit or expiry) can take a new pick placed that night for S+1 | Picks are made after S's close |
| Numbers | `Decimal` everywhere. Prices quantized to 4 dp (`numeric(12,4)`), cash/equity to 4 dp (`numeric(14,4)`), shares are `int` | Matches the schema and `seer_engine.bars.Bar` (Decimal prices) |
| State shape | Order state mirrors the `orders` columns (`status`, `fill_date`, `fill_price`, `days_held`, `exit_date`, `exit_price`, `exit_reason`, `pnl_usd`, `slot` 1–4, `shares`), so P4 can persist it without translation | P4 writes these rows; the web already reads them |

## 4. Verified facts (2026-10-03) — trust these

- **P1 is live on Neon**, from the runbook's "First run" section:
  - `bars`: 1,817,429 rows across 663 symbols, 2015-01-02 → 2026-10-02, 177 MB.
  - SPY covers 2,955 of 2,955 NYSE sessions with no gaps.
  - `fx_rates`: 3,009 rows. `universe`: 1,544 intervals.
  - 133 delisted symbols could not be fetched; they are logged `empty` in `backfill_log`.
  - One real `runs` row: data_date 2026-10-02, session_date 2026-10-05.
  - Demo data has been purged.
- **Engine APIs the simulator can use** (`engine/src/seer_engine/`):
  - `bars.Bar(symbol, date, open, high, low, close, volume)`: frozen dataclass with `Decimal` prices.
  - `bars.to_decimal`.
  - `dates.sessions(start, end)`, `next_session`, `prev_session`, `is_session` (NYSE).
  - `universe.members_on(conn, d)`.
  - Commands are discovered from `seer_engine/commands/*.py`, so a new command never edits `cli.py`.
- **Tests:** 216 engine tests and 20 web vitest tests pass, with 0 skipped. CI (`.github/workflows/engine-ci.yml`) is green on GitHub for `c81c1e8`. CI fails if any engine test is skipped.
- **Local test DB:** the Docker container `seer-pg`, at `postgresql://postgres:pg@localhost:55432/postgres` (`PG_TEST_URL`). The simulator core should need no database at all.
- **Split handling (P1):** the nightly job rescales stored history when a split executes (`split_adjustments`). Bars are therefore always consistent backwards, but an *open* order's limit/TP/SL/shares were set in pre-split prices. Design §8 says "open orders recomputed". P2 provides the pure function; P4 calls it.

## 5. Environment

- Local: WSL2 Ubuntu, **zsh** (use `${(P)name}`, not `${!name}`).
- Python 3.11.0 via pyenv, no `uv`. venv at `engine/.venv`; install with `engine/.venv/bin/pip install -e 'engine[dev]'`.
- Tests: `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`, after `docker start seer-pg`.
- `.env.local` at the repo root holds every key. Never `source` it, because `DATABASE_URL` has an unquoted `&`; the engine loads it with dotenv.
- Raw `psql` to Neon hangs from WSL (IPv6). Use the engine or Python instead. P2 shouldn't need Neon at all.
- The repo is public on purpose. Ask the owner before `git push` or `gh secret set`.

## 6. Acceptance criteria

1. Every design §5 rule and every §3 decision above has at least one test on synthetic bars, including:
   - touch vs penetrate, for the entry, TP and SL;
   - open < limit (fill at the open);
   - a gap through SL (`gap`) and a gap through TP (`tp`);
   - TP and SL both in range on the same bar (SL first);
   - no TP/SL check on the fill session;
   - the time stop at the open of day 6, including across a holiday and a half day;
   - expiry;
   - costs and `pnl_usd` to the cent;
   - whole-share sizing, the cash cap, and the ineligible pick (< 1 share);
   - no adding to an existing holding;
   - 0 picks;
   - slot reuse after an exit;
   - a missing bar for a held symbol;
   - a split while an order is open (forward and reverse).
2. Determinism: the same inputs give identical events and snapshots (no wall-clock reads, no unordered-set iteration leaking into output).
3. A multi-session scenario test (≥ 10 sessions, 4 slots, mixed outcomes) whose final cash, equity curve and closed-trade P/L are hand-checked in the test.
4. The core imports nothing from `psycopg`, `requests` or `yfinance` (enforced by a test).
5. The `engine/package_readme.md` section documents the API for P3 (backtest) and P4 (nightly).
6. The full engine suite is green with 0 skipped; CI stays green.

## 7. Open questions for the analysis to settle (recommend, don't ask open-ended)

- **API shape.** Recommended: a `Portfolio` value plus `step(portfolio, session_date, bars_by_symbol) -> (portfolio, events)` and `size_picks(portfolio, picks, data_date_closes) -> orders`, kept pure. P3 loops it over 10 years and P4 calls it once a night. Settle where it lives (`seer_engine/sim/`), and whether state is immutable or a mutable object with an event log.
- **Delisted or halted while held.** Recommended:
  - No bar for a held symbol → no event that session, but the day still counts.
  - The time-stop exit uses the next available open.
  - If no further bar ever arrives, close at the last known close, reason `time`, and mark the event so P3 can count it.
  - A pending order with no bar expires.
- **Reverse-split rounding on an open position.** Recommended: shares = floor(shares × factor), with the fractional remainder credited as cash at the adjusted price (how brokers pay cash in lieu). Document it.
- **Performance.** A 10-year backtest touches about 2,950 sessions, and the simulator only looks at bars for symbols with live orders, so `Decimal` should be fast enough. Confirm with a rough benchmark (e.g. 2,950 sessions × 4 slots in well under a few seconds) rather than switching to floats.

## 8. Not part of P2, but pending (owner)

- **GitHub secrets aren't set** (`gh secret list` is empty). `main` is pushed, so the nightly schedule will fire on Mon 2026-10-05 23:00 UTC and fail until `DATABASE_URL_UNPOOLED` and `MASSIVE_API_KEY` are set. The commands are in `docs/runbooks/data-pipeline.md` → "Owner steps".
- **GPS → GAP alias** is missing (Gap Inc. renamed), so `GPS` is logged `empty`. See the runbook's "Renames going forward".
- **P0** still lists "lint" as open; the repo has no lint script.
