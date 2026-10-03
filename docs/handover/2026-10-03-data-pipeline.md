# Handover — Seer data pipeline (roadmap P1)

Written 2026-10-03 at the end of the design + web session, for a fresh session to run
`/analyze` on. Read this whole file first; it lists decisions that are **already made** and
facts that were **verified**, so don't re-research or re-ask them.

## 1. What Seer is (one paragraph)

Seer is a personal web app. Every night it proposes up to 4 US stocks (slots S-E-E-R) to buy
in the next US session, each with a **Limit Buy, Take Profit, Stop Loss and whole-share
count** that the owner types into a Gotrade bracket order. Several strategies paper-trade
side by side on 20,000,000 IDR each. Real money only goes in when the champion passes a
fixed go-live checklist. The owner is new to trading; what matters is **measured profit
against buying and holding SPY**, not method elegance.

Read before planning:
- `docs/plans/2026-10-03-seer-design.md`: the validated design. §5 trade rules are law.
- `docs/ROADMAP.md`: P0–P6. **This handover covers P1 only.**
- `db/migrations/001_init.sql`: the live schema the pipeline writes into.
- `web/lib/data.ts`: how the web app reads those tables (the pipeline must produce what it reads).

## 2. Goal of this task (P1 — Data pipeline)

Build `engine/` (Python) and a GitHub Actions workflow that:

1. **Backfills** 10+ years of split-adjusted daily bars for the universe into Neon `bars`.
2. **Maintains point-in-time universe membership** (S&P 500 ∪ Nasdaq-100) in a new table.
3. **Runs nightly** (~06:00 WIB = 23:00 UTC, Mon–Fri): fetches the latest session's bars and
   the USD/IDR rate, and writes a `runs` row with correct `data_date` and `session_date`.
4. Is **idempotent**: re-running any step for the same date changes nothing.

**Done when:** the nightly job keeps `bars` + `fx_rates` current for the whole universe,
re-runs are no-ops, and `runs` rows have the right dates (see §6 acceptance).

**Out of scope for P1** (later phases, don't build): fill simulator (P2), strategies and
backtest (P3), placing picks/orders, LLM explanations (P4), any web UI change.

## 3. Decisions already made — do not reopen

| Topic | Decision |
|---|---|
| Language / location | Python in `engine/` at repo root; web stays in `web/` (Next.js). |
| Scheduler + compute | **GitHub Actions cron**, not Vercel (function time limits). Repo: `github.com/miftahulmahfuzh/seer` (currently **public**, empty; local `main` not pushed yet). |
| Universe | S&P 500 ∪ Nasdaq-100, **point-in-time** membership for backtests (avoid survivorship bias where possible). |
| Bars | Daily OHLCV, **split-adjusted** (dividend adjustment: decide and document; the simulator compares limit/TP/SL against these prices, so they must match what Gotrade showed at that time as closely as possible → split-adjusted only is the likely answer). |
| Nightly source | **Massive** (ex-Polygon) free tier, `grouped daily` endpoint: whole US market for one date in **one call**. |
| History source | **yfinance** one-off backfill (Massive free only reaches ~2 years back). Known caveat: no delisted tickers → survivorship bias in the backtest; forward paper trading is the real judge. |
| FX | **Frankfurter** (ECB rates, free, no key): `https://api.frankfurter.dev/v1/latest?base=USD&symbols=IDR` → write `fx_rates(date, usd_idr)`. |
| Calendar | `pandas_market_calendars` (NYSE) for holidays and half days. |
| Dates | `session_date` = the US session (ET calendar date) the next picks are for; `data_date` = last completed session whose bars were used. On a holiday the engine skips to the next real session. |
| Demo data | Neon currently holds **demo rows** (`runs.is_demo = true`) seeded by `web/scripts/seed-demo.mjs`. The pipeline's **first real run must delete all demo data** (orders, equity_snapshots, bars, fx_rates, runs, action_dismissals where demo) in one transaction, then write real rows. The seed script refuses to run once any non-demo run exists. |

## 4. Verified facts (2026-10-03) — trust these

- **Massive free tier:** grouped daily for 2026-10-01 returned 12,594 tickers in one call.
  Requests for 2016 data return `NOT_AUTHORIZED` ("plan doesn't include this data
  timeframe"); 2024 data works → ~2 years of history. Rate limit is 5 calls/min (check docs
  before relying on it). Base URL `https://api.massive.com`, key via `apiKey=` query param.
- **Finnhub:** quote and company-news both work (needed in P6, not P1).
- **LLM:** GLM-5.3 via `https://api.z.ai/api/anthropic` (Anthropic Messages API compatible,
  `x-api-key` header). It's a thinking model: give `max_tokens` ≥ 1000 or the text block is empty.
- **Frankfurter:** works, no key. USD/IDR on 2026-10-02 = 17,950. The demo seed used 16,530.
- **Neon:** `ap-southeast-1`. Connect over HTTPS/WebSocket (`@neondatabase/serverless` in
  Node; for Python use `psycopg` with `DATABASE_URL_UNPOOLED` and `sslmode=require`).
  ⚠️ Raw `psql` from this WSL machine **hangs** (IPv6 route issue). That's local, not a
  credential problem; GitHub Actions runners are unaffected. Locally, test via Python or the
  Node driver.
- **Date pitfall (already hit once):** JS Date parsing of Postgres `date` shifts by the
  machine's TZ (WIB, UTC+7). The web selects dates as `::text`. Keep dates as plain
  `YYYY-MM-DD` strings / `datetime.date` in Python; never round-trip through local midnight.
- **Vercel:** project `seer`, root dir `web`, functions pinned to **sin1** (verified via
  `x-vercel-id: sin1::sin1`). Web reads Neon only; it never computes.

## 5. Environment

- Local: WSL2 Ubuntu, **zsh** (use `${(P)name}`, not `${!name}`), Python 3.11.0 via pyenv
  (no `uv` installed), Node 20.11.1 (too old for Vitest 5 / TS 7; the web pins Vitest 3, TS 5).
- `.env.local` at repo root (git-ignored) already has: `LLM_API_KEY`, `LLM_BASE_URL`,
  `LLM_MODEL`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `DATABASE_URL`,
  `DATABASE_URL_UNPOOLED`, `MASSIVE_API_KEY`, `FINNHUB_API_KEY`, `AUTH_GOOGLE_ID`,
  `AUTH_GOOGLE_SECRET`, `AUTH_SECRET`, `ALLOWED_EMAIL`. Note `DATABASE_URL` contains an
  unquoted `&`: dotenv parsers are fine, `source .env.local` in a shell is not.
- GitHub Actions will need repo secrets: `DATABASE_URL_UNPOOLED`, `MASSIVE_API_KEY` (later:
  `LLM_*`, `FINNHUB_API_KEY`). Set with `gh secret set` (gh is authenticated as
  `miftahulmahfuzh`). Ask the owner before pushing or setting secrets.

## 6. Acceptance criteria

1. Migration `db/migrations/002_*.sql` adds the universe-membership table (symbol, index,
   start/end dates or equivalent) and any engine bookkeeping; applied via `web`'s
   `npm run db:migrate` (or an equivalent Python runner that respects `schema_migrations`).
2. `bars` holds ≥ 10 years of daily bars for every symbol that was ever in the universe
   during that window and can be fetched (log the ones that can't).
3. Nightly job, run twice for the same date, leaves identical table contents.
4. On a Friday run, `session_date` = next Monday (or Tuesday if Monday is a holiday);
   on a pre-holiday run it skips the holiday. Unit-tested with fixed dates.
5. A failed fetch writes `runs.status='failed'` with `error` and leaves no partial bars for
   that date. The web app then shows its stale-data screen (it already handles this).
6. First real run removes all `is_demo` data atomically.
7. Unit tests for date logic, adjustment, and idempotent upserts; a dry-run mode that
   writes nothing.

## 7. Open questions for the analysis to settle (owner is new to trading: recommend, don't ask open-ended)

- Source of historical index membership (e.g. a maintained GitHub dataset vs. Wikipedia
  change tables). Pick one, document its gaps.
- yfinance batch strategy and throttling for ~700–900 symbols over 10 years.
- Whether to store bars for the full Massive grouped-daily response or only universe
  symbols (storage on Neon free tier is 0.5 GB; estimate before choosing).
- SPY must always be in `bars` (benchmark), even though it isn't an index member.
