// Pure helpers for /sean/plan: the plain sentences the page and its forms show, and the form
// input rules. No data access; relative imports only (vitest has no `@/` alias).
import { sharesLabel } from '../../../components/roster';
import { picksMonthlySizesWeekly } from '../../../lib/cadence';
import { shortDate, signedUsd, usd } from '../../../lib/format';
import type { Reminder } from '../../../lib/sean/reminders';

/** What a form shows after the owner saves. */
export type FormState = { tone: 'idle' | 'ok' | 'error'; message: string };

export const IDLE: FormState = { tone: 'idle', message: '' };
export const NOT_ALLOWED: FormState = { tone: 'error', message: 'Only the owner can change the plan.' };
export const WRITE_FAILED: FormState = {
  tone: 'error', message: 'The plan could not be saved just now. Nothing changed; try again in a moment.',
};
export const BAD_METHOD: FormState = {
  tone: 'error', message: 'Pick one of the methods on the list. Only methods still on the roster can be followed.',
};
export const BAD_DATE: FormState = { tone: 'error', message: 'Pick the day your plan started, like Oct 7, 2026.' };
export const BAD_BUDGET: FormState = {
  tone: 'error', message: 'Type the plan size in dollars, like 560, or leave it empty.',
};
export const BAD_OPENING: FormState = {
  tone: 'error',
  message: 'Type the cash you started with in dollars, like 555.69, or leave it empty.',
};
export const NOT_LINKED: FormState = { tone: 'error', message: 'Sean is not following a method right now. Pick one first.' };
export const SAVED: FormState = { tone: 'ok', message: 'Saved. The reminders below use it now.' };

export const linkedState = (short: string): FormState => ({
  tone: 'ok', message: `Following ${short}. Its reminders are below.`,
});

/** The largest plan size the form takes, in dollars. */
export const MAX_BUDGET = 10_000_000;

/** A YYYY-MM-DD that is a real calendar day in 2000 or later, else null. */
export function parseSince(raw: unknown): string | null {
  if (typeof raw !== 'string') return null;
  const v = raw.trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return null;
  const d = new Date(`${v}T00:00:00Z`);
  if (Number.isNaN(d.getTime()) || d.toISOString().slice(0, 10) !== v) return null;
  return v >= '2000-01-01' ? v : null;
}

/** The plan size field: empty -> null (use what the plan holds); '$1,000.5' -> 1000.5; else bad. */
export function parseBudget(raw: unknown): { ok: true; value: number | null } | { ok: false } {
  if (raw === null || raw === undefined) return { ok: true, value: null };
  if (typeof raw !== 'string') return { ok: false };
  const v = raw.replace(/[\s$,]/g, '');
  if (v === '') return { ok: true, value: null };
  if (!/^\d+(\.\d+)?$/.test(v)) return { ok: false };
  const n = Number(v);
  if (!Number.isFinite(n) || n <= 0 || n > MAX_BUDGET) return { ok: false };
  return { ok: true, value: Math.round(n * 100) / 100 };
}

/** A ticker as stored: 1-12 of A-Z, 0-9, '.', '-'. */
export function parseSymbol(raw: unknown): string | null {
  if (typeof raw !== 'string') return null;
  const v = raw.trim().toUpperCase();
  return /^[A-Z0-9.-]{1,12}$/.test(v) ? v : null;
}

export function parseSide(raw: unknown): 'buy' | 'sell' | null {
  return raw === 'buy' || raw === 'sell' ? raw : null;
}

/** '$27.90' under $100, '$1,045' from $100 up: an amount to type into Gotrade, roughly. */
export function aboutUsd(v: number): string {
  return v >= 100 ? `$${Math.round(v).toLocaleString('en-US')}` : usd(v);
}

/** 'RAW · Unbraked momentum' -> 'Unbraked momentum'; a name without a middle dot is kept. */
export function methodTitle(name: string): string {
  const i = name.indexOf('·');
  const rest = i < 0 ? '' : name.slice(i + 1).trim();
  return rest === '' ? name : rest;
}

/** 'A', 'A and B', 'A, B and C'. */
export function joinWords(words: readonly string[]): string {
  if (words.length <= 1) return words[0] ?? '';
  return `${words.slice(0, -1).join(', ')} and ${words[words.length - 1]}`;
}

export type Cadence = 'monthly' | 'weekly' | 'daily' | null;

/** How often a rule set picks, from its id (engine sim/rules.py presets). */
export function cadenceOf(rulesId: string | null): Cadence {
  if (!rulesId) return null;
  if (rulesId.startsWith('monthly-')) return 'monthly';
  if (rulesId.startsWith('weekly-')) return 'weekly';
  if (rulesId.startsWith('daily-') || rulesId.startsWith('swing-')) return 'daily';
  return null;
}

/** When the method picks next, in words. */
export function nextPickWords(rulesId: string | null): string {
  if (picksMonthlySizesWeekly(rulesId)) return 'at the start of next month, and checks sizes every week';
  const c = cadenceOf(rulesId);
  if (c === 'monthly') return 'at the start of next month';
  if (c === 'weekly') return 'next week';
  if (c === 'daily') return 'on the next market day';
  return 'when it next decides';
}

/** The page lede once a method is followed and has picked. */
export function picksLine(p: {
  short: string; sessionDate: string; pending: boolean; count: number; rulesId: string | null;
}): string {
  const head = `${p.short} picked ${p.count === 1 ? '1 stock' : `${p.count} stocks`} for ${shortDate(p.sessionDate)}.`;
  return p.pending
    ? `${head} Its paper book buys them at that day's open; you can follow any time from then.`
    : `${head} It picks again ${nextPickWords(p.rulesId)}.`;
}

/** The reminder itself: 'Buy about $28.00 of MU'. */
export function reminderTitle(r: Reminder): string {
  if (r.action === 'buy') return r.usd === null ? `Buy ${r.symbol}` : `Buy about ${aboutUsd(r.usd)} of ${r.symbol}`;
  if (r.action === 'add') return `Buy about ${aboutUsd(r.usd ?? 0)} more of ${r.symbol}`;
  if (r.action === 'trim') return `Sell about ${aboutUsd(r.usd ?? 0)} of ${r.symbol}`;
  const shares = r.shares === null ? '' : ` ${sharesLabel(r.shares)}`;
  const about = r.usd !== null && r.usd > 0 ? ` (about ${aboutUsd(r.usd)})` : '';
  return `Sell all${shares} of ${r.symbol}${about}`;
}

/** The line under it: why. */
export function reminderDetail(r: Reminder, short: string): string {
  if (r.action === 'buy') {
    const base = `One of ${short}'s picks, and not in your plan yet.`;
    const outside = r.alsoOutside ? ` The ${r.symbol} you bought before this plan is not counted.` : '';
    const size = r.usd === null ? ' Set a plan size below to see how much.' : '';
    return base + outside + size;
  }
  if (r.action === 'add') return `In your plan, but about ${aboutUsd(r.usd ?? 0)} below its share.`;
  if (r.action === 'trim') return `In your plan, but about ${aboutUsd(r.usd ?? 0)} above its share.`;
  const keep = r.alsoOutside ? ` Sell only these; keep the ${r.symbol} you had before this plan.` : '';
  return `${short} no longer picks it.${keep}`;
}

/**
 * What the wallet can actually put into this one right now, in the owner's words; '' when the
 * question does not apply (a sell, a trim, a reminder already done, or no wallet to spend).
 *
 * `Reminder.fundedUsd` is filled by `reminders.fund`, which walks the open buys in RANK ORDER and
 * shrinks the one the cash runs out on -- the engine's own rule -- so the top picks go in whole and
 * the tail is what waits. A remainder under the fee floor is left unspent on purpose: Gotrade's
 * $0.10 minimum makes a tiny order mostly fee, and it is worth more rolled into the next deposit.
 */
export function fundedLine(r: Reminder): string {
  if (r.fundedUsd === null || r.usd === null) return '';
  if (r.fundedUsd <= 0) return 'Your spare cash will not stretch to this one. It waits for the next deposit, or for a sale to settle.';
  if (r.fundedUsd >= r.usd) return 'Your spare cash covers this in full.';
  return `Your spare cash covers about ${aboutUsd(r.fundedUsd)} of it. Buy that much now; the rest can wait for the next deposit or a sale to settle.`;
}

/** Why a done reminder is done. */
export function doneLine(r: Reminder, sessionDate: string): string {
  if (r.done === 'mark') return 'You marked this done.';
  return `You ${r.side === 'buy' ? 'bought' : 'sold'} ${r.symbol} on or after ${shortDate(sessionDate)}.`;
}

/** 'Nothing to do' / '1 thing to do' / '3 things to do'. */
export function todoLabel(n: number): string {
  if (n === 0) return 'Nothing to do';
  return n === 1 ? '1 thing to do' : `${n} things to do`;
}

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

/** The note about holdings from before the plan; null when there are none. */
export function outsideLine(symbols: readonly string[], since: string): string | null {
  if (symbols.length === 0) return null;
  return `You also hold ${joinWords(symbols)} from before ${shortDate(since)}. They are not part of this plan, so Sean never asks you to sell them.`;
}
