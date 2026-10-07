> Adopted from `JOURNAL_UNSEEN_BADGES_PLAN.md` phase 3. Source: `.workflows/plan/journal-unseen-badges/phase-3.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 3: The page renders unseen counts, the boundary, and per-card state

**Plan set:** `JOURNAL_UNSEEN_BADGES_PLAN.md`
**Analysis:** `20261007-103957-J4N8_code_analyzer.md`
**Satisfies:** R1 (unseen entries sit at the top of every section, seen entries below a boundary), R3 (the number on each of the seven tab icons is the true unseen count)
**Depends on:** Phase 1, Phase 2
**Difficulty:** NORMAL
**Package:** `web/app/sera/journal`

---

## READ THIS FIRST — phase 2's real interface, reconciled

This phase was planned in parallel with phase 2, which owns `view.ts`. **The reconciler has
since read phase 2's plan and rewritten every name in this file to match it.** There are no
guesses left and no alternatives to choose between: what is written below is phase 2's actual
contract.

The names this phase consumes, all from `./view`:

| Name | Shape | Notes |
|---|---|---|
| `unseenCounts(insights, seen?)` | `Record<KindFilter, number>` | keyed by all seven tabs — `fresh.all` is the unseen total, **no `INSIGHT_KINDS.reduce` needed** |
| `badgeTip(heading, unseen, total)` | `string` | the single formatter for all seven tab tooltips; the copy lives in `view.ts`, not here |
| `SEEN_COPY.boundary` / `.marker` / `.markerLabel` | `'Seen earlier'` / `'New'` / `'Not seen yet'` | the divider label, the marker's tooltip, the marker's screen-reader text |
| `journalGroups(insights, filter, seen?)` | `JournalGroup[]` | third parameter optional |
| `JournalGroup.unseen` / `.seen` | `JournalEntry[]` where `JournalEntry = { insight: LabInsight; unseen: boolean }` | already sorted newest-first, already partitioned — **this phase renders them directly, with no adapter** |
| `JournalGroup.items` | `JournalEntry[]` | `unseen` then `seen`; `items.length` is the group's entry count |
| `JournalGroup.unseenCount` | `number` | `=== unseen.length`; the boundary test is `g.unseenCount > 0 && g.unseenCount < g.items.length` |
| `JournalGroup.entries` | `LabInsight[]` | still exported by phase 2 and asserted by `view.test.ts`. **This phase stops using it and must not remove it** — `view.ts` is phase 2's file and this phase does not touch it. |

Still read `web/app/sera/journal/view.ts` as it stands after phase 2 landed before you type —
the code is the final word — but expect it to match the table above exactly.

---

## Goal

`/sera/journal` stops counting inventory and starts counting news. The seven badges carry the
number of **unseen** entries for their tab, each section lists its unseen entries first and its
already-seen entries below a quiet divider, and every card is tagged with its insight id and its
server-rendered unseen state. The page stays a pure server component and gains the three
`data-` hooks phase 4's client island binds to.

## Interface Contract

**Creates (DOM hooks — this is a contract phase 4 depends on and cannot negotiate):**

- `article[data-insight-id="<number>"]` — on **every** insight card, seen or unseen. The value is
  `LabInsight.id` rendered as a decimal string. This is the handle phase 4's
  `IntersectionObserver` enumerates (`document.querySelectorAll('[data-insight-id]')`).
- `article[data-unseen="true" | "false"]` — on **every** insight card. **Always present, never
  omitted**, so phase 4 can both (a) skip cards already seen on the server and (b) retire a
  marker live by setting the attribute to `"false"`. The value is a string, not a JSX boolean —
  a JSX `false` would drop the attribute entirely.
- `a[data-seen-click]` — on the redirect-arrow `<Link>` inside `.cardFoot`. Rendered as
  `data-seen-click="true"`; phase 4 must select on **attribute presence**
  (`[data-seen-click]`), never on the value. The arrow's own insight id is reached with
  `el.closest('[data-insight-id]')`. The arrow exists only on cards that have both a `methodId`
  and a resolving `methodById()` — 21 of the 26 insights in today's snapshot. The other 5 have
  no arrow at all and can only ever be marked seen by phase 4's dwell rule.
- `article[data-seen-now]` — **not rendered by this phase**; phase 4's island sets it
  imperatively on a card it marks during the visit. This phase owns the CSS that reads it (see
  below), because `journal.module.css` is this phase's file and phase 4 touches it not at all.
- CSS class `journal.module.css` `.new` — the unseen dot. **Its visibility is driven by
  attributes, not by React.** The element is always in the DOM. Three rules, all in this phase's
  file:
  - `.card[data-unseen='true'] .new` — shown.
  - `.card[data-seen-now] .new` — **also shown, but at `opacity: 0` with a 240ms transition.**
    This is what lets phase 4 retire a marker live without the dot's box collapsing and reflowing
    the title beside it (invariant 5). Phase 4 sets `data-unseen="false"` *and* `data-seen-now`
    on the same card, so the dot fades in place and the card does not move by a pixel.
  - Everything else is `display: none`.
  There is **no `data-unseen-marker` attribute in this plan set.** The rule lives in this phase's
  own CSS module, where the hashed `.new` class name is in scope, so no extra hook is needed.
- CSS classes `.boundary`, `.sr` in `journal.module.css`.

**Creates (page):**

- `export const dynamic = 'force-dynamic'` in `web/app/sera/journal/page.tsx`. This is the only
  place in this plan set that adds it to `page.tsx`; phase 1 declares its own, separately, in
  `web/app/api/sera/journal/seen/route.ts`. Neither touches the other's file.
- `InsightCard` gains a required `unseen: boolean` prop.
- The `options` array grows two fields, `heading: string` and `total: number`, beside its
  existing `id` / `tip` / `n` / `Icon`. They are the two arguments `badgeTip` takes beside the
  live count, and phase 4 reads them straight off `options` to keep the tooltip honest as the
  badge falls — which is why they are fields rather than inline expressions.

**Signature changes:** none that leave this file. `InsightCard` is module-private to `page.tsx`.

**Deletes:** nothing. `kindCounts` is still imported and still called — the tooltip says
"2 new of 4", and the 4 comes from `kindCounts`.

**Requires (from earlier phases):**

- Phase 1: `seenInsightIds(): Promise<Set<number>>`, server-only, exported from
  `web/lib/sera/seen.ts`, imported here as `@/lib/sera/seen`. It swallows its own errors and
  resolves to an empty set when Neon is unreachable (invariant 9). **This phase adds no
  `try`/`catch` around it** — a second one would hide a real bug, and phase 1 already owns the
  degrade.
  *(Phase 1 also exports `unseenCount(ids): Promise<number | null>`. That one is phase 5's, for
  the rail: it is the only reader that can tell "the read failed" from "nothing is unseen". This
  page wants the whole set, so it uses `seenInsightIds`. The two are not duplicates — they answer
  different questions.)*
- Phase 2: `journalGroups(insights, filter, seenIds?)` — the seen-set is a trailing **optional**
  `ReadonlySet<number>` parameter; `JournalGroup` carries the unseen/seen partition as
  `unseen` / `seen` / `items` / `unseenCount`, each entry a `{ insight, unseen }`.
- Phase 2: `unseenCounts(insights, seen?): Record<KindFilter, number>` — keyed by all seven tabs,
  so `fresh.all` is the unseen total and the `'all'` sentinel needs no special case.
- Phase 2: `badgeTip(heading, unseen, total): string` — the single formatter for the seven tab
  tooltips. This page does **not** write its own tip string; phase 4 calls the same function when
  it rewrites a tooltip live, so there is exactly one place the wording exists.
- Phase 2: `SEEN_COPY` — `.boundary` for the divider label, `.marker` for the marker's tooltip,
  `.markerLabel` for its screen-reader text.

**Leaves alone (owned by others):**

- `web/app/sera/journal/view.ts`, `view.test.ts` — phase 2.
- `web/lib/sera/seen.ts`, `web/app/api/sera/journal/seen/route.ts` — phase 1.
- `web/components/sera/SeraNav.tsx`, `SeraNav.module.css`, `web/app/sera/layout.tsx`,
  `web/package_readme.md` — phase 5.
- `web/app/sera/journal/JournalSeen.tsx`, `seen-client.ts` — phase 4. **No `'use client'`
  anywhere in this phase**, and nothing is mounted.
- `web/components/sera/Section.tsx`, `PageHeader.tsx`, `web/lib/sera/*` except the new
  `seen.ts` import, `web/data/lab.json`, `web/app/globals.css`.

## Files

| File | Action | What changes |
|---|---|---|
| `web/app/sera/journal/page.tsx` | modify | `force-dynamic`; await `seenInsightIds()`; badges carry unseen counts and `badgeTip` tooltips; `options` grows `heading` and `total`; each section renders `g.unseen`, the boundary, then `g.seen`; `InsightCard` takes `unseen` and carries the three `data-` hooks |
| `web/app/sera/journal/journal.module.css` | modify | four new rules appended — `.new` (the unseen dot, attribute-driven, including the `[data-seen-now]` fade phase 4's island triggers), `.boundary` (the divider), `.sr` (screen-reader-only text) |

Nothing is created and nothing is deleted.

## Implementation Steps

### Step 1: Make the page dynamic and read the seen-set

**File:** `web/app/sera/journal/page.tsx:17` (just under the `metadata` export) and `:30-36`
(the top of `JournalPage`)

**Change:** The page now reads a Neon table, so it must declare `force-dynamic` the way every
`(app)` page that reads Neon does (`web/app/(app)/page.tsx:16`). `requireSera()` already makes
the route dynamic in practice; the declaration is the convention, and it keeps the page honest
if the gate is ever changed.

The seen-set read goes **after** `requireSera`, not in parallel with it: gate first, query
second, so an unauthorised request never touches the database. It is one `await` and the query
is a single-column scan of a table with at most as many rows as there are insights.

**Code:** the finished shape of these lines appears in Step 5, which gives the complete file.
The two pieces are:

```tsx
// The page reads journal_seen from Neon, so it is never cached — the (app) convention.
export const dynamic = 'force-dynamic';
```

```tsx
  const q = await searchParams;
  const filter = parseKind(q.kind);
  await requireSera(journalHref(filter));
  const seenIds = await seenInsightIds();
```

The set is named `seenIds`, not `seen`, on purpose: `seen` is taken inside the section loop by
the group's already-read entry list, and the shadowing would be a trap.

**Impact:** the page is explicitly uncached. With Neon unreachable, `seenInsightIds()` resolves
to an empty set and the page renders with every entry unseen — which is exactly today's render
plus a dot on every card. The Journal never 500s on a database outage (invariant 9).

### Step 2: The seven badges carry unseen counts

**File:** `web/app/sera/journal/page.tsx:34-46`

**Change:** `kindCounts(lab.insights)` stays — the tooltip still wants the total. Alongside it,
`unseenCounts(lab.insights, seenIds)` gives the per-kind unseen tally. Phase 2 keys that record
by `KindFilter`, so **`fresh.all` is the unseen total** and the `'all'` sentinel needs no
arithmetic of its own: no `INSIGHT_KINDS.reduce`, no summing, one lookup.

INVARIANT 8 is preserved to the letter: the `options` array is still the `'all'` sentinel
followed by `INSIGHT_KINDS.map(...)` in its declared order, each entry still carries
`KIND_ICON[k]`, each `<Link>` still has `className={`icon-btn md ${s.segBtn}`}`, `data-tip`,
`aria-label`, `aria-current`, the same `<Icon size={19} strokeWidth={on ? 2 : 1.5} />`, and the
same `<span className={s.badge}>` in the corner. Only `n` changes meaning, from total to unseen.

**The tooltips come from phase 2's `badgeTip(heading, unseen, total)`** — this page writes no tip
string of its own. `badgeTip` returns "Risks we see · 2 new of 4" when something is new, "Risks
we see · 4 entries, all seen" at zero, and "Ideas worth testing · none yet" for an empty kind;
that wording is phase 2's, tested in `view.test.ts`, and phase 4 calls the same function when it
rewrites a tooltip as the badge falls. One formatter, three callers, no duplicated copy.

To let phase 4 call it without re-deriving anything, each `options` entry carries the two
arguments `badgeTip` needs beside the live count:

```tsx
  { id: 'all', heading: 'Everything', total, tip: badgeTip('Everything', fresh.all, total), n: fresh.all, Icon: ListFilter }
```

`heading` and `total` are new fields on `options` (and on its inline type annotation). Phase 4
reads them off the same array and adds nothing to it.

`.badge.zero` (`journal.module.css:13`) now fires whenever a tab has nothing new rather than
only when a kind is empty outright. That is the style doing its real job and needs no change.

**Impact:** with an empty `journal_seen` table the badges show exactly the numbers they show
today, because nothing has been seen. As ids land in the table, each badge falls and goes muted
at zero. The `hypothesis` tab, which has no entries at all in today's snapshot, shows `0` muted
both before and after — unchanged.

### Step 3: No adapter — render phase 2's partition directly

**File:** none — a deliberate non-step, recorded so nobody re-adds the helper.

Phase 2's `JournalGroup` already carries exactly what this page renders:

- `g.unseen` — the unseen half, `JournalEntry[]`, newest-first.
- `g.seen` — the seen half, `JournalEntry[]`, newest-first.
- `g.items` — the two concatenated; `g.items.length` is the group's entry count.
- `g.unseenCount` — `=== g.unseen.length`, and the index at which the seen half begins.

So there is **no `split()` helper in this phase** and no adapter of any kind. The section body
maps `g.unseen` and `g.seen` straight into `InsightCard`s, dereferencing `e.insight` at the call
site. A pass-through function between the two would be a layer that explains nothing.

A card's unseen state is still determined by **which of the two lists it came from**, so the
`unseen` prop and the card's position cannot disagree. `e.unseen` is available on every entry
and is deliberately not read — the list is the fact.

`g.entries` is likewise not read by this page any more. It stays in `view.ts` because phase 2
owns that file and `view.test.ts` asserts it; this phase must not remove it.

### Step 4: The section body — unseen, boundary, seen

**File:** `web/app/sera/journal/page.tsx:75-90`

**Change:** The `groups.map(...)` callback grows a body: it reads `g.items.length` as the entry
count and renders `g.unseen`, the boundary, then `g.seen`. The boundary renders **only when both
sides are non-empty** — phase 2's own test names this condition and this page uses it verbatim:

```tsx
g.unseenCount > 0 && g.unseenCount < g.items.length
```

A section with nothing seen yet, a section where everything has been read, and an empty section
all render with no stray divider.

The boundary element is a `<p>` inside the `.cards` grid carrying `grid-column: 1 / -1`, so it
spans both columns on desktop and the single column below 1024px. It is a quiet labelled
hairline, styled like an eyebrow, not another section header.

The `Section`'s `eyebrow` stays **exactly** what it is today — `"N entries"`. It is tempting to
append "· 2 new", and this plan deliberately does not: phase 4 counts the badges down live, and
a second count in the sheet header would go stale mid-visit unless phase 4 maintained it too.
The badge, the tooltip and the boundary carry R3's signal; the eyebrow stays inventory. Same
reasoning for `s.barNote`, which is left verbatim.

The order within each list is phase 2's, computed once on the server from the seen-set as it
stood at request time. Nothing here re-sorts, and phase 4 must never move a card
(invariant 5).

**Impact:** R1 is satisfied end to end on the server. With JavaScript disabled the partition,
the boundary and the badges are all still correct — only the live countdown needs the client.

### Step 5: `InsightCard` — the `unseen` prop and the three hooks

**File:** `web/app/sera/journal/page.tsx:96-120`

**Change:** `InsightCard` takes a required `unseen: boolean`. The `<article>` carries
`data-insight-id` and `data-unseen`; the title gains a marker span that CSS shows only when
`data-unseen` is `"true"`; the redirect-arrow `<Link>` gains `data-seen-click="true"`.

The marker is rendered **unconditionally** and hidden by CSS, rather than rendered behind
`{unseen && ...}`. That is the whole point: phase 4 retires the marker on a card by setting
attributes, with no React involvement and no risk of the island and the server disagreeing about
what is in the DOM. The accessible text (`SEEN_COPY.markerLabel`, "Not seen yet") lives inside
the same span, so it disappears with it — a `.sr` span uses `clip`, which screen readers still
read, so it must be inside the element CSS sets to `display: none`, not beside it.

The marker also carries `data-tip={SEEN_COPY.marker}` ("New"), so hovering the dot explains it
through the delegated tooltip layer this page already uses on every tab and every arrow
(`components/TooltipLayer.tsx`). That is the third of `SEEN_COPY`'s strings and the reason all
three are exported: the dot's meaning is copy, and copy on this page lives in `view.ts`.

`aria-hidden` is **not** put on the marker: the dot is drawn by `.new::before`, which is already
invisible to assistive technology, and the `.sr` text inside is the accessible rendering of the
same fact.

**Code — the complete new contents of `web/app/sera/journal/page.tsx`:**

```tsx
import {
  ArrowUpRight, Database, FlaskRound, Layers, ListFilter, Sparkles, TriangleAlert, Wrench, type LucideIcon,
} from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { requireSera } from '@/lib/sera/gate';
import { INSIGHT_KIND_LABEL } from '@/lib/sera/glossary';
import { lab, methodById } from '@/lib/sera/lab';
import { renderMarkdown } from '@/lib/sera/markdown';
import { seenInsightIds } from '@/lib/sera/seen';
import { INSIGHT_KINDS, type InsightKind, type LabInsight } from '@/lib/sera/types';
import {
  SEEN_COPY, badgeTip, dayLabel, journalGroups, journalHref, kindCounts, parseKind, unseenCounts,
  type KindFilter,
} from './view';
import s from './journal.module.css';

// The layout's title template renders this as "Journal · Sera".
export const metadata: Metadata = { title: 'Journal' };

// The page reads journal_seen from Neon, so it is never cached — the (app) convention.
export const dynamic = 'force-dynamic';

const KIND_ICON: Record<InsightKind, LucideIcon> = {
  synthesis: Layers,
  observation: Sparkles,
  hypothesis: FlaskRound,
  'data-wish': Database,
  'feature-wish': Wrench,
  risk: TriangleAlert,
};

type Search = { kind?: string | string[] };

export default async function JournalPage({ searchParams }: { searchParams: Promise<Search> }) {
  const q = await searchParams;
  const filter = parseKind(q.kind);
  await requireSera(journalHref(filter));
  const seenIds = await seenInsightIds();
  const counts = kindCounts(lab.insights);
  const fresh = unseenCounts(lab.insights, seenIds);
  const groups = journalGroups(lab.insights, filter, seenIds);
  const total = lab.insights.length;

  // heading + total ride along on every option: they are badgeTip's other two arguments, and the
  // client island (phase 4) reads them off this array to keep the tooltip honest as `n` falls.
  const options: { id: KindFilter; heading: string; total: number; tip: string; n: number; Icon: LucideIcon }[] = [
    {
      id: 'all',
      heading: 'Everything',
      total,
      tip: badgeTip('Everything', fresh.all, total),
      n: fresh.all,
      Icon: ListFilter,
    },
    ...INSIGHT_KINDS.map(k => ({
      id: k as KindFilter,
      heading: INSIGHT_KIND_LABEL[k].heading,
      total: counts[k],
      tip: badgeTip(INSIGHT_KIND_LABEL[k].heading, fresh[k], counts[k]),
      n: fresh[k],
      Icon: KIND_ICON[k],
    })),
  ];

  return (
    <>
      <PageHeader
        eyebrow="Journal"
        title="What the lab is thinking"
        lede="Everything the lab noticed along the way: lessons, hunches, the data and tools it wishes it had, and the risks it sees. Food for thought, newest first."
        asOf={lab.asOf}
      />
      <div className={s.page}>
        <div className={s.bar}>
          <nav className="seg" aria-label="Show one kind of entry">
            {options.map(({ id, tip, n, Icon }) => {
              const on = id === filter;
              return (
                <Link key={id} href={journalHref(id)} replace scroll={false} className={`icon-btn md ${s.segBtn}`}
                  data-tip={tip} aria-label={tip} aria-current={on ? 'true' : undefined}>
                  <Icon size={19} strokeWidth={on ? 2 : 1.5} />
                  <span className={`${s.badge} ${n === 0 ? s.zero : ''}`} aria-hidden="true">{n}</span>
                </Link>
              );
            })}
          </nav>
          <p className={s.barNote}>
            {total} {total === 1 ? 'entry' : 'entries'} in all. Every lab run adds to this page.
          </p>
        </div>

        {groups.map(g => {
          const n = g.items.length;
          return (
            <Section
              key={g.kind}
              eyebrow={`${n} ${n === 1 ? 'entry' : 'entries'}`}
              title={g.heading}
              caption={g.caption}
            >
              {n === 0 ? (
                <p className={s.empty}>{g.empty}</p>
              ) : (
                <div className={s.cards}>
                  {g.unseen.map(e => (
                    <InsightCard key={e.insight.id} insight={e.insight} tone={g.tone} unseen />
                  ))}
                  {g.unseenCount > 0 && g.unseenCount < n && (
                    <p className={s.boundary}>{SEEN_COPY.boundary}</p>
                  )}
                  {g.seen.map(e => (
                    <InsightCard key={e.insight.id} insight={e.insight} tone={g.tone} unseen={false} />
                  ))}
                </div>
              )}
            </Section>
          );
        })}
      </div>
    </>
  );
}

function InsightCard({ insight, tone, unseen }: { insight: LabInsight; tone: string; unseen: boolean }) {
  const method = insight.methodId ? methodById(insight.methodId) : undefined;
  return (
    <article
      className={`${s.card} ${tone}`}
      data-insight-id={insight.id}
      data-unseen={unseen ? 'true' : 'false'}
    >
      <header className={s.cardHead}>
        <h3 className={s.cardTitle}>
          <span className={s.new} data-tip={SEEN_COPY.marker}>
            <span className={s.sr}>{SEEN_COPY.markerLabel}: </span>
          </span>
          {insight.title}
        </h3>
        <time className={s.date} dateTime={insight.added}>{dayLabel(insight.added)}</time>
      </header>
      <div className={s.body} dangerouslySetInnerHTML={{ __html: renderMarkdown(insight.body) }} />
      {insight.methodId && (
        <footer className={s.cardFoot}>
          <span className={s.about}>
            About {insight.methodId}{method ? ` · ${method.name}` : ''}
          </span>
          {method && (
            <Link href={`/sera/methods/${encodeURIComponent(method.id)}`} className="icon-btn sm"
              data-seen-click="true"
              aria-label={`Open ${method.id}, ${method.name}`} data-tip={`Open ${method.id}`}>
              <ArrowUpRight size={18} strokeWidth={1.5} />
            </Link>
          )}
        </footer>
      )}
    </article>
  );
}
```

**Impact:** every card in the DOM is addressable by its insight id and declares its state.
`dangerouslySetInnerHTML` is untouched — `renderMarkdown` is still escape-first
(`lib/sera/markdown.ts`), and nothing new is interpolated into HTML. The tooltip layer is
unaffected: it is globally delegated on `data-tip` (`components/TooltipLayer.tsx`,
`components/tooltip.ts`) and neither new attribute collides with it.

### Step 6: The CSS — the dot, the divider, the screen-reader span

**File:** `web/app/sera/journal/journal.module.css` — append after `.empty`
(line 35), before the `@media (max-width: 1023.98px)` block at line 37

**Change:** four new rules. Nothing existing is edited: `.badge`, `.badge.zero`, `.segBtn`,
`.cards`, `.card`, `.cardHead`, `.cardTitle`, `.date`, `.body`, `.cardFoot`, `.about`, `.empty`
and the 1023.98px breakpoint all stay exactly as they are, the two-column grid included.

Only tokens already in use on this page are used: `--coral` for the dot (the same colour as the
badge it counts toward), `--ink-2` for the divider's label and `--hair` for its rules (the same
pair `.date`/`.about` and the body's table borders already use). No new token, no new colour.

**Code — the four rules, verbatim:**

```css
/* An unseen card's marker: a coral dot before the title, the same colour as the badge it counts
   toward. Shown by the data-unseen attribute rather than by React, so the client island can
   retire one card's marker by flipping attributes (plan invariant 5: it never moves a card).
   [data-seen-now] is set by phase 4's island on a card marked during this visit: the dot KEEPS
   its box and fades, so retiring it never reflows the title beside it. The island sets both
   data-unseen="false" and data-seen-now, and the second rule is what stops the first collapsing
   the box. This rule lives here, in phase 3's own module, because the hashed `.new` class is only
   in scope in this file — which is why this plan set has no `data-unseen-marker` attribute. */
.new { display: none; margin-right: 9px; }
.card[data-unseen='true'] .new, .card[data-seen-now] .new { display: inline-block; }
.card[data-seen-now] .new { opacity: 0; transition: opacity 240ms ease; }
.new::before {
  content: ''; display: inline-block; width: 8px; height: 8px;
  border-radius: 999px; background: var(--coral); vertical-align: 0.12em;
}

/* The line between what is new and what has already been read. A labelled hairline spanning the
   whole grid — a quiet divider, deliberately not a second section header. */
.boundary {
  grid-column: 1 / -1; display: flex; align-items: center; gap: 12px; margin: 2px 0;
  font-size: 13px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink-2);
}
.boundary::before, .boundary::after { content: ''; flex: 1 1 auto; height: 1px; background: var(--hair); }

/* Visible to screen readers only (the same rule ideas.module.css uses). */
.sr {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden;
  clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
}
```

**Code — the complete `journal.module.css` after the change, for an exact diff:**

```css
/* Journal: a filter bar, then one sheet per kind holding two columns of insight cards. */
.page { display: flex; flex-direction: column; gap: 12px; }

.bar { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 4px 0 2px; }
.barNote { font-size: 15px; color: var(--ink-2); }
.segBtn { position: relative; }
.badge {
  position: absolute; top: -4px; right: -4px; min-width: 20px; height: 20px; padding: 0 6px;
  border-radius: 999px; background: var(--coral); color: var(--on-coral);
  font-size: 11.5px; line-height: 20px; text-align: center; font-variant-numeric: tabular-nums;
  pointer-events: none;
}
.badge.zero { background: var(--outline); color: var(--ink-2); }

.cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.card { border-radius: 28px; padding: 22px 24px 20px; display: flex; flex-direction: column; gap: 12px; }
.cardHead { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; }
.cardTitle { margin: 0; font-size: 20px; font-weight: 500; letter-spacing: -0.01em; line-height: 1.25; }
.date { flex: none; font-size: 13px; color: var(--ink-2); white-space: nowrap; }

.body { font-size: 15.5px; line-height: 1.5; overflow-wrap: anywhere; }
.body :global(p) { margin: 0 0 10px; }
.body :global(p:last-child) { margin-bottom: 0; }
.body :global(ul), .body :global(ol) { margin: 0 0 10px; padding-left: 20px; }
.body :global(li) { margin: 2px 0; }
.body :global(strong) { font-weight: 600; }
.body :global(code) { font-size: 0.92em; padding: 1px 6px; border-radius: 6px; background: var(--chip); }
.body :global(a) { text-decoration: underline; text-underline-offset: 3px; }
.body :global(h3), .body :global(h4), .body :global(h5) { margin: 12px 0 6px; font-size: 16px; font-weight: 500; }
.body :global(table) { border-collapse: collapse; font-size: 14px; margin: 0 0 10px; }
.body :global(th), .body :global(td) { padding: 6px 12px 6px 0; border-bottom: 1px solid var(--hair); text-align: left; font-weight: 400; }

.cardFoot { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-top: 4px; }
.about { font-size: 14px; color: var(--ink-2); }
.empty { font-size: 16px; color: var(--ink-2); }

/* An unseen card's marker: a coral dot before the title, the same colour as the badge it counts
   toward. Shown by the data-unseen attribute rather than by React, so the client island can
   retire one card's marker by flipping attributes (plan invariant 5: it never moves a card).
   [data-seen-now] is set by phase 4's island on a card marked during this visit: the dot KEEPS
   its box and fades, so retiring it never reflows the title beside it. */
.new { display: none; margin-right: 9px; }
.card[data-unseen='true'] .new, .card[data-seen-now] .new { display: inline-block; }
.card[data-seen-now] .new { opacity: 0; transition: opacity 240ms ease; }
.new::before {
  content: ''; display: inline-block; width: 8px; height: 8px;
  border-radius: 999px; background: var(--coral); vertical-align: 0.12em;
}

/* The line between what is new and what has already been read. A labelled hairline spanning the
   whole grid — a quiet divider, deliberately not a second section header. */
.boundary {
  grid-column: 1 / -1; display: flex; align-items: center; gap: 12px; margin: 2px 0;
  font-size: 13px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink-2);
}
.boundary::before, .boundary::after { content: ''; flex: 1 1 auto; height: 1px; background: var(--hair); }

/* Visible to screen readers only (the same rule ideas.module.css uses). */
.sr {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden;
  clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
}

@media (max-width: 1023.98px) {
  .cards { grid-template-columns: 1fr; }
  .bar { flex-direction: column; align-items: flex-start; }
}
```

**Impact:** the dot adds 8px plus a 9px gutter to the first line of an unseen card's title;
`.cardTitle` already wraps, and later lines align to the card's left edge. `--coral` and
`--ink-2`/`--hair` are all redefined under `prefers-color-scheme: dark` in
`globals.css:55-68`, so both the dot and the divider follow the theme with no dark-mode rule of
their own. `grid-column: 1 / -1` is valid in both the two-column and the single-column grid, so
the divider spans the full width at every breakpoint. No existing selector gains or loses
specificity.

### Step 7: Verify the shape against what phase 2 actually landed

**File:** none — a check, not an edit

**Change:** Before running the build, re-read `web/app/sera/journal/view.ts` and confirm it
exports `SEEN_COPY`, `unseenCounts`, `badgeTip` and a three-parameter `journalGroups` whose
`JournalGroup` carries `unseen` / `seen` / `items` / `unseenCount` as the table at the top of
this plan says. `npx tsc --noEmit` catches every mismatch except a same-named function with a
different return shape.

**Impact:** phase 2's contract has already been reconciled against this plan, so a mismatch here
means phase 2 drifted from its own plan — fix `view.ts` to match its plan, or raise it; do not
bend this file around it.

## Verification

The worktree's `web/node_modules` is already a symlink to `/home/miftah/seer/web/node_modules`
(`package.json` and `package-lock.json` are byte-identical to the base commit), and
`npx tsc --noEmit` is confirmed clean on the base tree. **Do not run `npm ci` or `npm install`.**

**Build:** `cd web && npx tsc --noEmit && npx next build`
**Tests:** `cd web && npm test` (vitest; `view.test.ts` is phase 2's and must stay green — this
phase adds no test, because a server component rendering a bundled snapshot has no unit seam
the repo tests today; the `app/sera/journal` suite covers the logic this page now consumes)

**Manual check** (`cd web && npm run dev`, then `/sera/journal`):

1. With `journal_seen` empty: every badge shows the number it showed before the change, every
   card has the coral dot, no section shows a divider, and the tooltips read "Everything · 26 new
   of 26", "Risks we see · 4 new of 4", and — for the empty `hypothesis` tab — "Ideas worth
   testing · none yet". Those exact strings come from phase 2's `badgeTip`, which `view.test.ts`
   already asserts; if one of them is wrong, the bug is in `view.ts`, not here.
2. `INSERT INTO journal_seen (insight_id, via) VALUES (1,'view'), (3,'view'), (5,'click');`
   then reload: the observation badge drops by 3, the `all` badge drops by 3, those three cards
   lose their dots, sit below a divider reading the boundary copy, and the remaining
   observations stay above it newest-first.
3. Mark every observation seen: the observation tab's badge reads `0` in the muted
   `.badge.zero` style, its tooltip reads "What we learned · 18 entries, all seen", the section
   shows all its cards below the divider with none above it, and **no stray divider** appears at
   the top. Mark none of the risks: the risk section shows no divider either.
4. `?kind=risk`, `?kind=hypothesis`, `?kind=bogus` still filter and fall back exactly as before;
   the active tab still carries `aria-current="true"`; hovering a tab still shows the tooltip
   through the delegated layer.
5. In devtools, `document.querySelectorAll('[data-insight-id]').length` equals the number of
   cards on the page, every one of them has a `data-unseen` of `"true"` or `"false"`, and
   `document.querySelectorAll('[data-seen-click]').length` equals the number of cards with a
   resolving method (21 of 26 on the full page in today's snapshot).
6. Set a card's `data-unseen` to `"false"` by hand in devtools: its dot disappears. Then set
   `data-unseen="false"` **and** `data-seen-now=""` on another card: its dot fades out over
   ~240ms and the title does **not** shift left — the box stays. That pair is exactly what phase
   4's island does, and it is the contract phase 4 relies on.
7. Stop Neon (or point `DATABASE_URL` at a dead host): the page still renders, everything
   unseen, no error page.
8. Narrow the window below 1024px: the cards collapse to one column, the divider still spans the
   full width, the bar still stacks.

**Exit criteria:** the seven badges show unseen counts and nothing else about the bar changed;
each section lists unseen entries, then a divider, then seen entries, with the divider present
only when both sides are non-empty; every card carries `data-insight-id` and `data-unseen`;
every redirect arrow carries `data-seen-click`; `npx tsc --noEmit && npm test` are clean;
nothing in the page is a client component.

## Handoffs

**To phase 4 — the live bar is settled: `data-` hooks on this markup, not a client component.**
Phase 4's plan takes that route and this plan leaves the bar ready for it. Concretely:

- Phase 4 adds `data-badge-kind={id}` to each `<span className={s.badge}>` and rewrites
  `textContent` plus the `s.zero` class as ids are marked. That is phase 4's one attribute on
  this file; everything else in the bar stays as written above.
- **The tooltip is rewritten by calling `badgeTip` again, not by templating.** `view.ts` is pure
  — it imports only `lib/sera/glossary` and `lib/sera/types`, both of which are pure and
  type-only beyond `INSIGHT_KIND_LABEL` — so a `'use client'` island may import it. Phase 4
  reads `heading` and `total` off this page's `options` array, passes them to `badgeTip` with
  the live count, and sets `data-tip`/`aria-label` on the enclosing `<Link>`. There is no
  `data-tip-template` attribute anywhere in this plan set: one formatter, one copy of the words.
- The *lift the bar into a client component* alternative was rejected. The trap that killed it:
  `options` carries `Icon: LucideIcon`, a **function**, which a server component cannot pass
  across the client boundary — a `JournalBar.tsx` would have to own `KIND_ICON` and pull
  `lucide-react` into a client bundle, and it would mean cutting this phase's bar markup out
  from under itself in the very next phase.

**To phase 4 — three things this phase deliberately did not make live.** The section eyebrow
(`"4 entries"`), `s.barNote` (`"26 entries in all…"`) and the boundary's position are all
inventory facts or frozen positions, not unseen counts, so none of them goes stale as the reader
reads. If phase 4 wants the sheet headers to count down too, it owns that decision and the extra
hook; this plan kept the live surface to exactly one thing — the badge — so invariant 5 is easy
to hold.

**To phase 4 — the five arrow-less cards.** `page.tsx` renders the footer only when
`insight.methodId` is set and the arrow only when `methodById()` resolves. In today's snapshot 5
of 26 insights have no `methodId` and therefore no `[data-seen-click]` anywhere in the card.
They still carry `data-insight-id` and `data-unseen`, so the dwell rule is the only thing that
will ever mark them — which is exactly R2's point.

**To phase 5 — the unseen total is *not* taken from here.** This page reads `fresh.all` from
phase 2's `unseenCounts`, which needs the whole seen-set. Phase 5's rail must distinguish "the
read failed" from "nothing is unseen" (invariant 9 — no badge on failure), and an empty `Set`
cannot say which it is, so phase 5 calls **phase 1's** `unseenCount(lab.insights.map(i => i.id))`
instead and renders no badge on `null` or `0`. The two paths agree on every successful read:
`unseenCount(allIds)` and `unseenCounts(lab.insights, seen).all` both count snapshot ids absent
from `journal_seen`. Nothing is imported from this page, which exports only its default
component.

**Not done, on purpose (would be scope creep):** no "mark all as read" control, no change to
`PageHeader`, no change to the `all` tab's behaviour of showing every section, no dimming or
restyling of already-seen cards beyond removing the dot, and no new design token.

## Rollback

`git revert` this phase's commit, or `git checkout <base> -- web/app/sera/journal/page.tsx
web/app/sera/journal/journal.module.css`. The page returns to total counts and a flat
newest-first list; phases 1 and 2 become dead code that still builds and still tests green, and
the `journal_seen` table keeps whatever rows it has. Nothing outside these two files is touched,
so nothing else needs undoing. Note that phase 4's island binds to the `data-` hooks added here
— reverting this phase after phase 4 has landed breaks phase 4, so revert the two together.
