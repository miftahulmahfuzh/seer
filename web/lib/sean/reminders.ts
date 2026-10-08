/**
 * Sean's buy/sell reminders (plan phase 5, requirement R4; cash added in the Gotrade fee rebuild,
 * phase 10 / R9).
 *
 * The followed roster method's newest picks (`book_targets` at its latest session) against the
 * owner's PLAN holdings: the orders whose New York trade date (ledger orderSession) is on or after
 * `sean_link.since`, run through the one ledger (contract B, ./ledger). Holdings from before
 * `since` are never part of the plan, so they never get a sell reminder.
 *
 * Rules:
 *  - sell: a plan holding the picks no longer name. The whole plan position, never more.
 *  - buy:  a pick the plan does not hold, sized weight × plan size (no amount without a plan size).
 *  - add / trim: only when the method's rules resize (engine `resize=True`), measured at the
 *    pick's decision price like the engine, and only when the gap is at least MIN_TRADE_USD and at
 *    least RESIZE_BAND of the plan (Gotrade's minimum fee makes smaller trades waste money).
 *  - done: an uploaded order of the same side and stock whose New York trade date is on or after
 *    the decision session, or a row the owner marked done for that decision.
 *  - no picks at all: no reminders (an empty decision is not an order to sell everything).
 *
 * PLAN SIZE IS HOLDINGS PLUS CASH. The owner adds 5,000,000 IDR to his wallet every month, and a
 * plan size taken from holdings alone cannot see it: on 2026-11-02 that is $280.16 of real money
 * and every buy would be sized about a third short. `cashUsd` comes from ./cash, which derives the
 * wallet from the contribution schedule and the plan's own orders, because ./ledger can never read
 * a balance off a receipt. `budgetUsd` (sean_link.budget_usd) still overrides everything when the
 * owner types a number in.
 *
 * Orders are always DOLLAR-DENOMINATED, never share counts: prices drift between the decision's
 * close and the next open, and a fractional dollar order absorbs that drift where a share count
 * does not. The roster's book rules are already `-frac`.
 *
 * Pure: no database, relative imports only (vitest has no `@/` alias).
 */
import { RESIZE_BAND } from '../cadence';
import { buildLedger, orderSession, type LedgerOrder } from './ledger';

/**
 * An add or a trim smaller than this is not worth Gotrade's fees. Derived from the schedule's own
 * two constants (engine sim/costs.py, current regime: `trading_rate = 0.002`, `trading_min = 0.10`),
 * not chosen: the $0.10 floor charges a premium of `0.10 − 0.002 × amount` over what the rate alone
 * would take, and that premium stops exceeding the rate's own charge at
 * `0.10 / (2 × 0.002)` = $25. So at $25 the floor at most doubles the trading fee; below it, it
 * more than doubles it, and at $10 it quintuples it ($0.10 charged where the rate earns $0.02).
 *
 * Measured round trip (buy fee + sell fee over the amount, `costs.fee_parts` on the current
 * regime, 2026-10-08): $10 pays 2.500%, $25 pays 1.080%, $50 pays 0.620%, $560 pays 0.534%.
 *
 * Not $50, which is where the floor stops binding altogether (0.10 / 0.002): the owner's plan size
 * on 2026-11-02 is $838.16 over 20 names, a $41.91 slot, and an add's gap can never exceed its own
 * slot -- a $50 floor would make an add structurally impossible rather than merely expensive.
 */
export const MIN_TRADE_USD = 25;

/** Shares below this are a closed position (contract B). */
export const CLOSED_SHARES = 1e-9;

/** Float noise allowed when the plan's shares are subtracted from all shares. */
const OUTSIDE_EPS = 1e-6;

/**
 * Engine rule sets with `resize=True` (engine/src/seer_engine/sim/rules.py PRESETS): on a decision
 * session they trade a held pick back to its weight. A hand mirror, like cadence.ts's
 * SPLIT_CADENCE_RULES; append when a resizing preset is added to the engine.
 */
export const RESIZING_RULES: readonly string[] = [
  'monthly-hold',
  'monthly-hold-tbill',
  'monthly-hold-frac',
  'weekly-hold',
  'monthly-rank-weekly-resize',
  'monthly-rank-weekly-resize-tbill',
  'monthly-rank-weekly-resize-frac',
  // Gotrade real-fee twins of the two fractional presets (Sean phase 7); they resize the same way.
  'monthly-hold-frac-gotrade',
  'monthly-rank-weekly-resize-frac-gotrade',
];

/** Does this rule set trade a held pick back to its weight? */
export function resizes(rulesId: string | null | undefined): boolean {
  return typeof rulesId === 'string' && RESIZING_RULES.includes(rulesId);
}

export type Side = 'buy' | 'sell';
export type ReminderAction = 'buy' | 'add' | 'trim' | 'sell';

/** One pick of the method's latest decision. `last` is the decision's price (book_targets.last_price). */
export type Target = { symbol: string; weight: number; last: number };

/** The fields of a plan order the reminders read. LedgerOrder satisfies it. */
export type PlanOrderLite = { symbol: string; side: Side; executedAt: string; price: number };

/** A reminder the owner marked done by hand (sean_reminder_marks; `side` is its `action` column). */
export type ReminderMark = { sessionDate: string; symbol: string; side: Side };

/** Why a reminder counts as done: an uploaded order, the owner's mark, or not done (null). */
export type Done = 'order' | 'mark' | null;

export type Reminder = {
  /** `${sessionDate}:${symbol}:${side}`: unique within one decision (a stock gets one reminder). */
  key: string;
  action: ReminderAction;
  /** What an order or a mark must be to clear it: buy for buy/add, sell for sell/trim. */
  side: Side;
  symbol: string;
  /** About how many dollars; null for a buy when there is no plan size yet. */
  usd: number | null;
  /** sell only: the plan's shares, all of which are sold. null otherwise. */
  shares: number | null;
  /** The pick's weight; null for a sell (no longer picked). */
  weight: number | null;
  /** The owner also holds this stock from before the plan (not counted, never sold by Sean). */
  alsoOutside: boolean;
  done: Done;
};

/** One stock the plan holds, valued at the decision price when picked, else the latest close. */
export type PlanHolding = { symbol: string; shares: number; price: number; value: number; picked: boolean };

export type ReminderInput = {
  /** The decision's session (book_targets.session_date), YYYY-MM-DD. */
  sessionDate: string;
  /** The decision's picks, in rank order. Empty: no reminders. */
  targets: readonly Target[];
  /** resizes(rulesId) of the followed method. */
  resizes: boolean;
  /** Plan shares per stock (sharesBySymbol over planOrders). */
  held: ReadonlyMap<string, number>;
  /** Shares held from outside the plan per stock (outsideShares). */
  outside: ReadonlyMap<string, number>;
  /** Latest daily close per stock (sean_marks). */
  closes: ReadonlyMap<string, number>;
  /** sean_link.budget_usd: the owner's manual override; null = derive the plan size. */
  budgetUsd: number | null;
  /**
   * The wallet (./cash cashUsd): deposits so far less what the plan's orders spent. null when it
   * cannot be derived, and then the plan size falls back to holdings alone, as it did before
   * phase 10. May be negative.
   */
  cashUsd: number | null;
  /** The plan's orders, oldest first. */
  orders: readonly PlanOrderLite[];
  /** The owner's done marks (any decision; only this decision's count). */
  marks: readonly ReminderMark[];
};

export type ReminderPlan = {
  /** Σ plan shares × price. */
  planValue: number;
  /** The wallet as it was given (ReminderInput.cashUsd), passed through for the page. */
  cashUsd: number | null;
  /**
   * What each pick's weight is multiplied by: budgetUsd when the owner set one, else
   * planValue + cashUsd, else planValue, else null (and then buys carry no amount).
   */
  planSize: number | null;
  /** The plan's open positions, largest first. */
  holdings: PlanHolding[];
  /** Every reminder, sells first (they free the money for buys), then trims, buys, adds. */
  reminders: Reminder[];
  open: Reminder[];
  done: Reminder[];
};

const ACTION_ORDER: Record<ReminderAction, number> = { sell: 0, trim: 1, buy: 2, add: 3 };

/** The side an order must have to clear a reminder of this action. */
export const sideOf = (action: ReminderAction): Side => (action === 'buy' || action === 'add' ? 'buy' : 'sell');

/** The orders that belong to the plan: New York trade date (orderSession) on or after `since`. */
export function planOrders<T extends { executedAt: string }>(orders: readonly T[], since: string): T[] {
  return orders.filter(o => orderSession(o.executedAt) >= since);
}

/** Open shares per stock after `orders`, by the one ledger (contract B; open positions only). */
export function sharesBySymbol(orders: readonly LedgerOrder[]): Map<string, number> {
  const out = new Map<string, number>();
  for (const h of buildLedger([...orders]).holdings) {
    if (h.shares >= CLOSED_SHARES) out.set(h.symbol, h.shares);
  }
  return out;
}

/** Shares held beyond the plan's, per stock: all holdings minus plan holdings. */
export function outsideShares(
  all: ReadonlyMap<string, number>, plan: ReadonlyMap<string, number>,
): Map<string, number> {
  const out = new Map<string, number>();
  for (const [symbol, shares] of all) {
    const extra = shares - (plan.get(symbol) ?? 0);
    if (extra >= OUTSIDE_EPS) out.set(symbol, extra);
  }
  return out;
}

/** The last order price per stock (orders oldest first, so the later one wins). */
export function lastPrices(orders: readonly PlanOrderLite[]): Map<string, number> {
  const out = new Map<string, number>();
  for (const o of orders) out.set(o.symbol, o.price);
  return out;
}

function doneBy(symbol: string, side: Side, input: ReminderInput): Done {
  const ordered = input.orders.some(
    o => o.symbol === symbol && o.side === side && orderSession(o.executedAt) >= input.sessionDate,
  );
  if (ordered) return 'order';
  const marked = input.marks.some(
    m => m.symbol === symbol && m.side === side && m.sessionDate === input.sessionDate,
  );
  return marked ? 'mark' : null;
}

/** The reminders for one decision against the plan. See the module comment for the rules. */
export function buildReminders(input: ReminderInput): ReminderPlan {
  const targetBy = new Map<string, Target>();
  for (const t of input.targets) if (!targetBy.has(t.symbol)) targetBy.set(t.symbol, t);
  const fallback = lastPrices(input.orders);
  const priceOf = (symbol: string): number =>
    targetBy.get(symbol)?.last ?? input.closes.get(symbol) ?? fallback.get(symbol) ?? 0;
  const heldOf = (symbol: string): number => {
    const shares = input.held.get(symbol) ?? 0;
    return shares >= CLOSED_SHARES ? shares : 0;
  };
  const holdsOutside = (symbol: string): boolean => (input.outside.get(symbol) ?? 0) >= OUTSIDE_EPS;

  const holdings: PlanHolding[] = [];
  for (const symbol of input.held.keys()) {
    const shares = heldOf(symbol);
    if (shares === 0) continue;
    const price = priceOf(symbol);
    holdings.push({ symbol, shares, price, value: shares * price, picked: targetBy.has(symbol) });
  }
  holdings.sort((a, b) => b.value - a.value || a.symbol.localeCompare(b.symbol));
  const planValue = holdings.reduce((sum, h) => sum + h.value, 0);
  // Holdings plus the wallet: the money that is going to be spread over the picks, not just the
  // money already in them. The owner's override wins; cash that cannot be derived falls back to
  // holdings alone, which is what this did before phase 10.
  const funded = input.cashUsd === null ? planValue : planValue + input.cashUsd;
  const planSize =
    input.budgetUsd !== null && input.budgetUsd > 0 ? input.budgetUsd : funded > 0 ? funded : null;

  const drafts: Omit<Reminder, 'key' | 'done'>[] = [];
  if (targetBy.size > 0) {
    for (const h of holdings) {
      if (h.picked) continue;
      drafts.push({
        action: 'sell', side: 'sell', symbol: h.symbol, usd: h.value > 0 ? h.value : null,
        shares: h.shares, weight: null, alsoOutside: holdsOutside(h.symbol),
      });
    }
    for (const t of targetBy.values()) {
      const shares = heldOf(t.symbol);
      if (shares === 0) {
        drafts.push({
          action: 'buy', side: 'buy', symbol: t.symbol, usd: planSize === null ? null : t.weight * planSize,
          shares: null, weight: t.weight, alsoOutside: holdsOutside(t.symbol),
        });
        continue;
      }
      if (!input.resizes || planSize === null) continue;
      const gap = t.weight * planSize - shares * t.last;
      if (Math.abs(gap) < Math.max(MIN_TRADE_USD, RESIZE_BAND * planSize)) continue;
      const action: ReminderAction = gap > 0 ? 'add' : 'trim';
      drafts.push({
        action, side: sideOf(action), symbol: t.symbol, usd: Math.abs(gap),
        shares: null, weight: t.weight, alsoOutside: holdsOutside(t.symbol),
      });
    }
  }
  // Array.prototype.sort is stable: within one action, rank order (buys/adds) and size order (sells) hold.
  drafts.sort((a, b) => ACTION_ORDER[a.action] - ACTION_ORDER[b.action]);
  const reminders: Reminder[] = drafts.map(d => ({
    ...d,
    key: `${input.sessionDate}:${d.symbol}:${d.side}`,
    done: doneBy(d.symbol, d.side, input),
  }));
  return {
    planValue,
    cashUsd: input.cashUsd,
    planSize,
    holdings,
    reminders,
    open: reminders.filter(r => r.done === null),
    done: reminders.filter(r => r.done !== null),
  };
}
