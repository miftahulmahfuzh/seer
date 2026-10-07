// Pure helpers for split-cadence book strategies: rules that pick their stocks on the first session
// of each month and check how much to hold on the first session of each week (engine
// `sim/rules.py` MONTHLY_RANK_WEEKLY_RESIZE*). No database access, so pages and tests import them
// without a connection.
import { usd } from './format';

/** `strategies.rules_id` values whose basket is picked monthly and resized weekly. */
export const SPLIT_CADENCE_RULES: readonly string[] = [
  'monthly-rank-weekly-resize',
  'monthly-rank-weekly-resize-tbill',
  'monthly-rank-weekly-resize-frac',
  'monthly-rank-weekly-resize-frac-gotrade',
];

/** Does this strategy pick its stocks monthly and check how much to hold weekly? */
export function picksMonthlySizesWeekly(rulesId: string | null | undefined): boolean {
  return typeof rulesId === 'string' && SPLIT_CADENCE_RULES.includes(rulesId);
}

/**
 * Mirror of the engine's `RESIZE_BAND = Decimal("0.01")` (engine/src/seer_engine/sim/rules.py):
 * a held position is only traded back to its target when it is off by at least this share of
 * paper equity (sim/book.py skips the trade when the gap is strictly smaller).
 */
export const RESIZE_BAND = 0.01;

/**
 * What one book order means against what is held now, in dollars at tonight's marks and equity.
 * `buy`: not held, the whole target is bought. `add` / `trim`: held, the gap to the target.
 * `none`: held and off by less than RESIZE_BAND of equity, so the engine leaves it alone.
 * `usd` is always >= 0 (0 for `none`).
 */
export type SizeChange = { action: 'buy' | 'add' | 'trim' | 'none'; usd: number };

/**
 * The order's dollar change: target `weight × equity` against `heldUsd`, the dollar value held now
 * (shares × current mark), or null when the symbol is not held. Approximate on purpose: the engine
 * sizes at the open's equity and the target's last close, the page at tonight's equity and marks.
 */
export function sizeChange(weight: number, equity: number, heldUsd: number | null): SizeChange {
  const target = weight * equity;
  if (heldUsd === null) return { action: 'buy', usd: Math.max(0, target) };
  const gap = target - heldUsd;
  if (Math.abs(gap) < RESIZE_BAND * equity) return { action: 'none', usd: 0 };
  return gap > 0 ? { action: 'add', usd: gap } : { action: 'trim', usd: -gap };
}

/** Dollar value held now per symbol (the sum, should a symbol ever appear twice). */
export function heldUsd(holdings: readonly { symbol: string; value: number }[]): Map<string, number> {
  const out = new Map<string, number>();
  for (const h of holdings) out.set(h.symbol, (out.get(h.symbol) ?? 0) + h.value);
  return out;
}

/** `sizeChange` for one order row; null when the weight or the paper equity is not known. */
export function orderSizeChange(
  weight: number | null, equity: number | null, symbol: string, held: ReadonlyMap<string, number>,
): SizeChange | null {
  if (weight === null || equity === null) return null;
  return sizeChange(weight, equity, held.get(symbol) ?? null);
}

/** The words in the cell: 'Buy about $40.00', 'Add about $6.12', 'Trim about $9.80', 'No change'. */
export function sizeLabel(c: SizeChange): string {
  if (c.action === 'buy') return `Buy about ${usd(c.usd)}`;
  if (c.action === 'add') return `Add about ${usd(c.usd)}`;
  if (c.action === 'trim') return `Trim about ${usd(c.usd)}`;
  return 'No change';
}

/** The cell's tooltip, in plain words. */
export function sizeTip(c: SizeChange): string {
  if (c.action === 'buy') return 'Not held yet: the whole amount is bought at the open';
  if (c.action === 'add') return 'Held, but below its target: about this much more is bought at the open';
  if (c.action === 'trim') return 'Held, but above its target: about this much is sold at the open';
  return 'Off its target by less than 1% of paper equity, too little to trade';
}
