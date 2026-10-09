> Adopted from `GOLIVE_CHECKLIST_COUNT_PLAN.md` phase 1. Source: `.workflows/plan/golive-checklist-count/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: Count the rules once, where the rules are

**Plan set:** `GOLIVE_CHECKLIST_COUNT_PLAN.md`
**Analysis:** `20261009-123010-G6K4_code_analyzer.md`
**Satisfies:** R1 (the Leaderboard scores out of 6 over 5 rows and can never say "Ready for real money"), R2 (`/sera/how` still states the pre-§13 paper bar)
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `web`

All quotations below are from the worktree at `/home/miftah/.worktrees/seer/golive-checklist-count`,
base `origin/main` @ `d8c0cab`, and were read on 2026-10-09. Every line number was verified there.

---

## Goal

`web/lib/metrics.ts` becomes the one place in the web that says how many go-live rules there are,
exporting `CHECKLIST_RULES = 5` beside the `checklist()` that returns them, with a test that fails
the moment the list and the count disagree. The Leaderboard's `CHECKS` becomes that constant
instead of a literal `6`, its "all six" copy is derived from the number through a word lookup, and
its `scoreOf` suite drives real `checklist()` output rather than hand-built six-element fixtures —
so a strategy that passes all five now reads `5/5` and "Ready for real money". `/sera/how` stops
spelling the paper bar a second time: `PAPER_MONTHS`/`PAPER_TRADES` are deleted and the pipeline's
paper stage reads `MIN_PAPER_MONTHS` from `lib/golive.ts`.

## Interface Contract

**Creates:**
- `lib/metrics.CHECKLIST_RULES` (`web/lib/metrics.ts`, new line after `checklist`'s closing brace)
- module-private `NUMBER_WORDS`, `numberWord`, `ALL`, `ALL_CAP` in
  `web/app/(app)/leaderboard/view.ts` (not exported)

**Deletes:**
- `app/sera/how/view.PAPER_MONTHS` (`web/app/sera/how/view.ts:21`)
- `app/sera/how/view.PAPER_TRADES` (`web/app/sera/how/view.ts:22`)
- the test `it('is never ready with fewer than six items', …)`
  (`web/app/(app)/leaderboard/view.test.ts:294-296`) — it pins the bug
- the local helper `const items = (oks: boolean[]) => …`
  (`web/app/(app)/leaderboard/view.test.ts:277`), scoped to the `scoreOf` describe and used
  nowhere else in the file

**Renames:** none

**Signature changes:** none. `scoreOf(items, gate)`, `checklist(m, spyReturn, gate)`,
`gateItem(gate)` and `Score`/`GateIn`/`CheckItem` all keep their exact shapes.

**Value changes:**
- `CHECKS`: `6` -> `CHECKLIST_RULES` (= `5`). This is the only behavioural change in the phase.
- No threshold moves: `MIN_PAPER_MONTHS` stays `18`, `MAX_DRAWDOWN` stays `0.2`, the profit-factor
  bar stays `1.3`, `data/lab.json`'s `gate.minTrades` stays `100`.

**Rendered-string changes** (exactly three, plus the `/sera/how` stage):
- `'All six pass.'` -> `'All five pass.'`
- `'all six pass'` -> `'all five pass'`
- `` `At least ${PAPER_MONTHS} months`, `and ${PAPER_TRADES} trades,`, 'no real money' `` ->
  `` `At least ${MIN_PAPER_MONTHS} months`, 'of forward paper,', 'no real money' ``

**Requires (from earlier phases):** nothing — this is the only phase.

**Leaves alone (owned by nobody, deliberately untouched):**
- everything under `engine/`, `db/`, `docs/`, `web/data/`
- `web/lib/sera/derive.ts` — `CONDITION_KEYS`'s `trades: '>= 100 trades'` is the **lab dev gate**,
  still live (`data/lab.json` `gate.minTrades = 100`)
- `web/app/sera/how/view.test.ts` — its `'At least 100 trades'` and its `'cleared all six at once'`
  expectations are the same lab gate and are correct
- `web/app/(app)/leaderboard/page.tsx` — it imports `scoreOf` and `NO_GATE` but **not** `CHECKS`
  (verified: `page.tsx:16-19`), so nothing there needs to move
- `web/lib/golive.test.ts`, `web/app/sera/journal/view.test.ts`, `web/app/sera/methods/view.ts`,
  `web/app/sera/how/page.tsx` — every other "six" in `web/` is the lab's six hurdles

## Files

| File | Action | What changes |
|---|---|---|
| `web/lib/metrics.ts` | modify | adds `CHECKLIST_RULES = 5` after `checklist` (new lines 89-101) |
| `web/lib/metrics.test.ts` | modify | imports `CHECKLIST_RULES`; adds the length coupling test |
| `web/app/(app)/leaderboard/view.ts` | modify | `CHECKS = CHECKLIST_RULES`; word lookup; three strings; two docstrings (lines 17, 377-378, 388-403) |
| `web/app/(app)/leaderboard/view.test.ts` | modify | the whole `scoreOf` describe (lines 276-309) is rewritten against real `checklist()` output; import line 2 and line 5 grow |
| `web/app/sera/how/view.ts` | modify | deletes two constants, imports `MIN_PAPER_MONTHS`, rewords the `paper` stage |
| `web/lib/golive.ts` | modify | one word in a docstring (line 6) |
| `web/package_readme.md` | modify | six stale statements (lines 186, 376, 394, 418, 791, 829) plus a new Last Updated entry at line 4 |

---

## Implementation Steps

### Step 1: `CHECKLIST_RULES` — the one definition of the count

**File:** `web/lib/metrics.ts:87` (append after the closing `}` of `checklist`; the file currently
ends at line 87)

**Change:** add the exported count immediately below the list it counts, with the docstring that
explains why the engine's twin has four.

**Code** — append exactly this (one blank line after the current line 87, then):

```ts

/**
 * How many rules `checklist` returns. THE definition of that number in `web/`: nothing else may
 * spell it. `metrics.test.ts` asserts `checklist(...)` has exactly this many rows, and
 * `app/(app)/leaderboard/view.ts`'s `CHECKS` is this constant rather than a literal.
 *
 * It is here, beside the list, because a literal elsewhere is exactly how this went wrong: design
 * §13 (2026-10-07, commit `ba8a05b`) folded "≥ 3 months forward AND ≥ 100 trades" into "≥ 18
 * months forward" and shortened this list from six rows to five, while the leaderboard kept its
 * own `CHECKS = 6`. It then scored five rendered rows out of six and `ready` — which requires
 * `items.length === CHECKS` — became unreachable, so a strategy that passed everything read 5/6
 * and never said "Ready for real money".
 *
 * The engine's twin, `backtest.metrics.checklist`, returns FOUR and is not wrong: its missing
 * fifth is the backtest gate, which reads `strategies.params.backtest_gate` — a roster fact no
 * backtest can evaluate — so the web appends `gateItem` and the engine does not. The engine/web
 * parity test compares labels, not lengths, and needs no change when this number moves.
 */
export const CHECKLIST_RULES = 5;
```

**Impact:** new export; no behaviour change on its own.

---

### Step 2: the test that would have caught the 2026-10-07 drift

**File:** `web/lib/metrics.test.ts:2` (import) and `:41` (new test inside the `checklist` describe)

**Change (a) — the import.** Line 2 today:

```ts
import { checklist, gateItem, strategyMetrics } from './metrics';
```

becomes:

```ts
import { checklist, CHECKLIST_RULES, gateItem, strategyMetrics } from './metrics';
```

**Change (b) — the coupling test.** Lines 37-41 today read:

```ts
describe('checklist', () => {
  const base = { totalReturn: 0.068, winRate: 0.58, profitFactor: 1.42, maxDrawdown: 0.079, trades: 84, months: 3.0 };

  // `base` is 3 months, which no longer passes item 1: design §13 (2026-10-07) raised it to 18
  // and DELETED the trades clause, so `trades` can no longer make or break any row here.
```

Insert the new test between `base` and that comment, so lines 37-43 become:

```ts
describe('checklist', () => {
  const base = { totalReturn: 0.068, winRate: 0.58, profitFactor: 1.42, maxDrawdown: 0.079, trades: 84, months: 3.0 };

  // The coupling that did not exist on 2026-10-07. Design §13 shortened this list from six rows to
  // five and nothing in TypeScript failed, so `leaderboard/view.ts`'s `CHECKS = 6` went on scoring
  // five rendered rows out of six with "Ready for real money" unreachable. This is the test that
  // would have caught that: the count and the list it counts can no longer drift apart in silence.
  it('returns exactly CHECKLIST_RULES rows, whatever the gate says', () => {
    expect(checklist(base, 0.046, PASSED)).toHaveLength(CHECKLIST_RULES);
    expect(checklist(base, 0.046, FAILED)).toHaveLength(CHECKLIST_RULES);
    expect(checklist(base, 0.046, NOT_APPLICABLE)).toHaveLength(CHECKLIST_RULES);
  });

  // `base` is 3 months, which no longer passes item 1: design §13 (2026-10-07) raised it to 18
  // and DELETED the trades clause, so `trades` can no longer make or break any row here.
```

**Impact:** `PASSED`, `FAILED` and `NOT_APPLICABLE` are already defined at module scope
(`metrics.test.ts:7-9`), so no fixture is added. The two existing `expect(items).toHaveLength(5)`
assertions at lines 60 and 67 stay exactly as they are — they are independent literal pins of the
same fact and removing them would weaken the file. Every other test in the file is untouched.

---

### Step 3: `CHECKS` becomes the constant, and the copy is built from it

**File:** `web/app/(app)/leaderboard/view.ts`

**Change (a) — the import, line 17.** Today:

```ts
import type { Snapshot } from '../../../lib/metrics';
```

becomes (the file's style uses inline `type` modifiers elsewhere — see `view.test.ts:4-8` — and
this keeps the module to a single import line):

```ts
import { CHECKLIST_RULES, type Snapshot } from '../../../lib/metrics';
```

This is the only import change. `lib/metrics.ts` imports only `./strategy` (types) and
`./golive`, and `lib/golive.ts` imports only `./format`, which imports nothing — so no database
module is pulled into `view.ts`, which is the constraint the file's header comment protects.

**Change (b) — lines 377-378.** Today:

```ts
/** Design §1's five rules plus "Backtest gate passed". */
export const CHECKS = 6;
```

Replace those two lines with:

```ts
/**
 * How many rules the score divides by: `lib/metrics.ts`'s `CHECKLIST_RULES`, never a literal.
 *
 * The old comment here said "§1's five rules plus Backtest gate passed", which is the fossil that
 * produced the bug: that was true before design §13 (2026-10-07), when §1 had five forward clauses
 * and the gate made six. Today §1 has five conditions and the backtest gate IS the fifth of them.
 */
export const CHECKS = CHECKLIST_RULES;

/**
 * 'five' for 5. Small on purpose — the verdict lines name the rule count in words, and words that
 * are typed rather than derived are what outlived §13 here. Past the lookup it falls back to the
 * digits, which reads oddly but can never be wrong.
 */
const NUMBER_WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'];
const numberWord = (n: number): string => NUMBER_WORDS[n] ?? String(n);

/** 'all five', continuing a line; and 'All five', leading one. */
const ALL = `all ${numberWord(CHECKS)}`;
const ALL_CAP = `${ALL[0].toUpperCase()}${ALL.slice(1)}`;
```

**Change (c) — the `scoreOf` docstring and body, lines 388-404.** Today:

```ts
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
```

Replace the whole block with:

```ts
/**
 * The checklist score and its two-line verdict. Never "Ready for real money" unless every rule
 * passes, and never for a strategy whose backtest item is not applicable (C, handover D9): real
 * money for it would need an explicit owner decision even if the four forward rules pass.
 *
 * `items.length === CHECKS` is load-bearing and stays. `page.tsx` passes `items = []` for a
 * strategy with no gate row at all; a denominator of `items.length` would render that as 0/0 and
 * let a missing checklist read like a passing one. A fixed denominator makes it 0/5, "Paper only".
 */
export function scoreOf(items: { ok: boolean }[], gate: GateIn): Score {
  const passed = items.filter(i => i.ok).length;
  const ready = gate.applicable && items.length === CHECKS && passed === CHECKS;
  const lines: [string, string] = !gate.applicable
    ? ['Paper only. No backtest gate.', 'Real money needs an owner decision']
    : ready
      ? [`${ALL_CAP} pass.`, 'Ready for real money']
      : gate.passed
        ? ['Paper trading until', `${ALL} pass`]
        : ['Paper only.', 'Backtest gate not passed'];
  return { passed, total: CHECKS, ready, lines };
}
```

The logic is byte-for-byte what it was; only `CHECKS`'s value and the two interpolated strings
move. `${ALL_CAP} pass.` evaluates to `'All five pass.'` and `${ALL} pass` to `'all five pass'`,
which is exactly the current capitalisation: the first leads a line, the second continues one.

**Impact:** this is the user-visible fix. `page.tsx:147` renders `{score.passed}/{score.total}`,
which becomes `x/5` over the five rows `page.tsx` already draws, and `ready` is reachable for the
first time since 2026-10-07.

> **Note on "the five forward rules" in the old docstring (line 391).** That clause was stale too:
> there are **four** forward rules, the gate being the fifth rule overall. The replacement above
> says four. It is the same fossil as the `CHECKS` comment, in the same sentence block, so it is
> fixed here rather than handed off.

---

### Step 4: the `scoreOf` suite drives the real `checklist()`

**File:** `web/app/(app)/leaderboard/view.test.ts`

This is the most important edit in the phase: the suite's six-element fixtures are what let the
drift through, and `it('is never ready with fewer than six items', …)` actively asserts the bug.

**Change (a) — line 2.** Today:

```ts
import type { Snapshot } from '../../../lib/metrics';
```

becomes:

```ts
import { checklist, type Metrics, type Snapshot } from '../../../lib/metrics';
```

**Change (b) — the `./view` import, lines 4-8.** Today:

```ts
import {
  CHECKS, compare, LOOK_PERIOD, looks, MIN_COMMON_SESSIONS, MIN_RANKED, monthLabel, monthLines,
  NO_GATE, pickResearch, researchOf, retiredLabel, scoreOf, sinceStartLine, spyOverSpan,
  windowLine, type RankIn, type RosterIn,
} from './view';
```

becomes (adds `type GateIn`, used by the local `checks` helper):

```ts
import {
  CHECKS, compare, LOOK_PERIOD, looks, MIN_COMMON_SESSIONS, MIN_RANKED, monthLabel, monthLines,
  NO_GATE, pickResearch, researchOf, retiredLabel, scoreOf, sinceStartLine, spyOverSpan,
  windowLine, type GateIn, type RankIn, type RosterIn,
} from './view';
```

**Change (c) — replace lines 276-309 in full.** That is the entire `describe('scoreOf', …)` block,
from `describe('scoreOf', () => {` through its closing `});`. Today it reads:

```ts
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
```

Replace it with:

```ts
describe('scoreOf', () => {
  const PASSED = { passed: true, applicable: true };
  const FAILED = { passed: false, applicable: true };
  const NOT_APPLICABLE = { passed: false, applicable: false };

  // Driven by the REAL `checklist()`, not by hand-built arrays. Hand-built fixtures are how the
  // 2026-10-07 drift got through: six-element arrays agreed with `CHECKS = 6` for ever while
  // production fed `scoreOf` five rows, so the suite stayed green over an unreachable `ready`.
  // Whatever the rule count becomes next, these cases are built from the list itself.
  const SPY = 0.046;
  /** Passes all four forward rules: 24 months ≥ 18, +6.8% beats SPY's +4.6%, PF 1.42, drawdown 7.9%. */
  const STRONG: Metrics = {
    totalReturn: 0.068, winRate: 0.58, profitFactor: 1.42, maxDrawdown: 0.079, trades: 84, months: 24,
  };
  /** Fails two of them: 3.0 months (< 18) and a 1.10 profit factor (< 1.3). */
  const WEAK: Metrics = { ...STRONG, months: 3.0, profitFactor: 1.1 };
  const checks = (m: Metrics, gate: GateIn) => checklist(m, SPY, gate);

  it('scores out of the rules the checklist returns, and says paper only while the gate has not passed', () => {
    const sc = scoreOf(checks(STRONG, FAILED), FAILED);
    expect(sc).toEqual({ passed: 4, total: CHECKS, ready: false, lines: ['Paper only.', 'Backtest gate not passed'] });
    // A strategy with no gate row at all: page.tsx passes []. It must read 0 of CHECKS, never 0/0.
    expect(scoreOf([], NO_GATE)).toEqual({
      passed: 0, total: CHECKS, ready: false, lines: ['Paper only.', 'Backtest gate not passed'],
    });
  });

  it('says paper trading until all five pass when the gate passed but a forward rule did not', () => {
    const sc = scoreOf(checks(WEAK, PASSED), PASSED);
    expect(sc.passed).toBe(3);
    expect(sc.ready).toBe(false);
    expect(sc.lines).toEqual(['Paper trading until', 'all five pass']);
  });

  // THE regression pin for the reported bug. On `main` at d8c0cab this read 5 of 6, ready: false,
  // "Paper trading until / all six pass" — a strategy that passed every rule could never go live.
  it('is ready when all five pass with a passed gate', () => {
    const sc = scoreOf(checks(STRONG, PASSED), PASSED);
    expect(sc.ready).toBe(true);
    expect(sc.passed).toBe(5);
    expect(sc.total).toBe(5);
    expect(sc.lines).toEqual(['All five pass.', 'Ready for real money']);
  });

  // Replaces 'is never ready with fewer than six items', which asserted that five passing rules are
  // not ready — i.e. it pinned the bug, using production's own input as the counter-example. The
  // real invariant is this one: the number the score divides by IS the number of rows rendered.
  it('divides by the number of rows checklist actually returns', () => {
    expect(scoreOf(checks(STRONG, PASSED), PASSED).total).toBe(checks(STRONG, PASSED).length);
    expect(CHECKS).toBe(checks(STRONG, NOT_APPLICABLE).length);
  });

  it('says real money needs an owner decision when the gate is not applicable (C, handover D9)', () => {
    const sc = scoreOf(checks(STRONG, NOT_APPLICABLE), NOT_APPLICABLE);
    expect(sc).toEqual({
      passed: 4, total: CHECKS, ready: false,
      lines: ['Paper only. No backtest gate.', 'Real money needs an owner decision'],
    });
  });

  it('is never ready when the gate is not applicable, whatever the rules say', () => {
    const sc = scoreOf(checks(STRONG, NOT_APPLICABLE), NOT_APPLICABLE);
    expect(sc.ready).toBe(false);
    expect(sc.lines[1]).toBe('Real money needs an owner decision');
  });
});
```

**Arithmetic, verified against `lib/metrics.ts:61-87` so the implementer does not have to re-derive it:**

| case | months ≥ 18 | beats SPY | PF ≥ 1.3 | maxDD ≤ 0.2 | gate | `passed` |
|---|---|---|---|---|---|---|
| `STRONG` + `FAILED` | 24 ✓ | 0.068 > 0.046 ✓ | 1.42 ✓ | 0.079 ✓ | ✗ | **4** |
| `STRONG` + `PASSED` | ✓ | ✓ | ✓ | ✓ | ✓ | **5**, `ready` |
| `STRONG` + `NOT_APPLICABLE` | ✓ | ✓ | ✓ | ✓ | ✗ (`Not applicable`) | **4**, never ready |
| `WEAK` + `PASSED` | 3.0 ✗ | ✓ | 1.1 ✗ | ✓ | ✓ | **3** |
| `[]` + `NO_GATE` | — | — | — | — | — | **0**, `total` 5 |

**Impact:** `GateIn` is structurally identical to `lib/strategy`'s `Gate`
(`{ passed: boolean; applicable: boolean }`, verified at `lib/strategy.ts:16`), so passing a
`GateIn` to `checklist` type-checks with no cast. The `items` helper disappears with the block —
it was declared inside this `describe` and is used nowhere else in the file (verified). Everything
from `describe('month rows', …)` at line 311 onwards, and everything above line 276, is untouched.

---

### Step 5 (R2): `/sera/how` stops spelling the paper bar a second time

**File:** `web/app/sera/how/view.ts`

**Grep result, as required before deleting the constants.** Searched `web/` for `PAPER_MONTHS` and
`PAPER_TRADES` across `*.ts`, `*.tsx` and `*.md`, excluding `node_modules`. Four hits outside the
definition site:

| hit | verdict |
|---|---|
| `app/sera/how/view.ts:116` (the `detail` array) | the only code use; rewritten in change (c) below |
| `package_readme.md:418` | documentation; corrected in Step 7 |
| `.workflows/plan/P1-WEB-08WD.md:74, 1346, 1347, 1440, 2051` | a shipped plan file, a historical record — **not** edited |
| `app/sera/how/view.test.ts` | **no hit.** Nothing pins these constants or the paper stage's strings |

So deleting them breaks no import and no test.

**Change (a) — the import block, lines 1-5.** Today:

```ts
// Pure helpers for /sera/how. No data access; page.tsx feeds the snapshot (structurally narrowed).
import { monthYear, type Era, type PipelineStage } from '../../../components/sera/diagrams/geometry';
import { CONDITION_KEYS, type ConditionKey } from '../../../lib/sera/derive';
import { CONDITION_TERM, type GlossaryKey } from '../../../lib/sera/glossary';
import type { Gate, LabMethod, LabSnapshot, LabTrial } from '../../../lib/sera/types';
```

becomes (the new import is in path order, between `components/` and `lib/sera/`):

```ts
// Pure helpers for /sera/how. No data access; page.tsx feeds the snapshot (structurally narrowed).
import { monthYear, type Era, type PipelineStage } from '../../../components/sera/diagrams/geometry';
// Design §1's paper bar before real money: MIN_PAPER_MONTHS = 18 months of forward paper, months
// alone since §13 (2026-10-07) deleted the trades clause — a trade count scales with how many
// names a book holds, not with how much evidence exists. Imported rather than spelled again: the
// local `PAPER_MONTHS = 3` / `PAPER_TRADES = 100` that used to sit below this block outlived that
// revision by two days. It is still absent from `snapshot.gate` — the lab never reaches paper by
// itself, so there is no carrier to read it from — which is why this one bar comes from
// `lib/golive.ts` while `gate.maxDrawdown` and every other lab bar still come from the snapshot.
import { MIN_PAPER_MONTHS } from '../../../lib/golive';
import { CONDITION_KEYS, type ConditionKey } from '../../../lib/sera/derive';
import { CONDITION_TERM, type GlossaryKey } from '../../../lib/sera/glossary';
import type { Gate, LabMethod, LabSnapshot, LabTrial } from '../../../lib/sera/types';
```

`lib/golive.ts` imports only `./format`, and `lib/format.ts` imports nothing at all (verified:
`lib/format.ts:1` is `const MINUS = '−';`). No lab snapshot, no `data/lab.json`, no database
module enters this page's bundle.

> This does **not** contradict `lib/golive.ts`'s own warning that "Pages that already hold a
> snapshot must read `gate.maxDrawdown` from it instead of importing this — `app/sera/how/view.ts`
> is the model." That warning is scoped to `gate.maxDrawdown`, which has a carrier in the snapshot;
> `how/view.ts` still reads `g.maxDrawdown` from the snapshot at line 95 (`pctLabel(g.maxDrawdown)`)
> and remains the model for exactly that. `MIN_PAPER_MONTHS` has no carrier, as `golive.ts:27-28`
> states, so there is nothing to read it from. Leave that docstring alone.

**Change (b) — delete lines 17-22 and the blank line that follows them.** Today:

```ts
/**
 * Design §1's paper bar before real money: at least 3 months and 100 trades on paper.
 * Not in snapshot.gate (the lab never reaches paper by itself). See the Phase 6 handoff to Phase 1.
 */
export const PAPER_MONTHS = 3;
export const PAPER_TRADES = 100;

/** The two bear markets inside the dev window (S&P 500 peak to trough). */
export const BEARS: Era[] = [
```

becomes:

```ts
/** The two bear markets inside the dev window (S&P 500 peak to trough). */
export const BEARS: Era[] = [
```

Leave exactly one blank line between the import block and the `BEARS` docstring.

**Change (c) — the `paper` stage, line 116.** Today:

```ts
    {
      key: 'paper',
      title: ['Paper trading'],
      detail: [`At least ${PAPER_MONTHS} months`, `and ${PAPER_TRADES} trades,`, 'no real money'],
      count: `${count(c.paper)} on paper`,
      countTip: 'Lab methods trading with pretend money now',
      fails: true,
    },
```

becomes:

```ts
    {
      key: 'paper',
      title: ['Paper trading'],
      detail: [`At least ${MIN_PAPER_MONTHS} months`, 'of forward paper,', 'no real money'],
      count: `${count(c.paper)} on paper`,
      countTip: 'Lab methods trading with pretend money now',
      fails: true,
    },
```

**Geometry, verified rather than assumed.** `Pipeline.tsx:50,58-59` lays `detail` out as one `<text>`
per entry at `detailY + j * 17`, so the stage's box height is a function of `detail.length` — the
array must stay **three** entries, and it does. `app/sera/how/view.test.ts:79-85` (which this phase
must not touch) enforces a per-line cap of 18 characters for any stage without a `weight > 1`, and
`paper` has no `weight`. Measured:

| line | chars | cap |
|---|---|---|
| `At least 18 months` | 18 | 18 ✓ |
| `of forward paper,` | 17 | 18 ✓ |
| `no real money` | 13 | 18 ✓ |

The neighbouring `test` stage runs 16 / 18 / 15 and the `idea` stage 16 / 15 / 17, so the new
block sits in the same visual envelope. Nothing in the Pipeline diagram's geometry moves.

**Impact:** `/sera/how` states design §1's bar as the owner set it on 2026-10-07, in months, with
no trades clause, from the same constant the Leaderboard judges against.

---

### Step 6: `lib/golive.ts` docstring

**File:** `web/lib/golive.ts:6`

**Change:** one word. Today:

```
 * there as `backtest.tuning.MAX_DRAWDOWN`, and it reaches the web twice over: here, for the
 * leaderboard's six-rule checklist in `lib/metrics.ts`, and in `data/lab.json`'s
 * `gate.maxDrawdown`, written by `lab.store.snapshot`. `golive.test.ts` asserts the two are the
```

becomes:

```
 * there as `backtest.tuning.MAX_DRAWDOWN`, and it reaches the web twice over: here, for the
 * leaderboard's five-rule checklist in `lib/metrics.ts`, and in `data/lab.json`'s
 * `gate.maxDrawdown`, written by `lab.store.snapshot`. `golive.test.ts` asserts the two are the
```

**Impact:** none. No value in this file changes; `MIN_PAPER_MONTHS` stays `18` and
`MAX_DRAWDOWN` stays `0.2`, and `golive.test.ts` keeps passing untouched.

---

### Step 7: `web/package_readme.md`

Six stale statements, not five. The analysis listed 186, 376, 394, 418 and 791; the worktree also
has **line 829**, which repeats the pre-§13 paper bar in the Gotchas section. All six line numbers
were verified in the worktree at `d8c0cab` and none had moved.

**Change (a) — the `lib/metrics.ts` signature block, line 182.** Today:

```ts
function checklist(m: Metrics, spyReturn: number | null, gate: Gate): CheckItem[];
```

becomes (adds the new export on the following line, before the closing fence at line 183):

```ts
function checklist(m: Metrics, spyReturn: number | null, gate: Gate): CheckItem[];
const CHECKLIST_RULES = 5;                                          // checklist's length; THE count
```

**Change (b) — line 186.** Today, in full:

```
- `checklist`: design §1 go-live rules, **six** items, all must hold: >= 3 months forward, >= 100 trades, beats SPY, profit factor >= 1.3, max drawdown <= 20% (`MAX_DRAWDOWN` / `MAX_DRAWDOWN_LABEL` from `lib/golive.ts`, raised from 15% on 2026-10-07; `golive.test.ts` asserts it equals `data/lab.json`'s `gate.maxDrawdown`, so the leaderboard can never judge at a bar the engine abandoned), and **Backtest gate passed** (from `gate`; carries `note` when the roster gives one). The gate parameter is required. Row 6 is `gateItem(gate)`: for a not-applicable gate it reads `{ label: 'Backtest gate', val: 'Not applicable', ok: false }` (plus the note), so such a strategy never passes all six.
```

Replace the whole line with:

```
- `checklist`: design §1 go-live rules, **five** items, all must hold: >= 18 months forward (`MIN_PAPER_MONTHS` / `MIN_PAPER_MONTHS_LABEL` from `lib/golive.ts`; design §13 replaced ">= 3 months forward AND >= 100 trades" with months alone on 2026-10-07, so no row counts trades any more), beats SPY, profit factor >= 1.3, max drawdown <= 20% (`MAX_DRAWDOWN` / `MAX_DRAWDOWN_LABEL` from `lib/golive.ts`, raised from 15% on 2026-10-07; `golive.test.ts` asserts it equals `data/lab.json`'s `gate.maxDrawdown`, so the leaderboard can never judge at a bar the engine abandoned), and **Backtest gate passed** (from `gate`; carries `note` when the roster gives one). The gate parameter is required. Row 5 is `gateItem(gate)`: for a not-applicable gate it reads `{ label: 'Backtest gate', val: 'Not applicable', ok: false }` (plus the note), so such a strategy never passes all five.
- `CHECKLIST_RULES`: how many rows `checklist` returns, exported beside it as THE definition of that number in `web/`. `leaderboard/view.ts`'s `CHECKS` is this constant rather than a literal, and `metrics.test.ts` asserts `checklist(...)` has exactly this length — the coupling that did not exist when §13 shortened the list and left `CHECKS = 6` scoring five rendered rows out of six. The engine's twin returns **four** and is not wrong: its missing fifth is the gate, a roster fact (`strategies.params.backtest_gate`) no backtest can evaluate, and the engine/web parity test compares labels, not lengths.
```

(The "carries `note`" clauses are preserved verbatim — they are separately stale, see **Handoffs**,
and correcting them is not this phase's requirement.)

**Change (c) — line 376, inside the `leaderboard/view.ts` signature block.** Today:

```ts
const CHECKS = 6;
```

becomes (the block aligns its trailing comments at column 68; `const CHECKS = CHECKLIST_RULES;` is
31 characters, so 36 spaces precede the `//`, matching `const NO_GATE: GateIn;` on line 381):

```ts
const CHECKS = CHECKLIST_RULES;                                     // 5; defined in lib/metrics.ts
```

**Change (d) — line 394.** Today:

```
- `scoreOf`: `ready` only when exactly six items are given and all pass; lines are "All six pass. / Ready for real money", else "Paper trading until / all six pass" when the gate passed, else "Paper only. / Backtest gate not passed". A not-applicable gate (C) is never ready and reads "Paper only. No backtest gate. / Real money needs an owner decision" (handover D9).
```

becomes:

```
- `scoreOf`: `ready` only when exactly `CHECKS` items are given and all pass; lines are "All five pass. / Ready for real money", else "Paper trading until / all five pass" when the gate passed, else "Paper only. / Backtest gate not passed". The word "five" in those strings is built from `CHECKS` through a small number-to-word lookup (digits past the lookup), so the copy can never name a count the score does not use — a hand-typed "six" is exactly what outlived design §13. The fixed denominator and the `items.length === CHECKS` guard are both deliberate: `page.tsx` passes `items = []` for a strategy with no gate row, which must read `0/5` "Paper only" and never `0/0`, which would let a missing checklist look like a passing one. A not-applicable gate (C) is never ready and reads "Paper only. No backtest gate. / Real money needs an owner decision" (handover D9).
```

**Change (e) — line 418.** Today the line ends:

```
... `honestyRules`, `dataFacts(data, gate)` (has / lacks), `BEARS` (2000-02, 2008-09) and `PAPER_MONTHS = 3` / `PAPER_TRADES = 100` (design section 1's paper bar; not in `snapshot.gate`).
```

Replace from " and `PAPER_MONTHS" to the end of the line, so the line ends:

```
... `honestyRules`, `dataFacts(data, gate)` (has / lacks) and `BEARS` (2000-02, 2008-09). The Pipeline's paper stage reads `MIN_PAPER_MONTHS` (18) from `lib/golive.ts`: design section 13 deleted the trades clause on 2026-10-07 and the local `PAPER_MONTHS = 3` / `PAPER_TRADES = 100` constants that outlived it are gone. The bar is still not in `snapshot.gate` — the lab never reaches paper by itself — which is why this one value is imported while `gate.maxDrawdown` and every other lab bar is read from the snapshot.
```

**Change (f) — line 791.** Today:

```
- The Leaderboard never says "Ready for real money" unless all six checklist items pass (`scoreOf`); a missing gate yields no items and a 0/6 "Paper only" line.
```

becomes:

```
- The Leaderboard never says "Ready for real money" unless all five checklist items pass (`scoreOf`); a missing gate yields no items and a 0/5 "Paper only" line. The count is `lib/metrics.ts`'s `CHECKLIST_RULES`, never a literal: `view.ts` held its own `6` through design section 13's shortening of the list and made "Ready" unreachable — five rendered rows under a score of x/6 — until it was fixed on 2026-10-09.
```

**Change (g) — line 829.** Today:

```
- The paper bar (3 months, 100 trades) on How it works is a constant in `app/sera/how/view.ts`, not snapshot data; change it there if design section 1 changes.
```

becomes:

```
- The paper bar on How it works is `MIN_PAPER_MONTHS` (18 months) imported from `lib/golive.ts`, not snapshot data and no longer a second constant in `app/sera/how/view.ts`; design section 13 deleted the old trades clause on 2026-10-07. If design section 1 moves the bar again, move `lib/golive.ts` and its Python twin — there is nothing else to change.
```

**Change (h) — the Last Updated entry, line 4.** House style is newest first, with every previous
entry preserved behind "Earlier:". The line currently begins:

```
**Last Updated**: 2026-10-09 (repo README: two new scripts and nothing else. `scripts/film.mjs` ...
```

Replace **only that prefix** — `**Last Updated**: 2026-10-09 (repo README: two new scripts` — with
the text below, leaving the remaining ~3,400 characters of the line exactly as they are:

```
**Last Updated**: 2026-10-09 (the go-live checklist now counts what it renders. `lib/metrics.ts` exports `CHECKLIST_RULES = 5` beside `checklist`, and that constant -- not a literal -- is `leaderboard/view.ts`'s `CHECKS`, which had been stuck at 6 ever since design section 13 (commit `ba8a05b`, 2026-10-07) replaced ">= 3 months forward AND >= 100 trades" with ">= 18 months forward" and shortened the list to five rules. The web half of `ba8a05b` was only `lib/golive.ts`, `lib/metrics.ts` and their two tests, so the Leaderboard went on rendering five rows under a score of x/6 and `ready` -- which requires `items.length === CHECKS` -- was unreachable: a strategy that passed everything read 5/6 and never said "Ready for real money". The "all six" copy is now built from the number through a number-to-word lookup, so the words cannot outlive the count, and `scoreOf` keeps its fixed denominator and its length guard, so a strategy with no gate row still reads 0/5 "Paper only" rather than 0/0. The tests that let it through are rewritten: `metrics.test.ts` pins `checklist(...)` to `CHECKLIST_RULES`, and `view.test.ts`'s `scoreOf` suite drives real `checklist()` output instead of hand-built six-element arrays -- the case that asserted "is never ready with fewer than six items" was pinning the bug with production's own input and is gone. `/sera/how` stated the same pre-section-13 bar, so `PAPER_MONTHS = 3` / `PAPER_TRADES = 100` are deleted and the Pipeline's paper stage reads `MIN_PAPER_MONTHS` from `lib/golive.ts`. No engine file, no migration, no database read, and no threshold value moved. Earlier: repo README: two new scripts
```

**Impact:** documentation only; no test reads `package_readme.md`.

---

## Verification

Run from `/home/miftah/.worktrees/seer/golive-checklist-count/web` (`node_modules` is already
hardlinked into the worktree's `web/`, and `npx tsc --noEmit` was verified clean on the base
commit, so both commands run as-is):

**Build:**

```
npx tsc --noEmit
```

**Tests:**

```
npm test
```

**Invariant 1 — no engine, db or docs file in the diff:**

```
git -C /home/miftah/.worktrees/seer/golive-checklist-count diff --name-only | grep -E '^(engine|db|docs)/' && echo 'INVARIANT 1 VIOLATED' || echo 'invariant 1 ok'
```

**Manual checks:**

- `git -C /home/miftah/.worktrees/seer/golive-checklist-count diff --name-only` lists exactly seven
  files, all under `web/`.
- `grep -rn "all six\|All six" web/app/\(app\)/leaderboard/` returns nothing. Every remaining
  "six" in `web/` (`app/sera/how/page.tsx:86`, `app/sera/how/view.ts:101`,
  `app/sera/journal/view.test.ts:129`, `app/sera/methods/view.ts:285`,
  `app/sera/methods/view.test.ts:239`, `lib/sera/derive.ts:125`) is the **lab's** six hurdles and
  must still be there.
- `grep -rn "PAPER_MONTHS\|PAPER_TRADES" web --include="*.ts" --include="*.tsx"` returns only
  `MIN_PAPER_MONTHS` hits (`lib/golive.ts`, `lib/golive.test.ts`, `lib/metrics.ts`,
  `app/sera/how/view.ts`).
- Optional, if the app is run (`run-the-web-app` skill): `/leaderboard` shows `x/5` over five rows,
  and `/sera/how`'s Pipeline paper box reads "At least 18 months / of forward paper, / no real
  money" in three lines with the box the same height as before.

**Exit criteria:**

1. `npx tsc --noEmit` is clean and `npm test` is green in `web/`.
2. `web/lib/metrics.ts` exports `CHECKLIST_RULES`, and `metrics.test.ts` fails if `checklist()`'s
   length ever stops matching it.
3. `grep -n "CHECKS" web/app/\(app\)/leaderboard/view.ts` shows no numeric literal — `CHECKS` is
   `CHECKLIST_RULES`.
4. `scoreOf(checklist(strong, spy, passedGate), passedGate)` is
   `{ passed: 5, total: 5, ready: true, lines: ['All five pass.', 'Ready for real money'] }`, and a
   test asserts it.
5. `scoreOf([], NO_GATE)` is still `{ passed: 0, total: 5, ready: false, … }` — never `0/0`.
6. The test named "is never ready with fewer than six items" does not exist anywhere.
7. `/sera/how`'s paper stage has three `detail` lines, each ≤ 18 characters, naming months and no
   trades, built from `MIN_PAPER_MONTHS`.
8. The invariant-1 command prints `invariant 1 ok`.

## Handoffs

Found while reading; deliberately **not** done here.

1. **`package_readme.md`'s `note` field is stale, twice.** Line 180 declares
   `type CheckItem = { label: string; val: string; ok: boolean; note?: string }` and line 186 says
   the gate row "carries `note` when the roster gives one" / "(plus the note)". The real
   `CheckItem` (`lib/metrics.ts:42`) has exactly three fields, and `metrics.test.ts:82-88` pins
   that — "carries no prose on any item: a failed gate explains itself on the Sera method page"
   (owner, 2026-10-07). This is a different stale statement from a different revision, it serves
   neither R1 nor R2, and it is left verbatim so this phase's diff stays one defect wide. The fix
   is two edits: drop `; note?: string` from line 180, and drop "; carries `note` when the roster
   gives one" and " (plus the note)" from line 186.
2. **`.workflows/plan/P1-WEB-08WD.md`** still shows `PAPER_MONTHS = 3` / `PAPER_TRADES = 100` at
   lines 74, 1346, 1347, 1440 and 2051. It is a shipped plan file — a record of what was decided
   then, not a statement about the code now — and is left alone on purpose.
3. **The engine side is correct and stays untouched.** `backtest/metrics.py`'s `checklist` returns
   four items by design and `gate_checks()` already selects by meaning rather than by slice
   position, which is the guard this phase is adding on the TypeScript side.
4. **`docs/media/leaderboard.png`**, committed at `d8c0cab`, renders `1/6` over five rows — the bug
   as a picture. `docs/` is out of scope for this plan set; regenerating the screenshot is a
   separate, later job (`npm run shoot`).

## Rollback

`git revert` of the single commit, or
`git -C /home/miftah/.worktrees/seer/golive-checklist-count checkout d8c0cab -- web/lib/metrics.ts web/lib/metrics.test.ts web/lib/golive.ts 'web/app/(app)/leaderboard/view.ts' 'web/app/(app)/leaderboard/view.test.ts' web/app/sera/how/view.ts web/package_readme.md`.

Nothing is persisted, migrated, published or cached: the change is pure TypeScript, its tests, and
markdown. Reverting restores a Leaderboard that reads `x/6` over five rows and a `/sera/how` paper
stage that says "At least 3 months / and 100 trades, / no real money" — the behaviour on `main` at
`d8c0cab`.
