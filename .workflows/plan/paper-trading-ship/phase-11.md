# Phase 11: Web: Today, Positions, History

**Plan set:** `PAPER_TRADING_SHIP_PLAN.md`
**Analysis:** `20261004-082027-P4S7_code_analyzer.md`
**Satisfies:** R4 — Today's SPY-champion no-buys state, paper labelling (D3), book positions and trades in Positions and History, no 4-slot assumption for book strategies
**Depends on:** Phase 10 (web data layer)
**Difficulty:** HARD
**Package:** `web/app/(app)` (+ new shared `web/components/*`)

---

## Goal

Today shows "SPY buy-and-hold is the champion. Seer recommends no buys." in the Seer v2 empty-state
style whenever the champion is the benchmark (or there is none), and never shows research picks,
slot dots or day-5 actions. Positions gets a roster-driven, icon-only strategy switcher (`?s=`),
a dashed "Paper" chip on every research card, bracket cards (stop/target range + 5 day dots), book
cards (fractional shares, weight, days held, P/L, stop/target only when set), a benchmark card for
the SPY holding, a "Paper orders for <session>" sheet with WhyToggle explanations, and a warning
sheet when the latest run's paper step did not succeed. History's strategy filter is built from the
roster, exit reasons `signal` and `forced` get icons and tooltips, and each research row carries a
Paper tag.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts.

**Deletes:**
- `web/app/(app)/history/page.tsx`: the hardcoded `STRAT` map and `STRAT_BTNS` list (lines 14, 18) and the `BrainCircuit`, `Gavel`, `ListFilter`, `Sigma` imports.
- `web/app/(app)/positions/page.tsx`: the `champion()` call and the `SLOT_BG` import (cards use phase 10's `cardBg`).

**Renames:** none.

**Creates:**
- `web/components/roster.ts` — pure helpers that `web/lib` lacks: `strategyIcon(name: string): LucideIcon`, `selectStrategy<T extends { id: string; isBenchmark: boolean }>(roster: T[], requested: string | undefined): T | null`, `sharesLabel(n: number): string`. (Short labels and the paper flag are phase 10's `Strategy.short` / `lib/strategy.ts` `shortLabel` and `Strategy.isPaper`; not duplicated.)
- `web/components/roster.test.ts` — vitest for the helpers.
- `web/components/StrategySwitch.tsx` — `export const ALL = 'all'`; `export function StrategySwitch(props: { strategies: { id: string; name: string; icon: string }[]; current: string; href: (id: string) => string; label: string; allTip?: string })`. **Server component** (no `'use client'`; `href` is a function prop, so it must be rendered from a server component).
- `web/components/StrategySwitch.module.css` — `.group`.
- `web/components/PaperChip.tsx` — `export function PaperChip(props: { size?: 'sm' | 'md' })`.
- `web/components/PaperChip.module.css` — `.md`, `.sm`.

**Signature changes:**
- `Positions()` page now takes `{ searchParams: Promise<{ s?: string }> }`.

**Requires (from Phase 10, `web/lib/data.ts` / `web/lib/slots.ts` / `web/lib/strategy.ts`).** Reconciled
against phase 10's actual exports; these are the names this phase codes against:

```ts
// lib/strategy.ts
export type Engine = 'bracket' | 'book' | 'benchmark';
export function shortLabel(name: string, id: string): string;
// lib/data.ts
export type Strategy = { id; name; sub; icon; isChampion; isBenchmark;
  engine: Engine; rulesId: string | null; paperStart: string | null; gate: Gate; isPaper: boolean; short: string };
export function strategies(): Promise<Strategy[]>;            // ORDER BY sort, id (SPY, A, F4, F1)
export function champion(): Promise<Strategy | null>;
export type RunState = 'running' | 'success' | 'failed';
export type RunStatus = { sessionDate; dataDate; finishedAt; isDemo; stale; usdIdr;
  latestStatus: RunState | null; paperStatus: RunState | null; paperError: string | null; paperFinishedAt: Date | null };
export function runStatus(now?: Date): Promise<RunStatus>;
export type Pick = { id; slot; symbol; company; last; limit; tp; sl; shares; explanation };   // unchanged
export function picks(strategyId: string, sessionDate: string): Promise<Pick[]>;          // unchanged
export type Holding = { key: string; kind: Engine; orderId: number | null; slot: number | null; symbol: string;
  company: string | null; shares: number; entry: number; entryDate: string | null; current: number;
  tp: number | null; sl: number | null; day: number; maxDays: number | null; value: number;
  weight: number | null; pnl: number; pnlPct: number; dismissed: boolean; exitPending: boolean };
export function positions(strategyId: string): Promise<Holding[]>;
export type PendingOrder = { key; kind: 'bracket' | 'book'; sessionDate; rank; slot: number | null; symbol;
  company: string | null; last; limit: number | null; tp: number | null; sl: number | null;
  shares: number | null; weight: number | null; explanation: string | null };
export type Pending = { sessionDate: string | null; decision: boolean; orders: PendingOrder[] };
export function pendingOrders(strategyId: string): Promise<Pending>;
export type ExitReason = 'tp' | 'sl' | 'time' | 'gap' | 'signal' | 'forced';
export type Trade = { key: string; id: number; kind: 'bracket' | 'book'; strategyId: string; strategyShort: string;
  symbol; entry; exit; entryDate: string | null; exitDate: string; shares: number | null; days: number | null;
  reason: ExitReason; pnl: number };
export function closedTrades(strategyId: string | null, outcome: 'win' | 'loss' | null): Promise<Trade[]>;
// lib/slots.ts
export const SLOT_BG, SLOT_LETTERS; export const slotBg, slotLetter, slotCount, cardBg;
```
The three pages are quoted **as phase 10 Step 10 leaves them** (its minimal compile fixes land first;
this phase then replaces each page whole). Sequence 10 → 11 → 12.

Also from phase 10's demo seed (`seed-demo.mjs`): SPY is champion; roster rows A, F4-MOM12-N20-TREND,
F1-SPY-SMA200-M with `engine`, `rules_id`, `paper_start`; the demo `runs` row has
`paper_status = 'success'`; book positions for at least one book strategy and SPY; pending `orders` for A
and `book_targets` for a book strategy on the demo session; closed `book_trades` including a `signal`
and a `forced` exit — so the manual visual check exercises every state below.

**Leaves alone (owned by others):** `web/lib/*` (phase 10), `web/scripts/seed-demo.mjs` (phase 10),
`web/app/(app)/leaderboard/*` (phase 12), `web/components/{AppHeader,Nav,WhyToggle,CopyButton,RefreshButton,TooltipLayer,tooltip}*` (unchanged),
`web/app/globals.css` (unchanged), `engine/*`, workflows, docs.

## Files

| File | Action | What changes |
|---|---|---|
| `web/components/roster.ts` | create | pure helpers `web/lib` lacks: icon map, default selection, fractional shares label |
| `web/components/roster.test.ts` | create | vitest for the helpers |
| `web/components/StrategySwitch.tsx` | create | icon-only `Link` per roster strategy, `?s=` hrefs, `aria-current`, `data-tip` = name, optional "All" button |
| `web/components/StrategySwitch.module.css` | create | button group layout |
| `web/components/PaperChip.tsx` | create | dashed "Paper" label with `FlaskConical`, tooltip |
| `web/components/PaperChip.module.css` | create | chip sizes |
| `web/app/(app)/page.tsx` | modify (full replace of phase 10's version) | champion gate for picks; no-buys state; no slot dots / actions for a benchmark champion |
| `web/app/(app)/today.module.css` | modify (insert after line 26) | `.noneSub` |
| `web/app/(app)/positions/page.tsx` | modify (full replace of phase 10's version) | switcher, paper chip, bracket/book/benchmark cards via `Holding.kind`, paper orders via `pendingOrders`, paper-step warning |
| `web/app/(app)/positions/positions.module.css` | modify (full replace, lines 1–42) | new card, warning, orders and weight styles |
| `web/app/(app)/history/page.tsx` | modify (full replace; phase 10 leaves it unchanged) | roster-driven filter via `StrategySwitch`, `signal`/`forced` reasons, Paper tag |
| `web/app/(app)/history/history.module.css` | modify (full replace, lines 1–42) | `.line1` no-wrap/min-width, `.tag` `flex: none` |

## Implementation Steps

### Step 1: Pure roster helpers
**File:** `web/components/roster.ts` (new)
**Change:** One place maps a `strategies.icon` name to its Lucide component and picks the default
selection. Short labels and the paper flag are **not** duplicated here: they are phase 10's
`Strategy.short` (`lib/strategy.ts` `shortLabel`) and `Strategy.isPaper`. Phase 12 imports `strategyIcon`
and `selectStrategy` from here instead of its own maps.
**Code:**
```ts
import { BrainCircuit, Gavel, Landmark, Shield, Sigma, TrendingUp, type LucideIcon } from 'lucide-react';

// The `icon` column of `strategies` names a Lucide icon (kebab-case). Roster: landmark (SPY),
// sigma (A), trending-up (F4), shield (F1); brain-circuit and gavel kept for old demo rows.
const ICONS: Record<string, LucideIcon> = {
  landmark: Landmark,
  sigma: Sigma,
  'trending-up': TrendingUp,
  shield: Shield,
  'brain-circuit': BrainCircuit,
  gavel: Gavel,
};

/** The Lucide icon a strategies row names; Sigma when the name is unknown. */
export const strategyIcon = (name: string): LucideIcon => ICONS[name] ?? Sigma;

// Short labels and the paper flag are phase 10's: `Strategy.short` (lib/strategy.ts `shortLabel`)
// and `Strategy.isPaper`. This module holds only what web/lib lacks.

/**
 * The strategy a screen shows: the requested id when it is on the roster, else the first
 * research (non-benchmark) strategy, else the first row, else null.
 */
export function selectStrategy<T extends { id: string; isBenchmark: boolean }>(
  roster: T[],
  requested: string | undefined,
): T | null {
  return roster.find(r => r.id === requested) ?? roster.find(r => !r.isBenchmark) ?? roster[0] ?? null;
}

/** 1 -> '1 share', 3 -> '3 shares', 2.50004 -> '2.5 shares'. Book shares are fractional to 4 dp. */
export function sharesLabel(n: number): string {
  const v = Number(n.toFixed(4));
  return v === 1 ? '1 share' : `${v} shares`;
}
```
**Impact:** new file; nothing imports it until steps 4–7.

### Step 2: Tests for the helpers
**File:** `web/components/roster.test.ts` (new)
**Code:**
```ts
import { Landmark, Shield, Sigma, TrendingUp } from 'lucide-react';
import { describe, expect, it } from 'vitest';
import { selectStrategy, sharesLabel, strategyIcon } from './roster';

const roster = [
  { id: 'SPY', name: 'SPY', isChampion: true, isBenchmark: true },
  { id: 'A', name: 'A · Quant', isChampion: false, isBenchmark: false },
  { id: 'F4-MOM12-N20-TREND', name: 'F4 · Momentum', isChampion: false, isBenchmark: false },
  { id: 'F1-SPY-SMA200-M', name: 'F1 · Trend', isChampion: false, isBenchmark: false },
];

describe('selectStrategy', () => {
  it('returns the requested strategy when it is on the roster', () => {
    expect(selectStrategy(roster, 'F1-SPY-SMA200-M')?.id).toBe('F1-SPY-SMA200-M');
    expect(selectStrategy(roster, 'SPY')?.id).toBe('SPY');
  });
  it('defaults to the first research strategy', () => {
    expect(selectStrategy(roster, undefined)?.id).toBe('A');
    expect(selectStrategy(roster, 'B')?.id).toBe('A');
  });
  it('falls back to the first row, then null', () => {
    expect(selectStrategy([roster[0]], undefined)?.id).toBe('SPY');
    expect(selectStrategy([], undefined)).toBeNull();
  });
});

describe('strategyIcon', () => {
  it('maps the roster icons and falls back to Sigma', () => {
    expect(strategyIcon('landmark')).toBe(Landmark);
    expect(strategyIcon('trending-up')).toBe(TrendingUp);
    expect(strategyIcon('shield')).toBe(Shield);
    expect(strategyIcon('nope')).toBe(Sigma);
  });
});

describe('sharesLabel', () => {
  it('formats whole and fractional shares', () => {
    expect(sharesLabel(1)).toBe('1 share');
    expect(sharesLabel(3)).toBe('3 shares');
    expect(sharesLabel(2.5)).toBe('2.5 shares');
    expect(sharesLabel(0.123456)).toBe('0.1235 shares');
  });
});
```
**Impact:** vitest picks it up by default (`**/*.test.ts`); no config change.

### Step 3: Shared components — StrategySwitch and PaperChip
**File:** `web/components/StrategySwitch.tsx` (new)
**Code:**
```tsx
import { ListFilter } from 'lucide-react';
import Link from 'next/link';
import { strategyIcon } from './roster';
import s from './StrategySwitch.module.css';

export const ALL = 'all';

type Props = {
  /** Roster rows in display order. */
  strategies: { id: string; name: string; icon: string }[];
  /** The selected id, or ALL when `allTip` is set and nothing is filtered. */
  current: string;
  /** Builds each link's href (keep other query params there). */
  href: (id: string) => string;
  /** Accessible name of the group. */
  label: string;
  /** When set, a leading ListFilter button with id ALL and this tooltip. */
  allTip?: string;
};

/**
 * Icon-only strategy switcher: one Link per roster strategy with its own Lucide icon,
 * tooltip and aria-label = its name, aria-current on the selected one.
 * Server component: `href` is a function prop.
 */
export function StrategySwitch({ strategies, current, href, label, allTip }: Props) {
  const items = [
    ...(allTip ? [{ id: ALL, tip: allTip, Icon: ListFilter }] : []),
    ...strategies.map(st => ({ id: st.id, tip: st.name, Icon: strategyIcon(st.icon) })),
  ];
  return (
    <nav className={s.group} aria-label={label}>
      {items.map(({ id, tip, Icon }) => {
        const on = current === id;
        return (
          <Link key={id} href={href(id)} replace scroll={false} className="icon-btn md"
            data-tip={tip} aria-label={tip} aria-current={on ? 'true' : undefined}>
            <Icon size={19} strokeWidth={on ? 2 : 1.5} />
          </Link>
        );
      })}
    </nav>
  );
}
```

**File:** `web/components/StrategySwitch.module.css` (new)
```css
.group { display: flex; flex-wrap: wrap; gap: 6px; }
```

**File:** `web/components/PaperChip.tsx` (new)
```tsx
import { FlaskConical } from 'lucide-react';
import s from './PaperChip.module.css';

const TIP = 'Paper trade: simulated, no real money';

/**
 * Marks a research strategy's position, order or trade as paper (D3). A data label, not a
 * button. Dashed like the design's empty slots: it is not a real holding.
 */
export function PaperChip({ size = 'md' }: { size?: 'sm' | 'md' }) {
  return (
    <span className={size === 'sm' ? s.sm : s.md} data-tip={TIP}>
      <FlaskConical size={size === 'sm' ? 12 : 15} strokeWidth={1.75} aria-hidden="true" />
      Paper
    </span>
  );
}
```

**File:** `web/components/PaperChip.module.css` (new)
```css
.md, .sm {
  flex: none;
  display: inline-flex;
  align-items: center;
  border: 1.5px dashed var(--ink-3);
  border-radius: 999px;
  color: var(--ink-2);
  white-space: nowrap;
  letter-spacing: 0.02em;
}
.md { height: 34px; padding: 0 13px; gap: 6px; font-size: 15px; }
.sm { height: 24px; padding: 0 8px; gap: 4px; font-size: 12px; }
```
**Impact:** new files only. Phase 12 reuses `StrategySwitch`, `PaperChip` and `strategyIcon`.

### Step 4: Today — the SPY-champion, no-buys state
**File:** `web/app/(app)/page.tsx:1-171` (full replace)
**Change:** The file is quoted as phase 10 Step 10 left it (lines 26, 87, 92 already on `Holding`); this
step replaces it whole. Picks, slot dots, empty-slot cards and day-5 actions exist only for a non-benchmark bracket
champion (`picksChampion`). With SPY as champion (D2) or no champion, the stale alarm still wins; otherwise
the design's empty-state sheet reads "SPY buy-and-hold is the champion." / "Seer recommends no buys."
Research strategies are never queried here (`champion()` only), so research picks cannot appear.
**Code:**
```tsx
import { Check, Crown, TriangleAlert } from 'lucide-react';
import { AppHeader } from '@/components/AppHeader';
import { CopyButton } from '@/components/CopyButton';
import { RefreshButton } from '@/components/RefreshButton';
import { WhyToggle } from '@/components/WhyToggle';
import {
  champion, picks as getPicks, positions as getPositions, runStatus,
  type Holding, type Pick, type Strategy,
} from '@/lib/data';
import { money, monthDay, rp, shortDate, signedRp, signedUsd, usd } from '@/lib/format';
import { wibDate } from '@/lib/session';
import { SLOT_BG, SLOT_LETTERS, slotBg, slotLetter } from '@/lib/slots';
import { dismiss } from './actions';
import s from './today.module.css';

export const dynamic = 'force-dynamic';

const ORDINAL = ['first', 'second', 'third', 'fourth'];
const WIB_TIME = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Jakarta', hour: '2-digit', minute: '2-digit' });

/** Only a bracket champion that is not the benchmark makes buy picks. With SPY as champion (D2), none does. */
const picksChampion = (c: Strategy | null): Strategy | null =>
  c && !c.isBenchmark && c.engine === 'bracket' ? c : null;

const champLabel = (c: Strategy | null) =>
  !c ? 'No champion yet' : c.isBenchmark ? `${c.name} · ${c.sub}` : `Strategy ${c.id} · ${c.sub}`;

const noBuysTitle = (c: Strategy | null) =>
  !c ? 'No champion yet.' : c.isBenchmark ? `${c.name} buy-and-hold is the champion.` : `${c.name} is the champion.`;

export default async function Today() {
  const now = new Date();
  const [champ, run] = await Promise.all([champion(), runStatus(now)]);
  const pc = picksChampion(champ);
  const [picks, open] = await Promise.all([
    pc && run.sessionDate && !run.stale ? getPicks(pc.id, run.sessionDate) : Promise.resolve([] as Pick[]),
    pc ? getPositions(pc.id) : Promise.resolve([] as Holding[]),
  ]);
  // Phase 10's guard, kept: only a bracket holding with an order id and a time exit has a day-5 action.
  const actions = open.filter(p => p.orderId !== null && p.maxDays !== null && p.day >= p.maxDays && !p.dismissed);
  const filled = new Set(picks.map(p => p.slot));
  const emptySlots = [1, 2, 3, 4].filter(n => !filled.has(n));
  const session = run.sessionDate ? shortDate(run.sessionDate) : '—';
  const stratLabel = champLabel(champ);

  return (
    <>
      <AppHeader
        date={shortDate(wibDate(now))}
        title="Today"
        deskTitle={run.stale ? 'Today' : pc ? `Picks for US session ${session}` : `US session ${session}`}
        deskAside={<span className="pill-outline" style={{ height: 52, fontSize: 16, color: 'var(--ink)' }}><Crown size={16} />{stratLabel}</span>}
        demo={run.isDemo}
      />

      <div className="stack">
        <section className={`sheet bg-sheet mobile-only ${s.summary}`}>
          <div className={s.between}>
            <span className="eyebrow">US session</span>
            <span className="pill-outline" style={{ fontSize: 16, padding: '0 20px' }}>{session}</span>
          </div>
          <div className={s.between} style={{ alignItems: 'flex-end' }}>
            <div className={s.count}>
              <span className={s.countNum}>{run.stale ? '—' : picks.length}</span>
              <span className={s.countLabel}>{pc ? 'Picks tonight' : 'Buys tonight'}</span>
            </div>
            <div className={s.slotsCol}>
              {pc && (
                <div className="slot-dots" aria-label={`${picks.length} of 4 slots filled`}>
                  {SLOT_LETTERS.map((l, i) => (
                    <span key={i} className={`slot-dot ${filled.has(i + 1) ? SLOT_BG[i] : 'empty'}`}>{l}</span>
                  ))}
                </div>
              )}
              <span className={s.strat}><Crown size={15} />{stratLabel}</span>
            </div>
          </div>
        </section>

        {run.stale ? (
          <section className={`sheet over ${s.alarm}`}>
            <div className={s.between}>
              <span className={s.alarmIcon}><TriangleAlert size={28} /></span>
              <RefreshButton className={`icon-btn ${s.alarmBtn}`} />
            </div>
            <span className={s.alarmTitle}>
              {run.dataDate ? `Data is from ${monthDay(run.dataDate)}. Do not trade today.` : 'No data yet. Do not trade today.'}
            </span>
            <span className={s.alarmSub}>
              {run.finishedAt
                ? `Last good run ${shortDate(wibDate(run.finishedAt))} at ${WIB_TIME.format(run.finishedAt)} WIB. Picks stay hidden until fresh prices arrive.`
                : 'The nightly engine has not completed a run yet. Picks stay hidden until it does.'}
            </span>
          </section>
        ) : !pc ? (
          <section className={`sheet over bg-stone ${s.none}`}>
            <span>{noBuysTitle(champ)}</span>
            <span style={{ color: 'var(--ink-3)' }}>Seer recommends no buys.</span>
            <span className={s.noneSub}>
              Research strategies trade on paper only, with no real money. Their orders are in Positions, never here.
            </span>
          </section>
        ) : picks.length === 0 ? (
          <section className={`sheet over bg-stone ${s.none}`}>
            <span>No setups today.</span>
            <span style={{ color: 'var(--ink-3)' }}>Cash is a position.</span>
          </section>
        ) : (
          <div className={s.board}>
            {actions.map(a => (
              <section key={a.key} className={`sheet over bg-coral ${s.action}`}>
                <span className="eyebrow">Action needed</span>
                <div className={s.actionRow}>
                  <span className={s.actionText}><b>{a.symbol}</b>: day {a.day} of {a.maxDays}. Cancel bracket and sell at market.</span>
                  <form action={dismiss}>
                    <input type="hidden" name="orderId" value={a.orderId ?? ''} />
                    <button type="submit" className={`icon-btn ${s.onCoral}`} data-tip="Mark as done" aria-label="Mark as done">
                      <Check size={22} />
                    </button>
                  </form>
                </div>
              </section>
            ))}

            <div className={s.grid}>
              {picks.map(p => <PickCard key={p.id} p={p} rate={run.usdIdr} />)}
              {emptySlots.map(n => (
                <section key={n} className={`${s.emptySlot} desk-only`}>
                  <span className={s.emptyDot}>{slotLetter(n)}</span>
                  <span className={s.emptyTitle}>Empty slot</span>
                  <span className={s.emptySub}>No {ORDINAL[n - 1]} stock passed the rules tonight.</span>
                </section>
              ))}
            </div>

            {emptySlots.length > 0 && (
              <section className={`sheet over bg-sheet mobile-only ${s.emptyRow}`}>
                <span className={s.emptyDot}>{slotLetter(emptySlots[0])}</span>
                <div className={s.emptyText}>
                  <span className={s.emptyTitle}>{emptySlots.length === 1 ? 'Empty slot' : `${emptySlots.length} empty slots`}</span>
                  <span className={s.emptySub}>
                    {emptySlots.length === 1 ? `No ${ORDINAL[emptySlots[0] - 1]} stock passed the rules tonight.` : `Only ${picks.length} passed the rules tonight.`}
                  </span>
                </div>
              </section>
            )}
          </div>
        )}
        <div className="nav-clear" />
      </div>
    </>
  );
}

function PickCard({ p, rate }: { p: Pick; rate: number }) {
  const cost = p.limit * p.shares, profit = (p.tp - p.limit) * p.shares, loss = (p.limit - p.sl) * p.shares;
  const fields = [
    { label: 'Limit buy', unit: '$', value: money(p.limit), tip: 'Copy limit price' },
    { label: 'Take profit', unit: '$', value: money(p.tp), tip: 'Copy take-profit price' },
    { label: 'Stop loss', unit: '$', value: money(p.sl), tip: 'Copy stop-loss price' },
    { label: 'Shares', unit: '', value: String(p.shares), tip: 'Copy number of shares' },
  ];
  return (
    <article className={`sheet over ${slotBg(p.slot)} ${s.pick}`}>
      <div className={s.pickHead}>
        <div className={s.ticker}>
          <span className={s.sym}>{p.symbol}</span>
          <span className={s.company}>{p.company}</span>
        </div>
        <span className={s.slot}>{slotLetter(p.slot)}</span>
      </div>
      <div className={s.lastRow}>
        <span className="chip num">Last {usd(p.last)}</span>
        <span className={`${s.bracket} mobile-only`}>Bracket order, exits by day 5</span>
      </div>
      <div className={s.fields}>
        {fields.map(f => (
          <div key={f.label} className={s.field}>
            <span className={s.fieldLabel}>{f.label}</span>
            <div className={s.fieldRow}>
              <span className={`num ${s.fieldVal}`}><span className={s.unit}>{f.unit}</span><span className={s.value}>{f.value}</span></span>
              <CopyButton value={f.value} tip={f.tip} />
            </div>
          </div>
        ))}
      </div>
      <div className={s.est}>
        <div className={s.estItem}><span className={s.estLabel}>Est. cost</span><span className={s.estVals}><span className={s.estUsd}>{usd(cost)}</span><span className={s.estIdr}>{rp(cost, rate)}</span></span></div>
        <div className={`${s.estItem} pos`}><span className={s.estLabel}>Est. profit</span><span className={s.estVals}><span className={s.estUsd}>{signedUsd(profit)}</span><span className={s.estIdr}>{signedRp(profit, rate)}</span></span></div>
        <div className={`${s.estItem} neg`}><span className={s.estLabel}>Est. loss</span><span className={s.estVals}><span className={s.estUsd}>{signedUsd(-loss)}</span><span className={s.estIdr}>{signedRp(-loss, rate)}</span></span></div>
      </div>
      <WhyToggle text={p.explanation} />
    </article>
  );
}
```
**Impact:** with the roster's SPY champion Today makes no `picks`/`positions` queries and renders the
no-buys sheet; a stale or failed bars run still shows the alarm first. The bracket path is unchanged for
a future bracket champion. The day-5 action filter keeps phase 10 Step 10's `Holding` guard
(`orderId !== null && maxDays !== null`), and `key`/`orderId` replace the old `id`.

### Step 5: Today CSS — sub line of the no-buys sheet
**File:** `web/app/(app)/today.module.css:26` (insert after the `.none` rule, which ends on line 26)
**Code:**
```css
.noneSub {
  margin-top: auto; padding-top: 28px; max-width: 34ch;
  font-size: 16px; line-height: 1.45; letter-spacing: 0; color: var(--ink-2); text-wrap: pretty;
}
```
**Impact:** `.none` keeps `min-height: 540px` and the design's 56px two-line type; the sub line sits at
the bottom of the sheet. Desktop rule `.alarm, .none { border-radius: 40px; }` already covers it.

### Step 6: Positions — switcher, paper/book/benchmark cards, paper orders, paper-step warning
**File:** `web/app/(app)/positions/page.tsx:1-85` (full replace)
**Change:** The page reads the roster, selects `?s=` (default: first research strategy), and renders by
`Holding.kind` (phase 10). Research cards and the orders sheet carry `PaperChip`. Paper orders come from
phase 10's `pendingOrders(id)` (`Pending.sessionDate`, `.decision`, `.orders: PendingOrder[]`) and show no
copy buttons: they are not something to place in a broker. The warning sheet appears whenever the most
recent run's `paperStatus` (phase 10 `RunStatus`) is not `success`. This replaces phase 10 Step 10's
stop-gap lines in this file (the file is quoted as phase 10 left it; the whole file is replaced).
**Code:**
```tsx
import { Crown, Landmark, TriangleAlert } from 'lucide-react';
import { AppHeader } from '@/components/AppHeader';
import { PaperChip } from '@/components/PaperChip';
import { selectStrategy, sharesLabel, strategyIcon } from '@/components/roster';
import { StrategySwitch } from '@/components/StrategySwitch';
import { WhyToggle } from '@/components/WhyToggle';
import {
  pendingOrders, positions as getPositions, runStatus, strategies,
  type Holding, type Pending, type PendingOrder, type RunStatus, type Strategy,
} from '@/lib/data';
import { pct, shortDate, signedPct, signedRp, signedUsd, usd } from '@/lib/format';
import { wibDate } from '@/lib/session';
import { cardBg } from '@/lib/slots';
import s from './positions.module.css';

export const dynamic = 'force-dynamic';

type Search = { s?: string };

const NO_PENDING: Pending = { sessionDate: null, decision: false, orders: [] };

export default async function Positions({ searchParams }: { searchParams: Promise<Search> }) {
  const now = new Date();
  const q = await searchParams;
  const [roster, run] = await Promise.all([strategies(), runStatus(now)]);
  const strat = selectStrategy(roster, q.s);
  // Paper orders exist for research strategies only; hidden while the data is stale.
  const showOrders = !!strat && !strat.isBenchmark && !run.stale;
  const [open, pending] = await Promise.all([
    strat ? getPositions(strat.id) : Promise.resolve([] as Holding[]),
    showOrders && strat ? pendingOrders(strat.id) : Promise.resolve(NO_PENDING),
  ]);

  const bracket = open.filter(p => p.kind === 'bracket');
  const book = open.filter(p => p.kind !== 'bracket');
  const pnl = open.reduce((a, p) => a + p.pnl, 0);
  const exitsToday = bracket.filter(p => p.maxDays !== null && p.day >= p.maxDays).length + book.filter(p => p.exitPending).length;
  const invested = book.reduce((a, p) => a + (p.weight ?? 0), 0);
  const holdsBook = strat?.engine === 'book' || strat?.engine === 'benchmark';
  const paper = !!strat && strat.isPaper;
  const paperWarn = !!run.sessionDate && run.paperStatus !== 'success';
  const StratIcon = strat ? strategyIcon(strat.icon) : Landmark;
  const href = (id: string) => `/positions?s=${encodeURIComponent(id)}`;
  const [noneTitle, noneSub] = emptyState(strat);
  const orderSession = showOrders ? pending.sessionDate : null;

  return (
    <>
      <AppHeader date={shortDate(wibDate(now))} title="Positions" demo={run.isDemo} />
      <div className="stack">
        <section className={`sheet bg-sheet ${s.summary}`}>
          <div className={s.between}>
            <span className="eyebrow">Unrealized P/L</span>
            <span className="pill-outline">
              {strat?.isChampion ? <Crown size={15} /> : <StratIcon size={15} />}
              {strat?.name ?? '—'}
            </span>
          </div>
          {strat && <StrategySwitch strategies={roster} current={strat.id} href={href} label="Strategy" />}
          <div className={s.stats}>
            <div className={`${s.stat} ${pnl < 0 ? 'neg' : 'pos'}`}>
              <span className={`num ${s.big}`}>{signedUsd(pnl)}</span>
              <span className={s.sub}>{signedRp(pnl, run.usdIdr)}</span>
            </div>
            <div className={s.stat}><span className={s.mid}>{open.length}</span><span className={s.sub}>Open</span></div>
            {holdsBook ? (
              <div className={s.stat}><span className={`num ${s.mid}`}>{pct(invested, 0)}</span><span className={s.sub}>Invested</span></div>
            ) : (
              <div className={s.stat}><span className={s.mid}>{exitsToday}</span><span className={s.sub}>Exits today</span></div>
            )}
          </div>
          {paper && strat && (
            <div className={s.paperLine}><PaperChip /><span>{paperNote(strat)}</span></div>
          )}
        </section>

        {paperWarn && run.sessionDate && (
          <section className={`sheet over bg-coral ${s.warn}`} role="status">
            <div className={s.warnHead}>
              <span className={s.warnIcon} aria-hidden="true"><TriangleAlert size={22} /></span>
              <span className="eyebrow">Paper step</span>
            </div>
            <span className={s.warnText}>{paperWarning(run.paperStatus, run.sessionDate)}</span>
          </section>
        )}

        {open.length === 0 ? (
          <section className={`sheet over bg-stone ${s.none}`}>
            <span>{noneTitle}</span>
            {noneSub && <span className={s.noneSub}>{noneSub}</span>}
          </section>
        ) : (
          <div className={s.grid}>
            {bracket.map((p, i) => <BracketCard key={p.key} q={p} bg={cardBg(p.slot, i)} paper={paper} />)}
            {book.map((p, i) => p.kind === 'benchmark'
              ? <BenchmarkCard key={p.key} q={p} />
              : <BookCard key={p.key} q={p} bg={cardBg(null, bracket.length + i)} paper={paper} />)}
          </div>
        )}

        {strat && orderSession && (
          <section className={`sheet over bg-sheet ${s.orders}`}>
            <div className={s.between}>
              <span className="eyebrow">Paper orders for {shortDate(orderSession)}</span>
              {paper && <PaperChip />}
            </div>
            {pending.orders.some(o => o.kind === 'book') && <span className={s.ordersSub}>Target portfolio after the open, by rank</span>}
            {pending.orders.length === 0 ? (
              <span className={s.ordersNone}>{noOrders(strat, pending)}</span>
            ) : (
              <ul className={s.orderList}>
                {pending.orders.map(o => <OrderRow key={o.key} o={o} />)}
              </ul>
            )}
          </section>
        )}
        <div className="nav-clear" />
      </div>
    </>
  );
}

function paperNote(st: Strategy): string {
  const since = st.paperStart ? `On paper since ${shortDate(st.paperStart)}.` : 'Paper trading starts with the next nightly run.';
  return `${since} Simulated orders, no real money.`;
}

function paperWarning(status: RunStatus['paperStatus'], session: string): string {
  const day = shortDate(session);
  if (status === 'failed') return `Paper trading failed for ${day}. Paper positions and orders are from the night before.`;
  if (status === 'running') return `Paper trading for ${day} is still running. Paper positions may be a night old.`;
  return `Paper trading has not run for ${day} yet. Paper positions may be a night old.`;
}

function emptyState(st: Strategy | null): [string, string | null] {
  if (!st) return ['No strategies yet.', null];
  if (st.engine === 'benchmark') return ['Not bought yet.', `${st.name} is bought at the open of the first paper session.`];
  if (st.engine === 'book') return ['In cash.', `${st.short} decides on the first session of each month.`];
  return ['No open positions.', null];
}

function noOrders(st: Strategy, p: Pending): string {
  if (st.engine === 'book') {
    return p.decision
      ? `No orders. ${st.short} decided to hold cash.`
      : `No orders. ${st.short} decides on the first session of each month.`;
  }
  return 'No setups tonight. Cash is a position.';
}

function Change({ pnl, ratio }: { pnl: number; ratio: number | null }) {
  return (
    <div className={`${s.change} ${pnl < 0 ? 'neg' : 'pos'}`}>
      <span className={`num ${s.pct}`}>{ratio === null ? '—' : signedPct(ratio)}</span>
      <span className="num">{signedUsd(pnl)}</span>
    </div>
  );
}

function Range({ stop, target, entry, current }: { stop: number; target: number; entry: number; current: number }) {
  const span = target - stop;
  const at = (v: number) => (span > 0 ? Math.min(100, Math.max(0, ((v - stop) / span) * 100)) : 50);
  const e = at(entry), c = at(current), up = current >= entry;
  return (
    <div className={s.range}>
      <div className={`num ${s.between} ${s.rangeLabels}`}><span>Stop {usd(stop)}</span><span>Target {usd(target)}</span></div>
      <div className={s.track} role="img" aria-label={`Price is ${Math.round(c)}% of the way from stop to target`}>
        <div className={s.fill} style={{ left: `${Math.min(e, c)}%`, width: `${Math.abs(c - e)}%`, background: up ? 'var(--pos)' : 'var(--neg)' }} />
        <div className={s.entry} style={{ left: `${e}%` }} />
        <div className={s.cur} style={{ left: `${c}%` }} />
      </div>
    </div>
  );
}

function Weight({ weight, label }: { weight: number | null; label: string }) {
  if (weight === null) return null;
  const w = Math.min(1, Math.max(0, weight));
  return (
    <div className={s.weight}>
      <div className={`num ${s.between} ${s.rangeLabels}`}><span>{pct(w, 1)} {label}</span></div>
      <div className={s.track} role="img" aria-label={`${pct(w, 1)} ${label}`}>
        <div className={s.weightFill} style={{ width: `${w * 100}%` }} />
      </div>
    </div>
  );
}

function StopTarget({ q }: { q: Holding }) {
  if (q.sl !== null && q.tp !== null) return <Range stop={q.sl} target={q.tp} entry={q.entry} current={q.current} />;
  if (q.sl === null && q.tp === null) return null;
  return (
    <div className={s.chips}>
      {q.sl !== null && <span className="chip num">Stop {usd(q.sl)}</span>}
      {q.tp !== null && <span className="chip num">Target {usd(q.tp)}</span>}
    </div>
  );
}

function BracketCard({ q, bg, paper }: { q: Holding; bg: string; paper: boolean }) {
  const max = q.maxDays ?? 5;
  return (
    <article className={`sheet over ${bg} ${s.card}`}>
      <div className={s.head}>
        <div className={s.ticker}>
          <span className={s.sym}>{q.symbol}</span>
          <span className={s.company}>{q.company ? `${q.company} · ` : ''}{sharesLabel(q.shares)}</span>
        </div>
        <Change pnl={q.pnl} ratio={q.pnlPct} />
      </div>
      <div className={s.chips}>
        {paper && <PaperChip />}
        <span className="chip num">Entry {usd(q.entry)}</span>
        <span className={`chip num ${s.now}`}>Now {usd(q.current)}</span>
      </div>
      <StopTarget q={q} />
      <div className={s.between}>
        <div className={s.days} aria-hidden="true">
          {Array.from({ length: max }, (_, k) => k + 1).map(k => <span key={k} className={k <= q.day ? s.dayOn : s.dayOff} />)}
        </div>
        <span className={s.dayLabel}>{q.day >= max ? `Day ${q.day}/${max} · exit today` : `Day ${q.day}/${max}`}</span>
      </div>
    </article>
  );
}

function BookCard({ q, bg, paper }: { q: Holding; bg: string; paper: boolean }) {
  return (
    <article className={`sheet over ${bg} ${s.card}`}>
      <div className={s.head}>
        <div className={s.ticker}>
          <span className={s.sym}>{q.symbol}</span>
          <span className={s.company}>{q.company ? `${q.company} · ` : ''}{sharesLabel(q.shares)}</span>
        </div>
        <Change pnl={q.pnl} ratio={q.pnlPct} />
      </div>
      <div className={s.chips}>
        {paper && <PaperChip />}
        <span className="chip num">Entry {usd(q.entry)}</span>
        <span className={`chip num ${s.now}`}>Now {usd(q.current)}</span>
      </div>
      <StopTarget q={q} />
      <Weight weight={q.weight} label="of paper equity" />
      <div className={s.between}>
        <span className={s.held}>{q.exitPending ? 'Sells at the next open' : 'Held until the rules say sell'}</span>
        <span className={s.dayLabel}>{q.day === 1 ? 'Day 1' : `${q.day} days held`}</span>
      </div>
    </article>
  );
}

function BenchmarkCard({ q }: { q: Holding }) {
  return (
    <article className={`sheet over bg-stone ${s.card}`}>
      <div className={s.head}>
        <div className={s.ticker}>
          <span className={s.sym}>{q.symbol}</span>
          <span className={s.company}>{q.company ? `${q.company} · ` : ''}{sharesLabel(q.shares)}</span>
        </div>
        <Change pnl={q.pnl} ratio={q.pnlPct} />
      </div>
      <div className={s.chips}>
        <span className={`chip ${s.benchChip}`} data-tip="The yardstick every paper strategy is measured against">
          <Landmark size={15} aria-hidden="true" />Benchmark
        </span>
        <span className="chip num">Entry {usd(q.entry)}</span>
        <span className={`chip num ${s.now}`}>Now {usd(q.current)}</span>
      </div>
      <Weight weight={q.weight} label="invested" />
      <div className={s.between}>
        <span className={s.held}>Buy and hold, dividends reinvested</span>
        <span className={s.dayLabel}>{q.day === 1 ? 'Day 1' : `${q.day} days held`}</span>
      </div>
    </article>
  );
}

function OrderRow({ o }: { o: PendingOrder }) {
  const cells: [string, string][] = o.kind === 'bracket'
    ? [
        ['Limit', o.limit === null ? '—' : usd(o.limit)],
        ['Target', o.tp === null ? '—' : usd(o.tp)],
        ['Stop', o.sl === null ? '—' : usd(o.sl)],
        ['Shares', o.shares === null ? '—' : String(o.shares)],
      ]
    : [
        ['Weight', o.weight === null ? '—' : pct(o.weight, 1)],
        ['Limit', o.limit === null ? 'Open' : usd(o.limit)],
        ['Stop', o.sl === null ? '—' : usd(o.sl)],
        ['Target', o.tp === null ? '—' : usd(o.tp)],
      ];
  return (
    <li className={s.order}>
      <div className={s.orderHead}>
        {o.kind === 'book' && <span className={s.rank}>{o.rank}</span>}
        <span className={s.orderSym}>{o.symbol}</span>
        <span className={s.orderCo}>{o.company ? `${o.company} · ` : ''}last {usd(o.last)}</span>
      </div>
      <OrderCells cells={cells} />
      <WhyToggle text={o.explanation} />
    </li>
  );
}

function OrderCells({ cells }: { cells: [string, string][] }) {
  return (
    <dl className={s.cells}>
      {cells.map(([k, v]) => (
        <div key={k} className={s.cell}><dt>{k}</dt><dd className="num">{v}</dd></div>
      ))}
    </dl>
  );
}
```
**Impact:** `/positions` defaults to strategy A (first research row by `sort`), not the champion.
`/positions?s=SPY` shows the benchmark holding. Card colours come from phase 10's `cardBg(slot, index)`
(a bracket card keeps its slot's sheet; a book card cycles by place), and the day dots come from
`Holding.maxDays`, so book strategies get no slot semantics. The only controls are the switcher links and WhyToggle buttons, all
icon-only with `aria-label` + `data-tip`.

### Step 7: Positions CSS
**File:** `web/app/(app)/positions/positions.module.css:1-42` (full replace)
**Code:**
```css
.between { display: flex; align-items: center; justify-content: space-between; gap: 12px; }

/* ---- Summary ---- */
.summary { padding-bottom: 64px; gap: 20px; }
.stats { display: flex; align-items: flex-end; gap: 28px; }
.stat { display: flex; flex-direction: column; gap: 2px; }
.big { font-size: 52px; line-height: 0.95; letter-spacing: -0.04em; }
.mid { font-size: 26px; letter-spacing: -0.02em; }
.sub { font-size: 15px; }
.paperLine { display: flex; align-items: center; gap: 12px; font-size: 15px; line-height: 1.35; color: var(--ink-2); text-wrap: pretty; }

/* ---- Paper step warning ---- */
.warn { padding: 26px 22px 66px 24px; gap: 12px; }
.warnHead { display: flex; align-items: center; gap: 12px; }
.warnIcon {
  flex: none; width: 44px; height: 44px; border-radius: 999px; border: 1px solid #1d1c1a;
  display: flex; align-items: center; justify-content: center;
}
.warnText { font-size: 21px; line-height: 1.25; letter-spacing: -0.01em; text-wrap: pretty; }

/* ---- Empty ---- */
.none { padding: 44px 26px 160px; gap: 10px; font-size: 40px; letter-spacing: -0.04em; }
.noneSub { font-size: 16px; line-height: 1.45; letter-spacing: 0; color: var(--ink-2); text-wrap: pretty; }

/* ---- Cards ---- */
.grid { display: contents; }
.card { gap: 18px; }
.head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.ticker { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.sym { font-size: 36px; line-height: 1; letter-spacing: -0.03em; font-weight: 500; }
.company { font-size: 16px; color: var(--ink-2); }
.change { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; font-size: 15px; }
.pct { font-size: 28px; letter-spacing: -0.03em; }
.chips { display: flex; gap: 10px; flex-wrap: wrap; }
.now { background: var(--chip-solid); font-weight: 500; }
.benchChip { background: var(--ink); color: var(--sheet); }

.range, .weight { display: flex; flex-direction: column; gap: 10px; }
.rangeLabels { font-size: 15px; }
.track { position: relative; height: 6px; border-radius: 999px; background: var(--hair); }
.fill { position: absolute; top: 0; bottom: 0; border-radius: 999px; }
.weightFill { position: absolute; top: 0; bottom: 0; left: 0; border-radius: 999px; background: var(--ink); }
.entry { position: absolute; top: -6px; bottom: -6px; width: 2px; margin-left: -1px; border-radius: 2px; background: var(--ink-2); }
.cur {
  position: absolute; top: 50%; width: 20px; height: 20px; margin: -10px 0 0 -10px;
  border-radius: 999px; background: var(--ink); border: 4px solid var(--chip-solid);
}

.days { display: flex; align-items: flex-end; gap: 6px; height: 30px; }
.dayOn, .dayOff { width: 5px; border-radius: 999px; background: var(--ink); }
.dayOn { height: 28px; }
.dayOff { height: 5px; }
.dayLabel { font-size: 17px; font-weight: 500; white-space: nowrap; }
.held { font-size: 15px; color: var(--ink-2); text-wrap: pretty; }

/* ---- Paper orders ---- */
.orders { gap: 14px; }
.ordersSub { margin-top: -6px; font-size: 15px; color: var(--ink-2); }
.ordersNone { font-size: 21px; line-height: 1.3; letter-spacing: -0.01em; color: var(--ink-2); text-wrap: pretty; }
.orderList { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.order { display: flex; flex-direction: column; gap: 12px; padding: 16px 0; border-top: 1px solid var(--hair); }
.orderHead { display: flex; align-items: center; gap: 10px; min-width: 0; }
.rank {
  flex: none; width: 36px; height: 36px; border-radius: 999px; border: 1.5px dashed var(--outline);
  display: flex; align-items: center; justify-content: center; font-size: 15px; color: var(--ink-2);
}
.orderSym { flex: none; font-size: 24px; font-weight: 500; letter-spacing: -0.02em; }
.orderCo { flex: 1; min-width: 0; font-size: 15px; color: var(--ink-2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cells { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin: 0; }
.cell { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.cell dt { font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink-2); }
.cell dd { margin: 0; font-size: 18px; letter-spacing: -0.01em; white-space: nowrap; }

@media (min-width: 1024px) {
  .summary { border-radius: 40px; }
  .warn { margin-top: 12px; border-radius: 40px; padding: 22px 30px; }
  .grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 12px; align-items: start; }
  .card { border-radius: 32px; padding: 22px; }
  .none { margin-top: 12px; border-radius: 40px; }
  .orders { margin-top: 12px; border-radius: 40px; padding: 28px 30px; }
  .orderList { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 40px; }
}
```
**Impact:** existing card styles kept (same class names and values); the inline `Now` chip style becomes
`.now`. Light/dark come from the existing tokens only.

### Step 8: History — roster filters, new exit reasons, Paper tag
**File:** `web/app/(app)/history/page.tsx:1-103` (full replace)
**Change:** The strategy filter is `StrategySwitch` over the roster's research strategies (SPY never closes
a trade) with an "All strategies" button; the outcome filter keeps its local links. `REASON` gains
`signal` and `forced`. Rows show the strategy's short name (`Trade.strategyShort`) and icon from the roster
plus `PaperChip` for paper strategies (`Strategy.isPaper`). Rows are keyed by phase 10's `Trade.key`
(unique across `orders` and `book_trades`). The file is quoted as phase 10 left it (unchanged there).
**Code:**
```tsx
import {
  ArrowRightLeft, CircleDashed, CircleSlash, Hourglass, List, OctagonX, SkipForward, Target, TrendingDown, TrendingUp,
  type LucideIcon,
} from 'lucide-react';
import Link from 'next/link';
import { AppHeader } from '@/components/AppHeader';
import { PaperChip } from '@/components/PaperChip';
import { strategyIcon } from '@/components/roster';
import { ALL, StrategySwitch } from '@/components/StrategySwitch';
import { closedTrades, runStatus, strategies } from '@/lib/data';
import { monthDay, money, shortDate, signedPct, signedUsd } from '@/lib/format';
import { wibDate } from '@/lib/session';
import s from './history.module.css';

export const dynamic = 'force-dynamic';

// [icon, tooltip, legend label]
const REASON: Record<string, [LucideIcon, string, string]> = {
  tp: [Target, 'Take profit hit', 'Take profit'],
  sl: [OctagonX, 'Stop loss hit', 'Stop loss'],
  time: [Hourglass, 'Time exit, day 5', 'Day 5'],
  gap: [SkipForward, 'Gapped past stop at open', 'Gap'],
  signal: [ArrowRightLeft, 'Rules said sell, sold at the open', 'Signal'],
  forced: [CircleSlash, 'Forced close, no more prices', 'Forced'],
};
const UNKNOWN_REASON: [LucideIcon, string, string] = [CircleDashed, 'Closed', 'Closed'];
const OUT_BTNS: [string, LucideIcon, string][] = [['all', List, 'Wins and losses'], ['win', TrendingUp, 'Wins only'], ['loss', TrendingDown, 'Losses only']];

type Search = { s?: string; o?: string };

export default async function History({ searchParams }: { searchParams: Promise<Search> }) {
  const now = new Date();
  const q = await searchParams;
  const roster = await strategies();
  const research = roster.filter(r => !r.isBenchmark);
  const strat = q.s && research.some(r => r.id === q.s) ? q.s : ALL;
  const outcome = q.o === 'win' || q.o === 'loss' ? q.o : 'all';
  const [run, rows] = await Promise.all([
    runStatus(now),
    closedTrades(strat === ALL ? null : strat, outcome === 'all' ? null : outcome),
  ]);
  const byId = new Map(roster.map(r => [r.id, r]));
  const net = rows.reduce((a, r) => a + r.pnl, 0);
  const wins = rows.filter(r => r.pnl > 0).length;

  const href = (next: Search) => {
    const p = new URLSearchParams();
    const sv = next.s ?? strat, ov = next.o ?? outcome;
    if (sv !== ALL) p.set('s', sv);
    if (ov !== 'all') p.set('o', ov);
    const qs = p.toString();
    return qs ? `/history?${qs}` : '/history';
  };

  return (
    <>
      <AppHeader date={shortDate(wibDate(now))} title="History" demo={run.isDemo} />
      <div className="stack">
        <section className={`sheet bg-sheet ${s.summary}`}>
          <div className={s.filters}>
            <StrategySwitch strategies={research} current={strat} href={id => href({ s: id })}
              label="Strategy filter" allTip="All strategies" />
            <div className={s.group} role="group" aria-label="Outcome filter">
              {OUT_BTNS.map(([v, Icon, tip]) => (
                <Link key={v} href={href({ o: v })} replace scroll={false} className="icon-btn md"
                  data-tip={tip} aria-label={tip} aria-current={outcome === v ? 'true' : undefined}>
                  <Icon size={19} strokeWidth={outcome === v ? 2 : 1.5} />
                </Link>
              ))}
            </div>
          </div>
          <div className={s.stats}>
            <div className={s.stat}><span className={`num ${s.big} ${net < 0 ? 'neg' : 'pos'}`}>{signedUsd(net)}</span><span className={s.sub}>Net result</span></div>
            <div className={s.stat}><span className={`num ${s.mid}`}>{wins}</span><span className={s.sub}>Won</span></div>
            <div className={s.stat}><span className={`num ${s.mid}`}>{rows.length - wins}</span><span className={s.sub}>Lost</span></div>
          </div>
          <div className={s.key}>
            {Object.entries(REASON).map(([k, [Icon, , label]]) => (
              <span key={k}><Icon size={15} />{label}</span>
            ))}
          </div>
        </section>

        <section className={`sheet over bg-stone ${s.list}`}>
          {rows.length === 0 && <div className={s.none}>No trades match these filters.</div>}
          {rows.map(r => {
            const [RIcon, rTip] = REASON[r.reason] ?? UNKNOWN_REASON;
            const st = byId.get(r.strategyId);
            const SIcon = strategyIcon(st?.icon ?? '');
            const win = r.pnl > 0;
            return (
              <div key={r.key} className={s.row}>
                <span className={s.reason} data-tip={rTip} aria-label={rTip}><RIcon size={19} strokeWidth={1.6} /></span>
                <div className={s.main}>
                  <span className={s.line1}>
                    <span className={s.sym}>{r.symbol}</span>
                    <span className={s.tag} data-tip={st?.name ?? r.strategyId}><SIcon size={12} />{r.strategyShort}</span>
                    {(!st || st.isPaper) && <PaperChip size="sm" />}
                  </span>
                  <span className={`num ${s.line2}`}>{money(r.entry)} → {money(r.exit)} · {monthDay(r.exitDate)}</span>
                </div>
                <div className={`${s.result} ${win ? 'pos' : 'neg'}`}>
                  <span className={`num ${s.pct}`}>{signedPct(r.exit / r.entry - 1)}</span>
                  <span className="num">{signedUsd(r.pnl)}</span>
                </div>
              </div>
            );
          })}
        </section>
      </div>
    </>
  );
}
```
**Impact:** `?s=` is validated against the roster (B/C links from old bookmarks fall back to All). The
outcome links keep the design's existing markup, now wrapped in a labelled group.

### Step 9: History CSS
**File:** `web/app/(app)/history/history.module.css:1-42` (full replace)
**Change:** `.line1` gets `min-width: 0` and `.tag` gets `flex: none` so symbol + strategy tag + Paper
tag fit one line at 414 pt; everything else is unchanged.
**Code:**
```css
.summary { padding-bottom: 64px; gap: 20px; }
.filters { display: flex; justify-content: space-between; gap: 8px; }
.group { display: flex; gap: 6px; }
.stats { display: flex; align-items: flex-end; gap: 26px; }
.stat { display: flex; flex-direction: column; gap: 2px; }
.big { font-size: 52px; line-height: 0.95; letter-spacing: -0.04em; }
.mid { font-size: 26px; }
.sub { font-size: 15px; }
.key { display: flex; flex-wrap: wrap; gap: 8px 14px; font-size: 14px; color: var(--ink-2); }
.key span { display: flex; align-items: center; gap: 5px; }

.list { padding: 16px 22px var(--nav-clear); gap: 0; flex: 1; }
.none { padding: 32px 0; text-align: center; font-size: 17px; color: var(--ink-2); }
.row { display: flex; align-items: center; gap: 14px; padding: 14px 0; border-bottom: 1px solid var(--hair); }
.reason {
  flex: none; width: 46px; height: 46px; border-radius: 999px; background: var(--chip-solid);
  display: flex; align-items: center; justify-content: center;
}
.main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.line1 { display: flex; align-items: center; gap: 8px; min-width: 0; }
.sym { font-size: 20px; font-weight: 500; letter-spacing: -0.01em; }
.tag {
  flex: none; height: 24px; padding: 0 9px; border-radius: 999px; background: var(--chip);
  display: flex; align-items: center; gap: 4px; font-size: 12px;
}
.line2 { font-size: 14px; color: var(--ink-2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.result { display: flex; flex-direction: column; align-items: flex-end; gap: 1px; font-size: 13px; }
.pct { font-size: 19px; }

@media (min-width: 1024px) {
  .summary {
    border-radius: 40px; padding: 28px 30px; flex-direction: row; align-items: center;
    justify-content: space-between; flex-wrap: wrap; gap: 20px 32px;
  }
  .filters { order: 2; gap: 18px; }
  .key { order: 3; width: 100%; }
  .list {
    margin-top: 12px; border-radius: 40px; padding: 8px 30px 20px;
    display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 40px; align-content: start;
  }
  .none { grid-column: 1 / -1; }
}
```
**Impact:** filter row at 414 pt: 4 strategy buttons (All, A, F4, F1) + 3 outcome buttons = 7 × 46 pt +
gaps ≈ 352 pt inside the 366 pt sheet; `StrategySwitch` wraps if a longer roster ever lands.

## Verification

**Build:** `cd web && npm ci && npx tsc --noEmit`
**Tests:** `cd web && npx vitest run` (includes the new `components/roster.test.ts`); engine suite untouched
but invariant 1 still holds: `docker start seer-pg && PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q` (0 skipped).
**Manual check (not required for exit, needs a demo DB the owner chooses; never write to Neon from this phase):**
`cd web && npm run dev`, against a database seeded with phase 10's `npm run db:seed-demo`, at 414 × 896
(DevTools iPhone XS Max) and ≥ 1280 wide, light and dark (`prefers-color-scheme` emulation):
1. `/` — no slot dots, no pick cards, no "Action needed"; stone sheet "SPY buy-and-hold is the champion." / "Seer recommends no buys." and the paper sub line; crown pill "SPY · S&P 500, buy and hold". Set the demo run's `session_date` back a day (local DB only) → the black stale alarm replaces it.
2. `/positions` — A selected by default; switcher shows SPY, A, F4, F1 icons with tooltips; A's cards show the dashed Paper chip, stop/target range and 5 day dots; "Paper orders for <session>" lists A's pending orders with Why toggles and no copy buttons. `?s=F4-MOM12-N20-TREND` → book cards (fractional shares, weight bar, days held, stop/target only if set) or "In cash."; `?s=SPY` → black "Benchmark" chip card, no orders sheet. Set the demo run's `paper_status` to `failed` (local DB) → coral "Paper step" sheet.
3. `/history` — strategy buttons are All + roster research icons (no B/C); `signal` and `forced` rows show ArrowRightLeft / CircleSlash with tooltips; each row has the strategy short name tag and the small dashed Paper tag; filters keep each other's state.
**Exit criteria:** `npx tsc --noEmit` clean and `npx vitest run` green against phase 10's `web/lib`; no
file under `web/lib`, `web/app/(app)/leaderboard`, `engine` changed; every new control is an icon-only
Lucide `Link`/`button` with `aria-label` and `data-tip`; Today cannot render research picks (it only
queries `champion()` and only for a non-benchmark bracket champion).

## Handoffs

- **Phase 10 (R4, data, reconciled):** this phase codes against phase 10's real exports (Requires):
  `Holding` (`kind`, `key`, `orderId`, `maxDays`, nullable `tp`/`sl`/`weight`/`company`, `pnl`, `pnlPct`,
  `exitPending`), `pendingOrders()` → `Pending`/`PendingOrder`, `Trade.key`/`strategyShort`/`ExitReason`,
  `Strategy.engine/rulesId/paperStart/isPaper/short`, `RunStatus.paperStatus`, `cardBg`. Phase 10 Step 10's
  compile fixes to these three pages land first; this phase replaces the pages whole. The demo seed
  covers the manual-check states (A pending orders, F4/F1 positions and targets, the SPY holding,
  `signal`/`forced` book trades, run `paper_status = 'success'`).
- **Phase 12 (R4, leaderboard):** reuse `StrategySwitch` (`ALL`, `allTip` optional), `PaperChip`,
  `strategyIcon` and `selectStrategy` from `web/components/roster.ts` instead of its own `ICONS` map or
  selection helper; short labels come from phase 10's `Strategy.short`. `StrategySwitch` must be rendered
  from a server component.
- **Drive-by, not done:** `WhyToggle`'s label is "Why this pick" for paper orders too; a "Why this order"
  variant would need a prop on a component nobody owns in this set — left as is. `sharesLabel` lives in
  `components/roster.ts` because `web/lib/format.ts` is phase 10's; moving it into `format.ts` is a later
  cleanup.

## Rollback

`git revert` this phase's commit: it restores the three pages and two CSS modules and deletes
`web/components/{roster.ts,roster.test.ts,StrategySwitch.tsx,StrategySwitch.module.css,PaperChip.tsx,PaperChip.module.css}`.
If phase 12 already imports `StrategySwitch`/`PaperChip`/`roster`, revert phase 12 first. Phase 10's
`web/lib` stays, and the reverted pages are phase 10 Step 10's versions, which compile against it.
