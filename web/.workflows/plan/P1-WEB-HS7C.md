> Adopted from `/home/miftah/seer/.workflows/orchestration/sera-responsive/PLAN.md` phase 3. Source: `.workflows/plan/sera-responsive/phase-3.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 3: /sera/methods: cards on a phone, table on a desk

**Plan set:** `SERA_RESPONSIVE_PLAN.md`
**Analysis:** `docs/analyzer/20261012-165855-R4C9_code_analyzer.md`
**Satisfies:** R1 (a *designed* narrow layout for the methods list) — and **holds** R2 on
`/sera/methods` at 390/414/1280, a number phases 1 and 2 moved and this phase must not spend
**Depends on:** Phase 1 (the narrow nav and shell), Phase 2 (`Term`'s containing-block fix)
**Difficulty:** HARD
**Package:** `web/app/sera/methods`
**Port:** 3123

---

## Goal

Below 1024px `/sera/methods` stops being an eleven-column, 1200px table stuffed into a 330px
scroller and becomes one card per method — the same 28px-radius, `var(--stone)` panel vocabulary
every other Sera page already uses at that width. At 1024px and above the table renders exactly as
it does today, down to the computed styles. Exactly one of the two presentations is in the
accessibility tree at any width, and the page measures the viewport width at 390, 414 and 1280 in
both themes.

## The decision this phase implements (D4 — already made, not re-opened)

> **Below 1024px the methods list is a card per method; at ≥1024px it stays the table it is today,
> byte for byte.**

Handover §6 raised card-per-row as a question and asked for the cost to be flagged. It was decided
on the owner's own sentence (handover §1): *"fully revamp xsmax UI to improve responsive UI/UX user
experience."* The 390px screenshot of the current page shows the reader gets `STATUS`, a truncated
`METHOD`, and no affordance that nine more columns exist to the right. The surrounding convention
agrees: `ideas.module.css` (`.card`, `.wish`, `.group`), `journal.module.css` (`.card`) and
`overview.module.css` (`.card`) are all card-at-narrow.

### The cost, stated plainly

Two presentations means more markup per request, at **every** width — the hidden one is still in
the HTML.

- Today's payload: 130 `<tr>`, ~14 elements each ≈ **1,800 elements**.
- After: those 1,800, plus ~74 tested cards × ~16 elements and ~56 untested cards × ~8 ≈
  **~1,630 more**. The methods list's element count roughly **doubles**.
- Measured on the data actually committed: `web/data/lab.json` holds **130 methods**, **56** of
  which have no trial (`best === null`).

**The mitigation is the one the codebase already uses**, `components/Nav.tsx:26-50`: one data
source (`TABS`), two renders (`aside.rail.desk-only` and `nav.bar.mobile-only`), and the *shared
inner piece* extracted into one component (`Tabs`, `Nav.tsx:54`) so the logic is not written twice.
Here that means:

- `shown` is computed **once** (`page.tsx:49`, one `filterRows` call) and both presentations map
  that same array.
- **All derivation stays in `view.ts`** — `pct1`, `pfText`, `fixed`, `marks`, `markLabel`,
  `SOURCE_ICON`, `sourceHref` — which both `Row` and `Card` call. No row-building logic is
  duplicated; only markup is, which is unavoidable because a `<tr>` and an `<li>` cannot be the
  same element.
- `Dots` stays **one component** called by both, so the six-hurdle rendering, its `role="img"`
  label and its tooltip exist in exactly one place.

The element count is the real, accepted cost of the decision. Record it during verification (the
command is in **Verification**) so the next person has a number rather than this estimate.

## Interface Contract

**Deletes:** nothing. No symbol, class, prop or config key is removed.

**Renames:** none.

**Creates (all in files this phase owns):**

- `page.tsx` — `function Card({ r }: { r: MethodRow })` (local, not exported)
- `page.tsx` — `function CardStat({ label, children })` (local, not exported; named `CardStat`
  rather than `Stat` deliberately, so it is never confused with `components/sera/Stat.tsx`, which
  Phase 5 owns)
- `methods.module.css` — one new `@media (max-width: 1023.98px)` block defining the local classes
  `.cards`, `.card`, `.cardHead`, `.cardTitles`, `.cardLink`, `.cardScore`, `.cardGo`, `.stats`,
  `.stat`, `.statLabel`, `.statValue`, plus narrow-only overrides of the **existing** `.toolbar`,
  `.counts` and `.status[data-tone='bad']`

**Signature changes:** none. `Row`, `Dots` and `Methods` keep their current signatures; `Row` and
`Dots` keep their current bodies verbatim.

**DOM shape the narrow presentation introduces** (the reconciler should check Phase 4 did not pick
different names for the same idea):

```
ul.cards.mobile-only
└── li.card                       position: relative; the whole card is one link
    ├── div.cardHead              span.id            +  span.chip.status[data-tone]
    ├── div.cardTitles            a.cardLink > span.name   +  span.family
    ├── div.cardScore             span.dots (role="img")  |  span.untested      + svg.cardGo
    └── dl.stats                  div.stat > dt.statLabel + dd.statValue   (×4, 2×2 grid)
```

**Requires (from earlier phases):**

- **Phase 1** — the narrow shell. Phase 1 **rewrites** `app/sera/sera.module.css`'s narrow block,
  so quote the post-change state, not `09515d1`'s: the narrow `.main` becomes
  `padding: var(--safe-top) 16px var(--nav-clear)`, and `.shell { flex-direction: column }` is
  deleted. What this phase depends on is the part phase 1 pins as unchanged — **side padding stays
  16px**, so the content width at 390 is still 358px and at 414 still 382px, which is what every
  measurement below assumes. Phase 1 also reserves the floating bar's space **once**, on `.main`,
  with `var(--nav-clear)`: this phase must not add a second `padding-bottom`, a `.nav-clear`
  spacer, or its own show/hide media query — `.desk-only` / `.mobile-only` is the element-level
  switch for the whole set. And the nav no longer adds its 456px row.
- **Phase 2** — `components/sera/Term.module.css` gives `.term { position: relative }` so the
  five `<th>` `Term.sr` spans stop escaping `.tableWrap`.
  **Reconciled:** this phase puts the whole table behind `.desk-only` (`display: none !important`
  below 1024), so those five `.sr` spans generate no boxes at narrow width and `/sera/methods`
  reaches 456 **at 390 and 414** with or without Phase 2. That is true and it is **not** permission
  to drop Phase 2, which stays a hard dependency. Phase 2 is wave 1 and this phase is wave 2, so in
  the tree this phase actually runs in the fix is already there and `/sera/methods` already
  measures exactly 390; Phase 2 is also the only thing covering the 1024px-and-up band where the
  table still renders inside a `position: static` scroller, the whole of `/sera/methods/M0102`
  before Phase 4 lands, and every future scroller that holds a glossary term. Phase 2's own plan
  carries the full argument under *"This phase is not made redundant by phases 3 and 4"*.

**Leaves alone (owned by others), hard boundaries:**

- `app/sera/methods/view.ts` and `app/sera/methods/view.test.ts` — **frozen**, shared with Phase 4
  (`[id]/page.tsx:20` imports `from '../view'`). This phase imports from them and changes nothing.
  Verified: `view.test.ts` imports only `./view`, and **no test file in `web/` imports `page.tsx`,
  `methods.module.css`, or asserts on `.desk-only`/`.mobile-only`** (grep over all 49 test files —
  see **Tests**).
- `app/sera/methods/[id]/**` — Phase 4
- `components/sera/Term.tsx`, `Term.module.css` — Phase 2
- `components/sera/Section.*`, `components/sera/PageHeader.*`, `app/sera/sera.module.css` — Phase 1
- `app/globals.css` — read-only precedent for everyone
- `app/sera/ideas/*`, `app/sera/overview.module.css`, `components/sera/Stat.module.css`,
  `app/sera/how/how.module.css` — Phase 5

## Files

| File | Action | What changes |
|---|---|---|
| `web/app/sera/methods/page.tsx` | modify | `.tableWrap` gains `desk-only`; a sibling `ul.cards.mobile-only` is added over the same `shown` array; two new local components `Card` and `CardStat`. `Row`, `Dots`, `Methods`' data flow and every import are untouched. |
| `web/app/sera/methods/methods.module.css` | modify | One new `@media (max-width: 1023.98px)` block appended after the file's last line. Nothing above it is edited — the column-budget comment block (`:24-38`) and the `@media (min-width: 1024px)` block (`:83-85`) are left exactly as they are. |

## The card's information hierarchy — decided, and why

The table has eleven columns: Status, Method (id + name + family), Source, Growth-a-year vs SPY,
Max DD, PF, Trades, DSR, Hurdles (6 dots + n/6), Verdict, chevron. At 390 the card has
**278–310px of content width** (390 − 2×16 `.main` − 2×22 `Section` − 2×18 card padding). Eleven
columns do not fit legibly in that, so four of them are dropped. The row's whole purpose is to get
the reader into the method, so the test for every column is: *does this change whether I tap it?*

### Kept, in this order

| # | What | Why it earns its pixels |
|---|---|---|
| 1 | **Method id** (`M0116`), small and muted, top-left | The only way to match a card to a commit message (`lab: M0116 pre-registered — …`). Stays 12px `--ink-3` because invariant 8 says the owner's reading text avoids ids — this is a handle, not prose. |
| 2 | **Status chip**, top-right | One word for how the method ended. The highest signal-per-pixel item on the row, and it keeps its `data-tip={st.meaning}`. |
| 3 | **Name**, the link | The thing being identified, and the tap target. Reuses `.name` (16px/500) unchanged — the table wraps it in a 224–340px auto column, so full wrapping at 278px is the same behaviour, not a new one. Names run to 160 characters; it is **not** clamped, because a method's name is its identity and a half-name is worse than four lines. |
| 4 | **Family** (`book-drawdown-brake`), muted under the name | Reuses `.family`. One line, and it is how the owner groups a batch. |
| 5 | **Six hurdle dots + `n/6`**, with the chevron pushed right | The Section's own caption says *"The six dots on each row are the six hurdles a method must clear"* — the caption is copy this phase does not change, so the dots cannot leave. Reuses the existing `Dots` component whole, which keeps `role="img"` and the `aria-label` naming every missed hurdle. |
| 6 | **Four numbers** in a 2×2 grid: Growth a year (vs SPY), Max drawdown, Profit factor, Luck check | These are four of the six hurdles, and a dot alone says *missed* without saying *by how much*. "Profit factor missed" is uninformative; "Profit factor 1.02" tells you it was a whisker. ~52px of card height for the four. |

### Dropped, and where each goes instead

| Dropped | Why | Where it still lives |
|---|---|---|
| **Trades** | A sample-size check, not a result. It is the one number least likely to change whether the reader opens the card, and its hurdle is still a dot. | The method's own page, in full with its threshold. |
| **Source** (icon + label + external-link glyph) | Provenance, not performance. The desktop column is already an ellipsised label; at 278px it eats a whole line to say "Variation of an earlier method". Worse, it is an `<a>` **inside** a card that is itself one big link — on a phone a competing tap target inside a 278px card is a mis-tap waiting to happen, and it is why the card keeps exactly one. | `/sera/methods/[id]` (Phase 4's page), where the source has room and no competition. |
| **Verdict teaser** | 434 characters (the longest in `lab.json`) clamped to two lines at 278px is ~68 characters — in practice `"P3 gate failed: out of sample 2022-01-03 -> 2026-10…"`, a fragment of dates, ids and file paths cut mid-clause. **That is precisely the text style invariant 8 forbids** for what the owner reads. The status chip already carries the plain one-word answer plus its `meaning` tooltip. | `/sera/methods/[id]`, whole, in sentences. |
| **The `<th>` glossary `Term`s** | The table abbreviates ("Max DD", "PF", "DSR") because of the measured column budget, and buys the meaning back with a `Term` tooltip. The card has no such budget, so it **spells the labels out** instead: `Growth a year`, `Max drawdown`, `Profit factor`, `Luck check`. Those are the house's own plain words, taken verbatim from `lib/sera/glossary.ts` (`GLOSSARY.maxDrawdown.term`, `GLOSSARY.profitFactor.term`) and `lib/sera/derive.ts` (`CONDITION_LABEL.dsr === 'Luck check'`). | Nothing is lost: a `Term` inside the card would be a `tabIndex={0}` span under the card-wide link overlay — unreachable *and* a focus trap. |

### `b === null` — "Not tested yet" (56 of the 130 methods)

The table renders `<td class="untested r">Not tested yet</td><td colSpan={5} />`. The card renders
the same five words with the existing `.untested` class, left-aligned, **in the score line's slot**
— so an untested card still has a chevron in the same place and the list keeps a regular rhythm.
The stat grid is omitted entirely rather than filled with four em-dashes. No new copy is invented:
the status chip (`Idea`, `Blocked on data`, `Registered`) carries the nuance via its own tooltip,
exactly as on desktop.

## Accessibility (plan invariant 10) — confirmed against the real rules

`app/globals.css:245-250`, read in this worktree, verbatim:

```css
@media (max-width: 1023.98px) {
  .desk-only { display: none !important; }
}
@media (min-width: 1024px) {
  .mobile-only { display: none !important; }
}
```

`display: none` removes an element **and its whole subtree** from the layout tree *and* from the
accessibility tree in every engine — it is the canonical "hide from everyone" (unlike
`visibility: hidden` offsets, `opacity: 0`, or off-screen positioning, which leave nodes exposed).
So **exactly one of the two presentations is ever exposed to assistive tech**, at every viewport
width, and neither needs `aria-hidden` — adding it would be redundant and, on the visible one,
actively wrong. The two media queries are complementary and non-overlapping (1023.98 / 1024), so
there is no width at which both are hidden or both are shown.

What survives, item by item:

- **`scope="col"`** on all ten labelled `<th>` — untouched; the table's markup is not edited beyond
  the wrapper's className.
- **The `Dots` `role="img"` + `aria-label`** (`"Cleared 3 of 6 hurdles. Beats SPY: missed · …"`) —
  the same component renders in both presentations, so the label is identical in both.
- **`aria-label` on every control** — the four filter links in `.seg` keep both `aria-label` and
  `data-tip` and are not touched.
- **The whole-row link affordance** — on desktop `.nameLink::after { inset: 0 }` over
  `.row { position: relative }`; on the card `.cardLink::after { inset: 0 }` over
  `.card { position: relative }`. Same idiom, same accessible name (the method's name), no
  `aria-label` added — the link's text content is already the name.
- **`:focus-within` outline** — `.row:focus-within` has one; `.card:focus-within` gets the matching
  one (`2px solid var(--coral)`, offset `2px` rather than `-2px`, because the card has a 28px
  radius and an inset outline would cut its corners).

**Pre-existing behaviour mirrored, not introduced:** the full-bleed `::after` overlay sits above
the `Dots` span and the status chip, so their `data-tip` hover tooltips do not fire inside a row.
That is already true on desktop today. The card reproduces it rather than diverging. The
`aria-label` path is unaffected, so nothing is lost for assistive tech. Listed under **Handoffs**.

## Controls stay icon-only with `aria-label` + `data-tip` (invariant 4)

The toolbar's filter `.seg` is four `icon-btn` links, each with `data-tip={tip}` **and**
`aria-label={tip}` (`page.tsx:67-68`). **No control is added, removed or re-labelled by this
phase.** Fit at 390, computed from `globals.css:176-184`: `.seg` is `padding: 3px` around four
buttons at `var(--seg-btn, 40px)` — `4 × 40 + 2 × 3 = 166px` inside 310px of content. It fits with
144px to spare and the 19px Lucide glyphs are the same size they are everywhere else in the app.

What *does* change at narrow width is the toolbar's **arrangement**: today `.toolbar` is
`justify-content: space-between` with `.counts` (five `white-space: nowrap` chips) as the second
flex item, so at 390 the five chips stack into a ~110px column beside the pill. It does not
overflow — `166 + 16 + 110 = 292 ≤ 310` — but it reads as a ragged sidebar. Below 1024 the toolbar
becomes a column with the chips wrapping across the full width, which is exactly what
`journal.module.css:67` does to `.bar` at the same breakpoint.

## Design vocabulary (invariant 5) — borrowed, not invented

| Card piece | Token / rule | Where it already exists |
|---|---|---|
| `border-radius: 28px` | — | `ideas.module.css:7` `.card`, `journal.module.css:16` `.card` |
| `background: var(--stone)` | — | `ideas.module.css:22` `.wish`, `:39` `.group` — the house background for a panel **inside** a `--sheet` Section, which is this card's exact position |
| status chip | `chip` + the existing `.status[data-tone=…]` rules | `methods.module.css:63-67`, reused unchanged except for one tone (below) |
| hurdle dots | `.dots`, `.dotOn`, `.dotOff`, `.dotNa`, `.dotsN` | `methods.module.css:69-74`, reused verbatim |
| "Not tested yet" | `.untested` | `methods.module.css:60`, reused verbatim |
| name / family / id | `.name`, `.family`, `.id` | `methods.module.css:49-51`, reused verbatim |
| `vs 9.1%` | `.vs` | `methods.module.css:59`, reused verbatim |
| small uppercase label | `12px / 0.12em / uppercase / var(--ink-3)` | `ideas.module.css:16` `.label` — copied exactly |
| chip sizing on a tinted panel | `height: 30px; font-size: 14px` | `ideas.module.css:13` `.chips :global(.chip)` |
| column stack at narrow | `flex-direction: column; align-items: flex-start` | `journal.module.css:67` `.bar` |

**The one tone that needs an override, and why it is not a new tone.** `.status` and
`.status[data-tone='bad']` are both `background: var(--stone)` — which is the card's own
background, so a `Rejected` chip would vanish. The fix is a background swap for that one tone,
`var(--chip-solid)`:

- `--chip-solid` is the token for *a chip that must sit proud of a tinted surface*
  (`globals.css:169` `.icon-btn.solid`). In light it is `#ffffff`; in dark it is
  `rgba(255,255,255,0.14)` — **lighter** than `--stone` (`#2c2823`), which `var(--sheet)`
  (`#211f1c`) would not be. Using `--sheet` would make the chip darker than its own card in dark
  mode.
- `ideas.module.css` makes the identical move twice (`.tally :global(.chip)`,
  `.chips :global(.chip)` → `background: var(--sheet)`), so the pattern is house, not invented.
- The other three tones are left alone on purpose: `wait` is `transparent` + a dashed
  `--outline` border and reads correctly on stone (and *should* stay quiet — it means "not yet");
  `neutral` is `--butter`; `good` is `--ink` on `--sheet`. Only `bad` collides.

## Desktop must not drift (invariant 2)

- **Every new CSS rule in this phase is inside one `@media (max-width: 1023.98px)` block**, appended
  after the file's current last line. Grep the file after the change: there is nothing new outside
  that block. The `@media (min-width: 1024px)` block at `:83-85` and the measured column-budget
  comment at `:24-38` are **not edited** — `CLAUDE.md` says carefully measured things are not to be
  "fixed".
- The classes `.cards`/`.card`/… could have lived outside a media query (they only ever land on a
  `.mobile-only` subtree), but putting them inside makes the desktop-safety audit a single grep.
- `.desk-only` has **no declarations at all** at ≥1024px, so adding it to `.tableWrap`'s className
  changes nothing about the table's computed styles at 1280.
- The new `<ul class="… mobile-only">` is `display: none !important` at ≥1024px. A `display: none`
  flex item generates no box and therefore **no flex gap**, so the Section's `gap: 20px`
  (`methods.module.css:3`) does not grow by one gap on desktop. This is the one way a
  "purely additive hidden sibling" could have moved desktop pixels, and it does not.
- **`.tableWrap` does NOT get `position: relative`.** Phase 2's note asked me to consider it. It is
  not needed and would be a desktop-affecting change for no measured benefit: at narrow width the
  wrapper is `display: none` and cannot contribute to document width at all, and at 1280 the page
  measures 0px of overflow today. The general containing-block fix stays where Phase 2 put it, in
  `Term.module.css`, where it also covers `overview.module.css`, `journal.module.css` and
  `[id]/method.module.css`'s static scrollers. Deliberate non-change; stated so the reconciler can
  see it was considered.

---

## Implementation Steps

### Step 1: Split the list into two presentations

**File:** `web/app/sera/methods/page.tsx:82-107`
**Change:** replace the `shown.length === 0 ? … : (…)` expression. The `<table>` and its `<thead>`/
`<tbody>` are **character-for-character what they are today**; only the wrapping `<div>`'s
className changes, and a sibling `<ul>` is added.

**Code — replace lines 82-107 with:**

```tsx
        {shown.length === 0 ? (
          <p className={s.empty}>{EMPTY[show]}</p>
        ) : (
          <>
            {/* Two presentations of one `shown` array, switched by the global 1024px helpers
               (globals.css:245-250). Those rules are `display: none !important`, which takes the
               hidden subtree out of the accessibility tree as well as out of layout, so exactly
               one of the two is ever exposed and neither needs aria-hidden (plan invariant 10).
               The idiom is components/Nav.tsx:26-50, which renders the same TABS as a desktop
               rail and a phone bar; the shared inner piece here is <Dots>, called by both.
               An eleven-column, 1200px table does not become readable by being put inside a 330px
               scroller -- at 390 the reader sees STATUS, a cut-off METHOD, and no hint that nine
               more columns exist -- so below 1024px the table is not shown at all. */}
            <div className={`${s.tableWrap} desk-only`}>
              <table className={s.table}>
                <thead>
                  <tr>
                    <th className={s.cStatus} scope="col">Status</th>
                    <th className={s.cMethod} scope="col">Method</th>
                    <th className={s.cSource} scope="col">Source</th>
                    <th className={`${s.cCagr} ${s.r}`} scope="col"><T k="cagr">Growth a year</T> vs SPY</th>
                    <th className={`${s.cMaxDd} ${s.r}`} scope="col"><T k="maxDrawdown">Max DD</T></th>
                    <th className={`${s.cPf} ${s.r}`} scope="col"><T k="profitFactor">PF</T></th>
                    <th className={`${s.cTrades} ${s.r}`} scope="col"><T k="trades">Trades</T></th>
                    <th className={`${s.cDsr} ${s.r}`} scope="col"><T k="dsr">DSR</T></th>
                    <th className={s.cDots} scope="col">Hurdles</th>
                    <th className={s.cVerdict} scope="col">Verdict</th>
                    <th className={s.cGo} aria-hidden="true" />
                  </tr>
                </thead>
                <tbody>
                  {shown.map(r => <Row key={r.method.id} r={r} />)}
                </tbody>
              </table>
            </div>
            <ul className={`${s.cards} mobile-only`}>
              {shown.map(r => <Card key={r.method.id} r={r} />)}
            </ul>
          </>
        )}
```

**Impact:** at ≥1024px the rendered table is unchanged and the `<ul>` paints nothing and takes no
flex gap. Below 1024px the table is gone — which also removes the five `<th>` `Term.sr` spans that
the analysis measured escaping `.tableWrap` (959px at 390). `/sera/methods` drops from 959 to 456
(nav only) on this change alone. The HTML payload for the list roughly doubles; see the cost
section and record the measured number in verification.

### Step 2: Add the `Card` and `CardStat` components

**File:** `web/app/sera/methods/page.tsx` — insert immediately **after** `Row` ends (today line 170)
and **before** `function Dots` (today line 172), so `Row` and `Card` read as the pair they are and
the shared `Dots` sits last.
**Change:** two new local components. Nothing else in the file moves. **No import changes are
needed** — `ChevronRight`, `Link`, `ReactNode`, `STATUS_LABEL`, `excessCagr`, `pct1`, `pfText`,
`fixed` and `MethodRow` are all already imported at `page.tsx:1-17`.

**Code:**

```tsx
/**
 * One method as a card: the narrow-width presentation of `Row`.
 *
 * A 390px screen cannot carry the table's eleven columns legibly, so the card keeps only what
 * decides whether the reader opens the method -- what it is, how it ended, how close it came, and
 * whether it beat SPY without an unbearable fall -- and leaves the rest to the method's own page,
 * which the whole card links to.
 *
 * Dropped on purpose, each reachable one tap away:
 *   - Trades: a sample-size check, not a result; its hurdle is still one of the six dots.
 *   - Source: provenance, not performance, and a second tap target inside a card that is itself
 *     one big link is a mis-tap waiting to happen on a phone.
 *   - The verdict: the longest in the lab runs to 434 characters, and two lines of it at this
 *     width is a fragment of dates and file paths cut mid-clause -- exactly the text the owner
 *     should never be handed. The status chip already gives the plain one-word answer.
 *
 * The labels are spelled out rather than abbreviated: the table says "Max DD" / "PF" / "DSR"
 * because of its measured column budget and buys the meaning back with a <Term> tooltip, which a
 * card cannot use (a Term is a tabIndex={0} span, and it would sit under the card-wide link
 * overlay). The words here are the glossary's own: GLOSSARY.maxDrawdown.term,
 * GLOSSARY.profitFactor.term, and derive.CONDITION_LABEL.dsr ("Luck check").
 */
function Card({ r }: { r: MethodRow }) {
  const m = r.method;
  const b = r.best;
  const st = STATUS_LABEL[m.status];
  const excess = b ? excessCagr(b) : null;
  return (
    <li className={s.card}>
      <div className={s.cardHead}>
        <span className={s.id}>{m.id}</span>
        <span className={`chip ${s.status}`} data-tone={st.tone} data-tip={st.meaning}>{st.label}</span>
      </div>
      <div className={s.cardTitles}>
        {/* The ::after on .cardLink covers the whole card, as .nameLink::after covers the whole
            row on desktop. The link's accessible name stays the method's name. */}
        <Link href={`/sera/methods/${m.id}`} className={s.cardLink}>
          <span className={s.name}>{m.name}</span>
        </Link>
        <span className={s.family}>{m.family}</span>
      </div>
      <div className={s.cardScore}>
        {b
          ? <Dots best={b} passed={r.passed ?? 0} />
          : <span className={s.untested}>Not tested yet</span>}
        <ChevronRight size={18} className={s.cardGo} aria-hidden="true" />
      </div>
      {b ? (
        <dl className={s.stats}>
          <CardStat label="Growth a year">
            <span className={`num ${excess === null ? '' : excess >= 0 ? 'pos' : 'neg'}`}>{pct1(b.cagr)}</span>
            <span className={s.vs}> vs {pct1(b.spyTrCagr)}</span>
          </CardStat>
          <CardStat label="Max drawdown"><span className="num">{pct1(b.maxDrawdown)}</span></CardStat>
          <CardStat label="Profit factor"><span className="num">{pfText(b)}</span></CardStat>
          <CardStat label="Luck check"><span className="num">{fixed(b.dsrNow, 2)}</span></CardStat>
        </dl>
      ) : null}
    </li>
  );
}

/** One label/value pair in a card's 2x2 stat grid. A <div> around dt/dd is valid inside a <dl>. */
function CardStat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className={s.stat}>
      <dt className={s.statLabel}>{label}</dt>
      <dd className={s.statValue}>{children}</dd>
    </div>
  );
}
```

**Impact:** adds the narrow presentation. `Row` and `Dots` are not edited. The colour logic for
growth-vs-SPY (`excess >= 0 ? 'pos' : 'neg'`) is copied from `Row` (`page.tsx:151`) so both
presentations colour the same number the same way; the derivation itself is still the one
`excessCagr` call from `lib/sera/derive`.

### Step 3: Append the narrow-width stylesheet block

**File:** `web/app/sera/methods/methods.module.css` — append after the current last line (`:85`).
**Change:** one new media block. **Nothing above line 85 is edited.**

**Code — append verbatim:**

```css

/* ---- Below 1024px: a card per method ---------------------------------------------------------
   The table above is 1200px of eleven columns and does not become readable by being put in a
   330px scroller: measured at 390, the reader gets STATUS, a truncated METHOD, and no affordance
   that nine more columns exist. So below this width the table is hidden outright (.desk-only in
   page.tsx) and the same rows are rendered again as cards -- the vocabulary every other Sera page
   already uses here: ideas.module.css .card/.wish/.group and journal.module.css .card are all
   28px-radius panels on var(--stone) inside their sheet.

   Everything new in this file is inside this one query, so desktop cannot drift: nothing below
   this comment applies at >= 1024px. The column budget above (:24-38) and the >= 1024px block
   (:83-85) are measured records and are left exactly as they are. */
@media (max-width: 1023.98px) {
  /* The filter pill (166px) and the five count chips stop sharing one row and fighting for it.
     journal.module.css does the same to .bar at the same breakpoint. */
  .toolbar { flex-direction: column; align-items: flex-start; gap: 12px; }
  .counts :global(.chip) { height: 30px; font-size: 14px; }

  .cards { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }

  .card {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 16px 18px 14px;
    border-radius: 28px;
    background: var(--stone);
  }
  /* Offset outward, not inward: an inset outline would cut the 28px corners. */
  .card:focus-within { outline: 2px solid var(--coral); outline-offset: 2px; }

  .cardHead { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .cardTitles { min-width: 0; }

  /* The whole card is the link, exactly as .nameLink::after covers the whole row on desktop.
     The card deliberately carries no second tap target, so nothing competes with it. */
  .cardLink { display: block; color: var(--ink); outline: none; }
  .cardLink::after { content: ''; position: absolute; inset: 0; border-radius: 28px; }

  .cardScore { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .cardGo { flex: none; color: var(--ink-3); }

  /* One tone, not a new palette. .status and .status[data-tone='bad'] are both var(--stone), which
     is this card's own background, so a Rejected chip would vanish. --chip-solid is the token for
     a chip that must sit proud of a tinted surface (globals.css:169) and, unlike var(--sheet), it
     stays LIGHTER than --stone in the dark theme. ideas.module.css makes the same move with
     `.chips :global(.chip)`. The other three tones are correct on stone and are left alone -- in
     particular 'wait' keeps its transparent, dashed-outline look, which is the point of it. */
  .card .status[data-tone='bad'] { background: var(--chip-solid); }

  /* Four numbers, 2x2. At 390 each column is ~131px: "GROWTH A YEAR" is the widest label at
     ~103px and "12.3% vs 9.1%" the widest value at ~88px, so neither needs to truncate. */
  .stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 14px; margin: 2px 0 0; }
  .stat { min-width: 0; }
  /* ideas.module.css .label, copied exactly. */
  .statLabel {
    display: block; margin: 0; font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--ink-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  /* margin: 0 first -- a <dd> carries a 40px inline-start margin by default. */
  .statValue { margin: 2px 0 0; font-size: 16px; line-height: 1.2; }
}
```

**Impact:** defines the narrow presentation and restyles only `.toolbar`/`.counts` below 1024px.
No rule in the block can match at ≥1024px.

---

## Verification

Run from the worktree. **Port 3123** — concurrent phases share this worktree and `npm run dev:env`
hardcodes 3111.

**Build + tests (invariant 1):**

```bash
cd /home/miftah/.worktrees/seer/sera-responsive/web
npx tsc --noEmit && npm test
```

Both must be clean. `npm test` is `vitest run`; no test in the repo imports `page.tsx` or
`methods.module.css`, so the expected result is the same pass count as before the change.

**The acceptance test — all seven routes, three widths, both themes:**

```bash
cd /home/miftah/.worktrees/seer/sera-responsive/web
node scripts/with-env.mjs npx next dev -p 3123 &
# wait for "Ready in", then:
npm run shoot -- --base http://localhost:3123 --out .shots/p3 --width 390 --width 414 --width 1280 \
  /sera /sera/journal /sera/methods /sera/methods/M0102 /sera/ideas /sera/how /sera/gotrade
```

`--theme` defaults to `both`, so this is 7 routes × 3 widths × 2 themes = 42 shots.
`shoot.mjs:106` fails the run on `scrollWidth - viewport > 1` at any of them.

**Record the cost (do not estimate it):** with the dev server up, in the same Playwright session or
a throwaway probe under `web/scripts/_*.mjs` (they must live in `web/` so `playwright` resolves,
and `ensureState(base)` must be given the base URL):

```js
await page.goto('http://localhost:3123/sera/methods', { waitUntil: 'networkidle' });
console.log('elements', await page.evaluate(() => document.querySelectorAll('*').length));
console.log('html bytes', await page.evaluate(() => document.documentElement.outerHTML.length));
```

Run it on `main` and on the branch and write both numbers into the commit message. Delete the
probe afterwards; it is not committed.

**Manual check — this is part of the exit, not optional.** R1 is the half of the ask the shoot
cannot see: a green run only means nothing threw, and *"doesn't overflow" is not the same as "is
good on a phone"*. **Open the PNGs** in `web/.shots/p3/`:

- `sera-methods__light__390.png`, `sera-methods__dark__390.png`,
  `sera-methods__light__414.png`, `sera-methods__dark__414.png` — confirm, by eye:
  1. a card per method, not a table in a scroller;
  2. the status chip is **visible on the card in both themes**, `Rejected` included (this is the
     `--chip-solid` override — check it specifically in dark);
  3. the name wraps and is not clipped; the longest in the lab is 160 characters
     (`M0113`, `M0114`);
  4. the six dots and `n/6` read, and the chevron is on the same line, right-aligned;
  5. the four stat labels are not ellipsised at 390;
  6. an untested card (there are 56) shows "Not tested yet" and no stat grid;
  7. the filter pill sits on its own row above the count chips, and all four filter icons are
     distinguishable.
- `sera-methods__light__1280.png`, `sera-methods__dark__1280.png` — compare against a baseline
  taken **before you edit anything**, into this phase's own directory:
  `npm run shoot -- --base http://localhost:3123 --out .shots/p3-before --width 1280 /sera/methods`.
  They must be **pixel-identical** (`cmp` is the cheap check; if the bytes differ, diff the images
  before calling it a drift).

  **Do not `git stash` for the baseline.** Five phase sessions share this one worktree and one git
  index, so a bare stash pockets the *other* sessions' uncommitted work. Never stash,
  `reset --hard`, or `git add -A` here; commit by pathspec.

Use the `run-the-web-app` skill; it signs in without a human and self-renews. Never ask the owner
to sign in.

**Exit criteria:**

1. `npx tsc --noEmit` and `npm test` both clean.
2. `/sera/methods` measures **exactly 390 at 390 and 414 at 414**, in both themes. In the tree this
   phase runs in — wave 1 landed — phases 1 and 2 have already taken it there (959 → 456 by phase
   2, 456 → 390 by phase 1), so this is a number to **hold**, not to move: phase 3 moves no R2
   number of its own, and every change here is R1. Standalone on `09515d1` the same change would
   read 456 (nav only), which is phase 1's residue.
3. `/sera/methods` at 1280 is pixel-identical to `main` in both themes.
4. Below 1024px the reader sees a readable card per method; at or above 1024px the table is what it
   is today.
5. Exactly one presentation is in the accessibility tree at any width (by construction —
   `display: none !important`).
6. **The one route that may still report PROBLEMS, and must not be fixed from here:**
   `/sera/ideas`, at 476 at both narrow widths, until phase 5 lands — see the plan index's
   *Residual-overflow ledger*, which is the single ledger the whole set is scored against. Phase 4
   moves no R2 number, so `/sera/methods/M0102` should already be exact; if it is not, that is
   phase 4 mid-flight in the shared worktree, not phase 3's to chase. A phase-3 run that made
   `/sera/ideas` green would mean scope was crossed.
7. `git diff --name-only -- web/app/sera/methods` lists exactly `page.tsx` and
   `methods.module.css`. Check by pathspec: in a shared worktree a bare `git diff` also shows the
   peers' work, and commits must be made by pathspec too — never `git add -A`.

## Tests

Grepped `web/**/*.test.ts` and `web/**/*.test.tsx` — 49 files. **Nothing needs updating:**

- `app/sera/methods/view.test.ts` (373 lines) imports **only** from `./view` and exercises pure
  functions (`methodRows`, `marks`, `pct1`, `pfText`, `fixed`, `conditionSentence`, `techRows`, …).
  This phase changes neither `view.ts` nor any value those functions return. **If a change in this
  phase would break `view.test.ts`, that is proof the work crossed into `view.ts` — stop and move
  it, do not edit the test.** The file may be read; it must not be edited.
- No test imports `app/sera/methods/page.tsx` or `methods.module.css`.
- No test asserts on `.desk-only` / `.mobile-only`.
- `lib/sera/glossary.test.ts` checks the glossary's own shape (keys, one-sentence plain
  definitions); it does not scan page files, so spelling labels out on the card does not reach it.
- The engine-mirrored-constants test (invariant 7) is nowhere near this file — no constant is
  touched.

**No new test is added.** The acceptance test for this work is `npm run shoot` plus reading the
PNGs, which the plan index names as the one and only acceptance test for the set
(*"Do not invent another"*).

## Handoffs

Found while planning, deliberately **not** done here:

1. **`methods.module.css:7` is a dead rule.** `.counts .num { color: var(--ink); font-weight: 500 }`
   compiles `.num` to a hashed local class, but the markup applies the **global** `num`
   (`page.tsx:74-78`, `className="num"`). It has therefore never matched. The fix is
   `.counts :global(.num)`. Left alone: it is a drive-by cleanup, it changes desktop pixels (the
   count numbers would become `--ink` and 500-weight for the first time), and desktop is explicitly
   out of scope for this plan set. **Worth its own card.**
2. **The whole-row `::after` overlay swallows `data-tip` hovers** on `Dots` and the status chip.
   This is already true on desktop today; the card mirrors it rather than diverging. Both elements
   keep their `aria-label`/`role="img"`, so assistive tech is unaffected. A real fix would mean
   raising the tooltip targets above the overlay (`position: relative; z-index: 1`, the way
   `.sourceLink` does at `:55`) and belongs with whoever owns tooltip behaviour, not a responsive
   pass.
3. **`/sera/methods/[id]`** — the same card-vs-table treatment for the variants table is **Phase 4**
   (R1). This phase touches nothing under `[id]/`. **Settled by the reconciler:** phase 4 now uses
   these names for the ideas both pages have — `.cards`, `.card`, `.cardHead`, `.stats`, `.stat`,
   `.statLabel`, `.statValue` — and the same card geometry (`border-radius: 28px`,
   `background: var(--stone)`, `padding: 16px 18px 14px`, `gap: 10px`) and the same
   `ideas.module.css .label` small-caps label. `.cardLink` / `.cardScore` / `.cardGo` /
   `.cardTitles` stay phase-3-only (a variant card is not a link), and phase 4 keeps `v`-prefixed
   names for the pieces only it has. Separate CSS modules, so nothing collides. Phase 4 also drops
   `<Term>` from its card labels and spells them out, as this phase does.
4. **`Term`'s containing-block fix** stays in `Term.module.css` (**Phase 2**, R2). `.tableWrap` is
   deliberately left `position: static`; see *Desktop must not drift*.
5. **The 56 untested methods** could carry `view.ts`'s `untestedNote(m)` — a status-specific
   sentence — instead of the flat "Not tested yet". Not done: it is new copy on an existing page
   (a design change, not a responsive one), it would roughly double an untested card's height, and
   the status chip's tooltip already carries the nuance.

## Rollback

This phase is one commit on `feature/sera-responsive` touching exactly two files, and every change
is additive: one appended `@media (max-width: 1023.98px)` block, one className gaining `desk-only`,
one new hidden-at-desktop `<ul>`, and two new local components.

```bash
git revert <sha>          # restores the 1200px-table-in-a-scroller narrow layout
```

Nothing outside `web/app/sera/methods/` is touched. No migration runs. `lab/lab.sqlite` and
`web/data/lab.json` are read-only to this phase and are never written. Desktop is unaffected by
both the change and the revert.
