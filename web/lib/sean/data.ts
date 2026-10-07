/**
 * Sean's reads and writes on sean_orders. Server only: it opens the connection from lib/db, so
 * client components and tests never import it (they may `import type` from it; types are erased).
 * The Overview's reads live in overviewData.ts and the Plan's in planData.ts; both read the
 * owner's orders through ledgerOrders() here.
 */
import { sql } from '@/lib/db';
import type { LedgerOrder } from './ledger';
import type { SeanOrder } from './types';

type Row = Record<string, any>;

/** One stored order, as the Trades page and the upload route show it. Money in dollars. */
export type OrderRow = {
  id: number;
  side: 'buy' | 'sell';
  orderType: string;
  symbol: string;
  /** Jakarta wall-clock time of the fill, 'YYYY-MM-DDTHH:MM' (the receipt's own WIB time). */
  executedWib: string;
  price: number;
  shares: number;
  amountUsd: number;
  tradingFeeUsd: number;
  regulatoryFeeUsd: number;
  ppnUsd: number;
  /** trading + regulatory + PPN, to the cent. */
  feesUsd: number;
  totalUsd: number;
  /** Gotrade's own 'Net Profit' on a sell; null on buys. */
  netProfitUsd: number | null;
};

const cents = (v: number) => Math.round(v * 100) / 100;
const nn = (v: unknown) => (v === null || v === undefined ? null : Number(v));

function toRow(r: Row): OrderRow {
  const trading = Number(r.trading_fee_usd);
  const regulatory = Number(r.regulatory_fee_usd);
  const ppn = Number(r.ppn_usd);
  return {
    id: Number(r.id),
    side: r.side === 'sell' ? 'sell' : 'buy',
    orderType: String(r.order_type),
    symbol: String(r.symbol),
    executedWib: String(r.executed_wib),
    price: Number(r.price),
    shares: Number(r.shares),
    amountUsd: Number(r.amount_usd),
    tradingFeeUsd: trading,
    regulatoryFeeUsd: regulatory,
    ppnUsd: ppn,
    feesUsd: cents(trading + regulatory + ppn),
    totalUsd: Number(r.total_usd),
    netProfitUsd: nn(r.net_profit_usd),
  };
}

/** Every stored order, newest first. Null when Neon cannot be read, so the page can say so. */
export async function orders(): Promise<OrderRow[] | null> {
  try {
    const rows = await sql`
      SELECT id, side, order_type, symbol,
             to_char(executed_at AT TIME ZONE 'Asia/Jakarta', 'YYYY-MM-DD"T"HH24:MI') AS executed_wib,
             price, shares, amount_usd, trading_fee_usd, regulatory_fee_usd, ppn_usd, total_usd, net_profit_usd
        FROM sean_orders
       ORDER BY executed_at DESC, id DESC`;
    return rows.map(toRow);
  } catch (e) {
    console.error('sean_orders read failed', e);
    return null;
  }
}

/** An order as the shared ledger (lib/sean/ledger.ts) reads it, plus its trade amount. */
export type LedgerRow = LedgerOrder & { amountUsd: number };

/**
 * Every stored order, oldest first (executed_at, then id: the ledger's own order), shaped for
 * buildLedger / pnlSeries / pnlAt. executedAt is ISO 8601 with the receipt's +07:00 offset, so
 * orderSession() reads the New York trade date from it. Throws when the read fails.
 */
export async function ledgerOrders(): Promise<LedgerRow[]> {
  const rows = await sql`
    SELECT id, side, symbol,
           to_char(executed_at AT TIME ZONE 'Asia/Jakarta', 'YYYY-MM-DD"T"HH24:MI:SS') || '+07:00' AS executed_iso,
           price, shares, amount_usd, total_usd, trading_fee_usd, regulatory_fee_usd, ppn_usd
      FROM sean_orders
     ORDER BY sean_orders.executed_at, id`;
  return rows.map((r): LedgerRow => ({
    id: Number(r.id),
    side: r.side === 'sell' ? 'sell' : 'buy',
    symbol: String(r.symbol),
    executedAt: String(r.executed_iso),
    price: Number(r.price),
    shares: Number(r.shares),
    amountUsd: Number(r.amount_usd),
    totalUsd: Number(r.total_usd),
    tradingFeeUsd: Number(r.trading_fee_usd),
    regulatoryFeeUsd: Number(r.regulatory_fee_usd),
    ppnUsd: Number(r.ppn_usd),
  }));
}

/** Every ticker the owner has ever bought or sold, A to Z. Throws when the read fails. */
export async function ownerSymbols(): Promise<string[]> {
  const rows = await sql`SELECT DISTINCT symbol FROM sean_orders ORDER BY symbol`;
  return rows.map(r => String(r.symbol));
}

/** One order by id, or null. Throws when the read fails. */
export async function orderById(id: number): Promise<OrderRow | null> {
  const rows = await sql`
    SELECT id, side, order_type, symbol,
           to_char(executed_at AT TIME ZONE 'Asia/Jakarta', 'YYYY-MM-DD"T"HH24:MI') AS executed_wib,
           price, shares, amount_usd, trading_fee_usd, regulatory_fee_usd, ppn_usd, total_usd, net_profit_usd
      FROM sean_orders
     WHERE id = ${id}`;
  return rows.length > 0 ? toRow(rows[0]) : null;
}

/** The order already read from this exact picture (hex SHA-256), or null. Throws when the read fails. */
export async function orderIdBySha(sha: string): Promise<number | null> {
  const rows = await sql`SELECT id FROM sean_orders WHERE image_sha256 = ${sha} LIMIT 1`;
  return rows.length > 0 ? Number(rows[0].id) : null;
}

/** The digest of the screenshot an order was read from; null when the order is gone. */
export async function orderSha(id: number): Promise<string | null> {
  const rows = await sql`SELECT image_sha256 FROM sean_orders WHERE id = ${id}`;
  return rows.length > 0 && rows[0].image_sha256 ? String(rows[0].image_sha256) : null;
}

/**
 * Stores one read order. Both unique keys dedupe: the same picture (image_sha256) and the same
 * order seen in a different screenshot (symbol, side, executed_at, shares). On either conflict
 * nothing is written and the existing row's id comes back with duplicate = true.
 * Throws when the write fails.
 */
export async function saveOrder(order: SeanOrder, sha: string, raw: unknown): Promise<{ id: number; duplicate: boolean }> {
  const inserted = await sql`
    INSERT INTO sean_orders (
      image_sha256, side, order_type, status, symbol, executed_at, price, shares, amount_usd,
      trading_fee_usd, regulatory_fee_usd, ppn_usd, total_usd, net_profit_usd, fills, raw)
    VALUES (
      ${sha}, ${order.side}, ${order.orderType}, ${order.status}, ${order.symbol},
      ${order.executedAt}::timestamptz, ${order.price}, ${order.shares}, ${order.amountUsd},
      ${order.tradingFeeUsd}, ${order.regulatoryFeeUsd}, ${order.ppnUsd}, ${order.totalUsd},
      ${order.netProfitUsd}, ${JSON.stringify(order.fills)}::jsonb, ${JSON.stringify(raw ?? null)}::jsonb)
    ON CONFLICT DO NOTHING
    RETURNING id`;
  if (inserted.length > 0) return { id: Number(inserted[0].id), duplicate: false };

  const existing = await sql`
    SELECT id FROM sean_orders
     WHERE image_sha256 = ${sha}
        OR (symbol = ${order.symbol} AND side = ${order.side}
            AND executed_at = ${order.executedAt}::timestamptz AND shares = ${order.shares}::numeric)
     ORDER BY id
     LIMIT 1`;
  if (existing.length === 0) throw new Error('sean_orders insert was skipped but no matching row exists');
  return { id: Number(existing[0].id), duplicate: true };
}

/** Deletes one order. False when it was already gone. Throws when the write fails. */
export async function removeOrder(id: number): Promise<boolean> {
  const rows = await sql`DELETE FROM sean_orders WHERE id = ${id} RETURNING id`;
  return rows.length > 0;
}
