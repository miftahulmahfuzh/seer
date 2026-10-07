// Pure helpers for `strategies` rows: engine, backtest gate and short label. No database access,
// so pages, metrics and tests can import them without a connection.

/** How a strategy trades (migration 003, `strategies.engine`). */
export type Engine = 'bracket' | 'book' | 'benchmark';

/**
 * `strategies.params->'backtest_gate'` (contract C2): did the strategy pass its backtest gate?
 * `applicable` is false only for a strategy the backtest item does not apply to (design §1 item 5:
 * C, an LLM strategy, cannot be backtested without look-ahead). Not applicable never counts as passed.
 *
 * The verdict only. The prose `note` the engine used to ship alongside it is deliberately dropped
 * here and never reaches a payload or a page (owner, 2026-10-07): the checklist states the verdict,
 * and the reasoning behind it belongs on the method's own Sera page, one click from the pick's name.
 */
export type Gate = { passed: boolean; applicable: boolean };

const ENGINES: readonly string[] = ['bracket', 'book', 'benchmark'];

/** The row's engine. Rows written before migration 003 have none: benchmark when flagged, else bracket. */
export function engineOf(engine: unknown, isBenchmark: boolean): Engine {
  if (typeof engine === 'string' && ENGINES.includes(engine)) return engine as Engine;
  return isBenchmark ? 'benchmark' : 'bracket';
}

/**
 * Reads the gate from params. Missing or malformed reads as not passed and applicable: a pass is
 * never assumed, and only an explicit `applicable: false` marks the backtest item not applicable.
 * A `note` on the stored jsonb is ignored: rows written before 2026-10-07 still carry one, and
 * this is the boundary where it stops — nothing downstream can render what it never receives.
 */
export function parseGate(raw: unknown): Gate {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) return { passed: false, applicable: true };
  const g = raw as Record<string, unknown>;
  const applicable = g.applicable !== false;
  return { passed: applicable && g.passed === true, applicable };
}

/** 'F4 · Momentum' -> 'F4', 'A · Quant' -> 'A', 'SPY' -> 'SPY'; the id when the name has no head. */
export function shortLabel(name: string, id: string): string {
  const head = name.split('·')[0].trim();
  return head === '' ? id : head;
}

/**
 * Does this strategy run the nightly news check (strategy C, handover D1/D6)? True when its frozen
 * spec names the C object, or for the roster id 'C' before `paper` has written a spec.
 */
export function checksNews(id: string, specObject: unknown): boolean {
  return specObject === 'STRATEGY_C' || id === 'C';
}
