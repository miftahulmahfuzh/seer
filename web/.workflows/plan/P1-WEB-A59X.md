> Adopted from `.workflows/plan/LEADERBOARD_DESKTOP_REVAMP_PLAN.md` phase 1. Source: `.workflows/plan/leaderboard-desktop-revamp/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: Unique colour and icon per method

**Plan set:** `LEADERBOARD_DESKTOP_REVAMP_PLAN.md`
**Analysis:** `.workflows/analyze/20261110-090235-LB7D_code_analyzer.md`
**Satisfies:** R1, every method is unique in colour and in icon
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `web`

---

## Goal

After this phase no two strategies on the board share a card sheet, a chart line colour or an
icon, as long as there are at most twelve research strategies. A Claude twin now wears its
original's *partner* colour (F4 sky, F4+Claude teal) and draws its own icon (F4 gauge, F4+Claude
rocket). That icon is the same on the Leaderboard, Positions, History and Sean's plan. Every
original keeps the colour it has today, and adding a twin still moves no original's colour.

## Interface Contract

**Deletes:** nothing.
**Renames:** nothing.
**Creates:**
- CSS tokens in `web/app/globals.css`, light and dark: `--iris`, `--teal`, `--moss`, `--berry`,
  `--orchid`, `--amber`, each with a `--<name>-line`, plus the classes `.bg-iris`, `.bg-teal`,
  `.bg-moss`, `.bg-berry`, `.bg-orchid` and `.bg-amber`.
- `web/app/(app)/leaderboard/view.ts`: `PARTNER_BGS`, `SLOT_BGS`, `PALETTE_SIZE` (exported) and
  the private `Slot`, `slotAt` and `PARTNER`.
- `web/components/roster.ts`: `TWIN_ICON` (ReadonlyMap), `SPARE_ICONS`, `type IconIn`,
  `displayIcons(roster)`, `withDisplayIcons(roster)`. 21 new Lucide icons are registered in `ICONS`.
**Signature changes:**
- `LOOK_PERIOD` changes value from 12 to 24. It now means "sheet claims (originals and twins
  together) before any line repeats" (12 sheets times 2 lap dashes).
- `looks()` keeps its signature but changes behaviour. A twin takes its original's partner sheet
  instead of the original's own sheet. The 7th to 12th originals take partner sheets before any
  dashed lap.
- `strategyIcon(name)` keeps its signature. Prototype keys such as `'constructor'` now draw Sigma
  as well.
**Requires (from earlier phases):** none.
**Leaves alone (owned by others):**
- `web/components/StrategySwitch.tsx` and `StrategySwitch.module.css` (Phase 2). Its `{icon: string}`
  prop stays, and callers pass display icons.
- The `.switch` rule and every rule in `leaderboard.module.css` (Phases 2 and 3).
- `leaderboard/page.tsx`: the checklist sheet `<StrategySwitch …>` call at line 154 (Phase 2), and
  the live card section, `card()` markup, `tabEdge` and the `Legend`/"No common window yet" lines
  (Phase 3). This phase edits only the import at line 6 and the data load at line 33.
- `RetiredShelf.tsx`, the engine and the DB. Twin rows keep the `icon` the engine copies onto them.

## Files

| File | Action | What changes |
|---|---|---|
| `web/app/globals.css` | modify | six partner tints and lines, light (after l.22, l.29) and dark (after l.67, l.73); six `.bg-*` classes (after l.243) |
| `web/app/(app)/leaderboard/view.ts` | modify | l.4-5 header note; l.34-121 palette constants and `looks()` rewritten to the partner rule |
| `web/app/(app)/leaderboard/view.test.ts` | modify | l.1-8 imports; l.19-110 `describe('looks')` rewritten; new `describe('palette tokens in globals.css')` |
| `web/components/roster.ts` | modify | l.1-23: icon registry grows; `displayIcons`, `withDisplayIcons`, `TWIN_ICON`, `SPARE_ICONS` |
| `web/components/roster.test.ts` | modify | l.1-3 imports; l.29-42 `strategyIcon` tests extended; new `describe('displayIcons')` |
| `web/app/(app)/leaderboard/page.tsx` | modify | l.6 import; l.33 board rows carry display icons |
| `web/app/(app)/positions/page.tsx` | modify | l.4 import; l.32 roster carries display icons |
| `web/app/(app)/history/page.tsx` | modify | l.10 import; l.42 roster carries display icons |
| `web/app/sean/plan/page.tsx` | modify | l.3 import, new `lib/data` import; l.28-36 `load()` swaps in display icons |
| `web/lib/sean/planData.ts` | modify | l.26 doc comment on `LinkableMethod.icon` |
| `.claude/skills/verify-seer/features/leaderboard.md` | modify | twin sub-feature, new uniqueness sub-feature, step comment, two gotchas |
| `.claude/skills/verify-seer/features/positions-history.md` | modify | one sentence on the switcher's unique icons |
| `.claude/skills/verify-seer/features/steps/leaderboard-twin.mjs` | rewrite | asserts partner colour, own icon, unique sheets and icons |

## Implementation Steps

Order: CSS tokens, then `looks()` and its tests, then the icon resolver and its tests, then the
consumers, then verify-seer. Each step ends at a state that builds. Run
`npx tsc --noEmit && npx vitest run <file>` after each of Steps 2 to 5.

Worktree setup (once, before Step 1). The worktree has no `web/node_modules`. Hard-link it; a
symlink passes vitest and tsc but breaks `next build`:

```bash
cp -al /home/miftah/seer/web/node_modules /home/miftah/.worktrees/seer/leaderboard-desktop-revamp/web/node_modules
```

### Step 1: Six partner tints in globals.css

**File:** `web/app/globals.css:22`, `:29`, `:67`, `:73`, `:243`
**Change:** Add each family's partner sheet and line in both themes, plus its sheet class. Use
the file's existing dark pattern (the one `@media (prefers-color-scheme: dark)` block). Butter is
untouched.

How the values were chosen. Each value was computed in OKLab this session with a scratch script;
none comes from memory. Each partner sits one hue step from its base: lav to iris (bluer), sky
to teal (greener), sage to moss (yellower), rose to berry (redder), plum to orchid (pinker) and
stone to amber (warmer). In light mode a partner's line is darker than its base, and in dark mode
lighter. So a pair differs in lightness as well as hue.

| Measured | Light | Dark |
|---|---|---|
| Closest pair of the existing 6 lines (OKLab distance) | 0.097 (lav/plum) | 0.067 (lav/plum) |
| Closest pair of all 12 lines | 0.092 (stone/amber) | 0.066 (berry/orchid) |
| Closest pair of the existing 6 sheets | 0.022 (stone/rose) | 0.024 (lav/plum) |
| Closest pair of all 12 sheets, butter and plain sheet included | 0.022 (stone/rose, unchanged) | 0.024 (lav/plum, unchanged) |

Contrast of each new line against `--sheet` (WCAG ratio, must be at least 3:1):

| Line | Light vs `#ffffff` | Dark vs `#211f1c` |
|---|---|---|
| iris | `#005fad` 6.48 | `#a4d6ff` 10.68 |
| teal | `#00756e` 5.57 | `#8be8df` 11.51 |
| moss | `#677000` 5.39 | `#d5e279` 11.73 |
| berry | `#ad2751` 6.59 | `#ffb9c8` 10.20 |
| orchid | `#903182` 7.12 | `#ffb6f5` 10.38 |
| amber | `#a1551e` 5.48 | `#ffbf94` 10.28 |

The existing lines measure 3.50 to 4.64 (light) and 7.41 to 8.95 (dark). Step 3's test re-checks
all twelve against globals.css, so nobody has to trust this table.

**Code (insert after line 22, `  --plum: #ebe0ee;`):**
```css
  /* Each family's partner sheet: a Claude twin wears its original's partner (view.ts looks()). */
  --iris: #cbdff4;
  --teal: #c3e5e1;
  --moss: #dbe0c5;
  --berry: #f2cfd4;
  --orchid: #ebd4e8;
  --amber: #f0d7c6;
```

**Code (insert after line 29, `  --stone-line: #9a7a52;`):**
```css
  --iris-line: #005fad;
  --teal-line: #00756e;
  --moss-line: #677000;
  --berry-line: #ad2751;
  --orchid-line: #903182;
  --amber-line: #a1551e;
```

**Code (insert after line 67, `    --plum: #33263a;`):**
```css
    --iris: #26384c;
    --teal: #1a3e3b;
    --moss: #2e3b26;
    --berry: #4a2d32;
    --orchid: #432f41;
    --amber: #493024;
```

**Code (insert after line 73, `    --stone-line: #cfae84;`):**
```css
    --iris-line: #a4d6ff;
    --teal-line: #8be8df;
    --moss-line: #d5e279;
    --berry-line: #ffb9c8;
    --orchid-line: #ffb6f5;
    --amber-line: #ffbf94;
```

**Code (insert after line 243, `.bg-plum { background: var(--plum); }`):**
```css
.bg-iris { background: var(--iris); }
.bg-teal { background: var(--teal); }
.bg-moss { background: var(--moss); }
.bg-berry { background: var(--berry); }
.bg-orchid { background: var(--orchid); }
.bg-amber { background: var(--amber); }
```

**Impact:** No visual change yet, because nothing uses the classes. The names do not collide
with anything: `grep -rnE -- '--(iris|teal|moss|berry|orchid|amber)\b|bg-(iris|teal|moss|berry|orchid|amber)'`
over `web/` (excluding node_modules) returned nothing this session.

### Step 2: Partner-hue `looks()` in view.ts

**File:** `web/app/(app)/leaderboard/view.ts:4-5` and `:34-121`
**Change:** Rewrite the palette and `looks()` to the partner rule.
- The i-th original (twins are not counted) takes `SLOT_BGS[i]`: the six bases, then the six
  partners, last family first. Because twins are not counted, originals never depend on twins.
- A twin takes its original's partner when no original holds it. Otherwise it takes the first
  free slot from its original's lap onward. A twin's stroke is always a `TWIN_DASHES` stroke.
- Beyond twelve claims the existing dashed lap begins.

**Code (replace lines 4-5):**
```ts
// Selection (`selectStrategy`) and icons (`strategyIcon`, and `displayIcons` that makes them unique
// per roster) are `components/roster.ts`; short labels are phase 10's `Strategy.short`; the month
// math is phase 10's `lib/monthly.ts`.
```

**Code (replace lines 34-121, from the `/**` above `CARD_BGS` through the closing `}` of `looks`):**
```ts
/**
 * Every research strategy gets a sheet of its own, and a Claude twin gets the sheet next to its
 * original's. The palette is six families, each a base tint and a partner tint one step round the
 * colour wheel: lav/iris, sky/teal, sage/moss, rose/berry, plum/orchid, stone/amber. An original
 * takes the next slot of `SLOT_BGS` in roster order: the six bases first (the design's lav, sky and
 * stone plus sage, rose and plum, so the first six keep the colours they always had), then the
 * partners. A twin takes its original's partner. So a pair still reads as a pair (F4 sky,
 * F4+Claude teal) and never shares a card, a tab or a line with anything else on the board.
 *
 * Partners are lent to originals from the last family backwards. A seventh original has to borrow
 * one, and the families at the top of the roster are the ones the owner has read longest, so they
 * keep their natural pair the longest. A twin whose partner an original already holds takes the
 * first free slot instead (see `looks`).
 *
 * Butter is not in the palette: it is the checklist's own sheet on mobile, and the month-by-month
 * sheet stacked right under it takes the picked strategy's tint, so a butter strategy would merge
 * them. Stone, the closest tint to the plain sheet in dark mode, is the last base. The partners were
 * picked in OKLab so that no two of the twelve sit closer than the two closest original tints
 * already did, and each is a step darker (light theme) or lighter (dark theme) than its base, so a
 * pair differs in lightness as well as in hue.
 *
 * Each sheet has its chart line in the same colour family (`--<tint>-line`, at least 3:1 against
 * the plain chart sheet in both themes; view.test.ts reads globals.css and holds that), so a card,
 * its tab and its curve all say the same colour.
 *
 * The roster is variable length, so the palette may not be assumed to cover it. Twelve research
 * strategies fill it. The thirteenth starts a second lap that reuses the sheets with a dashed line,
 * so lines stay unique for `LOOK_PERIOD` claims; past that both repeat. Every token is defined for
 * light and dark in `globals.css`.
 */
export const CARD_BGS = ['bg-lav', 'bg-sky', 'bg-sage', 'bg-rose', 'bg-plum', 'bg-stone'] as const;

/** Each family's partner sheet, at the same index as its base in `CARD_BGS`. */
export const PARTNER_BGS = ['bg-iris', 'bg-teal', 'bg-moss', 'bg-berry', 'bg-orchid', 'bg-amber'] as const;

/** The order originals take sheets in: the six bases, then the partners, last family first. */
export const SLOT_BGS = [...CARD_BGS, 'bg-amber', 'bg-orchid', 'bg-berry', 'bg-moss', 'bg-teal', 'bg-iris'] as const;

/** Research strategies before any sheet repeats. */
export const PALETTE_SIZE = SLOT_BGS.length;

/** Stroke patterns per lap of the palette: solid, then dashed. SPY's dotted '1 4' is not among them. */
export const LAP_DASHES = [null, '7 5'] as const;

/**
 * A Claude twin's stroke, by the lap of the sheet it holds: short even dashes, then dash-dot.
 * Neither is a lap dash or SPY's dotted '1 4', so a twin's line never equals an original's even
 * where a later lap reuses its colour. With the partner colour, the pair reads as "this one's pair,
 * with Claude" even on a glance at the legend.
 */
export const TWIN_DASHES = ['3 3', '10 3 2 3'] as const;

/** Sheet claims, originals and twins together, before any line repeats. */
export const LOOK_PERIOD = PALETTE_SIZE * LAP_DASHES.length;

/**
 * `bg` is the sheet class; `tint` is the same colour as a CSS value, for surfaces that borrow it;
 * `dash` is the line's stroke-dasharray, null for a solid line.
 */
export type Look = { bg: string; tint: string; line: string; width: number; dash: string | null };

/** 'bg-lav' -> 'lav': every sheet class in globals.css is a one-token background. */
const tokenOf = (bg: string): string => bg.slice(3);

/** One claim on the palette: which tint, on which lap of it. */
type Slot = { token: string; lap: number };

/** The n-th claim in `SLOT_BGS` order, laps included. */
const slotAt = (n: number): Slot => ({ token: tokenOf(SLOT_BGS[n % PALETTE_SIZE]), lap: Math.floor(n / PALETTE_SIZE) });

/** 'sky' -> 'teal' and 'teal' -> 'sky': a pair is a pair from either side. */
const PARTNER = new Map<string, string>(
  CARD_BGS.flatMap((bg, i): [string, string][] => [
    [tokenOf(bg), tokenOf(PARTNER_BGS[i])],
    [tokenOf(PARTNER_BGS[i]), tokenOf(bg)],
  ]),
);

export const LOOK_FALLBACK: Look = { bg: 'bg-sheet', tint: 'var(--sheet)', line: 'var(--ink-2)', width: 2, dash: null };

/** SPY's stroke: the benchmark is the dotted line on a plain sheet. */
export const BENCHMARK_DASH = '1 4';

/**
 * Card sheet and chart line per strategy id, by roster order, in three passes so that no
 * original's look can depend on a twin:
 *
 * 1. SPY gets the plain sheet and the dotted line. The i-th original (every row that is not an
 *    attached twin, a twin whose original is absent included) takes `SLOT_BGS[i]` with its lap's
 *    dash. Twins are not counted, so adding one moves no original: the owner keeps reading F1 as
 *    sage and C as rose.
 * 2. Each attached twin takes its original's partner, on its original's lap, when nothing holds it
 *    yet, with a `TWIN_DASHES` stroke and the ordinary width (a twin is never champion). That
 *    depends only on the original, so it does not depend on where the twin sits in `roster`.
 * 3. A twin whose partner is held (an original borrowed it, or the original has a second twin)
 *    takes the first free slot from its original's lap on. Up to `PALETTE_SIZE` research
 *    strategies there is always one on the first lap, so no two of them share a sheet, a tint or a
 *    line colour.
 */
export function looks(roster: RosterIn[]): Map<string, Look> {
  const out = new Map<string, Look>();
  const byId = new Map(roster.map(st => [st.id, st]));
  const originalOf = (st: RosterIn): RosterIn | null => {
    if (st.isBenchmark) return null;
    const o = attachedOriginal(st, byId);
    return o && !o.isBenchmark ? o : null;
  };
  const held = new Set<string>();
  const slotOf = new Map<string, Slot>();
  const keyOf = (s: Slot): string => `${s.token}|${s.lap}`;
  const claim = (st: RosterIn, s: Slot, dash: string | null, width: number): void => {
    held.add(keyOf(s));
    slotOf.set(st.id, s);
    out.set(st.id, { bg: `bg-${s.token}`, tint: `var(--${s.token})`, line: `var(--${s.token}-line)`, width, dash });
  };

  let i = 0;
  for (const st of roster) {
    if (st.isBenchmark) {
      out.set(st.id, { bg: 'bg-sheet', tint: 'var(--sheet)', line: 'var(--ink-3)', width: 1.75, dash: BENCHMARK_DASH });
      continue;
    }
    if (originalOf(st)) continue;
    const s = slotAt(i);
    claim(st, s, LAP_DASHES[s.lap % LAP_DASHES.length], st.isChampion ? 2.75 : 2);
    i += 1;
  }

  const twins = roster.flatMap(st => {
    const o = originalOf(st);
    const at = o ? slotOf.get(o.id) : undefined;
    return at ? [{ st, at }] : [];
  });
  const displaced: typeof twins = [];
  for (const t of twins) {
    const want: Slot = { token: PARTNER.get(t.at.token) ?? t.at.token, lap: t.at.lap };
    if (held.has(keyOf(want))) displaced.push(t);
    else claim(t.st, want, TWIN_DASHES[want.lap % TWIN_DASHES.length], 2);
  }
  for (const t of displaced) {
    let n = t.at.lap * PALETTE_SIZE;
    while (held.has(keyOf(slotAt(n)))) n += 1;
    const s = slotAt(n);
    claim(t.st, s, TWIN_DASHES[s.lap % TWIN_DASHES.length], 2);
  }
  return out;
}
```

**Impact:**
- Demo board (verify-seer `up`): A lav, F4 sky, F4+Claude goes from sky to **teal** (`3 3`), F1
  sage, C rose.
- Production board, roster order taken from the analysis's 1440 screenshot and not re-read from
  the DB this session: C, COSK, COSK+Claude, RAW35, RAW35+Claude, A, A+Claude. Every original keeps
  its colour, and the three twins move to their partners (teal, moss and berry if C, COSK, RAW35
  and A are lav, sky, sage and rose). Proof journey 6 reads the real board back.
- Only rosters with seven or more originals change for originals: the 7th original moves from
  lav-dashed to amber-solid. The live board has four originals (unverified count, from the same
  screenshot).
- The `lapOf` map and the "copy the original's look" branch are gone. Nothing outside view.ts used
  them (`grep -rn "TWIN_DASHES\|LOOK_PERIOD\|CARD_BGS\|LAP_DASHES"` hit only view.ts and
  view.test.ts this session).

### Step 3: Rewrite the `looks` tests and pin the palette tokens

**File:** `web/app/(app)/leaderboard/view.test.ts:1-8` and `:19-110`
**Change:** Rewrite `describe('looks')` to the partner rule. The tests that still hold are kept
word for word. The twin tests now assert partner colours, uniqueness and "adding a twin moves no
original", all exhaustively up to a full palette. A new `describe` reads `globals.css` and pins
three things: every palette token exists in both themes, every line contrasts at least 3:1, and
butter stays out. This is the lever for a mistake no reviewer can see by eye: a token forgotten in
the dark block renders a transparent card in dark mode only.

**Code (replace lines 1-8):**
```ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { checklist, type Metrics, type Snapshot } from '../../../lib/metrics';
import type { MonthlyTable } from '../../../lib/monthly';
import {
  CARD_BGS, CHECKS, compare, LOOK_PERIOD, looks, MIN_COMMON_SESSIONS, MIN_RANKED, monthLabel, monthLines,
  NO_GATE, PALETTE_SIZE, PARTNER_BGS, pickResearch, researchOf, retiredLabel, scoreOf, sinceStartLine,
  SLOT_BGS, spyOverSpan, TWIN_DASHES, twinChipTip, windowLine, type GateIn, type RankIn, type RosterIn,
} from './view';
```

**Code (replace lines 19-110, the whole `describe('looks', …)` block):**
```ts
const research = (n: number, prefix = 'S'): RosterIn[] =>
  Array.from({ length: n }, (_, i) => ({ id: `${prefix}${i}`, isChampion: false, isBenchmark: false }));
const twinOf = (o: RosterIn): RosterIn => ({ id: `${o.id}-CX`, isChampion: false, isBenchmark: false, twinOf: o.id });

describe('looks', () => {
  it('gives the benchmark the dotted line on a plain sheet', () => {
    expect(looks(roster).get('SPY')).toEqual({ bg: 'bg-sheet', tint: 'var(--sheet)', line: 'var(--ink-3)', width: 1.75, dash: '1 4' });
  });
  it('assigns research sheets, and lines of the same colour, in roster order', () => {
    const l = looks(roster);
    expect(RESEARCH.map(id => l.get(id)!.bg)).toEqual(['bg-lav', 'bg-sky', 'bg-sage', 'bg-rose']);
    expect(RESEARCH.map(id => l.get(id)!.tint)).toEqual(['var(--lav)', 'var(--sky)', 'var(--sage)', 'var(--rose)']);
    expect(RESEARCH.map(id => l.get(id)!.line)).toEqual(['var(--lav-line)', 'var(--sky-line)', 'var(--sage-line)', 'var(--rose-line)']);
    expect(RESEARCH.map(id => l.get(id)!.width)).toEqual([2, 2, 2, 2]);
    expect(RESEARCH.map(id => l.get(id)!.dash)).toEqual([null, null, null, null]);
  });
  it('never gives C the look of A', () => {
    const l = looks(roster);
    expect(l.get('C')).not.toEqual(l.get('A'));
    expect(l.get('C')).toEqual({ bg: 'bg-rose', tint: 'var(--rose)', line: 'var(--rose-line)', width: 2, dash: null });
  });
  it('follows roster order, not ids', () => {
    const l = looks([roster[3], roster[0], roster[1]]);
    expect(l.get('F1-SPY-SMA200-M')!.bg).toBe('bg-lav');
    expect(l.get('A')!.bg).toBe('bg-sky');
  });
  it('gives six research strategies six different sheets, butter never among them', () => {
    const extra = ['X9', 'X10'].map(id => ({ id, isChampion: false, isBenchmark: false }));
    const l = looks([...roster, ...extra]);
    const bgs = [...RESEARCH, ...extra.map(e => e.id)].map(id => l.get(id)!.bg);
    expect(new Set(bgs).size).toBe(6);
    expect(bgs).not.toContain('bg-butter');
    expect(bgs).not.toContain('bg-sheet');
    expect(l.get('X9')).toEqual({ bg: 'bg-plum', tint: 'var(--plum)', line: 'var(--plum-line)', width: 2, dash: null });
    expect(l.get('X10')).toEqual({ bg: 'bg-stone', tint: 'var(--stone)', line: 'var(--stone-line)', width: 2, dash: null });
  });
  it('lends the seventh to twelfth originals the partners, last family first, before any dashed lap', () => {
    const l = looks(research(13));
    expect(l.get('S6')).toEqual({ bg: 'bg-amber', tint: 'var(--amber)', line: 'var(--amber-line)', width: 2, dash: null });
    expect(['S6', 'S7', 'S8', 'S9', 'S10', 'S11'].map(id => l.get(id)!.bg))
      .toEqual(['bg-amber', 'bg-orchid', 'bg-berry', 'bg-moss', 'bg-teal', 'bg-iris']);
    expect(l.get('S12')).toEqual({ bg: 'bg-lav', tint: 'var(--lav)', line: 'var(--lav-line)', width: 2, dash: '7 5' });
  });
  it('never gives two research strategies the same sheet up to PALETTE_SIZE, or the same line up to LOOK_PERIOD', () => {
    expect(PALETTE_SIZE).toBe(12);
    expect(LOOK_PERIOD).toBe(24);
    const many = research(LOOK_PERIOD);
    const l = looks(many);
    expect(new Set(many.slice(0, PALETTE_SIZE).map(st => l.get(st.id)!.bg)).size).toBe(PALETTE_SIZE);
    expect(new Set(many.map(st => `${l.get(st.id)!.line}|${l.get(st.id)!.dash}`)).size).toBe(LOOK_PERIOD);
  });
  it('emphasises a non-benchmark champion', () => {
    const l = looks([{ ...roster[0], isChampion: false }, { ...roster[1], isChampion: true }]);
    expect(l.get('A')!.width).toBe(2.75);
  });

  // Seer Adversarial + R1: a Claude twin wears its original's PARTNER colour with a twin dash. It
  // takes no original's slot, so every original keeps the colour it had before twins existed.
  const F4_TWIN: RosterIn = { id: 'F4-MOM12-N20-TREND-CX', isChampion: false, isBenchmark: false, twinOf: 'F4-MOM12-N20-TREND' };
  const withTwin: RosterIn[] = [roster[0], roster[1], roster[2], F4_TWIN, roster[3], roster[4]];

  it("gives a twin its original's partner sheet, tint and line, with a twin dash", () => {
    const l = looks(withTwin);
    expect(l.get('F4-MOM12-N20-TREND')).toEqual({ bg: 'bg-sky', tint: 'var(--sky)', line: 'var(--sky-line)', width: 2, dash: null });
    expect(l.get(F4_TWIN.id)).toEqual({ bg: 'bg-teal', tint: 'var(--teal)', line: 'var(--teal-line)', width: 2, dash: TWIN_DASHES[0] });
  });
  it('pairs every family with its own partner', () => {
    const originals = research(6);
    const twins = originals.map(twinOf);
    const l = looks([roster[0], ...originals, ...twins]);
    expect(originals.map(o => l.get(o.id)!.bg)).toEqual([...CARD_BGS]);
    expect(twins.map(t => l.get(t.id)!.bg)).toEqual([...PARTNER_BGS]);
  });
  it('moves no other strategy: originals keep their looks', () => {
    const before = looks(roster), after = looks(withTwin);
    for (const id of RESEARCH) expect(after.get(id)).toEqual(before.get(id));
    expect(after.get('SPY')).toEqual(before.get('SPY'));
  });
  it('moves no original, whichever original gains a twin, up to a full palette', () => {
    for (let n = 1; n <= PALETTE_SIZE; n++) {
      const originals = research(n);
      const before = looks([roster[0], ...originals]);
      for (const o of originals) {
        const after = looks([roster[0], ...originals, twinOf(o)]);
        for (const p of originals) expect(after.get(p.id)).toEqual(before.get(p.id));
      }
    }
  });
  it('gives every research strategy its own sheet and line colour, twins included, up to PALETTE_SIZE', () => {
    for (let n = 1; n <= PALETTE_SIZE; n++) {
      const originals = research(n);
      const t = Math.min(n, PALETTE_SIZE - n);
      // Twins of the first originals (natural partners), then of the last (the most displaced).
      for (const paired of [originals.slice(0, t), originals.slice(n - t)]) {
        const all = [...originals, ...paired.map(twinOf)];
        const l = looks([roster[0], ...all]);
        const bgs = all.map(st => l.get(st.id)!.bg);
        expect(new Set(bgs).size).toBe(all.length);
        expect(new Set(all.map(st => l.get(st.id)!.line)).size).toBe(all.length);
        expect(bgs).not.toContain('bg-butter');
        expect(bgs).not.toContain('bg-sheet');
      }
    }
  });
  it('lends a displaced twin the first free sheet', () => {
    // Seven originals: S6 borrows stone's partner (amber), so stone's twin takes the next free one.
    const originals = research(7);
    const l = looks([...originals, twinOf(originals[5])]);
    expect(l.get('S6')!.bg).toBe('bg-amber');
    expect(l.get('S5-CX')).toEqual({ bg: 'bg-orchid', tint: 'var(--orchid)', line: 'var(--orchid-line)', width: 2, dash: TWIN_DASHES[0] });
  });
  it('does not depend on where the twin sits in the roster', () => {
    const first = looks([F4_TWIN, ...roster]);
    expect(first.get(F4_TWIN.id)).toEqual(looks(withTwin).get(F4_TWIN.id));
    expect(first.get('A')!.bg).toBe('bg-lav');
  });
  it('colours a twin whose original is not on the roster like any other strategy', () => {
    const l = looks([roster[0], { id: 'X-CX', isChampion: false, isBenchmark: false, twinOf: 'X' }]);
    expect(l.get('X-CX')).toEqual({ bg: 'bg-lav', tint: 'var(--lav)', line: 'var(--lav-line)', width: 2, dash: null });
  });
  it("never emphasises a twin, even when its original is champion", () => {
    const l = looks([{ ...roster[1], isChampion: true }, { id: 'A-CX', isChampion: false, isBenchmark: false, twinOf: 'A' }]);
    expect(l.get('A')!.width).toBe(2.75);
    expect(l.get('A-CX')!.width).toBe(2);
  });
  it('never gives a twin the line of any original or of SPY, up to PALETTE_SIZE originals each with a twin', () => {
    const originals = research(PALETTE_SIZE);
    const twins = originals.map(twinOf);
    const l = looks([roster[0], ...originals, ...twins]);
    const all = [...originals, ...twins].map(st => `${l.get(st.id)!.line}|${l.get(st.id)!.dash}`);
    expect(new Set(all).size).toBe(LOOK_PERIOD);
    // Twelve originals hold every first-lap sheet, so every twin is lent one on the second lap.
    expect(l.get('S0-CX')!.dash).toBe(TWIN_DASHES[1]);
    for (const t of twins) expect(TWIN_DASHES as readonly string[]).toContain(l.get(t.id)!.dash);
  });
});

describe('palette tokens in globals.css', () => {
  const css = readFileSync(join(import.meta.dirname, '../../globals.css'), 'utf8');
  const light = css.match(/^:root \{([^}]*)\}/m)?.[1] ?? '';
  const dark = css.match(/@media \(prefers-color-scheme: dark\) \{\s*:root \{([^}]*)\}/)?.[1] ?? '';
  const token = (block: string, name: string): string | null =>
    block.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6});`))?.[1] ?? null;
  const luminance = (hex: string): number => {
    const [r, g, b] = [1, 3, 5]
      .map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map(c => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const contrast = (a: string, b: string): number => {
    const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (hi + 0.05) / (lo + 0.05);
  };

  it('finds both theme blocks', () => {
    expect(token(light, 'sheet')).toBe('#ffffff');
    expect(token(dark, 'sheet')).toBe('#211f1c');
  });
  it('defines every palette sheet and line for light and dark, with a sheet class', () => {
    for (const bg of SLOT_BGS) {
      const t = bg.slice(3);
      for (const block of [light, dark]) {
        expect(token(block, t), `--${t}`).not.toBeNull();
        expect(token(block, `${t}-line`), `--${t}-line`).not.toBeNull();
      }
      expect(css).toContain(`.${bg} { background: var(--${t}); }`);
    }
  });
  it('keeps every chart line at 3:1 or better against the plain chart sheet, in both themes', () => {
    for (const block of [light, dark]) {
      const sheet = token(block, 'sheet')!;
      for (const bg of SLOT_BGS) {
        const line = token(block, `${bg.slice(3)}-line`)!;
        expect(contrast(line, sheet), `${bg} line ${line} on ${sheet}`).toBeGreaterThanOrEqual(3);
      }
    }
  });
  it('keeps butter out of a palette of twelve different sheets', () => {
    expect(SLOT_BGS as readonly string[]).not.toContain('bg-butter');
    expect(new Set(SLOT_BGS).size).toBe(12);
  });
});
```
(`roster` and `RESEARCH` at lines 10-17 stay as they are; the new `research`/`twinOf` helpers sit
just above `describe('looks')`. The `describe('researchOf')` block and everything after line 110
are unchanged.)

**Impact:** `npx vitest run 'app/(app)/leaderboard/view.test.ts'` passes. `looks` gets 19 cases
and the palette gets 4.

### Step 4: Unique display icons in roster.ts

**File:** `web/components/roster.ts:1-23`
**Change:**
- Register the twin partners and the spare pool in `ICONS`.
- Normalise unknown names to the Sigma they draw. This also covers prototype keys.
- Add `displayIcons`, a pure resolver. It walks the roster in order: SPY first, then each row
  claims its wanted icon. A twin wants `TWIN_ICON[original's icon]`. Any collision takes the next
  free `SPARE_ICONS` entry.
- Add `withDisplayIcons`, which returns the rows with `icon` swapped.

None of the new icons is a `-off` icon, because those read as "disabled". The spare pool also
leaves out icons the app already uses for other meanings: `telescope` is Sera's nav icon, and
`target` and `hourglass` are History's exit reasons. Every name below was checked against
`lucide-react@1.50.0`'s `.d.ts` this session (`Building2` and `Waves` do not exist there, so they
are not used). The rendered `<svg>` carries `class="lucide lucide-<name>"`, which Step 10's
browser check reads.

**Code (replace lines 1-23):**
```ts
import {
  Activity, Anchor, BookOpen, BrainCircuit, Building, CloudLightning, Compass, Cpu, Feather, Flame, Gauge, Gavel, Gem,
  Landmark, Leaf, Library, Mountain, Newspaper, Orbit, Pi, Puzzle, Radar, Rocket, Sailboat, Scale, Shield, Sigma,
  Tornado, Umbrella, Waypoints, Weight, Zap, type LucideIcon,
} from 'lucide-react';
import { attachedOriginal } from '../lib/strategy';

// The `icon` column of `strategies` names a Lucide icon (kebab-case). Roster: landmark (SPY),
// sigma (A), trending-up (F4), shield (F1), gavel (C, migration 004), book-open (FND), activity (RM, 010),
// zap (RAW, 013), scale (MVW, 013), cloud-lightning (COSK, 022: the stocks that fall hardest in the market's storms);
// brain-circuit kept for old demo rows.
// F4's stored 'trending-up' draws Gauge: History's "Wins only" filter already uses TrendingUp.
//
// The rest are display-only, never stored: each stored icon's twin partner (`TWIN_ICON`) and the
// spare pool (`SPARE_ICONS`) that `displayIcons` draws from when two rows would share an icon.
const ICONS: Record<string, LucideIcon> = {
  landmark: Landmark,
  sigma: Sigma,
  'trending-up': Gauge,
  shield: Shield,
  'brain-circuit': BrainCircuit,
  gavel: Gavel,
  'book-open': BookOpen,
  activity: Activity,
  zap: Zap,
  scale: Scale,
  'cloud-lightning': CloudLightning,
  building: Building,
  pi: Pi,
  rocket: Rocket,
  umbrella: Umbrella,
  cpu: Cpu,
  newspaper: Newspaper,
  library: Library,
  radar: Radar,
  flame: Flame,
  weight: Weight,
  tornado: Tornado,
  compass: Compass,
  anchor: Anchor,
  feather: Feather,
  gem: Gem,
  leaf: Leaf,
  mountain: Mountain,
  orbit: Orbit,
  puzzle: Puzzle,
  sailboat: Sailboat,
  waypoints: Waypoints,
};

/** The registered name a stored icon draws as: itself when registered, else 'sigma', the fallback. */
const drawnName = (name: string): string => (Object.prototype.hasOwnProperty.call(ICONS, name) ? name : 'sigma');

/** The Lucide icon a strategies row names; Sigma when the name is unknown. */
export const strategyIcon = (name: string): LucideIcon => ICONS[drawnName(name)];

/**
 * A Claude twin's icon, by its original's. The engine copies the original's `icon` onto the twin
 * row (`ensure_twins`), which made a pair indistinguishable in every icon row on the site. Each
 * partner keeps a family likeness so the pair still reads as a pair (sigma/pi, gavel/newspaper,
 * zap/flame, cloud-lightning/tornado) while drawing visibly differently at 19px. Display only: the
 * DB keeps what the engine wrote, so no migration and no engine change for a visual concern.
 */
export const TWIN_ICON: ReadonlyMap<string, string> = new Map([
  ['landmark', 'building'],
  ['sigma', 'pi'],
  ['trending-up', 'rocket'],
  ['shield', 'umbrella'],
  ['brain-circuit', 'cpu'],
  ['gavel', 'newspaper'],
  ['book-open', 'library'],
  ['activity', 'radar'],
  ['zap', 'flame'],
  ['scale', 'weight'],
  ['cloud-lightning', 'tornado'],
]);

/**
 * Where a row goes when the icon it wants is already on the board, in this order. None of them is
 * a stored icon, a twin partner, a `-off` icon (those read as "disabled"), or an icon the app uses
 * for something else (telescope is Sera's nav icon; target and hourglass are History's exits).
 */
export const SPARE_ICONS = [
  'compass', 'anchor', 'feather', 'gem', 'leaf', 'mountain', 'orbit', 'puzzle', 'sailboat', 'waypoints',
] as const;

/** The roster fields the resolver reads: a structural subset of lib/data's `Strategy`. */
export type IconIn = { id: string; icon: string; isBenchmark: boolean; twinOf?: string | null };

/**
 * One icon name per strategy id, unique across `roster` (R1: every method is unique in icon).
 *
 * The benchmark claims first, so SPY always keeps its landmark. Then each row, in roster order,
 * claims the icon it stores (an unknown name counts as the Sigma it draws), and an attached Claude
 * twin claims its original's partner (`TWIN_ICON`). A claim that is already taken gets the next
 * free `SPARE_ICONS` entry. Only if all of those are gone too does it keep what it wanted.
 *
 * Every screen passes the roster it already has. Claims run in roster order, so a list resolves
 * the same way whatever rows follow it. `strategies()` is a prefix of `boardStrategies()`, which is
 * why Positions, History, Sean's plan and the Leaderboard agree on every live strategy's icon. A
 * twin listed before its original resolves the original first, so a twin's icon never depends on
 * where it sits.
 */
export function displayIcons(roster: IconIn[]): Map<string, string> {
  const out = new Map<string, string>();
  const taken = new Set<string>();
  const byId = new Map(roster.map(st => [st.id, st]));
  const claim = (st: IconIn, wanted: string): void => {
    const icon = !taken.has(wanted) ? wanted : (SPARE_ICONS.find(n => !taken.has(n)) ?? wanted);
    taken.add(icon);
    out.set(st.id, icon);
  };
  const resolve = (st: IconIn): void => {
    if (out.has(st.id)) return;
    const o = st.isBenchmark ? null : attachedOriginal(st, byId);
    if (!o || o.isBenchmark) {
      claim(st, drawnName(st.icon));
      return;
    }
    resolve(o);
    const mine = out.get(o.id) ?? drawnName(o.icon);
    claim(st, TWIN_ICON.get(mine) ?? mine);
  };
  for (const st of roster) if (st.isBenchmark) resolve(st);
  for (const st of roster) resolve(st);
  return out;
}

/** `roster` with each row's `icon` replaced by its `displayIcons` name; the input is not mutated. */
export function withDisplayIcons<T extends IconIn>(roster: T[]): T[] {
  const icons = displayIcons(roster);
  return roster.map(st => ({ ...st, icon: icons.get(st.id) ?? st.icon }));
}
```
(Lines 25-43, the `selectStrategy` and `sharesLabel` code, are unchanged.)

**Impact:** This is a pure module. `lib/strategy.ts` has no DB access (its header says so), so
the client component `LinkPicker.tsx`, which imports `strategyIcon` from here, stays client-safe.

### Step 5: Resolver tests

**File:** `web/components/roster.test.ts:1-3`, `:29-42`, and append
**Change:** Extend the `strategyIcon` tests and add `describe('displayIcons')`.

**Code (replace lines 1-3):**
```ts
import { BookOpen, CloudLightning, Gauge, Gavel, Landmark, Rocket, Scale, Shield, Sigma, Zap } from 'lucide-react';
import { describe, expect, it } from 'vitest';
import {
  displayIcons, selectStrategy, sharesLabel, SPARE_ICONS, strategyIcon, TWIN_ICON, withDisplayIcons, type IconIn,
} from './roster';
```

**Code (replace lines 29-42, the `describe('strategyIcon')` block):**
```ts
describe('strategyIcon', () => {
  it('maps the roster icons and falls back to Sigma', () => {
    expect(strategyIcon('landmark')).toBe(Landmark);
    expect(strategyIcon('trending-up')).toBe(Gauge);
    expect(strategyIcon('shield')).toBe(Shield);
    expect(strategyIcon('gavel')).toBe(Gavel);
    expect(strategyIcon('sigma')).toBe(Sigma);
    expect(strategyIcon('book-open')).toBe(BookOpen);
    expect(strategyIcon('zap')).toBe(Zap);
    expect(strategyIcon('scale')).toBe(Scale);
    expect(strategyIcon('cloud-lightning')).toBe(CloudLightning);
    expect(strategyIcon('nope')).toBe(Sigma);
    expect(strategyIcon('constructor')).toBe(Sigma);
  });
  it('registers every twin partner and spare, each drawing its own icon, none a disabled-looking -off', () => {
    const extra = [...TWIN_ICON.values(), ...SPARE_ICONS];
    for (const name of extra) {
      expect(strategyIcon(name), name).not.toBe(Sigma);
      expect(name.endsWith('-off')).toBe(false);
    }
    const drawn = [...TWIN_ICON.keys(), ...extra].map(strategyIcon);
    expect(new Set(drawn).size).toBe(drawn.length);
  });
});
```

**Code (append at end of file):**
```ts
const row = (id: string, icon: string, extra: Partial<IconIn> = {}): IconIn => ({ id, icon, isBenchmark: false, twinOf: null, ...extra });
const SPY = row('SPY', 'landmark', { isBenchmark: true });

describe('displayIcons', () => {
  it('keeps every stored icon when none collide', () => {
    const r = [SPY, row('A', 'sigma'), row('F4', 'trending-up'), row('F1', 'shield'), row('C', 'gavel')];
    expect([...displayIcons(r)]).toEqual([['SPY', 'landmark'], ['A', 'sigma'], ['F4', 'trending-up'], ['F1', 'shield'], ['C', 'gavel']]);
  });
  it("gives a twin its original's partner icon", () => {
    const m = displayIcons([SPY, row('F4', 'trending-up'), row('F4-CX', 'trending-up', { twinOf: 'F4' })]);
    expect(m.get('F4')).toBe('trending-up');
    expect(m.get('F4-CX')).toBe('rocket');
    expect(strategyIcon(m.get('F4-CX')!)).toBe(Rocket);
  });
  it('resolves the board the owner reported (three originals with twins) to eight different icons', () => {
    // Roster order and stored icons from the 2026-11-10 analysis screenshot; ids shortened.
    const r = [
      SPY, row('C', 'gavel'),
      row('COSK', 'cloud-lightning'), row('COSK-CX', 'cloud-lightning', { twinOf: 'COSK' }),
      row('RAW35', 'zap'), row('RAW35-CX', 'zap', { twinOf: 'RAW35' }),
      row('A', 'sigma'), row('A-CX', 'sigma', { twinOf: 'A' }),
    ];
    const m = displayIcons(r);
    expect(r.map(st => m.get(st.id))).toEqual(['landmark', 'gavel', 'cloud-lightning', 'tornado', 'zap', 'flame', 'sigma', 'pi']);
  });
  it('keeps landmark for SPY even when a research row listed before it stores landmark', () => {
    const m = displayIcons([row('X', 'landmark'), SPY]);
    expect(m.get('SPY')).toBe('landmark');
    expect(m.get('X')).toBe(SPARE_ICONS[0]);
  });
  it('gives each later original that stores a taken icon the next spare', () => {
    const m = displayIcons([SPY, row('A', 'sigma'), row('B', 'sigma'), row('C', 'sigma')]);
    expect([m.get('A'), m.get('B'), m.get('C')]).toEqual(['sigma', SPARE_ICONS[0], SPARE_ICONS[1]]);
  });
  it('treats an unknown stored icon as the Sigma it draws', () => {
    const m = displayIcons([SPY, row('A', 'sigma'), row('B', 'nope')]);
    expect(m.get('B')).toBe(SPARE_ICONS[0]);
  });
  it('sends a twin to a spare when an original already holds its partner icon', () => {
    const m = displayIcons([SPY, row('F4', 'trending-up'), row('R', 'rocket'), row('F4-CX', 'trending-up', { twinOf: 'F4' })]);
    expect(m.get('R')).toBe('rocket');
    expect(m.get('F4-CX')).toBe(SPARE_ICONS[0]);
  });
  it('does not depend on where a twin sits relative to its original', () => {
    const after = displayIcons([SPY, row('F4', 'trending-up'), row('F4-CX', 'trending-up', { twinOf: 'F4' })]);
    const before = displayIcons([SPY, row('F4-CX', 'trending-up', { twinOf: 'F4' }), row('F4', 'trending-up')]);
    expect(before.get('F4')).toBe(after.get('F4'));
    expect(before.get('F4-CX')).toBe(after.get('F4-CX'));
  });
  it('resolves a list the same way when more rows follow it (strategies() vs boardStrategies())', () => {
    const live = [SPY, row('A', 'sigma'), row('A-CX', 'sigma', { twinOf: 'A' }), row('F4', 'trending-up')];
    const board = [...live, row('OLD', 'pi'), row('OLD-CX', 'pi', { twinOf: 'OLD' })];
    const a = displayIcons(live), b = displayIcons(board);
    for (const st of live) expect(b.get(st.id)).toBe(a.get(st.id));
    expect(b.get('OLD')).toBe(SPARE_ICONS[0]);
    expect(b.get('OLD-CX')).toBe(SPARE_ICONS[1]);
  });
  it('draws a different icon for every row of a twelve-strategy roster where every original has a twin', () => {
    const stored = [...TWIN_ICON.keys()].filter(n => n !== 'landmark').slice(0, 6);
    const all = [SPY, ...stored.flatMap((icon, i) => [row(`S${i}`, icon), row(`S${i}-CX`, icon, { twinOf: `S${i}` })])];
    const m = displayIcons(all);
    const drawn = all.map(st => strategyIcon(m.get(st.id)!));
    expect(new Set(drawn).size).toBe(all.length);
  });
  it('withDisplayIcons swaps only the icon, keeps the order and leaves the input alone', () => {
    const r = [SPY, row('F4', 'trending-up'), row('F4-CX', 'trending-up', { twinOf: 'F4' })];
    const out = withDisplayIcons(r);
    expect(out.map(st => st.id)).toEqual(['SPY', 'F4', 'F4-CX']);
    expect(out[2]).toEqual({ ...r[2], icon: 'rocket' });
    expect(r[2].icon).toBe('trending-up');
  });
});
```

**Impact:** `npx vitest run components/roster.test.ts` passes.

### Step 6: Leaderboard rows carry display icons

**File:** `web/app/(app)/leaderboard/page.tsx:6`, `:33`
**Change:** Resolve icons once over the whole board roster (live and retired), and rebuild
`board` with display icons. After that, everything below that reads `st.icon` gets the unique
icon without further changes: `card()` at l.233, and `switchable`, which goes to `StrategySwitch`
at l.154. This keeps the edit at two lines, away from the switcher (Phase 2) and the card markup
(Phase 3).

**Code (replace line 6):**
```ts
import { displayIcons, strategyIcon } from '@/components/roster';
```

**Code (replace line 33):**
```ts
  const [stored, run, user] = await Promise.all([leaderboard(), runStatus(now), currentUser()]);
  // R1: every card and switch button draws its own icon. A Claude twin's row stores its original's
  // icon (the engine copies it), so the unique one is resolved here from the whole board, once, and
  // everything below keeps reading `st.icon`.
  const icons = displayIcons(stored.rows.map(r => r.strategy));
  const board: Board = {
    ...stored,
    rows: stored.rows.map(r => ({ ...r, strategy: { ...r.strategy, icon: icons.get(r.strategy.id) ?? r.strategy.icon } })),
  };
```
**Impact:** `Board` is already imported (l.9). `compare`, `looks`, `buildChart` and `monthly` do
not read `icon`.

### Step 7: Positions and History rosters carry display icons

**File:** `web/app/(app)/positions/page.tsx:4`, `:32`
**Code (replace line 4):**
```ts
import { selectStrategy, sharesLabel, strategyIcon, withDisplayIcons } from '@/components/roster';
```
**Code (replace line 32):**
```ts
  const [stored, run] = await Promise.all([strategies(), runStatus(now)]);
  // R1: the switcher and the header pill draw the roster's unique icon, not the twin's copied one.
  const roster = withDisplayIcons(stored);
```

**File:** `web/app/(app)/history/page.tsx:10`, `:42`
**Code (replace line 10):**
```ts
import { sharesLabel, strategyIcon, withDisplayIcons } from '@/components/roster';
```
**Code (replace line 42):**
```ts
  // R1: the filter row and each trade's strategy tag draw the roster's unique icon.
  const roster = withDisplayIcons(await strategies());
```
**Impact:** `roster` keeps type `Strategy[]`. The switcher, `strat.icon` (positions l.62) and
`byId` (history l.132/154) all read display icons now.

### Step 8: Sean's plan draws the same icon

**File:** `web/app/sean/plan/page.tsx:3`, `:28-36`; `web/lib/sean/planData.ts:26`
**Change:** `linkableMethods()` and `link()` read `strategies.icon` themselves, and a book twin is
linkable (`engine = 'book'`). So the picker shows each pair with one icon. Fetch `strategies()`
next to them and swap in display icons. A followed method that has left the roster is not in
`strategies()`, so it keeps its stored icon. `LinkPicker.tsx` itself does not change: it renders
`m.icon`.

**Code (replace line 3):**
```ts
import { displayIcons, sharesLabel, strategyIcon } from '@/components/roster';
import { strategies } from '@/lib/data';
```

**Code (replace lines 28-36, the whole `load` function):**
```ts
async function load(): Promise<Loaded> {
  try {
    const [state, methods, roster] = await Promise.all([planState(), linkableMethods(), strategies()]);
    // R1: a Claude twin's row stores its original's icon. Draw the roster's unique one instead, the
    // same one the Leaderboard and Positions show. A method that has left the roster keeps its own.
    const icons = displayIcons(roster);
    const iconOf = (id: string, stored: string): string => icons.get(id) ?? stored;
    return {
      ok: true,
      state: state && { ...state, link: { ...state.link, icon: iconOf(state.link.strategyId, state.link.icon) } },
      methods: methods.map(m => ({ ...m, icon: iconOf(m.id, m.icon) })),
    };
  } catch (e) {
    console.error('sean plan read failed', e);
    return { ok: false };
  }
}
```

**Code (`web/lib/sean/planData.ts`, replace line 26):**
```ts
  /** strategies.icon as stored (a Lucide name). The plan page swaps in components/roster.ts displayIcons. */
```
**Impact:** Each `/sean/plan` visit runs one more read-only query. A failure lands in the existing
"Can't read the plan right now" branch.

### Step 9: Feature map

**File:** `.claude/skills/verify-seer/features/leaderboard.md`
**Change:** Edit four places.

(a) Sub-features, replace the line starting `- Claude twins (Seer Adversarial): a twin's card sits right after its original's, in the original's colour,`:
```markdown
- Claude twins (Seer Adversarial): a twin's card sits right after its original's, in its original's **partner** colour (F4 sky, F4+Claude teal), with an icon of its own (F4 gauge, F4+Claude rocket) and a `Paper` chip; its chart line is the partner colour with the twin dash (`3 3`). Every original keeps the colour it had before twins existed. The twin's checklist reads rule 5 as `Backtest gate · Can't be run`, with "Paper only. No backtest possible. Claude knows how the past turned out". Its name links to the original's Sera method page.
- Every strategy is unique on the board (R1): no two cards share a sheet, a chart line colour or an icon while there are at most twelve research strategies. Originals take lav, sky, sage, rose, plum, stone in roster order, then amber, orchid, berry, moss, teal, iris; a twin takes its original's partner (lav/iris, sky/teal, sage/moss, rose/berry, plum/orchid, stone/amber), or the first free sheet when an original holds it. Icons come from `displayIcons` in `web/components/roster.ts`: a twin draws its original's partner icon, a collision draws the next spare, and the same icon shows on Positions, History and Sean's plan.
```

(b) In "Driving it with verify.sh", replace the comment on the `leaderboard-twin.mjs` line:
```markdown
$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-twin.mjs   # order, partner colour, own icon, unique sheets and icons, dash, chip, rule 5; result: PASS
```

(c) Gotchas, replace `- The demo twin is built after every other demo row, so it moves none of the numbers above. Read the PNGs: F4 and F4+Claude are both sky; F1 sage and C rose, as before twins.` with:
```markdown
- The demo twin is built after every other demo row, so it moves none of the numbers above. Read the PNGs: A lav, F4 sky with a gauge, F4+Claude teal with a rocket, F1 sage and C rose. The originals look as they did before twins.
```

(d) Gotchas, replace `- A twin's legend swatch is dashed like a second-lap original's. Its label (`F4+Claude`) is what tells them apart.` with:
```markdown
- A twin's legend swatch is dashed (the twin dash) and in its own partner colour, so neither its colour nor its dash matches any original's line.
```
(Leave the desktop-ellipsis gotcha alone. Phase 3 owns the card layout and rewrites it.)

**File:** `.claude/skills/verify-seer/features/positions-history.md`
**Change:** In the first Sub-features bullet, replace `a Claude twin sits right after its original and carries the `Paper` label)` with:
```markdown
a Claude twin sits right after its original, carries the `Paper` label and draws its own icon, e.g. F4's gauge and F4+Claude's rocket, the same icons the Leaderboard shows)
```

### Step 10: Rewrite the twin UI step

**File:** `.claude/skills/verify-seer/features/steps/leaderboard-twin.mjs` (whole file)
**Change:** Assert the partner colour (`bg-teal`) and the twin's own icon (`svg.lucide-rocket` on
its card and its switch button, `svg.lucide-gauge` on F4's). Also assert that every card wears a
different sheet and every switch button a different icon, and that the chart has one solid sky line
and one `3 3` teal line. The checklist assertions stay. On pre-phase code this step fails at
`F4-MOM12-N20-TREND-CX card is not bg-teal`.

**Code:**
```js
// Seer Adversarial + R1 (leaderboard-desktop-revamp phase 1): F4's Claude twin sits right after F4
// in F4's PARTNER colour (sky -> teal) with the twin dash and an icon of its own (F4 gauge, the twin
// rocket), labelled Paper; A, F1 and C keep their colours; no two cards share a sheet and no two
// switch buttons share an icon; the twin's checklist says its backtest can't be run.
// Run on `up` demo data: `$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-twin.mjs`.
const F4 = 'F4-MOM12-N20-TREND';
const TWIN = 'F4-MOM12-N20-TREND-CX';
const card = id => `a[href="/leaderboard?s=${encodeURIComponent(id)}"][data-status]`;
const SHEETS = [
  'bg-sheet', 'bg-lav', 'bg-sky', 'bg-sage', 'bg-rose', 'bg-plum', 'bg-stone',
  'bg-amber', 'bg-orchid', 'bg-berry', 'bg-moss', 'bg-teal', 'bg-iris',
];

export default async ({ page, base, shot, log }) => {
  await page.goto(base + '/leaderboard', { waitUntil: 'networkidle' });
  const order = await page.locator('a[href^="/leaderboard?s="][data-status]').evaluateAll(
    els => els.map(e => decodeURIComponent(new URL(e.href).searchParams.get('s'))));
  const at = order.indexOf(F4);
  if (at < 0 || order[at + 1] !== TWIN) throw new Error(`twin is not right after F4: ${order.join(', ')}`);
  log(`card order: ${order.join(', ')}`);

  const cls = async id => (await page.locator(card(id)).first().getAttribute('class')) ?? '';
  const want = { A: 'bg-lav', [F4]: 'bg-sky', [TWIN]: 'bg-teal', 'F1-SPY-SMA200-M': 'bg-sage', C: 'bg-rose' };
  for (const [id, bg] of Object.entries(want)) {
    if (!(await cls(id)).split(/\s+/).includes(bg)) throw new Error(`${id} card is not ${bg}: ${await cls(id)}`);
  }
  log('colours: A lav, F4 sky, F4+Claude teal (its partner), F1 sage, C rose (originals unchanged by the twin)');

  const sheets = await page.locator('a[data-status], article[data-status]').evaluateAll(
    (els, list) => els.map(e => [...e.classList].find(c => list.includes(c)) ?? '(none)'), SHEETS);
  if (new Set(sheets).size !== sheets.length) throw new Error(`two cards share a sheet: ${sheets.join(', ')}`);
  log(`every card its own sheet: ${sheets.join(', ')}`);

  const strokes = async v => page.locator(`svg path[stroke="var(--${v}-line)"]`).evaluateAll(
    els => els.map(e => e.getAttribute('stroke-dasharray')));
  const sky = await strokes('sky'), teal = await strokes('teal');
  if (sky.length !== 1 || sky[0] !== null) throw new Error(`sky lines: ${JSON.stringify(sky)}`);
  if (teal.length !== 1 || teal[0] !== '3 3') throw new Error(`teal lines: ${JSON.stringify(teal)}`);
  log('chart: F4 one solid sky line, its twin one teal line dashed 3 3');

  const icons = async sel => page.locator(sel).evaluateAll(els => els.map(e =>
    [...e.classList].find(c => c.startsWith('lucide-')) ?? '(none)'));
  const iconsOf = async id => icons(`${card(id)} svg`);
  const f4Icons = await iconsOf(F4), twinIcons = await iconsOf(TWIN);
  if (!f4Icons.includes('lucide-gauge') || f4Icons.includes('lucide-rocket')) throw new Error(`F4 card icons: ${f4Icons}`);
  if (!twinIcons.includes('lucide-rocket') || twinIcons.includes('lucide-gauge')) throw new Error(`twin card icons: ${twinIcons}`);
  log('cards: F4 draws a gauge, F4+Claude a rocket');

  const switchIcons = await icons('nav[aria-label="Strategy"] a svg');
  if (switchIcons.length < 2 || new Set(switchIcons).size !== switchIcons.length)
    throw new Error(`switch icons repeat: ${switchIcons.join(', ')}`);
  if ((await page.locator(`nav[aria-label="Strategy"] a[href="/leaderboard?s=${TWIN}"] svg.lucide-rocket`).count()) !== 1)
    throw new Error('the twin switch button does not draw a rocket');
  log(`switch: every button its own icon: ${switchIcons.join(', ')}`);

  const chip = page.locator(card(TWIN)).getByText('Paper', { exact: true });
  await chip.first().waitFor();
  if ((await page.locator(card(F4)).getByText('Paper', { exact: true }).count()) !== 0)
    throw new Error('the original carries a Paper chip; only twins do');
  log('Paper chip on the twin card only');
  await shot('board');

  await page.locator(card(TWIN)).first().click();
  await page.waitForURL(u => u.searchParams.get('s') === TWIN);
  await page.getByText("Can't be run").first().waitFor();
  await page.getByText('Paper only. No backtest possible.').first().waitFor();
  await page.getByText('Claude knows how the past turned out').first().waitFor();
  await shot('twin-checklist');
  log("picking the twin: checklist rule 5 reads Backtest gate · Can't be run, with the reason");
};
```
**Impact:** The step depends on the hrefs and `data-status` attributes of the card links and on
the `nav[aria-label="Strategy"]` switcher. Phase 3 keeps both and replaces only the twin-click line
(see Handoffs).

## Principles applied

- Laziness protocol: icons are resolved on the web from the roster, with no engine change and no
  migration. Each consumer edit is one line that rebuilds the roster or board rows with display
  icons, so `StrategySwitch`, `card()` and `LinkPicker` keep their code and their props.
- Make illegal states unrepresentable: `looks()` counts only originals when assigning slots,
  and twins claim afterwards. So "a twin moved an original's colour" cannot be built at all,
  rather than being checked for. Unknown icon names are normalised to the Sigma they draw before
  the uniqueness check, so two rows that look identical can never pass as different names.
- Build the lever: the palette's correctness (each token in both themes, line contrast at least
  3:1, butter excluded) can't be judged by eye in a diff. A test reads `globals.css` and computes
  it. A loop over every palette size and twin placement replaces a few hand-picked cases.
- Prove it works: the Proof section drives the real page with verify-seer (the rewritten twin
  step, screenshots) and the real board with `npm run shoot`, not only vitest.
- Test behavior, not implementation: the tests assert the looks and icon names a caller receives
  and the Lucide component they draw. The verify step asserts classes on the rendered DOM. Nothing
  inspects private helpers.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/leaderboard-desktop-revamp/web && npx tsc --noEmit`
**Tests:** `cd /home/miftah/.worktrees/seer/leaderboard-desktop-revamp/web && npm test`
(Targeted while iterating: `npx vitest run 'app/(app)/leaderboard/view.test.ts' components/roster.test.ts`.)
**Proof:**
- Harness: `.claude/skills/verify-seer` (`scripts/verify.sh`), plus `web/scripts/shoot.mjs` (the
  `run-the-web-app` skill) for the real board, which has three twins. The demo seed has one.
- Feature-map entries: `.claude/skills/verify-seer/features/leaderboard.md`,
  `.claude/skills/verify-seer/features/positions-history.md`, `.claude/skills/verify-seer/features/sean.md` (neighbour)
- Journeys (`V=.claude/skills/verify-seer/scripts/verify.sh`; every `RUN` is the id `up` prints):
  0. **Fails before the change.** From the main checkout (base `22d1051`, without this phase):
     `cd /home/miftah/seer && $V up` then
     `$V ui RUN /home/miftah/.worktrees/seer/leaderboard-desktop-revamp/.claude/skills/verify-seer/features/steps/leaderboard-twin.mjs`.
     Passes the journey when the step FAILS with `F4-MOM12-N20-TREND-CX card is not bg-teal`. Then
     `$V down RUN`. (`up` snapshots `web/` and never writes the main checkout.)
  1. **Partner colour and own icon, desktop.** From the worktree after the change:
     `cd /home/miftah/.worktrees/seer/leaderboard-desktop-revamp && $V up`,
     `$V doctor RUN`, then `$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-twin.mjs`.
     Passes when it reports PASS and the log has these lines: `colours: A lav, F4 sky, F4+Claude teal …`,
     `every card its own sheet: …` with six different classes, `chart: F4 one solid sky line, its twin one teal line dashed 3 3`,
     `cards: F4 draws a gauge, F4+Claude a rocket`, and `switch: every button its own icon: …`.
  2. **Same on a phone, light theme:** `$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-twin.mjs --width 390 --theme light`.
     Passes when it reports PASS. This also proves the mobile layout has no horizontal scroll (`ui` fails on scroll).
  3. **Positions and History draw the twin's own icon.**
     `$V api RUN GET '/positions?s=F4-MOM12-N20-TREND-CX'` and `$V api RUN GET /history`. Then, for each
     saved page: `f=$(ls -t ~/.local/state/seer-verify/RUN/evidence/*-api-*.html | head -1)` (run it
     right after each `api` call). Next, `grep -o 'lucide-rocket' "$f" | wc -l` and `grep -o 'lucide-gauge' "$f" | wc -l`.
     Passes when both counts are ≥ 1 on both pages: the twin's switch button draws a rocket and F4's
     draws a gauge. On Positions the header pill also draws the rocket.
  4. **Screenshots, read them.**
     `$V shoot RUN --theme light --width 1440 /leaderboard`, `$V shoot RUN --theme dark --width 1440 /leaderboard`,
     `$V shoot RUN --theme dark --width 390 /leaderboard '/leaderboard?s=F4-MOM12-N20-TREND-CX'`.
     Passes when the exit is 0 and the PNGs (`evidence/NN-shoot-*/`) show six cards: SPY plain,
     A lav, F4 sky with a gauge, F4+Claude teal with a rocket, F1 sage and C rose. The checklist
     switch must show five different icons. In dark mode the teal card must be a visible dark teal
     and not the plain sheet.
  5. **Sean's plan still renders with the extra roster read.** `$V api RUN GET /sean/plan`.
     Passes when the text contains `Following F4` and the saved HTML contains `lucide-gauge` (F4's icon).
  6. **The real board (three twins).** This reads the real DB and writes nothing. Run it in the
     worktree's `web/`, with `node_modules` hard-linked (setup above) and
     `SEER_ENV_FILE=/home/miftah/seer/.env.local`: `npm run dev:env &`, then
     `npm run shoot -- --theme light --width 1440 /leaderboard` and
     `npm run shoot -- --theme dark --width 1440 /leaderboard`. Read
     `web/.shots/leaderboard__light__1440.png` and `__dark__1440.png`. Passes when every live card
     (eight, per the analysis's screenshot, but count them) has a different sheet and a different
     icon. Each twin must sit in its original's partner colour: COSK+Claude a tornado, RAW35+Claude a
     flame, A+Claude a pi. A `PROBLEMS: horizontal scroll` line at 1440 is the known 8 px card-row
     overflow that Phase 3 owns. It does not fail this journey, because the PNG is written before
     that check (shoot.mjs l.101 vs l.105).
- Neighbor check: the History trades list (each trade's strategy tag icon) and the Positions
  switcher are the features most likely to break. Journey 3 covers them. Also run
  `$V shoot RUN --theme light --width 1280 /positions /history` and pass when the exit is 0.
- Cost: no paid drives. All journeys are offline (`MODE=offline`, LLM budget 0).

**Exit criteria:** Both `npx tsc --noEmit` and `npm test` in `web/` pass. On pre-phase code the
twin step fails with `card is not bg-teal`, and on this phase's code it passes at 1280 dark and
390 light. Positions and History serve `lucide-rocket` for the twin and `lucide-gauge` for F4. The
real board's 1440 screenshots show every live card with its own sheet and its own icon.

## Handoffs

- **Phase 2 (R2):** `StrategySwitch` needs no prop change. Every caller now passes display icon
  names (leaderboard via the rebuilt `board`, positions and history via `withDisplayIcons`). This
  phase does not touch the checklist `StrategySwitch` call (line 154 at base; line 162-163 after this
  phase's 9-line `board` block at line 33), where Phase 2 adds `fit`.
- **Phase 3 (R3):**
  - Each family's stack can find its twin with `attachedOriginal` (`lib/strategy.ts`). Twins already
    carry their partner `look.bg`/`look.tint` from `looks()` and their own `st.icon` from the
    rebuilt `board`, so `card()` needs no colour or icon logic.
  - Phase 3 keeps the `a[href="/leaderboard?s=<id>"][data-status]` links (and `article[data-status]`
    for SPY) and `nav[aria-label="Strategy"]` that `features/steps/leaderboard-twin.mjs` asserts on.
    Phase 3 then edits that file's one twin-click line (reconciled) so the click lands on the peeking
    edge of a tucked twin at desktop width; `card()`'s icon line stays `strategyIcon(st.icon)`.
  - The desktop-ellipsis gotcha in `leaderboard.md` is Phase 3's to rewrite.
  - The `PROBLEMS: horizontal scroll` at 1440 on the real board is Phase 3's.
- **Out of the plan set (no phase):** the engine still copies the original's `icon` onto each twin
  row (`engine/src/seer_engine/paper/store.py` `ensure_twins`). That is harmless now that the web
  resolves display icons. A stored per-twin icon would need an engine change and a migration, and
  is not needed for R1.

## Rollback

Revert this phase's commit. No data, schema or engine state changes, so nothing has to be undone
outside git. After the revert the twin is sky with the `3 3` dash and draws its original's icon
again. The old `leaderboard-twin.mjs` returns with the commit, so the feature map and the code stay
consistent.
