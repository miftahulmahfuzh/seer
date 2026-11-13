# Phase 6: The signal map on `/sera/signals`

**Plan set:** `SERA_SIGNAL_PANEL_PLAN.md`
**Analysis:** `.workflows/analyze/20261113-200537-K7P2_code_analyzer.md`
**Satisfies:** R6 — the owner can read the panel's ranked map of stock-picking ideas on the site, in plain words
**Criteria:** R6.2, R6.3
**Depends on:** Phase 2
**Difficulty:** NORMAL
**Package:** `web/app/sera/signals`

---

## Goal

A new Sera page, `/sera/signals`, reads the `panel` key that phase 2 adds to `web/data/lab.json`
and shows every measured stock-picking idea, ranked, each named by what it ranks on, with its
verdict, its three readings and its origin in everyday words and never an id, digest or code.
When the snapshot holds no panel rows (the committed state until Sera's first replay) the page
says so as an empty state. The page is reachable from a seventh tab in Sera's rail and phone bar,
and it renders 50 rows per page so 1,500+ rows never ship as one megabyte-scale HTML document.

## Interface Contract

**Deletes:** nothing
**Renames:** nothing
**Creates:**
- route `/sera/signals` (`web/app/sera/signals/page.tsx`), query param `?page=N`
- `web/app/sera/signals/view.ts`: `PAGE_SIZE`, `EMPTY_TEXT`, `FINDING_TEXT`, type `PanelSignal`, type `SignalRowView`, type `SignalMap`, `rankSignals`, `displayNames`, `readings`, `controlled`, `parsePage`, `pageHref`, `signalMap`
- `web/app/sera/signals/view.test.ts`, `web/app/sera/signals/signals.module.css`
- nav tab `{ href: '/sera/signals', icon: Radar, tip: 'Signal map' }` in `web/components/sera/SeraNav.tsx`
**Signature changes:** none
**Requires (from earlier phases):**
- Phase 2: `LabSnapshot` in `web/lib/sera/types.ts` has a `panel` key shaped as the plan index's Shared contracts: `panel: { rule: string; fdr: number; signals: Array<{ id: string; kind: 'signal' | 'replay'; name: string; family: string; methodId: string | null; clears: boolean; q: number | null; reasons: string[]; twinOf: string | null; dev: { all, pre2009, recent } | null; survivorship: { all, pre2009, recent } | null }> }`, each era object `{ months, ic, icT, spread, spreadT, slope, slopeT, turnover }` **or null** (reconciled: phase 1 leaves out an era with fewer than 12 measured months, and `dev` is null for a panel not measured on the current dev store). `spread` is annualised; `slope` is monthly. This phase derives every type it uses from `LabSnapshot['panel']`, so phase 2's own names for those types (`LabPanel`, …) do not matter; only the field names do.
- Phase 2: the committed worktree `web/data/lab.json` carries `"panel": {"rule": "panel-v1", "fdr": 0.1, "signals": []}` (version 9).
- Phase 2: `reasons` are owner-readable sentences (one per failed condition, no ids, no code, no column names). This phase prints them as given and adds a test that fails the build if the committed snapshot ever publishes one that is not (Step 2). A replay's `name` is its method's own `methods.name` (Decisions): owner-facing already on `/sera/methods`, and it may legitimately mention another method, so the committed-snapshot pin covers `reasons` only.
**Leaves alone (owned by others):** `web/lib/sera/types.ts`, `web/lib/sera/lab.ts`, `web/lib/sera/lab.test.ts`, `web/app/sera/overview.test.ts`, `web/lib/sera/fixture.ts`, `web/data/lab.json` (phase 2); `.claude/skills/verify-seer/features/README.md` (phase 3 adds its row there); `web/lib/sera/glossary.ts` and `glossary.test.ts` (not needed: every term on the page is said in plain words); the engine (phases 1-5).

## Files

| File | Action | What changes |
|---|---|---|
| `web/app/sera/signals/view.ts` | create | pure view-model: ranking, plain-word readings, verdict, origin, twin line, pagination |
| `web/app/sera/signals/view.test.ts` | create | vitest: behaviour of the view-model on fixture panels, plus a no-ids pin on the committed snapshot |
| `web/app/sera/signals/page.tsx` | create | the server component: header, tally, finding, ranked page of rows, pager, empty state |
| `web/app/sera/signals/signals.module.css` | create | layout for the rows, one presentation at every width |
| `web/components/sera/SeraNav.tsx:3,8-15,32-36,71,95` | modify | seventh tab (Radar, "Signal map") after Methods; comments say seven |
| `web/components/sera/SeraNav.module.css:30-55,57-58` | modify | phone bar fits seven tabs: 364 px wide, 48 px tracks, 2 px gap |
| `web/components/sera/PageHeader.tsx:31` | modify | comment only: "six-tab bar" -> "seven-tab bar" (made false by this phase's tab) |
| `.claude/skills/verify-seer/features/sera.md` | modify | sub-feature line, how to get there, two driving lines, two gotchas |

## Implementation Steps

Next.js reading done for this plan: `web/AGENTS.md`; `node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/page.md` (Next 16.3.8: `searchParams` is a `Promise` and must be awaited; reading it makes the page render at request time, which is what `/sera/methods` and `/sera/journal` already do with the same `{ searchParams }: { searchParams: Promise<Search> }` shape). The implementer re-reads `page.md` before writing `page.tsx`.

Worktree setup (once, before Step 1): `cp -al /home/miftah/seer/web/node_modules /home/miftah/.worktrees/seer/sera-signal-panel/web/node_modules` (hardlink, never a symlink: a symlink passes vitest and tsc and then kills `next build`).

### Step 1: The view-model
**File:** `web/app/sera/signals/view.ts` (new)
**Change:** every decision about what the page says lives here, pure and tested; `page.tsx` only lays it out. Types are derived from `LabSnapshot['panel']` so the file depends on phase 2's field names only.
**Code:**
```ts
// Pure helpers for /sera/signals. No data access; page.tsx feeds lab.panel and the raw ?page value.
//
// Everything the owner reads on the page is written here, in plain words, so one test file can
// hold the page to its two rules: no id, digest or code ever reaches the text (CLAUDE.md
// Conventions), and the verdict is the engine's, never re-judged here. `clears` and `reasons` come
// from the engine's published verdict (lab/panel_verdict.py), which is computed at export time
// across every panel ever recorded; a page that recomputed it from the readings would disagree
// with `lab panel-map` the moment the correction moved.
import type { LabSnapshot } from '../../../lib/sera/types';

type Panel = LabSnapshot['panel'];
export type PanelSignal = Panel['signals'][number];
type StoreReading = NonNullable<PanelSignal['dev']>;
type Era = NonNullable<StoreReading['all']>;

/**
 * Rows per page. The panel can hold 1,500+ rows once Sera replays every recorded stock-signal
 * method, and /sera already renders about 4 MB of HTML (features/sera.md); fifty rows keep this
 * page a few tens of kilobytes whatever the panel grows to.
 */
export const PAGE_SIZE = 50;

const INTRO =
  'Every stock-picking idea the lab has tried, measured by one question before any portfolio is ' +
  'built: did the stocks it ranked highest beat the rest over the next month?';

/** Shown in place of the ranking when the snapshot holds no panel rows. */
export const EMPTY_TEXT =
  'The map fills in the first time Sera runs the stock-picking strategies it has already tested ' +
  'through this check, and gains a row for every new idea after that.';

/** Shown above the ranking when rows exist and none passed: the finding, not a gap. */
export const FINDING_TEXT =
  'Not one idea passed. Each one either did no better than luck would, given how many ideas were ' +
  'tried, or stopped working after 2009, or lost its edge once the companies that later failed ' +
  'were put back. That is the finding: none of these ways of picking stocks is worth building a ' +
  'portfolio on.';

const CONTROLS = 'Allowing for recent winners, company size, market swings and how jumpy a stock is';

export type SignalRowView = {
  /** React key only. Never rendered. */
  key: string;
  /** 1-based place in the whole ranking, not in the page. */
  rank: number;
  name: string;
  clears: boolean;
  verdict: string;
  /** The engine's reasons, as given, when it did not pass; empty when it passed. */
  why: string[];
  readings: string;
  controlled: string | null;
  origin: string;
  twin: string | null;
};

export type SignalMap = {
  lede: string;
  total: number;
  cleared: number;
  replays: number;
  twins: number;
  finding: string | null;
  page: number;
  pages: number;
  rows: SignalRowView[];
};

const count = (n: number): string => n.toLocaleString('en-US');

const slopeOf = (sig: PanelSignal): number | null => {
  const v = sig.dev?.all?.slope;
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
};

/**
 * Best first by the dev whole-window controlled slope, the order `lab panel-map` prints (R2.3).
 * A row with no slope sorts last; ties go by name, then id, so the order never depends on the
 * snapshot's own row order.
 */
export function rankSignals(signals: readonly PanelSignal[]): PanelSignal[] {
  return [...signals].sort((a, b) => {
    const x = slopeOf(a);
    const y = slopeOf(b);
    if (x !== y) {
      if (x === null) return 1;
      if (y === null) return -1;
      return y - x;
    }
    const byName = a.name.localeCompare(b.name, 'en');
    return byName !== 0 ? byName : a.id.localeCompare(b.id, 'en', { numeric: true });
  });
}

/**
 * The name each row is shown under. Replays of one method's several variants can share the
 * method's name; those get "(variant k of n)" in id order, so two rows with different results
 * never read as the same idea and a twin line can say which one it means — without printing the
 * id that tells them apart.
 */
export function displayNames(signals: readonly PanelSignal[]): Map<string, string> {
  const byName = new Map<string, PanelSignal[]>();
  for (const sig of signals) {
    const list = byName.get(sig.name) ?? [];
    list.push(sig);
    byName.set(sig.name, list);
  }
  const out = new Map<string, string>();
  for (const [name, list] of byName) {
    if (list.length === 1) {
      out.set(list[0].id, name);
      continue;
    }
    const ordered = [...list].sort((a, b) => a.id.localeCompare(b.id, 'en', { numeric: true }));
    ordered.forEach((sig, i) => out.set(sig.id, `${name} (variant ${i + 1} of ${ordered.length})`));
  }
  return out;
}

type Compare = { verb: 'beat' | 'trailed' | 'matched'; by: string };

/** A yearly spread as a verb and an amount; null when there is no reading. */
function compare(spread: number | null | undefined): Compare | null {
  if (typeof spread !== 'number' || !Number.isFinite(spread)) return null;
  if (Math.abs(spread) < 0.0005) return { verb: 'matched', by: '' };
  return { verb: spread > 0 ? 'beat' : 'trailed', by: ` by ${(Math.abs(spread) * 100).toFixed(1)}%` };
}

const spreadOf = (era: Era | null | undefined): number | null =>
  era && typeof era.spread === 'number' ? era.spread : null;

/**
 * The three readings the panel bar is built on, as one sentence: the whole dev window, 2009-2015
 * alone, and the survivorship store (the dead companies put back).
 */
//
// A store that is null was never measured; an era that is null on a measured store had fewer than
// twelve measured months (phase 1 leaves it out), which the page says as "not enough months to say".
export function readings(sig: PanelSignal): string {
  const all = compare(spreadOf(sig.dev?.all));
  const recent = compare(spreadOf(sig.dev?.recent));
  const dead = compare(spreadOf(sig.survivorship?.all));
  const first = all
    ? `Its top picks ${all.verb} the average stock it could have picked${all.by}${all.by ? ' a year' : ''}`
    : sig.dev
      ? 'Over the whole period there are not enough months to say how its top picks did'
      : 'Its top picks have not been measured yet';
  const second = recent
    ? `since 2009 they ${recent.verb} it${recent.by}`
    : sig.dev
      ? 'since 2009 there are not enough months to say'
      : 'since 2009 it has not been measured yet';
  const third = dead
    ? `with the companies that later failed put back, they ${dead.verb} it${dead.by}`
    : sig.survivorship
      ? 'with the companies that later failed put back, there are not enough months to say'
      : 'with the companies that later failed put back, it has not been measured yet';
  return `${first}; ${second}; ${third}.`;
}

/**
 * The controlled slope, by its sign only: its size is in units the owner has no use for. The slope
 * is a MONTHLY figure (phase 1) while `spread` is yearly; if a yearly slope is ever printed it is
 * `slope * 12`, and the two are never printed as one unit.
 */
export function controlled(sig: PanelSignal): string | null {
  const slope = slopeOf(sig);
  if (slope === null) return null;
  return slope > 0
    ? `${CONTROLS}, the stocks it ranked higher still did better.`
    : `${CONTROLS}, the stocks it ranked higher did no better.`;
}

/** `?page=` as a page number in 1..pages; anything else is page 1, anything past the end the last page. */
export function parsePage(raw: string | string[] | undefined, pages: number): number {
  const v = Array.isArray(raw) ? raw[0] : raw;
  const n = Number(v);
  if (!Number.isInteger(n) || n < 1) return 1;
  return Math.min(n, Math.max(1, pages));
}

export const pageHref = (page: number): string => (page <= 1 ? '/sera/signals' : `/sera/signals?page=${page}`);

function rowView(sig: PanelSignal, rank: number, names: Map<string, string>): SignalRowView {
  return {
    key: sig.id,
    rank,
    name: names.get(sig.id) ?? sig.name,
    clears: sig.clears,
    verdict: sig.clears ? 'Passed the screen' : 'Did not pass',
    why: sig.clears ? [] : [...sig.reasons],
    readings: readings(sig),
    controlled: controlled(sig),
    origin: sig.kind === 'replay' ? 'From a strategy already tested' : 'Tested as a signal first',
    twin: sig.twinOf ? `The same picks as ${names.get(sig.twinOf) ?? 'an earlier idea'}` : null,
  };
}

/** Everything /sera/signals renders for one page of the ranking. */
export function signalMap(panel: Panel, rawPage: string | string[] | undefined): SignalMap {
  const signals = panel.signals;
  const total = signals.length;
  const cleared = signals.filter(sig => sig.clears).length;
  const replays = signals.filter(sig => sig.kind === 'replay').length;
  const twins = signals.filter(sig => sig.twinOf !== null).length;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const page = parsePage(rawPage, pages);
  const names = displayNames(signals);
  const first = (page - 1) * PAGE_SIZE;
  const rows = rankSignals(signals)
    .slice(first, first + PAGE_SIZE)
    .map((sig, i) => rowView(sig, first + i + 1, names));
  const tally =
    total === 0
      ? 'No idea has been measured yet.'
      : `${count(total)} ${total === 1 ? 'idea' : 'ideas'} measured; ${cleared === 0 ? 'none' : count(cleared)} passed.`;
  return {
    lede: `${INTRO} ${tally}`,
    total,
    cleared,
    replays,
    twins,
    finding: total > 0 && cleared === 0 ? FINDING_TEXT : null,
    page,
    pages,
    rows,
  };
}
```
**Impact:** new file; nothing imports it but `page.tsx` and its test.

### Step 2: The view-model's tests
**File:** `web/app/sera/signals/view.test.ts` (new)
**Change:** behaviour tests on fixture panels (the committed snapshot is empty until the first replay, so fixtures are the only way the ranked states are exercised in CI), plus one pin on the committed snapshot that encodes the no-ids rule structurally: the day the snapshot publishes a reason with a method id, a digest or code in it, `npm test` fails (reasons only: a replay's name is its method's own name, Decisions). The builders are local to this file (the `fixture.ts` pattern, without touching phase 2's file).
**Code:**
```ts
import { describe, expect, it } from 'vitest';
import { lab } from '../../../lib/sera/lab';
import type { LabSnapshot } from '../../../lib/sera/types';
import {
  EMPTY_TEXT, FINDING_TEXT, PAGE_SIZE, controlled, displayNames, pageHref, parsePage, rankSignals, readings,
  signalMap, type PanelSignal, type SignalMap,
} from './view';

type Panel = LabSnapshot['panel'];
type Era = NonNullable<NonNullable<PanelSignal['dev']>['all']>;

/** Text that must never reach the owner: a method or signal id, a digest, or code punctuation. */
const NOT_PLAIN = /\b[MS]\d{4}\b|\b[0-9a-f]{12,}\b|[_`{}<>]|=>/;

const era = (over: Partial<Era> = {}): Era => ({
  months: 120, ic: 0.01, icT: 1.2, spread: 0.02, spreadT: 1.5, slope: 0.001, slopeT: 1.1, turnover: 0.3, ...over,
});

function sig(over: Partial<PanelSignal> = {}): PanelSignal {
  return {
    id: 'S0001',
    kind: 'signal',
    name: 'Twelve-month winners, skipping the last month',
    family: 'stock-momentum',
    methodId: null,
    clears: false,
    q: 0.4,
    reasons: ['Its lead could be luck, given how many ideas were tried'],
    twinOf: null,
    dev: { all: era({ spread: 0.021 }), pre2009: era(), recent: era({ spread: 0.004 }) },
    survivorship: { all: era({ spread: 0.018 }), pre2009: era(), recent: era() },
    ...over,
  };
}

const panel = (signals: PanelSignal[]): Panel => ({ rule: 'panel-v1', fdr: 0.1, signals });

/** Every string signalMap hands the page. */
function ownerText(map: SignalMap): string[] {
  return [
    map.lede,
    ...(map.finding ? [map.finding] : []),
    ...map.rows.flatMap(r => [r.name, r.verdict, ...r.why, r.readings, r.controlled ?? '', r.origin, r.twin ?? '']),
  ];
}

describe('signalMap on an empty panel (R6.3)', () => {
  const map = signalMap(panel([]), undefined);
  it('says nothing has been measured, with no rows and no finding', () => {
    expect(map.total).toBe(0);
    expect(map.rows).toEqual([]);
    expect(map.finding).toBeNull();
    expect(map.pages).toBe(1);
    expect(map.page).toBe(1);
    expect(map.lede.endsWith('No idea has been measured yet.')).toBe(true);
  });
  it('has an empty-state sentence that names no id', () => {
    expect(EMPTY_TEXT).not.toMatch(NOT_PLAIN);
  });
});

describe('signalMap headline', () => {
  it('counts ideas and passes, and reads "none" when nothing passed', () => {
    const map = signalMap(panel([sig(), sig({ id: 'S0002', name: 'Cheap on earnings' })]), undefined);
    expect(map.lede.endsWith('2 ideas measured; none passed.')).toBe(true);
    expect(map.finding).toBe(FINDING_TEXT);
  });
  it('drops the finding once one idea passes', () => {
    const map = signalMap(panel([sig({ clears: true, reasons: [] }), sig({ id: 'S0002', name: 'Cheap' })]), undefined);
    expect(map.lede.endsWith('2 ideas measured; 1 passed.')).toBe(true);
    expect(map.finding).toBeNull();
    expect(map.cleared).toBe(1);
  });
  it('formats large counts with separators', () => {
    const many = Array.from({ length: 1500 }, (_, i) => sig({ id: `S${String(i + 1).padStart(4, '0')}`, name: `Idea ${i}` }));
    expect(signalMap(panel(many), undefined).lede.endsWith('1,500 ideas measured; none passed.')).toBe(true);
  });
});

describe('rankSignals', () => {
  it('orders by the controlled slope, best first, with no slope last and ties by name', () => {
    const ranked = rankSignals([
      sig({ id: 'S0001', name: 'B', dev: { all: era({ slope: 0.001 }), pre2009: era(), recent: era() } }),
      sig({ id: 'S0002', name: 'A', dev: { all: era({ slope: 0.003 }), pre2009: era(), recent: era() } }),
      sig({ id: 'S0003', name: 'C', dev: { all: era({ slope: Number.NaN }), pre2009: era(), recent: era() } }),
      sig({ id: 'S0004', name: 'A2', dev: { all: era({ slope: 0.001 }), pre2009: era(), recent: era() } }),
    ]);
    expect(ranked.map(s => s.id)).toEqual(['S0002', 'S0004', 'S0001', 'S0003']);
  });
});

describe('row wording (R6.2)', () => {
  it('says the three readings in words, with their meaning', () => {
    expect(readings(sig())).toBe(
      'Its top picks beat the average stock it could have picked by 2.1% a year; since 2009 they beat it by 0.4%; ' +
        'with the companies that later failed put back, they beat it by 1.8%.',
    );
  });
  it('says trailed for a negative spread and matched for a zero one', () => {
    const s = sig({
      dev: { all: era({ spread: -0.012 }), pre2009: era(), recent: era({ spread: 0.0001 }) },
      survivorship: null,
    });
    expect(readings(s)).toBe(
      'Its top picks trailed the average stock it could have picked by 1.2% a year; since 2009 they matched it; ' +
        'with the companies that later failed put back, it has not been measured yet.',
    );
  });
  it('says "not enough months to say" for an era left out of a measured store', () => {
    const s = sig({
      dev: { all: era({ spread: 0.021 }), pre2009: era(), recent: null },
      survivorship: { all: null, pre2009: null, recent: null },
    });
    expect(readings(s)).toBe(
      'Its top picks beat the average stock it could have picked by 2.1% a year; since 2009 there are not enough months to say; ' +
        'with the companies that later failed put back, there are not enough months to say.',
    );
  });
  it('says the controlled slope by its sign only', () => {
    expect(controlled(sig({ dev: { all: era({ slope: 0.002 }), pre2009: era(), recent: era() } }))).toMatch(/still did better\.$/);
    expect(controlled(sig({ dev: { all: era({ slope: -0.002 }), pre2009: era(), recent: era() } }))).toMatch(/did no better\.$/);
  });
  it('gives the verdict in words, with the engine reasons only when it did not pass', () => {
    const [pass, miss] = signalMap(
      panel([
        sig({ id: 'S0001', clears: true, reasons: [], dev: { all: era({ slope: 0.01 }), pre2009: era(), recent: era() } }),
        sig({ id: 'S0002', name: 'Cheap on earnings', reasons: ['It stopped working after 2009'] }),
      ]),
      undefined,
    ).rows;
    expect([pass.verdict, pass.why]).toEqual(['Passed the screen', []]);
    expect([miss.verdict, miss.why]).toEqual(['Did not pass', ['It stopped working after 2009']]);
  });
  it('tells replays from new signals in words', () => {
    const rows = signalMap(
      panel([sig(), sig({ id: 'M0614-V1', kind: 'replay', methodId: 'M0614', name: 'Quiet stocks near their high' })]),
      undefined,
    ).rows;
    expect(rows.map(r => r.origin).sort()).toEqual(['From a strategy already tested', 'Tested as a signal first']);
  });
  it('names a twin by the name of the row it repeats, never its id', () => {
    const rows = signalMap(
      panel([
        sig({ id: 'M0614-V1', kind: 'replay', methodId: 'M0614', name: 'Quiet stocks near their high' }),
        sig({ id: 'M0614-V2', kind: 'replay', methodId: 'M0614', name: 'Quiet stocks near their high', twinOf: 'M0614-V1' }),
        sig({ id: 'S0009', name: 'Orphan', twinOf: 'S9999' }),
      ]),
      undefined,
    ).rows;
    const byName = new Map(rows.map(r => [r.name, r]));
    expect(byName.get('Quiet stocks near their high (variant 2 of 2)')?.twin).toBe(
      'The same picks as Quiet stocks near their high (variant 1 of 2)',
    );
    expect(byName.get('Quiet stocks near their high (variant 1 of 2)')?.twin).toBeNull();
    expect(byName.get('Orphan')?.twin).toBe('The same picks as an earlier idea');
  });
  it('suffixes only names that collide', () => {
    const names = displayNames([sig({ id: 'S0001', name: 'A' }), sig({ id: 'S0002', name: 'B' })]);
    expect([...names.values()]).toEqual(['A', 'B']);
  });
  it('never puts an id, a digest or code in front of the owner', () => {
    const map = signalMap(
      panel([
        sig({ id: 'S0001', clears: true, reasons: [] }),
        sig({ id: 'M0614-V1', kind: 'replay', methodId: 'M0614', name: 'Quiet stocks near their high', survivorship: null }),
        sig({ id: 'M0614-V2', kind: 'replay', methodId: 'M0614', name: 'Quiet stocks near their high', twinOf: 'M0614-V1' }),
        sig({ id: 'S0003', name: 'Orphan', twinOf: 'S9999' }),
      ]),
      undefined,
    );
    for (const text of ownerText(map)) expect(text).not.toMatch(NOT_PLAIN);
  });
});

describe('pagination', () => {
  const many = Array.from({ length: 120 }, (_, i) =>
    sig({
      id: `S${String(i + 1).padStart(4, '0')}`,
      name: `Idea ${String(i + 1).padStart(3, '0')}`,
      dev: { all: era({ slope: 1 - i / 1000 }), pre2009: era(), recent: era() },
    }),
  );
  it('serves PAGE_SIZE rows a page, ranked across the whole list', () => {
    const p1 = signalMap(panel(many), undefined);
    const p3 = signalMap(panel(many), '3');
    expect(PAGE_SIZE).toBe(50);
    expect([p1.pages, p1.rows.length, p1.rows[0].rank, p1.rows[0].name]).toEqual([3, 50, 1, 'Idea 001']);
    expect([p3.page, p3.rows.length, p3.rows[0].rank, p3.rows[19].rank]).toEqual([3, 20, 101, 120]);
  });
  it('reads garbage as page 1 and a page past the end as the last page', () => {
    expect(parsePage(undefined, 3)).toBe(1);
    expect(parsePage('abc', 3)).toBe(1);
    expect(parsePage('0', 3)).toBe(1);
    expect(parsePage('2.5', 3)).toBe(1);
    expect(parsePage(['2', '3'], 3)).toBe(2);
    expect(parsePage('99', 3)).toBe(3);
    expect(parsePage('5', 1)).toBe(1);
  });
  it('links page 1 without a query', () => {
    expect([pageHref(1), pageHref(2)]).toEqual(['/sera/signals', '/sera/signals?page=2']);
  });
});

describe('the committed snapshot', () => {
  // Reasons only (Decisions): a replay's name is its method's own name, owner-facing already on
  // /sera/methods, and a method name may legitimately mention another method. The fixture tests
  // above still hold every name, verdict and line the page prints to the no-ids rule.
  it('publishes owner-readable reasons for every panel row', () => {
    for (const s of lab.panel.signals) {
      for (const text of s.reasons) {
        expect([s.id, text, NOT_PLAIN.test(text)]).toEqual([s.id, text, false]);
      }
    }
  });
  it('renders without throwing on whatever it holds', () => {
    const map = signalMap(lab.panel, undefined);
    expect(map.total).toBe(lab.panel.signals.length);
    expect(map.rows.length).toBe(Math.min(PAGE_SIZE, map.total));
  });
});
```
**Impact:** `npm test` gains one file. On the committed (empty) snapshot the last block passes vacuously; it starts guarding the day Sera's replay commits panel rows.

### Step 3: The page
**File:** `web/app/sera/signals/page.tsx` (new)
**Change:** a server component, the `/sera/methods` shape: await `searchParams`, build the map, `requireSera` with the page's own href, render. One presentation of the rows at every width (a list, not a desktop table plus phone cards), so each page's HTML carries each row once. Buttons: only the pager's two links, icon-only with `aria-label` and `data-tip`.
**Code:**
```tsx
import { Check, ChevronLeft, ChevronRight, X } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { requireSera } from '@/lib/sera/gate';
import { lab } from '@/lib/sera/lab';
import { EMPTY_TEXT, pageHref, signalMap, type SignalRowView } from './view';
import s from './signals.module.css';

// The layout's title template renders this as "Signal map · Sera".
export const metadata: Metadata = { title: 'Signal map' };

type Search = { page?: string | string[] };

/**
 * The signal map: every stock-picking idea the panel has measured, ranked, in plain words.
 *
 * Paged by `?page=` rather than collapsed: a <details> remainder would still put every row in the
 * HTML, and the panel is expected to hold 1,500+ rows once Sera replays the recorded methods.
 */
export default async function SignalsPage({ searchParams }: { searchParams: Promise<Search> }) {
  const q = await searchParams;
  const map = signalMap(lab.panel, q.page);
  await requireSera(pageHref(map.page));

  return (
    <>
      <PageHeader eyebrow="Signals" title="The signal map" lede={map.lede} asOf={lab.asOf} />
      <div className={s.page}>
        {map.total === 0 ? (
          <Section eyebrow="Signal map" title="Nothing measured yet">
            <p className={s.empty}>{EMPTY_TEXT}</p>
          </Section>
        ) : (
          <>
            <div className={s.tally}>
              <span className="chip"><span className="num">{map.total.toLocaleString('en-US')}</span>&nbsp;measured</span>
              <span className="chip"><span className="num">{map.cleared.toLocaleString('en-US')}</span>&nbsp;passed</span>
              <span className="chip"><span className="num">{map.replays.toLocaleString('en-US')}</span>&nbsp;from strategies already tested</span>
              <span className="chip"><span className="num">{map.twins.toLocaleString('en-US')}</span>&nbsp;repeat another idea’s picks</span>
            </div>

            {map.finding && (
              <Section bg="butter" eyebrow="The finding" title="Not one idea passed">
                <p className={s.finding}>{map.finding}</p>
              </Section>
            )}

            <Section
              eyebrow={`Ranking · page ${map.page} of ${map.pages}`}
              title="Every idea, best first"
              caption="Ranked by how much better the stocks each idea ranked higher did, once the usual explanations are allowed for. To pass, an idea has to beat luck given how many ideas were tried, still work after 2009, and keep its edge with the companies that later failed put back."
            >
              <ol className={s.rows}>
                {map.rows.map(r => <SignalRow key={r.key} r={r} />)}
              </ol>
              <Pager page={map.page} pages={map.pages} />
            </Section>
          </>
        )}
      </div>
    </>
  );
}

function SignalRow({ r }: { r: SignalRowView }) {
  return (
    <li className={s.row}>
      <span className={`num ${s.rank}`}>{r.rank}</span>
      <div className={s.main}>
        <div className={s.head}>
          <h3 className={s.name}>{r.name}</h3>
          <span className={`chip ${s.verdict} ${r.clears ? s.pass : s.miss}`}>
            {r.clears
              ? <Check size={15} strokeWidth={2} aria-hidden="true" />
              : <X size={15} strokeWidth={2} aria-hidden="true" />}
            {r.verdict}
          </span>
        </div>
        <p className={s.text}>{r.readings}</p>
        {r.controlled && <p className={s.sub}>{r.controlled}</p>}
        {r.why.length > 0 && (
          <ul className={s.why}>
            {r.why.map(w => <li key={w}>{w}</li>)}
          </ul>
        )}
        <div className={s.chips}>
          <span className="chip">{r.origin}</span>
          {r.twin && <span className="chip">{r.twin}</span>}
        </div>
      </div>
    </li>
  );
}

function Pager({ page, pages }: { page: number; pages: number }) {
  if (pages <= 1) return null;
  return (
    <nav className={s.pager} aria-label="Pages of the ranking">
      <span className="num">Page {page} of {pages}</span>
      {page > 1 && (
        <Link href={pageHref(page - 1)} className="icon-btn sm" aria-label="Previous page" data-tip="Previous page">
          <ChevronLeft size={18} strokeWidth={1.5} />
        </Link>
      )}
      {page < pages && (
        <Link href={pageHref(page + 1)} className="icon-btn sm" aria-label="Next page" data-tip="Next page">
          <ChevronRight size={18} strokeWidth={1.5} />
        </Link>
      )}
    </nav>
  );
}
```
**Impact:** new route. Nothing else links to it until Step 5.

### Step 4: The page's styles
**File:** `web/app/sera/signals/signals.module.css` (new)
**Change:** one layout at every width; chips are allowed to wrap (the `ideas.module.css` lesson: a nowrap chip holds a 390 px page wider than the viewport).
**Code:**
```css
/* The signal map: tally chips, the finding, then one ranked list, read the same way at 390 and 1280.
   One presentation, not a desktop table plus phone cards, so each page's HTML carries each row once. */
.page { display: flex; flex-direction: column; gap: 12px; }
.tally { display: flex; flex-wrap: wrap; gap: 8px; padding: 4px 0 2px; }
.tally :global(.chip) { background: var(--sheet); }

.finding { margin: 0; font-size: 17px; line-height: 1.5; max-width: 72ch; }
.empty { margin: 0; font-size: 16px; line-height: 1.5; color: var(--ink-2); max-width: 72ch; }

.rows { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.row {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr);
  gap: 16px;
  padding: 18px 0;
  border-bottom: 1px solid var(--hair);
}
.row:last-child { border-bottom: 0; }
.rank { font-size: 22px; line-height: 1.3; color: var(--ink-3); text-align: right; }
.main { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.head { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.name { margin: 0; font-size: 19px; font-weight: 500; line-height: 1.3; overflow-wrap: anywhere; }
.text { margin: 0; font-size: 15.5px; line-height: 1.5; }
.sub { margin: 0; font-size: 14.5px; line-height: 1.45; color: var(--ink-2); }
.why { margin: 0; padding-left: 18px; font-size: 14.5px; line-height: 1.45; color: var(--ink-2); }

/* Chips here hold sentences ("The same picks as …"), so they wrap: a 30 px floor, not a fixed
   30 px pill, and `white-space: normal` over globals.css's nowrap. Two classes deep so the rule
   wins over the global `.chip` whatever order the stylesheets load in. */
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chips :global(.chip), .head .verdict {
  white-space: normal;
  height: auto;
  min-height: 30px;
  padding: 5px 14px;
  line-height: 1.3;
  font-size: 14px;
}
.chips :global(.chip) { background: var(--stone); }
.head .verdict { display: inline-flex; align-items: center; gap: 6px; background: var(--sheet); }
.head .pass { color: var(--pos); }
.head .miss { color: var(--ink-2); }

.pager { display: flex; align-items: center; justify-content: flex-end; gap: 12px; padding-top: 12px; font-size: 14px; color: var(--ink-2); }

@media (max-width: 1023.98px) {
  .row { grid-template-columns: 34px minmax(0, 1fr); gap: 10px; }
  .rank { font-size: 17px; }
  .name { font-size: 17px; }
}
```
**Impact:** none outside the page.

### Step 5: The seventh tab
**File:** `web/components/sera/SeraNav.tsx:3`, `:8-15`, `:32-36`, `:71`, `:95`
**Change:** add the tab after Methods (the map sits between the ideas and the books built from them) and keep the comments true.

Line 3 becomes:
```tsx
import { Ban, Eye, FlaskConical, LayoutDashboard, Lightbulb, NotebookPen, Radar, Workflow } from 'lucide-react';
```
Lines 8-15 (`const TABS = [...]`) become:
```tsx
const TABS = [
  { href: '/sera', icon: LayoutDashboard, tip: 'Overview' },
  { href: '/sera/methods', icon: FlaskConical, tip: 'Methods' },
  { href: '/sera/signals', icon: Radar, tip: 'Signal map' },
  { href: '/sera/journal', icon: NotebookPen, tip: 'Journal' },
  { href: '/sera/ideas', icon: Lightbulb, tip: 'Ideas' },
  { href: '/sera/gotrade', icon: Ban, tip: 'Not on Gotrade' },
  { href: '/sera/how', icon: Workflow, tip: 'How it works' },
];
```
Lines 32-36 (the paragraph starting "The phone bar carries the six section tabs") become:
```tsx
 * The phone bar carries the seven section tabs and nothing else. It has no wordmark because Seer's
 * bar has none either and because PageHeader already prints "Sera · the method lab" as the eyebrow
 * at the top of every page; dropping it is what leaves room for all seven tabs (7 × 48 + 6 × 2 gap
 * + 2 × 8 padding = 364 px, which clears the 390 px floor with 13 px of gutter either side). The
 * seventh tab, the signal map, cost the bar's tabs 4 px of width each; their height stays the
 * rail's 52 px. The way back to Seer moved out of the bar for the same reason and
```
(the following line, "now sits beside sign-out in PageHeader — see SeraBackLink below.", is unchanged.)

Line 71: `* The six tabs themselves, rendered into …` -> `* The seven tabs themselves, rendered into …` (rest of the sentence unchanged).
Line 95: `* The way back to Seer on a phone. The bar below 1024 px is six section tabs and no more, so this` -> `* The way back to Seer on a phone. The bar below 1024 px is seven section tabs and no more, so this`.
**Impact:** every Sera page gains the tab, in the rail and the phone bar (one `Tabs` definition renders both).

### Step 6: The phone bar fits seven
**File:** `web/components/sera/SeraNav.module.css:30-55` and `:57-58`
**Change:** 7 × 52 + 6 × 4 + 16 = 404 px would overflow a 390 px phone. Narrow the bar's tracks to 48 px with a 2 px gap: 364 px. The rail is untouched.

Replace lines 30-55 (from the comment `/* Sera's phone navigation: …` through the `.barTabs { … }` rule) with:
```css
/* Sera's phone navigation: Seer's own floating pill (Nav.module.css .bar), at Seer's own height.
   Sera has seven sections where Seer has four, so the width and the tracks differ:
   7 x 48 tab + 6 x 2 gap + 2 x 8 padding = 364 px, which fits the 390 px floor with 13 px of
   gutter each side and 414 with 25 px. At the rail's 52 px and 4 px gap seven tabs would need
   404 px and overflow a phone; the seventh tab (the signal map) is paid for by 4 px of each tab's
   width, never its 52 px height. There is no wordmark and no back button in here on purpose
   -- that is what leaves room for seven (SeraNav.tsx). */
.bar {
  position: fixed;
  left: 50%;
  bottom: max(11px, calc((var(--safe-bottom) - 4px) * 0.7));
  transform: translateX(-50%);
  width: 364px;
  height: 68px;
  border-radius: 999px;
  background: var(--bar);
  padding: 8px;
  z-index: 50;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.18);
}

.barTabs {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
  height: 100%;
}

/* In the bar a tab takes its 48 px track; the rail's 52 px floor (.tab below) would push the
   seventh tab out of the pill. */
.barTabs > .tab, .barTabs > .active { min-width: 0; }
```
Lines 57-58 (the comment above `.tab, .active`):
```css
/* One tab, whichever pill holds it: 52 px wide in the rail, its 48 px track in .barTabs, 52 px tall
   in both, so the bar and the rail show the same button at nearly the same size. */
```
**Impact:** the phone bar is 16 px wider and each tab 4 px narrower; the Journal badge (`top: -2px; right: -2px`) is unchanged.

### Step 7: PageHeader's comment
**File:** `web/components/sera/PageHeader.tsx:31`
**Change:** comment only. `joins sign-out in the aside because the six-tab bar has no room for it (SeraBackLink renders` -> `joins sign-out in the aside because the seven-tab bar has no room for it (SeraBackLink renders`.
**Impact:** none at runtime.

### Step 8: The feature map
**File:** `.claude/skills/verify-seer/features/sera.md`
**Change:** four edits.

1. In `## Sub-features`, replace the first bullet with:
```markdown
- Overview, Methods, one method's page (`/sera/methods/MNNNN`: The idea, What could go wrong, variants, verdict), Signal map, Journal, Ideas, Not on Gotrade, How it works.
- Signal map (`/sera/signals`): every stock-picking idea the signal panel has measured, ranked best first by its controlled reading, 50 a page (`?page=N`). Each row is named by what it ranks on and says, in words, whether it passed, the engine's reasons when it did not, its three readings (whole window, since 2009, with the dead companies back), whether it repeats another row's picks (by name), and whether it came from a strategy already tested or was tested as a signal first. No id, digest or code appears. With no panel rows it shows "Nothing measured yet"; with rows and no pass, a "Not one idea passed" finding above the ranking.
```
2. Replace the `## How to get to it (user POV)` body with:
```markdown
The telescope icon at the bottom of the rail ("Sera, the method lab"). Sera has its own rail and a "Back to Seer" link. The signal map is the radar icon ("Signal map"), third in the rail and third in the phone bar.
```
3. In the `## Driving it with verify.sh` block, after the `GET /sera/how` line, add:
```sh
$V api RUN GET /sera/signals               # "The signal map", "No idea has been measured yet.", "Nothing measured yet" (committed lab: no panel rows until Sera's first replay)
$V api RUN GET '/sera/signals?page=2'      # with fixture rows (see Gotchas): "Page 2 of 2", "[Previous page]"
```
4. Append to `## Gotchas`:
```markdown
- `/sera/signals` reads `panel.signals` from the committed `lab.json`, which is empty until the post-merge `lab panel-replay` runs on `main`, so it shows its empty state. To see the ranked map, overwrite `panel` in the run's own web snapshot (`~/.local/state/seer-verify/<RUN>/web/data/lab.json`) with fixture rows, as the sera-signal-panel phase-6 Proof does, then GET the page again: `next dev` recompiles on the change. Never write fixture rows into the checkout's `web/data/lab.json`; the snapshot test byte-compares it against `lab/lab.sqlite`.
- Sera's phone bar holds seven tabs at 48 px wide (364 px). An eighth would not fit 390 px without another trade.
```
**Impact:** documentation only.

## Principles applied

- Laziness protocol: no glossary entry (it would also force edits to `glossary.test.ts`'s key list and `GLOSSARY_ORDER`, which the How page renders); every term is said in words instead. No shared `fixture.ts` builder: the two builders live in `view.test.ts`, so this phase touches no file phase 2 owns.
- Boundary discipline: `?page=` is parsed once, in `parsePage` (garbage -> 1, past the end -> last page); the rest of the page trusts the number.
- Encode lessons in structure: the "no ids or code in owner text" rule (CLAUDE.md Conventions, invariant 10) is a test, not a sentence: `view.test.ts` checks the view-model's output on fixtures and pins every `reason` in the committed snapshot (not `name`: a replay's name is its method's own `methods.name`, Decisions), so a reason that carries a method id fails `npm test`.
- Test behaviour, not implementation: tests assert the sentences and ranks the page prints and the page boundaries, not how `signalMap` builds them.
- Prove it works: Proof drives the real page through verify-seer, empty on the committed snapshot and ranked on fixture rows written into the run's own web snapshot, with screenshots at 390 and 1280 in both themes.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/sera-signal-panel/web && (test -d node_modules || cp -al /home/miftah/seer/web/node_modules node_modules) && npx tsc --noEmit`
**Tests:** `cd /home/miftah/.worktrees/seer/sera-signal-panel/web && npx vitest run app/sera/signals/view.test.ts && npm test`
**Proof:** the real `/sera/signals` page, signed in, renders its empty state on the committed snapshot and the ranked map on fixture rows, with no id in its text.
- Harness: `.claude/skills/verify-seer` (`V=.claude/skills/verify-seer/scripts/verify.sh`, run from `/home/miftah/.worktrees/seer/sera-signal-panel`; needs `web/node_modules` hardlinked as in Build)
- Feature-map entries: `features/sera.md`
- Fixture decision: the page statically imports `web/data/lab.json`, and the committed snapshot holds no panel rows. The ranked states are shot by overwriting `panel` in the **run's own web snapshot** (`$VERIFY_HOME/<RUN>/web/data/lab.json`, a copy `verify.sh up` makes), never in the checkout, so nothing needs restoring and `git status` stays clean. The view-model's states are also covered by vitest on fixtures (Step 2).
- Setup, shared by the journeys (run once, in this order):
  ```sh
  cd /home/miftah/.worktrees/seer/sera-signal-panel
  V=.claude/skills/verify-seer/scripts/verify.sh
  RUN=$($V up | sed -n 's/^RUN=//p'); echo "$RUN"
  $V doctor "$RUN"
  ```
- Journeys:
  - **J1** · traces R6.3 — on the committed snapshot (before any fixture write): `jq -c '.panel.signals | length' "$HOME/.local/state/seer-verify/$RUN/web/data/lab.json"; $V api "$RUN" GET /sera/signals; $V shoot "$RUN" --theme both --width 390 --width 1280 /sera/signals` → passes when `jq` prints `0`, the api text contains "The signal map", "No idea has been measured yet." and "Nothing measured yet" and "The map fills in the first time Sera runs", contains neither "Every idea, best first" nor "Page 1 of", and `shoot` exits 0 (no HTTP error, no console error, no horizontal scroll) with four PNGs that, read, show the empty-state sheet in both themes at both widths
  - **J2** · traces R6.2 — write 60 fixture rows into the run's web snapshot, then drive both pages:
    ```sh
    F=$(mktemp -d)/fill-panel.mjs
    cat >"$F" <<'EOF'
    import { readFileSync, writeFileSync } from 'node:fs';
    const file = process.argv[2];
    const snap = JSON.parse(readFileSync(file, 'utf8'));
    const era = (spread, slope) => ({ months: 120, ic: 0.01, icT: 1.1, spread, spreadT: 1.4, slope, slopeT: 1.2, turnover: 0.3 });
    const store = (a, r, slope) => ({ all: era(a, slope), pre2009: era(a, slope), recent: era(r, slope) });
    const signals = [
      { id: 'S0001', kind: 'signal', name: 'Twelve-month winners, skipping the last month', family: 'stock-momentum',
        methodId: null, clears: true, q: 0.04, reasons: [], twinOf: null,
        dev: store(0.021, 0.004, 0.004), survivorship: store(0.018, 0.002, 0.003) },
      { id: 'M0614-V1', kind: 'replay', name: 'Quiet stocks near their high', family: 'stock-low-vol',
        methodId: 'M0614', clears: false, q: 0.6, reasons: ['Its lead could be luck, given how many ideas were tried'],
        twinOf: null, dev: store(0.011, -0.002, 0.002), survivorship: null },
      { id: 'M0614-V2', kind: 'replay', name: 'Quiet stocks near their high', family: 'stock-low-vol',
        methodId: 'M0614', clears: false, q: 0.6, reasons: ['Its lead could be luck, given how many ideas were tried'],
        twinOf: 'M0614-V1', dev: store(0.011, -0.002, 0.002), survivorship: null },
    ];
    for (let i = 0; i < 57; i++) {
      signals.push({ id: `S${String(100 + i).padStart(4, '0')}`, kind: 'signal', name: `Filler idea number ${i + 1}`,
        family: 'stock-filler', methodId: null, clears: false, q: 0.9, reasons: ['It stopped working after 2009'],
        twinOf: null, dev: store(-0.001 * i, -0.003, -0.0001 * (i + 1)), survivorship: store(-0.002, -0.002, -0.0001) });
    }
    snap.panel = { rule: 'panel-v1', fdr: 0.1, signals };
    writeFileSync(file, JSON.stringify(snap));
    EOF
    node "$F" "$HOME/.local/state/seer-verify/$RUN/web/data/lab.json"
    $V api "$RUN" GET /sera/signals
    $V api "$RUN" GET '/sera/signals?page=2'
    $V shoot "$RUN" --theme both --width 390 --width 1280 /sera/signals '/sera/signals?page=2'
    ```
    → passes when page 1's text contains "60 ideas measured; 1 passed.", "Twelve-month winners, skipping the last month" followed by "Passed the screen", "Its top picks beat the average stock it could have picked by 2.1% a year; since 2009 they beat it by 0.4%; with the companies that later failed put back, they beat it by 1.8%.", "Quiet stocks near their high (variant 1 of 2)", "The same picks as Quiet stocks near their high (variant 1 of 2)", "Did not pass", "Its lead could be luck, given how many ideas were tried", "From a strategy already tested", "Tested as a signal first", "it has not been measured yet", "Page 1 of 2" and "[Next page]", and does not contain "Not one idea passed"; page 2's text contains "Page 2 of 2", "[Previous page]" and "Filler idea number 57" and not "[Next page]"; `shoot` exits 0 with eight PNGs that, read, show ranked rows with wrapped chips inside the column at 390 in both themes. (If page 1 still shows "Nothing measured yet", `next dev` missed the file change: `touch "$HOME/.local/state/seer-verify/$RUN/web/app/sera/signals/page.tsx"` and GET again; if it still does, the journey fails.)
  - **J3** · traces R6.2 — after J2, on the same run: `for p in /sera/signals '/sera/signals?page=2'; do $V api "$RUN" GET "$p" | grep -cE '\b[MS][0-9]{4}\b|[0-9a-f]{12,}' ; done` → passes when both counts print `0` (the fixture holds `S0001`, `M0614-V1`, `M0614-V2` and `M0614` as ids and a `twinOf` id; none reaches the page text or an aria-label)
- Neighbor check (traces nothing): the nav change touches every Sera page. `$V api "$RUN" GET /sera; $V shoot "$RUN" --theme both --width 390 /sera /sera/ideas /sera/journal` → passes when the api text lists the seven tab labels `[Overview]`, `[Methods]`, `[Signal map]`, `[Journal…]`, `[Ideas]`, `[Not on Gotrade]`, `[How it works]`, `shoot` exits 0, and the 390 PNGs, read, show all seven tabs inside the floating bar with no tab clipped, in both themes. Then `$V down "$RUN"`.
- Cost: none (no `--llm`, no `--net`).
**Exit criteria:** `npx tsc --noEmit` and `npm test` pass; J1-J3 and the neighbor check pass on one verify run; `git status --short` lists only the eight files in **Files** (plus `web/node_modules`, which is git-ignored).

## Handoffs

- **Phase 2:** `reasons` must be owner-readable sentences (no ids, column names, symbols like `<=`, or code). `view.test.ts` pins this on the committed snapshot with `/\b[MS]\d{4}\b|\b[0-9a-f]{12,}\b|[_`{}<>]|=>/`; a reason like "dev slope <= 0" would fail `npm test`. If phase 2's `LabSnapshot['panel']` field names differ from the Shared contracts (for example `twinOf`, `survivorship`, `recent`, `spread`, `slope`), this phase's view-model and tests fail `tsc`; the reconciler aligns one side.
- **Phase 2 / Phase 4 (reconciled):** a replay row's `name` is its method's own `methods.name` (phase 4 no longer appends the rationale). Variants of one method share it and are told apart on the page as "(variant k of n)" in id order.
- **Phase 2:** if it adds a `panelSignal()` builder to `web/lib/sera/fixture.ts`, the reconciler may switch `view.test.ts`'s local `sig()`/`era()` to it; nothing else depends on the local builders.
- **Phase 3:** owns `.claude/skills/verify-seer/features/README.md`; if it rewrites the Sera row's summary, "signal map" belongs in the parentheses. This phase does not touch that file.
- Units: the page ranks signal rows (slope per 1 sd of score) and replay rows (slope on a pick dummy) on one scale, exactly as `lab panel-map` does (R2.3). If the reconciler decides the two must be ranked separately, the change is one `filter` in `signalMap` plus a second Section.

## Rollback

Revert this phase's commit: the route, its view-model, test and stylesheet go away, the nav returns to six tabs at 348 px, and the feature-map entry loses its signal-map lines. No data, snapshot or engine file changes.
