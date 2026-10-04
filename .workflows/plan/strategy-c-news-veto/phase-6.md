# Phase 6: Web: C everywhere, Vetoed tonight, D9 row, demo seed

**Plan set:** `STRATEGY_C_NEWS_VETO_PLAN.md`
**Analysis:** `20261004-171449-C5V8_code_analyzer.md`
**Spec:** `docs/handover/2026-10-04-strategy-c-news-veto.md` (D1, D9, D10; §5 item 6)
**Satisfies:** R4 — C shows in every roster view, Positions gets "Vetoed tonight", the checklist reads the D9 row, the demo seed has a C portfolio with verdicts
**Depends on:** Phase 2 (migration `004_news_veto.sql`: the `C` strategies row and the `news_vetoes` table, K2)
**Difficulty:** HARD
**Package:** `web`

---

## Goal

After this phase the web app treats C like any roster strategy (switchers, History filter, Leaderboard
cards and chart, Month by month) with its own look (butter sheet, coral line), its go-live checklist
reads row 6 as "Backtest gate · Not applicable" (never counted as passed) with the score line
"Paper only. No backtest gate. / Real money needs an owner decision", and Positions for C shows a
"Vetoed tonight" sheet under its paper orders listing vetoed and failed candidates (symbol, verdict chip,
reason via `WhyToggle`, headline count, earnings date), "n checked · k allowed", and the empty and
all-failed states. The demo seed builds a C portfolio on its own younger clock plus six verdict rows
for the pending session. Today is unchanged.

Every code block below was built and verified in a scratch copy of `web/` (see Verification): vitest
83/83 after reconciliation (82/82 as planned; 65 before), `tsc --noEmit` clean, seed applied onto a local database migrated 001–004 (with
the K2 SQL as 004), and Positions, Leaderboard, History and Today rendered at 414 px and 1440 px,
light and dark, against that seeded data.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing. (`CARD_BGS`/`LINES` keep their names; they gain a 4th entry.)
**Creates:**
- `web/lib/vetoes.ts` (new): `type Verdict = 'allow' | 'veto' | 'failed'`; `type Veto = { rank; symbol; verdict; reason; headlineCount; earningsDate: string | null; decidedAt: string }` (exactly K8's shape); `parseVerdict(v: unknown): Verdict` (unknown → `'failed'`); `type VetoSheet` (`missing` | `failed` | `listed`); `vetoSheet(rows: Veto[]): VetoSheet`; `checkedLine(checked, allowed)`; `headlinesLabel(k)`; `noCheckLine(day, short)` (the neutral no-rows line, reconciliation decision).
- `web/lib/vetoes.test.ts` (new).
- `web/lib/data.ts`: `vetoes(strategyId: string, sessionDate: string): Promise<Veto[]>` (all verdicts, by rank; `headlineCount = jsonb_array_length(headlines)`); re-exports `type Veto, Verdict`; `Strategy.checksNews: boolean`.
- `web/lib/strategy.ts`: `checksNews(id: string, specObject: unknown): boolean` (`specObject === 'STRATEGY_C' || id === 'C'`).
- `web/lib/metrics.ts`: `gateItem(gate: Gate): CheckItem` (row 6 on its own).
- `web/app/(app)/leaderboard/view.ts`: `type GateIn = { passed: boolean; applicable: boolean }`, `NO_GATE`, `monthsBg(look: Look): string`.
**Signature changes:**
- `type Gate = { passed: boolean; note: string | null }` → `{ passed: boolean; applicable: boolean; note: string | null }` (K8). `parseGate` reads `applicable = raw.applicable !== false`; a not-applicable gate always reads `passed: false`.
- `scoreOf(items, gatePassed: boolean)` → `scoreOf(items, gate: GateIn)` (K8). Not applicable → `ready: false`, lines `['Paper only. No backtest gate.', 'Real money needs an owner decision']`.
- `checklist(m, spy, gate)` signature unchanged; row 6 for a not-applicable gate is `{ label: 'Backtest gate', val: 'Not applicable', ok: false, note }` (K8).
- `WhyToggle({ text })` → `WhyToggle({ text, label?, missing? })` (optional, defaults keep Today byte-identical in behaviour).
**Requires (from earlier phases):**
- Phase 2: `db/migrations/004_news_veto.sql` exactly as K2 (the `C` row: name `C · News veto`, sub `A's picks, LLM can veto on news`, icon `gavel`, sort 5, engine `bracket`, rules `design-v0`; table `news_vetoes` with columns `strategy_id, session_date, rank, symbol, verdict, reason, model, prompt_version, headlines jsonb, earnings_date, decided_at`).
- Phase 2 (K4): `backtest_gate(C) == {"passed": false, "applicable": false, "note": "Backtest gate: not applicable (LLM strategy, design §1 item 5)"}`, and C's spec has `"object": "STRATEGY_C"` (`object_name`).
- Phase 4 (K6) writes `news_vetoes` rows for `run_dates(now).session_date`, which is the session `paper_state.pending_session` names for C after `paper` runs — the web reads verdicts for that session. No code dependency (phase 6 builds and tests without phase 4).
**Leaves alone (owned by others):** `engine/**`, `db/migrations/**` (phase 2), `.github/workflows/nightly.yml`, `docs/**`, `engine/package_readme.md`, `.env.example` (phase 7). `web/package_readme.md` is under `web/**` and therefore **this** phase's (Step 16). `web/app/(app)/page.tsx` (Today) is not edited.

## Files

| File | Action | What changes |
|---|---|---|
| `web/lib/strategy.ts` | replace | `Gate.applicable`, `parseGate`, new `checksNews` |
| `web/lib/strategy.test.ts` | replace | gate cases incl. not applicable; `checksNews`; `C · News veto` short label |
| `web/lib/metrics.ts` | replace | `gateItem` (row 6, not-applicable variant), used by `checklist` |
| `web/lib/metrics.test.ts` | replace | `applicable` in fixtures; D9 row cases |
| `web/lib/vetoes.ts` | create | `Veto`, `Verdict`, `parseVerdict`, `vetoSheet`, labels incl. `noCheckLine` |
| `web/lib/vetoes.test.ts` | create | sheet states and labels |
| `web/lib/data.ts` | modify (l.1–7, 20–39, 41–65, after 280) | `checksNews` field + `spec_object` column; `vetoes()` |
| `web/app/(app)/leaderboard/view.ts` | replace | 4th look (butter / coral), `monthsBg`, `GateIn`, `NO_GATE`, `scoreOf(items, gate)` |
| `web/app/(app)/leaderboard/view.test.ts` | replace | C in the roster fixture; looks, monthsBg, scoreOf cases |
| `web/app/(app)/leaderboard/page.tsx` | modify (l.11–14, 42, 135, 173) | `scoreOf(items, gate ?? NO_GATE)`, `monthsBg`, up to 5 card columns |
| `web/app/(app)/positions/page.tsx` | replace | read verdicts for news strategies; `VetoedTonight`, `VetoRow`; `noOrders` for C |
| `web/app/(app)/positions/positions.module.css` | replace | `.vetoes`, `.vetoHead`, `.vetoCount`, `.vetoReason`, `.vetoGap`, `.vetoFacts`, `.vetoChip`, `.failChip`; desktop `.vetoes` |
| `web/components/WhyToggle.tsx` | replace | optional `label`, `missing` props |
| `web/components/roster.ts` | modify (l.3–4) | comment: gavel is C's icon (code unchanged; `gavel` already mapped) |
| `web/components/roster.test.ts` | replace | C row; `gavel` → `Gavel` |
| `web/package_readme.md` | modify | Step 16: `lib/vetoes.ts`, `vetoes()`, `Strategy.checksNews`, `Gate.applicable`, `checksNews`, `gateItem`, `scoreOf(items, gate)`, the seed's C rows and its need for 004 |
| `web/scripts/seed-demo.mjs` | replace | C roster row + gate, C's own clock, bracket writes parameterised by id, C's pending/open/closed orders + snapshots + paper_state, six `news_vetoes` rows, `news_vetoes` in the TRUNCATE |

17 files (2 new). History (`app/(app)/history/page.tsx`) and the switchers need no change: they are
roster-driven (`strategies()` + `StrategySwitch` + `strategyIcon('gavel')`), so C appears once 004's row exists.

## Design decisions (this phase)

| Question | Decision | Why |
|---|---|---|
| C's Leaderboard look | `bg-butter` sheet + `var(--coral)` line (4th entry of `CARD_BGS`/`LINES`) | Seer v2's sheet palette is lav/butter/sky/stone (`SLOT_BG` in the design); lav/sky/stone are taken by A/F4/F1 in roster order. Coral is the design's accent token, distinct from ink (A), line-b (F4), line-c (F1) and the dotted ink-3 benchmark in both themes. The design's own C row used stone/line-c, but F1 holds those now |
| Month-by-month sheet for C | `monthsBg(look)`: butter → `bg-stone` | On mobile the months sheet slides under the butter checklist sheet; two butter sheets merge into one. White would merge with the SPY card below |
| Card columns at desktop | `--cols` cap 4 → 5 | Five roster rows: one row of five instead of four plus a lone card (verified at 1440 px) |
| Which strategies read verdicts | `Strategy.checksNews` (`spec.object === 'STRATEGY_C'` or id `C`); `vetoes()` is called only for those | `news_vetoes` exists only after 004; the C row also comes from 004, so A/F4/F1 never query a table Vercel may serve before the nightly `Migrate` step applies 004 |
| Verdict sheet states | no rows → "No news check for {date}: A had no candidates, or the check did not run. C buys nothing this session." (`noCheckLine`; reconciliation decision: `veto` writes no rows on a zero-candidate night, so the app cannot tell the two apart and says so); all `failed` with one reason → "News check failed for {date}: C sits this session out." + the reason; else list `veto`/`failed` rows by rank (or "Nothing vetoed. Every pick passed the news check.") | K8; a shared failure (no keys, model mismatch) is shown once, not ten times |
| Reason disclosure | Existing `WhyToggle` with `label` "Why vetoed" / "Why it failed" | Reuses the icon-only toggle (aria-label + data-tip already); a fixed "Why this pick" label would be wrong on a vetoed row |
| `parseGate` with `applicable: false, passed: true` | reads `passed: false` | Not applicable never counts as a pass (D9) |
| Demo C clock | C starts 28 sessions before the data date (`C_PAPER_START`), A/F4/F1/SPY at session 1 | D1: a new id has its own clock; the demo shows the younger clock and a partial first month |

## Implementation Steps

### Step 1: Gate with `applicable`, `checksNews`
**File:** `web/lib/strategy.ts` — whole file (30 lines today)
**Change:** Replace the whole file.
**Code:**
````ts
// Pure helpers for `strategies` rows: engine, backtest gate and short label. No database access,
// so pages, metrics and tests can import them without a connection.

/** How a strategy trades (migration 003, `strategies.engine`). */
export type Engine = 'bracket' | 'book' | 'benchmark';

/**
 * `strategies.params->'backtest_gate'` (contract C2): did the strategy pass its backtest gate?
 * `applicable` is false only for a strategy the backtest item does not apply to (design §1 item 5:
 * C, an LLM strategy, cannot be backtested without look-ahead). Not applicable never counts as passed.
 */
export type Gate = { passed: boolean; applicable: boolean; note: string | null };

const ENGINES: readonly string[] = ['bracket', 'book', 'benchmark'];

/** The row's engine. Rows written before migration 003 have none: benchmark when flagged, else bracket. */
export function engineOf(engine: unknown, isBenchmark: boolean): Engine {
  if (typeof engine === 'string' && ENGINES.includes(engine)) return engine as Engine;
  return isBenchmark ? 'benchmark' : 'bracket';
}

/**
 * Reads the gate from params. Missing or malformed reads as not passed and applicable: a pass is
 * never assumed, and only an explicit `applicable: false` marks the backtest item not applicable.
 */
export function parseGate(raw: unknown): Gate {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) return { passed: false, applicable: true, note: null };
  const g = raw as Record<string, unknown>;
  const note = typeof g.note === 'string' && g.note.trim() !== '' ? g.note : null;
  const applicable = g.applicable !== false;
  return { passed: applicable && g.passed === true, applicable, note };
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
````
**Impact:** `Gate` gains a required field: every object literal typed `Gate` must add it (only tests construct them; updated below). `data.ts` passes `parseGate(r.gate)` unchanged.

### Step 2: Strategy tests
**File:** `web/lib/strategy.test.ts` — whole file
**Change:** Replace the whole file.
**Code:**
````ts
import { describe, expect, it } from 'vitest';
import { checksNews, engineOf, parseGate, shortLabel } from './strategy';

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
      .toEqual({ passed: false, applicable: true, note: 'P7a dev window only; failed max DD <= 15% (22.2%)' });
    expect(parseGate({ passed: true, note: '' })).toEqual({ passed: true, applicable: true, note: null });
  });
  it('never assumes a pass', () => {
    expect(parseGate(null)).toEqual({ passed: false, applicable: true, note: null });
    expect(parseGate(undefined)).toEqual({ passed: false, applicable: true, note: null });
    expect(parseGate({ passed: 'true' })).toEqual({ passed: false, applicable: true, note: null });
    expect(parseGate([true])).toEqual({ passed: false, applicable: true, note: null });
  });
  it('reads a not-applicable gate (C, design §1 item 5)', () => {
    const note = 'Backtest gate: not applicable (LLM strategy, design §1 item 5)';
    expect(parseGate({ passed: false, applicable: false, note })).toEqual({ passed: false, applicable: false, note });
  });
  it('only an explicit false makes the gate not applicable, and not applicable is never a pass', () => {
    expect(parseGate({ passed: false, applicable: 'false' }).applicable).toBe(true);
    expect(parseGate({ passed: false, applicable: null }).applicable).toBe(true);
    expect(parseGate({ passed: true, applicable: false })).toEqual({ passed: false, applicable: false, note: null });
  });
});

describe('shortLabel', () => {
  it('takes the part before the middle dot', () => {
    expect(shortLabel('F4 · Momentum', 'F4-MOM12-N20-TREND')).toBe('F4');
    expect(shortLabel('A · Quant', 'A')).toBe('A');
    expect(shortLabel('C · News veto', 'C')).toBe('C');
    expect(shortLabel('SPY', 'SPY')).toBe('SPY');
    expect(shortLabel(' · Nameless', 'X1')).toBe('X1');
  });
});

describe('checksNews', () => {
  it('is true for the C object or the C roster id', () => {
    expect(checksNews('C', 'STRATEGY_C')).toBe(true);
    expect(checksNews('C', null)).toBe(true);
    expect(checksNews('C2-news', 'STRATEGY_C')).toBe(true);
  });
  it('is false for every other strategy', () => {
    expect(checksNews('A', 'STRATEGY_A')).toBe(false);
    expect(checksNews('SPY', null)).toBe(false);
    expect(checksNews('F4-MOM12-N20-TREND', 'FACTOR')).toBe(false);
  });
});
````
**Impact:** Existing `parseGate` expectations gain `applicable: true`.

### Step 3: Checklist row 6: not-applicable variant
**File:** `web/lib/metrics.ts` — whole file (72 lines today; `checklist` at l.47–72)
**Change:** Replace the whole file. Only `checklist` changes: row 6 moves into `gateItem`.
**Code:**
````ts
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

/** The sixth rule: "Backtest gate passed", or "Not applicable" for C (design §1 item 5), which never counts as passed. */
export function gateItem(gate: Gate): CheckItem {
  const item: CheckItem = gate.applicable
    ? { label: 'Backtest gate passed', val: gate.passed ? 'Passed' : 'Not passed', ok: gate.passed }
    : { label: 'Backtest gate', val: 'Not applicable', ok: false };
  if (gate.note !== null) item.note = gate.note;
  return item;
}

/**
 * The fixed go-live rules from the design doc (§1): five forward-test metrics, then
 * "Backtest gate passed" from `strategies.params.backtest_gate` (D12). All six must hold.
 * A strategy whose backtest item is not applicable (C, handover D9) can never pass all six.
 */
export function checklist(m: Metrics, spyReturn: number | null, gate: Gate): CheckItem[] {
  const ret = m.totalReturn ?? 0;
  const p1 = (v: number) => (v >= 0 ? '+' : '−') + Math.abs(v * 100).toFixed(1);
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
    gateItem(gate),
  ];
}
````
**Impact:** Applicable gates produce byte-identical rows to today.

### Step 4: Metrics tests
**File:** `web/lib/metrics.test.ts` — whole file
**Change:** Replace the whole file.
**Code:**
````ts
import { describe, expect, it } from 'vitest';
import { checklist, gateItem, strategyMetrics } from './metrics';

const snaps = (vals: number[]) =>
  vals.map((equity, i) => ({ date: new Date(Date.UTC(2026, 6, 1 + i)).toISOString().slice(0, 10), equity }));

const FAILED = { passed: false, applicable: true, note: 'P7a dev window only; failed max DD <= 15% (22.2%)' };
const PASSED = { passed: true, applicable: true, note: null };
const NOT_APPLICABLE = { passed: false, applicable: false, note: 'Backtest gate: not applicable (LLM strategy, design §1 item 5)' };

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

  it('reads "Not applicable" for C and never counts it as passed (handover D9)', () => {
    const items = checklist(base, 0.046, NOT_APPLICABLE);
    expect(items).toHaveLength(6);
    expect(items[5]).toEqual({ label: 'Backtest gate', val: 'Not applicable', ok: false, note: NOT_APPLICABLE.note });
    // Even every forward metric passing leaves C at five of six.
    const allForward = checklist({ ...base, trades: 120 }, 0.046, NOT_APPLICABLE);
    expect(allForward.filter(i => i.ok)).toHaveLength(5);
    expect(allForward.every(i => i.ok)).toBe(false);
  });

  it('builds the sixth rule on its own', () => {
    expect(gateItem({ passed: false, applicable: false, note: null })).toEqual({ label: 'Backtest gate', val: 'Not applicable', ok: false });
    expect(gateItem(PASSED)).toEqual({ label: 'Backtest gate passed', val: 'Passed', ok: true });
  });

  it('passes only when all six hold', () => {
    expect(checklist({ ...base, trades: 120 }, 0.046, PASSED).every(i => i.ok)).toBe(true);
    // Every forward metric passing does not make a strategy ready while its backtest gate failed.
    const failedGate = checklist({ ...base, trades: 120 }, 0.046, FAILED);
    expect(failedGate.filter(i => i.ok)).toHaveLength(5);
    expect(failedGate.every(i => i.ok)).toBe(false);
  });
});
````
**Impact:** Fixtures gain `applicable`; adds the D9 cases.

### Step 5: Verdict helpers (new module)
**File:** `web/lib/vetoes.ts` — new file
**Change:** Create.
**Code:**
````ts
// Pure helpers for the news check's verdicts (`news_vetoes`, migration 004; strategy C, handover
// D6/D10). No database access: lib/data reads the rows, Positions renders what these return.

/** The stored verdict. Anything else reads as 'failed': a failed check is no trade (design §8). */
export type Verdict = 'allow' | 'veto' | 'failed';

/** One candidate's verdict for one session, as Positions shows it. */
export type Veto = {
  /** Rank in A's ranked list for the session (1..10). */
  rank: number;
  symbol: string;
  verdict: Verdict;
  /** The LLM's one sentence, or why the check failed (redacted by the engine). */
  reason: string;
  /** Headlines the check saw (jsonb_array_length(headlines)). */
  headlineCount: number;
  /** Scheduled earnings found inside the holding window, if any. */
  earningsDate: string | null;
  /** The veto run's start: the news cutoff (ISO, UTC). */
  decidedAt: string;
};

/** Never assumes 'allow': an unknown value is a failed check. */
export function parseVerdict(v: unknown): Verdict {
  return v === 'allow' || v === 'veto' ? v : 'failed';
}

/**
 * What the "Vetoed tonight" sheet shows:
 * - 'missing': no verdict rows for the session, so the strategy buys nothing that session. `veto`
 *   writes no rows when A had no candidates, so this cannot be told apart from a check that did not
 *   run (or came after Paper had decided); `noCheckLine` says so;
 * - 'failed': every check failed for the same reason (no keys, wrong model, ...), shown once;
 * - 'listed': the vetoed and failed candidates (possibly none), by rank.
 */
export type VetoSheet =
  | { state: 'missing' }
  | { state: 'failed'; checked: number; reason: string }
  | { state: 'listed'; checked: number; allowed: number; rows: Veto[] };

export function vetoSheet(rows: Veto[]): VetoSheet {
  if (rows.length === 0) return { state: 'missing' };
  const sorted = [...rows].sort((a, b) => a.rank - b.rank);
  const reasons = new Set(sorted.map(r => r.reason));
  if (sorted.every(r => r.verdict === 'failed') && reasons.size === 1) {
    return { state: 'failed', checked: sorted.length, reason: sorted[0].reason };
  }
  return {
    state: 'listed',
    checked: sorted.length,
    allowed: sorted.filter(r => r.verdict === 'allow').length,
    rows: sorted.filter(r => r.verdict !== 'allow'),
  };
}

/** '8 checked · 5 allowed' */
export const checkedLine = (checked: number, allowed: number) => `${checked} checked · ${allowed} allowed`;

/** 0 -> 'No headlines', 1 -> '1 headline', 12 -> '12 headlines' */
export const headlinesLabel = (k: number) => (k === 0 ? 'No headlines' : k === 1 ? '1 headline' : `${k} headlines`);

/**
 * The 'missing' sheet's line (`day` already formatted, `short` the strategy's short label). Honest about
 * what the app cannot know: no rows means A had no candidates or the check did not run.
 */
export const noCheckLine = (day: string, short: string) =>
  `No news check for ${day}: A had no candidates, or the check did not run. ${short} buys nothing this session.`;
````
**Impact:** Pure; no DB import, so tests and the page share it.

### Step 6: Verdict helper tests (new)
**File:** `web/lib/vetoes.test.ts` — new file
**Change:** Create.
**Code:**
````ts
import { describe, expect, it } from 'vitest';
import { checkedLine, headlinesLabel, noCheckLine, parseVerdict, vetoSheet, type Veto } from './vetoes';

const v = (rank: number, symbol: string, verdict: Veto['verdict'], reason = 'r'): Veto => ({
  rank, symbol, verdict, reason, headlineCount: 3, earningsDate: null, decidedAt: '2026-10-05T23:10:00.000Z',
});

describe('parseVerdict', () => {
  it('keeps allow and veto and reads anything else as failed', () => {
    expect(parseVerdict('allow')).toBe('allow');
    expect(parseVerdict('veto')).toBe('veto');
    expect(parseVerdict('failed')).toBe('failed');
    expect(parseVerdict('ALLOW')).toBe('failed');
    expect(parseVerdict(null)).toBe('failed');
  });
});

describe('vetoSheet', () => {
  it('is missing when there are no rows (A had no candidates, or the check did not run)', () => {
    expect(vetoSheet([])).toEqual({ state: 'missing' });
  });
  it('shows one shared reason when every check failed the same way', () => {
    const why = 'LLM_API_KEY, LLM_BASE_URL or LLM_MODEL is not set';
    expect(vetoSheet([v(2, 'B', 'failed', why), v(1, 'A', 'failed', why)]))
      .toEqual({ state: 'failed', checked: 2, reason: why });
  });
  it('lists vetoed and failed candidates by rank, with the counts', () => {
    const sheet = vetoSheet([v(3, 'C', 'allow'), v(2, 'B', 'failed', 'timeout'), v(1, 'A', 'veto', 'earnings')]);
    expect(sheet).toEqual({
      state: 'listed', checked: 3, allowed: 1,
      rows: [v(1, 'A', 'veto', 'earnings'), v(2, 'B', 'failed', 'timeout')],
    });
  });
  it('lists every failed row when the reasons differ', () => {
    const sheet = vetoSheet([v(1, 'A', 'failed', 'timeout'), v(2, 'B', 'failed', 'HTTP 502')]);
    expect(sheet.state).toBe('listed');
    if (sheet.state === 'listed') expect(sheet.rows.map(r => r.symbol)).toEqual(['A', 'B']);
  });
  it('lists nothing when every candidate was allowed', () => {
    expect(vetoSheet([v(1, 'A', 'allow'), v(2, 'B', 'allow')])).toEqual({ state: 'listed', checked: 2, allowed: 2, rows: [] });
  });
});

describe('labels', () => {
  it('counts checks and headlines', () => {
    expect(checkedLine(8, 5)).toBe('8 checked · 5 allowed');
    expect(headlinesLabel(0)).toBe('No headlines');
    expect(headlinesLabel(1)).toBe('1 headline');
    expect(headlinesLabel(12)).toBe('12 headlines');
  });
  it('says honestly what no rows can mean', () => {
    expect(noCheckLine('Mon, Oct 5', 'C')).toBe(
      'No news check for Mon, Oct 5: A had no candidates, or the check did not run. C buys nothing this session.',
    );
  });
});
````
**Impact:** —

### Step 7: `checksNews` on `Strategy` and `vetoes()`
**File:** `web/lib/data.ts` — imports l.1–7; `Strategy` l.20–39; `toStrategy`/`strategies()` l.41–65; new function inserted before `/** Bracket exits (design §5) ...` (l.282 today)
**Change:** Apply this exact diff (every `-` line is the current text).
**Code:**
````diff
--- a/web/lib/data.ts
+++ b/web/lib/data.ts
@@ -2,9 +2,11 @@
 import { strategyMetrics, type Metrics, type Snapshot } from '@/lib/metrics';
 import { monthlyTable, type MonthlyTable } from '@/lib/monthly';
 import { isStale } from '@/lib/session';
-import { engineOf, parseGate, shortLabel, type Engine, type Gate } from '@/lib/strategy';
+import { checksNews, engineOf, parseGate, shortLabel, type Engine, type Gate } from '@/lib/strategy';
+import { parseVerdict, type Veto } from '@/lib/vetoes';
 
 export type { Engine, Gate } from '@/lib/strategy';
+export type { Veto, Verdict } from '@/lib/vetoes';
 
 type Row = Record<string, any>;
 
@@ -24,18 +26,20 @@
   icon: string;
   isChampion: boolean;
   isBenchmark: boolean;
-  /** 'bracket' (A), 'book' (F4, F1) or 'benchmark' (SPY). */
+  /** 'bracket' (A, C), 'book' (F4, F1) or 'benchmark' (SPY). */
   engine: Engine;
   /** 'design-v0', 'monthly-hold'; null for SPY. */
   rulesId: string | null;
   /** First paper session; null until the engine's `paper` command starts the clock. */
   paperStart: string | null;
-  /** params->'backtest_gate'; { passed: false, note: null } until `paper` writes the frozen spec. */
+  /** params->'backtest_gate'; { passed: false, applicable: true, note: null } until `paper` writes the frozen spec. */
   gate: Gate;
   /** A research strategy: its orders and positions are paper only and never a buy recommendation. */
   isPaper: boolean;
-  /** 'A', 'F4', 'F1', 'SPY': the part of the name before the middle dot. */
+  /** 'A', 'C', 'F4', 'F1', 'SPY': the part of the name before the middle dot. */
   short: string;
+  /** Runs the nightly news check (C): Positions shows its verdicts under the paper orders. */
+  checksNews: boolean;
 };
 
 function toStrategy(r: Row): Strategy {
@@ -54,12 +58,13 @@
     gate: parseGate(r.gate),
     isPaper: !isBenchmark && !isChampion,
     short: shortLabel(r.name, r.id),
+    checksNews: checksNews(r.id, r.spec_object),
   };
 }
 
 export async function strategies(): Promise<Strategy[]> {
   const rows = await sql`SELECT id, name, sub, icon, is_champion, is_benchmark, engine, rules_id,
-      paper_start::text AS paper_start, params->'backtest_gate' AS gate
+      paper_start::text AS paper_start, params->'backtest_gate' AS gate, params->'spec'->>'object' AS spec_object
     FROM strategies ORDER BY sort, id`;
   return rows.map(toStrategy);
 }
@@ -279,6 +284,21 @@
   return { sessionDate: pendingSession, decision: false, orders: [] };
 }
 
+/**
+ * The news check's verdicts for one strategy and session (`news_vetoes`, migration 004), every
+ * verdict, by rank in A's list. Empty when the `veto` step did not run (or found no candidates).
+ */
+export async function vetoes(strategyId: string, sessionDate: string): Promise<Veto[]> {
+  const rows = await sql`SELECT rank, symbol, verdict, reason, jsonb_array_length(headlines) AS headline_count,
+      earnings_date::text AS earnings_date, decided_at
+    FROM news_vetoes WHERE strategy_id = ${strategyId} AND session_date = ${sessionDate} ORDER BY rank`;
+  return rows.map(r => ({
+    rank: n(r.rank), symbol: r.symbol, verdict: parseVerdict(r.verdict), reason: String(r.reason ?? ''),
+    headlineCount: n(r.headline_count), earningsDate: ymdOrNull(r.earnings_date),
+    decidedAt: new Date(r.decided_at).toISOString(),
+  }));
+}
+
 /** Bracket exits (design §5) plus the book engine's signal and forced exits. */
 export type ExitReason = 'tp' | 'sl' | 'time' | 'gap' | 'signal' | 'forced';
 
````
**Impact:** `strategies()` selects one more column (`params->'spec'->>'object'`, NULL for rows without a spec). `vetoes()` reads `news_vetoes`; it is only called for `checksNews` strategies (Step 12).

### Step 8: Leaderboard view helpers
**File:** `web/app/(app)/leaderboard/view.ts` — whole file (118 lines today; `CARD_BGS`/`LINES` l.12–13, `scoreOf` l.59–69)
**Change:** Replace the whole file.
**Code:**
````ts
// Pure helpers for the Leaderboard: roster-driven looks, the best research strategy, the honest
// checklist line and the month-by-month rows. No data access; page.tsx feeds it.
// Selection (`selectStrategy`) and icons (`strategyIcon`) are phase 11's `components/roster.ts`;
// short labels are phase 10's `Strategy.short`; the month math is phase 10's `lib/monthly.ts`.
import { monthDay, monthName, pct, signedPct } from '../../../lib/format';
import type { MonthlyTable } from '../../../lib/monthly';

/** The roster fields these helpers read (a structural subset of lib/data's Strategy). */
export type RosterIn = { id: string; isChampion: boolean; isBenchmark: boolean };

/**
 * Research strategies take the design's sheet and line pairs in roster order: the A/B/C pairs, then
 * butter (the fourth sheet of the design's slot palette) with the coral accent line, so a fourth
 * research strategy (C · News veto) never reuses the first one's look.
 */
export const CARD_BGS = ['bg-lav', 'bg-sky', 'bg-stone', 'bg-butter'] as const;
export const LINES = ['var(--ink)', 'var(--line-b)', 'var(--line-c)', 'var(--coral)'] as const;

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

/**
 * The month-by-month sheet's tint: the strategy's card sheet, except butter, which on mobile would
 * merge into the butter checklist sheet stacked right above it; that one takes stone instead.
 */
export const monthsBg = (look: Look): string => (look.bg === 'bg-butter' ? 'bg-stone' : look.bg);

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

/** The gate fields the score reads (a structural subset of lib/strategy's Gate). */
export type GateIn = { passed: boolean; applicable: boolean };

/** A strategy with no checklist yet: not passed, applicable. */
export const NO_GATE: GateIn = { passed: false, applicable: true };

/**
 * The checklist score and its two-line verdict. Never "Ready for real money" unless all six pass,
 * and never for a strategy whose backtest item is not applicable (C, handover D9): real money for
 * it would need an explicit owner decision even if the five forward rules pass.
 */
export function scoreOf(items: { ok: boolean }[], gate: GateIn): Score {
  const passed = items.filter(i => i.ok).length;
  const ready = gate.applicable && items.length === CHECKS && passed === CHECKS;
  const lines: [string, string] = !gate.applicable
    ? ['Paper only. No backtest gate.', 'Real money needs an owner decision']
    : ready
      ? ['All six pass.', 'Ready for real money']
      : gate.passed
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
````
**Impact:** `scoreOf`'s second argument changes type (boolean → `GateIn`); its only caller is `leaderboard/page.tsx` (next step but one). A 5th research strategy now cycles to lav/ink-2 (was the 4th).

### Step 9: Leaderboard view tests
**File:** `web/app/(app)/leaderboard/view.test.ts` — whole file
**Change:** Replace the whole file.
**Code:**
````ts
import { describe, expect, it } from 'vitest';
import type { MonthlyTable } from '../../../lib/monthly';
import {
  bestResearch, CHECKS, looks, monthLabel, monthLines, monthsBg, NO_GATE, researchOf, scoreOf, sinceStartLine,
  type RosterIn,
} from './view';

const roster: RosterIn[] = [
  { id: 'SPY', isChampion: true, isBenchmark: true },
  { id: 'A', isChampion: false, isBenchmark: false },
  { id: 'F4-MOM12-N20-TREND', isChampion: false, isBenchmark: false },
  { id: 'F1-SPY-SMA200-M', isChampion: false, isBenchmark: false },
  { id: 'C', isChampion: false, isBenchmark: false },
];
const RESEARCH = ['A', 'F4-MOM12-N20-TREND', 'F1-SPY-SMA200-M', 'C'];

describe('looks', () => {
  it('gives the benchmark the dotted line on a plain sheet', () => {
    expect(looks(roster).get('SPY')).toEqual({ bg: 'bg-sheet', line: 'var(--ink-3)', width: 1.75, dotted: true });
  });
  it('assigns research sheets and lines in roster order', () => {
    const l = looks(roster);
    expect(RESEARCH.map(id => l.get(id)!.bg)).toEqual(['bg-lav', 'bg-sky', 'bg-stone', 'bg-butter']);
    expect(RESEARCH.map(id => l.get(id)!.line)).toEqual(['var(--ink)', 'var(--line-b)', 'var(--line-c)', 'var(--coral)']);
    expect(RESEARCH.map(id => l.get(id)!.width)).toEqual([2, 2, 2, 2]);
  });
  it('never gives C the look of A', () => {
    const l = looks(roster);
    expect(l.get('C')).not.toEqual(l.get('A'));
    expect(l.get('C')).toEqual({ bg: 'bg-butter', line: 'var(--coral)', width: 2, dotted: false });
  });
  it('follows roster order, not ids', () => {
    const l = looks([roster[3], roster[0], roster[1]]);
    expect(l.get('F1-SPY-SMA200-M')).toEqual({ bg: 'bg-lav', line: 'var(--ink)', width: 2, dotted: false });
    expect(l.get('A')).toEqual({ bg: 'bg-sky', line: 'var(--line-b)', width: 2, dotted: false });
  });
  it('cycles sheets and uses the spare line for a fifth research strategy', () => {
    const l = looks([...roster, { id: 'X9', isChampion: false, isBenchmark: false }]);
    expect(l.get('X9')).toEqual({ bg: 'bg-lav', line: 'var(--ink-2)', width: 2, dotted: false });
  });
  it('emphasises a non-benchmark champion', () => {
    const l = looks([{ ...roster[0], isChampion: false }, { ...roster[1], isChampion: true }]);
    expect(l.get('A')!.width).toBe(2.75);
  });
});

describe('monthsBg', () => {
  it('keeps the card sheet, except butter, which would merge into the butter checklist above it', () => {
    const l = looks(roster);
    expect(monthsBg(l.get('A')!)).toBe('bg-lav');
    expect(monthsBg(l.get('F4-MOM12-N20-TREND')!)).toBe('bg-sky');
    expect(monthsBg(l.get('C')!)).toBe('bg-stone');
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
    const b = bestResearch([row(0, 0.05), row(1, -0.01), row(2, 0.02), row(3, null), row(4, 0.01)]);
    expect(b?.strategy.id).toBe('F4-MOM12-N20-TREND');
    expect(b?.ret).toBeCloseTo(0.02);
  });
  it('is null before any paper result', () => {
    expect(bestResearch([row(0, 0.01), row(1, null)])).toBeNull();
  });
});

describe('scoreOf', () => {
  const items = (oks: boolean[]) => oks.map(ok => ({ ok }));
  const PASSED = { passed: true, applicable: true };
  const FAILED = { passed: false, applicable: true };
  const NOT_APPLICABLE = { passed: false, applicable: false };
  it('scores out of six and says paper only while the gate has not passed', () => {
    const sc = scoreOf(items([true, true, true, true, true, false]), FAILED);
    expect(sc).toEqual({ passed: 5, total: CHECKS, ready: false, lines: ['Paper only.', 'Backtest gate not passed'] });
    expect(scoreOf([], NO_GATE).lines).toEqual(['Paper only.', 'Backtest gate not passed']);
  });
  it('says paper trading until all six pass when only the gate has passed', () => {
    expect(scoreOf(items([false, false, true, true, true, true]), PASSED).lines).toEqual(['Paper trading until', 'all six pass']);
  });
  it('is ready only when all six pass', () => {
    const sc = scoreOf(items([true, true, true, true, true, true]), PASSED);
    expect(sc.ready).toBe(true);
    expect(sc.lines).toEqual(['All six pass.', 'Ready for real money']);
  });
  it('is never ready with fewer than six items', () => {
    expect(scoreOf(items([true, true, true, true, true]), PASSED).ready).toBe(false);
  });
  it('says real money needs an owner decision when the gate is not applicable (C, handover D9)', () => {
    const sc = scoreOf(items([true, true, true, true, true, false]), NOT_APPLICABLE);
    expect(sc).toEqual({
      passed: 5, total: CHECKS, ready: false,
      lines: ['Paper only. No backtest gate.', 'Real money needs an owner decision'],
    });
  });
  it('is never ready when the gate is not applicable, whatever the items say', () => {
    const sc = scoreOf(items([true, true, true, true, true, true]), NOT_APPLICABLE);
    expect(sc.ready).toBe(false);
    expect(sc.lines[1]).toBe('Real money needs an owner decision');
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
````
**Impact:** —

### Step 10: Leaderboard page
**File:** `web/app/(app)/leaderboard/page.tsx` — l.11–14 (import), l.42 (`scoreOf`), l.135 (months sheet), l.173 (`--cols`)
**Change:** Apply this exact diff.
**Code:**
````diff
--- a/web/app/(app)/leaderboard/page.tsx
+++ b/web/app/(app)/leaderboard/page.tsx
@@ -9,7 +9,7 @@
 import { checklist } from '@/lib/metrics';
 import { wibDate } from '@/lib/session';
 import {
-  bestResearch, LOOK_FALLBACK, looks, monthLines, researchOf, scoreOf, sinceStartLine,
+  bestResearch, LOOK_FALLBACK, looks, monthLines, monthsBg, NO_GATE, researchOf, scoreOf, sinceStartLine,
   type Look, type MonthLine,
 } from './view';
 import s from './leaderboard.module.css';
@@ -39,7 +39,7 @@
   const pickRow = pick ? board.rows.find(r => r.strategy.id === pick.id) : undefined;
   const gate = pickRow?.strategy.gate ?? null;
   const items = pickRow && gate ? checklist(pickRow.metrics, spyRet, gate) : [];
-  const score = scoreOf(items, gate?.passed === true);
+  const score = scoreOf(items, gate ?? NO_GATE);
   // The latest month is partial while the engine's next session (runStatus().sessionDate) is in it.
   const table = pick ? await monthly(pick.id, run.sessionDate) : null;
   const since = table ? sinceStartLine(table) : null;
@@ -132,7 +132,7 @@
   );
 
   const monthsSheet = (
-    <section className={`sheet over ${pick ? lookOf(pick.id).bg : 'bg-sheet'} ${s.months}`} aria-labelledby="months-title">
+    <section className={`sheet over ${pick ? monthsBg(lookOf(pick.id)) : 'bg-sheet'} ${s.months}`} aria-labelledby="months-title">
       <div className={s.between}>
         <h2 id="months-title" className="eyebrow">Month by month · {pick ? pick.short : '—'}</h2>
         {pick && <PaperChip />}
@@ -170,7 +170,7 @@
       <div className="stack">
         <div className={s.top}>{chartSheet}{checklistSheet}</div>
         {monthsSheet}
-        <div className={s.cards} style={{ '--cols': Math.min(Math.max(board.rows.length, 1), 4) } as CSSProperties}>
+        <div className={s.cards} style={{ '--cols': Math.min(Math.max(board.rows.length, 1), 5) } as CSSProperties}>
           {board.rows.map(({ strategy: st, metrics: m }) => {
             const Icon = strategyIcon(st.icon);
             const dash = (v: string) => (st.isBenchmark ? '—' : v);
````
**Impact:** The checklist sheet already prints `gate.note` under the rows, so C's note ("Backtest gate: not applicable (LLM strategy, design §1 item 5)") shows with no further change.

### Step 11: `WhyToggle` label
**File:** `web/components/WhyToggle.tsx` — whole file
**Change:** Replace the whole file. With no `label`/`missing`, the rendered output equals today's (Today and the paper orders keep "Why this pick").
**Code:**
````tsx
'use client';

import { ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';
import s from './WhyToggle.module.css';

/**
 * "Why this pick": the LLM's plain-language explanation, collapsed by default. `label` and
 * `missing` let other plain-language reasons (the news check's verdicts) reuse it unchanged.
 */
export function WhyToggle({ text, label = 'Why this pick', missing = 'Explanation unavailable for this pick.' }: {
  text: string | null;
  label?: string;
  missing?: string;
}) {
  const [open, setOpen] = useState(false);
  const tip = open ? 'Hide explanation' : label;
  return (
    <>
      <div className={s.row}>
        <button type="button" className={`icon-btn sm ${open ? 'inverted' : 'soft'}`} data-tip={tip} aria-label={tip}
          aria-expanded={open} onClick={() => setOpen(o => !o)}>
          {open ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </button>
        <span className={s.label}>{label}</span>
      </div>
      {open && <p className={s.why}>{text ?? missing}</p>}
    </>
  );
}
````
**Impact:** none for existing callers.

### Step 12: Positions — "Vetoed tonight"
**File:** `web/app/(app)/positions/page.tsx` — whole file (313 lines today; orders section l.101–116, `noOrders` l.142–149)
**Change:** Replace the whole file. Differences from today: imports (`Gavel`, `vetoes as getVetoes`, `type Veto`, `monthDay`, `lib/vetoes`); `showChecks`/`checks`/`sheet` after `orderSession`; `noOrders(st, p, sheet)`; the `<VetoedTonight>` sheet after the orders sheet (inside the same `strat && orderSession` condition, so hidden while data is stale); new `VetoedTonight` and `VetoRow`. For reference, the diff against today is at the end of this step.
**Code:**
````tsx
import { Crown, Gavel, Landmark, TriangleAlert } from 'lucide-react';
import { AppHeader } from '@/components/AppHeader';
import { PaperChip } from '@/components/PaperChip';
import { selectStrategy, sharesLabel, strategyIcon } from '@/components/roster';
import { StrategySwitch } from '@/components/StrategySwitch';
import { WhyToggle } from '@/components/WhyToggle';
import {
  pendingOrders, positions as getPositions, runStatus, strategies, vetoes as getVetoes,
  type Holding, type Pending, type PendingOrder, type RunStatus, type Strategy, type Veto,
} from '@/lib/data';
import { monthDay, pct, shortDate, signedPct, signedRp, signedUsd, usd } from '@/lib/format';
import { wibDate } from '@/lib/session';
import { cardBg } from '@/lib/slots';
import { checkedLine, headlinesLabel, noCheckLine, vetoSheet, type VetoSheet } from '@/lib/vetoes';
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
  // The news check's verdicts for the same session (C, handover D10). Read only for a strategy that runs
  // the check: its roster row comes from migration 004, which also creates news_vetoes.
  const showChecks = !!strat && !!orderSession && strat.checksNews && strat.engine === 'bracket';
  const checks = showChecks && strat && orderSession ? await getVetoes(strat.id, orderSession) : [];
  const sheet = showChecks ? vetoSheet(checks) : null;

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
              <span className={s.ordersNone}>{noOrders(strat, pending, sheet)}</span>
            ) : (
              <ul className={s.orderList}>
                {pending.orders.map(o => <OrderRow key={o.key} o={o} />)}
              </ul>
            )}
          </section>
        )}

        {strat && orderSession && sheet && <VetoedTonight st={strat} session={orderSession} sheet={sheet} />}
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

function noOrders(st: Strategy, p: Pending, sheet: VetoSheet | null): string {
  if (st.engine === 'book') {
    return p.decision
      ? `No orders. ${st.short} decided to hold cash.`
      : `No orders. ${st.short} decides on the first session of each month.`;
  }
  if (sheet && sheet.state === 'missing') return `No orders. ${st.short} buys nothing this session.`;
  if (sheet && sheet.state === 'failed') return `No orders. ${st.short} sits this session out.`;
  if (sheet && sheet.allowed === 0) return 'No orders. Nothing passed the news check.';
  return 'No setups tonight. Cash is a position.';
}

/**
 * "Vetoed tonight" (handover D10): what the news check took out of A's picks for this session.
 * A failed check is no trade (design §8), so failed rows are listed with the vetoes.
 */
function VetoedTonight({ st, session, sheet }: { st: Strategy; session: string; sheet: VetoSheet }) {
  return (
    <section className={`sheet over bg-stone ${s.vetoes}`}>
      <div className={`${s.between} ${s.vetoHead}`}>
        <span className="eyebrow">Vetoed tonight</span>
        {sheet.state !== 'missing' && (
          <span className={`chip num ${s.vetoCount}`}>{checkedLine(sheet.checked, sheet.state === 'listed' ? sheet.allowed : 0)}</span>
        )}
      </div>
      {sheet.state === 'missing' && (
        <span className={s.ordersNone}>{noCheckLine(shortDate(session), st.short)}</span>
      )}
      {sheet.state === 'failed' && (
        <>
          <span className={s.ordersNone}>News check failed for {shortDate(session)}: {st.short} sits this session out.</span>
          <span className={s.vetoReason}>{sheet.reason}</span>
        </>
      )}
      {sheet.state === 'listed' && (sheet.rows.length === 0 ? (
        <span className={s.ordersNone}>Nothing vetoed. Every pick passed the news check.</span>
      ) : (
        <ul className={s.orderList}>
          {sheet.rows.map(v => <VetoRow key={v.symbol} v={v} />)}
        </ul>
      ))}
    </section>
  );
}

function VetoRow({ v }: { v: Veto }) {
  const veto = v.verdict === 'veto';
  const facts = headlinesLabel(v.headlineCount) + (v.earningsDate ? ` · earnings ${monthDay(v.earningsDate)}` : '');
  return (
    <li className={s.order}>
      <div className={s.orderHead}>
        <span className={s.rank} data-tip="Rank among A's picks">{v.rank}</span>
        <span className={s.orderSym}>{v.symbol}</span>
        <span className={s.vetoGap} />
        {veto ? (
          <span className={`chip ${s.vetoChip}`} data-tip="The LLM vetoed this pick on its news">
            <Gavel size={15} aria-hidden="true" />Veto
          </span>
        ) : (
          <span className={`chip ${s.failChip}`} data-tip="The news check failed, so no trade (design §8)">
            <TriangleAlert size={15} aria-hidden="true" />Failed
          </span>
        )}
      </div>
      <span className={s.vetoFacts}>{facts}</span>
      <WhyToggle text={v.reason.trim() === '' ? null : v.reason} label={veto ? 'Why vetoed' : 'Why it failed'}
        missing="No reason was stored for this check." />
    </li>
  );
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
````
Reference diff (not to be applied in addition — the block above is the whole file):
````diff
--- a/web/app/(app)/positions/page.tsx
+++ b/web/app/(app)/positions/page.tsx
@@ -1,16 +1,17 @@
-import { Crown, Landmark, TriangleAlert } from 'lucide-react';
+import { Crown, Gavel, Landmark, TriangleAlert } from 'lucide-react';
 import { AppHeader } from '@/components/AppHeader';
 import { PaperChip } from '@/components/PaperChip';
 import { selectStrategy, sharesLabel, strategyIcon } from '@/components/roster';
 import { StrategySwitch } from '@/components/StrategySwitch';
 import { WhyToggle } from '@/components/WhyToggle';
 import {
-  pendingOrders, positions as getPositions, runStatus, strategies,
-  type Holding, type Pending, type PendingOrder, type RunStatus, type Strategy,
+  pendingOrders, positions as getPositions, runStatus, strategies, vetoes as getVetoes,
+  type Holding, type Pending, type PendingOrder, type RunStatus, type Strategy, type Veto,
 } from '@/lib/data';
-import { pct, shortDate, signedPct, signedRp, signedUsd, usd } from '@/lib/format';
+import { monthDay, pct, shortDate, signedPct, signedRp, signedUsd, usd } from '@/lib/format';
 import { wibDate } from '@/lib/session';
 import { cardBg } from '@/lib/slots';
+import { checkedLine, headlinesLabel, noCheckLine, vetoSheet, type VetoSheet } from '@/lib/vetoes';
 import s from './positions.module.css';
 
 export const dynamic = 'force-dynamic';
@@ -43,6 +44,11 @@
   const href = (id: string) => `/positions?s=${encodeURIComponent(id)}`;
   const [noneTitle, noneSub] = emptyState(strat);
   const orderSession = showOrders ? pending.sessionDate : null;
+  // The news check's verdicts for the same session (C, handover D10). Read only for a strategy that runs
+  // the check: its roster row comes from migration 004, which also creates news_vetoes.
+  const showChecks = !!strat && !!orderSession && strat.checksNews && strat.engine === 'bracket';
+  const checks = showChecks && strat && orderSession ? await getVetoes(strat.id, orderSession) : [];
+  const sheet = showChecks ? vetoSheet(checks) : null;
 
   return (
     <>
@@ -106,7 +112,7 @@
             </div>
             {pending.orders.some(o => o.kind === 'book') && <span className={s.ordersSub}>Target portfolio after the open, by rank</span>}
             {pending.orders.length === 0 ? (
-              <span className={s.ordersNone}>{noOrders(strat, pending)}</span>
+              <span className={s.ordersNone}>{noOrders(strat, pending, sheet)}</span>
             ) : (
               <ul className={s.orderList}>
                 {pending.orders.map(o => <OrderRow key={o.key} o={o} />)}
@@ -114,6 +120,8 @@
             )}
           </section>
         )}
+
+        {strat && orderSession && sheet && <VetoedTonight st={strat} session={orderSession} sheet={sheet} />}
         <div className="nav-clear" />
       </div>
     </>
@@ -139,15 +147,77 @@
   return ['No open positions.', null];
 }
 
-function noOrders(st: Strategy, p: Pending): string {
+function noOrders(st: Strategy, p: Pending, sheet: VetoSheet | null): string {
   if (st.engine === 'book') {
     return p.decision
       ? `No orders. ${st.short} decided to hold cash.`
       : `No orders. ${st.short} decides on the first session of each month.`;
   }
+  if (sheet && sheet.state === 'missing') return `No orders. ${st.short} buys nothing this session.`;
+  if (sheet && sheet.state === 'failed') return `No orders. ${st.short} sits this session out.`;
+  if (sheet && sheet.allowed === 0) return 'No orders. Nothing passed the news check.';
   return 'No setups tonight. Cash is a position.';
 }
 
+/**
+ * "Vetoed tonight" (handover D10): what the news check took out of A's picks for this session.
+ * A failed check is no trade (design §8), so failed rows are listed with the vetoes.
+ */
+function VetoedTonight({ st, session, sheet }: { st: Strategy; session: string; sheet: VetoSheet }) {
+  return (
+    <section className={`sheet over bg-stone ${s.vetoes}`}>
+      <div className={`${s.between} ${s.vetoHead}`}>
+        <span className="eyebrow">Vetoed tonight</span>
+        {sheet.state !== 'missing' && (
+          <span className={`chip num ${s.vetoCount}`}>{checkedLine(sheet.checked, sheet.state === 'listed' ? sheet.allowed : 0)}</span>
+        )}
+      </div>
+      {sheet.state === 'missing' && (
+        <span className={s.ordersNone}>{noCheckLine(shortDate(session), st.short)}</span>
+      )}
+      {sheet.state === 'failed' && (
+        <>
+          <span className={s.ordersNone}>News check failed for {shortDate(session)}: {st.short} sits this session out.</span>
+          <span className={s.vetoReason}>{sheet.reason}</span>
+        </>
+      )}
+      {sheet.state === 'listed' && (sheet.rows.length === 0 ? (
+        <span className={s.ordersNone}>Nothing vetoed. Every pick passed the news check.</span>
+      ) : (
+        <ul className={s.orderList}>
+          {sheet.rows.map(v => <VetoRow key={v.symbol} v={v} />)}
+        </ul>
+      ))}
+    </section>
+  );
+}
+
+function VetoRow({ v }: { v: Veto }) {
+  const veto = v.verdict === 'veto';
+  const facts = headlinesLabel(v.headlineCount) + (v.earningsDate ? ` · earnings ${monthDay(v.earningsDate)}` : '');
+  return (
+    <li className={s.order}>
+      <div className={s.orderHead}>
+        <span className={s.rank} data-tip="Rank among A's picks">{v.rank}</span>
+        <span className={s.orderSym}>{v.symbol}</span>
+        <span className={s.vetoGap} />
+        {veto ? (
+          <span className={`chip ${s.vetoChip}`} data-tip="The LLM vetoed this pick on its news">
+            <Gavel size={15} aria-hidden="true" />Veto
+          </span>
+        ) : (
+          <span className={`chip ${s.failChip}`} data-tip="The news check failed, so no trade (design §8)">
+            <TriangleAlert size={15} aria-hidden="true" />Failed
+          </span>
+        )}
+      </div>
+      <span className={s.vetoFacts}>{facts}</span>
+      <WhyToggle text={v.reason.trim() === '' ? null : v.reason} label={veto ? 'Why vetoed' : 'Why it failed'}
+        missing="No reason was stored for this check." />
+    </li>
+  );
+}
+
 function Change({ pnl, ratio }: { pnl: number; ratio: number | null }) {
   return (
     <div className={`${s.change} ${pnl < 0 ? 'neg' : 'pos'}`}>
````
**Impact:** One extra query (`vetoes`) on Positions only when the selected strategy is C. No buttons added besides `WhyToggle` (icon-only, aria-label + data-tip); the verdict chips and rank circle are data labels with `data-tip`, like the benchmark chip.

### Step 13: Positions styles
**File:** `web/app/(app)/positions/positions.module.css` — whole file (82 lines today; new block before `@media (min-width: 1024px)` at l.74, one desktop line after `.orders` at l.80)
**Change:** Replace the whole file.
**Code:**
````css
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

/* ---- Vetoed tonight (C's news check) ---- */
.vetoes { gap: 14px; }
.vetoHead { flex-wrap: wrap; row-gap: 8px; }
.vetoCount { flex: none; font-size: 14px; }
.vetoReason { font-size: 16px; line-height: 1.45; color: var(--ink-2); text-wrap: pretty; overflow-wrap: anywhere; }
.vetoGap { flex: 1; }
.vetoFacts { margin-top: -4px; font-size: 15px; color: var(--ink-2); }
.vetoChip { flex: none; background: var(--ink); color: var(--sheet); }
.failChip { flex: none; background: transparent; border: 1.5px dashed var(--outline); color: var(--ink-2); }

@media (min-width: 1024px) {
  .summary { border-radius: 40px; }
  .warn { margin-top: 12px; border-radius: 40px; padding: 22px 30px; }
  .grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 12px; align-items: start; }
  .card { border-radius: 32px; padding: 22px; }
  .none { margin-top: 12px; border-radius: 40px; }
  .orders { margin-top: 12px; border-radius: 40px; padding: 28px 30px; }
  .vetoes { margin-top: 12px; border-radius: 40px; padding: 28px 30px; }
  .orderList { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 40px; }
}
````
**Impact:** Only tokens already defined in `globals.css` (light and dark): `--ink`, `--sheet`, `--ink-2`, `--outline`. The sheet is `bg-stone` (the design's muted "not bought" sheet); the veto chip is inverted ink like the benchmark chip; the failed chip is dashed like the paper chip.

### Step 14: Roster icon comment and tests
**File:** `web/components/roster.ts` — l.3–4 (comment only; `gavel: Gavel` is already in `ICONS` at l.12)
**Change:** Apply this exact diff.
**Code:**
````diff
--- a/web/components/roster.ts
+++ b/web/components/roster.ts
@@ -1,7 +1,7 @@
 import { BrainCircuit, Gavel, Landmark, Shield, Sigma, TrendingUp, type LucideIcon } from 'lucide-react';
 
 // The `icon` column of `strategies` names a Lucide icon (kebab-case). Roster: landmark (SPY),
-// sigma (A), trending-up (F4), shield (F1); brain-circuit and gavel kept for old demo rows.
+// sigma (A), trending-up (F4), shield (F1), gavel (C, migration 004); brain-circuit kept for old demo rows.
 const ICONS: Record<string, LucideIcon> = {
   landmark: Landmark,
   sigma: Sigma,
````
**File:** `web/components/roster.test.ts` — whole file. Replace with:
````ts
import { Gavel, Landmark, Shield, Sigma, TrendingUp } from 'lucide-react';
import { describe, expect, it } from 'vitest';
import { selectStrategy, sharesLabel, strategyIcon } from './roster';

const roster = [
  { id: 'SPY', name: 'SPY', isChampion: true, isBenchmark: true },
  { id: 'A', name: 'A · Quant', isChampion: false, isBenchmark: false },
  { id: 'F4-MOM12-N20-TREND', name: 'F4 · Momentum', isChampion: false, isBenchmark: false },
  { id: 'F1-SPY-SMA200-M', name: 'F1 · Trend', isChampion: false, isBenchmark: false },
  { id: 'C', name: 'C · News veto', isChampion: false, isBenchmark: false },
];

describe('selectStrategy', () => {
  it('returns the requested strategy when it is on the roster', () => {
    expect(selectStrategy(roster, 'F1-SPY-SMA200-M')?.id).toBe('F1-SPY-SMA200-M');
    expect(selectStrategy(roster, 'SPY')?.id).toBe('SPY');
    expect(selectStrategy(roster, 'C')?.id).toBe('C');
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
    expect(strategyIcon('gavel')).toBe(Gavel);
    expect(strategyIcon('sigma')).toBe(Sigma);
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
````
**Impact:** —

### Step 15: Demo seed with C
**File:** `web/scripts/seed-demo.mjs` — whole file (308 lines today; roster l.49–68, A block l.167–218, writes l.240–301)
**Change:** Replace the whole file. Differences: header comment; `C_DAY0`/`C_PAPER_START`; every roster row carries `paperStart` (inserted instead of the shared `PAPER_START`); the `C` row (sort 5, `gavel`, spec object `STRATEGY_C`, `backtest_gate: { passed: false, applicable: false, note: 'Backtest gate: not applicable (LLM strategy, design §1 item 5)' }`); `fillClosed` and `bracketBook` factor A's closed-trade and snapshot generation (same `rnd()` call order, so A's, F4's, F1's and SPY's rows are unchanged) and build C's; the bracket writes loop over `brackets` with the strategy id as `$1` (the `'A'` literal is gone); bar inserts are `ON CONFLICT DO NOTHING` (A and C share GE/CSCO/AMZN); six `news_vetoes` rows for C's pending session (GE allow, LRCX veto with an earnings date, CSCO allow, MU failed, PANW allow, WBD veto) with synthetic, clearly-labelled headlines; `news_vetoes` in the TRUNCATE and in the final counts.
**Code:**
````js
// Fills Neon with demo data in the paper-trading shape (migrations 003 and 004), flagged is_demo so
// the UI warns "Demo data". Dates are relative to now so the demo is never stale.
// Roster: SPY (champion, buy and hold), A (bracket), F4-MOM12-N20-TREND and F1-SPY-SMA200-M
// (monthly book strategies), C (bracket: A's picks minus the news check's vetoes, on its own
// younger clock). 66 sessions ending at the last completed session: day 0 is the first, paper
// start the second, so the demo spans at least three calendar months. C starts 28 sessions ago.
// Needs migration 004 (news_vetoes, the C row's columns) applied first.
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
// C has its own clock (handover D1): it started after the others.
const C_DAY0 = LAST - 28;
const C_PAPER_START = sessions[C_DAY0 + 1];

// Monthly book strategies decide on the first session of a month (MONTHLY_HOLD).
const decisions = sessions.map((_, i) => i).filter(i => i >= 1 && monthOf(sessions[i]) !== monthOf(sessions[i - 1]));
if (decisions.length < 2) throw new Error('demo window must hold two month starts');
const FIRST_DECISION = decisions[0];
const LAST_DECISION = decisions[decisions.length - 1];
const pendingDecision = monthOf(session) !== monthOf(dataDate);

// --- deterministic randomness ------------------------------------------------
let seed = 7;
const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;

// --- roster (display rows as in migrations 003 and 004; params as the `paper` command writes them) ---
const gate = note => ({ passed: false, note });
const strategies = [
  { id: 'SPY', name: 'SPY', sub: 'S&P 500, buy and hold', icon: 'landmark', champion: true, benchmark: true, sort: 1,
    engine: 'benchmark', rulesId: null, paperStart: PAPER_START,
    params: { demo: true, spec: { engine: 'benchmark', symbol: 'SPY' }, digest: null,
      backtest_gate: gate('Benchmark, not a strategy: it has no backtest gate and is never a Seer pick') } },
  { id: 'A', name: 'A · Quant', sub: 'Mean reversion, 5-day brackets', icon: 'sigma', champion: false, benchmark: false, sort: 2,
    engine: 'bracket', rulesId: 'design-v0', paperStart: PAPER_START,
    params: { demo: true, spec: { engine: 'bracket', object: 'STRATEGY_A', rules_id: 'design-v0' }, digest: null,
      backtest_gate: gate('P3 gate failed out of sample (2022-01-03..2026-10-02): -15.0% vs SPY TR +71.9%, PF 0.92, max DD 33.3%') } },
  { id: 'F4-MOM12-N20-TREND', name: 'F4 · Momentum', sub: 'Top 20 by 12-1 momentum, monthly', icon: 'trending-up', champion: false, benchmark: false, sort: 3,
    engine: 'book', rulesId: 'monthly-hold', paperStart: PAPER_START,
    params: { demo: true, spec: { engine: 'book', object: 'FACTOR', registry_id: 'F4-MOM12-N20-TREND', rules_id: 'monthly-hold' }, digest: null,
      backtest_gate: gate('P7a dev window only; failed max DD <= 15% (22.2%)') } },
  { id: 'F1-SPY-SMA200-M', name: 'F1 · Trend', sub: 'SPY above its 200-day average, monthly', icon: 'shield', champion: false, benchmark: false, sort: 4,
    engine: 'book', rulesId: 'monthly-hold', paperStart: PAPER_START,
    params: { demo: true, spec: { engine: 'book', object: 'TIMING', registry_id: 'F1-SPY-SMA200-M', rules_id: 'monthly-hold' }, digest: null,
      backtest_gate: gate('P7a dev window only; failed max DD <= 15% (18.7%) and >= 100 trades (11)') } },
  { id: 'C', name: 'C · News veto', sub: 'A\'s picks, LLM can veto on news', icon: 'gavel', champion: false, benchmark: false, sort: 5,
    engine: 'bracket', rulesId: 'design-v0', paperStart: C_PAPER_START,
    params: { demo: true, spec: { engine: 'bracket', object: 'STRATEGY_C', rules_id: 'design-v0' }, digest: null,
      backtest_gate: { passed: false, applicable: false, note: 'Backtest gate: not applicable (LLM strategy, design §1 item 5)' } } },
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

// --- bracket portfolios (A, C): pending picks, open orders, closed trades -------------
// Pending picks: [slot, symbol, company, last, limit, tp, sl, shares, explanation]
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

// Closed trades up to `n`, random from POOL, exiting `agoFrom`..`agoFrom + agoSpan - 1` sessions ago
// (fills three sessions earlier, so inside the strategy's own paper window).
const fillClosed = (closed, n, w, pf, agoFrom, agoSpan) => {
  const cost = 0.002, avgWin = 0.022; // round-trip cost; losses sized so the net profit factor ≈ target
  const avgLoss = (w * (avgWin - cost)) / ((1 - w) * pf) - cost;
  for (let i = closed.length; i < n; i++) {
    const [sym, , base] = POOL[Math.floor(rnd() * POOL.length)];
    const win = rnd() < w;
    const en = r2(base * (0.9 + rnd() * 0.2));
    const move = (win ? avgWin : -avgLoss) * (0.6 + rnd() * 0.8);
    const reason = win ? (rnd() < 0.8 ? 'tp' : 'time') : (rnd() < 0.7 ? 'sl' : rnd() < 0.5 ? 'time' : 'gap');
    closed.push({ sym, en, ex: r2(en * (1 + move)), sh: Math.max(1, Math.floor(300 / en)), reason, exitDate: back(agoFrom + Math.floor(rnd() * agoSpan)) });
  }
  return closed;
};

// A: exits within the paper window (fills at least three sessions after paper start).
const closed = fillClosed(named.map(([sym, en, ex, sh, reason, ago]) => ({ sym, en, ex, sh, reason, exitDate: back(ago) })), 38, 0.53, 1.12, 7, 52);
// Snapshots and paper_state of a bracket strategy: equity curve from `day0`, open orders marked at the last close.
const bracketBook = (id, target, vol, day0, openRows) => {
  const eq = curve(target, vol, day0);
  const held = openRows.reduce((a, [, , sh, , cur]) => a + sh * cur, 0);
  eq.forEach((e, i) => { if (i >= day0) snapshots.push([id, sessions[i], i === day0 ? e : r4(e - (i === LAST ? held : 0)), e]); });
  paperState.push([id, r4(eq[LAST] - held), eq[LAST], false]);
};
bracketBook('A', 0.021, 3.3, 0, open);

// --- C: A's picks minus the news check's vetoes (handover D2) --------------------
// Tonight's checks for `session`, A's ranked list: LRCX vetoed (earnings in the window), MU failed
// (LLM timeout: no trade, design §8), WBD vetoed (buyout talks). GE and CSCO fill C's two free
// slots; PANW is allowed but C has no slot left.
const cPicks = [
  [1, 'GE', 'GE Aerospace', 273.18, 271.40, 278.90, 260.15, 1,
    'Strategy C takes the same GE dip as Strategy A. The news check read six recent headlines, all routine contract and product news with no earnings date in the next five sessions, so it let the pick through.'],
  [2, 'CSCO', 'Cisco Systems', 67.42, 66.85, 68.30, 64.70, 4,
    'Cisco slipped to the bottom of its two-week range, the same setup Strategy A sees. Its recent news is product launches and analyst notes without a rating change, so the news check allowed it.'],
];
// [symbol, company, shares, entry, current, tp, sl, days held]
const cOpen = [
  ['AMZN', 'Amazon', 2, 221.50, 218.10, 228.90, 212.40, 3],
  ['PG', 'Procter & Gamble', 2, 165.20, 167.05, 169.40, 160.10, 2],
];
const cClosed = fillClosed([], 14, 0.55, 1.2, 1, 22);
bracketBook('C', 0.012, 2.6, C_DAY0, cOpen);

const brackets = [
  { id: 'A', picks, open, closed },
  { id: 'C', picks: cPicks, open: cOpen, closed: cClosed },
];

// news_vetoes rows for C's pending session: [rank, symbol, company, verdict, reason, headline count, earnings date]
const VETO_DECIDED = new Date(Date.now() - 4 * 60_000); // the veto step runs after `nightly`, before `paper`
const thirdSession = nextWeekday(nextWeekday(session, 1), 1);
const VETO_CHECKS = [
  [1, 'GE', 'GE Aerospace', 'allow', 'Headlines are routine contract and product news with no event risk in the next five sessions.', 6, null],
  [2, 'LRCX', 'Lam Research', 'veto', `Lam Research reports quarterly earnings on ${thirdSession}, inside the holding window.`, 9, thirdSession],
  [3, 'CSCO', 'Cisco Systems', 'allow', 'Product launches and analyst notes only; no downgrade, legal or earnings news.', 4, null],
  [4, 'MU', 'Micron Technology', 'failed', 'LLM request failed: timed out after 30s', 11, null],
  [5, 'PANW', 'Palo Alto Networks', 'allow', 'Recent coverage is general sector commentary with no company-specific event.', 3, null],
  [6, 'WBD', 'Warner Bros. Discovery', 'veto', 'Reports of buyout talks with a rival studio are merger news inside the holding window.', 14, null],
];
const SOURCES = ['Reuters', 'Benzinga', 'Yahoo', 'MarketWatch'];
const newsVetoes = VETO_CHECKS.map(([rank, sym, name, verdict, reason, k, earnings]) => [
  'C', session, rank, sym, verdict, reason, 'glm-5.3', 'c-veto-v1',
  JSON.stringify(Array.from({ length: k }, (_, j) => ({
    id: 900000 + rank * 100 + j,
    datetime: new Date(VETO_DECIDED.getTime() - (j + 1) * 3 * 3_600_000).toISOString().slice(0, 19) + 'Z',
    source: SOURCES[j % SOURCES.length],
    headline: `${name}: demo headline ${j + 1}`,
  }))),
  earnings, VETO_DECIDED.toISOString(),
]);

const rows = { strategies, snapshots, paperState, bookPositions, bookTargets, bookTrades, picks, open, closed,
  cPicks, cOpen, cClosed, newsVetoes };

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
    book_targets, book_fills, book_trades, dividends, news_vetoes, strategies RESTART IDENTITY CASCADE`);

  for (const s of strategies)
    await c.query(`INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id, paper_start, params)
      VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)`,
    [s.id, s.name, s.sub, s.icon, s.champion, s.benchmark, s.sort, s.engine, s.rulesId, s.paperStart, JSON.stringify(s.params)]);

  await c.query(`INSERT INTO runs (started_at, finished_at, status, data_date, session_date, is_demo, paper_status, paper_finished_at)
    VALUES (now() - interval '5 minutes', now() - interval '2 minutes', 'success', $1, $2, true, 'success', now())`, [dataDate, session]);
  await c.query('INSERT INTO fx_rates (date, usd_idr) VALUES ($1, $2)', [dataDate, RATE]);

  const bar = (sym, close) => c.query('INSERT INTO bars VALUES ($1,$2,$3,$3,$3,$3,1000000) ON CONFLICT DO NOTHING', [sym, dataDate, close]);
  for (const b of brackets) {
    for (const [slot, sym, name, last, lim, tp, sl, sh, why] of b.picks) {
      await c.query(`INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, limit_price, tp_price, sl_price, shares, explanation, status)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,'pending')`, [b.id, session, slot, sym, name, last, lim, tp, sl, sh, why]);
      await bar(sym, last);
    }

    for (const [i, [sym, name, sh, entry, cur, tp, sl, days]] of b.open.entries()) {
      const fill = back(days - 1);
      await c.query(`INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, limit_price, tp_price, sl_price, shares, status, fill_date, fill_price, days_held, mark)
        VALUES ($1,$2,$3,$4,$5,$6,$6,$7,$8,$9,'open',$2,$6,$10,$11)`, [b.id, fill, i + 1, sym, name, entry, tp, sl, sh, days, cur]);
      await bar(sym, cur);
    }

    for (const t of b.closed) {
      const pnl = (t.ex - t.en) * t.sh - FEE * (t.ex + t.en) * t.sh;
      const filled = nextWeekday(t.exitDate, -3);
      const tp = t.reason === 'tp' ? t.ex : r2(t.en * 1.025);
      const sl = t.reason === 'sl' ? t.ex : r2(t.en * 0.96);
      await c.query(`INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, limit_price, tp_price, sl_price, shares, status,
          fill_date, fill_price, days_held, exit_date, exit_price, exit_reason, pnl_usd)
        VALUES ($1,$2,1,$3,$4,$5,$5,$6,$7,$8,'closed',$2,$5,3,$9,$10,$11,$12) ON CONFLICT DO NOTHING`,
      [b.id, filled, t.sym, company[t.sym], t.en, tp, sl, t.sh, t.exitDate, t.ex, t.reason, pnl.toFixed(4)]);
    }
  }
  await bar('SPY', spy[LAST]);

  for (const r of newsVetoes)
    await c.query(`INSERT INTO news_vetoes (strategy_id, session_date, rank, symbol, verdict, reason, model, prompt_version, headlines,
        earnings_date, decided_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)`, r);

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
    UNION ALL SELECT 'equity_snapshots', count(*)::int FROM equity_snapshots
    UNION ALL SELECT 'news_vetoes', count(*)::int FROM news_vetoes ORDER BY what`);
  console.log(`demo seeded: paper start ${PAPER_START}, session ${session}, data ${dataDate}`, counts.rows);
} catch (e) {
  await c.query('ROLLBACK').catch(() => {});
  throw e;
} finally {
  c.release();
  await pool.end();
}
````
**Impact:** The seed now needs migration 004 applied first (TRUNCATE names `news_vetoes`; the run order is `db:migrate` then `db:seed-demo`, as today). Its safety checks (refuses once real runs, bars or paper state exist) are unchanged, so it can never touch the live Neon database after the paper clock started.

### Step 16: `web/package_readme.md` (added by reconciliation: the file is under `web/**`, so it is this phase's)
**File:** `web/package_readme.md`
**Change:** documentation only; each Old text is quoted from `HEAD` (no other phase edits this file).

16a. Layout block. Replace
```
    strategy.ts             Engine, Gate, engineOf, parseGate, shortLabel        (pure)
    metrics.ts              Snapshot, Metrics, strategyMetrics, checklist          (pure)
```
with
```
    strategy.ts             Engine, Gate, engineOf, parseGate, shortLabel, checksNews (pure)
    metrics.ts              Snapshot, Metrics, strategyMetrics, gateItem, checklist (pure)
    vetoes.ts               Verdict, Veto, parseVerdict, vetoSheet, checkedLine, headlinesLabel, noCheckLine (pure; P6)
```

16b. `### lib/strategy.ts (pure)` code block and bullets. Replace
```
type Gate = { passed: boolean; note: string | null };
```
with
```
type Gate = { passed: boolean; applicable: boolean; note: string | null };
```
replace `function shortLabel(name: string, id: string): string;` with
```
function shortLabel(name: string, id: string): string;
function checksNews(id: string, specObject: unknown): boolean;
```
and replace the `parseGate` bullet with
```markdown
- `parseGate`: reads `strategies.params->'backtest_gate'` (contract C2). Missing, malformed, or anything other than `passed === true` reads as not passed; a blank note becomes `null`. A pass is never assumed. `applicable` is false only for an explicit `applicable: false` (Strategy C, an LLM strategy: design §1 item 5, handover D9), and a not-applicable gate always reads `passed: false`.
- `checksNews`: true for a strategy that runs the nightly news check (C): its spec `object` is `STRATEGY_C`, or its id is `C` before `paper` wrote a spec.
```

16c. `### lib/metrics.ts (pure)`: after `type CheckItem = ...;` add `function gateItem(gate: Gate): CheckItem;`, and append to the `checklist` bullet: ` Row 6 is `gateItem(gate)`: for a not-applicable gate it reads `{ label: 'Backtest gate', val: 'Not applicable', ok: false }` (plus the note), so such a strategy never passes all six.`

16d. New section after `### lib/monthly.ts (pure)`'s block (before `### lib/data.ts`):
````markdown
### lib/vetoes.ts (pure, P6)

```ts
type Verdict = 'allow' | 'veto' | 'failed';
type Veto = { rank: number; symbol: string; verdict: Verdict; reason: string; headlineCount: number; earningsDate: string | null; decidedAt: string };
function parseVerdict(v: unknown): Verdict;                 // anything unknown -> 'failed'
type VetoSheet = { state: 'missing' } | { state: 'failed'; checked; reason } | { state: 'listed'; checked; allowed; rows: Veto[] };
function vetoSheet(rows: Veto[]): VetoSheet;
const checkedLine: (checked: number, allowed: number) => string;   // '8 checked · 5 allowed'
const headlinesLabel: (k: number) => string;                       // 'No headlines' | '1 headline' | '12 headlines'
const noCheckLine: (day: string, short: string) => string;
```

- `vetoSheet`: no rows → `missing`; every row `failed` with one shared reason → `failed` (shown once); else the `veto` and `failed` rows by rank with the counts.
- `noCheckLine`: the `missing` state's line, "No news check for {day}: A had no candidates, or the check did not run. {short} buys nothing this session." `veto` writes no rows on a night A has no candidates, so the app cannot tell that from a check that did not run, and says so.
````

16e. `### lib/data.ts`: in the `Strategy` bullet replace `` `id, name, sub, icon, isChampion, isBenchmark, engine, rulesId, paperStart, gate, isPaper, short` `` with `` `id, name, sub, icon, isChampion, isBenchmark, engine, rulesId, paperStart, gate, isPaper, short, checksNews` `` and append ` `checksNews` (P6) marks C, whose Positions view reads its verdicts.`; after the `pendingOrders` function bullet add:
```markdown
- `vetoes(strategyId, sessionDate): Promise<Veto[]>` (P6): every `news_vetoes` row for that strategy and session, by rank (`headlineCount = jsonb_array_length(headlines)`). Called only for `checksNews` strategies: their roster row and the table both come from migration 004.
```

16f. `### components/roster.ts`: in the `strategyIcon` bullet replace `` plus `brain-circuit` and `gavel` for old demo rows `` with `` `gavel` (C, migration 004), plus `brain-circuit` for old demo rows ``.

16g. `### app/(app)/leaderboard/view.ts (pure)`: replace `function scoreOf(items: { ok: boolean }[], gatePassed: boolean): Score;` with
```
type GateIn = { passed: boolean; applicable: boolean };
const NO_GATE: GateIn;                                              // not passed, applicable
function scoreOf(items: { ok: boolean }[], gate: GateIn): Score;
function monthsBg(look: Look): string;                              // butter -> stone (months sheet)
```
replace `` (`CARD_BGS` lav/sky/stone, `LINES`) `` with `` (`CARD_BGS` lav/sky/stone/butter, `LINES` ink/line-b/line-c/coral) `` and `cycling sheets past three` with `cycling sheets past four`; and append to the `scoreOf` bullet: ` A not-applicable gate (C) is never ready and reads "Paper only. No backtest gate. / Real money needs an owner decision" (handover D9).`

16h. Configuration, the `db:seed-demo` bullet: replace `Roster: SPY (champion, buy and hold), A (bracket), F4-MOM12-N20-TREND and F1-SPY-SMA200-M (monthly book strategies, deciding on each month's first session).` with `Roster: SPY (champion, buy and hold), A (bracket), F4-MOM12-N20-TREND and F1-SPY-SMA200-M (monthly book strategies, deciding on each month's first session), and C (bracket, its own younger clock, gate `applicable: false`). Needs migration 004 applied first.` and replace `` `book_positions`, `book_targets`, `book_trades`. `` with `` `book_positions`, `book_targets`, `book_trades`, and six `news_vetoes` rows for C's pending session. ``; in the `npm test` bullet add `vetoes` to the list of pure modules.

16i. Gotchas: after the bullet starting `- The gate defaults to not passed`, add
```markdown
- C's gate is `applicable: false`: its checklist reads 5/6 at best forever, and the score line says real money needs an owner decision (D9).
- Positions for C shows "Vetoed tonight" for the pending session. No rows there means A had no candidates or the news check did not run; the app cannot tell which (`noCheckLine`).
```
**Impact:** documentation only.

## Verification

**Build:** `cd web && npx tsc --noEmit`
**Tests:** `cd web && npx vitest run` — expect 10 files, 83 tests (65 today + 18).
**Re-verified by the reconciler (2026-10-04)** on a scratch copy of `web/` with every code block of this
plan applied as written (whole files copied, the three diffs applied with `patch -p1`), including the
reconciliation's `noCheckLine` change: vitest 10 files / 83 tests passed, `tsc --noEmit` clean,
`node scripts/seed-demo.mjs --dry-run` prints 5 strategies and `newsVetoes: 6`.
**Seed (local only, never Neon, never `.env.local`'s URL):**
1. `docker start seer-pg`; `docker exec seer-pg psql -U postgres -c "CREATE DATABASE seer_p6_check"`.
2. Apply `db/migrations/001..004` in order (`docker exec -i seer-pg psql -v ON_ERROR_STOP=1 -U postgres -d seer_p6_check < db/migrations/00N_*.sql`).
3. The seed imports `@neondatabase/serverless` `Pool`, which speaks Neon's websocket protocol, not plain Postgres. To run it locally, copy `seed-demo.mjs` into a scratch directory whose `node_modules/@neondatabase/serverless/index.js` re-exports `pg`'s `Pool` and an empty `neonConfig` (plus `npm i pg ws` there), then `DATABASE_URL_UNPOOLED=postgresql://postgres:pg@localhost:55432/seer_p6_check node seed-demo.mjs`. Expected counts: `news_vetoes 6`, `orders pending 5`, `orders open 5`, `orders closed 49`, `equity_snapshots 293`, `book_positions 14`, `book_trades 6`. `node web/scripts/seed-demo.mjs --dry-run` needs no database: 5 strategies, 293 snapshots, 6 newsVetoes.
4. Check: `SELECT id, params->'backtest_gate' FROM strategies WHERE id='C'` → `applicable: false`; `SELECT rank, symbol, verdict, jsonb_array_length(headlines) FROM news_vetoes ORDER BY rank` → 6 rows, ranks 1–6.

**Manual check (done during planning on the seeded scratch database, scratch-only shims for `lib/db.ts` and `currentUser`):**
- Positions `?s=C`, 414 px light: switcher has 5 icon buttons (gavel last); 2 paper orders (GE, CSCO); "Vetoed tonight" stone sheet with "6 checked · 3 allowed", rows LRCX (Veto, "9 headlines · earnings Oct 7"), MU (Failed, "11 headlines"), WBD (Veto); each with a "Why vetoed"/"Why it failed" toggle. 1440 px dark: two-column list, chips legible.
- With every row set `failed` with one reason: "News check failed for Mon, Oct 5: C sits this session out." + the reason, "6 checked · 0 allowed". With no rows: "No news check for Mon, Oct 5: A had no candidates, or the check did not run. C buys nothing this session.", no count chip (text changed by reconciliation after the planner's screenshots; same element and style).
- Leaderboard `?s=C`: score "1/6 · Paper only. No backtest gate. / Real money needs an owner decision"; row 6 "Backtest gate · Not applicable" with ✕; note under the rows; legend and chart show C in coral; C card butter; five cards in one desktop row; mobile months sheet stone under the butter checklist.
- History: All + A/F4/F1/C filter buttons. Today: unchanged (SPY champion, no buys).
**Exit criteria:** vitest and `tsc --noEmit` green; the seed applies on a 001–004 database; C renders in Positions (with "Vetoed tonight"), History, Leaderboard, Month by month and the checklist at 414 px and desktop, light and dark; Today still shows no buys; nothing in `engine/` changed.

## Handoffs

- **Phase 7 (docs, R5):** the runbook's "what the UI shows" for the veto states quotes the three Positions texts above (the no-rows line is `noCheckLine`'s) and the score line. `web/package_readme.md` is this phase's (Step 16); phase 7 does not touch it.
- **Phase 4 (R2), zero candidates — settled by reconciliation:** a night with zero candidates writes no rows, so the app cannot tell it from a check that did not run (or one that came after Paper decided, H1). No marker table is added; the no-rows state shows the honest neutral line `noCheckLine` ("No news check for {date}: A had no candidates, or the check did not run. C buys nothing this session.").
- **Phase 2 (R1/R2):** this phase relies on `backtest_gate(C)` carrying `"applicable": false` and C's spec `object` being `"STRATEGY_C"` (K4). If phase 2 names the object differently, `checksNews` still matches by id `C`.

## Risks

- **Deploy order:** Vercel deploys on merge, before the nightly `Migrate` applies 004 on Neon. Until then the C row does not exist, so no page queries `news_vetoes`; nothing else in the web references 004. Safe by construction (Design decisions, "Which strategies read verdicts").
- Coral as a line colour is ~2.6:1 against the white chart sheet in light mode (the existing `--line-c` is ~2.8:1); acceptable for a 2 px line with a text legend, same class as today's lines.

## Rollback

Revert this phase's commit: all changes are inside `web/`, additive to the schema reads (one extra
selected column, one new query), and the seed returns to the four-strategy roster. The engine and
the database are untouched by this phase.

