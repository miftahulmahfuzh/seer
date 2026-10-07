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
