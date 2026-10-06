# Phase 5: Show reasons on the site

**Plan set:** `WHY_THIS_PICK_PIPELINE_PLAN.md`
**Analysis:** `20261006-213425-W7P3_code_analyzer.md`
**Satisfies:** R5, R6, R8 — every pick on Positions/Today shows its own reason (the LLM's text, else the method's own facts); C keeps its news-check line; "would pick now" rows get a reason; nothing technical on screen
**Depends on:** Phase 2 (migration 009 adds `evidence jsonb` to `orders`, `book_targets`, `book_previews`)
**Difficulty:** NORMAL
**Package:** `web`

---

## Goal

The web app reads each paper entry's stored evidence (a JSON array of plain-English facts) next
to its explanation. A "Why this pick" toggle shows the LLM's text when there is one, else the
facts as a short list, else "unavailable". "Would pick now" rows get a "Why it's on the list"
toggle with their facts (no LLM). All reads work both before and after the nightly applies 009.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- `web/lib/why.ts` (pure): `parseEvidence(raw: unknown): string[] | null`,
  `type Why = { kind: 'text'; text: string } | { kind: 'facts'; facts: string[] } | { kind: 'missing'; text: string }`,
  `whyContent(text, facts, missing): Why`
- `web/lib/why.test.ts` (vitest)
- CSS class `.facts` in `web/components/WhyToggle.module.css`
- demo `book_previews` rows (F4, F1) and demo `evidence` in `web/scripts/seed-demo.mjs`

**Signature changes:**
- `type Pick` (`web/lib/data.ts:148`) gains `evidence: string[] | null`
- `type PendingOrder` (`web/lib/data.ts:250`) gains `evidence: string[] | null`
- `type PreviewPick` (`web/lib/data.ts:315`) gains `evidence: string[] | null`
- `WhyToggle({ text, label?, missing? })` -> `WhyToggle({ text, facts?, label?, missing? })` (`facts` optional, default `null`; existing callers unchanged)

**Requires (from earlier phases):**
- Phase 2: migration `db/migrations/009_evidence.sql` adds a nullable `evidence jsonb` column to
  `orders`, `book_targets`, `book_previews`, holding a JSON **array of strings** (not a JSON
  string containing an array) or SQL NULL. The web reads it as `to_jsonb(<alias>) -> 'evidence'`,
  so it works before 009 is applied (key absent -> NULL). A non-array value is read as NULL.
- Phase 1: the fact strings are already plain English for the owner (no ids, no indicator codes).
  The web renders them verbatim; it does not rewrite them.
- Phase 3: `explanation` is either NULL or complete text (no "…"). The web shows whatever is there.

**Leaves alone (owned by others):** everything under `engine/`, `db/migrations/*` (phase 2),
`docs/runbooks/*`, `engine/package_readme.md` (phase 3), `.claude/skills/*` (phase 4).
`news_vetoes` reads (`vetoes()`), `lib/vetoes.ts` and C's "Why it passed the news check" line are
not changed.

## Files

| File | Action | What changes |
|---|---|---|
| `web/lib/why.ts` | create | `parseEvidence`, `Why`, `whyContent` (pure) |
| `web/lib/why.test.ts` | create | vitest for both helpers |
| `web/lib/data.ts` | modify | import `parseEvidence` (line 6); `Pick`/`picks` (148–161), `PendingOrder`/`pendingOrders` (249–313), `PreviewPick`/`bookPreview` (315–332) read `evidence` via `to_jsonb` |
| `web/components/WhyToggle.tsx` | modify | whole file: optional `facts` prop, renders text / facts list / missing via `whyContent` |
| `web/components/WhyToggle.module.css` | modify | add `.facts` list styles (mobile + desktop) |
| `web/app/(app)/positions/page.tsx` | modify | `WouldPick` (360–384) gets a facts toggle; `OrderRow` (408) passes `facts` |
| `web/app/(app)/page.tsx` | modify | `PickCard` (193) passes `facts` |
| `web/scripts/seed-demo.mjs` | modify | demo evidence on pending orders and book targets, demo `book_previews`, header says it needs migrations through 009 |
| `web/package_readme.md` | modify | layout, `lib/why.ts` API, data types, Positions flow, seed config, tests list, gotcha |

## Implementation Steps

### Step 1: Pure helper `lib/why.ts`
**File:** `web/lib/why.ts` (new)
**Change:** The single place that decides what a "why" toggle shows, and how a raw `evidence`
value from Neon becomes a list. Relative-import-free (vitest has no `@/` alias; this module
imports nothing).
**Code:**
```ts
/**
 * "Why this pick": what a reason toggle shows, and how a stored `evidence` value is read.
 *
 * `evidence` (migration 009, written by the engine's paper step) is a JSON array of short
 * plain-English facts: the numbers the method used for that pick. The LLM's explanation is
 * written from those facts; when there is no explanation the facts themselves are the reason.
 */

/**
 * A stored `evidence` value as a list of facts, or null when there is nothing usable. Defensive on
 * purpose: anything that is not an array (NULL, a missing key before 009 is applied, an object, a
 * string) reads as null, non-string items are dropped, items are trimmed and blank ones dropped,
 * and an array left empty reads as null.
 */
export function parseEvidence(raw: unknown): string[] | null {
  if (!Array.isArray(raw)) return null;
  const facts = raw
    .filter((f): f is string => typeof f === 'string')
    .map(f => f.trim())
    .filter(f => f !== '');
  return facts.length > 0 ? facts : null;
}

export type Why =
  | { kind: 'text'; text: string }
  | { kind: 'facts'; facts: string[] }
  | { kind: 'missing'; text: string };

/**
 * What a reason toggle shows: the plain-language text when there is one; else the facts, as a
 * short list; else the `missing` line. Blank text counts as no text.
 */
export function whyContent(text: string | null | undefined, facts: readonly string[] | null | undefined, missing: string): Why {
  const t = (text ?? '').trim();
  if (t !== '') return { kind: 'text', text: t };
  const f = parseEvidence(facts);
  if (f) return { kind: 'facts', facts: f };
  return { kind: 'missing', text: missing };
}
```
**Impact:** none on its own.

### Step 2: Tests for the helper
**File:** `web/lib/why.test.ts` (new)
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import { parseEvidence, whyContent } from './why';

const MISSING = 'Explanation unavailable for this pick.';

describe('parseEvidence', () => {
  it('keeps an array of strings, in order', () => {
    expect(parseEvidence(['GE closed at $273.18.', 'It was 1st of 6 stocks that qualified tonight.']))
      .toEqual(['GE closed at $273.18.', 'It was 1st of 6 stocks that qualified tonight.']);
  });

  it('reads anything that is not an array as null', () => {
    expect(parseEvidence(null)).toBeNull();
    expect(parseEvidence(undefined)).toBeNull();
    expect(parseEvidence('["a JSON string, not an array"]')).toBeNull();
    expect(parseEvidence({ facts: ['a'] })).toBeNull();
    expect(parseEvidence(42)).toBeNull();
    expect(parseEvidence(true)).toBeNull();
  });

  it('drops non-strings and blank items, and trims the rest', () => {
    expect(parseEvidence(['  rose 48.2%  ', 3, null, { a: 1 }, ['nested'], '', '   ', 'ranks 3rd of 412']))
      .toEqual(['rose 48.2%', 'ranks 3rd of 412']);
  });

  it('reads an array with nothing usable as null', () => {
    expect(parseEvidence([])).toBeNull();
    expect(parseEvidence([1, 2, null])).toBeNull();
    expect(parseEvidence(['', '  '])).toBeNull();
  });
});

describe('whyContent', () => {
  const facts = ['SPY closed at $671.20, 8.3% above its 200-day average.'];

  it('shows the text when there is one, even with facts', () => {
    expect(whyContent('F1 holds SPY because it closed above its long average.', facts, MISSING))
      .toEqual({ kind: 'text', text: 'F1 holds SPY because it closed above its long average.' });
  });

  it('trims the text', () => {
    expect(whyContent('  Short reason.  ', null, MISSING)).toEqual({ kind: 'text', text: 'Short reason.' });
  });

  it('falls back to the facts when the text is null or blank', () => {
    expect(whyContent(null, facts, MISSING)).toEqual({ kind: 'facts', facts });
    expect(whyContent(undefined, facts, MISSING)).toEqual({ kind: 'facts', facts });
    expect(whyContent('   ', facts, MISSING)).toEqual({ kind: 'facts', facts });
  });

  it('cleans the facts it falls back to', () => {
    expect(whyContent(null, ['', ' rose 12.0% '], MISSING)).toEqual({ kind: 'facts', facts: ['rose 12.0%'] });
  });

  it('says unavailable only when there is neither text nor facts', () => {
    expect(whyContent(null, null, MISSING)).toEqual({ kind: 'missing', text: MISSING });
    expect(whyContent(null, [], MISSING)).toEqual({ kind: 'missing', text: MISSING });
    expect(whyContent('', ['  '], MISSING)).toEqual({ kind: 'missing', text: MISSING });
  });

  it('uses the caller\'s missing line', () => {
    expect(whyContent(null, null, 'No reason was stored for this check.'))
      .toEqual({ kind: 'missing', text: 'No reason was stored for this check.' });
  });
});
```

### Step 3: Read `evidence` in the data layer
**File:** `web/lib/data.ts`

**3a — import (line 6).** After the `vetoes` import add:
```ts
import { parseEvidence } from '@/lib/why';
```

**3b — `Pick` and `picks` (lines 148–161).** Replace both with:
```ts
export type Pick = {
  id: number; slot: number; symbol: string; company: string; last: number;
  limit: number; tp: number; sl: number; shares: number; explanation: string | null;
  /** The facts the method used for this pick (migration 009); null when none were stored. */
  evidence: string[] | null;
};

/** The champion's pending bracket orders for one session (Today). Returns [] for SPY. */
export async function picks(strategyId: string, sessionDate: string): Promise<Pick[]> {
  // `to_jsonb(o) -> 'evidence'` never names the column: before the nightly applies migration 009 the
  // key is absent and the value is NULL, where `o.evidence` would fail the whole query.
  const rows = await sql`SELECT o.id, o.slot, o.symbol, o.company, o.last_price, o.limit_price, o.tp_price, o.sl_price,
      o.shares, o.explanation, to_jsonb(o) -> 'evidence' AS evidence
    FROM orders o WHERE o.strategy_id = ${strategyId} AND o.session_date = ${sessionDate} AND o.status = 'pending' ORDER BY o.slot`;
  return rows.map(r => ({
    id: n(r.id), slot: r.slot, symbol: r.symbol, company: r.company, last: n(r.last_price),
    limit: n(r.limit_price), tp: n(r.tp_price), sl: n(r.sl_price), shares: r.shares, explanation: r.explanation,
    evidence: parseEvidence(r.evidence),
  }));
}
```

**3c — `PendingOrder` and `pendingOrders` (lines 249–313).** Replace both with:
```ts
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
  /** The facts the method used for this pick (migration 009); null when none were stored. */
  evidence: string[] | null;
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
  // `to_jsonb(<row>) -> 'evidence'`: NULL, not a query error, before the nightly applies migration 009.
  const [[st], [ps], orders, targets] = await Promise.all([
    sql`SELECT engine, is_benchmark FROM strategies WHERE id = ${strategyId}`,
    sql`SELECT pending_session::text AS pending_session, pending_decision FROM paper_state WHERE strategy_id = ${strategyId}`,
    sql`SELECT o.id, o.session_date::text AS session_date, o.slot, o.symbol, o.company, o.last_price, o.limit_price, o.tp_price,
        o.sl_price, o.shares, o.explanation, to_jsonb(o) -> 'evidence' AS evidence
      FROM orders o WHERE o.strategy_id = ${strategyId} AND o.status = 'pending' ORDER BY o.session_date, o.slot`,
    sql`SELECT t.session_date::text AS session_date, t.rank, t.symbol, t.weight, t.last_price, t.limit_price,
        t.stop_price, t.take_price, t.explanation, to_jsonb(t) -> 'evidence' AS evidence
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
      evidence: parseEvidence(r.evidence),
    }));
    return { sessionDate: pendingSession ?? items[0]?.sessionDate ?? null, decision: true, orders: items };
  }
  if (engine === 'book') {
    const items: PendingOrder[] = targets.map(r => ({
      key: `t:${strategyId}:${ymd(r.session_date)}:${r.symbol}`, kind: 'book', sessionDate: ymd(r.session_date),
      rank: n(r.rank), slot: null, symbol: r.symbol, company: null, last: n(r.last_price), limit: nn(r.limit_price),
      tp: nn(r.take_price), sl: nn(r.stop_price), shares: null, weight: n(r.weight), explanation: r.explanation ?? null,
      evidence: parseEvidence(r.evidence),
    }));
    return { sessionDate: pendingSession, decision: ps?.pending_decision === true, orders: items };
  }
  return { sessionDate: pendingSession, decision: false, orders: [] };
}
```

**3d — `PreviewPick` and `bookPreview` (lines 315–332).** Replace with:
```ts
export type PreviewPick = {
  rank: number; symbol: string; weight: number; last: number;
  /** The facts the method used for this pick (migration 009); null when none were stored. Shown as-is, no LLM. */
  evidence: string[] | null;
};

/** What a book strategy would pick if it ranked tonight (`book_previews`, migration 008): display only. */
export type Preview = { dataDate: string | null; picks: PreviewPick[] };

export async function bookPreview(strategyId: string): Promise<Preview> {
  try {
    // `to_jsonb(p) -> 'evidence'`: NULL, not a query error, before the nightly applies migration 009.
    const rows = await sql`SELECT p.data_date::text AS data_date, p.rank, p.symbol, p.weight, p.last,
        to_jsonb(p) -> 'evidence' AS evidence
      FROM book_previews p WHERE p.strategy_id = ${strategyId} ORDER BY p.rank`;
    return {
      dataDate: rows[0] ? ymd(rows[0].data_date) : null,
      picks: rows.map(r => ({
        rank: n(r.rank), symbol: r.symbol, weight: n(r.weight), last: n(r.last), evidence: parseEvidence(r.evidence),
      })),
    };
  } catch {
    // Before the nightly applies 008 the table does not exist yet: no preview, not a broken page.
    return { dataDate: null, picks: [] };
  }
}
```
**Impact:** three types widen; `tsc` forces every constructor of them to set `evidence` (only
these three functions build them). `@neondatabase/serverless` returns `jsonb` already parsed,
so `r.evidence` is a JS array or `null`.

### Step 4: `WhyToggle` shows facts when there is no text
**File:** `web/components/WhyToggle.tsx` (whole file, lines 1–30)
**Change:** Optional `facts` prop; content chosen by `whyContent`. The button is unchanged:
icon-only Lucide chevron, `aria-label` and `data-tip` (UI law).
**Code:**
```tsx
'use client';

import { ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';
import { whyContent } from '@/lib/why';
import s from './WhyToggle.module.css';

/**
 * "Why this pick", collapsed by default. Shows the LLM's plain-language explanation when there is
 * one; else the facts the method used for the pick (`orders.evidence` and friends), as a short list;
 * else `missing`. `label` and `missing` let other plain-language reasons (the news check's verdicts,
 * "would pick now") reuse it unchanged.
 */
export function WhyToggle({ text, facts = null, label = 'Why this pick', missing = 'Explanation unavailable for this pick.' }: {
  text: string | null;
  facts?: readonly string[] | null;
  label?: string;
  missing?: string;
}) {
  const [open, setOpen] = useState(false);
  const tip = open ? 'Hide explanation' : label;
  const why = whyContent(text, facts, missing);
  return (
    <>
      <div className={s.row}>
        <button type="button" className={`icon-btn sm ${open ? 'inverted' : 'soft'}`} data-tip={tip} aria-label={tip}
          aria-expanded={open} onClick={() => setOpen(o => !o)}>
          {open ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </button>
        <span className={s.label}>{label}</span>
      </div>
      {open && (why.kind === 'facts' ? (
        <ul className={s.facts}>
          {why.facts.map((f, i) => <li key={i}>{f}</li>)}
        </ul>
      ) : (
        <p className={s.why}>{why.text}</p>
      ))}
    </>
  );
}
```
**Impact:** existing callers (`VetoRow`, C's passed line) pass no `facts`, so they behave exactly
as before (text, else their `missing`).

### Step 5: Facts list styles
**File:** `web/components/WhyToggle.module.css` (whole file, lines 1–9)
**Code:**
```css
.row { display: flex; align-items: center; gap: 12px; }
.label { font-size: 15px; color: var(--ink-2); }
.why { margin-top: -4px; font-size: 17px; line-height: 1.5; text-wrap: pretty; }
.facts {
  margin: -4px 0 0; padding: 0; list-style: none;
  display: flex; flex-direction: column; gap: 8px;
  font-size: 17px; line-height: 1.45; text-wrap: pretty;
}
.facts li { position: relative; padding-left: 16px; }
.facts li::before {
  content: ''; position: absolute; left: 2px; top: 0.62em;
  width: 6px; height: 6px; border-radius: 50%; background: var(--ink-2);
}

@media (min-width: 1024px) {
  .row { gap: 10px; }
  .label { font-size: 14px; }
  .why { margin-top: 0; font-size: 15px; }
  .facts { margin-top: 0; gap: 6px; font-size: 15px; }
}
```
**Impact:** colours come from existing tokens (`--ink-2`), which `globals.css` redefines under
`prefers-color-scheme: dark`, so dark mode needs nothing extra.

### Step 6: Positions — order rows and "would pick now"
**File:** `web/app/(app)/positions/page.tsx`

**6a — `OrderRow`, line 408.** Replace
```tsx
      <WhyToggle text={o.explanation} />
```
with
```tsx
      <WhyToggle text={o.explanation} facts={o.evidence} />
```
Lines 409–415 (C's headline count line and `<WhyToggle ... label="Why it passed the news check" ...>`)
stay exactly as they are (R5).

**6b — `WouldPick`, lines 356–384.** Replace the doc comment and function with:
```tsx
/**
 * What a book strategy would hold if it rebalanced tonight (`book_previews`): shown between its monthly
 * decisions so a monthly strategy is never silent. Display only: nothing trades on it. Each row's reason
 * is the facts the ranking read, as stored (no LLM: previews are replaced every night); a row without
 * stored facts shows no toggle rather than a list of "unavailable" lines.
 */
function WouldPick({ st, preview }: { st: Strategy; preview: Preview }) {
  return (
    <section className={`sheet over bg-sheet ${s.orders}`}>
      <div className={s.between}>
        <span className="eyebrow">{st.short} would pick now</span>
        <span className="chip num">{preview.picks.length}</span>
      </div>
      <span className={s.ordersSub}>
        From the {shortDate(preview.dataDate!)} closes. {st.short} only trades when it rebalances, on the first session of each month.
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
**Impact:** no new imports (`WhyToggle` is already imported at line 6).

### Step 7: Today — `PickCard`
**File:** `web/app/(app)/page.tsx:193`
**Change:** Replace
```tsx
      <WhyToggle text={p.explanation} />
```
with
```tsx
      <WhyToggle text={p.explanation} facts={p.evidence} />
```
**Impact:** none visible today (SPY is champion, so Today shows no picks); "SPY buy-and-hold is
the champion" copy untouched.

### Step 8: Demo data carries evidence
**File:** `web/scripts/seed-demo.mjs`

How the seed runs (verified): `npm run db:seed-demo` = `node --env-file=.env.local
scripts/seed-demo.mjs` against `DATABASE_URL_UNPOOLED`. It refuses any database where real engine
runs, >100 bars or real paper state exist, so it only ever targets a fresh/empty Neon database —
never production. On such a database the order is `npm run db:migrate` (applies 001–009) then
`npm run db:seed-demo`. Its INSERTs now name `evidence` and `book_previews`, so it needs 008 and
009 applied first; this is written in the header and in `package_readme.md`. `--dry-run` builds
every row without connecting. Demo facts are fixed arithmetic, never `rnd()`, so the random
sequence (and every other demo number) is unchanged.

**8a — header, line 7.** Replace
```js
// Needs migration 004 (news_vetoes, the C row's columns) applied first.
```
with
```js
// Needs migrations through 009 applied first (`npm run db:migrate`): 004 (news_vetoes, the C row's
// columns), 008 (book_previews) and 009 (`evidence` on orders, book_targets and book_previews).
// Pending orders, book targets and "would pick now" rows carry demo evidence: plain-English facts.
```

**8b — helpers, after line 19 (`const r4 = …`).** Insert:
```js
// Money as the engine's facts write it (strategies/evidence.py `_money`): "$1,231.40".
const $ = v => '$' + v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const ordinal = k => {
  const t = k % 100, u = k % 10;
  return k + (t >= 11 && t <= 13 ? 'th' : u === 1 ? 'st' : u === 2 ? 'nd' : u === 3 ? 'rd' : 'th');
};
// An `evidence` value for a jsonb parameter: a JSON array of strings, or NULL.
const json = v => (v === null || v === undefined ? null : JSON.stringify(v));
```

**8c — row lists, line 87.** Replace
```js
const bookTargets = []; // [strategy, session, rank, symbol, weight, last, limit, stop, take, explanation]
```
with
```js
const bookTargets = []; // [strategy, session, rank, symbol, weight, last, limit, stop, take, explanation, evidence?]
const bookPreviews = []; // [strategy, rank, symbol, weight, last, evidence]: "would pick now" for dataDate
```

**8d — F1, lines 112–114.** Replace
```js
  const why = 'SPY closed above its 200-day average, so F1 holds SPY for the month.';
  for (const d of decisions) bookTargets.push([id, sessions[d], 1, 'SPY', 1, spy[d - 1], null, null, null, why]);
  if (pendingDecision) bookTargets.push([id, session, 1, 'SPY', 1, spy[LAST], null, null, null, why]);
```
with
```js
  const why = 'SPY closed above its 200-day average, so F1 holds SPY for the month.';
  // The facts F1's rule read (demo numbers), in the engine's exact TIMING wording (phase 1 "Fact strings").
  const f1Facts = close => [
    `SPY closed at ${$(close)}, 6.2% above its 200-day average of ${$(close / 1.062)}.`,
    'The rule holds SPY while SPY closes above its 200-day average, so it holds SPY.',
  ];
  for (const d of decisions) bookTargets.push([id, sessions[d], 1, 'SPY', 1, spy[d - 1], null, null, null, why, f1Facts(spy[d - 1])]);
  if (pendingDecision) bookTargets.push([id, session, 1, 'SPY', 1, spy[LAST], null, null, null, why, f1Facts(spy[LAST])]);
  bookPreviews.push([id, 1, 'SPY', 1, spy[LAST], f1Facts(spy[LAST])]);
```

**8e — F4, lines 141–151.** Replace from `let invested = 0;` through the end of the
`HELD.forEach(...)` call (`});` on line 151) with:
```js
  // The facts F4's ranking read (demo numbers, falling with rank), in the engine's exact FACTOR wording
  // (phase 1 "Fact strings"): the price move, its rank, the market filter.
  const f4Facts = rank => [
    `Its price rose ${(61.4 - rank * 2.3).toFixed(1)}% from 12 months ago to 1 month ago.`,
    `It ranked ${ordinal(rank)} of 412 stocks checked on that move, strongest first.`,
    'SPY closed 4.1% above its 200-day average, so the method is allowed to hold stocks.',
  ];
  let invested = 0;
  HELD.forEach(([sym, mark, early], rank) => {
    const from = early ? FIRST_DECISION : LAST_DECISION;
    const entry = r2(mark / (1 + (rnd() - 0.4) * 0.15));
    const shares = Math.max(1, Math.floor((0.05 * E) / mark));
    invested += shares * mark;
    const facts = f4Facts(rank + 1);
    bookPositions.push([id, sym, shares, mark, sessions[from], entry, LAST - from + 1, r4(shares * entry * (1 + FEE)), 0, null, null, false]);
    bookTargets.push([id, sessions[LAST_DECISION], rank + 1, sym, 0.05, r2(mark * (1 + (rnd() - 0.5) * 0.04)), null, null, null,
      rank === 0 ? `${sym} rose the most of the index members from 12 months ago to 1 month ago, and SPY is above its 200-day average.` : null, facts]);
    if (pendingDecision) bookTargets.push([id, session, rank + 1, sym, 0.05, mark, null, null, null, null, facts]);
    bookPreviews.push([id, rank + 1, sym, 0.05, mark, facts]);
  });
```
(The two `rnd()` calls keep their original order. Line 170's first-decision targets keep 10
elements; the insert in 8j reads a missing 11th element as NULL.)

**8f — A's picks, lines 176–185.** Replace with:
```js
// --- bracket portfolios (A, C): pending picks, open orders, closed trades -------------
// A's facts for a pick (demo numbers), in the engine's exact STRATEGY_A wording (phase 1 "Fact
// strings"): close vs its 200-day average, the 2-day strength score, the 2- and 5-day moves, daily
// trading value, and its place among the stocks that passed the rule. C trades A's picks, so its
// pending orders carry the same facts (the engine's C evidence is A's under C's params).
const aFacts = ({ close, above, score, d2, d5, traded, place, of }) => [
  `It closed at ${$(close)}, ${above.toFixed(1)}% above its 200-day average of ${$(close / (1 + above / 100))}.`,
  `Its 2-day strength score was ${score} out of 100; below 10 counts as a sharp short drop.`,
  `Over the last 2 trading days it fell ${d2.toFixed(1)}%, and over the last 5 it fell ${d5.toFixed(1)}%.`,
  `On an average day over the last 20 trading days, ${traded} of its shares changed hands.`,
  `It ranked ${ordinal(place)} of ${of} stocks that passed the rule that day, lowest strength score first.`,
];
const A_FACTS = {
  GE: aFacts({ close: 273.18, above: 9.4, score: 4, d2: 3.1, d5: 4.8, traded: '$1.6 billion', place: 1, of: 6 }),
  LRCX: aFacts({ close: 99.64, above: 12.7, score: 3, d2: 5.2, d5: 7.9, traded: '$1.1 billion', place: 2, of: 6 }),
  CSCO: aFacts({ close: 67.42, above: 3.8, score: 8, d2: 1.6, d5: 2.4, traded: '$1.3 billion', place: 3, of: 6 }),
};

// Pending picks: [slot, symbol, company, last, limit, tp, sl, shares, explanation, evidence]. CSCO has no
// explanation, so the demo shows the facts standing in for it.
const picks = [
  [1, 'GE', 'GE Aerospace', 273.18, 271.40, 278.90, 260.15, 1,
    'GE fell three days in a row and now sits below its usual range, while its longer trend is still up. Strategy A buys short dips like this when they have usually recovered within a week. The limit is a little under the last price, so it only buys if the price dips further at the open.',
    A_FACTS.GE],
  [2, 'LRCX', 'Lam Research', 99.64, 98.20, 102.10, 92.35, 3,
    'Chip-equipment stocks sold off and Lam Research dropped more than its peers without news of its own. Past drops of this size have tended to win back part of the move within five sessions. The stop sits below last month’s low.',
    A_FACTS.LRCX],
  [3, 'CSCO', 'Cisco Systems', 67.42, 66.85, 68.30, 64.70, 4, null, A_FACTS.CSCO],
];
```

**8g — C's picks, lines 237–242.** Replace with:
```js
const cPicks = [
  [1, 'GE', 'GE Aerospace', 273.18, 271.40, 278.90, 260.15, 1,
    'Strategy C takes the same GE dip as Strategy A. The news check read six recent headlines, all routine contract and product news with no earnings date in the next five sessions, so it let the pick through.',
    A_FACTS.GE],
  [2, 'CSCO', 'Cisco Systems', 67.42, 66.85, 68.30, 64.70, 4,
    'Cisco slipped to the bottom of its two-week range, the same setup Strategy A sees. Its recent news is product launches and analyst notes without a rating change, so the news check allowed it.',
    A_FACTS.CSCO],
];
```

**8h — row map, lines 279–280.** Replace with:
```js
const rows = { strategies, snapshots, paperState, bookPositions, bookTargets, bookPreviews, bookTrades, picks, open, closed,
  cPicks, cOpen, cClosed, newsVetoes };
```

**8i — TRUNCATE, lines 303–304.** Replace with:
```js
  await c.query(`TRUNCATE action_dismissals, orders, equity_snapshots, bars, fx_rates, runs, paper_state, book_positions,
    book_targets, book_previews, book_fills, book_trades, dividends, news_vetoes, strategies RESTART IDENTITY CASCADE`);
```

**8j — pending order insert, lines 317–319.** Replace with:
```js
    for (const [slot, sym, name, last, lim, tp, sl, sh, why, facts] of b.picks) {
      await c.query(`INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, limit_price, tp_price, sl_price, shares,
          explanation, evidence, status)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,'pending')`, [b.id, session, slot, sym, name, last, lim, tp, sl, sh, why, json(facts)]);
```
(the following `await bar(sym, last);` and `}` stay.)

**8k — book target insert, lines 357–359.** Replace with:
```js
  for (const r of bookTargets)
    await c.query(`INSERT INTO book_targets (strategy_id, session_date, rank, symbol, weight, last_price, limit_price, stop_price, take_price,
        explanation, evidence) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)`, [...r.slice(0, 10), json(r[10])]);

  for (const [id, rank, sym, weight, last, facts] of bookPreviews)
    await c.query(`INSERT INTO book_previews (strategy_id, data_date, rank, symbol, weight, last, evidence)
      VALUES ($1,$2,$3,$4,$5,$6,$7)`, [id, dataDate, rank, sym, weight, last, json(facts)]);
```

**8l — counts, lines 366–370.** Replace with:
```js
  const counts = await c.query(`SELECT 'orders ' || status AS what, count(*)::int AS n FROM orders GROUP BY status
    UNION ALL SELECT 'book_positions', count(*)::int FROM book_positions
    UNION ALL SELECT 'book_previews', count(*)::int FROM book_previews
    UNION ALL SELECT 'book_trades', count(*)::int FROM book_trades
    UNION ALL SELECT 'equity_snapshots', count(*)::int FROM equity_snapshots
    UNION ALL SELECT 'news_vetoes', count(*)::int FROM news_vetoes ORDER BY what`);
```
**Impact:** demo only. Nothing on screen gets an id or code: every demo fact is a sentence in the
engine's own fact wording (phase 1 "Fact strings"), with no advice word (the reconciled trend fact
says "allowed to hold stocks"), and the one demo text that named the code `12-1` now says it in words
(invariant 7).

### Step 9: `web/package_readme.md`
**File:** `web/package_readme.md`
- **Line 3** (`**Last Updated**`): replace with
  `**Last Updated**: 2026-10-06 (why-this-pick-pipeline phase 5: "Why this pick" falls back to the method's stored facts; "would pick now" rows show theirs; `lib/why.ts`)`
- **Layout, `lib/` block (after the `vetoes.ts` line, ~line 89):** add
  `    why.ts                  parseEvidence, Why, whyContent: what a "why" toggle shows     (pure)`
- **Exported API, new section after `### lib/vetoes.ts` (before `### lib/data.ts`, ~line 187):**
  ````markdown
  ### lib/why.ts (pure)

  ```ts
  function parseEvidence(raw: unknown): string[] | null;   // non-array -> null; non-strings and blanks dropped; empty -> null
  type Why = { kind: 'text'; text: string } | { kind: 'facts'; facts: string[] } | { kind: 'missing'; text: string };
  function whyContent(text: string | null | undefined, facts: readonly string[] | null | undefined, missing: string): Why;
  ```

  - `evidence` (migration 009, written by the engine's paper step) is a JSON array of short plain-English facts: the numbers the method used for that pick. The engine's Explain step writes `explanation` from them.
  - `whyContent`: the text when it is non-blank; else the facts (a short list); else `missing`. `WhyToggle` renders it.
  ````
- **lib/data.ts Types:** `Pick` line becomes "a champion's pending bracket order for Today, with
  `evidence`"; append to the `PendingOrder` / `Pending` bullet: "`evidence: string[] | null` is the
  method's stored facts for the pick."; add a bullet: "`PreviewPick` / `Preview`: `book_previews`
  rows (`rank, symbol, weight, last, evidence`) for 'would pick now'."
- **lib/data.ts Functions:** add a bullet: "`bookPreview(strategyId): Promise<Preview>`: tonight's
  'would pick now' list; empty when 008 is not applied. `picks`, `pendingOrders` and
  `bookPreview` read `evidence` as `to_jsonb(<row>) -> 'evidence'`, so they work before the
  nightly applies 009 (the value is NULL), and pass it through `parseEvidence`."
- **Data Flow, Positions bullet (line 323):** append: "Every order row's `WhyToggle` gets
  `facts={o.evidence}`: it shows the explanation, else the facts as a list, else 'unavailable';
  C's 'Why it passed the news check' line follows unchanged. For a book strategy between
  decisions, `bookPreview` feeds 'would pick now'; each row with stored facts has a 'Why it's on
  the list' toggle showing them (no LLM)." Today bullet: append "`PickCard`'s 'Why this pick' uses
  the same fallback."
- **Configuration, `db:seed-demo` bullet (line 404):** replace "Needs migration 004 applied
  first." with "Needs migrations through 009 applied first (`npm run db:migrate`, then
  `npm run db:seed-demo`; it only runs on an empty database, never production)." and replace
  "`book_targets`, `book_trades`" with "`book_targets` and `book_previews` (pending orders,
  targets and previews with demo `evidence`; A's CSCO has no explanation so its facts show),
  `book_trades`".
- **Configuration, `npm test` bullet (line 405):** add `why` to the list of pure modules.
- **Gotchas (end of list, ~line 429):** add
  "- Read `evidence` only as `to_jsonb(<row>) -> 'evidence'`, never as a plain column: Vercel deploys on push, hours before the nightly applies 009, and a named missing column fails the whole query. The facts are rendered verbatim, so they must stay plain English (the engine's evidence module owns the wording)."

## Verification

**Setup (worktree has no `.env.local`; never use main's tree for the build):**
```bash
cp /home/miftah/seer/web/.env.local /home/miftah/.worktrees/seer/why-this-pick-pipeline/web/.env.local   # gitignored (.env*)
cd /home/miftah/.worktrees/seer/why-this-pick-pipeline/web && ls node_modules/.bin/next   # else: npm ci
```

**Build:** `cd /home/miftah/.worktrees/seer/why-this-pick-pipeline/web && npx tsc --noEmit && npx next build`
**Tests:** `cd /home/miftah/.worktrees/seer/why-this-pick-pipeline/web && npx vitest run` (new `lib/why.test.ts` plus every existing suite);
`node --check scripts/seed-demo.mjs && node scripts/seed-demo.mjs --dry-run` (prints counts incl. `bookPreviews: 13`, no connection).
Plan invariant 1, in full, at phase end (engine unaffected by this phase, still run):
`docker start seer-pg`, then from the worktree root
`PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`
(passes except the two known Python-3.12-only failures `test_f_fundamental.py::test_allocator_shape`
and `test_market_fundamentals.py::test_adding_the_hook_does_not_change_the_allocator_check`) and
`engine/.venv/bin/ruff check engine`.

**Manual check — `next dev` with a minted session, screenshots at 414 px light and dark:**

1. Start the dev server against the `.env.local` database (production Neon, read-only use):
   `cd /home/miftah/.worktrees/seer/why-this-pick-pipeline/web && npx next dev -p 3000` (run in background).
   Note: `next dev` may rewrite `web/AGENTS.md`'s managed block; don't commit an unrelated diff there.
2. Write the shooter in the scratchpad (not in the repo), e.g. `$SCRATCH/shoot.mjs`:
   ```js
   // node --env-file=/home/miftah/.worktrees/seer/why-this-pick-pipeline/web/.env.local shoot.mjs <outDir> [suffix]
   import { chromium } from '/home/miftah/run-insights/node_modules/playwright-core/index.mjs';
   import { encode } from '/home/miftah/.worktrees/seer/why-this-pick-pipeline/web/node_modules/next-auth/jwt.js';

   const BASE = 'http://localhost:3000';
   const [out, suffix = ''] = process.argv.slice(2);
   const email = process.env.ALLOWED_EMAIL.split(',')[0].trim();
   // Auth.js v5 JWT session: http cookie name 'authjs.session-token', which is also the HKDF salt.
   const token = await encode({
     token: { email, name: 'Owner', sub: 'local-check' }, secret: process.env.AUTH_SECRET, salt: 'authjs.session-token',
   });
   const PAGES = [
     ['today', '/'],
     ['pos-A', '/positions?s=A'],
     ['pos-C', '/positions?s=C'],
     ['pos-F4', '/positions?s=F4-MOM12-N20-TREND'],
     ['pos-F1', '/positions?s=F1-SPY-SMA200-M'],
   ];
   const browser = await chromium.launch();
   for (const [scheme, width] of [['light', 414], ['dark', 414], ['light', 1280]]) {
     const ctx = await browser.newContext({ viewport: { width, height: 900 }, deviceScaleFactor: 2, colorScheme: scheme });
     await ctx.addCookies([{ name: 'authjs.session-token', value: token, domain: 'localhost', path: '/', httpOnly: true, sameSite: 'Lax' }]);
     const page = await ctx.newPage();
     for (const [name, path] of PAGES) {
       await page.goto(BASE + path, { waitUntil: 'networkidle' });
       if (page.url().includes('/signin')) throw new Error(`not signed in on ${path}: check AUTH_SECRET / ALLOWED_EMAIL`);
       // Open every reason toggle so the shot shows what each one reveals.
       for (const b of await page.locator('button[aria-expanded="false"][data-tip^="Why"]').all()) await b.click();
       await page.screenshot({ path: `${out}/${name}-${scheme}-${width}${suffix}.png`, fullPage: true });
     }
     await ctx.close();
   }
   await browser.close();
   ```
   Add the FND strategy's `?s=` id too (take it from the Positions strategy switch).
3. **Pass A — production data as it is (009 not applied yet, or applied with NULL evidence):**
   `node --env-file=…/web/.env.local $SCRATCH/shoot.mjs $SCRATCH/shots`. Every page renders (no
   error boundary: proves the `to_jsonb` guard); bracket rows show their explanation or
   "Explanation unavailable for this pick."; C's rows still show the headline line and "Why it
   passed the news check"; F4/F1/FND "would pick now" rows show **no** toggle while evidence is NULL.
4. **Pass B — facts rendering, with a throwaway unstaged edit:** `git add -A web` (stage the real
   work), then temporarily make `parseEvidence` in `web/lib/why.ts` return
   `['Demo fact: rose 48.2% over the 12 months up to a month ago.', 'Demo fact: that is the 3rd strongest rise of the 412 stocks checked.']`
   when `raw` is `null`/`undefined`; let `next dev` hot-reload; run the shooter with suffix `-facts`;
   then `git checkout -- web/lib/why.ts` (restores the staged version) and confirm
   `git diff -- web/lib/why.ts` is empty. Check: C's rows (explanation NULL on prod) show the
   bullet list under "Why this pick" and then the news-check line; "would pick now" rows show a
   "Why it's on the list" toggle with the list; A's rows with text still show text, not facts.
5. Read every PNG: 414 px light and dark and 1280 desktop — bullets align with the text, no
   horizontal scroll, list colour readable in dark, chevron button unchanged (icon-only, tooltip
   on hover), no ids/codes/column names anywhere.

**Exit criteria:** `vitest` (incl. `lib/why.test.ts`) and `tsc --noEmit` pass; `next build`
succeeds; seed dry-run passes; Positions and Today render against a database without 009; a
"Why this pick" with NULL text and stored evidence shows the facts as a list, with neither shows
"Explanation unavailable for this pick."; "would pick now" rows with evidence show "Why it's on
the list"; C's "Why it passed the news check" line is unchanged; screenshots at 414 px light and
dark (and desktop) were looked at.

## Handoffs

- **Phase 2 (R1, R6):** store `evidence` as a jsonb **array** (e.g. psycopg `Jsonb(list(facts))`),
  never a JSON-encoded string inside jsonb; the web reads a jsonb string as NULL by design
  (`parseEvidence` rejects non-arrays). Previews must get evidence too for R6 to show anything.
- **Phase 1 (R8):** the site renders fact strings verbatim; plain wording (no `RSI(2)`, `SMA200`,
  `12-1`, ids) is enforced only in the engine's evidence module and its tests.
- **Phase 3 (R2/R4):** demo `explanation` texts in `seed-demo.mjs` still read like the old long
  style (three sentences, some order mechanics). Left as is: they are demo data and rewriting them
  is not needed for this phase; a later cleanup could shorten them to the new 2-sentence style.
- **Not done (no owner):** existing production rows written before this ships keep NULL
  evidence and show their old text or "unavailable" (plan scope: no re-explaining).

## Rollback

Revert this phase's commit. The web goes back to reading `explanation` only; `evidence` columns
(phase 2) stay unread. The seed reverts to not writing `evidence`/`book_previews`, which still
works on a database that has 009.
