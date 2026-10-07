# Plan: Sean — track the owner's real Gotrade trades, follow a roster method, and feed real costs to the lab

**Slug:** sean-gotrade-tracker
**Date:** 2026-10-07 22:26 WIB
**Analysis:** `20261007-222658-S3AN_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/seer/sean-gotrade-tracker`
**Branch:** `feature/sean-gotrade-tracker` (base: `origin/main` @ `c2d2891`)
**Phases:** 7
**Status:** planned
**Coordinator:** —

---

## Why

Verbatim from the owner:

> we are gonna be implementing another big system.
> we already have : Seer, Sera .
> let's call this one Sean . let's put Sean button above Sera (in Seer UI).
> Sean will track all my trading activities in Gotrade, and maybe show the graph of profit and loss of it.
> we need to be able to connect Sean with one of the method in the Seer's Roster as well. right now i followed RAW recommendations.
> by connecting, i am hoping Sean can add reminders to buy stocks / sell my own stocks based on the selected Roster (RAW)
>
> the plan is, i will upload all my Buy/Sell Order Summary screenshots to Sean, and he will parse it using glm-4.6v
> these are the files:
> ./gotrade_order_summary_screenshots.zip
>
> > [!IMPORTANT]
> > learn how to parse screenshots from ~/run-insights
> > i hope we can incorporate these valuable, real gotrade trading data to how we explore the new methods and how we calculate the profits and loss in Sera method lab, because using this data, we can see how much the other costs included in every buy/sell were.

## Requirements

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | A new system called Sean, reached by a Sean button placed above the Sera button in the Seer UI | 2 |
| R2 | Sean tracks all of the owner's Gotrade trading activity and shows a profit-and-loss graph | 1, 3, 4 |
| R3 | Upload Buy/Sell Order Summary screenshots; Sean parses them with glm-4.6v, the run-insights way | 1, 2 |
| R4 | Connect Sean to one roster method (RAW today); Sean reminds the owner to buy / sell by it | 5 |
| R5 | Real Gotrade costs feed method exploration and the Sera lab's profit-and-loss | 6, 7 |

How each phase serves its ids: R1 — Phase 2's rail button above Sera, plus a phone-header button
(the screenshots live on the phone; the mobile tab bar has no Sean). R2 — Phase 1's ledger, Phase
3's Overview, Phase 4's nightly marks and series. R3 — Phase 1's reader and zip reader, Phase 2's
upload route and uploader. R4 — Phase 5. R5 — Phase 6's fee schedule and `cost_model` lever,
Phase 7's `calibrate`, `lab costs`, M0031 rule, real-fee presets, skills and design doc.

## Scope

**In scope:** a `/sean` section (owner-only, Sera's gate) with three tabs — Overview (P&L graph + numbers + holdings), Trades (upload screenshots or the zip, list, delete), Plan (link a roster method, reminders); a GLM-4.6V screenshot reader; a ledger shared by web (TS) and engine (Python) through one fixture; a nightly engine job that marks the owner's holdings to market and writes a daily P&L series; a Gotrade fee schedule fitted to the real receipts, usable by the lab through a new no-op-default `cost_model` lever; lab/skill changes so new methods are measured with real costs.

**Out of scope:** storing the screenshot images (only a SHA-256 for dedupe); Gotrade cash balance; push/email reminders; changing any pinned digest, any live paper strategy's rules, or `DESIGN_V0`/the bracket engine; re-gating existing lab methods; a README (memory: README only at release).

**Follow-ups (known, unowned on purpose — not phases of this set):**
- **Stock splits and dividends in Sean's P&L.** Yahoo closes are split-adjusted, receipts are not: after a split a pre-split holding reads as a loss of the split ratio until post-split shares are known. Cash dividends received are not in the P&L (receipts don't show them).
- **The paper SPY benchmark stays at the flat 0.1%** (`paper/benchmark.py`, `paper/replay.py`); only the lab benchmark pays the candidate's cost model (Phase 6). If a real-fee strategy is promoted to paper, its paper benchmark should pay Gotrade too.
- **`GITHUB_DISPATCH_TOKEN` is absent from the Vercel project**, so the site's dispatches (`dispatchSeanMarks`, like Sera's `dispatchRepick`) are skipped in production; the nightly run picks Sean up instead (Phase 4's nightly step). Adding the token is the owner's call.
- **Production Neon gets migration 015 from the engine's `migrate` step** in `nightly.yml` / `sean.yml` (or `npm run db:migrate`); until it runs, uploads answer "couldn't be saved". No phase runs a migration against production.
- `components/sera/PageHeader.tsx` signs out to `/signin?next=%2Fsera` and its as-of tip says "lab record"; Sean pages reuse it (cosmetic; Sera's component).
- After merge, run `lab costs` on the roster's lab methods (RAW = M0007-N20-RAW) and `lab stage` in the main checkout so seertrade.site/sera shows what real fees do (Phase 7 handoff; writes the shared `lab/lab.sqlite`).
- The Sera site does not yet mark which trials ran at real fees (M0031+); `web/package_readme.md` / `engine/package_readme.md` gain Sean, `sim/costs.py` and `cost_model` at completion (readme-updater).

## Invariants

1. **The tree builds and tests pass at the end of every phase**: `cd web && npx tsc --noEmit && npx vitest run && npx next build` for web phases; `cd engine && .venv/bin/ruff check . && .venv/bin/pytest` for engine phases (worktree needs its own venv: `python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'`). **Known red at the base commit `c2d2891`, not caused by this set:** `web/lib/sera/lab.test.ts > lab snapshot (web/data/lab.json) > publishes a verdict that agrees with the gate published beside it` (M0021-B70-RAW) fails on main as it stands (checked at reconciliation, main's own `node_modules`). A phase's gate is "no new failure"; no phase of this set owns `web/data/lab.json`.
2. **No pinned digest moves.** Every existing lab trial digest, registry pin and paper spec digest canonicalizes byte for byte as before (`LEVERS_SINCE_PINS`). Existing lab methods and roster rows keep `cost_rate=0.001` flat costs.
3. **Sean is owner-only**: every `/sean` page and `/api/sean/*` route passes the same check as Sera (`isAllowed(ALLOWED_EMAIL) && isSeraUser`); anyone else gets 404; the Seer rail shows the Sean button only to that account.
4. **Design:** Seer v2 tokens and existing components (`Section`, `Stat`, `PageHeader`, `LineChart`, `.icon-btn`, `.sheet`, `.num`, `.pos/.neg`); **every button icon-only (Lucide) with `aria-label` + identical `data-tip`**; plain words for a non-trader, no ids/digests/sha on the page; green/red only mean profit/loss, coral marks "you need to act".
5. **The vision call copies run-insights' measured transport exactly**: `POST {LLM_VISION_BASE_URL}/chat/completions`, `Bearer LLM_API_KEY`, `model: LLM_VISION_MODEL`, `thinking:{type:'disabled'}`, base64 `data:image/jpeg` URL, token floor that fails closed, injectable `fetch` for tests. Never the `/api/anthropic` base URL.
6. **One ledger, two languages.** The TS ledger (`web/lib/sean/ledger.ts`) and the Python ledger (`engine/src/seer_engine/sean/ledger.py`) both pass the same fixture `web/lib/sean/fixtures/ledger.json`; the math below is the contract.
7. Web modules that are unit-tested use relative imports (vitest has no `@/` alias); DB reads live in server-only modules that are not unit-tested: `web/lib/sean/data.ts` (Phase 2 only), `overviewData.ts` (Phase 3 only), `planData.ts` (Phase 5 only). Pure modules may `import type` from them.
8. **Which date an order counts on:** its New York trade date (`orderSession` in TS, `Order.trade_date` in Python) — in the ledger, the P&L series (engine and web fallback), plan membership (`sean_link.since`) and the reminder "done" check. Only `sean calibrate` reads receipts by their WIB date, because Gotrade's fee regimes start on the WIB day its app began charging them.

### Shared contract A — migration `db/migrations/015_sean.sql` (Phase 1 writes it, everyone reads it)

```sql
CREATE TABLE IF NOT EXISTS sean_orders (
  id                  bigserial PRIMARY KEY,
  image_sha256        text UNIQUE,                    -- hex SHA-256 of the uploaded bytes; NULL never written by the app today
  side                text NOT NULL CHECK (side IN ('buy', 'sell')),
  order_type          text NOT NULL,                  -- as printed: 'Market Buy', 'Limit Sell', ...
  status              text NOT NULL,                  -- as printed: 'Filled'
  symbol              text NOT NULL,
  executed_at         timestamptz NOT NULL,           -- receipt Date + Time, read as WIB (+07:00)
  price               numeric(18,6) NOT NULL,         -- 'Average price' or 'Execution price'
  shares              numeric(24,9) NOT NULL,
  amount_usd          numeric(14,2) NOT NULL,         -- 'Trade amount'
  trading_fee_usd     numeric(10,2) NOT NULL CHECK (trading_fee_usd >= 0),     -- magnitudes; the receipt's +/- sign is the side
  regulatory_fee_usd  numeric(10,2) NOT NULL CHECK (regulatory_fee_usd >= 0),
  ppn_usd             numeric(10,2) NOT NULL CHECK (ppn_usd >= 0),
  total_usd           numeric(14,2) NOT NULL,         -- buy: amount + fees; sell: amount - fees
  net_profit_usd      numeric(14,2),                  -- the sell receipt's 'Net Profit', NULL on buys
  fills               jsonb NOT NULL DEFAULT '[]',    -- [{shares, price}] partial-fill lines, [] when none printed
  raw                 jsonb,                          -- the model's JSON, kept for audit
  created_at          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (symbol, side, executed_at, shares)          -- same order from two different screenshots
);
CREATE INDEX IF NOT EXISTS sean_orders_executed_at ON sean_orders (executed_at);

-- One followed roster method at most (singleton row).
CREATE TABLE IF NOT EXISTS sean_link (
  id           smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  strategy_id  text NOT NULL REFERENCES strategies(id),
  since        date NOT NULL,                         -- orders whose New York trade date is on/after this belong to the plan
  budget_usd   numeric(14,2),                         -- owner's intended plan size; NULL = the plan's current value
  linked_at    timestamptz NOT NULL DEFAULT now()
);

-- A reminder the owner marked done by hand (uploaded orders clear reminders on their own).
CREATE TABLE IF NOT EXISTS sean_reminder_marks (
  strategy_id   text NOT NULL,
  session_date  date NOT NULL,                        -- the method's decision session
  symbol        text NOT NULL,
  action        text NOT NULL CHECK (action IN ('buy', 'sell')),
  marked_at     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (strategy_id, session_date, symbol, action)
);

-- Daily closes for every symbol the owner has held (written by the engine, Phase 4).
CREATE TABLE IF NOT EXISTS sean_marks (
  symbol  text NOT NULL,
  date    date NOT NULL,
  close   numeric(18,4) NOT NULL,
  PRIMARY KEY (symbol, date)
);

-- The owner's daily P&L series (written by the engine, Phase 4; read by the Overview, Phase 3).
CREATE TABLE IF NOT EXISTS sean_equity (
  date            date PRIMARY KEY,                   -- NYSE session
  value_usd       numeric(14,2) NOT NULL,             -- holdings marked at that session's close
  cost_usd        numeric(14,2) NOT NULL,             -- open cost basis (fees included)
  realized_usd    numeric(14,2) NOT NULL,             -- cumulative
  unrealized_usd  numeric(14,2) NOT NULL,             -- value - cost
  pnl_usd         numeric(14,2) NOT NULL,             -- realized + unrealized
  fees_usd        numeric(14,2) NOT NULL,             -- cumulative trading + regulatory + PPN
  computed_at     timestamptz NOT NULL DEFAULT now()
);
```

### Shared contract B — ledger math (TS and Python identical)

The single source is the fixture `web/lib/sean/fixtures/ledger.json` (Phase 1); `web/lib/sean/ledger.ts` (Phase 1) and `engine/src/seer_engine/sean/ledger.py` (Phase 4) both reproduce it to the cent.

- **Order:** orders replay sorted by `executed_at` (as an instant), then `id`.
- **Trade date:** an order counts at date `d` when the America/New_York calendar date of its `executed_at` is `<= d` (a 03:30 WIB fill is the previous US session).
- **Buy:** `shares += s`; `cost += total_usd` (amount + fees).
- **Sell (pro rata):** `sold = min(s, held)`. When `sold > 0`: `avg = cost / held`; `proceeds = total_usd` when `sold == s`, else `total_usd × sold / s` (multiply first, then divide); `realized += proceeds − sold × avg`; `cost −= sold × avg`; `shares −= sold`. The shares sold beyond what Sean knows of, **and their money**, are ignored: a sell of a stock Sean never saw bought adds nothing to realized — only its fees count — so selling a pre-Sean holding never books invented profit.
- **Closing:** shares `< 1e-9` after an order → `shares = cost = 0`; the symbol leaves the holdings.
- **Fees:** `fees += trading + regulatory + ppn` on every order, the clamped part included.
- **Value at `d`:** `value = Σ shares × close(symbol, last close ≤ d)`, else the price of the symbol's latest order replayed so far; `unrealized = value − Σ cost`; `pnl = realized + unrealized`.
- **Rounding:** money to cents half up (ties away from zero, Python `ROUND_HALF_UP`), each output figure on its own from unrounded values (so `pnl` may differ by a cent from `realized + unrealized`); shares to 9 decimals.
- The receipt's own `net_profit_usd` (Gotrade's convention: sell total − shares × average buy price, buy fees **not** in the basis) is stored and shown on the sell row; it is not the ledger's realized figure.

### Shared contract C — `POST /api/sean/orders` (Phase 2 writes it)

Request JSON `{ "image": "<base64 JPEG, no data: prefix>", "sha256": "<hex>" }` (≤ 1.5 MB decoded). Responses: `201 {order}` new; `200 {order, duplicate: true}` same image or same order already stored; `400 {error}` malformed or digest mismatch; `413 {error}` too large; `422 {error}` refused by the reader — not an order summary, not filled, or unreadable after Phase 1's one repair (`error` = Phase 1's plain-words `READ_MESSAGES` text); `502 {error}` reader not set up, unreachable, timed out or did not see the picture (`isReaderDown`); `500 {error}` the save failed; `404` (empty) for anyone but the owner. The read runs `readOrder(visionDeps(cfg), image)` inside Phase 1's 55 s budget. `export const maxDuration = 60` literal.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Sean core: schema, screenshot reader, ledger | R2, R3 | `db/migrations`, `web/lib/sean` | 20 | — | HARD | `.workflows/plan/sean-gotrade-tracker/phase-1.md` | — | — |
| 2 | Sean section, Sean buttons (rail + phone header), Trades upload | R1, R3 | `web/app/sean`, `web/components`, `web/app/api/sean`, `web/lib/sean` | 25 + Vercel env | 1 | HARD | `.workflows/plan/sean-gotrade-tracker/phase-2.md` | — | — |
| 3 | Overview: P&L graph and holdings | R2 | `web/app/sean`, `web/lib/sean/overviewData.ts` | 7 | 1, 2 | NORMAL | `.workflows/plan/sean-gotrade-tracker/phase-3.md` | — | — |
| 4 | Engine: marks and the daily P&L series | R2 | `engine/src/seer_engine/sean`, `.github/workflows` | 10 | 1 | NORMAL | `.workflows/plan/sean-gotrade-tracker/phase-4.md` | — | — |
| 5 | Plan: link a roster method, buy/sell reminders | R4 | `web/app/sean/plan`, `web/lib/sean`, `web/components` | 16 | 1, 2 | HARD | `.workflows/plan/sean-gotrade-tracker/phase-5.md` | — | — |
| 6 | Engine: Gotrade fee schedule as a cost-model lever | R5 | `engine/src/seer_engine/sim`, `backtest` | 14 | — | HARD | `.workflows/plan/sean-gotrade-tracker/phase-6.md` | — | — |
| 7 | Lab: calibrate from real orders, measure methods at real cost | R5 | `engine/src/seer_engine/lab`, `sean`, `sim/rules.py`, `.claude/skills`, `docs`, `web/lib/cadence.ts` | 16 | 4, 6 | NORMAL | `.workflows/plan/sean-gotrade-tracker/phase-7.md` | — | — |

Run order: 1 and 6 first (independent); then 2 and 4 (after 1); then 3 and 5 in parallel (after 2; they share no file); 7 after 4 and 6. Phase 1 serves R2 and R3 together because the ledger and the reader share one type and one migration. Phase 2 serves R1 and R3 because the buttons and the upload are the same section shell.

### Phase 1 — Sean core: schema, screenshot reader, ledger
**Satisfies:** R2, R3
**Owns:** `db/migrations/015_sean.sql` (contract A verbatim + header comment); `web/lib/sean/` pure modules: `types.ts` (`OrderSide`, `SeanFill`, `SeanOrder`, `RawFill`, `RawReceipt`), `money.ts` (receipt text → numbers, `roundHalfUp`/`cents`/`fixed`, "October 07, 2026"+"21:55 WIB" → ISO `…+07:00`), `extractJson.ts` (verbatim port), `prompt.ts` (the model transcribes printed strings; code converts), `vision.ts` (`visionConfigFromEnv`, `callVisionWithFetch`, `readOrderWithFetch`, `repairOrderWithFetch`, a text-aware token floor `ceil(text chars / 3) + 150 per image` that fails closed, `VisionTokenFloorError`, `VisionTransportError`), `order.ts` (`toOrder(raw)` → `{ok, order}` or `{ok:false, kind: 'not_order'|'not_filled'|'unreadable', issues}`; checks: total = amount ± fees within $0.01, amount ≈ price × shares within `$0.01 + shares × $0.005`, partial fills sum to shares; refuses every status but Filled), `readOrder.ts` (`readOrder(visionDeps(cfg), imageB64, budgetMs = 55_000)` → `ReadOrderOutcome`, never throws for a model problem; **one repair that re-sends the image** with the issues, budget-gated; `isReaderDown(code)` splits 502 from 422; `READ_MESSAGES` plain words), `ledger.ts` (contract B: `LedgerOrder`, `Close`, `Holding`, `PnlPoint`, `orderSession`, `buildLedger`, `pnlSeries`, `pnlAt`), `unzip.ts` (`readZip(bytes, {inflateRaw?, accept?})`, `ZipError`, stored + deflate, CRC-checked, skips folders/`__MACOSX`/`.DS_Store`), `fixtures/ledger.json` (shared with Phase 4's pytest), `fixtures/receipts.json` (4 real receipts), seven colocated test files (92 tests), live smoke script `web/scripts/sean-vision-smoke.mjs` (not CI; measured 30/30 on the owner's zip, no repair needed).
**Does not touch:** any page, route, component, Nav; engine; `web/package.json`.
**Exit criteria:** `tsc` clean; vitest green (all 4 fixture receipts convert; the ledger reproduces `fixtures/ledger.json` to the cent); `015_sean.sql` applies after 001–014 on a fresh schema and re-applies as a no-op (`engine/tests/test_migrate.py`); `next build` green; nothing outside `db/migrations/015_sean.sql`, `web/lib/sean/`, `web/scripts/sean-vision-smoke.mjs` changed.

### Phase 2 — Sean section, Sean buttons, Trades upload
**Satisfies:** R1, R3
**Owns:** `web/components/Nav.tsx` + `Nav.module.css` (Sean `icon-btn` with class `.sean` directly above Sera, Lucide `Wallet`, tip/aria "Sean, your real trades", both in a `.foot` wrapper that takes over `margin-top:auto`; `.sera` deleted); `web/components/AppHeader.tsx` + `.module.css` (now `async`; an owner-only, mobile-only `Wallet` icon button beside Sign out, class `.sean` — the phone's way into Sean; call sites unchanged); `web/app/(app)/layout.tsx` (`owner` = Sera's check, `showSean`); `web/lib/sean/gate.ts` (`requireSean`, `isSeanCaller`); `web/lib/sean/data.ts` (server-only, **owned by this phase alone**: `orders()`, `ledgerOrders()`/`LedgerRow` for Phases 3 and 5, `ownerSymbols()`, `orderById()`, `orderIdBySha()`, `saveOrder()`, `removeOrder()`); `web/lib/sean/dispatch.ts` (`dispatchSeanMarks()`: `{ref:'main'}`, best effort); `web/components/sean/SeanNav.tsx` + css (`planOpen` badge, top bar below 1024 px); `web/app/sean/{layout,not-found,sean.module.css,page (placeholder),plan/page (placeholder)}`; `web/app/api/sean/orders/route.ts` (contract C); `web/app/sean/trades/{page, Uploader, DeleteOrder, actions, view(+test), upload(+test), trades.module.css}`; Vercel env `LLM_API_KEY`/`LLM_VISION_BASE_URL`/`LLM_VISION_MODEL` if missing.
**Uploader rules:** the browser unzips with Phase 1's `readZip`, re-encodes only non-JPEGs or JPEGs over ~1 MB (long side ≤ 2400 px, **short side never under 560 px**), hashes, posts three at a time; failures for reader or network reasons (offline, 400, 502, 504, other 5xx) are kept and re-sent by a retry icon button.
**Does not touch:** `web/lib/sean/{types,money,prompt,extractJson,vision,order,readOrder,ledger,unzip}.ts`, `reminders.ts`, `overviewData.ts`, `planData.ts`; engine.
**Exit criteria:** `tsc`, vitest, `next build` green; owner sees Sean above Sera on desktop and the Sean header button on a phone, and the three tabs; images or the zip upload with per-file status three at a time; duplicates report as already saved; a reader/network failure can be retried; delete works; a non-owner gets 404 on `/sean/*` and the API; `vercel env ls` lists the three `LLM_*` names.

### Phase 3 — Overview: P&L graph and holdings
**Satisfies:** R2
**Owns:** `web/app/sean/page.tsx` (replaces Phase 2's placeholder), `web/app/sean/overview.ts` + `overview.test.ts` (pure view model over Phase 1's ledger), `web/app/sean/OverviewBody.tsx` + `OverviewBody.test.tsx`, `web/app/sean/overview.module.css`, `web/lib/sean/overviewData.ts` (new: `equity()`, `marks()`); reads orders through Phase 2's `ledgerOrders()`.
**Content:** stats row (total profit/loss, realized, unrealized, fees paid, fees as % of money traded); `LineChart` of daily `pnl_usd` from `sean_equity` (faint dashed cumulative fees, break-even line), plus a live point for today (New York date) when an order is newer than the last nightly session; when `sean_equity` is empty, the series is `pnlSeries` over the orders' New York trade dates at last order prices and the caption says prices come nightly; holdings table (shares, average cost with buying fees, last price — italic when it is the order price — value, P&L `.pos/.neg`); empty state with an icon button to Trades.
**Does not touch:** `data.ts`, Trades, Plan, `Nav`, `AppHeader`, engine. Shares no file with Phase 5.
**Exit criteria:** `tsc`, vitest (`overview.test.ts`, `OverviewBody.test.tsx`: zero, one, many orders; nightly series with and without a live point) and `next build` green; `/sean` no longer shows the placeholder.

### Phase 4 — Engine: marks and the daily P&L series
**Satisfies:** R2
**Owns:** `engine/src/seer_engine/sean/{__init__,ledger,marks,equity}.py`, `engine/src/seer_engine/commands/sean.py` (subcommand `marks`; `_HANDLERS = {"marks": _marks}` of `(conn, args) -> int`), tests `test_sean_{ledger,marks,command}.py` (ledger against Phase 1's `fixtures/ledger.json`, pro-rata oversell), `.github/workflows/sean.yml` (`workflow_dispatch`, optional `dry_run` input, no required input, group `sean-writer`, runs migrate + `sean marks`), one `Sean marks` step at the end of `nightly.yml` (`continue-on-error: true`).
**Does not touch:** `sim/`, `lab/`, `paper/`, web, migrations.
**Exit criteria:** ruff + full pytest green with nothing skipped; `python -m seer_engine sean marks` against an empty `sean_orders` exits 0 with no network call; both workflow files parse.

### Phase 5 — Plan: link a roster method, buy/sell reminders
**Satisfies:** R4
**Owns:** `web/lib/sean/reminders.ts` + test (pure: plan orders = New York trade date on/after `since`; sells for plan holdings no longer picked, buys sized `weight × planSize`, add/trim only for resizing rule sets — incl. the two `-gotrade` presets — when the gap ≥ max($10, 1% of the plan); done = a matching order whose New York trade date is on/after the decision session, or a mark); `web/lib/sean/planData.ts` (new: `linkableMethods`, `link`, `latestTargets`, `reminderMarks`, `latestCloses`, `planState`, React-`cache`d `openReminderCount`); `web/app/sean/plan/{page, view(+test), actions (via isSeanCaller), LinkPicker, PlanSettings, plan.module.css}` (replaces the placeholder); `planOpen` into `SeanNav` (`app/sean/layout.tsx`); the coral dot + "· N to do" words on both Sean buttons — `Nav.tsx` (`seanOpen` prop, fed by `(app)/layout.tsx`) and `AppHeader.tsx` (reads the cached count itself).
**Rules:** only active, non-benchmark `engine='book'` roster rows are linkable; `since` defaults to the method's latest decision session; pre-plan holdings never get a sell reminder; plain sentences, no ids.
**Does not touch:** `data.ts`, Overview files, `overviewData.ts`, Trades upload, `cadence.ts`, engine.
**Exit criteria:** reminder and view tests green (fresh link, the real Oct 7 follow-through, month turnover, partial follow-through, an after-midnight-WIB order, resize band, pre-plan holdings untouched, marked done); `tsc`, full vitest, `next build` green.

### Phase 6 — Engine: Gotrade fee schedule as a cost-model lever
**Satisfies:** R5
**Owns:** `engine/src/seer_engine/sim/costs.py` (`GOTRADE` schedule of four dated `FeeRegime`s fitted to the receipts — current regime since 2026-06-16: trading 0.2% half-up, min $0.10; regulatory 0.054% rounded up, cap $0.11, sells +0.04% up; PPN 11% of the printed fees, half-down; `fee_parts(side, amount, on=None)`, `GOTRADE.current`, `gotrade_cash`, `gotrade_shares_for`); `TradeRules.cost_model: Literal['flat','gotrade'] = 'flat'` in `LEVERS_SINCE_PINS`, validated (`gotrade` needs the default `cost_rate`; never for `DESIGN_V0`); `rule_owner_inputs` does not flag it; `describe_rules` line; `sim/book.py` money functions dispatch on the model (every simulated fill at the current regime); lab SPY benchmark and `dev._run` pay the candidate's model; `engine/tests/fixtures/gotrade_fees.json` (fee-only rows); tests incl. `test_sim_costs.py` and `test_cost_model_pins.py` (every committed lab digest recomputes byte for byte). **Adds no preset.**
**Does not touch:** `DESIGN_V0`/bracket engine (`sim/model.py`, `sizing.py`, `lifecycle.py`), `paper/` (paper benchmark stays flat), web.
**Exit criteria:** ruff + full pytest green incl. `test_registry`, `test_lab_methods`, `test_paper_roster`, `test_cost_model_pins`; every current-regime receipt reproduced to the cent; a gotrade book run on $28 slots pays more than flat.

### Phase 7 — Lab: calibrate from real orders, measure methods at real cost
**Satisfies:** R5
**Owns:** `engine/src/seer_engine/sean/calibrate.py` + `commands/sean.py` subcommand `calibrate` (replays `fee_parts` on each receipt's **WIB** date; exit 1 when an order since `GOTRADE.current.since` is off by more than a cent); `engine/src/seer_engine/lab/real_costs.py` + `lab costs MNNNN` (report only: no trial, N unchanged, one journal observation); `runner.preflight` refuses a flat-cost variant from M0031; the two real-fee presets `MONTHLY_HOLD_FRAC_GOTRADE` / `MONTHLY_RANK_WEEKLY_RESIZE_FRAC_GOTRADE` appended to `PRESETS` (rules.py after Phase 6) with their pins in `test_sim_rules.py` and Phase 6's `test_cost_model_pins.py`; `web/lib/cadence.ts` `SPLIT_CADENCE_RULES` + test learn `monthly-rank-weekly-resize-frac-gotrade`; tests `test_sean_calibrate.py`, `test_lab_costs.py`; both lab skills + `method_template.py`; design doc costs line + §15.
**Does not touch:** `sim/costs.py` numbers, `sim/book.py`, `backtest/*` (Phase 6); Phase 4's `marks` code; other web files; existing trial rows; `lab/lab.sqlite`.
**Exit criteria:** ruff + full pytest green (DB tests with `PG_TEST_URL`); `web/lib/cadence.test.ts` green; `sean calibrate` exits 0 on the fee fixture and 1 on a drifted receipt; `lab costs` writes exactly one insight and leaves trials, moments, methods, N and looks unchanged; `lab run` refuses a flat-cost M0031 and accepts one on `MONTHLY_HOLD_FRAC_GOTRADE`; `lab costs M0007` runs locally (`SEER_LAB_COSTS_LIVE=1`, skipped in CI).

## Reconciliation Log

| # | Conflict | Class | Resolution |
|---|---|---|---|
| 1 | Phase 4's Python ledger booked a clamped sell's whole `total_usd` as proceeds (`avg = 0` with nothing held); Phase 1's TS ledger and the shared fixture prorate and ignore unknown shares | Contract drift (invariant 6) | Phase 4's `_Book.apply`, docstring and two unit tests rewritten to Phase 1's pro-rata rule; reconciled `ledger.py` + `test_sean_ledger.py` re-run against Phase 1's fixture: 13/13 green. Contract B above is the final text. |
| 2 | Phases 2, 3, 5 wrote "Interface assumptions" against a Phase 1 that did not exist (`readOrder(image, {config, timeoutMs})` that throws, `readZipEntries`, `buildLedger(SeanOrder[]).positions` as a Map/`{cost}`, `Closes` as a map, `PnlPoint.pnl/fees`, `orders(): SeanOrder[]`) | Unmet assumption | Code rebound to Phase 1's real exports: route uses `readOrder(visionDeps(cfg), image)` + `isReaderDown` (502/422) with `out.message`; uploader uses `readZip(bytes, {accept})` and surfaces `ZipError` text; Overview and reminders use `LedgerOrder`, `Close[]`, `PnlPoint.*Usd`, `buildLedger().holdings`. Phases 1–3 and 5 extracted from the plans into a scratch copy of `web/` (main's `node_modules`): `tsc --noEmit` clean, 185/185 Sean tests green. |
| 3 | Phase 2's route had its own `isFilledStatus` check and `READ_BUDGET_MS = 52_000` | Duplicate work | Removed: Phase 1's `toOrder` refuses non-Filled and `readOrder` owns the 55 s budget. `isFilledStatus`, its test and the unused `SAY.notFilled/notReceived` deleted. |
| 4 | Phases 3 and 5 (parallel, both after 2) both appended to Phase 2's `web/lib/sean/data.ts` | File collision | Phase 3 → new `web/lib/sean/overviewData.ts`; Phase 5 → new `web/lib/sean/planData.ts`; neither edits `data.ts`. Both needed orders in the ledger's shape, which Phase 2's `orders()` (Jakarta wall-clock string, no `id`-ordered ISO) does not give, so Phase 2's `data.ts` gains `ledgerOrders()`/`LedgerRow`, read by both. Phases 3 and 5 now share no file. |
| 5 | Phase 3 (Jakarta `wibDate` for order days and "today") and Phase 5 (`wibDate` for plan membership and the done check) disagreed with the ledger's New York trade date | Contract drift | Both switched to `orderSession`; Phase 3's page passes today's New York date; Phase 5's `wibDate` deleted; tests updated (after-midnight-WIB cases added). `sean_link.since` comment in contract A / Phase 1 Step 1 reworded to "New York trade date" (comment only). |
| 6 | No mobile way into Sean, though the screenshots live on the phone (Phase 2 left it "not in any phase") | Gap (R1/R3) | Phase 2 Step 3b: owner-only, mobile-only `Wallet` icon button in `AppHeader` beside Sign out (`AppHeader` made `async`, call sites unchanged). Phase 5 puts the same coral dot on it. |
| 7 | Phase 5's dot assumed a `s.sean`/`s.seanBadged` class Phase 2 never defined; Phase 5's `(app)/layout.tsx` edit quoted a `showSean` variable Phase 2 does not have | File collision (post-change code) | Phase 2 gives both Sean links class `.sean { position: relative }`; Phase 5 quotes Phase 2's real code (`owner`), adds only `.seanDot`, and reads the count in `AppHeader` too, through a React-`cache`d `openReminderCount` so one request runs `planState` once. |
| 8 | Phase 5's `actions.ts` re-implemented the gate Phase 2 exports as `isSeanCaller` | Duplicate work | Phase 5 imports `isSeanCaller` from `lib/sean/gate.ts`. |
| 9 | Phase 7 bound to `GOTRADE.regimes[-1].since` and kept "drop Steps 6–7 if Phase 6 adds presets" | Unmet assumption | Bound to Phase 6's `GOTRADE.current.since`, `fee_parts(side, amount, on)`, `FeeParts`; Phase 6 adds no preset, so Phase 7 adds both; the conditional was removed. Phase 7's pure calibrate tests run green against Phase 6's `costs.py` and fixture (11/11). |
| 10 | Phase 7's two `-gotrade` presets would turn Phase 6's `test_flat_is_absent_from_every_canonical_form` red (it asserts no preset carries `cost_model`) | Broken-build phase | Phase 7 Step 7c narrows that loop to flat presets and pins the two real-fee ids; Phase 7's `test_sim_rules.py` edits quote the file after Phase 6 (located by function name). |
| 11 | The new `monthly-rank-weekly-resize-frac-gotrade` preset was unknown to the web's hand mirrors (`cadence.ts` `SPLIT_CADENCE_RULES`, Phase 5's `RESIZING_RULES`) | Gap | Phase 5's `RESIZING_RULES` lists both `-gotrade` ids; Phase 7 Step 7d adds the split-cadence id to `cadence.ts` + test (R5, no other phase edits that file). |
| 12 | Phase 5's test "a pick held only from before the plan gets a buy" passed the plan's own LLY buy in `orders`, so the reminder was already done (found by running the test) | Contract drift (test vs. code) | Test now passes `octBuys` without LLY, matching its `held`. |
| 13 | Phase 2's uploader downscale had no short-edge floor (Phase 1 handoff: ≥ 560 px) | Unmet assumption | `fitWithin` never takes the short side under `MIN_SHORT_PX = 560` and never scales up; two test cases added. |
| 14 | Index text for Phase 1 said the repair is text-only and kept run-insights' flat token floor and 0.1% amount tolerance | Contract drift | Index rewritten to Phase 1's measured design: the repair re-sends the image; text-aware floor; `$0.01 + shares × $0.005` tolerance. |
| 15 | Phase 4 dispatch shape vs Phase 2's `dispatchSeanMarks` | (checked) | Consistent: `sean.yml` has only an optional `dry_run` input; `{"ref":"main"}` dispatches it. |
| 16 | Phase 3's reads vs migration 015 columns | (checked) | `sean_equity (date, value_usd, cost_usd, realized_usd, unrealized_usd, pnl_usd, fees_usd)` and `sean_marks (symbol, date, close)` read exactly. |
| 17 | Phase 7's `commands/sean.py` edits vs Phase 4's file | (checked) | Matches: `sub` subparsers with `dest="sean_command"`, `_HANDLERS` of `(conn, args) -> int`, `run` owns the connection, module `log`. |

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| Who may see Sean | owner only, Sera's exact gate | 6: convention (Sera gate) + R2 "my trading" |
| Keep screenshots? | no — parsed row + SHA-256 only; no `@vercel/blob` | 6: convention (web has no Blob dep) |
| Upload the zip as-is? | yes — browser unzips (Phase 1 `readZip`), plus plain multi-image select | 5: raw input names the zip |
| Pre-RAW holdings vs RAW sells | plan = orders on/after `sean_link.since`; older holdings never get sell reminders | 5: raw input "remind … based on the selected Roster" |
| Real costs in existing digests | new `cost_model` lever, no-op default in `LEVERS_SINCE_PINS`; old methods/paper unchanged | 1: invariant 2 |
| Re-measuring old methods at real cost | report-only `lab costs`, no trial rows (N unchanged) | 1: invariant 2 + lab honesty rules |
| Vercel env for the vision keys | Phase 2 copies them from `web/.env.local` if missing | 3: phase exit criteria need the route to work in prod |
| **Oversell** (a sell of more shares than Sean saw bought) | Phase 1's pro rata: only the known shares and their share of the receipt total count; a sell of a never-seen holding adds only its fees. Phase 4 mirrors it; `fixtures/ledger.json` (Phase 1) is the single source | 1: invariant 6 (one ledger) + 5: the owner wants true P&L, not invented profit |
| **Which date an order counts on** | the New York trade date (`orderSession` / `trade_date`) for the ledger, the P&L series (engine and web fallback), Phase 3's days and "today", plan membership (`since`) and Phase 5's done check; `sean calibrate` alone keeps WIB receipt dates for fee-regime lookup (documented in `calibrate.py`) | 1: invariants 6 and 8 |
| Phase 3/5 collision on `data.ts` | separate `overviewData.ts` / `planData.ts`; `data.ts` is Phase 2's alone and serves both through `ledgerOrders()` | 1: invariant 1 (build green per phase) — parallel phases cannot edit one file |
| **Mobile reach to Sean** | owner-only, mobile-only icon button in `AppHeader` next to Sign out (not a fifth tab in the shared 4-column pill); Phase 5's coral dot on it too | 5: raw input "i will upload all my … screenshots" (they are on the phone) |
| Repair call content | re-sends the image with the issues (not text-only) | 3: Phase 1 code, measured live 30/30 |
| Words for a refused read | the route returns Phase 1's `READ_MESSAGES` text (`out.message`); Phase 2's `SAY` only for its own refusals and as the uploader's fallback | 3: Phase 1 code (its tests pin the messages) |
| Who adds the `-gotrade` presets | Phase 7, after Phase 6; Phase 7 quotes `sim/rules.py` and `test_sim_rules.py` as Phase 6 leaves them | 3: Phase 6 code (adds none) and Phase 7 code |
| Retrying a failed upload | every reader/network failure (offline, 400, 502, 504, 5xx) is kept and re-sent by the retry icon button, as often as pressed; a 422 refusal is not offered again | 3: Phase 1 measured a transient transport failure |
| Downscaling a picture | only above 2400 px on the long side, and never under 560 px on the short side | 3: Phase 1 handoff (run-insights 108/108 at 560 px) |
| `current regime` name for calibrate | `GOTRADE.current.since` | 3: Phase 6 code defines `current` |

## Open Questions

(none)

## Rollback

Per phase, revert its commit, later phases first where they build on it (3 and 5 before 2; 2 and 4 before 1; 7 before 4 and 6).
- **Phase 1:** deletes 20 new files; nothing else imports them once 2–5 are reverted. If 015 was applied anywhere: `DROP TABLE sean_equity, sean_marks, sean_reminder_marks, sean_link, sean_orders; DELETE FROM schema_migrations WHERE name = '015_sean.sql';` (no other table references them).
- **Phase 2:** restores `Nav.tsx`/`.module.css`, `AppHeader.tsx`/`.module.css`, `(app)/layout.tsx`; deletes the section, route and `data.ts`. The Vercel `LLM_*` variables are harmless to leave (`vercel env rm` removes them).
- **Phase 3:** restores the Overview placeholder; deletes `overview*`, `OverviewBody*`, `overviewData.ts`.
- **Phase 4:** deletes the engine `sean` package/command/tests and `sean.yml`, drops the nightly step; `TRUNCATE sean_marks, sean_equity` if wanted.
- **Phase 5:** deletes `reminders*`, `planData.ts`, `plan/*` (placeholder restored); `Nav`, `AppHeader`, both layouts lose the count plumbing; `DELETE FROM sean_link; DELETE FROM sean_reminder_marks;` if wanted.
- **Phase 6:** the lever's default is a true no-op, so every digest stays where it was; revert Phase 7 first (it imports `sim.costs`).
- **Phase 7:** no persistent state; `lab costs` insights already staged stay in `lab/lab.sqlite` (append-only, harmless). The presets may stay if a method file already uses them.
- **Whole set:** revert the merge.

## Next

    /implement -f SEAN_GOTRADE_TRACKER_PLAN.md --phase 1

    /analyze-orchestrator -f SEAN_GOTRADE_TRACKER_PLAN.md
