/**
 * The owner's real ledger: positions, realized and unrealized profit, fees -- from Gotrade orders
 * and daily closes only (receipts never show the cash balance).
 *
 * ONE LEDGER, TWO LANGUAGES. engine/src/seer_engine/sean/ledger.py (Phase 4) does the same math
 * and both pass web/lib/sean/fixtures/ledger.json. Change the math here and you change it there.
 *
 * The math (plan contract B, made exact):
 *  - Orders replay sorted by executedAt (as an instant), then id.
 *  - An order belongs to the NYSE session of its executedAt read in America/New_York: a buy at
 *    03:30 WIB on Jan 8 filled at 15:30 New York time on Jan 7, so it is in Jan 7's session.
 *  - Per symbol, average cost, fees inside the cost:
 *      buy:  shares += s; cost += totalUsd (amount + fees).
 *      sell: s = min(receipt shares, held). If s > 0: avg = cost / held;
 *            proceeds = totalUsd when s is the whole receipt, else totalUsd * s / receipt shares
 *            (the shares sold beyond what Sean knows of, and their money, are ignored);
 *            realized += proceeds - s * avg; cost -= s * avg; shares -= s.
 *            So a sell of a stock Sean never saw bought (held before the owner started
 *            uploading) changes nothing but the fees: booking its whole proceeds as profit
 *            would invent gains the size of the position.
 *      Shares below 1e-9 close the position: shares = cost = 0.
 *  - fees += trading + regulatory + PPN on every order, the clamped part included.
 *  - At date d: value = sum of shares x (the symbol's last close on or before d, else the price of
 *    its last order replayed so far); unrealized = value - sum of cost; pnl = realized + unrealized.
 *  - Money is rounded to cents only at output, each figure on its own (half up); shares keep 9
 *    decimals. So pnlUsd can differ from realizedUsd + unrealizedUsd by a cent.
 *  - Gotrade's own "Net Profit" on a sell (no buy fees in its basis) is NOT this ledger's realized
 *    figure; the Trades page shows it on the sell row.
 *
 * Pure: relative imports only.
 */
import { cents, roundHalfUp } from './money';
import type { OrderSide } from './types';

/** The fields of a stored order the ledger reads. `id` breaks ties between equal timestamps. */
export type LedgerOrder = {
  id: number;
  side: OrderSide;
  symbol: string;
  executedAt: string;
  price: number;
  shares: number;
  totalUsd: number;
  tradingFeeUsd: number;
  regulatoryFeeUsd: number;
  ppnUsd: number;
};

/** One daily close (sean_marks). */
export type Close = { symbol: string; date: string; close: number };

export const DUST_SHARES = 1e-9;

export type Holding = {
  symbol: string;
  /** 9 decimals. */
  shares: number;
  /** Open cost basis, fees included, in cents. */
  costUsd: number;
  /** costUsd / shares, 6 decimals. */
  avgPrice: number;
  /** The price on the last order in this symbol. */
  lastOrderPrice: number;
};

export type LedgerBook = {
  /** Open positions only, by symbol. */
  holdings: Holding[];
  realizedUsd: number;
  feesUsd: number;
};

/** One day of the P&L series; mirrors a sean_equity row. */
export type PnlPoint = {
  date: string;
  valueUsd: number;
  costUsd: number;
  realizedUsd: number;
  unrealizedUsd: number;
  pnlUsd: number;
  feesUsd: number;
};

const NEW_YORK = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});

/** The NYSE session date (YYYY-MM-DD, New York calendar) an order filled in. */
export function orderSession(executedAt: string): string {
  const ms = Date.parse(executedAt);
  if (Number.isNaN(ms)) throw new Error(`not a timestamp: ${executedAt}`);
  const parts = Object.fromEntries(NEW_YORK.formatToParts(ms).map(p => [p.type, p.value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
}

type Position = { shares: number; cost: number; lastPrice: number };
type Queued = LedgerOrder & { ms: number; session: string };

/** Replays orders once, in order, as far as asked. */
class Replay {
  readonly positions = new Map<string, Position>();
  realized = 0;
  fees = 0;
  private readonly queue: Queued[];
  private next = 0;

  constructor(orders: LedgerOrder[]) {
    this.queue = orders
      .map(o => ({ ...o, ms: Date.parse(o.executedAt), session: orderSession(o.executedAt) }))
      .sort((a, b) => a.ms - b.ms || a.id - b.id);
  }

  /** Apply every order whose session is on or before `date` (all of them when null). */
  advanceThrough(date: string | null): void {
    while (this.next < this.queue.length && (date === null || this.queue[this.next].session <= date)) {
      this.apply(this.queue[this.next]);
      this.next += 1;
    }
  }

  private apply(o: Queued): void {
    this.fees += o.tradingFeeUsd + o.regulatoryFeeUsd + o.ppnUsd;
    const p = this.positions.get(o.symbol) ?? { shares: 0, cost: 0, lastPrice: o.price };
    p.lastPrice = o.price;
    if (o.side === 'buy') {
      p.shares += o.shares;
      p.cost += o.totalUsd;
    } else {
      const held = p.shares;
      const s = Math.min(o.shares, held);
      if (s > 0 && o.shares > 0) {
        const avg = p.cost / held;
        const proceeds = s === o.shares ? o.totalUsd : (o.totalUsd * s) / o.shares;
        this.realized += proceeds - s * avg;
        p.cost -= s * avg;
        p.shares -= s;
      }
    }
    if (p.shares < DUST_SHARES) {
      p.shares = 0;
      p.cost = 0;
    }
    this.positions.set(o.symbol, p);
  }
}

type CloseIndex = Map<string, { dates: string[]; closes: number[] }>;

function indexCloses(closes: Close[]): CloseIndex {
  const bySymbol = new Map<string, Close[]>();
  for (const c of closes) {
    const list = bySymbol.get(c.symbol) ?? [];
    list.push(c);
    bySymbol.set(c.symbol, list);
  }
  const index: CloseIndex = new Map();
  for (const [symbol, list] of bySymbol) {
    list.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
    index.set(symbol, { dates: list.map(c => c.date), closes: list.map(c => c.close) });
  }
  return index;
}

/** The symbol's last close on or before `date`, or null. */
function closeOnOrBefore(index: CloseIndex, symbol: string, date: string): number | null {
  const s = index.get(symbol);
  if (!s) return null;
  let lo = 0;
  let hi = s.dates.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (s.dates[mid] <= date) {
      found = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return found < 0 ? null : s.closes[found];
}

function point(replay: Replay, index: CloseIndex, date: string): PnlPoint {
  let value = 0;
  let cost = 0;
  for (const [symbol, p] of replay.positions) {
    if (p.shares === 0) continue;
    value += p.shares * (closeOnOrBefore(index, symbol, date) ?? p.lastPrice);
    cost += p.cost;
  }
  const unrealized = value - cost;
  return {
    date,
    valueUsd: cents(value),
    costUsd: cents(cost),
    realizedUsd: cents(replay.realized),
    unrealizedUsd: cents(unrealized),
    pnlUsd: cents(replay.realized + unrealized),
    feesUsd: cents(replay.fees),
  };
}

/** The book after every order whose session is on or before `through` (all orders when omitted). */
export function buildLedger(orders: LedgerOrder[], through?: string): LedgerBook {
  const replay = new Replay(orders);
  replay.advanceThrough(through ?? null);
  const holdings: Holding[] = [];
  for (const [symbol, p] of replay.positions) {
    if (p.shares === 0) continue;
    holdings.push({
      symbol,
      shares: roundHalfUp(p.shares, 9),
      costUsd: cents(p.cost),
      avgPrice: roundHalfUp(p.cost / p.shares, 6),
      lastOrderPrice: p.lastPrice,
    });
  }
  holdings.sort((a, b) => (a.symbol < b.symbol ? -1 : a.symbol > b.symbol ? 1 : 0));
  return { holdings, realizedUsd: cents(replay.realized), feesUsd: cents(replay.fees) };
}

/** One P&L point per date (YYYY-MM-DD), ascending, duplicates dropped. */
export function pnlSeries(orders: LedgerOrder[], closes: Close[], dates: string[]): PnlPoint[] {
  const replay = new Replay(orders);
  const index = indexCloses(closes);
  const days = [...new Set(dates)].sort();
  return days.map(date => {
    replay.advanceThrough(date);
    return point(replay, index, date);
  });
}

/** The P&L at one date. */
export function pnlAt(orders: LedgerOrder[], closes: Close[], date: string): PnlPoint {
  return pnlSeries(orders, closes, [date])[0];
}
