> Adopted from `ROSTER_PROMOTION_PIPELINE_PLAN.md` phase 4. Source: `.workflows/plan/roster-promotion-pipeline/phase-4.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 4: The leaderboard re-sorts honestly, and shows retired horsemen

**Plan set:** `ROSTER_PROMOTION_PIPELINE_PLAN.md`
**Analysis:** `20261005-165054-XGER_code_analyzer.md`
**Satisfies:** R3 — a robust pipeline to compare and "re-sort" the horsemen, so a better method can be recognised as better
**Depends on:** Phase 1 (`strategies.status`, `strategies.paper_end`), Phase 3 (`paper/compare.py`, the common-window math)
**Difficulty:** NORMAL
**Package:** `web`

---

## Runtime preamble

Verbatim from the index, plus the web half.

```bash
export SEER_WT=/home/miftah/.worktrees/seer/roster-promotion-pipeline
export SEER_PY=/home/miftah/seer/engine/.venv/bin/python
export PYTHONPATH=$SEER_WT/engine/src                        # wins over the editable .pth
export SEER_MAIN=/home/miftah/seer
export SEER_ENV_FILE=$SEER_MAIN/.env.local-train             # ABSOLUTE, always
export PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres
cd "$SEER_WT"
"$SEER_PY" -c 'import seer_engine, pathlib; print(pathlib.Path(seer_engine.__file__).resolve())'
# must print $SEER_WT/engine/src/seer_engine/__init__.py
```

```bash
cd "$SEER_WT/web" && npm ci      # once; then `npm test` and `npm run build`
```

This phase touches **no Python**. The preamble is still required so that the `npm ci` line is run
from the right worktree and so that the engine suite can be re-run unchanged to prove the delta.

---

## Goal

The leaderboard stops claiming a winner it cannot justify. `bestResearch`'s bare `max(totalReturn)`
over strategies with different `paper_start` dates is replaced by a common-window, risk-adjusted
comparison, and **the window it ranked over is printed on the page** — a ranking that hides its
window fails R3 just as surely as wrong arithmetic. A retired strategy keeps every snapshot, every
month row and a visible `Retired <date>` marker while being excluded from "best"; a strategy with
too few shared sessions is labelled `Not ranked` rather than silently winning or silently
vanishing. And `looks` stops assuming four research strategies: a fifth, sixth and seventh horseman
each get a look of their own.

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Deletes:**
- `view.bestResearch` (`web/app/(app)/leaderboard/view.ts:52`) — the raw-`totalReturn` max. Its only
  consumer is `page.tsx:35`, which this phase rewrites. Its two tests
  (`view.test.ts:62-72`) are deleted with it.
- the `--cols` custom property on `.cards` (`page.tsx:173`, `leaderboard.module.css:97`) — the
  "at most five columns" assumption, replaced by an `auto-fit` grid.
- the `import type { CSSProperties } from 'react'` in `page.tsx:2`, which existed only for `--cols`.

**Renames:** none.

**Creates (all in `web/app/(app)/leaderboard/view.ts` unless stated):**
- type `RankIn` — `RosterIn & { status: 'active' | 'retired' }`
- type `CompareWindow` — `{ from: string; to: string; sessions: number }`
- type `CompareStatus` — `'ranked' | 'insufficient' | 'retired'`
- type `CompareRow<T>` , type `Comparison<T>`, type `WindowLine`
- `MIN_COMMON_SESSIONS` (= `63`, phase 3's value), `MIN_RANKED` (= `2`), `LOOK_PERIOD` (= `20`)
- `compare(rows)`, `windowLine(c)`, `spyOverSpan(spy, curve)`, `pickResearch(research, requested)`,
  `retiredLabel(paperEnd)`
- `web/lib/data.ts`: type `StrategyStatus`, `parseStatus(raw)`, and two new `Strategy` fields —
  `status: StrategyStatus`, `paperEnd: string | null`
- `leaderboard.module.css`: `.window`, `.windowLabel`, `.windowDetail`, `.retired`, `.unranked`,
  `.legendRetired`

**Signature changes:**
- `LINES` gains a fifth entry: `readonly [4]` -> `readonly [5]`. `'var(--ink-2)'` is appended.
  `CARD_BGS` keeps its four entries. The first four `(bg, line)` pairs are **byte-identical** to
  today's, so every pinned look assertion in `view.test.ts` passes unchanged.
- `web/lib/data.ts` `strategies()` SQL gains `paper_end::text AS paper_end, status` in its
  projection. **This requires phase 1's migration to have run** — see Requires.
- `checklist(...)`'s `spyReturn` argument at `page.tsx:41` changes from SPY's inception-to-date
  total return to SPY's return **over the picked strategy's own span** (`spyOverSpan`). Same
  signature, honest argument.

**Requires (from earlier phases):**
- **Phase 1** — `strategies.status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','retired'))`
  and `strategies.paper_end date`, both present on the `strategies` table before `strategies()`
  runs. `web/lib/data.ts` selects both columns by name; without the migration the query errors.
  `parseStatus` reads only the exact string `'retired'`, so the `CHECK`'s exact spelling is the
  contract. If phase 1 spells the retired value anything but `'retired'`, **change the one string
  literal in `parseStatus`** and nothing else.
- **Phase 3** — `engine/src/seer_engine/paper/compare.py`. This phase **ports its math into
  TypeScript** rather than calling it (both plans agree; see A2). Phase 4 adds **no** import of,
  and no subprocess call to, any engine module. **Reconciled against phase 3's shipped contract**:
  `MIN_COMMON_SESSIONS = 63` (not the 21 this plan first guessed), `MIN_RANKED = 2`, annualised
  Sharpe as the only risk-adjusted figure, phase 3's `_select` drop-the-worst-overlap algorithm,
  phase 3's rank key including the max-drawdown tiebreak, and `window === null` exactly when
  nothing is ranked. A3 below records what remains adjustable; the five items above do not.
- **Phase 2** — writes `paper_end` when a strategy retires. This phase only renders it, and renders
  `Retired` with no date when `paper_end` is null, so it is correct whether or not phase 2 has
  landed.

**Leaves alone (owned by others):**
- `engine/**` entirely — including `paper/compare.py` (Phase 3) and `paper/roster.py` (Phase 1).
- `db/migrations/*` (Phase 1, Phase 6).
- `web/lib/sera/*`, `web/app/sera/*` — the Sera lab pages are not part of this set.
- `web/components/roster.ts` (`selectStrategy`, `strategyIcon`) and `web/components/roster.test.ts`
  — `pickResearch` is added beside `selectStrategy`, which keeps working untouched for
  `positions/page.tsx`.
- `web/lib/metrics.ts` (`checklist`, `strategyMetrics`), `web/lib/monthly.ts`,
  `web/lib/strategy.ts`, `web/lib/slots.ts`, `web/scripts/seed-demo.mjs`.
- `web/app/(app)/page.tsx`, `positions/page.tsx`, `history/page.tsx` — they consume `Strategy`,
  which only gains fields. See Handoffs for the default-selection follow-up they inherit.

## Files

| File | Action | What changes |
|---|---|---|
| `web/lib/data.ts` | modify | `:22` `Strategy` gains `status` and `paperEnd`; `:45` `toStrategy` fills them; `:66` the projection selects `status` and `paper_end`; new `StrategyStatus` + `parseStatus` above `toStrategy` |
| `web/app/(app)/leaderboard/view.ts` | modify | `:17` `LINES` gains a fifth line; `:24` `looks` cycles both arrays; `:52` `bestResearch` deleted; `compare`/`windowLine`/`spyOverSpan`/`pickResearch`/`retiredLabel` added |
| `web/app/(app)/leaderboard/page.tsx` | modify | `:2,12,35,38,41,173,174-199,229-247` — the window row, the comparison, the windowed `spyRet`, the retired and not-ranked chips, the auto-fit card grid, the legend's retired marker |
| `web/app/(app)/leaderboard/leaderboard.module.css` | modify | after `:14` the window row; after `:63` the two chips and the retired card; `:97` the card grid |
| `web/app/(app)/leaderboard/view.test.ts` | modify | `:62-72` the two `bestResearch` tests deleted; 20 tests added across `looks`, `compare`, `windowLine`, `spyOverSpan`, `pickResearch`, `retiredLabel` |

Five files, exactly the set the index's phase row assigns. No new file is created.

---

## Implementation Steps

### Step 1: `strategies.status` and `paper_end` reach the web layer

**File:** `web/lib/data.ts:16-18` (the coercion helpers), `:22-63` (`Strategy`, `toStrategy`), `:65-70` (`strategies`)

**Change:** add the lifecycle type and its parser beside the other row coercions, add the two
fields to `Strategy`, fill them in `toStrategy`, and select the two new columns.

Insert after `ymdOrNull` (`data.ts:17`):

```ts
/**
 * Roster lifecycle (migration 006, phase 1): 'retired' stops trading and keeps the record.
 * Mirrors the `status` union in `app/(app)/leaderboard/view.ts`'s `RankIn`; the two are
 * structurally identical on purpose, so `Strategy` satisfies `RankIn` without an import.
 */
export type StrategyStatus = 'active' | 'retired';

/**
 * `strategies.status`. Only the exact string 'retired' retires a row: a missing, null or
 * malformed value reads as active, never as retired — the same discipline as `parseGate`, where a
 * pass is never assumed. A bad read must not hide a live strategy from the board.
 */
export const parseStatus = (raw: unknown): StrategyStatus => (raw === 'retired' ? 'retired' : 'active');
```

Replace the `Strategy` type (`data.ts:22-43`) in full:

```ts
export type Strategy = {
  id: string;
  name: string;
  sub: string;
  icon: string;
  isChampion: boolean;
  isBenchmark: boolean;
  /** 'bracket' (A, C), 'book' (F4, F1) or 'benchmark' (SPY). */
  engine: Engine;
  /** 'design-v0', 'monthly-hold'; null for SPY. */
  rulesId: string | null;
  /** First paper session; null until the engine's `paper` command starts the clock. */
  paperStart: string | null;
  /**
   * 'active' or 'retired' (migration 006). Retirement stops trading and keeps every snapshot,
   * order and trade: a retired strategy stays on the board, marked, and is never ranked.
   */
  status: StrategyStatus;
  /** Last paper session a retired strategy traded (migration 006); null while it is active. */
  paperEnd: string | null;
  /** params->'backtest_gate'; { passed: false, applicable: true, note: null } until `paper` writes the frozen spec. */
  gate: Gate;
  /** A research strategy: its orders and positions are paper only and never a buy recommendation. */
  isPaper: boolean;
  /** 'A', 'C', 'F4', 'F1', 'SPY': the part of the name before the middle dot. */
  short: string;
  /** Runs the nightly news check (C): Positions shows its verdicts under the paper orders. */
  checksNews: boolean;
};
```

Replace `toStrategy` (`data.ts:45-63`) in full:

```ts
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
    status: parseStatus(r.status),
    paperEnd: ymdOrNull(r.paper_end),
    gate: parseGate(r.gate),
    isPaper: !isBenchmark && !isChampion,
    short: shortLabel(r.name, r.id),
    checksNews: checksNews(r.id, r.spec_object),
  };
}
```

Replace `strategies` (`data.ts:65-70`) in full:

```ts
export async function strategies(): Promise<Strategy[]> {
  // spec_object: the frozen spec wins where it exists, and `object_name` (migration 006) answers
  // for a strategy that has not been frozen yet — a just-promoted row has `params = '{}'` until
  // its first paper night, and without the COALESCE it would lose a display fact for a night.
  const rows = await sql`SELECT id, name, sub, icon, is_champion, is_benchmark, engine, rules_id,
      paper_start::text AS paper_start, paper_end::text AS paper_end, status,
      params->'backtest_gate' AS gate,
      COALESCE(params->'spec'->>'object', object_name) AS spec_object
    FROM strategies ORDER BY sort, id`;
  return rows.map(toStrategy);
}
```

**Impact:** every consumer of `Strategy` gains two fields; none loses one, so
`app/(app)/page.tsx`, `positions/page.tsx` and `history/page.tsx` keep compiling untouched. The
query now names three columns that exist only after phase 1's `006_roster.sql` has run
(`status`, `paper_end`, `object_name`) — this is the phase's one hard schema dependency, and it is
already declared in Requires.

---

### Step 2: `looks` stops assuming four research strategies

**File:** `web/app/(app)/leaderboard/view.ts:11-41`

**Change:** give `LINES` a real fifth entry and cycle both arrays modularly. Because `CARD_BGS` has
four entries and `LINES` five, the `(bg, line)` pair repeats only after `lcm(4, 5) = 20` research
strategies — so a fifth, sixth and seventh horseman each get a look nobody else has, using only
tokens `globals.css` already defines in both themes.

Replace `view.ts:11-41` in full:

```ts
/**
 * Research strategies take the design's sheet and line pairs in roster order: the A/B/C pairs, then
 * butter (the fourth sheet of the design's slot palette) with the coral accent line, so a fourth
 * research strategy (C · News veto) never reuses the first one's look.
 *
 * The roster is variable length — a promotion adds a horseman and a retirement keeps one on the
 * board — so neither array may be assumed to cover it. They are cycled independently and their
 * lengths are coprime, so the (sheet, line) pair a strategy gets is unique for the first
 * `LOOK_PERIOD` research strategies. Both tokens are defined for light and dark in `globals.css`.
 */
export const CARD_BGS = ['bg-lav', 'bg-sky', 'bg-stone', 'bg-butter'] as const;
export const LINES = ['var(--ink)', 'var(--line-b)', 'var(--line-c)', 'var(--coral)', 'var(--ink-2)'] as const;

/** lcm(CARD_BGS.length, LINES.length): research strategies before any (sheet, line) pair repeats. */
export const LOOK_PERIOD = 20;

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
      line: LINES[i % LINES.length],
      width: st.isChampion ? 2.75 : 2,
      dotted: false,
    });
    i += 1;
  }
  return out;
}
```

**Impact:** indices 0–3 are unchanged (`bg-lav`/`--ink`, `bg-sky`/`--line-b`, `bg-stone`/`--line-c`,
`bg-butter`/`--coral`), and index 4 is **also** unchanged — the old fallback produced
`bg-lav` + `var(--ink-2)` and so does the new cycle. So all six existing `looks` assertions,
including `view.test.ts:37-40`'s fifth-strategy case, pass **byte-identically**. The behaviour
changes only from the sixth strategy on, where the old code repeated `var(--ink-2)` forever and the
new code moves on to `bg-sky` + `var(--ink)` — a pair nobody holds.

---

### Step 3: the common-window comparison, ported from phase 3

**File:** `web/app/(app)/leaderboard/view.ts` — after `researchOf` (`:49`), replacing
`bestResearch` (`:51-62`) entirely.

**Change:** delete `bestResearch`. Add the comparison, the sentence that makes its window visible,
the windowed benchmark figure the checklist needs, and the two small selection/label helpers the
page needs for retirement.

First extend the header comment and imports. Replace `view.ts:1-9`:

```ts
// Pure helpers for the Leaderboard: roster-driven looks, the common-window comparison that ranks
// research strategies honestly, the honest checklist line and the month-by-month rows. No data
// access; page.tsx feeds it.
// Selection (`selectStrategy`) and icons (`strategyIcon`) are phase 11's `components/roster.ts`;
// short labels are phase 10's `Strategy.short`; the month math is phase 10's `lib/monthly.ts`.
//
// `compare` is a TypeScript port of the engine's `seer_engine/paper/compare.py`
// (roster-promotion-pipeline phase 3): the same window rule, the same selection, the same metrics,
// the same `insufficient` cut, the same rank order. The leaderboard is a server component
// rendering inside a request and cannot run the Python CLI, so the math is ported rather than
// called; `compare.py` stays the reference implementation and its tests are the specification.
// MIN_COMMON_SESSIONS, MIN_RANKED, the selection rule and the rank key must all stay equal to it:
// a leaderboard that ranks differently from `python -m seer_engine compare` is worse than either
// being wrong alone, because nothing says which one to believe. Pin new fixtures against
// `compare --json`.
import { monthDay, monthName, pct, signedPct } from '../../../lib/format';
import type { Snapshot } from '../../../lib/metrics';
import type { MonthlyTable } from '../../../lib/monthly';

/** The roster fields these helpers read (a structural subset of lib/data's Strategy). */
export type RosterIn = { id: string; isChampion: boolean; isBenchmark: boolean };

/**
 * What the ranking reads: the roster fields plus phase 1's lifecycle column. Structurally equal to
 * `lib/data`'s `Strategy['status']`, so a `Strategy` satisfies `RankIn` with no import (view.ts
 * must not pull in `lib/data`, which opens a database connection).
 */
export type RankIn = RosterIn & { status: 'active' | 'retired' };
```

Then replace `bestResearch` (`view.ts:51-62`) with the block below:

```ts
/**
 * Sessions a strategy must share with the others before it can be ranked. **This is
 * `compare.py`'s `MIN_COMMON_SESSIONS` and must stay equal to it** — 63, one quarter of a
 * 252-session year, which is three full rebalances for a monthly-hold book strategy, so a ranked
 * strategy has made at least three independent decisions inside the window. A three-week-old
 * method does not win a leaderboard, and a window shorter than this is not a ranking, it is noise.
 */
export const MIN_COMMON_SESSIONS = 63;

/** `compare.py`'s `MIN_RANKED`. A ranking of one is not a comparison. */
export const MIN_RANKED = 2;

const DAY = 86_400_000;
const TRADING_DAYS = 252;

/** The window a comparison ranked over: its first and last shared session, and how many there were. */
export type CompareWindow = { from: string; to: string; sessions: number };

/**
 * 'ranked'       — compared over the whole common window; every windowed figure is a number.
 * 'insufficient' — too few shared sessions to rank (a newcomer, or a window that is still short).
 * 'retired'      — stopped trading; its record stands, but it is never ranked against the living.
 *
 * 'ranked' and 'insufficient' are `compare.py`'s own two statuses, spelled identically. 'retired'
 * is a UI-side **pre-filter outcome** that the engine module never sees: a retired strategy is
 * dropped before the window is computed, exactly as `compare --exclude <id>` drops it on the CLI
 * side (phase 3's Handoffs settle this). Windowed figures are non-null **only** for 'ranked'.
 */
export type CompareStatus = 'ranked' | 'insufficient' | 'retired';

export type CompareRow<T extends RankIn = RankIn> = {
  strategy: T;
  status: CompareStatus;
  /** Sessions ranked over ('ranked'), else the strategy's own snapshot count. */
  sessions: number;
  /** Over the common window. Null unless `status` is 'ranked'. */
  totalReturn: number | null;
  cagr: number | null;
  maxDrawdown: number | null;
  sharpe: number | null;
  /** Inception to date, over the strategy's own whole record. Never mixed into the ranking. */
  inception: number | null;
};

export type Comparison<T extends RankIn = RankIn> = {
  /**
   * The window the ranking used. **Null exactly when nothing is ranked** — `compare.py`'s own
   * guarantee (`window === null ⟺ no row has status 'ranked'`), so a window on the page is always
   * a window something was actually ranked over.
   */
  window: CompareWindow | null;
  /**
   * How many sessions every live research strategy currently shares, ranked or not. Presentation
   * only: it is what lets `windowLine` say how far off a ranking is instead of showing a blank.
   * It is never a window and nothing is ever ranked over it.
   */
  shared: number;
  /** Every research strategy, benchmark excluded, in roster order. Nothing is ever dropped. */
  rows: CompareRow<T>[];
  /** The rankable subset, best first. Empty while the window is too short. */
  ranked: CompareRow<T>[];
  best: CompareRow<T> | null;
};

const byDate = (a: Snapshot, b: Snapshot) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0);

/**
 * Every date all of `curves` have: the set intersection, ascending. [] for no curves.
 * This is `compare.py`'s `_common_dates`, character for character in intent — a plain
 * intersection, NOT `[max(start), min(end)]`, so a session one strategy missed is dropped for
 * every strategy and all of them are measured over the very same consecutive pairs of dates.
 */
function commonDates(curves: Snapshot[][]): string[] {
  if (curves.length === 0) return [];
  const sets = curves.map(c => new Set(c.map(p => p.date)));
  return [...sets[0]].filter(d => sets.every(s => s.has(d))).sort();
}

/** Inception-to-date total return over a strategy's whole record; null with fewer than two snapshots. */
function inceptionOf(curve: Snapshot[]): number | null {
  if (curve.length < 2) return null;
  const c = [...curve].sort(byDate);
  return c[0].equity === 0 ? null : c[c.length - 1].equity / c[0].equity - 1;
}

type Windowed = {
  totalReturn: number; cagr: number | null; maxDrawdown: number; sharpe: number | null;
};

/** The window's figures for one curve, which must have a snapshot on every date in `dates`. */
function windowed(curve: Snapshot[], dates: string[]): Windowed {
  const on = new Map(curve.map(p => [p.date, p.equity]));
  const eq = dates.map(d => on.get(d)!);
  const start = eq[0], end = eq[eq.length - 1];

  let peak = start, maxDrawdown = 0;
  for (const v of eq) {
    if (v > peak) peak = v;
    if (peak > 0) maxDrawdown = Math.max(maxDrawdown, (peak - v) / peak);
  }

  const years = (Date.parse(dates[dates.length - 1]) - Date.parse(dates[0])) / DAY / 365.25;
  const cagr = years > 0 && start > 0 ? Math.pow(end / start, 1 / years) - 1 : null;

  const rets: number[] = [];
  for (let i = 1; i < eq.length; i++) if (eq[i - 1] !== 0) rets.push(eq[i] / eq[i - 1] - 1);
  let sharpe: number | null = null;
  if (rets.length >= 2) {
    const mean = rets.reduce((a, v) => a + v, 0) / rets.length;
    const sd = Math.sqrt(rets.reduce((a, v) => a + (v - mean) ** 2, 0) / (rets.length - 1));
    sharpe = sd > 0 ? (mean / sd) * Math.sqrt(TRADING_DAYS) : null;
  }

  return { totalReturn: start === 0 ? 0 : end / start - 1, cagr, maxDrawdown, sharpe };
}

/**
 * Best first, and this is `compare.py`'s `_rank_key` with the signs flipped into a comparator:
 * finite Sharpe descending; rows with no Sharpe last; then total return descending; then the
 * SMALLER max drawdown; then the id. Every tie is broken, so the order never depends on the order
 * the rows arrived in — the property `test_selection_is_independent_of_input_order` pins on the
 * Python side.
 */
function rankCmp<T extends RankIn>(a: CompareRow<T>, b: CompareRow<T>): number {
  const ag = a.sharpe === null ? 1 : 0, bg = b.sharpe === null ? 1 : 0;
  if (ag !== bg) return ag - bg;
  if (ag === 0 && a.sharpe !== b.sharpe) return (b.sharpe as number) - (a.sharpe as number);
  const ar = a.totalReturn ?? 0, br = b.totalReturn ?? 0;
  if (ar !== br) return br - ar;
  const ad = a.maxDrawdown ?? 0, bd = b.maxDrawdown ?? 0;
  if (ad !== bd) return ad - bd;
  return a.strategy.id < b.strategy.id ? -1 : a.strategy.id > b.strategy.id ? 1 : 0;
}

/**
 * Who gets ranked, and over which dates — `compare.py`'s `_select`, ported.
 *
 * First every curve shorter than `MIN_COMMON_SESSIONS` on its own is dropped, so one young
 * strategy cannot shorten the window for the board. Then, while the intersection is still short,
 * the strategy whose removal leaves the LONGEST intersection goes (ties: the shortest own curve,
 * then the id) and the intersection is recomputed. It stops when the intersection is long enough,
 * or when fewer than `MIN_RANKED` strategies remain — in which case nothing is ranked at all.
 *
 * The greedy drop is the half this plan originally left out, and it is the half that matters: a
 * board of four where one strategy barely overlaps still produces a ranking of the other three
 * here, exactly as the CLI does, instead of ranking nothing.
 */
function selectRanked(
  curves: Map<string, Snapshot[]>, minSessions: number,
): { ids: Set<string>; dates: string[] } {
  const own = (id: string) => curves.get(id)!;
  let live = [...curves.keys()].filter(id => own(id).length >= minSessions).sort();
  while (live.length >= MIN_RANKED) {
    const common = commonDates(live.map(own));
    if (common.length >= minSessions) return { ids: new Set(live), dates: common };
    if (live.length === MIN_RANKED) break;
    let worst = live[0];
    let worstKey: [number, number, string] | null = null;
    for (const id of live) {
      const rest = live.filter(o => o !== id);
      const key: [number, number, string] = [-commonDates(rest.map(own)).length, own(id).length, id];
      if (worstKey === null || key[0] < worstKey[0]
        || (key[0] === worstKey[0] && key[1] < worstKey[1])
        || (key[0] === worstKey[0] && key[1] === worstKey[1] && key[2] < worstKey[2])) {
        worst = id;
        worstKey = key;
      }
    }
    live = live.filter(id => id !== worst);
  }
  return { ids: new Set(), dates: [] };
}

/**
 * Rank the research strategies over the window they actually share (R3, invariant 6).
 *
 * A TypeScript port of `seer_engine/paper/compare.py`'s `compare`, selection rule included. The
 * window is the intersection of the selected strategies' snapshot dates (`selectRanked`), and it
 * is returned rather than implied; `window` is null exactly when nothing could be ranked, which is
 * the engine module's own guarantee.
 *
 * Two filters happen HERE and not in the engine module, because they are roster semantics rather
 * than arithmetic — `compare.py` is deliberately blind to both:
 *
 * - **The benchmark is never compared.** It is the yardstick, not a method.
 * - **A retired strategy is never ranked, and never dropped from `rows`.** It keeps its card and
 *   its inception-to-date figure (invariant 4) and is excluded from the window, so a retirement
 *   cannot shorten the living strategies' comparison. On the CLI side the same exclusion is
 *   `compare --exclude <id>`.
 */
export function compare<T extends RankIn>(rows: { strategy: T; curve: Snapshot[] }[]): Comparison<T> {
  const research = rows.filter(r => !r.strategy.isBenchmark);
  const live = research.filter(r => r.strategy.status === 'active' && r.curve.length >= 2);
  const curves = new Map(live.map(r => [r.strategy.id, [...r.curve].sort(byDate)]));

  const { ids: rankedIds, dates } = selectRanked(curves, MIN_COMMON_SESSIONS);
  const window: CompareWindow | null = dates.length > 0
    ? { from: dates[0], to: dates[dates.length - 1], sessions: dates.length }
    : null;
  // How much the LIVE board shares right now, ranked or not. Never a ranking; only the sentence
  // that says how far off one is.
  const shared = commonDates([...curves.values()]).length;

  const out: CompareRow<T>[] = research.map(r => {
    const base = {
      strategy: r.strategy,
      sessions: r.curve.length,
      inception: inceptionOf(r.curve),
      totalReturn: null,
      cagr: null,
      maxDrawdown: null,
      sharpe: null,
    };
    if (r.strategy.status === 'retired') return { ...base, status: 'retired' as const };
    if (!rankedIds.has(r.strategy.id)) return { ...base, status: 'insufficient' as const };
    return {
      strategy: r.strategy,
      status: 'ranked' as const,
      sessions: dates.length,
      inception: base.inception,
      ...windowed(curves.get(r.strategy.id)!, dates),
    };
  });

  const ranked = out.filter(r => r.status === 'ranked').sort(rankCmp);
  return { window, shared, rows: out, ranked, best: ranked[0] ?? null };
}

/** The two lines that put the ranking's window on the page. */
export type WindowLine = { label: string; detail: string };

/**
 * The sentence that makes the window visible (invariant 6): the leaderboard never shows a "best"
 * without saying, next to it, over which sessions it was best. With no window yet it says how far
 * off one is instead of quietly showing a number that compares unequal records.
 */
export function windowLine(c: Comparison): WindowLine {
  const compared = c.ranked.length;
  const active = c.rows.filter(r => r.strategy.status === 'active').length;
  if (compared === 0) {
    // `c.window` is null here by construction, so the honest number is `c.shared` — the sessions
    // the live board has in common so far. Saying "0 of 63" when four strategies share 40 would be
    // its own small lie.
    return {
      label: 'No common window yet',
      detail: `${c.shared} of ${MIN_COMMON_SESSIONS} sessions shared by every strategy`,
    };
  }
  const w = c.window!;
  return {
    label: `Ranked over ${monthDay(w.from)} – ${monthDay(w.to)}`,
    detail: `${w.sessions} shared sessions · ${compared} of ${active} active strategies compared`,
  };
}

/**
 * The benchmark's return over exactly the span `curve` covers. "Beats SPY" must compare the two
 * over the same dates once strategies can start on different days (invariant 6); SPY's own
 * inception-to-date figure is its record, not the comparison. Null when the benchmark has no
 * snapshot on one of the two boundary dates.
 */
export function spyOverSpan(spy: Snapshot[], curve: Snapshot[]): number | null {
  if (curve.length < 2) return null;
  const c = [...curve].sort(byDate);
  const on = new Map(spy.map(p => [p.date, p.equity]));
  const a = on.get(c[0].date), b = on.get(c[c.length - 1].date);
  return a === undefined || b === undefined || a === 0 ? null : b / a - 1;
}

/**
 * The research strategy the page shows: the requested id when it is on the roster, else the first
 * **active** one, else the first row. Retired strategies stay selectable — retirement preserves the
 * record (invariant 4), it does not hide it — but the default never lands on one while a live
 * strategy exists.
 */
export function pickResearch<T extends RankIn>(research: T[], requested: string | undefined): T | null {
  return research.find(r => r.id === requested)
    ?? research.find(r => r.status === 'active')
    ?? research[0]
    ?? null;
}

/** 'Retired Dec 2' for the card's marker; plain 'Retired' until `paper_end` is written (phase 2). */
export const retiredLabel = (paperEnd: string | null): string =>
  paperEnd === null ? 'Retired' : `Retired ${monthDay(paperEnd)}`;
```

**Impact:** `bestResearch` no longer exists; `page.tsx` is the only consumer and Step 4 rewrites it.
Nothing else in `web/` imports it (verified: `grep -rn bestResearch` finds only `view.ts`,
`view.test.ts` and `page.tsx`). `view.ts` now imports `Snapshot` from `lib/metrics`, which is a
pure module with no database import, so `view.test.ts` still runs with no connection.

---

### Step 4: the page shows the window, the retired marker and the unranked marker

**File:** `web/app/(app)/leaderboard/page.tsx`

**Change 4a — imports.** Replace `page.tsx:1-15`:

```tsx
import { Archive, Check, CircleDashed, Crown, X } from 'lucide-react';
import { AppHeader } from '@/components/AppHeader';
import { PaperChip } from '@/components/PaperChip';
import { strategyIcon } from '@/components/roster';
import { StrategySwitch } from '@/components/StrategySwitch';
import { leaderboard, monthly, runStatus, type Board } from '@/lib/data';
import { monthDay, monthName, shortDate, signedPct } from '@/lib/format';
import { checklist } from '@/lib/metrics';
import { wibDate } from '@/lib/session';
import {
  compare, LOOK_FALLBACK, looks, MIN_COMMON_SESSIONS, monthLines, monthsBg, NO_GATE, pickResearch,
  researchOf, retiredLabel, scoreOf, sinceStartLine, spyOverSpan, windowLine,
  type CompareRow, type Look, type MonthLine,
} from './view';
import s from './leaderboard.module.css';
```

`CSSProperties` and `selectStrategy` are both dropped — `--cols` goes away in 4e, and the
leaderboard now selects with `pickResearch` so retirement is honoured. `selectStrategy` stays
exported and tested for `positions/page.tsx`.

**Change 4b — the body's head.** Replace `page.tsx:23-63` (from `export default` through `second`):

```tsx
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

  // R3: rank over the sessions the compared strategies actually share, never over raw total return
  // across unequal paper starts (invariant 6). `wline` is what puts that window on the page, and
  // `cmpOf` is what lets a card say "not ranked" instead of silently dropping out of the order.
  const cmp = compare(board.rows);
  const best = cmp.best;
  const wline = windowLine(cmp);
  const cmpMap = new Map(cmp.rows.map(r => [r.strategy.id, r]));
  const cmpOf = (id: string): CompareRow | null => cmpMap.get(id) ?? null;

  // Research only: SPY is in every month row's SPY column, so it is not selectable here. Retired
  // strategies stay selectable (their record is the point) but are never the default.
  const pick = pickResearch(research, q.s);
  const pickRow = pick ? board.rows.find(r => r.strategy.id === pick.id) : undefined;
  const gate = pickRow?.strategy.gate ?? null;
  // "Beats SPY" measures the benchmark over the picked strategy's own span, not over SPY's whole
  // record: the two need not have started on the same day once the roster is promotable.
  const pickSpy = pickRow && spy ? spyOverSpan(spy.curve, pickRow.curve) : null;
  const items = pickRow && gate ? checklist(pickRow.metrics, pickSpy, gate) : [];
  const score = scoreOf(items, gate ?? NO_GATE);
  // The latest month is partial while the engine's next session (runStatus().sessionDate) is in it.
  const table = pick ? await monthly(pick.id, run.sessionDate) : null;
  const since = table ? sinceStartLine(table) : null;
  const months = table ? monthLines(table) : [];

  // Forward test runs from the earliest paper snapshot; strategies promoted later start later, so
  // this is the board's whole span and NOT the window anything is ranked over (see `wline`).
  const period = board.from && board.to ? `${monthDay(board.from)} – ${monthDay(board.to)}` : 'Not started';
  const chart = buildChart(board, lookOf);
  const ret = (v: number | null) => (v === null ? '—' : signedPct(v, 1));
  const tone = (v: number | null) => (v === null ? '' : v < 0 ? 'neg' : 'pos');
  const champRet = champ?.metrics.totalReturn ?? null;

  // Big figure = the champion (SPY today, D2). Second figure = the best research strategy over the
  // common window while the champion is the benchmark; otherwise SPY, as in the design. With no
  // common window there is no "best": a number here without a window would be the very claim R3
  // exists to stop making.
  const second = champ?.strategy.isBenchmark
    ? {
        value: best ? ret(best.totalReturn) : '—',
        mobile: best ? `Best · ${best.strategy.short}` : 'Not ranked',
        desk: best ? `${best.strategy.name}, best over the common window` : wline.label,
      }
    : { value: ret(spyRet), mobile: 'SPY', desk: 'SPY' };
```

**Change 4c — the window row in the chart sheet.** Insert a new row between the `.headline` block
and the `<svg>` (`page.tsx:93`/`:94`). Replace the chart sheet's closing of `.headline` through the
`<svg>` open tag:

```tsx
        <Legend rows={board.rows} lookOf={lookOf} className="desk-only" />
      </div>
      <div className={`${s.window} ${s.pad}`}>
        <span className={s.windowLabel}>{wline.label}</span>
        <span className={s.windowDetail}>{wline.detail}</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className={s.chart} role="img"
        aria-label="Equity curves of each strategy against SPY">
```

**Change 4d — the cards carry the markers.** Replace `page.tsx:174-199` (the `board.rows.map`
callback) in full:

```tsx
          {board.rows.map(({ strategy: st, metrics: m }) => {
            const Icon = strategyIcon(st.icon);
            const dash = (v: string) => (st.isBenchmark ? '—' : v);
            const cr = cmpOf(st.id);
            const retired = st.status === 'retired';
            return (
              <article key={st.id} data-status={cr?.status ?? 'benchmark'}
                className={`sheet over ${lookOf(st.id).bg} ${s.card}`}>
                <div className={s.cardHead}>
                  <div className={s.cardName}>
                    <span className={s.name}>
                      {st.name}
                      {st.isChampion && <span data-tip="Champion" aria-label="Champion" role="img" className={s.crown}><Crown size={20} /></span>}
                      {!st.isBenchmark && !retired && <PaperChip />}
                      {retired && (
                        <span className={`chip ${s.retired}`}
                          data-tip="Retired: it stopped trading and keeps its whole record">
                          <Archive size={14} strokeWidth={1.75} aria-hidden="true" />
                          {retiredLabel(st.paperEnd)}
                        </span>
                      )}
                      {cr?.status === 'insufficient' && (
                        <span className={`chip ${s.unranked}`}
                          data-tip={`Not ranked: fewer than ${MIN_COMMON_SESSIONS} sessions shared with the others`}>
                          Not ranked
                        </span>
                      )}
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
```

The five metric rows are unchanged and stay inception-to-date, labelled "Total return" — that is
each strategy's own record, which retirement and insufficiency must never remove (invariant 4). The
chips say which of those records is also a *ranking*.

**Change 4e — the card grid stops capping at five.** Replace `page.tsx:173`:

```tsx
        <div className={s.cards}>
```

**Change 4f — the legend marks the retired.** Replace `page.tsx:228-247` (`Legend`) in full:

```tsx
/** One swatch + short label per strategy (full name as its tooltip), so the legend stays on one row. */
function Legend({ rows, lookOf, className }: {
  rows: Board['rows']; lookOf: (id: string) => Look; className: string;
}) {
  return (
    <div className={`${s.legend} ${className}`}>
      {rows.map(({ strategy: st }) => {
        const look = lookOf(st.id);
        const retired = st.status === 'retired';
        const tip = retired ? `${st.name} · ${retiredLabel(st.paperEnd).toLowerCase()}` : st.name;
        return (
          <span key={st.id} data-tip={tip} aria-label={tip}
            className={retired ? `${s.legendItem} ${s.legendRetired}` : s.legendItem}>
            {look.dotted
              ? <span className={s.swatchDot} />
              : <span className={s.swatch} style={{ background: look.line }} />}
            {st.short}
          </span>
        );
      })}
    </div>
  );
}
```

`buildChart` is **not** changed: a retired strategy's equity curve keeps being drawn, in its own
colour, for as long as its snapshots run. Hiding or restyling the line would be the one thing
invariant 4 forbids.

**Impact:** the leaderboard gains a visible window line, two card markers and an active-first
default pick. Nothing is removed from any card. The `StrategySwitch` at `:110-115` still lists
`research`, retired entries included, so a retired horseman's month-by-month table stays reachable.

---

### Step 5: the CSS for the window row and the two markers

**File:** `web/app/(app)/leaderboard/leaderboard.module.css`

Insert after `.axis` (`:14`):

```css
/* The ranking's window, stated under the headline: a "best" is never shown without it. */
.window { display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 10px; font-size: 14px; }
.windowLabel { color: var(--ink); }
.windowDetail { color: var(--ink-2); }
```

Insert after `.cardSub` (`:63`):

```css
/* A retired strategy keeps its card and its numbers; the chip and the muted sheet say it stopped. */
.retired { height: 28px; padding: 0 11px; gap: 5px; font-size: 13px; color: var(--ink-2); }
.card[data-status='retired'] { opacity: 0.74; }
.legendRetired { opacity: 0.6; }
/* Dashed, like PaperChip: a state, not a holding. "Not ranked" is a fact about the window, not a loss. */
.unranked {
  height: 28px; padding: 0 11px; font-size: 13px; color: var(--ink-2);
  background: transparent; border: 1.5px dashed var(--ink-3);
}
```

Replace the `.cards` rule inside the `@media (min-width: 1024px)` block (`:96-99`):

```css
  /* auto-fit, not a column count: the roster is variable length, and a sixth or seventh horseman
     must wrap rather than squeeze. 180px keeps today's five strategies on one row at 1024px. */
  .cards {
    order: 1; display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px; margin-top: 12px;
  }
```

Insert inside the same `@media` block, beside the other desktop overrides (after `.statLabel`, `:79`):

```css
  .window { font-size: 13px; }
```

**Impact:** at 1024px, five cards at ≥180px still fit one row exactly as today; six wrap to 5 + 1
instead of being crushed. The mobile `.cards { display: contents; }` rule (`:57`) is untouched, so
phone layout is unchanged.

---

### Step 6: the tests

**File:** `web/app/(app)/leaderboard/view.test.ts`

**Delete** the whole `describe('bestResearch', …)` block (`:62-72`) and drop `bestResearch` from the
import list — the function no longer exists. This is the only existing assertion this phase removes,
and it is removed because the behaviour it pinned ("highest total return wins") is precisely what R3
rejects. **Every other existing assertion in this file passes unchanged**, including
`:37-40`'s fifth-research-strategy look.

**Replace** the import block (`:1-6`):

```ts
import { describe, expect, it } from 'vitest';
import type { Snapshot } from '../../../lib/metrics';
import type { MonthlyTable } from '../../../lib/monthly';
import {
  CHECKS, compare, looks, MIN_COMMON_SESSIONS, MIN_RANKED, monthLabel, monthLines, monthsBg,
  NO_GATE, pickResearch, researchOf, retiredLabel, scoreOf, sinceStartLine, spyOverSpan,
  windowLine, type RankIn, type RosterIn,
} from './view';
```

**Add** inside `describe('looks', …)`, after the existing fifth-strategy test (`:40`):

```ts
  it('gives a sixth and a seventh research strategy looks of their own', () => {
    const extra = ['X9', 'X10', 'X11'].map(id => ({ id, isChampion: false, isBenchmark: false }));
    const l = looks([...roster, ...extra]);
    expect(l.get('X10')).toEqual({ bg: 'bg-sky', line: 'var(--ink)', width: 2, dotted: false });
    expect(l.get('X11')).toEqual({ bg: 'bg-stone', line: 'var(--line-b)', width: 2, dotted: false });
  });
  it('never gives two research strategies the same look, up to a roster of twenty', () => {
    const many: RosterIn[] = Array.from({ length: 20 }, (_, i) => ({
      id: `S${i}`, isChampion: false, isBenchmark: false,
    }));
    const l = looks(many);
    const seen = many.map(st => `${l.get(st.id)!.bg}|${l.get(st.id)!.line}`);
    expect(new Set(seen).size).toBe(20);
  });
```

**Add** the comparison suites, after `describe('researchOf', …)`:

```ts
// --- the common-window comparison (R3, invariant 6) ---------------------------------------------

/** `n` consecutive dates from `start`. compare() reads dates, not a calendar: weekends do not matter. */
function days(start: string, n: number): string[] {
  const t0 = Date.parse(`${start}T00:00:00Z`);
  return Array.from({ length: n }, (_, i) => new Date(t0 + i * 86_400_000).toISOString().slice(0, 10));
}
const curveOf = (start: string, equities: number[]): Snapshot[] =>
  days(start, equities.length).map((date, i) => ({ date, equity: equities[i] }));
/** 100000 on every date but the last, so the window's total return is exactly `ret`. */
const flatThen = (n: number, ret: number) => [...Array(n - 1).fill(100000), 100000 * (1 + ret)];

const st = (id: string, status: 'active' | 'retired' = 'active'): RankIn =>
  ({ id, isChampion: false, isBenchmark: false, status });
const bench: RankIn = { id: 'SPY', isChampion: true, isBenchmark: true, status: 'active' };

// Shared window: 2026-03-02 .. 2026-05-03, 63 sessions — exactly MIN_COMMON_SESSIONS, so every
// fixture here is the smallest board that can be ranked at all.
const SHARED = '2026-03-02';
const N = MIN_COMMON_SESSIONS;        // 63
const A1 = { strategy: st('A1'), curve: curveOf(SHARED, flatThen(N, 0.01)) };
const B1 = { strategy: st('B1'), curve: curveOf(SHARED, flatThen(N, 0.005)) };
// Doubled its money before the window opened; inside it, it made 0.2%. Raw total return would
// crown it; the common window must not.
const OLD = {
  strategy: st('OLD'),
  curve: curveOf('2026-01-31', [...Array(30).fill(50000), ...flatThen(N, 0.002)]),
};
const SPY_ROW = { strategy: bench, curve: curveOf(SHARED, flatThen(N, 0.9)) };

describe('compare', () => {
  it('ranks over the sessions every compared strategy shares, and reports that window', () => {
    const c = compare([SPY_ROW, A1, B1, OLD]);
    expect(c.window).toEqual({ from: '2026-03-02', to: '2026-05-03', sessions: 63 });
    expect(c.ranked.map(r => r.strategy.id)).toEqual(['A1', 'B1', 'OLD']);
    expect(c.best?.strategy.id).toBe('A1');
    expect(c.best?.totalReturn).toBeCloseTo(0.01, 10);
    expect(c.best?.sessions).toBe(63);
  });

  it('is the engine module’s minimum, not its own', () => {
    // The one number that must never drift from seer_engine/paper/compare.py.
    expect(MIN_COMMON_SESSIONS).toBe(63);
    expect(MIN_RANKED).toBe(2);
  });

  it('drops the worst-overlapping strategy rather than ranking nothing', () => {
    // compare.py's `_select`: ODD overlaps the others by only 20 sessions, so including it would
    // leave the board below 63. It goes; the other three still rank over their own 63.
    const odd = { strategy: st('ODD'), curve: curveOf('2026-04-14', flatThen(80, 0.4)) };
    const c = compare([A1, B1, OLD, odd]);
    expect(c.window).toEqual({ from: '2026-03-02', to: '2026-05-03', sessions: 63 });
    expect(c.ranked.map(r => r.strategy.id)).toEqual(['A1', 'B1', 'OLD']);
    expect(c.rows.find(r => r.strategy.id === 'ODD')!.status).toBe('insufficient');
    expect(c.best!.strategy.id).toBe('A1'); // +40% but unranked: it does not win
  });

  it('does not depend on the order the rows arrive in', () => {
    const base = compare([A1, B1, OLD]);
    const shuffled = compare([OLD, B1, A1]);
    expect(shuffled.ranked.map(r => r.strategy.id)).toEqual(base.ranked.map(r => r.strategy.id));
    expect(shuffled.window).toEqual(base.window);
  });

  it('does not crown a return earned outside the window (what bestResearch got wrong)', () => {
    const c = compare([A1, B1, OLD]);
    const old = c.rows.find(r => r.strategy.id === 'OLD')!;
    expect(old.inception).toBeCloseTo(100200 / 50000 - 1, 10); // +100.4% inception to date
    expect(old.totalReturn).toBeCloseTo(0.002, 10);            // +0.2% over the shared window
    expect(c.best!.strategy.id).toBe('A1');                    // raw max would have said OLD
    expect(c.best!.totalReturn!).toBeLessThan(old.inception!);
  });

  it('never compares the benchmark', () => {
    const c = compare([SPY_ROW, A1, B1]);
    expect(c.rows.map(r => r.strategy.id)).toEqual(['A1', 'B1']);
  });

  it('calls a newcomer insufficient without letting it shorten the others’ window', () => {
    const fresh = { strategy: st('NEW'), curve: curveOf('2026-04-20', flatThen(9, 0.05)) };
    const c = compare([A1, B1, OLD, fresh]);
    expect(c.window).toEqual({ from: '2026-03-02', to: '2026-05-03', sessions: 63 });
    const n = c.rows.find(r => r.strategy.id === 'NEW')!;
    expect(n.status).toBe('insufficient');
    expect(n.sessions).toBe(9);
    expect(c.ranked.map(r => r.strategy.id)).toEqual(['A1', 'B1', 'OLD']);
    expect(c.best!.strategy.id).toBe('A1'); // +5% but unranked: it does not win
  });

  it('keeps a retired strategy’s record, out of the ranking and out of the window', () => {
    const gone = { strategy: st('GONE', 'retired'), curve: curveOf(SHARED, flatThen(N, 0.2)) };
    const c = compare([A1, B1, OLD, gone]);
    const g = c.rows.find(r => r.strategy.id === 'GONE')!;
    expect(g.status).toBe('retired');
    expect(g.inception).toBeCloseTo(0.2, 10);     // the record stands
    expect(g.totalReturn).toBeNull();             // but it is not a ranking
    expect(c.ranked.map(r => r.strategy.id)).not.toContain('GONE');
    expect(c.best!.strategy.id).toBe('A1');       // +20% retired does not win
    expect(c.window).toEqual({ from: '2026-03-02', to: '2026-05-03', sessions: 63 });
  });

  it('ranks nothing while the common window is short, and still reports how short', () => {
    const short = MIN_COMMON_SESSIONS - 11;   // 52
    const c = compare([
      { strategy: st('A1'), curve: curveOf(SHARED, flatThen(short, 0.01)) },
      { strategy: st('B1'), curve: curveOf(SHARED, flatThen(short, 0.02)) },
    ]);
    expect(c.ranked).toEqual([]);
    expect(c.best).toBeNull();
    // `window` is null whenever nothing ranked — compare.py's own guarantee. How short the board
    // still is lives in `shared`, which is never a ranking.
    expect(c.window).toBeNull();
    expect(c.shared).toBe(short);
    expect(c.rows.map(r => r.status)).toEqual(['insufficient', 'insufficient']);
  });

  it('leaves every windowed figure null on any row it did not rank', () => {
    const gone = { strategy: st('GONE', 'retired'), curve: curveOf(SHARED, flatThen(N, 0.2)) };
    const fresh = { strategy: st('NEW'), curve: curveOf('2026-04-20', flatThen(9, 0.05)) };
    for (const r of compare([A1, B1, gone, fresh]).rows) {
      if (r.status === 'ranked') continue;
      expect([r.totalReturn, r.cagr, r.maxDrawdown, r.sharpe]).toEqual([null, null, null, null]);
    }
  });
});

describe('windowLine', () => {
  it('names the window the ranking used and how many strategies it covered', () => {
    const w = windowLine(compare([A1, B1, OLD]));
    expect(w.label).toBe('Ranked over Mar 2 – May 3');
    expect(w.detail).toBe('63 shared sessions · 3 of 3 active strategies compared');
  });
  it('says how far off a window is rather than showing an unearned ranking', () => {
    const short = MIN_COMMON_SESSIONS - 11;
    const w = windowLine(compare([
      { strategy: st('A1'), curve: curveOf(SHARED, flatThen(short, 0.01)) },
      { strategy: st('B1'), curve: curveOf(SHARED, flatThen(short, 0.02)) },
    ]));
    expect(w.label).toBe('No common window yet');
    expect(w.detail).toBe(`${short} of ${MIN_COMMON_SESSIONS} sessions shared by every strategy`);
  });
});

describe('spyOverSpan', () => {
  it('measures the benchmark over the strategy’s own span, not over its whole record', () => {
    // 30 days at 10, then 63 days rising 100 → 162. The pick spans exactly those 63 days.
    const spy = curveOf('2026-01-31', [...Array(30).fill(10), ...Array(N).fill(0).map((_, i) => 100 + i)]);
    const pick = curveOf(SHARED, flatThen(N, 0.01));
    expect(spyOverSpan(spy, pick)).toBeCloseTo(162 / 100 - 1, 10);
  });
  it('is null when the benchmark has no snapshot on a boundary date', () => {
    expect(spyOverSpan(curveOf('2026-06-01', flatThen(5, 0.1)), curveOf(SHARED, flatThen(N, 0.01)))).toBeNull();
    expect(spyOverSpan(curveOf(SHARED, flatThen(N, 0.01)), [{ date: SHARED, equity: 1 }])).toBeNull();
  });
});

describe('pickResearch', () => {
  const list = [st('GONE', 'retired'), st('A1'), st('B1')];
  it('defaults to the first active strategy, never to a retired one', () => {
    expect(pickResearch(list, undefined)?.id).toBe('A1');
    expect(pickResearch(list, 'nope')?.id).toBe('A1');
  });
  it('honours an explicit request for a retired strategy: the record stays reachable', () => {
    expect(pickResearch(list, 'GONE')?.id).toBe('GONE');
  });
  it('falls back to the first row when every strategy is retired, and is null when there are none', () => {
    expect(pickResearch([st('GONE', 'retired')], undefined)?.id).toBe('GONE');
    expect(pickResearch([], undefined)).toBeNull();
  });
});

describe('retiredLabel', () => {
  it('names the date it stopped, and degrades before paper_end is written', () => {
    expect(retiredLabel('2026-12-02')).toBe('Retired Dec 2');
    expect(retiredLabel(null)).toBe('Retired');
  });
});
```

**Impact:** `view.test.ts` goes from 20 to 38 tests (+20 added, −2 deleted).

Hand-check of the fixtures, so the expected values can be verified without running anything.
2026 is not a leap year, which is what every date below turns on:

- `days('2026-03-02', 63)` ends at index 62 = `2026-05-03` (Mar 2 + 29 = Mar 31, +30 = Apr 30,
  +3 = May 3). That is the shared window, and it is exactly `MIN_COMMON_SESSIONS` long.
- `days('2026-01-31', 93)`: index 30 is `2026-01-31 + 30d` = `2026-03-02` (Feb has 28 days) and
  index 92 is `2026-05-03`. `OLD` therefore shares `A1`/`B1`'s exact 63 dates and no others.
- `flatThen(63, r)` is 62 values of `100000` and a last of `100000·(1+r)`, so the window's total
  return is exactly `r`, max drawdown is `0` for `r ≥ 0`, and — the shape being identical across
  `A1`, `B1` and `OLD` — the Sharpe ordering is the `r` ordering: `0.01 > 0.005 > 0.002`.
- `OLD`'s window anchor is its value on `2026-03-02`, which is `100000` (index 30 is the first of
  the `flatThen` block), so `+0.2%`; its inception anchor is `50000`, so `+100.4%`.
- `ODD` runs `2026-04-14 .. 2026-07-02` (80 days), overlapping the shared window by 20 sessions.
  Dropping `ODD` restores a 63-session intersection; dropping any of the other three leaves 20. So
  `selectRanked`'s first greedy step drops `ODD` and the remaining three rank — the behaviour the
  engine's `_select` has and this plan's first draft did not.
- `NEW` runs `2026-04-20 .. 2026-04-28` (9 days), inside the shared window, so it is dropped by the
  own-curve-length rule before any intersection is computed and cannot shorten anything.

---

## Verification

**Install:** `cd $SEER_WT/web && npm ci`
**Build:** `cd $SEER_WT/web && npm run build`
**Tests:** `cd $SEER_WT/web && npm test`
**Types:** `cd $SEER_WT/web && npx tsc --noEmit`
**Engine (unchanged, to prove the zero delta):** `cd $SEER_WT && "$SEER_PY" -m pytest engine/tests -q`

### Test DELTA

Both suites, measured on this worktree at the branch point (`0d03490`) before any phase landed.

| Suite | Delta |
|---|---|
| `web`: `npm test` | **+18 tests, +0 files** |
| `engine`: `pytest engine/tests -q` | **0** (this phase edits no Python) |
| `engine` with `PG_TEST_URL` | **0** |

The web baseline measured on this worktree at `0d03490` is `Test Files 24 passed (24) / Tests 247
passed (247)`, and `npm run build` compiles all 16 routes — so this phase alone would print 265.
**Report the delta, not that absolute**: the phases land in a swarm and the engine numbers in
particular are whatever phases 1–3 left.

The web +18 is `+20 added − 2 deleted`. The two deletions are the `bestResearch` tests, deleted
with the function they pin. No other existing test changes its result, and no test file is added or
removed.

**Manual check** (`npm run dev`, then `/leaderboard` on demo data at 414 pt and at desktop, light
and dark):

1. Under the big figures, a line reads either `Ranked over <Mon d> – <Mon d>` with
   `N shared sessions · k of m active strategies compared`, or `No common window yet` with
   `N of 63 sessions shared by every strategy`. **If no such line is visible, the phase is not
   done**, whatever the tests say. On demo data with fewer than 63 sessions the second form is the
   expected one — it is not a bug to fix, it is D8 showing.
2. The second big figure is either the best strategy's windowed return or `—`; it is never a number
   without the window line next to it.
3. `UPDATE strategies SET status='retired', paper_end='<a date in the record>' WHERE id='C'` on a
   dev database: C's card keeps all five metrics and gains a `Retired <date>` chip, its sheet dims,
   its legend entry dims, **its line stays on the chart**, its month-by-month table is still
   reachable from the switcher, and it is not the default pick and not the "best".
4. `UPDATE strategies SET status='active', paper_end=NULL WHERE id='C'` restores it exactly.
5. Six cards (temporarily inserting a sixth row) wrap to 5 + 1 at desktop with six distinct sheet
   and line pairs, and stack cleanly on mobile.

**Exit criteria:**

- `bestResearch` does not exist; `page.tsx` ranks with `compare` and prints `windowLine` on the page.
- A retired strategy renders with every snapshot, both markers and its full card, is excluded from
  `ranked` and from `best`, and is never the default pick.
- A strategy the comparison reports `insufficient` carries a `Not ranked` chip and keeps its card.
- `looks` gives 20 research strategies 20 distinct `(sheet, line)` pairs.
- `MIN_COMMON_SESSIONS === 63` and `MIN_RANKED === 2`, asserted by a test, and `compare`'s
  selection reproduces `compare.py`'s `_select` — including the greedy drop of the
  worst-overlapping strategy, which is the case `drops the worst-overlapping strategy rather than
  ranking nothing` pins.
- `npm test` is **+18** on what the phase inherited, `npm run build` green, `npx tsc --noEmit`
  clean.

---

## Assumptions

**A1 — Phase 1 has landed, with `status` spelled `'active'`/`'retired'` and `paper_end` a `date`.**
`web/lib/data.ts` selects `status` and `paper_end::text` by name. If phase 1 named the lifecycle
column something else, change the two identifiers in `strategies()`'s SQL and the `'retired'`
literal in `parseStatus`; nothing else in this phase reads the schema.

**A2 — Phase 3's math is ported, not called.** The index's phase 4 exit criterion allows either
("replaced by phase 3's windowed comparison, **or by a direct port of it**"). The port is forced,
not preferred: `/leaderboard` is a `force-dynamic` React server component rendering inside a
request against Neon, with no Python runtime in the Vercel function and no artefact of `compare.py`
on disk. Phase 3's own exit criteria describe a *pure function plus a read-only CLI to print a
table* — a CLI is not callable from a request. So the math is ported and `compare.py` is named in
`view.ts`'s header as the reference implementation.

**A3 — what agrees with phase 3. Reconciled: these are no longer assumptions, they are the
engine module's shipped values, copied here.** Changing any of them changes the leaderboard away
from the CLI, which is the one failure mode a port has that a call does not:

| What | Pinned value, from `paper/compare.py` |
|---|---|
| The common window | the plain **set intersection** of the selected strategies' snapshot dates — never `[max(start), min(end)]` |
| Who is selected | drop every curve shorter than the minimum on its own, then greedily drop the strategy whose removal leaves the longest intersection (ties: shortest own curve, then id), stopping at the minimum or at `MIN_RANKED` |
| Minimum sessions to rank | `MIN_COMMON_SESSIONS = 63` — one quarter of a trading year, three rebalances for a monthly-hold book. **This plan's draft said 21; 63 won on phase 3's exit criteria, which pin the number by name. See index Decisions D8** |
| `MIN_RANKED` | `2` |
| The risk-adjusted figure | annualised Sharpe at a zero risk-free rate, `mean / stdev(ddof=1) × √252`. **No Calmar and no `RANK_BY` knob** — both were in this plan's draft and both are removed, because a configurable rank key is a drift vector between two implementations that must agree |
| The rank order | finite Sharpe desc → no-Sharpe rows → total return desc → smaller max drawdown → id |
| `window === null` | exactly when nothing is ranked. The "how short is it still" number lives in the port's own `shared` field, which the engine has no equivalent of and never ranks |
| The statuses | `'ranked'` / `'insufficient'`, spelled identically. `'retired'` is the port's third status and is a **pre-filter outcome**, not an engine one |

`CompareRow`'s figure fields are exactly phase 3's `Performance` fields — total return, CAGR, max
drawdown, Sharpe — plus the session count and inception-to-date kept separate, under the same
names. There is one vocabulary.

**A4 — phase 2 may or may not have landed.** `retiredLabel(null)` renders plain `Retired`, so a row
retired before phase 2 writes `paper_end` still shows correctly.

**A5 — today's five roster entries all share one `paper_start`, and the live record is shorter
than 63 sessions.** So on the live board the window is the whole period, and **until the record
reaches 63 sessions the page shows `No common window yet` with `N of 63 sessions shared by every
strategy` and no "best" figure**. That is the intended behaviour and it is the visible cost of
D8: a "best" over 40 shared sessions is exactly the claim R3 exists to stop making, and the line
tells the reader how far off one is rather than going blank. The engine side offers
`compare --min-sessions N` for a human who wants to look earlier; the page does not, because a
page-level override is a setting nobody would read before trusting the number. The comparison's
teeth show in full once phase 5 or 6 adds a strategy with a later start — which is exactly when
they are needed.

## Handoffs

- **`positions/page.tsx` and `history/page.tsx` still default to the first research strategy
  regardless of `status`** (`selectStrategy`, `components/roster.ts:25`). After a retirement they
  can open on a retired strategy. The fix is `pickResearch`'s rule applied there, or `status`
  pushed into `selectStrategy`. Left out because those files belong to no phase in this set and
  `components/roster.ts` is explicitly outside this phase's ownership. **Serves no R in this set.**
- **`StrategyStatus`/`parseStatus` arguably belong in `web/lib/strategy.ts`**, beside `parseGate`,
  with a case in `lib/strategy.test.ts`. They are in `data.ts` here so this phase stays inside the
  five files the index assigns it. A later move is mechanical.
- **`web/scripts/seed-demo.mjs` does not seed `status` or `paper_end`.** It does not need to —
  phase 1's column defaults to `'active'` and `paper_end` is nullable — but a demo row exercising
  the retired presentation would be worth adding when the seed is next touched. Not this phase's
  file. **Serves no R in this set.**
- **Phase 6's `FND` is the first real test of `looks` beyond four and of the `insufficient`
  path.** This phase ships both and tests them with fixtures; phase 6 should confirm on the live
  board that `FND` renders with its own sheet and line and carries `Not ranked` for its first month.
- **`CHECKS = 6` needs no change for a fifth research strategy.** The go-live checklist is six rules
  about *one* strategy, so its arithmetic does not read the roster's length and cannot lie about it.
  What *could* lie was the "Beats SPY" row, which compared the picked strategy's inception-to-date
  return against SPY's inception-to-date return over a different span; Step 4b fixes that at the
  feeding site with `spyOverSpan`. `web/lib/metrics.ts` itself is untouched. (This is inside R3 —
  it is the same invariant 6 — so it is a step, not a handoff; recorded here because the scope note
  asked for the checklist to be checked.)
- **`web/lib/monthly.ts:108` (`all.totalReturn` for the since-start row) is correct as it stands.**
  It is labelled `Since <date>` and is explicitly one strategy's own record, not a ranking across
  strategies, so invariant 6 does not bind it. No change, by design, not by omission.

## Rollback

`git revert` the phase's single commit on `feature/roster-promotion-pipeline`. Nothing outside git
is written: this phase runs no migration, writes no row, and calls no service. The leaderboard
returns to the raw-`totalReturn` `bestResearch` and the four-look palette, and `web/lib/data.ts`
stops selecting `status` and `paper_end` — which also means **reverting this phase alone is safe
even if phase 1's migration is rolled back**, and is in fact the required order if it is: revert
phase 4 before dropping the columns, or `strategies()` will error on every page load.
