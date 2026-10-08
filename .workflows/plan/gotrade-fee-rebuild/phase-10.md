# Phase 10: Sean sizes a rotation from cash, not from holdings

**Plan set:** `GOTRADE_FEE_REBUILD_PLAN.md`
**Analysis:** `20261008-091321-H3M8_code_analyzer.md`
**Satisfies:** R9 — on 2 November the owner opens `/sean/plan`, reads the list top to bottom, types
what it says into Gotrade, and does no arithmetic.
**Depends on:** Phase 5 (semantics only — see *Assumptions*; no file of phase 5's is read or edited)
**Difficulty:** NORMAL
**Package:** `web/lib/sean`

---

## Goal

Today Sean can only size buys from what the plan already holds, or from a number the owner typed
into `sean_link.budget_usd` by hand. After this phase the plan size is **holdings + cash**, and cash
is derived from a recurring contribution schedule (10,000,000 IDR at the start, +5,000,000 IDR on
the 25th of each month) minus what the plan's own uploaded orders have spent. The manual
`budget_usd` survives as an override for when reality diverges. `MIN_TRADE_USD` moves from a guessed
$10 to $25, derived from Gotrade's own two fee constants.

Measured, this is the difference on the owner's real November rotation:

| | before this phase | after |
|---|---|---|
| plan size on 2026-11-02 | $558.00 (what it holds) | **$838.16** |
| each of 20 slots | $27.90 | **$41.91** |
| five replacement buys | $139.50 | **$209.54** |

The $280.16 gap is the 25 October deposit, which is invisible to Sean today.

---

## A correction to the phase brief

The brief and the plan index both say the Sean surface lives under `web/app/(app)/sean/`. **It does
not.** Measured:

```
$ cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild/web && find app -path '*sean*' -name 'page.tsx'
app/sean/page.tsx
app/sean/plan/page.tsx
app/sean/trades/page.tsx
```

Sean is a sibling of `(app)`, not a child of it: `web/app/sean/`. This phase owns `web/app/sean/plan/`.
Phase 9's boundary ("it owns the rest of `web/app/(app)`") is therefore not adjacent to this phase at
all — there is no shared directory and no possible collision. Nothing under `web/app/(app)` is
touched here.

---

## Interface Contract

The reconciler reads this section to detect cross-phase conflicts. Be exact and exhaustive.

**Creates:**
- `web/lib/sean/cash.ts` (new file) exporting `ContributionSchedule`, `OWNER_MONTHLY`,
  `OWNER_USD_IDR`, `CashFlowOrder`, `depositDates`, `depositedIdr`, `depositedUsd`, `netSpentUsd`,
  `cashUsd`

> **Renamed by the reconciler, 2026-10-08.** This plan's draft called the TypeScript constant
> `OWNER_SCHEDULE`; phase 5's Python constant is `OWNER_MONTHLY`. Two names for one schedule in two
> runtimes is the kind of fork that costs a 3am session an hour, so the mirror takes the engine's
> name — `OWNER_MONTHLY` on both sides, `grep` finds both halves. The *type* stays
> `ContributionSchedule`, which is also phase 5's class name. Nothing else about this phase moves:
> the mirror is still hand-written, still TypeScript, and still imports no Python (rung 6: the
> surrounding code's convention — `RESIZING_RULES` and `RESIZE_BAND` already mirror the engine's
> names exactly).
- `web/lib/sean/cash.test.ts` (new file)
- `web/app/sean/plan/view.ts` → `cashLine` (new export, `view.ts:164`, appended)

**Signature changes:**
- `ReminderInput` (`reminders.ts:92`) gains a **required** field `cashUsd: number | null`
- `ReminderPlan` (`reminders.ts:113`) gains a field `cashUsd: number | null`
- `planSizeLine(planSize, budgetUsd)` → `planSizeLine(planSize, budgetUsd, cashUsd)`
  (`app/sean/plan/view.ts:152`)

**Value changes:**
- `MIN_TRADE_USD` (`reminders.ts:25`) `10` → `25`

**Deletes:** none. **Renames:** none.

**Requires (from earlier phases):** nothing in code. Phase 5's
`engine/src/seer_engine/sim/contributions.py` is mirrored by hand in `cash.ts`, exactly as
`reminders.ts:34-38 RESIZING_RULES` mirrors `sim/rules.py PRESETS` and `cadence.ts:21-25` mirrors
`RESIZE_BAND`. See *Assumptions* for the four semantics the mirror asserts; if phase 5 lands them
differently, only the comment and the constants in `cash.ts` move.

**Claims a file the index did not name:** `web/lib/sean/planData.ts`. It is the only wiring between
`cash.ts` and `buildReminders`, it lives inside `web/lib/sean` (this phase's package), and **no other
phase in the set names it**. *Reconciler, 2026-10-08: checked against all eleven other plan files —
unclaimed everywhere else. The claim is recorded in the index's phase-10 **Owns** line.*

**Leaves alone (owned by others):**
- `web/lib/sean/ledger.ts` — its contract is untouched. `cash.ts` reads `totalUsd`, a field
  `types.ts:33` already defines as "Buy: amount + fees. Sell: amount − fees"; cash is **derived**,
  never read from a receipt.
- `web/app/(app)/positions/`, `web/app/(app)/page.tsx`, `web/lib/session.ts` — phase 9
- `web/lib/sera/*`, `web/app/sera/*`, `web/data/lab.json` — phase 2
- `db/migrations/*` — phase 6 holds 016, phase 12 holds 017. **This phase adds no migration and
  changes no schema.** `sean_link.budget_usd` keeps its meaning and its column.
- every file under `engine/` — including `sim/costs.py` (invariant 5) and phase 5's
  `sim/contributions.py`. `costs.py` was *called* to measure the fee curve below; it is not edited.

---

## Files

| File | Action | What changes |
|---|---|---|
| `web/lib/sean/cash.ts` | **create** | the contribution schedule and the cash derivation, pure |
| `web/lib/sean/cash.test.ts` | **create** | 12 tests, including the owner's real October ledger |
| `web/lib/sean/reminders.ts` | modify | `:25` `MIN_TRADE_USD` 10→25; `:92` `ReminderInput.cashUsd`; `:113` `ReminderPlan.cashUsd`; `:196-198` `planSize`; module doc `:1-20` |
| `web/lib/sean/reminders.test.ts` | modify | `:29-33` the `input()` helper; `:115-152` the whole resizing block, re-anchored on the November numbers; two new cash tests |
| `web/lib/sean/planData.ts` | modify | `:117` a new `usdIdr()` read; `:138-164` `planState` derives cash and passes it |
| `web/app/sean/plan/view.ts` | modify | `:5` import `signedUsd`; `:152-158` `planSizeLine` takes cash; `:164` new `cashAmount` + `cashLine` |
| `web/app/sean/plan/view.test.ts` | modify | `:108-117` the `planSizeLine` assertions; `cashLine` |
| `web/app/sean/plan/page.tsx` | modify | `:113-114` the middle `Stat` becomes "Plan size" with a cash sub-line |

Eight files. The index's Files column says 5; it was written before the wiring file
(`planData.ts`) and the two view files were identified. No CSS module is touched — the `Stat`
component already carries a `sub` line (`components/sera/Stat.tsx:13`), so the three-column
`.stats` grid (`plan.module.css:14`) stays as it is.

---

## Measured inputs

Everything numeric below has a command behind it. Run them yourself before implementing; they take
seconds.

### 1. The Gotrade fee curve, and where the $0.10 floor stops biting

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild && PYTHONPATH=engine/src python -c "
from decimal import Decimal as D
from seer_engine.sim.costs import fee_parts
print('amt   buyfee sellfee roundtrip%')
for a in [5,10,15,20,25,28,30,35,40,45,50,60,70,100,200,280,560]:
    a=D(a); b=fee_parts('buy',a).total; s=fee_parts('sell',a).total
    print(f'{a:6} {b:7} {s:7}   {(b+s)/a*100:.3f}%')"
```

Measured 2026-10-08 on the current regime:

| order | buy fee | sell fee | round trip |
|---|---|---|---|
| $5 | 0.12 | 0.13 | **5.000%** |
| $10 | 0.12 | 0.13 | **2.500%** |
| $15 | 0.12 | 0.13 | 1.667% |
| $20 | 0.13 | 0.14 | 1.350% |
| **$25** | **0.13** | **0.14** | **1.080%** |
| $28 | 0.13 | 0.16 | 1.036% |
| $35 | 0.13 | 0.16 | 0.829% |
| $40 | 0.14 | 0.17 | 0.775% |
| $50 | 0.14 | 0.17 | **0.620%** |
| $100 | 0.29 | 0.33 | 0.620% |
| $280 | 0.74 | 0.88 | 0.579% |
| $560 | 1.37 | 1.62 | 0.534% |

And the curve's measured minimum:

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild && PYTHONPATH=engine/src python -c "
from decimal import Decimal as D
from seer_engine.sim.costs import fee_parts
best=min((((fee_parts('buy',D(c)/100).total+fee_parts('sell',D(c)/100).total)/(D(c)/100)*100, D(c)/100)
          for c in range(1000,20001)), key=lambda t:t[0])
print(best)"
# (Decimal('0.5931852669333701200165540074'), Decimal('72.49'))
```

### 2. Why $25, and not $10, $50 or $72.49

`sim/costs.py:230-231` sets Gotrade's current regime to `trading_rate = 0.002` and
`trading_min = 0.10`. Those two constants settle the question without any judgement:

- The trading fee an order actually pays is `max(0.10, 0.002 × amount)`. Confirmed directly:
  `fee_parts('buy', 40)` returns `trading=0.10`, and so does `fee_parts('buy', 50)` — at $50,
  `0.002 × 50 = 0.10` exactly, so **$50 is the amount at which the floor stops being the binding
  term**. That is `trading_min / trading_rate`.
- Below $50 the floor charges a premium of `0.10 − 0.002 × amount` over what the rate alone would
  take. That premium equals the rate's own charge at `0.10 − 0.002a = 0.002a`, i.e. at
  **a = `trading_min / (2 × trading_rate)` = $25**. So: at $25 the floor at most **doubles** the
  trading fee; below $25 it more than doubles it, and at $10 it **quintuples** it ($0.10 charged
  where the rate earns $0.02).
- **$10 is rejected** because a corrective trade there pays 2.500% round trip — four times the
  0.620% a floor-free order pays — to correct a gap the engine itself only cares about above 1% of
  equity.
- **$50 is rejected despite being the exact knee**, on a measurement. The owner's plan size on
  2026-11-02 is $838.16 across 20 names, so one slot is **$41.91**. An add's gap is
  `weight × planSize − held`, which can never exceed the slot itself, so with `MIN_TRADE_USD = 50`
  an add is **structurally impossible** and a trim needs a position above $91.91 — more than
  doubled. $50 would not re-tune the rule, it would delete it.
- **$72.49 is rejected** for the same reason, more so: it is the curve's minimum, not a threshold.

So `MIN_TRADE_USD = 25`, and the comment in the code states the derivation, not the figure.

**The measured consequence, which the owner should not meet as a surprise.** On 2 November each of
the 15 kept names sits $14.01 below its $41.91 slot — under the $25 floor — so Sean asks for no
top-ups and about $210 of cash stays idle for a month. That is the floor working: 15 top-ups of
$14.01 would cost $0.13 each, $1.95, which is 0.93% of the money deployed. By the third month the
slot is $56.05 (20,000,000 IDR at 17,841 ÷ 20) and the same untouched position is $28.15 short,
over the floor, so the adds fire on their own. The rule self-corrects; it does not strand the money
permanently. New picks are always sized at the **full** slot, so a rotation deploys cash whether or
not any add fires — the floor governs corrective trades only, which is what it was written for.

### 3. The owner's real money, and the identity the tests assert

`paper/capital.py:11` holds `PAPER_INITIAL_IDR = 10000000`, and the handover
(`docs/handover/2026-10-08-…:94,166`) records the rate the owner's real cash was converted at:
**17,841 IDR/USD**, giving `paper_state.initial_cash_usd = 560.5067`.

```
10,000,000 / 17,841 = 560.50670   (the 7 Oct start)
 5,000,000 / 17,841 = 280.25335   (each 25th)
15,000,000 / 17,841 = 840.76005   (deposited by 2026-11-02)
```

His real 7 October follow-through: 20 buys of $27.90 each = **$558.00** of stock, **$2.60** of fees,
**$560.60** of cash (handover §Q2 calibration point: *"$2.60 to deploy $558 — 0.47% before a single
round trip"*). So on 2 November:

```
cash      = 840.76005 − 560.60  = 280.16005   →  $280.16
planValue =                       558.00      →  $558.00
planSize  = 558.00 + 280.16     = 838.16      →  $838.16
```

and the identity that makes this testable without a price feed:

> **planValue + cash ≡ deposits − fees paid.**
> `558.00 + 280.16005 = 838.16005` and `840.76005 − 2.60 = 838.16005`. Exact.

**D7 (settlement is not a blocker), now measured rather than argued.** Five replacement buys at
`838.16 / 20 = $41.908` each cost **$209.54**. Cash available is **$280.16**, and all of it dates
from the 25 October deposit ($280.25) — settled **8 calendar days** before the 2 November rotation.
The rotation is funded entirely without that morning's sale proceeds. Same-day reuse is a bonus and
the list never depends on it.

### 4. Baselines, so you can tell your breakage from `main`'s

```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild/web && npx vitest run
#   Test Files  1 failed | 45 passed (46)
#        Tests  1 failed | 578 passed (579)
#   the one failure is lib/sera/lab.test.ts — PHASE 2'S, expected until phase 2 lands

cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild/web && npx tsc --noEmit
#   clean, exit 0

cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild/web && npx vitest run lib/sean/reminders.test.ts app/sean/plan/view.test.ts
#   Test Files  2 passed (2)   Tests  35 passed (35)
```

---

## Implementation Steps

### Step 1: `web/lib/sean/cash.ts` — the schedule and the derivation

**File:** `web/lib/sean/cash.ts` (new file)
**Change:** the whole module. Pure, relative imports only, no database — the same contract
`reminders.ts:19` states.
**Code:**

```ts
/**
 * The owner's wallet, derived (Sean plan phase 10, requirement R9).
 *
 * WHY THIS FILE EXISTS. `./ledger` says it in its first line: "receipts never show the cash
 * balance." Sean reconstructs positions from Gotrade order screenshots, so it can never read the
 * wallet off a receipt. Without cash, `buildReminders` can only size buys from what the plan
 * already holds, and the owner's monthly 5,000,000 IDR is invisible -- on 2026-11-02 that is
 * $280.16 of real money, and every buy comes out about a third short.
 *
 * So cash is DERIVED, never read:
 *
 *     cash = what has been deposited  -  what the plan's own orders have spent
 *
 * The deposits come from a recurring SCHEDULE, not from a monthly hand entry. A schedule also
 * self-corrects: when the owner's actual fills differ from the plan, the next month's cash is still
 * right, because the orders he uploads are subtracted from the same deposits. A number precomputed
 * once into `sean_link.budget_usd` cannot do that. `budget_usd` survives as a manual override for
 * when reality diverges (a withdrawal, a missed month, a rate the mirror below has got wrong).
 *
 * A HAND MIRROR. `OWNER_MONTHLY` mirrors the engine's own `OWNER_MONTHLY` --
 * engine/src/seer_engine/sim/contributions.py, `ContributionSchedule(Decimal("5000000"), 25)` --
 * exactly as `reminders.ts` RESIZING_RULES mirrors sim/rules.py PRESETS and cadence.ts RESIZE_BAND
 * mirrors sim/rules.py RESIZE_BAND. It carries the ENGINE'S NAME ON PURPOSE: there is one schedule
 * in this system and `grep -rn OWNER_MONTHLY` must find both halves of it. Update this file when
 * the engine's schedule changes: the amounts, the day of the month, or the rule that a deposit is
 * dated on its calendar day.
 *
 * ONE DIFFERENCE FROM THE ENGINE, ON PURPOSE. The engine deposits on the calendar date and lets the
 * NYSE calendar decide which session first spends the money (the gap from the 25th to the next
 * month's first session is a measured 7.0 days on average, 4 to 10). Sean has no market calendar
 * and does not need one: it reports the WALLET, and money is in the wallet from the day it lands.
 * Both are the same rule -- "the deposit is dated on the 25th" -- read for two different questions.
 *
 * Pure: no database, relative imports only (vitest has no `@/` alias).
 */
import { cents } from './money';
import type { Side } from './reminders';

/**
 * A recurring contribution: one opening amount on `startDate`, then `monthlyIdr` on every
 * `dayOfMonth` after it. Amounts are IDR because that is the currency the owner actually adds;
 * `depositedUsd` converts once, at the rate it is given.
 */
export type ContributionSchedule = {
  /** YYYY-MM-DD. The opening deposit lands on this day. */
  startDate: string;
  /** The opening deposit, in rupiah. */
  initialIdr: number;
  /** Added on every `dayOfMonth` strictly after `startDate`, in rupiah. */
  monthlyIdr: number;
  /** 1-28, so that every month has the day. */
  dayOfMonth: number;
};

/**
 * The owner's own plan, decided 2026-10-08: 10,000,000 IDR to start, +5,000,000 IDR on the 25th of
 * each month. `startDate` is a placeholder here -- callers pass `sean_link.since`, the day the
 * owner's plan actually began, so the schedule and the plan's orders are sliced on the same date.
 */
export const OWNER_MONTHLY: ContributionSchedule = {
  startDate: '2026-10-07',
  initialIdr: 10_000_000,
  monthlyIdr: 5_000_000,
  dayOfMonth: 25,
};

/**
 * The rate to fall back on when `fx_rates` has no row: 17,841 IDR/USD, the rate the owner's real
 * 10,000,000 IDR was converted at (`paper_state.initial_cash_usd` = 560.5067; handover
 * 2026-10-08, sections Q3 and 5). A fallback only -- `planData.ts` reads the live rate first.
 */
export const OWNER_USD_IDR = 17_841;

/** The fields of a plan order the cash derivation reads. A ledger order satisfies it. */
export type CashFlowOrder = {
  side: Side;
  /** Buy: amount + fees (cash out). Sell: amount - fees (cash in). See ./types SeanOrder.totalUsd. */
  totalUsd: number;
};

function checkSchedule(s: ContributionSchedule): void {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s.startDate)) {
    throw new Error(`startDate must be YYYY-MM-DD, got ${s.startDate}`);
  }
  if (!Number.isInteger(s.dayOfMonth) || s.dayOfMonth < 1 || s.dayOfMonth > 28) {
    throw new Error(`dayOfMonth must be a whole number from 1 to 28, got ${s.dayOfMonth}`);
  }
  if (!Number.isFinite(s.initialIdr) || s.initialIdr < 0) {
    throw new Error(`initialIdr must be >= 0, got ${s.initialIdr}`);
  }
  if (!Number.isFinite(s.monthlyIdr) || s.monthlyIdr < 0) {
    throw new Error(`monthlyIdr must be >= 0, got ${s.monthlyIdr}`);
  }
}

/**
 * Every day money landed, from `startDate` through `through` (both YYYY-MM-DD, inclusive),
 * ascending. The first is `startDate` itself; the rest are each `dayOfMonth` strictly after it.
 * Empty when `through` is before `startDate`. A `startDate` that IS the day of the month gets one
 * deposit that day, not two.
 */
export function depositDates(s: ContributionSchedule, through: string): string[] {
  checkSchedule(s);
  const out: string[] = [];
  if (through < s.startDate) return out;
  out.push(s.startDate);
  const dd = String(s.dayOfMonth).padStart(2, '0');
  let year = Number(s.startDate.slice(0, 4));
  let month = Number(s.startDate.slice(5, 7));
  for (;;) {
    const day = `${year}-${String(month).padStart(2, '0')}-${dd}`;
    if (day > through) break;
    if (day > s.startDate) out.push(day);
    month += 1;
    if (month > 12) {
      month = 1;
      year += 1;
    }
  }
  return out;
}

/** Rupiah deposited from `startDate` through `through`. */
export function depositedIdr(s: ContributionSchedule, through: string): number {
  const days = depositDates(s, through);
  if (days.length === 0) return 0;
  return s.initialIdr + s.monthlyIdr * (days.length - 1);
}

/**
 * Dollars deposited from `startDate` through `through`, converted at `usdIdr` (rupiah per dollar),
 * to the cent. One rate for every deposit: the owner's wallet is in dollars once it reaches
 * Gotrade, and Sean has no record of the rate each transfer actually got. The override
 * (`sean_link.budget_usd`) is what corrects a rate that has drifted far enough to matter.
 */
export function depositedUsd(s: ContributionSchedule, through: string, usdIdr: number): number {
  if (!Number.isFinite(usdIdr) || usdIdr <= 0) throw new Error(`usdIdr must be > 0, got ${usdIdr}`);
  return cents(depositedIdr(s, through) / usdIdr);
}

/**
 * Dollars the plan's orders took out of the wallet: buys out, sells in, fees already inside
 * `totalUsd` on both sides. Negative when the plan has sold more than it has bought.
 */
export function netSpentUsd(orders: readonly CashFlowOrder[]): number {
  let out = 0;
  for (const o of orders) out += o.side === 'buy' ? o.totalUsd : -o.totalUsd;
  return cents(out);
}

/**
 * The wallet: deposits through `through`, less what the plan's orders spent. `orders` must be the
 * SAME slice the reminders use -- `planOrders(all, since)` -- so that a sale of a stock bought
 * before the plan, made after `since`, funds the plan exactly as it did in real life on
 * 2026-10-07.
 *
 * Can be negative, and is left negative rather than clamped: a wallet that reads below zero means
 * the schedule and the uploaded orders disagree, and hiding that would be worse than showing it.
 */
export function cashUsd(input: {
  schedule: ContributionSchedule;
  through: string;
  usdIdr: number;
  orders: readonly CashFlowOrder[];
}): number {
  return cents(depositedUsd(input.schedule, input.through, input.usdIdr) - netSpentUsd(input.orders));
}
```

**Impact:** a new pure module. Nothing imports it yet. `import type { Side } from './reminders'`
is a type-only import, so there is no import cycle at runtime.

---

### Step 2: `reminders.ts` — the floor, the input, and `planSize`

**File:** `web/lib/sean/reminders.ts:1-20` (module doc), `:25` (the floor), `:92-111`
(`ReminderInput`), `:113-124` (`ReminderPlan`), `:196-198` (`planSize`)
**Change:** four edits. Nothing else in the file moves — `ACTION_ORDER:126` stays, `doneBy:164`
stays, the stable sort at `:229` stays, the whole-position sell at `:202-208` stays, the
dollar-denominated buy at `:209-216` stays.

**2a. The module doc, `:1-20`.** Replace the existing block comment with:

```ts
/**
 * Sean's buy/sell reminders (plan phase 5, requirement R4; cash added in the Gotrade fee rebuild,
 * phase 10 / R9).
 *
 * The followed roster method's newest picks (`book_targets` at its latest session) against the
 * owner's PLAN holdings: the orders whose New York trade date (ledger orderSession) is on or after
 * `sean_link.since`, run through the one ledger (contract B, ./ledger). Holdings from before
 * `since` are never part of the plan, so they never get a sell reminder.
 *
 * Rules:
 *  - sell: a plan holding the picks no longer name. The whole plan position, never more.
 *  - buy:  a pick the plan does not hold, sized weight × plan size (no amount without a plan size).
 *  - add / trim: only when the method's rules resize (engine `resize=True`), measured at the
 *    pick's decision price like the engine, and only when the gap is at least MIN_TRADE_USD and at
 *    least RESIZE_BAND of the plan (Gotrade's minimum fee makes smaller trades waste money).
 *  - done: an uploaded order of the same side and stock whose New York trade date is on or after
 *    the decision session, or a row the owner marked done for that decision.
 *  - no picks at all: no reminders (an empty decision is not an order to sell everything).
 *
 * PLAN SIZE IS HOLDINGS PLUS CASH. The owner adds 5,000,000 IDR to his wallet every month, and a
 * plan size taken from holdings alone cannot see it: on 2026-11-02 that is $280.16 of real money
 * and every buy would be sized about a third short. `cashUsd` comes from ./cash, which derives the
 * wallet from the contribution schedule and the plan's own orders, because ./ledger can never read
 * a balance off a receipt. `budgetUsd` (sean_link.budget_usd) still overrides everything when the
 * owner types a number in.
 *
 * Orders are always DOLLAR-DENOMINATED, never share counts: prices drift between the decision's
 * close and the next open, and a fractional dollar order absorbs that drift where a share count
 * does not. The roster's book rules are already `-frac`.
 *
 * Pure: no database, relative imports only (vitest has no `@/` alias).
 */
```

**2b. The floor, `:24-25`.** Replace both lines with:

```ts
/**
 * An add or a trim smaller than this is not worth Gotrade's fees. Derived from the schedule's own
 * two constants (engine sim/costs.py, current regime: `trading_rate = 0.002`, `trading_min = 0.10`),
 * not chosen: the $0.10 floor charges a premium of `0.10 − 0.002 × amount` over what the rate alone
 * would take, and that premium stops exceeding the rate's own charge at
 * `0.10 / (2 × 0.002)` = $25. So at $25 the floor at most doubles the trading fee; below it, it
 * more than doubles it, and at $10 it quintuples it ($0.10 charged where the rate earns $0.02).
 *
 * Measured round trip (buy fee + sell fee over the amount, `costs.fee_parts` on the current
 * regime, 2026-10-08): $10 pays 2.500%, $25 pays 1.080%, $50 pays 0.620%, $560 pays 0.534%.
 *
 * Not $50, which is where the floor stops binding altogether (0.10 / 0.002): the owner's plan size
 * on 2026-11-02 is $838.16 over 20 names, a $41.91 slot, and an add's gap can never exceed its own
 * slot -- a $50 floor would make an add structurally impossible rather than merely expensive.
 */
export const MIN_TRADE_USD = 25;
```

**2c. `ReminderInput`, `:92-111`.** Add one field after `budgetUsd`:

```ts
export type ReminderInput = {
  /** The decision's session (book_targets.session_date), YYYY-MM-DD. */
  sessionDate: string;
  /** The decision's picks, in rank order. Empty: no reminders. */
  targets: readonly Target[];
  /** resizes(rulesId) of the followed method. */
  resizes: boolean;
  /** Plan shares per stock (sharesBySymbol over planOrders). */
  held: ReadonlyMap<string, number>;
  /** Shares held from outside the plan per stock (outsideShares). */
  outside: ReadonlyMap<string, number>;
  /** Latest daily close per stock (sean_marks). */
  closes: ReadonlyMap<string, number>;
  /** sean_link.budget_usd: the owner's manual override; null = derive the plan size. */
  budgetUsd: number | null;
  /**
   * The wallet (./cash cashUsd): deposits so far less what the plan's orders spent. null when it
   * cannot be derived, and then the plan size falls back to holdings alone, as it did before
   * phase 10. May be negative.
   */
  cashUsd: number | null;
  /** The plan's orders, oldest first. */
  orders: readonly PlanOrderLite[];
  /** The owner's done marks (any decision; only this decision's count). */
  marks: readonly ReminderMark[];
};
```

**2d. `ReminderPlan`, `:113-124`.** Add one field and restate `planSize`'s doc:

```ts
export type ReminderPlan = {
  /** Σ plan shares × price. */
  planValue: number;
  /** The wallet as it was given (ReminderInput.cashUsd), passed through for the page. */
  cashUsd: number | null;
  /**
   * What each pick's weight is multiplied by: budgetUsd when the owner set one, else
   * planValue + cashUsd, else planValue, else null (and then buys carry no amount).
   */
  planSize: number | null;
  /** The plan's open positions, largest first. */
  holdings: PlanHolding[];
  /** Every reminder, sells first (they free the money for buys), then trims, buys, adds. */
  reminders: Reminder[];
  open: Reminder[];
  done: Reminder[];
};
```

**2e. `planSize`, `:196-198`.** Replace the two statements with:

```ts
  const planValue = holdings.reduce((sum, h) => sum + h.value, 0);
  // Holdings plus the wallet: the money that is going to be spread over the picks, not just the
  // money already in them. The owner's override wins; cash that cannot be derived falls back to
  // holdings alone, which is what this did before phase 10.
  const funded = input.cashUsd === null ? planValue : planValue + input.cashUsd;
  const planSize =
    input.budgetUsd !== null && input.budgetUsd > 0 ? input.budgetUsd : funded > 0 ? funded : null;
```

**2f. The return, `:235-242`.** Add `cashUsd` to the returned object:

```ts
  return {
    planValue,
    cashUsd: input.cashUsd,
    planSize,
    holdings,
    reminders,
    open: reminders.filter(r => r.done === null),
    done: reminders.filter(r => r.done !== null),
  };
```

**Impact:** `ReminderInput` gains a required field, so every construction site must supply it.
Measured, there are exactly two: `planData.ts:152` (step 3) and the `input()` helper at
`reminders.test.ts:29` (step 6). `npx tsc --noEmit` catches any other.

---

### Step 3: `planData.ts` — read the rate, derive the cash, pass it in

**File:** `web/lib/sean/planData.ts:1-12` (imports), after `:125` (the new read), `:138-164`
(`planState`)
**Change:** three edits.

**3a. Imports, `:9-13`.** Add the `cash` imports beside the existing ones:

```ts
import { cashUsd, OWNER_MONTHLY, OWNER_USD_IDR } from '@/lib/sean/cash';
import { orderSession } from '@/lib/sean/ledger';
import {
  buildReminders, outsideShares, planOrders, resizes, sharesBySymbol,
  type ReminderMark, type ReminderPlan, type Side, type Target,
} from '@/lib/sean/reminders';
```

**3b. A new read, appended after `latestCloses` (`:125`).**

```ts
/**
 * The newest USD/IDR rate the engine has stored (fx_rates, written by the data workflows), used to
 * put the owner's rupiah contributions into dollars. Falls back to OWNER_USD_IDR -- the rate his
 * real 10,000,000 IDR was converted at -- when the table is empty, so a missing row costs accuracy
 * and never the page.
 */
export async function latestUsdIdr(): Promise<number> {
  const [r] = await sql`SELECT usd_idr FROM fx_rates ORDER BY date DESC LIMIT 1`;
  const rate = r === undefined ? NaN : Number(r.usd_idr);
  return Number.isFinite(rate) && rate > 0 ? rate : OWNER_USD_IDR;
}
```

**3c. `planState`, `:138-164`.** Replace the whole function:

```ts
/** The followed method, its picks and the reminders against the plan; null when nothing is followed. */
export async function planState(): Promise<PlanState | null> {
  const l = await link();
  if (!l) return null;
  const [decision, all] = await Promise.all([
    l.retired ? Promise.resolve(null) : latestTargets(l.strategyId),
    ledgerOrders(),
  ]);
  const inPlan = planOrders(all, l.since);
  const held = sharesBySymbol(inPlan);
  const outside = outsideShares(sharesBySymbol(all), held);
  const [marksDone, closes, usdIdr] = await Promise.all([
    decision ? reminderMarks(l.strategyId, decision.sessionDate) : Promise.resolve([] as ReminderMark[]),
    latestCloses([...held.keys()]),
    latestUsdIdr(),
  ]);
  // The wallet, derived: the contribution schedule from the plan's own start date, less what the
  // plan's orders have spent. `through` is today's New York date -- the same calendar plan
  // membership is counted in (planOrders / orderSession), so the deposits and the orders are
  // sliced consistently.
  const cash = cashUsd({
    schedule: { ...OWNER_MONTHLY, startDate: l.since },
    through: orderSession(new Date().toISOString()),
    usdIdr,
    orders: inPlan.map(o => ({ side: o.side, totalUsd: o.totalUsd })),
  });
  const plan = buildReminders({
    sessionDate: decision?.sessionDate ?? l.since,
    targets: decision?.targets ?? [],
    resizes: resizes(l.rulesId),
    held,
    outside,
    closes,
    budgetUsd: l.budgetUsd,
    cashUsd: cash,
    orders: inPlan.map(o => ({ symbol: o.symbol, side: o.side, executedAt: o.executedAt, price: o.price })),
    marks: marksDone,
  });
  return { link: l, targets: decision, plan, outside: [...outside.keys()].sort() };
}
```

**Impact:** one extra query per `/sean/plan` request, run inside the existing `Promise.all`, so no
extra round trip in wall-clock terms. `openReminderCount` (`:172`) already wraps `planState` in
`try/catch` and returns 0 on any failure, so a broken `fx_rates` read cannot take the badge or the
rail down. `inPlan` is `LedgerRow[]`, which carries `totalUsd` (`data.ts:98`), so no query changes.

---

### Step 4: `view.ts` — the plain words

**File:** `web/app/sean/plan/view.ts:5` (import), `:151-158` (replace `planSizeLine`), then append
`cashLine`
**Change:** the caption now says where the money came from, in the owner's own terms.

**A trap, measured.** `lib/format.ts:6` is `money = (v) => Math.abs(v).toFixed(2)`, so **`usd()`
drops the minus sign**: `usd(-0.09)` renders `'$0.09'`. Cash can genuinely be negative — the owner's
real wallet was **−$0.09** on 8 October (he spent $560.60 against a $560.51 deposit). Rendering that
as `$0.09` would be a lie on the page. Use `signedUsd` (`format.ts:8`, which renders `−$0.09`)
whenever the number can be below zero.

**4a. The import, `:5`:**

```ts
import { shortDate, signedUsd, usd } from '../../../lib/format';
```

**4b. The code:**

```ts
/** Cash, with its sign kept: usd() takes an absolute value, and the wallet can be below zero. */
const cashAmount = (v: number): string => (v < 0 ? signedUsd(v) : usd(v));

/** The caption of "Your plan": where the plan size comes from, in the owner's own terms. */
export function planSizeLine(
  planSize: number | null, budgetUsd: number | null, cashUsd: number | null,
): string {
  if (budgetUsd !== null) return `Plan size ${usd(budgetUsd)}, the amount you set. Each pick gets its share of it.`;
  if (planSize !== null && cashUsd !== null) {
    return `Plan size ${usd(planSize)}: ${usd(planSize - cashUsd)} in stocks and ${cashAmount(cashUsd)} in cash. Each pick gets its share of the whole amount, so the cash gets used. Set an amount below to override it.`;
  }
  if (planSize !== null) {
    return `Plan size ${usd(planSize)}, what the plan holds now. Set an amount to size buys differently.`;
  }
  return 'Set how much you want to put into this plan, and Sean will say how much of each stock to buy.';
}

/**
 * The line under the Plan size tile: what it is made of. null when there is no plan size, or when
 * the owner typed one in (then the tile already says so and the split would be a guess).
 */
export function cashLine(planSize: number | null, cashUsd: number | null, budgetUsd: number | null): string | null {
  if (planSize === null || cashUsd === null || budgetUsd !== null) return null;
  return `${usd(planSize - cashUsd)} in stocks + ${cashAmount(cashUsd)} cash`;
}
```

**Impact:** `planSizeLine` gains a third required parameter. One call site (`page.tsx:144`) and one
test (`view.test.ts:109-111`), both updated below. `signedUsd` is a new import in this file; `usd`
and `shortDate` are already imported at `:5`.

---

### Step 5: `page.tsx` — one tile tells him what he has to spend

**File:** `web/app/sean/plan/page.tsx:15-17` (import), `:113-114` (the middle `Stat`), `:144`
(the caption)
**Change:** three edits. No new tile and no CSS change — `.stats` stays a three-column grid
(`plan.module.css:14`) and the existing `Stat` `sub` line (`components/sera/Stat.tsx:13`) carries
the split.

**5a. The import, `:15-17`:**

```tsx
import {
  cashLine, doneLine, methodTitle, outsideLine, picksLine, planSizeLine, reminderDetail,
  reminderTitle, todoLabel,
} from './view';
```

**5b. The middle tile, `:113-114`.** Replace the one `Stat`:

```tsx
            <Stat value={plan.planSize === null ? '—' : usd(plan.planSize)} label="Plan size" size="md"
              sub={cashLine(plan.planSize, plan.cashUsd, link.budgetUsd)}
              tip="What the picks are sized against: the stocks this plan holds plus the cash you have added since it started" />
```

**5c. The caption, `:144`:**

```tsx
        <Section eyebrow={`Since ${shortDate(link.since)}`} title="Your plan"
          caption={planSizeLine(plan.planSize, link.budgetUsd, plan.cashUsd)}>
```

**Impact:** the owner now reads one number — *Plan size $838.16, $558.00 in stocks + $280.16 cash* —
and every "Buy about $41.91 of XYZ" below it is that number times a weight. Nothing on the page asks
him to add anything up. The rows themselves (`ReminderRow:181`, sells first by `ACTION_ORDER:126`)
are unchanged, so his sequence — sell the five, then buy from the list — is the order he already
reads top to bottom.

---

### Step 6: `reminders.test.ts` — the helper, the resizing block, and two cash tests

**File:** `web/lib/sean/reminders.test.ts:29-33` and `:115-152`
**Change:** `input()` gains the new field; the resizing block is re-anchored on the owner's real
November numbers, because at `MIN_TRADE_USD = 25` the old $17 and $18 gaps no longer fire; two cash
tests are added.

**6a. The helper, `:29-33`:**

```ts
function input(over: Partial<ReminderInput> = {}): ReminderInput {
  return {
    sessionDate: OCT, targets: RAW, resizes: true, held: new Map(), outside: new Map(), closes: new Map(),
    budgetUsd: null, cashUsd: null, orders: [], marks: [], ...over,
  };
}
```

**6b. Append a new block after the `fresh link` describe (`:57`):**

```ts
describe('buildReminders: the plan size is holdings plus cash', () => {
  /**
   * 2026-11-02, measured. Deposited by then: 15,000,000 IDR at 17,841 = $840.76. Spent: the 20 real
   * Oct 7 buys, $560.60 including $2.60 of fees. So cash = $280.16, holdings = $558.00, and the
   * plan size is $838.16 -- which is the deposits less the fees, exactly.
   */
  const NOV_CASH = 280.16;

  it('sizes buys from holdings + cash, not holdings alone', () => {
    const r = buildReminders(input({ held: followed(), orders: octBuys, cashUsd: NOV_CASH }));
    expect(r.planValue).toBeCloseTo(558, 6);
    expect(r.cashUsd).toBe(NOV_CASH);
    expect(r.planSize).toBeCloseTo(838.16, 6);
    // the identity: holdings + cash = deposits - fees paid
    expect(r.planValue + NOV_CASH).toBeCloseTo(840.76 - 2.6, 2);
  });

  it('a rotation is funded by the deposit alone: five new names cost less than the cash', () => {
    const picks: Target[] = [
      ...RAW.filter(t => !['DOW', 'BAX', 'UPS', 'BMY', 'TGT'].includes(t.symbol)),
      ...['AAA', 'BBB', 'CCC', 'DDD', 'EEE'].map(symbol => ({ symbol, weight: 0.05, last: 100 })),
    ];
    const r = buildReminders(input({
      sessionDate: NOV, targets: picks, held: followed(), orders: octBuys, cashUsd: NOV_CASH,
    }));
    const sells = r.open.filter(x => x.action === 'sell');
    const buys = r.open.filter(x => x.action === 'buy');
    expect(sells).toHaveLength(5);
    expect(buys).toHaveLength(5);
    // sells come first: ACTION_ORDER, and the owner's own stated sequence
    expect(r.open.slice(0, 5).every(x => x.action === 'sell')).toBe(true);
    const needed = buys.reduce((sum, x) => sum + (x.usd ?? 0), 0);
    expect(needed).toBeCloseTo(209.54, 2);
    // D7: the buys are covered by settled cash, with no sale proceeds reused the same day
    expect(needed).toBeLessThan(NOV_CASH);
  });

  it('cash the owner has spent beyond his deposits reads negative, and still sizes the plan', () => {
    const r = buildReminders(input({ held: followed(), orders: octBuys, cashUsd: -0.09 }));
    expect(r.cashUsd).toBe(-0.09);
    expect(r.planSize).toBeCloseTo(557.91, 6);
  });

  it('the owner’s typed plan size still overrides the derived one', () => {
    const r = buildReminders(input({ held: followed(), orders: octBuys, cashUsd: NOV_CASH, budgetUsd: 1000 }));
    expect(r.planSize).toBe(1000);
  });

  it('without cash it falls back to holdings, exactly as before', () => {
    const r = buildReminders(input({ held: followed(), orders: octBuys, cashUsd: null }));
    expect(r.planSize).toBeCloseTo(558, 6);
  });
});
```

**6c. Replace the whole `resizing` describe, `:115-152`:**

```ts
describe('buildReminders: resizing', () => {
  /** The owner's real 2026-11-02 plan size: $558.00 of stock + $280.16 of cash. Slot: $41.908. */
  const NOV_SIZE = 838.16;
  const SLOT = NOV_SIZE * 0.05; // 41.908

  const drifted = (): Map<string, number> => {
    const held = followed();
    held.set('MU', 80 / 1045.56); // $80 at the decision price: $38.09 above its $41.91 share
    held.set('BAX', 60 / 24.36); // $60: $18.09 above, under the $25 floor
    return held;
  };

  it('trims a pick above its share, ignores gaps under $25', () => {
    const r = buildReminders(input({ held: drifted(), budgetUsd: NOV_SIZE }));
    expect(r.open).toHaveLength(1);
    expect(r.open[0]).toMatchObject({ action: 'trim', side: 'sell', symbol: 'MU' });
    expect(r.open[0].usd).toBeCloseTo(80 - SLOT, 6);
  });

  it('adds to a pick below its share', () => {
    const held = followed();
    held.set('MU', 10 / 1045.56); // $31.91 below its $41.91 share
    const r = buildReminders(input({ held, budgetUsd: NOV_SIZE }));
    expect(r.open).toHaveLength(1);
    expect(r.open[0]).toMatchObject({ action: 'add', side: 'buy', symbol: 'MU' });
    expect(r.open[0].usd).toBeCloseTo(SLOT - 10, 6);
  });

  it('a gap that would have traded at the old $10 floor is left alone at $25', () => {
    const held = followed();
    held.set('MU', 28 / 1045.56); // $13.91 below its share: over $10, under $25
    const r = buildReminders(input({ held, budgetUsd: NOV_SIZE }));
    expect(r.reminders).toHaveLength(0);
  });

  it('never adds or trims for rules that do not resize', () => {
    const r = buildReminders(input({ held: drifted(), budgetUsd: NOV_SIZE, resizes: false }));
    expect(r.reminders).toHaveLength(0);
  });

  it('a big plan uses the engine 1% band, not the $25 floor', () => {
    const held = new Map(RAW.map(t => [t.symbol, 250 / t.last]));
    held.set('MU', 220 / 1045.56); // $30 below its $250 share: under 1% of $5,000
    held.set('DELL', 190 / 574); // $60 below: over the band
    const r = buildReminders(input({ held, budgetUsd: 5000 }));
    expect(r.open.map(x => `${x.action}:${x.symbol}`)).toEqual(['add:DELL']);
    expect(r.open[0].usd).toBeCloseTo(60, 6);
  });
});
```

**Impact:** the `$5,000` band test is unchanged in substance and still passes
(`max(25, 0.01 × 5000 = 50) = 50`, so the $30 gap is skipped and the $60 gap fires). The third test
is new and pins the floor change itself: $13.91 traded at $10 and does not at $25.

---

### Step 7: `cash.test.ts` — the schedule, the arithmetic, and the owner's real October

**File:** `web/lib/sean/cash.test.ts` (new file)
**Change:** the whole file.
**Code:**

```ts
import { describe, expect, it } from 'vitest';
import {
  cashUsd, depositDates, depositedIdr, depositedUsd, netSpentUsd, OWNER_MONTHLY, OWNER_USD_IDR,
  type CashFlowOrder, type ContributionSchedule,
} from './cash';

/** The owner's own plan, started the day he first followed RAW. */
const OWNER: ContributionSchedule = { ...OWNER_MONTHLY, startDate: '2026-10-07' };

describe('depositDates', () => {
  it('the start day, then every 25th after it', () => {
    expect(depositDates(OWNER, '2026-11-02')).toEqual(['2026-10-07', '2026-10-25']);
    expect(depositDates(OWNER, '2027-01-04')).toEqual([
      '2026-10-07', '2026-10-25', '2026-11-25', '2026-12-25',
    ]);
  });

  it('rolls the year over', () => {
    expect(depositDates(OWNER, '2027-02-01')).toContain('2027-01-25');
  });

  it('nothing before the start day, one deposit on it', () => {
    expect(depositDates(OWNER, '2026-10-06')).toEqual([]);
    expect(depositDates(OWNER, '2026-10-07')).toEqual(['2026-10-07']);
    expect(depositDates(OWNER, '2026-10-24')).toEqual(['2026-10-07']);
    expect(depositDates(OWNER, '2026-10-25')).toEqual(['2026-10-07', '2026-10-25']);
  });

  it('a start day that is itself the 25th gets one deposit, not two', () => {
    const s: ContributionSchedule = { ...OWNER, startDate: '2026-10-25' };
    expect(depositDates(s, '2026-11-01')).toEqual(['2026-10-25']);
    expect(depositDates(s, '2026-11-25')).toEqual(['2026-10-25', '2026-11-25']);
  });

  it('refuses a schedule it cannot honour every month', () => {
    expect(() => depositDates({ ...OWNER, dayOfMonth: 31 }, '2027-01-01')).toThrow(/1 to 28/);
    expect(() => depositDates({ ...OWNER, startDate: '7 Oct 2026' }, '2027-01-01')).toThrow(/YYYY-MM-DD/);
  });
});

describe('depositedIdr and depositedUsd', () => {
  it('the owner’s real rupiah: 10M to start, +5M on each 25th', () => {
    expect(depositedIdr(OWNER, '2026-10-24')).toBe(10_000_000);
    expect(depositedIdr(OWNER, '2026-11-02')).toBe(15_000_000);
    expect(depositedIdr(OWNER, '2026-12-01')).toBe(20_000_000);
  });

  it('converts at the rate it is given, to the cent', () => {
    // 17,841 IDR/USD: the rate paper_state.initial_cash_usd = 560.5067 was written at
    expect(depositedUsd(OWNER, '2026-10-24', OWNER_USD_IDR)).toBeCloseTo(560.51, 2);
    expect(depositedUsd(OWNER, '2026-11-02', OWNER_USD_IDR)).toBeCloseTo(840.76, 2);
  });

  it('refuses a rate that is not a positive number', () => {
    expect(() => depositedUsd(OWNER, '2026-11-02', 0)).toThrow(/usdIdr/);
    expect(() => depositedUsd(OWNER, '2026-11-02', Number.NaN)).toThrow(/usdIdr/);
  });
});

describe('netSpentUsd', () => {
  it('buys take money out, sells put it back, fees already inside totalUsd', () => {
    const orders: CashFlowOrder[] = [
      { side: 'buy', totalUsd: 28.03 },
      { side: 'buy', totalUsd: 28.03 },
      { side: 'sell', totalUsd: 10.0 },
    ];
    expect(netSpentUsd(orders)).toBeCloseTo(46.06, 2);
    expect(netSpentUsd([])).toBe(0);
  });
});

describe('cashUsd: the owner’s real wallet', () => {
  /** His real 7 Oct follow-through: 20 buys of $27.90 of stock + $0.13 of fees each. */
  const OCT_BUYS: CashFlowOrder[] = Array.from({ length: 20 }, () => ({ side: 'buy' as const, totalUsd: 28.03 }));

  it('on 2 November the wallet holds the 25 October deposit', () => {
    const cash = cashUsd({ schedule: OWNER, through: '2026-11-02', usdIdr: OWNER_USD_IDR, orders: OCT_BUYS });
    expect(cash).toBeCloseTo(280.16, 2);
  });

  it('holdings + cash equals the deposits less the fees paid', () => {
    const cash = cashUsd({ schedule: OWNER, through: '2026-11-02', usdIdr: OWNER_USD_IDR, orders: OCT_BUYS });
    const holdings = 558.0; // 20 x $27.90 of stock
    const fees = 2.6; // 20 x $0.13
    expect(holdings + cash).toBeCloseTo(840.76 - fees, 2);
  });

  it('on 8 October he had spent 9 cents more than he had deposited', () => {
    const cash = cashUsd({ schedule: OWNER, through: '2026-10-08', usdIdr: OWNER_USD_IDR, orders: OCT_BUYS });
    expect(cash).toBeCloseTo(-0.09, 2);
  });

  it('a sale after the start day funds the plan, as the real PLTR sale did', () => {
    const withSale: CashFlowOrder[] = [...OCT_BUYS, { side: 'sell', totalUsd: 100 }];
    const cash = cashUsd({ schedule: OWNER, through: '2026-10-08', usdIdr: OWNER_USD_IDR, orders: withSale });
    expect(cash).toBeCloseTo(99.91, 2);
  });
});
```

**Impact:** 12 new tests in one new file.

---

### Step 8: `view.test.ts` — the new captions

**File:** `web/app/sean/plan/view.test.ts:1-6` (import) and `:108-117`
**Change:** `planSizeLine` takes three arguments now; `cashLine` is new.

**8a. The import, `:1-6`.** Add `cashLine` to the existing named import list from `'./view'`.

**8b. Replace the `planSizeLine and outsideLine` test, `:108-117`:**

```ts
  it('planSizeLine, cashLine and outsideLine', () => {
    expect(planSizeLine(560, 560, 280.16)).toContain('the amount you set');
    expect(planSizeLine(838.16, null, 280.16)).toContain('$558.00 in stocks and $280.16 in cash');
    expect(planSizeLine(558, null, null)).toContain('what the plan holds now');
    expect(planSizeLine(null, null, null)).toContain('Set how much');

    expect(cashLine(838.16, 280.16, null)).toBe('$558.00 in stocks + $280.16 cash');
    expect(cashLine(838.16, 280.16, 560)).toBeNull(); // the owner typed a size: no split to show
    expect(cashLine(558, null, null)).toBeNull();
    expect(cashLine(null, null, null)).toBeNull();

    // usd() takes an absolute value (format.ts:6): a negative wallet must keep its sign
    // NOTE: the minus below is U+2212 (format.ts:1 MINUS), not a hyphen.
    expect(cashLine(557.91, -0.09, null)).toBe('$558.00 in stocks + −$0.09 cash');
    expect(planSizeLine(557.91, null, -0.09)).toContain('−$0.09 in cash');

    expect(outsideLine([], '2026-10-07')).toBeNull();
    expect(outsideLine(['NVDA', 'SPY'], '2026-10-07')).toBe(
      'You also hold NVDA and SPY from before Wed, Oct 7. They are not part of this plan, so Sean never asks you to sell them.',
    );
  });
```

**Impact:** the exact strings depend on `lib/format.ts`'s `usd()`. If `usd(558)` renders
`'$558.00'`, the assertions above hold as written; if it renders differently, use the same
`usd()` in the expectation rather than a literal. Check once with
`npx vitest run app/sean/plan/view.test.ts` and adjust the two literals only.

---

## Assumptions

Things this phase takes as given, and from whom.

**About phase 5 (`engine/src/seer_engine/sim/contributions.py`).** Its plan file did not exist when
this one was written (`.workflows/plan/gotrade-fee-rebuild/` was empty at 09:22 WIB), so `cash.ts`
mirrors the semantics the index's Phase 5 entry and Decision D6 fix, not its field names. The mirror
asserts exactly four things:

*Reconciler, 2026-10-08: all four were checked against `phase-5.md` after it was written, and all
four hold. Phase 5 defines `ContributionSchedule(amount_idr: Decimal, day_of_month: int = 25)` with
`OWNER_MONTHLY = ContributionSchedule(Decimal("5000000"), 25)` and `dates_in(first, last)` over
calendar dates; the only correction needed was the constant's name, done above. The engine's
`backtest.runner.INITIAL_IDR` also moves to `Decimal("10000000")` in phase 5, so assumption 1 is now
true on both sides of the system rather than only in `paper/capital.py`.*

1. The opening capital is **10,000,000 IDR** (`paper/capital.py:11 PAPER_INITIAL_IDR`, already in
   the tree) and the recurring contribution is **+5,000,000 IDR**.
2. The recurring deposit is dated **the 25th of the month, as a calendar date** (D6).
3. A deposit is **money in the wallet from its own date**. Phase 5 then lets the NYSE calendar
   decide which session first spends it; Sean has no market calendar and reports the wallet, so it
   stops at the calendar date. These are the same rule read for two different questions — see the
   `cash.ts` module comment, which says so.
4. The opening deposit lands on the plan's **start date**, and recurring deposits land on every
   25th **strictly after** it.

If phase 5 lands any of these differently, the fix is local: the constants and the comment in
`cash.ts`, plus the dates in `cash.test.ts`. No other file moves. **Nothing in this phase imports,
reads or builds any Python.**

**About phase 6 (`db/migrations/016_contributions.sql`).** The brief suggested preferring a table
phase 6 might add over a second source of truth. This phase deliberately does **not** take that
option, for two reasons. (a) Phase 6's table records deposits into **paper**, whose books are the
engine's simulated ones; Sean's wallet is the owner's **real** Gotrade account, and the two are
different money — paper is paused at zero stepped sessions (invariant 2), so its deposit rows would
be empty on 2 November anyway. (b) The brief's own specification is a **schedule**, "not a monthly
manual entry", and a schedule in one declared constant is a smaller surface than a table the owner
has to remember to write to. Should phase 6's table turn out to hold the owner's real deposits
rather than paper's, swapping `depositedUsd` for a query is a change to `planData.ts` alone, because
`cashUsd` already takes the deposit total through a pure function. Recorded in **Handoffs**.

**About phase 9.** No overlap exists: Sean is `web/app/sean/`, phase 9 is `web/app/(app)/`. See
*A correction to the phase brief*.

**About phase 2.** `lib/sera/lab.test.ts` is red on `main` and stays red until phase 2 lands. It is
not touched and not counted against this phase's exit criteria.

---

## Verification

**Build:**
```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild/web && npx tsc --noEmit
```
Must be clean, exit 0 — that is the baseline measured above, so any error is this phase's.

**Tests:**
```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild/web && npx vitest run
```
Expected after this phase: **47 test files** (46 baseline + `cash.test.ts`) and **596 tests**
(578 passing baseline + 12 new in `cash.test.ts` + 5 new in the *holdings plus cash* block + 1 new in
the resizing block; the extra assertions folded into existing `it` blocks do not change the count).

**The number that matters is not the total — it is that the only failure is `lib/sera/lab.test.ts`,
phase 2's.** If anything under `lib/sean/` or `app/sean/` fails, it is yours.

Narrower, while working:
```
cd /home/miftah/.worktrees/seer/gotrade-fee-rebuild/web && npx vitest run lib/sean app/sean
```
Must be **0 failed**.

**Never** run vitest with `-o addopts` or any config override, and never replace
`web/node_modules` with a symlink — it is hardlinked in this worktree, and a symlink passes vitest
and `tsc` and then kills `next build` with a misleading "filesystem root" error.

**Manual check** (the one that matters, because the owner reads this page himself):
`/sean/plan` shows a **Plan size** tile reading about `$838.16` with `$558.00 in stocks + $280.16
cash` under it, and the buy reminders below it each read about **`$41.91`**, not `$27.90`. Sells
still come before buys. Read the page top to bottom out loud: there must be no step where a number
has to be added to another number before it can be typed into Gotrade.

**Exit criteria:**
1. `planSize` is `holdings + cash` when cash is derivable, `holdings` when it is not, and
   `budget_usd` whenever the owner has set one.
2. Cash is derived from the schedule and the plan's orders, and **no code path reads a balance off
   a receipt** — `ledger.ts` is unmodified.
3. `MIN_TRADE_USD` is 25, and its comment states the derivation
   (`trading_min / (2 × trading_rate)`) rather than the number.
4. Every reminder amount is in **dollars**; no share count is ever asked for (sells say "Sell all
   N shares", which is a position, not an order size — unchanged).
5. The rotation list works without same-day reuse of sale proceeds: the phase's own test asserts
   `needed ($209.54) < cash ($280.16)`.
6. `npx tsc --noEmit` clean; `npx vitest run lib/sean app/sean` 0 failed.

---

## Handoffs

Work found and deliberately left.

- **A deposit the owner actually made, that the schedule does not know about** (he skipped a month,
  added extra, or withdrew). Today the lever is `sean_link.budget_usd`, which this phase keeps
  working. A proper fix is a deposits table the owner can write to from `/sean/plan`. That is a
  migration, and migrations 016 and 017 belong to **phases 6 and 12**; a Sean deposits table would
  be 018 and belongs to a later plan set. Not started here.
- **If phase 6's `016_contributions.sql` turns out to record the owner's *real* deposits rather than
  paper's simulated ones**, `planData.ts` should read them instead of deriving from the schedule.
  The seam is already there: `cashUsd` takes the deposit total through a pure function, so only
  `planState` changes. **For phase 6 / the reconciler:** nothing in this phase blocks on that, and
  this phase makes no claim on 016.
- **The idle cash in month 2.** Measured above: about $210 sits uninvested for a month because the
  15 kept names are each $14.01 short of their new slot, under the $25 floor, and the floor is right
  to refuse 15 trades costing $1.95 to deploy $210. It resolves itself by month 3 (slot $56.05, gap
  $28.15, over the floor). If the owner would rather be fully invested, the single lever is
  `MIN_TRADE_USD` and the arithmetic to redo is in *Measured inputs* §2 of this file. Left as it is,
  deliberately, because the settled sub-decision was to tune the floor against the fee curve.
- **Sizing new buys to absorb the whole free cash** (rather than `weight × planSize`) would deploy
  that $210 in the rotation itself. It is a change to how the **engine** weights a book, not to how
  Sean reports it, and Sean must keep mirroring the engine or the two diverge. Not this phase, and
  arguably not this plan set.
- **`RESIZING_RULES` (`reminders.ts:38-49`) will need the phase 12 successor rule ids appended** when
  the rebuilt roster lands, exactly as the two `-gotrade` twins were appended for Sean phase 7. This
  phase does not touch the list because phase 12's ids do not exist yet. **For phase 12:** if your
  successor entries use new `rules_id` values, add them to `RESIZING_RULES` and to
  `cadence.ts:8-13 SPLIT_CADENCE_RULES`; both files say in their comments that they are hand
  mirrors.
- **`db/migrations/015_sean.sql:47-53`'s comment on `budget_usd`** ("NULL = the plan's current
  value") is now one word out of date — NULL means "derive it from holdings and cash". Changing a
  migration that has already been applied is not something this phase does, and the authoritative
  wording now lives in `ReminderInput.budgetUsd`'s own doc comment. Noted, not fixed.

---

## Rollback

This phase is one commit on `feature/gotrade-fee-rebuild`; `git revert` it. It is independently
revertible (plan index, Rollback: "Phases 1, 2, 3, 9, 10 and 11 are independently revertible"), and
the revert is genuinely clean:

- No migration, no schema change, no data written. `sean_link.budget_usd` keeps the meaning it has
  today, so a reverted tree reads every existing row correctly.
- No engine file, so phases 4, 5, 6, 7 and 12 are unaffected either way.
- The two new files (`cash.ts`, `cash.test.ts`) disappear with nothing importing them.
- `MIN_TRADE_USD` returns to 10 and the resizing tests to their $10-era figures in the same revert,
  because both live in this commit.

The only visible consequence of a revert is that the owner's buys are sized from holdings again, and
he goes back to typing a number into **Plan size in dollars** (`PlanSettings.tsx:20-24`) each month
— the manual step this phase exists to remove, which is still there and still works.
