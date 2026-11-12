> Adopted from `.workflows/plan/LEADERBOARD_CARD_SPREAD_PLAN.md` phase 1. Source: `.workflows/plan/leaderboard-card-spread/phase-1.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 1: Flat overlapping card spread

**Plan set:** `LEADERBOARD_CARD_SPREAD_PLAN.md`
**Analysis:** `.workflows/analyze/20261112-075853-LCS1_code_analyzer.md`
**Satisfies:** R1, R2, R3, R4 — the desktop leaderboard's live cards become one flat, left-over-right spread; a click raises the card in place; twins stop pairing with their originals
**Criteria:** R1.1, R1.2, R1.3, R2.1, R2.2, R3.1, R3.2, R3.3, R4.1, R4.2
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `web/app/(app)/leaderboard`

---

## Goal

At 1024px and wider, the live cards on `/leaderboard` are one flat row in board order: every card
the same width, each laid over the left 40% of the card to its right, the row exactly filling its
width. SPY is always on top. A click raises the clicked card above every card but SPY in its own
place, with a front shadow, and it stays the tab into the month-by-month sheet. The family decks
(`stacks()`, tucked twins, peek strips, open decks) are gone. Below 1024px nothing changes.

## Interface Contract

**Deletes:**
- `stacks` (`web/app/(app)/leaderboard/view.ts:199-232`) and its doc comment
- the `describe('stacks', …)` block and the `stacks` import (`web/app/(app)/leaderboard/view.test.ts:9,233-274`)
- in `page.tsx`: `decks`, `isOpen`, `rowCols` (`:191-198`), the `deck()` function (`:247-265`), the `place` parameter of `card()`, `tucked`, the `.peek` span, the `--depth` style, the tucked `aria-label` (`:271-345`)
- CSS classes and custom properties `.deck`, `.peek`, `--peek`, `--lift`, `--depth`, `[data-deck]`, `[data-open]` (`leaderboard.module.css:79-83,242-300,313-317`)
- DOM attributes `data-deck`, `data-open`
- the verify-seer step file `.claude/skills/verify-seer/features/steps/leaderboard-stack.mjs`

**Renames:** none (the stack step is replaced by a new file, not renamed: its content is all new)

**Creates:**
- `spreadZ(st, at)`, a function local to the `Leaderboard` component (`page.tsx`), not exported
- CSS custom properties `--n` (inline on the live row), `--z` (inline on each live card), `--w`, `--spread-edge`, `--front-shadow` (on `.cards`, desktop only)
- `.claude/skills/verify-seer/features/steps/leaderboard-spread.mjs`

**Signature changes:** `card(row, tab, place?: { depth: number; open: boolean })` -> `card(row, tab, at?: number)` (local to `page.tsx`)

**Requires (from earlier phases):** none

**Leaves alone (owned by others):** `web/lib/strategy.ts` (`attachedOriginal`, `orderTwins`), `web/lib/data.ts`, `web/components/*`, `RetiredShelf.tsx` (only its `cols` prop value changes, at the call site in `page.tsx`), `leaderboard-twin.mjs` and `leaderboard-switch-row.mjs` (run as neighbours, not edited), `web/package_readme.md` (see Handoffs), every rule below 1024px

## Files

| File | Action | What changes |
|---|---|---|
| `web/app/(app)/leaderboard/page.tsx` | modify | `:19` drop `stacks` import; `:185-198` flat row + `tabEdge` from `live`; `:236-238` render `live` with `--n`, shelf `cols={live.length}`; `:247-347` delete `deck()`, add `spreadZ`, `card()` takes `at` |
| `web/app/(app)/leaderboard/view.ts` | modify | `:199-233` delete `stacks` and its doc comment |
| `web/app/(app)/leaderboard/view.test.ts` | modify | `:9` drop `stacks` from the import; `:233-275` delete the `stacks` describe block |
| `web/app/(app)/leaderboard/leaderboard.module.css` | modify | `:78-83` drop mobile `.deck`/`.peek`; `:169-175` `.cards` becomes the spread; `:189-198,211-213` tab comments, drop its `z-index: 1`; `:242-300` deck rules replaced by spread rules, dark tokens, reduced motion; `:313-317` deck container rule deleted |
| `.claude/skills/verify-seer/features/steps/leaderboard-stack.mjs` | delete | asserts decks, which no longer exist |
| `.claude/skills/verify-seer/features/steps/leaderboard-spread.mjs` | create | the desktop spread journey and the phone column check |
| `.claude/skills/verify-seer/features/leaderboard.md` | modify | `:10` decks bullet rewritten; `:30-32` step commands; `:51-53` deck gotchas rewritten |

## Implementation Steps

Read `web/AGENTS.md` first. This phase uses only `next/link` (unchanged usage) and a server
component with inline custom properties: no new Next API, and no client component (plan index
invariant 3). If you touch anything else in Next, read `web/node_modules/next/dist/docs/` first.

Steps 1-3 are one unit: the tree does not type-check between them. Check it after Step 3.

### Step 1: The page renders one flat row
**File:** `web/app/(app)/leaderboard/page.tsx:17-21`, `:185-198`, `:233-245`, `:247-347`

**Change 1a** (`:17-21`): drop `stacks` from the `./view` import.
**Code:**
```tsx
import {
  BENCHMARK_DASH, compare, LOOK_FALLBACK, looks, MIN_COMMON_SESSIONS, monthLines, NO_GATE, pickResearch,
  researchOf, retiredLabel, scoreOf, sinceStartLine, spyOverSpan, twinChipTip, windowLine,
  type CompareRow, type Look, type MonthLine,
} from './view';
```

**Change 1b** (`:185-198`): replace the comment and the `decks`/`ids`/`tabEdge`/`isOpen`/`rowCols`
block (everything from `// Desktop: the live row is one deck per family` down to and including
`const rowCols = …;`) with:
**Code:**
```tsx
  // Desktop: the live row is one spread of cards in board order. `live` is already that order:
  // `orderTwins` puts each Claude twin right after its original, so a twin needs no grouping of its
  // own and is just the next card. The picked card drops into this sheet as a tab, and at either
  // end of the row the tab meets the sheet's own rounded corner, which has to square off for the
  // two to read as one surface. Nothing in the row moves on a pick, so its ends are always `live`'s.
  const ids = live.map(r => r.strategy.id);
  const tabEdge = !pick ? undefined : ids[0] === pick.id ? 'first' : ids.at(-1) === pick.id ? 'last' : undefined;
```

**Change 1c** (`:229-245`): the return block renders `live` directly and the shelf counts live cards.
**Code:**
```tsx
  return (
    <>
      <AppHeader date={shortDate(wibDate(now))} title="Leaderboard" demo={run.isDemo}
        deskAside={<span className="pill-outline" style={{ height: 52, fontSize: 16, color: 'var(--ink)' }}>Forward test · {period}</span>} />
      <div className="stack">
        <div className={s.top}>{chartSheet}{checklistSheet}</div>
        {monthsSheet}
        <div className={s.cards} style={{ '--n': live.length } as CSSProperties}>
          {live.map((r, at) => card(r, true, at))}
        </div>
        {retiredRows.length > 0 && (
          <RetiredShelf count={retiredRows.length} cols={live.length} open={pick?.status === 'retired'}>
            {retiredRows.map(r => card(r, false))}
          </RetiredShelf>
        )}
        <div className="nav-clear" />
      </div>
    </>
  );
```

**Change 1d** (`:247-347`): delete the `deck()` function and its doc comment (`:247-265`), and
replace the `card()` doc comment and function (`:267-347`) with `spreadZ` and the new `card()`.
Everything from the `/**` above `function deck` down to the closing `}` of `function card` (the line
before the component's own closing `}` at `:348`) becomes:
**Code:**
```tsx
  /**
   * A live card's place in the desktop spread's stacking order (`--z`, read only at 1024px and
   * up). Left covers right: each card sits above every card to its right, so `n - at`. The pick
   * rises above all of them in its own place, and SPY above the pick: the owner reads every card
   * against the baseline, so it is the one card nothing ever covers, and it is never a pick.
   * `n + 1` is left free for a keyboard-focused card (the stylesheet), so its focus ring shows over
   * its neighbours but never over the pick. Derived from the pick on every render, never stored, so
   * no card can be raised without being the pick.
   */
  function spreadZ(st: Board['rows'][number]['strategy'], at: number) {
    const n = live.length;
    return st.isBenchmark ? n + 3 : st.id === pick?.id ? n + 2 : n - at;
  }

  /**
   * One strategy's card. `tab`: the picked live card becomes the tab into the month-by-month sheet
   * right under the live row (desktop); a retired card sits on the shelf below that sheet, so when
   * it is the pick it is marked as picked instead of pretending to be attached to it.
   * `at`: a live card's index in the row, which sets its place in the spread's stacking order
   * (`spreadZ`). A Claude twin is an ordinary card here: picking it raises it alone.
   */
  function card({ strategy: st, metrics: m }: Board['rows'][number], tab: boolean, at?: number) {
    const Icon = strategyIcon(st.icon); // st.icon is already the unique display icon (`board` above).
    const look = lookOf(st.id);
    const dash = (v: string) => (st.isBenchmark ? '—' : v);
    const cr = cmpOf(st.id);
    const retired = st.status === 'retired';
    const active = st.id === pick?.id;
    // Desktop shows the code; the full name and the one-line description live in this tip.
    const tip = `${st.name}\n${st.sub}`;
    const body = (
      <>
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
    const style = { '--tint': look.tint, ...(at !== undefined && { '--z': spreadZ(st, at) }) } as CSSProperties;
    // Which end of the row the tab sits at, if any: there the sheet's corner squares off instead
    // of the tab drawing a fillet past the row's edge.
    const edge = active && tab ? tabEdge : undefined;
    // SPY is in every month row already, so only research cards pick the month-by-month sheet.
    return st.isBenchmark ? (
      <article key={st.id} data-status={cr?.status ?? 'benchmark'} className={cls} style={style}>{body}</article>
    ) : (
      <Link key={st.id} href={`/leaderboard?s=${encodeURIComponent(st.id)}`} scroll={false}
        data-status={cr?.status ?? 'benchmark'} data-edge={edge} aria-current={active ? 'true' : undefined}
        className={`${cls} ${s.cardLink}`} style={style}>{body}</Link>
    );
  }
```
**Impact:** the live row's DOM is `div.cards > (article|a)*` with no wrapper per family. Each live
card carries `--z` inline; it is read only by a ≥1024px rule (Step 4), so the mobile column's
stacking (later sheet on top) is untouched. The retired shelf's cards get no `--z` (`at` is
undefined). The shelf's desktop grid now has `live.length` columns (Decision: retired shelf cols).

### Step 2: Delete `stacks`
**File:** `web/app/(app)/leaderboard/view.ts:199-233`
**Change:** delete the whole doc comment that starts `/**` / ` * The desktop card row as decks (owner, 2026-11-10: …`
(`:199`), the function `export function stacks<R extends { strategy: RosterIn }>(rows: R[]): R[][] { … }`
(`:211-232`), and the blank line after it (`:233`). After the edit, `export const researchOf = …`
(`:197`) is followed by one blank line and then the `/**` that opens the `MIN_COMMON_SESSIONS` doc
comment. Keep the `attachedOriginal` import at `:20`: `looks()` still uses it at `:146`.
**Code:** the resulting seam:
```ts
export const researchOf = <T extends RosterIn>(roster: T[]): T[] => roster.filter(st => !st.isBenchmark);

/**
 * Sessions a strategy must share with the others before it can be ranked. **This is
```
**Impact:** `page.tsx` was the only caller (removed in Step 1).

### Step 3: Delete the `stacks` tests
**File:** `web/app/(app)/leaderboard/view.test.ts:6-10`, `:233-275`
**Change 3a** (`:6-10`): drop `stacks` from the import.
**Code:**
```ts
import {
  CARD_BGS, CHECKS, compare, LOOK_PERIOD, looks, MIN_COMMON_SESSIONS, MIN_RANKED, monthLabel, monthLines,
  NO_GATE, PALETTE_SIZE, PARTNER_BGS, pickResearch, researchOf, retiredLabel, scoreOf, sinceStartLine,
  SLOT_BGS, spyOverSpan, TWIN_DASHES, twinChipTip, windowLine, type GateIn, type RankIn, type RosterIn,
} from './view';
```
**Change 3b** (`:233-275`): delete from `describe('stacks', () => {` through its closing `});`
(`:274`) and the blank line after it (`:275`). The `researchOf` describe block's closing `});`
(`:231`) is then followed by one blank line and `// --- the common-window comparison (R3, invariant 6) ---…`.
**Code:** the resulting seam:
```ts
describe('researchOf', () => {
  it('lists research strategies only', () => {
    expect(researchOf(roster).map(s => s.id)).toEqual(RESEARCH);
  });
});

// --- the common-window comparison (R3, invariant 6) ---------------------------------------------
```
**Impact:** the flat row has no grouping logic left to unit-test; its behaviour (order, overlap,
stacking) is proved on the rendered page by the new verify step (Step 5).

**Check (end of Steps 1-3):** `cd web && npx tsc --noEmit && npm test` passes.

### Step 4: The stylesheet becomes the spread
**File:** `web/app/(app)/leaderboard/leaderboard.module.css`

**Change 4a** (`:78-83`): the mobile `.deck`/`.peek` fallbacks go (those elements no longer exist).
Replace
```css
.cards { display: contents; }
/* The desktop row is decks (`deck()` in page.tsx). Below 1024px a deck is `display: contents`, so
   its cards are the mobile column's own stacked sheets exactly as before, and the peek strip of a
   tucked twin does not exist. */
.deck { display: contents; }
.peek { display: none; }
```
with
**Code:**
```css
/* Below 1024px the live row is not a box: its cards are the mobile column's own stacked sheets. */
.cards { display: contents; }
```

**Change 4b** (`:169-175`, inside the second `@media (min-width: 1024px)` block): replace the
`.cards` comment and rule
```css
  /* One row, one column per strategy: the picked card is a tab into the month-by-month sheet
     right under the row, so it must never wrap onto a second row away from it. Narrow cards
     stack their metrics instead (container query below). */
  .cards {
    order: 1; display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr);
    gap: 12px; margin-top: 12px; container: cards / inline-size; --card-r: 32px;
  }
```
with
**Code:**
```css
  /* The live row is one spread (owner, 2026-11-12): every card the same width, each laid over the
     left 40% of the card to its right, so n cards take 1 + 0.6(n - 1) card widths and fill the
     row exactly, with no scroll. `--n` (the live count) comes from the page. `--w` stays
     unresolved here: its `100%` resolves where a card uses it, and width, margin and padding
     percentages all resolve against this row's width. The picked card is a tab into the
     month-by-month sheet right under the row, so the row never wraps. Narrow cards stack their
     metrics instead (container query below). */
  .cards {
    order: 1; display: flex; margin-top: 12px; container: cards / inline-size; --card-r: 32px;
    --w: calc(100% / (1 + (var(--n, 1) - 1) * 0.6));
    --spread-edge: rgba(29, 28, 26, 0.12);
    --front-shadow: -18px -6px 30px -16px rgba(29, 28, 26, 0.38), 18px -6px 30px -16px rgba(29, 28, 26, 0.38);
  }
```

**Change 4c** (`:189-198`): the tab's comment describes the spread and its `z-index: 1` goes (the
card's `--z` sets it now; `.cards > .card` below would override it anyway). Replace
```css
  /* The tab: square bottom, stretched over the 12px gap onto the sheet, with concave fillets
     where it meets the sheet's top edge. The fillets take the card's own corner radius, so the
     turn into the sheet reads as the same curve as the corner above it. --tint is the card's
     sheet colour. The fillet reaches past the 12px gap onto the neighbour's column, but only
     below the neighbour's bottom edge: at --card-r 32 the curve clears it by 13px. */
  .cardActive {
    position: relative; z-index: 1;
    border-bottom-left-radius: 0; border-bottom-right-radius: 0;
    margin-bottom: -12px; padding-bottom: 34px;
  }
```
with
**Code:**
```css
  /* The tab: square bottom, stretched over the 12px gap onto the sheet, with concave fillets
     where it meets the sheet's top edge. The fillets take the card's own corner radius, so the
     turn into the sheet reads as the same curve as the corner above it. --tint is the card's
     sheet colour. In the spread the fillets lie over the feet of the cards beside the tab, which
     sit under the pick, so the tab's own stacking order (`--z`) carries them; SPY, above the
     pick, covers the one beside it. */
  .cardActive {
    position: relative;
    border-bottom-left-radius: 0; border-bottom-right-radius: 0;
    margin-bottom: -12px; padding-bottom: 34px;
  }
```

**Change 4d** (`:211-213`): replace
```css
  /* At either end of the row (`data-edge`, from the page's `tabEdge`) the fillet would reach past
     the row; the sheet's corner squares off there instead. Inside a deck, :first-child would mean
     "first in its deck", which is not the row's edge. */
```
with
**Code:**
```css
  /* At either end of the row (`data-edge`, from the page's `tabEdge`) the fillet would reach past
     the row; the sheet's corner squares off there instead. */
```
(the two rules under it, `:214-216`, stay as they are).

**Change 4e** (`:242-300`): in the third `@media (min-width: 1024px)` block, keep the legend rules
(`:230-240`) and replace everything from `/* A deck: one column of the row, every card in the same
grid cell.` (`:242`) down to the block's closing `}` (`:295`), plus the reduced-motion block that
follows (`:297-300`), with:
**Code:**
```css
  /* Left covers right: each card's stacking order (`--z`, from the page's `spreadZ`) puts it above
     every card to its right, so SPY, the baseline, is never covered, and each card's edge casts a
     soft shadow onto the card it lies over. The pick rises above every card but SPY in its own
     place: no transform and no extra column, so nothing in the row moves on a click. */
  .cards > .card {
    flex: none; width: var(--w); z-index: var(--z);
    padding-left: calc(var(--w) * 0.4 + 16px);
    box-shadow: 10px 0 22px -14px var(--spread-edge);
    transition: box-shadow 0.18s ease;
  }
  .cards > .card + .card { margin-left: calc(var(--w) * -0.4); }
  /* The front card's shadow is cast up and to the sides only: its foot is the tab, and a shadow
     there would fall on the month-by-month sheet. */
  .cards > .cardActive { box-shadow: var(--front-shadow); }
  /* A keyboard user's focused card rises just under the pick (`spreadZ` leaves n + 1 free), so its
     focus ring shows whole. */
  .cards > .card:focus-visible:not(.cardActive) { z-index: calc(var(--n) + 1); }

  /* Mirrored contents. The card on the left covers this card's left 40%, so everything the owner
     reads (code, chips, total return, metrics) sits right-aligned in the right 60%, past the
     padding above, and the icon, which only decorates, takes the top-left corner. Codes show
     whole: a twin's breaks after its '+' (`breakable`), anything longer breaks anywhere rather
     than spill, and the chips wrap inside the card. */
  .cards .icon { position: absolute; top: 22px; left: 22px; }
  .cards .cardName { align-items: flex-end; text-align: right; }
  .cards .titleRow { align-items: flex-end; }
  .cards .name { font-size: 26px; }
  .cards .nameText {
    white-space: normal; overflow: visible; text-overflow: clip;
    overflow-wrap: anywhere; line-height: 1.05;
  }
  .cards .chips { max-width: 100%; flex-wrap: wrap; justify-content: flex-end; row-gap: 6px; }
  .cards .metric { align-items: flex-end; text-align: right; }

  /* A narrow row (`.card`'s tighter padding in the container query below): the icon follows it. */
  @container cards (max-width: 1000px) {
    .cards .icon { top: 18px; left: 16px; }
  }
  /* A spread card's readable part is about 135px wide at 1280 and 160px at 1440: a smaller code
     keeps 'COSK+' and 'Claude' to two clean lines, and a smaller total return stays on its line. */
  @container card (max-width: 200px) {
    .cards .name { font-size: 22px; }
    .cards .ret { font-size: 30px; }
  }
}

/* The edge and front shadows need more weight to read on the dark ground. */
@media (min-width: 1024px) and (prefers-color-scheme: dark) {
  .cards {
    --spread-edge: rgba(0, 0, 0, 0.45);
    --front-shadow: -18px -6px 30px -16px rgba(0, 0, 0, 0.7), 18px -6px 30px -16px rgba(0, 0, 0, 0.7);
  }
}

/* The front shadow fading in is motion; with reduced motion it snaps. */
@media (min-width: 1024px) and (prefers-reduced-motion: reduce) {
  .cards > .card { transition: none; }
}
```

**Change 4f** (`:313-317`): delete the old deck container rule and its comment (its replacement is
inside the media block above):
```css
/* A deck card in a six-column row at 1280 (an open pair) is ~180px wide: a smaller code keeps
   'RAW35+' and 'Claude' to two clean lines beside the icon. */
@container card (max-width: 200px) {
  .deck .name { font-size: 22px; }
}
```
The file then ends with the `@container card (max-width: 150px)` rule. Keep the
`@container cards (max-width: 1000px)` (`:302-309`) and `@container card (max-width: 150px)`
(`:310-312`) rules as they are: they already only match at desktop width (the containers exist only
there), and the 150px one is what stacks a spread card's metrics into one column at 1280.

**Geometry this produces** (rail 104px + main's 20px right padding; demo has 6 live cards):
row 1156px at 1280 → card 289px, step 173.4px; row 1316px at 1440 → card 329px, step 197.4px;
row 900px at 1024 → card 225px. Content box (what `@container card` measures) =
0.6·w − 38px: ~135px at 1280 (one-column metrics), ~159px at 1440 (two columns).
Front shadow reach: its lowest edge stops 7px above the card's foot, so it never touches the
month sheet; edge shadow reaches 7px right of a card.

**Impact:** desktop only. Every new or changed rule is inside a `min-width: 1024px` media query
(or a container query nested in one). Below 1024px the only CSS change is the removal of rules for
elements that no longer render (`.deck`, `.peek`). Specificity: `.cards > .card` (0,2,0) overrides
`.card`'s `padding: 22px` and the narrow container's `padding: 18px 16px` on the left side only, so
`.cardActive`'s `padding-bottom: 34px`/`30px` still apply.

**Check:** `cd web && npx tsc --noEmit && npm test` still passes (CSS is not type-checked; this
catches nothing new, the proof is Step 5's journey).

### Step 5: Replace the stack step with the spread step
**File:** delete `.claude/skills/verify-seer/features/steps/leaderboard-stack.mjs`; create
`.claude/skills/verify-seer/features/steps/leaderboard-spread.mjs`
**Change:** `git rm` the old step; write the new one. Each `log()` line starts with the journey
label the Proof section names, so a verifier can grep the transcript.
**Code:**
```js
// Desktop card spread (leaderboard-card-spread phase 1): the live cards are one flat row, each card
// laid over the left 40% of the card to its right, SPY always on top, a picked card raised in its
// own place, a Claude twin an ordinary card. Below 1024px: the unchanged column.
// Run on `up` demo data, at both desktop widths and at a phone width:
//   $V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-spread.mjs --width 1440 --theme light
//   $V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-spread.mjs --width 1280
//   $V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-spread.mjs --width 390
// Demo roster in board order: SPY, A, F4, F4's Claude twin, F1, C. With no ?s= the pick is A.
const F4 = 'F4-MOM12-N20-TREND';
const TWIN = 'F4-MOM12-N20-TREND-CX';
const F1 = 'F1-SPY-SMA200-M';
const ORDER = ['SPY', 'A', F4, TWIN, F1, 'C'];
const MONTHS = 'section[aria-labelledby="months-title"]';
const SPY = 'article[data-status]';
const card = id => `a[href="/leaderboard?s=${encodeURIComponent(id)}"][data-status]`;
const OVERLAP = 0.4;

// Every live card in DOM order (the row is SPY's parent). Positions are also taken relative to the
// row: the checklist above can change height with the pick and move the whole row down, and R3.2
// is about the cards within the row.
const readRow = page => page.locator(SPY).first().evaluate(spy => {
  const row = spy.parentElement;
  const rb = row.getBoundingClientRect();
  const idOf = c => (c.getAttribute('href') ? decodeURIComponent(new URL(c.href).searchParams.get('s')) : 'SPY');
  const boxOf = el => {
    const b = el.getBoundingClientRect();
    return { x: b.x, y: b.y, w: b.width, h: b.height, right: b.right, bottom: b.bottom };
  };
  const cards = [...row.children].map(c => {
    const cs = getComputedStyle(c);
    const visible = sel => [...c.querySelectorAll(sel)].find(e => e.offsetParent !== null) ?? null;
    const code = visible('[class*="nameText"]');
    const ret = visible('[class*="metrics"] > :first-child .num');
    const box = boxOf(c);
    return {
      id: idOf(c), ...box, relX: box.x - rb.x, relY: box.y - rb.y,
      z: cs.zIndex, shadow: cs.boxShadow, transform: cs.transform, marginLeft: cs.marginLeft,
      outline: cs.outlineStyle,
      current: c.getAttribute('aria-current') === 'true', active: c.className.includes('cardActive'),
      ariaLabel: c.getAttribute('aria-label'),
      code: code && { ...boxOf(code), text: code.textContent, cut: code.scrollWidth > code.clientWidth + 1 },
      ret: ret && { ...boxOf(ret), text: ret.textContent },
    };
  });
  const rs = getComputedStyle(row);
  return { x: rb.x, right: rb.right, display: rs.display, flexDir: rs.flexDirection, cards };
});

export default async ({ page, base, shot, log }) => {
  const width = page.viewportSize()?.width ?? 0;
  const near = (a, b, tol = 0.5) => Math.abs(a - b) <= tol;
  const byId = row => Object.fromEntries(row.cards.map(c => [c.id, c]));
  // The card that is on top at a viewport point (the page's real hit testing, not a class name).
  const hit = (x, y) => page.evaluate(([px, py]) => {
    const c = document.elementFromPoint(px, py)?.closest('[data-status]');
    if (!c) return null;
    return c.getAttribute('href') ? decodeURIComponent(new URL(c.href).searchParams.get('s')) : 'SPY';
  }, [x, y]);
  const centre = async sel => {
    await page.locator(sel).first().evaluate(e => e.scrollIntoView({ block: 'center' }));
    await page.mouse.move(0, 0); // no hover state, no tooltip over a hit point
    await page.waitForTimeout(400); // the front shadow fades in over 0.18s
  };
  const open = async path => {
    await page.goto(base + path, { waitUntil: 'networkidle' });
    await centre(SPY);
  };
  const noDecks = async () => {
    const n = await page.locator('[data-deck], [class*="peek"]').count();
    if (n) throw new Error(`${n} deck wrappers or peek strips are still rendered`);
  };
  // For each neighbouring pair (i-1, i), the card on top inside card i's left 40%, where they overlap.
  const overlapTops = async row => {
    const out = [];
    for (let i = 1; i < row.cards.length; i++) {
      const c = row.cards[i];
      out.push(await hit(c.x + c.w * OVERLAP / 2, c.y + c.h / 2));
    }
    return out;
  };
  const spyWhole = async row => {
    const sp = row.cards.find(c => c.id === 'SPY');
    for (const fx of [0.15, 0.5, 0.85, 0.98]) for (const fy of [0.15, 0.5, 0.85]) {
      const top = await hit(sp.x + sp.w * fx, sp.y + sp.h * fy);
      if (top !== 'SPY') throw new Error(`SPY is covered by ${top} at (${fx}, ${fy}) of its box`);
    }
  };

  if (width < 1024) {
    // J6 (R1.2): the phone column, exactly as before.
    await page.goto(base + '/leaderboard', { waitUntil: 'networkidle' });
    await noDecks();
    const r = await readRow(page);
    const ids = r.cards.map(c => c.id);
    if (JSON.stringify(ids) !== JSON.stringify(ORDER)) throw new Error(`column: ${ids.join(', ')}`);
    if (r.display !== 'contents') throw new Error(`the live row is a ${r.display} box below 1024px; want display: contents`);
    const [c0] = r.cards;
    for (const c of r.cards) {
      if (!near(c.x, c0.x) || !near(c.w, c0.w)) throw new Error(`${c.id} is out of the column: x ${c.x} w ${c.w}, want x ${c0.x} w ${c0.w}`);
      if (c.z !== 'auto' || c.transform !== 'none' || c.marginLeft !== '0px')
        throw new Error(`${c.id} carries desktop spread styles: z-index ${c.z}, transform ${c.transform}, margin-left ${c.marginLeft}`);
    }
    for (let i = 1; i < r.cards.length; i++) {
      const tuck = r.cards[i].y - r.cards[i - 1].bottom;
      if (!near(tuck, -40, 1)) throw new Error(`${r.cards[i].id} starts ${tuck}px from ${r.cards[i - 1].id}'s foot; the column tucks each sheet 40px`);
    }
    await centre(card(TWIN));
    const rc = await readRow(page);
    const f4 = rc.cards[2], tw = rc.cards[3];
    if ((await hit(tw.x + tw.w / 2, f4.bottom - 20)) !== TWIN) throw new Error("the twin's sheet does not lie over F4's foot");
    log(`J6 phone: one column ${ids.join(' | ')}, every card at x ${c0.x.toFixed(1)} and ${c0.w.toFixed(1)}px wide; ` +
      'no z-index, no transform, no sideways margin; each sheet tucks 40px under the next, the later sheet on top');
    await shot('phone');
    return;
  }

  // J1 (R1.1, R4.2): one flat row in board order, equal widths, 40% overlap, filling the row.
  await open('/leaderboard');
  await noDecks();
  const r0 = await readRow(page);
  const ids = r0.cards.map(c => c.id);
  if (JSON.stringify(ids) !== JSON.stringify(ORDER)) throw new Error(`row: ${ids.join(', ')}`);
  if (r0.display !== 'flex' || r0.flexDir !== 'row') throw new Error(`the live row is ${r0.display} ${r0.flexDir}`);
  const w = r0.cards[0].w;
  for (const c of r0.cards) {
    if (!near(c.w, w)) throw new Error(`${c.id} is ${c.w}px wide, SPY ${w}px`);
    if (!near(c.relY, 0)) throw new Error(`${c.id} sits ${c.relY}px below the row's top`);
    if (c.transform !== 'none') throw new Error(`${c.id} is transformed: ${c.transform}`);
    if (c.ariaLabel) throw new Error(`${c.id} still carries a tucked-card label: ${c.ariaLabel}`);
  }
  for (let i = 1; i < r0.cards.length; i++) {
    const step = r0.cards[i].x - r0.cards[i - 1].x;
    if (!near(step, w * (1 - OVERLAP), 0.75)) throw new Error(`${r0.cards[i].id} starts ${step}px after ${r0.cards[i - 1].id}; want ${w * (1 - OVERLAP)}`);
  }
  if (!near(r0.cards[0].x, r0.x) || !near(r0.cards.at(-1).right, r0.right, 0.75))
    throw new Error(`the row does not fill its width: cards ${r0.cards[0].x}–${r0.cards.at(-1).right}, row ${r0.x}–${r0.right}`);
  log(`J1 row: ${ids.join(' | ')} as one flat row; every card ${w.toFixed(1)}px wide, each next one ` +
    `${(w * (1 - OVERLAP)).toFixed(1)}px on (40% overlap); the cards span the row's ${(r0.right - r0.x).toFixed(1)}px exactly; no deck, no peek strip`);

  // J2 (R2.1, R2.2): left covers right; SPY whole and above the pick (A, right next to it).
  const tops0 = await overlapTops(r0);
  if (JSON.stringify(tops0) !== JSON.stringify(ORDER.slice(0, -1))) throw new Error(`on top where cards overlap: ${tops0.join(', ')}`);
  await spyWhole(r0);
  if (!byId(r0).A.current) throw new Error('A is not the default pick');
  log(`J2 stacking, A picked: every overlap shows its left card (${tops0.join(', ')}); SPY is on top at 12 points of its box, its right edge above the picked A`);

  // J3 (R1.3): each card's code and total return lie in its uncovered right 60% and are on top there.
  for (const c of r0.cards) {
    const free = c.x + c.w * OVERLAP;
    for (const [what, b] of [['code', c.code], ['total return', c.ret]]) {
      if (!b) throw new Error(`${c.id}: no ${what} on the card`);
      if (b.x < free - 0.5 || b.right > c.right + 0.5)
        throw new Error(`${c.id}'s ${what} spans ${b.x.toFixed(1)}–${b.right.toFixed(1)}, outside its uncovered ${free.toFixed(1)}–${c.right.toFixed(1)}`);
      if ((await hit(b.x + b.w / 2, b.y + b.h / 2)) !== c.id) throw new Error(`${c.id}'s ${what} is covered`);
    }
    if (c.code.cut) throw new Error(`${c.id}'s code is cut off: ${c.code.text}`);
  }
  log(`J3 readable: every card's code and total return sit in its uncovered right 60%, whole: ${r0.cards.map(c => `${c.code.text} ${c.ret.text}`).join(' · ')}`);

  // Legend stays one row (the earlier revamp's promise; not this phase's criterion).
  const legendTops = await page.locator('[class*="legendItem"]').evaluateAll(els =>
    els.filter(e => e.offsetParent !== null).map(e => Math.round(e.getBoundingClientRect().top)));
  if (legendTops.length !== ORDER.length || new Set(legendTops).size !== 1) throw new Error(`legend rows: ${JSON.stringify(legendTops)}`);
  await shot('spread');

  // Keyboard: a focused card rises just under the pick, so its focus ring shows.
  let focused = null;
  for (let k = 0; k < 80 && focused !== F1; k++) {
    await page.keyboard.press('Tab');
    focused = await page.evaluate(() => {
      const a = document.activeElement;
      return a?.hasAttribute('data-status') && a.getAttribute('href') ? decodeURIComponent(new URL(a.href).searchParams.get('s')) : null;
    });
  }
  if (focused !== F1) throw new Error('Tab never reached the F1 card');
  await page.waitForTimeout(100);
  const rf = await readRow(page);
  const f1 = byId(rf)[F1];
  if ((await hit(f1.x + f1.w * OVERLAP / 2, f1.y + f1.h / 2)) !== F1) throw new Error('the focused F1 card did not rise over its left neighbour');
  if (f1.outline !== 'solid') throw new Error(`the focused F1 card has no focus ring (${f1.outline})`);
  log('focus: Tab onto F1 raises it over the twin on its left, focus ring drawn');
  await page.evaluate(() => document.activeElement?.blur());

  // J4 (R3.1, R3.2, R4.1): pick the twin by its uncovered part. It rises in place with the front
  // shadow; nothing moves or resizes; F4, its original, is exactly as it was.
  await centre(SPY);
  const before = byId(await readRow(page));
  const tw = before[TWIN];
  await page.locator(card(TWIN)).first().click({ position: { x: tw.w * 0.7, y: tw.h / 2 } });
  await page.waitForURL(u => u.searchParams.get('s') === TWIN);
  await page.getByText("Can't be run").first().waitFor();
  await centre(SPY);
  const r2 = await readRow(page);
  const after = byId(r2);
  if (r2.cards.length !== ORDER.length) throw new Error(`the row has ${r2.cards.length} cards after the pick`);
  if (!after[TWIN].current || !after[TWIN].active) throw new Error('the twin is not the current, active card');
  const tops2 = await overlapTops(r2);
  const want2 = ['SPY', 'A', TWIN, TWIN, F1];
  if (JSON.stringify(tops2) !== JSON.stringify(want2)) throw new Error(`on top where cards overlap, twin picked: ${tops2.join(', ')}`);
  await spyWhole(r2);
  if (after[TWIN].shadow !== before.A.shadow || after[TWIN].shadow === before[TWIN].shadow)
    throw new Error(`the twin did not take the front card's shadow: ${after[TWIN].shadow}`);
  if (after.A.shadow !== before[F1].shadow) throw new Error('A kept the front shadow after the pick moved on');
  for (const id of ORDER) {
    const b = before[id], a = after[id];
    if (!near(a.relX, b.relX) || !near(a.relY, b.relY) || !near(a.w, b.w))
      throw new Error(`${id} moved or resized on the pick: x ${b.relX}->${a.relX}, y ${b.relY}->${a.relY}, w ${b.w}->${a.w}`);
    if (a.transform !== 'none') throw new Error(`${id} is transformed after the pick: ${a.transform}`);
    if (id !== 'A' && id !== TWIN && !near(a.h, b.h)) throw new Error(`${id} changed height on the pick: ${b.h}->${a.h}`);
  }
  // Only the tab is taller, by the 12px it reaches over the gap onto the month sheet.
  if (!near(before.A.h - before[F1].h, 12) || !near(after[TWIN].h - after[F1].h, 12))
    throw new Error(`tab heights: A +${before.A.h - before[F1].h}, twin +${after[TWIN].h - after[F1].h}; want +12`);
  const f4b = before[F4], f4a = after[F4];
  if (f4a.z !== f4b.z || f4a.shadow !== f4b.shadow || f4a.current || f4a.active || !near(f4a.h, f4b.h))
    throw new Error(`F4 changed when its twin was picked: z ${f4b.z}->${f4a.z}, shadow ${f4b.shadow}->${f4a.shadow}`);
  log(`J4 twin picked: ?s=${TWIN}; it now covers F4 where they overlap (${tops2.join(', ')}), front shadow on it, SPY still whole; ` +
    `every card's x, y and width unchanged, no transform, only the tab 12px taller; F4 untouched (same place, size, z ${f4a.z}, shadow)`);
  await shot('twin-picked');

  // J5 (R3.3): the pick still drives the checklist and the month sheet, and is the tab into it.
  const months = await page.locator(MONTHS).boundingBox();
  if (!near(after[TWIN].bottom, months.y, 1.5)) throw new Error(`the twin's tab ends at ${after[TWIN].bottom}, the month sheet starts at ${months.y}`);
  // textContent, not innerText: the eyebrow is upper-cased by CSS, and innerText applies that.
  const monthsTitle = (await page.locator('#months-title').textContent()) ?? '';
  const monthsCls = (await page.locator(MONTHS).getAttribute('class')) ?? '';
  if (!monthsTitle.includes('F4+Claude') || !monthsCls.split(/\s+/).includes('bg-teal'))
    throw new Error(`month sheet: "${monthsTitle}" in ${monthsCls}`);
  await page.getByText(/Go-live checklist · F4\+Claude/).first().waitFor();
  if ((await page.locator(MONTHS).getAttribute('data-tab')) !== null) throw new Error('a mid-row tab squared a sheet corner');
  await open('/leaderboard?s=C');
  const r3 = await readRow(page);
  const c = byId(r3).C;
  const tab = await page.locator(MONTHS).getAttribute('data-tab');
  const edge = await page.locator(card('C')).getAttribute('data-edge');
  const m3 = await page.locator(MONTHS).boundingBox();
  if (tab !== 'last' || edge !== 'last' || !near(c.bottom, m3.y, 1.5)) throw new Error(`C picked: data-tab=${tab} data-edge=${edge}, tab ${c.bottom} vs sheet ${m3.y}`);
  const tops3 = await overlapTops(r3);
  if (JSON.stringify(tops3) !== JSON.stringify(['SPY', 'A', F4, TWIN, 'C'])) throw new Error(`on top, C picked: ${tops3.join(', ')}`);
  for (const id of ORDER) {
    const b = before[id], a = byId(r3)[id];
    if (!near(a.relX, b.relX) || !near(a.w, b.w)) throw new Error(`${id} moved when C was picked`);
  }
  log('J5 panels: twin picked -> month sheet "' + monthsTitle.replace(/\s+/g, ' ') + '" in teal, checklist on F4+Claude, ' +
    'its tab meets the sheet; C picked -> data-tab=last, data-edge=last, its tab meets the sheet, C covers F1 where they overlap');
  await shot('last-tab');

  // Motion only without reduced motion.
  const durations = () => page.locator(card('C')).evaluate(e => getComputedStyle(e).transitionDuration);
  const moving = d => d.split(',').some(x => parseFloat(x) > 0);
  if (!moving(await durations())) throw new Error('no shadow transition on the spread cards');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  if (moving(await durations())) throw new Error('cards still animate under prefers-reduced-motion');
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  log('motion: the front shadow fades in, and snaps under prefers-reduced-motion');
};
```
**Impact:** the old stack step is gone; the feature map (Step 6) points at this file.

### Step 6: Update the feature-map entry
**File:** `.claude/skills/verify-seer/features/leaderboard.md:10`, `:30-32`, `:51-53`

**Change 6a** (`:10`): replace the bullet that starts `- Desktop (≥ 1024 px) card row as decks:` with
**Code:**
```markdown
- Desktop (≥ 1024 px) card row as one spread (owner, 2026-11-12): every live card in board order, all the same width, each laid over the left 40% of the card to its right ("left covers right"), the row filling its width exactly with no scroll. SPY, the baseline, is always on top and nothing ever covers it. A card's code, chips, total return and metrics sit right-aligned in its uncovered right 60%, with its icon top-left. Clicking a card picks it: it rises above every card but SPY in its own place, with the front card's shadow (cast up and sideways, never onto the month sheet), and no card moves or resizes except that the pick is the tab into the month-by-month sheet. A Claude twin is an ordinary card: picking it leaves its original exactly as it was. A keyboard-focused card rises just under the pick so its focus ring shows. The shadow fade is CSS only and off under `prefers-reduced-motion`. Codes show whole, chips stay inside the card, the chart legend is one row. Below 1024 px the cards are the same column as before.
```
**Change 6b** (`:30-32`): replace the three `leaderboard-stack.mjs` lines with
**Code:**
```sh
$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-spread.mjs --width 1440 --theme light
                                # SPY | A | F4 | F4+Claude | F1 | C one flat row, 40% overlap, filling the row; left covers right,
                                # SPY whole; codes and returns in each card's right 60%; Tab raises a focused card; picking the
                                # twin raises it in place (front shadow, F4 untouched, nothing moves); ?s=C gives data-tab=last; result: PASS
$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-spread.mjs --width 1280
$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-spread.mjs --width 390
                                # phone: the unchanged column, each sheet tucked 40px under the next; result: PASS
```
**Change 6c** (`:51-53`): replace the last three gotchas (`- At desktop width a card shows its code
whole…`, `- A tucked twin's face is covered…`, `- Picking a twin's deck adds a column…`) with
**Code:**
```markdown
- At desktop width a card shows its code whole in its uncovered right 60%: `F4+Claude` breaks after the `+` onto two lines, never `F4+…`. The full name and description are the tooltip.
- Where cards overlap only the top one takes a click, so a desktop Playwright click on a card must land in its right 60% (`click({ position: { x: width * 0.7, y: height / 2 } })`): its left 40% belongs to the card on its left unless it is the pick.
- When the pick is not the card right after SPY, it covers its left neighbour's right 40%, code and return included; only that neighbour's middle 20% shows while the pick is in front. That is the agreed cost of raising a card in place; the neighbour keeps its name as a tooltip.
- The picked card is 12px taller than the rest (its tab reaches over the gap onto the month sheet); every other card keeps its exact place and size on a pick. Measure card positions relative to the row: the checklist above can change height with the pick and move the whole row.
```
**Impact:** documentation only; the verifier reads these commands.

## Principles applied

- Subtract before you add: Steps 1-3 delete `stacks`, its tests, `deck()`, `place`/`tucked`/`.peek`/`isOpen`/`rowCols` and Step 4 deletes every `.deck`/`.peek`/`--peek`/`--lift`/`--depth` rule before the spread rules are written; nothing of the deck path survives as a dead branch.
- Laziness protocol: the row is `live` as it already comes (`orderTwins` order), no new grouping; the stacking order is a three-way expression in a component-local `spreadZ`, not a new exported helper or client component; the existing `.cardActive` tab, fillets and `data-edge`/`data-tab` are reused unchanged except for one dropped `z-index`.
- Make illegal states unrepresentable: the raise is derived from the pick on every render (`spreadZ` reads `pick`), never stored, so a card cannot be raised without being the pick; `--z` is a custom property read only by a ≥1024px rule, so the phone column cannot pick up desktop stacking.
- Prove it works / Test behavior, not implementation: the proof is the rendered page's own hit testing (`elementFromPoint` at the overlap points) and measured boxes, not class names or z-index numbers; no unit test replaces the deleted `stacks` tests because there is no grouping logic left to unit-test.
- Sequence into verifiable units: Steps 1-3 end in `tsc` + vitest; Step 4 is proved by Step 5's journeys at 1440, 1280 and 390.

## Verification

**Build:** `cd /home/miftah/.worktrees/seer/leaderboard-card-spread/web && npx tsc --noEmit`
**Tests:** `cd /home/miftah/.worktrees/seer/leaderboard-card-spread/web && npm test`
(If `web/node_modules` is missing in the worktree: `cp -al /home/miftah/seer/web/node_modules /home/miftah/.worktrees/seer/leaderboard-card-spread/web/node_modules` — a hard-linked copy, never a symlink — or `npm ci`.)
**Proof:** the real page, signed in, on demo data, driven by Playwright through verify-seer.
- Harness: `.claude/skills/verify-seer` (`scripts/verify.sh`). From the worktree root:
  ```sh
  cd /home/miftah/.worktrees/seer/leaderboard-card-spread
  V=.claude/skills/verify-seer/scripts/verify.sh
  $V up                     # prints RUN=...; use it below. Run `up` AFTER the code is in place: the web snapshot is taken at up.
  $V doctor $RUN            # must not warn "working tree changed since up"
  ```
- Feature-map entries: `.claude/skills/verify-seer/features/leaderboard.md`
- Journeys (each `ui` run writes `~/.local/state/seer-verify/$RUN/evidence/NN-ui-leaderboard-spread.txt`; grep the `J{k}` line and `result: PASS`):
  - **J1** · traces R1.1, R4.2 — `$V ui $RUN .claude/skills/verify-seer/features/steps/leaderboard-spread.mjs --width 1440 --theme light` and again with `--width 1280` → passes when each transcript has a line starting `J1 row: SPY | A | F4-MOM12-N20-TREND | F4-MOM12-N20-TREND-CX | F1-SPY-SMA200-M | C as one flat row` stating equal card widths, a step of 60% of the width, the cards spanning the row exactly and "no deck, no peek strip", and ends `result: PASS` (the harness also fails on any horizontal scroll)
  - **J2** · traces R2.1, R2.2 — same two runs → passes when each transcript has `J2 stacking, A picked: every overlap shows its left card (SPY, A, F4-MOM12-N20-TREND, F4-MOM12-N20-TREND-CX, F1-SPY-SMA200-M)` and "SPY is on top at 12 points of its box, its right edge above the picked A"
  - **J3** · traces R1.3 — same two runs → passes when each transcript has `J3 readable: every card's code and total return sit in its uncovered right 60%, whole:` followed by six code/return pairs, and the `NN-ui-leaderboard-spread-1-spread.png` screenshot shows each card's code and return readable in its right part
  - **J4** · traces R3.1, R3.2, R4.1 — same two runs → passes when each transcript has `J4 twin picked: ?s=F4-MOM12-N20-TREND-CX; it now covers F4 where they overlap (SPY, A, F4-MOM12-N20-TREND-CX, F4-MOM12-N20-TREND-CX, F1-SPY-SMA200-M), front shadow on it, SPY still whole; every card's x, y and width unchanged, no transform, only the tab 12px taller; F4 untouched`
  - **J5** · traces R3.1, R3.3 — same two runs → passes when each transcript has `J5 panels: twin picked -> month sheet "Month by month · F4+Claude…" in teal, checklist on F4+Claude, its tab meets the sheet; C picked -> data-tab=last, data-edge=last, its tab meets the sheet, C covers F1 where they overlap`
  - **J6** · traces R1.2 — `$V ui $RUN .claude/skills/verify-seer/features/steps/leaderboard-spread.mjs --width 390` → passes when the transcript has `J6 phone: one column SPY | A | F4-MOM12-N20-TREND | F4-MOM12-N20-TREND-CX | F1-SPY-SMA200-M | C` with "no z-index, no transform, no sideways margin; each sheet tucks 40px under the next, the later sheet on top" and `result: PASS`
  - **J7** · traces R1.1, R1.3, R2.2, R3.1 — `$V shoot $RUN --theme light --width 1440 /leaderboard '/leaderboard?s=F4-MOM12-N20-TREND-CX'`, then `$V shoot $RUN --theme dark --width 1440 /leaderboard '/leaderboard?s=F4-MOM12-N20-TREND-CX'`, then `$V shoot $RUN --theme dark --width 390 /leaderboard` → passes when all three exit 0 and the PNGs in `evidence/NN-shoot-*/` show, at 1440 in both themes, one flat spread with SPY whole on the left, each card's code and return readable in its right part, a visible edge shadow between overlapping cards, and on the twin URL the twin in front with a shadow on its sides and its tab running into the teal month sheet; and at 390 dark the same stacked column as before (compare with the 390 shot recipe in `leaderboard.md`)
- Neighbor check (traces nothing): `$V ui $RUN .claude/skills/verify-seer/features/steps/leaderboard-twin.mjs` (1280 dark; its desktop click lands at the twin's horizontal middle, inside its uncovered part) and `$V ui $RUN .claude/skills/verify-seer/features/steps/leaderboard-switch-row.mjs --width 1280` → both end `result: PASS`. Then `$V down $RUN`.
- Before the fix (optional, shows the journey can fail): the same spread step run against `origin/main` @ 650b355 fails at J1 (the row is a grid of decks, and the twin card is tucked behind F4, so the 40%-step check throws).
- Cost: none. Offline, no `--llm`, no `--net`.
**Exit criteria:** `npx tsc --noEmit` and `npm test` green in `web/`; `leaderboard-spread.mjs` PASS at `--width 1440 --theme light`, `--width 1280` and `--width 390`; `leaderboard-twin.mjs` and `leaderboard-switch-row.mjs --width 1280` PASS; the three shoots exit 0 and their PNGs match the approved prototype's left-covers-right look; `git grep -nE "stacks\(|data-deck|\.deck|\.peek|--peek|--lift|--depth|leaderboard-stack" -- web .claude` prints nothing.

## Handoffs

- `web/package_readme.md:4` describes `stacks()`, decks, `rowCols` and `leaderboard-stack.mjs`. Left for the readme-updater / completion-handler that runs after this phase (not a source file this phase owns).
- `.claude/skills/verify-seer/features/steps/leaderboard-twin.mjs:76-78` still says "At desktop width the twin is tucked behind F4 and only its top edge shows: click that strip." The click it makes (`x: width / 2, y: 3`) still lands on the twin's uncovered part, so it passes unchanged; the comment is stale. Out of this phase's owned files: a follow-up should reword it (e.g. "At desktop width F4 covers the twin's left 40%: click its middle").
- `RetiredShelf.tsx:19` documents `cols` as "How many live cards share the row above: the shelf's desktop grid keeps their column width." With the spread, a live card is wider than `row / n`, so the shelf's columns no longer match the live cards' width; only the count matches. The plan index forbids touching `RetiredShelf.tsx`; a follow-up should reword the doc or decide a new shelf width.
- R1.2 says "with no overlap". The existing phone column tucks each sheet 40px under the next (`.over`, globals.css), which is vertical overlap by design and must stay (invariant 2). J6 proves no sideways overlap and the unchanged 40px tuck. Reconciler: read R1.2's "no overlap" as "no spread overlap".
- R1.3 holds in full while the pick is the card right after SPY (the default). When the pick sits further right, it covers its left neighbour's code and return by the index's Decision 3 ("Accepted"). J3 measures the default state; the gotcha in `leaderboard.md` records the trade-off.

## Rollback

Revert the phase's single commit (`git revert <sha>`): it restores `stacks()` and its tests, the deck markup and CSS, `leaderboard-stack.mjs` and the decks text in `leaderboard.md`. No data, schema or engine change is involved.
