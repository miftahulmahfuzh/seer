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
 * How often a rule set can act at all: `daily`, `weekly`, `monthly` (a basket picked on the first
 * session of a month and held), `monthly-weekly` (picked monthly, resized weekly) or `unknown`.
 *
 * Mirrors `sim.rules.PRESETS`' `cadence` and `resize_cadence` for every preset the roster can
 * carry (engine/src/seer_engine/sim/rules.py). This is a PLAIN ANSWER TO "when can this sell?",
 * not a calendar: the NYSE holiday list lives in the engine and `lib/session.ts` deliberately
 * does not model it, so nothing here ever names a date.
 *
 * `unknown` for a preset this table has not been taught and for the benchmark (rules_id null),
 * and every caller must read it as "say nothing specific" rather than guess.
 */
export type Cadence = 'daily' | 'weekly' | 'monthly' | 'monthly-weekly' | 'unknown';

const CADENCE: Record<string, Cadence> = {
  'design-v0': 'daily',
  'design-v0-gotrade': 'daily',
  'daily-switch': 'daily',
  'daily-switch-tbill': 'daily',
  'swing-t10': 'daily',
  'swing-t20': 'daily',
  'swing-t20-open': 'daily',
  'weekly-hold': 'weekly',
  'weekly-hold-frac-gotrade-tband-cash': 'weekly',
  'monthly-hold': 'monthly',
  'monthly-hold-tbill': 'monthly',
  'monthly-hold-frac': 'monthly',
  'monthly-hold-frac-gotrade': 'monthly',
  'monthly-hold-frac-gotrade-tband': 'monthly',
  'monthly-hold-frac-gotrade-tband-cash': 'monthly',
  'monthly-rank-weekly-resize': 'monthly-weekly',
  'monthly-rank-weekly-resize-tbill': 'monthly-weekly',
  'monthly-rank-weekly-resize-frac': 'monthly-weekly',
  'monthly-rank-weekly-resize-frac-gotrade': 'monthly-weekly',
};

export function cadenceOf(rulesId: string | null | undefined): Cadence {
  return (typeof rulesId === 'string' && CADENCE[rulesId]) || 'unknown';
}

/** When this rule set can next change what it holds, in words and without a date. */
export function sellsWhen(c: Cadence): string | null {
  if (c === 'daily') return 'it decides every session';
  if (c === 'weekly') return 'it picks a new basket on the first session of each week';
  if (c === 'monthly') return 'it picks a new basket on the first session of each month and holds it until then';
  if (c === 'monthly-weekly') {
    return 'it picks a new basket on the first session of each month and checks the sizes weekly';
  }
  return null;
}

/**
 * Mirror of the engine's `RESIZE_BAND = Decimal("0.01")` (engine/src/seer_engine/sim/rules.py):
 * on the equity basis (every rule set not in TARGET_BAND_RULES) a held position is only traded
 * back to its target when it is off by at least this share of paper equity (sim/book.py skips the
 * trade when the gap is strictly smaller).
 */
export const RESIZE_BAND = 0.01;

/**
 * Mirror of the engine's `TARGET_RESIZE_BAND = Decimal("0.20")` (sim/rules.py): for a rule set in
 * TARGET_BAND_RULES a held position is only traded back when it is off by at least this share of
 * its OWN target value (weight × equity), not of the whole account. In a 20-name book 1% of
 * equity is a fifth of one holding; in a 50-name book it is half of one, which is why the engine
 * grew the second basis.
 */
export const TARGET_RESIZE_BAND = 0.2;

/**
 * Engine rule sets with `resize_basis="target"` (sim/rules.py PRESETS). Their band is
 * TARGET_RESIZE_BAND of each holding target instead of RESIZE_BAND of equity. A hand mirror,
 * guarded by engine/tests/test_sean_mirrors.py; append when such a preset is added.
 */
export const TARGET_BAND_RULES: readonly string[] = [
  'monthly-hold-frac-gotrade-tband',
  'monthly-hold-frac-gotrade-tband-cash',
  'weekly-hold-frac-gotrade-tband-cash',
  // 023: the same target basis with the band shut (resize_band = 0), so every non-zero gap is
  // beyond it and every holding is traded back to its slot each month. FULL50-FR-GT runs it.
  'monthly-hold-frac-gotrade-tband00',
];

/**
 * Engine rule sets that name their OWN `resize_band`, overriding the basis constant. The lever
 * lives in sim/rules.py LEVERS_SINCE_PINS at its no-op `None`, which means "use the basis
 * constant"; a preset that sets it explicitly is saying something the two constants above cannot
 * express. A hand mirror of every preset whose `resize_band is not None`, guarded by
 * engine/tests/test_resize_band_pins.py -- which goes red the day a preset names a band, so that
 * this table learns the lever before a paper strategy can carry it.
 *
 * 023 is the first: the band-zero tape, where every non-zero gap is beyond the band, so a holding
 * is traded back to its slot every month rather than only when it has drifted a fifth of the way.
 */
export const RULE_SET_BANDS: Readonly<Record<string, number>> = {
  'monthly-hold-frac-gotrade-tband00': 0,
};

/** What a resize gap is measured against: the whole account, or the holding's own target. */
export type ResizeBasis = 'equity' | 'target';

/**
 * The band fraction a rule set applies, on its own basis: its named band where it names one,
 * otherwise the constant its basis implies. Multiply by the holding's target on the target basis,
 * or by equity on the equity basis -- exactly what sim/book.py does.
 */
export function bandFractionOf(rulesId: string | null | undefined): number {
  const named = typeof rulesId === 'string' ? RULE_SET_BANDS[rulesId] : undefined;
  if (named !== undefined) return named;
  return resizeBasisOf(rulesId) === 'target' ? TARGET_RESIZE_BAND : RESIZE_BAND;
}

/** The engine `resize_basis` of a rule set: 'target' for TARGET_BAND_RULES, else 'equity'. */
export function resizeBasisOf(rulesId: string | null | undefined): ResizeBasis {
  return typeof rulesId === 'string' && TARGET_BAND_RULES.includes(rulesId) ? 'target' : 'equity';
}

/**
 * What one book order means against what is held now, in dollars at tonight's marks and equity.
 * `buy`: not held, the whole target is bought. `add` / `trim`: held, the gap to the target.
 * `none`: held and inside the band (RESIZE_BAND of equity, or TARGET_RESIZE_BAND of the target on
 * the target basis), so the engine leaves it alone. `usd` is always >= 0 (0 for `none`).
 */
export type SizeChange = { action: 'buy' | 'add' | 'trim' | 'none'; usd: number };

/**
 * The order's dollar change: target `weight × equity` against `heldUsd`, the dollar value held now
 * (shares × current mark), or null when the symbol is not held. Approximate on purpose: the engine
 * sizes at the open's equity and the target's last close, the page at tonight's equity and marks.
 * `basis` is the rule set's (resizeBasisOf); the band it picks matches sim/book.py's.
 */
export function sizeChange(
  weight: number, equity: number, heldUsd: number | null, basis: ResizeBasis = 'equity',
): SizeChange {
  const target = weight * equity;
  if (heldUsd === null) return { action: 'buy', usd: Math.max(0, target) };
  const gap = target - heldUsd;
  const band = basis === 'target' ? TARGET_RESIZE_BAND * target : RESIZE_BAND * equity;
  if (Math.abs(gap) < band) return { action: 'none', usd: 0 };
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
  basis: ResizeBasis = 'equity',
): SizeChange | null {
  if (weight === null || equity === null) return null;
  return sizeChange(weight, equity, held.get(symbol) ?? null, basis);
}

/** The words in the cell: 'Buy about $40.00', 'Add about $6.12', 'Trim about $9.80', 'No change'. */
export function sizeLabel(c: SizeChange): string {
  if (c.action === 'buy') return `Buy about ${usd(c.usd)}`;
  if (c.action === 'add') return `Add about ${usd(c.usd)}`;
  if (c.action === 'trim') return `Trim about ${usd(c.usd)}`;
  return 'No change';
}

/** The cell's tooltip, in plain words. */
export function sizeTip(c: SizeChange, basis: ResizeBasis = 'equity'): string {
  if (c.action === 'buy') return 'Not held yet: the whole amount is bought at the open';
  if (c.action === 'add') return 'Held, but below its target: about this much more is bought at the open';
  if (c.action === 'trim') return 'Held, but above its target: about this much is sold at the open';
  if (basis === 'target') {
    return `Off its target by less than ${Math.round(TARGET_RESIZE_BAND * 100)}% of that target, too little to trade`;
  }
  return 'Off its target by less than 1% of paper equity, too little to trade';
}
