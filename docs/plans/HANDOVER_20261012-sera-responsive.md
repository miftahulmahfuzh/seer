# Handover — make Sera work on a phone

**Written:** 2026-10-12, by the session that landed `lab-brakes-and-gate` and then fixed
`lab gate`'s variant readers.
**For:** `/analyze` — a plan set that revamps the Sera UI so it is usable at phone widths.
**Base:** `main` @ `d5783df`. Tree clean, engine 4452 passed / 3 skipped, web 676 tests, `tsc` clean.

---

## 1. The ask, in the owner's words

> fully revamp xsmax UI to improve responsive UI/UX user experience

"xsmax" is the iPhone XS Max — **414 × 896 CSS px**. The repo's screenshot tool already defaults to
**390** (the narrower iPhone 12/13/14 class) and **1280**. Both widths are broken today; 414 is
merely less broken than 390. Treat **390 as the floor to hold** and 414 as the owner's own device,
and hold both.

## 2. The one framing fact — this is undone design, not a bug list

`components/sera/SeraNav.module.css` says it outright, in two comments that are the whole story:

```css
/* Same rail as Seer's Nav (Nav.module.css), always shown: Sera is desktop-first, not desktop-only. */
...
/* Below 1024 px: a top bar, not designed further (plan: desktop only for now). */
```

So Sera was **deliberately** shipped desktop-first with a placeholder narrow layout. Everything in
§3 follows from that one decision. Do not write the plan as "fix N overflow bugs" — write it as
"design the narrow layout that was deferred", and let the overflows be the acceptance test.

**This matters for scope.** `/sean` and the main `app/(app)` pages are a *different* nav
(`components/sean/SeanNav.tsx`, `Nav.module.css`) and were **not** measured for this handover. Do
not assume they share the problem or the fix. Measure before widening scope.

## 3. What is actually broken, measured 2026-10-12 on `main` @ `d5783df`

Method: `npm run dev:env`, then a throwaway Playwright script walking every element and reporting
any whose right edge passes the viewport. Figures are
`document.documentElement.scrollWidth - viewport`.

| route | @390 | @414 | the element responsible |
|---|---:|---:|---|
| `/sera` | 66px | 42px | the nav top bar |
| `/sera/journal` | 66px | 42px | the nav top bar |
| `/sera/gotrade` | 66px | 42px | the nav top bar |
| `/sera/how` | 66px | 42px | the nav top bar **plus** an inline SVG diagram at `min-width: 960px` |
| `/sera/ideas` | 86px | 62px | the nav, plus a non-wrapping idea row (`.group` 438px wide, `.groupHead` 402px, with a 44px icon button after it) |
| `/sera/methods` | **569px** | **545px** | `app/sera/methods/methods.module.css:12` — `.table { min-width: 1200px; table-layout: fixed }`, **no scroll wrapper at all** |
| `/sera/methods/[id]` | **539px** | **515px** | `app/sera/methods/[id]/*.module.css:34` — `.table { min-width: 1240px }` |

### 3a. The nav bar — one cause, every page

Below 1024px `.rail` becomes a flex **row** that does not wrap: wordmark + 7 tabs (44px each,
5px padding, 16px gaps) + a `.back` button pushed out with `margin-left: auto`. Its right edge
measures **456px** regardless of viewport, which is exactly the 66px at 390 and 42px at 414.

Fixing this one element clears four of the seven routes outright. It is the highest-value single
change in the set and probably belongs in its own early phase that the others build on.

### 3b. The two tables — and a live puzzle worth handing over unsolved

`/sera/methods` has a `min-width: 1200px` table with **no** `overflow-x` container. That one is
straightforward.

`/sera/methods/[id]` is the interesting one: it **already has** `.tableWrap { overflow-x: auto;
margin: 0 -6px }` at line 33, and the page still overflows. The numbers say the containment is
partial, not absent — the table's own right edge measures **1289px**, but the document only scrolls
to **929px**. Something is clipping some of it and not the rest.

**Do not guess at this one.** The usual cause is a flex/grid ancestor missing `min-width: 0`, and
`app/sera/sera.module.css` already sets `min-width: 0` on `.main`, so the real cause is somewhere
else and worth finding before touching anything. A phase that "adds overflow-x: auto" without
explaining the 929-vs-1289 gap has not understood the bug.

Also note `.main { padding: 0 40px 56px 12px }` in `sera.module.css` — 40px right against 12px
left. That asymmetry is a desktop-rail assumption and reads as a visual error once the rail is a
top bar.

## 4. The acceptance test already exists — use it, do not invent one

`npm run shoot` **fails the run on horizontal scroll at any width**, by design. From the
`run-the-web-app` skill:

> HTTP >= 400 · a redirect to `/signin` · any browser console or page error · **horizontal scroll
> at any width**. The last one is the one that earns its keep.

So the exit criterion for every phase is mechanical and needs no new tooling:

```bash
cd web && npm run dev:env &
npm run shoot -- --width 390 --width 414 --width 1280 \
  /sera /sera/journal /sera/methods /sera/methods/M0030 /sera/ideas /sera/how /sera/gotrade
```

Green means no page scrolls sideways at any of the three widths, in both themes. **Read the PNGs
too** — a green exit only means nothing threw, and "doesn't overflow" is not the same as "is good
on a phone", which is what the owner actually asked for.

Use the **`run-the-web-app`** skill for this; it signs in without a human and self-renews the
session. Never ask the owner to sign in.

## 5. Rules this plan set must hold

From `CLAUDE.md`, all load-bearing here:

- **Read `node_modules/next/dist/docs/` before writing web code.** This Next.js (16) and React 19
  are newer than your training data. `web/AGENTS.md` repeats it and `next dev` re-adds that block.
- **Every button is icon-only (Lucide) with an `aria-label` and a tooltip.** A responsive pass is
  exactly where someone is tempted to add a text button or drop a tooltip. Don't.
- **Follow the Seer v2 design** at `docs/design/Seer v2.dc.html` and avoid generic styling. A
  narrow layout that looks like Bootstrap is a failed phase even if it stops scrolling.
- **`web/` mirrors some engine constants** (drawdown bar, contribution schedule, fee minimums,
  resize band) and a test asserts they match. Layout work should not go near them; if a phase finds
  itself editing one, it has wandered.
- **Text the owner reads uses plain language** — no ids, digests or code. Relevant if any phase
  reflows or truncates copy.
- **`/sera` is read-only over the committed `web/data/lab.json`.** No phase needs the database, and
  none should write `lab/lab.sqlite`.

## 6. What is NOT in scope, and why it is worth saying

- **The lab, the engine, the method pages' numbers.** All current as of `d5783df`. The `N` chip bug
  (a method page could show `N = 126` beside a lab whose hurdle is 74) was found and fixed in that
  commit; don't re-open it.
- **`/sean` and `app/(app)`.** Different nav, not measured. See §2.
- **Making the tables *good* on a phone is a design question, not a CSS question.** A 1240px table
  of 15 columns inside a horizontal scroller is technically compliant and still miserable to read
  on a phone. The owner asked for "UI/UX user experience", so the plan should at least consider
  card-per-row at narrow widths rather than only wrapping the table in a scroller. Flag the cost;
  let him choose.

## 7. Suggested shape (the planner may overrule this)

The dependency structure is unusually clean, because one element causes most of it:

1. **The nav's narrow layout** — clears `/sera`, `/sera/journal`, `/sera/gotrade` and most of
   `/sera/how`. Everything else builds on the tree this leaves.
2. **The two tables** — `/sera/methods` and `/sera/methods/[id]`, including the 929-vs-1289
   diagnosis. Likely one phase, since they share the problem and probably the fix.
3. **`/sera/ideas` rows** and **`/sera/how`'s 960px SVG** — independent of each other and of (2).
4. **The shell**: `.main`'s asymmetric padding and whatever the rail change leaves behind.

Phases 2, 3 and 4 can run concurrently once 1 lands. **They all edit `web/`, and a swarm shares one
worktree and one git index** — so if this runs under `/analyze-orchestrator`, phases that touch the
same `.module.css` must be serialised, exactly as phases 1 and 2 of `lab-brakes-and-gate` were.

## 8. Reproducing the measurements

The diagnostic script was a throwaway and is **not** committed. To rebuild it: launch Playwright
with the session from `web/scripts/session.mjs` (`ensureState('http://localhost:3111')` returns
`{ state }`, which is a Playwright `storageState`), set the viewport, and walk
`document.querySelectorAll('*')` reporting any element whose `getBoundingClientRect().right`
exceeds the viewport width, with its computed `min-width`, `white-space` and `overflow-x`. Sorting
by document order puts the outermost offender first, which is the one worth fixing.

Two traps that cost this session time:

- The script must live **inside `web/`** — `playwright` resolves from `web/node_modules`, so a
  script in `/tmp` fails with `ERR_MODULE_NOT_FOUND`.
- `ensureState(base)` takes the base URL and returns `{ state, renewed, real }`. Calling it with no
  argument throws `Invalid URL` from deep inside `cookieFor`.

---

**Start here:**

    /analyze -f docs/plans/HANDOVER_20261012-sera-responsive.md
