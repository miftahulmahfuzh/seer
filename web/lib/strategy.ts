// Pure helpers for `strategies` rows: engine, backtest gate, short label and Claude twins. No
// database access, so pages, metrics and tests can import them without a connection.

/** How a strategy trades (migration 003, `strategies.engine`). */
export type Engine = 'bracket' | 'book' | 'benchmark';

/**
 * `strategies.params->'backtest_gate'` (contract C2): did the strategy pass its backtest gate?
 * `applicable` is false only for a strategy the backtest item does not apply to (design §1 item 5:
 * C, an LLM strategy, cannot be backtested without look-ahead). Not applicable never counts as passed.
 *
 * `twin` marks the other reason a backtest cannot apply: a Claude twin (Seer Adversarial, contract
 * C2). Claude already knows how the past turned out, so no backtest of a twin can be honest. It is
 * only ever set by `TWIN_GATE`, which `gateOf` hands every row with `twin_of`. The stored jsonb is
 * never read for it, so a twin cannot carry a pass from anywhere.
 *
 * The verdict only. The prose `note` the engine used to ship alongside it is deliberately dropped
 * here and never reaches a payload or a page (owner, 2026-10-07): the checklist states the verdict,
 * and the reasoning behind it belongs on the method's own Sera page, one click from the pick's name.
 */
export type Gate = { passed: boolean; applicable: boolean; twin?: true };

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

/** A Claude twin's gate: never passed, never applicable, and saying why. Frozen so no caller edits it. */
export const TWIN_GATE: Gate = Object.freeze({ passed: false, applicable: false, twin: true as const });

/**
 * The gate a row shows. For a twin it is `TWIN_GATE`, whatever `params` holds. A twin's params is
 * `'{}'` until its first paper night freezes the spec, and `parseGate('{}')` would read
 * "applicable, not passed", so for that one night the sheet would claim a backtest could still pass.
 */
export function gateOf(raw: unknown, twinOf: string | null): Gate {
  return twinOf !== null ? TWIN_GATE : parseGate(raw);
}

/** 'F4 · Momentum' -> 'F4', 'A · Quant' -> 'A', 'SPY' -> 'SPY'; the id when the name has no head. */
export function shortLabel(name: string, id: string): string {
  const head = name.split('·')[0].trim();
  return head === '' ? id : head;
}

/**
 * Does this strategy run the nightly news check (strategy C, handover D1/D6)? True when its frozen
 * spec names the C object, or for the roster id 'C' before `paper` has written a spec. Never for a
 * Claude twin: a twin's filter is Claude's verdicts, not C's news check, so Positions must not show
 * news-check rows under its orders even if its spec names an object C also uses.
 */
export function checksNews(id: string, specObject: unknown, twinOf: string | null = null): boolean {
  if (twinOf !== null) return false;
  return specObject === 'STRATEGY_C' || id === 'C';
}

/**
 * `strategies.twin_of` (migration 027): the ORIGINAL's id for a Claude twin, null for every other
 * row. Anything that is not a non-empty string reads as null. That includes the missing key on a
 * DB that has not applied 027 yet, so a bad read gives a plain strategy and never a phantom twin.
 */
export function twinOfRow(raw: unknown): string | null {
  return typeof raw === 'string' && raw !== '' ? raw : null;
}

/** The fields the twin helpers read: a structural subset of `lib/data`'s `Strategy`. */
export type TwinIn = { id: string; twinOf?: string | null };

/**
 * The original `st` hangs off on this list, or null. It is null when `st` is not a twin, when its
 * original is not on the list (a twin shown without its original stands on its own), or when the
 * original is itself a twin. Contract C2 never makes a twin of a twin, and treating one as a plain
 * row keeps every list finite and every row in it.
 */
export function attachedOriginal<T extends TwinIn>(st: T, byId: Map<string, T>): T | null {
  if (st.twinOf === null || st.twinOf === undefined) return null;
  const o = byId.get(st.twinOf);
  return o !== undefined && (o.twinOf === null || o.twinOf === undefined) ? o : null;
}

/**
 * `rows` with each attached twin moved to sit directly after its original. Everything else keeps
 * its order, and nothing is added or dropped. Twins of the same original keep their own relative
 * order. Phase 2 gives a twin whatever `sort` it gives it, and the board must not depend on that:
 * "next to its original" is the owner's rule (decision 8), so the order is set here, once.
 */
export function orderTwins<T extends TwinIn>(rows: T[]): T[] {
  const byId = new Map(rows.map(r => [r.id, r]));
  const twinsOf = new Map<string, T[]>();
  for (const r of rows) {
    const o = attachedOriginal(r, byId);
    if (o) twinsOf.set(o.id, [...(twinsOf.get(o.id) ?? []), r]);
  }
  const out: T[] = [];
  for (const r of rows) {
    if (attachedOriginal(r, byId)) continue;
    out.push(r, ...(twinsOf.get(r.id) ?? []));
  }
  return out;
}
