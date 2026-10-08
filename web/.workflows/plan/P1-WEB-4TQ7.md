> Adopted from `GOTRADE_FEE_REBUILD_PLAN.md` phase 9. Source: `.workflows/plan/gotrade-fee-rebuild/phase-9.md`.
> Written and reconciled by /analyze — edit the source, not this copy.

# Phase 9: The blank panel says which of five things it means

**Plan set:** `GOTRADE_FEE_REBUILD_PLAN.md`
**Analysis:** `20261008-091321-H3M8_code_analyzer.md`
**Satisfies:** R5 — the blank pending-picks panel must say which of its five causes it is, and never read as a live instruction
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `web/lib`, `web/app/(app)`

---

## Goal

Positions and Today stop rendering one blank for five different situations. A pure, tested
classifier names which of them it is — paper is paused, paper never started, the nightly is late,
the last decision is spent, or nothing was due — and says when the next decision arrives **in WIB**,
derived from `nightly.yml`'s three cron slots rather than from a hard-coded hour. The expired
decision stays visible as a record, stripped of every field that reads like an order ticket, so the
morning of 2026-10-08 cannot repeat: the owner saw a blank page and read it as data loss while 80
`book_targets` rows and 4 orders sat untouched in the database.

## Interface Contract

**Creates:**
- `web/lib/decision.ts` — `PAPER_PAUSED`, `NIGHTLY_SLOTS_UTC`, `NIGHTLY_DAYS_UTC`, `publishDay`,
  `timing`, `pipelineState`, `panelState`, and the types `Timing`, `PipelineState`, `PanelState`.
- `web/lib/decision.test.ts`.
- `web/lib/session.ts`: `wibTime` (new export), `addDays` (was module-private, now exported).
- `web/app/(app)/positions/page.tsx`: `Standing`, `standingWords`, `SpentDecision`, `PausedNote`
  (all module-local).
- `web/app/(app)/page.tsx`: `alarmTitle`, `alarmSub`, `PausedNote` (all module-local).
- CSS classes `paused`/`pausedIcon`/`pausedText`/`pausedTitle`/`pausedSub`,
  `standing`/`standingHead`/`standingIcon`/`standingTitle`/`standingBody`/`standingNext`/`standingLate`,
  `spent`/`spentHead`/`spentChip`/`spentNote`/`spentList`/`spentRow`/`spentSym`/`spentGap`/`spentWeight`
  in `positions.module.css`; `waiting`/`waitingHead`/`waitingIcon`/`waitingTitle`/`waitingSub` and the
  `paused*` set in `today.module.css`.

**Deletes:** the local `const showOrders` (`positions/page.tsx:31`); the local
`const WIB_TIME` (`page.tsx:19`, replaced by `session.wibTime`).

**Renames:** none.

**Signature changes:** none. `noOrders(st, p, sheet)`, `emptyState(st)`, `paperWarning(...)`,
`picksMonthlySizesWeekly(...)`, `runStatus(...)`, `pendingOrders(...)` and `bookPreview(...)` all keep
their current signatures. `noOrders` is called with `sheet = null` from the new path, which it
already accepts.

**Requires (from earlier phases):** nothing. Phase 9 is in wave 1 and depends on no other phase.

**Leaves alone (owned by others):**
- `web/lib/sera/*`, `web/app/sera/*` — phase 2. Its `web/lib/sera/lab.test.ts` failure (1 failed /
  9 passed) is expected to persist until phase 2 lands; this phase does not chase it.
- `web/lib/sean/*` and `web/app/sean/*` — phase 10. **There is no shared directory at all**: phase 10
  measured that Sean lives at `web/app/sean/`, a *sibling* of `(app)`, not at `web/app/(app)/sean/`
  as this plan's draft and the index's draft both said. This phase owns `web/app/(app)/positions/`
  and `web/app/(app)/page.tsx`; nothing else under `web/app/(app)` is touched by either phase.
- `web/lib/format.ts` — **not touched by any phase.** Phase 10 routes negative cash through
  `signedUsd`, which already exists at `format.ts:8`; it is imported, not added. Recorded here
  because both phases are web phases and the reconciler checked it.
- `web/lib/data.ts` — read only. No query is changed. `RunStatus`, `Pending`, `PendingOrder`,
  `Strategy` are imported as they are.
- `web/components/*` — not touched. See Handoffs for why `PausedNote` is duplicated rather than
  shared.
- `.github/workflows/nightly.yml` — **read only**, and only by a test. Invariant 2 holds:
  `PAPER_PAUSED` stays `'true'` and this phase does not edit the file. Phase 12 owns its comment.
  **Four phases touch that file's pause switch and the reconciler checked all four are compatible:**
  this phase mirrors the value into `web/lib/decision.ts` and reads it back with
  `/^\s*PAPER_PAUSED: '(true|false)'/m`; **phase 11** reads the same line with `sed` from a workflow;
  **phase 12** rewrites only the *comment block above* it (`:46-69`); and **no phase edits the
  `PAPER_PAUSED:` line itself** (invariant 2). Phase 12's plan now carries an explicit constraint
  that the line's exact text and indentation are preserved, because this phase's regex and phase
  11's `sed` both key on them.
- `docs/runbooks/paper-trading.md:76` — the stale `cron 23:00 UTC Mon-Fri (06:00 WIB)` line is
  phase 12's to fix, not this phase's, even though it is the same mismatch.

## Files

| File | Action | What changes |
|---|---|---|
| `web/lib/session.ts` | modify | export `addDays` (:15); add `wibTime` and its formatter |
| `web/lib/decision.ts` | create | the classifier: `PAPER_PAUSED`, the cron slots, `timing`, `pipelineState`, `panelState` |
| `web/lib/decision.test.ts` | create | drift tests against `nightly.yml`, plus the 2026-10-08 morning |
| `web/lib/session.test.ts` | modify | `wibTime` and `addDays` cases; correct the stale "06:00 WIB nightly" comment at :17 |
| `web/app/(app)/positions/page.tsx` | modify | `showOrders` (:31) becomes a classified state; new `Standing`, `SpentDecision`, `PausedNote` |
| `web/app/(app)/positions/positions.module.css` | modify | the paused note, the standing panel, the spent record |
| `web/app/(app)/page.tsx` | modify | routine expiry stops rendering as a coral alarm (:80-94); `PausedNote` |
| `web/app/(app)/today.module.css` | modify | the `waiting` sheet and the paused note |

## Measured facts this plan rests on

Every number below has a command behind it. All were run in this worktree on 2026-10-08.

**1. The mechanism, confirmed by executing the site's own functions** (scratch script over
`web/lib/session.ts`'s exact source):

```
nextUsSession(2026-10-08T01:17:40Z) = 2026-10-08
isStale('2026-10-07', 2026-10-08T01:17:40Z) = true
```

so `showOrders = !!strat && !strat.isBenchmark && !run.stale` is **false**, `pendingOrders` and
`bookPreview` are never called, and the sections at `positions/page.tsx:118` and `:138` do not
render. There is no `stale` branch anywhere in that file.

**2. The data was never touched.** Live database, 2026-10-08:

```
$ python - <<'PY'   # DATABASE_URL_UNPOOLED from /home/miftah/seer/.env.local
... SELECT session_date, strategy_id, count(*) FROM book_targets GROUP BY 1,2 ...
PY
(2026-10-07, 'MOM-FR', 20)  (2026-10-07, 'MVW-FR', 20)
(2026-10-07, 'RAW-FR', 20)  (2026-10-07, 'RMW-FR', 20)      -> 80 rows
orders:  ('C', 2026-10-07, 'pending', 4)
paper_state (strategy_id, last_session, pending_session, pending_decision, kickoff_session):
  C       2026-10-06  2026-10-07  False  None
  MOM-FR  2026-10-06  2026-10-07  True   2026-10-07
  MVW-FR  2026-10-06  2026-10-07  True   2026-10-07
  RAW-FR  2026-10-06  2026-10-07  True   2026-10-07
  RMW-FR  2026-10-06  2026-10-07  True   2026-10-07
  SPY     2026-10-06  2026-10-07  False  None
```

`kickoff_session = 2026-10-07` on all four quant books confirms the scope's reading: 2026-10-07 was
not a rank session, it was the **kickoff**.

**3. The pause cannot be derived from the database — measured, not assumed.** The only candidate
signature is "the latest run succeeded and its paper step never ran". Live `runs`:

```
id session_date data_date   status   paper_status  finished_at
10  2026-10-07  2026-10-06  success  success       2026-10-07 13:30:28 UTC
 7  2026-10-06  2026-10-05  success  NULL          2026-10-06 13:23:09 UTC
 1  2026-10-05  2026-10-02  success  NULL          2026-10-03 06:23:28 UTC
```

It fails twice over. **Late:** paper has been paused since 2026-10-08 and the latest run still reads
`paper_status = 'success'`, so the signature says "not paused" today. **Ambiguous:** rows 7 and 1
carry exactly the signature for a different reason — paper had not started yet
(`strategies.paper_start = 2026-10-07` for every active entry). The pause is therefore **declared**,
not inferred. See Decisions, below.

**4. The cron slots, and the times the owner reads.** `.github/workflows/nightly.yml:15,18,19` are
`'17 6 * * 2-6'`, `'41 9 * * 2-6'`, `'41 12 * * 2-6'` — 06:17, 09:41 and 12:41 UTC on Tuesday
through Saturday. Formatted for Jakarta:

```
$ node -e "const f=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Jakarta',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
           for (const t of ['2026-10-08T06:17:00Z','2026-10-08T09:41:00Z','2026-10-08T12:41:00Z']) console.log(t, f.format(new Date(t)))"
2026-10-08T06:17:00Z 13:17
2026-10-08T09:41:00Z 16:41
2026-10-08T12:41:00Z 19:41
```

**5. The due-time derivation, executed over nine instants** (scratch script, the logic of
`decision.ts` below verbatim):

```
owner's morning 2026-10-08T01:17:40Z | target 2026-10-08 | pubDay 2026-10-08 | due Thu 13:17 WIB | late after 19:41 WIB | overdue=false
Thu 20:00 WIB   2026-10-08T13:00:00Z | target 2026-10-08 | pubDay 2026-10-08 | due Thu 13:17 WIB | late after 19:41 WIB | overdue=true
Fri 17:00 ET    2026-10-09T21:00:00Z | target 2026-10-12 | pubDay 2026-10-10 | due Sat 13:17 WIB
Sun 10:00 WIB   2026-10-11T03:00:00Z | target 2026-10-12 | pubDay 2026-10-10 | due Sat 13:17 WIB   <- a Sunday reads correctly
Mon 17:00 ET    2026-10-12T21:00:00Z | target 2026-10-13 | pubDay 2026-10-13 | due Tue 13:17 WIB | overdue=false
2026-11-09 (EST) 2026-11-09T22:00:00Z| target 2026-11-10 | pubDay 2026-11-10 | due Tue 13:17 WIB
```

The last row is the daylight-saving check: `nextUsSession` reads ET through `Intl`, so the target
still rolls at the 16:00 ET close after the US clocks change. **Monday evening is the case that kills
the naive rule** — "a slot has fired since the last good run" would call Monday 17:00 ET overdue,
because the last fired slot is Saturday's. Keying the window to `publishDay(target)` gets it right.

**6. `lucide-react` 1.50.0 exports `Clock` and `Pause`** (`grep -c "declare const Clock:"
node_modules/lucide-react/dist/lucide-react.d.ts` → 1; same for `Pause`). `PauseCircle` does **not**
exist in this version; `CirclePause` does.

**7. `vitest` 3.2.7 with no config file**, so the default environment is `node` and a test may
`readFileSync` the workflow. `web/tsconfig.json` has `"include": ["**/*.ts", ...]`, so the new test
is type-checked by `npx tsc --noEmit` too.

## Decisions settled here

**D9.1 — How does `PAPER_PAUSED` reach the page?** *By a mirrored constant in `web/lib/decision.ts`,
with a test that fails when it drifts from `.github/workflows/nightly.yml`.*

Derivation from the database is rejected on measured grounds (fact 3 above): it is both late and
ambiguous. An environment variable on Vercel is rejected because it is a second switch the owner
must remember to flip, with nothing to catch a disagreement. Making `nightly.yml` read a committed
file is rejected because this phase must not edit that file (phase 12 owns it, invariant 2 governs
its value).

What is left is a mirror — and a mirror is only safe if drift is a test failure. `decision.test.ts`
reads `nightly.yml`, parses `PAPER_PAUSED: '<bool>'`, and asserts the constant agrees. The workflow
stays the single source of truth; the constant is a compile-time copy of it; `npx vitest run` — which
is already a gate on every phase of this set (invariant 1) — is what keeps them equal. The same test
pins the three cron slots, which is the operative form of "derive the next-decision time from the
cron slots rather than hard-coding one".

**D9.2 — Do expired picks stay visible?** *Yes: visible, greyed, labelled `Expired`, and stripped of
every order-ticket field.*

Removing them is what caused the incident — the owner read a blank page as data loss. The rows are
also the only place he can see what the system decided that night. The constraint is honoured by
what is **not** rendered: no limit, no stop, no take-profit, no share count, no dollar size, no copy
button. A book row shows rank, ticker and its target share of the portfolio (a portfolio weight, not
an order); a bracket row shows rank and ticker only. The section's own copy says the session has
closed and that nothing in it is to be placed.

**D9.3 — How is "(a) holding, nothing was due" determined?** *From the engine's own recorded answer,
`paper_state.pending_decision`, never re-derived in TypeScript.*

State (a) depends on each strategy's **own** cadence — `RMW-FR` resizes on 2026-10-12 when the other
three have nothing — and the month and week boundaries the engine uses are **NYSE trading sessions**.
`web/lib/session.ts:2-3` says in its own header that it does not model holidays, and it is right not
to: a naive "first weekday of the month" is correct for 2026-11-02 only by luck (Nov 1 is a Sunday)
and wrong for January 2027, where Jan 1 is a holiday and the first session is Jan 4. `decide_book`
already writes the answer: on a session that is neither rank nor resize it returns `(None, False)`
and `paper/store.py:471` records `pending_session = <the coming session>` with
`pending_decision = false`. That pair is state (a), read, not computed. The page writes the cadence
*sentence* by calling the existing `noOrders()`, which already reuses `picksMonthlySizesWeekly`.

**D9.4 — Is "paused" a panel state or a page banner?** *A page banner, beside the panel state, not
instead of it.*

The pause explains why a strategy will stay spent; it is not itself what the strategy decided. Making
it a sixth value of `PanelState` would swallow the per-strategy fact. So `PAPER_PAUSED` renders one
note at the top of both pages, and the panel below still says `spent` / `holding` / `never` / `live`.
The one thing the pause does change in the panel is the "next run is due …" line, which is suppressed
while paused — because while paused the next run will **not** produce a decision, and saying it would
is exactly the kind of sentence this phase exists to delete.

**D9.6 — Does a retired strategy's pending decision read as live?** *No, and it is settled
generically rather than against one rebuild.* **Added by the reconciler, 2026-10-08**, from an edge
neither this phase nor phase 12 could see alone.

Phase 12 retires the six live entries and creates six successors. Measured against production:
80 `book_targets` rows and 4 `orders` dated 2026-10-07 belong to the entries it retires and still
carry `pending_decision = true`. They are **not** deleted (plan invariant 3 — settled history is
never rewritten, and they are the record of a decision that was made and never acted on). So a
retired entry can hold a pending row whose session has not closed, which is the one case where
`pendingSession >= target` and the panel must *still* not say `live`.

This phase is wave 1 and phase 12 is wave 4, so this phase cannot depend on it — and does not need
to. `panelState` takes a `retired` flag (defaulted `false`), read from `Strategy.status`, which
`web/lib/data.ts` already publishes and `positions/page.tsx` already uses. A retired entry is
`spent`, and `standingWords` says so in plain words. **That is correct today** — the roster has
retired entries already (`A`, `FND`, `RM-FR`, the whole-share F4/F1 pair) — so it is testable now,
and it stays correct for every future roster change rather than for phase 12's in particular.
Phase 12's own exit criteria verify it against the six entries it retires.

**D9.5 — When is late an alarm?** *Only after the last retry slot has fired and nothing new has
arrived.*

`now >= lateAfter(target)` where `lateAfter` is 12:41 UTC = 19:41 WIB on `publishDay(target)`. Before
that the state is `waiting`, which is calm and carries the due time. This is the whole of the owner's
complaint: at 08:17 WIB on 2026-10-08 the coral `TriangleAlert` read *"Data is from Oct 7. Do not
trade today."* when the run was not due for another five hours.

## Implementation Steps

### Step 1: `session.ts` gains a WIB clock and exports `addDays`
**File:** `web/lib/session.ts:1-39` (whole file)
**Change:** export `addDays` so the classifier can step the calendar, and add `wibTime` so both pages
stop defining their own Jakarta formatter. Nothing existing changes behaviour.
**Code:**

```ts
// US market session dates, seen from Jakarta.
// Holidays are not modelled here: the engine knows the real calendar and writes
// the true session_date; this only needs to tell "fresh" from "stale".

const ET = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', hourCycle: 'h23', weekday: 'short',
});

// 24-hour on purpose: the owner reads WIB and every schedule in this repo is UTC, so the two are
// always printed side by side and an am/pm would be one more thing to translate.
const WIB_TIME = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Jakarta', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
});

function etParts(now: Date) {
  const p = Object.fromEntries(ET.formatToParts(now).map(x => [x.type, x.value]));
  return { ymd: `${p.year}-${p.month}-${p.day}`, hour: Number(p.hour), weekday: p.weekday as string };
}

/** `ymd` moved `n` calendar days; `n` may be negative. Pure date arithmetic, no timezone. */
export function addDays(ymd: string, n: number): string {
  const d = new Date(`${ymd}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

const isWeekend = (ymd: string) => [0, 6].includes(new Date(`${ymd}T12:00:00Z`).getUTCDay());

/** The US session (ET calendar date) that new picks should target right now. */
export function nextUsSession(now: Date): string {
  const { ymd, hour } = etParts(now);
  let day = !isWeekend(ymd) && hour < 16 ? ymd : addDays(ymd, 1);
  while (isWeekend(day)) day = addDays(day, 1);
  return day;
}

/** Picks are stale when the latest successful run targets an earlier session. */
export function isStale(latestSessionDate: string | null, now: Date): boolean {
  return latestSessionDate === null || latestSessionDate < nextUsSession(now);
}

/** Today's calendar date in Jakarta (WIB). */
export function wibDate(now: Date): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Jakarta' }).format(now);
}

/** The clock time in Jakarta (WIB), 24-hour: '13:17'. */
export function wibTime(at: Date): string {
  return WIB_TIME.format(at);
}
```

**Impact:** `addDays` becomes part of the module's surface. No caller changes.

### Step 2: the classifier
**File:** `web/lib/decision.ts` (new)
**Change:** one pure module that names the state and the times. It renders nothing and reads nothing
from the network, so both pages and the tests import it freely.
**Code:**

```ts
/**
 * Why there is nothing to act on, in one word, and when the next decision is due.
 *
 * The blank panel (handover Q5): `positions/page.tsx` used to render *nothing* in place of two whole
 * sections whenever the data was stale, and the same blank covered five different situations — the
 * strategy was holding and nothing was due (the common one, roughly three weeks in four), the
 * decision expired at the New York close, nothing was ever produced, the pipeline failed, and paper
 * trading is switched off. Nothing here renders: it only names the state and the times, so both
 * pages say the same words and a test can pin them.
 *
 * Times. The owner reads WIB; every schedule in this repo is UTC. The slots below mirror the three
 * cron lines of `.github/workflows/nightly.yml` and `decision.test.ts` fails if they drift from it:
 * 06:17 UTC = 13:17 WIB, 09:41 = 16:41 WIB, 12:41 = 19:41 WIB.
 */
import { addDays, nextUsSession } from './session';

/**
 * Paper trading is switched off. Mirrors `PAPER_PAUSED` in `.github/workflows/nightly.yml`, which
 * stays the source of truth; `decision.test.ts` reads that file and fails when the two disagree.
 *
 * It is deliberately NOT derived from the database. Measured against the live database on
 * 2026-10-08: the only candidate signature is "the latest run succeeded and its paper step never
 * ran" (`runs.status = 'success' AND runs.paper_status IS NULL`), and it fails twice. It is late —
 * the latest run (id 10, session 2026-10-07) still carries `paper_status = 'success'` from before
 * the pause, so the rule would report "not paused" today. And it is ambiguous — runs 1 and 7 carry
 * exactly that signature for a different reason: paper had not started yet
 * (`strategies.paper_start = 2026-10-07`).
 */
export const PAPER_PAUSED = true;

/**
 * The nightly's cron slots as UTC [hour, minute]: `17 6`, `41 9`, `41 12`. The first is when a
 * decision is due; the last is its final retry, after which silence is a failure rather than a wait.
 */
export const NIGHTLY_SLOTS_UTC: readonly (readonly [number, number])[] = [[6, 17], [9, 41], [12, 41]];

/**
 * The UTC weekdays the nightly runs: cron's `2-6`, Tuesday through Saturday. Cron and
 * `Date.getUTCDay()` use the same numbering (0 = Sunday), so the digits carry over unchanged.
 */
export const NIGHTLY_DAYS_UTC: readonly number[] = [2, 3, 4, 5, 6];

const at = (ymd: string, [h, m]: readonly [number, number]) =>
  new Date(`${ymd}T${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:00Z`);

const utcDay = (ymd: string) => new Date(`${ymd}T12:00:00Z`).getUTCDay();

/**
 * The UTC date of the nightly that owes `session` its decision: the latest Tuesday-to-Saturday on or
 * before it. Tuesday's run reads Monday's session and produces Tuesday's picks; Monday's picks come
 * from Saturday's run, because a session only becomes fetchable at ET midnight (nightly.yml's own
 * comment). Keying the window to this date and not to "the last slot that fired" is what keeps a
 * Monday evening from reading as late: at Monday's close the target is Tuesday, whose run has not
 * come due yet.
 */
export function publishDay(session: string): string {
  let d = session;
  for (let i = 0; i < 7; i++) {
    if (NIGHTLY_DAYS_UTC.includes(utcDay(d))) return d;
    d = addDays(d, -1);
  }
  return session; // unreachable: five days of every seven are in the set
}

/** The session a fresh decision would be for, and the window the nightly has to produce it. */
export type Timing = {
  /** The US session (ET calendar date) new picks target right now. */
  target: string;
  /** The first slot that can produce it: 13:17 WIB on `publishDay(target)`. */
  dueAt: Date;
  /** Its last retry slot, 19:41 WIB. Past this and still nothing is late, not merely pending. */
  lateAfter: Date;
};

export function timing(now: Date): Timing {
  const target = nextUsSession(now);
  const day = publishDay(target);
  return {
    target,
    dueAt: at(day, NIGHTLY_SLOTS_UTC[0]),
    lateAfter: at(day, NIGHTLY_SLOTS_UTC[NIGHTLY_SLOTS_UTC.length - 1]),
  };
}

/**
 * The pipeline, from the page's side:
 * - `never`   no run has ever finished successfully;
 * - `late`    the run that owes `target` a decision has missed its last retry slot;
 * - `waiting` the last good run is spent and the next is not due yet — the routine daily state, and
 *             the one that used to render as a coral alarm;
 * - `current` the last good run targets the session that is coming.
 */
export type PipelineState = 'never' | 'late' | 'waiting' | 'current';

export function pipelineState(
  runSession: string | null, lastGoodRun: Date | null, now: Date,
): PipelineState {
  if (lastGoodRun === null || runSession === null) return 'never';
  const { target, lateAfter } = timing(now);
  if (runSession >= target) return 'current';
  return now.getTime() >= lateAfter.getTime() ? 'late' : 'waiting';
}

/**
 * One strategy's own decision panel:
 * - `never`   paper has not started for it (`paper_state.pending_session` is null);
 * - `live`    it decided, and the decision is for the session that is coming;
 * - `holding` the coming session is not one of its decision sessions — the common state, roughly
 *             three weeks in four for a monthly book. Read from the engine's recorded answer
 *             (`paper_state.pending_decision`, which `decide_book` leaves false on a session that is
 *             neither a rank nor a resize), never re-derived here: those boundaries are NYSE trading
 *             sessions and this module has no trading calendar;
 * - `spent`   whatever it decided was for a session that has closed, OR the strategy has been
 *             retired and superseded. A record, not an order.
 */
export type PanelState = 'never' | 'live' | 'holding' | 'spent';

export function panelState(
  pendingSession: string | null, pendingDecision: boolean, now: Date, retired = false,
): PanelState {
  if (pendingSession === null) return 'never';
  // A retired strategy's last decision is a record whatever its date says. This is the ONE case
  // where a pending row can be dated for a session that has not closed and still must never read
  // as an instruction: an entry is retired and its successor started on the same night, so the
  // predecessor's `pending_session` is the coming session while the predecessor is finished.
  // Measured against production on 2026-10-08: 80 `book_targets` rows and 4 `orders` dated
  // 2026-10-07 carry `pending_decision = true` and belong to entries the roster rebuild retires.
  // They are deliberately NOT deleted -- they are the record of a decision that was made and never
  // acted on -- so the page is the only thing standing between them and the owner's order ticket.
  // That is exactly the failure R5 exists to prevent, and it is handled generically here rather
  // than against any particular rebuild, so it stays true for every future roster change.
  if (retired) return 'spent';
  if (pendingSession < timing(now).target) return 'spent';
  return pendingDecision ? 'live' : 'holding';
}
```

`retired` is defaulted, so the parameter is additive: `web/lib/data.ts`'s `Strategy` already carries
`status`, and `positions/page.tsx` already reads it (`roster.filter(r => r.status !== 'retired' …)`),
so the call site is `panelState(pending.sessionDate, pending.decision, now, strat.status === 'retired')`.

**Impact:** new module, no callers yet.

### Step 3: the classifier's tests, including the two drift guards
**File:** `web/lib/decision.test.ts` (new)
**Change:** pin the constants to `nightly.yml` and the behaviour to the morning that produced this
requirement.
**Code:**

```ts
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
  NIGHTLY_DAYS_UTC, NIGHTLY_SLOTS_UTC, PAPER_PAUSED, panelState, pipelineState, publishDay, timing,
} from './decision';
import { wibDate, wibTime } from './session';

// The workflow is the source of truth for both the schedule and the switch; this module only
// mirrors them. Reading the file here is what turns a drift into a failing test rather than a page
// that quietly states the wrong hour.
const NIGHTLY = readFileSync(new URL('../../.github/workflows/nightly.yml', import.meta.url), 'utf8');

describe('nightly.yml is the source of truth', () => {
  it('mirrors every cron slot, in order', () => {
    const crons = [...NIGHTLY.matchAll(/^\s*- cron: '(\d+) (\d+) \* \* (\S+)'/gm)].map(m => m.slice(1));
    expect(crons).toHaveLength(NIGHTLY_SLOTS_UTC.length);
    expect(crons.map(([min, hour]) => [Number(hour), Number(min)]))
      .toEqual(NIGHTLY_SLOTS_UTC.map(s => [s[0], s[1]]));
    for (const c of crons) expect(c[2]).toBe('2-6');
  });

  it('reads cron 2-6 as Tuesday through Saturday', () => {
    expect(NIGHTLY_DAYS_UTC).toEqual([2, 3, 4, 5, 6]);
  });

  it('mirrors PAPER_PAUSED', () => {
    const m = NIGHTLY.match(/^\s*PAPER_PAUSED: '(true|false)'/m);
    expect(m).not.toBeNull();
    expect(PAPER_PAUSED).toBe(m![1] === 'true');
  });
});

describe('the slots in the time the owner reads', () => {
  const t = timing(new Date('2026-10-08T01:17:40Z'));
  it('is due at 13:17 WIB and late after 19:41 WIB', () => {
    expect(wibTime(t.dueAt)).toBe('13:17');
    expect(wibTime(t.lateAfter)).toBe('19:41');
  });
});

describe('publishDay', () => {
  it("is the session's own day from Tuesday to Friday", () => {
    expect(publishDay('2026-10-06')).toBe('2026-10-06'); // Tue
    expect(publishDay('2026-10-09')).toBe('2026-10-09'); // Fri
  });
  it("is the Saturday before for a Monday session", () => {
    expect(publishDay('2026-10-12')).toBe('2026-10-10'); // Mon <- Sat
  });
});

// 2026-10-08, 08:17 WIB. The page was blank and read as data loss; 80 book_targets rows, 4 orders
// and four pending decisions were untouched in the database, and the nightly was not due for
// another five hours. `lastGoodRun` is runs.id 10's real finished_at.
describe('the morning that produced this requirement', () => {
  const now = new Date('2026-10-08T01:17:40Z');
  const lastGoodRun = new Date('2026-10-07T13:30:28Z');

  it('knows nothing is wrong yet', () => {
    expect(pipelineState('2026-10-07', lastGoodRun, now)).toBe('waiting');
  });

  it('says when the next decision is due, in WIB', () => {
    const t = timing(now);
    expect(t.target).toBe('2026-10-08');
    expect(wibDate(t.dueAt)).toBe('2026-10-08');
    expect(wibTime(t.dueAt)).toBe('13:17');
  });

  it('calls the expired decision spent, not missing', () => {
    expect(panelState('2026-10-07', true, now)).toBe('spent');
  });

  it('calls an expired no-decision session spent too (C and SPY)', () => {
    expect(panelState('2026-10-07', false, now)).toBe('spent');
  });
});

describe('pipelineState', () => {
  it('is never before the first successful run', () => {
    expect(pipelineState(null, null, new Date('2026-10-08T01:00:00Z'))).toBe('never');
    expect(pipelineState('2026-10-07', null, new Date('2026-10-08T01:00:00Z'))).toBe('never');
  });

  it('is current while the last good run targets the coming session', () => {
    // Wed 10:00 ET: the session that is coming is still 2026-10-07.
    expect(pipelineState('2026-10-07', new Date('2026-10-07T13:30:28Z'), new Date('2026-10-07T14:00:00Z')))
      .toBe('current');
  });

  it('is late only once the last retry slot has fired', () => {
    const run = new Date('2026-10-07T13:30:28Z');
    expect(pipelineState('2026-10-07', run, new Date('2026-10-08T12:40:00Z'))).toBe('waiting');
    expect(pipelineState('2026-10-07', run, new Date('2026-10-08T12:41:00Z'))).toBe('late');
  });

  // The case a "a slot has fired since the last good run" rule gets wrong: at Monday's close the
  // target is Tuesday, and Tuesday's run has not come due yet.
  it('is not late on a Monday evening', () => {
    expect(pipelineState('2026-10-12', new Date('2026-10-10T06:30:00Z'), new Date('2026-10-12T21:00:00Z')))
      .toBe('waiting');
  });

  it('reads a Sunday against the Saturday run that owes Monday its picks', () => {
    const sunday = new Date('2026-10-11T03:00:00Z');
    expect(timing(sunday).target).toBe('2026-10-12');
    expect(wibTime(timing(sunday).dueAt)).toBe('13:17');
    // Saturday delivered Monday's picks: nothing is wrong.
    expect(pipelineState('2026-10-12', new Date('2026-10-10T06:30:00Z'), sunday)).toBe('current');
    // Saturday never ran: by Sunday that is late, not a wait.
    expect(pipelineState('2026-10-09', new Date('2026-10-09T06:30:00Z'), sunday)).toBe('late');
  });

  // After the US clocks change, nextUsSession still rolls at the 16:00 ET close.
  it('holds across the daylight-saving change', () => {
    expect(timing(new Date('2026-11-09T22:00:00Z')).target).toBe('2026-11-10');
    expect(wibTime(timing(new Date('2026-11-09T22:00:00Z')).dueAt)).toBe('13:17');
  });
});

describe('panelState', () => {
  const now = new Date('2026-10-08T01:17:40Z'); // target 2026-10-08

  it('is never while paper has not started for the strategy', () => {
    expect(panelState(null, false, now)).toBe('never');
  });

  it('never calls a retired strategy live, even on a decision for the coming session', () => {
    // D9.6: phase 12 retires six entries and leaves their pending rows in place (invariant 3).
    // A predecessor retired on the night its successor started holds a `pending_session` for the
    // COMING session with `pending_decision = true` -- the one shape where the date test alone
    // would say `live`. It is a record, and it must read as one.
    const now = new Date('2026-10-08T01:17:40Z');   // target 2026-10-08
    expect(panelState('2026-10-08', true, now)).toBe('live');              // active: an instruction
    expect(panelState('2026-10-08', true, now, true)).toBe('spent');       // retired: a record
    expect(panelState('2026-10-07', true, now, true)).toBe('spent');       // and the common case
    expect(panelState(null, false, now, true)).toBe('never');              // never started, retired
    // The flag defaults off, so every existing call keeps its meaning.
    expect(panelState('2026-10-08', true, now, false)).toBe(panelState('2026-10-08', true, now));
  });

  it('is live when the decision is for the session that is coming', () => {
    expect(panelState('2026-10-08', true, now)).toBe('live');
    expect(panelState('2026-10-09', true, now)).toBe('live');
  });

  // The common case: roughly three weeks in four for a monthly book. The engine wrote the answer;
  // this module does not recompute the month and week boundaries.
  it('is holding when the coming session is not a decision session', () => {
    expect(panelState('2026-10-08', false, now)).toBe('holding');
  });
});
```

**Impact:** the test suite now fails if anyone edits `nightly.yml`'s schedule or switch without
updating the page, which is the whole point of the mirror.

### Step 4: `session.test.ts` covers the two new exports
**File:** `web/lib/session.test.ts:1-2` (import) and append at `:42`
**Change:** add `wibTime` and `addDays` cases, and correct the comment at `:17`, which still names
the 23:00 UTC schedule that no longer exists. The assertion itself is unchanged.
**Code (the import line, replacing `:2`):**

```ts
import { addDays, isStale, nextUsSession, wibDate, wibTime } from './session';
```

**Code (replacing the `it` at `:17-19`):**

```ts
  // 23:00 UTC was the old nightly slot; the real one is 06:17 UTC (13:17 WIB). Either way an
  // instant after the US close targets the next session.
  it('rolls to the next session for an instant after the close', () => {
    expect(nextUsSession(new Date('2026-10-06T23:00:00Z'))).toBe('2026-10-07'); // Tue 19:00 ET
  });
```

**Code (appended after the `wibDate` describe at `:42`):**

```ts

describe('wibTime', () => {
  it('reads the three nightly slots in Jakarta, 24-hour', () => {
    expect(wibTime(new Date('2026-10-08T06:17:00Z'))).toBe('13:17');
    expect(wibTime(new Date('2026-10-08T09:41:00Z'))).toBe('16:41');
    expect(wibTime(new Date('2026-10-08T12:41:00Z'))).toBe('19:41');
  });
  it('is 00:00, not 24:00, at the WIB day boundary', () => {
    expect(wibTime(new Date('2026-10-07T17:00:00Z'))).toBe('00:00');
  });
});

describe('addDays', () => {
  it('steps the calendar forwards and backwards', () => {
    expect(addDays('2026-10-08', 1)).toBe('2026-10-09');
    expect(addDays('2026-10-12', -2)).toBe('2026-10-10');
    expect(addDays('2026-11-01', -1)).toBe('2026-10-31');
    expect(addDays('2027-03-01', -1)).toBe('2027-02-28');
  });
});
```

**Impact:** none on behaviour.

### Step 5: Positions — `showOrders` becomes a classified state
**File:** `web/app/(app)/positions/page.tsx:1-16` (imports)
**Change:** pull in the two icons, the classifier and `wibTime`.
**Code (replacing lines 1-16):**

```tsx
import { Clock, Crown, Gavel, Landmark, Pause, TriangleAlert } from 'lucide-react';
import { AppHeader } from '@/components/AppHeader';
import { PaperChip } from '@/components/PaperChip';
import { selectStrategy, sharesLabel, strategyIcon } from '@/components/roster';
import { StrategySwitch } from '@/components/StrategySwitch';
import { WhyToggle } from '@/components/WhyToggle';
import { heldUsd, orderSizeChange, picksMonthlySizesWeekly, sizeLabel, sizeTip, type SizeChange } from '@/lib/cadence';
import {
  bookPreview, pendingOrders, positions as getPositions, runStatus, strategies, vetoes as getVetoes,
  type Holding, type Pending, type PendingOrder, type Preview, type RunStatus, type Strategy, type Veto,
} from '@/lib/data';
import {
  PAPER_PAUSED, panelState, pipelineState, timing,
  type PanelState, type PipelineState, type Timing,
} from '@/lib/decision';
import { companyName, monthDay, pct, shortDate, signedPct, signedRp, signedUsd, usd } from '@/lib/format';
import { wibDate, wibTime } from '@/lib/session';
import { cardBg } from '@/lib/slots';
import { checkedLine, headlinesLabel, noCheckLine, vetoSheet, type VetoSheet } from '@/lib/vetoes';
import s from './positions.module.css';
```

### Step 6: Positions — the component body
**File:** `web/app/(app)/positions/page.tsx:25-147` (the whole `Positions` function)
**Change:** fetch the pending decision whatever its session date, classify it, and render a sheet in
every branch where the page used to render nothing.
**Code (complete replacement of the function):**

```tsx
export default async function Positions({ searchParams }: { searchParams: Promise<Search> }) {
  const now = new Date();
  const q = await searchParams;
  const [roster, run] = await Promise.all([strategies(), runStatus(now)]);
  const strat = selectStrategy(roster, q.s);
  // Paper orders exist for research strategies only. They are now fetched whatever session they are
  // for: an expired decision is shown as a spent record (handover Q5), never left as a blank panel.
  const asksOrders = !!strat && !strat.isBenchmark;
  const [open, pending, preview] = await Promise.all([
    strat ? getPositions(strat.id) : Promise.resolve([] as Holding[]),
    asksOrders && strat ? pendingOrders(strat.id) : Promise.resolve(NO_PENDING),
    asksOrders && strat?.engine === 'book' ? bookPreview(strat.id) : Promise.resolve(NO_PREVIEW),
  ]);

  // Which of the five the blank used to be (web/lib/decision.ts). `panel` is this strategy's own
  // decision; `pipeline` is the nightly behind it; the paused note is page-level and sits above both.
  const when = timing(now);
  // The fourth argument is D9.6 and is NOT optional here, whatever its default says: a retired
  // strategy's pending row is a record, never an instruction. Drop it and a superseded entry
  // renders a live order on the night its successor starts.
  const panel = panelState(pending.sessionDate, pending.decision, now, strat?.status === 'retired');
  const pipeline = pipelineState(run.sessionDate, run.finishedAt, now);
  const live = asksOrders && panel === 'live';

  const bracket = open.filter(p => p.kind === 'bracket');
  const book = open.filter(p => p.kind !== 'bracket');
  const pnl = open.reduce((a, p) => a + p.pnl, 0);
  const exitsToday = bracket.filter(p => p.maxDays !== null && p.day >= p.maxDays).length + book.filter(p => p.exitPending).length;
  const invested = book.reduce((a, p) => a + (p.weight ?? 0), 0);
  const holdsBook = strat?.engine === 'book' || strat?.engine === 'benchmark';
  const paper = !!strat && strat.isPaper;
  // No warning for a strategy whose paper clock has not started (a paused or not-yet-run paper night).
  const paperWarn = !!run.sessionDate && run.paperStatus !== 'success' && !!strat?.paperStart;
  const StratIcon = strat ? strategyIcon(strat.icon) : Landmark;
  const href = (id: string) => `/positions?s=${encodeURIComponent(id)}`;
  const [noneTitle, noneSub] = emptyState(strat);
  const orderSession = live ? pending.sessionDate : null;
  // Monthly pick, weekly size check (web/lib/cadence.ts): only these strategies show the change per order.
  const splitCadence = !!strat && picksMonthlySizesWeekly(strat.rulesId);
  const held = heldUsd(book);
  // The news check's verdicts for the same session (C, handover D10). Read only for a strategy that runs
  // the check: its roster row comes from migration 004, which also creates news_vetoes.
  const showChecks = !!strat && !!orderSession && strat.checksNews && strat.engine === 'bracket';
  const checks = showChecks && strat && orderSession ? await getVetoes(strat.id, orderSession) : [];
  const sheet = showChecks ? vetoSheet(checks) : null;

  return (
    <>
      <AppHeader date={shortDate(wibDate(now))} title="Positions" demo={run.isDemo} />
      <div className="stack">
        <section className={`sheet bg-sheet ${s.summary}`}>
          <div className={s.between}>
            <span className="eyebrow">Unrealized P/L</span>
            <span className="pill-outline">
              {strat?.isChampion ? <Crown size={15} /> : <StratIcon size={15} />}
              {strat?.name ?? '—'}
            </span>
          </div>
          {strat && (
            // Retired strategies hold nothing and place nothing: only the one asked for by link is kept.
            <StrategySwitch strategies={roster.filter(r => r.status !== 'retired' || r.id === strat.id)} current={strat.id}
              href={href} label="Strategy" />
          )}
          <div className={s.stats}>
            <div className={`${s.stat} ${pnl < 0 ? 'neg' : 'pos'}`}>
              <span className={`num ${s.big}`}>{signedUsd(pnl)}</span>
              <span className={s.sub}>{signedRp(pnl, run.usdIdr)}</span>
            </div>
            <div className={s.stat}><span className={s.mid}>{open.length}</span><span className={s.sub}>Open</span></div>
            {holdsBook ? (
              <div className={s.stat}><span className={`num ${s.mid}`}>{pct(invested, 0)}</span><span className={s.sub}>Invested</span></div>
            ) : (
              <div className={s.stat}><span className={s.mid}>{exitsToday}</span><span className={s.sub}>Exits today</span></div>
            )}
          </div>
          {paper && strat && (
            <div className={s.paperLine}><PaperChip /><span>{paperNote(strat)}</span></div>
          )}
        </section>

        {PAPER_PAUSED && <PausedNote />}

        {paperWarn && run.sessionDate && (
          <section className={`sheet over bg-coral ${s.warn}`} role="status">
            <div className={s.warnHead}>
              <span className={s.warnIcon} aria-hidden="true"><TriangleAlert size={22} /></span>
              <span className="eyebrow">Paper step</span>
            </div>
            <span className={s.warnText}>{paperWarning(run.paperStatus, run.sessionDate)}</span>
          </section>
        )}

        {open.length === 0 ? (
          <section className={`sheet over bg-stone ${s.none}`}>
            <span>{noneTitle}</span>
            {noneSub && <span className={s.noneSub}>{noneSub}</span>}
          </section>
        ) : (
          <div className={s.grid}>
            {bracket.map((p, i) => <BracketCard key={p.key} q={p} bg={cardBg(p.slot, i)} paper={paper} />)}
            {book.map((p, i) => p.kind === 'benchmark'
              ? <BenchmarkCard key={p.key} q={p} />
              : <BookCard key={p.key} q={p} bg={cardBg(null, bracket.length + i)} paper={paper} />)}
          </div>
        )}

        {strat && live && orderSession && (
          <section className={`sheet over bg-sheet ${s.orders}`}>
            <div className={s.between}>
              <span className="eyebrow">Paper orders for {shortDate(orderSession)}</span>
              {paper && <PaperChip />}
            </div>
            {pending.orders.some(o => o.kind === 'book') && <span className={s.ordersSub}>Target portfolio after the open, by rank</span>}
            {pending.orders.length === 0 ? (
              <span className={s.ordersNone}>{noOrders(strat, pending, sheet)}</span>
            ) : (
              <ul className={s.orderList}>
                {pending.orders.map(o => (
                  <OrderRow key={o.key} o={o} equity={pending.equity} passed={checks.find(v => v.symbol === o.symbol && v.verdict === 'allow')}
                    size={splitCadence && o.kind === 'book' ? orderSizeChange(o.weight, pending.equity, o.symbol, held) : undefined} />
                ))}
              </ul>
            )}
          </section>
        )}

        {/* Q5: where the page used to render nothing at all, it now says which of the five it is. */}
        {strat && asksOrders && !live && (
          <Standing st={strat} state={panel} pipeline={pipeline} when={when} pending={pending} />
        )}

        {strat && panel === 'spent' && pending.sessionDate && pending.orders.length > 0 && (
          <SpentDecision st={strat} session={pending.sessionDate} orders={pending.orders} />
        )}

        {strat && !pending.decision && preview.picks.length > 0 && preview.dataDate && (
          <WouldPick st={strat} preview={preview} />
        )}

        {strat && live && orderSession && sheet && <VetoedTonight st={strat} session={orderSession} sheet={sheet} />}
        <div className="nav-clear" />
      </div>
    </>
  );
}
```

**Impact:** `showOrders` is gone. `pendingOrders` and `bookPreview` now run on a stale page — two
queries that used to be skipped; both are per-strategy and indexed, and the page is already
`force-dynamic`. The "Paper orders for …" and "Vetoed tonight" sections render only in the `live`
state, exactly as before. Everything else that used to be blank now renders a sheet.

### Step 7: Positions — the three new components and the prose
**File:** `web/app/(app)/positions/page.tsx`, inserted after `noOrders` (currently ending at `:182`)
**Change:** the paused note, the standing panel and the spent record. `standingWords` is the only
place the wording lives, and it calls the existing `noOrders()` for the cadence sentence rather than
writing a second one.
**Code (inserted between `noOrders` and `VetoedTonight`):**

```tsx
/**
 * Paper trading is switched off (`PAPER_PAUSED` in `.github/workflows/nightly.yml`). The fifth state
 * of handover Q5, and the one nothing in the app used to say anywhere. While it holds, no paper
 * order is placed and no paper session is stepped, so every panel below stays on the last decision;
 * the nightly's price step still runs, so marks and positions are current.
 */
function PausedNote() {
  return (
    <section className={`sheet over bg-butter ${s.paused}`} role="status">
      <span className={s.pausedIcon} aria-hidden="true"><Pause size={20} /></span>
      <div className={s.pausedText}>
        <span className={s.pausedTitle}>Paper trading is paused</span>
        <span className={s.pausedSub}>
          No paper orders are placed and no paper session is stepped while the roster is rebuilt to
          pay the real broker fees. Prices and positions below are still updated every night.
        </span>
      </div>
    </section>
  );
}

/**
 * Why there is nothing to act on, in plain words (handover Q5), for everything that is not a live
 * decision. The cadence sentence comes from `noOrders()` so the vocabulary lives in one place. The
 * "next run is due" line is suppressed while paper is paused: the next run will not produce a
 * decision, and saying it would is the kind of sentence this panel exists to delete.
 */
function standingWords(
  st: Strategy, state: PanelState, pipeline: PipelineState, when: Timing, p: Pending,
): { title: string; body: string; next: string | null } {
  const dueLine = `The next nightly run is due ${shortDate(wibDate(when.dueAt))} at ${wibTime(when.dueAt)} WIB.`;
  const nextLine = PAPER_PAUSED ? null : dueLine;

  // A retired strategy is finished: it will never decide again, so a "next run is due" line would
  // be false for it even when paper is running. Its last decision is shown as the record it is.
  if (st.status === 'retired') {
    const was = p.sessionDate ? shortDate(p.sessionDate) : 'an earlier session';
    return {
      title: `${st.short} has been replaced`,
      body: p.orders.length > 0
        ? `${st.short} is retired. The ${p.orders.length} ${p.orders.length === 1 ? 'position' : 'positions'} below are what it decided for the ${was} US session before it was replaced — a record of what it decided, never an order to place. Its successor runs in its place.`
        : `${st.short} is retired and decides nothing further. Its successor runs in its place.`,
      next: null,
    };
  }

  if (state === 'never') {
    return {
      title: 'Paper trading has not started',
      body: `${st.short} places its first paper orders at its first paper session. Nothing is pending.`,
      next: nextLine,
    };
  }
  if (pipeline === 'late') {
    return {
      title: 'The nightly run is late',
      body: `A decision for the ${shortDate(when.target)} US session was due at ${wibTime(when.dueAt)} WIB, and the last retry ran at ${wibTime(when.lateAfter)} WIB. Nothing new has arrived.`,
      next: 'Nothing on this page is an instruction to trade.',
    };
  }
  if (state === 'spent') {
    const was = p.sessionDate ? shortDate(p.sessionDate) : 'an earlier session';
    const body = p.orders.length > 0
      ? `${st.short} decided ${p.orders.length} ${p.orders.length === 1 ? 'position' : 'positions'} for the ${was} US session. That session has closed, so they are a record of what it decided — not an order to place.`
      : `${st.short} had nothing to decide for the ${was} US session, and that session has closed.`;
    return { title: 'The last decision has expired', body, next: nextLine };
  }
  // 'holding' — the common state, roughly three weeks in four for a monthly book.
  return {
    title: `Nothing was due for ${p.sessionDate ? shortDate(p.sessionDate) : 'the next session'}`,
    body: noOrders(st, p, null),
    next: nextLine,
  };
}

function Standing({ st, state, pipeline, when, pending }: {
  st: Strategy; state: PanelState; pipeline: PipelineState; when: Timing; pending: Pending;
}) {
  const w = standingWords(st, state, pipeline, when, pending);
  const late = pipeline === 'late';
  return (
    <section className={`sheet over bg-sheet ${s.standing} ${late ? s.standingLate : ''}`} role="status">
      <div className={s.standingHead}>
        <span className={s.standingIcon} aria-hidden="true">
          {late ? <TriangleAlert size={22} /> : <Clock size={22} />}
        </span>
        <span className="eyebrow">{late ? 'Nightly run' : 'Nothing to act on'}</span>
      </div>
      <span className={s.standingTitle}>{w.title}</span>
      <span className={s.standingBody}>{w.body}</span>
      {w.next && <span className={s.standingNext}>{w.next}</span>}
    </section>
  );
}

/**
 * The decision whose session has closed, kept visible rather than removed. Removing it is what
 * caused the incident: on 2026-10-08 the owner read the blank page as data loss while 80
 * `book_targets` rows and four orders sat untouched. Shown as a record and nothing else — rank,
 * ticker, and for a book its target share of the portfolio. Every field that reads like an order
 * ticket (limit, stop, take-profit, share count, dollar size) and every copy button is deliberately
 * absent, so no row here can be mistaken for something to place.
 */
function SpentDecision({ st, session, orders }: { st: Strategy; session: string; orders: PendingOrder[] }) {
  return (
    <section className={`sheet over bg-stone ${s.spent}`}>
      <div className={`${s.between} ${s.spentHead}`}>
        <span className="eyebrow">What {st.short} decided for {shortDate(session)}</span>
        <span className={`chip ${s.spentChip}`} data-tip="That US session has closed: a record, not an order">Expired</span>
      </div>
      <span className={s.spentNote}>
        The {shortDate(session)} US session has closed. This is the record of what {st.short} decided
        that night. Prices, limits and sizes are not shown, because none of it is a live instruction.
      </span>
      <ul className={s.spentList}>
        {orders.map(o => (
          <li key={o.key} className={s.spentRow}>
            <span className={s.rank}>{o.rank}</span>
            <span className={s.spentSym}>{o.symbol}</span>
            <span className={s.spentGap} />
            {o.weight !== null && <span className={`num ${s.spentWeight}`}>{pct(o.weight, 1)}</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}
```

**Impact:** `monthDay` stays imported (still used by `VetoRow` and `OrderRow`). `Pause` and `Clock`
are the only new icons.

### Step 8: Positions CSS
**File:** `web/app/(app)/positions/positions.module.css`, inserted after the "Paper step warning"
block (`:20`), with three lines added to the desktop block (`:85-93`)
**Change:** styles for the three new sections. No existing rule is edited.
**Code (inserted after line 19, before `/* ---- Empty ---- */`):**

```css

/* ---- Paper paused (nightly.yml's PAPER_PAUSED: the 5th state of handover Q5) ---- */
/* Butter, not coral: the pause is a deliberate, known state, not a failure. */
.paused { flex-direction: row; align-items: flex-start; gap: 14px; padding: 22px 22px 62px 24px; }
.pausedIcon {
  flex: none; width: 40px; height: 40px; border-radius: 999px; border: 1.5px solid var(--outline);
  display: flex; align-items: center; justify-content: center;
}
.pausedText { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.pausedTitle { font-size: 21px; line-height: 1.25; letter-spacing: -0.01em; }
.pausedSub { font-size: 15px; line-height: 1.45; color: var(--ink-2); text-wrap: pretty; }

/* ---- Standing: why there is nothing to act on (handover Q5) ---- */
.standing { gap: 10px; padding: 26px 22px 66px 24px; }
.standingHead { display: flex; align-items: center; gap: 12px; }
.standingIcon {
  flex: none; width: 44px; height: 44px; border-radius: 999px; border: 1.5px solid var(--outline);
  display: flex; align-items: center; justify-content: center; color: var(--ink-2);
}
.standingTitle { font-size: 21px; line-height: 1.25; letter-spacing: -0.01em; text-wrap: pretty; }
.standingBody { font-size: 16px; line-height: 1.45; color: var(--ink-2); text-wrap: pretty; }
.standingNext { font-size: 15px; line-height: 1.45; color: var(--ink-3); text-wrap: pretty; }
/* Only a late nightly is a problem; routine expiry and a holding week are not. */
.standingLate .standingIcon { border-color: var(--neg); color: var(--neg); }

/* ---- A spent decision: shown, greyed, and never an order ---- */
.spent { gap: 14px; }
.spentHead { flex-wrap: wrap; row-gap: 8px; }
.spentChip { flex: none; background: transparent; border: 1.5px dashed var(--outline); color: var(--ink-2); }
.spentNote { margin-top: -6px; font-size: 15px; line-height: 1.45; color: var(--ink-2); text-wrap: pretty; }
.spentList { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; color: var(--ink-2); }
.spentRow { display: flex; align-items: center; gap: 10px; padding: 14px 0; border-top: 1px solid var(--hair); }
.spentSym { flex: none; font-size: 20px; font-weight: 500; letter-spacing: -0.02em; }
.spentGap { flex: 1; }
.spentWeight { flex: none; font-size: 15px; }
```

**Code (added inside the `@media (min-width: 1024px)` block, after the `.warn` line at `:87`):**

```css
  .paused { margin-top: 12px; border-radius: 40px; padding: 20px 30px; }
  .standing { margin-top: 12px; border-radius: 40px; padding: 28px 30px; }
  .spent { margin-top: 12px; border-radius: 40px; padding: 28px 30px; }
  .spentList { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 40px; }
```

**Impact:** `.paused`'s `flex-direction: row` overrides `.sheet`'s column, the same pattern
`today.module.css`'s `.emptyRow` already uses. Its 62px bottom padding clears the next sheet's
`.over` overlap of −40px, as `.warn`'s 66px does.

### Step 9: Today — routine expiry stops being an alarm
**File:** `web/app/(app)/page.tsx:1-19` (imports and the local formatter) and `:31-154`
**Change:** the single `run.stale` coral alarm becomes three outcomes: alarm for the two states that
are actually wrong, a calm `waiting` sheet for routine daily expiry, and the paused note above both.
**Code (replacing lines 1-19):**

```tsx
import { Check, Clock, Crown, Pause, TriangleAlert } from 'lucide-react';
import { AppHeader } from '@/components/AppHeader';
import { CopyButton } from '@/components/CopyButton';
import { RefreshButton } from '@/components/RefreshButton';
import { WhyToggle } from '@/components/WhyToggle';
import {
  champion, picks as getPicks, positions as getPositions, runStatus,
  type Holding, type Pick, type RunStatus, type Strategy,
} from '@/lib/data';
import { PAPER_PAUSED, pipelineState, timing, type PipelineState, type Timing } from '@/lib/decision';
import { companyName, money, monthDay, rp, shortDate, signedRp, signedUsd, usd } from '@/lib/format';
import { wibDate, wibTime } from '@/lib/session';
import { SLOT_BG, SLOT_LETTERS, slotBg, slotLetter } from '@/lib/slots';
import { dismiss } from './actions';
import s from './today.module.css';

export const dynamic = 'force-dynamic';

const ORDINAL = ['first', 'second', 'third', 'fourth'];
```

**Code (replacing the `Today` function at `:31-154`):**

```tsx
export default async function Today() {
  const now = new Date();
  const [champ, run] = await Promise.all([champion(), runStatus(now)]);
  const pc = picksChampion(champ);
  const [picks, open] = await Promise.all([
    pc && run.sessionDate && !run.stale ? getPicks(pc.id, run.sessionDate) : Promise.resolve([] as Pick[]),
    pc ? getPositions(pc.id) : Promise.resolve([] as Holding[]),
  ]);
  // Handover Q5: `run.stale` alone used to raise a coral alarm on the ordinary day after the New
  // York close. Only two of its states are actually wrong — no run has ever finished, or the run
  // that owed today's picks missed its last retry at 19:41 WIB.
  const pipeline = pipelineState(run.sessionDate, run.finishedAt, now);
  const when = timing(now);
  const alarm = pipeline === 'never' || pipeline === 'late';
  // Phase 10's guard, kept: only a bracket holding with an order id and a time exit has a day-5 action.
  const actions = open.filter(p => p.orderId !== null && p.maxDays !== null && p.day >= p.maxDays && !p.dismissed);
  const filled = new Set(picks.map(p => p.slot));
  const emptySlots = [1, 2, 3, 4].filter(n => !filled.has(n));
  const session = run.sessionDate ? shortDate(run.sessionDate) : '—';
  const stratLabel = champLabel(champ);

  return (
    <>
      <AppHeader
        date={shortDate(wibDate(now))}
        title="Today"
        deskTitle={run.stale ? 'Today' : pc ? `Picks for US session ${session}` : `US session ${session}`}
        deskAside={<span className="pill-outline" style={{ height: 52, fontSize: 16, color: 'var(--ink)' }}><Crown size={16} />{stratLabel}</span>}
        demo={run.isDemo}
      />

      <div className="stack">
        <section className={`sheet bg-sheet mobile-only ${s.summary}`}>
          <div className={s.between}>
            <span className="eyebrow">US session</span>
            <span className="pill-outline" style={{ fontSize: 16, padding: '0 20px' }}>{session}</span>
          </div>
          <div className={s.between} style={{ alignItems: 'flex-end' }}>
            <div className={s.count}>
              <span className={s.countNum}>{run.stale ? '—' : picks.length}</span>
              <span className={s.countLabel}>{pc ? 'Picks tonight' : 'Buys tonight'}</span>
            </div>
            <div className={s.slotsCol}>
              {pc && (
                <div className="slot-dots" aria-label={`${picks.length} of 4 slots filled`}>
                  {SLOT_LETTERS.map((l, i) => (
                    <span key={i} className={`slot-dot ${filled.has(i + 1) ? SLOT_BG[i] : 'empty'}`}>{l}</span>
                  ))}
                </div>
              )}
              <span className={s.strat}><Crown size={15} />{stratLabel}</span>
            </div>
          </div>
        </section>

        {PAPER_PAUSED && <PausedNote />}

        {alarm ? (
          <section className={`sheet over ${s.alarm}`}>
            <div className={s.between}>
              <span className={s.alarmIcon}><TriangleAlert size={28} /></span>
              <RefreshButton className={`icon-btn ${s.alarmBtn}`} />
            </div>
            <span className={s.alarmTitle}>{alarmTitle(pipeline, when)}</span>
            <span className={s.alarmSub}>{alarmSub(pipeline, run, when)}</span>
          </section>
        ) : pipeline === 'waiting' ? (
          <section className={`sheet over bg-stone ${s.waiting}`} role="status">
            <div className={s.waitingHead}>
              <span className={s.waitingIcon} aria-hidden="true"><Clock size={24} /></span>
              <span className="eyebrow">Nothing to do yet</span>
            </div>
            <span className={s.waitingTitle}>
              {run.sessionDate ? `The ${shortDate(run.sessionDate)} US session has closed.` : 'The last US session has closed.'}
            </span>
            <span className={s.waitingSub}>
              The next picks are due {shortDate(wibDate(when.dueAt))} at {wibTime(when.dueAt)} WIB.
              {run.finishedAt ? ` The last good run finished ${shortDate(wibDate(run.finishedAt))} at ${wibTime(run.finishedAt)} WIB.` : ''}
            </span>
            <span className={s.waitingSub}>Nothing on this page is a live instruction until then.</span>
          </section>
        ) : !pc ? (
          <section className={`sheet over bg-stone ${s.none}`}>
            <span>{noBuysTitle(champ)}</span>
            <span style={{ color: 'var(--ink-3)' }}>Seer recommends no buys.</span>
            <span className={s.noneSub}>
              Research strategies trade on paper only, with no real money. Their orders are in Positions, never here.
            </span>
          </section>
        ) : picks.length === 0 ? (
          <section className={`sheet over bg-stone ${s.none}`}>
            <span>No setups today.</span>
            <span style={{ color: 'var(--ink-3)' }}>Cash is a position.</span>
          </section>
        ) : (
          <div className={s.board}>
            {actions.map(a => (
              <section key={a.key} className={`sheet over bg-coral ${s.action}`}>
                <span className="eyebrow">Action needed</span>
                <div className={s.actionRow}>
                  <span className={s.actionText}><b>{a.symbol}</b>: day {a.day} of {a.maxDays}. Cancel bracket and sell at market.</span>
                  <form action={dismiss}>
                    <input type="hidden" name="orderId" value={a.orderId ?? ''} />
                    <button type="submit" className={`icon-btn ${s.onCoral}`} data-tip="Mark as done" aria-label="Mark as done">
                      <Check size={22} />
                    </button>
                  </form>
                </div>
              </section>
            ))}

            <div className={s.grid}>
              {picks.map(p => <PickCard key={p.id} p={p} rate={run.usdIdr} />)}
              {emptySlots.map(n => (
                <section key={n} className={`${s.emptySlot} desk-only`}>
                  <span className={s.emptyDot}>{slotLetter(n)}</span>
                  <span className={s.emptyTitle}>Empty slot</span>
                  <span className={s.emptySub}>No {ORDINAL[n - 1]} stock passed the rules tonight.</span>
                </section>
              ))}
            </div>

            {emptySlots.length > 0 && (
              <section className={`sheet over bg-sheet mobile-only ${s.emptyRow}`}>
                <span className={s.emptyDot}>{slotLetter(emptySlots[0])}</span>
                <div className={s.emptyText}>
                  <span className={s.emptyTitle}>{emptySlots.length === 1 ? 'Empty slot' : `${emptySlots.length} empty slots`}</span>
                  <span className={s.emptySub}>
                    {emptySlots.length === 1 ? `No ${ORDINAL[emptySlots[0] - 1]} stock passed the rules tonight.` : `Only ${picks.length} passed the rules tonight.`}
                  </span>
                </div>
              </section>
            )}
          </div>
        )}
        {/* The alarm sheet runs to the bottom edge itself; a spacer under it would only show page
            background. Every other branch, the `waiting` sheet included, needs the spacer. */}
        {!alarm && <div className="nav-clear" />}
      </div>
    </>
  );
}
```

**Impact:** `run.stale` is still used for `deskTitle` and the picks count, where it means exactly what
it says. The `nav-clear` condition changes from `!run.stale` to `!alarm`, because the new `waiting`
sheet is a normal sheet and does need the spacer.

### Step 10: Today — the alarm prose and the paused note
**File:** `web/app/(app)/page.tsx`, inserted after the `Today` function (before `PickCard`)
**Change:** the two alarm strings become functions that name the due time, and the paused note.
**Code:**

```tsx
/**
 * The coral alarm is for the two states that are actually wrong: no run has ever finished, or the
 * run that owed today's picks missed its last retry. Routine daily expiry is the `waiting` sheet
 * instead, which says when the next picks arrive. The old single alarm read "Data is from Oct 7. Do
 * not trade today." at 08:17 WIB on a morning when the run was not due until 13:17 WIB.
 */
function alarmTitle(pipeline: PipelineState, when: Timing): string {
  if (pipeline === 'never') return 'No data yet. Do not trade today.';
  return `No picks for ${monthDay(when.target)}. Do not trade today.`;
}

function alarmSub(pipeline: PipelineState, run: RunStatus, when: Timing): string {
  if (pipeline === 'never') return 'The nightly engine has not completed a run yet. Picks stay hidden until it does.';
  const due = `The run was due at ${wibTime(when.dueAt)} WIB and its last retry was ${wibTime(when.lateAfter)} WIB.`;
  const last = run.finishedAt
    ? ` Last good run ${shortDate(wibDate(run.finishedAt))} at ${wibTime(run.finishedAt)} WIB${run.dataDate ? `, from the ${monthDay(run.dataDate)} closes` : ''}.`
    : '';
  return `${due}${last} Picks stay hidden until fresh prices arrive.`;
}

/**
 * Paper trading is switched off (`PAPER_PAUSED` in `.github/workflows/nightly.yml`). The fifth state
 * of handover Q5. The nightly's price step still runs, so this page's data is unaffected; what is
 * frozen is every paper order and paper session behind Positions.
 */
function PausedNote() {
  return (
    <section className={`sheet over bg-butter ${s.paused}`} role="status">
      <span className={s.pausedIcon} aria-hidden="true"><Pause size={20} /></span>
      <div className={s.pausedText}>
        <span className={s.pausedTitle}>Paper trading is paused</span>
        <span className={s.pausedSub}>
          No paper orders are placed and no paper session is stepped while the roster is rebuilt to
          pay the real broker fees. Prices are still updated every night.
        </span>
      </div>
    </section>
  );
}
```

**Impact:** none beyond the two pages.

### Step 11: Today CSS
**File:** `web/app/(app)/today.module.css`, inserted after the `.alarmSub` rule (`:26`), with three
lines added to the desktop block after `.alarm` (`:90`)
**Change:** the `waiting` sheet and the paused note.
**Code (inserted after line 26, before `/* ---- No setups ---- */`):**

```css

/* ---- Waiting: the routine daily expiry (handover Q5) ---- */
/* Not an alarm, and deliberately not the full-bleed `.alarm` sheet: the last session closed and the
   next run is not due yet. Stone, a clock, and the time the next picks arrive -- in WIB, because the
   schedule is UTC and the owner is not. */
.waiting { gap: 10px; padding: 30px 24px 150px; min-height: 420px; }
.waitingHead { display: flex; align-items: center; gap: 12px; }
.waitingIcon {
  flex: none; width: 52px; height: 52px; border-radius: 999px; border: 1.5px solid var(--outline);
  display: flex; align-items: center; justify-content: center; color: var(--ink-2);
}
.waitingTitle { font-size: 40px; line-height: 1; letter-spacing: -0.04em; text-wrap: pretty; }
.waitingSub { max-width: 42ch; font-size: 16px; line-height: 1.45; color: var(--ink-2); text-wrap: pretty; }

/* ---- Paper paused (nightly.yml's PAPER_PAUSED) ---- */
.paused { flex-direction: row; align-items: flex-start; gap: 14px; padding: 22px 22px 62px 24px; }
.pausedIcon {
  flex: none; width: 40px; height: 40px; border-radius: 999px; border: 1.5px solid var(--outline);
  display: flex; align-items: center; justify-content: center;
}
.pausedText { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.pausedTitle { font-size: 21px; line-height: 1.25; letter-spacing: -0.01em; }
.pausedSub { font-size: 15px; line-height: 1.45; color: var(--ink-2); text-wrap: pretty; }
```

**Code (added inside `@media (min-width: 1024px)`, after the `.alarm` line):**

```css
  .waiting { border-radius: 40px; min-height: 0; padding: 32px 32px 36px; }
  .waitingTitle { font-size: 44px; }
  .paused { margin-top: 12px; border-radius: 40px; padding: 20px 30px; }
```

**Impact:** no existing rule changes.

## Verification

**Build:**

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild/web && npx tsc --noEmit
```

Expect no output. (`web/node_modules` in this worktree is **hardlinked**; never replace it with a
symlink — a symlink passes vitest and tsc and then kills `next build` with a misleading "filesystem
root" error.)

**Tests:**

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild/web && npx vitest run
```

Expect `web/lib/decision.test.ts` and `web/lib/session.test.ts` green, and **one known failure that
is not this phase's**: `web/lib/sera/lab.test.ts` (1 failed / 9 passed), which is phase 2's. Do not
chase it.

**Manual check**, against the live database, with no dev server — it prints what each strategy's
panel will say:

```
cd /home/miftah/seer && python - <<'PY'
import re, psycopg
env = dict(re.findall(r'^([A-Z_]+)=(.*)$', open('/home/miftah/seer/.env.local').read(), re.M))
with psycopg.connect(env['DATABASE_URL_UNPOOLED'].strip()) as c:
    print(list(c.execute("SELECT session_date, finished_at FROM runs WHERE status='success' ORDER BY finished_at DESC LIMIT 1")))
    for r in c.execute("SELECT strategy_id, pending_session, pending_decision FROM paper_state ORDER BY strategy_id"):
        print(r)
PY
```

Feed those three columns to `panelState` / `pipelineState` for `new Date()`. At 2026-10-08 the
expected reading is: pipeline `waiting` (nothing is wrong — the run is due 13:17 WIB); panel `spent`
for all six entries, with 20 greyed rows each for `MOM-FR`, `MVW-FR`, `RAW-FR` and `RMW-FR`, 4 for
`C`, and none for `SPY` (a benchmark places no orders); and the paused note on both pages.

**Exit criteria.**

1. No branch of either page renders nothing. Every state that used to be blank now renders a sheet
   naming it.
2. The five states are distinguishable in plain words: **(a) holding, nothing was due** — the
   `holding` panel, written by the existing `noOrders()`; **(b) expired at the New York close** — the
   `spent` panel plus the visible, greyed record; **(c) never produced** — the `never` panel and the
   `never` alarm; **(d) failed** — the existing `paperWarn` coral sheet, untouched, plus the new
   `late` state when the nightly misses its last retry; **(e) paper is paused** — the butter note on
   both pages, which nothing in the app said before.
3. The next decision's time is stated in **WIB** and derived from `nightly.yml`'s cron slots; the
   test fails if the slots or `PAPER_PAUSED` drift from that file.
4. Nothing rendered is mistakable for a live instruction: the spent record carries no limit, stop,
   take-profit, share count, dollar size or copy button, and says so.
5. `npx tsc --noEmit` is clean and `npx vitest run` shows no failure other than phase 2's
   `web/lib/sera/lab.test.ts`.
6. `PAPER_PAUSED` in `.github/workflows/nightly.yml` is still `'true'` and that file is unchanged
   (`git diff --stat .github/` is empty).
7. **(D9.6)** A **retired** strategy's panel reads `spent` whatever its `pending_session` says, and
   its words name it as replaced rather than pending. Pinned by `decision.test.ts`'s
   *"never calls a retired strategy live"* case, which includes the shape phase 12 creates: a
   predecessor holding `pending_decision = true` for the **coming** session.
   **And the flag actually reaches the classifier**, which a unit test on `panelState` alone cannot
   prove: `grep -n 'panelState(' web/app/\(app\)/positions/page.tsx` shows the call passing
   `strat?.status === 'retired'` as its fourth argument. A correct classifier called with three
   arguments renders a retired entry's record as a live order — the exact failure D9.6 and phase
   12's exit criterion 13 exist to stop.

## Handoffs

- **`docs/runbooks/paper-trading.md:76`** still states `cron 23:00 UTC Mon-Fri (06:00 WIB)`, a
  schedule that no longer exists — the same UTC/WIB mismatch this phase fixes in the UI, and the
  documentary cause of one false alarm. **Phase 12 owns it** (R1). Not touched here.
- **A shared `<PausedBanner />` in `web/components/`.** `PausedNote` is ~14 lines duplicated across
  the two pages because `web/components/` is not in this phase's scope and phase 10 is working in
  `web/app/(app)` concurrently. Lifting it into one component, with its own CSS module, is the
  obvious follow-up once the set has landed. Not a requirement of R5.
- **`web/lib/decision.ts`'s vocabulary and phase 11's daily line (R8) — SETTLED by the reconciler,
  2026-10-08.** Phase 11 reports the same four facts — stepped, published, green, paused — to a
  different audience, from its own workflow. Both planners asked to be aligned with the other.
  **The two surfaces keep their own register and share the two words that matter:**

  | the fact | phase 11's daily line (terse, one line) | this phase's panel (a sentence) |
  |---|---|---|
  | (a) holding, nothing was due | `picks none due` | title *"Nothing was due for &lt;date&gt;"* |
  | (e) paper is paused | `paper PAUSED` | banner *"Paper trading is paused"* |

  Neither side imports the other — they are different runtimes and a workflow cannot import
  TypeScript — so the agreement is in the **words the owner reads**, which is what invariant 7 asks
  for. If either side is reworded, reword both. For the cron slots, `NIGHTLY_SLOTS_UTC` and the drift
  test here are the model to copy, not to import.
- **Making `nightly.yml` read the switch from a committed file** would collapse the mirror into a
  single source and delete the drift test. It requires editing `nightly.yml`, which phase 12 owns
  and invariant 2 constrains. Worth raising with the owner after the roster rebuild; out of scope
  now.
- **The next *rebalance* date, as a date.** The panel says the cadence in words ("on the first
  session of each month") but never a date, because the web layer has no NYSE calendar (D9.3). If
  the owner wants "the next decision is 2 Nov", the engine should publish it — a `next_decision`
  column beside `pending_session` — rather than the page guessing it. Not R5, and it would require a
  migration no phase in this set owns.

## Rollback

One commit. `git revert` it. Nothing outside `web/` is touched, no schema changes, no query changes,
and the two new files (`web/lib/decision.ts`, `web/lib/decision.test.ts`) have no importers outside
the two pages. The plan index lists phase 9 as independently revertible.
