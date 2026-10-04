> Adopted from `PAPER_TRADING_SHIP_PLAN.md` phase 12. Source: `.workflows/plan/paper-trading-ship/phase-12.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 12: Web: Leaderboard, monthly table, checklist

**Plan set:** `PAPER_TRADING_SHIP_PLAN.md`
**Analysis:** `20261004-082027-P4S7_code_analyzer.md`
**Satisfies:** R4 — the owner opens the Leaderboard and sees, month by month and next to SPY, how each paper strategy is doing, with an honest go-live checklist per strategy
**Depends on:** Phase 11 (and through it phase 10)
**Difficulty:** HARD
**Package:** `web/app/(app)/leaderboard`

---

## Goal

The Leaderboard is driven by the roster, not by hardcoded ids A/B/C. SPY wears the champion crown and stays the dotted benchmark line. The checklist has six rows (including "Backtest gate passed") for the research strategy picked with `StrategySwitch` (`?s=`), and the score line never says "Ready for real money" unless all six pass. A new "Month by month" sheet shows the same strategy's calendar months (Return, SPY, Trades, Worst drop), a since-start row and a partial-month marker. It renders at 414 pt and on desktop, in light and dark.

## Design decisions (made here, with reasons)

1. **Headline: the big figure stays the champion's.** The Seer v2 design (`docs/design/Seer v2.dc.html:233-235` mobile, `:448-449` desktop) puts the crown on the big figure and gives the second figure to the comparison. Today the champion is SPY (D2), so the big figure is SPY's return with the crown and "SPY, champion". The second figure becomes the best research strategy on paper ("Best · F4" on mobile, "F4 · Momentum, best on paper" on desktop). Giving the big figure to a research strategy would read as a recommendation and break D12. If a non-benchmark ever becomes champion, the second figure goes back to SPY, as in the design. It is one roster-driven branch, not a special case.
2. **Months newest first, with the since-start row on top.** The design has no month table. Its closest list, History, puts the summary first and orders rows newest first (`history/page.tsx`, `closedTrades … ORDER BY exit_date DESC`). The owner checks "how is this month going", so the current (partial) month comes right under the since-start total. The order is set in `view.ts` (`monthLines` sorts by month descending), so it does not depend on the order `monthly()` returns.
3. **One switcher drives both checklist and table.** `?s=` picks one research strategy. The switcher sits at the top of the checklist sheet, where filter buttons sit in History. The design's eyebrow there already names a strategy ("Go-live checklist · A"). On mobile the Month by month sheet comes directly after it, so the switcher sits right above both. SPY is not selectable, because every month row already shows it in the SPY column. An unknown or missing `?s=` falls back to the first research strategy in roster order.
4. **Roster-order colours from existing tokens only.** The benchmark gets `bg-sheet` and `var(--ink-3)` dotted (as in the design). Research strategies in roster order take the design's A/B/C pairs: (`bg-lav`, `var(--ink)`), (`bg-sky`, `var(--line-b)`), (`bg-stone`, `var(--line-c)`). A fourth one cycles the sheets and uses `var(--ink-2)`. All research lines are width 2 (the design's 2.75 emphasis belonged to the champion; SPY is the champion now and keeps its dotted style). A non-benchmark champion would get 2.75 again.
5. **Month by month sheet colour = the selected strategy's card sheet.** This ties the table to its card and chart line. Its neighbours on mobile are the butter checklist and the SPY card (`bg-sheet`), so it never blends into an adjacent sheet of the same colour while SPY sorts first (it does: `sort = 1`, C1).
6. **Desktop order:** chart | checklist, then the strategy cards, then Month by month (CSS `order`). This keeps the design's 1280×820 first viewport (`:429`). On mobile the DOM order is used: chart, checklist, months, cards.
7. **Partial marker = Lucide `CircleDashed` icon** with `role="img"`, `aria-label` and `data-tip` "Partial month". A key line under the table spells it out, the same way the History sheet keys its reason icons. It is not a button, so the icon-only button rule is untouched.
8. **Pure view logic lives in a new `leaderboard/view.ts`** with its own `view.test.ts`, both in this phase's directory. It holds only leaderboard-specific logic: the roster colouring, the best-research pick, the honest score line and the month formatting (over phase 10's `MonthlyTable`). Selection, icons and short labels are reused from phases 10 and 11, not redefined.
9. **Partial current month (reconciled):** the latest month is partial while the engine's next session (`runStatus().sessionDate`) is in it, per phase 10's `monthly(id, sessionDate)`; the page passes `run.sessionDate`, not the WIB calendar date.

## Interface Contract

**Deletes:** file-local constants `ICONS` (old map with `brain-circuit`/`gavel`), `CARD_BG`, `LINE` in `web/app/(app)/leaderboard/page.tsx:11-13` (not exported; nothing else references them).
**Renames:** none.
**Creates:**
- `web/app/(app)/leaderboard/view.ts` (leaderboard-specific helpers only): `CARD_BGS`, `LINES`, `LOOK_FALLBACK`, `type Look`, `type RosterIn`, `type Cell`, `type MonthLine`, `type Score`, `CHECKS`, `looks()`, `researchOf()`, `bestResearch()`, `scoreOf()`, `monthLabel()`, `monthLines(t: MonthlyTable)`, `sinceStartLine(t: MonthlyTable)`. No `shortName`/`selectStrategy`/icon map: those are phase 10's `Strategy.short` and phase 11's `components/roster.ts`.
- `web/app/(app)/leaderboard/view.test.ts`
**Signature changes:** `Leaderboard()` → `Leaderboard({ searchParams }: { searchParams: Promise<{ s?: string }> })` (Next route component; reads `?s=`).

**Requires (from earlier phases).** Reconciled against phase 10's and phase 11's actual exports:

| # | Symbol | Shape this phase codes against | Used at |
|---|---|---|---|
| A1 | `Strategy` (`web/lib/data.ts`, phase 10) | `gate: { passed: boolean; note: string \| null }` (never null; `{ passed: false, note: null }` until `paper` writes C2), `short: string` (`'A'`, `'F4'`, `'F1'`, `'SPY'`), `isPaper`, `icon`, `isChampion`, `isBenchmark` | page.tsx |
| A2 | `leaderboard(): Promise<Board>` (phase 10) | `Board = { rows: { strategy; metrics; curve }[]; from; to }`, rows in `sort, id` order, `curve` incl. day 0 | page.tsx |
| A3 | `checklist(m, spyReturn, gate: Gate)` (`web/lib/metrics.ts`, phase 10) | 6 items, the 6th `Backtest gate passed` with optional `note` | page.tsx |
| A4 | `monthly(strategyId, sessionDate): Promise<MonthlyTable>` (`web/lib/data.ts`, phase 10) | `MonthlyTable = { months: MonthRow[] /* oldest first */; sinceStart: SinceStartRow \| null }`; `MonthRow = { month, from, to, return, spyReturn \| null, trades, worstDrop, partial }`; called with `run.sessionDate` | page.tsx, view.ts (type only) |
| A5 | `StrategySwitch` (phase 11) | `{ strategies: { id; name; icon }[]; current: string; href: (id) => string; label: string; allTip?: string }`; server component | page.tsx checklist sheet |
| A6 | `PaperChip`, `strategyIcon`, `selectStrategy` (phase 11, `web/components`) | `PaperChip({ size? })`; `strategyIcon(name) -> LucideIcon` (fallback `Sigma`); `selectStrategy(roster, requested)` | page.tsx |
| A7 | Demo seed (phase 10) | roster SPY/A/F4/F1, 66 sessions from one day 0, A/F4 trades, partial first and current months | manual check only |

**Leaves alone (owned by others):** `web/lib/*` (phase 10), `web/components/StrategySwitch.tsx`, `web/components/PaperChip.tsx` and the Today/Positions/History pages (phase 11), `web/app/globals.css`, everything under `engine/`, `db/`, workflows, docs.

## Files

| File | Action | What changes |
|---|---|---|
| `web/app/(app)/leaderboard/view.ts` | create | pure roster colouring, best research, score line, month-row formatting |
| `web/app/(app)/leaderboard/view.test.ts` | create | vitest coverage for every `view.ts` export |
| `web/app/(app)/leaderboard/page.tsx` | replace (lines 1–160) | roster-driven page, SPY-champion headline, `?s=` checklist with six rows, Month by month sheet, paper chips |
| `web/app/(app)/leaderboard/leaderboard.module.css` | replace (lines 1–82) | switcher row, gate note, month table, key, partial marker, desktop order, roster-sized card grid |

## Implementation Steps

### Step 1: Pure view helpers
**File:** `web/app/(app)/leaderboard/view.ts` (new)
**Change:** New module with leaderboard-specific helpers only. It uses relative imports so vitest (no config, no `@/` alias) can load it; at runtime it imports only `lib/format`, plus the `MonthlyTable` type from phase 10's `lib/monthly`. Selection is phase 11's `selectStrategy` and short labels are phase 10's `Strategy.short`, so neither is redefined here.
**Code:**
```ts
// Pure helpers for the Leaderboard: roster-driven looks, the best research strategy, the honest
// checklist line and the month-by-month rows. No data access; page.tsx feeds it.
// Selection (`selectStrategy`) and icons (`strategyIcon`) are phase 11's `components/roster.ts`;
// short labels are phase 10's `Strategy.short`; the month math is phase 10's `lib/monthly.ts`.
import { monthDay, monthName, pct, signedPct } from '../../../lib/format';
import type { MonthlyTable } from '../../../lib/monthly';

/** The roster fields these helpers read (a structural subset of lib/data's Strategy). */
export type RosterIn = { id: string; isChampion: boolean; isBenchmark: boolean };

/** Research strategies take the design's A/B/C sheet and line pairs in roster order. */
export const CARD_BGS = ['bg-lav', 'bg-sky', 'bg-stone'] as const;
export const LINES = ['var(--ink)', 'var(--line-b)', 'var(--line-c)'] as const;

export type Look = { bg: string; line: string; width: number; dotted: boolean };

export const LOOK_FALLBACK: Look = { bg: 'bg-sheet', line: 'var(--ink-2)', width: 2, dotted: false };

/** Card sheet and chart line per strategy id, by roster order. The benchmark is the dotted line on a plain sheet. */
export function looks(roster: RosterIn[]): Map<string, Look> {
  const out = new Map<string, Look>();
  let i = 0;
  for (const st of roster) {
    if (st.isBenchmark) {
      out.set(st.id, { bg: 'bg-sheet', line: 'var(--ink-3)', width: 1.75, dotted: true });
      continue;
    }
    out.set(st.id, {
      bg: CARD_BGS[i % CARD_BGS.length],
      line: i < LINES.length ? LINES[i] : 'var(--ink-2)',
      width: st.isChampion ? 2.75 : 2,
      dotted: false,
    });
    i += 1;
  }
  return out;
}

export const researchOf = <T extends RosterIn>(roster: T[]): T[] => roster.filter(st => !st.isBenchmark);

/** Highest total return among research strategies that have one. */
export function bestResearch<T extends RosterIn>(
  rows: { strategy: T; metrics: { totalReturn: number | null } }[],
): { strategy: T; ret: number } | null {
  let best: { strategy: T; ret: number } | null = null;
  for (const r of rows) {
    const v = r.metrics.totalReturn;
    if (r.strategy.isBenchmark || v === null) continue;
    if (best === null || v > best.ret) best = { strategy: r.strategy, ret: v };
  }
  return best;
}

/** Design §1's five rules plus "Backtest gate passed". */
export const CHECKS = 6;

export type Score = { passed: number; total: number; ready: boolean; lines: [string, string] };

/** The checklist score and its two-line verdict. Never "Ready for real money" unless all six pass. */
export function scoreOf(items: { ok: boolean }[], gatePassed: boolean): Score {
  const passed = items.filter(i => i.ok).length;
  const ready = items.length === CHECKS && passed === CHECKS;
  const lines: [string, string] = ready
    ? ['All six pass.', 'Ready for real money']
    : gatePassed
      ? ['Paper trading until', 'all six pass']
      : ['Paper only.', 'Backtest gate not passed'];
  return { passed, total: CHECKS, ready, lines };
}

export type Cell = { text: string; tone: '' | 'pos' | 'neg' };

export type MonthLine = {
  key: string;
  label: string;
  partial: boolean;
  ret: Cell;
  spy: string;
  trades: string;
  drop: string;
};

const toned = (v: number | null): Cell =>
  v === null ? { text: '—', tone: '' } : { text: signedPct(v, 1), tone: v < 0 ? 'neg' : 'pos' };
const plain = (v: number | null) => (v === null ? '—' : signedPct(v, 1));

/** '2026-10' -> 'Oct 2026' */
export const monthLabel = (ym: string) => `${monthName(`${ym}-01`)} ${ym.slice(0, 4)}`;

/** Month rows of phase 10's MonthlyTable, newest first (monthly() returns them oldest first). */
export function monthLines(t: MonthlyTable): MonthLine[] {
  return [...t.months]
    .sort((a, b) => b.month.localeCompare(a.month))
    .map(r => ({
      key: r.month,
      label: monthLabel(r.month),
      partial: r.partial,
      ret: toned(r.return),
      spy: plain(r.spyReturn),
      trades: String(r.trades),
      drop: pct(r.worstDrop, 1),
    }));
}

/** The since-start total row (from day 0); null before the first paper session. */
export function sinceStartLine(t: MonthlyTable): MonthLine | null {
  const ss = t.sinceStart;
  if (ss === null) return null;
  return {
    key: 'since-start',
    label: `Since ${monthDay(ss.from)}`,
    partial: false,
    ret: toned(ss.return),
    spy: plain(ss.spyReturn),
    trades: String(ss.trades),
    drop: pct(ss.worstDrop, 1),
  };
}
```
**Impact:** New file, nothing imports it yet. Next ignores non-special files under `app/`.

### Step 2: Tests for the view helpers
**File:** `web/app/(app)/leaderboard/view.test.ts` (new)
**Change:** vitest coverage. Roster fixtures use only `RosterIn` fields; the month fixture is phase 10's `MonthlyTable` shape.
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import type { MonthlyTable } from '../../../lib/monthly';
import {
  bestResearch, CHECKS, looks, monthLabel, monthLines, researchOf, scoreOf, sinceStartLine, type RosterIn,
} from './view';

const roster: RosterIn[] = [
  { id: 'SPY', isChampion: true, isBenchmark: true },
  { id: 'A', isChampion: false, isBenchmark: false },
  { id: 'F4-MOM12-N20-TREND', isChampion: false, isBenchmark: false },
  { id: 'F1-SPY-SMA200-M', isChampion: false, isBenchmark: false },
];
const RESEARCH = ['A', 'F4-MOM12-N20-TREND', 'F1-SPY-SMA200-M'];

describe('looks', () => {
  it('gives the benchmark the dotted line on a plain sheet', () => {
    expect(looks(roster).get('SPY')).toEqual({ bg: 'bg-sheet', line: 'var(--ink-3)', width: 1.75, dotted: true });
  });
  it('assigns research sheets and lines in roster order', () => {
    const l = looks(roster);
    expect(RESEARCH.map(id => l.get(id)!.bg)).toEqual(['bg-lav', 'bg-sky', 'bg-stone']);
    expect(RESEARCH.map(id => l.get(id)!.line)).toEqual(['var(--ink)', 'var(--line-b)', 'var(--line-c)']);
    expect(RESEARCH.map(id => l.get(id)!.width)).toEqual([2, 2, 2]);
  });
  it('follows roster order, not ids', () => {
    const l = looks([roster[3], roster[0], roster[1]]);
    expect(l.get('F1-SPY-SMA200-M')).toEqual({ bg: 'bg-lav', line: 'var(--ink)', width: 2, dotted: false });
    expect(l.get('A')).toEqual({ bg: 'bg-sky', line: 'var(--line-b)', width: 2, dotted: false });
  });
  it('cycles sheets and uses the spare line for a fourth research strategy', () => {
    const l = looks([...roster, { id: 'X9', isChampion: false, isBenchmark: false }]);
    expect(l.get('X9')).toEqual({ bg: 'bg-lav', line: 'var(--ink-2)', width: 2, dotted: false });
  });
  it('emphasises a non-benchmark champion', () => {
    const l = looks([{ ...roster[0], isChampion: false }, { ...roster[1], isChampion: true }]);
    expect(l.get('A')!.width).toBe(2.75);
  });
});

describe('researchOf', () => {
  it('lists research strategies only', () => {
    expect(researchOf(roster).map(s => s.id)).toEqual(RESEARCH);
  });
});

describe('bestResearch', () => {
  const row = (i: number, totalReturn: number | null) => ({ strategy: roster[i], metrics: { totalReturn } });
  it('ignores the benchmark and strategies without a return', () => {
    const b = bestResearch([row(0, 0.05), row(1, -0.01), row(2, 0.02), row(3, null)]);
    expect(b?.strategy.id).toBe('F4-MOM12-N20-TREND');
    expect(b?.ret).toBeCloseTo(0.02);
  });
  it('is null before any paper result', () => {
    expect(bestResearch([row(0, 0.01), row(1, null)])).toBeNull();
  });
});

describe('scoreOf', () => {
  const items = (oks: boolean[]) => oks.map(ok => ({ ok }));
  it('scores out of six and says paper only while the gate has not passed', () => {
    const sc = scoreOf(items([true, true, true, true, true, false]), false);
    expect(sc).toEqual({ passed: 5, total: CHECKS, ready: false, lines: ['Paper only.', 'Backtest gate not passed'] });
  });
  it('says paper trading until all six pass when only the gate has passed', () => {
    expect(scoreOf(items([false, false, true, true, true, true]), true).lines).toEqual(['Paper trading until', 'all six pass']);
  });
  it('is ready only when all six pass', () => {
    const sc = scoreOf(items([true, true, true, true, true, true]), true);
    expect(sc.ready).toBe(true);
    expect(sc.lines).toEqual(['All six pass.', 'Ready for real money']);
  });
  it('is never ready with fewer than six items', () => {
    expect(scoreOf(items([true, true, true, true, true]), true).ready).toBe(false);
  });
});

describe('month rows', () => {
  // Phase 10's MonthlyTable shape, oldest first as monthly() returns it.
  const t: MonthlyTable = {
    months: [
      { month: '2026-10', from: '2026-10-05', to: '2026-10-30', return: 0.012, spyReturn: 0.008, trades: 3, worstDrop: 0.021, partial: true },
      { month: '2026-11', from: '2026-10-30', to: '2026-11-30', return: -0.004, spyReturn: null, trades: 0, worstDrop: 0, partial: false },
      { month: '2026-12', from: '2026-11-30', to: '2026-12-02', return: 0, spyReturn: 0.01, trades: 0, worstDrop: 0.005, partial: true },
    ],
    sinceStart: { from: '2026-10-05', to: '2026-12-02', return: 0.008, spyReturn: 0.019, trades: 3, worstDrop: 0.03 },
  };
  it('labels months', () => {
    expect(monthLabel('2026-10')).toBe('Oct 2026');
  });
  it('orders newest first and formats every column', () => {
    const rows = monthLines(t);
    expect(rows.map(r => r.key)).toEqual(['2026-12', '2026-11', '2026-10']);
    expect(rows[1]).toEqual({
      key: '2026-11', label: 'Nov 2026', partial: false,
      ret: { text: '−0.4%', tone: 'neg' }, spy: '—', trades: '0', drop: '0.0%',
    });
    expect(rows[2]).toEqual({
      key: '2026-10', label: 'Oct 2026', partial: true,
      ret: { text: '+1.2%', tone: 'pos' }, spy: '+0.8%', trades: '3', drop: '2.1%',
    });
    expect(rows[0].partial).toBe(true);
  });
  it('builds the since-start row from day 0', () => {
    expect(sinceStartLine(t)).toEqual({
      key: 'since-start', label: 'Since Oct 5', partial: false,
      ret: { text: '+0.8%', tone: 'pos' }, spy: '+1.9%', trades: '3', drop: '3.0%',
    });
  });
  it('has no since-start row before the first paper session', () => {
    expect(sinceStartLine({ months: [], sinceStart: null })).toBeNull();
  });
});
```
**Impact:** Adds 16 vitest cases. It imports only a type from phase 10 (`MonthlyTable`), no runtime code.

### Step 3: Roster-driven Leaderboard page
**File:** `web/app/(app)/leaderboard/page.tsx:1-160` (whole file replaced)
**Change:**
- The file is quoted as phase 10 Step 10 left it (the `checklist(..., champ.strategy.gate)` and six-of-six stop-gaps); this step replaces it whole.
- The roster drives icons (phase 11's `strategyIcon`, fallback `Sigma`), sheets and lines.
- SPY gets the crown and the dotted line.
- Headline per Design decision 1.
- `?s=` selects the strategy with phase 11's `selectStrategy` over the research rows; phase 11's `StrategySwitch` (`href`, `label` props) sits in the checklist sheet.
- Month by month is phase 10's `monthly(id, run.sessionDate)` (async, `lib/data`), rendered newest first.
- Six-row checklist with the honest line and the gate note.
- New Month by month sheet.
- `PaperChip` on research cards and the months header.
- Legend labels use display names, never long ids. The old `st.id` short label would print `F4-MOM12-N20-TREND`.
- The forward-test period comes from the earliest paper snapshot (`board.from`).
**Code:**
```tsx
import { Check, CircleDashed, Crown, X } from 'lucide-react';
import type { CSSProperties } from 'react';
import { AppHeader } from '@/components/AppHeader';
import { PaperChip } from '@/components/PaperChip';
import { selectStrategy, strategyIcon } from '@/components/roster';
import { StrategySwitch } from '@/components/StrategySwitch';
import { leaderboard, monthly, runStatus, type Board } from '@/lib/data';
import { monthDay, monthName, shortDate, signedPct } from '@/lib/format';
import { checklist } from '@/lib/metrics';
import { wibDate } from '@/lib/session';
import {
  bestResearch, LOOK_FALLBACK, looks, monthLines, researchOf, scoreOf, sinceStartLine,
  type Look, type MonthLine,
} from './view';
import s from './leaderboard.module.css';

export const dynamic = 'force-dynamic';

const W = 340, H = 170;

type Search = { s?: string };

export default async function Leaderboard({ searchParams }: { searchParams: Promise<Search> }) {
  const now = new Date();
  const q = await searchParams;
  const [board, run] = await Promise.all([leaderboard(), runStatus(now)]);

  const roster = board.rows.map(r => r.strategy);
  const lookMap = looks(roster);
  const lookOf = (id: string): Look => lookMap.get(id) ?? LOOK_FALLBACK;
  const research = researchOf(roster);
  const champ = board.rows.find(r => r.strategy.isChampion);
  const spy = board.rows.find(r => r.strategy.isBenchmark);
  const spyRet = spy?.metrics.totalReturn ?? null;
  const best = bestResearch(board.rows);

  // Research only: SPY is in every month row's SPY column, so it is not selectable here.
  const pick = selectStrategy(research, q.s);
  const pickRow = pick ? board.rows.find(r => r.strategy.id === pick.id) : undefined;
  const gate = pickRow?.strategy.gate ?? null;
  const items = pickRow && gate ? checklist(pickRow.metrics, spyRet, gate) : [];
  const score = scoreOf(items, gate?.passed === true);
  // The latest month is partial while the engine's next session (runStatus().sessionDate) is in it.
  const table = pick ? await monthly(pick.id, run.sessionDate) : null;
  const since = table ? sinceStartLine(table) : null;
  const months = table ? monthLines(table) : [];

  // Forward test runs from the earliest paper snapshot (every roster entry starts the same day).
  const period = board.from && board.to ? `${monthDay(board.from)} – ${monthDay(board.to)}` : 'Not started';
  const chart = buildChart(board, lookOf);
  const ret = (v: number | null) => (v === null ? '—' : signedPct(v, 1));
  const tone = (v: number | null) => (v === null ? '' : v < 0 ? 'neg' : 'pos');
  const champRet = champ?.metrics.totalReturn ?? null;

  // Big figure = the champion (SPY today, D2). Second figure = the best research strategy on paper
  // while the champion is the benchmark; otherwise SPY, as in the design.
  const second = champ?.strategy.isBenchmark
    ? {
        value: best ? ret(best.ret) : '—',
        mobile: best ? `Best · ${best.strategy.short}` : 'Paper',
        desk: best ? `${best.strategy.name}, best on paper` : 'No paper results yet',
      }
    : { value: ret(spyRet), mobile: 'SPY', desk: 'SPY' };

  const chartSheet = (
    <section className={`sheet bg-sheet ${s.chartSheet}`}>
      <div className={`${s.between} ${s.pad} mobile-only`}>
        <span className="eyebrow">Forward test</span>
        <span className="pill-outline">{period}</span>
      </div>
      <div className={`${s.headline} ${s.pad}`}>
        <div className={s.stats}>
          <div className={s.stat}>
            <span className={`num ${s.big} ${tone(champRet)}`}>{ret(champRet)}</span>
            <span className={s.statLabel}>
              <Crown size={14} />
              <span>{champ?.strategy.name ?? 'No champion'}<span className="desk-only">, champion</span></span>
            </span>
          </div>
          <div className={s.stat}>
            <span className={`num ${s.mid}`}>{second.value}</span>
            <span className={s.statLabel}>
              <span className="mobile-only">{second.mobile}</span>
              <span className="desk-only">{second.desk}</span>
            </span>
          </div>
          <div className={`${s.stat} mobile-only`}>
            <span className={`num ${s.mid}`}>{champ?.curve.length ?? 0}</span>
            <span className={s.statLabel}>Sessions</span>
          </div>
        </div>
        <Legend rows={board.rows} lookOf={lookOf} className="desk-only" short />
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className={s.chart} role="img"
        aria-label="Equity curves of each strategy against SPY">
        {chart.grid.map(y => <line key={y} x1="0" x2={W} y1={y} y2={y} vectorEffect="non-scaling-stroke" stroke="var(--hair)" />)}
        <line x1="0" x2={W} y1={chart.zero} y2={chart.zero} vectorEffect="non-scaling-stroke" stroke="var(--outline)" strokeDasharray="3 3" />
        {chart.lines.map(l => (
          <path key={l.id} d={l.d} vectorEffect="non-scaling-stroke" fill="none" stroke={l.color} strokeWidth={l.width}
            strokeDasharray={l.dotted ? '1 4' : undefined} strokeLinecap="round" strokeLinejoin="round" />
        ))}
      </svg>
      <div className={`${s.axis} ${s.pad}`}>{chart.labels.map((l, i) => <span key={i}>{l}</span>)}</div>
      <Legend rows={board.rows} lookOf={lookOf} className={`${s.pad} mobile-only`} />
    </section>
  );

  const checklistSheet = (
    <section className={`sheet over bg-butter ${s.check}`}>
      {pick && research.length > 1 && (
        <div className={s.switch}>
          <StrategySwitch strategies={research} current={pick.id}
            href={id => `/leaderboard?s=${encodeURIComponent(id)}`} label="Strategy" />
        </div>
      )}
      <span className="eyebrow">Go-live checklist · {pick ? pick.short : '—'}</span>
      <div className={s.score}>
        <span className={`num ${s.scoreNum}`}>{score.passed}/{score.total}</span>
        <span className={s.scoreText}>{score.lines[0]}<br />{score.lines[1]}</span>
      </div>
      {items.map(c => (
        <div key={c.label} className={s.item}>
          {c.ok
            ? <span className={s.ok} role="img" aria-label="Passed"><Check size={18} strokeWidth={2.25} /></span>
            : <span className={s.no} role="img" aria-label="Not yet"><X size={18} strokeWidth={2.25} /></span>}
          <span className={s.itemLabel}>{c.label}</span>
          <span className={`chip num ${s.itemVal}`}>{c.val}</span>
        </div>
      ))}
      {gate?.note && <p className={s.note}>{gate.note}</p>}
    </section>
  );

  const monthsSheet = (
    <section className={`sheet over ${pick ? lookOf(pick.id).bg : 'bg-sheet'} ${s.months}`} aria-labelledby="months-title">
      <div className={s.between}>
        <h2 id="months-title" className="eyebrow">Month by month · {pick ? pick.short : '—'}</h2>
        {pick && <PaperChip />}
      </div>
      {pick && since ? (
        <table className={s.table}>
          <thead>
            <tr>
              <th scope="col">Month</th>
              <th scope="col">Return</th>
              <th scope="col">SPY</th>
              <th scope="col">Trades</th>
              <th scope="col">Worst drop</th>
            </tr>
          </thead>
          <tbody>
            <MonthRow line={since} total />
            {months.map(m => <MonthRow key={m.key} line={m} />)}
          </tbody>
        </table>
      ) : (
        <div className={s.none}>{pick ? 'No paper sessions yet.' : 'No paper strategy on the roster.'}</div>
      )}
      <div className={s.key}>
        <span><CircleDashed size={15} />Partial month</span>
        <span>One month is mostly luck</span>
      </div>
    </section>
  );

  return (
    <>
      <AppHeader date={shortDate(wibDate(now))} title="Leaderboard" demo={run.isDemo}
        deskAside={<span className="pill-outline" style={{ height: 52, fontSize: 16, color: 'var(--ink)' }}>Forward test · {period}</span>} />
      <div className="stack">
        <div className={s.top}>{chartSheet}{checklistSheet}</div>
        {monthsSheet}
        <div className={s.cards} style={{ '--cols': Math.min(Math.max(board.rows.length, 1), 4) } as CSSProperties}>
          {board.rows.map(({ strategy: st, metrics: m }) => {
            const Icon = strategyIcon(st.icon);
            const dash = (v: string) => (st.isBenchmark ? '—' : v);
            return (
              <article key={st.id} className={`sheet over ${lookOf(st.id).bg} ${s.card}`}>
                <div className={s.cardHead}>
                  <div className={s.cardName}>
                    <span className={s.name}>
                      {st.name}
                      {st.isChampion && <span data-tip="Champion" aria-label="Champion" role="img" className={s.crown}><Crown size={20} /></span>}
                      {!st.isBenchmark && <PaperChip />}
                    </span>
                    <span className={s.cardSub}>{st.sub}</span>
                  </div>
                  <span className={s.icon}><Icon size={22} strokeWidth={1.6} /></span>
                </div>
                <div className={s.metrics}>
                  <div className={s.metric}><span className={`num ${s.ret} ${tone(m.totalReturn)}`}>{ret(m.totalReturn)}</span><span className={s.mLabel}><span className="mobile-only">Return</span><span className="desk-only">Total return</span></span></div>
                  <div className={s.metric}><span className="num">{dash(m.winRate === null ? '—' : Math.round(m.winRate * 100) + '%')}</span><span className={s.mLabel}>Win rate</span></div>
                  <div className={s.metric}><span className="num">{dash(m.profitFactor === null ? '—' : m.profitFactor === Infinity ? '∞' : m.profitFactor.toFixed(2))}</span><span className={s.mLabel}><span className="mobile-only">Profit f.</span><span className="desk-only">Profit factor</span></span></div>
                  <div className={s.metric}><span className="num">{m.maxDrawdown === null ? '—' : (m.maxDrawdown * 100).toFixed(1) + '%'}</span><span className={s.mLabel}><span className="mobile-only">Max DD</span><span className="desk-only">Max drawdown</span></span></div>
                  <div className={s.metric}><span className="num">{dash(String(m.trades))}</span><span className={s.mLabel}>Trades</span></div>
                </div>
              </article>
            );
          })}
        </div>
        <div className="nav-clear" />
      </div>
    </>
  );
}

function MonthRow({ line, total }: { line: MonthLine; total?: boolean }) {
  return (
    <tr className={total ? s.total : undefined}>
      <th scope="row">
        <span className={s.monthLabel}>
          {line.label}
          {line.partial && (
            <span className={s.partial} role="img" aria-label="Partial month" data-tip="Partial month">
              <CircleDashed size={14} />
            </span>
          )}
        </span>
      </th>
      <td className={`num ${line.ret.tone}`}>{line.ret.text}</td>
      <td className="num">{line.spy}</td>
      <td className="num">{line.trades}</td>
      <td className="num">{line.drop}</td>
    </tr>
  );
}

function Legend({ rows, lookOf, className, short }: {
  rows: Board['rows']; lookOf: (id: string) => Look; className: string; short?: boolean;
}) {
  return (
    <div className={`${s.legend} ${className}`}>
      {rows.map(({ strategy: st }) => {
        const look = lookOf(st.id);
        return (
          <span key={st.id} className={s.legendItem}>
            {look.dotted
              ? <span className={s.swatchDot} />
              : <span className={s.swatch} style={{ background: look.line }} />}
            {short ? st.short : st.name}
          </span>
        );
      })}
    </div>
  );
}

function buildChart(board: Board, lookOf: (id: string) => Look) {
  const dates = [...new Set(board.rows.flatMap(r => r.curve.map(c => c.date)))].sort();
  const xi = new Map(dates.map((d, i) => [d, i]));
  const series = board.rows.filter(r => r.curve.length > 1).map(r => ({
    row: r,
    pts: r.curve.map(c => ({ x: xi.get(c.date)!, v: (c.equity / r.curve[0].equity - 1) * 100 })),
  }));
  const all = series.flatMap(sr => sr.pts.map(p => p.v)).concat(0);
  const lo = Math.min(...all), hi = Math.max(...all);
  const span = hi - lo || 1;
  const y = (v: number) => +(H - 10 - ((v - lo) / span) * (H - 24)).toFixed(1);
  const x = (i: number) => +((i / Math.max(1, dates.length - 1)) * W).toFixed(1);

  // Champion last so it draws on top.
  const ordered = [...series].sort((a, b) => Number(a.row.strategy.isChampion) - Number(b.row.strategy.isChampion));
  const lines = ordered.map(({ row, pts }) => {
    const look = lookOf(row.strategy.id);
    return {
      id: row.strategy.id,
      d: pts.map((p, i) => `${i ? 'L' : 'M'}${x(p.x)} ${y(p.v)}`).join(' '),
      color: look.line,
      width: look.width,
      dotted: look.dotted,
    };
  });

  const labels: string[] = [];
  if (dates.length) {
    labels.push(monthDay(dates[0]));
    const first = monthName(dates[0]), last = monthName(dates[dates.length - 1]);
    for (const m of [...new Set(dates.map(monthName))]) if (m !== first && m !== last) labels.push(m);
    if (dates.length > 1) labels.push(monthDay(dates[dates.length - 1]));
  }
  return { lines, labels, zero: y(0), grid: [y(hi), y((hi + lo) / 2)] };
}
```
**Impact:**
- The Leaderboard now needs `?s=` handling (Next 16 async `searchParams`, the same pattern as `history/page.tsx`).
- It imports phase 10's `monthly`/`checklist`/`Strategy.short`/`Strategy.gate` and phase 11's `StrategySwitch`/`PaperChip`/`strategyIcon`/`selectStrategy`, so it will not compile before those land (expected: depends on 11).
- `Crown`/check icons gain `role="img"` so their `aria-label` is announced.

### Step 4: Styles
**File:** `web/app/(app)/leaderboard/leaderboard.module.css:1-82` (whole file replaced)
**Change:**
- Keep every existing rule.
- Add `.switch`, `.note`, the month sheet (`.months`, `.table`, `.total`, `.monthLabel`, `.partial`, `.none`, `.key`).
- `.name` wraps (for the paper chip).
- Desktop card grid sized by `--cols`; desktop order puts the cards before Month by month.
- Existing tokens only.
**Code:**
```css
.between { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.pad { padding: 0 24px; }

.top { display: contents; }

.chartSheet { padding: 28px 0 64px; gap: 18px; }
.headline { display: flex; align-items: flex-end; justify-content: space-between; gap: 26px; }
.stats { display: flex; align-items: flex-end; gap: 26px; }
.stat { display: flex; flex-direction: column; gap: 2px; }
.big { font-size: 52px; line-height: 0.95; letter-spacing: -0.04em; }
.mid { font-size: 26px; letter-spacing: -0.02em; }
.statLabel { font-size: 15px; display: flex; align-items: center; gap: 5px; white-space: nowrap; }
.chart { width: 100%; height: 170px; display: block; overflow: visible; }
.axis { display: flex; justify-content: space-between; font-size: 13px; color: var(--ink-2); }
.legend { display: flex; flex-wrap: wrap; gap: 8px 18px; font-size: 14px; }
.legendItem { display: flex; align-items: center; gap: 7px; }
.swatch { width: 18px; height: 3px; border-radius: 9px; }
.swatchDot { width: 18px; height: 0; border-top: 2.5px dotted var(--ink-3); }

.check { padding-bottom: 64px; gap: 8px; }
.switch { display: flex; gap: 6px; padding-bottom: 8px; }
.score { display: flex; align-items: center; gap: 12px; padding-bottom: 8px; }
.scoreNum { font-size: 52px; line-height: 1; letter-spacing: -0.04em; }
.scoreText { font-size: 16px; line-height: 1.3; color: var(--ink-2); }
.item { display: flex; align-items: center; gap: 14px; padding: 6px 0; }
.ok, .no {
  flex: none; width: 40px; height: 40px; border-radius: 999px;
  display: flex; align-items: center; justify-content: center;
}
.ok { background: var(--ink); color: var(--sheet); }
.no { border: 1.5px solid var(--ink); }
.itemLabel { flex: 1; font-size: 17px; }
.itemVal { height: 32px; padding: 0 12px; font-size: 14px; }
.note { margin: 6px 0 0; font-size: 14px; line-height: 1.35; color: var(--ink-2); }

.months { gap: 14px; }
.table { width: 100%; border-collapse: collapse; font-size: 16px; }
.table th, .table td {
  padding: 11px 0 11px 8px; text-align: right; font-weight: 400; white-space: nowrap;
  border-bottom: 1px solid var(--hair);
}
.table th:first-child, .table td:first-child { padding-left: 0; text-align: left; }
.table thead th {
  padding-top: 0; padding-bottom: 8px; font-size: 12px; color: var(--ink-2);
  vertical-align: bottom; white-space: normal;
}
.table tbody tr:last-child th, .table tbody tr:last-child td { border-bottom: 0; }
.total th, .total td { font-weight: 500; border-bottom-color: var(--outline); }
.monthLabel { display: inline-flex; align-items: center; gap: 6px; }
.partial { display: inline-flex; color: var(--ink-2); }
.none { padding: 8px 0; font-size: 16px; color: var(--ink-2); }
.key { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 14px; color: var(--ink-2); }
.key span { display: flex; align-items: center; gap: 5px; }

.cards { display: contents; }
.card { gap: 18px; }
.cardHead { display: flex; align-items: center; gap: 14px; }
.cardName { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.name { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 24px; letter-spacing: -0.02em; font-weight: 500; }
.crown { display: flex; }
.cardSub { font-size: 15px; color: var(--ink-2); }
.icon {
  flex: none; width: 52px; height: 52px; border-radius: 999px; background: var(--chip-solid);
  display: flex; align-items: center; justify-content: center;
}
.metrics { display: grid; grid-template-columns: 1.3fr 1fr 1fr 1fr 1fr; gap: 8px; align-items: end; font-size: 18px; }
.metric { display: flex; flex-direction: column; gap: 2px; }
.ret { font-size: 24px; letter-spacing: -0.03em; }
.mLabel { font-size: 12px; }

@media (min-width: 1024px) {
  .top { display: grid; grid-template-columns: minmax(0, 1fr) 380px; gap: 12px; order: 0; }
  .chartSheet { padding: 28px 0 20px; gap: 16px; border-radius: 40px; }
  .pad { padding: 0 30px; }
  .big { font-size: 60px; letter-spacing: -0.045em; }
  .mid { font-size: 28px; }
  .statLabel { font-size: 16px; }
  .stats { gap: 32px; }
  .chart { height: 290px; }

  .check { padding: 28px; gap: 6px; border-radius: 40px; }
  .scoreText { font-size: 15px; }
  .item { gap: 12px; padding: 5px 0; }
  .ok, .no { width: 38px; height: 38px; }
  .itemLabel { font-size: 16px; }
  .itemVal { height: 30px; padding: 0 11px; font-size: 13px; }
  .note { font-size: 13px; }

  .months { order: 2; margin-top: 12px; border-radius: 40px; padding: 28px 30px; gap: 16px; }
  .table { font-size: 17px; }
  .table thead th { font-size: 13px; }
  .table th:first-child { width: 36%; }

  .cards {
    order: 1; display: grid; grid-template-columns: repeat(var(--cols, 4), minmax(0, 1fr));
    gap: 12px; margin-top: 12px;
  }
  .card { border-radius: 32px; padding: 22px; gap: 16px; }
  .cardHead { align-items: flex-start; gap: 10px; }
  .name { font-size: 22px; }
  .cardSub { font-size: 14px; }
  .icon { width: 46px; height: 46px; }
  .metrics {
    grid-template-columns: 1fr 1fr; gap: 10px; font-size: 19px;
  }
  .metric:first-child {
    grid-column: 1 / -1; padding-bottom: 12px; border-bottom: 1px solid var(--hair);
  }
  .ret { font-size: 36px; letter-spacing: -0.04em; }
  .metric:first-child .mLabel { font-size: 14px; color: var(--ink); }
  .mLabel { font-size: 13px; color: var(--ink-2); }
}
```
**Impact:**
- Visual only.
- At 414 pt the table's content width is 366 px (sheet padding 24 px each side). Column budget: month about 86 px (label plus icon), four numeric columns about 52–60 px each, 8 px gaps. "Worst drop" may wrap to two lines in the 12 px header, by design (`white-space: normal`).
- `.statLabel` gains `nowrap` so "Best · F4" stays on one line.

## Verification

**Setup (the worktree has no `node_modules`):** `cd /home/miftah/.worktrees/seer/paper-trading-ship/web && npm ci`
**Build:** `cd /home/miftah/.worktrees/seer/paper-trading-ship/web && npx tsc --noEmit`
**Tests:** `cd /home/miftah/.worktrees/seer/paper-trading-ship/web && npx vitest run` (includes the new `app/(app)/leaderboard/view.test.ts`)
**Manual check:**
1. Seed and run: `npm run db:seed-demo` (phase 10's seed, roster SPY/A/F4/F1), then `npm run dev`. Open `/leaderboard`.
2. Confirm:
   - The crown sits on SPY: the big figure and the SPY card.
   - SPY is the dotted line.
   - A, F4 and F1 have lav/sky/stone cards and ink/line-b/line-c lines, matching the legend.
   - The legend reads "SPY A F4 F1" on desktop and full names on mobile. No raw ids such as `F4-MOM12-N20-TREND` appear.
3. In the checklist sheet, tap each switcher button. The URL becomes `?s=<id>` and scroll is kept. The eyebrow, the six rows (the last is "Backtest gate passed ✕"), the score "n/6", the line "Paper only. / Backtest gate not passed" and the gate note all follow the selection. The Month by month sheet follows too and takes that strategy's sheet colour.
4. Month by month:
   - The since-start row is on top in bold; months are newest first.
   - The first and current months carry the dashed-circle marker, and its tooltip says "Partial month" (hover on desktop, long-press on touch).
   - A month without trades shows `0`. Returns are signed with U+2212 for negatives.
5. `/leaderboard?s=SPY` and `/leaderboard?s=bogus` both select A (phase 11's `selectStrategy` over the research rows).
6. DevTools device at 414×896 (iPhone XS Max) and at 1280×820, each with `prefers-color-scheme` light and dark. Check that there is no horizontal scroll, the table fits, the sheets overlap 40 px on mobile, and on desktop the order is chart | checklist, then cards, then Month by month.
7. Confirm with the keyboard that every switcher control is an icon-only link with `aria-label` and `data-tip` (phase 11's component). This page adds no other button.

**Exit criteria:**
- `npx tsc --noEmit` is clean and `npx vitest run` is green.
- The Leaderboard renders the demo roster with the SPY crown and the dotted SPY line, a six-row checklist per research strategy selected by `?s=`, and a Month by month table with since-start and partial markers.
- It renders at 414 pt and 1280 px, light and dark.
- No string on the page says "Ready for real money" while any check fails.

## Handoffs

- **Phases 10 and 11 (reconciled):** this phase codes against their real exports (Requires A1–A6). Phase 10 Step 10's stop-gap edits to `leaderboard/page.tsx` land first; this phase replaces the file whole. Sequence 10 → 11 → 12.
- **Phase 13 (R7):** the paper runbook/ROADMAP may describe the Leaderboard's Month by month sheet and the `?s=` link for sharing a strategy's view.

## Rollback

`git revert` this phase's commit. It restores `leaderboard/page.tsx` (phase 10 Step 10's version, which already calls the three-argument `checklist`) and `leaderboard.module.css`, and removes `view.ts`/`view.test.ts`. Nothing else imports them, and `tsc` stays green.
