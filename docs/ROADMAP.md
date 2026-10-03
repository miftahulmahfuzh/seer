# Seer Roadmap — v0.1.0 major plans

Design: [docs/plans/2026-10-03-seer-design.md](plans/2026-10-03-seer-design.md)

v0.1.0 goal: **Strategy A forward paper trading live every night, visible on the phone.**
Real money is out of scope until the go-live checklist is fully green.

## P0 — Foundations · mostly done 2026-10-03 (CI still open)
- Repo layout: `web/` (Next.js), `engine/` (Python), `.github/workflows/`
- `.gitignore`, `.env.example`; rotate any secrets that were ever exposed
- Neon schema + migrations (tables from design §7)
- Accounts: Massive, Google OAuth, Finnhub, LLM, Vercel, Neon: all verified 2026-10-03
- **Done when:** schema migrated on Neon, CI runs lint + tests on push

## P1 — Data pipeline · done 2026-10-03 locally on Neon (backfill + nightly, [runbook](runbooks/data-pipeline.md)); pushed, Actions schedule awaits repo secrets
- Point-in-time S&P 500 ∪ Nasdaq-100 membership
- Backfill 10+ years of split-adjusted daily bars via yfinance (Massive free tier only reaches ~2 years back); nightly incremental fetch via Massive grouped-daily
- Market calendar (holidays, half days)
- **Done when:** nightly job keeps `bars` current for the whole universe, idempotent re-runs

## P2 — Fill simulator (critical path) · done 2026-10-03 on synthetic bars (`engine/src/seer_engine/sim/`, API in [engine/package_readme.md](../engine/package_readme.md)); P3/P4 wire it in
- Order lifecycle exactly as design §5 (strict fill, SL-first, gaps, time stop, costs)
- Whole-share sizing, 4 slots, equity ÷ 4
- Exhaustive unit tests on synthetic bars
- **Done when:** every edge case in design §5 has a passing test

## P3 — Strategy A + backtest · done 2026-10-03: **Gate failed — rework before P4; P4 must not start** ([report](backtests/2026-10-02-strategy-a.md))
- Implement Strategy A on the shared simulator
- 10-year backtest vs SPY; tune parameters on early years, validate on later years
  (no tuning on the validation window), then freeze parameters
- Backtest report: equity curve, return, win rate, profit factor, max drawdown
- **Gate:** if A cannot beat SPY in backtest, rework before P4. Don't paper-trade a loser.
- **Verdict (2026-10-02 data, out-of-sample 2022-01-03 → 2026-10-02):** Strategy A fails the P3 gate: out of sample it returned −15.0% against +71.9% for total-return SPY, with profit factor 0.92 and max drawdown 33.3%, so it fails on beating total-return SPY, profit factor ≥ 1.3 and max drawdown ≤ 15%; P4 must not start until Strategy A is reworked.

## P3b — Strategy A rework under walk-forward · done 2026-10-03: **Gate failed — Strategy A's one rework failed; P4 stays blocked** ([report](backtests/2026-10-02-strategy-a2-walkforward.md))
- Spec: [handover](handover/2026-10-03-strategy-a-rework.md). The 2022-01-03 → 2026-10-02 window was burned by P3, so validation is an anchored yearly walk-forward: tune on 2015-10-19 → the end of Y−1, trade Y, 2018 → 2026-10-02, as one continuous portfolio
- Tried, all pre-registered: V0 `control` (v1), V1 `regime` (no new picks when SPY ≤ its SMA(200)), V2 `regime_calm` (rank by ATR/close), V3 `regime_calm_floor` (close ≥ $10) × P3's 81-run grid = 324 combinations per fold, selected by P3's rule; every variant's own walk-forward is in the report too
- **Gate:** the walk-forward curve must beat total-return SPY over the same span with PF ≥ 1.3 and max DD ≤ 15%
- **Verdict (2026-10-02 data, walk-forward 2018-01-02 → 2026-10-02):** Strategy A2 fails the P3b gate: walk-forward from 2018-01-02 to 2026-10-02 it returned +9.1% against +187.6% for total-return SPY, with profit factor 1.02 and max drawdown 29.1%, so it fails on beating total-return SPY, profit factor ≥ 1.3 and max drawdown ≤ 15%; Strategy A's one rework has failed, and P4 stays blocked.
- Strategy A's one rework failed. Strategy A is not reworked again on this data, `STRATEGY_A2_PARAMS` stays `None`, and P4 stays blocked. The owner decides next (handover §8):
  - (a) go to P6's Strategy B (ML ranker), validated with the same walk-forward machinery;
  - (b) accept SPY buy-and-hold as the honest champion for now: paper-trade research strategies, and recommend no real-money picks;
  - (c) revisit a design-§5 trade rule (for example the 5-day time stop or the 4 slots). That is a design change, and it needs the owner's explicit decision and a new handover; it is never done inside a rework.

## P4 — Nightly forward paper trading
- GitHub Actions cron ~06:00 WIB: fetch → settle → pick → snapshot → run log
- LLM explanation per pick (GLM via z.ai); failure-tolerant
- Stale-data and failed-run handling
- **Done when:** 5 consecutive trading days run unattended with correct settlement

## P5 — Web app · done 2026-10-03 on demo data (seed: `npm run db:seed-demo`); awaiting seertrade.site DNS
- Implement the Claude Design output: Sign-in, Today, Positions, Leaderboard, History
- Auth.js, Google only, single `ALLOWED_EMAIL`
- PWA manifest + apple-touch-icon; Lucide icon-only buttons
- Deploy to Vercel, connect seertrade.site
- **Done when:** usable from the XS Max home screen; picks copyable into Gotrade

## P6 — Challengers
- Strategy B (ML ranker), walk-forward backtest, then forward paper
- Strategy C (Finnhub news + LLM veto on A's candidates), forward paper only
- Leaderboard + champion selection + go-live checklist
- **Done when:** A, B, C each have independent paper portfolios on the leaderboard

## v0.1.0 release
P0–P5 done (P6 may trail into v0.2.0). The 3-month forward clock starts on the first
live paper day.

## Later (v0.2+)
- Real-trade journal: log actual Gotrade fills against Seer picks, real vs paper slippage
- Notifications (e.g. Telegram) for picks and day-5 exits
- Parameter/strategy versioning so changes reset the forward clock honestly
