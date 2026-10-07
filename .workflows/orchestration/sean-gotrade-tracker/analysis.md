# Code Analysis: Sean — the Gotrade trade tracker

**Type:** Feature Implementation
**Date:** 2026-10-07 22:26 WIB
**Session ID:** 20261007-222658-S3AN
**Plan:** `SEAN_GOTRADE_TRACKER_PLAN.md` (7 phases)
**Worktree:** `/home/miftah/.worktrees/seer/sean-gotrade-tracker` on `feature/sean-gotrade-tracker` (base `origin/main` @ c2d2891)

---

## User Input

### Original User Request

```
we are gonna be implementing another big system.
we already have : Seer, Sera .
let's call this one Sean . let's put Sean button above Sera (in Seer UI).
Sean will track all my trading activities in Gotrade, and maybe show the graph of profit and loss of it.
we need to be able to connect Sean with one of the method in the Seer's Roster as well. right now i followed RAW recommendations.
by connecting, i am hoping Sean can add reminders to buy stocks / sell my own stocks based on the selected Roster (RAW)

the plan is, i will upload all my Buy/Sell Order Summary screenshots to Sean, and he will parse it using glm-4.6v
these are the files:
./gotrade_order_summary_screenshots.zip


> [!IMPORTANT]
> learn how to parse screenshots from ~/run-insights
> i hope we can incorporate these valuable, real gotrade trading data to how we explore the new methods and how we calculate the profits and loss in Sera method lab, because using this data, we can see how much the other costs included in every buy/sell were.
```

### User-Provided Context

- The screenshots: `/home/miftah/seer/gotrade_order_summary_screenshots.zip` (untracked in the main checkout, NOT in the worktree; 30 JPEGs, ~60 KB each, 739×1600 phone screenshots of Gotrade's "Order Summary" sheet).
- A full, checked transcription of all 30 is at
  `.workflows/plan/sean-gotrade-tracker/screenshots_truth.json` (ground truth: 29 buys, 1 sell; every `total` reconciles to amount ± fees).
- The reference implementation for GLM vision parsing: `~/run-insights` (`lib/llm/vision.ts`, `lib/llm/extractJson.ts`, `lib/llm/prompts/extraction.ts`, `lib/schema/extractedSession.ts`).

### User-Provided Files
- `./gotrade_order_summary_screenshots.zip`

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | A new system called **Sean**, reached by a Sean button placed **above the Sera button** in the Seer UI |
| R2 | Sean **tracks all of the owner's Gotrade trading activity** and shows a **profit-and-loss graph** of it |
| R3 | The owner **uploads Buy/Sell Order Summary screenshots** to Sean, which **parses them with glm-4.6v**, the way `~/run-insights` parses screenshots |
| R4 | Sean can be **connected to one method on Seer's Roster** (RAW today) and then **reminds the owner to buy / sell** stocks according to that method |
| R5 | The real Gotrade orders feed back into **how new methods are explored and how the Sera method lab computes profit and loss**, because they show the true costs of every buy/sell |

---

## Detailed Requirements Understanding

**Problem/Requirement Statement.** Seer today only knows simulated money: every fill in Neon is
written by the Python engine's simulator, and every cost is one assumed number — 0.1% of
notional per side (`engine/src/seer_engine/sim/rules.py:50`, design doc `docs/plans/2026-10-03-seer-design.md:29`
"Unverified, **assumed**"). The owner actually trades on Gotrade, following RAW's targets, and
has 30 order receipts that prove the real costs are 3–5× the assumption at the sizes the owner
trades. Sean is a third section next to Seer and Sera that (a) ingests those receipts by
screenshot through the GLM-4.6V vision model, (b) keeps a ledger of the owner's real orders,
positions and realized/unrealized P&L with a graph, (c) follows one roster method and turns its
monthly target portfolio into concrete buy/sell reminders against the owner's real holdings,
and (d) turns the observed fee schedule into a calibrated cost model the method lab can use.

**Success Criteria.**
1. The Seer desktop rail shows a Sean icon button directly above the Sera button, for the owner account only; it opens `/sean`.
2. Selecting the 30 screenshots (or the zip) on `/sean/trades` produces 30 order rows whose fields match `screenshots_truth.json`; uploading the same image twice adds nothing.
3. `/sean` shows a P&L line over time (from the first order to today), plus realized P&L, unrealized P&L, total fees paid and fees as % of traded value.
4. `/sean/plan` lets the owner pick one active book method from the roster (RAW-FR today) and lists reminders: buy X for about $Y, sell Z, with the method's decision date — reminders clear when a matching order is uploaded or the owner marks them done.
5. The engine has a Gotrade fee schedule fitted to the real receipts, a test proves it reproduces the observed fees, `TradeRules` can price trades with it without moving any pinned digest, and new lab methods are measured with it.

**Key Considerations.**
- **Fee facts observed (ground truth file):**
  - Trading fee: $0 in June 2025; 0.3% of amount 2025-06-26 → 2026-03-25; **0.2% since 2026-06-16**; **minimum $0.10** (every $27.90 order pays $0.10).
  - Regulatory fee: not proportional on buys — $0.02 @ $27.90, $0.06 @ $105, $0.08 @ $147, $0.10–0.11 for $366–$1,833 (capped ≈ $0.11). The single sell paid $0.07 on $72.51.
  - **PPN = 11% of (trading fee + regulatory fee)**, rounded to the cent (29/30 exact).
  - Buys: `total = amount + fees`; sells: `total = amount − fees`.
  - Gotrade's "Net Profit" on a sell = sell total − shares × average buy price (buy fees **not** in the basis).
  - Layout variants: "Average price" + partial-fill lines (orders split into fractional + whole parts) vs "Execution price"; dates "October 07, 2026"; times "21:55 WIB"; shares up to 9 decimals; prices with thousands separators and up to 3 decimals.
- **The vision call** must copy run-insights exactly where it was measured: OpenAI-shaped `POST {LLM_VISION_BASE_URL}/chat/completions`, `Bearer LLM_API_KEY`, `model: LLM_VISION_MODEL` (`glm-4.6v`), `thinking: {type:'disabled'}`, image as a base64 `data:image/jpeg` URL, a token floor (prompt_tokens per image) that fails closed, never the `/api/anthropic` base URL (it silently drops images). The keys already exist in `web/.env.local` (`LLM_API_KEY`, `LLM_VISION_BASE_URL=https://api.z.ai/api/coding/paas/v4`, `LLM_VISION_MODEL=glm-4.6v`); Vercel's env must get them too.
- **Pinned digests.** `cost_rate` is part of every lab trial's config digest, the registry pins and the paper roster's spec digest. Changing the default re-digests everything (pre-registrations fail, paper books hit `SpecMismatch`). The established escape hatch is a new lever with a true no-op default registered in `LEVERS_SINCE_PINS` (`sim/rules.py:213-215`).
- **Owner holds pre-RAW positions** (SPY, NVDA, PLTR, FUTU, GE, LRCX, LLY, WDC…) bought long before RAW existed. Reminders must not tell the owner to sell those just because RAW does not hold them.
- **No cash data.** Order receipts don't show the Gotrade cash balance; P&L must be computed from orders + market prices only.
- **Owner isn't a trader** (memory): plain words, no ids/digests on the page; every button icon-only Lucide + `aria-label` + `data-tip`; Seer v2 design tokens and components, never a generic look.

**Assumptions (stated, planned against).**
- Sean is owner-only, gated exactly like Sera (`SERA_EMAIL`), because it shows the owner's real money.
- Screenshots are not stored after parsing — only the parsed order and a SHA-256 of the image bytes (dedupe). Seer web has no Blob dependency and doesn't need one.
- Reminders are in-app (a badge on the Sean button + a list), not push/email.

---

## Analysis Scope

### Explicitly Mentioned Files
- `gotrade_order_summary_screenshots.zip`
- `~/run-insights` (vision parsing reference)

### Discovered Related Files
- `web/components/Nav.tsx` / `Nav.module.css` — Seer rail with the Sera button
- `web/app/(app)/layout.tsx` — renders `<Nav showSera=…/>`
- `web/app/sera/layout.tsx`, `web/components/sera/SeraNav.tsx` (+ `.module.css`), `web/app/sera/sera.module.css` — the pattern for a separate section shell
- `web/lib/sera/gate.ts`, `web/lib/sera/access.ts` — the owner gate
- `web/lib/sera/gotrade.ts` — GitHub `workflow_dispatch` helper (`GITHUB_DISPATCH_TOKEN`)
- `web/app/sera/gotrade/actions.ts` — server-action write pattern
- `web/components/sera/{Section,Stat,PageHeader,Term}.tsx`, `web/components/sera/charts/{LineChart,Legend,scale}.tsx`
- `web/components/tooltip.ts`, `web/app/globals.css` (tokens, `.icon-btn`, `.sheet`, `.num`, `.pos/.neg`)
- `web/lib/data.ts`, `web/lib/db.ts`, `web/components/roster.ts`, `web/lib/cadence.ts`, `web/lib/sera/paper.ts`
- `web/scripts/migrate.mjs`, `db/migrations/*.sql` (latest `014_unavailable.sql`)
- `engine/src/seer_engine/sim/{rules,book,model,sizing}.py`, `backtest/{benchmark,book_runner,labels,dev,metrics}.py`, `paper/{benchmark,roster,store}.py`, `lab/{runner,store,method}.py`, `commands/{lab,paper,nightly}.py`, `yahoo.py`, `cli.py`
- `.github/workflows/{nightly,repick,engine-ci}.yml`
- `.claude/skills/explore-and-experiment-new-method/SKILL.md`, `.claude/skills/sera-the-explorer/SKILL.md`
- `docs/plans/2026-10-03-seer-design.md` (§ costs), `docs/design/Seer v2.dc.html`, `docs/plans/claude-design-brief.md`

---

## Current Dataflow

### Entry Point: the Seer rail

**Location:** `web/app/(app)/layout.tsx:12` → `web/components/Nav.tsx:19-28`
**Trigger:** every `(app)` page render (server layout, client Nav)

```tsx
<aside className={`${s.rail} desk-only`}>
  <span className={s.wordmark}>Seer.</span>
  <Tabs path={path} vertical />
  {showSera && (
    <Link href="/sera" className={`icon-btn ${s.sera}`} data-tip="Sera, the method lab" aria-label="Sera, the method lab">
      <Telescope size={21} strokeWidth={1.5} />
    </Link>
  )}
</aside>
```
`.sera { margin-top: auto; }` (`Nav.module.css:69-70`) pins the Sera button to the rail foot. The
rail is desktop-only (≥1024 px); the mobile bar is a fixed 4-column grid without Sera.

### Entry Point: the Sera section (the pattern Sean copies)

- `web/app/sera/layout.tsx:35-45`: `await requireSera()`, reads the journal-unseen count, renders
  `<div className={s.shell}><SeraNav journalUnseen=…/><main className={s.main}><div className={s.column}>{children}`.
- `web/lib/sera/gate.ts:9-14`: signed out → `/signin?next=…`; not `ALLOWED_EMAIL` or not `SERA_EMAIL` → `notFound()`. Each page also calls `requireSera('<path>')` (layouts don't re-run on client navigation).
- `SeraNav.tsx`: wordmark "Sera.", icon-only tabs (`TABS` array of `{href, icon, tip}`), unseen badge on one tab, "Back to Seer" (`Eye`) at the rail foot; top bar below 1024 px.

### Processing chain: roster → recommendations (what Sean must read)

1. Nightly GitHub workflow (`.github/workflows/nightly.yml`, crons `17 6 / 41 9 / 41 12 * * 2-6`) runs `seer_engine migrate` → nightly → veto → paper → paper_check.
2. `engine/src/seer_engine/commands/paper.py:_step_book` (`:787-864`) → `settle_book`/`step_book` (simulated fills at `rules.cost_rate`) → `decide_book` → `paper/store.py:save_book_decision` (`:1019-1070`) writes **`book_targets`** (strategy_id, session_date, rank, symbol, weight, last_price, limit_price, explanation, evidence) on decision sessions only (first session of each month for `monthly-hold-frac`).
3. `paper_state` (strategy_id, last_session, pending_session, pending_decision, …) says whether the next session acts.
4. Web reads via `web/lib/data.ts` (`pendingOrders()` `:296-333`, `positions()`, `bookPreview()`), server components with `dynamic = 'force-dynamic'`.

RAW = roster row `RAW-FR` (`db/migrations/013_roster_first_night.sql:43`): name `'RAW · Unbraked momentum'`, engine `book`, rules `monthly-hold-frac` (monthly, fractional, open_limit, 0.1% cost), top 20 equal-weight residual momentum (lab M0007-N20-RAW). "What RAW says to hold now" = `book_targets WHERE strategy_id='RAW-FR'` at the latest `session_date`.

### Processing chain: lab P&L and costs

1. `lab run` (`commands/lab.py:1002`) → `lab/runner.run_method` → `backtest/dev.run_registry` → `book_runner.run_rules` → `sim/book.run_book`/`step_book`.
2. Every money movement goes through four functions, `sim/book.py:335-362`:
   ```python
   def _buy_cash(price, shares, rules):  return q(price * shares * (_ONE + rules.cost_rate))
   def _sell_cash(price, shares, rules): return q(price * shares * (_ONE - rules.cost_rate))
   def _fee(price, shares, rules):       return q(price * shares * rules.cost_rate)
   def _shares_for(budget, price, rules):  unit = price * (_ONE + rules.cost_rate) ...
   ```
3. P&L per trade `pnl_usd = income − cost_usd` (`book.py:421`); equity = cash + Σ shares×mark; metrics (`backtest/metrics.py:109-146`): PF, max DD, CAGR, Sharpe; gates in `dev.make_row` (`dev.py:351-399`) and DSR (`dev.py:560-597`, `DSR_MIN=0.90`).
4. SPY benchmark uses the module constant `COST_RATE` (`sim/model.py:25`), not `rules.cost_rate`: `backtest/benchmark.py:104-125`, `paper/benchmark.py:170,250,278`.
5. `rule_owner_inputs` (`sim/rules.py:291-306`) flags any `cost_rate != 0.001` as owner input `"fee"`, which makes a variant ineligible (`dev.py:384`).
6. `LEVERS_SINCE_PINS` (`sim/rules.py:213-215`) + `is_pinned_default` keep a new no-op lever out of canonical text (`backtest/registry._canon`, `paper/roster.rules_dict`).

### Data Persistence

**Neon (Postgres).** Migrations in `db/migrations/NNN_name.sql`, applied by both `web/scripts/migrate.mjs` (`npm run db:migrate`, `DATABASE_URL_UNPOOLED`, one transaction per file, recorded in `schema_migrations`) and `engine commands/migrate.py` (run by nightly/repick). Additive only, `IF NOT EXISTS`. The web app writes only `action_dismissals`, `journal_seen`, `unavailable_symbols`. **No table holds real broker fills.**

**Prices.** `bars` (001) holds daily bars for universe symbols only; owner-held symbols such as FUTU may be missing. `engine/src/seer_engine/yahoo.py:download()` fetches arbitrary tickers.

### Exit Points
- Pages: server-rendered HTML; writes through server actions; one API route (`/api/sera/journal/seen`).
- GitHub `workflow_dispatch` from the web (`lib/sera/gotrade.ts:102-132`, `GITHUB_DISPATCH_TOKEN`).

---

## The reference: run-insights' GLM vision client

- `lib/llm/vision.ts:119-135`:
  ```ts
  res = await fetchImpl(`${env.LLM_VISION_BASE_URL}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${env.LLM_API_KEY}` },
    body: JSON.stringify({ model: env.LLM_VISION_MODEL, max_tokens: 4096, thinking: { type: 'disabled' }, messages }),
    signal: AbortSignal.timeout(opts.timeoutMs),
  })
  ```
  No `response_format`, no temperature, no stream. Reads `choices[0].message.content` only.
- Messages: system prompt + one user turn `[{type:'text', text:'IMAGE — …'}, {type:'image_url', image_url:{url:'data:image/jpeg;base64,…'}}, {type:'text', text:'Return one JSON object with exactly this shape: …'}]`.
- Token floor (`vision.ts:40,160-170`): `usage.prompt_tokens < 500 × imageCount` → `VisionTokenFloorError` (missing usage = 0, fails closed); checked before `res.ok`. Non-200/network/timeout → `VisionTransportError`.
- JSON extraction (`lib/llm/extractJson.ts:21-42`): strip ```` ```json ```` fence, take first `{` … last `}`, `JSON.parse`, `null` on failure/non-object.
- Validation with zod; one text-only "repair" retry with the bad reply and the issues.
- Prompt rules that measured best: "Transcribe ONLY what is literally visible. Never infer, never compute…", explicit format conversions, "Return ONLY a JSON object. No markdown fences…".
- Latency: 33–38 s median for 3 images with thinking disabled (73 s with thinking). `maxDuration = 60` must be a literal number in the route file.
- Tests inject `fetchImpl`: `vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(body))`; assert the request body has `thinking: {type:'disabled'}`.
- Client compression: JPEG q0.8 via `browser-image-compression`; Seer can use a canvas re-encode (no new dependency).

---

## Key Data Structures

### Table: `strategies` (roster)
**Location:** `db/migrations/001_init.sql:3` + `003_paper.sql:6-8` + `006_roster.sql:21-30`
**Fields used here:** `id`, `name`, `sub`, `icon`, `engine` ('book'|'bracket_v0'), `rules_id`, `status` ('active'|'retired'), `sort`.

### Table: `book_targets`
**Location:** `db/migrations/003_paper.sql:47-60` (+ `evidence jsonb` in 009)
**Fields:** `strategy_id, session_date, rank, symbol, weight numeric (0..1], last_price, limit_price, stop_price, take_price, explanation, evidence`.

### Dataclass: `TradeRules`
**Location:** `engine/src/seer_engine/sim/rules.py:71-86`
**Fields:** `id, engine, cadence, resize_cadence, entry, max_positions, time_stop, resize, fractional, dividends, idle_symbol, cost_rate=Decimal('0.001')`.

### Component: `LineChart`
**Location:** `web/components/sera/charts/LineChart.tsx:14-69`
**Props:** `series: LineSeries[]` (`{id,label,points:[x,y|null,tip?][],color,width,dash,area,step,dots,endLabel}`), `ariaLabel`, `x:'date'|'number'`, `yFormat`, `refLines`, `legend`, `width=960`, `height=360`. Server-rendered SVG, tested with `renderToStaticMarkup`.

---

## Dependencies

### Configuration / Environment
- Web: `DATABASE_URL`, `DATABASE_URL_UNPOOLED`, `ALLOWED_EMAIL`, `GITHUB_DISPATCH_TOKEN`, NextAuth vars; **new for Sean:** `LLM_API_KEY`, `LLM_VISION_BASE_URL`, `LLM_VISION_MODEL` (present in `web/.env.local`, must be added to the Vercel project).
- Engine: `DATABASE_URL` (Neon), yfinance for prices.
- `web/vercel.json`: `{"regions":["sin1"]}`; no Vercel crons — scheduling is GitHub Actions.

### Conventions that bind every phase
- Web tests: vitest, colocated `*.test.ts(x)`, **no `@/` alias in tested modules** (relative imports), no DB mocking — pure modules are tested, `lib/data.ts`/pages are not.
- Engine tests: pytest + xdist; `engine/tests/conftest.py` throwaway Postgres schema on `PG_TEST_URL` (docker postgres:16 on 55432); `simkit` refuses floats.
- Worktrees have no `engine/.venv`: `python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'` inside the worktree (memory `worktree-needs-own-venv`).
- `engine-ci.yml` runs ruff + pytest + web vitest.

---

## Impact Points (files that WILL need changes)

1. `db/migrations/015_sean.sql` (new) — Sean's tables. **Phase 1**
2. `web/lib/sean/*` (new: types, money parsing, vision client, prompt, extractJson, order validation, ledger, unzip) — **Phase 1**
3. `web/lib/sean/fixtures/*.json` (new: shared ledger/fee fixtures read by vitest AND pytest) — **Phase 1**
4. `web/components/Nav.tsx`, `Nav.module.css` — Sean button above Sera. **Phase 2**
5. `web/app/sean/{layout,page,trades/*,plan/page,not-found}.tsx`, `web/components/sean/SeanNav.tsx`, `web/lib/sean/gate.ts`, `web/app/api/sean/orders/route.ts` — **Phase 2** (overview/plan pages as placeholders)
6. `web/lib/sean/data.ts` (server-only reads) — created **Phase 2**, extended by 3 and 5
7. `web/app/sean/page.tsx` + `web/app/sean/overview.ts` — P&L page. **Phase 3**
8. `engine/src/seer_engine/commands/sean.py`, `engine/src/seer_engine/sean/*` (ledger + marks + equity writer), `.github/workflows/sean.yml`, `nightly.yml` — **Phase 4**
9. `web/app/sean/plan/*`, `web/lib/sean/reminders.ts`, `SeanNav`/`Nav` badge — **Phase 5**
10. `engine/src/seer_engine/sim/{costs.py,rules.py,book.py,model.py}`, `backtest/benchmark.py`, `backtest/book_runner.py`, `paper/benchmark.py` — Gotrade cost model + `cost_model` lever. **Phase 6**
11. `engine/src/seer_engine/commands/sean.py` (calibrate), `lab/*` cost reporting, `.claude/skills/explore-and-experiment-new-method/SKILL.md`, `sera-the-explorer/SKILL.md`, `docs/plans/2026-10-03-seer-design.md` (costs line) — **Phase 7**

**This document describes. The plan files prescribe.**
