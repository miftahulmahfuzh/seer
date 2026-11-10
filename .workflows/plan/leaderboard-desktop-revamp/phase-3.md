# Phase 3: Desktop card stacks

**Plan set:** `LEADERBOARD_DESKTOP_REVAMP_PLAN.md`
**Analysis:** `.workflows/analyze/20261110-090235-LB7D_code_analyzer.md`
**Satisfies:** R3 — the desktop live row becomes one stack (deck) per method family, and clicking a card pops its stack forward in its own slot
**Depends on:** Phase 1, 2
**Difficulty:** HARD
**Package:** `web`

---

## Goal

At 1024 px and wider, the live card row on `/leaderboard` is one deck per family: SPY alone, each
original on top with its Claude twin tucked behind it, so the twin's edge and colour show above and
to the right. The deck holding the pick is open. It fans the twin out beside the original at full
card width and pops forward in its own slot (raised, slightly larger, shadowed, on top), and the
picked card is still the tab into the month-by-month sheet. Codes show whole, chips stay inside
their cards, the chart legend is one row, "No common window yet" appears once, and the page has no
horizontal scroll at 1280 or 1440. Below 1024 px nothing moves.

## Interface Contract

**Deletes:** CSS rule `.cardActive:first-child::before, .cardActive:last-child::after { display: none; }` (`leaderboard.module.css:206`). It is replaced in place by a `data-edge` version, because inside a deck `:first-child`/`:last-child` mean "first in the deck", not "first in the row".
**Renames:** none
**Creates:**
- `stacks<R extends { strategy: RosterIn }>(rows: R[]): R[][]` (`web/app/(app)/leaderboard/view.ts`, after `researchOf`) plus `describe('stacks')` in `view.test.ts`
- page-local `deck(rows)` (inside `Leaderboard`) and module-level `breakable(code)` (`page.tsx`)
- CSS module classes `.deck`, `.peek`, `.legendLabel` (`leaderboard.module.css`)
- DOM attributes `data-deck="<original id>"` and `data-open` on each deck, `data-edge="first|last"` on the tab card
- `.claude/skills/verify-seer/features/steps/leaderboard-stack.mjs` (new UI journey)

**Signature changes:** page-local `card(row, tab)` -> `card(row, tab, place?: { depth: number; open: boolean })`. Retired-shelf callers keep `card(r, false)`. The `cols` value page.tsx passes to `RetiredShelf` changes from `live.length` to `rowCols` (the live row's grid column count); `RetiredShelf`'s props are unchanged.
**Requires (from earlier phases):**
- Phase 1: `card()`'s icon line is unchanged by Phase 1 and still reads `const Icon = strategyIcon(st.icon);`. Phase 1 rebuilds `board` right after the data load (line 33 became the 9-line `stored`/`displayIcons`/`board` block), so every row's `st.icon` is already the unique display icon; `card()` needs no icon logic. Phase 1 changed `page.tsx` line 6 to `import { displayIcons, strategyIcon } from '@/components/roster';`.
- Phase 1: `looks()` gives every card its own `bg`/`tint` (a twin gets its partner tint), so a tucked twin's peeking edge shows a different colour from the original on top. This plan only reads `look.bg`/`look.tint`.
- Phase 1: the `./view` import list in `page.tsx` (lines 17-21) is unchanged by Phase 1. The `./view` import list in `view.test.ts` was rewritten by Phase 1 (adds `CARD_BGS`, `PALETTE_SIZE`, `PARTNER_BGS`, `SLOT_BGS`); Step 2 quotes it.
- Phase 1: `leaderboard-twin.mjs` is Phase 1's rewrite (it clicks the twin with `await page.locator(card(TWIN)).first().click();`), and `leaderboard.md` is as Phases 1 and 2 leave it; Steps 9 and 10 quote both.
- Phase 2: `fit` is passed on the `StrategySwitch` call in the checklist sheet, and `.switch` (CSS line 45) is phase 2's rule. Neither is edited here, and nothing here changes `.top`'s 380px checklist column that Phase 2's fit grid divides.

**Line numbers.** `page.tsx` numbers below are as Phases 1 and 2 leave the file: base `22d1051` plus 8 for every line after 33. `view.ts` and `view.test.ts` are found by anchor text, since Phase 1 rewrote large blocks above them. Earlier steps of this phase shift later ones, so find each block by its quoted text.

**Leaves alone (owned by others):** `globals.css`, `looks()` and its tests, `components/roster.ts`, `components/StrategySwitch.*`, `.switch` (Phases 1-2). `RetiredShelf.tsx` itself (its markup, props and CSS). Every mobile (< 1024 px) rule. `compare`, `checklist`, `scoreOf`.
**Edits after a peer (owned here from this phase on):** `.claude/skills/verify-seer/features/steps/leaderboard-twin.mjs` as Phase 1 rewrote it: its twin click must hit the peeking edge, because at desktop width the twin is tucked behind its original (Step 9). `features/leaderboard.md` as Phases 1 and 2 leave it: this phase adds the stack lines and replaces the "ellipsises to `F4+…`" gotcha (Step 10), which Phase 1 left for it. The twin bullet's colour sentence is Phase 1's and is not touched here.

## Files

| File | Action | What changes |
|---|---|---|
| `web/app/(app)/leaderboard/view.ts` | modify | add `stacks()` directly after the `export const researchOf` line (line 123 at base, ~183 after Phase 1) |
| `web/app/(app)/leaderboard/view.test.ts` | modify | import list as Phase 1 left it + `stacks`; add `describe('stacks')` after `describe('researchOf')` closes |
| `web/app/(app)/leaderboard/page.tsx` | modify | `./view` import (17-21), `second.desk` (102-108), deck/tab-edge block (183-186), card row and `RetiredShelf` `cols` (224, 226), `deck()` + `card()` (235-304), `breakable` (new, before `MonthRow` at 307), `Legend` (328-350). Line numbers as Phases 1-2 leave the file |
| `web/app/(app)/leaderboard/leaderboard.module.css` | modify | `.deck`/`.peek` base (after 78), fillet rule (206), new desktop block + reduced-motion + container rule (after 219 / end of file) |
| `.claude/skills/verify-seer/features/steps/leaderboard-stack.mjs` | create | geometry journey for decks, peek, open/pop, tab edge, legend row, reduced motion |
| `.claude/skills/verify-seer/features/steps/leaderboard-twin.mjs` | modify | twin click lands on the peeking edge at desktop width |
| `.claude/skills/verify-seer/features/leaderboard.md` | modify | stack sub-feature, journeys, gotcha |

## Implementation Steps

### Step 0: Reproduce the three desktop defects before touching code
**File:** none (evidence only)
**Change:** Fixing a root cause starts with seeing it. On the tree as Phases 1 and 2 left it, reproduce the defects against the real roster (8 live cards, 3 twins). This reads Neon and never writes. Record the output in the commit body.
```sh
cd /home/miftah/.worktrees/seer/leaderboard-desktop-revamp/web
[ -e node_modules ] || cp -al /home/miftah/seer/web/node_modules node_modules   # hardlink, never a symlink
export SEER_ENV_FILE=/home/miftah/seer/.env.local
node scripts/with-env.mjs npx next dev -p 3121     # run in the background; port 3111 may be the owner's
npm run shoot -- --base http://localhost:3121 --theme light --width 1440 /leaderboard   # signs in; expect a PROBLEMS line: horizontal scroll ~8px
```
Write `web/.shots/overflow.mjs` (`.shots/` is git-ignored, and the script must live under `web/` so `playwright` resolves):
```js
// Which elements stick out past the viewport's right edge? node .shots/overflow.mjs <url> <width>
import { chromium } from 'playwright';
const [url, width] = process.argv.slice(2);
const browser = await chromium.launch();
const ctx = await browser.newContext({ storageState: '.auth/state.json', viewport: { width: Number(width), height: 900 } });
const page = await ctx.newPage();
await page.goto(url, { waitUntil: 'networkidle' });
await page.waitForTimeout(800);
const out = await page.evaluate(() => {
  const vw = document.documentElement.clientWidth;
  const culprits = [...document.querySelectorAll('body *')]
    .map(e => [e, e.getBoundingClientRect()])
    .filter(([, r]) => r.width > 0 && r.right > vw + 0.5)
    .map(([e, r]) => `${e.tagName.toLowerCase()}.${String(e.className).trim().split(/\s+/).join('.')} right=${Math.round(r.right)} text=${(e.textContent ?? '').trim().slice(0, 24)}`);
  const legend = [...document.querySelectorAll('[class*="legendItem"]')].filter(e => e.offsetParent)
    .map(e => Math.round(e.getBoundingClientRect().top));
  return { overflowPx: document.documentElement.scrollWidth - vw, culprits: culprits.slice(0, 15), legendRows: new Set(legend).size,
    noWindowCount: (document.body.innerText.match(/No common window yet/g) ?? []).length };
});
console.log(JSON.stringify(out, null, 1));
await browser.close();
```
```sh
node .shots/overflow.mjs http://localhost:3121/leaderboard 1440
node .shots/overflow.mjs http://localhost:3121/leaderboard 1280
```
**Expected before the fix:** `overflowPx` > 0 at 1440, `legendRows` 2, `noWindowCount` 2 (if the real board has no common window yet). The culprit list names the element that overflows. The hypothesis is the last card's `.chips` (`flex: none`, line 86) or its `.name`, pushed past the card's right edge in an 8-column row. If the culprit is in the card row or the legend, Steps 4 and 6 remove it. If it is the switch (`.switch`/StrategySwitch, Phase 2), do not fix it here: record it in Handoffs as a Phase 2 regression and report it.
**Root causes already traced in the code:**
- Duplicate line: `page.tsx:98` sets `second.desk` to `wline.label` when nothing is ranked, and `page.tsx:132` prints `wline.label` again in the window row.
- Two-row legend: `.legend { flex-wrap: wrap }` (`leaderboard.module.css:19`) inside the desktop `.headline` (`:7`), which shares one line with the stats.
- Truncated codes: `.nameText` ellipsis (`:83`) plus `.name { max-width: 100% }` (`:178`) in a 1/8-width column.
**Impact:** none (read only).

### Step 1: `stacks()` — the pure grouping
**File:** `web/app/(app)/leaderboard/view.ts` (insert directly after the line `export const researchOf = <T extends RosterIn>(roster: T[]): T[] => roster.filter(st => !st.isBenchmark);`, line 123 at base and about 183 after Phase 1's `looks()` rewrite)
**Change:** Add the grouping helper. It reuses `attachedOriginal` (already imported at line 19) and the same "not behind the benchmark" rule `looks()` applies.
**Code:**
```ts
/**
 * The desktop card row as decks (owner, 2026-11-10: "a stack of cards ... active card will make
 * the cards pop forward, but still stay in place"). Each deck is one family: a strategy, then every
 * Claude twin attached to it (`attachedOriginal`), twins in the order `rows` gives them. A deck
 * sits where its original sits in `rows`, so the row keeps the board's order whatever order the
 * twins arrive in. The benchmark always stands alone, and so does a twin whose original is not in
 * `rows` (retired, so off the live row) or is the benchmark: the same two cases `looks` colours as
 * a plain strategy. Every row lands in exactly one deck.
 *
 * Pure grouping: which deck is open is not decided here. Open means "holds the pick", and the page
 * derives it from the pick, so a deck can never be open without holding it.
 */
export function stacks<R extends { strategy: RosterIn }>(rows: R[]): R[][] {
  const byId = new Map(rows.map(r => [r.strategy.id, r.strategy]));
  const originalOf = (st: RosterIn): RosterIn | null => {
    const o = attachedOriginal(st, byId);
    return o && !o.isBenchmark ? o : null;
  };
  const decks: R[][] = [];
  const deckOf = new Map<string, R[]>();
  for (const r of rows) {
    if (originalOf(r.strategy)) continue;
    const deck = [r];
    decks.push(deck);
    deckOf.set(r.strategy.id, deck);
  }
  // `originalOf` only returns a row of `rows` that is neither a twin nor the benchmark, and every
  // such row opened a deck in the loop above, so the lookup cannot miss.
  for (const r of rows) {
    const o = originalOf(r.strategy);
    if (o) deckOf.get(o.id)!.push(r);
  }
  return decks;
}
```
**Impact:** new export only. Nothing calls it until Step 3.

### Step 2: Tests for `stacks()`
**File:** `web/app/(app)/leaderboard/view.test.ts`. Phase 1 replaced the import block (now lines 4-11). Replace it with this, which is Phase 1's list plus `stacks`:
```ts
import {
  CARD_BGS, CHECKS, compare, LOOK_PERIOD, looks, MIN_COMMON_SESSIONS, MIN_RANKED, monthLabel, monthLines,
  NO_GATE, PALETTE_SIZE, PARTNER_BGS, pickResearch, researchOf, retiredLabel, scoreOf, sinceStartLine,
  SLOT_BGS, spyOverSpan, stacks, TWIN_DASHES, twinChipTip, windowLine, type GateIn, type RankIn, type RosterIn,
} from './view';
```
Insert the block below right after `describe('researchOf', …)` closes (before the `// --- the common-window comparison` comment and `describe('compare'`). Phase 1 added a module-level `twinOf(o)` helper in this file, so the local row builder names its parameter `of` rather than shadowing it.
**Code:**
```ts
describe('stacks', () => {
  const row = (id: string, of: string | null = null, isBenchmark = false) =>
    ({ strategy: { id, isChampion: isBenchmark, isBenchmark, twinOf: of } satisfies RosterIn });
  const ids = (decks: { strategy: RosterIn }[][]) => decks.map(d => d.map(r => r.strategy.id));

  it('puts each twin behind its original and leaves SPY and plain strategies alone, in board order', () => {
    const rows = [
      row('SPY', null, true), row('C'), row('COSK'), row('COSK-CX', 'COSK'),
      row('RAW35'), row('RAW35-CX', 'RAW35'), row('A'), row('A-CX', 'A'),
    ];
    expect(ids(stacks(rows))).toEqual([['SPY'], ['C'], ['COSK', 'COSK-CX'], ['RAW35', 'RAW35-CX'], ['A', 'A-CX']]);
  });

  it("files a twin listed before its original into the original's deck, at the original's place", () => {
    expect(ids(stacks([row('SPY', null, true), row('A-CX', 'A'), row('C'), row('A')])))
      .toEqual([['SPY'], ['C'], ['A', 'A-CX']]);
  });

  it('lets a twin whose original is off the row stand alone where it is', () => {
    expect(ids(stacks([row('SPY', null, true), row('A-CX', 'A'), row('C')])))
      .toEqual([['SPY'], ['A-CX'], ['C']]);
  });

  it('never tucks anything behind the benchmark', () => {
    expect(ids(stacks([row('SPY', null, true), row('SPY-CX', 'SPY')]))).toEqual([['SPY'], ['SPY-CX']]);
  });

  it("keeps two twins of one original in the board's order", () => {
    expect(ids(stacks([row('A'), row('A-CX2', 'A'), row('A-CX1', 'A')]))).toEqual([['A', 'A-CX2', 'A-CX1']]);
  });

  it('places every row in exactly one deck and returns the rows themselves', () => {
    const rows = [row('SPY', null, true), row('F4'), row('F4-CX', 'F4'), row('F1'), row('C'), row('X-CX', 'X')];
    const decks = stacks(rows);
    expect(decks.flat()).toHaveLength(rows.length);
    expect(new Set(decks.flat())).toEqual(new Set(rows));
  });

  it('returns no decks for an empty row', () => {
    expect(stacks([])).toEqual([]);
  });
});
```
**Impact:** about 7 more tests. Check with `cd web && npx vitest run 'app/(app)/leaderboard/view.test.ts'`.

### Step 3: Page — import, the duplicate line, decks and the tab edge
**File:** `web/app/(app)/leaderboard/page.tsx`

3a. **Import (lines 17-21).** Add `stacks`. Phase 1 does not change this block (it edits only line 6, the `@/components/roster` import, which now reads `import { displayIcons, strategyIcon } from '@/components/roster';` and stays as is). After this step the block reads:
```ts
import {
  BENCHMARK_DASH, compare, LOOK_FALLBACK, looks, MIN_COMMON_SESSIONS, monthLines, NO_GATE, pickResearch,
  researchOf, retiredLabel, scoreOf, sinceStartLine, spyOverSpan, stacks, twinChipTip, windowLine,
  type CompareRow, type Look, type MonthLine,
} from './view';
```

3b. **`second` (lines 102-108).** This is the root cause of "No common window yet" printing twice: `desk` fell back to `wline.label`, which the window row prints again two lines down.
```ts
  const second = champ?.strategy.isBenchmark
    ? {
        value: best ? ret(best.totalReturn) : '—',
        mobile: best ? `Best · ${best.strategy.short}` : 'Not ranked',
        // With nothing ranked, the window row right under the headline already says "No common
        // window yet" and how far off one is; repeating it here printed it twice on desktop.
        desk: best ? `${best.strategy.name}, best over the common window` : 'Not ranked',
      }
    : { value: ret(spyRet), mobile: 'SPY', desk: 'SPY' };
```

3c. **Decks, tab edge and the row's column count (lines 183-186, replace the comment and the two `ids`/`tabEdge` lines).**
```ts
  // Desktop: the live row is one deck per family (`stacks`), an original with its Claude twin
  // tucked behind it. The picked card drops into this sheet as a tab, and at either end of the row
  // the tab meets the sheet's own rounded corner, which has to square off for the two to read as
  // one surface. The row's leftmost card is always the first deck's top card. The deck holding the
  // pick is always open (its cards side by side), so when the pick sits in the last deck,
  // `decks.flat().at(-1)` is the rightmost card on screen.
  const decks = stacks(live);
  const ids = decks.flat().map(r => r.strategy.id);
  const tabEdge = !pick ? undefined : ids[0] === pick.id ? 'first' : ids.at(-1) === pick.id ? 'last' : undefined;
  // A deck is open when it holds the pick, so "open" can never be stored apart from the pick.
  const isOpen = (rows: Board['rows']) => rows.some(r => r.strategy.id === pick?.id);
  // The retired shelf keeps the live row's column width (`RetiredShelf`'s `cols`). The row is no
  // longer one column per card: it is one per deck, and the open deck spans one per card.
  const rowCols = decks.reduce((n, d) => n + (isOpen(d) ? d.length : 1), 0);
```

3d. **The card row and the shelf's columns (lines 224 and 226).** Replace
`<div className={s.cards}>{live.map(r => card(r, true))}</div>` with
```tsx
        <div className={s.cards}>{decks.map(d => deck(d))}</div>
```
and in the `RetiredShelf` call two lines below, replace `cols={live.length}` with `cols={rowCols}`. Leave the rest of that call as it is (`count`, `open`, `card(r, false)`). The shelf's own layout does not change: it still takes the live row's column width, which is what `cols` has always meant.
**Impact:** the DOM order of live cards is unchanged (`orderTwins` already puts each twin right after its original), so mobile reads the same sequence.

### Step 4: Page — `deck()` and `card()`
**File:** `web/app/(app)/leaderboard/page.tsx:235-304` (as Phases 1-2 leave it). Replace the whole `card` function (its doc comment through its closing brace) with the two functions below. The `const Icon = strategyIcon(st.icon);` line is unchanged from base: Phase 1 made `st.icon` the display icon upstream.
**Code:**
```tsx
  /**
   * One family on the desktop row: the original on top, its Claude twin tucked behind it with its
   * edge and colour peeking out above and to the right. The deck holding the pick is open. It takes
   * one column per card, fans the twin out beside the original and pops forward in its own slot,
   * so every other deck keeps its place. "Open" is derived from the pick and never stored, so a deck
   * cannot be open without holding it. Below 1024px the deck is `display: contents` and its cards
   * fall back into the mobile column exactly as before. CSS alone moves the cards: the deck and
   * card keys are stable ids, so React keeps the same elements across a pick and their transform
   * transitions run with no client component.
   */
  function deck(rows: Board['rows']) {
    const open = isOpen(rows);
    return (
      <div key={rows[0].strategy.id} className={s.deck} data-deck={rows[0].strategy.id}
        data-open={open ? '' : undefined} style={{ '--n': rows.length } as CSSProperties}>
        {rows.map((r, depth) => card(r, true, { depth, open }))}
      </div>
    );
  }

  /**
   * One strategy's card. `tab`: the picked live card becomes the tab into the month-by-month sheet
   * right under the live row (desktop); a retired card sits on the shelf below that sheet, so when
   * it is the pick it is marked as picked instead of pretending to be attached to it.
   * `place`: a live card's position in its deck. A twin behind a closed deck shows only its edge on
   * desktop, so it carries its name as its accessible name, and as the tooltip of the edge.
   */
  function card({ strategy: st, metrics: m }: Board['rows'][number], tab: boolean, place?: { depth: number; open: boolean }) {
    const Icon = strategyIcon(st.icon); // st.icon is already the unique display icon (Phase 1's `board`).
    const look = lookOf(st.id);
    const dash = (v: string) => (st.isBenchmark ? '—' : v);
    const cr = cmpOf(st.id);
    const retired = st.status === 'retired';
    const active = st.id === pick?.id;
    const tucked = place !== undefined && place.depth > 0 && !place.open;
    // Desktop shows the code; the full name and the one-line description live in this tip.
    const tip = `${st.name}\n${st.sub}`;
    const body = (
      <>
        {/* Desktop, a tucked twin: the strip that peeks out from behind the deck is its whole
            clickable face, so the strip carries the name. Never rendered on an open deck. */}
        {tucked && <span className={s.peek} data-tip={st.name} aria-hidden="true" />}
        <div className={s.cardHead}>
          <div className={s.cardName}>
            <div className={s.titleRow}>
              {/* Mobile: one row, the name gives way (ellipsis) before the chips wrap under it.
                  Desktop: the whole code (a twin's breaks after its '+'), with the chips on their
                  own line below. */}
              <span className={s.name} data-tip={tip}>
                <span className={`${s.nameText} mobile-only`}>{st.name}</span>
                <span className={`${s.nameText} desk-only`}>{breakable(st.short)}</span>
                {st.isChampion && <span data-tip="Champion" aria-label="Champion" role="img" className={`${s.crown} mobile-only`}><Crown size={20} /></span>}
              </span>
              {/* Desktop: the status line under the code — champion, Claude twin (Paper), retired, not ranked. */}
              <span className={s.chips}>
                {st.isChampion && <span data-tip="Champion" aria-label="Champion" role="img" className={`${s.crown} desk-only`}><Crown size={20} /></span>}
                {st.twinOf !== null && <PaperChip size="sm" tip={twinChipTip(shortOf.get(st.twinOf) ?? null)} />}
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
            </div>
            <span className={s.cardSub}>{st.sub}</span>
          </div>
          <span className={s.icon} data-tip={tip}><Icon size={22} strokeWidth={1.6} /></span>
        </div>
        <div className={s.metrics}>
          <div className={s.metric}><span className={`num ${s.ret} ${tone(m.totalReturn)}`}>{ret(m.totalReturn)}</span><span className={s.mLabel}><span className="mobile-only">Return</span><span className="desk-only">Total return</span></span></div>
          <div className={s.metric}><span className="num">{dash(m.winRate === null ? '—' : Math.round(m.winRate * 100) + '%')}</span><span className={s.mLabel}>Win rate</span></div>
          <div className={s.metric}><span className="num">{dash(m.profitFactor === null ? '—' : m.profitFactor === Infinity ? '∞' : m.profitFactor.toFixed(2))}</span><span className={s.mLabel}><span className="mobile-only">Profit f.</span><span className="desk-only">Profit factor</span></span></div>
          <div className={s.metric}><span className="num">{m.maxDrawdown === null ? '—' : (m.maxDrawdown * 100).toFixed(1) + '%'}</span><span className={s.mLabel}><span className="mobile-only">Max DD</span><span className="desk-only">Max drawdown</span></span></div>
          <div className={s.metric}><span className="num">{dash(String(m.trades))}</span><span className={s.mLabel}>Trades</span></div>
        </div>
      </>
    );
    const picked = active ? ` ${tab ? s.cardActive : s.cardPicked}` : '';
    const cls = `sheet ${tab ? 'over ' : ''}${look.bg} ${s.card}${picked}`;
    const style = (place ? { '--tint': look.tint, '--depth': place.depth } : { '--tint': look.tint }) as CSSProperties;
    // Which end of the row the tab sits at, if any: there the sheet's corner squares off instead
    // of the tab drawing a fillet past the row's edge.
    const edge = active && tab ? tabEdge : undefined;
    // SPY is in every month row already, so only research cards pick the month-by-month sheet.
    return st.isBenchmark ? (
      <article key={st.id} data-status={cr?.status ?? 'benchmark'} className={cls} style={style}>{body}</article>
    ) : (
      <Link key={st.id} href={`/leaderboard?s=${encodeURIComponent(st.id)}`} scroll={false}
        data-status={cr?.status ?? 'benchmark'} data-edge={edge} aria-current={active ? 'true' : undefined}
        aria-label={tucked ? st.name : undefined}
        className={`${cls} ${s.cardLink}`} style={style}>{body}</Link>
    );
  }
```
**Impact:**
- Retired cards (`card(r, false)`): `place` is undefined, so `tucked` is false, there is no `--depth`, and they look the same as before.
- Mobile: the peek span is `display: none` below 1024 px, and `<wbr>` sits inside a `desk-only` span. The `aria-label` on a tucked twin is the only mobile-visible markup change, and it affects screen readers only: the accessible name becomes the twin's name instead of all its text.
- The `.cardActive` tab now carries `data-edge`, which Step 6 uses.

### Step 5: Page — `breakable()` and the legend label
**File:** `web/app/(app)/leaderboard/page.tsx`. Insert `breakable` at module level, directly above `function MonthRow` (line 307 as Phases 1-2 leave it, before this phase's Step 4 grows `card()`). Replace `Legend` (lines 328-350 before Step 4) whole.
**Code:**
```tsx
/** A twin's code may break after its '+' ('RAW35+' / 'Claude') rather than mid-word in a narrow card. */
function breakable(code: string) {
  const at = code.indexOf('+');
  return at < 0 ? code : <>{code.slice(0, at + 1)}<wbr />{code.slice(at + 1)}</>;
}
```
```tsx
/**
 * One swatch + short label per strategy (full name as its tooltip). On desktop it is one row: it
 * sits beside the headline figures when it fits and drops under them when it does not. Past about
 * a dozen strategies its codes ellipsise rather than wrap (`.legendLabel`). On mobile it is the
 * wrapping row under the axis.
 */
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
            {look.dash
              ? <span className={s.swatchDash} style={{ borderTopColor: look.line, borderTopStyle: look.dash === BENCHMARK_DASH ? 'dotted' : 'dashed' }} />
              : <span className={s.swatch} style={{ background: look.line }} />}
            <span className={s.legendLabel}>{st.short}</span>
          </span>
        );
      })}
    </div>
  );
}
```
**Impact:** `.legendLabel` has no rule below 1024 px, so the mobile legend renders as before.

### Step 6: CSS — base rules and the fillet rule
**File:** `web/app/(app)/leaderboard/leaderboard.module.css`

6a. Insert directly after `.cards { display: contents; }` (line 78):
```css
/* The desktop row is decks (`deck()` in page.tsx). Below 1024px a deck is `display: contents`, so
   its cards are the mobile column's own stacked sheets exactly as before, and the peek strip of a
   tucked twin does not exist. */
.deck { display: contents; }
.peek { display: none; }
```

6b. Replace line 206
`  .cardActive:first-child::before, .cardActive:last-child::after { display: none; }`
with
```css
  /* At either end of the row (`data-edge`, from the page's `tabEdge`) the fillet would reach past
     the row; the sheet's corner squares off there instead. Inside a deck, :first-child would mean
     "first in its deck", which is not the row's edge. */
  .cardActive[data-edge='first']::before, .cardActive[data-edge='last']::after { display: none; }
```

### Step 7: CSS — desktop decks, legend row, reduced motion
**File:** `web/app/(app)/leaderboard/leaderboard.module.css`. Insert after the closing `}` of the second `@media (min-width: 1024px)` block (line 219), before `/* A narrow row … */` and `@container cards`:
```css
@media (min-width: 1024px) {
  /* The legend is one row. It sits beside the headline figures when it fits and drops under them,
     still one row, when it does not. Only past a dozen strategies do its codes ellipsise (each
     keeps its full name as its tooltip), never a second row. */
  .headline { flex-wrap: wrap; row-gap: 14px; }
  .headline > .legend {
    flex: 0 1 auto; min-width: 0; margin-left: auto;
    flex-wrap: nowrap; gap: 6px 14px; font-size: 13px;
  }
  .headline > .legend .legendItem { min-width: 0; gap: 6px; }
  .headline > .legend .swatch, .headline > .legend .swatchDash { flex: none; }
  .headline > .legend .legendLabel { min-width: 0; overflow: hidden; text-overflow: ellipsis; }

  /* A deck: one column of the row, every card in the same grid cell. The original (depth 0) is on
     top; each twin sits a step behind it, offset up and right by --peek, so its edge and its own
     colour show in the 12px gaps. Hovering a deck slides the edge a little further out. The deck is
     its own stacking context, so a twin's z-index never competes with a neighbouring deck. */
  .deck {
    --peek: 7px; --lift: 10px;
    position: relative; z-index: 0;
    display: grid; grid-template-columns: minmax(0, 1fr);
  }
  .deck > .card {
    grid-area: 1 / 1;
    z-index: calc(4 - var(--depth, 0));
    transform: translate(calc(var(--depth, 0) * var(--peek)), calc(var(--depth, 0) * var(--peek) * -1));
    transform-origin: 50% 100%;
    transition: transform 0.32s cubic-bezier(0.2, 0.8, 0.2, 1), box-shadow 0.32s ease;
  }
  .deck:not([data-open]):hover { --peek: 10px; }
  /* A keyboard user tabbing onto a tucked twin sees it come to the front with its focus ring. */
  .deck:not([data-open]) > .card:focus-visible { z-index: 5; }
  /* Only rendered on a tucked twin: covers its face so the peeking strip is the hover target. */
  .peek { display: block; position: absolute; inset: 0; z-index: 1; border-radius: inherit; }

  /* The open deck holds the pick. It takes one column per card, so the twin fans out beside the
     original at full card width. It pops forward in its own slot: raised by --lift, 2% larger from
     its bottom edge, shadowed, above its neighbours. The other decks keep their order. */
  .deck[data-open] {
    z-index: 1;
    grid-column: span var(--n);
    grid-template-columns: repeat(var(--n), minmax(0, 1fr));
    gap: 12px;
  }
  .deck[data-open] > .card {
    grid-area: auto; z-index: 1;
    transform: translateY(calc(var(--lift) * -1)) scale(1.02);
    box-shadow: 0 22px 34px -22px rgba(0, 0, 0, 0.45);
  }
  /* The picked card is the front one and still the tab. It reaches --lift further down so that,
     once raised, its square bottom lands on the month-by-month sheet exactly as before. Its shadow
     would fall on that sheet, so it has none. */
  .deck[data-open] > .cardActive {
    z-index: 2;
    margin-bottom: calc(-12px - var(--lift));
    box-shadow: none;
  }

  /* Codes show whole: a twin's breaks after its '+' (`breakable`), anything longer breaks
     anywhere rather than spill, and the chips wrap inside the card. */
  .deck .name { font-size: 26px; }
  .deck .nameText {
    white-space: normal; overflow: visible; text-overflow: clip;
    overflow-wrap: anywhere; line-height: 1.05;
  }
  .deck .chips { max-width: 100%; flex-wrap: wrap; row-gap: 6px; }
}

/* The pop and the peek are motion; with reduced motion the deck snaps to the same places. */
@media (min-width: 1024px) and (prefers-reduced-motion: reduce) {
  .deck > .card { transition: none; }
}
```
Append at the very end of the file (after the last `@container card` block):
```css
/* A deck card in a six-column row at 1280 (an open pair) is ~180px wide: a smaller code keeps
   'RAW35+' and 'Claude' to two clean lines beside the icon. */
@container card (max-width: 200px) {
  .deck .name { font-size: 22px; }
}
```
**Impact:** these apply only under `.deck` or `.headline > .legend` at ≥ 1024 px. Shelf cards (`.shelfCards .card`) are not inside a `.deck` and are untouched. `.switch` (Phase 2's line 45) is untouched, and nothing here changes `.top`'s `minmax(0, 1fr) 380px` grid, so Phase 2's 324px checklist row and its fit grid are unaffected. The legend fix stays inside the chart sheet (the `.top` grid's first column, `minmax(0, 1fr)`), and no rule here uses `overflow: clip/hidden` on a container to hide the scroll.

### Step 8: The UI journey for the stack
**File:** `.claude/skills/verify-seer/features/steps/leaderboard-stack.mjs` (create)
**Code:**
```js
// Desktop card stacks (leaderboard-desktop-revamp phase 3). Run on `up` demo data at desktop width:
//   $V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-stack.mjs --width 1440 --theme light
// Demo roster: SPY, A, F4 with its Claude twin, F1, C. With no ?s= the pick is A.
const F4 = 'F4-MOM12-N20-TREND';
const TWIN = 'F4-MOM12-N20-TREND-CX';
const MONTHS = 'section[aria-labelledby="months-title"]';
const card = id => `a[href="/leaderboard?s=${encodeURIComponent(id)}"][data-status]`;
const settle = page => page.waitForTimeout(700); // the pop is a 0.32s transition

export default async ({ page, base, shot, log }) => {
  if ((page.viewportSize()?.width ?? 0) < 1024) throw new Error('run at --width 1280 or 1440: decks are desktop only');
  const box = async sel => {
    const b = await page.locator(sel).first().boundingBox();
    if (!b) throw new Error(`no box for ${sel}`);
    return b;
  };
  const hitAt = (x, y) => page.evaluate(([px, py]) =>
    document.elementFromPoint(px, py)?.closest('[data-status]')?.getAttribute('href') ?? null, [x, y]);
  const center = b => [b.x + b.width / 2, b.y + b.height / 2];

  await page.goto(base + '/leaderboard', { waitUntil: 'networkidle' });
  await settle(page);

  // One deck per family, in board order.
  const decks = await page.locator('[data-deck]').evaluateAll(els => els.map(d =>
    [...d.querySelectorAll('[data-status]')].map(c =>
      c.getAttribute('href') ? decodeURIComponent(new URL(c.href).searchParams.get('s')) : 'SPY')));
  const want = [['SPY'], ['A'], [F4, TWIN], ['F1-SPY-SMA200-M'], ['C']];
  if (JSON.stringify(decks) !== JSON.stringify(want)) throw new Error(`decks: ${JSON.stringify(decks)}`);
  log(`decks: ${decks.map(d => d.join(' + ')).join(' | ')}`);

  const openAt = async () => page.locator('[data-deck][data-open]').evaluateAll(els => els.map(e => e.getAttribute('data-deck')));
  if (JSON.stringify(await openAt()) !== JSON.stringify(['A'])) throw new Error(`open decks with A picked: ${await openAt()}`);

  // Closed F4 deck: the twin is tucked behind F4, offset up and right, and F4 covers its face.
  const f4 = await box(card(F4)), tw = await box(card(TWIN));
  const dx = tw.x - f4.x, dy = f4.y - tw.y;
  if (!(dx >= 4 && dx <= 12 && dy >= 4 && dy <= 12)) throw new Error(`twin offset dx=${dx} dy=${dy}`);
  if ((await hitAt(...center(tw))) !== `/leaderboard?s=${F4}`) throw new Error('the twin is not tucked behind F4');
  if (!((await page.locator(card(TWIN)).getAttribute('aria-label')) ?? '').includes('+Claude'))
    throw new Error('the tucked twin has no name as its label');
  log(`closed: F4+Claude peeks ${dx.toFixed(1)}px right and ${dy.toFixed(1)}px up from behind F4`);

  // One-row legend, whole codes, chips inside their cards.
  const tops = await page.locator('[class*="legendItem"]').evaluateAll(els =>
    els.filter(e => e.offsetParent !== null).map(e => Math.round(e.getBoundingClientRect().top)));
  if (tops.length !== 6 || new Set(tops).size !== 1) throw new Error(`legend rows: ${JSON.stringify(tops)}`);
  const cut = await page.locator('[data-deck] [class*="nameText"]').evaluateAll(els =>
    els.filter(e => e.offsetParent !== null && e.scrollWidth > e.clientWidth + 1).map(e => e.textContent));
  if (cut.length) throw new Error(`codes cut off: ${cut.join(', ')}`);
  const spill = await page.locator('[data-deck] [data-status]').evaluateAll(cards => cards.flatMap(c => {
    const r = c.getBoundingClientRect();
    return [...c.querySelectorAll('[class*="chips"] > *')].filter(x => {
      const b = x.getBoundingClientRect();
      return b.width > 0 && (b.right > r.right + 0.5 || b.left < r.left - 0.5);
    }).map(x => x.textContent);
  }));
  if (spill.length) throw new Error(`chips outside their card: ${spill.join(', ')}`);
  log('legend on one row (6 items); every code whole; every chip inside its card');
  await shot('closed');

  // Pick the twin by its peeking edge: its deck opens, F4 and the twin side by side, both readable.
  await page.locator(card(TWIN)).first().click({ position: { x: tw.width / 2, y: 3 } });
  await page.waitForURL(u => u.searchParams.get('s') === TWIN);
  await settle(page);
  if (JSON.stringify(await openAt()) !== JSON.stringify([F4])) throw new Error(`open decks with the twin picked: ${await openAt()}`);
  const f4o = await box(card(F4)), two = await box(card(TWIN)), a = await box(card('A'));
  if (two.x < f4o.x + f4o.width) throw new Error('the twin is not fanned out beside F4');
  if ((await hitAt(...center(f4o))) !== `/leaderboard?s=${F4}` || (await hitAt(...center(two))) !== `/leaderboard?s=${TWIN}`)
    throw new Error('F4 and its twin are not both readable');
  if (!(f4o.y < a.y - 5)) throw new Error(`the open deck did not pop forward: F4 top ${f4o.y}, A top ${a.y}`);
  if ((await page.locator(card(TWIN)).getAttribute('aria-current')) !== 'true') throw new Error('the twin is not the current card');
  const m1 = await box(MONTHS);
  if (Math.abs(two.y + two.height - m1.y) > 1.5) throw new Error(`the tab does not meet the sheet: ${two.y + two.height} vs ${m1.y}`);
  log(`twin picked: F4 deck open (F4 | F4+Claude), raised ${(a.y - f4o.y).toFixed(1)}px; the twin's tab meets the month sheet`);
  await shot('twin-open');

  // The last deck's pick squares the sheet's top-right corner.
  await page.goto(base + '/leaderboard?s=C', { waitUntil: 'networkidle' });
  await settle(page);
  const tab = await page.locator(MONTHS).getAttribute('data-tab');
  const edge = await page.locator(card('C')).getAttribute('data-edge');
  if (tab !== 'last' || edge !== 'last') throw new Error(`C picked: data-tab=${tab} data-edge=${edge}`);
  const c = await box(card('C')), m2 = await box(MONTHS);
  if (Math.abs(c.y + c.height - m2.y) > 1.5) throw new Error('C\'s tab does not meet the sheet');
  log('C picked: months sheet data-tab=last, C carries data-edge=last');
  await shot('last-tab');

  // Motion only without reduced motion.
  const durations = () => page.locator(card('C')).evaluate(e => getComputedStyle(e).transitionDuration);
  const moving = d => d.split(',').some(x => parseFloat(x) > 0);
  if (!moving(await durations())) throw new Error('no transition on deck cards');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  if (moving(await durations())) throw new Error('cards still animate under prefers-reduced-motion');
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  log('the pop is a transition, and none under prefers-reduced-motion');
};
```

### Step 9: The twin journey clicks the peeking edge
**File:** `.claude/skills/verify-seer/features/steps/leaderboard-twin.mjs` as Phase 1 rewrote it. The line is `  await page.locator(card(TWIN)).first().click();`, directly above `  await page.waitForURL(u => u.searchParams.get('s') === TWIN);` near the end of the file (line 63 of Phase 1's file; line 34 at base). It occurs exactly once. The rest of Phase 1's file, including the `a[href][data-status]` card selector and the `nav[aria-label="Strategy"]` switch selectors, still matches this phase's markup: cards stay `Link`s with `href` and `data-status` (SPY an `article[data-status]`), and the switcher is not touched.
**Change:** at desktop width the twin's face is covered by F4, so Playwright's click would time out on "element intercepts pointer events". Click the strip that peeks out above F4 instead.
**Code:** (replaces that one line)
```js
  // At desktop width the twin is tucked behind F4 and only its top edge shows: click that strip.
  const twinCard = page.locator(card(TWIN)).first();
  const twinBox = await twinCard.boundingBox();
  await twinCard.click((page.viewportSize()?.width ?? 0) >= 1024 && twinBox ? { position: { x: twinBox.width / 2, y: 3 } } : {});
```
**Impact:** the step passes at both 390 and 1280.

### Step 10: Feature map
**File:** `.claude/skills/verify-seer/features/leaderboard.md`, as Phases 1 and 2 leave it. Phase 1 already rewrote the twin bullet ("… in its original's **partner** colour …") and added the "Every strategy is unique on the board (R1)" bullet; do not edit either, and do not reintroduce "in the original's colour" anywhere.
**Change:** (a) In `## Sub-features`, directly after Phase 1's "Every strategy is unique on the board (R1)" bullet, add:
```markdown
- Desktop (≥ 1024 px) card row as decks: one deck per family, SPY and plain strategies alone, each original on top with its Claude twin tucked behind it so the twin's edge and colour peek out above and to the right. Clicking a card (the peeking edge, for a tucked twin) picks it. The deck holding the pick pops forward in its own slot (raised, 2% larger, shadowed) and fans the twin out beside the original. The picked card is the tab into the month-by-month sheet. Other decks stay closed and in order. Codes show whole, chips stay inside the card, the chart legend is one row. Motion is CSS only and off under `prefers-reduced-motion`. Below 1024 px the cards are the same flat column as before.
```
(b) In `## Driving it with verify.sh`, directly after Phase 2's line
`$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-switch-row.mjs --width 1280   # one row at the real count, at 7 and at 12; positions unchanged`
(which itself follows Phase 1's `leaderboard-twin.mjs` line), add:
```sh
$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-stack.mjs --width 1440 --theme light
                                # decks SPY | A | F4 + F4+Claude | F1 | C; twin peeks ~7px up/right; legend one row;
                                # clicking the twin's edge opens F4's deck side by side, raised; ?s=C gives data-tab=last; result: PASS
$V shoot RUN --theme both --width 1280 --width 1440 /leaderboard '/leaderboard?s=F4-MOM12-N20-TREND-CX'
```
(c) In `## Gotchas`, replace the bullet that begins "At desktop width a card shows only the code, and `F4+Claude` is too long …" (the last bullet; Phases 1 and 2 leave it as it is at base) with:
```markdown
- At desktop width a card shows its code whole: `F4+Claude` breaks after the `+` onto two lines when the column is narrow, never `F4+…`. The full name and description are the tooltip.
- A tucked twin's face is covered by its original, so a desktop Playwright click on it must hit the peeking strip (`click({ position: { x: width / 2, y: 3 } })`); a centre click times out on "intercepts pointer events".
- Picking a twin's deck adds a column (the open deck spans one column per card), so the other decks narrow slightly on that pick. Their order never changes.
```

## Principles applied

- Laziness protocol: no client island. The pop and the peek are CSS transitions that run because deck/card keys are stable ids across the RSC re-render. The tab edge stays the same one-line expression, now read over `decks.flat()`. `RetiredShelf` itself is untouched; only the `cols` value the page hands it follows the row's new column count, so the shelf keeps the row's column width as before.
- Make illegal states unrepresentable: `stacks()` stores no open flag. `open` is `isOpen(rows)` (`rows.some(id === pick)`), shared by `deck()` and `rowCols`, and `tucked` is derived from `place`, so a deck cannot be open without the pick, and a twin cannot be tucked in an open deck.
- Fix root causes: the duplicate line is fixed at its source (`page.tsx:98`, `desk` falling back to `wline.label`). The legend fix targets `flex-wrap: wrap` in the shared headline row. Step 0 reproduces the 8 px scroll on the real roster and names the overflowing element before any CSS changes, and it routes a switch culprit to Phase 2 instead of masking it with `overflow: clip`.
- Build the lever: geometry is checked by script, not by eye. `leaderboard-stack.mjs` asserts the decks, the peek offset, the occlusion, the fan-out, the pop, the tab joint, the legend row and reduced motion, and the mobile journey diffs a layout fingerprint before and after.
- Test behavior, not implementation: the `stacks` tests assert the grouping a reader sees (who sits behind whom, in what order, nobody lost), not how it is computed.

## Verification

**Build:** `cd web && npx tsc --noEmit`
**Tests:** `cd web && npm test` (focused: `npx vitest run 'app/(app)/leaderboard/view.test.ts'`)
**Proof:**
- Harness: `.claude/skills/verify-seer` (`V=.claude/skills/verify-seer/scripts/verify.sh`, run from `/home/miftah/.worktrees/seer/leaderboard-desktop-revamp`), plus one read-only real-roster journey through `run-the-web-app` (`npm run shoot`), because the demo board has one twin and production has three.
- Setup: `[ -e web/node_modules ] || cp -al /home/miftah/seer/web/node_modules web/node_modules` (hardlink; a symlink breaks `next`). `$V up` after the phase is committed: the web snapshot is copied at `up`.
- Feature-map entries: `features/leaderboard.md`
- Journeys:
  1. **Duplicate line (fails before the fix).** `$V up --empty` gives RUN1, the migrated real roster with no snapshots, so nothing is ranked. Precondition: `$V sql RUN1 "select id from strategies where is_champion and is_benchmark and status = 'active'"` returns one row (if none, mark this journey inconclusive: the champion branch that duplicates is not reached). Then `$V api RUN1 GET /leaderboard | grep -o 'No common window yet' | wc -l` prints `1` (`2` on the parent commit, see journey 5). `$V shoot RUN1 --theme light --width 1280 --width 1440 /leaderboard` exits 0 (no horizontal scroll). `$V down RUN1`.
  2. **Stacks, pop, tab, legend, motion.** `$V up` gives RUN2 (demo). `$V ui RUN2 .claude/skills/verify-seer/features/steps/leaderboard-stack.mjs --width 1280 --theme light` and `… --width 1440 --theme dark` both end `PASS`, with log lines `decks: SPY | A | F4-MOM12-N20-TREND + F4-MOM12-N20-TREND-CX | F1-SPY-SMA200-M | C`, `closed: F4+Claude peeks …`, `legend on one row (6 items)…`, `twin picked: F4 deck open …`, `C picked: months sheet data-tab=last …`, `… none under prefers-reduced-motion`.
  3. **Screenshots.** `$V shoot RUN2 --theme both --width 1280 --width 1440 /leaderboard '/leaderboard?s=F4-MOM12-N20-TREND-CX'` exits 0. Read the PNGs. On `/leaderboard`, five decks with F4's twin a coloured strip above and right of F4, A raised as the tab. On `?s=…-CX`, F4 and F4+Claude side by side, raised, F4+Claude's square bottom joined to the month sheet in its tint, the legend one row, no `F4+…` ellipsis.
  4. **Real roster (production, read only).** In `web/`, with `SEER_ENV_FILE=/home/miftah/seer/.env.local`, run `node scripts/with-env.mjs npx next dev -p 3121` in the background, then `npm run shoot -- --base http://localhost:3121 --theme both --width 1280 --width 1440 /leaderboard`. Exit 0 with no `PROBLEMS:` line (this one carried "horizontal scroll" at 1440 before). Get the twin ids with `node scripts/with-env.mjs node --input-type=module -e "import {neon} from '@neondatabase/serverless'; const r = await neon(process.env.DATABASE_URL)\`select id from strategies where twin_of is not null and status = 'active'\`; console.log(r.map(x => x.id).join(' '))"`. Then `npm run shoot -- --base http://localhost:3121 --theme light --width 1440 "/leaderboard?s=<one of them>"` exits 0, and `node .shots/overflow.mjs http://localhost:3121/leaderboard 1440` (Step 0's script) prints `"overflowPx": 0` and `"legendRows": 1`. Read `web/.shots/leaderboard__light__1440.png`: five decks (SPY, C, COSK, RAW35, A), three of them with a peeking twin. Free the port with `fuser -k 3121/tcp`.
  5. **Mobile unchanged (before/after fingerprint) and the failing baseline.** Write `$SCR/fp.mjs` (`SCR=$(mktemp -d)`):
     ```js
     // Layout fingerprint of /leaderboard on a phone: card boxes, legend boxes, page width.
     export default async ({ page, base, log }) => {
       for (const path of ['/leaderboard', '/leaderboard?s=F4-MOM12-N20-TREND-CX']) {
         await page.goto(base + path, { waitUntil: 'networkidle' });
         await page.waitForTimeout(700);
         const fp = await page.evaluate(() => ({
           scroll: document.documentElement.scrollWidth,
           cards: [...document.querySelectorAll('[data-status]')].map(e => { const r = e.getBoundingClientRect();
             return [e.getAttribute('href') ?? 'SPY', Math.round(r.x), Math.round(r.y + scrollY), Math.round(r.width), Math.round(r.height)]; }),
           legend: [...document.querySelectorAll('[class*="legendItem"]')].filter(e => e.offsetParent).map(e => { const r = e.getBoundingClientRect();
             return [e.textContent, Math.round(r.x), Math.round(r.y + scrollY)]; }),
         }));
         log(`FP ${path} ${JSON.stringify(fp)}`);
       }
     };
     ```
     Baseline from the parent of the phase-3 commit: `B=$SCR/base; git worktree add --detach "$B" HEAD~1 && cp -al web/node_modules "$B/web/node_modules"`, then `(cd "$B" && .claude/skills/verify-seer/scripts/verify.sh up)` gives RUNB. Run `(cd "$B" && .claude/skills/verify-seer/scripts/verify.sh ui RUNB "$SCR/fp.mjs" --width 390 --theme dark)`. Also run `… ui RUNB /home/miftah/.worktrees/seer/leaderboard-desktop-revamp/.claude/skills/verify-seer/features/steps/leaderboard-stack.mjs --width 1440`, which **must fail** (`decks: []`), and `… api RUNB GET /leaderboard` on an `--empty` baseline, which gives the count `2` for journey 1. After the change, run `$V ui RUN2 "$SCR/fp.mjs" --width 390 --theme dark`. Pass condition: `diff <(grep -o 'FP .*' <RUNB evidence ui txt>) <(grep -o 'FP .*' <RUN2 evidence ui txt>)` is empty. Evidence lives in `~/.local/state/seer-verify/<RUN>/evidence/NN-ui-*.txt`. Then `$V down RUNB` and `git worktree remove --force "$B"`.
- Neighbor check: `$V ui RUN2 .claude/skills/verify-seer/features/steps/leaderboard-twin.mjs` (1280 dark) and `… --width 390` both `PASS`: twin order, partner colours, unique sheets and icons, `3 3` dash, Paper chip, the twin's rule 5 (Phase 1's assertions, with Step 9's edge click). `$V ui RUN2 .claude/skills/verify-seer/features/steps/leaderboard-switch-row.mjs --width 1280` (Phase 2's) still `PASS`. The retired shelf does not exist on demo data. Its component is untouched, `RetiredShelf.test.tsx` runs in `npm test`, and journey 4's real roster shows the shelf if production has retired rows.
- Cost: none. Every drive is offline or read-only, with no LLM turns.
- Cleanup: `$V down RUN2` (and any run left up).

**Exit criteria:** `tsc` and `npm test` pass. `leaderboard-stack.mjs` passes at 1280 light and 1440 dark. `shoot` at 1280/1440 exits with no horizontal scroll on both demo and real roster. "No common window yet" counts 1 on the `--empty` board. The 390 px fingerprint is identical before and after.

## Handoffs

- `RetiredShelf` now receives `cols={rowCols}` (Step 3c/3d, reconciled): the shelf keeps the live row's column width, as its `cols` prop doc says.
- Phase 2 has landed before this phase and its exit criteria (one row at 1024/1280/1440, `shoot` with no horizontal scroll) rule out the switcher as the overflow culprit. If Step 0 nevertheless names `.switch`/`StrategySwitch`, Phase 2 did not meet its exit criteria: stop and report it as a Phase 2 regression rather than editing Phase 2's files here.
- Step 9 edits Phase 1's rewritten `leaderboard-twin.mjs` (reconciled: the click line quoted there is Phase 1's).
- The tucked twin's peeking strip is the only pointer target for a closed twin. Long-press on touch never sees it, because decks exist only at ≥ 1024 px.

## Rollback

Revert the phase-3 commit. It touches only `view.ts`/`view.test.ts` (`stacks` and its tests), `page.tsx`, `leaderboard.module.css` and three verify-seer files. Phases 1 and 2 do not read anything it adds, so they stay intact.
