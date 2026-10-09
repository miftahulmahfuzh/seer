# Package: seer-web

**Location**: `web` (Next.js app router; package name `seer-web`, private)
**Last Updated**: 2026-10-09 (repo README: two new scripts and nothing else. `scripts/film.mjs` records an animated GIF of the app through a goto/click/scroll/hold scene language -- `shoot.mjs` for things that move -- and `scripts/seed-demo-sean.mjs` fills Sean's tables on top of `seed-demo.mjs`, pricing every demo receipt at the real Gotrade fee regime of its own date so the demo's totals are arithmetic the Trades page can check. `db:migrate`, `db:seed-demo` and `db:seed-demo-sean` now load the repo-root `.env.local` through `with-env.mjs` like every other script; `--env-file=.env.local` resolved to a `web/.env.local` that does not exist and must not (see `with-env.mjs`). No app file, route, library or migration touched. Earlier: P1-WEB-V7XD: Sean's rotation plan is sized on holdings **plus cash**. A new pure module `lib/sean/cash.ts` derives the wallet — the owner's contribution schedule (10,000,000 IDR to start, +5,000,000 IDR on the 25th; `OWNER_MONTHLY`, deliberately the engine's own name) less what the plan's own orders spent — because a Gotrade receipt never shows a balance, so no code path reads one (`ledger.ts` is untouched); `planData.latestUsdIdr()` reads `fx_rates` and falls back to the measured `OWNER_USD_IDR` = 17,841. `buildReminders` sizes picks against `planValue + cashUsd` (`sean_link.budget_usd` survives as the manual override), `MIN_TRADE_USD` moves from a guessed $10 to a measured $25 (`trading_min / (2 × trading_rate)` from the engine's own fee constants), every amount is in dollars and never a share count, and the Plan tile now reads "Plan size" with its stocks-plus-cash split (`planSizeLine`, `cashLine`). Measured on the owner's real 2 November rotation: plan size $558.00 -> $838.16, each of 20 slots $27.90 -> $41.91. No migration, no schema change, no engine file touched. Earlier: P1-WEB-4TQ7: the blank panel is gone. A new pure, tested classifier `lib/decision.ts` names which of five situations "nothing to act on" is — paper paused, never started, the nightly late, the last decision spent, nothing due — and says in WIB when the next decision is due, from the cron slots of `.github/workflows/nightly.yml`. Positions renders a `Standing` sheet for each, keeps an expired decision visible as a `SpentDecision` record stripped of every order-ticket field, and never lets a retired strategy's pending row read as a live instruction; Today splits the old single coral alarm into a real alarm (never ran / late) and a calm `waiting` sheet. `lib/session.ts` gains `wibTime` and exports `addDays`. Earlier: P1-ROOT-XA2W, Sean phase 5: the `/sean/plan` tab — follow one roster book method (`sean_link`), buy/sell/add/trim reminders against the plan's holdings (pure `lib/sean/reminders.ts`, server reads in `lib/sean/planData.ts`), hand-made done marks (`sean_reminder_marks`), the Plan tab badge and a coral reminder dot on Seer's Sean buttons (`Nav`, `AppHeader`). Earlier: P1-ROOT-8JIM, Sean phase 3: the `/sean` Overview — stats row, daily profit-and-loss line from `sean_equity` with a live point or an order-only fallback, holdings table, empty state — via `app/sean/overview.ts` and `lib/sean/overviewData.ts`. Earlier: P1-ROOT-AUY5, Sean phase 1: migration `015_sean.sql` and the pure, DB-free foundation of Sean, the owner's real Gotrade trade tracker, under `lib/sean/` — receipt parsing and checking, the glm-4.6v screenshot reader, the shared ledger, a dependency-free zip reader — plus the live smoke script `scripts/sean-vision-smoke.mjs`. No route or page uses them yet)

## Overview

`seer-web` is Seer's private web app: a Next.js 16 / React 19 front end that reads the Neon
(Postgres) tables written by the Python engine (`engine/`) and shows tonight's picks, open
holdings, closed trades and the strategy leaderboard. It never trades and never computes
signals; it is a read model over `strategies`, `runs`, `orders`, `book_positions`,
`book_targets`, `book_trades`, `equity_snapshots`, `paper_state`, `bars` and `fx_rates`, plus two
writes (`action_dismissals` and `journal_seen`). A second, separate section, **Sera** (`/sera`),
shows the method lab from a committed JSON snapshot (`data/lab.json`): every lab *fact* — methods,
trials, insights — comes from the snapshot and none of it from Neon. The one thing Sera keeps in
Postgres is reader state: which Journal entries have been seen (`journal_seen`), so the badges on
the Journal's tabs count what is new instead of what exists.

A third section, **Sean**, is being built (plan `sean-gotrade-tracker`, 7 phases): it tracks the
owner's *real* Gotrade trades from "Order Summary" screenshots and shows real profit and loss.
Phase 1 landed its schema (`db/migrations/015_sean.sql`) and pure modules (`lib/sean/`); phase 2
the owner-only section and Trades upload; phase 3 the Overview (`/sean`); phase 5 the Plan
(`/sean/plan`: follow one roster method, buy/sell reminders sized on holdings plus derived cash).
See [Sean](#sean-sean-libsean).

**Key Responsibilities:**
- Google sign-in locked to exactly one allowlisted account (`auth.ts`, `lib/allow.ts`)
- One data layer (`lib/data.ts`) that turns rows of all three engines (`bracket`, `book`, `benchmark`) into typed view models
- Pure, DB-free logic that tests run without a connection: metrics and the go-live checklist (`lib/metrics.ts`), month-by-month paper performance (`lib/monthly.ts`), strategy row helpers (`lib/strategy.ts`), split-cadence wording and per-order size change (`lib/cadence.ts`), slot letters and card colours (`lib/slots.ts`), session freshness and WIB clock (`lib/session.ts`), why there is nothing to act on and when the next decision is due (`lib/decision.ts`), number/date formatting (`lib/format.ts`)
- Four pages: Today, Positions, History, Leaderboard
- Sera (`/sera`), the method lab section: gated to one account (`lib/sera/`), its own desktop shell and rail (`app/sera/layout.tsx`, `components/sera/`), a dependency-free SVG chart kit (`components/sera/charts/`), hand-built SVG diagrams for How it works (`components/sera/diagrams/`), and a pure data layer over the bundled lab snapshot `data/lab.json` (`lib/sera/types.ts`, `lab.ts`, `derive.ts`, `glossary.ts`, `markdown.ts`). Pages: Overview, Methods list + detail, Journal, Ideas, How it works; each page keeps its logic in a pure, tested `view.ts` (`overview.ts` for the Overview, and the Journal a second one, `seen-client.ts`, beside it). The Journal is the one Sera page that also touches Neon, for reader state only: `lib/sera/seen.ts` over `journal_seen` decides which entries are unseen, which orders them and fills the badges; it is also the only Sera page to mount a `'use client'` island of its own (`JournalSeen.tsx`), so `SeraNav.tsx` is no longer the section's sole client component. See [Sera](#sera-sera)
- Sean foundation (`lib/sean/`, phase 1, pure): Gotrade receipt text -> numbers (`money.ts`), the arithmetic check that turns the model's JSON into one `SeanOrder` (`order.ts`), the glm-4.6v vision client with its token floor (`vision.ts`, `prompt.ts`, `extractJson.ts`), the read-and-one-repair flow (`readOrder.ts`), the average-cost ledger shared with the engine (`ledger.ts`), and a browser zip reader (`unzip.ts`)
- Shared roster UI (`components/StrategySwitch.tsx`, `components/PaperChip.tsx`, `components/roster.ts`): icon-only strategy switching by `?s=` and the paper marker on research strategies' holdings, orders and trades
- Migrations runner shared with the engine (`scripts/migrate.mjs`) and two demo seeders (`scripts/seed-demo.mjs` for the paper roster, `scripts/seed-demo-sean.mjs` for Sean)
- Proof that a change renders: `scripts/shoot.mjs` (stills) and `scripts/film.mjs` (animated GIFs), both signed in without a human through `scripts/session.mjs`

## Layout

```
web/
  package.json              scripts: dev, dev:env, build, start, test (vitest), signin, shoot, film, db:migrate, db:seed-demo, db:seed-demo-sean
  next.config.ts, tsconfig.json, vercel.json (region sin1)
  auth.ts                   NextAuth (Google, JWT sessions), currentUser()
  scripts/
    gen_app_icon.py         OpenRouter (OPENROUTER_API_KEY in .env.local) draws eye candidates; spends money
    make-icon.mjs           erases the drawn pupil, adds the Lucide Sigma, writes apple-icon.png, icon.png, public/icons/* the splash mask public/splash-eye.png and the header mask public/eye-mark.png
    .icon/eye.png           the promoted candidate make-icon.mjs reads
  app/
    layout.tsx, globals.css, manifest.ts
    icon.png                favicon: the same eye as a rounded tile (scripts/make-icon.mjs)
    apple-icon.png          home-screen icon: Eye of Horus, Sigma pupil, on coral (scripts/make-icon.mjs)
    signin/                 sign-in / denied page; splash art is the mirrored eye (public/splash-eye.png) masked in --splash-star; honours ?next= via safeNext
    api/auth/               NextAuth route handlers
    api/sera/journal/seen/  route.ts: POST {ids, via} marks Journal insight ids seen; 204 ok / 400 bad body / 404 not the Sera user / 500 the write threw. Re-derives the /sera rule from isAllowed + isSeraUser rather than calling requireSera, whose redirect() would 307 to /signin and disclose the section exists; force-dynamic, and it parses the body itself without checking Content-Type because sendBeacon sends a Blob typed text/plain
    (app)/
      layout.tsx            signed-in shell
      actions.ts            server action dismiss(formData)
      page.tsx              Today: champion's picks + day-5 bracket actions; no-buys state for a SPY/non-bracket champion; paused note, and the coral alarm split from the calm "waiting" sheet by lib/decision.ts
      positions/page.tsx    any strategy's holdings (?s=), cards by Holding.kind, next-session paper orders, paper-step warning, the paused note, the Standing sheet naming why there is nothing to act on, and SpentDecision (an expired decision kept as a record)
      history/page.tsx      closed trades of both engines, filter by research strategy (?s=) and win/loss (?o=)
      leaderboard/page.tsx  roster-driven equity curves, champion crown, common-window ranking + window line, retired/not-ranked chips, per-strategy go-live checklist (?s=), month-by-month sheet
      leaderboard/view.ts   looks, researchOf, compare, windowLine, spyOverSpan, pickResearch, retiredLabel, scoreOf, monthLines, sinceStartLine  (pure)
      leaderboard/view.test.ts  vitest suite for view.ts
    sera/
      layout.tsx            requireSera(), the Journal's unseen total, then SeraNav rail + centred column (max 1360px); stacks below 1024px
      not-found.tsx         in-shell 404 (Section + back-to-overview icon link)
      sera.module.css
      page.tsx              /sera Overview: latest synthesis, KPI tiles, trial scatter vs the gate, hurdle funnel, progress, luck bar, families, latest methods
      overview.ts           pure shaping of the snapshot into chart-kit props (+ overview.test.ts, overview.module.css)
      methods/page.tsx      /sera/methods list, ?show=all|lab|historical|alive (view.ts pure helpers + view.test.ts, methods.module.css)
      methods/[id]/page.tsx /sera/methods/[id] method detail (method.module.css)
      journal/page.tsx      /sera/journal insights grouped by kind, ?kind= filter; unseen first (newest first), then seen below a divider; badges count unseen (view.ts + view.test.ts, journal.module.css)
      journal/JournalSeen.tsx   (client) marks entries seen: dwell on screen in a visible tab, or a redirect-arrow click; batches ids, flushes on page-hide, counts the badges down live
      journal/seen-client.ts    pure dwell/batch policy and the pending-id queue, DOM-free (+ seen-client.test.ts)
      ideas/page.tsx        /sera/ideas backlog, blocked-on-data wishlist, reading list (view.ts + view.test.ts, ideas.module.css)
      how/page.tsx          /sera/how path, calendar, hurdles, honesty rules, data, glossary (view.ts + view.test.ts, how.module.css)
  data/
    lab.json                GENERATED by `python -m seer_engine lab stage` / `lab export-json`; never edit by hand
  components/               AppHeader (eye mark left of the titles, mobile only), Nav, CopyButton, RefreshButton, WhyToggle, TooltipLayer, tooltip
    StrategySwitch.tsx      icon-only roster switcher (Links), ALL sentinel           (server component)
    PaperChip.tsx           "Paper" data label with tooltip, sm | md
    roster.ts               strategyIcon, selectStrategy, sharesLabel                (pure)
    roster.test.ts          vitest suite for roster.ts
    sera/
      SeraNav.tsx           (client) icon-only rail: Overview, Methods, Journal, Ideas, How it works (/sera/*), Back to Seer; the Journal tab carries an unseen-count badge (prop from app/sera/layout.tsx; no badge at zero)
      PageHeader.tsx        eyebrow, title, lede, asOf, aside
      Section.tsx           Section (eyebrow/title/caption, bg sheet|lav|butter|sky|stone|coral, aside), SectionGrid
      Stat.tsx              big figure + label, tone, tip, sub, size
      Term.tsx              glossary term with a wrapping definition tooltip
      charts/
        scale.ts            pure scales, nice ticks, year ticks, paths, label spreading, formatters, CHART_COLORS
        parts.tsx           HRef / VRef reference lines
        LineChart.tsx, ScatterChart.tsx, BarChart.tsx (+ barGroups), Legend.tsx (+ legendFromSeries)
        scale.test.ts, charts.test.tsx
      diagrams/
        geometry.ts         pure layout: PipelineStage, Era, rowBoxes, timeScale, yearTicks, monthYear (+ geometry.test.ts)
        Pipeline.tsx        idea -> real money stage boxes with a dashed "fails" lane (one per page: fixed marker ids)
        Windows.tsx         dev / test / paper timeline with shaded bear markets
        diagrams.module.css
  lib/
    db.ts                   sql = neon(DATABASE_URL)
    data.ts                 all DB reads (server only)
    strategy.ts             Engine, Gate, engineOf, parseGate, shortLabel, checksNews (pure)
    metrics.ts              Snapshot, Metrics, strategyMetrics, gateItem, checklist (pure)
    vetoes.ts               Verdict, Veto, parseVerdict, vetoSheet, checkedLine, headlinesLabel, noCheckLine (pure; P6)
    why.ts                  parseEvidence, Why, whyContent: what a "why" toggle shows     (pure)
    cadence.ts              SPLIT_CADENCE_RULES, picksMonthlySizesWeekly, RESIZE_BAND, sizeChange, sizeLabel (pure)
    monthly.ts              monthlyTable, monthOf                                  (pure)
    slots.ts                slot letters/sheets, slotCount, cardBg                 (pure)
    session.ts              addDays, nextUsSession, isStale, wibDate, wibTime      (pure)
    decision.ts             PAPER_PAUSED, NIGHTLY_SLOTS_UTC/DAYS_UTC, publishDay,
                            timing, pipelineState, panelState                      (pure)
    format.ts               money/usd/rp/pct and date formatters                   (pure)
    allow.ts                isAllowed, safeNext                                    (pure)
    sera/access.ts          SERA_EMAIL, isSeraUser                                 (pure)
    sera/gate.ts            requireSera(next) (server only)
    sera/seen.ts            seenInsightIds() / unseenCount(ids) / markInsightsSeen(ids, via): the journal_seen read/write. The two reads never throw -- a failed query is an empty set for the page and null for the rail -- while markInsightsSeen throws by design, which is the route's 500 (server only)
    sera/types.ts           LabSnapshot / LabMethod / LabTrial / LabInsight: the data/lab.json contract
    sera/lab.ts             lab snapshot + methodById, trialsOf, insightsOf, childrenOf (server only)
    sera/derive.ts          gate checks (threshold labels matched by prefix), misses, closest, bestVariant, funnel, progress, families, SPY TR, drawdown, years (pure)
    sera/glossary.ts        GLOSSARY plain-language terms, status / insight / source labels  (pure)
    sera/markdown.ts        escape-first markdown -> HTML for lab analysis text            (pure)
    sera/fixture.ts         GATE, trial(), method() builders (tests only)
    sera/gotrade-symbol.ts  normalizeSymbol: a Gotrade ticker -> the engine's canonical symbol (used by sean/order.ts)
    sean/                   Sean phase 1, all pure (relative imports only), each with a colocated *.test.ts
      types.ts              OrderSide, SeanFill, SeanOrder (mirrors sean_orders), RawFill, RawReceipt (the model's printed-text shape)
      money.ts              asText, roundHalfUp (Python ROUND_HALF_UP), cents, fixed, parseUsdParts, parseUsd, parseShares, parseReceiptDate (WIB)
      extractJson.ts        extractJsonObject: first `{` to last `}` of a model reply, null never throws
      prompt.ts             ORDER_SYSTEM_PROMPT, ORDER_SHAPE, jpegDataUri, buildOrderUserContent, buildRepairNote
      vision.ts             glm-4.6v fetch client: visionConfigFromEnv, tokenFloor, readOrderWithFetch, repairOrderWithFetch, VisionTokenFloorError, VisionTransportError
      order.ts              toOrder(raw) -> { ok, order } | { ok: false, kind, issues }; sideOf; tolerances
      readOrder.ts          readOrder(deps, imageB64, budgetMs): vision -> JSON -> toOrder -> at most one repair; READ_MESSAGES, isReaderDown, visionDeps
      ledger.ts             orderSession (NY session), buildLedger, pnlSeries, pnlAt, DUST_SHARES
      unzip.ts              readZip (stored + deflate, CRC-checked), ZipError, inflateRawWeb, IMAGE_NAME, baseName, isJunkEntry, crc32
      fixtures/receipts.json  four real receipts transcribed by hand, raw + expected SeanOrder
      fixtures/ledger.json    shared ledger fixture (contract B), replayed by web and engine tests alike
      overviewData.ts       phase 3, server only (Neon): equity() -> EquityRow[] (sean_equity, oldest first), marks() -> LatestMark[] (newest sean_marks close per symbol)
      cash.ts               phase 10, pure: the derived wallet — OWNER_MONTHLY (mirrors the engine's schedule), OWNER_USD_IDR, depositDates, depositedIdr, depositedUsd, netSpentUsd, cashUsd
      reminders.ts          phase 5, pure: buildReminders (sell/trim/buy/add vs the plan, sized on holdings + cash), planOrders, sharesBySymbol, outsideShares, resizes, RESIZING_RULES, MIN_TRADE_USD ($25, derived)
      planData.ts           phase 5, server only (Neon): linkableMethods, link, latestTargets, reminderMarks, latestCloses, latestUsdIdr, planState, openReminderCount (React cache, 0 on any failure)
    *.test.ts               vitest suites for every pure module
  scripts/
    migrate.mjs             applies ../db/migrations/*.sql once each (schema_migrations)
    seed-demo.mjs           demo data in the paper-trading shape; --dry-run
    seed-demo-sean.mjs      Sean demo data on top of it: broker receipts priced at the real Gotrade
                            fee regime of each order's date, the ledger, the nightly P&L series, a
                            plan mid-rotation with three live buy reminders, and one order claimed
                            as the owner's own. Refuses to run unless the roster is the demo one;
                            --dry-run
    film.mjs                an animated GIF of the app, signed in -- shoot.mjs for things that move.
                            A scene language of goto/click/scroll/hold steps, captured at --interval
                            and assembled by ffmpeg with a per-GIF palette. Needs ffmpeg on PATH
    sean-vision-smoke.mjs   live (paid) check of lib/sean/readOrder against real receipts; never in CI
```

## Exported API

### lib/strategy.ts (pure)

```ts
type Engine = 'bracket' | 'book' | 'benchmark';
type Gate = { passed: boolean; applicable: boolean; note: string | null };
function engineOf(engine: unknown, isBenchmark: boolean): Engine;
function parseGate(raw: unknown): Gate;
function shortLabel(name: string, id: string): string;
function checksNews(id: string, specObject: unknown): boolean;
```

- `engineOf`: the `strategies.engine` column (migration 003). Unknown or missing (pre-003 rows) falls back to `benchmark` when `is_benchmark`, else `bracket`.
- `parseGate`: reads `strategies.params->'backtest_gate'` (contract C2). Missing, malformed, or anything other than `passed === true` reads as not passed; a blank note becomes `null`. A pass is never assumed. `applicable` is false only for an explicit `applicable: false` (Strategy C, an LLM strategy: design §1 item 5, handover D9), and a not-applicable gate always reads `passed: false`.
- `checksNews`: true for a strategy that runs the nightly news check (C): its spec `object` is `STRATEGY_C`, or its id is `C` before `paper` wrote a spec.
- `shortLabel`: the part of the name before the middle dot (`'F4 · Momentum'` -> `'F4'`); the id when that part is empty.

### lib/metrics.ts (pure)

```ts
type Snapshot = { date: string; equity: number };
type Metrics = { totalReturn; winRate; profitFactor; maxDrawdown: number | null; trades: number; months: number };
function strategyMetrics(snaps: Snapshot[], pnls: number[]): Metrics;
type CheckItem = { label: string; val: string; ok: boolean; note?: string };
function gateItem(gate: Gate): CheckItem;
function checklist(m: Metrics, spyReturn: number | null, gate: Gate): CheckItem[];
```

- `strategyMetrics`: total return first-to-last snapshot, win rate and profit factor over closed-trade P/L (`Infinity` with no losses), max drawdown over the curve, months = days / 30.44. Expects snapshots in date order. Definitions are identical to the engine's backtest metrics.
- `checklist`: design §1 go-live rules, **six** items, all must hold: >= 3 months forward, >= 100 trades, beats SPY, profit factor >= 1.3, max drawdown <= 20% (`MAX_DRAWDOWN` / `MAX_DRAWDOWN_LABEL` from `lib/golive.ts`, raised from 15% on 2026-10-07; `golive.test.ts` asserts it equals `data/lab.json`'s `gate.maxDrawdown`, so the leaderboard can never judge at a bar the engine abandoned), and **Backtest gate passed** (from `gate`; carries `note` when the roster gives one). The gate parameter is required. Row 6 is `gateItem(gate)`: for a not-applicable gate it reads `{ label: 'Backtest gate', val: 'Not applicable', ok: false }` (plus the note), so such a strategy never passes all six.

### lib/monthly.ts (pure)

```ts
type MonthRow = { month: string; from: string; to: string; return: number; spyReturn: number | null;
                  trades: number; worstDrop: number; partial: boolean };
type SinceStartRow = { from; to; return; spyReturn; trades; worstDrop };
type MonthlyTable = { months: MonthRow[]; sinceStart: SinceStartRow | null };
type MonthlyInput = { snaps: Snapshot[]; spy: Snapshot[] | null; exitDates: string[]; sessionDate: string | null };
const monthOf: (ymd: string) => string;           // 'YYYY-MM'
function monthlyTable(input: MonthlyInput): MonthlyTable;
```

Month-by-month paper performance (D5), oldest month first, plus a since-start row. Rules:
a month's base is the last snapshot before it (day 0 for the first month); return = month-end
equity / base - 1; SPY return uses the benchmark's equity on the same two dates (null if either
is missing); trades = closed trades whose exit date falls in the month; worst drop = largest
peak-to-trough within the month with the peak seeded at the base. The first month is `partial`
when day 0 is in it; the latest month is `partial` while `sessionDate` is still in it (or unknown).
Fewer than two snapshots returns `{ months: [], sinceStart: null }`. Input snapshots may be in
any order.

### lib/slots.ts (pure)

```ts
SLOT_LETTERS = ['S','E','E','R']; SLOT_BG = ['bg-lav','bg-butter','bg-sky','bg-stone']; BRACKET_SLOTS = 4;
slotLetter(slot: number); slotBg(slot: number);              // 1-based, wraps any integer
slotCount(engine: Engine): number;                           // 4 for bracket, 0 for book and benchmark
cardBg(slot: number | null, index: number): string;          // slot's sheet, else cycled by 0-based list index
```

### lib/vetoes.ts (pure, P6)

```ts
type Verdict = 'allow' | 'veto' | 'failed';
type Veto = { rank: number; symbol: string; verdict: Verdict; reason: string; headlineCount: number; earningsDate: string | null; decidedAt: string };
function parseVerdict(v: unknown): Verdict;                 // anything unknown -> 'failed'
type VetoSheet = { state: 'missing' } | { state: 'failed'; checked; reason } | { state: 'listed'; checked; allowed; rows: Veto[] };
function vetoSheet(rows: Veto[]): VetoSheet;
const checkedLine: (checked: number, allowed: number) => string;   // '8 checked · 5 allowed'
const headlinesLabel: (k: number) => string;                       // 'No headlines' | '1 headline' | '12 headlines'
const noCheckLine: (day: string, short: string) => string;
```

- `vetoSheet`: no rows → `missing`; every row `failed` with one shared reason → `failed` (shown once); else the `veto` and `failed` rows by rank with the counts.
- `noCheckLine`: the `missing` state's line, "No news check for {day}: A had no candidates, or the check did not run. {short} buys nothing this session." `veto` writes no rows on a night A has no candidates, so the app cannot tell that from a check that did not run, and says so.

### lib/why.ts (pure)

```ts
function parseEvidence(raw: unknown): string[] | null;   // non-array -> null; non-strings and blanks dropped; empty -> null
type Why = { kind: 'text'; text: string } | { kind: 'facts'; facts: string[] } | { kind: 'missing'; text: string };
function whyContent(text: string | null | undefined, facts: readonly string[] | null | undefined, missing: string): Why;
```

- `evidence` (migration 009, written by the engine's paper step) is a JSON array of short plain-English facts: the numbers the method used for that pick. The engine's Explain step writes `explanation` from them.
- `whyContent`: the text when it is non-blank; else the facts (a short list); else `missing`. `WhyToggle` renders it.

### lib/cadence.ts (pure)

```ts
const SPLIT_CADENCE_RULES: readonly string[];   // 'monthly-rank-weekly-resize', '-tbill', '-frac'
function picksMonthlySizesWeekly(rulesId: string | null | undefined): boolean;
const RESIZE_BAND = 0.01;                        // share of paper equity
type SizeChange = { action: 'buy' | 'add' | 'trim' | 'none'; usd: number };   // usd >= 0, 0 for none
function sizeChange(weight: number, equity: number, heldUsd: number | null): SizeChange;
function heldUsd(holdings: readonly { symbol: string; value: number }[]): Map<string, number>;
function orderSizeChange(weight: number | null, equity: number | null, symbol: string, held: ReadonlyMap<string, number>): SizeChange | null;
function sizeLabel(c: SizeChange): string;      // 'Buy about $40.00' | 'Add about …' | 'Trim about …' | 'No change'
function sizeTip(c: SizeChange): string;        // plain-words tooltip
```

- Split-cadence book strategies pick their stocks on the first session of each month and check how much to hold on the first session of each week (engine `sim/rules.py` `MONTHLY_RANK_WEEKLY_RESIZE*`). `picksMonthlySizesWeekly` keys on `Strategy.rulesId`.
- `sizeChange`: target = `weight × equity`. Not held -> `buy` the whole target; held and off by less than `RESIZE_BAND × equity` -> `none` (the engine skips such a trade); else `add` / `trim` the gap. Approximate on purpose: the engine sizes at the open's equity, the page at tonight's equity and marks.
- `orderSizeChange` returns null when the weight or paper equity is unknown; `heldUsd` sums `Holding.value` per symbol.

### lib/decision.ts (pure)

Why there is nothing to act on, in one word, and when the next decision is due. Renders nothing: it
only names the state and the times, so Today and Positions say the same words and a test can pin
them.

```ts
const PAPER_PAUSED: boolean;                                  // true while the roster is rebuilt at Gotrade's real fees
const NIGHTLY_SLOTS_UTC: readonly (readonly [number, number])[];  // [[6,17],[9,41],[12,41]] = 13:17 / 16:41 / 19:41 WIB
const NIGHTLY_DAYS_UTC: readonly number[];                    // [2,3,4,5,6] — cron's 2-6, Tue..Sat; Date.getUTCDay() numbering
function publishDay(session: string): string;                 // the latest Tue..Sat on or before `session`
type Timing = { target: string; dueAt: Date; lateAfter: Date };
function timing(now: Date): Timing;
type PipelineState = 'never' | 'late' | 'waiting' | 'current';
function pipelineState(runSession: string | null, lastGoodRun: Date | null, now: Date): PipelineState;
type PanelState = 'never' | 'live' | 'holding' | 'spent';
function panelState(pendingSession: string | null, pendingDecision: boolean, now: Date, retired?: boolean): PanelState;
```

- `.github/workflows/nightly.yml` is the source of truth for all three constants, and `decision.test.ts`
  reads that file and fails when they drift from it: the three cron slots in order, `2-6` as
  Tuesday-to-Saturday, and `PAPER_PAUSED`.
- `PAPER_PAUSED` is a constant on purpose, not derived from the database. The only candidate
  signature ("the latest run succeeded and its paper step never ran") is both late (a run from
  before the pause still carries `paper_status = 'success'`) and ambiguous (it also describes a
  strategy whose paper had not started yet).
- `publishDay` is why a Monday evening does not read as late: Monday's picks come from Saturday's
  run, because a session only becomes fetchable at ET midnight. The window is keyed to the nightly
  that *owes* `target` its decision, never to "the last slot that fired".
- `pipelineState` is the nightly behind the page. `waiting` is the routine daily state — the last
  good run is spent and the next is not due yet — and it is what used to render as a coral alarm.
  `late` requires the final retry slot (19:41 WIB) to have passed.
- `panelState` is one strategy's own decision. `holding` is read from the engine's recorded answer
  (`paper_state.pending_decision`), never re-derived: those boundaries are NYSE trading sessions and
  this module has no trading calendar. The fourth argument is not optional in practice — see Gotchas.

### lib/data.ts (server only; every function queries Neon)

Types:
- `Strategy`: `id, name, sub, icon, isChampion, isBenchmark, engine, rulesId, paperStart, status, paperEnd, gate, isPaper, short, checksNews`. `isPaper` = neither champion nor benchmark (research strategy, never a buy recommendation). `paperStart` is null until the engine's `paper` command starts the clock. `status: StrategyStatus = 'active' | 'retired'` and `paperEnd` (the last paper session a retired strategy traded; null while active) are migration 006's roster lifecycle. `parseStatus` reads **only** the exact string `'retired'` as retired, so a missing, null or malformed value reads as active and a bad read never hides a live strategy. `checksNews` (P6) marks C, whose Positions view reads its verdicts.
- `RunStatus`: `sessionDate, dataDate, finishedAt, isDemo, stale, usdIdr` from the latest **successful** run (IDR falls back to 16500), plus `latestStatus, paperStatus, paperError, paperFinishedAt` from the most recent run whatever its outcome. `RunState = 'running' | 'success' | 'failed'`.
- `Pick`: a champion's pending bracket order for Today, with `evidence`.
- `Holding` (replaces the old `Position`): one open holding of any engine. `key` is unique across engines (`'o:<orders.id>'` or `'b:<strategy>:<symbol>'`); `kind: Engine`; bracket-only `orderId`, `slot`; `tp`/`sl` nullable (book sets them only when its rules do); `maxDays` is 5 for bracket, null otherwise; `weight` = value / last equity; `pnl`/`pnlPct` for book include fees and dividends (`value + income - cost`); `dismissed` (bracket day-5 action done); `exitPending` (book sell decided for the next open).
- `PendingOrder` / `Pending`: what a strategy will do at the next session. Bracket: pending orders (`rank` = slot, whole `shares`). Book: `book_targets` of the pending decision (`weight` in (0,1], `shares` null). `Pending.decision` is false for SPY and for book strategies whose next session is not a decision session. `evidence: string[] | null` is the method's stored facts for the pick.
- `PreviewPick` / `Preview`: `book_previews` rows (`rank, symbol, weight, last, evidence`) for 'would pick now'.
- `ExitReason = 'tp' | 'sl' | 'time' | 'gap' | 'signal' | 'forced'`.
- `Trade`: closed trade of either engine. `key` unique across engines (`'o:<id>'` / `'b:<id>'`); `id` is unique only within its own table; `kind`, `strategyShort`, nullable `shares` (book keeps none) and `days`.
- `Board`: `{ rows: { strategy, metrics, curve }[]; from; to }`.
- `BRACKET_MAX_DAYS = 5` (design §5).

Functions:
- `strategies(): Promise<Strategy[]>` ordered by `sort, id`; `champion(): Promise<Strategy | null>`. It projects `status` and `paper_end` alongside the rest, and takes the spec object from `COALESCE(params->'spec'->>'object', object_name)`: a just-promoted row has `params = '{}'` until its first paper night, so the roster column answers until the spec is frozen and no display fact is lost on the first night.
- `runStatus(now?): Promise<RunStatus>`.
- `picks(strategyId, sessionDate): Promise<Pick[]>`: pending bracket orders for one session.
- `positions(strategyId): Promise<Holding[]>`: bracket orders (days held desc, slot) then book positions (value desc). Equity for `weight` comes from `paper_state`, else the latest snapshot.
- `pendingOrders(strategyId): Promise<Pending>`.
- `bookPreview(strategyId): Promise<Preview>`: tonight's 'would pick now' list; empty when 008 is not applied. `picks`, `pendingOrders` and `bookPreview` read `evidence` as `to_jsonb(<row>) -> 'evidence'`, so they work before the nightly applies 009 (the value is NULL), and pass it through `parseEvidence`.
- `vetoes(strategyId, sessionDate): Promise<Veto[]>` (P6): every `news_vetoes` row for that strategy and session, by rank (`headlineCount = jsonb_array_length(headlines)`). Called only for `checksNews` strategies: their roster row and the table both come from migration 004.
- `closedTrades(strategyId | null, 'win' | 'loss' | null): Promise<Trade[]>`: closed orders UNION non-idle book trades, newest first, max 300.
- `leaderboard(): Promise<Board>`: each strategy's metrics over all its snapshots (day 0 included) and only **its own engine's** closed trades (bracket -> orders, book -> book_trades, benchmark -> none).
- `monthly(strategyId, sessionDate): Promise<MonthlyTable>`: loads the strategy's and the benchmark's snapshots and its exit dates, then delegates to `monthlyTable`.
- `dismissAction(orderId)`: the only write; idempotent insert into `action_dismissals`.

### components/roster.ts (pure)

```ts
function strategyIcon(name: string): LucideIcon;   // strategies.icon (kebab-case) -> Lucide icon
function selectStrategy<T extends { id: string; isBenchmark: boolean }>(roster: T[], requested: string | undefined): T | null;
function sharesLabel(n: number): string;          // 1 -> '1 share', 2.50004 -> '2.5 shares'
```

- `strategyIcon`: known names `landmark` (SPY), `sigma` (A), `trending-up` (F4), `shield` (F1), `gavel` (C, migration 004), plus `brain-circuit` for old demo rows; unknown falls back to `Sigma`.
- `selectStrategy`: the requested id when it is on the roster, else the first non-benchmark strategy, else the first row, else null.
- `sharesLabel`: rounds to 4 dp (book shares are fractional); singular only at exactly 1.
- Short labels and the paper flag are not here: they are `Strategy.short` and `Strategy.isPaper` from `lib/data.ts`.

### components/StrategySwitch.tsx, components/PaperChip.tsx

```tsx
const ALL = 'all';
<StrategySwitch strategies={{ id, name, icon }[]} current={string} href={(id) => string} label={string} allTip?={string} />
<PaperChip size?={'sm' | 'md'} />
```

- `StrategySwitch`: a `<nav aria-label={label}>` of `next/link` icon buttons (`replace`, `scroll={false}`), one per roster row with `strategyIcon(icon)`, tooltip and `aria-label` = its name, `aria-current` on `current`. `allTip` adds a leading `ListFilter` button whose id is `ALL`. Server component because `href` is a function prop; callers build hrefs so other query params survive.
- `PaperChip`: a non-interactive span (FlaskConical + "Paper", dashed) with the tooltip "Paper trade: simulated, no real money" (D3).

### app/(app)/leaderboard/view.ts (pure)

```ts
type RosterIn = { id: string; isChampion: boolean; isBenchmark: boolean };
type Look = { bg: string; line: string; width: number; dotted: boolean };
function looks(roster: RosterIn[]): Map<string, Look>;
const LOOK_FALLBACK: Look;
const LOOK_PERIOD = 20;                                             // lcm(CARD_BGS, LINES)
function researchOf<T extends RosterIn>(roster: T[]): T[];          // non-benchmark rows

type RankIn = RosterIn & { status: 'active' | 'retired' };          // Strategy satisfies it, no import
const MIN_COMMON_SESSIONS = 63;                                     // == compare.py's
const MIN_RANKED = 2;                                               // == compare.py's
type CompareWindow = { from: string; to: string; sessions: number };
type CompareStatus = 'ranked' | 'insufficient' | 'retired';
type CompareRow<T> = { strategy: T; status: CompareStatus; sessions: number;
  totalReturn; cagr; maxDrawdown; sharpe: number | null;            // windowed; null unless 'ranked'
  inception: number | null };                                       // own whole record, never ranked on
type Comparison<T> = { window: CompareWindow | null; shared: number;
  rows: CompareRow<T>[]; ranked: CompareRow<T>[]; best: CompareRow<T> | null };
function compare<T extends RankIn>(rows: { strategy: T; curve: Snapshot[] }[]): Comparison<T>;
type WindowLine = { label: string; detail: string };
function windowLine(c: Comparison): WindowLine;
function spyOverSpan(spy: Snapshot[], curve: Snapshot[]): number | null;
function pickResearch<T extends RankIn>(research: T[], requested: string | undefined): T | null;
const retiredLabel: (paperEnd: string | null) => string;            // 'Retired Dec 2' | 'Retired'
const CHECKS = 6;
type Score = { passed: number; total: number; ready: boolean; lines: [string, string] };
type GateIn = { passed: boolean; applicable: boolean };
const NO_GATE: GateIn;                                              // not passed, applicable
function scoreOf(items: { ok: boolean }[], gate: GateIn): Score;
function monthsBg(look: Look): string;                              // butter -> stone (months sheet)
type MonthLine = { key; label; partial: boolean; ret: { text; tone: '' | 'pos' | 'neg' }; spy; trades; drop };
function monthLabel(ym: string): string;                            // '2026-10' -> 'Oct 2026'
function monthLines(t: MonthlyTable): MonthLine[];                  // newest first
function sinceStartLine(t: MonthlyTable): MonthLine | null;         // null before the first paper session
```

- `looks`: research strategies take the design's sheets and lines (`CARD_BGS` lav/sky/stone/butter, `LINES` ink/line-b/line-c/coral/ink-2) in roster order. The roster is variable length — a promotion adds a strategy, a retirement keeps one — so neither array is assumed to cover it: the two cycle **independently** and their lengths are coprime, so the (sheet, line) pair is unique for the first `LOOK_PERIOD = 20` research strategies. The champion's line is thicker (2.75); the benchmark is a dotted `--ink-3` line on a plain sheet. No hardcoded A/B/C ids. The card grid is `auto-fit` (`minmax(180px, 1fr)`), not a capped column count, so a sixth strategy wraps instead of squeezing.
- `compare`: the only way the page ranks anything — a faithful TypeScript port of the engine's `seer_engine/paper/compare.py`, same set-intersection common window, same greedy drop-the-worst-overlap `_select`, same `MIN_COMMON_SESSIONS = 63` / `MIN_RANKED = 2`, same rank key (annualised Sharpe desc, no-Sharpe last, total return desc, smaller max drawdown, id). It replaced the old raw `max(totalReturn)`, which compared strategies with different `paper_start` dates and so was not a comparison at all. Two filters live **here** rather than in the ported math, which stays status-blind and benchmark-blind like `compare.py`: the benchmark is never compared (it is the yardstick), and a retired strategy is excluded from the window and from `ranked` but never dropped from `rows` — it keeps its card, its inception-to-date figure, its chart line and its month sheet. `window` is null exactly when nothing is ranked; `shared` is presentation only (how many sessions the live board has in common so far) and is never a window.
- `windowLine`: the sentence that puts the window on the page, so a "best" is never shown without saying over which sessions it was best — `Ranked over <Mon d> – <Mon d>` with `<n> shared sessions · <k> of <m> active strategies compared`, or `No common window yet` / `<shared> of 63 sessions shared by every strategy` when nothing is ranked (and then the page shows no "best" figure at all).
- `spyOverSpan`: the benchmark's return over exactly the span a strategy's curve covers. The "Beats SPY" checklist row uses this, not SPY's inception-to-date figure, now that strategies need not start on the same day. Null when SPY has no snapshot on a boundary date.
- `pickResearch` (replaces `selectStrategy` on this page): the requested id when it is on the roster, else the first **active** strategy, else the first row. Retired strategies stay selectable — retirement preserves the record, it does not hide it — but the default never lands on one while a live strategy exists.
- `retiredLabel`: `'Retired Dec 2'` for the card's `Archive` chip, plain `'Retired'` until `paper_end` is written. A retired card is dimmed (`[data-status='retired']`) and its legend swatch muted; a `status: 'insufficient'` card carries a dashed "Not ranked" chip instead of silently vanishing from the board.
- `scoreOf`: `ready` only when exactly six items are given and all pass; lines are "All six pass. / Ready for real money", else "Paper trading until / all six pass" when the gate passed, else "Paper only. / Backtest gate not passed". A not-applicable gate (C) is never ready and reads "Paper only. No backtest gate. / Real money needs an owner decision" (handover D9).
- `monthLines` / `sinceStartLine`: format `lib/monthly.ts`'s `MonthlyTable` (Return toned pos/neg, SPY, Trades, Worst drop; `—` for nulls); the since-start row is labelled `Since <monthDay(from)>`.

### Other modules

- `lib/session.ts`: `addDays(ymd, n)` (pure date arithmetic, no timezone; `n` may be negative), `nextUsSession(now)`, `isStale(latestSessionDate, now)`, `wibDate(now)`, `wibTime(at)` (the Jakarta clock time, 24-hour: `'13:17'`; 24-hour on purpose because the owner reads WIB and every schedule in this repo is UTC, so the two are always printed side by side). Weekends only; holidays are the engine's job. `addDays` and `wibTime` exist for `lib/decision.ts` and the two pages' "next run is due" lines.
- `lib/format.ts`: `money, usd, signedUsd, rp, signedRp, pct, signedPct, shortDate, monthDay, monthName` (true minus sign, IDR rounded to Rp 1,000, dates parsed at UTC noon).
- `lib/allow.ts`: `isAllowed(email, allowed)`, case/space-insensitive exact match. `safeNext(next, fallback = '/')`: returns `next` (first value if an array) only when it is an internal path: starts with `/`, not `//` or `/\`, no control characters or backslashes; else `fallback`. Sign-in uses it for its post-login redirect.
- `lib/sera/access.ts`: `SERA_EMAIL = 'mahfuzh74@gmail.com'`; `isSeraUser(email)` trimmed, case-insensitive equality with it.
- `lib/sera/gate.ts`: `requireSera(next = '/sera')`: signed out -> `redirect('/signin?next=…')`; signed in but not `ALLOWED_EMAIL` or not `SERA_EMAIL` -> `notFound()` (the section is not revealed); else returns the user. Called by `app/sera/layout.tsx`.
- `lib/sera/types.ts`: the `data/lab.json` contract (`LabSnapshot` with `asOf`, `gate`, `data`, `summary`, `benchmark`, `methods`, `trials`, `insights`, `ideasSeen`), derived aliases (`LabStatus`, `InsightKind`, `SourceKind`, `Gate`, `DsrPolicy`, `Benchmark`, `Point = [date, value]`) and the `METHOD_STATUSES` / `INSIGHT_KINDS` / `SOURCE_KINDS` lists. Must match the engine's `lab stage` export. The `gate` block carries the luck check in full: `dsrMin` (the bar, `lab.store.DSR_MIN`, 0.90 since 2026-10-07), `dsrPolicy` (`DsrPolicy = 'all-trials' | 'methods' | 'effective'` — `lab.store.DSR_POLICY`, `all-trials` in force), `dsrN` (what that policy resolves to on this snapshot, computed at export time, not stored) and `dsrNBasis` (one line of engine-written evidence for that N; display as given, never parse it). `maxDrawdown` is 0.2.
- `lib/sera/lab.ts`: `lab` (the JSON imported at build time; server components only, it is large), `methodById(id)`, `trialsOf(methodId)` (by n), `insightsOf(methodId)` (by id), `childrenOf(methodId)` (by id).
- `lib/sera/derive.ts` (pure): six hurdles `CONDITION_KEYS` (`spy, drawdown, pf, trades, owner, dsr`) with `CONDITION_LABEL` / `FAILURE_LABEL`. `FAILURE_LABEL` covers only the four labels that carry no number; the luck and drawdown labels spell their own threshold, so `conditionOk` matches them by prefix instead — `DSR_FAILURE_PREFIX = 'DSR >= '` and `DRAWDOWN_FAILURE_PREFIX = 'max DD <= '`, mirroring the engine's `lab.store.LUCK_LABEL_PREFIX` and `dev.FAILURE_LABELS`. `trials` is append-only, so a row judged before 2026-10-07 carries `DSR >= 0.95` and `max DD <= 15%` for ever while a later row carries `DSR >= 0.90` and `max DD <= 20%`; both mean the same miss, and exact-equality matching would silently stop recognising the older half. Also `conditionOk` (null = not measured), `gateChecks(trial, gate)`, `conditionsPassed`, `misses`, `excessCagr`; over dev-window trials: `closest(trials, k)` (most hurdles, then MAR, then earliest), `bestVariant` (fewest misses, falls back to non-dev trials), `funnel`, `progress` (running best); `families(methods, trials)` aggregates; `trialsByMethod`; `spyForWindow(trial, benchmark)` rebases SPY TR to 1.0 at the trial start on its curve dates; `drawdownSeries(curve)`, `yearlyReturns(curve)` (calendar years).
- `lib/sera/glossary.ts` (pure): `GLOSSARY` / `GLOSSARY_ORDER` plain-language definitions, `CONDITION_TERM`, `STATUS_LABEL` (label, meaning, tone), `INSIGHT_KIND_LABEL`, `SOURCE_KIND_LABEL`.
- `lib/sera/markdown.ts` (pure): `escapeHtml`, `renderInline`, `renderMarkdown`. Escapes all source first, then adds only headings (`#`..`###` -> h3..h5), paragraphs, bold/italic/code, lists, pipe tables and http(s) links; raw HTML always renders as text.
- `lib/sera/fixture.ts`: test builders `GATE`, `trial(over)`, `method(over)`; not for runtime code.
- `components/Nav.tsx`: `Nav({ showSera, showSean, seanOpen })`; the `(app)` layout passes `isSeraUser(user.email)` for both flags, which adds Sean (`Wallet`, above) and Sera (`Telescope`) links at the foot of the desktop rail only (no mobile entry; the phone's Sean way in is `AppHeader`). `seanOpen` (the layout's `openReminderCount()`, owner only) puts a coral dot (`.seanDot`, `aria-hidden`) on the Sean button and adds "· N to do" to its tooltip; non-finite or non-positive values show no dot.
- `components/tooltip.ts`: short tips stay one-line pills; long tips wrap in a box (max 340px); a `\n` in the text forces a line break (`pre-line`).
- `components/sera/charts/`: server-renderable inline-SVG charts, no chart library. `LineChart` (series of `[x, y|null, tip?]` points, numeric or date x, reference lines), `ScatterChart` (points plus shaded regions), `BarChart` (groups; `barGroups` lifts a flat list), `Legend` (`line|dash|dot|ring|zone` shapes). Point and bar tooltips use the shared `data-tip` layer. `scale.ts` is pure and unit-tested.
- `components/sera/diagrams/`: server-rendered inline SVG on a fixed 1240-wide viewBox, no library. `Pipeline({ stages, failLabel, label })` lays `PipelineStage` boxes out by `weight` (SVG text does not wrap, so titles/details arrive pre-broken into short lines; `fails` stages draw a dashed arrow into the journal lane; `final` gets the accent fill). `Windows({ start, devEnd, testStart, today, testNote, paperSince, bears, label })` draws the dev and test bands, the paper strip and `Era` shading over a year axis. `label` is the accessible summary of each diagram. Geometry is pure in `geometry.ts`.
- `app/sera/journal/view.ts` (pure): `KIND_COPY` (caption, empty text, sheet tone per insight kind), `SEEN_COPY` (the unseen/seen divider label, the card marker and its screen-reader text), `parseKind(?kind)` (unknown -> `'all'`), `journalHref`, `newestFirst` (by `added`, then higher id), `kindCounts` (how many of each kind exist in all), `unseenCounts(insights, seen?)` (how many of each kind are unseen, keyed by all seven tabs so `.all` is the total; a seen id not in the snapshot is ignored), `badgeTip(heading, unseen, total)` (the one formatter for the seven tab tooltips — the server render and the client island both call it, so the wording cannot fork), `journalGroups(insights, filter, seen?)` (one group per kind in `INSIGHT_KINDS` order; inside each, unseen entries newest-first, then seen entries newest-first, carried on the group as `unseen` / `seen` / `items` / `unseenCount` alongside the flat `entries` — the seen set defaults to empty, which is "nothing seen yet"), `dayLabel` (UTC). Takes a `ReadonlySet<number>`; never imports `lib/sera/seen.ts` or the database, which is what lets the client island import `badgeTip` from it.
- `lib/sera/seen.ts` (server only; every reader queries Neon): `seenInsightIds()` -> every `insight_id` in `journal_seen` as a `Set<number>`; a failed query resolves to an empty set and logs, never throws, so `/sera/journal` degrades to "nothing seen yet" rather than 500 (invariant 9). `unseenCount(ids)` -> how many of `ids` are *not* in the table, or `null` when the read failed — the rail's number, and the one reader that can tell a failure from a clean zero, which is why `app/sera/layout.tsx` shows no badge on `null`. It takes the ids rather than reading the snapshot itself, so the API route's bundle never pulls `data/lab.json`. `markInsightsSeen(ids, via)` -> one multi-row `INSERT … ON CONFLICT DO NOTHING` (`via` is `'view'` or `'click'`), returning how many rows were new; idempotent, so posting the same id twice leaves one row. Unlike the two reads it does *not* swallow a failure — it throws, and the POST route turns that into its 500. `normalizeSeenIds` / `parseSeenVia` are the shared input guard the route uses, and `MAX_SEEN_BATCH` (500) is the per-request id cap, enforced inside `normalizeSeenIds` rather than by the route.
- `app/sera/journal/seen-client.ts` (pure, DOM-free): the dwell/batch constants in one place (`VISIBLE_FRACTION`, `TALL_VIEWPORT_FRACTION`, `DWELL_MS`, `FLUSH_IDLE_MS`, `MAX_BATCH`, `OBSERVER_THRESHOLDS`, `SEEN_ENDPOINT`), the arithmetic deciding whether an `IntersectionObserver` entry counts as on screen (`isOnScreen`, `isUnseenAttr`), the live badge tally (`badgeCounts`), the request body (`seenRequestBody`) and the pending-id queue (`createSeenQueue`: add, peek, take a batch, remember what is already marked so an id is never posted twice in a session). Unit-tested without a browser (`seen-client.test.ts`).
- `app/sera/ideas/view.ts` (pure): `methodsWithStatus(methods, status)` (numeric-aware id order; page uses `idea` and `blocked-data`), `needs(blockedOn)`, `sourceLabel`, `sourceLink` (http(s) only, else null), `urlParts` (safe flag, host, 72-char display), `readingList(ideasSeen)`: `url:` keys become links newest first, every other key is a concept (`concept:` prefix dropped) grouped by method id, untied last.
- `app/sera/how/view.ts` (pure, takes a structurally narrowed `HowInput`): `stageCounts`, `pipelineStages` / `pipelineLabel` (Pipeline model), `windowsModel` (Windows model; `paperSince` = earliest `updated` of a `paper` method; `asOf` falls back to `gate.testStart` for an empty lab), `hurdles(gate, tries)` (the six `CONDITION_KEYS` in plain words), `honestyRules`, `dataFacts(data, gate)` (has / lacks), `BEARS` (2000-02, 2008-09) and `PAPER_MONTHS = 3` / `PAPER_TRADES = 100` (design section 1's paper bar; not in `snapshot.gate`).
- `auth.ts`: `handlers, auth, signIn, signOut`, `currentUser()`.
- `lib/sean/*`, `app/sean/overview.ts`: see [Sean](#sean-sean-libsean).
- `app/(app)/actions.ts`: server action `dismiss(formData)` (auth check, validates `orderId`, revalidates `/`).

## Data Flow

```
engine (Python, nightly) -> Neon tables -> lib/data.ts (SQL, row -> view model)
                                              |-> pure lib/* (metrics, monthly, strategy, slots, format, decision)
.github/workflows/nightly.yml (cron slots, PAPER_PAUSED) -> lib/decision.ts (mirrored, test-pinned)
                                              -> Today's alarm/waiting sheets, Positions' Standing sheet
                                              -> server components in app/(app)/* -> HTML
engine `lab stage` -> web/data/lab.json (committed) -> lib/sera/lab.ts -> pure lib/sera/derive.ts -> /sera server components
user "Mark as done" -> actions.dismiss -> data.dismissAction -> action_dismissals
reader reads /sera/journal -> JournalSeen (dwell on screen, or arrow click) -> POST /api/sera/journal/seen -> sera/seen.markInsightsSeen -> journal_seen
Sean (phase 1, no route yet): screenshot (or a .zip of them, unzip.readZip) -> readOrder (vision.ts glm-4.6v
  -> extractJson -> order.toOrder, one repair on "unreadable") -> SeanOrder -> [phase 2: sean_orders]
  sean_orders + sean_marks -> ledger.pnlSeries (web) == engine sean/ledger.py -> [phase 4: sean_equity]
/sean (phase 3): data.ledgerOrders + overviewData.equity + overviewData.marks -> app/sean/overview.ts (pnlAt, buildLedger,
  pnlSeries) -> OverviewBody (Stat row, LineChart, holdings table | empty state)
/sean/plan (phase 5): sean_link + book_targets (newest session) + data.ledgerOrders (split at `since`) + sean_marks
  + sean_reminder_marks -> planData.planState -> reminders.buildReminders -> plan page (to do / done, holdings)
  cash (phase 10): OWNER_MONTHLY schedule (dated from sean_link.since) + fx_rates (planData.latestUsdIdr,
    else OWNER_USD_IDR) − the plan's own orders -> cash.cashUsd -> planSize = planValue + cashUsd
    (sean_link.budget_usd overrides); no receipt is ever read for a balance
  owner taps link / settings / done / undo -> plan/actions.ts -> sean_link | sean_reminder_marks -> revalidatePath('/sean', 'layout')
  planData.openReminderCount -> SeanNav Plan badge, Nav rail dot, AppHeader phone dot
journal_seen -> sera/seen.seenInsightIds -> journal/view.ts (unseen counts, unseen-then-seen order) -> the seven badges
             -> sera/seen.unseenCount(lab ids) -> app/sera/layout.tsx -> the SeraNav Journal badge (null = no badge)
```

Pages are async server components; each calls `runStatus()` plus the reads it needs in
parallel (`Promise.all`). Dates are selected as `::text` and sliced to `YYYY-MM-DD` so the server
timezone never shifts them.

Page consumers:
- Today: `champion`, `runStatus`, then `picks` and `positions` only for a picks champion (not benchmark, engine `bracket`); actions are holdings with an `orderId`, a `maxDays` and `day >= maxDays`, not dismissed. The page branches on `pipelineState(run.sessionDate, run.finishedAt, now)`, not on `run.stale`: only `never` and `late` raise the coral alarm (`alarmTitle` / `alarmSub` name which, and print the due and last-retry slots in WIB), while `waiting` renders a calm stone sheet saying the last session has closed and when the next picks are due. `run.stale` alone used to raise the alarm on the ordinary morning after the New York close, hours before the run was due. A `PausedNote` (butter) sits above all of them while `PAPER_PAUSED`; the nav spacer is dropped only for `alarm`, which runs to the bottom edge itself. Any other champion (SPY under D2) shows the no-buys sheet: "Seer recommends no buys", research strategies trade on paper only and their orders live in Positions. `PickCard`'s 'Why this pick' uses the same fallback.
- Positions: `strategies`, `runStatus`, then `positions(strat)` and `pendingOrders(strat)` for `selectStrategy(roster, ?s)`. Pending orders are skipped (empty `Pending`) for the benchmark only — they are now fetched whatever session they are for, so an expired decision can be shown as a record instead of leaving a blank panel. The page then classifies with `lib/decision.ts`: `panel = panelState(pending.sessionDate, pending.decision, now, strat?.status === 'retired')` is this strategy's own decision, `pipeline = pipelineState(...)` is the nightly behind it, and `PAPER_PAUSED` renders a page-level `PausedNote` above both. The live orders sheet shows only for `panel === 'live'`; every other case renders the `Standing` sheet (`standingWords`: retired / `never` / `late` / `spent` / `holding`, with the cadence sentence borrowed from `noOrders()` so the vocabulary lives in one place, and the "next nightly run is due …" line suppressed while paper is paused or the strategy is retired). `panel === 'spent'` with orders additionally renders `SpentDecision`, a stone record of rank, ticker and target weight with every order-ticket field (limit, stop, take-profit, share count, dollar size) and every copy button deliberately absent. Holdings split by `Holding.kind` into `BracketCard` (stop/target range, days), `BookCard` (weight, stop/target only when set) and `BenchmarkCard`; cards keyed by `Holding.key`. The orders sheet lists bracket orders by slot or book targets by rank with weight; empty-state copy depends on engine and `Pending.decision`. A paper-step warning shows when `paperStatus !== 'success'` (failed / running / not yet run). `PaperChip` and a "on paper since" line mark `isPaper` strategies. For a `checksNews` bracket strategy (C) with a pending session it also calls `vetoes(strat, session)` and renders `vetoSheet` as a stone "Vetoed tonight" sheet; each vetoed/failed row reuses `WhyToggle` (new optional `label`/`missing` props) as "Why vetoed" / "Why it failed". Every order row's `WhyToggle` gets `facts={o.evidence}`: it shows the explanation, else the facts as a list, else 'unavailable'; C's 'Why it passed the news check' line follows unchanged. For a book strategy between decisions, `bookPreview` feeds 'would pick now'; each row with stored facts has a 'Why it's on the list' toggle showing them (no LLM). For a split-cadence book strategy (`picksMonthlySizesWeekly(strat.rulesId)`) the empty-state, no-orders and 'would pick now' sentences say it picks its stocks monthly and checks how much to hold weekly (instead of "rebalances on the first session of each month"), and each book order row adds a full-width `SizeCell` ("Against what it holds now", `.cellWide`): `sizeLabel(orderSizeChange(o.weight, pending.equity, o.symbol, heldUsd(book)))` with `sizeTip` as its tooltip, `—` when paper equity is unknown.
- History: `strategies`, `closedTrades`, `runStatus`. Filters are `StrategySwitch` over non-benchmark strategies with an `ALL` button (`?s=`, unknown ids read as all) and win/loss icon buttons (`?o=`); defaults are dropped from the URL. Exit-reason icons cover `tp`, `sl`, `time`, `gap`, `signal` (rules said sell, sold at the open) and `forced` (forced close, no more prices), with a fallback for unknown reasons. Rows keyed by `Trade.key`; each shows the strategy tag (`strategyShort`) and a small `PaperChip` when the strategy is paper or missing from the roster.
- Leaderboard: `leaderboard`, `runStatus`, then `monthly(pick.id, run.sessionDate)`. Every card, chart line and legend entry comes from the roster via `looks`. The big figure is the champion (crowned; SPY today); the second figure is `compare(board.rows).best` — the best research strategy **over the common window** — while the champion is the benchmark, else SPY; with no common window there is no second figure, only `windowLine`'s label. `windowLine` prints under the chart. The checklist and month sheet follow `pick = pickResearch(researchOf(roster), ?s)`; a `StrategySwitch` over research strategies shows when there are two or more (SPY is not selectable here, it is the SPY column). Checklist is `checklist(pick.metrics, spyOverSpan(spy.curve, pick.curve), pick.strategy.gate)` scored by `scoreOf`; the gate's `note` prints under it. "Month by month" lists the since-start row then months newest first, with a `CircleDashed` partial-month marker while the next session is in that month.

## Sera (/sera)

The method lab, shown: every method and trial the lab has run (the 14 historical `H-*` methods
seeded from P7a and every lab `M*` method), with charts and plain-language explanations, the
analysis and opinion on each method, and the insights journal. It is desktop-first. Below
1024 px the pages stack in one column, readable but not designed.

### Routes

| Route | What it shows |
|---|---|
| `/sera` | Overview: the latest `synthesis` insight as the headline (else the latest insight); KPI tiles; every dev trial as max DD vs CAGR minus SPY, with the pass zone shaded; how many trials pass each hurdle; progress over trial number; the luck bar — each trial's DSR against `gate.dsrMin` (0.90 today) with an `N = gate.dsrN` marker whose tip is `gate.dsrNBasis`, and the policy (`all-trials`) named; families; latest methods |
| `/sera/methods` | every method with status, family, source and best variant (CAGR vs SPY, max DD, PF, trades, DSR, conditions passed n/6) and verdict; icon-only filter `?show=all\|lab\|historical\|alive` |
| `/sera/methods/[id]` | one method: idea, what could go wrong, verdict, parent and children, variants against the six conditions, growth of 1 vs total-return SPY, drawdown, year by year, its variants against the gate, the rendered analysis, related insights, each trial's full technical detail. `generateStaticParams` covers every method; unknown id -> `notFound()` |
| `/sera/journal` | insights grouped as Batch summaries (synthesis), What we learned, Ideas worth testing, Data we wish we had, Features to build, Risks we see; `?kind=<kind>` filter (e.g. `/sera/journal?kind=data-wish`). Inside each group, unseen entries come first newest-first, then the seen ones below a divider; each of the seven tab badges counts that tab's unseen entries. See [What the reader has seen](#what-the-reader-has-seen-journal_seen) |
| `/sera/ideas` | the backlog (`idea`, `#backlog`), ideas blocked on data (a data wishlist, `#blocked`), and the reading list from `ideasSeen` (`url:` keys as links, `concept:` keys as tags, `#reading`) |
| `/sera/how` | the pipeline and time-window diagrams, each hurdle with its threshold from `snapshot.gate` (the luck hurdle naming `dsrMin` and the N it is discounted by, `dsrN`, against the total dev tries), the honesty rules, the data the lab has and lacks, and the glossary |

### Access gate

`requireSera(next)` (`lib/sera/gate.ts`) guards every `/sera/**` route on top of the app-wide
`ALLOWED_EMAIL` sign-in. `app/sera/layout.tsx` calls it, and so does every page with its own path,
because a layout is not re-run on client-side navigation. Signed out ->
`redirect('/signin?next=<path>')`; `/signin` honours `?next=` through `safeNext` (`lib/allow.ts`,
internal paths only), so sign-in returns there. Signed in as anyone but `SERA_EMAIL` -> `notFound()`,
so the section's existence is never revealed. `SERA_EMAIL = 'mahfuzh74@gmail.com'` is a constant in
`lib/sera/access.ts`, not an env var; `isSeraUser(email)` matches it trimmed and case-insensitively.
The same check shows the Sera link on Seer's desktop rail (`components/Nav.tsx`).

`requireSera` is for *navigations*. The one `/api/sera/**` route — `POST /api/sera/journal/seen` —
deliberately does not call it: a `redirect('/signin?next=…')` answered to a `fetch` or a
`sendBeacon` would be a 307 that discloses the section exists. It re-derives the same rule from
`isAllowed` + `isSeraUser` and answers `404` to everyone it rejects, revealing nothing.

### Data source and how it stays current

```
skill session (explore / sera) -> lab/lab.sqlite
  -> python -m seer_engine lab stage   (exclusive lock: writes web/data/lab.json, git-adds both)
  -> commit + push main -> CI (engine sync guard, web tsc + vitest) and Vercel production build
  -> lib/sera/lab.ts bundles data/lab.json at build time -> /sera pages (rendered per request, since the gate reads the session)
```

- `data/lab.json` is the `LabSnapshot` contract (`lib/sera/types.ts`): `version`, `asOf`, `gate`,
  `data`, `summary`, `benchmark` (month-end SPY total-return and price, 1993 -> 2015-10-16),
  `methods`, `trials` (with month-end curves), `insights`, `ideasSeen`. It is deterministic: the
  same database always gives the same bytes, and it holds no wall-clock time.
- No human step: every lab commit goes through `lab stage`, so the JSON travels with the database.
  An engine test fails any commit whose JSON differs from `lab export-json` of the committed
  database, and CI runs on `lab/**` as well as `web/**`.
- The web never computes a trading result. It only reshapes and draws the snapshot. Gate
  thresholds come from `snapshot.gate`, never from numbers in web code, and no web test pins a
  threshold's value — moving `DSR_MIN` or `MAX_DRAWDOWN` in the engine must not need a web edit.
  The one deliberate copy is `lib/golive.ts`, which the leaderboard needs outside a server
  component; its test asserts it equals `gate.maxDrawdown`. Where a threshold is baked into a
  stored failure label, the site matches the label by prefix (`lib/sera/derive.ts`) so that
  append-only rows judged under an older bar still read as the same miss.
- The newest `synthesis` insight (written by `/sera-the-explorer` at the end of each batch) becomes
  the Overview headline on the next push; method analyses and insights come from
  `/explore-and-experiment-new-method`, written in plain language with a closing `My opinion:`.


### What the reader has seen (journal_seen)

Lab facts are read-only and come from the snapshot. The single exception in all of Sera is
**reader** state: which Journal entries have been looked at. It lives in Neon, in `journal_seen`
(`db/migrations/012_journal_seen.sql`), modelled on `action_dismissals`: `insight_id bigint`
primary key, `seen_at`, and a `via` column saying how it was marked (`'view'` or `'click'`). No
user column — Seer is one account — and no foreign key: insights live in the engine's SQLite lab
store, not in Postgres, and their ids are append-only and never reused, so there is nothing to
cascade from. `via` is diagnostics only: nothing reads it to decide seen-ness. A row existing is
what "seen" means, so do not build a filter on it.

- **Marked by.** A redirect-arrow click (`via: 'click'`), or the entry dwelling on screen in a
  visible tab for long enough to have been read past (`via: 'view'`) — the five insights with no
  `methodId` carry no arrow, so dwell is the only rule that reaches them. A background tab marks
  nothing. `app/sera/journal/JournalSeen.tsx` observes, `seen-client.ts` holds the policy and the
  queue, and ids are batched and flushed to `POST /api/sera/journal/seen` on an idle debounce, at
  the batch cap, and on page-hide via `navigator.sendBeacon`.
- **Additive and idempotent.** Nothing ever deletes a row or marks an entry unseen; posting an id
  twice is a no-op. There is no "mark all as read" control by design.
- **Counted off the snapshot, not off the table.** Unseen is always `lab.insights` minus the seen
  set — never `count(*)`, never `insights.length - seen.size`. A row may name an id that is not
  in the build's `data/lab.json`, and it must not move a badge.
- **Frozen per page view.** The unseen/seen partition is computed once on the server from the set
  as it stood when the page was requested. Marking an entry seen during a visit changes the
  badges and the card's marker; it never moves a card out from under the reader.
- **Degrades, and the two surfaces degrade differently on purpose.** Nothing ever 500s because
  Postgres is unreachable. `/sera/journal` reads `seenInsightIds()`, whose failed query resolves
  to an empty set: every entry unseen, the page still renders the list. The rail reads
  `unseenCount()`, which returns `null` on a failed read and so shows **no badge** — a bare
  notification number that is wrong is worse than none, while "everything is new to you" is the
  safe reading for a list you are already looking at. The divergence is a decision, not a bug.
- **The rail.** `app/sera/layout.tsx` calls `unseenCount(lab.insights.map(i => i.id))` and passes
  the result to `SeraNav`, so the Journal tab carries a badge on every `/sera/*` page. It is
  computed when the layout renders, so it is a per-load number, not a live one.

## Sean (/sean, lib/sean)

Sean tracks the owner's real Gotrade orders. Every order leaves an "Order Summary" receipt; Sean
reads the screenshot with a vision model, checks the numbers, stores one row per order and (from
later phases) marks holdings to market nightly and shows profit and loss, optionally following one
roster method. Phase 1 is the schema and the pure modules only.

**Schema (`db/migrations/015_sean.sql`, additive; nothing outside Sean reads these):**
- `sean_orders`: one row per receipt. Fee columns are magnitudes (the receipt's +/- sign only
  restates the side). `image_sha256 UNIQUE` dedupes a re-upload of the same file, and
  `UNIQUE (symbol, side, executed_at, shares)` dedupes the same order from two screenshots; the
  image itself is never stored. `executed_at` is the receipt's Date + Time read as WIB. `fills` is
  the partial-fill lines, `raw` the model's JSON for audit, `net_profit_usd` Gotrade's own figure
  (sells only).
- `sean_link`: singleton (`id = 1`) — the one roster strategy Sean follows, `since`, `budget_usd`.
- `sean_reminder_marks`: reminders ticked off by hand, keyed by strategy, session, symbol, action.
- `sean_marks` (engine-written): daily closes for every symbol the owner has held.
- `sean_equity` (engine-written, replaced whole each run): value, cost, realized, unrealized, pnl, fees per NYSE session.

**Modules (`lib/sean/`, pure, relative imports only so vitest loads them without `@/`):**
- `money.ts`: `parseUsd` / `parseUsdParts` (sign and magnitude, `$1,063.886`, `US$`, unicode minus),
  `parseShares`, `parseReceiptDate(date, time)` -> ISO with `+07:00`; `roundHalfUp` matches Python's
  `ROUND_HALF_UP` (with a `toPrecision(15)` step so binary noise cannot turn a tie into a round-down);
  `cents`, `fixed`.
- `order.ts`: `toOrder(raw: unknown)` -> `{ ok: true, order }` or `{ ok: false, kind: 'not_order' |
  'not_filled' | 'unreadable', issues }`. Hand-rolled, no zod: total = amount +/- fees within
  `TOTAL_TOLERANCE_USD` (0.01); amount = price x shares within `AMOUNT_TOLERANCE_USD` + shares x
  `AMOUNT_TOLERANCE_PER_SHARE` (0.005); fills sum to filled shares within `FILL_SHARES_TOLERANCE`
  and average to the price; a fee with the other side's sign is a misread. Issues are worded for
  both the model's repair turn and the owner. Symbol goes through `lib/sera/gotrade-symbol.ts`.
- `prompt.ts`: the model transcribes printed text only (`ORDER_SHAPE`, every value a string);
  `money.ts` does the parsing. `buildRepairNote(issues)` drives the one retry.
- `vision.ts`: one `fetch` to `{LLM_VISION_BASE_URL}/chat/completions` (OpenAI shape, thinking
  disabled, `MAX_TOKENS` 2048), `fetch` injected. `visionConfigFromEnv` returns `null` when a key is
  missing **or the base URL is z.ai's `/anthropic` one**, which answers 200 while dropping the image.
  `tokenFloor(messages, images)` = sent text at 3 chars/token + 150 per image; a reply reporting
  fewer prompt tokens throws `VisionTokenFloorError` and is never read. Measured 2026-10-07: 2,351
  prompt tokens per receipt vs a floor of 1,141, 30/30 receipts read correctly first try.
- `readOrder.ts`: `readOrder(deps, imageB64, budgetMs = READ_BUDGET_MS /* 55 s */)` never throws for a
  model problem; it returns `{ ok: false, code, message, issues, ... }` with `READ_MESSAGES[code]`
  in plain words. Only `unreadable` gets the single repair, and only if `MIN_REPAIR_BUDGET_MS` is
  left; `isReaderDown(code)` (token floor, timeout, transport) separates reader failures (route
  502) from bad pictures (422). `ReadOrderDeps` injects the calls and the clock.
- `ledger.ts`: average cost with fees inside the cost; orders replay by `executedAt` then id, each
  in its New York session (`orderSession`: a 03:30 WIB fill belongs to the previous NY day). A sell
  is clamped to the shares Sean knows about, so selling a position bought before uploads began
  books no phantom profit; dust below `DUST_SHARES` closes a position. Value uses the last close on
  or before the date, else the last order price. Money rounds to cents only at output, so `pnlUsd`
  may differ from realized + unrealized by a cent. `buildLedger`, `pnlSeries`, `pnlAt`.
- `unzip.ts`: `readZip(bytes, { inflateRaw?, accept? })` reads the central directory, stored and
  deflate entries (browser `DecompressionStream('deflate-raw')` by default; tests and the smoke
  script pass `node:zlib`), checks size and CRC-32, skips `__MACOSX/`, `._*`, `.DS_Store`, refuses
  Zip64 and encryption with a plain-words `ZipError`.
- `extractJson.ts`: ported verbatim from run-insights; strips a ```json fence, takes first `{` to last `}`.

**Section (phase 2, owner only).** `app/sean/layout.tsx` gives Sean its own rail (`SeanNav`:
Overview, Trades, Plan; the Plan tab's `planOpen` badge is `openReminderCount()`, phase 5).
Overview (`/sean`) is phase 3 and Plan (`/sean/plan`) phase 5 (both below). `/sean/trades` lists every order (`orders()`,
newest first, `null` on a failed read so the page says so) with a per-row delete
(`DeleteOrder` -> `deleteOrder` server action), and `Uploader` takes screenshots or a zip
(unzipped in the browser by `lib/sean/unzip.ts`), re-encodes large or non-JPEG pictures to JPEG
(`upload.ts`: long side <= `MAX_SIDE_PX`, cap `MAX_UPLOAD_BYTES` 1.5 MB), sends them `CONCURRENCY`
(3) at a time, then calls `refreshPnl()`. `view.ts` holds the plain-words strings (`SAY`) and
`readResponse(status, body)`. The way in is an icon button: `Nav` (`showSean`, desktop rail foot,
above Sera) and `AppHeader` (phone only); `(app)/layout.tsx` shows both to the owner only.
- `lib/sean/gate.ts`: `requireSean(next)` — signed out -> `/signin?next=`, anyone but the owner
  (`ALLOWED_EMAIL` and `isSeraUser`, Sera's exact rule) -> 404; every page calls it itself.
  `isSeanCaller()` is the same check as a boolean for routes and server actions (no redirect).
- `lib/sean/data.ts` (server only, Neon): `orders`, `ledgerOrders()` (oldest first, `executedAt`
  ISO with `+07:00`, shaped for `buildLedger`/`pnlSeries`/`pnlAt`; throws on failure),
  `ownerSymbols`, `orderById`, `orderIdBySha`, `saveOrder(order, sha, raw)` -> `{ id, duplicate }`,
  `removeOrder`.
- `POST /api/sean/orders`: body `{ image: base64 JPEG, sha256 }`; the server re-hashes the bytes
  and refuses a mismatch. Known sha -> 200 `{ order, duplicate: true }`; otherwise `readOrder` on
  the vision model, then `saveOrder`. 201 new, 400 damaged, 413 too large, 422 not a filled
  receipt, 502 reader missing/down, 500 save failed, 404 to anyone but the owner.
  `maxDuration = 60` (must stay a literal).
- `lib/sean/dispatch.ts`: `dispatchSeanMarks()` POSTs a `workflow_dispatch` for `sean.yml` on
  `main` so marks and P&L catch up before the nightly. Best effort, never throws: no
  `GITHUB_DISPATCH_TOKEN`, a 404 (workflow not on main yet) or any error returns `false`.

**Overview (phase 3, `/sean`).** `app/sean/page.tsx` (`force-dynamic`, `requireSean('/sean')`)
reads `ledgerOrders()`, `equity()` and `marks()` in parallel and passes them, with today as a New
York date (`orderSession(now)`), to `overview()`; `OverviewBody` renders the result with Sera's
`Section`, `Stat`, `LineChart` and `Legend` (styles in `overview.module.css`).
- `lib/sean/overviewData.ts` (server only, Neon): `equity()` -> `EquityRow[]` (`date`, `valueUsd`,
  `costUsd`, `realizedUsd`, `unrealizedUsd`, `pnlUsd`, `feesUsd`; empty until the engine's
  `sean marks` runs); `marks()` -> `LatestMark[]` (`DISTINCT ON (symbol)`, newest close). Both throw
  on a failed read. `overview.ts` only `import type`s from it.
- `app/sean/overview.ts` (pure, relative imports only): `overview({ orders, equity, marks, today })`
  -> `{ empty: true }` with no orders, else `{ orderCount, firstDay, stats, chart, holdings, total,
  closed }`. All money math is the shared ledger's (`pnlAt` for "now", `buildLedger` for open
  positions, `pnlSeries` for the fallback line); this module only picks and words numbers.
  - `stats(now, sorted)`: five tiles — total, realized, unrealized, fees paid, fees as a share of
    money traded (sum of `amountUsd`) — each with a plain-words `sub` and `tip`; `toneOf` colours
    only gains and losses.
  - `holdings(sorted, marks)`: open positions priced at the latest close, else the owner's last
    order price (`estimate: true`, tooltip says so), biggest value first, plus `total` and the
    `closed` symbols sold out of.
  - `pnlChart(...)`: `source: 'nightly'` draws `sean_equity` and, when an order is newer than its
    last session, appends a `live` point for today; with no `sean_equity` rows it falls back to
    `source: 'orders'` (the ledger on each trade date, at order prices). Two series (P&L solid,
    cumulative fees dashed), a break-even ref line, `monthTicks` x-axis, a one-week `xDomain` for a
    single-day series, dots up to 40 points.
  - Formatters: `usdText`, `signedUsdText`, `pctText`, `signedPctText`, `sharesText`, `priceText`,
    `usdTick`, `dayText`, `monthYearText`, `orderDay`, `round2` (true minus sign `−`).
- `OverviewBody({ v })`: empty state is a "No trades yet" sheet with one icon-only link to
  `/sean/trades` (`TRADES_HREF`); otherwise the P&L section (stats over the chart) and a holdings
  table.

**Plan (phase 5, `/sean/plan`).** Sean can follow one roster method and remind the owner what to
buy and sell to copy it. `app/sean/plan/page.tsx` (`force-dynamic`, `requireSean`) loads
`planState()` and `linkableMethods()` in parallel; with nothing followed it shows `LinkPicker`,
otherwise the method, its newest picks (`picksLine`), the to-do reminders (each with an icon-only
"done" button), the done ones (with undo when the owner marked them), the plan's holdings, stocks
held from outside the plan, `PlanSettings` and an unlink button.
- `lib/sean/reminders.ts` (pure, relative imports only): `buildReminders(input: ReminderInput) ->
  ReminderPlan` (`planValue`, `planSize`, `holdings`, `reminders`, `open`, `done`). The plan is the
  orders whose New York trade date (`orderSession`) is on or after `sean_link.since`
  (`planOrders`), run through the one ledger (`sharesBySymbol`); everything bought before is
  `outsideShares` and is never sold by Sean. Rules: **sell** the whole plan position of a stock the
  picks no longer name; **buy** a pick the plan does not hold, `weight × planSize` dollars (no amount
  without a plan size); **add / trim** only when `resizes(rulesId)` (the `RESIZING_RULES` mirror of
  the engine's `resize=True` presets), measured at the pick's decision price, and only when the gap
  is at least `max(MIN_TRADE_USD` ($25, derived — see Gotchas), `RESIZE_BAND × planSize)`; no picks at
  all -> no reminders.
  Order: sells, trims, buys, adds. A reminder is **done** (`'order'`) when an uploaded order of the
  same side and stock has a NY trade date on or after the decision session, or (`'mark'`) when the
  owner marked it for that decision. **`planSize` is holdings plus cash**: `budgetUsd` when the owner
  set one, else `planValue + cashUsd`, else `planValue` alone when the wallet cannot be derived (what
  this did before phase 10), else null and buys carry no amount. `cashUsd` comes in from `./cash` and
  is passed back out on the `ReminderPlan` for the page; it may be negative. Every amount is in
  dollars and Sean never asks for a share count: prices drift between the decision's close and the
  next open, and a fractional-dollar order absorbs that drift where a share count does not (the
  roster's book rules are already `-frac`).
  Keys are `${sessionDate}:${symbol}:${side}`.
- `lib/sean/cash.ts` (phase 10, pure): the wallet, **derived, never read**. A Gotrade receipt has no
  balance printed on it, so no code path reads one and `lib/sean/ledger.ts` is unmodified. `cashUsd({
  schedule, through, usdIdr, orders })` = `depositedUsd` − `netSpentUsd`, each to the cent: the
  contribution schedule from `sean_link.since` through today's New York date (`orderSession`, the same
  calendar plan membership is counted in), less what the plan's own orders took out (buys out, sells
  in, fees already inside `totalUsd`) over the SAME `planOrders(all, since)` slice the reminders use.
  `OWNER_MONTHLY` is the owner's own plan — 10,000,000 IDR to start, +5,000,000 IDR on `dayOfMonth` 25
  (1–28, so every month has the day) — and carries **the engine's name on purpose**
  (`engine/src/seer_engine/sim/contributions.py`), so one `grep -rn OWNER_MONTHLY` finds both halves of
  the one schedule. `OWNER_USD_IDR` (17,841) is the rate the owner's real 10,000,000 IDR was actually
  converted at, a fallback only. A schedule self-corrects where a number precomputed into
  `budget_usd` cannot: the orders he uploads are subtracted from the same deposits, so next month's
  cash is right even when his fills diverged from the plan. The wallet is left negative rather than
  clamped — below zero means the schedule and the uploaded orders disagree, and hiding that would be
  worse than showing it. Also `depositDates` / `depositedIdr` / `depositedUsd` / `netSpentUsd`.
- `lib/sean/planData.ts` (server only, Neon; untested by design, the logic is in `reminders.ts`):
  `linkableMethods()` (active, `engine = 'book'`, not benchmark, with `lastPick`), `link()`
  (`sean_link` joined to `strategies`; `retired` when the method left the roster),
  `latestTargets(id)` (`book_targets` at its newest session, `pending` from `paper_state`),
  `reminderMarks`, `latestCloses(symbols)` (newest `sean_marks` close; named apart from phase 3's
  `marks()`), `latestUsdIdr()` (the newest `fx_rates` row, falling back to `cash.ts`'s `OWNER_USD_IDR`
  so a missing row costs accuracy and never the page), `planState()` (null when nothing is followed; a
  retired method yields no picks; it derives the wallet with `cashUsd` and hands it to
  `buildReminders`), and
  `openReminderCount` — React-`cache`d so `(app)/layout.tsx`, `AppHeader` and `app/sean/layout.tsx`
  share one `planState()` per request, returning 0 when nothing is followed **or anything throws**.
- `app/sean/plan/actions.ts` (server actions, each gated by `isSeanCaller()`): `linkMethod(prev,
  formData)` with `op = 'link'` (upserts the singleton, re-checking the method is an active
  non-benchmark book method) or `'edit'` (since and budget only), returning a `FormState`;
  `unlinkMethod()` (done marks are kept, keyed by method and decision); `markDone` / `undoDone`
  (insert / delete a `sean_reminder_marks` row for the followed method). All revalidate
  `/sean` as a layout so the badge refreshes.
- `app/sean/plan/view.ts` (pure, tested): `FormState` messages (`IDLE`, `SAVED`, `BAD_DATE`, ...),
  input guards `parseSince`, `parseBudget` (empty -> null, cap `MAX_BUDGET`), `parseSymbol`,
  `parseSide`, and the plain-words strings (`reminderTitle`, `reminderDetail`, `doneLine`,
  `picksLine`, `nextPickWords` via `cadenceOf(rulesId)`, `methodTitle`, `aboutUsd`, `todoLabel`, ...).
  `planSizeLine(planSize, budgetUsd, cashUsd)` and `cashLine(planSize, cashUsd, budgetUsd)` word the
  stocks-plus-cash split; both fall back (or go quiet) when the owner set a budget, since then the
  split would be a guess, and both print cash through `signedUsd` when it is negative because `usd`
  takes an absolute value. The page's middle tile is **Plan size** — what the picks are sized against
  — not the old "Plan value", with `cashLine` beneath it.
- `LinkPicker` / `PlanSettings` (client, `useActionState(linkMethod)`): the picker's start date
  defaults to the method's newest pick, so orders placed to follow it count.
- The way the owner notices: `Nav` (desktop rail) and `AppHeader` (phone) put a coral dot on their
  Sean button when `openReminderCount() > 0`; both read it only for the owner.

## Dependencies

- `next` 16, `react` / `react-dom` 19: app router, server components, server actions.
- `next-auth` 5 (beta) with the Google provider: sign-in, JWT sessions.
- `@neondatabase/serverless`: `neon()` HTTP tagged-template `sql` for the app; `Pool` over websockets (`ws`) for the scripts, which need transactions.
- `lucide-react`: icons (every button is icon-only with `aria-label` and a tooltip).
- Dev: `typescript`, `vitest`, `ws`.
- Internal: shares `db/migrations/*.sql` and `schema_migrations` with the engine; the engine owns writes to every table except `action_dismissals` and `journal_seen` (`db/migrations/012_journal_seen.sql`), which only the web app writes. Sean (`015_sean.sql`) splits the same way once its later phases land: the web writes `sean_orders`, `sean_link`, `sean_reminder_marks`; the engine writes `sean_marks`, `sean_equity`.
- External (Sean): a glm-4.6v vision endpoint over plain `fetch`, no SDK.

## Concurrency

No shared mutable state. Each request runs its own parallel queries; both writes
(`action_dismissals`, `journal_seen`) are idempotent `INSERT ... ON CONFLICT DO NOTHING`, so a
retried beacon or two tabs flushing the same ids cost nothing. Not a concern beyond that.

## Error Handling

No custom error types. DB errors propagate to Next's error boundary — with one deliberate
exception, the Journal's seen state. Its two reads swallow a failed query (`seenInsightIds` to an
empty set, `unseenCount` to `null`) so neither `/sera/journal` nor the `/sera` layout can 500 over
a badge, and its write is fire-and-forget from the browser: a failed POST is never surfaced, the
ids are requeued, and the badge stays optimistically counted down. `markInsightsSeen` itself does
throw, which the route answers as a bodiless 500 the island ignores. `dismiss` throws on a
missing session or a bad order id. `seed-demo.mjs` throws (and writes nothing) when real engine
runs exist, more than 100 bars exist (backfill ran), or real paper state exists, and when its
window lacks two month starts.

## Configuration

- `DATABASE_URL` (app, pooled HTTP), `DATABASE_URL_UNPOOLED` (scripts), `ALLOWED_EMAIL`, NextAuth Google credentials. Scripts read `web/.env.local` via `node --env-file`.
- Sera needs no env var of its own: `SERA_EMAIL` is a constant (`lib/sera/access.ts`), and its lab data is the committed `data/lab.json`. It does share the app's `DATABASE_URL`, for `journal_seen` only. Regenerate the JSON with `python -m seer_engine lab stage` (writes and stages it with `lab/lab.sqlite`) or `lab export-json` (writes only). In a worktree, run them as `env -u SEER_LAB_DB PYTHONPATH=<worktree>/engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine …`.
- Sean's reader: `LLM_API_KEY`, `LLM_VISION_BASE_URL` (OpenAI-shaped; never z.ai's `/api/anthropic`), `LLM_VISION_MODEL` (glm-4.6v), set in Vercel; read by `/api/sean/orders` (missing -> 502). `GITHUB_DISPATCH_TOKEN` (optional) lets `dispatchSeanMarks` start `sean.yml`.
- `npx vite-node scripts/sean-vision-smoke.mjs -- <zip | folder | image ...> [--truth <json>] [--env .env.local] [--limit N]` (from `web/`): runs the real `readOrder` against real screenshots, prints prompt tokens vs the floor, tries and seconds per picture, and with `--truth` compares every field to a hand-checked transcription; exits 1 on any failure. Spends tokens; never in CI. Re-run it after any change to `prompt.ts`.
- `npm run db:migrate`: apply new migrations in name order, one transaction each.
- `npm run db:seed-demo [-- --dry-run]`: builds a 66-session demo (day 0 + paper start, at least three calendar months) ending at the last completed session, flagged `is_demo`. Roster: SPY (champion, buy and hold), A (bracket), F4-MOM12-N20-TREND and F1-SPY-SMA200-M (monthly book strategies, deciding on each month's first session), and C (bracket, its own younger clock, gate `applicable: false`). Needs migrations through 009 applied first (`npm run db:migrate`, then `npm run db:seed-demo`; it only runs on an empty database, never production). Writes strategies (with `engine`, `rules_id`, `paper_start`, `params.backtest_gate`), runs (with paper status), fx, bars, orders, equity snapshots, `paper_state`, `book_positions`, `book_targets` and `book_previews` (pending orders, targets and previews with demo `evidence`; A's CSCO has no explanation so its facts show), `book_trades`, and six `news_vetoes` rows for C's pending session. `--dry-run` builds every row and prints counts without connecting.
- `npm test`: vitest over the pure modules (`strategy`, `metrics`, `vetoes`, `monthly`, `slots`, `session`, `format`, `allow`, `why`, `sera/*`), `components/roster`, `components/sera/charts`, `components/sera/diagrams/geometry`, `app/(app)/leaderboard/view`, the `app/sera/*/view` helpers, `app/sera/journal/seen-client`, `lib/sean/*` (receipts and ledger fixtures included; no network) and `app/sean/overview` / `OverviewBody`, `app/sean/plan/view` (`lib/sean/reminders` is among `lib/sean/*`).

## Gotchas

- `Trade.id` and `Holding.orderId` are per-table ids; use `key` for React keys and cross-engine identity.
- Only bracket holdings have `orderId`, `slot` and `maxDays`; book `tp`/`sl` may be null. Do not assume a stop/target range exists.
- `slotCount` is 0 for book and benchmark strategies: only bracket strategies fill the S-E-E-R slots.
- The gate defaults to not passed, so the checklist reads 5/6 at best until the engine's `paper` command writes `backtest_gate.passed = true`.
- C's gate is `applicable: false`: its checklist reads 5/6 at best forever, and the score line says real money needs an owner decision (D9).
- Positions for C shows "Vetoed tonight" for the pending session. No rows there means A had no candidates or the news check did not run; the app cannot tell which (`noCheckLine`).
- `runStatus` mixes two runs: freshness from the latest successful run, `latestStatus`/`paperStatus` from the most recent run of any outcome.
- `panelState`'s fourth argument (`retired`) defaults to `false`, but it is not optional at the call site — `app/(app)/positions/page.tsx` passes `strat?.status === 'retired'`. Drop it and a superseded entry renders a live order ticket on the night its successor starts: a retired strategy's `pending_session` can still be the coming session, and those `book_targets` and `orders` rows are deliberately kept as the record of a decision that was made and never acted on. The page is the only thing between them and the owner's order ticket.
- `NIGHTLY_SLOTS_UTC`, `NIGHTLY_DAYS_UTC` and `PAPER_PAUSED` in `lib/decision.ts` are hand mirrors of `.github/workflows/nightly.yml`, like `SPLIT_CADENCE_RULES` mirrors the engine presets. `decision.test.ts` reads the workflow file and fails on drift, so change the cron or un-pause the paper step there first — never only in the TypeScript.
- Do not branch a page on `run.stale` for anything the owner reads as an alarm. It is true from the New York close until the next nightly finishes, which is most of the owner's waking day; `pipelineState` is the one that can tell "not due yet" (`waiting`) from "missed its last retry" (`late`).
- `lib/decision.ts` never re-derives whether tonight is a decision session. It reads the engine's recorded `paper_state.pending_decision`: the boundaries are NYSE trading sessions and the web package has no trading calendar (`lib/session.ts` models weekends only).
- Leaderboard win rate and trade counts only use the strategy's own engine's trade table; SPY has no trades.
- The Leaderboard never says "Ready for real money" unless all six checklist items pass (`scoreOf`); a missing gate yields no items and a 0/6 "Paper only" line.
- The Leaderboard never ranks on raw total return: with promotable strategies the paper starts differ, so `compare` ranks only over the sessions the live strategies share and `windowLine` always says which. `MIN_COMMON_SESSIONS` / `MIN_RANKED` and the rank key must stay equal to `engine/src/seer_engine/paper/compare.py`'s — the port is only honest while it tracks the engine.
- A retired strategy is excluded, not hidden: it keeps every snapshot, its card, its chart line and its month sheet, and is dropped only from the window and from "best", so a retirement can never shorten the living strategies' comparison.
- Seer ships paper-only (2026-10-04): `isPaper` strategies are research, never a buy recommendation. Today never shows their orders; Positions and History mark them with `PaperChip`.
- `RESIZE_BAND` in `lib/cadence.ts` must equal the engine's `RESIZE_BAND` (`engine/src/seer_engine/sim/rules.py`), and `SPLIT_CADENCE_RULES` must list every split-cadence `rules_id`; a new variant missing there falls back to the monthly-rebalance wording and loses its size cell. The page's dollar figures are estimates at tonight's marks, not the engine's fill sizes.
- Positions defaults to the first research strategy, not the champion: with SPY as champion, `selectStrategy` skips the benchmark unless `?s=` asks for it.
- `StrategySwitch` takes `href` as a function, so it must stay a server component (functions cannot cross into a client component).
- Sera access is two locks: sign-in still needs `ALLOWED_EMAIL`, and `/sera` additionally needs `SERA_EMAIL` (hard-coded). Any other signed-in account gets a 404, not a denial page, by design.
- Every `SeraNav` destination now has a page (`/sera`, `/sera/methods`, `/sera/journal`, `/sera/ideas`, `/sera/how`); each page also calls `requireSera(<its path>)` so sign-in returns to it.
- `/sera/journal` and `app/sera/layout.tsx` are the only Sera code that reads Neon, and only for `journal_seen`. Neither may throw: the layout wraps every `/sera` page, so a thrown seen-state read takes down the whole section over a badge. The page uses `seenInsightIds()`, which swallows its query failure and degrades to "nothing seen yet"; the layout uses `unseenCount()`, which returns `null` on failure so the rail shows no badge rather than the full inventory. Use `unseenCount` for anything that is just a number — an empty `Set` cannot tell you the read failed.
- Unseen is always `lab.insights` minus the seen set. Never `SELECT count(*) FROM journal_seen` and never `insights.length - seen.size`: a row can name an id that is not in this build's snapshot (the table is in Neon, the snapshot is bundled at build time), and the rail's badge must agree with the seven on the page.
- The rail's Journal badge is computed when the Sera layout renders. A soft client-side navigation inside `/sera` does not re-run the layout, so the rail number does not refresh mid-visit — the Journal page's own seven badges are the live ones, counted down by `JournalSeen`. A zero count renders no rail badge at all, while the Journal's seven keep a muted zero pill to keep the row even.
- The two seen-state caps are different things and cannot share a constant: `MAX_SEEN_BATCH = 500` (`lib/sera/seen.ts`, server-only — it builds the Neon client at module scope) is the per-request id cap, enforced inside `normalizeSeenIds`; `MAX_BATCH = 50` (`seen-client.ts`) is the client's flush trigger. The invariant is `MAX_BATCH <= MAX_SEEN_BATCH`. Raise the client past 500 and every full flush becomes a **silent** 400 — the route answers with no body and the island swallows failures, so nothing would ever be marked seen and nothing would say so.
- The POST route parses its body with `JSON.parse(await req.text())` and ignores `Content-Type` on purpose: `navigator.sendBeacon` sends a `Blob` typed `text/plain`, so narrowing the route to `application/json` would silently break every page-hide flush.
- `Pipeline` uses fixed SVG marker ids: render at most one per page. Its stage text must be pre-broken (title lines <= 14 chars, detail <= 18, <= 26 on a weight-1.35 box) or it overflows the boxes.
- `data/lab.json` is generated. Never edit it by hand or commit it without its database: the engine sync guard fails the build. A lab change reaches `/sera` only by being committed and pushed, because the snapshot is bundled at build time.
- `lib/sera/*` and the page helper modules import each other relatively: vitest has no `@/` alias. Only `page.tsx` files and components use `@/`.
- Sera's markdown renderer escapes HTML first. Analysis text is never trusted as HTML.
- Read `evidence` only as `to_jsonb(<row>) -> 'evidence'`, never as a plain column: Vercel deploys on push, hours before the nightly applies 009, and a named missing column fails the whole query. The facts are rendered verbatim, so they must stay plain English (the engine's evidence module owns the wording).
- Sean's ledger exists twice: `lib/sean/ledger.ts` and the engine's `seer_engine/sean/ledger.py` (phase 4). Both must pass `lib/sean/fixtures/ledger.json`; change the math in one and you change it in the other. `roundHalfUp` is what keeps their cents equal.
- Sean's realized profit is not Gotrade's "Net Profit": Gotrade leaves buy fees out of its basis. Keep both; never reconcile one to the other.
- Sean never stores a screenshot. `image_sha256` and the `(symbol, side, executed_at, shares)` key are the only dedupe.
- `lib/sean/vision.ts` and `readOrder.ts` take their config and `fetch` as arguments and never read a server env module, so they stay importable from vitest and the smoke script; keep the server-only part in the (phase 2) route.
- `RESIZING_RULES` in `lib/sean/reminders.ts` is a hand mirror of the engine presets with `resize=True` (`engine/src/seer_engine/sim/rules.py`), like `SPLIT_CADENCE_RULES`; a resizing preset missing there silently gets no add/trim reminders. Its size band is `lib/cadence.ts`'s `RESIZE_BAND`.
- `OWNER_MONTHLY` in `lib/sean/cash.ts` is a hand mirror of the engine's contribution schedule
  (`engine/src/seer_engine/sim/contributions.py`), the way `RESIZING_RULES` mirrors `sim/rules.py`. It
  carries the engine's name deliberately so one `grep -rn OWNER_MONTHLY` finds both halves; change the
  amounts, the day of the month, or the rule that a deposit is dated on its calendar day in one place
  and you must change the other. The one difference is on purpose: the engine lets the NYSE calendar
  decide which session first spends the money, while Sean reports the wallet, where money counts from
  the day it lands.
- `MIN_TRADE_USD` is derived, not picked: `trading_min / (2 × trading_rate)` from the engine's own fee
  constants (`sim/costs.py`; currently 0.10 and 0.002, so $25) — the point where the $0.10 floor stops
  more than doubling the trading fee. Its comment states the derivation, not the number; if a fee
  constant moves, redo the arithmetic instead of guessing a round number. Not $50 (where the floor
  stops binding at all): an add's gap can never exceed its own slot, and the owner's slot is $41.91,
  so a $50 floor would make an add structurally impossible rather than merely expensive.
- `openReminderCount()` runs inside `(app)/layout.tsx`, which wraps every Seer page: it must never throw (it returns 0), and it relies on React `cache` so the layout and `AppHeader` do not each run `planState()`. A reminder only clears from an uploaded order dated on or after the decision session, so an order placed earlier needs a hand "done" mark.
- The paper bar (3 months, 100 trades) on How it works is a constant in `app/sera/how/view.ts`, not snapshot data; change it there if design section 1 changes.

## Notes

Documentation Created: 2026-10-04 (P1-WEB-Y9MV). Before this phase the data layer was
bracket-only (`Position` with non-null `tp`/`sl`, `Trade` keyed by order id, a five-item
checklist); this phase widened it to the bracket, book and benchmark engines of migration 003.
