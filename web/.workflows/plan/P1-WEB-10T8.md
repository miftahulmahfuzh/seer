> Adopted from `PAPER_SPLIT_CADENCE_PLAN.md` phase 3. Source: `.workflows/plan/paper-split-cadence/phase-3.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 3: Positions page: monthly pick / weekly size copy and trim-or-add cell

**Plan set:** `PAPER_SPLIT_CADENCE_PLAN.md`
**Analysis:** `20261007-011957-S9C4_code_analyzer.md`
**Satisfies:** R6 (holds R4 for the web) — the Positions page says, in plain words, that a split-cadence strategy picks its stocks monthly and checks how much to hold weekly, and each of its orders shows what to buy, add, trim, or leave alone
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `web`

---

## Goal

After this phase the Positions page recognises a strategy whose rules pick monthly and resize
weekly (`Strategy.rulesId` in a fixed set of three engine preset ids). For such a strategy only,
the three "rebalances on the first session of each month" sentences say instead that it picks its
stocks on the first session of each month and checks how much to hold on the first session of each
week, and every book order row gets one extra wide cell: "Buy about $X" (not held), "Add about $X",
"Trim about $X", or "No change" (gap under 1% of paper equity, the engine's `RESIZE_BAND`). Every
other strategy renders byte for byte as before.

## Interface Contract

**Deletes:** nothing
**Renames:** nothing
**Creates:**
- `web/lib/cadence.ts` (new): `SPLIT_CADENCE_RULES`, `picksMonthlySizesWeekly(rulesId)`,
  `RESIZE_BAND` (= 0.01, mirror of engine `sim/rules.py:39`), `type SizeChange`,
  `sizeChange(weight, equity, heldUsd)`, `heldUsd(holdings)`, `orderSizeChange(weight, equity, symbol, held)`,
  `sizeLabel(c)`, `sizeTip(c)`
- `web/lib/cadence.test.ts` (new): vitest tests for all of the above
- `web/app/(app)/positions/page.tsx`: new local component `SizeCell`
- `web/app/(app)/positions/positions.module.css`: new class `.cellWide`

**Signature changes:** local (non-exported) `OrderRow` in `positions/page.tsx` gains an optional
prop `size?: SizeChange | null` (omitted for every non-split-cadence strategy).
**Requires (from earlier phases):** nothing at build or test time. At run time the id
`'monthly-rank-weekly-resize-frac'` only appears in `strategies.rules_id` once Phase 1 adds the
preset and a strategy is promoted on it; the web set lists it regardless (a string, no import).
**Leaves alone (owned by others):** `engine/*` (Phases 1 and 2), including `RESIZE_BAND`,
`sim/rules.py` presets and `book_targets`; `web/lib/data.ts` (read only — no query or type change);
every other page and component; the leaderboard.

## Files

| File | Action | What changes |
|---|---|---|
| `web/lib/cadence.ts` | create | pure split-cadence helpers: id set, band mirror, size-change arithmetic and words |
| `web/lib/cadence.test.ts` | create | vitest unit tests for `cadence.ts` |
| `web/app/(app)/positions/page.tsx` | modify | import (after line 11); `splitCadence` + `held` consts (after line 48); `OrderRow` call (line 125); `emptyState` (155–160); `noOrders` (162–167); `WouldPick` subtitle (373–375); `OrderRow` (393–418); new `SizeCell` (after `OrderCells`, line 438) |
| `web/app/(app)/positions/positions.module.css` | modify | add `.cellWide` after `.cell dd` (line 72) |

## Implementation Steps

### Step 0: Give the worktree its own node_modules
**File:** `web/` (no source change)
**Change:** the worktree has no `web/node_modules`. Run once before anything else:
```bash
cd /home/miftah/.worktrees/seer/paper-split-cadence/web && npm ci
```
Confirm the baseline is green before editing: `npx vitest run && npx tsc --noEmit`.
**Impact:** none on the tree (`node_modules` is git-ignored).

### Step 1: Pure helpers
**File:** `web/lib/cadence.ts` (new)
**Change:** new module. No database access, no React, so tests import it directly. Facts it
mirrors, verified in the engine on `dffac31`:
- `MONTHLY_RANK_WEEKLY_RESIZE` (`id="monthly-rank-weekly-resize"`, `sim/rules.py:179`) and
  `MONTHLY_RANK_WEEKLY_RESIZE_TBILL` (`:181`); Phase 1 adds `monthly-rank-weekly-resize-frac`.
  All three are `replace(MONTHLY_HOLD, ...)`, so `resize=True`: held positions are traded back to
  target on rank sessions as well as resize sessions, so the cell is right on every decision.
- `RESIZE_BAND = Decimal("0.01")` (`sim/rules.py:39`); `sim/book.py:600` and `:637` skip a trim or
  an add when `gap_shares * last < RESIZE_BAND * equity` — strictly less means no trade, at
  exactly 1% it trades. `sizeChange` keeps that boundary.
- A buy of a symbol not held is not subject to the band (the band only gates `add`/`trim` of a
  held position), so a new symbol reads as a buy of the full amount whatever its size.
**Code:**
```ts
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
```
**Impact:** new file, nothing imports it until Step 3.

### Step 2: Unit tests
**File:** `web/lib/cadence.test.ts` (new)
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import {
  heldUsd, orderSizeChange, picksMonthlySizesWeekly, RESIZE_BAND, sizeChange, sizeLabel, sizeTip, SPLIT_CADENCE_RULES,
} from './cadence';

describe('picksMonthlySizesWeekly', () => {
  it('knows the three split-cadence rule sets', () => {
    expect(picksMonthlySizesWeekly('monthly-rank-weekly-resize')).toBe(true);
    expect(picksMonthlySizesWeekly('monthly-rank-weekly-resize-tbill')).toBe(true);
    expect(picksMonthlySizesWeekly('monthly-rank-weekly-resize-frac')).toBe(true);
    expect(SPLIT_CADENCE_RULES).toHaveLength(3);
  });
  it('is false for every other rule set and for none', () => {
    for (const id of ['monthly-hold', 'monthly-hold-frac', 'monthly-hold-tbill', 'weekly-hold', 'daily-switch', 'design-v0', '']) {
      expect(picksMonthlySizesWeekly(id)).toBe(false);
    }
    expect(picksMonthlySizesWeekly(null)).toBe(false);
    expect(picksMonthlySizesWeekly(undefined)).toBe(false);
  });
});

describe('sizeChange', () => {
  it('mirrors the engine band of 1% of equity', () => {
    expect(RESIZE_BAND).toBe(0.01);
  });
  it('reads a symbol not held as a buy of the full amount', () => {
    expect(sizeChange(0.2, 500, null)).toEqual({ action: 'buy', usd: 100 });
    // The band gates resizes only: a small new buy is still a buy.
    expect(sizeChange(0.005, 500, null)).toEqual({ action: 'buy', usd: 2.5 });
  });
  it('adds when the holding is below its target by at least the band', () => {
    expect(sizeChange(0.1, 1000, 80)).toEqual({ action: 'add', usd: 20 });
  });
  it('trims when the holding is above its target by at least the band', () => {
    expect(sizeChange(0.1, 1000, 130)).toEqual({ action: 'trim', usd: 30 });
  });
  it('trades at exactly the band and not under it (the engine skips only a strictly smaller gap)', () => {
    expect(sizeChange(0.1, 1000, 90)).toEqual({ action: 'add', usd: 10 });
    expect(sizeChange(0.1, 1000, 91)).toEqual({ action: 'none', usd: 0 });
    expect(sizeChange(0.1, 1000, 109)).toEqual({ action: 'none', usd: 0 });
    expect(sizeChange(0.1, 1000, 110)).toEqual({ action: 'trim', usd: 10 });
  });
  it('treats the idle instrument like any other symbol', () => {
    const held = heldUsd([{ symbol: 'BIL', value: 300 }]);
    expect(orderSizeChange(0.5, 1000, 'BIL', held)).toEqual({ action: 'add', usd: 200 });
  });
});

describe('heldUsd and orderSizeChange', () => {
  it('maps each symbol to its dollar value held now', () => {
    const held = heldUsd([{ symbol: 'AAPL', value: 120.5 }, { symbol: 'MSFT', value: 80 }, { symbol: 'AAPL', value: 0.5 }]);
    expect(held.get('AAPL')).toBe(121);
    expect(held.get('MSFT')).toBe(80);
    expect(held.has('NVDA')).toBe(false);
  });
  it('is null when the weight or the equity is unknown', () => {
    const held = heldUsd([]);
    expect(orderSizeChange(null, 1000, 'AAPL', held)).toBeNull();
    expect(orderSizeChange(0.1, null, 'AAPL', held)).toBeNull();
  });
  it('buys a symbol that is not held', () => {
    expect(orderSizeChange(0.25, 558, 'NVDA', heldUsd([{ symbol: 'AAPL', value: 100 }]))).toEqual({ action: 'buy', usd: 139.5 });
  });
});

describe('sizeLabel and sizeTip', () => {
  it('says it in plain words with dollars to the cent', () => {
    expect(sizeLabel({ action: 'buy', usd: 40 })).toBe('Buy about $40.00');
    expect(sizeLabel({ action: 'add', usd: 6.123 })).toBe('Add about $6.12');
    expect(sizeLabel({ action: 'trim', usd: 9.8 })).toBe('Trim about $9.80');
    expect(sizeLabel({ action: 'none', usd: 0 })).toBe('No change');
  });
  it('has a tooltip for every action', () => {
    for (const action of ['buy', 'add', 'trim', 'none'] as const) {
      expect(sizeTip({ action, usd: 1 }).length).toBeGreaterThan(0);
    }
    expect(sizeTip({ action: 'none', usd: 0 })).toContain('1%');
  });
});
```
**Impact:** adds tests; nothing else.

### Step 3: Import the helpers in the page
**File:** `web/app/(app)/positions/page.tsx:7` (insert one line before the `@/lib/data` import block, keeping imports sorted by path)
**Change:** add the import. Final import block (lines 1–16 after the edit):
```tsx
import { Crown, Gavel, Landmark, TriangleAlert } from 'lucide-react';
import { AppHeader } from '@/components/AppHeader';
import { PaperChip } from '@/components/PaperChip';
import { selectStrategy, sharesLabel, strategyIcon } from '@/components/roster';
import { StrategySwitch } from '@/components/StrategySwitch';
import { WhyToggle } from '@/components/WhyToggle';
import { heldUsd, orderSizeChange, picksMonthlySizesWeekly, sizeLabel, sizeTip, type SizeChange } from '@/lib/cadence';
import {
  bookPreview, pendingOrders, positions as getPositions, runStatus, strategies, vetoes as getVetoes,
  type Holding, type Pending, type PendingOrder, type Preview, type RunStatus, type Strategy, type Veto,
} from '@/lib/data';
import { companyName, monthDay, pct, shortDate, signedPct, signedRp, signedUsd, usd } from '@/lib/format';
import { wibDate } from '@/lib/session';
import { cardBg } from '@/lib/slots';
import { checkedLine, headlinesLabel, noCheckLine, vetoSheet, type VetoSheet } from '@/lib/vetoes';
import s from './positions.module.css';
```
**Impact:** none on its own. All line numbers below are the ORIGINAL file's (add 1 after this step).

### Step 4: Split-cadence flag and holdings map in `Positions`
**File:** `web/app/(app)/positions/page.tsx:48` (after `const orderSession = ...`)
**Change:** add two consts. `book` (line 38) is `open.filter(p => p.kind !== 'bracket')`: the book
strategy's own positions, idle instrument included; `Holding.value` is `shares × current`
(`web/lib/data.ts:202`, `:248`, `current` = `book_positions.mark`).
**Code** (inserted between the original lines 48 and 49):
```tsx
  // Monthly pick, weekly size check (web/lib/cadence.ts): only these strategies show the change per order.
  const splitCadence = !!strat && picksMonthlySizesWeekly(strat.rulesId);
  const held = heldUsd(book);
```
**Impact:** none until used in Step 5.

### Step 5: Pass the size change to each order row
**File:** `web/app/(app)/positions/page.tsx:124-126`
**Change:** replace the `pending.orders.map(...)` block with:
```tsx
                {pending.orders.map(o => (
                  <OrderRow key={o.key} o={o} equity={pending.equity} passed={checks.find(v => v.symbol === o.symbol && v.verdict === 'allow')}
                    size={splitCadence && o.kind === 'book' ? orderSizeChange(o.weight, pending.equity, o.symbol, held) : undefined} />
                ))}
```
**Impact:** `size` is `undefined` for every non-split-cadence strategy, so `OrderRow` renders as today.

### Step 6: Empty-state sentence
**File:** `web/app/(app)/positions/page.tsx:155-160`
**Change:** full replacement of `emptyState`. The non-split book line is the original string unchanged.
**Code:**
```tsx
function emptyState(st: Strategy | null): [string, string | null] {
  if (!st) return ['No strategies yet.', null];
  if (st.engine === 'benchmark') return ['Not bought yet.', `${st.name} is bought at the open of the first paper session.`];
  if (st.engine === 'book' && picksMonthlySizesWeekly(st.rulesId)) {
    return ['In cash.', `${st.short} makes its first decision at its first paper session, then picks its stocks on the first session of each month and checks how much to hold on the first session of each week.`];
  }
  if (st.engine === 'book') return ['In cash.', `${st.short} makes its first decision at its first paper session, then rebalances on the first session of each month.`];
  return ['No open positions.', null];
}
```

### Step 7: No-orders sentence
**File:** `web/app/(app)/positions/page.tsx:162-172`
**Change:** full replacement of `noOrders`. Only the not-a-decision-night book line branches; the
"decided to hold cash" line and every bracket line are unchanged.
**Code:**
```tsx
function noOrders(st: Strategy, p: Pending, sheet: VetoSheet | null): string {
  if (st.engine === 'book') {
    if (p.decision) return `No orders. ${st.short} decided to hold cash.`;
    return picksMonthlySizesWeekly(st.rulesId)
      ? `No orders. ${st.short} keeps what it holds. It picks its stocks on the first session of each month and checks how much to hold on the first session of each week.`
      : `No orders. ${st.short} keeps what it holds until it rebalances on the first session of each month.`;
  }
  if (sheet && sheet.state === 'missing') return `No orders. ${st.short} buys nothing this session.`;
  if (sheet && sheet.state === 'failed') return `No orders. ${st.short} sits this session out.`;
  if (sheet && sheet.allowed === 0) return 'No orders. Nothing passed the news check.';
  return 'No setups tonight. Cash is a position.';
}
```

### Step 8: "Would pick now" subtitle
**File:** `web/app/(app)/positions/page.tsx:360-391`
**Change:** full replacement of `WouldPick`. The subtitle branches in a JSX ternary whose
non-split arm is the original JSX unchanged, so existing strategies' markup (React's text-node
separators included) stays identical. Per the plan index Decision on `book_previews`, a
split-cadence strategy's resize night has a pending decision, so this section is hidden that
night and the orders show instead; it shows on the nights between.
**Code:**
```tsx
/**
 * What a book strategy would hold if it rebalanced tonight (`book_previews`): shown between its monthly
 * decisions so a monthly strategy is never silent. Display only: nothing trades on it. Each row's reason
 * is the facts the ranking read, as stored (no LLM: previews are replaced every night); a row without
 * stored facts shows no toggle rather than a list of "unavailable" lines. A strategy that picks monthly
 * and checks its sizes weekly says so instead of "only trades when it rebalances".
 */
function WouldPick({ st, preview }: { st: Strategy; preview: Preview }) {
  return (
    <section className={`sheet over bg-sheet ${s.orders}`}>
      <div className={s.between}>
        <span className="eyebrow">{st.short} would pick now</span>
        <span className="chip num">{preview.picks.length}</span>
      </div>
      <span className={s.ordersSub}>
        {picksMonthlySizesWeekly(st.rulesId)
          ? <>From the {shortDate(preview.dataDate!)} closes. {st.short} only changes its stocks on the first session of each month, and checks how much to hold on the first session of each week.</>
          : <>From the {shortDate(preview.dataDate!)} closes. {st.short} only trades when it rebalances, on the first session of each month.</>}
      </span>
      <ul className={s.orderList}>
        {preview.picks.map(p => (
          <li key={p.symbol} className={s.order}>
            <div className={s.orderHead}>
              <span className={s.rank} data-tip="Rank in tonight's list">{p.rank}</span>
              <span className={s.orderSym}>{p.symbol}</span>
              <span className={s.orderCo}>last {usd(p.last)}</span>
            </div>
            <OrderCells cells={[['Weight', pct(p.weight, 1)]]} />
            {p.evidence && <WhyToggle text={null} facts={p.evidence} label="Why it's on the list" />}
          </li>
        ))}
      </ul>
    </section>
  );
}
```

### Step 9: `OrderRow` takes the size change
**File:** `web/app/(app)/positions/page.tsx:393-428`
**Change:** full replacement of `OrderRow`. The only differences from today: the optional `size`
prop and the `SizeCell` line right after `OrderCells`.
**Code:**
```tsx
function OrderRow({ o, equity, passed, size }: { o: PendingOrder; equity: number | null; passed?: Veto; size?: SizeChange | null }) {
  const cells: [string, string][] = o.kind === 'bracket'
    ? [
        ['Limit', o.limit === null ? '—' : usd(o.limit)],
        ['Target', o.tp === null ? '—' : usd(o.tp)],
        ['Stop', o.sl === null ? '—' : usd(o.sl)],
        ['Shares', o.shares === null ? '—' : String(o.shares)],
      ]
    : [
        ['Weight', o.weight === null ? '—' : pct(o.weight, 1)],
        // What the weight buys at tonight's equity; the open's equity sizes the real order.
        ['About', o.weight === null || equity === null ? '—' : usd(o.weight * equity)],
        ['Limit', o.limit === null ? 'Open' : usd(o.limit)],
        o.sl === null && o.tp === null
          ? ['Exit', 'Monthly']
          : ['Stop', o.sl === null ? '—' : usd(o.sl)],
      ];
  return (
    <li className={s.order}>
      <div className={s.orderHead}>
        {o.kind === 'book' && <span className={s.rank}>{o.rank}</span>}
        <span className={s.orderSym}>{o.symbol}</span>
        <span className={s.orderCo}>{companyName(o.company, o.symbol) ? `${o.company} · ` : ''}last {usd(o.last)}</span>
      </div>
      <OrderCells cells={cells} />
      {size !== undefined && <SizeCell size={size} />}
      <WhyToggle text={o.explanation} facts={o.evidence} />
      {passed && (
        <>
          <span className={s.vetoFacts}>{headlinesLabel(passed.headlineCount)} read{passed.earningsDate ? ` · earnings ${monthDay(passed.earningsDate)}` : ''}</span>
          <WhyToggle text={passed.reason.trim() === '' ? null : passed.reason} label="Why it passed the news check"
            missing="No reason was stored for this check." />
        </>
      )}
    </li>
  );
}
```
**Impact:** `{size !== undefined && ...}` renders `false` (nothing) when `size` is omitted, so the
non-split-cadence row markup is unchanged.

### Step 10: `SizeCell`
**File:** `web/app/(app)/positions/page.tsx:438` (append after `OrderCells`, end of file)
**Change:** a single full-width cell in the same `dl`/`dt`/`dd` look as the other order cells (the
Seer v2 cells: small uppercase label, 18px tabular number), with a tooltip through the app's global
`data-tip` handler (`web/components/tooltip.ts`). Not a button; no icon needed.
**Code:**
```tsx
/**
 * Split-cadence strategies only: the order against what is held now, at tonight's marks and equity.
 * "No change" when the gap is under 1% of paper equity, the engine's RESIZE_BAND (web/lib/cadence.ts).
 */
function SizeCell({ size }: { size: SizeChange | null }) {
  return (
    <dl className={s.cells}>
      <div className={`${s.cell} ${s.cellWide}`} data-tip={size ? sizeTip(size) : 'Paper equity is not known yet'}>
        <dt>Against what it holds now</dt>
        <dd className="num">{size ? sizeLabel(size) : '—'}</dd>
      </div>
    </dl>
  );
}
```

### Step 11: Wide cell style
**File:** `web/app/(app)/positions/positions.module.css:72` (insert after the `.cell dd` rule)
**Code:**
```css
.cellWide { grid-column: 1 / -1; }
```
**Impact:** a new class used only by `SizeCell`; the 4-column grid keeps "Trim about $123.45"
on one line at phone width instead of squeezing it into a quarter column.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/paper-split-cadence/web && npx tsc --noEmit`
**Tests:** `cd /home/miftah/.worktrees/seer/paper-split-cadence/web && npx vitest run` (new
`lib/cadence.test.ts` plus every existing test green)
**Manual check:** optional, with the demo seed: set one book strategy's `rules_id` to
`monthly-rank-weekly-resize` in a local DB and open `/positions?s=<id>`: each order shows the
wide cell; switch back and the page is as before. Also `git diff` of `page.tsx`: every original
string for non-split strategies is still present verbatim (grep
`rebalances on the first session of each month` → 2 hits, `only trades when it rebalances` → 1 hit).
**Exit criteria:** vitest and tsc green; for a strategy whose `rulesId` is not one of the three
ids, `emptyState`, `noOrders`, `WouldPick` and `OrderRow` produce the same output as on `dffac31`;
for a split-cadence strategy the three sentences speak of a monthly pick and a weekly size check
and each book order shows Buy / Add / Trim about $X or No change.

## Handoffs

- **Phase 1 (R5):** the `'monthly-rank-weekly-resize-frac'` id string in `SPLIT_CADENCE_RULES`
  must equal the id Phase 1 gives `MONTHLY_RANK_WEEKLY_RESIZE_FRAC` in `sim/rules.py`.
  Reconciled: phase-1.md creates exactly `monthly-rank-weekly-resize-frac`, so the string stands.
- **Not done, not in any R (note for the owner/later):** on a rank session the page lists only
  the targets; a held symbol dropped from the basket is sold but has no order row, so it gets no
  "Sell" cell. That is true for every book strategy today (the card shows "Sells at the next open"
  only when `exitPending`), so it is outside R6 and left alone.
- **Not done:** the `Exit: Monthly` cell text for book orders without stop/take is left as is for
  split-cadence strategies too (the basket still changes monthly; the weekly check is said by the
  new cell and the copy).

## Rollback

Revert this phase's commit: delete `web/lib/cadence.ts` and `web/lib/cadence.test.ts`, restore
`positions/page.tsx` and `positions.module.css`. No engine, data or migration involvement;
independent of Phases 1 and 2.
