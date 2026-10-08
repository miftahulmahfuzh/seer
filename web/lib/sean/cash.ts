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
