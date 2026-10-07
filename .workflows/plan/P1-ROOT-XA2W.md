> Adopted from `SEAN_GOTRADE_TRACKER_PLAN.md` phase 5. Source: `.workflows/plan/sean-gotrade-tracker/phase-5.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 5: Plan — link a roster method, buy/sell reminders

**Plan set:** `SEAN_GOTRADE_TRACKER_PLAN.md`
**Analysis:** `20261007-222658-S3AN_code_analyzer.md`
**Satisfies:** R4 — connect Sean to one roster method (RAW today); Sean reminds the owner to buy / sell by it
**Depends on:** Phase 1 (migration 015, `lib/sean/ledger.ts`), Phase 2 (`/sean` shell, `SeanNav planOpen`, `gate.ts` with `isSeanCaller`, `data.ts` with `ledgerOrders()`, the Sean buttons in `Nav.tsx` and `AppHeader.tsx`, placeholder `app/sean/plan/page.tsx`)
**Difficulty:** HARD
**Package:** `web/app/sean/plan`, `web/lib/sean`

---

## Goal

After this phase the owner can open `/sean/plan`, pick one active book method from Seer's roster (RAW-FR today), say from which day his orders count toward it and, optionally, how much money the plan is, and see plain reminders — "Buy about $28 of MU", "Sell all 0.99 shares of DOW (about $28)" — computed from the method's newest picks against the shares he bought for the plan. Reminders clear on their own when an uploaded order matches them (on or after the method's decision day), or when he marks them done; the open count shows as a badge on the Plan tab (SeanNav) and a coral dot on Seer's Sean buttons (the desktop rail's and the phone header's). Holdings bought before the plan's start date (SPY, NVDA, PLTR, FUTU, GE, older LRCX/LLY lots, WDC) never get a sell reminder.

## Facts this plan is built on (read from the code and the live DB, 2026-10-07)

- `book_targets` holds one decision per (strategy, session_date); rows are written only on decision sessions (`paper/store.py:1019-1070`), and `_rewrite_executed_targets` (`:951`) later rewrites weights/prices of the same symbols after the session trades. So "the method's current picks" = rows at `max(session_date)` for the strategy. Live: RAW-FR has one decision, `2026-10-07`, 20 rows of weight 0.05, and `paper_state` says `last_session=2026-10-06, pending_session=2026-10-07, pending_decision=true` — the decision is for a session that has not been simulated yet. The page says so ("Its paper book buys them at that day's open").
- `unavailable_symbols` (014) is applied by the engine before the decision is written (`paper/store.load_market_window`, `commands/paper.py:496-506`), and `repick` rewrites a waiting decision. Targets therefore never contain a stock the owner listed as not on Gotrade; this phase does not re-filter.
- `MONTHLY_HOLD_FRAC = replace(MONTHLY_HOLD, fractional=True)` and `MONTHLY_HOLD` has `resize=True` (`engine/src/seer_engine/sim/rules.py:166-170`): on a decision session the engine trades a held target back to its weight when the gap is at least `RESIZE_BAND` (1%) of equity (`web/lib/cadence.ts:23`, `sim/book.py:540,596,631`). Rule sets with `resize=True`: `monthly-hold`, `monthly-hold-tbill`, `monthly-hold-frac`, `weekly-hold`, `monthly-rank-weekly-resize{,-tbill,-frac}`. Without resize: `daily-switch*`, `swing-*`, `design-v0`.
- The engine sizes resizes at the **target's last close** (`book_targets.last_price`), not at today's mark. Sean does the same, so an add/trim reminder does not flicker with every price move between decisions.
- Linkable roster rows today: `RMW-FR` (`monthly-rank-weekly-resize-frac`), `RAW-FR`, `MOM-FR`, `MVW-FR` (`monthly-hold-frac`) — all `status='active' AND engine='book' AND NOT is_benchmark`.
- Owner reality: 20 RAW buys at $27.90 each on 2026-10-07 WIB evening (= the US session of 2026-10-07). Paper equity is $560.51; 20 × $27.90 = $558.
- Gotrade fees: $0.10 minimum trading fee + regulatory + 11% PPN per order, so adds/trims under $10 are suppressed (`MIN_TRADE_USD`).
- The worktree has no `web/node_modules`; run `npm ci` in `web/` before verifying.

## Bindings (reconciled against Phase 1's and Phase 2's plans)

| From | Real export | Used in |
|---|---|---|
| Phase 1 `web/lib/sean/ledger.ts` | `type LedgerOrder = { id, side, symbol, executedAt, price, shares, totalUsd, tradingFeeUsd, regulatoryFeeUsd, ppnUsd }`; `buildLedger(orders: LedgerOrder[], through?): { holdings: Holding[]; realizedUsd; feesUsd }` where `holdings` are open positions only, `{ symbol, shares (9 dp), costUsd, avgPrice, lastOrderPrice }`; `orderSession(executedAt): string` (the New York trade date) | `reminders.ts` `sharesBySymbol`, `planOrders`, `doneBy`; `plan/page.tsx` "today" |
| Phase 2 `web/lib/sean/data.ts` | `type LedgerRow = LedgerOrder & { amountUsd }`; `ledgerOrders(): Promise<LedgerRow[]>` (oldest first, `executedAt` ISO with `+07:00`) | `planData.ts` `planState` |
| Phase 2 `web/lib/sean/gate.ts` | `requireSean(next = '/sean')`; `isSeanCaller(): Promise<boolean>` (the same two predicates, as a yes/no for actions) | `plan/page.tsx`; `plan/actions.ts` |
| Phase 2 `web/components/sean/SeanNav.tsx` | `SeanNav({ planOpen = 0 })`, badge on the `/sean/plan` tab | `app/sean/layout.tsx` |
| Phase 2 `web/components/Nav.tsx` | `Nav({ showSera = false, showSean = false })`; the Sean `<Link href="/sean" className={`icon-btn ${s.sean}`}>` (Lucide `Wallet`, tip/aria "Sean, your real trades") directly above the Sera link inside `.foot`; `.sean { position: relative; }` in `Nav.module.css` | `Nav.tsx` edit |
| Phase 2 `web/components/AppHeader.tsx` | `async AppHeader(props)`; `const owner = isSeraUser((await currentUser())?.email)`; owner-only `<Link href="/sean" className={`icon-btn mobile-only ${s.sean}`}>` (`Wallet`, tip/aria `SEAN_TIP`) before the Sign out form; `.sean { position: relative; }` in `AppHeader.module.css` | `AppHeader.tsx` edit |
| Phase 2 `web/app/(app)/layout.tsx` | `const owner = isSeraUser(user.email);` and `<Nav showSera={owner} showSean={owner} />` | `(app)/layout.tsx` edit |
| Phase 2 `web/app/sean/layout.tsx` | `await requireSean();` then `<SeanNav planOpen={0} />` inside the Sera-like shell | `app/sean/layout.tsx` edit |

**Which date an order counts on (plan Decisions):** the New York trade date (`orderSession`) —
for plan membership (`since`), and for the "done" check against a decision session (also a New
York date: `book_targets.session_date`). The owner's real RAW buys at 21:55 WIB on Oct 7 are 10:55
in New York, the Oct 7 session, so nothing changes for him; a fill after midnight WIB now counts
on the session it actually traded in.

## Interface Contract

**Deletes:** the Phase 2 placeholder body of `web/app/sean/plan/page.tsx` (file replaced whole).
**Renames:** none.
**Creates:**
- `web/lib/sean/reminders.ts`: `MIN_TRADE_USD`, `CLOSED_SHARES`, `RESIZING_RULES`, `resizes()`, `planOrders()`, `sharesBySymbol()`, `outsideShares()`, `lastPrices()`, `buildReminders()`, `sideOf()`; types `Side`, `ReminderAction`, `Target`, `PlanOrderLite`, `ReminderMark`, `Done`, `Reminder`, `PlanHolding`, `ReminderInput`, `ReminderPlan`.
- `web/lib/sean/reminders.test.ts`.
- `web/lib/sean/planData.ts` (new, server only; a file of this phase's own so it never shares a file with Phase 3, which runs in parallel): `LinkableMethod`, `linkableMethods()`, `SeanLink`, `link()`, `LatestTargets`, `latestTargets(strategyId)`, `reminderMarks(strategyId, sessionDate)`, `latestCloses(symbols)`, `PlanState`, `planState()`, `openReminderCount()` (React `cache`d: one count per request, shared by the layout and the header).
- `web/app/sean/plan/{page.tsx, view.ts, view.test.ts, actions.ts, LinkPicker.tsx, PlanSettings.tsx, plan.module.css}`. Server actions: `linkMethod(prev, formData)`, `unlinkMethod()`, `markDone(formData)`, `undoDone(formData)`.
**Signature changes:**
- `Nav({ showSera, showSean })` -> `Nav({ showSera, showSean, seanOpen = 0 })` (`web/components/Nav.tsx`). `AppHeader`'s props do not change: it reads the count itself (owner only), like it reads the owner check.
**DB writes (new, owner-only server actions):** `sean_link` (upsert / update / delete singleton id=1), `sean_reminder_marks` (insert / delete).
**Requires (from earlier phases):** migration `015_sean.sql` tables `sean_orders`, `sean_link`, `sean_reminder_marks`, `sean_marks` (Phase 1); `LedgerOrder`, `buildLedger`, `orderSession` (Phase 1); `ledgerOrders()`, `requireSean`, `isSeanCaller`, `SeanNav planOpen`, the Sean buttons in `Nav.tsx`/`AppHeader.tsx`, the owner check in `(app)/layout.tsx`, placeholder plan page (Phase 2). See **Bindings**.
**Leaves alone (owned by others):** `web/lib/sean/data.ts` (Phase 2; imported, never edited); `web/app/sean/page.tsx`, `overview.*`, `OverviewBody*`, `web/lib/sean/overviewData.ts` (Phase 3 — this phase shares no file with Phase 3); `web/app/sean/trades/*`, `web/app/api/sean/*`, `SeanNav.tsx` internals, `gate.ts` (Phase 2); `web/lib/sean/{types,ledger,money,prompt,vision,order,readOrder,unzip,extractJson}.ts` internals and `015_sean.sql` (Phase 1); `web/lib/cadence.ts` (Phase 7 adds the real-fee split-cadence id there); everything under `engine/` (Phases 4, 6, 7).

## Files

| File | Action | What changes |
|---|---|---|
| `web/lib/sean/reminders.ts` | create | the pure reminder engine |
| `web/lib/sean/reminders.test.ts` | create | fresh link, real Oct 7 follow-through, month turnover, resize, partial follow-through, marks, pre-plan holdings |
| `web/lib/sean/planData.ts` | create | link / targets / marks / closes reads, `planState()`, `openReminderCount()` |
| `web/app/sean/plan/page.tsx` | replace | the Plan page |
| `web/app/sean/plan/view.ts` | create | plain sentences + form parsing |
| `web/app/sean/plan/view.test.ts` | create | tests for view.ts |
| `web/app/sean/plan/actions.ts` | create | `linkMethod`, `unlinkMethod`, `markDone`, `undoDone` |
| `web/app/sean/plan/LinkPicker.tsx` | create | client: choose a method, start date, plan size |
| `web/app/sean/plan/PlanSettings.tsx` | create | client: edit start date and plan size |
| `web/app/sean/plan/plan.module.css` | create | page styles |
| `web/app/sean/layout.tsx` | modify (the `SeanNav` render line + one import + one call) | feed `planOpen` |
| `web/components/Nav.tsx` | modify (props + the Sean `<Link>`) | `seanOpen` count -> coral dot, count in tip/aria |
| `web/components/Nav.module.css` | modify (append 1 rule at end) | `.seanDot` |
| `web/components/AppHeader.tsx` | modify (one import, one line, the Sean `<Link>`) | the same dot and words on the phone's Sean button |
| `web/components/AppHeader.module.css` | modify (append 1 rule at end) | `.seanDot` |
| `web/app/(app)/layout.tsx` | modify (one import, one line, one prop) | pass `seanOpen` |

## Implementation Steps

### Step 1: The reminder engine
**File:** `web/lib/sean/reminders.ts` (new)
**Change:** pure module. Plan holdings come from the one ledger (contract B) run over orders on/after `since`; reminders compare them with the latest picks.
**Code:**
```ts
/**
 * Sean's buy/sell reminders (plan phase 5, requirement R4).
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
 * Pure: no database, relative imports only (vitest has no `@/` alias).
 */
import { RESIZE_BAND } from '../cadence';
import { buildLedger, orderSession, type LedgerOrder } from './ledger';

/** An add or trim smaller than this is not worth Gotrade's fees ($0.10 minimum + regulatory + PPN). */
export const MIN_TRADE_USD = 10;

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
  /** sean_link.budget_usd: the owner's plan size; null = what the plan holds now. */
  budgetUsd: number | null;
  /** The plan's orders, oldest first. */
  orders: readonly PlanOrderLite[];
  /** The owner's done marks (any decision; only this decision's count). */
  marks: readonly ReminderMark[];
};

export type ReminderPlan = {
  /** Σ plan shares × price. */
  planValue: number;
  /** budgetUsd when set, else planValue when above zero, else null (buys carry no amount). */
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
  const planSize =
    input.budgetUsd !== null && input.budgetUsd > 0 ? input.budgetUsd : planValue > 0 ? planValue : null;

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
    planSize,
    holdings,
    reminders,
    open: reminders.filter(r => r.done === null),
    done: reminders.filter(r => r.done !== null),
  };
}
```
**Impact:** new module; nothing else changes. Depends on Phase 1's `buildLedger`, `orderSession` and `LedgerOrder` (see Bindings).

### Step 2: Reminder tests
**File:** `web/lib/sean/reminders.test.ts` (new)
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import {
  buildReminders, lastPrices, outsideShares, planOrders, resizes, sideOf,
  type PlanOrderLite, type ReminderInput, type Target,
} from './reminders';

const OCT = '2026-10-07';
const NOV = '2026-11-02';

// RAW-FR's real decision for 2026-10-07 (book_targets), rank order.
const PICKS: [string, number][] = [
  ['MRNA', 187.46], ['CNC', 64.61], ['MRVL', 287.01], ['MU', 1045.56], ['FTNT', 191.27],
  ['IT', 184.92], ['INTC', 112.5], ['AMAT', 530.27], ['TER', 430.32], ['DELL', 574],
  ['DOW', 28.16], ['TGT', 154.33], ['UNH', 376.32], ['BAX', 24.36], ['ASML', 1834.1],
  ['UPS', 93.11], ['JBHT', 225.93], ['LLY', 1157.49], ['BMY', 59.59], ['LRCX', 333.89],
];
const RAW: Target[] = PICKS.map(([symbol, last]) => ({ symbol, weight: 0.05, last }));

/** The owner's real follow-through: $27.90 of each pick, Oct 7 evening WIB. */
const followed = (): Map<string, number> => new Map(RAW.map(t => [t.symbol, 27.9 / t.last]));
const octBuys: PlanOrderLite[] = RAW.map(t => ({
  symbol: t.symbol, side: 'buy', executedAt: '2026-10-07T21:55:00+07:00', price: t.last,
}));
/** What he held before RAW existed: never in the plan. */
const PRE_PLAN = new Map<string, number>([
  ['SPY', 2], ['NVDA', 3], ['PLTR', 5.38], ['FUTU', 1], ['GE', 0.5], ['LRCX', 0.4], ['LLY', 0.1], ['WDC', 1],
]);

function input(over: Partial<ReminderInput> = {}): ReminderInput {
  return {
    sessionDate: OCT, targets: RAW, resizes: true, held: new Map(), outside: new Map(), closes: new Map(),
    budgetUsd: null, orders: [], marks: [], ...over,
  };
}

/** November's decision: DOW dropped, XYZ picked. */
const NOV_PICKS: Target[] = [...RAW.filter(t => t.symbol !== 'DOW'), { symbol: 'XYZ', weight: 0.05, last: 50 }];

describe('buildReminders: fresh link', () => {
  it('with a plan size: one buy per pick, sized weight × plan size, in rank order', () => {
    const r = buildReminders(input({ budgetUsd: 560 }));
    expect(r.planSize).toBe(560);
    expect(r.planValue).toBe(0);
    expect(r.open).toHaveLength(20);
    expect(r.open.every(x => x.action === 'buy' && x.side === 'buy')).toBe(true);
    expect(r.open[0].symbol).toBe('MRNA');
    expect(r.open[19].symbol).toBe('LRCX');
    for (const x of r.open) expect(x.usd).toBeCloseTo(28, 6);
  });

  it('without a plan size: buys carry no amount', () => {
    const r = buildReminders(input());
    expect(r.planSize).toBeNull();
    expect(r.open).toHaveLength(20);
    expect(r.open.every(x => x.usd === null)).toBe(true);
  });
});

describe('buildReminders: the real Oct 7 follow-through', () => {
  it('leaves nothing to do, and holdings from before the plan are never sold', () => {
    const r = buildReminders(input({ held: followed(), outside: PRE_PLAN, orders: octBuys }));
    expect(r.reminders).toHaveLength(0);
    expect(r.holdings).toHaveLength(20);
    expect(r.holdings.every(h => h.picked)).toBe(true);
    expect(r.planValue).toBeCloseTo(558, 6);
    expect(r.planSize).toBeCloseTo(558, 6);
  });

  it('stays quiet with a budget a little off the plan value', () => {
    const r = buildReminders(input({ held: followed(), orders: octBuys, budgetUsd: 560.51 }));
    expect(r.reminders).toHaveLength(0);
  });
});

describe('buildReminders: month turnover', () => {
  it('sells a dropped pick in full and buys the new one, sells first', () => {
    const r = buildReminders(input({ sessionDate: NOV, targets: NOV_PICKS, held: followed(), orders: octBuys }));
    expect(r.open.map(x => `${x.action}:${x.symbol}`)).toEqual(['sell:DOW', 'buy:XYZ']);
    const [sell, buy] = r.open;
    expect(sell.shares).toBeCloseTo(27.9 / 28.16, 9);
    expect(sell.usd).toBeCloseTo(27.9, 6);
    expect(sell.alsoOutside).toBe(false);
    expect(buy.usd).toBeCloseTo(0.05 * 558, 6);
    expect(new Set(r.reminders.map(x => x.key)).size).toBe(r.reminders.length);
    expect(sell.key).toBe(`${NOV}:DOW:sell`);
  });

  it('a dropped pick also held from before the plan: says so, sells only the plan shares', () => {
    const outside = new Map([['DOW', 2]]);
    const r = buildReminders(input({ sessionDate: NOV, targets: NOV_PICKS, held: followed(), outside, orders: octBuys }));
    const sell = r.open.find(x => x.symbol === 'DOW')!;
    expect(sell.alsoOutside).toBe(true);
    expect(sell.shares).toBeCloseTo(27.9 / 28.16, 9);
  });

  it('a pre-plan holding the method drops gets no reminder', () => {
    const picks = RAW.filter(t => t.symbol !== 'LLY');
    const held = followed();
    held.delete('LLY');
    const r = buildReminders(input({ sessionDate: NOV, targets: picks, held, outside: PRE_PLAN }));
    expect(r.reminders.find(x => x.symbol === 'LLY')).toBeUndefined();
    expect(r.reminders.find(x => x.symbol === 'SPY')).toBeUndefined();
  });

  it('a pick held only from before the plan gets a buy that says so', () => {
    const held = followed();
    held.delete('LLY');
    // the plan never bought LLY, so no plan order clears the reminder either
    const r = buildReminders(input({ held, outside: PRE_PLAN, orders: octBuys.filter(o => o.symbol !== 'LLY') }));
    expect(r.open).toHaveLength(1);
    expect(r.open[0]).toMatchObject({ action: 'buy', symbol: 'LLY', alsoOutside: true });
  });
});

describe('buildReminders: resizing', () => {
  const drifted = (): Map<string, number> => {
    const held = followed();
    held.set('MU', 45 / 1045.56); // $45 at the decision price: $17 above its $28 share
    held.set('BAX', 33 / 24.36); // $33: $5 above, under the $10 floor
    return held;
  };

  it('trims a pick above its share, ignores gaps under $10', () => {
    const r = buildReminders(input({ held: drifted(), budgetUsd: 560 }));
    expect(r.open).toHaveLength(1);
    expect(r.open[0]).toMatchObject({ action: 'trim', side: 'sell', symbol: 'MU' });
    expect(r.open[0].usd).toBeCloseTo(17, 6);
  });

  it('adds to a pick below its share', () => {
    const held = followed();
    held.set('MU', 10 / 1045.56);
    const r = buildReminders(input({ held, budgetUsd: 560 }));
    expect(r.open).toHaveLength(1);
    expect(r.open[0]).toMatchObject({ action: 'add', side: 'buy', symbol: 'MU' });
    expect(r.open[0].usd).toBeCloseTo(18, 6);
  });

  it('never adds or trims for rules that do not resize', () => {
    const r = buildReminders(input({ held: drifted(), budgetUsd: 560, resizes: false }));
    expect(r.reminders).toHaveLength(0);
  });

  it('a big plan uses the engine 1% band, not the $10 floor', () => {
    const held = new Map(RAW.map(t => [t.symbol, 250 / t.last]));
    held.set('MU', 220 / 1045.56); // $30 below its $250 share: under 1% of $5,000
    held.set('DELL', 190 / 574); // $60 below: over the band
    const r = buildReminders(input({ held, budgetUsd: 5000 }));
    expect(r.open.map(x => `${x.action}:${x.symbol}`)).toEqual(['add:DELL']);
    expect(r.open[0].usd).toBeCloseTo(60, 6);
  });
});

describe('buildReminders: done', () => {
  it('partial follow-through: an order on or after the decision day clears that reminder only', () => {
    const held = followed();
    held.set('DOW', 0.5);
    const orders: PlanOrderLite[] = [
      ...octBuys,
      { symbol: 'DOW', side: 'sell', executedAt: '2026-11-02T21:40:00+07:00', price: 28 },
    ];
    const r = buildReminders(input({ sessionDate: NOV, targets: NOV_PICKS, held, orders }));
    expect(r.done.map(x => `${x.symbol}:${x.done}`)).toEqual(['DOW:order']);
    expect(r.open.map(x => x.symbol)).toEqual(['XYZ']);
  });

  it('an order before the decision day does not clear it', () => {
    const held = followed();
    held.set('DOW', 0.5);
    const orders: PlanOrderLite[] = [
      ...octBuys,
      { symbol: 'DOW', side: 'sell', executedAt: '2026-10-30T22:00:00+07:00', price: 28 },
    ];
    const r = buildReminders(input({ sessionDate: NOV, targets: NOV_PICKS, held, orders }));
    expect(r.open.map(x => x.symbol)).toEqual(['DOW', 'XYZ']);
  });

  it('a mark for this decision clears it; a mark for an older decision does not', () => {
    const r = buildReminders(input({
      sessionDate: NOV, targets: NOV_PICKS, held: followed(), orders: octBuys,
      marks: [
        { sessionDate: NOV, symbol: 'XYZ', side: 'buy' },
        { sessionDate: OCT, symbol: 'DOW', side: 'sell' },
      ],
    }));
    expect(r.done.map(x => `${x.symbol}:${x.done}`)).toEqual(['XYZ:mark']);
    expect(r.open.map(x => x.symbol)).toEqual(['DOW']);
  });
});

describe('buildReminders: edges', () => {
  it('no picks: no reminders, holdings still listed', () => {
    const r = buildReminders(input({ targets: [], held: followed(), orders: octBuys }));
    expect(r.reminders).toHaveLength(0);
    expect(r.holdings).toHaveLength(20);
    expect(r.holdings.every(h => !h.picked)).toBe(true);
  });

  it('values a non-pick at the latest close, else its last order price', () => {
    const held = new Map([['AAA', 2], ['BBB', 3]]);
    const orders: PlanOrderLite[] = [
      { symbol: 'AAA', side: 'buy', executedAt: '2026-10-07T21:00:00+07:00', price: 10 },
      { symbol: 'BBB', side: 'buy', executedAt: '2026-10-07T21:00:00+07:00', price: 20 },
    ];
    const r = buildReminders(input({ held, orders, closes: new Map([['AAA', 11]]) }));
    expect(r.holdings.find(h => h.symbol === 'AAA')!.value).toBeCloseTo(22, 9);
    expect(r.holdings.find(h => h.symbol === 'BBB')!.value).toBeCloseTo(60, 9);
    expect(r.holdings[0].symbol).toBe('BBB');
  });

  it('ignores dust below 1e-9 shares', () => {
    const r = buildReminders(input({ held: new Map([['DUST', 1e-12]]) }));
    expect(r.holdings).toHaveLength(0);
  });
});

describe('helpers', () => {
  it('planOrders keeps orders whose New York trade date is on or after since', () => {
    const orders = [
      { executedAt: '2025-06-10T21:34:00+07:00', id: 1 },
      { executedAt: '2026-10-06T23:59:00+07:00', id: 2 }, // New York: Oct 6, 12:59
      { executedAt: '2026-10-07T00:10:00+07:00', id: 3 }, // New York: Oct 6, 13:10 -- the Oct 6 session
      { executedAt: '2026-10-07T21:55:00+07:00', id: 4 }, // New York: Oct 7, 10:55
      { executedAt: '2026-10-08T03:30:00+07:00', id: 5 }, // New York: Oct 7, 16:30 -- still the Oct 7 session
    ];
    expect(planOrders(orders, OCT).map(o => o.id)).toEqual([4, 5]);
  });

  it('an order after midnight WIB clears a reminder of the session it traded in', () => {
    const held = followed();
    held.set('DOW', 0.5);
    const orders: PlanOrderLite[] = [
      ...octBuys,
      // 03:30 WIB on Nov 3 is 15:30 on Nov 2 in New York: the Nov 2 decision's session
      { symbol: 'DOW', side: 'sell', executedAt: '2026-11-03T03:30:00+07:00', price: 28 },
      // 23:00 WIB on Nov 1 is 11:00 on Nov 1 in New York: before the decision, so it does not count
      { symbol: 'XYZ', side: 'buy', executedAt: '2026-11-01T23:00:00+07:00', price: 50 },
    ];
    const r = buildReminders(input({ sessionDate: NOV, targets: NOV_PICKS, held, orders }));
    expect(r.done.map(x => `${x.symbol}:${x.done}`)).toEqual(['DOW:order']);
    expect(r.open.map(x => x.symbol)).toEqual(['XYZ']);
  });

  it('outsideShares is all minus plan, dropping float noise', () => {
    const all = new Map([['LLY', 0.1 + 0.0241], ['SPY', 2], ['MU', 0.0267]]);
    const plan = new Map([['LLY', 0.0241], ['MU', 0.0267]]);
    const out = outsideShares(all, plan);
    expect([...out.keys()].sort()).toEqual(['LLY', 'SPY']);
    expect(out.get('LLY')).toBeCloseTo(0.1, 9);
  });

  it('lastPrices keeps the latest order price', () => {
    const p = lastPrices([
      { symbol: 'MU', side: 'buy', executedAt: '2026-10-07T21:00:00+07:00', price: 1000 },
      { symbol: 'MU', side: 'buy', executedAt: '2026-10-08T21:00:00+07:00', price: 1010 },
    ]);
    expect(p.get('MU')).toBe(1010);
  });

  it('resizes mirrors the engine presets', () => {
    expect(resizes('monthly-hold-frac')).toBe(true);
    expect(resizes('monthly-rank-weekly-resize-frac')).toBe(true);
    expect(resizes('monthly-hold-frac-gotrade')).toBe(true);
    expect(resizes('monthly-rank-weekly-resize-frac-gotrade')).toBe(true);
    expect(resizes('daily-switch')).toBe(false);
    expect(resizes('swing-t20')).toBe(false);
    expect(resizes(null)).toBe(false);
  });

  it('sideOf', () => {
    expect(sideOf('buy')).toBe('buy');
    expect(sideOf('add')).toBe('buy');
    expect(sideOf('trim')).toBe('sell');
    expect(sideOf('sell')).toBe('sell');
  });
});
```
**Impact:** none beyond the test run.

### Step 3: Data reads
**File:** `web/lib/sean/planData.ts` (new). A file of this phase's own: Phase 2 owns `data.ts` and Phase 3 (parallel to this phase) writes `overviewData.ts`, so no two phases edit one file. `sql` comes from `@/lib/db` exactly as `data.ts` imports it; orders come from Phase 2's `ledgerOrders()`.
**Code (whole file):**
```ts
/**
 * The Plan's reads (Sean phase 5): the followed roster method, its newest picks, the owner's done
 * marks, the latest closes, and the reminders built from them. Server only (opens Neon through
 * lib/db); never unit-tested (plan invariant 7) -- the logic lives in the pure reminders.ts.
 */
import { cache } from 'react';
import { sql } from '@/lib/db';
import { ledgerOrders } from '@/lib/sean/data';
import {
  buildReminders, outsideShares, planOrders, resizes, sharesBySymbol,
  type ReminderMark, type ReminderPlan, type Side, type Target,
} from '@/lib/sean/reminders';
import { shortLabel } from '@/lib/strategy';

/** A roster method Sean can follow: active, book engine (it holds a basket), not the benchmark. */
export type LinkableMethod = {
  id: string;
  /** 'RAW': the part of the name before the middle dot. */
  short: string;
  /** 'RAW · Unbraked momentum'. */
  name: string;
  sub: string;
  /** strategies.icon (a Lucide name; components/roster.ts strategyIcon). */
  icon: string;
  rulesId: string | null;
  /** Its newest decision's session (book_targets), YYYY-MM-DD; null before its first pick. */
  lastPick: string | null;
};

export async function linkableMethods(): Promise<LinkableMethod[]> {
  const rows = await sql`SELECT s.id, s.name, s.sub, s.icon, s.rules_id,
      (SELECT max(t.session_date)::text FROM book_targets t WHERE t.strategy_id = s.id) AS last_pick
    FROM strategies s
    WHERE s.status = 'active' AND s.engine = 'book' AND NOT s.is_benchmark
    ORDER BY s.sort, s.id`;
  return rows.map(r => ({
    id: r.id,
    short: shortLabel(r.name, r.id),
    name: r.name,
    sub: r.sub ?? '',
    icon: r.icon ?? '',
    rulesId: r.rules_id ?? null,
    lastPick: r.last_pick ? String(r.last_pick).slice(0, 10) : null,
  }));
}

/** The followed method (sean_link, singleton) joined to its roster row. */
export type SeanLink = {
  strategyId: string;
  /** Orders whose New York trade date is on or after this belong to the plan. */
  since: string;
  /** The owner's plan size; null = what the plan holds now. */
  budgetUsd: number | null;
  short: string;
  name: string;
  sub: string;
  icon: string;
  rulesId: string | null;
  /** The method left the roster: no picks to follow. */
  retired: boolean;
};

export async function link(): Promise<SeanLink | null> {
  const [r] = await sql`SELECT l.strategy_id, l.since::text AS since, l.budget_usd,
      s.name, s.sub, s.icon, s.rules_id, s.status
    FROM sean_link l JOIN strategies s ON s.id = l.strategy_id
    WHERE l.id = 1`;
  if (!r) return null;
  return {
    strategyId: r.strategy_id,
    since: String(r.since).slice(0, 10),
    budgetUsd: r.budget_usd === null || r.budget_usd === undefined ? null : Number(r.budget_usd),
    short: shortLabel(r.name, r.strategy_id),
    name: r.name,
    sub: r.sub ?? '',
    icon: r.icon ?? '',
    rulesId: r.rules_id ?? null,
    retired: r.status === 'retired',
  };
}

/** A method's newest decision. `pending`: its paper book has not traded that session yet. */
export type LatestTargets = { sessionDate: string; pending: boolean; targets: Target[] };

export async function latestTargets(strategyId: string): Promise<LatestTargets | null> {
  const rows = await sql`SELECT t.session_date::text AS session_date, t.symbol, t.weight, t.last_price,
      COALESCE(ps.pending_decision AND ps.pending_session = t.session_date, false) AS pending
    FROM book_targets t
    LEFT JOIN paper_state ps ON ps.strategy_id = t.strategy_id
    WHERE t.strategy_id = ${strategyId}
      AND t.session_date = (SELECT max(session_date) FROM book_targets WHERE strategy_id = ${strategyId})
    ORDER BY t.rank`;
  if (rows.length === 0) return null;
  return {
    sessionDate: String(rows[0].session_date).slice(0, 10),
    pending: rows[0].pending === true,
    targets: rows.map(r => ({ symbol: r.symbol, weight: Number(r.weight), last: Number(r.last_price) })),
  };
}

/** The owner's done marks for one decision of one method. */
export async function reminderMarks(strategyId: string, sessionDate: string): Promise<ReminderMark[]> {
  const rows = await sql`SELECT session_date::text AS session_date, symbol, action
    FROM sean_reminder_marks
    WHERE strategy_id = ${strategyId} AND session_date = ${sessionDate}::date`;
  return rows.map(r => ({
    sessionDate: String(r.session_date).slice(0, 10),
    symbol: r.symbol,
    side: (r.action === 'sell' ? 'sell' : 'buy') as Side,
  }));
}

/**
 * The newest daily close per stock in sean_marks (written nightly by the engine, phase 4).
 * Named apart from phase 3's marks() on purpose. Stocks without a close are absent.
 */
export async function latestCloses(symbols: string[]): Promise<Map<string, number>> {
  const out = new Map<string, number>();
  if (symbols.length === 0) return out;
  const rows = await sql`SELECT DISTINCT ON (symbol) symbol, close
    FROM sean_marks WHERE symbol = ANY(${symbols}::text[])
    ORDER BY symbol, date DESC`;
  for (const r of rows) out.set(r.symbol, Number(r.close));
  return out;
}

/** Everything /sean/plan shows once a method is followed. */
export type PlanState = {
  link: SeanLink;
  /** The method's newest decision; null before its first pick or once it is retired. */
  targets: LatestTargets | null;
  plan: ReminderPlan;
  /** Stocks held from outside the plan (before `since`), by ticker: never sold by Sean. */
  outside: string[];
};

/** The followed method, its picks and the reminders against the plan; null when nothing is followed. */
export async function planState(): Promise<PlanState | null> {
  const l = await link();
  if (!l) return null;
  const [decision, all] = await Promise.all([
    l.retired ? Promise.resolve(null) : latestTargets(l.strategyId),
    ledgerOrders(),
  ]);
  const inPlan = planOrders(all, l.since);
  const held = sharesBySymbol(inPlan);
  const outside = outsideShares(sharesBySymbol(all), held);
  const [marksDone, closes] = await Promise.all([
    decision ? reminderMarks(l.strategyId, decision.sessionDate) : Promise.resolve([] as ReminderMark[]),
    latestCloses([...held.keys()]),
  ]);
  const plan = buildReminders({
    sessionDate: decision?.sessionDate ?? l.since,
    targets: decision?.targets ?? [],
    resizes: resizes(l.rulesId),
    held,
    outside,
    closes,
    budgetUsd: l.budgetUsd,
    orders: inPlan.map(o => ({ symbol: o.symbol, side: o.side, executedAt: o.executedAt, price: o.price })),
    marks: marksDone,
  });
  return { link: l, targets: decision, plan, outside: [...outside.keys()].sort() };
}

/**
 * Open reminders, for the Plan tab badge and the coral dot on Seer's Sean buttons (rail and phone
 * header). 0 when nothing is followed and when anything fails: a badge must never take a page
 * down. React `cache`: (app)/layout.tsx and AppHeader both ask during one request, and planState
 * runs once.
 */
export const openReminderCount = cache(async (): Promise<number> => {
  try {
    const st = await planState();
    return st ? st.plan.open.length : 0;
  } catch {
    return 0;
  }
});
```
**Impact:** new file. Every function here is server-only (opens Neon through `sql`); none is unit-tested (invariant 7).

### Step 4: Plain words and form rules
**File:** `web/app/sean/plan/view.ts` (new)
**Code:**
```ts
// Pure helpers for /sean/plan: the plain sentences the page and its forms show, and the form
// input rules. No data access; relative imports only (vitest has no `@/` alias).
import { sharesLabel } from '../../../components/roster';
import { picksMonthlySizesWeekly } from '../../../lib/cadence';
import { shortDate, usd } from '../../../lib/format';
import type { Reminder } from '../../../lib/sean/reminders';

/** What a form shows after the owner saves. */
export type FormState = { tone: 'idle' | 'ok' | 'error'; message: string };

export const IDLE: FormState = { tone: 'idle', message: '' };
export const NOT_ALLOWED: FormState = { tone: 'error', message: 'Only the owner can change the plan.' };
export const WRITE_FAILED: FormState = {
  tone: 'error', message: 'The plan could not be saved just now. Nothing changed; try again in a moment.',
};
export const BAD_METHOD: FormState = {
  tone: 'error', message: 'Pick one of the methods on the list. Only methods still on the roster can be followed.',
};
export const BAD_DATE: FormState = { tone: 'error', message: 'Pick the day your plan started, like Oct 7, 2026.' };
export const BAD_BUDGET: FormState = {
  tone: 'error', message: 'Type the plan size in dollars, like 560, or leave it empty.',
};
export const NOT_LINKED: FormState = { tone: 'error', message: 'Sean is not following a method right now. Pick one first.' };
export const SAVED: FormState = { tone: 'ok', message: 'Saved. The reminders below use it now.' };

export const linkedState = (short: string): FormState => ({
  tone: 'ok', message: `Following ${short}. Its reminders are below.`,
});

/** The largest plan size the form takes, in dollars. */
export const MAX_BUDGET = 10_000_000;

/** A YYYY-MM-DD that is a real calendar day in 2000 or later, else null. */
export function parseSince(raw: unknown): string | null {
  if (typeof raw !== 'string') return null;
  const v = raw.trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return null;
  const d = new Date(`${v}T00:00:00Z`);
  if (Number.isNaN(d.getTime()) || d.toISOString().slice(0, 10) !== v) return null;
  return v >= '2000-01-01' ? v : null;
}

/** The plan size field: empty -> null (use what the plan holds); '$1,000.5' -> 1000.5; else bad. */
export function parseBudget(raw: unknown): { ok: true; value: number | null } | { ok: false } {
  if (raw === null || raw === undefined) return { ok: true, value: null };
  if (typeof raw !== 'string') return { ok: false };
  const v = raw.replace(/[\s$,]/g, '');
  if (v === '') return { ok: true, value: null };
  if (!/^\d+(\.\d+)?$/.test(v)) return { ok: false };
  const n = Number(v);
  if (!Number.isFinite(n) || n <= 0 || n > MAX_BUDGET) return { ok: false };
  return { ok: true, value: Math.round(n * 100) / 100 };
}

/** A ticker as stored: 1-12 of A-Z, 0-9, '.', '-'. */
export function parseSymbol(raw: unknown): string | null {
  if (typeof raw !== 'string') return null;
  const v = raw.trim().toUpperCase();
  return /^[A-Z0-9.-]{1,12}$/.test(v) ? v : null;
}

export function parseSide(raw: unknown): 'buy' | 'sell' | null {
  return raw === 'buy' || raw === 'sell' ? raw : null;
}

/** '$27.90' under $100, '$1,045' from $100 up: an amount to type into Gotrade, roughly. */
export function aboutUsd(v: number): string {
  return v >= 100 ? `$${Math.round(v).toLocaleString('en-US')}` : usd(v);
}

/** 'RAW · Unbraked momentum' -> 'Unbraked momentum'; a name without a middle dot is kept. */
export function methodTitle(name: string): string {
  const i = name.indexOf('·');
  const rest = i < 0 ? '' : name.slice(i + 1).trim();
  return rest === '' ? name : rest;
}

/** 'A', 'A and B', 'A, B and C'. */
export function joinWords(words: readonly string[]): string {
  if (words.length <= 1) return words[0] ?? '';
  return `${words.slice(0, -1).join(', ')} and ${words[words.length - 1]}`;
}

export type Cadence = 'monthly' | 'weekly' | 'daily' | null;

/** How often a rule set picks, from its id (engine sim/rules.py presets). */
export function cadenceOf(rulesId: string | null): Cadence {
  if (!rulesId) return null;
  if (rulesId.startsWith('monthly-')) return 'monthly';
  if (rulesId.startsWith('weekly-')) return 'weekly';
  if (rulesId.startsWith('daily-') || rulesId.startsWith('swing-')) return 'daily';
  return null;
}

/** When the method picks next, in words. */
export function nextPickWords(rulesId: string | null): string {
  if (picksMonthlySizesWeekly(rulesId)) return 'at the start of next month, and checks sizes every week';
  const c = cadenceOf(rulesId);
  if (c === 'monthly') return 'at the start of next month';
  if (c === 'weekly') return 'next week';
  if (c === 'daily') return 'on the next market day';
  return 'when it next decides';
}

/** The page lede once a method is followed and has picked. */
export function picksLine(p: {
  short: string; sessionDate: string; pending: boolean; count: number; rulesId: string | null;
}): string {
  const head = `${p.short} picked ${p.count === 1 ? '1 stock' : `${p.count} stocks`} for ${shortDate(p.sessionDate)}.`;
  return p.pending
    ? `${head} Its paper book buys them at that day's open; you can follow any time from then.`
    : `${head} It picks again ${nextPickWords(p.rulesId)}.`;
}

/** The reminder itself: 'Buy about $28.00 of MU'. */
export function reminderTitle(r: Reminder): string {
  if (r.action === 'buy') return r.usd === null ? `Buy ${r.symbol}` : `Buy about ${aboutUsd(r.usd)} of ${r.symbol}`;
  if (r.action === 'add') return `Buy about ${aboutUsd(r.usd ?? 0)} more of ${r.symbol}`;
  if (r.action === 'trim') return `Sell about ${aboutUsd(r.usd ?? 0)} of ${r.symbol}`;
  const shares = r.shares === null ? '' : ` ${sharesLabel(r.shares)}`;
  const about = r.usd !== null && r.usd > 0 ? ` (about ${aboutUsd(r.usd)})` : '';
  return `Sell all${shares} of ${r.symbol}${about}`;
}

/** The line under it: why. */
export function reminderDetail(r: Reminder, short: string): string {
  if (r.action === 'buy') {
    const base = `One of ${short}'s picks, and not in your plan yet.`;
    const outside = r.alsoOutside ? ` The ${r.symbol} you bought before this plan is not counted.` : '';
    const size = r.usd === null ? ' Set a plan size below to see how much.' : '';
    return base + outside + size;
  }
  if (r.action === 'add') return `In your plan, but about ${aboutUsd(r.usd ?? 0)} below its share.`;
  if (r.action === 'trim') return `In your plan, but about ${aboutUsd(r.usd ?? 0)} above its share.`;
  const keep = r.alsoOutside ? ` Sell only these; keep the ${r.symbol} you had before this plan.` : '';
  return `${short} no longer picks it.${keep}`;
}

/** Why a done reminder is done. */
export function doneLine(r: Reminder, sessionDate: string): string {
  if (r.done === 'mark') return 'You marked this done.';
  return `You ${r.side === 'buy' ? 'bought' : 'sold'} ${r.symbol} on or after ${shortDate(sessionDate)}.`;
}

/** 'Nothing to do' / '1 thing to do' / '3 things to do'. */
export function todoLabel(n: number): string {
  if (n === 0) return 'Nothing to do';
  return n === 1 ? '1 thing to do' : `${n} things to do`;
}

/** The caption of "Your plan": where the plan size comes from. */
export function planSizeLine(planSize: number | null, budgetUsd: number | null): string {
  if (budgetUsd !== null) return `Plan size ${usd(budgetUsd)}, the amount you set. Each pick gets its share of it.`;
  if (planSize !== null) {
    return `Plan size ${usd(planSize)}, what the plan holds now. Set an amount to size buys differently.`;
  }
  return 'Set how much you want to put into this plan, and Sean will say how much of each stock to buy.';
}

/** The note about holdings from before the plan; null when there are none. */
export function outsideLine(symbols: readonly string[], since: string): string | null {
  if (symbols.length === 0) return null;
  return `You also hold ${joinWords(symbols)} from before ${shortDate(since)}. They are not part of this plan, so Sean never asks you to sell them.`;
}
```
**Impact:** new module.

### Step 5: view tests
**File:** `web/app/sean/plan/view.test.ts` (new)
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import type { Reminder } from '../../../lib/sean/reminders';
import {
  aboutUsd, cadenceOf, doneLine, joinWords, methodTitle, nextPickWords, outsideLine, parseBudget, parseSide,
  parseSince, parseSymbol, picksLine, planSizeLine, reminderDetail, reminderTitle, todoLabel,
} from './view';

const r = (over: Partial<Reminder>): Reminder => ({
  key: '2026-10-07:MU:buy', action: 'buy', side: 'buy', symbol: 'MU', usd: 28, shares: null, weight: 0.05,
  alsoOutside: false, done: null, ...over,
});

describe('form rules', () => {
  it('parseSince takes real days only', () => {
    expect(parseSince('2026-10-07')).toBe('2026-10-07');
    expect(parseSince(' 2026-10-07 ')).toBe('2026-10-07');
    expect(parseSince('2026-02-30')).toBeNull();
    expect(parseSince('07/10/2026')).toBeNull();
    expect(parseSince('1999-12-31')).toBeNull();
    expect(parseSince(null)).toBeNull();
  });

  it('parseBudget: empty is none, money strings parse, junk fails', () => {
    expect(parseBudget('')).toEqual({ ok: true, value: null });
    expect(parseBudget(null)).toEqual({ ok: true, value: null });
    expect(parseBudget('560')).toEqual({ ok: true, value: 560 });
    expect(parseBudget('$1,000.50')).toEqual({ ok: true, value: 1000.5 });
    expect(parseBudget(' 27.904 ')).toEqual({ ok: true, value: 27.9 });
    expect(parseBudget('0')).toEqual({ ok: false });
    expect(parseBudget('-5')).toEqual({ ok: false });
    expect(parseBudget('abc')).toEqual({ ok: false });
    expect(parseBudget('20000000')).toEqual({ ok: false });
  });

  it('parseSymbol and parseSide', () => {
    expect(parseSymbol('brk.b')).toBe('BRK.B');
    expect(parseSymbol('DROP TABLE')).toBeNull();
    expect(parseSide('buy')).toBe('buy');
    expect(parseSide('add')).toBeNull();
  });
});

describe('words', () => {
  it('aboutUsd keeps cents under $100 and rounds above', () => {
    expect(aboutUsd(27.9)).toBe('$27.90');
    expect(aboutUsd(1045.56)).toBe('$1,046');
  });

  it('methodTitle and joinWords', () => {
    expect(methodTitle('RAW · Unbraked momentum')).toBe('Unbraked momentum');
    expect(methodTitle('SPY')).toBe('SPY');
    expect(joinWords([])).toBe('');
    expect(joinWords(['SPY'])).toBe('SPY');
    expect(joinWords(['SPY', 'NVDA'])).toBe('SPY and NVDA');
    expect(joinWords(['SPY', 'NVDA', 'GE'])).toBe('SPY, NVDA and GE');
  });

  it('cadence words', () => {
    expect(cadenceOf('monthly-hold-frac')).toBe('monthly');
    expect(cadenceOf('weekly-hold')).toBe('weekly');
    expect(cadenceOf('daily-switch')).toBe('daily');
    expect(cadenceOf(null)).toBeNull();
    expect(nextPickWords('monthly-hold-frac')).toBe('at the start of next month');
    expect(nextPickWords('monthly-rank-weekly-resize-frac')).toContain('every week');
  });

  it('picksLine says when the method acts', () => {
    const base = { short: 'RAW', sessionDate: '2026-10-07', count: 20, rulesId: 'monthly-hold-frac' };
    expect(picksLine({ ...base, pending: true })).toBe(
      "RAW picked 20 stocks for Wed, Oct 7. Its paper book buys them at that day's open; you can follow any time from then.",
    );
    expect(picksLine({ ...base, pending: false })).toBe(
      'RAW picked 20 stocks for Wed, Oct 7. It picks again at the start of next month.',
    );
  });

  it('reminderTitle for each action', () => {
    expect(reminderTitle(r({}))).toBe('Buy about $28.00 of MU');
    expect(reminderTitle(r({ usd: null }))).toBe('Buy MU');
    expect(reminderTitle(r({ action: 'add', usd: 12.5 }))).toBe('Buy about $12.50 more of MU');
    expect(reminderTitle(r({ action: 'trim', side: 'sell', usd: 17 }))).toBe('Sell about $17.00 of MU');
    expect(reminderTitle(r({ action: 'sell', side: 'sell', symbol: 'DOW', shares: 0.99077, usd: 27.9 })))
      .toBe('Sell all 0.9908 shares of DOW (about $27.90)');
  });

  it('reminderDetail names the plan, never ids', () => {
    expect(reminderDetail(r({}), 'RAW')).toBe("One of RAW's picks, and not in your plan yet.");
    expect(reminderDetail(r({ usd: null, alsoOutside: true, symbol: 'LLY' }), 'RAW')).toBe(
      "One of RAW's picks, and not in your plan yet. The LLY you bought before this plan is not counted. Set a plan size below to see how much.",
    );
    expect(reminderDetail(r({ action: 'sell', side: 'sell', symbol: 'DOW', alsoOutside: true }), 'RAW')).toBe(
      'RAW no longer picks it. Sell only these; keep the DOW you had before this plan.',
    );
    expect(reminderDetail(r({ action: 'trim', side: 'sell', usd: 17 }), 'RAW')).toBe(
      'In your plan, but about $17.00 above its share.',
    );
  });

  it('doneLine and todoLabel', () => {
    expect(doneLine(r({ done: 'mark' }), '2026-10-07')).toBe('You marked this done.');
    expect(doneLine(r({ done: 'order' }), '2026-10-07')).toBe('You bought MU on or after Wed, Oct 7.');
    expect(doneLine(r({ done: 'order', side: 'sell', action: 'sell' }), '2026-10-07')).toBe('You sold MU on or after Wed, Oct 7.');
    expect(todoLabel(0)).toBe('Nothing to do');
    expect(todoLabel(1)).toBe('1 thing to do');
    expect(todoLabel(4)).toBe('4 things to do');
  });

  it('planSizeLine and outsideLine', () => {
    expect(planSizeLine(560, 560)).toContain('the amount you set');
    expect(planSizeLine(558, null)).toContain('what the plan holds now');
    expect(planSizeLine(null, null)).toContain('Set how much');
    expect(outsideLine([], '2026-10-07')).toBeNull();
    expect(outsideLine(['NVDA', 'SPY'], '2026-10-07')).toBe(
      'You also hold NVDA and SPY from before Wed, Oct 7. They are not part of this plan, so Sean never asks you to sell them.',
    );
  });
});
```

### Step 6: Server actions
**File:** `web/app/sean/plan/actions.ts` (new)
**Change:** owner-only writes, the `web/app/sera/gotrade/actions.ts` pattern: Phase 2's `isSeanCaller()` (`lib/sean/gate.ts`), the yes/no form of `requireSean` (a server action must answer with a status, not a 404 page). `strategy_id` for marks is read from `sean_link` server-side, never trusted from the form.
**Code:**
```ts
'use server';

import { revalidatePath } from 'next/cache';
import { sql } from '@/lib/db';
import { isSeanCaller } from '@/lib/sean/gate';
import { shortLabel } from '@/lib/strategy';
import {
  BAD_BUDGET, BAD_DATE, BAD_METHOD, linkedState, NOT_ALLOWED, NOT_LINKED, parseBudget, parseSide, parseSince,
  parseSymbol, SAVED, WRITE_FAILED, type FormState,
} from './view';

/** The Plan page and the Plan tab badge read these rows: refresh the whole /sean section. */
function refresh(): void {
  revalidatePath('/sean', 'layout');
}

/**
 * The picker and the settings form both post here. `op` 'link' (strategyId, since, budget) follows
 * a method, replacing any other; 'edit' (since, budget) changes the followed one.
 */
export async function linkMethod(_prev: FormState, formData: FormData): Promise<FormState> {
  if (!(await isSeanCaller())) return NOT_ALLOWED;
  const since = parseSince(formData.get('since'));
  if (!since) return BAD_DATE;
  const budget = parseBudget(formData.get('budget'));
  if (!budget.ok) return BAD_BUDGET;
  const op = formData.get('op');

  try {
    if (op === 'link') {
      const id = formData.get('strategyId');
      if (typeof id !== 'string' || id === '') return BAD_METHOD;
      const [m] = await sql`SELECT id, name FROM strategies
        WHERE id = ${id} AND status = 'active' AND engine = 'book' AND NOT is_benchmark`;
      if (!m) return BAD_METHOD;
      await sql`INSERT INTO sean_link (id, strategy_id, since, budget_usd)
        VALUES (1, ${id}, ${since}::date, ${budget.value}::numeric)
        ON CONFLICT (id) DO UPDATE SET strategy_id = EXCLUDED.strategy_id, since = EXCLUDED.since,
          budget_usd = EXCLUDED.budget_usd, linked_at = now()`;
      refresh();
      return linkedState(shortLabel(m.name, m.id));
    }
    if (op === 'edit') {
      const rows = await sql`UPDATE sean_link SET since = ${since}::date, budget_usd = ${budget.value}::numeric
        WHERE id = 1 RETURNING id`;
      if (rows.length === 0) return NOT_LINKED;
      refresh();
      return SAVED;
    }
  } catch (e) {
    console.error('sean_link write failed', e);
    return WRITE_FAILED;
  }
  return BAD_METHOD;
}

/** Stop following. Done marks stay (keyed by method and decision), harmless if it is followed again. */
export async function unlinkMethod(): Promise<void> {
  if (!(await isSeanCaller())) return;
  try {
    await sql`DELETE FROM sean_link WHERE id = 1`;
  } catch (e) {
    console.error('sean_link delete failed', e);
    return;
  }
  refresh();
}

/** Mark one reminder of the followed method's decision as done by hand. */
export async function markDone(formData: FormData): Promise<void> {
  if (!(await isSeanCaller())) return;
  const sessionDate = parseSince(formData.get('sessionDate'));
  const symbol = parseSymbol(formData.get('symbol'));
  const side = parseSide(formData.get('side'));
  if (!sessionDate || !symbol || !side) return;
  try {
    await sql`INSERT INTO sean_reminder_marks (strategy_id, session_date, symbol, action)
      SELECT strategy_id, ${sessionDate}::date, ${symbol}::text, ${side}::text FROM sean_link WHERE id = 1
      ON CONFLICT DO NOTHING`;
  } catch (e) {
    console.error('sean_reminder_marks insert failed', e);
    return;
  }
  refresh();
}

/** Take a hand-made done mark back. */
export async function undoDone(formData: FormData): Promise<void> {
  if (!(await isSeanCaller())) return;
  const sessionDate = parseSince(formData.get('sessionDate'));
  const symbol = parseSymbol(formData.get('symbol'));
  const side = parseSide(formData.get('side'));
  if (!sessionDate || !symbol || !side) return;
  try {
    await sql`DELETE FROM sean_reminder_marks
      WHERE strategy_id = (SELECT strategy_id FROM sean_link WHERE id = 1)
        AND session_date = ${sessionDate}::date AND symbol = ${symbol} AND action = ${side}`;
  } catch (e) {
    console.error('sean_reminder_marks delete failed', e);
    return;
  }
  refresh();
}
```
**Impact:** the only web writes to `sean_link` / `sean_reminder_marks`.

### Step 7: The method picker
**File:** `web/app/sean/plan/LinkPicker.tsx` (new)
**Code:**
```tsx
'use client';

import { Link2, LoaderCircle } from 'lucide-react';
import { useActionState, useState } from 'react';
import { strategyIcon } from '@/components/roster';
import { shortDate } from '@/lib/format';
import type { LinkableMethod } from '@/lib/sean/planData';
import { linkMethod } from './actions';
import { IDLE, methodTitle } from './view';
import s from './plan.module.css';

/**
 * Pick one roster method to follow. The start date defaults to the method's newest pick, so orders
 * placed to follow that pick count and everything bought before stays out of the plan.
 */
export function LinkPicker({ methods, today }: { methods: LinkableMethod[]; today: string }) {
  const [state, action, pending] = useActionState(linkMethod, IDLE);
  const [chosen, setChosen] = useState<string>(methods[0]?.id ?? '');
  const [since, setSince] = useState<string>(methods[0]?.lastPick ?? today);

  if (methods.length === 0) {
    return <p className={s.empty}>No method on Seer&apos;s roster can be followed right now.</p>;
  }

  const choose = (m: LinkableMethod) => {
    setChosen(m.id);
    setSince(m.lastPick ?? today);
  };

  return (
    <form action={action} className={s.picker}>
      <input type="hidden" name="op" value="link" />
      <fieldset className={s.choices} disabled={pending}>
        <legend className={s.sr}>Method to follow</legend>
        {methods.map(m => {
          const Icon = strategyIcon(m.icon);
          return (
            <label key={m.id} className={s.choice}>
              <input type="radio" name="strategyId" value={m.id} checked={chosen === m.id}
                onChange={() => choose(m)} className={s.sr} />
              <span className={s.choiceIcon} aria-hidden="true"><Icon size={22} strokeWidth={1.5} /></span>
              <span className={s.choiceText}>
                <span className={s.choiceName}><b>{m.short}</b> {methodTitle(m.name)}</span>
                <span className={s.choiceSub}>{m.sub}</span>
                <span className={s.choiceWhen}>
                  {m.lastPick ? `Last picked for ${shortDate(m.lastPick)}` : 'Has not picked yet'}
                </span>
              </span>
            </label>
          );
        })}
      </fieldset>

      <div className={s.settings}>
        <label className={s.field}>
          <span className={s.fieldLabel}>Counting your orders from</span>
          <input type="date" name="since" value={since} onChange={e => setSince(e.target.value)} required
            className={s.input} disabled={pending} />
        </label>
        <label className={s.field}>
          <span className={s.fieldLabel}>Plan size in dollars, if you want one</span>
          <input name="budget" inputMode="decimal" placeholder="What it holds" className={s.input}
            autoComplete="off" disabled={pending} />
        </label>
        <button type="submit" className={`icon-btn ${s.go}`} disabled={pending || chosen === ''}
          aria-label="Follow this method" data-tip="Follow this method">
          {pending
            ? <LoaderCircle size={22} strokeWidth={1.75} style={{ animation: 'spin 0.9s linear infinite' }} />
            : <Link2 size={22} strokeWidth={1.75} />}
        </button>
      </div>

      <p className={state.tone === 'error' ? s.error : s.status} aria-live="polite" role="status">
        {state.message}
      </p>
    </form>
  );
}
```

### Step 8: Plan settings
**File:** `web/app/sean/plan/PlanSettings.tsx` (new)
**Code:**
```tsx
'use client';

import { Check, LoaderCircle } from 'lucide-react';
import { useActionState } from 'react';
import { linkMethod } from './actions';
import { IDLE } from './view';
import s from './plan.module.css';

/** Change the followed plan's start date and plan size. An empty size means "what it holds now". */
export function PlanSettings({ since, budget }: { since: string; budget: number | null }) {
  const [state, action, pending] = useActionState(linkMethod, IDLE);
  return (
    <form action={action} className={s.settingsForm}>
      <input type="hidden" name="op" value="edit" />
      <div className={s.settings}>
        <label className={s.field}>
          <span className={s.fieldLabel}>Counting your orders from</span>
          <input type="date" name="since" defaultValue={since} required className={s.input} disabled={pending} />
        </label>
        <label className={s.field}>
          <span className={s.fieldLabel}>Plan size in dollars</span>
          <input name="budget" inputMode="decimal" defaultValue={budget === null ? '' : budget.toFixed(2)}
            placeholder="What it holds" className={s.input} autoComplete="off" disabled={pending} />
        </label>
        <button type="submit" className={`icon-btn ${s.go}`} disabled={pending}
          aria-label="Save the plan settings" data-tip="Save the plan settings">
          {pending
            ? <LoaderCircle size={22} strokeWidth={1.75} style={{ animation: 'spin 0.9s linear infinite' }} />
            : <Check size={22} strokeWidth={1.75} />}
        </button>
      </div>
      <p className={state.tone === 'error' ? s.error : s.status} aria-live="polite" role="status">
        {state.message}
      </p>
    </form>
  );
}
```

### Step 9: The page
**File:** `web/app/sean/plan/page.tsx` (replace Phase 2's placeholder whole)
**Code:**
```tsx
import { Check, CircleMinus, CirclePlus, Link2Off, RotateCcw } from 'lucide-react';
import type { Metadata } from 'next';
import { sharesLabel, strategyIcon } from '@/components/roster';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { Stat } from '@/components/sera/Stat';
import { shortDate, usd } from '@/lib/format';
import { requireSean } from '@/lib/sean/gate';
import { orderSession } from '@/lib/sean/ledger';
import { linkableMethods, planState, type LinkableMethod, type PlanState } from '@/lib/sean/planData';
import type { Reminder } from '@/lib/sean/reminders';
import { markDone, undoDone, unlinkMethod } from './actions';
import { LinkPicker } from './LinkPicker';
import { PlanSettings } from './PlanSettings';
import {
  doneLine, methodTitle, outsideLine, picksLine, planSizeLine, reminderDetail, reminderTitle, todoLabel,
} from './view';
import s from './plan.module.css';

export const metadata: Metadata = { title: 'Plan' };

// Reads and writes Neon on every visit: never prerendered.
export const dynamic = 'force-dynamic';

type Loaded = { ok: true; state: PlanState | null; methods: LinkableMethod[] } | { ok: false };

async function load(): Promise<Loaded> {
  try {
    const [state, methods] = await Promise.all([planState(), linkableMethods()]);
    return { ok: true, state, methods };
  } catch (e) {
    console.error('sean plan read failed', e);
    return { ok: false };
  }
}

export default async function PlanPage() {
  await requireSean('/sean/plan');
  const loaded = await load();
  if (!loaded.ok) {
    return (
      <>
        <PageHeader eyebrow="Plan" title="Follow a method" />
        <Section eyebrow="Plan" title="Can't read the plan right now">
          <p className={s.empty}>Nothing has changed; try again in a moment.</p>
        </Section>
      </>
    );
  }
  // The start date a method with no pick yet defaults to: today's New York date, the calendar
  // plan membership is counted in (plan Decisions).
  if (!loaded.state) return <Unlinked methods={loaded.methods} today={orderSession(new Date().toISOString())} />;
  return <Linked state={loaded.state} />;
}

function Unlinked({ methods, today }: { methods: LinkableMethod[]; today: string }) {
  return (
    <>
      <PageHeader
        eyebrow="Plan"
        title="Follow a method"
        lede="Pick one method from Seer's roster. Sean compares its picks with what you bought for it and tells you what to buy and sell."
      />
      <div className={s.page}>
        <Section eyebrow="Roster" title="Pick a method"
          caption="Only methods that hold a basket of stocks can be followed. Orders from the start date on count toward the plan; anything you bought earlier stays out of it.">
          <LinkPicker methods={methods} today={today} />
        </Section>
      </div>
    </>
  );
}

function Linked({ state }: { state: PlanState }) {
  const { link, targets, plan, outside } = state;
  const Icon = strategyIcon(link.icon);
  const picks = targets?.targets.length ?? 0;
  const heldPicks = plan.holdings.filter(h => h.picked).length;
  const sessionDate = targets?.sessionDate ?? link.since;
  const lede = link.retired
    ? `${link.short} has left Seer's roster, so there are no picks to follow. Stop following it and pick another method.`
    : targets
      ? picksLine({ short: link.short, sessionDate: targets.sessionDate, pending: targets.pending, count: picks, rulesId: link.rulesId })
      : `${link.short} has not picked any stocks yet. Reminders show up after its first pick.`;
  const unlinkTip = `Stop following ${link.short}`;
  const outsideNote = outsideLine(outside, link.since);

  return (
    <>
      <PageHeader
        eyebrow="Plan"
        title={`Following ${link.short}`}
        lede={lede}
        aside={
          <form action={unlinkMethod}>
            <button type="submit" className="icon-btn" aria-label={unlinkTip} data-tip={unlinkTip}>
              <Link2Off size={21} strokeWidth={1.5} />
            </button>
          </form>
        }
      />
      <div className={s.page}>
        <Section className={s.summary}>
          <div className={s.method}>
            <span className={s.methodIcon} aria-hidden="true"><Icon size={24} strokeWidth={1.5} /></span>
            <span className={s.methodText}>
              <span className={s.methodName}>{methodTitle(link.name)}</span>
              <span className={s.methodSub}>{link.sub}</span>
            </span>
          </div>
          <div className={s.stats}>
            <Stat value={String(plan.open.length)} label="To do" size="md" tip="Reminders still waiting for you" />
            <Stat value={usd(plan.planValue)} label="Plan value" size="md"
              tip="What the stocks bought for this plan are worth, at the latest prices Sean has" />
            <Stat value={`${heldPicks} of ${picks}`} label="Picks held" size="md"
              tip={`How many of ${link.short}'s picks your plan holds`} />
          </div>
        </Section>

        <Section eyebrow={todoLabel(plan.open.length)} title="To do"
          caption={plan.open.length > 0
            ? `Sells first: they free the money for the buys. A reminder clears when you upload the order, or when you mark it done.`
            : `Your plan matches ${link.short}'s picks. New reminders show up after its next pick.`}>
          {plan.open.length > 0 && (
            <ul className={s.list}>
              {plan.open.map(r => (
                <ReminderRow key={r.key} r={r} short={link.short} sessionDate={sessionDate} />
              ))}
            </ul>
          )}
        </Section>

        {plan.done.length > 0 && (
          <Section bg="stone" eyebrow="Done" title="Already done"
            caption={`Reminders for ${shortDate(sessionDate)} that you have taken care of.`}>
            <ul className={s.list}>
              {plan.done.map(r => (
                <DoneRow key={r.key} r={r} sessionDate={sessionDate} />
              ))}
            </ul>
          </Section>
        )}

        <Section eyebrow={`Since ${shortDate(link.since)}`} title="Your plan" caption={planSizeLine(plan.planSize, link.budgetUsd)}>
          <PlanSettings since={link.since} budget={link.budgetUsd} />
          {plan.holdings.length === 0 ? (
            <p className={s.empty}>
              Nothing bought for this plan yet. Upload your order screenshots on the Trades tab and they show up here.
            </p>
          ) : (
            <table className={s.table}>
              <thead>
                <tr>
                  <th scope="col">Stock</th>
                  <th scope="col" className={s.right}>Shares</th>
                  <th scope="col" className={s.right}>Price</th>
                  <th scope="col" className={s.right}>Value</th>
                  <th scope="col">{link.short}</th>
                </tr>
              </thead>
              <tbody>
                {plan.holdings.map(h => (
                  <tr key={h.symbol}>
                    <th scope="row" className={`num ${s.symbol}`}>{h.symbol}</th>
                    <td className={`num ${s.right}`}>{sharesLabel(h.shares)}</td>
                    <td className={`num ${s.right}`}>{usd(h.price)}</td>
                    <td className={`num ${s.right}`}>{usd(h.value)}</td>
                    <td className={s.muted}>{h.picked ? 'Picked' : 'No longer picked'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {outsideNote && <p className={s.note}>{outsideNote}</p>}
        </Section>
      </div>
    </>
  );
}

function ReminderRow({ r, short, sessionDate }: { r: Reminder; short: string; sessionDate: string }) {
  const title = reminderTitle(r);
  const tip = `Mark done: ${title}`;
  const Mark = r.side === 'buy' ? CirclePlus : CircleMinus;
  return (
    <li className={s.row}>
      <span className={s.todoMark} aria-hidden="true"><Mark size={20} strokeWidth={1.75} /></span>
      <span className={s.rowText}>
        <span className={`num ${s.rowTitle}`}>{title}</span>
        <span className={s.rowDetail}>{reminderDetail(r, short)}</span>
      </span>
      <form action={markDone}>
        <input type="hidden" name="sessionDate" value={sessionDate} />
        <input type="hidden" name="symbol" value={r.symbol} />
        <input type="hidden" name="side" value={r.side} />
        <button type="submit" className={`icon-btn sm ${s.doneBtn}`} aria-label={tip} data-tip={tip}>
          <Check size={18} strokeWidth={1.75} />
        </button>
      </form>
    </li>
  );
}

function DoneRow({ r, sessionDate }: { r: Reminder; sessionDate: string }) {
  const title = reminderTitle(r);
  const tip = `Not done yet: ${title}`;
  return (
    <li className={s.row}>
      <span className={s.doneMark} aria-hidden="true"><Check size={20} strokeWidth={1.75} /></span>
      <span className={s.rowText}>
        <span className={`num ${s.rowTitle} ${s.struck}`}>{title}</span>
        <span className={s.rowDetail}>{doneLine(r, sessionDate)}</span>
      </span>
      {r.done === 'mark' && (
        <form action={undoDone}>
          <input type="hidden" name="sessionDate" value={sessionDate} />
          <input type="hidden" name="symbol" value={r.symbol} />
          <input type="hidden" name="side" value={r.side} />
          <button type="submit" className="icon-btn sm" aria-label={tip} data-tip={tip}>
            <RotateCcw size={18} strokeWidth={1.5} />
          </button>
        </form>
      )}
    </li>
  );
}
```
**Impact:** replaces the Phase 2 placeholder. Coral marks only the open reminders and their done buttons (invariant 4: coral = you need to act); green/red are not used (no profit/loss on this page).

### Step 10: Page styles
**File:** `web/app/sean/plan/plan.module.css` (new)
**Code:**
```css
/* /sean/plan: a summary sheet, the to-do list, what is done, and the plan's holdings. */
.page { display: flex; flex-direction: column; gap: 12px; }

/* Summary: the followed method on the left, three numbers on the right. */
.summary { padding-bottom: 28px; }
.method { display: flex; align-items: center; gap: 14px; min-width: 0; }
.methodIcon {
  display: inline-flex; align-items: center; justify-content: center; flex: none;
  width: 52px; height: 52px; border-radius: 999px; background: var(--stone);
}
.methodText { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.methodName { font-size: 20px; font-weight: 500; }
.methodSub { font-size: 15px; color: var(--ink-2); }
.stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }

/* Reminders. */
.list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.row {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 0; border-bottom: 1px solid var(--hair);
}
.row:last-child { border-bottom: 0; }
.todoMark, .doneMark {
  display: inline-flex; align-items: center; justify-content: center; flex: none;
  width: 40px; height: 40px; border-radius: 999px;
}
.todoMark { background: var(--coral); color: var(--on-coral); }
.doneMark { background: var(--chip); color: var(--ink-2); }
.rowText { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.rowTitle { font-size: 18px; font-weight: 500; }
.rowDetail { font-size: 14.5px; line-height: 1.4; color: var(--ink-2); }
.struck { text-decoration: line-through; text-decoration-color: var(--ink-3); color: var(--ink-2); }
.doneBtn { border: 0; background: var(--coral); color: var(--on-coral); }
.doneBtn:hover { background: var(--coral); filter: brightness(0.95); }

/* Forms: picker and settings share one rounded track of inputs and a coral button. */
.picker, .settingsForm { display: flex; flex-direction: column; gap: 12px; }
.choices {
  border: 0; margin: 0; padding: 0; min-width: 0;
  display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px;
}
.choice {
  display: flex; align-items: flex-start; gap: 14px; padding: 18px 20px;
  border-radius: 24px; background: var(--stone); cursor: pointer;
  box-shadow: inset 0 0 0 2px transparent; transition: box-shadow 0.12s;
}
.choice:has(input:checked) { box-shadow: inset 0 0 0 2px var(--coral); background: var(--sheet); }
.choice:has(input:focus-visible) { outline: 2px solid var(--coral); outline-offset: 2px; }
.choices:disabled .choice { cursor: progress; opacity: 0.7; }
.choiceIcon {
  display: inline-flex; align-items: center; justify-content: center; flex: none;
  width: 44px; height: 44px; border-radius: 999px; background: var(--chip);
}
.choiceText { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.choiceName { font-size: 17px; }
.choiceName b { font-weight: 600; margin-right: 4px; }
.choiceSub { font-size: 14.5px; line-height: 1.4; color: var(--ink-2); }
.choiceWhen { font-size: 13.5px; color: var(--ink-3); }

.settings {
  display: flex; align-items: flex-end; flex-wrap: wrap; gap: 10px;
  padding: 10px; border-radius: 28px; background: var(--stone);
}
.field { display: flex; flex-direction: column; gap: 4px; flex: 1 1 200px; min-width: 0; }
.fieldLabel { font-size: 13px; color: var(--ink-2); padding: 0 14px; }
.input {
  height: 52px; border: 0; border-radius: 999px; background: var(--sheet); color: var(--ink);
  font: inherit; font-size: 17px; padding: 0 18px; min-width: 0; outline: none;
  font-variant-numeric: tabular-nums;
}
.input::placeholder { color: var(--ink-3); }
.input:focus-visible { box-shadow: 0 0 0 2px var(--coral); }
.input:disabled { opacity: 0.6; }
.go { border: 0; background: var(--coral); color: var(--on-coral); }
.go:hover { background: var(--coral); filter: brightness(0.95); }
.go:disabled { cursor: progress; }

.status, .error { min-height: 22px; margin: 0; font-size: 15px; line-height: 1.45; padding: 0 12px; }
.status { color: var(--ink-2); }
.error { color: var(--neg); }

/* Holdings table. */
.table { width: 100%; border-collapse: collapse; font-size: 15.5px; }
.table th, .table td { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--hair); }
.table thead th { font-size: 13px; font-weight: 400; color: var(--ink-2); }
.table tbody tr:last-child th, .table tbody tr:last-child td { border-bottom: 0; }
.right { text-align: right !important; }
.symbol { font-weight: 500; letter-spacing: 0.02em; }
.muted { color: var(--ink-2); }

.note { margin: 0; font-size: 15px; line-height: 1.45; color: var(--ink-2); }
.empty { margin: 0; font-size: 16px; color: var(--ink-2); }

.sr {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden;
  clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
}

@media (max-width: 1023.98px) {
  .stats { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
  .table { font-size: 14.5px; }
  .table th:nth-child(3), .table td:nth-child(3) { display: none; }
  .settings { border-radius: 24px; }
  .go { margin-left: auto; }
}
```

### Step 11: Plan tab badge
**File:** `web/app/sean/layout.tsx` (Phase 2's file; the `SeanNav` render and the layout function body)
**Change:** add one import, compute the count after the gate, pass it. Only these three edits; everything else in Phase 2's layout stays.
**Code (added import):**
```tsx
import { openReminderCount } from '@/lib/sean/planData';
```
**Code (inside `SeanLayout`, directly after `await requireSean();`):**
```tsx
  // Open reminders: the Plan tab's badge. openReminderCount returns 0 on any failure.
  const planOpen = await openReminderCount();
```
**Code (the nav element, replacing Phase 2's `<SeanNav planOpen={0} />`):**
```tsx
      <SeanNav planOpen={planOpen} />
```
Also drop the sentence "`planOpen` is 0 until Phase 5 reads the open reminder count here." from the layout's doc comment.
**Impact:** every `/sean` page renders the Plan badge; the call is wrapped so it never throws.

### Step 12: The coral dot on Seer's Sean buttons
The same count, the same dot, the same words on both ways into Sean: the desktop rail button
(`Nav.tsx`) and the phone's header button (`AppHeader.tsx`, Phase 2 Step 3b). Phase 2 already gave
each link the class `s.sean` with `position: relative`, so only the dot is added here.

**File:** `web/components/Nav.tsx` (Phase 2's version — the doc comment, the `Nav` signature and the Sean `<Link>`)
**Change:** new prop `seanOpen = 0`; when above zero the Sean link carries a small coral dot and says the count in its tip and aria-label (identical text).
**Code (doc comment and signature, replacing Phase 2's):**
```tsx
/**
 * Floating pill tab bar on mobile, vertical rail on desktop. Icon-only.
 * `showSean` and `showSera` add the ways into Sean (the owner's real trades) and Sera (the method
 * lab) to the foot of the desktop rail, Sean above Sera; `seanOpen` (Sean's open plan reminders)
 * puts a coral dot on the Sean button.
 */
export function Nav({ showSera = false, showSean = false, seanOpen = 0 }: { showSera?: boolean; showSean?: boolean; seanOpen?: number }) {
  const path = usePathname();
  const open = Number.isFinite(seanOpen) && seanOpen > 0 ? Math.floor(seanOpen) : 0;
  const seanTip = open > 0 ? `Sean, your real trades · ${open} to do` : 'Sean, your real trades';
```
**Code (the Sean link, replacing Phase 2's inside `.foot`):**
```tsx
            {showSean && (
              <Link href="/sean" className={`icon-btn ${s.sean}`} data-tip={seanTip} aria-label={seanTip}>
                <Wallet size={21} strokeWidth={1.5} />
                {open > 0 && <span className={s.seanDot} aria-hidden="true" />}
              </Link>
            )}
```
**File:** `web/components/Nav.module.css` (append at end of file)
**Code:**
```css
/* Sean has plan reminders waiting: a coral dot on the rail button (phase 5). Coral = you need to act. */
.seanDot {
  position: absolute;
  top: 7px;
  right: 7px;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: var(--coral);
  box-shadow: 0 0 0 2px var(--bg);
  pointer-events: none;
}
```

**File:** `web/components/AppHeader.tsx` (Phase 2's version — one import, the owner line, the Sean `<Link>`)
**Change:** the owner's header reads the same cached count (`openReminderCount` is React-`cache`d, so this and `(app)/layout.tsx` share one `planState()` per request).
**Code (added import):**
```tsx
import { openReminderCount } from '@/lib/sean/planData';
```
**Code (directly after Phase 2's `const owner = isSeraUser((await currentUser())?.email);`):**
```tsx
  // Sean's open plan reminders: the same coral dot as the rail's. Owner only; 0 on any failure.
  const open = owner ? await openReminderCount() : 0;
  const seanTip = open > 0 ? `${SEAN_TIP} · ${open} to do` : SEAN_TIP;
```
**Code (the Sean link, replacing Phase 2's):**
```tsx
        {owner && (
          <Link href="/sean" className={`icon-btn mobile-only ${s.sean}`} data-tip={seanTip} aria-label={seanTip}>
            <Wallet size={21} strokeWidth={1.5} />
            {open > 0 && <span className={s.seanDot} aria-hidden="true" />}
          </Link>
        )}
```
**File:** `web/components/AppHeader.module.css` (append at end of file)
**Code:**
```css
/* Sean has plan reminders waiting: the phone's twin of the rail's coral dot. */
.seanDot {
  position: absolute;
  top: 7px;
  right: 7px;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: var(--coral);
  box-shadow: 0 0 0 2px var(--bg);
  pointer-events: none;
}
```
**Impact:** `Nav`'s new prop is optional with default 0, so any other caller compiles unchanged; `AppHeader`'s props do not change.

### Step 13: Feed the count from the Seer layout
**File:** `web/app/(app)/layout.tsx` (Phase 2's version, which computes `const owner = isSeraUser(user.email);`)
**Change:** one import, one line after `owner`, one prop. Only the owner pays for the query.
**Code (import):**
```tsx
import { openReminderCount } from '@/lib/sean/planData';
```
**Code (directly after Phase 2's `const owner = isSeraUser(user.email);`):**
```tsx
  // Sean's open plan reminders (coral dot on the rail). Owner only; 0 on any failure.
  const seanOpen = owner ? await openReminderCount() : 0;
```
**Code (the Nav element, replacing Phase 2's):**
```tsx
      <Nav showSera={owner} showSean={owner} seanOpen={seanOpen} />
```
**Impact:** owner's Seer pages run `planState()` once per request (link + targets + orders + marks + closes; ~5 small queries), shared with `AppHeader` through React `cache`. Non-owners: zero queries.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/sean-gotrade-tracker/web && npm ci && npx tsc --noEmit && npx next build`
**Tests:** `cd /home/miftah/.worktrees/seer/sean-gotrade-tracker/web && npx vitest run lib/sean/reminders.test.ts app/sean/plan/view.test.ts && npx vitest run`
**Manual check (dev server against the dev Neon with 015 applied and the owner's orders uploaded via Phase 2):**
1. `/sean/plan` with no link: four cards (RMW, RAW, MOM, MVW); choosing RAW fills "Counting your orders from" with 2026-10-07.
1b. At 390 px with open reminders, the header's Sean button on Today shows the coral dot and its tip says "… · N to do".
2. Follow RAW with no plan size: the To do list is empty once the 20 Oct 7 orders are uploaded ("Your plan matches RAW's picks"), Picks held reads "20 of 20", Plan value ≈ $558, and the note names SPY, NVDA, PLTR, FUTU, GE, WDC (and LLY/LRCX if their older lots are still open) as outside the plan. No reminder mentions any of them.
3. Before uploading the Oct 7 orders (or with a later start date), 20 coral "Buy …" rows appear; with plan size 560 each reads "Buy about $28.00 of …"; the Plan tab shows a badge and the Seer rail's Sean button a coral dot; marking one done moves it to "Already done" with an undo button.
4. Every button is icon-only with matching `aria-label` and `data-tip`; no ids, digests or rule ids on the page.
**Exit criteria:** `reminders.test.ts` and `view.test.ts` green (fresh link, real Oct 7 follow-through, month turnover, partial follow-through, resize band, pre-plan holdings untouched, marked done); full `vitest run`, `tsc --noEmit` and `next build` green; the manual checks above hold.

## Handoffs

- **Phase 1 (R2, R3):** reconciled — `sharesBySymbol` reads `buildLedger(orders).holdings`; plan membership and the done check use `orderSession`.
- **Phase 2 (R1, R3):** reconciled — see **Bindings**; this phase adds only the count plumbing to `SeanNav`, `Nav.tsx`, `AppHeader.tsx` and `(app)/layout.tsx`, and reads orders through `ledgerOrders()`.
- **Phase 3 (R2):** owns `marks()`/`equity()` in its own `overviewData.ts`; this phase's `latestCloses()` in `planData.ts` is a separate read of the same `sean_marks` table. No shared file.
- **Phase 7 (R5):** adds `monthly-rank-weekly-resize-frac-gotrade` to `web/lib/cadence.ts` `SPLIT_CADENCE_RULES`; `RESIZING_RULES` here already lists both real-fee preset ids.
- **Phase 4 (R2):** `sean_marks` must include every symbol the plan holds for "Plan value" to use real closes; without it the page falls back to the decision price (picks) and last order price (others), which is correct but stale.
- **Engine mirror (no phase):** `RESIZING_RULES` hand-mirrors `sim/rules.py` presets with `resize=True`, like `cadence.ts` `SPLIT_CADENCE_RULES`. A new resizing preset must be appended there; a test in the engine that cross-checks the list would be a separate follow-up card, not this set.
- **Out of scope noticed:** Phase 2's reuse of Sera's `PageHeader` signs out to `/signin?next=%2Fsera`; not this phase's to fix.

## Rollback

Revert this phase's commit. That deletes `web/lib/sean/{reminders*,planData}.ts` and `web/app/sean/plan/{view*,actions,LinkPicker,PlanSettings,plan.module.css}`, restores Phase 2's placeholder `plan/page.tsx`, and removes the `seanOpen`/`planOpen` plumbing and both dots (`Nav` and `AppHeader` fall back to their Phase 2 versions; `SeanNav planOpen` defaults to 0). Rows already written to `sean_link` / `sean_reminder_marks` are harmless (nothing else reads them); `DELETE FROM sean_link; DELETE FROM sean_reminder_marks;` clears them if wanted.
