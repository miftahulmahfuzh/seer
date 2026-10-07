> Adopted from `JOURNAL_UNSEEN_BADGES_PLAN.md` phase 5. Source: `.workflows/plan/journal-unseen-badges/phase-5.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 5: The rail badge and the package readme

**Plan set:** `JOURNAL_UNSEEN_BADGES_PLAN.md`
**Analysis:** `20261007-103957-J4N8_code_analyzer.md`
**Satisfies:** R3 — the notification number is a real signal. Phases 2–4 make the Journal's own
seven badges truthful; this phase carries one number out to the Sera rail, so a new entry is
visible from `/sera`, `/sera/methods`, `/sera/ideas` and `/sera/how` — the only places the reader
can actually be *surprised* by it. Inside `/sera/journal` you are already looking at the thing.
**Depends on:** Phase 1 (`web/lib/sera/seen.ts`)
**Difficulty:** EASY
**Package:** `web` (`web/components/sera`, `web/app/sera`, `web/package_readme.md`)

---

## READ THIS FIRST — phase 1's real interface, reconciled

The reconciler has read phase 1's plan. **This phase calls exactly one function, and it is not
`seenInsightIds`:**

```ts
// web/lib/sera/seen.ts, phase 1
export async function unseenCount(insightIds: Iterable<number>): Promise<number | null>;
```

`unseenCount(ids)` returns how many of `ids` are *not* in `journal_seen`, or **`null` when the
read failed**. The rail calls it as:

```ts
await unseenCount(lab.insights.map(i => i.id))
```

and renders **no badge** when the result is `null` or `0`.

**Why this one and not `seenInsightIds`, in one sentence: invariant 9.** Invariant 9 says a
failed seen-state read degrades to the page still rendering, and this phase's exit criterion is
*no badge* on failure. `seenInsightIds()` swallows its own error and resolves to an empty `Set`,
and an empty set is indistinguishable from a clean read of an empty table — so a layout built on
it would show the full inventory (26 today) during a Neon outage and call it a notification.
Only `unseenCount`'s `null` can tell "the read failed" from "nothing is unseen". There is no
substitution table here and nothing to choose: `unseenCount` is the call.

**Both functions exist on purpose and neither is redundant.** They answer different questions:

| | question | caller |
|---|---|---|
| `seenInsightIds(): Promise<Set<number>>` | *which* entries are seen — the whole set, needed to partition and to count per kind | `/sera/journal`'s page (phase 3) |
| `unseenCount(ids): Promise<number \| null>` | *how many* of these ids are unseen, and did the read work | the Sera layout (this phase) |

The page needs the set and can afford to degrade to "everything unseen", because it is rendering
the entries anyway. The rail needs one number and must be able to say "I don't know". Phase 2's
`unseenCounts(insights, seen)` is a third thing again — the per-kind tally over a set the caller
already has, pure, no database. All three are live; none shadows another.

`unseenCount` deliberately takes the ids rather than reaching for the snapshot itself, so phase
1's API route never pulls `web/data/lab.json` (0.89 MB) into its bundle. **This phase supplies
them, from `lab.insights`.** That is also the derivation rule, and it is not negotiable:

```
unseen total = number of ids in `lab.insights` that are NOT in journal_seen
```

Never `SELECT count(*) FROM journal_seen`, and never `lab.insights.length - seenSet.size`. A
`journal_seen` row may name an insight id that is not in *this build's* `data/lab.json` (the
table is in Neon, the snapshot is bundled at build time, and they are versioned independently).
Counting rows makes the rail disagree with the seven badges `/sera/journal` renders — the one
thing this phase exists to prevent. `unseenCount(ids)` gets this right by construction: it only
ever looks at the ids you hand it.

Still read `web/lib/sera/seen.ts` as it stands after phase 1 landed before you type. If it
disagrees with the above, phase 1 drifted from its own plan — raise it rather than inventing a
fallback here.

---

## Goal

The Journal tab in Sera's left rail carries a small coral badge with the number of journal
entries the reader has not seen yet, visible from every `/sera/*` page, in both the ≥1024px rail
layout and the below-1024px top bar. A zero count renders no badge at all. And
`web/package_readme.md` stops claiming Sera never reads Neon: it describes the seen-state table,
the second web write, and every file this plan set added.

## Interface Contract

**Deletes:** none.

**Renames:** none.

**Creates:**
- `SeraNav` gains a prop: `function SeraNav({ journalUnseen = 0 }: { journalUnseen?: number })`
  (`web/components/sera/SeraNav.tsx:17`). **Optional with a default of `0`**, so any caller that
  does not pass it still compiles and renders today's rail.
- `badgeCount(n: number): number` — module-local, not exported (`SeraNav.tsx`).
- `BADGED = '/sera/journal'` — module-local const (`SeraNav.tsx`).
- `journalUnseen(): Promise<number>` — module-local, not exported (`web/app/sera/layout.tsx`).
- CSS class `.badge` in `web/components/sera/SeraNav.module.css` (module-scoped; it does **not**
  collide with `journal.module.css`'s `.badge` — CSS Modules hash per file).

**Signature changes:**
- `SeraNav()` -> `SeraNav({ journalUnseen }: { journalUnseen?: number })`. Sole call site is
  `web/app/sera/layout.tsx:13`, which this phase also edits. Verified by
  `grep -rn "SeraNav" web/` — `web/app/sera/layout.tsx` is the only one.
- `.tab, .active` in `SeraNav.module.css:27` gains `position: relative`.

**Requires (from earlier phases):**
- Phase 1: `web/lib/sera/seen.ts` exports
  `unseenCount(insightIds: Iterable<number>): Promise<number | null>` — the count of ids not in
  `journal_seen`, or `null` when the read failed. It never throws. See READ THIS FIRST.
- Phase 1: `db/migrations/012_journal_seen.sql` is applied wherever this runs. If it is not, the
  query fails, `unseenCount` returns `null`, and the rail shows **no badge** — the correct
  reading of "I cannot tell you".

**Leaves alone (owned by others):**
- `web/app/sera/journal/*` — **every file**: `page.tsx`, `journal.module.css`, `view.ts`,
  `view.test.ts`, `JournalSeen.tsx`, `seen-client.ts`, `seen-client.test.ts` (phases 2, 3, 4).
  This phase only *mentions* them, in the readme.
- `web/lib/sera/seen.ts`, `web/app/api/sera/journal/seen/route.ts`, `db/migrations/` (phase 1).
- `web/app/(app)/**`, `web/components/Nav.tsx`, `web/app/globals.css`,
  `web/app/sera/sera.module.css` — untouched.
- The other four rail tabs (`/sera`, `/sera/methods`, `/sera/ideas`, `/sera/how`): unchanged
  href, icon, tip, `aria-label`, `aria-current`, class. Only the Journal tab gains anything.

## Files

| File | Action | What changes |
|---|---|---|
| `web/app/sera/layout.tsx` | modify | read the unseen total after the gate, pass it to `SeraNav`; never throw |
| `web/components/sera/SeraNav.tsx` | modify | optional `journalUnseen` prop; the Journal tab renders a badge when it is above zero |
| `web/components/sera/SeraNav.module.css` | modify | `position: relative` on the tab; a new `.badge` rule, an inverted variant on the active tab, and a smaller size in the top-bar breakpoint |
| `web/package_readme.md` | modify | 11 quoted edits: Overview, Key Responsibilities, Layout tree (x5), Exported API (x2), Data Flow, Sera section, Dependencies, Concurrency, Configuration, Gotchas, Last Updated |

---

## Implementation Steps

### Step 1: The layout reads the unseen total

**File:** `web/app/sera/layout.tsx:1-19` (whole file replaced)

**Change:** Two new imports, a module-local `journalUnseen()` helper, one extra `await` after the
gate, and the count handed to `<SeraNav />`.

Ordering matters: `await requireSera()` **first**, then the count. The two are independent, so
`Promise.all` would be a touch faster — do not do it. `requireSera` is the gate; firing a Neon
query for a visitor who is about to get a `redirect` or a `notFound` leaks a database round trip
to an unauthenticated caller for no benefit on a page that is already dynamic.

`lab` is imported at module scope, as every other `/sera` server component already does
(`lib/sera/lab.ts:9`); the layout is a server component (`async function`, no `'use client'`),
so the 0.89 MB snapshot does not reach the browser.

**Code:**
```tsx
import type { Metadata } from 'next';
import { SeraNav } from '@/components/sera/SeraNav';
import { requireSera } from '@/lib/sera/gate';
import { lab } from '@/lib/sera/lab';
import { unseenCount } from '@/lib/sera/seen';
import s from './sera.module.css';

export const metadata: Metadata = { title: { default: 'Sera', template: '%s · Sera' } };

/**
 * Entries in the bundled snapshot the reader has not seen — the number on the rail's Journal
 * tab. 0 renders no badge at all, and so does a failed read.
 *
 * The ids come from `lab.insights`, never from journal_seen's row count and never as
 * `insights.length - seen.size`: a row may name an id that is not in this build's snapshot (the
 * table lives in Neon, the snapshot is bundled at build time), and the rail must agree with the
 * seven badges /sera/journal renders for itself. unseenCount only looks at the ids it is given,
 * so handing it lab.insights' ids is the derivation rule, enforced.
 *
 * unseenCount returns null when the read failed, which is why it is the function this layout
 * calls rather than seenInsightIds: an empty Set cannot say whether nothing is unseen or Neon is
 * down, and invariant 9 asks for no badge in the second case rather than a confident 26. The
 * try/catch is belt-and-braces -- unseenCount already swallows its own query failure -- because
 * this layout wraps every /sera page and a throw here takes the whole section down over a badge.
 */
async function journalUnseen(): Promise<number> {
  try {
    return (await unseenCount(lab.insights.map(i => i.id))) ?? 0;
  } catch {
    return 0;
  }
}

/** Sera, the method lab: gated to SERA_EMAIL (invariant 3), desktop shell with its own rail. */
export default async function SeraLayout({ children }: { children: React.ReactNode }) {
  await requireSera();
  const unseen = await journalUnseen();
  return (
    <div className={s.shell}>
      <SeraNav journalUnseen={unseen} />
      <main className={s.main}>
        <div className={s.column}>{children}</div>
      </main>
    </div>
  );
}
```

**Invariant 9 is fully reachable here, and the `?? 0` is the whole trick.** `unseenCount` returns
`null` on a failed read and a number on a good one, so the three outcomes are distinct:

| `unseenCount(...)` | rail | meaning |
|---|---|---|
| `0` | no badge | everything has been seen |
| `n > 0` | badge `n` | `n` entries are new |
| `null` | no badge | the read failed — the rail says nothing rather than something it cannot stand behind |

A Neon outage therefore shows **no rail badge**, not a confident "26". Note that `/sera/journal`
itself degrades differently in the same outage — phase 3 reads through `seenInsightIds`, which
resolves to an empty set, so the page renders every entry as unseen. That divergence is
deliberate and is the right call on both sides: the page is rendering the entries regardless and
"everything is new to you" is the safe reading for a list; the rail is a bare notification
number, and a wrong notification number is worse than none. R3's "a new number is a real signal"
is exactly the property that makes silence the right failure mode for the rail.

**Impact:** One extra Neon round trip on every `/sera/*` page load, behind the gate. `/sera`
pages are already dynamic (`requireSera()` reads cookies via `auth()`), so no caching behaviour
changes and no `export const dynamic` is needed here — the analysis establishes this at
"Caching", and the layout does not declare one today.

---

### Step 2: `SeraNav` renders the badge on the Journal tab

**File:** `web/components/sera/SeraNav.tsx:1-40` (whole file replaced)

**Change:** an optional `journalUnseen` prop, a `BADGED` constant naming the one tab that gets a
badge, a `badgeCount` guard, and a conditional `<span>` inside the Journal tab's `<Link>`.

Four things to notice in the code below:

1. **Zero renders nothing.** This is deliberate and differs from the Journal page's own seven
   badges, which keep a muted `.zero` pill (`journal.module.css:13`) so the row of seven stays
   visually even. One tab in a vertical rail has no row to stay even with, and a permanent grey
   `0` floating on a nav icon reads as clutter, not as a notification. No `.zero` variant is
   added to `SeraNav.module.css` at all.
2. **`badgeCount` guards the prop.** `journalUnseen` crosses a server→client boundary as plain
   JSON; a `NaN`, a negative, or a float must not reach the DOM. `Number.isFinite(n) && n > 0`
   first, then `Math.floor`.
3. **`99+` cap.** 26 insights today, growing by a handful per lab batch — but a reader who leaves
   it for months must not blow out a 52px tab. The cap is on the *text*, not on the count.
4. **The tip and the label are two strings.** `data-tip` uses the `·` separator the Journal page
   already uses for its badge tooltips (`page.tsx:40`), `aria-label` uses a comma so a screen
   reader says "Journal, 4 new" and not "Journal dot 4 new". The other four tabs keep the single
   string they have today, because `label === tip` for them.

**Code:**
```tsx
'use client';

import { Eye, FlaskConical, LayoutDashboard, Lightbulb, NotebookPen, Workflow } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import s from './SeraNav.module.css';

const TABS = [
  { href: '/sera', icon: LayoutDashboard, tip: 'Overview' },
  { href: '/sera/methods', icon: FlaskConical, tip: 'Methods' },
  { href: '/sera/journal', icon: NotebookPen, tip: 'Journal' },
  { href: '/sera/ideas', icon: Lightbulb, tip: 'Ideas' },
  { href: '/sera/how', icon: Workflow, tip: 'How it works' },
];

/** The one tab that carries an unseen badge. The other four count nothing. */
const BADGED = '/sera/journal';

/** A count fit to print: a whole number above zero, or 0, which renders no badge at all. */
const badgeCount = (n: number): number => (Number.isFinite(n) && n > 0 ? Math.floor(n) : 0);

/**
 * Sera's rail: wordmark, five icon-only section tabs, and a way back to Seer. A top bar below 1024 px.
 *
 * `journalUnseen` is the number of journal entries not yet seen, read server-side in
 * app/sera/layout.tsx. It exists so a new entry is visible from the other Sera pages, not only
 * from /sera/journal, where the seven badges already say it. Zero (or absent) means no badge —
 * unlike the Journal's own badges, which keep a muted zero pill to keep the row of seven even.
 */
export function SeraNav({ journalUnseen = 0 }: { journalUnseen?: number }) {
  const path = usePathname() ?? '';
  return (
    <aside className={s.rail}>
      <span className={s.wordmark}>
        Sera<span className={s.dot}>.</span>
      </span>
      <nav className={s.tabs} aria-label="Sera sections">
        {TABS.map(({ href, icon: Icon, tip }) => {
          const active = href === '/sera' ? path === '/sera' : path === href || path.startsWith(`${href}/`);
          const n = href === BADGED ? badgeCount(journalUnseen) : 0;
          return (
            <Link key={href} href={href} className={active ? s.active : s.tab}
              data-tip={n > 0 ? `${tip} · ${n} new` : tip}
              aria-label={n > 0 ? `${tip}, ${n} new` : tip}
              aria-current={active ? 'page' : undefined}>
              <Icon size={22} strokeWidth={active ? 1.75 : 1.5} />
              {n > 0 && <span className={s.badge} aria-hidden="true">{n > 99 ? '99+' : n}</span>}
            </Link>
          );
        })}
      </nav>
      <Link href="/" className={`icon-btn ${s.back}`} data-tip="Back to Seer" aria-label="Back to Seer">
        <Eye size={21} strokeWidth={1.5} />
      </Link>
    </aside>
  );
}
```

**Impact:** The component's only call site is the layout from Step 1. The prop is optional, so
the two steps are independently compilable in either order. `data-tip` keeps working unchanged —
tooltips are a delegated layer keyed on the attribute (`components/TooltipLayer.tsx`,
`components/tooltip.ts`), not a per-component thing.

---

### Step 3: The rail badge style

**File:** `web/components/sera/SeraNav.module.css:27-37` (one declaration added) and `:43`
(new block inserted after `.back`), `:56-58` (one rule added inside the existing media query)

**Change 3a — the tab becomes a positioning context.** Add `position: relative` as the first
declaration of the existing `.tab, .active` rule. Do not add a second `.tab, .active { }` block;
keep the file's one-rule-per-selector shape.

Before (`SeraNav.module.css:27-37`):
```css
.tab, .active {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 52px;
  min-width: 52px;
  border-radius: 999px;
  -webkit-tap-highlight-color: transparent;
  user-select: none;
  transition: background 0.12s;
}
```

After:
```css
.tab, .active {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 52px;
  min-width: 52px;
  border-radius: 999px;
  -webkit-tap-highlight-color: transparent;
  user-select: none;
  transition: background 0.12s;
}
```

**Change 3b — the badge.** Insert this block immediately after `.back { margin-top: auto; }`
(`SeraNav.module.css:43`), before the `@media (max-width: 1023.98px)` block.

The geometry, since the scope asks for it to be checked rather than guessed. The rail tab is a
52px circle (centre 26,26, r 26). A 20px pill at `top: -2px; right: -2px` has its centre at
(40, 8); that is 24.1px from the circle's centre, i.e. sitting **on** the rim — the same reading
as `journal.module.css`'s 20px pill at `-4px` on a 46px circle (centre 24.1px out on a 23px
radius). Same pill, same place, different button size. The 2px ring in `--bar` separates it from
the tab pill's own background. The `.tabs` container has 8px of padding and no `overflow: hidden`,
so the badge plus its ring (reaching 4px past the tab) never clips and never touches the pill's
edge.

```css
/* Unseen journal entries. A sibling of the Journal page's own badge
   (app/sera/journal/journal.module.css .badge): same coral pill, same tabular numerals,
   sized for the rail's 52 px tab and ringed so it reads off the tab strip. There is no
   `.zero` variant on purpose — a zero count renders no badge at all (SeraNav.tsx). */
.badge {
  position: absolute;
  top: -2px;
  right: -2px;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 999px;
  background: var(--coral);
  color: var(--on-coral);
  box-shadow: 0 0 0 2px var(--bar);
  font-size: 11.5px;
  line-height: 20px;
  text-align: center;
  font-variant-numeric: tabular-nums;
  pointer-events: none;
}
/* On the active tab the button is already --coral: invert, or the badge disappears into it. */
.active .badge {
  background: var(--on-coral);
  color: var(--coral);
  box-shadow: 0 0 0 2px var(--coral);
}
```

**Change 3c — the top bar, below 1024px.** The tabs become a 44px row inside a 5px-padded pill
(`SeraNav.module.css:56-57`). Add one rule at the end of that media query, after
`.back { margin-top: 0; margin-left: auto; }`.

Before (`SeraNav.module.css:45-59`):
```css
/* Below 1024 px: a top bar, not designed further (plan: desktop only for now). */
@media (max-width: 1023.98px) {
  .rail {
    z-index: 40;
    width: 100%;
    height: auto;
    flex-direction: row;
    padding: calc(10px + var(--safe-top)) 16px 10px;
    gap: 16px;
    background: var(--bg);
  }
  .tabs { flex-direction: row; padding: 5px; }
  .tab, .active { height: 44px; min-width: 44px; }
  .back { margin-top: 0; margin-left: auto; }
}
```

After:
```css
/* Below 1024 px: a top bar, not designed further (plan: desktop only for now). */
@media (max-width: 1023.98px) {
  .rail {
    z-index: 40;
    width: 100%;
    height: auto;
    flex-direction: row;
    padding: calc(10px + var(--safe-top)) 16px 10px;
    gap: 16px;
    background: var(--bg);
  }
  .tabs { flex-direction: row; padding: 5px; }
  .tab, .active { height: 44px; min-width: 44px; }
  .back { margin-top: 0; margin-left: auto; }
  /* 44 px tab: a smaller pill, nudged out to sit on the rim rather than over the icon. */
  .badge {
    top: -3px;
    right: -3px;
    min-width: 18px;
    height: 18px;
    padding: 0 5px;
    font-size: 11px;
    line-height: 18px;
  }
}
```

Geometry check for the top bar: 44px circle (centre 22,22, r 22); an 18px pill at `-3px` has its
centre at (32, 6), 19.7px out — on the rim, same reading. Journal is the third of five tabs, so
horizontally it sits in the middle of the row where the pill's top edge is a straight line; the
badge plus ring reaches 5px above the tab, exactly the container's 5px padding, so it grazes the
strip's top edge and is never clipped (`.tabs` sets no `overflow`).

**Impact:** CSS Modules hash class names per file, so this `.badge` and `journal.module.css`'s
`.badge` cannot collide even though both are on screen at once on `/sera/journal`. Nothing else
in the file changes; the other four tabs render byte-identically.

---

### Step 4: `web/package_readme.md` — eleven quoted edits

The readme is 470 lines and no other phase in this set touches it, so every edit below is given
as an exact before/after. **Apply them in file order.** Line numbers are as the file stands at
base `46c04b4`; re-grep rather than trusting them if anything has shifted.

Three of the edits (4d, 4f, 4h) name files phases 2–4 own. The reconciler has pinned those
phases' exports, so the wording below is written against the real contracts rather than a guess.
**Still read those files in the worktree before writing their one-line descriptions** — the code
is the final word, and if it disagrees, fix the readme to match the code.

---

#### Edit 4a — Overview: the "not from Neon" sentence (`package_readme.md:11-14`)

This is the sentence the analysis singles out. Two things are wrong by omission: the write count
and the blanket "not from Neon".

**Before:**
```
`book_targets`, `book_trades`, `equity_snapshots`, `paper_state`, `bars` and `fx_rates`, plus one
write (`action_dismissals`). A second, separate section, **Sera** (`/sera`), shows the method lab
from a committed JSON snapshot (`data/lab.json`), not from Neon.
```

**After:**
```
`book_targets`, `book_trades`, `equity_snapshots`, `paper_state`, `bars` and `fx_rates`, plus two
writes (`action_dismissals` and `journal_seen`). A second, separate section, **Sera** (`/sera`),
shows the method lab from a committed JSON snapshot (`data/lab.json`): every lab *fact* — methods,
trials, insights — comes from the snapshot and none of it from Neon. The one thing Sera keeps in
Postgres is reader state: which Journal entries have been seen (`journal_seen`), so the badges on
the Journal's tabs count what is new instead of what exists.
```

---

#### Edit 4b — Key Responsibilities, the Sera bullet (`package_readme.md:22`)

A long single-line bullet. Match on its tail and append one sentence.

**Before** (the tail of the bullet):
```
Pages: Overview, Methods list + detail, Journal, Ideas, How it works; each page keeps its logic in a pure, tested `view.ts` (`overview.ts` for the Overview). See [Sera](#sera-sera)
```

**After:**
```
Pages: Overview, Methods list + detail, Journal, Ideas, How it works; each page keeps its logic in a pure, tested `view.ts` (`overview.ts` for the Overview). The Journal is the one Sera page that also touches Neon, for reader state only: `lib/sera/seen.ts` over `journal_seen` decides which entries are unseen, which orders them and fills the badges. See [Sera](#sera-sera)
```

---

#### Edit 4c — Layout tree: the API route (`package_readme.md:36`)

**Before:**
```
    api/auth/               NextAuth route handlers
```

**After:**
```
    api/auth/               NextAuth route handlers
    api/sera/journal/seen/  route.ts: POST {ids, via} marks Journal insight ids seen; requireSera's gate answered as 204 / 400 / 404 (beacon target, not a navigation)
```

---

#### Edit 4d — Layout tree: the Sera layout and journal page (`package_readme.md:52` and `:60`)

Two separate replacements inside the `sera/` block.

**Before (`:52`):**
```
      layout.tsx            requireSera(), then SeraNav rail + centred column (max 1360px); stacks below 1024px
```

**After:**
```
      layout.tsx            requireSera(), the Journal's unseen total, then SeraNav rail + centred column (max 1360px); stacks below 1024px
```

**Before (`:60`):**
```
      journal/page.tsx      /sera/journal insights grouped by kind, ?kind= filter (view.ts + view.test.ts, journal.module.css)
```

**After** — *verify the three new lines against the files phases 3 and 4 actually shipped:*
```
      journal/page.tsx      /sera/journal insights grouped by kind, ?kind= filter; unseen first (newest first), then seen below a divider; badges count unseen (view.ts + view.test.ts, journal.module.css)
      journal/JournalSeen.tsx   (client) marks entries seen: dwell on screen in a visible tab, or a redirect-arrow click; batches ids, flushes on page-hide, counts the badges down live
      journal/seen-client.ts    pure dwell/batch policy and the pending-id queue, DOM-free (+ seen-client.test.ts)
```

---

#### Edit 4e — Layout tree: `lib/sera/seen.ts` (`package_readme.md:93`)

**Before:**
```
    sera/gate.ts            requireSera(next) (server only)
```

**After:**
```
    sera/gate.ts            requireSera(next) (server only)
    sera/seen.ts            seenInsightIds() / unseenCount(ids) / markInsightsSeen(ids, via): the journal_seen read/write; a failed read is an empty set for the page and null for the rail, never a throw (server only)
```

---

#### Edit 4f — Layout tree: the `SeraNav` line (`package_readme.md:70`)

**Before:**
```
      SeraNav.tsx           (client) icon-only rail: Overview, Methods, Journal, Ideas, How it works (/sera/*), Back to Seer
```

**After:**
```
      SeraNav.tsx           (client) icon-only rail: Overview, Methods, Journal, Ideas, How it works (/sera/*), Back to Seer; the Journal tab carries an unseen-count badge (prop from app/sera/layout.tsx; no badge at zero)
```

---

#### Edit 4g — Exported API, "Other modules": the `journalGroups` bullet (`package_readme.md:331`)

> The reconciler has pinned phase 2's exports, so the wording below is final, not a template:
> `view.ts` exports `SEEN_COPY`, `unseenCounts(insights, seen?)`, `badgeTip(heading, unseen,
> total)`, `journalGroups(insights, filter, seen?)` and a `JournalGroup` carrying
> `entries` / `items` / `unseen` / `seen` / `unseenCount`. Still open the file and check before
> you write the line.

**Before:**
```
- `app/sera/journal/view.ts` (pure): `KIND_COPY` (caption, empty text, sheet tone per insight kind), `parseKind(?kind)` (unknown -> `'all'`), `journalHref`, `newestFirst` (by `added`, then higher id), `kindCounts`, `journalGroups(insights, filter)` (one group per kind in `INSIGHT_KINDS` order), `dayLabel` (UTC).
```

**After:**
```
- `app/sera/journal/view.ts` (pure): `KIND_COPY` (caption, empty text, sheet tone per insight kind), `SEEN_COPY` (the unseen/seen divider label, the card marker and its screen-reader text), `parseKind(?kind)` (unknown -> `'all'`), `journalHref`, `newestFirst` (by `added`, then higher id), `kindCounts` (how many of each kind exist in all), `unseenCounts(insights, seen?)` (how many of each kind are unseen, keyed by all seven tabs so `.all` is the total; a seen id not in the snapshot is ignored), `badgeTip(heading, unseen, total)` (the one formatter for the seven tab tooltips — the server render and the client island both call it, so the wording cannot fork), `journalGroups(insights, filter, seen?)` (one group per kind in `INSIGHT_KINDS` order; inside each, unseen entries newest-first, then seen entries newest-first, carried on the group as `unseen` / `seen` / `items` / `unseenCount` alongside the flat `entries` — the seen set defaults to empty, which is "nothing seen yet"), `dayLabel` (UTC). Takes a `ReadonlySet<number>`; never imports `lib/sera/seen.ts` or the database, which is what lets the client island import `badgeTip` from it.
```

---

#### Edit 4h — Exported API, "Other modules": two new bullets (`package_readme.md:331`, after 4g's line)

> `seen-client.ts`'s exported names are phase 4's call. Read the file; substitute.

**Insert immediately after the `app/sera/journal/view.ts` bullet:**
```
- `lib/sera/seen.ts` (server only; every reader queries Neon): `seenInsightIds()` -> every `insight_id` in `journal_seen` as a `Set<number>`; a failed query resolves to an empty set and logs, never throws, so `/sera/journal` degrades to "nothing seen yet" rather than 500 (invariant 9). `unseenCount(ids)` -> how many of `ids` are *not* in the table, or `null` when the read failed — the rail's number, and the one reader that can tell a failure from a clean zero, which is why `app/sera/layout.tsx` shows no badge on `null`. It takes the ids rather than reading the snapshot itself, so the API route's bundle never pulls `data/lab.json`. `markInsightsSeen(ids, via)` -> one multi-row `INSERT … ON CONFLICT DO NOTHING` (`via` is `'view'` or `'click'`), returning how many rows were new; idempotent, so posting the same id twice leaves one row. `normalizeSeenIds` / `parseSeenVia` are the shared input guard the POST route uses, and `MAX_SEEN_BATCH` (500) is the per-request id cap it enforces.
- `app/sera/journal/seen-client.ts` (pure, DOM-free): the dwell/batch constants in one place (on-screen fraction, tall-card pixel fallback, dwell ms, idle debounce, max batch) and the pending-id queue (add, peek, take a batch, remember what is already marked so an id is never posted twice in a session), plus the arithmetic deciding whether an `IntersectionObserver` entry counts as on screen. Unit-tested without a browser (`seen-client.test.ts`).
```

---

#### Edit 4i — Data Flow (`package_readme.md:342-347`)

**Before:**
```
engine (Python, nightly) -> Neon tables -> lib/data.ts (SQL, row -> view model)
                                              |-> pure lib/* (metrics, monthly, strategy, slots, format)
                                              -> server components in app/(app)/* -> HTML
engine `lab stage` -> web/data/lab.json (committed) -> lib/sera/lab.ts -> pure lib/sera/derive.ts -> /sera server components
user "Mark as done" -> actions.dismiss -> data.dismissAction -> action_dismissals
```

**After:**
```
engine (Python, nightly) -> Neon tables -> lib/data.ts (SQL, row -> view model)
                                              |-> pure lib/* (metrics, monthly, strategy, slots, format)
                                              -> server components in app/(app)/* -> HTML
engine `lab stage` -> web/data/lab.json (committed) -> lib/sera/lab.ts -> pure lib/sera/derive.ts -> /sera server components
user "Mark as done" -> actions.dismiss -> data.dismissAction -> action_dismissals
reader reads /sera/journal -> JournalSeen (dwell on screen, or arrow click) -> POST /api/sera/journal/seen -> sera/seen.markInsightsSeen -> journal_seen
journal_seen -> sera/seen.seenInsightIds -> journal/view.ts (unseen counts, unseen-then-seen order) -> the seven badges
             -> sera/seen.unseenCount(lab ids) -> app/sera/layout.tsx -> the SeraNav Journal badge (null = no badge)
```

---

#### Edit 4j — Sera section: the Journal route row, and a new subsection

**Before (the Routes table's journal row, `package_readme.md:371`):**
```
| `/sera/journal` | insights grouped as Batch summaries (synthesis), What we learned, Ideas worth testing, Data we wish we had, Features to build, Risks we see; `?kind=<kind>` filter (e.g. `/sera/journal?kind=data-wish`), newest first |
```

**After:**
```
| `/sera/journal` | insights grouped as Batch summaries (synthesis), What we learned, Ideas worth testing, Data we wish we had, Features to build, Risks we see; `?kind=<kind>` filter (e.g. `/sera/journal?kind=data-wish`). Inside each group, unseen entries come first newest-first, then the seen ones below a divider; each of the seven tab badges counts that tab's unseen entries. See [What the reader has seen](#what-the-reader-has-seen-journal_seen) |
```

**Then insert this whole subsection after the "Data source and how it stays current" subsection**
— that is, after the paragraph ending `...written in plain language with a closing `My opinion:`.`
and immediately before `## Dependencies`:

```
### What the reader has seen (journal_seen)

Lab facts are read-only and come from the snapshot. The single exception in all of Sera is
**reader** state: which Journal entries have been looked at. It lives in Neon, in `journal_seen`
(`db/migrations/012_journal_seen.sql`), modelled on `action_dismissals`: `insight_id bigint`
primary key, `seen_at`, and a `via` column saying how it was marked (`'view'` or `'click'`). No
user column — Seer is one account — and no foreign key: insights live in the engine's SQLite lab
store, not in Postgres, and their ids are append-only and never reused, so there is nothing to
cascade from.

- **Marked by.** A redirect-arrow click (`via: 'click'`), or the entry dwelling on screen in a
  visible tab for long enough to have been read past (`via: 'view'`) — the five insights with no
  `methodId` carry no arrow, so dwell is the only rule that reaches them. A background tab marks
  nothing. `app/sera/journal/JournalSeen.tsx` observes, `seen-client.ts` holds the policy and the
  queue, and ids are batched and flushed to `POST /api/sera/journal/seen` on an idle debounce, at
  the batch cap, and on page-hide via `navigator.sendBeacon`.
- **Additive and idempotent.** Nothing ever deletes a row or marks an entry unseen; posting an id
  twice is a no-op. There is no "mark all as read" control by design.
- **Counted off the snapshot, not off the table.** Unseen is always `lab.insights` minus the seen
  set — never `count(*)`, never `insights.length - seen.size`. A row may name an id that is not
  in the build's `data/lab.json`, and it must not move a badge.
- **Frozen per page view.** The unseen/seen partition is computed once on the server from the set
  as it stood when the page was requested. Marking an entry seen during a visit changes the
  badges and the card's marker; it never moves a card out from under the reader.
- **Degrades, and the two surfaces degrade differently on purpose.** Nothing ever 500s because
  Postgres is unreachable. `/sera/journal` reads `seenInsightIds()`, whose failed query resolves
  to an empty set: every entry unseen, the page still renders the list. The rail reads
  `unseenCount()`, which returns `null` on a failed read and so shows **no badge** — a bare
  notification number that is wrong is worse than none, while "everything is new to you" is the
  safe reading for a list you are already looking at.
- **The rail.** `app/sera/layout.tsx` calls `unseenCount(lab.insights.map(i => i.id))` and passes
  the result to `SeraNav`, so the Journal tab carries a badge on every `/sera/*` page. It is
  computed when the layout renders, so it is a per-load number, not a live one.
```

---

#### Edit 4k — Dependencies, Concurrency, Configuration, Gotchas

**Dependencies (`package_readme.md:419`). Before:**
```
- Internal: shares `db/migrations/*.sql` and `schema_migrations` with the engine; the engine owns writes to every table except `action_dismissals`.
```
**After:**
```
- Internal: shares `db/migrations/*.sql` and `schema_migrations` with the engine; the engine owns writes to every table except `action_dismissals` and `journal_seen` (`db/migrations/012_journal_seen.sql`), which only the web app writes.
```

**Concurrency (`package_readme.md:423-424`). Before:**
```
No shared mutable state. Each request runs its own parallel queries; the only write is an
idempotent `INSERT ... ON CONFLICT DO NOTHING`. Not a concern beyond that.
```
**After:**
```
No shared mutable state. Each request runs its own parallel queries; both writes
(`action_dismissals`, `journal_seen`) are idempotent `INSERT ... ON CONFLICT DO NOTHING`, so a
retried beacon or two tabs flushing the same ids cost nothing. Not a concern beyond that.
```

**Configuration — the Sera env-var bullet (`package_readme.md:434`). Before:**
```
- Sera needs no env var: `SERA_EMAIL` is a constant (`lib/sera/access.ts`), and its data is the committed `data/lab.json`. Regenerate the JSON with `python -m seer_engine lab stage` (writes and stages it with `lab/lab.sqlite`) or `lab export-json` (writes only). In a worktree, run them as `env -u SEER_LAB_DB PYTHONPATH=<worktree>/engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine …`.
```
**After:**
```
- Sera needs no env var of its own: `SERA_EMAIL` is a constant (`lib/sera/access.ts`), and its lab data is the committed `data/lab.json`. It does share the app's `DATABASE_URL`, for `journal_seen` only. Regenerate the JSON with `python -m seer_engine lab stage` (writes and stages it with `lab/lab.sqlite`) or `lab export-json` (writes only). In a worktree, run them as `env -u SEER_LAB_DB PYTHONPATH=<worktree>/engine/src /home/miftah/seer/engine/.venv/bin/python -m seer_engine …`.
```

**Configuration — the `npm test` bullet (`package_readme.md:438`). Before** (its tail):
```
`app/(app)/leaderboard/view` and the `app/sera/*/view` helpers.
```
**After:**
```
`app/(app)/leaderboard/view`, the `app/sera/*/view` helpers and `app/sera/journal/seen-client`.
```

**Gotchas — three new bullets.** Insert them after the existing Sera run of bullets, immediately
after:
```
- Every `SeraNav` destination now has a page (`/sera`, `/sera/methods`, `/sera/journal`, `/sera/ideas`, `/sera/how`); each page also calls `requireSera(<its path>)` so sign-in returns to it.
```
**Insert:**
```
- `/sera/journal` and `app/sera/layout.tsx` are the only Sera code that reads Neon, and only for `journal_seen`. Neither may throw: the layout wraps every `/sera` page, so a thrown seen-state read takes down the whole section over a badge. The page uses `seenInsightIds()`, which swallows its query failure and degrades to "nothing seen yet"; the layout uses `unseenCount()`, which returns `null` on failure so the rail shows no badge rather than the full inventory. Use `unseenCount` for anything that is just a number — an empty `Set` cannot tell you the read failed.
- Unseen is always `lab.insights` minus the seen set. Never `SELECT count(*) FROM journal_seen` and never `insights.length - seen.size`: a row can name an id that is not in this build's snapshot (the table is in Neon, the snapshot is bundled at build time), and the rail's badge must agree with the seven on the page.
- The rail's Journal badge is computed when the Sera layout renders. A soft client-side navigation inside `/sera` does not re-run the layout, so the rail number does not refresh mid-visit — the Journal page's own seven badges are the live ones, counted down by `JournalSeen`. A zero count renders no rail badge at all, while the Journal's seven keep a muted zero pill to keep the row even.
```

---

#### Edit 4l — the "Last Updated" line (`package_readme.md:4`)

Last, so the summary describes what actually landed. The existing style is
`**Last Updated**: <date> (<phase id>, <slug>: <one-line summary>; <module>)`.

> **Phase id.** The plan index's TaskID column is `—` for every phase of this set. Use the card's
> TaskID if one was minted by the time this lands; otherwise `P5-WEB-J4N8`, taking the suffix
> from the analysis session id `20261007-103957-J4N8`, which is how the rest of this tree names
> an un-carded phase.

**Before:**
```
**Last Updated**: 2026-10-07 (P1-WEB-10T8, paper-split-cadence: Positions speaks "picks monthly, sizes weekly" for split-cadence book strategies and shows each order against what is held now; `lib/cadence.ts`)
```

**After:**
```
**Last Updated**: 2026-10-07 (P5-WEB-J4N8, journal-unseen-badges: the Journal's badges count entries the reader has not seen, unseen entries sort above seen ones, and the Sera rail's Journal tab carries the unseen total; `lib/sera/seen.ts`, `journal_seen`)
```

**Impact:** documentation only; no code behaviour changes.

---

## Verification

The worktree's `web/node_modules` is already a symlink to `/home/miftah/seer/web/node_modules`
(`package.json` and `package-lock.json` are byte-identical to the base commit), and
`npx tsc --noEmit` is confirmed clean on the base tree. **Do not run `npm ci` or `npm install`.**

**Build:**
```
cd /home/miftah/.worktrees/seer/journal-unseen-badges/web && npx tsc --noEmit
```

**Tests:**
```
cd /home/miftah/.worktrees/seer/journal-unseen-badges/web && npm test
```
There is no existing test over `SeraNav` or `app/sera/layout.tsx` (confirmed: `grep -rn "SeraNav" web/` finds only
`SeraNav.tsx`, `layout.tsx` and docs). This phase adds none — a snapshot test over a five-link
rail would assert the markup, not the behaviour, and the badge's only logic (`badgeCount`) is
three terms. `npm test` must stay green because phases 2 and 4 own the suites that cover this
set's logic.

**Production compile** (the layout's new server-only imports are the thing worth proving):
```
cd /home/miftah/.worktrees/seer/journal-unseen-badges/web && npx next build
```
Watch for "You're importing a component that needs …" — `lib/sera/lab.ts` and `lib/sera/seen.ts`
must stay on the server side of the boundary. They will: `layout.tsx` has no `'use client'`, and
only a `number` crosses into `SeraNav`.

**Manual check** (`npm run dev`, signed in as `SERA_EMAIL`):
1. With `journal_seen` empty, open `/sera`. The rail's Journal tab shows a coral `26` (today's
   snapshot size). Hover it: "Journal · 26 new".
2. Click through to `/sera/journal`. The tab is now active (coral), and the badge inverts to
   `--on-coral` on `--coral` — still legible, not swallowed by the button.
3. Insert a couple of rows by hand
   (`INSERT INTO journal_seen (insight_id, via) VALUES (1,'view'),(2,'view');`), reload `/sera`.
   The rail reads `24`, and it matches the `all` badge on `/sera/journal` exactly.
4. `INSERT INTO journal_seen (insight_id, via) VALUES (99999,'view');` — a row for an id that is
   not in the snapshot. Reload. The number does **not** move. (This is the row-count trap.)
5. Mark every id seen. The rail badge disappears entirely; the Journal's own seven keep their
   muted `0` pills.
6. Narrow the window below 1024px. The rail becomes the top bar; the badge shrinks to 18px, still
   on the Journal icon's rim, not clipped by the tab strip and not overlapping its neighbours.
   Check both at ~1023px and at ~380px.
7. Toggle the OS to light mode and back: the badge's ring is `var(--bar)`, which flips with the
   theme (`globals.css:33` / `:77`), so it keeps separating the pill from the strip in both.
8. Point `DATABASE_URL` at an unreachable host and load `/sera`. The page renders, nothing 500s,
   and **the rail shows no badge at all** — `unseenCount` returned `null`. (`/sera/journal` in
   the same state shows every entry as unseen; that divergence is deliberate, see Step 1.)

**Exit criteria:**
- The rail's Journal tab shows the unseen total on every `/sera/*` page, and no badge at zero.
- A failed seen-state read shows **no badge**, not the full inventory — invariant 9, reached via
  `unseenCount`'s `null`.
- That number is identical to the `all` badge on `/sera/journal` whenever the read succeeds,
  including when `journal_seen` holds an id outside the snapshot.
- The rail renders correctly at ≥1024px and below 1024px, in light and dark.
- The other four rail tabs are byte-identical in rendered markup.
- `web/package_readme.md` no longer claims Sera never reads Neon, names both web writes, lists
  `lib/sera/seen.ts`, `app/api/sera/journal/seen/`, `app/sera/journal/JournalSeen.tsx`,
  `seen-client.ts` and `seen-client.test.ts` in the Layout tree, notes
  `db/migrations/012_journal_seen.sql`, and has a fresh "Last Updated" line.
- `npx tsc --noEmit && npm test` clean; `npx next build` compiles.

## Handoffs

- **Live rail countdown — deliberately not done.** The rail badge is server-computed per layout
  render, so it does not fall while `JournalSeen` marks entries on `/sera/journal`. Making it
  live would mean lifting the count into client state shared between the Journal island and the
  rail (a context, or a `router.refresh()` after each flush), which is R3 work owned by phase 4
  inside `/sera/journal`, and would put the layout's state in a client component for a number
  nobody is looking at while they are on the page it describes. Left out on purpose; if it is
  ever wanted, it belongs in a follow-up, not in this set.
- **`revalidatePath('/sera')` after a flush** would refresh the rail on the next navigation
  without client state. Phase 1 owns the POST route; this phase will not reach into it. Noted for
  whoever revisits the above.
- **Badges on the other four rail tabs** (Methods, Ideas) are out of scope by the plan index
  ("the Methods and Ideas pages keep the counts they have"). Not started.
- **`web/.workflows/todos.md`** is not touched here; the completion-handler / readme-updater flow
  owns it after the set lands.
- **Edits 4d, 4g and 4h describe files phases 2–4 own.** If their final exports differ from the
  wording above, fix the readme to match the code — never the code to match the readme.

### Phase 1 handoff — readme findings from the completion of P1-WEB-K3QM (2026-10-07)

Phase 1 shipped and its files were read against this plan's Step 4. Findings, for this phase to
act on. **Nothing in `package_readme.md` was edited** — it is this phase's deliverable.

- **All eleven line anchors in Step 4 are stale by 3-6 lines.** Every quoted *before* string
  still exists verbatim, but seek by grep, not by line number. Actual positions in the current
  470-line file: 4a `:12-14`, 4b `:21`, 4c `:41`, 4d `:52` and `:59`, 4e `:99`, 4f `:69`,
  4g `:334`, 4i `:343-347`, 4j `:374`, 4k `:418`/`:423`/`:435`/`:438`, gotcha anchor `:458`.
- **Edit 4c understates the route contract: it also returns 500.** A throw from
  `markInsightsSeen` is caught and answered `empty(500)`. "204 / 400 / 404" is incomplete.
- **Edit 4c's "requireSera's gate" is misleading.** The route deliberately does *not* call
  `requireSera` — it re-derives the rule from `isAllowed` + `isSeraUser`, because
  `requireSera`'s `redirect()`/`notFound()` are navigation responses and a 307 to `/signin`
  would disclose that the section exists (invariant 7). Reword.
- **Edit 4e's "never a throw" is wrong as a module-wide claim.** True for the two *reads*;
  `markInsightsSeen` throws by design, which is what the 500 above is made of.
- **Missing Gotchas bullet — the cap pairing.** `MAX_SEEN_BATCH = 500` (server) vs phase 4's
  `MAX_BATCH = 50` (client). They cannot share a constant: `lib/sera/seen.ts` is server-only and
  builds the Neon client at module scope. A client cap above 500 turns every full flush into a
  **silent** 400 — the route sends no body and the island swallows failures. Worth a bullet in
  edit 4k. (The 500 cap is enforced inside `normalizeSeenIds`, not by the route.)
- **The Sera gate paragraph (~`:380`) goes stale** and no edit touches it: it says
  `requireSera(next)` guards every `/sera/**` route, but there is now an `/api/sera/**` route
  that deliberately does not use it and answers 404 instead of redirecting.
- **Undocumented anywhere:** the route's `export const dynamic = 'force-dynamic'`, and its
  hand-rolled `JSON.parse(await req.text())` that ignores Content-Type because `sendBeacon`
  sends a Blob typed `text/plain`.
- **Edit 4j's `via` wording invites a wrong inference.** `via` is diagnostics-only; nothing reads
  it to decide seen-ness — a row existing is what "seen" means. Say so, or someone builds a
  filter on it later.

Verified accurate and needing no change: edit 4h (all three of `normalizeSeenIds`,
`parseSeenVia`, `MAX_SEEN_BATCH = 500`), and edit 4j's column description of
`db/migrations/012_journal_seen.sql`, which matches the shipped migration exactly.

There is no `db/package_readme.md` and none is needed: `db/` holds only `migrations/`, and
`engine/package_readme.md` documents only engine-owned migrations (001, 005, 008, 010 and 011
have no section there either). Web-owned `012` belongs in `web/package_readme.md`, where edits
4j and 4k already put it.

## Rollback

`git revert` this phase's commit. It touches four files, and nothing in the set depends on it:

- `app/sera/layout.tsx` returns to `await requireSera()` + `<SeraNav />`. The layout stops
  querying Neon entirely.
- `SeraNav` loses the prop (optional with a default, so even a half-revert compiles) and the
  Journal tab loses its badge. The other four tabs never changed.
- `SeraNav.module.css` loses `.badge`, `.active .badge`, the media-query override, and
  `position: relative` on `.tab, .active`.
- The readme returns to its previous text. The schema, `lib/sera/seen.ts`, the API route and the
  Journal's own seven badges are untouched — phases 1–4 keep working and keep testing green.

No migration to undo, no data to clean up: this phase writes nothing.
