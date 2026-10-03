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

## P1 — Data pipeline
- Point-in-time S&P 500 ∪ Nasdaq-100 membership
- Backfill 10+ years of split-adjusted daily bars via yfinance (Massive free tier only reaches ~2 years back); nightly incremental fetch via Massive grouped-daily
- Market calendar (holidays, half days)
- **Done when:** nightly job keeps `bars` current for the whole universe, idempotent re-runs

## P2 — Fill simulator (critical path)
- Order lifecycle exactly as design §5 (strict fill, SL-first, gaps, time stop, costs)
- Whole-share sizing, 4 slots, equity ÷ 4
- Exhaustive unit tests on synthetic bars
- **Done when:** every edge case in design §5 has a passing test

## P3 — Strategy A + backtest
- Implement Strategy A on the shared simulator
- 10-year backtest vs SPY; tune parameters on early years, validate on later years
  (no tuning on the validation window), then freeze parameters
- Backtest report: equity curve, return, win rate, profit factor, max drawdown
- **Gate:** if A cannot beat SPY in backtest, rework before P4. Don't paper-trade a loser.

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
