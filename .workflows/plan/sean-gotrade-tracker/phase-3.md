# Phase 3: Overview: P&L graph and holdings

**Plan set:** `SEAN_GOTRADE_TRACKER_PLAN.md`
**Analysis:** `20261007-222658-S3AN_code_analyzer.md`
**Satisfies:** R2 — Sean tracks all of the owner's Gotrade trading activity and shows a profit-and-loss graph
**Depends on:** Phase 1 (ledger), Phase 2 (section shell, gate, `data.ts` with `ledgerOrders()`, placeholder `/sean` page)
**Difficulty:** NORMAL
**Package:** `web/app/sean`

---

## Goal

`/sean` stops being Phase 2's placeholder and becomes the owner's money page: five plain-word
numbers (total profit or loss, realized, unrealized, fees paid, fees as a share of money traded),
a line of the total profit or loss over time with a faint line of fees paid so far and a
break-even line, and a table of what the owner holds now with average cost, last price, value and
profit or loss. The graph reads the nightly `sean_equity` series when Phase 4 has written it, and
falls back to the shared ledger over order dates (valued at the owner's own last order prices)
when it has not, so the page is useful the moment the first screenshot is uploaded.

## Interface Contract

**Deletes:** the body of Phase 2's placeholder `web/app/sean/page.tsx` (the file is replaced whole, its default export keeps the same role)
**Renames:** none
**Creates:**
- `web/lib/sean/overviewData.ts` (new, server only): `EquityRow`, `LatestMark` types and `equity()`, `marks()` reads. A file of its own so Phase 3 and Phase 5 (which run in parallel off Phase 2) never edit the same file; `data.ts` stays Phase 2's.
- `web/app/sean/overview.ts`: `overview`, `sortOrders`, `toCloses`, `holdings`, `stats`, `pnlChart`, `monthTicks`, `orderDay`, formatters `usdText`, `signedUsdText`, `pctText`, `signedPctText`, `sharesText`, `priceText`, `usdTick`, `dayText`, `monthYearText`, `toneOf`, `round2`, colours `PNL_COLOR`, `FEES_COLOR`, `EVEN_COLOR`, types `Overview`, `OverviewInput`, `OverviewOrder`, `OverviewStat`, `StatKey`, `Holding`, `HoldingsTotal`, `PnlChart`, `Tone`
- `web/app/sean/OverviewBody.tsx`: `OverviewBody`, `TRADES_HREF` (pure server-renderable component, so the page renders with zero, one and many orders under vitest)
- `web/app/sean/overview.test.ts`, `web/app/sean/OverviewBody.test.tsx`, `web/app/sean/overview.module.css`
**Signature changes:** none
**Requires (from earlier phases):** see **Bindings** below — `buildLedger`/`pnlAt`/`pnlSeries`/`orderSession`/`Close`/`PnlPoint` (Phase 1 `ledger.ts`), `requireSean(next)` (Phase 2 `gate.ts`), `ledgerOrders()`/`LedgerRow` (Phase 2 `data.ts`), `app/sean/layout.tsx` shell with a page title template (Phase 2), tables `sean_equity` and `sean_marks` from migration `015_sean.sql` (Phase 1).
**Leaves alone (owned by others):** `web/lib/sean/data.ts`, `web/app/sean/layout.tsx`, `not-found.tsx`, `sean.module.css`, `web/app/sean/trades/*`, `web/app/api/sean/*`, `web/components/sean/*`, `web/components/{Nav,AppHeader}.tsx`, `web/lib/sean/gate.ts` (Phase 2); `web/app/sean/plan/*`, `web/lib/sean/{reminders,planData}.ts` (Phase 5); every other `web/lib/sean/*` module (Phase 1); engine and workflows (Phases 4, 6, 7); `web/components/sera/*` (read-only reuse). This phase shares no file with Phase 5.

### Bindings (reconciled against Phase 1's and Phase 2's plans)

Phase 1's ledger was written and tested before reconciliation; these are its real exports, and the
whole adapter is three call sites in `overview.ts` (`holdings`, `pnlChart`, `overview`).

```ts
// web/lib/sean/ledger.ts (Phase 1, contract B)
export type LedgerOrder = { id: number; side: 'buy' | 'sell'; symbol: string; executedAt: string; price: number;
  shares: number; totalUsd: number; tradingFeeUsd: number; regulatoryFeeUsd: number; ppnUsd: number };
export type Close = { symbol: string; date: string; close: number };          // a flat array, not a map
export type Holding = { symbol: string; shares: number; costUsd: number; avgPrice: number; lastOrderPrice: number };
export type LedgerBook = { holdings: Holding[]; realizedUsd: number; feesUsd: number };   // open positions only, by symbol
export type PnlPoint = { date: string; valueUsd: number; costUsd: number; realizedUsd: number;
  unrealizedUsd: number; pnlUsd: number; feesUsd: number };                   // every figure in cents
/** The New York calendar date of executedAt: the NYSE session an order counts in (plan Decisions). */
export function orderSession(executedAt: string): string;
export function buildLedger(orders: LedgerOrder[], through?: string): LedgerBook;
/** Orders whose orderSession <= date; holdings at the last close <= date, else their last order price. */
export function pnlSeries(orders: LedgerOrder[], closes: Close[], dates: string[]): PnlPoint[];  // sorted, deduped
export function pnlAt(orders: LedgerOrder[], closes: Close[], date: string): PnlPoint;

// web/lib/sean/data.ts (Phase 2, server only)
export type LedgerRow = LedgerOrder & { amountUsd: number };
/** Every order, oldest first; executedAt ISO with +07:00. */
export async function ledgerOrders(): Promise<LedgerRow[]>;

// web/lib/sean/gate.ts (Phase 2)
export async function requireSean(next?: string): Promise<User>;
```

**Which date an order counts on (plan Decisions):** the New York trade date, `orderSession`, the
same date the engine writes `sean_equity` under. The fallback series' x values, the first-day
label and "today" (the live point and `pnlAt`) are all New York dates, so the fallback line and
the nightly line never disagree by a day around midnight WIB.

Phase 2's `app/sean/layout.tsx` sets `metadata.title.template = '%s · Sean'` and renders
`requireSean()`, SeanNav and `<main>` → `.column`.

## Files

| File | Action | What changes |
|---|---|---|
| `web/lib/sean/overviewData.ts` | create | `EquityRow`, `LatestMark`, `equity()`, `marks()` (server only) |
| `web/app/sean/overview.ts` | create | pure view model: stats, chart series, holdings, formatters |
| `web/app/sean/overview.test.ts` | create | view-model tests: empty, one order, many orders, all sold, nightly series, live point, ticks, formatters |
| `web/app/sean/OverviewBody.tsx` | create | renders an `Overview` with `Section`, `Stat`, `LineChart`, `Legend`, a holdings table and the empty state |
| `web/app/sean/OverviewBody.test.tsx` | create | `renderToStaticMarkup` with zero, one and many orders |
| `web/app/sean/overview.module.css` | create | grid, stats row, holdings table, empty state |
| `web/app/sean/page.tsx` | replace (whole file, line 1 onward) | gate, three reads, `PageHeader`, `<OverviewBody>` |

## Implementation Steps

### Step 1: The Overview's reads
**File:** `web/lib/sean/overviewData.ts` (new)
**Change:** two server-only reads, in a file of this phase's own (Phase 2 owns `data.ts`; Phase 5 writes `planData.ts` in parallel). `sql` comes from `@/lib/db`, exactly as `data.ts` imports it. Not unit-tested (plan invariant 7).
**Code:**
```ts
/**
 * The Overview's reads (Sean phase 3): the nightly profit-and-loss series and the latest closes.
 * Server only (opens Neon through lib/db); the page reads orders through data.ts ledgerOrders().
 * overview.ts may `import type` from here: types are erased, so no DB code reaches a test.
 */
import { sql } from '@/lib/db';

/** One day of the owner's profit-and-loss series (sean_equity, written nightly by the engine). */
export type EquityRow = {
  /** NYSE session, 'YYYY-MM-DD'. */
  date: string;
  valueUsd: number;
  costUsd: number;
  realizedUsd: number;
  unrealizedUsd: number;
  pnlUsd: number;
  feesUsd: number;
};

/** The newest daily close Sean has for one symbol (sean_marks). Same shape as the ledger's Close. */
export type LatestMark = { symbol: string; date: string; close: number };

/** The whole sean_equity series, oldest first. Empty until the engine's `sean marks` has run. */
export async function equity(): Promise<EquityRow[]> {
  const rows = await sql`
    SELECT date::text AS date, value_usd, cost_usd, realized_usd, unrealized_usd, pnl_usd, fees_usd
    FROM sean_equity
    ORDER BY date`;
  return rows.map((r: Record<string, unknown>) => ({
    date: String(r.date).slice(0, 10),
    valueUsd: Number(r.value_usd),
    costUsd: Number(r.cost_usd),
    realizedUsd: Number(r.realized_usd),
    unrealizedUsd: Number(r.unrealized_usd),
    pnlUsd: Number(r.pnl_usd),
    feesUsd: Number(r.fees_usd),
  }));
}

/** The latest close per symbol the owner has ever held. Empty until the engine's `sean marks` has run. */
export async function marks(): Promise<LatestMark[]> {
  const rows = await sql`
    SELECT DISTINCT ON (symbol) symbol, date::text AS date, close
    FROM sean_marks
    ORDER BY symbol, date DESC`;
  return rows.map((r: Record<string, unknown>) => ({
    symbol: String(r.symbol),
    date: String(r.date).slice(0, 10),
    close: Number(r.close),
  }));
}
```
The column names are migration 015's exactly: `sean_equity (date, value_usd, cost_usd, realized_usd, unrealized_usd, pnl_usd, fees_usd)` and `sean_marks (symbol, date, close)`.
**Impact:** new file. Both tables exist from Phase 1's migration; they are empty until Phase 4 runs, which the view model handles.

### Step 2: The view model
**File:** `web/app/sean/overview.ts` (new)
**Change:** everything the page shows, computed from orders + equity rows + latest marks + today's New York date. No React, no DB, relative imports only (plan invariant 7). Ledger math is never re-implemented here: totals come from `pnlAt`, the fallback series from `pnlSeries`, open positions and their cost from `buildLedger`. The only arithmetic of its own is display: per-holding value and P&L (`shares × price − cost`, the same rule as contract B), the sum of traded amounts, and the fee share.
**Code:**
```ts
// Sean's Overview as a pure view model: the owner's orders, the nightly profit-and-loss series and
// the latest closes in; plain-word stats, chart series and holdings rows out. No React and no DB,
// so it is unit-tested under plain vitest (relative imports only, plan invariant 7).
//
// The money math is the shared ledger's (contract B, lib/sean/ledger.ts). This module only picks
// which numbers to show and how to say them.
import type { LineSeries } from '../../components/sera/charts/LineChart';
import { type Domain, type Format, type RefLine, type Tick, dateNum, extent } from '../../components/sera/charts/scale';
import type { LedgerRow } from '../../lib/sean/data';
import { buildLedger, type Close, orderSession, type PnlPoint, pnlAt, pnlSeries } from '../../lib/sean/ledger';
import type { EquityRow, LatestMark } from '../../lib/sean/overviewData';

/** An order as the Overview reads it: the ledger's fields plus the trade amount (data.ts ledgerOrders). */
export type OverviewOrder = LedgerRow;

// ---- Colours (Seer v2 tokens; green/red stay reserved for profit and loss numbers) ------------

export const PNL_COLOR = 'var(--ink)';
export const FEES_COLOR = 'var(--ink-3)';
export const EVEN_COLOR = 'var(--ink-3)';

/** Up to this many points the line gets a dot per day, each with its own tooltip. */
const DOTS_UP_TO = 40;
const DAY_MS = 86_400_000;
const MINUS = '−';

// ---- Formatting ---------------------------------------------------------------------------------

const isZero = (v: number): boolean => Math.abs(v) < 0.005;
const cents = (v: number): string =>
  Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Cents, with -0 folded to 0. */
export const round2 = (v: number): number => Math.round(v * 100) / 100 || 0;

/** 1234.5 -> '$1,234.50', -3.2 -> '−$3.20'. */
export const usdText = (v: number): string => `${!isZero(v) && v < 0 ? MINUS : ''}$${cents(v)}`;

/** 3.61 -> '+$3.61', -0.14 -> '−$0.14', 0 -> '$0.00'. */
export const signedUsdText = (v: number): string => `${isZero(v) ? '' : v < 0 ? MINUS : '+'}$${cents(v)}`;

/** 0.0075 -> '0.75%'; null or not finite -> '—'. */
export function pctText(v: number | null, digits = 2): string {
  if (v === null || !Number.isFinite(v)) return '—';
  const shown = (Math.abs(v) * 100).toFixed(digits);
  return `${v < 0 && Number(shown) !== 0 ? MINUS : ''}${shown}%`;
}

/** 0.1917 -> '+19.2%', -0.0065 -> '−0.6%'; null -> '—'. */
export function signedPctText(v: number | null, digits = 1): string {
  if (v === null || !Number.isFinite(v)) return '—';
  const shown = (Math.abs(v) * 100).toFixed(digits);
  return `${Number(shown) === 0 ? '' : v < 0 ? MINUS : '+'}${shown}%`;
}

/** 0.5 -> '0.5', 12 -> '12', 0.035842123 -> '0.035842'. */
export const sharesText = (v: number): string => v.toLocaleString('en-US', { maximumFractionDigits: 6 });

/** 12 -> '$12.00', 1063.886 -> '$1,063.886'. */
export const priceText = (v: number): string =>
  `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 3 })}`;

/** Axis labels in dollars: usdTick(2)(-1) -> '−$1.00', usdTick(0)(1500) -> '$1,500'. */
export const usdTick = (digits: number): Format => v => {
  const shown = Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return `${Number(Math.abs(v).toFixed(digits)) === 0 ? '' : v < 0 ? MINUS : ''}$${shown}`;
};

export type Tone = 'pos' | 'neg';
/** Green for a gain, red for a loss, nothing for zero: the only meaning those colours have here. */
export const toneOf = (v: number): Tone | undefined => (isZero(v) ? undefined : v > 0 ? 'pos' : 'neg');

const DAY = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric', year: 'numeric' });
const DAY_SHORT = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric' });
const MON = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short' });
const MONTH_YEAR = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short', year: 'numeric' });
const noon = (ymd: string): Date => new Date(`${ymd}T12:00:00Z`);

/** '2026-10-06' -> 'Oct 6, 2026'. */
export const dayText = (ymd: string): string => DAY.format(noon(ymd));
/** '2025-06-12' -> 'Jun 2025'. */
export const monthYearText = (ymd: string): string => MONTH_YEAR.format(noon(ymd));
/** The New York trade date an order counts on (the ledger's orderSession; plan Decisions). */
export const orderDay = (o: Pick<OverviewOrder, 'executedAt'>): string => orderSession(o.executedAt);

/**
 * Month-start ticks between two 'YYYY-MM-DD' days, every 1, 2, 3, 6, 12 or 24 months so there are
 * at most `max`. The first tick and every January carry the year ('Jul 2025', 'Sep', 'Jan 2026').
 * A window with fewer than two month starts gets its two ends ('Sep 1', 'Sep 15'); a single day
 * gets one tick.
 */
export function monthTicks(from: string, to: string, max = 8): Tick[] {
  const a = dateNum(from);
  const b = dateNum(to);
  if (!(b > a)) return [{ value: a, label: DAY_SHORT.format(new Date(a)) }];
  const A = new Date(a);
  const B = new Date(b);
  const i0 = A.getUTCFullYear() * 12 + A.getUTCMonth() + (A.getUTCDate() > 1 ? 1 : 0);
  const i1 = B.getUTCFullYear() * 12 + B.getUTCMonth();
  const count = (step: number): number => {
    let n = 0;
    for (let i = i0; i <= i1; i++) if (i % step === 0) n++;
    return n;
  };
  const step = [1, 2, 3, 6, 12, 24].find(st => count(st) <= max) ?? 24;
  const out: Tick[] = [];
  for (let i = i0; i <= i1; i++) {
    if (i % step !== 0) continue;
    const y = Math.floor(i / 12);
    const m = i % 12;
    const at = Date.UTC(y, m, 1);
    const mon = MON.format(new Date(at));
    out.push({ value: at, label: out.length === 0 || m === 0 ? `${mon} ${y}` : mon });
  }
  if (out.length >= 2) return out;
  return [
    { value: a, label: DAY_SHORT.format(new Date(a)) },
    { value: b, label: DAY_SHORT.format(new Date(b)) },
  ];
}

// ---- Ledger adapter (the only place that knows the shapes Phase 1 exports) ----------------------

/** Oldest first; same moment -> lower id first (contract B's order). */
export function sortOrders(orders: readonly OverviewOrder[]): OverviewOrder[] {
  return [...orders].sort((a, b) => Date.parse(a.executedAt) - Date.parse(b.executedAt) || a.id - b.id);
}

/** Latest marks -> the ledger's flat Close list (copied, oldest first). */
export function toCloses(marks: readonly LatestMark[]): Close[] {
  return [...marks]
    .sort((x, y) => x.date.localeCompare(y.date) || x.symbol.localeCompare(y.symbol))
    .map(m => ({ symbol: m.symbol, date: m.date, close: m.close }));
}

// ---- Stats --------------------------------------------------------------------------------------

export type StatKey = 'total' | 'realized' | 'unrealized' | 'fees' | 'feeShare';
export type OverviewStat = { key: StatKey; label: string; value: string; tone?: Tone; sub: string; tip: string };

/** The five numbers at the top, from the ledger's "now" point and the orders themselves. */
export function stats(now: PnlPoint, sorted: readonly OverviewOrder[]): OverviewStat[] {
  const traded = sorted.reduce((sum, o) => sum + o.amountUsd, 0);
  const n = sorted.length;
  return [
    {
      key: 'total',
      label: 'Total profit or loss',
      value: signedUsdText(now.pnlUsd),
      tone: toneOf(now.pnlUsd),
      sub: 'Sold and still held, after every fee',
      tip: 'What you made by selling plus what your stocks are up or down now. Every fee is already taken out.',
    },
    {
      key: 'realized',
      label: 'From stocks you sold',
      value: signedUsdText(now.realizedUsd),
      tone: toneOf(now.realizedUsd),
      sub: 'Realized: locked in for good',
      tip: 'What your sales brought in minus what those shares cost you, buying fees included.',
    },
    {
      key: 'unrealized',
      label: 'On stocks you still hold',
      value: signedUsdText(now.unrealizedUsd),
      tone: toneOf(now.unrealizedUsd),
      sub: 'Unrealized: moves with the price until you sell',
      tip: 'What your stocks are worth now minus what you paid for them, buying fees included.',
    },
    {
      key: 'fees',
      label: 'Fees paid',
      value: usdText(now.feesUsd),
      sub: `On ${n} order${n === 1 ? '' : 's'}`,
      tip: 'The trading fee, the regulatory fee and the tax on them (PPN), added up over every order.',
    },
    {
      key: 'feeShare',
      label: 'Fees as a share of money traded',
      value: pctText(traded > 0 ? now.feesUsd / traded : null),
      sub: `${usdText(traded)} bought and sold in total`,
      tip: 'All fees divided by the dollar amount of every buy and every sell.',
    },
  ];
}

// ---- Holdings -----------------------------------------------------------------------------------

export type Holding = {
  symbol: string;
  shares: number;
  /** What the shares still held cost, buying fees included (contract B). */
  cost: number;
  avgCost: number;
  price: number;
  value: number;
  pnl: number;
  pnlPct: number | null;
  /** True when there is no close yet and the price is the owner's own last order price. */
  estimate: boolean;
  priceTip: string;
  sharesText: string;
  avgCostText: string;
  priceText: string;
  valueText: string;
  pnlText: string;
  pnlPctText: string;
  tone?: Tone;
};

export type HoldingsTotal = { cost: number; value: number; pnl: number; valueText: string; pnlText: string; tone?: Tone };

/** Open positions priced at their latest close (else the last order price), biggest first, plus the symbols sold out of. */
export function holdings(
  sorted: readonly OverviewOrder[],
  marks: readonly LatestMark[],
): { rows: Holding[]; total: HoldingsTotal; closed: string[] } {
  const markOf = new Map<string, LatestMark>();
  for (const m of marks) {
    const seen = markOf.get(m.symbol);
    if (!seen || m.date > seen.date) markOf.set(m.symbol, m);
  }

  // The ledger's open positions (contract B): shares to 9 dp, cost in cents with buying fees,
  // average price, and the last order price that stands in until a close exists.
  const rows: Holding[] = buildLedger([...sorted])
    .holdings.map(p => {
      const mark = markOf.get(p.symbol);
      const price = mark ? mark.close : p.lastOrderPrice;
      const value = p.shares * price;
      const pnl = value - p.costUsd;
      const pnlPct = p.costUsd > 0 ? pnl / p.costUsd : null;
      const avgCost = p.avgPrice;
      return {
        symbol: p.symbol,
        shares: p.shares,
        cost: p.costUsd,
        avgCost,
        price,
        value,
        pnl,
        pnlPct,
        estimate: !mark,
        priceTip: mark
          ? `Closing price on ${dayText(mark.date)}`
          : 'Your own last order price. Market prices are added every night after the US market closes.',
        sharesText: sharesText(p.shares),
        avgCostText: priceText(avgCost),
        priceText: priceText(price),
        valueText: usdText(value),
        pnlText: signedUsdText(pnl),
        pnlPctText: signedPctText(pnlPct),
        tone: toneOf(pnl),
      };
    })
    .sort((a, b) => b.value - a.value || a.symbol.localeCompare(b.symbol));

  const cost = rows.reduce((sum, r) => sum + r.cost, 0);
  const value = rows.reduce((sum, r) => sum + r.value, 0);
  const pnl = value - cost;
  const held = new Set(rows.map(r => r.symbol));
  const closed = [...new Set(sorted.map(o => o.symbol))].filter(sym => !held.has(sym)).sort();
  return {
    rows,
    total: { cost, value, pnl, valueText: usdText(value), pnlText: signedUsdText(pnl), tone: toneOf(pnl) },
    closed,
  };
}

// ---- The profit-and-loss chart ------------------------------------------------------------------

export type PnlChart = {
  /** 'nightly': sean_equity at each session's close. 'orders': the ledger on each trading day at order prices. */
  source: 'nightly' | 'orders';
  title: string;
  caption: string;
  ariaLabel: string;
  series: LineSeries[];
  refLines: RefLine[];
  xTicks: Tick[];
  /** Set only for a one-day series, so its single point sits mid-plot on a one-week axis. */
  xDomain?: Domain;
  yFormat: Format;
  /** True when a last point for today was added because orders are newer than the nightly prices. */
  live: boolean;
  /** The last nightly session, or null when the chart is built from orders alone. */
  pricesAsOf: string | null;
};

type ChartPoint = { date: string; pnl: number; fees: number; live: boolean };

const headline = (pnl: number, first: string): string =>
  isZero(pnl)
    ? `Even since ${monthYearText(first)}`
    : `${pnl > 0 ? 'Up' : 'Down'} ${usdText(Math.abs(pnl))} since ${monthYearText(first)}`;

/**
 * The line: sean_equity when the engine has written it (plus a point for today when an uploaded
 * order is newer than its last session), else the ledger on every day the owner traded.
 */
export function pnlChart(
  sorted: readonly OverviewOrder[],
  equityRows: readonly EquityRow[],
  closes: Close[],
  today: string,
  now: PnlPoint,
): PnlChart {
  const first = orderDay(sorted[0]);
  const lastOrder = orderDay(sorted[sorted.length - 1]);
  let pts: ChartPoint[];
  let source: PnlChart['source'];
  let pricesAsOf: string | null = null;
  let live = false;

  if (equityRows.length > 0) {
    const eq = [...equityRows].sort((a, b) => a.date.localeCompare(b.date));
    pts = eq.map(r => ({ date: r.date, pnl: r.pnlUsd, fees: r.feesUsd, live: false }));
    pricesAsOf = eq[eq.length - 1].date;
    if (lastOrder > pricesAsOf && today > pricesAsOf) {
      pts.push({ date: today, pnl: now.pnlUsd, fees: now.feesUsd, live: true });
      live = true;
    }
    source = 'nightly';
  } else {
    // One point per New York trade date the owner traded on (pnlSeries sorts and dedupes them).
    pts = pnlSeries([...sorted], closes, sorted.map(orderDay)).map(p => ({
      date: p.date, pnl: p.pnlUsd, fees: p.feesUsd, live: false,
    }));
    source = 'orders';
  }

  const pointTip = (p: ChartPoint): string =>
    `${dayText(p.date)}: ${signedUsdText(p.pnl)}${p.live ? ', with your newest orders' : ''}`;
  const dots = pts.length <= DOTS_UP_TO;
  const series: LineSeries[] = [
    {
      id: 'pnl',
      label: 'Profit or loss',
      points: pts.map(p => [p.date, round2(p.pnl), pointTip(p)] as const),
      color: PNL_COLOR,
      width: 2.5,
      dots,
      tip: 'Your total profit or loss after every fee',
    },
    {
      id: 'fees',
      label: 'Fees paid so far',
      points: pts.map(p => [p.date, round2(p.fees), `${dayText(p.date)}: ${usdText(p.fees)} in fees so far`] as const),
      color: FEES_COLOR,
      width: 1.5,
      dash: '6 4',
      tip: 'Every fee you have paid up to that day',
    },
  ];

  const span = extent([...pts.map(p => p.pnl), ...pts.map(p => p.fees)], [0]);
  const firstPt = pts[0].date;
  const lastPt = pts[pts.length - 1].date;
  const xDomain: Domain | undefined =
    firstPt === lastPt ? [dateNum(firstPt) - 3 * DAY_MS, dateNum(firstPt) + 3 * DAY_MS] : undefined;

  const how =
    source === 'nightly'
      ? `Your total profit or loss after every fee, at each day's closing prices. The dashed line is what you have paid in fees so far. Prices as of ${dayText(pricesAsOf as string)}.${live ? ' The last point adds orders newer than those prices.' : ''}`
      : 'Your total profit or loss after every fee, on each day you traded. Sean has no market prices yet, so your stocks are valued at your own last order price until the nightly prices come in. The dashed line is what you have paid in fees so far.';

  return {
    source,
    title: headline(now.pnlUsd, first),
    caption: how,
    ariaLabel: `Profit or loss over time, from ${dayText(firstPt)} to ${dayText(lastPt)}, now ${signedUsdText(now.pnlUsd)}`,
    series,
    refLines: [
      {
        value: 0,
        label: 'Break-even',
        color: EVEN_COLOR,
        tip: 'Above this line you are up overall, below it you are down',
      },
    ],
    xTicks: monthTicks(firstPt, lastPt),
    xDomain,
    yFormat: usdTick(span[1] - span[0] < 20 ? 2 : 0),
    live,
    pricesAsOf,
  };
}

// ---- The page model -----------------------------------------------------------------------------

export type OverviewInput = {
  orders: readonly OverviewOrder[];
  equity: readonly EquityRow[];
  marks: readonly LatestMark[];
  /** Today's New York date, 'YYYY-MM-DD' (orderSession(new Date().toISOString())): every order placed so far counts on or before it. */
  today: string;
};

export type Overview =
  | { empty: true }
  | {
      empty: false;
      orderCount: number;
      firstDay: string;
      stats: OverviewStat[];
      chart: PnlChart;
      holdings: Holding[];
      total: HoldingsTotal;
      closed: string[];
    };

export function overview({ orders, equity, marks, today }: OverviewInput): Overview {
  if (orders.length === 0) return { empty: true };
  const sorted = sortOrders(orders);
  const closes = toCloses(marks);
  const now = pnlAt([...sorted], closes, today);
  const h = holdings(sorted, marks);
  return {
    empty: false,
    orderCount: sorted.length,
    firstDay: orderDay(sorted[0]),
    stats: stats(now, sorted),
    chart: pnlChart(sorted, equity, closes, today, now),
    holdings: h.rows,
    total: h.total,
    closed: h.closed,
  };
}
```
**Impact:** new module; nothing imports it yet.

### Step 3: View-model tests
**File:** `web/app/sean/overview.test.ts` (new)
**Change:** hand-computed cases against contract B. The numbers:

- A: buy 2 AAA @ $10.00 on Sep 1 (fees 0.10 + 0.02 + 0.02) → amount 20.00, total 20.14.
- B: sell 1 AAA @ $12.00 on Sep 15 (fees 0.10 + 0.01 + 0.01) → amount 12.00, total 11.88. avg 10.07 → realized 1.81, AAA left 1 share costing 10.07.
- C: buy 0.5 BBB @ $40.00 on Sep 15 (fees 0.10 + 0.02 + 0.01) → amount 20.00, total 20.13.
- No marks: AAA at 12 (last order) → +1.93; BBB at 40 → −0.13; unrealized 1.80; pnl 3.61; fees 0.39; traded 52 → 0.75%.
- AAA close 13 on Oct 6: unrealized 2.80, pnl 4.61.
- D: buy 1 CCC @ $5.00 on Oct 7 (fees 0.10 + 0.02 + 0.01) → total 5.13; with the AAA mark pnl 4.48, fees 0.52.
- A + sell 2 AAA @ $12 (fees 0.10 + 0.02 + 0.02, total 23.86) → realized 3.72, nothing held.
- Every order is at 21:00–22:00 WIB, i.e. 10:00–11:00 New York, so its New York trade date is its WIB date; the after-midnight case is pinned in the `orderDay` test.

These figures were re-checked against Phase 1's real `ledger.ts` (average cost with fees, last-order-price fallback, cents half up): every expectation below holds unchanged.

**Code:**
```ts
import { describe, expect, it } from 'vitest';
import { dateNum } from '../../components/sera/charts/scale';
import type { EquityRow, LatestMark } from '../../lib/sean/overviewData';
import {
  FEES_COLOR,
  holdings,
  monthTicks,
  orderDay,
  overview,
  type OverviewOrder,
  PNL_COLOR,
  pctText,
  priceText,
  sharesText,
  signedPctText,
  signedUsdText,
  sortOrders,
  toCloses,
  usdText,
  usdTick,
} from './overview';

let nextId = 1;
function mk(
  side: 'buy' | 'sell',
  symbol: string,
  executedAt: string,
  price: number,
  shares: number,
  [trading, regulatory, ppn]: [number, number, number],
): OverviewOrder {
  const amount = Math.round(price * shares * 100) / 100;
  const fees = trading + regulatory + ppn;
  const total = Math.round((side === 'buy' ? amount + fees : amount - fees) * 100) / 100;
  return {
    id: nextId++,
    side,
    symbol,
    executedAt,
    price,
    shares,
    amountUsd: amount,
    tradingFeeUsd: trading,
    regulatoryFeeUsd: regulatory,
    ppnUsd: ppn,
    totalUsd: total,
  };
}

const A = mk('buy', 'AAA', '2026-09-01T21:30:00+07:00', 10, 2, [0.1, 0.02, 0.02]);
const B = mk('sell', 'AAA', '2026-09-15T21:30:00+07:00', 12, 1, [0.1, 0.01, 0.01]);
const C = mk('buy', 'BBB', '2026-09-15T22:00:00+07:00', 40, 0.5, [0.1, 0.02, 0.01]);
const D = mk('buy', 'CCC', '2026-10-07T21:00:00+07:00', 5, 1, [0.1, 0.02, 0.01]);
const SELL_ALL = mk('sell', 'AAA', '2026-09-15T21:30:00+07:00', 12, 2, [0.1, 0.02, 0.02]);
const TODAY = '2026-10-07';
const MARK_AAA: LatestMark = { symbol: 'AAA', date: '2026-10-06', close: 13 };

const eqRow = (date: string, pnlUsd: number, feesUsd: number): EquityRow => ({
  date,
  valueUsd: 0,
  costUsd: 0,
  realizedUsd: 0,
  unrealizedUsd: 0,
  pnlUsd,
  feesUsd,
});

const statValue = (v: ReturnType<typeof overview>, key: string) => {
  if (v.empty) throw new Error('expected orders');
  return v.stats.find(s => s.key === key);
};

describe('formatters', () => {
  it('writes dollars with a real minus sign and thousands separators', () => {
    expect(usdText(1234.5)).toBe('$1,234.50');
    expect(usdText(-3.2)).toBe('−$3.20');
    expect(signedUsdText(3.61)).toBe('+$3.61');
    expect(signedUsdText(-0.14)).toBe('−$0.14');
    expect(signedUsdText(0.001)).toBe('$0.00');
  });

  it('writes percentages, shares and prices plainly', () => {
    expect(pctText(0.0075)).toBe('0.75%');
    expect(pctText(null)).toBe('—');
    expect(signedPctText(0.191658)).toBe('+19.2%');
    expect(signedPctText(-0.006458)).toBe('−0.6%');
    expect(signedPctText(0.0001)).toBe('0.0%');
    expect(sharesText(0.5)).toBe('0.5');
    expect(sharesText(12)).toBe('12');
    expect(sharesText(0.035842123)).toBe('0.035842');
    expect(priceText(12)).toBe('$12.00');
    expect(priceText(1063.886)).toBe('$1,063.886');
  });

  it('labels the dollar axis with cents only when the range is small', () => {
    expect(usdTick(2)(1)).toBe('$1.00');
    expect(usdTick(2)(-1)).toBe('−$1.00');
    expect(usdTick(0)(1500)).toBe('$1,500');
    expect(usdTick(0)(-0.2)).toBe('$0');
  });

  it('reads the order day as the New York trade date', () => {
    expect(orderDay({ executedAt: '2026-10-07T21:55:00+07:00' })).toBe('2026-10-07');
    // 03:30 WIB on Oct 8 is 16:30 on Oct 7 in New York: that session's trade
    expect(orderDay({ executedAt: '2026-10-08T03:30:00+07:00' })).toBe('2026-10-07');
  });
});

describe('monthTicks', () => {
  it('spaces month starts so at most eight fit, with the year on the first and on January', () => {
    const ticks = monthTicks('2025-06-12', '2026-10-07');
    expect(ticks.map(t => t.label)).toEqual(['Jul 2025', 'Sep', 'Nov', 'Jan 2026', 'Mar', 'May', 'Jul', 'Sep']);
    expect(ticks[0].value).toBe(Date.UTC(2025, 6, 1));
  });

  it('falls back to the two ends inside one month, and to one tick for one day', () => {
    expect(monthTicks('2026-09-01', '2026-09-15').map(t => t.label)).toEqual(['Sep 1', 'Sep 15']);
    expect(monthTicks('2026-09-01', '2026-09-01')).toEqual([{ value: dateNum('2026-09-01'), label: 'Sep 1' }]);
  });
});

describe('ledger adapter', () => {
  it('sorts orders by time, then by id', () => {
    const late = mk('buy', 'ZZZ', '2026-09-15T21:30:00+07:00', 1, 1, [0.1, 0, 0]);
    expect(sortOrders([late, C, B, A]).map(o => o.id)).toEqual([A.id, B.id, late.id, C.id]);
  });

  it('turns latest marks into the flat closes the ledger takes, oldest first', () => {
    const closes = toCloses([
      { symbol: 'AAA', date: '2026-10-06', close: 13 },
      { symbol: 'AAA', date: '2026-10-05', close: 12.5 },
      { symbol: 'BBB', date: '2026-10-06', close: 41 },
    ]);
    expect(closes).toEqual([
      { symbol: 'AAA', date: '2026-10-05', close: 12.5 },
      { symbol: 'AAA', date: '2026-10-06', close: 13 },
      { symbol: 'BBB', date: '2026-10-06', close: 41 },
    ]);
  });
});

describe('overview', () => {
  it('is empty with no orders', () => {
    expect(overview({ orders: [], equity: [], marks: [], today: TODAY })).toEqual({ empty: true });
  });

  it('one buy and no prices: down by its fees, one dotted point on a one-week axis', () => {
    const v = overview({ orders: [A], equity: [], marks: [], today: TODAY });
    if (v.empty) throw new Error('expected orders');
    expect(statValue(v, 'total')?.value).toBe('−$0.14');
    expect(statValue(v, 'total')?.tone).toBe('neg');
    expect(statValue(v, 'realized')?.value).toBe('$0.00');
    expect(statValue(v, 'realized')?.tone).toBeUndefined();
    expect(statValue(v, 'fees')?.value).toBe('$0.14');
    expect(statValue(v, 'fees')?.sub).toBe('On 1 order');
    expect(v.chart.title).toBe('Down $0.14 since Sep 2026');
    expect(v.chart.source).toBe('orders');
    expect(v.chart.series[0].points).toHaveLength(1);
    expect(v.chart.series[0].dots).toBe(true);
    expect(v.chart.xDomain).toEqual([dateNum('2026-09-01') - 3 * 86_400_000, dateNum('2026-09-01') + 3 * 86_400_000]);
    expect(v.holdings).toHaveLength(1);
    expect(v.holdings[0].estimate).toBe(true);
    expect(v.holdings[0].priceText).toBe('$10.00');
    expect(v.holdings[0].avgCostText).toBe('$10.07');
  });

  it('many orders and no prices: the ledger at order prices on each trading day', () => {
    const v = overview({ orders: [C, B, A], equity: [], marks: [], today: TODAY });
    if (v.empty) throw new Error('expected orders');
    expect(v.orderCount).toBe(3);
    expect(v.firstDay).toBe('2026-09-01');
    expect(v.stats.map(s => s.value)).toEqual(['+$3.61', '+$1.81', '+$1.80', '$0.39', '0.75%']);
    expect(statValue(v, 'feeShare')?.sub).toBe('$52.00 bought and sold in total');

    const pnl = v.chart.series.find(s => s.id === 'pnl');
    const fees = v.chart.series.find(s => s.id === 'fees');
    expect(pnl?.color).toBe(PNL_COLOR);
    expect(fees?.color).toBe(FEES_COLOR);
    expect(fees?.dash).toBe('6 4');
    expect(pnl?.points.map(p => p[0])).toEqual(['2026-09-01', '2026-09-15']);
    expect(pnl?.points[0][1]).toBeCloseTo(-0.14, 2);
    expect(pnl?.points[1][1]).toBeCloseTo(3.61, 2);
    expect(fees?.points[1][1]).toBeCloseTo(0.39, 2);
    expect(pnl?.points[1][2]).toBe('Sep 15, 2026: +$3.61');
    expect(v.chart.refLines).toEqual([expect.objectContaining({ value: 0, label: 'Break-even' })]);
    expect(v.chart.title).toBe('Up $3.61 since Sep 2026');
    expect(v.chart.caption).toContain('no market prices yet');
    expect(v.chart.pricesAsOf).toBeNull();
    expect(v.chart.yFormat(1)).toBe('$1.00');

    expect(v.holdings.map(h => h.symbol)).toEqual(['BBB', 'AAA']);
    const [bbb, aaa] = v.holdings;
    expect(bbb.sharesText).toBe('0.5');
    expect(bbb.avgCostText).toBe('$40.26');
    expect(bbb.valueText).toBe('$20.00');
    expect(bbb.pnlText).toBe('−$0.13');
    expect(bbb.pnlPctText).toBe('−0.6%');
    expect(bbb.tone).toBe('neg');
    expect(aaa.priceText).toBe('$12.00');
    expect(aaa.pnlText).toBe('+$1.93');
    expect(aaa.pnlPctText).toBe('+19.2%');
    expect(aaa.tone).toBe('pos');
    expect(aaa.priceTip).toContain('last order price');
    expect(v.total.value).toBeCloseTo(32, 6);
    expect(v.total.pnl).toBeCloseTo(1.8, 6);
    expect(v.closed).toEqual([]);
  });

  it('a nightly close replaces the order price for that stock only', () => {
    const v = overview({ orders: [A, B, C], equity: [], marks: [MARK_AAA], today: TODAY });
    if (v.empty) throw new Error('expected orders');
    expect(statValue(v, 'total')?.value).toBe('+$4.61');
    expect(statValue(v, 'unrealized')?.value).toBe('+$2.80');
    const aaa = v.holdings.find(h => h.symbol === 'AAA');
    const bbb = v.holdings.find(h => h.symbol === 'BBB');
    expect(aaa?.estimate).toBe(false);
    expect(aaa?.priceText).toBe('$13.00');
    expect(aaa?.priceTip).toBe('Closing price on Oct 6, 2026');
    expect(bbb?.estimate).toBe(true);
  });

  it('holdings keep only the newest mark when several are given', () => {
    const h = holdings(sortOrders([A]), [MARK_AAA, { symbol: 'AAA', date: '2026-10-01', close: 9 }]);
    expect(h.rows[0].priceText).toBe('$13.00');
  });

  it('uses the nightly series when it exists, with no extra point when no order is newer', () => {
    const v = overview({
      orders: [A, B, C],
      equity: [eqRow('2026-10-06', 4.61, 0.39), eqRow('2026-10-05', 4, 0.39)],
      marks: [MARK_AAA],
      today: TODAY,
    });
    if (v.empty) throw new Error('expected orders');
    expect(v.chart.source).toBe('nightly');
    expect(v.chart.live).toBe(false);
    expect(v.chart.pricesAsOf).toBe('2026-10-06');
    expect(v.chart.series[0].points.map(p => p[0])).toEqual(['2026-10-05', '2026-10-06']);
    expect(v.chart.caption).toContain('Prices as of Oct 6, 2026.');
    expect(v.chart.xDomain).toBeUndefined();
  });

  it('adds a point for today when an uploaded order is newer than the nightly prices', () => {
    const v = overview({
      orders: [A, B, C, D],
      equity: [eqRow('2026-10-05', 4, 0.39), eqRow('2026-10-06', 4.61, 0.39)],
      marks: [MARK_AAA],
      today: TODAY,
    });
    if (v.empty) throw new Error('expected orders');
    expect(v.chart.live).toBe(true);
    const pts = v.chart.series[0].points;
    expect(pts[pts.length - 1][0]).toBe(TODAY);
    expect(pts[pts.length - 1][1]).toBeCloseTo(4.48, 2);
    expect(pts[pts.length - 1][2]).toBe('Oct 7, 2026: +$4.48, with your newest orders');
    expect(v.chart.series[1].points[pts.length - 1][1]).toBeCloseTo(0.52, 2);
    expect(statValue(v, 'total')?.value).toBe('+$4.48');
    expect(v.chart.caption).toContain('newer than those prices');
  });

  it('everything sold: realized only, nothing held, the symbol listed as sold out', () => {
    const v = overview({ orders: [A, SELL_ALL], equity: [], marks: [], today: TODAY });
    if (v.empty) throw new Error('expected orders');
    expect(statValue(v, 'realized')?.value).toBe('+$3.72');
    expect(statValue(v, 'unrealized')?.value).toBe('$0.00');
    expect(statValue(v, 'total')?.value).toBe('+$3.72');
    expect(v.holdings).toEqual([]);
    expect(v.total.value).toBe(0);
    expect(v.closed).toEqual(['AAA']);
  });

  it('holdings P&L adds up to the unrealized stat', () => {
    const v = overview({ orders: [A, B, C, D], equity: [], marks: [MARK_AAA], today: TODAY });
    if (v.empty) throw new Error('expected orders');
    expect(signedUsdText(v.total.pnl)).toBe(statValue(v, 'unrealized')?.value);
  });
});
```
**Impact:** test only.

### Step 4: The rendering component
**File:** `web/app/sean/OverviewBody.tsx` (new)
**Change:** pure, server-renderable JSX for an `Overview` (relative imports, so it renders under vitest). Every button is icon-only Lucide with an `aria-label` equal to its `data-tip`. Green/red appear only on profit/loss numbers (via `Stat` `tone` and `.pos/.neg`).
**Code:**
```tsx
import { ReceiptText } from 'lucide-react';
import Link from 'next/link';
import { Legend, legendFromSeries } from '../../components/sera/charts/Legend';
import { LineChart } from '../../components/sera/charts/LineChart';
import { Section } from '../../components/sera/Section';
import { Stat } from '../../components/sera/Stat';
import type { Overview } from './overview';
import s from './overview.module.css';

export const TRADES_HREF = '/sean/trades';

const ADD_TIP = 'Add your order screenshots';
const ORDERS_TIP = 'See every order';

/** Sean's Overview: numbers + profit-and-loss line, then holdings; or the empty state. */
export function OverviewBody({ v }: { v: Overview }) {
  if (v.empty) {
    return (
      <Section
        eyebrow="Nothing here yet"
        title="No trades yet"
        caption="Add the Order Summary screenshots from Gotrade, or the zip of them, and Sean will add up what you have made or lost after fees."
      >
        <div className={s.emptyBody}>
          <Link href={TRADES_HREF} className="icon-btn solid md" aria-label={ADD_TIP} data-tip={ADD_TIP}>
            <ReceiptText size={21} strokeWidth={1.5} aria-hidden="true" />
          </Link>
        </div>
      </Section>
    );
  }

  const c = v.chart;
  const n = v.holdings.length;
  const holdTitle = n === 0 ? 'Nothing held right now' : `${n} stock${n === 1 ? '' : 's'} worth ${v.total.valueText}`;

  return (
    <div className={s.grid}>
      <Section className={s.pnl} eyebrow="Profit and loss" title={c.title} caption={c.caption}>
        <div className={s.stats}>
          {v.stats.map(st => (
            <Stat key={st.key} size="md" label={st.label} value={st.value} tone={st.tone} sub={st.sub} tip={st.tip} />
          ))}
        </div>
        <LineChart
          ariaLabel={c.ariaLabel}
          series={c.series}
          refLines={c.refLines}
          x="date"
          xTicks={c.xTicks}
          xDomain={c.xDomain}
          yFormat={c.yFormat}
          includeZero
          height={340}
          legend={<Legend items={legendFromSeries(c.series)} />}
        />
      </Section>

      <Section
        className={s.holdings}
        eyebrow="What you hold"
        title={holdTitle}
        caption="Average cost includes the fees you paid to buy. Each stock is valued at the latest closing price Sean has, or at your own last order price (in italics) until the nightly prices come in."
        aside={
          <Link href={TRADES_HREF} className="icon-btn" aria-label={ORDERS_TIP} data-tip={ORDERS_TIP}>
            <ReceiptText size={21} strokeWidth={1.5} aria-hidden="true" />
          </Link>
        }
      >
        {n > 0 ? (
          <div className={s.tableWrap}>
            <table className={s.table}>
              <thead>
                <tr>
                  <th scope="col">Stock</th>
                  <th scope="col">Shares</th>
                  <th scope="col">Average cost</th>
                  <th scope="col">Last price</th>
                  <th scope="col">Value</th>
                  <th scope="col">Profit or loss</th>
                </tr>
              </thead>
              <tbody>
                {v.holdings.map(h => (
                  <tr key={h.symbol}>
                    <th scope="row" className={s.symbol}>{h.symbol}</th>
                    <td className="num">{h.sharesText}</td>
                    <td className="num">{h.avgCostText}</td>
                    <td className={`num ${h.estimate ? s.estimate : ''}`} data-tip={h.priceTip}>{h.priceText}</td>
                    <td className="num">{h.valueText}</td>
                    <td className="num">
                      <span className={h.tone ?? ''}>{h.pnlText}</span>
                      <span className={s.pct}>{h.pnlPctText}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th scope="row">Total</th>
                  <td />
                  <td />
                  <td />
                  <td className="num">{v.total.valueText}</td>
                  <td className="num">
                    <span className={v.total.tone ?? ''}>{v.total.pnlText}</span>
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        ) : (
          <p className={s.note}>Everything you bought has been sold.</p>
        )}
        {v.closed.length > 0 ? <p className={s.note}>Sold out of: {v.closed.join(', ')}.</p> : null}
      </Section>
    </div>
  );
}
```
**Impact:** new component; used by the page in Step 7.

### Step 5: Render tests
**File:** `web/app/sean/OverviewBody.test.tsx` (new)
**Change:** proves the page body renders with zero, one and many orders (the phase exit criterion), the icon-only rule, and green/red only on P&L.
**Code:**
```tsx
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { overview, type OverviewOrder } from './overview';
import { OverviewBody, TRADES_HREF } from './OverviewBody';

let nextId = 1;
function mk(side: 'buy' | 'sell', symbol: string, executedAt: string, price: number, shares: number): OverviewOrder {
  const amount = Math.round(price * shares * 100) / 100;
  const total = Math.round((side === 'buy' ? amount + 0.14 : amount - 0.14) * 100) / 100;
  return {
    id: nextId++,
    side,
    symbol,
    executedAt,
    price,
    shares,
    amountUsd: amount,
    tradingFeeUsd: 0.1,
    regulatoryFeeUsd: 0.02,
    ppnUsd: 0.02,
    totalUsd: total,
  };
}

const render = (orders: OverviewOrder[]) =>
  renderToStaticMarkup(<OverviewBody v={overview({ orders, equity: [], marks: [], today: '2026-10-07' })} />);

/** Every <a> and <button> in the markup: icon-only, with aria-label === data-tip. */
function controls(html: string): Array<{ label: string | undefined; tip: string | undefined; text: string }> {
  return [...html.matchAll(/<(a|button)\b([^>]*)>([\s\S]*?)<\/\1>/g)].map(m => ({
    label: /aria-label="([^"]*)"/.exec(m[2])?.[1],
    tip: /data-tip="([^"]*)"/.exec(m[2])?.[1],
    text: m[3].replace(/<[^>]*>/g, '').trim(),
  }));
}

describe('OverviewBody', () => {
  it('zero orders: an empty state with one icon link to Trades', () => {
    const html = render([]);
    expect(html).toContain('No trades yet');
    expect(html).toContain(`href="${TRADES_HREF}"`);
    expect(html).not.toContain('role="img"');
    const cs = controls(html);
    expect(cs).toHaveLength(1);
    expect(cs[0].label).toBe('Add your order screenshots');
    expect(cs[0].tip).toBe(cs[0].label);
    expect(cs[0].text).toBe('');
  });

  it('one order: the five numbers, a chart and one holding', () => {
    const html = render([mk('buy', 'MU', '2026-09-01T21:30:00+07:00', 10, 2)]);
    expect(html).toContain('Down $0.14 since Sep 2026');
    expect(html).toContain('Total profit or loss');
    expect(html).toContain('Fees as a share of money traded');
    expect(html).toContain('role="img"');
    expect(html).toContain('Break-even');
    expect(html).toContain('1 stock worth $20.00');
    expect(html.match(/<tbody>[\s\S]*<\/tbody>/)?.[0].match(/<tr>/g)).toHaveLength(1);
  });

  it('many orders: one row per open stock, sold-out stocks named, every control icon-only', () => {
    const html = render([
      mk('buy', 'MU', '2026-07-01T21:30:00+07:00', 10, 2),
      mk('buy', 'SPY', '2026-08-03T21:30:00+07:00', 600, 0.1),
      mk('buy', 'PLTR', '2026-08-20T21:30:00+07:00', 150, 0.2),
      mk('sell', 'PLTR', '2026-09-20T21:30:00+07:00', 170, 0.2),
      mk('buy', 'NVDA', '2026-10-01T21:30:00+07:00', 180, 0.15),
    ]);
    expect(html.match(/<tbody>[\s\S]*<\/tbody>/)?.[0].match(/<tr>/g)).toHaveLength(3);
    expect(html).toContain('Sold out of: PLTR.');
    expect(html).toContain('<tfoot>');
    for (const c of controls(html)) {
      expect(c.label).toBeTruthy();
      expect(c.tip).toBe(c.label);
      expect(c.text).toBe('');
    }
  });

  it('colours only profit and loss numbers', () => {
    const html = render([mk('buy', 'MU', '2026-09-01T21:30:00+07:00', 10, 2)]);
    // The fees stat and the fees line never carry a profit/loss colour.
    const feesTile = html.split('Fees paid')[0].split('Unrealized')[1] ?? '';
    expect(feesTile).not.toMatch(/class="[^"]*\b(pos|neg)\b/);
    expect(html).not.toContain('var(--pos)');
    expect(html).not.toContain('var(--neg)');
  });
});
```
**Impact:** test only.

### Step 6: Styles
**File:** `web/app/sean/overview.module.css` (new)
**Change:** Seer v2 tokens only; one column below 1024 px; the table scrolls inside its sheet on a phone (no page-level horizontal scroll).
**Code:**
```css
/* /sean Overview: Seer v2 tokens only. One column below 1024px; on desktop the P&L sheet spans
   the column and the holdings sheet sits under it. The table scrolls sideways inside its sheet. */
.grid { display: flex; flex-direction: column; gap: 12px; }

.pnl, .holdings { min-width: 0; }

.stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 22px 24px; align-content: start; }

.tableWrap { overflow-x: auto; margin: 0 -8px; }
.table { width: 100%; min-width: 640px; border-collapse: collapse; font-size: 16px; }
.table th, .table td {
  padding: 13px 8px;
  text-align: right;
  font-weight: 400;
  white-space: nowrap;
  vertical-align: middle;
  border-bottom: 1px solid var(--hair);
}
.table th:first-child, .table td:first-child { text-align: left; }
.table thead th {
  padding-top: 0;
  padding-bottom: 10px;
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ink-2);
  vertical-align: bottom;
}
.table tbody tr:last-child th, .table tbody tr:last-child td { border-bottom: 0; }
.table tfoot th, .table tfoot td { border-top: 1.25px solid var(--outline); border-bottom: 0; font-weight: 500; }
.table td[data-tip] { cursor: help; }

.symbol { font-weight: 500; letter-spacing: -0.01em; }
.pct { margin-left: 8px; font-size: 14px; color: var(--ink-2); }
.estimate { font-style: italic; color: var(--ink-2); }

.note { font-size: 16px; line-height: 1.5; color: var(--ink-2); }

.emptyBody { display: flex; align-items: center; gap: 16px; }

@media (min-width: 1024px) {
  .stats { grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 24px; }
}

@media (min-width: 1024px) and (max-width: 1239.98px) {
  .stats { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
```
**Impact:** new stylesheet, scoped to the Overview.

### Step 7: Replace the placeholder page
**File:** `web/app/sean/page.tsx` — replace the whole file (Phase 2's placeholder, line 1 to end).
**Change:** gate (pages re-check: layouts do not re-run on client navigation, as in Sera), three reads in parallel, header, body.
**Code:**
```tsx
import type { Metadata } from 'next';
import { PageHeader } from '@/components/sera/PageHeader';
import { ledgerOrders } from '@/lib/sean/data';
import { requireSean } from '@/lib/sean/gate';
import { orderSession } from '@/lib/sean/ledger';
import { equity, marks } from '@/lib/sean/overviewData';
import { overview } from './overview';
import { OverviewBody } from './OverviewBody';

export const metadata: Metadata = { title: 'Overview' };
export const dynamic = 'force-dynamic';

export default async function SeanOverview() {
  await requireSean('/sean');
  const [os, eq, mk] = await Promise.all([ledgerOrders(), equity(), marks()]);
  // Today as a New York date: the date every order placed so far counts on (plan Decisions).
  const v = overview({ orders: os, equity: eq, marks: mk, today: orderSession(new Date().toISOString()) });

  return (
    <>
      <PageHeader
        eyebrow="Sean · your real trades"
        title="Overview"
        lede="Every order you have made on Gotrade, added up: what you have made or lost after fees, and what you hold now."
      />
      <OverviewBody v={v} />
    </>
  );
}
```
`asOf` is deliberately not passed: `PageHeader`'s as-of pill tooltip reads "When the lab record shown here was last written", which is wrong for Sean; the price date lives in the chart caption instead.
**Impact:** `/sean` shows the real Overview. Trades and Plan are untouched.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/sean-gotrade-tracker/web && npm ci && npx tsc --noEmit && npx next build`
**Tests:** `cd /home/miftah/.worktrees/seer/sean-gotrade-tracker/web && npx vitest run app/sean/overview.test.ts app/sean/OverviewBody.test.tsx && npx vitest run`
**Manual check:** `npm run dev` with `web/.env.local`, signed in as the owner:
1. With no `sean_orders` rows (or on a preview DB), `/sean` shows "No trades yet" and one icon button; hovering shows "Add your order screenshots"; it opens `/sean/trades`.
2. Upload one screenshot on Trades, back to `/sean`: five numbers, one dotted point, one holding with an italic last price.
3. Upload the rest (the zip): the line has one dot per trading day from Jun 2025; the stat "Fees paid" equals the sum of the receipts' trading + regulatory + PPN (≈ $9–10 for the 30 receipts in `screenshots_truth.json`); PLTR still shows (only part was sold).
4. After Phase 4's `sean marks` has run once (`gh workflow run sean.yml` or locally), reload: caption says "Prices as of …", no dots on the long series, last prices no longer italic.
5. Phone width (390 px): no horizontal page scroll; the holdings table scrolls inside its sheet.
6. Signed in as anyone else: `/sean` is a 404 (Phase 2's gate, re-checked here by `requireSean`).

**Exit criteria:** `tsc`, the full vitest run and `next build` are green; `overview.test.ts` and `OverviewBody.test.tsx` pass, which shows the page body rendering with zero, one and many orders, from orders alone and from the nightly series (with and without a live point); `/sean` no longer shows Phase 2's placeholder sentence.

## Handoffs

- **Phase 2 (R1):** `PageHeader`'s sign-out form hard-codes `next=%2Fsera` and its as-of tip says "lab record". Sean pages inherit both. If Phase 2 generalises `PageHeader` (a `signOutNext` and `asOfTip` prop) or ships a `SeanHeader`, `page.tsx` here should switch to it; Phase 3 does not edit `web/components/sera/PageHeader.tsx`.
- **Phase 1 (R2):** reconciled — `overview.ts` binds to Phase 1's real `ledger.ts` (`LedgerOrder`, flat `Close[]`, `PnlPoint.*Usd`, `buildLedger().holdings` with `costUsd`/`avgPrice`/`lastOrderPrice`, `orderSession`). The last-order-price fallback the no-prices mode rests on is implemented and tested there.
- **Phase 4 (R2):** the chart reads `sean_equity` as written; it assumes one row per NYSE session from the first order date, `pnl_usd`/`fees_usd` cumulative (contract A). It also expects `sean_marks` to cover every symbol ever held, so `marks()` returns a latest close per held symbol.
- **Phase 5 (R4):** nothing on the Overview links to the plan; a "plan holdings vs. pre-plan holdings" split of the table, if wanted, belongs to Phase 5 or later.
- Not done here (no requirement asks for it): a time-range filter on the chart, a P&L-per-stock history, IDR display.

## Rollback

Revert this phase's commit. That restores Phase 2's placeholder `page.tsx`, removes `overview.ts`, `OverviewBody.tsx`, their tests and `overview.module.css`, and deletes `web/lib/sean/overviewData.ts` (nothing else calls it). No schema or engine change to undo.
