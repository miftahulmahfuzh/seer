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
