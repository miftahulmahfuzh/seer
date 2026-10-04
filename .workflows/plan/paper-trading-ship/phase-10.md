# Phase 10: Web data layer, monthly math, demo seed

**Plan set:** `PAPER_TRADING_SHIP_PLAN.md`
**Analysis:** `20261004-082027-P4S7_code_analyzer.md`
**Satisfies:** R4 (web reads every engine, monthly math, checklist honesty, no 4-slot assumption), R2 (demo seed in the new shape)
**Depends on:** Phase 1 (migration `003_paper.sql`, contract C1; roster rows; params C2)
**Difficulty:** HARD
**Package:** `web/lib` (plus `web/scripts/seed-demo.mjs`)

---

## Goal

After this phase the web's data layer reads all three engines. It returns:
- each strategy's engine, rules id, paper start and backtest gate;
- the paper-step status of the latest run;
- open holdings of both engines and the SPY benchmark holding;
- next-session pending orders and targets;
- closed trades from `orders` and non-idle `book_trades`;
- leaderboard metrics counted per engine;
- a month-by-month table.

The table comes from a new pure `web/lib/monthly.ts` and is checked against a hand-worked fixture. The go-live checklist gets a sixth item, "Backtest gate passed". The demo seed writes the roster in its paper shape.

Pages are not redesigned here. Their compile fixes (and two safety guards) are listed below and kept to the minimum.

## Verified while planning

Every code block below was applied to a scratch copy of `web/` (`npm ci`) before this plan was written. The results:
- `npx tsc --noEmit` is clean, including the page compile fixes;
- `npx vitest run` passes: 7 files, 44 tests (20 before);
- the seed's SQL (captured with a stub driver) replays without a constraint error into a fresh Postgres with `001` + `002` + the C1 SQL from the plan index;
- every `data.ts` query runs against that seeded database and returns the expected rows.

## Interface Contract

**Deletes:** none. (`Position` type in `web/lib/data.ts:59` is replaced by `Holding`; see Renames.)

**Renames:**
- `data.Position` (type) -> `data.Holding`. Field `id` -> `orderId: number | null` (bracket only) plus `key: string`. `tp` and `sl` become `number | null`.

**Creates:**
- `web/lib/strategy.ts` (pure):
  - `type Engine = 'bracket' | 'book' | 'benchmark'`
  - `type Gate = { passed: boolean; note: string | null }`
  - `engineOf(engine: unknown, isBenchmark: boolean): Engine`
  - `parseGate(raw: unknown): Gate`
  - `shortLabel(name: string, id: string): string`
- `web/lib/monthly.ts` (pure):
  - types `MonthRow`, `SinceStartRow`, `MonthlyTable`, `MonthlyInput`
  - `monthOf(ymd)`
  - `monthlyTable(input: MonthlyInput): MonthlyTable`
- `web/lib/data.ts`:
  - `BRACKET_MAX_DAYS = 5`
  - types `RunState`, `Holding`, `PendingOrder`, `Pending`, `ExitReason`
  - `pendingOrders(strategyId): Promise<Pending>`
  - `monthly(strategyId, sessionDate): Promise<MonthlyTable>`
  - re-exports `type Engine`, `type Gate`
- `web/lib/slots.ts`:
  - `BRACKET_SLOTS = 4`
  - `slotCount(engine: Engine): number`
  - `cardBg(slot: number | null, index: number)`
- Tests:
  - `web/lib/monthly.test.ts`
  - `web/lib/strategy.test.ts`
  - `web/lib/slots.test.ts`
- `seed-demo.mjs --dry-run` flag.

**Signature changes:**
- `checklist(m, spyReturn)` -> `checklist(m: Metrics, spyReturn: number | null, gate: Gate): CheckItem[]`. It returns 6 items; item 6 is `{ label: 'Backtest gate passed', val: 'Passed' | 'Not passed', ok: gate.passed, note? }`. Items 1–5 are unchanged.
- `CheckItem` gains optional `note?: string`.
- `positions(strategyId): Promise<Position[]>` -> `Promise<Holding[]>`.
- `Strategy` gains `engine`, `rulesId`, `paperStart`, `gate`, `isPaper`, `short`.
- `RunStatus` gains `latestStatus`, `paperStatus`, `paperError`, `paperFinishedAt`.
- `Trade` gains `key`, `kind`, `strategyShort`, `entryDate`, `shares: number | null`, `days: number | null`. `reason` widens to `ExitReason` (`'tp' | 'sl' | 'time' | 'gap' | 'signal' | 'forced'`). `id` is kept, but is unique only within its own table; use `key` for React keys.
- `slotLetter` and `slotBg` keep their signatures and now wrap any integer, including 0 and negatives.

**Unchanged (callers keep working):** `champion()`, `picks()`/`Pick` (Today still calls it and gets `[]` for SPY), `leaderboard()`/`Board` shape, `dismissAction()`, `strategyMetrics()`, `Snapshot`, `Metrics`, `SLOT_LETTERS`, `SLOT_BG`.

**Exact semantics the UI phases code against:**
- `Strategy.isPaper` is `!isBenchmark && !isChampion`. It is true for A, F4 and F1, false for SPY.
- `Strategy.short` is the name before `·`: `'A'`, `'F4'`, `'F1'`, `'SPY'`.
- `Strategy.gate` is `{ passed: false, note: null }` until `paper` writes `params.backtest_gate` (phase 7).
- `RunStatus.paperStatus`, `paperError` and `paperFinishedAt` come from the most recent `runs` row (ordered by `started_at DESC, id DESC`), whether that run succeeded or not. "The latest real run" is read as the latest row, not the latest success. Demo rows are included so the demo shows its success. In production a demo run never coexists with real runs, because `nightly`/`paper` purge demo data first. `paperStatus === null` means the paper step never started for that run, for example because the bars step failed. `latestStatus` is that same row's bars `status`. `stale` and `sessionDate` keep their logic (latest *successful* run).
- `Holding.kind` is `'bracket'` for an open `orders` row, `'book'` for a `book_positions` row of a book strategy, and `'benchmark'` for the SPY holding.
- `Holding.maxDays` is `5` for bracket and `null` otherwise. A "day N of 5" UI must check `maxDays !== null`.
- `Holding.current`:
  - bracket: `orders.mark`, else the latest `bars.close`, else the fill price;
  - book: `book_positions.mark`.
- `Holding.weight` is `value / equity`, where equity is `paper_state.equity_usd`, else the latest snapshot.
- `Holding.pnl`:
  - bracket: `(current − entry) × shares`;
  - book: `value + income_usd − cost_usd`, so buy costs and dividends are included, matching how `sim.book` closes a `Trade`.
- `Pending.decision`:
  - bracket: always `true`;
  - book: `paper_state.pending_decision`;
  - benchmark: `false`.
- Book `PendingOrder`s are `book_targets` rows for `paper_state.pending_session`, and only when `pending_decision`. They carry `weight` and `shares: null`.
- `closedTrades` returns at most 300 rows: closed `orders` plus `book_trades WHERE NOT idle`, newest exit first.
- `leaderboard()` takes P/L per engine:
  - bracket: closed `orders.pnl_usd`;
  - book: non-idle `book_trades.pnl_usd`;
  - benchmark: none.
  The snapshots used are all `equity_snapshots` of the strategy, including the day-0 snapshot.
- `monthly(strategyId, sessionDate)`: pass `runStatus().sessionDate`. It returns the table described in `monthly.ts` (month rows oldest first, plus `sinceStart`). It returns `{ months: [], sinceStart: null }` for an unknown id or when fewer than 2 snapshots exist.

**Requires (from earlier phases):**
- Phase 1 migration `003` exactly as C1 lists. Columns used:
  - `strategies.engine`, `rules_id`, `paper_start`;
  - `orders.mark`;
  - `runs.paper_status`, `paper_error`, `paper_finished_at`;
  - tables `paper_state`, `book_positions`, `book_targets`, `book_fills` (TRUNCATE only), `book_trades`, `dividends` (TRUNCATE only).
- C2 `params.backtest_gate` = `{ passed: boolean, note: string }`.

**Leaves alone (owned by others):**
- `web/app/(app)/page.tsx`, `positions/*`, `history/*`, new `StrategySwitch`/`PaperChip` (phase 11), beyond the compile fixes in Step 10;
- `web/app/(app)/leaderboard/*` (phase 12), beyond the compile fix in Step 10;
- all CSS;
- `engine/*`, `db/migrations/*` (phase 1);
- `.github/*` and the CI `tsc` step (phase 13).

## Files

| File | Action | What changes |
|---|---|---|
| `web/lib/strategy.ts` | create | pure engine/gate/short-label helpers |
| `web/lib/strategy.test.ts` | create | tests for the helpers |
| `web/lib/metrics.ts` | modify (lines 1–63, whole file) | `Gate` import, `CheckItem.note`, `checklist(m, spy, gate)` with a 6th item |
| `web/lib/metrics.test.ts` | modify (lines 1–42, whole file) | checklist tests for 6 items |
| `web/lib/monthly.ts` | create | pure month-by-month table |
| `web/lib/monthly.test.ts` | create | hand-checked fixture plus edge cases |
| `web/lib/slots.ts` | modify (lines 1–6, whole file) | wrap-safe helpers, `slotCount`, `cardBg` |
| `web/lib/slots.test.ts` | create | slot helper tests |
| `web/lib/data.ts` | modify (lines 1–118, whole file) | strategies/runStatus/positions/pendingOrders/closedTrades/leaderboard/monthly |
| `web/scripts/seed-demo.mjs` | modify (lines 1–152, whole file) | roster in the paper shape, book tables, paper_state, `--dry-run` |
| `web/app/(app)/page.tsx` | minimal fix (lines 26, 87, 92) | compile fix for `Holding`, plus the day-5 action guard (safety) |
| `web/app/(app)/positions/page.tsx` | minimal fix (lines 16, 42–43, 47, 63) | compile fix for nullable `tp`/`sl` and `key`, plus the exits-today guard |
| `web/app/(app)/leaderboard/page.tsx` | minimal fix (lines 22, 63–64) | compile fix for `checklist` arity, plus the six-of-six guard (safety) |

## Implementation Steps

Run `cd web && npm ci` once if `web/node_modules` is missing (the worktree has none today).

### Step 1: Pure strategy helpers
**File:** `web/lib/strategy.ts` (new)
**Change:** Holds the `Engine` and `Gate` types and the row helpers in a module with no DB import, so that `metrics.ts`, `slots.ts`, pages and tests can use them without a connection. A gate that is missing or malformed reads as **not passed** (D12: a pass is never assumed).
**Code:**
```ts
// Pure helpers for `strategies` rows: engine, backtest gate and short label. No database access,
// so pages, metrics and tests can import them without a connection.

/** How a strategy trades (migration 003, `strategies.engine`). */
export type Engine = 'bracket' | 'book' | 'benchmark';

/** `strategies.params->'backtest_gate'` (contract C2): did the strategy pass its backtest gate? */
export type Gate = { passed: boolean; note: string | null };

const ENGINES: readonly string[] = ['bracket', 'book', 'benchmark'];

/** The row's engine. Rows written before migration 003 have none: benchmark when flagged, else bracket. */
export function engineOf(engine: unknown, isBenchmark: boolean): Engine {
  if (typeof engine === 'string' && ENGINES.includes(engine)) return engine as Engine;
  return isBenchmark ? 'benchmark' : 'bracket';
}

/** Reads the gate from params. Missing or malformed reads as not passed: a pass is never assumed. */
export function parseGate(raw: unknown): Gate {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) return { passed: false, note: null };
  const g = raw as Record<string, unknown>;
  const note = typeof g.note === 'string' && g.note.trim() !== '' ? g.note : null;
  return { passed: g.passed === true, note };
}

/** 'F4 · Momentum' -> 'F4', 'A · Quant' -> 'A', 'SPY' -> 'SPY'; the id when the name has no head. */
export function shortLabel(name: string, id: string): string {
  const head = name.split('·')[0].trim();
  return head === '' ? id : head;
}
```
**Impact:** None on existing code.

### Step 2: Tests for the strategy helpers
**File:** `web/lib/strategy.test.ts` (new)
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import { engineOf, parseGate, shortLabel } from './strategy';

describe('engineOf', () => {
  it('keeps a known engine', () => {
    expect(engineOf('book', false)).toBe('book');
    expect(engineOf('bracket', false)).toBe('bracket');
    expect(engineOf('benchmark', true)).toBe('benchmark');
  });
  it('falls back for rows written before migration 003', () => {
    expect(engineOf(null, true)).toBe('benchmark');
    expect(engineOf(null, false)).toBe('bracket');
    expect(engineOf('ml', false)).toBe('bracket');
  });
});

describe('parseGate', () => {
  it('reads the backtest gate from params', () => {
    expect(parseGate({ passed: false, note: 'P7a dev window only; failed max DD <= 15% (22.2%)' }))
      .toEqual({ passed: false, note: 'P7a dev window only; failed max DD <= 15% (22.2%)' });
    expect(parseGate({ passed: true, note: '' })).toEqual({ passed: true, note: null });
  });
  it('never assumes a pass', () => {
    expect(parseGate(null)).toEqual({ passed: false, note: null });
    expect(parseGate(undefined)).toEqual({ passed: false, note: null });
    expect(parseGate({ passed: 'true' })).toEqual({ passed: false, note: null });
    expect(parseGate([true])).toEqual({ passed: false, note: null });
  });
});

describe('shortLabel', () => {
  it('takes the part before the middle dot', () => {
    expect(shortLabel('F4 · Momentum', 'F4-MOM12-N20-TREND')).toBe('F4');
    expect(shortLabel('A · Quant', 'A')).toBe('A');
    expect(shortLabel('SPY', 'SPY')).toBe('SPY');
    expect(shortLabel(' · Nameless', 'X1')).toBe('X1');
  });
});
```
**Impact:** Three tests added.

### Step 3: Checklist gains "Backtest gate passed"
**File:** `web/lib/metrics.ts:1-63` (replace the whole file)
**Change:**
- `strategyMetrics` is byte-for-byte unchanged.
- `checklist` takes the strategy's `Gate` and appends a sixth item, which carries the gate's `note` when there is one.
- Items 1–5 keep their labels, values and `ok` rules.
**Code:**
```ts
import type { Gate } from './strategy';

export type Snapshot = { date: string; equity: number };

export type Metrics = {
  totalReturn: number | null;
  winRate: number | null;
  profitFactor: number | null;
  maxDrawdown: number | null;
  trades: number;
  months: number;
};

const DAY = 86_400_000;

/** Metrics over a strategy's equity curve and its closed trades' P/L (USD). */
export function strategyMetrics(snaps: Snapshot[], pnls: number[]): Metrics {
  const wins = pnls.filter(p => p > 0);
  const losses = pnls.filter(p => p <= 0);
  const grossWin = wins.reduce((a, p) => a + p, 0);
  const grossLoss = -losses.reduce((a, p) => a + p, 0);

  let peak = -Infinity, maxDd = 0;
  for (const s of snaps) {
    peak = Math.max(peak, s.equity);
    maxDd = Math.max(maxDd, (peak - s.equity) / peak);
  }

  const first = snaps[0], last = snaps[snaps.length - 1];
  return {
    totalReturn: first ? last.equity / first.equity - 1 : null,
    winRate: pnls.length ? wins.length / pnls.length : null,
    profitFactor: pnls.length ? (grossLoss === 0 ? Infinity : grossWin / grossLoss) : null,
    maxDrawdown: snaps.length ? maxDd : null,
    trades: pnls.length,
    months: first ? (Date.parse(last.date) - Date.parse(first.date)) / DAY / 30.44 : 0,
  };
}

/** One go-live rule. `note` explains a backtest-gate verdict when the roster gives one. */
export type CheckItem = { label: string; val: string; ok: boolean; note?: string };

/**
 * The fixed go-live rules from the design doc (§1): five forward-test metrics, then
 * "Backtest gate passed" from `strategies.params.backtest_gate` (D12). All six must hold.
 */
export function checklist(m: Metrics, spyReturn: number | null, gate: Gate): CheckItem[] {
  const ret = m.totalReturn ?? 0;
  const p1 = (v: number) => (v >= 0 ? '+' : '−') + Math.abs(v * 100).toFixed(1);
  const gateItem: CheckItem = { label: 'Backtest gate passed', val: gate.passed ? 'Passed' : 'Not passed', ok: gate.passed };
  if (gate.note !== null) gateItem.note = gate.note;
  return [
    { label: '≥ 3 months forward', val: `${(Math.floor(m.months * 10) / 10).toFixed(1)} mo`, ok: m.months >= 3 },
    { label: '≥ 100 trades', val: `${m.trades} / 100`, ok: m.trades >= 100 },
    {
      label: 'Beats SPY',
      val: spyReturn === null ? '—' : `${p1(ret)} vs ${p1(spyReturn)}`,
      ok: m.totalReturn !== null && spyReturn !== null && ret > spyReturn,
    },
    {
      label: 'Profit factor ≥ 1.3',
      val: m.profitFactor === null ? '—' : m.profitFactor === Infinity ? '∞' : m.profitFactor.toFixed(2),
      ok: (m.profitFactor ?? 0) >= 1.3,
    },
    {
      label: 'Max drawdown ≤ 15%',
      val: m.maxDrawdown === null ? '—' : (m.maxDrawdown * 100).toFixed(1) + '%',
      ok: m.maxDrawdown !== null && m.maxDrawdown <= 0.15,
    },
    gateItem,
  ];
}
```
**Impact:**
- `checklist` arity 2 -> 3. The only caller, `leaderboard/page.tsx:22`, is fixed in Step 10.
- The checklist length 5 -> 6: `leaderboard/page.tsx:63-64` hardcodes 5 and is fixed in Step 10.

### Step 4: Checklist tests
**File:** `web/lib/metrics.test.ts:1-42` (replace the whole file)
**Change:**
- The `strategyMetrics` tests are kept as they are.
- The checklist test is split into three: the five rules are unchanged, the gate is item 6, and only six of six passes. The case "every forward metric passes but the gate failed" is pinned to 5/6, not ready.
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import { checklist, strategyMetrics } from './metrics';

const snaps = (vals: number[]) =>
  vals.map((equity, i) => ({ date: new Date(Date.UTC(2026, 6, 1 + i)).toISOString().slice(0, 10), equity }));

const FAILED = { passed: false, note: 'P7a dev window only; failed max DD <= 15% (22.2%)' };
const PASSED = { passed: true, note: null };

describe('strategyMetrics', () => {
  it('computes return, win rate, profit factor, drawdown and trade count', () => {
    const m = strategyMetrics(snaps([1000, 1100, 990, 1050]), [30, -10, 20, -10]);
    expect(m.totalReturn).toBeCloseTo(0.05);
    expect(m.winRate).toBeCloseTo(0.5);
    expect(m.profitFactor).toBeCloseTo(2.5);
    expect(m.maxDrawdown).toBeCloseTo(0.1); // 1100 -> 990
    expect(m.trades).toBe(4);
  });
  it('returns nulls with no data', () => {
    const m = strategyMetrics([], []);
    expect(m.totalReturn).toBeNull();
    expect(m.winRate).toBeNull();
    expect(m.profitFactor).toBeNull();
    expect(m.maxDrawdown).toBeNull();
    expect(m.trades).toBe(0);
  });
  it('gives an infinite profit factor when nothing lost', () => {
    expect(strategyMetrics(snaps([1, 2]), [5]).profitFactor).toBe(Infinity);
  });
  it('measures months of forward testing', () => {
    const m = strategyMetrics([{ date: '2026-07-06', equity: 1 }, { date: '2026-10-05', equity: 1 }], []);
    expect(m.months).toBeCloseTo(3.0, 1);
  });
});

describe('checklist', () => {
  const base = { totalReturn: 0.068, winRate: 0.58, profitFactor: 1.42, maxDrawdown: 0.079, trades: 84, months: 3.0 };

  it('keeps the five forward-test rules unchanged', () => {
    const items = checklist(base, 0.046, PASSED);
    expect(items.slice(0, 5).map(i => i.ok)).toEqual([true, false, true, true, true]);
    expect(items[1].val).toBe('84 / 100');
    expect(checklist({ ...base, maxDrawdown: 0.16, trades: 120 }, 0.046, PASSED)[4].ok).toBe(false);
  });

  it('adds the backtest gate as a sixth rule', () => {
    const items = checklist(base, 0.046, FAILED);
    expect(items).toHaveLength(6);
    expect(items[5]).toEqual({ label: 'Backtest gate passed', val: 'Not passed', ok: false, note: FAILED.note });
    expect(checklist(base, 0.046, PASSED)[5]).toEqual({ label: 'Backtest gate passed', val: 'Passed', ok: true });
  });

  it('passes only when all six hold', () => {
    expect(checklist({ ...base, trades: 120 }, 0.046, PASSED).every(i => i.ok)).toBe(true);
    // Every forward metric passing does not make a strategy ready while its backtest gate failed.
    const failedGate = checklist({ ...base, trades: 120 }, 0.046, FAILED);
    expect(failedGate.filter(i => i.ok)).toHaveLength(5);
    expect(failedGate.every(i => i.ok)).toBe(false);
  });
});
```

### Step 5: Pure month-by-month math
**File:** `web/lib/monthly.ts` (new)
**Change:** The table for D5. The grouping is by snapshot index: snapshots after day 0 are grouped by calendar month, and each group's base is the snapshot just before it. So the first month's base is day 0, and each later month's base is the previous month's last snapshot. Definitions are in the file header. They match `metrics.ts`:
- the since-start `return` and `worstDrop` are `strategyMetrics(...).totalReturn` and `.maxDrawdown`;
- `trades` uses the same trade set the leaderboard counts.

SPY is read on the **exact same two dates** (base and month end), so a missing SPY snapshot shows as `null`, never as a value over a different window. Months with no snapshot at all (the engine off for a whole month) produce no row. That cannot happen while `paper` runs nightly, so it is not padded.
**Code:**
```ts
// Month-by-month paper performance (D5). Pure: the data layer passes the rows in.
//
// Definitions (the same as metrics.ts):
// - A month's base is the last snapshot before the month; for the first month that is the
//   day-0 snapshot (initial cash, dated the session before paper start).
// - Return = the month's last equity / base equity - 1.
// - SPY = the benchmark's equity on the same two dates, / - 1 (null when either is missing).
// - Trades = closed trades whose exit date falls in the month (the trades metrics.ts counts).
// - Worst drop = the largest peak-to-trough fall within the month, the running peak seeded at
//   the base: (peak - equity) / peak, >= 0.
// - The first month is partial when its base (day 0) is in the same month; the latest month is
//   partial while the next session on the engine's calendar is still in that month.
import { strategyMetrics, type Snapshot } from './metrics';

/** One calendar month of a strategy's paper equity, next to SPY over the same dates. */
export type MonthRow = {
  month: string; // 'YYYY-MM'
  from: string; // base snapshot date
  to: string; // the month's last snapshot date
  return: number;
  spyReturn: number | null;
  trades: number;
  worstDrop: number;
  partial: boolean;
};

/** The whole paper period: day 0 to the latest snapshot. */
export type SinceStartRow = {
  from: string;
  to: string;
  return: number;
  spyReturn: number | null;
  trades: number;
  worstDrop: number;
};

export type MonthlyTable = { months: MonthRow[]; sinceStart: SinceStartRow | null };

export type MonthlyInput = {
  /** The strategy's equity snapshots, day 0 included. Any order. */
  snaps: Snapshot[];
  /** The benchmark's (SPY) snapshots; null when there is no benchmark. */
  spy: Snapshot[] | null;
  /** Exit dates of the strategy's closed trades (closed orders, or non-idle book trades). */
  exitDates: string[];
  /** runStatus().sessionDate: the next session on the engine's calendar; null when unknown. */
  sessionDate: string | null;
};

/** 'YYYY-MM' of a 'YYYY-MM-DD' date. */
export const monthOf = (ymd: string) => ymd.slice(0, 7);

const byDate = (a: Snapshot, b: Snapshot) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0);

function worstDrop(base: number, values: number[]): number {
  let peak = base, worst = 0;
  for (const v of values) {
    peak = Math.max(peak, v);
    worst = Math.max(worst, (peak - v) / peak);
  }
  return worst;
}

/** Month rows oldest first, plus the since-start row. Fewer than two snapshots: nothing to show yet. */
export function monthlyTable({ snaps, spy, exitDates, sessionDate }: MonthlyInput): MonthlyTable {
  const s = [...snaps].sort(byDate);
  if (s.length < 2) return { months: [], sinceStart: null };

  const spyOn = new Map((spy ?? []).map(x => [x.date, x.equity]));
  const spyOver = (from: string, to: string): number | null => {
    const a = spyOn.get(from), b = spyOn.get(to);
    return a === undefined || b === undefined ? null : b / a - 1;
  };
  const tradesIn = new Map<string, number>();
  for (const d of exitDates) tradesIn.set(monthOf(d), (tradesIn.get(monthOf(d)) ?? 0) + 1);

  const day0 = s[0], last = s[s.length - 1];
  const months: MonthRow[] = [];
  let i = 1;
  while (i < s.length) {
    const month = monthOf(s[i].date);
    const base = s[i - 1];
    let j = i;
    while (j < s.length && monthOf(s[j].date) === month) j++;
    const inMonth = s.slice(i, j);
    const end = inMonth[inMonth.length - 1];
    const firstPartial = i === 1 && monthOf(day0.date) === month;
    const latestPartial = j === s.length && (sessionDate === null || monthOf(sessionDate) === month);
    months.push({
      month,
      from: base.date,
      to: end.date,
      return: end.equity / base.equity - 1,
      spyReturn: spyOver(base.date, end.date),
      trades: tradesIn.get(month) ?? 0,
      worstDrop: worstDrop(base.equity, inMonth.map(x => x.equity)),
      partial: firstPartial || latestPartial,
    });
    i = j;
  }

  const all = strategyMetrics(s, []);
  return {
    months,
    sinceStart: {
      from: day0.date,
      to: last.date,
      return: all.totalReturn ?? 0,
      spyReturn: spyOver(day0.date, last.date),
      trades: exitDates.length,
      worstDrop: all.maxDrawdown ?? 0,
    },
  };
}
```
**Impact:** None on existing code. Phase 12 renders `MonthlyTable`.

### Step 6: Monthly fixture tests (acceptance 4)
**File:** `web/lib/monthly.test.ts` (new)
**Change:** A hand-checked fixture. Day 0 is Mon 2026-10-05; there are snapshots through 2026-12-02, and the next session is 2026-12-03. The expected values, worked by hand:

| Month | Base -> end | Return | SPY | Trades | Worst drop | Partial |
|---|---|---|---|---|---|---|
| 2026-10 | 1000 (day 0) -> 990 | −1.00% | 500 -> 510 = +2.00% | 1 | (1010−990)/1010 = 1.98% | yes (day 0 in October) |
| 2026-11 | 990 -> 1000 | +1.01% | 510 -> 520 = +1.96% | 0 | (1020−960)/1020 = 5.88% | no |
| 2026-12 | 1000 -> 1029 | +2.90% | 520 -> 546 = +5.00% | 2 | (1050−1029)/1050 = 2.00% | yes (next session in December) |
| Since start | 1000 -> 1029 | +2.90% | 500 -> 546 = +9.20% | 3 | 5.88% | — |

The edge tests cover:
- a peak seeded at the base;
- a full first month when day 0 falls in the previous month (no row for the day-0-only month);
- an unknown next session (the latest month is partial);
- fewer than 2 snapshots;
- unsorted input;
- SPY missing on a date.

**Code:**
```ts
import { describe, expect, it } from 'vitest';
import { strategyMetrics } from './metrics';
import { monthlyTable, monthOf } from './monthly';

const series = (rows: [string, number][]) => rows.map(([date, equity]) => ({ date, equity }));

// Hand-checked fixture. Day 0 is Mon 2026-10-05 (paper start Tue 2026-10-06), so October is a
// partial first month. The next session is 2026-12-03, so December is the partial current month.
// November has no closed trades.
const STRAT = series([
  ['2026-10-05', 1000], // day 0: initial cash
  ['2026-10-06', 1010],
  ['2026-10-30', 990], // October's last session
  ['2026-11-02', 1020],
  ['2026-11-16', 960],
  ['2026-11-30', 1000], // November's last session
  ['2026-12-01', 1050],
  ['2026-12-02', 1029],
]);
const SPY = series([
  ['2026-10-05', 500],
  ['2026-10-06', 505],
  ['2026-10-30', 510],
  ['2026-11-02', 500],
  ['2026-11-16', 495],
  ['2026-11-30', 520],
  ['2026-12-01', 520],
  ['2026-12-02', 546],
]);
const EXITS = ['2026-10-30', '2026-12-01', '2026-12-02'];

describe('monthlyTable: hand-checked fixture', () => {
  const t = monthlyTable({ snaps: STRAT, spy: SPY, exitDates: EXITS, sessionDate: '2026-12-03' });

  it('splits on calendar-month boundaries, oldest first', () => {
    expect(t.months.map(m => [m.month, m.from, m.to])).toEqual([
      ['2026-10', '2026-10-05', '2026-10-30'], // base = day 0
      ['2026-11', '2026-10-30', '2026-11-30'], // base = October's last snapshot
      ['2026-12', '2026-11-30', '2026-12-02'], // base = November's last snapshot
    ]);
  });

  it('computes each month from its base', () => {
    const [oct, nov, dec] = t.months;
    expect(oct.return).toBeCloseTo(990 / 1000 - 1, 12); // -1.00%
    expect(nov.return).toBeCloseTo(1000 / 990 - 1, 12); // +1.01%
    expect(dec.return).toBeCloseTo(1029 / 1000 - 1, 12); // +2.90%
  });

  it('puts SPY over the same dates', () => {
    const [oct, nov, dec] = t.months;
    expect(oct.spyReturn).toBeCloseTo(510 / 500 - 1, 12); // +2.00%
    expect(nov.spyReturn).toBeCloseTo(520 / 510 - 1, 12); // +1.96%
    expect(dec.spyReturn).toBeCloseTo(546 / 520 - 1, 12); // +5.00%
  });

  it('counts trades by exit month, zero for a month with none', () => {
    expect(t.months.map(m => m.trades)).toEqual([1, 0, 2]);
  });

  it('measures the worst drop within each month', () => {
    const [oct, nov, dec] = t.months;
    expect(oct.worstDrop).toBeCloseTo((1010 - 990) / 1010, 12); // 1.98%
    expect(nov.worstDrop).toBeCloseTo((1020 - 960) / 1020, 12); // 5.88%
    expect(dec.worstDrop).toBeCloseTo((1050 - 1029) / 1050, 12); // 2.00%
  });

  it('marks the first and the current month partial, not the full month between', () => {
    expect(t.months.map(m => m.partial)).toEqual([true, false, true]);
  });

  it('adds a since-start row with the metrics.ts definitions', () => {
    expect(t.sinceStart).not.toBeNull();
    const ss = t.sinceStart!;
    expect([ss.from, ss.to]).toEqual(['2026-10-05', '2026-12-02']);
    expect(ss.return).toBeCloseTo(0.029, 12);
    expect(ss.spyReturn).toBeCloseTo(546 / 500 - 1, 12); // +9.20%
    expect(ss.trades).toBe(3);
    expect(ss.worstDrop).toBeCloseTo((1020 - 960) / 1020, 12);
    const m = strategyMetrics(STRAT, []);
    expect(ss.return).toBe(m.totalReturn);
    expect(ss.worstDrop).toBe(m.maxDrawdown);
  });

  it('chains: compounding the months gives the since-start return', () => {
    const chained = t.months.reduce((a, m) => a * (1 + m.return), 1) - 1;
    expect(chained).toBeCloseTo(t.sinceStart!.return, 12);
  });
});

describe('monthlyTable: edges', () => {
  it('seeds the running peak at the base, so a month that opens lower shows its drop', () => {
    const t = monthlyTable({
      snaps: series([['2026-10-30', 1000], ['2026-11-02', 950], ['2026-11-03', 980]]),
      spy: null, exitDates: [], sessionDate: '2026-11-04',
    });
    expect(t.months).toHaveLength(1);
    expect(t.months[0].worstDrop).toBeCloseTo(0.05, 12);
    expect(t.months[0].return).toBeCloseTo(-0.02, 12);
    expect(t.months[0].spyReturn).toBeNull();
  });

  it('has a full first month when day 0 falls in the month before', () => {
    const t = monthlyTable({
      snaps: series([['2026-10-30', 1000], ['2026-11-02', 1010], ['2026-11-30', 1020]]),
      spy: null, exitDates: [], sessionDate: '2026-12-01',
    });
    expect(t.months.map(m => [m.month, m.partial])).toEqual([['2026-11', false]]); // no October row: day 0 only
  });

  it('treats the latest month as partial when the next session is unknown', () => {
    const t = monthlyTable({
      snaps: series([['2026-10-30', 1000], ['2026-11-30', 1020]]), spy: null, exitDates: [], sessionDate: null,
    });
    expect(t.months[0].partial).toBe(true);
  });

  it('shows nothing before the first paper session', () => {
    expect(monthlyTable({ snaps: series([['2026-10-05', 1000]]), spy: null, exitDates: [], sessionDate: '2026-10-06' }))
      .toEqual({ months: [], sinceStart: null });
    expect(monthlyTable({ snaps: [], spy: null, exitDates: [], sessionDate: null })).toEqual({ months: [], sinceStart: null });
  });

  it('sorts its input and leaves SPY empty where SPY has no snapshot on a base or end date', () => {
    const snaps = series([['2026-11-02', 1010], ['2026-10-30', 1000], ['2026-12-01', 1030], ['2026-11-30', 1020]]);
    const spy = series([['2026-10-30', 500], ['2026-11-30', 510]]); // no 2026-12-01
    const t = monthlyTable({ snaps, spy, exitDates: [], sessionDate: '2026-12-02' });
    expect(t.months.map(m => m.month)).toEqual(['2026-11', '2026-12']);
    expect(t.months[0].spyReturn).toBeCloseTo(0.02, 12);
    expect(t.months[1].spyReturn).toBeNull();
    expect(t.sinceStart!.spyReturn).toBeNull();
  });

  it('reads the month from a date string', () => {
    expect(monthOf('2026-10-05')).toBe('2026-10');
  });
});
```

### Step 7: Slot helpers that work without slots
**File:** `web/lib/slots.ts:1-6` (replace the whole file)
**Change:**
- `slotLetter` and `slotBg` keep their signatures but wrap any integer (the old `(slot - 1) % 4` returned `undefined` for slot 0).
- New `slotCount(engine)`: 4 for bracket, 0 for book and benchmark. Phase 11 uses it instead of assuming 4.
- New `cardBg(slot | null, index)`: a pastel for slotless book cards, cycled by list position.
**Code:**
```ts
import type { Engine } from './strategy';

/** Seer's four pick slots spell its name; each has its own pastel sheet. Only bracket strategies have slots. */
export const SLOT_LETTERS = ['S', 'E', 'E', 'R'] as const;
export const SLOT_BG = ['bg-lav', 'bg-butter', 'bg-sky', 'bg-stone'] as const;
export const BRACKET_SLOTS = 4;

/** 0..3 for any integer, negatives included. */
const wrap = (i: number) => ((Math.trunc(i) % 4) + 4) % 4;

export const slotLetter = (slot: number) => SLOT_LETTERS[wrap(slot - 1)];
export const slotBg = (slot: number) => SLOT_BG[wrap(slot - 1)];

/** Pick slots a strategy fills: 4 for bracket strategies, none for book and benchmark strategies. */
export const slotCount = (engine: Engine) => (engine === 'bracket' ? BRACKET_SLOTS : 0);

/** A card's pastel sheet: its slot's sheet when it has a slot, else cycled by its 0-based place in the list. */
export const cardBg = (slot: number | null, index: number) => (slot === null ? SLOT_BG[wrap(index)] : slotBg(slot));
```
**Impact:** Existing callers (`page.tsx`, `positions/page.tsx`) compile unchanged.

### Step 8: Slot helper tests
**File:** `web/lib/slots.test.ts` (new)
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import { cardBg, slotBg, slotCount, slotLetter } from './slots';

describe('slots', () => {
  it('spells SEER across slots 1..4 and wraps', () => {
    expect([1, 2, 3, 4].map(slotLetter).join('')).toBe('SEER');
    expect(slotLetter(5)).toBe('S');
    expect(slotBg(4)).toBe('bg-stone');
    expect(slotBg(0)).toBe('bg-stone');
  });
  it('gives only bracket strategies slots', () => {
    expect(slotCount('bracket')).toBe(4);
    expect(slotCount('book')).toBe(0);
    expect(slotCount('benchmark')).toBe(0);
  });
  it('colours slotless cards by their place in the list', () => {
    expect(cardBg(null, 0)).toBe('bg-lav');
    expect(cardBg(null, 5)).toBe('bg-butter');
    expect(cardBg(null, 19)).toBe('bg-stone');
    expect(cardBg(3, 0)).toBe('bg-sky');
  });
});
```

### Step 9: Data layer for every engine
**File:** `web/lib/data.ts:1-118` (replace the whole file)
**Change:** See the Interface Contract for the exact semantics. Notes:
- `strategies()` reads `engine`, `rules_id`, `paper_start::text` and `params->'backtest_gate'`. It now orders by `sort, id`.
- `runStatus()` runs three queries in parallel. The latest-success query is unchanged, so the stale logic is unchanged. The query for the most recent row adds the paper fields.
- `positions()` queries `orders` (status `open`) and `book_positions` in parallel and concatenates them. A strategy has rows in only one of the two.
  - The mark comes from `orders.mark`. The fallback to the latest close is only for rows written before `003`. A post-split close would be in the wrong units for a pre-split order, and the engine (phase 7) always writes `mark`.
- `pendingOrders()` reads the strategy's engine, `paper_state`, pending orders and pending targets in parallel, then picks by engine.
- `closedTrades()` is one `UNION ALL` (orders `closed` + `book_trades NOT idle`) joined to `strategies` for the short label. The filters are as before.
- `leaderboard()` gets P/L rows tagged with their source table and keeps, per strategy, only those from its own engine's table. Benchmark gets none.
- `monthly()` loads the strategy's snapshots, the benchmark's snapshots, and the exit dates from the engine's own trade table, then calls `monthlyTable`.
**Code:**
```ts
import { sql } from '@/lib/db';
import { strategyMetrics, type Metrics, type Snapshot } from '@/lib/metrics';
import { monthlyTable, type MonthlyTable } from '@/lib/monthly';
import { isStale } from '@/lib/session';
import { engineOf, parseGate, shortLabel, type Engine, type Gate } from '@/lib/strategy';

export type { Engine, Gate } from '@/lib/strategy';

type Row = Record<string, any>;

const n = (v: unknown) => Number(v);
const nn = (v: unknown) => (v === null || v === undefined ? null : Number(v));
// Date columns are selected as ::text; JS Date parsing would shift them by the server's timezone.
const ymd = (v: unknown) => String(v).slice(0, 10);
const ymdOrNull = (v: unknown) => (v === null || v === undefined ? null : ymd(v));

/** Design §5: a bracket position is closed by the end of its fifth session. */
export const BRACKET_MAX_DAYS = 5;

export type Strategy = {
  id: string;
  name: string;
  sub: string;
  icon: string;
  isChampion: boolean;
  isBenchmark: boolean;
  /** 'bracket' (A), 'book' (F4, F1) or 'benchmark' (SPY). */
  engine: Engine;
  /** 'design-v0', 'monthly-hold'; null for SPY. */
  rulesId: string | null;
  /** First paper session; null until the engine's `paper` command starts the clock. */
  paperStart: string | null;
  /** params->'backtest_gate'; { passed: false, note: null } until `paper` writes the frozen spec. */
  gate: Gate;
  /** A research strategy: its orders and positions are paper only and never a buy recommendation. */
  isPaper: boolean;
  /** 'A', 'F4', 'F1', 'SPY': the part of the name before the middle dot. */
  short: string;
};

function toStrategy(r: Row): Strategy {
  const isBenchmark = r.is_benchmark === true;
  const isChampion = r.is_champion === true;
  return {
    id: r.id,
    name: r.name,
    sub: r.sub,
    icon: r.icon,
    isChampion,
    isBenchmark,
    engine: engineOf(r.engine, isBenchmark),
    rulesId: r.rules_id ?? null,
    paperStart: ymdOrNull(r.paper_start),
    gate: parseGate(r.gate),
    isPaper: !isBenchmark && !isChampion,
    short: shortLabel(r.name, r.id),
  };
}

export async function strategies(): Promise<Strategy[]> {
  const rows = await sql`SELECT id, name, sub, icon, is_champion, is_benchmark, engine, rules_id,
      paper_start::text AS paper_start, params->'backtest_gate' AS gate
    FROM strategies ORDER BY sort, id`;
  return rows.map(toStrategy);
}

export async function champion(): Promise<Strategy | null> {
  return (await strategies()).find(s => s.isChampion) ?? null;
}

export type RunState = 'running' | 'success' | 'failed';
const runState = (v: unknown): RunState | null => (v === 'running' || v === 'success' || v === 'failed' ? v : null);

export type RunStatus = {
  sessionDate: string | null;
  dataDate: string | null;
  finishedAt: Date | null;
  isDemo: boolean;
  stale: boolean;
  usdIdr: number;
  /** Bars step of the most recent run, whatever its outcome; null before the first run. */
  latestStatus: RunState | null;
  /** Paper step of the most recent run; null when it never started (e.g. the bars step failed). */
  paperStatus: RunState | null;
  paperError: string | null;
  paperFinishedAt: Date | null;
};

/**
 * Latest successful pipeline run, whether it's stale, and the IDR rate to display; plus the
 * bars and paper status of the most recent run (successful or not).
 */
export async function runStatus(now = new Date()): Promise<RunStatus> {
  const [[run], [latest], [fx]] = await Promise.all([
    sql`SELECT session_date::text AS session_date, data_date::text AS data_date, finished_at, is_demo FROM runs
      WHERE status = 'success' ORDER BY finished_at DESC LIMIT 1`,
    sql`SELECT status, paper_status, paper_error, paper_finished_at FROM runs ORDER BY started_at DESC, id DESC LIMIT 1`,
    sql`SELECT usd_idr FROM fx_rates ORDER BY date DESC LIMIT 1`,
  ]);
  const sessionDate = run ? ymd(run.session_date) : null;
  return {
    sessionDate,
    dataDate: run ? ymd(run.data_date) : null,
    finishedAt: run ? new Date(run.finished_at) : null,
    isDemo: run?.is_demo ?? false,
    stale: isStale(sessionDate, now),
    usdIdr: fx ? n(fx.usd_idr) : 16500,
    latestStatus: latest ? runState(latest.status) : null,
    paperStatus: latest ? runState(latest.paper_status) : null,
    paperError: latest?.paper_error ?? null,
    paperFinishedAt: latest?.paper_finished_at ? new Date(latest.paper_finished_at) : null,
  };
}

export type Pick = {
  id: number; slot: number; symbol: string; company: string; last: number;
  limit: number; tp: number; sl: number; shares: number; explanation: string | null;
};

/** The champion's pending bracket orders for one session (Today). Unchanged; returns [] for SPY. */
export async function picks(strategyId: string, sessionDate: string): Promise<Pick[]> {
  const rows = await sql`SELECT id, slot, symbol, company, last_price, limit_price, tp_price, sl_price, shares, explanation
    FROM orders WHERE strategy_id = ${strategyId} AND session_date = ${sessionDate} AND status = 'pending' ORDER BY slot`;
  return rows.map(r => ({
    id: n(r.id), slot: r.slot, symbol: r.symbol, company: r.company, last: n(r.last_price),
    limit: n(r.limit_price), tp: n(r.tp_price), sl: n(r.sl_price), shares: r.shares, explanation: r.explanation,
  }));
}

/** One open holding of any engine: a bracket order, a book position, or the SPY benchmark holding. */
export type Holding = {
  /** Unique across engines: 'o:<orders.id>' or 'b:<strategy>:<symbol>'. */
  key: string;
  kind: Engine;
  /** Bracket only: orders.id, for the day-5 "mark as done" action. */
  orderId: number | null;
  /** Bracket only: slot 1..4. */
  slot: number | null;
  symbol: string;
  /** Bracket orders carry a company name; book positions do not. */
  company: string | null;
  /** Whole shares for bracket; book shares are numeric(16,4). */
  shares: number;
  /** Bracket: fill price. Book: the episode's first entry price. */
  entry: number;
  entryDate: string | null;
  /** Mark: orders.mark (else the latest close, else the fill) for bracket; book_positions.mark for book. */
  current: number;
  /** Take profit: always set for bracket; for book only when the rules set one. */
  tp: number | null;
  /** Stop loss: always set for bracket; for book only when the rules set one. */
  sl: number | null;
  /** Sessions held, the fill session counting as 1. */
  day: number;
  /** 5 for bracket (time exit); null for book and benchmark holdings. */
  maxDays: number | null;
  /** shares x current. */
  value: number;
  /** value / the strategy's equity at its last snapshot; null when no equity is known. */
  weight: number | null;
  /** Bracket: (current - entry) x shares. Book: value + income - cost (fees and dividends included). */
  pnl: number;
  /** Bracket: current / entry - 1. Book: (value + income) / cost - 1. */
  pnlPct: number;
  /** Bracket day-5 action marked done. */
  dismissed: boolean;
  /** Book: a sell is decided and executes at the next open. */
  exitPending: boolean;
};

/** A strategy's open holdings: bracket orders (by days held, slot), then book positions (largest first). */
export async function positions(strategyId: string): Promise<Holding[]> {
  const [orders, book] = await Promise.all([
    sql`SELECT o.id, o.slot, o.symbol, o.company, o.shares, o.fill_date::text AS fill_date, o.fill_price,
        o.tp_price, o.sl_price, o.days_held, (d.order_id IS NOT NULL) AS dismissed,
        COALESCE(o.mark, (SELECT b.close FROM bars b WHERE b.symbol = o.symbol ORDER BY b.date DESC LIMIT 1), o.fill_price) AS mark,
        COALESCE((SELECT ps.equity_usd FROM paper_state ps WHERE ps.strategy_id = o.strategy_id),
          (SELECT e.equity_usd FROM equity_snapshots e WHERE e.strategy_id = o.strategy_id ORDER BY e.date DESC LIMIT 1)) AS equity
      FROM orders o LEFT JOIN action_dismissals d ON d.order_id = o.id
      WHERE o.strategy_id = ${strategyId} AND o.status = 'open' ORDER BY o.days_held DESC, o.slot`,
    sql`SELECT p.symbol, p.shares, p.mark, p.entry_date::text AS entry_date, p.entry_price, p.days_held, p.cost_usd, p.income_usd,
        p.stop_price, p.take_price, p.exit_pending, s.engine, s.is_benchmark,
        COALESCE((SELECT ps.equity_usd FROM paper_state ps WHERE ps.strategy_id = p.strategy_id),
          (SELECT e.equity_usd FROM equity_snapshots e WHERE e.strategy_id = p.strategy_id ORDER BY e.date DESC LIMIT 1)) AS equity
      FROM book_positions p JOIN strategies s ON s.id = p.strategy_id
      WHERE p.strategy_id = ${strategyId} ORDER BY p.shares * p.mark DESC, p.symbol`,
  ]);

  const bracket: Holding[] = orders.map(r => {
    const shares = n(r.shares), entry = n(r.fill_price), current = n(r.mark), equity = nn(r.equity);
    const value = shares * current;
    return {
      key: `o:${r.id}`, kind: 'bracket', orderId: n(r.id), slot: n(r.slot), symbol: r.symbol, company: r.company ?? null,
      shares, entry, entryDate: ymdOrNull(r.fill_date), current, tp: n(r.tp_price), sl: n(r.sl_price),
      day: n(r.days_held), maxDays: BRACKET_MAX_DAYS, value, weight: equity ? value / equity : null,
      pnl: (current - entry) * shares, pnlPct: entry > 0 ? current / entry - 1 : 0, dismissed: r.dismissed === true, exitPending: false,
    };
  });

  const held: Holding[] = book.map(r => {
    const engine = engineOf(r.engine, r.is_benchmark === true);
    const shares = n(r.shares), current = n(r.mark), cost = n(r.cost_usd), income = n(r.income_usd), equity = nn(r.equity);
    const value = shares * current;
    return {
      key: `b:${strategyId}:${r.symbol}`, kind: engine === 'benchmark' ? 'benchmark' : 'book', orderId: null, slot: null,
      symbol: r.symbol, company: null, shares, entry: n(r.entry_price), entryDate: ymdOrNull(r.entry_date), current,
      tp: nn(r.take_price), sl: nn(r.stop_price), day: n(r.days_held), maxDays: null, value,
      weight: equity ? value / equity : null, pnl: value + income - cost, pnlPct: cost > 0 ? (value + income) / cost - 1 : 0,
      dismissed: false, exitPending: r.exit_pending === true,
    };
  });

  return [...bracket, ...held];
}

/** One order or target a strategy has decided for its next session. */
export type PendingOrder = {
  /** 'o:<orders.id>' or 't:<strategy>:<session>:<symbol>'. */
  key: string;
  kind: 'bracket' | 'book';
  sessionDate: string;
  /** Bracket: the slot. Book: the target's rank (1 = best). */
  rank: number;
  slot: number | null;
  symbol: string;
  company: string | null;
  last: number;
  limit: number | null;
  tp: number | null;
  sl: number | null;
  /** Bracket: sized whole shares. Book: null (sized from the weight at the open). */
  shares: number | null;
  /** Book: target weight of equity, (0, 1]. Bracket: null. */
  weight: number | null;
  explanation: string | null;
};

export type Pending = {
  /** The session these are for: paper_state.pending_session, else the bracket orders' own session. */
  sessionDate: string | null;
  /** False when a book strategy's next session is not a decision session (it changes nothing), and for SPY. */
  decision: boolean;
  orders: PendingOrder[];
};

/** What a strategy will do at the next session: pending bracket orders, or a book decision's targets. */
export async function pendingOrders(strategyId: string): Promise<Pending> {
  const [[st], [ps], orders, targets] = await Promise.all([
    sql`SELECT engine, is_benchmark FROM strategies WHERE id = ${strategyId}`,
    sql`SELECT pending_session::text AS pending_session, pending_decision FROM paper_state WHERE strategy_id = ${strategyId}`,
    sql`SELECT id, session_date::text AS session_date, slot, symbol, company, last_price, limit_price, tp_price, sl_price,
        shares, explanation
      FROM orders WHERE strategy_id = ${strategyId} AND status = 'pending' ORDER BY session_date, slot`,
    sql`SELECT t.session_date::text AS session_date, t.rank, t.symbol, t.weight, t.last_price, t.limit_price,
        t.stop_price, t.take_price, t.explanation
      FROM paper_state ps JOIN book_targets t ON t.strategy_id = ps.strategy_id AND t.session_date = ps.pending_session
      WHERE ps.strategy_id = ${strategyId} AND ps.pending_decision ORDER BY t.rank`,
  ]);
  if (!st) return { sessionDate: null, decision: false, orders: [] };
  const engine = engineOf(st.engine, st.is_benchmark === true);
  const pendingSession = ps ? ymdOrNull(ps.pending_session) : null;

  if (engine === 'bracket') {
    const items: PendingOrder[] = orders.map(r => ({
      key: `o:${r.id}`, kind: 'bracket', sessionDate: ymd(r.session_date), rank: n(r.slot), slot: n(r.slot),
      symbol: r.symbol, company: r.company ?? null, last: n(r.last_price), limit: n(r.limit_price),
      tp: n(r.tp_price), sl: n(r.sl_price), shares: n(r.shares), weight: null, explanation: r.explanation ?? null,
    }));
    return { sessionDate: pendingSession ?? items[0]?.sessionDate ?? null, decision: true, orders: items };
  }
  if (engine === 'book') {
    const items: PendingOrder[] = targets.map(r => ({
      key: `t:${strategyId}:${ymd(r.session_date)}:${r.symbol}`, kind: 'book', sessionDate: ymd(r.session_date),
      rank: n(r.rank), slot: null, symbol: r.symbol, company: null, last: n(r.last_price), limit: nn(r.limit_price),
      tp: nn(r.take_price), sl: nn(r.stop_price), shares: null, weight: n(r.weight), explanation: r.explanation ?? null,
    }));
    return { sessionDate: pendingSession, decision: ps?.pending_decision === true, orders: items };
  }
  return { sessionDate: pendingSession, decision: false, orders: [] };
}

/** Bracket exits (design §5) plus the book engine's signal and forced exits. */
export type ExitReason = 'tp' | 'sl' | 'time' | 'gap' | 'signal' | 'forced';

export type Trade = {
  /** Unique across engines: 'o:<orders.id>' or 'b:<book_trades.id>'. */
  key: string;
  /** Row id within its own table (orders or book_trades): not unique across engines. */
  id: number;
  kind: 'bracket' | 'book';
  strategyId: string;
  /** 'A', 'F4', 'F1': the strategy's short label. */
  strategyShort: string;
  symbol: string;
  entry: number;
  exit: number;
  entryDate: string | null;
  exitDate: string;
  /** Bracket: whole shares. Book: null (book_trades keeps no share count). */
  shares: number | null;
  days: number | null;
  reason: ExitReason;
  pnl: number;
};

/** Closed trades of every engine (closed orders and non-idle book trades), newest first, at most 300. */
export async function closedTrades(strategyId: string | null, outcome: 'win' | 'loss' | null): Promise<Trade[]> {
  const rows = await sql`SELECT x.kind, x.id, x.strategy_id, s.name, s.id AS sid, x.symbol, x.entry_price, x.exit_price,
      x.entry_date::text AS entry_date, x.exit_date::text AS exit_date, x.shares, x.days_held, x.exit_reason, x.pnl_usd
    FROM (
      SELECT 'bracket' AS kind, o.id, o.strategy_id, o.symbol, o.fill_price AS entry_price, o.exit_price,
        o.fill_date AS entry_date, o.exit_date, o.shares::numeric AS shares, o.days_held, o.exit_reason, o.pnl_usd
      FROM orders o WHERE o.status = 'closed'
      UNION ALL
      SELECT 'book' AS kind, t.id, t.strategy_id, t.symbol, t.entry_price, t.exit_price,
        t.entry_date, t.exit_date, NULL::numeric AS shares, t.days_held, t.exit_reason, t.pnl_usd
      FROM book_trades t WHERE NOT t.idle
    ) x JOIN strategies s ON s.id = x.strategy_id
    WHERE (${strategyId}::text IS NULL OR x.strategy_id = ${strategyId})
      AND (${outcome}::text IS NULL OR (${outcome} = 'win') = (x.pnl_usd > 0))
    ORDER BY x.exit_date DESC, x.kind, x.id DESC LIMIT 300`;
  return rows.map(r => ({
    key: `${r.kind === 'book' ? 'b' : 'o'}:${r.id}`, id: n(r.id), kind: r.kind === 'book' ? 'book' : 'bracket',
    strategyId: r.strategy_id, strategyShort: shortLabel(r.name, r.sid), symbol: r.symbol,
    entry: n(r.entry_price), exit: n(r.exit_price), entryDate: ymdOrNull(r.entry_date), exitDate: ymd(r.exit_date),
    shares: nn(r.shares), days: nn(r.days_held), reason: r.exit_reason as ExitReason, pnl: n(r.pnl_usd),
  }));
}

/** Which closed-trade rows count for a strategy: closed orders (bracket), non-idle book trades (book), none (benchmark). */
const countsFor = (engine: Engine, src: unknown) => engine !== 'benchmark' && src === engine;

export type Board = {
  rows: { strategy: Strategy; metrics: Metrics; curve: Snapshot[] }[];
  from: string | null;
  to: string | null;
};

/** Every strategy's metrics over all its snapshots (day 0 included) and its own engine's closed trades. */
export async function leaderboard(): Promise<Board> {
  const [strats, snaps, pnls] = await Promise.all([
    strategies(),
    sql`SELECT strategy_id, date::text AS date, equity_usd FROM equity_snapshots ORDER BY date`,
    sql`SELECT 'bracket' AS src, strategy_id, pnl_usd FROM orders WHERE status = 'closed'
      UNION ALL SELECT 'book' AS src, strategy_id, pnl_usd FROM book_trades WHERE NOT idle`,
  ]);
  const rows = strats.map(strategy => {
    const curve = snaps.filter(s => s.strategy_id === strategy.id).map(s => ({ date: ymd(s.date), equity: n(s.equity_usd) }));
    const p = pnls.filter(t => t.strategy_id === strategy.id && countsFor(strategy.engine, t.src)).map(t => n(t.pnl_usd));
    return { strategy, metrics: strategyMetrics(curve, p), curve };
  });
  const dates = snaps.map(s => ymd(s.date));
  return { rows, from: dates[0] ?? null, to: dates[dates.length - 1] ?? null };
}

/**
 * Month-by-month paper performance of one strategy next to the benchmark (D5), for the
 * Leaderboard's monthly sheet. `sessionDate` is runStatus().sessionDate (marks the current month partial).
 */
export async function monthly(strategyId: string, sessionDate: string | null): Promise<MonthlyTable> {
  const strats = await strategies();
  const st = strats.find(x => x.id === strategyId);
  if (!st) return { months: [], sinceStart: null };
  const bench = strats.find(x => x.isBenchmark) ?? null;
  const none = Promise.resolve([] as Row[]);
  const [snaps, spy, exits] = await Promise.all([
    sql`SELECT date::text AS date, equity_usd FROM equity_snapshots WHERE strategy_id = ${st.id} ORDER BY date`,
    bench ? sql`SELECT date::text AS date, equity_usd FROM equity_snapshots WHERE strategy_id = ${bench.id} ORDER BY date` : none,
    st.engine === 'bracket'
      ? sql`SELECT exit_date::text AS exit_date FROM orders WHERE strategy_id = ${st.id} AND status = 'closed'`
      : st.engine === 'book'
        ? sql`SELECT exit_date::text AS exit_date FROM book_trades WHERE strategy_id = ${st.id} AND NOT idle`
        : none,
  ]);
  const toSnap = (r: Row): Snapshot => ({ date: ymd(r.date), equity: n(r.equity_usd) });
  return monthlyTable({
    snaps: snaps.map(toSnap),
    spy: bench ? spy.map(toSnap) : null,
    exitDates: exits.map(r => ymd(r.exit_date)),
    sessionDate,
  });
}

export async function dismissAction(orderId: number) {
  await sql`INSERT INTO action_dismissals (order_id) VALUES (${orderId}) ON CONFLICT DO NOTHING`;
}
```
**Impact:** `Holding` replaces `Position`, which breaks `page.tsx` and `positions/page.tsx` type-checking. `checklist` arity breaks `leaderboard/page.tsx`. All three are fixed in Step 10. `history/page.tsx` compiles unchanged: it still has `id`, and `REASON` is a `Record<string, …>` with a `?? REASON.time` fallback.

### Step 10: Minimal page compile fixes (and two safety guards)
Phases 11 and 12 rewrite these pages. This step only keeps `tsc --noEmit` green and stops two wrong messages that SPY-as-champion would otherwise show in between:
- Today telling the owner to "sell at market" their SPY on "day 65 of 5";
- the Leaderboard reading "All five pass. Ready for real money" at 5/6.

No CSS and no layout changes.

**File:** `web/app/(app)/page.tsx:26`
```tsx
  const actions = open.filter(p => p.orderId !== null && p.maxDays !== null && p.day >= p.maxDays && !p.dismissed);
```
**File:** `web/app/(app)/page.tsx:87`
```tsx
              <section key={a.key} className={`sheet over bg-coral ${s.action}`}>
```
**File:** `web/app/(app)/page.tsx:92`
```tsx
                    <input type="hidden" name="orderId" value={a.orderId ?? ''} />
```

**File:** `web/app/(app)/positions/page.tsx:16`
```tsx
  const exitsToday = open.filter(p => p.maxDays !== null && p.day >= p.maxDays).length;
```
**File:** `web/app/(app)/positions/page.tsx:42-43` (two lines become three)
```tsx
              const sl = q.sl ?? Math.min(q.entry, q.current), tp = q.tp ?? Math.max(q.entry, q.current);
              const range = tp - sl || 1;
              const at = (v: number) => Math.min(100, Math.max(0, ((v - sl) / range) * 100));
```
**File:** `web/app/(app)/positions/page.tsx:47`
```tsx
                <article key={q.key} className={`sheet over ${SLOT_BG[i % 4]} ${s.card}`}>
```
**File:** `web/app/(app)/positions/page.tsx:63`
```tsx
                    <div className={`num ${s.between}`} style={{ fontSize: 15 }}><span>Stop {q.sl === null ? '—' : usd(q.sl)}</span><span>Target {q.tp === null ? '—' : usd(q.tp)}</span></div>
```

**File:** `web/app/(app)/leaderboard/page.tsx:22`
```tsx
  const items = champ ? checklist(champ.metrics, spy?.metrics.totalReturn ?? null, champ.strategy.gate) : [];
```
**File:** `web/app/(app)/leaderboard/page.tsx:63-64`
```tsx
        <span className={s.scoreNum}>{passed}/{items.length || 6}</span>
        <span className={s.scoreText}>{items.length > 0 && passed === items.length ? <>All six pass.<br />Ready for real money</> : <>Paper trading until<br />all six pass</>}</span>
```
**Impact:** The pages type-check, and render as before on bracket data. On the new demo they render SPY (champion) with its single holding and no day-5 action. Phases 11 and 12 replace these pages entirely.

### Step 11: Demo seed in the paper shape
**File:** `web/scripts/seed-demo.mjs:1-152` (replace the whole file)
**Change:**
- **Roster.** The rows are the C1 display rows, with `engine`, `rules_id`, `paper_start` (= session 2 of 66) and `params` = `{ demo: true, spec, digest: null, backtest_gate: { passed: false, note } }`.
  - SPY is the champion and benchmark; B and C are gone.
  - The gate notes are phase 1's `roster.py` `gate_note` texts verbatim (reconciled), so the demo shows exactly what `paper` will write.
- **Sessions.** There are 66 weekday sessions ending at the last completed session. Session 1 is day 0 (initial cash, every strategy). Session 2 is the paper start. That covers about 92 days, so at least 3 calendar months and always at least two month starts. The seed asserts this.
- **SPY.** Whole shares at paper start's open, marked at a deterministic synthetic close path. Its snapshots are exactly cash + shares × close. One `book_positions` row (kind benchmark).
- **F1.** Cash until the first month start, then all-in SPY (whole shares, MONTHLY_HOLD has `fractional=False`). Snapshots are exact. There is a `book_targets` decision record (SPY, weight 1) for every month start. It has no trades, so it shows months with no trades.
- **F4.** Cash until the first month start, then a pinned random-walk curve. It holds 12 names priced under about $60, because MONTHLY_HOLD buys whole shares and 5% of about $1,210 is about $60. That is honest about the real account size.
  - Of the 12, 7 were held since the first decision and 5 bought at the last.
  - Trades: 5 `signal` exits at the last decision and 1 `forced` exit (WBA).
  - `book_targets` decision records exist for the first decision (ranks 1..13: the 7 early names, the 5 later sold, WBA) and the last (ranks 1..12).
  - Pending targets for the next session are written only when it is a month start.
- **A.** 3 pending orders for the next session (now "paper", shown by phase 11 in Positions, never on Today), 3 open orders with `mark`, and about 35 closed orders, all with fills on or after paper start. Equity is a pinned random walk.
- **`paper_state`.** One row per strategy: `last_session` = data date, `pending_session` = next session; `pending_decision` is true only for F4/F1 on a month start.
- **One demo run.** `status = 'success'`, `paper_status = 'success'`, `paper_finished_at = now()`.
- **TRUNCATE.** It now lists the new tables. The refusals are kept (real runs, real bars), plus one more: real `paper_state` with no demo run.
- **`--dry-run`.** Prints the dates, months, decisions and row counts without connecting.

Bars written: 7 rows (picks, open orders, SPY at the data date), so a re-seed still passes the `bars <= 100` refusal.
**Code:**
```js
// Fills Neon with demo data in the paper-trading shape (migration 003), flagged is_demo so the
// UI warns "Demo data". Dates are relative to now so the demo is never stale.
// Roster: SPY (champion, buy and hold), A (bracket), F4-MOM12-N20-TREND and F1-SPY-SMA200-M
// (monthly book strategies). 66 sessions ending at the last completed session: day 0 is the
// first, paper start the second, so the demo spans at least three calendar months.
// Refuses to run once the real engine has written a run, backfilled bars or started paper trading.
// `--dry-run` builds every row and prints the counts without connecting.
import { Pool, neonConfig } from '@neondatabase/serverless';
import ws from 'ws';

const DRY_RUN = process.argv.includes('--dry-run');

const RATE = 16530;
const START_USD = +(20_000_000 / RATE).toFixed(4);
const FEE = 0.001; // demo cost per side
const r2 = v => +v.toFixed(2);
const r4 = v => +v.toFixed(4);

// --- dates (ET calendar, weekdays only) -------------------------------------
const etNow = Object.fromEntries(new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', hourCycle: 'h23',
}).formatToParts(new Date()).map(p => [p.type, p.value]));
const addDays = (ymd, n) => { const d = new Date(`${ymd}T12:00:00Z`); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const weekend = ymd => [0, 6].includes(new Date(`${ymd}T12:00:00Z`).getUTCDay());
const nextWeekday = (ymd, dir) => { let d = addDays(ymd, dir); while (weekend(d)) d = addDays(d, dir); return d; };
const monthOf = ymd => ymd.slice(0, 7);

const today = `${etNow.year}-${etNow.month}-${etNow.day}`;
const session = !weekend(today) && +etNow.hour < 16 ? today : nextWeekday(today, 1);
const dataDate = nextWeekday(session, -1);
const sessions = [dataDate]; // 66 sessions ending at dataDate, oldest first
while (sessions.length < 66) sessions.unshift(nextWeekday(sessions[0], -1));
const LAST = sessions.length - 1;
const back = n => sessions[LAST - n]; // n sessions before dataDate
const DAY0 = sessions[0]; // initial cash snapshot (the session before paper start)
const PAPER_START = sessions[1];

// Monthly book strategies decide on the first session of a month (MONTHLY_HOLD).
const decisions = sessions.map((_, i) => i).filter(i => i >= 1 && monthOf(sessions[i]) !== monthOf(sessions[i - 1]));
if (decisions.length < 2) throw new Error('demo window must hold two month starts');
const FIRST_DECISION = decisions[0];
const LAST_DECISION = decisions[decisions.length - 1];
const pendingDecision = monthOf(session) !== monthOf(dataDate);

// --- deterministic randomness ------------------------------------------------
let seed = 7;
const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;

// --- roster (display rows as in migration 003; params as the `paper` command writes them) ---
const gate = note => ({ passed: false, note });
const strategies = [
  { id: 'SPY', name: 'SPY', sub: 'S&P 500, buy and hold', icon: 'landmark', champion: true, benchmark: true, sort: 1,
    engine: 'benchmark', rulesId: null,
    params: { demo: true, spec: { engine: 'benchmark', symbol: 'SPY' }, digest: null,
      backtest_gate: gate('Benchmark, not a strategy: it has no backtest gate and is never a Seer pick') } },
  { id: 'A', name: 'A · Quant', sub: 'Mean reversion, 5-day brackets', icon: 'sigma', champion: false, benchmark: false, sort: 2,
    engine: 'bracket', rulesId: 'design-v0',
    params: { demo: true, spec: { engine: 'bracket', object: 'STRATEGY_A', rules_id: 'design-v0' }, digest: null,
      backtest_gate: gate('P3 gate failed out of sample (2022-01-03..2026-10-02): -15.0% vs SPY TR +71.9%, PF 0.92, max DD 33.3%') } },
  { id: 'F4-MOM12-N20-TREND', name: 'F4 · Momentum', sub: 'Top 20 by 12-1 momentum, monthly', icon: 'trending-up', champion: false, benchmark: false, sort: 3,
    engine: 'book', rulesId: 'monthly-hold',
    params: { demo: true, spec: { engine: 'book', object: 'FACTOR', registry_id: 'F4-MOM12-N20-TREND', rules_id: 'monthly-hold' }, digest: null,
      backtest_gate: gate('P7a dev window only; failed max DD <= 15% (22.2%)') } },
  { id: 'F1-SPY-SMA200-M', name: 'F1 · Trend', sub: 'SPY above its 200-day average, monthly', icon: 'shield', champion: false, benchmark: false, sort: 4,
    engine: 'book', rulesId: 'monthly-hold',
    params: { demo: true, spec: { engine: 'book', object: 'TIMING', registry_id: 'F1-SPY-SMA200-M', rules_id: 'monthly-hold' }, digest: null,
      backtest_gate: gate('P7a dev window only; failed max DD <= 15% (18.7%) and >= 100 trades (11)') } },
];

// --- SPY closes, one per session ---------------------------------------------
const spy = [];
for (let i = 0, px = 562; i <= LAST; i++) { px *= 1 + (rnd() - 0.46) * 0.014; spy.push(r2(px)); }
const openOf = i => r2(spy[i - 1] * (1 + (rnd() - 0.5) * 0.004)); // session i's open, near the prior close

const snapshots = []; // [strategy, date, cash, equity]
const paperState = []; // [strategy, cash, equity, pendingDecision]
const bookPositions = []; // [strategy, symbol, shares, mark, entryDate, entryPrice, daysHeld, cost, income, stop, take, exitPending]
const bookTargets = []; // [strategy, session, rank, symbol, weight, last, limit, stop, take, explanation]
const bookTrades = []; // [strategy, symbol, entryDate, exitDate, entryPrice, exitPrice, daysHeld, cost, income, pnl, reason]

// --- SPY: whole shares at paper start's open, held, marked at each close -------
{
  const entry = openOf(1);
  const shares = Math.floor(START_USD / (entry * (1 + FEE)));
  const cost = r4(shares * entry * (1 + FEE));
  const cash = r4(START_USD - cost);
  snapshots.push(['SPY', DAY0, START_USD, START_USD]);
  for (let i = 1; i <= LAST; i++) snapshots.push(['SPY', sessions[i], cash, r4(cash + shares * spy[i])]);
  bookPositions.push(['SPY', 'SPY', shares, spy[LAST], PAPER_START, entry, LAST, cost, 0, null, null, false]);
  paperState.push(['SPY', cash, r4(cash + shares * spy[LAST]), false]);
}

// --- F1: cash until the first month start, then all-in SPY (whole shares) -----
{
  const id = 'F1-SPY-SMA200-M';
  const entry = openOf(FIRST_DECISION);
  const shares = Math.floor(START_USD / (entry * (1 + FEE)));
  const cost = r4(shares * entry * (1 + FEE));
  const cash = r4(START_USD - cost);
  for (let i = 0; i <= LAST; i++)
    snapshots.push(i < FIRST_DECISION ? [id, sessions[i], START_USD, START_USD] : [id, sessions[i], cash, r4(cash + shares * spy[i])]);
  bookPositions.push([id, 'SPY', shares, spy[LAST], sessions[FIRST_DECISION], entry, LAST - FIRST_DECISION + 1, cost, 0, null, null, false]);
  const why = 'SPY closed above its 200-day average, so F1 holds SPY for the month.';
  for (const d of decisions) bookTargets.push([id, sessions[d], 1, 'SPY', 1, spy[d - 1], null, null, null, why]);
  if (pendingDecision) bookTargets.push([id, session, 1, 'SPY', 1, spy[LAST], null, null, null, why]);
  paperState.push([id, cash, r4(cash + shares * spy[LAST]), pendingDecision]);
}

// --- equity curve: random walk pinned to a target return, flat before `from` ---
const curve = (target, vol, from = 1) => {
  const w = [0];
  for (let i = 1; i <= LAST; i++) w.push(w[i - 1] + (rnd() - 0.5) * vol);
  const span = LAST - from;
  return sessions.map((_, i) => {
    if (i < from) return START_USD;
    const k = i - from;
    const wk = w[i] - w[from];
    const wn = w[LAST] - w[from];
    return r4(START_USD * (1 + (wk - wn * k / span + target * 100 * k / span) / 100));
  });
};

// --- F4: 12 names (MONTHLY_HOLD buys whole shares, so names over ~$60 do not fit) ------
{
  const id = 'F4-MOM12-N20-TREND';
  const eq = curve(0.031, 2.4, FIRST_DECISION);
  const E = eq[LAST];
  // [symbol, mark, held since the first decision?]
  const HELD = [['INTC', 36.42, true], ['PFE', 25.08, false], ['F', 11.31, true], ['T', 27.64, true], ['BAC', 47.18, false],
    ['WBD', 12.37, true], ['KMI', 27.93, false], ['HPE', 22.46, true], ['CMCSA', 32.81, false], ['CSX', 33.57, true],
    ['CCL', 28.44, false], ['HBAN', 16.72, true]];
  let invested = 0;
  HELD.forEach(([sym, mark, early], rank) => {
    const from = early ? FIRST_DECISION : LAST_DECISION;
    const entry = r2(mark / (1 + (rnd() - 0.4) * 0.15));
    const shares = Math.max(1, Math.floor((0.05 * E) / mark));
    invested += shares * mark;
    bookPositions.push([id, sym, shares, mark, sessions[from], entry, LAST - from + 1, r4(shares * entry * (1 + FEE)), 0, null, null, false]);
    bookTargets.push([id, sessions[LAST_DECISION], rank + 1, sym, 0.05, r2(mark * (1 + (rnd() - 0.5) * 0.04)), null, null, null,
      rank === 0 ? `${sym} ranks first by 12-1 momentum among index members, and SPY is above its 200-day average.` : null]);
    if (pendingDecision) bookTargets.push([id, session, rank + 1, sym, 0.05, mark, null, null, null, null]);
  });
  // The first decision's targets: the early names, five sold at the last decision (their rank
  // fell), and one closed by force when it left the index and its bars stopped.
  const firstTargets = HELD.filter(([, , early]) => early).map(([sym, mark]) => [sym, r2(mark * 0.97)]);
  const SOLD = [['KEY', 18.2], ['RF', 25.3], ['NCLH', 24.1], ['KHC', 26.4], ['VZ', 41.7]];
  for (const [sym, en] of SOLD) {
    const ex = r2(en * (1 + (rnd() - 0.55) * 0.16));
    const shares = Math.max(1, Math.floor((0.05 * START_USD) / en));
    const cost = r4(shares * en * (1 + FEE)), income = r4(shares * ex * (1 - FEE));
    firstTargets.push([sym, en]);
    bookTrades.push([id, sym, sessions[FIRST_DECISION], sessions[LAST_DECISION], en, ex, LAST_DECISION - FIRST_DECISION + 1, cost, income, r4(income - cost), 'signal']);
  }
  {
    const at = Math.min(LAST - 1, FIRST_DECISION + 12);
    const en = 10.9, ex = 10.25, shares = Math.floor((0.05 * START_USD) / en);
    const cost = r4(shares * en * (1 + FEE)), income = r4(shares * ex * (1 - FEE));
    firstTargets.push(['WBA', en]);
    bookTrades.push([id, 'WBA', sessions[FIRST_DECISION], sessions[at], en, ex, at - FIRST_DECISION + 1, cost, income, r4(income - cost), 'forced']);
  }
  firstTargets.forEach(([sym, last], k) => bookTargets.push([id, sessions[FIRST_DECISION], k + 1, sym, 0.05, last, null, null, null, null]));
  const cashShare = Math.max(0, 1 - invested / E);
  eq.forEach((e, i) => snapshots.push([id, sessions[i], i < FIRST_DECISION ? e : r4(e * cashShare), e]));
  paperState.push([id, r4(E - invested), E, pendingDecision]);
}

// --- A: bracket orders ---------------------------------------------------------
const picks = [
  [1, 'GE', 'GE Aerospace', 273.18, 271.40, 278.90, 260.15, 1,
    'GE fell three days in a row and now sits below its usual range, while its longer trend is still up. Strategy A buys short dips like this when they have usually recovered within a week. The limit is a little under the last price, so it only buys if the price dips further at the open.'],
  [2, 'LRCX', 'Lam Research', 99.64, 98.20, 102.10, 92.35, 3,
    'Chip-equipment stocks sold off and Lam Research dropped more than its peers without news of its own. Past drops of this size have tended to win back part of the move within five sessions. The stop sits below last month’s low.'],
  [3, 'CSCO', 'Cisco Systems', 67.42, 66.85, 68.30, 64.70, 4,
    'Cisco is a steady, slow-moving stock that slipped to the bottom of its two-week range. The target is modest because Cisco rarely moves far. Four shares keep the possible loss in line with the other picks.'],
];

// [symbol, company, shares, entry, current, tp, sl, days held]
const open = [
  ['NVDA', 'Nvidia', 1, 184.20, 186.95, 190.60, 176.80, 5],
  ['AMZN', 'Amazon', 2, 221.50, 218.10, 228.90, 212.40, 3],
  ['KO', 'Coca-Cola', 3, 69.40, 70.05, 71.20, 67.30, 1],
];

// The design's history rows first: [symbol, entry, exit, shares, reason, sessions ago]
const named = [
  ['MSFT', 412.30, 421.10, 1, 'tp', 0], ['JPM', 298.15, 300.02, 2, 'time', 1],
  ['HD', 401.80, 409.90, 1, 'tp', 4], ['COST', 912.00, 908.40, 1, 'time', 6],
];
const POOL = [['AAPL', 'Apple', 231], ['META', 'Meta Platforms', 610], ['GOOGL', 'Alphabet', 188], ['ABBV', 'AbbVie', 192],
  ['PEP', 'PepsiCo', 151], ['WMT', 'Walmart', 98], ['QCOM', 'Qualcomm', 167], ['TXN', 'Texas Instruments', 201],
  ['CAT', 'Caterpillar', 389], ['UNH', 'UnitedHealth', 512], ['ORCL', 'Oracle', 176], ['ADBE', 'Adobe', 462],
  ['MRK', 'Merck', 96], ['CVX', 'Chevron', 152], ['BA', 'Boeing', 171], ['NKE', 'Nike', 78]];
const company = Object.fromEntries([...POOL.map(([s, c]) => [s, c]),
  ['MSFT', 'Microsoft'], ['JPM', 'JPMorgan Chase'], ['HD', 'Home Depot'], ['COST', 'Costco']]);

// Closed trades: exits within the paper window (fills at least three sessions after paper start).
const closed = named.map(([sym, en, ex, sh, reason, ago]) => ({ sym, en, ex, sh, reason, exitDate: back(ago) }));
{
  const [n, w, pf] = [38, 0.53, 1.12];
  const cost = 0.002, avgWin = 0.022; // round-trip cost; losses sized so the net profit factor ≈ target
  const avgLoss = (w * (avgWin - cost)) / ((1 - w) * pf) - cost;
  for (let i = closed.length; i < n; i++) {
    const [sym, , base] = POOL[Math.floor(rnd() * POOL.length)];
    const win = rnd() < w;
    const en = r2(base * (0.9 + rnd() * 0.2));
    const move = (win ? avgWin : -avgLoss) * (0.6 + rnd() * 0.8);
    const reason = win ? (rnd() < 0.8 ? 'tp' : 'time') : (rnd() < 0.7 ? 'sl' : rnd() < 0.5 ? 'time' : 'gap');
    closed.push({ sym, en, ex: r2(en * (1 + move)), sh: Math.max(1, Math.floor(300 / en)), reason, exitDate: back(7 + Math.floor(rnd() * 52)) });
  }
}
{
  const eq = curve(0.021, 3.3);
  const held = open.reduce((a, [, , sh, , cur]) => a + sh * cur, 0);
  eq.forEach((e, i) => snapshots.push(['A', sessions[i], i === 0 ? e : r4(e - (i === LAST ? held : 0)), e]));
  paperState.push(['A', r4(eq[LAST] - held), eq[LAST], false]);
}

const rows = { strategies, snapshots, paperState, bookPositions, bookTargets, bookTrades, picks, open, closed };

if (DRY_RUN) {
  const months = [...new Set(sessions.map(monthOf))];
  console.log(`dry run: day 0 ${DAY0}, paper start ${PAPER_START}, data ${dataDate}, session ${session}`);
  console.log(`months ${months.join(', ')}; decisions ${decisions.map(i => sessions[i]).join(', ')}; pending decision ${pendingDecision}`);
  console.log(Object.fromEntries(Object.entries(rows).map(([k, v]) => [k, v.length])));
  process.exit(0);
}

// --- write ---------------------------------------------------------------------
neonConfig.webSocketConstructor = ws;
const pool = new Pool({ connectionString: process.env.DATABASE_URL_UNPOOLED });
const c = await pool.connect();
try {
  const real = await c.query('SELECT count(*)::int AS n FROM runs WHERE NOT is_demo');
  if (real.rows[0].n > 0) throw new Error('Real engine runs exist; refusing to overwrite with demo data.');
  const bars = await c.query('SELECT count(*)::int AS n FROM bars');
  if (bars.rows[0].n > 100) throw new Error('Real bars exist (backfill ran); refusing to overwrite with demo data.');
  const paper = await c.query('SELECT count(*)::int AS n FROM paper_state WHERE NOT EXISTS (SELECT 1 FROM runs WHERE is_demo)');
  if (paper.rows[0].n > 0) throw new Error('Real paper state exists; refusing to overwrite with demo data.');

  await c.query('BEGIN');
  await c.query(`TRUNCATE action_dismissals, orders, equity_snapshots, bars, fx_rates, runs, paper_state, book_positions,
    book_targets, book_fills, book_trades, dividends, strategies RESTART IDENTITY CASCADE`);

  for (const s of strategies)
    await c.query(`INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id, paper_start, params)
      VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)`,
    [s.id, s.name, s.sub, s.icon, s.champion, s.benchmark, s.sort, s.engine, s.rulesId, PAPER_START, JSON.stringify(s.params)]);

  await c.query(`INSERT INTO runs (started_at, finished_at, status, data_date, session_date, is_demo, paper_status, paper_finished_at)
    VALUES (now() - interval '5 minutes', now() - interval '2 minutes', 'success', $1, $2, true, 'success', now())`, [dataDate, session]);
  await c.query('INSERT INTO fx_rates (date, usd_idr) VALUES ($1, $2)', [dataDate, RATE]);

  for (const [slot, sym, name, last, lim, tp, sl, sh, why] of picks) {
    await c.query(`INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, limit_price, tp_price, sl_price, shares, explanation, status)
      VALUES ('A',$1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'pending')`, [session, slot, sym, name, last, lim, tp, sl, sh, why]);
    await c.query('INSERT INTO bars VALUES ($1,$2,$3,$3,$3,$3,1000000)', [sym, dataDate, last]);
  }

  for (const [i, [sym, name, sh, entry, cur, tp, sl, days]] of open.entries()) {
    const fill = back(days - 1);
    await c.query(`INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, limit_price, tp_price, sl_price, shares, status, fill_date, fill_price, days_held, mark)
      VALUES ('A',$1,$2,$3,$4,$5,$5,$6,$7,$8,'open',$1,$5,$9,$10)`, [fill, i + 1, sym, name, entry, tp, sl, sh, days, cur]);
    await c.query('INSERT INTO bars VALUES ($1,$2,$3,$3,$3,$3,1000000)', [sym, dataDate, cur]);
  }
  await c.query('INSERT INTO bars VALUES ($1,$2,$3,$3,$3,$3,1000000)', ['SPY', dataDate, spy[LAST]]);

  for (const t of closed) {
    const pnl = (t.ex - t.en) * t.sh - FEE * (t.ex + t.en) * t.sh;
    const filled = nextWeekday(t.exitDate, -3);
    const tp = t.reason === 'tp' ? t.ex : r2(t.en * 1.025);
    const sl = t.reason === 'sl' ? t.ex : r2(t.en * 0.96);
    await c.query(`INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, limit_price, tp_price, sl_price, shares, status,
        fill_date, fill_price, days_held, exit_date, exit_price, exit_reason, pnl_usd)
      VALUES ('A',$1,1,$2,$3,$4,$4,$5,$6,$7,'closed',$1,$4,3,$8,$9,$10,$11) ON CONFLICT DO NOTHING`,
    [filled, t.sym, company[t.sym], t.en, tp, sl, t.sh, t.exitDate, t.ex, t.reason, pnl.toFixed(4)]);
  }

  for (const r of snapshots) await c.query('INSERT INTO equity_snapshots (strategy_id, date, cash_usd, equity_usd) VALUES ($1,$2,$3,$4)', r);

  for (const [id, cash, equity, decision] of paperState)
    await c.query(`INSERT INTO paper_state (strategy_id, last_session, cash_usd, equity_usd, initial_cash_usd, usd_idr, pending_session, pending_decision)
      VALUES ($1,$2,$3,$4,$5,$6,$7,$8)`, [id, dataDate, cash, equity, START_USD, RATE, session, decision]);

  for (const r of bookPositions)
    await c.query(`INSERT INTO book_positions (strategy_id, symbol, shares, mark, entry_date, entry_price, days_held, cost_usd, income_usd,
        stop_price, take_price, exit_pending) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)`, r);

  for (const r of bookTargets)
    await c.query(`INSERT INTO book_targets (strategy_id, session_date, rank, symbol, weight, last_price, limit_price, stop_price, take_price, explanation)
      VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)`, r);

  for (const r of bookTrades)
    await c.query(`INSERT INTO book_trades (strategy_id, symbol, entry_date, exit_date, entry_price, exit_price, days_held, cost_usd, income_usd,
        pnl_usd, exit_reason) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)`, r);

  await c.query('COMMIT');
  const counts = await c.query(`SELECT 'orders ' || status AS what, count(*)::int AS n FROM orders GROUP BY status
    UNION ALL SELECT 'book_positions', count(*)::int FROM book_positions
    UNION ALL SELECT 'book_trades', count(*)::int FROM book_trades
    UNION ALL SELECT 'equity_snapshots', count(*)::int FROM equity_snapshots ORDER BY what`);
  console.log(`demo seeded: paper start ${PAPER_START}, session ${session}, data ${dataDate}`, counts.rows);
} catch (e) {
  await c.query('ROLLBACK').catch(() => {});
  throw e;
} finally {
  c.release();
  await pool.end();
}
```
**Impact:**
- `npm run db:seed-demo` needs migration `003` applied first (`npm run db:migrate`).
- The seeded `strategies` rows carry `paper_start` and `params`. `demo.purge_demo` keeps the `strategies` rows but resets those two columns (phase 1, reconciled), so the first real `paper` run after a purge starts the clock cleanly.

## Verification

**Build:** `cd web && npm ci && npx tsc --noEmit` (clean).
**Tests:** `cd web && npx vitest run`: 7 files, 44 tests, all passing:
- `monthly` 14;
- `metrics` 7;
- `strategy` 5;
- `slots` 3;
- unchanged `allow`, `format`, `session`.

Invariant 1 also asks for the engine suite. This phase touches no engine code, so `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q` is unaffected; run it anyway to confirm 0 skipped.
**Seed checks:**
- `cd web && node scripts/seed-demo.mjs --dry-run` prints:
  - day 0 and the paper start;
  - at least 3 months;
  - at least 2 decisions;
  - counts: `strategies: 4, snapshots: 264, paperState: 4, bookPositions: 14, bookTargets: 28, bookTrades: 6` on a date whose next session is not a month start. `bookTargets` is one F1 row per month start in the window, plus 13 more when the next session is a month start.
- Optional, against a scratch Neon branch or local Postgres with `001`–`003` applied: `npm run db:migrate && npm run db:seed-demo`, then `npm run dev`. The existing pages render: Today shows SPY as champion with no picks and no day-5 action; Positions shows the SPY holding; History shows A and F4 trades; Leaderboard shows four strategies and "0/6" or similar for SPY.
**Manual check:** None needed for the redesign; phases 11 and 12 own the screens.
**Exit criteria:**
- vitest is green, including the monthly fixture (month boundaries, partial first and current months, a no-trade month, SPY on the same dates);
- `tsc --noEmit` is clean;
- `seed-demo.mjs --dry-run` succeeds;
- the existing pages still compile.

## Handoffs

1. **Phase 1 (or 7): demo purge must clear the seeded paper clock (risk, important).**
   - `engine/src/seer_engine/demo.py` keeps `strategies` when it purges.
   - The new seed writes `strategies.paper_start` and `params` (with `digest: null`, `demo: true`) on the roster rows.
   - C2 says a row with `paper_start` set and a digest that differs from the code's is a hard error in `paper`. So after a demo seed, the first real `paper` run would refuse to start.

   Reconciled: phase 1's `purge_demo` runs `UPDATE strategies SET paper_start = NULL, params = '{}'` whenever it purges (plan index Decisions, "Demo purge vs paper clock"). The seed may therefore write `paper_start` and `params` freely; phase 7 keeps its frozen-spec refusal unchanged.
2. **Phase 1: `DEMO_TABLES` must include** `paper_state`, `book_positions`, `book_targets`, `book_fills`, `book_trades` (the seed writes the first four book/state tables). `dividends` is not written by the seed, but the seed truncates it.
3. **Phase 1: gate note texts.** Done in reconciliation: the seed's `backtest_gate.note` strings are phase 1's `RosterEntry.gate_note` texts verbatim.
4. **Phase 11** consumes:
   - `Holding` (`kind`, `orderId`, `maxDays`, `weight`, `pnl`, `pnlPct`, `exitPending`, nullable `tp`/`sl`/`company`);
   - `pendingOrders()` / `Pending` (`decision: false` means "no decision until the next month start");
   - `Trade.key`, `Trade.strategyShort` and the widened `ExitReason` (icons needed for `signal` and `forced`);
   - `Strategy.isPaper` / `short` / `engine` for the switcher and the paper chip;
   - `RunStatus.paperStatus` / `paperError` / `latestStatus` for the paper-step warning;
   - `slotCount(engine)` / `cardBg(slot, i)`.

   It also replaces Step 10's stop-gap edits in `page.tsx` and `positions/page.tsx`.
5. **Phase 12** consumes:
   - `monthly(strategyId, run.sessionDate)` -> `MonthlyTable` (months oldest first; reverse it for newest-first display);
   - `checklist(metrics, spyReturn, strategy.gate)` with 6 items, where item 6 may carry `note`.

   The checklist should be shown per research strategy, not for the champion SPY, whose gate is "not a candidate". Phase 12 also replaces Step 10's stop-gap edits in `leaderboard/page.tsx`.
6. **Phase 13: apply `003` to Neon before `vercel deploy`.** Every `data.ts` query now reads 003 columns, so the deployed web fails against a pre-003 database.
7. **Book `company` names.** `book_positions` and `book_targets` have no company column, so `Holding.company` and `PendingOrder.company` are `null` for book rows. If phase 11 wants names, it needs a source (a later phase or a lookup table). That is out of this phase.

## Rollback

`git revert` the phase commit. It restores:
- the old `data.ts`, `metrics.ts`, `slots.ts` and seed;
- the old page lines.

It also removes the three new lib files and the three new tests. No schema or engine change is involved. A demo database seeded with the new seed keeps working with the old web, apart from the B/C strategies being absent. Re-run the old seed only on a database without `003`'s new tables referenced: the old seed's TRUNCATE does not list them, but `CASCADE` from `strategies` covers them.
