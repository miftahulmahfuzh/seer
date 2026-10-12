> Adopted from `/home/miftah/seer/.workflows/orchestration/sera-responsive/PLAN.md` phase 4. Source: `.workflows/plan/sera-responsive/phase-4.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 4: `/sera/methods/[id]`: the variants table, same treatment

**Plan set:** `SERA_RESPONSIVE_PLAN.md`
**Analysis:** `docs/analyzer/20261012-165855-R4C9_code_analyzer.md`
**Satisfies:** R1 (a designed narrow layout for the method page) — and **holds** R2 on
`/sera/methods/[id]` at 390/414/1280, a number phases 1 and 2 moved and this phase must not spend
**Depends on:** Phase 1 (the narrow nav), Phase 2 (`Term`'s containing-block fix)
**Difficulty:** HARD
**Package:** `web/app/sera/methods/[id]`
**Port:** 3124

---

## Goal

Below 1024px the variants table stops being a 1240px, 17-column scroller and becomes one card per
variant, carrying every measure the row carried but ordered for a 282px-wide reading column. At
1024px and above the table renders byte for byte as it does today. The page's markdown-table
scrollers stop being 965px wide for want of a line break, and the `Redone realistically` block
stacks across the whole narrow band instead of only below 544px.

---

## Measurements this plan is built on

Taken in this worktree at `09515d1`, on `next dev -p 3124`, signed in through
`scripts/session.mjs`, with phase 2's one-line fix simulated live
(`span[class*="Term-module"][class*="term"] { position: relative }`) so the numbers are what phase
4 actually inherits. Probe scripts were written under `web/scripts/_probe4*.mjs`, run, and
deleted; the tree is clean.

**`document.documentElement.scrollWidth` with phase 2 applied** — every method page is already at
**456 (the nav, phase 1's)** and nothing on this page contributes:

| route | before phase 2 @390 | after phase 2 @390 | after phase 2 @414 |
|---|---:|---:|---:|
| `/sera/methods/M0102` | 848 | **456** | **456** |
| `/sera/methods/M0007` | 821 | **456** | **456** |
| `/sera/methods/M0084` | 852 | **456** | **456** |
| `/sera/methods/M0040` | 456 | **456** | **456** |

The only unclipped offenders left at 390 and 414 on all four are
`a[icon-btn SeraNav.back] right=456` and the 441px chevron `<svg>` inside it. **Both are phase 1's
nav.** So every change in this phase is R1 work; R2 on this route is already paid for by phases 1
and 2, and the exit criterion is that phase 4 does not spend it.

**The five horizontal scrollers on this page, each checked at 390 and 414:**

| scroller | position | client / scroll @390 | abs-positioned descendants | verdict |
|---|---|---|---|---|
| `.tableWrap` (variants) | static | 326 / 1240 | 8–9 (the header `Term.sr` spans) | **replaced** — hidden below 1024px, so it stops being a scroller at all |
| `.prose [data-md-table]` | static | 314 / up to **965** | **0** | contained, but unreadable — one line of CSS, below |
| `.config` | static | — | 0 | **nothing needed**, proven below |
| `charts/*` (`.figure`, `.svg`) | — | — | — | **nothing needed**, and not mine |
| the nav's own | — | — | — | phase 1's |

- **`.config` never scrolls sideways.** It is `overflow: auto`, but `white-space: pre-wrap` +
  `overflow-wrap: anywhere` + `max-height: 360px` make it a *vertical*-only scroller. Probed at
  390 with every `<details>` on the page forced open: no `.config` appears among the elements
  whose `scrollWidth > clientWidth`. It is correct as it stands and this phase does not touch it.
- **The prose markdown tables cannot have phase 2's bug.** `lib/sera/markdown` renders
  escape-first HTML; no `<Term>` ever reaches the prose, and the probe confirms **0**
  absolutely-positioned descendants inside every one of them on all three sample pages. A
  `position: relative` guard here would be the duplicate fix the analysis argued against (§"The fix
  the plan takes: one line, in `Term`, not in each scroller"). **No guard is added.**
- **The charts are clean.** `.figure { min-width: 0 }` and `.svg { width: 100%; height: auto }`
  already do the job; no chart element is an unclipped offender at either width. `components/sera/charts/*`
  is outside this phase's scope anyway.

**The one prose measurement that justifies a change.** `method.module.css:85` puts
`white-space: nowrap` on every prose cell. Applying `white-space: normal` below 1024px, measured
live:

| page | prose scrollers @390 before | after |
|---|---|---|
| `M0084` | 7 scrollers: 630, 470, 462, 630, 470, 462, **850** | 2 scrollers: 364, 364 |
| `M0007` | 3 scrollers: **965**, 421, 917 | 1 scroller: 633 |
| `M0102` | 2 scrollers: 727, 727 | 2 scrollers: 352, 352 |

The document stays 456 in every case — this buys nothing for R2 and a great deal for R1. The
residual scrollers are tables with genuinely wide content and still contain themselves.

**The three extra method pages, chosen by reading `web/data/lab.json` for different shapes:**

| id | why it was picked |
|---|---|
| **M0007** | has a `Redone realistically` block (its child `M0032` was run on deposits), 5 variants, 18 markdown-table lines in its analysis, **unfunded** — so the variants table is 11 columns + 6 marks |
| **M0084** | **funded** (`mwr` present), so the `What your money earned` column appears — 12 columns + 6 marks, the widest the table ever gets; 6 variants; **73** markdown-table lines, the heaviest prose in the lab |
| **M0040** | **Not tested yet** (`status: blocked-data`, 0 trials) — no charts, no variants table, and it prints the `Waiting on:` line; the shape where this phase must change nothing |

`M0102` stays in the set as the plan's own baseline route.

---

## Interface Contract

**Deletes:** `@media (max-width: 34rem)` block (`app/sera/methods/[id]/method.module.css:173-176`)
— its two declarations move into the file's new `@media (max-width: 1023.98px)` block.

**Renames:** none.

**Creates:**
- `app/sera/methods/[id]/page.tsx` — `VariantCard` (new local component, file-private)
- `app/sera/methods/[id]/method.module.css` — new local classes. The seven that name an idea
  `/sera/methods` also has take **phase 3's spelling**, so the two pages read as one design:
  `.cards`, `.card`, `.cardHead`, `.stats`, `.stat`, `.statLabel`, `.statValue`. The rest name
  pieces only a variant card has: `.vName`, `.vBest`, `.vWhen`, `.vLead`, `.vLeadLabel`,
  `.vLeadValue`, `.vLeadVs`, `.vNote`, `.vMore`, `.vMoreItem`, `.vMarks`, `.vMark`. CSS modules are
  scoped, so the shared names cannot collide with phase 3's; neither name is new to this file
  (checked: `method.module.css` has no `.card`, `.cards`, `.stat*` today).
- `app/sera/methods/[id]/method.module.css` — a new `@media (max-width: 1023.98px)` block (the
  file has none today). It is this file's **only** narrow breakpoint and carries every rule this
  phase adds, card styles included.

**Signature changes:**
- `MarkIcon({ mark, size })` -> `MarkIcon({ mark, size, decorative? })` — **local to
  `[id]/page.tsx`, not exported, not shared with phase 3.** `decorative` defaults to `false`, so
  both existing call sites are unchanged.

**DOM shape introduced (for the reconciler to align with phase 3):**

```
<Section eyebrow="Variants">                      (unchanged)
  <div class="{tableWrap} desk-only">             ← the existing table, wrapper gains one class
    <table class="{table}"> …unchanged… </table>
  </div>
  <ul class="{cards} mobile-only">              ← same names phase 3 uses for the same ideas
    <li class="{card}" data-best="true">         ← data-best replaces the table's .bestRow
      <div class="{cardHead}">  {vName}  span.chip.{vBest}  </div>
      <div class="{vWhen}">  span.{window}  windowText  </div>
      <div class="{vLead}">  {vLeadLabel} {vLeadValue} {vLeadVs}  </div>
      <dl class="{stats}">   4 × div.{stat} > dt.{statLabel} + dd.{statValue}  </dl>
      <p  class="{vMore}">   3–4 × span.{vMoreItem}  </p>
      <ul class="{vMarks}">  6 × li.{vMark} > MarkIcon(decorative) + text  </ul>
    </li>
  </ul>
</Section>
```

**Requires (from earlier phases):**
- Phase 2: `components/sera/Term.module.css` gives `.term { position: relative }`. Without it this
  page measures 848 at 390 regardless of anything phase 4 does. Phase 4 does **not** re-fix it.
- Phase 1: the nav no longer measures 456px wide. Without it every route here reports 66px of
  scroll at 390 and 42px at 414, and that is not a phase-4 failure.

**Leaves alone (owned by others):**
- `app/sera/methods/view.ts` and `view.test.ts` — **frozen**, shared with phase 3. Nothing in this
  plan adds, changes or re-exports anything there; every derived value the cards need is either
  already exported or computed inline in `page.tsx`.
- `app/sera/methods/methods.module.css`, `app/sera/methods/page.tsx` — phase 3
- `components/sera/Term.*` — phase 2
- `components/sera/Section.*`, `components/sera/PageHeader.*`, `app/sera/sera.module.css` — phase 1
- `components/sera/charts/*`, `components/sera/diagrams/*`, `app/globals.css` — phase 5 / read-only
  precedent. `.desk-only`, `.mobile-only`, `.chip`, `.num` are **used as they are**; nothing is
  added to `globals.css`.

---

## The card's information hierarchy — the decision, and why

The desk table is 17 columns at 1240px (18 on a funded method), and **every cell takes its whole
meaning from the header row above it**. At 390 the reading column inside the sheet is 314px
(measured), 282px inside a card. Two columns fit. So the card is not a narrower table; it is a
re-ranked one.

**Nothing in the row is dropped.** Every measure the table prints appears on the card. What
changes is prominence, in five tiers:

| tier | carries | why |
|---|---|---|
| 1 — head | variant name (`candidateId`), **Best** chip | identity, and the `.bestRow` highlight made legible (below) |
| 2 — when | the `Dev`/`Test` window chip + `1993–2015` | it was column 2 on the desk; it stays a chip, reusing the existing `.window` rule unchanged |
| 3 — lead | **the measure the SPY hurdle is actually decided by**, big: growth a year vs SPY, or — on a funded run — what the money earned vs the same deposits in SPY | see below |
| 4 — grid, 2×2 | **Max DD, PF, Trades, DSR** — the four hurdles that have a number | a principled cut, not an arbitrary one: these are exactly the gate's numeric hurdles. `spy` is the lead; `owner` has no number |
| 5a — `.vMore`, one wrapping line | **Return, Sharpe, MAR** (and a blanked *Growth a year* on a funded run) | demoted because **no hurdle reads them**. They are context, so they get context's weight |
| 5b — `.vMarks` | the six condition marks, **each with its label printed** | on a desk these are bare centred icons under a `.c` column header. A card has no header above them, so six unlabelled glyphs would mean nothing. This is the one place the card carries *more* than the cell |

**Why the lead switches on funding.** `view.conditionSentence('spy', …)` already decides this, and
says why in its own comment: *"a funded run is judged on what its money earned … its `cagr` is not
a yearly return once deposits keep arriving"*. The `RedonePanel` on this same page makes the same
split in prose. Leading a funded card with `cagr` would headline a number the engine did not judge
it by. So:

- unfunded → label `Growth a year`, value `pct1(t.cagr)`, sub `vs 7.9% from SPY with dividends`
- funded → label `What your money earned`, value `earned(t)`, sub
  `vs +7.1% from the same deposits in SPY` — the `RedonePanel`'s own wording (invariant 8)

**The two blanked cells survive.** On a funded run the table blanks *Growth a year* and *Return*
and hangs `DEPOSITS_TIP` on them. The card keeps both blanks, in `.vMore`, with the same tooltip —
the honest-blanking message is the point, and dropping the blanks would lose it.

**How `.bestRow` survives.** The table paints the best row `var(--butter)` with rounded ends and
leans on the caption "The best variant is highlighted." A card is round already, so:

1. `.card[data-best='true'] { background: var(--butter); }` — same token, same wash. The
   `data-` attribute rather than a second class is this codebase's own idiom
   (`journal.module.css:44`, `.card[data-unseen='true']`).
2. **plus a named chip** reading **Best** with a `Star` icon, because on a phone a tint alone is
   not a label — the two cards either side of it may be off-screen, so there is nothing to
   contrast against. Its `data-tip` says what "best" means in plain words:
   *"Of this method's development runs, the one that missed the fewest hurdles. It is the run the
   verdict above is written about."* (That is `derive.bestVariant`: dev trials first, fewest
   misses, then MAR, then `n`.)

**The labels are spelled out, and carry no `<Term>`.** The desk table says `Max DD` / `PF` / `DSR`
because of its measured column budget and buys the meaning back with a `<Term>` tooltip. A card has
no such budget, so it prints the glossary's own plain words instead — `Max drawdown`,
`Profit factor`, `Luck check` (`GLOSSARY.maxDrawdown.term`, `GLOSSARY.profitFactor.term`,
`derive.CONDITION_LABEL.dsr`) — and the `<T>` wrapper comes off every label on the card, in the
lead, the stat grid and the `.vMore` line alike. This is phase 3's rule on `/sera/methods`, applied
here so the two pages speak the same way; phase 3 cannot go the other direction, because its card
is one card-wide link and a `<Term>`'s `tabIndex={0}` span under that overlay is both unreachable
and a focus trap. `<T>` stays exactly as it is in the desk table's `<th>`s, so the import is still
used and 1280 is unchanged.

**Invariant 8.** No copy is clamped or truncated anywhere on the card. `.vName` gets
`overflow-wrap: anywhere` so a long `candidateId` breaks instead of pushing the card wide; it is
an id, not a sentence.

---

## Files

| File | Action | What changes |
|---|---|---|
| `web/app/sera/methods/[id]/page.tsx` | modify | `Star` + `Gate` imports; `MarkIcon` gains an optional `decorative` prop; the Variants `<Section>` body becomes table-plus-cards; new `VariantCard` component |
| `web/app/sera/methods/[id]/method.module.css` | modify | one new `@media (max-width: 1023.98px)` block appended at the end of the file, carrying the card styles, the prose-cell wrap and the two rules moved out of the deleted `34rem` query |

No other file in the repo is touched. No test file imports this page (`find web -name '*.test.ts*'`
→ the only `/sera/methods` test is `view.test.ts`, which imports `./view` and nothing else).

---

## Implementation Steps

### Step 1: two imports

**File:** `web/app/sera/methods/[id]/page.tsx:1` and `:19`

**Change:** add `Star` to the Lucide import (alphabetical, after `Hash`), and `Gate` to the types
import (alphabetical, before `LabMethod`).

**Code:** line 1 becomes

```tsx
import { CalendarClock, CalendarPlus, Check, ChevronRight, CircleDashed, ExternalLink, GitFork, Hash, Star, X } from 'lucide-react';
```

line 19 becomes

```tsx
import type { Gate, LabMethod, LabTrial } from '@/lib/sera/types';
```

**Impact:** none at runtime. `Gate` is already what `lab.gate` is typed as, and `view.ts` imports
it from the same module, so no new dependency edge.

---

### Step 2: `MarkIcon` can render decoratively

**File:** `web/app/sera/methods/[id]/page.tsx:179-187`

**Change:** the card prints each mark's label as visible text, so the icon beside it must not also
announce it — a screen reader would otherwise hear *"Beats SPY: cleared. Beats SPY: cleared."*
`decorative` defaults to `false`, so the two existing call sites (`.worked` at line 300 and the
table cell at line 447) keep their exact current behaviour.

**Code — replace the whole function:**

```tsx
/**
 * A condition mark: tick, cross, or a dashed circle for a hurdle that does not apply.
 *
 * `decorative` is for the places that print the mark's label as visible text right beside it —
 * the narrow-width variant cards. There the icon is a picture of a sentence the reader can
 * already read, so it is hidden from assistive tech rather than announced twice.
 */
function MarkIcon({ mark, size, decorative = false }: { mark: Mark; size: number; decorative?: boolean }) {
  const label = markLabel(mark);
  const cls = mark.ok === true ? s.ok : mark.ok === null ? s.na : s.no;
  const glyph = mark.ok === true ? <Check size={size} /> : mark.ok === null ? <CircleDashed size={size} /> : <X size={size} />;
  if (decorative) {
    return <span className={cls} aria-hidden="true" data-tip={label}>{glyph}</span>;
  }
  return (
    <span className={cls} role="img" aria-label={label} data-tip={label}>
      {glyph}
    </span>
  );
}
```

**Impact:** no visual or accessibility change to anything that exists today.

---

### Step 3: the Variants section renders two presentations

**File:** `web/app/sera/methods/[id]/page.tsx:373-455` (the whole
`<Section eyebrow="Variants" …>…</Section>` inside `Tested`)

**Change:** the existing `<div className={s.tableWrap}>` gains `desk-only`, and a `<ul>` of cards
gains `mobile-only`. The table itself — every `<th scope>`, every cell, the `funded` column, the
`.bestRow` class, the comments — is **byte for byte what it is today**.

**Code — replace lines 373-455 with:**

```tsx
      <Section eyebrow="Variants" title="Every variant"
        caption={`One row per test run. A tick means the hurdle was cleared. The best variant is highlighted.${
          funded ? ' Some runs here had money added every month, so their return and growth-a-year cells are left blank: with deposits arriving, neither is a return. What that money actually earned has a column of its own.' : ''}`}
        className={s.chartSheet}>
        {/* One list, two presentations, switched at 1024px by globals' .desk-only / .mobile-only
            pair -- the idiom components/Nav.tsx already uses for its two navs. Those classes set
            `display: none !important`, so exactly one of the two is in the accessibility tree at
            any width (plan invariant 10): the table keeps its scope attributes for a desk reader,
            and the cards carry their own labels for a phone one. A 1240px table of 17 columns
            whose every cell takes its meaning from the header row is not readable on a 390px
            screen even inside a working scroller, which is why the phone gets cards instead of a
            narrower table. */}
        <div className={`${s.tableWrap} desk-only`}>
          <table className={s.table}>
            <thead>
              <tr>
                <th scope="col">Variant</th>
                <th scope="col">Window</th>
                <th scope="col" className={s.r}><T k="cagr">Growth a year</T> vs SPY</th>
                <th scope="col" className={s.r}><T k="return">Return</T></th>
                {funded && (
                  <th scope="col" className={s.r}><T k="mwr">What your money earned</T> vs SPY</th>
                )}
                <th scope="col" className={s.r}><T k="maxDrawdown">Max DD</T></th>
                <th scope="col" className={s.r}><T k="profitFactor">PF</T></th>
                <th scope="col" className={s.r}><T k="trades">Trades</T></th>
                <th scope="col" className={s.r}><T k="sharpe">Sharpe</T></th>
                <th scope="col" className={s.r}><T k="mar">MAR</T></th>
                <th scope="col" className={s.r}><T k="dsr">DSR</T></th>
                {CONDITION_KEYS.map(k => (
                  <th key={k} scope="col" className={s.c}>
                    <span data-tip={conditionTip(k, gate)}>{CONDITION_LABEL[k]}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trials.map(t => {
                const note = dsrNote(t, gate);
                // The two cells the deposits inflate. They are blanked rather than printed,
                // because a funded run's +1078% is mostly the owner's own money arriving and
                // putting it in the same column as an unfunded run's return invites exactly the
                // comparison that is not true.
                const money = moneyWeighted(t);
                return (
                  <tr key={t.n} className={t.n === best.n ? s.bestRow : undefined}>
                    <th scope="row" className={s.variant}>{t.candidateId}</th>
                    <td><span className={s.window} data-window={t.window}>{t.window === 'dev' ? 'Dev' : 'Test'}</span> {windowText(t)}</td>
                    <td className={s.r}>
                      {money ? (
                        <span className="num" data-tip={DEPOSITS_TIP}>—</span>
                      ) : (
                        <>
                          <span className="num">{pct1(t.cagr)}</span>
                          <span className={s.vs}> vs {pct1(t.spyTrCagr)}</span>
                        </>
                      )}
                    </td>
                    <td className={`num ${s.r}`}>
                      {money ? <span data-tip={DEPOSITS_TIP}>—</span> : signed1(t.totalReturn)}
                    </td>
                    {funded && (
                      <td className={s.r}>
                        <span className="num">{earned(t)}</span>
                        {earnedVs(t) !== null && <span className={s.vs}> {earnedVs(t)}</span>}
                      </td>
                    )}
                    <td className={`num ${s.r}`}>{pct1(t.maxDrawdown)}</td>
                    <td className={`num ${s.r}`}>{pfText(t)}</td>
                    <td className={`num ${s.r}`}>{count(t.trades)}</td>
                    <td className={`num ${s.r}`}>{fixed(t.sharpe, 2)}</td>
                    <td className={`num ${s.r}`}>{fixed(t.mar, 2)}</td>
                    {/* The score at today's N, beside ticks decided at today's N — but only where
                        today's N is the N it was scored at. A test run's DSR is a measurement with
                        no bar beside it, so it is annotated as such rather than as `at N 126`. The
                        run-date pair (t.dsr at t.nTrialsAtRun) is the record and lives in
                        Technical detail. */}
                    <td className={`num ${s.r}`}>
                      {fixed(t.dsrNow, 2)}
                      {note !== null && <span className={s.vs}> {note}</span>}
                    </td>
                    {marks(t).map(x => (
                      <td key={x.key} className={s.c}><MarkIcon mark={x} size={14} /></td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <ul className={`${s.cards} mobile-only`}>
          {trials.map(t => (
            <VariantCard key={t.n} t={t} gate={gate} isBest={t.n === best.n} />
          ))}
        </ul>
      </Section>
```

**Impact:** at ≥1024px the rendered output is identical (one extra class name on a wrapper that
`@media (min-width: 1024px)` makes a no-op, and a `<ul>` that is `display: none !important`).
Below 1024px the table leaves the accessibility tree and the cards enter it. The hidden
presentation's markup still ships in the HTML at both widths — the same cost `components/Nav.tsx`
already pays for its two navs, and at 5–6 variants per page it is a few hundred bytes.

---

### Step 4: the `VariantCard` component

**File:** `web/app/sera/methods/[id]/page.tsx` — insert immediately after `Tested` closes
(after line 458 as the file stands today), before `function Tech(`.

**Code:**

```tsx
/**
 * One variant, as a card: the phone presentation of a row of the variants table.
 *
 * The desk table is 17 columns at 1240px and every cell takes its whole meaning from the header
 * row above it, so a 390px screen shows two of them and understands neither. The card re-ranks
 * rather than abbreviates: nothing the row prints is dropped. It leads on the measure the SPY
 * hurdle is decided by, gives the four hurdles that have a number a two-up grid, demotes the
 * three measures no hurdle reads (return, Sharpe, MAR) to one compact line, and prints a label
 * beside every condition mark — on a desk those marks borrow their meaning from a column header
 * a card does not have.
 *
 * The labels are the glossary's plain words rather than the table's abbreviations, and carry no
 * <Term>: the table says "Max DD" / "PF" / "DSR" because of a column budget a card does not have,
 * and /sera/methods' cards already spell them out. <T> stays in the desk table's headers.
 *
 * The lead switches on funding for the reason view.conditionSentence('spy') switches: a run that
 * was fed deposits is judged on what its money earned, and its `cagr` is not a yearly return once
 * deposits keep arriving. Leading a funded card with `cagr` would headline a number the engine
 * did not decide the tick by. The two cells the deposits inflate stay blanked, with the same
 * tooltip the table hangs on them, because the blanking is the honest part.
 */
function VariantCard({ t, gate, isBest }: { t: LabTrial; gate: Gate; isBest: boolean }) {
  const money = moneyWeighted(t);
  const note = dsrNote(t, gate);
  return (
    <li className={s.card} data-best={isBest ? 'true' : undefined}>
      <div className={s.cardHead}>
        <span className={s.vName}>{t.candidateId}</span>
        {isBest && (
          <span className={`chip ${s.vBest}`}
            data-tip="Of this method's development runs, the one that missed the fewest hurdles. It is the run the verdict above is written about.">
            <Star size={14} aria-hidden="true" />Best
          </span>
        )}
      </div>

      <div className={s.vWhen}>
        <span className={s.window} data-window={t.window}>{t.window === 'dev' ? 'Dev' : 'Test'}</span>
        <span>{windowText(t)}</span>
      </div>

      <div className={s.vLead}>
        <span className={s.vLeadLabel}>
          {money ? 'What your money earned' : 'Growth a year'}
        </span>
        <span className={`num ${s.vLeadValue}`}>{money ? earned(t) : pct1(t.cagr)}</span>
        <span className={s.vLeadVs}>
          {money
            ? `${earnedVs(t)} from the same deposits in SPY`
            : `vs ${pct1(t.spyTrCagr)} from SPY with dividends`}
        </span>
      </div>

      <dl className={s.stats}>
        <div className={s.stat}>
          <dt className={s.statLabel}>Max drawdown</dt>
          <dd className={`num ${s.statValue}`}>{pct1(t.maxDrawdown)}</dd>
        </div>
        <div className={s.stat}>
          <dt className={s.statLabel}>Profit factor</dt>
          <dd className={`num ${s.statValue}`}>{pfText(t)}</dd>
        </div>
        <div className={s.stat}>
          <dt className={s.statLabel}>Trades</dt>
          <dd className={`num ${s.statValue}`}>{count(t.trades)}</dd>
        </div>
        <div className={s.stat}>
          <dt className={s.statLabel}>Luck check</dt>
          <dd className={`num ${s.statValue}`}>
            {fixed(t.dsrNow, 2)}
            {note !== null && <span className={s.vNote}>{note}</span>}
          </dd>
        </div>
      </dl>

      <p className={s.vMore}>
        {money !== null && (
          <span className={s.vMoreItem}>
            Growth a year
            <span className="num" data-tip={DEPOSITS_TIP}>—</span>
          </span>
        )}
        <span className={s.vMoreItem}>
          Return
          {money !== null
            ? <span className="num" data-tip={DEPOSITS_TIP}>—</span>
            : <span className="num">{signed1(t.totalReturn)}</span>}
        </span>
        <span className={s.vMoreItem}>
          Sharpe<span className="num">{fixed(t.sharpe, 2)}</span>
        </span>
        <span className={s.vMoreItem}>
          MAR<span className="num">{fixed(t.mar, 2)}</span>
        </span>
      </p>

      <ul className={s.vMarks}>
        {marks(t).map(x => (
          <li key={x.key} className={s.vMark}>
            <MarkIcon mark={x} size={14} decorative />
            <span>{markLabel(x)}</span>
          </li>
        ))}
      </ul>
    </li>
  );
}
```

**Impact:**

- Every helper used is already imported by this file: `moneyWeighted` and `CONDITION_LABEL` from
  `@/lib/sera/derive` (line 14); `dsrNote`, `earned`, `earnedVs`, `fixed`, `markLabel`, `marks`,
  `pct1`, `pfText`, `signed1`, `count`, `windowText`, `DEPOSITS_TIP` from `'../view'` (lines
  20-25). **`view.ts` is not read for anything new and is not modified.**
- `markLabel(x)` prints `Beats SPY: cleared` / `Max drawdown: missed` / `Luck check: not
  applicable` — plain language, no ids or codes (invariant 8), and the exact phrase the desk
  table's tooltip already says.
- `<dl>` wrapping each `<dt>/<dd>` pair in a `<div>` is valid HTML and is what `.techGrid` on this
  same page already does.

---

### Step 5: one narrow-width block, carrying the card styles and the two rules the `34rem` query held

**File:** `web/app/sera/methods/[id]/method.module.css`

**Change, in two parts.**

First, **delete** the existing block at `:173-176` (verified: the file is 176 lines and this is the
only `max-width` query in it):

```css
@media (max-width: 34rem) {
  .redoneRow { grid-template-columns: 1fr; }
  .redoneValue { text-align: left; }
}
```

Then **append**, at the end of the file, the single `@media (max-width: 1023.98px)` block below.
One breakpoint per stylesheet: every narrow rule this phase adds lives in it, which makes the
desktop-safety audit one grep — the same convention phase 3 states for `methods.module.css`, and
the reason the card rules are *not* left at the file's top level even though `.cards` only ever
lands on a `mobile-only` element.

**Code — append verbatim:**

```css

/* ---- Below 1024px: the variants, as cards ----------------------------------------------------
   The desk table is 17 columns at 1240px and every cell takes its meaning from the header row
   above it; a 390px screen shows two of them. So below 1024px the same trials render as one card
   each and the table is hidden outright, through globals' .desk-only / .mobile-only pair -- the
   idiom components/Nav.tsx already uses for its two navs. Hiding rather than reflowing is what
   keeps exactly one of the two presentations in the accessibility tree.

   Nothing from the row is dropped. The vocabulary is Sera's own narrow card, the one
   ideas.module.css .card, journal.module.css .card and overview.module.css .card all use: a 28px
   radius on var(--stone) inside the sheet. The class names for the pieces both method pages share
   -- .cards, .card, .cardHead, .stats, .stat, .statLabel, .statValue -- are the names phase 3 gives
   the same ideas on /sera/methods, so the two pages read as one design; the v-prefixed names below
   are only for the pieces a variant card has and a method card does not. CSS modules are scoped, so
   the shared names cannot collide across the two files.

   Desktop cannot drift: nothing in this block applies at >= 1024px. */
@media (max-width: 1023.98px) {
  .cards { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
  .card {
    display: flex; flex-direction: column; gap: 10px;
    padding: 16px 18px 14px; border-radius: 28px; background: var(--stone);
  }
  /* The table's .bestRow highlight, carried across: the same --butter wash (a card is round
     already, so the rounded ends come free) and, beside it, a named chip -- on a phone the cards
     either side may be off-screen, so a tint has nothing to be a contrast against and cannot be
     the only label. The data- attribute rather than a second class is this codebase's own idiom
     (journal.module.css:44, .card[data-unseen='true']). */
  .card[data-best='true'] { background: var(--butter); }

  .cardHead { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
  .vName { font-size: 16px; font-weight: 500; letter-spacing: -0.01em; min-width: 0; overflow-wrap: anywhere; }
  .vBest { flex: none; height: 26px; padding: 0 10px; font-size: 12.5px; background: var(--ink); color: var(--sheet); }

  .vWhen { display: flex; align-items: center; gap: 8px; font-size: 14px; color: var(--ink-2); }

  /* The measure the SPY hurdle is decided by: growth a year, or -- on a run that was fed deposits
     -- what the money earned. */
  .vLead { display: flex; flex-direction: column; gap: 2px; }
  .vLeadValue { font-size: 26px; line-height: 1.1; letter-spacing: -0.02em; }
  .vLeadVs { font-size: 13px; line-height: 1.35; color: var(--ink-2); }

  /* The four hurdles that have a number. Same construction, same metrics and the same small-caps
     label as /sera/methods' card grid (methods.module.css), which took them from
     ideas.module.css .label -- the house measure for a label over a number. */
  .stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 14px; margin: 2px 0 0; }
  .stat { min-width: 0; }
  .vLeadLabel, .statLabel {
    display: block; margin: 0; font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--ink-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  /* margin: 0 first -- a <dd> carries a 40px inline-start margin by default. */
  .statValue { margin: 2px 0 0; font-size: 16px; line-height: 1.2; }
  .vNote { display: block; font-size: 12px; line-height: 1.3; color: var(--ink-2); }

  /* The three measures no hurdle reads, plus whichever cells the deposits blanked. */
  .vMore { margin: 0; display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 13px; color: var(--ink-2); }
  .vMoreItem { display: inline-flex; align-items: baseline; gap: 5px; white-space: nowrap; }
  .vMoreItem :global(.num) { color: var(--ink); }

  /* The six condition marks. On a desk these are bare centred icons under a column header; a card
     has no header above them, so each one prints its own sentence. */
  .vMarks { list-style: none; margin: 0; padding: 10px 0 0; border-top: 1px solid var(--hair); display: grid; gap: 7px; }
  .vMark { display: flex; align-items: center; gap: 9px; font-size: 13.5px; line-height: 1.3; }
  .vMark .ok, .vMark .no, .vMark .na { width: 20px; height: 20px; }

  /* The markdown tables Sera writes into her analysis. Nothing escapes these scrollers -- they
     hold no <Term>, because lib/sera/markdown renders escaped HTML, and the probe counts zero
     absolutely-positioned descendants inside every one of them, so the containing-block bug phase
     2 fixed cannot occur here and a second guard would be the duplicate the analysis argued
     against. What `white-space: nowrap` did do was make a two-column table 965px wide inside a
     314px sheet. Letting the cells wrap is the same move ideas' .tag makes, and it is measured at
     390: M0084's seven prose scrollers (up to 850px) become two at 364px; M0007's three
     (965 / 421 / 917) become one at 633px; M0102's two 727s become two 352s. The document measures
     390 either way -- this is readability, not overflow. */
  .prose th, .prose td { white-space: normal; }

  /* Previously `@media (max-width: 34rem)`. One breakpoint per stylesheet: at 34rem (544px at the
     app's 16px root, and the only root-font-size-dependent layout query in /sera) the Redone rows
     stayed a three-column grid across the whole 544-1024px band -- a band that is already one
     column everywhere else and has no designed layout of its own. Desktop is unchanged: at 1024px
     and above the row is still three columns. */
  .redoneRow { grid-template-columns: 1fr; }
  .redoneValue { text-align: left; }
}
```

**Impact:**

- All the card selectors are new local class names; nothing that exists today changes.
  `.vMoreItem :global(.num)` must be `:global` — `.num` is a global utility from
  `app/globals.css:136`, and a bare `.num` inside a CSS module would be hashed and never match.
  `.vMark .ok` needs no `:global`: `.ok` / `.no` / `.na` are local to this module (line 24).
- `.prose th, .prose td { white-space: normal }` must sit **after** line 85 in source order to win
  (same specificity). Appending at the end of the file guarantees it.
- At >= 1024px not one rule in the block can match, and `.cards` carries `mobile-only` in any case.
  **Desktop is untouched** (invariant 2).
- The only behavioural change outside 390/414 is the `Redone realistically` block between 544px and
  1023.98px, which goes from a three-column row to a stacked one. That is inside the narrow band by
  definition, so invariant 2 holds. Check it on `/sera/methods/M0007` at 1280 — unchanged — and
  eyeball it once at 768 if convenient.

---

## Verification

Phase 4 uses **port 3124**. Concurrent phases share this worktree, so never use 3111.

### Build and tests

```bash
cd /home/miftah/.worktrees/seer/sera-responsive/web
npx tsc --noEmit && npm test
```

Both must be clean. **`app/sera/methods/view.test.ts` must pass untouched** — it imports `./view`
and nothing else. If a change of yours would make you edit it, you have crossed into `view.ts`,
which is frozen and shared with phase 3: back the change out and compute the value in `page.tsx`
instead. Grep confirms no test file in `web/` imports `app/sera/methods/[id]/page.tsx` or
`method.module.css`:

```bash
cd /home/miftah/.worktrees/seer/sera-responsive/web
grep -rln "methods/\[id\]\|method.module" --include='*.test.ts' --include='*.test.tsx' .
# -> no matches
```

### The baseline for "1280 pixel-identical"

Take it **before** editing anything, on the branch as it stands:

```bash
cd /home/miftah/.worktrees/seer/sera-responsive/web
node scripts/with-env.mjs npx next dev -p 3124 &
npm run shoot -- --base http://localhost:3124 --out .shots/p4-before --width 1280 \
  /sera/methods/M0102 /sera/methods/M0007 /sera/methods/M0084 /sera/methods/M0040
```

**Why a before-shot rather than `git stash`.** Five phase sessions share this one worktree and one
git index. A bare `git stash` would pocket the *other* sessions' uncommitted work along with yours.
Take the baseline before you edit, and never stash, `reset --hard`, or stage anything you do not
own. Each phase also writes its PNGs under its own `--out .shots/pN` for the same reason.

### The acceptance run

Seven routes plus the three extra method ids, all three widths, both themes (`--theme` defaults to
`both`):

```bash
cd /home/miftah/.worktrees/seer/sera-responsive/web
npm run shoot -- --base http://localhost:3124 --out .shots/p4 --width 390 --width 414 --width 1280 \
  /sera /sera/journal /sera/methods /sera/methods/M0102 /sera/ideas /sera/how /sera/gotrade \
  /sera/methods/M0007 /sera/methods/M0084 /sera/methods/M0040
```

Use the `run-the-web-app` skill; it signs in without a human and self-renews the cookie. Never ask
the owner to sign in.

### Desktop did not drift

```bash
cd /home/miftah/.worktrees/seer/sera-responsive/web
for id in M0102 M0007 M0084 M0040; do
  for th in light dark; do
    cmp ".shots/p4-before/sera-methods-$id__${th}__1280.png" ".shots/p4/sera-methods-$id__${th}__1280.png" \
      && echo "$id $th 1280 identical"
  done
done
```

(`shoot.mjs` names files `${slug(path)}__${theme}__${width}.png`; confirm the slug it actually
writes and adjust the glob rather than assuming.) Any difference at 1280 is a phase-4 failure, not
a tolerance.

### Read the PNGs — R1 is invisible to the shoot

A green run only means nothing threw. Open, at minimum, at 390 **and** 414, in both themes:

| shot | what must be true |
|---|---|
| `M0102` @390 | the variants section is five cards, not a scroller. One card has the butter wash **and** the Best chip. Each card's lead number is legible without zooming. The four grid labels read `MAX DRAWDOWN` / `PROFIT FACTOR` / `TRADES` / `LUCK CHECK` — spelled out, no dotted glossary underline |
| `M0084` @390 | the funded shape: every card leads on *What your money earned*, and *Growth a year* and *Return* both show `—` on the `.vMore` line. Its prose markdown tables wrap instead of running 850px wide |
| `M0007` @390 | the `Redone realistically` block is stacked, each row naming its own measure. Its two lines are still two different measures, not two versions of one number |
| `M0040` @390 | unchanged: the `Not tested yet` sheet, the `Waiting on:` line, no charts, no variants section. This page is the control |
| any of them @1280 | identical to `.shots/p4-before` — the table, the 34rem-band Redone row, the nowrap prose cells |

### Accessibility spot-check (invariant 10)

With devtools at 390 and at 1280, on `/sera/methods/M0084`:

- exactly one of `div.tableWrap` / `ul.cards` has a computed `display` other than `none`
- the surviving table (at 1280) still has `scope="col"` on every header and `scope="row"` on the
  variant cell — Step 3 copies them verbatim
- at 390 a screen reader reads each mark once, not twice (`decorative` hides the icon; the text
  carries it)
- the `<details>`/`<summary>` disclosures in *Technical detail* still open and close at both
  widths, and `.config` still wraps rather than scrolling sideways

### Exit criteria

1. `npx tsc --noEmit && npm test` clean.
2. **The R2 numbers this phase must HOLD, not move.** Phases 1 and 2 already took every method page
   to exactly the viewport width (848 → 456 by phase 2, 456 → 390 by phase 1), so in the tree this
   phase runs in — wave 1 landed — `/sera/methods/M0102`, `/sera/methods/M0007`,
   `/sera/methods/M0084` and `/sera/methods/M0040` already measure exactly 390 at 390 and 414 at
   414. The exit criterion is that they **still** do after this phase. Phase 4 moves no R2 number of
   its own; every change here is R1.
3. **Routes that may still report PROBLEMS, and must not be fixed from here:** `/sera/ideas`, at
   476 at both narrow widths, until phase 5 lands — see the plan index's *Residual-overflow ledger*.
   A phase-4 run that made `/sera/ideas` green would mean scope was crossed. If `/sera/methods` is
   anything but exact, that is phase 3 mid-flight in the shared worktree, not phase 4's to chase.
4. The four 1280 method-page PNGs are pixel-identical to the pre-change baseline (`cmp` is the
   cheap check; if the bytes differ, diff the images before calling it a drift).
5. The PNGs at 390 and 414 show cards, not a horizontal scroller, on every method page that has
   variants — with the best variant visibly named.
6. Nothing outside `app/sera/methods/[id]/page.tsx` and `app/sera/methods/[id]/method.module.css`
   is modified. In a shared worktree `git diff --name-only` also shows the peers' work, so check
   by pathspec: `git diff --name-only -- 'web/app/sera/methods/[id]'` lists exactly those two
   files, and commit by pathspec too — never `git add -A`.

---

## Handoffs

- **Phase 3 — card vocabulary, settled by the reconciler; nothing left to negotiate.** The seven
  pieces both pages have take phase 3's names (`.cards`, `.card`, `.cardHead`, `.stats`, `.stat`,
  `.statLabel`, `.statValue`); the variant-only pieces keep their `v` prefix. The card's geometry is
  phase 3's too — `border-radius: 28px`, `background: var(--stone)`, `padding: 16px 18px 14px`,
  `gap: 10px` — because 28px on stone is Sera's narrow card everywhere it appears
  (`ideas.module.css`, `journal.module.css`, `overview.module.css`, `how.module.css`), while the
  22px this plan first took from `.tech` belongs to a disclosure panel, not a list of records. The
  small-caps label is `ideas.module.css .label` verbatim on both pages. `data-best='true'` carries
  the highlight; the global `.desk-only` / `.mobile-only` pair does the switching. CSS modules are
  scoped, so the shared names cannot collide.
- **Phase 5** — `/sera/how`'s 960px diagram inside a 330px scroller needs a *visible affordance
  that it scrolls*, and that affordance is phase 5's to design. The same want exists here: after
  Step 5 this page still has one to two contained prose scrollers per method (352–633px measured).
  Phase 4 deliberately does not invent a second affordance idiom (invariant 6). Once phase 5's
  exists, a short follow-up should apply it to `.prose [data-md-table]` in `method.module.css`.
- **Phase 2** — `.prose [data-md-table]` and `.config` were checked for the containing-block escape
  and are clean (0 absolutely-positioned descendants, measured on M0007, M0084 and M0102 at 390 and
  414, with every `<details>` forced open). Neither needs a `position: relative` guard. Phase 2
  need not widen its scope on this page's account.
- **Not done, deliberately** — `.table { min-width: 1240px }` and `white-space: nowrap` on the desk
  table are left exactly as they are. They are correct at ≥1024px and the narrow band no longer
  renders them.
- **Not done, deliberately** — the `Redone realistically` panel is not re-designed, only
  re-breakpointed. Its stacked narrow form already exists and reads correctly.

---

## Rollback

One commit on `feature/sera-responsive`; `git revert <sha>` restores it alone. Everything added is
either a new local class name that only paints below 1024px, a class on a wrapper that is a no-op
above 1024px, or an optional component prop that defaults to today's behaviour. The one change
that is not purely additive is Step 5's breakpoint move (`34rem` → `1023.98px`); reverting restores
the `34rem` query verbatim. No migration runs, no engine constant is touched, and `lab/lab.sqlite`
and `web/data/lab.json` are read-only to this phase.
