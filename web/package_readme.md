# Package: seer-web

**Location**: `web` (Next.js app router; package name `seer-web`, private)
**Last Updated**: 2026-10-04 (P1-WEB-DX8D, paper-trading-ship phase 12: roster-driven Leaderboard with SPY crown, per-research-strategy six-item checklist via `StrategySwitch` with an honest score line, and a "Month by month" sheet; helpers in `leaderboard/view.ts`)

## Overview

`seer-web` is Seer's private web app: a Next.js 16 / React 19 front end that reads the Neon
(Postgres) tables written by the Python engine (`engine/`) and shows tonight's picks, open
holdings, closed trades and the strategy leaderboard. It never trades and never computes
signals; it is a read model over `strategies`, `runs`, `orders`, `book_positions`,
`book_targets`, `book_trades`, `equity_snapshots`, `paper_state`, `bars` and `fx_rates`, plus one
write (`action_dismissals`).

**Key Responsibilities:**
- Google sign-in locked to exactly one allowlisted account (`auth.ts`, `lib/allow.ts`)
- One data layer (`lib/data.ts`) that turns rows of all three engines (`bracket`, `book`, `benchmark`) into typed view models
- Pure, DB-free logic that tests run without a connection: metrics and the go-live checklist (`lib/metrics.ts`), month-by-month paper performance (`lib/monthly.ts`), strategy row helpers (`lib/strategy.ts`), slot letters and card colours (`lib/slots.ts`), session freshness (`lib/session.ts`), number/date formatting (`lib/format.ts`)
- Four pages: Today, Positions, History, Leaderboard
- Shared roster UI (`components/StrategySwitch.tsx`, `components/PaperChip.tsx`, `components/roster.ts`): icon-only strategy switching by `?s=` and the paper marker on research strategies' holdings, orders and trades
- Migrations runner shared with the engine (`scripts/migrate.mjs`) and a demo seeder (`scripts/seed-demo.mjs`)

## Layout

```
web/
  package.json              scripts: dev, build, start, test (vitest), db:migrate, db:seed-demo
  next.config.ts, tsconfig.json, vercel.json (region sin1)
  auth.ts                   NextAuth (Google, JWT sessions), currentUser()
  app/
    layout.tsx, globals.css, manifest.ts, icon.svg, apple-icon.tsx
    signin/                 sign-in / denied page
    api/auth/               NextAuth route handlers
    (app)/
      layout.tsx            signed-in shell
      actions.ts            server action dismiss(formData)
      page.tsx              Today: champion's picks + day-5 bracket actions; no-buys state for a SPY/non-bracket champion
      positions/page.tsx    any strategy's holdings (?s=), cards by Holding.kind, next-session paper orders, paper-step warning
      history/page.tsx      closed trades of both engines, filter by research strategy (?s=) and win/loss (?o=)
      leaderboard/page.tsx  roster-driven equity curves, champion crown, per-strategy go-live checklist (?s=), month-by-month sheet
      leaderboard/view.ts   looks, researchOf, bestResearch, scoreOf, monthLines, sinceStartLine  (pure)
      leaderboard/view.test.ts  vitest suite for view.ts
  components/               AppHeader, Nav, CopyButton, RefreshButton, WhyToggle, TooltipLayer, tooltip
    StrategySwitch.tsx      icon-only roster switcher (Links), ALL sentinel           (server component)
    PaperChip.tsx           "Paper" data label with tooltip, sm | md
    roster.ts               strategyIcon, selectStrategy, sharesLabel                (pure)
    roster.test.ts          vitest suite for roster.ts
  lib/
    db.ts                   sql = neon(DATABASE_URL)
    data.ts                 all DB reads (server only)
    strategy.ts             Engine, Gate, engineOf, parseGate, shortLabel, checksNews (pure)
    metrics.ts              Snapshot, Metrics, strategyMetrics, gateItem, checklist (pure)
    vetoes.ts               Verdict, Veto, parseVerdict, vetoSheet, checkedLine, headlinesLabel, noCheckLine (pure; P6)
    monthly.ts              monthlyTable, monthOf                                  (pure)
    slots.ts                slot letters/sheets, slotCount, cardBg                 (pure)
    session.ts              nextUsSession, isStale, wibDate                        (pure)
    format.ts               money/usd/rp/pct and date formatters                   (pure)
    allow.ts                isAllowed                                              (pure)
    *.test.ts               vitest suites for every pure module
  scripts/
    migrate.mjs             applies ../db/migrations/*.sql once each (schema_migrations)
    seed-demo.mjs           demo data in the paper-trading shape; --dry-run
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
- `checklist`: design §1 go-live rules, **six** items, all must hold: >= 3 months forward, >= 100 trades, beats SPY, profit factor >= 1.3, max drawdown <= 15%, and **Backtest gate passed** (from `gate`; carries `note` when the roster gives one). The gate parameter is required. Row 6 is `gateItem(gate)`: for a not-applicable gate it reads `{ label: 'Backtest gate', val: 'Not applicable', ok: false }` (plus the note), so such a strategy never passes all six.

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

### lib/data.ts (server only; every function queries Neon)

Types:
- `Strategy`: `id, name, sub, icon, isChampion, isBenchmark, engine, rulesId, paperStart, gate, isPaper, short, checksNews`. `isPaper` = neither champion nor benchmark (research strategy, never a buy recommendation). `paperStart` is null until the engine's `paper` command starts the clock. `checksNews` (P6) marks C, whose Positions view reads its verdicts.
- `RunStatus`: `sessionDate, dataDate, finishedAt, isDemo, stale, usdIdr` from the latest **successful** run (IDR falls back to 16500), plus `latestStatus, paperStatus, paperError, paperFinishedAt` from the most recent run whatever its outcome. `RunState = 'running' | 'success' | 'failed'`.
- `Pick`: a champion's pending bracket order for Today (unchanged shape).
- `Holding` (replaces the old `Position`): one open holding of any engine. `key` is unique across engines (`'o:<orders.id>'` or `'b:<strategy>:<symbol>'`); `kind: Engine`; bracket-only `orderId`, `slot`; `tp`/`sl` nullable (book sets them only when its rules do); `maxDays` is 5 for bracket, null otherwise; `weight` = value / last equity; `pnl`/`pnlPct` for book include fees and dividends (`value + income - cost`); `dismissed` (bracket day-5 action done); `exitPending` (book sell decided for the next open).
- `PendingOrder` / `Pending`: what a strategy will do at the next session. Bracket: pending orders (`rank` = slot, whole `shares`). Book: `book_targets` of the pending decision (`weight` in (0,1], `shares` null). `Pending.decision` is false for SPY and for book strategies whose next session is not a decision session.
- `ExitReason = 'tp' | 'sl' | 'time' | 'gap' | 'signal' | 'forced'`.
- `Trade`: closed trade of either engine. `key` unique across engines (`'o:<id>'` / `'b:<id>'`); `id` is unique only within its own table; `kind`, `strategyShort`, nullable `shares` (book keeps none) and `days`.
- `Board`: `{ rows: { strategy, metrics, curve }[]; from; to }`.
- `BRACKET_MAX_DAYS = 5` (design §5).

Functions:
- `strategies(): Promise<Strategy[]>` ordered by `sort, id`; `champion(): Promise<Strategy | null>`.
- `runStatus(now?): Promise<RunStatus>`.
- `picks(strategyId, sessionDate): Promise<Pick[]>`: pending bracket orders for one session.
- `positions(strategyId): Promise<Holding[]>`: bracket orders (days held desc, slot) then book positions (value desc). Equity for `weight` comes from `paper_state`, else the latest snapshot.
- `pendingOrders(strategyId): Promise<Pending>`.
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
function researchOf<T extends RosterIn>(roster: T[]): T[];          // non-benchmark rows
function bestResearch<T>(rows: { strategy: T; metrics: { totalReturn: number | null } }[]): { strategy: T; ret: number } | null;
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

- `looks`: research strategies take the design's sheet/line pairs (`CARD_BGS` lav/sky/stone/butter, `LINES` ink/line-b/line-c/coral) in roster order, cycling sheets past four; the champion's line is thicker (2.75). The benchmark is a dotted `--ink-3` line on a plain sheet. No hardcoded A/B/C ids.
- `bestResearch`: highest `totalReturn` among non-benchmark rows that have one.
- `scoreOf`: `ready` only when exactly six items are given and all pass; lines are "All six pass. / Ready for real money", else "Paper trading until / all six pass" when the gate passed, else "Paper only. / Backtest gate not passed". A not-applicable gate (C) is never ready and reads "Paper only. No backtest gate. / Real money needs an owner decision" (handover D9).
- `monthLines` / `sinceStartLine`: format `lib/monthly.ts`'s `MonthlyTable` (Return toned pos/neg, SPY, Trades, Worst drop; `—` for nulls); the since-start row is labelled `Since <monthDay(from)>`.

### Other modules

- `lib/session.ts`: `nextUsSession(now)`, `isStale(latestSessionDate, now)`, `wibDate(now)`. Weekends only; holidays are the engine's job.
- `lib/format.ts`: `money, usd, signedUsd, rp, signedRp, pct, signedPct, shortDate, monthDay, monthName` (true minus sign, IDR rounded to Rp 1,000, dates parsed at UTC noon).
- `lib/allow.ts`: `isAllowed(email, allowed)`, case/space-insensitive exact match.
- `auth.ts`: `handlers, auth, signIn, signOut`, `currentUser()`.
- `app/(app)/actions.ts`: server action `dismiss(formData)` (auth check, validates `orderId`, revalidates `/`).

## Data Flow

```
engine (Python, nightly) -> Neon tables -> lib/data.ts (SQL, row -> view model)
                                              |-> pure lib/* (metrics, monthly, strategy, slots, format)
                                              -> server components in app/(app)/* -> HTML
user "Mark as done" -> actions.dismiss -> data.dismissAction -> action_dismissals
```

Pages are async server components; each calls `runStatus()` plus the reads it needs in
parallel (`Promise.all`). Dates are selected as `::text` and sliced to `YYYY-MM-DD` so the server
timezone never shifts them.

Page consumers:
- Today: `champion`, `runStatus`, then `picks` and `positions` only for a picks champion (not benchmark, engine `bracket`); actions are holdings with an `orderId`, a `maxDays` and `day >= maxDays`, not dismissed. Any other champion (SPY under D2) shows the no-buys sheet: "Seer recommends no buys", research strategies trade on paper only and their orders live in Positions.
- Positions: `strategies`, `runStatus`, then `positions(strat)` and `pendingOrders(strat)` for `selectStrategy(roster, ?s)`. Pending orders are skipped (empty `Pending`) for the benchmark and while the run is stale. Holdings split by `Holding.kind` into `BracketCard` (stop/target range, days), `BookCard` (weight, stop/target only when set) and `BenchmarkCard`; cards keyed by `Holding.key`. The orders sheet lists bracket orders by slot or book targets by rank with weight; empty-state copy depends on engine and `Pending.decision`. A paper-step warning shows when `paperStatus !== 'success'` (failed / running / not yet run). `PaperChip` and a "on paper since" line mark `isPaper` strategies. For a `checksNews` bracket strategy (C) with a pending session it also calls `vetoes(strat, session)` and renders `vetoSheet` as a stone "Vetoed tonight" sheet; each vetoed/failed row reuses `WhyToggle` (new optional `label`/`missing` props) as "Why vetoed" / "Why it failed".
- History: `strategies`, `closedTrades`, `runStatus`. Filters are `StrategySwitch` over non-benchmark strategies with an `ALL` button (`?s=`, unknown ids read as all) and win/loss icon buttons (`?o=`); defaults are dropped from the URL. Exit-reason icons cover `tp`, `sl`, `time`, `gap`, `signal` (rules said sell, sold at the open) and `forced` (forced close, no more prices), with a fallback for unknown reasons. Rows keyed by `Trade.key`; each shows the strategy tag (`strategyShort`) and a small `PaperChip` when the strategy is paper or missing from the roster.
- Leaderboard: `leaderboard`, `runStatus`, then `monthly(pick.id, run.sessionDate)`. Every card, chart line and legend entry comes from the roster via `looks`. The big figure is the champion (crowned; SPY today); the second figure is the best research strategy on paper while the champion is the benchmark, else SPY. The checklist and month sheet follow `pick = selectStrategy(researchOf(roster), ?s)`; a `StrategySwitch` over research strategies shows when there are two or more (SPY is not selectable here, it is the SPY column). Checklist is `checklist(pick.metrics, spy.totalReturn, pick.strategy.gate)` scored by `scoreOf`; the gate's `note` prints under it. "Month by month" lists the since-start row then months newest first, with a `CircleDashed` partial-month marker while the next session is in that month.

## Dependencies

- `next` 16, `react` / `react-dom` 19: app router, server components, server actions.
- `next-auth` 5 (beta) with the Google provider: sign-in, JWT sessions.
- `@neondatabase/serverless`: `neon()` HTTP tagged-template `sql` for the app; `Pool` over websockets (`ws`) for the scripts, which need transactions.
- `lucide-react`: icons (every button is icon-only with `aria-label` and a tooltip).
- Dev: `typescript`, `vitest`, `ws`.
- Internal: shares `db/migrations/*.sql` and `schema_migrations` with the engine; the engine owns writes to every table except `action_dismissals`.

## Concurrency

No shared mutable state. Each request runs its own parallel queries; the only write is an
idempotent `INSERT ... ON CONFLICT DO NOTHING`. Not a concern beyond that.

## Error Handling

No custom error types. DB errors propagate to Next's error boundary. `dismiss` throws on a
missing session or a bad order id. `seed-demo.mjs` throws (and writes nothing) when real engine
runs exist, more than 100 bars exist (backfill ran), or real paper state exists, and when its
window lacks two month starts.

## Configuration

- `DATABASE_URL` (app, pooled HTTP), `DATABASE_URL_UNPOOLED` (scripts), `ALLOWED_EMAIL`, NextAuth Google credentials. Scripts read `web/.env.local` via `node --env-file`.
- `npm run db:migrate`: apply new migrations in name order, one transaction each.
- `npm run db:seed-demo [-- --dry-run]`: builds a 66-session demo (day 0 + paper start, at least three calendar months) ending at the last completed session, flagged `is_demo`. Roster: SPY (champion, buy and hold), A (bracket), F4-MOM12-N20-TREND and F1-SPY-SMA200-M (monthly book strategies, deciding on each month's first session), and C (bracket, its own younger clock, gate `applicable: false`). Needs migration 004 applied first. Writes strategies (with `engine`, `rules_id`, `paper_start`, `params.backtest_gate`), runs (with paper status), fx, bars, orders, equity snapshots, `paper_state`, `book_positions`, `book_targets`, `book_trades`, and six `news_vetoes` rows for C's pending session. `--dry-run` builds every row and prints counts without connecting.
- `npm test`: vitest over the pure modules (`strategy`, `metrics`, `vetoes`, `monthly`, `slots`, `session`, `format`, `allow`), `components/roster` and `app/(app)/leaderboard/view`.

## Gotchas

- `Trade.id` and `Holding.orderId` are per-table ids; use `key` for React keys and cross-engine identity.
- Only bracket holdings have `orderId`, `slot` and `maxDays`; book `tp`/`sl` may be null. Do not assume a stop/target range exists.
- `slotCount` is 0 for book and benchmark strategies: only bracket strategies fill the S-E-E-R slots.
- The gate defaults to not passed, so the checklist reads 5/6 at best until the engine's `paper` command writes `backtest_gate.passed = true`.
- C's gate is `applicable: false`: its checklist reads 5/6 at best forever, and the score line says real money needs an owner decision (D9).
- Positions for C shows "Vetoed tonight" for the pending session. No rows there means A had no candidates or the news check did not run; the app cannot tell which (`noCheckLine`).
- `runStatus` mixes two runs: freshness from the latest successful run, `latestStatus`/`paperStatus` from the most recent run of any outcome.
- Leaderboard win rate and trade counts only use the strategy's own engine's trade table; SPY has no trades.
- The Leaderboard never says "Ready for real money" unless all six checklist items pass (`scoreOf`); a missing gate yields no items and a 0/6 "Paper only" line.
- Seer ships paper-only (2026-10-04): `isPaper` strategies are research, never a buy recommendation. Today never shows their orders; Positions and History mark them with `PaperChip`.
- Positions defaults to the first research strategy, not the champion: with SPY as champion, `selectStrategy` skips the benchmark unless `?s=` asks for it.
- `StrategySwitch` takes `href` as a function, so it must stay a server component (functions cannot cross into a client component).

## Notes

Documentation Created: 2026-10-04 (P1-WEB-Y9MV). Before this phase the data layer was
bracket-only (`Position` with non-null `tp`/`sl`, `Trade` keyed by order id, a five-item
checklist); this phase widened it to the bracket, book and benchmark engines of migration 003.
